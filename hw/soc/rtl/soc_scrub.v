// SCRUB: the memory codec's counters, the scrubber's control, and the
// address of the last word that could not be repaired.
//
// =====================================================================
// WHY THIS BLOCK EXISTS, AND WHY IT IS NOT FOUR MORE BITS IN BUSSTAT
// =====================================================================
//
// docs/67 puts a SECDED code over every row of the RAM and the boot
// ROM and a scrubber under both (hw/soc/rtl/soc_mem_ecc.v). A
// correction the operator cannot see is docs/43 section 6.5's
// "indistinguishable from no upset at all", which soc_busstat.v exists
// to end -- and soc_busstat.v is FULL: docs/58 took the last sticky bit
// below its interrupt bit, and that file's S_MTECC comment says what a
// ninth source costs. This block is where the memory's six sources
// live instead, and the frozen map has had the slot ready since
// docs/39:
//
//     0xFF916000  SCRUB  irq 23  line 11  reserved
//     "Memory scrubber control, MEMSCRUB-like"
//
// GR740's MEMSCRUB is the shape: a scrubber that walks a memory and a
// register block that reports what it found. Nothing about the
// address, the slot, the interrupt number or the line is new here.
//
// =====================================================================
// THE SIX COUNTERS, AND WHAT EACH ONE IS A COUNT OF
// =====================================================================
//
// Two memories, three events each, and the three are DIFFERENT
// quantities that soc_busstat.v's header already argued must not be
// folded into one:
//
//   CNT_RAMSEC   Rows the scrubber REPAIRED in the RAM. Counted on the
//   CNT_ROMSEC   write-back, so an upset that nothing overwrote first
//                is counted EXACTLY ONCE, however many reads returned
//                it corrected before the scrubber reached it. THIS IS
//                THE UPSET-RATE COUNTER of each memory, the way
//                BUSSTAT.CNT_RFSEC is the register file's. A row in
//                which several byte lanes were hit is one event.
//
//   CNT_RAMRD    READS that returned a corrected word. Not a count of
//   CNT_ROMRD    upsets: one corrupt word read in a loop raises it on
//                every iteration until the scrubber gets there. It is
//                carried because RD >> SEC is the observable signature
//                of the scrub interval being too long for the rate,
//                which is what SCRUBCTL.IVL exists to change.
//
//   CNT_RAMDED   Syndromes the codec could not correct, on a read or on
//   CNT_ROMDED   a scrub. A read that raised one was answered with a
//                bus error and the core took an access fault; a scrub
//                that raised one left the row as it was, so the next
//                read of it will trap. RAMADDR / ROMADDR hold the byte
//                offset, within the region, of the LAST such row: the
//                address a handler needs and the one thing a counter
//                cannot carry.
//
// All six SATURATE, for pilot_top.v's and soc_busstat.v's reason: a
// counter that wraps is indistinguishable from one that barely moved.
//
// =====================================================================
// THE CONTROL REGISTER
// =====================================================================
//
//   SCRUBCTL[0]      RAM_EN   the RAM scrubber walks
//   SCRUBCTL[1]      ROM_EN   the ROM scrubber walks
//   SCRUBCTL[31:16]  IVL      idle cycles between scrub reads
//
// IT SHIPS ENABLED. docs/44 section 11's rule is that a mechanism that
// ships disabled and has never caught anything is a liability in an
// area budget, so both scrubbers walk from reset and software may slow
// or stop them, not the reverse. IVL_RST is the interval at reset and
// soc_top.v sets it; at IVL = 0 a scrubber reads on every idle cycle,
// which is the setting a campaign uses and not the one a part ships
// with, because every scrub read is a macro access and docs/57
// measured what those cost in energy.
//
// SCRUBCTL is in the SYSTEM reset domain: a watchdog stage-2 reset puts
// the scrubbers back to their defaults, which is the safe direction.
// The RECORD -- the counters, the stickies and the two addresses -- is
// in the POWER-ON domain, and the interrupt enable is in the system
// domain, for exactly soc_busstat.v's reasons: the reading that
// matters is the one taken after the reset it explains, and a fault
// line that survived the reset it caused must not re-enter a handler
// the fresh boot has not installed (docs/40 section 7.2).
//
// CLR is write-only and clears counters and stickies by bit; an event
// in the cycle of its own clear wins. Both are soc_busstat.v's
// conventions and the reasons are in that file.
//
// =====================================================================
// BUS
// =====================================================================
//
// AMBA 3 APB slave, the conventions soc_uart.v and soc_busstat.v use:
// PREADY tied high, PSLVERR tied low, an offset inside the slot that
// names no register reads zero and a write to it does nothing.

`timescale 1ns / 1ps
`default_nettype none

module soc_scrub #(
    // Counter width. 16 bits saturating at 65,535, BUSSTAT's CNT_W.
    parameter integer CNT_W   = 16,
    // The scrub interval at reset.
    parameter [15:0]  IVL_RST = 16'd255
) (
    input  wire        clk_i,
    // System reset: SCRUBCTL and the interrupt enable.
    input  wire        rst_ni,
    // Power-on reset: the record.
    input  wire        rst_por_ni,

    // ---- APB slave ----
    input  wire        psel_i,
    input  wire        penable_i,
    input  wire [11:0] paddr_i,      // offset within the 4 KiB slot
    input  wire        pwrite_i,
    input  wire [31:0] pwdata_i,
    output reg  [31:0] prdata_o,
    output wire        pready_o,
    output wire        pslverr_o,

    // ---- the memories' reports, one cycle per event at the source ----
    input  wire        ram_sec_i,
    input  wire        ram_rd_i,
    input  wire        ram_ded_i,
    input  wire [31:0] ram_addr_i,
    input  wire        rom_sec_i,
    input  wire        rom_rd_i,
    input  wire        rom_ded_i,
    input  wire [31:0] rom_addr_i,

    // ---- the scrubbers' control ----
    output wire        ram_en_o,
    output wire        rom_en_o,
    output wire [15:0] ivl_o,

    // Level, to fast interrupt line 11 (IRQ 23 in the frozen map).
    output wire        irq_o
);

  localparam [11:0] REG_STATUS  = 12'h000;
  localparam [11:0] REG_IRQEN   = 12'h004;
  localparam [11:0] REG_RAMSEC  = 12'h008;
  localparam [11:0] REG_RAMRD   = 12'h00C;
  localparam [11:0] REG_RAMDED  = 12'h010;
  localparam [11:0] REG_ROMSEC  = 12'h014;
  localparam [11:0] REG_ROMRD   = 12'h018;
  localparam [11:0] REG_ROMDED  = 12'h01C;
  localparam [11:0] REG_CLR     = 12'h020;
  localparam [11:0] REG_CTRL    = 12'h024;
  localparam [11:0] REG_RAMADDR = 12'h028;
  localparam [11:0] REG_ROMADDR = 12'h02C;

  // Bit index of each source, shared by STATUS, IRQEN and CLR.
  // hw/soc/tb/sw/soc_scrub.h carries the same names.
  localparam integer S_RAMSEC = 0;
  localparam integer S_RAMRD  = 1;
  localparam integer S_RAMDED = 2;
  localparam integer S_ROMSEC = 3;
  localparam integer S_ROMRD  = 4;
  localparam integer S_ROMDED = 5;
  localparam integer NSRC     = 6;

  localparam [CNT_W-1:0] CNT_MAX = {CNT_W{1'b1}};

  assign pready_o  = 1'b1;
  assign pslverr_o = 1'b0;

  wire access = psel_i && penable_i;
  wire wr     = access && pwrite_i;

  // ---- the events, one bit per source ---------------------------------
  wire [NSRC-1:0] ev;
  assign ev[S_RAMSEC] = ram_sec_i;
  assign ev[S_RAMRD]  = ram_rd_i;
  assign ev[S_RAMDED] = ram_ded_i;
  assign ev[S_ROMSEC] = rom_sec_i;
  assign ev[S_ROMRD]  = rom_rd_i;
  assign ev[S_ROMDED] = rom_ded_i;

  // ---- the clear strobes ---------------------------------------------
  wire [NSRC-1:0] clr;
  assign clr = (wr && (paddr_i == REG_CLR)) ? pwdata_i[NSRC-1:0]
                                            : {NSRC{1'b0}};

  // ---- the record: one counter and one sticky per source, POR domain
  //
  // The event is a BRANCH CONDITION and not an addend, for the reason
  // soc_busstat.v records at length: an X on an event line in the first
  // cycles after reset must not poison a counter for the run.
  wire [CNT_W-1:0] cnt    [0:NSRC-1];
  wire [NSRC-1:0]  sticky;

  genvar gi;
  generate
    for (gi = 0; gi < NSRC; gi = gi + 1) begin : g_src
      reg [CNT_W-1:0] cnt_q;
      reg             sticky_q;

      always @(posedge clk_i or negedge rst_por_ni) begin
        if (!rst_por_ni) begin
          cnt_q    <= {CNT_W{1'b0}};
          sticky_q <= 1'b0;
        end else if (clr[gi]) begin
          if (ev[gi]) begin
            cnt_q    <= {{(CNT_W-1){1'b0}}, 1'b1};
            sticky_q <= 1'b1;
          end else begin
            cnt_q    <= {CNT_W{1'b0}};
            sticky_q <= 1'b0;
          end
        end else if (ev[gi]) begin
          sticky_q <= 1'b1;
          if (~&cnt_q) cnt_q <= cnt_q + {{(CNT_W-1){1'b0}}, 1'b1};
        end
      end

      assign cnt[gi]    = cnt_q;
      assign sticky[gi] = sticky_q;
    end
  endgenerate

  // The address of the last uncorrectable row, per memory, POR domain.
  // Latched on the event and never cleared: the most recent one is the
  // one a handler wants, and a zero would look like a valid address.
  reg [31:0] ram_addr_q, rom_addr_q;
  always @(posedge clk_i or negedge rst_por_ni) begin
    if (!rst_por_ni) begin
      ram_addr_q <= 32'h0;
      rom_addr_q <= 32'h0;
    end else begin
      if (ram_ded_i) ram_addr_q <= ram_addr_i;
      if (rom_ded_i) rom_addr_q <= rom_addr_i;
    end
  end

  // ---- the control and the interrupt enable, system domain -----------
  reg            ram_en_q, rom_en_q;
  reg [15:0]     ivl_q;
  reg [NSRC-1:0] irqen;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      ram_en_q <= 1'b1;               // ships enabled; see the header
      rom_en_q <= 1'b1;
      ivl_q    <= IVL_RST;
      irqen    <= {NSRC{1'b0}};       // nothing is enabled out of reset
    end else begin
      if (wr && (paddr_i == REG_CTRL)) begin
        ram_en_q <= pwdata_i[0];
        rom_en_q <= pwdata_i[1];
        ivl_q    <= pwdata_i[31:16];
      end
      if (wr && (paddr_i == REG_IRQEN))
        irqen <= pwdata_i[NSRC-1:0];
    end
  end

  assign ram_en_o = ram_en_q;
  assign rom_en_o = rom_en_q;
  assign ivl_o    = ivl_q;

  // Level, from the STICKY and not from the event, soc_busstat.v's
  // acknowledge discipline: the handler clears the sticky through CLR
  // and that is what deasserts the line.
  assign irq_o = |(sticky & irqen);

  // ---- reads -----------------------------------------------------------
  always @(*) begin
    case (paddr_i)
      // Bit 8 is the interrupt, where soc_busstat.v keeps it, so a
      // driver that reads both blocks reads them the same way.
      REG_STATUS:  prdata_o = {23'h0, irq_o, 2'b00, sticky};
      REG_IRQEN:   prdata_o = {{(32-NSRC){1'b0}}, irqen};
      REG_RAMSEC:  prdata_o = {{(32-CNT_W){1'b0}}, cnt[S_RAMSEC]};
      REG_RAMRD:   prdata_o = {{(32-CNT_W){1'b0}}, cnt[S_RAMRD]};
      REG_RAMDED:  prdata_o = {{(32-CNT_W){1'b0}}, cnt[S_RAMDED]};
      REG_ROMSEC:  prdata_o = {{(32-CNT_W){1'b0}}, cnt[S_ROMSEC]};
      REG_ROMRD:   prdata_o = {{(32-CNT_W){1'b0}}, cnt[S_ROMRD]};
      REG_ROMDED:  prdata_o = {{(32-CNT_W){1'b0}}, cnt[S_ROMDED]};
      REG_CTRL:    prdata_o = {ivl_q, 14'h0, rom_en_q, ram_en_q};
      REG_RAMADDR: prdata_o = ram_addr_q;
      REG_ROMADDR: prdata_o = rom_addr_q;
      // CLR is write-only and reads zero, for soc_busstat.v's reason.
      default:     prdata_o = 32'h0;
    endcase
  end

`ifdef FORMAL
`include "soc_scrub_props.v"
`endif

endmodule

`default_nettype wire
