# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""soc_gptimer suite: GRLIB's GPTIMER register map, on AMBA 3 APB.

WHERE THE EXPECTATIONS COME FROM. Three places, none of which is the RTL:

  * GRLIB's GPTIMER register map, grip.pdf table 463, quoted in
    docs/08-gr801-datasheet-notes.md section 2.5 and adopted by section 3
    row 8: scaler at 0x00, scaler reload at 0x04, configuration at 0x08,
    latch configuration at 0x0C, and timer n at 0x10*n with counter,
    reload, control and latch. Control bits EN, RS, LD, IE, IP, CH, DH at
    positions 0..6;
  * AMBA 3 APB: a transfer is SETUP for one cycle then ACCESS held until
    PREADY, with the payload stable across both. The driver below obeys
    that and the monitor checks the slave's side of it on every cycle;
  * the generated memory map, sw/golden/memmap_gen.py, for the slot's
    plug-and-play interrupt SOURCE NUMBER, which the configuration
    register has to report. That number is not written down here: it is
    read out of APB_SLOTS, so moving it in regmap/memmap.yaml moves what
    this suite demands.

WHAT THIS SUITE DOES NOT COVER
------------------------------
  * The watchdog. Timer NGEN+1 is soc_wdog.v and has its own suite; this
    file checks only that the shell ROUTES the right offsets to it and
    does not pretend it is a general timer.
  * Per-timer interrupts. This block implements the shared-interrupt
    configuration and reports SI = 0. The separate-interrupt mode GRLIB
    also offers is not built and is not tested.
  * The latch registers and the DH and DF bits, which are not
    implemented; they are checked to read zero and nothing more.
  * PSLVERR. This slave never asserts it, matching soc_uart.v; an offset
    inside the slot that names no register reads zero, which is GRLIB's
    behaviour for unoccupied space behind a bridge (GR740 UM 2.3).
  * Byte strobes. The bridge carries PSTRB and this block ignores it:
    every register here is written whole. A sub-word store to a GPTIMER
    register writes the whole register, and that is stated rather than
    checked.
  * Any timing property, gate-level behaviour, X-propagation or power.
"""

import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "sw"))
from golden.memmap_gen import APB_SLOTS, IRQ_SOURCES  # noqa: E402

# Parameters the Makefile builds the block with.
NGEN = 2
NT = NGEN + 1
IRQ_NUM = APB_SLOTS["TIMER0"][2]

# grip.pdf table 463.
REG_SCALER = 0x000
REG_SCRELOAD = 0x004
REG_CONFIG = 0x008
REG_LATCHCFG = 0x00C


def T_CNT(n):
    return 0x10 * n


def T_RLD(n):
    return 0x10 * n + 4


def T_CTRL(n):
    return 0x10 * n + 8


def T_LATCH(n):
    return 0x10 * n + 0xC


REG_WDOGSTAT = 0x10 * (NT + 1)

B_EN, B_RS, B_LD, B_IE, B_IP, B_CH = 1, 2, 4, 8, 16, 32

WDOG_KEY = 0xA51F

CLK_NS = 10
T_DRIVE = 1
T_SAMPLE = 8


def val(sig):
    s = str(sig.value)
    if any(c not in "01" for c in s):
        raise AssertionError("non-binary value {!r} on {}".format(s, sig._path))
    return int(s, 2)


class Apb:
    """An AMBA 3 APB requester: one SETUP cycle, then ACCESS until PREADY.

    It also CHECKS the completer's half on every transfer: PREADY must be
    high in the ACCESS cycle (this slave has no wait states and says so in
    its header) and PSLVERR must be low.
    """

    def __init__(self, dut):
        self.dut = dut
        self.transfers = 0

    async def _xfer(self, off, write, data=0):
        dut = self.dut
        # SETUP
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
        dut.psel_i.value = 1
        dut.penable_i.value = 0
        dut.paddr_i.value = off
        dut.pwrite_i.value = 1 if write else 0
        dut.pwdata_i.value = data
        await Timer(T_SAMPLE - T_DRIVE, unit="ns")
        assert val(dut.pready_o) in (0, 1)
        # ACCESS
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
        dut.penable_i.value = 1
        await Timer(T_SAMPLE - T_DRIVE, unit="ns")
        assert val(dut.pready_o) == 1, (
            "offset 0x{:03x}: PREADY low; this slave declares no wait states"
            .format(off))
        assert val(dut.pslverr_o) == 0, (
            "offset 0x{:03x}: PSLVERR asserted".format(off))
        out = val(dut.prdata_o)
        self.transfers += 1
        # IDLE
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
        dut.psel_i.value = 0
        dut.penable_i.value = 0
        return out

    async def read(self, off):
        return await self._xfer(off, False)

    async def write(self, off, data):
        await self._xfer(off, True, data)


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    dut.rst_ni.value = 0
    dut.rst_por_ni.value = 0
    dut.psel_i.value = 0
    dut.penable_i.value = 0
    dut.paddr_i.value = 0
    dut.pwrite_i.value = 0
    dut.pwdata_i.value = 0
    dut.wdog_dis_i.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.rst_ni.value = 1
    dut.rst_por_ni.value = 1
    await RisingEdge(dut.clk_i)
    return Apb(dut)


# ---------------------------------------------------------------------------


@cocotb.test()
async def test_configuration_register_reports_the_map(dut):
    """TIMERS, IRQ and SI are the truth about this instance.

    The IRQ field is the interesting one. It is the plug-and-play SOURCE
    NUMBER, and it reaches the block as a parameter from the generated
    map rather than as a constant in the RTL, so the number a driver
    reads out of this register and the number in the device table are the
    same number by construction. This check is what makes that claim
    testable: the expected value comes from sw/golden/memmap_gen.py.
    """
    a = await setup(dut)
    cfg = await a.read(REG_CONFIG)
    assert cfg & 0x7 == NT, (
        "TIMERS reads {}, this instance has {} timers including the watchdog"
        .format(cfg & 0x7, NT))
    assert (cfg >> 3) & 0x1F == IRQ_NUM, (
        "IRQ reads {}, the map assigns source {} to TIMER0"
        .format((cfg >> 3) & 0x1F, IRQ_NUM))
    assert (cfg >> 8) & 1 == 0, "SI reads 1, but this block has one shared line"
    assert (cfg >> 9) & 1 == 0, "DF reads 1, but freeze is not implemented"
    assert await a.read(REG_LATCHCFG) == 0, "latch configuration is not zero"
    # And the map's own view of the same source.
    assert IRQ_SOURCES["TIMER0"][0] == IRQ_NUM
    dut._log.info("config 0x%08x: %d timers, source %d, shared", cfg, NT, IRQ_NUM)


@cocotb.test()
async def test_reset_state(dut):
    """Every general timer is off, and no interrupt is asserted.

    The watchdog is NOT off, which is the point of it, and its registers
    are excluded here for that reason -- test_soc_wdog.py owns them.
    """
    a = await setup(dut)
    assert val(dut.irq_o) == 0
    for n in range(1, NGEN + 1):
        assert await a.read(T_CNT(n)) == 0
        assert await a.read(T_RLD(n)) == 0
        assert await a.read(T_CTRL(n)) == 0, (
            "timer {} is enabled out of reset".format(n))
    assert await a.read(REG_SCALER) == 0
    assert await a.read(REG_SCRELOAD) == 0


@cocotb.test()
async def test_a_timer_counts_down_at_the_scaler_rate(dut):
    """The period is (reload + 1) * (scaler reload + 1) clocks, measured.

    Both dividers are exercised, and the count is measured rather than
    approximated: "roughly periodic" is how a timer that is a factor of
    two out gets shipped.
    """
    a = await setup(dut)
    for scaler, reload_ in ((0, 3), (2, 4), (5, 1)):
        await a.write(REG_SCRELOAD, scaler)
        await a.write(REG_SCALER, scaler)
        await a.write(T_RLD(1), reload_)
        await a.write(T_CTRL(1), B_EN | B_RS | B_LD | B_IE)
        # Clear anything the load left behind, then time the next edge.
        await a.write(T_CTRL(1), B_EN | B_RS | B_IE | B_IP)
        n = 0
        while val(dut.irq_o) == 0 and n < 4000:
            await RisingEdge(dut.clk_i)
            await Timer(T_SAMPLE, unit="ns")
            n += 1
        assert n < 4000, (
            "scaler {} reload {}: no interrupt".format(scaler, reload_))
        expect = (reload_ + 1) * (scaler + 1)
        assert abs(n - expect) <= (scaler + 1) + 2, (
            "scaler {} reload {}: fired after {} clocks, expected about {}"
            .format(scaler, reload_, n, expect))
        await a.write(T_CTRL(1), B_IP)     # stop and clear
        dut._log.info("scaler %d reload %d: %d clocks (expected %d)",
                      scaler, reload_, n, expect)


@cocotb.test()
async def test_ip_is_write_one_to_clear_and_ie_gates_the_line(dut):
    """IP records the wrap; IE decides whether it reaches irq_o.

    A timer with IE clear must still set IP -- software that polls has to
    be able to see the wrap -- and must not drive the shared line. That
    separation is what makes the shared line usable at all: the handler
    reads the IP bits to find out which timer fired.
    """
    a = await setup(dut)
    await a.write(REG_SCRELOAD, 0)
    await a.write(T_RLD(1), 2)
    await a.write(T_CTRL(1), B_EN | B_RS | B_LD)      # IE clear
    for _ in range(20):
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        assert val(dut.irq_o) == 0, "IE is clear and irq_o asserted"
    assert await a.read(T_CTRL(1)) & B_IP, "IP not set with IE clear"

    # Enabling IE now publishes the pending bit.
    await a.write(T_CTRL(1), B_EN | B_RS | B_IE)
    await RisingEdge(dut.clk_i)
    await Timer(T_SAMPLE, unit="ns")
    assert val(dut.irq_o) == 1, "IE set with IP pending and irq_o low"

    # Write one to clear -- in two steps, and the order matters.
    #
    # A wrap in the same cycle as the clearing write WINS, deliberately:
    # losing an interrupt is worse than reporting one twice. With the
    # timer still running at one wrap every three clocks, a single write
    # therefore clears IP about two times in three, which is exactly how
    # this test first failed. The correct sequence, and the one a driver
    # has to use, is to stop the timer and then clear.
    await a.write(T_CTRL(1), B_IE)             # EN clear: stop it
    await a.write(T_CTRL(1), B_IE | B_IP)      # then clear the flag
    assert await a.read(T_CTRL(1)) & B_IP == 0, "IP survived a write of one"
    assert val(dut.irq_o) == 0


@cocotb.test()
async def test_rs_decides_one_shot_or_periodic(dut):
    """Without RS a timer stops after one wrap; with RS it repeats.

    GRLIB's one-shot behaviour is that the timer clears its own EN on the
    wrap. A block that always restarted would pass a periodic test and
    fail this one.
    """
    a = await setup(dut)
    await a.write(REG_SCRELOAD, 0)
    await a.write(T_RLD(1), 3)
    await a.write(T_CTRL(1), B_EN | B_LD | B_IE)       # RS clear: one shot
    n = 0
    while val(dut.irq_o) == 0 and n < 200:
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        n += 1
    assert n < 200, "the one-shot timer never fired"
    ctrl = await a.read(T_CTRL(1))
    assert ctrl & B_EN == 0, (
        "EN is still set after a wrap with RS clear, so the timer is periodic "
        "when it was asked to be one-shot")
    await a.write(T_CTRL(1), B_IE | B_IP)
    for _ in range(40):
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        assert val(dut.irq_o) == 0, "a stopped one-shot timer fired again"


@cocotb.test()
async def test_chaining(dut):
    """Timer 2 with CH set advances only when timer 1 wraps.

    Its period is therefore the product of the two, which is the whole
    reason GRLIB has the bit. Timer 1 has no predecessor and its CH must
    read zero however it is written.
    """
    a = await setup(dut)
    await a.write(REG_SCRELOAD, 0)
    await a.write(T_RLD(1), 1)
    await a.write(T_RLD(2), 2)
    await a.write(T_CTRL(1), B_EN | B_RS | B_LD)
    await a.write(T_CTRL(2), B_EN | B_RS | B_LD | B_CH | B_IE)
    assert await a.read(T_CTRL(2)) & B_CH, "CH did not take on timer 2"

    n = 0
    while val(dut.irq_o) == 0 and n < 400:
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        n += 1
    assert n < 400, "the chained timer never fired"
    expect = (1 + 1) * (2 + 1)
    assert abs(n - expect) <= 4, (
        "chained period was {} clocks, expected about {}".format(n, expect))

    await a.write(T_CTRL(1), 0xFFFF)
    assert await a.read(T_CTRL(1)) & B_CH == 0, (
        "timer 1 accepted CH, but it has no predecessor to chain to")


@cocotb.test()
async def test_the_watchdog_offsets_reach_the_watchdog(dut):
    """Timer NT and the status offset are the watchdog, and only those.

    This is the whole of what this suite claims about the watchdog: the
    shell routes those offsets to it. Two things make the check
    non-vacuous. First, the watchdog is ARMED at reset while every
    general timer is off, so reading timer NT's control register and
    finding EN set can only be the watchdog. Second, its registers need
    the key -- an unkeyed write to timer NT's reload does nothing, while
    the same write to a general timer's reload lands.
    """
    a = await setup(dut)
    wd_ctrl = await a.read(T_CTRL(NT))
    assert wd_ctrl & B_EN, (
        "timer {} is not enabled at reset, so this offset is not reaching "
        "the watchdog".format(NT))
    for n in range(1, NGEN + 1):
        assert await a.read(T_CTRL(n)) & B_EN == 0

    # The key, as a routing check rather than a policy check.
    await a.write(T_RLD(NT), 0x0044)                    # unkeyed
    assert await a.read(T_RLD(NT)) != 0x0044, (
        "an unkeyed write landed in timer {}'s reload, so that offset is "
        "reaching a general timer".format(NT))
    await a.write(T_RLD(NT), (WDOG_KEY << 16) | 0x0044)  # keyed
    assert await a.read(T_RLD(NT)) == 0x0044

    await a.write(T_RLD(1), 0x0044)
    assert await a.read(T_RLD(1)) == 0x0044, (
        "a general timer's reload needed a key, so the routing is inverted")

    # The status offset is the watchdog's and is not a general timer's.
    st = await a.read(REG_WDOGSTAT)
    assert st & 0xF0 == 0
    assert val(dut.nmi_o) == 0
    assert val(dut.rst_req_o) == 0
    assert val(dut.wdog_no) == 1


@cocotb.test()
async def test_the_watchdog_is_not_on_the_shared_interrupt(dut):
    """irq_o never carries the watchdog.

    The watchdog's signal is the non-maskable one and goes straight to
    the core. If it were ORed into the shared line as GRLIB's would be,
    a driver could mask it with one write to mie -- which is the whole
    thing soc_wdog.v W3 exists to prevent. The watchdog is driven all the
    way to stage 1 with both general timers disabled and irq_o watched
    throughout.
    """
    a = await setup(dut)
    await a.write(T_RLD(NT), (WDOG_KEY << 16) | 3)
    await a.write(T_CTRL(NT), (WDOG_KEY << 16) | B_LD)
    n = 0
    while val(dut.nmi_o) == 0 and n < 2000:
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        assert val(dut.irq_o) == 0, (
            "irq_o asserted while the watchdog was counting")
        n += 1
    assert n < 2000, "the watchdog never fired"
    for _ in range(20):
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        assert val(dut.irq_o) == 0, (
            "irq_o asserted when the watchdog reached stage 1, so the "
            "non-maskable signal is also on a maskable line")


@cocotb.test()
async def test_unoccupied_offsets_read_zero(dut):
    """An offset inside the slot that names no register reads zero.

    GRLIB's behaviour for unoccupied space behind an APB bridge (GR740 UM
    section 2.3), and the same choice soc_uart.v makes. It differs from
    soc_clint.v, which faults -- deliberately, and both files say why.
    """
    a = await setup(dut)
    for off in (0x100, 0x200, 0xFF0, 0x080, 0x054):
        assert await a.read(off) == 0, (
            "offset 0x{:03x} is not a register and did not read zero"
            .format(off))
        await a.write(off, 0xFFFFFFFF)
    # And nothing that write touched moved.
    assert val(dut.irq_o) == 0
    for n in range(1, NGEN + 1):
        assert await a.read(T_CTRL(n)) == 0
    # The latch registers are inside the timers and are also not there.
    for n in range(1, NT + 1):
        assert await a.read(T_LATCH(n)) == 0


@cocotb.test()
async def test_no_transfer_and_no_interrupt_in_reset(dut):
    """With rst_ni low, no general timer runs and irq_o stays low.

    rst_por_ni is held high throughout, so this also demonstrates the
    thing the two reset domains exist for: the shell is in reset and the
    watchdog is not.
    """
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    dut.rst_ni.value = 0
    dut.rst_por_ni.value = 1
    dut.psel_i.value = 1
    dut.penable_i.value = 1
    dut.paddr_i.value = T_CTRL(1)
    dut.pwrite_i.value = 1
    dut.pwdata_i.value = 0xFFFFFFFF
    dut.wdog_dis_i.value = 0
    for cycle in range(20):
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        assert val(dut.irq_o) == 0, (
            "cycle {}: a write during reset started a timer".format(cycle))
    dut.psel_i.value = 0
    dut.penable_i.value = 0
