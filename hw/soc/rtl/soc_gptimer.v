// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// General purpose timer unit, and the shell the watchdog lives in.
//
// Register map mirrored from GRLIB's GPTIMER (grip.pdf table 463, quoted
// in docs/08-gr801-datasheet-notes.md section 2.5 and adopted by section
// 3 row 8):
//
//   0x00  scaler value          0x08  configuration
//   0x04  scaler reload         0x0C  latch configuration
//   timer n at 0x10*n:  +0 counter  +4 reload  +8 control  +C latch
//
// docs/08 section 3 row 8 says "last timer is the watchdog", which this
// block mirrors in ADDRESSES and deliberately does not mirror in
// BEHAVIOUR. Timers 1..NGEN are ordinary GRLIB timers. Timer NGEN+1 is
// hw/soc/rtl/soc_wdog.v, which is armed at reset, cannot be disabled by
// software, does not share the scaler below, escalates in three stages
// and keeps its state through the reset it causes. Every one of those is
// a departure from GRLIB and every one is argued in
// docs/40-interrupts-timers-watchdog.md section 5. The header of
// soc_wdog.v states them as W1-W5; this file's job is to put them at the
// addresses a GRLIB reader will look in.
//
// WHY THE WATCHDOG IS NOT SIMPLY TIMER NGEN+1 OF THE LOOP BELOW. Two
// reasons, and the first is structural: it is in a different RESET
// DOMAIN. This module is reset by rst_ni, the system reset -- which the
// watchdog itself generates. The watchdog is reset by rst_por_ni and by
// nothing else, so that WDOGSTAT still says what happened after the
// reset has happened. A block cannot be half in one domain, so it is a
// separate module with its own suite and its own proof.
//
// =====================================================================
// WHAT IS AND IS NOT IMPLEMENTED
// =====================================================================
//
//   * ONE SHARED INTERRUPT, not one per timer. GRLIB's SI configuration
//     bit selects between "all timers share the block's interrupt" and
//     "timer n uses interrupt base+n"; this block implements the first
//     and reports SI = 0, so a driver reads the truth out of the
//     register. The reason is the frozen map: it gives this slot exactly
//     one source number (docs/memmap-soc.md section 3), and separate
//     interrupts would consume the three consecutive numbers 8, 9, 10
//     that GR740's numbering implies but that this project's map has not
//     reserved. A handler therefore reads the per-timer IP bits to find
//     out which timer fired, which is what a GRLIB driver does in the
//     SI = 0 configuration anyway.
//   * The watchdog does NOT contribute to that interrupt. Its signal is
//     the non-maskable one and it goes straight to the core.
//   * CHAINING (control bit CH) is implemented: timer n decrements when
//     timer n-1 reloads. Timer 1 has no predecessor and its CH reads 0.
//   * LATCH registers (0x0C and each timer's +0xC) are NOT implemented
//     and read as zero, and the latch-configuration field of the
//     configuration register reads zero with it. GRLIB's latch feature
//     snapshots every timer on an external event; there is no such event
//     in this SoC yet.
//   * DEBUG HALT (control bit DH) and DISABLE FREEZE (configuration bit
//     DF) are NOT implemented and read as zero. There is no debug module
//     in this SoC to freeze for.
//   * The scaler is SWIDTH bits and the timers are TWIDTH bits, which
//     GRLIB also leaves configurable. The configuration register does
//     not report either, matching GRLIB, so software has to know.
//
// Bus: AMBA 3 APB slave, PREADY tied high and PSLVERR tied low, exactly
// as soc_uart.v. An offset inside the slot that names no register reads
// as zero and a write to it does nothing, which is GRLIB's documented
// behaviour for unoccupied space behind a bridge (GR740 UM section 2.3).
// That differs from soc_clint.v, which faults an unimplemented offset --
// deliberately, because the CLINT is a system-bus region where this
// SoC's rule is that an address nothing implements is an error, and the
// peripheral bus is where GRLIB's rule applies.

`timescale 1ns / 1ps

module soc_gptimer #(
    parameter integer NGEN   = 2,    // general purpose timers
    parameter integer TWIDTH = 32,   // timer counter width
    parameter integer SWIDTH = 16,   // prescaler width
    parameter [4:0]   IRQ_NUM = 5'd0,// plug-and-play source number, from the map
    // Passed through to soc_wdog. See that file's header.
    parameter integer WDOG_WIDTH      = 16,
    parameter integer WDOG_PRESCALE   = 16,
    parameter integer WDOG_RST_CYCLES = 16,
    parameter integer WDOG_ESCALATE   = 2,
    parameter [15:0]  WDOG_KEY        = 16'hA51F
) (
    input  wire        clk_i,
    // System reset. The watchdog generates this; nothing in the watchdog
    // is reset by it.
    input  wire        rst_ni,
    // Power-on reset, for the watchdog only.
    input  wire        rst_por_ni,

    // ---- APB slave ----
    input  wire        psel_i,
    input  wire        penable_i,
    input  wire [11:0] paddr_i,
    input  wire        pwrite_i,
    input  wire [31:0] pwdata_i,
    output reg  [31:0] prdata_o,
    output wire        pready_o,
    output wire        pslverr_o,

    // ---- watchdog bootstrap pin ----
    input  wire        wdog_dis_i,

    // ---- interrupts and escalation ----
    output wire        irq_o,        // shared, timers 1..NGEN, maskable
    output wire        nmi_o,        // watchdog stage 1
    output wire        rst_req_o,    // watchdog stage 2
    output wire        wdog_no,      // watchdog stage 3, external pin

    // The watchdog's TMR fault line, passed straight through to
    // soc_busstat. docs/41 section 10 item 3.
    output wire        tmr_ev_o
);

  localparam integer NT = NGEN + 1;    // including the watchdog
  // Sized copies, so no expression below part-selects a parameter or an
  // integer. Both are accepted by some tools and not others, and three
  // of them read this file: Icarus, Yosys and Verilator.
  /* verilator lint_off WIDTHTRUNC */
  localparam [7:0] NGEN_B = NGEN;
  localparam [7:0] NT_IDX = NGEN + 1;
  localparam [2:0] NT_CFG = NGEN + 1;
  localparam [11:0] REG_WDOGSTAT = 12'h010 * (NGEN + 2);
  /* verilator lint_on WIDTHTRUNC */

  localparam [11:0] REG_SCALER    = 12'h000;
  localparam [11:0] REG_SCRELOAD  = 12'h004;
  localparam [11:0] REG_CONFIG    = 12'h008;
  localparam [11:0] REG_LATCHCFG  = 12'h00C;

  // GRLIB timer control bit positions.
  localparam integer B_EN = 0, B_RS = 1, B_LD = 2, B_IE = 3,
                     B_IP = 4, B_CH = 5;

  assign pready_o  = 1'b1;
  assign pslverr_o = 1'b0;

  wire access = psel_i && penable_i;
  wire wr     = access && pwrite_i;

  // Which timer, if any, this offset names. Timer n occupies
  // 0x10*n .. 0x10*n+0xC, for n in 1..NT.
  wire [7:0]  tsel_idx = paddr_i[11:4];              // == n
  wire [1:0]  tsel_reg = paddr_i[3:2];               // 0 cnt 1 rld 2 ctrl 3 latch
  wire        in_timer = (tsel_idx >= 8'd1) && (tsel_idx <= NT_IDX);
  wire        is_wdog  = in_timer && (tsel_idx == NT_IDX);

  // -------------------------------------------------------------------
  // Prescaler
  // -------------------------------------------------------------------
  reg [SWIDTH-1:0] scaler;
  reg [SWIDTH-1:0] scaler_reload;
  wire             tick = (scaler == 0);

  // -------------------------------------------------------------------
  // General timers
  // -------------------------------------------------------------------
  reg [TWIDTH-1:0] cnt  [1:NGEN];
  reg [TWIDTH-1:0] rld  [1:NGEN];
  reg              t_en [1:NGEN];
  reg              t_rs [1:NGEN];
  reg              t_ie [1:NGEN];
  reg              t_ip [1:NGEN];
  reg              t_ch [1:NGEN];

  // A timer reloads when it is enabled, its clock source ticks and it is
  // already at zero. The clock source is the prescaler for timer 1 and,
  // when CH is set, the previous timer's reload event for timer n.
  wire [NGEN:1] t_src;
  wire [NGEN:1] t_wrap;

  genvar gi;
  generate
    for (gi = 1; gi <= NGEN; gi = gi + 1) begin : g_src
      if (gi == 1) assign t_src[gi] = tick;
      else         assign t_src[gi] = t_ch[gi] ? t_wrap[gi - 1] : tick;
      assign t_wrap[gi] = t_en[gi] && t_src[gi] && (cnt[gi] == 0);
    end
  endgenerate

  // Shared, level, maskable. The watchdog is not in it.
  wire [NGEN:1] t_irq;
  generate
    for (gi = 1; gi <= NGEN; gi = gi + 1) begin : g_irq
      assign t_irq[gi] = t_ip[gi] && t_ie[gi];
    end
  endgenerate
  assign irq_o = |t_irq;

  // -------------------------------------------------------------------
  // The watchdog
  // -------------------------------------------------------------------
  //
  // sel is one-hot over {window, status, control, reload, counter} and
  // is asserted only in the ACCESS phase, so the block sees exactly one
  // register event per APB transfer.
  //
  // Bit 4 is WDOGWIN -- soc_wdog.v W7 and W8 -- and it sits at the
  // watchdog's own +0xC. In GRLIB that offset is a general timer's
  // LATCH register (grip.pdf table 463), which this block reports as
  // not implemented for every general timer and has never decoded at
  // all for the watchdog. Putting the cadence contract there rather
  // than at a new base costs no address space and keeps every watchdog
  // register inside the watchdog's own sixteen bytes.
  wire [4:0] wd_sel = {access && is_wdog && (tsel_reg == 2'd3),
                       access && (paddr_i == REG_WDOGSTAT),
                       access && is_wdog && (tsel_reg == 2'd2),
                       access && is_wdog && (tsel_reg == 2'd1),
                       access && is_wdog && (tsel_reg == 2'd0)};
  wire [31:0] wd_rdata;

  soc_wdog #(
      .WIDTH      (WDOG_WIDTH),
      .PRESCALE   (WDOG_PRESCALE),
      .RST_CYCLES (WDOG_RST_CYCLES),
      .ESCALATE   (WDOG_ESCALATE),
      .KEY        (WDOG_KEY)
  ) u_wdog (
      .clk_i      (clk_i),
      .rst_por_ni (rst_por_ni),
      .dis_i      (wdog_dis_i),
      .sel_i      (wd_sel),
      .we_i       (wr),
      .wdata_i    (pwdata_i),
      .rdata_o    (wd_rdata),
      .nmi_o      (nmi_o),
      .rst_req_o  (rst_req_o),
      .wdog_no    (wdog_no),
      .tmr_ev_o   (tmr_ev_o)
  );

  // -------------------------------------------------------------------
  // Sequential
  // -------------------------------------------------------------------
  // Eight bits, not an integer, so that (tsel_idx == n) is a
  // same-width comparison rather than a zero-extension.
  reg [7:0] n;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      scaler        <= {SWIDTH{1'b0}};
      scaler_reload <= {SWIDTH{1'b0}};
      for (n = 1; n <= NGEN_B; n = n + 1) begin
        cnt[n]  <= {TWIDTH{1'b0}};
        rld[n]  <= {TWIDTH{1'b0}};
        t_en[n] <= 1'b0;
        t_rs[n] <= 1'b0;
        t_ie[n] <= 1'b0;
        t_ip[n] <= 1'b0;
        t_ch[n] <= 1'b0;
      end
    end else begin
      // ---- prescaler ----
      if (wr && (paddr_i == REG_SCALER))
        scaler <= pwdata_i[SWIDTH-1:0];
      else if (tick)
        scaler <= scaler_reload;
      else
        scaler <= scaler - 1'b1;

      if (wr && (paddr_i == REG_SCRELOAD))
        scaler_reload <= pwdata_i[SWIDTH-1:0];

      // ---- timers ----
      for (n = 1; n <= NGEN_B; n = n + 1) begin
        // Counter. A write, then a load, then the countdown: a write to
        // the counter register and a LD in the same cycle cannot both
        // happen, because they are different addresses.
        if (wr && in_timer && (tsel_idx == n) && (tsel_reg == 2'd0))
          cnt[n] <= pwdata_i[TWIDTH-1:0];
        else if (wr && in_timer && (tsel_idx == n) &&
                 (tsel_reg == 2'd2) && pwdata_i[B_LD])
          cnt[n] <= rld[n];
        else if (t_en[n] && t_src[n])
          cnt[n] <= (cnt[n] == 0) ? rld[n] : cnt[n] - 1'b1;

        if (wr && in_timer && (tsel_idx == n) && (tsel_reg == 2'd1))
          rld[n] <= pwdata_i[TWIDTH-1:0];

        // Control. EN is cleared by the timer itself on a wrap when RS
        // is not set, which is GRLIB's one-shot behaviour.
        if (wr && in_timer && (tsel_idx == n) && (tsel_reg == 2'd2)) begin
          t_en[n] <= pwdata_i[B_EN];
          t_rs[n] <= pwdata_i[B_RS];
          t_ie[n] <= pwdata_i[B_IE];
          t_ch[n] <= (n == 1) ? 1'b0 : pwdata_i[B_CH];
          // IP is write-one-to-clear and is also set by a wrap in the
          // same cycle; the wrap wins, because losing an interrupt is
          // worse than reporting one twice.
          if (t_wrap[n])           t_ip[n] <= 1'b1;
          else if (pwdata_i[B_IP]) t_ip[n] <= 1'b0;
        end else begin
          if (t_wrap[n]) begin
            t_ip[n] <= 1'b1;
            if (!t_rs[n]) t_en[n] <= 1'b0;
          end
        end
      end
    end
  end

  // -------------------------------------------------------------------
  // Reads
  // -------------------------------------------------------------------
  //
  // The configuration register's IRQ field is the plug-and-play source
  // number, taken from the generated map through IRQ_NUM rather than
  // written down here, so the number a driver reads out of this block
  // and the number in the device table are the same number.
  // A separate loop variable from the sequential block's. Two always
  // blocks sharing one integer is a simulation race, not a style point.
  reg [7:0] m;
  reg [31:0] timer_rdata;
  always @(*) begin
    timer_rdata = 32'h0;
    for (m = 1; m <= NGEN_B; m = m + 1) begin
      if (tsel_idx == m) begin
        case (tsel_reg)
          2'd0: timer_rdata = {{(32 - TWIDTH){1'b0}}, cnt[m]};
          2'd1: timer_rdata = {{(32 - TWIDTH){1'b0}}, rld[m]};
          2'd2: timer_rdata = {26'h0, t_ch[m], t_ip[m], t_ie[m],
                               1'b0, t_rs[m], t_en[m]};
          default: timer_rdata = 32'h0;      // latch, not implemented
        endcase
      end
    end
  end

  always @(*) begin
    if (is_wdog || (paddr_i == REG_WDOGSTAT)) begin
      prdata_o = wd_rdata;
    end else if (in_timer) begin
      prdata_o = timer_rdata;
    end else begin
      case (paddr_i)
        REG_SCALER:   prdata_o = {{(32 - SWIDTH){1'b0}}, scaler};
        REG_SCRELOAD: prdata_o = {{(32 - SWIDTH){1'b0}}, scaler_reload};
        // TIMERS[2:0] IRQ[7:3] SI[8] DF[9]. SI reads 0: one shared
        // interrupt, see the header.
        REG_CONFIG:   prdata_o = {22'h0, 1'b0, 1'b0, IRQ_NUM, NT_CFG};
        REG_LATCHCFG: prdata_o = 32'h0;      // not implemented
        default:      prdata_o = 32'h0;
      endcase
    end
  end

endmodule
