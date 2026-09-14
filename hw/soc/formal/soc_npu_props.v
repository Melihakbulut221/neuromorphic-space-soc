// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0
// The event engine's one-line invariant, proved over every reachable state.
//
// Included into hw/soc/rtl/soc_npu.v under `ifdef FORMAL, the arrangement
// soc_npu_ser.v and every fabric block use, so that the FSM's signals are
// in scope natively -- aer_in_stb, ev_state and E_PIN_S are all declared
// at module level (lines ~1390, ~1472, ~1465), outside every generate
// block, which is what makes this include safe. (regfile_scrub_props.v
// learned the other way: a hierarchical reference from an outside
// wrapper into a generate scope silently declares a fresh free wire.)
//
// WHY THIS FILE EXISTS. soc_npu.v is the largest RTL file in the SoC and
// the block the accelerator lives in, and it carried no proof. docs/55
// section 9.3 named the gap and declined to close it; docs/56 section 9.4
// declined a second time and said so: "H5's invariant --
// aer_in_stb == (ev_state == E_PIN_S) -- is one line and is the entire
// basis of the mechanism, and it is checked here by one cocotb test and
// one textual guard rather than over all reachable states." This is the
// check over all reachable states.
//
// H5   aer_in_stb is exactly the E_PIN_S state. Not implied by it, not
//      implying it: equal. The strobe that presents an event to the node
//      is asserted in that one FSM state and in no other, so an upset
//      that moves ev_state moves the strobe with it and an upset that
//      flips aer_in_stb alone is a mismatch the equality exposes. The
//      RTL computes the same term at line ~1842 as aer_stb_state; H5
//      says the register and the decode never disagree.
//
// NOT proved here: liveness (that E_PIN_S is reached), which the cover
// below only shows is reachable; and anything about the fetch, decide
// or dispatch paths, which have their own sections in docs/56 and are
// the next properties to add once this one closes.

`ifdef FORMAL
  // Reset discipline: held low for the first cycle, then free. Without
  // this, bmc starts from an arbitrary register state -- the first run
  // did, and its counterexample was ev_state=8 with aer_in_stb=1 at
  // step 0, a state no reset ever produces. The assertion is guarded on
  // rst_ni so that a free reset later in the trace is simply skipped.
  initial assume (!rst_ni);
  reg f_npu_past_valid = 1'b0;
  always @(posedge clk_i) f_npu_past_valid <= 1'b1;
  always @(*) if (!f_npu_past_valid) assume (!rst_ni);

  // ---- H5: the strobe IS the state -------------------------------------
  always @(posedge clk_i)
    if (rst_ni && f_npu_past_valid)
      assert (aer_in_stb == (ev_state == E_PIN_S));

  // ---- and the state is reachable, so H5 is not vacuous ----------------
  always @(posedge clk_i)
    if (rst_ni && f_npu_past_valid)
      cover (ev_state == E_PIN_S);
`endif
