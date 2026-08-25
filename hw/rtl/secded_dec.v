// SECDED (72, 64) decoder for the synaptic weight SRAM
// (docs/10-npu-mvp-spec.md sections 5 and 11.2). One 72-bit physical word
// in; corrected 64-bit weight word plus the two fault flags out.
//
// Purely combinational, no state, no clock. Golden model:
// sw/golden/secded.py; cross-checked in hw/tb/test_secded.py, proven in
// formal/secded.sby.
//
// Decode rules (normative, mirrored by the model):
//
//   syndrome == 0                            clean word, no flags
//   syndrome odd parity and equal to some     single-bit error: that bit
//     H column                                is flipped back, sec = 1
//   syndrome != 0 otherwise                   uncorrectable: ded = 1, the
//                                             data field passes through
//                                             untouched, sec = 0
//
// Because every H column has odd weight, a two-bit error always produces a
// nonzero EVEN-parity syndrome, which can never equal a column: double
// errors are detected and never miscorrected. The "otherwise" branch also
// catches odd syndromes that match no column (56 of the 128 odd values are
// not columns; a triple error can reach one) - reported uncorrectable
// rather than miscorrected. sec therefore means "corrected", not merely
// "odd syndrome".
//
// Consumers (docs/10 sections 10 and 11.2): sec increments CNT_SEC and the
// scrubber rewrites the corrected word; ded increments CNT_DED, latches
// FAULT_ADDR, sets STATUS.DED_SEEN and makes the datapath substitute zero
// contributions for the 16 weights of the word (E10, fail-operational).
// Both flags are level outputs, one per decoded word; the register block
// qualifies them with its own read strobe.
//
// The H matrix constants are identical to secded_enc.v (each module stays
// self-contained and hand-auditable); any divergence breaks
// formal/secded.sby, which composes the two.
`default_nettype none

module secded_dec #(
    parameter DATA_W  = 64,  // fixed by docs/10 section 5, do not override
    parameter CHECK_W = 8
) (
    input  wire [71:0] code_in,
    output wire [63:0] data_out,
    output wire [7:0]  syndrome,
    output wire        sec,       // single-bit error corrected  -> CNT_SEC
    output wire        ded        // uncorrectable, detected     -> CNT_DED
);

    generate
        if (DATA_W != 64 || CHECK_W != 8) begin : g_bad_width
            ERROR_secded_dec_is_fixed_at_72_64 guard ();
        end
    endgenerate

    localparam [63:0] H_ROW0 = 64'h1F04225844B12CB7;
    localparam [63:0] H_ROW1 = 64'h2F0844A88952555B;
    localparam [63:0] H_ROW2 = 64'h4F10893112649A6D;
    localparam [63:0] H_ROW3 = 64'h8F2111C22388E38E;
    localparam [63:0] H_ROW4 = 64'hF1421E043C0F03F0;
    localparam [63:0] H_ROW5 = 64'hF283E007C00FFC00;
    localparam [63:0] H_ROW6 = 64'hF4FC0007FFF00000;
    localparam [63:0] H_ROW7 = 64'hF8FFFFF800000000;

    wire [63:0] data_raw  = code_in[63:0];
    wire [7:0]  check_raw = code_in[71:64];

    // Recomputed check bits over the received data field (same XOR trees
    // as secded_enc.v), and the syndrome against the received check bits.
    wire [7:0] check_calc;
    assign check_calc[0] = ^(data_raw & H_ROW0);
    assign check_calc[1] = ^(data_raw & H_ROW1);
    assign check_calc[2] = ^(data_raw & H_ROW2);
    assign check_calc[3] = ^(data_raw & H_ROW3);
    assign check_calc[4] = ^(data_raw & H_ROW4);
    assign check_calc[5] = ^(data_raw & H_ROW5);
    assign check_calc[6] = ^(data_raw & H_ROW6);
    assign check_calc[7] = ^(data_raw & H_ROW7);

    assign syndrome = check_calc ^ check_raw;

    wire syn_nonzero = |syndrome;
    wire syn_odd     = ^syndrome;

    // Column view of the same matrix: data bit j is identified by the
    // syndrome equal to its H column. The columns are distinct, so at most
    // one bit of corr_mask can be set.
    wire [63:0] corr_mask;
    genvar j;
    generate
        for (j = 0; j < 64; j = j + 1) begin : g_column
            wire [7:0] col = {H_ROW7[j], H_ROW6[j], H_ROW5[j], H_ROW4[j],
                              H_ROW3[j], H_ROW2[j], H_ROW1[j], H_ROW0[j]};
            assign corr_mask[j] = (syndrome == col);
        end
    endgenerate

    wire data_hit  = |corr_mask;                          // a data column
    wire check_hit = syn_nonzero && ((syndrome & (syndrome - 8'd1)) == 8'd0);
                                                          // an identity column

    // syn_odd is implied by the matrix (every column has odd weight) and is
    // kept as an explicit gate on purpose: if the constants above were ever
    // mistyped into an even-weight column, this degrades the outcome to
    // "uncorrectable" instead of to a silent miscorrection.
    wire correctable = syn_odd && (data_hit || check_hit);

    assign sec = syn_nonzero && correctable;
    assign ded = syn_nonzero && !correctable;

    // A flipped check bit needs no data repair; the flag still fires.
    assign data_out = sec ? (data_raw ^ corr_mask) : data_raw;

endmodule

`default_nettype wire
