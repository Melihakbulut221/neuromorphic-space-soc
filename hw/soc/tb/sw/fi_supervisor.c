// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: Apache-2.0

// The SECOND workload of the core fault-injection campaign: a static
// partitioned supervisor, written to be what this project's software is
// actually going to be.
//
// =====================================================================
// WHY A SECOND WORKLOAD EXISTS AT ALL
// =====================================================================
//
// docs/43 section 12 item 5 states the open question this file is built
// to answer:
//
//   "A decision about W7, made from a second workload rather than from
//    this one. Section 8.4 measured its value on this program at zero
//    and its cost at seven spurious escalations and 4,904 um2. That is
//    one program. Before floorplanning, either a workload that produces
//    a fast runaway justifies keeping it, or it should be removed."
//
// docs/43 section 4.3 is why one program was not enough. `fi_workload.c`
// kicks the watchdog from six places inside a round, wherever the code
// happens to pass, and measures a kick-interval ratio of 57.2 -- which
// fits inside no window at all. Rewritten to kick once per round it
// measures 1.018. Neither number is a fact about realistic software;
// they are two facts about one small program written two ways.
//
// =====================================================================
// THE TRAP THIS FILE HAD TO AVOID, STATED BEFORE ANYTHING ELSE
// =====================================================================
//
// A workload written with W7 in mind -- kicking on a regular cadence
// because its author knows a window is watching -- measures its author's
// intentions and proves nothing. So this program is written against what
// the software is going to be, and the watchdog is placed where the
// argument in "WHERE THE KICK GOES" below puts it. THAT SECTION WAS
// WRITTEN BEFORE THE PROGRAM WAS FIRST BUILT AND BEFORE ANY CADENCE WAS
// MEASURED, and it has not been edited since. That is a claim about
// process and the only evidence for it is this branch's history;
// docs/46 section 4 says so where it quotes the decision.
//
// =====================================================================
// WHAT THE SOFTWARE IS GOING TO BE
// =====================================================================
//
// docs/09 part B track 3 chose option S2 and described it:
//
//   "a static partitioned bare-metal supervisor in the style of the
//    Microkit static architecture -- fixed set of tasks ('protection
//    domains'), fixed communication channels, no dynamic allocation
//    after init, event-driven loop. M-mode supervisor ~1-2 kSLOC C;
//    tasks in U-mode with PMP regions as the isolation mechanism."
//
// This program is a small, honest instance of that:
//
//   * four partitions, a static schedule, no dynamic allocation;
//   * partitions run in U-MODE and are isolated by PMP, with the region
//     that describes a partition's private memory reprogrammed on every
//     switch -- which is the actual per-dispatch cost of the isolation
//     mechanism S2 chose;
//   * a periodic frame tick from CLINT mtimecmp, which is the one time
//     base with an architectural meaning (soc_clint.v's header);
//   * partitions run to completion and return by `ecall`; a partition
//     that faults is terminated and the supervisor carries on;
//   * partitions of deliberately unequal length, doing data-dependent
//     work on a variable-length message, so the frame's execution time
//     is not a constant;
//   * only the supervisor touches the watchdog. The partitions cannot:
//     PMP does not give U-mode the peripheral bus, so there is exactly
//     one place in the whole program that kicks.
//
// It satisfies the two Ibex constraints this repository has already paid
// for. docs/38 section 7.5 defect 3: mtvec is 256-byte aligned and
// vectored-only, so the vector table in sup_crt0.S is a 32-entry table
// on a 256-byte boundary and link_soc.ld asserts both. Defect 4: the
// reset vector is fixed at {boot_addr_i[31:8], 8'h80} and the image
// origin is not free, so `_start` is asserted onto it by the same
// script.
//
// WHAT IT IS NOT. It is not the S2 supervisor. It has no channels
// between partitions, no driver model, no error-recovery policy and no
// MISRA or Frama-C evidence, and it is about 400 lines rather than
// docs/09's 1-2 kSLOC. It is the smallest program that has the
// STRUCTURE S2 will have -- privilege switches, PMP reprogramming, a
// frame tick, unequal data-dependent partitions -- because it is that
// structure, and not the arithmetic inside a partition, that determines
// a kick cadence.
//
// =====================================================================
// WHERE THE KICK GOES  --  the decision, made before any measurement
// =====================================================================
//
// The kick is issued ONCE PER FRAME, IN THE SUPERVISOR, IMMEDIATELY
// AFTER THE LAST PARTITION IN THE STATIC SCHEDULE HAS RETURNED.
//
// Four placements are available to a supervisor of this shape, and the
// argument for the one chosen is an argument about what a kick asserts.
//
//   (a) IN THE TICK HANDLER, once per tick. Rejected. It decouples the
//       kick from the work: a system in which every partition has
//       deadlocked still takes its timer interrupt, so the watchdog goes
//       on being petted by a machine that has stopped doing anything.
//       This is the classic watchdog anti-pattern and it is rejected on
//       that ground alone, not on any ground to do with a window.
//
//   (b) IN THE IDLE PATH, whenever the supervisor has nothing to do.
//       Rejected. It asserts that the supervisor reached its idle loop,
//       which is a statement about the supervisor and not about the
//       system; and a system that is never idle never kicks, so the
//       watchdog fires hardest exactly when the machine is busiest.
//
//   (c) ONCE PER PARTITION, at each partition's return. Rejected, for
//       two reasons. It asserts less -- "some partition ran" rather than
//       "the schedule completed" -- and it multiplies the number of
//       places in the program that touch the watchdog by the number of
//       partitions, which is the wrong direction for a block whose whole
//       argument (soc_wdog.v W5, docs/40 section 5.6) is that a runaway
//       must not be able to pet it by accident.
//
//   (d) ONCE PER FRAME, AFTER EVERY PARTITION HAS RUN AND RETURNED.
//       CHOSEN. It is the strongest statement the supervisor can make
//       from evidence it actually holds: every partition in the static
//       schedule was dispatched, ran, and returned through the one exit
//       the architecture gives it. It is the "all partitions checked in
//       this frame" pattern that time-partitioned avionics supervisors
//       use, and it is the placement that makes the watchdog a progress
//       detector rather than a liveness detector for the timer.
//
// AND THE PART OF (d) THAT IS UNDER-DETERMINED, RECORDED HERE BECAUSE IT
// TURNED OUT TO MATTER. "Once per frame after every partition has
// returned" still admits two instants: at the moment the last partition
// returns, or at the top of the next frame gated on the previous frame
// having completed. Both are progress attestations. This file takes the
// FIRST, on the ground that a kick should be as close in time as
// possible to the evidence it attests: a kick issued at the top of the
// next frame attests work that finished up to a whole frame period ago,
// and if the machine dies in the idle gap the watchdog has already been
// petted for a frame that did complete. Minimising the staleness of the
// attestation is a reason that has nothing to do with any window, and it
// is the reason recorded here.
//
// It is worth being explicit that this choice does not flatter a window.
// The kick instant is tied to the WORK, so all of the frame's execution
// -time variation lands in the kick interval. The alternative instant is
// tied to the CLOCK and would produce a tighter cadence. docs/46 section
// 7 measures both, because a decision about W7 that rests on a placement
// the requirement does not determine is a decision that should say so.
//
// =====================================================================
// TWO DISPATCH DISCIPLINES, BOTH BUILDABLE, NEITHER CHOSEN FOR W7
// =====================================================================
//
// The supervisor is TIME-TRIGGERED by default: each frame opens on the
// tick and the supervisor idles in WFI between the end of one frame's
// work and the start of the next. That is the ordinary shape of a
// periodic spacecraft management loop and it is what a fixed frame
// budget means.
//
// -DSUP_FREERUN builds the same schedule WORK-TRIGGERED: the next frame
// starts the instant the previous one finished, with no idle. That is
// the other plausible reading of docs/09's "event-driven loop", and it
// is a fork docs/09 has not resolved.
//
// The two are not a workload and a variant of it written to get a
// number. They are the same partitions, the same schedule, the same kick
// placement and the same code, differing in one `wfi` -- and they bracket
// the kick cadence a real S2 supervisor could have.
//
// =====================================================================
// THE ORACLE AND THE SELF-CHECKS
// =====================================================================
//
// docs/42 section 3's discipline, unchanged. What decides right from
// wrong is an undeposited run of the same program on the same design;
// `fi_mask` says whether the program itself noticed, which is a weaker
// and different claim, and the campaign keeps them apart.
//
// Every self-check is a DUAL COMPUTATION and NOT ONE OF THEM COMPARES
// AGAINST A WRITTEN-DOWN CONSTANT -- docs/38 section 7.5 defect 1, where
// four hand-computed expected values were all wrong and all four were
// caught by the core being right.
//
// THE FOUR WORDS THE TESTBENCH READS are fi_workload.c's, unchanged, so
// hw/soc/tb/tb_soc_fi.v runs this program with no modification at all:
// `fi_phase` (0 before the measured window, 1 during, 2 after),
// `fi_sig`, `fi_mask` and `fi_rounds_done`, which here counts frames.

#include <stdint.h>

#include "soc_memmap.h"
#include "soc_timers.h"
#include "sup_config.h"

// GRLIB APBUART, grip.pdf table 126, the same offsets test_ibex.c and
// fi_workload.c use.
#define UART_DATA   (SOC_UART0_BASE + 0x00u)
#define UART_STATUS (SOC_UART0_BASE + 0x04u)
#define UART_CTRL   (SOC_UART0_BASE + 0x08u)
#define UART_SCALER (SOC_UART0_BASE + 0x0Cu)
#define UART_STATUS_TE (1u << 2)
#define UART_CTRL_TE   (1u << 1)

#ifndef UART_SCALER_VAL
#define UART_SCALER_VAL 0u
#endif

/* The cadence contract, soc_wdog.v W7 and W8. As in fi_workload.c this
 * is a SEPARATE BUILD and not a runtime option, because a program that
 * declares a contract and a program that does not are different
 * programs and docs/46 keeps their campaigns apart. */
#ifndef SUP_WIN_S
#define SUP_WIN_S 1u
#endif
#ifndef SUP_KICK_BUDGET
#define SUP_KICK_BUDGET (SUP_FRAMES + 2u)
#endif

/* THE TWO BOUNDS OF docs/43 SECTION 4.2, CHECKED AT BUILD TIME.
 *
 * A build that gets either of them wrong does not fail, it escalates in
 * a loop, and a program that resets in a loop is the failure docs/40
 * section 7.2 spent a section on. So a build that declares a contract
 * must state the MEASURED longest and shortest intervals between its
 * own kicks, and the timeout is checked against both:
 *
 *     T > i_max                     or a legitimate frame expires
 *     T * (1 - 2^-WINS) < i_min     or a legitimate kick is early
 *
 * There is deliberately NO DEFAULT. A default would be a number for one
 * dispatch discipline at one frame period, silently wrong for the other,
 * and a guard that is inert unless somebody remembers to arm it is a
 * guard that reads wider than it is -- which is the class of defect
 * docs/41 section 6.6 lists nine instances of. The measurement is
 * docs/46 section 5 and the numbers are passed on the command line.
 *
 * SUP_SWEEP TURNS BOTH GUARDS OFF, and exists for exactly one purpose:
 * docs/46 section 6.1 sweeps WINS across settings the guards refuse, in
 * order to MEASURE what a window set one notch too tight costs on a
 * healthy program. A guard is a bound and a sweep is the measurement of
 * it, and a document that could not build the rejected settings could
 * not show what they cost. It is not an escape hatch for a build that
 * is meant to run anything. */
#if defined(SUP_WINDOWED) && !defined(SUP_SWEEP)
#if !defined(SUP_KICK_MAX) || !defined(SUP_KICK_MIN)
#error "a windowed build must state its MEASURED kick interval: -DSUP_KICK_MIN=... -DSUP_KICK_MAX=... (docs/46 section 5)"
#endif
#if ((SUP_WDOG_RELOAD + 1u) * 16u) <= SUP_KICK_MAX
#error "the watchdog timeout is shorter than this program's longest measured interval between kicks -- raise SUP_WDOG_RELOAD"
#endif
#if (((SUP_WDOG_RELOAD + 1u) * 16u) - (((SUP_WDOG_RELOAD + 1u) * 16u) >> SUP_WIN_S)) >= SUP_KICK_MIN
#error "the window opens later than this program's shortest measured interval between kicks -- lower SUP_WIN_S or SUP_WDOG_RELOAD"
#endif
#endif

// ---------------------------------------------------------------------
// The four words tb_soc_fi.v reads. Not static: the flow resolves their
// addresses out of the ELF with `nm`.
// ---------------------------------------------------------------------
volatile uint32_t fi_phase;
volatile uint32_t fi_sig;
volatile uint32_t fi_mask;
volatile uint32_t fi_rounds_done;

// ---------------------------------------------------------------------
// From sup_crt0.S.
// ---------------------------------------------------------------------
extern uint32_t sup_dispatch(void (*entry)(uint32_t *), void *stack_top,
                             uint32_t *arg);
extern volatile uint32_t sup_tick_pending;
extern volatile uint32_t sup_fault;
extern uint32_t sup_ecalls;
extern uint32_t sup_ticks;
extern uint32_t sup_spurious_irqs;
extern uint32_t trap_count;

// ---------------------------------------------------------------------
// Partition memory.
//
// One naturally aligned block per partition, described to PMP in NAPOT
// form. The alignment is not cosmetic: a NAPOT region whose base is not
// naturally aligned does not encode a slightly wrong region, it encodes
// a much larger one, and a partition that could reach its neighbour's
// memory would make the isolation claim false without failing anything.
// link_soc.ld makes the same point about __pmp_buf.
//
// The low words are the partition's mailbox -- the supervisor writes the
// inputs and reads the outputs, in M-mode, which PMP does not restrict
// while the regions are unlocked. The rest is the partition's stack,
// growing down from the top of the block.
// ---------------------------------------------------------------------
#define MB_SEED   0u
#define MB_LEN    1u
#define MB_MSG    2u
#define MB_RESULT 3u
#define MB_FLAGS  4u
#define MB_WORK   8u          /* the partition's own work area starts here */

static uint8_t task_mem[SUP_NTASK][SUP_TASK_MEM]
    __attribute__((aligned(SUP_TASK_MEM)));

/* The frame's input message: written by the supervisor, READ-ONLY to
 * every partition. This is the "fixed communication channel" of the
 * static architecture, and making it read-only to U-mode is the point:
 * a partition cannot corrupt the input another partition is about to
 * read. 64 bytes, naturally aligned, for the same NAPOT reason. */
static uint32_t sup_msg[16] __attribute__((aligned(64)));

// ---------------------------------------------------------------------
static void uart_init(void) {
  *(volatile uint32_t *)UART_SCALER = UART_SCALER_VAL;
  *(volatile uint32_t *)UART_CTRL   = UART_CTRL_TE;
}

static void putc_(char c) {
  while (!(*(volatile uint32_t *)UART_STATUS & UART_STATUS_TE)) { }
  *(volatile uint32_t *)UART_DATA = (uint32_t)c;
}

static void puts_(const char *s) { while (*s) putc_(*s++); }

static void puthex(uint32_t v) {
  const char *d = "0123456789abcdef";
  for (int i = 28; i >= 0; i -= 4) putc_(d[(v >> i) & 0xfu]);
}

// The kick. Keyed, because soc_wdog.v W5 ignores every write that is
// not. THIS IS THE ONLY PLACE IN THE PROGRAM THAT WRITES A WATCHDOG
// REGISTER OTHER THAN THE ARMING SEQUENCE, and the only place a
// partition could not reach even if it tried.
static void wdog_kick(void) {
  *(volatile uint32_t *)WDOG_CTRL = WDOG_W(GPT_LD);
}

// ---------------------------------------------------------------------
// PMP.
//
// Three regions of the four Ibex is built with (soc_top.v,
// PMPNumRegions = 4):
//
//   0  the boot ROM, R+X. Every partition's code and every string
//      constant is in it, and nothing else in the map is executable.
//   1  the partition's own 1 KiB of RAM, R+W. REPROGRAMMED ON EVERY
//      DISPATCH -- this is the actual per-switch cost of choosing PMP as
//      the isolation mechanism.
//   2  the frame's input message, R only, shared by every partition.
//
// A U-mode access that matches nothing fails, so a partition can reach
// its own memory, the shared message and the code, and nothing else --
// not RAM outside its block, not another partition's block, and not the
// peripheral bus, which is what makes the watchdog unreachable from a
// partition.
//
// THE REGIONS ARE NOT LOCKED. The L bit would apply them to M-mode as
// well (test 10 of test_ibex.c records that PMP does not constrain
// M-mode at all without it), and the supervisor has to be able to read a
// partition's mailbox and write the next partition's region. That is a
// deliberate weakening and it is what "the supervisor is the TCB" means.
// ---------------------------------------------------------------------
#define PMP_R      0x01u
#define PMP_W      0x02u
#define PMP_X      0x04u
#define PMP_NAPOT  0x18u

#define CSRW(csr, v) __asm__ volatile ("csrw " #csr ", %0" :: "r"(v))

/* The NAPOT encoding of a naturally aligned block: the address field is
 * base >> 2 with the low log2(size)-3 bits set. Derived, not
 * transcribed -- test 10 of test_ibex.c writes the same expression for
 * its 64-byte buffer. */
static uint32_t napot(uint32_t base, uint32_t size) {
  return (base >> 2) | ((size >> 3) - 1u);
}

static void pmp_init(void) {
  CSRW(pmpaddr0, napot(SOC_ROM_BASE, SOC_ROM_SIZE));
  CSRW(pmpaddr1, napot((uint32_t)(uintptr_t)task_mem[0], SUP_TASK_MEM));
  CSRW(pmpaddr2, napot((uint32_t)(uintptr_t)sup_msg, sizeof sup_msg));
  CSRW(pmpcfg0, (uint32_t)((PMP_NAPOT | PMP_R | PMP_X)
                           | ((PMP_NAPOT | PMP_R | PMP_W) << 8)
                           | ((PMP_NAPOT | PMP_R) << 16)));
}

static void pmp_select(uint32_t t) {
  CSRW(pmpaddr1, napot((uint32_t)(uintptr_t)task_mem[t], SUP_TASK_MEM));
}

// ---------------------------------------------------------------------
// The frame tick.
//
// mtimecmp is 64 bits and the bus is 32, and soc_clint.v's header sets
// out the hazard and the architectural sequence for it. This program
// takes the shortcut that sequence exists to make unnecessary: MTIMECMPH
// is written ONCE, to zero, and never again, and the run is far shorter
// than 2^32 clocks, so the deadline only ever moves upward inside the
// low word and no intermediate value is ever below mtime. sup_crt0.S's
// tick handler writes MTIMECMPL alone for the same reason.
// ---------------------------------------------------------------------
static void tick_init(void) {
  uint32_t now = *(volatile uint32_t *)CLINT_MTIMEL;
  *(volatile uint32_t *)CLINT_MTIMECMPH = 0u;
  *(volatile uint32_t *)CLINT_MTIMECMPL = now + SUP_TICK_PERIOD;
  __asm__ volatile ("csrs mie, %0" :: "r"(MIE_MTIE));
  __asm__ volatile ("csrs mstatus, %0" :: "r"(MSTATUS_MIE));
}

static void wait_for_frame(void) {
#ifndef SUP_FREERUN
  while (!sup_tick_pending) { __asm__ volatile ("wfi"); }
  sup_tick_pending = 0u;
#endif
}

// =====================================================================
// The partitions.
//
// Four, deliberately unequal, all doing data-dependent work on a
// message whose length changes from frame to frame. Each one:
//
//   * reads its inputs from its own mailbox and the shared message,
//   * computes a result TWO STRUCTURALLY DIFFERENT WAYS and compares
//     them -- no expected constant appears anywhere,
//   * writes the result and a failure bit into its mailbox,
//   * and returns by `ecall`, which is the only exit U-mode has.
//
// A partition may not touch a global: PMP would fault it. That is the
// isolation working, and it is why every input arrives through the
// mailbox pointer the supervisor passes in a0.
// =====================================================================

#define F_T0     (1u << 0)
#define F_T1     (1u << 1)
#define F_T2     (1u << 2)
#define F_T3     (1u << 3)
#define F_FAULT  (1u << 8)    /* a partition faulted instead of returning */
#define F_ECALL  (1u << 9)    /* not every dispatch returned by ecall */
#define F_FRAME  (1u << 10)   /* the frame loop did not run its frames */
#define F_SPUR   (1u << 11)   /* an interrupt with no source in this SoC */
#define F_TRAP   (1u << 12)   /* the supervisor itself took an exception */

__attribute__((noreturn))
static void task_return(void) {
  for (;;) __asm__ volatile ("ecall");
}

/* Partition 0, "telemetry acquisition": the message summed forwards and
 * the same message summed backwards. Unsigned addition is associative
 * and commutative modulo 2^32, so the two agree exactly. The shortest
 * partition in the schedule. */
__attribute__((noreturn))
static void task0(uint32_t *m) {
  const uint32_t *msg = (const uint32_t *)(uintptr_t)m[MB_MSG];
  uint32_t n = m[MB_LEN], i, fwd = 0u, rev = 0u;

#ifdef SUP_PROVE_ISOLATION
  /* THE POSITIVE CONTROL ON THE ISOLATION, and it is not decoration.
   *
   * Every partition in the ordinary build touches only its own memory,
   * so an ordinary run would look exactly the same if PMP were not
   * enforcing anything at all -- the partitions would simply run in
   * U-mode with no region ever consulted. A green run therefore says
   * nothing about isolation, which is the same shape of defect as
   * campaign.py's control 4 (docs/42 section 5.1: the first version of
   * the testbench made every injection a no-op and the whole campaign
   * came back MASKED, which is what a healthy core looks like).
   *
   * So this build reads word 0 of RAM, which is below every region
   * granted to U-mode. It must fault. `sup_crt0.S` then terminates the
   * partition and the supervisor carries on, so the run completes with
   * F_FAULT and F_TRAP set and a nonzero trap count -- which is the
   * containment behaviour as well as the enforcement.
   *
   * docs/46 section 3.4 reports what it printed. */
  {
    const volatile uint32_t *outside = (const volatile uint32_t *)0u;
    fwd += *outside;
  }
#endif

  for (i = 0u; i < n; i++) fwd += msg[i];
  for (i = n; i-- > 0u; )  rev += msg[i];
  m[MB_RESULT] = fwd;
  m[MB_FLAGS]  = (fwd != rev) ? F_T0 : 0u;
  task_return();
}

/* Partition 1, "attitude control": a fixed-point accumulate over the
 * message, and one hardware multiply checked against a shift-and-add
 * loop -- RV32M against RV32I, which needs no constant. The shift-add
 * loop is a fixed cost on top of a message-length-dependent one. */
__attribute__((noreturn))
static void task1(uint32_t *m) {
  const uint32_t *msg = (const uint32_t *)(uintptr_t)m[MB_MSG];
  uint32_t n = m[MB_LEN], i, acc = m[MB_SEED];
  uint32_t a, b, hw, sw = 0u, fail = 0u;
  for (i = 0u; i < n; i++) acc = (acc << 1) + msg[i] * 3u;
  a = acc | 1u;
  b = msg[0] | 1u;
  hw = a * b;
  while (b) {
    if (b & 1u) sw += a;
    a <<= 1;
    b >>= 1;
  }
  if (hw != sw) fail = F_T1;
  m[MB_RESULT] = acc ^ hw;
  m[MB_FLAGS]  = fail;
  task_return();
}

/* Partition 2, "housekeeping": the divider against its own definition,
 * once per message word. q*d + r == n and r < d, with d forced nonzero
 * so this is the ordinary case and not the ISA-defined divide-by-zero
 * one. Division is multi-cycle, so this partition is long in proportion
 * to the message. */
__attribute__((noreturn))
static void task2(uint32_t *m) {
  const uint32_t *msg = (const uint32_t *)(uintptr_t)m[MB_MSG];
  uint32_t n = m[MB_LEN], i, sig = 0u, fail = 0u;
  for (i = 0u; i < n; i++) {
    uint32_t v = msg[i];
    uint32_t d = (v >> 16) | 1u;
    uint32_t q = v / d;
    uint32_t r = v % d;
    if ((q * d + r) != v) fail = F_T2;
    if (r >= d)           fail = F_T2;
    sig += q ^ r;
  }
  m[MB_RESULT] = sig;
  m[MB_FLAGS]  = fail;
  task_return();
}

/* Partition 3, "downlink framing": the message copied into the
 * partition's own work area a byte at a time with a checksum
 * accumulated as it goes, then read back as 32-bit words and the
 * checksum recomputed from those. A load/store unit that mislaid a byte
 * lane, or an address that lost a bit, breaks the agreement. The longest
 * partition in the schedule. */
__attribute__((noreturn))
static void task3(uint32_t *m) {
  const uint8_t *msg = (const uint8_t *)(uintptr_t)m[MB_MSG];
  uint8_t *work = (uint8_t *)&m[MB_WORK];
  uint32_t *word = &m[MB_WORK];
  uint32_t n = m[MB_LEN] * 4u, i, wr = 0u, rd = 0u;
  for (i = 0u; i < n; i++) {
    uint8_t v = msg[i];
    work[i] = v;
    wr = (wr << 1) + v;
  }
  for (i = 0u; i < n; i += 4u) {
    uint32_t w = word[i >> 2];
    rd = (rd << 1) + ((w >> 0) & 0xffu);
    rd = (rd << 1) + ((w >> 8) & 0xffu);
    rd = (rd << 1) + ((w >> 16) & 0xffu);
    rd = (rd << 1) + ((w >> 24) & 0xffu);
  }
  m[MB_RESULT] = wr;
  m[MB_FLAGS]  = (wr != rd) ? F_T3 : 0u;
  task_return();
}

static void (*const task_entry[SUP_NTASK])(uint32_t *) = {
  task0, task1, task2, task3
};

// ---------------------------------------------------------------------
static uint32_t lcg(uint32_t s) { return s * 1664525u + 1013904223u; }

/* The frame's input message. Its LENGTH is data-dependent -- one to
 * sixteen words -- because a telemetry or downlink partition processes a
 * variable-length packet and a supervisor whose partitions always did
 * exactly the same amount of work would be a supervisor with no
 * execution-time variation to measure. The span is the buffer, not a
 * number chosen to produce a jitter figure. */
static uint32_t fill_msg(uint32_t seed) {
  uint32_t n = 1u + (seed & 15u);
  uint32_t i, s = seed;
  for (i = 0u; i < 16u; i++) { s = lcg(s); sup_msg[i] = s; }
  return n;
}

// =====================================================================
int main(void) {
  uint32_t sig = 0x9e3779b9u;
  uint32_t mask = 0u;
  uint32_t seed = 0x13579bdfu;
  uint32_t f, t, n;

  uart_init();
  pmp_init();
  tick_init();

  /* ENTERING THE OPERATIONAL PHASE.
   *
   * The watchdog's reset default is the maximum timeout, 1,048,576
   * clocks (soc_wdog.v W1 and docs/40 section 5.7: a short default risks
   * a board whose boot is slower than its watchdog), and that is what
   * has been protecting everything above. The timeout is shortened HERE,
   * at the point the supervisor enters the phase whose cadence it
   * matches -- not at reset, because the boot cadence and the
   * operational cadence are different and one timeout cannot suit both.
   *
   * The kick immediately follows, because writing the reload does not
   * reload the counter; and the contract is declared immediately after
   * the kick, because docs/43 section 4.6 found by running it that a
   * window armed BEFORE a kick makes the very next kick early. */
  *(volatile uint32_t *)WDOG_RLD = WDOG_W(SUP_WDOG_RELOAD);
  wdog_kick();

#ifdef SUP_WINDOWED
  /* The budget is SUP_FRAMES + 2: this phase kicks once per frame and
   * that is SUP_FRAMES kicks, with two spare, so the contract is a
   * statement about the schedule's length and not a hair-trigger on the
   * exact count. docs/43 section 5.5 is what a kick budget is and is
   * not. */
  *(volatile uint32_t *)WDOG_WIN =
      WDOG_W(WDOG_WIN_WINS(SUP_WIN_S) | WDOG_WIN_BUDEN |
             WDOG_WIN_KICKS(SUP_KICK_BUDGET));
#endif

  /* The measured injection window opens here, at the start of the
   * operational phase and after the contract is in force, so every
   * injection the campaign draws lands in a machine running the schedule
   * under the contract. */
  fi_phase = 1u;

  for (f = 0u; f < SUP_FRAMES; f++) {
    /* The frame opens on the tick. In the free-running build this
     * returns immediately and the next frame starts the instant the
     * previous one finished. */
    wait_for_frame();

    seed = lcg(seed);
    n = fill_msg(seed);

    for (t = 0u; t < SUP_NTASK; t++) {
      uint32_t *m = (uint32_t *)(uintptr_t)task_mem[t];
      uint32_t before = sup_ecalls;

      m[MB_SEED]   = seed + t;
      m[MB_LEN]    = n;
      m[MB_MSG]    = (uint32_t)(uintptr_t)sup_msg;
      m[MB_RESULT] = 0u;
      m[MB_FLAGS]  = 0u;
      sup_fault    = 0u;

      /* The isolation, reprogrammed for this partition, and the
       * privilege switch into it. */
      pmp_select(t);
      (void)sup_dispatch(task_entry[t], &task_mem[t][SUP_TASK_MEM], m);

      if (sup_fault)              mask |= F_FAULT;
      else if (sup_ecalls == before) mask |= F_ECALL;

      sig = (sig << 1) ^ m[MB_RESULT];
      mask |= (m[MB_FLAGS] & (F_T0 | F_T1 | F_T2 | F_T3));
    }

    fi_sig = sig;
    fi_rounds_done = f + 1u;

    /* THE KICK. Every partition in this frame's static schedule has been
     * dispatched, has run, and has returned through the one exit U-mode
     * gives it. See "WHERE THE KICK GOES". */
    wdog_kick();
  }

  if (fi_rounds_done != SUP_FRAMES) mask |= F_FRAME;
  if (sup_ecalls != SUP_FRAMES * SUP_NTASK) mask |= F_ECALL;
  if (sup_spurious_irqs) mask |= F_SPUR;
  if (trap_count) mask |= F_TRAP;

  /* And the window closes here, before anything is read back or
   * printed. A deposit drawn after this point would land after the
   * program's answer was already fixed -- docs/41 section 8.4 records
   * that exact defect presenting as a design result. */
  fi_phase = 2u;

  fi_sig  = sig;
  fi_mask = mask;

  /* Deliberately NOT printed: the tick count, the frame execution times,
   * or anything else that a purely temporal perturbation would move. The
   * console stream is part of what the campaign compares against the
   * golden run (docs/42 section 5), and a program that published its own
   * timing would turn every displaced cycle into a wrong answer. */
  puts_("S");
  puthex(sig);
  puts_("M");
  puthex(mask);
  puts_("\n");

  return (int)mask;
}
