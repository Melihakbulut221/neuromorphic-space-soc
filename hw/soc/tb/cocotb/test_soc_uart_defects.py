# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""cocotb suite for the hw/soc/rtl/soc_uart.v holding-register race an
audit sweep found on 2026-09-11, and for the fix.

WHAT THE DEFECT WAS. `soc_uart.v` has one holding register, `thr`, and
one flag, `thr_full`, and TWO branches of the same always block assign
that flag: the register-write branch sets it when a driver writes DATA,
and the serialiser's loader clears it when it takes the byte. The loader
fires only on a bit boundary -- one system clock in `8*(SCALER+1)` --
and in the version before this suite the write branch came FIRST, so on
that one clock Verilog's last-assignment-wins gave the flag to the
loader:

    thr      <= pwdata      the new byte is stored
    thr_full <= 1'b1        ... and then
    thr_full <= 1'b0        the loader clears it in the same cycle

The frame that goes out is correct -- `shifter` takes the old `thr`,
because these are non-blocking assignments -- and the byte just written
is left sitting in a register nothing will ever load. It is lost, and
STATUS reports the write accepted on the way out, because TF reads
`thr_full` and `thr_full` is now clear. One byte in eight of a blind
writer's stream, at SCALER = 0.

WHY IT SURVIVED. Every one of the five programs in `hw/soc/tb/sw` polls
TE before writing, and a driver that polls cannot hit the window: TE
high means the holding register is empty, so the loader has nothing to
load and does not fire. `tb_soc.v` decodes the console output of exactly
those programs. The defect is reachable only by a driver that writes
blind -- which is what a driver does when it has been told the part
reports back-pressure through TF, and this part does.

WHAT THE FIX IS. The register-write block is moved AFTER the serialiser,
so the write's `thr_full <= 1'b1` is the last assignment. The same cycle
then sends the old byte and keeps the new one. Nothing else is shared
between the two blocks.

HOW TO RUN IT RED. The same MODULE against a copy of the file from
before the fix, which is what `git show <pre>:hw/soc/rtl/soc_uart.v`
produces:

    cd hw/soc/tb/cocotb && make -f Makefile.soc_uart \\
        MODULE=test_soc_uart_defects \\
        SOC_UART_SRC=/tmp/pre/soc_uart.v \\
        SIM_BUILD=sim_build_uart_defects_pre \\
        COCOTB_RESULTS_FILE=results_soc_uart_defects_pre.xml

`scripts/run_cocotb.sh`'s EXTRA_MODULES table runs the green half.

WHAT THIS SUITE DOES NOT COVER. It drives one scaler value and finds the
window by sweeping the write's phase against the bit boundary, so it
shows the window exists and is closed; it does not show that no other
pair of branches in this file shares a register. The receiver does not
exist in this part, so nothing here is about it.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer

from test_soc_uart import (
    CTRL, CT_TE, DATA, SCALER, ST_TE, STATUS,
    apb_read, apb_write, bit_clocks, bit_ns, idle, setup, val,
)

# Small, so a frame is 8 clocks a bit and the phase sweep is short.
SWEEP_SCALER = 0


async def arm(dut, scaler):
    await setup(dut)
    await apb_write(dut, SCALER, scaler)
    await apb_write(dut, CTRL, CT_TE)


def start_monitor(dut, scaler):
    """Decode every frame on tx_o from now on, into a list the caller
    reads afterwards.

    A BACKGROUND MONITOR AND NOT A LOOP OF `recv_byte`, and the reason
    is a defect this file had first. `recv_byte` asserts the line is
    idle when it is called, which is right for it: a caller that starts
    decoding three clocks into a start bit reads a plausible wrong byte
    out of a correct transmitter. But a loop that calls it and catches
    AssertionError cannot tell "no more frames" from "the frame had
    already started before I looked" -- both arrive as the same
    exception, and the first version of this file read the second as the
    first and reported five phases of eight as a swallowed byte on a
    transmitter that was sending correctly.

    The monitor is started before anything is written, so it never
    misses a start bit and never has to guess.
    """
    period = bit_ns(scaler)
    out = []

    async def run():
        while True:
            await FallingEdge(dut.tx_o)
            # Land in the middle of the start bit, then step a bit at a
            # time. Always 1 ns past an edge, so a sample never
            # coincides with the edge that changes the line.
            await Timer(period // 2 + 1, unit="ns")
            if val(dut.tx_o) != 0:
                continue                      # a glitch, not a start bit
            byte = 0
            for i in range(8):
                await Timer(period, unit="ns")
                byte |= val(dut.tx_o) << i
            await Timer(period, unit="ns")
            if val(dut.tx_o) != 1:
                raise AssertionError(
                    "frame 0x{:02X} had no stop bit".format(byte))
            out.append(byte)

    task = cocotb.start_soon(run())
    return out, task


async def quiet(dut, scaler, periods=3):
    """Let the line finish whatever it is doing, then some."""
    await Timer(periods * 10 * bit_ns(scaler), unit="ns")


@cocotb.test()
async def test_the_last_byte_a_blind_writer_writes_always_comes_out(dut):
    """THE DEFECT, stated as the property that separates it from the
    documented behaviour beside it.

    Two DATA writes with no polling, the second walked across every
    phase of the bit boundary. TWO outcomes are correct and the block's
    own header says why:

      * the second write lands while the holding register is still
        full, so it overwrites -- [0x55] on the line. GRLIB's part
        drops the same byte when its FIFO is full and reports it
        through TF, and soc_uart.v says so where it happens.
      * the loader has already taken the first byte, so both go out --
        [0xAA, 0x55].

    The defect is a THIRD outcome that looks like neither: [0xAA], the
    second byte swallowed. It happened when the write landed in the same
    cycle as the load, because both branches assign `thr_full` and the
    loader's `thr_full <= 1'b0` came second.

    What is common to the two correct outcomes and absent from the
    defect is the property this test asserts: the last byte written is
    always the last byte transmitted. A driver may lose an earlier byte
    to a documented overwrite; it may never lose its most recent one to
    a race.
    """
    period = bit_clocks(SWEEP_SCALER)
    seen = {}
    for phase in range(period):
        await arm(dut, SWEEP_SCALER)
        got, mon = start_monitor(dut, SWEEP_SCALER)
        await apb_write(dut, DATA, 0xAA)
        await idle(dut, phase)
        await apb_write(dut, DATA, 0x55)
        await quiet(dut, SWEEP_SCALER)
        mon.kill()
        seen[phase] = list(got)

    swallowed = {ph: g for ph, g in seen.items() if not g or g[-1] != 0x55}
    assert not swallowed, (
        "the LAST byte written did not come out at {} of {} phases of the "
        "bit boundary.".format(len(swallowed), period)
        + "\n\nPhase -> frames on the line: {}".format(dict(sorted(seen.items())))
        + "\n\n[0x55] and [0xAA, 0x55] are both correct -- the first is the"
        + "\ndocumented overwrite of a full holding register. [0xAA] is the"
        + "\ndefect: the write landed in the same cycle as the loader taking"
        + "\nthe first byte, `thr` took the new byte, and the loader's"
        + "\n`thr_full <= 1'b0` was the later assignment, so nothing would"
        + "\never load it. Moving the register-write block AFTER the"
        + "\nserialiser makes the write's `thr_full <= 1'b1` the last"
        + "\nassignment: the old byte goes out and the new one is kept.")


@cocotb.test()
async def test_only_the_documented_overwrite_ever_loses_a_byte(dut):
    """The other half, and the reason the test above is not enough on
    its own.

    "The last byte always comes out" is satisfied by a part that
    transmits ONLY the last byte -- a transmitter that dropped
    everything else would pass it. So the frames are also checked to be
    one of the two sequences the design documents, in order, and nothing
    else: no reordering, no byte that was never written, no third frame.
    """
    period = bit_clocks(SWEEP_SCALER)
    for phase in range(period):
        await arm(dut, SWEEP_SCALER)
        got, mon = start_monitor(dut, SWEEP_SCALER)
        await apb_write(dut, DATA, 0x3C)
        await idle(dut, phase)
        await apb_write(dut, DATA, 0xC3)
        await quiet(dut, SWEEP_SCALER)
        mon.kill()
        got = list(got)
        assert got in ([0xC3], [0x3C, 0xC3]), (
            "phase {}: the line carried {} -- neither the documented "
            "overwrite ([0xC3]) nor".format(phase, [hex(b) for b in got])
            + "\nboth bytes in order ([0x3C, 0xC3]). A byte was reordered,"
            + "\ninvented or lost in a way the design does not describe.")


@cocotb.test()
async def test_a_polling_driver_loses_nothing_at_any_phase(dut):
    """The control, and the reason this defect survived to 2026-09-11.

    A driver that waits for TE before writing cannot hit the window: TE
    high means the holding register is empty, so the loader has nothing
    to take and does not fire in that cycle. Every program in
    hw/soc/tb/sw polls, tb_soc.v decodes their output, and that is the
    whole of why nothing here ever saw it.

    If this test ever fails, the defect above has moved somewhere a
    polling driver can reach it, which is a much more serious thing than
    what this file was written for.
    """
    period = bit_clocks(SWEEP_SCALER)
    want = [0x81, 0x7E, 0x00]
    for phase in range(period):
        await arm(dut, SWEEP_SCALER)
        got, mon = start_monitor(dut, SWEEP_SCALER)
        for byte in want:
            for _ in range(64 * period):
                if await apb_read(dut, STATUS) & ST_TE:
                    break
                await idle(dut, 1)
            else:
                raise AssertionError(
                    "phase {}: TE never went high, so the polling driver "
                    "could not write".format(phase))
            await apb_write(dut, DATA, byte)
            await idle(dut, phase)
        await quiet(dut, SWEEP_SCALER)
        mon.kill()
        got = list(got)
        assert got == want, (
            "phase {}: a POLLING driver wrote {} and the line carried "
            "{}.".format(phase, [hex(b) for b in want], [hex(b) for b in got])
            + "\nPolling is the contract this part offers through TE, and it"
            + "\nhas to lose nothing.")
        assert val(dut.rst_ni) == 1
