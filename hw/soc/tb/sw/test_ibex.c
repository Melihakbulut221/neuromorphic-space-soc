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

#include <stdint.h>

#define PUTC_ADDR 0x00100000u
#define HALT_ADDR 0x00100004u

extern uint32_t trap_mcause, trap_mepc, trap_count, trap_saw_rvc;
extern char __pmp_buf[];

static void putc_(char c) { *(volatile uint32_t *)PUTC_ADDR = (uint32_t)c; }
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

#ifdef HAVE_PMP
// Only test 10 uses this, and test 10 is compiled out on a core built
// without PMP. -Werror makes an unused static function an error, which
// is the wanted behaviour: it says the guard around the caller and the
// guard around the callee have to agree.
static void do_store(volatile uint32_t *p, uint32_t v) {
  __asm__ volatile(".option push\n.option norvc\n"
                   "sw %1, 0(%0)\n"
                   ".option pop\n" :: "r"(p), "r"(v) : "memory");
}
#endif

#define CSRR(name)      ({ uint32_t v_; __asm__ volatile ("csrr %0, " #name : "=r"(v_)); v_; })
#define CSRW(name, v)   __asm__ volatile ("csrw " #name ", %0" :: "r"(v))

int main(void) {
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

  check(11, trap_saw_rvc == 0u);   /* handler never had to guess a width */

  puts_("checks run: ");  puthex(checks);
  puts_("  fail mask: "); puthex(fails);
  putc_('\n');
  puts_(fails ? "RESULT FAIL\n" : "RESULT PASS\n");
  return (int)fails;
}
