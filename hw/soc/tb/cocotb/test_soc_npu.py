"""cocotb suite for hw/soc/rtl/soc_npu.v -- the CPU-side NPU interface
with the frozen pilot behind it.

WHAT IS UNDER TEST AND WHAT IS NOT
----------------------------------
The device under test is `soc_npu`, which INSTANTIATES hw/rtl/pilot_top.v
unmodified. So the pilot is in the loop and is not a model of one: every
register value below travels a real 40-bit serial frame into the frozen
submission and back, and every event travels either the parallel AER pins
or that same frame.

The pilot's OWN behaviour is not this suite's subject. hw/tb/test_pilot_top.py
covers it through the Tiny Tapeout pins and is the place a defect in the
die belongs. What is checked here is the CONNECTION: that the window
presents the architecture's register map at the architecture's offsets,
that reserved addresses fault, that the fabric slave contract is kept,
that the event port carries the docs/10 section 7.1 event stream in both
directions, and that the interrupt means what the register map says.

WHERE THE EXPECTATIONS COME FROM
--------------------------------
Nothing here is read out of hw/soc/rtl/soc_npu.v except the port names.

  - node register offsets, reset values and field positions come from
    sw/golden/regmap_gen.py, generated from regmap/regmap.yaml, which is
    the same single source that produces the die's own header;
  - the fabric slave contract is soc_bus.v's S1-S4, quoted in the
    docstrings that test it;
  - the serial frame format and its three host obligations are
    hw/rtl/pilot_top.v section 2, quoted where they are checked;
  - the inference answer is sw/golden/lif_core.py, the normative
    executable form of the docs/10 section 4 equations;
  - the NPUCFG block's own offsets are written here, because that block's
    register map has never been described anywhere else -- the same split
    docs/40 section 8.1 states for the CLINT and the GPTIMER.

WHAT THIS SUITE DOES NOT COVER
------------------------------
  - It never drives two masters, because soc_npu has one slave port. The
    arbitration consequence of a 172-cycle slave is a whole-SoC property
    and is measured there, not here.
  - It injects no upsets. The queues carry aer_fifo's parity and pointer
    voting; nothing here provokes either.
  - It runs at one geometry (8 x 8), one node, and SER_HALF = 2. The
    frame-length test is parameterised and the Makefile can raise
    SER_HALF, but no test sweeps it.
  - It says nothing about what happens if the die stops answering. There
    is no timeout in the transport, by design, and no test for one.

Run: cd hw/soc/tb/cocotb && make -f Makefile.soc_npu
"""

import os
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

ROOT = Path(__file__).resolve().parents[4]
for _p in (str(ROOT), str(ROOT / "sw")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from golden.lif_core import LIFConfig, LIFCore          # noqa: E402
from golden.memmap_gen import REGIONS                   # noqa: E402
from golden.regmap_gen import ADDR, FIELDS, RESET       # noqa: E402

CLK_NS = 10
T_DRIVE = 1     # every driver applies this cycle's stimulus here
T_SAMPLE = 8    # every monitor samples the settled cycle here

# Elaboration, from the Makefile. Every test that depends on one of these
# checks it against something the DUT reports, so a dropped override
# fails rather than silently testing the other configuration.
N_NODES = int(os.environ.get("SOC_NPU_NODES", "1"))
N_NEURONS = int(os.environ.get("SOC_NPU_NEURONS", "8"))
N_AXONS = int(os.environ.get("SOC_NPU_AXONS", "8"))
SER_HALF = int(os.environ.get("SOC_NPU_SER_HALF", "2"))
INJ_DEPTH = int(os.environ.get("SOC_NPU_INJ_DEPTH", "8"))
CAP_DEPTH = int(os.environ.get("SOC_NPU_CAP_DEPTH", "8"))

NPU_BASE = REGIONS["NPU"][0]

# NPUCFG's own map, hw/soc/rtl/soc_npu.v. Mirrored by
# hw/soc/tb/sw/soc_npucfg.h, which is the program's copy.
C_ID, C_VERSION, C_CTRL, C_STATUS = 0x000, 0x004, 0x008, 0x00C
C_IRQCAUSE, C_IRQMASK = 0x010, 0x014
C_EVQ_IN, C_EVQ_OUT, C_EVQ_STAT = 0x018, 0x01C, 0x020
C_GEOM, C_CNT, C_CNT_DROP = 0x024, 0x028, 0x02C
C_UNIMPL = 0x800

CTRL_IN_EN, CTRL_OUT_EN, CTRL_FLUSH, CTRL_SCRUB = 1, 2, 4, 8
ST_SER_BUSY, ST_INJ_EMPTY, ST_INJ_FULL = 1 << 0, 1 << 1, 1 << 2
ST_CAP_EMPTY, ST_CAP_FULL, ST_IN_RDY = 1 << 3, 1 << 4, 1 << 5
ST_OUT_VLD, ST_NODE_BUSY, ST_NODE_ERR = 1 << 6, 1 << 7, 1 << 8
CAUSE_EVT, CAUSE_ERR = 1 << 0, 1 << 1
CAUSE_DED, CAUSE_INJ_OVF, CAUSE_FETCH_ER = 1 << 3, 1 << 5, 1 << 6
EVQ_VALID = 1 << 31

# docs/10 section 7.1
TYPE_SPIKE, TYPE_TICK, TYPE_SYNC = 0 << 14, 1 << 14, 2 << 14


def node(n, off):
    """docs/10 section 8 item 5: one register block per node at a
    per-node base address, 4 KiB apart."""
    return NPU_BASE + (n << 12) + off


# ---------------------------------------------------------------------------
# Bus drivers
# ---------------------------------------------------------------------------
class Env:
    """The two bus faces, driven to soc_bus.v's contract and to AMBA 3 APB."""

    def __init__(self, dut):
        self.dut = dut

    async def reset(self):
        d = self.dut
        cocotb.start_soon(Clock(d.clk_i, CLK_NS, unit="ns").start())
        d.rst_ni.value = 0
        d.req_i.value = 0
        d.addr_i.value = 0
        d.we_i.value = 0
        d.be_i.value = 0xF
        d.wdata_i.value = 0
        d.psel_i.value = 0
        d.penable_i.value = 0
        d.paddr_i.value = 0
        d.pwrite_i.value = 0
        d.pwdata_i.value = 0
        for _ in range(6):
            await RisingEdge(d.clk_i)
        d.rst_ni.value = 1
        for _ in range(4):
            await RisingEdge(d.clk_i)

    # ---- fabric slave port, the node register window --------------------
    #
    # THE CYCLE CONVENTION, which this repository has been bitten by once
    # already (docs/40 section 7.5): T_DRIVE and T_SAMPLE are offsets
    # INTO a cycle, applied after a RisingEdge, and a coroutine must
    # never accumulate them. Every loop below ends its iteration at
    # T_SAMPLE and re-enters on the next RisingEdge, so the phase is
    # reset by the clock rather than carried.
    async def bus(self, addr, we=0, wdata=0, be=0xF, limit=4000):
        """One Ibex-native transaction. Returns (rdata, err, cycles).

        Rule 1: drive a valid address and assert req; the slave answers
        with gnt when it is ready, which may be any number of cycles
        later. Rule 3: exactly one rvalid per granted request, carrying
        rdata and err in that cycle.

        `cycles` counts from the cycle req was first asserted to the
        cycle rvalid returned, which is the measurement the latency test
        uses.
        """
        d = self.dut
        await RisingEdge(d.clk_i)
        await Timer(T_DRIVE, unit="ns")
        d.req_i.value = 1
        d.addr_i.value = addr
        d.we_i.value = we
        d.wdata_i.value = wdata
        d.be_i.value = be

        # THE GRANT CAN BE IN THE SAME CYCLE AS THE REQUEST, because
        # gnt_o is combinational on req_i -- rule 1 says "the same cycle
        # or any number of cycles later" and this slave takes the first
        # option when it is idle. A driver that starts looking on the
        # NEXT cycle misses it, holds req high through the whole frame,
        # and is then granted a SECOND transaction the moment the first
        # response returns. Measured while writing this suite: one read
        # became two frames and 350 cycles where the design does one and
        # 176, and every symptom of it read as a design defect.
        cycles = 0
        while True:
            await Timer(T_SAMPLE - T_DRIVE, unit="ns")
            cycles += 1
            if d.gnt_o.value:
                break
            assert cycles < limit, f"no grant at 0x{addr:08x} in {limit} cycles"
            await RisingEdge(d.clk_i)
            await Timer(T_DRIVE, unit="ns")

        # Rule 2: after a grant the address, wdata, we and be MAY CHANGE
        # in the next cycle -- the slave is assumed to have captured
        # them. Dropping the payload here rather than holding it is what
        # makes S2 a tested property of this slave instead of an
        # assumption about it.
        await RisingEdge(d.clk_i)
        await Timer(T_DRIVE, unit="ns")
        d.req_i.value = 0
        d.addr_i.value = 0xDEADBEEF
        d.we_i.value = 0
        d.wdata_i.value = 0xDEADBEEF
        d.be_i.value = 0x0

        # Rule 3 forbids a response in the grant cycle, so the search
        # for rvalid starts here.
        while True:
            await Timer(T_SAMPLE - T_DRIVE, unit="ns")
            cycles += 1
            if d.rvalid_o.value:
                return int(d.rdata_o.value), int(d.err_o.value), cycles
            assert cycles < limit, f"no rvalid at 0x{addr:08x} in {limit} cycles"
            await RisingEdge(d.clk_i)
            await Timer(T_DRIVE, unit="ns")

    async def nrd(self, off, n=0):
        rd, er, _ = await self.bus(node(n, off))
        assert not er, f"node {n} offset 0x{off:03x} answered with an error"
        return rd

    async def nwr(self, off, val, n=0):
        _, er, _ = await self.bus(node(n, off), we=1, wdata=val)
        assert not er, f"node {n} offset 0x{off:03x} answered with an error"

    # ---- APB slave port, the NPUCFG slot --------------------------------
    async def apb(self, off, we=0, wdata=0):
        """One AMBA 3 APB transfer: SETUP for exactly one cycle, then
        ACCESS until PREADY, with PSLVERR sampled only in the PREADY
        cycle."""
        d = self.dut
        await RisingEdge(d.clk_i)
        await Timer(T_DRIVE, unit="ns")
        d.psel_i.value = 1
        d.penable_i.value = 0
        d.paddr_i.value = off
        d.pwrite_i.value = we
        d.pwdata_i.value = wdata
        await RisingEdge(d.clk_i)
        await Timer(T_DRIVE, unit="ns")
        d.penable_i.value = 1
        while True:
            await Timer(T_SAMPLE - T_DRIVE, unit="ns")
            if d.pready_o.value:
                rd = int(d.prdata_o.value)
                er = int(d.pslverr_o.value)
                break
            await RisingEdge(d.clk_i)
            await Timer(T_DRIVE, unit="ns")
        await RisingEdge(d.clk_i)
        await Timer(T_DRIVE, unit="ns")
        d.psel_i.value = 0
        d.penable_i.value = 0
        return rd, er

    async def crd(self, off):
        rd, er = await self.apb(off)
        assert not er, f"NPUCFG offset 0x{off:03x} answered with PSLVERR"
        return rd

    async def cwr(self, off, val):
        _, er = await self.apb(off, we=1, wdata=val)
        assert not er, f"NPUCFG offset 0x{off:03x} answered with PSLVERR"


# ---------------------------------------------------------------------------
# 1. The transport, and the map it carries
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_the_window_reports_the_architecture_identity(dut):
    """A read through the window is a read of docs/10 section 10.

    ID and VERSION are the discovery words regmap/regmap.yaml puts at the
    base of every node block, and their reset values come from that file
    through the generated golden model. A window that answered with
    anything of its own -- zero, the address, a controller identity --
    fails here.
    """
    env = Env(dut)
    await env.reset()
    assert await env.nrd(ADDR["ID"]) == RESET["ID"]
    assert await env.nrd(ADDR["VERSION"]) == RESET["VERSION"]


@cocotb.test()
async def test_every_reset_value_survives_the_transport(dut):
    """Every readable node register reads its reset value.

    This is the transport's real test: 40 bits shifted each way, per
    register, against a table nothing in the RTL produced. A frame that
    was one bit short, one bit long, sampled on the wrong edge or
    misaligned by a deselect that was never seen would corrupt SOME of
    these and not others, which is why the whole map is walked rather
    than one register.

    Two documented divergences, both hw/rtl/pilot_top.v deviation D2:
    CFG_NEUR is read-only and reports N_NEURONS rather than its
    architectural reset, and CFG_AXON resets to N_AXONS for the same
    reason. They are checked against the geometry instead of being
    skipped.
    """
    env = Env(dut)
    await env.reset()

    # W_BASE and PASS_ID are not implemented in the pilot (its header,
    # section 3): they are multi-pass bookkeeping with no hardware effect
    # in a single-pass build and read as zero like any unmapped offset.
    # WO registers have no read value to compare.
    # N_DATA is excluded and the reason is normative rather than
    # convenient: docs/10 section 3 says the neuron state memory is NOT
    # cleared by reset and its content after reset is UNDEFINED, so
    # there is no value to compare against until CTRL.STATE_CLR has run.
    # A suite that asserted a value here would be asserting something
    # the specification refuses to promise.
    skip = {"W_BASE", "PASS_ID", "W_DATA_LO", "W_DATA_HI", "ECC_INJ",
            "N_DATA"}
    override = {"CFG_NEUR": N_NEURONS, "CFG_AXON": N_AXONS}

    checked = 0
    for name, off in sorted(ADDR.items()):
        if name in skip:
            continue
        want = override.get(name, RESET[name])
        got = await env.nrd(off)
        assert got == want, (
            f"{name} at 0x{off:03x}: read 0x{got:08x}, "
            f"regmap says 0x{want:08x}")
        checked += 1
    dut._log.info("%d node registers read their reset value through the "
                  "serial transport", checked)
    assert checked >= 20


@cocotb.test()
async def test_a_write_reaches_the_die_and_reads_back(dut):
    """SCRATCH is the register the map defines for exactly this.

    regmap/regmap.yaml: "Read/write test register, no side effects". A
    round trip through it exercises the write half of the frame -- the
    command byte's WR bit, 32 bits of MOSI, and the commit on the 40th
    rising edge -- which no read can.
    """
    env = Env(dut)
    await env.reset()
    for pattern in (0xA5A50F0F, 0x5A5AF0F0, 0xFFFFFFFF, 0x00000000,
                    0x00000001, 0x80000000):
        await env.nwr(ADDR["SCRATCH"], pattern)
        got = await env.nrd(ADDR["SCRATCH"])
        assert got == pattern, (
            f"SCRATCH round trip: wrote 0x{pattern:08x}, read 0x{got:08x}")


@cocotb.test()
async def test_a_write_to_a_read_only_register_is_refused(dut):
    """The window does not add write capability the die does not have.

    ID is RO in regmap/regmap.yaml. A transport that turned a store into
    something the die accepted would be inventing a register map.
    """
    env = Env(dut)
    await env.reset()
    await env.nwr(ADDR["ID"], 0xDEADBEEF)
    assert await env.nrd(ADDR["ID"]) == RESET["ID"]


# ---------------------------------------------------------------------------
# 2. The fabric slave contract, soc_bus.v S1-S4
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_gnt_is_withheld_while_a_frame_is_in_flight(dut):
    """S4 permits a slave to accept one request at a time, and this one
    does. What must not happen is a SECOND grant while the first
    transaction is unanswered.

    THE REQUEST IS HELD HIGH FOR THE WHOLE FRAME, deliberately. A test
    that dropped req as soon as it saw the grant would never present the
    slave with the opportunity to misbehave -- and it did not: the
    mutation `gnt_o = req_i` passed all 21 tests until this one was
    rewritten. A grant the fabric records owes an rvalid the slave never
    sends, which underflows soc_bus.v's per-slave ownership queue.
    """
    env = Env(dut)
    await env.reset()
    d = dut

    await RisingEdge(d.clk_i)
    await Timer(T_DRIVE, unit="ns")
    d.req_i.value = 1
    d.addr_i.value = node(0, ADDR["ID"])
    d.we_i.value = 0

    # THE PROPERTY IS AN OUTSTANDING COUNT, not a grant count. With the
    # request held high the slave legitimately starts a SECOND
    # transaction in the cycle it answers the first -- gnt and rvalid may
    # coincide, they belong to different transactions, and
    # soc_apb_bridge.v's header says the same of itself. What must never
    # happen is a grant while a response is still owed.
    grants = 0
    rvalids = 0
    worst = 0
    for _ in range(2000):
        await Timer(T_SAMPLE - T_DRIVE, unit="ns")
        if d.rvalid_o.value:
            rvalids += 1
        if d.gnt_o.value:
            grants += 1
        worst = max(worst, grants - rvalids)
        await RisingEdge(d.clk_i)
        await Timer(T_DRIVE, unit="ns")
        if rvalids >= 3:
            break
    else:
        raise AssertionError("no responses while req was held high")

    assert worst == 1, (
        "{} transactions outstanding at once; the slave accepted a "
        "request it cannot hold".format(worst))
    assert grants - rvalids <= 1

    await RisingEdge(d.clk_i)
    await Timer(T_DRIVE, unit="ns")
    d.req_i.value = 0


@cocotb.test()
async def test_exactly_one_rvalid_per_grant_over_many_frames(dut):
    """Rule 3, counted rather than assumed, over a run of transactions."""
    env = Env(dut)
    await env.reset()
    d = dut
    seen = {"g": 0, "r": 0}

    async def watch():
        while True:
            await RisingEdge(d.clk_i)
            await Timer(T_SAMPLE, unit="ns")
            if d.gnt_o.value:
                seen["g"] += 1
            if d.rvalid_o.value:
                seen["r"] += 1

    cocotb.start_soon(watch())
    n = 8
    for _ in range(n):
        await env.nrd(ADDR["ID"])
    await RisingEdge(d.clk_i)
    assert seen["g"] == n, seen
    assert seen["r"] == n, seen


@cocotb.test()
async def test_the_frame_costs_what_the_protocol_says_it_costs(dut):
    """Measure the register-access latency; do not quote it.

    hw/rtl/pilot_top.v section 2 fixes the frame at 40 SER_SCK cycles and
    host obligations H2 and H3 add one full SER_SCK period of select
    setup and one of inter-frame gap. At SER_HALF clk cycles per half
    period that is at least (40 + 1 + 1) * 2 * SER_HALF clock cycles of
    serial activity, and the state machine around it adds a small
    constant.

    The bound below is the protocol's own arithmetic with generous slack
    on the constant. What the test is really for is that the number is
    MEASURED, so docs/51 quotes an observation.
    """
    env = Env(dut)
    await env.reset()
    floor = (40 + 1 + 1) * 2 * SER_HALF
    _, er, cycles = await env.bus(node(0, ADDR["ID"]))
    assert not er
    assert floor <= cycles <= floor + 24, (
        f"a register access took {cycles} cycles; the protocol floor at "
        f"SER_HALF={SER_HALF} is {floor}")
    dut._log.info("one node register access: %d clock cycles at SER_HALF=%d",
                  cycles, SER_HALF)


@cocotb.test()
async def test_reserved_addresses_in_the_window_are_bus_errors(dut):
    """"Reserved" is a property, not a comment.

    The frozen map gives the NPU 256 MiB. This block implements sixteen
    4 KiB node windows in the low 64 KiB of it and instantiates N_NODES
    of them. Everything else -- absent nodes, offsets above the die's
    7-bit register address, the descriptor-ring area docs/08 section 3.1
    sketches -- must answer err and not zero, which is the rule soc_bus.v
    applies to an unmapped address and soc_top.v to an empty slot.
    """
    env = Env(dut)
    await env.reset()

    bad = [(node(N_NODES, ADDR["ID"]), "the first node that is not there"),
           (node(15, ADDR["ID"]), "node 15"),
           (NPU_BASE + 0x200, "above the die's 7-bit register address"),
           (NPU_BASE + 0xFFC, "the top of node 0's 4 KiB window"),
           (NPU_BASE + 0x10000, "above the node windows"),
           (NPU_BASE + 0x08000000, "the descriptor-ring area"),
           (NPU_BASE + 0x0FFFFFFC, "the last word of the region")]
    for addr, what in bad:
        rd, er, _ = await env.bus(addr)
        assert er, f"{what} (0x{addr:08x}) did not answer with an error"
        assert rd == 0, f"{what} returned data as well as an error"

    # And the addresses that must NOT fault, so the test above is not
    # passing by faulting everything.
    for off in (ADDR["ID"], ADDR["EVQ_STAT"], 0x1FC):
        _, er, _ = await env.bus(node(0, off))
        assert not er, f"node 0 offset 0x{off:03x} faulted"


@cocotb.test()
async def test_a_partial_write_is_refused(dut):
    """The serial frame is 32 bits wide and carries no byte enable.

    A slave that accepted a sub-word store would have to widen it, which
    writes three bytes of a register the master never named. It faults
    instead. Reads are not restricted: a byte load reads the whole word
    and the core extracts the lane.
    """
    env = Env(dut)
    await env.reset()
    await env.nwr(ADDR["SCRATCH"], 0x12345678)
    for be in (0x1, 0x3, 0xC, 0xE):
        _, er, _ = await env.bus(node(0, ADDR["SCRATCH"]), we=1,
                                 wdata=0xFFFFFFFF, be=be)
        assert er, f"a store with be=0x{be:x} was accepted"
    assert await env.nrd(ADDR["SCRATCH"]) == 0x12345678, \
        "a refused partial store changed the register anyway"

    # A misaligned address is refused for the same reason.
    for a in (1, 2, 3):
        _, er, _ = await env.bus(node(0, ADDR["SCRATCH"]) + a, we=1,
                                 wdata=0xFFFFFFFF)
        assert er, f"a store at +{a} was accepted"


# ---------------------------------------------------------------------------
# 3. NPUCFG, the fabric controller
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_npucfg_identity_and_geometry(dut):
    """The block reports what it was elaborated with.

    GEOM exists so that software does not have to be told the geometry by
    whoever built the SoC; this test is also the guard that the Makefile's
    parameters reached the design, which no exit status would show.
    """
    env = Env(dut)
    await env.reset()
    assert await env.crd(C_ID) == 0x4E505543          # "NPUC"
    assert await env.crd(C_VERSION) == 1
    geom = await env.crd(C_GEOM)
    assert geom & 0xFF == N_NODES
    assert (geom >> 8) & 0xFF == SER_HALF
    assert (geom >> 16) & 0xFF == INJ_DEPTH
    assert (geom >> 24) & 0xFF == CAP_DEPTH


@cocotb.test()
async def test_npucfg_reserved_offsets_are_slave_errors(dut):
    """An offset the block does not implement completes with PSLVERR.

    Same rule as soc_clint.v inside its own window: a reserved address is
    a bus error at the core, never a read of zero that looks like a
    working register. It must still COMPLETE, or the bridge hangs.
    """
    env = Env(dut)
    await env.reset()
    for off in (C_UNIMPL, 0x030, 0x100, 0xFFC):
        rd, er = await env.apb(off)
        assert er, f"NPUCFG offset 0x{off:03x} did not answer with PSLVERR"
        assert rd == 0
    for off in (C_ID, C_STATUS, C_EVQ_STAT):
        _, er = await env.apb(off)
        assert not er, f"NPUCFG offset 0x{off:03x} answered with PSLVERR"


@cocotb.test()
async def test_status_reports_the_dies_own_pins(dut):
    """STATUS is a window onto the die's fault and flow-control pins.

    hw/rtl/pilot_top.v section 1 makes BUSY, ERR, SEC, DED, TMR,
    AER_IN_RDY and AER_OUT_VLD real outputs, so an SoC does not have to
    poll a register over a 172-cycle transport to know the node's state.
    Out of reset the die is idle, has room for an event, has nothing to
    give and no fault.
    """
    env = Env(dut)
    await env.reset()
    st = await env.crd(C_STATUS)
    assert st & ST_IN_RDY, "the die reports its input queue full at reset"
    assert not st & ST_OUT_VLD
    assert not st & ST_NODE_BUSY
    assert not st & ST_NODE_ERR
    assert st & ST_INJ_EMPTY and st & ST_CAP_EMPTY
    assert not st & ST_SER_BUSY


# ---------------------------------------------------------------------------
# 4. The event port
# ---------------------------------------------------------------------------
CFG = LIFConfig(thresh=20, v_reset=-4, leak_shift=2, syn_shift=2,
                refr_period=2, leak_en=True)
FRAMES = [[0, 1], [2], [1, 1, 3], [], [0, 2, 3], [3]]


def make_weights(n_axons, n_neurons, seed=20260921):
    import random
    rng = random.Random(seed)
    return [[rng.randint(-8, 7) for _ in range(n_neurons)]
            for _ in range(n_axons)]


def pack_words(weights):
    flat = [w for row in weights for w in row]
    return [sum((w & 0xF) << (4 * k) for k, w in enumerate(flat[b:b + 16]))
            for b in range(0, len(flat), 16)]


async def bring_up(env, weights):
    """docs/10 section 11.1's order: state clear, configure, load, enable.
    Configuration registers are locked while BUSY, so the enable is last.
    """
    await env.nwr(ADDR["CTRL"], 1 << FIELDS["CTRL"]["STATE_CLR"])
    for _ in range(64):
        if not (await env.nrd(ADDR["STATUS"])) & (1 << FIELDS["STATUS"]["BUSY"]):
            break
    else:
        raise AssertionError("the state-clear sweep never finished")

    await env.nwr(ADDR["CFG_AXON"], N_AXONS)
    await env.nwr(ADDR["CFG_THRESH"], CFG.thresh & 0xFFFF)
    await env.nwr(ADDR["CFG_VRESET"], CFG.v_reset & 0xFFFF)
    await env.nwr(ADDR["CFG_LEAK"], CFG.leak_shift)
    await env.nwr(ADDR["CFG_SYNSHIFT"], CFG.syn_shift)
    await env.nwr(ADDR["CFG_REFR"], CFG.refr_period)
    await env.nwr(ADDR["CFG_FLAGS"], (1 if CFG.leak_en else 0) << 1)
    await env.nwr(ADDR["PASS_TILE_OFF"], 0)

    # Read back, because a configuration write that was refused -- the
    # lock, an out-of-range value, a decode into the wrong register --
    # is otherwise invisible until the arithmetic comes out wrong, and
    # then it looks like an arithmetic defect.
    for name, want in (("CFG_THRESH", CFG.thresh & 0xFFFF),
                       ("CFG_VRESET", CFG.v_reset & 0xFFFF),
                       ("CFG_LEAK", CFG.leak_shift),
                       ("CFG_SYNSHIFT", CFG.syn_shift),
                       ("CFG_REFR", CFG.refr_period)):
        got = await env.nrd(ADDR[name])
        assert got == want, f"{name} read back 0x{got:x}, wrote 0x{want:x}"

    await env.nwr(ADDR["W_ADDR"], 0)
    for w in pack_words(weights):
        await env.nwr(ADDR["W_DATA_LO"], w & 0xFFFFFFFF)
        await env.nwr(ADDR["W_DATA_HI"], (w >> 32) & 0xFFFFFFFF)
    assert await env.nrd(ADDR["CNT_SEC"]) == 0
    assert await env.nrd(ADDR["CNT_DED"]) == 0

    await env.nwr(ADDR["CTRL"], (1 << FIELDS["CTRL"]["EN"])
                  | (1 << FIELDS["CTRL"]["SCRUB_EN"]))


async def run_stream(env, frames, limit=200000):
    """Inject each frame and read until its barrier comes back.

    The stream is self-delimiting because of SYNC: docs/10 section 7.1
    says a consumed SYNC means every prior event is fully processed and
    the barrier is echoed. So this needs no timing knowledge, only the
    echo, which is exactly the property that makes the frame handshake
    worth carrying over the serial port when the pins cannot.
    """
    out = []
    for k, frame in enumerate(frames):
        for axon in frame:
            await env.cwr(C_EVQ_IN, TYPE_SPIKE | axon)
        await env.cwr(C_EVQ_IN, TYPE_TICK)
        await env.cwr(C_EVQ_IN, TYPE_SYNC | k)
        barrier = TYPE_SYNC | k
        spins = 0
        while True:
            w = await env.crd(C_EVQ_OUT)
            if w & EVQ_VALID:
                out.append(w & 0xFFFF)
                if (w & 0xFFFF) == barrier:
                    break
                spins = 0
            else:
                spins += 1
                assert spins < limit, f"frame {k}: the barrier never came back"
    return out


@cocotb.test()
async def test_inference_matches_the_golden_model(dut):
    """THE DEMONSTRATION, at block level.

    Configure the node, load its weights, push the docs/10 section 7.1
    event stream in through the event port, read the output stream back,
    and compare it against sw/golden/lif_core.py -- the normative form of
    the section 4 equations -- rather than against what the hardware
    produced.

    Everything is in the loop: the serial transport for configuration and
    for the barrier, the parallel AER pins for spikes and ticks, the
    die's ECC-checked weight loader, its queues, its LIF datapath, and
    the drain engine that reads the output words back over the serial
    EVQ_OUT register because the output pins carry no TYPE field.
    """
    env = Env(dut)
    await env.reset()
    weights = make_weights(N_AXONS, N_NEURONS)
    await bring_up(env, weights)
    await env.cwr(C_CTRL, CTRL_IN_EN | CTRL_OUT_EN)

    core = LIFCore(N_NEURONS, N_AXONS, weights, CFG)
    per_frame = core.run_frames(FRAMES)
    expect = []
    for k, spikes in enumerate(per_frame):
        expect += [TYPE_SPIKE | s for s in spikes]
        expect.append(TYPE_SYNC | k)

    assert sum(len(s) for s in per_frame) > 0, \
        "the stimulus must actually produce spikes to be worth running"

    got = await run_stream(env, FRAMES)
    assert got == expect, (
        "output stream\n  got  " + " ".join(f"{w:04x}" for w in got)
        + "\n  want " + " ".join(f"{w:04x}" for w in expect))

    # The whole neuron state file, which is strictly stronger than the
    # spike stream: it catches an error that happened to cancel.
    for j in range(N_NEURONS):
        await env.nwr(ADDR["N_ADDR"], j)
        word = await env.nrd(ADDR["N_DATA"])
        v = word & 0xFFFF
        v = v - 0x10000 if v >= 0x8000 else v
        r = (word >> 16) & 0xF
        assert (v, r) == core.get_state(j), (
            f"neuron {j}: rtl (V={v}, R={r}), golden {core.get_state(j)}")

    # Nothing lost on either side, counted by the hardware independently
    # of the stream this test collected.
    cnt = await env.crd(C_CNT)
    n_in = sum(len(f) + 2 for f in FRAMES)
    assert cnt & 0xFFFF == n_in, f"CNT injected {cnt & 0xFFFF}, sent {n_in}"
    assert (cnt >> 16) & 0xFFFF == len(expect)
    assert await env.crd(C_CNT_DROP) == 0
    assert await env.nrd(ADDR["CNT_EVQ_OVF"]) == 0
    assert await env.nrd(ADDR["CNT_AXON_OOR"]) == 0
    assert await env.crd(C_IRQCAUSE) & (CAUSE_ERR | CAUSE_DED
                                        | CAUSE_INJ_OVF
                                        | CAUSE_FETCH_ER) == 0


@cocotb.test()
async def test_a_spike_and_a_tick_go_over_the_pins(dut):
    """The inbound transport is the parallel port, and it is used.

    A SPIKE or a TICK is one rising edge of AER_IN_STB with the address
    and the type on their own pins, which is why the inbound direction
    costs a handful of cycles against the outbound direction's frame.
    The observation port makes the strobe visible without reaching into
    the hierarchy.
    """
    env = Env(dut)
    await env.reset()
    await env.cwr(C_CTRL, CTRL_IN_EN)

    strobes = {"n": 0}

    async def watch():
        prev = 0
        while True:
            await RisingEdge(dut.clk_i)
            await Timer(T_SAMPLE, unit="ns")
            cur = int(dut.obs_aer_in_stb_o.value)
            if cur and not prev:
                strobes["n"] += 1
            prev = cur

    cocotb.start_soon(watch())
    for w in (TYPE_SPIKE | 1, TYPE_SPIKE | 2, TYPE_TICK):
        await env.cwr(C_EVQ_IN, w)
    for _ in range(200):
        await RisingEdge(dut.clk_i)
    assert strobes["n"] == 3, (
        f"{strobes['n']} strobes for three pin-transported events")


@cocotb.test()
async def test_a_sync_cannot_go_over_the_pins_and_does_not(dut):
    """SYNC has no pin, so it takes the serial port.

    hw/rtl/pilot_top.v builds the pin event word's TYPE from AER_IN_TICK
    alone, so it is 00 or 01 and never 10. The barrier is therefore
    injected by writing the die's EVQ_IN register, and the evidence is
    that the strobe never moves while the chip select does.
    """
    env = Env(dut)
    await env.reset()
    await env.cwr(C_CTRL, CTRL_IN_EN)

    seen = {"stb": 0, "frames": 0}

    async def watch():
        prev_stb, prev_cs = 0, 1
        while True:
            await RisingEdge(dut.clk_i)
            await Timer(T_SAMPLE, unit="ns")
            stb = int(dut.obs_aer_in_stb_o.value)
            cs = int(dut.obs_ser_cs_n_o.value)
            if stb and not prev_stb:
                seen["stb"] += 1
            if prev_cs and not cs:
                seen["frames"] += 1
            prev_stb, prev_cs = stb, cs

    cocotb.start_soon(watch())
    await env.cwr(C_EVQ_IN, TYPE_SYNC | 0x2A)
    for _ in range(400):
        await RisingEdge(dut.clk_i)
    assert seen["stb"] == 0, "a SYNC was strobed onto the AER pins"
    assert seen["frames"] == 1, (
        f"{seen['frames']} serial frames for one SYNC injection")


async def enable_node(env):
    """The die's event pipeline is gated by CTRL.EN and its reset value
    is 0 (regmap/regmap.yaml). A test that injects without enabling is
    testing a node that is deliberately not listening."""
    await env.nwr(ADDR["CTRL"], 1 << FIELDS["CTRL"]["STATE_CLR"])
    for _ in range(64):
        if not (await env.nrd(ADDR["STATUS"])) & (1 << FIELDS["STATUS"]["BUSY"]):
            break
    await env.nwr(ADDR["CTRL"], 1 << FIELDS["CTRL"]["EN"])


@cocotb.test()
async def test_the_barrier_comes_back_with_its_own_id(dut):
    """SYNC in, SYNC out, and the ID field survives.

    The echo carries the consumed word, so a barrier can be labelled. The
    program uses that to delimit frames without counting spikes, and this
    is the property that makes it legitimate.
    """
    env = Env(dut)
    await env.reset()
    await enable_node(env)
    await env.cwr(C_CTRL, CTRL_IN_EN | CTRL_OUT_EN)
    for tag in (0, 1, 0x3FF, 0x155):
        await env.cwr(C_EVQ_IN, TYPE_SYNC | tag)
        for _ in range(4000):
            w = await env.crd(C_EVQ_OUT)
            if w & EVQ_VALID:
                break
        else:
            raise AssertionError(f"barrier {tag:#x} never came back")
        assert w & 0xFFFF == (TYPE_SYNC | tag), (
            f"barrier came back as 0x{w & 0xFFFF:04x}, sent "
            f"0x{TYPE_SYNC | tag:04x}")


@cocotb.test()
async def test_a_read_of_an_empty_capture_queue_reports_not_valid(dut):
    """regmap/regmap.yaml's EVQ_OUT contract, mirrored on this side.

    "b31 VALID, [15:0] event word", single access, show-ahead. An empty
    queue must say so rather than return a stale word with VALID set,
    which is the failure mode a holding register invites.
    """
    env = Env(dut)
    await env.reset()
    await enable_node(env)
    await env.cwr(C_CTRL, CTRL_IN_EN | CTRL_OUT_EN)
    for _ in range(4):
        assert await env.crd(C_EVQ_OUT) & EVQ_VALID == 0

    await env.cwr(C_EVQ_IN, TYPE_SYNC | 7)
    for _ in range(4000):
        w = await env.crd(C_EVQ_OUT)
        if w & EVQ_VALID:
            break
    assert w & 0xFFFF == (TYPE_SYNC | 7)
    # The pop is the read. A second read must not return it again.
    for _ in range(4):
        assert await env.crd(C_EVQ_OUT) & EVQ_VALID == 0


@cocotb.test()
async def test_the_injection_queue_refuses_and_counts_rather_than_hides(dut):
    """A refused injection is an EVENT and it is reported as one.

    With the engine disabled nothing drains the injection queue, so a
    burst longer than INJ_DEPTH overflows it. The write is refused, the
    drop is counted, and the sticky cause bit latches -- which is exactly
    the distinction docs/50 section 5.1 draws between a level with state
    behind it and an event with none.
    """
    env = Env(dut)
    await env.reset()
    await env.cwr(C_CTRL, 0)             # engine off: nothing drains

    over = 5
    for i in range(INJ_DEPTH + over):
        await env.cwr(C_EVQ_IN, TYPE_SPIKE | (i & 0xF))

    st = await env.crd(C_STATUS)
    assert st & ST_INJ_FULL, "the queue took more than INJ_DEPTH entries"
    assert await env.crd(C_CNT_DROP) == over, (
        f"CNT_DROP {await env.crd(C_CNT_DROP)}, expected {over}")
    assert await env.crd(C_IRQCAUSE) & CAUSE_INJ_OVF, \
        "an overflow that nothing recorded"

    # It is write-1-to-clear, and clearing it does not empty the queue.
    await env.cwr(C_IRQCAUSE, CAUSE_INJ_OVF)
    assert await env.crd(C_IRQCAUSE) & CAUSE_INJ_OVF == 0
    assert await env.crd(C_EVQ_STAT) & 0xFF == INJ_DEPTH


@cocotb.test()
async def test_flush_empties_the_queues_and_keeps_the_record(dut):
    """CTRL.FLUSH is the SoC-side analogue of the die's CTRL.SOFT_RST.

    The queues go back to empty; the sticky record of what went wrong
    does not. A recovery that erased the evidence of what it recovered
    from is the defect docs/16 section 5.1 named at the die, and this
    side must not reintroduce it.
    """
    env = Env(dut)
    await env.reset()
    await env.cwr(C_CTRL, 0)
    for i in range(INJ_DEPTH + 2):
        await env.cwr(C_EVQ_IN, TYPE_SPIKE | (i & 0xF))
    assert await env.crd(C_IRQCAUSE) & CAUSE_INJ_OVF

    await env.cwr(C_CTRL, CTRL_FLUSH)
    for _ in range(8):
        await RisingEdge(dut.clk_i)
    assert await env.crd(C_EVQ_STAT) & 0xFF == 0, "FLUSH left the queue full"
    assert await env.crd(C_STATUS) & ST_INJ_EMPTY
    assert await env.crd(C_IRQCAUSE) & CAUSE_INJ_OVF, \
        "FLUSH erased the record of the overflow that preceded it"


# ---------------------------------------------------------------------------
# 5. The interrupt
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_the_line_is_the_cause_and_the_mask(dut):
    """irq_o = |(cause & mask), and the mask resets to zero.

    docs/40 froze NPUCFG on fast local line 12 before this block existed.
    A line that came up asserted would interrupt a core that had never
    heard of the block, so the reset value of the mask is what makes
    adding this block to soc_top.v behaviourally free.
    """
    env = Env(dut)
    await env.reset()
    assert dut.irq_o.value == 0
    assert await env.crd(C_IRQMASK) == 0

    await enable_node(env)
    await env.cwr(C_CTRL, CTRL_IN_EN | CTRL_OUT_EN)
    await env.cwr(C_EVQ_IN, TYPE_SYNC | 3)
    for _ in range(4000):
        if await env.crd(C_STATUS) & ST_CAP_EMPTY == 0:
            break
    else:
        raise AssertionError("the barrier never reached the capture queue")

    assert await env.crd(C_IRQCAUSE) & CAUSE_EVT, "EVT did not rise"
    assert dut.irq_o.value == 0, "the line rose with the mask clear"

    await env.cwr(C_IRQMASK, CAUSE_EVT)
    await RisingEdge(dut.clk_i)
    await Timer(T_SAMPLE, unit="ns")
    assert dut.irq_o.value == 1, "the line did not rise with EVT masked in"


@cocotb.test()
async def test_evt_is_a_level_and_says_so(dut):
    """EVT cannot be acknowledged; it is cleared by draining the queue.

    A write of 1 to it is accepted and does nothing, because the way to
    clear a level is to fix what raises it. That is a real decision and
    an easy one to get wrong in the other direction, so it is stated as
    a property rather than left to the register file.
    """
    env = Env(dut)
    await env.reset()
    await enable_node(env)
    await env.cwr(C_CTRL, CTRL_IN_EN | CTRL_OUT_EN)
    await env.cwr(C_EVQ_IN, TYPE_SYNC | 5)
    for _ in range(4000):
        if await env.crd(C_IRQCAUSE) & CAUSE_EVT:
            break
    else:
        raise AssertionError("EVT never rose")

    await env.cwr(C_IRQCAUSE, CAUSE_EVT)
    assert await env.crd(C_IRQCAUSE) & CAUSE_EVT, \
        "EVT was cleared by a write; it is a level and must not be"

    w = await env.crd(C_EVQ_OUT)
    assert w & EVQ_VALID
    assert await env.crd(C_IRQCAUSE) & CAUSE_EVT == 0, \
        "EVT stayed set with the queue empty"
