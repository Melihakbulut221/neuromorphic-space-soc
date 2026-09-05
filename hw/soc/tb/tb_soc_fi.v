// Fault-injection testbench for the management core.
//
// WHAT THIS IS FOR
//
// `docs/38-ibex-bringup.md` section 10 item 4 records the owner choosing
// Ibex `small-pmp` over `small-pmp-sec` and states the obligation that
// follows: "the core needs its own fault-injection campaign ... An
// unmeasured block, in a design whose entire claim is *measured* fault
// tolerance, is the gap a reviewer finds before we do."  It also states
// the second, harder question -- the watchdog is "the only backstop
// currently planned ... Whether it suffices is open".
//
// This file is the instrument for both.  It runs the whole SoC of
// docs/39 and docs/40 with one bit of one core flip-flop flipped at one
// cycle, and it reports what came out of the pins.  `hw/soc/fi/campaign.py`
// is the classifier; this file measures and does not judge.
//
// THE DIVISION OF LABOUR IS DELIBERATE.  Everything here is an
// observation.  Nothing here decides whether a run passed, because a
// testbench that classified would be a testbench that could be written
// around a result.  It emits one RECORD line of key=value facts and
// the campaign compares that against the golden run's.
//
// WHAT IS OBSERVED, AND WHY EACH ONE
//
//   uart_tx_o, decoded            the program's answer, over a pin, the
//                                 whole way through the fabric, the APB
//                                 bridge and the UART.  tb_soc.v's pass
//                                 criterion 4 is the same argument.
//   nmi_o, wdog_rst_o, wdog_no    the watchdog's three stages, as PORT
//                                 EVENTS with the cycle they happened
//                                 on.  This is the load-bearing one:
//                                 "the watchdog caught it" must be a
//                                 transition on a pin and never the
//                                 simulation running out of budget.
//                                 A run that ends on the budget with no
//                                 transition here is a HANG, and the
//                                 campaign cannot confuse the two.
//   core_sleep_o                  how the program says it has finished,
//                                 with the exit magic, exactly as
//                                 tb_soc.v requires.
//   alert_minor_o, alert_major_*  Ibex's own alert pins.
//   double_fault_seen_o           Ibex's own double-fault pin.
//
// and four words read out of RAM through a hierarchical reference, the
// same way tb_soc.v reads the exit code: `fi_sig`, `fi_mask`,
// `fi_rounds_done` and `trap_count`/`trap_mcause`.  Those are a
// convenience, not a pin -- a real bench would read them over the debug
// port or take them from the console -- and the campaign does not rest
// on any of them alone: the signature and the mask are also on the
// console, so the two paths can disagree and be caught disagreeing.
//
// THE INJECTION
//
// One bit, one flip-flop, one cycle, XORed in place.  The value stays
// flipped until the design's own logic writes the register again, which
// is the single-event-upset model docs/16 section 7.4 describes and the
// same one `hw/soc/tb/cocotb/test_soc_wdog_fi.py` uses.
//
// The deposit happens at a fixed point inside the cycle, after the
// clock edge and before the next one, so it can never race the design's
// own write.  `fi_before`, `fi_after` and `fi_w` are reported, so a
// deposit that did not land, or landed outside the register's width, is
// visible in the record rather than being a silent no-op that classifies
// MASKED.  docs/41 section 8.1's fourth honesty check is the same idea.
//
// The site table is `hw/soc/fi/targets.py` and is INCLUDED, not
// duplicated: that file generates the case statement below and the dump
// the campaign checks it against.
//
// WHAT THIS TESTBENCH DOES NOT DO
//
//   * it does not inject into anything outside `u_ibex` EXCEPT, since
//     docs/67, one word of one memory: +mem, +midx and +mbit name a
//     stored bit of the RAM or the boot ROM -- a data bit or, in the
//     hardened build, a check bit -- and the deposit lands there at
//     +cycle exactly as a core deposit would. hw/soc/fi/mem_campaign.py
//     draws those by region of the program's own link map. The fabric,
//     the CLINT, the timers and the watchdog itself are still not
//     targets here; the watchdog's own state is the subject of docs/41
//     section 8.
//   * it does not model a transient in combinational logic, a multi-bit
//     strike, or anything at gate level.
//   * it has no notion of a correct answer.  The golden run is the
//     campaign's, not this file's.

`timescale 1ns / 1ps

`ifndef ROM_HEX
  `define ROM_HEX "fi_workload.hex"
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

// docs/44 section 8.2's software-visible fault counters. Zero unless
// the FI_BUSSTAT build defined the symbols, and zero is how the report
// below decides not to print them.
`ifndef FI_BST_SEC_ADDR
  `define FI_BST_SEC_ADDR 32'h0
`endif
`ifndef FI_BST_RD_ADDR
  `define FI_BST_RD_ADDR 32'h0
`endif
`ifndef FI_BST_DED_ADDR
  `define FI_BST_DED_ADDR 32'h0
`endif
`ifndef FI_BST_TMR_ADDR
  `define FI_BST_TMR_ADDR 32'h0
`endif
// A ceiling that no legitimate run reaches.  The campaign always passes
// +budget explicitly; this is only so the file is runnable by hand.
`ifndef FI_DEFAULT_BUDGET
  `define FI_DEFAULT_BUDGET 200000
`endif

module tb_soc_fi;

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
  localparam [31:0] FI_BST_SEC_ADDR  = `FI_BST_SEC_ADDR;
  localparam [31:0] FI_BST_RD_ADDR   = `FI_BST_RD_ADDR;
  localparam [31:0] FI_BST_DED_ADDR  = `FI_BST_DED_ADDR;
  localparam [31:0] FI_BST_TMR_ADDR  = `FI_BST_TMR_ADDR;
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
  // docs/67: a memory target. -1 means none; 0 the RAM, 1 the boot ROM.
  // +midx is the word index inside the region, +mbit the bit of the
  // stored row: 0..31 the data word, 32.. the check field (32 bits on the
  // RAM's byte code, 7 on the ROM's word code), which exists only in the
  // build fi_core.sh made with SOC_MEM_HARDEN=1.
  integer arg_mem    = -1;
  integer arg_midx   = 0;
  integer arg_mbit   = 0;
  reg [31:0] mem_before = 32'h0;
  reg [31:0] mem_after  = 32'h0;

  // The watchdog bootstrap pin.  soc_wdog.v W1 samples it ONCE when
  // power-on reset releases and ignores it for ever after, so driving it
  // from a plusarg here is a board configuration and not a back door.
  //
  // THIS PIN IS THE COUNTERFACTUAL.  The campaign runs every injection
  // twice, once with the watchdog armed and once with it held off, and
  // the pair is what turns "the watchdog escalated" into "the watchdog
  // escalated on a machine that was in fact dead".  Without the second
  // run there is no way to tell a catch from a machine that would have
  // been fine, and docs/41 section 8.3 makes the same argument about the
  // hardened and unhardened watchdog.
  wire wdog_dis = (arg_armed != 0) ? 1'b0 : 1'b1;

  wire uart_tx, uart_irq;
  wire wdog_n, wdog_rst, nmi, irq_timer, irq_soft, gptimer_irq;
  wire alert_minor, alert_major_internal, alert_major_bus;
  wire double_fault_seen, core_sleep;

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
      .alert_minor_o          (alert_minor),
      .alert_major_internal_o (alert_major_internal),
      .alert_major_bus_o      (alert_major_bus),
      .double_fault_seen_o    (double_fault_seen),
      .core_sleep_o           (core_sleep)
  );

  // ------------------------------------------------------------------
  // The site table, generated from hw/soc/fi/targets.py
  // ------------------------------------------------------------------
`include "fi_targets.vh"

  reg [127:0] fi_bitmask = 128'd0;
  reg [127:0] fi_before  = 128'd0;
  reg [127:0] fi_after   = 128'd0;
  integer     fi_w       = 0;
  reg         fi_hit     = 1'b0;
  reg         fi_done    = 1'b0;

  // ------------------------------------------------------------------
  // Cycle counter, on the POWER-ON reset.  It keeps running across a
  // watchdog reset, which is what makes an escalation cycle comparable
  // between a run that reset itself and one that did not.
  // ------------------------------------------------------------------
  integer cycles = 0;
  always @(posedge clk) if (rst_n) cycles = cycles + 1;

  // ------------------------------------------------------------------
  // Watchdog escalation, as ordered port events.
  //
  // Counted AND time-stamped.  The first stage-1 cycle is the quantity
  // the campaign uses to say how long the backstop took to notice, and
  // it is meaningless unless it is a transition on a pin.
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
  // Latched alerts and the double-fault pin.
  // ------------------------------------------------------------------
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
  // The measured injection window.
  //
  // fi_workload.c writes 1 into fi_phase when the measured kernel opens
  // and 2 when it closes, and the campaign draws its cycles inside the
  // interval those two transitions bound.  Measuring the window rather
  // than assuming it is docs/41 section 8.1's last honesty clause: a
  // change to the workload moves the draws with it instead of silently
  // pushing half the campaign past the end of the run.
  //
  // Only the FIRST transitions are recorded.  A run that takes a
  // watchdog reset re-enters phase 1, and the window of record is the
  // clean run's.
  // ------------------------------------------------------------------
  // The watchdog's programmed timeout, read out of the block at the
  // moment the measured window opens rather than written down in the
  // campaign.  campaign.py derives its simulation budget and its
  // escalation-ladder length from this, so a change to the workload's
  // FI_WDOG_RELOAD moves the budget with it instead of silently making
  // "the watchdog did not fire" mean "the watchdog had not got there
  // yet".
  integer wdog_rld_at_open = -1;

  integer win_open = -1, win_close = -1;
  reg [31:0] phase_q = 32'hffff_ffff;
  always @(posedge clk) if (rst_n) begin
    if (dut.u_ram.mem[FI_PHASE_ADDR[31:2]] !== phase_q) begin
      phase_q = dut.u_ram.mem[FI_PHASE_ADDR[31:2]];
      if (phase_q == 32'd1 && win_open  < 0) begin
        win_open = cycles;
        wdog_rld_at_open = dut.u_timer0.u_wdog.reload;
      end
      if (phase_q == 32'd2 && win_close < 0) win_close = cycles;
    end
  end

  // ------------------------------------------------------------------
  // The kick cadence, measured rather than assumed.
  //
  // soc_wdog.v W7 makes a kick that arrives too EARLY a violation, and
  // the bound it is checked against is a fraction of the period. What
  // fraction a given program can live inside is a property OF THAT
  // PROGRAM -- the ratio of its longest to its shortest interval
  // between kicks -- and it is not something a designer should guess.
  // So the instrument measures it: every kick request the block sees,
  // the interval since the previous one, and the smallest and largest
  // of those intervals over the run.
  //
  // `kick_req` and not `kick`: the quantity of interest is when the
  // SOFTWARE asked, including the asks the block rejected.
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

`ifdef FI_REGFILE_SECDED
  // ------------------------------------------------------------------
  // The register file's correction report.
  //
  // These four registers are INSIDE the substituted register file and
  // drive no port of it, because `ibex_register_file_ff` has upstream's
  // port list and upstream's port list has no error output. In the
  // netlist opt_clean deletes them; here they are readable because this
  // is a simulation, exactly as `dut.u_ram.mem[...]` is readable and
  // for the same reason.
  //
  // THIS IS A BENCH OBSERVATION AND NOT AN OPERATOR CHANNEL, and the
  // campaign's report says so where it uses them. In silicon a
  // corrected upset is indistinguishable from no upset at all, which is
  // the price hw/soc/rtl/ibex_regfile_secded.v pays for changing
  // nothing in Ibex.
  `define FI_RF_PATH dut.u_ibex.gen_regfile_ff.register_file_i.g_plain_rf.g_secded
`endif

  // ------------------------------------------------------------------
  // Console.  Start bit, eight data bits LSB first, one stop bit, no
  // parity, sampled in the middle -- soc_uart.v's format and tb_soc.v's
  // receiver, unchanged.
  //
  // The stream is reduced to a length and a hash rather than kept, so a
  // record is one line.  The hash is FNV-1a, chosen only because it is
  // four lines and order-dependent; nothing rests on its strength, and
  // the campaign additionally compares the last characters verbatim.
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
  // Termination.  tb_soc.v's criterion, unchanged and for its reasons:
  // Ibex reports core_sleep_o high while it is held in reset, so "was
  // awake and is now asleep" goes true in the middle of a watchdog
  // reset.  Requiring the exit magic makes it "the program posted its
  // result and then slept".
  // ------------------------------------------------------------------
  reg saw_awake = 1'b0;
  always @(posedge clk) if (rst_n && !core_sleep) saw_awake <= 1'b1;

  // docs/67: in the hardened build every word this bench reads out of
  // the RAM goes through soc_mem.v's `observe`, which decodes it as a
  // bus read would. The raw array would show a deposited-and-not-yet-
  // read flip as a changed answer, and a flip in the exit magic would
  // look like a run that never finished. A task and not a function,
  // because `observe` takes a zero-delay step to let the decoders
  // settle and a function may not call it.
  task ram_word;
    input  [31:0] addr;
    output [31:0] w;
    begin
`ifdef FI_MEM_HARDENED
      dut.u_ram.g_ecc.observe(addr[31:2], w);
`else
      w = dut.u_ram.mem[addr[31:2]];
`endif
    end
  endtask

  // The termination condition still reads the RAW array, on purpose:
  // the program's last act is to store the magic, so no deposit drawn
  // inside the window can survive into it, and reading it through a
  // sampled `observe` moved docs/42's 18,682-cycle clean run by one
  // cycle. The RECORD fields below are what a deposit can survive into,
  // and those go through the codec.
  wire finished = saw_awake && core_sleep &&
                  (dut.u_ram.mem[EXIT_MAGIC_ADDR[31:2]] == EXIT_MAGIC);

  // `finished` is a WIRE and must be latched when the wait loop exits.
  //
  // The first version reported it live, long after the loop, and one
  // upset produced a run in which core_sleep_o PULSED: setting
  // `debug_mode_q` puts Ibex in debug mode, where the RISC-V debug
  // specification makes WFI a no-op, so `crt0.S`'s terminating
  // `wfi; j` loop wakes immediately every time round.  The wait loop
  // saw the pulse and exited at 18,682 cycles -- the clean run's own
  // count -- and the report then read the wire again, found it low, and
  // recorded the run as never having completed inside a 600,000-cycle
  // budget.  Seven injections were classified HANG on that basis.
  //
  // `core_sleep_o` at the end of the run is now reported separately and
  // is part of the compared result, because a core that posts the right
  // answer and then never sleeps IS observably different from one that
  // does, on a pin, and calling that MASKED would be the narrow green
  // check this repository keeps being bitten by.
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
      fi_done = 1'b1;
    end
  endtask

  // The memory deposit, docs/67. The data array is `mem` in both builds;
  // the check array exists only under g_ecc and only in the hardened
  // build, so a check-bit request against the other build reports a
  // miss rather than depositing nowhere -- mem_campaign.py refuses a
  // record whose hit is 0.
  task do_mem_deposit;
    begin
      fi_hit = 1'b0;
      fi_w   = 0;
      if (arg_mem == 0) begin
        if (arg_mbit < 32) begin
          mem_before = dut.u_ram.mem[arg_midx];
          dut.u_ram.mem[arg_midx] = mem_before ^ (32'd1 << arg_mbit);
          mem_after  = dut.u_ram.mem[arg_midx];
          fi_hit = 1'b1; fi_w = 32;
        end
`ifdef FI_MEM_HARDENED
        else if (arg_mbit < 64) begin
          mem_before = dut.u_ram.g_ecc.chk[arg_midx];
          dut.u_ram.g_ecc.chk[arg_midx] = mem_before ^ (32'd1 << (arg_mbit - 32));
          mem_after  = dut.u_ram.g_ecc.chk[arg_midx];
          fi_hit = 1'b1; fi_w = 64;
        end
`endif
      end else if (arg_mem == 1) begin
        if (arg_mbit < 32) begin
          mem_before = dut.u_rom.mem[arg_midx];
          dut.u_rom.mem[arg_midx] = mem_before ^ (32'd1 << arg_mbit);
          mem_after  = dut.u_rom.mem[arg_midx];
          fi_hit = 1'b1; fi_w = 32;
        end
`ifdef FI_MEM_HARDENED
        else if (arg_mbit < 39) begin
          mem_before = {25'h0, dut.u_rom.g_ecc.chk[arg_midx]};
          dut.u_rom.g_ecc.chk[arg_midx] = mem_before[6:0] ^ (7'd1 << (arg_mbit - 32));
          mem_after  = {25'h0, dut.u_rom.g_ecc.chk[arg_midx]};
          fi_hit = 1'b1; fi_w = 39;
        end
`endif
      end
      fi_done = 1'b1;
    end
  endtask

  // The deposit lands one quarter of a cycle after the edge: after every
  // flip-flop in the design has taken its new value and well before the
  // next edge samples it.  A deposit ON the edge would race the design's
  // own write and the outcome would depend on the simulator's event
  // ordering rather than on the fault model.
  //
  // `args_ready` is not decoration.  The plusargs are parsed in the
  // other `initial` block, and the first version of this one tested
  // `arg_site` at time zero -- before the parse -- so it saw the
  // declaration's -1 and every injection in the campaign was a no-op.
  // The whole run came back MASKED, which is exactly what a healthy
  // design looks like.  campaign.py's positive control caught it: the
  // stack pointer with bit 20 set cannot classify MASKED.  This is the
  // same shape as the eight instances docs/41 section 6.6 lists and it
  // is why that control exists.
  reg args_ready = 1'b0;

  initial begin
    wait (args_ready);
    if (arg_site >= 0 || arg_mem >= 0) begin
      @(posedge rst_n);
      while (cycles < arg_cycle) @(posedge clk);
      #(CLK_HALF / 2);
      if (arg_site >= 0) do_deposit;
      else               do_mem_deposit;
    end
  end

  // ------------------------------------------------------------------
  integer exit_code, exit_magic;
  reg [31:0] rec_sig, rec_mask, rec_rounds, rec_traps, rec_mcause, rec_nmis,
             rec_bst_sec, rec_bst_rd, rec_bst_ded, rec_bst_tmr;
  integer rec_cycles;

  initial begin
    if (!$value$plusargs("site=%d",   arg_site))   arg_site   = -1;
    if (!$value$plusargs("bit=%d",    arg_bit))    arg_bit    = 0;
    if (!$value$plusargs("cycle=%d",  arg_cycle))  arg_cycle  = 0;
    if (!$value$plusargs("armed=%d",  arg_armed))  arg_armed  = 1;
    if (!$value$plusargs("budget=%d", arg_budget)) arg_budget = `FI_DEFAULT_BUDGET;
    if (!$value$plusargs("mem=%d",    arg_mem))    arg_mem    = -1;
    if (!$value$plusargs("midx=%d",   arg_midx))   arg_midx   = 0;
    if (!$value$plusargs("mbit=%d",   arg_mbit))   arg_mbit   = 0;
    dump_sites = $test$plusargs("dumpsites") ? 1 : 0;
    args_ready = 1'b1;

    if ($test$plusargs("vcd")) begin
      $dumpfile("tb_soc_fi.vcd");
      $dumpvars(0, tb_soc_fi);
    end

    repeat (20) @(posedge clk);
    rst_n = 1'b1;

    // The site dump is emitted after reset so every hierarchical name in
    // it has been elaborated and $bits reports the width the simulator
    // actually built.  The campaign compares this against
    // hw/soc/fi/targets.py before it injects anything: a path that moved
    // in the RTL, a width that changed, or an index that slipped is
    // caught here and not by a reader.
    if (dump_sites) begin
      `FI_DUMP_SITES
      $display("SITECOUNT %0d", `FI_SITE_COUNT);
    end

    while (!finished && cycles < arg_budget) @(posedge clk);
    done_q = finished;

    // Let the console drain, so a run is not recorded as one character
    // short of the golden one for no reason but where it stopped.
    //
    // Twenty-four bit times, not twelve.  GRLIB's APBUART reports TE --
    // "transmit holding register empty" -- so the program's last write
    // returns while the PREVIOUS character is still shifting, and the
    // last character can be up to two full frames behind the store that
    // queued it.  Twelve bit times covered one frame and dropped the
    // final newline of the clean run, which would have made every
    // injected run that happened to be a few cycles slower differ from
    // golden by one console character for a reason that has nothing to
    // do with the injection.
    #(BIT_TIME * 24);

    // The cycle count is captured BEFORE the corrected reads: `observe`
    // takes zero-delay steps, the console drain ends exactly on a
    // clock edge, and reading `cycles` after those steps reports the
    // edge's increment where the raw read did not -- one cycle, and a
    // published number (docs/42's 18,682).
    rec_cycles = cycles;
    ram_word(EXIT_CODE_ADDR,   exit_code);
    ram_word(EXIT_MAGIC_ADDR,  exit_magic);
    ram_word(FI_SIG_ADDR,      rec_sig);
    ram_word(FI_MASK_ADDR,     rec_mask);
    ram_word(FI_ROUNDS_ADDR,   rec_rounds);
    ram_word(TRAP_COUNT_ADDR,  rec_traps);
    ram_word(TRAP_MCAUSE_ADDR, rec_mcause);
    ram_word(NMI_COUNT_ADDR,   rec_nmis);
    ram_word(FI_BST_SEC_ADDR,  rec_bst_sec);
    ram_word(FI_BST_RD_ADDR,   rec_bst_rd);
    ram_word(FI_BST_DED_ADDR,  rec_bst_ded);
    ram_word(FI_BST_TMR_ADDR,  rec_bst_tmr);

    $display("RECORD site=%0d bit=%0d cycle=%0d armed=%0d",
             arg_site, arg_bit, arg_cycle, arg_armed);
    $display("RECORD hit=%0d width=%0d before=%032x after=%032x",
             fi_hit, fi_w, fi_before, fi_after);
    // docs/67: the memory deposit, and what the SCRUB block counted.
    // The counters are read hierarchically, as the register file's are
    // above, and the same caveat applies: in silicon they are read over
    // the peripheral bus, and the program in this campaign does not.
    $display("RECORD mem=%0d midx=%0d mbit=%0d mem_before=%08x mem_after=%08x",
             arg_mem, arg_midx, arg_mbit, mem_before, mem_after);
    $display({"RECORD scr_ramsec=%0d scr_ramrd=%0d scr_ramded=%0d ",
              "scr_romsec=%0d scr_romrd=%0d scr_romded=%0d ",
              "scr_ramaddr=%08x scr_romaddr=%08x"},
             dut.u_scrub.g_src[0].cnt_q, dut.u_scrub.g_src[1].cnt_q,
             dut.u_scrub.g_src[2].cnt_q, dut.u_scrub.g_src[3].cnt_q,
             dut.u_scrub.g_src[4].cnt_q, dut.u_scrub.g_src[5].cnt_q,
             dut.u_scrub.ram_addr_q, dut.u_scrub.rom_addr_q);
    $display("RECORD done=%0d cycles=%0d budget=%0d",
             done_q, rec_cycles, arg_budget);
    $display("RECORD slept=%0d expired=%0d",
             core_sleep, (rec_cycles >= arg_budget));
    $display("RECORD sig=%08x mask=%08x rounds=%0d",
             rec_sig,
             rec_mask,
             rec_rounds);
    $display("RECORD exit=%08x magic=%08x", exit_code, exit_magic);
    $display("RECORD console_chars=%0d console_hash=%08x console_framing=%0d",
             rx_chars, rx_hash, rx_framing_errors);
    $display("RECORD console_tail=%s", rx_tail);
    $display("RECORD wdog1=%0d wdog2=%0d wdog3=%0d wdog_first=%0d",
             wdog_stage1, wdog_stage2, wdog_stage3, wdog_first_cycle);
    $display("RECORD traps=%0d mcause=%08x nmis=%0d",
             rec_traps,
             rec_mcause,
             rec_nmis);
    $display("RECORD alert_minor=%0d alert_int=%0d alert_bus=%0d dblfault=%0d",
             saw_alert_minor, saw_alert_major_int,
             saw_alert_major_bus, saw_double_fault);
    $display("RECORD win_open=%0d win_close=%0d", win_open, win_close);
    $display("RECORD wdog_rld=%0d wdog_pre=%0d kicks=%0d kick_min=%0d kick_max=%0d",
             wdog_rld_at_open, dut.u_timer0.WDOG_PRESCALE,
             kicks, kick_gap_min, kick_gap_max);
    $display("RECORD wdog_early=%0d wdog_budget=%0d wdog_win=%08x",
             wdog_early, wdog_budget, dut.u_timer0.u_wdog.prot);
`ifdef FI_REGFILE_SECDED
    $display("RECORD rf_sec=%0d rf_ded=%0d rf_sec_seen=%0d rf_ded_seen=%0d",
             `FI_RF_PATH.sec_cycles, `FI_RF_PATH.ded_cycles,
             `FI_RF_PATH.sec_seen,   `FI_RF_PATH.ded_seen);
`else
    $display("RECORD rf_sec=0 rf_ded=0 rf_sec_seen=0 rf_ded_seen=0");
`endif

    // docs/44 section 8.2: the same events, counted by the SoC and read
    // by a LOAD INSTRUCTION THE CORE EXECUTED, beside the bench's
    // hierarchical read of the module's own counters. Printed only when
    // the FI_BUSSTAT build defined the symbols -- the default build's
    // ROM image is byte-identical to docs/42's and must stay so.
    //
    // The ADDRESS is printed with the values on purpose. A counter that
    // reads zero because the symbol was not found looks exactly like a
    // counter that never moved, and a report that cannot tell those two
    // apart is the failure this whole feature exists to remove.
    if (FI_BST_SEC_ADDR != 32'h0)
      $display({"RECORD sw_bst_sec=%0d sw_bst_rd=%0d sw_bst_ded=%0d ",
                "sw_bst_tmr=%0d sw_bst_at=%08x"},
               rec_bst_sec,
               rec_bst_rd,
               rec_bst_ded,
               rec_bst_tmr,
               FI_BST_SEC_ADDR);
    $display("RECORD end");

    $finish;
  end

endmodule
