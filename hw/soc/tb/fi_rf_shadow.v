// The register file's correction report, recomputed from storage.
//
// hw/soc/rtl/ibex_regfile_secded.v counts the cycles in which any of its
// three decoders -- read port a, read port b, the scrub -- saw a
// correctable syndrome, in `sec_cycles`, and the uncorrectable ones in
// `ded_cycles`. Those counters drive no port, so opt_clean deletes them
// from the netlist (docs/43 section 6.5): in silicon a corrected upset
// is indistinguishable from no upset, and on the mapped netlist the
// bench cannot read a counter that is not there.
//
// This module is the same count, made by the bench from the same
// inputs: the 31 registers' stored data and check bits, the scrub
// pointer, and the two read addresses -- all of which ARE flip-flops in
// the netlist and are read out of it by name (hw/soc/fi/gl_map.py
// generates the wiring, with the storage polarity the mapping found).
// The decoders are hw/rtl/secded_dec.v, read in place, exactly as the
// register file instantiates them.
//
// It is a bench instrument and not an operator channel, which is what
// the RTL counters were too. What it adds to the gate-level campaign is
// the CORRECTED class: without it every corrected upset would be MASKED
// and the reconciliation with docs/43 would fail on 190 records for a
// reason that has nothing to do with the netlist.
//
// The upper 32 data bits of each codeword are zero and the eighth check
// bit is zero, as in the register file (docs/43 section 6.3): the
// netlist has seven check flip-flops per register and this module
// supplies the constant.

`timescale 1ns / 1ps

module fi_rf_shadow (
    input  wire         clk_i,
    input  wire         rst_ni,
    input  wire [991:0] data_i,     // x1..x31, register i at [32*(i-1) +: 32]
    input  wire [216:0] chk_i,      // x1..x31, register i at [7*(i-1) +: 7]
    input  wire [4:0]   ptr_i,      // the scrub pointer
    input  wire [4:0]   raddr_a_i,
    input  wire [4:0]   raddr_b_i,
    output reg  [15:0]  sec_cycles_o,
    output reg  [15:0]  ded_cycles_o,
    output reg          sec_seen_o,
    output reg          ded_seen_o
);

  // THE SELECTS ARE WRITTEN OUT, NOT WRAPPED IN A FUNCTION, AND THAT IS
  // NOT A STYLE CHOICE.  The first version of this file read the array
  // through `function rdata(input [4:0] a)` and assigned
  // `wire [31:0] raw_s = rdata(ptr_i);`.  A continuous assignment is
  // sensitive to the signals that appear in its expression, and
  // `data_i` appears only INSIDE the function body -- so Icarus
  // re-evaluated the select when the ADDRESS changed and not when the
  // storage did.  The scrub port holds its pointer for as long as the
  // core is writing, which is exactly when an upset is waiting to be
  // corrected, so the shadow reported a register as clean while the
  // flip-flop under it was corrupted: docs/74 section 9.3 group A, four
  // corrections missed and two invented over 180 records, found by
  // probing the shadow's own input beside its output.  With the select
  // in the expression the assignment is sensitive to both.
  wire [31:0] raw_a = (raddr_a_i == 5'd0) ? 32'h0 : data_i[32 * (raddr_a_i - 5'd1) +: 32];
  wire [31:0] raw_b = (raddr_b_i == 5'd0) ? 32'h0 : data_i[32 * (raddr_b_i - 5'd1) +: 32];
  wire [31:0] raw_s = (ptr_i      == 5'd0) ? 32'h0 : data_i[32 * (ptr_i      - 5'd1) +: 32];
  wire [6:0]  chk_a = (raddr_a_i == 5'd0) ? 7'h0  : chk_i [7  * (raddr_a_i - 5'd1) +: 7];
  wire [6:0]  chk_b = (raddr_b_i == 5'd0) ? 7'h0  : chk_i [7  * (raddr_b_i - 5'd1) +: 7];
  wire [6:0]  chk_s = (ptr_i      == 5'd0) ? 7'h0  : chk_i [7  * (ptr_i      - 5'd1) +: 7];

  wire [63:0] out_a, out_b, out_s;
  wire [7:0]  syn_a, syn_b, syn_s;
  wire        sec_a, sec_b, sec_s, ded_a, ded_b, ded_s;

  secded_dec u_dec_a (
      .code_in  ({1'b0, chk_a, 32'h0, raw_a}),
      .data_out (out_a), .syndrome (syn_a), .sec (sec_a), .ded (ded_a));
  secded_dec u_dec_b (
      .code_in  ({1'b0, chk_b, 32'h0, raw_b}),
      .data_out (out_b), .syndrome (syn_b), .sec (sec_b), .ded (ded_b));
  secded_dec u_dec_s (
      .code_in  ({1'b0, chk_s, 32'h0, raw_s}),
      .data_out (out_s), .syndrome (syn_s), .sec (sec_s), .ded (ded_s));

  wire sec_any = sec_a | sec_b | sec_s;
  wire ded_any = ded_a | ded_b | ded_s;

  always @(posedge clk_i or negedge rst_ni)
    if (!rst_ni) begin
      sec_seen_o   <= 1'b0;
      ded_seen_o   <= 1'b0;
      sec_cycles_o <= 16'h0;
      ded_cycles_o <= 16'h0;
    end else begin
      if (sec_any) begin
        sec_seen_o <= 1'b1;
        if (~&sec_cycles_o) sec_cycles_o <= sec_cycles_o + 16'd1;
      end
      if (ded_any) begin
        ded_seen_o <= 1'b1;
        if (~&ded_cycles_o) ded_cycles_o <= ded_cycles_o + 16'd1;
      end
    end

  wire unused;
  assign unused = ^{out_a, out_b, out_s, syn_a, syn_b, syn_s};

endmodule
