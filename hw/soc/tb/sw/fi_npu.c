// The workload the NPU-connection fault-injection campaign of docs/52
// runs.
//
// WHY THIS IS NOT fi_workload.c AND NOT test_ibex.c
//
// `hw/soc/tb/sw/fi_workload.c` is docs/42's kernel. It exercises the
// CORE and touches nothing in the NPU, so an upset in the transport, the
// event engine or the node window would be MASKED in every draw. It is
// the wrong workload for this campaign for the same reason test_ibex.c
// was the wrong workload for that one.
//
// `hw/soc/tb/sw/test_ibex.c` check 26 IS this inference, and it is
// 213,971 cycles with 27 checks and four deliberate traps. All three
// properties are wrong for a campaign that runs the program a thousand
// times and treats an unexpected trap as an announcement.
//
// So this is a third workload: the docs/51 section 7 demonstration and
// nothing else, as short as it can be made, with everything the campaign
// needs published as a word.
//
// THE ORACLE IS THE GOLDEN MODEL, AND THAT IS THE DIFFERENCE FROM docs/42
//
// docs/42 section 3 had to settle for "an undeposited run of the same
// program on the same design" as its oracle, and said so at length:
// it measures DEVIATION and not CORRECTNESS, and it licenses no claim
// about latent corruption -- "an upset that leaves a register wrong in a
// way THIS PROGRAM never reads is MASKED here".
//
// Here the oracle is available. `hw/soc/flow/gen_npu_vectors.py` runs
// `sw/golden/lif_core.py` -- which docs/10 section 13 makes the
// normative executable form of the section 4 equations -- at BUILD TIME
// and emits the expected event stream and the expected neuron state file
// as constants. This program compares against those constants. So:
//
//   * a corrupted inference is a WRONG ANSWER against the specification,
//     not merely a difference from another run of the same RTL;
//   * and the neuron state file read back at the end is an
//     ARCHITECTURAL-STATE oracle for the NPU. An upset that leaves V or
//     R wrong without producing a wrong spike inside this stimulus is
//     caught here. docs/16 section 1.6 names that class and keeps
//     `spikes_ok` and `state_ok` apart; this program does the same, in
//     two bits of `fi_mask`.
//
// That is what the campaign spends the extra checks on, and docs/52
// section 5.2 measures how many records it actually separated.
//
// THE SELF-CHECKS ARE A DETECTION CHANNEL *AND* AN ORACLE HERE, AND THE
// TWO ROLES ARE KEPT APART ANYWAY
//
// `fi_mask` is nonzero when the program noticed. That is a detection
// channel, exactly as in docs/42. What is different is that the thing it
// compared against is the specification, so the campaign is additionally
// entitled to read `fi_mask` bits 1..3 as "the inference was wrong".
// `hw/soc/fi/npu_campaign.py` uses them in both roles and labels which
// is which; it still decides MASKED from the whole compared result and
// never from `fi_mask` alone.
//
// THE WORDS THE TESTBENCH READS
//
//   fi_phase   0 before the measured kernel, 1 during it, 2 after. The
//              testbench records the cycle of each transition and the
//              campaign draws inside [1, 2), so the window is MEASURED
//              and not assumed -- docs/41 section 8.1's last honesty
//              clause, inherited unchanged.
//   fi_sig     a 32-bit fold of the whole collected event stream and the
//              whole neuron state file. The program's answer.
//   fi_mask    which self-checks failed. Zero in the clean run.
//   fi_rounds_done  frames whose barrier came back. 6 in the clean run.
//
// and six more that are TELEMETRY THE PROGRAM READ WITH A LOAD, not
// bench observations: fi_nev, fi_cause, fi_drop, fi_ovf, fi_oor,
// fi_status. docs/44 section 8.2 makes the distinction that matters
// here -- a counter a testbench reads hierarchically is not a counter an
// operator can see, and these six are the ones an operator can.
//
// WHAT IS DELIBERATELY NOT ARMED
//
// The NPUCFG interrupt. `irq_mask` resets to zero and this program never
// writes it, so the interrupt line never rises. That is not laziness: an
// armed interrupt would put the cause register's contents on the
// program's control flow, and the campaign wants the cause register
// measured as a REPORT -- what the operator is told -- rather than as a
// branch. docs/52 section 9 states what that leaves uncovered.

#include <stdint.h>

#include "soc_memmap.h"
#include "soc_timers.h"
#include "soc_npucfg.h"

/* Generated on every build by hw/soc/flow/gen_npu_vectors.py:
   npu_regs.h is the node register map from regmap/regmap.yaml, and
   npu_vectors.h is the stimulus together with the answer
   sw/golden/lif_core.py computes for it. */
#include "npu_regs.h"
#include "npu_vectors.h"

// GRLIB APBUART, grip.pdf table 126, the same offsets fi_workload.c uses.
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
// to stage 2. Same value and same reasoning as fi_workload.c: the reset
// default is 1,048,576 clocks, which protects the boot path of every run
// and is longer than any budget a campaign can afford to wait through.
#ifndef FI_WDOG_RELOAD
#define FI_WDOG_RELOAD 127u
#endif

// The bound on a barrier wait, in polls of NPUCFG.EVQ_OUT.
//
// MEASURED AND NOT GUESSED. The program publishes the largest number of
// consecutive empty polls it saw in `fi_spins`, and hw/soc/fi/
// npu_campaign.py control 2 prints it from the clean run and refuses to
// proceed if the bound is not comfortably above it. The clean run's
// largest is 21 [fact], and the constant below is eight times that. A
// bound chosen without the measurement is either a hang detector that
// fires on a healthy run -- which would make every injected run's
// classification meaningless -- or one so loose that a wedged engine
// costs more simulated time than the campaign has.
#ifndef FI_SPIN_MAX
#define FI_SPIN_MAX 168
#endif

// Bound on the STATE_CLR poll, in reads of the node's STATUS register.
// Each read is a 176-cycle serial frame, so this is expensive to get
// wrong in the other direction; the clean run needs one.
#ifndef FI_IDLE_MAX
#define FI_IDLE_MAX 16
#endif

// -------------------------------------------------------------------
// The words the testbench reads. Not static: hw/soc/flow/fi_npu.sh
// resolves their addresses out of the ELF with `nm`, exactly as
// fi_core.sh does for docs/42's, so no address is written twice.
// -------------------------------------------------------------------
volatile uint32_t fi_phase;
volatile uint32_t fi_sig;
volatile uint32_t fi_mask;
volatile uint32_t fi_rounds_done;

/* Telemetry the program READ, with a load instruction it executed.
 * tb_soc_npu_fi.v additionally reads the same state hierarchically, and
 * docs/52 section 6.3 is the two columns beside each other: what the
 * hardware did, and what an operator would have been told about it. */
volatile uint32_t fi_nev;      /* events collected */
volatile uint32_t fi_cause;    /* NPUCFG.IRQ_CAUSE at the end */
volatile uint32_t fi_status;   /* NPUCFG.STATUS at the end */
volatile uint32_t fi_drop;     /* NPUCFG.CNT_DROP: the SoC queues' drops */
volatile uint32_t fi_ovf;      /* the die's CNT_EVQ_OVF */
volatile uint32_t fi_oor;      /* the die's CNT_AXON_OOR */
volatile uint32_t fi_cnt;      /* NPUCFG.CNT: {out, in}, the engine's count */
volatile uint32_t fi_spins;    /* the largest empty-poll run seen */

/* The collected stream, in .bss so crt0 zeroes it on every boot and a
 * re-run after a watchdog reset starts from the memory the first run
 * did. Sized with slack so an engine that emits extra events is caught
 * as a length mismatch rather than by scribbling past the array. */
#define GOT_N (NPUV_N_EXPECT + 8)
static uint16_t got[GOT_N];

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
// NPU access.
//
// The node register window is ORDINARY MEMORY to this program: a load or
// a store at SOC_NPU_BASE + node*0x1000 + offset. What is behind it is a
// 176-cycle serial frame, and the SLAVE holds the response, so the core
// stalls on the load exactly as it would on a slow memory.
//
// THE KICK IS INSIDE THE ACCESSOR AND THAT IS A DECISION. One node
// access is 176 clocks and the timeout this program arms is 2,048, so a
// bring-up sequence of two dozen back-to-back accesses would expire a
// watchdog on a healthy run if the kicks were only at the outer loop.
// Kicking per access makes the longest interval between kicks one access
// and puts the escalation ladder squarely on "the accesses stopped",
// which is the failure this campaign is trying to see. It also means, as
// in docs/42 section 8.1, that a machine which keeps making accesses
// keeps kicking however wrong its answers are -- and docs/52 section 9
// says so rather than leaving it to be discovered.
// -------------------------------------------------------------------
static void npu_wr(uint32_t off, uint32_t v) {
  *(volatile uint32_t *)NPU_NODE(0, off) = v;
  wdog_kick();
}
static uint32_t npu_rd(uint32_t off) {
  uint32_t v = *(volatile uint32_t *)NPU_NODE(0, off);
  wdog_kick();
  return v;
}
static uint32_t cfg_rd(uint32_t a) { return *(volatile uint32_t *)a; }
static void cfg_wr(uint32_t a, uint32_t v) { *(volatile uint32_t *)a = v; }

// Bit numbers in fi_mask. One per self-check, so a failure says which,
// and so the campaign can separate the classes docs/16 section 1.6
// separates.
#define F_BRINGUP (1u << 0)   // the node did not come up as specified
#define F_LEN     (1u << 1)   // the stream is the wrong length
#define F_STREAM  (1u << 2)   // an event differs from the golden model
#define F_STATE   (1u << 3)   // a neuron state word differs from the model
#define F_TELEM   (1u << 4)   // a fault counter or cause bit moved
#define F_CNT     (1u << 5)   // the hardware's own counts disagree
#define F_TIMEOUT (1u << 6)   // a barrier never came back

/* Bring the node up in the order docs/10 section 11.1 requires: state
   clear, configure, load weights, enable. Configuration registers are
   LOCKED while BUSY (docs/10 section 6), so the enable is last and the
   state clear has to complete first. This is test_ibex.c's npu_bring_up
   with the console reporting removed. */
static uint32_t npu_bring_up(void) {
  uint32_t bad = 0u;
  int i;

  npu_wr(NPU_CTRL, 1u << NPU_BIT_CTRL_STATE_CLR);
  for (i = 0; i < FI_IDLE_MAX; i++)
    if ((npu_rd(NPU_STATUS) & (1u << NPU_BIT_STATUS_BUSY)) == 0u) break;
  if (i == FI_IDLE_MAX) bad = F_BRINGUP;

  npu_wr(NPUV_OFF_CFG_AXON,      NPUV_VAL_CFG_AXON);
  npu_wr(NPUV_OFF_CFG_THRESH,    NPUV_VAL_CFG_THRESH);
  npu_wr(NPUV_OFF_CFG_VRESET,    NPUV_VAL_CFG_VRESET);
  npu_wr(NPUV_OFF_CFG_LEAK,      NPUV_VAL_CFG_LEAK);
  npu_wr(NPUV_OFF_CFG_SYNSHIFT,  NPUV_VAL_CFG_SYNSHIFT);
  npu_wr(NPUV_OFF_CFG_REFR,      NPUV_VAL_CFG_REFR);
  npu_wr(NPUV_OFF_CFG_FLAGS,     NPUV_VAL_CFG_FLAGS);
  npu_wr(NPUV_OFF_PASS_TILE_OFF, NPUV_VAL_PASS_TILE_OFF);

  /* Read one back. A configuration write that was refused is otherwise
     invisible until the arithmetic comes out wrong, and then it looks
     like an arithmetic defect. docs/51 section 7.2. */
  if (npu_rd(NPUV_OFF_CFG_THRESH) != NPUV_VAL_CFG_THRESH) bad |= F_BRINGUP;

  npu_wr(NPU_W_ADDR, 0u);
  for (i = 0; i < NPUV_N_WWORDS; i++) {
    npu_wr(NPU_W_DATA_LO, npuv_wlo[i]);
    npu_wr(NPU_W_DATA_HI, npuv_whi[i]);
  }
  /* W_ADDR wraps to zero on the last commit (pilot_top.v deviation D3)
     and a clean image must produce no ECC event. */
  if (npu_rd(NPU_W_ADDR) != (uint32_t)NPUV_WADDR_AFTER_LOAD) bad |= F_BRINGUP;
  if (npu_rd(NPU_CNT_SEC) != 0u) bad |= F_BRINGUP;
  if (npu_rd(NPU_CNT_DED) != 0u) bad |= F_BRINGUP;

  npu_wr(NPU_CTRL, (1u << NPU_BIT_CTRL_EN) | (1u << NPU_BIT_CTRL_SCRUB_EN));
  return bad;
}

/* Run the stimulus and collect the output stream. Returns the number of
   events collected; sets *bad's F_TIMEOUT if a barrier never came back.

   The read loop has NO TIMING KNOWLEDGE. docs/10 section 7.1: when the
   node consumes a SYNC every prior event is fully processed and the
   barrier is echoed downstream, so the loop reads until the echo. The
   spin bound is a hang detector and nothing else, and its value is a
   measurement of the clean run (see FI_SPIN_MAX). */
static int npu_run(uint32_t *bad) {
  int n = 0, k = 0, f;
  uint32_t worst = 0u;

  for (f = 0; f < NPUV_N_FRAMES; f++) {
    int i;
    uint16_t barrier = NPU_EV_SYNC(f);
    uint32_t spins = 0u;

    for (i = 0; i < npuv_inj_len[f]; i++)
      cfg_wr(NPUCFG_EVQ_IN, npuv_inject[k++]);

    for (;;) {
      uint32_t w = cfg_rd(NPUCFG_EVQ_OUT);
      if (w & NPUCFG_EVQ_VALID) {
        if (n < GOT_N) got[n] = (uint16_t)(w & 0xFFFFu);
        n++;
        if (spins > worst) worst = spins;
        spins = 0u;
        if ((uint16_t)(w & 0xFFFFu) == barrier) break;
      } else if (++spins > (uint32_t)FI_SPIN_MAX) {
        *bad |= F_TIMEOUT;
        if (spins > worst) worst = spins;
        fi_spins = worst;
        return n;
      }
      wdog_kick();
    }
    fi_rounds_done = (uint32_t)(f + 1);
  }
  fi_spins = worst;
  return n;
}

// -------------------------------------------------------------------
int main(void) {
  uint32_t mask = 0u;
  uint32_t sig  = 0x4E505543u;      /* "NPUC", a constant to fold into */
  int n, i;

  /* FIRST, before anything else, arm the short timeout. On a boot that
     follows a watchdog reset the reload has been restored to the maximum
     (docs/40 section 7.2), so this write is what makes the second and
     later ladders as short as the first. */
  *(volatile uint32_t *)WDOG_RLD = WDOG_W(FI_WDOG_RELOAD);
  wdog_kick();

  uart_init();

  /* The measured window opens here, BEFORE the bring-up, because the
     bring-up is part of what this campaign is measuring: a corrupted
     weight-word write is exactly the failure docs/51 section 18 says the
     campaign could invalidate a decision over. */
  fi_phase = 1u;

  mask |= npu_bring_up();

  cfg_wr(NPUCFG_CTRL, NPUCFG_IN_EN | NPUCFG_OUT_EN);
  n = npu_run(&mask);
  fi_nev = (uint32_t)n;

  /* THE ANSWER, against sw/golden/lif_core.py's constants. */
  if (n != NPUV_N_EXPECT) {
    mask |= F_LEN;
  } else {
    for (i = 0; i < NPUV_N_EXPECT; i++)
      if (got[i] != npuv_expect[i]) mask |= F_STREAM;
  }
  for (i = 0; i < n && i < GOT_N; i++)
    sig = (sig * 16777619u) ^ (uint32_t)got[i];

  /* The whole neuron state file, against the same model. This is the
     ARCHITECTURAL-STATE oracle docs/42 section 9 says its own campaign
     did not have: an upset that leaves V wrong without producing a wrong
     spike inside this stimulus is caught here and would be MASKED under
     an output-only oracle. docs/16 section 1.6 keeps the two apart and
     so does F_STATE against F_STREAM. */
  for (i = 0; i < NPUV_N_NEURONS; i++) {
    uint32_t w;
    npu_wr(NPU_N_ADDR, (uint32_t)i);
    w = npu_rd(NPU_N_DATA) & 0x000FFFFFu;
    if (w != npuv_state[i]) mask |= F_STATE;
    sig = (sig * 16777619u) ^ w;
  }

  /* What the operator would be told. Every one of these is a load this
     core executed, not a hierarchical read by a testbench. */
  fi_status = cfg_rd(NPUCFG_STATUS);
  fi_cause  = cfg_rd(NPUCFG_IRQCAUSE);
  fi_cnt    = cfg_rd(NPUCFG_CNT);
  fi_drop   = cfg_rd(NPUCFG_CNT_DROP);
  fi_ovf    = npu_rd(NPU_CNT_EVQ_OVF);
  fi_oor    = npu_rd(NPU_CNT_AXON_OOR);

  if ((fi_cause & (NPUCFG_C_ERR | NPUCFG_C_SEC | NPUCFG_C_DED
                   | NPUCFG_C_TMR | NPUCFG_C_INJ_OVF | NPUCFG_C_FETCH_ER))
      || fi_drop || fi_ovf || fi_oor)
    mask |= F_TELEM;

  /* The hardware's own count of what it delivered and drained, against
     the stream this program collected. A second path to the same
     conclusion, and the one that catches an engine that produced the
     right events by the wrong route. */
  if ((fi_cnt & 0xFFFFu) != (uint32_t)NPUV_N_INJECT)          mask |= F_CNT;
  if (((fi_cnt >> 16) & 0xFFFFu) != (uint32_t)n)              mask |= F_CNT;
  if (fi_rounds_done != (uint32_t)NPUV_N_FRAMES)              mask |= F_CNT;

  /* And closes here, before anything is printed. A deposit drawn after
     this point would land after the program's answer was already fixed
     -- docs/41 section 8.4 records that defect presenting as a design
     result. */
  fi_phase = 2u;

  fi_sig  = sig;
  fi_mask = mask;

  puts_("S");
  puthex(sig);
  puts_("M");
  puthex(mask);
  puts_("\n");

  /* crt0.S posts this in exit_code beside the exit magic and sleeps. */
  return (int)mask;
}
