// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Properties for clkgate_wake_gnt.v -- docs/77 section 18.
//
// Textually included at the end of the module body under `ifdef FORMAL,
// clkgate_wake_props.v's arrangement and for its reason: every property
// samples the same `posedge clk_i` the design does.

  reg f_past_valid;
  initial f_past_valid = 1'b0;
  always @(posedge clk_i) f_past_valid <= 1'b1;

  // The part comes out of reset. clkgate_wake_props.v says why: the
  // wake bit and the hold counter are asynchronously reset and the
  // basecase must start from the state silicon starts from.
  initial assume (!rst_ni);

  // -------------------------------------------------------------------
  // R1 -- THE FABRIC'S RULE 1, assumed of the master.  A request is held
  // until it is granted: soc_bus.v S1, and what makes a grant one cycle
  // late a delay and not a loss.  Without it G3's second half is not a
  // statement about anything -- a master that withdraws in the refused
  // cycle is not owed a grant in the next.
  // -------------------------------------------------------------------
  always @(posedge clk_i)
    if (f_past_valid && $past(rst_ni) && rst_ni && $past(req_i && !gnt))
      assume (req_i);

  // -------------------------------------------------------------------
  // G1 -- NO ACCEPTANCE IN A CYCLE THE GATE REMOVES.  The grant and the
  // APB completion both imply the enable.  By construction, and stated
  // so that a later edit to either line is caught: this is the property
  // that lets the two transient inputs leave the enable.
  // -------------------------------------------------------------------
  always @(*) if (rst_ni) assert (!gnt || en);
  always @(*) if (rst_ni) assert (!apb_done || en);

  // -------------------------------------------------------------------
  // G2 -- THE ENABLE READS NO INPUT.  In every cycle after reset, `en`
  // equals a function of the previous edge's registers alone: it is
  // `$past(npu_act) || (wake_hold != 0)`, and `wake_hold` is a register.
  // The inputs of THIS cycle -- `req_i`, `psel_i`, `slow_i`, `idle_i`
  // -- are free here and appear nowhere in the right-hand side, which
  // is the formal form of "the GATE pin's cone is four flip-flops".
  // -------------------------------------------------------------------
  always @(posedge clk_i)
    if (f_past_valid && $past(rst_ni) && rst_ni)
      assert (en == ($past(npu_act) || (wake_hold != HOLD_ZERO)));

  // -------------------------------------------------------------------
  // G3 -- THE COST IS ONE CYCLE, BOUNDED.  A request present in any
  // cycle has the block clocked at the end of the next one; and a
  // request that was refused is granted in the cycle after, if the block
  // is idle then.  "If idle" is the block's own readiness, which the
  // grant was qualified by before this change and is not this change's
  // to bound.
  // -------------------------------------------------------------------
  always @(posedge clk_i)
    if (f_past_valid && $past(rst_ni) && rst_ni && $past(req_i))
      assert (en);
  always @(posedge clk_i)
    if (f_past_valid && $past(rst_ni) && rst_ni && $past(req_i && !gnt)
        && idle_i)
      assert (gnt);

  // -------------------------------------------------------------------
  // T2 -- clkgate_wake.v's T2, UNCHANGED.  A frozen term true in any
  // cycle has the block clocked at the end of the next.  The fault
  // lines' guarantee does not depend on the fast half being in the
  // enable, and this is where that is shown.
  // -------------------------------------------------------------------
  always @(posedge clk_i)
    if (f_past_valid && $past(rst_ni) && rst_ni && $past(slow_i))
      assert (en);

  // -------------------------------------------------------------------
  // Vacuity, docs/09 section B.1.  G1 is satisfied by an enable that is
  // the constant 1 and G3 by a request that never comes, so the states
  // the theorem is about are covered explicitly.
  // -------------------------------------------------------------------
  always @(*) if (rst_ni) cover (!en);                          // W1: it shuts
  always @(posedge clk_i)                                       // W2: for a while
    if (f_past_valid && $past(rst_ni) && rst_ni)
      cover (!en && !$past(en));
  always @(*) if (rst_ni) cover (req_i && !en);                 // W5: a request
                                                                // finds it shut
  always @(posedge clk_i)                                       // W6: ...and is
    if (f_past_valid && $past(rst_ni) && rst_ni)                // granted one
      cover ($past(req_i && !en) && gnt);                       // cycle later
  always @(posedge clk_i)                                       // W7: the first
    if (f_past_valid && $past(rst_ni) && rst_ni)                // grant after a
      cover (gnt && !$past(en));                                // sleep
  always @(posedge clk_i)                                       // W8: an APB
    if (f_past_valid && $past(rst_ni) && rst_ni)                // access
      cover ($past(psel_i && !penable_i && !en) && apb_done);   // completes at
                                                                // its first
                                                                // ACCESS cycle
