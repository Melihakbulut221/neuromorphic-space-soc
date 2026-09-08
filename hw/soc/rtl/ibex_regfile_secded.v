// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// A SECDED-protected architectural register file for Ibex.
//
// =====================================================================
// WHY THIS FILE EXISTS, AND WHY IT IS SHAPED LIKE THIS
// =====================================================================
//
// docs/42-core-fault-injection.md measured the management core and
// ranked its structures by what their corruption costs. The ranking is
// close to the inverse of the flip-flop count in every place except
// one: the architectural register file is 992 of the core's 2,198
// injectable RTL bits -- 45 % -- and it carries 3.2 of the 4.9
// design-weighted percentage points of wrong-or-dead outcome, more than
// everything else in the core combined. Nothing else is close. That is
// the whole reason this file was written, and it is a measurement and
// not a preference.
//
// It is deliberately NOT a new codec. docs/38 section 8.5 declined
// SecureIbex partly because `RegFileLockstepECC` would put a second
// SECDED implementation on a die that already carries this project's
// own, and called two independent implementations of one idea "a
// maintenance and verification cost, not a redundancy benefit". That
// argument is still good and this file obeys it: the encoder and the
// decoder below are hw/rtl/secded_enc.v and hw/rtl/secded_dec.v, READ
// in place and not copied, the same (72,64) Hsiao code that
// sw/golden/secded.py models, hw/tb/test_secded.py cross-checks and
// formal/secded.sby proves. Nothing in hw/rtl is modified.
//
// AND THE OTHER HALF OF THAT ARGUMENT, STATED SO A READER OF docs/38
// DOES NOT THINK WE FORGOT IT. docs/38 section 10 item 4 declined
// lockstep, and the reason it gave for the register file specifically
// was duplication, not futility. Building register-file protection here
// is not a reversal of that decision, and the distinction is exactly the
// one docs/38 section 8.5 drew for itself:
//
//   * Lockstep DETECTS. A shadow core comparing outputs announces a
//     divergence; it does not produce the right answer, and the
//     recovery policy that would have to follow the announcement is
//     still not written.
//   * This CORRECTS. A single-bit upset in a register is repaired on
//     the way out and scrubbed out of the storage, and the program
//     never sees it.
//
// So the overlap docs/38 objected to was one codec against another, and
// there is still only one codec. What has changed is that the cost is
// now known: +112 % core area for detection, against this, for
// correction, over the 45 % of the core's flip-flops that carry most of
// its measured failure rate.
//
// =====================================================================
// THE SUBSTITUTION, AND WHAT IT COSTS
// =====================================================================
//
// `ibex_top` selects among `ibex_register_file_ff`, `_fpga` and
// `_latch` by the `RegFile` parameter, in a generate chain with no
// default branch. This module therefore carries UPSTREAM'S MODULE NAME
// AND UPSTREAM'S PORT LIST, and the substitution is made by giving the
// build this file INSTEAD OF hw/soc/gen/ibex_register_file_ff.v.
// Nothing in hw/soc/ext/ibex changes, nothing in hw/soc/gen changes,
// nothing in soc_top.v changes; the choice of register file is a file
// list and not an edit.
//
// docs/38 section 4.2 makes "patches required to Ibex: zero" a headline
// and it is load-bearing -- it is why upstream tracking is cheap and
// why the sv2v claim is clean. That claim SURVIVES this file, because
// the claim is about the checkout and the checkout is untouched. What
// does not survive is the weaker sentence a reader might infer from it:
// this build is no longer bit-for-bit the Ibex the pinned commit
// describes. docs/43 section 3 states the four costs in full. The two
// that live in this file are:
//
//   1. IF UPSTREAM CHANGES THIS INTERFACE, this module is wrong. A port
//      added or removed fails at elaboration, loudly, because every
//      connection in ibex_top.v is by name. A port whose MEANING
//      changes without its name changing does not, and that is the real
//      exposure. sw/tests/test_soc_regfile_guards.py reads the port
//      list and the parameter list out of the pristine sv2v output and
//      fails if either has moved, so the first case is caught at test
//      time as well as at build time; the second is caught by nothing
//      here and is named in docs/43 section 3 as an accepted risk.
//   2. THIS FILE IS OUTSIDE THE PINNED SET. hw/soc/ext/ibex is pinned by
//      commit and hw/soc/gen is generated from it; this is neither. It
//      is ordinary tracked RTL of this project, reviewed and tested as
//      such, and it must be re-read against upstream whenever the pin
//      moves. That obligation is real and it did not exist before.
//
// The module supports exactly the configuration this SoC builds --
// BaseIsa = RV32I, RV32E = 0, DataWidth = 32, DummyInstructions = 0 --
// and refuses anything else at elaboration rather than quietly building
// a different register file. Upstream's file covers configurations this
// one does not, and pretending otherwise is how a substitution becomes
// a silent divergence.
//
// =====================================================================
// THE CODE, AND WHY (72,64) AND NOT (39,32)
// =====================================================================
//
// The registers are 32 bits and the codec is fixed at 64 data bits and
// 8 check bits; both facts are given. There were two ways to reconcile
// them and the choice is worth writing down.
//
//   PAIRING two architectural registers into one 64-bit codeword needs
//   about 128 check flip-flops, against the 217 this one costs in the
//   mapped netlist -- see the note on the eighth check bit below -- and
//   it was rejected for two reasons. A write to one register of a pair
//   would have to re-encode over the other, so the write path would
//   carry a decode as well as an encode; and, worse, two architectural
//   registers would share a codeword, so an upset in x8 and an upset in
//   x9 would be a DOUBLE error -- detected and NOT corrected -- where
//   here they are two independent single errors. Pairing buys about 89
//   flip-flops by making two registers share a fate.
//
//   ONE CODEWORD PER REGISTER, with the codec's upper 32 data bits tied
//   to zero, is what is built. The tie-off is a constant the synthesiser
//   folds, so what is actually built is the (40,32) shortening of the
//   same Hsiao code: the eight XOR trees keep only their low halves and
//   the decoder keeps only the columns of the bits that exist. The
//   shortening is safe for exactly the reason the code is safe -- all 72
//   columns of H are distinct, nonzero and of odd weight, so any 40 of
//   them are too -- and a single error among the 40 stored bits produces
//   the syndrome of its own column and nothing else. NO PARAMETER OF
//   THE CODEC IS OVERRIDDEN: both modules carry an elaboration guard
//   that refuses any width but 72/64, and this file passes 64 and 8.
//
// =====================================================================
// CORRECT ON READ, AND SCRUB, AND WHY BOTH
// =====================================================================
//
// Correction on read alone would repair the value the program sees and
// leave the corruption in the flip-flop. docs/41 section 5.1 made the
// same argument about the watchdog's protected word and it is stronger
// here: a register a program writes once and reads for the rest of the
// run -- a loop bound, a base pointer, a callee-saved register held
// across a long call -- keeps an upset for as long as it holds its
// value, and the SECOND upset in that word is uncorrectable.
//
// So there is a scrub. A pointer walks x1..x31; on every cycle in which
// the core is NOT writing the file, the register it points at is
// decoded, re-encoded from the corrected value, and written back, and
// the pointer advances. On cycles when the core writes, the scrub
// stalls and the pointer HOLDS -- it does not skip -- so no register is
// passed over, and the register the core wrote was re-encoded by that
// write in any case.
//
// The scrub and the core writes share one encoder and one write port,
// which is why the scrub stalls rather than proceeding in parallel: a
// second write port would need a 40-bit two-input multiplexer in front
// of all 31 registers and it would cost more than the protection.
//
// WHAT THE SCRUB DOES NOT PROMISE. Its period is data-dependent. It is
// 31 cycles when the core is not writing and it is unbounded in the
// limit of a program that writes the register file on every cycle
// forever -- which no real program does, because Ibex cannot retire a
// writing instruction every cycle indefinitely, but this file does not
// prove that and neither does anything else in this repository. It is
// NOT measured either, and docs/43 section 10 lists it among the things
// this work leaves unbounded rather than closed.
//
// =====================================================================
// THE CORRECTION IS IN SERIES WITH THE ALU, SO ITS DEPTH IS THE PRICE
// =====================================================================
//
// The decoder is on the register read path and the register read path
// feeds the ALU, so unlike a shadow core -- which runs in PARALLEL with
// what it checks -- this runs in SERIES with it. Every gate level of the
// decoder is a gate level the whole design pays for.
//
// HOW MUCH, MEASURED. docs/43 section 7.4 priced this by subtracting two
// whole-core setup slacks, and docs/44 section 5.1 shows why that
// subtraction could not carry the attribution: the path it measured
// starts at a configuration input soc_top.v ties to a constant. The
// number that does carry it comes from hw/soc/flow/sta_regfile.sh, which
// times this module alone, where nothing else can move: at the slow
// corner the arrival at rdata_a_o goes from 5.5282 ns at HARDEN = 0 to
// 8.3210 ns with docs/43's read path. THE CODEC COSTS 2.7928 ns.
//
// FASTCORR = 1 removes the levels that are on that path FOR NO REASON,
// and MEASURED, it recovers 0.2593 ns of the 2.7928 -- 9.3 % -- for
// +1,201.5486 um2 and +128 cells on this module. That is a small
// recovery and it is quoted here rather than rounded up, because the
// alternative that recovers 66.9 % is SYNPRE below and it costs
// twenty-six times as much area. hw/rtl/secded_dec.v computes
//
//     data_out = sec ? (data_raw ^ corr_mask) : data_raw
//
// and `sec` is `syn_nonzero && syn_odd && (data_hit || check_hit)`,
// where `data_hit` is a 64-wide OR of the column comparisons and
// `check_hit` contains an eight-bit subtract. That qualification is
// correct and it is also, on the DATA path, redundant:
//
//     corr_mask[j] = 1  =>  syndrome equals H column j
//                    =>  syndrome is nonzero (no column is zero)
//                    and syndrome has odd parity (every column has odd
//                        weight, which is what makes this code SECDED)
//                    and data_hit = 1
//                    =>  sec = 1.
//
// So `sec` is 1 whenever the mask is nonzero, and when the mask is zero
// both arms of the multiplexer are `data_raw`. `data_raw ^ corr_mask` is
// therefore BIT-FOR-BIT the same function as `data_out`, for every input
// -- and it does not wait for the 64-wide OR, the subtract, the AND that
// joins them or the multiplexer they select. hw/soc/formal/
// regfile_secded.sby task `prove_fast` states that equality over a free
// codeword and refuses to be believed on the strength of the paragraph
// above.
//
// WHY THE MASK IS DERIVED AND NOT WRITTEN DOWN. Computing the mask here
// needs the H columns, and hw/rtl/secded_dec.v does not export them.
// Writing the matrix into this file a second time is exactly the
// duplication docs/38 section 8.5 refused and docs/43 section 6.1
// promised not to commit, and it would be the worst kind: two copies of
// a constant that must agree and that no build step compares. So the
// columns are DERIVED, from the pilot's own encoder, using its
// definition: the H column of data bit j is the check word of the unit
// vector 1<<j. Thirty-two `secded_enc` instances on constant inputs are
// a compile-time table; the synthesiser folds every one of them and
// sw/tests/test_soc_regfile_guards.py asserts that the mapped netlist is
// not one cell larger for them. If hw/rtl/secded_enc.v ever changed, the
// columns here would change with it, which is the property a written-out
// copy cannot have.
//
// WHAT FASTCORR DOES NOT TOUCH. The scrub still writes back
// `u_dec_s.data_out`, unaltered, because the scrub is not on the read
// path and the write-back is the one place where being literally the
// frozen decoder's output is worth more than the levels it costs.
// `sec`, `ded` and the syndrome still come from the frozen decoder for all
// three ports; what FASTCORR replaces is the DATA output of the two read
// ports and nothing else.
//
// FASTCORR = 0 builds the read path docs/43 measured, so the recovery
// is priced against the same file with one parameter moved -- the
// discipline docs/41 section 6.5 records the cost of not keeping.
//
// =====================================================================
// THE REPORT NOW HAS SOMEWHERE TO GO, AND WHAT THAT COST
// =====================================================================
//
// As docs/43 shipped this file, the counters below recorded what the
// codec did and NOTHING READ THEM: the substituted module carried
// upstream's port list, upstream's port list has no error output, and
// adding one is a patch to ibex_top. docs/43 section 6.5 stated the
// consequence plainly -- the correction was SILENT, and in silicon a
// corrected upset and no upset were the same event.
//
// docs/44 closes that, because an unobservable correction is
// indistinguishable from an absent one at any distance greater than a
// simulator. `rf_ecc_err_o` is this project's own port, appended AFTER
// upstream's list, and it is carried out of `ibex_top` by the smallest
// patch that reaches the SoC: three hunks in ONE generated file, applied
// mechanically by hw/soc/flow/ibex_fault_port.py, never edited by hand
// and never committed. docs/44 section 4 states what that costs the
// pinning story; the two costs that live in this file are that the port
// list is no longer upstream's exactly -- it is upstream's followed by
// one port of ours -- and that
// sw/tests/test_soc_regfile_guards.py's port check has been weakened
// from equality to "upstream's list is a prefix" to admit it.
//
// WHAT THE THREE BITS MEAN, because a counter whose unit is ambiguous
// is a number that gets quoted wrongly:
//
//   [0] SEC_SCRUB  the SCRUB corrected a word, and the corrected word
//                  is being written back on this cycle. This is the bit
//                  to count for an upset RATE: the walk reaches every
//                  register, so a single-bit upset that the program does
//                  not overwrite first raises this EXACTLY ONCE.
//   [1] SEC_READ   a read port corrected the word it returned, on this
//                  cycle. This is a count of CYCLES and not of upsets:
//                  the same corrupted register read on ten cycles before
//                  the scrub reaches it raises this ten times, and both
//                  ports reading it raises it once. It is an upper
//                  bound on the number of upsets and a lower bound on
//                  nothing.
//   [2] DED        a read port or the scrub reported a syndrome it
//                  cannot correct. Two upsets in one register between
//                  two scrubs is the case this exists for.
//
// The internal counters are KEPT even though the port makes them
// redundant in silicon: hw/soc/tb/tb_soc_fi.v reads them hierarchically
// and docs/43's campaign is reported off them, so removing them would
// break the comparison that makes the campaign delta a delta. They still
// drive nothing, so `opt_clean` still deletes them and they still cost
// no area -- what has changed is that the port beside them does not.
//
// =====================================================================
// WHAT THIS DOES NOT PROTECT
// =====================================================================
//
//   * x0. It has no flip-flops in this configuration and never did.
//   * The read and write ADDRESSES. `raddr_a_i`, `raddr_b_i` and
//     `waddr_a_i` come from the decoder and are unprotected there; a
//     corrupted address reads or writes the wrong register with a
//     perfectly valid codeword, and no code over the data can see it.
//     docs/42's `if_id` and `id_ctrl` strata are where those bits live
//     and they are still measured at their unprotected rate.
//   * Anything else in the core. This is 45 % of its flip-flops and no
//     more; the controller, the fetch FIFO and the load/store FSM are
//     untouched, and docs/42 section 6.3 shows they carry the highest
//     per-bit rates in the design.
//   * Two upsets in one register between two scrubs. The decoder
//     reports those as uncorrectable rather than miscorrecting them --
//     that is what the odd column weight buys -- but reporting is all
//     it can do, and there is nowhere for the report to go.

`timescale 1ns / 1ps
`default_nettype none

module ibex_register_file_ff (
    clk_i,
    rst_ni,
    test_en_i,
    dummy_instr_id_i,
    dummy_instr_wb_i,
    cheriot_enable_i,
    raddr_a_i,
    rdata_a_o,
    rcap_a_o,
    raddr_b_i,
    rdata_b_o,
    rcap_b_o,
    waddr_a_i,
    wdata_a_i,
    wcap_a_i,
    we_a_i,
    // ---- this project's, APPENDED after upstream's list ------------
    // Everything above this line is upstream's port list in upstream's
    // order, which is what sw/tests/test_soc_regfile_guards.py checks.
    // Everything below it is this project's, and it reaches the SoC
    // only through the ibex_top patch of hw/soc/flow/ibex_fault_port.py.
    rf_ecc_err_o
);

  // ---- upstream's parameters, in upstream's order and encodings -----
  // ibex_top.v overrides five of these by name. The two capability
  // parameters are not overridden at BaseIsa = RV32I and are here so
  // that the port widths match ibex_top's nets.
  parameter integer BaseIsa = 32'sd0;
  parameter [0:0]   RV32E = 0;
  parameter [31:0]  DataWidth = 32;
  parameter [0:0]   DummyInstructions = 0;
  // Upstream writes these two defaults as `1'sb0`, a SIGNED one-bit
  // zero that the elaborator extends. The value is identical and the
  // form is not: Verilator's WIDTHEXPAND fires on upstream's spelling,
  // and this file is linted rather than waived. `ibex_top` overrides
  // WordZeroVal at every instantiation, so what is written here is the
  // default the STANDALONE measurements of docs/43 section 7.2 use.
  parameter [DataWidth - 1:0] WordZeroVal = {DataWidth{1'b0}};
  localparam [31:0] ibex_cheriot_pkg_REGCAP_W = 35;
  parameter [31:0]  CapWidth = ibex_cheriot_pkg_REGCAP_W;
  parameter [CapWidth - 1:0] CapWordZeroVal = {CapWidth{1'b0}};

  // ---- this project's parameters, which upstream never sets --------
  // HARDEN = 0 builds the plain register file, bit for bit what
  // hw/soc/gen/ibex_register_file_ff.v builds at these parameters. It
  // exists so the area of the protection is measured against THE SAME
  // FILE rather than against the upstream one: docs/41 section 6.5
  // records a cost understated by crediting the hardening with a saving
  // a refactor made, and the way not to repeat that is to have both
  // configurations in one source. docs/43 section 7 measures all three
  // -- upstream, HARDEN = 0 and HARDEN = 1 -- and reports the first
  // difference as the refactor rather than as the hardening.
  parameter integer HARDEN = 1;
  // SCRUB = 0 keeps correction on read and removes the walking
  // write-back, so what the scrub costs is separable from what the code
  // costs.
  parameter integer SCRUB = 1;
  // FASTCORR = 0 restores the read path docs/43 section 7.4 measured:
  // the frozen decoder's own `data_out`, multiplexer and all. It exists
  // so the timing recovery is priced against the same source with one
  // parameter moved, and so docs/43's numbers stay reproducible.
  parameter integer FASTCORR = 1;
  // SYNPRE = 1 computes the syndrome of EVERY register beside its own
  // flip-flops and multiplexes the seven-bit result, instead of
  // multiplexing the forty-bit codeword and computing one syndrome
  // after it. The syndrome is a linear function of the stored word and
  // the multiplexer is a selection, so the two orders compute the same
  // thing; what changes is that the XOR tree runs IN PARALLEL with the
  // read multiplexer instead of behind it.
  //
  // It costs 31 more encoder instances -- one whole parity tree per
  // register -- and it is the only structural way to take the tree off
  // the read path, because hiding k levels of a tree behind a
  // multiplexer needs 2^k copies of it and the tree is four levels
  // deep.
  //
  // THIS IS A MEASUREMENT CONFIGURATION AND NOTHING BUILDS IT. It is
  // here so that "the syndrome tree could be hoisted" is a number in
  // docs/44 section 5.5 rather than a suggestion, and the number is what
  // keeps the default at 0. Same role as HARDEN = 0 and SCRUB = 0:
  // hw/soc/flow/syn_regfile.sh measures it, sw/tests checks that no
  // build sets it, and it is not a feature.
  parameter integer SYNPRE = 0;

  input  wire                  clk_i;
  input  wire                  rst_ni;
  input  wire                  test_en_i;
  input  wire                  dummy_instr_id_i;
  input  wire                  dummy_instr_wb_i;
  input  wire [3:0]            cheriot_enable_i;
  input  wire [4:0]            raddr_a_i;
  output wire [DataWidth-1:0]  rdata_a_o;
  output wire [CapWidth-1:0]   rcap_a_o;
  input  wire [4:0]            raddr_b_i;
  output wire [DataWidth-1:0]  rdata_b_o;
  output wire [CapWidth-1:0]   rcap_b_o;
  input  wire [4:0]            waddr_a_i;
  input  wire [DataWidth-1:0]  wdata_a_i;
  input  wire [CapWidth-1:0]   wcap_a_i;
  input  wire                  we_a_i;
  // {DED, SEC_READ, SEC_SCRUB}; see the header for what each one counts.
  output wire [2:0]            rf_ecc_err_o;

  localparam integer NUM_WORDS = 32;
  localparam integer CHK_W     = 8;

  genvar gi;
  genvar gj;

  // Elaboration guards, aer_fifo house style: a configuration this file
  // does not implement references a module that deliberately does not
  // exist, so the build stops with the reason in the message instead of
  // silently producing a register file that is not the one asked for.
  generate
    if (BaseIsa != 32'sd0) begin : g_no_cheriot
      ERROR_ibex_regfile_secded_does_not_implement_the_CHERIoT_file guard ();
    end
    if (RV32E != 1'b0) begin : g_no_rv32e
      ERROR_ibex_regfile_secded_does_not_implement_RV32E guard ();
    end
    if (DataWidth != 32) begin : g_bad_width
      ERROR_ibex_regfile_secded_is_fixed_at_32_bit_registers guard ();
    end
    if (DummyInstructions != 1'b0) begin : g_no_dummy
      ERROR_ibex_regfile_secded_does_not_implement_dummy_instructions guard ();
    end
    // The reset image has to BE a codeword, and this file spends no
    // logic checking that it is: it relies on the encoding of the
    // all-zero word being the all-zero codeword, which is true of any
    // linear systematic code and therefore of this one. Any other
    // WordZeroVal would need its check bits computed, so any other
    // WordZeroVal stops the build.
    if (WordZeroVal != {DataWidth{1'b0}}) begin : g_bad_reset_image
      ERROR_ibex_regfile_secded_needs_a_zero_WordZeroVal guard ();
    end
  endgenerate

  // Ports this configuration does not use, tied off exactly as
  // upstream's file ties them off so the lint result is the same.
  wire unused_test_en;
  assign unused_test_en = test_en_i;
  wire unused_dummy_instr;
  assign unused_dummy_instr = dummy_instr_id_i ^ dummy_instr_wb_i;
  wire unused_wcap_a;
  assign unused_wcap_a = ^wcap_a_i;
  wire unused_cheriot_enable;
  assign unused_cheriot_enable = ^cheriot_enable_i;
  assign rcap_a_o = CapWordZeroVal;
  assign rcap_b_o = CapWordZeroVal;

  // ===================================================================
  // The file
  // ===================================================================
  //
  // The generate-block and instance names below are upstream's --
  // `g_plain_rf`, `g_rf_flops[i]`, `rf_reg_q` -- and that is deliberate
  // rather than incidental. hw/soc/fi/targets.py names every
  // architectural register by its hierarchical path, and docs/42's
  // campaign drew 100 injections into those paths. Keeping the names
  // means the hardened campaign injects into THE SAME PATHS, so the two
  // campaigns are comparable draw by draw instead of only in aggregate.
  generate
  if (BaseIsa == 32'sd0) begin : g_plain_rf

    // The check bits of the reset image.
    //
    // This is a written-down constant and it is allowed to be one for a
    // reason that is a theorem rather than an observation: the code is
    // LINEAR and systematic, so the encoding of the all-zero data word
    // is the all-zero codeword, for any parity-check matrix whatever.
    // What is NOT allowed is assuming the reset image is zero, so the
    // guard above refuses any other WordZeroVal instead of quietly
    // producing a reset state that is not a codeword -- which would
    // make the first read after reset report an uncorrectable error.
    //
    // The alternative, an encoder instance on the constant, was tried
    // and rejected: yosys reports "async reset value is not constant"
    // for a reset image driven by a cell, and a flip-flop whose reset
    // value the synthesiser cannot fold is not the flip-flop this file
    // means to build.
    wire [CHK_W-1:0] rst_chk = {CHK_W{1'b0}};

    // ---- the write port, shared by the core and the scrub ----------
    wire             scrub_go;
    wire [4:0]       scrub_ptr;
    wire [31:0]      scrub_data;

    wire             wr_en   = we_a_i | scrub_go;
    wire [4:0]       wr_addr = we_a_i ? waddr_a_i : scrub_ptr;
    wire [31:0]      wr_data = we_a_i ? wdata_a_i : scrub_data;

    // One encoder for both. In the core's case it encodes the value the
    // pipeline is writing; in the scrub's case it re-encodes the
    // CORRECTED value the decoder produced, which is what repairs a
    // corrupted check bit as well as a corrupted data bit.
    wire [CHK_W-1:0] wr_chk;
    wire [71:0]      wr_code_unused;
    secded_enc u_enc_wr (
        .data_in   ({32'h0, wr_data}),
        .check_out (wr_chk),
        .code_out  (wr_code_unused)
    );

    // A one-hot shift rather than upstream's comparison loop, which is
    // the same function written so that no loop variable has to be
    // part-selected: `wr_addr` is exactly five bits and NUM_WORDS is
    // exactly 32, so the shift cannot leave the word.
    wire [NUM_WORDS-1:0] we_a_dec =
        wr_en ? ({{NUM_WORDS-1{1'b0}}, 1'b1} << wr_addr)
              : {NUM_WORDS{1'b0}};
    wire unused_strobe;
    assign unused_strobe = we_a_dec[0];

    // ---- the storage ----------------------------------------------
    // 40 bits per register: upstream's 32 in `rf_reg_q`, at upstream's
    // path, plus 8 check bits beside them. The check flip-flops are
    // inside their own generate block so that HARDEN = 0 does not build
    // them at all -- a baseline that carried 248 dead flip-flops would
    // understate the cost of the protection, which is the direction
    // docs/41 section 6.5 says to be careful about.
    wire [31:0]      rf_data [0:NUM_WORDS-1];
    wire [CHK_W-1:0] rf_chk  [0:NUM_WORDS-1];

    for (gi = 1; gi < NUM_WORDS; gi = gi + 1) begin : g_rf_flops
      reg [31:0] rf_reg_q;
      always @(posedge clk_i or negedge rst_ni)
        if (!rst_ni)
          rf_reg_q <= WordZeroVal;
        else if (we_a_dec[gi])
          rf_reg_q <= wr_data;
      assign rf_data[gi] = rf_reg_q;

      if (HARDEN != 0) begin : g_chk
        reg [CHK_W-1:0] rf_chk_q;
        always @(posedge clk_i or negedge rst_ni)
          if (!rst_ni)
            rf_chk_q <= rst_chk;
          else if (we_a_dec[gi])
            rf_chk_q <= wr_chk;
        assign rf_chk[gi] = rf_chk_q;
      end else begin : g_no_chk
        assign rf_chk[gi] = rst_chk;
      end
    end

    // x0 has no storage in this configuration, and its codeword is the
    // encoding of the zero word so that a read of it decodes clean.
    assign rf_data[0] = WordZeroVal;
    assign rf_chk[0]  = rst_chk;

    // ---- the read ports --------------------------------------------
    wire [31:0]      raw_a = rf_data[raddr_a_i];
    wire [CHK_W-1:0] chk_a = rf_chk[raddr_a_i];
    wire [31:0]      raw_b = rf_data[raddr_b_i];
    wire [CHK_W-1:0] chk_b = rf_chk[raddr_b_i];

    if (HARDEN != 0) begin : g_secded

      wire [63:0]      out_a, out_b, out_s;
      wire [CHK_W-1:0] syn_a, syn_b, syn_s;
      wire             sec_a, sec_b, sec_s;
      wire             ded_a, ded_b, ded_s;

      secded_dec u_dec_a (
          .code_in  ({chk_a, 32'h0, raw_a}),
          .data_out (out_a), .syndrome (syn_a),
          .sec (sec_a), .ded (ded_a));
      secded_dec u_dec_b (
          .code_in  ({chk_b, 32'h0, raw_b}),
          .data_out (out_b), .syndrome (syn_b),
          .sec (sec_b), .ded (ded_b));

      // ---- the correction, and the levels it does not wait for ----
      //
      // See the header. `data_raw ^ corr_mask` is bit-for-bit
      // `data_out`, and it does not wait for the 64-wide OR, the
      // subtract or the multiplexer that qualify it.
      //
      // The columns are the pilot encoder's own, evaluated on the unit
      // vectors. Nothing here writes H down a second time; if
      // hw/rtl/secded_enc.v changed, these would change with it.
      if (FASTCORR != 0) begin : g_fast
        wire [CHK_W-1:0] h_col [0:31];
        wire [31:0]      mask_a, mask_b;

        // SYNPRE = 1 moves the syndrome's XOR tree to the OTHER SIDE of
        // the read multiplexer. See the parameter's own comment: it is a
        // MEASUREMENT CONFIGURATION and not a shipped one, and
        // docs/44 section 5.5 gives the number that keeps it at 0.
        wire [CHK_W-1:0] use_syn_a, use_syn_b;
        if (SYNPRE != 0) begin : g_synpre
          wire [CHK_W-1:0] rf_syn [0:NUM_WORDS-1];
          for (gj = 0; gj < NUM_WORDS; gj = gj + 1) begin : g_pre
            wire [CHK_W-1:0] chk_calc;
            wire [71:0]      pre_code_unused;
            secded_enc u_pre (
                .data_in   ({32'h0, rf_data[gj]}),
                .check_out (chk_calc),
                .code_out  (pre_code_unused));
            assign rf_syn[gj] = chk_calc ^ rf_chk[gj];
          end
          assign use_syn_a = rf_syn[raddr_a_i];
          assign use_syn_b = rf_syn[raddr_b_i];
        end else begin : g_synpost
          assign use_syn_a = syn_a;
          assign use_syn_b = syn_b;
        end

        for (gj = 0; gj < 32; gj = gj + 1) begin : g_col
          wire [71:0] col_code_unused;
          secded_enc u_col (
              .data_in   ({32'h0, {{31{1'b0}}, 1'b1} << gj}),
              .check_out (h_col[gj]),
              .code_out  (col_code_unused));
          assign mask_a[gj] = (use_syn_a == h_col[gj]);
          assign mask_b[gj] = (use_syn_b == h_col[gj]);
        end

        assign rdata_a_o = raw_a ^ mask_a;
        assign rdata_b_o = raw_b ^ mask_b;
      end else begin : g_dec_out
        // docs/43's read path, kept so the recovery is measured against
        // the same file rather than against a previous document's
        // number.
        assign rdata_a_o = out_a[31:0];
        assign rdata_b_o = out_b[31:0];
      end

      // ---- the scrub ----------------------------------------------
      if (SCRUB != 0) begin : g_scrub
        reg [4:0] ptr_q;
        wire [31:0]      raw_s = rf_data[ptr_q];
        wire [CHK_W-1:0] chk_s = rf_chk[ptr_q];

        secded_dec u_dec_s (
            .code_in  ({chk_s, 32'h0, raw_s}),
            .data_out (out_s), .syndrome (syn_s),
            .sec (sec_s), .ded (ded_s));

        // The core owns the write port. The scrub takes the cycles the
        // core leaves, and the pointer HOLDS when it cannot write, so
        // the walk skips nothing.
        assign scrub_go   = !we_a_i;
        assign scrub_ptr  = ptr_q;
        assign scrub_data = out_s[31:0];

        always @(posedge clk_i or negedge rst_ni)
          if (!rst_ni)          ptr_q <= 5'd1;
          else if (scrub_go)    ptr_q <= (ptr_q == 5'd31) ? 5'd1
                                                          : ptr_q + 5'd1;
      end else begin : g_no_scrub
        assign scrub_go   = 1'b0;
        assign scrub_ptr  = 5'd0;
        assign scrub_data = 32'h0;
        assign out_s = 64'h0;
        assign syn_s = {CHK_W{1'b0}};
        assign sec_s = 1'b0;
        assign ded_s = 1'b0;
      end

      // ---- the report ---------------------------------------------
      //
      // `rf_ecc_err_o` is the operator channel and the four registers
      // below are the bench one. See the header for what each bit
      // counts and why they are not the same number.
      //
      // SEC_SCRUB is gated on `scrub_go` and not on `sec_s` alone, and
      // that gate is the whole reason this bit is a count of UPSETS
      // rather than of cycles: `u_dec_s` decodes the register the
      // pointer names on every cycle, including the cycles the core is
      // writing and the scrub is stalled, so an ungated `sec_s` would
      // report the same upset once per stalled cycle. Gated, it reports
      // once -- on the cycle the corrected word is written back, which
      // is also the cycle after which the upset is gone.
      wire sec_scrub_ev = sec_s & scrub_go;
      wire ded_scrub_ev = ded_s & scrub_go;
      assign rf_ecc_err_o = {ded_a | ded_b | ded_scrub_ev,
                             sec_a | sec_b,
                             sec_scrub_ev};
      //
      // `sec_cycles` counts CYCLES IN WHICH A CORRECTION HAPPENED and
      // not corrections: a cycle in which both read ports and the scrub
      // all correct the same corrupted register counts once. The name
      // says so because a counter whose unit is ambiguous is a number
      // that gets quoted wrongly.
      wire sec_any = sec_a | sec_b | sec_s;
      wire ded_any = ded_a | ded_b | ded_s;

      reg        sec_seen;
      reg        ded_seen;
      reg [15:0] sec_cycles;
      reg [15:0] ded_cycles;
      always @(posedge clk_i or negedge rst_ni)
        if (!rst_ni) begin
          sec_seen   <= 1'b0;
          ded_seen   <= 1'b0;
          sec_cycles <= 16'h0;
          ded_cycles <= 16'h0;
        end else begin
          if (sec_any) begin
            sec_seen <= 1'b1;
            if (~&sec_cycles) sec_cycles <= sec_cycles + 16'd1;
          end
          if (ded_any) begin
            ded_seen <= 1'b1;
            if (~&ded_cycles) ded_cycles <= ded_cycles + 16'd1;
          end
        end

      wire unused_syndromes;
      assign unused_syndromes = ^{syn_a, syn_b, syn_s,
                                  out_a, out_b, out_s};

    end else begin : g_plain
      // HARDEN = 0. Upstream's behaviour, from this file, for the area
      // baseline. The check flip-flops still exist in the RTL but
      // nothing reads them, so the optimiser removes them and the
      // count is upstream's -- which is the point: the same source,
      // measured twice.
      assign rdata_a_o    = raw_a;
      assign rdata_b_o    = raw_b;
      assign scrub_go     = 1'b0;
      assign scrub_ptr    = 5'd0;
      assign scrub_data   = 32'h0;
      // No code, nothing to report. The port stays, so the SoC above
      // wires the same way at both settings and the BUSSTAT counters
      // read zero instead of failing to elaborate.
      assign rf_ecc_err_o = 3'b000;
    end

  end
  endgenerate

`ifdef FORMAL
`include "ibex_regfile_secded_props.v"
`endif

endmodule

`default_nettype wire
