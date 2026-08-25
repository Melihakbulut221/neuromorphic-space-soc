"""TMR voter RTL vs an independent Python majority model.

hw/rtl/tmr_voter.v computes the majority as a sum of AND terms; the
reference below counts votes per bit. The two formulations are different
by construction, so agreement is evidence rather than a restatement of the
implementation (the same discipline the formal property set uses,
formal/tmr_voter_props.v).

The voter is purely combinational: no clock, no reset, one settle delay
per vector. Width comes from the elaborated parameter, so the same tests
run at every width hw/tb/Makefile.tmr elaborates (1, 8, 32); at WIDTH = 1
the input space is only eight combinations and is swept exhaustively.

Two tests exist only at some widths: the exhaustive sweep is a WIDTH = 1
test, and a pairwise three-way split needs WIDTH >= 2. cocotb fixes `skip`
when the module is imported, before there is a design handle to read WIDTH
from, so the gate reads the elaboration selector TMR_WIDTH out of the
environment - hw/tb/Makefile.tmr exports it, the same way
hw/tb/Makefile.secded exports SECDED_DUT. `width_of()` then asserts that
the elaborated parameter really is that width, so a stale or missing
TMR_WIDTH fails the run loudly instead of silently skipping (or silently
not skipping) the wrong tests.
"""

import os
import random

import cocotb
from cocotb.triggers import Timer

SETTLE_NS = 1

# Elaboration selector, mirroring `TMR_WIDTH ?= 8` in hw/tb/Makefile.tmr.
REQUESTED_WIDTH = int(os.environ.get("TMR_WIDTH", "8"))

# Skip flags: the tests that do not exist at this elaborated width. A
# skipped test is reported as skipped, not as a pass with nothing in it.
SKIP_UNLESS_WIDTH_1 = REQUESTED_WIDTH != 1
SKIP_UNLESS_WIDTH_GE_2 = REQUESTED_WIDTH < 2


def majority(a, b, c, width):
    """Reference: bit k of the result is 1 when at least two of the three
    replica bits are 1. Counted, not expressed as AND/OR terms."""
    out = 0
    for k in range(width):
        votes = ((a >> k) & 1) + ((b >> k) & 1) + ((c >> k) & 1)
        if votes >= 2:
            out |= 1 << k
    return out


def expect_mismatch(a, b, c):
    return 0 if (a == b and b == c) else 1


def width_of(dut):
    """The elaborated WIDTH, cross-checked against the skip gate.

    Every test goes through here, so an elaboration that does not match
    TMR_WIDTH fails on the first vector instead of quietly running the
    wrong subset of the suite.
    """
    width = int(dut.WIDTH.value)
    assert width == REQUESTED_WIDTH, (
        f"elaborated WIDTH is {width} but TMR_WIDTH says {REQUESTED_WIDTH}; "
        "the width-gated tests would be skipped on the wrong criterion")
    return width


async def vote(dut, a, b, c):
    dut.in_a.value = a
    dut.in_b.value = b
    dut.in_c.value = c
    await Timer(SETTLE_NS, unit="ns")
    return int(dut.out.value), int(dut.mismatch.value)


async def check(dut, a, b, c, note=""):
    width = width_of(dut)
    out, mismatch = await vote(dut, a, b, c)
    ref = majority(a, b, c, width)
    assert out == ref, (
        f"{note}out 0x{out:X}, model 0x{ref:X} for "
        f"a=0x{a:X} b=0x{b:X} c=0x{c:X}")
    assert mismatch == expect_mismatch(a, b, c), (
        f"{note}mismatch {mismatch} for a=0x{a:X} b=0x{b:X} c=0x{c:X}")
    return out, mismatch


@cocotb.test()
async def test_unanimous_inputs_pass_through(dut):
    """Three healthy replicas: the voted word is the replica word and no
    disagreement is reported."""
    width = width_of(dut)
    rng = random.Random(0x77733001)
    mask = (1 << width) - 1
    words = [0, mask, 0xAAAAAAAA & mask, 0x55555555 & mask]
    words += [rng.getrandbits(width) for _ in range(50)]
    for word in words:
        out, mismatch = await check(dut, word, word, word)
        assert out == word
        assert mismatch == 0, "unanimous replicas must not raise the flag"


@cocotb.test()
async def test_single_bit_upset_in_any_replica_is_masked(dut):
    """Exhaustive over (replica, bit position): one flipped bit in one
    replica never reaches the output, and always raises the flag."""
    width = width_of(dut)
    rng = random.Random(0x77733002)
    mask = (1 << width) - 1
    bases = [0, mask, rng.getrandbits(width), rng.getrandbits(width)]
    for base in bases:
        for bit in range(width):
            corrupt = base ^ (1 << bit)
            for replica in range(3):
                trio = [base, base, base]
                trio[replica] = corrupt
                out, mismatch = await check(
                    dut, trio[0], trio[1], trio[2],
                    f"replica {replica} bit {bit}: ")
                assert out == base, "a single upset changed the voted word"
                assert mismatch == 1, "a masked upset must still be counted"


@cocotb.test()
async def test_arbitrarily_corrupted_replica_is_masked(dut):
    """The masking theorem with no assumption on the fault: one replica is
    replaced by a random word, however many bits it gets wrong."""
    width = width_of(dut)
    rng = random.Random(0x77733003)
    for _ in range(300):
        base = rng.getrandbits(width)
        corrupt = rng.getrandbits(width)
        for replica in range(3):
            trio = [base, base, base]
            trio[replica] = corrupt
            out, mismatch = await check(dut, trio[0], trio[1], trio[2])
            assert out == base, "two healthy replicas must outvote the third"
            assert mismatch == (0 if corrupt == base else 1)


@cocotb.test()
async def test_random_triples_match_the_model(dut):
    """Unconstrained inputs, including cases where all three differ."""
    width = width_of(dut)
    rng = random.Random(0x77733004)
    for _ in range(2000):
        await check(dut, rng.getrandbits(width), rng.getrandbits(width),
                    rng.getrandbits(width))


@cocotb.test()
async def test_output_is_always_a_replica_value_per_bit(dut):
    """The voter can never invent a bit value no replica supplied."""
    width = width_of(dut)
    rng = random.Random(0x77733005)
    for _ in range(500):
        a = rng.getrandbits(width)
        b = rng.getrandbits(width)
        c = rng.getrandbits(width)
        out, _ = await vote(dut, a, b, c)
        assert ((out ^ a) & (out ^ b) & (out ^ c)) == 0


@cocotb.test(skip=SKIP_UNLESS_WIDTH_GE_2)
async def test_three_way_disagreement_is_flagged(dut):
    """Three pairwise-distinct replicas: skipped at WIDTH = 1, where three
    pairwise-distinct one-bit words do not exist."""
    width = width_of(dut)
    assert width >= 2
    rng = random.Random(0x77733006)
    checked = 0
    while checked < 200:
        a = rng.getrandbits(width)
        b = rng.getrandbits(width)
        c = rng.getrandbits(width)
        if a == b or b == c or a == c:
            continue
        _, mismatch = await check(dut, a, b, c)
        assert mismatch == 1
        checked += 1


@cocotb.test(skip=SKIP_UNLESS_WIDTH_1)
async def test_exhaustive_at_width_one(dut):
    """At WIDTH = 1 the whole input space is eight combinations. Skipped at
    every other width, where the table does not apply."""
    width = width_of(dut)
    assert width == 1
    table = {
        (0, 0, 0): (0, 0),
        (0, 0, 1): (0, 1),
        (0, 1, 0): (0, 1),
        (0, 1, 1): (1, 1),
        (1, 0, 0): (0, 1),
        (1, 0, 1): (1, 1),
        (1, 1, 0): (1, 1),
        (1, 1, 1): (1, 0),
    }
    for (a, b, c), expected in table.items():
        out, mismatch = await check(dut, a, b, c)
        assert (out, mismatch) == expected, (
            f"a={a} b={b} c={c}: got ({out}, {mismatch}), "
            f"expected {expected}")
