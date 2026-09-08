// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Clock gate model for the riscv-formal run. docs/63.
//
// THIS IS A SUBSTITUTION AND NOT THE DESIGN. hw/soc/rtl/prim_clock_gating.v
// binds the PDK's real integrated clock gate `sg13g2_lgcp_1`, and behind
// `SG13G2_ICG_BEHAVIOURAL` it carries a latch-plus-AND simulation model.
// Neither is used here. This one passes the clock through unchanged and
// discards the enable.
//
// WHY. `ibex_top` gates the whole core's clock when it sleeps, so both
// of the real models produce a DERIVED clock. A derived clock makes the
// design multi-clock, and sby's single-clock smtbmc model cannot
// represent it: the flows that can (`multiclock on`, or `clk2fflogic`)
// re-express every flip-flop as level-sensitive logic and multiply the
// state space by a large factor on a design that already has ~2,100
// flip-flops. Every riscv-formal check would become intractable to buy
// the modelling of a power optimisation.
//
// WHAT IT COSTS, and it is not nothing. With the gate held open the
// core keeps clocking through the sleep state that a `wfi` enters. The
// controller's own state machine is what holds the core in that state,
// so the retirement trace should be unaffected -- but "should be" is the
// right verb: this is an assumption and docs/63 section 4.1 ledgers it
// as A7. Ibex's own formal flow makes the same one and says so in one
// line: "We assume `ResetAll` and no clock gating"
// (dv/formal/README.md at the pinned commit) [fact].
//
// The port list is `ibex_top`'s, unchanged, so a port that moves
// upstream is an elaboration error and not a silent mis-binding.

module prim_clock_gating (
  input  clk_i,
  input  en_i,
  input  test_en_i,
  output clk_o
);
  // The enable is read and discarded, so an unused-signal warning does
  // not hide a genuinely unconnected port.
  wire unused_en = en_i & test_en_i;
  assign clk_o = clk_i;
endmodule
