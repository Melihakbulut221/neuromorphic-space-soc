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
// probe_ahbl_top -- the whole candidate fabric in one module, so that the
// synthesiser sees the complete path and cannot delete a block because
// its outputs go nowhere.
//
//   instruction port --> ibex2ahbl --\
//                                     +-> ahbl_arbiter -> ahbl_interconnect
//   data port -------> ibex2ahbl --/                        |
//                                                           +-> s0, s1, s2
//                                                           |   (top ports,
//                                                           |    memory-ish
//                                                           |    slaves)
//                                                           +-> ahbl2apb -> APB
//
// Every output of every instance reaches a top-level port, either
// directly or through the block downstream of it, so nothing in the
// measured area is an artefact of a dangling net.
//
// Deliberate measurement choice: both Ibex-side ports are given a full
// write path here (we/be/wdata as top-level inputs), including the
// instruction port. The real Ibex instruction port is read-only, so in a
// real integration the instruction-side bridge and part of the arbiter's
// write-data multiplexer would shrink. This top therefore measures the
// conservative case, and the numbers for the five modules stay additive
// instead of being distorted by tie-off propagation.
//
// Memory map used for the measurement (only the decode logic costs area,
// the addresses themselves are arbitrary):
//   0x0000_0000 .. 0x000F_FFFF   s0
//   0x0010_0000 .. 0x001F_FFFF   s1
//   0x0020_0000 .. 0x002F_FFFF   s2
//   0x0030_0000 .. 0x003F_FFFF   APB window, 8 x 4 KiB slots at the base
//   everything else              default slave, two-cycle ERROR
//
module probe_ahbl_top (
  input  wire        clk_i,
  input  wire        rst_ni,

  // Ibex-native instruction-side port
  input  wire        instr_req_i,
  output wire        instr_gnt_o,
  output wire        instr_rvalid_o,
  input  wire [31:0] instr_addr_i,
  input  wire        instr_we_i,
  input  wire [3:0]  instr_be_i,
  input  wire [31:0] instr_wdata_i,
  output wire [31:0] instr_rdata_o,
  output wire        instr_err_o,

  // Ibex-native data-side port
  input  wire        data_req_i,
  output wire        data_gnt_o,
  output wire        data_rvalid_o,
  input  wire [31:0] data_addr_i,
  input  wire        data_we_i,
  input  wire [3:0]  data_be_i,
  input  wire [31:0] data_wdata_i,
  output wire [31:0] data_rdata_o,
  output wire        data_err_o,

  // Broadcast AHB-lite address/control/write data to the three external
  // memory-ish slaves
  output wire [31:0] s_haddr_o,
  output wire [1:0]  s_htrans_o,
  output wire        s_hwrite_o,
  output wire [2:0]  s_hsize_o,
  output wire [2:0]  s_hburst_o,
  output wire [3:0]  s_hprot_o,
  output wire [31:0] s_hwdata_o,
  output wire        s_hready_o,

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

  // APB3 port out of the AHB-to-APB bridge
  output wire [7:0]  psel_o,
  output wire        penable_o,
  output wire [31:0] paddr_o,
  output wire        pwrite_o,
  output wire [31:0] pwdata_o,
  output wire [3:0]  pstrb_o,
  input  wire [31:0] prdata_i,
  input  wire        pready_i,
  input  wire        pslverr_i
);

  // ---- instruction-side bridge ----------------------------------------
  wire [31:0] i_haddr;
  wire [1:0]  i_htrans;
  wire        i_hwrite;
  wire [2:0]  i_hsize;
  wire [2:0]  i_hburst;
  wire [3:0]  i_hprot;
  wire [31:0] i_hwdata;
  wire [31:0] i_hrdata;
  wire        i_hready;
  wire        i_hresp;

  ibex2ahbl #(.HPROT_VAL(4'b0010)) u_ibridge (
    .clk_i    (clk_i),
    .rst_ni   (rst_ni),
    .req_i    (instr_req_i),
    .gnt_o    (instr_gnt_o),
    .rvalid_o (instr_rvalid_o),
    .addr_i   (instr_addr_i),
    .we_i     (instr_we_i),
    .be_i     (instr_be_i),
    .wdata_i  (instr_wdata_i),
    .rdata_o  (instr_rdata_o),
    .err_o    (instr_err_o),
    .haddr_o  (i_haddr),
    .htrans_o (i_htrans),
    .hwrite_o (i_hwrite),
    .hsize_o  (i_hsize),
    .hburst_o (i_hburst),
    .hprot_o  (i_hprot),
    .hwdata_o (i_hwdata),
    .hrdata_i (i_hrdata),
    .hready_i (i_hready),
    .hresp_i  (i_hresp)
  );

  // ---- data-side bridge ------------------------------------------------
  wire [31:0] d_haddr;
  wire [1:0]  d_htrans;
  wire        d_hwrite;
  wire [2:0]  d_hsize;
  wire [2:0]  d_hburst;
  wire [3:0]  d_hprot;
  wire [31:0] d_hwdata;
  wire [31:0] d_hrdata;
  wire        d_hready;
  wire        d_hresp;

  ibex2ahbl #(.HPROT_VAL(4'b0011)) u_dbridge (
    .clk_i    (clk_i),
    .rst_ni   (rst_ni),
    .req_i    (data_req_i),
    .gnt_o    (data_gnt_o),
    .rvalid_o (data_rvalid_o),
    .addr_i   (data_addr_i),
    .we_i     (data_we_i),
    .be_i     (data_be_i),
    .wdata_i  (data_wdata_i),
    .rdata_o  (data_rdata_o),
    .err_o    (data_err_o),
    .haddr_o  (d_haddr),
    .htrans_o (d_htrans),
    .hwrite_o (d_hwrite),
    .hsize_o  (d_hsize),
    .hburst_o (d_hburst),
    .hprot_o  (d_hprot),
    .hwdata_o (d_hwdata),
    .hrdata_i (d_hrdata),
    .hready_i (d_hready),
    .hresp_i  (d_hresp)
  );

  // ---- arbiter ---------------------------------------------------------
  wire [31:0] a_haddr;
  wire [1:0]  a_htrans;
  wire        a_hwrite;
  wire [2:0]  a_hsize;
  wire [2:0]  a_hburst;
  wire [3:0]  a_hprot;
  wire [31:0] a_hwdata;
  wire [31:0] a_hrdata;
  wire        a_hready;
  wire        a_hresp;

  ahbl_arbiter u_arb (
    .clk_i       (clk_i),
    .rst_ni      (rst_ni),
    .m0_haddr_i  (i_haddr),
    .m0_htrans_i (i_htrans),
    .m0_hwrite_i (i_hwrite),
    .m0_hsize_i  (i_hsize),
    .m0_hburst_i (i_hburst),
    .m0_hprot_i  (i_hprot),
    .m0_hwdata_i (i_hwdata),
    .m0_hrdata_o (i_hrdata),
    .m0_hready_o (i_hready),
    .m0_hresp_o  (i_hresp),
    .m1_haddr_i  (d_haddr),
    .m1_htrans_i (d_htrans),
    .m1_hwrite_i (d_hwrite),
    .m1_hsize_i  (d_hsize),
    .m1_hburst_i (d_hburst),
    .m1_hprot_i  (d_hprot),
    .m1_hwdata_i (d_hwdata),
    .m1_hrdata_o (d_hrdata),
    .m1_hready_o (d_hready),
    .m1_hresp_o  (d_hresp),
    .haddr_o     (a_haddr),
    .htrans_o    (a_htrans),
    .hwrite_o    (a_hwrite),
    .hsize_o     (a_hsize),
    .hburst_o    (a_hburst),
    .hprot_o     (a_hprot),
    .hwdata_o    (a_hwdata),
    .hrdata_i    (a_hrdata),
    .hready_i    (a_hready),
    .hresp_i     (a_hresp)
  );

  // ---- interconnect ----------------------------------------------------
  wire        s3_hsel;
  wire [31:0] s3_hrdata;
  wire        s3_hreadyout;
  wire        s3_hresp;

  ahbl_interconnect #(
    .S0_BASE (32'h0000_0000), .S0_MASK (32'hFFF0_0000),
    .S1_BASE (32'h0010_0000), .S1_MASK (32'hFFF0_0000),
    .S2_BASE (32'h0020_0000), .S2_MASK (32'hFFF0_0000),
    .S3_BASE (32'h0030_0000), .S3_MASK (32'hFFF0_0000)
  ) u_icn (
    .clk_i          (clk_i),
    .rst_ni         (rst_ni),
    .haddr_i        (a_haddr),
    .htrans_i       (a_htrans),
    .hwrite_i       (a_hwrite),
    .hsize_i        (a_hsize),
    .hburst_i       (a_hburst),
    .hprot_i        (a_hprot),
    .hwdata_i       (a_hwdata),
    .hrdata_o       (a_hrdata),
    .hready_o       (a_hready),
    .hresp_o        (a_hresp),
    .s_haddr_o      (s_haddr_o),
    .s_htrans_o     (s_htrans_o),
    .s_hwrite_o     (s_hwrite_o),
    .s_hsize_o      (s_hsize_o),
    .s_hburst_o     (s_hburst_o),
    .s_hprot_o      (s_hprot_o),
    .s_hwdata_o     (s_hwdata_o),
    .s_hready_o     (s_hready_o),
    .s0_hsel_o      (s0_hsel_o),
    .s0_hrdata_i    (s0_hrdata_i),
    .s0_hreadyout_i (s0_hreadyout_i),
    .s0_hresp_i     (s0_hresp_i),
    .s1_hsel_o      (s1_hsel_o),
    .s1_hrdata_i    (s1_hrdata_i),
    .s1_hreadyout_i (s1_hreadyout_i),
    .s1_hresp_i     (s1_hresp_i),
    .s2_hsel_o      (s2_hsel_o),
    .s2_hrdata_i    (s2_hrdata_i),
    .s2_hreadyout_i (s2_hreadyout_i),
    .s2_hresp_i     (s2_hresp_i),
    .s3_hsel_o      (s3_hsel),
    .s3_hrdata_i    (s3_hrdata),
    .s3_hreadyout_i (s3_hreadyout),
    .s3_hresp_i     (s3_hresp)
  );

  // ---- AHB to APB bridge on slave 3 ------------------------------------
  ahbl2apb u_apb (
    .clk_i       (clk_i),
    .rst_ni      (rst_ni),
    .hsel_i      (s3_hsel),
    .haddr_i     (s_haddr_o),
    .htrans_i    (s_htrans_o),
    .hwrite_i    (s_hwrite_o),
    .hsize_i     (s_hsize_o),
    .hwdata_i    (s_hwdata_o),
    .hready_i    (s_hready_o),
    .hrdata_o    (s3_hrdata),
    .hreadyout_o (s3_hreadyout),
    .hresp_o     (s3_hresp),
    .psel_o      (psel_o),
    .penable_o   (penable_o),
    .paddr_o     (paddr_o),
    .pwrite_o    (pwrite_o),
    .pwdata_o    (pwdata_o),
    .pstrb_o     (pstrb_o),
    .prdata_i    (prdata_i),
    .pready_i    (pready_i),
    .pslverr_i   (pslverr_i)
  );

endmodule
