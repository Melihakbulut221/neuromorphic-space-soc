// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// The wakefulness-qualified grant, as a THEOREM about the transformation
// rather than about one block.  docs/77 section 11 priced it and section
// 18 builds it behind soc_npu.v's WAKE_GNT; this file is what is proved
// of it, in the same shape as clkgate_wake.v and for the same reason.
//
// WHY THIS FILE IS AN ABSTRACTION AND NOT `soc_npu.v`.  clkgate_wake.v's
// header says it at length and nothing has changed: `soc_npu`
// instantiates the frozen die, so "no register in `soc_npu` moves while
// the enable is low" cannot be proved here.  What CAN be proved is what
// the change does to the handshake and to the enable, and that is all
// the property set below claims.
//
// WHAT CHANGES.  docs/77's enable is `fast | wake_q | hold`, with `fast`
// the two transient inputs `req_i | psel_i` -- combinational, because a
// grant given in the cycle a request arrives has to be clocked in at the
// edge that ends it.  WAKE_GNT removes `fast` from the enable and pays
// for it at the handshake instead: the grant and the APB completion are
// qualified by `awake = wake_q | hold`, so the block never accepts
// anything in a cycle it is not clocked in.  `wake_q` is still set by
// `fast | slow`, so a request that finds the block asleep sets the wake
// bit at the end of its own cycle and is granted in the next.
//
// The abstraction holds `wake_q` exactly as soc_npu.v holds it and
// `wake_hold` as a bounded counter with soc_npu.v's reload rule, because
// the hold counter is now IN the enable's cone rather than beside it and
// the theorem has to be about the enable that is built.  `req_i` is a
// free input under a rule-1 assumption (a request is held until it is
// granted); `idle_i` is a free input standing for `win_state == W_IDLE
// && (!win_out || rvalid_o)`, the block's own readiness, which the
// grant was already qualified by.
//
// What is proved, by k-induction (clkgate_wake_gnt_props.v):
//
//   G1  No grant and no APB completion in a cycle the block is not
//       clocked in: `gnt -> en` and `pready -> en`.  This is the
//       property that lets `req_i` and `psel_i` leave the enable, and it
//       is by construction -- both are qualified by the same `awake`
//       that IS the enable.
//
//   G2  The enable reads no input.  `en` is a function of `wake_q` and
//       `wake_hold` alone, which is stated as: whatever the inputs do in
//       a cycle, `en` in that cycle is what the previous edge left.
//       This is the clock-gating check's closure, as a theorem: the
//       GATE pin's cone is four flip-flops.  On the design it is
//       discharged by sw/tests/test_soc_clkgate_guards.py's cone census
//       of `clk_en_o` at WAKE_GNT = 1.
//
//   G3  The cost is bounded at ONE cycle: a request present in a cycle
//       has the block clocked at the end of the next one, and a request
//       held across a refusal is granted in the cycle after it, if the
//       block is idle then.  Nothing is lost and nothing waits longer.
//
//   T2  clkgate_wake.v's T2, unchanged: a frozen term true in any cycle
//       has the block clocked at the end of the next.  The fault lines'
//       guarantee survives the removal of the fast half.
//
// NOT proved here, as before: that the enable is complete over the
// die's state (docs/76 section 10), and anything about what the block
// computes.
module clkgate_wake_gnt #(
    parameter integer HOLD_CYCLES = 4
) (
    input wire clk_i,
    input wire rst_ni,
    input wire req_i,       // the fabric request, held until granted
    input wire psel_i,      // the APB select
    input wire penable_i,   // the APB access phase
    input wire idle_i,      // the block's own readiness to grant
    input wire slow_i       // slow(state): the frozen terms
);

  localparam integer HOLD_W = (HOLD_CYCLES < 2)   ? 1 :
                              (HOLD_CYCLES < 4)   ? 2 :
                              (HOLD_CYCLES < 8)   ? 3 :
                              (HOLD_CYCLES < 16)  ? 4 :
                              (HOLD_CYCLES < 32)  ? 5 : 6;
  localparam [31:0]       HOLD_32   = HOLD_CYCLES;
  localparam [HOLD_W-1:0] HOLD_LOAD = HOLD_32[HOLD_W-1:0];
  localparam [HOLD_W-1:0] HOLD_ZERO = {HOLD_W{1'b0}};
  localparam [HOLD_W-1:0] HOLD_ONE  = {{(HOLD_W-1){1'b0}}, 1'b1};

  wire fast    = req_i | psel_i;
  wire npu_act = fast | slow_i;

  // The wake bit, on the ungated clock, exactly as soc_npu.v holds it.
  reg wake_q;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) wake_q <= 1'b1;
    else         wake_q <= npu_act;
  end

  // The registered half, and the enable under WAKE_GNT is exactly it.
  reg [HOLD_W-1:0] wake_hold;
  wire awake = wake_q || (wake_hold != HOLD_ZERO);
  wire en    = awake;

  // soc_npu.v's reload rule at WAKE_GNT = 1: accepted activity only.
  // In silicon the counter is on the gated clock and this is what the
  // gate makes of `npu_act`; here it is written out, so that the model
  // is the bare block and the gated one at once.
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni)                     wake_hold <= HOLD_LOAD;
    else if (npu_act && awake)       wake_hold <= HOLD_LOAD;
    else if (wake_hold != HOLD_ZERO) wake_hold <= wake_hold - HOLD_ONE;
  end

  // The handshake, qualified.
  wire gnt    = req_i && awake && idle_i;
  wire pready = awake;
  wire apb_done = psel_i && penable_i && pready;

`ifdef FORMAL
`include "clkgate_wake_gnt_props.v"
`endif

endmodule
