# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""soc_busstat suite: the counters that make a corrected upset visible.

WHERE THE EXPECTATIONS COME FROM. Not from the RTL:

  * `docs/43-core-hardening.md` section 6.5 and section 10, which state
    the requirement this block exists to meet: a corrected upset must be
    distinguishable, from outside the part, from no upset at all. What
    follows from that is what a telemetry counter has to do -- never
    lose an event, never wrap silently, survive the reset it explains,
    and be readable by software through the frozen map.
  * `docs/41-watchdog-hardening.md` section 10 item 3, which named the
    second source in its own words: "Nothing raises an alarm on TMRERR.
    The mismatch is counted and sticky in a register and that is all. A
    fault line into BUSSTAT, or a fast interrupt, is the obvious next
    step and neither exists."
  * `docs/40-interrupts-timers-watchdog.md` section 7.2, which is where
    the two-reset-domain requirement comes from: a fault mechanism that
    survives the reset it caused and re-fires on the fresh boot is a
    brick, and this project built one once.
  * The AMBA 3 APB slave contract soc_uart.v and soc_gptimer.v already
    obey: PREADY high, PSLVERR low, one ACCESS cycle per transfer.
  * `sw/golden/memmap_gen.py`, generated from `regmap/memmap.yaml`, for
    the slot and the interrupt line. No address literal for the block's
    base appears below.

The RTL was read for the port names and for the fact that the resets are
active low. The register OFFSETS inside the slot are this project's own
and are written here because here is where they are defined -- the same
position `test_soc_wdog.py` takes for the watchdog's.

WHAT THIS SUITE DOES NOT COVER
------------------------------
  * That the event wires are CONNECTED to anything. Every test below
    drives them by hand. A block whose inputs are stubbed passes every
    one of these, which is precisely the failure `pilot_top.v` shipped
    once -- four ECC status wires left unconnected while every proof and
    every test stayed green. The connection is checked by
    `sw/tests/test_soc_regfile_guards.py` and demonstrated end to end by
    the SoC run of `docs/44` section 8.2.
  * That CNT_RFSEC is the upset RATE. That is a property of the register
    file's scrub, measured in `docs/44` section 7, not of this block.
  * Any fault model. This block is unprotected: no code, no replication.
    An upset in a counter corrupts a number.
  * Gate-level behaviour, timing, X-propagation and power.
"""

import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "sw"))
from golden.memmap_gen import APB_SLOTS, IRQ_SOURCES  # noqa: E402

# Register offsets inside the 4 KiB slot.
STATUS = 0x000
IRQEN = 0x004
CNT_RFSEC = 0x008
CNT_RFRD = 0x00C
CNT_RFDED = 0x010
CNT_TMRERR = 0x014
CLR = 0x018
# docs/55's three, added above CLR rather than displacing it: CLR's
# offset is in hw/soc/tb/sw/soc_timers.h and in every program written
# against this block.
CNT_NPUCOR = 0x01C
CNT_NPUDET = 0x020
CNT_NPUTMR = 0x024
# docs/58's one, the CLINT's mtime codeword. Same rule again: nothing
# below it moves.
CNT_MTECC = 0x028

# Bit index of each source, shared by STATUS, IRQEN and CLR.
S_RFSEC, S_RFRD, S_RFDED, S_TMRERR = 0, 1, 2, 3
S_NPUCOR, S_NPUDET, S_NPUTMR = 4, 5, 6
# docs/58. THE LAST BIT BELOW THE INTERRUPT: STATUS puts irq_o at bit 8
# and soc_busstat.v's read multiplexer forbids moving it, so the sticky
# field is now full and a ninth source cannot be added below it.
S_MTECC = 7
NSRC = 8
STATUS_IRQ = 8

CNT_MAX = 0xFFFF          # CNT_W = 16, saturating

CLK_NS = 10


def val(sig):
    s = str(sig.value)
    if any(c not in "01" for c in s):
        raise AssertionError("non-binary value {!r} on {}".format(s, sig._path))
    return int(s, 2)


async def setup(dut):
    """Clock, then a power-on reset that also asserts the system reset.

    Every test starts its own clock. `test_soc_wdog_win.py` records what
    the other arrangement cost: a cocotb coroutine started by one test is
    killed when that test ends, so a later test that relied on it ran
    with no clock at all and hung rather than failed, taking seven tests
    down with it and reporting them as failures with 0 ns of simulated
    time.
    """
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, units="ns").start())
    dut.rst_por_ni.value = 0
    dut.rst_ni.value = 0
    dut.psel_i.value = 0
    dut.penable_i.value = 0
    dut.paddr_i.value = 0
    dut.pwrite_i.value = 0
    dut.pwdata_i.value = 0
    dut.rf_ecc_err_i.value = 0
    dut.tmr_ev_i.value = 0
    dut.mt_ecc_i.value = 0
    dut.npu_cor_i.value = 0
    dut.npu_det_i.value = 0
    dut.npu_tmr_i.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk_i)
    dut.rst_por_ni.value = 1
    dut.rst_ni.value = 1
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")


async def apb_write(dut, addr, data):
    await RisingEdge(dut.clk_i)
    dut.psel_i.value = 1
    dut.penable_i.value = 0
    dut.paddr_i.value = addr
    dut.pwrite_i.value = 1
    dut.pwdata_i.value = data
    await RisingEdge(dut.clk_i)
    dut.penable_i.value = 1
    await Timer(1, units="ns")
    assert val(dut.pready_o) == 1, "PREADY low: this block always completes"
    assert val(dut.pslverr_o) == 0, "PSLVERR high: this block never errors"
    await RisingEdge(dut.clk_i)
    dut.psel_i.value = 0
    dut.penable_i.value = 0
    dut.pwrite_i.value = 0
    await Timer(1, units="ns")


async def apb_read(dut, addr):
    await RisingEdge(dut.clk_i)
    dut.psel_i.value = 1
    dut.penable_i.value = 0
    dut.paddr_i.value = addr
    dut.pwrite_i.value = 0
    await RisingEdge(dut.clk_i)
    dut.penable_i.value = 1
    await Timer(1, units="ns")
    assert val(dut.pready_o) == 1
    assert val(dut.pslverr_o) == 0
    v = val(dut.prdata_o)
    await RisingEdge(dut.clk_i)
    dut.psel_i.value = 0
    dut.penable_i.value = 0
    await Timer(1, units="ns")
    return v


async def pulse(dut, sig_setter, n=1):
    """Raise an event line for n clocks, then drop it."""
    for _ in range(n):
        await RisingEdge(dut.clk_i)
        await Timer(1, units="ns")
        sig_setter(1)
        await RisingEdge(dut.clk_i)
        await Timer(1, units="ns")
        sig_setter(0)
    await Timer(1, units="ns")


def rf(dut, bit):
    def setter(v):
        dut.rf_ecc_err_i.value = (v << bit) if v else 0
    return setter


def tmr(dut):
    def setter(v):
        dut.tmr_ev_i.value = v
    return setter


def mtecc(dut):
    """docs/58's line: the CLINT's stored mtime codeword was not a
    codeword this cycle."""
    def setter(v):
        dut.mt_ecc_i.value = v
    return setter


def npu(dut, which):
    """One of docs/55's three NPU fault lines, by name.

    They are three ports and not one field for the reason docs/44
    section 6.2 gives and pilot_top.v's header records paying for: a
    corrected queue pointer, a discarded queue entry and a masked vote in
    the NPU's cause bank are three structures with three remedies, and a
    host reading an aggregate could not tell them apart.
    """
    def setter(v):
        getattr(dut, "npu_{}_i".format(which)).value = v
    return setter


@cocotb.test()
async def test_out_of_reset_nothing_is_reported_and_nothing_is_enabled(dut):
    """The reset state a fresh boot must see.

    Everything zero, and specifically the interrupt line low. A part that
    powers on asserting a fault interrupt cannot boot.
    """
    await setup(dut)
    for reg in (STATUS, IRQEN, CNT_RFSEC, CNT_RFRD, CNT_RFDED, CNT_TMRERR,
                CNT_NPUCOR, CNT_NPUDET, CNT_NPUTMR, CNT_MTECC):
        assert await apb_read(dut, reg) == 0, hex(reg)
    assert val(dut.irq_o) == 0


@cocotb.test()
async def test_each_source_counts_its_own_events_and_no_others(dut):
    """Eight counters, eight sources, no cross-talk.

    This is the reason the block has eight counters instead of one:
    pilot_top.v aggregates its two ECC domains into one CNT_SEC and says
    in a comment what that costs -- "a host reading CNT_SEC cannot tell a
    synapse array correction from a load-path one".

    Every count in the plan below is a DIFFERENT number on purpose. Equal
    counts would pass on a block whose sources all drove one counter,
    which is the exact defect the separation exists to prevent.
    """
    await setup(dut)
    plan = [(S_RFSEC, rf(dut, 0), CNT_RFSEC, 3),
            (S_RFRD, rf(dut, 1), CNT_RFRD, 5),
            (S_RFDED, rf(dut, 2), CNT_RFDED, 2),
            (S_TMRERR, tmr(dut), CNT_TMRERR, 7),
            (S_NPUCOR, npu(dut, "cor"), CNT_NPUCOR, 11),
            (S_NPUDET, npu(dut, "det"), CNT_NPUDET, 4),
            (S_NPUTMR, npu(dut, "tmr"), CNT_NPUTMR, 9),
            (S_MTECC, mtecc(dut), CNT_MTECC, 13)]
    for _, setter, _, n in plan:
        await pulse(dut, setter, n)
    for src, _, reg, n in plan:
        assert await apb_read(dut, reg) == n, "source {} counted wrong".format(src)
    assert await apb_read(dut, STATUS) & ((1 << NSRC) - 1) == (1 << NSRC) - 1


@cocotb.test()
async def test_a_sticky_survives_a_system_reset_and_the_enable_does_not(dut):
    """docs/40 section 7.2's brick, not rebuilt.

    The RECORD is in the power-on domain, because the most valuable
    reading of an upset counter is the one taken after the watchdog reset
    it explains. The INTERRUPT ENABLE is in the system domain, because a
    fault line that survived that reset with its enable intact would
    re-enter a handler the fresh boot has not installed yet -- which is
    the failure docs/40 spent a section on.
    """
    await setup(dut)
    await pulse(dut, rf(dut, 0), 4)
    await apb_write(dut, IRQEN, 1 << S_RFSEC)
    assert val(dut.irq_o) == 1

    # A watchdog stage-2 reset: system reset asserted, power-on not.
    dut.rst_ni.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    assert val(dut.irq_o) == 0, \
        "the fresh boot is interrupted by the fault that reset it"
    dut.rst_ni.value = 1
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")

    assert await apb_read(dut, IRQEN) == 0, "the enable survived a reset"
    assert await apb_read(dut, CNT_RFSEC) == 4, "the record did not survive"
    assert await apb_read(dut, STATUS) & (1 << S_RFSEC) != 0


@cocotb.test()
async def test_clearing_one_source_leaves_the_others_standing(dut):
    """CLR is per source. A frame that zeroes one counter to start a new
    interval must not zero the interval of another."""
    await setup(dut)
    await pulse(dut, rf(dut, 0), 3)
    await pulse(dut, tmr(dut), 6)
    await apb_write(dut, CLR, 1 << S_RFSEC)
    assert await apb_read(dut, CNT_RFSEC) == 0
    assert await apb_read(dut, CNT_TMRERR) == 6
    st = await apb_read(dut, STATUS)
    assert st & (1 << S_RFSEC) == 0
    assert st & (1 << S_TMRERR) != 0


@cocotb.test()
async def test_an_event_in_the_cycle_of_its_own_clear_is_not_lost(dut):
    """The race a telemetry counter has to lose in the right direction.

    An upset that arrives on exactly the cycle software zeroes the
    counter is the one a naive clear drops, and it is not a rare cycle:
    it is the cycle the telemetry frame is being built. The block
    resolves it in favour of the event, so the count comes back one and
    the sticky stays set.
    """
    await setup(dut)
    await pulse(dut, rf(dut, 0), 2)
    # Drive the event high across the whole write so it is high in the
    # ACCESS cycle, which is the cycle the clear strobe exists in.
    dut.rf_ecc_err_i.value = 1 << S_RFSEC
    await apb_write(dut, CLR, 1 << S_RFSEC)
    dut.rf_ecc_err_i.value = 0
    await Timer(1, units="ns")
    assert await apb_read(dut, CNT_RFSEC) == 1, \
        "an event was lost to its own clear"
    assert await apb_read(dut, STATUS) & (1 << S_RFSEC) != 0


@cocotb.test()
async def test_the_counter_saturates_rather_than_wrapping(dut):
    """A wrapped counter is indistinguishable from one that barely moved.

    Driven to the top by holding the line high, which the RTL counts once
    per cycle. The number is CNT_W's, read from nothing: 16 bits is what
    soc_top.v instantiates and 0xFFFF is what saturation means.
    """
    await setup(dut)
    dut.rf_ecc_err_i.value = 1 << S_RFDED
    for _ in range(CNT_MAX + 40):
        await RisingEdge(dut.clk_i)
    dut.rf_ecc_err_i.value = 0
    await Timer(1, units="ns")
    assert await apb_read(dut, CNT_RFDED) == CNT_MAX, \
        "the counter wrapped instead of saturating"


@cocotb.test()
async def test_the_interrupt_is_the_enabled_stickies_and_is_a_level(dut):
    """A one-cycle pulse on a fast interrupt line is a pulse the core can
    be in the middle of a trap for, so the line is driven from the STICKY
    and the handler deasserts it by clearing. The same acknowledge
    discipline the watchdog's stage 1 uses."""
    await setup(dut)
    await apb_write(dut, IRQEN, 1 << S_TMRERR)
    assert val(dut.irq_o) == 0

    await pulse(dut, rf(dut, 0), 1)
    assert val(dut.irq_o) == 0, "an unenabled source raised the line"

    await pulse(dut, tmr(dut), 1)
    assert val(dut.irq_o) == 1
    for _ in range(20):
        await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    assert val(dut.irq_o) == 1, "the line is a pulse, not a level"
    assert await apb_read(dut, STATUS) & (1 << STATUS_IRQ) != 0

    await apb_write(dut, CLR, 1 << S_TMRERR)
    assert val(dut.irq_o) == 0, "clearing the sticky did not deassert"


@cocotb.test()
async def test_an_offset_that_names_no_register_reads_zero(dut):
    """GRLIB's documented behaviour for unoccupied space behind a bridge,
    and soc_uart.v's. CLR is write-only and reads zero for its own
    reason: a strobe that reads back invites software to treat it as
    state."""
    await setup(dut)
    await pulse(dut, rf(dut, 0), 1)
    assert await apb_read(dut, CLR) == 0
    for off in (0x028, 0x100, 0xFFC):
        assert await apb_read(dut, off) == 0, hex(off)
    assert await apb_read(dut, CNT_RFSEC) == 1, \
        "a read of an unoccupied offset disturbed a counter"


@cocotb.test()
async def test_a_read_never_counts_and_never_clears(dut):
    """The clear is a WRITE to CLR. A read of it, or a write to any other
    offset, must leave the record alone -- otherwise a telemetry poll
    would erase what it polled."""
    await setup(dut)
    await pulse(dut, rf(dut, 0), 5)
    for _ in range(3):
        await apb_read(dut, CNT_RFSEC)
        await apb_read(dut, STATUS)
    await apb_write(dut, CNT_RFSEC, 0xFFFFFFFF)
    await apb_write(dut, STATUS, 0xFFFFFFFF)
    assert await apb_read(dut, CNT_RFSEC) == 5, \
        "the record was disturbed by reads or by a write to a read-only word"


@cocotb.test()
async def test_the_slot_and_the_line_are_the_frozen_maps(dut):
    """The block is only reachable if it is where the map says it is.

    This asserts against the GENERATED map rather than against a literal,
    so a change to regmap/memmap.yaml fails here rather than in silicon.
    """
    await setup(dut)
    _base, slot, irq, status = APB_SLOTS["BUSSTAT"]
    assert slot == 0x015
    assert irq == 22
    assert status == "implemented", \
        "BUSSTAT is decoded by soc_top.v but the map still calls it reserved"
    assert IRQ_SOURCES["BUSSTAT"][1] == 10, "the fast interrupt line moved"
