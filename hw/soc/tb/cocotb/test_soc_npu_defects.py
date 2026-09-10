# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""cocotb suite for the three hw/soc/rtl/soc_npu.v defects a hostile
design review found on 2026-09-10, and for the fixes.

WHY THIS IS A SECOND FILE AND NOT MORE TESTS IN test_soc_npu.py
---------------------------------------------------------------
Every test here is written to FAIL ON THE RTL AS IT WAS and pass on the
RTL as it is, and a test with that job has to be runnable against both.
Keeping them together means the red run and the green run are the same
MODULE against two different `SOC_NPU_SRC` values, and nothing else
moves between them.

  green, the tree as committed:

    cd hw/soc/tb/cocotb && make -f Makefile.soc_npu \\
        MODULE=test_soc_npu_defects \\
        SIM_BUILD=sim_build_npu_defects \\
        COCOTB_RESULTS_FILE=results_soc_npu_defects.xml

  red, against a copy of the file from before the fixes -- which is what
  `git show HEAD:hw/soc/rtl/soc_npu.v > /tmp/pre/soc_npu.v` produces:

    cd hw/soc/tb/cocotb && make -f Makefile.soc_npu \\
        MODULE=test_soc_npu_defects SOC_NPU_SRC=/tmp/pre/soc_npu.v \\
        SIM_BUILD=sim_build_npu_defects_pre \\
        COCOTB_RESULTS_FILE=results_soc_npu_defects_pre.xml

`SOC_NPU_SRC` is already in Makefile.soc_npu for exactly this; the
mutation runs in sw/tests/test_soc_synthesis_guards.py use the same
handle. Neither the Makefile nor test_soc_npu.py is modified by this
file -- the shared harness is IMPORTED from test_soc_npu.py, so the bus
driver, the APB driver and the cycle convention here are the same
objects that suite uses and cannot drift from them.

WHAT EACH TEST FAILS ON, STATED SO A GREEN RUN IS NOT MISTAKEN FOR
COVERAGE
------------------------------------------------------------------
  1. test_the_engine_escapes_a_full_die_when_the_drain_is_turned_on
     the E_DECIDE deadlock. Fails by TIMEOUT of a bounded poll on the
     pre-fix RTL: the engine never leaves E_DECIDE, so no event is ever
     captured and no injected event is ever delivered.
  2. test_the_detour_delivers_the_event_it_left_and_does_not_drop_it
     the review's shorter suggestion -- divert to E_DRN_RQ and let the
     drain end at E_IDLE -- passes test 1 and fails this one, because
     the word already popped into `ev_word` is never delivered. It is
     an event-count test and it is the reason the fix carries a bit.
  3. test_the_window_refuses_a_grant_while_it_still_owes_a_response
     the grant qualification. Deposits docs/52's sixth dead machine and
     asks the two questions rule 3 asks: was a grant issued while a
     response was owed, and did exactly one response come back.
  4. test_a_wait_counter_pushed_past_its_bound_expires_now
     the three `==`. Deposits `ev_wait` ABOVE each bound and measures
     how long the state takes to give up. With `==` it takes the long
     way round the whole four-bit range.

WHAT IS NOT COVERED HERE
------------------------
  - No metastability, no gate delays, no timing. This is RTL.
  - Tests 3 and 4 DEPOSIT into flip-flops rather than reaching their
    states through stimulus, because both are unreachable without an
    upset -- which is stated in soc_npu.v for one and is the whole
    content of docs/52 for the other. Test 1 injects nothing at all:
    that deadlock is reachable on a healthy part with the documented
    event stream, which is why it is the serious one.
  - Nothing here says the E_DECIDE hold is now BOUNDED. It is not.
    soc_npu.v names the three cases the escape does not cover and this
    file does not pretend to close them.
"""

import sys
from pathlib import Path

import cocotb
from cocotb.triggers import RisingEdge, Timer

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_soc_npu import (                                    # noqa: E402
    Env, N_AXONS, N_NEURONS, bring_up, node,
    C_CTRL, C_EVQ_IN, C_EVQ_OUT, C_STATUS, C_CNT, C_CNT_DROP, C_IRQCAUSE,
    CTRL_IN_EN, CTRL_OUT_EN,
    TYPE_SPIKE, TYPE_TICK, EVQ_VALID,
    ST_IN_RDY, ST_OUT_VLD, ST_CAP_FULL,
    CAUSE_INJ_OVF, CAUSE_FETCH_ER, CAUSE_WIN_TO,
    T_DRIVE, T_SAMPLE,
)
from golden.regmap_gen import ADDR                            # noqa: E402

# The event engine's own encoding, hw/soc/rtl/soc_npu.v. Written here
# because it is not exported anywhere; a rename in the RTL fails the
# assertion messages rather than silently passing, because the states
# are also checked against behaviour and not only against the number.
E_IDLE, E_FETCH, E_DECIDE = 0, 1, 2
E_PIN_G = 5

W_IDLE = 0


def strong_weights(n_axons, n_neurons):
    """Every axon drives every neuron at the largest positive weight the
    4-bit field holds, so one spike per axon and one tick fires the whole
    layer and the die has N_NEURONS events to give back. The random
    weights test_soc_npu.py uses are for comparing against the golden
    model; what is needed here is a full EVQ_OUT."""
    return [[7 for _ in range(n_neurons)] for _ in range(n_axons)]


async def stall_the_die(env, dut):
    """Drive the interlock the engine cannot get out of, with no upset.

    docs/10 section 7.2: a full EVQ_OUT stalls the die's update pipeline
    -- spikes are never dropped, the pipeline waits. A stalled pipeline
    stops consuming EVQ_IN. A full EVQ_IN drops AER_IN_RDY. And a low
    AER_IN_RDY is what E_DECIDE holds on.

    So: bring the node up, turn the DRAIN OFF and the injection ON, and
    push one full frame in. Nothing here is a fault: CTRL.OUT_EN reset
    value is 0 and a host that has not started reading yet is the
    ordinary case at the start of a run.

    Returns the number of event words written to EVQ_IN.
    """
    await bring_up(env, strong_weights(N_AXONS, N_NEURONS))
    await env.cwr(C_CTRL, CTRL_IN_EN)

    written = 0
    for a in range(N_AXONS):
        await env.cwr(C_EVQ_IN, TYPE_SPIKE | a)
        written += 1
    await env.cwr(C_EVQ_IN, TYPE_TICK)
    written += 1

    for _ in range(600):
        await RisingEdge(dut.clk_i)

    st = await env.crd(C_STATUS)
    assert st & ST_IN_RDY == 0, (
        f"STATUS reads 0x{st:03x}: the die's input queue is not full, so "
        "this test never reached the state it is about")
    assert st & ST_OUT_VLD, (
        f"STATUS reads 0x{st:03x}: the die has nothing to drain, so the "
        "escape being tested would have nothing to escape to")
    assert st & ST_CAP_FULL == 0, (
        "the capture queue is full, so `drain_want` would be low for a "
        "reason this test is not about")
    assert int(dut.ev_state.value) == E_DECIDE, (
        f"the engine is in state {int(dut.ev_state.value)} and not "
        f"E_DECIDE ({E_DECIDE}); the deadlock under test is E_DECIDE's")

    # Not a fault report anywhere: nothing was dropped and nothing timed
    # out. The stall is the design working as docs/10 says it does.
    assert await env.crd(C_CNT_DROP) == 0
    assert await env.crd(C_IRQCAUSE) & (CAUSE_INJ_OVF | CAUSE_FETCH_ER) == 0
    return written


# ---------------------------------------------------------------------------
# 1. E_DECIDE had no escape, and the escape is the drain
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_the_engine_escapes_a_full_die_when_the_drain_is_turned_on(dut):
    """The state the engine cannot drain from is the state a full die
    puts it in, and that is a deadlock rather than a stall.

    The chain is soc_npu.v's own, one paragraph above the state machine:
    DRAIN OUTRANKS INJECT because a full EVQ_OUT stalls the die and
    injecting into a stalled core achieves nothing while draining
    unblocks it. The engine acted on that rule in E_IDLE and nowhere
    else -- and E_DECIDE, the one state a stalled die can hold it in,
    could not reach E_DRN_RQ.

    THE RECOVERY UNDER TEST IS THE OPERATOR'S, not a reset. Software
    that notices the part has gone quiet sets CTRL.OUT_EN and starts
    reading EVQ_OUT. On the pre-fix RTL that changes nothing at all,
    because `drain_want` is not looked at again once the engine is in
    E_DECIDE, and the only thing that ends it is CTRL.FLUSH -- which
    throws the queues away, and with them whatever the die had computed.
    """
    env = Env(dut)
    await env.reset()
    await stall_the_die(env, dut)

    # Hold still for a while first, so that the failure below cannot be
    # blamed on not having waited long enough before the recovery.
    for _ in range(200):
        await RisingEdge(dut.clk_i)
    assert int(dut.ev_state.value) == E_DECIDE

    # The recovery: turn the drain on and read the capture queue, which
    # is what a host does.
    await env.cwr(C_CTRL, CTRL_IN_EN | CTRL_OUT_EN)

    drained = []
    left_decide = False
    for _ in range(2000):
        if int(dut.ev_state.value) != E_DECIDE:
            left_decide = True
        w = await env.crd(C_EVQ_OUT)
        if w & EVQ_VALID:
            drained.append(w & 0xFFFF)
            if len(drained) >= N_NEURONS:
                break

    assert left_decide, (
        "CTRL.OUT_EN was set with the die holding an event to give up "
        "and the capture queue empty, and the engine never left E_DECIDE. "
        "`drain_want` is true and unread: this is the deadlock, and "
        "nothing short of CTRL.FLUSH ends it.")
    assert len(drained) >= N_NEURONS, (
        f"{len(drained)} of {N_NEURONS} output events came back after the "
        "drain was turned on. The engine reached the drain but did not "
        "keep reaching it.")

    # And the part is still a part: the injected event that was waiting
    # in E_DECIDE goes over the pins once the die has room, and the
    # engine ends up idle rather than in some other stuck state.
    for _ in range(4000):
        await RisingEdge(dut.clk_i)
        if int(dut.ev_state.value) == E_IDLE:
            break
    else:
        raise AssertionError(
            f"the engine settled in state {int(dut.ev_state.value)} and "
            "not E_IDLE after the queues drained")
    st = await env.crd(C_STATUS)
    assert st & ST_IN_RDY, (
        f"STATUS reads 0x{st:03x}: the die never took the event back")


# ---------------------------------------------------------------------------
# 2. The detour must not be a restart
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_the_detour_delivers_the_event_it_left_and_does_not_drop_it(dut):
    """The review's suggestion was "re-evaluate drain_want in E_DECIDE and
    move to the drain-request state", and that form alone LOSES AN EVENT.

    E_DRN_RQ and E_DRN_W both end at E_IDLE, and E_IDLE pops the next
    word out of the injection queue. The event already in `ev_word` --
    popped, so the queue no longer holds it, and not yet delivered, so
    the die has never seen it -- would be dropped silently, counted by
    nothing on either side. docs/10 section 7.2 is that spikes are never
    dropped; a fix for a deadlock that drops one event per escape is a
    different defect at a lower rate.

    So the count is the test. CNT.IN is the engine's own tally of events
    it delivered, incremented in E_PIN_G for a pin event and in E_SER_W
    for a serial one, and it must equal the number of words written to
    EVQ_IN once everything has drained. Nothing in this test looks at
    `ev_resume`: what is asserted is the event, not the mechanism.
    """
    env = Env(dut)
    await env.reset()
    written = await stall_the_die(env, dut)

    await env.cwr(C_CTRL, CTRL_IN_EN | CTRL_OUT_EN)

    # Read the capture queue until both sides are quiet: the die has no
    # more to give and the engine has nothing left to inject.
    quiet = 0
    for _ in range(600):
        w = await env.crd(C_EVQ_OUT)
        if w & EVQ_VALID:
            quiet = 0
            continue
        st = await env.crd(C_STATUS)
        if st & ST_OUT_VLD or int(dut.ev_state.value) != E_IDLE:
            quiet = 0
            continue
        quiet += 1
        if quiet >= 4:
            break
    else:
        raise AssertionError("the part never went quiet")

    cnt = await env.crd(C_CNT)
    delivered = cnt & 0xFFFF
    assert await env.crd(C_CNT_DROP) == 0, (
        "the injection queue refused a write, so the arithmetic below "
        "would be measuring the wrong thing")
    assert delivered == written, (
        f"{written} event words were written to EVQ_IN and CNT.IN reports "
        f"{delivered} delivered. The difference is the word that was "
        "sitting in `ev_word` when the engine took the drain detour: a "
        "detour that returns to E_IDLE instead of to E_DECIDE throws it "
        "away, and nothing on either side of the transport counts it.")
    assert await env.crd(C_IRQCAUSE) & CAUSE_FETCH_ER == 0, (
        "an injected event was abandoned in E_FETCH during the recovery")


# ---------------------------------------------------------------------------
# 3. The grant, and the response the slave still owes
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_the_window_refuses_a_grant_while_it_still_owes_a_response(dut):
    """docs/52's sixth dead machine, and what the grant did with it.

    `win_state` bit 1 flipped takes W_WAIT (2) to W_IDLE (0): the window
    does not wait for ever, it FORGETS that it was waiting, with a
    granted request unanswered. soc_npu.v already says that and already
    bounds it -- `win_out` is the fabric's own record that a response is
    owed, and `win_guard` runs while it is set.

    What was missing is one level up. `gnt_o` was `req_i && (win_state ==
    W_IDLE)`, so in that same forgotten state the slave ADVERTISED
    ITSELF FREE. A master holding `req_i` up is then granted, W_IDLE
    captures the new payload, and `win_guard` -- which is cleared by
    `gnt_o` -- goes back to zero. The bound built for this exact record
    is re-armed by it, for ever, and the slave stays one rvalid short of
    soc_bus.v's response-ownership queue.

    Two questions, which are soc_bus.v rule 3 and nothing else:
    was a grant issued while a response was owed, and did exactly one
    response come back.
    """
    env = Env(dut)
    await env.reset()

    grants = 0
    rvalids = 0
    granted_owing = 0

    async def watch():
        nonlocal grants, rvalids, granted_owing
        while True:
            await RisingEdge(dut.clk_i)
            await Timer(T_SAMPLE, unit="ns")
            g = int(dut.gnt_o.value) and int(dut.req_i.value)
            r = int(dut.rvalid_o.value)
            if g:
                grants += 1
                if int(dut.win_out.value) and not r:
                    granted_owing += 1
            if r:
                rvalids += 1

    w = cocotb.start_soon(watch())

    # A normal access first, driven by hand rather than through env.bus,
    # because this test needs `req_i` to STAY UP after the grant -- which
    # is legal (soc_bus.v MAX_OUT is 2 and Ibex's prefetch buffer does
    # exactly this) and is the condition that makes the re-grant happen.
    await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.req_i.value = 1
    dut.addr_i.value = node(0, ADDR["ID"])
    dut.we_i.value = 0
    dut.be_i.value = 0xF

    for _ in range(50):
        await Timer(T_SAMPLE - T_DRIVE, unit="ns")
        if int(dut.gnt_o.value):
            break
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
    else:
        raise AssertionError("the idle window never granted the first request")

    # Into the frame, and then the upset: the window forgets it was
    # waiting. `win_out` is untouched, so the fabric is still owed one.
    for _ in range(30):
        await RisingEdge(dut.clk_i)
    assert int(dut.win_out.value) == 1, "nothing is outstanding to forget"
    await Timer(T_DRIVE, unit="ns")
    dut.win_state.value = W_IDLE
    await Timer(T_SAMPLE - T_DRIVE, unit="ns")

    # THE DIRECT QUESTION, asked in the cycle the deposit lands: the FSM
    # says idle and the handshake says one is owed. A slave that grants
    # here has taken a second transaction it cannot answer.
    assert int(dut.gnt_o.value) == 0, (
        "the window granted a request in the cycle it was holding "
        "win_state = W_IDLE with win_out set. It has just accepted a "
        "second transaction while owing the fabric a response for the "
        "first, and `win_guard` -- which the grant clears -- has been put "
        "back to zero, so the bound that exists for this record will "
        "never fire while the master keeps asking.")

    # And the whole episode: exactly one response per grant, and the
    # bound is what ends it. `req_i` is held up until the first response
    # comes back, because that is the master behaviour the defect needs;
    # the window may legitimately take a SECOND transaction in the cycle
    # it returns that response -- soc_npu.v says so and the `|| rvalid_o`
    # term is there for it -- so the episode is run to the end and the
    # two counts are compared once nothing is outstanding.
    bound = int(dut.WIN_MAX.value)
    for _ in range(bound + 400):
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        if rvalids:
            break
    else:
        raise AssertionError(
            f"no response in {bound + 400} clocks after the window forgot "
            f"it was waiting, on a bound of {bound}. The grant restarted "
            "the window and `win_guard`, which the grant clears, never "
            "reached the bound.")
    await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.req_i.value = 0
    for _ in range(bound + 400):
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        if int(dut.win_out.value) == 0 and rvalids == grants:
            break
    for _ in range(20):
        await RisingEdge(dut.clk_i)
    w.cancel()

    assert granted_owing == 0, (
        f"{granted_owing} grants were issued while the slave owed the "
        "fabric a response")
    assert rvalids == grants, (
        f"{grants} grants and {rvalids} responses. soc_bus.v rule 3 is "
        "exactly one rvalid per granted request, and a slave that gets "
        "that wrong puts the fabric's per-slave ownership queue out of "
        "step for every later response")
    cause = await env.crd(C_IRQCAUSE)
    assert cause & CAUSE_WIN_TO, (
        f"IRQ_CAUSE reads 0x{cause:08x}: the window recovered without "
        "saying it had to")


# ---------------------------------------------------------------------------
# 4. A guard counter pushed above its bound
# ---------------------------------------------------------------------------
async def _cycles_to_leave(dut, state, deposit_wait, limit=40):
    """Put the engine in `state` with `ev_wait` above that state's bound
    and count the clocks until it leaves. Both deposits are one
    assignment each, which is what docs/52's campaign does."""
    for _ in range(20):
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        if int(dut.ev_state.value) == E_IDLE:
            break
    else:
        raise AssertionError("the engine never reached E_IDLE to deposit into")

    await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.ev_state.value = state
    dut.ev_wait.value = deposit_wait

    n = 0
    while n < limit:
        await Timer(T_SAMPLE - T_DRIVE, unit="ns")
        if int(dut.ev_state.value) != state:
            return n
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
        n += 1
    return limit


@cocotb.test()
async def test_a_wait_counter_pushed_past_its_bound_expires_now(dut):
    """soc_npu_ser.v's rule, which soc_npu.v applies at `win_guard >=
    WIN_MAX` and at `oh_guard >= OH_MAX_G` and did not apply to
    `ev_wait`: an upset that pushes a counter ABOVE its bound must expire
    NOW, not wrap.

    `ev_wait` is four bits. With `==` a counter deposited past its bound
    counts on to 4'hF, wraps to zero and comes back round -- so the state
    whose whole purpose is to be bounded holds for up to fifteen extra
    clocks on the strength of one flipped bit. E_PIN_G is the sharper of
    the two: its bound is 2, so the long way round is thirteen clocks
    added to a state that is meant to last three.

    Both sites are checked, and so is the third `==`, which is not a
    state at all: `fetch_expire` is the sticky report and it has to be
    the SAME predicate as E_FETCH's exit, or an expiry happens and
    C_FETCH_ER stays clear.
    """
    env = Env(dut)
    await env.reset()

    # E_FETCH's bound is FETCH_MAX. Deposit two above it.
    bound_fetch = int(dut.FETCH_MAX.value)
    n = await _cycles_to_leave(dut, E_FETCH, bound_fetch + 2)
    assert n <= 1, (
        f"E_FETCH held for {n} clocks with `ev_wait` deposited at "
        f"{bound_fetch + 2}, above its bound of {bound_fetch}. With `==` "
        "the counter takes the long way round the whole four-bit range; "
        "the rule this file applies to its other two guards is `>=`.")
    cause = await env.crd(C_IRQCAUSE)
    assert cause & CAUSE_FETCH_ER, (
        f"IRQ_CAUSE reads 0x{cause:08x}: E_FETCH gave up on an injected "
        "event and C_FETCH_ER is clear. `fetch_expire` is the only "
        "durable record that an event was abandoned, and it has to fire "
        "on the same condition the state exits on.")

    # E_PIN_G's bound is 2.
    n = await _cycles_to_leave(dut, E_PIN_G, 5)
    assert n <= 1, (
        f"E_PIN_G held for {n} clocks with `ev_wait` deposited at 5, "
        "above its bound of 2. Thirteen of those clocks are the counter "
        "going round the four-bit range to reach 2 again.")

    # And the part still works afterwards, so that neither number above
    # is a measurement of a machine that had simply died.
    assert await env.nrd(ADDR["ID"]) != 0
