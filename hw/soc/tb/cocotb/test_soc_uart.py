# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""soc_uart suite: the console UART, driven against what is written down.

WHY THIS SUITE EXISTS AND WHAT RAN BEFORE IT
--------------------------------------------
soc_uart.v is the oldest peripheral in hw/soc/rtl and had no simulation
of its own, no property set and no guard until this file. It is also the
block the other four APB suites cite as the contract they follow. Three
of them open with "The AMBA 3 APB slave contract soc_uart.v ... already
obey(s)" as the source of their own PREADY and PSLVERR expectations
(test_soc_gpio.py line 17, test_soc_qspi.py line 22, test_soc_busstat.py
line 23, all read at HEAD cf2ece6) and the fourth writes "PSLVERR. This
slave never asserts it, matching soc_uart.v" (test_soc_gptimer.py line
33). What those four cited was soc_uart.v's header comment. Nothing had
ever driven the bus of the block they cited.

What did run before this file is worth stating precisely, because it is
not nothing: hw/soc/tb/tb_soc.v decodes tx_o while Ibex runs the console
program, so the serialiser and the CTRL.TE path were exercised at one
scaler value, in one direction, with no register ever read back. The
transmit interrupt was not exercised at all -- every program in
hw/soc/tb/sw writes UART_CTRL = UART_CTRL_TE and nothing else (boot.c
line 408, test_ibex.c line 112, fi_npu.c line 213, fi_workload.c line
227, fi_supervisor.c line 311), so CTRL bit 3 has never been set in this
repository and irq_o has been identically zero in every simulation ever
run here.

WHERE THE EXPECTATIONS COME FROM
--------------------------------
  * docs/08-gr801-datasheet-notes.md section 2.5, the APBUART row of the
    register-map table: "0x00 data, 0x04 status, 0x08 control, 0x0C
    scaler, 0x10 FIFO debug, 0x14 FIFO debug control, 0x18 capability",
    quoted there from grip.pdf table 126. Section 3 row 9 is the decision
    to mirror that map.
  * The AMBA 3 APB slave protocol: SETUP then ACCESS, a transfer
    completes in the cycle PSEL, PENABLE and PREADY are all high, and a
    write takes effect once, in ACCESS. This suite drives SETUP cycles
    that it then abandons, so "once, in ACCESS" is measured rather than
    assumed.
  * docs/42-core-fault-injection.md section 8.4 item 3 for what the
    transmitter's empty flag means on a part with one holding register:
    "GRLIB's APBUART reports transmit holding register empty, so the
    program's last write returns while the previous character is still
    shifting and the last character can be two frames behind the store
    that queued it." That defect cost a re-run of a fault-injection
    campaign, and test_status_te_goes_high_a_whole_frame_before_ts_does
    below is that sentence turned into a measurement.
  * sw/golden/memmap_gen.py, generated from regmap/memmap.yaml, for the
    slot and the interrupt line. No address literal for the block's base
    appears below.
  * soc_uart.v's own header for the SUBSET it declares -- transmit only,
    one holding register rather than a FIFO, no parity, no FIFO-debug or
    capability registers, PREADY tied high and PSLVERR tied low. Those
    are the design's stated choices; this suite checks the part reports
    them truthfully, which is a different thing from checking the choices
    are right.

WHAT THIS SUITE COULD NOT CHECK, AND SAYS SO
--------------------------------------------
grip.pdf is not in this repository. The OFFSETS are attested by docs/08
section 2.5, but the BIT POSITIONS inside STATUS (0 DR, 1 TS, 2 TE, 7 TF)
and inside CTRL (1 TE, 3 TI) appear in this tree only in soc_uart.v's own
header, which is the file under test. This suite therefore holds the
block to its header for the bit positions and to docs/08 for the offsets,
and a reader who wants the positions confirmed against Gaisler's document
has to open Gaisler's document. Saying that here is cheaper than a suite
that looks like it checked and did not.

WHAT THIS SUITE DOES NOT COVER
------------------------------
  * A receiver. There is none. DR is checked to stay zero and a read of
    DATA to return zero, which is the whole of the receive story.
  * Parity, other frame formats, break detection, flow control, and the
    FIFO-debug and capability registers. All absent by declaration; the
    suite checks the registers read zero, not that the features would
    work.
  * Baud accuracy against a real clock. The divider is checked to be
    8*(SCALER+1) system clocks per bit, exactly, at three scaler values;
    what that is in bits per second depends on the clock the part gets.
  * The interrupt reaching the core. The line is observed at irq_o; that
    it lands on fast line 0 and vectors at mtvec+0x40 is a whole-SoC
    question and the map assertion at the end is the only part of it
    checked here.
  * Any fault model. This block is unprotected: 52 flip-flops with no
    ECC, no TMR and no parity, and a single event upset in the shifter
    corrupts a console character silently. docs/60 section 5.8 records
    the cell count; nothing in this file is a hardening claim.
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

# docs/08 section 2.5, the APBUART row.
DATA = 0x000
STATUS = 0x004
CTRL = 0x008
SCALER = 0x00C
FIFO_DEBUG = 0x010
FIFO_DEBUG_CTRL = 0x014
CAPABILITY = 0x018

# STATUS bit positions, from soc_uart.v's header (see the note above).
ST_DR = 1 << 0
ST_TS = 1 << 1
ST_TE = 1 << 2
ST_TF = 1 << 7

# CTRL bit positions, same source. RE (bit 0) is the receiver enable this
# part does not implement.
CT_RE = 1 << 0
CT_TE = 1 << 1
CT_TI = 1 << 3

SCALER_BITS = 12
SCALER_MASK = (1 << SCALER_BITS) - 1

CLK_NS = 10

# 8x oversampling: the scaler feeds the oversampling clock, so one bit is
# eight scaler periods. soc_uart.v's header states the divider as
# 8*(SCALER+1) and this is the only place the suite writes it down.
OVERSAMPLE = 8


def bit_clocks(scaler):
    return OVERSAMPLE * (scaler + 1)


def bit_ns(scaler):
    return bit_clocks(scaler) * CLK_NS


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


async def apb_setup_only(dut, addr, data):
    """One SETUP cycle with PENABLE never raised, then release.

    An APB slave must not act on this. It is the phase in which the
    address and the write data are already valid on the bus, so a slave
    that decodes on PSEL alone writes twice or writes early, and the
    symptom in a system is a register that moves when a neighbouring
    slot is addressed.
    """
    await RisingEdge(dut.clk_i)
    dut.psel_i.value = 1
    dut.penable_i.value = 0
    dut.paddr_i.value = addr
    dut.pwrite_i.value = 1
    dut.pwdata_i.value = data
    await RisingEdge(dut.clk_i)
    dut.psel_i.value = 0
    dut.pwrite_i.value = 0
    await Timer(1, units="ns")


async def wait_for_start_bit(dut, limit_clocks):
    """Clocks until tx_o is first low, or an assertion.

    The bound is a check and not a convenience: with the transmitter
    enabled and a byte queued, the load happens on the next bit boundary,
    so the start bit cannot be more than one bit period away. A part that
    never starts would otherwise hang the run instead of failing it.
    """
    for n in range(1, limit_clocks + 1):
        await RisingEdge(dut.clk_i)
        await Timer(1, units="ns")
        if val(dut.tx_o) == 0:
            return n
    raise AssertionError(
        "no start bit within {} clocks: the transmitter never started".format(
            limit_clocks))


async def recv_byte(dut, scaler, slack=4):
    """Decode one frame off tx_o: start bit, eight data bits LSB first,
    stop bit, sampled at the middle of each bit.

    The line is decoded rather than the register write snooped, so the
    baud divider, the shifter and the frame order are inside what the
    run proves. That is soc_uart.v's own stated intent (header, "The
    testbench decodes that line rather than snooping the register
    write") and it is what tb_soc.v does at system level.

    THE LINE MUST BE IDLE WHEN THIS IS CALLED, and that is asserted
    rather than assumed. Every sample below is taken relative to the
    clock edge on which tx_o was first seen low, so a caller that starts
    decoding three clocks into a start bit shifts every sample by three
    clocks and reads a plausible wrong byte out of a correct
    transmitter. That is not hypothetical: the first run of this file
    did exactly that in the interrupt test and decoded 0xBF for a
    transmitted 0x7E. Without this assertion the failure looked like a
    shifter defect.
    """
    period = bit_ns(scaler)
    assert val(dut.tx_o) == 1, \
        "recv_byte was called with the line already low: the frame had " \
        "already started and every sample below would be off by the same " \
        "amount"
    # One bit period plus the clocks of slack the caller needs before the
    # transmitter can load.
    await wait_for_start_bit(dut, bit_clocks(scaler) + slack)
    # Now at the first clock edge of the start bit, plus 1 ns. Land in
    # the middle of each bit, always 1 ns past a clock edge so that a
    # sample never coincides with the edge that changes the line.
    await Timer(period // 2, units="ns")
    assert val(dut.tx_o) == 0, "the start bit was not low at its own middle"
    byte = 0
    for i in range(8):
        await Timer(period, units="ns")
        byte |= val(dut.tx_o) << i
    await Timer(period, units="ns")
    assert val(dut.tx_o) == 1, "the stop bit was not high"
    return byte


async def idle(dut, clocks):
    for _ in range(clocks):
        await RisingEdge(dut.clk_i)
    await Timer(1, units="ns")


@cocotb.test()
async def test_reset_values_of_every_register(dut):
    """Out of reset: CTRL and SCALER are zero, so the transmitter is
    disabled and the divider is at its minimum; STATUS reports an empty
    holding register and an idle shifter; DATA reads zero because there
    is no receiver.

    STATUS is the interesting one. TE ("holding register empty") and TS
    ("shift register empty") are both true out of reset and TF is false,
    so the reset value is ST_TE | ST_TS and nothing else. A part that
    powered up with TF set would deadlock a polling driver on its first
    character, and a part that powered up with the transmitter enabled
    would put the frame it happened to hold on the line before software
    had configured the baud rate.
    """
    await setup(dut)
    assert await apb_read(dut, CTRL) == 0, "the transmitter is enabled out of reset"
    assert await apb_read(dut, SCALER) == 0
    assert await apb_read(dut, DATA) == 0, "DATA is not zero on a part with no receiver"
    status = await apb_read(dut, STATUS)
    assert status == (ST_TE | ST_TS), \
        "STATUS out of reset is {:#x}, expected TE and TS only".format(status)
    assert status & ST_TF == 0, "TF claims a full holding register out of reset"
    assert status & ST_DR == 0, "DR claims received data on a part with no receiver"
    assert val(dut.tx_o) == 1, "the line is not idle high out of reset"
    assert val(dut.irq_o) == 0, "the interrupt is asserted out of reset"
    # The registers this part declares absent.
    for off in (FIFO_DEBUG, FIFO_DEBUG_CTRL, CAPABILITY):
        assert await apb_read(dut, off) == 0, hex(off)


@cocotb.test()
async def test_the_write_path_stores_the_implemented_bits_and_drops_the_rest(dut):
    """CTRL keeps bits 1 and 3 and nothing else; SCALER keeps twelve bits.

    All ones is written to each register and read back, so a bit that is
    stored but not declared shows up as a read-back the specification
    does not allow. RE (bit 0) is the receiver enable of a part with no
    receiver: writing it must not make it appear to exist.
    """
    await setup(dut)
    await apb_write(dut, CTRL, 0xFFFFFFFF)
    ctrl = await apb_read(dut, CTRL)
    assert ctrl == (CT_TE | CT_TI), \
        "CTRL read back {:#x}, expected only TE and TI".format(ctrl)
    assert ctrl & CT_RE == 0, "CTRL.RE is set on a part with no receiver"

    await apb_write(dut, SCALER, 0xFFFFFFFF)
    assert await apb_read(dut, SCALER) == SCALER_MASK, \
        "SCALER is not exactly {} bits wide".format(SCALER_BITS)
    await apb_write(dut, SCALER, 0x000)
    assert await apb_read(dut, SCALER) == 0, "SCALER did not go back to zero"

    # Each bit of CTRL on its own, so a block that decoded the two bits
    # into one register fails here rather than in a console.
    await apb_write(dut, CTRL, CT_TE)
    assert await apb_read(dut, CTRL) == CT_TE
    await apb_write(dut, CTRL, CT_TI)
    assert await apb_read(dut, CTRL) == CT_TI, "TE and TI are not independent"


@cocotb.test()
async def test_the_read_path_returns_each_register_and_zero_elsewhere(dut):
    """Four registers at four offsets, each holding a value the others do
    not, read back one at a time.

    The values are chosen so that no two registers could be confused: a
    read multiplexer with a swapped case arm returns a value that belongs
    to another offset and is caught. Every other offset in the 4 KiB slot
    reads zero, which is the documented behaviour for unoccupied space
    behind the bridge (soc_uart.v header, citing GR740 UM section 2.3).
    """
    await setup(dut)
    await apb_write(dut, CTRL, CT_TI)
    await apb_write(dut, SCALER, 0xABC)
    assert await apb_read(dut, DATA) == 0
    assert await apb_read(dut, STATUS) == (ST_TE | ST_TS)
    assert await apb_read(dut, CTRL) == CT_TI
    assert await apb_read(dut, SCALER) == 0xABC
    for off in (FIFO_DEBUG, FIFO_DEBUG_CTRL, CAPABILITY, 0x01C, 0x020,
                0x100, 0x400, 0x800, 0xFFC):
        assert await apb_read(dut, off) == 0, \
            "offset {:#x} reads non-zero".format(off)
    # Reads have no side effects: the two registers that hold state are
    # unchanged after all of the above.
    assert await apb_read(dut, CTRL) == CT_TI
    assert await apb_read(dut, SCALER) == 0xABC


@cocotb.test()
async def test_the_transmit_path_puts_the_byte_on_the_line_lsb_first(dut):
    """The frame: one low start bit, eight data bits least significant
    first, one high stop bit, the line idle high on both sides.

    Four bytes are sent, each decoded off tx_o. 0x55 and 0xAA are
    complements, so a decoder or a shifter that reversed the bit order
    would return the other one; 0x00 and 0xFF are the two frames whose
    data field is indistinguishable from the start and stop bits, which
    is where a frame that is one bit long in the wrong place shows up.
    """
    await setup(dut)
    await apb_write(dut, SCALER, 0)
    await apb_write(dut, CTRL, CT_TE)
    for byte in (0x55, 0xAA, 0x00, 0xFF):
        assert val(dut.tx_o) == 1, "the line was not idle before the frame"
        await apb_write(dut, DATA, byte)
        got = await recv_byte(dut, 0)
        assert got == byte, "sent {:#04x}, decoded {:#04x}".format(byte, got)
    await idle(dut, 4)
    assert val(dut.tx_o) == 1, "the line did not return to idle high"


@cocotb.test()
async def test_one_bit_lasts_eight_scaler_periods_exactly(dut):
    """The divider is 8*(SCALER+1) system clocks per bit, measured.

    Measured rather than decoded: 0xFF has a 1 in bit 0, so the line
    falls for the start bit and rises again after exactly one bit period
    and stays high for the rest of the frame. Counting clocks between
    those two transitions measures the bit period with no sampling
    tolerance at all -- an off-by-one in the oversampling counter is one
    clock at scaler 0 and this test sees one clock.

    Three scaler values, because a divider that ignored SCALER entirely
    would pass at any single one of them.
    """
    await setup(dut)
    await apb_write(dut, CTRL, CT_TE)
    for scaler in (0, 1, 3):
        await apb_write(dut, SCALER, scaler)
        await apb_write(dut, DATA, 0xFF)
        await wait_for_start_bit(dut, bit_clocks(scaler) + 4)
        n = 0
        while True:
            await RisingEdge(dut.clk_i)
            await Timer(1, units="ns")
            n += 1
            if val(dut.tx_o) == 1:
                break
            assert n <= 4 * bit_clocks(scaler), \
                "the start bit at scaler {} never ended".format(scaler)
        assert n == bit_clocks(scaler), \
            "scaler {}: the start bit lasted {} clocks, expected {}".format(
                scaler, n, bit_clocks(scaler))
        # Let the rest of the frame drain before the next scaler change.
        await idle(dut, 10 * bit_clocks(scaler) + 8)
        assert val(dut.tx_o) == 1


@cocotb.test()
async def test_status_tf_and_te_track_the_holding_register(dut):
    """TF is the holding register being occupied and TE is its
    complement, on a part whose "FIFO" is one byte deep (soc_uart.v
    header).

    With the transmitter disabled the byte cannot leave, so this is the
    one place where TF can be held still and read: write, TF is set and
    TE is clear; enable the transmitter, the byte loads and TF clears
    again. A driver polls exactly this pair before every character.

    WHAT TS MEANS ON THIS PART, recorded because the first version of
    this test asserted the other thing and failed. TS here is
    ~(busy | thr_full): it is low whenever the transmitter still holds a
    byte ANYWHERE, queued or shifting, and not only while the shift
    register is loaded. So with a byte queued behind a disabled
    transmitter the shift register is genuinely empty and TS still reads
    zero. That is consistent with the header's "TE and TS differ by one
    byte" -- they are the two ends of a one-byte pipeline -- and it is
    the reading software wants for "is it safe to stop the clock". It is
    not the literal reading of the name, and a driver that treats TS as
    strictly "shift register empty" will believe a byte is on the wire
    when it is only queued. Asserted here so the meaning is pinned by a
    run rather than by a comment.
    """
    await setup(dut)
    await apb_write(dut, SCALER, 0)
    await apb_write(dut, CTRL, 0)          # transmitter disabled
    await apb_write(dut, DATA, 0x41)
    status = await apb_read(dut, STATUS)
    assert status & ST_TF != 0, "TF is clear with a byte in the holding register"
    assert status & ST_TE == 0, "TE claims empty with a byte in the holding register"
    assert status & ST_TS == 0, \
        "TS reported the transmitter empty with a byte queued behind it"
    assert status == ST_TF, \
        "STATUS with one byte queued is {:#x}, expected TF alone".format(status)
    await idle(dut, 40)
    assert val(dut.tx_o) == 1, "a disabled transmitter drove the line"
    assert await apb_read(dut, STATUS) & ST_TF != 0, \
        "the byte left the holding register with the transmitter disabled"
    await apb_write(dut, CTRL, CT_TE)
    got = await recv_byte(dut, 0)
    assert got == 0x41, "the queued byte came out as {:#04x}".format(got)


@cocotb.test()
async def test_status_te_goes_high_a_whole_frame_before_ts_does(dut):
    """docs/42 section 8.4 item 3, turned into a measurement.

    "GRLIB's APBUART reports transmit holding register empty, so the
    program's last write returns while the previous character is still
    shifting and the last character can be two frames behind the store
    that queued it." A campaign was re-run over that sentence: a console
    drain of twelve bit times was one frame short and the reference run
    recorded 18 characters where the program emitted 19.

    So: queue a byte, wait for it to load, and check TE is already high
    -- the driver may write the next character now -- while TS is still
    low, because the shifter has a whole frame left to go. Then check TS
    only rises after the stop bit. The two flags differing by one frame
    is the property; anything that drains a console has to know it.
    """
    await setup(dut)
    await apb_write(dut, SCALER, 0)
    await apb_write(dut, CTRL, CT_TE)
    await apb_write(dut, DATA, 0x39)
    await wait_for_start_bit(dut, bit_clocks(0) + 4)
    status = await apb_read(dut, STATUS)
    assert status & ST_TE != 0, "TE is low while the holding register is empty"
    assert status & ST_TF == 0, "TF is high while the holding register is empty"
    assert status & ST_TS == 0, "TS claims an idle shifter in the middle of a frame"
    # Three quarters of the way through the frame, TS is still low.
    await idle(dut, 7 * bit_clocks(0))
    assert await apb_read(dut, STATUS) & ST_TS == 0, \
        "TS went high before the frame ended"
    # After the stop bit it is high again.
    await idle(dut, 4 * bit_clocks(0))
    status = await apb_read(dut, STATUS)
    assert status & ST_TS != 0, "TS never reported the shifter empty"
    assert status == (ST_TE | ST_TS), \
        "STATUS after a full frame is {:#x}, expected TE and TS".format(status)


@cocotb.test()
async def test_the_transmit_interrupt_follows_the_enable_and_the_holding_register(dut):
    """CTRL.TI, which nothing in this repository had ever set.

    irq_o is the transmitter's "holding register empty" interrupt: it is
    the AND of the enable and the empty flag, so it is a level and not a
    pulse, and it follows STATUS.TE exactly. Four steps, each of which a
    driver depends on:

      * TI clear and the register empty -- no interrupt, which is the
        state every program in hw/soc/tb/sw leaves the part in and the
        reason this line has been zero in every run so far.
      * TI set and the register empty -- the interrupt asserts at once.
        That is correct for a level "there is room for a character"
        interrupt and it is why an interrupt-driven driver must set TI
        only when it has something to send.
      * The enable removed while the condition holds -- the line drops.
      * The condition removed while the enable holds -- the line drops.
        That second case is the next test.

    irq_o is also checked to equal STATUS.TE at every step, so the line
    and the flag cannot drift apart.
    """
    await setup(dut)
    await apb_write(dut, SCALER, 0)
    assert val(dut.irq_o) == 0, "the interrupt is asserted with TI clear"

    await apb_write(dut, CTRL, CT_TI)
    assert val(dut.irq_o) == 1, \
        "TI set with an empty holding register did not raise the interrupt"
    assert (await apb_read(dut, STATUS)) & ST_TE != 0
    await idle(dut, 20)
    assert val(dut.irq_o) == 1, "the interrupt is a pulse, not a level"

    await apb_write(dut, CTRL, 0)
    assert val(dut.irq_o) == 0, "clearing TI did not drop the interrupt"

    # The enable and the transmitter enable are independent: TI without
    # TE still reports room in the holding register.
    await apb_write(dut, CTRL, CT_TI | CT_TE)
    assert val(dut.irq_o) == 1
    await apb_write(dut, CTRL, CT_TE)
    assert val(dut.irq_o) == 0, "TE alone raised the transmit interrupt"


@cocotb.test()
async def test_the_transmit_interrupt_deasserts_while_a_byte_is_queued(dut):
    """The other half: with TI set, the interrupt is low exactly while
    the holding register holds a byte.

    The transmitter is left DISABLED for the first part so that the byte
    cannot leave, which is the only way to hold the deasserted state
    still for long enough to be sure it is a state and not a glitch --
    forty clocks of it. Then the transmitter is enabled, the byte loads,
    and the interrupt comes back on the same edge the holding register
    empties.

    A handler that acknowledged this interrupt by writing the next
    character depends on precisely this: the line must go down when the
    character is accepted, or the handler re-enters immediately and the
    part becomes an interrupt storm.
    """
    await setup(dut)
    await apb_write(dut, SCALER, 0)
    await apb_write(dut, CTRL, CT_TI)      # enabled, transmitter off
    assert val(dut.irq_o) == 1

    await apb_write(dut, DATA, 0x7E)
    assert val(dut.irq_o) == 0, \
        "the interrupt stayed up with a byte in the holding register"
    for _ in range(40):
        await RisingEdge(dut.clk_i)
        await Timer(1, units="ns")
        assert val(dut.irq_o) == 0, "the interrupt returned while the byte was queued"

    # The decoder is started BEFORE the transmitter is enabled. The load
    # happens on the next bit boundary, which can be the very next clock,
    # so a decoder started after the poll below would already be inside
    # the start bit -- see recv_byte's docstring for what that costs.
    rx = cocotb.start_soon(recv_byte(dut, 0, slack=16))
    await apb_write(dut, CTRL, CT_TI | CT_TE)
    for _ in range(bit_clocks(0) + 8):
        await RisingEdge(dut.clk_i)
        await Timer(1, units="ns")
        if val(dut.irq_o) == 1:
            break
    else:
        raise AssertionError(
            "the interrupt never returned after the byte left the holding register")
    assert (await apb_read(dut, STATUS)) & ST_TF == 0
    got = await rx
    assert got == 0x7E, \
        "the byte the interrupt released came out as {:#04x}".format(got)


@cocotb.test()
async def test_a_write_in_the_setup_phase_does_nothing(dut):
    """AMBA 3 APB: the transfer completes in ACCESS, once. A SETUP cycle
    that is abandoned before PENABLE rises must leave the block exactly
    as it was.

    This is the error path a bridge exercises constantly -- PSEL goes
    high on the selected slave one cycle before PENABLE -- and a slave
    that acted on PSEL alone would write every register twice and would
    queue a console character for every address decode.
    """
    await setup(dut)
    await apb_write(dut, SCALER, 0x111)
    await apb_write(dut, CTRL, CT_TE)
    await apb_setup_only(dut, SCALER, 0xFFF)
    await apb_setup_only(dut, CTRL, CT_TI)
    await apb_setup_only(dut, DATA, 0x5A)
    assert await apb_read(dut, SCALER) == 0x111, "a SETUP cycle wrote SCALER"
    assert await apb_read(dut, CTRL) == CT_TE, "a SETUP cycle wrote CTRL"
    assert await apb_read(dut, STATUS) & ST_TF == 0, \
        "a SETUP cycle queued a character"
    await idle(dut, 3 * bit_clocks(0))
    assert val(dut.tx_o) == 1, "a SETUP cycle put a frame on the line"


@cocotb.test()
async def test_writes_to_the_registers_this_part_does_not_have_do_nothing(dut):
    """The FIFO-debug registers, the capability register and every offset
    in the slot that names nothing are not implemented. A write to any of
    them, and a write to the read-only STATUS register, must leave the
    real registers alone and must not queue a character.

    The part refuses nothing -- PSLVERR is tied low and apb_write asserts
    that on every access here -- so "the write did nothing" is the only
    observable difference between an unimplemented register and a real
    one, and it is what this checks.
    """
    await setup(dut)
    await apb_write(dut, SCALER, 0x2C4)
    await apb_write(dut, CTRL, CT_TE | CT_TI)
    for off in (STATUS, FIFO_DEBUG, FIFO_DEBUG_CTRL, CAPABILITY, 0x01C,
                0x020, 0x080, 0x100, 0x800, 0xFFC):
        await apb_write(dut, off, 0xFFFFFFFF)
    assert await apb_read(dut, SCALER) == 0x2C4, "a stray write disturbed SCALER"
    assert await apb_read(dut, CTRL) == (CT_TE | CT_TI), \
        "a stray write disturbed CTRL"
    assert await apb_read(dut, STATUS) == (ST_TE | ST_TS), \
        "a stray write disturbed STATUS or queued a character"
    await idle(dut, 3 * bit_clocks(0))
    assert val(dut.tx_o) == 1, "a stray write put a frame on the line"
    assert val(dut.irq_o) == 1, "TI was set: the interrupt should be up"


@cocotb.test()
async def test_a_byte_written_over_a_full_holding_register_replaces_it(dut):
    """soc_uart.v header: "Overwriting a full holding register drops the
    previous byte. GRLIB's part does the same when the FIFO is full and
    reports it through TF; a driver is expected to poll."

    So the rule is that the LATER byte survives and the earlier one is
    lost, and TF is the flag that told the driver not to do this. Both
    halves are checked: TF is set between the two writes, and the byte
    that reaches the line is the second one.

    THE ONE CYCLE THIS DOES NOT COVER is the write that lands in the same
    clock as the shifter's load. There the later byte is the one lost,
    not the earlier one -- see the report accompanying this suite. It is
    unreachable by a driver that polls TF, because the load needs TF
    already set and a polling driver only writes when TF is clear, and
    this suite does not enter it.
    """
    await setup(dut)
    await apb_write(dut, SCALER, 0)
    await apb_write(dut, CTRL, 0)          # transmitter off: nothing can leave
    await apb_write(dut, DATA, 0x11)
    assert await apb_read(dut, STATUS) & ST_TF != 0, \
        "TF did not warn that the holding register was occupied"
    await apb_write(dut, DATA, 0x22)
    assert await apb_read(dut, STATUS) & ST_TF != 0, \
        "the second write emptied the holding register"
    await apb_write(dut, CTRL, CT_TE)
    got = await recv_byte(dut, 0)
    assert got == 0x22, \
        "the overwrite kept the earlier byte: got {:#04x}, expected 0x22".format(got)
    # And only one frame was sent: the dropped byte does not appear later.
    await idle(dut, 12 * bit_clocks(0))
    assert val(dut.tx_o) == 1, "a second frame followed the overwrite"
    assert await apb_read(dut, STATUS) == (ST_TE | ST_TS)


@cocotb.test()
async def test_the_receiver_that_is_not_there_never_appears(dut):
    """soc_uart.v header: "STATUS.DR reads 0 forever, CTRL.RE is
    read-only zero, and a read of the data register returns zero. A
    driver that waits for DR will wait forever, which is the correct
    behaviour for a part with no receiver and is better than a receiver
    that appears to exist."

    Held to that through a whole transmitted frame, because the plausible
    defect is a DATA register that reads back the byte last written to it
    -- which is what a loopback test would then appear to prove.
    """
    await setup(dut)
    await apb_write(dut, CTRL, 0xFFFFFFFF)
    assert await apb_read(dut, CTRL) & CT_RE == 0
    await apb_write(dut, SCALER, 0)
    await apb_write(dut, DATA, 0xC3)
    for _ in range(12):
        assert await apb_read(dut, DATA) == 0, \
            "DATA read back the byte written to it: this part has no receiver"
        assert await apb_read(dut, STATUS) & ST_DR == 0, "DR was set"
        await idle(dut, bit_clocks(0))


@cocotb.test()
async def test_the_slot_and_the_line_are_the_frozen_maps(dut):
    """The block is only reachable if it is where the map says it is.

    Asserted against the GENERATED map rather than a literal, so a change
    to regmap/memmap.yaml fails here rather than in silicon. UART0 is
    slot 0x000, source number 2 and fast line 0, and the interrupt this
    suite has just measured for the first time is the one that vectors at
    mtvec+0x40.
    """
    await setup(dut)
    _base, slot, irq, status = APB_SLOTS["UART0"]
    assert slot == 0x000
    assert irq == 2
    assert status == "implemented"
    source, fast, mcause, vector = IRQ_SOURCES["UART0"]
    assert source == irq, "the slot and the interrupt table disagree about UART0"
    assert fast == 0, "the fast interrupt line moved"
    assert mcause == 16
    assert vector == 0x40
