// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// The QSPI controller on a board with two flash devices, for cocotb.
//
// hw/soc/tb/cocotb/test_soc_qspi.py drives the APB side of this module
// and reads what the two W25Q128JV models saw. It exists because the
// block's contract has two sides -- the register interface and the
// pins -- and the pin side is a specification (the part's datasheet,
// hw/soc/tb/flash_w25q128jv.v) that only a device on the wire can hold
// the controller to. Driving the four IO lanes by hand from Python
// would test the controller against whatever the test author believed
// a flash does.
//
// The board: SCK and the four IO lanes are shared; each chip select
// goes to its own device. The IO lanes are `tri1` -- a pull-up on every
// lane, which is what a board carries on /WP and /HOLD so that a
// released pin is not a floating one. The controller drives a lane
// only while io_oe_o says so, and a device drives only while selected
// and in an output phase, so contention shows up as X on the wire and
// in RX, and not as a value.
//
// Each device is loaded from a plusarg -- +flash0=<hex>, +flash1=<hex>
// -- one byte per line, written by hw/soc/flow/gen_flash_image.py. The
// load is delayed one time unit so that it lands after the model's own
// initial fill with FFh; a $readmemh in a second initial block at time
// zero has no defined order against the first.
//
// The busy times are SCALED: tW, tPP, tSE and tRST are 2 us here where
// the table says 15 ms, 3 ms, 400 ms and 30 us. A test that waits on
// BUSY waits the scaled time and proves the polling, not the part.

`timescale 1ns / 1ps

module tb_soc_qspi #(
    parameter integer NCS   = 2,
    parameter integer DIV_W = 4,
    parameter integer LEN_W = 16
) (
    input  wire        clk_i,
    input  wire        rst_ni,
    input  wire        psel_i,
    input  wire        penable_i,
    input  wire [11:0] paddr_i,
    input  wire        pwrite_i,
    input  wire [31:0] pwdata_i,
    output wire [31:0] prdata_o,
    output wire        pready_o,
    output wire        pslverr_o,
    output wire        irq_o,
    // the wire, observed
    output wire        sck,
    output wire [NCS-1:0] cs_n,
    output wire [3:0]  io_bus
);

  wire [3:0] io_o, io_oe;
  tri1 [3:0] io;

  genvar g;
  generate
    for (g = 0; g < 4; g = g + 1) begin : g_lane
      assign io[g] = io_oe[g] ? io_o[g] : 1'bz;
    end
  endgenerate
  assign io_bus = io;

  soc_qspi #(.NCS(NCS), .DIV_W(DIV_W), .LEN_W(LEN_W)) dut (
      .clk_i (clk_i), .rst_ni (rst_ni),
      .psel_i (psel_i), .penable_i (penable_i), .paddr_i (paddr_i),
      .pwrite_i (pwrite_i), .pwdata_i (pwdata_i),
      .prdata_o (prdata_o), .pready_o (pready_o), .pslverr_o (pslverr_o),
      .sck_o (sck), .cs_no (cs_n),
      .io_o (io_o), .io_oe_o (io_oe), .io_i (io),
      .irq_o (irq_o)
  );

  localparam real SCALED = 2000.0;

  flash_w25q128jv #(.T_W_NS(SCALED), .T_PP_NS(SCALED), .T_SE_NS(SCALED),
                    .T_RST_NS(SCALED)) u_flash0 (
      .cs_n (cs_n[0]), .sck (sck), .io (io)
  );

  generate
    if (NCS > 1) begin : g_flash1
      flash_w25q128jv #(.T_W_NS(SCALED), .T_PP_NS(SCALED), .T_SE_NS(SCALED),
                        .T_RST_NS(SCALED)) u_flash1 (
          .cs_n (cs_n[1]), .sck (sck), .io (io)
      );
    end
  endgenerate

  reg [8*256-1:0] fname;
  initial begin
    #1;
    if ($value$plusargs("flash0=%s", fname)) $readmemh(fname, u_flash0.mem);
    if (NCS > 1) begin
      if ($value$plusargs("flash1=%s", fname))
        $readmemh(fname, g_flash1.u_flash1.mem);
    end
  end

endmodule
