// BOOTREG: the bootstrap pins as they were sampled, the boot counter no
// software can write, and two words that survive the reset they
// describe.
//
// =====================================================================
// WHY THIS BLOCK EXISTS
// =====================================================================
//
// docs/68 builds the boot flow: a loader in the ROM copies a
// checksummed image out of the QSPI flash docs/66 built, into the
// SECDED-protected RAM docs/67 built, and jumps to it. Three of that
// flow's four questions need state that is NOT in either of those
// blocks, and the frozen map has had the slot ready for them since
// docs/39:
//
//     0xFF917000  BOOTREG  reserved
//     "Bootstrap pin readback and boot report register, GRGPREG-like"
//
// GR716B's boot flow (docs/08 section 2.4) is the shape: bootstrap pins
// select the boot source and can bypass the ROM, and a general-purpose
// register block carries a boot report across the reset. GR740's
// GRGPREG is the register block this is named after.
//
// =====================================================================
// THE ONE FIELD WITH AUTHORITY IS THE ONE SOFTWARE CANNOT WRITE
// =====================================================================
//
// That sentence is the whole design rule of this block, and it is what
// keeps it out of docs/40 section 7.2's brick loop.
//
// docs/40's watchdog put its record in the POWER-ON domain (W4) so that
// a stage-2 reset could not erase the evidence of what caused it -- and
// then found, by running it, that the RELOAD register was in the same
// domain, so a short timeout installed by software that had already
// gone wrong survived the reset that going wrong caused, and the SoC
// reset itself for ever with the console never reaching its first
// character. Putting state outside the reset domain is what makes a
// record survive; it is also what makes a stale configuration survive.
//
// A boot report is exactly that shape again: it must survive the reset
// it describes, and the boot flow that reads it must not be able to
// brick itself on what it finds. The rule here is therefore sharper
// than "restore the default on reset":
//
//   * BOOTCNT is maintained BY HARDWARE, saturating, cleared only by
//     power-on reset, and NO APB WRITE CHANGES IT. It is the only field
//     of this block that changes what the loader does -- it is what
//     stops the loader retrying -- and it is the only field software
//     cannot forge. That is soc_wdog.v W1's independence argument
//     ("a watchdog its own software can switch off is not a backstop
//     against software that has stopped behaving") applied to a boot
//     counter, and it is why this block needs no write key: the
//     watchdog keyed its writes because its ACKNOWLEDGE had authority
//     (soc_wdog.v W5), and nothing writable here has any.
//
//   * BRPT and EPOCH are EVIDENCE, not authority. Software writes them,
//     they survive a stage-2 reset, and nothing in this block or in the
//     boot flow branches on their contents. A runaway core can fill
//     them with rubbish and the worst outcome is a wrong diagnosis in
//     telemetry; it cannot lengthen a budget, shorten a timeout or
//     persuade the next boot to try again.
//
//   * NOTHING HERE CAN EXTEND A DEADLINE. This block has no output that
//     reaches the watchdog, the memories or the fabric. Its only ports
//     out are the APB read data. The failure docs/40 section 7.2 found
//     was a persistent register that could SHORTEN the next boot's
//     budget; a persistent register that cannot reach the budget at all
//     is the structural version of the same fix.
//
// =====================================================================
// BOOTCNT: WHY IT IS NOT WDOGSTAT.RSTCNT
// =====================================================================
//
// soc_wdog.v already carries RSTCNT, saturating and power-on-only, and
// on THIS SoC every non-power-on reset is a watchdog stage-2 reset, so
// today the two counters are the same number. They are two counters
// anyway, and the reason is what each one counts:
//
//   RSTCNT   stage-2 assertions BY THE WATCHDOG. It is the watchdog's
//            own escalation input and it is inside the watchdog's
//            key-protected, triple-redundant register bank.
//   BOOTCNT  RELEASES OF THE SYSTEM RESET, whatever asserted it, with
//            the power-on boot counting zero.
//
// The boot flow escalates on the number of times it has BOOTED, not on
// the number of times a particular block reset it: a boot loop driven
// by something the watchdog did not cause -- an external reset pin, a
// brownout, a debug reset, none of which this SoC has yet -- must still
// terminate. Counting the boot is the general statement and counting
// the watchdog is the special case; the loader reads both and reports
// the pair, so that on this SoC, where they must agree, a disagreement
// is a finding rather than an invisible divergence.
//
// =====================================================================
// THE STRAPS
// =====================================================================
//
// Sampled ONCE, three clocks after power-on reset releases, through two
// synchroniser flops, and ignored for ever after. soc_wdog.v W1 states
// the reason for its own bootstrap pin and it is the same one: a pin
// that could change a boot decision at any moment would be a hardware
// back door into the decision. BSTRAP.VALID says the sample has been
// taken, so a read taken in the first three clocks -- which no software
// can do, because the core is fetching its first instruction -- is
// distinguishable from a strap field of zero.
//
//   bit 0   SRC0  \  boot source: 0 = flash on chip select 0,
//   bit 1   SRC1  /  1 = chip select 1, 2 and 3 reserved
//   bit 2   NOBOOT   do not load an image; stay in the ROM. This is
//                    GR716B's "direct boot" bootstrap in the only form
//                    this part can offer it, and it is the board's way
//                    of getting a part with a bad flash to a console.
//   bit 3   spare
//
// The names are a SOFTWARE CONVENTION -- hw/soc/tb/sw/soc_boot.h -- and
// not a hardware behaviour. This block samples the pins and reports
// them; the loader is what acts on them. That split is deliberate: a
// strap that gated something in hardware would be a second, silent
// control path into a flow whose whole argument is that its control
// path is one counter.
//
// WDOGDIS is the watchdog's OWN bootstrap pin, sampled here a second
// time for readback. It is reported and not consumed: soc_wdog.v
// samples the same wire for itself and WDOGSTAT.DISABLED is the
// authoritative report of what the watchdog did with it. Two samples of
// one static pin that must agree is a cheap cross-check and it is what
// makes "the map promises bootstrap pin readback" true for the one
// bootstrap pin this SoC had before this document.
//
// =====================================================================
// EPOCH
// =====================================================================
//
// docs/58 section 5.2 planned the recovery from an uncorrectable in
// mtime -- "it re-epochs" -- and said the correlation with absolute
// time "has to come from outside". mtime is in the SYSTEM reset domain
// and a stage-2 reset zeroes it, so every boot starts a new epoch
// whether anything asked for one or not. EPOCH is where the epoch's
// IDENTITY lives: a word in the power-on domain that the loader
// increments once per boot before it hands over, so that two readings
// of mtime taken in different epochs are distinguishable as such.
//
// It is deliberately NOT a copy of mtime and not a second time base.
// Nothing here counts. Reconstructing the elapsed time across a reset
// needs a counter in the power-on domain that this part does not have,
// and docs/58 section 5.2's `mcycle` reconstruction is still [planned];
// what this register removes is the weaker failure of not being able to
// tell that a re-epoch happened at all.
//
// =====================================================================
// BUS
// =====================================================================
//
// AMBA 3 APB slave, the conventions soc_uart.v, soc_busstat.v and
// soc_scrub.v use: PREADY tied high, PSLVERR tied low, an offset inside
// the slot that names no register reads zero and a write to it does
// nothing.

`timescale 1ns / 1ps
`default_nettype none

module soc_boot #(
    // Bootstrap pins. Four is what soc_top.v brings out; the block
    // accepts 1..16 and BSTRAP reports the width so a driver written
    // for a wider part reads the right number of bits.
    parameter integer NSTRAP = 4,

    // Boot counter width. 8 bits, saturating at 255.
    parameter integer CNT_W = 8,

    // THE ATTEMPT LIMIT, AND WHY IT IS A PARAMETER AND NOT A REGISTER.
    //
    // soc_wdog.v W2: "a bound enforced by the width of a counter cannot
    // be misconfigured; one enforced by a comparator can." The same
    // argument applies one level up. The number of boots after which
    // the loader stops trying the flash is a property of the part, it
    // is reported through BSTAT so the loader does not carry a second
    // copy of it, and no register reaches it.
    //
    // THREE, and the reason is soc_top.v's WDOG_ESCALATE = 2. The
    // watchdog asserts its external pin on its SECOND stage-2 reset,
    // which is the reset that begins boot 2 (counting the power-on boot
    // as 0). Setting the limit to 3 makes boot 2 the last one the
    // loader attempts, and it is a boot during which the platform
    // supervisor has ALREADY been told: software gives up after the
    // hardware has escalated, never before. docs/68 section 6.
    parameter integer LIMIT = 3
) (
    input  wire        clk_i,
    // System reset. Not used to reset anything in this block -- see the
    // header -- but its RELEASE is what BOOTCNT counts, so it is an
    // input to the logic rather than to the flip-flops.
    input  wire        rst_ni,
    // Power-on reset. The only reset this block has.
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

    // ---- the pins ----
    input  wire [NSTRAP-1:0] strap_i,
    input  wire        wdog_dis_i
);

  localparam [11:0] REG_BSTRAP = 12'h000;
  localparam [11:0] REG_BSTAT  = 12'h004;
  localparam [11:0] REG_BRPT   = 12'h008;
  localparam [11:0] REG_EPOCH  = 12'h00C;

  localparam [CNT_W-1:0] CNT_MAX = {CNT_W{1'b1}};

  assign pready_o  = 1'b1;
  assign pslverr_o = 1'b0;

  wire access = psel_i && penable_i;
  wire wr     = access && pwrite_i;

  // -------------------------------------------------------------------
  // The straps, sampled once
  // -------------------------------------------------------------------
  //
  // Two synchroniser flops per pin and then a hold. `dly` counts the
  // three clocks; when it reaches 3 the synchronised value is latched
  // and VALID goes high, and neither ever changes again short of a
  // power cycle.
  reg [NSTRAP-1:0] sync0, sync1;
  reg              wsync0, wsync1;
  reg [1:0]        dly;
  reg              valid_q;
  reg [NSTRAP-1:0] strap_q;
  reg              wdis_q;

  always @(posedge clk_i or negedge rst_por_ni) begin
    if (!rst_por_ni) begin
      sync0   <= {NSTRAP{1'b0}};
      sync1   <= {NSTRAP{1'b0}};
      wsync0  <= 1'b0;
      wsync1  <= 1'b0;
      dly     <= 2'd0;
      valid_q <= 1'b0;
      strap_q <= {NSTRAP{1'b0}};
      wdis_q  <= 1'b0;
    end else begin
      sync0  <= strap_i;
      sync1  <= sync0;
      wsync0 <= wdog_dis_i;
      wsync1 <= wsync0;
      if (!valid_q) begin
        if (dly == 2'd2) begin
          strap_q <= sync1;
          wdis_q  <= wsync1;
          valid_q <= 1'b1;
        end else begin
          dly <= dly + 2'd1;
        end
      end
    end
  end

  // -------------------------------------------------------------------
  // BOOTCNT: releases of the system reset, saturating, power-on only
  // -------------------------------------------------------------------
  //
  // `armed_q` is what makes the POWER-ON boot count zero. The power-on
  // release is a release like any other and would otherwise be counted;
  // instead it arms the counter, so BOOTCNT reads "boots since power-on,
  // not counting this one" -- which is the number the loader needs,
  // because it is deciding whether to attempt THIS boot.
  reg                sys_q;
  reg                armed_q;
  reg [CNT_W-1:0]    cnt_q;

  always @(posedge clk_i or negedge rst_por_ni) begin
    if (!rst_por_ni) begin
      sys_q   <= 1'b0;
      armed_q <= 1'b0;
      cnt_q   <= {CNT_W{1'b0}};
    end else begin
      sys_q <= rst_ni;
      if (rst_ni && !sys_q) begin
        if (!armed_q)        armed_q <= 1'b1;
        else if (~&cnt_q)    cnt_q   <= cnt_q + {{(CNT_W-1){1'b0}}, 1'b1};
      end
    end
  end

  // -------------------------------------------------------------------
  // The report and the epoch: written by software, kept across a reset
  // -------------------------------------------------------------------
  reg [31:0] brpt_q, epoch_q;
  always @(posedge clk_i or negedge rst_por_ni) begin
    if (!rst_por_ni) begin
      brpt_q  <= 32'h0;
      epoch_q <= 32'h0;
    end else begin
      if (wr && (paddr_i == REG_BRPT))  brpt_q  <= pwdata_i;
      if (wr && (paddr_i == REG_EPOCH)) epoch_q <= pwdata_i;
    end
  end

  // -------------------------------------------------------------------
  // Reads
  // -------------------------------------------------------------------
  // The limit as a vector of each width it is compared or reported at,
  // written once so no comparison below carries its own conversion.
  //
  // The part-selects are EXPLICIT rather than left to the assignment's
  // implicit truncation, because Verilator's WIDTHTRUNC is an error in
  // this repository's lint and an implicit narrowing of a parameter is
  // exactly the class of thing it is right to be loud about: a LIMIT
  // that did not fit in CNT_W bits would silently become a different
  // limit. It does not fit is now a thing a reader can see.
  localparam [CNT_W-1:0]  LIMIT_C  = LIMIT[CNT_W-1:0];
  localparam [7:0]        LIMIT_B  = LIMIT[7:0];
  localparam [3:0]        NSTRAP_B = NSTRAP[3:0];

  wire last_attempt = (cnt_q >= (LIMIT_C - {{(CNT_W-1){1'b0}}, 1'b1}));
  wire over_limit   = (cnt_q >= LIMIT_C);

  // Widened once so the read decode below is a plain concatenation, and
  // widened by assignment rather than by concatenation so that NSTRAP =
  // 16 or CNT_W = 8 does not ask for a zero-width replication.
  reg [15:0] strap_w;
  reg [7:0]  cnt_w;
  always @(*) begin
    strap_w = 16'h0;
    strap_w[NSTRAP-1:0] = strap_q;
    cnt_w = 8'h0;
    cnt_w[CNT_W-1:0] = cnt_q;
  end

  always @(*) begin
    case (paddr_i)
      // BSTRAP: the pins in the low half, the width and the two
      // one-shot flags in the high half.
      REG_BSTRAP: prdata_o = {valid_q, 3'h0, NSTRAP_B,
                              7'h0, wdis_q, strap_w};
      // BSTAT: the counter, the two derived flags a loader would
      // otherwise recompute, and the limit that is a constant of the
      // netlist.
      REG_BSTAT:  prdata_o = {8'h0, LIMIT_B,
                              6'h0, over_limit, last_attempt, cnt_w};
      REG_BRPT:   prdata_o = brpt_q;
      REG_EPOCH:  prdata_o = epoch_q;
      default:    prdata_o = 32'h0;
    endcase
  end

`ifdef FORMAL
`include "soc_boot_props.v"
`endif

endmodule

`default_nettype wire
