// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Formal properties for the lif_core memory hardening: the two coded
// files, in place, inside the datapath that reads them. SymbiYosys
// harness: formal/lif_mem.sby, driver formal/lif_mem.mk.
//
// This file is textually included inside the lif_core module body under
// `ifdef FORMAL when LIF_MEM_FORMAL is also defined (end of
// hw/rtl/lif_core.v), so it sees vmem, rmem, smem, wmem, wchk, the scan
// index and both decoders directly. It is invisible to Icarus simulation
// and to synthesis. It REPLACES formal/lif_ctrl_props.v rather than
// joining it: the two model different faults and want different starting
// states, and the include in lif_core.v selects one or the other.
//
// Why this job exists, and what it is NOT. formal/lif_mem_codec_props.v
// proves the (26,20) codec correct in isolation, and formal/secded.sby
// already proves the (72,64) codec the same way. Neither says anything
// about whether lif_core USES them correctly -- whether the codeword the
// decoder sees is the one the encoder wrote, whether the datapath
// consumes the corrected value or the raw one, whether a write leaves
// the two halves of a codeword agreeing. Those are the properties here,
// and they are the ones a wrong wiring would break while both codecs
// stayed perfect.
//
// Method. The fault model is the same as the docs/16 campaign's: one
// stored bit, flipped. It is expressed as an assumption on the current
// state -- the codeword the scan is about to read is a clean codeword
// XOR a symbolic error vector -- rather than as a stimulus, because a
// state carrying an injected upset is by construction not reachable from
// reset, which is the same reason formal/lif_ctrl.sby's bmc_safe task
// starts from an illegal FSM encoding. Everything downstream of the two
// decoders is combinational, so a depth-1 BMC over a fully symbolic
// state is exhaustive over this fault model at the chosen geometry.
//
// Proven in the read tasks (mode bmc, depth 1):
//   M1  a single-bit error anywhere in a neuron's 26-bit state codeword
//       -- in V, in R, or in the check field -- leaves the value the
//       datapath reads EQUAL to the value that was stored. Since the
//       spike decision (E4), the saturating update (E3), the leak (E6),
//       the refractory gate (E7), the emitted event word (E5) and the
//       state write-back are all combinational functions of v_cur, r_cur
//       and w_code, this is the statement that a single-bit error in a
//       protected word cannot change the emitted result: it cannot even
//       change the datapath's input.
//   M2  the same error is ANNOUNCED: state_sec is high for exactly the
//       cycles the scan consumes a corrected word, and state_ded stays
//       low. A correction the telemetry cannot see is a fault the
//       operator never learns about (docs/08 section 2.3).
//   M3  the same single-bit error leaves the DEBUG READ PORT correct.
//       dbg_v and dbg_r are module outputs, so this one is a statement
//       about an observable pin of the block, not about an internal cut.
//   M4  a single-bit error anywhere in a 72-bit synapse codeword leaves
//       the weight the scan reads equal to the weight that was stored,
//       with wmem_sec announcing it and wmem_ded low.
//   M5  a double-bit error in a synapse codeword is detected, never
//       miscorrected, and degrades to E10: every weight of that word
//       contributes exactly zero, which is what
//       sw/golden/lif_core.py poison_word() models. This is the property
//       that makes the golden model's E10 path testable against this
//       build rather than against a comment.
//   M6  a clean codeword raises neither flag and returns its own data,
//       on both files. This is the transparency requirement --
//       hw/tb/test_lif_core_rtl.py's bit-exact lockstep would fail if it
//       did not hold -- stated as a proof rather than as a test result.
//
// Proven in the invariant task (mode prove, k-induction), under
// LIF_MEM_INV:
//   M7  every write to the neuron state file leaves that neuron's
//       codeword consistent: the stored check field is exactly the one
//       the encoder computes for the stored data. There is no path that
//       updates V or R without updating the check field, in any state,
//       from either writer.
//   M8  the same for the synapse file across the load port's
//       read-modify-write.
// M7 and M8 are what make M1..M6 mean anything about the running design:
// the read properties assume a stored codeword that is clean or singly
// corrupted, and the invariant is what says the design only ever creates
// clean ones.
//
// Contract assumptions, and why each is legitimate rather than
// convenient. All three are obligations the lif_core header's Contract
// block already places on the instantiating block, and the first is
// additionally an invariant proven by H5 in formal/lif_ctrl_props.v:
//   * the scan index addresses a neuron that exists;
//   * the debug port addresses a neuron that exists;
//   * the weight ports address a synapse that exists.
// At a power-of-two geometry every one of them is true by construction
// and the assumption is a no-op; they are written out so the job also
// runs at 3 x 2, where the index widths round up and can encode indices
// with no array entry behind them.

// ---------------------------------------------------------------------
// Index legality (see the Contract note above)
// ---------------------------------------------------------------------
always @(*) begin
    assume (jj < N_NEURONS);
    assume (dbg_addr < N_NEURONS);
    assume (w_rd_index < N_SYN);
    assume (w_wr_index < N_SYN);
end

`ifdef LIF_MEM_INV
// =====================================================================
// M7 / M8: writes leave both codewords consistent (k-induction)
// =====================================================================
// One arbitrary but fixed neuron and one arbitrary but fixed synapse
// codeword. Proving the invariant for a symbolic index proves it for
// every index.

(* anyconst *) reg [NEUR_W-1:0] f_j;
(* anyconst *) reg [WW_W-1:0]   f_w;

always @(*) begin
    assume (f_j < N_NEURONS);
    assume (f_w < N_WWORD);
end

// The check field the encoder would produce for what is stored now.
wire [ST_C-1:0] f_st_chk_ref;
lif_state_enc u_f_st_ref (
    .data_in   ({rmem[f_j], vmem[f_j]}),
    .check_out (f_st_chk_ref)
);

wire [7:0]  f_w_chk_ref;
wire [71:0] f_w_code_ref;
secded_enc u_f_w_ref (
    .data_in   (w_data_all[{f_w, 6'd0} +: 64]),
    .check_out (f_w_chk_ref),
    .code_out  (f_w_code_ref)
);

wire f_st_consistent = (smem[f_j * ST_C +: ST_C] == f_st_chk_ref);
wire f_w_consistent  = (wchk[{f_w, 3'd0} +: 8]   == f_w_chk_ref);

// The files are deliberately off the reset net (spec section 3), so
// consistency is established by the first STATE_CLR and the first weight
// load rather than by reset. The induction base is therefore an
// assumption on the initial state, exactly as the design's own bring-up
// contract states, and the step is what has to be proven.
initial assume (f_st_consistent);
initial assume (f_w_consistent);

always @(posedge clk) begin
    assert (f_st_consistent);   // M7
    assert (f_w_consistent);    // M8
end

// Non-vacuity: the writes the invariant has to survive really happen.
always @(posedge clk) begin
    cover (st_we && (st_addr == f_j) && (state == S_CLR));
    cover (st_we && (st_addr == f_j) && (state == S_EV));
    cover (st_we && (st_addr == f_j) && (state == S_TICK));
    cover (st_we && (st_addr == f_j) && (state == S_IDLE));
    cover (w_wr_en && (w_wr_word == f_w));
end

`else
// =====================================================================
// M1..M6: a single stored bit, flipped
// =====================================================================

// -- neuron state file -------------------------------------------------
(* anyconst *) reg [ST_D-1:0] f_sdata;   // the state word that was stored
(* anyconst *) reg [25:0]     f_serr;    // the error the storage took

wire [ST_C-1:0] f_schk;
lif_state_enc u_f_s_enc (
    .data_in   (f_sdata),
    .check_out (f_schk)
);
wire [25:0] f_scode = {f_schk, f_sdata};

function [7:0] f_weight26;
    input [25:0] v;
    integer i;
    begin
        f_weight26 = 8'd0;
        for (i = 0; i < 26; i = i + 1)
            f_weight26 = f_weight26 + {7'd0, v[i]};
    end
endfunction

wire [7:0] f_sw = f_weight26(f_serr);

// -- synapse file ------------------------------------------------------
(* anyconst *) reg [63:0] f_wdata;       // the codeword's 16 weights
(* anyconst *) reg [71:0] f_werr;        // the error the storage took

wire [7:0]  f_wchk;
wire [71:0] f_wcode;
secded_enc u_f_w_enc (
    .data_in   (f_wdata),
    .check_out (f_wchk),
    .code_out  (f_wcode)
);

function [7:0] f_weight72;
    input [71:0] v;
    integer i;
    begin
        f_weight72 = 8'd0;
        for (i = 0; i < 72; i = i + 1)
            f_weight72 = f_weight72 + {7'd0, v[i]};
    end
endfunction

wire [7:0] f_ww = f_weight72(f_werr);

// The weight the scan is asking for, taken out of the word that was
// stored rather than out of the word that was read back.
wire [3:0] f_w_true = f_wdata[{w_rd_nib, 2'd0} +: 4];

integer f_k;
always @(*) begin
    // A geometry whose synapse count is not a multiple of 16 leaves the
    // top of the last codeword with no storage behind it. Those nibbles
    // are tied to zero on both the encode and the decode side, so they
    // can carry neither data nor an error; saying so keeps the weight
    // arithmetic above honest at such a geometry instead of letting the
    // solver hide error bits where nothing can flip.
    for (f_k = 0; f_k < 16; f_k = f_k + 1)
        if ({w_rd_word, f_k[3:0]} >= N_SYN) begin
            assume (f_wdata[f_k*4 +: 4] == 4'd0);
            assume (f_werr[f_k*4 +: 4]  == 4'd0);
        end

    // THE FAULT MODEL. What is in the storage is a clean codeword with a
    // symbolic error vector applied. The error weight is deliberately not
    // assumed; each property below is an implication on the weight, so
    // the covers are evaluated in the same unconstrained model.
    assume ({smem[jj * ST_C +: ST_C], rmem[jj], vmem[jj]}
            == (f_scode ^ f_serr));
    assume ({smem[dbg_addr * ST_C +: ST_C], rmem[dbg_addr], vmem[dbg_addr]}
            == (f_scode ^ f_serr));
    assume ({wchk[{w_rd_word, 3'd0} +: 8],
             w_data_all[{w_rd_word, 6'd0} +: 64]} == (f_wcode ^ f_werr));

    // -- M6: a clean word is transparent ------------------------------
    if (f_sw == 8'd0) begin
        assert ({r_cur, v_cur} == f_sdata);
        assert ({dbg_r, dbg_v} == f_sdata);
        assert (!st_scan_sec);
        assert (!st_scan_ded);
        assert (!state_sec);
        assert (!state_ded);
    end
    if (f_ww == 8'd0) begin
        assert (w_code == f_w_true);
        assert (!w_rd_sec);
        assert (!w_rd_ded);
        assert (!wmem_sec);
        assert (!wmem_ded);
    end

    // -- M1 / M2 / M3: one flipped bit in a neuron state word ----------
    if (f_sw == 8'd1) begin
        assert ({r_cur, v_cur} == f_sdata);      // M1
        assert ({dbg_r, dbg_v} == f_sdata);      // M3
        assert (st_scan_sec);                    // M2
        assert (!st_scan_ded);
        assert (!state_ded);
        assert (state_sec == st_rd_used);
    end

    // -- M4: one flipped bit in a synapse codeword ---------------------
    if (f_ww == 8'd1) begin
        assert (w_code == f_w_true);
        assert (w_rd_sec);
        assert (!w_rd_ded);
        assert (!wmem_ded);
        assert (wmem_sec == w_rd_used);
    end

    // -- M5: two flipped bits in a synapse codeword, and E10 -----------
    if (f_ww == 8'd2) begin
        assert (w_rd_ded);
        assert (!w_rd_sec);
        assert (w_code == 4'd0);                 // (E10) zero substitution
        assert (!wmem_sec);
        assert (wmem_ded == w_rd_used);
    end

    // -- two flipped bits in a neuron state word -----------------------
    // No fail-operational substitution exists for a membrane potential,
    // so the contract is detect-and-report and the data field is passed
    // through untouched. Stating it here is what stops a future edit from
    // quietly inventing a substitution the golden model does not have.
    if (f_sw == 8'd2) begin
        assert (st_scan_ded);
        assert (!st_scan_sec);
        assert ({r_cur, v_cur} == (f_sdata ^ f_serr[19:0]));
        assert (!state_sec);
        assert (state_ded == st_rd_used);
    end

    // Global: the two flags of a file are never both asserted, and a
    // correction is never silent.
    assert (!(st_scan_sec && st_scan_ded));
    assert (!(w_rd_sec && w_rd_ded));
    if (f_sw <= 8'd2 && !st_scan_sec)
        assert ({r_cur, v_cur} == (f_sdata ^ f_serr[19:0]));
end

// -----------------------------------------------------------------
// Non-vacuity (docs/09 section B.1). Every branch above must be
// reachable, and the three that matter most -- a repair the datapath
// actually consumed, a repair inside the refractory counter, and an E10
// substitution -- must be reachable with the scan running.
// -----------------------------------------------------------------
always @(*) begin
    cover (f_sw == 8'd0 && !st_scan_sec && !st_scan_ded);
    cover (f_sw == 8'd1 && st_scan_sec && st_rd_used);
    cover (f_sw == 8'd1 && st_scan_sec && f_serr[19:16] != 4'd0);  // in R
    cover (f_sw == 8'd1 && st_scan_sec && f_serr[15:0]  != 16'd0); // in V
    cover (f_sw == 8'd1 && st_scan_sec && f_serr[25:20] != 6'd0);  // in check
    cover (f_sw == 8'd2 && st_scan_ded && st_rd_used);
    cover (f_ww == 8'd1 && w_rd_sec && w_rd_used && f_w_true != 4'd0);
    cover (f_ww == 8'd2 && w_rd_ded && w_rd_used && f_w_true != 4'd0);
    cover (f_ww == 8'd1 && w_rd_sec && f_werr[71:64] != 8'd0);     // in check
end

`endif
