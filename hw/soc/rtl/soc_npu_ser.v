// soc_npu_ser: the serial host master that drives the frozen pilot.
//
// This is a TRANSPORT and nothing else. It carries one 32-bit register
// transaction at a time onto the four serial pins the TTIHP26b pilot
// exposes -- ser_sck, ser_cs_n, ser_mosi, ser_miso -- and it exists
// because those four pins are the only way into that die's register
// bank. docs/51-npu-integration.md section 3 is the argument for
// driving the frozen module rather than adding a parallel port to a
// copy of it; this file is the consequence of that argument and it has
// no opinion about the register map above it.
//
// =====================================================================
// THE PROTOCOL, which is a specification and not a description of this
// file
// =====================================================================
//
// Restated from hw/rtl/pilot_top.v section 2, which is the normative
// statement of what the die accepts. This module has to be correct
// against that text, not against itself, and
// hw/soc/formal/soc_npu_ser_props.v states the same clauses over this
// module's ports.
//
//   P1. Mode-0 SPI slave: CPOL = 0, CPHA = 0, MSB first. The slave
//       samples SER_MOSI on the RISING edge of SER_SCK and moves
//       SER_MISO on the FALLING edge.
//   P2. One register per frame. A frame is 40 SER_SCK cycles:
//         bits 39..32   command byte { WR, ADDR[6:0] }, WR = 1 writes
//         bits 31..0    register data, MSB first
//       ADDR[6:0] is the regmap byte offset shifted right by two.
//   P3. Reads: the addressed register is captured when the command byte
//       completes and shifted out on the following falling edges, so
//       data bit 31 is readable on SER_SCK cycle 9. Read side effects
//       -- the EVQ_OUT pop -- happen once, at that capture.
//   P4. Writes commit on the 40th rising edge, not at CS_N release, so
//       an aborted frame changes nothing.
//
// and three HOST obligations, which pilot_top.v calls H1, H2 and H3 and
// says all three are real:
//
//   H1. SER_SCK <= clk/4.
//   H2. SER_CS_N falls at least one full SER_SCK period before the
//       first SER_SCK edge.
//   H3. SER_CS_N stays high at least one full SER_SCK period BETWEEN
//       frames.
//
// H2 and H3 exist because the die two-flop synchronizes all four pins.
// H3 in particular was found during the pilot's own bring-up with a
// half-period gap: the bit counter is held at zero only while the
// SYNCHRONIZED select reads inactive, so a deselect that is never seen
// leaves the counter running and the next frame decodes at the wrong
// offset. This module satisfies both by construction -- SETUP and GAP
// are each one full SER_SCK period -- and the formal job asserts it
// rather than leaving it to the state encoding.
//
// =====================================================================
// TIMING: WHY HALF = 2 IS THE DEFAULT AND WHERE ITS MARGIN IS
// =====================================================================
//
// HALF is the number of clk cycles in one SER_SCK half period, so
// SER_SCK = clk / (2*HALF) and HALF = 2 is H1 at its documented limit --
// the same rate hw/tb/test_pilot_top.py drives, whose docstring says it
// runs there deliberately.
//
// The one edge that has to be got right is when the host may sample
// SER_MISO, and the answer is NOT "any time SER_SCK is high". The die
// drives ser_miso from tx_sh[31], and tx_sh shifts on its own
// SYNCHRONIZED falling edge: two synchronizer flops plus an edge
// detect, so the new bit appears three clk cycles after the falling
// edge on the pin. The next SER_SCK high phase ENDS 2*HALF - 1 cycles
// after that same falling edge. At HALF = 2 those are the same cycle.
//
//   THIS MODULE THEREFORE SAMPLES SER_MISO IN THE LAST clk CYCLE OF THE
//   SER_SCK HIGH PHASE, WHICH IS THE FIRST CYCLE THE BIT IS THERE AT
//   HALF = 2 AND HAS 2*(HALF-2) CYCLES OF SLACK ABOVE IT.
//
// Sampling at the rising edge instead -- the textbook mode-0 point, and
// what a bench host with a scope does -- returns the PREVIOUS bit at
// HALF = 2 and the whole word comes back shifted by one position.
//
// That analysis holds because inside an SoC the master and the die
// share one clock, so the synchronizers are pure delay and the phase is
// deterministic. IT DOES NOT HOLD FOR A BENCH HOST DRIVING REAL
// SILICON over an independent clock, and the honest consequence is that
// a bench must raise HALF. HALF is a parameter for exactly that reason
// and for no other.
//
// =====================================================================
// WHAT THIS MODULE DOES NOT DO
// =====================================================================
//
// It does not know the register map. addr_i is the seven-bit word index
// P2 defines and this module passes it through; which offsets exist,
// which are read-only and which have side effects are soc_npu.v's
// problem and the die's.
//
// It has no timeout. A frame always completes in a fixed number of
// cycles because nothing in the protocol can stall it -- there is no
// ready signal on a mode-0 slave -- so `busy_o` falls on a schedule and
// not on a handshake. A die that is absent or unpowered returns all
// ones or all zeros and this module reports it as data; detecting that
// is a job for whatever reads NPUCFG's identity word.

`timescale 1ns / 1ps

module soc_npu_ser #(
    // clk cycles per SER_SCK half period. 2 is H1 at its limit.
    parameter integer HALF = 2
) (
    input  wire        clk_i,
    input  wire        rst_ni,

    // ---- transaction port ----
    // start_i is a one-cycle pulse and is ignored while busy_o is high.
    // addr_i/we_i/wdata_i are captured in the start cycle.
    input  wire        start_i,
    input  wire        we_i,
    input  wire [6:0]  addr_i,
    input  wire [31:0] wdata_i,
    output wire        busy_o,
    output reg         done_o,      // one cycle, the frame has completed
    output reg  [31:0] rdata_o,     // valid from done_o onward

    // ---- serial pins, toward the frozen pilot ----
    output reg         ser_sck_o,
    output reg         ser_cs_n_o,
    output reg         ser_mosi_o,
    input  wire        ser_miso_i
);

  // HALF < 2 violates H1. Fail elaboration with the reason as the
  // message, the house style hw/rtl/aer_fifo.v established.
  generate
    if (HALF < 2) begin : g_bad_half
      ERROR_soc_npu_ser_HALF_below_2_violates_pilot_host_obligation_H1 g ();
    end
  endgenerate

  localparam integer NBITS = 40;

  localparam [1:0] ST_IDLE  = 2'd0;
  localparam [1:0] ST_SETUP = 2'd1;   // CS_N low, SCK still low   (H2)
  localparam [1:0] ST_SHIFT = 2'd2;   // 40 SER_SCK cycles
  localparam [1:0] ST_GAP   = 2'd3;   // CS_N high between frames  (H3)

  reg [1:0]  state;
  reg [39:0] tx;              // command byte then write data, MSB first
  reg [31:0] rx;
  reg [5:0]  bit_cnt;         // 0..NBITS-1
  reg [1:0]  hcnt;            // half periods elapsed in this state, or
                              // in ST_SHIFT: 0 = SER_SCK low, 1 = high
  reg [15:0] tick;            // clk cycles elapsed in the current half

  wire half_done = (tick == HALF[15:0] - 16'd1);

  assign busy_o = (state != ST_IDLE);

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state      <= ST_IDLE;
      tx         <= 40'd0;
      rx         <= 32'd0;
      bit_cnt    <= 6'd0;
      hcnt       <= 2'd0;
      tick       <= 16'd0;
      done_o     <= 1'b0;
      rdata_o    <= 32'd0;
      ser_sck_o  <= 1'b0;
      ser_cs_n_o <= 1'b1;
      ser_mosi_o <= 1'b0;
    end else begin
      done_o <= 1'b0;

      case (state)
        ST_IDLE: begin
          ser_sck_o  <= 1'b0;
          ser_cs_n_o <= 1'b1;
          ser_mosi_o <= 1'b0;
          if (start_i) begin
            // P2's frame content, assembled once. Nothing below looks
            // at addr_i or wdata_i again, so the caller may drop them
            // in the next cycle.
            tx         <= {we_i, addr_i, wdata_i};
            rx         <= 32'd0;
            bit_cnt    <= 6'd0;
            hcnt       <= 2'd0;
            tick       <= 16'd0;
            ser_cs_n_o <= 1'b0;
            state      <= ST_SETUP;
          end
        end

        // H2: one full SER_SCK period of select setup, so the die's
        // frame-start reset clears its synchronizer before the first
        // sampled clock edge arrives. Two half periods, counted the
        // same way the shift phases are.
        ST_SETUP: begin
          ser_mosi_o <= tx[39];
          if (half_done) begin
            tick <= 16'd0;
            if (hcnt == 2'd1) begin
              hcnt  <= 2'd0;
              state <= ST_SHIFT;
            end else begin
              hcnt <= hcnt + 2'd1;
            end
          end else begin
            tick <= tick + 16'd1;
          end
        end

        ST_SHIFT: begin
          if (hcnt == 2'd0) begin
            // Low half. SER_MOSI is already presenting this bit; it was
            // driven one full half period before the rising edge, which
            // is what the die's own two-flop MOSI synchronizer needs.
            ser_sck_o <= 1'b0;
            if (half_done) begin
              tick      <= 16'd0;
              hcnt      <= 2'd1;
              ser_sck_o <= 1'b1;
            end else begin
              tick <= tick + 16'd1;
            end
          end else begin
            // High half. SER_MISO is sampled in its LAST cycle -- see
            // the timing section in the header; this is the load-bearing
            // line of the module.
            if (half_done) begin
              rx        <= {rx[30:0], ser_miso_i};
              tick      <= 16'd0;
              hcnt      <= 2'd0;
              ser_sck_o <= 1'b0;
              tx        <= {tx[38:0], 1'b0};
              ser_mosi_o <= tx[38];
              if (bit_cnt == NBITS[5:0] - 6'd1) begin
                state <= ST_GAP;
              end else begin
                bit_cnt <= bit_cnt + 6'd1;
              end
            end else begin
              tick <= tick + 16'd1;
            end
          end
        end

        // H3: the deselect must be SEEN, for one full SER_SCK period.
        // Three half periods: one trailing with CS_N still low so the
        // last falling edge is seen too, then two with CS_N high.
        ST_GAP: begin
          ser_mosi_o <= 1'b0;
          if (half_done) begin
            tick <= 16'd0;
            hcnt <= hcnt + 2'd1;
            if (hcnt == 2'd0) begin
              ser_cs_n_o <= 1'b1;
            end else if (hcnt == 2'd2) begin
              // rx holds the last 32 of the 40 sampled MISO bits, which
              // are SER_SCK cycles 9..40. P3 puts data bit 31 on cycle
              // 9, so the eight command-byte-window samples have already
              // been shifted out of rx by construction.
              rdata_o <= rx;
              done_o  <= 1'b1;
              hcnt    <= 2'd0;
              state   <= ST_IDLE;
            end
          end else begin
            tick <= tick + 16'd1;
          end
        end

        default: state <= ST_IDLE;
      endcase
    end
  end

`ifdef FORMAL
`include "soc_npu_ser_props.v"
`endif

endmodule
