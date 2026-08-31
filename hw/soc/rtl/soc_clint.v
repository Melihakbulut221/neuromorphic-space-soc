// Core-local interruptor: the RISC-V machine timer and the machine
// software interrupt.
//
// WHAT THIS IS FOR, and why it is not the same thing as the GPTIMER two
// slots away on the peripheral bus. That question is argued in
// docs/40-interrupts-timers-watchdog.md section 4; the short form is the
// division of labour this file implements and the GPTIMER's header
// mirrors:
//
//   CLINT owns TIME. mtime is a free-running 64-bit up-counter that is
//   never reloaded and never restarted, and mtimecmp is a deadline on
//   it. That is the only time base with an architectural meaning: the
//   RISC-V privileged specification names mtime, every RV32 operating
//   system's clocksource reads it, and a core without one has no
//   portable notion of elapsed time. It drives irq_timer_i and NOTHING
//   ELSE drives irq_timer_i.
//
//   GPTIMER owns INTERVALS. Its timers count DOWN from a reload value
//   and restart, which is what periodic work and timeouts want, and its
//   last timer is the watchdog. It is a peripheral, on the peripheral
//   bus, with GRLIB's register map.
//
// Up-counting monotonic time and down-counting reloadable intervals are
// different jobs with different register shapes, and neither is a
// convenient way to do the other's. That is the whole answer to "are
// these two blocks duplication".
//
// =====================================================================
// REGISTER MAP
// =====================================================================
//
// The standard CLINT layout, which is what NOELVSYS places at
// 0xE0000000 (docs/08-gr801-datasheet-notes.md section 2.2) and what
// every RISC-V platform uses. Offsets are within the region.
//
//   0x0000  MSIP       bit 0 only. Writing 1 raises irq_software_o.
//   0x4000  MTIMECMPL  low  32 bits of the 64-bit deadline
//   0x4004  MTIMECMPH  high 32 bits
//   0xBFF8  MTIMEL     low  32 bits of the 64-bit counter
//   0xBFFC  MTIMEH     high 32 bits
//
// mtip_o is a LEVEL: mtime >= mtimecmp, unsigned, 64 bits wide, compared
// combinationally every cycle. It is not a pulse and it is not latched.
// The only way software clears it is by moving mtimecmp above mtime,
// which is the RISC-V privileged specification's own statement of how
// the machine timer works and is why there is no "acknowledge" register
// here to get wrong.
//
// MSIP AND MTIMECMP RESET TO ZERO, WHICH MEANS MTIP IS HIGH AT RESET.
// mtimecmp = 0 and mtime = 0 satisfies mtime >= mtimecmp. That is
// correct and standard -- the RISC-V specification gives mtimecmp no
// reset value, and a platform that reset it to zero has a pending timer
// interrupt from cycle zero. It is harmless because mie.MTIE resets to
// zero, so nothing is taken until software enables it, but a driver that
// enables MTIE before programming mtimecmp will take an immediate
// interrupt. Recorded here rather than hidden behind a non-standard
// reset value, and hw/soc/tb/cocotb/test_soc_clint.py asserts it.
//
// =====================================================================
// THE 64-BIT-REGISTER-ON-A-32-BIT-BUS HAZARD, NOT SOLVED HERE
// =====================================================================
//
// mtimecmp is 64 bits and the bus is 32. Writing it in two stores passes
// through an intermediate value that is neither the old deadline nor the
// new one, and if that intermediate is <= mtime a spurious timer
// interrupt appears between the two stores.
//
// This block does NOT paper over that with a shadow register, because
// doing so would change the programming model that every RISC-V timer
// driver already implements. The architectural sequence is the one in
// the RISC-V privileged specification's own commentary:
//
//     sw   all_ones, MTIMECMPL   ; no deadline can be met
//     sw   new_hi,   MTIMECMPH
//     sw   new_lo,   MTIMECMPL
//
// The same hazard exists on a 64-bit READ of mtime, and the standard
// answer is the same: read high, read low, read high again, and repeat
// if the two highs differ. hw/soc/tb/sw/test_ibex.c uses both sequences
// and hw/soc/tb/cocotb/test_soc_clint.py demonstrates the hazard is real
// by driving the naive sequence and observing the spurious interrupt.
//
// =====================================================================
// WHAT IS NOT HERE
// =====================================================================
//
//   * More than one hart. MSIP is one bit at offset 0 and MTIMECMP one
//     pair at 0x4000. A multi-hart CLINT indexes both by hart ID; there
//     is one hart, so there is one of each, and every other offset in
//     the 64 KiB window is unimplemented.
//   * An independent time base. mtime here is driven from the system
//     clock divided by TICK_DIV. A real part wants mtime on an
//     always-on oscillator that survives the system clock being gated or
//     stopped, which is a clocking and power-intent question this SoC
//     has not reached. Consequence: with TICK_DIV = 1 the mtime tick and
//     the CPU cycle are the same event, so mtime cannot be used to
//     measure anything the clock itself is doing wrong.
//   * Any protection. No parity on the counter, no ECC, no redundancy.
//     An upset in mtime is a silently wrong clock and nothing here would
//     notice. That belongs with the hardening architecture.
//
// UNIMPLEMENTED OFFSETS ARE A BUS ERROR, not a read of zero. This is the
// same choice soc_top.v makes for an unoccupied peripheral slot and the
// same choice soc_bus.v makes for an unmapped address, and it is made
// for the same reason: a register that reads zero looks like a register
// that works. It does diverge from a multi-hart-aware driver's
// expectation that probing hart 1's MSIP returns something rather than
// faulting -- there is no hart 1 in this SoC, and saying so loudly is
// the point.

`timescale 1ns / 1ps

module soc_clint #(
    // System clocks per mtime tick. 1 means mtime counts CPU cycles,
    // which is what the simulation uses because it makes every deadline
    // in a test exactly computable. A real part sets this from the
    // always-on time base's frequency.
    parameter integer TICK_DIV = 1
) (
    input  wire        clk_i,
    input  wire        rst_ni,

    // ---- system bus slave port, soc_bus.v rules S1-S4 ----
    input  wire        req_i,
    input  wire [31:0] addr_i,
    input  wire        we_i,
    input  wire [3:0]  be_i,
    input  wire [31:0] wdata_i,
    output wire        gnt_o,
    output reg         rvalid_o,
    output reg  [31:0] rdata_o,
    output reg         err_o,

    // ---- to the core ----
    output wire        irq_timer_o,      // Ibex irq_timer_i,    ID 7
    output wire        irq_software_o    // Ibex irq_software_i, ID 3
);

  // Offsets within the region. Sixteen bits is the whole 64 KiB window.
  localparam [15:0] REG_MSIP      = 16'h0000;
  localparam [15:0] REG_MTIMECMPL = 16'h4000;
  localparam [15:0] REG_MTIMECMPH = 16'h4004;
  localparam [15:0] REG_MTIMEL    = 16'hBFF8;
  localparam [15:0] REG_MTIMEH    = 16'hBFFC;

  wire [15:0] off = addr_i[15:0];

  wire hit = (off == REG_MSIP)      || (off == REG_MTIMECMPL)
          || (off == REG_MTIMECMPH) || (off == REG_MTIMEL)
          || (off == REG_MTIMEH);

  // ---- storage ----
  reg [63:0] mtime;
  reg [63:0] mtimecmp;
  reg        msip;

  reg [31:0] tick_cnt;
  wire       tick = (TICK_DIV <= 1) || (tick_cnt == 32'd0);

  // ---- interrupt outputs ----
  //
  // Both are levels, as Ibex requires: its interrupt inputs are
  // level-sensitive and it is the source's job to deassert them
  // (ext/ibex/doc/03_reference/exception_interrupts.rst).
  assign irq_timer_o    = (mtime >= mtimecmp);
  assign irq_software_o = msip;

  // ---- bus ----
  //
  // Always ready, fixed one-cycle response. That is the same shape
  // soc_mem.v has and it is what makes an mtime read cost one fabric
  // cycle rather than the bridge's three.
  assign gnt_o = req_i;

  wire wr = req_i && we_i && hit;

  // Byte lanes are honoured. Every other register block in this SoC
  // writes whole words and says so; here they are honoured because a
  // 64-bit CSR written as two words through a compiler that may split a
  // store is exactly where a dropped lane would be invisible.
  // EVERY input is an argument, including be_i and wdata_i, which are
  // module-level nets this function could have read directly. It could
  // not, in fact: mtime_next below is a CONTINUOUS assignment that calls
  // this function, and a continuous assignment's sensitivity is inferred
  // from the expression -- which, for a function call, is the argument
  // list and not whatever the body happens to reference. Written the
  // short way, mtime_next never re-evaluated when wdata_i moved, and the
  // effect was that writes to mtime silently did nothing while writes to
  // mtimecmp (assigned inside a clocked always block, so re-evaluated at
  // every edge) worked perfectly. The symptom in
  // hw/soc/tb/cocotb/test_soc_clint.py was a 64-bit comparison that
  // looked off by one.
  function [31:0] wmerge;
    input [31:0] old;
    input [3:0]  be;
    input [31:0] wd;
    begin
      wmerge = {be[3] ? wd[31:24] : old[31:24],
                be[2] ? wd[23:16] : old[23:16],
                be[1] ? wd[15:8]  : old[15:8],
                be[0] ? wd[7:0]   : old[7:0]};
    end
  endfunction

  // The next value of mtime, as ONE expression rather than an increment
  // and a later bit-select override. Written the second way -- an
  // unconditional 64-bit increment followed by a 32-bit write -- the
  // later assignment wins only for the bits it covers, so a store to
  // MTIMEL in the same cycle as a carry out of bit 31 would keep the
  // carry in the upper half and discard it in the lower, producing a
  // clock that has jumped by 2^32. A software write takes precedence
  // over the tick for the half it names, and the other half still ticks.
  wire [63:0] mtime_ticked = tick ? (mtime + 64'd1) : mtime;
  wire        wr_mtimel    = wr && (off == REG_MTIMEL);
  wire        wr_mtimeh    = wr && (off == REG_MTIMEH);
  wire [63:0] mtime_next   = {
      wr_mtimeh ? wmerge(mtime[63:32], be_i, wdata_i) : mtime_ticked[63:32],
      wr_mtimel ? wmerge(mtime[31:0], be_i, wdata_i)  : mtime_ticked[31:0]};

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      mtime    <= 64'd0;
      mtimecmp <= 64'd0;
      msip     <= 1'b0;
      tick_cnt <= 32'd0;
      rvalid_o <= 1'b0;
      rdata_o  <= 32'h0;
      err_o    <= 1'b0;
    end else begin
      // -- time base --
      if (TICK_DIV > 1) begin
        if (tick_cnt == 32'd0) tick_cnt <= TICK_DIV[31:0] - 32'd1;
        else                   tick_cnt <= tick_cnt - 32'd1;
      end
      mtime <= mtime_next;

      // -- register writes --
      if (wr) begin
        case (off)
          REG_MSIP:      msip <= be_i[0] ? wdata_i[0] : msip;
          REG_MTIMECMPL: mtimecmp[31:0]  <= wmerge(mtimecmp[31:0], be_i, wdata_i);
          REG_MTIMECMPH: mtimecmp[63:32] <= wmerge(mtimecmp[63:32], be_i, wdata_i);
          default: ;
        endcase
      end

      // -- response --
      rvalid_o <= req_i;
      err_o    <= req_i && !hit;
      if (req_i) begin
        case (off)
          REG_MSIP:      rdata_o <= {31'h0, msip};
          REG_MTIMECMPL: rdata_o <= mtimecmp[31:0];
          REG_MTIMECMPH: rdata_o <= mtimecmp[63:32];
          REG_MTIMEL:    rdata_o <= mtime[31:0];
          REG_MTIMEH:    rdata_o <= mtime[63:32];
          default:       rdata_o <= 32'h0;
        endcase
      end
    end
  end

`ifdef FORMAL
`include "soc_clint_props.v"
`endif

endmodule
