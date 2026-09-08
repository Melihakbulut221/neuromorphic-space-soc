// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// SECDED (72, 64) encoder for the synaptic weight SRAM
// (docs/10-npu-mvp-spec.md section 5: "64 data bits = 16 weights, plus 8
// SECDED check bits (72-bit macro word, 12.5 percent overhead)"). One
// 64-bit weight word in, one 72-bit physical word out.
//
// Purely combinational, no state, no clock. The golden model is
// sw/golden/secded.py; hw/tb/test_secded.py cross-checks this module
// against it and formal/secded.sby proves the encoder/decoder pair.
//
// Codeword layout (identical in the model and in secded_dec.v):
//
//     code_out[63:0]   data field, systematic (data bit j at bit j)
//     code_out[71:64]  check field  (check bit i at bit 64 + i)
//
// Parity-check matrix H, row form: H_ROW[i] has bit j set when data bit j
// feeds check bit i, so check_out[i] = ^(data_in & H_ROW[i]). The column
// view (H column of data bit j = the 8-bit vector of H_ROW[*][j]) is a
// Hsiao code: all 72 columns distinct, nonzero and of ODD weight (56 of
// weight 3, 8 of weight 5, 8 identity columns for the check field). Odd
// weight is the whole SEC-DED argument - see the header of
// sw/golden/secded.py and formal/secded_props.v.
//
// Every row has weight 26 over the data field (plus its own check bit),
// so all eight XOR trees are the same depth: 5 levels of 2-input XOR.
//
// The eight constants below are the normative matrix. They also appear in
// secded_dec.v (each module stays self-contained and hand-auditable); any
// divergence between the two copies, or from sw/golden/secded.py, breaks
// formal/secded.sby and hw/tb/test_secded.py immediately.
`default_nettype none

module secded_enc #(
    parameter DATA_W  = 64,  // fixed by docs/10 section 5, do not override
    parameter CHECK_W = 8
) (
    input  wire [63:0] data_in,
    output wire [7:0]  check_out,
    output wire [71:0] code_out
);

    // Elaboration guard, aer_fifo house style: a build that overrides the
    // widths references a module that deliberately does not exist, so it
    // fails at elaboration with the reason in the message.
    generate
        if (DATA_W != 64 || CHECK_W != 8) begin : g_bad_width
            ERROR_secded_enc_is_fixed_at_72_64 guard ();
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

    assign check_out[0] = ^(data_in & H_ROW0);
    assign check_out[1] = ^(data_in & H_ROW1);
    assign check_out[2] = ^(data_in & H_ROW2);
    assign check_out[3] = ^(data_in & H_ROW3);
    assign check_out[4] = ^(data_in & H_ROW4);
    assign check_out[5] = ^(data_in & H_ROW5);
    assign check_out[6] = ^(data_in & H_ROW6);
    assign check_out[7] = ^(data_in & H_ROW7);

    assign code_out = {check_out, data_in};

endmodule

`default_nettype wire
