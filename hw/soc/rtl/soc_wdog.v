// The watchdog.
//
// =====================================================================
// WHY THIS BLOCK IS NOT A TIMER WITH A RESET ON THE END
// =====================================================================
//
// `docs/38-ibex-bringup.md` section 10 item 4 chose Ibex `small-pmp`:
// no lockstep, no shadow register file. This project's TMR covers the
// NPU and the configuration state and does not reach inside the CPU. The
// consequence that decision records, in its own words, is that "the
// management processor is therefore the least hardened block in the
// design" and that "the watchdog in the docs/08 map is the only backstop
// currently planned, and resetting a core is a coarse instrument".
//
// So this watchdog is carrying weight a GRLIB GPTIMER's last timer was
// never designed to carry, and building it to that template would have
// been the wrong answer. `docs/40-interrupts-timers-watchdog.md` section
// 5 argues each of the five departures below. They are stated here as
// the specification the properties in
// hw/soc/formal/soc_wdog_props.v and the suite in
// hw/soc/tb/cocotb/test_soc_wdog.py are written against.
//
// W1. ARMED AT RESET AND NOT DISABLEABLE BY SOFTWARE. EN reads 1 out of
//     power-on reset and a write of 0 to it is ignored. There is exactly
//     one thing that can stop this block and it is not software: the
//     dis_i input, a bootstrap pin, sampled once when power-on reset
//     releases and never again. A watchdog whose watched software can
//     switch it off is not a backstop against software that has stopped
//     behaving, which is the only case it exists for.
//
// W2. ITS TIME BASE IS NOT SOFTWARE-PROGRAMMABLE. GRLIB's GPTIMER
//     watchdog shares the block's prescaler, and that prescaler is a
//     writable register -- so on a real GPTIMER, software that cannot
//     clear EN can still multiply the timeout by up to 1024 with one
//     store, which is the same thing with extra steps. Here the
//     watchdog has its own fixed divider, PRESCALE, that no register
//     reaches, and its counter is WIDTH bits. The longest timeout this
//     block can be talked into is therefore a constant of the netlist,
//         2^WIDTH * PRESCALE clocks,
//     and no value software can write to the reload register exceeds
//     it, because no such value fits. There is deliberately no clamp
//     register and no maximum-reload parameter: a bound enforced by the
//     width of a counter cannot be misconfigured, and one enforced by a
//     comparator can.
//
// W3. IT ESCALATES IN THREE STAGES RATHER THAN RESETTING.
//       stage 1  the counter reaches zero: raise nmi_o and reload.
//                Software gets one full timeout to notice, record and
//                recover. nmi_o goes to Ibex's irq_nm_i and NOT to a
//                maskable line, because the state this fires in is the
//                state where mstatus.MIE is quite likely already zero --
//                the core clears it on entry to every trap handler -- so
//                a maskable interrupt would simply never be taken.
//       stage 2  the counter reaches zero AGAIN with stage 1 still
//                unacknowledged: assert rst_req_o for RST_CYCLES. The
//                core is not involved and cannot prevent it.
//       stage 3  after ESCALATE watchdog resets since power-on: assert
//                wdog_o, the external pin, latched until power-on reset.
//                Resetting has demonstrably not worked and the decision
//                belongs to whatever is outside the chip.
//
// W4. ITS STATE SURVIVES THE RESET IT CAUSES. Everything in this file is
//     in the POWER-ON reset domain. rst_req_o drives the system reset;
//     nothing here is reset by it. So after a watchdog reset the boot
//     code can read WDOGSTAT and find WDOGRST set and RSTCNT non-zero,
//     and a watchdog reset is distinguishable from a power cycle. A
//     watchdog that erased its own evidence would leave the operator
//     with a machine that reboots for no discoverable reason, which is
//     the worst possible failure report from a spacecraft.
//
// W5. EVERY WRITE IS KEYED. No write to any register of this block has
//     any effect unless wdata[31:16] == KEY. The whole failure mode this
//     block guards is a processor executing something other than the
//     program, and such a processor stores wild values to wild
//     addresses; a single-bit "pet me" with no key is a watchdog a
//     runaway can pet by accident, and an unkeyed acknowledge bit is one
//     a runaway can hold in stage 1 forever by spraying stores at the
//     status register. The rule is therefore all writes and not just the
//     kick, and the value field of every register is consequently the
//     LOW half word -- which is why WIDTH may not exceed 16. GRLIB
//     leaves the upper half of these registers reserved, so this is a
//     documented divergence and not an incompatibility with a defined
//     field.
//
// =====================================================================
// ONE CONSEQUENCE THAT WAS NOT OBVIOUS AND IS NOT A CHOICE
// =====================================================================
//
// Entering stage 2 CLEARS the pending stage-1 NMI. It has to. Ibex
// initialises mtvec to boot_addr when it boots
// (ext/ibex/rtl/ibex_if_stage.sv, csr_mtvec_init_o), so at the instant
// the system reset releases the NMI vector is boot_addr + 0x7C -- four
// bytes BELOW the reset vector at boot_addr + 0x80, in ROM the image
// does not cover. A watchdog that held nmi_o through its own reset would
// therefore vector the freshly reset core into padding before it had
// executed a single instruction of the program. The reset supersedes the
// NMI; the fact that stage 1 happened survives in WDOGSTAT.
//
// =====================================================================
// WHAT THIS BLOCK DOES NOT DO
// =====================================================================
//
//   * No windowed mode. A kick that arrives too EARLY is accepted. A
//     windowed watchdog rejects those and so catches a fast runaway loop
//     that happens to include the kick; this one does not, and a runaway
//     that keeps kicking is invisible to it.
//   * No protection of its own state. The counter, the reload and the
//     status bits have no parity, no redundancy and no TMR. The block
//     whose job is to catch upsets is itself unprotected, which is a gap
//     and not an omission -- docs/40 section 9 records it as the first
//     thing the hardening architecture should reach.
//   * No independent clock. It counts the system clock. If the clock
//     stops, the watchdog stops with everything else and nothing fires.
//   * It cannot tell a hung core from a core doing something slow and
//     legitimate. That is what the reload value is for and choosing it
//     is a software problem this block cannot solve.
//   * dis_i is a hole by construction: a board that ties it high has no
//     watchdog. It exists so that lab bring-up and gate-level debug do
//     not have to fight it, and WDOGSTAT.DISABLED says so out loud so
//     that a part in that state cannot claim to be protected.

`timescale 1ns / 1ps

module soc_wdog #(
    // Down-counter width, at most 16: the upper half of every write is
    // the key (W5). With PRESCALE this fixes the longest timeout the
    // block can be programmed to, which W2 requires to be a constant.
    parameter integer WIDTH     = 16,
    // Fixed divider in front of the counter. NOT software reachable.
    parameter integer PRESCALE  = 16,
    // Cycles rst_req_o is held asserted.
    parameter integer RST_CYCLES = 16,
    // Watchdog resets since power-on after which wdog_o latches.
    parameter integer ESCALATE  = 2,
    // Upper half of a control-register write, W5.
    parameter [15:0] KEY = 16'hA51F
) (
    input  wire        clk_i,
    // POWER-ON reset. The only reset in this file, W4.
    input  wire        rst_por_ni,

    // Bootstrap pin, W1. Sampled once, when rst_por_ni releases.
    input  wire        dis_i,

    // ---- register port, decoded by soc_gptimer.v ----
    // One-hot: bit 0 counter, 1 reload, 2 control, 3 status.
    input  wire [3:0]  sel_i,
    input  wire        we_i,
    input  wire [31:0] wdata_i,
    output reg  [31:0] rdata_o,

    // ---- escalation ----
    output wire        nmi_o,        // stage 1, to Ibex irq_nm_i
    output wire        rst_req_o,    // stage 2, drives the system reset
    output wire        wdog_no       // stage 3, external pin, active low
);

  localparam integer PRE_W = (PRESCALE <= 1) ? 1 : $clog2(PRESCALE);
  localparam integer RST_W = (RST_CYCLES <= 1) ? 1 : $clog2(RST_CYCLES + 1);
  localparam integer CNT_W = 8;   // saturating reset counter

  // Sized constants, so that no expression below part-selects a
  // parameter. A part-select of a parameter is accepted by some tools
  // and not others, and three of them read this same file: Icarus,
  // Yosys and Verilator.
  //
  // Narrowing an integer parameter to the width it is declared with is
  // exactly what is meant here, so the truncation warning is turned off
  // for these three lines and for nothing else. A file-wide waiver would
  // hide the truncations that are NOT intended.
  /* verilator lint_off WIDTHTRUNC */
  localparam [PRE_W-1:0] PRE_TOP = PRESCALE - 1;
  localparam [RST_W-1:0] RST_TOP = RST_CYCLES;
  localparam [CNT_W-1:0] ESC_AT  = ESCALATE;
  /* verilator lint_on WIDTHTRUNC */

  // ---- GRLIB GPTIMER timer control bits (grip.pdf table 463) ----
  localparam integer B_EN = 0, B_RS = 1, B_LD = 2, B_IE = 3, B_IP = 4;

  // ---- WDOGSTAT bit positions, this project's extension ----
  localparam integer B_STAT_NMI = 0, B_STAT_RST = 1,
                     B_STAT_ESC = 2, B_STAT_DIS = 3;

  // -------------------------------------------------------------------
  // The bootstrap pin, latched once
  // -------------------------------------------------------------------
  reg dis_q, dis_seen;
  always @(posedge clk_i or negedge rst_por_ni) begin
    if (!rst_por_ni) begin
      dis_q    <= 1'b0;
      dis_seen <= 1'b0;
    end else if (!dis_seen) begin
      dis_q    <= dis_i;
      dis_seen <= 1'b1;
    end
  end

  wire armed = !dis_q;

  // -------------------------------------------------------------------
  // Register writes
  // -------------------------------------------------------------------
  //
  // A control write is effective only with the key (W5). The reload and
  // the counter are ordinary writes: neither can disable the block --
  // the reload is clamped (W2) and writing the counter can only ever
  // move the deadline within the same clamp.
  wire keyed   = we_i && (wdata_i[31:16] == KEY);
  wire wr_cnt  = sel_i[0] && keyed;
  wire wr_rld  = sel_i[1] && keyed;
  wire wr_ctrl = sel_i[2] && keyed;
  wire wr_stat = sel_i[3] && keyed;

  // The value field of every register is wdata_i[15:0]; the upper half
  // is the key (W5) and never reaches a register. Bits above WIDTH are
  // discarded, which is the whole of W2's bound: a reload longer than
  // the counter does not fit in the counter.
  wire [15:0]      wval = wdata_i[15:0];
  wire [WIDTH-1:0] wnum = wval[WIDTH-1:0];

  // -------------------------------------------------------------------
  // State, all of it in the power-on domain (W4)
  // -------------------------------------------------------------------
  reg [WIDTH-1:0] reload;
  reg [WIDTH-1:0] counter;
  reg [PRE_W-1:0] pre;
  reg             nmi_pend;      // stage 1 fired, not acknowledged
  reg             rst_seen;      // a watchdog reset happened since POR
  reg [CNT_W-1:0] rst_count;     // saturating
  reg [RST_W-1:0] rst_hold;      // stage-2 stretch

  wire in_reset = (rst_hold != 0);
  wire tick     = (PRESCALE <= 1) || (pre == 0);
  wire expire   = armed && !in_reset && tick && (counter == 0);

  // Stage 2 is the SECOND expiry with stage 1 still unacknowledged.
  wire stage2   = expire && nmi_pend;

  assign nmi_o     = nmi_pend;
  assign rst_req_o = in_reset;
  assign wdog_no   = !(rst_count >= ESC_AT);

  // ---- a kick ----
  //
  // A keyed control write with LD set reloads the counter. It does NOT
  // acknowledge a pending NMI: "I am alive" and "I have seen and handled
  // the warning" are different statements and collapsing them would let
  // a periodic kicker that never looks at the status register mask a
  // stage-1 event forever.
  wire kick = wr_ctrl && wval[B_LD];

  always @(posedge clk_i or negedge rst_por_ni) begin
    if (!rst_por_ni) begin
      // Armed, at the longest timeout the block allows. Anything shorter
      // as a reset default risks a board whose boot is slower than the
      // watchdog resetting forever with no way in -- docs/40 section 5.
      reload    <= {WIDTH{1'b1}};
      counter   <= {WIDTH{1'b1}};
      pre       <= 0;
      nmi_pend  <= 1'b0;
      rst_seen  <= 1'b0;
      rst_count <= 0;
      rst_hold  <= 0;
    end else begin
      // ---- prescaler ----
      if (PRESCALE > 1) begin
        if (pre == 0) pre <= PRE_TOP;
        else          pre <= pre - 1'b1;
      end

      // ---- the reset stretch ----
      if (rst_hold != 0) rst_hold <= rst_hold - 1'b1;

      // ---- counter ----
      if (kick) begin
        counter <= reload;
      end else if (in_reset) begin
        // Held reloaded for the whole of the reset it caused, so the
        // core comes out of reset with the full budget in front of it.
        // This is the "staged through boot" half of docs/08 section 4
        // item 8: the boot stage's timeout is the reset default, and
        // software shortens it once it is running.
        counter <= reload;
      end else if (wr_cnt) begin
        counter <= wnum;
      end else if (armed && tick) begin
        counter <= (counter == 0) ? reload : counter - 1'b1;
      end

      // The reload is restored to the longest timeout by a stage-2
      // reset, and this is NOT cosmetic. It was found by running the
      // thing: the reload register is in the power-on domain (W4), so a
      // short timeout that software installed before it went wrong
      // SURVIVES the reset that going wrong caused. The first version of
      // this file kept it, and the SoC entered an unbreakable loop --
      // reset, 1,952 clocks of boot, reset again, forever, with the
      // console never reaching its first character. Every reset stage of
      // GR716B's boot flow (docs/08 section 2.4) starts from the boot
      // timeout for the same reason: whatever the last software
      // configured, the next boot gets the whole budget.
      if (stage2)      reload <= {WIDTH{1'b1}};
      else if (wr_rld) reload <= wnum;

      // ---- escalation ----
      if (stage2) begin
        rst_hold  <= RST_TOP;
        rst_seen  <= 1'b1;
        if (~&rst_count) rst_count <= rst_count + 1'b1;
        // Cleared on purpose: see the note in the header about
        // boot_addr + 0x7C.
        nmi_pend  <= 1'b0;
      end else if (expire) begin
        nmi_pend  <= 1'b1;
      end else if ((wr_stat && wval[B_STAT_NMI]) ||
                   (wr_ctrl && wval[B_IP])) begin
        // Write-one-to-clear, from either the status register's NMI bit
        // or GRLIB's IP bit in the control register. Both are the same
        // flag and both are offered because a GRLIB driver will reach
        // for IP and this project's own code reads the status word.
        //
        // The bit position here is B_STAT_NMI and it is a named constant
        // for a reason: it was written as a literal 1 first, against a
        // status layout that puts NMI at bit 0, and the effect was a
        // watchdog that accepted the acknowledge and ignored it. The
        // symptom was not "the write failed" -- it was a system reset
        // 3,216 clocks later, with a correct-looking NMI handler in
        // between. Nothing short of stage 2 firing would have shown it.
        nmi_pend  <= 1'b0;
      end
    end
  end

  // -------------------------------------------------------------------
  // Reads
  // -------------------------------------------------------------------
  //
  // The control register reports EN, RS and IE as 1 and ignores writes
  // to them (W1): this watchdog is always enabled, always restarts and
  // always signals. A driver that clears them and reads back gets 1, so
  // the divergence is discoverable at run time rather than only in this
  // comment.
  always @(*) begin
    rdata_o = 32'h0;
    case (1'b1)
      sel_i[0]: rdata_o = {{(32 - WIDTH){1'b0}}, counter};
      sel_i[1]: rdata_o = {{(32 - WIDTH){1'b0}}, reload};
      sel_i[2]: rdata_o = {27'h0,
                           nmi_pend,        // 4 IP
                           armed,           // 3 IE
                           1'b0,            // 2 LD, write-only
                           armed,           // 1 RS
                           armed};          // 0 EN
      // The four flag bits are placed by their named constants above,
      // so the layout the acknowledge decodes and the layout a reader
      // sees are the same declaration.
      sel_i[3]: begin
        rdata_o = 32'h0;
        rdata_o[B_STAT_NMI] = nmi_pend;
        rdata_o[B_STAT_RST] = rst_seen;
        rdata_o[B_STAT_ESC] = !wdog_no;
        rdata_o[B_STAT_DIS] = dis_q;
        rdata_o[15:8]       = rst_count;
      end
      default:  rdata_o = 32'h0;
    endcase
  end

`ifdef FORMAL
`include "soc_wdog_props.v"
`endif

endmodule
