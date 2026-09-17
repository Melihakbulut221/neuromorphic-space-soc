// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// The SECDED register file behind upstream's port list exactly.
//
// WHY THIS EXISTS. `docs/43` substitutes `hw/soc/rtl/ibex_regfile_secded.v`
// for the vendored `ibex_register_file_ff` by FILE SWAP: same module
// name, same parameters, and -- almost -- the same ports. Almost is the
// word that matters. The substituted file adds one output,
// `rf_ecc_err_o`, so an equivalence check of the two refuses to combine
// them: "No matching port in gold module was found for \rf_ecc_err_o".
//
// That extra port is not a defect and must not be deleted; it is how the
// file reports a correction to `soc_scrub`. What it means is that the
// two modules are not interface-identical, so the equivalence question
// has to be asked about the PART that is: the sixteen ports upstream
// has. This shim is that restriction, written out rather than hidden in
// a tool flag, and the port list below is upstream's own, in upstream's
// order.
//
// WHAT THE CHECK THIS FEEDS CAN AND CANNOT SAY. With `SCRUB = 0` the
// scrub walker is off and the file is a register file with an encoder on
// the write path and a decoder on the read path. If the two agree there,
// the encoding round-trips for every word and every address, which is
// the claim the substitution rests on. It says nothing about the scrub
// -- `hw/soc/formal/regfile_scrub_abs.sby` is that proof -- and nothing
// about behaviour under an injected upset, which is a property of the
// code's distance and is claimed nowhere.

`default_nettype none

module regfile_shim #(
    parameter integer BaseIsa = 32'sd0,
    parameter [0:0]   RV32E = 0,
    parameter [31:0]  DataWidth = 32,
    parameter [0:0]   DummyInstructions = 0,
    parameter [31:0]  CapWidth = 1,
    parameter integer SCRUB = 0
) (
    input  wire                   clk_i,
    input  wire                   rst_ni,
    input  wire                   test_en_i,
    input  wire                   dummy_instr_id_i,
    input  wire                   dummy_instr_wb_i,
    input  wire [3:0]             cheriot_enable_i,
    input  wire [4:0]             raddr_a_i,
    output wire [DataWidth-1:0]   rdata_a_o,
    output wire [CapWidth-1:0]    rcap_a_o,
    input  wire [4:0]             raddr_b_i,
    output wire [DataWidth-1:0]   rdata_b_o,
    output wire [CapWidth-1:0]    rcap_b_o,
    input  wire [4:0]             waddr_a_i,
    input  wire [DataWidth-1:0]   wdata_a_i,
    input  wire [CapWidth-1:0]    wcap_a_i,
    input  wire                   we_a_i
);

  ibex_register_file_ff #(
      .BaseIsa           (BaseIsa),
      .RV32E             (RV32E),
      .DataWidth         (DataWidth),
      .DummyInstructions (DummyInstructions),
      .CapWidth          (CapWidth)
  ) u_rf (
      .clk_i             (clk_i),
      .rst_ni            (rst_ni),
      .test_en_i         (test_en_i),
      .dummy_instr_id_i  (dummy_instr_id_i),
      .dummy_instr_wb_i  (dummy_instr_wb_i),
      .cheriot_enable_i  (cheriot_enable_i),
      .raddr_a_i         (raddr_a_i),
      .rdata_a_o         (rdata_a_o),
      .rcap_a_o          (rcap_a_o),
      .raddr_b_i         (raddr_b_i),
      .rdata_b_o         (rdata_b_o),
      .rcap_b_o          (rcap_b_o),
      .waddr_a_i         (waddr_a_i),
      .wdata_a_i         (wdata_a_i),
      .wcap_a_i          (wcap_a_i),
      .we_a_i            (we_a_i)
  );

endmodule

`default_nettype wire
