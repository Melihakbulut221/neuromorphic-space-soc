// Formal properties for the watchdog's protected word: three
// soc_tmr_bank replicas under one tmr_voter, the composition
// hw/soc/rtl/soc_wdog.v builds in its `g_prot_tmr` generate block.
// SymbiYosys harness: hw/soc/formal/soc_wdog_tmr.sby.
//
// WHY THIS IS A SEPARATE JOB FROM soc_wdog.sby
//
// soc_wdog.sby elaborates the whole watchdog INCLUDING this
// composition, and every property in soc_wdog_props.v is therefore
// already proved over the voted state. That is a regression statement:
// it says the hardening did not change the policy. It is not a
// redundancy statement, and it cannot be one, because soc_wdog has no
// port through which a fault can be injected -- so in that job the
// three replicas are always in agreement and the voter is proved to be
// a wire.
//
// This job adds the only thing that makes a TMR domain a TMR domain: a
// fault model.
//
// WHY THIS IS WORTH A PROOF RATHER THAN A TEST
//
// The failure it catches is silent in the one direction that matters.
// Suppose replica C's storage transform did not round-trip -- a wrong
// rotation in mix_dec, a half-width split that loses a bit, a polarity
// applied on one side only. Then C presents a value the other two do
// not, the voter masks it, and every functional test, every proof in
// soc_wdog.sby and the whole-SoC simulation still pass. What has
// happened is that the watchdog's triple redundancy has quietly become
// a duplex with a permanently wrong third rail: the NEXT upset, in A or
// in B, is no longer masked. The fault-tolerance claim is gone and
// nothing observable has changed. That is exactly the argument
// formal/tmr_voter_cfg_props.v makes for the pilot's configuration
// domain, and soc_tmr_bank is a DIFFERENT module -- no per-bit write
// enable, a different width, and MIX on two replicas rather than one --
// so none of that proof carries over.
//
// WHAT THIS HARNESS COPIES FROM soc_wdog.v, STATED PLAINLY
//
// soc_wdog.v does have an `ifdef FORMAL hook, but a fault model needs
// free inputs at the VOTER, and adding them to the design under an
// `ifdef would put simulation-invisible wiring into the block this
// whole document is about protecting. The composition is rebuilt here
// instead, and three things are therefore copied rather than proven:
// the three POL masks, which replicas carry MIX, and the reset image.
// `make -C hw/soc/formal wdog_tmr_params` reads the masks and the MIX
// assignments back out of hw/soc/rtl/soc_wdog.v and fails if any of
// them has moved; it runs first in the `wdogtmr` target, so the copy
// cannot drift silently.
//
// The WIDTH is deliberately NOT copied. soc_wdog computes PROT_W from
// its own field layout, and reproducing that arithmetic here would be
// copying the thing most likely to change. W is a parameter and the job
// runs at four values instead: 22 (what soc_wdog builds today), 4 (the
// narrowest the MIX guard allows, where the LO/HI split is 2/2 and the
// layer-2 rotation modulus is small enough that an off-by-one in it has
// nowhere to hide), 21 (odd, so LO != HI) and 5 (odd and narrow).
//
// PROVEN (mode prove, k-induction)
//   T1  every replica presents the reference word. f_ref is a plain
//       register written unconditionally from d, which is the semantics
//       soc_wdog.v relies on for its scrub, and it is NOT read out of
//       any bank. qa, qb and qc each equal it at all times. T1 fails if
//       mix_enc and mix_dec are not inverses, if the polarity is
//       applied on one side only, or if the reset image is stored
//       unencoded.
//   T2  and therefore the three replicas agree with each other. Stated
//       separately from T1 because it is the redundancy claim itself:
//       three banks that disagree in the absence of a fault are not a
//       TMR domain, whatever the voter downstream reports.
//   T3  MASKING. Under a fault free in every bit and every cycle,
//       restricted only to one replica at a time -- which is all a
//       bitwise majority claims -- the voted word is still the
//       reference. The fault may move between replicas from one cycle
//       to the next and may corrupt any subset of one replica's bits,
//       which is wider than the single-bit deposits
//       hw/soc/tb/cocotb/test_soc_wdog_fi.py can make.
//   T4  and the disagreement is reported exactly, both directions.
//       soc_wdog.v counts prot_mismatch into WDOGSTAT.TMRCNT, and a
//       flag that also fired on clean cycles would make that count a
//       fiction.
//   T5  the fault-free case on its own, because that is the one the
//       chip runs in.
//   T6  the scrub. One cycle after a fault stops, the replicas agree
//       again -- which is the property the unconditional write exists
//       for and the one that bounds the exposure window to a single
//       cycle. A bank that held its value would satisfy T1 to T5 and
//       fail this.
//
// NOT IN SCOPE, so this file cannot be read as more than it is:
//   * The next-value logic. What soc_wdog.v computes into prot_n is
//     soc_wdog.sby's business, and d is free here.
//   * Two faulty replicas. Nothing about a bitwise majority over three
//     claims anything there, and T3's assumption says so out loud.
//   * The anti-merge argument. POL and MIX exist so that yosys cannot
//     hash the three banks into one, and every property here stays true
//     of a design in which that happened -- setting MIX to 0 on both
//     mixed replicas keeps this whole file passing while destroying the
//     defence. That is sw/tests/test_soc_synthesis_guards.py's job and
//     the two are not substitutes.
//   * Anything about the UNPROTECTED state: counter, reload and pre are
//     outside this composition by decision (soc_wdog.v, W6).
`default_nettype none

module soc_wdog_tmr_props #(
    // 22 is PROT_W at soc_wdog.v's default parameters. It is a
    // parameter and not a copy: see the header.
    parameter integer W       = 22,
    parameter [63:0]  RST_VAL = 64'd0,
    // The three masks soc_wdog.v declares. Guarded against drift by
    // `make -C hw/soc/formal wdog_tmr_params`.
    parameter [63:0]  POL_A   = 64'h0000000000000000,
    parameter [63:0]  POL_B   = 64'h5555555555555555,
    parameter [63:0]  POL_C   = 64'hAAAAAAAAAAAAAAAA
) (
    input wire clk,
    input wire rst_n
);

    // The next value, free every cycle and over every bit. soc_wdog.v
    // drives it from prot_n; here it is unconstrained, so the proof
    // covers every word that logic could ever produce and every one it
    // could not.
    (* anyseq *) reg [W-1:0] d;

    wire [W-1:0] qa, qb, qc;

    soc_tmr_bank #(.W(W), .RST_VAL(RST_VAL), .POL(POL_A), .MIX(0))
        u_prot_a (.clk_i(clk), .rst_ni(rst_n), .d_i(d), .q_o(qa));
    soc_tmr_bank #(.W(W), .RST_VAL(RST_VAL), .POL(POL_B), .MIX(1))
        u_prot_b (.clk_i(clk), .rst_ni(rst_n), .d_i(d), .q_o(qb));
    soc_tmr_bank #(.W(W), .RST_VAL(RST_VAL), .POL(POL_C), .MIX(1))
        u_prot_c (.clk_i(clk), .rst_ni(rst_n), .d_i(d), .q_o(qc));

    // -----------------------------------------------------------------
    // The fault model
    // -----------------------------------------------------------------
    // One free vector per replica, XORed in on the way to the voter,
    // the same shape hw/rtl/pilot_top.v uses on its configuration
    // replicas and formal/tmr_voter_cfg_props.v proves against. Free
    // every cycle and over every bit, so this covers a single-cycle
    // strike, a replica stuck wrong indefinitely, and a fault that
    // moves between replicas from one cycle to the next.
    //
    // Injecting at the bank's OUTPUT rather than at its stored bits is
    // a superset here and not a weakening: the bank takes no feedback
    // from the vote -- soc_wdog.v's next-value logic does, but that is
    // outside this composition and d is free -- so a corrupted output
    // covers a corrupted stored bit and additionally covers corruption
    // a real upset could not produce.
    (* anyseq *) reg [W-1:0] inj_a;
    (* anyseq *) reg [W-1:0] inj_b;
    (* anyseq *) reg [W-1:0] inj_c;

    wire f_bad_a = |inj_a;
    wire f_bad_b = |inj_b;
    wire f_bad_c = |inj_c;

    always @(*) begin
        assume (!(f_bad_a && f_bad_b));
        assume (!(f_bad_a && f_bad_c));
        assume (!(f_bad_b && f_bad_c));
    end

    wire f_faulty = f_bad_a || f_bad_b || f_bad_c;

    wire [W-1:0] prot;
    wire         prot_mismatch;

    tmr_voter #(.WIDTH(W)) u_prot_vote (
        .in_a     (qa ^ inj_a),
        .in_b     (qb ^ inj_b),
        .in_c     (qc ^ inj_c),
        .out      (prot),
        .mismatch (prot_mismatch)
    );

    // -----------------------------------------------------------------
    // The reference: the word soc_wdog.v asked to store, not the word
    // any bank stores
    // -----------------------------------------------------------------
    reg [W-1:0] f_ref;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) f_ref <= RST_VAL[W-1:0];
        else        f_ref <= d;
    end

    // Start in reset so the induction base matches hardware bring-up.
    // rst_n is free afterwards, so the proof also covers a power-on
    // reset asserted in the middle of everything else.
    initial assume (!rst_n);

    always @(posedge clk) begin
        // T1: every replica round-trips its storage transform.
        assert (qa == f_ref);
        assert (qb == f_ref);
        assert (qc == f_ref);

        // T2: the redundancy is real.
        assert (qa == qb);
        assert (qa == qc);

        // T3: masking.
        assert (prot == f_ref);

        // T4: exact reporting, both directions.
        assert (prot_mismatch == f_faulty);

        // T5: the fault-free case on its own.
        if (!f_faulty) begin
            assert (!prot_mismatch);
            assert (prot == qa);
        end
    end

    // T6: the scrub. One cycle after the fault stops, the replicas
    // agree again -- trivially here, because T1 already says each of
    // them always equals the reference, and that is exactly the point:
    // the bank has no way to remember a corruption because it is
    // written unconditionally. Stated on its own so that a future
    // change to soc_tmr_bank that reintroduced a write enable would
    // fail a property whose NAME says what was lost, rather than
    // failing T1 for a reason a reader has to reconstruct.
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk)
        f_past_valid <= 1'b1;

    always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
        assert (qa == qb && qb == qc);
    end

    // -----------------------------------------------------------------
    // Non-vacuity (docs/09 section B.1 vacuity rule). The second and
    // third of these are what would make T3 an empty statement.
    // -----------------------------------------------------------------
    always @(posedge clk) if (f_past_valid && rst_n) begin
        // The word holds something that is not the reset image, so T1
        // is not proven over a constant.
        cover (f_ref != RST_VAL[W-1:0]);
        // Each replica is corrupted in turn and masked, with the word
        // holding a real value at the time.
        cover (f_bad_a && prot == f_ref && f_ref != {W{1'b0}});
        cover (f_bad_b && prot == f_ref && f_ref != {W{1'b0}});
        cover (f_bad_c && prot == f_ref && f_ref != {W{1'b0}});
        // A fault that MOVES between replicas, which is what makes the
        // free-every-cycle model wider than a single deposit.
        cover (f_bad_a && $past(f_bad_b) && prot == f_ref);
        // And the scrub: corrupted last cycle, agreeing this cycle.
        cover ($past(f_faulty) && !f_faulty && f_ref != {W{1'b0}});
    end

endmodule

`default_nettype wire
