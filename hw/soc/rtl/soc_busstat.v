// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// BUSSTAT: the counters that make a corrected upset an observable event.
//
// =====================================================================
// WHY THIS BLOCK EXISTS
// =====================================================================
//
// `docs/43-core-hardening.md` put a SECDED codec around the
// architectural register file and measured it working: 190 of 200
// injections corrected, zero silent corruptions where docs/42 had three.
// Then section 6.5 said what that was worth to an operator:
//
//     the correction is SILENT: in silicon, a corrected upset is
//     indistinguishable from no upset at all
//
// and section 10 called it "the single largest gap this document opens".
// A part whose stated purpose is to survive an upset environment and
// which cannot say how often it is being hit has no way to tell a
// healthy part from one about to fail, and no way to report the
// environment it is in. docs/16 section 4.1 made the same point about
// the NPU pilot and pilot_top.v records the same mistake being made
// there: four ECC status wires were left unconnected, so a campaign
// measured 84 corrections and had to classify every one MASKED.
//
// This is the destination the frozen memory map already reserved for
// exactly this. `docs/memmap-soc.md` section 3 has carried
//
//     0xFF915000  BUSSTAT  irq 22  line 10  reserved
//     "System-bus error latch and ECC counters; AHBSTAT in spirit,
//      not in name"
//
// since docs/39 froze the map. Nothing about the address, the slot, the
// interrupt number or the line is new here; what is new is that
// something now decodes it.
//
// It also closes `docs/41` section 10 item 3 in that document's own
// words -- "Nothing raises an alarm on TMRERR ... A fault line into
// BUSSTAT, or a fast interrupt, is the obvious next step and neither
// exists" -- because the watchdog's voter mismatch arrives here on
// `tmr_ev_i` and is counted beside the register file's.
//
// =====================================================================
// THE COUNTERS, AND WHY THEY ARE EIGHT AND NOT ONE
// =====================================================================
//
// pilot_top.v aggregates its LIF core's corrections into the same
// CNT_SEC as its weight-load path, and says in a comment what that
// costs: "a host reading CNT_SEC cannot tell a synapse array correction
// from a load-path one". That aggregation was the right call there
// because the register map was already frozen. Here the map is not, so
// the counters are separated where separating them answers a different
// question:
//
//   CNT_RFSEC   Single-bit upsets the register file's SCRUB repaired.
//               THIS IS THE UPSET-RATE COUNTER. The scrub walks x1..x31
//               and re-encodes what it finds, so an upset that the
//               program does not overwrite first is counted EXACTLY
//               ONCE -- on the cycle the repaired word is written back.
//               A mission that wants its measured SEU rate reads this
//               one.
//
//   CNT_RFRD    CYCLES in which a read port returned a corrected word.
//               This is NOT a count of upsets and the name of the field
//               in the header file says so: one corrupted register read
//               on ten cycles before the scrub reaches it raises this
//               ten times. It is an upper bound on the upset count and
//               a lower bound on nothing. It is carried separately
//               rather than folded into CNT_RFSEC precisely so that no
//               reader can mistake one for the other, and it is worth
//               carrying because CNT_RFRD >> CNT_RFSEC means upsets are
//               being read before they are scrubbed -- which is the
//               observable signature of the scrub period being too long
//               for the rate, the one thing docs/43 section 6.4 left
//               unbounded.
//
//   CNT_RFDED   Syndromes the codec could not correct. Two upsets in one
//               register between two scrubs is what this counts, and it
//               is the number that says the environment has outrun the
//               protection.
//
//   CNT_TMRERR  Mismatches the watchdog's voter masked (docs/41 W6).
//               A different structure, a different mechanism and a
//               different remedy, so a different counter.
//
// and three added by docs/55, which are the NPU connection's. docs/52
// section 10 counted 79 upsets in 700 injections absorbed by mechanisms
// that WORKED, and found that no software and no pin could see any of
// them -- "in silicon a corrected pointer upset is indistinguishable
// from no upset at all". docs/51 section 14 item 1 had declined to give
// them a home on the grounds that a fault-counter block invented inside
// soc_npu.v would put NPU-only telemetry outside BUSSTAT. That argument
// is about WHERE THE COUNTERS LIVE, and this is where they live.
//
//   CNT_NPUCOR  Pointer-vote disagreements aer_fifo CORRECTED, across
//               both of the connection's queues. The queues' pointers
//               are triple-redundant and reload every replica from the
//               vote on the next edge, so this counts upsets the part
//               survived. It is the connection's UPSET-RATE counter, the
//               way CNT_RFSEC is the core's, and docs/52 section 6.1
//               measured 74 of them in 700 injections.
//
//   CNT_NPUDET  Queue entries the connection DISCARDED: an entry whose
//               stored parity failed, or a read whose two rd_valid rails
//               disagreed. NOT the same event as CNT_NPUCOR and
//               deliberately not folded into it -- a correction lost
//               nothing and a discard LOST AN EVENT. A mission reading
//               this one is reading dropped work.
//
//   CNT_NPUTMR  Mismatches the NPU cause bank's own voter masked
//               (soc_npu.v H3). Separate from CNT_TMRERR for exactly the
//               reason CNT_TMRERR is separate from CNT_RFSEC: a host
//               that could not tell a watchdog vote from an NPU vote
//               would be reading the aggregate pilot_top.v's header
//               records costing it -- "a host reading CNT_SEC cannot
//               tell a synapse array correction from a load-path one".
//
// and one added by docs/58, which is the time base's:
//
//   CNT_MTECC   Cycles in which the CLINT's stored mtime codeword was
//               not a codeword (soc_clint.v H6). docs/41 section 7.4
//               ranked mtime above everything the watchdog wave left
//               unprotected -- "an upset displaces it FOR EVER" -- and
//               this is the counter that says how often the code that
//               now protects it has had to act.
//
//               IT CONFLATES A CORRECTION WITH AN UNCORRECTABLE, which
//               is the exact aggregation the paragraph above criticises
//               pilot_top.v for, and it is done knowingly. There is one
//               bit left below the interrupt bit, S_MTECC's comment
//               says why a ninth source is not free, and the class the
//               conflation hides is empty under this repository's fault
//               model: mtime's codeword is re-encoded every clock, so
//               an uncorrectable needs TWO upsets inside one 20 ns tick
//               in one 72-bit word. The cost is named rather than
//               glossed -- an operator watching this counter move
//               cannot tell a healed clock from a wrong one, and the
//               only thing that can is software comparing mtime against
//               the core's own mcycle. docs/58 sections 5 and 9.
//
// All five SATURATE. A counter that wraps is indistinguishable from a
// counter that has barely moved, which for a radiation counter is the
// one failure that cannot be detected downstream. pilot_top.v saturates
// for the same reason.
//
// =====================================================================
// TWO RESET DOMAINS, AND THE BRICK THAT MADE THEM TWO
// =====================================================================
//
// The RECORD -- the eight counters and the eight sticky bits -- is in the
// POWER-ON domain, by docs/40's W4 argument applied to telemetry: a
// watchdog stage-2 reset must not erase the evidence of what caused it.
// The most valuable reading of these counters is the one taken after
// the reset they explain.
//
// The INTERRUPT ENABLE is in the SYSTEM domain, and it is in a different
// domain from the record on purpose. docs/40 section 7.2 spent a section
// on a brick this project built once already: a mechanism installed
// before software went wrong, which survived the reset that going wrong
// caused, and which then fired again on the fresh boot for ever. An
// enabled fault interrupt with a sticky bit still set is exactly that
// shape -- the handler would be entered before the boot code has
// installed one. So IRQEN clears on every system reset, the record does
// not, and a fresh boot sees the whole history and is interrupted by
// none of it until it asks to be.
//
// =====================================================================
// WHAT CLEARING MEANS, AND THE ARGUMENT AGAINST IT
// =====================================================================
//
// docs/43 section 5.3 states the rule this block has to answer to: "A
// record software can erase is a record an upset can erase." Here the
// record IS software-clearable, through CLR, and that is a decision
// rather than an oversight:
//
//   * A rate is a count over an interval, and an interval needs an
//     origin. A counter that can never be zeroed can report a total and
//     cannot report a rate, and the rate is what a mission telemetry
//     frame carries.
//   * The saturation makes the un-clearable version worse rather than
//     better: a counter that has saturated and cannot be cleared is
//     dead for the rest of the mission.
//   * pilot_top.v's FAULT_CLR makes the same choice for the same
//     registers, so this is the convention this project already has.
//
// The cost, stated: a wild store to CLR erases the record. That is the
// same exposure every clearable status register in this SoC has, it is
// not gated by a key -- unlike the watchdog, this block cannot brick
// anything -- and it is named here rather than left to be found.
//
// An event and a clear in the same cycle resolve in favour of the
// EVENT: the counter goes to one and the sticky stays set. Losing the
// upset that arrives on the cycle the frame is read is the one loss
// this block can avoid for free.
//
// =====================================================================
// BUS
// =====================================================================
//
// AMBA 3 APB slave, the conventions soc_uart.v and soc_gptimer.v already
// use: PREADY tied high, PSLVERR tied low, an offset inside the slot
// that names no register reads zero and a write to it does nothing.

`timescale 1ns / 1ps
`default_nettype none

module soc_busstat #(
    // Counter width. 16 bits saturating at 65,535 is the pilot's CNT_W.
    parameter integer CNT_W = 16
) (
    input  wire        clk_i,
    // System reset: the interrupt enable, and nothing else.
    input  wire        rst_ni,
    // Power-on reset: the record.
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

    // ---- fault lines ----
    // {2,1,0} = {DED, corrected on read, corrected by the scrub}, from
    // ibex_regfile_secded.v by way of the ibex_top port that
    // hw/soc/flow/ibex_fault_port.py adds.
    input  wire [2:0]  rf_ecc_err_i,
    // One pulse per masked TMR mismatch in the watchdog (docs/41 W6).
    input  wire        tmr_ev_i,
    // The NPU connection's three, from soc_npu.v (docs/55). Each is one
    // cycle per event by construction at the source, which is the
    // property these counters need and the one soc_npu.v's port comment
    // establishes for all three.
    input  wire        npu_cor_i,   // a queue pointer vote corrected
    input  wire        npu_det_i,   // a queue entry was discarded
    input  wire        npu_tmr_i,   // the NPU cause bank's voter masked
    // The CLINT's, from soc_clint.v H6 (docs/58). One cycle per event by
    // construction at the source for a reason no other line here has:
    // mtime's codeword is re-encoded on EVERY edge, so a syndrome that is
    // nonzero this cycle is zero the next whether it was correctable or
    // not. THIS IS THE LAST SOURCE THAT FITS -- see S_MTECC below.
    input  wire        mt_ecc_i,

    // Level, to fast interrupt line 10 (IRQ 22 in the frozen map).
    output wire        irq_o
);

  localparam [11:0] REG_STATUS = 12'h000;
  localparam [11:0] REG_IRQEN  = 12'h004;
  localparam [11:0] REG_RFSEC  = 12'h008;
  localparam [11:0] REG_RFRD   = 12'h00C;
  localparam [11:0] REG_RFDED  = 12'h010;
  localparam [11:0] REG_TMRERR = 12'h014;
  localparam [11:0] REG_CLR    = 12'h018;
  // docs/55. CLR keeps 0x018 -- it is in hw/soc/tb/sw/soc_busstat.h and
  // in every program that has been written against this block -- and the
  // three new counters go above it rather than displacing anything.
  localparam [11:0] REG_NPUCOR = 12'h01C;
  localparam [11:0] REG_NPUDET = 12'h020;
  localparam [11:0] REG_NPUTMR = 12'h024;
  // docs/58. Same rule: nothing below it moves.
  localparam [11:0] REG_MTECC  = 12'h028;

  // Bit index of each source, shared by STATUS, IRQEN and CLR so that
  // the three cannot disagree about which bit is which. sw/tests and
  // hw/soc/tb/sw/soc_timers.h carry the same names.
  localparam integer S_RFSEC  = 0;
  localparam integer S_RFRD   = 1;
  localparam integer S_RFDED  = 2;
  localparam integer S_TMRERR = 3;
  localparam integer S_NPUCOR = 4;
  localparam integer S_NPUDET = 5;
  localparam integer S_NPUTMR = 6;
  // docs/58 H6. THE LAST BIT BELOW THE INTERRUPT, and that is a hard
  // constraint and not a coincidence: the read multiplexer below places
  // irq_o at bit 8 and the comment there forbids moving it, so the
  // sticky field could grow to bit 7 and no further. A ninth source
  // either moves an interrupt bit that is in a frozen header and in
  // every program written against this block, or leaves a hole at bit 8
  // and puts the sticky field on both sides of it. Neither is free, and
  // whoever needs a ninth should read docs/58 section 9 before choosing.
  localparam integer S_MTECC  = 7;
  localparam integer NSRC     = 8;

  localparam [CNT_W-1:0] CNT_MAX = {CNT_W{1'b1}};

  assign pready_o  = 1'b1;
  assign pslverr_o = 1'b0;

  wire access = psel_i && penable_i;
  wire wr     = access && pwrite_i;

  // ---- the events, one bit per source, in one vector ----------------
  wire [NSRC-1:0] ev;
  assign ev[S_RFSEC]  = rf_ecc_err_i[0];
  assign ev[S_RFRD]   = rf_ecc_err_i[1];
  assign ev[S_RFDED]  = rf_ecc_err_i[2];
  assign ev[S_TMRERR] = tmr_ev_i;
  assign ev[S_NPUCOR] = npu_cor_i;
  assign ev[S_NPUDET] = npu_det_i;
  assign ev[S_NPUTMR] = npu_tmr_i;
  assign ev[S_MTECC]  = mt_ecc_i;

  // ---- the clear strobes --------------------------------------------
  wire [NSRC-1:0] clr;
  assign clr = (wr && (paddr_i == REG_CLR)) ? pwdata_i[NSRC-1:0]
                                            : {NSRC{1'b0}};

  // ---- the record: one counter and one sticky per source, POR domain
  //
  // One `always` block per source, each driving its own `reg`, gathered
  // into the vectors below by continuous assignment. Writing different
  // elements of one array from four generated blocks is legal and it is
  // the shape that has bitten this repository's tools before; this
  // costs nothing and cannot.
  wire [CNT_W-1:0] cnt    [0:NSRC-1];
  wire [NSRC-1:0]  sticky;

  genvar gi;
  generate
    for (gi = 0; gi < NSRC; gi = gi + 1) begin : g_src
      reg [CNT_W-1:0] cnt_q;
      reg             sticky_q;

      // THE EVENT IS A BRANCH CONDITION AND NOT AN ADDEND, and that is
      // not a style choice. The first version of this block computed
      // `{1'b0, cnt_q} + {{CNT_W{1'b0}}, ev[gi]}` and saturated on the
      // carry, which is arithmetically identical and synthesises the
      // same -- and it made two of the counters read X for the
      // whole of every SoC simulation.
      //
      // The reason is upstream's, not this block's. `rf_ecc_err_i[1]`
      // and `[2]` are the READ-PORT reports, and a read port's syndrome
      // is a function of `raddr_a_i`, which comes from
      // `instr_rdata_id` -- a flip-flop Ibex does not reset at
      // SecureIbex = 0. So for the first instructions after reset the
      // read address is X in simulation, the syndrome is X, the report
      // is X, and an ADDED X poisons the counter permanently. A
      // BRANCHED X does not: the branch is simply not taken, which is
      // also what happens in silicon, where the address is an
      // unspecified but definite value, the registers are all reset to
      // a valid codeword, and no error is reported at all.
      //
      // The cost of the branch form, stated: in SIMULATION this counter
      // does not include any correction that happened while the read
      // address was still X. docs/44 section 10 lists it. The saturation
      // guard is `~&cnt_q`, the same idiom soc_wdog.v uses for TMRCNT
      // and ibex_regfile_secded.v for its own counters.
      always @(posedge clk_i or negedge rst_por_ni) begin
        if (!rst_por_ni) begin
          cnt_q    <= {CNT_W{1'b0}};
          sticky_q <= 1'b0;
        end else if (clr[gi]) begin
          // The event wins. See the header.
          if (ev[gi]) begin
            cnt_q    <= {{(CNT_W-1){1'b0}}, 1'b1};
            sticky_q <= 1'b1;
          end else begin
            cnt_q    <= {CNT_W{1'b0}};
            sticky_q <= 1'b0;
          end
        end else if (ev[gi]) begin
          sticky_q <= 1'b1;
          if (~&cnt_q) cnt_q <= cnt_q + {{(CNT_W-1){1'b0}}, 1'b1};
        end
      end

      assign cnt[gi]    = cnt_q;
      assign sticky[gi] = sticky_q;
    end
  endgenerate

  // ---- the interrupt enable, system domain --------------------------
  reg [NSRC-1:0] irqen;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni)
      irqen <= {NSRC{1'b0}};          // nothing is enabled out of reset
    else if (wr && (paddr_i == REG_IRQEN))
      irqen <= pwdata_i[NSRC-1:0];
  end

  // Level, from the STICKY and not from the event: a one-cycle pulse on
  // a fast interrupt line is a pulse the core can be in the middle of a
  // trap for. The handler clears the sticky through CLR, which is what
  // deasserts the line -- the same acknowledge discipline the watchdog's
  // stage 1 uses.
  assign irq_o = |(sticky & irqen);

  // ---- reads --------------------------------------------------------
  always @(*) begin
    case (paddr_i)
      // Bit 8 is the interrupt and stays at bit 8: it is in the frozen
      // header and in every program written against this block, so the
      // sticky field grew UP TO bit 7 and the gap between them closed
      // rather than the interrupt moving. docs/58 took the last bit of
      // that gap; the field is now full and S_MTECC's comment says what
      // a ninth source costs.
      REG_STATUS: prdata_o = {23'h0,
                              irq_o,                        // 8
                              sticky};                      // 7..0
      REG_IRQEN:  prdata_o = {{(32-NSRC){1'b0}}, irqen};
      REG_RFSEC:  prdata_o = {{(32-CNT_W){1'b0}}, cnt[S_RFSEC]};
      REG_RFRD:   prdata_o = {{(32-CNT_W){1'b0}}, cnt[S_RFRD]};
      REG_RFDED:  prdata_o = {{(32-CNT_W){1'b0}}, cnt[S_RFDED]};
      REG_TMRERR: prdata_o = {{(32-CNT_W){1'b0}}, cnt[S_TMRERR]};
      REG_NPUCOR: prdata_o = {{(32-CNT_W){1'b0}}, cnt[S_NPUCOR]};
      REG_NPUDET: prdata_o = {{(32-CNT_W){1'b0}}, cnt[S_NPUDET]};
      REG_NPUTMR: prdata_o = {{(32-CNT_W){1'b0}}, cnt[S_NPUTMR]};
      REG_MTECC:  prdata_o = {{(32-CNT_W){1'b0}}, cnt[S_MTECC]};
      // CLR is write-only. It reads zero rather than reading back what
      // was last written, because a clear strobe has no state and a
      // register that reads back a strobe invites software to treat it
      // as one.
      default:    prdata_o = 32'h0;
    endcase
  end

`ifdef FORMAL
`include "soc_busstat_props.v"
`endif

endmodule

`default_nettype wire
