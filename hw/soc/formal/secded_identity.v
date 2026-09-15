// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0
// FORMAL STAND-INS for hw/rtl/secded_enc.v and hw/rtl/secded_dec.v: the
// same module names, the same ports, and a DEGENERATE code -- one check
// bit that says "the word is non-zero", a syndrome that is the mismatch
// of that bit, no correction. Read by regfile_scrub_abs.sby INSTEAD of
// the real pair, never by any synthesis or simulation flow.
//
// WHY. regfile_scrub.sby binds the real codec and its four engines
// (yices, boolector, abc pdr, and yices again in prove) all stall at
// bmc step 4 [fact, /tmp/rfs-*.log, 2026-09-15]. Step 4 is the first
// cycle at which R1's `rdata_a_o == val` is checked on a word the file
// has stored, so the solver is being asked to relate the encoder's
// eight parity trees over the written word to the decoder's eight over
// the stored one through thirty-two scrub encoders that also read the
// storage. Parity is the textbook hard case for CDCL SAT -- a resolution
// proof of an XOR identity is exponential in the chain length, and none
// of the pinned SMT solvers carries Gaussian elimination -- so the stall
// is structural, not a matter of depth or engine. docs/63 section 11
// item 3 ranked exactly this route third and called it "most likely to
// make cycle 25 tractable".
//
// WHY NOT THE IDENTITY CODE. The first version of this file was the
// identity (no check bits, zero syndrome) and bmc FAILED at step 3 with
// every read inverted: 0x80000000 written, 0x7fffffff read, and x0
// reading 0xffffffff [fact, regfile_scrub_abs_bmc/engine_0/trace.vcd
// of that run]. The cause is in the wrapper, not the stand-in:
// ibex_regfile_secded.v's g_fast_dec read path corrects by comparing
// the syndrome against every column of H -- `mask[j] = (use_syn ==
// h_col[j])`, h_col[j] being the encoder applied to the unit vector
// 1<<j -- and flips every bit whose column matches. With an all-zero
// column set and a zero syndrome that is every bit. So the wrapper
// carries two structural assumptions about its codec that a stand-in
// must honour and the real code does by construction:
//
//   (1) every column of H is non-zero, so a zero syndrome flips nothing;
//   (2) the check word of the all-zero data word is zero, because the
//       file resets its check bits to a literal 0 (rst_chk, line ~491)
//       rather than to enc(WordZeroVal).
//
// The code below satisfies both: check = 1 iff the data word is
// non-zero, so enc(1<<j) = 1 for every j (non-zero columns, all equal --
// distinctness is only needed to LOCATE an error, and no error exists in
// the fault-free contract this job proves) and enc(0) = 0.
//
// WHAT IS AND IS NOT LOST. The codec's correctness -- dec(enc(x)) == x,
// single-bit correction, double-bit detection, on the (40,32)
// shortening the register file uses -- is proved SEPARATELY by
// regfile_secded.sby, against the real hw/rtl files. What
// regfile_scrub_abs.sby proves with this stand-in is everything the
// register file does AROUND the codec: the storage, the read
// multiplexers, the scrub pointer's walk, the write-port arbitration
// between the core and the scrub, and that a fault-free file never
// reports an error. The composition is the usual one: a property of the
// wrapper that holds for every codec satisfying dec(enc(x)) == x and
// assumptions (1) and (2) holds in particular for the real one, which
// satisfies all three. What this composition does NOT cover is any
// property that depends on the code's distance -- R4 under an injected
// upset, for instance -- and no such property is claimed by that job.
//
// The port lists below are copied from the real files; DATA_W/CHECK_W
// are accepted and ignored exactly as the real modules fix them.

`default_nettype none

module secded_enc #(
    parameter DATA_W  = 64,
    parameter CHECK_W = 8
) (
    input  wire [63:0] data_in,
    output wire [7:0]  check_out,
    output wire [71:0] code_out
);
  assign check_out = {7'h00, |data_in};
  assign code_out  = {check_out, data_in};
endmodule

module secded_dec #(
    parameter DATA_W  = 64,
    parameter CHECK_W = 8
) (
    input  wire [71:0] code_in,
    output wire [63:0] data_out,
    output wire [7:0]  syndrome,
    output wire        sec,
    output wire        ded
);
  assign data_out = code_in[63:0];
  assign syndrome = code_in[71:64] ^ {7'h00, |code_in[63:0]};
  assign sec      = 1'b0;
  assign ded      = |syndrome;
endmodule

`default_nettype wire
