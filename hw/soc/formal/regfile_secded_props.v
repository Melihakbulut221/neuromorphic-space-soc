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
    end

    // Vacuity, docs/09 B.1: every branch above has to be reachable, or
    // the job proves nothing about the cases it claims to cover.
    always @(posedge clk_i) begin
        cover (w == 7'd0);
        cover (w == 7'd1 && sec && (e_i[31:0] != 32'h0));   // a data bit
        cover (w == 7'd1 && sec && (e_i[39:32] != 8'h0));   // a check bit
        cover (w == 7'd2 && ded);
        cover (w == 7'd3);
    end

endmodule

`default_nettype wire
