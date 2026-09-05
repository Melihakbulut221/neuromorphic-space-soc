"""soc_scrub suite: the memory codec's counters and the scrubbers' control.

WHERE THE EXPECTATIONS COME FROM. Not from the RTL:

  * `docs/67`, which puts a SECDED code and a scrubber under both
    memories and needs, per memory, the same three quantities
    soc_busstat.v's header argued must never be folded into one: rows
    the scrubber REPAIRED (the upset rate), reads that returned a
    CORRECTED word (the scrub-interval signature), and UNCORRECTABLE
    syndromes, with the address of the last of those.
  * `docs/43` section 6.5 and `docs/44`, for what a telemetry counter has
    to do: never lose an event, never wrap silently, survive the reset
    it explains, and be readable through the frozen map.
  * `docs/44` section 11's rule that a mechanism which ships disabled is
    a liability: the scrubbers are ENABLED out of reset and software may
    slow or stop them.
  * The AMBA 3 APB slave contract soc_busstat.v obeys.
  * `sw/golden/memmap_gen.py`, generated from `regmap/memmap.yaml`, for
    the slot and the line. No address literal for the block's base
    appears below.

The register OFFSETS inside the slot are this block's own and are
written here because here is where they are defined, exactly as
test_soc_busstat.py does for BUSSTAT.

WHAT THIS SUITE DOES NOT COVER
------------------------------
  * That the event wires are CONNECTED to the memories, or that the
    control wires reach the scrubbers. Every test below drives and reads
    the ports by hand. sw/tests/test_soc_memory_guards.py checks the
    connection textually and the whole-SoC campaign of docs/67 section 7
    exercises it end to end.
  * That CNT_RAMSEC is the upset RATE. That is a property of
    soc_mem_ecc.v's scrubber, measured in test_soc_mem.py.
  * Any fault model. This block is unprotected: an upset in a counter
    corrupts a number.
"""

import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "sw"))
from golden.memmap_gen import APB_SLOTS, IRQ_SOURCES  # noqa: E402

STATUS = 0x000
IRQEN = 0x004
CNT_RAMSEC = 0x008
CNT_RAMRD = 0x00C
CNT_RAMDED = 0x010
CNT_ROMSEC = 0x014
CNT_ROMRD = 0x018
CNT_ROMDED = 0x01C
CLR = 0x020
CTRL = 0x024
RAMADDR = 0x028
ROMADDR = 0x02C

S_RAMSEC, S_RAMRD, S_RAMDED, S_ROMSEC, S_ROMRD, S_ROMDED = range(6)
NSRC = 6
STATUS_IRQ = 8
CNT_MAX = 0xFFFF
IVL_RST = 255            # soc_top.v's SCRUB_IVL_RST, the Makefile's default

CLK_NS = 10

SOURCES = {
    S_RAMSEC: ("ram_sec_i", CNT_RAMSEC),
    S_RAMRD: ("ram_rd_i", CNT_RAMRD),
    S_RAMDED: ("ram_ded_i", CNT_RAMDED),
    S_ROMSEC: ("rom_sec_i", CNT_ROMSEC),
    S_ROMRD: ("rom_rd_i", CNT_ROMRD),
    S_ROMDED: ("rom_ded_i", CNT_ROMDED),
}


def val(sig):
    s = str(sig.value)
    if any(c not in "01" for c in s):
        raise AssertionError("non-binary value {!r} on {}".format(s, sig._path))
    return int(s, 2)


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    dut.rst_por_ni.value = 0
    dut.rst_ni.value = 0
    dut.psel_i.value = 0
    dut.penable_i.value = 0
    dut.paddr_i.value = 0
    dut.pwrite_i.value = 0
    dut.pwdata_i.value = 0
    for name, _ in SOURCES.values():
        getattr(dut, name).value = 0
    dut.ram_addr_i.value = 0
    dut.rom_addr_i.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk_i)
    dut.rst_por_ni.value = 1
    dut.rst_ni.value = 1
    await RisingEdge(dut.clk_i)
    await Timer(1, unit="ns")


async def apb_write(dut, addr, data):
    await RisingEdge(dut.clk_i)
    dut.psel_i.value = 1
    dut.penable_i.value = 0
    dut.paddr_i.value = addr
    dut.pwrite_i.value = 1
    dut.pwdata_i.value = data
    await RisingEdge(dut.clk_i)
    dut.penable_i.value = 1
    await Timer(1, unit="ns")
    assert val(dut.pready_o) == 1, "PREADY low: this block always completes"
    assert val(dut.pslverr_o) == 0, "PSLVERR high: this block never errors"
    await RisingEdge(dut.clk_i)
    dut.psel_i.value = 0
    dut.penable_i.value = 0
    dut.pwrite_i.value = 0
    await Timer(1, unit="ns")


async def apb_read(dut, addr):
    await RisingEdge(dut.clk_i)
    dut.psel_i.value = 1
    dut.penable_i.value = 0
    dut.paddr_i.value = addr
    dut.pwrite_i.value = 0
    await RisingEdge(dut.clk_i)
    dut.penable_i.value = 1
    await Timer(1, unit="ns")
    assert val(dut.pready_o) == 1
    assert val(dut.pslverr_o) == 0
    v = val(dut.prdata_o)
    await RisingEdge(dut.clk_i)
    dut.psel_i.value = 0
    dut.penable_i.value = 0
    await Timer(1, unit="ns")
    return v


async def pulse(dut, src, n=1, addr=None):
    """Raise one source's event line for n clocks, one at a time, with
    an address on the memory's address input if given."""
    name, _ = SOURCES[src]
    sig = getattr(dut, name)
    for _ in range(n):
        await RisingEdge(dut.clk_i)
        await Timer(1, unit="ns")
        if addr is not None:
            (dut.ram_addr_i if src < S_ROMSEC else dut.rom_addr_i).value = addr
        sig.value = 1
        await RisingEdge(dut.clk_i)
        await Timer(1, unit="ns")
        sig.value = 0
    await Timer(1, unit="ns")


@cocotb.test()
async def test_out_of_reset_nothing_is_reported_and_the_scrubbers_run(dut):
    """The record is empty, nothing is enabled to interrupt, the line is
    low -- and CTRL says both scrubbers are walking at the reset
    interval. docs/44 section 11: a mechanism that ships disabled and
    has never caught anything is a liability."""
    await setup(dut)
    assert await apb_read(dut, STATUS) == 0
    assert await apb_read(dut, IRQEN) == 0
    for _, off in SOURCES.values():
        assert await apb_read(dut, off) == 0
    assert await apb_read(dut, RAMADDR) == 0
    assert await apb_read(dut, ROMADDR) == 0
    ctrl = await apb_read(dut, CTRL)
    assert ctrl & 1, "the RAM scrubber does not run out of reset"
    assert ctrl & 2, "the ROM scrubber does not run out of reset"
    assert ctrl >> 16 == IVL_RST
    assert val(dut.ram_en_o) == 1 and val(dut.rom_en_o) == 1
    assert val(dut.ivl_o) == IVL_RST
    assert val(dut.irq_o) == 0


@cocotb.test()
async def test_each_source_counts_its_own_events_and_no_others(dut):
    """Six sources, six counters, six stickies. An event on one moves
    its counter by exactly its count and touches none of the other
    five."""
    await setup(dut)
    for src, (_, off) in SOURCES.items():
        await pulse(dut, src, n=src + 1)
        for other, (_, ooff) in SOURCES.items():
            want = other + 1 if other <= src else 0
            got = await apb_read(dut, ooff)
            assert got == want, (
                "after source {} pulsed {} times, counter {} reads {} "
                "(expected {})".format(src, src + 1, other, got, want))
        st = await apb_read(dut, STATUS)
        assert st & ((1 << (src + 1)) - 1) == (1 << (src + 1)) - 1
        assert st & ~((1 << (src + 1)) - 1) == 0, "a sticky set without its event"


@cocotb.test()
async def test_the_uncorrectable_address_is_latched_per_memory(dut):
    """RAMADDR and ROMADDR hold the offset presented with the LAST
    ded event of their memory, are untouched by the other memory's
    events and by SEC/RD events, and are not cleared by CLR: the most
    recent uncorrectable address is the one a handler wants."""
    await setup(dut)
    await pulse(dut, S_RAMDED, addr=0x1234)
    await pulse(dut, S_ROMDED, addr=0x0FF8)
    assert await apb_read(dut, RAMADDR) == 0x1234
    assert await apb_read(dut, ROMADDR) == 0x0FF8
    await pulse(dut, S_RAMSEC, addr=0xBEEF)      # SEC carries no address
    await pulse(dut, S_ROMRD, addr=0xBEEF)
    assert await apb_read(dut, RAMADDR) == 0x1234
    assert await apb_read(dut, ROMADDR) == 0x0FF8
    await pulse(dut, S_RAMDED, addr=0x7FFC)
    assert await apb_read(dut, RAMADDR) == 0x7FFC
    assert await apb_read(dut, ROMADDR) == 0x0FF8
    await apb_write(dut, CLR, (1 << NSRC) - 1)
    assert await apb_read(dut, RAMADDR) == 0x7FFC, "CLR erased an address"
    assert await apb_read(dut, CNT_RAMDED) == 0


@cocotb.test()
async def test_a_sticky_survives_a_system_reset_and_the_enable_and_control_do_not(dut):
    """The record is power-on-domain state and the enable and CTRL are
    system-domain: after a watchdog reset the counters and stickies
    stand, the interrupt is off, and both scrubbers are back at their
    defaults -- the safe direction for a scrubber."""
    await setup(dut)
    await pulse(dut, S_ROMSEC, n=3)
    await apb_write(dut, IRQEN, 1 << S_ROMSEC)
    await apb_write(dut, CTRL, (7 << 16) | 0)      # both off, interval 7
    assert val(dut.irq_o) == 1
    assert val(dut.ram_en_o) == 0 and val(dut.rom_en_o) == 0 and val(dut.ivl_o) == 7
    await RisingEdge(dut.clk_i)
    dut.rst_ni.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk_i)
    await Timer(1, unit="ns")
    assert val(dut.irq_o) == 0, "the interrupt survived the system reset"
    assert val(dut.ram_en_o) == 1 and val(dut.rom_en_o) == 1
    assert val(dut.ivl_o) == IVL_RST
    dut.rst_ni.value = 1
    await RisingEdge(dut.clk_i)
    await Timer(1, unit="ns")
    assert await apb_read(dut, CNT_ROMSEC) == 3, "the counter did not survive"
    assert (await apb_read(dut, STATUS)) & (1 << S_ROMSEC)
    assert await apb_read(dut, IRQEN) == 0
    assert await apb_read(dut, CTRL) == (IVL_RST << 16) | 3


@cocotb.test()
async def test_clearing_one_source_leaves_the_others_standing(dut):
    await setup(dut)
    for src in SOURCES:
        await pulse(dut, src, n=2)
    await apb_write(dut, CLR, 1 << S_RAMRD)
    for src, (_, off) in SOURCES.items():
        want = 0 if src == S_RAMRD else 2
        assert await apb_read(dut, off) == want
    st = await apb_read(dut, STATUS)
    assert st & (1 << S_RAMRD) == 0 and st & 0x3F == 0x3F & ~(1 << S_RAMRD)


@cocotb.test()
async def test_an_event_in_the_cycle_of_its_own_clear_is_not_lost(dut):
    """The event wins: the counter reads one and the sticky is set."""
    await setup(dut)
    await pulse(dut, S_RAMDED, n=5)
    await RisingEdge(dut.clk_i)
    dut.psel_i.value = 1
    dut.penable_i.value = 0
    dut.paddr_i.value = CLR
    dut.pwrite_i.value = 1
    dut.pwdata_i.value = 1 << S_RAMDED
    await RisingEdge(dut.clk_i)
    dut.penable_i.value = 1
    dut.ram_ded_i.value = 1                 # the ACCESS cycle is the clear
    await RisingEdge(dut.clk_i)
    dut.psel_i.value = 0
    dut.penable_i.value = 0
    dut.pwrite_i.value = 0
    dut.ram_ded_i.value = 0
    await Timer(1, unit="ns")
    assert await apb_read(dut, CNT_RAMDED) == 1
    assert (await apb_read(dut, STATUS)) & (1 << S_RAMDED)


@cocotb.test()
async def test_the_counter_saturates_rather_than_wrapping(dut):
    await setup(dut)
    await pulse(dut, S_RAMRD, n=CNT_MAX + 5)
    assert await apb_read(dut, CNT_RAMRD) == CNT_MAX
    assert await apb_read(dut, CNT_RAMSEC) == 0


@cocotb.test()
async def test_the_interrupt_is_the_enabled_stickies_and_is_a_level(dut):
    await setup(dut)
    await pulse(dut, S_ROMDED)
    assert val(dut.irq_o) == 0, "an unenabled sticky raised the line"
    await apb_write(dut, IRQEN, 1 << S_ROMDED)
    assert val(dut.irq_o) == 1
    assert (await apb_read(dut, STATUS)) & (1 << STATUS_IRQ)
    for _ in range(10):
        await RisingEdge(dut.clk_i)
    assert val(dut.irq_o) == 1, "the line is a level, not a pulse"
    await apb_write(dut, CLR, 1 << S_ROMDED)
    assert val(dut.irq_o) == 0, "clearing the sticky did not drop the line"


@cocotb.test()
async def test_the_control_register_reaches_the_scrubbers(dut):
    """CTRL[0], CTRL[1] and CTRL[31:16] are the three control outputs,
    each on its own; the reserved bits read zero."""
    await setup(dut)
    await apb_write(dut, CTRL, (0x0123 << 16) | 0x2)
    assert val(dut.ram_en_o) == 0 and val(dut.rom_en_o) == 1
    assert val(dut.ivl_o) == 0x0123
    assert await apb_read(dut, CTRL) == (0x0123 << 16) | 0x2
    await apb_write(dut, CTRL, 0xFFFF_FFFF)
    assert await apb_read(dut, CTRL) == 0xFFFF_0003, "reserved CTRL bits read back"
    await apb_write(dut, CTRL, 0)
    assert val(dut.ram_en_o) == 0 and val(dut.rom_en_o) == 0 and val(dut.ivl_o) == 0


@cocotb.test()
async def test_an_offset_that_names_no_register_reads_zero(dut):
    await setup(dut)
    await pulse(dut, S_RAMSEC)
    for off in (0x030, 0x100, 0xFFC):
        assert await apb_read(dut, off) == 0
    await apb_write(dut, 0x030, 0xFFFFFFFF)
    assert await apb_read(dut, CNT_RAMSEC) == 1
    assert await apb_read(dut, CTRL) == (IVL_RST << 16) | 3
    assert await apb_read(dut, CLR) == 0, "CLR is write-only and reads zero"


@cocotb.test()
async def test_a_read_never_counts_and_never_clears(dut):
    await setup(dut)
    await pulse(dut, S_ROMRD, n=4)
    for _ in range(5):
        for _, off in SOURCES.values():
            await apb_read(dut, off)
        await apb_read(dut, CLR)
        await apb_read(dut, STATUS)
    assert await apb_read(dut, CNT_ROMRD) == 4


@cocotb.test()
async def test_the_slot_and_the_line_are_the_frozen_maps(dut):
    """The block has no knowledge of its own address; soc_top.v decodes
    the slot and wires the line. Recorded here as the numbers the map
    freezes, so a test reading this file knows what it is looking at."""
    await setup(dut)
    addr, slot, irq, status = APB_SLOTS["SCRUB"]
    assert status == "implemented"
    assert slot == 0x016 and irq == 23
    assert IRQ_SOURCES["SCRUB"][1] == 11, "SCRUB is on fast line 11"
