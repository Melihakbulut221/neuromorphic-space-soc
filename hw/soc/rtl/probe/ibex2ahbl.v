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
// ibex2ahbl -- one Ibex-native memory port to one AHB-lite master port.
//
// Ibex-native protocol being served (ext/ibex/doc/03_reference/
// load_store_unit.rst, section "Protocol"):
//   1. req_i is held high until gnt_o is high for one cycle; addr/we/be/
//      wdata are valid alongside req_i.
//   2. after gnt_o the core may change addr/we/be/wdata in the very next
//      cycle, so anything still needed after the grant must be captured.
//   3. exactly one rvalid_o pulse per granted request, carrying rdata_o
//      and err_o.
//   4. multiple granted requests may be outstanding; responses must come
//      back in issue order.
//
// AHB-lite side, honestly implemented:
//   * address phase: haddr_o/htrans_o/hwrite_o/hsize_o are driven and
//     the transfer is accepted at a rising edge with hready_i high.
//   * data phase: the cycle after acceptance. hwdata_o must be driven
//     there, which is one cycle after Ibex is allowed to drop wdata_i,
//     so write data is registered (32 flops -- this is a direct cost of
//     the phase split, the native protocol needs none of it).
//   * address phase of transfer N+1 overlaps the data phase of transfer
//     N, so back-to-back single transfers still run one per cycle.
//   * htrans_o is NONSEQ or IDLE only; no bursts, hburst_o is SINGLE.
//   * an AHB ERROR is two cycles (hresp_i high with hready_i low, then
//     hresp_i high with hready_i high). Only the second cycle produces
//     rvalid_o, so Ibex still sees exactly one response per request.
//     During the error the address phase is withdrawn to IDLE, as the
//     AMBA spec requires of the master.
//
// Outstanding-request depth: AHB-lite pipelines exactly one address
// phase against one data phase, so at most two transfers are in flight
// here. Ibex's instruction port issues up to two outstanding requests
// (NUM_REQS = 2 in ibex_prefetch_buffer.sv) and the data port issues two
// during a split misaligned access, so this depth happens to match. A
// deeper Ibex would be throttled by the bus, not by the bridge.
//
module ibex2ahbl #(
  // HPROT for every transfer this port issues. 4'b0011 = data, privileged,
  // non-bufferable, non-cacheable. Instruction ports pass 4'b0010.
  parameter [3:0] HPROT_VAL = 4'b0011
) (
  input  wire        clk_i,
  input  wire        rst_ni,

  // Ibex-native memory port (this module is the memory side of it)
  input  wire        req_i,
  output wire        gnt_o,
  output wire        rvalid_o,
  input  wire [31:0] addr_i,
  input  wire        we_i,
  input  wire [3:0]  be_i,
  input  wire [31:0] wdata_i,
  output wire [31:0] rdata_o,
  output wire        err_o,

  // AHB-lite master port
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
  localparam [2:0] BURST_SINGLE = 3'b000;

  // -------------------------------------------------------------------
  // Byte enables to HSIZE plus low address bits.
  //
  // Ibex describes a sub-word access as a word address plus a contiguous
  // byte-enable mask. AHB describes it as a byte address plus a size.
  // The two are not the same encoding, so the bridge has to translate,
  // and the low two address bits have to be reconstructed from be_i.
  // Non-contiguous masks cannot be expressed in AHB at all; Ibex never
  // emits one (its LSU splits a misaligned access into two aligned
  // word accesses), so they fall through to a word transfer.
  // -------------------------------------------------------------------
  reg [2:0] size_d;
  reg [1:0] boff_d;
  always @(*) begin
    case (be_i)
      4'b1111: begin size_d = 3'd2; boff_d = 2'd0; end  // word
      4'b0011: begin size_d = 3'd1; boff_d = 2'd0; end  // halfword lo
      4'b1100: begin size_d = 3'd1; boff_d = 2'd2; end  // halfword hi
      4'b0001: begin size_d = 3'd0; boff_d = 2'd0; end  // byte 0
      4'b0010: begin size_d = 3'd0; boff_d = 2'd1; end  // byte 1
      4'b0100: begin size_d = 3'd0; boff_d = 2'd2; end  // byte 2
      4'b1000: begin size_d = 3'd0; boff_d = 2'd3; end  // byte 3
      default: begin size_d = 3'd2; boff_d = 2'd0; end
    endcase
  end

  // -------------------------------------------------------------------
  // Pipeline state.
  //   dphase_q    a transfer accepted last cycle is in its data phase.
  //   errdly_q    second cycle of an AHB two-cycle ERROR response.
  //   wdata_q     write data captured at grant, replayed in the data
  //               phase (rule 2 of the Ibex protocol makes this
  //               mandatory).
  // -------------------------------------------------------------------
  reg        dphase_q;
  reg        errdly_q;
  reg [31:0] wdata_q;

  // First cycle of an ERROR response: hresp high while hready is low.
  wire err_first = dphase_q & hresp_i & ~hready_i;

  // The master must withdraw its address phase for both cycles of the
  // error response, so no new transfer is issued while either holds.
  wire hold_idle = err_first | errdly_q;

  // Address phase presented this cycle.
  wire ap_go = req_i & ~hold_idle;

  assign htrans_o = ap_go ? TRANS_NONSEQ : TRANS_IDLE;
  assign haddr_o  = {addr_i[31:2], boff_d};
  assign hwrite_o = we_i;
  assign hsize_o  = size_d;
  assign hburst_o = BURST_SINGLE;
  assign hprot_o  = HPROT_VAL;
  assign hwdata_o = wdata_q;

  // Address phase is accepted, and only then, is the Ibex request granted.
  assign gnt_o = ap_go & hready_i;

  // Data phase completes on hready; that is the single rvalid for this
  // request. The first cycle of a two-cycle error has hready low and so
  // deliberately produces nothing.
  assign rvalid_o = dphase_q & hready_i;
  assign err_o    = dphase_q & hresp_i;
  assign rdata_o  = hrdata_i;

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      dphase_q <= 1'b0;
      errdly_q <= 1'b0;
      wdata_q  <= 32'b0;
    end else begin
      errdly_q <= err_first;
      // The AHB pipeline only advances on hready.
      if (hready_i) begin
        dphase_q <= ap_go;
        if (ap_go) begin
          wdata_q <= wdata_i;
        end
      end
    end
  end

endmodule
