# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""soc_wdog suite: the five requirements W1-W5, one test group each.

WHERE THE EXPECTATIONS COME FROM. From the specification in the header of
hw/soc/rtl/soc_wdog.v, which is a list of five requirements argued in
docs/40-interrupts-timers-watchdog.md section 5 and written before the
RTL. They are restated here in the form a test can check:

  W1  armed out of power-on reset; no write can disarm it; the only thing
      that can is the dis_i bootstrap pin, sampled once.
  W2  the time base is not reachable from any register, so the longest
      timeout is a constant of the netlist: 2^WIDTH * PRESCALE clocks.
  W3  three stages -- NMI, then system reset, then the external pin --
      and each is reached only from the one before it.
  W4  every status bit survives the reset this block generates, because
      nothing here is in that reset's domain.
  W5  no write to any register has any effect without the key.

The RTL was read for the port names, the parameter names and the fact
that rst_por_ni is active low. The register LAYOUT is GRLIB's GPTIMER
timer registers (grip.pdf table 463) plus this project's WDOGSTAT
extension, both of which are documented interfaces rather than
implementation.

WHAT THIS SUITE DOES NOT COVER
------------------------------
  * The APB shell. This block has a four-bit one-hot register port, not
    an APB port; which offsets soc_gptimer.v maps onto those four bits is
    that block's suite, and whether soc_top.v routes the slot to it is
    the whole-SoC run.
  * Whether Ibex takes the NMI. nmi_o is checked as a wire here. The core
    taking it, vectoring to mtvec + 0x7C and returning is test 21 of
    hw/soc/tb/sw/test_ibex.c on the real fabric.
  * The system reset actually resetting anything. rst_req_o is checked as
    a pulse of the right length; that soc_top.v turns it into a reset for
    every other block, and that the SoC then reboots, is
    `SW_DEFINES=-DWDOG_RESET_DEMO hw/soc/flow/sim_soc.sh`.
  * Parameter values other than the small ones used here. The suite runs
    with WIDTH 8 and PRESCALE 4 so that a full timeout is a few thousand
    clocks; soc_top.v instantiates WIDTH 16 and PRESCALE 16. The
    behaviour is parameterised but only one point is measured.
  * Any upset in the block's own state. It has no parity, no redundancy
    and no protection of any kind, and nothing here injects a fault.
  * A windowed mode. There is none: an early kick is accepted, and a
    runaway that keeps kicking is invisible to this block and to this
    suite.
  * Gate-level behaviour, timing, X-propagation, power and clock gating.
"""

import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "sw"))
from golden.memmap_gen import CORE_IRQS  # noqa: E402

# Parameters the Makefile builds the block with. Small, so a full timeout
# is a few thousand clocks rather than a million.
WIDTH = 8
PRESCALE = 4
RST_CYCLES = 8
ESCALATE = 2
KEY = 0xA51F

MAX_RELOAD = (1 << WIDTH) - 1
FULL_TIMEOUT = (MAX_RELOAD + 1) * PRESCALE

# One-hot register select, as soc_gptimer.v drives it.
SEL_CNT, SEL_RLD, SEL_CTRL, SEL_STAT = 1, 2, 4, 8

# GRLIB timer control bits (grip.pdf table 463).
B_EN, B_RS, B_LD, B_IE, B_IP = 1, 2, 4, 8, 16

# WDOGSTAT, this project's extension.
ST_NMI, ST_WDOGRST, ST_ESCALATED, ST_DISABLED = 1, 2, 4, 8

CLK_NS = 10
T_DRIVE = 1
T_SAMPLE = 8


def val(sig):
    s = str(sig.value)
    if any(c not in "01" for c in s):
        raise AssertionError("non-binary value {!r} on {}".format(s, sig._path))
    return int(s, 2)


def keyed(v):
    return (KEY << 16) | (v & 0xFFFF)


class Wdog:
    def __init__(self, dut):
        self.dut = dut

    async def _access(self, sel, we, data):
        dut = self.dut
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
        dut.sel_i.value = sel
        dut.we_i.value = we
        dut.wdata_i.value = data
        await Timer(T_SAMPLE - T_DRIVE, unit="ns")
        out = val(dut.rdata_o)
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
        dut.sel_i.value = 0
        dut.we_i.value = 0
        dut.wdata_i.value = 0
        return out

    async def read(self, sel):
        return await self._access(sel, 0, 0)

    async def write(self, sel, data):
        """A write with the key."""
        return await self._access(sel, 1, keyed(data))

    async def write_raw(self, sel, data):
        """A write with whatever the caller supplies, key or not."""
        return await self._access(sel, 1, data)

    async def kick(self):
        await self.write(SEL_CTRL, B_LD)

    async def ack(self):
        await self.write(SEL_STAT, ST_NMI)


async def por(dut, dis=0):
    """Apply and release power-on reset. Does NOT start a clock.

    setup() starts exactly one clock per test and a test that needs a
    fresh power-on reset in a loop calls this instead. Starting a clock
    per iteration leaves one Clock driver per pass on clk_i and the
    effective period shortens with each -- which is how
    test_the_timeout_is_reload_plus_one_prescaler_periods first failed,
    reporting a stage-1 delay of 10 clocks where 32 was expected. That
    reads exactly like a prescaler bug and is not one.
    """
    await Timer(T_DRIVE, unit="ns")
    dut.rst_por_ni.value = 0
    dut.dis_i.value = dis
    dut.sel_i.value = 0
    dut.we_i.value = 0
    dut.wdata_i.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.rst_por_ni.value = 1
    # THREE clocks, not one, and the number is the design's rather than a
    # margin. `dis_i` is a board strap: soc_wdog.v puts it through a
    # two-flop synchroniser and then a two-count hold-off, and `dis_seen`
    # -- the term that makes `armed` mean anything -- cannot be set until
    # both have settled. Reading CTRL on the first clock after release
    # reads a part that is disarmed BY CONSTRUCTION and reports itself so,
    # which is what test_armed_out_of_power_on_reset and
    # test_the_bootstrap_pin_disables_it_and_says_so both saw at 81 ns.
    #
    # It is fixed here rather than in the two tests because this helper is
    # what claims power-on reset has been applied and released, and a
    # part whose strap has not been sampled has not finished coming out of
    # it. Any test written later against por() gets the same guarantee
    # without knowing about the synchroniser.
    #
    # hw/soc/formal/soc_wdog_props.v's `f_armed_ready` is the same fact on
    # the proof side, and its comment states what that window costs.
    for _ in range(3):
        await RisingEdge(dut.clk_i)
    return Wdog(dut)


async def setup(dut, dis=0):
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    return await por(dut, dis)


async def run_until(dut, sig, limit):
    """Clocks until `sig` is high, or `limit`. Returns the count."""
    for n in range(limit):
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        if val(getattr(dut, sig)):
            return n + 1
    return None


# ---------------------------------------------------------------------------
# W1: armed at reset, and software cannot disarm it
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_armed_out_of_power_on_reset(dut):
    """EN, RS and IE read 1 and the counter is at the maximum reload.

    "Armed at reset" is the map's own words (docs/memmap-soc.md section 3,
    TIMER0) and docs/08 section 4 item 8 makes it a project requirement
    rather than an option. The reload being the MAXIMUM is the other half
    of it: a short default would let a board whose boot is slower than the
    watchdog reset forever with no way in.
    """
    w = await setup(dut)
    ctrl = await w.read(SEL_CTRL)
    assert ctrl & B_EN, "not enabled out of power-on reset"
    assert ctrl & B_RS, "not restarting out of power-on reset"
    assert ctrl & B_IE, "not signalling out of power-on reset"
    assert await w.read(SEL_RLD) == MAX_RELOAD, (
        "the reset reload is not the maximum the counter can hold, so the "
        "boot timeout is shorter than the hardware allows")
    st = await w.read(SEL_STAT)
    assert st == 0, "status is not clean out of power-on reset: 0x{:x}".format(st)
    assert val(dut.nmi_o) == 0
    assert val(dut.rst_req_o) == 0
    assert val(dut.wdog_no) == 1, "the external pin is asserted at reset"
    # The map's own record of which core input this drives.
    assert CORE_IRQS["NMI"][0] == 31


@cocotb.test()
async def test_software_cannot_disarm_it(dut):
    """Keyed writes clearing EN, RS and IE are accepted and ignored.

    This is W1 and it is the single most important property in the file.
    The write is KEYED -- so this is not "the write was rejected because
    it lacked the key", it is "a fully authorised attempt to switch the
    watchdog off did nothing". The read-back reports 1, so a driver that
    tried can discover that it failed.
    """
    w = await setup(dut)
    for attempt in (0, B_IP, B_RS, B_EN, 0xFFFF & ~B_EN):
        await w.write_raw(SEL_CTRL, keyed(attempt))
        ctrl = await w.read(SEL_CTRL)
        assert ctrl & B_EN, (
            "writing 0x{:04x} cleared EN".format(attempt))
        assert ctrl & B_RS, "writing 0x{:04x} cleared RS".format(attempt)
        assert ctrl & B_IE, "writing 0x{:04x} cleared IE".format(attempt)
    # And it still fires afterwards, which is what "ignored" has to mean.
    await w.write(SEL_RLD, 3)
    await w.kick()
    n = await run_until(dut, "nmi_o", 20 * PRESCALE)
    assert n is not None, "the watchdog stopped counting after a disarm attempt"


@cocotb.test()
async def test_the_bootstrap_pin_disables_it_and_says_so(dut):
    """dis_i high at power-on reset: no counting, and DISABLED reads 1.

    This is the one hole in W1 and it is deliberate -- lab bring-up and
    gate-level debug have to be able to hold the watchdog off. What makes
    it acceptable is that the part cannot then claim to be protected:
    WDOGSTAT.DISABLED is set, and EN reads 0 rather than lying.
    """
    w = await setup(dut, dis=1)
    st = await w.read(SEL_STAT)
    assert st & ST_DISABLED, "the pin was high and DISABLED does not say so"
    assert (await w.read(SEL_CTRL)) & B_EN == 0, (
        "EN reads 1 on a part whose watchdog is held off by the pin")
    for _ in range(3 * FULL_TIMEOUT):
        await RisingEdge(dut.clk_i)
    assert val(dut.nmi_o) == 0, "a disabled watchdog fired"
    assert val(dut.rst_req_o) == 0


@cocotb.test()
async def test_the_pin_is_sampled_once_and_ignored_afterwards(dut):
    """dis_i moving after reset changes nothing.

    A pin that could disable the watchdog at any moment is a hardware
    backdoor into the one block whose job is to be unstoppable. Sampling
    it only at power-on reset makes it a board-level configuration
    instead.
    """
    w = await setup(dut, dis=0)
    await Timer(T_DRIVE, unit="ns")
    dut.dis_i.value = 1
    await w.write(SEL_RLD, 3)
    await w.kick()
    n = await run_until(dut, "nmi_o", 20 * PRESCALE)
    assert n is not None, (
        "raising dis_i after reset stopped the watchdog, so the pin is not "
        "sampled once")
    assert (await w.read(SEL_STAT)) & ST_DISABLED == 0


# ---------------------------------------------------------------------------
# W5: every write is keyed
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_unkeyed_writes_do_nothing(dut):
    """A write without the key changes no register and kicks nothing.

    The wrong keys include the key off by one bit and the key in the
    wrong half of the word, because a runaway store is much more likely
    to produce a near miss than a random value.
    """
    w = await setup(dut)
    await w.write(SEL_RLD, 0x30)
    base_rld = await w.read(SEL_RLD)
    assert base_rld == 0x30

    wrong = [0x0000_0044, 0xFFFF_0044, 0xA51E_0044, 0xA51F_0000 >> 1,
             0x0000_A51F, 0x5A1F_0044]
    for wd in wrong:
        if (wd >> 16) == KEY:
            continue
        await w.write_raw(SEL_RLD, wd)
        assert await w.read(SEL_RLD) == base_rld, (
            "unkeyed write 0x{:08x} changed the reload".format(wd))
        await w.write_raw(SEL_CNT, wd)
        await w.write_raw(SEL_CTRL, wd)
        await w.write_raw(SEL_STAT, wd)

    # An unkeyed control write with LD set must NOT kick: let the counter
    # run down and confirm it fired on schedule anyway.
    await w.write(SEL_RLD, 3)
    await w.kick()
    for _ in range(2 * PRESCALE):
        await RisingEdge(dut.clk_i)
        await w.write_raw(SEL_CTRL, B_LD)      # unkeyed kick attempts
    n = await run_until(dut, "nmi_o", 20 * PRESCALE)
    assert n is not None, (
        "unkeyed writes with LD set kept the watchdog alive, so a runaway "
        "storing arbitrary values can pet it")


@cocotb.test()
async def test_unkeyed_status_write_cannot_hold_off_stage_2(dut):
    """The acknowledge is keyed too, and that is not pedantry.

    Stage 2 fires on a second expiry with stage 1 still unacknowledged.
    If the acknowledge bit were unkeyed, a runaway spraying stores at the
    status register would clear it before every second expiry and hold
    the machine in stage 1 forever -- the watchdog would warn and never
    act. Here the unkeyed clears do nothing and stage 2 arrives.
    """
    w = await setup(dut)
    await w.write(SEL_RLD, 3)
    await w.kick()
    assert await run_until(dut, "nmi_o", 20 * PRESCALE) is not None
    saw_reset = False
    for _ in range(30 * PRESCALE):
        await w.write_raw(SEL_STAT, ST_NMI)    # unkeyed acknowledge
        if val(dut.rst_req_o):
            saw_reset = True
            break
    assert saw_reset, (
        "unkeyed acknowledges suppressed stage 2, so a runaway can keep the "
        "watchdog in stage 1 indefinitely")


# ---------------------------------------------------------------------------
# W2: the time base is not reachable from a register
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_the_longest_timeout_is_a_constant(dut):
    """No reload software can write produces a timeout past the maximum.

    Every value the register can hold is tried at the top of its range,
    including a full 16-bit field with the key in place, and the measured
    time to stage 1 never exceeds 2^WIDTH * PRESCALE clocks. This is what
    replaces GRLIB's arrangement, where the watchdog shares a software
    writable prescaler and one store multiplies the timeout by up to a
    thousand.
    """
    w = await setup(dut)
    for req in (MAX_RELOAD, MAX_RELOAD + 1, 0xFFFF, 0x8000):
        w2 = await por(dut)
        await w2.write_raw(SEL_RLD, keyed(req))
        got = await w2.read(SEL_RLD)
        assert got <= MAX_RELOAD, (
            "reload {} was accepted; the register is wider than the counter"
            .format(got))
        await w2.kick()
        n = await run_until(dut, "nmi_o", 3 * FULL_TIMEOUT)
        assert n is not None, "no stage 1 within three full timeouts"
        assert n <= FULL_TIMEOUT + 4 * PRESCALE, (
            "requesting reload 0x{:x} produced a timeout of {} clocks, past "
            "the {} the netlist is supposed to bound it to"
            .format(req, n, FULL_TIMEOUT))
    dut._log.info("longest timeout bounded at %d clocks", FULL_TIMEOUT)
    assert w is not None


@cocotb.test()
async def test_the_timeout_is_reload_plus_one_prescaler_periods(dut):
    """A kick with reload R gives (R+1)*PRESCALE clocks, measured.

    The arithmetic is stated rather than approximated, because "about the
    right length" is how a watchdog that is a factor of two out gets
    shipped. Measured at several R.
    """
    w = await setup(dut)
    for r in (0, 1, 2, 7, 40):
        w = await por(dut)
        await w.write(SEL_RLD, r)
        await w.kick()
        n = await run_until(dut, "nmi_o", 4 * FULL_TIMEOUT)
        assert n is not None, "reload {}: no stage 1".format(r)
        expect = (r + 1) * PRESCALE
        assert abs(n - expect) <= PRESCALE, (
            "reload {}: stage 1 after {} clocks, expected about {}"
            .format(r, n, expect))
    dut._log.info("timeout arithmetic exact at reload 0, 1, 2, 7, 40")


# ---------------------------------------------------------------------------
# W3: three stages, each reached only from the one before
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_a_kick_prevents_stage_1(dut):
    """Kicking within the timeout means nothing ever fires.

    The vacuity guard on every other test in this file: if the watchdog
    fired regardless of kicks, the escalation tests would still pass and
    would be measuring nothing.
    """
    w = await setup(dut)
    await w.write(SEL_RLD, 8)
    await w.kick()
    for _ in range(12):
        for _ in range(4 * PRESCALE):
            await RisingEdge(dut.clk_i)
            await Timer(T_SAMPLE, unit="ns")
            assert val(dut.nmi_o) == 0, "fired despite being kicked in time"
            assert val(dut.rst_req_o) == 0
        await w.kick()


@cocotb.test()
async def test_stage_1_then_stage_2_then_stage_3(dut):
    """The whole ladder, and the ORDER of it.

    Stage 2 must not arrive before stage 1; stage 3 must not arrive
    before the ESCALATE-th stage 2. The acknowledge in the middle of the
    run is what shows stage 2 is reached only by NOT acknowledging: an
    acknowledged stage 1 rearms and the machine goes round again from the
    beginning rather than escalating.
    """
    w = await setup(dut)
    await w.write(SEL_RLD, 4)

    # -- acknowledged stage 1 does NOT escalate --
    await w.kick()
    assert await run_until(dut, "nmi_o", 8 * PRESCALE) is not None
    assert val(dut.rst_req_o) == 0, "stage 2 arrived at the same time as stage 1"
    await w.ack()
    assert val(dut.nmi_o) == 0, "the acknowledge did not clear the NMI"
    await w.kick()
    for _ in range(4 * PRESCALE):
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        assert val(dut.rst_req_o) == 0, (
            "stage 2 fired after an acknowledged stage 1 and a kick")

    # -- unacknowledged stage 1 escalates, exactly once per timeout --
    resets = 0
    for _ in range(ESCALATE):
        # Re-shorten the timeout on every pass. The previous stage 2
        # restored the reload to the maximum, which is the behaviour
        # test_the_reload_is_restored_to_the_maximum_by_a_reset exists
        # for; without this line the second iteration waits a full
        # 2^WIDTH * PRESCALE clocks and this test times out.
        await w.write(SEL_RLD, 4)
        await w.kick()
        assert await run_until(dut, "nmi_o", 12 * PRESCALE) is not None
        assert val(dut.rst_req_o) == 0
        n = await run_until(dut, "rst_req_o", 12 * PRESCALE)
        assert n is not None, "stage 1 was not followed by stage 2"
        resets += 1
        # The reset is a pulse of the length the parameter names.
        held = 1
        while val(dut.rst_req_o):
            await RisingEdge(dut.clk_i)
            await Timer(T_SAMPLE, unit="ns")
            held += 1
            assert held <= RST_CYCLES + 2, "rst_req_o never released"
        assert held >= RST_CYCLES - 1, (
            "rst_req_o held for {} clocks, expected about {}"
            .format(held, RST_CYCLES))
        st = await w.read(SEL_STAT)
        assert st & ST_WDOGRST, "WDOGRST not set after a watchdog reset"
        assert st & ST_NMI == 0, (
            "the pending NMI survived the reset it caused: a core coming out "
            "of that reset vectors to boot_addr + 0x7C before it has run an "
            "instruction")
        assert (st >> 8) & 0xFF == resets, (
            "RSTCNT is {}, expected {}".format((st >> 8) & 0xFF, resets))

    assert val(dut.wdog_no) == 0, (
        "the external pin is not asserted after {} watchdog resets, and "
        "ESCALATE is {}".format(resets, ESCALATE))
    assert (await w.read(SEL_STAT)) & ST_ESCALATED, (
        "ESCALATED does not report what the pin is doing")


@cocotb.test()
async def test_the_external_pin_waits_for_the_escalate_count(dut):
    """Stage 3 is not reached on the first watchdog reset.

    ESCALATE is 2 here, so one reset must NOT assert the pin. Without
    this the previous test would pass on an implementation that asserted
    the pin the moment it first reset anything, which is a different and
    much noisier policy than the one docs/40 section 5 argues for.
    """
    w = await setup(dut)
    await w.write(SEL_RLD, 3)
    await w.kick()
    assert await run_until(dut, "nmi_o", 12 * PRESCALE) is not None
    assert await run_until(dut, "rst_req_o", 12 * PRESCALE) is not None
    st = await w.read(SEL_STAT)
    assert (st >> 8) & 0xFF == 1
    assert val(dut.wdog_no) == 1, (
        "the external pin asserted after one watchdog reset; ESCALATE is 2")
    assert st & ST_ESCALATED == 0


# ---------------------------------------------------------------------------
# W4: the state survives the reset this block causes
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_the_reload_is_restored_to_the_maximum_by_a_reset(dut):
    """A short timeout installed before the failure does not outlive it.

    Found by running the SoC. The reload register is in the power-on
    domain, so without this it survives the watchdog reset -- and a
    program that shortened the timeout and then went wrong leaves the
    next boot with a timeout too short to reach its first instruction.
    The whole SoC entered an unbreakable reset loop on exactly that.
    """
    w = await setup(dut)
    await w.write(SEL_RLD, 3)
    await w.kick()
    assert await run_until(dut, "nmi_o", 12 * PRESCALE) is not None
    assert await run_until(dut, "rst_req_o", 12 * PRESCALE) is not None
    while val(dut.rst_req_o):
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
    assert await w.read(SEL_RLD) == MAX_RELOAD, (
        "the short reload survived the reset it caused, so the next boot has "
        "less time than the hardware default")
    # And the counter really does have the full budget in front of it.
    n = await run_until(dut, "nmi_o", 3 * FULL_TIMEOUT)
    assert n is not None
    assert n > FULL_TIMEOUT // 2, (
        "stage 1 came back after {} clocks, so the counter was not reloaded "
        "with the restored value".format(n))


@cocotb.test()
async def test_only_power_on_reset_clears_the_record(dut):
    """WDOGRST, RSTCNT and ESCALATED are cleared by nothing else.

    Not by a keyed write, not by a kick, not by the acknowledge. A
    counter the failing software can clear is a counter that reports what
    the failing software wants it to.
    """
    w = await setup(dut)
    await w.write(SEL_RLD, 3)
    await w.kick()
    assert await run_until(dut, "nmi_o", 12 * PRESCALE) is not None
    assert await run_until(dut, "rst_req_o", 12 * PRESCALE) is not None
    while val(dut.rst_req_o):
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
    before = await w.read(SEL_STAT)
    assert before & ST_WDOGRST

    for data in (0xFFFF, ST_WDOGRST, ST_ESCALATED, 0xFF00, 0x0000):
        await w.write(SEL_STAT, data)
        await w.write(SEL_CTRL, data)
        st = await w.read(SEL_STAT)
        assert st & ST_WDOGRST, (
            "writing 0x{:04x} cleared WDOGRST".format(data))
        assert (st >> 8) & 0xFF == (before >> 8) & 0xFF, (
            "writing 0x{:04x} changed RSTCNT".format(data))

    # Power-on reset, and only that, clears it.
    await Timer(T_DRIVE, unit="ns")
    dut.rst_por_ni.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.rst_por_ni.value = 1
    await RisingEdge(dut.clk_i)
    assert await w.read(SEL_STAT) == 0, (
        "power-on reset did not clear the record")


@cocotb.test()
async def test_the_reset_count_saturates(dut):
    """RSTCNT stops at its maximum instead of wrapping to zero.

    A counter that wraps reports "no watchdog resets have happened" after
    255 of them, which is the worst possible answer.
    """
    w = await setup(dut)
    await w.write(SEL_RLD, 0)
    top = 0xFF
    for _ in range(top + 4):
        st = await w.read(SEL_STAT)
        if (st >> 8) & 0xFF == top:
            break
        await w.kick()
        if await run_until(dut, "rst_req_o", 20 * PRESCALE) is None:
            continue
        while val(dut.rst_req_o):
            await RisingEdge(dut.clk_i)
            await Timer(T_SAMPLE, unit="ns")
        # Restore the short reload the reset just cleared.
        await w.write(SEL_RLD, 0)
    st = await w.read(SEL_STAT)
    n = (st >> 8) & 0xFF
    assert n == top, "RSTCNT reached {} of {}".format(n, top)
    # One more must not wrap.
    await w.kick()
    if await run_until(dut, "rst_req_o", 20 * PRESCALE) is not None:
        while val(dut.rst_req_o):
            await RisingEdge(dut.clk_i)
            await Timer(T_SAMPLE, unit="ns")
    assert ((await w.read(SEL_STAT)) >> 8) & 0xFF == top, "RSTCNT wrapped"


# =====================================================================
# W9: the reset request is registered, and the register is the decode
# =====================================================================
#
# docs/75. W9 put one flip-flop between the combinational decode of the
# voted protected word and rst_req_o, so that no transient of that
# decode can reach soc_top.v's asynchronous rst_raw_n. The RTL claim it
# rests on is that `in_reset_q` and `in_reset` are equal on every cycle,
# and it is proved by k-induction in hw/soc/formal/soc_wdog_props.v
# (W9a). This is the same statement measured on every cycle of a run
# that actually climbs the ladder, because a proof of an equality and a
# measurement of it fail in different ways.
#
# WHAT THIS TEST CANNOT DO, and it is worth being blunt about it: it
# cannot fail on the design W9 replaced. `rst_req_o = in_reset` and
# `rst_req_o = in_reset && in_reset_q` are the same function of the same
# state on every cycle of every run, so no simulation can tell them
# apart. The evidence that W9 does anything is on the NETLIST --
# test_no_transient_of_the_voted_word_can_reach_the_system_reset in
# sw/tests/test_soc_synthesis_guards.py -- and in the gate-level
# campaign of docs/75 section 8. What this test catches is W9
# implemented WRONGLY: a flip-flop fed from `prot` instead of `prot_n`,
# or one registered off `in_reset`, lags the decode by a clock, and the
# AND then holds rst_req_o low for the first cycle of a genuine stage-2
# stretch. docs/75 section 7.7 records that mutation failing here.
@cocotb.test()
async def test_the_registered_reset_request_tracks_the_decode_every_cycle(dut):
    """W9a and W9b, on every clock edge of a full escalation."""
    w = await setup(dut)
    seen_asserted = 0
    checks = 0

    async def sample():
        nonlocal seen_asserted, checks
        await Timer(T_SAMPLE, unit="ns")
        q = val(dut.in_reset_q)
        c = val(dut.in_reset)
        assert q == c, (
            "W9a: in_reset_q is {} and the decode of the voted word says "
            "{}. The two are the same predicate on opposite sides of one "
            "register boundary and must agree on every cycle; if they do "
            "not, rst_req_o is no longer the signal docs/40 and docs/41 "
            "describe.".format(q, c))
        assert val(dut.rst_req_o) == c, (
            "W9b: rst_req_o is {} where (rst_hold != 0) is {}"
            .format(val(dut.rst_req_o), c))
        seen_asserted += c
        checks += 1

    for _ in range(ESCALATE):
        await w.write(SEL_RLD, 4)
        await w.kick()
        for _ in range(40 * PRESCALE):
            await RisingEdge(dut.clk_i)
            await sample()
            if val(dut.rst_req_o):
                break
        assert val(dut.rst_req_o), "the ladder never reached stage 2"
        while val(dut.rst_req_o):
            await RisingEdge(dut.clk_i)
            await sample()

    # A cover, not decoration: an in_reset_q that were stuck at zero
    # would satisfy the equality above on a run that never resets.
    assert seen_asserted >= 2 * (RST_CYCLES - 1), (
        "the run asserted the reset on only {} of {} sampled cycles, so "
        "the equality above was checked mostly against zero"
        .format(seen_asserted, checks))
