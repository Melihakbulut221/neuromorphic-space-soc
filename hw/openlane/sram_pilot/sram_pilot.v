// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Decision vehicle for the 2026-09-07 RM_IHPSG13 go/no-go (docs/06 B.6.1).
//
// One RM_IHPSG13_1P_512x32_c2_bm_bist macro in a registered wrapper and
// nothing else. The point is NOT the function -- it is to answer the two
// questions that only a routed run can answer:
//
//   1. does detailed routing reach the macro's 188 bottom-edge Metal2
//      pins, each a single 0.26 x 0.26 um access point (docs/12 6.4c);
//   2. does Netgen LVS close over the macro's CDL (docs/12 6.4f).
//
// Measured answers, run macro-03: (1) yes, 0 routing DRC errors and 0
// antenna violations; (2) no, 359 LVS errors. docs/12 sections 7 and 8.
//
// Deliberately minimal so that any failure is attributable to the macro
// integration and not to surrounding logic. Every macro port is driven
// from a flop or a constant, so the router has a real (not trivial)
// pin-access problem while synthesis has almost nothing to optimise.
//
// A_DLY is tied high. The datasheet for THIS macro words it as
// "recommended setting: Tie to 1" rather than the "MANDATORY" wording
// used by 16 of the 27 parts (docs/12 6.4e); tie it high regardless.
// The BIST port set is parked inactive: A_BIST_EN low selects the
// functional port, and the remaining A_BIST_* inputs are held at 0 so
// they do not float in the extracted netlist.
//
// This file lives under hw/openlane/ and not hw/rtl/ on purpose: it is
// flow-experiment scaffolding for a go/no-go, not project RTL, and it is
// not part of any pilot submission.

`default_nettype none

module sram_pilot (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        en,
    input  wire        we,
    input  wire [8:0]  addr,
    input  wire [31:0] din,
    output wire [31:0] dout
);

    // Input registers: the macro sees only flop outputs.
    reg        en_q;
    reg        we_q;
    reg [8:0]  addr_q;
    reg [31:0] din_q;

    // Output register: the macro's A_DOUT is captured, never combinational
    // to a port. Keeps the read arc (docs/12 6.4g) inside the block.
    reg [31:0] dout_q;

    wire [31:0] mem_dout;

    always @(posedge clk) begin
        if (!rst_n) begin
            en_q   <= 1'b0;
            we_q   <= 1'b0;
            addr_q <= 9'b0;
            din_q  <= 32'b0;
        end else begin
            en_q   <= en;
            we_q   <= we;
            addr_q <= addr;
            din_q  <= din;
        end
    end

    always @(posedge clk) begin
        if (!rst_n)
            dout_q <= 32'b0;
        else
            dout_q <= mem_dout;
    end

    assign dout = dout_q;

    RM_IHPSG13_1P_512x32_c2_bm_bist u_sram (
        .A_CLK       (clk),
        .A_MEN       (en_q),
        .A_WEN       (we_q),
        .A_REN       (~we_q),
        .A_ADDR      (addr_q),
        .A_DIN       (din_q),
        .A_DLY       (1'b1),
        .A_DOUT      (mem_dout),
        .A_BM        ({32{1'b1}}),
        .A_BIST_CLK  (1'b0),
        .A_BIST_EN   (1'b0),
        .A_BIST_MEN  (1'b0),
        .A_BIST_WEN  (1'b0),
        .A_BIST_REN  (1'b0),
        .A_BIST_ADDR (9'b0),
        .A_BIST_DIN  (32'b0),
        .A_BIST_BM   (32'b0)
    );

endmodule

`default_nettype wire
