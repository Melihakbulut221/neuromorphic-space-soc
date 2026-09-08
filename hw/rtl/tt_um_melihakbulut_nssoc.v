// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Tiny Tapeout wrapper for the TTIHP26b pilot (hw/rtl/pilot_top.v).
//
// The wrapper does three things and nothing else: it maps the pilot's
// named ports onto the TT port list, it fixes the uio directions, and it
// synchronizes the reset deassertion. All design intent lives in
// pilot_top.v; the pin contract is documented in that file's header
// section 1 and reproduced here so the two cannot drift silently.
//
// The module name is the submission's name, not a description of it.
// Tiny Tapeout assembles every project on a shuttle into one die, and
// tt-support-tools configure.py asserts that macro instance names are
// unique across all of them, so a top level has to be namespaced
// tt_um_<user>_<project> -- the convention the sibling project shipped
// under (tt_um_melihakbulut_goldfinch). This file was called
// tt_um_pilot.v until the submission generator stopped wrapping it in a
// generated name adapter; the name here is now the name that is
// hardened, and there is one hierarchy level less between the pin list
// and the design.
//
// Pin map (identical to pilot_top.v section 1):
//
//   ui_in[0] SER_SCK        uo_out[0] SER_MISO
//   ui_in[1] SER_CS_N       uo_out[1] BUSY
//   ui_in[2] SER_MOSI       uo_out[2] AER_IN_RDY
//   ui_in[3] AER_IN_STB     uo_out[3] AER_OUT_VLD
//   ui_in[4] AER_IN_TICK    uo_out[4] ERR
//   ui_in[5] AER_OUT_ACK    uo_out[5] SEC
//   ui_in[6] SCRUB_STB      uo_out[6] DED
//   ui_in[7] reserved       uo_out[7] TMR
//
//   uio[3:0] AER_IN_ADDR    inputs,  uio_oe[3:0] = 0
//   uio[7:4] AER_OUT_ID     outputs, uio_oe[7:4] = 1
//
// Reset: Tiny Tapeout drives rst_n from the chip infrastructure and its
// deassertion is not guaranteed to be synchronous to clk. A two-flop
// synchronizer gives the design a synchronous deassert while keeping the
// assertion asynchronous, so a reset release that lands inside a setup
// window cannot put different flops into different reset states. This is
// the same construct, and for the same recorded reason, as the sibling
// project's shipped TT wrapper.
//
// ena is driven by the TT mux and is high whenever this design is
// selected; the pilot has no use for it and it is sunk explicitly rather
// than left dangling.
//
// Plain Verilog-2005, Icarus-clean.
`default_nettype none

module tt_um_melihakbulut_nssoc (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

    // Synchronized reset deassert; the assert path stays asynchronous.
    reg [1:0] rst_sync;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) rst_sync <= 2'b00;
        else        rst_sync <= {rst_sync[0], 1'b1};
    end
    wire rst_n_sync = rst_sync[1];

    wire       ser_miso;
    wire       busy, err, sec_seen, ded_seen, tmr_seen;
    wire       aer_in_rdy, aer_out_vld;
    wire [3:0] aer_out_id;

    pilot_top u_pilot (
        .clk         (clk),
        .rst_n       (rst_n_sync),
        .ser_sck     (ui_in[0]),
        .ser_cs_n    (ui_in[1]),
        .ser_mosi    (ui_in[2]),
        .ser_miso    (ser_miso),
        .aer_in_stb  (ui_in[3]),
        .aer_in_tick (ui_in[4]),
        .aer_in_addr (uio_in[3:0]),
        .aer_in_rdy  (aer_in_rdy),
        .aer_out_vld (aer_out_vld),
        .aer_out_id  (aer_out_id),
        .aer_out_ack (ui_in[5]),
        .scrub_stb   (ui_in[6]),
        .busy        (busy),
        .err         (err),
        .sec_seen    (sec_seen),
        .ded_seen    (ded_seen),
        .tmr_seen    (tmr_seen)
    );

    assign uo_out  = {tmr_seen, ded_seen, sec_seen, err,
                      aer_out_vld, aer_in_rdy, busy, ser_miso};
    assign uio_out = {aer_out_id, 4'b0000};
    assign uio_oe  = 8'b1111_0000;

    wire _unused = &{1'b0, ena, ui_in[7], uio_in[7:4], 1'b0};

endmodule

`default_nettype wire
