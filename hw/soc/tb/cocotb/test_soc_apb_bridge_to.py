# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""The APB bridge's ACCESS timeout, at APB_TIMEOUT = 8.

WHY THIS FILE EXISTS. ST_ACCESS had exactly one exit, `pready_i`, so a
slave that never asserts PREADY held the fabric's ownership queue and
stalled the core until the watchdog's stage-3 reset. It is not a live
bug at the shipping parameters -- eight of the nine mapped slaves drive
PREADY as the literal 1, the ninth does at its default, and an address
inside the window that names no slot is completed by soc_top's mux --
but `soc_apb_wb.v` has a genuinely non-constant PREADY and is written
and proved, so the first wait-state slave wired in makes it live.

WHAT THE PARAMETER COSTS is in soc_apb_bridge_props.v's header and is
not repeated here: three AMBA clauses, each guarded and each stated
where it is deviated from, and none of them at APB_TIMEOUT = 0.

THIS FILE IS ELABORATED SEPARATELY, by Makefile.soc_apb_bridge_to,
because at the default the timeout arm does not exist and every test
below would pass by proving nothing.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

TIMEOUT = 8


async def reset(dut):
    dut.rst_ni.value = 0
    dut.req_i.value = 0
    dut.addr_i.value = 0
    dut.we_i.value = 0
    dut.be_i.value = 0
    dut.wdata_i.value = 0
    dut.pready_i.value = 0
    dut.prdata_i.value = 0
    dut.pslverr_i.value = 0
    await ClockCycles(dut.clk_i, 3)
    dut.rst_ni.value = 1
    await ClockCycles(dut.clk_i, 2)


async def start(dut):
    cocotb.start_soon(Clock(dut.clk_i, 10, units="ns").start())
    await reset(dut)


async def request(dut, addr=0x1000):
    """One read request, granted."""
    dut.req_i.value = 1
    dut.addr_i.value = addr
    dut.we_i.value = 0
    await RisingEdge(dut.clk_i)
    dut.req_i.value = 0


@cocotb.test()
async def test_a_never_ready_slave_ends_in_an_error_not_a_hang(dut):
    """The finding, driven: PREADY is never asserted."""
    await start(dut)
    await request(dut)

    saw_rvalid, saw_err, edges = False, False, 0
    for edges in range(1, 4 * TIMEOUT + 8):
        await RisingEdge(dut.clk_i)
        if int(dut.rvalid_o.value):
            saw_rvalid = True
            saw_err = bool(int(dut.err_o.value))
            break

    assert saw_rvalid, (
        "the bridge never answered a request its slave never completed: "
        "%d edges with PREADY low and no rvalid_o. That is the hang the "
        "timeout exists to convert into an error." % edges)
    assert saw_err, "the transaction ended without err_o, so the core "\
                    "would treat a slave that never answered as a success"
    assert int(dut.timeout_o.value) == 1, (
        "timeout_o did not rise, so nothing downstream could count it")


@cocotb.test()
async def test_the_apb_side_is_held_and_not_aborted(dut):
    """A4 in simulation: PSEL and PENABLE stay high through and after.

    APB has no master-side abort. The fabric is released and the APB
    side is not, which is the whole design and the reason A5 rather
    than A4 is the clause that gives.
    """
    await start(dut)
    await request(dut)

    # PENABLE rises one cycle AFTER PSEL -- that is the APB handshake,
    # not a drop -- so the window starts at ACCESS and not at the grant.
    for _ in range(4):
        await RisingEdge(dut.clk_i)
        if int(dut.penable_o.value):
            break
    assert int(dut.penable_o.value) == 1, "the transfer never reached ACCESS"

    for _ in range(4 * TIMEOUT + 8):
        await RisingEdge(dut.clk_i)
        assert int(dut.psel_o.value) == 1, "PSEL dropped mid-transfer"
        assert int(dut.penable_o.value) == 1, "PENABLE dropped mid-transfer"


@cocotb.test()
async def test_a_late_pready_does_not_produce_a_second_response(dut):
    """The hole the proof found, in simulation.

    Before `&& !to_fired` guarded the PREADY branch, a slave that woke
    up after the timeout sent the machine back to idle and delivered a
    SECOND rvalid for ONE request. A6 and A9 both forbid it and the
    ownership queue would mis-pop on it.
    """
    await start(dut)
    await request(dut)
    for _ in range(TIMEOUT + 4):
        await RisingEdge(dut.clk_i)
        if int(dut.rvalid_o.value):
            break

    # The slave wakes up far too late.
    dut.pready_i.value = 1
    dut.prdata_i.value = 0xA5A5A5A5
    seconds = 0
    for _ in range(TIMEOUT + 8):
        await RisingEdge(dut.clk_i)
        seconds += int(dut.rvalid_o.value)
    assert seconds == 0, (
        "a late PREADY produced %d further responses for one request" % seconds)


@cocotb.test()
async def test_a_slave_that_answers_in_time_is_untouched(dut):
    """The ordinary path still ends the ordinary way."""
    await start(dut)
    await request(dut)
    await RisingEdge(dut.clk_i)          # SETUP -> ACCESS
    dut.pready_i.value = 1
    dut.prdata_i.value = 0x1234_5678
    dut.pslverr_i.value = 0
    await RisingEdge(dut.clk_i)
    dut.pready_i.value = 0
    await RisingEdge(dut.clk_i)
    assert int(dut.rvalid_o.value) == 1
    assert int(dut.rdata_o.value) == 0x1234_5678
    assert int(dut.err_o.value) == 0
    assert int(dut.timeout_o.value) == 0, (
        "a transfer that completed normally set the timeout flag")
