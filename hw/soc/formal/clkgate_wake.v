// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// The registered-wake clock-gate enable, as a THEOREM about the
// transformation rather than about one block.  docs/77 section 6.
//
// WHY THIS FILE IS AN ABSTRACTION AND NOT `soc_npu.v`.
//
// docs/76 section 10 states the limit this work inherits: "F10 is a
// theorem about `soc_bus` and about nothing else.  For `soc_npu` the
// statement is section 6's" -- a measured bit-exact equivalence over two
// workloads.  The reason is structural and has not changed: `soc_npu`
// instantiates `hw/rtl/pilot_top.v`, which `docs/34` freezes for the
// TTIHP26b shuttle, whose 2,152 flip-flops are not this project's to
// abstract and whose own property set lives in `formal/` and may not be
// extended.  A k-induction proof of "no register in `soc_npu` moves
// while the enable is low" would have to quantify over the die's state,
// and replacing the die with a free-input stub makes the statement false
// rather than hard: a stub whose outputs move on their own is a die that
// changes state with its clock stopped.
//
// So docs/77 does what it can prove and says which half is which.  The
// change docs/77 makes to the enable is a TRANSFORMATION with two side
// conditions, and this file is the transformation:
//
//   A1  docs/76's enable is complete.  Whenever the block's state moves
//       at the edge that ends a cycle, `fast | slow` is true in that
//       cycle.  This is the hypothesis, not a result: it is what
//       docs/76 section 6 measured over 5,137 signal paths and 415,345
//       clock edges, and docs/77 re-measures it on the same instrument.
//
//   A2  `slow` is a function of the block's STATE.  If the state did not
//       move at the previous edge, `slow` did not move either.  This is
//       the side condition docs/77 makes machine-checkable:
//       `sw/tests/test_soc_clkgate_guards.py` walks the fan-in cone of
//       `npu_act_slow` cut at every sequential cell and fails if any
//       input port is reachable, and that census is what found
//       `C_INJ_OVF` and moved it to the fast half.
//
// and what is proved from them, by k-induction, is:
//
//   T1  The registered-wake enable `fast | wake` is complete TOO.  The
//       substitution is therefore sound, and F1-F9's transport argument
//       -- a design whose state does not change is a design whose state
//       does not change whether or not it is clocked -- applies to it
//       exactly as docs/76 section 4.2 applies it to F10.
//
//   T2  And nothing frozen is LOST, only delayed by one cycle: if a slow
//       term is true in any cycle at all, the block is clocked at the
//       edge that ends the NEXT cycle.  T2 needs neither A1 nor A2,
//       which is why it holds in the case both of them are about --
//       an upset that raises a fault line inside a block whose clock is
//       stopped.  That is the whole of what `|sticky_ev` is in the
//       enable for, and T2 is the statement that moving it off the
//       combinational path did not cost it.
//
// THE SIGNALS ARE FREE INPUTS ON PURPOSE.  `changed_i` is "the block's
// state differs between this cycle and the next"; `slow_i` and `fast_i`
// are the two halves of the activity predicate.  Nothing here models
// WHAT the block computes, because nothing in T1 or T2 depends on it --
// which is the point of proving the transformation rather than one
// instance of it.
module clkgate_wake (
    input wire clk_i,
    input wire rst_ni,
    input wire fast_i,      // fast(inputs): the transient external terms
    input wire slow_i,      // slow(state):  the terms A2 constrains
    input wire changed_i    // the block's state moves at the edge that
                            // ends this cycle
);

  // The wake bit, on the ungated clock, exactly as soc_npu.v holds it.
  // Reset to 1 so the block is clocked out of reset.
  reg wake_q;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) wake_q <= 1'b1;
    else         wake_q <= fast_i | slow_i;
  end

  wire en_old = fast_i | slow_i;   // docs/76's enable
  wire en_new = fast_i | wake_q;   // docs/77's

`ifdef FORMAL
`include "clkgate_wake_props.v"
`endif

endmodule
