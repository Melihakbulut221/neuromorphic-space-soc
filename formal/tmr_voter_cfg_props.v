// Formal properties for the pilot's configuration TMR domain: three
// pilot_cfg_bank replicas under one tmr_voter, the composition
// hw/rtl/pilot_top.v builds at lines 1484-1512. SymbiYosys harness:
// formal/tmr_voter_cfg.sby, driver formal/tmr_voter_cfg.mk.
//
// WHICH ACCEPTANCE CRITERION THIS DISCHARGES
//
// docs/09-formal-verification-plan.md target #6 lists four clauses for
// the register file, three of which formal/npu_regbank_props.v proves.
// The fourth is "TMR'd CSRs vote correctly (reuse #4)", and the status
// column said in as many words that nothing proved it:
//
//   "hw/rtl/pilot_top.v votes 55 configuration bits through the proven
//    voter, but no property in this repository binds the register bank
//    to the voter."
//
// It also discharges the half of target #4a's acceptance criterion that
// formal/tmr_voter_props.v cannot reach on its own -- "the masking
// theorem ... is reported per protected block". The voter proof is about
// a combinational majority over three arbitrary words. This one is about
// the only protected block the pilot actually has: three banks that
// STORE the configuration, each through a different storage transform,
// with the voter on top.
//
// WHY THIS IS WORTH A PROOF RATHER THAN A TEST
//
// The failure this catches is silent by construction, and it is silent
// in the one direction that matters. Suppose replica C's storage
// transform did not round-trip -- a wrong rotation in cfg_dec, a
// half-width split that loses a bit, a partial write that re-encodes the
// wrong word. Then C presents a value the other two do not. The voter
// masks it, so cfg_v is still right, so every functional test, every
// golden-model lockstep and every gate-level run still passes. What has
// happened is that the chip's triple redundancy has quietly become a
// duplex with a permanently wrong third rail: the NEXT upset, in A or in
// B, is no longer masked, because two of three replicas now disagree
// with each other and the majority can land on the corrupted value. The
// fault-tolerance claim is gone and nothing observable has changed.
//
// The same argument applies to the read-modify-write in the MIX bank and
// is why that path gets its own attention below. A partial write there
// decodes the whole stored word, substitutes the enabled bits and
// re-encodes; the polarity banks just write the enabled bits. If the two
// disagree on what a partial write leaves behind, the replicas diverge
// permanently on the untouched bits, again with the voter hiding it.
//
// This is not a hypothetical class for this project. hw/rtl/aer_fifo.v
// carries the same POL/MIX construction on its pointer replicas, and
// there the round-trip is already proven -- as a side effect of P7a in
// formal/aer_fifo_props.v, which asserts the three decoded pointers are
// always equal. pilot_cfg_bank is a DIFFERENT module with a different
// width (55 against 7, so a different LO/HI split and a different
// rotation modulus) and a per-bit write port the pointer bank does not
// have. None of the pointer proof carries over to it.
//
// WHAT THIS HARNESS COPIES FROM pilot_top.v, STATED PLAINLY
//
// hw/rtl/pilot_top.v has no `ifdef FORMAL include hook and the pilot is
// frozen, so the composition is rebuilt here out of the same two RTL
// modules rather than bound into the instance. Three things are
// therefore copied and not proven: the parameter W, the three POL masks,
// and which replica carries MIX = 1. formal/tmr_voter_cfg.mk has a
// `tmr_cfg_params` target that greps hw/rtl/pilot_top.v for those exact
// literals and fails if any of them has moved, and it runs first in
// `tmr_cfg_all`, so the copy cannot drift silently. What is NOT copied
// is the reset image: CFG_RST_VAL is assembled inside pilot_top from the
// generated RST_* constants, and reproducing that assembly here would be
// copying the very thing a proof should not assume. RST_VAL is a
// parameter of this harness instead, and the job runs at three of them
// (0, all ones, and an alternating pattern), so the reset property is
// "the banks reset to the image they are given" -- which is the module's
// claim. That the image pilot_top gives them is the right one is
// npu_regbank P1's business and the elaboration guards', not this file's.
//
// PROVEN (mode prove, k-induction)
//   G1  every replica presents the reference value. f_ref is a plain
//       register with the per-bit write semantics the register map
//       specifies -- written where wr_en is high, held where it is not --
//       and it is NOT read out of any bank. qa, qb and qc each equal it
//       at all times. This is the round-trip property: it fails if
//       cfg_enc/cfg_dec are not inverses, if the polarity is applied on
//       one side only, if the reset image is stored unencoded, or if a
//       partial write in the MIX bank re-encodes the wrong word.
//   G2  and therefore the three replicas agree with each other. Stated
//       separately from G1 because it is the redundancy claim itself:
//       three banks that disagree in the absence of a fault are not a
//       TMR domain, whatever the voter downstream reports.
//   G3  MASKING, the per-block form of target #4a. Under a fault free in
//       every bit and every cycle, restricted only to one replica at a
//       time -- which is all a bitwise majority claims -- the voted
//       configuration word is still the reference value. The fault is
//       modelled at the voter input exactly as hw/rtl/pilot_top.v's own
//       tmr_inj hook does, and it is wider than that hook: tmr_inj can
//       corrupt one bit of one replica, this corrupts any subset of one
//       replica's 55 bits and may move to another replica next cycle.
//   G4  and the disagreement is reported exactly: cfg_mismatch is high
//       if and only if a replica is actually being corrupted this cycle.
//       Both directions, for the same reason P8 gives in
//       formal/aer_fifo_props.v -- the pilot counts this flag into
//       CNT_TMR, and a flag that also fired on clean cycles would make
//       that count a fiction.
//   G5  no fault, no alarm, and the voted word is the stored word: the
//       fault-free case is not merely the special case of G3, it is the
//       one the chip runs in, so it is asserted on its own.
//
// NOT IN SCOPE, so this file cannot be read as more than it is: the
// register decode that produces cfg_wr_en / cfg_wr_d (that is target #6
// proper, formal/npu_regbank_props.v P2), the field packing at the T_*
// offsets, the reset image assembly, and replica RESYNCHRONIZATION --
// docs/09 target #4b. This domain has no resync path: the banks hold
// their own state and are restored by a host rewrite, which is what
// hw/rtl/pilot_top.v says. The queue pointer domain does have one and
// formal/aer_fifo.sby's resync task proves it.
`default_nettype none

module tmr_voter_cfg_props #(
    // The silicon parameters of hw/rtl/pilot_top.v's configuration TMR
    // domain. Guarded against drift by `make -C formal -f tmr_voter_cfg.mk
    // tmr_cfg_params`, which reads them back out of the RTL.
    parameter integer W       = 55,
    parameter [63:0]  RST_VAL = 64'd0,
    parameter [63:0]  POL_A   = 64'h0000000000000000,
    parameter [63:0]  POL_B   = 64'h007FFFFFFFFFFFFF,
    parameter [63:0]  POL_C   = 64'h002AAAAAAAAAAAAA
) (
    input wire clk,
    input wire rst_n
);

    // The write port, free every cycle and over every bit. pilot_top
    // drives it from the register decode; here it is unconstrained, so
    // the proof covers every write pattern the decode could ever produce
    // and every one it could not.
    (* anyseq *) reg [W-1:0] wr_en;
    (* anyseq *) reg [W-1:0] wr_d;

    wire [W-1:0] qa, qb, qc;

    pilot_cfg_bank #(.W(W), .RST_VAL(RST_VAL), .POL(POL_A))
        u_cfg_a (.clk(clk), .rst_n(rst_n), .wr_en(wr_en), .wr_d(wr_d),
                 .q(qa));

    pilot_cfg_bank #(.W(W), .RST_VAL(RST_VAL), .POL(POL_B))
        u_cfg_b (.clk(clk), .rst_n(rst_n), .wr_en(wr_en), .wr_d(wr_d),
                 .q(qb));

    // MIX = 1 on exactly one replica, as in pilot_top.
    pilot_cfg_bank #(.W(W), .RST_VAL(RST_VAL), .POL(POL_C), .MIX(1))
        u_cfg_c (.clk(clk), .rst_n(rst_n), .wr_en(wr_en), .wr_d(wr_d),
                 .q(qc));

    // -----------------------------------------------------------------
    // The fault model
    // -----------------------------------------------------------------
    // One free vector per replica, XORed in on the way to the voter, the
    // same shape hw/rtl/pilot_top.v uses (inj_a / inj_b / inj_c) and the
    // same shape hw/rtl/aer_fifo.v uses on its pointer replicas. Free
    // every cycle and over every bit, so the proof covers a single-cycle
    // strike, a replica stuck wrong indefinitely, and a fault that moves
    // between replicas from one cycle to the next. The only restriction
    // is at most one faulty replica at a time, which is exactly what a
    // bitwise majority over three corrects and no more.
    //
    // Injecting at the bank's output rather than at its stored bits is a
    // SUPERSET here, not a weakening: the bank has no feedback from the
    // vote -- that is precisely why this domain has no resync path -- so
    // a corrupted output covers a corrupted stored bit, and a vector
    // that is free every cycle additionally covers stored corruption
    // that a real upset could not produce.
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

    wire [W-1:0] cfg_v;
    wire         cfg_mismatch;

    tmr_voter #(.WIDTH(W)) u_cfg_vote (
        .in_a     (qa ^ inj_a),
        .in_b     (qb ^ inj_b),
        .in_c     (qc ^ inj_c),
        .out      (cfg_v),
        .mismatch (cfg_mismatch)
    );

    // -----------------------------------------------------------------
    // The reference: the configuration word as the register map defines
    // it, not as any bank stores it
    // -----------------------------------------------------------------
    reg [W-1:0] f_ref;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) f_ref <= RST_VAL[W-1:0];
        else        f_ref <= (wr_d & wr_en) | (f_ref & ~wr_en);
    end

    // Start in reset so the induction base matches hardware bring-up.
    // rst_n is free afterwards, so the proof also covers a reset asserted
    // in the middle of a configuration write.
    initial assume (!rst_n);

    always @(posedge clk) begin
        // G1: every replica round-trips its storage transform.
        assert (qa == f_ref);
        assert (qb == f_ref);
        assert (qc == f_ref);

        // G2: the redundancy is real -- no replica is silently the odd
        // one out in the absence of a fault.
        assert (qa == qb);
        assert (qa == qc);

        // G3: masking. The voted configuration is the reference value
        // whatever the corrupted replica holds.
        assert (cfg_v == f_ref);

        // G4: exact reporting, both directions.
        assert (cfg_mismatch == f_faulty);

        // G5: the fault-free case on its own.
        if (!f_faulty) begin
            assert (!cfg_mismatch);
            assert (cfg_v == qa);
        end
    end

    // -----------------------------------------------------------------
    // Non-vacuity (docs/09 section B.1 vacuity rule). Two things have to
    // be shown reachable, and the second is the one that would make G3
    // an empty statement: a genuinely corrupted replica.
    // -----------------------------------------------------------------
    reg f_past_valid;
    initial f_past_valid = 1'b0;
    always @(posedge clk)
        f_past_valid <= 1'b1;

    always @(posedge clk) if (f_past_valid && rst_n) begin
        // The configuration is written and holds a value that is not the
        // reset image, so G1 is not proven over a constant.
        cover (f_ref != RST_VAL[W-1:0]);
        // A PARTIAL write: some bits enabled, some not, and the word is
        // not uniform afterwards. This is the pattern the MIX bank's
        // read-modify-write exists for and the one a polarity-only bank
        // gets for free.
        cover ($past(wr_en) != {W{1'b0}} && $past(wr_en) != {W{1'b1}}
               && f_ref != {W{1'b0}} && f_ref != {W{1'b1}});
        // Each replica is corrupted in turn and masked, with the
        // configuration holding a real value at the time.
        cover (f_bad_a && cfg_v == f_ref && f_ref != {W{1'b0}});
        cover (f_bad_b && cfg_v == f_ref && f_ref != {W{1'b0}});
        cover (f_bad_c && cfg_v == f_ref && f_ref != {W{1'b0}});
        // The MIX replica corrupted in more than one bit at once -- the
        // case the bank header calls out, where one upset inside the
        // mixed replica widens to two or three wrong bits at q.
        cover (f_bad_c && (inj_c & (inj_c - 1'b1)) != {W{1'b0}}
               && cfg_v == f_ref);
        // A fault arriving while a write lands.
        cover (f_faulty && wr_en != {W{1'b0}} && cfg_v == f_ref);
        // And the alarm reaches the pilot's counter.
        cover (cfg_mismatch);
    end

endmodule

`default_nettype wire
