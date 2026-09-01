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
// W7. THE KICK HAS A CADENCE AND NOT ONLY A DEADLINE (the window)
// =====================================================================
//
// Added by docs/43-core-hardening.md, from a measurement rather than a
// preference. docs/42 section 7.2 measured this block catching 91.7 %
// of the upsets that leave the core dead -- and section 8.1 found the
// class it is structurally blind to: a machine that keeps executing its
// own instructions, in order, at full speed, and pets the watchdog on
// schedule while computing nothing.
//
// W1-W5 have no purchase on that, because none of them is about
// WHETHER THE SOFTWARE SHOULD STILL BE RUNNING. A watchdog that only
// asks "has a kick arrived within T" accepts any kick, at any moment,
// including one from a runaway that happens to sweep through the kick
// site far faster than the program ever would.
//
// So the kick now has a WINDOW. After a reload the counter runs from
// `reload` down to zero; the window is CLOSED while
//
//     counter > (reload >> WINS)
//
// and a kick that arrives while it is closed is a violation, not a
// kick. WINS is a four-bit field in the new WDOGWIN register:
//
//     WINS = 0   the window is open for the whole period. This is the
//                reset default and it is EXACTLY the block docs/42
//                measured: at zero, W7 is not merely disabled, it is
//                absent from the behaviour.
//     WINS = s   the window is open for the last 2^-s of the period, so
//                the minimum permitted interval between two kicks is
//                    T_min = T * (1 - 2^-s).
//
// WHAT THE WINDOW COSTS, STATED AS THE RULE A PROGRAM HAS TO OBEY.
// Every kick must land in (T_min, T]. Writing i_min and i_max for the
// shortest and longest interval between consecutive kicks that the
// software can ever produce, the constraint is
//
//     T * (1 - 2^-s)  <  i_min      and      i_max  <  T
//
// which forces
//
//     i_max / i_min  <  1 / (1 - 2^-s)
//
// so s is, exactly, a bound on the JITTER RATIO of the software's kick
// cadence: s = 1 permits 2:1, s = 2 permits 4:3, s = 3 permits 8:7.
// That is the whole cost, and it is a cost paid by the program and not
// by the hardware. A program that kicks from several places at unequal
// spacing -- which is the ordinary way to use a watchdog, and is how
// hw/soc/tb/sw/fi_workload.c was written before this -- has an
// unbounded jitter ratio and CANNOT use any s > 0. docs/43 section 4
// measures the ratio for that program and says what it had to become.
//
// AND WHAT IT DOES NOT BUY, said here because docs/42 section 10
// expected more of it than it can deliver. A window fires on a kick
// that is too EARLY. The x23 failure of docs/42 section 8.1 is a
// corrupted loop BOUND: the loop body is untouched, so the corrupted
// machine kicks at exactly the cadence the program was written to
// produce. It is not early. W7 does not catch it and cannot, and
// docs/43 section 5 measures that rather than asserting it. W8 is the
// mechanism that does.
//
// =====================================================================
// W8. A PHASE MAY ONLY ISSUE THE KICKS IT SAID IT WOULD (the budget)
// =====================================================================
//
// The generalisation of the x23 finding is that no check on the TIMING
// of a kick can distinguish "the right loop" from "the right loop, too
// many times". Only a bound on the amount of work can, and the software
// is the only thing that knows what that bound is.
//
// So a keyed write to WDOGWIN with BUDEN set loads KICKS into an
// eight-bit down-counter and arms it. Every accepted kick decrements
// it; a kick that arrives when it is already zero is a violation, in
// exactly the sense W7's early kick is. The contract is a statement
// about PROGRESS rather than liveness: "this phase will kick at most N
// times, and if it kicks more it is not my program any more".
//
// It is disarmed at power-on reset and by every stage-2 reset, so it is
// opt-in per phase, and a program that never writes WDOGWIN gets the
// block docs/42 measured, bit for bit.
//
// WHAT A VIOLATION DOES. Both W7's and W8's violations enter W3's
// ladder at the point an expiry would: stage 1 raises the NMI, and a
// second violation or expiry with stage 1 unacknowledged is stage 2.
// They deliberately do NOT reset immediately -- a spurious early kick
// from a program whose cadence drifted deserves the same one-timeout
// warning an ordinary expiry gets. A violating kick also does NOT
// reload the counter, because a kick the block has rejected must not
// be able to postpone the deadline it was rejected for.
//
// WHAT STOPS SOFTWARE FROM SIMPLY WIDENING IT (W1's question, asked of
// W7 and W8). Three answers, in increasing order of strength:
//
//   * The write is keyed like every other (W5). WINS and the budget are
//     no more reachable by a runaway storing wild values than `reload`
//     already is, and `reload` decides the timeout itself.
//   * Neither field can DISARM the block. WINS = 0 and BUDEN = 0
//     restore the conventional watchdog of docs/40, which still
//     expires, still escalates and still resets. That is a loss of the
//     new check, not of the old one, and it is the reason W7 and W8 are
//     compatible with W1 while a writable EN bit is not.
//   * An UPSET cannot widen them either: WINS, the budget's armed flag
//     and both violation records are fields of W6's protected word.
//     They are there by W6's own criterion -- software writes them once
//     per phase, nothing else rewrites them, and their corruption
//     toward zero is silent. `kick_left` is NOT protected, for the same
//     reason `counter` is not: the block itself rewrites it, an upset
//     up costs at most 255 further kicks before the budget still bites,
//     and an upset down is a spurious ladder, which is loud. docs/43
//     measures that price rather than asserting it.
//
// AND THE FAILURE docs/40 SECTION 7.2 FOUND, WHICH THIS FEATURE CAN
// REPRODUCE. A window installed before software went wrong would
// survive the reset that going wrong caused -- W4 puts it in the
// power-on domain -- and every kick of the fresh boot would be early,
// so the SoC would reset for ever with the console never reaching its
// first character. That is precisely the brick docs/40 section 7.2
// found with `reload`, and the fix is the same line: A STAGE-2 RESET
// RESTORES WINS TO 0 AND DISARMS THE BUDGET, beside the reload being
// restored to the maximum. Whatever the last software configured, the
// next boot gets the whole budget and no cadence contract at all.
//
// =====================================================================
// WHAT THIS BLOCK DOES NOT DO
// =====================================================================
//
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
    parameter integer HARDEN = 1,
    // W7 + W8. 1 = the window and the kick budget are built, 0 = neither
    // exists and this block behaves exactly as docs/40 shipped it.
    //
    // It is here for the reason HARDEN is here: so the area cost of W7
    // and W8 can be measured against the same source file rather than
    // against a remembered number. docs/41 section 6.5 records what
    // quoting a delta against the wrong baseline cost once. Nothing in
    // the design sets it to 0.
    parameter integer WINDOW = 1,
    // Width of the W8 kick-budget down-counter, and therefore the
    // largest number of kicks one phase may declare.
    parameter integer KICK_W = 8
) (
    input  wire        clk_i,
    // POWER-ON reset. The only reset in this file, W4.
    input  wire        rst_por_ni,

    // Bootstrap pin, W1. Sampled once, when rst_por_ni releases.
    input  wire        dis_i,

    // ---- register port, decoded by soc_gptimer.v ----
    // One-hot: bit 0 counter, 1 reload, 2 control, 3 status, 4 window.
    input  wire [4:0]  sel_i,
    input  wire        we_i,
    input  wire [31:0] wdata_i,
    output reg  [31:0] rdata_o,

    // ---- escalation ----
    output wire        nmi_o,        // stage 1, to Ibex irq_nm_i
    output wire        rst_req_o,    // stage 2, drives the system reset
    output wire        wdog_no,      // stage 3, external pin, active low

    // ---- the W6 report, on a wire instead of only in a register ----
    // One pulse per cycle in which the three replicas of the protected
    // word disagree and the voter masked it. docs/41 section 10 item 3
    // left this open in exactly these words: "Nothing raises an alarm on
    // TMRERR. The mismatch is counted and sticky in a register and that
    // is all. A fault line into BUSSTAT, or a fast interrupt, is the
    // obvious next step and neither exists." This is that fault line,
    // and soc_busstat.v is what it reaches.
    //
    // It is the per-cycle EVENT and not the sticky bit, because a
    // consumer that counts a level counts one fault once per cycle
    // forever. WDOGSTAT's own TMRERR and TMRCNT are unchanged and stay
    // inside the protected word, where docs/41 section 5 put them: this
    // adds a second, unprotected observer of the same event and takes
    // nothing away from the first.
    output wire        tmr_ev_o
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
                     B_STAT_TMR = 4,              // W6, sticky
                     B_STAT_EARLY = 5,            // W7, sticky
                     B_STAT_BUDGET = 6;           // W8, sticky
  localparam integer B_STAT_TMRCNT = 16;          // W6, TMC_W bits

  // ---- WDOGWIN bit positions, W7 and W8 ----
  // Write (keyed, W5):  [3:0] WINS, [7] BUDEN, [15:8] KICKS
  // Read:               [3:0] WINS, [4] BUDARM, [15:8] the kicks left
  localparam integer B_WIN_WINS  = 0;             // 4 bits
  localparam integer B_WIN_BUDEN = 7;             // write-only, one shot
  localparam integer B_WIN_KICKS = 8;             // KICK_W bits
  localparam integer B_WIN_BUDARM = 4;            // read-only

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
  localparam integer P6_W      = P_RSTHOLD + RST_W;    // the W6 word

  // W7 and W8 add four more fields to the same word, by the same
  // criterion: software writes them once per phase, nothing else
  // rewrites them, and their corruption toward zero is silent.
  //
  //   win_s     to 0 turns the cadence check off, silently.
  //   bud_arm   to 0 turns the kick budget off, silently. This is a
  //             dis_q-class bit for W8 and it is the reason W8's armed
  //             flag is in here while its down-counter is not.
  //   early_seen, bud_seen  the two records, and they live INSIDE the
  //             protected word for the reason docs/16 section 5.8
  //             measured on this repository's own safety nets: a report
  //             beside the protection is a report an upset can erase.
  localparam integer P_WINS    = P6_W;                 // 4
  localparam integer P_EARLY   = P_WINS  + 4;          // 1
  localparam integer P_BUDARM  = P_EARLY + 1;          // 1
  localparam integer P_BUDSEEN = P_BUDARM + 1;         // 1
  localparam integer P7_W      = 7;
  localparam integer PFULL_W   = P6_W + P7_W;

  // What is actually BANKED. At WINDOW = 0 the four W7/W8 fields are
  // not stored at all, so the flip-flop count of that configuration is
  // the docs/41 design and not the docs/41 design with seven dead bits
  // in it. docs/41 section 6.5 is the reason that distinction is worth
  // a localparam: a baseline that carries part of the feature
  // understates the feature's cost.
  localparam integer PROT_W = (WINDOW != 0) ? PFULL_W : P6_W;

  // Elaboration guards, aer_fifo house style: a build that violates one
  // references a module that deliberately does not exist, so it fails
  // at elaboration with the reason in the message rather than producing
  // a silently different block.
  generate
    // W5 puts the key in the upper half word, so the whole of a kick
    // budget has to fit in wdata_i[15:8].
    if (KICK_W > 8) begin : g_kick_w_too_wide
      ERROR_soc_wdog_KICK_W_exceeds_the_keyed_value_field guard ();
    end
    // soc_tmr_bank refuses below four bits, and PROT_W is derived, so a
    // future field-list edit that narrowed it would be caught there
    // rather than here. This guard is for the other direction: POL and
    // RST_VAL are 64-bit parameters.
    if (PROT_W > 64) begin : g_prot_too_wide
      ERROR_soc_wdog_protected_word_exceeds_64_bits guard ();
    end
  endgenerate

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

  wire [PROT_W-1:0]  prot_store;      // the voted word, or the plain one
  wire               prot_mismatch;   // this cycle a replica disagrees
  reg  [PFULL_W-1:0] prot_n;          // next value, combinational

  // The fault line. At HARDEN = 0 `prot_mismatch` is the constant zero
  // that line 580 assigns, so this port is a constant too and the
  // netlist census of sw/tests/test_soc_synthesis_guards.py sees the
  // same 53 flip-flops it saw before.
  assign tmr_ev_o = prot_mismatch;

  // `prot` is the full field layout, always PFULL_W wide so that every
  // part-select below is in range whatever WINDOW is. At WINDOW = 0 the
  // top P7_W bits are constants that never enter a bank, which is what
  // makes that configuration the docs/41 design exactly rather than the
  // docs/41 design carrying seven bits of a feature it does not have.
  wire [PFULL_W-1:0] prot;
  assign prot = prot_store;          // zero-extended when WINDOW = 0

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
  wire [3:0]       win_s     = prot[P_WINS +: 4];   // W7
  wire             early_seen = prot[P_EARLY];      // W7, sticky
  wire             bud_arm    = prot[P_BUDARM];     // W8
  wire             bud_seen   = prot[P_BUDSEEN];    // W8, sticky

  generate
  if (HARDEN != 0) begin : g_prot_tmr
    wire [PROT_W-1:0] qa, qb, qc;

    // Written unconditionally from prot_n on every edge. That is the
    // scrub: this whole word is in the power-on domain, so no reset
    // ever repairs it and some of it is written once in a mission, and
    // a bank that held its value would accumulate corruption instead of
    // shedding it. See soc_tmr_bank.v difference 1.
    soc_tmr_bank #(.W(PROT_W), .RST_VAL(64'd0), .POL(POL_A), .MIX(0))
      u_prot_a (.clk_i(clk_i), .rst_ni(rst_por_ni),
                .d_i(prot_n[PROT_W-1:0]), .q_o(qa));
    soc_tmr_bank #(.W(PROT_W), .RST_VAL(64'd0), .POL(POL_B), .MIX(1))
      u_prot_b (.clk_i(clk_i), .rst_ni(rst_por_ni),
                .d_i(prot_n[PROT_W-1:0]), .q_o(qb));
    soc_tmr_bank #(.W(PROT_W), .RST_VAL(64'd0), .POL(POL_C), .MIX(1))
      u_prot_c (.clk_i(clk_i), .rst_ni(rst_por_ni),
                .d_i(prot_n[PROT_W-1:0]), .q_o(qc));

    // hw/rtl/tmr_voter.v, read in place and not copied. It is a
    // standalone file with no includes, proven exhaustively in
    // formal/tmr_voter.sby and checked against an independent Python
    // majority model in hw/tb/test_tmr_voter.py. Nothing in hw/rtl is
    // modified by this instantiation; docs/34's freeze is untouched.
    tmr_voter #(.WIDTH(PROT_W)) u_prot_vote (
        .in_a     (qa),
        .in_b     (qb),
        .in_c     (qc),
        .out      (prot_store),
        .mismatch (prot_mismatch)
    );
  end else begin : g_prot_plain
    // HARDEN = 0: the block as docs/40 shipped it. Measurement only.
    reg [PROT_W-1:0] plain;
    always @(posedge clk_i or negedge rst_por_ni) begin
      if (!rst_por_ni) plain <= {PROT_W{1'b0}};
      else             plain <= prot_n[PROT_W-1:0];
    end
    assign prot_store    = plain;
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
  // W7 and W8's register. Keyed like the rest, and inert at WINDOW = 0
  // so that configuration has no path from the bus into state it does
  // not have.
  wire wr_win  = sel_i[4] && keyed && (WINDOW != 0);

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
  //   win_s / bud_arm      the W7 and W8 contract
  //   early_seen / bud_seen  the W7 and W8 records
  //
  // The FOUR below are deliberately NOT protected, and the argument is
  // W6's second list: each of them is rewritten by the block itself, so
  // an upset in it is bounded in time rather than permanent.
  reg [WIDTH-1:0] reload;
  reg [WIDTH-1:0] counter;
  reg [PRE_W-1:0] pre;

  // W8's down-counter, and it is deliberately NOT in the protected word.
  // The criterion is W6's and it is the one `counter` already passes:
  // the block itself rewrites it every kick, so nothing accumulates; an
  // upset upward buys the runaway at most 2^KICK_W - 1 further kicks
  // before the budget bites anyway, and an upset downward is a spurious
  // escalation, which is loud and which the protected record captures
  // correctly while it happens. Its ARMED flag is a different question
  // and is protected: that bit is silent in the direction that matters.
  reg [KICK_W-1:0] kick_left;

  wire in_reset = (rst_hold != 0);
  wire tick     = (PRESCALE <= 1) || (pre == 0);
  wire expire   = armed && !in_reset && tick && (counter == 0);

  // ---- a kick ----
  //
  // A keyed control write with LD set reloads the counter. It does NOT
  // acknowledge a pending NMI: "I am alive" and "I have seen and handled
  // the warning" are different statements and collapsing them would let
  // a periodic kicker that never looks at the status register mask a
  // stage-1 event forever.
  wire kick_req = wr_ctrl && wval[B_LD];

  // -------------------------------------------------------------------
  // W7: is the window open?
  // -------------------------------------------------------------------
  //
  // The counter runs down from `reload`, so the elapsed part of the
  // period is (reload - counter) and the remaining part is `counter`.
  // The window is open for the last 2^-win_s of the period:
  //
  //     open  <=>  win_s == 0  ||  counter <= (reload >> win_s)
  //
  // win_s = 0 makes the right-hand side `counter <= reload`, which is
  // true for every reachable counter value -- so the zero case is not a
  // special case in the logic, only in the reading. It is written out
  // as one anyway, because the shift is a barrel shifter and gating it
  // is what makes WINDOW = 0 and win_s = 0 cost the same nothing.
  //
  // The comparison is against `reload` and not against a second
  // programmed number on purpose: a window expressed as a FRACTION of
  // the period cannot be made inconsistent with the period. A separate
  // absolute open-point register could be set above the reload, which
  // would close the window for ever and stop every kick -- a way to
  // brick the part with one store, which W1 exists to prevent.
  wire [WIDTH-1:0] win_open_at = reload >> win_s;
  wire win_open = (WINDOW == 0) || (win_s == 4'd0) ||
                  (counter <= win_open_at);

  // A kick that arrives while the window is closed. Gated by `armed`
  // and by `!in_reset` for the same reason `expire` is: a block held
  // off by its bootstrap pin does nothing, and the kicks a core issues
  // while it is being reset are not the program's.
  wire early_kick = (WINDOW != 0) && kick_req && armed && !in_reset &&
                    !win_open;

  // -------------------------------------------------------------------
  // W8: has this phase run out of kicks?
  // -------------------------------------------------------------------
  wire budget_out = (WINDOW != 0) && kick_req && armed && !in_reset &&
                    bud_arm && (kick_left == {KICK_W{1'b0}});

  // A violation is either of the two, and it enters W3's ladder exactly
  // where an expiry does. A violating kick is NOT a kick: it does not
  // reload the counter, because a kick the block has rejected must not
  // postpone the deadline it was rejected for.
  wire violate = early_kick || budget_out;
  wire kick    = kick_req && !violate;

  // Stage 2 is the SECOND fault with stage 1 still unacknowledged, and
  // `fault` rather than `expire` is what changed here: an early kick or
  // an exhausted budget counts as one.
  wire fault    = expire || violate;
  wire stage2   = fault && nmi_pend;

  assign nmi_o     = nmi_pend;
  assign rst_req_o = in_reset;
  assign wdog_no   = !(rst_count >= ESC_AT);

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

    // W7 and W8's configuration. Placed BEFORE the escalation so that
    // the stage-2 restore below overrides it: if a write and a reset
    // ever landed in the same cycle, the thing that stops the part
    // bricking has to be the one that wins.
    if (wr_win) begin
      prot_n[P_WINS +: 4] = wval[B_WIN_WINS +: 4];
      if (wval[B_WIN_BUDEN]) prot_n[P_BUDARM] = 1'b1;
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
      // docs/40 section 7.2's line, extended to W7 and W8 for its own
      // reason. A window or a budget installed before software went
      // wrong survives the reset that going wrong caused -- everything
      // here is in the power-on domain by W4 -- so the fresh boot would
      // trip the same contract on its first kick and reset again, for
      // ever, with the console never reaching its first character.
      // Whatever the last software configured, the next boot gets the
      // whole budget and no cadence contract.
      prot_n[P_WINS +: 4] = 4'd0;
      prot_n[P_BUDARM]    = 1'b0;
    end else if (fault) begin
      prot_n[P_NMI] = 1'b1;
    end else if (ack) begin
      prot_n[P_NMI] = 1'b0;
    end

    // W7 and W8's records. Sticky and not clearable, for the reason
    // WDOGRST and RSTCNT are not: a record software can erase is a
    // record an upset can erase.
    if (early_kick) prot_n[P_EARLY]   = 1'b1;
    if (budget_out) prot_n[P_BUDSEEN] = 1'b1;

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
      kick_left <= {KICK_W{1'b0}};
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

      // ---- W8's kick budget ----
      //
      // Loaded by a keyed WDOGWIN write with BUDEN, decremented by
      // every ACCEPTED kick, and saturating at zero -- the zero itself
      // is the violation, and the counter must stay there so that every
      // subsequent kick of a runaway is a violation too rather than
      // only the first one after a wrap.
      if (WINDOW != 0) begin
        if (wr_win && wval[B_WIN_BUDEN])
          kick_left <= wval[B_WIN_KICKS +: KICK_W];
        else if (kick && bud_arm && (kick_left != {KICK_W{1'b0}}))
          kick_left <= kick_left - 1'b1;
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
        rdata_o[B_STAT_EARLY]  = early_seen;    // W7
        rdata_o[B_STAT_BUDGET] = bud_seen;      // W8
        rdata_o[15:8]       = rst_count;
        rdata_o[B_STAT_TMRCNT +: TMC_W] = tmr_count;
      end
      // WDOGWIN, W7 and W8. The configuration reads back so that
      // software can discover it did not take -- the same reason W1
      // makes EN read 1 after a write of 0 rather than silently
      // ignoring it -- and `kick_left` reads back so that a phase can
      // see how much of its declared budget it has spent.
      sel_i[4]: begin
        rdata_o = 32'h0;
        rdata_o[B_WIN_WINS +: 4]      = win_s;
        rdata_o[B_WIN_BUDARM]         = bud_arm;
        rdata_o[B_WIN_KICKS +: KICK_W] = kick_left;
      end
      default:  rdata_o = 32'h0;
    endcase
  end

`ifdef FORMAL
`include "soc_wdog_props.v"
`endif

endmodule
