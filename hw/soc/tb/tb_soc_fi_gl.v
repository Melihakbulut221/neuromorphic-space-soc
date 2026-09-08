// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Gate-level fault-injection testbench for the management core, docs/74.
//
// WHAT THIS IS
//
// hw/soc/tb/tb_soc_fi.v is the instrument of docs/42, docs/43, docs/46
// and docs/67: it runs the whole SoC at RTL with one bit of one core
// flip-flop flipped at one cycle and prints what came out of the pins.
// This file is the same instrument pointed at the MAPPED NETLIST -- the
// sign-off layout's `final/nl/soc_top.nl.v`, one flattened module of
// sg13g2 cells and six RM_IHPSG13 SRAM macros -- and it keeps the same
// clock, the same reset, the same pin ties, the same console receiver,
// the same termination rule, the same drain and the same RECORD keys,
// so that hw/soc/fi/campaign.py's classifier reads a gate-level record
// exactly as it reads an RTL one and the two campaigns can be compared
// record for record (docs/32 section 5's standard).
//
// WHAT IS DIFFERENT, AND WHY EACH ONE
//
//   THE INJECTION.  An RTL deposit XORs a `reg` in place.  There is no
//   reg here: every flip-flop is a cell whose Q drives a net, and a
//   deposit onto a driven net is a stuck-at (docs/24 section 4.3,
//   measured).  So the upset is a FORCE on the flip-flop's Q net from a
//   quarter cycle after one edge to a quarter cycle after the next --
//   docs/26 section 4's primitive, re-validated on the pilot's sign-off
//   netlist in docs/32 section 4.1.  During the window the fan-out cone
//   sees the flipped value; at the edge inside it the cell samples the D
//   its own logic computed from that value, so a register that holds
//   captures the corruption and a register that reloads does not; on
//   release the net returns to the cell's own drive.  The injector
//   decides neither.  The record carries the value before the force, the
//   value DURING it (which proves the force took) and the value after
//   release (which says whether the design kept it).
//
//   THE SITE.  An RTL site is a hierarchical register name and a bit; a
//   gate-level site is an INDEX into the netlist's own flip-flop list,
//   which hw/soc/fi/gl_netlist.py parses out of the file and turns into
//   the case statements included below.  Which netlist index is the
//   twin of which RTL bit is not decided here: hw/soc/fi/gl_map.py
//   derives it from a per-cycle trace of both designs, and this bench
//   can write that trace (+trace=<file>).
//
//   THE MEMORIES.  soc_mem.v's register arrays are SRAM macros here, so
//   the words tb_soc_fi.v reads with `dut.u_ram.mem[i]` are read out of
//   the macro models' arrays, bank and row selected the way
//   soc_mem_sram.v selects them, and the boot ROM is loaded into its two
//   macros at time zero the way soc_mem.v's $readmemh loads the RTL
//   array.  The RAM macros are ZEROED at time zero, data and check
//   field, because soc_mem.v zeroes its array ("a fetch from
//   uninitialised memory should decode as an illegal instruction and
//   trap, not propagate x"): the silicon's RAM powers up undefined and
//   the comparison this bench serves is against the RTL's initial
//   condition, not the silicon's.  Both facts are stated in docs/74.
//
//   WHAT THE NETLIST DOES NOT CARRY.  The watchdog's kick request, its
//   early-kick and budget flags and its programmed reload are internal
//   nets whose names did not survive synthesis, and the register file's
//   correction counters were deleted by opt_clean because nothing reads
//   them (docs/43 section 6.5).  The kick statistics are reported as -1;
//   the timeout the campaign derives its budget from is taken from the
//   RTL clean run and passed in (+wdog_rld, +wdog_pre) rather than read
//   out of the design; and the correction counters are recomputed by a
//   SHADOW decoder over the netlist's own storage flip-flops
//   (hw/soc/tb/fi_rf_shadow.v), reading the same registers the design's
//   deleted counters read.  That shadow is a bench instrument and not a
//   pin, exactly as the RTL counters were.
//
// WHAT THIS TESTBENCH DOES NOT DO
//
//   * it has no timing: the cell models are zero-delay and the SRAM
//     macros are their FUNCTIONAL behavioural models.  A fault whose
//     effect depends on a hold or setup margin is invisible here.
//   * it does not model a transient in combinational logic or a
//     multi-bit strike.
//   * it has no notion of a correct answer.  The golden run is the
//     campaign's.

`timescale 1ns / 1ps

`ifndef ROM_HEX
  `define ROM_HEX "fi_workload.hex"
`endif
`ifndef ROM_INIT_WORD
  `define ROM_INIT_WORD 32
`endif
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
`ifndef TRAP_COUNT_ADDR
  `define TRAP_COUNT_ADDR 32'h0
`endif
`ifndef NMI_COUNT_ADDR
  `define NMI_COUNT_ADDR 32'h0
`endif
`ifndef FI_PHASE_ADDR
  `define FI_PHASE_ADDR 32'h0
`endif
`ifndef FI_SIG_ADDR
  `define FI_SIG_ADDR 32'h0
`endif
`ifndef FI_MASK_ADDR
  `define FI_MASK_ADDR 32'h0
`endif
`ifndef FI_ROUNDS_ADDR
  `define FI_ROUNDS_ADDR 32'h0
`endif
`ifndef FI_DEFAULT_BUDGET
  `define FI_DEFAULT_BUDGET 200000
`endif

module tb_soc_fi_gl;

  localparam integer CLK_HALF   = 5;
  localparam integer BIT_CYCLES = `UART_BIT_CYCLES;
  localparam integer BIT_TIME   = BIT_CYCLES * 2 * CLK_HALF;

  localparam [31:0] EXIT_CODE_ADDR   = `EXIT_CODE_ADDR;
  localparam [31:0] EXIT_MAGIC_ADDR  = `EXIT_MAGIC_ADDR;
  localparam [31:0] TRAP_MCAUSE_ADDR = `TRAP_MCAUSE_ADDR;
  localparam [31:0] TRAP_COUNT_ADDR  = `TRAP_COUNT_ADDR;
  localparam [31:0] NMI_COUNT_ADDR   = `NMI_COUNT_ADDR;
  localparam [31:0] FI_PHASE_ADDR    = `FI_PHASE_ADDR;
  localparam [31:0] FI_SIG_ADDR      = `FI_SIG_ADDR;
  localparam [31:0] FI_MASK_ADDR     = `FI_MASK_ADDR;
  localparam [31:0] FI_ROUNDS_ADDR   = `FI_ROUNDS_ADDR;
  localparam [31:0] EXIT_MAGIC       = 32'h600d_c0de;

  reg clk   = 1'b0;
  reg rst_n = 1'b0;
  always #CLK_HALF clk = ~clk;

  // ------------------------------------------------------------------
  // Command line
  // ------------------------------------------------------------------
  integer arg_site   = -1;      // netlist flip-flop index; -1 = clean
  integer arg_cycle  = 0;
  integer arg_armed  = 1;
  integer arg_budget = `FI_DEFAULT_BUDGET;
  integer arg_rld    = -1;      // the RTL clean run's reload and prescale
  integer arg_pre    = -1;
  integer arg_zero   = 1;       // zero the RAM macros at time 0
  reg [1023:0] trace_file;
  integer trace_fd = 0;

  wire wdog_dis = (arg_armed != 0) ? 1'b0 : 1'b1;

  wire uart_tx, uart_irq;
  wire wdog_n, wdog_rst, nmi, irq_timer, irq_soft, gptimer_irq;
  wire alert_minor, alert_major_internal, alert_major_bus;
  wire double_fault_seen, core_sleep;

  // The netlist's soc_top: the same port list as the RTL's, and the
  // same ties tb_soc_fi.v makes.
  soc_top dut (
      .clk_i  (clk),
      .rst_ni (rst_n),
      .wdog_dis_i (wdog_dis),
      .strap_i    (4'h0),
      .uart_tx_o  (uart_tx),
      .uart_irq_o (uart_irq),
      .gpio_i     (16'h0000),
      .gpio_o     (),
      .gpio_oe_o  (),
      .gpio_irq_o (),
      .qspi_sck_o   (),
      .qspi_cs_no   (),
      .qspi_io_o    (),
      .qspi_io_oe_o (),
      .qspi_io_i    (4'hF),
      .qspi_irq_o   (),
      .npu_aer_in_stb_o  (),
      .npu_aer_out_vld_o (),
      .npu_irq_o         (),
      .npu_ser_cs_n_o    (),
      .npu_ser_miso_o    (),
      .npu_ser_mosi_o    (),
      .npu_ser_sck_o     (),
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

  // ------------------------------------------------------------------
  // The flip-flop list, generated from the netlist by gl_netlist.py:
  // FI_GL_COUNT, FI_GL_QVEC (bit i is flop i), FI_GL_FORCE_CASES and
  // FI_GL_RELEASE_CASES.
  // ------------------------------------------------------------------
`include "fi_gl_sites.vh"

  wire [`FI_GL_COUNT-1:0] fi_q = `FI_GL_QVEC;

  reg     fi_val    = 1'b0;
  reg     fi_hit    = 1'b0;
  reg     fi_before = 1'b0;
  reg     fi_during = 1'b0;
  reg     fi_after  = 1'b0;
  reg     fi_done   = 1'b0;

  task gl_force;
    begin
      case (arg_site)
        `FI_GL_FORCE_CASES
        default: ;
      endcase
    end
  endtask

  task gl_release;
    begin
      case (arg_site)
        `FI_GL_RELEASE_CASES
        default: ;
      endcase
    end
  endtask

  // ------------------------------------------------------------------
  // The memories: the macro models' arrays, addressed the way
  // soc_mem_sram.v addresses the macros.
  //
  //   RAM  8192 rows of 64 bits, {check[31:0], data[31:0]};
  //        bank = word[12:11], row = word[10:0]
  //   ROM  2048 rows of 32 bits (ROM_HARDEN = 0);
  //        bank = word[10], row = word[9:0]
  // ------------------------------------------------------------------
  function [31:0] ram_word;
    input [31:0] addr;
    reg [12:0] widx;
    reg [63:0] row;
    begin
      widx = addr[14:2];
      case (widx[12:11])
        2'd0: row = dut.\u_ram.g_ram_2048x64_ecc.u_b0 .i_SRAM_1P_behavioral_bm_bist.memory[widx[10:0]];
        2'd1: row = dut.\u_ram.g_ram_2048x64_ecc.u_b1 .i_SRAM_1P_behavioral_bm_bist.memory[widx[10:0]];
        2'd2: row = dut.\u_ram.g_ram_2048x64_ecc.u_b2 .i_SRAM_1P_behavioral_bm_bist.memory[widx[10:0]];
        default: row = dut.\u_ram.g_ram_2048x64_ecc.u_b3 .i_SRAM_1P_behavioral_bm_bist.memory[widx[10:0]];
      endcase
      ram_word = row[31:0];
    end
  endfunction

  reg [31:0] rom_img [0:2047];
  integer i;
  initial begin
    for (i = 0; i < 2048; i = i + 1) rom_img[i] = 32'h0;
    $readmemh(`ROM_HEX, rom_img, `ROM_INIT_WORD);
    for (i = 0; i < 1024; i = i + 1) begin
      dut.\u_rom.g_rom_1024x32.u_b0 .i_SRAM_1P_behavioral_bm_bist.memory[i] = rom_img[i];
      dut.\u_rom.g_rom_1024x32.u_b1 .i_SRAM_1P_behavioral_bm_bist.memory[i] = rom_img[1024 + i];
    end
  end

  initial begin
    // Ordered behind the plusarg parse by the #0 so +zero=0 can leave
    // the macros undefined, which is the silicon's own initial state.
    #0;
    if (arg_zero) begin
      for (i = 0; i < 2048; i = i + 1) begin
        dut.\u_ram.g_ram_2048x64_ecc.u_b0 .i_SRAM_1P_behavioral_bm_bist.memory[i] = 64'h0;
        dut.\u_ram.g_ram_2048x64_ecc.u_b1 .i_SRAM_1P_behavioral_bm_bist.memory[i] = 64'h0;
        dut.\u_ram.g_ram_2048x64_ecc.u_b2 .i_SRAM_1P_behavioral_bm_bist.memory[i] = 64'h0;
        dut.\u_ram.g_ram_2048x64_ecc.u_b3 .i_SRAM_1P_behavioral_bm_bist.memory[i] = 64'h0;
      end
    end
  end

  // ------------------------------------------------------------------
  // Cycle counter, on the power-on reset -- tb_soc_fi.v's, unchanged.
  // ------------------------------------------------------------------
  integer cycles = 0;
  always @(posedge clk) if (rst_n) cycles = cycles + 1;

  // ------------------------------------------------------------------
  // Watchdog escalation, as ordered port events -- unchanged.
  // ------------------------------------------------------------------
  reg nmi_q = 1'b0, wdog_rst_q = 1'b0, wdog_n_q = 1'b1;
  integer wdog_stage1 = 0, wdog_stage2 = 0, wdog_stage3 = 0;
  integer wdog_first_cycle = -1;
  always @(posedge clk) if (rst_n) begin
    if (nmi && !nmi_q) begin
      wdog_stage1 = wdog_stage1 + 1;
      if (wdog_first_cycle < 0) wdog_first_cycle = cycles;
    end
    if (wdog_rst && !wdog_rst_q) begin
      wdog_stage2 = wdog_stage2 + 1;
      if (wdog_first_cycle < 0) wdog_first_cycle = cycles;
    end
    if (!wdog_n && wdog_n_q) begin
      wdog_stage3 = wdog_stage3 + 1;
      if (wdog_first_cycle < 0) wdog_first_cycle = cycles;
    end
    nmi_q      <= nmi;
    wdog_rst_q <= wdog_rst;
    wdog_n_q   <= wdog_n;
  end

  // docs/74 section 10.2: the watchdog's stage-2 request is decoded
  // combinationally out of the voted replicas into an ASYNCHRONOUS
  // reset, and on the netlist a change of the protected word can put a
  // zero-width pulse on it that the edge-sampled counters above never
  // see.  This counts every rising event on the pin, however narrow.
  // Added after the campaigns of docs/74 ran; every record there was
  // taken without it, and the document says so.
  integer wdog_rst_events = 0;
  always @(posedge wdog_rst) wdog_rst_events = wdog_rst_events + 1;

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

  // ------------------------------------------------------------------
  // The measured injection window, from the phase word in the RAM
  // macros -- the same rule as tb_soc_fi.v, through ram_word().
  // ------------------------------------------------------------------
  integer win_open = -1, win_close = -1;
  reg [31:0] phase_q = 32'hffff_ffff;
  reg [31:0] phase_now;
  always @(posedge clk) if (rst_n) begin
    phase_now = ram_word(FI_PHASE_ADDR);
    if (phase_now !== phase_q) begin
      phase_q = phase_now;
      if (phase_q == 32'd1 && win_open  < 0) win_open  = cycles;
      if (phase_q == 32'd2 && win_close < 0) win_close = cycles;
    end
  end

  // ------------------------------------------------------------------
  // The register file's correction report, recomputed from the
  // netlist's storage.  Generated by gl_map.py once the mapping is
  // known; absent, the record says -1 and the campaign refuses to
  // classify CORRECTED.
  // ------------------------------------------------------------------
  wire [15:0] rf_sec_cycles, rf_ded_cycles;
  wire        rf_sec_seen, rf_ded_seen;
`ifdef FI_GL_RF
`include "fi_gl_rf.vh"
  localparam RF_SHADOW = 1;
`else
  assign rf_sec_cycles = 16'h0;
  assign rf_ded_cycles = 16'h0;
  assign rf_sec_seen   = 1'b0;
  assign rf_ded_seen   = 1'b0;
  localparam RF_SHADOW = 0;
`endif

  // ------------------------------------------------------------------
  // The watchdog's protected word, as the voter sees it.  Generated by
  // gl_netlist.py --emit-wdog from the netlist's own `qb`/`qc` nets and
  // replica A's flip-flops; counts the cycles on which a replica
  // disagrees with the vote and reads the voted word's own W6 report
  // (tmr_err, tmr_count), which in silicon is WDOGSTAT over the bus.
  // ------------------------------------------------------------------
  wire [31:0] wd_mismatch_cycles;
  wire [3:0]  wd_tmr_count;
  wire        wd_tmr_err;
`ifdef FI_GL_WDOG
`include "fi_gl_wdog.vh"
  localparam WD_SHADOW = 1;
`else
  assign wd_mismatch_cycles = 32'h0;
  assign wd_tmr_count = 4'h0;
  assign wd_tmr_err = 1'b0;
  localparam WD_SHADOW = 0;
`endif

  // ------------------------------------------------------------------
  // Console -- tb_soc_fi.v's receiver, unchanged.
  // ------------------------------------------------------------------
  integer rx_chars = 0;
  integer rx_framing_errors = 0;
  reg [31:0] rx_hash = 32'h811c_9dc5;
  reg [7:0] rx_byte;
  reg [175:0] rx_tail = 176'h0;
  integer bit_i;

  initial begin
    @(posedge rst_n);
    @(posedge clk);
    forever begin
      @(negedge uart_tx);
      #(BIT_TIME + BIT_TIME / 2);
      for (bit_i = 0; bit_i < 8; bit_i = bit_i + 1) begin
        rx_byte[bit_i] = uart_tx;
        #(BIT_TIME);
      end
      if (uart_tx !== 1'b1) rx_framing_errors = rx_framing_errors + 1;
      rx_chars = rx_chars + 1;
      rx_hash  = (rx_hash ^ {24'h0, rx_byte}) * 32'h0100_0193;
      rx_tail  = {rx_tail[167:0], rx_byte};
    end
  end

  // ------------------------------------------------------------------
  // Termination -- tb_soc_fi.v's rule.  The magic is sampled out of the
  // macro array at the edge, since a continuous read of a memory word
  // through a hierarchical reference is not something every simulator
  // evaluates on every write.
  // ------------------------------------------------------------------
  reg saw_awake = 1'b0;
  always @(posedge clk) if (rst_n && !core_sleep) saw_awake <= 1'b1;

  reg [31:0] magic_now = 32'h0;
  always @(posedge clk) if (rst_n) magic_now = ram_word(EXIT_MAGIC_ADDR);

  wire finished = saw_awake && core_sleep && (magic_now == EXIT_MAGIC);
  reg done_q = 1'b0;

  // ------------------------------------------------------------------
  // The upset: force for one edge, then release.  Same instant in the
  // cycle as tb_soc_fi.v's deposit, for the reason given there.
  // ------------------------------------------------------------------
  reg args_ready = 1'b0;
  time fi_force_time = 0;

  // The instant is ABSOLUTE, not counted.  tb_soc_fi.v waits
  // `while (cycles < arg_cycle) @(posedge clk)`, and `cycles` is
  // incremented by another process on the same edge; which of the two
  // the simulator runs first is a race, and docs/74 section 7 measured
  // it landing a deposit one clock late on one record and on time on
  // another.  Here +cycle names the clock edge itself: edge 0 is the
  // one reset is released on, edge c is 10 ns x c later, and the force
  // lands a quarter cycle after it.  The time is reported so the row
  // can be checked against the trace.
  initial begin
    wait (args_ready);
    if (arg_site >= 0) begin
      @(posedge rst_n);
      #(2 * CLK_HALF * arg_cycle);
      #(CLK_HALF / 2);
      fi_force_time = $time;
      fi_before = fi_q[arg_site];
      fi_val    = ~fi_before;
      gl_force;
      #1;
      fi_during = fi_q[arg_site];
      fi_hit    = 1'b1;
      @(posedge clk);
      #(CLK_HALF / 2);
      gl_release;
      #1;
      fi_after  = fi_q[arg_site];
      fi_done   = 1'b1;
    end
  end

  // ------------------------------------------------------------------
  // The trace: every flip-flop, every cycle, sampled on the falling
  // edge so the values are the ones the rising edge produced.  Written
  // only when +trace names a file; gl_map.py reads it.
  // ------------------------------------------------------------------
  always @(negedge clk) if (rst_n && trace_fd) $fwrite(trace_fd, "%b\n", fi_q);

  // ------------------------------------------------------------------
  integer exit_code, exit_magic;
  reg [31:0] rec_sig, rec_mask, rec_rounds, rec_traps, rec_mcause, rec_nmis;
  integer rec_cycles;

  initial begin
    if (!$value$plusargs("site=%d",   arg_site))   arg_site   = -1;
    if (!$value$plusargs("cycle=%d",  arg_cycle))  arg_cycle  = 0;
    if (!$value$plusargs("armed=%d",  arg_armed))  arg_armed  = 1;
    if (!$value$plusargs("budget=%d", arg_budget)) arg_budget = `FI_DEFAULT_BUDGET;
    if (!$value$plusargs("wdog_rld=%d", arg_rld))  arg_rld    = -1;
    if (!$value$plusargs("wdog_pre=%d", arg_pre))  arg_pre    = -1;
    if (!$value$plusargs("zero=%d",   arg_zero))   arg_zero   = 1;
    if ($value$plusargs("trace=%s", trace_file)) trace_fd = $fopen(trace_file, "w");
    args_ready = 1'b1;

    if ($test$plusargs("vcd")) begin
      $dumpfile("tb_soc_fi_gl.vcd");
      $dumpvars(0, tb_soc_fi_gl);
    end

    repeat (20) @(posedge clk);
    rst_n = 1'b1;

    if ($test$plusargs("dumpsites")) $display("SITECOUNT %0d", `FI_GL_COUNT);

    while (!finished && cycles < arg_budget) @(posedge clk);
    done_q = finished;

    #(BIT_TIME * 24);

    rec_cycles = cycles;
    exit_code  = ram_word(EXIT_CODE_ADDR);
    exit_magic = ram_word(EXIT_MAGIC_ADDR);
    rec_sig    = ram_word(FI_SIG_ADDR);
    rec_mask   = ram_word(FI_MASK_ADDR);
    rec_rounds = ram_word(FI_ROUNDS_ADDR);
    rec_traps  = ram_word(TRAP_COUNT_ADDR);
    rec_mcause = ram_word(TRAP_MCAUSE_ADDR);
    rec_nmis   = ram_word(NMI_COUNT_ADDR);

    $display("RECORD site=%0d bit=0 cycle=%0d armed=%0d",
             arg_site, arg_cycle, arg_armed);
    // `width` is 1 by construction; `before`/`after` carry the RTL
    // record's meaning; `during` and `persist` are gate-level facts.
    $display("RECORD hit=%0d width=1 before=%032x after=%032x during=%0d persist=%0d force_ps=%0t",
             fi_hit, {127'h0, fi_before}, {127'h0, fi_after}, fi_during,
             (fi_after !== fi_before), fi_force_time);
    $display("RECORD done=%0d cycles=%0d budget=%0d",
             done_q, rec_cycles, arg_budget);
    $display("RECORD slept=%0d expired=%0d",
             core_sleep, (rec_cycles >= arg_budget));
    $display("RECORD sig=%08x mask=%08x rounds=%0d",
             rec_sig, rec_mask, rec_rounds);
    $display("RECORD exit=%08x magic=%08x", exit_code, exit_magic);
    $display("RECORD console_chars=%0d console_hash=%08x console_framing=%0d",
             rx_chars, rx_hash, rx_framing_errors);
    $display("RECORD console_tail=%s", rx_tail);
    $display("RECORD wdog1=%0d wdog2=%0d wdog3=%0d wdog_first=%0d wdog_rst_events=%0d",
             wdog_stage1, wdog_stage2, wdog_stage3, wdog_first_cycle, wdog_rst_events);
    $display("RECORD traps=%0d mcause=%08x nmis=%0d",
             rec_traps, rec_mcause, rec_nmis);
    $display("RECORD alert_minor=%0d alert_int=%0d alert_bus=%0d dblfault=%0d",
             saw_alert_minor, saw_alert_major_int,
             saw_alert_major_bus, saw_double_fault);
    $display("RECORD win_open=%0d win_close=%0d", win_open, win_close);
    // The reload and prescale are the RTL clean run's, passed in; the
    // kick statistics are not observable on this netlist.
    $display("RECORD wdog_rld=%0d wdog_pre=%0d kicks=-1 kick_min=-1 kick_max=-1",
             arg_rld, arg_pre);
    $display("RECORD wdog_early=-1 wdog_budget=-1 wdog_win=00000000");
    if (RF_SHADOW)
      $display("RECORD rf_sec=%0d rf_ded=%0d rf_sec_seen=%0d rf_ded_seen=%0d rf_shadow=1",
               rf_sec_cycles, rf_ded_cycles, rf_sec_seen, rf_ded_seen);
    else
      $display("RECORD rf_sec=-1 rf_ded=-1 rf_sec_seen=0 rf_ded_seen=0 rf_shadow=0");
    if (WD_SHADOW)
      $display("RECORD wd_mismatch=%0d wd_tmr_count=%0d wd_tmr_err=%0d wd_shadow=1",
               wd_mismatch_cycles, wd_tmr_count, wd_tmr_err);
    else
      $display("RECORD wd_mismatch=-1 wd_tmr_count=-1 wd_tmr_err=0 wd_shadow=0");
    $display("RECORD end");

    if (trace_fd) $fclose(trace_fd);
    $finish;
  end

endmodule
