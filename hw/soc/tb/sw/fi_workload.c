// The workload the core fault-injection campaign of docs/42 runs.
//
// WHY THIS IS NOT test_ibex.c
//
// `hw/soc/tb/sw/test_ibex.c` is the bring-up program of docs/38, docs/39
// and docs/40. It is 22 checks, 185,443 cycles on the SoC, and it traps
// on purpose four times. All three properties are wrong for a campaign
// that runs the program hundreds of times and treats a trap as an
// announcement:
//
//   * 185,443 cycles is about 50 s of Icarus per injection. A campaign
//     of 480 injections run twice would be a fortnight.
//   * a program that traps on purpose cannot use "an unexpected trap
//     happened" as a detection channel, because the classifier would
//     have to know which traps were meant.
//   * its checks are wide but shallow in time: most of the run is
//     console output, and an upset drawn uniformly in it lands in the
//     UART wait loop far more often than in anything interesting.
//
// So this is a separate, deliberately short, deliberately dense
// workload. It is NOT a replacement for test_ibex.c and nothing here
// should be read as re-running the bring-up suite.
//
// WHAT IT IS
//
// A fixed number of rounds. Each round exercises, on data it derives
// itself, the structures the campaign strata are drawn over: the
// register file (deep expression trees and a recursive call), the
// fetch path (a data-dependent loop), the controller (branches and
// calls), the load/store unit (byte, half and word accesses at every
// alignment), the multiplier and divider (RV32M in both directions),
// and the machine CSRs (a read-modify-write of mscratch). The watchdog
// is kicked several times inside every round, so the interval between
// kicks stays well under the timeout the program arms and the clean run
// never escalates.
//
// THE SELF-CHECKS CARRY NO EXTERNAL CONSTANTS, ON PURPOSE
//
// docs/38 section 7.5 defect 1 records four hand-computed expected
// values in the bring-up program, all four wrong, all four caught by
// the core being right. A campaign program that carried a table of
// expected results would carry the same risk with nobody to catch it.
//
// Every check here is therefore a DUAL COMPUTATION: the same quantity
// derived two structurally different ways, compared against each other.
// A sum forwards against a sum backwards; a hardware multiply against a
// shift-and-add loop; a hardware divide against its own reconstruction
// q*d + r; a recursive Fibonacci against an iterative one; a checksum
// accumulated while writing memory against one computed by reading it
// back at a different access width. None of them can be wrong in the
// way a transcribed constant can be wrong, and each of them fails if
// exactly one of its two computations is disturbed.
//
// This is a DETECTION channel and not the oracle. What decides right
// from wrong is the golden run -- docs/42 section 3. `fail_mask` says
// whether the program itself noticed, which is a different and weaker
// question, and the campaign keeps the two apart.
//
// THE THREE WORDS THE TESTBENCH READS
//
//   fi_phase  0 before the measured kernel, 1 during it, 2 after. The
//             testbench records the cycle of each transition and the
//             campaign draws its injection cycles inside [1, 2). The
//             window is therefore MEASURED from the clean run rather
//             than assumed, which is docs/41 section 8.1's last
//             honesty clause.
//   fi_sig    a 32-bit signature folding every intermediate result of
//             every round. It is the program's answer.
//   fi_mask   which self-checks failed. Zero in the clean run.
//
// They are also printed on the console, so the same three facts reach
// the testbench by two independent paths -- a hierarchical read of RAM
// and a decode of the UART pin. tb_soc.v's pass criterion 4 makes the
// same argument.

#include <stdint.h>

#include "soc_memmap.h"
#include "soc_timers.h"

// GRLIB APBUART, grip.pdf table 126, the same offsets test_ibex.c uses.
#define UART_DATA   (SOC_UART0_BASE + 0x00u)
#define UART_STATUS (SOC_UART0_BASE + 0x04u)
#define UART_CTRL   (SOC_UART0_BASE + 0x08u)
#define UART_SCALER (SOC_UART0_BASE + 0x0Cu)
#define UART_STATUS_TE (1u << 2)
#define UART_CTRL_TE   (1u << 1)

#ifndef UART_SCALER_VAL
#define UART_SCALER_VAL 0u
#endif

// The watchdog timeout this program arms, in the block's own arithmetic:
// (RELOAD + 1) * WDOG_PRESCALE clocks, and soc_top.v instantiates
// WDOG_PRESCALE = 16. At 127 that is 2,048 clocks to stage 1 and 4,096
// to stage 2.
//
// The reset default is the MAXIMUM, 65,535, or 1,048,576 clocks
// (soc_wdog.v W1 and docs/40 section 5.7: a short default risks a board
// whose boot is slower than its watchdog). That protects the boot path
// of every run in this campaign, injected or not: this program
// has the whole of it to reach the write below. Shortening it here is
// what makes the escalation ladder observable inside a campaign run at
// all -- at the reset default a single ladder is longer than the
// simulation budget and the campaign could not tell "the watchdog did
// not fire" from "the watchdog had not got there yet".
#ifndef FI_WDOG_RELOAD
#define FI_WDOG_RELOAD 127u
#endif

/* ---- the windowed variant, docs/43 ---------------------------------
 *
 * FI_WINDOWED builds the same kernel under soc_wdog.v's W7 cadence
 * contract and W8 kick budget. It is a SEPARATE BUILD and not a runtime
 * option because it changes the program, and docs/43 keeps the two
 * campaigns apart for exactly that reason: campaign A runs this file
 * with FI_WINDOWED off, which is byte-for-byte the docs/42 workload, so
 * the register-file result is measured with the software held fixed.
 *
 * WHY THE KICKS HAD TO MOVE. Measured on the unmodified program: 25
 * kicks in the window, shortest interval 30 clocks, longest 1,716 --
 * a jitter ratio of 57. W7 with WINS = 1 permits 2. The ordinary way to
 * use a watchdog -- kick wherever the code happens to pass -- cannot
 * live inside any window at all, and that is a real cost of W7 and not
 * a defect of this program.
 *
 * So the windowed build kicks EXACTLY ONCE PER ROUND, at the top of the
 * round, and nowhere else. The interval is then one round of the kernel
 * and its jitter is whatever the kernel's own data-dependent branching
 * produces -- which is what a program written to live inside a window
 * has to look like, and which docs/43 section 4 measures.
 */
#ifdef FI_WINDOWED
#define ROUND_KICK() do { } while (0)
#else
#define ROUND_KICK() wdog_kick()
#endif

/* The window bound and the kick budget the windowed build declares.
 * Both are chosen FROM THE MEASURED cadence of this program, in
 * docs/43 section 4, and neither is a round number picked to look
 * tidy. */
#ifndef FI_WIN_S
#define FI_WIN_S 1u
#endif
#ifndef FI_KICK_BUDGET
#define FI_KICK_BUDGET (FI_ROUNDS + 2u)
#endif

/* MEASURED, not assumed: with the in-round kicks removed this program
 * issues five kicks in the run and the intervals between them are
 * 4,094 clocks at the shortest and 4,164 at the longest -- a jitter
 * ratio of 1.017 (docs/43 section 4, from the clean run's own record).
 *
 * W7 then bounds the timeout T = (RELOAD + 1) * WDOG_PRESCALE from both
 * sides:
 *
 *     T > g_max                       or a legitimate round expires
 *     T * (1 - 2^-WINS) < g_min       or a legitimate kick is early
 *
 * At WINS = 1 that is 4,164 < T < 8,188, and FI_WDOG_RELOAD = 383 puts
 * T at 6,144 -- 33 % above the lower bound and 33 % below the upper.
 * The lower guard is checked here because the build that gets it wrong
 * does not fail, it resets in a loop, and a program that resets in a
 * loop is the failure docs/40 section 7.2 spent a section on.
 */
#ifdef FI_WINDOWED
#if ((FI_WDOG_RELOAD + 1u) * 16u) <= 4164u
#error "windowed build: the watchdog timeout is shorter than this program's longest measured interval between kicks -- raise FI_WDOG_RELOAD"
#endif
#endif

// Rounds of the measured kernel, and the depth of the recursion inside
// one. Sized so the clean run is short enough to multiply by a campaign
// and long enough that the kernel, and not the boot path or the
// console, is most of the injection window.
#ifndef FI_ROUNDS
#define FI_ROUNDS 4
#endif
#ifndef FI_FIB_N
#define FI_FIB_N 8u
#endif

#define ARRAY_N 12
#define BUF_N   24

// -------------------------------------------------------------------
// The three words the testbench reads. Not static: the flow resolves
// their addresses out of the ELF with `nm`, exactly as sim_soc.sh
// resolves exit_code and exit_magic, so no address is written twice.
// -------------------------------------------------------------------
volatile uint32_t fi_phase;
volatile uint32_t fi_sig;
volatile uint32_t fi_mask;
volatile uint32_t fi_rounds_done;

#ifdef FI_BUSSTAT
/* docs/44 section 8.2. The whole point of BUSSTAT is that SOFTWARE can
 * see a corrected upset, so the demonstration has to be a load
 * instruction executed by the core and not a hierarchical read by the
 * testbench. These four words are what the program saw; tb_soc_fi.v
 * prints them beside the bench's own hierarchical count of the same
 * events, and docs/44 section 8.2 is the two columns agreeing.
 *
 * It is behind an #ifdef because the unwindowed build's ROM image is
 * BYTE-IDENTICAL to docs/42's and campaign A's whole claim to being a
 * paired comparison rests on that. Four more words of .bss and four
 * more loads would break it.
 */
volatile uint32_t fi_bst_sec;
volatile uint32_t fi_bst_rd;
volatile uint32_t fi_bst_ded;
volatile uint32_t fi_bst_tmr;
#endif

// The buffer the load/store round works in. In .bss, so crt0 zeroes it
// on every boot and a re-run after a watchdog reset starts from the
// same memory the first run did.
static uint8_t buf[BUF_N];

// -------------------------------------------------------------------
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
// not -- a runaway core cannot pet this watchdog by accident.
static void wdog_kick(void) {
  *(volatile uint32_t *)WDOG_CTRL = WDOG_W(GPT_LD);
}

// -------------------------------------------------------------------
// The kernel. Every function here is deliberately not inlined so the
// call path, the stack and the register-save convention are part of
// what runs.
// -------------------------------------------------------------------

static uint32_t lcg(uint32_t s) { return s * 1664525u + 1013904223u; }

__attribute__((noinline))
static uint32_t fib_rec(uint32_t n) {
  if (n < 2u) return n;
  return fib_rec(n - 1u) + fib_rec(n - 2u);
}

__attribute__((noinline))
static uint32_t fib_iter(uint32_t n) {
  uint32_t a = 0u, b = 1u;
  for (uint32_t i = 0u; i < n; i++) { uint32_t t = a + b; a = b; b = t; }
  return a;
}

// Multiply without the multiplier: shift and add. The comparison against
// `a * b` is a check on RV32M against RV32I, and it needs no constant.
__attribute__((noinline))
static uint32_t mul_sw(uint32_t a, uint32_t b) {
  uint32_t p = 0u;
  while (b) {
    if (b & 1u) p += a;
    a <<= 1;
    b >>= 1;
  }
  return p;
}

// Bit numbers in fi_mask. One per self-check, so a failure says which.
#define F_SUM   (1u << 0)
#define F_MUL   (1u << 1)
#define F_DIV   (1u << 2)
#define F_FIB   (1u << 3)
#define F_MEM   (1u << 4)
#define F_CSR   (1u << 5)
#define F_ROUND (1u << 6)   // the loop did not run the rounds it should

__attribute__((noinline))
static uint32_t round_once(uint32_t seed, uint32_t *mask) {
  uint32_t a[ARRAY_N];
  uint32_t sig = seed;
  uint32_t s = seed;
  uint32_t i;

  for (i = 0u; i < ARRAY_N; i++) { s = lcg(s); a[i] = s; }

  // 1. A sum forwards and the same sum backwards. Unsigned addition is
  //    associative and commutative modulo 2^32, so these agree exactly.
  {
    uint32_t fwd = 0u, rev = 0u;
    for (i = 0u; i < ARRAY_N; i++)      fwd += a[i];
    for (i = ARRAY_N; i-- > 0u; )       rev += a[i];
    if (fwd != rev) *mask |= F_SUM;
    sig ^= fwd;
    ROUND_KICK();
  }

  // 2. The multiplier against a shift-and-add loop.
  {
    uint32_t hw = a[0] * a[1];
    uint32_t sw = mul_sw(a[0], a[1]);
    if (hw != sw) *mask |= F_MUL;
    sig = (sig << 1) ^ hw;
    ROUND_KICK();
  }

  // 3. The divider against its own definition. d is forced nonzero, so
  //    this is not the divide-by-zero case -- that is an ISA-defined
  //    result and this check is about the ordinary one.
  {
    uint32_t n = a[2];
    uint32_t d = (a[3] | 1u);
    uint32_t q = n / d;
    uint32_t r = n % d;
    if ((q * d + r) != n) *mask |= F_DIV;
    if (r >= d)           *mask |= F_DIV;
    sig += q ^ r;
    ROUND_KICK();
  }

  // 4. Recursion against iteration. The recursive side is 67 calls at
  //    FI_FIB_N = 8, which is what puts the return-address path and the
  //    stack in the run.
  {
    uint32_t fr = fib_rec(FI_FIB_N);
    uint32_t fi = fib_iter(FI_FIB_N);
    if (fr != fi) *mask |= F_FIB;
    sig ^= fr * 3u;
    ROUND_KICK();
  }

  // 5. Memory at three widths. The buffer is written as bytes with a
  //    checksum accumulated as it goes, then read back as half words
  //    and words and the checksum recomputed from those. A load/store
  //    unit that mislaid a byte lane, or an address that lost a bit,
  //    breaks the agreement.
  {
    uint32_t wr = 0u, rd = 0u;
    for (i = 0u; i < BUF_N; i++) {
      uint8_t v = (uint8_t)(a[i % ARRAY_N] >> (i & 7u));
      buf[i] = v;
      wr = (wr << 1) + v;
    }
    for (i = 0u; i < BUF_N; i += 2u) {
      uint16_t h;
      __builtin_memcpy(&h, &buf[i], sizeof h);
      rd = (rd << 1) + (uint32_t)(h & 0xffu);
      rd = (rd << 1) + (uint32_t)(h >> 8);
    }
    if (wr != rd) *mask |= F_MEM;

    // And once more through 32-bit accesses, which take a different
    // path through the byte-enable decode.
    {
      uint32_t rw = 0u;
      for (i = 0u; i < BUF_N; i += 4u) {
        uint32_t w;
        __builtin_memcpy(&w, &buf[i], sizeof w);
        rw = (rw << 1) + ((w >> 0) & 0xffu);
        rw = (rw << 1) + ((w >> 8) & 0xffu);
        rw = (rw << 1) + ((w >> 16) & 0xffu);
        rw = (rw << 1) + ((w >> 24) & 0xffu);
      }
      if (rw != wr) *mask |= F_MEM;
    }
    sig ^= wr;
    ROUND_KICK();
  }

  // 6. A machine CSR round trip. mscratch has no architectural side
  //    effect, which is why the ISA provides it and why it is the one
  //    to use: writing anything else would change the machine.
  {
    uint32_t back;
    __asm__ volatile ("csrw mscratch, %0" :: "r"(sig));
    __asm__ volatile ("csrr %0, mscratch" : "=r"(back));
    if (back != sig) *mask |= F_CSR;
    sig += back >> 3;
  }

  return sig;
}

// -------------------------------------------------------------------
int main(void) {
  uint32_t sig = 0x9e3779b9u;
  uint32_t mask = 0u;
  uint32_t r;

  // FIRST, before anything else, arm the short timeout. On a boot that
  // follows a watchdog reset the reload has been restored to the
  // maximum (docs/40 section 7.2), so this write is what makes the
  // second and later ladders as short as the first.
  *(volatile uint32_t *)WDOG_RLD = WDOG_W(FI_WDOG_RELOAD);
  wdog_kick();

  uart_init();

#ifdef FI_WINDOWED
  // The cadence contract, declared before the phase it applies to and
  // after the kick above, so the first kick inside the contract is a
  // full round away. W7's window is a fraction of the period, so
  // arming it mid-period cannot close it retrospectively.
  //
  // The budget is FI_ROUNDS + 2: this phase kicks once per round and
  // that is FI_ROUNDS kicks, with two spare so that the contract is a
  // statement about the loop bound and not a hair-trigger on the exact
  // count. Under docs/42 section 8.1's corrupted `x23` the loop does
  // not terminate, so the kicks do not stop, so the budget is spent and
  // the block escalates -- which is the whole reason W8 exists and is
  // measured rather than asserted in docs/43 section 5.
  *(volatile uint32_t *)WDOG_WIN =
      WDOG_W(WDOG_WIN_WINS(FI_WIN_S) | WDOG_WIN_BUDEN |
             WDOG_WIN_KICKS(FI_KICK_BUDGET));
#endif

  // The measured window opens here.
  fi_phase = 1u;

  for (r = 0u; r < FI_ROUNDS; r++) {
    sig = round_once(sig + r, &mask);
    fi_sig = sig;
    fi_rounds_done = r + 1u;
    // The one kick the windowed build keeps, and the sixth of six the
    // unwindowed build has. It stays exactly here in both, so that the
    // FI_WINDOWED-off build is the program docs/42 measured down to the
    // instruction order -- campaign A of docs/43 compares against that
    // campaign draw by draw and would not be entitled to if the
    // software had moved. Verified rather than argued: the two builds
    // produce a byte-identical ROM image when FI_WINDOWED is off.
    wdog_kick();
  }

  if (fi_rounds_done != FI_ROUNDS) mask |= F_ROUND;

  // And closes here, before anything is read back or printed. A deposit
  // drawn after this point would land after the program's answer was
  // already fixed. docs/41 section 8.4 records that exact defect
  // presenting as a design result.
  fi_phase = 2u;

  fi_sig = sig;
  fi_mask = mask;

#ifdef FI_BUSSTAT
  /* Read AFTER fi_phase = 2, so the answer is already fixed and these
   * loads cannot be mistaken for part of the computation. */
  fi_bst_sec = *(volatile uint32_t *)BST_RFSEC;
  fi_bst_rd  = *(volatile uint32_t *)BST_RFRD;
  fi_bst_ded = *(volatile uint32_t *)BST_RFDED;
  fi_bst_tmr = *(volatile uint32_t *)BST_TMRERR;
#endif

  puts_("S");
  puthex(sig);
  puts_("M");
  puthex(mask);
  puts_("\n");

  // crt0.S posts this in exit_code beside the exit magic and sleeps.
  return (int)mask;
}
