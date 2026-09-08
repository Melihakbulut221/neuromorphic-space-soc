// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Properties for clkgate_wake.v -- docs/77 section 6.
//
// Textually included at the end of the module body under `ifdef FORMAL,
// which is soc_bus_props.v's arrangement and for its reason: every
// property samples the same `posedge clk_i` the design does.

  reg f_past_valid;
  initial f_past_valid = 1'b0;
  always @(posedge clk_i) f_past_valid <= 1'b1;

  // THE PART COMES OUT OF RESET, and without saying so the basecase
  // starts from an arbitrary `wake_q` -- a state no silicon is ever in,
  // because the bit is asynchronously reset to 1 by the same `rst_ni`
  // soc_npu.v resets `wake_hold` with. Without this the induction step
  // passes and the basecase fails on step 0, which is the model's
  // initial state and not a behaviour. soc_bus_props.v's F10 excludes
  // the same edge with `$past(rst_ni) && rst_ni` and says so.
  initial assume (!rst_ni);

  // -------------------------------------------------------------------
  // A1 -- THE HYPOTHESIS.  docs/76's enable is complete: the block's
  // state never moves at an edge that `fast | slow` did not cover.
  //
  // It is ASSUMED here and MEASURED elsewhere.  docs/76 section 6 is the
  // measurement -- two whole-SoC builds one parameter apart, 5,137
  // signal paths compared at 415,345 clock edges, zero cycles differing
  // -- and docs/77 section 7 repeats it on this document's RTL.  Stating
  // it as an assumption is what makes the theorem below a statement
  // about the CHANGE rather than a second proof of docs/76.
  // -------------------------------------------------------------------
  always @(*) if (rst_ni) assume (!changed_i || en_old);

  // -------------------------------------------------------------------
  // A2 -- THE SIDE CONDITION.  `slow` is a function of the block's
  // state, so it cannot move in a cycle in which the state did not.
  //
  // This is the one docs/77 makes machine-checkable rather than
  // arguable: sw/tests/test_soc_clkgate_guards.py elaborates soc_npu.v,
  // flattens it, walks the fan-in cone of `npu_act_slow` cut at every
  // sequential cell, and fails if any input port is reachable.
  //
  // THE `upset` TASKS DROP IT, and that is not a weakening of the job --
  // it is the second half of it. An upset that flips a register inside a
  // block whose clock is stopped is exactly a `slow` term rising in a
  // cycle in which the state did not move, which is what A2 forbids. So
  // the tasks that drop A2 are the tasks that model the fault, and what
  // survives there is T2 and not T1. docs/77 section 6.3.
  // -------------------------------------------------------------------
`ifndef NO_A2
  always @(posedge clk_i)
    if (f_past_valid && $past(rst_ni) && rst_ni && !$past(changed_i))
      assume (slow_i == $past(slow_i));
`endif

  // -------------------------------------------------------------------
  // T1 -- THE THEOREM.  The registered-wake enable is complete too.
  //
  // Everything docs/76 section 4.2 says about F10's transport then
  // applies unchanged: the gated instance's state can differ from the
  // ungated one's only at an edge the gate removed, and T1 says the
  // ungated instance's state does not change at those edges either.
  //
  // It NEEDS A2 and the `upset` tasks are where that shows: with A2
  // dropped a slow term may rise in a cycle in which the state did not
  // move, the wake bit is then one cycle behind it, and completeness in
  // THAT cycle is exactly what the one cycle costs. T1 is therefore
  // asserted only where A2 holds, and T2 -- which needs neither -- is
  // what carries the fault case.
  // -------------------------------------------------------------------
`ifndef NO_A2
  always @(*) if (rst_ni) assert (!changed_i || en_new);
`endif

  // -------------------------------------------------------------------
  // T2 -- AND NOTHING FROZEN IS LOST, ONLY DELAYED BY ONE CYCLE.
  //
  // If a slow term is true in ANY cycle, the block is clocked at the
  // edge that ends the next one.  T2 uses neither A1 nor A2, which is
  // exactly why it covers the case those two do not: an upset that
  // raises a fault line inside a block whose clock is stopped.  The
  // fault line is a function of registers that are not moving, so it
  // stays up; T2 says one cycle later the clock is running; and a block
  // that is clocked with the line still up records it.
  //
  // THIS IS THE PROPERTY THAT REPLACES `|sticky_ev`'s COMBINATIONAL
  // PLACE IN THE ENABLE, and it is a bound rather than a hope: one
  // cycle, not eventually.
  // -------------------------------------------------------------------
  always @(posedge clk_i)
    if (f_past_valid && $past(rst_ni) && rst_ni && $past(slow_i))
      assert (en_new);

  // -------------------------------------------------------------------
  // Vacuity.  docs/09 section B.1 makes an assert set with unreachable
  // behaviour a red result, and T1 is satisfied by an enable that is the
  // constant 1 -- a proof that a clock gate nobody built is safe.  So
  // the three states the theorem is about are covered explicitly.
  // -------------------------------------------------------------------
  always @(*) if (rst_ni) cover (!en_new);                 // W1: it shuts
  always @(posedge clk_i)                                  // W2: it shuts
    if (f_past_valid && $past(rst_ni) && rst_ni)           // for a while
      cover (!en_new && !$past(en_new));
  always @(*) if (rst_ni) cover (changed_i && !slow_i);    // W3: fast only

  // W4 is the FAULT, and it is reachable only in the `upset` tasks --
  // which is the cover that says what A2 means. A slow term rises while
  // the gate is shut and with no fast term anywhere near it, and one
  // cycle later the clock is running. Under A2 this is UNREACHABLE, and
  // that is the statement that a fault-free machine never pays the
  // cycle: docs/77 section 8 measures exactly that, 401,274 of 415,345
  // cycles gated in both builds, to the cycle.
`ifdef NO_A2
  always @(posedge clk_i)
    if (f_past_valid && $past(rst_ni) && rst_ni)
      cover (!$past(en_new) && $past(slow_i) && en_new && !fast_i);
`endif
