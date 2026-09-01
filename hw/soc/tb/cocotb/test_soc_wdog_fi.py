"""Fault injection into the watchdog's own state.

WHY THIS EXISTS

`docs/40-interrupts-timers-watchdog.md` section 10 item 2 stated the gap
this campaign closes: "the block whose job is to catch upsets is itself
unprotected". `hw/soc/rtl/soc_wdog.v` W6 is the answer, and W6 makes two
claims that a proof cannot settle and an argument should not be trusted
with:

  1. an upset in the PROTECTED word is masked at the ports and counted;
  2. an upset in the DELIBERATELY UNPROTECTED state -- `counter`,
     `reload`, `pre` -- is bounded in time rather than permanent: the
     block recovers, the escalation ladder still completes, and the
     watchdog is still armed at the end.

The second is the one worth measuring, because it is the price of the
decision not to protect them. An argument that "the block rewrites it
anyway" is exactly the kind of reasoning
`docs/16-fault-injection-campaign.md` exists to replace with a number.

METHOD, adapted from docs/16 sections 1.2 to 1.6

  * The DUT is `soc_wdog` itself. **Only the stimulus reaches into the
    hierarchy.** Every observation is one a bench with a logic analyser
    and a register read could make: `nmi_o`, `rst_req_o`, `wdog_no`, and
    the four-bit register port. There is no pin that injects an upset.
  * Per injection: power-on reset, bring-up (program a short reload and
    kick, so the ladder takes hundreds of clocks instead of a million),
    then the workload, with one bit of one flip-flop XORed at a
    seeded-random cycle inside the measured window.
  * The GOLDEN MODEL decides right from wrong, always. It is a run of
    the same workload with no deposit, recorded once. The design's own
    flags only decide whether a wrong answer was *announced*; they are
    never allowed to declare an answer correct, which is why every
    record carries `out_ok` separately from its class.
  * Classification, exactly one class per injection, in this order:

      HANG       a bounded wait expired and nothing was flagged
      DETECTED   WDOGSTAT.TMRERR set, or TMRCNT nonzero
      SDC        the trace or the final reads differ from golden and
                 nothing was flagged
      CORRECTED  trace and final reads match golden and TMRCNT moved
      MASKED     matches golden and nothing moved

  * Four further per-record facts, because five classes cannot carry
    them and because the W6 argument is about them and not about the
    class:

      order_ok     the same escalation events in the same order,
                   ignoring WHEN they happened. A timing upset that
                   moves stage 1 by forty clocks is SDC against a
                   cycle-exact oracle and is not a lost backstop.
      ladder_ok    all three stages were still reached.
      armed_at_end EN still reads 1 and WDOGSTAT.DISABLED still reads 0.
                   This is the single post-condition the whole block
                   exists for, and the criterion in test_zz_summary that
                   would fail if `dis_q` were left unprotected.
      final_ok     the end-of-run register reads match golden, which is
                   the "bounded in time" half of claim 2.

WHAT THIS CAMPAIGN DOES **NOT** COVER

  * It is RTL, single-bit, flip-flop only. No gate-level netlist, no
    back-annotated timing, no multi-bit strike, no SET in combinational
    logic, no upset in the voter itself -- which is combinational and
    has no state, so an SET there is a different fault model this
    harness cannot express. docs/16 section 7.4 makes the same
    disclaimer at length.
  * It says nothing about RATES. Every number here is a conditional
    probability given that an upset landed in the injection window, on a
    uniform choice of target and bit. docs/16 section 7.5.
  * DETECTED depends on someone looking. WDOGSTAT.TMRERR and TMRCNT are
    registers; nothing raises an interrupt or a pin on them, and the
    software that would read them may be the thing that failed. docs/16
    section 7.6.
  * One workload, one parameter point (WIDTH 8, PRESCALE 4, RST_CYCLES
    8, ESCALATE 2), one seed. `soc_top.v` instantiates WIDTH 16 and
    PRESCALE 16 and nothing here runs at those.
  * It cannot fail because a replica vanished in synthesis. Every
    target path exists in the RTL whatever the netlist holds.
    `sw/tests/test_soc_synthesis_guards.py` is the separate,
    netlist-level criterion for that class and neither substitutes for
    the other.
  * The injection window is the workload. An upset during the bring-up
    writes, or during power-on reset, is not covered.
"""

import os
import random
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

# Parameters the Makefile builds the block with.
WIDTH = 8
PRESCALE = 4
RST_CYCLES = 8
ESCALATE = 2
KEY = 0xA51F

# PROT_W as soc_wdog.v computes it: dis_q, dis_seen, nmi_pend, rst_seen,
# tmr_err (5 x 1 bit), tmr_count (4), rst_count (8), rst_hold (RST_W),
# and -- added by docs/43 -- win_s (4), early_seen, bud_arm, bud_seen.
RST_W = max(1, (RST_CYCLES + 1 - 1).bit_length())
KICK_W = 8
P6_W = 5 + 4 + 8 + RST_W
PROT_W = P6_W + 4 + 3
PRE_W = max(1, (PRESCALE - 1).bit_length())

# One-hot register select, as soc_gptimer.v drives it.
SEL_CNT, SEL_RLD, SEL_CTRL, SEL_STAT, SEL_WIN = 1, 2, 4, 8, 16

# GRLIB timer control bits (grip.pdf table 463).
B_EN, B_RS, B_LD, B_IE, B_IP = 1, 2, 4, 8, 16

# WDOGSTAT, this project's extension.
ST_NMI, ST_WDOGRST, ST_ESCALATED, ST_DISABLED, ST_TMRERR = 1, 2, 4, 8, 16
ST_RSTCNT_SH, ST_RSTCNT_MASK = 8, 0xFF
ST_TMRCNT_SH, ST_TMRCNT_MASK = 16, 0xF

CLK_NS = 10
T_DRIVE = 1
T_SAMPLE = 8
T_INJECT = 4          # inside the cycle, after the drive and before the
                      # sample, so a deposit never races a register write

# A short reload, so a full timeout is (15 + 1) * 4 = 64 clocks instead
# of 1,024 and the whole ladder fits in a few hundred.
RELOAD_SHORT = 15
TIMEOUT_CLK = (RELOAD_SHORT + 1) * PRESCALE

# Bounded waits. A wait that expires is a HANG record, never a hung
# suite -- docs/16 section 1.3, "every loop in the harness is bounded".
#
# Sized against the LONGEST timeout the block can be talked into rather
# than against the short one the workload programs, because that is what
# an upset in `counter` or `reload` can stretch a wait to: W2 makes
# 2^WIDTH * PRESCALE a constant of the netlist, and no upset can exceed
# it. A budget sized to the short timeout would report a bounded delay
# as a HANG, which is the opposite of what this campaign is measuring.
WAIT_BUDGET = 2 * (1 << WIDTH) * PRESCALE

# One seed drives every randomised injection cycle; the targets, the
# bits and the phase counts are constants. docs/16 section 1.7.
SEED = 0x41F12026
DRAWS_PER_BIT = 2


def val(sig):
    s = str(sig.value)
    if any(c not in "01" for c in s):
        raise AssertionError("non-binary value {!r} on {}".format(s, sig._path))
    return int(s, 2)


def keyed(v):
    return (KEY << 16) | (v & 0xFFFF)


# =====================================================================
# the device, driven only through its ports
# =====================================================================
class Wdog:
    def __init__(self, dut):
        self.dut = dut

    async def _access(self, sel, we, data):
        dut = self.dut
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
        dut.sel_i.value = sel
        dut.we_i.value = we
        dut.wdata_i.value = data
        await Timer(T_SAMPLE - T_DRIVE, unit="ns")
        out = val(dut.rdata_o)
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
        dut.sel_i.value = 0
        dut.we_i.value = 0
        dut.wdata_i.value = 0
        return out

    async def read(self, sel):
        return await self._access(sel, 0, 0)

    async def write(self, sel, data):
        return await self._access(sel, 1, keyed(data))

    async def kick(self):
        await self.write(SEL_CTRL, B_LD)

    async def ack(self):
        await self.write(SEL_STAT, ST_NMI)


async def por(dut, dis=0):
    """Apply and release power-on reset. Does NOT start a clock: one
    Clock driver per call would shorten the effective period on every
    iteration, which docs/40 section 7.5 records costing a day."""
    dut.rst_por_ni.value = 0
    dut.dis_i.value = dis
    dut.sel_i.value = 0
    dut.we_i.value = 0
    dut.wdata_i.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.rst_por_ni.value = 1
    await RisingEdge(dut.clk_i)


# =====================================================================
# targets
# =====================================================================
# Every entry is (group, hierarchical path, width). The PROTECTED group
# names each replica's STORAGE register and never the voted `prot` wire.
#
# That distinction is not pedantry: docs/16 section 1.8 records this
# campaign's ancestor depositing into a continuously driven voter output
# twice and reporting the result as if it said something about the
# replicas. A deposit on `prot` is overwritten by the voter in the same
# delta cycle and comes back MASKED, which is exactly the quiet nothing
# a mis-targeted injector produces. test_00_control asserts that no
# target is the voted wire.
# Every entry is (group, path, bit indices), and the bits are listed
# rather than counted so the counterfactual below can leave out the ones
# the unhardened design does not have.
PROTECTED = [
    ("prot_a", "g_prot_tmr.u_prot_a.bits", tuple(range(PROT_W))),
    ("prot_b", "g_prot_tmr.u_prot_b.bits", tuple(range(PROT_W))),
    ("prot_c", "g_prot_tmr.u_prot_c.bits", tuple(range(PROT_W))),
]

# Deliberately unprotected, soc_wdog.v W6's second list. Injected on
# purpose: the decision not to protect them is only a decision if its
# price is measured.
UNPROTECTED = [
    ("counter", "counter", tuple(range(WIDTH))),
    ("reload", "reload", tuple(range(WIDTH))),
    ("pre", "pre", tuple(range(PRE_W))),
    # docs/43. W8's kick budget down-counter is left unprotected by the
    # same criterion `counter` is -- the block rewrites it, an upset
    # upward buys a runaway at most 255 further kicks before the budget
    # bites anyway, and an upset downward is a spurious ladder, which is
    # loud. That is a decision, so it is measured here rather than
    # asserted. This workload never arms the budget, so what these
    # injections show is that an upset in a disarmed counter changes
    # nothing at the ports -- which is a weaker statement than the one
    # docs/43 section 10 would like and it says so.
    ("kick_left", "kick_left", tuple(range(KICK_W))),
]

# The W6 report fields inside the protected word: the sticky mismatch
# flag at bit 4 and the four-bit saturating counter above it.
REPORT_BITS = tuple(range(4, 9))

# THE COUNTERFACTUAL. With SOC_WDOG_FI_UNHARDENED set, and the block
# built with -Psoc_wdog.HARDEN=0, the same campaign runs against the
# single plain register bank the watchdog had before W6 -- the block
# exactly as docs/40 shipped it. The protected group becomes one target
# instead of three and the acceptance criteria in test_zz_summary become
# reports instead of gates, because they are promises W6 makes and this
# mode is the design that does not make them.
#
# It exists because "the protection works" is not a measurement unless
# the same experiment on the unprotected design produces a different
# number. docs/41 section 8 puts the two columns side by side.
#
#   make -f Makefile.soc_wdog_fi \
#        EXTRA_COMPILE_ARGS=-Psoc_wdog.HARDEN=0 \
#        SOC_WDOG_FI_UNHARDENED=1 SIM_BUILD=sim_build_soc_wdog_fi_h0
UNHARDENED = bool(os.environ.get("SOC_WDOG_FI_UNHARDENED"))
if UNHARDENED:
    # The report bits are excluded, and leaving them in was a mistake
    # worth recording: with HARDEN = 0 the mismatch wire is a constant
    # zero, so those five flip-flops are dead and yosys deletes them --
    # sw/tests/test_soc_synthesis_guards.py measures the unhardened
    # block at 53 flip-flops and not 58. Injecting into them puts an
    # upset into storage the unhardened part does not contain, and the
    # first run of this counterfactual reported ten CORRECTED records
    # from a design with no redundancy because a deposit had fabricated
    # a report out of nothing.
    PROTECTED = [("prot_plain", "g_prot_plain.plain",
                  tuple(i for i in range(PROT_W) if i not in REPORT_BITS))]

TARGETS = PROTECTED + UNPROTECTED
PROTECTED_GROUPS = {g for g, _, _ in PROTECTED}
UNPROTECTED_GROUPS = {g for g, _, _ in UNPROTECTED}


def handle(dut, path):
    obj = dut
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


# =====================================================================
# the workload, and what is observed of it
# =====================================================================
class Trace:
    """The ordered escalation events, and the registers read at the end.

    Everything in here is visible on a pin or through a register read.
    """

    def __init__(self):
        self.events = []     # (name, cycle)
        self.final = {}
        self.hang = None
        self.cycles = 0      # length of the whole observed run
        self.window = 0      # cycles before the final read-back begins

    def order(self):
        return tuple(name for name, _ in self.events)

    def full(self):
        return tuple(self.events)

    def __eq__(self, other):
        return (self.full() == other.full()
                and self.final == other.final
                and self.hang == other.hang)


async def _watch(dut, trace, stop):
    """Record every port transition, with the cycle it happened on."""
    prev = (0, 0, 1)
    cycle = 0
    while not stop["done"]:
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        cycle += 1
        stop["cycles"] = cycle
        cur = (val(dut.nmi_o), val(dut.rst_req_o), val(dut.wdog_no))
        for idx, name in ((0, "nmi"), (1, "rst"), (2, "wdogn")):
            if cur[idx] != prev[idx]:
                trace.events.append(
                    ("{}{}".format(name, "+" if cur[idx] else "-"), cycle))
        prev = cur


async def _await_port(dut, trace, get, want, what):
    """Bounded wait on a port. Returns False on expiry, which is a HANG
    record and never a hung suite."""
    for _ in range(WAIT_BUDGET):
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        if get() == want:
            return True
    trace.hang = what
    return False


async def _inject(dut, path, bit):
    sig = handle(dut, path)
    await Timer(T_INJECT - T_SAMPLE + CLK_NS, unit="ns")
    sig.value = val(sig) ^ (1 << bit)


async def run_workload(dut, deposit=None):
    """One injection: reset, bring-up, the ladder, read back.

    `deposit` is (path, bit, cycle_within_window) or None.
    """
    w = Wdog(dut)
    trace = Trace()
    await por(dut, dis=0)

    # ---- bring-up: a short timeout, and one kick to load it ----
    await w.write(SEL_RLD, RELOAD_SHORT)
    await w.kick()

    stop = {"done": False, "cycles": 0}
    cocotb.start_soon(_watch(dut, trace, stop))

    # ---- the deposit, at a drawn cycle inside the window ----
    if deposit is not None:
        path, bit, when = deposit

        async def _later():
            for _ in range(when):
                await RisingEdge(dut.clk_i)
            await Timer(T_INJECT, unit="ns")
            sig = handle(dut, path)
            sig.value = val(sig) ^ (1 << bit)

        cocotb.start_soon(_later())

    ok = True

    # ---- phase A: alive. Kick well inside the timeout, four times. ----
    for _ in range(4):
        for _ in range(TIMEOUT_CLK // 2):
            await RisingEdge(dut.clk_i)
        await w.kick()

    # ---- phase B: stop kicking, take the warning, acknowledge it ----
    if ok:
        ok = await _await_port(dut, trace, lambda: val(dut.nmi_o), 1,
                               "stage 1 never arrived")
    if ok:
        await w.ack()
        ok = await _await_port(dut, trace, lambda: val(dut.nmi_o), 0,
                               "the acknowledge never took")

    # ---- phases C and D: two full ladders, no acknowledge ----
    for n in range(ESCALATE):
        if not ok:
            break
        ok = await _await_port(dut, trace, lambda: val(dut.nmi_o), 1,
                               "stage 1 of ladder {} never arrived".format(n))
        if not ok:
            break
        ok = await _await_port(dut, trace, lambda: val(dut.rst_req_o), 1,
                               "stage 2 of ladder {} never arrived".format(n))
        if not ok:
            break
        ok = await _await_port(dut, trace, lambda: val(dut.rst_req_o), 0,
                               "the reset of ladder {} never released".format(n))
        if not ok:
            break
        # What the reload reads the instant the reset releases is the
        # observable form of docs/40 section 7.2's fix, and it is the
        # reason `reload` is safe to leave unprotected: whatever the
        # last software configured, and whatever an upset put there, the
        # next boot gets the whole budget. Recorded per ladder rather
        # than once at the end, because it is the recovery and not the
        # final state.
        trace.final["reload_after_{}".format(n)] = await w.read(SEL_RLD)
        # And then the boot code re-arms with a short timeout, which is
        # what the reset default is FOR. Without this the second ladder
        # would run at the full 2^WIDTH * PRESCALE and every injection
        # would cost sixteen times the simulation.
        await w.write(SEL_RLD, RELOAD_SHORT)
        await w.kick()

    # ---- read back ----
    #
    # The injection window CLOSES here. A deposit drawn after this point
    # would land after the status register had already been read, so the
    # report it produced would be invisible and the record would come
    # back MASKED -- from a design that masked and counted it correctly.
    # The first version of this harness drew across the whole run and
    # two of 126 protected injections came back MASKED for exactly that
    # reason, which is a harness defect presenting as a design result.
    trace.window = stop["cycles"]
    if ok:
        stat = await w.read(SEL_STAT)
        ctrl = await w.read(SEL_CTRL)
        rld = await w.read(SEL_RLD)
        trace.final.update({
            "wdogrst": bool(stat & ST_WDOGRST),
            "escalated": bool(stat & ST_ESCALATED),
            "disabled": bool(stat & ST_DISABLED),
            "rstcnt": (stat >> ST_RSTCNT_SH) & ST_RSTCNT_MASK,
            "tmrerr": bool(stat & ST_TMRERR),
            "tmrcnt": (stat >> ST_TMRCNT_SH) & ST_TMRCNT_MASK,
            "en": bool(ctrl & B_EN),
            "reload": rld,
        })

    stop["done"] = True
    await RisingEdge(dut.clk_i)
    trace.cycles = stop["cycles"]
    return trace


def classify(golden, trace):
    """Exactly one class, decided in docs/16 section 1.6's order."""
    flagged = bool(trace.final.get("tmrerr")) or trace.final.get("tmrcnt", 0)
    out_ok = (trace.hang is None
              and trace.full() == golden.full()
              and _final_without_report(trace) == _final_without_report(golden))
    if trace.hang is not None:
        return ("HANG" if not flagged else "DETECTED"), out_ok
    if flagged and not out_ok:
        return "DETECTED", out_ok
    if not out_ok:
        return "SDC", out_ok
    if flagged:
        return "CORRECTED", out_ok
    return "MASKED", out_ok


def _final_without_report(trace):
    """The final reads with the W6 report fields removed.

    The report is part of the observable state and it is SUPPOSED to
    differ after a masked upset, so comparing it against golden would
    make every corrected injection look like a wrong answer. Keeping the
    two apart is the same split docs/16 draws with `telemetry_ok`.
    """
    return {k: v for k, v in trace.final.items()
            if k not in ("tmrerr", "tmrcnt")}


def _shifts(golden, trace):
    """How far an upset moved the escalation events, two ways.

    This is the quantity W6's second list is an argument about. Saying
    an upset in `counter` is "bounded" is only worth anything next to a
    bound, and the bound the block provides is W2's constant:
    2^WIDTH * PRESCALE clocks, the longest single timeout no software
    and no upset can produce, because no longer value fits in the
    counter.

    `gap` is the largest change to any single INTERVAL between
    consecutive escalation events -- one deadline. That is the quantity
    W2 bounds, and it is what the acceptance criterion is written over.

    `cum` is the largest change to an event's absolute cycle. It is NOT
    bounded by one timeout and this campaign measured why: an upset in
    `reload` persists across every deadline until a stage-2 reset
    restores the maximum, so its effect accumulates. The first version
    of the criterion here was written over `cum` and failed at 1,536
    clocks against a 1,024-clock bound -- correctly, because the
    criterion was wrong and not the design. Both numbers are reported;
    only `gap` is asserted.

    Both are None if the event sequences differ, in which case there is
    nothing to line up.
    """
    if trace.order() != golden.order():
        return None, None
    g = [c for _, c in golden.events]
    t = [c for _, c in trace.events]
    cum = max((abs(a - b) for a, b in zip(t, g)), default=0)
    gaps_g = [g[0]] + [g[i] - g[i - 1] for i in range(1, len(g))]
    gaps_t = [t[0]] + [t[i] - t[i - 1] for i in range(1, len(t))]
    gap = max((abs(a - b) for a, b in zip(gaps_t, gaps_g)), default=0)
    return cum, gap


def facts(golden, trace):
    cum, gap = _shifts(golden, trace)
    return {
        "order_ok": trace.order() == golden.order(),
        "max_shift": cum,
        "max_gap_shift": gap,
        # The backstop still escalated all the way. Deliberately ">="
        # and not "==": an upset in the unprotected `reload` can make
        # the timeout SHORTER and produce an EXTRA ladder, which is a
        # spurious system reset and is conservative in the direction
        # docs/40 section 5.4 argues is the right one for a spacecraft.
        # A criterion written as "==" would call that a failure of the
        # backstop when it is an excess of it.
        "ladder_ok": (trace.order().count("rst+") >= ESCALATE
                      and "wdogn-" in trace.order()),
        "extra_ladders": trace.order().count("rst+") - ESCALATE,
        # The record is never WEAKER than the clean run's: the part is
        # still armed, the escalation still happened, and the reset
        # count never went backwards. This is what W6 claims about the
        # unprotected state, and it is what the acceptance criterion is
        # written over -- an exact match (final_ok) is stronger than the
        # claim and the campaign measured a case where it does not hold.
        "no_weaker": (trace.final.get("en") is True
                      and trace.final.get("disabled") is False
                      and trace.final.get("wdogrst") is True
                      and trace.final.get("escalated") is True
                      and trace.final.get("rstcnt", -1)
                      >= golden.final.get("rstcnt", 0)),
        "armed_at_end": (trace.final.get("en") is True
                         and trace.final.get("disabled") is False),
        "final_ok": (_final_without_report(trace)
                     == _final_without_report(golden)),
    }


# =====================================================================
# the campaign
# =====================================================================
RESULTS = []


def _draws(window):
    """Every (group, path, bit, cycle) the campaign injects, in a fixed
    order from one seed.

    `window` is the MEASURED length of the clean run, so a drawn delay
    always lands on a working design rather than after it finished --
    docs/16 section 1.8's last honesty clause. It is passed in rather
    than assumed, which means a workload change moves the draws with it
    instead of silently pushing half the campaign past the end.

    The seed is derived PER TARGET BIT rather than consumed from one
    stream, so the cycle drawn for `counter` bit 3 is the same number
    whatever else is in the target list. Without that, adding or
    removing a target group silently re-rolls every draw after it, and
    the unhardened counterfactual of section 8 could not be compared
    against the hardened run target by target -- which is the whole
    point of running it.
    """
    out = []
    for group, path, bits in TARGETS:
        for bit in bits:
            for draw in range(DRAWS_PER_BIT):
                rng = random.Random(
                    "{}:{}:{}:{}".format(SEED, group, bit, draw))
                out.append((group, path, bit, rng.randrange(4, window)))
    return out


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    dut.rst_por_ni.value = 0
    dut.dis_i.value = 0
    dut.sel_i.value = 0
    dut.we_i.value = 0
    dut.wdata_i.value = 0
    await Timer(1, unit="ns")


@cocotb.test(timeout_time=200, timeout_unit="us")
async def test_00_control(dut):
    """Harness honesty checks, before any data point.

    docs/16 section 1.8. Each of these is a way the campaign could
    report a confident number while measuring nothing.
    """
    await setup(dut)

    # 1. An uninjected run reproduces itself, and classifies MASKED.
    golden = await run_workload(dut)
    assert golden.hang is None, "the clean run did not complete: {}".format(
        golden.hang)
    again = await run_workload(dut)
    assert again.full() == golden.full(), (
        "the clean run is not reproducible: {} then {}".format(
            golden.full(), again.full()))
    cls, out_ok = classify(golden, again)
    assert (cls, out_ok) == ("MASKED", True), (cls, out_ok)

    # 2. The workload actually exercises the whole ladder, or the
    #    campaign is measuring a machine that never escalates.
    f = facts(golden, golden)
    assert f["ladder_ok"], (
        "the clean workload did not reach all three stages: {}".format(
            golden.order()))
    assert f["armed_at_end"]
    assert golden.final["rstcnt"] == ESCALATE
    assert golden.final["escalated"] is True
    assert golden.final["wdogrst"] is True
    # And every stage-2 reset restores the reload to the maximum, which
    # is docs/40 section 7.2's fix. If that stopped happening, `reload`
    # would be a permanent single point and W6's second list would be
    # wrong -- so this is a precondition of the whole campaign and not
    # an incidental check.
    for n in range(ESCALATE):
        assert golden.final["reload_after_{}".format(n)] == (1 << WIDTH) - 1, (
            golden.final)

    # 3. No target is the voted wire. A deposit there is overwritten by
    #    the voter and comes back MASKED, which is what a mis-targeted
    #    injector produces.
    for _, path, _bits in TARGETS:
        assert path.endswith(".bits") or path.endswith(".plain") \
            or "." not in path, path
        assert not path.endswith("prot"), path
    if not UNHARDENED:
        assert len(PROTECTED) == 3, (
            "a replica went missing from the target list")

    # 4. The injection mechanism demonstrably reaches a target. A
    #    deposit into a replica must come back CORRECTED. If it came
    #    back MASKED the deposit is not landing and the whole campaign
    #    would be measuring nothing. The probe result is discarded --
    #    it is a self-test, not a data point.
    probe = await run_workload(dut, deposit=(PROTECTED[0][1], 0, 40))
    cls, out_ok = classify(golden, probe)
    if UNHARDENED:
        # The counterfactual: the same deposit into the unprotected
        # bank must NOT come back corrected, or the two columns are not
        # measuring different designs.
        assert cls != "CORRECTED", cls
        assert probe.final.get("tmrcnt", 0) == 0
    else:
        assert cls == "CORRECTED", (
            "the probe deposit into replica A came back {} rather than "
            "CORRECTED. MASKED here means the deposit never "
            "landed.".format(cls))
        assert probe.final["tmrcnt"] >= 1

    # 5. The drawn cycles all land inside the window the workload is
    #    actually running, so no injection is a no-op on an idle design.
    assert golden.window > 4 * TIMEOUT_CLK, golden.window
    assert golden.window < golden.cycles, (
        "the injection window must close before the final read-back, or "
        "a masked-and-counted upset can be drawn after the status "
        "register was read and reported as MASKED")
    for _, _, _, when in _draws(golden.window):
        assert 0 < when < golden.window

    dut._log.info("control: golden run %d cycles, injection window %d, "
                  "order %s",
                  golden.cycles, golden.window, " ".join(golden.order()))


@cocotb.test(timeout_time=3600, timeout_unit="us")
async def test_01_campaign(dut):
    """The campaign itself."""
    await setup(dut)
    golden = await run_workload(dut)
    assert golden.hang is None

    for group, path, bit, when in _draws(golden.window):
        trace = await run_workload(dut, deposit=(path, bit, when))
        cls, out_ok = classify(golden, trace)
        rec = {"group": group, "path": path, "bit": bit, "cycle": when,
               "cls": cls, "out_ok": out_ok, "hang": trace.hang}
        rec.update(facts(golden, trace))
        RESULTS.append(rec)

    hist = {}
    for r in RESULTS:
        hist[r["cls"]] = hist.get(r["cls"], 0) + 1
    dut._log.info("campaign: %d injections, %s", len(RESULTS), hist)
    for g in [g for g, _, _ in TARGETS]:
        sub = [r for r in RESULTS if r["group"] == g]
        h = {}
        for r in sub:
            h[r["cls"]] = h.get(r["cls"], 0) + 1
        cums = [r["max_shift"] for r in sub if r["max_shift"] is not None]
        gaps = [r["max_gap_shift"] for r in sub
                if r["max_gap_shift"] is not None]
        dut._log.info(
            "  %-8s n=%-4d %-40s armed=%d/%d ladder=%d/%d order=%d/%d "
            "final=%d/%d weaker=%d extra_ladders=%d "
            "worst_deadline_shift=%s worst_cumulative=%s clocks",
            g, len(sub), str(h),
            sum(r["armed_at_end"] for r in sub), len(sub),
            sum(r["ladder_ok"] for r in sub), len(sub),
            sum(r["order_ok"] for r in sub), len(sub),
            sum(r["final_ok"] for r in sub), len(sub),
            sum(not r["no_weaker"] for r in sub),
            sum(max(0, r["extra_ladders"]) for r in sub),
            max(gaps) if gaps else "n/a", max(cums) if cums else "n/a")
        for r in sub:
            if not (r["ladder_ok"] and r["no_weaker"]) or r["extra_ladders"]:
                dut._log.info("    notable: %s", r)


@cocotb.test(timeout_time=10, timeout_unit="us")
async def test_zz_summary(dut):
    """The acceptance criteria.

    Each of these is a promise W6 makes. They are deliberately written
    as promises and not as descriptions of the measurement: a criterion
    written around a result is a criterion written to pass.
    """
    assert RESULTS, "the campaign did not run"

    if UNHARDENED:
        # This mode is a measurement and not a gate. Every criterion
        # below is a promise W6 makes, and the point of running the
        # campaign against HARDEN = 0 is that the block does not make
        # them -- so asserting them here would be asserting that the
        # counterfactual fails, which tells a future reader nothing they
        # could act on. The numbers are in the campaign log.
        disarmed = [r for r in RESULTS if not r["armed_at_end"]]
        cls = {}
        for r in RESULTS:
            cls[r["cls"]] = cls.get(r["cls"], 0) + 1
        dut._log.info("UNHARDENED counterfactual: %s, %d of %d injections "
                      "left the watchdog reading disarmed",
                      cls, len(disarmed), len(RESULTS))
        return

    # A presence check first, and the shape of it is the point. The way
    # a structure comes to be unmeasured in this repository has twice
    # been an omission rather than a decision, and an omission that
    # fails a test cannot repeat.
    groups = {r["group"] for r in RESULTS}
    assert groups == PROTECTED_GROUPS | UNPROTECTED_GROUPS, groups
    assert len(RESULTS) >= DRAWS_PER_BIT * sum(len(b) for _, _, b in TARGETS)

    # 1. THE HEADLINE. No single upset anywhere in this block may leave
    #    the watchdog disarmed. This is the criterion that fails if
    #    dis_q is left unprotected, and it is the whole reason W6's
    #    ranking puts that bit first.
    disarmed = [r for r in RESULTS if not r["armed_at_end"]]
    assert not disarmed, (
        "{} injections left the watchdog reading disarmed: {}".format(
            len(disarmed), disarmed[:5]))

    # 2. The protected word. Deliberately stronger than "never SDC": an
    #    injection that never reached a flip-flop comes back MASKED, and
    #    MASKED is exactly the quiet nothing a mis-targeted injector
    #    produces. Every replica upset must be masked at the ports AND
    #    counted in TMRCNT.
    prot = [r for r in RESULTS if r["group"] in PROTECTED_GROUPS]
    bad = [r for r in prot if r["cls"] != "CORRECTED"]
    assert not bad, (
        "{} of {} protected-replica injections were not CORRECTED: "
        "{}".format(len(bad), len(prot), bad[:5]))

    # 3. The deliberately unprotected state. The claim W6 makes about it
    #    is not that an upset is invisible -- it plainly is not, it
    #    moves the deadline -- but that it is BOUNDED: the ladder still
    #    completes and the block recovers.
    unprot = [r for r in RESULTS if r["group"] in UNPROTECTED_GROUPS]
    assert unprot
    no_ladder = [r for r in unprot if not r["ladder_ok"]]
    assert not no_ladder, (
        "{} upsets in the unprotected state stopped the escalation "
        "ladder completing: {}".format(len(no_ladder), no_ladder[:5]))
    weaker = [r for r in unprot if not r["no_weaker"]]
    assert not weaker, (
        "{} upsets in the unprotected state left the block in a state "
        "WEAKER than the clean run -- disarmed, or with the escalation "
        "record reduced: {}".format(len(weaker), weaker[:5]))

    # 4. The deadline an upset moves is bounded by the block's own
    #    netlist constant. W2 makes 2^WIDTH * PRESCALE the longest
    #    timeout this block can be talked into; W6's decision to leave
    #    `counter`, `reload` and `pre` unprotected rests on an upset in
    #    them being no worse than that, and nothing but a measurement
    #    can say whether it is.
    bound = (1 << WIDTH) * PRESCALE
    over = [r for r in RESULTS
            if r["max_gap_shift"] is not None and r["max_gap_shift"] > bound]
    assert not over, (
        "{} injections moved a single deadline by more than the "
        "{}-clock bound W2 fixes: {}".format(len(over), bound, over[:5]))

    # 5. Nothing anywhere may hang. A watchdog that stops escalating is
    #    the failure this whole block exists to prevent.
    hung = [r for r in RESULTS if r["cls"] == "HANG"]
    assert not hung, "{} injections hung: {}".format(len(hung), hung[:5])


def pytest_sessionfinish():   # pragma: no cover - cocotb runs standalone
    pass


if os.environ.get("SOC_WDOG_FI_DUMP"):   # pragma: no cover
    sys.stderr.write("draws: {}\n".format(len(_draws())))
