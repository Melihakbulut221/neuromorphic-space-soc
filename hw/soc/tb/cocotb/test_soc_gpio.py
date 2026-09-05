"""soc_gpio suite: a GRGPIO-shaped port, driven against the specification.

WHERE THE EXPECTATIONS COME FROM. Not from the RTL:

  * grip.pdf chapter 62, GRGPIO -- table 923 for the offsets, tables
    924 to 937 for each register's fields and reset value, and the
    prose of 62.2 for what the interrupt logic does: "If the edge
    register is 0, the interrupt is treated as level sensitive. If the
    polarity register is 0, the interrupt is active low ... If the edge
    register is 1, the interrupt is edge-triggered. The polarity
    register then selects between rising edge (1) or falling edge (0)."
    And for the input path: "The input from each buffer is synchronized
    by two flip-flops in series."
  * The AMBA 3 APB slave contract soc_uart.v, soc_gptimer.v and
    soc_busstat.v already obey: PREADY high, PSLVERR low, one ACCESS
    cycle per transfer.
  * `sw/golden/memmap_gen.py`, generated from `regmap/memmap.yaml`, for
    the slot and the interrupt line. No address literal for the block's
    base appears below.

The RTL was read for the port names and the fact that the reset is
active low. The configuration this block reports in CAP -- one shared
interrupt line, an interrupt flag register, no input enable, no pulse --
is soc_gpio.v's stated choice and the suite checks the choice is
reported truthfully, which is a different thing from checking that the
choice is right.

WHAT THIS SUITE DOES NOT COVER
------------------------------
  * A pad. gpio_i is driven by hand here and never by gpio_o. The
    read-back of a pin THROUGH a pad is what hw/soc/tb/tb_soc.v's board
    model and check 28 of the bring-up program demonstrate.
  * Metastability. Two synchroniser stages are checked to be present
    by their latency; whether two is enough is not an RTL property.
  * The interrupt reaching the core. The line is observed at irq_o;
    that it lands on fast line 2 and vectors at mtvec+0x48 is check 28.
  * Any fault model. This block is unprotected.
  * Gate-level behaviour, timing, X-propagation and power.
"""

import os
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "sw"))
from golden.memmap_gen import APB_SLOTS, IRQ_SOURCES  # noqa: E402

# The width the Makefile elaborated, from the same variable it used.
NBITS = int(os.environ.get("NBITS", "16"))
MASK = (1 << NBITS) - 1

# grip.pdf table 923.
DATA = 0x000
OUTPUT = 0x004
DIRECTION = 0x008
IMASK = 0x00C
IPOL = 0x010
IEDGE = 0x014
BYPASS = 0x018
CAP = 0x01C
IRQMAP0 = 0x020
IAVAIL = 0x040
IFLAG = 0x044
IPEN = 0x048
PULSE = 0x04C
IPEN_OR = 0x050
OUTPUT_OR, DIRECTION_OR, IMASK_OR = 0x054, 0x058, 0x05C
IPEN_AND = 0x060
OUTPUT_AND, DIRECTION_AND, IMASK_AND = 0x064, 0x068, 0x06C
IPEN_XOR = 0x070
OUTPUT_XOR, DIRECTION_XOR, IMASK_XOR = 0x074, 0x078, 0x07C

# grip.pdf table 931.
CAP_PU = 1 << 18
CAP_IER = 1 << 17
CAP_IFL = 1 << 16
CAP_IRQGEN_SHIFT = 8
CAP_NLINES_MASK = 0x1F

CLK_NS = 10


def val(sig):
    s = str(sig.value)
    if any(c not in "01" for c in s):
        raise AssertionError("non-binary value {!r} on {}".format(s, sig._path))
    return int(s, 2)


async def setup(dut):
    """Clock, reset, every input low.

    Every test starts its own clock -- test_soc_wdog_win.py records what
    the other arrangement cost.
    """
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, units="ns").start())
    dut.rst_ni.value = 0
    dut.psel_i.value = 0
    dut.penable_i.value = 0
    dut.paddr_i.value = 0
    dut.pwrite_i.value = 0
    dut.pwdata_i.value = 0
    dut.gpio_i.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk_i)
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


async def drive(dut, value, settle=3):
    """Set the pins and wait for the synchroniser to have seen them."""
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    dut.gpio_i.value = value & MASK
    for _ in range(settle):
        await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")


@cocotb.test()
async def test_reset_state_is_every_pin_an_input_and_nothing_enabled(dut):
    """grip.pdf tables 925 to 929: OUTPUT, DIRECTION and IMASK reset to
    zero. IPOL and IEDGE are marked NR there and soc_gpio.v resets them
    to zero anyway, which is what this asserts, so the divergence is
    tested rather than merely documented. A part that powered up with a
    pin driving or an interrupt armed could not be brought up."""
    await setup(dut)
    for reg in (OUTPUT, DIRECTION, IMASK, IPOL, IEDGE, IFLAG):
        assert await apb_read(dut, reg) == 0, hex(reg)
    assert val(dut.gpio_oe_o) == 0, "a pin is driving out of reset"
    assert val(dut.gpio_o) == 0
    assert val(dut.irq_o) == 0


@cocotb.test()
async def test_data_is_the_pins_two_clocks_late_and_never_the_output_register(dut):
    """62.2: two flip-flops in series. The latency is measured to be
    exactly two: after one clock the old value is still read, after two
    the new one.

    And DATA is gpio_i and nothing else -- a pin whose DIRECTION bit is
    set and whose OUTPUT bit is 1 still reads whatever gpio_i says,
    because there is no pad here and a block that read its own output
    register back would pass a loopback test with no pin at all.
    """
    await setup(dut)
    pattern = 0xA5A5 & MASK
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    dut.gpio_i.value = pattern
    await RisingEdge(dut.clk_i)        # sync1 has it
    await Timer(1, units="ns")
    assert val(dut.prdata_o) & MASK != pattern or pattern == 0, \
        "DATA changed after one clock: only one synchroniser stage"
    # Read through the bus, which takes its own two cycles.
    assert await apb_read(dut, DATA) == pattern

    # Now the block drives every pin high; gpio_i stays at the pattern.
    await apb_write(dut, DIRECTION, MASK)
    await apb_write(dut, OUTPUT, MASK)
    await drive(dut, pattern)
    assert await apb_read(dut, DATA) == pattern, \
        "DATA read the OUTPUT register instead of the pins"


@cocotb.test()
async def test_output_and_direction_drive_the_pin_wires(dut):
    """Tables 925 and 926: gpio_o carries OUTPUT and gpio_oe_o carries
    DIRECTION, and the two are independent -- an OUTPUT bit on an input
    pin is stored but the enable stays low."""
    await setup(dut)
    await apb_write(dut, OUTPUT, 0x00F0 & MASK)
    assert val(dut.gpio_o) == 0x00F0 & MASK
    assert val(dut.gpio_oe_o) == 0, "writing OUTPUT enabled a driver"
    await apb_write(dut, DIRECTION, 0x0030 & MASK)
    assert val(dut.gpio_oe_o) == 0x0030 & MASK
    assert val(dut.gpio_o) == 0x00F0 & MASK
    assert await apb_read(dut, OUTPUT) == 0x00F0 & MASK
    assert await apb_read(dut, DIRECTION) == 0x0030 & MASK


@cocotb.test()
async def test_logical_or_and_xor_aliases_update_output_direction_and_imask(dut):
    """Table 937: New value = <Old value> logical-op <Write data>, for
    the OUTPUT, DIRECTION and IMASK registers. Each register gets a
    different sequence so a block that routed every alias to one
    register would fail."""
    await setup(dut)
    plan = [(OUTPUT, OUTPUT_OR, OUTPUT_AND, OUTPUT_XOR, 0x1234),
            (DIRECTION, DIRECTION_OR, DIRECTION_AND, DIRECTION_XOR, 0x0F0F),
            (IMASK, IMASK_OR, IMASK_AND, IMASK_XOR, 0x00FF)]
    for plain, r_or, r_and, r_xor, seed in plan:
        seed &= MASK
        await apb_write(dut, plain, seed)
        await apb_write(dut, r_or, 0x8001 & MASK)
        exp = seed | (0x8001 & MASK)
        assert await apb_read(dut, plain) == exp, "OR at {:#x}".format(plain)
        await apb_write(dut, r_and, 0xF00F & MASK)
        exp &= 0xF00F & MASK
        assert await apb_read(dut, plain) == exp, "AND at {:#x}".format(plain)
        await apb_write(dut, r_xor, 0x5555 & MASK)
        exp ^= 0x5555 & MASK
        assert await apb_read(dut, plain) == exp, "XOR at {:#x}".format(plain)
    # And the aliases are write-only: they read zero (access "w*").
    for r in (OUTPUT_OR, DIRECTION_AND, IMASK_XOR):
        assert await apb_read(dut, r) == 0, hex(r)


@cocotb.test()
async def test_level_interrupt_follows_the_polarity_register(dut):
    """62.2: with IEDGE 0, IPOL 0 is active low and IPOL 1 is active
    high. The flag is set while the condition holds, so clearing it
    while the input is still active sets it again -- which is what makes
    it a level, and what a level handler has to know."""
    await setup(dut)
    line = 3 % NBITS
    bit = 1 << line
    await apb_write(dut, IEDGE, 0)
    await apb_write(dut, IPOL, bit)            # active high on this line
    await apb_write(dut, IMASK, bit)
    await drive(dut, 0)
    assert val(dut.irq_o) == 0
    assert await apb_read(dut, IFLAG) == 0
    await drive(dut, bit)
    assert val(dut.irq_o) == 1, "active-high level not detected"
    assert await apb_read(dut, IFLAG) == bit
    # Clearing while the level is still present re-sets it.
    await apb_write(dut, IFLAG, bit)
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    assert await apb_read(dut, IFLAG) == bit, \
        "a level that is still active did not re-set the flag"
    # Remove the cause, then clear: it stays clear.
    await drive(dut, 0)
    await apb_write(dut, IFLAG, bit)
    assert await apb_read(dut, IFLAG) == 0
    assert val(dut.irq_o) == 0

    # Now active low on the same line.
    await apb_write(dut, IPOL, 0)
    await drive(dut, bit)
    await apb_write(dut, IFLAG, bit)
    assert await apb_read(dut, IFLAG) == 0, "active-low fired on a high input"
    await drive(dut, 0)
    assert val(dut.irq_o) == 1, "active-low level not detected"


@cocotb.test()
async def test_edge_interrupt_fires_once_on_the_selected_edge(dut):
    """62.2: with IEDGE 1, IPOL 1 is rising and IPOL 0 is falling. An
    edge sets the flag ONCE; clearing it with the input still at the new
    level does not set it again, which is the difference from a level
    and the reason the bring-up program uses an edge."""
    await setup(dut)
    line = (NBITS - 1)
    bit = 1 << line
    await apb_write(dut, IEDGE, bit)
    await apb_write(dut, IPOL, bit)            # rising
    await apb_write(dut, IMASK, bit)
    await drive(dut, 0)
    assert await apb_read(dut, IFLAG) == 0
    await drive(dut, bit)                      # the rising edge
    assert await apb_read(dut, IFLAG) == bit, "rising edge not detected"
    assert val(dut.irq_o) == 1
    await apb_write(dut, IFLAG, bit)
    for _ in range(5):
        await RisingEdge(dut.clk_i)
    assert await apb_read(dut, IFLAG) == 0, "an edge re-fired as a level"
    assert val(dut.irq_o) == 0
    await drive(dut, 0)                        # falling: not selected
    assert await apb_read(dut, IFLAG) == 0, "a falling edge fired in rising mode"

    await apb_write(dut, IPOL, 0)              # falling
    await drive(dut, bit)
    assert await apb_read(dut, IFLAG) == 0, "a rising edge fired in falling mode"
    await drive(dut, 0)
    assert await apb_read(dut, IFLAG) == bit, "falling edge not detected"


@cocotb.test()
async def test_the_mask_gates_the_flag_on_the_way_in_and_the_line_on_the_way_out(dut):
    """62.2: "To enable an interrupt, the corresponding bit in the
    interrupt mask register must be set." So a masked line does not
    set its flag, an event from before the unmask is not delivered
    afterwards, and masking a line whose flag is set silences the line
    at once."""
    await setup(dut)
    bit = 1 << (1 % NBITS)
    await apb_write(dut, IEDGE, bit)
    await apb_write(dut, IPOL, bit)
    await apb_write(dut, IMASK, 0)
    await drive(dut, 0)
    await drive(dut, bit)                      # a rising edge, masked
    assert await apb_read(dut, IFLAG) == 0, "a masked line set its flag"
    await apb_write(dut, IMASK, bit)
    for _ in range(4):
        await RisingEdge(dut.clk_i)
    assert await apb_read(dut, IFLAG) == 0, \
        "an event from before the unmask was delivered after it"
    assert val(dut.irq_o) == 0
    await drive(dut, 0)
    await drive(dut, bit)
    assert val(dut.irq_o) == 1
    await apb_write(dut, IMASK, 0)
    assert val(dut.irq_o) == 0, "masking did not silence the line"
    assert await apb_read(dut, IFLAG) == bit, "masking erased the flag"


@cocotb.test()
async def test_iflag_is_write_one_to_clear_per_line_and_zero_writes_do_nothing(dut):
    """Table 934: "Write 1 to the corresponding bit to clear. Writes of 0
    have no effect." Two lines flagged, one cleared, the other must
    stand; then a write of all zeros must leave it standing."""
    await setup(dut)
    a, b = 1 << (0 % NBITS), 1 << (2 % NBITS)
    await apb_write(dut, IEDGE, a | b)
    await apb_write(dut, IPOL, a | b)
    await apb_write(dut, IMASK, a | b)
    await drive(dut, 0)
    await drive(dut, a | b)
    assert await apb_read(dut, IFLAG) == (a | b)
    await apb_write(dut, IFLAG, a)
    assert await apb_read(dut, IFLAG) == b, "clearing one line cleared another"
    await apb_write(dut, IFLAG, 0)
    assert await apb_read(dut, IFLAG) == b, "a write of zero cleared a flag"
    assert val(dut.irq_o) == 1


@cocotb.test()
async def test_an_edge_in_the_cycle_of_its_own_clear_is_not_lost(dut):
    """The race a handler has to lose in the right direction: the edge
    that arrives on the very cycle software acknowledges the previous
    one. The block resolves it in favour of the event, the same rule
    soc_busstat.v applies to its counters."""
    await setup(dut)
    bit = 1 << (5 % NBITS)
    await apb_write(dut, IEDGE, bit)
    await apb_write(dut, IPOL, bit)
    await apb_write(dut, IMASK, bit)
    await drive(dut, 0)
    await drive(dut, bit)
    assert await apb_read(dut, IFLAG) == bit
    # Line the next rising edge up so the synchroniser delivers it in
    # the ACCESS cycle of the clearing write: gpio_i must change two
    # clocks before that cycle. apb_write spends one clock in SETUP
    # after the edge it starts on, so the change goes in one clock
    # before the write begins.
    await drive(dut, 0)
    await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")
    dut.gpio_i.value = bit
    await apb_write(dut, IFLAG, bit)
    assert await apb_read(dut, IFLAG) == bit, \
        "the edge that coincided with the clear was lost"


@cocotb.test()
async def test_cap_reports_this_configuration_and_iavail_reports_every_line(dut):
    """Table 931. The block is configured with one shared interrupt
    line (IRQGEN = 1, the frozen map gives the slot one source), an
    interrupt flag register (IFL = 1), no input enable (IER = 0) and no
    pulse register (PU = 0); NLINES is the width minus one. Table 933:
    IAVAIL says which lines can interrupt, and every line can."""
    await setup(dut)
    cap = await apb_read(dut, CAP)
    assert cap & CAP_PU == 0, "PU claims a pulse register that is not there"
    assert cap & CAP_IER == 0, "IER claims an input-enable register"
    assert cap & CAP_IFL != 0, "IFL denies the flag register this block has"
    assert (cap >> CAP_IRQGEN_SHIFT) & 0x1F == 1, "IRQGEN is not 'one shared line'"
    assert cap & CAP_NLINES_MASK == NBITS - 1, "NLINES is not the width minus one"
    assert cap & ~(CAP_PU | CAP_IER | CAP_IFL | (0x1F << CAP_IRQGEN_SHIFT)
                   | CAP_NLINES_MASK) == 0, "a reserved CAP field is set"
    assert await apb_read(dut, IAVAIL) == MASK


@cocotb.test()
async def test_unimplemented_registers_read_zero_and_writes_to_them_do_nothing(dut):
    """BYPASS, the interrupt map registers, the input-enable register and
    its aliases, and the pulse register are not implemented and CAP says
    so. Each reads zero, and a write to any of them -- or to a read-only
    register, or to an offset that names nothing -- leaves every real
    register exactly as it was."""
    await setup(dut)
    await apb_write(dut, OUTPUT, 0x1357 & MASK)
    await apb_write(dut, DIRECTION, 0x2468 & MASK)
    await apb_write(dut, IMASK, 0x0001)
    await apb_write(dut, IPOL, 0x0001)
    await apb_write(dut, IEDGE, 0x0001)
    before = {}
    for r in (OUTPUT, DIRECTION, IMASK, IPOL, IEDGE):
        before[r] = await apb_read(dut, r)
    for off in (DATA, BYPASS, CAP, IRQMAP0, IRQMAP0 + 4, IAVAIL, IPEN, PULSE,
                IPEN_OR, IPEN_AND, IPEN_XOR, 0x080, 0x100, 0x800, 0xFFC):
        if off not in (DATA, CAP, IAVAIL):
            assert await apb_read(dut, off) == 0, "reads non-zero: {:#x}".format(off)
        await apb_write(dut, off, 0xFFFFFFFF)
    for r, v in before.items():
        assert await apb_read(dut, r) == v, \
            "a stray write disturbed {:#x}".format(r)


@cocotb.test()
async def test_bits_above_the_port_width_read_zero_and_are_not_stored(dut):
    """Tables 924 to 929: bits 31..NBITS are RESERVED, read zero. A
    write of all ones to a register must read back as the low NBITS."""
    await setup(dut)
    if NBITS >= 32:
        return
    for r in (OUTPUT, DIRECTION, IMASK, IPOL, IEDGE):
        await apb_write(dut, r, 0xFFFFFFFF)
        assert await apb_read(dut, r) == MASK, hex(r)
    assert val(dut.gpio_o) == MASK
    assert val(dut.gpio_oe_o) == MASK
    await drive(dut, MASK)
    assert await apb_read(dut, DATA) == MASK


@cocotb.test()
async def test_reads_have_no_side_effects(dut):
    """A telemetry poll of DATA and IFLAG must not clear a flag or move a
    register: only a write of 1 to IFLAG clears (table 934)."""
    await setup(dut)
    bit = 1 << (4 % NBITS)
    await apb_write(dut, IEDGE, bit)
    await apb_write(dut, IPOL, bit)
    await apb_write(dut, IMASK, bit)
    await drive(dut, 0)
    await drive(dut, bit)
    for _ in range(3):
        assert await apb_read(dut, IFLAG) == bit
        await apb_read(dut, DATA)
        await apb_read(dut, IMASK)
    assert val(dut.irq_o) == 1


@cocotb.test()
async def test_the_slot_and_the_line_are_the_frozen_maps(dut):
    """The block is only reachable if it is where the map says it is.

    Asserted against the GENERATED map rather than a literal, so a
    change to regmap/memmap.yaml fails here rather than in silicon. The
    slot, source number and device id are the values the map has
    carried for GPIO since docs/39 froze it; what this work changes is
    the status.
    """
    await setup(dut)
    _base, slot, irq, status = APB_SLOTS["GPIO"]
    assert slot == 0x002
    assert irq == 4
    assert status == "implemented", \
        "GPIO is decoded by soc_top.v but the map still calls it reserved"
    assert IRQ_SOURCES["GPIO"][1] == 2, "the fast interrupt line moved"
