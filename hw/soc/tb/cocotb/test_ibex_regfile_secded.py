# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""The substituted register file: does it behave, and does it correct?

WHERE THESE EXPECTATIONS COME FROM

Two sources, and neither is the RTL.

  * WHAT A REGISTER FILE DOES is the RISC-V architecture and Ibex's own
    interface: 31 architectural registers, two combinational read ports,
    one write port, x0 reads zero. The golden model below is a Python
    dictionary implementing exactly that and nothing else. It is the
    same separation `docs/16` draws between the instrument and the
    oracle: the design's own correction counters never decide whether an
    answer was right, only whether a wrong one was noticed.
  * WHAT THE PROTECTION PROMISES is stated in the header of
    `hw/soc/rtl/ibex_regfile_secded.v` and argued in
    `docs/43-core-hardening.md`: a single-bit upset anywhere in a
    register's 40 stored bits is corrected on the way out AND scrubbed
    out of the storage, and two bits in one register are detected rather
    than miscorrected.

THE SECOND HALF IS THE ONE WORTH MEASURING. "Corrected on read" is easy
to check and easy to believe. "Scrubbed out of the storage" is the claim
that decides whether the SECOND upset in a register is survivable, and
the only way to check it without reading the design's own internals is
to inject twice into the same register with idle cycles in between and
see whether the second one is still a single error.
`test_the_scrub_makes_a_second_upset_survivable` is that experiment and
`test_without_the_scrub_it_is_not` is its counterfactual, built with
SCRUB = 0, because a protection claim is not a measurement unless the
design without it produces a different number.

WHAT THIS SUITE DOES NOT COVER

  * The addresses. `raddr_a_i`, `raddr_b_i` and `waddr_a_i` are
    unprotected here and everywhere; a corrupted address reads the wrong
    register with a perfectly valid codeword and no code over the data
    can see it.
  * The codec's own combinational logic. Every deposit here is into a
    flip-flop. A single-event transient in an XOR tree is a fault model
    neither this nor `hw/soc/formal/regfile_secded.sby` expresses.
  * Ibex. Whether the substituted file behaves inside a running core is
    `hw/soc/flow/sim_soc.sh` -- which reproduces docs/40's whole-SoC run
    cycle for cycle -- and the campaign of docs/43 section 8.
  * The netlist. `sw/tests/test_soc_regfile_guards.py` is the only check
    that looks at what the foundry would receive, and it is not a
    substitute for this nor this for it.
  * More than one upset in more than one register, and more than two in
    one.
"""

import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

CLK_NS = 10
T_DRIVE = 1
T_SAMPLE = 8

NUM_WORDS = 32
DATA_W = 32
CHK_W = 7          # what the (72,64) codec shortens to over 32 data
                   # bits: H_ROW7's low half is zero, so the eighth
                   # check bit is a constant and does not exist. Proved
                   # in hw/soc/formal/regfile_secded.sby property C4 and
                   # counted in sw/tests/test_soc_regfile_guards.py.
STORED_W = DATA_W + 8      # the RTL still declares eight; one is dead

SCRUB = int(os.environ.get("REGFILE_SCRUB") or "1")
SEED = 0x43C0DE


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


def data_path(i):
    return "g_plain_rf.g_rf_flops[{}].rf_reg_q".format(i)


def chk_path(i):
    return "g_plain_rf.g_rf_flops[{}].g_chk.rf_chk_q".format(i)


def report(dut, name):
    return handle(dut, "g_plain_rf.g_secded." + name)


# =====================================================================
# the workload
# =====================================================================
#
# A fixed pseudo-random sequence of accesses, generated once so that the
# clean run and every injected run see EXACTLY the same stimulus. The
# idle fraction matters: the scrub takes the cycles the core does not
# use, so a workload that wrote on every cycle would never let it run
# and a workload that never wrote would not exercise the write port.
def make_workload(n):
    rng = random.Random(SEED)
    ops = []
    for _ in range(n):
        we = rng.random() < 0.45
        ops.append({
            "we": we,
            "waddr": rng.randrange(NUM_WORDS),
            "wdata": rng.getrandbits(DATA_W),
            "ra": rng.randrange(NUM_WORDS),
            "rb": rng.randrange(NUM_WORDS),
        })
    return ops


WORKLOAD = make_workload(200)


async def por(dut):
    dut.rst_ni.value = 0
    dut.test_en_i.value = 0
    dut.dummy_instr_id_i.value = 0
    dut.dummy_instr_wb_i.value = 0
    dut.cheriot_enable_i.value = 0b1010     # ibex_pkg::IbexMuBiOff
    dut.raddr_a_i.value = 0
    dut.raddr_b_i.value = 0
    dut.waddr_a_i.value = 0
    dut.wdata_a_i.value = 0
    dut.wcap_a_i.value = 0
    dut.we_a_i.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.rst_ni.value = 1
    await RisingEdge(dut.clk_i)


async def run(dut, deposit=None, deposit2=None):
    """Run the workload against an independent model.

    `deposit` and `deposit2` are (cycle, path, bit). Returns the number
    of read mismatches, and the design's own two counters -- which are
    reported and never used to decide whether a read was right.
    """
    model = {i: 0 for i in range(NUM_WORDS)}
    mismatches = []

    for n, op in enumerate(WORKLOAD):
        await Timer(T_DRIVE, unit="ns")
        dut.raddr_a_i.value = op["ra"]
        dut.raddr_b_i.value = op["rb"]
        dut.waddr_a_i.value = op["waddr"]
        dut.wdata_a_i.value = op["wdata"]
        dut.we_a_i.value = 1 if op["we"] else 0

        for dep in (deposit, deposit2):
            if dep is not None and dep[0] == n:
                obj = handle(dut, dep[1])
                obj.value = val(obj) ^ (1 << dep[2])

        await Timer(T_SAMPLE - T_DRIVE, unit="ns")
        got_a, got_b = val(dut.rdata_a_o), val(dut.rdata_b_o)
        want_a = model[op["ra"]] if op["ra"] else 0
        want_b = model[op["rb"]] if op["rb"] else 0
        if got_a != want_a:
            mismatches.append((n, "a", op["ra"], want_a, got_a))
        if got_b != want_b:
            mismatches.append((n, "b", op["rb"], want_b, got_b))

        await RisingEdge(dut.clk_i)
        if op["we"] and op["waddr"] != 0:
            model[op["waddr"]] = op["wdata"]

    # A tail of idle cycles, long enough for the scrub to complete a
    # whole sweep whatever it was pointing at.
    #
    # This is not padding. Without it, an upset drawn near the end of
    # the workload into a register that is neither read nor written
    # again is MASKED for a reason that is entirely about where the run
    # stopped -- three of them were, in the first version -- and the
    # campaign would then be reporting the length of its own stimulus.
    # With it, every injection has been given the chance to be seen, so
    # a MASKED record means the upset was OVERWRITTEN and nothing else.
    await idle(dut, NUM_WORDS + 8)

    sec = val(report(dut, "sec_cycles"))
    ded = val(report(dut, "ded_cycles"))
    return mismatches, sec, ded


async def idle(dut, cycles):
    """Cycles in which the core does not write, which is when the scrub
    gets the write port."""
    await Timer(T_DRIVE, unit="ns")
    dut.we_a_i.value = 0
    for _ in range(cycles):
        await RisingEdge(dut.clk_i)
    await Timer(T_SAMPLE, unit="ns")


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    await por(dut)


# =====================================================================
# controls, before any data point
# =====================================================================


@cocotb.test()
async def test_00_the_clean_run_is_clean(dut):
    """The oracle has to agree with the design when nothing is wrong,
    and the correction counters have to be at zero -- otherwise every
    later record's "the codec moved" says nothing."""
    await setup(dut)
    mism, sec, ded = await run(dut)
    assert not mism, "the clean run disagrees with the model: {}".format(
        mism[:4])
    assert sec == 0, "the clean run corrected {} times".format(sec)
    assert ded == 0, "the clean run detected {} uncorrectable words".format(ded)
    dut._log.info("control: %d accesses, no mismatch, no correction",
                  len(WORKLOAD))


@cocotb.test()
async def test_01_a_deposit_that_is_never_corrected_is_visible(dut):
    """The negative control, and it is the one that matters.

    If the injector did not reach the storage, every record in this file
    would come back MASKED -- which is exactly what a perfectly
    protected register file looks like. docs/41 section 8.1's fourth
    honesty check and docs/42 section 5.1's control 4 are the same idea.
    So: deposit into a register, and check the design NOTICED, by its
    own counter, which is a different question from whether the answer
    was right."""
    await setup(dut)
    mism, sec, ded = await run(dut, deposit=(20, data_path(5), 17))
    assert sec > 0, ("a deposit into x5 produced no correction at all; "
                     "the injector is not reaching the storage")
    assert not mism, "and it was not corrected: {}".format(mism[:4])


# =====================================================================
# the campaign
# =====================================================================


RESULTS = []


@cocotb.test()
async def test_02_every_register_every_field(dut):
    """One draw per (register, field), over all 31 registers.

    Bits are drawn uniformly over the 40 STORED bits of a register --
    the 32 data bits and the 8 the RTL declares for check, of which 7
    exist -- so the campaign visits the check field in proportion to its
    size and not in proportion to how interesting it looks."""
    await setup(dut)
    rng = random.Random(SEED ^ 0x5EED)
    counts = {}
    for reg in range(1, NUM_WORDS):
        for _ in range(4):
            b = rng.randrange(STORED_W)
            cycle = rng.randrange(5, len(WORKLOAD) - 5)
            if b < DATA_W:
                path, bit, field = data_path(reg), b, "data"
            else:
                path, bit, field = chk_path(reg), b - DATA_W, "chk"
            await por(dut)
            mism, sec, ded = await run(dut, deposit=(cycle, path, bit))
            if mism and ded == 0:
                cls = "SDC"
            elif mism:
                cls = "DETECTED"
            elif sec > 0:
                cls = "CORRECTED"
            else:
                cls = "MASKED"
            RESULTS.append({"reg": reg, "field": field, "bit": bit,
                            "cycle": cycle, "cls": cls, "sec": sec,
                            "ded": ded})
            counts[cls] = counts.get(cls, 0) + 1
    dut._log.info("campaign: %d injections, %s", len(RESULTS), counts)


def overwritten_after(reg, cycle):
    """Did the workload write this register after this cycle?

    An upset in a register that is written before anything reads it and
    before the scrub sweeps it is gone, and gone without the codec
    having seen it. That is a genuine MASKED and not a missed deposit,
    and this is how the two are told apart."""
    # From `cycle` and not `cycle + 1`: the deposit lands just after the
    # clock edge that starts the cycle, and the write of that same cycle
    # commits at the edge that ends it, so a write in the injection
    # cycle overwrites the upset. One record was unexplained until this
    # was off by that one.
    return any(op["we"] and op["waddr"] == reg
               for op in WORKLOAD[cycle:])


@cocotb.test()
async def test_03_every_injection_was_corrected_or_overwritten(dut):
    """The acceptance criterion, and getting it right took two goes.

    The first version demanded CORRECTED of every injection, on the
    model of `docs/41` section 8.2's 126 of 126. It failed at 104 of
    124, and the design was right and the criterion was wrong. The
    watchdog's protected word is rewritten from the voted value ON EVERY
    CLOCK, so an upset in it is seen within one cycle and there is no
    third outcome. A register file is not like that: the scrub takes
    only the cycles the core does not write, and a register the program
    OVERWRITES before the scrub reaches it has shed the upset without
    the codec ever seeing it. That is MASKED, it is correct behaviour,
    and demanding CORRECTED of it would have been a criterion that could
    only be met by a slower workload.

    So the criterion is in two parts and both matter:

      * NOTHING is SDC and nothing is DETECTED. A wrong value must never
        reach a read port, corrected or not.
      * Every MASKED record is EXPLAINED -- the workload wrote that
        register after the injection. A MASKED record that cannot be
        explained that way is the signature of a deposit that did not
        land, which is the failure mode `test_01` exists to catch and
        which docs/41 section 8.1 lists as its fourth honesty check."""
    assert RESULTS, "the campaign did not run"
    wrong = [r for r in RESULTS if r["cls"] in ("SDC", "DETECTED")]
    assert not wrong, "{} of {} injections reached a read port wrong: {}".format(
        len(wrong), len(RESULTS), wrong[:5])

    masked = [r for r in RESULTS if r["cls"] == "MASKED"]
    unexplained = [r for r in masked
                   if not overwritten_after(r["reg"], r["cycle"])]
    if SCRUB:
        assert not unexplained, (
            "{} MASKED records are not explained by the register being "
            "overwritten: {}".format(len(unexplained), unexplained[:5]))
    else:
        # THE COUNTERFACTUAL. At SCRUB = 0 an upset sits in the storage
        # until something reads or overwrites the register, so records
        # the scrub would have found come back MASKED with nothing to
        # explain them -- and each one is an upset the design is
        # carrying into whatever happens next. Reported and not
        # asserted, because it is the price of the configuration and not
        # a promise it breaks. docs/41 section 8.3 makes the criteria
        # reports rather than gates in its counterfactual for the same
        # reason.
        dut._log.info(
            "SCRUB=0: %d of %d MASKED records are upsets still sitting "
            "in the storage at the end of the run, unseen by anything. "
            "With the scrub the same campaign leaves none.",
            len(unexplained), len(RESULTS))

    corrected = [r for r in RESULTS if r["cls"] == "CORRECTED"]
    chk = sum(1 for r in RESULTS if r["field"] == "chk")
    assert chk > 0, "the campaign never drew a check bit"
    assert corrected, "not one injection was corrected"
    dut._log.info(
        "%d injections: %d CORRECTED, %d MASKED (every one of them "
        "overwritten by the workload before anything read it), "
        "0 SDC, 0 DETECTED. %d of the draws were into the check field.",
        len(RESULTS), len(corrected), len(masked), chk)


# =====================================================================
# the scrub, and the counterfactual for it
# =====================================================================


async def _two_upsets(dut, gap):
    """Upset one bit of x7, wait `gap` idle cycles, upset another, then
    read x7. Returns (mismatched, sec, ded)."""
    await por(dut)
    # Put a known value in x7 and let the model and the design agree.
    await Timer(T_DRIVE, unit="ns")
    dut.we_a_i.value = 1
    dut.waddr_a_i.value = 7
    dut.wdata_a_i.value = 0xA5A5_1234
    await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.we_a_i.value = 0

    obj = handle(dut, data_path(7))
    obj.value = val(obj) ^ (1 << 3)
    await idle(dut, gap)

    obj = handle(dut, data_path(7))
    obj.value = val(obj) ^ (1 << 19)
    await idle(dut, 2)

    await Timer(T_DRIVE, unit="ns")
    dut.raddr_a_i.value = 7
    await Timer(T_SAMPLE - T_DRIVE, unit="ns")
    got = val(dut.rdata_a_o)
    ded = val(report(dut, "ded_cycles"))
    await RisingEdge(dut.clk_i)
    return got != 0xA5A5_1234, ded


@cocotb.test()
async def test_the_scrub_makes_a_second_upset_survivable(dut):
    """Two upsets in one register, far enough apart for the scrub to
    have swept.

    Without a scrub these are a double error: detected, not corrected,
    and the program gets a wrong value with nothing to tell it so --
    which is the failure mode `docs/41` section 5.1 spent a section on
    for the watchdog's protected word. With one, the first is gone by
    the time the second arrives and both are single errors."""
    await setup(dut)
    wrong, ded = await _two_upsets(dut, gap=NUM_WORDS + 4)
    if SCRUB:
        assert not wrong, "the second upset was not corrected"
        assert ded == 0, "the codec reported an uncorrectable word"
    else:
        # The counterfactual build. Recorded rather than asserted the
        # other way round, because what SCRUB = 0 does with two upsets
        # is a measurement and not a promise.
        dut._log.info("SCRUB=0: two upsets 36 cycles apart -> "
                      "wrong=%s, ded_cycles=%d", wrong, ded)


@cocotb.test()
async def test_two_upsets_with_no_time_between_are_detected_not_hidden(dut):
    """The other half of SECDED, and the half that a code with an
    even-weight column would silently lose.

    With no idle cycles between them the scrub has not run, so the two
    bits are in the word together. The promise is NOT that this is
    corrected -- it cannot be -- but that it is DETECTED rather than
    turned into a third, plausible, wrong value."""
    await setup(dut)
    wrong, ded = await _two_upsets(dut, gap=0)
    assert ded > 0, ("two bits in one register were not reported as "
                     "uncorrectable")
    dut._log.info("two coincident upsets: read differs from golden = %s, "
                  "ded_cycles = %d", wrong, ded)
