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
// ahbl_arbiter -- round-robin arbiter and multiplexer that lets two
// AHB-lite master ports share one AHB-lite bus.
//
// WHY THIS BLOCK EXISTS AT ALL
// ----------------------------
// AHB-Lite is defined as a single-master protocol. Ibex has two memory
// ports, instruction and data, so something has to merge them before the
// bus. Full AHB solves this with sideband HBUSREQ/HGRANT signals that
// AHB-Lite does not have, so the merge has to be done with the in-band
// signals only, and that is where the cost is.
//
// THE HARD PART
// -------------
// On an Ibex-native port, "your request was accepted" (gnt) and "your
// response is here" (rvalid) are two separate wires. AHB-Lite folds both
// onto one wire, HREADY. A master that is told HREADY=0 to stop it
// issuing a new address phase is simultaneously told its outstanding
// data phase has not finished. So an arbiter cannot back-pressure one
// half without stalling the other, and a master that keeps requesting
// can never be pushed off the bus.
//
// Two ways out, both real:
//   (a) only hand the bus over when the current owner has no data phase
//       in flight. Costs no storage, but forces a dead cycle on every
//       ownership change and starves one master while the other streams.
//   (b) let the data phase complete on the bus while the owner has
//       already changed, and park the response in a register until the
//       master it belongs to is the owner again, at which point it is
//       released together with that master's next address-phase accept
//       -- which is exactly what a normal pipelined AHB cycle looks like
//       from the master's side.
//
// This module implements (b), because it is the one that keeps both
// masters at full throughput: with both requesting, ownership alternates
// every cycle and one transfer per cycle still completes. The price is
// the parking registers: 32 bits of HRDATA plus HRESP plus a valid bit
// per master. That storage is the direct, measurable cost of AHB-Lite
// having exactly one master.
//
// KNOWN DEVIATION, and a reason this must not be treated as verified:
// a parked ERROR is released to the master as a single cycle of
// HRESP=1 with HREADY=1, not as the two-cycle sequence AMBA requires.
// The bridge in ibex2ahbl.v happens to accept that form, so the pair
// works together, but the master port of this arbiter is not a strictly
// compliant AHB-Lite slave port for an arbitrary third-party master.
//
// Round-robin policy: ownership passes to the other master whenever that
// master is presenting a transfer or still has a parked response to
// collect. With one master idle the active one keeps the bus.
//
module ahbl_arbiter (
  input  wire        clk_i,
  input  wire        rst_ni,

  // Master port 0 (this module is the slave side of it)
  input  wire [31:0] m0_haddr_i,
  input  wire [1:0]  m0_htrans_i,
  input  wire        m0_hwrite_i,
  input  wire [2:0]  m0_hsize_i,
  input  wire [2:0]  m0_hburst_i,
  input  wire [3:0]  m0_hprot_i,
  input  wire [31:0] m0_hwdata_i,
  output wire [31:0] m0_hrdata_o,
  output wire        m0_hready_o,
  output wire        m0_hresp_o,

  // Master port 1
  input  wire [31:0] m1_haddr_i,
  input  wire [1:0]  m1_htrans_i,
  input  wire        m1_hwrite_i,
  input  wire [2:0]  m1_hsize_i,
  input  wire [2:0]  m1_hburst_i,
  input  wire [3:0]  m1_hprot_i,
  input  wire [31:0] m1_hwdata_i,
  output wire [31:0] m1_hrdata_o,
  output wire        m1_hready_o,
  output wire        m1_hresp_o,

  // Downstream single AHB-lite master port
  output wire [31:0] haddr_o,
  output wire [1:0]  htrans_o,
  output wire        hwrite_o,
  output wire [2:0]  hsize_o,
  output wire [2:0]  hburst_o,
  output wire [3:0]  hprot_o,
  output wire [31:0] hwdata_o,
  input  wire [31:0] hrdata_i,
  input  wire        hready_i,
  input  wire        hresp_i
);

  localparam [1:0] TRANS_IDLE   = 2'b00;
  localparam [1:0] TRANS_NONSEQ = 2'b10;

  // own_q  : which master owns the address phase this cycle
  // dphv_q : a transfer is in its data phase on the downstream bus
  // dphm_q : which master that data phase belongs to
  reg own_q;
  reg dphv_q;
  reg dphm_q;

  // Parked responses, one per master.
  reg        hold0_v, hold1_v;
  reg [31:0] hold0_d, hold1_d;
  reg        hold0_e, hold1_e;

  wire req0 = m0_htrans_i[1];
  wire req1 = m1_htrans_i[1];

  wire req_own  = own_q ? req1 : req0;
  wire req_oth  = own_q ? req0 : req1;
  wire hold_oth = own_q ? hold0_v : hold1_v;

  // The other master needs the bus if it wants to issue, or if it still
  // has a parked response that can only be released while it is owner.
  wire need_oth = req_oth | hold_oth;

  // Address phase presented downstream this cycle.
  wire ap_go = req_own;

  assign htrans_o = ap_go ? TRANS_NONSEQ : TRANS_IDLE;
  assign haddr_o  = own_q ? m1_haddr_i  : m0_haddr_i;
  assign hwrite_o = own_q ? m1_hwrite_i : m0_hwrite_i;
  assign hsize_o  = own_q ? m1_hsize_i  : m0_hsize_i;
  assign hburst_o = own_q ? m1_hburst_i : m0_hburst_i;
  assign hprot_o  = own_q ? m1_hprot_i  : m0_hprot_i;

  // Write data belongs to the data-phase owner, which is one cycle
  // behind the address-phase owner. This is the second place where the
  // AHB phase split forces a separate select.
  assign hwdata_o = dphm_q ? m1_hwdata_i : m0_hwdata_i;

  // A master only sees HREADY high while it owns the address phase, so a
  // non-owner can neither have an address phase accepted nor a data
  // phase completed.
  assign m0_hready_o = (own_q == 1'b0) & hready_i;
  assign m1_hready_o = (own_q == 1'b1) & hready_i;

  assign m0_hrdata_o = hold0_v ? hold0_d : hrdata_i;
  assign m0_hresp_o  = hold0_v ? hold0_e : hresp_i;
  assign m1_hrdata_o = hold1_v ? hold1_d : hrdata_i;
  assign m1_hresp_o  = hold1_v ? hold1_e : hresp_i;

  // Downstream data phase finishing this cycle.
  wire dp_done = dphv_q & hready_i;

  // It finished while its owner is no longer the address-phase owner, so
  // the response cannot be handed over now and has to be parked.
  wire park = dp_done & (dphm_q != own_q);

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      own_q   <= 1'b0;
      dphv_q  <= 1'b0;
      dphm_q  <= 1'b0;
      hold0_v <= 1'b0;
      hold1_v <= 1'b0;
      hold0_d <= 32'b0;
      hold1_d <= 32'b0;
      hold0_e <= 1'b0;
      hold1_e <= 1'b0;
    end else begin
      // The AHB pipeline, and therefore ownership, only moves on hready.
      if (hready_i) begin
        dphv_q <= ap_go;
        dphm_q <= own_q;
        if (need_oth) begin
          own_q <= ~own_q;
        end

        // Release: the owner collects any response parked for it in the
        // same cycle its next address phase is accepted.
        if (own_q == 1'b0) hold0_v <= 1'b0;
        if (own_q == 1'b1) hold1_v <= 1'b0;
      end

      // Park. Disjoint from the release above: park always targets the
      // master that is not the current owner.
      if (park) begin
        if (dphm_q == 1'b1) begin
          hold1_v <= 1'b1;
          hold1_d <= hrdata_i;
          hold1_e <= hresp_i;
        end else begin
          hold0_v <= 1'b1;
          hold0_d <= hrdata_i;
          hold0_e <= hresp_i;
        end
      end
    end
  end

endmodule
