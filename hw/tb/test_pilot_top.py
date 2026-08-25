"""TTIHP26b pilot bring-up suite: the Tiny Tapeout wrapper end to end.

The device under test is hw/rtl/tt_um_melihakbulut_nssoc.v, the Tiny
Tapeout wrapper, so every stimulus in this file goes through the eight
inputs, eight outputs and eight
bidirectionals the shuttle actually gives us. Exactly three tests reach
into the hierarchy, all for the same reason -- no pin injects a
single-event upset -- and all three are marked as such. Two of them
observe only what a bench could observe. The remaining one additionally
holds one internal flop, because the two terms of STATUS.ERR_CFG are
otherwise indistinguishable from outside; its docstring says so in full.
If any other test passes here it passes on a board with an SPI master
and a logic analyser, which is the whole point of a pilot.

Coverage, in the order the tests appear:

  reset          reset values of every implemented register against
                 regmap/regmap.yaml (through sw/golden/regmap_gen.py),
                 the uio direction word, quiescent output pins, and an
                 asynchronously released reset
  serial         register read/write round trips, write-to-read-only,
                 unmapped offsets, the minimum chip-select setup of one
                 serial-clock period, and the configuration lock
  event path     EVQ_IN/EVQ_OUT over the serial port and over the
                 parallel AER pins, the show-ahead EVQ_OUT contract,
                 SYNC barrier echo, out-of-range axon drops,
                 input-queue overflow, soft reset, state clear
  inference      a small end-to-end run checked spike for spike and
                 neuron state for neuron state against sw/golden
  demonstrators  SECDED single-bit correction with a syndrome walk,
                 double-bit detection with the E10 zero substitution
                 proven by an inference, the scrub loop driven from the
                 SCRUB_STB pin, TMR masking proven by running the same
                 inference with a configuration replica corrupted, and
                 an upset in the neuron core's FSM state register
                 observed at STATUS.ERR_CFG and the ERR pin, twice: once
                 for the recovery path and once for the live term that
                 keeps the bit asserted while the core is still parked,
                 and an upset that strands the event dispatcher in
                 D_FETCH, whose bounded wait must clear BUSY on its own
                 and report the recovery (docs/16 section 5.1)
  register map   the FAULT_CLR bit assignment against regmap.yaml

Run: cd hw/tb && make -f Makefile.pilot
"""

import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.handle import Force, Release
from cocotb.triggers import RisingEdge, Timer

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "sw")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from golden.lif_core import LIFConfig, LIFCore  # noqa: E402
from golden.regmap_gen import ADDR, FIELDS, RESET  # noqa: E402

CLK_NS = 10          # 100 MHz simulation clock
HALF = 20            # serial half period, i.e. SER_SCK = clk/4, the limit

# ui_in bits (pilot_top.v section 1)
SER_SCK, SER_CS_N, SER_MOSI = 0, 1, 2
AER_IN_STB, AER_IN_TICK, AER_OUT_ACK, SCRUB_STB = 3, 4, 5, 6
# uo_out bits
SER_MISO, BUSY, AER_IN_RDY, AER_OUT_VLD = 0, 1, 2, 3
ERR, SEC, DED, TMR = 4, 5, 6, 7

# pilot-only registers (pilot_top.v section 5)
ADDR_ECC_INJ_POS = 0x0A0
ADDR_TMR_INJ = 0x0A4
ADDR_CNT_TMR = 0x0A8

# STATUS / CTRL / ECC_INJ field masks, named so the tests read as intent
ST_BUSY, ST_IN_EMPTY, ST_OUT_EMPTY = 1 << 0, 1 << 1, 1 << 2
ST_SYNC_DONE, ST_ERR_CFG, ST_DED_SEEN, ST_OVF_SEEN = 1 << 3, 1 << 4, 1 << 5, 1 << 6
CTRL_EN, CTRL_STATE_CLR, CTRL_SOFT_RST, CTRL_SCRUB_EN = 1, 2, 4, 8
INJ_SINGLE, INJ_DOUBLE = 1, 2

# FAULT_CLR bits. The first five are normative and come from
# regmap/regmap.yaml through the generated golden model, so this suite
# fails rather than passes if the map ever renumbers them. The sixth is
# the pilot-only CNT_TMR clear (pilot_top.v section 5): CNT_TMR is not in
# the architecture register map, so neither is its clear bit.
FCLR_SEC = 1 << FIELDS["FAULT_CLR"]["CNT_SEC"]
FCLR_DED = 1 << FIELDS["FAULT_CLR"]["CNT_DED"]
FCLR_EVQ_OVF = 1 << FIELDS["FAULT_CLR"]["CNT_EVQ_OVF"]
FCLR_AXON_OOR = 1 << FIELDS["FAULT_CLR"]["CNT_AXON_OOR"]
FCLR_FAULT_ADDR = 1 << FIELDS["FAULT_CLR"]["FAULT_ADDR"]
FCLR_CNT_TMR = 1 << 5

TYPE_SPIKE, TYPE_TICK, TYPE_SYNC = 0 << 14, 1 << 14, 2 << 14


# ---------------------------------------------------------------------
# pin plumbing
# ---------------------------------------------------------------------
# cocotb value deposits are scheduled, not immediate: a read-modify-write
# of dut.ui_in.value with no await in between reads the PRE-deposit value
# and silently drops the previous bit write. The same trap cost a
# debugging session on the sibling project's wrapper, so ui_in and uio_in
# are kept in Python-side shadows and only ever written whole.
class Pins:
    def __init__(self, dut):
        self.dut = dut
        self.ui = 1 << SER_CS_N     # CS_n idles high, everything else low
        self.uio = 0

    def set_ui(self, bit, val):
        self.ui = (self.ui & ~(1 << bit)) | ((val & 1) << bit)
        self.dut.ui_in.value = self.ui

    def set_uio(self, val):
        self.uio = val & 0x0F
        self.dut.uio_in.value = self.uio


def uo(dut, bit):
    """X-safe single-bit sample of uo_out."""
    s = str(dut.uo_out.value)
    return 1 if s[7 - bit] == "1" else 0


def uio_out_nibble(dut):
    s = str(dut.uio_out.value)
    return int("".join("1" if c == "1" else "0" for c in s[:4]), 2)


async def realign(dut):
    """Put the test back on the system-clock grid before a serial frame.

    Every helper below drives SER_SCK at exactly clk/4, which is host
    obligation H1 at its limit (pilot_top.v section 2), and it does so by
    counting nanoseconds from wherever the test happens to be. A test
    that samples a pin mid-cycle -- `await RisingEdge(clk)` followed by a
    short `Timer` to let combinational logic settle -- leaves the clock
    offset by that Timer, and every SPI edge of the next frame inherits
    it. Measured on this design: one leftover nanosecond moves the MISO
    sampling point across a system-clock edge and the host reads the
    whole 32-bit word shifted by one bit position (0xA5A51234 came back
    as 0xD2D2891A). Awaiting one more clock edge discards the offset,
    because the clock's edges are on the grid by construction.

    That is a property of this testbench's timing, not of the design: a
    real host's SER_SCK has no phase relationship to clk at all, which is
    what the two-flop synchronizer exists for. Frames driven from
    `reset()` are already on the grid, so only tests that sample pins
    between frames need this.
    """
    await RisingEdge(dut.clk)


async def spi_byte(p, tx):
    """One mode-0 byte, MSB first. Returns the byte shifted out on MISO."""
    rx = 0
    for i in range(7, -1, -1):
        p.set_ui(SER_MOSI, (tx >> i) & 1)
        await Timer(HALF, unit="ns")
        p.set_ui(SER_SCK, 1)
        await Timer(1, unit="ns")
        rx = (rx << 1) | uo(p.dut, SER_MISO)
        await Timer(HALF - 1, unit="ns")
        p.set_ui(SER_SCK, 0)
    return rx


async def frame(p, write, addr, data=0, cs_setup=2 * HALF):
    """One 40-bit serial frame: command byte then 32 data bits.

    cs_setup is the delay between the chip-select falling edge and the
    first serial-clock edge. It defaults to one full SER_SCK period,
    which is the documented minimum (pilot_top.v section 2): the frame
    reset has to clear the two-flop synchronizer before the first sampled
    clock edge arrives.

    The trailing gap is one full SER_SCK period as well, for the mirror
    reason: the deselect has to be SEEN before the next frame starts, or
    the bit counter carries over and the next frame decodes at the wrong
    offset. That failure was observed during bring-up with a half-period
    gap and is why pilot_top.v section 2 states both requirements.
    """
    p.set_ui(SER_CS_N, 0)
    await Timer(cs_setup, unit="ns")
    await spi_byte(p, ((1 if write else 0) << 7) | ((addr >> 2) & 0x7F))
    out = 0
    for shift in (24, 16, 8, 0):
        out = (out << 8) | await spi_byte(p, (data >> shift) & 0xFF)
    await Timer(HALF, unit="ns")
    p.set_ui(SER_CS_N, 1)
    await Timer(2 * HALF, unit="ns")
    return out


async def wr(p, addr, data):
    await frame(p, True, addr, data)


async def rd(p, addr):
    return await frame(p, False, addr)


async def reset(dut, async_release=False):
    """Bring the DUT up. Returns the pin shadow used by every helper."""
    p = Pins(dut)
    cocotb.start_soon(Clock(dut.clk, CLK_NS, unit="ns").start())
    dut.ena.value = 1
    dut.ui_in.value = p.ui
    dut.uio_in.value = p.uio
    dut.rst_n.value = 0
    for _ in range(6):
        await RisingEdge(dut.clk)
    if async_release:
        # Release the reset off the clock edge, which is what the Tiny
        # Tapeout infrastructure is allowed to do. The wrapper's two-flop
        # synchronizer is what makes this safe.
        await Timer(CLK_NS // 3, unit="ns")
    dut.rst_n.value = 1
    for _ in range(6):
        await RisingEdge(dut.clk)
    return p


# ---------------------------------------------------------------------
# golden-model plumbing
# ---------------------------------------------------------------------
async def geometry(p):
    """Read the elaborated geometry back out of the register map."""
    n_neurons = await rd(p, ADDR["CFG_NEUR"])
    n_axons = await rd(p, ADDR["CFG_AXON"])
    return n_neurons, n_axons


def pack_words(weights, n_neurons):
    """weights[axon][neuron] -> list of 64-bit ECC data words.

    docs/10 section 5: linear index (a * N_NEURONS + j), axon-major,
    16 four-bit weights per 64-bit word, weight k at bits [4k+3:4k].
    """
    flat = [w for row in weights for w in row]
    words = []
    for base in range(0, len(flat), 16):
        word = 0
        for k, w in enumerate(flat[base:base + 16]):
            word |= (w & 0xF) << (4 * k)
        words.append(word)
    return words


async def load_weights(p, weights, n_neurons, first_word=0):
    words = pack_words(weights, n_neurons)
    await wr(p, ADDR["W_ADDR"], first_word)
    for word in words:
        await wr(p, ADDR["W_DATA_LO"], word & 0xFFFFFFFF)
        await wr(p, ADDR["W_DATA_HI"], (word >> 32) & 0xFFFFFFFF)


async def configure(p, cfg, tile_off=0):
    await wr(p, ADDR["CFG_THRESH"], cfg.thresh & 0xFFFF)
    await wr(p, ADDR["CFG_VRESET"], cfg.v_reset & 0xFFFF)
    await wr(p, ADDR["CFG_LEAK"], cfg.leak_shift)
    await wr(p, ADDR["CFG_SYNSHIFT"], cfg.syn_shift)
    await wr(p, ADDR["CFG_REFR"], cfg.refr_period)
    await wr(p, ADDR["CFG_FLAGS"], 2 if cfg.leak_en else 0)
    await wr(p, ADDR["PASS_TILE_OFF"], tile_off)


async def state_clr(p):
    await wr(p, ADDR["CTRL"], CTRL_STATE_CLR)
    for _ in range(4):
        if (await rd(p, ADDR["STATUS"])) & ST_BUSY == 0:
            return
    raise AssertionError("STATE_CLR never completed")


async def drain(p, limit=400):
    """Pop every queued output event; returns them in emission order."""
    spikes = []
    for _ in range(limit):
        st = await rd(p, ADDR["STATUS"])
        if not (st & ST_BUSY) and (st & ST_OUT_EMPTY):
            return spikes
        word = await rd(p, ADDR["EVQ_OUT"])
        if word & (1 << 31):
            spikes.append(word & 0xFFFF)
    raise AssertionError("output queue never drained")


async def run_frames(p, frames):
    """Push timesteps through EVQ_IN, draining after every command.

    Each timestep is its spike events in order followed by one TICK,
    which is exactly the golden model's run_frames contract (E8). The
    drain after every command keeps the five-entry output path (queue
    plus holding register) from ever backpressuring, so the comparison
    below is about arithmetic, not about flow control -- backpressure has
    its own test.
    """
    out = []
    for timestep in frames:
        spikes = []
        for axon in timestep:
            await wr(p, ADDR["EVQ_IN"], TYPE_SPIKE | axon)
            spikes.extend(await drain(p))
        await wr(p, ADDR["EVQ_IN"], TYPE_TICK)
        spikes.extend(await drain(p))
        out.append(spikes)
    return out


async def check_state(p, core, n_neurons):
    """Compare the whole neuron state file against the golden model."""
    for j in range(n_neurons):
        await wr(p, ADDR["N_ADDR"], j)
        word = await rd(p, ADDR["N_DATA"])
        v = word & 0xFFFF
        v = v - 0x10000 if v >= 0x8000 else v
        r = (word >> 16) & 0xF
        gv, gr = core.get_state(j)
        assert (v, r) == (gv, gr), \
            f"neuron {j}: rtl V={v} R={r}, golden V={gv} R={gr}"


# ---------------------------------------------------------------------
# 1. reset
# ---------------------------------------------------------------------
@cocotb.test()
async def test_reset_values(dut):
    """Every implemented register comes out of reset at its regmap value.

    The expected values come from sw/golden/regmap_gen.py, which is
    generated from regmap/regmap.yaml, so this test fails if the RTL and
    the register map ever drift apart -- the same guard the register-bank
    suite applies to the full block.
    """
    p = await reset(dut)
    n_neurons, n_axons = await geometry(p)

    for name in ("ID", "VERSION", "SCRATCH", "CTRL", "STATUS", "CFG_THRESH",
                 "CFG_VRESET", "CFG_LEAK", "CFG_SYNSHIFT", "CFG_REFR",
                 "CFG_FLAGS", "PASS_TILE_OFF", "W_ADDR", "W_DATA_LO",
                 "W_DATA_HI", "N_ADDR", "CNT_SEC", "CNT_DED", "CNT_EVQ_OVF",
                 "CNT_AXON_OOR", "FAULT_ADDR", "ECC_INJ", "NODE_ID"):
        got = await rd(p, ADDR[name])
        assert got == RESET[name], \
            f"{name} reset {got:#010x}, regmap says {RESET[name]:#010x}"

    # CFG_NEUR and CFG_AXON report the elaborated geometry (deviation D2).
    assert (n_neurons, n_axons) in (
        (4, 8), (8, 4), (8, 8), (8, 16), (16, 8), (16, 16)), \
        f"unexpected geometry {n_neurons}x{n_axons}"
    assert await rd(p, ADDR["EVQ_STAT"]) == 0, "queues must reset empty"

    # pilot-only block (deviation D5)
    assert await rd(p, ADDR_ECC_INJ_POS) == 0
    assert await rd(p, ADDR_TMR_INJ) == 0
    assert await rd(p, ADDR_CNT_TMR) == 0


@cocotb.test()
async def test_reset_pins_and_directions(dut):
    """uio directions and the quiescent output pins."""
    p = await reset(dut)
    assert int(dut.uio_oe.value) == 0xF0, \
        "uio[3:0] must be inputs (AER_IN_ADDR), uio[7:4] outputs (AER_OUT_ID)"
    for bit, name in ((BUSY, "BUSY"), (AER_OUT_VLD, "AER_OUT_VLD"),
                      (ERR, "ERR"), (SEC, "SEC"), (DED, "DED"), (TMR, "TMR")):
        assert uo(dut, bit) == 0, f"{name} must be low after reset"
    assert uo(dut, AER_IN_RDY) == 1, "EVQ_IN must have room after reset"


@cocotb.test()
async def test_reset_released_asynchronously(dut):
    """Tiny Tapeout may release rst_n off the clock edge.

    The wrapper's two-flop synchronizer is what makes that safe. Release
    the reset a third of a clock period after an edge and check the
    design still comes up coherently and still works.
    """
    p = await reset(dut, async_release=True)
    assert await rd(p, ADDR["ID"]) == RESET["ID"]
    assert await rd(p, ADDR["STATUS"]) == RESET["STATUS"]
    await wr(p, ADDR["SCRATCH"], 0xA5A5_5A5A)
    assert await rd(p, ADDR["SCRATCH"]) == 0xA5A5_5A5A

    # A second reset, asserted asynchronously, must scrub the write.
    await Timer(3, unit="ns")
    dut.rst_n.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    for _ in range(4):
        await RisingEdge(dut.clk)
    assert await rd(p, ADDR["SCRATCH"]) == 0


# ---------------------------------------------------------------------
# 2. serial register access
# ---------------------------------------------------------------------
@cocotb.test()
async def test_register_access(dut):
    p = await reset(dut)

    for pattern in (0x0000_0000, 0xFFFF_FFFF, 0xDEAD_BEEF, 0x1234_5678):
        await wr(p, ADDR["SCRATCH"], pattern)
        assert await rd(p, ADDR["SCRATCH"]) == pattern

    # narrow registers ignore the bits above their field
    await wr(p, ADDR["NODE_ID"], 0xFFFF_FFFF)
    assert await rd(p, ADDR["NODE_ID"]) == 0xF
    await wr(p, ADDR["CFG_SYNSHIFT"], 0xFFFF_FFFF)
    assert await rd(p, ADDR["CFG_SYNSHIFT"]) == 0x7

    # read-only registers refuse writes
    await wr(p, ADDR["ID"], 0)
    assert await rd(p, ADDR["ID"]) == RESET["ID"]
    await wr(p, ADDR["VERSION"], 0x55)
    assert await rd(p, ADDR["VERSION"]) == RESET["VERSION"]

    # unmapped offsets read zero and swallow writes without side effects
    await wr(p, 0x0C0, 0xFFFF_FFFF)
    assert await rd(p, 0x0C0) == 0
    assert await rd(p, ADDR["W_BASE"]) == 0     # not implemented in the pilot
    assert await rd(p, ADDR["SCRATCH"]) == 0x1234_5678


@cocotb.test()
async def test_chip_select_setup(dut):
    """The host protocol requirement, exercised at its stated minimum.

    pilot_top.v section 2 requires the chip select to fall at least one
    full serial-clock period before the first serial-clock edge, and to
    stay high at least that long between frames. This test holds the
    boundary case and several margins, at SER_SCK = clk/4, which is the
    fastest serial clock the design allows.

    There is deliberately no assertion that a shorter setup FAILS. Both
    the select and the serial clock cross into the clk domain through
    identical two-flop synchronizers, so whether a marginal setup
    survives depends on the phase between the two clocks -- which is not
    controllable on silicon and is exactly why the requirement is stated
    as a host obligation rather than discovered by experiment.
    """
    p = await reset(dut)
    await wr(p, ADDR["SCRATCH"], 0x0BAD_C0DE)

    for setup in (2 * HALF, 3 * HALF, 4 * HALF, 16 * HALF):
        got = await frame(p, False, ADDR["SCRATCH"], cs_setup=setup)
        assert got == 0x0BAD_C0DE, f"read failed at CS setup {setup} ns"

    # back-to-back frames at the minimum inter-frame gap keep their
    # alignment: the bit counter must restart at every frame.
    for _ in range(4):
        assert await rd(p, ADDR["SCRATCH"]) == 0x0BAD_C0DE
    await wr(p, ADDR["SCRATCH"], 0x1357_9BDF)
    assert await rd(p, ADDR["SCRATCH"]) == 0x1357_9BDF


# ---------------------------------------------------------------------
# 3. event path
# ---------------------------------------------------------------------
@cocotb.test()
async def test_input_queue_overflow(dut):
    """EVQ_IN drops on full and counts, per docs/10 section 7.2.

    CTRL.EN stays clear so nothing drains the queue, which makes the
    overflow deterministic rather than a race with the dispatcher.
    """
    p = await reset(dut)

    # The depth is an elaboration parameter, so it is discovered rather
    # than assumed: push until the fill level stops rising.
    depth, guard = 0, 0
    while True:
        prev, guard = depth, guard + 1
        assert guard < 64, "the input queue never filled"
        await wr(p, ADDR["EVQ_IN"], TYPE_SPIKE | (guard & 0x0F))
        depth = (await rd(p, ADDR["EVQ_STAT"])) & 0xFF
        if depth == prev:
            break                       # that write was the first drop
    assert depth >= 2, "aer_fifo DEPTH must be at least 2"
    assert uo(dut, AER_IN_RDY) == 0, "AER_IN_RDY must fall when the queue is full"

    for _ in range(2):
        await wr(p, ADDR["EVQ_IN"], TYPE_SPIKE | 0)
    assert (await rd(p, ADDR["EVQ_STAT"])) & 0xFF == depth, "queue must be full"
    assert await rd(p, ADDR["CNT_EVQ_OVF"]) == 3, "three writes must be dropped"
    assert (await rd(p, ADDR["STATUS"])) & ST_OVF_SEEN, "OVF_SEEN is sticky"
    assert uo(dut, ERR) == 1, "the ERR pin must show a queue overflow"

    await wr(p, ADDR["FAULT_CLR"], FCLR_EVQ_OVF)
    await wr(p, ADDR["STATUS_CLR"], ST_OVF_SEEN)
    assert await rd(p, ADDR["CNT_EVQ_OVF"]) == 0
    assert not (await rd(p, ADDR["STATUS"])) & ST_OVF_SEEN
    assert uo(dut, ERR) == 0


@cocotb.test()
async def test_soft_reset_flushes_queues_keeps_config(dut):
    """CTRL.SOFT_RST: flush the queues and the pipeline, keep the config."""
    p = await reset(dut)
    await wr(p, ADDR["CFG_THRESH"], 0x1234)
    await wr(p, ADDR["EVQ_IN"], TYPE_SPIKE | 0)
    await wr(p, ADDR["EVQ_IN"], TYPE_SPIKE | 1)
    assert (await rd(p, ADDR["EVQ_STAT"])) & 0xFF == 2

    await wr(p, ADDR["CTRL"], CTRL_SOFT_RST)
    assert (await rd(p, ADDR["EVQ_STAT"])) & 0xFF == 0
    assert (await rd(p, ADDR["STATUS"])) & ST_IN_EMPTY
    assert await rd(p, ADDR["CFG_THRESH"]) == 0x1234, "config must survive"
    assert (await rd(p, ADDR["CTRL"])) & CTRL_SOFT_RST == 0, "SOFT_RST self-clears"


@cocotb.test()
async def test_state_clear_and_state_port(dut):
    """CTRL.STATE_CLR and the N_ADDR / N_DATA debug port."""
    p = await reset(dut)
    n_neurons, _ = await geometry(p)
    await state_clr(p)

    for j in range(n_neurons):
        await wr(p, ADDR["N_ADDR"], j)
        assert await rd(p, ADDR["N_DATA"]) == 0, f"neuron {j} not cleared"

    # write a state word and read it back through the same port
    await wr(p, ADDR["N_ADDR"], 1)
    await wr(p, ADDR["N_DATA"], (3 << 16) | 0x04D2)
    assert await rd(p, ADDR["N_DATA"]) == (3 << 16) | 0x04D2
    await wr(p, ADDR["N_ADDR"], 0)
    assert await rd(p, ADDR["N_DATA"]) == 0, "only the addressed neuron changes"

    await state_clr(p)
    await wr(p, ADDR["N_ADDR"], 1)
    assert await rd(p, ADDR["N_DATA"]) == 0


@cocotb.test()
async def test_sync_barrier(dut):
    """SYNC is echoed downstream and sets STATUS.SYNC_DONE (docs/10 7.1)."""
    p = await reset(dut)
    await state_clr(p)
    await wr(p, ADDR["CTRL"], CTRL_EN)
    assert not (await rd(p, ADDR["STATUS"])) & ST_SYNC_DONE

    await wr(p, ADDR["EVQ_IN"], TYPE_SYNC | 0x2A)
    echoed = await drain(p)
    assert echoed == [TYPE_SYNC | 0x2A], f"barrier echo wrong: {echoed}"
    assert (await rd(p, ADDR["STATUS"])) & ST_SYNC_DONE

    await wr(p, ADDR["STATUS_CLR"], ST_SYNC_DONE)
    assert not (await rd(p, ADDR["STATUS"])) & ST_SYNC_DONE


@cocotb.test()
async def test_axon_out_of_range_is_dropped_and_counted(dut):
    """CFG_AXON bounds the axon id; over-range events drop and count."""
    p = await reset(dut)
    n_neurons, n_axons = await geometry(p)
    await state_clr(p)
    await wr(p, ADDR["CFG_AXON"], 2)
    await wr(p, ADDR["CFG_THRESH"], 1)
    await wr(p, ADDR["CFG_FLAGS"], 0)          # leak off, so V holds
    await wr(p, ADDR["CTRL"], CTRL_EN)

    await wr(p, ADDR["EVQ_IN"], TYPE_SPIKE | (n_axons - 1))
    assert await drain(p) == [], "an over-range event must not reach the core"
    assert await rd(p, ADDR["CNT_AXON_OOR"]) == 1

    await wr(p, ADDR["EVQ_IN"], TYPE_SPIKE | 1)
    await drain(p)
    assert await rd(p, ADDR["CNT_AXON_OOR"]) == 1, "an in-range event must pass"

    await wr(p, ADDR["FAULT_CLR"], FCLR_AXON_OOR)
    assert await rd(p, ADDR["CNT_AXON_OOR"]) == 0
    assert n_neurons >= 4


@cocotb.test()
async def test_config_lock_while_busy(dut):
    """docs/10 section 6: config writes while BUSY are ignored, ERR_CFG set.

    BUSY is held for as long as the test needs by starving the output
    path: with every neuron above threshold, two events emit more spikes
    than the five-entry output path can hold, so lif_core stalls in its
    scan -- which also demonstrates that spikes are never dropped.
    """
    p = await reset(dut)
    n_neurons, n_axons = await geometry(p)
    await state_clr(p)
    await wr(p, ADDR["CFG_THRESH"], 1)
    await wr(p, ADDR["CFG_SYNSHIFT"], 0)
    await wr(p, ADDR["CFG_FLAGS"], 0)
    await load_weights(p, [[7] * n_neurons for _ in range(n_axons)], n_neurons)
    await wr(p, ADDR["CTRL"], CTRL_EN)

    await wr(p, ADDR["EVQ_IN"], TYPE_SPIKE | 0)
    await wr(p, ADDR["EVQ_IN"], TYPE_SPIKE | 0)
    assert (await rd(p, ADDR["STATUS"])) & ST_BUSY, "core must be stalled"

    await wr(p, ADDR["CFG_THRESH"], 0x7FFF)
    assert await rd(p, ADDR["CFG_THRESH"]) == 1, "locked write must be ignored"
    assert (await rd(p, ADDR["STATUS"])) & ST_ERR_CFG, "ERR_CFG must latch"
    assert uo(dut, ERR) == 1

    # CTRL, STATUS_CLR and FAULT_CLR stay writable while BUSY
    await wr(p, ADDR["STATUS_CLR"], ST_ERR_CFG)
    assert not (await rd(p, ADDR["STATUS"])) & ST_ERR_CFG

    spikes = await drain(p)
    assert len(spikes) == 2 * n_neurons, \
        f"no spike may be dropped under backpressure: got {len(spikes)}"
    assert spikes == sorted(spikes[:n_neurons]) + sorted(spikes[n_neurons:]), \
        "spikes must leave in ascending scan order (E8)"

    # once idle the same write lands
    await wr(p, ADDR["CFG_THRESH"], 0x7FFF)
    assert await rd(p, ADDR["CFG_THRESH"]) == 0x7FFF


@cocotb.test()
async def test_parallel_aer_pins(dut):
    """The AER_IN and AER_OUT pin path, independent of the serial port."""
    p = await reset(dut)
    n_neurons, n_axons = await geometry(p)
    await state_clr(p)
    await wr(p, ADDR["CFG_THRESH"], 1)
    await wr(p, ADDR["CFG_SYNSHIFT"], 0)
    await wr(p, ADDR["CFG_FLAGS"], 0)
    # only axon 1 drives neuron 2 above threshold
    weights = [[0] * n_neurons for _ in range(n_axons)]
    weights[1][2] = 7
    await load_weights(p, weights, n_neurons)
    await wr(p, ADDR["CTRL"], CTRL_EN)
    assert uo(dut, AER_IN_RDY) == 1

    # one SPIKE event on axon 1, strobed in on the pins
    p.set_uio(1)
    p.set_ui(AER_IN_TICK, 0)
    for _ in range(4):
        await RisingEdge(dut.clk)
    p.set_ui(AER_IN_STB, 1)
    for _ in range(4):
        await RisingEdge(dut.clk)
    p.set_ui(AER_IN_STB, 0)

    for _ in range(200):
        await RisingEdge(dut.clk)
        if uo(dut, AER_OUT_VLD):
            break
    else:
        raise AssertionError("AER_OUT_VLD never asserted")
    assert uio_out_nibble(dut) == 2, "AER_OUT_ID must carry the neuron id"

    # acknowledge on the pin and watch the entry retire
    p.set_ui(AER_OUT_ACK, 1)
    for _ in range(6):
        await RisingEdge(dut.clk)
    p.set_ui(AER_OUT_ACK, 0)
    for _ in range(6):
        await RisingEdge(dut.clk)
    assert uo(dut, AER_OUT_VLD) == 0, "the pin pop must retire the event"
    assert (await rd(p, ADDR["STATUS"])) & ST_OUT_EMPTY

    # a TICK strobed in on the pins is consumed and emits nothing
    p.set_ui(AER_IN_TICK, 1)
    for _ in range(4):
        await RisingEdge(dut.clk)
    p.set_ui(AER_IN_STB, 1)
    for _ in range(4):
        await RisingEdge(dut.clk)
    p.set_ui(AER_IN_STB, 0)
    p.set_ui(AER_IN_TICK, 0)
    assert await drain(p) == [], "a TICK never emits (docs/10 section 4.2)"


@cocotb.test()
async def test_evq_out_is_show_ahead(dut):
    """The EVQ_OUT source presents a word before anything pops it.

    hw/rtl/aer_fifo.v is a registered-output queue: its data appears one
    cycle AFTER an accepted read. The register map defines EVQ_OUT as a
    single-access pop, and hw/rtl/npu_regbank.v states the same thing as
    convention C9: valid means "a word is presented now", the data is that
    word, and both hold until the pop advances the queue. pilot_top.v
    section 8 closes the gap with a one-entry show-ahead adapter rather
    than by making the queue combinationally read-through.

    This test is that contract, checked from outside the chip. Two spikes
    are produced from one event so that there is a word in the adapter
    AND a word still in the queue:

      * a word is presented on the pins with nothing having popped it,
        and it holds indefinitely (the "show-ahead" half);
      * EVQ_STAT.OUT_FILL counts the presented word, so the fill level a
        host reads is the number of events it can still get out;
      * the serial read returns exactly the word the pins were showing,
        and the next word takes its place (the "pop advances" half);
      * when both are gone the queue reports empty and reads return
        VALID = 0.
    """
    p = await reset(dut)
    n_neurons, n_axons = await geometry(p)
    await state_clr(p)
    await wr(p, ADDR["CFG_THRESH"], 1)
    await wr(p, ADDR["CFG_SYNSHIFT"], 0)
    await wr(p, ADDR["CFG_FLAGS"], 0)          # leak off
    # axon 1 drives exactly two neurons over threshold, so one event
    # produces exactly two output words, in ascending scan order (E8).
    weights = [[0] * n_neurons for _ in range(n_axons)]
    weights[1][2] = 7
    weights[1][3] = 7
    await load_weights(p, weights, n_neurons)
    await wr(p, ADDR["CTRL"], CTRL_EN)

    await wr(p, ADDR["EVQ_IN"], TYPE_SPIKE | 1)
    for _ in range(20):
        if not (await rd(p, ADDR["STATUS"])) & ST_BUSY:
            break
    else:
        raise AssertionError("the event never retired")

    # 1. A word is presented with nothing having popped it, and it holds.
    assert uo(dut, AER_OUT_VLD) == 1, \
        "a queued event must be presented without a pop first"
    first = uio_out_nibble(dut)
    assert first == 2, f"first emitted neuron id must be 2, got {first}"
    for _ in range(40):
        await RisingEdge(dut.clk)
        assert uo(dut, AER_OUT_VLD) == 1, "the presented word must hold"
        assert uio_out_nibble(dut) == first, "and must not change under it"

    # 2. The presented word is counted in the fill level.
    out_fill = ((await rd(p, ADDR["EVQ_STAT"])) >> 8) & 0xFF
    assert out_fill == 2, \
        f"OUT_FILL must count the presented word too, got {out_fill}"
    assert not (await rd(p, ADDR["STATUS"])) & ST_OUT_EMPTY

    # 3. The pop returns that word, and the next one takes its place.
    word = await rd(p, ADDR["EVQ_OUT"])
    assert word & (1 << 31), "EVQ_OUT must report VALID"
    assert (word & 0xF) == first, \
        "the popped word must be the one the pins were showing"
    for _ in range(20):
        await RisingEdge(dut.clk)
        if uo(dut, AER_OUT_VLD):
            break
    else:
        raise AssertionError("the second word was never presented")
    assert uio_out_nibble(dut) == 3, "the second emitted neuron id must be 3"
    out_fill = ((await rd(p, ADDR["EVQ_STAT"])) >> 8) & 0xFF
    assert out_fill == 1, f"one event left, OUT_FILL says {out_fill}"

    # 4. Drain the last one and the queue reports itself empty.
    word = await rd(p, ADDR["EVQ_OUT"])
    assert word & (1 << 31) and (word & 0xF) == 3
    assert uo(dut, AER_OUT_VLD) == 0, "nothing left to present"
    assert (await rd(p, ADDR["STATUS"])) & ST_OUT_EMPTY
    assert ((await rd(p, ADDR["EVQ_STAT"])) >> 8) & 0xFF == 0
    assert (await rd(p, ADDR["EVQ_OUT"])) & (1 << 31) == 0, \
        "a read of an empty queue must report VALID = 0"


# ---------------------------------------------------------------------
# 4. end-to-end inference against sw/golden
# ---------------------------------------------------------------------
CFG = LIFConfig(thresh=20, v_reset=-4, leak_shift=2, syn_shift=2,
                refr_period=2, leak_en=True)
FRAMES = [[0, 1], [2], [1, 1, 3], [], [0, 2, 3], [3]]


def make_weights(n_axons, n_neurons, seed=20260921):
    """Deterministic weight matrix; the seed is fixed so a failure is
    reproducible from the test name alone."""
    import random
    rng = random.Random(seed)
    return [[rng.randint(-8, 7) for _ in range(n_neurons)]
            for _ in range(n_axons)]


async def bring_up(p, weights, n_neurons, cfg=CFG, tile_off=0):
    """State clear, configure, load weights, enable. In that order:
    every configuration register is locked while BUSY, so the enable has
    to come last."""
    await state_clr(p)
    await configure(p, cfg, tile_off)
    await load_weights(p, weights, n_neurons)
    await wr(p, ADDR["CTRL"], CTRL_EN)


@cocotb.test()
async def test_inference_matches_golden(dut):
    """A small inference, spike for spike and state for state.

    The golden model sw/golden/lif_core.py is the normative form of the
    docs/10 section 4 equations. This is the same lockstep the lif_core
    suite runs, but driven entirely through the pilot's pins: the serial
    port, the register map, the ECC-checked weight loader, the event
    queues and the AER event word are all in the loop.
    """
    p = await reset(dut)
    n_neurons, n_axons = await geometry(p)
    weights = make_weights(n_axons, n_neurons)
    await bring_up(p, weights, n_neurons)

    core = LIFCore(n_neurons, n_axons, weights, CFG)
    expected = core.run_frames(FRAMES)
    got = await run_frames(p, FRAMES)

    assert got == expected, f"spike stream: rtl {got}, golden {expected}"
    assert any(step for step in expected), \
        "the stimulus must actually produce spikes to be worth running"
    await check_state(p, core, n_neurons)


@cocotb.test()
async def test_inference_with_tile_offset(dut):
    """PASS_TILE_OFF is added to every emitted id (E5 / E9)."""
    p = await reset(dut)
    n_neurons, n_axons = await geometry(p)
    weights = make_weights(n_axons, n_neurons, seed=7)
    tile_off = 512
    await bring_up(p, weights, n_neurons, tile_off=tile_off)

    core = LIFCore(n_neurons, n_axons, weights, CFG, tile_offset=tile_off)
    expected = core.run_frames(FRAMES)
    got = await run_frames(p, FRAMES)
    assert got == expected, f"spike stream: rtl {got}, golden {expected}"
    assert any(sid >= tile_off for step in expected for sid in step), \
        "the offset must actually appear in the emitted ids"


# ---------------------------------------------------------------------
# 5. fault-tolerance demonstrators
# ---------------------------------------------------------------------
@cocotb.test()
async def test_secded_single_bit_correction(dut):
    """A one-bit upset in a weight word is corrected on the read path.

    With CTRL.SCRUB_EN clear the injected bit stays in the stored word --
    that is what makes it observable on a bench -- but the weights that
    reach the datapath are the decoded ones, so the inference is
    unaffected. Enabling the scrubber then repairs the stored word.
    """
    p = await reset(dut)
    n_neurons, n_axons = await geometry(p)
    weights = make_weights(n_axons, n_neurons)
    words = pack_words(weights, n_neurons)

    await state_clr(p)
    await configure(p, CFG)
    await wr(p, ADDR["CTRL"], 0)                 # EN off, SCRUB_EN off
    await wr(p, ADDR_ECC_INJ_POS, 0)             # codeword bit 0 = data bit 0
    await wr(p, ADDR["W_ADDR"], 0)
    await wr(p, ADDR["ECC_INJ"], INJ_SINGLE)
    await wr(p, ADDR["W_DATA_LO"], words[0] & 0xFFFFFFFF)
    await wr(p, ADDR["W_DATA_HI"], (words[0] >> 32) & 0xFFFFFFFF)

    assert await rd(p, ADDR["CNT_SEC"]) == 1, "one corrected single-bit error"
    assert await rd(p, ADDR["CNT_DED"]) == 0
    assert uo(dut, SEC) == 1 and uo(dut, DED) == 0
    assert await rd(p, ADDR["ECC_INJ"]) == 0, "the injection is one-shot"
    assert await rd(p, ADDR["W_DATA_LO"]) == (words[0] & 0xFFFFFFFF) ^ 1, \
        "with the scrubber off the stored word keeps the injected bit"

    # load the remaining words cleanly and run the inference: the
    # corrected weights must give exactly the golden result
    for word in words[1:]:
        await wr(p, ADDR["W_DATA_LO"], word & 0xFFFFFFFF)
        await wr(p, ADDR["W_DATA_HI"], (word >> 32) & 0xFFFFFFFF)
    await wr(p, ADDR["CTRL"], CTRL_EN)
    core = LIFCore(n_neurons, n_axons, weights, CFG)
    assert await run_frames(p, FRAMES) == core.run_frames(FRAMES), \
        "a corrected single-bit error must not change the inference"

    # The stored codeword is a single staging register (deviation D4),
    # so loading the rest of the image has already overwritten it. Put
    # the corrupted word back to exercise the scrub loop.
    await wr(p, ADDR["CTRL"], 0)
    await wr(p, ADDR["W_ADDR"], 0)
    await wr(p, ADDR["ECC_INJ"], INJ_SINGLE)
    await wr(p, ADDR["W_DATA_LO"], words[0] & 0xFFFFFFFF)
    await wr(p, ADDR["W_DATA_HI"], (words[0] >> 32) & 0xFFFFFFFF)

    # a scrub pulse with the scrubber off counts again and repairs nothing
    before = await rd(p, ADDR["CNT_SEC"])
    await pulse_scrub(p)
    assert await rd(p, ADDR["CNT_SEC"]) == before + 1, \
        "SCRUB_STB must re-check the stored word"
    assert await rd(p, ADDR["W_DATA_LO"]) == (words[0] & 0xFFFFFFFF) ^ 1

    # the same pulse with CTRL.SCRUB_EN set writes the repaired word back
    await wr(p, ADDR["CTRL"], CTRL_SCRUB_EN)
    await pulse_scrub(p)
    assert await rd(p, ADDR["W_DATA_LO"]) == words[0] & 0xFFFFFFFF, \
        "the scrubber must write the repaired word back"
    clean = await rd(p, ADDR["CNT_SEC"])
    await pulse_scrub(p)
    assert await rd(p, ADDR["CNT_SEC"]) == clean, \
        "a repaired word must not keep counting"

    await wr(p, ADDR["FAULT_CLR"], FCLR_SEC)
    assert await rd(p, ADDR["CNT_SEC"]) == 0 and uo(dut, SEC) == 0


async def pulse_scrub(p):
    """One rising edge on the SCRUB_STB pin."""
    for _ in range(3):
        await RisingEdge(p.dut.clk)
    p.set_ui(SCRUB_STB, 1)
    for _ in range(4):
        await RisingEdge(p.dut.clk)
    p.set_ui(SCRUB_STB, 0)
    for _ in range(4):
        await RisingEdge(p.dut.clk)


@cocotb.test()
async def test_secded_syndrome_walk(dut):
    """Every injected single-bit position is corrected, never mistaken
    for an uncorrectable word.

    The positions cover both fields of the codeword: data bits 0..63 and
    check bits 64..71. A subset is walked rather than all 72 so the suite
    stays inside a sensible run time; the boundaries of both fields are
    always included.
    """
    p = await reset(dut)
    n_neurons, n_axons = await geometry(p)
    words = pack_words(make_weights(n_axons, n_neurons), n_neurons)
    payload = words[0]

    await wr(p, ADDR["CTRL"], 0)                  # scrubber off
    positions = [0, 1, 17, 31, 32, 47, 63, 64, 67, 71]
    for n, pos in enumerate(positions, start=1):
        await wr(p, ADDR_ECC_INJ_POS, pos)
        await wr(p, ADDR["W_ADDR"], 0)
        await wr(p, ADDR["ECC_INJ"], INJ_SINGLE)
        await wr(p, ADDR["W_DATA_LO"], payload & 0xFFFFFFFF)
        await wr(p, ADDR["W_DATA_HI"], (payload >> 32) & 0xFFFFFFFF)
        assert await rd(p, ADDR["CNT_SEC"]) == n, f"position {pos} not corrected"
        assert await rd(p, ADDR["CNT_DED"]) == 0, f"position {pos} read as DED"
        # a clean commit clears the corruption for the next iteration
        await wr(p, ADDR["W_ADDR"], 0)
        await wr(p, ADDR["W_DATA_LO"], payload & 0xFFFFFFFF)
        await wr(p, ADDR["W_DATA_HI"], (payload >> 32) & 0xFFFFFFFF)
        assert await rd(p, ADDR["CNT_SEC"]) == n, "a clean word must not count"


@cocotb.test()
async def test_secded_double_bit_detection_and_e10(dut):
    """Two bits: detected, never miscorrected, and the word reads zero.

    E10 (docs/10 section 11.2) makes an uncorrectable weight word
    contribute nothing rather than contributing garbage. The proof here
    is an inference against a golden model built with exactly those
    sixteen weights zeroed.
    """
    p = await reset(dut)
    n_neurons, n_axons = await geometry(p)
    weights = make_weights(n_axons, n_neurons)
    words = pack_words(weights, n_neurons)

    await state_clr(p)
    await configure(p, CFG)
    await wr(p, ADDR["CTRL"], 0)                  # scrubber off
    await wr(p, ADDR["W_ADDR"], 0)
    await wr(p, ADDR["ECC_INJ"], INJ_DOUBLE)
    await wr(p, ADDR["W_DATA_LO"], words[0] & 0xFFFFFFFF)
    await wr(p, ADDR["W_DATA_HI"], (words[0] >> 32) & 0xFFFFFFFF)

    assert await rd(p, ADDR["CNT_DED"]) == 1, "the double error must be seen"
    assert await rd(p, ADDR["CNT_SEC"]) == 0, "and never miscorrected"
    assert uo(dut, DED) == 1 and uo(dut, SEC) == 0
    assert (await rd(p, ADDR["STATUS"])) & ST_DED_SEEN
    assert await rd(p, ADDR["FAULT_ADDR"]) == 0, "FAULT_ADDR latches the word"

    for word in words[1:]:
        await wr(p, ADDR["W_DATA_LO"], word & 0xFFFFFFFF)
        await wr(p, ADDR["W_DATA_HI"], (word >> 32) & 0xFFFFFFFF)
    await wr(p, ADDR["CTRL"], CTRL_EN)

    poisoned = [row[:] for row in weights]
    for m in range(16):                            # word 0 = flat indices 0..15
        poisoned[m // n_neurons][m % n_neurons] = 0
    core = LIFCore(n_neurons, n_axons, poisoned, CFG)
    assert await run_frames(p, FRAMES) == core.run_frames(FRAMES), \
        "an uncorrectable word must contribute zero, not garbage (E10)"

    await wr(p, ADDR["FAULT_CLR"], FCLR_DED)
    await wr(p, ADDR["STATUS_CLR"], ST_DED_SEEN)
    assert await rd(p, ADDR["CNT_DED"]) == 0
    assert uo(dut, DED) == 0


@cocotb.test()
async def test_tmr_masks_a_corrupted_config_replica(dut):
    """A corrupted configuration replica is masked, counted, and harmless.

    The same inference is run twice: once clean, once with a bit of one
    voter replica held wrong. The spike streams must be identical, the
    software-visible configuration must be identical, and the fault must
    still be counted -- docs/08 section 2.3 requires a silently repaired
    upset to reach telemetry.
    """
    p = await reset(dut)
    n_neurons, n_axons = await geometry(p)
    weights = make_weights(n_axons, n_neurons)

    await bring_up(p, weights, n_neurons)
    core = LIFCore(n_neurons, n_axons, weights, CFG)
    clean = await run_frames(p, FRAMES)
    assert clean == core.run_frames(FRAMES)
    assert await rd(p, ADDR_CNT_TMR) == 0 and uo(dut, TMR) == 0

    # bit 3 of the voted vector is CFG_THRESH bit 3; corrupt replica B
    await bring_up(p, weights, n_neurons)
    await wr(p, ADDR_TMR_INJ, (0b10 << 8) | 3)
    assert await rd(p, ADDR["CFG_THRESH"]) == CFG.thresh, \
        "software must read the voted value, not the corrupted replica"
    assert await rd(p, ADDR_CNT_TMR) == 1, "the masked upset must be counted"
    assert uo(dut, TMR) == 1

    core = LIFCore(n_neurons, n_axons, weights, CFG)
    masked = await run_frames(p, FRAMES)
    assert masked == core.run_frames(FRAMES) == clean, \
        "TMR must make the corrupted replica invisible to the datapath"

    # every replica can be selected, and clearing works
    for rep in (0b01, 0b11):
        await wr(p, ADDR_TMR_INJ, (rep << 8) | 5)
        assert await rd(p, ADDR["CFG_THRESH"]) == CFG.thresh
    await wr(p, ADDR_TMR_INJ, 0)
    await wr(p, ADDR["FAULT_CLR"], FCLR_CNT_TMR)
    assert await rd(p, ADDR_CNT_TMR) == 0 and uo(dut, TMR) == 0


@cocotb.test()
async def test_fsm_upset_reaches_status_and_the_err_pin(dut):
    """An upset in the neuron core's state register is host-visible.

    lif_core encodes its control FSM in five Hamming-distance-2 words, so
    a single-bit upset always lands on a word no legal transition can
    produce. The core then parks in S_SAFE, freezes the neuron state file
    and raises err_cfg (docs/10 section 11.4). That is precisely the
    single-event-upset signature this pilot exists to demonstrate, so it
    has to be visible from outside: STATUS.ERR_CFG and the ERR pin, both
    checked here through the serial port and the output pins.

    This is the one test in this file that reaches into the hierarchy,
    and it has to: there is no pin that injects an upset, and a
    demonstrator that cannot be provoked in simulation is a claim rather
    than a result. Only the STIMULUS is internal. Every observation below
    is made exactly as a bench would make it.
    """
    p = await reset(dut)
    n_neurons, n_axons = await geometry(p)
    weights = make_weights(n_axons, n_neurons)
    await bring_up(p, weights, n_neurons)

    assert not (await rd(p, ADDR["STATUS"])) & ST_ERR_CFG
    assert uo(dut, ERR) == 0, "nothing has gone wrong yet"

    # S_IDLE is 4'b0000 and every legal encoding has even parity, so
    # flipping one bit is guaranteed to produce an illegal word.
    await RisingEdge(dut.clk)
    dut.u_pilot.u_lif.state.value = 0b0001
    for _ in range(3):
        await RisingEdge(dut.clk)

    assert (await rd(p, ADDR["STATUS"])) & ST_ERR_CFG, \
        "an illegal FSM state must set STATUS.ERR_CFG"
    assert uo(dut, ERR) == 1, "and must light the ERR pin"
    assert (await rd(p, ADDR["STATUS"])) & ST_BUSY, \
        "a parked core never returns to idle, so BUSY stays high"

    # STATUS_CLR must not appear to clear it: the flag is latched inside
    # lif_core until that block is reset, and the core is still parked.
    await wr(p, ADDR["STATUS_CLR"], ST_ERR_CFG)
    assert (await rd(p, ADDR["STATUS"])) & ST_ERR_CFG, \
        "STATUS_CLR must not hide a fault that is still present"
    assert uo(dut, ERR) == 1

    # The parked core does no work: an event pushed now emits nothing.
    await wr(p, ADDR["EVQ_IN"], TYPE_SPIKE | 1)
    for _ in range(50):
        await RisingEdge(dut.clk)
    assert uo(dut, AER_OUT_VLD) == 0, "a parked core must not emit"
    assert (await rd(p, ADDR["EVQ_OUT"])) & (1 << 31) == 0

    # CTRL.SOFT_RST is the documented recovery: it resets the core, the
    # queues and the dispatcher, and keeps the configuration and the
    # neuron state file (which is not on the reset net).
    await wr(p, ADDR["CTRL"], CTRL_SOFT_RST)
    assert not (await rd(p, ADDR["STATUS"])) & ST_BUSY, \
        "SOFT_RST must un-park the core"

    # The live fault is gone, the record of it is not. A chip built to
    # measure upset rates must not lose an upset to its own recovery, so
    # the bit stays until the operator says "recorded".
    assert (await rd(p, ADDR["STATUS"])) & ST_ERR_CFG, \
        "SOFT_RST must not erase the evidence that an upset happened"
    assert uo(dut, ERR) == 1
    await wr(p, ADDR["STATUS_CLR"], ST_ERR_CFG)
    assert not (await rd(p, ADDR["STATUS"])) & ST_ERR_CFG, \
        "once the core is running again, STATUS_CLR clears the record"
    assert uo(dut, ERR) == 0

    # and the chip works again, bit for bit
    await wr(p, ADDR["CTRL"], CTRL_EN)
    core = LIFCore(n_neurons, n_axons, weights, CFG)
    assert await run_frames(p, FRAMES) == core.run_frames(FRAMES), \
        "the core must be fully functional after the recovery reset"


@cocotb.test()
async def test_parked_core_holds_err_cfg_on_the_live_term(dut):
    """STATUS.ERR_CFG holds on lif_err_cfg itself, not on the sticky flop.

    pilot_top.v section 7 builds STATUS.ERR_CFG out of two sources and
    says what each one buys. The test above proves the LATCHED half: the
    record of an upset survives CTRL.SOFT_RST, the recovery for that
    exact fault. It does not prove the LIVE half, and no sequence of pin
    activity can, because while the core is parked

        if (lif_err_cfg) sticky_errcfg <= 1'b1;

    re-arms the sticky flop on every clock edge and, sitting later in the
    same always block, beats the STATUS_CLR clear above it. The sticky
    term alone therefore answers every host-visible stimulus, and
    reverting `err_cfg_any` to `sticky_errcfg` passes the rest of this
    suite -- measured, 21 of 21. That makes the live term untested, not
    unnecessary; this test closes that gap.

    Two independent observations separate the terms, and each one kills
    the `err_cfg_any = sticky_errcfg` mutant on its own:

      1. Timing, from the pins alone. lif_core registers err_cfg on the
         clock edge that takes its FSM into S_SAFE; pilot_top samples
         that output one edge later. In the cycle between the two, the
         ERR pin is already high while the sticky flop is still zero, so
         that cycle is driven by the live term and by nothing else.
      2. A clear the re-arm cannot undo. Holding sticky_errcfg at zero is
         what a STATUS_CLR would achieve if the re-arm did not exist.
         STATUS.ERR_CFG and the ERR pin must stay asserted through it,
         because the core is still parked and reporting a parked core as
         recovered is the failure section 7 exists to prevent.

    Like the test above, the stimulus reaches into the hierarchy because
    no pin injects an upset. This one also forces one internal flop, for
    observation 2, and that force is the whole of the deviation: every
    value it checks is read at a pin or over the serial port.
    """
    p = await reset(dut)
    n_neurons, n_axons = await geometry(p)
    weights = make_weights(n_axons, n_neurons)
    await bring_up(p, weights, n_neurons)

    assert uo(dut, ERR) == 0, "nothing has gone wrong yet"
    assert int(dut.u_pilot.sticky_errcfg.value) == 0

    # ---- observation 1: the cycle the latch has not closed yet --------
    # S_IDLE is 4'b0000 and every legal encoding has even parity, so
    # flipping one bit is guaranteed to produce an illegal word.
    await RisingEdge(dut.clk)
    dut.u_pilot.u_lif.state.value = 0b0001

    await RisingEdge(dut.clk)          # lif_core parks and raises err_cfg
    await Timer(1, unit="ns")          # settle the combinational pin
    assert int(dut.u_pilot.sticky_errcfg.value) == 0, \
        "the sticky latch cannot have closed yet -- it samples err_cfg " \
        "one edge later; if it has, this observation is measuring nothing"
    assert uo(dut, ERR) == 1, \
        "the ERR pin must rise in the cycle the core parks, on the live " \
        "lif_err_cfg term, before the sticky flop has seen anything"

    await RisingEdge(dut.clk)          # now the latch closes
    await Timer(1, unit="ns")
    assert int(dut.u_pilot.sticky_errcfg.value) == 1, \
        "and one edge later the fault is recorded in the sticky flop too"

    await realign(dut)

    # ---- observation 2: a STATUS_CLR that does reach the sticky flop --
    # The write is the real host action; the force is what makes it take
    # effect, standing in for the re-arm that would otherwise cancel it.
    # The core is still parked throughout.
    await wr(p, ADDR["STATUS_CLR"], ST_ERR_CFG)
    dut.u_pilot.sticky_errcfg.value = Force(0)
    await RisingEdge(dut.clk)
    assert int(dut.u_pilot.sticky_errcfg.value) == 0, \
        "the force did not take: this observation needs the sticky term " \
        "out of the way to say anything about the live one"

    assert (await rd(p, ADDR["STATUS"])) & ST_ERR_CFG, \
        "with the sticky term cleared and the core still parked, " \
        "STATUS.ERR_CFG must be held by lif_err_cfg alone"
    assert uo(dut, ERR) == 1, "and the ERR pin with it"
    assert (await rd(p, ADDR["STATUS"])) & ST_BUSY, \
        "the core really is still parked, so the report above is honest"

    # Releasing leaves the flop at zero; the re-arm sets it again on the
    # next edge, which is the behaviour the force was standing in for.
    dut.u_pilot.sticky_errcfg.value = Release()
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.u_pilot.sticky_errcfg.value) == 1, \
        "a parked core re-arms the sticky flop every cycle"

    await realign(dut)

    # SOFT_RST still recovers, so nothing above left the design wedged.
    await wr(p, ADDR["CTRL"], CTRL_SOFT_RST)
    assert not (await rd(p, ADDR["STATUS"])) & ST_BUSY
    await wr(p, ADDR["STATUS_CLR"], ST_ERR_CFG)
    assert not (await rd(p, ADDR["STATUS"])) & ST_ERR_CFG
    assert uo(dut, ERR) == 0


# The dispatcher gives up after FETCH_WAIT_MAX = 63 cycles, so the wait
# below is bounded by 64 plus the cycle the deposit lands in. The poll is
# given eight times that: the assertion this test makes is "the wait is
# bounded", not "the bound is exactly 63", so a later change to
# FETCH_WAIT_MAX must not have to touch this file, while an unbounded
# wait must still fail here rather than run into a suite timeout.
FETCH_TIMEOUT_POLL = 512


@cocotb.test()
async def test_dispatcher_stranded_in_fetch_recovers_and_is_flagged(dut):
    """A dispatcher stranded in D_FETCH gives up, and says so.

    This is the regression test for the one failure class the pilot
    exists to rule out, found by the fault-injection campaign of docs/16
    section 5.1 and fixed in pilot_top.v section 8.

    The dispatcher requests a queue read in D_IDLE and waits for it in
    D_FETCH. `fi_rd_en` is asserted from the D_IDLE arm and nowhere
    else, so a single-bit upset that lands the FSM in D_FETCH without a
    read outstanding is waiting for a grant that will never be
    requested. Before the fix D_FETCH had exactly one exit,
    `if (fi_rd_valid)`, so that dispatcher waited forever: STATUS.BUSY
    stuck high, every further event refused, and -- measured against the
    pre-fix RTL, not assumed -- no fault flag, no counter and no fault
    pin. Five of 255 injections reached it, from two independent
    targets. The fix bounds the wait, returns to D_IDLE and pulses
    `fetch_timeout`, which latches `sticky_errcfg`.

    The deposit below is exactly the campaign's: `dstate` = D_FETCH
    (2'b01), landing 3 ns after a clock edge, with the input queue empty
    so no read is or can be outstanding. An on-edge deposit is
    overwritten by that same edge's non-blocking update before anything
    samples it, which is why the offset is not cosmetic.

    Four host-visible results, and this test checks only those:

      1. BUSY clears by itself inside a bounded number of cycles, with
         no CTRL.SOFT_RST and no host action of any kind;
      2. STATUS.ERR_CFG is set, so the recovery is recorded instead of
         being silent -- and, the core not being parked, STATUS_CLR
         clears it, which is what distinguishes this from the latched
         live term of the test above;
      3. the ERR pin is high, so a logic analyser sees it with no
         serial frame at all;
      4. the pilot then accepts events again and reproduces sw/golden
         spike for spike and neuron for neuron.

    Like the two tests above, only the STIMULUS reaches into the
    hierarchy -- no pin injects an upset. Every observation below is one
    a bench with an SPI master and a logic analyser could make, so
    reverting the D_FETCH arm to its single-exit form fails check 1 at
    the BUSY poll rather than fails an internal-signal assertion.
    """
    p = await reset(dut)
    n_neurons, n_axons = await geometry(p)
    weights = make_weights(n_axons, n_neurons)
    await bring_up(p, weights, n_neurons)

    st = await rd(p, ADDR["STATUS"])
    assert st & ST_IN_EMPTY, \
        "the deposit needs an empty input queue, or a read could be " \
        "granted and the dispatcher would not be stranded at all"
    assert not st & ST_BUSY, "the pilot must be idle before the upset"
    assert not st & ST_ERR_CFG and uo(dut, ERR) == 0, \
        "nothing has gone wrong yet"

    # ---- the upset: D_FETCH with no read outstanding -----------------
    await RisingEdge(dut.clk)
    await Timer(3, unit="ns")
    dut.u_pilot.dstate.value = 0b01                 # D_FETCH
    await Timer(1, unit="ns")
    assert uo(dut, BUSY) == 1, \
        "the deposit did not take: BUSY is driven by dstate != D_IDLE, " \
        "so a stranded dispatcher must show BUSY immediately"

    # ---- 1. BUSY clears on its own, inside a bound -------------------
    for waited in range(1, FETCH_TIMEOUT_POLL + 1):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if uo(dut, BUSY) == 0:
            break
    else:
        raise AssertionError(
            f"the dispatcher never left D_FETCH: BUSY still high "
            f"{FETCH_TIMEOUT_POLL} cycles after an upset put the FSM "
            f"there with no read outstanding. That is the silent "
            f"deadlock of docs/16 section 5.1 -- the pilot is wedged "
            f"with nothing flagged and only CTRL.SOFT_RST recovers it.")
    dut._log.info(f"the dispatcher gave up after {waited} cycles")

    # The sticky flop samples fetch_timeout on the edge after the pulse,
    # so ERR follows BUSY's fall by one cycle.
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    # ---- 2 and 3. the recovery is recorded, and reaches the pin ------
    assert uo(dut, ERR) == 1, \
        "a bounded wait that recovers silently is still a silent " \
        "failure: the ERR pin must report it with no serial frame"
    await realign(dut)
    assert (await rd(p, ADDR["STATUS"])) & ST_ERR_CFG, \
        "the abandoned fetch must latch STATUS.ERR_CFG"

    # The core was never parked, so this is a plain sticky and the host
    # can acknowledge it -- unlike the parked-core case above, where the
    # live term deliberately refuses the clear.
    await wr(p, ADDR["STATUS_CLR"], ST_ERR_CFG)
    assert not (await rd(p, ADDR["STATUS"])) & ST_ERR_CFG, \
        "with the dispatcher running again, STATUS_CLR clears the record"
    assert uo(dut, ERR) == 0

    # ---- 4. and the pilot works, bit for bit -------------------------
    core = LIFCore(n_neurons, n_axons, weights, CFG)
    expected = core.run_frames(FRAMES)
    got = await run_frames(p, FRAMES)
    assert any(step for step in expected), \
        "the follow-up stimulus must actually produce spikes"
    assert got == expected, \
        f"the dispatcher must dispatch again after the timeout: " \
        f"rtl {got}, golden {expected}"
    await check_state(p, core, n_neurons)

    st = await rd(p, ADDR["STATUS"])
    assert not st & (ST_ERR_CFG | ST_DED_SEEN | ST_OVF_SEEN), \
        f"the recovered run raised a new flag: STATUS {st:#x}"


# ---------------------------------------------------------------------
# 6. register-map conformance
# ---------------------------------------------------------------------
@cocotb.test()
async def test_fault_clr_bit_assignment(dut):
    """FAULT_CLR is regmap/regmap.yaml's, bit for bit.

    The map allocates five bits in fault-block offset order -- b0
    CNT_SEC, b1 CNT_DED, b2 CNT_EVQ_OVF, b3 CNT_AXON_OOR, b4 FAULT_ADDR
    -- and this pilot implements all five with those meanings. CNT_TMR is
    a pilot-only register (pilot_top.v section 5) and takes b5, the first
    bit the map leaves free.

    The pair that an overload of b4 would confuse is checked together:
    b4 must clear FAULT_ADDR and leave CNT_TMR alone, b5 must do the
    opposite, and neither may disturb the ECC counters.
    """
    p = await reset(dut)

    # A double-bit error at a NON-zero weight-word index, so that a
    # cleared FAULT_ADDR is distinguishable from an uncleared one.
    await wr(p, ADDR["CTRL"], 0)                  # scrubber off
    await wr(p, ADDR["W_ADDR"], 1)
    await wr(p, ADDR["ECC_INJ"], INJ_DOUBLE)
    await wr(p, ADDR["W_DATA_LO"], 0x1234_5678)
    await wr(p, ADDR["W_DATA_HI"], 0x9ABC_DEF0)
    assert await rd(p, ADDR["FAULT_ADDR"]) == 1, "FAULT_ADDR latches W_ADDR"
    assert await rd(p, ADDR["CNT_DED"]) == 1

    # and a masked TMR disagreement, so both counters are non-zero
    await wr(p, ADDR_TMR_INJ, (0b01 << 8) | 7)
    assert await rd(p, ADDR_CNT_TMR) == 1 and uo(dut, TMR) == 1

    # b4 is FAULT_ADDR, not CNT_TMR
    await wr(p, ADDR["FAULT_CLR"], FCLR_FAULT_ADDR)
    assert await rd(p, ADDR["FAULT_ADDR"]) == 0, \
        "FAULT_CLR b4 must clear FAULT_ADDR (regmap.yaml)"
    assert await rd(p, ADDR_CNT_TMR) == 1, \
        "FAULT_CLR b4 must not clear the pilot-only TMR counter"
    assert uo(dut, TMR) == 1
    assert await rd(p, ADDR["CNT_DED"]) == 1, "b4 must not touch CNT_DED"

    # b5 is CNT_TMR, and only that
    await wr(p, ADDR["FAULT_CLR"], FCLR_CNT_TMR)
    assert await rd(p, ADDR_CNT_TMR) == 0 and uo(dut, TMR) == 0
    assert await rd(p, ADDR["CNT_DED"]) == 1, "b5 must not touch CNT_DED"

    # the remaining normative bits, so the whole assignment is covered
    await wr(p, ADDR["FAULT_CLR"], FCLR_DED)
    assert await rd(p, ADDR["CNT_DED"]) == 0
    await wr(p, ADDR_TMR_INJ, 0)
