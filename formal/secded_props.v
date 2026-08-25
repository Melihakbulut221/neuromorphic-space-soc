// Formal properties for the SECDED (72, 64) codec (SymbiYosys harness,
// formal/secded.sby). Acceptance criteria from
// docs/09-formal-verification-plan.md target #2:
//
//   "decode(encode(x)) = x for all x; every 1-bit error corrected and
//    flagged CE; every 2-bit error flagged UE, never silently
//    miscorrected; syndrome=0 iff valid codeword (S). BMC depth 1 over
//    fully symbolic data + symbolic error mask constrained to weight
//    0/1/2 - exhaustive for combinational logic."
//
// This is a wrapper module (the style docs/09 B.1 sanctions for property
// sets that must see more than one instance) rather than an `ifdef FORMAL
// include: it composes hw/rtl/secded_enc.v with hw/rtl/secded_dec.v, so
// the proof also pins the two copies of the H matrix to each other.
//
// Method. f_data and f_err are $anyconst, i.e. the solver picks a 64-bit
// data word and a 72-bit error vector and holds them; the design is purely
// combinational, so BMC at depth 1 covers the entire (2^64 x 2^72) input
// space - this is a full proof, not a bounded one. The error weight is not
// assumed; each property is written as an implication on the weight, so
// the cover statements below are evaluated in the same unconstrained model
// and cannot be made vacuous by an over-tight assumption.
//
// Proven:
//   S1  clean word: weight 0 -> syndrome 0, no flags, data returned intact
//       (this is decode(encode(x)) == x for symbolic x).
//   S2  syndrome == 0 only for codewords, inside the distance the code
//       guarantees: any error vector of weight 1 or 2 produces a nonzero
//       syndrome, and - under the error-weight <= 2 guard the assertion
//       actually carries - a zero syndrome implies the received word is
//       exactly the transmitted codeword. The guard is not removable and
//       is not a gap in this implementation: the code has minimum distance
//       4, so a weight-4 error that lands on another codeword gives a zero
//       syndrome with rx != code. Every (72, 64) SECDED code behaves that
//       way, and the sw/golden/secded.py header states the same limit.
//   S3  every one-hot error is corrected: sec, no ded, and the data field
//       comes back equal to the transmitted data.
//   S4  every two-hot error is detected: ded, never sec, the data field is
//       passed through unrepaired, and the syndrome is nonzero with even
//       parity (the Hsiao argument).
//   S5  the flags are mutually exclusive and sec always means the decoder
//       landed back on the transmitted word.
//   C1  the encoder's two outputs agree: check_out is the check field of
//       code_out.
//   C2  the encoder's check_out equals the check bits the DECODER's copy of
//       the H matrix computes for the same data word (a second decoder
//       instance driven with a zeroed check field). Without C1/C2 the
//       check_out port is connected but unconstrained: nothing else in this
//       proof reads it.
`default_nettype none

module secded_props (
    input wire clk
);

    (* anyconst *) reg [63:0] f_data;
    (* anyconst *) reg [71:0] f_err;

    // Transmitted codeword.
    wire [7:0]  enc_check;
    wire [71:0] code;
    secded_enc u_enc (
        .data_in   (f_data),
        .check_out (enc_check),
        .code_out  (code)
    );

    // Second decoder instance, used only to constrain the encoder's
    // check_out port (see C1/C2 below). Feeding it a word whose check field
    // is zero makes its syndrome the pure check-bit function of the data
    // field, computed by the decoder's own copy of the H matrix. Only the
    // syndrome is taken; the other outputs are left unconnected so this
    // instance adds no wire that no property mentions.
    wire [7:0] chk_syndrome;
    secded_dec u_dec_check (
        .code_in  ({8'd0, f_data}),
        .data_out (),
        .syndrome (chk_syndrome),
        .sec      (),
        .ded      ()
    );

    // Received word: the codeword with the symbolic error vector applied.
    wire [71:0] rx = code ^ f_err;

    wire [63:0] dec_data;
    wire [7:0]  dec_syndrome;
    wire        dec_sec;
    wire        dec_ded;
    secded_dec u_dec (
        .code_in  (rx),
        .data_out (dec_data),
        .syndrome (dec_syndrome),
        .sec      (dec_sec),
        .ded      (dec_ded)
    );

    // Hamming weight of the symbolic error vector.
    function [7:0] weight72;
        input [71:0] v;
        integer i;
        begin
            weight72 = 8'd0;
            for (i = 0; i < 72; i = i + 1)
                weight72 = weight72 + {7'd0, v[i]};
        end
    endfunction

    wire [7:0] f_weight = weight72(f_err);

    always @(*) begin
        // S1: no error at all.
        if (f_weight == 8'd0) begin
            assert (dec_syndrome == 8'd0);
            assert (!dec_sec);
            assert (!dec_ded);
            assert (dec_data == f_data);         // decode(encode(x)) == x
            assert (rx == code);
        end

        // S3: any single flipped bit, anywhere in the 72-bit word.
        if (f_weight == 8'd1) begin
            assert (dec_sec);
            assert (!dec_ded);
            assert (dec_data == f_data);         // corrected, not merely flagged
            assert (dec_syndrome != 8'd0);       // S2
            assert (^dec_syndrome);              // odd column weight
        end

        // S4: any two flipped bits, anywhere in the 72-bit word.
        if (f_weight == 8'd2) begin
            assert (dec_ded);
            assert (!dec_sec);                   // never silently corrected
            assert (dec_data == rx[63:0]);       // passed through unrepaired
            assert (dec_syndrome != 8'd0);       // S2: detected
            assert (!(^dec_syndrome));           // even parity: not a column
        end

        // S5: global consistency, independent of the error weight.
        assert (!(dec_sec && dec_ded));
        if (dec_sec) assert (!dec_ded);
        if (f_weight <= 8'd2 && dec_sec)
            assert (dec_data == f_data);         // sec implies real recovery
        if (f_weight <= 8'd2 && dec_syndrome == 8'd0)
            assert (rx == code);                 // S2: syndrome 0 iff codeword
        if (!dec_sec)
            assert (dec_data == rx[63:0]);       // no repair without the flag
        assert (code[63:0] == f_data);           // the code stays systematic

        // C1/C2: the encoder's check_out port. Only code_out feeds the rest
        // of this proof, so without these two check_out would be an output
        // no property mentions and the solver would be free to give it any
        // value at all.
        //   C1  the two encoder outputs agree: check_out is exactly the
        //       check field of code_out. This is the port contract of
        //       hw/rtl/secded_enc.v - a consumer that reads check_out and a
        //       consumer that slices code_out must see the same 8 bits.
        //   C2  the check bits are the right ones, judged by an independent
        //       copy of the matrix: the decoder's syndrome of a word with a
        //       zeroed check field is the decoder's own recomputation of
        //       check_bits(data), and it equals check_out. This pins
        //       secded_enc's H rows to secded_dec's H rows on the check
        //       port, the same way S1..S4 pin them on the codeword path. It
        //       is the formal form of the one-hot basis sweep in
        //       hw/tb/test_secded.py.
        assert (enc_check == code[71:64]);       // C1
        assert (chk_syndrome == enc_check);      // C2
    end

    // -----------------------------------------------------------------
    // Non-vacuity: every branch above is actually reachable, and the
    // interesting mechanisms (a real data-field repair, a check-field
    // repair, detection with the data field left dirty) really happen.
    // -----------------------------------------------------------------
    always @(*) begin
        cover (f_weight == 8'd0 && !dec_sec && !dec_ded);
        cover (f_weight == 8'd1 && dec_sec && dec_data != rx[63:0]);
        cover (f_weight == 8'd1 && dec_sec && f_err[71:64] != 8'd0);
        cover (f_weight == 8'd2 && dec_ded && dec_data != f_data);
        cover (f_weight == 8'd2 && dec_ded && f_err[63:0] == 64'd0);
        cover (dec_ded && f_data != 64'd0);
        cover (dec_syndrome == 8'hFF);
        // The check port is exercised at both rails, so C1/C2 above are not
        // proven over a single constant value of enc_check.
        cover (enc_check == 8'h00 && f_data != 64'd0);
        cover (enc_check == 8'hFF);
    end

endmodule

`default_nettype wire
