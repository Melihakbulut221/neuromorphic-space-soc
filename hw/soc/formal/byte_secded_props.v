// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// The byte shortening, proved.
//
// hw/soc/rtl/soc_mem_ecc.v stores each byte of a RAM word as its own
// codeword: the frozen (72,64) codec with data bits 8..63 tied to zero,
// so eight data bits and the eight check bits the encoder produces over
// them, of which three are identically zero. This harness states, over
// a free byte and a free 16-bit error vector applied to exactly the
// bits the row stores:
//
//   B1  no error           -> no flag, the byte comes back
//   B2  exactly one bit    -> corrected, sec, no ded -- including a bit
//                             in one of the three constant-zero check
//                             positions, which is a stored bit like any
//                             other and can be hit like any other
//   B3  exactly two bits   -> ded and NEVER sec: detected, never
//                             miscorrected into a third wrong byte
//   B4  check bits 5, 6 and 7 are identically zero over a byte, which
//       is why the stored code is (13,8) and why a flip in one of them
//       is always a check-bit error with an unambiguous syndrome
//   B5  the four lanes of a row are independent: with a second free
//       lane beside the first, an error confined to one lane never
//       changes the other's output or flags -- the property a word
//       code would not have and the reason soc_mem_ecc.v's
//       double-upset test can put two upsets in one row and read it
//       clean
//   B6  THE FAST DECODE IS THE DECODER'S DECODE for every error of
//       weight 0, 1 or 2: the byte, sec and ded that soc_mem_ecc.v
//       builds from the syndrome alone -- eight column matches derived
//       from the frozen encoder, a one-hot test, and an XOR -- equal
//       the frozen decoder's data_out, sec and ded bit for bit. Stated
//       over a free byte and a free 16-bit error vector, as
//       regfile_secded.sby C5 states the register file's. The cover at
//       the end reaches the weight-3 case where the two DIFFER -- the
//       frozen decoder 'corrects' a tied-off bit and reports sec, the
//       fast decode reports ded -- so that the divergence
//       soc_mem_ecc.v's header describes is a witnessed fact and not a
//       claim.
//
// The encoder instance and the decoder instance are the repository's
// own, read out of hw/rtl/ and not copied, so the proof follows the
// matrix if it ever changed rather than certifying a transcription.

`default_nettype none

module byte_secded_props (
    input wire        clk_i,
    input wire [7:0]  d_i,       // the byte's true value
    input wire [15:0] e_i,       // the upset over the 16 stored bits
    input wire [7:0]  d2_i,      // a second lane, for B5
    input wire [15:0] e2_i
);

    // ---- lane 0: what the row stores for this byte ----------------
    wire [7:0]  chk;
    wire [71:0] code_unused;
    secded_enc u_enc (
        .data_in   ({56'h0, d_i}),
        .check_out (chk),
        .code_out  (code_unused)
    );

    wire [7:0] stored_data = d_i ^ e_i[7:0];
    wire [7:0] stored_chk  = chk ^ e_i[15:8];

    wire [63:0] out;
    wire [7:0]  syn;
    wire        sec, ded;
    secded_dec u_dec (
        .code_in  ({stored_chk, 56'h0, stored_data}),
        .data_out (out),
        .syndrome (syn),
        .sec      (sec),
        .ded      (ded)
    );

    // ---- lane 1, beside it, exactly as g_dec_byte wires it --------
    wire [7:0]  chk2;
    wire [71:0] code2_unused;
    secded_enc u_enc2 (
        .data_in   ({56'h0, d2_i}),
        .check_out (chk2),
        .code_out  (code2_unused)
    );
    wire [7:0]  stored2_data = d2_i ^ e2_i[7:0];
    wire [7:0]  stored2_chk  = chk2 ^ e2_i[15:8];
    wire [63:0] out2;
    wire [7:0]  syn2;
    wire        sec2, ded2;
    secded_dec u_dec2 (
        .code_in  ({stored2_chk, 56'h0, stored2_data}),
        .data_out (out2),
        .syndrome (syn2),
        .sec      (sec2),
        .ded      (ded2)
    );

    // ---- the fast decode, exactly as soc_mem_ecc.v g_dec_byte builds it
    wire [7:0] h_col [0:7];
    wire [7:0] mask;
    genvar gj;
    generate
        for (gj = 0; gj < 8; gj = gj + 1) begin : g_col
            wire [71:0] col_code_unused;
            secded_enc u_col (
                .data_in   ({56'h0, {7'h0, 1'b1} << gj}),
                .check_out (h_col[gj]),
                .code_out  (col_code_unused)
            );
            assign mask[gj] = (syn == h_col[gj]);
        end
    endgenerate
    wire       f_syn_nz = |syn;
    wire       f_onehot = f_syn_nz && ((syn & (syn - 8'd1)) == 8'd0);
    wire       f_sec    = (|mask) || f_onehot;
    wire       f_ded    = f_syn_nz && !f_sec;
    wire [7:0] f_out    = stored_data ^ mask;

    function [4:0] f_weight(input [15:0] v);
        integer k;
        begin
            f_weight = 5'd0;
            for (k = 0; k < 16; k = k + 1)
                f_weight = f_weight + {4'd0, v[k]};
        end
    endfunction

    wire [4:0] w  = f_weight(e_i);
    wire [4:0] w2 = f_weight(e2_i);

    always @(*) begin
        // B4. Three check rows have no bit below bit 8.
        assert (chk[7:5] == 3'b000);

        // B1.
        if (w == 5'd0) begin
            assert (!sec);
            assert (!ded);
            assert (syn == 8'h0);
            assert (out[7:0] == d_i);
        end

        // B2. One bit anywhere in the sixteen.
        if (w == 5'd1) begin
            assert (sec);
            assert (!ded);
            assert (out[7:0] == d_i);
        end

        // B3. Two bits: detected, never miscorrected.
        if (w == 5'd2) begin
            assert (ded);
            assert (!sec);
        end

        // The data field above the byte never comes back set: the
        // decoder cannot "correct" a tied-off bit into a one, which is
        // what would happen if a syndrome matched a tied-off column.
        // With at most two errors it cannot (B2 and B3 say why), and
        // the statement is made over the whole out bus so a reader
        // does not have to compose it.
        if (w <= 5'd2)
            assert (out[63:8] == 56'h0);

        // B6. The fast decode is the decoder's decode, up to weight 2.
        if (w <= 5'd2) begin
            assert (f_out == out[7:0]);
            assert (f_sec == sec);
            assert (f_ded == ded);
        end

        // B5. Lane 1 is a function of lane 1 alone.
        if (w2 == 5'd0) begin
            assert (!sec2 && !ded2);
            assert (out2[7:0] == d2_i);
        end
        if (w2 == 5'd1) begin
            assert (sec2 && !ded2);
            assert (out2[7:0] == d2_i);
        end
    end

    // Vacuity, docs/09 B.1.
    always @(posedge clk_i) begin
        cover (w == 5'd0);
        cover (w == 5'd1 && sec && (e_i[7:0] != 8'h0));       // a data bit
        cover (w == 5'd1 && sec && (e_i[12:8] != 5'h0));      // a live check bit
        cover (w == 5'd1 && sec && (e_i[15:13] != 3'h0));     // a constant-zero check bit
        cover (w == 5'd2 && ded);
        cover (w == 5'd3);
        // both lanes hit at once and both corrected, the independence
        cover (w == 5'd1 && w2 == 5'd1 && sec && sec2);
        // one lane uncorrectable while the other corrects
        cover (w == 5'd2 && w2 == 5'd1 && ded && sec2);
        // B6's stated divergence, witnessed: a triple error the frozen
        // decoder reports as corrected -- its syndrome matched a column
        // of a bit the byte code does not store -- and the fast decode
        // reports as uncorrectable
        cover (w == 5'd3 && sec && f_ded);
        // and a triple error on which the two agree
        cover (w == 5'd3 && ded && f_ded);
    end

endmodule

`default_nettype wire
