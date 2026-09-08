// SoC top level: Ibex, the system fabric, the memories, the peripheral
// bridge and the two device tables.
//
// This is the first thing in this project that is a system rather than a
// block. What it is and is not:
//
//   IS   the memory map of regmap/memmap.yaml, decoded by soc_bus.v,
//        with the four implemented regions behind real slaves and
//        everything else answered by the error slave.
//   IS   a working boot path: the core resets into the ROM at the
//        address the map derives, fetches from one slave, reads and
//        writes data in another, and reaches its peripherals through an
//        APB bridge.
//   IS PARTLY hardened, and the list is worth being exact about because
//        this line said "IS NOT hardened. No ECC, no scrubbing, no TMR,
//        no bus error latch ... the BUSSTAT and SCRUB slots in the map
//        are reserved and empty" until docs/55, by which time four
//        documents had made most of it false. What is protected today:
//        the architectural register file carries a SECDED codec and a
//        scrub (docs/43); the watchdog's persistent state is a
//        triple-redundant word (docs/41); BUSSTAT is implemented and
//        counts what those two mechanisms absorb (docs/44); and the NPU
//        connection carries bounded waits on its transport and its
//        register window plus a triple-redundant control and cause bank
//        (docs/55); the time base is a SECDED codeword (docs/58); and
//        as of docs/67 EVERY ROW OF THE RAM AND THE BOOT ROM carries a
//        SECDED check field, is corrected on read, answers an
//        uncorrectable word with a bus error, and is walked by a
//        scrubber -- soc_mem_ecc.v, under both soc_mem.v and
//        soc_mem_sram.v, reporting into the SCRUB slot the map reserved
//        for it (soc_scrub.v). What is NOT: the core is still
//        SecureIbex = 0 with no lockstep, the fabric and the timers are
//        unprotected, and the NPU's transport, event engine and queue
//        storage are single points by the decision docs/52 measured
//        and docs/55 section 6 records. THE RAM IS 32 KiB, not 64: the
//        same four macros hold one protected word per row, and docs/67
//        section 3 is why that was cheaper than a seventh.
//   IS   interruptible, and the interrupts are real. soc_clint.v drives
//        irq_timer_i and irq_software_i, soc_gptimer.v and soc_uart.v
//        drive fast local interrupt lines the generated map assigns, and
//        the watchdog drives irq_nm_i. There is still no PLIC and
//        irq_external_i is tied low; docs/40 section 3 is the argument
//        for why that is a decision and not an omission, and the PLIC
//        region stays reserved and faulting.
//   IS   resettable BY ITSELF. rst_ni is now the POWER-ON reset. The
//        system reset the rest of this file runs on is derived from it
//        and from the watchdog's stage-2 request, so the SoC can reset
//        its own core while the watchdog keeps the evidence. See the
//        reset section below.
//   IS NOT the whole map. Four regions and ten peripheral slots are
//        reserved and unimplemented. An access to any of them takes a
//        bus error, on purpose: docs/39-soc-bus-and-memory-map.md
//        section 8 lists them.
//   HAS  one spacecraft interface, as of docs/65: a GRGPIO-shaped
//        16-pin GPIO port (soc_gpio.v) in the slot the map reserved for
//        it since docs/39, on the fast interrupt line docs/40 assigned
//        it. It is this project's own RTL and it is here first so that
//        the slot-to-driver-to-program path was walked once on a block
//        with no third-party dependency before any bus bridge is
//        written. The pins leave this module as three wires per pin
//        because there is no pad ring.
//   BOOTS FROM FLASH, as of docs/68. The boot ROM holds a LOADER, not
//        a program: it initialises every word of the RAM so the codec's
//        check bits exist before anything reads them, copies a
//        checksummed image out of the QSPI flash through soc_qspi.v,
//        and jumps to it. soc_boot.v is the BOOTREG slot the map has
//        carried reserved since docs/39 -- the bootstrap pins as they
//        were sampled, a boot counter no software can write, and a boot
//        report and an epoch word that survive the reset they describe.
//        The escalation when an image cannot be loaded is the
//        WATCHDOG's, reached by the loader declining to kick it; there
//        is no second ladder. docs/68 is the argument.
//   HAS  the one interface the NPU itself needs, as of docs/66: a
//        register-mode QSPI flash controller with two chip selects
//        (soc_qspi.v) in the QSPICTL slot on fast line 9. Software
//        drives flash transactions through it and the bring-up program
//        loads the NPU's weight image from a modelled flash through
//        it. The two execute-in-place windows QSPI3 and QSPI4 stay
//        reserved and faulting; soc_qspi.v's header says why.
//   IS   a NEUROMORPHIC SoC, as of docs/51-npu-integration.md.
//        soc_npu.v instantiates hw/rtl/pilot_top.v -- the frozen
//        TTIHP26b submission, unmodified -- reaches its register bank
//        over the same four serial pins the die will have, drives its
//        parallel AER port for events, and answers the 256 MiB NPU
//        window and the NPUCFG peripheral slot that the map has carried
//        empty since docs/39.
//
// SecureIbex IS FIXED AT 0, which is the owner's decision rather than
// this file's default: docs/38 section 10 item 4 records `small-pmp`
// chosen on 2026-08-31, RV32IMC plus PMP, no lockstep and no shadow
// register file.
//
// It also cannot be flipped here even if that decision were revisited.
// ibex_top.sv line 41 makes MemECC follow SecureIbex, so turning it on
// changes the MEMORY INTERFACE CONTRACT: the core then requires seven
// SECDED check bits alongside every instruction and data word and raises
// alert_major_bus_o on the first fetch without them -- docs/38 section
// 7.4 is the bring-up record of exactly that failure, where it presented
// as a catastrophic lockstep mismatch and was a missing testbench
// feature. The memories store check bits since docs/67, but NOT Ibex's:
// theirs are per BYTE LANE (four (16,8) codewords per RAM row) and per
// word for the ROM, corrected inside the memory and never carried
// across the fabric, whereas MemECC wants Ibex's own (39,32) delivered
// end to end on the bus. The integrity inputs stay tied to zero and are
// unused at SecureIbex = 0; docs/67 section 9 says what end-to-end
// integrity would still cost.

`timescale 1ns / 1ps

module soc_top #(
    // Simulation image for the boot ROM. Empty means an all-zero ROM,
    // which the core will fetch as a compressed illegal instruction and
    // trap on, rather than propagate x.
    parameter ROM_INIT = "",

    // ---- the memory pipeline, docs/50 ----
    //
    // MEM_RDREG puts one register stage on the RAM's and the boot ROM's
    // read return -- soc_mem's RDREG, and in the SRAM build the only
    // measured mechanism that splits the macro's 9.5277 ns read arc away
    // from the 26 standard-cell stages that follow it.
    //
    // IT DEFAULTS TO 0, so this file elaborates the SoC docs/47 to
    // docs/49 measured unless something asks otherwise, and
    // sw/tests/test_soc_memory_guards.py enforces the default. The
    // fabric needs NO parameter to go with it: soc_bus.v's protocol
    // already allows a response one or more cycles after the grant, and
    // docs/50 section 3 measures that its one conservatism -- refusing a
    // grant in the cycle a response returns -- is unreachable in this
    // SoC because Ibex's own NUM_REQS equals the fabric's MAX_OUT.
    parameter MEM_RDREG = 1'b0,

    // ---- the memory codec and the scrubber, docs/67 ----
    //
    // MEM_HARDEN puts hw/soc/rtl/soc_mem_ecc.v under both memories: a
    // SECDED check field on every row, correction on read, a bus error
    // on an uncorrectable word, and a scrubber. IT DEFAULTS TO 1 AND
    // NOTHING IN THE DESIGN MAY SET IT TO 0; sw/tests enforces that, as
    // it does for the watchdog's and the CLINT's HARDEN. The unprotected
    // configuration exists so that the codec's cost can be measured
    // from the same files (docs/41 section 6.5's rule) and for the
    // fault-injection counterfactual, and for nothing else.
    //
    // ROM_HARDEN follows MEM_HARDEN and exists for one measurement:
    // the ROM's check-bit macros have no place in docs/61's floorplan,
    // so the layout of docs/67 section 5 is taken with the RAM
    // protected and the ROM as docs/47 built it. A flow that sets it
    // is a measurement configuration and not the design.
    parameter integer MEM_HARDEN = 1,
    parameter integer ROM_HARDEN = MEM_HARDEN,
    // The scrubbers' interval at reset: idle cycles between scrub
    // reads. 255 walks the 8,192-row RAM in about 2.1 million cycles
    // when the bus is idle and costs one macro read in 256 cycles;
    // soc_scrub.v's header says why it ships enabled. A campaign sets
    // 0 through the same parameter.
    parameter [15:0] SCRUB_IVL_RST = 16'd255,

    // The GPIO port width. 16 is what the frozen map's slot description
    // and docs/01 section 4 say; soc_gpio.v accepts 2..32.
    parameter integer GPIO_NBITS = 16,

    // QSPI chip selects. Two, as GR801 has (docs/03 section 2.2); the
    // second one's cost is measured in docs/66 section 8.
    parameter integer QSPI_NCS = 2,

    // ---- the boot flow, docs/68 ----
    //
    // Bootstrap pins into soc_boot.v, sampled once when power-on reset
    // releases and reported through BOOTREG.BSTRAP. Four of them, and
    // the boot flow's software convention for what each one means is in
    // hw/soc/tb/sw/soc_boot.h -- nothing in the hardware acts on any of
    // them, which is soc_boot.v's header's point.
    parameter integer BOOT_NSTRAP = 4,
    // The boot attempt limit, reported through BOOTREG.BSTAT and
    // reachable by no register. Three, and soc_boot.v says why that
    // number and WDOG_ESCALATE = 2 go together.
    parameter integer BOOT_LIMIT = 3,

    // ---- the second and third clock gates, docs/76 ----
    //
    // CLKGATE puts an `sg13g2_lgcp_1` on the fabric's clock and another
    // on the accelerator's, driven by each block's own `clk_en_o`. IT
    // DEFAULTS TO 1 AND NOTHING IN THE DESIGN MAY SET IT TO 0; sw/tests
    // enforces that, as it does for MEM_HARDEN and for the watchdog's
    // and the CLINT's HARDEN. The ungated configuration exists so that
    // the gates' cost can be measured from the same files -- docs/41
    // section 6.5's rule -- and so that the bit-exact equivalence of the
    // two configurations is a measurement rather than an argument, and
    // for nothing else.
    //
    // ONE PARAMETER, TWO DOMAINS, deliberately. They wake for different
    // reasons and are proved by different means -- soc_bus.v's enable by
    // k-induction, soc_npu.v's by measurement over a frozen die -- but
    // there is no configuration in which one is wanted and the other is
    // not, and a second parameter would be a second thing to get wrong.
    parameter integer CLKGATE = 1
) (
    input  wire        clk_i,
    // POWER-ON reset. Asynchronously asserted, and the only reset the
    // watchdog obeys.
    input  wire        rst_ni,

    // Watchdog bootstrap pin. Held low in this SoC; a board that ties it
    // high has no watchdog and WDOGSTAT.DISABLED says so.
    input  wire        wdog_dis_i,

    // Boot bootstrap pins, docs/68. Sampled once by soc_boot.v when
    // power-on reset releases and reported, never acted on in hardware.
    // tb_soc.v ties them to the board's configuration.
    input  wire [BOOT_NSTRAP-1:0] strap_i,

    output wire        uart_tx_o,
    output wire        uart_irq_o,

    // ---- the GPIO pins, docs/65 ----
    // Three wires per pin, because there is no pad ring: what the pad
    // sees, what it should drive, and whether it should drive.
    // hw/soc/tb/tb_soc.v models the pad and a board with a loopback.
    input  wire [GPIO_NBITS-1:0] gpio_i,
    output wire [GPIO_NBITS-1:0] gpio_o,
    output wire [GPIO_NBITS-1:0] gpio_oe_o,
    output wire        gpio_irq_o,     // GPIO IFLAG AND IMASK, a level

    // ---- the QSPI flash pins, docs/66 ----
    // SCK and the chip selects are outputs; each of the four IO lanes
    // is three wires, as the GPIO pins are, because there is no pad
    // ring. hw/soc/tb/tb_soc.v resolves them on a pulled-up net and
    // hangs a modelled flash on chip select 0.
    output wire        qspi_sck_o,
    output wire [QSPI_NCS-1:0] qspi_cs_no,
    output wire [3:0]  qspi_io_o,
    output wire [3:0]  qspi_io_oe_o,
    input  wire [3:0]  qspi_io_i,
    output wire        qspi_irq_o,     // QSPI IEN AND (DONE OR DR), a level

    // ---- observation, for the testbench and for pins later ----
    output wire        wdog_no,        // watchdog stage 3, active low
    output wire        wdog_rst_o,     // watchdog stage 2 is asserting
    output wire        nmi_o,          // watchdog stage 1 is pending
    output wire        irq_timer_o,    // CLINT mtime >= mtimecmp
    output wire        irq_soft_o,     // CLINT msip
    output wire        gptimer_irq_o,  // GPTIMER shared timer interrupt
    output wire        npu_irq_o,      // NPUCFG cause AND mask

    // The die's own pins, brought out so a testbench or a scope sees
    // exactly what an external pilot would see. Nothing in the SoC
    // reads them back.
    output wire        npu_ser_sck_o,
    output wire        npu_ser_cs_n_o,
    output wire        npu_ser_mosi_o,
    output wire        npu_ser_miso_o,
    output wire        npu_aer_in_stb_o,
    output wire        npu_aer_out_vld_o,

    output wire        alert_minor_o,
    output wire        alert_major_internal_o,
    output wire        alert_major_bus_o,
    output wire        double_fault_seen_o,
    output wire        core_sleep_o
);

`include "soc_memmap.vh"

  // -------------------------------------------------------------------
  // Reset
  // -------------------------------------------------------------------
  //
  // Two domains. rst_ni is the power-on reset and reaches only the
  // watchdog. Everything else runs on rst_sys_n, which the watchdog can
  // pull -- that is its stage 2, and it is the reason its own state has
  // to be outside this domain (soc_wdog.v W4).
  //
  // The synchroniser is not decoration. rst_req is a registered signal
  // in this clock domain, so rst_sys_n would otherwise DEASSERT on a
  // clock edge, which is a recovery-time violation at every flop in the
  // SoC. Asynchronous assert, synchronous deassert, two stages.
  wire wdog_rst_req;
  wire rst_raw_n = rst_ni && !wdog_rst_req;

  reg [1:0] rst_sync;
  always @(posedge clk_i or negedge rst_raw_n)
    if (!rst_raw_n) rst_sync <= 2'b00;
    else            rst_sync <= {rst_sync[0], 1'b1};

  wire rst_sys_n = rst_sync[1];

  assign wdog_rst_o = wdog_rst_req;

  localparam integer RAM_WORDS = SOC_SIZE_RAM / 4;
  localparam integer ROM_WORDS = SOC_SIZE_ROM / 4;
  // The ROM image is linked at the reset vector, not at the region base,
  // so it loads that many words in.
  localparam integer ROM_INIT_WORD = (SOC_RESET_VECTOR - SOC_BASE_ROM) / 4;

  // -------------------------------------------------------------------
  // Core
  // -------------------------------------------------------------------
  wire        instr_req, instr_gnt, instr_rvalid, instr_err;
  wire [31:0] instr_addr, instr_rdata;

  // Interrupt sources, declared here because the core below consumes
  // them and the blocks that drive them are instantiated further down.
  wire        clint_irq_timer, clint_irq_soft;
  wire        gptimer_irq, uart_irq, wdog_nmi, busstat_irq, npu_irq;
  wire        gpio_irq, qspi_irq;
  // The fault lines soc_busstat counts. docs/44.
  wire [2:0]  rf_ecc_err;      // from the register file, via ibex_top
  wire        wdog_tmr_ev;     // from the watchdog's voter
  // The NPU connection's three, added by docs/55. docs/52 section 10
  // measured 79 upsets absorbed by mechanisms that worked and visible to
  // nothing; these are the wires that end that.
  wire        npu_cor_ev;      // a queue pointer vote corrected
  wire        npu_det_ev;      // a queue entry was discarded
  wire        npu_tmr_ev;      // the NPU cause bank's voter masked one
  // The CLINT's, added by docs/58 H6: the stored mtime codeword was not a
  // codeword this cycle. One event per cycle by construction at the
  // source, because the codeword is re-encoded on every edge.
  wire        clint_mt_ecc_ev;
  // The memories', added by docs/67: repaired by the scrubber, read
  // corrected, and uncorrectable, with the offset of the last of those.
  // They go to soc_scrub.v and not to soc_busstat.v, whose sticky field
  // is full; soc_scrub.v's header says so.
  wire        ram_sec_ev, ram_rd_ev, ram_ded_ev;
  wire        rom_sec_ev, rom_rd_ev, rom_ded_ev;
  wire [31:0] ram_ded_addr, rom_ded_addr;
  wire        scrub_ram_en, scrub_rom_en;
  wire [15:0] scrub_ivl;
  wire        scrub_irq;

  // -------------------------------------------------------------------
  // The fast local interrupt vector
  //
  // Every index below is a generated constant from regmap/memmap.yaml,
  // so the wire a peripheral lands on, the mie bit a driver sets, the
  // mcause it reads and the vector-table slot crt0.S fills all come from
  // one source. An unassigned line is driven low: Ibex's inputs are
  // level-sensitive, and a floating one would be an interrupt whose
  // source does not exist.
  //
  // The UART's line is connected here for the first time. Note what its
  // interrupt MEANS: soc_uart.v raises it whenever the transmit holding
  // register is empty and CTRL.TI is set, which is GRLIB's
  // transmitter-ready semantics -- a LEVEL that is high almost always.
  // Software that sets TI without a handler that clears it gets an
  // interrupt storm, and the bring-up program deliberately never sets
  // it.
  // -------------------------------------------------------------------
  reg [14:0] irq_fast;
  always @(*) begin
    irq_fast = 15'h0;
    irq_fast[SOC_IRQLINE_UART0]   = uart_irq;
    irq_fast[SOC_IRQLINE_TIMER0]  = gptimer_irq;
    // BUSSTAT's line, connected here for the first time. It is a LEVEL
    // driven by soc_busstat's sticky bits AND its enable register,
    // which resets to zero -- so this wire is low until software asks
    // for it, and the whole-SoC run of docs/40 and docs/41 is
    // cycle-identical with this block present.
    irq_fast[SOC_IRQLINE_BUSSTAT] = busstat_irq;
    // The NPU's line, connected here for the first time. docs/40 froze
    // this source number and this wire index before either end existed;
    // nothing spare is spent, because NPUCFG was one of the thirteen
    // sources that document assigned. Its level is |(cause & mask) and
    // the mask resets to zero, so the wire is low until software asks
    // for it -- the same discipline BUSSTAT follows and the reason the
    // pre-NPU whole-SoC run is reproducible with this block present.
    irq_fast[SOC_IRQLINE_NPUCFG]  = npu_irq;
    // The GPIO's line, connected here for the first time (docs/65).
    // docs/40 assigned source 4 and line 2 before the block existed;
    // nothing spare is spent. Its level is |(IFLAG & IMASK) and IMASK
    // resets to zero, so the wire is low until software asks for it --
    // the same discipline BUSSTAT and NPUCFG follow, and the reason the
    // whole-SoC run of docs/56 is cycle-identical with this block
    // present and the program unchanged.
    irq_fast[SOC_IRQLINE_GPIO]    = gpio_irq;
    // The QSPI controller's line, connected here for the first time
    // (docs/66). docs/40 assigned source 21 and line 9 before the block
    // existed. Its level is IEN AND (DONE OR DR) and IEN resets to
    // zero, so the wire is low until software asks for it -- the same
    // discipline as every line above, and the reason the whole-SoC run
    // of docs/65 is cycle-identical with this block present and the
    // program unchanged.
    irq_fast[SOC_IRQLINE_QSPICTL] = qspi_irq;
    // The memory scrubber's line, connected here for the first time
    // (docs/67). docs/40 assigned source 23 and line 11 before the
    // block existed. Its level is |(sticky & IRQEN) and IRQEN resets to
    // zero, so the wire is low until software asks for it -- the same
    // discipline as every line above.
    irq_fast[SOC_IRQLINE_SCRUB]   = scrub_irq;
  end


  wire        data_req, data_gnt, data_rvalid, data_err, data_we;
  wire [3:0]  data_be;
  wire [31:0] data_addr, data_wdata, data_rdata;

  // Parameter values are the integer encodings from
  // ext/ibex/rtl/ibex_pkg.sv, the same ones hw/soc/flow/syn_ibex.sh
  // gives Yosys and hw/soc/tb/ibex_min_system.v uses, so the simulated
  // and the synthesised configurations cannot drift apart. This is the
  // small-pmp configuration of docs/38 section 3.1.
  //   BaseIsa 0 = RV32I,  RV32M 2 = RV32MFast,
  //   RV32B   0 = none,   RV32ZC 0 = Zca,   RegFile 0 = FF
  ibex_top #(
      .BaseIsa         (0),
      .PMPEnable       (1),
      .PMPGranularity  (0),
      .PMPNumRegions   (4),
      .MHPMCounterNum  (0),
      .MHPMCounterWidth(40),
      .RV32E           (0),
      .RV32M           (2),
      .RV32B           (0),
      .RV32ZC          (0),
      .RegFile         (0),
      .BranchTargetALU (0),
      .WritebackStage  (0),
      .ICache          (0),
      .ICacheECC       (0),
      .BranchPredictor (0),
      .DbgTriggerEn    (0),
      .SecureIbex      (0),
      .ICacheScramble  (0)
  ) u_ibex (
      .clk_i  (clk_i),
      .rst_ni (rst_sys_n),
      .test_en_i(1'b0),

      .ram_cfg_icache_tag_i  (24'h0),
      .ram_cfg_icache_tag_o  (),
      .ram_cfg_icache_data_i (24'h0),
      .ram_cfg_icache_data_o (),

      // ibex_pkg::IbexMuBiOff = 4'b1010: the CHERIoT half of this
      // dual-ISA core is held off.
      .cheriot_enable_i (4'b1010),

      .hart_id_i             (32'h0),
      .boot_addr_i           (SOC_BOOT_ADDR),
      .trvk_heap_base_addr_i (32'h0),

      .instr_req_o        (instr_req),
      .instr_gnt_i        (instr_gnt),
      .instr_rvalid_i     (instr_rvalid),
      .instr_addr_o       (instr_addr),
      .instr_rdata_i      (instr_rdata),
      .instr_rdata_intg_i (7'h0),
      .instr_err_i        (instr_err),

      .data_req_o        (data_req),
      .data_gnt_i        (data_gnt),
      .data_rvalid_i     (data_rvalid),
      .data_we_o         (data_we),
      .data_be_o         (data_be),
      .data_addr_o       (data_addr),
      .data_wdata_o      (data_wdata),
      .data_wdata_intg_o (),
      .data_tag_o        (),
      .data_rdata_i      (data_rdata),
      .data_rdata_intg_i (7'h0),
      .data_tag_i        (1'b0),
      .data_err_i        (data_err),

      .trvk_revbm_req_o        (),
      .trvk_revbm_gnt_i        (1'b0),
      .trvk_revbm_rvalid_i     (1'b0),
      .trvk_revbm_addr_o       (),
      .trvk_revbm_rdata_i      (32'h0),
      .trvk_revbm_rdata_intg_i (7'h0),
      .trvk_revbm_err_i        (1'b0),

      // Interrupts. irq_external_i is the one that is still tied low:
      // it is the PLIC's input and there is no PLIC (docs/40 section 3).
      // Leaving it unconnected rather than repurposing it is what makes
      // adding one later a wiring change and not a rework.
      .irq_software_i (clint_irq_soft),
      .irq_timer_i    (clint_irq_timer),
      .irq_external_i (1'b0),
      .irq_fast_i     (irq_fast),
      .irq_nm_i       (wdog_nmi),

      .scramble_key_valid_i (1'b0),
      .scramble_key_i       (128'h0),
      .scramble_nonce_i     (64'h0),
      .scramble_req_o       (),

      .debug_req_i         (1'b0),
      .crash_dump_o        (),
      .double_fault_seen_o (double_fault_seen_o),

      // ibex_pkg::IbexMuBiOn = 4'b0101
      .fetch_enable_i        (4'b0101),
      .mcounteren_writable_i (4'b1010),

      // This project's port, added to ibex_top by
      // hw/soc/flow/ibex_fault_port.py. It is connected
      // UNCONDITIONALLY and without an `ifdef: a build that forgot to
      // ask for the patched top fails here, at elaboration, with the
      // port's name in the message. docs/44 section 4.
      .rf_ecc_err_o           (rf_ecc_err),

      .alert_minor_o          (alert_minor_o),
      .alert_major_internal_o (alert_major_internal_o),
      .alert_major_bus_o      (alert_major_bus_o),
      .core_sleep_o           (core_sleep_o),

      .scan_rst_ni (1'b1),

      .lockstep_cmp_en_o        (),
      .data_req_shadow_o        (),
      .data_we_shadow_o         (),
      .data_be_shadow_o         (),
      .data_addr_shadow_o       (),
      .data_wdata_shadow_o      (),
      .data_wdata_intg_shadow_o (),
      .instr_req_shadow_o       (),
      .instr_addr_shadow_o      ()
  );

  // -------------------------------------------------------------------
  // Fabric
  // -------------------------------------------------------------------
  wire [5:0]  s_req;
  wire [31:0] s_addr, s_wdata;
  wire        s_we;
  wire [3:0]  s_be;
  wire [5:0]  s_gnt, s_rvalid, s_err;
  wire [31:0] s_rdata_ram, s_rdata_rom, s_rdata_apb, s_rdata_pnp,
              s_rdata_clint, s_rdata_npu;

  // -------------------------------------------------------------------
  // The second and third clock gates
  //
  // docs/57 found the FIRST one -- `u_ibex.core_clock_gate_i.u_icg`,
  // bound by hw/soc/rtl/prim_clock_gating.v, covering 2,323 of the
  // design's flip-flops -- and measured that the part idles at 16.3 %
  // of its busy power because of it. docs/61 section 7.3 then measured
  // that every one of the 2,178 flip-flops the accelerator brought is
  // on the UNGATED net, so that gate now covers 44.1 % of the design
  // rather than 79.9 %. These two are the answer to that.
  //
  // WHAT IS GATED AND WHAT IS NOT, with the reason in one line each:
  //
  //   u_bus     GATED. Its enable is proved complete by k-induction
  //             (soc_bus_props.v F10), so the gated fabric and the
  //             ungated one have the same state in every cycle and F1
  //             to F9 -- the fairness bound F9 included -- transport
  //             unchanged. That proof is the whole price of the gate.
  //   u_npu     GATED, as one domain including the frozen die. Its
  //             enable is conservative and measured rather than proved,
  //             for the reason soc_npu.v's own section gives.
  //   u_clint   NOT GATED, AND IT CANNOT BE. TICK_DIV = 1, so `mtime`
  //             increments and its SECDED codeword is re-encoded on
  //             every single clock edge (docs/58 H6). A complete enable
  //             for this block is the constant 1, and an incomplete one
  //             stops the architectural time base -- which is not a
  //             power saving, it is a different device. docs/57 section
  //             7.3 measured it as 52.4 % of all idle switching, so it
  //             is the largest single target in the SoC and it is the
  //             one that must not be taken.
  //   u_timer0  NOT GATED, same reason at a smaller size: the GPTIMER
  //             prescaler and the watchdog counter advance every cycle
  //             by construction. 24.6 % of idle switching.
  //   u_uart0   NOT GATED: the baud divider free-runs. 23.0 %.
  //   the rest  NOT GATED HERE. u_apb, u_pnp, u_gpio, u_qspi, u_scrub,
  //             u_busstat, u_boot and the two memories carry 237 of the
  //             468 non-core flip-flop bits docs/57 section 7.3 counted
  //             and 0.02 % of the idle switching between them. Each
  //             needs its own completeness argument and buys a share of
  //             a number that is already almost zero; docs/76 section
  //             14 ranks them and this document does not take them.
  //
  // The gates are instantiated HERE and not inside the two blocks, so
  // that every property in hw/soc/formal/ is still a property of a
  // module on an ungated clock. soc_bus.v's header says why that
  // matters and F10 is what makes it sound.
  wire bus_clk_en, npu_clk_en;
  wire clk_bus, clk_npu;

  generate
  if (CLKGATE != 0) begin : g_clkgate
    prim_clock_gating u_bus_cg (
        .clk_i     (clk_i),
        .en_i      (bus_clk_en),
        .test_en_i (1'b0),
        .clk_o     (clk_bus)
    );
    prim_clock_gating u_npu_cg (
        .clk_i     (clk_i),
        .en_i      (npu_clk_en),
        .test_en_i (1'b0),
        .clk_o     (clk_npu)
    );
  end else begin : g_noclkgate
    assign clk_bus = clk_i;
    assign clk_npu = clk_i;
    wire _unused_cg = &{1'b0, bus_clk_en, npu_clk_en, 1'b0};
  end
  endgenerate

  soc_bus u_bus (
      .clk_i  (clk_bus),
      .rst_ni (rst_sys_n),
      .clk_en_o (bus_clk_en),

      .mi_req_i    (instr_req),
      .mi_addr_i   (instr_addr),
      .mi_gnt_o    (instr_gnt),
      .mi_rvalid_o (instr_rvalid),
      .mi_rdata_o  (instr_rdata),
      .mi_err_o    (instr_err),

      .md_req_i    (data_req),
      .md_addr_i   (data_addr),
      .md_we_i     (data_we),
      .md_be_i     (data_be),
      .md_wdata_i  (data_wdata),
      .md_gnt_o    (data_gnt),
      .md_rvalid_o (data_rvalid),
      .md_rdata_o  (data_rdata),
      .md_err_o    (data_err),

      .s_req_o     (s_req),
      .s_addr_o    (s_addr),
      .s_we_o      (s_we),
      .s_be_o      (s_be),
      .s_wdata_o   (s_wdata),
      .s_gnt_i     (s_gnt),
      .s_rvalid_i  (s_rvalid),
      .s_rdata_0_i (s_rdata_ram),
      .s_rdata_1_i (s_rdata_rom),
      .s_rdata_2_i (s_rdata_apb),
      .s_rdata_3_i (s_rdata_pnp),
      .s_rdata_4_i (s_rdata_clint),
      .s_rdata_5_i (s_rdata_npu),
      .s_err_i     (s_err)
  );

  // -------------------------------------------------------------------
  // Slave 0: RAM.  Slave 1: boot ROM.
  // -------------------------------------------------------------------
  //
  // The RAM holds four (16,8) byte codewords per row and the ROM one
  // (39,32) word codeword; soc_mem_ecc.v says why the two differ and
  // soc_mem_sram.v says which macros hold which. Both scrub under
  // soc_scrub.v's control and report into it.
  soc_mem #(.WORDS(RAM_WORDS), .RO(1'b0), .RDREG(MEM_RDREG),
            .HARDEN(MEM_HARDEN), .ECC_BYTE(1'b1)) u_ram (
      .clk_i (clk_i), .rst_ni (rst_sys_n),
      .req_i (s_req[0]), .addr_i (s_addr), .we_i (s_we),
      .be_i (s_be), .wdata_i (s_wdata),
      .gnt_o (s_gnt[0]), .rvalid_o (s_rvalid[0]),
      .rdata_o (s_rdata_ram), .err_o (s_err[0]),
      .scrub_en_i (scrub_ram_en), .scrub_ivl_i (scrub_ivl),
      .sec_o (ram_sec_ev), .rd_o (ram_rd_ev), .ded_o (ram_ded_ev),
      .evt_addr_o (ram_ded_addr)
  );

  soc_mem #(.WORDS(ROM_WORDS), .RO(1'b1), .RDREG(MEM_RDREG),
            .INIT_FILE(ROM_INIT), .INIT_WORD(ROM_INIT_WORD),
            .HARDEN(ROM_HARDEN), .ECC_BYTE(1'b0)) u_rom (
      .clk_i (clk_i), .rst_ni (rst_sys_n),
      .req_i (s_req[1]), .addr_i (s_addr), .we_i (s_we),
      .be_i (s_be), .wdata_i (s_wdata),
      .gnt_o (s_gnt[1]), .rvalid_o (s_rvalid[1]),
      .rdata_o (s_rdata_rom), .err_o (s_err[1]),
      .scrub_en_i (scrub_rom_en), .scrub_ivl_i (scrub_ivl),
      .sec_o (rom_sec_ev), .rd_o (rom_rd_ev), .ded_o (rom_ded_ev),
      .evt_addr_o (rom_ded_addr)
  );

  // -------------------------------------------------------------------
  // Slave 2: peripheral bus bridge
  // -------------------------------------------------------------------
  wire        psel, penable, pwrite;
  wire [19:0] paddr;
  wire [31:0] pwdata;
  wire [3:0]  pstrb;
  wire [31:0] prdata;
  wire        pready, pslverr;

  soc_apb_bridge u_apb (
      .clk_i (clk_i), .rst_ni (rst_sys_n),
      .req_i (s_req[2]), .addr_i (s_addr), .we_i (s_we),
      .be_i (s_be), .wdata_i (s_wdata),
      .gnt_o (s_gnt[2]), .rvalid_o (s_rvalid[2]),
      .rdata_o (s_rdata_apb), .err_o (s_err[2]),
      .psel_o (psel), .penable_o (penable), .paddr_o (paddr),
      .pwrite_o (pwrite), .pwdata_o (pwdata), .pstrb_o (pstrb),
      .prdata_i (prdata), .pready_i (pready), .pslverr_i (pslverr)
  );

  // pstrb is generated by the bridge and carried to the peripherals, but
  // neither peripheral implements sub-word writes: both are register
  // files whose registers are written whole. Named so the unused signal
  // is a decision rather than an oversight.
  wire _unused_pstrb = &{1'b0, pstrb, 1'b0};

  // ---- slot decode ----
  //
  // The slot constants come from the generated map. This is the only
  // place in the RTL that knows which slot a peripheral occupies, and
  // sw/tests/test_memmap.py's
  // test_top_level_decodes_the_implemented_apb_slots checks it against
  // the generated Python map rather than against this file.
  wire [7:0] slot = paddr[19:12];

  wire sel_uart0  = psel && (slot == SOC_APBSLOT_UART0);
  wire sel_gpio   = psel && (slot == SOC_APBSLOT_GPIO);
  wire sel_qspi   = psel && (slot == SOC_APBSLOT_QSPICTL);
  wire sel_timer0 = psel && (slot == SOC_APBSLOT_TIMER0);
  wire sel_busstat = psel && (slot == SOC_APBSLOT_BUSSTAT);
  wire sel_scrub  = psel && (slot == SOC_APBSLOT_SCRUB);
  wire sel_bootreg = psel && (slot == SOC_APBSLOT_BOOTREG);
  wire sel_npucfg = psel && (slot == SOC_APBSLOT_NPUCFG);
  wire sel_apbpnp = psel && (slot == SOC_APBSLOT_APBPNP);
  wire sel_none   = psel && !sel_uart0 && !sel_gpio && !sel_qspi
                         && !sel_timer0 && !sel_busstat && !sel_scrub
                         && !sel_bootreg && !sel_npucfg && !sel_apbpnp;

  wire [31:0] prdata_uart0, prdata_timer0, prdata_apbpnp, prdata_busstat,
              prdata_npucfg, prdata_gpio, prdata_qspi, prdata_scrub,
              prdata_bootreg;
  wire        pready_uart0, pready_timer0, pready_apbpnp, pready_busstat,
              pready_npucfg, pready_gpio, pready_qspi, pready_scrub,
              pready_bootreg;
  wire        pslverr_uart0, pslverr_timer0, pslverr_apbpnp, pslverr_busstat,
              pslverr_npucfg, pslverr_gpio, pslverr_qspi, pslverr_scrub,
              pslverr_bootreg;

  soc_uart u_uart0 (
      .clk_i (clk_i), .rst_ni (rst_sys_n),
      .psel_i (sel_uart0), .penable_i (penable), .paddr_i (paddr[11:0]),
      .pwrite_i (pwrite), .pwdata_i (pwdata),
      .prdata_o (prdata_uart0), .pready_o (pready_uart0),
      .pslverr_o (pslverr_uart0),
      .tx_o (uart_tx_o), .irq_o (uart_irq)
  );

  // The GPIO port, docs/65. GRGPIO's register map (grip.pdf table 923)
  // in the slot the map has reserved for it since docs/39. Its input
  // path is two synchroniser flops from gpio_i and nothing else: DATA
  // reads the pad, not the OUTPUT register, so a read-back goes through
  // whatever is outside this module -- soc_gpio.v's header says why.
  soc_gpio #(.NBITS(GPIO_NBITS)) u_gpio (
      .clk_i (clk_i), .rst_ni (rst_sys_n),
      .psel_i (sel_gpio), .penable_i (penable), .paddr_i (paddr[11:0]),
      .pwrite_i (pwrite), .pwdata_i (pwdata),
      .prdata_o (prdata_gpio), .pready_o (pready_gpio),
      .pslverr_o (pslverr_gpio),
      .gpio_i (gpio_i), .gpio_o (gpio_o), .gpio_oe_o (gpio_oe_o),
      .irq_o (gpio_irq)
  );

  // The QSPI flash controller, docs/66. Register mode, two chip
  // selects, in the QSPICTL slot the map has reserved since docs/39;
  // the XIP windows in front of it stay reserved. Its lanes leave this
  // module as three wires each and meet a modelled flash in tb_soc.v.
  soc_qspi #(.NCS(QSPI_NCS)) u_qspi (
      .clk_i (clk_i), .rst_ni (rst_sys_n),
      .psel_i (sel_qspi), .penable_i (penable), .paddr_i (paddr[11:0]),
      .pwrite_i (pwrite), .pwdata_i (pwdata),
      .prdata_o (prdata_qspi), .pready_o (pready_qspi),
      .pslverr_o (pslverr_qspi),
      .sck_o (qspi_sck_o), .cs_no (qspi_cs_no),
      .io_o (qspi_io_o), .io_oe_o (qspi_io_oe_o), .io_i (qspi_io_i),
      .irq_o (qspi_irq)
  );

  // GRLIB GPTIMER register map, two general timers, and the watchdog as
  // the last timer -- docs/08 section 3 row 8. IRQ_NUM comes from the
  // generated map so the number this block reports in its configuration
  // register is the same number the device table carries.
  //
  // WDOG_PRESCALE and WDOG_WIDTH together fix the longest timeout the
  // watchdog can ever be programmed to, which is the property soc_wdog.v
  // W2 requires to be a constant of the netlist rather than a register:
  //   (2^16) * 16 = 1,048,576 clocks, about 10.5 ms at 100 MHz.
  soc_gptimer #(
      .NGEN            (2),
      .TWIDTH          (32),
      .SWIDTH          (16),
      .IRQ_NUM         (SOC_IRQNUM_TIMER0),
      .WDOG_WIDTH      (16),
      .WDOG_PRESCALE   (16),
      .WDOG_RST_CYCLES (16),
      .WDOG_ESCALATE   (2)
  ) u_timer0 (
      .clk_i (clk_i), .rst_ni (rst_sys_n), .rst_por_ni (rst_ni),
      .psel_i (sel_timer0), .penable_i (penable), .paddr_i (paddr[11:0]),
      .pwrite_i (pwrite), .pwdata_i (pwdata),
      .prdata_o (prdata_timer0), .pready_o (pready_timer0),
      .pslverr_o (pslverr_timer0),
      .wdog_dis_i (wdog_dis_i),
      .irq_o (gptimer_irq), .nmi_o (wdog_nmi),
      .rst_req_o (wdog_rst_req), .wdog_no (wdog_no),
      .tmr_ev_o (wdog_tmr_ev)
  );

  // The counters that make a corrected upset observable. docs/43
  // section 12 item 1 and docs/41 section 10 item 3, in the slot the
  // frozen map has reserved for them since docs/39.
  //
  // Two resets, and they are different on purpose: the RECORD is in the
  // power-on domain so a watchdog stage-2 reset cannot erase the
  // evidence of what caused it, and the INTERRUPT ENABLE is in the
  // system domain so the fresh boot after that reset is not immediately
  // interrupted by a sticky bit it has not read yet (docs/40 section
  // 7.2's brick, in a new place).
  soc_busstat u_busstat (
      .clk_i (clk_i), .rst_ni (rst_sys_n), .rst_por_ni (rst_ni),
      .psel_i (sel_busstat), .penable_i (penable), .paddr_i (paddr[11:0]),
      .pwrite_i (pwrite), .pwdata_i (pwdata),
      .prdata_o (prdata_busstat), .pready_o (pready_busstat),
      .pslverr_o (pslverr_busstat),
      .rf_ecc_err_i (rf_ecc_err),
      .tmr_ev_i (wdog_tmr_ev),
      .npu_cor_i (npu_cor_ev),
      .npu_det_i (npu_det_ev),
      .npu_tmr_i (npu_tmr_ev),
      .mt_ecc_i (clint_mt_ecc_ev),
      .irq_o (busstat_irq)
  );

  // The memory codec's counters and the scrubbers' control, docs/67, in
  // the SCRUB slot the map has reserved since docs/39. The same two
  // reset domains as BUSSTAT, for the same reasons, and the control
  // register in the system domain so a watchdog reset restores the
  // scrubbers' defaults.
  soc_scrub #(.IVL_RST(SCRUB_IVL_RST)) u_scrub (
      .clk_i (clk_i), .rst_ni (rst_sys_n), .rst_por_ni (rst_ni),
      .psel_i (sel_scrub), .penable_i (penable), .paddr_i (paddr[11:0]),
      .pwrite_i (pwrite), .pwdata_i (pwdata),
      .prdata_o (prdata_scrub), .pready_o (pready_scrub),
      .pslverr_o (pslverr_scrub),
      .ram_sec_i (ram_sec_ev), .ram_rd_i (ram_rd_ev),
      .ram_ded_i (ram_ded_ev), .ram_addr_i (ram_ded_addr),
      .rom_sec_i (rom_sec_ev), .rom_rd_i (rom_rd_ev),
      .rom_ded_i (rom_ded_ev), .rom_addr_i (rom_ded_addr),
      .ram_en_o (scrub_ram_en), .rom_en_o (scrub_rom_en),
      .ivl_o (scrub_ivl),
      .irq_o (scrub_irq)
  );

  // The boot flow's register block, docs/68, in the BOOTREG slot the map
  // has reserved since docs/39.
  //
  // Two resets again, and this block is the extreme case of the split
  // soc_busstat.v and soc_scrub.v use: EVERYTHING in it is in the
  // power-on domain, because everything in it is either a pin sampled
  // once at power-on or a record that has to survive the reset it
  // describes. The system reset is an INPUT to the logic and resets
  // nothing -- its release is what the boot counter counts. soc_boot.v's
  // header is the argument, and the reason this cannot be docs/40
  // section 7.2's brick is that no output of this block reaches the
  // watchdog, the memories or the fabric.
  soc_boot #(.NSTRAP(BOOT_NSTRAP), .LIMIT(BOOT_LIMIT)) u_boot (
      .clk_i (clk_i), .rst_ni (rst_sys_n), .rst_por_ni (rst_ni),
      .psel_i (sel_bootreg), .penable_i (penable), .paddr_i (paddr[11:0]),
      .pwrite_i (pwrite), .pwdata_i (pwdata),
      .prdata_o (prdata_bootreg), .pready_o (pready_bootreg),
      .pslverr_o (pslverr_bootreg),
      .strap_i (strap_i), .wdog_dis_i (wdog_dis_i)
  );

  soc_apb_pnp u_apbpnp (
      .psel_i (sel_apbpnp), .penable_i (penable), .paddr_i (paddr[11:0]),
      .pwrite_i (pwrite), .pwdata_i (pwdata),
      .prdata_o (prdata_apbpnp), .pready_o (pready_apbpnp),
      .pslverr_o (pslverr_apbpnp)
  );

  // A slot nobody occupies must still complete, or the bridge hangs and
  // the core hangs with it. It completes with PSLVERR, so an access to a
  // reserved peripheral slot is a bus error at the core rather than a
  // read of zero that looks like a working register.
  assign prdata  = sel_uart0   ? prdata_uart0
                 : sel_gpio    ? prdata_gpio
                 : sel_qspi    ? prdata_qspi
                 : sel_timer0  ? prdata_timer0
                 : sel_busstat ? prdata_busstat
                 : sel_scrub   ? prdata_scrub
                 : sel_bootreg ? prdata_bootreg
                 : sel_npucfg  ? prdata_npucfg
                 : sel_apbpnp  ? prdata_apbpnp
                 : 32'h0;
  assign pready  = sel_uart0   ? pready_uart0
                 : sel_gpio    ? pready_gpio
                 : sel_qspi    ? pready_qspi
                 : sel_timer0  ? pready_timer0
                 : sel_busstat ? pready_busstat
                 : sel_scrub   ? pready_scrub
                 : sel_bootreg ? pready_bootreg
                 : sel_npucfg  ? pready_npucfg
                 : sel_apbpnp  ? pready_apbpnp
                 : 1'b1;
  assign pslverr = sel_uart0   ? pslverr_uart0
                 : sel_gpio    ? pslverr_gpio
                 : sel_qspi    ? pslverr_qspi
                 : sel_timer0  ? pslverr_timer0
                 : sel_busstat ? pslverr_busstat
                 : sel_scrub   ? pslverr_scrub
                 : sel_bootreg ? pslverr_bootreg
                 : sel_npucfg  ? pslverr_npucfg
                 : sel_apbpnp  ? pslverr_apbpnp
                 : sel_none;

  // -------------------------------------------------------------------
  // Slave 3: system-bus device table
  // -------------------------------------------------------------------
  soc_pnp u_pnp (
      .clk_i (clk_i), .rst_ni (rst_sys_n),
      .req_i (s_req[3]), .addr_i (s_addr), .we_i (s_we),
      .be_i (s_be), .wdata_i (s_wdata),
      .gnt_o (s_gnt[3]), .rvalid_o (s_rvalid[3]),
      .rdata_o (s_rdata_pnp), .err_o (s_err[3])
  );

  // -------------------------------------------------------------------
  // Slave 4: core-local interruptor
  //
  // On the system bus and not behind the APB bridge, because the frozen
  // map makes it a region of its own at 0xE0000000 and because mtime is
  // the one register in this SoC that software reads in a loop.
  //
  // TICK_DIV = 1 makes mtime count CPU cycles, which is what lets the
  // bring-up program compute an exact deadline. A real part needs an
  // always-on time base; soc_clint.v says so.
  // -------------------------------------------------------------------
  soc_clint #(.TICK_DIV(1)) u_clint (
      .clk_i (clk_i), .rst_ni (rst_sys_n),
      .req_i (s_req[4]), .addr_i (s_addr), .we_i (s_we),
      .be_i (s_be), .wdata_i (s_wdata),
      .gnt_o (s_gnt[4]), .rvalid_o (s_rvalid[4]),
      .rdata_o (s_rdata_clint), .err_o (s_err[4]),
      .irq_timer_o (clint_irq_timer),
      .irq_software_o (clint_irq_soft),
      .mt_ecc_o (clint_mt_ecc_ev)
  );

  // -------------------------------------------------------------------
  // Slave 5, and the NPUCFG peripheral slot: the NPU subsystem
  //
  // ONE BLOCK WITH TWO BUS FACES, because configuration and events are
  // different problems and the frozen map put them in different places.
  // soc_npu.v's header is the contract; docs/51 is the argument.
  //
  // The pilot's geometry is the shuttle's: 8 neurons, 8 axons, the
  // default hw/rtl/pilot_top.v section 6 records as the configuration
  // docs/15 measured to fit the tile budget. It is written here rather
  // than left to the module's macro defaults so that a reader of the
  // SoC can see what is inside it.
  // -------------------------------------------------------------------
  soc_npu #(
      .N_NODES   (1),
      .N_NEURONS (8),
      .N_AXONS   (8),
      .SER_HALF  (2),
      .INJ_DEPTH (8),
      .CAP_DEPTH (8),
      .CLKGATE   (CLKGATE)
  ) u_npu (
      .clk_i (clk_npu), .rst_ni (rst_sys_n),
      // The gated clock for the block, and the UNGATED one for the
      // single flip-flop that holds its wake bit. docs/77 section 5:
      // the wake bit has to keep running while the block it wakes is
      // stopped, so it cannot be on `clk_npu`, and it is one flip-flop
      // rather than a second domain because `clk_npu` is `clk_i` with
      // edges removed and nothing here crosses between them.
      .clk_free_i (clk_i),
      .clk_en_o (npu_clk_en),
      .req_i (s_req[5]), .addr_i (s_addr), .we_i (s_we),
      .be_i (s_be), .wdata_i (s_wdata),
      .gnt_o (s_gnt[5]), .rvalid_o (s_rvalid[5]),
      .rdata_o (s_rdata_npu), .err_o (s_err[5]),
      .psel_i (sel_npucfg), .penable_i (penable), .paddr_i (paddr[11:0]),
      .pwrite_i (pwrite), .pwdata_i (pwdata),
      .prdata_o (prdata_npucfg), .pready_o (pready_npucfg),
      .pslverr_o (pslverr_npucfg),
      .irq_o (npu_irq),
      .q_cor_o (npu_cor_ev),
      .q_det_o (npu_det_ev),
      .cfg_tmr_o (npu_tmr_ev),
      .obs_ser_sck_o (npu_ser_sck_o),
      .obs_ser_cs_n_o (npu_ser_cs_n_o),
      .obs_ser_mosi_o (npu_ser_mosi_o),
      .obs_ser_miso_o (npu_ser_miso_o),
      .obs_aer_in_stb_o (npu_aer_in_stb_o),
      .obs_aer_out_vld_o (npu_aer_out_vld_o)
  );

  assign uart_irq_o     = uart_irq;
  assign gpio_irq_o     = gpio_irq;
  assign qspi_irq_o     = qspi_irq;
  assign npu_irq_o      = npu_irq;
  assign gptimer_irq_o  = gptimer_irq;
  assign nmi_o          = wdog_nmi;
  assign irq_timer_o    = clint_irq_timer;
  assign irq_soft_o     = clint_irq_soft;

endmodule
