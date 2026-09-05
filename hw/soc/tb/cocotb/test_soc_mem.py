"""soc_mem suite: the memory as a FABRIC SLAVE, at both response latencies.

Every expectation here comes from one of two specifications and not from
the RTL:

  * the slave contract S1-S4 in the header of hw/soc/rtl/soc_bus.v, which
    is itself Ibex's load/store-unit protocol (rules 1-4) restated from
    the slave side: always answer a granted request exactly once, carry
    rdata and err in that cycle, never answer in the grant cycle, never
    reorder, never limit the master;

  * hw/soc/rtl/soc_mem.v's own header, which states what RDREG is and
    what it does NOT change -- gnt stays combinational from req, so the
    memory still accepts a request every cycle, and the extra cycle is
    LATENCY and not throughput. It also states that the write response is
    delayed with the read response, because rule 4 makes the latency a
    property of the slave rather than of the access.

WHY THIS SUITE IS NEW. Before docs/50 this module was one always block
and the whole-SoC run was proportionate verification of it. docs/50 gives
it a second response stage, and a slave with two arms and a parameter
that selects between them is a protocol obligation that has to be checked
directly: the system-level run only exercises the memory through Ibex, so
a defect Ibex does not happen to provoke would not appear there.

THE SAME TESTS RUN AT BOTH RDREG VALUES. Not one set for each: the
protocol is identical at both, only the latency differs, and the whole
point is that nothing except the latency moved. `LATENCY` below is
MEASURED from the DUT in test_the_latency_is_the_one_that_was_built and
every later test uses the measured value, so a build whose parameter
override was dropped fails the first test instead of quietly passing the
other arm's suite.

WHAT THIS SUITE DOES NOT COVER
------------------------------
  * hw/soc/rtl/soc_mem_sram.v. That file declares the same module name and
    the same protocol, and cannot be simulated without the PDK's macro
    models. What is checked of it here is nothing; what is checked of it
    at all is the synthesis parameter guard in
    sw/tests/test_soc_memory_guards.py and the netlist docs/50 hardens.
  * The behaviour of two masters, arbitration, or anything above this
    port. That is soc_bus's suite.
  * Timing, X-propagation and reset in the middle of an outstanding
    request. The last is a real gap and it is the same gap
    test_soc_bus.py declares.
  * INIT_FILE. The suite runs with an empty image and writes what it
    reads back.
"""

import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

CLK_NS = 10
T_DRIVE = 1    # stimulus applied here
T_SAMPLE = 8   # outputs sampled here, settled

# What the build was ASKED for. The suite does not trust it: the first
# test measures the latency the design actually has and compares.
RDREG_REQUESTED = int(os.environ.get("SOC_MEM_RDREG", "0"))
WORDS = int(os.environ.get("SOC_MEM_WORDS", "64"))
# docs/67's configurations. RO builds have no bus writes, so the three
# protocol tests that write skip there; the ROM's rows are loaded by the
# deposit helper below, as the flight part's loader would load them.
HARDEN = int(os.environ.get("SOC_MEM_HARDEN", "1"))
RO = int(os.environ.get("SOC_MEM_RO", "0"))
ECC_BYTE = int(os.environ.get("SOC_MEM_ECC_BYTE", "1"))

# soc_mem.v's header: RDREG = 0 answers one cycle after the grant, RDREG =
# 1 answers two cycles after it.
EXPECTED_LATENCY = 2 if RDREG_REQUESTED else 1

# Filled in by the first test and used by every later one.
LATENCY = None


def val(sig):
    s = str(sig.value)
    if any(c not in "01" for c in s):
        raise AssertionError("non-binary value {!r} on {}".format(s, sig._path))
    return int(s, 2)


async def start(dut):
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    dut.req_i.value = 0
    dut.addr_i.value = 0
    dut.we_i.value = 0
    dut.be_i.value = 0
    dut.wdata_i.value = 0
    dut.rst_ni.value = 0
    for _ in range(3):
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.rst_ni.value = 1
    await RisingEdge(dut.clk_i)


def drive(dut, req, addr=0, we=0, be=0xF, wdata=0):
    dut.req_i.value = req
    dut.addr_i.value = addr
    dut.we_i.value = we
    dut.be_i.value = be
    dut.wdata_i.value = wdata


class Monitor:
    """Watches the port and enforces S1 rule 3 every cycle.

    THE SAMPLING PHASE IS THE WHOLE SUBTLETY AND IT IS STATED HERE RATHER
    THAN DISCOVERED TWICE. At T_SAMPLE after a clock edge, `rvalid_o` is
    the OUTPUT of the edge that has just passed, while `req_i` and
    `gnt_o` are the stimulus that the NEXT edge will consume. The two are
    one edge apart, so a grant seen in monitor cycle c is answered no
    earlier than monitor cycle c + 1, and the response counted in a cycle
    must be covered by grants counted STRICTLY BEFORE it. That is the
    order the loop below counts them in, and it is what makes "never a
    response in the grant cycle" -- rule 3's second sentence -- an
    ordinary consequence of `rvalids <= grants` rather than a separate
    check with its own off-by-one.

    Checked continuously, at every latency:
      * no response without an earlier granted request to answer;
      * the running response count never overtakes the running grant
        count, which is one response per grant and no duplicates.
    The per-response payload is checked by the caller against the value it
    wrote, because only the caller knows it.
    """

    def __init__(self, dut):
        self.dut = dut
        self.grants = 0
        self.rvalids = 0
        self.responses = []           # (rdata, err) in arrival order
        self.grant_cycles = []
        self.rvalid_cycles = []
        self.cycle = 0
        self.max_outstanding = 0

    async def run(self):
        # THE SAMPLE COMES FIRST AND THE EDGE SECOND. This coroutine is
        # started immediately after an edge, and the request it has to
        # see is the one driven T_DRIVE into THIS cycle and consumed by
        # the NEXT edge. A loop that waited for an edge first would miss
        # the first grant of every test and then report its response as
        # unsolicited -- which is what the first version of this file did.
        while True:
            await Timer(T_SAMPLE, unit="ns")
            self.cycle += 1
            if val(self.dut.rvalid_o):
                self.rvalids += 1
                self.responses.append((val(self.dut.rdata_o),
                                       val(self.dut.err_o)))
                self.rvalid_cycles.append(self.cycle)
                assert self.rvalids <= self.grants, (
                    "response number {} with only {} grants strictly before "
                    "it: either a response for a request that was never "
                    "made, a duplicate, or a response in its own grant "
                    "cycle".format(self.rvalids, self.grants))
            if val(self.dut.req_i) and val(self.dut.gnt_o):
                self.grants += 1
                self.grant_cycles.append(self.cycle)
            self.max_outstanding = max(self.max_outstanding,
                                       self.grants - self.rvalids)
            await RisingEdge(self.dut.clk_i)


@cocotb.test()
async def test_the_latency_is_the_one_that_was_built(dut):
    """The guard, and it runs first on purpose.

    A parameter override that is silently discarded is docs/41 section
    6.6's shape and docs/49 section 8.1 found an instance of it in this
    very simulator. The repair there was to read the compiled object; the
    repair here is cheaper and stronger, because this suite can simply
    MEASURE the property the parameter controls. One request, count the
    cycles to its answer, compare with what the Makefile said it built.
    """
    global LATENCY
    mon = Monitor(dut)
    await start(dut)
    cocotb.start_soon(mon.run())

    await Timer(T_DRIVE, unit="ns")
    drive(dut, 1, addr=0)
    await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    drive(dut, 0)
    for _ in range(8):
        await RisingEdge(dut.clk_i)

    assert len(mon.grant_cycles) == 1, "expected one grant, saw {}".format(
        len(mon.grant_cycles))
    assert len(mon.rvalid_cycles) == 1, (
        "expected one response within 8 cycles of a grant, saw {}".format(
            len(mon.rvalid_cycles)))
    LATENCY = mon.rvalid_cycles[0] - mon.grant_cycles[0]
    assert LATENCY == EXPECTED_LATENCY, (
        "the build answers {} cycle(s) after the grant, but RDREG={} was "
        "requested, which is {} cycle(s). The parameter override did not "
        "take.".format(LATENCY, RDREG_REQUESTED, EXPECTED_LATENCY))
    dut._log.info("measured response latency %d cycle(s), RDREG=%d",
                  LATENCY, RDREG_REQUESTED)


@cocotb.test()
async def test_gnt_is_combinational_and_never_withheld(dut):
    """soc_mem.v's header: RDREG changes the LATENCY and not the
    throughput. gnt_o follows req_i combinationally in both arms, so a
    master may be granted on every cycle including the cycles in which
    earlier responses are still in flight. A memory that throttled to
    protect its own pipeline would show here."""
    await start(dut)
    for _ in range(12):
        await Timer(T_DRIVE, unit="ns")
        drive(dut, 1, addr=0)
        await Timer(T_SAMPLE - T_DRIVE, unit="ns")
        assert val(dut.gnt_o) == 1, "gnt withheld from a request"
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    drive(dut, 0)
    await Timer(T_SAMPLE - T_DRIVE, unit="ns")
    assert val(dut.gnt_o) == 0, "gnt asserted without a request"


@cocotb.test(skip=bool(RO))
async def test_exactly_one_response_per_grant_back_to_back(dut):
    """S1 rule 3 and S3, on the traffic pattern the extra stage is about:
    a request every cycle, so at RDREG = 1 two are always in flight.

    The tags are the written words, so a response that is duplicated,
    dropped or reordered is visible in the payload as well as in the
    count."""
    mon = Monitor(dut)
    await start(dut)
    cocotb.start_soon(mon.run())

    n = 16
    words = [(0x5A000000 | (i * 0x10001)) & 0xFFFFFFFF for i in range(n)]

    # Fill, one write per cycle.
    for i, w in enumerate(words):
        await Timer(T_DRIVE, unit="ns")
        drive(dut, 1, addr=4 * i, we=1, wdata=w)
        await RisingEdge(dut.clk_i)
    # Read back, one read per cycle, immediately after.
    for i in range(n):
        await Timer(T_DRIVE, unit="ns")
        drive(dut, 1, addr=4 * i)
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    drive(dut, 0)
    for _ in range(8):
        await RisingEdge(dut.clk_i)

    assert mon.grants == 2 * n, "expected {} grants, saw {}".format(
        2 * n, mon.grants)
    assert mon.rvalids == mon.grants, (
        "{} responses for {} grants".format(mon.rvalids, mon.grants))

    # The reads are the second half of the response stream and must carry
    # the words the first half wrote, in order.
    got = [r[0] for r in mon.responses[n:]]
    assert got == words, (
        "read-back mismatch at RDREG={}: first difference at index {}".format(
            RDREG_REQUESTED,
            next((i for i, (a, b) in enumerate(zip(got, words)) if a != b),
                 len(got))))

    # Vacuity guard. At two cycles of latency a request every cycle MUST
    # produce two outstanding; at one cycle it must not exceed one. This
    # is the assertion that the extra stage is a pipeline and not a stall.
    assert mon.max_outstanding == LATENCY, (
        "peak outstanding was {} at a measured latency of {}: the memory "
        "is not pipelining".format(mon.max_outstanding, LATENCY))


@cocotb.test()
async def test_every_response_is_exactly_latency_cycles_after_its_grant(dut):
    """S1 rule 3 says one response per grant and rule 4 says in order, so
    with a fixed-latency slave the k-th response must land exactly LATENCY
    cycles after the k-th grant -- for EVERY k, not on average. A memory
    that dropped one and duplicated another would keep the totals and fail
    here."""
    rng = random.Random(3)
    mon = Monitor(dut)
    await start(dut)
    cocotb.start_soon(mon.run())

    for _ in range(60):
        await Timer(T_DRIVE, unit="ns")
        if rng.randrange(3):
            drive(dut, 1, addr=4 * rng.randrange(WORDS),
                  we=rng.randrange(2), be=0xF, wdata=rng.randrange(1 << 32))
        else:
            drive(dut, 0)
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    drive(dut, 0)
    for _ in range(8):
        await RisingEdge(dut.clk_i)

    assert mon.grants > 20, "too little traffic to conclude anything"
    assert len(mon.rvalid_cycles) == len(mon.grant_cycles)
    for k, (g, r) in enumerate(zip(mon.grant_cycles, mon.rvalid_cycles)):
        assert r - g == LATENCY, (
            "response {} came {} cycles after its grant, not {}".format(
                k, r - g, LATENCY))


@cocotb.test()
async def test_a_write_is_answered_like_a_read(dut):
    """soc_mem.v's header, and it is a protocol requirement rather than a
    convenience: rule 3 gives every granted request exactly one rvalid and
    rule 4 requires them in order, so a memory that answered writes faster
    than reads would reorder its own responses the first time a store
    followed a load. The interleaved stream below is exactly that case,
    and the previous test's per-response cycle check is what would catch
    it -- this one states it as its own property so the reason is
    recorded."""
    mon = Monitor(dut)
    await start(dut)
    cocotb.start_soon(mon.run())

    ops = [(0, 0x40), (1, 0x44), (0, 0x48), (1, 0x4C), (1, 0x50), (0, 0x54)]
    for we, addr in ops:
        await Timer(T_DRIVE, unit="ns")
        drive(dut, 1, addr=addr, we=we, wdata=0xDEADBE00 | addr)
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    drive(dut, 0)
    for _ in range(8):
        await RisingEdge(dut.clk_i)

    assert mon.rvalids == len(ops)
    for k, (g, r) in enumerate(zip(mon.grant_cycles, mon.rvalid_cycles)):
        assert r - g == LATENCY, (
            "response {} ({}) came {} cycles after its grant, not {}: the "
            "latency depends on the ACCESS and not on the slave".format(
                k, "write" if ops[k][0] else "read", r - g, LATENCY))


@cocotb.test(skip=bool(RO))
async def test_byte_enables(dut):
    """Sub-word writes, because Ibex emits sb and sh and the response
    stage must not change which bytes land. Unrelated to RDREG and run at
    both values for exactly that reason."""
    mon = Monitor(dut)
    await start(dut)
    cocotb.start_soon(mon.run())

    async def access(**kw):
        await Timer(T_DRIVE, unit="ns")
        drive(dut, 1, **kw)
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
        drive(dut, 0)
        for _ in range(LATENCY + 1):
            await RisingEdge(dut.clk_i)

    await access(addr=0x20, we=1, be=0xF, wdata=0x00000000)
    await access(addr=0x20, we=1, be=0x2, wdata=0xFFFFFFFF)
    await access(addr=0x20)
    assert mon.responses[-1][0] == 0x0000FF00, (
        "be=0x2 wrote {:#010x}".format(mon.responses[-1][0]))

    await access(addr=0x20, we=1, be=0x9, wdata=0x11223344)
    await access(addr=0x20)
    assert mon.responses[-1][0] == 0x1100FF44, (
        "be=0x9 wrote {:#010x}".format(mon.responses[-1][0]))


@cocotb.test()
async def test_read_only_answers_a_write_with_err(dut):
    """RO is the boot ROM. soc_mem.v: a write is not performed and IS
    answered, with err, so a stray store takes a store access fault rather
    than a silent no-op. err must arrive in the response cycle -- rule 3 --
    which at RDREG = 1 means it has to be carried through the extra stage
    alongside rdata. That is the part of this test that is new.

    RO is a parameter of the instance and this suite builds one DUT, so
    the RO behaviour is checked here through the err path of a
    read-write memory: err is 0 for every access, in the right cycle,
    which is the same wire and the same stage. The RO=1 case is checked at
    the system level, where soc_top.v instantiates it."""
    mon = Monitor(dut)
    await start(dut)
    cocotb.start_soon(mon.run())

    for we in (0, 1, 1, 0):
        await Timer(T_DRIVE, unit="ns")
        drive(dut, 1, addr=0x30, we=we, wdata=0x12345678)
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    drive(dut, 0)
    for _ in range(8):
        await RisingEdge(dut.clk_i)

    assert mon.rvalids == 4
    if RO:
        # The ROM build, since docs/67: the two writes are refused with
        # err, in their response cycle, and the two reads are not.
        assert [e for _, e in mon.responses] == [0, 1, 1, 0], (
            "a read-only memory did not answer exactly its writes with err")
    else:
        assert all(e == 0 for _, e in mon.responses), (
            "a read-write memory reported err on a legal access")


# =====================================================================
# docs/67: the codec and the scrubber
# =====================================================================
#
# Everything below skips at HARDEN = 0, where there is nothing to test,
# and adapts to the code shape: four (16,8) byte codewords per row on
# the RAM (SOC_MEM_ECC_BYTE = 1) or one (39,32) word codeword on the
# ROM (SOC_MEM_ECC_BYTE = 0, SOC_MEM_RO = 1).
#
# THE EXPECTED CHECK BITS COME FROM sw/golden/secded.py, never from the
# DUT: a suite that read the encoder's output back and called it right
# would be comparing the design against itself. That is the same
# cross-check hw/tb/test_secded.py makes on the codec and
# test_soc_clint.py makes on the CLINT's codeword.
#
# THE STIMULUS reaches into the hierarchy -- `mem[i]` and `g_ecc.chk[i]`
# are the stored row, and an upset is an XOR into one of them -- and
# EVERY OBSERVATION is one a bench could make: the response, err_o, and
# the three report lines. The two peeks in the port-contention test are
# named where they happen and are bench observations of state, not
# oracles.

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "sw"))
from golden import secded  # noqa: E402

CW = 32 if ECC_BYTE else 7          # check bits per row
ROW_BITS = 32 + CW


def golden_chk(word):
    """The check field of one row, from the golden model."""
    if ECC_BYTE:
        c = 0
        for lane in range(4):
            c |= secded.check_bits((word >> (8 * lane)) & 0xFF) << (8 * lane)
        return c
    return secded.check_bits(word) & 0x7F


def lane_of(bit):
    """Which codeword a row bit belongs to. Data bit b of lane l is
    row bit 8l+b, its check bit c is row bit 32+8l+c (ECC_BYTE); the
    word code is one codeword."""
    if not ECC_BYTE:
        return 0
    return ((bit - 32) // 8) if bit >= 32 else (bit // 8)


class Reports:
    """Counts the three report lines and err_o, cycle by cycle, at the
    settled sampling point. rd/sec/ded are per-cycle pulses at the
    source, so a count is a count of events."""

    def __init__(self, dut):
        self.dut = dut
        self.sec = 0
        self.rd = 0
        self.ded = 0
        self.err = 0
        self.ded_addr = []
        self.sec_at = []          # (time, scrub pointer) of every sec_o
        self.rv = 0

    async def run(self):
        while True:
            await Timer(T_SAMPLE, unit="ns")
            d = self.dut
            if val(d.sec_o):
                self.sec += 1
                self.sec_at.append((cocotb.utils.get_sim_time("ns"),
                                    val(d.g_ecc.u_ecc.g_scrub.sptr)))
            if val(d.rd_o):
                self.rd += 1
            if val(d.ded_o):
                self.ded += 1
                self.ded_addr.append(val(d.evt_addr_o))
            if val(d.rvalid_o):
                self.rv += 1
                if val(d.err_o):
                    self.err += 1
            await RisingEdge(d.clk_i)


async def start_h(dut, scrub_en=0, ivl=0):
    await start(dut)
    dut.scrub_en_i.value = scrub_en
    dut.scrub_ivl_i.value = ivl
    rep = Reports(dut)
    cocotb.start_soon(rep.run())
    return rep


async def xact(dut, addr, we=0, be=0xF, wdata=0):
    """One access, and its response: (rdata, err)."""
    await Timer(T_DRIVE, unit="ns")
    drive(dut, 1, addr=addr, we=we, be=be, wdata=wdata)
    await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    drive(dut, 0)
    for _ in range(8):
        await Timer(T_SAMPLE - T_DRIVE, unit="ns")
        if val(dut.rvalid_o):
            r = (val(dut.rdata_o), val(dut.err_o))
            await RisingEdge(dut.clk_i)
            return r
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
    raise AssertionError("no response within 8 cycles")


async def idle(dut, n):
    for _ in range(n):
        await RisingEdge(dut.clk_i)


def stored(dut, i):
    return val(dut.mem[i]), val(dut.g_ecc.chk[i])


def deposit_row(dut, i, word):
    """The loader a ROM has to have: write a word AND its check field
    straight into the storage, as whatever loads the macro must. Used
    for the RO build, where the bus cannot write, and nowhere else."""
    dut.mem[i].value = word
    dut.g_ecc.chk[i].value = golden_chk(word)


async def fill(dut, words):
    """Put `words` into rows 0..n-1 through the bus, or through the
    loader on a read-only build."""
    for i, w in enumerate(words):
        if RO:
            deposit_row(dut, i, w)
        else:
            await xact(dut, 4 * i, we=1, wdata=w)
    await idle(dut, 2)


async def upset(dut, i, bit):
    """XOR one bit of row i: data bits 0..31, check bits 32..

    Async, and it waits a nanosecond after the deposit, because a cocotb
    deposit is applied at the next scheduling point and not when the
    assignment runs: two of these in a row at the same simulation time
    read the same stale value and compose into a DOUBLE flip. The first
    version of this file did exactly that on the undo-then-flip between
    two bits and reported a bus error on a single upset."""
    if bit < 32:
        dut.mem[i].value = val(dut.mem[i]) ^ (1 << bit)
    else:
        dut.g_ecc.chk[i].value = val(dut.g_ecc.chk[i]) ^ (1 << (bit - 32))
    await Timer(1, unit="ns")


def pattern(i):
    return (0x9E3779B1 * (i + 1) + 0x5A5A0000) & 0xFFFFFFFF


hardened = cocotb.test(skip=(HARDEN == 0))


@hardened
async def test_the_stored_rows_are_codewords_of_the_golden_model(dut):
    """Every row written through the bus -- whole words and every byte
    lane pattern -- carries the check field sw/golden/secded.py says it
    should. For the byte code that is four lanes encoded on their own;
    for the word code, seven bits of the (40,32) shortening. A row that
    passed this and every read below would still be wrong if the
    encoder and the golden model had drifted together, which is what
    hw/tb/test_secded.py and formal/secded.sby stand between."""
    await start_h(dut)
    n = min(WORDS, 24)
    words = [pattern(i) for i in range(n)]
    await fill(dut, words)
    if not RO:
        # Byte lanes, one at a time, on top of what is there.
        for i in range(n):
            be = 1 << (i % 4)
            await xact(dut, 4 * i, we=1, be=be, wdata=~words[i] & 0xFFFFFFFF)
            m = 0xFF << (8 * (i % 4))
            words[i] = (words[i] & ~m) | (~words[i] & m)
        await idle(dut, 2)
    for i in range(n):
        d, c = stored(dut, i)
        assert d == words[i], "row {} holds {:08x}, wrote {:08x}".format(
            i, d, words[i])
        assert c == golden_chk(words[i]), (
            "row {} check field {:0{w}x} against golden {:0{w}x}".format(
                i, c, golden_chk(words[i]), w=CW // 4 + 1))


@hardened
async def test_a_single_upset_in_any_stored_bit_is_corrected_on_read(dut):
    """EVERY bit of the row -- all 32 data and all CW check bits -- on
    several rows, with the scrubber held off so that correction on read
    is the only mechanism in play: the read returns the written word,
    err_o is low, rd_o pulses exactly once per corrected read, and the
    row itself is STILL corrupt afterwards, which is what the scrubber
    exists for."""
    rep = await start_h(dut, scrub_en=0)
    rows = [0, 1, 5, min(WORDS, 64) - 1]
    words = [pattern(i) for i in range(min(WORDS, 64))]
    await fill(dut, words)
    n_reads = 0
    for i in rows:
        for bit in range(ROW_BITS):
            await upset(dut, i, bit)
            before = rep.rd
            data, err = await xact(dut, 4 * i)
            n_reads += 1
            assert err == 0, "row {} bit {}: err on a single upset".format(i, bit)
            assert data == words[i], (
                "row {} bit {}: read {:08x}, wrote {:08x}".format(
                    i, bit, data, words[i]))
            assert rep.rd == before + 1, (
                "row {} bit {}: rd_o pulsed {} times, not once".format(
                    i, bit, rep.rd - before))
            # still corrupt in the storage: correct-on-read repairs the
            # value on the way out and nothing else
            d, c = stored(dut, i)
            assert (d != words[i]) or (c != golden_chk(words[i]))
            await upset(dut, i, bit)    # undo, for the next bit
    assert rep.sec == 0 and rep.ded == 0 and rep.err == 0
    assert rep.rd == n_reads


@hardened
async def test_a_double_upset_is_detected_and_answers_with_a_bus_error(dut):
    """Two bits in ONE codeword: the read carries err_o, ded_o pulses
    with the row's offset, nothing is corrected and the data is not
    silently 'repaired' into a third value. Then, on the byte code, two
    bits in TWO codewords of the same row: each lane corrects its own
    and the read is clean -- the independence the per-lane code buys
    and a word code would not."""
    rep = await start_h(dut, scrub_en=0)
    words = [pattern(i) for i in range(min(WORDS, 16))]
    await fill(dut, words)
    rng = random.Random(67)
    pairs = 0
    for i in range(min(WORDS, 16)):
        # two distinct bits of the same codeword
        lane = rng.randrange(4) if ECC_BYTE else 0
        if ECC_BYTE:
            cand = list(range(8 * lane, 8 * lane + 8)) + \
                   list(range(32 + 8 * lane, 32 + 8 * lane + 8))
        else:
            cand = list(range(ROW_BITS))
        a, b = rng.sample(cand, 2)
        await upset(dut, i, a)
        await upset(dut, i, b)
        d0, c0 = stored(dut, i)
        before = (rep.ded, rep.rd)
        data, err = await xact(dut, 4 * i)
        pairs += 1
        assert err == 1, "row {} bits {},{}: no bus error on a double".format(i, a, b)
        assert rep.ded == before[0] + 1, "ded_o did not pulse once"
        assert rep.rd == before[1], "rd_o pulsed on an uncorrectable read"
        assert rep.ded_addr[-1] == 4 * i, (
            "evt_addr_o {:#x} is not row {}'s offset".format(rep.ded_addr[-1], i))
        assert stored(dut, i) == (d0, c0), "an uncorrectable row was modified"
        await upset(dut, i, a)
        await upset(dut, i, b)
    assert rep.sec == 0
    if ECC_BYTE:
        for i in range(min(WORDS, 16)):
            la, lb = rng.sample(range(4), 2)
            a = 8 * la + rng.randrange(8)
            b = 32 + 8 * lb + rng.randrange(8)
            await upset(dut, i, a)
            await upset(dut, i, b)
            before = rep.rd
            data, err = await xact(dut, 4 * i)
            assert err == 0 and data == words[i], (
                "row {}: two lanes each with one upset were not both "
                "corrected".format(i))
            assert rep.rd == before + 1
            await upset(dut, i, a)
            await upset(dut, i, b)
    assert rep.ded == pairs


@hardened
async def test_the_scrubber_repairs_a_word_nobody_reads(dut):
    """An upset in a row the program never touches again: with the
    scrubber walking at interval 0, sec_o pulses EXACTLY ONCE, the row is
    a codeword of the written word again, and a later read of it is
    clean -- rd_o stays low, because there is nothing left to correct.
    Then the same with the interval set, to show the pacing is the
    interval and not the row count."""
    for ivl in (0, 3):
        rep = await start_h(dut, scrub_en=1, ivl=ivl)
        words = [pattern(i) for i in range(WORDS)]
        await fill(dut, words)
        rows = [2, WORDS // 2, WORDS - 1]
        for i in rows:
            await upset(dut, i, (7 * i) % ROW_BITS)
        # One full walk of the memory, plus slack: the pointer visits
        # every row once per WORDS scrub reads, and a read is one idle
        # cycle plus the interval.
        budget = 2 * WORDS * (ivl + 2) + 20
        sec0 = rep.sec
        for _ in range(budget):
            await RisingEdge(dut.clk_i)
            if rep.sec - sec0 >= len(rows):
                break
        assert rep.sec - sec0 == len(rows), (
            "ivl {}: the scrubber repaired {} rows of {} inside {} cycles".format(
                ivl, rep.sec - sec0, len(rows), budget))
        # sec_o is sampled IN the write-back cycle; the row changes at
        # the edge that ends it. Two more edges before looking.
        await idle(dut, 2)
        for i in rows:
            assert stored(dut, i) == (words[i], golden_chk(words[i])), (
                "ivl {}: row {} was not restored to its codeword: holds "
                "{:08x}/{:08x}, want {:08x}/{:08x}; sec pulses {}".format(
                    ivl, i, stored(dut, i)[0], stored(dut, i)[1], words[i],
                    golden_chk(words[i]), rep.sec_at))
        # and it counted each row once: a further walk repairs nothing
        for _ in range(WORDS * (ivl + 2) + 20):
            await RisingEdge(dut.clk_i)
        assert rep.sec - sec0 == len(rows), "sec_o pulsed again on clean rows"
        for i in rows:
            before = rep.rd
            data, err = await xact(dut, 4 * i)
            assert data == words[i] and err == 0
            assert rep.rd == before, "rd_o pulsed on a row the scrubber had repaired"
        assert rep.ded == 0 and rep.err == 0


@hardened
async def test_the_scrubber_never_writes_back_an_uncorrectable_row(dut):
    """Two upsets in one codeword, found by the scrubber: ded_o pulses
    with the row's offset, sec_o never does, the row is left EXACTLY as
    it was -- re-encoding it would turn a detected error into a valid
    codeword over a wrong value -- and the next read of it traps."""
    rep = await start_h(dut, scrub_en=1, ivl=0)
    words = [pattern(i) for i in range(WORDS)]
    await fill(dut, words)
    i = 3
    if ECC_BYTE:
        a, b = 8 * 2 + 1, 32 + 8 * 2 + 4       # lane 2, one data and one check
    else:
        a, b = 5, 32 + 2
    await upset(dut, i, a)
    await upset(dut, i, b)
    raw = stored(dut, i)
    for _ in range(2 * WORDS + 20):
        await RisingEdge(dut.clk_i)
        if rep.ded:
            break
    assert rep.ded >= 1, "the scrubber never reported the uncorrectable row"
    assert rep.ded_addr[0] == 4 * i
    assert rep.sec == 0, "sec_o pulsed: something was written back"
    assert stored(dut, i) == raw, "the uncorrectable row was modified"
    data, err = await xact(dut, 4 * i)
    assert err == 1
    # every other row is untouched and reads clean
    for j in (0, 1, WORDS - 1):
        data, err = await xact(dut, 4 * j)
        assert (data, err) == (words[j], 0)


@hardened
async def test_the_bus_always_wins_the_port(dut):
    """Two claims about the back-door port, both bench-observable.

    1. While the bus asks on every cycle the scrubber makes no progress:
       an upset sits unrepaired for as long as the traffic lasts, and
       gnt_o was high on every one of those cycles.
    2. A bus write that lands between the scrubber's read of a row and
       its write-back is NOT overwritten: the write-back is dropped.
       The moment is found by peeking at the scrubber's `srd_q` and its
       pointer -- a bench observation of state, used to TIME the
       stimulus and not to judge the result. The result is judged by
       what the row holds and what a read returns."""
    if RO:
        # A ROM has no bus writes; claim 2 has nothing to test and claim
        # 1 is covered by the RAM build of this same test.
        return
    rep = await start_h(dut, scrub_en=1, ivl=0)
    words = [pattern(i) for i in range(WORDS)]
    await fill(dut, words)
    i = 4
    await upset(dut, i, 3)
    # claim 1: 4 * WORDS back-to-back reads of OTHER rows -- every row
    # but i, cycling, so no read ever lands on the corrupt one
    for k in range(4 * WORDS):
        await Timer(T_DRIVE, unit="ns")
        drive(dut, 1, addr=4 * ((i + 1 + (k % (WORDS - 1))) % WORDS))
        await Timer(T_SAMPLE - T_DRIVE, unit="ns")
        assert val(dut.gnt_o) == 1, "gnt withheld while the scrubber had work"
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    drive(dut, 0)
    assert rep.sec == 0, (
        "the scrubber wrote back while the bus never let go: {}".format(rep.sec_at))
    assert rep.rd == 0 and rep.err == 0
    # let it go: repaired within one walk
    for _ in range(2 * WORDS + 10):
        await RisingEdge(dut.clk_i)
        if rep.sec:
            break
    await idle(dut, 2)          # the write-back lands at the next edge
    assert rep.sec == 1, "sec pulses: {}".format(rep.sec_at)
    assert stored(dut, i) == (words[i], golden_chk(words[i]))

    # claim 2: catch the cycle after the scrub read of row j and write j
    j = 9
    await upset(dut, j, 32 + 1)
    new = 0x0BAD_C0DE
    sptr = dut.g_ecc.u_ecc.g_scrub.sptr
    srd = dut.g_ecc.u_ecc.g_scrub.srd_q
    caught = False
    sec_before = rep.sec
    for _ in range(4 * WORDS + 20):
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
        if val(srd) == 1 and val(sptr) == j:
            # This is the cycle in which the write-back would happen.
            drive(dut, 1, addr=4 * j, we=1, wdata=new)
            caught = True
            await RisingEdge(dut.clk_i)
            await Timer(T_DRIVE, unit="ns")
            drive(dut, 0)
            break
    assert caught, "never observed the scrub read of row {}".format(j)
    await idle(dut, 4)
    assert stored(dut, j) == (new, golden_chk(new)), (
        "the scrub write-back overwrote a bus write: row holds {:08x}".format(
            stored(dut, j)[0]))
    assert rep.sec == sec_before, (
        "a write-back the bus pre-empted was counted as a repair: {}".format(
            rep.sec_at))
    data, err = await xact(dut, 4 * j)
    assert (data, err) == (new, 0)

    # claim 3: the pre-empting access is a READ of another row. A
    # scrubber that ignored the bus here would put its write-back onto
    # the port in the bus's cycle -- and the port would carry the bus's
    # address and the bus's mask, so the row being READ would be written
    # with whatever was on wdata. Row k must come back untouched, the
    # read must return it, and nothing may be counted.
    m = 12
    k = 20
    await upset(dut, m, 3)
    sec_before = rep.sec
    caught = False
    for _ in range(4 * WORDS + 20):
        await RisingEdge(dut.clk_i)
        await Timer(T_DRIVE, unit="ns")
        if val(srd) == 1 and val(sptr) == m:
            drive(dut, 1, addr=4 * k, we=0, wdata=0xFFFF_FFFF)
            caught = True
            caught_at = cocotb.utils.get_sim_time("ns")
            await RisingEdge(dut.clk_i)
            await Timer(T_DRIVE, unit="ns")
            drive(dut, 0)
            break
    assert caught, "never observed the scrub read of row {}".format(m)
    await idle(dut, 4)
    assert stored(dut, k) == (words[k], golden_chk(words[k])), (
        "a row the bus was reading was written while the scrubber held "
        "a result: holds {:08x}".format(stored(dut, k)[0]))
    # No repair was counted IN the pre-empted cycle -- the pointer stays
    # and the row is read again two cycles later, which is the retry
    # soc_mem_ecc.v's header describes, and that one may count.
    assert all(t != caught_at + T_SAMPLE - T_DRIVE for t, _ in rep.sec_at), (
        "a write-back the bus pre-empted was counted: pulses {} "
        "(pre-empted at {})".format(rep.sec_at, caught_at))
    # and row m is repaired on the retry
    for _ in range(2 * WORDS + 10):
        await RisingEdge(dut.clk_i)
        if rep.sec > sec_before:
            break
    await idle(dut, 2)
    assert rep.sec == sec_before + 1, rep.sec_at
    assert stored(dut, m) == (words[m], golden_chk(words[m]))


@hardened
async def test_the_interval_paces_the_scrubber(dut):
    """scrub_ivl_i is idle cycles between scrub reads: at N the row port
    is read once every max(2, N+1) idle cycles -- the row read in one
    cycle is examined in the next, so the shortest period is two and
    intervals 0 and 1 are the same rate. Counted on the row port (a
    bench observation of the array's enable) over a long idle stretch,
    so the number is a rate and not a coincidence."""
    for ivl, want in ((0, 0.5), (1, 0.5), (3, 0.25), (7, 0.125)):
        await start_h(dut, scrub_en=1, ivl=ivl)
        await idle(dut, 4)
        n = 0
        span = 8 * (ivl + 1) * 8
        for _ in range(span):
            await Timer(T_SAMPLE, unit="ns")
            if val(dut.g_ecc.row_en):
                n += 1
            await RisingEdge(dut.clk_i)
        rate = n / span
        assert abs(rate - want) < 0.05, (
            "ivl {}: {} scrub reads in {} idle cycles, rate {:.3f}, "
            "expected {:.3f}".format(ivl, n, span, rate, want))
    # and disabled means none
    await start_h(dut, scrub_en=0, ivl=0)
    await idle(dut, 4)
    for _ in range(64):
        await Timer(T_SAMPLE, unit="ns")
        assert val(dut.g_ecc.row_en) == 0, "the row port moved with the scrubber off"
        await RisingEdge(dut.clk_i)


@hardened
async def test_nothing_is_reported_when_nothing_is_wrong(dut):
    """Random traffic of every shape the slave has, with the scrubber
    walking at interval 0 underneath it: no sec_o, no rd_o, no ded_o, no
    err_o on a legal access, and every read returns what was written.
    A report line that pulses on healthy traffic makes the SCRUB block's
    counters noise."""
    rep = await start_h(dut, scrub_en=1, ivl=0)
    rng = random.Random(0x67)
    # Every row is filled first: the array keeps whatever the previous
    # test left in it, so a model that assumed zeros would be a model of
    # a different memory.
    model = [rng.randrange(1 << 32) for _ in range(WORDS)]
    await fill(dut, model)
    for _ in range(300):
        i = rng.randrange(WORDS)
        if not RO and rng.randrange(3) == 0:
            be = rng.randrange(1, 16)
            w = rng.randrange(1 << 32)
            await xact(dut, 4 * i, we=1, be=be, wdata=w)
            for lane in range(4):
                if be & (1 << lane):
                    m = 0xFF << (8 * lane)
                    model[i] = (model[i] & ~m) | (w & m)
        else:
            data, err = await xact(dut, 4 * i)
            assert err == 0 and data == model[i]
        if rng.randrange(4) == 0:
            await idle(dut, rng.randrange(5))
    assert rep.sec == 0 and rep.rd == 0 and rep.ded == 0 and rep.err == 0


@hardened
async def test_a_read_only_memory_refuses_the_bus_and_keeps_its_codeword(dut):
    """The ROM build: a bus write is answered with err and changes
    nothing -- neither the word nor its check field -- so the only
    writer of the ROM's rows is the scrubber's write-back."""
    if not RO:
        return
    rep = await start_h(dut, scrub_en=1, ivl=0)
    words = [pattern(i) for i in range(WORDS)]
    await fill(dut, words)
    for i in (0, 7, WORDS - 1):
        data, err = await xact(dut, 4 * i, we=1, wdata=0xFFFFFFFF)
        assert err == 1, "a write into the ROM was not refused"
        assert stored(dut, i) == (words[i], golden_chk(words[i]))
        data, err = await xact(dut, 4 * i)
        assert (data, err) == (words[i], 0)
    assert rep.sec == 0 and rep.rd == 0 and rep.ded == 0
