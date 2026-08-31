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
extern char __pmp_buf[];

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

int main(void) {
#ifdef SOC_PLATFORM
  // Nothing can be reported before this: the console is a peripheral on
  // the far side of the bridge and its transmitter is disabled at reset,
  // as GRLIB's APBUART is. A failure between the reset vector and here
  // is silent and shows up as a testbench timeout with a fetch address.
  uart_init();
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
    /* 12: a reserved region reaches the error slave. SOC_CLINT_BASE is
       frozen in the map and nothing decodes it, so the load must come
       back with err and become a load access fault, mcause 5. A fabric
       whose default was "return zero" would pass every other check in
       this program and fail here. */
    uint32_t before = trap_count;
    (void)do_load((volatile uint32_t *)(uintptr_t)SOC_CLINT_BASE);
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

  check(11, trap_saw_rvc == 0u);   /* handler never had to guess a width */

  puts_("checks run: ");  puthex(checks);
  puts_("  fail mask: "); puthex(fails);
  putc_('\n');
  puts_(fails ? "RESULT FAIL\n" : "RESULT PASS\n");
  return (int)fails;
}
