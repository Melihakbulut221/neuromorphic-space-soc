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
// W6. ITS OWN STATE IS PROTECTED WHERE CORRUPTION IS PERMANENT OR SILENT
// =====================================================================
//
// Added by docs/41-watchdog-hardening.md. docs/40 section 10 item 2
// recorded the gap in its own words -- "the block whose job is to catch
// upsets is itself unprotected" -- and the reason it is worse than an
// ordinary gap is that a watchdog an upset can silently disarm is worse
// than no watchdog, because the system believes it has one.
//
// THE RANKING. Not everything here deserves TMR, and the criterion is
// not "how important does the register sound". It is PERSISTENCE times
// SILENCE: what rewrites this register, and does its corruption
// announce itself?
//
//   Protected, because nothing rewrites it and its corruption is
//   silent. All of it lives in the power-on domain, so there is no
//   reset in the mission that restores it and no software write that
//   sets it:
//     dis_q     an upset to 1 sets armed low and the block STOPS. No
//               expiry, no NMI, no reset, for ever, with EN reading 0
//               and WDOGSTAT.DISABLED reading 1 on a board that never
//               asserted the pin. This is the single worst bit in the
//               design and it is the reason this section exists.
//     dis_seen  an upset to 0 re-opens the sampling window W1 closes,
//               turning a bootstrap pin back into a live one.
//     nmi_pend  an upset to 0 means stage 1 never becomes stage 2: the
//               watchdog warns and never acts, which is exactly the
//               failure W5's key check exists to stop software doing
//               and which an upset would do in hardware. An upset to 1
//               resets the system a full timeout early.
//     rst_seen  the record W4 exists for. An upset to 0 leaves the
//               operator with a machine that reboots for no
//               discoverable reason.
//     rst_count both a record and a policy: an upset up asserts the
//               external pin on a healthy part, an upset down means the
//               "resetting has not worked" signal never arrives.
//     rst_hold  the only state in this file that can assert a system
//               reset on its own; an upset down truncates the reset
//               pulse the rest of the SoC is being held by.
//
//   Deliberately NOT protected, because the block already rewrites it
//   and the worst case is bounded and loud:
//     counter   an upset moves the deadline by at most one full timeout
//               and is gone at the next expiry or kick, both of which
//               reload it. Nothing accumulates.
//     reload    an upset survives -- it is in the power-on domain too --
//               but it cannot survive an escalation, because a stage-2
//               reset restores it to the maximum (docs/40 section 7.2,
//               which found that the hard way). So the worst case is at
//               most one spurious ladder, and the protected state
//               records it correctly while it happens.
//     pre       an upset moves the tick by at most PRESCALE-1 clocks
//               out of 2^WIDTH * PRESCALE.
//   That list is a decision, not an omission, and
//   hw/soc/tb/cocotb/test_soc_wdog_fi.py injects into all three of them
//   so the price is measured rather than asserted.
//
// THE CONSTRUCTION. The protected bits are CONCATENATED into one word
// of PROT_W bits and that word is replicated three times under
// hw/rtl/tmr_voter.v. The bundling is not tidiness. Most of what is
// protected here is one-bit flags, and three replicas cannot be held
// apart over one bit -- there are exactly two storage functions, x and
// ~x, so a third replica is bit-for-bit identical to one of the others
// and yosys merges it away (hw/rtl/pilot_top.v section 8.2, generalised
// in docs/30 section 3.3: over W bits the affine transforms give
// 2 * (2^W - 1) coordinate functions, so three bits is the first width
// at which a third replica has functions left to take). Bundling buys
// the width. soc_tmr_bank.v carries the transform and the argument.
//
// THE POWER-ON DOMAIN CUTS BOTH WAYS AND THE BANK IS WRITTEN EVERY
// CYCLE BECAUSE OF IT. docs/40 section 7.2's finding -- state outside
// the reset domain makes the record survive AND makes stale
// configuration survive -- applies to the protection as well: the
// replicas are not reset either. A bank that only wrote when the value
// changed would repair a corrupted replica only at the next write, and
// `rst_seen` and the bootstrap latch are written once in a mission. The
// bank is therefore written unconditionally from the VOTED word on
// every edge, which makes the voter a continuous scrubber: the window
// in which a second upset in a different replica is uncorrectable is
// one clock cycle rather than the rest of the mission.
//
// WHAT THIS DOES NOT BUY, stated here so it is not read as more:
//   * The unprotected registers above are still unprotected.
//   * Two upsets in two different replicas in the same cycle on the
//     same bit are not corrected. Nothing about three replicas claims
//     they are.
//   * The mismatch is COUNTED and STICKY in WDOGSTAT and nothing raises
//     an interrupt or a pin on it. Reading it is software's job, and
//     the software may be the thing that has failed -- docs/16 section
//     7.6, "DETECTED depends on someone looking".
//   * HARDEN = 0 removes all of it. That parameter exists so the area
//     cost can be measured like for like against the same file, and
//     because the synthesis guard needs a mutation whose flip-flop
//     count differs. Nothing in the design instantiates it, which
//     sw/tests/test_soc_synthesis_guards.py checks textually.
//
// =====================================================================
// WHAT THIS BLOCK DOES NOT DO
// =====================================================================
//
//   * No windowed mode. A kick that arrives too EARLY is accepted. A
//     windowed watchdog rejects those and so catches a fast runaway loop
//     that happens to include the kick; this one does not, and a runaway
//     that keeps kicking is invisible to it.
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
    parameter [15:0] KEY = 16'hA51F,
    // W6. 1 = the protected word is three replicas under a voter,
    // 0 = one plain register bank and no protection at all.
    //
    // This exists so the area cost of W6 can be measured against the
    // same source file rather than against a remembered number, and so
    // that sw/tests/test_soc_synthesis_guards.py has a mutation whose
    // flip-flop count differs. Nothing in the design sets it to 0 and
    // that test checks textually that nothing does.
    parameter integer HARDEN = 1
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
  localparam integer TMC_W = 4;   // saturating TMR mismatch counter (W6)

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
                     B_STAT_ESC = 2, B_STAT_DIS = 3,
                     B_STAT_TMR = 4;              // W6, sticky
  localparam integer B_STAT_TMRCNT = 16;          // W6, TMC_W bits

  // -------------------------------------------------------------------
  // The protected word (W6)
  // -------------------------------------------------------------------
  //
  // Every bit whose corruption is permanent or silent, concatenated
  // into one word so that the MIX transform has a width to work in --
  // three replicas cannot be held apart over one bit. The field offsets
  // are named constants used by the packing, the unpacking and the
  // register reads alike, because docs/40 section 7.4 records what a
  // literal bit position cost this file once.
  localparam integer P_DISQ    = 0;                    // 1
  localparam integer P_DISSEEN = 1;                    // 1
  localparam integer P_NMI     = 2;                    // 1
  localparam integer P_RSTSEEN = 3;                    // 1
  localparam integer P_TMRERR  = 4;                    // 1
  localparam integer P_TMRCNT  = 5;                    // TMC_W
  localparam integer P_RSTCNT  = P_TMRCNT + TMC_W;     // CNT_W
  localparam integer P_RSTHOLD = P_RSTCNT + CNT_W;     // RST_W
  localparam integer PROT_W    = P_RSTHOLD + RST_W;

  // Per-replica storage transform. A is the true image; B and C are
  // mixed, so every stored bit of either is an XOR of two or three
  // distinct word bits and can equal neither x_i nor ~x_i for any i --
  // which is what makes them provably non-collidable with A rather than
  // measured to be. B and C are separated from each other by
  // POL_B = ~POL_C on every bit.
  //
  // Neither mask is uniform, and that is deliberate: docs/33 measured
  // that a bank whose reset image is all ones is one dfflibmap has to
  // build by inversion, and abc then folds the inversion against the
  // bank's own correction. A mixed mask leaves a mixed reset image.
  // Whether that survives technology mapping is measured in docs/41
  // section 6 and is not claimed here.
  localparam [63:0] POL_A = 64'h0000000000000000;
  localparam [63:0] POL_B = 64'h5555555555555555;
  localparam [63:0] POL_C = 64'hAAAAAAAAAAAAAAAA;

  wire [PROT_W-1:0] prot;            // the voted word, or the plain one
  wire              prot_mismatch;   // this cycle a replica disagrees
  reg  [PROT_W-1:0] prot_n;          // next value, combinational

  // Named views. Everything below this line reads these and never the
  // storage, so this file's register reads and the invariants in
  // hw/soc/formal/soc_wdog_props.v are written against the same names
  // they were written against before W6 existed.
  wire             dis_q     = prot[P_DISQ];
  wire             dis_seen  = prot[P_DISSEEN];
  wire             nmi_pend  = prot[P_NMI];
  wire             rst_seen  = prot[P_RSTSEEN];
  wire             tmr_err   = prot[P_TMRERR];
  wire [TMC_W-1:0] tmr_count = prot[P_TMRCNT  +: TMC_W];
  wire [CNT_W-1:0] rst_count = prot[P_RSTCNT  +: CNT_W];
  wire [RST_W-1:0] rst_hold  = prot[P_RSTHOLD +: RST_W];

  generate
  if (HARDEN != 0) begin : g_prot_tmr
    wire [PROT_W-1:0] qa, qb, qc;

    // Written unconditionally from prot_n on every edge. That is the
    // scrub: this whole word is in the power-on domain, so no reset
    // ever repairs it and some of it is written once in a mission, and
    // a bank that held its value would accumulate corruption instead of
    // shedding it. See soc_tmr_bank.v difference 1.
    soc_tmr_bank #(.W(PROT_W), .RST_VAL(64'd0), .POL(POL_A), .MIX(0))
      u_prot_a (.clk_i(clk_i), .rst_ni(rst_por_ni), .d_i(prot_n), .q_o(qa));
    soc_tmr_bank #(.W(PROT_W), .RST_VAL(64'd0), .POL(POL_B), .MIX(1))
      u_prot_b (.clk_i(clk_i), .rst_ni(rst_por_ni), .d_i(prot_n), .q_o(qb));
    soc_tmr_bank #(.W(PROT_W), .RST_VAL(64'd0), .POL(POL_C), .MIX(1))
      u_prot_c (.clk_i(clk_i), .rst_ni(rst_por_ni), .d_i(prot_n), .q_o(qc));

    // hw/rtl/tmr_voter.v, read in place and not copied. It is a
    // standalone file with no includes, proven exhaustively in
    // formal/tmr_voter.sby and checked against an independent Python
    // majority model in hw/tb/test_tmr_voter.py. Nothing in hw/rtl is
    // modified by this instantiation; docs/34's freeze is untouched.
    tmr_voter #(.WIDTH(PROT_W)) u_prot_vote (
        .in_a     (qa),
        .in_b     (qb),
        .in_c     (qc),
        .out      (prot),
        .mismatch (prot_mismatch)
    );
  end else begin : g_prot_plain
    // HARDEN = 0: the block as docs/40 shipped it. Measurement only.
    reg [PROT_W-1:0] plain;
    always @(posedge clk_i or negedge rst_por_ni) begin
      if (!rst_por_ni) plain <= {PROT_W{1'b0}};
      else             plain <= prot_n;
    end
    assign prot          = plain;
    assign prot_mismatch = 1'b0;
  end
  endgenerate

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
  //
  // The rest of the state is the protected word above:
  //   nmi_pend   stage 1 fired, not acknowledged
  //   rst_seen   a watchdog reset happened since POR
  //   rst_count  saturating
  //   rst_hold   stage-2 stretch
  //   dis_q / dis_seen  the bootstrap latch
  //   tmr_err / tmr_count  the W6 report
  //
  // The three below are deliberately NOT protected, and the argument is
  // W6's second list: each of them is rewritten by the block itself, so
  // an upset in it is bounded in time rather than permanent.
  reg [WIDTH-1:0] reload;
  reg [WIDTH-1:0] counter;
  reg [PRE_W-1:0] pre;

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

  // A write-one-to-clear of the pending stage 1, from either the status
  // register's NMI bit or GRLIB's IP bit in the control register. Both
  // are the same flag and both are offered because a GRLIB driver will
  // reach for IP and this project's own code reads the status word.
  //
  // The bit position here is B_STAT_NMI and it is a named constant for a
  // reason: it was written as a literal 1 first, against a status layout
  // that puts NMI at bit 0, and the effect was a watchdog that accepted
  // the acknowledge and ignored it. The symptom was not "the write
  // failed" -- it was a system reset 3,216 clocks later, with a
  // correct-looking NMI handler in between. Nothing short of stage 2
  // firing would have shown it.
  wire ack = (wr_stat && wval[B_STAT_NMI]) || (wr_ctrl && wval[B_IP]);

  // -------------------------------------------------------------------
  // Next value of the protected word (W6)
  // -------------------------------------------------------------------
  //
  // Written as one combinational function of the VOTED word, so that
  // both the hardened and the HARDEN = 0 configurations run identical
  // policy and the hardening cannot change behaviour by accident. The
  // ordering below reproduces the last-assignment-wins semantics the
  // sequential version had: a stage-2 reset overrides the stretch
  // decrement, and the acknowledge is only reached when neither stage
  // fired this cycle.
  always @(*) begin
    prot_n = prot;

    // The bootstrap pin, sampled once, then held for ever (W1).
    if (!dis_seen) begin
      prot_n[P_DISQ]    = dis_i;
      prot_n[P_DISSEEN] = 1'b1;
    end

    // The reset stretch, and then the escalation which overrides it.
    if (in_reset) prot_n[P_RSTHOLD +: RST_W] = rst_hold - 1'b1;

    if (stage2) begin
      prot_n[P_RSTHOLD +: RST_W] = RST_TOP;
      prot_n[P_RSTSEEN]          = 1'b1;
      if (~&rst_count) prot_n[P_RSTCNT +: CNT_W] = rst_count + 1'b1;
      // Cleared on purpose: see the note in the header about
      // boot_addr + 0x7C.
      prot_n[P_NMI]              = 1'b0;
    end else if (expire) begin
      prot_n[P_NMI] = 1'b1;
    end else if (ack) begin
      prot_n[P_NMI] = 1'b0;
    end

    // The W6 report, and it lives INSIDE the protected word on purpose.
    // docs/16 section 5.8 measured the other arrangement on this
    // repository's own safety nets and found the report was the single
    // point of failure -- an upset could erase the announcement of the
    // very event it caused. Here the write-back that repairs the
    // replica and the write that records the repair are the same write
    // on the same edge, so there is no cycle in which the report exists
    // as separate, unprotected state. An upset in the report bit itself
    // is both corrected and counted, because it is a disagreement like
    // any other.
    prot_n[P_TMRERR] = tmr_err | prot_mismatch;
    if (prot_mismatch && ~&tmr_count)
      prot_n[P_TMRCNT +: TMC_W] = tmr_count + 1'b1;
  end

  // -------------------------------------------------------------------
  // The unprotected state (W6's second list)
  // -------------------------------------------------------------------
  always @(posedge clk_i or negedge rst_por_ni) begin
    if (!rst_por_ni) begin
      // Armed, at the longest timeout the block allows. Anything shorter
      // as a reset default risks a board whose boot is slower than the
      // watchdog resetting forever with no way in -- docs/40 section 5.
      reload    <= {WIDTH{1'b1}};
      counter   <= {WIDTH{1'b1}};
      pre       <= 0;
    end else begin
      // ---- prescaler ----
      if (PRESCALE > 1) begin
        if (pre == 0) pre <= PRE_TOP;
        else          pre <= pre - 1'b1;
      end

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
      // The flag bits are placed by their named constants above, so the
      // layout the acknowledge decodes and the layout a reader sees are
      // the same declaration.
      //
      // TMRERR and TMRCNT are not clearable, for the same reason
      // WDOGRST and RSTCNT are not: they are the fault record, and a
      // record software can erase is a record an upset can erase.
      sel_i[3]: begin
        rdata_o = 32'h0;
        rdata_o[B_STAT_NMI] = nmi_pend;
        rdata_o[B_STAT_RST] = rst_seen;
        rdata_o[B_STAT_ESC] = !wdog_no;
        rdata_o[B_STAT_DIS] = dis_q;
        rdata_o[B_STAT_TMR] = tmr_err;
        rdata_o[15:8]       = rst_count;
        rdata_o[B_STAT_TMRCNT +: TMC_W] = tmr_count;
      end
      default:  rdata_o = 32'h0;
    endcase
  end

`ifdef FORMAL
`include "soc_wdog_props.v"
`endif

endmodule
