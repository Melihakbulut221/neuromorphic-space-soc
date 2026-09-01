"""W7 and W8: the cadence contract and the kick budget.

WHERE THESE EXPECTATIONS COME FROM

They are the two requirements W7 and W8 stated in the header of
`hw/soc/rtl/soc_wdog.v` and argued in `docs/43-core-hardening.md`
sections 4 and 5.

**And a claim `test_soc_wdog.py` can make that this file cannot.** W1-W5
were written down before the RTL that implements them; W7 and W8 were
not -- the requirement and the implementation were written in the same
change, which is a weaker position and saying otherwise would be a
pretence. What is done instead is to keep the expectations at one
remove from the implementation in every case where that is possible:

  * every number below is computed from the requirement's own
    arithmetic -- "the window is open for the last 2^-WINS of the
    period" -- and from the block's parameters, and none is copied out
    of an expression in the design;
  * `test_the_window_boundary_is_where_the_requirement_says` does not
    assert a formula at all. It SWEEPS the tick at which the kick lands,
    finds the first one the block accepts, and compares that with the
    arithmetic. A shift the wrong way round, off by one, or taken
    against the counter instead of the reload would all still be a
    watchdog, and all three would fail here;
  * and the properties in `hw/soc/formal/soc_wdog_props.v` state the
    same requirements over the ports, where a k-induction proof rather
    than a stimulus decides them.

`test_soc_wdog.py`'s 14 tests continue to run unchanged against the same
file and are the regression that says W1-W5 did not move.

This file adds only what is new.

THE ONE MEASUREMENT RATHER THAN CHECK IN HERE is
`test_an_upset_in_the_unprotected_kick_budget_is_bounded`. `kick_left`
is deliberately outside W6's protected word, by the criterion `counter`
is outside it, and the price of that decision is measured here rather
than argued. `hw/soc/tb/cocotb/test_soc_wdog_fi.py` injects into it too,
but with a workload that never arms the budget -- so those injections
say only that a disarmed counter is inert, which is the weaker
statement. This one arms it first.

WHAT THIS SUITE DOES NOT COVER

  * The whole SoC. Whether a real program can live inside a window is a
    property of that program, and it is measured on the real fabric by
    `hw/soc/flow/fi_core.sh` and reported in docs/43 section 4.
  * Parameters other than the small ones the Makefile builds.
  * Any upset except the two deliberate deposits at the end. The
    protected word's own campaign is `test_soc_wdog_fi.py`.
  * WINDOW = 0. That configuration is proved rather than simulated:
    `hw/soc/formal/soc_wdog.sby` task `prove_w0`.
"""

import cocotb
from cocotb.triggers import RisingEdge, Timer

from test_soc_wdog import (
    B_LD, KEY, PRESCALE, RST_CYCLES, SEL_CTRL, SEL_RLD, SEL_STAT,
    T_DRIVE, T_SAMPLE, WIDTH, keyed, por, run_until, setup, val,
)

# The fifth watchdog register, at the watchdog's own +0xC.
SEL_WIN = 16

# WDOGWIN fields, soc_wdog.v W7 and W8.
WIN_WINS_MASK = 0xF
WIN_BUDEN = 1 << 7
WIN_BUDARM = 1 << 4


def win_word(wins=0, kicks=0, buden=False):
    return ((wins & WIN_WINS_MASK) |
            (WIN_BUDEN if buden else 0) |
            ((kicks & 0xFF) << 8))


# WDOGSTAT, the two new records.
ST_EARLY = 1 << 5
ST_BUDGET = 1 << 6


def timeout_of(reload_val):
    """The requirement's arithmetic, W2: (reload + 1) * PRESCALE."""
    return (reload_val + 1) * PRESCALE


def window_opens_at(reload_val, wins):
    """W7's own definition: the window is open while the counter is at
    or below reload >> WINS, so the earliest a kick may arrive is
    (reload - (reload >> WINS)) ticks after the reload."""
    return reload_val - (reload_val >> wins) if wins else 0


# A reload small enough that a whole period is a few hundred clocks and
# large enough that reload >> 2 is not degenerate.
RLD = 63


async def arm(w, wins=0, kicks=0, buden=False, reload_val=RLD):
    """Install the timeout, KICK, and only then declare the contract.

    THE ORDER IS THE POINT AND IT IS A PROPERTY OF W7, not a quirk of
    this helper. The window is a fraction of the period MEASURED FROM
    THE LAST RELOAD, and out of power-on reset the counter is running
    down from its maximum -- so a contract armed before a kick is a
    contract whose first period began before the timeout it is stated
    against existed. The first version of this file armed first and
    kicked second, and the arming kick was itself early: stage 1 on the
    spot, stage 2 on the next kick, and every test in the file failed
    for one reason that had nothing to do with what any of them was
    checking.

    hw/soc/tb/sw/fi_workload.c does it in this order for the same
    reason, and docs/43 section 4 records it as the first obligation a
    program that uses W7 takes on."""
    await w.write(SEL_RLD, reload_val)
    await w.kick()
    await w.write(SEL_WIN, win_word(wins, kicks, buden))


async def ticks(dut, n):
    """n prescaler ticks, which is n * PRESCALE clocks."""
    for _ in range(n * PRESCALE):
        await RisingEdge(dut.clk_i)
    await Timer(T_SAMPLE, unit="ns")


# ---------------------------------------------------------------------------
# W7a: the contract is readable, so a driver can discover it did not take
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_the_contract_reads_back(dut):
    w = await setup(dut)
    assert val(dut.nmi_o) == 0

    # The reset default is the whole period and no budget. This is the
    # state docs/42 measured, and W7b proves nothing can fire in it.
    r = await w.read(SEL_WIN)
    assert (r & WIN_WINS_MASK) == 0, "WINS is not 0 out of power-on reset"
    assert (r & WIN_BUDARM) == 0, "the kick budget is armed out of reset"

    await w.write(SEL_WIN, win_word(wins=3, kicks=7, buden=True))
    r = await w.read(SEL_WIN)
    assert (r & WIN_WINS_MASK) == 3
    assert (r & WIN_BUDARM) != 0
    assert ((r >> 8) & 0xFF) == 7, "the budget did not load"


@cocotb.test()
async def test_an_unkeyed_write_cannot_set_the_contract(dut):
    """W5 covers every register and this is a new one.

    An unkeyed write to WDOGWIN is the way a runaway would install a
    contract nobody asked for -- a one-kick budget, say -- and reset the
    part deliberately."""
    w = await setup(dut)
    await w.write_raw(SEL_WIN, ((KEY ^ 1) << 16) | win_word(wins=3, kicks=1,
                                                            buden=True))
    r = await w.read(SEL_WIN)
    assert (r & WIN_WINS_MASK) == 0
    assert (r & WIN_BUDARM) == 0


# ---------------------------------------------------------------------------
# W7: the window itself
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_with_the_window_open_a_kick_at_any_time_is_accepted(dut):
    """WINS = 0 is the docs/40 watchdog, and this is the regression.

    A kick one tick after the reload -- as early as a kick can be -- is
    accepted, reloads the counter and prevents stage 1."""
    w = await setup(dut)
    await arm(w, wins=0)
    await ticks(dut, 1)
    await w.kick()
    # A full timeout from HERE, minus a margin, with no stage 1.
    n = await run_until(dut, "nmi_o", timeout_of(RLD) - 2 * PRESCALE)
    assert n is None, "stage 1 arrived {} clocks after an accepted kick".format(n)
    assert (await w.read(SEL_STAT)) & ST_EARLY == 0


@cocotb.test()
async def test_a_kick_before_the_window_opens_is_rejected_and_escalates(dut):
    w = await setup(dut)
    await arm(w, wins=1)
    # One tick after the reload the counter is at RLD - 1, far above
    # RLD >> 1, so the window is shut.
    await ticks(dut, 1)
    await w.kick()
    await Timer(T_SAMPLE, unit="ns")
    assert val(dut.nmi_o) == 1, "an early kick did not raise stage 1"
    st = await w.read(SEL_STAT)
    assert st & ST_EARLY, "WDOGSTAT.EARLY was not set"
    assert st & ST_BUDGET == 0, "W8 fired on a W7 violation"


@cocotb.test()
async def test_a_kick_inside_the_window_is_accepted(dut):
    w = await setup(dut)
    await arm(w, wins=1)
    # Past the open point by two ticks.
    await ticks(dut, window_opens_at(RLD, 1) + 2)
    await w.kick()
    await Timer(T_SAMPLE, unit="ns")
    assert val(dut.nmi_o) == 0, "a kick inside the window escalated"
    assert (await w.read(SEL_STAT)) & ST_EARLY == 0


@cocotb.test()
async def test_the_window_boundary_is_where_the_requirement_says(dut):
    """Sweep the tick at which the kick lands and find the first one the
    block accepts, then compare it with W7's own arithmetic.

    This is the test that would fail if the shift were the wrong way
    round, off by one, or against the counter instead of the reload --
    none of which any other check in this repository would notice,
    because all of them would still be a watchdog."""
    # setup() first, then por() inside the loop. A cocotb test's
    # `start_soon` coroutines are killed when the test ends, so a test
    # that relies on a clock an earlier test started runs with no clock
    # at all -- which is a hang and not a failure, and it takes the rest
    # of the file down with it. test_soc_wdog.py's por() docstring
    # records the other half of the same hazard.
    await setup(dut)
    for wins in (1, 2, 3):
        first_accepted = None
        for t in range(1, RLD):
            w = await por(dut)
            await arm(w, wins=wins)
            await ticks(dut, t)
            await w.kick()
            await Timer(T_SAMPLE, unit="ns")
            early = (await w.read(SEL_STAT)) & ST_EARLY
            if not early:
                first_accepted = t
                break
        want = window_opens_at(RLD, wins)
        assert first_accepted is not None, \
            "WINS={} accepted no kick at all".format(wins)
        # One tick of slack: the kick is a bus access that takes a cycle
        # to land, so the counter may have moved on by one tick between
        # the deposit of the request and the block's decision.
        assert abs(first_accepted - want) <= 1, (
            "WINS={}: the window opened at tick {}, the requirement says {}"
            .format(wins, first_accepted, want))


@cocotb.test()
async def test_an_early_kick_does_not_postpone_the_deadline(dut):
    """A kick the block rejected must not reload the counter.

    If it did, a runaway kicking too fast would be told off once a
    period and reloaded anyway, and W7 would be a complaint counter
    rather than a backstop -- which is the entire point of it."""
    w = await setup(dut)
    await arm(w, wins=1)
    await ticks(dut, 1)
    before = await w.read(1)          # SEL_CNT
    await w.kick()
    after = await w.read(1)
    assert after < before, \
        "an early kick reloaded the counter: {} -> {}".format(before, after)


# ---------------------------------------------------------------------------
# W8: the kick budget
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_a_phase_may_spend_exactly_the_kicks_it_declared(dut):
    w = await setup(dut)
    budget = 3
    await arm(w, wins=0, kicks=budget, buden=True)
    for n in range(budget):
        await ticks(dut, 2)
        await w.kick()
        await Timer(T_SAMPLE, unit="ns")
        assert val(dut.nmi_o) == 0, \
            "kick {} of a budget of {} escalated".format(n + 1, budget)
        left = ((await w.read(SEL_WIN)) >> 8) & 0xFF
        assert left == budget - n - 1, \
            "after {} kicks the budget reads {}".format(n + 1, left)

    await ticks(dut, 2)
    await w.kick()
    await Timer(T_SAMPLE, unit="ns")
    assert val(dut.nmi_o) == 1, "the kick past the budget did not escalate"
    st = await w.read(SEL_STAT)
    assert st & ST_BUDGET, "WDOGSTAT.BUDGET was not set"
    assert st & ST_EARLY == 0, "W7 fired on a W8 violation"


@cocotb.test()
async def test_a_disarmed_budget_never_bites(dut):
    """The budget is opt-in. A program that never writes WDOGWIN gets
    docs/42's block, and this is that stated as a test rather than left
    to the reset value."""
    w = await setup(dut)
    await w.write(SEL_RLD, RLD)
    await w.kick()
    for _ in range(20):
        await ticks(dut, 2)
        await w.kick()
    await Timer(T_SAMPLE, unit="ns")
    assert val(dut.nmi_o) == 0
    assert (await w.read(SEL_STAT)) & (ST_EARLY | ST_BUDGET) == 0


@cocotb.test()
async def test_the_records_are_sticky(dut):
    """Both violation records follow WDOGRST's rule: a record software
    can erase is a record an upset can erase."""
    w = await setup(dut)
    await arm(w, wins=1)
    await ticks(dut, 1)
    await w.kick()                      # early
    await w.ack()
    st = await w.read(SEL_STAT)
    assert st & ST_EARLY
    # Try to clear it, every way the register offers.
    await w.write(SEL_STAT, 0xFFFF)
    assert (await w.read(SEL_STAT)) & ST_EARLY, "EARLY was cleared"


# ---------------------------------------------------------------------------
# The docs/40 section 7.2 inheritance
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_a_stage_2_reset_restores_the_whole_period_and_no_budget(dut):
    """docs/40 section 7.2 found that a short reload installed before
    software went wrong survived the reset that going wrong caused, and
    bricked the SoC in an unbreakable reset loop. W7 and W8 can
    reproduce that exactly -- a window too tight, or a budget too small,
    would trip on the first kick of every fresh boot -- so a stage-2
    reset restores WINS to 0 and disarms the budget beside restoring the
    reload to the maximum. This is that line, tested."""
    w = await setup(dut)
    await arm(w, wins=3, kicks=1, buden=True)

    # Two violations with no acknowledge in between: stage 1, then stage 2.
    await ticks(dut, 1)
    await w.kick()
    await Timer(T_SAMPLE, unit="ns")
    assert val(dut.nmi_o) == 1
    await ticks(dut, 1)
    await w.kick()
    await Timer(T_SAMPLE, unit="ns")
    assert val(dut.rst_req_o) == 1, "the second violation did not reach stage 2"

    for _ in range(RST_CYCLES + 4):
        await RisingEdge(dut.clk_i)
    await Timer(T_SAMPLE, unit="ns")

    r = await w.read(SEL_WIN)
    assert (r & WIN_WINS_MASK) == 0, "WINS survived the reset it caused"
    assert (r & WIN_BUDARM) == 0, "the budget survived the reset it caused"
    assert (await w.read(SEL_RLD)) == (1 << WIDTH) - 1

    # And the records of what happened did NOT go with it.
    st = await w.read(SEL_STAT)
    assert st & ST_EARLY, "the restore erased the record of the violation"
    assert st & 2, "WDOGRST was lost"


# ---------------------------------------------------------------------------
# The price of leaving the budget counter unprotected, MEASURED
# ---------------------------------------------------------------------------


async def _deposit(dut, path, bit):
    obj = dut
    for part in path.split("."):
        obj = getattr(obj, part)
    await Timer(T_DRIVE, unit="ns")
    obj.value = val(obj) ^ (1 << bit)


@cocotb.test()
async def test_arming_the_contract_before_a_kick_trips_it_immediately(dut):
    """The hazard the `arm` helper documents, stated as a test so that a
    later reordering of it is a red test rather than a silent one.

    Out of power-on reset the counter is running down from its maximum
    against a reload that software has just shortened, so it is far
    above the open point. A contract declared at that moment is a
    contract whose very next kick is early -- and the block is right to
    say so. This is the ordering obligation W7 places on software, and
    it is the reason fi_workload.c kicks before it arms."""
    w = await setup(dut)
    await w.write(SEL_RLD, RLD)
    await w.write(SEL_WIN, win_word(wins=1))     # armed WITHOUT a kick
    await w.kick()
    await Timer(T_SAMPLE, unit="ns")
    assert val(dut.nmi_o) == 1, \
        "a kick issued a whole reload's worth of ticks early was accepted"
    assert (await w.read(SEL_STAT)) & ST_EARLY


@cocotb.test()
async def test_an_upset_in_the_unprotected_kick_budget_is_bounded(dut):
    """`kick_left` is outside W6's protected word, by the criterion
    `counter` is outside it. What that costs is measured here.

    The claim W8 makes is NOT that an upset in this counter is
    invisible. It is that it is bounded in both directions: upward it
    buys a runaway at most 2^KICK_W - 1 further kicks before the budget
    bites anyway, and downward it produces a spurious escalation, which
    is loud and which the protected record captures correctly. Both
    halves are exercised."""
    await setup(dut)
    upward = downward = 0

    for bit in range(8):
        w = await por(dut)
        await arm(w, wins=0, kicks=8, buden=True)
        await ticks(dut, 1)
        await _deposit(dut, "kick_left", bit)
        left_after = ((await w.read(SEL_WIN)) >> 8) & 0xFF

        # Spend kicks until the budget bites or an obvious bound passes.
        fired_at = None
        for n in range(1, 300):
            await ticks(dut, 2)
            await w.kick()
            await Timer(T_SAMPLE, unit="ns")
            if val(dut.nmi_o):
                fired_at = n
                break
        assert fired_at is not None, \
            "bit {} left the budget never biting at all".format(bit)
        assert (await w.read(SEL_STAT)) & ST_BUDGET, \
            "bit {} escalated for a reason that was not the budget".format(bit)
        # The bound: the budget still bites, at the value it now holds.
        assert fired_at == left_after + 1, (
            "bit {}: budget read {} and it bit after {} kicks"
            .format(bit, left_after, fired_at))
        if left_after > 8:
            upward += 1
        elif left_after < 8:
            downward += 1

    dut._log.info(
        "kick_left: 8 single-bit upsets, %d raised the budget and %d "
        "lowered it; every one still escalated, at exactly the value the "
        "corrupted counter held. Worst extension: %d kicks.",
        upward, downward, 255 - 8)
