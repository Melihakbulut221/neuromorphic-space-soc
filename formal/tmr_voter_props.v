// Formal properties for the TMR voter (SymbiYosys harness,
// formal/tmr_voter.sby). Acceptance criteria from
// docs/09-formal-verification-plan.md target #4, "TMR voters + resync
// path", quoted in full so the scope of this file is unambiguous:
//
//   "Output = majority(a,b,c) always (S); any single corrupted replica
//    never changes output (S, symbolic fault via $anyseq on one replica);
//    after fault removal, replicas re-converge within N cycles (L as
//    bounded safety) | BMC depth 1 for voter; IND with one-symbolic-fault
//    assumption for masking; bounded-response counter for resync | Full
//    proofs; the masking theorem is the chip's 'integrity' headline result
//    and is reported per protected block."
//
// SCOPE. This file proves the voter clauses only: majority and masking,
// exhaustively, over three arbitrary replica words. It says nothing about
// any particular protected block, and it says nothing about
// re-convergence: hw/rtl/tmr_voter.v deliberately contains no
// resynchronization path (see its header - restoring a faulty replica
// belongs to the protected block, which alone knows how to restore its
// state).
//
// Where the other two clauses of target #4 are proven, as of 2026-08-31:
//
//   "the masking theorem ... is reported per protected block" -- the
//       pilot has one protected block, the configuration TMR domain of
//       hw/rtl/pilot_top.v, and formal/tmr_voter_cfg.sby proves the
//       masking there over the three banks that actually store the word,
//       each through a different storage transform. That job also proves
//       what this one cannot see: that all three replicas present the
//       configured value in the absence of a fault, which is the property
//       a broken storage transform would take away silently, with this
//       voter faithfully masking the damage.
//
//   #4b, "after fault removal, replicas re-converge within N cycles" --
//       proven for the one domain in the design that has a resync path,
//       the queue pointers of hw/rtl/aer_fifo.v, by the `resync` task of
//       formal/aer_fifo.sby, with N = 1. Until 2026-08-31 this header and
//       formal/ecc.mk both said the clause was proven nowhere and blocked
//       on RTL that did not exist; the RTL did exist, in a file neither of
//       them reads. The configuration domain still has no resync path and
//       #4b remains open there.
//
// Wrapper-module style (docs/09 B.1). The three replica words are
// $anyconst and the voter is combinational, so BMC at depth 1 is a full
// proof over the entire 2^(3*WIDTH) input space at the elaborated width.
// The sby file runs WIDTH = 1, 8 and 32, for both the assertion set and
// the cover set, so the parameterization itself is covered.
//
// A note on the symbolic-fault wording of the target: it asks for a fault
// injected with $anyseq into one replica under induction. The voter has no
// state and every property here is evaluated in the same combinational
// step, so a per-cycle $anyseq fault and a held $anyconst fault reach the
// same set of input vectors - the two are equivalent for this design, not
// a weakening. On the fault itself the properties are wider than the
// target asks: S2 quantifies over ALL values of the third replica, which
// is every fault of every weight and not only single-bit ones, and it does
// so for each of the three replicas in turn.
//
// Proven:
//   S1  bitwise majority, stated independently of the implementation: bit
//       k of out is 1 exactly when the population count of the three
//       replica bits is >= 2. The RTL computes it as a sum of AND terms;
//       the property counts. The two forms are not the same expression, so
//       the proof is not a tautology.
//   S2  masking theorem: whenever two replicas agree, the output is their
//       common value regardless of the third. Stated once per replica, so
//       it covers an arbitrary fault (any number of wrong bits) in any one
//       replica.
//   S3  the disagreement flag is exactly "the three inputs are not all
//       equal" - no false alarms, no missed disagreements.
//   S4  agreement implies transparency: all three equal -> out equals them
//       and mismatch is low.
`default_nettype none

module tmr_voter_props #(
    parameter WIDTH = 8
) (
    input wire clk
);

    (* anyconst *) reg [WIDTH-1:0] f_a;
    (* anyconst *) reg [WIDTH-1:0] f_b;
    (* anyconst *) reg [WIDTH-1:0] f_c;

    wire [WIDTH-1:0] v_out;
    wire             v_mismatch;

    tmr_voter #(.WIDTH(WIDTH)) u_voter (
        .in_a     (f_a),
        .in_b     (f_b),
        .in_c     (f_c),
        .out      (v_out),
        .mismatch (v_mismatch)
    );

    // S1: per-bit majority by population count.
    genvar k;
    generate
        for (k = 0; k < WIDTH; k = k + 1) begin : g_bit
            wire [1:0] votes = {1'b0, f_a[k]} + {1'b0, f_b[k]} + {1'b0, f_c[k]};
            always @(*)
                assert (v_out[k] == (votes >= 2'd2));
        end
    endgenerate

    always @(*) begin
        // S2: masking. Two healthy replicas outvote an arbitrarily
        // corrupted third one, whatever it holds.
        if (f_b == f_c) assert (v_out == f_b);
        if (f_a == f_c) assert (v_out == f_a);
        if (f_a == f_b) assert (v_out == f_a);

        // S3: the disagreement flag is exact.
        assert (v_mismatch == !((f_a == f_b) && (f_b == f_c)));

        // S4: unanimous input is passed through, no alarm.
        if ((f_a == f_b) && (f_b == f_c)) begin
            assert (v_out == f_a);
            assert (!v_mismatch);
        end

        // The output is always one of the replica values on every bit, so
        // the voter can never invent a value no replica produced.
        assert (((v_out ^ f_a) & (v_out ^ f_b) & (v_out ^ f_c)) == {WIDTH{1'b0}});
    end

    // -----------------------------------------------------------------
    // Non-vacuity: masking with a genuinely corrupted replica, unanimity,
    // and a three-way split are all reachable.
    // -----------------------------------------------------------------
    always @(*) begin
        cover (!v_mismatch && v_out == f_a);
        cover (v_mismatch && f_a != f_b && v_out == f_b);   // replica A masked
        cover (v_mismatch && f_b != f_a && v_out == f_a);   // replica B masked
        cover (v_mismatch && f_c != f_a && v_out == f_a);   // replica C masked
        cover (v_out == {WIDTH{1'b0}} && v_mismatch);
        cover (v_out == {WIDTH{1'b1}} && v_mismatch);
    end

    // Three replicas disagreeing pairwise needs at least two bits, so this
    // cover is only stated where it is reachable. formal/tmr_voter.sby runs
    // a cover task at WIDTH 1, 8 and 32, so both arms of this generate are
    // exercised: 6 covers reached at WIDTH = 1, 7 at WIDTH = 8 and 32.
    generate
        if (WIDTH >= 2) begin : g_cover_three_way
            always @(*)
                cover (f_a != f_b && f_b != f_c && f_a != f_c);
        end
    endgenerate

endmodule

`default_nettype wire
