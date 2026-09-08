// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// sg13g2 binding for the clock gate Ibex leaves to the integrator.
//
// ibex_top.sv instantiates `prim_clock_gating` (one instance when the
// flip-flop register file is selected) and does NOT provide a synthesis
// implementation: the upstream open synthesis flow substitutes
// syn/rtl/prim_clock_gating.v, a behavioural `always @*` latch plus an
// AND. That is a modelling stand-in, not a cell, and it leaves a
// combinational loop-shaped latch in the netlist for the mapper to
// resolve however it likes.
//
// ihp-sg13g2 ships a real integrated clock gate, so this project binds
// the cell instead:
//
//   sg13g2_lgcp_1   clock_gating_integrated_cell : "latch_posedge"
//                   CLK, GATE -> GCLK  (GCLK = CLK * int_GATE)
//                   area 27.216 um2
//   (read out of sg13g2_stdcell_typ_1p20V_25C.lib)
//
// test_en_i forces the gate open for scan/DFT, matching the semantics
// of every other prim_clock_gating implementation upstream ships.
//
// Verilog-2005 on purpose: this file is read by Icarus, Yosys and
// OpenSTA alongside the sv2v output, and must not need SystemVerilog.

`ifdef SG13G2_ICG_BEHAVIOURAL
// Simulation model. Icarus has no sg13g2_lgcp_1 unless the PDK cell
// library is also read; this branch keeps the RTL testbench standalone.
module prim_clock_gating (
  input  clk_i,
  input  en_i,
  input  test_en_i,
  output clk_o
);
  reg en_latch;
  always @* begin
    if (!clk_i) en_latch = en_i | test_en_i;
  end
  assign clk_o = en_latch & clk_i;
endmodule
`else
module prim_clock_gating (
  input  clk_i,
  input  en_i,
  input  test_en_i,
  output clk_o
);
  sg13g2_lgcp_1 u_icg (
    .CLK  (clk_i),
    .GATE (en_i | test_en_i),
    .GCLK (clk_o)
  );
endmodule
`endif
