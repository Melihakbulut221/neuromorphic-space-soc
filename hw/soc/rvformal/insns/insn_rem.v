// SPDX-License-Identifier: ISC
//
// Derived from riscv-formal, which is ISC-licensed. ISC requires the
// copyright and permission notice in all copies, and upstream ships them
// in COPYING rather than per file -- so they are reproduced here, because
// hw/soc/ext/ is gitignored and this file is tracked, which means this
// copy travels without upstream's.
//
//   Copyright (C) 2017  Claire Xenia Wolf <claire@yosyshq.com>
//
//   Permission to use, copy, modify, and/or distribute this software for
//   any purpose with or without fee is hereby granted, provided that the
//   above copyright notice and this permission notice appear in all
//   copies.
//
//   THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL
//   WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED
//   WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
//   AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL
//   DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR
//   PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
//   TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
//   PERFORMANCE OF THIS SOFTWARE.
//
// CORRECTED COPY of riscv-formal/insns/insn_rem.v at the commit
// hw/soc/tools.soc.mk pins. docs/63 section 7.5.
//
// Upstream's model computes an UNSIGNED remainder; this one computes a signed
// one. Everything else is byte-identical to upstream and the only edited
// lines are the ones between the two markers.
//
// THE DEFECT. Upstream writes the result as one conditional expression
// whose other branches are unsigned:
//
//     wire [XLEN-1:0] result = rs2 == 0 ? <unsigned> :
//                              <corner case> ? <unsigned> :
//                              $signed(rs1) % $signed(rs2);
//
// IEEE 1364-2005 section 5.5.1: the second and third operands of the
// conditional operator are context-determined, and the expression type
// is unsigned if EITHER of them is unsigned. The unsigned branch
// therefore demotes the third, the $signed casts do nothing, and the
// remainder is evaluated unsigned.
//
// MEASURED, on the counterexample the check produced [fact]:
//
//     rem x2, x5, x25 with rs1 = 0xFFFFB3AB (-19541) and rs2 =
//     0x50A00000 (+1352663040). Ibex returns 0xFFFFB3AB, which is
//     correct; upstream's model returns 0x0E1FB3AB, which is
//     4294947755 mod 1352663040.
//
// THE ARITHMETIC, hand-checked, so that a reader can confirm both
// answers with nothing but a calculator:
//
//     Operands. 0xFFFFB3AB is -19,541 read as signed and 4,294,947,755
//     read as unsigned (4,294,967,296 - 19,541). 0x50A00000 is
//     +1,352,663,040 either way -- its top bit is clear, so signedness
//     does not change it. Only the dividend is ambiguous here.
//
//     The signed result. Verilog's % truncates toward zero and gives
//     the remainder the sign of the dividend, which is what RISC-V
//     requires of REM. -19,541 / 1,352,663,040 = 0, so the remainder is
//     the whole dividend: -19,541 = 0xFFFFB3AB. That is Ibex's answer.
//
//     The unsigned result. 1,352,663,040 * 3 = 4,057,989,120, and
//     4,294,947,755 - 4,057,989,120 = 236,958,635 = 0x0E1FB3AB. That is
//     upstream's model's answer.
//
//     Why they differ. The same 32 bits are a small negative number and
//     a very large positive one. Signed, the dividend is smaller in
//     magnitude than the divisor, the quotient is 0, and the remainder
//     is the entire dividend. Unsigned, the dividend is the larger of
//     the two, the quotient is 3, and what is left over is a positive
//     value. The two answers share their low bits, which is the easiest
//     thing to check by eye: 1,352,663,040 * 3 = 0xF1E00000, whose
//     low 21 bits are zero, so subtracting it leaves the dividend's low
//     21 bits (0x1FB3AB) exactly as they were -- hence the common
//     0xB3AB tail on 0xFFFFB3AB and 0x0E1FB3AB. Sharing a tail is not
//     agreement: the two answers differ in exactly the bits of
//     0xFFFFB3AB ^ 0x0E1FB3AB = 0xF1E00000, the sign bit among them,
//     and a sign bit is the whole defect.
//
// and confirmed in a second, independent tool: Icarus Verilog, given
// THESE operands, evaluates upstream's conditional to 236,958,635
// (0x0E1FB3AB) and the same remainder written on its own
// self-determined wire to -19,541 (0xFFFFB3AB) -- upstream's model's
// wrong answer and Ibex's right one, from a front end that shares no
// code with Yosys [fact, iverilog 14.0 (devel) s20260301-337-ge3934871
// from the pinned oss-cad-suite-linux-x64-20260804]. Note that docs/63
// section 7.5 records its Icarus confirmation on the DIV operands only;
// the evaluation quoted here was run for this comment, on the rem
// counterexample, and is not in that document.
//
// 2026-09-09: the two numbers this paragraph used to quote, 1070592674
// and -347, were NOT this counterexample's, and the sentence claimed
// them as "its own counterexample". They belong to the DIV
// counterexample's operands, rs1 = 0xFFFFFEA5 and rs2 = 0x40100401, put
// through a remainder rather than a division: that pair gives
// 1,070,592,674 unsigned and -347 signed. The old sentence was right
// about the shape of the failure and wrong about which run it came
// from, so neither figure could be checked against the counterexample
// printed above it. It is replaced by the measurement above. The
// superseded numbers are left standing here rather than deleted, per
// the standing rule that a corrected figure stays visible.
//
// The fix is to give the signed operation its own self-determined wire,
// where nothing can demote it, and to use that wire in the conditional.
// hw/soc/flow/rvformal.sh substitutes this file for upstream's when
// RVF_INSN_FIX=1, by the same rule hw/soc/flow/ibex_sources.sh uses for
// the register file: a file list, never an edit to the checkout.
//
// This has NOT been reported upstream from inside this repository, and
// doing so is the obvious next step.

// DO NOT EDIT -- auto-generated from riscv-formal/insns/generate.py

module rvfi_insn_rem (
  input                                 rvfi_valid,
  input  [`RISCV_FORMAL_ILEN   - 1 : 0] rvfi_insn,
  input  [`RISCV_FORMAL_XLEN   - 1 : 0] rvfi_pc_rdata,
  input  [`RISCV_FORMAL_XLEN   - 1 : 0] rvfi_rs1_rdata,
  input  [`RISCV_FORMAL_XLEN   - 1 : 0] rvfi_rs2_rdata,
  input  [`RISCV_FORMAL_XLEN   - 1 : 0] rvfi_mem_rdata,
`ifdef RISCV_FORMAL_CSR_MISA
  input  [`RISCV_FORMAL_XLEN   - 1 : 0] rvfi_csr_misa_rdata,
  output [`RISCV_FORMAL_XLEN   - 1 : 0] spec_csr_misa_rmask,
`endif

  output                                spec_valid,
  output                                spec_trap,
  output [                       4 : 0] spec_rs1_addr,
  output [                       4 : 0] spec_rs2_addr,
  output [                       4 : 0] spec_rd_addr,
  output [`RISCV_FORMAL_XLEN   - 1 : 0] spec_rd_wdata,
  output [`RISCV_FORMAL_XLEN   - 1 : 0] spec_pc_wdata,
  output [`RISCV_FORMAL_XLEN   - 1 : 0] spec_mem_addr,
  output [`RISCV_FORMAL_XLEN/8 - 1 : 0] spec_mem_rmask,
  output [`RISCV_FORMAL_XLEN/8 - 1 : 0] spec_mem_wmask,
  output [`RISCV_FORMAL_XLEN   - 1 : 0] spec_mem_wdata
);

  // R-type instruction format
  wire [`RISCV_FORMAL_ILEN-1:0] insn_padding = rvfi_insn >> 16 >> 16;
  wire [6:0] insn_funct7 = rvfi_insn[31:25];
  wire [4:0] insn_rs2    = rvfi_insn[24:20];
  wire [4:0] insn_rs1    = rvfi_insn[19:15];
  wire [2:0] insn_funct3 = rvfi_insn[14:12];
  wire [4:0] insn_rd     = rvfi_insn[11: 7];
  wire [6:0] insn_opcode = rvfi_insn[ 6: 0];

`ifdef RISCV_FORMAL_CSR_MISA
  wire misa_ok = (rvfi_csr_misa_rdata & `RISCV_FORMAL_XLEN'h 1000) == `RISCV_FORMAL_XLEN'h 1000;
  assign spec_csr_misa_rmask = `RISCV_FORMAL_XLEN'h 1000;
`else
  wire misa_ok = 1;
`endif

  // REM instruction
`ifdef RISCV_FORMAL_ALTOPS
  wire [`RISCV_FORMAL_XLEN-1:0] altops_bitmask = 64'hf5b7d8538da68fa5;
  wire [`RISCV_FORMAL_XLEN-1:0] result = (rvfi_rs1_rdata - rvfi_rs2_rdata) ^ altops_bitmask;
`else
  // ---- docs/63 section 7.5: BEGIN the only edit in this file ----
  wire signed [`RISCV_FORMAL_XLEN-1:0] signed_result =
      $signed(rvfi_rs1_rdata) % $signed(rvfi_rs2_rdata);
  wire [`RISCV_FORMAL_XLEN-1:0] result = rvfi_rs2_rdata == `RISCV_FORMAL_XLEN'b0 ? rvfi_rs1_rdata :
                                         rvfi_rs1_rdata == {1'b1, {`RISCV_FORMAL_XLEN-1{1'b0}}} && rvfi_rs2_rdata == {`RISCV_FORMAL_XLEN{1'b1}} ? {`RISCV_FORMAL_XLEN{1'b0}} :
                                         signed_result;
  // ---- docs/63 section 7.5: END the only edit in this file ----
`endif
  assign spec_valid = rvfi_valid && !insn_padding && insn_funct7 == 7'b 0000001 && insn_funct3 == 3'b 110 && insn_opcode == 7'b 0110011;
  assign spec_rs1_addr = insn_rs1;
  assign spec_rs2_addr = insn_rs2;
  assign spec_rd_addr = insn_rd;
  assign spec_rd_wdata = spec_rd_addr ? result : 0;
  assign spec_pc_wdata = rvfi_pc_rdata + 4;

  // default assignments
  assign spec_trap = !misa_ok;
  assign spec_mem_addr = 0;
  assign spec_mem_rmask = 0;
  assign spec_mem_wmask = 0;
  assign spec_mem_wdata = 0;
endmodule
