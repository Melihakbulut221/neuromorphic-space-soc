// Blackbox declaration for RM_IHPSG13_1P_512x16_c2_bm_bist.
//
// Port list transcribed verbatim from the PDK's own behavioural model,
//   $PDK_ROOT/ihp-sg13g2/libs.ref/sg13g2_sram/verilog/RM_IHPSG13_1P_512x16_c2_bm_bist.v
// with the body removed. Nothing is added and no port is renamed.
// hw/soc/pnr/RM_IHPSG13_1P_1024x32_c2_bm_bist_bb.v says why a stub and
// not the PDK file; sw/tests/test_soc_synthesis_guards.py compares this
// file's declarations against the PDK model's.
//
// The check-bit macro of the protected boot ROM, docs/67: one per ROM
// bank, holding the seven (39,32) check bits of 1024 words as two
// 7-bit fields of a 16-bit row.
//
// Deliberately carries no power ports: the PDK's behavioural model has
// none either.

`default_nettype none

(* blackbox *)
module RM_IHPSG13_1P_512x16_c2_bm_bist (
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

    input A_CLK;
    input A_MEN;
    input A_WEN;
    input A_REN;
    input [8:0] A_ADDR;
    input [15:0] A_DIN;
    input A_DLY;
    output [15:0] A_DOUT;
    input [15:0] A_BM;
    input A_BIST_CLK;
    input A_BIST_EN;
    input A_BIST_MEN;
    input A_BIST_WEN;
    input A_BIST_REN;
    input [8:0] A_BIST_ADDR;
    input [15:0] A_BIST_DIN;
    input [15:0] A_BIST_BM;

endmodule

`default_nettype wire
