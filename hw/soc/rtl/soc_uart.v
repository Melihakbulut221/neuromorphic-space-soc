// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Console UART, transmit only, on the peripheral bus.
//
// Register map mirrored from GRLIB's APBUART (grip.pdf table 126, quoted
// in docs/08-gr801-datasheet-notes.md section 2.5 and adopted by section
// 3 row 9): 0x00 data, 0x04 status, 0x08 control, 0x0C scaler.
//
// WHAT IS IMPLEMENTED AND WHAT IS NOT. This is a subset and the omitted
// parts are omitted, not stubbed silently:
//
//   * Transmit only. There is no receiver. STATUS.DR reads 0 forever,
//     CTRL.RE is read-only zero, and a read of the data register returns
//     zero. A driver that waits for DR will wait forever, which is the
//     correct behaviour for a part with no receiver and is better than a
//     receiver that appears to exist.
//   * One holding register, not a FIFO. GRLIB's TE ("transmitter FIFO
//     empty") and TS ("shift register empty") therefore differ by one
//     byte rather than by a FIFO depth. TF ("FIFO full") is the holding
//     register being occupied.
//   * No parity, 8 data bits, one stop bit. GRLIB's parity control bits
//     are not implemented and read as zero.
//   * FIFO debug registers (0x10, 0x14) and the capability register
//     (0x18) are not implemented and read as zero.
//
// The transmitter is a real serialiser, not a simulation print hook. It
// divides the system clock by 8*(SCALER+1) as GRLIB's does -- the scaler
// feeds an 8x oversampling clock -- and shifts a start bit, eight data
// bits least significant first, and a stop bit onto tx_o. The testbench
// decodes that line rather than snooping the register write, so the
// baud-rate divider and the shifter are inside what the run proves.
//
// Bus: AMBA 3 APB slave. PREADY is tied high (every access completes in
// the ACCESS cycle) and PSLVERR is tied low: there is no access this
// block can refuse. An offset inside the slot that names no register
// reads as zero and a write to it does nothing, which is GRLIB's
// documented behaviour for unoccupied space behind a bridge (GR740 UM
// section 2.3).

`timescale 1ns / 1ps

module soc_uart (
    input  wire        clk_i,
    input  wire        rst_ni,

    // ---- APB slave ----
    input  wire        psel_i,
    input  wire        penable_i,
    input  wire [11:0] paddr_i,     // offset within the 4 KiB slot
    input  wire        pwrite_i,
    input  wire [31:0] pwdata_i,
    output reg  [31:0] prdata_o,
    output wire        pready_o,
    output wire        pslverr_o,

    output wire        tx_o,
    output wire        irq_o
);

  localparam [11:0] REG_DATA   = 12'h000;
  localparam [11:0] REG_STATUS = 12'h004;
  localparam [11:0] REG_CTRL   = 12'h008;
  localparam [11:0] REG_SCALER = 12'h00C;

  assign pready_o  = 1'b1;
  assign pslverr_o = 1'b0;

  // A write happens in the ACCESS phase, once. PSEL and PENABLE both
  // high with PREADY high is exactly one cycle per transfer.
  wire access = psel_i && penable_i;
  wire wr     = access && pwrite_i;

  // ---- control and scaler ----
  reg        ctrl_te;      // transmitter enable, CTRL bit 1
  reg        ctrl_ti;      // transmitter interrupt enable, CTRL bit 3
  reg [11:0] scaler;

  // ---- holding register and shifter ----
  reg [7:0]  thr;
  reg        thr_full;
  reg [9:0]  shifter;      // {stop, data[7:0], start}
  reg [3:0]  bit_cnt;      // 10 bits to send
  reg        busy;

  reg [11:0] scaler_cnt;
  reg [2:0]  ovs_cnt;      // 8x oversampling, as GRLIB's scaler defines
  wire       scaler_tick = (scaler_cnt == 12'd0);
  wire       bit_tick    = scaler_tick && (ovs_cnt == 3'd7);

  assign tx_o  = busy ? shifter[0] : 1'b1;   // idle line is high
  assign irq_o = ctrl_ti && !thr_full;

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      ctrl_te    <= 1'b0;
      ctrl_ti    <= 1'b0;
      scaler     <= 12'd0;
      thr        <= 8'h0;
      thr_full   <= 1'b0;
      shifter    <= 10'h3FF;
      bit_cnt    <= 4'd0;
      busy       <= 1'b0;
      scaler_cnt <= 12'd0;
      ovs_cnt    <= 3'd0;
    end else begin
      // ---- baud generator ----
      if (scaler_tick) begin
        scaler_cnt <= scaler;
        ovs_cnt    <= ovs_cnt + 3'd1;
      end else begin
        scaler_cnt <= scaler_cnt - 12'd1;
      end

      // ---- serialiser ----
      if (busy) begin
        if (bit_tick) begin
          shifter <= {1'b1, shifter[9:1]};
          if (bit_cnt == 4'd9) begin
            busy    <= 1'b0;
            bit_cnt <= 4'd0;
          end else begin
            bit_cnt <= bit_cnt + 4'd1;
          end
        end
      end else if (thr_full && ctrl_te) begin
        // Load at a bit boundary so the first bit is a full bit wide.
        if (bit_tick) begin
          shifter  <= {1'b1, thr, 1'b0};
          bit_cnt  <= 4'd0;
          busy     <= 1'b1;
          thr_full <= 1'b0;
        end
      end

      // ---- register writes ----
      //
      // AFTER THE SERIALISER, AND THE ORDER IS THE FIX. Both blocks
      // assign `thr_full`, and in one cycle in eight they do it in the
      // same cycle: a DATA write landing exactly on the bit boundary
      // where the loader takes the byte. Verilog's last-assignment-wins
      // then decides which one survives, and with the write block first
      // the loader won -- `shifter` correctly took the OLD `thr`, `thr`
      // correctly took the new byte, and `thr_full` was cleared, so the
      // byte just written was held in a register nothing would ever
      // load. It was lost silently, and STATUS reported the write
      // accepted (TF clear) on the way out.
      //
      // With the write last, the same cycle sends the old byte and keeps
      // the new one: `shifter` still takes the old `thr`, and
      // `thr_full <= 1'b1` wins, so the next boundary loads the byte the
      // driver wrote. Nothing else is shared between the two blocks --
      // `busy`, `bit_cnt` and `shifter` are the serialiser's alone, and
      // `ctrl_te`, `ctrl_ti` and `scaler` are the write block's -- so
      // the swap changes this one interaction and nothing else.
      //
      // Reachable by any driver that writes blind. It is NOT reachable
      // by the five programs in this tree, which all poll TE first, and
      // that is why it survived to 2026-09-11.
      //
      // MEASURED, not reasoned: hw/soc/tb/cocotb/test_soc_uart_defects.py
      // walks a second blind write across all eight phases of the bit
      // boundary at SCALER = 0. On the RTL as it was, phase 3 of 8 put
      // 0xAA on the line and nothing after it; the other seven were the
      // two correct outcomes. One byte in eight of a blind writer's
      // stream. The same file's third test drives a POLLING writer over
      // the same eight phases and loses nothing on either version, which
      // is the control that says why nothing here ever saw it.
      if (wr) begin
        case (paddr_i)
          REG_DATA: begin
            // Overwriting a full holding register drops the previous
            // byte. GRLIB's part does the same when the FIFO is full and
            // reports it through TF; a driver is expected to poll.
            thr      <= pwdata_i[7:0];
            thr_full <= 1'b1;
          end
          REG_CTRL: begin
            ctrl_te <= pwdata_i[1];
            ctrl_ti <= pwdata_i[3];
          end
          REG_SCALER: scaler <= pwdata_i[11:0];
          default: ;
        endcase
      end
    end
  end

  // ---- register reads ----
  //
  // STATUS bit positions are GRLIB's: 0 DR, 1 TS, 2 TE, 7 TF. The bits
  // this part does not implement read as zero rather than as a plausible
  // value.
  always @(*) begin
    case (paddr_i)
      REG_DATA:   prdata_o = 32'h0;                       // no receiver
      REG_STATUS: prdata_o = {24'h0,
                              thr_full,                   // 7 TF
                              4'h0,                       // 6..3
                              ~thr_full,                  // 2 TE
                              ~(busy || thr_full),        // 1 TS
                              1'b0};                      // 0 DR
      REG_CTRL:   prdata_o = {28'h0, ctrl_ti, 1'b0, ctrl_te, 1'b0};
      REG_SCALER: prdata_o = {20'h0, scaler};
      default:    prdata_o = 32'h0;
    endcase
  end

endmodule
