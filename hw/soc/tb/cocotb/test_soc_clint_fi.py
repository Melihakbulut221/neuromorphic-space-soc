"""Fault injection into the CLINT's time base.

WHY THIS EXISTS

`docs/41` section 7.4 ranked `mtime` above everything the watchdog wave
left unprotected and then left it alone; `docs/43` section 12 and
`docs/44` section 3 deferred it twice more. `hw/soc/rtl/soc_clint.v` H6
is the answer, and it makes two claims that neither the proof nor an
argument can settle:

  1. a single-bit upset anywhere in mtime's 72 stored bits -- 64 data
     and 8 check -- leaves the ARCHITECTURAL CLOCK UNCHANGED at every
     port, and is announced on `mt_ecc_o`;
  2. the state H6 deliberately does NOT protect -- `mtimecmp`, `msip`
     and the bus response registers -- fails in a way this campaign can
     name, because the decision not to protect them is only a decision
     if its price is measured.

The second is where the design argument is. `soc_clint.v`'s H6 section
claims `mtimecmp` is neither persistent nor silent by `docs/41` section
3.1's criterion. That is an argument. This is the number.

METHOD, adapted from `docs/16` sections 1.2 to 1.6

  * The DUT is `soc_clint` itself. **Only the stimulus reaches into the
    hierarchy.** Every observation is one a bench could make: the two
    interrupt pins, the fault pin, and what a bus master reads back.
  * Per injection: reset, bring-up (seed mtime to a mid-mission value
    and arm a deadline), then the workload, with one bit of one
    flip-flop XORed at a seeded-random cycle inside the MEASURED window.
  * The GOLDEN MODEL decides right from wrong, always. It is a run of
    the same workload with no deposit, recorded once. `mt_ecc_o` only
    decides whether a wrong answer was ANNOUNCED; it never declares an
    answer correct, which is why every record carries `clock_ok`
    separately from its class.

MTIME IS SEEDED, AND THAT IS THE WHOLE POINT OF THE BRING-UP

Out of reset mtime is zero and stays under 2^10 for the length of any
simulation anyone will run. A campaign drawn there would flip bit 47 of
a register whose bit 47 is zero, in a design where every deadline is
also small, and would report that the high half of the counter does not
matter. It matters for exactly the reason `docs/41` section 7.4 gives --
a flip in a high bit moves the clock by up to 2^63 ticks -- so the
workload WRITES mtime to a value with bits set across the whole word
before the injection window opens, using the architectural store this
block implements. MID_MTIME below is that value and section 3 of
`docs/58` says where it comes from.

CLASSIFICATION, exactly one class per injection, in `docs/16` section
1.6's order:

    HANG       a bounded wait expired and nothing was announced
    DETECTED   mt_ecc_o pulsed and the observation differs from golden
    SDC        the observation differs from golden and nothing pulsed
    CORRECTED  the observation matches golden and mt_ecc_o pulsed
    MASKED     matches golden and nothing pulsed

and four further per-record facts, because five classes cannot carry
them:

    clock_ok      every mtime a bus master read back was the value the
                  ARITHMETIC said it should be -- mtime minus the cycle
                  it was read on is a constant, which is C1 of
                  soc_clint_props.v restated as a measurement. THIS IS
                  THE COLUMN THE WHOLE DOCUMENT IS ABOUT: a wrong clock
                  that still fires its interrupt on time is the silent
                  failure docs/40 section 10 item 2 named. The oracle is
                  arithmetic and not a diff against golden for the
                  reason _epoch() records.
    deadline_ok   the timer interrupt rose on the golden cycle.
    clock_err     the largest absolute difference, in ticks, between a
                  read of mtime and what the arithmetic predicts. This
                  is the DISPLACEMENT, and it is the quantity docs/41
                  section 7.4 is an argument about.
    ecc_events    how many cycles mt_ecc_o was high.

WHAT THIS CAMPAIGN DOES **NOT** COVER

  * It is RTL, SINGLE-BIT, flip-flop only. No gate-level netlist, no
    back-annotated timing, no multi-bit strike, and no SET in
    combinational logic -- which for H6 is a larger gap than it is for
    a TMR block, because H6's defence is a combinational encoder and
    decoder and a transient inside either is a fault model this harness
    cannot express. `docs/58` section 10 states it at length.
  * Consequently THE UNCORRECTABLE CLASS IS EMPTY BY CONSTRUCTION. A
    double error needs two upsets in one 72-bit word inside one tick.
    `test_soc_clint.py` drives one directly, as a directed test rather
    than as a campaign draw, and asserts the codec does not miscorrect.
  * It says nothing about RATES. Every number is a conditional
    probability given that an upset landed in the window, on a uniform
    choice of target and bit. `docs/16` section 7.5.
  * DETECTED depends on someone looking. `mt_ecc_o` goes to a saturating
    counter in `soc_busstat.v` and nothing else; the software that would
    read it may be the thing that failed.
  * One workload, one seed, TICK_DIV = 1, and the block alone. Nothing
    here runs the CLINT inside the SoC with a core in front of it.
  * It cannot fail because the codec vanished in synthesis. Every target
    path exists in the RTL whatever the netlist holds, and
    `sw/tests/test_soc_synthesis_guards.py` is the separate,
    netlist-level criterion.
"""

import csv
import os
import random
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "sw"))
from golden.memmap_gen import REGIONS  # noqa: E402

BASE = REGIONS["CLINT"][0]

MSIP = 0x0000
MTIMECMPL = 0x4000
MTIMECMPH = 0x4004
MTIMEL = 0xBFF8
MTIMEH = 0xBFFC
UNMAPPED = 0x0100

CLK_NS = 10
T_DRIVE = 1
T_SAMPLE = 8
T_INJECT = 4          # inside the cycle, after the drive and before the
                      # sample, so a deposit never races a register write

# The mid-mission seed. Bits are set across the whole 64-bit word and in
# both polarities, so a drawn flip is as likely to clear a one as to set
# a zero, and the high half is not a field of zeros. docs/58 section 3.
MID_MTIME = 0x0003_5A6C_39F1_84B2

# The deadline, in ticks after the seed. Long enough that the interrupt
# is not already pending when it is programmed and short enough that the
# whole run is a few hundred cycles.
DEADLINE_DELTA = 200

# Bounded waits. A wait that expires is a HANG record, never a hung
# suite -- docs/16 section 1.3. Sized well above DEADLINE_DELTA, because
# an upset in mtimecmp can legitimately push the deadline out and the
# campaign has to record that as a moved deadline rather than as a hang
# of the harness.
WAIT_BUDGET = 4000

# One seed drives every randomised injection cycle; the targets, the
# bits and the draw counts are constants. docs/16 section 1.7.
SEED = 0x58C10007
DRAWS_PER_BIT = 2

# With SOC_CLINT_FI_UNHARDENED set, and the block built with
# -Psoc_clint.HARDEN=0, the same campaign runs against the design
# docs/40 shipped: mtime is a plain 64-bit register, there are no check
# bits, and mt_ecc_o is tied low.
#
# It exists because "the protection works" is not a measurement unless
# the same experiment on the unprotected design produces a different
# number, and because the strata H6 does not touch have to come back
# IDENTICAL between the two runs or the delta is a difference of two
# things. docs/56 section 8.1 is the discipline; section 8 of docs/58 is
# the result.
#
#   make -f Makefile.soc_clint_fi \
#        EXTRA_COMPILE_ARGS=-Psoc_clint.HARDEN=0 \
#        SOC_CLINT_FI_UNHARDENED=1 SIM_BUILD=sim_build_soc_clint_fi_h0 \
#        COCOTB_RESULTS_FILE=results_soc_clint_fi_h0.xml
UNHARDENED = bool(os.environ.get("SOC_CLINT_FI_UNHARDENED"))

# Where the per-record CSV goes. The replay in docs/58 section 8 is a
# diff of two of these, so the file is written unconditionally and the
# column order is fixed.
RECORDS = os.environ.get(
    "SOC_CLINT_FI_RECORDS",
    "records_soc_clint_fi_h0.csv" if UNHARDENED else "records_soc_clint_fi.csv")

# ---------------------------------------------------------------------
# targets
# ---------------------------------------------------------------------
# Every entry is (stratum, hierarchical path, bit indices).
#
# THE STRATA ARE THE DECISIONS, not the flip-flops. docs/42 section 4.1
# and docs/41 section 3.1: a stratum is a thing about which one could
# make a different hardening decision. `mtime` is protected, `mtime_chk`
# is the state the protection ADDED, and the other three are the three
# separate arguments soc_clint.v's H6 section makes for leaving
# something alone.
PROTECTED = [
    ("mtime", "mtime_q", tuple(range(64))),
]
# The check bits are a stratum of their own and not part of `mtime`, for
# docs/43's `regfile_ecc` reason: they are eight flip-flops the design
# did not have, an upset can land in them exactly as it can land in the
# data, and folding them into `mtime` would move that stratum's measured
# rate for two unrelated reasons at once.
if not UNHARDENED:
    PROTECTED.append(("mtime_chk", "mtime_chk_q", tuple(range(8))))

UNPROTECTED = [
    ("mtimecmp", "mtimecmp", tuple(range(64))),
    ("msip", "msip", (0,)),
    # The bus response registers. Three targets in one stratum because
    # they are one decision: soc_clint.v's H6 section leaves all three
    # alone on docs/41 section 3.1's "a register the block itself
    # overwrites every tick sheds an upset on its own", and a campaign
    # that measured them separately would be measuring the same argument
    # three times.
    ("rsp_rdata", "rdata_o", tuple(range(32))),
    ("rsp_ctrl_v", "rvalid_o", (0,)),
    ("rsp_ctrl_e", "err_o", (0,)),
]

TARGETS = PROTECTED + UNPROTECTED
PROTECTED_STRATA = {g for g, _, _ in PROTECTED}


def val(sig):
    s = str(sig.value)
    if any(c not in "01" for c in s):
        raise AssertionError("non-binary value {!r} on {}".format(s, sig._path))
    return int(s, 2)


def handle(dut, path):
    obj = dut
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


# =====================================================================
# the device, driven only through its ports
# =====================================================================
class Clint:
    """A protocol-legal fabric master, one transaction at a time.

    Deliberately a reduced copy of test_soc_clint.py's agent rather than
    an import of it: that one asserts on every access, and an assertion
    inside a fault-injection run turns a data point into a suite
    failure. Here a protocol violation is recorded and classified.
    """

    def __init__(self, dut, stop=None):
        self.dut = dut
        self.broken = None
        # The observer's cycle counter, so a read of mtime can be
        # STAMPED with the cycle it happened on. facts() needs the pair
        # and not the value: see _clock_error.
        self.stop = stop if stop is not None else {"cycles": 0}

    async def _xact(self, off, we, wdata=0, be=0xF):
        dut = self.dut
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
        dut.req_i.value = 1
        dut.addr_i.value = BASE + off
        dut.we_i.value = we
        dut.be_i.value = be
        dut.wdata_i.value = wdata
        for _ in range(64):
            await Timer(T_SAMPLE - T_DRIVE, unit="ns")
            if val(dut.gnt_o):
                break
            await RisingEdge(dut.clk_i)
            await Timer(T_DRIVE, unit="ns")
        else:
            self.broken = "no grant for 0x{:04x}".format(off)
            return 0, 1
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
        dut.req_i.value = 0
        dut.addr_i.value = 0xDEADBEE0
        dut.we_i.value = 0
        dut.be_i.value = 0
        dut.wdata_i.value = 0
        for _ in range(64):
            await Timer(T_SAMPLE - T_DRIVE, unit="ns")
            if val(dut.rvalid_o):
                return val(dut.rdata_o), val(dut.err_o)
            await RisingEdge(dut.clk_i)
            await Timer(T_DRIVE, unit="ns")
        self.broken = "no response for 0x{:04x}".format(off)
        return 0, 1

    async def read(self, off):
        return await self._xact(off, 0)

    async def write(self, off, data, be=0xF):
        return await self._xact(off, 1, data, be)

    async def mtime(self):
        """The documented read sequence: high, low, high again.

        Returns (value, cycle), where `cycle` is the observer's count at
        the instant the LOW half came back. The stamp is taken there and
        not at the start of the sequence, so a retry -- which a corrupt
        high half can cause -- moves the stamp with the read instead of
        silently shifting the value against it.

        Bounded at four attempts and NOT an assertion: a high half that
        keeps changing is a result, not a harness failure.
        """
        hi = lo = 0
        at = 0
        for _ in range(4):
            hi, _e = await self.read(MTIMEH)
            lo, _e = await self.read(MTIMEL)
            at = self.stop["cycles"]
            hi2, _e = await self.read(MTIMEH)
            if hi == hi2:
                return (hi << 32) | lo, at
        return (hi << 32) | lo, at

    async def set_mtime(self, v):
        await self.write(MTIMEH, (v >> 32) & 0xFFFFFFFF)
        await self.write(MTIMEL, v & 0xFFFFFFFF)

    async def set_mtimecmp(self, v):
        await self.write(MTIMECMPL, 0xFFFFFFFF)
        await self.write(MTIMECMPH, (v >> 32) & 0xFFFFFFFF)
        await self.write(MTIMECMPL, v & 0xFFFFFFFF)


async def por(dut):
    dut.rst_ni.value = 0
    dut.req_i.value = 0
    dut.addr_i.value = 0
    dut.we_i.value = 0
    dut.be_i.value = 0
    dut.wdata_i.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.rst_ni.value = 1
    await RisingEdge(dut.clk_i)


# =====================================================================
# the workload, and what is observed of it
# =====================================================================
class Trace:
    """Everything in here is visible on a pin or through a bus read."""

    def __init__(self):
        self.reads = []      # (label, cycle, value) -- mtime samples
        self.events = []     # (name, cycle) -- interrupt pin transitions
        self.final = {}
        self.hang = None
        self.cycles = 0
        self.window = 0
        self.ecc = 0         # cycles mt_ecc_o was high

    def observation(self):
        """The whole of what a bench sees, EXCLUDING the fault pin.

        The fault pin is the design's own report and is kept out for the
        same reason test_soc_wdog_fi.py keeps TMRERR out: comparing a
        report against golden would make every announced correction look
        like a wrong answer.
        """
        return (tuple(self.reads), tuple(self.events),
                tuple(sorted(self.final.items())), self.hang)


async def _watch(dut, trace, stop):
    """Record every pin transition, with the cycle it happened on.

    THE `done` CHECK IS AFTER THE SAMPLE AND NOT IN THE LOOP CONDITION,
    and that is not a style choice. Written as `while not stop["done"]`
    the watcher completes one more loop BODY after the run has ended --
    which is during the next run's power-on reset, where mtimecmp and
    mtime are both zero and mtip is therefore high. It appended that
    transition to the FINISHED run's trace, so a clean run did not
    reproduce itself, no injection ever classified MASKED because every
    trace differed from a golden that had a phantom event in it, and
    every record read "the deadline moved" while reporting that it had
    moved by zero cycles. Three symptoms, one race, and control 1 is
    what caught it.
    """
    prev = (0, 0)
    cycle = 0
    while True:
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        if stop["done"]:
            return
        cycle += 1
        stop["cycles"] = cycle
        if val(dut.mt_ecc_o):
            trace.ecc += 1
        cur = (val(dut.irq_timer_o), val(dut.irq_software_o))
        for idx, name in ((0, "mtip"), (1, "msi")):
            if cur[idx] != prev[idx]:
                trace.events.append(
                    ("{}{}".format(name, "+" if cur[idx] else "-"), cycle))
        prev = cur


async def _await_pin(dut, trace, get, want, what, stop):
    for _ in range(WAIT_BUDGET):
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        if get() == want:
            return True
    trace.hang = what
    return False


async def run_workload(dut, deposit=None):
    """One injection: reset, bring-up, the deadline, read back.

    `deposit` is (path, bit, cycle_within_window) or None.
    """
    stop = {"done": False, "cycles": 0}
    c = Clint(dut, stop)
    trace = Trace()
    await por(dut)

    # ---- bring-up, OUTSIDE the injection window ----
    #
    # Seed the counter to a mid-mission value and arm a deadline off it,
    # both through the architectural sequences this block implements.
    # An upset drawn during these writes would be measuring the
    # bring-up, which is not the mission.
    await c.set_mtime(MID_MTIME)
    t0, _at = await c.mtime()
    await c.set_mtimecmp(t0 + DEADLINE_DELTA)

    watcher = cocotb.start_soon(_watch(dut, trace, stop))

    if deposit is not None:
        path, bit, when = deposit

        async def _later():
            for _ in range(when):
                await RisingEdge(dut.clk_i)
            await Timer(T_INJECT, unit="ns")
            sig = handle(dut, path)
            sig.value = val(sig) ^ (1 << bit)

        cocotb.start_soon(_later())

    # ---- phase A: the clock is read while it runs ----
    #
    # Four samples, spaced. The VALUE is recorded and so is the CYCLE it
    # was taken on, because a clock that is wrong by a constant and a
    # clock that is right are the same sequence of reads if only the
    # differences are kept.
    for i in range(4):
        for _ in range(12):
            await RisingEdge(dut.clk_i)
        v, at = await c.mtime()
        trace.reads.append(("t%d" % i, at, v))

    # ---- phase B: the deadline ----
    ok = await _await_pin(dut, trace, lambda: val(dut.irq_timer_o), 1,
                          "the deadline never arrived", stop)
    if ok:
        trace.events.append(("deadline_seen", stop["cycles"]))
        # Move it out of reach again, the architectural way, and watch
        # the level fall. That is the only way software clears mtip and
        # it is what a driver does at every tick.
        now, _at = await c.mtime()
        await c.set_mtimecmp(now + 4 * DEADLINE_DELTA)
        ok = await _await_pin(dut, trace, lambda: val(dut.irq_timer_o), 0,
                              "mtip never cleared", stop)

    # ---- phase C: the software interrupt, and the error path ----
    if ok:
        await c.write(MSIP, 1)
        ok = await _await_pin(dut, trace, lambda: val(dut.irq_software_o), 1,
                              "msip never took", stop)
    if ok:
        await c.write(MSIP, 0)
        ok = await _await_pin(dut, trace, lambda: val(dut.irq_software_o), 0,
                              "msip never cleared", stop)
    if ok:
        d, e = await c.read(UNMAPPED)
        trace.final["unmapped_err"] = e
        trace.final["unmapped_data"] = d

    # ---- the window closes here ----
    trace.window = stop["cycles"]
    if ok:
        vend, atend = await c.mtime()
        trace.reads.append(("tend", atend, vend))
        trace.final["mtime_end"] = vend
        lo, _e = await c.read(MTIMECMPL)
        hi, _e = await c.read(MTIMECMPH)
        trace.final["mtimecmp_end"] = (hi << 32) | lo
        m, _e = await c.read(MSIP)
        trace.final["msip_end"] = m
        trace.final["broken"] = c.broken

    stop["done"] = True
    await RisingEdge(dut.clk_i)
    await Timer(T_SAMPLE + 1, unit="ns")
    # And killed as well as told to stop, so no run's observer can
    # outlive its run whatever the scheduler does with the pending
    # trigger. Belt and braces, for the reason in _watch's docstring.
    watcher.cancel()
    trace.cycles = stop["cycles"]
    return trace


def classify(golden, trace):
    flagged = trace.ecc > 0
    out_ok = trace.observation() == golden.observation()
    if trace.hang is not None:
        return ("HANG" if not flagged else "DETECTED"), out_ok
    if flagged and not out_ok:
        return "DETECTED", out_ok
    if not out_ok:
        return "SDC", out_ok
    if flagged:
        return "CORRECTED", out_ok
    return "MASKED", out_ok


def _epoch(golden):
    """mtime minus the cycle it was read on, from the golden run.

    THE ORACLE FOR THE CLOCK IS ARITHMETIC AND NOT A DIFF, and getting
    that wrong once is why this function exists. The obvious oracle --
    compare each read against the golden read with the same label -- is
    wrong for a reason the campaign demonstrated: an upset in `mtimecmp`
    changes how long the RUN takes, so the final read-back happens at a
    different cycle, so mtime legitimately reads differently, and the
    harness reported 115 of 128 `mtimecmp` injections as having
    corrupted the clock. They had not. mtimecmp cannot reach mtime; the
    workload had simply moved underneath the measurement.

    What mtime actually promises is C1 of soc_clint_props.v: at
    TICK_DIV = 1 it advances exactly one per clock. So `mtime - cycle`
    is a CONSTANT for the whole run, the golden run measures that
    constant, and every read in every injected run is checked against
    it. The check is then independent of how long the run took, which is
    what makes it a check on the clock rather than on the schedule.
    """
    offs = {v - cyc for _lab, cyc, v in golden.reads}
    return offs


def facts(golden, trace, epoch=None):
    """The four columns five classes cannot carry."""
    if epoch is None:
        epoch = _epoch(golden)
    base = next(iter(epoch)) if len(epoch) == 1 else None
    err = 0
    clock_ok = True
    if not trace.reads:
        clock_ok = False
    for _lab, cyc, v in trace.reads:
        want = None if base is None else base + cyc
        if want is None or want != v:
            clock_ok = False
        if want is not None:
            err = max(err, abs(v - want))
    # A run that never reached its final read-back never showed the
    # clock at the end, and silence is not evidence that it was right.
    if not any(lab == "tend" for lab, _c, _v in trace.reads):
        clock_ok = False

    gd = [c for n, c in golden.events if n == "mtip+"]
    td = [c for n, c in trace.events if n == "mtip+"]
    deadline_ok = gd == td
    deadline_shift = (abs(td[0] - gd[0]) if (gd and td) else None)

    return {
        # THE COLUMN THE DOCUMENT IS ABOUT.
        "clock_ok": clock_ok,
        # The largest displacement, in TICKS, between a read of mtime
        # and its golden value. docs/41 section 7.4's quantity.
        "clock_err": err,
        "deadline_ok": deadline_ok,
        "deadline_shift": deadline_shift,
        "ecc_events": trace.ecc,
        "final_ok": trace.final == golden.final,
    }


# =====================================================================
# the campaign
# =====================================================================
RESULTS = []


def _draws(window):
    """Every (stratum, path, bit, cycle) the campaign injects.

    The seed is derived PER TARGET BIT rather than consumed from one
    stream, so the cycle drawn for `mtimecmp` bit 3 is the same number
    whatever else is in the target list. Without that, the unhardened
    counterfactual -- which has no `mtime_chk` stratum -- would silently
    re-roll every draw after it and the two runs could not be compared
    record for record. That comparison is the calibration in docs/58
    section 8 and it is the whole reason this function looks like this.
    """
    out = []
    for stratum, path, bits in TARGETS:
        for bit in bits:
            for draw in range(DRAWS_PER_BIT):
                rng = random.Random(
                    "{}:{}:{}:{}".format(SEED, stratum, bit, draw))
                out.append((stratum, path, bit, rng.randrange(4, window)))
    return out


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    dut.rst_ni.value = 0
    dut.req_i.value = 0
    dut.addr_i.value = 0
    dut.we_i.value = 0
    dut.be_i.value = 0
    dut.wdata_i.value = 0
    await Timer(1, unit="ns")


@cocotb.test(timeout_time=400, timeout_unit="us")
async def test_00_control(dut):
    """Harness honesty checks, before any data point. docs/16 section 1.8."""
    await setup(dut)

    # 1. An uninjected run reproduces itself and classifies MASKED.
    golden = await run_workload(dut)
    assert golden.hang is None, "the clean run did not complete: {}".format(
        golden.hang)
    again = await run_workload(dut)
    assert again.observation() == golden.observation(), (
        "the clean run is not reproducible")
    assert classify(golden, again) == ("MASKED", True)

    # 2. The clean run never reports a fault. If mt_ecc_o pulsed with no
    #    deposit, the codec is being fed a non-codeword by the design
    #    itself and every DETECTED below would be meaningless.
    assert golden.ecc == 0, "mt_ecc_o pulsed on a clean run"

    # 3. THE CLOCK ORACLE IS A CONSTANT. mtime minus the cycle it was
    #    read on must be the SAME number for every read in the clean
    #    run, or the arithmetic oracle in facts() is not an oracle. This
    #    is C1 of soc_clint_props.v restated as a measurement: at
    #    TICK_DIV = 1 mtime advances exactly one per clock.
    ep = _epoch(golden)
    assert len(ep) == 1, (
        "mtime does not advance one per clock on the clean run: "
        "offsets {}".format(sorted(ep)))

    # 4. THE COUNTER IS ACTUALLY MID-MISSION. A campaign drawn over a
    #    zeroed counter measures the low ten bits and calls it mtime.
    for _lab, _c, v in golden.reads:
        assert v >> 32 == MID_MTIME >> 32, (
            "mtime's high half is not the seeded one: 0x{:016x}".format(v))
    assert bin(MID_MTIME).count("1") > 20, "the seed is not bit-diverse"

    # 5. The deadline is met inside the window and the error path ran.
    assert any(n == "mtip+" for n, _ in golden.events), golden.events
    assert golden.final["unmapped_err"] == 1
    assert golden.final["broken"] is None

    # 6. The injection mechanism demonstrably reaches a target, and the
    #    two builds differ. A deposit into mtime must come back
    #    CORRECTED when hardened and NOT when it is not. If the hardened
    #    probe came back MASKED the deposit is not landing and the whole
    #    campaign would be measuring nothing.
    probe = await run_workload(dut, deposit=("mtime_q", 40, 30))
    cls, out_ok = classify(golden, probe)
    if UNHARDENED:
        assert cls == "SDC", (
            "a flip of mtime bit 40 in the unprotected design came back "
            "{} rather than SDC".format(cls))
        assert probe.ecc == 0
    else:
        assert cls == "CORRECTED", (
            "a flip of mtime bit 40 came back {} rather than CORRECTED. "
            "MASKED here means the deposit never landed.".format(cls))
        assert probe.ecc == 1, probe.ecc
        assert facts(golden, probe)["clock_ok"] is True

    # 7. Every drawn cycle lands inside the window the workload runs.
    assert golden.window < golden.cycles, (
        "the injection window must close before the final read-back")
    for _, _, _, when in _draws(golden.window):
        assert 0 < when < golden.window

    # 8. No target is a wire the design drives continuously. Every path
    #    here is a `reg` in soc_clint.v.
    for _g, path, _bits in TARGETS:
        assert "." not in path, path

    dut._log.info("control: golden %d cycles, window %d, %d targets, "
                  "%d draws, hardened=%s",
                  golden.cycles, golden.window, len(TARGETS),
                  len(_draws(golden.window)), not UNHARDENED)


@cocotb.test(timeout_time=7200, timeout_unit="us")
async def test_01_campaign(dut):
    await setup(dut)
    golden = await run_workload(dut)
    assert golden.hang is None
    epoch = _epoch(golden)
    assert len(epoch) == 1, sorted(epoch)

    for stratum, path, bit, when in _draws(golden.window):
        trace = await run_workload(dut, deposit=(path, bit, when))
        cls, out_ok = classify(golden, trace)
        rec = {"stratum": stratum, "path": path, "bit": bit, "cycle": when,
               "cls": cls, "out_ok": out_ok, "hang": trace.hang or ""}
        rec.update(facts(golden, trace, epoch))
        RESULTS.append(rec)

    # The per-record file the replay diffs. Written here rather than in
    # the summary so that it exists even if an acceptance criterion
    # below fails -- a campaign whose records vanish when it fails is a
    # campaign that cannot be debugged.
    cols = ["stratum", "path", "bit", "cycle", "cls", "out_ok", "hang",
            "clock_ok", "clock_err", "deadline_ok", "deadline_shift",
            "ecc_events", "final_ok"]
    with open(RECORDS, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in RESULTS:
            w.writerow({k: r[k] for k in cols})

    hist = {}
    for r in RESULTS:
        hist[r["cls"]] = hist.get(r["cls"], 0) + 1
    dut._log.info("campaign: %d injections, %s -> %s",
                  len(RESULTS), hist, RECORDS)
    for g, _p, _b in TARGETS:
        sub = [r for r in RESULTS if r["stratum"] == g]
        if not sub:
            continue
        h = {}
        for r in sub:
            h[r["cls"]] = h.get(r["cls"], 0) + 1
        shifts = [r["deadline_shift"] for r in sub
                  if r["deadline_shift"] is not None]
        dut._log.info(
            "  %-11s n=%-4d %-46s clock_ok=%d/%d deadline_ok=%d/%d "
            "announced=%d worst_clock_err=%d worst_deadline_shift=%s",
            g, len(sub), str(h),
            sum(r["clock_ok"] for r in sub), len(sub),
            sum(r["deadline_ok"] for r in sub), len(sub),
            sum(r["ecc_events"] > 0 for r in sub),
            max(r["clock_err"] for r in sub),
            max(shifts) if shifts else "n/a")


@cocotb.test(timeout_time=10, timeout_unit="us")
async def test_zz_summary(dut):
    """The acceptance criteria: each is a promise H6 makes.

    They are written as promises and not as descriptions of the
    measurement, because a criterion written around a result is a
    criterion written to pass.
    """
    assert RESULTS, "the campaign did not run"

    prot = [r for r in RESULTS if r["stratum"] in PROTECTED_STRATA]
    unprot = [r for r in RESULTS if r["stratum"] not in PROTECTED_STRATA]

    if UNHARDENED:
        # A measurement, not a gate. This mode is the design that makes
        # none of the promises below, and the point of running it is
        # that its numbers differ.
        disp = [r for r in prot if r["clock_err"] > 0]
        hung = [r for r in prot if r["hang"]]
        cocotb.log.info(
            "UNHARDENED: %d of %d mtime injections displaced the clock, "
            "worst %d ticks; %d never reached the final read-back; "
            "%d were announced",
            len(disp), len(prot),
            max((r["clock_err"] for r in prot), default=0),
            len(hung), sum(r["ecc_events"] > 0 for r in prot))
        return

    # H6 promise 1: an upset in mtime or its check bits leaves the
    # architectural clock unchanged at every port.
    wrong = [r for r in prot if not r["clock_ok"]]
    assert not wrong, (
        "{} of {} single-bit upsets in the protected codeword left the "
        "clock wrong; first: {}".format(len(wrong), len(prot), wrong[0]))

    # H6 promise 2: and the deadline is not moved either. The clock and
    # the comparison are two different outputs and a codec that
    # corrected the read path and not the comparator would pass the
    # first criterion and fail this one.
    moved = [r for r in prot if not r["deadline_ok"]]
    assert not moved, (
        "{} of {} protected injections moved the deadline".format(
            len(moved), len(prot)))

    # H6 promise 3: EVERY one of them is announced. A correction nobody
    # can see is docs/43 section 6.5's complaint, and this is the
    # criterion that says this wave did not repeat it.
    silent = [r for r in prot if r["ecc_events"] == 0]
    assert not silent, (
        "{} of {} protected injections were corrected without being "
        "announced on mt_ecc_o; first: {}".format(
            len(silent), len(prot), silent[0]))

    # H6 promise 4: and nothing else is announced. mt_ecc_o must not
    # fire on an upset in a register the codec does not cover, or the
    # counter in soc_busstat.v is reporting something else's upsets.
    noisy = [r for r in unprot if r["ecc_events"] > 0]
    assert not noisy, (
        "mt_ecc_o fired on {} injections outside the codeword".format(
            len(noisy)))

    # And the classes are what those four promises imply.
    assert all(r["cls"] == "CORRECTED" for r in prot), (
        {r["cls"] for r in prot})
    # DISPLACED and NOT-OBSERVED are two different things and the
    # summary keeps them apart. A run that hung never reached its final
    # read of mtime, so its clock_ok is False because nothing looked --
    # counting those as "the clock was wrong" would credit mtimecmp with
    # a corruption it cannot cause, since nothing in mtimecmp reaches
    # mtime.
    cocotb.log.info(
        "H6: %d protected injections, all CORRECTED, all announced, "
        "clock unchanged; %d unprotected: %d displaced the clock "
        "(worst %d ticks), %d never reached the final read-back",
        len(prot), len(unprot),
        sum(r["clock_err"] > 0 for r in unprot),
        max((r["clock_err"] for r in unprot), default=0),
        sum(r["hang"] != "" for r in unprot))
