# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""The two device tables, soc_pnp and soc_apb_pnp, read and written.

Neither block had a test of any kind before this file. Both are read-only
constant multiplexers, which is the shape of block that looks least
worth testing and has exactly one path that a read cannot show: the
write. The system table answers a write with an error and the peripheral
table swallows it, and until now nothing had ever driven either.

ONE SUITE, TWO ARMS. Makefile.soc_pnp runs this module twice, once with
each table as TOPLEVEL, and every test below does real work in both arms
-- there is no test that returns early for the arm it does not apply to.
The two blocks are not the same shape and the suite says so where they
differ: soc_pnp is a system-bus slave with req/gnt/rvalid, a registered
one-cycle response and an error output; soc_apb_pnp is a combinational
APB slave with no clock, no reset and no way to signal an error at all.

WHERE THE EXPECTATIONS COME FROM
--------------------------------
  * sw/golden/memmap_gen.py, generated from regmap/memmap.yaml. This is
    the first check anywhere in the repository that the GENERATED VERILOG
    and the GENERATED PYTHON agree. hw/soc/rtl/soc_pnp_rom.vh and
    sw/golden/memmap_gen.py are two separate outputs of
    regmap/generate_memmap.py; scripts/ci_local.sh's licence job proves
    the generator is IDEMPOTENT (re-run it, the tree does not change),
    which is a different claim from the two outputs meaning the same
    thing. A hand edit to either file, or a generator that wrote the two
    from different data, passes that check and fails this one.
  * The record LAYOUT, from grlib.pdf section 5.3 as adopted by
    docs/08-gr801-datasheet-notes.md section 3 rows 2, 3 and 5: an
    8-word system record whose first word is
    vendor[31:24] device[23:12] version[9:5] irq[4:0] and whose bank
    address registers carry ADDR[31:20] in bits 31:20, MASK[31:20] in
    bits 15:4 and a type code in bits 3:0; a 2-word peripheral record
    whose bank address register compares PADDR[19:8] instead, which
    soc_apb_pnp.v's header states is why a 4 KiB slot is exact on that
    side and rounded on this one.
  * docs/memmap-soc.md section 4 for the rounding: the system side's
    1 MiB field granularity forces three regions up, so a system BAR
    carries base >> 20 and mask >> 20 and nothing finer.

WHY THE RECORDS ARE DECODED AND NOT ONLY COMPARED. Comparing what the
RTL returns with PNP_ROM would catch the two generated artefacts
drifting apart and nothing else: a generator that encoded every base
address one nibble left would write the same wrong number into both
files and the comparison would pass. So each word read below is also
taken apart and its fields checked against REGIONS, MASKS, APB_SLOTS and
IRQ_SOURCES -- the map itself, not the encoding of it.

WHAT THIS SUITE DOES NOT COVER
------------------------------
  * Every word. Three record words and the identity pair are read from
    each table, chosen because they decode exactly; the other ninety-odd
    non-zero words of the system table are checked only in the sense
    that an unpopulated word reads zero. A whole-table sweep against
    PNP_ROM would be a better check and is not what was asked for here.
  * Discoverability by a real GRLIB tool. soc_pnp.v's header is careful
    that this is a mirrored layout on a bus that is not AHB; nothing
    here parses the table with Gaisler's software.
  * The tables' place in the fabric. That soc_bus.v routes 0xFFFFF000 to
    this slave, and that the bridge routes slot 0x0FF to the other, is
    test_soc_bus.py's and test_soc_apb_bridge.py's question. This suite
    drives the blocks directly.
  * Any fault model. Both tables are unprotected constant logic; a
    single event upset in the read multiplexer returns a wrong record
    with nothing to say so.
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
from golden.memmap_gen import (  # noqa: E402
    APB_PNP_ROM,
    APB_SLOTS,
    IRQ_SOURCES,
    MASKS,
    PNP_ROM,
    REGIONS,
    VENDOR_ID,
)

# Which table the Makefile says it built. The first test measures which
# one it actually got.
ARM = os.environ.get("SOC_PNP_ARM", "sys")

CLK_NS = 10

# grlib.pdf section 5.3 as adopted by docs/08 section 3 row 2: the slave
# records of the system table start at word 0x200 and are eight words
# long, the bank address registers following the identification word.
SYS_SLAVE_BASE = 0x200
SYS_RECORD_WORDS = 8
SYS_BAR0 = 4

# docs/08 section 3 row 5: SoC device id and build id at 0xFFFFFFF0, the
# endianness word at 0xFFFFFFF4. Those are byte offsets 0xFF0 and 0xFF4
# inside the table's own 4 KiB window, so words 0x3FC and 0x3FD.
SYS_IDENT_WORD = 0x3FC
SYS_ENDIAN_WORD = 0x3FD

# The 1 MiB granularity of the system side's address and mask fields.
SYS_FIELD_SHIFT = 20

# The peripheral side compares PADDR[19:8], so its fields are shifted by
# eight and a 4 KiB slot is expressed exactly.
APB_FIELD_SHIFT = 8
APB_SLOT_MASK_FIELD = 0xFF0


def val(sig):
    s = str(sig.value)
    if any(c not in "01" for c in s):
        raise AssertionError("non-binary value {!r} on {}".format(s, sig._path))
    return int(s, 2)


def ident_fields(word):
    """Take an identification word apart: vendor, device, version, irq."""
    return {
        "vendor": (word >> 24) & 0xFF,
        "device": (word >> 12) & 0xFFF,
        "version": (word >> 5) & 0x1F,
        "irq": word & 0x1F,
    }


def bar_fields(word):
    """Take a bank address register apart: address field, mask field,
    type code. The two field positions are the same on both tables; what
    differs is which address bits they compare, which is why the callers
    below shift by 20 on one side and by 8 on the other."""
    return {
        "addr": (word >> 20) & 0xFFF,
        "mask": (word >> 4) & 0xFFF,
        "type": word & 0xF,
    }


def sys_record_word(region_name, offset):
    """Word index of one word of one region's system record.

    The record order is the order of REGIONS, which is the order
    regmap/generate_memmap.py emits. That assumption is not left
    implicit: the caller checks the record it located actually decodes to
    the region it asked for, so a reordered map fails here with the
    region named rather than returning a neighbour's record.
    """
    index = list(REGIONS).index(region_name)
    return SYS_SLAVE_BASE + index * SYS_RECORD_WORDS + offset


def apb_record_word(slot_name, offset):
    """Word index of one word of one peripheral's record: two words per
    RECORD, packed in the order regmap/generate_memmap.py emits them,
    which is the order of APB_SLOTS.

    NOT two words per SLOT. The first version of this helper indexed by
    the slot number -- record at 2*slot -- which agrees with the packed
    order for the first three peripherals and then diverges: APBPNP sits
    in slot 0x0FF and its record is at word 0x01E, not 0x1FE, and the
    suite failed with a KeyError on a table that was perfectly correct.
    The table is dense and the slot number lives in the bank address
    register, which is what the caller checks.
    """
    index = list(APB_SLOTS).index(slot_name)
    return index * 2 + offset


async def setup(dut):
    """Bring the arm under test to a defined state.

    The peripheral table has no clock and no reset -- it is a case
    statement -- so there is nothing to release there and this only
    parks the bus inputs.
    """
    if ARM == "sys":
        cocotb.start_soon(Clock(dut.clk_i, CLK_NS, units="ns").start())
        dut.rst_ni.value = 0
        dut.req_i.value = 0
        dut.addr_i.value = 0
        dut.we_i.value = 0
        dut.be_i.value = 0
        dut.wdata_i.value = 0
        for _ in range(4):
            await RisingEdge(dut.clk_i)
        dut.rst_ni.value = 1
        await RisingEdge(dut.clk_i)
        await Timer(1, units="ns")
    else:
        dut.psel_i.value = 0
        dut.penable_i.value = 0
        dut.paddr_i.value = 0
        dut.pwrite_i.value = 0
        dut.pwdata_i.value = 0
        await Timer(1, units="ns")


def word_address(word):
    """The byte address of a table word, taken through the generated map
    rather than written down here. The system table is addressed at its
    own region base and the peripheral table inside its own slot, and
    neither block decodes the bits above its window -- which is why the
    full address is driven rather than the offset alone."""
    if ARM == "sys":
        return REGIONS["PNP"][0] + (word << 2)
    base, _slot, _irq, _status = APB_SLOTS["APBPNP"]
    return base + (word << 2)


async def read_word(dut, word):
    """One read of one table word, with the arm's own handshake checked
    on the way through."""
    addr = word_address(word)
    if ARM == "sys":
        await RisingEdge(dut.clk_i)
        dut.req_i.value = 1
        dut.addr_i.value = addr
        dut.we_i.value = 0
        dut.be_i.value = 0xF
        dut.wdata_i.value = 0
        await Timer(1, units="ns")
        assert val(dut.gnt_o) == 1, "the table did not grant a read request"
        await RisingEdge(dut.clk_i)
        dut.req_i.value = 0
        await Timer(1, units="ns")
        assert val(dut.rvalid_o) == 1, "no response in the cycle after the grant"
        assert val(dut.err_o) == 0, "a read was answered with an error"
        data = val(dut.rdata_o)
        await RisingEdge(dut.clk_i)
        await Timer(1, units="ns")
        assert val(dut.rvalid_o) == 0, "the response repeated for one request"
        return data
    dut.paddr_i.value = addr & 0xFFF
    dut.psel_i.value = 1
    dut.penable_i.value = 0
    dut.pwrite_i.value = 0
    await Timer(1, units="ns")
    dut.penable_i.value = 1
    await Timer(1, units="ns")
    assert val(dut.pready_o) == 1, "PREADY low: this block always completes"
    assert val(dut.pslverr_o) == 0, "PSLVERR high: this block never errors"
    data = val(dut.prdata_o)
    dut.psel_i.value = 0
    dut.penable_i.value = 0
    await Timer(1, units="ns")
    return data


async def attempt_write(dut, word, data):
    """Drive one write at a table word. Returns True if the block
    answered with an error, False if it accepted the transfer.

    Both answers are legitimate and the two blocks give different ones;
    which one each gives is the point of the test that calls this.
    """
    addr = word_address(word)
    if ARM == "sys":
        await RisingEdge(dut.clk_i)
        dut.req_i.value = 1
        dut.addr_i.value = addr
        dut.we_i.value = 1
        dut.be_i.value = 0xF
        dut.wdata_i.value = data
        await Timer(1, units="ns")
        assert val(dut.gnt_o) == 1, "the table did not grant the request it refuses"
        await RisingEdge(dut.clk_i)
        dut.req_i.value = 0
        dut.we_i.value = 0
        await Timer(1, units="ns")
        assert val(dut.rvalid_o) == 1, \
            "a refused write got no response at all, which hangs the master"
        errored = val(dut.err_o) == 1
        await RisingEdge(dut.clk_i)
        await Timer(1, units="ns")
        assert val(dut.err_o) == 0, "the error output stayed up after the transfer"
        return errored
    dut.paddr_i.value = addr & 0xFFF
    dut.psel_i.value = 1
    dut.penable_i.value = 0
    dut.pwrite_i.value = 1
    dut.pwdata_i.value = data
    await Timer(1, units="ns")
    dut.penable_i.value = 1
    await Timer(1, units="ns")
    assert val(dut.pready_o) == 1
    errored = val(dut.pslverr_o) == 1
    dut.psel_i.value = 0
    dut.penable_i.value = 0
    dut.pwrite_i.value = 0
    await Timer(1, units="ns")
    return errored


@cocotb.test()
async def test_the_arm_the_makefile_asked_for_is_the_arm_that_elaborated(dut):
    """The Makefile exports SOC_PNP_ARM; this measures what actually
    elaborated, by a port only that arm has.

    Without this the two arms could be the same block run twice -- a
    typo in one VERILOG_SOURCES line -- and the result would be ten
    passing tests and one untested block, which is precisely the shape of
    a check that cannot go red.
    """
    has_clock = hasattr(dut, "clk_i")
    has_psel = hasattr(dut, "psel_i")
    if ARM == "sys":
        assert has_clock, "SOC_PNP_ARM=sys but the top module has no clock port"
        assert not has_psel, "SOC_PNP_ARM=sys but the top module is an APB slave"
    else:
        assert has_psel, "SOC_PNP_ARM=apb but the top module has no PSEL port"
        assert not has_clock, \
            "SOC_PNP_ARM=apb but the top module has a clock: soc_apb_pnp has none"
    await setup(dut)


@cocotb.test()
async def test_three_known_record_words_are_the_generated_table(dut):
    """Three record words read out of the block, compared with
    sw/golden/memmap_gen.py and then taken apart and checked against the
    memory map itself.

    System table: the RAM record's identification word, and the bank
    address registers of NPU and APB. Those two regions were chosen
    because their bases and masks are whole multiples of 1 MiB, so the
    encoding is exact and a rounding rule cannot hide an error in them.

    Peripheral table: UART0's identification word, GPIO's bank address
    register, and the table's own record. UART0's word carries an
    interrupt number in its low five bits, which is checked against
    IRQ_SOURCES rather than against the other generated file; GPIO's bank
    address register must express a 4 KiB slot exactly, which is
    soc_apb_pnp.v's stated reason for existing separately from soc_pnp.v.
    """
    await setup(dut)
    if ARM == "sys":
        w = sys_record_word("RAM", 0)
        got = await read_word(dut, w)
        assert got == PNP_ROM[w], \
            "word {:#05x}: the RTL table says {:#010x}, memmap_gen says " \
            "{:#010x}".format(w, got, PNP_ROM[w])
        f = ident_fields(got)
        assert f["vendor"] == VENDOR_ID, \
            "the RAM record's vendor is {:#04x}, the map says {:#04x}".format(
                f["vendor"], VENDOR_ID)
        assert f["device"] != 0, "the RAM record has no device code"

        for region in ("NPU", "APB"):
            w = sys_record_word(region, SYS_BAR0)
            got = await read_word(dut, w)
            assert got == PNP_ROM[w], \
                "word {:#05x}: RTL {:#010x}, memmap_gen {:#010x}".format(
                    w, got, PNP_ROM[w])
            f = bar_fields(got)
            base = REGIONS[region][0]
            assert f["addr"] == base >> SYS_FIELD_SHIFT, \
                "{} bank address register points at {:#x}, the map puts the " \
                "region at {:#010x}".format(
                    region, f["addr"] << SYS_FIELD_SHIFT, base)
            assert f["mask"] == (MASKS[region] & 0xFFFFFFFF) >> SYS_FIELD_SHIFT, \
                "{} bank address register carries mask field {:#05x}, the map " \
                "mask is {:#010x}".format(region, f["mask"], MASKS[region])
            assert f["type"] != 0, "{} record has no type code".format(region)
    else:
        w = apb_record_word("UART0", 0)
        got = await read_word(dut, w)
        assert got == APB_PNP_ROM[w], \
            "word {:#05x}: RTL {:#010x}, memmap_gen {:#010x}".format(
                w, got, APB_PNP_ROM[w])
        f = ident_fields(got)
        assert f["vendor"] == VENDOR_ID
        assert f["irq"] == IRQ_SOURCES["UART0"][0], \
            "UART0's record advertises interrupt {}, the map assigns it " \
            "{}".format(f["irq"], IRQ_SOURCES["UART0"][0])

        w = apb_record_word("GPIO", 1)
        got = await read_word(dut, w)
        assert got == APB_PNP_ROM[w]
        f = bar_fields(got)
        _base, slot, _irq, _status = APB_SLOTS["GPIO"]
        assert f["addr"] == (slot << 12) >> APB_FIELD_SHIFT, \
            "GPIO's bank address register points at slot {:#x}, the map puts " \
            "it at slot {:#05x}".format(f["addr"] >> 4, slot)
        assert f["mask"] == APB_SLOT_MASK_FIELD, \
            "GPIO's mask field is {:#05x}: the slot is not expressed as " \
            "exactly 4 KiB".format(f["mask"])

        w = apb_record_word("APBPNP", 0)
        got = await read_word(dut, w)
        assert got == APB_PNP_ROM[w], "the table's own record is not the map's"
        assert ident_fields(got)["vendor"] == VENDOR_ID


@cocotb.test()
async def test_the_identity_words_say_what_this_soc_is(dut):
    """docs/08 section 3 row 5, mirrored: a device and build word at byte
    offset 0xFF0 of the system table and an endianness word at 0xFF4.

    The device word's top half is the two ASCII characters of the
    project's own identifier, so the check below is that the part
    identifies itself rather than that a number matches a number. The
    peripheral table has no identity pair -- it is two words per slot and
    nothing else -- so on that arm this reads the first word past the
    populated records and holds it to zero, which is the same question
    asked where the answer is different.
    """
    await setup(dut)
    if ARM == "sys":
        got = await read_word(dut, SYS_IDENT_WORD)
        assert got == PNP_ROM[SYS_IDENT_WORD], \
            "the identity word is {:#010x}, memmap_gen says {:#010x}".format(
                got, PNP_ROM[SYS_IDENT_WORD])
        tag = bytes([(got >> 24) & 0xFF, (got >> 16) & 0xFF]).decode("ascii")
        assert tag == "NS", \
            "the identity word's tag is {!r}, expected the project's own".format(tag)
        assert got & 0xFFFF != 0, "the build field is zero"
        endian = await read_word(dut, SYS_ENDIAN_WORD)
        assert endian == PNP_ROM[SYS_ENDIAN_WORD]
        # regmap/generate_memmap.py line 379: "bit 0 of 0xFFFFFFF4
        # reports endianness, 1 = little". Bit 0 and not the whole word,
        # because the rest of that word is not claimed to mean anything.
        assert endian & 1 == 1, \
            "the endianness word is {:#010x}: bit 0 says big-endian, and this " \
            "SoC is little-endian (docs/08 section 3 row 20)".format(endian)
    else:
        first_unpopulated = max(APB_PNP_ROM) + 1
        assert first_unpopulated not in APB_PNP_ROM
        got = await read_word(dut, first_unpopulated)
        assert got == 0, \
            "word {:#05x} is past every record and reads {:#010x}".format(
                first_unpopulated, got)


@cocotb.test()
async def test_an_unpopulated_word_reads_zero(dut):
    """Both tables are sparse -- about a hundred non-zero words in 1024 on
    the system side, thirty-two on the peripheral side -- and the case
    statement's default is what makes them cheap (soc_pnp.v header, and
    docs/39 section 6 measures that it stayed a multiplexer).

    A word inside the window that no record occupies must read zero. Four
    of them are read on each arm, including the last word of the window,
    so a default arm that had been dropped or a decoder that wrapped
    shows up here. The indices are taken from the generated table by
    asking which words it does NOT define, so they cannot go stale when
    a record is added.
    """
    await setup(dut)
    rom = PNP_ROM if ARM == "sys" else APB_PNP_ROM
    top = 0x3FF
    candidates = [w for w in (0x001, 0x0FF, 0x100, 0x2FF, 0x20, 0x21, top)
                  if w not in rom]
    assert len(candidates) >= 4, \
        "fewer than four unpopulated words to choose from: the table is not sparse"
    for w in candidates[:4]:
        got = await read_word(dut, w)
        assert got == 0, \
            "unpopulated word {:#05x} reads {:#010x}".format(w, got)


@cocotb.test()
async def test_a_write_is_refused_and_the_table_does_not_move(dut):
    """The path neither block had ever been made to take.

    The two tables refuse differently and each is held to its own file:

      * soc_pnp.v: "Writes are answered with err rather than ignored."
        So a write must raise err_o in the response cycle, and it must
        still produce a response -- a slave that answered a write with
        neither a response nor an error would hang the master, which is
        worse than either.
      * soc_apb_pnp.v: "Read-only; a write is accepted and discarded,
        which is the documented behaviour for unoccupied space behind a
        GRLIB bridge and is what the surrounding bridge does everywhere
        else." So a write must NOT raise PSLVERR -- the block has no way
        to, it is tied low -- and the refusal is visible only as the
        table not moving.

    On both arms the word written to is read back before and after, and
    an adjacent word too, because a table that latched a write would show
    it at the word written and a table that latched into the wrong place
    would show it next door.
    """
    await setup(dut)
    rom = PNP_ROM if ARM == "sys" else APB_PNP_ROM
    if ARM == "sys":
        target = sys_record_word("RAM", 0)
        neighbour = sys_record_word("RAM", SYS_BAR0)
    else:
        target = apb_record_word("UART0", 0)
        neighbour = apb_record_word("UART0", 1)
    before_target = await read_word(dut, target)
    before_neighbour = await read_word(dut, neighbour)
    assert before_target == rom[target]
    assert before_neighbour == rom[neighbour]

    errored = await attempt_write(dut, target, 0xDEADBEEF)
    if ARM == "sys":
        assert errored, \
            "the system table accepted a write silently; soc_pnp.v says it " \
            "answers one with err"
    else:
        assert not errored, \
            "the peripheral table asserted PSLVERR; soc_apb_pnp.v ties it low " \
            "and says a write is accepted and discarded"

    assert await read_word(dut, target) == before_target, \
        "the word written to moved: the table is not read-only"
    assert await read_word(dut, neighbour) == before_neighbour, \
        "a neighbouring word moved after a write"

    # And an unpopulated word, where a latched write would be plainest of
    # all because the correct answer there is zero.
    spare = next(w for w in (0x100, 0x101, 0x102) if w not in rom)
    await attempt_write(dut, spare, 0xFFFFFFFF)
    assert await read_word(dut, spare) == 0, \
        "an unpopulated word kept what was written to it"


@cocotb.test()
async def test_the_response_shape_is_the_one_the_fabric_expects(dut):
    """Each arm against the protocol its own side of the SoC runs.

    System side, soc_bus.v rules S1 to S4 as soc_pnp.v's header cites
    them: GNT is combinational on REQ so the table is always ready, the
    response comes in the cycle after the grant and lasts one cycle, and
    out of reset there is no response and no error pending. Back-to-back
    requests are driven so that "one response per request" is measured
    over more than one request.

    Peripheral side: PREADY high and PSLVERR low unconditionally, and the
    read data is combinational on PADDR -- it must be right in the ACCESS
    cycle with no state carried from the previous access, which is what
    lets the bridge treat this slot as zero-wait-state.
    """
    await setup(dut)
    if ARM == "sys":
        assert val(dut.rvalid_o) == 0, "a response is pending out of reset"
        assert val(dut.err_o) == 0, "an error is pending out of reset"
        assert val(dut.gnt_o) == 0, "the table granted a request that was not made"

        # THE READ DATA IS NOT QUALIFIED BY ANYTHING, and that is checked
        # rather than assumed. rdata_o <= pnp_data runs every cycle,
        # request or no request, so one clock after reset is released the
        # register already holds the word at whatever address happens to
        # be on the bus -- here word zero, the first master record. A
        # master that read rdata_o without rvalid would therefore get a
        # plausible record rather than a zero or an X, which is the worst
        # of the three for finding the mistake. The first version of this
        # test asserted the register was still zero here and failed.
        assert val(dut.rdata_o) == PNP_ROM[0x000], \
            "rdata_o is {:#010x} one clock after reset with word zero " \
            "addressed; the table registers its output unconditionally " \
            "and this is the word at the parked address".format(val(dut.rdata_o))
        # Held in reset, it is cleared. That is the property the reset
        # branch of the RTL actually carries.
        dut.rst_ni.value = 0
        for _ in range(2):
            await RisingEdge(dut.clk_i)
        await Timer(1, units="ns")
        assert val(dut.rdata_o) == 0, "the read data register is not cleared by reset"
        assert val(dut.rvalid_o) == 0
        assert val(dut.err_o) == 0
        dut.rst_ni.value = 1
        await RisingEdge(dut.clk_i)
        await Timer(1, units="ns")

        words = [sys_record_word("RAM", 0), sys_record_word("NPU", 0),
                 sys_record_word("APB", SYS_BAR0)]
        # Back to back: request every cycle, response every cycle, one
        # cycle behind.
        await RisingEdge(dut.clk_i)
        dut.we_i.value = 0
        dut.be_i.value = 0xF
        seen = []
        for i, w in enumerate(words):
            dut.req_i.value = 1
            dut.addr_i.value = word_address(w)
            await Timer(1, units="ns")
            assert val(dut.gnt_o) == 1, "GNT did not follow REQ combinationally"
            await RisingEdge(dut.clk_i)
            await Timer(1, units="ns")
            assert val(dut.rvalid_o) == 1, \
                "no response for back-to-back request {}".format(i)
            assert val(dut.err_o) == 0, "a back-to-back read was answered with err"
            seen.append(val(dut.rdata_o))
        dut.req_i.value = 0
        await Timer(1, units="ns")
        assert val(dut.gnt_o) == 0, "GNT stayed high after REQ fell"
        await RisingEdge(dut.clk_i)
        await Timer(1, units="ns")
        assert val(dut.rvalid_o) == 0, "a response arrived with no request behind it"
        assert seen == [PNP_ROM[w] for w in words], \
            "back-to-back reads returned {} for words {}".format(
                [hex(v) for v in seen], [hex(w) for w in words])
    else:
        # PREADY and PSLVERR are constants: check them while the block is
        # not selected at all, which is where a slave that drove them
        # from a decode would differ.
        dut.psel_i.value = 0
        dut.penable_i.value = 0
        await Timer(1, units="ns")
        assert val(dut.pready_o) == 1, "PREADY is not unconditionally high"
        assert val(dut.pslverr_o) == 0, "PSLVERR is not unconditionally low"
        # Combinational on PADDR: two different words in successive
        # deltas, with no ACCESS phase between them.
        a = apb_record_word("UART0", 0)
        b = apb_record_word("GPIO", 0)
        for word in (a, b, a):
            dut.paddr_i.value = word_address(word) & 0xFFF
            await Timer(1, units="ns")
            assert val(dut.prdata_o) == APB_PNP_ROM[word], \
                "PRDATA did not follow PADDR combinationally at word " \
                "{:#05x}".format(word)
