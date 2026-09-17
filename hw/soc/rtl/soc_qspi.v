// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// QSPI flash controller, register mode, two chip selects, on APB.
//
// =====================================================================
// WHY THIS BLOCK EXISTS, AND WHAT IT IS NOT
// =====================================================================
//
// docs/51-npu-integration.md section 14 item 4: "No QSPI weight path ...
// there is no QSPI controller; weights are loaded a register at a time"
// from arrays the boot ROM image carries. That is a bring-up
// convenience. A flight part holds its weight image in external flash,
// and this is the block that reads it: the ONE interface the NPU itself
// needs, and the block docs/65 section 13 recommends writing from
// scratch rather than wrapping OpenTitan's spi_host, whose measured
// cost (65 kGE, 171 % of the Ibex core, four fifths of it FIFO storage
// at depths fixed in a generated package) is in docs/65 section 8.4.
//
// It is a REGISTER-MODE controller: software describes one flash
// transaction -- an opcode, an optional 24-bit address, dummy clocks, a
// data phase of any length in either direction, on one or four lanes --
// and the block drives it on the pins while software pulls words out of
// RX or pushes them into TX. It is NOT an execute-in-place controller.
// The two XIP windows the map reserves at QSPI3 and QSPI4 stay reserved,
// and docs/66 section 2 is the argument: XIP makes this block a fabric
// slave as well as an APB one, which is a change to soc_bus.v and a
// re-proof of it, and a quad read is about forty system clocks per word
// on a core with no cache, where docs/50 measured one extra cycle of
// memory latency at 25 % of run time. That is a document of its own.
//
// =====================================================================
// THE PART THE TESTBENCH MODELS, AND THE COMMANDS THIS BLOCK CAN SEND
// =====================================================================
//
// hw/soc/tb/flash_w25q128jv.v is a behavioural model of the Winbond
// W25Q128JV (datasheet Revision M, 2024-12-24), written from that
// datasheet and not from this file. The block itself knows nothing of
// the part: every field below is generic, and the part's command set is
// a matter for the driver. What the driver in hw/soc/tb/sw/soc_qspi.h
// uses, with the datasheet section that defines each:
//
//   9Fh  Read JEDEC ID          8.2.27   1-1-1, 3 bytes in
//   05h  Read Status Register-1 8.2.4    1-1-1, 1 byte in, BUSY is bit 0
//   35h  Read Status Register-2 8.2.4    1-1-1, 1 byte in, QE is bit 1
//   50h  Volatile SR Write En.  8.2.2    1-0-0
//   06h  Write Enable           8.2.1    1-0-0
//   31h  Write Status Reg-2     8.2.5    1-0-1, 1 byte out (sets QE)
//   03h  Read Data              8.2.6    1-1-1, no dummy, <= 50 MHz
//   0Bh  Fast Read              8.2.7    1-1-1, 8 dummy
//   6Bh  Fast Read Quad Output  8.2.9    1-1-4, 8 dummy, needs QE
//   EBh  Fast Read Quad I/O     8.2.11   1-4-4, M7-0 + 4 dummy, needs QE
//   02h  Page Program           8.2.13   1-1-1, up to 256 bytes out
//
// (x-y-z: lanes for opcode, address, data.) Quad I/O is the reason the
// block has four data lanes: docs/65 section 13 -- "quad I/O read is
// the whole reason for the Q; a 1-bit SPI controller is a different,
// smaller block."
//
// =====================================================================
// THE REGISTER MAP
// =====================================================================
//
// The first five offsets follow the shape of GRLIB's SPIMCTRL (docs/08
// section 2.5 row 8, GR716B usage): configuration, control, status,
// receive, transmit. grip.pdf was not readable in the environment this
// block was written in, so the offsets and bit names are SPIMCTRL's as
// docs/08 recalls them and NOT a verbatim mirror; docs/66 section 3.1
// says so. Everything from 0x14 up is this project's, because
// SPIMCTRL's user mode is one byte at a time on one lane and a quad
// data phase needs a transaction description.
//
//   0x00  CONF   rw   [DIV_W-1:0] DIV   SCK = clk / (2 * (DIV + 1))
//                     [11:8]      CS    which chip select the next
//                                       transaction asserts (0..NCS-1)
//   0x04  CTRL   rw   [0] RST   write 1: abort the transaction in
//                               progress: at the next falling edge of
//                               SCK (at once if SCK is low) the lanes
//                               are released and CS rises one half
//                               period later; DR, TXE and the TX word
//                               are cleared at once; the block stays
//                               BUSY through the deselect gap and then
//                               sets DONE as after any frame. Reads 0.
//                     [1] IEN   interrupt enable
//   0x08  STAT   r    [0] BUSY  a transaction is in progress, including
//                               the deselect gap after it
//                     [1] DR    RX holds a word software has not read
//                     [2] DONE  a transaction has finished, including
//                               its deselect gap, so a CMD write will
//                               now be accepted (w1c). Set after an
//                               abort too, for the same reason.
//                     [3] LOST  a CMD, CONF or ADDR write arrived while
//                               BUSY and was ignored (w1c)
//                     [4] TXE   the data phase is waiting for a TX word
//   0x0C  RX     r    the received word; reading it clears DR and lets
//                     the transaction continue. Byte lanes are
//                     LITTLE-ENDIAN: the first byte off the wire is
//                     [7:0], the fourth is [31:24], so a 32-bit word
//                     stored little-endian in the flash image reads
//                     back as itself. Bytes past LEN in a short last
//                     word read zero.
//   0x10  TX     w    the word to transmit next, same lane order:
//                     [7:0] goes first. Writing it clears TXE.
//   0x14  CMD    rw   [7:0]   OP     the opcode, sent MSB first on IO0
//                     [11:8]  DUMMY  clocks between the address (or the
//                                    opcode) and the data phase
//                     [12]    ADDR   send a 24-bit address after OP
//                     [13]    AQUAD  the address on four lanes, and the
//                                    first two DUMMY clocks carry M7-0
//                                    = FFh on the four lanes (the
//                                    part's 8.2.11 note 11: "should be
//                                    set to Fxh", and Fxh keeps it out
//                                    of continuous read mode)
//                     [14]    DQUAD  the data phase on four lanes
//                     [15]    WRITE  data goes out (TX) rather than in
//                     [31:16] LEN    bytes in the data phase, 0..65535;
//                                    0 means no data phase
//                     WRITING CMD STARTS THE TRANSACTION. If the block
//                     is BUSY the write is ignored and STAT.LOST is set.
//   0x18  ADDR   rw   [23:0] the address, sent A23 first
//
// Any other offset reads zero and ignores writes.
//
// =====================================================================
// THE TRANSACTION, ON THE PINS
// =====================================================================
//
// SPI mode 0: SCK idles low, outputs change on the falling edge, both
// sides sample on the rising edge. The chip select falls with SCK low,
// one half SCK period before the first rising edge (tSLCH, 3 ns in the
// part's table 9.6, is therefore DIV + 1 system clocks), and rises one
// half period after the last falling edge (tCHSH, 3 ns). After it rises
// the block stays BUSY for four SCK periods with every chip select high
// -- 8 * (DIV + 1) clocks, which at DIV = 0 and a 100 MHz clock is 80 ns
// against the part's 50 ns deselect time after a write (tSHSL2) and
// 10 ns after a read. A slower clock only lengthens it; docs/66 section
// 3.3 states the clock at which the margin would vanish.
//
// The frame is opcode, address, dummy, data, in that order, and any of
// the last three may be absent. What the four lanes do in each phase:
//
//   opcode          IO0 driven, IO1 released, IO2 and IO3 DRIVEN HIGH
//   address, 1 lane the same
//   address, 4 lane all four driven
//   dummy           first two clocks after a quad address: all four
//                   driven high (M7-0 = FFh); the rest: all four
//                   released if the data phase is quad, otherwise as
//                   the opcode phase
//   data in         all four released if quad; else as the opcode phase
//   data out        all four driven if quad; else IO0 driven, IO2 and
//                   IO3 high
//
// IO2 and IO3 are driven high in every single-lane phase because on
// this part they are /WP and /HOLD until the QE bit is set (datasheet
// 4.3, 4.4, 7.1.4): a released /HOLD that a board pulled low would pause
// the flash mid-frame. Once QE is set the part ignores them as control
// pins and reads them as data lanes, and in every quad phase this block
// drives or releases them as data. The lanes are released before the
// first data-out clock of a quad read because 8.2.9 asks for it: "the
// IO pins should be high-impedance prior to the falling edge of the
// first data out clock."
//
// THE DATA PHASE PAUSES AT EVERY WORD. Four bytes in, and the block
// holds SCK low with CS still asserted, sets DR and waits for software
// to read RX; four bytes out, and it waits for TX. So a data phase of
// any length needs one word of storage and no FIFO, and the flash --
// which is static and has no minimum clock frequency (table 9.6, "D.C.")
// -- simply waits. That is the whole of the difference between this
// block and the one docs/65 section 8.4 measured: the storage is where
// software is, not where the block is.
//
// =====================================================================
// BUS
// =====================================================================
//
// AMBA 3 APB slave, the conventions soc_uart.v, soc_gpio.v and
// soc_busstat.v use: PREADY tied high, PSLVERR tied low. A read of RX has
// a side effect (it clears DR and resumes the transaction) and it is the
// only read that does. Bits above a field read zero and are not stored.
// PSTRB is not honoured; every register is written whole.
//
// =====================================================================
// THE PINS
// =====================================================================
//
// There is no pad ring, so each IO lane leaves this module as three
// wires -- what to drive, whether to drive, what the pad sees -- the
// arrangement soc_gpio.v established. sck_o and cs_no are outputs only.
// hw/soc/tb/tb_soc.v resolves the three wires per lane on a tri-state
// net with a pull-up and hangs the flash model on it.
//
// =====================================================================
// WHAT IS NOT HERE
// =====================================================================
//
//   * No execute-in-place. Header, and docs/66 section 2.
//   * No 4-byte addressing, no dual lanes, no QPI mode (the command
//     phase is always one lane), no continuous-read mode.
//   * No DMA and no FIFO. Software moves every word.
//   * No hardening. An upset in the sequencer's state is a frame that
//     ends early or never; CTRL.RST is the recovery and the watchdog
//     is the backstop, and nothing here reports the upset.
//   * No sampling delay adjustment. Inputs are sampled at the rising
//     edge the block itself generates, so the SCK period must exceed
//     twice the part's clock-low-to-output-valid time (6 ns): docs/66
//     section 3.3.
//
// THE MINIMUM LEGAL DIVIDER, with the arithmetic rather than the
// conclusion (added 2026-09-18 for the external review's F4, which
// found that the ceiling above was stated and the budget under it was
// not).
//
//   SCK          = clk_i / (2 * (DIV + 1))                 line 73
//   half period  = (DIV + 1) * CLOCK_PERIOD                lines 130-131
//
// One half period is the whole external budget, because `io_i` goes
// straight into `cur` at line 472 with no intermediate flop, on the
// same clk_i edge that raises sck_q. It must cover, in order:
//
//   clk_i -> pad, board flight out, the part's tCLQV, board flight
//   back, pad -> core, and setup at `cur`.
//
//   tCLQV        6.0 ns    hw/soc/tb/flash_w25q128jv.v:113 (W25Q128JV)
//   board        2.0 ns    ASSUMED each way. There is no board, no pad
//                          ring (see line 186) and no pad model in this
//                          repository, so this is an assumption and is
//                          named as one; hw/soc/sta/soc_top_qspi_io.sdc
//                          carries it as a variable to be replaced by a
//                          measurement.
//
//   DIV >= ceil((tCLQV + 2 * board) / CLOCK_PERIOD) - 1
//
// At CLOCK_PERIOD = 20 ns, the value every layout in this repository
// was built at: ceil(10 / 20) - 1 = 0. DIV = 0 is legal, with 10 ns of
// the 20 left for setup and for whatever the assumption is wrong
// about. At 10 ns it is DIV >= 0 with nothing left over; at 5 ns,
// DIV >= 1. The arithmetic is here so that a reader who changes
// CLOCK_PERIOD recomputes it rather than inheriting a conclusion taken
// at 20 ns.
//
// NO SYNCHRONISER BELONGS ON THIS PATH, and that is worth saying
// because it is the obvious thing to reach for. `io_i` is
// source-synchronous: the flash launches it off the SCK this very
// block generates from clk_i, so it is phase-related to clk_i and not
// asynchronous to it. A two-flop synchroniser on a read-data lane
// would delay the data two clocks relative to the shift sequencer and
// corrupt every word read. The constraint is on the SCK period, which
// is what the arithmetic above bounds.

`timescale 1ns / 1ps
`default_nettype none

module soc_qspi #(
    // Chip selects. GR801 has two (docs/03 section 2.2) and so does
    // this block; docs/66 section 8 prices the second one.
    parameter integer NCS   = 2,
    // Width of CONF.DIV. 4 bits gives SCK down to clk / 32.
    parameter integer DIV_W = 4,
    // Width of CMD.LEN. 16 is the field's width in the register; the
    // formal job narrows it so a whole data phase fits a bounded model.
    parameter integer LEN_W = 16
) (
    input  wire             clk_i,
    input  wire             rst_ni,

    // ---- APB slave ----
    input  wire             psel_i,
    input  wire             penable_i,
    input  wire [11:0]      paddr_i,
    input  wire             pwrite_i,
    input  wire [31:0]      pwdata_i,
    output reg  [31:0]      prdata_o,
    output wire             pready_o,
    output wire             pslverr_o,

    // ---- the pins ----
    output wire             sck_o,
    output wire [NCS-1:0]   cs_no,        // active low, at most one low
    output wire [3:0]       io_o,
    output wire [3:0]       io_oe_o,
    input  wire [3:0]       io_i,

    // Level: CTRL.IEN and (STAT.DONE or STAT.DR).
    output wire             irq_o
);

  localparam [11:0] REG_CONF = 12'h000;
  localparam [11:0] REG_CTRL = 12'h004;
  localparam [11:0] REG_STAT = 12'h008;
  localparam [11:0] REG_RX   = 12'h00C;
  localparam [11:0] REG_TX   = 12'h010;
  localparam [11:0] REG_CMD  = 12'h014;
  localparam [11:0] REG_ADDR = 12'h018;

  localparam integer CS_W = (NCS > 1) ? $clog2(NCS) : 1;

  assign pready_o  = 1'b1;
  assign pslverr_o = 1'b0;

  wire access = psel_i && penable_i;
  wire wr     = access && pwrite_i;
  wire rd     = access && !pwrite_i;

  // ---- the registers -----------------------------------------------
  reg [DIV_W-1:0] div_q;
  reg [CS_W-1:0]  cs_q;
  reg             ien_q;
  reg [7:0]       op_q;
  reg [3:0]       dummy_q;
  reg             addr_en_q, aquad_q, dquad_q, write_q;
  reg [LEN_W-1:0] len_q;
  reg [23:0]      addr_q;
  reg [31:0]      tx_q, rx_q;
  reg             busy_q, dr_q, done_q, lost_q, tx_full_q;

  // ---- the sequencer ---------------------------------------------------
  localparam [2:0] S_IDLE   = 3'd0;
  localparam [2:0] S_CSSET  = 3'd1;   // CS low, first bit driven, wait
  localparam [2:0] S_SHIFT  = 3'd2;   // clocking
  localparam [2:0] S_WAITRX = 3'd3;   // paused, SCK low, DR set
  localparam [2:0] S_WAITTX = 3'd4;   // paused, SCK low, TXE set
  localparam [2:0] S_CSHOLD = 3'd5;   // last falling edge done, wait
  localparam [2:0] S_GAP    = 3'd6;   // CS high, deselect time

  localparam [1:0] PH_OP    = 2'd0;
  localparam [1:0] PH_ADDR  = 2'd1;
  localparam [1:0] PH_DUMMY = 2'd2;
  localparam [1:0] PH_DATA  = 2'd3;

  reg [2:0]       state;
  reg [1:0]       phase;
  reg             sck_q;
  reg [DIV_W-1:0] div_cnt;
  reg [3:0]       gap_cnt;      // ticks left in the deselect gap
  reg [7:0]       cur;          // the byte being shifted, MSB first
  reg [3:0]       unit_left;    // clocks left in this byte or dummy run
  reg [1:0]       byte_idx;     // byte lane within the word, 0..3
  reg [LEN_W-1:0] bytes_left;   // data bytes still to transfer
  reg [1:0]       abytes_left;  // address bytes still to send
  reg [NCS-1:0]   cs_n_q;
  reg [3:0]       io_o_q, io_oe_q;
  reg             out_phase;    // the current phase drives the lanes
  reg             quad_phase;   // the current phase uses four lanes
  reg             abort_pend;   // RST arrived with SCK high
  integer         i;

  assign sck_o    = sck_q;
  assign cs_no    = cs_n_q;
  assign io_o     = io_o_q;
  assign io_oe_o  = io_oe_q;

  // One tick per half SCK period. The divider is restarted whenever a
  // pause ends or a frame starts, so the first edge after either is a
  // whole half period away.
  wire tick = (div_cnt == {DIV_W{1'b0}});

  // The lane pattern for a single-lane phase: IO0 drives, IO1 is the
  // part's DO, IO2 and IO3 are /WP and /HOLD and are held high.
  localparam [3:0] OE_SINGLE = 4'b1101;

  // Register writes that the sequencer must not see mid-frame.
  wire cmd_wr  = wr && (paddr_i == REG_CMD);
  wire conf_wr = wr && (paddr_i == REG_CONF);
  wire addr_wr = wr && (paddr_i == REG_ADDR);
  wire tx_wr   = wr && (paddr_i == REG_TX);
  wire ctrl_wr = wr && (paddr_i == REG_CTRL);
  wire stat_wr = wr && (paddr_i == REG_STAT);
  wire rx_rd   = rd && (paddr_i == REG_RX);
  wire start   = cmd_wr && !busy_q;
  wire abort   = ctrl_wr && pwdata_i[0];

  // The transaction as written into CMD, used in the start cycle before
  // the registers have captured it.
  wire [LEN_W-1:0] len_w = pwdata_i[16 +: LEN_W];

  // What the next byte of the current output phase is. For the address
  // it is a byte of ADDR, MSB first; for data it is a lane of TX.
  function [7:0] addr_byte;
    input [23:0] a;
    input [1:0]  left;      // bytes left INCLUDING this one: 3, 2, 1
    begin
      case (left)
        2'd3:    addr_byte = a[23:16];
        2'd2:    addr_byte = a[15:8];
        default: addr_byte = a[7:0];
      endcase
    end
  endfunction

  function [7:0] lane_byte;
    input [31:0] w;
    input [1:0]  idx;
    begin
      case (idx)
        2'd0:    lane_byte = w[7:0];
        2'd1:    lane_byte = w[15:8];
        2'd2:    lane_byte = w[23:16];
        default: lane_byte = w[31:24];
      endcase
    end
  endfunction

  // The drive pattern for a byte's first unit -- its high nibble on four
  // lanes, or its MSB on IO0 with IO2 and IO3 high -- given the lanes.
  // The low nibble is deliberately not read: it is the second unit.
  /* verilator lint_off UNUSEDSIGNAL */
  function [3:0] first_unit;
    input [7:0] b;
    input       quad;
    begin
      first_unit = quad ? b[7:4] : {2'b11, 1'b0, b[7]};
    end
  endfunction
  /* verilator lint_on UNUSEDSIGNAL */

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      div_q <= {DIV_W{1'b0}}; cs_q <= {CS_W{1'b0}}; ien_q <= 1'b0;
      op_q <= 8'h0; dummy_q <= 4'h0;
      addr_en_q <= 1'b0; aquad_q <= 1'b0; dquad_q <= 1'b0; write_q <= 1'b0;
      len_q <= {LEN_W{1'b0}}; addr_q <= 24'h0;
      tx_q <= 32'h0; rx_q <= 32'h0;
      busy_q <= 1'b0; dr_q <= 1'b0; done_q <= 1'b0; lost_q <= 1'b0;
      tx_full_q <= 1'b0;
      state <= S_IDLE; phase <= PH_OP; sck_q <= 1'b0;
      div_cnt <= {DIV_W{1'b0}}; gap_cnt <= 4'h0;
      cur <= 8'h0; unit_left <= 4'h0; byte_idx <= 2'd0;
      bytes_left <= {LEN_W{1'b0}}; abytes_left <= 2'd0;
      cs_n_q <= {NCS{1'b1}}; io_o_q <= 4'hF; io_oe_q <= 4'b0000;
      out_phase <= 1'b0; quad_phase <= 1'b0; abort_pend <= 1'b0;
    end else begin
      // ---- register writes that are always accepted ----
      if (ctrl_wr) ien_q <= pwdata_i[1];
      if (stat_wr) begin
        if (pwdata_i[2]) done_q <= 1'b0;
        if (pwdata_i[3]) lost_q <= 1'b0;
      end
      if (tx_wr) begin
        tx_q      <= pwdata_i;
        tx_full_q <= 1'b1;
      end
      if (rx_rd) dr_q <= 1'b0;

      // ---- writes the sequencer must not see mid-frame ----
      if (busy_q && (cmd_wr || conf_wr || addr_wr)) lost_q <= 1'b1;
      if (!busy_q) begin
        if (conf_wr) begin
          div_q <= pwdata_i[DIV_W-1:0];
          cs_q  <= pwdata_i[8 +: CS_W];
        end
        if (addr_wr) addr_q <= pwdata_i[23:0];
        if (cmd_wr) begin
          op_q      <= pwdata_i[7:0];
          dummy_q   <= pwdata_i[11:8];
          addr_en_q <= pwdata_i[12];
          aquad_q   <= pwdata_i[13];
          dquad_q   <= pwdata_i[14];
          write_q   <= pwdata_i[15];
          len_q     <= len_w;
        end
      end

      // ---- the divider ----
      if (tick) div_cnt <= div_q;
      else      div_cnt <= div_cnt - 1'b1;

      // ---- the sequencer ----
      case (state)
        S_IDLE: begin
          sck_q  <= 1'b0;
          cs_n_q <= {NCS{1'b1}};
          if (start) begin
            busy_q     <= 1'b1;
            done_q     <= 1'b0;
            for (i = 0; i < NCS; i = i + 1)
              cs_n_q[i] <= !(cs_q == i[CS_W-1:0]);
            phase      <= PH_OP;
            cur        <= pwdata_i[7:0];
            unit_left  <= 4'd8;
            out_phase  <= 1'b1;
            quad_phase <= 1'b0;
            io_o_q     <= first_unit(pwdata_i[7:0], 1'b0);
            io_oe_q    <= OE_SINGLE;
            bytes_left <= len_w;
            abytes_left <= 2'd3;
            byte_idx   <= 2'd0;
            div_cnt    <= div_q;
            state      <= S_CSSET;
          end
        end

        S_CSSET: begin
          // CS is low and the first opcode bit is on IO0; the first
          // rising edge comes one half period after the fall.
          if (tick) begin
            sck_q <= 1'b1;
            state <= S_SHIFT;
          end
        end

        S_SHIFT: begin
          if (tick && sck_q && abort_pend) begin
            // ---- the falling edge an abort waited for ----
            abort_pend <= 1'b0;
            sck_q      <= 1'b0;
            io_oe_q    <= 4'b0000;
            io_o_q     <= 4'hF;
            state      <= S_CSHOLD;
          end else if (tick) begin
            if (!sck_q) begin
              // ---- rising edge: the flash samples, and so do we ----
              sck_q <= 1'b1;
              if (!out_phase && phase == PH_DATA)
                cur <= quad_phase ? {cur[3:0], io_i} : {cur[6:0], io_i[1]};
            end else begin
              // ---- falling edge: this unit is over; drive the next ----
              sck_q <= 1'b0;
              if (unit_left != 4'd1) begin
                // more units of the same byte or dummy run
                unit_left <= unit_left - 1'b1;
                if (out_phase) begin
                  cur    <= quad_phase ? {cur[3:0], 4'h0} : {cur[6:0], 1'b0};
                  io_o_q <= quad_phase ? cur[3:0]
                                       : {2'b11, 1'b0, cur[6]};
                end
                if (phase == PH_DUMMY && aquad_q
                    && unit_left == dummy_q - 4'd1) begin
                  // the second mode clock is over: release the lanes
                  // for the remaining dummy clocks, or hold the
                  // single-lane pattern if the data phase is not quad
                  io_oe_q <= dquad_q ? 4'b0000 : OE_SINGLE;
                  io_o_q  <= 4'hF;
                end
              end else begin
                // ---- the byte (or dummy run) is complete ----
                if (phase == PH_DATA && !out_phase) begin
                  // store the byte; DR when the word is full or LEN is
                  case (byte_idx)
                    2'd0: rx_q <= {24'h0, cur};
                    2'd1: rx_q[15:8]  <= cur;
                    2'd2: rx_q[23:16] <= cur;
                    default: rx_q[31:24] <= cur;
                  endcase
                end
                if (phase == PH_DATA) begin
                  bytes_left <= bytes_left - 1'b1;
                  byte_idx   <= byte_idx + 1'b1;
                  if (bytes_left == {{(LEN_W-1){1'b0}}, 1'b1}) begin
                    // the last byte of the frame; the lanes keep their
                    // pattern until CS rises
                    if (!out_phase) dr_q <= 1'b1;
                    state   <= S_CSHOLD;
                  end else if (byte_idx == 2'd3) begin
                    // a word boundary with more to come
                    if (!out_phase) begin
                      dr_q  <= 1'b1;
                      state <= S_WAITRX;
                    end else if (tx_full_q) begin
                      tx_full_q <= 1'b0;
                      cur       <= lane_byte(tx_q, 2'd0);
                      io_o_q    <= first_unit(lane_byte(tx_q, 2'd0), dquad_q);
                      unit_left <= dquad_q ? 4'd2 : 4'd8;
                    end else begin
                      state <= S_WAITTX;
                    end
                  end else begin
                    // the next byte of the same word
                    unit_left <= quad_phase ? 4'd2 : 4'd8;
                    if (out_phase) begin
                      cur    <= lane_byte(tx_q, byte_idx + 1'b1);
                      io_o_q <= first_unit(lane_byte(tx_q, byte_idx + 1'b1),
                                           dquad_q);
                    end
                  end
                end else if (phase == PH_ADDR && abytes_left != 2'd1) begin
                  abytes_left <= abytes_left - 1'b1;
                  cur        <= addr_byte(addr_q, abytes_left - 1'b1);
                  io_o_q     <= first_unit(addr_byte(addr_q, abytes_left - 1'b1),
                                           aquad_q);
                  unit_left  <= aquad_q ? 4'd2 : 4'd8;
                end else begin
                  // ---- advance to the next phase that exists ----
                  if (phase == PH_OP && addr_en_q) begin
                    phase      <= PH_ADDR;
                    quad_phase <= aquad_q;
                    cur        <= addr_q[23:16];
                    io_o_q     <= first_unit(addr_q[23:16], aquad_q);
                    io_oe_q    <= aquad_q ? 4'b1111 : OE_SINGLE;
                    unit_left  <= aquad_q ? 4'd2 : 4'd8;
                  end else if (phase != PH_DUMMY && dummy_q != 4'd0) begin
                    phase      <= PH_DUMMY;
                    out_phase  <= 1'b0;
                    unit_left  <= dummy_q;
                    // the mode byte on a quad address, else nothing
                    // meaningful: released for a quad data phase, the
                    // single-lane pattern otherwise
                    if (aquad_q) begin
                      io_oe_q <= 4'b1111;
                      io_o_q  <= 4'hF;
                    end else begin
                      io_oe_q <= dquad_q ? 4'b0000 : OE_SINGLE;
                      io_o_q  <= 4'hF;
                    end
                  end else if (len_q != {LEN_W{1'b0}}) begin
                    phase      <= PH_DATA;
                    quad_phase <= dquad_q;
                    out_phase  <= write_q;
                    byte_idx   <= 2'd0;
                    unit_left  <= dquad_q ? 4'd2 : 4'd8;
                    if (write_q) begin
                      io_oe_q <= dquad_q ? 4'b1111 : OE_SINGLE;
                      if (tx_full_q) begin
                        tx_full_q <= 1'b0;
                        cur       <= lane_byte(tx_q, 2'd0);
                        io_o_q    <= first_unit(lane_byte(tx_q, 2'd0), dquad_q);
                      end else begin
                        // nothing to drive yet: IO2 and IO3 high (they
                        // may just have carried address nibbles)
                        io_o_q <= 4'hF;
                        state  <= S_WAITTX;
                      end
                    end else begin
                      io_oe_q <= dquad_q ? 4'b0000 : OE_SINGLE;
                      io_o_q  <= 4'hF;
                      cur     <= 8'h0;
                    end
                  end else begin
                    state   <= S_CSHOLD;
                  end
                end
              end
            end
          end
        end

        S_WAITRX: begin
          // SCK low, CS low, DR set. A read of RX resumes.
          if (rx_rd) begin
            byte_idx  <= 2'd0;
            unit_left <= quad_phase ? 4'd2 : 4'd8;
            div_cnt   <= div_q;
            state     <= S_SHIFT;
          end
        end

        S_WAITTX: begin
          // SCK low, CS low, TXE set. A write of TX resumes with the
          // written word's first byte on the lanes. A word that landed
          // in TX on the very clock the pause was entered -- the
          // sequencer saw tx_full_q clear while the write set it --
          // resumes on the next clock from the register.
          if (tx_wr || tx_full_q) begin
            tx_full_q <= 1'b0;
            byte_idx  <= 2'd0;
            cur       <= lane_byte(tx_wr ? pwdata_i : tx_q, 2'd0);
            io_o_q    <= first_unit(lane_byte(tx_wr ? pwdata_i : tx_q, 2'd0),
                                    quad_phase);
            unit_left <= quad_phase ? 4'd2 : 4'd8;
            div_cnt   <= div_q;
            state     <= S_SHIFT;
          end
        end

        S_CSHOLD: begin
          // One half period with SCK low and the lanes still in their
          // last pattern (IO2 and IO3 high in a single-lane frame, so
          // /HOLD is never released while the part is selected); then
          // CS rises and every lane is released together.
          if (tick) begin
            cs_n_q  <= {NCS{1'b1}};
            io_oe_q <= 4'b0000;
            io_o_q  <= 4'hF;
            gap_cnt <= 4'd8;
            state   <= S_GAP;
          end
        end

        S_GAP: begin
          // DONE is set when the gap ends and not when CS rises, so
          // that DONE also means "a CMD write will be accepted": a
          // driver that polls DONE and then writes CMD cannot lose it.
          if (tick) begin
            gap_cnt <= gap_cnt - 1'b1;
            if (gap_cnt == 4'd1) begin
              busy_q <= 1'b0;
              done_q <= 1'b1;
              state  <= S_IDLE;
            end
          end
        end

        default: state <= S_IDLE;
      endcase

      // ---- abort ----
      // With SCK low: releases the lanes at once and goes through the
      // chip-select hold and the deselect gap like any frame, so CS
      // rises with SCK low (mode 0) and the next frame is a legal
      // distance from this one. With SCK high: the same, from the
      // falling edge the divider is already counting toward, so no
      // SCK level is ever shorter than a half period. DR, TXE and the
      // TX word are cleared at once either way; DONE is set when the
      // gap ends, as after any frame.
      // An abort in the hold or the gap has nothing left to cut short
      // and is ignored, so the gap is never restarted or extended.
      if (abort && state != S_IDLE && state != S_CSHOLD && state != S_GAP) begin
        dr_q      <= 1'b0;
        tx_full_q <= 1'b0;
        done_q    <= 1'b0;
        if (sck_q && !tick) begin
          // SCK is high and stays high this clock: wait for its edge
          abort_pend <= 1'b1;
        end else begin
          // SCK is low, or falls on this very clock
          sck_q     <= 1'b0;
          state     <= S_CSHOLD;
          io_oe_q   <= 4'b0000;
          io_o_q    <= 4'hF;
          div_cnt   <= div_q;
        end
      end
    end
  end

  wire txe = busy_q && (state == S_WAITTX);

  assign irq_o = ien_q && (done_q || dr_q);

  // ---- reads ----------------------------------------------------------
  always @(*) begin
    prdata_o = 32'h0;
    case (paddr_i)
      REG_CONF: begin
        prdata_o[DIV_W-1:0]  = div_q;
        prdata_o[8 +: CS_W]  = cs_q;
      end
      REG_CTRL: prdata_o[1] = ien_q;
      REG_STAT: prdata_o[4:0] = {txe, lost_q, done_q, dr_q, busy_q};
      REG_RX:   prdata_o = rx_q;
      REG_CMD: begin
        prdata_o[7:0]   = op_q;
        prdata_o[11:8]  = dummy_q;
        prdata_o[12]    = addr_en_q;
        prdata_o[13]    = aquad_q;
        prdata_o[14]    = dquad_q;
        prdata_o[15]    = write_q;
        prdata_o[16 +: LEN_W] = len_q;
      end
      REG_ADDR: prdata_o[23:0] = addr_q;
      default:  prdata_o = 32'h0;
    endcase
  end

  // Write lanes that reach no register (the reserved bits of every
  // register, and CMD.LEN's upper bits when LEN_W is narrowed), named so
  // they are a decision rather than an oversight.
  wire _unused = &{1'b0, pwdata_i, 1'b0};

`ifdef FORMAL
`include "soc_qspi_props.v"
`endif

endmodule

`default_nettype wire
