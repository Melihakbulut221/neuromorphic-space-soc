// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// BOOTREG: the bootstrap pins as they were sampled, the boot counter no
// software can write, and two words that survive the reset they
// describe.
//
// =====================================================================
// WHY THIS BLOCK EXISTS
// =====================================================================
//
// docs/68 builds the boot flow: a loader in the ROM copies a
// checksummed image out of the QSPI flash docs/66 built, into the
// SECDED-protected RAM docs/67 built, and jumps to it. Three of that
// flow's four questions need state that is NOT in either of those
// blocks, and the frozen map has had the slot ready for them since
// docs/39:
//
//     0xFF917000  BOOTREG  reserved
//     "Bootstrap pin readback and boot report register, GRGPREG-like"
//
// GR716B's boot flow (docs/08 section 2.4) is the shape: bootstrap pins
// select the boot source and can bypass the ROM, and a general-purpose
// register block carries a boot report across the reset. GR740's
// GRGPREG is the register block this is named after.
//
// =====================================================================
// THE ONE FIELD WITH AUTHORITY IS THE ONE SOFTWARE CANNOT WRITE
// =====================================================================
//
// That sentence is the whole design rule of this block, and it is what
// keeps it out of docs/40 section 7.2's brick loop.
//
// docs/40's watchdog put its record in the POWER-ON domain (W4) so that
// a stage-2 reset could not erase the evidence of what caused it -- and
// then found, by running it, that the RELOAD register was in the same
// domain, so a short timeout installed by software that had already
// gone wrong survived the reset that going wrong caused, and the SoC
// reset itself for ever with the console never reaching its first
// character. Putting state outside the reset domain is what makes a
// record survive; it is also what makes a stale configuration survive.
//
// A boot report is exactly that shape again: it must survive the reset
// it describes, and the boot flow that reads it must not be able to
// brick itself on what it finds. The rule here is therefore sharper
// than "restore the default on reset":
//
//   * BOOTCNT is maintained BY HARDWARE, saturating, cleared only by
//     power-on reset, and NO APB WRITE CHANGES IT. It is the only field
//     of this block that changes what the loader does -- it is what
//     stops the loader retrying -- and it is the only field software
//     cannot forge. That is soc_wdog.v W1's independence argument
//     ("a watchdog its own software can switch off is not a backstop
//     against software that has stopped behaving") applied to a boot
//     counter, and it is why this block needs no write key: the
//     watchdog keyed its writes because its ACKNOWLEDGE had authority
//     (soc_wdog.v W5), and nothing writable here has any.
//
//   * BRPT and EPOCH are EVIDENCE, not authority. Software writes them,
//     they survive a stage-2 reset, and nothing in this block or in the
//     boot flow branches on their contents. A runaway core can fill
//     them with rubbish and the worst outcome is a wrong diagnosis in
//     telemetry; it cannot lengthen a budget, shorten a timeout or
//     persuade the next boot to try again.
//
//   * NOTHING HERE CAN EXTEND A DEADLINE. This block has no output that
//     reaches the watchdog, the memories or the fabric. Its only ports
//     out are the APB read data. The failure docs/40 section 7.2 found
//     was a persistent register that could SHORTEN the next boot's
//     budget; a persistent register that cannot reach the budget at all
//     is the structural version of the same fix.
//
// =====================================================================
// BOOTCNT: WHY IT IS NOT WDOGSTAT.RSTCNT
// =====================================================================
//
// soc_wdog.v already carries RSTCNT, saturating and power-on-only, and
// on THIS SoC every non-power-on reset is a watchdog stage-2 reset, so
// today the two counters are the same number. They are two counters
// anyway, and the reason is what each one counts:
//
//   RSTCNT   stage-2 assertions BY THE WATCHDOG. It is the watchdog's
//            own escalation input and it is inside the watchdog's
//            key-protected, triple-redundant register bank.
//   BOOTCNT  RELEASES OF THE SYSTEM RESET, whatever asserted it, with
//            the power-on boot counting zero.
//
// The boot flow escalates on the number of times it has BOOTED, not on
// the number of times a particular block reset it: a boot loop driven
// by something the watchdog did not cause -- an external reset pin, a
// brownout, a debug reset, none of which this SoC has yet -- must still
// terminate. Counting the boot is the general statement and counting
// the watchdog is the special case; the loader reads both and reports
// the pair, so that on this SoC, where they must agree, a disagreement
// is a finding rather than an invisible divergence.
//
// =====================================================================
// THE STRAPS
// =====================================================================
//
// Sampled ONCE, three clocks after power-on reset releases, through two
// synchroniser flops, and ignored for ever after. soc_wdog.v W1 states
// the reason for its own bootstrap pin and it is the same one: a pin
// that could change a boot decision at any moment would be a hardware
// back door into the decision. BSTRAP.VALID says the sample has been
// taken, so a read taken in the first three clocks -- which no software
// can do, because the core is fetching its first instruction -- is
// distinguishable from a strap field of zero.
//
//   bit 0   SRC0  \  boot source: 0 = flash on chip select 0,
//   bit 1   SRC1  /  1 = chip select 1, 2 and 3 reserved
//   bit 2   NOBOOT   do not load an image; stay in the ROM. This is
//                    GR716B's "direct boot" bootstrap in the only form
//                    this part can offer it, and it is the board's way
//                    of getting a part with a bad flash to a console.
//   bit 3   spare
//
// The names are a SOFTWARE CONVENTION -- hw/soc/tb/sw/soc_boot.h -- and
// not a hardware behaviour. This block samples the pins and reports
// them; the loader is what acts on them. That split is deliberate: a
// strap that gated something in hardware would be a second, silent
// control path into a flow whose whole argument is that its control
// path is one counter.
//
// WDOGDIS is the watchdog's OWN bootstrap pin, sampled here a second
// time for readback. It is reported and not consumed: soc_wdog.v
// samples the same wire for itself and WDOGSTAT.DISABLED is the
// authoritative report of what the watchdog did with it. Two samples of
// one static pin that must agree is a cheap cross-check and it is what
// makes "the map promises bootstrap pin readback" true for the one
// bootstrap pin this SoC had before this document.
//
// =====================================================================
// EPOCH
// =====================================================================
//
// docs/58 section 5.2 planned the recovery from an uncorrectable in
// mtime -- "it re-epochs" -- and said the correlation with absolute
// time "has to come from outside". mtime is in the SYSTEM reset domain
// and a stage-2 reset zeroes it, so every boot starts a new epoch
// whether anything asked for one or not. EPOCH is where the epoch's
// IDENTITY lives: a word in the power-on domain that the loader
// increments once per boot before it hands over, so that two readings
// of mtime taken in different epochs are distinguishable as such.
//
// It is deliberately NOT a copy of mtime and not a second time base.
// Nothing here counts. Reconstructing the elapsed time across a reset
// needs a counter in the power-on domain that this part does not have,
// and docs/58 section 5.2's `mcycle` reconstruction is still [planned];
// what this register removes is the weaker failure of not being able to
// tell that a re-epoch happened at all.
//
// =====================================================================
// BUS
// =====================================================================
//
// AMBA 3 APB slave, the conventions soc_uart.v, soc_busstat.v and
// soc_scrub.v use: PREADY tied high, PSLVERR tied low, an offset inside
// the slot that names no register reads zero and a write to it does
// nothing.
//
// =====================================================================
// B1. THE DECISION STATE IS TRIPLED AND THE EVIDENCE IS NOT
// =====================================================================
//
// Added by docs/69-boot-hardening.md. Everything above this section is
// the block as docs/68 shipped it and is unchanged in behaviour; B1 is
// the first numbered requirement this file has, and it is numbered so
// that a later edit that drops it fails a property whose name says what
// was lost.
//
// THE PROBLEM. docs/68 section 16 item 1: this block was 92 flip-flops
// with no protection at all, and its own header had just finished
// arguing that ONE of its fields decides whether the part tries to boot
// again. An upset in that field is not a wrong number in telemetry:
//
//   BOOTCNT up    the loader reads BSTAT.OVER on a part that has booted
//                 once, does not touch the flash, reports GIVEUP and
//                 takes the give-up exit -- and because the counter is
//                 in the power-on domain and saturating, IT STAYS THERE.
//                 The part refuses to boot for the rest of the power
//                 cycle. A mission that stops retrying after one
//                 spurious increment is lost.
//   BOOTCNT down  the ladder never terminates. The loader retries for
//                 ever, and the watchdog CANNOT break the loop, because
//                 the loader kicks it -- docs/68 section 5.4 built that
//                 kick deliberately, and it is the thing that makes a
//                 stuck-low counter an unbounded burn instead of a
//                 bounded one.
//
// Those are different failures with different costs and BOTH of them
// come from eight flip-flops.
//
// THE RANKING, docs/41 section 3.1's criterion -- persistence times
// silence -- applied to this block's own state. Two questions decide it:
// what rewrites this register, and does its corruption announce itself.
//
//   PROTECTED, 18 bits. Everything that is written ONCE per power cycle
//   or maintained by hardware, or whose corruption reaches something
//   that is, and decides a boot:
//     cnt_q    8   the boot counter. Above.
//     armed_q  1   to 0 the next release re-arms instead of counting, so
//                  the counter never advances and the ladder never ends;
//                  to 1 before the power-on release the power-on boot is
//                  counted and every limit is off by one. This is the
//                  `cnt_por_zero` mutation, done by an upset.
//     valid_q  1   to 0 REOPENS THE SAMPLING WINDOW. The straps are
//                  re-sampled from live pins at an arbitrary later
//                  moment, which is `strap_live` done by an upset and is
//                  soc_wdog.v W1's hardware back door into the boot
//                  decision.
//     strap_q  4   sampled once, never rewritten. Bit 2 is NOBOOT: an
//                  upset that sets it makes every later boot refuse the
//                  flash. Bits 1:0 are SRC: an upset moves the boot to a
//                  chip select with nothing on it, which is NOFLASH on
//                  every attempt. Either is a part that does not boot
//                  again this power cycle.
//     wdis_q   1   reported, not consumed -- but it is the cross-check
//                  against WDOGSTAT.DISABLED, and a cross-check that
//                  disagrees for its own reason is worse than none. It
//                  is one bit and the bundle is already paid for.
//     dly      2   only live before VALID, and dead after -- but if an
//                  upset clears valid_q it is live again, so it is
//                  protected with the flag that makes it dead.
//     sys_q    1   THE ONE THE CAMPAIGN MOVED. It is rewritten from
//                  rst_ni every clock and the first version of this
//                  ranking left it unprotected for exactly that reason;
//                  hw/soc/tb/cocotb/test_soc_boot_fi.py then returned
//                  every draw into it as a part past its attempt limit,
//                  because an upset there manufactures a release edge
//                  and the counter it moves never comes down. A
//                  self-correcting register with a permanent
//                  consequence belongs on this list. See the localparam.
//
//   NOT PROTECTED, 74 flip-flops, which is FOUR FIFTHS OF THE BLOCK and
//   is the more interesting half of the decision:
//     brpt_q  32   EVIDENCE, NOT AUTHORITY, and the header above says so
//     epoch_q 32   in as many words: nothing in this block and nothing
//                  in the boot flow branches on their contents. An upset
//                  is a wrong diagnosis in ONE boot's telemetry, and the
//                  next boot overwrites it. 64 flip-flops, 69.6 % of the
//                  block, and tripling them would nearly triple the
//                  block to protect the one thing here that cannot cause
//                  a failure. That is docs/52's evq_data finding and
//                  docs/56's nine-of-140: the flip-flop count and the
//                  consequence are not the same distribution.
//     sync0/1  8   the strap synchronisers, rewritten from the pins
//     wsync0/1 2   every clock. An upset is gone in one or two clocks --
//                  EXCEPT in the two-clock window where the sample is
//                  taken, where it is latched into strap_q for the power
//                  cycle. That window is two clocks of a mission and it
//                  is the honest residual: the exposure is bounded and
//                  the effect, if it lands, is not. It is NOT the same
//                  shape as sys_q above, and the difference is the whole
//                  reason one of them is protected and the other is not:
//                  sys_q is exposed for the WHOLE mission and these are
//                  exposed for two clocks of it. docs/69 section 8.5
//                  measures the exposure and section 8.6 demonstrates
//                  the consequence with a directed injection, because a
//                  uniform campaign draws into a 2-clock window about
//                  twice in a hundred.
//
// THE REPLICATION BOUND. Five of the six protected fields are one or two
// bits wide and none of them can be tripled on its own: over W bits the
// affine storage transforms give 2*(2^W - 1) coordinate functions and
// three replicas need six, so three bits is the first width at which a
// third replica has functions left to take (hw/rtl/pilot_top.v section
// 8.2, generalised in docs/30 section 3.3). A naive replication of
// valid_q would produce ONE flip-flop and a voter voting it against
// itself, and every test and every proof in this repository would still
// pass. So the bits are CONCATENATED into one word and the WORD is
// replicated -- docs/41 section 4.2's answer, and soc_tmr_bank.v carries
// a compile-time guard refusing a bundle below four bits.
//
// THE REPORT IS INSIDE THE PROTECTED WORD, not beside it. docs/16
// section 5.8 measured this repository's own safety-net report and found
// it was the single point of failure: an upset could erase the
// announcement of the event it caused. TMRERR and TMRCNT are therefore
// fields of the voted word, so the write that repairs a replica and the
// write that records the repair are the same write on the same edge, and
// an upset in the report is itself corrected and counted. Neither is
// clearable, for the reason WDOGRST and RSTCNT are not: a record
// software can erase is a record an upset can erase.
//
// THE POWER-ON DOMAIN CUTS BOTH WAYS, AND HERE IT CUTS HARDER THAN IT
// DID IN THE WATCHDOG. docs/40 section 7.2: state outside the reset
// domain is what makes a record survive and what makes a stale
// configuration survive. The same double edge applies to the PROTECTION,
// because the replicas are not reset either, and this block is the worst
// case for it in the design: strap_q is written once in a power cycle
// and cnt_q perhaps three times in a mission. A bank that HELD its value
// would repair a corrupted replica only at the next write -- which for
// strap_q is never -- so the first upset would be masked and then WAIT,
// and the second, in a different replica on the same bit, would not be
// corrected. soc_tmr_bank has no write enable: the whole word is written
// from the VOTED value on every clock edge, which makes the voter a
// continuous scrubber and bounds the exposure to a coincident second
// upset at ONE CLOCK CYCLE rather than at the rest of the mission.
//
// AND THE OTHER EDGE, which is this block's own and is not the
// watchdog's. The boot counter MUST survive a reset in order to count
// it, and it must not survive in a way that strands the part. Three
// things keep it out of docs/40 section 7.2's brick loop and none of
// them is the protection:
//
//   * the bound is a PARAMETER of the netlist, not a register. No write
//     reaches LIMIT, so a corrupted counter can reach the end of the
//     ladder early but cannot move the end of the ladder.
//   * the terminal state is not silence. At BSTAT.OVER the loader still
//     runs, still opens the console, still writes the report, and still
//     hands the decision to the platform with WDOGN asserted. docs/40
//     section 7.2's brick was a part that reset for ever WITH THE
//     CONSOLE NEVER REACHING ITS FIRST CHARACTER; this one talks.
//   * nothing in this block reaches a budget. Its only outputs are the
//     APB read path, which is the structural version of that document's
//     fix and is asserted by
//     test_the_boot_block_drives_nothing_but_its_own_read_data.
//
//   What the protection changes is only how likely a single upset is to
//   put the counter somewhere it was not. What it does NOT change is
//   that TWO upsets in two replicas on one bit inside one clock are
//   uncorrected, permanently, because no reset in this block ever
//   repairs the word. That residual is stated here rather than left to
//   be inferred, and docs/69 section 10 states it again.
//
// WHAT THIS DOES NOT BUY:
//   * The 74 unprotected flip-flops above are still unprotected, by
//     decision, and the campaign injects into every one of them so the
//     price is measured rather than asserted.
//   * The mismatch is COUNTED and STICKY in BSTAT and nothing raises a
//     pin or an interrupt on it. This block has no interrupt line and
//     the map gives it none; BUSSTAT's sticky field has one bit left and
//     docs/58 section 9.2 already spent the argument for it. Reading
//     BSTAT is the loader's job, on the next boot -- docs/16 section
//     7.6, "DETECTED depends on someone looking".
//   * HARDEN = 0 removes all of it and is EXACTLY the docs/68 design:
//     the banked width drops to the decision bits, so the configuration
//     is that document's 92 flip-flops and not that document's design
//     carrying five dead report bits. docs/41 section 6.5 is why that
//     distinction is worth a localparam.

`timescale 1ns / 1ps
`default_nettype none

module soc_boot #(
    // Bootstrap pins. Four is what soc_top.v brings out; the block
    // accepts 1..16 and BSTRAP reports the width so a driver written
    // for a wider part reads the right number of bits.
    parameter integer NSTRAP = 4,

    // Boot counter width. 8 bits, saturating at 255.
    parameter integer CNT_W = 8,

    // THE ATTEMPT LIMIT, AND WHY IT IS A PARAMETER AND NOT A REGISTER.
    //
    // soc_wdog.v W2: "a bound enforced by the width of a counter cannot
    // be misconfigured; one enforced by a comparator can." The same
    // argument applies one level up. The number of boots after which
    // the loader stops trying the flash is a property of the part, it
    // is reported through BSTAT so the loader does not carry a second
    // copy of it, and no register reaches it.
    //
    // THREE, and the reason is soc_top.v's WDOG_ESCALATE = 2. The
    // watchdog asserts its external pin on its SECOND stage-2 reset,
    // which is the reset that begins boot 2 (counting the power-on boot
    // as 0). Setting the limit to 3 makes boot 2 the last one the
    // loader attempts, and it is a boot during which the platform
    // supervisor has ALREADY been told: software gives up after the
    // hardware has escalated, never before. docs/68 section 6.
    parameter integer LIMIT = 3,

    // B1. 1 = the decision word is three replicas under a voter,
    // 0 = one plain register bank and no protection at all.
    //
    // This exists so the area cost of B1 can be measured against the
    // SAME source file and the same file list rather than against a
    // remembered number -- docs/41 section 6.5 records what quoting a
    // delta against the wrong baseline cost once, and docs/58 section 7
    // records it costing 25.4394 um2 a second time. Nothing in the
    // design sets it to 0 and sw/tests/test_soc_boot_guards.py checks
    // textually that nothing does.
    parameter integer HARDEN = 1
) (
    input  wire        clk_i,
    // System reset. Not used to reset anything in this block -- see the
    // header -- but its RELEASE is what BOOTCNT counts, so it is an
    // input to the logic rather than to the flip-flops.
    input  wire        rst_ni,
    // Power-on reset. The only reset this block has.
    input  wire        rst_por_ni,

    // ---- APB slave ----
    input  wire        psel_i,
    input  wire        penable_i,
    input  wire [11:0] paddr_i,      // offset within the 4 KiB slot
    input  wire        pwrite_i,
    input  wire [31:0] pwdata_i,
    output reg  [31:0] prdata_o,
    output wire        pready_o,
    output wire        pslverr_o,

    // ---- the pins ----
    input  wire [NSTRAP-1:0] strap_i,
    input  wire        wdog_dis_i
);

  localparam [11:0] REG_BSTRAP = 12'h000;
  localparam [11:0] REG_BSTAT  = 12'h004;
  localparam [11:0] REG_BRPT   = 12'h008;
  localparam [11:0] REG_EPOCH  = 12'h00C;

  localparam [CNT_W-1:0] CNT_MAX = {CNT_W{1'b1}};

  assign pready_o  = 1'b1;
  assign pslverr_o = 1'b0;

  wire access = psel_i && penable_i;
  wire wr     = access && pwrite_i;

  // -------------------------------------------------------------------
  // The state this block does NOT protect (B1)
  // -------------------------------------------------------------------
  //
  // Two synchroniser flops per pin, rewritten from the pins on every
  // clock, so an upset in any of them is shed in one or two clocks --
  // docs/41 section 3.1's first question answered in the direction that
  // says "leave it alone". Measured: 40 of 40 draws into these ten
  // flip-flops came back MASKED (docs/69 section 8.3).
  //
  // The residual is the clock on which the sample is taken, where an
  // upset in sync1 is latched into the protected word for the power
  // cycle -- and B1 does NOT close it. sync0 has the corresponding
  // clock one earlier. A uniform campaign draws into a window that
  // narrow about once in a hundred, so docs/69 section 8.6 demonstrates
  // it with a directed injection instead of pretending the 40 MASKED
  // records cover it.
  //
  // That residual is not the same shape as sys_q's, and the difference
  // is the whole reason one of them is in the word and these are not:
  // sys_q was exposed for the WHOLE mission and these are exposed for
  // one or two clocks of it.
  reg [NSTRAP-1:0] sync0, sync1;
  reg              wsync0, wsync1;

  always @(posedge clk_i or negedge rst_por_ni) begin
    if (!rst_por_ni) begin
      sync0   <= {NSTRAP{1'b0}};
      sync1   <= {NSTRAP{1'b0}};
      wsync0  <= 1'b0;
      wsync1  <= 1'b0;
    end else begin
      sync0  <= strap_i;
      sync1  <= sync0;
      wsync0 <= wdog_dis_i;
      wsync1 <= wsync0;
    end
  end

  // -------------------------------------------------------------------
  // The protected word (B1)
  // -------------------------------------------------------------------
  //
  // Every bit that is written once per power cycle or maintained by
  // hardware, concatenated into one word so that the MIX transform has
  // a width to work in. The field offsets are named constants used by
  // the packing, the unpacking and the register reads alike, because
  // docs/40 section 7.4 records what one literal bit position cost
  // soc_wdog.v once.
  localparam integer TMC_W    = 4;                     // mismatch counter
  localparam integer P_DLY    = 0;                     // 2
  localparam integer P_VALID  = P_DLY   + 2;           // 1
  localparam integer P_STRAP  = P_VALID + 1;           // NSTRAP
  localparam integer P_WDIS   = P_STRAP + NSTRAP;      // 1
  localparam integer P_ARMED  = P_WDIS  + 1;           // 1
  // THE SYSTEM-RESET SAMPLE, AND IT IS HERE BECAUSE THE CAMPAIGN PUT IT
  // HERE. The first version of B1 left it out, on the argument that a
  // register rewritten from its input every clock sheds an upset on its
  // own -- docs/41 section 3.1's first question, answered in the
  // direction that says leave it alone. That argument is about the
  // register and the consequence is not: an upset in `sys_q` while the
  // system reset is released MANUFACTURES A RELEASE EDGE, the counter
  // increments, and the counter is saturating and power-on-only, so
  // NOTHING EVER TAKES IT BACK. A self-correcting flip-flop with a
  // permanent consequence is not a self-correcting stratum.
  //
  // The campaign is what settled it. In the first run of
  // hw/soc/tb/cocotb/test_soc_boot_fi.py this bit was a plain flop and
  // its own stratum, and both draws into it came back SDC with
  // `gave_up_early` set: one flip of one bit, in the window, put the
  // part past its attempt limit for the rest of the power cycle. The
  // campaign of record draws four times and finds 3 SDC and 1 that gave
  // up early (docs/69 section 8.4), which is the same conclusion with a
  // wider error bar. It costs two more flip-flops to bundle it and it
  // is the cheapest bit in the block by consequence per flip-flop.
  localparam integer P_SYS    = P_ARMED + 1;           // 1
  localparam integer P_CNT    = P_SYS   + 1;           // CNT_W
  // Everything below P_TMRERR is state the block had before B1 and is
  // what the design DECIDES with. Everything at or above it is state B1
  // ADDED, and it is the report.
  localparam integer P_TMRERR = P_CNT   + CNT_W;       // 1
  localparam integer P_TMRCNT = P_TMRERR + 1;          // TMC_W
  localparam integer PDEC_W   = P_TMRERR;              // the decision bits
  localparam integer PFULL_W  = P_TMRCNT + TMC_W;      // + the report

  // What is actually BANKED. At HARDEN = 0 the two report fields are not
  // stored at all -- `prot_mismatch` is a constant zero there, so they
  // would be five flip-flops that can never change -- and dropping them
  // from the bank makes that configuration the docs/68 design EXACTLY
  // rather than the docs/68 design carrying five dead bits. docs/41
  // section 6.5's rule is that a baseline which carries part of the
  // feature understates the feature's cost; this is the same rule
  // applied to the baseline's flip-flop count.
  localparam integer PBANK_W  = (HARDEN != 0) ? PFULL_W : PDEC_W;

  generate
    // soc_tmr_bank refuses a bundle below four bits, so the narrow
    // direction is caught there with the reason in the message. This
    // guard is the other direction: POL and RST_VAL are 64-bit
    // parameters, and PBANK_W grows with NSTRAP and CNT_W.
    if (PBANK_W > 64) begin : g_prot_too_wide
      ERROR_soc_boot_protected_word_exceeds_64_bits guard ();
    end
    // The read decode below puts TMRCNT in four bits of BSTAT.
    if (TMC_W != 4) begin : g_tmc_w_not_four
      ERROR_soc_boot_TMC_W_must_match_the_BSTAT_field guard ();
    end
  endgenerate

  // Per-replica storage transform, the masks and the reasoning of
  // soc_wdog.v's W6 section, which is where they are argued: A is the
  // true image; B and C are mixed, so every stored bit of either is an
  // XOR of two or three distinct word bits and can equal neither x_i nor
  // ~x_i for any i, which makes them PROVABLY non-collidable with A
  // rather than measured to be. B and C are separated from each other by
  // POL_B = ~POL_C on every bit, and neither reset image is uniform --
  // docs/33's finding, which is that a bank whose reset image is all
  // ones is one dfflibmap builds by inversion and abc then folds against
  // the bank's own correction.
  //
  // The three masks and which replicas carry MIX are the same as
  // soc_wdog.v's, and that is checked rather than trusted:
  // `make -C hw/soc/formal boot_tmr_params` reads all six back out of
  // this file and fails if any has moved, so the composition
  // soc_wdog_tmr.sby proves is the composition this block instantiates.
  //
  // That job proves the masking theorem -- the voted word is the
  // reference under a fault free in every bit of any one replica, which
  // may move between replicas from one cycle to the next -- and it now
  // runs a prove_w23 task, because PBANK_W here is 23 at soc_top.v's
  // parameters and the four widths it ran at before did not include it.
  // A width a proof is not run at is a width it does not cover.
  localparam [63:0] POL_A = 64'h0000000000000000;
  localparam [63:0] POL_B = 64'h5555555555555555;
  localparam [63:0] POL_C = 64'hAAAAAAAAAAAAAAAA;

  wire [PBANK_W-1:0] prot_store;     // the voted word, or the plain one
  wire               prot_mismatch;  // this cycle a replica disagrees
  reg  [PFULL_W-1:0] prot_n;         // next value, combinational

  // `prot` is the full field layout, always PFULL_W wide so that every
  // part-select below is in range whatever HARDEN is. At HARDEN = 0 the
  // top five bits are constants that never enter a bank.
  wire [PFULL_W-1:0] prot;
  assign prot = prot_store;          // zero-extended when HARDEN = 0

  // Named views. Everything below this line reads these and never the
  // storage, so the read decode and hw/soc/formal/soc_boot_props.v are
  // written against the same names they were written against before B1
  // existed.
  wire [1:0]        dly       = prot[P_DLY   +: 2];
  wire              valid_q   = prot[P_VALID];
  wire [NSTRAP-1:0] strap_q   = prot[P_STRAP +: NSTRAP];
  wire              wdis_q    = prot[P_WDIS];
  wire              armed_q   = prot[P_ARMED];
  wire              sys_q     = prot[P_SYS];
  wire [CNT_W-1:0]  cnt_q     = prot[P_CNT   +: CNT_W];
  wire              tmr_err   = prot[P_TMRERR];
  wire [TMC_W-1:0]  tmr_count = prot[P_TMRCNT +: TMC_W];

  generate
  if (HARDEN != 0) begin : g_prot_tmr
    wire [PBANK_W-1:0] qa, qb, qc;

    // Written unconditionally from prot_n on every edge. That is the
    // scrub, and in THIS block it is the whole of the answer to the
    // power-on domain: strap_q is written once in a power cycle and
    // cnt_q perhaps three times in a mission, so a bank that held its
    // value would carry the first upset until the second one made it
    // uncorrectable. See soc_tmr_bank.v difference 1 and the B1 section
    // of this file's header.
    soc_tmr_bank #(.W(PBANK_W), .RST_VAL(64'd0), .POL(POL_A), .MIX(0))
      u_prot_a (.clk_i(clk_i), .rst_ni(rst_por_ni),
                .d_i(prot_n[PBANK_W-1:0]), .q_o(qa));
    soc_tmr_bank #(.W(PBANK_W), .RST_VAL(64'd0), .POL(POL_B), .MIX(1))
      u_prot_b (.clk_i(clk_i), .rst_ni(rst_por_ni),
                .d_i(prot_n[PBANK_W-1:0]), .q_o(qb));
    soc_tmr_bank #(.W(PBANK_W), .RST_VAL(64'd0), .POL(POL_C), .MIX(1))
      u_prot_c (.clk_i(clk_i), .rst_ni(rst_por_ni),
                .d_i(prot_n[PBANK_W-1:0]), .q_o(qc));

    // hw/rtl/tmr_voter.v, read in place and not copied. docs/34 freezes
    // the directory it lives in and nothing here modifies it; it is the
    // majority gate formal/tmr_voter.sby proves exhaustively and
    // hw/tb/test_tmr_voter.py checks against an independent Python
    // model, rather than a copy that can drift.
    tmr_voter #(.WIDTH(PBANK_W)) u_prot_vote (
        .in_a     (qa),
        .in_b     (qb),
        .in_c     (qc),
        .out      (prot_store),
        .mismatch (prot_mismatch)
    );
  end else begin : g_prot_plain
    // HARDEN = 0: the block as docs/68 shipped it. Measurement only.
    reg [PBANK_W-1:0] plain;
    always @(posedge clk_i or negedge rst_por_ni) begin
      if (!rst_por_ni) plain <= {PBANK_W{1'b0}};
      else             plain <= prot_n[PBANK_W-1:0];
    end
    assign prot_store    = plain;
    assign prot_mismatch = 1'b0;
  end
  endgenerate

  // -------------------------------------------------------------------
  // The next state, as ONE combinational function
  // -------------------------------------------------------------------
  //
  // Written this way so that the hardened and the HARDEN = 0
  // configurations run IDENTICAL policy from identical text: the only
  // difference between them is what stores the word. docs/41 section 6.5
  // and docs/58 section 7 both record what happens when the baseline is
  // a different shape of the same design -- the delta credits the
  // hardening with a refactor's saving.
  //
  // Three groups, and they are the three always blocks docs/68 had:
  //
  //   the straps -- `dly` counts the three clocks, and when it reaches
  //   the third the synchronised value is latched and VALID goes high.
  //   Neither ever changes again short of a power cycle, which is D4.
  //
  //   BOOTCNT -- `armed_q` is what makes the POWER-ON boot count zero.
  //   The power-on release is a release like any other and would
  //   otherwise be counted; instead it arms the counter, so BOOTCNT
  //   reads "boots since power-on, not counting this one", which is the
  //   number the loader needs because it is deciding whether to attempt
  //   THIS boot.
  //
  //   the report -- last, and unconditionally, so that a mismatch is
  //   recorded on the same edge that repairs the replica it came from.
  always @(*) begin
    prot_n = prot;

    if (!valid_q) begin
      if (dly == 2'd2) begin
        prot_n[P_STRAP +: NSTRAP] = sync1;
        prot_n[P_WDIS]            = wsync1;
        prot_n[P_VALID]           = 1'b1;
      end else begin
        prot_n[P_DLY +: 2] = dly + 2'd1;
      end
    end

    prot_n[P_SYS] = rst_ni;
    if (rst_ni && !sys_q) begin
      if (!armed_q)     prot_n[P_ARMED]        = 1'b1;
      else if (~&cnt_q) prot_n[P_CNT +: CNT_W] =
                            cnt_q + {{(CNT_W-1){1'b0}}, 1'b1};
    end

    prot_n[P_TMRERR] = tmr_err | prot_mismatch;
    if (prot_mismatch && ~&tmr_count)
      prot_n[P_TMRCNT +: TMC_W] = tmr_count + {{(TMC_W-1){1'b0}}, 1'b1};
  end

  // -------------------------------------------------------------------
  // The report and the epoch: written by software, kept across a reset
  // -------------------------------------------------------------------
  reg [31:0] brpt_q, epoch_q;
  always @(posedge clk_i or negedge rst_por_ni) begin
    if (!rst_por_ni) begin
      brpt_q  <= 32'h0;
      epoch_q <= 32'h0;
    end else begin
      if (wr && (paddr_i == REG_BRPT))  brpt_q  <= pwdata_i;
      if (wr && (paddr_i == REG_EPOCH)) epoch_q <= pwdata_i;
    end
  end

  // -------------------------------------------------------------------
  // Reads
  // -------------------------------------------------------------------
  // The limit as a vector of each width it is compared or reported at,
  // written once so no comparison below carries its own conversion.
  //
  // The part-selects are EXPLICIT rather than left to the assignment's
  // implicit truncation, because Verilator's WIDTHTRUNC is an error in
  // this repository's lint and an implicit narrowing of a parameter is
  // exactly the class of thing it is right to be loud about: a LIMIT
  // that did not fit in CNT_W bits would silently become a different
  // limit. It does not fit is now a thing a reader can see.
  localparam [CNT_W-1:0]  LIMIT_C  = LIMIT[CNT_W-1:0];
  localparam [7:0]        LIMIT_B  = LIMIT[7:0];
  localparam [3:0]        NSTRAP_B = NSTRAP[3:0];

  wire last_attempt = (cnt_q >= (LIMIT_C - {{(CNT_W-1){1'b0}}, 1'b1}));
  wire over_limit   = (cnt_q >= LIMIT_C);

  // Widened once so the read decode below is a plain concatenation, and
  // widened by assignment rather than by concatenation so that NSTRAP =
  // 16 or CNT_W = 8 does not ask for a zero-width replication.
  reg [15:0] strap_w;
  reg [7:0]  cnt_w;
  always @(*) begin
    strap_w = 16'h0;
    strap_w[NSTRAP-1:0] = strap_q;
    cnt_w = 8'h0;
    cnt_w[CNT_W-1:0] = cnt_q;
  end

  always @(*) begin
    case (paddr_i)
      // BSTRAP: the pins in the low half, the width and the two
      // one-shot flags in the high half.
      REG_BSTRAP: prdata_o = {valid_q, 3'h0, NSTRAP_B,
                              7'h0, wdis_q, strap_w};
      // BSTAT: the counter, the two derived flags a loader would
      // otherwise recompute, the limit that is a constant of the
      // netlist, and B1's mismatch report in the top five bits.
      //
      // TMRERR is sticky and TMRCNT saturates, and NEITHER IS
      // CLEARABLE -- a write to this offset does nothing at all, which
      // is D1's shape applied to the report. A loader that finds TMRCNT
      // non-zero on a boot is looking at upsets the previous boot's
      // protection corrected; on this part that is the only channel the
      // report has, because the block has no interrupt line and the map
      // gives it none.
      REG_BSTAT:  prdata_o = {tmr_err, tmr_count, 3'h0, LIMIT_B,
                              6'h0, over_limit, last_attempt, cnt_w};
      REG_BRPT:   prdata_o = brpt_q;
      REG_EPOCH:  prdata_o = epoch_q;
      default:    prdata_o = 32'h0;
    endcase
  end

`ifdef FORMAL
`include "soc_boot_props.v"
`endif

endmodule

`default_nettype wire
