// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// AMBA APB completer to Wishbone B3 classic initiator, with a 32-to-8
// bit lane adapter.
//
// =====================================================================
// WHY THIS BRIDGE, AND WHY IT IS PROVED ON ITS OWN
// =====================================================================
//
// docs/65-gpio-and-the-interface-ip-assessment.md section 9.4 priced
// the bridges the selected interface IP needs and found the one
// structural fact in the table: two of the four cores -- the Mohor CAN
// controller and alexforencich's verilog-i2c -- are both Wishbone
// classic with an 8-bit data path, so ONE bridge, proved once, serves
// both. This is that bridge. It is written and proved before either
// core is wrapped, for the reason soc_gpio.v's header gives: when the
// second block fails, the failure should be in the core's wrapper and
// not in the bridge.
//
// The two cores' Wishbone ports, read from the pinned checkouts [fact]:
//
//   can_top.v (CAN_WISHBONE_IF)   wb_adr_i[7:0]  wb_dat_i[7:0]  wb_dat_o[7:0]
//                                 wb_cyc_i wb_stb_i wb_we_i wb_ack_o
//   i2c_master_wbs_8.v            wbs_adr_i[2:0] wbs_dat_i[7:0] wbs_dat_o[7:0]
//                                 wbs_cyc_i wbs_stb_i wbs_we_i wbs_ack_o
//
// Neither has SEL, ERR or RTY. The bridge still has all three, because
// they are part of the Wishbone B3 initiator interface and a bridge
// that omitted them would have to be re-proved for the first core that
// has them; at these two instantiations err_i and rty_i are tied low
// and sel_o is left open, and PSLVERR can then never rise.
//
// =====================================================================
// THE TWO PROTOCOLS
// =====================================================================
//
// APB side: AMBA 3 APB, the completer half of what soc_apb_bridge.v
// implements the requester half of. SETUP is one cycle with PSEL high
// and PENABLE low; ACCESS follows with both high and lasts until this
// module raises PREADY; PADDR, PWRITE, PWDATA and PSTRB are stable from
// SETUP to the end of ACCESS; PSLVERR is meaningful only in the PREADY
// cycle.
//
// Wishbone side: B3 CLASSIC single read and single write cycles, and
// nothing else -- no block cycles, no read-modify-write, no pipelined
// (B4) mode, no tags. The initiator raises CYC and STB together with
// ADR, WE, DAT and SEL, holds all of them unchanged until the target
// answers with ACK, ERR or RTY, then drops CYC and STB in the next
// cycle. Both cores need exactly that: the CAN core resynchronises
// cyc & stb into its own clock domain over several cycles and pulses
// ack once, and the I2C core toggles ack every cycle it sees stb, so a
// requester that did not drop stb after ack would get a second one.
//
// =====================================================================
// THE LANE ADAPTER
// =====================================================================
//
// One APB transfer is one Wishbone cycle, and the byte travels on ONE
// lane of PWDATA / PRDATA. Which lane is a question this fabric answers
// with PSTRB and not with PADDR, because of two facts read from the
// pinned sources [fact]:
//
//   * Ibex word-aligns every data address it issues.
//     hw/soc/ext/ibex/rtl/ibex_load_store_unit.sv, under "output data
//     address must be word aligned": data_addr_o = {data_addr[31:2],
//     2'b00}. The byte offset of an lb/lbu/sb travels in data_be_o as a
//     one-hot byte enable, for loads exactly as for stores -- the BE
//     generation block there is a function of the access type and the
//     offset and does not look at the direction -- and a load takes its
//     byte back from the lane that enable named (rdata_b_ext, selected
//     by rdata_offset_q).
//   * The fabric carries that byte enable to this port unchanged.
//     soc_bus.v passes md_be_i through as s_be_o; soc_apb_bridge.v
//     captures be_i into pstrb_o for reads as well as writes, which
//     soc_apb_bridge_props.v A11 proves.
//
// So at this port PADDR[1:0] is always 2'b00 and PSTRB alone names the
// lane. The first draft of this file decoded the lane from PADDR[1:0],
// and the proof passed, because the contract it proved was one the
// fabric cannot drive: from the CPU that bridge reached only the
// word-aligned quarter of each core's register file, and a byte store
// to any other register landed in the aligned one with the wrong byte
// (docs/65 section 9.5, the correction dated 2026-09-15, has the
// argument and an Icarus measurement of that draft: sb 0x5A at byte
// offset 1 wrote 0x00 to offset 0). The lane is the LOWEST set bit of
// PSTRB:
//
//   PSTRB      lane   write: dat_o =        read: prdata_o =
//   4'b???1    0      pwdata_i[ 7: 0]       {24'h0, byte      }
//   4'b??10    1      pwdata_i[15: 8]       {16'h0, byte,  8'h0}
//   4'b?100    2      pwdata_i[23:16]       { 8'h0, byte, 16'h0}
//   4'b1000    3      pwdata_i[31:24]       {       byte, 24'h0}
//   4'b0000    0      pwdata_i[ 7: 0]       {24'h0, byte      }
//
// which is the lane a byte access from Ibex names, so a driver reads
// and writes the cores' byte registers with lb/lbu/sb at their natural
// byte offsets and shifts nothing. A half-word or word access, with
// two or four strobes, reaches its lowest byte only; a requester that
// drives PSTRB low on a read gets lane 0. adr_o is the APB offset with
// its low two bits REPLACED by the lane, {paddr_i[ADR_W-1:2], lane}, so
// the target is addressed with the byte offset the software wrote.
// PADDR[1:0] is therefore not consulted, and a requester that encoded
// the byte offset there while driving all four strobes would be served
// at lane 0 of the aligned word; this fabric's requester is not that
// requester, and the properties say what PADDR[1:0] the lane covers
// are driven with.
//
// This is the one completer in the SoC that consults PSTRB. soc_top.v's
// note on pstrb -- "registers written whole" -- describes the 32-bit
// register files it was written for and not a byte-lane adapter; the
// _unused_pstrb tie there is the instantiation's to retire when this
// bridge is wired in, and that instantiation is not in this file.
//
// The truncation of adr_o to the core's own address width (8 bits for
// CAN, 3 for I2C) belongs to the instantiation, as does the polarity
// inversion of the reset: both cores take an active-high wb_rst_i and
// this SoC's fabric is active-low.
//
// =====================================================================
// TERMINATION, ONE OUTSTANDING, AND THE PRICE
// =====================================================================
//
// ACK ends the cycle cleanly. ERR ends it with PSLVERR high. RTY ends
// it with PSLVERR high too: APB has no retry, and a bridge that
// re-issued the cycle in hardware would turn a target that keeps
// saying "retry" into a bus that never answers, with no bound on the
// loop and nothing above the bridge able to see it. The requester sees
// an error and decides; that decision belongs to software, where a
// retry count can live.
//
// The response is REGISTERED. Termination is sampled at the clock edge,
// the data byte and the error flag are captured, and PREADY is raised
// in the following cycle from the captured copies. There is no
// combinational path from ack_i, err_i, rty_i or dat_i to any output, so
// a target whose ack is a combinational function of stb (the I2C core's
// is a flop, the CAN core's is a flop, but the next core's may not be)
// cannot close a loop through this bridge.
//
// One transfer at a time, by construction: the APB requester cannot
// present a second transfer before PREADY, and this module does not
// raise PREADY before the cycle it launched has terminated. The cost is
// three cycles per access with a zero-wait target -- SETUP, the strobe
// cycle, the response cycle -- plus every wait state the target adds.
// The cycle is launched from SETUP, because APB guarantees the payload
// there and waiting for ACCESS would add a fourth cycle for nothing;
// a requester that presents ACCESS without a SETUP (which APB forbids)
// is served from ACCESS instead, so nothing hangs on that mistake.
//
// The formal properties in hw/soc/formal/soc_apb_wb_props.v state the
// rules of both protocols over this module's PORTS and were written
// from the Wishbone B3 datasheet and the AMBA 3 APB specification, not
// from the code below, for the reason soc_apb_bridge.v's header gives.

`timescale 1ns / 1ps

module soc_apb_wb #(
    // The offset the fabric hands every completer is the 4 KiB slot
    // (soc_top.v connects paddr[11:0]). Must be at least 2: the low two
    // bits of adr_o carry the lane.
    parameter ADR_W = 12
) (
    input  wire             clk_i,
    input  wire             rst_ni,

    // ---- APB completer port, as soc_gpio.v and soc_uart.v present it, ----
    // ---- plus PSTRB, which this completer is the first to consult    ----
    input  wire             psel_i,
    input  wire             penable_i,
    input  wire [ADR_W-1:0] paddr_i,
    input  wire             pwrite_i,
    input  wire [31:0]      pwdata_i,
    input  wire [3:0]       pstrb_i,
    output reg  [31:0]      prdata_o,
    output wire             pready_o,
    output wire             pslverr_o,

    // ---- Wishbone B3 classic initiator port, 8-bit data, 8-bit granularity ----
    output wire             cyc_o,
    output wire             stb_o,
    output reg              we_o,
    output reg  [ADR_W-1:0] adr_o,
    output reg  [7:0]       dat_o,
    output wire             sel_o,     // one lane, one bit; high with stb_o
    input  wire [7:0]       dat_i,
    input  wire             ack_i,
    input  wire             err_i,
    input  wire             rty_i
);

  localparam [1:0] ST_IDLE  = 2'd0;   // no transfer; watching for PSEL
  localparam [1:0] ST_CYCLE = 2'd1;   // cyc/stb high, waiting for the target
  localparam [1:0] ST_RESP  = 2'd2;   // PREADY high for this one cycle

  reg [1:0] state;
  reg [7:0] rdata_q;    // dat_i captured at termination
  reg       err_q;      // err_i | rty_i captured at termination

  wire wb_term = ack_i | err_i | rty_i;

  assign cyc_o     = (state == ST_CYCLE);
  assign stb_o     = (state == ST_CYCLE);
  assign sel_o     = (state == ST_CYCLE);
  assign pready_o  = (state == ST_RESP);
  assign pslverr_o = (state == ST_RESP) && err_q;

  // PENABLE is not consulted. The cycle is launched from SETUP, and the
  // response lands in ACCESS because the requester's own rules put it
  // there -- SETUP is one cycle and ACCESS holds until PREADY, which
  // soc_apb_bridge_props.v A2 and A4 prove of the fabric's requester.
  // The port is kept because it is the completer interface and the
  // properties state ACCESS on it. Named so the unused signal is a
  // decision rather than an oversight.
  wire _unused_penable = &{1'b0, penable_i, 1'b0};

  // PADDR[1:0] is not consulted either: the lane comes from PSTRB (the
  // header says why) and replaces these two bits in adr_o. From this
  // fabric they are always zero. Same idiom, same reason.
  wire _unused_paddr_lo = &{1'b0, paddr_i[1:0], 1'b0};

  // The lane PSTRB names: its lowest set bit, lane 0 when no bit is
  // set. A function rather than a priority chain written out twice, so
  // that the write-data select and the address -- and, through adr_o,
  // the read-data select -- cannot drift apart.
  function [1:0] lane_of;
    input [3:0] strb;
    begin
      casez (strb)
        4'b???1: lane_of = 2'd0;
        4'b??10: lane_of = 2'd1;
        4'b?100: lane_of = 2'd2;
        4'b1000: lane_of = 2'd3;
        default: lane_of = 2'd0;
      endcase
    end
  endfunction

  wire [1:0] lane = lane_of(pstrb_i);

  // The captured byte on the lane the strobe selected, zero elsewhere.
  // The lane is adr_o[1:0], the captured offset's own low bits, rather
  // than a second register holding a copy of the lane: the first
  // induction attempt found exactly that copy free to disagree with the
  // address in an unreachable state, and a register that cannot exist
  // cannot disagree. Not gated by ST_RESP: APB says PRDATA is meaningful
  // only in the PREADY cycle and the fabric's bridge captures it only
  // then.
  always @(*) begin
    prdata_o = 32'h0;
    case (adr_o[1:0])
      2'd0: prdata_o[7:0]   = rdata_q;
      2'd1: prdata_o[15:8]  = rdata_q;
      2'd2: prdata_o[23:16] = rdata_q;
      2'd3: prdata_o[31:24] = rdata_q;
    endcase
  end

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state   <= ST_IDLE;
      rdata_q <= 8'h0;
      err_q   <= 1'b0;
      we_o    <= 1'b0;
      adr_o   <= {ADR_W{1'b0}};
      dat_o   <= 8'h0;
    end else begin
      case (state)
        ST_IDLE: begin
          // PSEL in IDLE is SETUP for a requester that obeys APB, and the
          // payload is guaranteed from SETUP on. Captured here so that
          // the strobe cycle is the first ACCESS cycle. The address the
          // target sees is the word offset with the strobe's lane in its
          // low two bits, which is the byte offset the software wrote.
          if (psel_i) begin
            adr_o  <= {paddr_i[ADR_W-1:2], lane};
            we_o   <= pwrite_i;
            case (lane)
              2'd0: dat_o <= pwdata_i[7:0];
              2'd1: dat_o <= pwdata_i[15:8];
              2'd2: dat_o <= pwdata_i[23:16];
              2'd3: dat_o <= pwdata_i[31:24];
            endcase
            state <= ST_CYCLE;
          end
        end
        ST_CYCLE: begin
          // Everything the target sees is held by not being assigned.
          // Any of the three terminating signals ends the cycle at this
          // edge; ERR and RTY both become PSLVERR.
          if (wb_term) begin
            rdata_q <= dat_i;
            err_q   <= err_i | rty_i;
            state   <= ST_RESP;
          end
        end
        ST_RESP: begin
          // Exactly one cycle, unconditionally: PREADY high ends the
          // APB transfer and the requester may present the next SETUP
          // in the cycle after this one, which is IDLE.
          state <= ST_IDLE;
        end
        default: state <= ST_IDLE;
      endcase
    end
  end

`ifdef FORMAL
`include "soc_apb_wb_props.v"
`endif

endmodule
