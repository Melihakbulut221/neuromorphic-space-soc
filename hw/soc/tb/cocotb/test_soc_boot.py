# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""soc_boot suite: the bootstrap pins, the boot counter and the record.

WHERE THE EXPECTATIONS COME FROM. Not from the RTL:

  * `docs/08` section 2.4, GR716B's boot flow: bootstrap pins select the
    boot source and can bypass the ROM, a general-purpose register block
    carries a boot report across the reset, and the watchdog is staged
    through the whole thing.
  * `docs/40` W1 and W4, applied one level up. W1: a mechanism the
    software it governs can switch off is not a backstop, so the boot
    counter is not writable. W4 and section 7.2 together: the record has
    to survive the reset it describes, and NOTHING THAT SURVIVES MAY
    SHORTEN THE NEXT BOOT'S BUDGET -- which here is structural, because
    the block has no output at all.
  * `docs/41` section 3.1's power-on domain, for what "survives" means.
  * The AMBA 3 APB slave contract soc_busstat.v, soc_scrub.v and
    soc_gpio.v obey.
  * `sw/golden/memmap_gen.py`, generated from `regmap/memmap.yaml`, for
    the slot. No address literal for the block's base appears below.

The register OFFSETS inside the slot are this block's own and are
written here because here is where they are defined, exactly as
test_soc_scrub.py does for SCRUB.

WHAT THIS SUITE DOES NOT COVER
------------------------------
  * That `rst_ni` here is the SYSTEM reset and `rst_por_ni` the
    power-on one in the real SoC, so that what this suite calls a boot
    is a boot. That is soc_top.v's wiring;
    sw/tests/test_soc_boot_guards.py checks it textually and the
    whole-SoC runs of docs/68 exercise it -- three boots in one
    simulation, with the counter reading 0, 1, 2.
  * That the straps reach a pin. In hardware they reach nothing but
    this block, which is the design (soc_boot.v's header).
  * That the LOADER does anything with what it reads. That is
    hw/soc/tb/sw/boot.c and the whole-SoC runs.
  * Any fault model. This block is unprotected: an upset in the counter
    corrupts a boot decision, and docs/68 section 9 says so.
"""

import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "sw"))
from golden.memmap_gen import APB_SLOTS  # noqa: E402

BSTRAP = 0x000
BSTAT = 0x004
BRPT = 0x008
EPOCH = 0x00C

STRAP_VALID = 1 << 31
STRAP_WDOGDIS = 1 << 16
STAT_LAST = 1 << 8
STAT_OVER = 1 << 9

# Makefile.soc_boot's defaults, and soc_top.v's for LIMIT and NSTRAP.
NSTRAP = 4
CNT_W = 4
LIMIT = 3
CNT_MAX = (1 << CNT_W) - 1

CLK_NS = 10


def val(sig):
    s = str(sig.value)
    if any(c not in "01" for c in s):
        raise AssertionError("non-binary value {!r} on {}".format(s, sig._path))
    return int(s, 2)


async def start(dut, strap=0, wdog_dis=0):
    """Clock up, both resets asserted, pins set. Does NOT release."""
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    dut.rst_por_ni.value = 0
    dut.rst_ni.value = 0
    dut.psel_i.value = 0
    dut.penable_i.value = 0
    dut.paddr_i.value = 0
    dut.pwrite_i.value = 0
    dut.pwdata_i.value = 0
    dut.strap_i.value = strap
    dut.wdog_dis_i.value = wdog_dis
    for _ in range(4):
        await RisingEdge(dut.clk_i)


async def power_on(dut, strap=0, wdog_dis=0):
    """A power cycle: both resets released together, then long enough for
    the strap sample to have been taken."""
    await start(dut, strap, wdog_dis)
    dut.rst_por_ni.value = 1
    dut.rst_ni.value = 1
    for _ in range(6):
        await RisingEdge(dut.clk_i)
    await Timer(1, unit="ns")


async def system_reset(dut, cycles=3):
    """A watchdog stage-2 reset: the SYSTEM reset only, power-on held."""
    await RisingEdge(dut.clk_i)
    dut.rst_ni.value = 0
    for _ in range(cycles):
        await RisingEdge(dut.clk_i)
    dut.rst_ni.value = 1
    for _ in range(2):
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


async def bootcnt(dut):
    return (await apb_read(dut, BSTAT)) & 0xFF


# ----------------------------------------------------------------------
# 1. The straps
# ----------------------------------------------------------------------


@cocotb.test()
async def test_the_straps_are_reported_as_they_were_wired(dut):
    """BSTRAP reads the pins and BSTRAP.VALID says the sample was taken.

    Every value of the four-pin field, because a strap field that
    reported the right number of bits and the wrong ones would look
    exactly like this test passing on one value.
    """
    for pins in range(1 << NSTRAP):
        await power_on(dut, strap=pins, wdog_dis=pins & 1)
        v = await apb_read(dut, BSTRAP)
        assert v & ((1 << NSTRAP) - 1) == pins, (
            "BSTRAP read 0x{:08x} for pins 0b{:04b}".format(v, pins))
        assert v & STRAP_VALID, "VALID low after the sample should be taken"
        assert bool(v & STRAP_WDOGDIS) == bool(pins & 1)
        assert (v >> 24) & 0xF == NSTRAP, (
            "BSTRAP does not report its own width")


@cocotb.test()
async def test_the_sample_is_taken_once_and_the_pins_are_then_ignored(dut):
    """soc_wdog.v W1, one block across: a pin that could change a boot
    decision after the boot began would be a hardware back door into the
    decision. This test moves every pin AFTER the sample and asserts
    nothing moves."""
    await power_on(dut, strap=0b0101, wdog_dis=1)
    before = await apb_read(dut, BSTRAP)
    assert before & 0xF == 0b0101

    dut.strap_i.value = 0b1010
    dut.wdog_dis_i.value = 0
    for _ in range(20):
        await RisingEdge(dut.clk_i)
    after = await apb_read(dut, BSTRAP)
    assert after == before, (
        "BSTRAP moved with the pins: 0x{:08x} -> 0x{:08x}".format(before, after))

    # And a SYSTEM reset does not re-sample either: the sample belongs to
    # the power cycle, not to the boot.
    dut.strap_i.value = 0b1111
    await system_reset(dut)
    assert await apb_read(dut, BSTRAP) == before, (
        "a system reset re-sampled the straps")


@cocotb.test()
async def test_a_power_cycle_re_samples(dut):
    """The other half of the same property: the sample is once PER POWER
    CYCLE, not once ever. A board that is rewired and power-cycled must
    read the new wiring."""
    await power_on(dut, strap=0b0011)
    assert (await apb_read(dut, BSTRAP)) & 0xF == 0b0011
    await power_on(dut, strap=0b1100)
    assert (await apb_read(dut, BSTRAP)) & 0xF == 0b1100


# ----------------------------------------------------------------------
# 2. The boot counter
# ----------------------------------------------------------------------


@cocotb.test()
async def test_the_power_on_boot_is_boot_zero(dut):
    """The power-on release is a release like any other and would
    otherwise be counted. `armed_q` is what makes BSTAT.CNT read "boots
    before this one", which is the number a loader deciding whether to
    attempt THIS boot needs."""
    await power_on(dut)
    assert await bootcnt(dut) == 0
    v = await apb_read(dut, BSTAT)
    assert (v >> 16) & 0xFF == LIMIT, "BSTAT does not report its own limit"
    assert not (v & STAT_OVER)


@cocotb.test()
async def test_every_system_reset_release_counts_one_boot(dut):
    """And a reset held for many cycles is still one boot: what is
    counted is the RELEASE, so the length of the assertion cannot
    inflate it."""
    await power_on(dut)
    assert await bootcnt(dut) == 0
    for i in range(1, CNT_MAX + 1):
        await system_reset(dut, cycles=1 + (i % 5))
        assert await bootcnt(dut) == i, (
            "after {} resets the counter reads {}".format(i, await bootcnt(dut)))


@cocotb.test()
async def test_the_counter_saturates_and_never_wraps(dut):
    """soc_busstat.v's rule, and here it is stronger than telemetry: a
    counter that wrapped would put a part that had rebooted 2^CNT_W
    times back below the attempt limit and start the whole ladder
    again."""
    await power_on(dut)
    for _ in range(CNT_MAX + 4):
        await system_reset(dut)
    assert await bootcnt(dut) == CNT_MAX
    v = await apb_read(dut, BSTAT)
    assert v & STAT_OVER and v & STAT_LAST


@cocotb.test()
async def test_no_write_can_move_the_boot_counter(dut):
    """THE PROPERTY THE BLOCK EXISTS FOR. docs/40 W1's independence
    argument: the one field that decides whether the loader tries again
    is the one field software cannot touch.

    Every offset in the slot's first sixteen words, and two values that
    a runaway core storing wild data would plausibly produce.
    """
    await power_on(dut)
    await system_reset(dut)
    await system_reset(dut)
    assert await bootcnt(dut) == 2
    for addr in range(0, 0x40, 4):
        for data in (0x00000000, 0xFFFFFFFF, 0xA51F0000, 0xDEADBEEF):
            await apb_write(dut, addr, data)
            assert await bootcnt(dut) == 2, (
                "a write of 0x{:08x} to offset 0x{:03x} moved the boot "
                "counter".format(data, addr))


@cocotb.test()
async def test_the_limit_flags_are_the_comparisons_a_loader_would_write(dut):
    """LAST on the last boot the loader may attempt, OVER past it, and
    OVER implies LAST. The loader reads these instead of carrying a
    second copy of LIMIT; a flag that disagreed with the counter beside
    it would be a loader giving up early or never."""
    await power_on(dut)
    for n in range(0, LIMIT + 3):
        v = await apb_read(dut, BSTAT)
        assert (v & 0xFF) == min(n, CNT_MAX)
        assert bool(v & STAT_LAST) == (n + 1 >= LIMIT)
        assert bool(v & STAT_OVER) == (n >= LIMIT)
        if v & STAT_OVER:
            assert v & STAT_LAST
        await system_reset(dut)


# ----------------------------------------------------------------------
# 3. The record
# ----------------------------------------------------------------------


@cocotb.test()
async def test_the_report_and_the_epoch_survive_the_reset_they_describe(dut):
    """docs/40 section 6.2's demonstration, at block level: the only
    thing that carried information between three boots of the whole SoC
    was a register outside the reset domain. This block has two of
    them."""
    await power_on(dut)
    await apb_write(dut, BRPT, 0xB0020015)
    await apb_write(dut, EPOCH, 0x00000007)
    for _ in range(3):
        await system_reset(dut)
        assert await apb_read(dut, BRPT) == 0xB0020015, (
            "the boot report did not survive a system reset")
        assert await apb_read(dut, EPOCH) == 0x00000007


@cocotb.test()
async def test_a_power_cycle_clears_the_record(dut):
    """The other half. A report that survived a POWER CYCLE would say a
    boot failed on a part that has just been powered up, which is the
    one reading an operator must be able to trust."""
    await power_on(dut)
    await apb_write(dut, BRPT, 0xB0020015)
    await apb_write(dut, EPOCH, 0x0000002A)
    await power_on(dut)
    assert await apb_read(dut, BRPT) == 0
    assert await apb_read(dut, EPOCH) == 0
    assert await bootcnt(dut) == 0


@cocotb.test()
async def test_the_record_is_written_only_by_its_own_offset(dut):
    """A write to any other offset must not land in either word. The
    report is evidence, and evidence that a nearby register write can
    scribble on is not evidence."""
    await power_on(dut)
    await apb_write(dut, BRPT, 0x11111111)
    await apb_write(dut, EPOCH, 0x22222222)
    for addr in range(0, 0x40, 4):
        if addr in (BRPT, EPOCH):
            continue
        await apb_write(dut, addr, 0xFFFFFFFF)
        assert await apb_read(dut, BRPT) == 0x11111111
        assert await apb_read(dut, EPOCH) == 0x22222222


# ----------------------------------------------------------------------
# 4. The bus, and the map
# ----------------------------------------------------------------------


@cocotb.test()
async def test_an_offset_that_names_no_register_reads_zero_and_completes(dut):
    """soc_busstat.v's and soc_scrub.v's convention. A slot that did not
    complete would hang the bridge and the core with it."""
    await power_on(dut)
    for addr in (0x010, 0x014, 0x080, 0x400, 0xFFC):
        assert await apb_read(dut, addr) == 0
        await apb_write(dut, addr, 0xFFFFFFFF)
        assert await apb_read(dut, addr) == 0


@cocotb.test()
async def test_the_block_sits_where_the_generated_map_says(dut):
    """The map is the source. This test fails if regmap/memmap.yaml
    moves BOOTREG or marks it reserved again, which is the case in which
    every address in hw/soc/tb/sw/soc_boot.h is wrong."""
    assert "BOOTREG" in APB_SLOTS, "the map has no BOOTREG slot"
    base, slot, irq, status = APB_SLOTS["BOOTREG"]
    assert status == "implemented", (
        "the map still calls BOOTREG reserved; docs/68 promotes it")
    assert slot == 0x017, "BOOTREG has moved slot"
    assert base == 0xFF917000, "BOOTREG has moved address"


@cocotb.test()
async def test_the_block_has_no_interrupt_and_the_map_agrees(dut):
    """A boot register does not interrupt: everything it reports is read
    once, by a loader, before anything else runs. The map gives it no
    line, and this test is what stops a later document giving it one
    without noticing that the block has no output to drive it with."""
    from golden.memmap_gen import IRQ_SOURCES
    assert "BOOTREG" not in IRQ_SOURCES, (
        "BOOTREG has acquired an interrupt line; soc_boot.v has no irq_o")
    assert not hasattr(dut, "irq_o")


# ----------------------------------------------------------------------
# 5. B1: the protection, and its report (docs/69)
# ----------------------------------------------------------------------
#
# These four are the only tests in this suite that reach into the
# hierarchy, and they do it for the reason docs/16 section 1.2 allows:
# the block has no port through which a fault can be injected, so a
# masking claim cannot be made from the outside. The OBSERVATION is
# still made entirely through the bus.
#
# What they are NOT is the campaign. hw/soc/tb/cocotb/test_soc_boot_fi.py
# injects into every bit of every replica at seeded-random cycles, with
# a golden model and a counterfactual build; these four are the directed
# checks that the mechanism is wired up at all, and they run in the
# functional suite so that a build which quietly lost it fails here
# rather than only in a campaign somebody has to remember to run.

STAT_TMRERR = 1 << 31
STAT_TMRCNT = 0xF << 27


def _replica(dut, which):
    return getattr(getattr(dut.g_prot_tmr, "u_prot_" + which), "bits")


@cocotb.test()
async def test_the_mismatch_report_reads_zero_on_a_healthy_part(dut):
    """docs/44 section 11's rule, and the precondition for every other
    reading of this field: a report that was non-zero on a clean part
    would make BSTAT.TMRCNT a counter of nothing in particular."""
    await power_on(dut)
    for _ in range(4):
        await system_reset(dut)
    v = await apb_read(dut, BSTAT)
    assert v & (STAT_TMRERR | STAT_TMRCNT) == 0, (
        "BSTAT reports a TMR mismatch on a part nothing has upset: "
        "0x{:08x}".format(v))


@cocotb.test()
async def test_an_upset_in_one_replica_is_masked_and_counted(dut):
    """B1's whole claim, directed: flip one bit of one replica and every
    register read is unchanged, and the block says it happened.

    The bit chosen is the top of the boot counter, which is the field
    docs/68 section 16 item 1 ranks first -- an upset there is a part
    that gives up early and stays that way, because the counter is
    saturating and lives in the power-on domain."""
    await power_on(dut)
    await system_reset(dut)
    before = await apb_read(dut, BSTAT)
    assert before & 0xFF == 1

    bank = _replica(dut, "a")
    await RisingEdge(dut.clk_i)
    await Timer(1, unit="ns")
    top = CNT_W - 1
    # P_CNT: dly(2) + valid(1) + strap(NSTRAP) + wdis(1) + armed(1)
    #        + sys(1). Recomputed, not copied, so a field inserted in
    #        the middle of the word moves this with it.
    p_cnt = 2 + 1 + NSTRAP + 1 + 1 + 1
    bank.value = val(bank) ^ (1 << (p_cnt + top))
    await RisingEdge(dut.clk_i)
    await Timer(1, unit="ns")

    after = await apb_read(dut, BSTAT)
    assert after & ~(STAT_TMRERR | STAT_TMRCNT) == \
        before & ~(STAT_TMRERR | STAT_TMRCNT), (
        "a flip of one replica's boot counter changed what a bus master "
        "reads: 0x{:08x} -> 0x{:08x}".format(before, after))
    assert after & STAT_TMRERR, "the mismatch was corrected and not reported"
    assert (after >> 27) & 0xF == 1, (
        "TMRCNT did not count the mismatch: 0x{:08x}".format(after))

    # And the scrub: the corrected word goes back into all three
    # replicas on the next edge, so the three agree again immediately.
    # That is what bounds the exposure to a coincident second upset at
    # one clock cycle rather than at the rest of the mission, and it is
    # the property soc_tmr_bank.v's "no write enable" exists for.
    assert val(_replica(dut, "a")) == val(_replica(dut, "a")), "read twice"
    later = await apb_read(dut, BSTAT)
    assert (later >> 27) & 0xF == 1, (
        "TMRCNT kept counting after the fault was gone, so the scrub did "
        "not restore the replica: 0x{:08x}".format(later))


@cocotb.test()
async def test_the_mismatch_report_cannot_be_cleared_by_software(dut):
    """docs/41 section 5.3: a record software can erase is a record an
    upset can erase. Neither field is clearable and no write reaches
    either, which is D1's shape applied to the state B1 added."""
    await power_on(dut)
    bank = _replica(dut, "b")
    await RisingEdge(dut.clk_i)
    await Timer(1, unit="ns")
    bank.value = val(bank) ^ 1
    for _ in range(3):
        await RisingEdge(dut.clk_i)
    await Timer(1, unit="ns")
    seen = await apb_read(dut, BSTAT)
    assert seen & STAT_TMRERR and (seen >> 27) & 0xF == 1

    for addr in (BSTRAP, BSTAT, BRPT, EPOCH, 0x010, 0x020):
        for data in (0x00000000, 0xFFFFFFFF, 0xF8000000):
            await apb_write(dut, addr, data)
    after = await apb_read(dut, BSTAT)
    assert after & STAT_TMRERR, "a write cleared TMRERR"
    assert (after >> 27) & 0xF == 1, "a write moved TMRCNT"


@cocotb.test()
async def test_the_mismatch_counter_saturates(dut):
    """soc_busstat.v's rule for every counter in this design. A counter
    that wrapped would let a part with many masked upsets report fewer
    than a part with none."""
    await power_on(dut)
    bank = _replica(dut, "c")
    for _ in range(20):
        await RisingEdge(dut.clk_i)
        await Timer(1, unit="ns")
        bank.value = val(bank) ^ 1
        await RisingEdge(dut.clk_i)
        await RisingEdge(dut.clk_i)
    v = await apb_read(dut, BSTAT)
    assert (v >> 27) & 0xF == 0xF, (
        "TMRCNT did not saturate after twenty mismatches: "
        "0x{:08x}".format(v))
    assert v & STAT_TMRERR
