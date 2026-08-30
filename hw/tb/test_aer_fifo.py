"""AER event FIFO suite: fill/drain ordering, registered-output timing,
simultaneous read/write streaming, overflow-drop counting (EVQ_IN
software-port semantics, docs/10 section 7.2), drop-counter clear and
saturation, read-on-empty refusal, and reset mid-traffic. A Python
scoreboard model mirrors the contract; the randomized test drives both
against the same stimulus. Fully port-driven, Icarus-clean.

The pointer-TMR group and the entry-parity group are the exception to
"fully port-driven": they reach into the replica banks and into the
queue's storage and corrupt it directly, because that is the fault
docs/16 sections 5.2 and 6.2 measured and there is no port that produces
it. They are the simulation half of the evidence for those two
hardenings; the other half is sw/tests/test_synthesis_guards.py, which is
what says the replicas and the parity bank exist as separate cells in the
netlist, and formal/aer_fifo_props.v P7/P8 and P10/P11/P12, which are
what say the masking and the detection hold for every fault of the class
rather than for the ones enumerated here.
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, Timer


def params(dut):
    width = int(dut.WIDTH.value)
    depth = int(dut.DEPTH.value)
    drop_max = (1 << int(dut.DROP_W.value)) - 1
    return width, depth, drop_max


async def reset(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.wr_en.value = 0
    dut.wr_data.value = 0
    dut.rd_en.value = 0
    dut.drop_clr.value = 0
    dut.rst_n.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def push(dut, value):
    """One-cycle write attempt (accepted or dropped by the DUT)."""
    dut.wr_en.value = 1
    dut.wr_data.value = value
    await RisingEdge(dut.clk)
    dut.wr_en.value = 0
    await Timer(1, unit="ns")  # settle past the NBA update


async def pop(dut):
    """One-cycle accepted read; returns the registered output word,
    which is valid one settle after the accepting edge."""
    assert dut.empty.value == 0, "pop called on an empty FIFO"
    dut.rd_en.value = 1
    await RisingEdge(dut.clk)
    dut.rd_en.value = 0
    await Timer(1, unit="ns")  # settle past the NBA update
    assert dut.rd_valid.value == 1, "accepted read must raise rd_valid"
    return int(dut.rd_data.value)


@cocotb.test()
async def test_reset_state(dut):
    """After reset: empty, not full, level 0, drop counter 0, no rd_valid."""
    await reset(dut)
    assert dut.empty.value == 1
    assert dut.full.value == 0
    assert int(dut.level.value) == 0
    assert int(dut.drop_cnt.value) == 0
    assert dut.rd_valid.value == 0


@cocotb.test()
async def test_fill_and_drain(dut):
    """Fill to DEPTH with distinct events, then drain: exact level
    bookkeeping, full/empty flags, FIFO order preserved end to end."""
    width, depth, _ = params(dut)
    await reset(dut)
    events = [random.getrandbits(width) for _ in range(depth)]
    for i, ev in enumerate(events):
        assert int(dut.level.value) == i
        await push(dut, ev)
    await Timer(1, unit="ns")
    assert int(dut.level.value) == depth
    assert dut.full.value == 1
    assert dut.empty.value == 0
    for i, ev in enumerate(events):
        assert int(dut.level.value) == depth - i
        got = await pop(dut)
        assert got == ev, f"event {i}: got 0x{got:X}, expected 0x{ev:X}"
    assert dut.empty.value == 1
    assert int(dut.level.value) == 0
    assert int(dut.drop_cnt.value) == 0, "no drop may occur below DEPTH"


@cocotb.test()
async def test_registered_output_timing(dut):
    """rd_data changes only on the edge after an accepted read and holds
    afterwards; rd_valid is a single-cycle strobe."""
    width, _, _ = params(dut)
    await reset(dut)
    ev = random.getrandbits(width) | 1
    await push(dut, ev)
    await RisingEdge(dut.clk)  # idle cycle: no read yet
    assert dut.rd_valid.value == 0
    got = await pop(dut)
    assert got == ev
    for _ in range(3):  # output holds, strobe drops
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert dut.rd_valid.value == 0
        assert int(dut.rd_data.value) == ev


@cocotb.test()
async def test_simultaneous_read_write(dut):
    """Streaming with wr_en and rd_en high in the same cycles at constant
    occupancy: level must not move, order must hold."""
    width, depth, _ = params(dut)
    await reset(dut)
    half = depth // 2
    stream = [random.getrandbits(width) for _ in range(half + 4 * depth)]
    for ev in stream[:half]:  # prefill to half
        await push(dut, ev)
    expected = list(stream[:half])
    got = []
    dut.rd_en.value = 1
    for ev in stream[half:]:
        dut.wr_en.value = 1
        dut.wr_data.value = ev
        expected.append(ev)
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.level.value) == half, "level moved during 1R1W stream"
        if dut.rd_valid.value == 1:
            got.append(int(dut.rd_data.value))
    dut.wr_en.value = 0
    await RisingEdge(dut.clk)
    dut.rd_en.value = 0
    await Timer(1, unit="ns")
    if dut.rd_valid.value == 1:
        got.append(int(dut.rd_data.value))
    assert got == expected[:len(got)], "order broken in simultaneous R/W"
    assert int(dut.drop_cnt.value) == 0


@cocotb.test()
async def test_overflow_drop_counting(dut):
    """Writes into a full FIFO are dropped and counted; stored events,
    level and pointers stay intact, and OVF stays visible until cleared."""
    width, depth, _ = params(dut)
    await reset(dut)
    events = [random.getrandbits(width) for _ in range(depth)]
    for ev in events:
        await push(dut, ev)
    extra = 5
    for k in range(extra):  # blind writes into a full FIFO
        await push(dut, random.getrandbits(width))
        await Timer(1, unit="ns")
        assert int(dut.drop_cnt.value) == k + 1, "drop not counted"
        assert int(dut.level.value) == depth, "drop disturbed the level"
        assert dut.full.value == 1
    for i, ev in enumerate(events):  # contents unharmed, order intact
        got = await pop(dut)
        assert got == ev, f"event {i} corrupted by overflow traffic"
    assert dut.empty.value == 1
    assert int(dut.drop_cnt.value) == extra, "drop counter must be sticky"


@cocotb.test()
async def test_drop_on_simultaneous_rw_when_full(dut):
    """A write coincident with a read while full is dropped (full is
    evaluated before the read frees the slot): level goes to DEPTH-1 and
    the drop is counted."""
    width, depth, _ = params(dut)
    await reset(dut)
    for ev in range(depth):
        await push(dut, ev & ((1 << width) - 1))
    dut.wr_en.value = 1
    dut.wr_data.value = (1 << width) - 1
    dut.rd_en.value = 1
    await RisingEdge(dut.clk)
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    await Timer(1, unit="ns")
    assert int(dut.drop_cnt.value) == 1, "coincident write-at-full not counted"
    assert int(dut.level.value) == depth - 1, "read at full must still proceed"
    got = await pop(dut)
    assert got == 1, "second-oldest event corrupted"


@cocotb.test()
async def test_drop_clear_and_coincident_drop(dut):
    """drop_clr zeroes the counter; a drop on the same edge as the clear
    restarts it at 1 so the event is not lost (house convention)."""
    width, depth, _ = params(dut)
    await reset(dut)
    for ev in range(depth):
        await push(dut, ev & ((1 << width) - 1))
    for _ in range(3):
        await push(dut, 0)
    await Timer(1, unit="ns")
    assert int(dut.drop_cnt.value) == 3
    dut.drop_clr.value = 1  # plain clear
    await RisingEdge(dut.clk)
    dut.drop_clr.value = 0
    await Timer(1, unit="ns")
    assert int(dut.drop_cnt.value) == 0, "drop_clr did not clear"
    dut.drop_clr.value = 1  # clear coincident with a dropped write
    dut.wr_en.value = 1
    dut.wr_data.value = 1
    await RisingEdge(dut.clk)
    dut.drop_clr.value = 0
    dut.wr_en.value = 0
    await Timer(1, unit="ns")
    assert int(dut.drop_cnt.value) == 1, "coincident drop lost by clear"


@cocotb.test()
async def test_drop_counter_saturates(dut):
    """The sticky counter saturates instead of wrapping: a wrapped drop
    counter would erase the overflow record."""
    width, depth, drop_max = params(dut)
    await reset(dut)
    for ev in range(depth):
        await push(dut, ev & ((1 << width) - 1))
    dut.wr_en.value = 1  # hold a blind write against the full FIFO
    dut.wr_data.value = 0
    await ClockCycles(dut.clk, drop_max + 50)
    dut.wr_en.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.drop_cnt.value) == drop_max, "drop counter wrapped"
    assert int(dut.level.value) == depth, "saturation traffic touched data"


@cocotb.test()
async def test_read_on_empty_refused(dut):
    """rd_en on an empty FIFO does nothing: no rd_valid, pointers hold,
    and the next write/read pair still behaves."""
    width, _, _ = params(dut)
    await reset(dut)
    dut.rd_en.value = 1
    for _ in range(4):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert dut.rd_valid.value == 0, "spurious rd_valid on empty"
        assert dut.empty.value == 1
        assert int(dut.level.value) == 0
    dut.rd_en.value = 0
    ev = random.getrandbits(width)
    await push(dut, ev)
    assert await pop(dut) == ev


@cocotb.test()
async def test_random_traffic_scoreboard(dut):
    """Randomized wr/rd/clear traffic against a Python model of the whole
    contract: occupancy, flags, output order and drop accounting."""
    width, depth, drop_max = params(dut)
    await reset(dut)
    random.seed(20260824)
    model = []          # FIFO contents
    model_drops = 0
    expected_rd = None  # value an accepted read will present next cycle
    for _ in range(2000):
        wr = random.random() < 0.55
        rd = random.random() < 0.45
        clr = random.random() < 0.01
        data = random.getrandbits(width)
        dut.wr_en.value = 1 if wr else 0
        dut.wr_data.value = data
        dut.rd_en.value = 1 if rd else 0
        dut.drop_clr.value = 1 if clr else 0
        # model the edge (full/empty sampled before the edge)
        wr_drop = wr and len(model) == depth
        rd_ok = rd and len(model) > 0
        if wr and len(model) < depth:
            model.append(data)
        expected_rd = model.pop(0) if rd_ok else None
        if clr:
            model_drops = 1 if wr_drop else 0
        elif wr_drop and model_drops < drop_max:
            model_drops += 1
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.level.value) == len(model), "level diverged from model"
        assert dut.full.value == (1 if len(model) == depth else 0)
        assert dut.empty.value == (1 if len(model) == 0 else 0)
        assert int(dut.drop_cnt.value) == model_drops, "drop accounting diverged"
        if expected_rd is not None:
            assert dut.rd_valid.value == 1
            assert int(dut.rd_data.value) == expected_rd, "data diverged"
        else:
            assert dut.rd_valid.value == 0
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    dut.drop_clr.value = 0


@cocotb.test()
async def test_reset_mid_traffic(dut):
    """An asynchronous reset in the middle of full-throttle traffic
    empties the FIFO, zeroes the drop record, and leaves the FIFO fully
    functional afterwards."""
    width, depth, _ = params(dut)
    await reset(dut)
    for ev in range(depth):  # make it full and force some drops
        await push(dut, ev & ((1 << width) - 1))
    await push(dut, 0)
    dut.wr_en.value = 1
    dut.wr_data.value = 0x5A5A & ((1 << width) - 1)
    dut.rd_en.value = 1
    await RisingEdge(dut.clk)
    await Timer(3, unit="ns")  # async assertion between edges
    dut.rst_n.value = 0
    await Timer(2, unit="ns")
    assert dut.empty.value == 1, "reset must empty the FIFO immediately"
    assert int(dut.level.value) == 0
    assert int(dut.drop_cnt.value) == 0
    await RisingEdge(dut.clk)
    dut.wr_en.value = 0
    dut.rd_en.value = 0
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    assert dut.rd_valid.value == 0
    events = [random.getrandbits(width) for _ in range(depth)]
    for ev in events:  # full fill/drain proves recovery
        await push(dut, ev)
    await Timer(1, unit="ns")
    assert dut.full.value == 1
    for ev in events:
        assert await pop(dut) == ev
    assert dut.empty.value == 1
    assert int(dut.drop_cnt.value) == 0


# =====================================================================
# pointer TMR (hw/rtl/aer_fifo.v, docs/16 section 5.2)
# =====================================================================
# The six replica banks of the two pointers. Each is an aer_ptr_bank
# instance holding one AW+1 bit pointer replica in `bits`, and `bits` is
# the STORED IMAGE, not the pointer: replica b holds the complement and
# replica c an XOR mixing of it. That is deliberate and it is why these
# tests flip a bit of `bits` rather than of the pointer value -- an upset
# lands on a physical cell, and in replica c one such cell carries two or
# three pointer bits at once, which is the harder case and the one the
# voter has to mask anyway.
PTR_BANKS = ("u_wptr_a", "u_wptr_b", "u_wptr_c",
             "u_rptr_a", "u_rptr_b", "u_rptr_c")


def ptr_width(dut):
    """AW + 1: the pointer width, wrap bit included."""
    return int(dut.AW.value) + 1


def observable(dut):
    """Everything a consumer of this module can see, except rd_valid,
    which is a one-cycle strobe and therefore not comparable across a
    clock edge. If a masked fault is really masked, none of this moves.
    """
    return (int(dut.level.value), int(dut.full.value),
            int(dut.empty.value), int(dut.rd_data.value),
            int(dut.drop_cnt.value))


def flip(bank, bit):
    """Flip one stored bit of one replica: the fault model of docs/16."""
    bank.bits.value = int(bank.bits.value) ^ (1 << bit)


@cocotb.test()
async def test_pointer_replicas_agree_and_are_quiet(dut):
    """No traffic pattern raises ptr_mismatch. A disagreement flag that
    fired during ordinary work would be worth nothing as telemetry, and
    the pilot counts it into CNT_TMR and lights a pin from it.
    """
    width, depth, _ = params(dut)
    await reset(dut)
    assert dut.ptr_mismatch.value == 0, "mismatch out of reset"
    events = [random.getrandbits(width) for _ in range(depth)]
    for ev in events:
        await push(dut, ev)
        assert dut.ptr_mismatch.value == 0, "mismatch during fill"
    for _ in range(4):  # writes into a full FIFO: pointers must not move
        await push(dut, 0)
        assert dut.ptr_mismatch.value == 0, "mismatch on a dropped write"
    for i, ev in enumerate(events):
        assert await pop(dut) == ev
        assert dut.ptr_mismatch.value == 0, f"mismatch during drain at {i}"
    # and the three replicas of each pointer hold the same pointer value
    for a, b, c in (("u_wptr_a", "u_wptr_b", "u_wptr_c"),
                    ("u_rptr_a", "u_rptr_b", "u_rptr_c")):
        qa = int(getattr(dut, a).q.value)
        qb = int(getattr(dut, b).q.value)
        qc = int(getattr(dut, c).q.value)
        assert qa == qb == qc, f"replicas diverged: {a}={qa} {b}={qb} {c}={qc}"


@cocotb.test()
async def test_single_replica_fault_is_masked_and_reported(dut):
    """Every bit of every replica, one at a time: the queue's observable
    state does not move, ptr_mismatch reports the correction, and the
    next clock edge repairs the replica from the vote.

    The repair is not decoration. Without it a replica stays wrong until
    the pointer next changes, and the second upset of a mission meets a
    domain already carrying the first -- which is the difference between
    a TMR domain that tolerates one fault at a time and one that
    tolerates one fault ever.
    """
    width, _, _ = params(dut)
    pw = ptr_width(dut)
    await reset(dut)
    for ev in range(5):  # move both pointers off zero and off each other
        await push(dut, (ev + 1) & ((1 << width) - 1))
    for _ in range(2):
        await pop(dut)
    await Timer(1, unit="ns")
    ref = observable(dut)
    assert dut.ptr_mismatch.value == 0

    for name in PTR_BANKS:
        bank = getattr(dut, name)
        for bit in range(pw):
            good = int(bank.bits.value)
            flip(bank, bit)
            await Timer(1, unit="ns")
            assert dut.ptr_mismatch.value == 1, (
                f"{name} bit {bit} corrupted and ptr_mismatch stayed low: "
                "a corrected upset that is not reported is the silence "
                "docs/16 section 5.2 is about")
            assert observable(dut) == ref, (
                f"{name} bit {bit}: single-replica fault reached the "
                f"outputs, {observable(dut)} != {ref}")
            await RisingEdge(dut.clk)   # idle edge: reload from the vote
            await Timer(1, unit="ns")
            assert int(bank.bits.value) == good, (
                f"{name} bit {bit} was not repaired by the voted "
                f"feedback: 0x{int(bank.bits.value):X} != 0x{good:X}")
            assert dut.ptr_mismatch.value == 0, (
                f"{name} bit {bit}: mismatch still asserted after repair")
            assert observable(dut) == ref


@cocotb.test()
async def test_pointer_fault_does_not_corrupt_the_event_stream(dut):
    """The docs/16 section 5.2 experiment, re-run against the protected
    pointers. That table is a list of what an unprotected pointer upset
    did to the drained stream -- whole bursts re-emitted, events
    duplicated, events lost, events fabricated, an unwritten slot
    presented as a spike -- none of which a consumer can tell from a real
    spike train, because docs/10 section 7.1 freezes the event word at
    TYPE plus a 10-bit ID with no sequence number and no length.

    The burst is the one from that table, truncated to DEPTH so that the
    queue is never asked to hold more than it has: this suite is run at
    DEPTH 2, 8 and the default 64, and a burst that overflowed would be
    testing the drop path instead of the pointers.

    One replica bit is corrupted during the fill and one during the
    drain, and the drained sequence must be the golden sequence exactly:
    same events, same order, same count.
    """
    width, depth, _ = params(dut)
    pw = ptr_width(dut)
    golden = [1, 2, 5, 6, 4, 2][:depth]
    fill_at = min(1, len(golden) - 1)
    drain_at = min(3, len(golden) - 1)
    await reset(dut)
    for name in PTR_BANKS:
        bank = getattr(dut, name)
        for bit in range(pw):
            seen_mismatch = False
            for i, ev in enumerate(golden):
                if i == fill_at:              # fault during the fill
                    flip(bank, bit)
                    await Timer(1, unit="ns")
                    seen_mismatch |= dut.ptr_mismatch.value == 1
                await push(dut, ev)
            got = []
            for i in range(len(golden)):
                if i == drain_at:             # fault during the drain
                    flip(bank, bit)
                    await Timer(1, unit="ns")
                    seen_mismatch |= dut.ptr_mismatch.value == 1
                got.append(await pop(dut))
            assert seen_mismatch, (
                f"{name} bit {bit}: neither injection was reported")
            assert got == golden, (
                f"{name} bit {bit}: drained {got}, expected {golden}")
            assert dut.empty.value == 1, (
                f"{name} bit {bit}: queue not empty after the drain, "
                f"level={int(dut.level.value)}")
            assert int(dut.drop_cnt.value) == 0, (
                f"{name} bit {bit}: a pointer fault caused a drop")


@cocotb.test()
async def test_pointer_fault_under_simultaneous_read_write(dut):
    """The same fault with both ports active, which is the case where a
    corrupted pointer has the most to break: the write index, the read
    index and the full/empty decision are all in flight on the same edge.
    """
    width, depth, _ = params(dut)
    pw = ptr_width(dut)
    await reset(dut)
    half = depth // 2
    for i in range(half):
        await push(dut, (0x100 + i) & ((1 << width) - 1))
    expected = [(0x100 + i) & ((1 << width) - 1) for i in range(half)]
    got = []
    nxt = 0x200
    dut.rd_en.value = 1
    for step in range(4 * pw):
        bank = getattr(dut, PTR_BANKS[step % len(PTR_BANKS)])
        flip(bank, step % pw)
        await Timer(1, unit="ns")
        assert dut.ptr_mismatch.value == 1, "injection not reported"
        word = nxt & ((1 << width) - 1)
        nxt += 1
        dut.wr_en.value = 1
        dut.wr_data.value = word
        expected.append(word)
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        assert int(dut.level.value) == half, (
            f"step {step}: level moved to {int(dut.level.value)} during a "
            f"1R1W stream, expected {half}")
        if dut.rd_valid.value == 1:
            got.append(int(dut.rd_data.value))
    dut.wr_en.value = 0
    await RisingEdge(dut.clk)
    dut.rd_en.value = 0
    await Timer(1, unit="ns")
    if dut.rd_valid.value == 1:
        got.append(int(dut.rd_data.value))
    assert got == expected[:len(got)], (
        f"order broken under injection: {got} vs {expected[:len(got)]}")
    assert int(dut.drop_cnt.value) == 0


# =====================================================================
# entry parity (hw/rtl/aer_fifo.v, docs/16 section 6.2 item 4)
# =====================================================================
# One even-parity bit per queue slot, held in the aer_par_bank instance
# u_par and checked on every accepted read. It DETECTS and does not
# correct: a stored word that fails its check is consumed, discarded,
# reported on par_err, and rd_valid stays low for that read.
#
# These tests deposit into the storage directly for the same reason the
# pointer group does -- an upset lands on a physical cell and no port
# produces one -- and they walk all four cases the header claims:
# a single upset in the data word (detected), a single upset in the check
# bit itself (detected, as a false discard of a good event), a
# double-bit upset (NOT detected, which is what one check bit costs), and
# a corrupted slot that is rewritten before it is read (repaired).
#
# The loops deliberately do not re-reset between cases. reset() starts a
# clock, so calling it in a loop would start several; and after a full
# fill and drain both pointers have advanced by DEPTH, so the slot
# indices realign and event k of the next fill lands in slot k again.


def word_parity(value, width):
    """Even parity of an event word: the bit aer_fifo stores beside it."""
    return bin(value & ((1 << width) - 1)).count("1") & 1


def slots_under_test(depth):
    """First, middle and last slot. Walking all 64 at the default DEPTH
    would multiply the runtime of four tests by twenty for no new
    mechanism: the parity bank is one flip-flop per slot with no carry
    and no interaction between slots."""
    return sorted({0, depth // 2, depth - 1})


def bits_under_test(width):
    """Bit 0, a middle bit and the top bit. docs/16 section 6.2 records
    that the evq_mem records were spread over bit 0 and bit 14 alike with
    no concentration to exploit, so position is sampled rather than
    walked."""
    return sorted({0, width // 2, width - 1})


async def read_probed(dut):
    """One accepted read, reporting what the check did with it.

    par_err is combinational and belongs to the cycle of the read, so it
    is sampled BEFORE the edge that captures the answer; rd_valid belongs
    to the cycle after it. Returns (par_err, rd_valid, rd_data).
    """
    assert dut.empty.value == 0, "read_probed called on an empty FIFO"
    dut.rd_en.value = 1
    await Timer(1, unit="ns")          # settle the combinational check
    err = int(dut.par_err.value)
    await RisingEdge(dut.clk)
    dut.rd_en.value = 0
    await Timer(1, unit="ns")          # settle past the NBA update
    return err, int(dut.rd_valid.value), int(dut.rd_data.value)


async def fill(dut, width, depth, base):
    """Fill an empty queue with DEPTH distinct events; event k lands in
    slot k. Returns the events."""
    assert dut.empty.value == 1, "fill called on a non-empty FIFO"
    mask = (1 << width) - 1
    events = [(base + i * 7) & mask for i in range(depth)]
    for ev in events:
        await push(dut, ev)
    return events


async def drain_probed(dut, depth):
    """Drain DEPTH accepted reads. Returns (delivered words, par_err
    count, the read indices that were discarded)."""
    got, errs, dropped = [], 0, []
    for i in range(depth):
        err, valid, data = await read_probed(dut)
        errs += err
        if valid:
            got.append(data)
        else:
            dropped.append(i)
        assert valid != err, (
            f"read {i}: par_err={err} and rd_valid={valid} -- a discarded "
            "read must not also answer, and an answered read must not "
            "also be reported")
    return got, errs, dropped


def flip_stored_word(dut, slot, *bits):
    """Flip the named bits of one stored event word in ONE write: the
    docs/16 evq_mem fault, and its double-bit companion.

    All the bits at once is not tidiness. A cocotb value write lands at
    the end of the delta cycle, so two successive read-modify-writes to
    the same handle both read the pre-write value and the second wins --
    a two-bit deposit written that way is a one-bit deposit, which the
    check detects, and the double-bit test would pass while measuring
    nothing.
    """
    word = int(dut.mem[slot].value)
    for bit in bits:
        word ^= 1 << bit
    dut.mem[slot].value = word


def flip_check_bit(dut, slot):
    """Flip one slot's stored parity bit inside the aer_par_bank."""
    dut.u_par.bits.value = int(dut.u_par.bits.value) ^ (1 << slot)


@cocotb.test()
async def test_entry_parity_is_quiet_and_stored_beside_the_word(dut):
    """No traffic pattern raises par_err, every read answers, and the
    bank holds the even parity of the word in the matching slot.

    A checker that fired during ordinary work would be worth nothing: it
    would convert good events into losses at the rate the queue runs at,
    which is a worse failure than the one it exists to catch. The stored
    image is asserted as well as the behaviour, because a bank that held
    something else and was checked against itself would also be quiet.
    """
    width, depth, _ = params(dut)
    await reset(dut)
    assert dut.par_err.value == 0, "par_err out of reset"
    events = await fill(dut, width, depth, 0x2A5)
    for slot, ev in enumerate(events):
        stored = (int(dut.u_par.bits.value) >> slot) & 1
        assert stored == word_parity(ev, width), (
            f"slot {slot}: bank holds {stored}, event 0x{ev:X} has parity "
            f"{word_parity(ev, width)}")
    for _ in range(4):                       # writes into a full FIFO
        await push(dut, 0)
        assert dut.par_err.value == 0, "par_err on a dropped write"
    got, errs, dropped = await drain_probed(dut, depth)
    assert errs == 0 and dropped == [], (
        f"a clean queue reported {errs} parity errors at reads {dropped}")
    assert got == events, "clean drain did not preserve the events"
    assert int(dut.drop_cnt.value) == 4, "the write-side count moved"


@cocotb.test()
async def test_single_bit_upset_in_a_stored_word_is_discarded(dut):
    """The docs/16 section 6.2 experiment, re-run against the check.

    That table is 32 single-bit deposits into the two queues' mem[] with
    7 ending in silent data corruption -- a wrong event word handed to a
    consumer that has no way to tell it from a real spike, because
    docs/10 section 7.1 freezes the word at TYPE plus a 10-bit ID with no
    sequence number and no length. Every one of those deposits is a
    single bit and therefore odd weight, which is exactly what one parity
    bit detects.

    For each sampled slot and bit: fill, corrupt one stored bit, drain.
    The corrupted read must report par_err and answer nothing, every
    other event must come out golden and in order, and the queue must
    still empty -- the entry is consumed, not parked on.
    """
    width, depth, _ = params(dut)
    await reset(dut)
    base = 0x111
    for slot in slots_under_test(depth):
        for bit in bits_under_test(width):
            events = await fill(dut, width, depth, base)
            base += 0x40
            flip_stored_word(dut, slot, bit)
            await Timer(1, unit="ns")
            got, errs, dropped = await drain_probed(dut, depth)
            assert dropped == [slot], (
                f"slot {slot} bit {bit}: discarded reads {dropped}, "
                f"expected exactly [{slot}] -- an undetected single-bit "
                "upset is the silent corruption this check exists for")
            assert errs == 1, (
                f"slot {slot} bit {bit}: par_err fired {errs} times")
            assert got == [e for i, e in enumerate(events) if i != slot], (
                f"slot {slot} bit {bit}: the surviving events were "
                f"{[hex(g) for g in got]}")
            assert dut.empty.value == 1, (
                f"slot {slot} bit {bit}: the discarded entry was not "
                f"consumed, level={int(dut.level.value)}")
            assert int(dut.drop_cnt.value) == 0, (
                f"slot {slot} bit {bit}: a parity discard moved the "
                "write-side drop counter, which counts refused writes")


@cocotb.test()
async def test_upset_in_the_check_bit_is_a_reported_false_discard(dut):
    """The check bit is inside the codeword it protects, so an upset in
    the parity bank itself is detected too -- as the loss of a good
    event rather than as the delivery of a bad one.

    That is the right side to fail on and it is worth measuring rather
    than assuming: the failure is a counted, announced drop of one event,
    not a corruption, and it costs exactly the same as the case it exists
    to catch. These flip-flops are new state this hardening adds, and
    this is the test that says what an upset in them does.
    """
    width, depth, _ = params(dut)
    await reset(dut)
    base = 0x333
    for slot in slots_under_test(depth):
        events = await fill(dut, width, depth, base)
        base += 0x40
        flip_check_bit(dut, slot)
        await Timer(1, unit="ns")
        got, errs, dropped = await drain_probed(dut, depth)
        assert dropped == [slot] and errs == 1, (
            f"check bit {slot}: discarded {dropped}, par_err {errs}")
        assert got == [e for i, e in enumerate(events) if i != slot], (
            f"check bit {slot}: an upset in the parity bank corrupted an "
            "event instead of dropping one")
        assert dut.empty.value == 1


@cocotb.test()
async def test_double_bit_upset_is_not_detected(dut):
    """The honest limit of one check bit, measured rather than stated.

    Even-weight corruption passes the check and is DELIVERED as a valid
    event. This is the residual after this hardening and it is what the
    SECDED (22,16) code of docs/16 section 6.2 item 4 would buy for six
    check bits per entry instead of one -- correction of the single-bit
    case and detection of this one. A test that only walked the covered
    cases would make the protection look complete.
    """
    width, depth, _ = params(dut)
    if width < 2:
        return
    await reset(dut)
    lo, hi = 0, width - 1
    for slot in slots_under_test(depth):
        events = await fill(dut, width, depth, 0x555)
        flip_stored_word(dut, slot, lo, hi)
        await Timer(1, unit="ns")
        got, errs, dropped = await drain_probed(dut, depth)
        assert errs == 0 and dropped == [], (
            f"slot {slot}: a two-bit upset was reported, which one parity "
            "bit cannot do -- the check has changed and this bound with it")
        corrupted = events[slot] ^ (1 << lo) ^ (1 << hi)
        expected = list(events)
        expected[slot] = corrupted
        assert got == expected, (
            f"slot {slot}: expected the corrupted word 0x{corrupted:X} to "
            f"be delivered undetected, got {[hex(g) for g in got]}")
        assert dut.empty.value == 1


@cocotb.test()
async def test_a_rewritten_slot_is_repaired(dut):
    """A corrupted slot that is written again before it is read carries
    no error afterwards: the check bit is rewritten with the word from
    the same wr_data on the same edge, so the pair cannot drift apart.

    Without this the protection would accumulate -- one upset would make
    a slot report an error for the rest of the mission, turning a
    single-event upset into a permanent one-in-DEPTH event loss.
    """
    width, depth, _ = params(dut)
    await reset(dut)
    events = await fill(dut, width, depth, 0x77)
    flip_stored_word(dut, 0, 0)
    await Timer(1, unit="ns")
    got, errs, dropped = await drain_probed(dut, depth)
    assert dropped == [0] and errs == 1
    assert got == events[1:]
    fresh = await fill(dut, width, depth, 0x99)
    got, errs, dropped = await drain_probed(dut, depth)
    assert errs == 0 and dropped == [], (
        "a slot corrupted in the previous fill still reported an error "
        f"after being rewritten: discarded {dropped}")
    assert got == fresh
