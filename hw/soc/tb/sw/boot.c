// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: Apache-2.0

/* The boot loader, docs/68.
 *
 * =====================================================================
 * WHAT THIS PROGRAM IS
 * =====================================================================
 *
 * It is what lives in the boot ROM from docs/68 onward, and it is the
 * answer to four questions that docs/47, docs/58, docs/66 and docs/67
 * each left open and that turn out to be one design:
 *
 *   1. HOW THE ROM GETS CONTENTS. docs/68 section 3 decides that the
 *      flight part's boot ROM is a mask-programmed array holding a
 *      loader and nothing else, and that the 8 KiB SRAM macro pair this
 *      PDK forces is a STAND-IN for it. This file is what the mask
 *      would hold: it is small, it is fixed at tape-out, and it can
 *      never be patched -- which is the whole reason the APPLICATION
 *      must live somewhere that can be.
 *
 *   2. HOW THE RAM GETS CHECK BITS. docs/67 protects every row of the
 *      RAM with SECDED, and an SRAM powers up undefined: a word nothing
 *      has written is an UNCORRECTABLE and a bus error, not a zero.
 *      boot_crt0.S sweeps every WORD of the RAM before anything else
 *      runs, and this file checks that the sweep's bounds were the
 *      map's.
 *
 *   3. WHAT THE BOOTSTRAP PINS AND THE BOOT REPORT ARE. soc_boot.v, in
 *      the BOOTREG slot the map has reserved since docs/39.
 *
 *   4. WHAT HAPPENS WHEN BOOT FAILS. Section "the escalation" below.
 *
 * =====================================================================
 * THE ORDER, AND WHY IT IS THIS ORDER
 * =====================================================================
 *
 *   boot_crt0.S  mtvec, then THE RAM SWEEP, then the stack, then .data.
 *                Nothing that reads RAM may run before the sweep.
 *   boot_main    the console, the boot report from the last boot, the
 *                straps, the attempt limit, then for each of the two
 *                image slots in the flash: the header, the geometry,
 *                the copy, the READ-BACK verify, and the jump.
 *
 * THE CHECKSUM IS COMPUTED FROM THE RAM AND NOT FROM THE FLASH. The
 * copy loop writes what the controller delivered; the verify loop reads
 * those words BACK OUT OF THE RAM and sums them. That is deliberate and
 * it is the difference between checking the flash read and checking the
 * image: a word that arrived intact and landed on a row whose codeword
 * did not take is caught by the second and invisible to the first. It
 * is also what makes an uncorrectable in the loaded image a REPORTED
 * boot failure rather than the application's first mysterious fault --
 * the read-back is where the codec would raise it, boot_crt0.S's
 * synchronous handler records it, and this file turns it into
 * BOOT_CAUSE_ECC and moves to the other image.
 *
 * =====================================================================
 * THE ESCALATION, AND WHY IT IS THE WATCHDOG'S AND NOT A NEW ONE
 * =====================================================================
 *
 * docs/40 W1: the watchdog is armed at reset, cannot be disabled by
 * software, and its longest timeout is a constant of the netlist. A
 * loader that retried for ever would be reset by it. That is not a
 * problem to work around -- IT IS THE ESCALATION, and this loader uses
 * it rather than building a second one:
 *
 *   within a boot   two image slots. The primary is tried; if its
 *                   header, its geometry, its checksum or its ECC fails
 *                   the secondary is tried. GR716B validates an image
 *                   "optionally from redundant memories" (docs/08
 *                   section 2.4) and this is that at this part's scale.
 *
 *   across boots    BOOTREG.BSTAT.CNT counts boots and NO SOFTWARE CAN
 *                   WRITE IT. Both slots failing means the loader
 *                   shortens the watchdog to its minimum, stops
 *                   kicking, and is reset. The next boot reads a
 *                   counter one higher.
 *
 *   the end         BSTAT.LIMIT boots. The limit is three and it is a
 *                   parameter of soc_boot.v, chosen so that the LAST
 *                   boot the loader attempts is one during which the
 *                   watchdog has ALREADY asserted its external pin
 *                   (soc_top.v's WDOG_ESCALATE = 2). Software gives up
 *                   after the hardware has told the platform, never
 *                   before. Past the limit the loader does not touch
 *                   the flash at all: it reports, and stops kicking,
 *                   and the part resets with WDOGN asserted and
 *                   BOOTREG carrying why.
 *
 * WHY IT IS NOT "WAIT FOR AN UPLOAD". GR716B's boot flow has a standby
 * mode that waits for a remote boot over SpaceWire, CAN, UART, SPI or
 * I2C. THIS PART HAS NO INGRESS CHANNEL AT ALL -- the console UART is
 * transmit-only (docs/39) and nothing else is built -- so there is
 * nothing to wait for, and a loader that waited would be a hang with a
 * good name. Handing the decision to the platform is the only terminal
 * state this part can offer, and docs/68 section 6 says what changes
 * the day an ingress channel exists.
 *
 * SHORTENING THE WATCHDOG ON THE WAY OUT IS SAFE, and it is worth
 * saying why, because docs/40 section 7.2 is a document about a short
 * reload that was not. That reload survived the reset it caused,
 * because the watchdog's state is in the power-on domain, and the SoC
 * bricked. The fix docs/40 made is that A STAGE-2 RESET RESTORES THE
 * RELOAD TO THE MAXIMUM -- so a short reload lasts exactly until the
 * reset it is there to hasten, and the next boot gets the whole budget.
 * This loader shortens it only on a path from which the only exit is
 * that reset.
 */

#include <stdint.h>

#include "soc_memmap.h"
#include "soc_timers.h"
#include "soc_qspi.h"
#include "soc_scrub.h"
#include "soc_boot.h"
#include "boot_image.h"     /* generated by flow/gen_boot_image.py */

#ifndef UART_SCALER_VAL
#define UART_SCALER_VAL 0u
#endif

#define UART_DATA   (SOC_UART0_BASE + 0x00u)
#define UART_STATUS (SOC_UART0_BASE + 0x04u)
#define UART_CTRL   (SOC_UART0_BASE + 0x08u)
#define UART_SCALER (SOC_UART0_BASE + 0x0Cu)
#define UART_STATUS_TE (1u << 2)
#define UART_CTRL_TE   (1u << 1)

/* Written by boot_crt0.S's synchronous trap handler. VOLATILE for
   test_ibex.c's reason: the handler is code the compiler cannot see, so
   a value it wrote is one the compiler is entitled to have cached. */
extern volatile uint32_t boot_fault_cause, boot_fault_pc, boot_fault_count;

/* From link_boot.ld. Used only to check that the sweep boot_crt0.S ran
   actually covered the loader's own .bss and stack, which is the one
   part of the sweep's correctness a C program can still observe. */
extern char __bss_start[], __boot_stack_top[], __boot_private[];

static inline uint32_t rd(uint32_t a) { return *(volatile uint32_t *)a; }
static inline void wr(uint32_t a, uint32_t v) { *(volatile uint32_t *)a = v; }

static void putc_(char c) {
  while (!(rd(UART_STATUS) & UART_STATUS_TE)) { }
  wr(UART_DATA, (uint32_t)c);
}
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void puthex(uint32_t v) {
  const char *d = "0123456789abcdef";
  putc_('0'); putc_('x');
  for (int i = 28; i >= 0; i -= 4) putc_(d[(v >> i) & 0xf]);
}

/* ---- the watchdog ---------------------------------------------------
 *
 * KICK ON PROGRESS, NOT ON A SCHEDULE. The copy loop calls this once
 * every BOOT_KICK_WORDS words it has actually moved, so a loop that is
 * moving words keeps the watchdog satisfied and a loop that is stuck
 * does not. A kick on a timer, or a kick at the top of the loop
 * whatever happened inside it, would be a loader keeping the watchdog
 * fed from inside its own failure -- which is precisely what docs/40
 * section 5.4 refuses for the stage-1 handler ("a stage-1 handler that
 * kicked would let a program that does nothing else keep the watchdog
 * satisfied from inside its own failure"). */
#define BOOT_KICK_WORDS 256u

static void wdog_kick(void) { wr(WDOG_CTRL, WDOG_W(GPT_LD)); }

/* ---- how long each phase took -------------------------------------
 *
 * soc_top.v instantiates the CLINT at TICK_DIV = 1, so one mtime tick
 * is one system clock and the low half of mtime is a cycle counter that
 * starts at zero on every system reset. The loader takes five readings
 * and prints the four differences once, at the end, so that the cost of
 * a boot is ATTRIBUTABLE rather than a single number -- which matters
 * because two of the four phases scale with the RAM and two with the
 * image, and a mission sizing either would otherwise have to guess.
 *
 * Only the low 32 bits are read. A boot that took 2^32 clocks is a boot
 * the watchdog ended a very long time ago. */
static uint32_t cyc(void) { return rd(CLINT_MTIMEL); }

static uint32_t t_entry, t_open, t_hdr, t_copy, t_verify;

/* The give-up path. Shorten the watchdog to a timeout that is still
   long enough for the console to drain, load it, and then spin without
   kicking. Nothing here can be undone by a corrupted store afterwards:
   the loader is not going to execute anything else. */
#define BOOT_GIVEUP_RELOAD 2000u

static void boot_give_up(void) {
  puts_("boot: giving up; the watchdog will reset this part\n");
  /* Drain the transmitter before shortening anything. */
  while (!(rd(UART_STATUS) & UART_STATUS_TE)) { }
  wr(WDOG_RLD, WDOG_W(BOOT_GIVEUP_RELOAD));
  wr(WDOG_CTRL, WDOG_W(GPT_LD));
  for (;;) { }
}

/* ---- the flash ------------------------------------------------------
 *
 * The same register-mode driver docs/66 section 7 wrote for the
 * bring-up program, at the size a loader needs. Every wait is bounded:
 * an unbounded wait against a flash that is not answering is a hang,
 * and a hang is the one failure this loader may not have -- it has to
 * REPORT "the flash did not answer" and move to the other image.
 */
#define QSPI_SPIN 20000

static int qspi_wait(uint32_t mask) {
  for (int i = 0; i < QSPI_SPIN; i++)
    if (rd(QSPI_STAT) & mask) return 1;
  return 0;
}

static int qspi_read(uint32_t cmdw, uint32_t addr, uint32_t *out, int n) {
  int ok = 1;
  wr(QSPI_ADDR, addr);
  wr(QSPI_CMD, cmdw | QSPI_CMD_LEN(n));
  for (int w = 0; w < (n + 3) / 4; w++) {
    ok &= qspi_wait(QSPI_ST_DR);
    out[w] = rd(QSPI_RX);
  }
  ok &= qspi_wait(QSPI_ST_DONE);
  wr(QSPI_STAT, QSPI_ST_DONE);
  return ok;
}

static int qspi_cmd(uint32_t op, uint32_t txw, int n) {
  if (n) wr(QSPI_TX, txw);
  wr(QSPI_CMD, QSPI_CMD_OP(op) | QSPI_CMD_WRITE | QSPI_CMD_LEN(n));
  int ok = qspi_wait(QSPI_ST_DONE);
  wr(QSPI_STAT, QSPI_ST_DONE);
  return ok;
}

/* Quad I/O needs the part's QE bit, which is not set out of a power
   cycle (W25Q128JV datasheet 4.3). The volatile status write (50h then
   31h) is used rather than the non-volatile one for the reason a loader
   cares about: it takes effect immediately, costs the part no write
   cycle, and is undone by the next power cycle, so a loader that ran
   once does not change the part it found. */
static int flash_open(uint32_t cs) {
  uint32_t id = 0;
  wr(QSPI_CONF, QSPI_CONF_DIV(0) | QSPI_CONF_CS(cs));
  wr(QSPI_CTRL, 0);
  wr(QSPI_STAT, QSPI_ST_DONE | QSPI_ST_LOST);
  if (!qspi_read(QSPI_CMD_OP(FLASH_OP_JEDEC), 0, &id, 3)) return 0;
  if (id != FLASH_JEDEC_WORD) {
    puts_("boot: jedec "); puthex(id); putc_('\n');
    return 0;
  }
  if (!qspi_cmd(FLASH_OP_VWREN, 0, 0)) return 0;
  if (!qspi_cmd(FLASH_OP_WRSR2, FLASH_SR2_QE, 1)) return 0;
  uint32_t sr2 = 0;
  if (!qspi_read(QSPI_CMD_OP(FLASH_OP_RDSR2), 0, &sr2, 1)) return 0;
  return (sr2 & FLASH_SR2_QE) != 0;
}

/* ---- one image slot -------------------------------------------------
 *
 * Returns 1 and writes *entry_out, or 0 with *cause saying why not.
 *
 * IT DOES NOT RETURN THE ENTRY POINT AS ITS RESULT, and that is a
 * defect this file had and a simulation found. The application is
 * linked to the base of the RAM (link_app.ld), so its entry point is
 * ZERO -- and a function that returns "the entry point, or 0 for
 * failure" reports every successful boot of it as a failure. The first
 * whole-SoC run of this loader rejected a perfectly good image with
 * `cause 0x00000000`, which is BOOT_CAUSE_OK, and the contradiction in
 * that line is what pointed at the sentinel. A sentinel value inside
 * the range of the thing it is a sentinel for is the bug; the fix is
 * that success is its own bit.
 */
static int try_image(uint32_t off, uint32_t *cause, uint32_t *entry_out) {
  uint32_t hdr[BOOT_IMG_WORDS];

  *cause = BOOT_CAUSE_TIMEOUT;
  *entry_out = 0;
  if (!qspi_read(FLASH_CMD_QIO, off, hdr, BOOT_IMG_BYTES)) return 0;

  if (hdr[BOOT_IMG_W_MAGIC] != BOOT_IMG_MAGIC) {
    *cause = BOOT_CAUSE_MAGIC;
    return 0;
  }

  /* The eight header words sum to zero. One comparison, no constant. */
  uint32_t hsum = 0;
  for (int i = 0; i < BOOT_IMG_WORDS; i++) hsum += hdr[i];
  if (hsum != 0u) {
    *cause = BOOT_CAUSE_HDRCSUM;
    return 0;
  }

  uint32_t load  = hdr[BOOT_IMG_W_LOAD];
  uint32_t bytes = hdr[BOOT_IMG_W_BYTES];
  uint32_t entry = hdr[BOOT_IMG_W_ENTRY];

  /* THE GEOMETRY CHECK, and it is not a formality. `load` and `bytes`
     come out of a flash that this loader has just decided it cannot
     fully trust, and they are about to be used as a destination. Four
     things have to hold and each one is a way to destroy the machine
     that is checking:
       - the image is word-aligned and a whole number of words, or the
         copy writes partial words and leaves check bits uninitialised
         in the middle of the image (the whole hazard again);
       - it is not empty;
       - it lies inside the RAM region AND BELOW __boot_private, so the
         copy cannot overwrite this loader's own stack while it runs;
       - the entry point is inside the part of RAM the image occupies. */
  uint32_t priv = (uint32_t)(uintptr_t)__boot_private;
  /* The lower bound on `load` is not written: SOC_RAM_BASE is zero on
     this map and an unsigned comparison against it is vacuous, which
     -Wtype-limits says out loud. It is the map's property and not this
     loader's assumption -- regmap/generate_memmap.py refuses a RAM base
     that is not naturally aligned, and moving it would make this a real
     comparison that the compiler would then keep. */
  int geom_ok = ((load & 3u) == 0u) && ((bytes & 3u) == 0u)
             && (bytes != 0u)
             && (bytes <= priv - SOC_RAM_BASE)
             && (load <= priv - bytes)
             && (entry >= load) && (entry < load + bytes);
  if (!geom_ok) {
    *cause = BOOT_CAUSE_GEOM;
    puts_("boot: geometry load="); puthex(load);
    puts_(" bytes="); puthex(bytes);
    puts_(" entry="); puthex(entry); putc_('\n');
    return 0;
  }

  t_hdr = cyc();

  /* ---- the copy ----------------------------------------------------
     One quad I/O frame for the whole body, pulled through the
     controller's one-word DR pause. Every word is a WHOLE-WORD store,
     which is what makes the destination row's four byte codewords all
     valid; docs/68 section 4. */
  volatile uint32_t *dst = (volatile uint32_t *)(uintptr_t)load;
  uint32_t nwords = bytes >> 2;

  wr(QSPI_ADDR, off + BOOT_IMG_BYTES);
  wr(QSPI_CMD, FLASH_CMD_QIO | QSPI_CMD_LEN(bytes));
  for (uint32_t w = 0; w < nwords; w++) {
    if (!qspi_wait(QSPI_ST_DR)) { *cause = BOOT_CAUSE_TIMEOUT; return 0; }
    dst[w] = rd(QSPI_RX);
    if ((w & (BOOT_KICK_WORDS - 1u)) == (BOOT_KICK_WORDS - 1u)) wdog_kick();
  }
  if (!qspi_wait(QSPI_ST_DONE)) { *cause = BOOT_CAUSE_TIMEOUT; return 0; }
  wr(QSPI_STAT, QSPI_ST_DONE);
  wdog_kick();
  t_copy = cyc();

  /* ---- the verify, READ BACK OUT OF THE RAM ------------------------
     See the header. A word whose row is not a codeword answers with a
     bus error here, boot_crt0.S records it, and the count is what
     separates BOOT_CAUSE_ECC from BOOT_CAUSE_CSUM. */
  uint32_t faults0 = boot_fault_count;
  uint32_t sum = 0;
  for (uint32_t w = 0; w < nwords; w++) {
    sum += dst[w];
    if ((w & (BOOT_KICK_WORDS - 1u)) == (BOOT_KICK_WORDS - 1u)) wdog_kick();
  }
  wdog_kick();

  t_verify = cyc();

  if (boot_fault_count != faults0) {
    *cause = BOOT_CAUSE_ECC;
    puts_("boot: fault cause="); puthex(boot_fault_cause);
    puts_(" pc="); puthex(boot_fault_pc); putc_('\n');
    return 0;
  }
  if (sum != hdr[BOOT_IMG_W_CSUM]) {
    *cause = BOOT_CAUSE_CSUM;
    puts_("boot: csum "); puthex(sum);
    puts_(" want "); puthex(hdr[BOOT_IMG_W_CSUM]); putc_('\n');
    return 0;
  }

  /* And the codec's own opinion, which is independent of the checksum:
     SCRUB counts a CORRECTED read too, and a corrected read during a
     boot means an upset was already sitting in a row this loader just
     wrote. It is not a failure -- the word was repaired and the sum is
     right -- so it is reported and not acted on. docs/68 section 9. */
  uint32_t ded = rd(SCR_RAMDED);
  if (ded != 0u) { puts_("boot: ramded "); puthex(ded); putc_('\n'); }

  *cause = BOOT_CAUSE_OK;
  *entry_out = entry;
  return 1;
}

/* ---------------------------------------------------------------------
 * boot_main
 * ------------------------------------------------------------------- */
uint32_t boot_main(void) {
  uint32_t strap, stat, cnt, limit, wstat, last_rpt;
  uint32_t cause = BOOT_CAUSE_GIVEUP;
  uint32_t entry = 0;

  /* Taken FIRST, before the console exists: everything before this
     point is boot_crt0.S -- the RAM sweep and the .data relocation --
     and it is the phase that scales with the size of the RAM rather
     than with the size of the image. */
  t_entry = cyc();

  wr(UART_SCALER, UART_SCALER_VAL);
  wr(UART_CTRL, UART_CTRL_TE);

  strap    = rd(BOOT_BSTRAP);
  stat     = rd(BOOT_BSTAT);
  wstat    = rd(WDOG_STAT);
  last_rpt = rd(BOOT_BRPT);
  cnt      = BOOT_STAT_CNT(stat);
  limit    = BOOT_STAT_LIMIT(stat);

  puts_("boot: strap "); puthex(strap);
  puts_(" cnt "); puthex(cnt);
  puts_(" of "); puthex(limit);
  puts_(" stat "); puthex(stat);
  puts_(" wdog "); puthex(wstat);
  puts_(" rpt "); puthex(last_rpt);
  /* docs/69's TMR replica report. It is counted in hardware, sticky and
     saturating, and until 2026-09-14 nothing outside the testbench read
     it -- so a voter that had corrected an upset said so to no one. Two
     words on the banner is the whole fix. */
  puts_(" tmr "); puthex(BOOT_STAT_TMRCNT(stat));
  if (stat & BOOT_STAT_TMRERR) puts_(" TMRERR");
  putc_('\n');

  /* THE EPOCH. mtime is in the system reset domain and a stage-2 reset
     zeroes it, so every boot is a new epoch whether anything asked for
     one or not. Incrementing this word here is what makes two readings
     of mtime taken in different epochs distinguishable; docs/58 section
     5.2 is the recovery it belongs to and soc_boot.v's header is why it
     is a bare counter and not a copy of the clock. */
  wr(BOOT_EPOCH, rd(BOOT_EPOCH) + 1u);

  /* The sweep's own witness. boot_crt0.S swept [RAM_BASE, RAM_TOP) and
     this loader's .bss and stack are inside it; reading them at all is
     only possible because it did. Checking the bounds here rather than
     trusting them is cheap and it is the only part of the sweep a C
     program can still see, because by the time C runs the evidence of
     an unswept word is a bus error and not a value. */
  if ((uint32_t)(uintptr_t)__boot_stack_top
      > SOC_RAM_BASE + SOC_RAM_SIZE
      || (uint32_t)(uintptr_t)__bss_start
         < (uint32_t)(uintptr_t)__boot_private) {
    puts_("boot: the loader's RAM is outside the swept region\n");
    boot_give_up();
  }

  /* THE SCRUB RECORD THE POWER-UP ITSELF CAUSED, and this is a finding
     rather than a tidy-up. docs/44 section 11's rule is that the
     scrubbers ship ENABLED, so soc_mem_ecc.v's RAM scrubber starts
     walking on the first idle cycle after reset -- across a memory that
     boot_crt0.S has not swept yet. Every row it reaches first reads as
     an uncorrectable, because that is what an uninitialised protected
     word IS, and SCRUB.CNT_RAMDED counts it. Those are not upsets and
     an operator reading them as upsets would be reading the boot as a
     radiation event.

     So the loader clears the RAM sources -- ONCE, on the power-on boot
     only. On any later boot the RAM was initialised by the previous
     one, the scrubber can no longer manufacture a count, and the record
     is a record: clearing it there would destroy exactly the evidence
     docs/44 built the counters for. The ROM's three counters are never
     touched, because nothing here ever writes the ROM.

     The window this leaves is stated rather than closed: an upset in
     the first few tens of thousands of cycles after power-on, before
     this clear, is lost. Nothing is running in that window. */
  if (cnt == 0u) {
    uint32_t sec = rd(SCR_RAMSEC), rdc = rd(SCR_RAMRD), ded = rd(SCR_RAMDED);
    if (sec || rdc || ded) {
      puts_("boot: scrub saw the uninitialised RAM: sec "); puthex(sec);
      puts_(" rd "); puthex(rdc);
      puts_(" ded "); puthex(ded);
      puts_(" -- clearing\n");
      wr(SCR_CLR, SCR_S_RAMSEC | SCR_S_RAMRD | SCR_S_RAMDED);
    }
  }

  /* Two counters that must agree on this SoC, reported together so that
     the day they do not is visible. soc_boot.v's header says why there
     are two. */
  if (WDOG_ST_RSTCNT(wstat) != cnt) {
    puts_("boot: bootcnt "); puthex(cnt);
    puts_(" != wdog rstcnt "); puthex(WDOG_ST_RSTCNT(wstat));
    putc_('\n');
  }

#ifdef BOOT_GIVEUP_DEMO
  /* THE DEMONSTRATION BUILD, and it exists for docs/40 section 6.2's
     reason stated one level up: the escalation is only reachable from
     software that has SEEN the ladder complete and there is no other
     way to reach it from inside a loader that works. This build refuses
     every image until the WATCHDOG HAS ASSERTED ITS EXTERNAL PIN --
     WDOGSTAT.ESCALATED, which is the platform having been told -- and
     then boots normally, so that the run terminates through the
     application's own exit and the whole ladder is in one log. It is
     zero in every normal build and this branch does not exist in one. */
  if (!(wstat & WDOG_ST_ESCALATED)) {
    puts_("boot: giveup demo, refusing the flash\n");
    wr(BOOT_BRPT, BOOT_RPT(BOOT_CAUSE_NOFLASH, 0xF,
                           WDOG_ST_RSTCNT(wstat), cnt));
    boot_give_up();
  }
  puts_("boot: giveup demo, the pin is asserted; booting\n");
  /* And the NOBOOT strap is released with it, so that the same demo
     build terminates whichever reason it was refusing for. */
  strap &= ~(uint32_t)BOOT_STRAP_NOBOOT;
#endif

  /* ---- past the limit: report and hand the decision outside -------- */
  if (stat & BOOT_STAT_OVER) {
    puts_("boot: attempt limit reached, not touching the flash\n");
    wr(BOOT_BRPT, BOOT_RPT(BOOT_CAUSE_GIVEUP, 0xF,
                           WDOG_ST_RSTCNT(wstat), cnt));
    boot_give_up();
  }

  /* ---- the NOBOOT strap ------------------------------------------- */
  if (strap & BOOT_STRAP_NOBOOT) {
    puts_("boot: NOBOOT strap; staying in the ROM\n");
    wr(BOOT_BRPT, BOOT_RPT(BOOT_CAUSE_NOBOOT, 0xF,
                           WDOG_ST_RSTCNT(wstat), cnt));
    /* A BOUNDED monitor, and the bound is a decision. A strap that
       parked the part in a kick loop for ever would be software holding
       a spacecraft in a state no operator can leave; the pin says "do
       not boot", not "never escalate". So the loader keeps the part
       alive long enough for a bench to see the console and then takes
       the same exit every other failure takes. The day this part has an
       ingress channel -- a UART receiver, SpaceWire -- this is where
       GR716B's standby mode goes and the bound goes away. */
    for (int i = 0; i < BOOT_NOBOOT_TICKS; i++) {
      puts_("boot: idle\n");
      wdog_kick();
    }
    boot_give_up();
  }

  /* ---- the flash --------------------------------------------------- */
  uint32_t cs = BOOT_STRAP_SRC(strap);
  if (!flash_open(cs)) {
    puts_("boot: no flash on cs "); puthex(cs); putc_('\n');
    wr(BOOT_BRPT, BOOT_RPT(BOOT_CAUSE_NOFLASH, 0xF,
                           WDOG_ST_RSTCNT(wstat), cnt));
    boot_give_up();
  }
  wdog_kick();
  t_open = cyc();

  /* ---- the two slots ----------------------------------------------- */
  static const uint32_t slot[2] = { BOOT_IMG0_OFF, BOOT_IMG1_OFF };
  uint32_t which = 0xF;
  int loaded = 0;
  for (uint32_t i = 0; i < 2u; i++) {
    puts_("boot: image "); puthex(i);
    puts_(" at "); puthex(slot[i]); putc_('\n');
    loaded = try_image(slot[i], &cause, &entry);
    if (loaded) { which = i; break; }
    puts_("boot: image "); puthex(i);
    puts_(" rejected, cause "); puthex(cause); putc_('\n');
  }

  if (!loaded) {
    wr(BOOT_BRPT, BOOT_RPT(cause, 0xF, WDOG_ST_RSTCNT(wstat), cnt));
    boot_give_up();
  }

  /* The report is written BEFORE the jump, not after: after the jump
     this loader does not run again, and a report written by the
     application would be the application's opinion of its own boot. */
  wr(BOOT_BRPT, BOOT_RPT(BOOT_CAUSE_OK, which,
                         WDOG_ST_RSTCNT(wstat), cnt));
  wdog_kick();

  /* The four phases, printed once. Each is in system clocks, because
     TICK_DIV = 1 (soc_top.v) makes an mtime tick one clock. `sweep` is
     boot_crt0.S's RAM initialisation and .data relocation, measured
     from reset; the other three are this file's. */
  puts_("boot: cycles sweep="); puthex(t_entry);
  puts_(" open="); puthex(t_open - t_entry);
  puts_(" hdr="); puthex(t_hdr - t_open);
  puts_(" copy="); puthex(t_copy - t_hdr);
  puts_(" verify="); puthex(t_verify - t_copy);
  putc_('\n');

  puts_("boot: entering "); puthex(entry); putc_('\n');
  return entry;
}
