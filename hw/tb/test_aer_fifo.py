"""AER event FIFO suite: fill/drain ordering, registered-output timing,
simultaneous read/write streaming, overflow-drop counting (EVQ_IN
software-port semantics, docs/10 section 7.2), drop-counter clear and
saturation, read-on-empty refusal, and reset mid-traffic. A Python
scoreboard model mirrors the contract; the randomized test drives both
against the same stimulus. Fully port-driven, Icarus-clean.
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
