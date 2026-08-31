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
//   IS NOT hardened. No ECC, no scrubbing, no TMR, no bus error latch.
//        soc_mem.v is a behavioural array; the BUSSTAT and SCRUB slots
//        in the map are reserved and empty.
//   IS NOT interruptible. There is no CLINT and no PLIC; their addresses
//        are frozen in the map and nothing decodes them. Every Ibex
//        interrupt input is tied off, which is also why the UART's
//        interrupt is brought to a port rather than connected.
//   IS NOT the whole map. Six regions and thirteen peripheral slots are
//        reserved and unimplemented. An access to any of them takes a
//        bus error, on purpose: docs/39-soc-bus-and-memory-map.md
//        section 8 lists them.
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
// feature. soc_mem.v stores no check bits, so SecureIbex here would need
// a memory subsystem that does. The integrity inputs are tied to zero
// and are unused at SecureIbex = 0.

`timescale 1ns / 1ps

module soc_top #(
    // Simulation image for the boot ROM. Empty means an all-zero ROM,
    // which the core will fetch as a compressed illegal instruction and
    // trap on, rather than propagate x.
    parameter ROM_INIT = ""
) (
    input  wire        clk_i,
    input  wire        rst_ni,

    output wire        uart_tx_o,
    output wire        uart_irq_o,

    output wire        alert_minor_o,
    output wire        alert_major_internal_o,
    output wire        alert_major_bus_o,
    output wire        double_fault_seen_o,
    output wire        core_sleep_o
);

`include "soc_memmap.vh"

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
      .rst_ni (rst_ni),
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

      // No interrupt controller in this build; see the header.
      .irq_software_i (1'b0),
      .irq_timer_i    (1'b0),
      .irq_external_i (1'b0),
      .irq_fast_i     (15'h0),
      .irq_nm_i       (1'b0),

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
  wire [3:0]  s_req;
  wire [31:0] s_addr, s_wdata;
  wire        s_we;
  wire [3:0]  s_be;
  wire [3:0]  s_gnt, s_rvalid, s_err;
  wire [31:0] s_rdata_ram, s_rdata_rom, s_rdata_apb, s_rdata_pnp;

  soc_bus u_bus (
      .clk_i  (clk_i),
      .rst_ni (rst_ni),

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
      .s_err_i     (s_err)
  );

  // -------------------------------------------------------------------
  // Slave 0: RAM.  Slave 1: boot ROM.
  // -------------------------------------------------------------------
  soc_mem #(.WORDS(RAM_WORDS), .RO(1'b0)) u_ram (
      .clk_i (clk_i), .rst_ni (rst_ni),
      .req_i (s_req[0]), .addr_i (s_addr), .we_i (s_we),
      .be_i (s_be), .wdata_i (s_wdata),
      .gnt_o (s_gnt[0]), .rvalid_o (s_rvalid[0]),
      .rdata_o (s_rdata_ram), .err_o (s_err[0])
  );

  soc_mem #(.WORDS(ROM_WORDS), .RO(1'b1),
            .INIT_FILE(ROM_INIT), .INIT_WORD(ROM_INIT_WORD)) u_rom (
      .clk_i (clk_i), .rst_ni (rst_ni),
      .req_i (s_req[1]), .addr_i (s_addr), .we_i (s_we),
      .be_i (s_be), .wdata_i (s_wdata),
      .gnt_o (s_gnt[1]), .rvalid_o (s_rvalid[1]),
      .rdata_o (s_rdata_rom), .err_o (s_err[1])
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
      .clk_i (clk_i), .rst_ni (rst_ni),
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
  // hw/soc/tb/cocotb/test_soc_apb.py checks it against the generated
  // Python map rather than against this file.
  wire [7:0] slot = paddr[19:12];

  wire sel_uart0 = psel && (slot == SOC_APBSLOT_UART0);
  wire sel_apbpnp = psel && (slot == SOC_APBSLOT_APBPNP);
  wire sel_none  = psel && !sel_uart0 && !sel_apbpnp;

  wire [31:0] prdata_uart0, prdata_apbpnp;
  wire        pready_uart0, pready_apbpnp;
  wire        pslverr_uart0, pslverr_apbpnp;

  soc_uart u_uart0 (
      .clk_i (clk_i), .rst_ni (rst_ni),
      .psel_i (sel_uart0), .penable_i (penable), .paddr_i (paddr[11:0]),
      .pwrite_i (pwrite), .pwdata_i (pwdata),
      .prdata_o (prdata_uart0), .pready_o (pready_uart0),
      .pslverr_o (pslverr_uart0),
      .tx_o (uart_tx_o), .irq_o (uart_irq_o)
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
  assign prdata  = sel_uart0  ? prdata_uart0
                 : sel_apbpnp ? prdata_apbpnp
                 : 32'h0;
  assign pready  = sel_uart0  ? pready_uart0
                 : sel_apbpnp ? pready_apbpnp
                 : 1'b1;
  assign pslverr = sel_uart0  ? pslverr_uart0
                 : sel_apbpnp ? pslverr_apbpnp
                 : sel_none;

  // -------------------------------------------------------------------
  // Slave 3: system-bus device table
  // -------------------------------------------------------------------
  soc_pnp u_pnp (
      .clk_i (clk_i), .rst_ni (rst_ni),
      .req_i (s_req[3]), .addr_i (s_addr), .we_i (s_we),
      .be_i (s_be), .wdata_i (s_wdata),
      .gnt_o (s_gnt[3]), .rvalid_o (s_rvalid[3]),
      .rdata_o (s_rdata_pnp), .err_o (s_err[3])
  );

endmodule
