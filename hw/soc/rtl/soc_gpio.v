// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// GPIO: a GRGPIO-shaped general purpose I/O port, 16 pins, on APB.
//
// =====================================================================
// WHY THIS BLOCK EXISTS, AND WHY IT IS FIRST
// =====================================================================
//
// docs/60-soc-datasheet.md section 4.1 says what this SoC has been
// since docs/39 froze the map: "no SpaceWire, no CAN, no SPI, no I2C,
// no QSPI and no GPIO, in the sense that matters: there is no RTL for
// any of them." Eleven of sixteen peripheral slots are reserved
// addresses that reach the error slave.
//
// This is the first of them to be filled, and it is filled first for a
// reason that is not "it is the easiest". docs/03-cpu-and-ip-survey.md
// section 2.2 selected the interface IP, and every selected core is
// native to a bus this SoC does not have -- Wishbone, TileLink,
// AXI4-Lite -- so every one of them needs a bridge to the AMBA 3 APB
// that soc_apb_bridge.v speaks, and the bridges are where the defects
// will be. Before any of those bridges is written, the path a
// peripheral takes to become real -- a slot in regmap/memmap.yaml moved
// from reserved to implemented, a device-table record, a fast interrupt
// line, a decode in soc_top.v, a driver in the bring-up program, a
// cocotb suite against the specification, a proof -- should be walked
// once on a block with NO third-party dependency, so that a defect
// found on the second block is a defect in the bridge and not in the
// path. This block is that walk. It is this project's own RTL, written
// against grip.pdf chapter 62 (GRGPIO, tables 923 to 937) and against
// nothing else.
//
// It also unlocks something concrete: a pin the bring-up program can
// toggle is the cheapest observable a board has, and until now the SoC
// had exactly one functional output, the UART's transmit line.
//
// =====================================================================
// THE REGISTER MAP, AND WHAT IS DELIBERATELY NOT IN IT
// =====================================================================
//
// The offsets are grip.pdf table 923. docs/08 section 3 row 8's rule --
// "adopt the GRLIB register maps verbatim where it costs nothing" --
// is honoured, and the places where it is not are listed here rather
// than discovered by a driver.
//
//   0x00  DATA       r   the SYNCHRONISED input value of every pin
//   0x04  OUTPUT     rw  the value driven on a pin whose DIR bit is 1
//   0x08  DIRECTION  rw  1 = output buffer enabled, 0 = input
//   0x0C  IMASK      rw  1 = the line may raise the interrupt
//   0x10  IPOL       rw  level: 0 = active low, 1 = active high
//                        edge:  0 = falling,    1 = rising
//   0x14  IEDGE      rw  0 = level sensitive, 1 = edge triggered
//   0x18  BYPASS     r   reads zero: no pin has an alternate function
//   0x1C  CAP        r   PU = 0, IER = 0, IFL = 1, IRQGEN = 1,
//                        NLINES = NBITS - 1
//   0x40  IAVAIL     r   which lines can interrupt: all of them
//   0x44  IFLAG      wc  which lines HAVE interrupted; write 1 to clear
//   0x54  OUTPUT     w   logical OR:  OUTPUT    <= OUTPUT    | wdata
//   0x58  DIRECTION  w   logical OR:  DIRECTION <= DIRECTION | wdata
//   0x5C  IMASK      w   logical OR:  IMASK     <= IMASK     | wdata
//   0x64  OUTPUT     w   logical AND
//   0x68  DIRECTION  w   logical AND
//   0x6C  IMASK      w   logical AND
//   0x74  OUTPUT     w   logical XOR
//   0x78  DIRECTION  w   logical XOR
//   0x7C  IMASK      w   logical XOR
//
// Not implemented, and each reads zero and ignores writes, which is
// GRLIB's documented behaviour for a register a configuration leaves
// out:
//
//   * BYPASS (0x18) and the alternate-function path of grip.pdf figure
//     150. No pin here is shared with anything, so there is nothing to
//     bypass to. CAP does not have a field for this; the register
//     reads zero, which in GRLIB means "normal output" on every pin.
//   * The interrupt map registers (0x20-0x3C). IRQGEN = 1 in CAP says
//     every line drives the ONE interrupt line the plug-and-play record
//     names, and grip.pdf 62.3.8 says no map registers exist in that
//     configuration. The frozen map gives this slot exactly one source
//     number (4) and one fast line (2); separate per-line interrupts
//     would consume sixteen source numbers the map has not reserved.
//     This is the same decision soc_gptimer.v takes with SI = 0, for
//     the same reason.
//   * The input-enable register (0x48) and its logical-op aliases
//     (0x50, 0x60, 0x70). IER = 0 in CAP. Every input is always
//     visible in DATA.
//   * The pulse register (0x4C). PU = 0 in CAP. There is no internal
//     signal to pulse on.
//
// One divergence that is not an omission: IPOL and IEDGE are RESET to
// zero here, where grip.pdf tables 928 and 929 mark them "NR" -- no
// reset value. A register that comes out of reset holding whatever the
// flip-flops happened to power up as is a register a fault-injection
// campaign cannot reason about, and this SoC's whole argument is that
// its state is accounted for. The cost is nothing: with IMASK reset to
// zero, the reset values of IPOL and IEDGE cannot be observed until
// software writes IMASK, and software that writes IMASK without having
// written IPOL and IEDGE first is relying on a value GRLIB does not
// define either.
//
// =====================================================================
// THE INPUT PATH, AND WHY DATA DOES NOT READ THE OUTPUT REGISTER
// =====================================================================
//
// grip.pdf 62.2: "The input from each buffer is synchronized by two
// flip-flops in series to remove potential meta-stability. The
// synchronized values can be read-out from the I/O port data register."
// So DATA is gpio_i, two clocks late, and it is NOTHING ELSE. In
// particular a pin whose DIR bit is 1 reads back through gpio_i and
// not through the OUTPUT register.
//
// That matters because this SoC has no pad ring. gpio_o and gpio_oe_o
// leave soc_top.v as separate wires and gpio_i enters it as a third,
// and whatever is outside -- a pad, a board, or hw/soc/tb/tb_soc.v's
// model of one -- is what connects them. A block that folded its own
// OUTPUT register into DATA would pass a write-then-read-back test
// with no pin present at all, and would hide exactly the class of
// board fault -- a pad that does not drive, a pin shorted to another --
// that a read-back through the pad is for.
//
// The synchroniser costs two clocks of latency on every input and it
// is applied to every pin, including ones configured as outputs. A
// read of DATA immediately after a write of OUTPUT therefore returns
// the OLD pin value, and the cocotb suite tests that this is so rather
// than papering over it.
//
// =====================================================================
// THE INTERRUPT, AND WHAT KIND OF SIGNAL IT IS
// =====================================================================
//
// grip.pdf 62.2, restated as what the logic does. A line n DETECTS in
// a cycle when IMASK[n] is set and:
//
//   IEDGE[n] = 0   the synchronised input equals IPOL[n]
//   IEDGE[n] = 1   the synchronised input changed this cycle AND now
//                  equals IPOL[n]  (IPOL = 1 rising, 0 falling)
//
// A detection sets IFLAG[n]. IFLAG is write-one-to-clear, and a
// detection in the cycle of its own clear WINS: the flag stays set and
// the interrupt is not lost. That is the same rule soc_busstat.v applies
// to its counters and for the same reason -- the cycle software
// acknowledges is not a rare cycle.
//
// irq_o is a LEVEL: the OR of IFLAG AND IMASK. It is driven from the
// flag and not from the detection, because a one-cycle pulse on an
// Ibex fast line is a pulse the core can be inside a trap for and never
// see; and it is gated by IMASK on the way out as well as on the way
// in, so that masking a line silences it immediately rather than after
// the next acknowledge. The handler clears IFLAG to drop the line --
// which for a LEVEL-sensitive line whose input is still active sets it
// again on the next cycle, exactly as GRLIB's does, so a level handler
// must remove the cause or mask the line. The bring-up program uses an
// edge for that reason and says so.
//
// The masking on the way in is GRLIB's: grip.pdf 62.2, "To enable an
// interrupt, the corresponding bit in the interrupt mask register must
// be set." A line that is masked does not set its flag, so unmasking a
// line later does not deliver an interrupt from before it was unmasked.
//
// =====================================================================
// BUS
// =====================================================================
//
// AMBA 3 APB slave, the conventions soc_uart.v, soc_gptimer.v and
// soc_busstat.v already use: PREADY tied high, PSLVERR tied low, an
// offset inside the slot that names no register reads zero and a write
// to it does nothing. PSTRB is not a port and byte lanes are not
// honoured: every register here is written whole, which is what
// soc_top.v's note on pstrb records for every peripheral in this SoC.
// Bits above NBITS read zero and are not stored.
//
// =====================================================================
// WHAT IS NOT HERE
// =====================================================================
//
//   * No hardening. No parity, no replication, no scrub. An upset in
//     DIRECTION turns an input into an output, which on a real board is
//     a contention fault; an upset in OUTPUT changes a pin. Neither is
//     silent -- both are visible on the pad -- but nothing here reports
//     either. The hardening architecture owns that decision.
//   * No pad ring, no pull-ups, no drive-strength control, no
//     open-drain mode. gpio_oe_o is a wire that means "drive"; what a
//     pad does with it is a pad's business and there is no pad.
//   * No debounce and no glitch filter. Two flip-flops of synchroniser
//     is what GRLIB specifies and what is here.

`timescale 1ns / 1ps
`default_nettype none

module soc_gpio #(
    // Port width, 2..32 in GRLIB. 16 is what the frozen map's slot
    // description and docs/01 section 4 say.
    parameter integer NBITS = 16
) (
    input  wire             clk_i,
    input  wire             rst_ni,

    // ---- APB slave ----
    input  wire             psel_i,
    input  wire             penable_i,
    input  wire [11:0]      paddr_i,      // offset within the 4 KiB slot
    input  wire             pwrite_i,
    input  wire [31:0]      pwdata_i,
    output reg  [31:0]      prdata_o,
    output wire             pready_o,
    output wire             pslverr_o,

    // ---- the pins, as three wires because there is no pad ----
    input  wire [NBITS-1:0] gpio_i,       // what the pad sees
    output wire [NBITS-1:0] gpio_o,       // what the pad should drive
    output wire [NBITS-1:0] gpio_oe_o,    // whether the pad should drive

    // Level, to the fast interrupt line the generated map assigns.
    output wire             irq_o
);

  // grip.pdf table 923.
  localparam [11:0] REG_DATA    = 12'h000;
  localparam [11:0] REG_OUTPUT  = 12'h004;
  localparam [11:0] REG_DIR     = 12'h008;
  localparam [11:0] REG_IMASK   = 12'h00C;
  localparam [11:0] REG_IPOL    = 12'h010;
  localparam [11:0] REG_IEDGE   = 12'h014;
  localparam [11:0] REG_BYPASS  = 12'h018;
  localparam [11:0] REG_CAP     = 12'h01C;
  localparam [11:0] REG_IAVAIL  = 12'h040;
  localparam [11:0] REG_IFLAG   = 12'h044;
  localparam [11:0] REG_OUTPUT_OR   = 12'h054;
  localparam [11:0] REG_DIR_OR      = 12'h058;
  localparam [11:0] REG_IMASK_OR    = 12'h05C;
  localparam [11:0] REG_OUTPUT_AND  = 12'h064;
  localparam [11:0] REG_DIR_AND     = 12'h068;
  localparam [11:0] REG_IMASK_AND   = 12'h06C;
  localparam [11:0] REG_OUTPUT_XOR  = 12'h074;
  localparam [11:0] REG_DIR_XOR     = 12'h078;
  localparam [11:0] REG_IMASK_XOR   = 12'h07C;

  // grip.pdf table 931. The fields this configuration reports, named
  // so the read multiplexer and the suite cannot disagree about where
  // they are.
  localparam integer CAP_PU     = 18;   // pulse register: no
  localparam integer CAP_IER    = 17;   // input enable register: no
  localparam integer CAP_IFL    = 16;   // interrupt flag register: YES
  localparam integer CAP_IRQGEN = 8;    // [12:8], 1 = one shared line
  localparam [4:0]   CAP_IRQGEN_VAL = 5'd1;
  localparam integer CAP_NLINES_I   = NBITS - 1;
  localparam [4:0]   CAP_NLINES     = CAP_NLINES_I[4:0];

  localparam [NBITS-1:0] ALL_ONES = {NBITS{1'b1}};

  assign pready_o  = 1'b1;
  assign pslverr_o = 1'b0;

  wire access = psel_i && penable_i;
  wire wr     = access && pwrite_i;
  wire [NBITS-1:0] wdata = pwdata_i[NBITS-1:0];

  // The write lanes above NBITS reach no register: every register here
  // is NBITS wide and the reserved field above it is read-only zero
  // (grip.pdf tables 924-929). Named so the unused bits are a decision
  // rather than an oversight, in the shape soc_top.v uses for pstrb.
  generate
    if (NBITS < 32) begin : g_unused_lanes
      wire _unused_pwdata = &{1'b0, pwdata_i[31:NBITS], 1'b0};
    end
  endgenerate

  // ---- the input path: two synchroniser stages and one history stage
  reg [NBITS-1:0] sync1, sync2, prev;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      sync1 <= {NBITS{1'b0}};
      sync2 <= {NBITS{1'b0}};
      prev  <= {NBITS{1'b0}};
    end else begin
      sync1 <= gpio_i;
      sync2 <= sync1;
      prev  <= sync2;
    end
  end

  // ---- the configuration registers ----------------------------------
  reg [NBITS-1:0] out_q, dir_q, imask_q, ipol_q, iedge_q;

  // Each of OUTPUT, DIRECTION and IMASK has four write ports -- plain,
  // OR, AND, XOR -- and one function computes the next value for all
  // three so the four cannot drift apart between registers. Every
  // input is an explicit argument, for the reason docs/40 section 7.3
  // records: a function that reads module scope from a continuous
  // assignment loses its sensitivity, and this one is called from a
  // clocked block only because that is where it is used today.
  function [NBITS-1:0] next_reg;
    input [NBITS-1:0] cur;
    input             hit_plain, hit_or, hit_and, hit_xor;
    input [NBITS-1:0] w;
    begin
      next_reg = cur;
      if (hit_plain) next_reg = w;
      if (hit_or)    next_reg = cur | w;
      if (hit_and)   next_reg = cur & w;
      if (hit_xor)   next_reg = cur ^ w;
    end
  endfunction

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      out_q   <= {NBITS{1'b0}};
      dir_q   <= {NBITS{1'b0}};     // every pin is an input at reset
      imask_q <= {NBITS{1'b0}};     // and none can interrupt
      ipol_q  <= {NBITS{1'b0}};     // GRLIB: NR. Here: zero. Header.
      iedge_q <= {NBITS{1'b0}};     // GRLIB: NR. Here: zero. Header.
    end else if (wr) begin
      out_q   <= next_reg(out_q,
                          paddr_i == REG_OUTPUT, paddr_i == REG_OUTPUT_OR,
                          paddr_i == REG_OUTPUT_AND, paddr_i == REG_OUTPUT_XOR,
                          wdata);
      dir_q   <= next_reg(dir_q,
                          paddr_i == REG_DIR, paddr_i == REG_DIR_OR,
                          paddr_i == REG_DIR_AND, paddr_i == REG_DIR_XOR,
                          wdata);
      imask_q <= next_reg(imask_q,
                          paddr_i == REG_IMASK, paddr_i == REG_IMASK_OR,
                          paddr_i == REG_IMASK_AND, paddr_i == REG_IMASK_XOR,
                          wdata);
      if (paddr_i == REG_IPOL)  ipol_q  <= wdata;
      if (paddr_i == REG_IEDGE) iedge_q <= wdata;
    end
  end

  assign gpio_o    = out_q;
  assign gpio_oe_o = dir_q;

  // ---- interrupt detection, grip.pdf 62.2 ---------------------------
  //
  // Per line: masked in, polarity compared against the synchronised
  // value, and for an edge additionally a change this cycle.
  wire [NBITS-1:0] at_pol  = ~(sync2 ^ ipol_q);         // value == IPOL
  wire [NBITS-1:0] changed = sync2 ^ prev;
  wire [NBITS-1:0] detect  = imask_q & at_pol & (~iedge_q | changed);

  // ---- the flag, write-one-to-clear, detection wins -----------------
  reg [NBITS-1:0] iflag_q;
  wire [NBITS-1:0] iclr = (wr && (paddr_i == REG_IFLAG)) ? wdata
                                                          : {NBITS{1'b0}};
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) iflag_q <= {NBITS{1'b0}};
    else         iflag_q <= (iflag_q & ~iclr) | detect;
  end

  assign irq_o = |(iflag_q & imask_q);

  // ---- reads --------------------------------------------------------
  always @(*) begin
    prdata_o = 32'h0;
    case (paddr_i)
      REG_DATA:   prdata_o[NBITS-1:0] = sync2;
      REG_OUTPUT: prdata_o[NBITS-1:0] = out_q;
      REG_DIR:    prdata_o[NBITS-1:0] = dir_q;
      REG_IMASK:  prdata_o[NBITS-1:0] = imask_q;
      REG_IPOL:   prdata_o[NBITS-1:0] = ipol_q;
      REG_IEDGE:  prdata_o[NBITS-1:0] = iedge_q;
      REG_BYPASS: prdata_o = 32'h0;              // no alternate function
      REG_CAP: begin
        prdata_o[CAP_PU]              = 1'b0;
        prdata_o[CAP_IER]             = 1'b0;
        prdata_o[CAP_IFL]             = 1'b1;
        prdata_o[CAP_IRQGEN+4:CAP_IRQGEN] = CAP_IRQGEN_VAL;
        prdata_o[4:0]                 = CAP_NLINES;
      end
      REG_IAVAIL: prdata_o[NBITS-1:0] = ALL_ONES;
      REG_IFLAG:  prdata_o[NBITS-1:0] = iflag_q;
      // The logical-op aliases are write-only (grip.pdf table 937,
      // access "w*"); the interrupt map, input enable and pulse
      // registers are not implemented. All read zero.
      default:    prdata_o = 32'h0;
    endcase
  end

`ifdef FORMAL
`include "soc_gpio_props.v"
`endif

endmodule

`default_nettype wire
