// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Triple modular redundancy voter: bitwise majority over three replicas,
// with a per-word disagreement flag for the fault counters.
//
// Role in the design: docs/09-formal-verification-plan.md target #4 (the
// masking theorem is the fault-tolerance headline result) and
// docs/10-npu-mvp-spec.md section 11.4, which puts the scheduler and
// sequencer FSMs plus the configuration register set in the core's TMR
// domain. docs/08 section 2.3 (fault-visibility convention) is the reason
// the flag exists at all: every masking event must be countable, so a
// silently-repaired upset still shows up in telemetry.
//
// Contract:
//   - out is the bitwise majority of in_a, in_b, in_c: bit k of out is 1
//     when at least two of the three replicas have bit k set. Any single
//     faulty replica is therefore masked, on every bit, with no
//     assumption about which replica is faulty or how many bits it got
//     wrong.
//   - mismatch is asserted exactly when the three inputs are not all
//     equal - one flag per voted word, not per bit, because that is what a
//     fault counter needs (one event = one voted word). It is a
//     combinational level output; the instantiating block qualifies it
//     with its own valid/strobe before counting.
//   - Purely combinational, no state, no clock, so a voter never adds a
//     failure mode of its own.
//
// Not in this module by design: replica resynchronization (the scrub or
// reload path that restores the faulty replica after masking) belongs to
// the protected block, which alone knows how to restore its state.
//
// Verified in hw/tb/test_tmr_voter.py against an independent Python
// majority model, and proven exhaustively in formal/tmr_voter.sby.
`default_nettype none

module tmr_voter #(
    parameter WIDTH = 1  // voted word width, >= 1
) (
    input  wire [WIDTH-1:0] in_a,
    input  wire [WIDTH-1:0] in_b,
    input  wire [WIDTH-1:0] in_c,
    output wire [WIDTH-1:0] out,
    output wire             mismatch
);

    // Elaboration guard, aer_fifo house style: WIDTH < 1 would degenerate
    // the [WIDTH-1:0] part-selects, so it must fail loudly at elaboration.
    generate
        if (WIDTH < 1) begin : g_bad_width
            ERROR_tmr_voter_WIDTH_must_be_ge_1 guard ();
        end
    endgenerate

    // Bitwise majority: at least two of three.
    assign out = (in_a & in_b) | (in_a & in_c) | (in_b & in_c);

    // Not-all-equal. (a^b) | (a^c) is zero exactly when b == a and c == a,
    // which also covers b != c, so no third term is needed.
    assign mismatch = |((in_a ^ in_b) | (in_a ^ in_c));

endmodule

`default_nettype wire
