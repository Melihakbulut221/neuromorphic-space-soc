// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Icarus testbench for the whole SoC: Ibex, the fabric, the memory map.
//
// The difference from tb_ibex_min.v is the point of the exercise. That
// testbench WAS the memory system -- one flat array and two magic
// addresses. This one contains no model of anything the design does. It
// supplies a clock, a reset and a ROM image, and then observes:
//
//   * the serial line out of the console UART, which it decodes back
//     into characters. The program's output therefore travels the whole
//     path -- core, fabric, APB bridge, slot decode, UART register file,
//     baud divider, shift register -- and any break anywhere in it shows
//     up as garbled or missing text. Snooping the register write instead
//     would have proved the bridge and nothing after it.
//   * core_sleep_o, which is how the program says it has finished. The
//     frozen memory map has no "halt the simulator" address and this
//     testbench does not invent one; crt0.S leaves the exit code in RAM
//     and executes WFI.
//   * the alert outputs and double_fault_seen_o, latched, as
//     tb_ibex_min.v does.
//   * since docs/68, WHERE THE CORE IS FETCHING FROM. The ROM holds a
//     loader and the program is copied into RAM out of the flash, so
//     the cycle at which instruction fetch first crosses into the RAM
//     region is the hand-over, and it splits the run into the loader's
//     cycles and the program's. Nothing gates on it; it is reported
//     because a boot flow whose cost is not attributable is a boot flow
//     nobody can argue about.
//
// AND IT MODELS A POWER-UP, WHICH IS NEW AND IS THE POINT OF docs/68
// SECTION 4. +ram_random=<seed> fills the RAM's data AND ITS SECDED
// CHECK FIELD with pseudo-random bits before reset is released, which is
// what an SRAM does. Without it soc_mem.v's model comes up all-zero with
// a valid check field derived by the frozen encoder -- a memory that is
// already initialised, which is exactly the assumption the boot flow
// exists to remove. The shipped run uses it.
//
// THE PASS CRITERION, and what it does not cover. A run passes only if
// ALL of these hold:
//
//   1. the core reached WFI, with the exit magic already posted in RAM,
//      before the timeout. The magic is part of the TERMINATION
//      condition and not only of the checks afterwards, because the SoC
//      can now reset its own core and Ibex reports core_sleep_o high
//      while it is held in reset -- so "awake, then asleep" alone goes
//      true in the middle of a watchdog reset;
//   2. the magic word beside the exit code says the exit code is
//      meaningful, so a WFI reached some other way is not mistaken for a
//      completed run;
//   3. the exit code is zero -- every self-check in the program passed;
//   4. the decoded serial stream contains "RESULT PASS", which is an
//      independent path to the same conclusion: criterion 3 reads RAM
//      through a hierarchical reference, criterion 4 reads the UART pin.
//      A fabric that corrupted peripheral writes would pass 3 and fail 4;
//      a program that lied about its own result would fail 3;
//   5. no alert asserted and double_fault_seen_o never asserted.
//
// It does NOT cover: any region or peripheral slot the map reserves and
// nothing implements (an access to one is checked as an error by the
// program, but nothing here checks that the reserved address is the
// right one); the fabric's behaviour under two masters contending, which
// this program exercises only as a by-product of running; anything at
// gate level; and any timing property at all. The cocotb suite in
// hw/soc/tb/cocotb/ is where the fabric is driven deliberately rather
// than incidentally.

`timescale 1ns / 1ps

`ifndef ROM_HEX
  `define ROM_HEX "test_ibex.hex"
`endif
`ifndef TIMEOUT_CYCLES
  `define TIMEOUT_CYCLES 5000000
`endif
// 8 * (scaler + 1) system clocks per bit, which is GRLIB's definition of
// the APBUART scaler: it feeds an 8x oversampling clock. The program
// programs the scaler from the same -D.
`ifndef UART_BIT_CYCLES
  `define UART_BIT_CYCLES 8
`endif
`ifndef EXIT_CODE_ADDR
  `define EXIT_CODE_ADDR 32'h0
`endif
`ifndef EXIT_MAGIC_ADDR
  `define EXIT_MAGIC_ADDR 32'h0
`endif
`ifndef TRAP_MCAUSE_ADDR
  `define TRAP_MCAUSE_ADDR 32'h0
`endif
`ifndef TRAP_MEPC_ADDR
  `define TRAP_MEPC_ADDR 32'h0
`endif
`ifndef TRAP_COUNT_ADDR
  `define TRAP_COUNT_ADDR 32'h0
`endif

module tb_soc;

  localparam integer CLK_HALF   = 5;     // 100 MHz, functional only
  localparam integer BIT_CYCLES = `UART_BIT_CYCLES;
  localparam integer BIT_TIME   = BIT_CYCLES * 2 * CLK_HALF;

  localparam [31:0] EXIT_CODE_ADDR  = `EXIT_CODE_ADDR;
  localparam [31:0] EXIT_MAGIC_ADDR = `EXIT_MAGIC_ADDR;
  localparam [31:0] TRAP_MCAUSE_ADDR = `TRAP_MCAUSE_ADDR;
  localparam [31:0] TRAP_MEPC_ADDR   = `TRAP_MEPC_ADDR;
  localparam [31:0] TRAP_COUNT_ADDR  = `TRAP_COUNT_ADDR;
  localparam [31:0] EXIT_MAGIC       = 32'h600d_c0de;

  reg clk   = 1'b0;
  reg rst_n = 1'b0;
  always #CLK_HALF clk = ~clk;

  // Declared here rather than beside the pass criterion because the
  // power-up model and the hand-over detector below both report in
  // cycles and Verilog wants the declaration first.
  integer cycles = 0;
  always @(posedge clk) if (rst_n) cycles = cycles + 1;

  wire uart_tx, uart_irq;
  wire wdog_n, wdog_rst, nmi, irq_timer, irq_soft, gptimer_irq;
  wire alert_minor, alert_major_internal, alert_major_bus;
  wire double_fault_seen, core_sleep;

  // -------------------------------------------------------------------
  // The GPIO pads and the board they are soldered to (docs/65).
  //
  // soc_top has no pad ring, so each pin leaves it as three wires --
  // what to drive, whether to drive, what the pad sees -- and the pad
  // is modelled HERE, as the one place outside the design where the
  // three meet. A pad whose output buffer is enabled shows the SoC's
  // own value; one whose buffer is disabled shows whatever the board
  // drives.
  //
  // The board is a loopback: pads 8..15 are wired to pads 0..7, so a
  // value the program drives on pin k arrives on pin k+8 as an INPUT.
  // That is what makes check 28 of the bring-up program a test of the
  // pin path rather than of a register: DATA reads back through the
  // pad model and the wire, never through the OUTPUT register, which
  // soc_gpio.v refuses to fold in for exactly this reason. Pins 0..7
  // are driven low by the board when the SoC does not drive them.
  //
  // Contention -- the SoC driving a looped-back pad against the pin it
  // is wired to, with a different value -- resolves to X, as it would
  // on a scope. The program never does it; a program that did would
  // read X out of DATA and fail its own check.
  // -------------------------------------------------------------------
  wire [15:0] gpio_o, gpio_oe, gpio_pad;
  wire        gpio_irq;
  genvar gp;
  generate
    for (gp = 0; gp < 8; gp = gp + 1) begin : g_pad
      assign gpio_pad[gp] = gpio_oe[gp] ? gpio_o[gp] : 1'b0;
      assign gpio_pad[gp + 8] = !gpio_oe[gp + 8]            ? gpio_pad[gp]
                              : (gpio_o[gp + 8] === gpio_pad[gp]) ? gpio_o[gp + 8]
                              : 1'bx;
    end
  endgenerate

  // -------------------------------------------------------------------
  // The QSPI flash on the board (docs/66).
  //
  // The controller's four IO lanes leave soc_top as three wires each,
  // as the GPIO pins do, and meet here on a pulled-up net: `tri1`, the
  // pull-up a board carries on /WP and /HOLD so that a released lane
  // is not a floating one. A W25Q128JV model hangs on chip select 0
  // and is loaded from +flash0=<hex>, which flow/sim_soc.sh passes and
  // flow/gen_flash_image.py writes: the byte pattern checks 29 reads
  // through the controller, and the weight image check 30 loads the
  // NPU from. Chip select 1 goes to nothing, so a frame the program
  // sent there would read the pull-ups: all ones.
  //
  // The model's busy times are scaled from milliseconds to two
  // microseconds, as in tb_soc_qspi.v, and it counts every departure
  // from the part's datasheet in `violations`; the count is printed at
  // the end and is part of the pass criterion.
  // -------------------------------------------------------------------
  wire        qspi_sck;
  wire [1:0]  qspi_cs_n;
  wire [3:0]  qspi_io_o, qspi_io_oe;
  wire        qspi_irq;
  tri1 [3:0]  qspi_io;
  genvar ql;
  generate
    for (ql = 0; ql < 4; ql = ql + 1) begin : g_qspi_lane
      assign qspi_io[ql] = qspi_io_oe[ql] ? qspi_io_o[ql] : 1'bz;
    end
  endgenerate

  flash_w25q128jv #(.T_W_NS(2000.0), .T_PP_NS(2000.0), .T_SE_NS(2000.0),
                    .T_RST_NS(2000.0)) u_flash0 (
      .cs_n (qspi_cs_n[0]), .sck (qspi_sck), .io (qspi_io)
  );

  reg [8*256-1:0] flash_fname;
  initial begin
    #1;   // after the model's own fill with FFh at time zero
    if ($value$plusargs("flash0=%s", flash_fname))
      $readmemh(flash_fname, u_flash0.mem);
    else
      $display("[TB] no +flash0= image: the flash is erased");
  end

  // -------------------------------------------------------------------
  // The bootstrap pins (docs/68).
  //
  // A board's static wiring, so a register here and not a driver: it is
  // set from +strap=<n> before reset is released and never moves again,
  // which is exactly what soc_boot.v samples. Zero is the board this
  // repository models -- boot from the flash on chip select 0 -- and the
  // NOBOOT demonstration passes 4.
  // -------------------------------------------------------------------
  reg [3:0] strap = 4'h0;
  integer   strap_arg;
  initial begin
    if ($value$plusargs("strap=%d", strap_arg)) strap = strap_arg[3:0];
  end

  // The watchdog bootstrap pin is held LOW, which is the armed state.
  // A run with it high would have no watchdog at all and every watchdog
  // check in the program would pass vacuously, so it is a constant here
  // and hw/soc/tb/cocotb/test_soc_wdog.py is where the disabled case is
  // driven.
  soc_top #(.ROM_INIT(`ROM_HEX)) dut (
      .clk_i  (clk),
      .rst_ni (rst_n),
      .wdog_dis_i (1'b0),
      .strap_i    (strap),
      .uart_tx_o  (uart_tx),
      .uart_irq_o (uart_irq),
      .gpio_i     (gpio_pad),
      .gpio_o     (gpio_o),
      .gpio_oe_o  (gpio_oe),
      .gpio_irq_o (gpio_irq),
      .qspi_sck_o   (qspi_sck),
      .qspi_cs_no   (qspi_cs_n),
      .qspi_io_o    (qspi_io_o),
      .qspi_io_oe_o (qspi_io_oe),
      .qspi_io_i    (qspi_io),
      .qspi_irq_o   (qspi_irq),
      .wdog_no       (wdog_n),
      .wdog_rst_o    (wdog_rst),
      .nmi_o         (nmi),
      .irq_timer_o   (irq_timer),
      .irq_soft_o    (irq_soft),
      .gptimer_irq_o (gptimer_irq),
      .alert_minor_o          (alert_minor),
      .alert_major_internal_o (alert_major_internal),
      .alert_major_bus_o      (alert_major_bus),
      .double_fault_seen_o    (double_fault_seen),
      .core_sleep_o           (core_sleep)
  );

  // -------------------------------------------------------------------
  // THE POWER-UP, and the one fault this testbench can inject
  //
  // +ram_random=<seed> writes pseudo-random bits into every word of the
  // RAM's data array AND its check field, at time 1 ns -- after
  // soc_mem.v's own initial blocks have zeroed the array and derived a
  // valid check field from the frozen encoder, and long before reset is
  // released 20 clocks later. That is what an SRAM comes up as, and it
  // is what makes the boot loader's RAM sweep load-bearing rather than
  // decorative: without the sweep, the first 32-bit read of a word
  // nobody has written finds three or four byte lanes that are not
  // codewords, and soc_mem_ecc.v answers it with a bus error.
  //
  // +ded_word=<index> is the other half: it flips TWO check bits of one
  // byte lane of one RAM word, on the edge after the loader writes that
  // word, which is an uncorrectable planted inside the image the loader
  // has just copied. That is the fault docs/68 section 6 escalates as
  // BOOT_CAUSE_ECC, and triggering it on the WRITE rather than at a
  // cycle number is what makes it reproducible across builds.
  //
  // +ded_skip=<n> is how many writes to that word to let past first,
  // and it DEFAULTS TO 1 rather than 0 for a reason the first run of
  // this found: the RAM SWEEP writes every word before the copy does,
  // so an injector that fired on the first write corrupted a word the
  // copy then overwrote, and the run passed while appearing to have
  // injected a fault. One skip puts the corruption after the copy's
  // write, which is where an uncorrectable in a loaded image is.
  //
  // Both reach into the codec arm's `chk` array, which does not exist
  // when the codec is off, so the whole block is behind a define that
  // flow/sim_soc.sh sets from SOC_MEM_HARDEN. A hierarchical name that
  // does not resolve is an elaboration error, not a skipped feature.
  // -------------------------------------------------------------------
  integer ram_seed;
  integer ram_i;
  reg     ram_randomised = 1'b0;
  integer ded_word = -1;
  integer ded_skip = 1;
  integer ded_seen = 0;
  reg     ded_done = 1'b0;

  initial begin
    #1;
    if ($value$plusargs("ram_random=%d", ram_seed)) begin
`ifdef RAM_POWERUP_ECC
      for (ram_i = 0; ram_i < dut.RAM_WORDS; ram_i = ram_i + 1) begin
        dut.u_ram.mem[ram_i]          = $random(ram_seed);
        dut.u_ram.g_ecc.chk[ram_i]    = $random(ram_seed);
      end
`else
      for (ram_i = 0; ram_i < dut.RAM_WORDS; ram_i = ram_i + 1)
        dut.u_ram.mem[ram_i] = $random(ram_seed);
`endif
      ram_randomised = 1'b1;
      $display("[TB] RAM powered up undefined: %0d words of data%s, seed %0d",
               dut.RAM_WORDS,
`ifdef RAM_POWERUP_ECC
               " and check bits",
`else
               " (no check field in this configuration)",
`endif
               ram_seed);
    end
  end

  initial begin
    if (!$value$plusargs("ded_word=%d", ded_word)) ded_word = -1;
    if (!$value$plusargs("ded_skip=%d", ded_skip)) ded_skip = 1;
  end

`ifdef RAM_POWERUP_ECC
  always @(posedge clk) begin
    if (rst_n && (ded_word >= 0) && !ded_done
        && dut.u_ram.g_ecc.row_en && dut.u_ram.g_ecc.row_we
        && (dut.u_ram.g_ecc.row_addr == ded_word[12:0])) begin
      if (ded_seen < ded_skip) begin
        ded_seen = ded_seen + 1;
      end else begin
      ded_done = 1'b1;
      @(posedge clk);
      dut.u_ram.g_ecc.chk[ded_word] = dut.u_ram.g_ecc.chk[ded_word] ^ 32'h3;
      $display("[TB] injected a double error into RAM word %0d at cycle %0d",
               ded_word, cycles);
      end
    end
  end
`endif

  // -------------------------------------------------------------------
  // Latched alerts. They are pulses; a run must fail if one ever fired,
  // not only if one is firing at the end. Latched separately because
  // they mean different things: alert_major_bus_o is a memory integrity
  // failure, alert_major_internal_o is a lockstep mismatch. This build
  // has SecureIbex = 0, so neither should ever fire and either firing is
  // a real finding rather than a configuration artifact.
  // -------------------------------------------------------------------
  reg saw_alert_minor     = 1'b0;
  reg saw_alert_major_int = 1'b0;
  reg saw_alert_major_bus = 1'b0;
  reg saw_double_fault    = 1'b0;
  always @(posedge clk) if (rst_n) begin
    if (alert_minor)          saw_alert_minor     <= 1'b1;
    if (alert_major_internal) saw_alert_major_int <= 1'b1;
    if (alert_major_bus)      saw_alert_major_bus <= 1'b1;
    if (double_fault_seen)    saw_double_fault    <= 1'b1;
  end

  // "The core has run and then stopped", not "the core is not running".
  //
  // core_sleep_o is ALREADY HIGH while the core is held in reset -- a
  // core that is not fetching is not busy, and Ibex says so. Waiting on
  // core_sleep_o alone therefore returns instantly on the cycle reset is
  // released, and the run reports a timeout at whatever cycle count the
  // free-running counter had reached by the time the report is printed,
  // which is a symptom that points nowhere. The first version of this
  // file did exactly that. Requiring the core to have been observed
  // awake first is the whole fix.
  reg saw_awake = 1'b0;
  always @(posedge clk) if (rst_n && !core_sleep) saw_awake <= 1'b1;

  // AND the exit magic must already be in RAM.
  //
  // That third term was added when the watchdog arrived and it is not
  // belt and braces. The SoC can now reset its own core (soc_top.v's
  // reset section), and a core held in reset reports core_sleep_o high
  // -- so "awake, then asleep" becomes true in the middle of a watchdog
  // reset, tens of thousands of cycles before the program has finished.
  // The first watchdog run ended with the testbench reporting a timeout
  // at a cycle count that meant nothing, for exactly that reason.
  // Requiring the magic word makes the criterion "the program posted its
  // result and then slept", which is what was always meant.
  wire finished = saw_awake && core_sleep &&
                  (dut.u_ram.mem[EXIT_MAGIC_ADDR[31:2]] == EXIT_MAGIC);

  // -------------------------------------------------------------------
  // The hand-over (docs/68).
  //
  // The core resets into the boot ROM and the loader runs there; the
  // image runs from RAM. So the first granted instruction fetch inside
  // the RAM region is the jump at the end of boot_crt0.S, and the cycle
  // it happens on splits the run. Recorded per boot, because the SoC can
  // reset itself and each boot runs the loader again.
  // -------------------------------------------------------------------
  integer handover_cycle = -1;
  integer handovers      = 0;
  reg     in_rom         = 1'b1;
  always @(posedge clk) if (rst_n) begin
    if (dut.instr_req && dut.instr_gnt) begin
      if (in_rom && (dut.instr_addr >= dut.SOC_BASE_RAM)
                 && (dut.instr_addr <  dut.SOC_BASE_RAM + dut.SOC_SIZE_RAM)) begin
        in_rom = 1'b0;
        handovers = handovers + 1;
        handover_cycle = cycles;
        $display("[TB] boot: handed over to RAM at cycle %0d (fetch 0x%08x)",
                 cycles, dut.instr_addr);
      end else if (!in_rom && (dut.instr_addr >= dut.SOC_BASE_ROM)) begin
        in_rom = 1'b1;     // a reset put the core back in the ROM
      end
    end
  end

  // -------------------------------------------------------------------
  // Watchdog escalation, reported as it happens.
  //
  // Not part of any pass criterion. It is here because every one of
  // these three events is invisible from the console -- stage 2 in
  // particular restarts the program, and without this line the symptom
  // is a log that simply begins again with no explanation. The first
  // watchdog bring-up run produced exactly that.
  // -------------------------------------------------------------------
  reg nmi_q = 1'b0, wdog_rst_q = 1'b0, wdog_n_q = 1'b1;
  integer wdog_stage1 = 0, wdog_stage2 = 0, wdog_stage3 = 0;
  always @(posedge clk) if (rst_n) begin
    if (nmi && !nmi_q) begin
      wdog_stage1 = wdog_stage1 + 1;
      $display("[TB] watchdog stage 1 (NMI) at cycle %0d", cycles);
    end
    if (wdog_rst && !wdog_rst_q) begin
      wdog_stage2 = wdog_stage2 + 1;
      $display("[TB] watchdog stage 2 (system reset) at cycle %0d", cycles);
    end
    if (!wdog_n && wdog_n_q) begin
      wdog_stage3 = wdog_stage3 + 1;
      $display("[TB] watchdog stage 3 (WDOGN pin) at cycle %0d", cycles);
    end
    nmi_q      <= nmi;
    wdog_rst_q <= wdog_rst;
    wdog_n_q   <= wdog_n;
  end

  // Last addresses seen on each master port, so a timeout can say WHERE
  // it stopped. A hang here is always "the program counter or a pointer
  // is somewhere unexpected", and these are the cheapest observation of
  // that -- no VCD, no reference inside the core.
  reg [31:0] last_instr_addr = 32'hffff_ffff;
  reg [31:0] last_data_addr  = 32'hffff_ffff;
  always @(posedge clk) if (rst_n) begin
    if (dut.instr_req && dut.instr_gnt) last_instr_addr <= dut.instr_addr;
    if (dut.data_req  && dut.data_gnt)  last_data_addr  <= dut.data_addr;
  end

  always @(posedge clk)
    if (rst_n && $test$plusargs("trace") && (cycles % 20000 == 0))
      $display("[TB] cycle %0d  fetch=0x%08x  data=0x%08x",
               cycles, last_instr_addr, last_data_addr);

  // -------------------------------------------------------------------
  // Every bus error, with the address that caused it.
  //
  // Not part of any pass criterion, and it costs nothing when nothing
  // errors. It exists because a bus error and a PMP violation arrive at
  // software as THE SAME `mcause` -- 5 for a load, 7 for a store -- and
  // from inside the program they are indistinguishable. This line is the
  // discriminator: a PMP violation never reaches the fabric, so an
  // `mcause 5` with no line here is the core's own permission check and
  // one with a line here is the memory or the decode. docs/68 section 10
  // needed exactly that distinction and did not have it.
  //
  // The address is the one the master issued in the cycle of the GRANT,
  // held until the response, which is what soc_bus.v's ownership queue
  // guarantees for a single outstanding request per port.
  // -------------------------------------------------------------------
  always @(posedge clk) if (rst_n && $test$plusargs("errtrace")) begin
    if (dut.data_rvalid && dut.data_err)
      $display("[ERR] cycle %0d: data error, last data address 0x%08x",
               cycles, last_data_addr);
    if (dut.instr_rvalid && dut.instr_err)
      $display("[ERR] cycle %0d: fetch error, last fetch address 0x%08x",
               cycles, last_instr_addr);
  end

  // A WINDOWED FETCH AND DATA TRACE.
  //
  // +ftrace_from=<cycle> +ftrace_to=<cycle> prints every granted
  // instruction fetch and every granted data access in that window.
  // Off by default and part of no criterion. It exists because the one
  // question a console log cannot answer is "which instructions
  // actually ran", and docs/68 section 10 needed exactly that: a check
  // that had passed from the boot ROM failed from RAM with a bus error
  // at an address no source line names, and the execution path is the
  // only thing that distinguishes a wrong pointer from a wrong branch.
  integer ftrace_from = -1, ftrace_to = -1;
  initial begin
    if (!$value$plusargs("ftrace_from=%d", ftrace_from)) ftrace_from = -1;
    if (!$value$plusargs("ftrace_to=%d", ftrace_to)) ftrace_to = -1;
  end
  always @(posedge clk)
    if (rst_n && ftrace_from >= 0 && cycles >= ftrace_from
        && cycles <= ftrace_to) begin
      if (dut.instr_req && dut.instr_gnt)
        $display("[FT] %0d I 0x%08x", cycles, dut.instr_addr);
      if (dut.data_req && dut.data_gnt)
        $display("[FT] %0d D %s 0x%08x be=%b", cycles,
                 dut.data_we ? "W" : "R", dut.data_addr, dut.data_be);
    end

  // +bustrace dumps every fabric handshake for the first BUSTRACE_CYCLES
  // cycles. Off by default and not part of any pass criterion: it is
  // here because a fabric stall is invisible from the outside -- the
  // symptom is a core that stops, with no clue which of the two masters
  // is waiting for what.
`ifndef BUSTRACE_CYCLES
  `define BUSTRACE_CYCLES 400
`endif
  always @(posedge clk)
    if (rst_n && $test$plusargs("bustrace") && cycles < `BUSTRACE_CYCLES)
      $display("[BUS] %0d I:%b%b%b %08x D:%b%b%b w%b %08x | req%b gnt%b rv%b | ci%0d/%0d cd%0d/%0d",
               cycles,
               dut.instr_req, dut.instr_gnt, dut.instr_rvalid, dut.instr_addr,
               dut.data_req, dut.data_gnt, dut.data_rvalid, dut.data_we,
               dut.data_addr,
               dut.s_req, dut.s_gnt, dut.s_rvalid,
               dut.u_bus.cnt_i, dut.u_bus.lock_i,
               dut.u_bus.cnt_d, dut.u_bus.lock_d);

  // -------------------------------------------------------------------
  // Serial receiver
  //
  // Start bit, eight data bits least significant first, one stop bit, no
  // parity -- what hw/soc/rtl/soc_uart.v transmits and what its header
  // documents. Sampling is at the middle of each bit: 1.5 bit times
  // after the falling edge of the start bit, then one bit time apart.
  //
  // The stop bit is checked. A framing error means the divider or the
  // shifter is wrong, and without the check that would show up only as
  // subtly wrong characters.
  // -------------------------------------------------------------------
  integer rx_chars = 0;
  integer rx_framing_errors = 0;
  reg [7:0] rx_byte;
  reg [87:0] rx_tail = 88'h0;      // last 11 characters
  reg rx_seen_pass = 1'b0;
  integer bit_i;

  initial begin
    @(posedge rst_n);
    // One clock so the UART's own reset has been applied and the line is
    // driven to its idle high before the first edge is looked for.
    @(posedge clk);
    forever begin
      @(negedge uart_tx);
      #(BIT_TIME + BIT_TIME / 2);
      for (bit_i = 0; bit_i < 8; bit_i = bit_i + 1) begin
        rx_byte[bit_i] = uart_tx;
        #(BIT_TIME);
      end
      // Now in the middle of the stop bit.
      if (uart_tx !== 1'b1) begin
        rx_framing_errors = rx_framing_errors + 1;
        $display("[TB] framing error after %0d characters", rx_chars);
      end
      rx_chars = rx_chars + 1;
      $write("%c", rx_byte);
      rx_tail = {rx_tail[79:0], rx_byte};
      if (rx_tail == "RESULT PASS") rx_seen_pass = 1'b1;
    end
  end

  // -------------------------------------------------------------------
  integer errors = 0;
  reg [31:0] exit_code, exit_magic;

  initial begin
    if ($test$plusargs("vcd")) begin
      $dumpfile("tb_soc.vcd");
      $dumpvars(0, tb_soc);
    end

    $display("[TB] SoC: boot 0x%08x, ROM image %s, %0d clocks per UART bit",
             dut.SOC_BOOT_ADDR, `ROM_HEX, BIT_CYCLES);

    repeat (20) @(posedge clk);
    rst_n = 1'b1;

    while (!finished && cycles < `TIMEOUT_CYCLES) @(posedge clk);

    // Let any character still in the shifter finish, so the log is not
    // truncated mid-word by the core going to sleep.
    #(BIT_TIME * 12);

    exit_code  = dut.u_ram.mem[EXIT_CODE_ADDR[31:2]];
    exit_magic = dut.u_ram.mem[EXIT_MAGIC_ADDR[31:2]];

    $display("");
    if (!finished) begin
      $display("[TB] FAIL: timeout after %0d cycles without reaching WFI", cycles);
      $display("[TB]   last fetch 0x%08x, last data 0x%08x",
               last_instr_addr, last_data_addr);
      $display("[TB]   trap_count=%0d mcause=0x%08x mepc=0x%08x",
               dut.u_ram.mem[TRAP_COUNT_ADDR[31:2]],
               dut.u_ram.mem[TRAP_MCAUSE_ADDR[31:2]],
               dut.u_ram.mem[TRAP_MEPC_ADDR[31:2]]);
      errors = errors + 1;
    end else begin
      $display("[TB] core asleep after %0d cycles", cycles);
      if (exit_magic !== EXIT_MAGIC) begin
        $display("[TB] FAIL: exit magic 0x%08x, expected 0x%08x: the core slept without finishing",
                 exit_magic, EXIT_MAGIC);
        errors = errors + 1;
      end else if (exit_code !== 32'h0) begin
        $display("[TB] FAIL: self-test reported failures, mask 0x%08x", exit_code);
        errors = errors + 1;
      end else begin
        $display("[TB] exit code 0x%08x", exit_code);
      end
    end

    $display("[TB] boot: %0d hand-over%s, the last at cycle %0d; %0d cycles in the image",
             handovers, (handovers == 1) ? "" : "s", handover_cycle,
             (handover_cycle >= 0) ? (cycles - handover_cycle) : 0);
    $display("[TB] bootreg: bstrap 0x%08x bstat 0x%08x brpt 0x%08x epoch 0x%08x",
             {dut.u_boot.valid_q, 3'h0, dut.u_boot.NSTRAP_B, 7'h0,
              dut.u_boot.wdis_q, dut.u_boot.strap_w},
             {8'h0, dut.u_boot.LIMIT_B, 6'h0, dut.u_boot.over_limit,
              dut.u_boot.last_attempt, dut.u_boot.cnt_w},
             dut.u_boot.brpt_q, dut.u_boot.epoch_q);
    if (handovers == 0) begin
      $display("[TB] FAIL: the loader never handed over to an image in RAM");
      errors = errors + 1;
    end
    $display("[TB] console: %0d characters decoded, %0d framing errors",
             rx_chars, rx_framing_errors);
    $display("[TB] watchdog: stage1 %0d, stage2 %0d, stage3 %0d",
             wdog_stage1, wdog_stage2, wdog_stage3);
    $display("[TB] gpio: pads 0x%04x, driven 0x%04x, irq %b",
             gpio_pad, gpio_oe, gpio_irq);
    $display("[TB] qspi: %0d frames on CS0, %0d datasheet violations, irq %b",
             u_flash0.frames, u_flash0.violations, qspi_irq);
    if (u_flash0.violations != 0) begin
      $display("[TB] FAIL: the flash model counted %0d datasheet violations",
               u_flash0.violations);
      errors = errors + 1;
    end
    // docs/67: the memory codec's six counters, read hierarchically as
    // the exit code is. A clean run reports NOTHING -- a scrubber that
    // walks every row of both memories for the whole run and repairs
    // none, a read path that corrects none -- and a nonzero count here
    // is either a stored row that was not a codeword or a report line
    // pulsing on healthy traffic, both of which are failures.
    $display("[TB] scrub: ram sec/rd/ded %0d/%0d/%0d, rom sec/rd/ded %0d/%0d/%0d",
             dut.u_scrub.g_src[0].cnt_q, dut.u_scrub.g_src[1].cnt_q,
             dut.u_scrub.g_src[2].cnt_q, dut.u_scrub.g_src[3].cnt_q,
             dut.u_scrub.g_src[4].cnt_q, dut.u_scrub.g_src[5].cnt_q);
    // A RUN WITH AN INJECTED FAULT IS NOT A CLEAN RUN, and this
    // criterion is about clean runs. +ded_word plants an uncorrectable
    // in a word the loader has just written (docs/68 section 6), so the
    // counters are SUPPOSED to move and the loader's report of what it
    // found is the evidence. Without this exemption the one run that
    // demonstrates the codec catching something reports a failure for
    // catching it.
    if (ded_word < 0 &&
        (dut.u_scrub.g_src[0].cnt_q != 0 || dut.u_scrub.g_src[1].cnt_q != 0 ||
         dut.u_scrub.g_src[2].cnt_q != 0 || dut.u_scrub.g_src[3].cnt_q != 0 ||
         dut.u_scrub.g_src[4].cnt_q != 0 || dut.u_scrub.g_src[5].cnt_q != 0)) begin
      $display("[TB] FAIL: the memory codec reported an event on a clean run");
      errors = errors + 1;
    end
    if (ded_word >= 0)
      $display("[TB] note: an uncorrectable was injected; the counters above are expected to be non-zero");
    if (rx_chars == 0) begin
      $display("[TB] FAIL: nothing came out of the UART");
      errors = errors + 1;
    end
    if (rx_framing_errors != 0) begin
      $display("[TB] FAIL: %0d framing errors on the console line",
               rx_framing_errors);
      errors = errors + 1;
    end
    if (!rx_seen_pass) begin
      $display("[TB] FAIL: \"RESULT PASS\" never appeared on the console line");
      errors = errors + 1;
    end

    if (saw_alert_major_int) begin
      $display("[TB] FAIL: alert_major_internal_o asserted (lockstep mismatch)");
      errors = errors + 1;
    end
    if (saw_alert_major_bus) begin
      $display("[TB] FAIL: alert_major_bus_o asserted (memory integrity)");
      errors = errors + 1;
    end
    if (saw_double_fault) begin
      $display("[TB] FAIL: double_fault_seen_o asserted during the run");
      errors = errors + 1;
    end
    if (saw_alert_minor)
      $display("[TB] note: alert_minor asserted at least once");

    if (errors == 0) $display("[TB] PASS");
    else             $display("[TB] FAIL (%0d problems)", errors);

    $finish;
  end

endmodule
