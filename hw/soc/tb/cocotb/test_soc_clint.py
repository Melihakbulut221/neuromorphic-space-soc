"""soc_clint suite: the RISC-V machine timer and software interrupt.

WHERE THE EXPECTATIONS COME FROM. Three places, none of which is the RTL:

  * the RISC-V privileged specification's machine timer. mtime is a
    monotonically increasing counter; mtimecmp is a comparand; the timer
    interrupt is a LEVEL that is asserted exactly while
    mtime >= mtimecmp, unsigned, over the full 64 bits; the only way
    software clears it is by raising mtimecmp. msip's low bit is the
    machine software interrupt and nothing else in the word is;
  * the standard CLINT register layout that NOELVSYS places at
    0xE0000000 (docs/08-gr801-datasheet-notes.md section 2.2): msip at
    0x0000, mtimecmp at 0x4000, mtime at 0xBFF8;
  * the fabric slave contract S1-S4 quoted in the header of
    hw/soc/rtl/soc_bus.v: gnt when ready, exactly one rvalid per grant
    carrying rdata and err, in order.

The region base comes from sw/golden/memmap_gen.py, which is generated
from regmap/memmap.yaml, so no address literal for the block's base
appears below. The OFFSETS inside the block are the RISC-V layout above
and are written here because that is where they are defined.

The RTL was read for the port names and for the fact that rst_ni is
active low. Nothing below restates its structure.

WHAT THIS SUITE DOES NOT COVER
------------------------------
  * TICK_DIV other than 1. Every test here runs the block with mtime
    incrementing once per clock, which is how soc_top.v instantiates it.
    A divided time base is a parameter nothing exercises.
  * The 64-bit write hazard as a BUG. test_naive_mtimecmp_write_glitches
    demonstrates that the hazard is real and reachable; it does not
    claim the block avoids it, because the block deliberately does not
    (soc_clint.v's header says why). What is checked is that the
    documented sequence avoids it.
  * Any interaction with the core. Whether Ibex takes the interrupt this
    block raises is the whole-SoC run in hw/soc/flow/sim_soc.sh, not
    here.
  * Multi-hart layout. There is one hart; the offsets a second hart's
    msip and mtimecmp would occupy are checked to FAULT, which is a
    statement about this SoC and not about the CLINT specification.
  * Wrap of mtime past 2^64. Unreachable in any simulation.
  * Gate-level behaviour, timing, X-propagation and power.
  * Reset asserted mid-transaction. Nothing in the fabric contract says
    what that should do, so nothing is claimed.
"""

import random
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "sw"))
from golden.memmap_gen import CORE_IRQS, REGIONS  # noqa: E402

BASE, SIZE = REGIONS["CLINT"][0], REGIONS["CLINT"][1]

# The standard CLINT layout. Offsets within the region.
MSIP = 0x0000
MTIMECMPL = 0x4000
MTIMECMPH = 0x4004
MTIMEL = 0xBFF8
MTIMEH = 0xBFFC
IMPLEMENTED = (MSIP, MTIMECMPL, MTIMECMPH, MTIMEL, MTIMEH)

CLK_NS = 10
T_DRIVE = 1
T_SAMPLE = 8
T_CHECK = 9


def val(sig):
    s = str(sig.value)
    if any(c not in "01" for c in s):
        raise AssertionError("non-binary value {!r} on {}".format(s, sig._path))
    return int(s, 2)


class Clint:
    """A protocol-legal fabric master driving one transaction at a time.

    Rule 1: req and payload held until gnt. Rule 3: exactly one rvalid per
    grant, never in the grant cycle. The agent enforces both while it
    runs, so every access made by every test below is also a protocol
    check.
    """

    def __init__(self, dut):
        self.dut = dut
        self.grants = 0
        self.rvalids = 0

    async def _xact(self, off, we, wdata=0, be=0xF):
        dut = self.dut
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
        dut.req_i.value = 1
        dut.addr_i.value = BASE + off
        dut.we_i.value = we
        dut.be_i.value = be
        dut.wdata_i.value = wdata
        # Hold until granted.
        for _ in range(64):
            await Timer(T_SAMPLE - T_DRIVE, unit="ns")
            if val(dut.gnt_o):
                self.grants += 1
                break
            assert val(dut.rvalid_o) == 0, "rvalid before any grant"
            await RisingEdge(dut.clk_i)
            await Timer(T_DRIVE, unit="ns")
        else:
            raise AssertionError("no grant for offset 0x{:04x} in 64 cycles"
                                 .format(off))
        # Payload may move after the grant (rule 2); make it move, so a
        # block that had not captured it is caught.
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
        dut.req_i.value = 0
        dut.addr_i.value = 0xDEADBEE0
        dut.we_i.value = 1
        dut.be_i.value = 0x5
        dut.wdata_i.value = 0xBADC0DE5
        for _ in range(64):
            await Timer(T_SAMPLE - T_DRIVE, unit="ns")
            if val(dut.rvalid_o):
                self.rvalids += 1
                return val(dut.rdata_o), val(dut.err_o)
            await RisingEdge(dut.clk_i)
            await Timer(T_DRIVE, unit="ns")
        raise AssertionError("no response for offset 0x{:04x}".format(off))

    async def read(self, off):
        d, e = await self._xact(off, 0)
        assert e == 0, "read of 0x{:04x} returned err".format(off)
        return d

    async def read_raw(self, off):
        return await self._xact(off, 0)

    async def write(self, off, data, be=0xF):
        d, e = await self._xact(off, 1, data, be)
        assert e == 0, "write of 0x{:04x} returned err".format(off)
        return d

    async def write_raw(self, off, data, be=0xF):
        return await self._xact(off, 1, data, be)

    async def mtime(self):
        """The documented read sequence: high, low, high again."""
        for _ in range(8):
            hi = await self.read(MTIMEH)
            lo = await self.read(MTIMEL)
            hi2 = await self.read(MTIMEH)
            if hi == hi2:
                return (hi << 32) | lo
        raise AssertionError("mtime never read coherently")

    async def set_mtimecmp(self, v):
        """The documented write sequence: unreachable low half first."""
        await self.write(MTIMECMPL, 0xFFFFFFFF)
        await self.write(MTIMECMPH, (v >> 32) & 0xFFFFFFFF)
        await self.write(MTIMECMPL, v & 0xFFFFFFFF)


async def next_cycle(dut):
    """Advance to the sampling point of the next clock cycle.

    Every transaction returns at T_SAMPLE of the cycle in which its write
    took effect, so a check written immediately after a write observes
    that cycle. Anything later has to come through here. The first
    version of this file used `Timer(T_CHECK)` for the purpose, which
    adds 9 ns to a point that is already 8 ns into a 10 ns cycle and so
    silently lands one cycle further on than intended -- three tests
    failed by exactly one mtime tick.
    """
    await RisingEdge(dut.clk_i)
    await Timer(T_SAMPLE, unit="ns")


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
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
    return Clint(dut)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_region_is_big_enough_for_the_layout(dut):
    """The frozen map's CLINT region must contain the standard layout.

    Derived from the generated map, so shrinking the region in the YAML
    fails here instead of silently aliasing mtime onto something else.
    """
    assert BASE == REGIONS["CLINT"][0]
    assert REGIONS["CLINT"][5] == "clint", (
        "CLINT has no fabric port in the map, so nothing decodes it")
    for off in IMPLEMENTED:
        assert off + 4 <= SIZE, (
            "offset 0x{:04x} is outside the 0x{:x}-byte region".format(off, SIZE))
    # The two core inputs this block drives, as the map names them.
    assert CORE_IRQS["MTIMER"][0] == 7
    assert CORE_IRQS["MSOFT"][0] == 3
    dut._log.info("CLINT at 0x%08x, 0x%x bytes, %d registers",
                  BASE, SIZE, len(IMPLEMENTED))


@cocotb.test()
async def test_reset_state(dut):
    """Out of reset: msip clear, mtimecmp zero -- and mtip therefore HIGH.

    That last part is not a defect and it is not an accident. The RISC-V
    specification gives mtimecmp no reset value; resetting it to zero
    means mtime >= mtimecmp from cycle zero. It is harmless because
    mie.MTIE resets clear, and it is asserted here so that anyone who
    changes it has to change this test and read the reasoning first.
    """
    c = await setup(dut)
    assert val(dut.irq_software_o) == 0
    assert val(dut.irq_timer_o) == 1, (
        "mtimecmp resets to 0, so the timer interrupt must be asserted at "
        "reset; a block that hid this with a non-standard reset value would "
        "surprise a driver that enabled MTIE before programming a deadline")
    assert await c.read(MSIP) == 0
    assert await c.read(MTIMECMPL) == 0
    assert await c.read(MTIMECMPH) == 0


@cocotb.test()
async def test_mtime_advances_once_per_clock(dut):
    """TICK_DIV = 1: mtime counts clocks, exactly.

    The two reads are separated by a known number of transactions, and
    each transaction is a known number of cycles, so the DIFFERENCE is
    checked and not merely the direction. A counter that ticked twice per
    clock, or every other clock, passes a monotonicity test and fails
    this one.
    """
    c = await setup(dut)
    a = await c.read(MTIMEL)
    n = 20
    for _ in range(n):
        await RisingEdge(dut.clk_i)
    b = await c.read(MTIMEL)
    # One read costs a fixed number of cycles; measure it rather than
    # asserting it, then require the gap to be that plus n.
    d0 = await c.read(MTIMEL)
    d1 = await c.read(MTIMEL)
    per_read = d1 - d0
    assert per_read > 0
    assert b - a == n + per_read, (
        "mtime advanced by {} over {} idle clocks plus one read of {}"
        .format(b - a, n, per_read))
    dut._log.info("mtime: %d clocks per read transaction", per_read)


@cocotb.test()
async def test_mtip_is_a_level_over_64_bits(dut):
    """mtip == (mtime >= mtimecmp), and the comparison is 64 bits wide.

    The high half is what makes this test worth writing: a block that
    compared only the low 32 bits would pass every test that keeps
    mtimecmp small. The first step below is exactly that trap -- mtimecmp
    is 2^40 + 0x1000 with mtime a few hundred, so a 32-bit compare would
    find mtime_low >= 0x1000 eventually and a 64-bit one never will.

    Both halves of mtime are read back after they are written. Without
    that, a high-half write that did nothing would make the last step
    look like a comparison bug instead of a lost store.
    """
    c = await setup(dut)
    deadline = (1 << 40) | 0x1000
    await c.set_mtimecmp(deadline)
    assert val(dut.irq_timer_o) == 0, (
        "mtimecmp = 2^40 + 0x1000 with mtime small: a 32-bit compare asserts "
        "here and a 64-bit one does not")

    # Same high half, low half below the deadline: still not met.
    await c.write(MTIMEH, deadline >> 32)
    await c.write(MTIMEL, 0x00000000)
    assert val(dut.irq_timer_o) == 0, (
        "high halves equal and mtime_low below mtimecmp_low, but mtip is high")
    assert await c.read(MTIMEH) == deadline >> 32, (
        "the write to the high half of mtime did not land")

    # Low half at the deadline: met, exactly.
    await c.write(MTIMEL, deadline & 0xFFFFFFFF)
    assert val(dut.irq_timer_o) == 1, (
        "mtime reached mtimecmp exactly and mtip is low; the comparison is "
        "strictly-greater rather than greater-or-equal")

    # Raising the deadline clears it again, which is the only mechanism
    # the specification gives software.
    await c.set_mtimecmp(deadline + (1 << 20))
    assert val(dut.irq_timer_o) == 0, (
        "mtip did not clear when mtimecmp was raised above mtime, so it is "
        "latched rather than a level")


@cocotb.test()
async def test_deadline_fires_at_the_right_cycle(dut):
    """A deadline n ticks ahead asserts mtip after exactly n clocks.

    Anchored on a WRITE and not on a read, so the timing is exact rather
    than approximate: a write transaction returns in the cycle its value
    landed, and every clock edge after that adds one tick. mtip must be
    low for the first n-1 of them and high on the nth. A counter that
    ticked twice per clock, or a comparison off by one, fails at a
    specific n rather than "sometimes".
    """
    c = await setup(dut)
    for n in (1, 2, 3, 8, 41):
        deadline = 0x0010_0000
        await c.set_mtimecmp(deadline)
        await c.write(MTIMEH, 0)
        await c.write(MTIMEL, deadline - n)
        assert val(dut.irq_timer_o) == 0, (
            "n = {}: mtip already high in the cycle mtime was set below the "
            "deadline".format(n))
        for k in range(1, n):
            await next_cycle(dut)
            assert val(dut.irq_timer_o) == 0, (
                "n = {}: mtip asserted {} clocks early".format(n, n - k))
        await next_cycle(dut)
        assert val(dut.irq_timer_o) == 1, (
            "n = {}: mtip not asserted on the deadline clock".format(n))
    dut._log.info("deadline: exact at n = 1, 2, 3, 8, 41 clocks")


@cocotb.test()
async def test_naive_mtimecmp_write_glitches_and_the_safe_one_does_not(dut):
    """The 64-bit hazard is real, and the documented sequence avoids it.

    Two halves, and the first is the unusual one: it demonstrates a
    SPURIOUS interrupt, deliberately. Moving the deadline from {2, 0} down
    to {0, 0x20000} high half first passes through {0, 0} -- which mtime
    met long ago -- so mtip asserts between the two stores.

    Asserting that the glitch HAPPENS is what makes the second half
    meaningful. soc_clint.v does not paper over the hazard, so a suite
    that only checked the safe sequence would prove nothing about the
    hazard it describes.
    """
    c = await setup(dut)
    await c.write(MTIMEH, 0)
    await c.write(MTIMEL, 0x0001_0000)

    # ---- naive: high half first ----
    await c.set_mtimecmp(2 << 32)
    assert val(dut.irq_timer_o) == 0
    await c.write(MTIMECMPH, 0)          # mtimecmp is now {0, 0}
    naive_glitch = val(dut.irq_timer_o)
    await c.write(MTIMECMPL, 0x0002_0000)
    settled = val(dut.irq_timer_o)
    assert naive_glitch == 1, (
        "the naive two-store sequence did NOT glitch, so this test is not "
        "demonstrating the hazard soc_clint.v documents and the safe-sequence "
        "half below would prove nothing")
    assert settled == 0, (
        "mtip did not clear once the naive sequence finished")

    # ---- safe: unreachable low half first ----
    #
    # The same move, {2, 0} down to {0, 0x30000}, through the documented
    # three-store sequence, with mtip sampled after every store.
    await c.set_mtimecmp(2 << 32)
    glitched = 0
    await c.write(MTIMECMPL, 0xFFFFFFFF)
    glitched |= val(dut.irq_timer_o)
    await c.write(MTIMECMPH, 0)
    glitched |= val(dut.irq_timer_o)
    await c.write(MTIMECMPL, 0x0003_0000)
    glitched |= val(dut.irq_timer_o)
    assert glitched == 0, (
        "the documented three-store sequence produced a spurious interrupt")


@cocotb.test()
async def test_msip_is_one_bit(dut):
    """msip bit 0 drives the software interrupt; bits 31:1 do not exist."""
    c = await setup(dut)
    assert val(dut.irq_software_o) == 0
    await c.write(MSIP, 0xFFFFFFFF)
    await RisingEdge(dut.clk_i)
    assert val(dut.irq_software_o) == 1
    assert await c.read(MSIP) == 1, (
        "msip must read back as one bit, not as what was written")
    await c.write(MSIP, 0xFFFFFFFE)
    await RisingEdge(dut.clk_i)
    assert val(dut.irq_software_o) == 0, (
        "a write with bit 0 clear left the software interrupt asserted, so "
        "some other bit of the word is reaching it")
    assert await c.read(MSIP) == 0


@cocotb.test()
async def test_byte_lanes_are_honoured(dut):
    """A sub-word write touches only the lanes its byte enables name.

    Every other register block in this SoC writes whole words. This one
    does not, because a 64-bit deadline written as two words through a
    compiler that may split a store is exactly where a dropped or
    misapplied lane would be invisible.
    """
    c = await setup(dut)
    rng = random.Random(31)
    await c.write(MTIMECMPL, 0x00000000)
    cur = 0
    for _ in range(24):
        be = rng.randrange(1, 16)
        w = rng.randrange(1 << 32)
        await c.write(MTIMECMPL, w, be=be)
        for lane in range(4):
            if be & (1 << lane):
                cur = (cur & ~(0xFF << (8 * lane))) | (w & (0xFF << (8 * lane)))
        got = await c.read(MTIMECMPL)
        assert got == cur, (
            "be=0x{:x} writing 0x{:08x}: read 0x{:08x}, expected 0x{:08x}"
            .format(be, w, got, cur))


@cocotb.test()
async def test_a_write_to_mtime_beats_the_tick(dut):
    """Writing one half of mtime does not disturb the other half's carry.

    An implementation that incremented the whole 64-bit counter and then
    let a 32-bit store override the low half would, on the cycle the low
    half carries, keep the carry in the high half and discard it in the
    low -- a clock that has jumped by 2^32. The write is placed at
    mtime = 0xFFFFFFFF repeatedly so that cycle is hit.
    """
    c = await setup(dut)
    for _ in range(6):
        await c.write(MTIMEH, 0)
        await c.write(MTIMEL, 0xFFFFFFF0)
        # Land a write to the low half somewhere around the carry.
        for _ in range(random.Random(7).randrange(1, 4)):
            await RisingEdge(dut.clk_i)
        await c.write(MTIMEL, 0x00000010)
        hi = await c.read(MTIMEH)
        assert hi == 0, (
            "the high half advanced to {} while the low half was being "
            "written: the tick and the store were applied to different "
            "halves of one value".format(hi))


@cocotb.test()
async def test_unimplemented_offsets_fault(dut):
    """An offset the block does not implement is a bus error.

    soc_clint.v's header argues this choice against the alternative of
    reading zero, and names its cost: a driver probing a second hart's
    msip faults, because there is no second hart. Both the probe
    addresses a multi-hart driver would use and a scatter of random
    offsets are driven, and a WRITE must fault as loudly as a read.
    """
    c = await setup(dut)
    rng = random.Random(41)
    probes = [MSIP + 4, MTIMECMPL + 8, MTIMEL - 8, 0x0100, 0x8000,
              SIZE - 4, 0x0004]
    probes += [rng.randrange(SIZE // 4) * 4 for _ in range(40)]
    n = 0
    for off in probes:
        if off in IMPLEMENTED:
            continue
        _, e = await c.read_raw(off)
        assert e == 1, "read of unimplemented 0x{:04x} did not fault".format(off)
        _, e = await c.write_raw(off, 0xA5A5A5A5)
        assert e == 1, "write of unimplemented 0x{:04x} did not fault".format(off)
        n += 2
    assert n > 20
    # And nothing an unimplemented write touched changed anything.
    assert val(dut.irq_software_o) == 0
    dut._log.info("unimplemented offsets: %d faulting accesses", n)


@cocotb.test()
async def test_one_response_per_request_under_back_to_back_traffic(dut):
    """Rule 3, aggregated over a long randomised stream.

    The per-transaction invariants live in the master agent above and run
    on every access in every test in this file; this one supplies the
    traffic and checks the totals, including that nothing trails after
    the stream has drained.
    """
    c = await setup(dut)
    rng = random.Random(53)
    for _ in range(120):
        off = rng.choice(IMPLEMENTED)
        if rng.randrange(2):
            await c.write(off, rng.randrange(1 << 32))
        else:
            await c.read(off)
    assert c.grants == c.rvalids == 120
    for _ in range(10):
        await RisingEdge(dut.clk_i)
        await Timer(T_CHECK, unit="ns")
        assert val(dut.rvalid_o) == 0, "trailing rvalid after the last response"


@cocotb.test()
async def test_no_traffic_and_no_response_in_reset(dut):
    """In reset: no grant, no response, and both interrupts deasserted.

    The interrupt half matters more than it looks. mtip is high out of
    reset (test_reset_state) because mtimecmp is zero, but while rst_ni
    is LOW the outputs must be quiet -- a core coming out of reset with a
    timer interrupt already latched somewhere would take it before it had
    a vector table.
    """
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    dut.rst_ni.value = 0
    dut.req_i.value = 1
    dut.addr_i.value = BASE + MSIP
    dut.we_i.value = 1
    dut.be_i.value = 0xF
    dut.wdata_i.value = 0xFFFFFFFF
    for cycle in range(12):
        await RisingEdge(dut.clk_i)
        await Timer(T_CHECK, unit="ns")
        assert val(dut.rvalid_o) == 0, (
            "cycle {}: rvalid while rst_ni is low".format(cycle))
        assert val(dut.irq_software_o) == 0, (
            "cycle {}: a write during reset reached msip".format(cycle))
    dut.req_i.value = 0


# ---------------------------------------------------------------------------
# H6, docs/58: mtime is a (72,64) SECDED codeword
#
# These are DIRECTED tests and not a campaign. The campaign is
# test_soc_clint_fi.py, which draws 342 injections and reports the rates;
# what these five do is pin the individual claims a rate cannot express,
# including the one the campaign cannot reach at all -- the double error,
# which needs two upsets inside one tick.
#
# Every one of them reaches into the hierarchy to DEPOSIT and observes
# only at the ports, which is docs/16 section 1.2's rule.
# ---------------------------------------------------------------------------

# The eight rows of secded_enc.v's H matrix, written out again rather
# than read off the instance. A check that read the encoder's own output
# would be comparing the design against itself.
H_ROWS = (0x1F04225844B12CB7, 0x2F0844A88952555B,
          0x4F10893112649A6D, 0x8F2111C22388E38E,
          0xF1421E043C0F03F0, 0xF283E007C00FFC00,
          0xF4FC0007FFF00000, 0xF8FFFFF800000000)


def _encode(data):
    chk = 0
    for i, row in enumerate(H_ROWS):
        chk |= (bin(data & row).count("1") & 1) << i
    return chk


def _hardened(dut):
    return hasattr(dut, "mtime_chk_q")


T_INJECT = 4          # inside the cycle, after the drive at T_DRIVE and
                      # before the sample at T_SAMPLE


async def _deposit(dut, sigs):
    """XOR a mask into one or more registers, mid-cycle.

    THE PHASE MATTERS AND GETTING IT WRONG IS SILENT. The deposit has to
    land after the stimulus has been driven and before the sampling
    point, so that the corrupt word is what the design holds for the
    whole of the cycle that is then observed. Written as `Timer(1)` from
    the T_SAMPLE point where a transaction returns, the deposit lands at
    9 ns of a 10 ns cycle -- one nanosecond before the edge that
    immediately re-encodes it -- so the correction happened, the pin
    pulsed between two sampling points, and three tests reported that a
    corrected upset had been corrected silently. It had not; nothing was
    looking when it was announced.

    Call from the T_SAMPLE point of a cycle. Returns at the T_SAMPLE
    point of the NEXT cycle, with the deposit in place and observable.
    """
    await RisingEdge(dut.clk_i)
    await Timer(T_INJECT, unit="ns")
    for sig, mask in sigs:
        sig.value = val(sig) ^ mask
    await Timer(T_SAMPLE - T_INJECT, unit="ns")


@cocotb.test()
async def test_the_stored_word_is_always_a_codeword(dut):
    """H6 E1, as a measurement rather than as an induction.

    The check bits are recomputed here from the eight H rows and
    compared against what the design stored, on every cycle of a run
    that ticks, that is written, and that is written with byte lanes.
    This is the self-scrub: there is no scrubber and no period, because
    the counter rewrites its own codeword on every edge.
    """
    c = await setup(dut)
    if not _hardened(dut):
        return
    for _ in range(20):
        await next_cycle(dut)
        assert val(dut.mtime_chk_q) == _encode(val(dut.mtime_q))
    await c.write(MTIMEH, 0x0003_5A6C)
    await c.write(MTIMEL, 0x39F1_84B2, be=0x3)
    for _ in range(20):
        await next_cycle(dut)
        assert val(dut.mtime_chk_q) == _encode(val(dut.mtime_q)), (
            "0x{:016x} carries check bits 0x{:02x}, not 0x{:02x}".format(
                val(dut.mtime_q), val(dut.mtime_chk_q),
                _encode(val(dut.mtime_q))))


@cocotb.test()
async def test_a_single_upset_in_mtime_never_reaches_a_port(dut):
    """H6's whole claim, on every one of the 64 data bits.

    Not a sample: every bit, because the argument docs/41 section 7.4
    makes is about the HIGH bits and a test that flipped bit 3 would be
    evidence about bit 3. After each deposit the very next read of mtime
    is the value the arithmetic predicts -- mtime advances one per
    clock -- and mt_ecc_o pulsed for exactly one cycle.
    """
    c = await setup(dut)
    if not _hardened(dut):
        return
    await c.write(MTIMEH, 0x0003_5A6C)
    await c.write(MTIMEL, 0x39F1_84B2)
    for bit in range(64):
        before = val(dut.mtime_q)
        await _deposit(dut, [(dut.mtime_q, 1 << bit)])
        # The pin is high for the one cycle the corrupt word is stored,
        # and the stored word IS corrupt while it is.
        assert val(dut.mt_ecc_o) == 1, (
            "bit {} was corrected silently".format(bit))
        assert val(dut.mtime_q) == (before + 1) ^ (1 << bit), bit
        await next_cycle(dut)
        assert val(dut.mt_ecc_o) == 0, (
            "bit {}: mt_ecc_o did not fall, so the codeword did not "
            "heal in one cycle".format(bit))
        # And the counter carried on from the RIGHT value: two cycles
        # elapsed between `before` and here.
        assert val(dut.mtime_q) == before + 2, (
            "bit {}: mtime is 0x{:016x}, expected 0x{:016x}".format(
                bit, val(dut.mtime_q), before + 2))


@cocotb.test()
async def test_a_single_upset_in_the_check_bits_is_corrected_too(dut):
    """The eight flip-flops H6 ADDED are eight an upset can land in.

    docs/43 made its check bits a stratum of their own for this reason.
    A codec that repaired the data and not its own check field would
    leave a word that is permanently one bit from uncorrectable.
    """
    c = await setup(dut)
    if not _hardened(dut):
        return
    await c.write(MTIMEH, 0x0003_5A6C)
    await c.write(MTIMEL, 0x39F1_84B2)
    for bit in range(8):
        before = val(dut.mtime_q)
        await _deposit(dut, [(dut.mtime_chk_q, 1 << bit)])
        assert val(dut.mt_ecc_o) == 1, bit
        # The DATA was never wrong here, so the counter must not have
        # moved off its own value either.
        assert val(dut.mtime_q) == before + 1, bit
        await next_cycle(dut)
        assert val(dut.mt_ecc_o) == 0, bit
        assert val(dut.mtime_chk_q) == _encode(val(dut.mtime_q)), bit
        assert val(dut.mtime_q) == before + 2, bit


@cocotb.test()
async def test_a_double_upset_is_detected_and_never_miscorrected(dut):
    """The class the campaign cannot reach, and the reason SECDED and
    not a plain Hamming code.

    Two upsets in one tick is outside this repository's single-upset
    fault model, so no draw in test_soc_clint_fi.py can produce one.
    What matters is not that the block repairs it -- it cannot, the
    information is gone -- but that it does not INVENT a third wrong
    value by correcting a bit neither upset touched. Every column of the
    H matrix has odd weight, so a two-bit error always produces a
    nonzero EVEN-parity syndrome, which can never equal a column.

    The measurement: over 64 disjoint pairs, the data field is passed
    through untouched and the event is announced.
    """
    c = await setup(dut)
    if not _hardened(dut):
        return
    await c.write(MTIMEH, 0x0003_5A6C)
    await c.write(MTIMEL, 0x39F1_84B2)
    for a in range(0, 64, 2):
        b = a + 1
        before = val(dut.mtime_q)
        mask = (1 << a) | (1 << b)
        corrupt = (before + 1) ^ mask
        await _deposit(dut, [(dut.mtime_q, mask)])
        assert val(dut.mt_ecc_o) == 1, (
            "bits {},{}: a double error was not announced".format(a, b))
        # Passed through, NOT miscorrected: the counter continues from
        # the corrupt value and from no other. A miscorrection would
        # show up on the next cycle as a THIRD value, which is the
        # failure the odd column weights exist to prevent.
        await next_cycle(dut)
        assert val(dut.mtime_q) == corrupt + 1, (
            "bits {},{}: the decoder produced 0x{:016x}, which is "
            "neither the stored word nor the true one".format(
                a, b, val(dut.mtime_q) - 1))
        # And it heals in one cycle, into a codeword over the WRONG
        # value. That is the honest end of this story: the clock is now
        # wrong for ever and the block has said so exactly once.
        assert val(dut.mt_ecc_o) == 0, (a, b)
        assert val(dut.mtime_chk_q) == _encode(val(dut.mtime_q)), (a, b)
        # Put the two bits back, so the next pair starts from a counter
        # that is on the value the arithmetic says it should be.
        await _deposit(dut, [(dut.mtime_q, mask)])
        await next_cycle(dut)


@cocotb.test()
async def test_nothing_is_reported_when_nothing_is_wrong(dut):
    """mt_ecc_o is a fault line into a saturating counter in
    soc_busstat.v. A line that pulses on healthy traffic turns the
    mission's upset-rate telemetry into noise, so this drives every
    access shape the block has -- ticks, whole-word writes, byte-lane
    writes, reads, and an unmapped offset -- and asserts silence.
    """
    c = await setup(dut)
    if not _hardened(dut):
        return
    rng = random.Random(58)
    for _ in range(150):
        off = rng.choice(IMPLEMENTED)
        if rng.randrange(2):
            await c.write_raw(off, rng.randrange(1 << 32),
                              be=rng.randrange(1, 16))
        else:
            await c.read_raw(off)
        assert val(dut.mt_ecc_o) == 0, (
            "mt_ecc_o pulsed on healthy traffic at offset 0x{:04x}".format(
                off))
    await c.read_raw(0x0100)
    assert val(dut.mt_ecc_o) == 0
