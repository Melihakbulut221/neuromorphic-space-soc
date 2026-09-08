// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// =====================================================================
// COST PROBE -- NOT VERIFIED, NOT PART OF THE SOC
//
// This file exists for one purpose only: to be synthesised so that the
// silicon area of a real AHB-lite fabric can be measured and compared
// against keeping Ibex's native req/gnt/rvalid memory protocol.
//
//   * It is synthesised and area-measured only.
//   * It has NO testbench, NO simulation, NO formal proof. Nothing in
//     this file has been shown to be functionally correct.
//   * It is not instantiated anywhere in the SoC and must not be.
//   * It must not be used as if it were verified RTL. If any of it is
//     ever wanted for real it has to be re-reviewed and verified from
//     scratch first.
// =====================================================================
//
// ahbl_interconnect -- AHB-lite address decoder and slave read
// multiplexer for four mapped slaves plus a built-in default slave.
//
// Structure, which is the standard AHB-lite one:
//   * the address phase decodes haddr_i against four base/mask pairs and
//     raises exactly one HSEL. Overlapping maps are resolved by index
//     order, low index wins, so a bad parameter set degrades to a
//     shadowed slave rather than to two slaves driving at once.
//   * everything except HSEL is broadcast to all four slaves; a slave
//     acts only when its own HSEL was high in the address phase.
//   * the selection is registered on the global HREADY and that
//     registered copy steers the HRDATA / HREADYOUT / HRESP multiplexer
//     during the data phase. This one-cycle skew is what makes the
//     decoder cost more than a plain mux: the response must be routed by
//     who was addressed last cycle, not by who is addressed now.
//   * an address that hits nothing selects the default slave, which
//     returns the AMBA-mandated two-cycle ERROR response. Without it an
//     unmapped access would hang the bus instead of trapping the core.
//
// HREADY when no data phase is in flight is driven high so an idle bus
// does not stall the master.
//
module ahbl_interconnect #(
  parameter [31:0] S0_BASE = 32'h0000_0000,
  parameter [31:0] S0_MASK = 32'hFFF0_0000,
  parameter [31:0] S1_BASE = 32'h0010_0000,
  parameter [31:0] S1_MASK = 32'hFFF0_0000,
  parameter [31:0] S2_BASE = 32'h0020_0000,
  parameter [31:0] S2_MASK = 32'hFFF0_0000,
  parameter [31:0] S3_BASE = 32'h0030_0000,
  parameter [31:0] S3_MASK = 32'hFFF0_0000
) (
  input  wire        clk_i,
  input  wire        rst_ni,

  // Upstream AHB-lite master port (from the arbiter)
  input  wire [31:0] haddr_i,
  input  wire [1:0]  htrans_i,
  input  wire        hwrite_i,
  input  wire [2:0]  hsize_i,
  input  wire [2:0]  hburst_i,
  input  wire [3:0]  hprot_i,
  input  wire [31:0] hwdata_i,
  output wire [31:0] hrdata_o,
  output wire        hready_o,
  output wire        hresp_o,

  // Broadcast address/control/write-data to all four slaves
  output wire [31:0] s_haddr_o,
  output wire [1:0]  s_htrans_o,
  output wire        s_hwrite_o,
  output wire [2:0]  s_hsize_o,
  output wire [2:0]  s_hburst_o,
  output wire [3:0]  s_hprot_o,
  output wire [31:0] s_hwdata_o,
  output wire        s_hready_o,

  // Per-slave select and response
  output wire        s0_hsel_o,
  input  wire [31:0] s0_hrdata_i,
  input  wire        s0_hreadyout_i,
  input  wire        s0_hresp_i,

  output wire        s1_hsel_o,
  input  wire [31:0] s1_hrdata_i,
  input  wire        s1_hreadyout_i,
  input  wire        s1_hresp_i,

  output wire        s2_hsel_o,
  input  wire [31:0] s2_hrdata_i,
  input  wire        s2_hreadyout_i,
  input  wire        s2_hresp_i,

  output wire        s3_hsel_o,
  input  wire [31:0] s3_hrdata_i,
  input  wire        s3_hreadyout_i,
  input  wire        s3_hresp_i
);

  localparam [1:0] DEF_IDLE = 2'd0;
  localparam [1:0] DEF_ERR1 = 2'd1;
  localparam [1:0] DEF_ERR2 = 2'd2;

  // ---- address phase decode ------------------------------------------
  wire ap = htrans_i[1];   // NONSEQ or SEQ; IDLE and BUSY select nothing

  wire hit0 = ((haddr_i & S0_MASK) == (S0_BASE & S0_MASK));
  wire hit1 = ((haddr_i & S1_MASK) == (S1_BASE & S1_MASK));
  wire hit2 = ((haddr_i & S2_MASK) == (S2_BASE & S2_MASK));
  wire hit3 = ((haddr_i & S3_MASK) == (S3_BASE & S3_MASK));

  wire sel0 =  hit0;
  wire sel1 =  hit1 & ~hit0;
  wire sel2 =  hit2 & ~hit1 & ~hit0;
  wire sel3 =  hit3 & ~hit2 & ~hit1 & ~hit0;
  wire seld = ~(hit0 | hit1 | hit2 | hit3);

  assign s0_hsel_o = ap & sel0;
  assign s1_hsel_o = ap & sel1;
  assign s2_hsel_o = ap & sel2;
  assign s3_hsel_o = ap & sel3;
  wire   sd_hsel   = ap & seld;

  assign s_haddr_o  = haddr_i;
  assign s_htrans_o = htrans_i;
  assign s_hwrite_o = hwrite_i;
  assign s_hsize_o  = hsize_i;
  assign s_hburst_o = hburst_i;
  assign s_hprot_o  = hprot_i;
  assign s_hwdata_o = hwdata_i;
  assign s_hready_o = hready_o;

  // ---- data phase selection ------------------------------------------
  // One-hot, bit 4 is the default slave. Zero means no data phase.
  reg [4:0] dsel_q;

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      dsel_q <= 5'b0;
    end else if (hready_o) begin
      dsel_q <= ap ? {seld, sel3, sel2, sel1, sel0} : 5'b0;
    end
  end

  // ---- default slave --------------------------------------------------
  // Mandatory AHB two-cycle ERROR for unmapped addresses: first cycle
  // HRESP high with HREADYOUT low, second cycle HRESP high with
  // HREADYOUT high. An IDLE transfer to it completes with OKAY.
  reg [1:0] def_q;

  wire def_hreadyout = (def_q != DEF_ERR1);
  wire def_hresp     = (def_q == DEF_ERR1) | (def_q == DEF_ERR2);

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      def_q <= DEF_IDLE;
    end else begin
      case (def_q)
        DEF_IDLE: if (sd_hsel & hready_o) def_q <= DEF_ERR1;
        DEF_ERR1: def_q <= DEF_ERR2;
        DEF_ERR2: def_q <= (sd_hsel & hready_o) ? DEF_ERR1 : DEF_IDLE;
        default:  def_q <= DEF_IDLE;
      endcase
    end
  end

  // ---- response multiplexer -------------------------------------------
  reg [31:0] rdata_mux;
  reg        ready_mux;
  reg        resp_mux;

  always @(*) begin
    case (dsel_q)
      5'b00001: begin rdata_mux = s0_hrdata_i; ready_mux = s0_hreadyout_i; resp_mux = s0_hresp_i; end
      5'b00010: begin rdata_mux = s1_hrdata_i; ready_mux = s1_hreadyout_i; resp_mux = s1_hresp_i; end
      5'b00100: begin rdata_mux = s2_hrdata_i; ready_mux = s2_hreadyout_i; resp_mux = s2_hresp_i; end
      5'b01000: begin rdata_mux = s3_hrdata_i; ready_mux = s3_hreadyout_i; resp_mux = s3_hresp_i; end
      5'b10000: begin rdata_mux = 32'b0;       ready_mux = def_hreadyout;  resp_mux = def_hresp;  end
      // no data phase in flight: idle bus must not stall the master
      default:  begin rdata_mux = 32'b0;       ready_mux = 1'b1;           resp_mux = 1'b0;       end
    endcase
  end

  assign hrdata_o = rdata_mux;
  assign hready_o = ready_mux;
  assign hresp_o  = resp_mux;

endmodule
