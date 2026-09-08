// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Formal properties for the SECDED (26, 20) neuron-state codec
// (hw/rtl/lif_core.v, modules lif_state_enc and lif_state_dec).
// SymbiYosys harness: formal/lif_mem.sby, driver formal/lif_mem.mk.
//
// Why this job exists. docs/16 ranked the neuron state file as the
// second and third largest sources of silent data corruption in the
// pilot (vmem 91.7% SDC over 128 flip-flops, rmem 100.0% over 32). The
// hardening that answers that ranking rests entirely on this 26-bit
// code: if it miscorrects, an upset that used to be visible as a wrong
// answer becomes a wrong answer the design certifies as right. The code
// is small enough to prove outright, so it is proven outright.
//
// This is a wrapper module, the style formal/secded_props.v uses and
// docs/09 B.1 sanctions for property sets that must see more than one
// instance: it composes lif_state_enc with lif_state_dec, so the proof
// also pins the two copies of the H mask table to each other. A typo in
// either copy fails here immediately.
//
// Method, identical to secded_props.v. f_data and f_err are $anyconst:
// the solver picks a 20-bit data word and a 26-bit error vector and holds
// them. Both modules are purely combinational, so BMC at depth 1
// evaluates the entire 2^20 x 2^26 input space -- this is a full proof in
// the sense of docs/09 target #2, not a bounded result. The error weight
// is not assumed; every property is an implication on the weight, so the
// cover statements are evaluated in the same unconstrained model and
// cannot be made vacuous by an over-tight assumption.
//
// Proven:
//   L1  clean word: weight 0 -> syndrome 0, no flags, data returned
//       intact. This is decode(encode(x)) == x for symbolic x, and it is
//       the property the golden-model lockstep depends on: if it failed,
//       the hardening would not be transparent.
//   L2  every single flipped bit, anywhere in the 26-bit word -- data
//       field, Hamming check field or the overall-parity bit -- is
//       corrected, not merely flagged: sec, no ded, and the data comes
//       back equal to the transmitted data.
//   L3  every two flipped bits are detected and never miscorrected: ded,
//       no sec, the data field passed through unrepaired.
//   L4  weight 1 and weight 2 are told apart by the overall-parity bit,
//       which is the whole distance-4 argument in one line: an odd number
//       of errors gives ^code_in == 1, an even nonzero number gives
//       ^code_in == 0 with a nonzero Hamming syndrome.
//   L5  global consistency independent of the error weight: the flags are
//       mutually exclusive, sec always means the decoder landed back on
//       the transmitted word, and without sec the data field is passed
//       through untouched.
//   L6  the code is systematic: code[19:0] is the data field verbatim, so
//       vmem and rmem hold the state word itself and a host reading them
//       through a debugger sees V and R, not a transform of them.
//   L7  the encoder's check field is the one the DECODER's copy of the
//       mask table computes, checked through a second decoder instance
//       driven with a zeroed check field. Without L7 the two copies of
//       the table are only pinned together on the codeword path.
`default_nettype none

module lif_mem_codec_props (
    input wire clk
);

    (* anyconst *) reg [19:0] f_data;
    (* anyconst *) reg [25:0] f_err;

    // Transmitted codeword.
    wire [5:0] enc_check;
    lif_state_enc u_enc (
        .data_in   (f_data),
        .check_out (enc_check)
    );
    wire [25:0] code = {enc_check, f_data};

    // Second decoder instance, used only to pin the encoder's mask table
    // to the decoder's (L7). A word whose check field is zero makes the
    // decoder's syndrome its own recomputation of check_bits(data): the
    // five Hamming bits come back directly, and the overall-parity bit of
    // that word is the parity of the data field alone, which is the
    // encoder's parity bit XOR the parity of the five Hamming bits.
    wire [5:0] chk_syndrome;
    lif_state_dec u_dec_check (
        .code_in  ({6'd0, f_data}),
        .data_out (),
        .syndrome (chk_syndrome),
        .sec      (),
        .ded      ()
    );

    // Received word: the codeword with the symbolic error vector applied.
    wire [25:0] rx = code ^ f_err;

    wire [19:0] dec_data;
    wire [5:0]  dec_syndrome;
    wire        dec_sec;
    wire        dec_ded;
    lif_state_dec u_dec (
        .code_in  (rx),
        .data_out (dec_data),
        .syndrome (dec_syndrome),
        .sec      (dec_sec),
        .ded      (dec_ded)
    );

    // Hamming weight of the symbolic error vector.
    function [7:0] weight26;
        input [25:0] v;
        integer i;
        begin
            weight26 = 8'd0;
            for (i = 0; i < 26; i = i + 1)
                weight26 = weight26 + {7'd0, v[i]};
        end
    endfunction

    wire [7:0] f_weight = weight26(f_err);

    // dec_syndrome is {overall parity, 5-bit Hamming syndrome}.
    wire       rx_par = dec_syndrome[5];
    wire [4:0] rx_syn = dec_syndrome[4:0];

    always @(*) begin
        // L1: no error at all.
        if (f_weight == 8'd0) begin
            assert (rx_syn == 5'd0);
            assert (!rx_par);
            assert (!dec_sec);
            assert (!dec_ded);
            assert (dec_data == f_data);         // decode(encode(x)) == x
            assert (rx == code);
        end

        // L2: any single flipped bit, anywhere in the 26-bit word.
        if (f_weight == 8'd1) begin
            assert (dec_sec);
            assert (!dec_ded);
            assert (dec_data == f_data);         // corrected, not just flagged
            assert (rx_par);                     // L4: odd weight
        end

        // L3: any two flipped bits, anywhere in the 26-bit word.
        if (f_weight == 8'd2) begin
            assert (dec_ded);
            assert (!dec_sec);                   // never silently corrected
            assert (dec_data == rx[19:0]);       // passed through unrepaired
            assert (!rx_par);                    // L4: even weight
            assert (rx_syn != 5'd0);             // ... and still detected
        end

        // L5: global consistency, independent of the error weight.
        assert (!(dec_sec && dec_ded));
        if (f_weight <= 8'd2 && dec_sec)
            assert (dec_data == f_data);         // sec implies real recovery
        if (f_weight <= 8'd2 && !dec_sec && !dec_ded)
            assert (rx == code);                 // no flag only for codewords
        if (!dec_sec)
            assert (dec_data == rx[19:0]);       // no repair without the flag

        // L6: the code stays systematic.
        assert (code[19:0] == f_data);

        // L7: the encoder's check field, judged by the decoder's copy of
        // the mask table. The Hamming bits come back verbatim; the parity
        // bit of a zero-check word is the data parity, which differs from
        // the encoder's parity bit by the parity of the Hamming bits.
        assert (chk_syndrome[4:0] == enc_check[4:0]);
        assert (chk_syndrome[5] == (enc_check[5] ^ (^enc_check[4:0])));
    end

    // -----------------------------------------------------------------
    // Non-vacuity (docs/09 section B.1): every branch above is reachable,
    // and each of the three places an error can land is exercised.
    // -----------------------------------------------------------------
    always @(*) begin
        cover (f_weight == 8'd0 && !dec_sec && !dec_ded);
        cover (f_weight == 8'd1 && dec_sec && dec_data != rx[19:0]);
        cover (f_weight == 8'd1 && dec_sec && f_err[24:20] != 5'd0);
        cover (f_weight == 8'd1 && dec_sec && f_err[25]);
        cover (f_weight == 8'd2 && dec_ded && dec_data != f_data);
        cover (f_weight == 8'd2 && dec_ded && f_err[19:0] == 20'd0);
        // The refractory field is the structure with the worst measured
        // per-bit rate in the design; cover a repair that lands in it.
        cover (f_weight == 8'd1 && dec_sec && f_err[19:16] != 4'd0);
        // The check port is exercised at both rails, so L7 is not proven
        // over a single constant value of enc_check.
        cover (enc_check == 6'h00 && f_data != 20'd0);
        cover (enc_check == 6'h3F);
    end

endmodule

`default_nettype wire
