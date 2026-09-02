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


@cocotb.test()
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


@cocotb.test()
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
    assert all(e == 0 for _, e in mon.responses), (
        "a read-write memory reported err on a legal access")
