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
//   * Protection for mtimecmp, msip, or the response registers. Section
//     H6 below is the argument, and it is an argument and not an
//     omission.
//
// UNIMPLEMENTED OFFSETS ARE A BUS ERROR, not a read of zero. This is the
// same choice soc_top.v makes for an unoccupied peripheral slot and the
// same choice soc_bus.v makes for an unmapped address, and it is made
// for the same reason: a register that reads zero looks like a register
// that works. It does diverge from a multi-hart-aware driver's
// expectation that probing hart 1's MSIP returns something rather than
// faulting -- there is no hart 1 in this SoC, and saying so loudly is
// the point.
//
// =====================================================================
// H6: MTIME IS A CODEWORD, AND THE CODE CORRECTS IT EVERY TICK
// =====================================================================
//
// docs/41 section 7.4 ranked mtime above everything the watchdog wave
// left unprotected and then declined to protect it, on cost:
//
//     mtime is monotonic and free-running and never reloads, so an
//     upset displaces it FOR EVER ... a single-bit flip in a high bit
//     jumps the architectural clock by up to 2^63 ticks, and every
//     deadline software computes as mtime + delta is then wrong
//
// and priced the obvious answer -- triple mtime and mtimecmp -- at 256
// added flip-flops and roughly +27,000 um2, about a tenth of the Ibex
// core. docs/43 section 12 and docs/44 section 3 deferred it twice more,
// each time for a stated reason. This is the answer, and it is not TMR.
//
// WHAT THE STRUCTURE BUYS. TMR is what you use when the next value of a
// register is unrelated to its current one, because then the only way to
// know the stored value is wrong is to store it again somewhere else.
// mtime is not that register: its next value is its current value plus
// one, and a code over it is therefore CHECKABLE and REPAIRABLE without
// a second copy of the data. Concretely:
//
//   mtime is held as the 64-bit data field of a (72,64) SECDED codeword
//   whose 8 check bits are the only added state. Every tick the stored
//   codeword is DECODED, the corrected 64-bit value is what ticks, what
//   the comparator sees and what a bus read returns, and the check bits
//   are RE-ENCODED over the value that goes back in.
//
// Three consequences, and the third is the one that makes this cheap:
//
//   1. A single-bit upset anywhere in the 72 bits -- data or check -- is
//      CORRECTED, not merely detected, and it is corrected before it
//      reaches any port. mtip never asserts early, a bus read never
//      returns the corrupt word, and the counter goes on from the right
//      value. That is the same guarantee TMR gives, on 8 added
//      flip-flops instead of 128.
//   2. A double-bit upset is DETECTED and never miscorrected, because
//      every column of the H matrix in secded_enc.v has odd weight. The
//      block cannot repair it -- the information is gone -- and it says
//      so on mt_ecc_o.
//   3. THE COUNTER SCRUBS ITSELF. A code over a register that is written
//      once a mission needs a scrubber, because errors accumulate until
//      something rewrites the word; docs/43 built one for the register
//      file and docs/43 section 6.4 left its period unbounded. mtime is
//      rewritten EVERY CLOCK by construction, so the scrub period here
//      is one cycle and there is no scrubber to build, no period to
//      choose and no accumulation to bound. The window in which a second
//      upset could turn a correctable word into an uncorrectable one is
//      20 ns wide.
//
// WHY NOT A RESIDUE CHECK, which docs/41 section 7.4 pointed at. A
// residue mod k maintained beside the counter -- r <= r + 1 mod k, and
// check mtime mod k == r -- is cheaper still: mod 3 is TWO flip-flops.
// It detects every single-bit flip, and that is not a small claim: a
// flip at bit i changes the value by +/- 2^i, and 2 is invertible modulo
// any ODD k, so 2^i is never 0 mod k and the residue always moves. All
// 64 bits, not most of them. (The trap is an EVEN modulus: mod 2^a the
// residue is the low a bits and is blind to bits a..63 -- 62 of the 64
// bits at mod 4. An even modulus is a check that covers the harmless end
// of the counter and none of the dangerous one.)
//
// But it only DETECTS. The residue says the clock is wrong; it does not
// say by how much, so there is nothing to subtract. Making a residue
// CORRECT means making the syndrome name the bit -- an arithmetic AN
// code with the 128 values +/- 2^i all distinct mod k, which needs k
// > 128 and so 8 check flip-flops, the SAME storage as this SECDED, plus
// a 128-way syndrome decode that the Hamming code gets for free from its
// column structure. So the residue is not a cheaper corrector; it is
// only a cheaper detector, and docs/38 section 8.5's argument against
// lockstep applies here in reverse: a detector whose only recovery is
// "software is told its clock is wrong" is worth less than a corrector
// that costs six more flip-flops. It is priced in docs/58 section 4.
//
// WHAT IS DELIBERATELY NOT PROTECTED, and these are decisions:
//
//   * mtimecmp, 64 flip-flops. It fails the docs/41 section 3.1
//     criterion on BOTH halves. It is not persistent -- software
//     rewrites it at every deadline, so an upset survives one interval
//     and not the mission -- and it is not silent: an upset DOWNWARD
//     satisfies mtime >= mtimecmp at once, the handler runs early and
//     rewrites the deadline, and an upset UPWARD moves the deadline out
//     of reach so the timer interrupt stops, which is a missed deadline,
//     which is the exact failure the watchdog is the backstop for.
//     mtime's upset is the one that keeps the interrupts coming and
//     makes them all wrong. That is the asymmetry, and it is why the
//     code is over the counter and not over the comparand.
//   * msip, 1 flip-flop. One bit cannot be tripled -- the replication
//     bound in soc_tmr_bank.v's header -- and there is nothing in this
//     module to bundle it with that shares its reset domain and its
//     write policy. Its upset raises or drops a software interrupt that
//     software itself sets and clears, and it is visible in the register
//     it lives in.
//   * rdata_o, rvalid_o, err_o -- 34 flip-flops of bus response. They
//     are overwritten every cycle from the request, which is docs/41
//     section 3.1's "a register the block itself overwrites every tick
//     sheds an upset on its own".
//   * tick_cnt. At TICK_DIV = 1 it is dead logic and the optimiser
//     removes it: the block's 163 flip-flops are 64 + 64 + 1 + 32 + 1 +
//     1 and there are none of it left to protect.
//
// WHAT THE REPORT IS, and what it conflates. mt_ecc_o is one cycle high
// whenever the stored codeword was not a codeword, corrected or not. It
// goes to BUSSTAT (docs/44), which is the only telemetry destination in
// this SoC: there is NO free offset in a standard CLINT window to put a
// status register at -- 0x0000..0x3FFF is the msip array, 0x4000..0xBFF7
// the mtimecmp array and 0xBFF8..0xBFFF mtime, so every offset this
// block faults on is architecturally spoken for by a hart that does not
// exist. Conflating a correction with an uncorrectable is the mistake
// soc_busstat.v's own header criticises pilot_top.v for making, and it
// is made here knowingly: BUSSTAT's STATUS register has exactly one bit
// left below the interrupt bit that its header forbids moving, and the
// class the conflation hides -- an uncorrectable -- needs two upsets
// inside one 20 ns tick in one 72-bit word, which is outside the
// single-upset fault model every campaign in this repository uses.
// docs/58 section 9 prices the separation at 18 more flip-flops.

`timescale 1ns / 1ps

module soc_clint #(
    // System clocks per mtime tick. 1 means mtime counts CPU cycles,
    // which is what the simulation uses because it makes every deadline
    // in a test exactly computable. A real part sets this from the
    // always-on time base's frequency.
    parameter integer TICK_DIV = 1,
    // H6. 1 holds mtime as a (72,64) SECDED codeword and corrects it on
    // every tick; 0 is the design docs/40 shipped, bit for bit.
    //
    // The unhardened configuration exists so that the SAME source list
    // and the SAME recipe can measure the baseline -- docs/41 section
    // 6.5's rule, which is that a baseline taken against an older file
    // list credits the hardening with a refactor's saving. NOTHING IN
    // THIS DESIGN INSTANTIATES IT AT 0, and sw/tests asserts that.
    parameter integer HARDEN = 1
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
    output wire        irq_software_o,   // Ibex irq_software_i, ID 3

    // ---- fault line, to soc_busstat.v (docs/44) ----
    //
    // ONE CYCLE PER EVENT BY CONSTRUCTION, which is the property
    // soc_busstat.v's counters need and which this block gets for free:
    // the codeword is re-encoded over the corrected value on the very
    // next edge, so a syndrome that is nonzero this cycle is zero the
    // next whether it was correctable or not. Constant 0 at HARDEN = 0.
    output wire        mt_ecc_o
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
  //
  // mtime_q is the STORED data field and `mtime` is the ARCHITECTURAL
  // value: at HARDEN = 1 they differ for exactly the one cycle after an
  // upset lands, and everything downstream -- the tick, the comparator,
  // the read multiplexer -- reads `mtime`. That is what makes the
  // correction invisible at the ports rather than merely available.
  reg [63:0] mtime_q;
  reg [7:0]  mtime_chk_q;
  reg [63:0] mtimecmp;
  reg        msip;

  reg [31:0] tick_cnt;
  wire       tick = (TICK_DIV <= 1) || (tick_cnt == 32'd0);

  wire [63:0] mtime;            // corrected, architectural
  wire [63:0] mtime_next;       // declared below, used by the codec
  wire [7:0]  mtime_chk_next;

  generate
  if (HARDEN != 0) begin : g_mtime_secded
    // hw/rtl/secded_dec.v and hw/rtl/secded_enc.v are READ from the
    // pilot's directory and never modified, exactly as
    // hw/rtl/tmr_voter.v is by soc_wdog.v and as these two already are
    // by ibex_regfile_secded.v (docs/43). docs/34 freezes that
    // directory by blob hash; nothing here touches it. They are fixed
    // at 64 data bits and 8 check bits by an elaboration guard, and 64
    // is exactly mtime's width, so no width parameter is passed and
    // none could be.
    wire       sec, ded;
    wire [7:0] syndrome_unused;

    secded_dec u_mtime_dec (
        .code_in  ({mtime_chk_q, mtime_q}),
        .data_out (mtime),
        .syndrome (syndrome_unused),
        .sec      (sec),
        .ded      (ded)
    );

    // Encoded over the value that is about to be STORED, not over the
    // value that was stored. Written the other way -- check bits
    // recomputed from mtime_q -- the code would follow the corruption
    // into consistency on the next edge and the error would be gone
    // without ever having been seen or repaired. That is the standard
    // way to build an ECC counter that silently does nothing.
    wire [71:0] code_unused;
    secded_enc u_mtime_enc (
        .data_in   (mtime_next),
        .check_out (mtime_chk_next),
        .code_out  (code_unused)
    );

    // Both classes, on one wire. The header says what that conflates
    // and why there is one wire and not two.
    assign mt_ecc_o = sec | ded;
  end else begin : g_mtime_plain
    assign mtime          = mtime_q;
    assign mtime_chk_next = 8'h0;
    assign mt_ecc_o       = 1'b0;
  end
  endgenerate

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
  //
  // EVERY TERM BELOW READS `mtime` AND NOT `mtime_q`, which is the whole
  // of the H6 correction: the value that ticks is the corrected one, so
  // a single upset is repaired on the next edge and never accumulates.
  wire [63:0] mtime_ticked = tick ? (mtime + 64'd1) : mtime;
  wire        wr_mtimel    = wr && (off == REG_MTIMEL);
  wire        wr_mtimeh    = wr && (off == REG_MTIMEH);
  assign      mtime_next   = {
      wr_mtimeh ? wmerge(mtime[63:32], be_i, wdata_i) : mtime_ticked[63:32],
      wr_mtimel ? wmerge(mtime[31:0], be_i, wdata_i)  : mtime_ticked[31:0]};

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      // secded_enc.v's H matrix over the all-zero word gives the
      // all-zero check field, so this reset image is a valid codeword
      // and the design comes out of reset with a clean syndrome. It is
      // an arithmetic fact about the code and not a coincidence: every
      // check bit is an XOR reduction over a subset of the data.
      mtime_q     <= 64'd0;
      mtime_chk_q <= 8'h00;
      mtimecmp    <= 64'd0;
      msip        <= 1'b0;
      tick_cnt    <= 32'd0;
      rvalid_o    <= 1'b0;
      rdata_o     <= 32'h0;
      err_o       <= 1'b0;
    end else begin
      // -- time base --
      if (TICK_DIV > 1) begin
        if (tick_cnt == 32'd0) tick_cnt <= TICK_DIV[31:0] - 32'd1;
        else                   tick_cnt <= tick_cnt - 32'd1;
      end
      mtime_q     <= mtime_next;
      mtime_chk_q <= mtime_chk_next;

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
