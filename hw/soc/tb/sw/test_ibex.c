// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: Apache-2.0

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

/* THE QSPI DEMONSTRATION IS A SECOND IMAGE, and the reason is the size
   of the boot ROM. The map gives it 8 KiB and the image is linked at
   the reset vector, 8,064 bytes; the 28-check program is 7,794 of them
   and checks 29 and 30 need about 1,800 more (docs/66 section 6). So
   with -DQSPI_DEMO the build keeps check 1, check 26 -- the inference
   from the ROM's weight arrays -- checks 29 and 30, and check 11, and
   compiles out the rest; without it the program is the 28-check one
   every document since docs/40 quotes, and hw/soc/flow/sim_soc.sh
   builds either from this one file, exactly as it builds the watchdog
   escalation demonstration with -DWDOG_RESET_DEMO. */
#ifdef QSPI_DEMO
#pragma GCC diagnostic ignored "-Wunused-function"
#pragma GCC diagnostic ignored "-Wunused-variable"
#endif

#ifdef SOC_PLATFORM
#include "soc_memmap.h"
#include "soc_timers.h"
#include "soc_npucfg.h"
#include "soc_gpio.h"
#include "soc_qspi.h"
/* Both generated into the build directory by
   hw/soc/flow/gen_npu_vectors.py, which build_sw_soc.sh runs first:
   npu_regs.h is the node register map from regmap/regmap.yaml, and
   npu_vectors.h is this demonstration's stimulus together with the
   answer sw/golden/lif_core.py computes for it. Checks 23 to 27 compare
   the hardware against the second and never against itself. */
#include "npu_regs.h"
#include "npu_vectors.h"
#ifdef QSPI_DEMO
/* Also generated into the build directory, by
   hw/soc/flow/gen_flash_image.py: what the modelled flash on chip
   select 0 holds and the sample words check 29 compares against. */
#include "qspi_image.h"
#endif

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
/* ALIGNED(64), AND THAT ATTRIBUTE IS LOAD-BEARING.
   link_soc.ld and link_app.ld both place this buffer on a 64-byte
   boundary and both ASSERT it, but a bare `extern char[]` tells the
   compiler its alignment is 1 -- and test 10 then dereferences it as a
   `volatile uint32_t *`, which on a RISC-V target that does not permit
   unaligned access is undefined behaviour. The compiler is entitled to
   expand it into byte accesses, and it does.
   docs/68 section 10 is where that stopped being harmless: when the
   program moved out of the boot ROM and into RAM the register
   allocation around test 10 changed, the byte accesses were emitted
   through a base register the surrounding code had since loaded with
   something else, and three of the four bytes went to an unmapped
   address and took bus errors. The symptom was `mcause 5` inside a PMP
   test, which reads exactly like a PMP failure and is not one.
   Declaring the alignment the linker script already guarantees removes
   the undefined behaviour and the access becomes one aligned word. */
extern char __pmp_buf[] __attribute__((aligned(64)));
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

#ifdef SOC_PLATFORM
/* ---- NPU access helpers -------------------------------------------
   The node register window is ORDINARY MEMORY as far as this program is
   concerned: a load or a store at SOC_NPU_BASE + node*0x1000 + offset.
   What is behind it is a serial frame into the frozen pilot and about
   172 clock cycles of it, which is why these are plain accesses and not
   a poll loop -- the SLAVE holds the response, so the core stalls on
   the load exactly as it would on a slow memory, and nothing here has
   to know the transport exists. That is the whole point of the design
   (hw/soc/rtl/soc_npu.v section 1).

   The one place the cost is visible is the BUSY poll below, which is
   bounded rather than unbounded for the reason every wait loop in this
   file is: a hang says nothing. */
static void npu_wr(uint32_t off, uint32_t v) {
  *(volatile uint32_t *)NPU_NODE(0, off) = v;
}
static uint32_t npu_rd(uint32_t off) {
  return *(volatile uint32_t *)NPU_NODE(0, off);
}
static uint32_t cfg_rd(uint32_t a) { return *(volatile uint32_t *)a; }
static void cfg_wr(uint32_t a, uint32_t v) { *(volatile uint32_t *)a = v; }

/* Wait for the node to go idle. STATUS.BUSY is bit 0 (regmap/regmap.yaml
   through the generated header). */
static int npu_wait_idle(int limit) {
  for (int i = 0; i < limit; i++)
    if ((npu_rd(NPU_STATUS) & (1u << NPU_BIT_STATUS_BUSY)) == 0u) return 1;
  return 0;
}

/* Bring the node up in the order docs/10 section 11.1 requires: reset,
   state clear, configure, load weights, enable. Configuration registers
   are LOCKED while BUSY (docs/10 section 6), so the enable is last and
   the state clear has to complete before the configuration starts. */
/* THE WEIGHT WORDS ARE A PARAMETER, as of docs/66: check 26 passes the
   arrays the ROM image carries and check 30 passes the words it read
   out of the flash through the QSPI controller. The sequence, and the
   read-backs, are the same for both. */
static int npu_bring_up(const uint32_t *wlo, const uint32_t *whi) {
  int ok = 1;
  npu_wr(NPU_CTRL, 1u << NPU_BIT_CTRL_STATE_CLR);
  if (!npu_wait_idle(64)) { ok = 0; puts_("  npu: state clear never ended\n"); }

  for (int c = 0; c < NPUV_N_CFG; c++)
    npu_wr(npuv_cfg_off[c], npuv_cfg_val[c]);

/* THE READ-BACK IS A PARAMETER SO THAT ITS COST CAN BE SEPARATED FROM
   THE RTL'S, and that separation is the whole evidentiary value of the
   whole-SoC cycle count. Every document since docs/40 has used that
   number to say "behaviour did not change"; docs/55 changes both the
   RTL and this program, so it reports the invariant TWICE -- once with
   the hardened RTL and this loop disabled, which must reproduce
   docs/51's number exactly, and once as shipped. One number could not
   have told the two apart.

     SW_DEFINES=-DNPU_CFG_READBACK=0 hw/soc/flow/sim_soc.sh <out>       */
#ifndef NPU_CFG_READBACK
#define NPU_CFG_READBACK 1
#endif

  /* Read EVERY one of them back. A configuration write that was
     silently refused -- the lock, an out-of-range value, a decode that
     went to the wrong register -- would otherwise be invisible until
     the inference produced the wrong answer, and then it would look
     like an arithmetic bug.

     IT USED TO READ BACK ONE, AND docs/52 MEASURED WHAT THAT MISSED.
     Of 265 injections that landed before the block was enabled, 14
     corrupted the inference; this sequence's read-backs caught 3; every
     one of the 14 was silent to every hardware channel. The sharpest
     record is `ser.tx` bit 32, which is ADDR[0] of the serial frame:
     the write went to the WRONG register, the die accepted it, and the
     single CFG_THRESH read-back read the register that was NOT
     corrupted and passed.

     The cost is NPUV_N_CFG - 1 extra 176-cycle frames, once per
     bring-up, and it is the reason the whole-SoC cycle count moved in
     docs/55. What it does NOT close is the weight array: docs/10
     section 10's map has no weight read port, so a weight word
     corrupted on the way in is stored as a valid SECDED codeword of the
     wrong value and nothing on this side of the pin boundary can ask
     the die what it holds. */
#if NPU_CFG_READBACK
  for (int c = 0; c < NPUV_N_CFG; c++) {
    uint32_t got = npu_rd(npuv_cfg_off[c]);
    if (got != npuv_cfg_val[c]) {
      ok = 0;
      puts_("  npu: cfg offset "); puthex(npuv_cfg_off[c]);
      puts_(" reads "); puthex(got);
      puts_(" want "); puthex(npuv_cfg_val[c]); putc_('\n');
    }
  }
#else
  /* docs/51's single read-back, kept only so the RTL's own contribution
     to the cycle count can be measured. */
  {
    uint32_t th = npu_rd(NPUV_OFF_CFG_THRESH);
    if (th != NPUV_VAL_CFG_THRESH) {
      ok = 0; puts_("  npu: CFG_THRESH reads "); puthex(th); putc_('\n');
    }
  }
#endif

  /* W_ADDR auto-increments on the W_DATA_HI commit (docs/10 section 10),
     so it is written once. */
  npu_wr(NPU_W_ADDR, 0u);
  for (int w = 0; w < NPUV_N_WWORDS; w++) {
    npu_wr(NPU_W_DATA_LO, wlo[w]);
    npu_wr(NPU_W_DATA_HI, whi[w]);
  }
  {
    uint32_t wa = npu_rd(NPU_W_ADDR), sec = npu_rd(NPU_CNT_SEC),
             ded = npu_rd(NPU_CNT_DED);
    /* W_ADDR auto-increments on the W_DATA_HI commit and its index is
       exactly wide enough for the array (pilot_top.v deviation D3), so
       loading the whole array wraps it back to zero. The generator
       computes the expected value rather than this program assuming
       one. No ECC event may have happened while loading a clean
       image. */
    if (wa != (uint32_t)NPUV_WADDR_AFTER_LOAD || sec != 0u || ded != 0u) {
      ok = 0;
      puts_("  npu: after load W_ADDR="); puthex(wa);
      puts_(" CNT_SEC="); puthex(sec);
      puts_(" CNT_DED="); puthex(ded); putc_('\n');
    }
  }

  npu_wr(NPU_CTRL, (1u << NPU_BIT_CTRL_EN) | (1u << NPU_BIT_CTRL_SCRUB_EN));
  return ok;
}

/* Run the whole stimulus and collect the output stream.
   `got` receives the event words in arrival order. Returns how many
   were collected, or -1 if a frame's barrier never came back. */
static int npu_run(uint16_t *got, int cap) {
  int n = 0, k = 0;
  for (int f = 0; f < NPUV_N_FRAMES; f++) {
    for (int i = 0; i < npuv_inj_len[f]; i++)
      cfg_wr(NPUCFG_EVQ_IN, npuv_inject[k++]);

    /* Read until the barrier this frame injected comes back. docs/10
       section 7.1: when the node consumes a SYNC, every prior event is
       fully processed and the barrier is echoed downstream -- so this
       loop needs no timing knowledge at all, only the echo. The
       iteration bound is a hang detector and nothing else. */
    uint16_t barrier = NPU_EV_SYNC(f);
    int spins = 0;
    for (;;) {
      uint32_t w = cfg_rd(NPUCFG_EVQ_OUT);
      if (w & NPUCFG_EVQ_VALID) {
        if (n < cap) got[n] = (uint16_t)(w & 0xFFFFu);
        n++;
        if ((uint16_t)(w & 0xFFFFu) == barrier) break;
        spins = 0;
      } else if (++spins > 20000) {
        return -1;
      }
    }
  }
  return n;
}

/* ONE INFERENCE, checked against the golden model. The body of check
   26 since docs/51, made a function by docs/66 so that check 30 can run
   the same inference with weights that came from the flash instead of
   from the ROM image. Everything is in the loop: the fabric, the APB
   bridge, the slot decode, the serial transport, the die's frozen
   register bank, its ECC-checked weight loader, its event queues, its
   LIF datapath, the parallel AER pins on the way in and the serial
   EVQ_OUT register on the way out -- and the answer is
   sw/golden/lif_core.py's, computed at BUILD time, never the
   hardware's. */
static int npu_inference(const uint32_t *wlo, const uint32_t *whi,
                         const char *tag) {
static uint16_t got[NPUV_N_EXPECT + 8];
/* The event counters are not cleared between inferences; what one
   inference adds to them is what is checked. */
uint32_t cnt0 = cfg_rd(NPUCFG_CNT);
int ok = npu_bring_up(wlo, whi);

  cfg_wr(NPUCFG_CTRL, NPUCFG_IN_EN | NPUCFG_OUT_EN);
  int n = npu_run(got, (int)(sizeof(got) / sizeof(got[0])));

  if (n != NPUV_N_EXPECT) {
    ok = 0;
    puts_("  npu stream length "); puthex((uint32_t)n);
    puts_(" want "); puthex((uint32_t)NPUV_N_EXPECT); putc_('\n');
    /* Print what did come back. A length mismatch with no stream is a
       report that says nothing about which event was extra or
       missing, and this program's whole convention is that a failure
       should be locatable from the log. */
    puts_("  got ");
    for (int i = 0; i < n && i < (int)(sizeof(got)/sizeof(got[0])); i++) {
      puthex(got[i]); putc_(' ');
    }
    putc_('\n');
    puts_("  want ");
    for (int i = 0; i < NPUV_N_EXPECT; i++) {
      puthex(npuv_expect[i]); putc_(' ');
    }
    putc_('\n');
  } else {
    for (int i = 0; i < NPUV_N_EXPECT; i++) {
      if (got[i] != npuv_expect[i]) {
        ok = 0;
        puts_("  npu event "); puthex((uint32_t)i);
        puts_(" got "); puthex(got[i]);
        puts_(" want "); puthex(npuv_expect[i]); putc_('\n');
      }
    }
  }

  /* The whole neuron state file afterwards, against the same model.
     The spike stream says the outputs matched; this says the internal
     trajectory did too, which is a strictly stronger statement and is
     the one that catches an error that happened to cancel. */
  for (int j = 0; j < NPUV_N_NEURONS; j++) {
    npu_wr(NPU_N_ADDR, (uint32_t)j);
    uint32_t w = npu_rd(NPU_N_DATA) & 0x000FFFFFu;
    if (w != npuv_state[j]) {
      ok = 0;
      puts_("  npu state "); puthex((uint32_t)j);
      puts_(" got "); puthex(w);
      puts_(" want "); puthex(npuv_state[j]); putc_('\n');
    }
  }

  /* Nothing may have been lost or faulted on the way. */
  uint32_t st = cfg_rd(NPUCFG_STATUS);
  uint32_t cnt = cfg_rd(NPUCFG_CNT);
  uint32_t cause = cfg_rd(NPUCFG_IRQCAUSE);
  uint32_t drop = cfg_rd(NPUCFG_CNT_DROP);
  uint32_t ovf = npu_rd(NPU_CNT_EVQ_OVF);
  uint32_t oor = npu_rd(NPU_CNT_AXON_OOR);
  if ((cause & (NPUCFG_C_ERR | NPUCFG_C_DED | NPUCFG_C_INJ_OVF
                | NPUCFG_C_FETCH_ER)) || drop || ovf || oor) {
    ok = 0;
    puts_("  npu: cause="); puthex(cause);
    puts_(" drop="); puthex(drop);
    puts_(" evq_ovf="); puthex(ovf);
    puts_(" axon_oor="); puthex(oor); putc_('\n');
  }
  /* Every injected word reached the node and every expected word came
     back out of it, counted by the hardware independently of the
     stream this program collected. */
  ok &= (((cnt - cnt0) & 0xFFFFu) == (uint32_t)NPUV_N_INJECT);
  ok &= ((((cnt >> 16) - (cnt0 >> 16)) & 0xFFFFu) == (uint32_t)NPUV_N_EXPECT);

  puts_(tag); puthex((uint32_t)n);
  puts_(" events, cnt="); puthex(cnt);
  puts_(" status="); puthex(st); putc_('\n');
  return ok;
}

#ifdef QSPI_DEMO
/* ---- QSPI flash access, docs/66 ------------------------------------
   The controller is register mode: software describes one transaction
   in CMD (writing it starts the frame), and pulls each word out of RX
   at DR or pushes it into TX at TXE. Every wait is bounded, for the
   reason every wait loop in this file is. */
static int qspi_wait(uint32_t mask) {
  for (int i = 0; i < 20000; i++)
    if (cfg_rd(QSPI_STAT) & mask) return 1;
  return 0;
}

/* A read-type transaction: `n` bytes into `out` words, little-endian
   lanes, through the DR pause at every word. Returns 1 if every wait
   ended and DONE arrived. */
static int qspi_read(uint32_t cmdw, uint32_t addr, uint32_t *out, int n) {
  int ok = 1;
  cfg_wr(QSPI_ADDR, addr);
  cfg_wr(QSPI_CMD, cmdw | QSPI_CMD_LEN(n));
  for (int w = 0; w < (n + 3) / 4; w++) {
    ok &= qspi_wait(QSPI_ST_DR);
    out[w] = cfg_rd(QSPI_RX);
  }
  ok &= qspi_wait(QSPI_ST_DONE);
  cfg_wr(QSPI_STAT, QSPI_ST_DONE);
  return ok;
}

/* A write-type or opcode-only transaction with at most one TX word. */
static int qspi_cmd(uint32_t op, uint32_t txw, int n) {
  if (n) cfg_wr(QSPI_TX, txw);
  cfg_wr(QSPI_CMD, QSPI_CMD_OP(op) | QSPI_CMD_WRITE | QSPI_CMD_LEN(n));
  int ok = qspi_wait(QSPI_ST_DONE);
  cfg_wr(QSPI_STAT, QSPI_ST_DONE);
  return ok;
}

static uint32_t flash_sr(uint32_t op) {
  uint32_t v = 0;
  (void)qspi_read(QSPI_CMD_OP(op), 0, &v, 1);
  return v & 0xFFu;
}
#endif /* QSPI_DEMO */

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

#ifndef QSPI_DEMO
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
    /* mepc as well as mcause, added by docs/68: this check first failed
       when the program moved from the boot ROM into RAM, and "a load
       access fault somewhere" is not a diagnosis. The faulting PC is. */
    if (!ok) { puts_("  pmp mcause="); puthex(trap_mcause);
               puts_(" mepc="); puthex(trap_mepc);
               puts_(" cnt="); puthex(trap_count);
               puts_(" buf="); puthex(base);
               puts_(" val="); puthex(p[0]); putc_('\n'); }
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
#endif /* !QSPI_DEMO */
#ifdef SOC_PLATFORM
#ifndef QSPI_DEMO
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

  {
    /* 23: the NPU fabric controller answers, and its reserved offsets
       do not. NPUCFG has been a slot number with nothing behind it in
       every document since docs/39; this is the first check that
       anything is there. The identity word is the discovery convention
       regmap/regmap.yaml uses for the node ("NPU1"); the controller is
       "NPUC", one letter apart on purpose. */
    int ok = (cfg_rd(NPUCFG_ID) == NPUCFG_ID_WORD);
    ok &= (cfg_rd(NPUCFG_VERSION) == 1u);
    /* The geometry the RTL was elaborated with, reported by the block
       rather than assumed by this program. */
    uint32_t geom = cfg_rd(NPUCFG_GEOM);
    ok &= ((geom & 0xFFu) == 1u);              /* one node             */
    ok &= (((geom >> 8) & 0xFFu) == 2u);       /* SER_SCK = clk/4      */

    trap_count = 0; trap_mcause = 0;
    (void)do_load((volatile uint32_t *)NPUCFG_UNIMPL);
    ok &= (trap_count == 1u && trap_mcause == 5u);

    if (!ok) { puts_("  npucfg id="); puthex(cfg_rd(NPUCFG_ID));
               puts_(" geom="); puthex(geom);
               puts_(" mcause="); puthex(trap_mcause); putc_('\n'); }
    check(23, ok);
  }

  {
    /* 24: THE NODE REGISTER WINDOW IS THE docs/10 SECTION 10 REGISTER
       MAP, reached with ordinary loads and stores.

       Every constant compared here comes from regmap/regmap.yaml
       through the generated npu_regs.h -- the same file that produces
       the die's own hw/rtl/npu_regs.vh -- so this is a check that the
       window presents the ARCHITECTURE's map and not that it presents
       whatever the transport happened to fetch.

       CFG_NEUR reports the elaborated neuron count rather than its
       architectural reset value: pilot_top.v deviation D2 makes it
       read-only and reports N_NEURONS, so the constant to compare
       against is the geometry, not RST_CFG_NEUR. That divergence is
       documented at the die and is checked here rather than papered
       over. */
    int ok = (npu_rd(NPU_ID) == NPU_RST_ID);
    ok &= (npu_rd(NPU_VERSION) == NPU_RST_VERSION);
    ok &= (npu_rd(NPU_CFG_NEUR) == (uint32_t)NPUV_N_NEURONS);
    ok &= (npu_rd(NPU_CFG_AXON) == (uint32_t)NPUV_N_AXONS);

    /* A write and a read back through the whole transport. SCRATCH is
       the register the map defines for exactly this and it has no side
       effects. */
    npu_wr(NPU_SCRATCH, 0xA5A50F0Fu);
    uint32_t scr = npu_rd(NPU_SCRATCH);
    ok &= (scr == 0xA5A50F0Fu);
    npu_wr(NPU_SCRATCH, NPU_RST_SCRATCH);

    if (!ok) { puts_("  node id="); puthex(npu_rd(NPU_ID));
               puts_(" ver="); puthex(npu_rd(NPU_VERSION));
               puts_(" neur="); puthex(npu_rd(NPU_CFG_NEUR));
               puts_(" axon="); puthex(npu_rd(NPU_CFG_AXON));
               puts_(" scratch="); puthex(scr);
               putc_('\n'); }
    check(24, ok);
  }

  {
    /* 25: the reserved parts of the 256 MiB window fault, all three
       kinds of them.

       This is the check that "reserved" is a property and not a
       comment. A window that decoded everything to node 0 would pass
       every other NPU check in this program and fail this one. */
    int ok = 1;
    /* static const, not a local initialiser: a local array of
       structs is copied out of .rodata with memcpy, and this program
       links no libc. -nostdlib turns that into a link error rather than
       a silent dependency, which is the wanted behaviour. */
    static const struct { uint32_t a; const char *what; } bad[] = {
      { NPU_NODE(1, NPU_ID),          "node 1, not instantiated" },
      { NPU_NODE(15, NPU_ID),         "node 15, not instantiated" },
      { SOC_NPU_BASE + 0x00000200u,   "above the die's 7-bit map" },
      { SOC_NPU_BASE + 0x00010000u,   "above the node windows" },
      { SOC_NPU_BASE + 0x08000000u,   "the descriptor-ring area" },
    };
    for (unsigned i = 0; i < sizeof(bad) / sizeof(bad[0]); i++) {
      trap_count = 0; trap_mcause = 0;
      (void)do_load((volatile uint32_t *)bad[i].a);
      if (trap_count != 1u || trap_mcause != 5u) {
        ok = 0;
        puts_("  npu window "); puts_(bad[i].what);
        puts_(" did not fault: mcause="); puthex(trap_mcause); putc_('\n');
      }
    }
    /* And a sub-word store, which the 32-bit serial frame cannot
       perform. Silently widening it would corrupt three bytes of a
       register the program never named. */
    trap_count = 0; trap_mcause = 0;
    __asm__ volatile(".option push\n.option norvc\n"
                     "sb %1, 0(%0)\n"
                     ".option pop\n"
                     :: "r"((volatile uint8_t *)NPU_NODE(0, NPU_SCRATCH)),
                        "r"(0x5Au) : "memory");
    if (trap_count != 1u || trap_mcause != 7u) {
      ok = 0;
      puts_("  npu byte store did not fault: mcause=");
      puthex(trap_mcause); putc_('\n');
    }
    check(25, ok);
  }

#endif /* !QSPI_DEMO */
  {
    /* 26: THE DEMONSTRATION. A program on Ibex, out of the boot ROM,
       over the real fabric, configures the NPU, feeds it events and
       reads results back -- and the results are compared against the
       answer sw/golden/lif_core.py computed at BUILD TIME, not against
       what the hardware produced.

       Everything is in the loop: the fabric, the APB bridge, the slot
       decode, the serial transport, the die's frozen register bank, its
       ECC-checked weight loader, its event queues, its LIF datapath,
       the parallel AER pins on the way in and the serial EVQ_OUT
       register on the way out. */
    int ok = npu_inference(npuv_wlo, npuv_whi, "npu: ");
    check(26, ok);
  }

#ifndef QSPI_DEMO
  {
    /* 27: the NPU raises its interrupt, on the fast local line the
       frozen map assigns it, at its own vector.

       Spending line 12 is not a new cost -- docs/40 assigned NPUCFG
       source 24 and line 12 before this block existed, and lines 13 and
       14 are still spare -- but a line that is assigned and never taken
       is indistinguishable from one that is not wired. This takes it.

       The cause bit used is EVT, which is a LEVEL: the capture queue is
       not empty. So the handler cannot clear it by acknowledging, and
       the mask is what stops the storm. That is deliberate and it is
       what the register map says. */
    int ok = 1;
    cfg_wr(NPUCFG_CTRL, NPUCFG_IN_EN | NPUCFG_OUT_EN);
    ok &= ((cfg_rd(NPUCFG_IRQCAUSE) & NPUCFG_C_EVT) == 0u);

    irq_marker = 0; irq_mcause = 0; irq_count = 0;
    csr_set_mie(1u << (16 + SOC_IRQLINE_NPUCFG));
    csr_set_mstatus(0x8u);                       /* MIE */
    cfg_wr(NPUCFG_IRQMASK, NPUCFG_C_EVT);

    /* One TICK produces no spike (docs/10 section 4.2), so a barrier is
       what makes the queue non-empty. One SYNC, one echo, one
       interrupt. */
    cfg_wr(NPUCFG_EVQ_IN, NPU_EV_SYNC(0x3FFu));

    int spun = 0;
    while (irq_count == 0u && spun < 20000) spun++;

    csr_clr_mstatus(0x8u);
    cfg_wr(NPUCFG_IRQMASK, 0u);

    ok &= (irq_count == 1u);
    ok &= (irq_mcause == SOC_IRQ_NPUCFG);
    ok &= (irq_marker == (SOC_FAST_IRQ_BASE + SOC_IRQLINE_NPUCFG));
    /* And the event is still there: the handler masked the line, it did
       not consume the event. */
    uint32_t w = cfg_rd(NPUCFG_EVQ_OUT);
    ok &= ((w & NPUCFG_EVQ_VALID) != 0u);
    ok &= ((w & 0xFFFFu) == NPU_EV_SYNC(0x3FFu));
    /* Draining it clears the level, which is the whole claim about
       what kind of bit this is. */
    ok &= ((cfg_rd(NPUCFG_IRQCAUSE) & NPUCFG_C_EVT) == 0u);

    if (!ok) { puts_("  npu irq cause="); puthex(irq_mcause);
               puts_(" vec="); puthex(irq_marker);
               puts_(" n="); puthex(irq_count);
               puts_(" ev="); puthex(w);
               puts_(" spun="); puthex((uint32_t)spun); putc_('\n'); }
    check(27, ok);
  }

  {
    /* 28: THE FIRST SPACECRAFT INTERFACE, through the pins.

       docs/60 section 4.1 recorded that this SoC had no interface of
       any kind and that its only functional output was the UART's
       transmit line. This check is the first thing to change that,
       and what it demonstrates is the whole path a peripheral has to
       travel to be real: a slot the map has reserved since docs/39,
       decoded in soc_top.v, a register file written against grip.pdf
       chapter 62, sixteen pins leaving the top level, and a fast
       interrupt line docs/40 assigned before the block existed.

       EVERY READ-BACK HERE GOES THROUGH A PAD. tb_soc.v models the
       pads and a board on which pins 8..15 are wired to pins 0..7.
       soc_gpio.v's DATA register reads the pad and never the OUTPUT
       register, so the value written on pin k is observed on pin k
       through its own pad and on pin k+8 through the board wire. A
       block that folded OUTPUT into DATA would pass a register test
       and fail this one on the high byte. */
    int ok = 1;
    uint32_t cap = cfg_rd(GPIO_CAP);
    ok &= (GPIO_CAP_NLINES(cap) == GPIO_NBITS - 1u);
    ok &= ((cap & GPIO_CAP_IFL) != 0u);           /* it has IFLAG      */
    ok &= (GPIO_CAP_IRQGEN(cap) == 1u);           /* one shared line   */
    ok &= ((cap & (GPIO_CAP_IER | GPIO_CAP_PU)) == 0u);

    /* Out of reset every pin is an input and the board drives them
       low, so DATA is zero and nothing is driven. */
    ok &= (cfg_rd(GPIO_DIR) == 0u);
    ok &= (cfg_rd(GPIO_DATA) == 0u);

    /* Drive 0xA5 on pins 7..0. Pins 15..8 stay inputs and the board
       wires them to 7..0, so DATA must read 0xA5A5: the low byte back
       through our own pads, the high byte through the board. */
    cfg_wr(GPIO_OUTPUT, 0x00A5u);
    cfg_wr(GPIO_DIR, 0x00FFu);
    uint32_t d0 = cfg_rd(GPIO_DATA);
    ok &= (d0 == 0xA5A5u);

    /* OUTPUT bits whose DIR bit is clear must not reach the input
       side: set them and DATA must not move. */
    cfg_wr(GPIO_OUTPUT_OR, 0xFF00u);
    uint32_t d1 = cfg_rd(GPIO_DATA);
    ok &= (d1 == 0xA5A5u);

    /* The XOR alias flips pin 0, and pad 8 follows it. */
    cfg_wr(GPIO_OUTPUT_XOR, 0x0001u);
    uint32_t d2 = cfg_rd(GPIO_DATA);
    ok &= (d2 == 0xA4A4u);

    /* The interrupt: a RISING EDGE on pin 15 -- an input, wired on
       the board to pin 7 -- on fast local line SOC_IRQLINE_GPIO, at
       its own vector. An edge rather than a level, because the
       handler in crt0.S masks the source in mie and does not touch
       the block; with a level the flag would re-arm as soon as it was
       cleared while pin 15 stayed high, which is correct and is what
       the cocotb suite checks, and is not the demonstration here. */
    cfg_wr(GPIO_OUTPUT_AND, 0xFF7Fu);             /* pin 7 low         */
    cfg_wr(GPIO_IFLAG, GPIO_PINS);                /* nothing pending   */
    cfg_wr(GPIO_IEDGE, 1u << 15);
    cfg_wr(GPIO_IPOL, 1u << 15);                  /* rising            */
    cfg_wr(GPIO_IMASK, 1u << 15);
    ok &= (cfg_rd(GPIO_IFLAG) == 0u);

    irq_marker = 0; irq_mcause = 0; irq_count = 0;
    csr_set_mie(1u << (16 + SOC_IRQLINE_GPIO));
    csr_set_mstatus(0x8u);                        /* MIE */
    cfg_wr(GPIO_OUTPUT_OR, 0x0080u);              /* pin 7 rises       */
    int spun = 0;
    while (irq_count == 0u && spun < 20000) spun++;
    csr_clr_mstatus(0x8u);

    ok &= (irq_count == 1u);
    ok &= (irq_mcause == SOC_IRQ_GPIO);
    ok &= (irq_marker == (SOC_FAST_IRQ_BASE + SOC_IRQLINE_GPIO));
    uint32_t fl = cfg_rd(GPIO_IFLAG);
    ok &= (fl == (1u << 15));
    /* Write-one-to-clear, and an edge does not re-arm while the pin
       stays high. The pins are back at 0xA4 -- pin 0 was flipped by
       the XOR above and pin 7 has been dropped and raised again -- and
       the board still mirrors them. */
    cfg_wr(GPIO_IFLAG, 1u << 15);
    ok &= (cfg_rd(GPIO_IFLAG) == 0u);
    ok &= (cfg_rd(GPIO_DATA) == 0xA4A4u);

    /* Leave the pins as they were found: inputs, nothing driven. */
    cfg_wr(GPIO_IMASK, 0u);
    cfg_wr(GPIO_DIR, 0u);
    cfg_wr(GPIO_OUTPUT, 0u);
    ok &= (cfg_rd(GPIO_DATA) == 0u);

    if (!ok) { puts_("  gpio cap="); puthex(cap);
               puts_(" d="); puthex(d0); putc_(' '); puthex(d1);
               putc_(' '); puthex(d2);
               puts_(" irq cause="); puthex(irq_mcause);
               puts_(" vec="); puthex(irq_marker);
               puts_(" n="); puthex(irq_count);
               puts_(" fl="); puthex(fl); putc_('\n'); }
    check(28, ok);
  }

#endif /* !QSPI_DEMO */
#ifdef QSPI_DEMO
  {
    /* 29: THE FLASH, through the real fabric.

       docs/65 section 13 named QSPI the next block and docs/66 built
       it: a register-mode controller in the QSPICTL slot on fast line
       9, with a modelled W25Q128JV on chip select 0 in tb_soc.v. Every
       word below travels core, fabric, APB bridge, slot decode, the
       block's sequencer, the four IO lanes, the model's datasheet
       timing checks and back. The expected words come from
       qspi_image.h, computed at build time from the pattern the image
       was written from, and never from anything the simulation
       produced. */
    int ok = 1;
    uint32_t w[4];
    cfg_wr(QSPI_CONF, QSPI_CONF_DIV(0) | QSPI_CONF_CS(0));

    /* The part identifies itself: 9Fh returns EF 40 18 (8.2.27). */
    ok &= qspi_read(QSPI_CMD_OP(FLASH_OP_JEDEC), 0, w, 3);
    ok &= (w[0] == FLASH_JEDEC_WORD);
    uint32_t id = w[0];

    /* Single-lane reads of the sample words, 03h, including the one at
       an unaligned address. */
    for (int i = 0; i < QSPI_IMG_N_SAMPLES; i++) {
      ok &= qspi_read(FLASH_CMD_READ, qspi_img_sample_addr[i], w, 4);
      if (w[0] != qspi_img_sample_cs0[i]) {
        ok = 0;
        puts_("  qspi 03h at "); puthex(qspi_img_sample_addr[i]);
        puts_(" read "); puthex(w[0]);
        puts_(" want "); puthex(qspi_img_sample_cs0[i]); putc_('\n');
      }
    }

    /* Quad I/O needs QE (8.2.11), and SINCE docs/68 IT IS ALREADY SET
       WHEN THIS PROGRAM STARTS -- the boot loader sets it, because it
       reads the image on four lanes, and the volatile write (50h, 31h;
       8.2.5) it uses is not undone by anything short of a power cycle.
       docs/66 checked that SR2 reads 0 "out of the box" and that was
       true of a part nothing had touched; it is now a check that the
       loader did NOT run, and it failed for exactly that reason the
       first time this program was loaded rather than fetched.
       What is checked instead is the property that still holds and
       that the application actually depends on: QE is set on entry,
       and setting it again is idempotent. */
    uint32_t sr2_before = flash_sr(FLASH_OP_RDSR2);
    ok &= (sr2_before == FLASH_SR2_QE);
    ok &= qspi_cmd(FLASH_OP_VWREN, 0, 0);
    ok &= qspi_cmd(FLASH_OP_WRSR2, FLASH_SR2_QE, 1);
    uint32_t sr2_after = flash_sr(FLASH_OP_RDSR2);
    ok &= (sr2_after == FLASH_SR2_QE);

    /* The aligned samples again, on four lanes: EBh with the mode
       byte and four dummy clocks, and 6Bh with eight. */
    for (int i = 0; i < QSPI_IMG_N_SAMPLES; i++) {
      if (qspi_img_sample_addr[i] & 3u) continue;
      ok &= qspi_read(FLASH_CMD_QIO, qspi_img_sample_addr[i], w, 4);
      if (w[0] != qspi_img_sample_cs0[i]) {
        ok = 0;
        puts_("  qspi EBh at "); puthex(qspi_img_sample_addr[i]);
        puts_(" read "); puthex(w[0]); putc_('\n');
      }
      ok &= qspi_read(FLASH_CMD_QOUT, qspi_img_sample_addr[i], w, 4);
      if (w[0] != qspi_img_sample_cs0[i]) {
        ok = 0;
        puts_("  qspi 6Bh at "); puthex(qspi_img_sample_addr[i]);
        puts_(" read "); puthex(w[0]); putc_('\n');
      }
    }

    /* A multi-word frame, 0Bh with its eight dummy clocks: the first
       two samples are consecutive words. */
    ok &= qspi_read(FLASH_CMD_FAST, qspi_img_sample_addr[0], w, 8);
    ok &= (w[0] == qspi_img_sample_cs0[0] && w[1] == qspi_img_sample_cs0[1]);

    /* Chip select 1 goes to nothing on this board: the lanes read as
       their pull-ups. */
    cfg_wr(QSPI_CONF, QSPI_CONF_DIV(0) | QSPI_CONF_CS(1));
    ok &= qspi_read(QSPI_CMD_OP(FLASH_OP_JEDEC), 0, w, 3);
    ok &= (w[0] == 0x00FFFFFFu);
    cfg_wr(QSPI_CONF, QSPI_CONF_DIV(0) | QSPI_CONF_CS(0));

    /* A CMD write while a frame is paused at DR is refused and flagged
       LOST; the frame runs on with the values it captured. */
    cfg_wr(QSPI_ADDR, qspi_img_sample_addr[0]);
    cfg_wr(QSPI_CMD, FLASH_CMD_READ | QSPI_CMD_LEN(8));
    ok &= qspi_wait(QSPI_ST_DR);
    cfg_wr(QSPI_CMD, QSPI_CMD_OP(FLASH_OP_JEDEC) | QSPI_CMD_LEN(3));
    uint32_t st = cfg_rd(QSPI_STAT);
    ok &= ((st & QSPI_ST_LOST) != 0u);
    cfg_wr(QSPI_STAT, QSPI_ST_LOST);
    w[0] = cfg_rd(QSPI_RX);
    ok &= qspi_wait(QSPI_ST_DR);
    w[1] = cfg_rd(QSPI_RX);
    ok &= qspi_wait(QSPI_ST_DONE);
    cfg_wr(QSPI_STAT, QSPI_ST_DONE);
    ok &= (w[0] == qspi_img_sample_cs0[0] && w[1] == qspi_img_sample_cs0[1]);
    ok &= ((cfg_rd(QSPI_STAT) & QSPI_ST_LOST) == 0u);

    /* The interrupt: a level of DONE or DR under IEN, on the fast local
       line the frozen map assigns, at its own vector. The first event
       of a read is DR, so the handler (which masks the line in mie and
       touches no register) is entered once, and the word is still
       there afterwards. */
    irq_marker = 0; irq_mcause = 0; irq_count = 0;
    csr_set_mie(1u << (16 + SOC_IRQLINE_QSPICTL));
    csr_set_mstatus(0x8u);                       /* MIE */
    cfg_wr(QSPI_CTRL, QSPI_CTRL_IEN);
    cfg_wr(QSPI_CMD, QSPI_CMD_OP(FLASH_OP_JEDEC) | QSPI_CMD_LEN(3));
    int spun = 0;
    while (irq_count == 0u && spun < 20000) spun++;
    csr_clr_mstatus(0x8u);
    ok &= (irq_count == 1u);
    ok &= (irq_mcause == SOC_IRQ_QSPICTL);
    ok &= (irq_marker == (SOC_FAST_IRQ_BASE + SOC_IRQLINE_QSPICTL));
    ok &= ((cfg_rd(QSPI_STAT) & QSPI_ST_DR) != 0u);
    w[0] = cfg_rd(QSPI_RX);
    ok &= (w[0] == FLASH_JEDEC_WORD);
    ok &= qspi_wait(QSPI_ST_DONE);
    cfg_wr(QSPI_STAT, QSPI_ST_DONE);
    cfg_wr(QSPI_CTRL, 0);

    if (!ok) { puts_("  qspi id="); puthex(id);
               puts_(" sr2="); puthex(sr2_before); putc_(' '); puthex(sr2_after);
               puts_(" st="); puthex(st);
               puts_(" irq cause="); puthex(irq_mcause);
               puts_(" vec="); puthex(irq_marker);
               puts_(" n="); puthex(irq_count); putc_('\n'); }
    check(29, ok);
  }

  {
    /* 30: THE NPU FED FROM THE FLASH.

       docs/51 section 14 item 4: "there is no QSPI controller; weights
       are loaded a register at a time" from arrays in the ROM image.
       This is the first time the NPU has been fed from where a flight
       part would feed it. The weight image sits in the modelled flash
       at QSPI_IMG_WIMG_OFF -- a 16-byte header, then the docs/51
       weight words -- written by hw/soc/flow/gen_flash_image.py from
       the SAME generator that fills the ROM's arrays. The program
       reads it on four lanes through the QSPI controller into RAM,
       checks the header, the checksum and (as a diagnostic) equality
       with the ROM's copy, and then runs THE SAME INFERENCE as check
       26 with the flash-loaded words. The pass criterion is the golden
       model's answer, not agreement with check 26. */
    int ok = 1;
    static uint32_t hdr[4];
    static uint32_t fw_lo[NPUV_N_WWORDS], fw_hi[NPUV_N_WWORDS];
    ok &= qspi_read(FLASH_CMD_QIO, QSPI_IMG_WIMG_OFF, hdr, 16);
    ok &= (hdr[0] == QSPI_IMG_WIMG_MAGIC);
    ok &= (hdr[1] == (uint32_t)NPUV_N_WWORDS);
    ok &= (hdr[2] == ((uint32_t)NPUV_N_AXONS << 16 | (uint32_t)NPUV_N_NEURONS));
    ok &= (hdr[2] == QSPI_IMG_WIMG_GEOM);

    /* The words, one frame, pulled through DR one word at a time. */
    uint32_t csum = 0;
    if (ok) {
      cfg_wr(QSPI_ADDR, QSPI_IMG_WIMG_OFF + 16u);
      cfg_wr(QSPI_CMD, FLASH_CMD_QIO | QSPI_CMD_LEN(8u * NPUV_N_WWORDS));
      for (int i = 0; i < NPUV_N_WWORDS; i++) {
        ok &= qspi_wait(QSPI_ST_DR);
        fw_lo[i] = cfg_rd(QSPI_RX);
        ok &= qspi_wait(QSPI_ST_DR);
        fw_hi[i] = cfg_rd(QSPI_RX);
        csum += fw_lo[i]; csum += fw_hi[i];
      }
      ok &= qspi_wait(QSPI_ST_DONE);
      cfg_wr(QSPI_STAT, QSPI_ST_DONE);
    }
    ok &= (csum == hdr[3]);
    ok &= (hdr[3] == QSPI_IMG_WIMG_CSUM);
    int same = 1;
    for (int i = 0; i < NPUV_N_WWORDS; i++)
      same &= (fw_lo[i] == npuv_wlo[i] && fw_hi[i] == npuv_whi[i]);
    if (!same) {
      ok = 0;
      puts_("  weight image differs from the ROM copy\n");
    }
    if (!ok) { puts_("  qspi wimg hdr="); puthex(hdr[0]); putc_(' ');
               puthex(hdr[1]); putc_(' '); puthex(hdr[2]); putc_(' ');
               puthex(hdr[3]); puts_(" csum="); puthex(csum); putc_('\n'); }

    /* And the inference, with what the flash delivered. */
    if (ok) ok &= npu_inference(fw_lo, fw_hi, "npu from flash: ");
    check(30, ok);
  }
#endif /* QSPI_DEMO */
#endif

  check(11, trap_saw_rvc == 0u);   /* handler never had to guess a width */

  puts_("checks run: ");  puthex(checks);
  puts_("  fail mask: "); puthex(fails);
  putc_('\n');
  puts_(fails ? "RESULT FAIL\n" : "RESULT PASS\n");
  return (int)fails;
}
