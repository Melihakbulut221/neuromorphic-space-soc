// Blackbox declaration for RM_IHPSG13_1P_512x32_c2_bm_bist.
//
// Port list transcribed verbatim from the PDK's own behavioural model,
//   $PDK_ROOT/ihp-sg13g2/libs.ref/sg13g2_sram/verilog/
//       RM_IHPSG13_1P_512x32_c2_bm_bist.v   (lines 21-56)
// with the body removed. Nothing is added and no port is renamed.
//
// Why a stub rather than the PDK file: the PDK model is a wrapper that
// instantiates RM_IHPSG13_1P_core_behavioral_bm_bist, which lives in a
// different file, so handing the PDK model to the linter or to Yosys as
// a blackbox source drags in a submodule that is not wanted at synthesis
// time. LibreLane consumes this file through MACROS.<macro>.vh, which is
// the highest-priority blackbox view; the real physical and timing data
// come from the LEF, GDS and the three Liberty corners.
//
// Deliberately carries no power ports: the PDK's behavioural model has
// none either. The macro's supplies (VDD!, VSS!, VDDARRAY!) are LEF pins
// and reach the netlist through the ODB-generated powered netlist, not
// through this declaration.

`default_nettype none

(* blackbox *)
module RM_IHPSG13_1P_512x32_c2_bm_bist (
    A_CLK,
    A_MEN,
    A_WEN,
    A_REN,
    A_ADDR,
    A_DIN,
    A_DLY,
    A_DOUT,
    A_BM,
    A_BIST_CLK,
    A_BIST_EN,
    A_BIST_MEN,
    A_BIST_WEN,
    A_BIST_REN,
    A_BIST_ADDR,
    A_BIST_DIN,
    A_BIST_BM
);

    input        A_CLK;
    input        A_MEN;
    input        A_WEN;
    input        A_REN;
    input  [8:0] A_ADDR;
    input [31:0] A_DIN;
    input        A_DLY;
    output[31:0] A_DOUT;
    input [31:0] A_BM;
    input        A_BIST_CLK;
    input        A_BIST_EN;
    input        A_BIST_MEN;
    input        A_BIST_WEN;
    input        A_BIST_REN;
    input  [8:0] A_BIST_ADDR;
    input [31:0] A_BIST_DIN;
    input [31:0] A_BIST_BM;

endmodule

`default_nettype wire
