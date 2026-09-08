// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// The shortened code, proved.
//
// WHAT THIS JOB IS FOR, AND WHAT IT DELIBERATELY IS NOT
//
// hw/soc/rtl/ibex_regfile_secded.v protects 32-bit architectural
// registers with a codec that is fixed at 64 data bits and 8 check
// bits. It does that by tying the codec's upper 32 data bits to zero,
// which turns the (72,64) Hsiao code into its (40,32) SHORTENING. The
// codec itself is already proved -- formal/secded.sby, docs/35 --  and
// hw/tb/test_secded.py already cross-checks it against
// sw/golden/secded.py. None of that is re-done here.
//
// What IS new is the shortening, and it is new in the way that matters:
// it is an argument about a matrix, made in a comment, which nothing
// checks. This job checks it. If the eight rows of H were ever retyped,
// or the tie-off were ever moved, the argument would still read
// correctly and the code would not be a SECDED code any more, and every
// simulation in this repository would still pass because a fault-free
// codeword decodes to itself whatever H is.
//
// FOUR PROPERTIES, over a free data word and a free 40-bit error vector
// applied to the 40 bits that are actually stored:
//
//   C1  no error            -> no flag, and the data comes back
//   C2  exactly one bit     -> corrected, sec, no ded
//   C3  exactly two bits    -> ded, and NEVER sec: a double error must
//                              be reported, not miscorrected into a
//                              third wrong word
//   C4  check bit 7 is identically zero over a 32-bit data field
//   C5  the fast correction is the decoder's correction, for EVERY
//       codeword and EVERY error vector -- docs/44's timing recovery,
//       stated as an equality rather than as an argument
//   C6  the syndrome computed from the ENCODER beside the storage is
//       the syndrome the DECODER computes after the read multiplexer --
//       docs/49's SYNPRE, and the one thing C5 does not cover
//   C7  and therefore the hoisted read path returns the same word,
//       stated directly rather than left as a corollary of C5 and C6
//   C8  (docs/67) the FLAGS re-derived from the syndrome alone -- sec
//       as 'some live column matched or the syndrome is one-hot', ded
//       as 'nonzero and not sec' -- equal the frozen decoder's sec and
//       ded for every error of weight 0, 1 or 2. hw/soc/rtl/
//       soc_mem_ecc.v's word code for the boot ROM derives its flags
//       this way, because they drive a macro's write mask and the
//       frozen decoder's 64-wide match was measured on that path;
//       byte_secded.sby B6 is the same statement for the byte code.
//
// C4 is the odd one out and it is here because it is a MEASUREMENT this
// document would otherwise have to take on trust. H_ROW7 is
// 64'hF8FFFFF800000000, whose low 32 bits are zero, so over a shortened
// 32-bit word that check bit is a constant -- and the synthesiser finds
// the constant and deletes one flip-flop per register, 31 in all. The
// shortened code is therefore (39,32) with seven check bits, which is
// the MINIMAL SECDED width for 32 data bits, arrived at by arithmetic
// rather than by design. docs/43 section 7 reports the flip-flop count
// that follows from it, and this property is why that count is a
// consequence rather than a coincidence.
//
// C5 IS THE ONE THIS DOCUMENT WOULD BE WRONG WITHOUT. docs/44 takes
// gate levels off the register read path by not using the frozen
// decoder's `data_out` at all: it XORs the raw word with a correction
// mask built from the decoder's SYNDROME, skipping the 64-wide OR, the
// eight-bit subtract, the AND that joins them and the multiplexer they
// select. The reasoning is that `sec` is 1 whenever the mask is
// nonzero, so the qualification cannot change the answer -- and that
// reasoning is a paragraph about a matrix, which is exactly the kind of
// thing this job exists because comments are not checks. C5 states the
// equality over a free codeword instead.
//
// The mask's columns are DERIVED here the same way the RTL derives
// them, from the pilot encoder on the unit vectors, so this proof would
// follow hw/rtl/secded_enc.v if it ever changed rather than certifying
// a copy of it.
//
// C6 IS WHAT docs/49 WOULD BE WRONG WITHOUT, AND C5 DOES NOT IMPLY IT.
// C5 is an equality between two functions of the DECODER's `syndrome`.
// SYNPRE does not change what is done with the syndrome; it changes
// WHERE THE SYNDROME COMES FROM. Instead of decoding the multiplexer's
// output it puts one `secded_enc` beside every register and takes
// `enc(stored_data).check_out ^ stored_chk`, so the XOR tree runs in
// parallel with the read multiplexer rather than behind it.
//
// That substitution is only sound if the encoder's H and the decoder's
// H are the same matrix, and THEY ARE TWO SEPARATE COPIES OF IT:
// hw/rtl/secded_dec.v says so in its own header -- "the H matrix
// constants are identical to secded_enc.v (each module stays
// self-contained)". Nothing in this repository compared them until now.
// formal/secded.sby proves the codec end to end, which is satisfied by
// any pair of matrices that agree with each other; it would pass on a
// pair that agreed with each other and disagreed with H. C6 states the
// bit-level equality of the two syndromes directly, over a free
// codeword and a free error vector, so the sentence "SYNPRE computes
// the same syndrome earlier" is a proof obligation rather than a
// comment. C7 then states the consequence at the port.
//
// THE FAULT MODEL. One error vector, free every cycle, over exactly the
// 40 bits the register file stores. Nothing here models a fault in the
// codec's own combinational logic, in the read multiplexer, in the
// address, or in the scrub sequencer; a single-event transient in any
// of those is outside this and outside the campaign, and docs/43
// section 11 says so.

`default_nettype none

module regfile_secded_props (
    input wire        clk_i,
    input wire [31:0] d_i,       // the register's true value
    input wire [39:0] e_i        // the upset, over the 40 stored bits
);

    // What the register file stores: the codec's check bits over the
    // 32-bit word with the upper half tied off, exactly as
    // ibex_regfile_secded.v ties it off.
    wire [7:0]  chk;
    wire [71:0] code_unused;
    secded_enc u_enc (
        .data_in   ({32'h0, d_i}),
        .check_out (chk),
        .code_out  (code_unused)
    );

    // The stored 40 bits, with the upset applied.
    wire [31:0] stored_data = d_i ^ e_i[31:0];
    wire [7:0]  stored_chk  = chk ^ e_i[39:32];

    wire [63:0] out;
    wire [7:0]  syn;
    wire        sec, ded;
    secded_dec u_dec (
        .code_in  ({stored_chk, 32'h0, stored_data}),
        .data_out (out),
        .syndrome (syn),
        .sec      (sec),
        .ded      (ded)
    );

    // Weight of the error vector. A function rather than $countones so
    // that the file is Verilog-2005 and reads in the same front ends
    // every other file in this tree reads in.
    function [6:0] f_weight(input [39:0] v);
        integer k;
        begin
            f_weight = 7'd0;
            for (k = 0; k < 40; k = k + 1)
                f_weight = f_weight + {6'd0, v[k]};
        end
    endfunction

    wire [6:0] w = f_weight(e_i);

    // ---- the fast correction, exactly as the RTL builds it ----------
    wire [7:0]  h_col [0:31];
    wire [31:0] mask;
    genvar gj;
    generate
        for (gj = 0; gj < 32; gj = gj + 1) begin : g_col
            wire [71:0] col_code_unused;
            secded_enc u_col (
                .data_in   ({32'h0, {{31{1'b0}}, 1'b1} << gj}),
                .check_out (h_col[gj]),
                .code_out  (col_code_unused)
            );
            assign mask[gj] = (syn == h_col[gj]);
        end
    endgenerate

    wire [31:0] fast_out = stored_data ^ mask;

    // ---- the fast flags, as soc_mem_ecc.v g_dec_word derives them ----
    wire f_syn_nz = |syn;
    wire f_onehot = f_syn_nz && ((syn & (syn - 8'd1)) == 8'd0);
    wire f_sec    = (|mask) || f_onehot;
    wire f_ded    = f_syn_nz && !f_sec;

    // ---- the hoisted syndrome, exactly as SYNPRE builds it ----------
    // One encoder beside the storage, over the stored data, and the
    // stored check bits XORed in. This is g_synpre's `rf_syn[gj]` with
    // the register index dropped, because the register file's storage
    // and multiplexer are not in this harness and the substitution is
    // per-register.
    wire [7:0]  pre_chk;
    wire [71:0] pre_code_unused;
    secded_enc u_pre (
        .data_in   ({32'h0, stored_data}),
        .check_out (pre_chk),
        .code_out  (pre_code_unused)
    );
    wire [7:0] pre_syn = pre_chk ^ stored_chk;

    // and the mask the register file would build from it.
    wire [31:0] pre_mask;
    generate
        for (gj = 0; gj < 32; gj = gj + 1) begin : g_pre_col
            assign pre_mask[gj] = (pre_syn == h_col[gj]);
        end
    endgenerate

    wire [31:0] pre_out = stored_data ^ pre_mask;

    always @(*) begin
        // C4. The eighth check bit does not exist over a 32-bit word.
        //     Asserted on the ENCODER's output, so it is a statement
        //     about the matrix and not about this harness.
        assert (chk[7] == 1'b0);

        // C1. Nothing wrong, nothing said, nothing changed.
        if (w == 7'd0) begin
            assert (!sec);
            assert (!ded);
            assert (syn == 8'h0);
            assert (out[31:0] == d_i);
        end

        // C2. One bit anywhere in the 40 -- data field or check field --
        //     is corrected, flagged as corrected, and not flagged as
        //     uncorrectable.
        if (w == 7'd1) begin
            assert (sec);
            assert (!ded);
            assert (out[31:0] == d_i);
        end

        // C3. Two bits are DETECTED and never miscorrected. This is the
        //     half of SECDED that a code with an even-weight column
        //     would silently lose, and losing it would turn a
        //     double-bit upset into a third, plausible, wrong value.
        if (w == 7'd2) begin
            assert (ded);
            assert (!sec);
        end

        // C5. THE FAST CORRECTION IS THE DECODER'S CORRECTION. No
        //     guard on the weight: this holds for every codeword and
        //     every error vector, including the ones that are neither
        //     correctable nor a double error, because that is what
        //     replacing an output with a different function of the same
        //     inputs has to mean.
        assert (fast_out == out[31:0]);

        // C6. THE HOISTED SYNDROME IS THE DECODER'S SYNDROME. Two
        //     independent copies of H -- the encoder's and the
        //     decoder's -- compared bit for bit, for every codeword and
        //     every error vector. No guard on the weight, for C5's
        //     reason: a substitution either is the same function or it
        //     is not.
        assert (pre_syn == syn);

        // C8. The fast flags are the decoder's flags, up to weight 2.
        if (w <= 7'd2) begin
            assert (f_sec == sec);
            assert (f_ded == ded);
        end

        // C7. And therefore the register file's read port returns the
        //     same word with the tree in front of the multiplexer as it
        //     does with the tree behind it. This follows from C5 and
        //     C6, and it is stated anyway because it is the sentence
        //     docs/49 relies on and a reader should not have to compose
        //     two properties to find it.
        assert (pre_out == out[31:0]);
    end

    // Vacuity, docs/09 B.1: every branch above has to be reachable, or
    // the job proves nothing about the cases it claims to cover.
    always @(posedge clk_i) begin
        cover (w == 7'd0);
        cover (w == 7'd1 && sec && (e_i[31:0] != 32'h0));   // a data bit
        cover (w == 7'd1 && sec && (e_i[39:32] != 8'h0));   // a check bit
        cover (w == 7'd2 && ded);
        cover (w == 7'd3);
        // C5's two interesting cases: the mask actually does something,
        // and the decoder reports uncorrectable while the mask is zero.
        // Without these, C5 could hold vacuously on a harness where the
        // mask were never nonzero.
        cover (mask != 32'h0);
        cover (ded && mask == 32'h0);
        // C6 and C7's, for the same reason: an equality between two
        // syndromes proves nothing if the syndrome is never nonzero,
        // and C7 proves nothing if the hoisted mask never corrects.
        cover (pre_syn != 8'h0);
        cover (pre_mask != 32'h0);
        // C8's stated limit, witnessed: a triple error on which the
        // frozen decoder says sec and the fast flags say ded
        cover (w == 7'd3 && sec && f_ded);
    end

endmodule

`default_nettype wire
