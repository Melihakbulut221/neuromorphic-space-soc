# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""cocotb suite for the hw/soc/rtl/soc_wdog.v bootstrap-strap defect a
hostile design review found on 2026-09-10, and for the fix.

WHAT THE DEFECT WAS. `dis_i` is a board strap. Nothing in this SoC drives
it, no clock relates to it, and soc_gptimer.v passes it through as a
wire, so it had met no flip-flop before this block. It went straight into
`prot_n[P_DISQ]` -- the data input of THREE replica banks that each store
the protected word under a different transform, so one asynchronous pin
fanned into three different combinational cones with three different
delays. A transition near a clock edge can be captured differently by the
three, and W1 holds whatever they settle on for the whole power cycle:
a watchdog silently disabled on a part whose board asked for it armed, or
armed on a part that asked for it off, with WDOGSTAT.DISABLED reporting
the same wrong answer it exists to make honest.

WHAT AN RTL SIMULATION CAN AND CANNOT SAY ABOUT THAT, because it matters
for reading a green run here. It cannot say anything about metastability:
Icarus has no setup time and no resolution time, a two-flop synchroniser
passes values through unchanged, and NO stimulus distinguishes a
synchronised pin from an unsynchronised one BY VALUE. Every test below is
therefore about the STRUCTURE the values travel through, which is what
the defect is:

  1. test_the_strap_pin_does_not_reach_the_replica_banks_combinationally
     the defect itself. With the block held in power-on reset, `prot_n`
     -- which IS the three banks' data input -- is watched while `dis_i`
     moves. On the pre-fix RTL it moves with it, inside the cycle. That
     is the combinational path, and it is the whole finding.
  2. test_the_sample_waits_for_the_synchroniser_and_takes_its_output
     the fix's other half. `dis_seen` resets to 0, so the sample fires on
     the first clock after the release -- on which a synchroniser's
     second flop still holds its reset value. Without the hold-off the
     pin would have been ignored entirely, which is worse than the defect.
  3. test_the_strap_still_disables_and_still_arms
     that the fix did not delete W1. This one PASSES ON BOTH and is
     stated as a regression guard rather than as evidence.

HOW TO RUN THE RED AND THE GREEN, which is the same MODULE against two
different `SOC_WDOG_SRC` values and nothing else:

  green, the tree as committed:

    cd hw/soc/tb/cocotb && make -f Makefile.soc_wdog \\
        MODULE=test_soc_wdog_strap \\
        SIM_BUILD=sim_build_soc_wdog_strap \\
        COCOTB_RESULTS_FILE=results_soc_wdog_strap.xml

  red, against the file before the fix
  (`git show HEAD:hw/soc/rtl/soc_wdog.v > /tmp/pre/soc_wdog.v`):

    cd hw/soc/tb/cocotb && make -f Makefile.soc_wdog \\
        MODULE=test_soc_wdog_strap SOC_WDOG_SRC=/tmp/pre/soc_wdog.v \\
        SIM_BUILD=sim_build_soc_wdog_strap_pre \\
        COCOTB_RESULTS_FILE=results_soc_wdog_strap_pre.xml

`SOC_WDOG_SRC` is already in Makefile.soc_wdog for mutation runs; nothing
here modifies the Makefile or test_soc_wdog.py, whose harness is
imported.

WHAT IS NOT COVERED
-------------------
  * `rst_por_ni`. It is the OTHER asynchronous input this block has, and
    it is not fixed here. soc_top.v gives every other block a
    two-stage, asynchronous-assert synchronous-deassert reset and hands
    this one the raw power-on reset, which W4 requires -- the watchdog
    cannot run on the reset it pulls -- so its release edge is
    asynchronous to clk_i at every flip-flop in the file, including the
    three replicas. Closing that is a soc_top.v change.
  * The register port. `sel_i`, `we_i` and `wdata_i` come from
    soc_gptimer.v's APB decode in this same clock domain and are not
    asynchronous; they are named here so that "what else does this block
    sample" has a written answer rather than a silence.
  * Anything about MTBF, transition density or the strap's real
    electrical behaviour. Two flops is the pattern soc_boot.v already
    uses on THIS SAME PIN; no number here justifies two rather than
    three.
"""

import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_soc_wdog import (                                   # noqa: E402
    Wdog, setup, val, run_until,
    SEL_STAT, ST_DISABLED, ST_NMI,
    CLK_NS, T_DRIVE, T_SAMPLE, MAX_RELOAD, PRESCALE,
)


def bit(dut, sig, pos):
    return (int(getattr(dut, sig).value) >> pos) & 1


# ---------------------------------------------------------------------------
# 1. The path itself
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_the_strap_pin_does_not_reach_the_replica_banks_combinationally(
        dut):
    """`prot_n` is not a convenience signal: it is the wire bundle handed
    to `u_prot_a`, `u_prot_b` and `u_prot_c` as `d_i`. So asking whether
    `dis_i` reaches `prot_n` inside one cycle is asking exactly whether
    an asynchronous board pin reaches three replica flip-flop banks with
    nothing registered in between, which is the defect.

    THE PROBE IS TAKEN WITH THE BLOCK IN POWER-ON RESET, and that is not
    a corner: it is the widest window the pre-fix RTL leaves open. The
    banks are asynchronously reset, so the voted word reads zero, so
    `dis_seen` reads zero, so the `if (!dis_seen)` arm of the next-state
    function is live -- and it stays live until the first clock after the
    release takes the sample. On the pre-fix RTL that arm is
    `prot_n[P_DISQ] = dis_i`, with no flip-flop anywhere on the path, and
    every move of the pin shows up on the banks' data input in the same
    delta.

    A FIXED BLOCK CANNOT MOVE HERE AT ALL. `prot_n[P_DISQ]` is
    `dis_sync1`, which is a flip-flop, and a flip-flop held in reset
    holds. That is the assertion.
    """
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    await Timer(T_DRIVE, unit="ns")
    dut.rst_por_ni.value = 0
    dut.dis_i.value = 0
    dut.sel_i.value = 0
    dut.we_i.value = 0
    dut.wdata_i.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk_i)

    p_disq = int(dut.P_DISQ.value)

    await Timer(T_SAMPLE - T_DRIVE, unit="ns")
    # Nothing has been sampled yet on either version of the block, which
    # is what makes this window the one to probe: the voted word is held
    # at its reset value, so `dis_seen` is clear and the pre-fix
    # next-state function's `prot_n[P_DISQ] = dis_i` arm is live.
    assert val(dut.dis_q) == 0 and val(dut.dis_seen) == 0, (
        "the strap has already been sampled with the block in power-on "
        "reset; this test is probing the wrong window")
    base = bit(dut, "prot_n", p_disq)
    assert base == 0, (
        "the banks' data input already carries a set DISQ with the strap "
        "low")

    # Move the pin, mid-cycle, and look again in the same cycle. Nothing
    # else is touched: no clock edge passes between the two reads.
    dut.dis_i.value = 1
    await Timer(1, unit="ns")
    now = bit(dut, "prot_n", p_disq)
    assert now == 0, (
        "moving the asynchronous strap pin `dis_i` from 0 to 1 changed "
        "the DISQ bit of `prot_n` -- the DATA INPUT OF u_prot_a, u_prot_b "
        "and u_prot_c -- within the same cycle, with no clock edge in "
        "between. That is a combinational path from an unsynchronised "
        "board pin into three replica banks that each transform the word "
        "differently, so a transition near an edge can be captured "
        "differently by the three and the voter's majority of a "
        "three-way disagreement is arbitrary. soc_boot.v takes this same "
        "pin through two flops before it stores it.")

    # And back, so the failure above cannot be one-directional luck.
    dut.dis_i.value = 0
    await Timer(1, unit="ns")
    assert bit(dut, "prot_n", p_disq) == 0

    # THE SAME PROBE IN THE RELEASE CYCLE, which is the cycle the pre-fix
    # block actually takes its sample at the end of. The reset is
    # released between edges, exactly as soc_top.v's power-on reset
    # arrives, and the pin is moved before the edge that samples it.
    await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.rst_por_ni.value = 1
    await Timer(2, unit="ns")
    dut.dis_i.value = 1
    await Timer(1, unit="ns")
    assert bit(dut, "prot_n", p_disq) == 0, (
        "the strap moved in the cycle the power-on reset released and "
        "the banks' data input moved with it, in the same cycle, on the "
        "one edge of the whole mission that decides whether this part "
        "has a watchdog")
    dut.dis_i.value = 0

    # The synchroniser itself, checked by name so that a fix which
    # removed the path by removing the FEATURE fails here too.
    assert int(dut.dis_sync1.value) == 0, (
        "the second synchroniser flop is not holding through reset")


# ---------------------------------------------------------------------------
# 2. The sample instant, and where it reads from
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_the_sample_waits_for_the_synchroniser_and_takes_its_output(dut):
    """A synchroniser in front of a once-per-power-cycle sample is only
    half a fix, and the missing half is not decoration.

    `dis_seen` is in the protected word and resets to 0, so the sample
    fires on the FIRST clock after the release -- and on that clock the
    second synchroniser flop still holds its reset value. Wiring the
    sample to a synchroniser without holding it off would have latched a
    constant 0 for every part ever built: the strap would be ignored
    entirely, WDOGSTAT.DISABLED would read 0 on a board that tied the pin
    high, and W1's one escape hatch would silently not exist. That is a
    worse defect than the one being fixed, which is why it is asserted
    here rather than left to the fact that test 3 happens to pass.

    So: with the strap high through the release, `dis_seen` must still be
    clear on the first two clocks -- the synchroniser is carrying the pin
    down the chain -- and set on the third, with DISQ then reading the
    strap.
    """
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    await Timer(T_DRIVE, unit="ns")
    dut.rst_por_ni.value = 0
    dut.dis_i.value = 1
    dut.sel_i.value = 0
    dut.we_i.value = 0
    dut.wdata_i.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.rst_por_ni.value = 1

    seen = []
    disq = []
    for _ in range(4):
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        seen.append(val(dut.dis_seen))
        disq.append(val(dut.dis_q))

    assert seen == [0, 0, 1, 1], (
        f"`dis_seen` reads {seen} on the first four clocks after the "
        "power-on reset released, and it must read [0, 0, 1, 1]. A 1 on "
        "the first clock is the sample being taken straight off the pin, "
        "which is the defect. A 0 on the third is a hold-off longer than "
        "the synchroniser it is waiting for, which delays W1 for no "
        "reason. soc_boot.v takes this same pin on its third clock.")
    assert disq == [0, 0, 1, 1], (
        f"DISQ reads {disq} across the sample. The value latched on the "
        "third clock is the pin as the first synchroniser flop saw it on "
        "the first, through the second flop, and it must be the strap.")

    # And it is held: W1 is "sampled once and never again", and the
    # synchroniser must not have turned it into a level.
    dut.dis_i.value = 0
    for _ in range(8):
        await RisingEdge(dut.clk_i)
    await Timer(T_SAMPLE, unit="ns")
    assert val(dut.dis_q) == 1, (
        "the strap was dropped after the sample and DISQ followed it. W1 "
        "is sampled ONCE; a strap that can change the answer at any "
        "moment is the hardware back door W1 exists to refuse.")


# ---------------------------------------------------------------------------
# 3. The feature still works, in both directions
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_the_strap_still_disables_and_still_arms(dut):
    """The regression guard, and it passes on the RTL before the fix as
    well -- which is said out loud so that a green run here is not read
    as evidence for anything the two tests above are for.

    Both directions, because a fix that stopped reading the pin would
    pass the "arms" half on its own: a board that ties `dis_i` high gets
    a part with no watchdog and WDOGSTAT.DISABLED says so, and a board
    that ties it low gets the W3 ladder.
    """
    wd = await setup(dut, dis=1)
    for _ in range(8):
        await RisingEdge(dut.clk_i)
    stat = await wd.read(SEL_STAT)
    assert stat & ST_DISABLED, (
        f"WDOGSTAT reads 0x{stat:x} with the strap tied high: a part with "
        "no watchdog that does not admit it is the one thing W1's last "
        "paragraph refuses")
    n = await run_until(dut, "nmi_o", (MAX_RELOAD + 1) * PRESCALE * 2)
    assert n is None, (
        f"the strap was tied high and stage 1 fired after {n} clocks")

    dut.rst_por_ni.value = 0
    dut.dis_i.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.rst_por_ni.value = 1
    for _ in range(8):
        await RisingEdge(dut.clk_i)
    wd = Wdog(dut)
    stat = await wd.read(SEL_STAT)
    assert stat & ST_DISABLED == 0, (
        f"WDOGSTAT reads 0x{stat:x} with the strap tied low")
    n = await run_until(dut, "nmi_o", (MAX_RELOAD + 1) * PRESCALE * 2)
    assert n is not None, (
        "the strap was tied low and stage 1 never fired: the fix armed "
        "nothing")
    stat = await wd.read(SEL_STAT)
    assert stat & ST_NMI, "stage 1 fired and WDOGSTAT.NMI is clear"
