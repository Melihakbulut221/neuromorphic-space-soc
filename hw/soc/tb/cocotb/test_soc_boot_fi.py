"""Fault injection into the boot register block's own state.

WHY THIS EXISTS

`docs/68` section 12 states it in as many words: *"No fault-injection
campaign was re-run ... `soc_boot.v` is unprotected: an upset in the boot
counter changes a boot decision, an upset in the report corrupts a
diagnosis, and neither is voted, coded or scrubbed."* Section 16 item 1
then ranks hardening it first, because eight of the block's 92 flip-flops
decide whether the part tries to boot again.

So this campaign establishes the BASELINE as well as the delta, and the
two are kept apart everywhere: the numbers from `SOC_BOOT_FI_UNHARDENED`
are what the block docs/68 shipped does under upset, and the numbers from
the default build are what B1 does about it. Nothing in docs/68 is being
compared against; nothing in docs/68 measured this.

B1 makes three claims that neither a proof nor an argument can settle,
and each is an acceptance criterion in test_zz_summary:

  1. a single-bit upset anywhere in the 23 stored bits of any ONE
     replica leaves every register read UNCHANGED, and is announced in
     BSTAT.TMRERR/TMRCNT;
  2. the state B1 deliberately does NOT protect -- the two
     synchronisers, the system-reset sample, the report and the epoch --
     fails in a way this campaign can name, because the decision not to
     protect them is only a decision if its price is measured;
  3. nothing outside the protected word is announced, or the mismatch
     counter is a counter of something else's upsets.

METHOD, adapted from `docs/16` sections 1.2 to 1.6, and from
`test_soc_wdog_fi.py` and `test_soc_clint_fi.py` which are the two
campaigns this one is shaped after.

  * The DUT is `soc_boot` itself. **Only the stimulus reaches into the
    hierarchy.** Every observation is one a bench with a bus master and
    a reset pin could make: what a read of BSTRAP, BSTAT, BRPT and EPOCH
    returns, at a stamped cycle.
  * Per injection: power-on reset, then the workload, with one bit of
    one flip-flop XORed at a seeded-random cycle inside the measured
    window.
  * The GOLDEN MODEL decides right from wrong, always. It is a run of
    the same workload with no deposit. The design's own report only ever
    decides whether a wrong answer was ANNOUNCED; it never declares an
    answer correct.

THE WINDOW OPENS AT RESET RELEASE, WHICH IS NOT WHAT THE OTHER TWO
CAMPAIGNS DO, AND THE DIFFERENCE IS THE POINT

`test_soc_wdog_fi.py` and `test_soc_clint_fi.py` both put their bring-up
OUTSIDE the injection window, because in those blocks the bring-up is a
program writing configuration and an upset drawn there measures the
bring-up rather than the mission. **In this block the bring-up IS the
mission.** The straps are sampled three clocks after power-on reset
releases and never again; `armed_q` is set on that same release; the
whole of what this block decides is decided in the first four clocks of
a power cycle and then held for the rest of it. A campaign that opened
its window after the sample could never draw the upset that lands in the
sample, which is the one residual the unprotected synchronisers have.

So the window opens on the cycle after the power-on release and closes
before the final read-back, and `test_00_control` asserts that a draw at
the earliest cycle in the window is a draw before `BSTRAP.VALID` is set.

THE STRAP PATTERN IS 0b1001 AND THAT IS A DECISION, NOT A DEFAULT

`docs/58` section 8.1's lesson, one block across: a campaign drawn over
a field of zeros measures only the 0 -> 1 direction, and would report
that clearing a strap is impossible because there was nothing set to
clear. 0b1001 sets bits 0 and 3 and clears bits 1 and 2, so a drawn flip
is as likely to clear a one as to set a zero -- and, deliberately,
**NOBOOT (bit 2) is CLEAR on the board**, so an upset that sets it is a
part that refuses to load an image for the rest of the power cycle.
That is the failure `noboot_set` counts.

CLASSIFICATION, exactly one class per injection, in `docs/16` section
1.6's order:

    HANG       a bounded wait expired, or the slave stopped completing
    DETECTED   the report moved and the observation differs from golden
    SDC        the observation differs from golden and nothing was
               reported
    CORRECTED  the observation matches golden and the report moved
    MASKED     matches golden and nothing was reported

and eight further per-record facts, because five classes cannot carry
them and the ranking in soc_boot.v's B1 section is entirely about them:

    cnt_ok         every read of BSTAT.CNT was the golden value. THE
                   COLUMN THE DOCUMENT IS ABOUT.
    cnt_err        the largest absolute displacement of BSTAT.CNT, in
                   boots.
    gave_up_early  at some read, OVER was set while golden's was clear:
                   THE LOADER DOES NOT TOUCH THE FLASH ON A PART THAT
                   STILL HAD ATTEMPTS LEFT, and the counter is
                   saturating and power-on-only, so it stays that way
                   for the power cycle. A mission that stops retrying
                   after one spurious increment is lost.
    never_gives_up at the last read of the window, golden's OVER was set
                   and this run's was not: THE LADDER DOES NOT
                   TERMINATE. The watchdog cannot break the loop,
                   because docs/68 section 5.4's loader kicks it from
                   inside the copy.
    strap_ok       every read of the strap field was what the board
                   wired.
    noboot_set     NOBOOT read as 1 on a board that strapped it 0.
    valid_lost     BSTRAP.VALID read as 0 after it had read 1 -- the
                   sampling window reopened, which is soc_wdog.v W1's
                   hardware back door into the boot decision.
    record_ok      BRPT and EPOCH read back what was written.

WHAT THIS CAMPAIGN DOES **NOT** COVER

  * It is RTL, SINGLE-BIT, flip-flop only. No gate-level netlist, no
    back-annotated timing, no multi-bit strike, and no single-event
    transient in combinational logic -- which includes the voter, which
    has no state to inject into, and the whole of the next-state
    function.
  * TWO UPSETS ARE NOT COVERED and nothing about three replicas claims
    they are. soc_tmr_bank is written unconditionally every clock, which
    bounds the window in which a second upset in a different replica on
    the same bit is uncorrectable to ONE CLOCK CYCLE; it does not
    eliminate it, and in this block no reset ever repairs the word.
  * It says nothing about RATES. Every number is conditional on an upset
    having landed in the window, on a uniform choice of target and bit.
  * DETECTED depends on someone looking. BSTAT.TMRERR and TMRCNT are
    register fields; this block has no interrupt line and the map gives
    it none, so the only reader is the next boot's loader.
  * ONE WORKLOAD, ONE SEED, and the block alone. Nothing here runs
    soc_boot inside the SoC with a core and a loader in front of it, so
    the consequences named in the fact columns above are consequences
    the LOADER would draw from what it read, argued from
    hw/soc/tb/sw/boot.c and not run.
  * It cannot fail because a replica vanished in synthesis. Every target
    path exists in the RTL whatever the netlist holds;
    `sw/tests/test_soc_synthesis_guards.py` is the separate,
    netlist-level criterion and neither substitutes for the other.
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
from golden.memmap_gen import APB_SLOTS  # noqa: E402,F401

BSTRAP = 0x000
BSTAT = 0x004
BRPT = 0x008
EPOCH = 0x00C

STRAP_VALID = 1 << 31
STRAP_WDOGDIS = 1 << 16
STAT_LAST = 1 << 8
STAT_OVER = 1 << 9
# B1's report, the top five bits of BSTAT. Masked out of the observation
# for the reason test_soc_wdog_fi.py keeps TMRERR out of its trace:
# comparing the design's own report against golden would make every
# ANNOUNCED CORRECTION look like a wrong answer, and every record in the
# protected strata would classify SDC.
STAT_TMRERR = 1 << 31
STAT_TMRCNT = 0xF << 27
STAT_REPORT = STAT_TMRERR | STAT_TMRCNT

# Makefile.soc_boot_fi's parameters, which are soc_top.v's. THE SHIPPED
# WIDTH, unlike the functional suite: nothing in this campaign needs the
# counter to saturate, only to pass the attempt limit, so there is no
# reason to measure four counter bits when the part has eight.
NSTRAP = 4
CNT_W = 8
LIMIT = 3

# What the board wires. Both polarities, and NOBOOT clear -- see the
# module docstring.
STRAP_PINS = 0b1001
WDOG_DIS_PIN = 0

CLK_NS = 10
# Bounded waits. A wait that expires is a HANG record, never a hung
# suite -- docs/16 section 1.3.
WAIT_BUDGET = 200

# One seed drives every randomised injection cycle; the targets, the
# bits and the draw counts are constants. docs/16 section 1.7.
SEED = 0x5B007001
DRAWS_PER_BIT = 4

UNHARDENED = bool(os.environ.get("SOC_BOOT_FI_UNHARDENED"))

RECORDS = os.environ.get(
    "SOC_BOOT_FI_RECORDS",
    "records_soc_boot_fi_h0.csv" if UNHARDENED else "records_soc_boot_fi.csv")


# ---------------------------------------------------------------------
# the protected word's layout, recomputed rather than copied
# ---------------------------------------------------------------------
# soc_boot.v's localparams, redone here from NSTRAP and CNT_W with the
# same arithmetic, so that a field added to the word moves this list
# instead of silently shifting every injection one bit sideways.
# `test_00_control` asserts the total against the width of the bank the
# DUT actually holds, which is the check that the arithmetic agrees with
# the RTL rather than with itself.
P_DLY = 0
P_VALID = P_DLY + 2
P_STRAP = P_VALID + 1
P_WDIS = P_STRAP + NSTRAP
P_ARMED = P_WDIS + 1
P_SYS = P_ARMED + 1
P_CNT = P_SYS + 1
P_TMRERR = P_CNT + CNT_W
TMC_W = 4
P_TMRCNT = P_TMRERR + 1
PDEC_W = P_TMRERR
PFULL_W = P_TMRCNT + TMC_W

# Where the decision word is stored in each build.
BANK_A = "g_prot_plain.plain" if UNHARDENED else "g_prot_tmr.u_prot_a.bits"
BANK_B = "g_prot_tmr.u_prot_b.bits"
BANK_C = "g_prot_tmr.u_prot_c.bits"


# ---------------------------------------------------------------------
# targets
# ---------------------------------------------------------------------
# Every entry is (stratum, hierarchical path, bit offset, bit indices).
# An injection flips bit `offset + i` of `path` and records `i`, so a
# field's records are indexed by the field's own bit in both builds.
#
# THE STRATA ARE THE DECISIONS, not the flip-flops -- docs/42 section
# 4.1 and docs/41 section 3.1: a stratum is a thing about which one
# could make a different hardening decision. soc_boot.v's B1 section
# makes six of them for the protected word and four for what it leaves
# alone, and this list is that section, executable.

# The six decision fields. THE SAME STRATUM NAMES AND THE SAME BIT
# INDICES IN BOTH BUILDS, which is what makes the counterfactual a
# record-for-record comparison of the same upset rather than of two
# campaigns that happened to be run. Replica A carries POL = 0 and MIX =
# 0, so bit `i` of its storage IS bit `i` of the word -- which is why
# the hardened build can inject at the same field offsets as the plain
# one and why the mixed replicas are separate strata below.
DECISION = [
    ("cnt", BANK_A, P_CNT, tuple(range(CNT_W))),
    ("armed", BANK_A, P_ARMED, (0,)),
    ("valid", BANK_A, P_VALID, (0,)),
    ("strap", BANK_A, P_STRAP, tuple(range(NSTRAP))),
    ("wdis", BANK_A, P_WDIS, (0,)),
    ("dly", BANK_A, P_DLY, tuple(range(2))),
    # THE ONE THE CAMPAIGN MOVED. It was in UNPROTECTED below, as a
    # plain flip-flop and its own stratum, on the argument that a
    # register rewritten every clock sheds an upset on its own. Every
    # draw came back SDC with `gave_up_early` set, because an upset here
    # manufactures a release edge and the counter it moves is saturating
    # and power-on-only. soc_boot.v's P_SYS localparam is the record.
    ("sysq", BANK_A, P_SYS, (0,)),
]

# The state B1 ADDED, as a stratum of its own and not folded into
# `cnt` -- docs/43's `regfile_ecc` argument and docs/58's `mtime_chk`:
# they are five flip-flops the design did not have, an upset can land in
# them exactly as it can land in a decision bit, and folding them in
# would move that stratum's measured rate for two unrelated reasons at
# once.
REPORT = [("report", BANK_A, P_TMRERR, tuple(range(1 + TMC_W)))]

# The two mixed replicas, whole. Every stored bit of either is an XOR of
# two or three word bits, so there is no field-wise reading of them and
# they are injected as whole banks rather than as fields.
MIXED = [
    ("prot_b", BANK_B, 0, tuple(range(PFULL_W))),
    ("prot_c", BANK_C, 0, tuple(range(PFULL_W))),
]

# What B1 deliberately leaves unprotected. IDENTICAL IN BOTH BUILDS, and
# that is the calibration: docs/55 section 8.3 had to refuse a 19 %
# improvement because its frozen-die stratum moved, and docs/56 and
# docs/58 could report their deltas because the same control came back
# at exactly zero drift. If one of these 150 records changes verdict
# between the two builds, the delta is a difference of two things and
# test_zz_summary says so instead of reporting it.
UNPROTECTED = [
    # The strap synchronisers, rewritten from the pins every clock. The
    # residual is the two-clock sampling window, which is why the
    # injection window opens at reset release.
    ("strap_sync", "sync0", 0, tuple(range(NSTRAP))),
    ("strap_sync", "sync1", 0, tuple(range(NSTRAP))),
    ("wdog_sync", "wsync0", 0, (0,)),
    ("wdog_sync", "wsync1", 0, (0,)),
    # Evidence, not authority. 64 flip-flops, 69.6 % of the block as
    # docs/68 shipped it, and nothing branches on either of them.
    ("brpt", "brpt_q", 0, tuple(range(32))),
    ("epoch", "epoch_q", 0, tuple(range(32))),
]

TARGETS = DECISION + (REPORT + MIXED if not UNHARDENED else []) + UNPROTECTED
PROTECTED_STRATA = {g for g, _p, _o, _b in DECISION + REPORT + MIXED}
CONTROL_STRATA = {g for g, _p, _o, _b in UNPROTECTED}


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
class Boot:
    """A protocol-legal APB master and the two reset pins.

    Deliberately a reduced copy of test_soc_boot.py's helpers rather
    than an import of them: those assert on PREADY and PSLVERR at every
    access, and an assertion inside a fault-injection run turns a data
    point into a suite failure. Here a protocol violation is recorded
    and classified as a HANG.
    """

    def __init__(self, dut, stop):
        self.dut = dut
        self.stop = stop
        self.broken = None

    async def _xact(self, addr, we, wdata=0):
        dut = self.dut
        await RisingEdge(dut.clk_i)
        dut.psel_i.value = 1
        dut.penable_i.value = 0
        dut.paddr_i.value = addr
        dut.pwrite_i.value = we
        dut.pwdata_i.value = wdata
        await RisingEdge(dut.clk_i)
        dut.penable_i.value = 1
        await Timer(1, unit="ns")
        v = val(dut.prdata_o)
        if val(dut.pready_o) != 1 or val(dut.pslverr_o) != 0:
            self.broken = "APB contract broken at 0x{:03x}".format(addr)
        at = self.stop["cycles"]
        await RisingEdge(dut.clk_i)
        dut.psel_i.value = 0
        dut.penable_i.value = 0
        dut.pwrite_i.value = 0
        await Timer(1, unit="ns")
        return v, at

    async def read(self, addr):
        return await self._xact(addr, 0)

    async def write(self, addr, data):
        await self._xact(addr, 1, data)

    async def boot(self, cycles=3):
        """A watchdog stage-2 reset: the system reset only.

        THE STRAP PINS ARE INVERTED WHILE THE RESET IS ASSERTED and put
        back afterwards, so that a run in which the sample was retaken
        is visibly different from one in which it was not. Without that
        the `valid` stratum could lose its flag and nothing would look
        wrong, because the pins would still be reading what was already
        latched -- which is the shape docs/41 section 8.4 calls a
        measurement narrower than the conclusion drawn from it.
        """
        dut = self.dut
        await RisingEdge(dut.clk_i)
        dut.rst_ni.value = 0
        dut.strap_i.value = (~STRAP_PINS) & ((1 << NSTRAP) - 1)
        dut.wdog_dis_i.value = 1 - WDOG_DIS_PIN
        for _ in range(cycles):
            await RisingEdge(dut.clk_i)
        dut.rst_ni.value = 1
        dut.strap_i.value = STRAP_PINS
        dut.wdog_dis_i.value = WDOG_DIS_PIN
        for _ in range(2):
            await RisingEdge(dut.clk_i)
        await Timer(1, unit="ns")


async def power_on(dut):
    dut.rst_por_ni.value = 0
    dut.rst_ni.value = 0
    dut.psel_i.value = 0
    dut.penable_i.value = 0
    dut.paddr_i.value = 0
    dut.pwrite_i.value = 0
    dut.pwdata_i.value = 0
    dut.strap_i.value = STRAP_PINS
    dut.wdog_dis_i.value = WDOG_DIS_PIN
    for _ in range(5):
        await RisingEdge(dut.clk_i)
    await Timer(1, unit="ns")
    dut.rst_por_ni.value = 1
    dut.rst_ni.value = 1
    await RisingEdge(dut.clk_i)


# =====================================================================
# the workload, and what is observed of it
# =====================================================================
class Trace:
    """Everything in here is visible through a bus read."""

    def __init__(self):
        self.reads = []       # (label, cycle, value)
        self.hang = None
        self.cycles = 0
        self.window = 0
        self.report = 0       # BSTAT's top five bits at the final read

    def observation(self):
        """What a bench sees, EXCLUDING the design's own report."""
        return (tuple(self.reads), self.hang)


async def _watch(dut, stop):
    """Count clock cycles for the read stamps and the injector.

    The `done` check is AFTER the sample and not in the loop condition,
    docs/58 section 8.2's race: written the other way the watcher
    completes one more body after the run has ended, which is during the
    next run's power-on reset.
    """
    cycle = 0
    while True:
        await RisingEdge(dut.clk_i)
        await Timer(2, unit="ns")
        if stop["done"]:
            return
        cycle += 1
        stop["cycles"] = cycle


async def run_workload(dut, deposit=None):
    """One injection: power on, four boots, the runaway store, read back.

    `deposit` is (path, bit, cycle_within_window) or None.
    """
    stop = {"done": False, "cycles": 0}
    trace = Trace()
    c = Boot(dut, stop)

    await power_on(dut)
    watcher = cocotb.start_soon(_watch(dut, stop))

    # ---- the window opens HERE, on the cycle after the power-on
    # release, so that the strap sample is inside it. See the docstring.
    if deposit is not None:
        path, bit, when = deposit

        async def _later():
            for _ in range(when):
                await RisingEdge(dut.clk_i)
            await Timer(4, unit="ns")
            sig = handle(dut, path)
            sig.value = val(sig) ^ (1 << bit)

        cocotb.start_soon(_later())

    # ---- phase A: the power-on boot ----
    for _ in range(6):
        await RisingEdge(dut.clk_i)
    for label, addr in (("bstrap0", BSTRAP), ("bstat0", BSTAT)):
        v, at = await c.read(addr)
        trace.reads.append((label, at, v))

    # ---- phase B: the record ----
    await c.write(BRPT, 0xB0000001)
    await c.write(EPOCH, 0x00000001)
    for label, addr in (("brpt0", BRPT), ("epoch0", EPOCH)):
        v, at = await c.read(addr)
        trace.reads.append((label, at, v))

    # ---- phase C: three boots, which walks the whole ladder ----
    #
    # At LIMIT = 3 the counter reads 0, 1, 2, 3 and the two derived
    # flags move at 2 and at 3, so the golden run passes LAST and then
    # OVER -- the two decisions the loader takes. A campaign that
    # stopped before OVER could not tell a part that gave up early from
    # a part that gave up on time.
    for n in (1, 2, 3):
        await c.boot()
        for label, addr in (("bstrap%d" % n, BSTRAP), ("bstat%d" % n, BSTAT),
                            ("brpt%d" % n, BRPT), ("epoch%d" % n, EPOCH)):
            v, at = await c.read(addr)
            trace.reads.append((label, at, v))
        await c.write(EPOCH, n + 1)

    # ---- phase D: the runaway store ----
    #
    # The property the block exists for, inside the campaign: a core
    # spraying wild stores must not be able to move the counter, and
    # must not be able to clear the mismatch report either.
    for addr in (BSTRAP, BSTAT):
        for data in (0x00000000, 0xFFFFFFFF):
            await c.write(addr, data)
    v, at = await c.read(BSTAT)
    trace.reads.append(("bstat_after_writes", at, v))

    # ---- the window closes here ----
    trace.window = stop["cycles"]

    # ---- the final read-back, OUTSIDE the window ----
    for label, addr in (("bstrap_end", BSTRAP), ("bstat_end", BSTAT),
                        ("brpt_end", BRPT), ("epoch_end", EPOCH)):
        v, at = await c.read(addr)
        trace.reads.append((label, at, v))
        if label == "bstat_end":
            trace.report = v & STAT_REPORT

    if c.broken is not None:
        trace.hang = c.broken

    stop["done"] = True
    await RisingEdge(dut.clk_i)
    await Timer(3, unit="ns")
    watcher.cancel()
    trace.cycles = stop["cycles"]

    # BSTAT's report bits are masked out of every recorded read, so that
    # an announced correction is not itself a difference from golden.
    trace.reads = [(lab, cyc, (v & ~STAT_REPORT) if lab.startswith("bstat")
                    else v)
                   for lab, cyc, v in trace.reads]
    return trace


def classify(golden, trace):
    flagged = trace.report != 0
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


def _by_label(trace):
    return {lab: v for lab, _c, v in trace.reads}


def facts(golden, trace):
    """The eight columns five classes cannot carry."""
    g = _by_label(golden)
    t = _by_label(trace)

    stat_labels = [lab for lab in g if lab.startswith("bstat")]
    strap_labels = [lab for lab in g if lab.startswith("bstrap")]

    cnt_ok = True
    cnt_err = 0
    gave_up_early = False
    for lab in stat_labels:
        if lab not in t:
            cnt_ok = False
            continue
        gc, tc = g[lab] & 0xFF, t[lab] & 0xFF
        if gc != tc:
            cnt_ok = False
            cnt_err = max(cnt_err, abs(gc - tc))
        if (t[lab] & STAT_OVER) and not (g[lab] & STAT_OVER):
            gave_up_early = True

    # THE OTHER FAILURE, and it is not the negation of the first: a
    # counter that never reaches the limit is a loader that retries for
    # ever. Read at the last observation inside the window, where golden
    # has finished its third boot and is over the limit.
    last = "bstat_after_writes"
    never_gives_up = bool(
        (g.get(last, 0) & STAT_OVER) and not (t.get(last, 0) & STAT_OVER))

    strap_ok = True
    noboot_set = False
    valid_lost = False
    seen_valid = False
    for lab in strap_labels:
        if lab not in t:
            strap_ok = False
            continue
        gs, ts = g[lab] & 0xFFFF, t[lab] & 0xFFFF
        if gs != ts:
            strap_ok = False
        # NOBOOT is bit 2 of the strap field and the board wires it 0.
        if (ts & 0b100) and not (gs & 0b100):
            noboot_set = True
        if t[lab] & STRAP_VALID:
            seen_valid = True
        elif seen_valid:
            valid_lost = True

    record_ok = all(
        lab in t and t[lab] == g[lab]
        for lab in g if lab.startswith(("brpt", "epoch")))

    return {
        "cnt_ok": cnt_ok,
        "cnt_err": cnt_err,
        "gave_up_early": gave_up_early,
        "never_gives_up": never_gives_up,
        "strap_ok": strap_ok,
        "noboot_set": noboot_set,
        "valid_lost": valid_lost,
        "record_ok": record_ok,
        "tmr_report": trace.report,
    }


# =====================================================================
# the campaign
# =====================================================================
RESULTS = []


def _draws(window):
    """Every (stratum, path, offset, bit, cycle) the campaign injects.

    The seed is derived PER TARGET BIT rather than consumed from one
    stream, so the cycle drawn for `cnt` bit 3 is the same number
    whatever else is in the target list. Without that, the unhardened
    counterfactual -- which has no `report`, `prot_b` or `prot_c`
    stratum -- would silently re-roll every draw after it and the two
    runs could not be compared record for record. That comparison is the
    calibration and it is the whole reason this function looks like this.

    The PATH is in the key as well as the stratum, because two entries
    share the `strap_sync` stratum and a key without it would give
    `sync0` bit 2 and `sync1` bit 2 the same draw.
    """
    out = []
    for stratum, path, offset, bits in TARGETS:
        for bit in bits:
            for draw in range(DRAWS_PER_BIT):
                rng = random.Random(
                    "{}:{}:{}:{}:{}".format(SEED, stratum, path, bit, draw))
                out.append((stratum, path, offset, bit, draw,
                            rng.randrange(1, window)))
    return out


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    dut.rst_por_ni.value = 0
    dut.rst_ni.value = 0
    dut.psel_i.value = 0
    dut.penable_i.value = 0
    dut.paddr_i.value = 0
    dut.pwrite_i.value = 0
    dut.pwdata_i.value = 0
    dut.strap_i.value = STRAP_PINS
    dut.wdog_dis_i.value = WDOG_DIS_PIN
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

    # 2. The clean run never reports a mismatch. If it did, the three
    #    replicas disagree with no fault injected and every DETECTED
    #    below would be meaningless.
    assert golden.report == 0, (
        "BSTAT reports a TMR mismatch on a clean run: 0x{:08x}".format(
            golden.report))

    # 3. THE WORKLOAD REACHES BOTH DECISIONS. A campaign whose golden run
    #    never passed the attempt limit could not tell a part that gave
    #    up early from one that gave up on time, and `never_gives_up`
    #    would be identically false.
    g = _by_label(golden)
    assert (g["bstat0"] & 0xFF) == 0, "the power-on boot is not boot zero"
    assert (g["bstat1"] & 0xFF) == 1
    assert (g["bstat2"] & 0xFF) == 2 and (g["bstat2"] & STAT_LAST)
    assert (g["bstat3"] & 0xFF) == 3 and (g["bstat3"] & STAT_OVER)
    assert g["bstat_after_writes"] & STAT_OVER, (
        "the last read inside the window is not past the limit, so "
        "never_gives_up cannot fire")

    # 4. THE STRAPS ARE BIT-DIVERSE AND NOBOOT IS CLEAR. docs/58 section
    #    8.1's lesson: a campaign over a field of zeros measures one
    #    direction and calls it the answer.
    assert (g["bstrap0"] & 0xFFFF) == STRAP_PINS, (
        "BSTRAP does not read the wired straps: 0x{:08x}".format(g["bstrap0"]))
    assert bin(STRAP_PINS).count("1") == 2 and not (STRAP_PINS & 0b100)
    assert g["bstrap0"] & STRAP_VALID
    assert not (g["bstrap0"] & STRAP_WDOGDIS)

    # 5. The record survives every boot and the counter refuses every
    #    write, on the clean run -- the two things the injected runs are
    #    measured against.
    assert g["brpt3"] == 0xB0000001 and g["epoch3"] == 3
    assert (g["bstat_after_writes"] & 0xFF) == 3

    # 6. THE FIELD ARITHMETIC AGREES WITH THE RTL. The layout above is
    #    recomputed from NSTRAP and CNT_W; this asserts the total against
    #    the width of the bank the DUT actually holds, which is what
    #    would catch a field being inserted in the middle of the word.
    bank = handle(dut, BANK_A)
    want = PDEC_W if UNHARDENED else PFULL_W
    assert len(bank.value.binstr) == want, (
        "the storage bank is {} bits and this file computed {}; every "
        "injection below would land one bit sideways".format(
            len(bank.value.binstr), want))

    # 7. THE INJECTION MECHANISM DEMONSTRABLY REACHES A TARGET, and the
    #    two builds differ. A deposit into the boot counter's top bit
    #    must come back CORRECTED when hardened and SDC when not. MASKED
    #    on the hardened probe would mean the deposit is not landing and
    #    the whole campaign would be measuring nothing.
    probe = await run_workload(
        dut, deposit=(BANK_A, P_CNT + CNT_W - 1, 20))
    cls, _ok = classify(golden, probe)
    f = facts(golden, probe)
    if UNHARDENED:
        assert cls == "SDC", (
            "a flip of the boot counter's top bit in the unprotected "
            "design came back {} rather than SDC".format(cls))
        assert probe.report == 0
        assert f["gave_up_early"], (
            "a flip of BOOTCNT bit {} did not put the unprotected part "
            "over its attempt limit".format(CNT_W - 1))
    else:
        assert cls == "CORRECTED", (
            "a flip of the boot counter's top bit came back {} rather "
            "than CORRECTED. MASKED here means the deposit never "
            "landed.".format(cls))
        assert f["cnt_ok"] and not f["gave_up_early"]
        assert probe.report & STAT_TMRERR

    # 8. Every drawn cycle lands inside the window, and the earliest of
    #    them is before the strap sample -- which is the residual the
    #    unprotected synchronisers have and the reason the window opens
    #    where it does.
    assert golden.window < golden.cycles, (
        "the injection window must close before the final read-back")
    draws = _draws(golden.window)
    for _s, _p, _o, _b, _d, when in draws:
        assert 0 < when < golden.window
    # The window opens before the strap sample, which is what makes the
    # synchroniser residual DRAWABLE. It is drawn rarely on purpose --
    # the sampling window is two clocks of the campaign's hundred, so a
    # uniform draw hits it about twice in a hundred -- and
    # test_02_directed is what demonstrates the consequence.
    assert min(w for *_r, w in draws) <= 4, (
        "no draw lands in the first four clocks, where the straps are "
        "sampled; the sampling residual cannot be measured")

    # 9. No target is a wire the design drives continuously. Every path
    #    is a `reg` in soc_boot.v or in soc_tmr_bank.v -- never the voted
    #    `prot` wire, which is docs/16 section 1.8's recorded mistake.
    for _g, path, _o, _b in TARGETS:
        assert path.split(".")[-1] in ("plain", "bits", "sync0", "sync1",
                                       "wsync0", "wsync1",
                                       "brpt_q", "epoch_q"), path

    dut._log.info("control: golden %d cycles, window %d, %d targets, "
                  "%d draws, hardened=%s",
                  golden.cycles, golden.window, len(TARGETS), len(draws),
                  not UNHARDENED)


@cocotb.test(timeout_time=7200, timeout_unit="us")
async def test_01_campaign(dut):
    await setup(dut)
    golden = await run_workload(dut)
    assert golden.hang is None

    for stratum, path, offset, bit, draw, when in _draws(golden.window):
        trace = await run_workload(dut, deposit=(path, offset + bit, when))
        cls, out_ok = classify(golden, trace)
        rec = {"stratum": stratum, "path": path, "bit": bit, "draw": draw,
               "abs_bit": offset + bit, "cycle": when, "cls": cls,
               "out_ok": out_ok, "hang": trace.hang or ""}
        rec.update(facts(golden, trace))
        RESULTS.append(rec)

    # The per-record file the calibration diffs. Written here rather than
    # in the summary so that it exists even if an acceptance criterion
    # below fails -- a campaign whose records vanish when it fails is a
    # campaign that cannot be debugged.
    cols = ["stratum", "path", "bit", "draw", "abs_bit", "cycle", "cls", "out_ok",
            "hang", "cnt_ok", "cnt_err", "gave_up_early", "never_gives_up",
            "strap_ok", "noboot_set", "valid_lost", "record_ok", "tmr_report"]
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
    seen = []
    for g, _p, _o, _b in TARGETS:
        if g in seen:
            continue
        seen.append(g)
        sub = [r for r in RESULTS if r["stratum"] == g]
        h = {}
        for r in sub:
            h[r["cls"]] = h.get(r["cls"], 0) + 1
        dut._log.info(
            "  %-11s n=%-4d %-42s cnt_ok=%d/%d strap_ok=%d/%d record_ok=%d/%d "
            "early=%d never=%d noboot=%d valid_lost=%d announced=%d "
            "worst_cnt_err=%d",
            g, len(sub), str(h),
            sum(r["cnt_ok"] for r in sub), len(sub),
            sum(r["strap_ok"] for r in sub), len(sub),
            sum(r["record_ok"] for r in sub), len(sub),
            sum(r["gave_up_early"] for r in sub),
            sum(r["never_gives_up"] for r in sub),
            sum(r["noboot_set"] for r in sub),
            sum(r["valid_lost"] for r in sub),
            sum(r["tmr_report"] != 0 for r in sub),
            max(r["cnt_err"] for r in sub))


@cocotb.test(timeout_time=400, timeout_unit="us")
async def test_02_directed(dut):
    """The two residuals a UNIFORM campaign under-samples, driven directly.

    docs/58 section 8.3's shape: a class that is empty by construction
    in the campaign gets a directed test rather than a bigger campaign,
    and the two are reported separately so that the campaign's rates
    stay conditional probabilities over a uniform draw.

    Both of these are things B1 does **not** fix, and they are here
    because a hardening document that only demonstrated what its
    mechanism catches would be describing the mechanism rather than the
    block.
    """
    await setup(dut)
    golden = await run_workload(dut)

    # ---- 1. THE SAMPLING WINDOW ----------------------------------
    #
    # `sync1` feeds the latch and the latch closes on one clock. An
    # upset in `sync1` bit 2 on that clock puts NOBOOT into `strap_q`
    # for the rest of the power cycle -- the part reports "do not load
    # an image" on a board that wired the opposite -- and B1 does
    # nothing about it, because sync1 is not in the protected word and
    # putting it there would protect a register whose value is a copy of
    # a pin for two clocks out of a mission.
    #
    # The clock is FOUND rather than written down: the sample is three
    # clocks after the release and the harness's cycle counter starts on
    # the release, so hard-coding it would be hard-coding an off-by-one.
    # The scan covers the first seven cycles, which is every cycle at
    # which a sync1 upset could still reach the latch; sync0's
    # equivalent cycle is one earlier and is NOT scanned, so the figure
    # logged below is a lower bound on the exposure across all ten
    # synchroniser flip-flops and docs/69 section 8.6 says so.
    latched = []
    for when in range(1, 8):
        t = await run_workload(dut, deposit=("sync1", 2, when))
        if _by_label(t)["bstrap_end"] & 0b100:
            latched.append(when)
    assert latched, (
        "no cycle in the first seven put a synchroniser upset into the "
        "strap latch; either the sample has moved or this test has "
        "stopped exercising the residual it exists for")
    # And it is PERMANENT and SILENT: still wrong at the last read, four
    # boots later, with nothing announced.
    t = await run_workload(dut, deposit=("sync1", 2, latched[0]))
    f = facts(golden, t)
    assert f["noboot_set"] and not f["strap_ok"]
    assert t.report == 0, (
        "the sampling residual was announced; it is not a TMR mismatch "
        "and nothing in this block can see it")
    dut._log.info(
        "directed: a sync1 upset at cycle %s of %d latches NOBOOT for the "
        "power cycle, in %s -- %d of %d cycles in the window would do it "
        "(%.1f %%), which is why the uniform campaign draws it rarely",
        latched, golden.window,
        "the unprotected block" if UNHARDENED else "the HARDENED block",
        len(latched), golden.window, 100.0 * len(latched) / golden.window)

    # ---- 2. THE REOPENED SAMPLING WINDOW, AND WHAT IT IS ACTUALLY
    #         WORTH ----------------------------------------------
    #
    # The B1 section of soc_boot.v argues that `valid_q` is protected
    # because clearing it REOPENS THE SAMPLING WINDOW, which is
    # soc_wdog.v W1's hardware back door into the boot decision. That
    # argument is right about the mechanism and the campaign then
    # measured what it is worth on this board: every draw into `valid`
    # and `dly` in the unprotected build came back MASKED.
    #
    # This test is why. `dly` SATURATES at 2 -- it stops incrementing on
    # the clock the sample is taken -- so clearing `valid_q` does not
    # restart a three-clock delay; it re-latches `sync1` on the VERY
    # NEXT CLOCK. And `sync1` is two flops behind pins that a board
    # holds static, so what a reopened window latches is the value that
    # was already there.
    #
    # So the back door exists and, on a board with static straps, it
    # opens onto the same room. Both halves are demonstrated: with the
    # pins moved before the flag is cleared the re-latch takes the new
    # value, and with the pins static it does not.
    async def _resample(deposit, move_pins_first):
        stop = {"done": False, "cycles": 0}
        c = Boot(dut, stop)
        await power_on(dut)
        w = cocotb.start_soon(_watch(dut, stop))
        for _ in range(25):
            await RisingEdge(dut.clk_i)
        if move_pins_first:
            dut.strap_i.value = (~STRAP_PINS) & ((1 << NSTRAP) - 1)
            for _ in range(4):     # long enough to reach sync1
                await RisingEdge(dut.clk_i)
        if deposit is not None:
            path, bit = deposit
            await Timer(4, unit="ns")
            sig = handle(dut, path)
            sig.value = val(sig) ^ (1 << bit)
        for _ in range(10):
            await RisingEdge(dut.clk_i)
        v, _at = await c.read(BSTRAP)
        stop["done"] = True
        await RisingEdge(dut.clk_i)
        await Timer(3, unit="ns")
        w.cancel()
        dut.strap_i.value = STRAP_PINS
        return v

    inv = (~STRAP_PINS) & ((1 << NSTRAP) - 1)

    # The control: moving the pins on a healthy part changes nothing,
    # which is D4 and is what makes the two rows below attributable.
    assert (await _resample(None, True)) & 0xFFFF == STRAP_PINS

    moved = await _resample((BANK_A, P_VALID), True)
    static = await _resample((BANK_A, P_VALID), False)
    if UNHARDENED:
        assert moved & 0xFFFF == inv, (
            "clearing VALID with the pins moved did not reopen the "
            "sampling window: BSTRAP read 0x{:04x}, expected the pins "
            "0x{:04x}. The residual this test exists for is gone and the "
            "protection of `valid` has lost its reason.".format(
                moved & 0xFFFF, inv))
        assert static & 0xFFFF == STRAP_PINS, (
            "clearing VALID with STATIC pins changed the strap field, "
            "which contradicts the campaign's 12 MASKED records")
        dut._log.info(
            "directed: clearing VALID reopens the window for one clock. "
            "With the pins moved BSTRAP re-latches 0x%04x; with the pins "
            "static it re-latches 0x%04x, which is what it already held "
            "-- so on a board with static straps this upset is benign, "
            "and that is what the 12 MASKED `valid`/`dly` records are",
            moved & 0xFFFF, static & 0xFFFF)
    else:
        assert moved & 0xFFFF == STRAP_PINS and static & 0xFFFF == STRAP_PINS, (
            "the voted VALID flag did not mask the upset: 0x{:04x} / "
            "0x{:04x}".format(moved & 0xFFFF, static & 0xFFFF))
        dut._log.info(
            "directed: clearing VALID in ONE replica changed nothing, "
            "with the pins moved and with them static; BSTRAP reads "
            "0x%04x either way", moved & 0xFFFF)


@cocotb.test(timeout_time=10, timeout_unit="us")
async def test_zz_summary(dut):
    """The acceptance criteria: each is a promise B1 makes.

    They are written as promises and not as descriptions of the
    measurement, because a criterion written around a result is a
    criterion written to pass.
    """
    assert RESULTS, "the campaign did not run"

    prot = [r for r in RESULTS if r["stratum"] in PROTECTED_STRATA]
    ctrl = [r for r in RESULTS if r["stratum"] in CONTROL_STRATA]

    if UNHARDENED:
        # A measurement, not a gate. This mode is the design that makes
        # none of the promises below, and the point of running it is
        # that its numbers differ.
        cocotb.log.info(
            "UNHARDENED: of %d injections into the decision word, %d "
            "corrupted the boot counter (worst %d boots), %d gave up "
            "early, %d never gave up, %d misreported the straps, %d set "
            "NOBOOT, %d reopened the sampling window; %d were announced",
            len(prot),
            sum(not r["cnt_ok"] for r in prot),
            max((r["cnt_err"] for r in prot), default=0),
            sum(r["gave_up_early"] for r in prot),
            sum(r["never_gives_up"] for r in prot),
            sum(not r["strap_ok"] for r in prot),
            sum(r["noboot_set"] for r in prot),
            sum(r["valid_lost"] for r in prot),
            sum(r["tmr_report"] != 0 for r in prot))
        return

    # B1 promise 1: a single-bit upset in ANY ONE replica leaves every
    # register read unchanged.
    wrong = [r for r in prot if not r["out_ok"]]
    assert not wrong, (
        "{} of {} single-bit upsets in the protected word changed what a "
        "bus master reads; first: {}".format(len(wrong), len(prot), wrong[0]))

    # And the four consequence columns, separately, because a mechanism
    # that corrected the counter and not the straps would pass the
    # criterion above only by accident of what the workload read.
    for col in ("cnt_ok", "strap_ok", "record_ok"):
        bad = [r for r in prot if not r[col]]
        assert not bad, "{} protected injections failed {}: {}".format(
            len(bad), col, bad[0])
    for col in ("gave_up_early", "never_gives_up", "noboot_set",
                "valid_lost"):
        bad = [r for r in prot if r[col]]
        assert not bad, "{} protected injections produced {}: {}".format(
            len(bad), col, bad[0])

    # B1 promise 2: EVERY one of them is announced. A correction nobody
    # can see is docs/43 section 6.5's complaint.
    silent = [r for r in prot if r["tmr_report"] == 0]
    assert not silent, (
        "{} of {} protected injections were corrected without being "
        "announced in BSTAT; first: {}".format(
            len(silent), len(prot), silent[0]))

    # B1 promise 3: and nothing else is announced. A mismatch flag that
    # fired on an upset in brpt_q would make BSTAT.TMRCNT a counter of
    # something else's upsets.
    noisy = [r for r in ctrl if r["tmr_report"] != 0]
    assert not noisy, (
        "the mismatch report fired on {} injections outside the protected "
        "word; first: {}".format(len(noisy), noisy[0]))

    assert all(r["cls"] == "CORRECTED" for r in prot), {
        r["cls"] for r in prot}

    cocotb.log.info(
        "B1: %d protected injections, all CORRECTED, all announced, every "
        "register read unchanged; %d control injections: %d corrupted the "
        "counter, %d gave up early, %d never gave up, %d misreported the "
        "straps, %d lost the record",
        len(prot), len(ctrl),
        sum(not r["cnt_ok"] for r in ctrl),
        sum(r["gave_up_early"] for r in ctrl),
        sum(r["never_gives_up"] for r in ctrl),
        sum(not r["strap_ok"] for r in ctrl),
        sum(not r["record_ok"] for r in ctrl))
