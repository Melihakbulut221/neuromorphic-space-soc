// Ibex bring-up self-test.
//
// This is the "prove it fetches and executes" program from the CPU
// bring-up gate. It is self-checking: every test either passes or
// changes the exit code, and the exit code is a bitmask so a failing
// run names which checks failed rather than only that something did.
//
// What each group is here to prove, in the order a doubt would arise:
//
//   1  the core fetches and runs straight-line code at all
//   2  RV32I ALU, including the shift and comparison corners
//   3  RV32M -- mul/mulh/div/rem. RV32M = RV32MFast in this
//      configuration, so these are the multi-cycle sequencer, not a
//      single-cycle array
//   4  loads and stores at all three widths, including sign extension
//      and unaligned-in-word byte lanes, against the testbench's
//      byte-enable decode
//   5  taken and not-taken branches, and a data-dependent loop
//   6  calls, returns and the stack -- recursion to a depth the
//      compiler cannot inline away
//   7  RV32C: the build is -march=rv32imc and this function is compiled
//      with compression on, so if the decoder did not implement C the
//      program would fault long before here. The check makes that
//      explicit by verifying a value computed inside a compressed
//      region AND asserting the code really is compressed, by
//      inspecting its own instruction stream
//   8  CSR read/write on mscratch, and mcycle advancing
//   9  traps: a deliberate illegal instruction reaches the handler with
//      mcause = 2
//  10  PMP enforcement. This is the one that matters for docs/09 part B
//      track 3 option S2, which makes PMP the isolation mechanism of the
//      supervisor: a locked read-only NAPOT region must permit a load
//      and fault a store, in M-mode, with mcause = 7.
//
// Test 10 is skipped, not failed, when the core is built with
// PMPEnable = 0 -- the C code cannot tell, so the build passes
// -DHAVE_PMP to say which core it is running on.

// Two platforms, one program (see crt0.S). Without SOC_PLATFORM this is
// the docs/38 bring-up program against the minimal testbench memory, and
// its behaviour is unchanged to the byte. With -DSOC_PLATFORM the same
// eleven checks run against the real fabric and the frozen memory map of
// docs/39-soc-bus-and-memory-map.md -- code fetched from the boot ROM,
// data in RAM, console output through a real UART on the peripheral bus
// -- and three further checks (12, 13, 14) exercise things that only
// exist there.
//
// Keeping one program rather than forking it is the point: if the eleven
// original checks pass on the SoC, they passed through the bus and the
// map rather than around them.

#include <stdint.h>

#ifdef SOC_PLATFORM
#include "soc_memmap.h"
#include "soc_timers.h"

// GRLIB APBUART register offsets and bits (grip.pdf table 126, adopted
// by docs/08 section 3 row 9 and implemented as a subset in
// hw/soc/rtl/soc_uart.v).
#define UART_DATA   (SOC_UART0_BASE + 0x00u)
#define UART_STATUS (SOC_UART0_BASE + 0x04u)
#define UART_CTRL   (SOC_UART0_BASE + 0x08u)
#define UART_SCALER (SOC_UART0_BASE + 0x0Cu)
#define UART_STATUS_TE (1u << 2)      /* transmit holding register empty */
#define UART_CTRL_TE   (1u << 1)      /* transmitter enable              */

// The divider the testbench's serial decoder assumes. Both come from the
// same -D on the compiler and the simulator command lines
// (hw/soc/flow/sim_soc.sh), so they cannot disagree.
#ifndef UART_SCALER_VAL
#define UART_SCALER_VAL 0u
#endif

static void uart_init(void) {
  *(volatile uint32_t *)UART_SCALER = UART_SCALER_VAL;
  *(volatile uint32_t *)UART_CTRL   = UART_CTRL_TE;
}

// Poll before writing. The minimal testbench's character port accepted a
// byte every cycle; a real UART does not, and a driver that ignores that
// drops most of its output. This is the only behavioural difference the
// eleven original checks see.
static void putc_(char c) {
  while (!(*(volatile uint32_t *)UART_STATUS & UART_STATUS_TE)) { }
  *(volatile uint32_t *)UART_DATA = (uint32_t)c;
}
#else
#define PUTC_ADDR 0x00100000u
#define HALT_ADDR 0x00100004u

static void putc_(char c) { *(volatile uint32_t *)PUTC_ADDR = (uint32_t)c; }
#endif

extern uint32_t trap_mcause, trap_mepc, trap_count, trap_saw_rvc;
/* Written by the vector stubs in crt0.S. irq_marker says which VECTOR
   the core entered at; irq_mcause says which interrupt the core believes
   it took. Comparing them is what makes a wrong vector visible.

   VOLATILE, and that word is load-bearing. These are written by a
   handler the compiler cannot see, so a wait loop spinning on one of
   them is a loop on a value the compiler is entitled to cache in a
   register -- and it does, at -Os. The first version of this file
   declared them plain and every wait loop below ran to its iteration
   limit before the check that follows read the true value: three tests
   failed on their timeout bound while reporting exactly the right cause
   and vector, and one of them spun long enough for the watchdog's stage
   2 to reset the SoC underneath it. */
extern volatile uint32_t irq_marker, irq_mcause, irq_count, nmi_count;
extern char __pmp_buf[];
extern char trap_vectors[];

static void puts_(const char *s) { while (*s) putc_(*s++); }

static void puthex(uint32_t v) {
  const char *d = "0123456789abcdef";
  putc_('0'); putc_('x');
  for (int i = 28; i >= 0; i -= 4) putc_(d[(v >> i) & 0xf]);
}

static uint32_t fails = 0;
static uint32_t checks = 0;

// Every test reports, pass or fail. A test that hangs is then located
// by the last line printed, instead of by bisecting the source: the
// first run of this program stopped after one FAIL line and the log
// could not say which of the seven following tests had hung.
static void check(int n, int ok) {
  checks++;
  puts_(ok ? "  ok   test " : "  FAIL test ");
  puthex((uint32_t)n);
  putc_('\n');
  if (!ok) fails |= (1u << n);
}

// ---- 3: RV32M, kept out of the constant folder ----------------------
static volatile int32_t  m_a = -1234567, m_b = 7654321;
static volatile uint32_t m_ua = 0xdeadbeefu, m_ub = 0x01234567u;

// ---- 6: recursion ---------------------------------------------------
static uint32_t __attribute__((noinline)) fib(uint32_t n) {
  return (n < 2) ? n : fib(n - 1) + fib(n - 2);
}

// ---- 7: compressed instructions -------------------------------------
static uint32_t __attribute__((noinline, aligned(4)))
compressed_sum(uint32_t n) {
  uint32_t s = 0;
  for (uint32_t i = 0; i <= n; i++) s += i;
  return s;
}

// ---- 9/10: faulting instructions, forced 32-bit so the handler's
//            "skip 4" is right --------------------------------------
// 0xFFFFFFFF, not 0x00000000. Both are illegal instructions, but the
// low two bits of 0x00000000 are 2'b00, which is the encoding for a
// COMPRESSED instruction -- it is c.unimp, a legal 16-bit illegal
// instruction. The trap handler decides how far to advance mepc by
// looking at those two bits, so on 0x00000000 it advanced by 2, landed
// on the second half of the same zero word, faulted again, and the run
// became an unbounded trap loop that showed up as double_fault_seen_o
// plus a timeout. 0xFFFFFFFF has low bits 2'b11 (a 32-bit instruction)
// and opcode 7'b1111111, which is reserved and decodes to
// illegal_insn in ibex_decoder.sv's default arm.
static void do_illegal(void) {
  __asm__ volatile(".option push\n.option norvc\n"
                   ".word 0xffffffff\n"
                   ".option pop\n" ::: "memory");
}

#if defined(HAVE_PMP) || defined(SOC_PLATFORM)
// Test 10 (PMP) and test 14 (store into the boot ROM) both need a store
// that is guaranteed 32-bit, so the trap handler's "skip 4" is right.
// -Werror makes an unused static function an error, which is the wanted
// behaviour: it says the guard around the caller and the guard around
// the callee have to agree.
static void do_store(volatile uint32_t *p, uint32_t v) {
  __asm__ volatile(".option push\n.option norvc\n"
                   "sw %1, 0(%0)\n"
                   ".option pop\n" :: "r"(p), "r"(v) : "memory");
}
#endif

#ifdef SOC_PLATFORM
// Same, for a load. Test 12 needs the fault to come from a load rather
// than a store so that it can tell mcause 5 (load access fault) from
// mcause 7, which test 10 already produces for a different reason.
static uint32_t do_load(volatile uint32_t *p) {
  uint32_t v;
  __asm__ volatile(".option push\n.option norvc\n"
                   "lw %0, 0(%1)\n"
                   ".option pop\n" : "=r"(v) : "r"(p) : "memory");
  return v;
}
#endif

#define CSRR(name)      ({ uint32_t v_; __asm__ volatile ("csrr %0, " #name : "=r"(v_)); v_; })
#define CSRW(name, v)   __asm__ volatile ("csrw " #name ", %0" :: "r"(v))
#define CSRS(name, v)   __asm__ volatile ("csrs " #name ", %0" :: "r"(v) : "memory")
#define CSRC(name, v)   __asm__ volatile ("csrc " #name ", %0" :: "r"(v) : "memory")

#ifdef SOC_PLATFORM
/* ---- CLINT access helpers ------------------------------------------
   Both sequences are the ones soc_clint.v's header states, and both
   exist because a 64-bit register on a 32-bit bus passes through an
   intermediate value that is neither the old one nor the new one. */

/* Read: high, low, high again, and retry while the two highs differ, so
   the pair never straddles a carry out of bit 31. Bounded, because an
   unbounded retry against a broken CLINT is a hang and a hang says
   nothing. */
static uint64_t clint_mtime(void) {
  for (int i = 0; i < 8; i++) {
    uint32_t hi = *(volatile uint32_t *)CLINT_MTIMEH;
    uint32_t lo = *(volatile uint32_t *)CLINT_MTIMEL;
    uint32_t hi2 = *(volatile uint32_t *)CLINT_MTIMEH;
    if (hi == hi2) return ((uint64_t)hi << 32) | lo;
  }
  return 0;   /* caller's monotonicity check turns this into a failure */
}

/* Write: an unreachable low half first, so no intermediate value of the
   pair is a deadline that is already met and no spurious timer interrupt
   can appear between the stores. */
static void clint_set_mtimecmp(uint64_t v) {
  *(volatile uint32_t *)CLINT_MTIMECMPL = 0xFFFFFFFFu;
  *(volatile uint32_t *)CLINT_MTIMECMPH = (uint32_t)(v >> 32);
  *(volatile uint32_t *)CLINT_MTIMECMPL = (uint32_t)v;
}

static void csr_set_mie(uint32_t m)     { CSRS(mie, m); }
static uint32_t csr_read_mie(void)      { return CSRR(mie); }
static uint32_t csr_read_mip(void)      { return CSRR(mip); }
static void csr_set_mstatus(uint32_t m) { CSRS(mstatus, m); }
static void csr_clr_mstatus(uint32_t m) { CSRC(mstatus, m); }
static uint32_t csr_read_mstatus(void)  { return CSRR(mstatus); }
static uint32_t csr_read_mtvec(void)    { return CSRR(mtvec); }
#endif

#if defined(SOC_PLATFORM) && defined(WDOG_RESET_DEMO)
extern volatile uint32_t nmi_no_ack;

/* The watchdog escalation ladder, end to end on the real SoC.
 *
 * Stage 1 is reachable from an ordinary program and test 21 above takes
 * it. Stages 2 and 3 are not: they only happen when software has SEEN
 * the stage-1 warning and failed to act on it, which is exactly the
 * condition a working program cannot produce. So this build has one
 * extra behaviour -- the NMI handler is told not to acknowledge -- and
 * everything else about the SoC is identical.
 *
 * The run is THREE BOOTS of the same image, and the thing that carries
 * information between them is the watchdog's own status register, which
 * is in the power-on reset domain and therefore survives the resets the
 * watchdog causes (soc_wdog.v W4). RAM does not carry it: crt0.S zeroes
 * .bss on every boot, so every variable this program has is gone. If
 * WDOGSTAT were reset by the reset it generates, this program could not
 * tell a watchdog reset from a power cycle and would loop forever --
 * which is precisely the operator-facing failure W4 exists to prevent.
 *
 *   boot 1  RSTCNT 0: arm short, refuse to acknowledge, hang.
 *           -> stage 1 (NMI), then stage 2 (system reset).
 *   boot 2  RSTCNT 1, WDOGRST set, ESCALATED clear: same again.
 *           -> stage 1, stage 2, and RSTCNT reaches ESCALATE = 2.
 *   boot 3  RSTCNT 2, WDOGRST set, ESCALATED set: report and stop.
 */
static int wdog_demo(void) {
  uint32_t st = *(volatile uint32_t *)WDOG_STAT;
  uint32_t n  = WDOG_ST_RSTCNT(st);
  uint32_t bad = 0;

  puts_("wdog demo: boot with WDOGSTAT ");
  puthex(st);
  putc_('\n');

  if (n == 0) {
    /* First boot. Nothing may claim a watchdog reset happened. */
    if (st & (WDOG_ST_WDOGRST | WDOG_ST_ESCALATED | WDOG_ST_NMI)) bad |= 1u;
  } else {
    /* Every later boot was caused by the watchdog and must say so. */
    if (!(st & WDOG_ST_WDOGRST)) bad |= 2u;
    /* Stage 2 clears the pending NMI on its way out -- it has to, see
       the note in soc_wdog.v about boot_addr + 0x7C. */
    if (st & WDOG_ST_NMI) bad |= 4u;
    /* The external pin follows the count and nothing else. */
    if ((n >= 2u) != ((st & WDOG_ST_ESCALATED) != 0u)) bad |= 8u;
    /* The reload was restored to the maximum by the reset, so this boot
       has the full budget however short the last one set it. */
    if (*(volatile uint32_t *)WDOG_RLD != 0xFFFFu) bad |= 16u;
  }

  if (bad) {
    puts_("wdog demo: FAIL mask "); puthex(bad); putc_('\n');
    puts_("RESULT FAIL\n");
    return (int)(0xD0000000u | bad);
  }

  if (n >= 2u) {
    puts_("wdog demo: three stages seen, rstcnt ");
    puthex(n);
    putc_('\n');
    puts_("RESULT PASS\n");
    return 0;
  }

  puts_("wdog demo: arming and refusing to acknowledge\n");
  nmi_no_ack = 1u;
  *(volatile uint32_t *)WDOG_RLD  = WDOG_W(200u);
  *(volatile uint32_t *)WDOG_CTRL = WDOG_W(GPT_LD);
  for (;;) { }        /* the hung core this whole block exists for */
}
#endif

int main(void) {
#ifdef SOC_PLATFORM
  // Nothing can be reported before this: the console is a peripheral on
  // the far side of the bridge and its transmitter is disabled at reset,
  // as GRLIB's APBUART is. A failure between the reset vector and here
  // is silent and shows up as a testbench timeout with a fetch address.
  uart_init();
#endif
#if defined(SOC_PLATFORM) && defined(WDOG_RESET_DEMO)
  return wdog_demo();
#endif

  puts_("ibex bring-up self-test\n");

  // 1 ----------------------------------------------------------------
  volatile uint32_t alive = 0;
  alive = 0xA5A5A5A5u;
  check(1, alive == 0xA5A5A5A5u);

  // 2 ----------------------------------------------------------------
  {
    volatile int32_t  x = -8;
    volatile uint32_t u = 0x80000000u;
    int ok = 1;
    ok &= ((x >> 2) == -2);                 /* arithmetic shift right  */
    ok &= ((u >> 31) == 1u);                /* logical shift right     */
    ok &= ((u << 1) == 0u);
    ok &= ((int32_t)u < 0);                 /* signed compare          */
    ok &= (u > 0x7fffffffu);                /* unsigned compare        */
    ok &= ((0x0f0fu ^ 0x00ffu) == 0x0ff0u);
    check(2, ok);
  }

  // 3 ----------------------------------------------------------------
  {
    int ok = 1;
    /* Expected values computed independently of this program, from the
       operand pair above, in exact integer arithmetic:
         mul    (-1234567 * 7654321) & 0xffffffff = 0xcdb09fa9
         mulh   (-1234567 * 7654321) >> 32        = -2201
         div/rem use C truncation-toward-zero, which is also RISC-V's
         7654321/1000 = 7654 r 321;  -1234567/1000 = -1234 r -567
         0xdeadbeef/0x01234567 = 195 r 0x00cfe17a
       The first version of this file carried three hand-computed
       constants and all three were wrong; the self-check caught them.
       That is the reason every expected value here is derived rather
       than asserted. */
    ok &= (m_a * m_b == (int32_t)0xcdb09fa9);
    ok &= ((int32_t)(((int64_t)m_a * (int64_t)m_b) >> 32) == (int32_t)-2201);
    ok &= (m_b / 1000 == 7654);
    ok &= (m_b % 1000 == 321);
    ok &= (m_a / 1000 == -1234);
    ok &= (m_a % 1000 == -567);
    ok &= (m_ua / m_ub == 195u);
    ok &= (m_ua % m_ub == 0x00cfe17au);
    /* the RISC-V-defined division corner cases */
    {
      volatile int32_t z = 0, one = 1;
      ok &= (one / z == -1);                /* x/0 = all ones          */
      ok &= (one % z == 1);                 /* x%0 = x                 */
    }
    check(3, ok);
  }

  // 4 ----------------------------------------------------------------
  {
    static volatile uint8_t buf[8];
    int ok = 1;
    for (int i = 0; i < 8; i++) buf[i] = (uint8_t)(0x80 + i);
    ok &= (buf[0] == 0x80 && buf[7] == 0x87);
    ok &= ((int8_t)buf[0] == -128);                        /* lb  sext */
    ok &= (*(volatile uint16_t *)&buf[2] == 0x8382u);      /* lhu      */
    ok &= (*(volatile uint32_t *)&buf[4] == 0x87868584u);  /* lw       */
    *(volatile uint16_t *)&buf[4] = 0x1234u;               /* sh       */
    ok &= (buf[4] == 0x34 && buf[5] == 0x12 && buf[6] == 0x86);
    check(4, ok);
  }

  // 5 ----------------------------------------------------------------
  {
    volatile uint32_t n = 0;
    uint32_t sum = 0;
    for (n = 0; n < 100; n++) if (n & 1) sum += n; else sum -= 1;
    check(5, sum == 2500u - 50u);
  }

  // 6 ----------------------------------------------------------------
  check(6, fib(17) == 1597u);

  // 7 ----------------------------------------------------------------
  {
    int ok = (compressed_sum(100) == 5050u);
    /* Assert the function really contains 16-bit instructions: read its
       own first halfword and check the low two bits are not 2'b11. If
       the build silently lost -march=rv32imc this fails rather than
       quietly proving nothing. */
    const uint16_t *insn = (const uint16_t *)(uintptr_t)&compressed_sum;
    int found_rvc = 0;
    for (int i = 0; i < 16 && !found_rvc; i++)
      if ((insn[i] & 3u) != 3u) found_rvc = 1;
    ok &= found_rvc;
    check(7, ok);
  }

  // 8 ----------------------------------------------------------------
  {
    int ok = 1;
    CSRW(mscratch, 0xcafef00du);
    ok &= (CSRR(mscratch) == 0xcafef00du);
    uint32_t c0 = CSRR(mcycle);
    for (volatile int i = 0; i < 50; i++) { }
    ok &= (CSRR(mcycle) > c0);
    check(8, ok);
  }

  // 9 ----------------------------------------------------------------
  {
    uint32_t before = trap_count;
    do_illegal();
    int ok = (trap_count == before + 1) && (trap_mcause == 2u);
    if (!ok) { puts_("  mcause="); puthex(trap_mcause); putc_('\n'); }
    check(9, ok);
  }

  // 10 ---------------------------------------------------------------
#ifdef HAVE_PMP
  {
    volatile uint32_t *p = (volatile uint32_t *)__pmp_buf;
    p[0] = 0x5eed5eedu;                     /* seed before locking      */

    /* NAPOT, 64 bytes at __pmp_buf: pmpaddr = (base >> 2) | ((64/8)-1).
       pmpcfg0 = L | A=NAPOT | R  = 0x80 | 0x18 | 0x01 = 0x99.
       L is required: without it PMP does not apply to M-mode at all
       (RISC-V privileged spec, PMP section), so an unlocked region
       would make this test pass for the wrong reason. */
    uint32_t base = (uint32_t)(uintptr_t)__pmp_buf;

    /* Check the alignment BEFORE programming, not after. A NAPOT base
       that is not naturally aligned does not encode a slightly wrong
       region, it encodes a much LARGER one: at base 0x7e0 the encoding
       below yields 0x1ff, which decodes as 4096 bytes at address 0 --
       the entire program -- read-only and non-executable. The core then
       faults on every instruction fetch, including the trap handler's,
       and there is no way back. Failing the check here turns that from
       an unrecoverable hang into a reported failure. The linker script
       also ASSERTs it, so this is the second of two independent
       guards on the same property. */
    if (base & 63u) {
      puts_("  pmp buffer not 64-byte aligned: "); puthex(base); putc_('\n');
      check(10, 0);
      goto pmp_done;
    }

    uint32_t napot = (base >> 2) | ((64u / 8u) - 1u);
    CSRW(pmpaddr0, napot);
    CSRW(pmpcfg0, 0x99u);

    int ok = 1;
    ok &= (p[0] == 0x5eed5eedu);            /* read still permitted     */

    uint32_t before = trap_count;
    do_store(p, 0xdeadbeefu);               /* write must fault         */
    ok &= (trap_count == before + 1);
    ok &= (trap_mcause == 7u);              /* store access fault       */
    ok &= (p[0] == 0x5eed5eedu);            /* and must not have landed */
    if (!ok) { puts_("  pmp mcause="); puthex(trap_mcause);
               puts_(" cnt="); puthex(trap_count); putc_('\n'); }
    check(10, ok);
  pmp_done: ;
  }
#else
  puts_("SKIP test 10 (core built with PMPEnable=0)\n");
#endif

  // 12, 13, 14 -----------------------------------------------------
  //
  // These exist only on the real SoC. They test the memory map and the
  // fabric rather than the core: an unmapped address must be a bus
  // error and not a silent zero, the device table must agree with the
  // map it was generated from, and the boot ROM must refuse a write.
#ifdef SOC_PLATFORM
  {
    /* 12: a reserved region reaches the error slave. SOC_PLIC_BASE is
       frozen in the map and nothing decodes it, so the load must come
       back with err and become a load access fault, mcause 5. A fabric
       whose default was "return zero" would pass every other check in
       this program and fail here.

       It used to be SOC_CLINT_BASE, until docs/40 implemented the CLINT
       and the check quietly started reading a real register instead of
       faulting. The PLIC region is the right successor for a specific
       reason and not merely because it is the next reserved thing: it is
       the region docs/40 section 3 decided to leave reserved, and this
       is the check that the decision has teeth -- irq_external_i is tied
       low AND the address space that would drive it faults. */
    uint32_t before = trap_count;
    (void)do_load((volatile uint32_t *)(uintptr_t)SOC_PLIC_BASE);
    int ok = (trap_count == before + 1) && (trap_mcause == 5u);
    if (!ok) { puts_("  unmapped mcause="); puthex(trap_mcause);
               puts_(" cnt="); puthex(trap_count); putc_('\n'); }
    check(12, ok);
  }

  {
    /* 13: the device table. Both words are generated from
       regmap/memmap.yaml into soc_memmap.h AND into the ROM contents of
       hw/soc/rtl/soc_pnp.v, so this compares two independent products of
       one source. It catches a generator that emits inconsistent
       outputs and a decode that puts the table at the wrong address; it
       does NOT check the record contents, only these two words. */
    volatile uint32_t *pnp = (volatile uint32_t *)(uintptr_t)SOC_PNP_BASE;
    uint32_t ident  = pnp[SOC_PNP_IDENT_OFF / 4];
    uint32_t endian = pnp[SOC_PNP_ENDIAN_OFF / 4];
    int ok = (ident == SOC_PNP_IDENT_WORD) && (endian == SOC_PNP_ENDIAN_WORD);
    if (!ok) { puts_("  pnp ident="); puthex(ident);
               puts_(" endian="); puthex(endian); putc_('\n'); }
    check(13, ok);
  }

  {
    /* 14: the boot ROM refuses a write. The program is executing out of
       this region, so a ROM that silently accepted stores would let a
       wild pointer rewrite the running code. mcause 7 is store access
       fault -- the same code PMP produces in test 10, which is why test
       12 uses a load: the two mechanisms have to be distinguishable. */
    uint32_t before = trap_count;
    do_store((volatile uint32_t *)(uintptr_t)(SOC_ROM_BASE + 0x100u),
             0xdeadbeefu);
    int ok = (trap_count == before + 1) && (trap_mcause == 7u);
    if (!ok) { puts_("  rom-write mcause="); puthex(trap_mcause);
               puts_(" cnt="); puthex(trap_count); putc_('\n'); }
    check(14, ok);
  }
#endif

  // 15..22 ---------------------------------------------------------
  //
  // The interrupt and timing subsystem. Every one of these is the first
  // time the thing it touches has ever run: docs/39 section 9 item 2
  // recorded that every Ibex interrupt input was tied off, so until now
  // the vectored-only mtvec of docs/38 section 7.5 defect 3 had never
  // been exercised at all.
#ifdef SOC_PLATFORM
  {
    /* 15: mtime runs, and the 64-bit read sequence is stable.
       The read is high, low, high again, repeated while the two highs
       differ -- the standard answer to reading a 64-bit counter over a
       32-bit bus, and the same shape as the write sequence in test 16.
       A CLINT whose halves were not coherent would show up here as a
       loop that never terminates, so the retry count is bounded and
       failing it is a failure rather than a hang. */
    int ok = 1;
    uint64_t a_ = clint_mtime();
    for (volatile int i = 0; i < 20; i++) { }
    uint64_t b_ = clint_mtime();
    ok &= (b_ > a_);
    ok &= ((uint32_t)(b_ - a_) < 10000u);   /* advancing, not jumping */

    /* An offset the CLINT does not implement is a bus error, not a
       register that reads zero. soc_clint.v's header argues that choice;
       this is the check that it was actually made. */
    uint32_t before = trap_count;
    (void)do_load((volatile uint32_t *)(uintptr_t)CLINT_UNMAPPED);
    ok &= (trap_count == before + 1) && (trap_mcause == 5u);
    if (!ok) { puts_("  mtime a="); puthex((uint32_t)a_);
               puts_(" b="); puthex((uint32_t)b_);
               puts_(" mcause="); puthex(trap_mcause); putc_('\n'); }
    check(15, ok);
  }

  {
    /* 16: THE MACHINE TIMER INTERRUPT IS TAKEN AND RETURNED FROM.
       This is the end-to-end demonstration the whole block exists for:
       a deadline programmed into the CLINT over the system fabric, an
       interrupt raised on a wire, the core vectoring to mtvec + 4*7,
       a handler running, and the interrupted code resuming.

       Four independent facts are checked, and the third is the one that
       has never been checked before in this project:
         - the handler ran exactly once;
         - mcause is the machine timer interrupt;
         - the core entered at the MTIMER vector and not at any other,
           which the marker written by that vector's own stub reports;
         - control came back here, which is only observable by this line
           executing at all. */
    uint32_t before = irq_count;
    irq_marker = 0;
    irq_mcause = 0;

    /* Deadline. The three-store sequence of soc_clint.v's header: an
       unreachable low half first, so the intermediate 64-bit value can
       never be a deadline that is already met. */
    uint64_t now = clint_mtime();
    clint_set_mtimecmp(now + 200u);

    csr_set_mie(MIE_MTIE);
    csr_set_mstatus(MSTATUS_MIE);

    int spun = 0;
    while (irq_count == before && spun < 20000) spun++;

    csr_clr_mstatus(MSTATUS_MIE);

    int ok = 1;
    ok &= (irq_count == before + 1);
    ok &= (irq_mcause == SOC_IRQ_MTIMER);
    ok &= (irq_marker == SOC_IRQID_MTIMER);
    ok &= (spun < 20000);
    /* The handler masked the source rather than clearing it, so MTIE
       must now be clear. If it were not, the level-sensitive line would
       have re-entered the handler and irq_count would be far above
       before+1 -- which the first check would have caught, but this one
       names the mechanism. */
    ok &= ((csr_read_mie() & MIE_MTIE) == 0u);
    if (!ok) { puts_("  mtimer cause="); puthex(irq_mcause);
               puts_(" vec="); puthex(irq_marker);
               puts_(" n="); puthex(irq_count - before);
               puts_(" spun="); puthex((uint32_t)spun); putc_('\n'); }
    check(16, ok);

    /* Disarm and confirm the level really went away: with mtimecmp at
       the top of the range, mip.MTIP must read zero. A pulse-based timer
       would pass every check above and fail this one. */
    clint_set_mtimecmp(~(uint64_t)0);
    ok = ((csr_read_mip() & MIE_MTIE) == 0u);
    if (!ok) { puts_("  mip still pending\n"); }
    check(17, ok);
  }

  {
    /* 18: the machine software interrupt, through the CLINT's msip.
       A different vector, a different mcause, the same fabric. It is
       here because it is the cheapest possible check that the vector
       table is a TABLE: if the core were entering at BASE for interrupts
       as well as exceptions, tests 16 and 18 would report the same
       marker. */
    uint32_t before = irq_count;
    irq_marker = 0;
    *(volatile uint32_t *)CLINT_MSIP = 1u;
    csr_set_mie(MIE_MSIE);
    csr_set_mstatus(MSTATUS_MIE);
    int spun = 0;
    while (irq_count == before && spun < 2000) spun++;
    csr_clr_mstatus(MSTATUS_MIE);
    *(volatile uint32_t *)CLINT_MSIP = 0u;

    int ok = (irq_count == before + 1)
          && (irq_mcause == SOC_IRQ_MSOFT)
          && (irq_marker == SOC_IRQID_MSOFT)
          && (spun < 2000);
    if (!ok) { puts_("  msoft cause="); puthex(irq_mcause);
               puts_(" vec="); puthex(irq_marker); putc_('\n'); }
    check(18, ok);
  }

  {
    /* 19: the GPTIMER on a FAST LOCAL interrupt line.
       This is the path a peripheral takes and the one that would need a
       PLIC if Ibex did not have fifteen of these -- docs/40 section 3.
       The vector is mtvec + 4*(16+line) and the line comes from the
       generated map, so if regmap/memmap.yaml moved GPTIMER0 to another
       line this test would demand the other vector.

       The configuration register is checked too: it must report three
       timers (two general plus the watchdog) and the plug-and-play
       source number the map assigns, because that number reaching the
       block from the map rather than from a constant in its RTL is the
       whole point of generating it. */
    uint32_t cfg = *(volatile uint32_t *)GPT_CONFIG;
    int ok = ((cfg & 7u) == 3u);
    ok &= (((cfg >> 3) & 0x1Fu) == 8u);   /* IRQ field, map's source 8 */
    ok &= (((cfg >> 8) & 1u) == 0u);      /* SI = 0, one shared line   */

    uint32_t before = irq_count;
    irq_marker = 0;
    *(volatile uint32_t *)GPT_SCRELOAD = 3u;      /* prescaler         */
    *(volatile uint32_t *)GPT_RLD(1)   = 40u;
    *(volatile uint32_t *)GPT_CTRL(1)  = GPT_EN | GPT_RS | GPT_LD | GPT_IE;

    csr_set_mie(MIE_FAST(SOC_IRQLINE_TIMER0));
    csr_set_mstatus(MSTATUS_MIE);
    int spun = 0;
    while (irq_count == before && spun < 20000) spun++;
    csr_clr_mstatus(MSTATUS_MIE);

    ok &= (irq_count == before + 1);
    ok &= (irq_mcause == SOC_IRQ_TIMER0);
    ok &= (irq_marker == (SOC_FAST_IRQ_BASE + SOC_IRQLINE_TIMER0));
    ok &= (spun < 20000);

    /* Stop it and clear the pending bit, so nothing left running here
       can disturb a later test. IP is write-one-to-clear. */
    *(volatile uint32_t *)GPT_CTRL(1) = GPT_IP;
    ok &= ((*(volatile uint32_t *)GPT_CTRL(1) & GPT_IP) == 0u);
    if (!ok) { puts_("  gptimer cfg="); puthex(cfg);
               puts_(" cause="); puthex(irq_mcause);
               puts_(" vec="); puthex(irq_marker); putc_('\n'); }
    check(19, ok);
  }

  {
    /* 20: the watchdog cannot be switched off by the software it
       watches, and cannot be written at all without the key.
       hw/soc/rtl/soc_wdog.v W1 and W5 stated as a program. */
    int ok = 1;
    uint32_t rld0 = *(volatile uint32_t *)WDOG_RLD;

    /* Unkeyed write: no effect anywhere. */
    *(volatile uint32_t *)WDOG_RLD = 0x1234u;
    ok &= (*(volatile uint32_t *)WDOG_RLD == rld0);

    /* Keyed write to clear EN, RS and IE: accepted by the bus, ignored
       by the block, and the read-back says so rather than lying. */
    *(volatile uint32_t *)WDOG_CTRL = WDOG_W(0u);
    uint32_t ctrl = *(volatile uint32_t *)WDOG_CTRL;
    ok &= ((ctrl & GPT_EN) != 0u);
    ok &= ((ctrl & GPT_RS) != 0u);
    ok &= ((ctrl & GPT_IE) != 0u);

    /* Boot status: this run was not started by the watchdog. */
    uint32_t st = *(volatile uint32_t *)WDOG_STAT;
    ok &= ((st & WDOG_ST_WDOGRST) == 0u);
    ok &= ((st & WDOG_ST_DISABLED) == 0u);
    ok &= (WDOG_ST_RSTCNT(st) == 0u);
    if (!ok) { puts_("  wdog ctrl="); puthex(ctrl);
               puts_(" stat="); puthex(st);
               puts_(" rld="); puthex(rld0); putc_('\n'); }
    check(20, ok);
  }

  {
    /* 21: the watchdog's stage 1 is a NON-MASKABLE interrupt, and it
       arrives with interrupts globally disabled.
       mstatus.MIE is left at zero for the whole of this test on purpose.
       That is the state the watchdog exists to fire in -- a core stuck
       inside a trap handler has MIE clear, because the hardware cleared
       it on entry -- and a maskable line would be invisible there.

       The timeout is shortened with a keyed write, the program then
       stops kicking, and the NMI must arrive at mtvec + 0x7C. */
    uint32_t before = nmi_count;
    irq_marker = 0;
    irq_mcause = 0;

    *(volatile uint32_t *)WDOG_RLD  = WDOG_W(200u);
    *(volatile uint32_t *)WDOG_CTRL = WDOG_W(GPT_LD);   /* kick, short */

    int spun = 0;
    while (nmi_count == before && spun < 40000) spun++;

    int ok = (nmi_count == before + 1);
    /* Interrupts were never globally enabled anywhere in this test, and
       that is the property being demonstrated: this one arrived anyway. */
    ok &= ((csr_read_mstatus() & MSTATUS_MIE) == 0u);
    ok &= (irq_mcause == SOC_IRQ_NMI);
    ok &= (irq_marker == SOC_IRQID_NMI);
    ok &= (spun < 40000);
    /* The handler acknowledged, so the pending bit is gone; had it not
       been, mret would have re-entered the handler immediately. */
    uint32_t st = *(volatile uint32_t *)WDOG_STAT;
    ok &= ((st & WDOG_ST_NMI) == 0u);
    ok &= ((st & WDOG_ST_WDOGRST) == 0u);   /* stage 2 has not fired   */

    /* Back to the longest timeout and kick, so the rest of the run is
       not racing stage 2. */
    *(volatile uint32_t *)WDOG_RLD  = WDOG_W(0xFFFFu);
    *(volatile uint32_t *)WDOG_CTRL = WDOG_W(GPT_LD);
    if (!ok) { puts_("  nmi cause="); puthex(irq_mcause);
               puts_(" vec="); puthex(irq_marker);
               puts_(" stat="); puthex(st);
               puts_(" spun="); puthex((uint32_t)spun); putc_('\n'); }
    check(21, ok);
  }

  {
    /* 22: the mtvec constraint itself, exercised rather than commented.
       docs/38 section 7.5 defect 3 says mtvec[7:2] reads as zero
       whatever is written and MODE is hardwired to vectored. Nothing has
       ever tested it, because until this document nothing could take an
       interrupt. Write a base four bytes off the 256-byte grid, with
       MODE bits that ask for direct mode, and require the read-back to
       be the enclosing 256-byte boundary with MODE still vectored.

       The old value is restored immediately. If this test failed by
       actually MOVING the vector table, every later trap would go
       somewhere else, so the restore is unconditional and comes before
       the comparison. */
    uint32_t good = (uint32_t)(uintptr_t)trap_vectors;
    uint32_t back;
    __asm__ volatile("csrw mtvec, %1\n csrr %0, mtvec\n csrw mtvec, %2\n"
                     : "=&r"(back) : "r"(good + 4u), "r"(good) : "memory");
    int ok = ((back & ~0xFFu) == (good & ~0xFFu));
    ok &= ((back & 0xFCu) == 0u);      /* BASE[7:2] forced to zero      */
    ok &= ((back & 0x3u) == 1u);       /* MODE is vectored and read-only*/
    /* mtvec NEVER reads back what was written: MODE is hardwired to
       2'b01, so the restored value reads as good|1. Checking for `good`
       here was this test's own first failure, which is a small
       demonstration of the same point -- a CSR whose write and read
       differ is exactly the shape of thing a handler address gets
       silently wrong on. */
    ok &= (csr_read_mtvec() == (good | 1u));
    if (!ok) { puts_("  mtvec back="); puthex(back);
               puts_(" good="); puthex(good); putc_('\n'); }
    check(22, ok);
  }
#endif

  check(11, trap_saw_rvc == 0u);   /* handler never had to guess a width */

  puts_("checks run: ");  puthex(checks);
  puts_("  fail mask: "); puthex(fails);
  putc_('\n');
  puts_(fails ? "RESULT FAIL\n" : "RESULT PASS\n");
  return (int)fails;
}
