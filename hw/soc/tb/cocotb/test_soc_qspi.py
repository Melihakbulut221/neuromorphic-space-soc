# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""soc_qspi suite: a register-mode QSPI flash controller, driven against
the specification, with a modelled flash on the wire.

WHERE THE EXPECTATIONS COME FROM. Not from the RTL:

  * The Winbond W25Q128JV datasheet, Revision M, through the
    behavioural model hw/soc/tb/flash_w25q128jv.v that was written from
    it. The model counts every departure from the part's AC table and
    command rules in `violations`, and every test here ends by asserting
    that count is zero -- so "the controller works" means "the device
    the datasheet describes accepted every frame and answered it", and
    not "the controller agrees with itself". What the device holds is
    hw/soc/flow/gen_flash_image.py's pattern, imported here and computed
    for the expectation, never read back from the simulation.
  * The register map as hw/soc/rtl/soc_qspi.v's header STATES it:
    offsets, fields, the little-endian byte lanes of RX and TX, the
    pause at every word, the deselect gap, LOST on a refused write,
    DONE meaning "a CMD write will be accepted".
  * The AMBA 3 APB slave contract soc_uart.v, soc_gpio.v and
    soc_busstat.v already obey: PREADY high, PSLVERR low, one ACCESS
    cycle per transfer.
  * `sw/golden/memmap_gen.py`, generated from `regmap/memmap.yaml`, for
    the slot and the interrupt line. No address literal for the block's
    base appears below.

The RTL was read for the port names and the reset polarity.

WHAT THIS SUITE DOES NOT COVER
------------------------------
  * A flash. The model is a set of inequalities and a byte array; it
    has no process, no voltage, no temperature and no wear, and the
    busy times are scaled from milliseconds to two microseconds. A
    controller that passes here obeys the datasheet as the model
    states it.
  * A pad. The IO lanes meet on a `tri1` net with a pull-up; there is
    no pad, no drive strength and no capacitance, and the datasheet's
    output timing is applied at the model's terminals.
  * The interrupt reaching the core, and the slot being decoded by
    soc_top.v: the whole-SoC program's checks 29 and 30.
  * Any fault model. This block is unprotected.
  * Execute-in-place. The block has none.
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
sys.path.insert(0, str(_REPO / "hw" / "soc" / "flow"))
from golden.memmap_gen import APB_SLOTS, IRQ_SOURCES  # noqa: E402
import gen_flash_image as img                          # noqa: E402

NCS = int(os.environ.get("NCS", "2"))
DIV_W = int(os.environ.get("DIV_W", "4"))
LEN_W = int(os.environ.get("LEN_W", "16"))

# soc_qspi.v's register map.
CONF, CTRL, STAT, RX, TX, CMD, ADDR = 0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18
CTRL_RST, CTRL_IEN = 1 << 0, 1 << 1
ST_BUSY, ST_DR, ST_DONE, ST_LOST, ST_TXE = 1, 2, 4, 8, 16
F_ADDR, F_AQUAD, F_DQUAD, F_WRITE = 1 << 12, 1 << 13, 1 << 14, 1 << 15

# The part's commands, datasheet section 8.1.2 / 8.2.
OP_WREN, OP_VWREN, OP_WRDI = 0x06, 0x50, 0x04
OP_RDSR1, OP_RDSR2, OP_WRSR2 = 0x05, 0x35, 0x31
OP_READ, OP_FAST, OP_QOUT, OP_QIO = 0x03, 0x0B, 0x6B, 0xEB
OP_PP, OP_SE = 0x02, 0x20
OP_JEDEC, OP_RSTEN, OP_RST = 0x9F, 0x66, 0x99
JEDEC_WORD = 0x001840EF          # EF, 40, 18 in little-endian lanes

CLK_NS = 10


def cmd(op, length=0, dummy=0, addr=False, aquad=False, dquad=False,
        write=False):
    v = op | (dummy << 8) | (length << 16)
    if addr:
        v |= F_ADDR
    if aquad:
        v |= F_AQUAD
    if dquad:
        v |= F_DQUAD
    if write:
        v |= F_WRITE
    return v


def val(sig):
    s = str(sig.value)
    if any(c not in "01" for c in s):
        raise AssertionError("non-binary value {!r} on {}".format(s, sig._path))
    return int(s, 2)


def flash(dut, cs):
    return dut.u_flash0 if cs == 0 else dut.g_flash1.u_flash1


async def setup(dut):
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
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
    await Timer(1, unit="ns")
    for cs in range(NCS):
        flash(dut, cs).violations.value = 0
        flash(dut, cs).quad_unaligned.value = 0


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


async def wait_stat(dut, mask, limit=4000):
    """Poll STAT until one of `mask` is set. Bounded: a hang says
    nothing."""
    for _ in range(limit):
        s = await apb_read(dut, STAT)
        if s & mask:
            return s
    raise AssertionError("STAT never showed {:#x}".format(mask))


async def wait_idle(dut, limit=4000):
    for _ in range(limit):
        s = await apb_read(dut, STAT)
        if not (s & ST_BUSY):
            return s
    raise AssertionError("BUSY never dropped")


async def xfer_in(dut, op, length, addr=None, dummy=0, aquad=False,
                  dquad=False, cs=0, div=0):
    """One read-type transaction; returns the words RX delivered, in
    order, pulling each one through the DR pause."""
    await apb_write(dut, CONF, div | (cs << 8))
    if addr is not None:
        await apb_write(dut, ADDR, addr)
    await apb_write(dut, CMD, cmd(op, length, dummy, addr is not None,
                                  aquad, dquad, False))
    words = []
    for _ in range((length + 3) // 4):
        await wait_stat(dut, ST_DR)
        words.append(await apb_read(dut, RX))
    await wait_stat(dut, ST_DONE)
    await apb_write(dut, STAT, ST_DONE)
    return words


async def xfer_out(dut, op, data_words=(), nbytes=None, addr=None, cs=0,
                   div=0, dquad=False):
    """One write-type transaction: the first TX word before CMD, the
    rest at each TXE."""
    if nbytes is None:
        nbytes = 4 * len(data_words)
    await apb_write(dut, CONF, div | (cs << 8))
    if addr is not None:
        await apb_write(dut, ADDR, addr)
    if data_words:
        await apb_write(dut, TX, data_words[0])
    await apb_write(dut, CMD, cmd(op, nbytes, 0, addr is not None, False,
                                  dquad, True))
    for w in data_words[1:]:
        await wait_stat(dut, ST_TXE)
        await apb_write(dut, TX, w)
    await wait_stat(dut, ST_DONE)
    await apb_write(dut, STAT, ST_DONE)


async def read_sr(dut, which, cs=0):
    return (await xfer_in(dut, which, 1, cs=cs))[0]


async def set_qe_volatile(dut, on, cs=0):
    """50h then 31h, datasheet 8.2.5: the volatile write, no busy time."""
    await xfer_out(dut, OP_VWREN, cs=cs)
    await xfer_out(dut, OP_WRSR2, (0x02 if on else 0x00,), nbytes=1, cs=cs)


async def software_reset(dut, cs=0):
    await xfer_out(dut, OP_RSTEN, cs=cs)
    await xfer_out(dut, OP_RST, cs=cs)
    # tRST, scaled to 2 us in tb_soc_qspi.v
    for _ in range(300):
        await RisingEdge(dut.clk_i)


def expect_words(addr, nbytes, seed):
    """What the pattern says a read of nbytes at addr returns, as RX
    words: little-endian lanes, a short last word zero-padded."""
    out = []
    for w in range((nbytes + 3) // 4):
        v = 0
        for k in range(4):
            i = 4 * w + k
            if i < nbytes:
                v |= img.pattern_byte(addr + i, seed) << (8 * k)
        out.append(v)
    return out


def no_violations(dut, where=""):
    for cs in range(NCS):
        n = int(flash(dut, cs).violations.value)
        assert n == 0, "flash {} counted {} datasheet violations {}".format(
            cs, n, where)


@cocotb.test()
async def test_reset_state_and_registers_read_back(dut):
    """Every register resets to zero and STAT to idle; CONF, CMD and
    ADDR read back what was written within their fields and zero
    above them; TX is write-only and CTRL.RST reads zero. The pins:
    every chip select high, SCK low, nothing driven."""
    await setup(dut)
    for r in (CONF, CTRL, STAT, RX, TX, CMD, ADDR):
        assert await apb_read(dut, r) == 0, hex(r)
    assert val(dut.cs_n) == (1 << NCS) - 1
    assert val(dut.sck) == 0
    assert val(dut.dut.io_oe_o) == 0
    assert val(dut.irq_o) == 0

    await apb_write(dut, CONF, 0xFFFFFFFF)
    conf = await apb_read(dut, CONF)
    cs_w = max(1, (NCS - 1).bit_length())
    assert conf == ((1 << DIV_W) - 1) | (((1 << cs_w) - 1) << 8), hex(conf)
    await apb_write(dut, CONF, 0)
    await apb_write(dut, ADDR, 0xFFFFFFFF)
    assert await apb_read(dut, ADDR) == 0xFFFFFF
    await apb_write(dut, ADDR, 0x123456)
    assert await apb_read(dut, ADDR) == 0x123456
    await apb_write(dut, CTRL, CTRL_IEN | CTRL_RST)
    assert await apb_read(dut, CTRL) == CTRL_IEN, "RST is self-clearing"
    await apb_write(dut, CTRL, 0)
    await apb_write(dut, TX, 0xDEADBEEF)
    assert await apb_read(dut, TX) == 0, "TX is write-only"
    # Every CMD write is a real transaction, so the field read-back is
    # checked through a legal one: a quad I/O frame with no data after
    # QE has been set (a quad address with QE clear would drive /HOLD).
    await set_qe_volatile(dut, True)
    frames = int(flash(dut, 0).frames.value)
    v = cmd(OP_QIO, 0, 6, True, True, True, False)
    await apb_write(dut, CMD, v)
    assert await apb_read(dut, CMD) == v
    await wait_idle(dut)
    await apb_write(dut, STAT, ST_DONE)
    assert int(flash(dut, 0).frames.value) == frames + 1
    await software_reset(dut)
    no_violations(dut)


@cocotb.test()
async def test_jedec_id_on_each_chip_select(dut):
    """Datasheet 8.2.27: 9Fh returns EFh, 40h, 18h MSB first, one byte
    per eight clocks on DO. In RX's little-endian lanes that is
    0x001840EF with LEN = 3. Each chip select reaches its own device
    and no other: the device that was not selected saw no frame."""
    await setup(dut)
    for cs in range(NCS):
        before = [int(flash(dut, c).frames.value) for c in range(NCS)]
        words = await xfer_in(dut, OP_JEDEC, 3, cs=cs)
        assert words == [JEDEC_WORD], [hex(w) for w in words]
        after = [int(flash(dut, c).frames.value) for c in range(NCS)]
        for c in range(NCS):
            assert after[c] - before[c] == (1 if c == cs else 0), \
                "chip select {} reached device {}".format(cs, c)
    no_violations(dut)


@cocotb.test()
async def test_read_data_03h_returns_the_image_little_endian(dut):
    """8.2.6: 03h, a 24-bit address, then data MSB first from that
    address, incrementing. The block pauses after every fourth byte
    with DR set, SCK low and CS still asserted, and resumes when RX is
    read. Words are the image's bytes in little-endian lanes; a short
    last word is zero-padded above LEN."""
    await setup(dut)
    addr = 0x000100
    await apb_write(dut, CONF, 0)
    await apb_write(dut, ADDR, addr)
    await apb_write(dut, CMD, cmd(OP_READ, 8, 0, True))
    s = await wait_stat(dut, ST_DR)
    assert s & ST_BUSY, "paused with DR but not BUSY"
    assert not (s & ST_DONE)
    # the pause: SCK low, CS0 low, and it stays that way
    for _ in range(20):
        await RisingEdge(dut.clk_i)
        assert val(dut.sck) == 0, "SCK ran during the DR pause"
        assert val(dut.cs_n) & 1 == 0, "CS rose during the DR pause"
    w0 = await apb_read(dut, RX)
    assert (await apb_read(dut, STAT)) & ST_DR == 0, "reading RX did not clear DR"
    await wait_stat(dut, ST_DR)
    w1 = await apb_read(dut, RX)
    await wait_stat(dut, ST_DONE)
    assert (await apb_read(dut, STAT)) & ST_BUSY == 0
    assert val(dut.cs_n) == (1 << NCS) - 1
    await apb_write(dut, STAT, ST_DONE)
    assert [w0, w1] == expect_words(addr, 8, img.SEED0), \
        [hex(w0), hex(w1)]

    # a short read, and one that is not a whole number of words
    for n in (1, 2, 3, 5, 7):
        got = await xfer_in(dut, OP_READ, n, addr=0x001234 + n)
        assert got == expect_words(0x001234 + n, n, img.SEED0), \
            "LEN {}: {}".format(n, [hex(g) for g in got])
    no_violations(dut)


@cocotb.test()
async def test_fast_read_0bh_with_eight_dummy_clocks(dut):
    """8.2.7: 0Bh, address, eight dummy clocks, then data. On chip
    select 1, whose image carries a different seed, so a read that
    reached device 0 would be wrong in every byte."""
    await setup(dut)
    if NCS < 2:
        return
    addr = 0x0007F1
    got = await xfer_in(dut, OP_FAST, 16, addr=addr, dummy=8, cs=1)
    assert got == expect_words(addr, 16, img.SEED1), [hex(g) for g in got]
    assert got != expect_words(addr, 16, img.SEED0)
    no_violations(dut)


@cocotb.test()
async def test_quad_reads_need_qe_and_then_deliver(dut):
    """8.2.9 and 8.2.11: 6Bh and EBh are refused until Status
    Register-2's QE bit is set; the device drives nothing, the lanes
    read as the pull-ups, and the model counts the refusal. After 50h +
    31h (the volatile write, 8.2.5) SR2 reads QE, 6Bh returns the image
    on four lanes after eight dummy clocks, and EBh returns it after a
    quad address, the FFh mode byte and four dummy clocks. A software
    reset (66h, 99h) drops the volatile QE again."""
    await setup(dut)
    f = flash(dut, 0)
    addr = 0x004000
    got = await xfer_in(dut, OP_QOUT, 8, addr=addr, dummy=8, dquad=True)
    assert int(f.violations.value) == 1, "the refusal was not counted"
    assert got == [0xFFFFFFFF, 0xFFFFFFFF], \
        "a refused quad read returned data: {}".format([hex(g) for g in got])
    f.violations.value = 0

    assert await read_sr(dut, OP_RDSR2) == 0x00
    await set_qe_volatile(dut, True)
    assert await read_sr(dut, OP_RDSR2) == 0x02, "QE not set"
    assert await read_sr(dut, OP_RDSR1) == 0x00, "WEL set by a volatile write"

    got = await xfer_in(dut, OP_QOUT, 12, addr=addr, dummy=8, dquad=True)
    assert got == expect_words(addr, 12, img.SEED0), [hex(g) for g in got]
    got = await xfer_in(dut, OP_QIO, 20, addr=addr + 0x40, dummy=6,
                        aquad=True, dquad=True)
    assert got == expect_words(addr + 0x40, 20, img.SEED0), \
        [hex(g) for g in got]
    assert int(f.quad_unaligned.value) == 0

    await software_reset(dut)
    assert await read_sr(dut, OP_RDSR2) == 0x00, "reset did not drop volatile QE"
    no_violations(dut)


@cocotb.test()
async def test_non_volatile_qe_write_shows_busy_and_survives_reset(dut):
    """8.2.1 and 8.2.5: 06h sets WEL; 31h then starts a self-timed
    write, BUSY reads 1 for tW (scaled to 2 us here) while only Read
    Status is accepted, and WEL is clear afterwards. The non-volatile
    QE survives 66h + 99h. Restored to 0 at the end so the device is as
    the other tests expect it."""
    await setup(dut)
    await xfer_out(dut, OP_WREN)
    assert await read_sr(dut, OP_RDSR1) == 0x02, "WEL not set by 06h"
    await xfer_out(dut, OP_WRSR2, (0x02,), nbytes=1)
    sr1 = await read_sr(dut, OP_RDSR1)
    assert sr1 & 0x01, "BUSY not reported during tW"
    for _ in range(400):
        sr1 = await read_sr(dut, OP_RDSR1)
        if not (sr1 & 0x01):
            break
    assert sr1 == 0x00, "BUSY never dropped, or WEL survived the write"
    assert await read_sr(dut, OP_RDSR2) == 0x02
    await software_reset(dut)
    assert await read_sr(dut, OP_RDSR2) == 0x02, "non-volatile QE lost on reset"
    # and a quad read works with the non-volatile bit
    got = await xfer_in(dut, OP_QIO, 8, addr=0x000200, dummy=6, aquad=True,
                        dquad=True)
    assert got == expect_words(0x000200, 8, img.SEED0)
    # restore
    await xfer_out(dut, OP_WREN)
    await xfer_out(dut, OP_WRSR2, (0x00,), nbytes=1)
    for _ in range(400):
        if not ((await read_sr(dut, OP_RDSR1)) & 0x01):
            break
    assert await read_sr(dut, OP_RDSR2) == 0x00
    no_violations(dut)


@cocotb.test()
async def test_page_program_drives_a_multi_word_tx_phase(dut):
    """8.2.13: 02h, address, one to 256 data bytes, after 06h. Twelve
    bytes go out as three TX words with the block pausing at TXE for
    the second and third; the part programs them after CS rises and
    reports BUSY for tPP; a 03h read then returns them. The area is
    erased (FFh) in the image, above the pattern."""
    await setup(dut)
    addr = 0x009000
    words = [0x11223344, 0xA5C3F00F, 0x00FF7E81]
    await xfer_out(dut, OP_WREN)
    await xfer_out(dut, OP_PP, words, addr=addr)
    assert (await read_sr(dut, OP_RDSR1)) & 0x01, "no tPP busy after program"
    for _ in range(400):
        if not ((await read_sr(dut, OP_RDSR1)) & 0x01):
            break
    got = await xfer_in(dut, OP_READ, 12, addr=addr)
    assert got == words, [hex(g) for g in got]
    # Without 06h the part ignores the program (8.2.13) and the model
    # counts it; the data is unchanged.
    await xfer_out(dut, OP_PP, [0x00000000], addr=addr)
    assert int(flash(dut, 0).violations.value) == 1
    flash(dut, 0).violations.value = 0
    for _ in range(50):
        await RisingEdge(dut.clk_i)
    got = await xfer_in(dut, OP_READ, 4, addr=addr)
    assert got == words[:1]
    no_violations(dut)


@cocotb.test()
async def test_sck_divider_cs_setup_and_the_deselect_gap(dut):
    """CONF.DIV: SCK = clk / (2 (DIV + 1)), measured on the wire as the
    spacing of rising edges; CS falls DIV + 1 clocks before the first
    rising edge and rises DIV + 1 clocks after the last falling edge;
    BUSY holds for 8 (DIV + 1) clocks after CS rises and a CMD written
    in that gap is refused and flagged LOST -- and DONE, which means the
    gap is over, is not set before then."""
    await setup(dut)
    async def watch(rec):
        # one sample per clock, taken after the edge, until CS has
        # fallen and risen again
        t, sck_prev, fell = 0, 0, False
        while True:
            await RisingEdge(dut.clk_i)
            await Timer(1, unit="ns")
            t += 1
            cs = val(dut.cs_n) & 1
            sck = val(dut.sck)
            if cs == 0 and rec["cs_fall"] is None:
                rec["cs_fall"] = t
                fell = True
            if sck and not sck_prev:
                rec["rises"].append(t)
            if sck_prev and not sck:
                rec["last_fall"] = t
            sck_prev = sck
            if fell and cs == 1:
                rec["cs_rise"] = t
                return

    for div in (0, 3):
        await apb_write(dut, CONF, div)
        rec = {"rises": [], "cs_fall": None, "cs_rise": None, "last_fall": None}
        task = cocotb.start_soon(watch(rec))
        await apb_write(dut, CMD, cmd(OP_JEDEC, 3))
        await task
        rises, cs_fall, cs_rise, last_fall = (rec["rises"], rec["cs_fall"],
                                              rec["cs_rise"], rec["last_fall"])
        assert cs_rise is not None, "CS never rose"
        period = 2 * (div + 1)
        assert len(rises) == 8 + 24, "9Fh with LEN 3 is 32 clocks, saw {}".format(len(rises))
        assert all(b - a == period for a, b in zip(rises, rises[1:])), rises
        assert rises[0] - cs_fall == div + 1, (rises[0], cs_fall)
        assert cs_rise - last_fall == div + 1, (cs_rise, last_fall)
        # the gap: BUSY for 8 (DIV + 1) clocks, DONE not before its end
        assert (await apb_read(dut, STAT)) & (ST_BUSY | ST_DONE) == ST_BUSY
        await apb_write(dut, CMD, cmd(OP_JEDEC, 3))
        s = await apb_read(dut, STAT)
        assert s & ST_LOST, "a CMD write during the gap was not flagged"
        frames = int(flash(dut, 0).frames.value)
        await wait_stat(dut, ST_DONE)
        assert int(flash(dut, 0).frames.value) == frames, \
            "the refused CMD started a frame"
        await apb_write(dut, STAT, ST_DONE | ST_LOST)
        await apb_read(dut, RX)
        assert await apb_read(dut, STAT) == 0
    no_violations(dut)


@cocotb.test()
async def test_writes_while_busy_are_refused_and_flagged(dut):
    """CONF, ADDR and CMD writes during a transaction are ignored and
    set LOST; the transaction runs on with the values it captured.
    CTRL and TX writes are accepted, and a write of 1 to STAT.LOST
    clears it."""
    await setup(dut)
    addr = 0x000010
    frames = int(flash(dut, 0).frames.value)
    await apb_write(dut, CONF, 1)
    await apb_write(dut, ADDR, addr)
    await apb_write(dut, CMD, cmd(OP_READ, 8, 0, True))
    await wait_stat(dut, ST_DR)
    await apb_write(dut, CONF, 0x0F | (1 << 8))
    await apb_write(dut, ADDR, 0xABCDEF)
    await apb_write(dut, CMD, cmd(OP_JEDEC, 3))
    await apb_write(dut, CTRL, CTRL_IEN)
    assert await apb_read(dut, CONF) == 1
    assert await apb_read(dut, ADDR) == addr
    assert await apb_read(dut, CMD) == cmd(OP_READ, 8, 0, True)
    assert await apb_read(dut, CTRL) == CTRL_IEN
    s = await apb_read(dut, STAT)
    assert s & ST_LOST
    await apb_write(dut, STAT, ST_LOST)
    assert (await apb_read(dut, STAT)) & ST_LOST == 0
    w0 = await apb_read(dut, RX)
    await wait_stat(dut, ST_DR)
    w1 = await apb_read(dut, RX)
    await wait_stat(dut, ST_DONE)
    await apb_write(dut, STAT, ST_DONE)
    await apb_write(dut, CTRL, 0)
    assert [w0, w1] == expect_words(addr, 8, img.SEED0)
    assert int(flash(dut, 0).frames.value) == frames + 1, \
        "a refused CMD started a frame"
    no_violations(dut)


@cocotb.test()
async def test_interrupt_is_a_level_of_done_or_dr_under_ien(dut):
    """irq_o = CTRL.IEN and (STAT.DONE or STAT.DR). It rises with DR,
    falls when RX is read, rises again with DONE, falls when DONE is
    cleared, and IEN silences it at once."""
    await setup(dut)
    await apb_write(dut, CONF, 0)
    await apb_write(dut, ADDR, 0)
    await apb_write(dut, CMD, cmd(OP_READ, 4, 0, True))
    await wait_stat(dut, ST_DR)
    assert val(dut.irq_o) == 0, "interrupt with IEN clear"
    await apb_write(dut, CTRL, CTRL_IEN)
    assert val(dut.irq_o) == 1, "DR under IEN did not raise the line"
    await apb_read(dut, RX)
    assert val(dut.irq_o) == 0, "reading RX did not drop the line"
    await wait_stat(dut, ST_DONE)
    assert val(dut.irq_o) == 1, "DONE under IEN did not raise the line"
    await apb_write(dut, CTRL, 0)
    assert val(dut.irq_o) == 0, "IEN clear did not silence the line"
    await apb_write(dut, CTRL, CTRL_IEN)
    assert val(dut.irq_o) == 1
    await apb_write(dut, STAT, ST_DONE)
    assert val(dut.irq_o) == 0, "clearing DONE did not drop the line"
    await apb_write(dut, CTRL, 0)
    no_violations(dut)


@cocotb.test()
async def test_abort_raises_cs_and_the_block_recovers(dut):
    """CTRL.RST in the middle of a read drops SCK and releases the lanes
    at once, raises the chip select one half period later (with SCK
    low, as mode 0 requires), clears DR and the TX word, runs the
    deselect gap and then sets DONE
    -- DONE meaning "a CMD write will be accepted", after an abort as
    after a frame. The next transaction is a normal one."""
    await setup(dut)
    await apb_write(dut, CONF, 0)
    await apb_write(dut, ADDR, 0x100)
    await apb_write(dut, CMD, cmd(OP_READ, 64, 0, True))
    await wait_stat(dut, ST_DR)
    assert val(dut.cs_n) & 1 == 0
    await apb_write(dut, CTRL, CTRL_RST)
    # paused at DR, so SCK was low: the lanes go at once
    assert val(dut.sck) == 0
    assert val(dut.dut.io_oe_o) == 0, "abort did not release the lanes"
    for _ in range(2):                       # the half period at DIV = 0
        await RisingEdge(dut.clk_i)
    await Timer(1, unit="ns")
    assert val(dut.cs_n) == (1 << NCS) - 1, "abort did not raise CS"
    s = await apb_read(dut, STAT)
    assert s & ST_BUSY and not (s & ST_DR), hex(s)
    s = await wait_idle(dut)
    assert s & ST_DONE, "no DONE after the abort's deselect gap"
    await apb_write(dut, STAT, ST_DONE)
    got = await xfer_in(dut, OP_JEDEC, 3)
    assert got == [JEDEC_WORD]

    # An abort while SCK is running, at DIV = 3: every SCK level still
    # lasts the full half period -- including the one the abort lands
    # in -- CS rises with SCK low, and the model counts no timing
    # violation. The wire is watched from before the abort.
    await apb_write(dut, CONF, 3)
    await apb_write(dut, ADDR, 0x200)
    await apb_write(dut, CMD, cmd(OP_READ, 64, 0, True))
    for _ in range(100):
        await RisingEdge(dut.clk_i)
    runs = []

    async def watch_levels():
        run, prev = 0, val(dut.sck)
        while True:
            await RisingEdge(dut.clk_i)
            await Timer(1, unit="ns")
            cur = val(dut.sck)
            if cur == prev:
                run += 1
            else:
                runs.append((prev, run))
                run, prev = 1, cur
            if val(dut.cs_n) == (1 << NCS) - 1:
                runs.append((prev, run))
                return

    task = cocotb.start_soon(watch_levels())
    for _ in range(12):                      # three whole levels first
        await RisingEdge(dut.clk_i)
    await apb_write(dut, CTRL, CTRL_RST)
    await task
    assert val(dut.cs_n) == (1 << NCS) - 1, "CS did not rise after the abort"
    # the watch's first two runs are the level it began in and the one
    # it may have joined late; every level after them must be whole
    highs = [n for lvl, n in runs[2:] if lvl == 1]
    assert highs and all(h == 4 for h in highs), \
        "an SCK high level was cut short: {}".format(runs)
    await wait_idle(dut)
    await apb_write(dut, STAT, ST_DONE)
    got = await xfer_in(dut, OP_JEDEC, 3)
    assert got == [JEDEC_WORD]
    no_violations(dut)


@cocotb.test()
async def test_lane_discipline_in_single_and_quad_phases(dut):
    """Datasheet 4.3 and 4.4: IO2 and IO3 are /WP and /HOLD until QE is
    set, so in every single-lane phase the block drives them high and
    IO1 (the part's DO) is never driven. In an EBh frame the address
    and the two mode clocks drive all four lanes, and from the first
    dummy clock after them nothing is driven -- 8.2.9's "high-impedance
    prior to the falling edge of the first data out clock"."""
    await setup(dut)
    # single lane: a whole 03h frame
    await apb_write(dut, CONF, 0)
    await apb_write(dut, ADDR, 0x000020)
    await apb_write(dut, CMD, cmd(OP_READ, 4, 0, True))
    seen = set()
    for _ in range(400):
        await RisingEdge(dut.clk_i)
        await Timer(1, unit="ns")
        if val(dut.cs_n) & 1 == 0:
            oe, o = val(dut.dut.io_oe_o), val(dut.dut.io_o)
            seen.add((oe, o >> 2))
            assert oe == 0b1101, "single-lane oe {:04b}".format(oe)
            assert (o >> 2) == 0b11, "IO2/IO3 not held high"
        elif seen:
            break
    assert seen, "no frame observed"
    await wait_stat(dut, ST_DR)
    await apb_read(dut, RX)
    await wait_stat(dut, ST_DONE)
    await apb_write(dut, STAT, ST_DONE)

    # quad I/O: count clocks by phase
    await set_qe_volatile(dut, True)
    await apb_write(dut, ADDR, 0x000040)
    await apb_write(dut, CMD, cmd(OP_QIO, 4, 6, True, True, True))
    oes = []
    sck_prev = 0
    for _ in range(400):
        await RisingEdge(dut.clk_i)
        await Timer(1, unit="ns")
        if val(dut.cs_n) & 1 == 0:
            sck = val(dut.sck)
            if sck and not sck_prev:
                oes.append((val(dut.dut.io_oe_o), val(dut.dut.io_o)))
            sck_prev = sck
        elif oes:
            break
    # 8 opcode clocks single, 6 address clocks quad, 2 mode clocks quad
    # with FFh, 4 dummy released, 8 data clocks released
    assert len(oes) == 8 + 6 + 2 + 4 + 8, len(oes)
    assert all(oe == 0b1101 for oe, _ in oes[:8]), oes[:8]
    assert all(oe == 0b1111 for oe, _ in oes[8:14]), oes[8:14]
    assert all(oe == 0b1111 and o == 0xF for oe, o in oes[14:16]), oes[14:16]
    assert all(oe == 0 for oe, _ in oes[16:]), oes[16:]
    await wait_stat(dut, ST_DR)
    got = await apb_read(dut, RX)
    assert got == expect_words(0x000040, 4, img.SEED0)[0]
    await wait_stat(dut, ST_DONE)
    await apb_write(dut, STAT, ST_DONE)
    await software_reset(dut)
    no_violations(dut)


@cocotb.test()
async def test_the_address_and_opcode_on_the_wire_are_the_registers(dut):
    """Two devices, two addresses, two opcodes: what the model decoded
    from the wire is what CMD and ADDR held, MSB first. Checked through
    the model's own decode of the frame, which was written from the
    datasheet's bit order."""
    await setup(dut)
    for cs, op, addr in ((0, OP_READ, 0x5A0F3C), (NCS - 1, OP_FAST, 0x000001)):
        await xfer_in(dut, op, 4, addr=addr, dummy=8 if op == OP_FAST else 0,
                      cs=cs)
        f = flash(dut, cs)
        assert int(f.last_opcode.value) == op
        # the model advances its address as it reads: 4 bytes on
        assert int(f.out_addr.value) == addr + 4, hex(int(f.out_addr.value))
    no_violations(dut)


@cocotb.test()
async def test_unimplemented_offsets_read_zero_and_writes_do_nothing(dut):
    """An offset that names no register reads zero, and a write to one
    leaves every real register as it was."""
    await setup(dut)
    await apb_write(dut, CONF, 0x00000103 & ((1 << DIV_W) - 1 | 0x100))
    await apb_write(dut, ADDR, 0x0F0F0F)
    await apb_write(dut, CTRL, CTRL_IEN)
    frames = int(flash(dut, 0).frames.value)
    before = {r: await apb_read(dut, r) for r in (CONF, CTRL, ADDR, STAT)}
    for off in (0x01C, 0x020, 0x040, 0x100, 0x800, 0xFFC):
        assert await apb_read(dut, off) == 0, hex(off)
        await apb_write(dut, off, 0xFFFFFFFF)
    for r, v in before.items():
        assert await apb_read(dut, r) == v, hex(r)
    assert int(flash(dut, 0).frames.value) == frames, \
        "a stray write started a frame"
    await apb_write(dut, CTRL, 0)
    no_violations(dut)


@cocotb.test()
async def test_reads_have_no_side_effects_except_rx(dut):
    """Polling STAT, CMD, CONF and ADDR clears nothing; only a read of
    RX clears DR, and only a write of 1 clears DONE and LOST."""
    await setup(dut)
    await apb_write(dut, CONF, 0)
    await apb_write(dut, ADDR, 0)
    await apb_write(dut, CMD, cmd(OP_READ, 4, 0, True))
    await wait_stat(dut, ST_DR)
    await apb_write(dut, CMD, 0)                  # refused: LOST
    for _ in range(3):
        for r in (STAT, CMD, CONF, ADDR, CTRL, TX):
            await apb_read(dut, r)
    s = await apb_read(dut, STAT)
    assert s & ST_DR and s & ST_LOST, hex(s)
    await apb_write(dut, STAT, 0)
    assert (await apb_read(dut, STAT)) & (ST_DR | ST_LOST) == (ST_DR | ST_LOST)
    await apb_read(dut, RX)
    await wait_stat(dut, ST_DONE)
    for _ in range(3):
        await apb_read(dut, STAT)
    assert (await apb_read(dut, STAT)) & (ST_DONE | ST_LOST) == (ST_DONE | ST_LOST)
    await apb_write(dut, STAT, ST_DONE | ST_LOST)
    assert await apb_read(dut, STAT) == 0
    no_violations(dut)


@cocotb.test()
async def test_the_slot_and_the_line_are_the_frozen_maps(dut):
    """Asserted against the GENERATED map, so a change to
    regmap/memmap.yaml fails here rather than in silicon. The slot,
    source number, device id and line are the values the map has
    carried for QSPICTL since docs/39 and docs/40; what this work
    changes is the status."""
    await setup(dut)
    _base, slot, irq, status = APB_SLOTS["QSPICTL"]
    assert slot == 0x014
    assert irq == 21
    assert status == "implemented", \
        "QSPICTL is decoded by soc_top.v but the map still calls it reserved"
    assert IRQ_SOURCES["QSPICTL"][1] == 9, "the fast interrupt line moved"
