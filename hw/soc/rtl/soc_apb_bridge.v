// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

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

module soc_apb_bridge #(
    // F3, 2026-09-18. ST_ACCESS had exactly one exit, `pready_i`, so a
    // slave that never asserts PREADY holds the fabric's ownership
    // queue and stalls the core until the watchdog's stage-3 reset.
    //
    // NOT A LIVE BUG TODAY, for a reason that is about the
    // instantiation set and not about this module: eight of the nine
    // mapped APB slaves drive PREADY as the literal 1'b1, the ninth
    // (soc_npu) does so at its shipping WAKE_GNT = 0, and an address
    // inside the window that names no slot is completed by soc_top's
    // pready mux. `soc_apb_wb.v` has a genuinely non-constant PREADY
    // and is written and proved but instantiated nowhere. The first
    // time a real wait-state slave is wired in, this becomes live.
    //
    // DEFAULT 0, WHICH IS OFF, and the module is then bit-identical to
    // what it was: every existing measurement, netlist and proof
    // remains reproducible. At a non-zero value the counter runs in
    // ST_ACCESS and on expiry the FABRIC side is released with an
    // error while PSEL and PENABLE STAY ASSERTED. That asymmetry is
    // the whole design: APB has no master-side abort, so dropping them
    // would violate the protocol clause A4 proves. The bridge stays
    // parked on the APB side until reset, which is acceptable because
    // the slave that got it there is already broken; what it buys is
    // that the core sees a bus error it can report instead of a hang
    // only the watchdog ends.
    parameter integer APB_TIMEOUT = 0
) (
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
    // Sticky, cleared only by reset: one or more transactions were
    // abandoned on expiry. BUSSTAT already has a counter shape for a
    // bus event and this is the line it would count.
    output reg         timeout_o,

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
  // Width from the parameter, so a bigger bound costs bits rather than
  // silently wrapping. At APB_TIMEOUT = 0 the counter is one bit wide
  // and the optimiser deletes it with the rest of the arm.
  localparam integer TO_W = (APB_TIMEOUT <= 1) ? 1 : $clog2(APB_TIMEOUT);
  localparam [TO_W-1:0] TO_LIMIT =
      (APB_TIMEOUT <= 1) ? {TO_W{1'b0}}
                         : (APB_TIMEOUT[TO_W-1:0] - {{(TO_W-1){1'b0}}, 1'b1});

  reg [TO_W-1:0] to_cnt;
  reg            to_fired;

  assign psel_o   = (state == ST_SETUP) || (state == ST_ACCESS);
  assign penable_o = (state == ST_ACCESS);

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state    <= ST_IDLE;
      paddr_o  <= 20'h0;
      pwrite_o <= 1'b0;
      pwdata_o <= 32'h0;
      pstrb_o  <= 4'h0;
      rvalid_o  <= 1'b0;
      rdata_o   <= 32'h0;
      err_o     <= 1'b0;
      timeout_o <= 1'b0;
      to_cnt    <= {TO_W{1'b0}};
      to_fired  <= 1'b0;
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
          // `&& !to_fired` found by the proof and not by reading.
          // Without it a slave that asserts PREADY LATE, after the
          // timeout already answered the fabric, sends the machine
          // back to idle and delivers a SECOND response for one
          // request -- which A6 and A9 both forbid and which the
          // ownership queue would mis-pop. Once the timeout has fired
          // the transfer is over as far as the fabric is concerned and
          // the APB side stays parked until reset, which is what the
          // parameter's comment says it does.
          if (pready_i && !to_fired) begin
            rdata_o  <= prdata_i;
            err_o    <= pslverr_i;
            rvalid_o <= 1'b1;
            state    <= ST_IDLE;
            to_cnt   <= {TO_W{1'b0}};
          end else if (APB_TIMEOUT != 0) begin
            if (!to_fired && (to_cnt == TO_LIMIT)) begin
              // Release the FABRIC and hold the APB side. state stays
              // ST_ACCESS, so psel_o and penable_o stay high and A4 is
              // untouched; rvalid_o and err_o go to the core so it
              // gets an error rather than a stall.
              rdata_o   <= 32'h0;
              err_o     <= 1'b1;
              rvalid_o  <= 1'b1;
              to_fired  <= 1'b1;
              timeout_o <= 1'b1;
            end else if (!to_fired) begin
              to_cnt <= to_cnt + {{(TO_W-1){1'b0}}, 1'b1};
            end
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
