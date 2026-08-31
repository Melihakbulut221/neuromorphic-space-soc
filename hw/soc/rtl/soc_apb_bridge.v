// System bus to AMBA APB bridge.
//
// This is the one place in the SoC where a standard bus protocol is
// implemented rather than declined, and docs/39-soc-bus-and-memory-map.md
// section 4 is the argument for why here and not on the system side. In
// short: APB is small enough that compliance can be PROVED rather than
// asserted -- the state machine has three states and the protocol has
// eight rules -- and the peripheral register maps this project is
// mirroring from GRLIB (docs/08 section 3 rows 8-12) are written against
// APB semantics.
//
// Protocol implemented: AMBA 3 APB. Every transfer is
//
//   IDLE    PSEL = 0, PENABLE = 0
//   SETUP   PSEL = 1, PENABLE = 0        exactly one cycle
//   ACCESS  PSEL = 1, PENABLE = 1        until PREADY
//
// with PADDR, PWRITE, PWDATA and PSTRB held stable from SETUP through
// ACCESS, and PSLVERR sampled only in the cycle PREADY is high.
//
// The formal properties in hw/soc/formal/soc_apb_bridge_props.v state
// those rules over this module's PORTS. They were written from the APB
// specification and from the Ibex protocol quoted in soc_bus.v, not from
// the code below -- this repository has twice locked in a bug by
// asserting that an implementation is correct (docs/09 section on
// vacuity, and the npu_regbank episode), so a property here that merely
// restated the state encoding would be worth nothing.
//
// SLAVE SIDE, toward the fabric: this bridge accepts ONE request at a
// time and withholds gnt otherwise. soc_bus.v rule S4 permits that. The
// cost is that a peripheral access takes three cycles back to back
// (accept, SETUP, ACCESS+PREADY, with rvalid overlapping the next
// accept) instead of the one cycle the RAM takes. That is the price of
// APB and it is charged only to peripheral traffic.
//
// PSEL DECODE IS NOT HERE. This module drives a single psel_o meaning
// "the bridge is selecting some peripheral" plus paddr_o; the per-slot
// PSEL comes from soc_top.v, which is where the generated slot constants
// live. A bridge that decoded slots itself would be a second copy of the
// memory map.

`timescale 1ns / 1ps

module soc_apb_bridge (
    input  wire        clk_i,
    input  wire        rst_ni,

    // ---- fabric slave port (Ibex-native protocol, soc_bus.v S1-S4) ----
    input  wire        req_i,
    input  wire [31:0] addr_i,
    input  wire        we_i,
    input  wire [3:0]  be_i,
    input  wire [31:0] wdata_i,
    output wire        gnt_o,
    output reg         rvalid_o,
    output reg  [31:0] rdata_o,
    output reg         err_o,

    // ---- APB master port ----
    // paddr_o is 20 bits: the offset inside the 1 MiB bridge window.
    output wire        psel_o,
    output wire        penable_o,
    output reg  [19:0] paddr_o,
    output reg         pwrite_o,
    output reg  [31:0] pwdata_o,
    output reg  [3:0]  pstrb_o,
    input  wire [31:0] prdata_i,
    input  wire        pready_i,
    input  wire        pslverr_i
);

  localparam [1:0] ST_IDLE   = 2'd0;
  localparam [1:0] ST_SETUP  = 2'd1;
  localparam [1:0] ST_ACCESS = 2'd2;

  reg [1:0] state;

  // gnt in IDLE only. rvalid may coincide with gnt: they belong to
  // different transactions, and the fabric's per-slave ownership queue
  // handles a simultaneous push and pop.
  assign gnt_o    = req_i && (state == ST_IDLE);
  assign psel_o   = (state == ST_SETUP) || (state == ST_ACCESS);
  assign penable_o = (state == ST_ACCESS);

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state    <= ST_IDLE;
      paddr_o  <= 20'h0;
      pwrite_o <= 1'b0;
      pwdata_o <= 32'h0;
      pstrb_o  <= 4'h0;
      rvalid_o <= 1'b0;
      rdata_o  <= 32'h0;
      err_o    <= 1'b0;
    end else begin
      rvalid_o <= 1'b0;
      case (state)
        ST_IDLE: begin
          if (req_i) begin
            // Captured in the grant cycle, which is the only cycle the
            // fabric guarantees the broadcast payload (soc_bus.v S2).
            paddr_o  <= addr_i[19:0];
            pwrite_o <= we_i;
            pwdata_o <= wdata_i;
            pstrb_o  <= be_i;
            state    <= ST_SETUP;
          end
        end
        ST_SETUP: begin
          // SETUP is exactly one cycle, unconditionally. PENABLE rising
          // the cycle after PSEL is the whole of the APB handshake.
          state <= ST_ACCESS;
        end
        ST_ACCESS: begin
          if (pready_i) begin
            rdata_o  <= prdata_i;
            err_o    <= pslverr_i;
            rvalid_o <= 1'b1;
            state    <= ST_IDLE;
          end
        end
        default: state <= ST_IDLE;
      endcase
    end
  end

`ifdef FORMAL
`include "soc_apb_bridge_props.v"
`endif

endmodule
