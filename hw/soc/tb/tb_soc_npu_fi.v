// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Fault-injection testbench for the NPU CONNECTION.
//
// WHAT THIS IS FOR
//
// `docs/51-npu-integration.md` section 14 item 7 records the gap:
//
//   No fault-injection campaign through the connection. docs/16
//   measures upsets in the die through its own pins; nothing measures
//   what an upset in the transport or the event engine does to an
//   inference.
//
// and section 18 makes it the recommended next block, with the reason:
// this is the first block in the SoC that sits BETWEEN TWO MEASURED
// THINGS -- the die of docs/16 and the core of docs/42 -- and is itself
// unmeasured.  It also states the discipline this file follows:
// MEASURE BEFORE HARDENING, because "hardening before measuring is the
// mistake docs/38 section 10 item 4 names".
//
// This file is the instrument.  It runs the whole SoC of docs/51 -- the
// core, the fabric, the connection and the frozen die inside it -- with
// one bit of one flip-flop flipped at one cycle, and reports what came
// out.  `hw/soc/fi/npu_campaign.py` is the classifier; this file
// measures and does not judge, which is the division of labour docs/16,
// docs/41 and docs/42 all use and for their reason: a testbench that
// classified would be a testbench that could be written around a result.
//
// WHAT IS OBSERVED, AND WHY EACH ONE
//
// Everything tb_soc_fi.v observes, unchanged, because the CPU is still
// in the loop and a corrupted connection can hang it:
//
//   uart_tx_o, decoded            the program's answer over a pin.
//   nmi_o, wdog_rst_o, wdog_no    the watchdog's three stages, as PORT
//                                 EVENTS with the cycle they happened
//                                 on.  "The watchdog caught it" must be
//                                 a transition on a pin and never the
//                                 simulation running out of budget.
//   core_sleep_o                  how the program says it has finished.
//   alert_*, double_fault_seen_o  Ibex's own alert pins.
//
// and five things that are new here.
//
//   1. THE PROGRAM'S ANSWER IS AGAINST THE GOLDEN MODEL.  `fi_mask`
//      carries seven bits and three of them -- F_LEN, F_STREAM and
//      F_STATE -- are comparisons against constants
//      `hw/soc/flow/gen_npu_vectors.py` computed from
//      `sw/golden/lif_core.py` at build time.  docs/42 section 3 had to
//      settle for an undeposited run as its oracle and said what that
//      cost; this campaign has the specification, and F_STATE in
//      particular is an ARCHITECTURAL-STATE oracle for the NPU, which
//      docs/42 section 9's first bullet names as the single largest
//      reason its own rate is a lower bound.
//
//   2. THE TELEMETRY, TWICE.  Six words the PROGRAM read with a load --
//      the cause register, the status word, the two drop counters, the
//      die's overflow and out-of-range counts -- beside this file's own
//      hierarchical reads of the same state.  docs/44 section 8.2 draws
//      the distinction that makes both necessary: a counter a testbench
//      reads is not a counter an operator can see.
//
//   3. THE QUEUE PROTECTION, WHICH HAS NO OPERATOR CHANNEL AT ALL.
//      `aer_fifo`'s `ptr_mismatch`, `par_err` and `rv_mismatch` are
//      brought out of both instances in soc_npu.v and CONNECTED TO
//      NOTHING (docs/51 section 14 item 1).  They are counted here
//      because they are the only correction and detection mechanism in
//      the connection, and they are reported SEPARATELY from the
//      announcement channels because nothing in silicon could see them.
//      That separation is docs/43's, where the register file's
//      correction counter is read hierarchically and the report says so.
//
//   4. THE EXPOSURE ARITHMETIC.  A register access costs 176 cycles
//      (docs/51 section 8.1) and the transport is 134 flip-flops of 738.
//      Those two numbers pull in opposite directions and a per-flop rate
//      hides it, so this file counts the cycles in the measured window
//      for which the transport, the window FSM and the event engine are
//      each BUSY, and records whether the transport was busy at the
//      cycle of the deposit.  docs/52 section 7 is the arithmetic.
//
//   5. WHICH SIDE OF THE PIN BOUNDARY.  `fi_frozen` says whether the
//      deposit went into `hw/rtl/pilot_top.v` -- silicon docs/34 has
//      already committed -- or into the connection, which is a design
//      still open.  The site table decides it and this file only
//      reports it, so a record cannot be attributed to the wrong side by
//      a reader.
//
// THE INJECTION
//
// One bit, one flip-flop, one cycle, XORed in place, at a fixed point
// inside the cycle so it can never race the design's own write.  The
// value stays flipped until the design's own logic writes the register
// again -- the single-event-upset model docs/16 section 7.4 describes.
// `fi_before`, `fi_after` and `fi_w` are reported so a deposit that did
// not land, or landed outside the register's width, is visible in the
// record rather than being a silent no-op that classifies MASKED.
//
// The site table is `hw/soc/fi/npu_targets.py` and is INCLUDED, not
// duplicated: that file generates the case statement below and the dump
// the campaign checks it against.
//
// WHAT THIS TESTBENCH DOES NOT DO
//
//   * it does not inject into the core, the fabric, the memories, the
//     CLINT, the timers or the watchdog.  docs/42 and docs/41 are those
//     campaigns.
//   * it does not inject into the rest of the frozen die.  docs/16 does,
//     on the block alone, and docs/32 confirms it at gate level.
//   * it does not model a transient in combinational logic, a multi-bit
//     strike, or anything at gate level.
//   * it has no notion of a correct answer.  The golden run is the
//     campaign's; the golden MODEL is the program's.

`timescale 1ns / 1ps

`ifndef ROM_HEX
  `define ROM_HEX "fi_npu.hex"
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
`ifndef FI_NEV_ADDR
  `define FI_NEV_ADDR 32'h0
`endif
`ifndef FI_CAUSE_ADDR
  `define FI_CAUSE_ADDR 32'h0
`endif
`ifndef FI_STATUS_ADDR
  `define FI_STATUS_ADDR 32'h0
`endif
`ifndef FI_DROP_ADDR
  `define FI_DROP_ADDR 32'h0
`endif
`ifndef FI_OVF_ADDR
  `define FI_OVF_ADDR 32'h0
`endif
`ifndef FI_OOR_ADDR
  `define FI_OOR_ADDR 32'h0
`endif
`ifndef FI_CNT_ADDR
  `define FI_CNT_ADDR 32'h0
`endif
`ifndef FI_SPINS_ADDR
  `define FI_SPINS_ADDR 32'h0
`endif
`ifndef FI_BSTCOR_ADDR
  `define FI_BSTCOR_ADDR 32'h0
`endif
`ifndef FI_BSTDET_ADDR
  `define FI_BSTDET_ADDR 32'h0
`endif
`ifndef FI_BSTTMR_ADDR
  `define FI_BSTTMR_ADDR 32'h0
`endif
`ifndef FI_DEFAULT_BUDGET
  `define FI_DEFAULT_BUDGET 400000
`endif

module tb_soc_npu_fi;

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
  localparam [31:0] FI_NEV_ADDR      = `FI_NEV_ADDR;
  localparam [31:0] FI_CAUSE_ADDR    = `FI_CAUSE_ADDR;
  localparam [31:0] FI_STATUS_ADDR   = `FI_STATUS_ADDR;
  localparam [31:0] FI_DROP_ADDR     = `FI_DROP_ADDR;
  localparam [31:0] FI_OVF_ADDR      = `FI_OVF_ADDR;
  localparam [31:0] FI_OOR_ADDR      = `FI_OOR_ADDR;
  localparam [31:0] FI_CNT_ADDR      = `FI_CNT_ADDR;
  localparam [31:0] FI_SPINS_ADDR    = `FI_SPINS_ADDR;
  localparam [31:0] FI_BSTCOR_ADDR   = `FI_BSTCOR_ADDR;
  localparam [31:0] FI_BSTDET_ADDR   = `FI_BSTDET_ADDR;
  localparam [31:0] FI_BSTTMR_ADDR   = `FI_BSTTMR_ADDR;
  localparam [31:0] EXIT_MAGIC       = 32'h600d_c0de;

  reg clk   = 1'b0;
  reg rst_n = 1'b0;
  always #CLK_HALF clk = ~clk;

  // ------------------------------------------------------------------
  // Command line
  // ------------------------------------------------------------------
  integer arg_site   = -1;      // -1 means a clean run
  integer arg_bit    = 0;
  integer arg_cycle  = 0;
  integer arg_armed  = 1;
  integer arg_budget = `FI_DEFAULT_BUDGET;
  integer dump_sites = 0;

  // The watchdog bootstrap pin, and THE COUNTERFACTUAL.
  //
  // soc_wdog.v W1 samples it once as power-on reset releases and ignores
  // it for ever after, so driving it from a plusarg is a board
  // configuration and not a back door.  The campaign runs every
  // injection twice, once with the watchdog armed and once with it held
  // off, and the pair is what turns "the watchdog escalated" into "the
  // watchdog escalated on a machine that was in fact dead".
  //
  // IT IS THE SAME COUNTERFACTUAL docs/42 SECTION 7.1 USED AND IT
  // ANSWERS A DIFFERENT QUESTION HERE.  There it asked whether the
  // backstop reaches a corrupted CORE.  Here it asks whether it reaches
  // a CPU that has stalled on a peripheral -- the node register window
  // holds the fabric response for 176 cycles by design, and an upset
  // that loses that response leaves a two-stage in-order core waiting
  // for ever with no fault of its own.  Nothing in this repository had
  // measured that.
  wire wdog_dis = (arg_armed != 0) ? 1'b0 : 1'b1;

  wire uart_tx, uart_irq;
  wire wdog_n, wdog_rst, nmi, irq_timer, irq_soft, gptimer_irq;
  wire alert_minor, alert_major_internal, alert_major_bus;
  wire double_fault_seen, core_sleep;
  wire npu_irq;
  wire npu_ser_sck, npu_ser_cs_n, npu_ser_mosi, npu_ser_miso;
  wire npu_aer_in_stb, npu_aer_out_vld;

  soc_top #(.ROM_INIT(`ROM_HEX)) dut (
      .clk_i  (clk),
      .rst_ni (rst_n),
      .wdog_dis_i (wdog_dis),
      // The bootstrap pins, docs/68. Tied to the board this campaign
      // models: boot from the flash on chip select 0, which is what
      // soc_boot.v samples once and reports. Nothing in this bench
      // reads them back; they are here because soc_top has the port.
      .strap_i    (4'h0),
      .uart_tx_o  (uart_tx),
      .uart_irq_o (uart_irq),
      // The GPIO pins (docs/65): a board with nothing on them. The
      // campaign program does not touch the block and IMASK resets to
      // zero, so the port's interrupt line is low throughout; the
      // outputs are observed by nothing here. Tied rather than left
      // open so that no X enters the synchroniser.
      .gpio_i     (16'h0000),
      .gpio_o     (),
      .gpio_oe_o  (),
      .gpio_irq_o (),
      // The QSPI pins (docs/66): a board with pull-ups and no flash.
      // The campaign program never touches the block and CTRL.IEN
      // resets to zero, so its line is low throughout; the lanes read
      // as pulled up so that no X enters the shift register.
      .qspi_sck_o   (),
      .qspi_cs_no   (),
      .qspi_io_o    (),
      .qspi_io_oe_o (),
      .qspi_io_i    (4'hF),
      .qspi_irq_o   (),
      .wdog_no       (wdog_n),
      .wdog_rst_o    (wdog_rst),
      .nmi_o         (nmi),
      .irq_timer_o   (irq_timer),
      .irq_soft_o    (irq_soft),
      .gptimer_irq_o (gptimer_irq),
      .npu_irq_o     (npu_irq),
      .npu_ser_sck_o     (npu_ser_sck),
      .npu_ser_cs_n_o    (npu_ser_cs_n),
      .npu_ser_mosi_o    (npu_ser_mosi),
      .npu_ser_miso_o    (npu_ser_miso),
      .npu_aer_in_stb_o  (npu_aer_in_stb),
      .npu_aer_out_vld_o (npu_aer_out_vld),
      .alert_minor_o          (alert_minor),
      .alert_major_internal_o (alert_major_internal),
      .alert_major_bus_o      (alert_major_bus),
      .double_fault_seen_o    (double_fault_seen),
      .core_sleep_o           (core_sleep)
  );

  // ------------------------------------------------------------------
  // The site table, generated from hw/soc/fi/npu_targets.py
  // ------------------------------------------------------------------
`include "fi_npu_targets.vh"

  reg [127:0] fi_bitmask = 128'd0;
  reg [127:0] fi_before  = 128'd0;
  reg [127:0] fi_after   = 128'd0;
  integer     fi_w       = 0;
  reg         fi_hit     = 1'b0;

  // ------------------------------------------------------------------
  // Cycle counter, on the POWER-ON reset.  It keeps running across a
  // watchdog reset, which is what makes an escalation cycle comparable
  // between a run that reset itself and one that did not.
  // ------------------------------------------------------------------
  integer cycles = 0;
  always @(posedge clk) if (rst_n) cycles = cycles + 1;

  // ------------------------------------------------------------------
  // Watchdog escalation, as ordered port events.
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

  // ------------------------------------------------------------------
  // Latched alerts, the double-fault pin, and the NPU's interrupt line.
  //
  // npu_irq CANNOT rise in the clean run: NPUCFG's IRQ_MASK resets to
  // zero and fi_npu.c never writes it.  It is watched anyway, because an
  // upset in `irq_mask` -- seven flip-flops of the `cfgreg` stratum --
  // is exactly how a spurious interrupt would be produced, and a channel
  // that is only watched when it is expected is not a channel.
  // ------------------------------------------------------------------
  reg saw_alert_minor     = 1'b0;
  reg saw_alert_major_int = 1'b0;
  reg saw_alert_major_bus = 1'b0;
  reg saw_double_fault    = 1'b0;
  reg saw_npu_irq         = 1'b0;
  always @(posedge clk) if (rst_n) begin
    if (alert_minor)          saw_alert_minor     <= 1'b1;
    if (alert_major_internal) saw_alert_major_int <= 1'b1;
    if (alert_major_bus)      saw_alert_major_bus <= 1'b1;
    if (double_fault_seen)    saw_double_fault    <= 1'b1;
    if (npu_irq)              saw_npu_irq         <= 1'b1;
  end

  // ------------------------------------------------------------------
  // The queues' own fault outputs, counted.
  //
  // THESE ARE BENCH OBSERVATIONS AND NOT OPERATOR CHANNELS, and the
  // campaign's report says so wherever it uses them.  soc_npu.v brings
  // `ptr_mismatch` and `par_err` out of both aer_fifo instances and
  // connects them to nothing -- docs/51 section 14 item 1 states that
  // and gives the reason: this SoC has no fault-counter block of its own
  // and NPU-only telemetry does not belong outside BUSSTAT, which
  // docs/41 owns.  `rv_mismatch` is not even brought out of the
  // instance; it is read from inside it here.
  //
  // In silicon a corrected pointer upset is therefore indistinguishable
  // from no upset at all, and a discarded queue entry is indistinguishable
  // from an event that was never injected.  That is the price the
  // connection currently pays for inheriting a protected queue and
  // giving it nowhere to report to, and docs/52 section 8 is the finding.
  // ------------------------------------------------------------------
  integer q_ptr_mm = 0;      // cycles a pointer vote corrected a replica
  integer q_par_err = 0;     // entries discarded on a failed parity check
  integer q_rv_mm = 0;       // rd_valid rail disagreements
  always @(posedge clk) if (rst_n) begin
    if (dut.u_npu.u_inj.ptr_mismatch) q_ptr_mm  = q_ptr_mm + 1;
    if (dut.u_npu.u_cap.ptr_mismatch) q_ptr_mm  = q_ptr_mm + 1;
    if (dut.u_npu.u_inj.par_err)      q_par_err = q_par_err + 1;
    if (dut.u_npu.u_cap.par_err)      q_par_err = q_par_err + 1;
    if (dut.u_npu.u_inj.rv_mismatch)  q_rv_mm   = q_rv_mm + 1;
    if (dut.u_npu.u_cap.rv_mismatch)  q_rv_mm   = q_rv_mm + 1;
  end

  // The engine's bounded wait, which IS a connection-local recovery and
  // does have an operator channel: it latches IRQ_CAUSE.FETCH_ER.
  // Counted here as well so the mechanism can be attributed rather than
  // inferred from the sticky bit alone.
  integer fetch_expire_n = 0;
  always @(posedge clk) if (rst_n)
    if (dut.u_npu.fetch_expire) fetch_expire_n = fetch_expire_n + 1;

  // The two bounds docs/55 added, counted at the bench so that a record
  // can be ATTRIBUTED to a mechanism rather than inferred from a sticky
  // bit that some later event might also have set.
  //
  // Both DO have an operator channel -- IRQ_CAUSE.SER_TO and
  // IRQ_CAUSE.WIN_TO, and the failed access itself is a bus error at the
  // core -- so unlike the queue counters above, these are a second view
  // of something software can see. Both views are printed, which is what
  // lets docs/55 say whether the two agree.
  integer ser_to_n = 0;      // frames the transport's own bound aborted
  integer win_to_n = 0;      // node-window waits that expired
  integer win_orph_n = 0;    // node-window states no grant put it in
  always @(posedge clk) if (rst_n) begin
    if (dut.u_npu.ser_timeout) ser_to_n   = ser_to_n + 1;
    if (dut.u_npu.win_expire)  win_to_n   = win_to_n + 1;
    // The window's two recoveries share one cause bit and are counted
    // apart HERE, because the register is what an operator reads and the
    // bench is where a record gets attributed to a mechanism.
    if (dut.u_npu.win_orphan)  win_orph_n = win_orph_n + 1;
  end

  // docs/56's bound, counted the same way and for the same reason: it is
  // the mechanism this wave built, so a record in which the show-ahead
  // adapter recovered has to be able to NAME it rather than have it
  // inferred from IRQ_CAUSE, which a later event could also have set.
  integer oh_to_n = 0;       // show-ahead reads that expired
  integer aer_mm_n = 0;      // strobe/state disagreements H5 suppressed
  always @(posedge clk) if (rst_n) begin
    if (dut.u_npu.oh_expire) oh_to_n  = oh_to_n + 1;
    if (dut.u_npu.aer_stb_mm) aer_mm_n = aer_mm_n + 1;
  end

  // AND THE OUTCOME THE BOUND EXISTS TO PREVENT, watched directly rather
  // than inferred. docs/56 section 5.1: before H4 a read that produced
  // no rd_valid left `oh_req` set FOR EVER and the adapter never issued
  // another one. The bench measures the longest run of consecutive
  // cycles with `oh_req` set, so a record in which the adapter wedged is
  // separable from one in which it recovered even where both end in the
  // same class -- and so that the clean run's own figure is on every
  // record as a control.
  integer oh_req_run = 0, oh_req_max = 0;
  always @(posedge clk) if (rst_n) begin
    if (dut.u_npu.oh_req) begin
      oh_req_run = oh_req_run + 1;
      if (oh_req_run > oh_req_max) oh_req_max = oh_req_run;
    end else begin
      oh_req_run = 0;
    end
  end

  // The connection's three fault lines into BUSSTAT, counted at the
  // source. The PROGRAM reads BUSSTAT's counters with a load and
  // publishes them in fi_bst_*; these are the bench's own count of the
  // same events, and a disagreement between the two would mean the
  // counters are not counting what reaches them.
  integer npu_cor_n = 0, npu_det_n = 0, npu_tmr_n = 0;
  always @(posedge clk) if (rst_n) begin
    if (dut.npu_cor_ev) npu_cor_n = npu_cor_n + 1;
    if (dut.npu_det_ev) npu_det_n = npu_det_n + 1;
    if (dut.npu_tmr_ev) npu_tmr_n = npu_tmr_n + 1;
  end

  // ------------------------------------------------------------------
  // The measured injection window, and THE EXPOSURE ARITHMETIC.
  //
  // fi_npu.c writes 1 into fi_phase when the measured kernel opens and 2
  // when it closes.  Measuring the window rather than assuming it is
  // docs/41 section 8.1's last honesty clause.
  //
  // AND WHILE IT IS OPEN, THE OCCUPANCY OF THE THREE BUSY SIGNALS IS
  // COUNTED.  docs/51 section 8.1 measures a register access at 176
  // clock cycles; docs/51 section 11 measures the transport at 134
  // flip-flops of the connection's 738.  A block that is SLOW is exposed
  // for LONGER, and a per-flip-flop rate cannot say that.  These three
  // counters are what turn the observation into arithmetic:
  //
  //   ser_busy    the transport has a frame in flight
  //   win_busy    the node window FSM is not idle -- a CPU access is in
  //               progress and the fabric response is outstanding
  //   ev_busy     the event engine is not idle
  //
  // docs/52 section 7 divides them by the window length and compares the
  // result against the flip-flop shares.
  // ------------------------------------------------------------------
  integer win_open = -1, win_close = -1;
  integer ser_busy_cyc = 0, win_busy_cyc = 0, ev_busy_cyc = 0;
  integer wdog_rld_at_open = -1;
  reg [31:0] phase_q = 32'hffff_ffff;
  reg in_window = 1'b0;

  always @(posedge clk) if (rst_n) begin
    if (dut.u_ram.mem[FI_PHASE_ADDR[31:2]] !== phase_q) begin
      phase_q = dut.u_ram.mem[FI_PHASE_ADDR[31:2]];
      if (phase_q == 32'd1 && win_open  < 0) begin
        win_open = cycles;
        wdog_rld_at_open = dut.u_timer0.u_wdog.reload;
        in_window = 1'b1;
      end
      if (phase_q == 32'd2 && win_close < 0) begin
        win_close = cycles;
        in_window = 1'b0;
      end
    end
    if (in_window) begin
      if (dut.u_npu.ser_busy)                     ser_busy_cyc = ser_busy_cyc + 1;
      if (dut.u_npu.win_state != 2'd0)            win_busy_cyc = win_busy_cyc + 1;
      if (dut.u_npu.ev_state  != 4'd0)            ev_busy_cyc  = ev_busy_cyc  + 1;
    end
  end

  // The cycle at which the block becomes LIVE, measured.
  //
  // fi_npu.c writes NPUCFG.CTRL with IN_EN and OUT_EN after the whole
  // bring-up sequence, which is two dozen 176-cycle serial frames, so
  // "the middle of the measured window" and "after the block is enabled"
  // are not the same interval and the first is not inside the second by
  // any argument a reader should have to make.
  //
  // THIS EXISTS BECAUSE THE POSITIVE CONTROL CAUGHT IT.  npu_campaign.py
  // control 4a clears CTRL.IN_EN and requires the run not to classify
  // MASKED; the first version drew its cycle at one eighth of the window
  // and MASKED was the correct answer, because the deposit landed on a
  // register the program had not written yet and then wrote.  The
  // control was right, the cycle was wrong, and the fix is to measure
  // the interval rather than to move the constant until the gate passes.
  // docs/52 section 6.1.
  integer ctrl_en_at = -1;
  always @(posedge clk) if (rst_n)
    if (dut.u_npu.ctrl_in_en && ctrl_en_at < 0) ctrl_en_at = cycles;

  // Was the transport busy AT THE CYCLE OF THE DEPOSIT?  Sampled once,
  // at the deposit, and reported per record.  A `ser` injection that
  // lands while the transport is idle lands in a register the next frame
  // start reloads -- `tx`, `rx`, `bit_cnt`, `hcnt` and `tick` are all
  // rewritten in ST_IDLE's transition -- so the stratum's rate is
  // conditional on this and the campaign reports it both ways.
  reg at_ser_busy = 1'b0;
  reg at_win_busy = 1'b0;
  reg at_ev_busy  = 1'b0;

  // ------------------------------------------------------------------
  // The kick cadence, measured rather than assumed.  Inherited from
  // tb_soc_fi.v unchanged.
  //
  // soc_wdog.v's W7 cadence window is BUILT here -- `WINDOW` defaults to
  // 1 and soc_gptimer.v does not override it -- and is NOT ARMED: `WINS`
  // resets to zero and fi_npu.c never writes WDOG_WIN, which is docs/43
  // section 8.1's campaign-A configuration and the one docs/46
  // recommends shipping.  `wdog_early` and `wdog_budget` are counted
  // anyway, because a nonzero entry would mean the block was firing in a
  // configuration where soc_wdog.sby's W7b proves it cannot, and that is
  // a check on the proof rather than a measurement of W7.  docs/44
  // section 9.4 makes the same distinction.
  //
  // The cadence itself still matters: it is what decides whether "the
  // watchdog did not fire" is a statement about the machine or about the
  // program.
  // ------------------------------------------------------------------
  integer kicks = 0;
  integer kick_last = -1;
  integer kick_gap_min = -1;
  integer kick_gap_max = -1;
  integer gap;
  integer wdog_early = 0, wdog_budget = 0;
  always @(posedge clk) if (rst_n) begin
    if (dut.u_timer0.u_wdog.kick_req) begin
      kicks = kicks + 1;
      if (kick_last >= 0) begin
        gap = cycles - kick_last;
        if (kick_gap_min < 0 || gap < kick_gap_min) kick_gap_min = gap;
        if (gap > kick_gap_max)                     kick_gap_max = gap;
      end
      kick_last = cycles;
    end
    if (dut.u_timer0.u_wdog.early_kick) wdog_early  = wdog_early + 1;
    if (dut.u_timer0.u_wdog.budget_out) wdog_budget = wdog_budget + 1;
  end

  // ------------------------------------------------------------------
  // Console.  soc_uart.v's format and tb_soc.v's receiver, unchanged.
  // ------------------------------------------------------------------
  integer rx_chars = 0;
  integer rx_framing_errors = 0;
  reg [31:0] rx_hash = 32'h811c_9dc5;
  reg [7:0] rx_byte;
  reg [175:0] rx_tail = 176'h0;      // last 22 characters
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
  // Termination.  tb_soc.v's criterion, unchanged and for its reasons.
  // `finished` is a WIRE and is LATCHED when the wait loop exits --
  // tb_soc_fi.v's header records the upset that made that necessary, and
  // `core_sleep_o` at the end is reported separately and compared.
  // ------------------------------------------------------------------
  reg saw_awake = 1'b0;
  always @(posedge clk) if (rst_n && !core_sleep) saw_awake <= 1'b1;

  wire finished = saw_awake && core_sleep &&
                  (dut.u_ram.mem[EXIT_MAGIC_ADDR[31:2]] == EXIT_MAGIC);
  reg done_q = 1'b0;

  // ------------------------------------------------------------------
  // The deposit
  // ------------------------------------------------------------------
  task do_deposit;
    begin
      fi_bitmask = 128'd1 << arg_bit;
      case (arg_site)
        `FI_DEPOSIT_CASES
        default: fi_hit = 1'b0;
      endcase
    end
  endtask

  // The deposit lands one quarter of a cycle after the edge: after every
  // flip-flop in the design has taken its new value and well before the
  // next edge samples it.  A deposit ON the edge would race the design's
  // own write and the outcome would depend on the simulator's event
  // ordering rather than on the fault model.
  //
  // `args_ready` is not decoration.  tb_soc_fi.v's header records what
  // testing `arg_site` before the plusarg parse cost docs/42: every
  // injection in the campaign was a no-op and the whole run came back
  // MASKED, which is exactly what a healthy design looks like.
  reg args_ready = 1'b0;

  // ------------------------------------------------------------------
  // THE QUEUE SENTINEL FILL, and why a campaign needs one.
  //
  // `hw/rtl/aer_fifo.v`'s storage array has NO RESET -- it is a memory,
  // and a memory that reset every entry would be a memory no SRAM macro
  // could implement, which is the same argument that file's header makes
  // about its registered output.  Its entry-parity bank has no reset for
  // the same reason.  So at time zero both are X, and they stay X in
  // every slot the design has not yet written.
  //
  // X IS NOT A PHYSICAL STATE.  A flip-flop in silicon powers up to a
  // zero or a one; X is the simulator declining to say which.  An
  // injection into an X bit is not a measurement of anything: `x ^ 1` is
  // x, so the deposit lands, changes nothing observable, and the run
  // comes back MASKED -- which is exactly the quiet nothing a
  // mis-targeted injector produces (docs/42 section 8.5 item 1).
  //
  // So both storage arrays are pre-loaded with a DEFINED word, which is
  // what `hw/tb/test_fi_campaign.py`'s `fill_fifo_sentinel` already does
  // for the die's own queues, with the same constant and for this
  // reason.  0xF0F0 is chosen there because its TYPE field is 2'b11 --
  // the reserved code docs/10 section 7.1 says the node drops and does
  // not count -- so a sentinel that somehow reached the datapath could
  // not be mistaken for a legitimate event, and it is not in the
  // expected stream.
  //
  // The parity bank is filled with the sentinel's OWN even parity rather
  // than with zero-because-it-is-tidy: 0xF0F0 has eight ones, so its
  // parity bit is 0, and filling both makes every unwritten slot
  // SELF-CONSISTENT.  A fill that left the two disagreeing would arm the
  // queue's own parity check on entries nothing wrote, and the campaign
  // would then be measuring a fault the harness injected.
  //
  // WHAT THIS COSTS, STATED.  It is an uncontrolled difference between
  // this campaign and any future gate-level one, exactly as docs/32
  // section 6 records for the die: the netlist's memories cannot be
  // filled this way.  docs/32 ran the experiment -- the RTL campaign
  // with the fill disabled -- and found it changed nothing on the four
  // records it was suspected of explaining.  Nothing equivalent has been
  // run here, and docs/52 section 9 says so.
  localparam [15:0] FIFO_SENTINEL = 16'hF0F0;
  integer sfill;
  reg sentinel_done = 1'b0;

  initial begin
    @(posedge rst_n);
    @(posedge clk);
    #(CLK_HALF / 2);
    for (sfill = 0; sfill < 8; sfill = sfill + 1) begin
      dut.u_npu.u_inj.mem[sfill] = FIFO_SENTINEL;
      dut.u_npu.u_cap.mem[sfill] = FIFO_SENTINEL;
    end
    dut.u_npu.u_inj.u_par.bits = 8'd0;   // ^0xF0F0 == 0, eight slots
    dut.u_npu.u_cap.u_par.bits = 8'd0;
    sentinel_done = 1'b1;
  end

  initial begin
    wait (args_ready);
    if (arg_site >= 0) begin
      @(posedge rst_n);
      // The deposit must not race the sentinel fill, or an injection
      // drawn at the first cycle after reset would be overwritten by it
      // and the record would say `hit` with nothing to show for it.
      wait (sentinel_done);
      while (cycles < arg_cycle) @(posedge clk);
      #(CLK_HALF / 2);
      at_ser_busy = dut.u_npu.ser_busy;
      at_win_busy = (dut.u_npu.win_state != 2'd0);
      at_ev_busy  = (dut.u_npu.ev_state  != 4'd0);
      do_deposit;
    end
  end

  // ------------------------------------------------------------------
  integer exit_code, exit_magic;

  initial begin
    if (!$value$plusargs("site=%d",   arg_site))   arg_site   = -1;
    if (!$value$plusargs("bit=%d",    arg_bit))    arg_bit    = 0;
    if (!$value$plusargs("cycle=%d",  arg_cycle))  arg_cycle  = 0;
    if (!$value$plusargs("armed=%d",  arg_armed))  arg_armed  = 1;
    if (!$value$plusargs("budget=%d", arg_budget)) arg_budget = `FI_DEFAULT_BUDGET;
    dump_sites = $test$plusargs("dumpsites") ? 1 : 0;
    args_ready = 1'b1;

    if ($test$plusargs("vcd")) begin
      $dumpfile("tb_soc_npu_fi.vcd");
      $dumpvars(0, tb_soc_npu_fi);
    end

    repeat (20) @(posedge clk);
    rst_n = 1'b1;

    // The site dump is emitted after reset so every hierarchical name in
    // it has been elaborated and $bits reports the width the simulator
    // actually built.  npu_campaign.py control 1 compares it against
    // hw/soc/fi/npu_targets.py before it injects anything.
    if (dump_sites) begin
      `FI_DUMP_SITES
      $display("SITECOUNT %0d", `FI_SITE_COUNT);
    end

    while (!finished && cycles < arg_budget) @(posedge clk);
    done_q = finished;

    // Twenty-four bit times of console drain, for tb_soc_fi.v's reason:
    // GRLIB's APBUART reports "transmit holding register empty", so the
    // last character can be two full frames behind the store that queued
    // it, and twelve bit times dropped the clean run's final newline.
    #(BIT_TIME * 24);

    exit_code  = dut.u_ram.mem[EXIT_CODE_ADDR[31:2]];
    exit_magic = dut.u_ram.mem[EXIT_MAGIC_ADDR[31:2]];

    $display("RECORD site=%0d bit=%0d cycle=%0d armed=%0d",
             arg_site, arg_bit, arg_cycle, arg_armed);
    $display("RECORD hit=%0d width=%0d before=%032x after=%032x",
             fi_hit, fi_w, fi_before, fi_after);
    $display("RECORD done=%0d cycles=%0d budget=%0d",
             done_q, cycles, arg_budget);
    $display("RECORD slept=%0d expired=%0d",
             core_sleep, (cycles >= arg_budget));
    $display("RECORD sig=%08x mask=%08x rounds=%0d",
             dut.u_ram.mem[FI_SIG_ADDR[31:2]],
             dut.u_ram.mem[FI_MASK_ADDR[31:2]],
             dut.u_ram.mem[FI_ROUNDS_ADDR[31:2]]);
    $display("RECORD exit=%08x magic=%08x", exit_code, exit_magic);
    $display("RECORD console_chars=%0d console_hash=%08x console_framing=%0d",
             rx_chars, rx_hash, rx_framing_errors);
    $display("RECORD console_tail=%s", rx_tail);
    $display("RECORD wdog1=%0d wdog2=%0d wdog3=%0d wdog_first=%0d",
             wdog_stage1, wdog_stage2, wdog_stage3, wdog_first_cycle);
    $display("RECORD traps=%0d mcause=%08x nmis=%0d",
             dut.u_ram.mem[TRAP_COUNT_ADDR[31:2]],
             dut.u_ram.mem[TRAP_MCAUSE_ADDR[31:2]],
             dut.u_ram.mem[NMI_COUNT_ADDR[31:2]]);
    $display("RECORD alert_minor=%0d alert_int=%0d alert_bus=%0d dblfault=%0d",
             saw_alert_minor, saw_alert_major_int,
             saw_alert_major_bus, saw_double_fault);
    $display("RECORD win_open=%0d win_close=%0d en_at=%0d",
             win_open, win_close, ctrl_en_at);
    $display("RECORD wdog_rld=%0d wdog_pre=%0d kicks=%0d kick_min=%0d kick_max=%0d",
             wdog_rld_at_open, dut.u_timer0.WDOG_PRESCALE,
             kicks, kick_gap_min, kick_gap_max);
    $display("RECORD wdog_early=%0d wdog_budget=%0d", wdog_early, wdog_budget);

    // ---- what the PROGRAM read, with a load instruction it executed --
    $display({"RECORD nev=%0d cause=%08x status=%08x drop=%08x ",
              "ovf=%08x oor=%08x cnt=%08x spins=%0d"},
             dut.u_ram.mem[FI_NEV_ADDR[31:2]],
             dut.u_ram.mem[FI_CAUSE_ADDR[31:2]],
             dut.u_ram.mem[FI_STATUS_ADDR[31:2]],
             dut.u_ram.mem[FI_DROP_ADDR[31:2]],
             dut.u_ram.mem[FI_OVF_ADDR[31:2]],
             dut.u_ram.mem[FI_OOR_ADDR[31:2]],
             dut.u_ram.mem[FI_CNT_ADDR[31:2]],
             dut.u_ram.mem[FI_SPINS_ADDR[31:2]]);

    // ---- what the BENCH saw, which no operator could ------------------
    $display("RECORD q_ptr_mm=%0d q_par_err=%0d q_rv_mm=%0d fetch_er=%0d",
             q_ptr_mm, q_par_err, q_rv_mm, fetch_expire_n);
    // docs/55's mechanisms: the two bounds, at the bench, and the three
    // fault lines counted where they leave soc_npu.
    $display({"RECORD ser_to=%0d win_to=%0d win_orph=%0d cor_ev=%0d ",
              "det_ev=%0d tmr_ev=%0d"},
             ser_to_n, win_to_n, win_orph_n, npu_cor_n, npu_det_n,
             npu_tmr_n);
    // docs/56's mechanism, and the state it exists to bound.
    $display("RECORD oh_to=%0d oh_req_max=%0d aer_mm=%0d",
             oh_to_n, oh_req_max, aer_mm_n);
    // ... and what the PROGRAM read out of BUSSTAT with a load. The pair
    // is docs/44 section 8.2's distinction made measurable: a counter a
    // testbench reads is not a counter an operator can see.
    $display("RECORD bst_cor=%08x bst_det=%08x bst_tmr=%08x",
             dut.u_ram.mem[FI_BSTCOR_ADDR[31:2]],
             dut.u_ram.mem[FI_BSTDET_ADDR[31:2]],
             dut.u_ram.mem[FI_BSTTMR_ADDR[31:2]]);
    $display("RECORD sentinel=%0d", sentinel_done);
    $display("RECORD npu_irq=%0d", saw_npu_irq);

    // ---- the exposure arithmetic -------------------------------------
    $display("RECORD ser_busy=%0d win_busy=%0d ev_busy=%0d",
             ser_busy_cyc, win_busy_cyc, ev_busy_cyc);
    $display("RECORD at_ser=%0d at_win=%0d at_ev=%0d",
             at_ser_busy, at_win_busy, at_ev_busy);
    $display("RECORD end");

    $finish;
  end

endmodule
