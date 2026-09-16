// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// HEAD-OF-LINE BLOCKING BENCH FOR soc_bus.v. NOT PART OF THE DESIGN.
//
// It exists because docs/84's first draft asserted a cost it had not
// measured: that the registered request phase blocks the other master
// while a slave refuses `gnt`, "where the combinational fabric would
// have let the other master go elsewhere". The combinational fabric
// does not. `target_ready` is computed from the arbitration WINNER's
// target, `i_wins` is `can_issue_i && !d_wins`, and `last_was_d`
// advances only on `accepted`, so when the winner's slave refuses, the
// loser is refused with it and the round-robin bit does not move. The
// blocking belongs to the arbiter and is there at both settings.
//
// This bench is the thing that says so rather than that paragraph. It
// puts the instruction port at the always-ready RAM and the data port
// at a slave that refuses, runs both masters continuously, and counts
// grants. docs/84 section 2.4a is the table it produced.
//
//   iverilog -g2012 -I hw/soc/rtl -P tb_soc_bus_hol.REQ_REG=0 \
//            -o hol0.vvp hw/soc/tb/tb_soc_bus_hol.v hw/soc/rtl/soc_bus.v
//   vvp hol0.vvp +NCYC=201 +MODE=0 +BUSY=10
//
// Icarus 12 (the pinned suite), and REQ_REG is a compile-time -P
// because it is a module parameter; everything else is a plusarg.
//
//   MODE   0 both masters request continuously
//          1 the data master asserts req for ONE cycle and goes idle,
//            which Ibex protocol rule 1 forbids and which is the only
//            asymmetry between the two settings this bench found
//   BUSY   cycles the data slave refuses after each accepted request
//   HOLD   cycles the data slave refuses from reset release
//   STUCK  1 = the data slave never grants at all
//   NCYC   cycles counted after reset release

`timescale 1ns / 1ps

module tb_soc_bus_hol;

  parameter integer REQ_REG = 0;

  reg clk = 1'b0;
  always #5 clk = ~clk;
  reg rst_n = 1'b0;

  integer BUSY  = 0;
  integer HOLD  = 0;
  integer STUCK = 0;
  integer NCYC  = 201;
  integer MODE  = 0;

  // ---- masters. Both hold req and payload, which is rule 1. ----
  reg         mi_req = 1'b0;
  wire [31:0] mi_addr = 32'h0000_0004;   // RAM, fabric port 0
  wire        mi_gnt, mi_rvalid, mi_err;
  wire [31:0] mi_rdata;

  reg         md_req = 1'b0;
  wire [31:0] md_addr = 32'hFF90_0000;   // APB, fabric port 2
  wire        md_gnt, md_rvalid, md_err;
  wire [31:0] md_rdata;

  wire [5:0]  s_req;
  wire [31:0] s_addr, s_wdata;
  wire        s_we;
  wire [3:0]  s_be;
  wire [5:0]  s_gnt;
  wire [5:0]  s_rvalid;
  wire [5:0]  s_err = 6'h0;

  // Port 0: always ready, one-cycle response.
  reg s0_rv = 1'b0;
  always @(posedge clk or negedge rst_n)
    if (!rst_n) s0_rv <= 1'b0;
    else        s0_rv <= s_req[0] & s_gnt[0];

  // Port 2: grants only when idle, refuses for BUSY cycles after each
  // accepted request and for HOLD cycles from reset release, and
  // answers when the refusal ends. This is soc_apb_bridge.v's shape --
  // `gnt_o = req_i && (state == ST_IDLE)` -- with the length as a knob.
  integer s2_busy = 0;
  integer s2_hold = 0;
  reg     s2_rv   = 1'b0;
  wire    s2_gnt  = (s2_busy == 0) && (s2_hold == 0) && (STUCK == 0);
  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      s2_busy <= 0;
      s2_hold <= HOLD;
      s2_rv   <= 1'b0;
    end else begin
      if (s2_hold != 0) s2_hold <= s2_hold - 1;
      s2_rv <= 1'b0;
      if (s2_busy != 0) begin
        s2_busy <= s2_busy - 1;
        if (s2_busy == 1) s2_rv <= 1'b1;
      end else if (s_req[2] && s2_gnt) begin
        if (BUSY == 0) s2_rv <= 1'b1;
        else           s2_busy <= BUSY;
      end
    end
  end

  assign s_gnt    = {3'b000, s2_gnt, 1'b0, 1'b1};
  assign s_rvalid = {3'b000, s2_rv,  1'b0, s0_rv};

  soc_bus #(.REQ_REG(REQ_REG)) dut (
      .clk_i(clk), .rst_ni(rst_n),
      .mi_req_i(mi_req), .mi_addr_i(mi_addr),
      .mi_gnt_o(mi_gnt), .mi_rvalid_o(mi_rvalid),
      .mi_rdata_o(mi_rdata), .mi_err_o(mi_err),
      .md_req_i(md_req), .md_addr_i(md_addr), .md_we_i(1'b0),
      .md_be_i(4'hF), .md_wdata_i(32'h0),
      .md_gnt_o(md_gnt), .md_rvalid_o(md_rvalid),
      .md_rdata_o(md_rdata), .md_err_o(md_err),
      .s_req_o(s_req), .s_addr_o(s_addr), .s_we_o(s_we),
      .s_be_o(s_be), .s_wdata_o(s_wdata),
      .s_gnt_i(s_gnt), .s_rvalid_i(s_rvalid),
      .s_rdata_0_i(32'hA0), .s_rdata_1_i(32'hA1), .s_rdata_2_i(32'hA2),
      .s_rdata_3_i(32'hA3), .s_rdata_4_i(32'hA4), .s_rdata_5_i(32'hA5),
      .s_err_i(s_err), .clk_en_o()
  );

  integer n_mi = 0, n_md = 0, cyc = 0, first_mi = -1;

  always @(posedge clk) if (rst_n) begin
    if (mi_gnt) begin
      n_mi = n_mi + 1;
      if (first_mi < 0) first_mi = cyc;
    end
    if (md_gnt) n_md = n_md + 1;
    cyc = cyc + 1;
  end

  initial begin
    if (!$value$plusargs("BUSY=%d",  BUSY))  BUSY  = 0;
    if (!$value$plusargs("HOLD=%d",  HOLD))  HOLD  = 0;
    if (!$value$plusargs("STUCK=%d", STUCK)) STUCK = 0;
    if (!$value$plusargs("NCYC=%d",  NCYC))  NCYC  = 201;
    if (!$value$plusargs("MODE=%d",  MODE))  MODE  = 0;

    repeat (4) @(posedge clk);
    rst_n = 1'b1;
    @(posedge clk);
    mi_req = 1'b1;
    md_req = 1'b1;
    if (MODE == 1) begin
      @(posedge clk);
      #1 md_req = 1'b0;
    end
    repeat (NCYC) @(posedge clk);
    #1;
    $display("REQ_REG=%0d MODE=%0d BUSY=%0d HOLD=%0d STUCK=%0d NCYC=%0d : mi_gnt=%0d md_gnt=%0d first_mi_gnt_at=%0d",
             REQ_REG, MODE, BUSY, HOLD, STUCK, NCYC, n_mi, n_md, first_mi);
    $finish;
  end

endmodule
