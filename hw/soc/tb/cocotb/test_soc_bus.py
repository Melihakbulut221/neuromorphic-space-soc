# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""soc_bus system fabric suite.

Every expected value in this file comes from one of exactly two sources:

  * the bus protocol, which is Ibex's own req/gnt/rvalid handshake as stated
    in hw/soc/ext/ibex/doc/03_reference/load_store_unit.rst section
    "Protocol" (rules 1-4), together with the slave-side obligations S1-S4,
    the one-slave-per-outstanding-burst restriction and MAX_OUT = 2 that the
    header of hw/soc/rtl/soc_bus.v states as specification;

  * the memory map, read programmatically from sw/golden/memmap_gen.py,
    which is generated from regmap/memmap.yaml. No address literal appears
    in a check below: every base, every size, every gap and every decode is
    computed from REGIONS / MASKS / PORTS, so moving a region in the YAML
    moves what this suite demands of the fabric.

The RTL was read for three things only: the port names, the fact that
rst_ni is active low, and the slave index list, which is PARSED out of the
specification block in the soc_bus.v header rather than copied here. The
list is not read from the decode logic, so this suite still fails if the
decode disagrees with the header. SLAVE_INDEX is then cross-checked against
PORTS, so adding or removing a fabric port in the YAML without touching the
header, or the reverse, fails loudly instead of silently skipping coverage.

The slaves are behavioural Python models that obey S1-S4: always-ready
unless a test deliberately withholds gnt, configurable latency, in-order,
exactly one rvalid per grant. Each model returns a per-(slave, address)
unique word as rdata, which is the transaction tag: response ordering,
response routing between the two masters and payload broadcast are all
checked against those tags.

WHAT THIS SUITE DOES NOT COVER
------------------------------
  * Gate-level or timing behaviour. This is RTL simulation with no
    back-annotation; setup/hold and X-pessimism are out of scope.
  * Fabric behaviour when a slave BREAKS S1-S4. The models never return two
    rvalids for one grant, never reorder and never respond in the grant
    cycle, so the fabric's response to an illegal slave is unknown here.
  * Anything about reset beyond one property: that an idle master produces
    no slave traffic. Reset asserted in the middle of an outstanding
    transaction is not checked, and neither is a master that asserts req
    while rst_ni is low. Neither the LSU protocol nor the memory map says
    what either of those should do, and the fabric was measured to decode
    and grant a request presented during reset, which is harmless only
    because Ibex holds its request ports low in reset. If that assumption
    ever changes, this suite will not notice.
  * Exhaustive address decode. Each region is probed at its base, at its top
    word and at random interior words, not at every word, and the gap
    addresses are sampled, not enumerated.
  * The value of rdata from the internal error slave. Rule 3 makes rdata
    meaningless when err is high, so only err and the rvalid count are
    checked for unmapped accesses.
  * Byte-enable and write semantics inside a slave. The fabric only
    broadcasts be and wdata; whether a slave honours them is that slave's
    suite.
  * Misaligned and sub-word addressing rules, which live in Ibex's LSU and
    not in the fabric.
  * The wiring of the slave ports in soc_top.v. This suite takes the
    index order from the soc_bus.v specification header; that the top level
    connects index 2 to the APB bridge is not verified here.
  * More than the two Ibex masters, and any notion of arbitration fairness
    finer than the cycle bound stated in test_no_starvation.
  * Reset-domain crossing, and the placement of the clock gate itself.
    The two tests at the end of this file exercise `clk_en_o` -- the
    COMBINATIONAL statement soc_bus.v makes about whether its own state
    can move -- but the gate that consumes it lives in soc_top.v and is
    not instantiated here, so nothing below runs on a stopped clock.
    hw/soc/formal/soc_bus_props.v F10 is the proof that gating on this
    signal changes nothing; these two are the same statement checked by
    execution rather than by induction, and the reason for having both is
    that one of them can be run against a mutant in a minute.
"""

import random
import re
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

# sw/golden/memmap_gen.py is the generated Python view of regmap/memmap.yaml.
# The repo root is computed from this file's own location so the suite does
# not depend on the working directory.
_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / "sw"))
from golden.memmap_gen import MASKS, PORTS, REGIONS  # noqa: E402

# ---------------------------------------------------------------------------
# Constants that are specification, with their source.
# ---------------------------------------------------------------------------

# soc_bus.v header, "THE ONE RESTRICTION THIS FABRIC IMPOSES ON A MASTER":
# MAX_OUT is 2 because Ibex's prefetch buffer has NUM_REQS = 2.
MAX_OUT = 2

# The slave index order is READ OUT of soc_bus.v's header rather than
# copied into this file, and the reason is a defect this suite caught in
# itself. docs/51 added the NPU as fabric port 5: it updated the RTL, the
# memory map and the formal property set, and left this constant at five
# entries. The cross-check in test_memory_map_is_self_consistent then
# failed on every run -- correctly -- and nobody saw it, because the cocotb
# suites were not being run between documents. Transcribing the list again
# would rebuild exactly the thing that broke.
#
# There are now two independent sources and they must agree: the header
# gives the ORDER, and regmap/memmap.yaml gives the MEMBERSHIP. Adding a
# port to one and not to the other still fails, which is the property that
# caught this.
def _slave_index_from_rtl():
    """Parse "0 RAM, 1 ROM, 2 APB, 3 PNP, 4 CLINT, 5 NPU" from the header."""
    src = (_REPO / "hw" / "soc" / "rtl" / "soc_bus.v").read_text()
    at = src.find("Index order is fixed")
    assert at != -1, (
        "soc_bus.v no longer states its slave index order; this suite reads "
        "that list rather than carrying its own copy")
    window = src[at:at + 400]
    pairs = re.findall(r"(\d+)\s+([A-Z][A-Z0-9]*)\b", window)
    idx = {}
    for n, name in pairs:
        if name in idx:
            break            # past the list, into the error-slave sentence
        idx[name] = int(n)
    assert idx, f"could not parse a slave index list out of {window[:120]!r}"
    assert sorted(idx.values()) == list(range(len(idx))), (
        f"slave indices in the soc_bus.v header are not 0..N-1: {idx}")
    return idx


SLAVE_INDEX = _slave_index_from_rtl()
N_SLAVES = len(SLAVE_INDEX)

WORD = 4
ADDR_BITS = 32
ADDR_MAX = (1 << ADDR_BITS) - 1

CLK_NS = 10
T_DRIVE = 1   # every driver applies this cycle's stimulus here
T_SAMPLE = 8  # every monitor samples the settled cycle here
T_CHECK = 9   # test-level polling, after all monitors have run

# ---------------------------------------------------------------------------
# Memory map helpers. Nothing below hard-codes an address.
# ---------------------------------------------------------------------------


def region_of(addr):
    """Region containing addr by base/size containment, or None."""
    for name, (base, size, _t, _a, _s, _p) in REGIONS.items():
        if base <= addr < base + size:
            return name
    return None


def port_regions():
    """Region name -> (base, size) for the regions with a fabric port."""
    out = {}
    for port, region in PORTS.items():
        base, size = REGIONS[region][0], REGIONS[region][1]
        out[region] = (base, size)
    return out


def gaps():
    """Address ranges (lo, hi_inclusive) covered by no region at all."""
    spans = sorted((b, b + s - 1) for (b, s, _t, _a, _st, _p) in REGIONS.values())
    out = []
    cursor = 0
    for lo, hi in spans:
        if lo > cursor:
            out.append((cursor, lo - 1))
        cursor = hi + 1
    if cursor <= ADDR_MAX:
        out.append((cursor, ADDR_MAX))
    return out


def portless_regions():
    """Regions that exist in the map but have no fabric port (reserved)."""
    return {
        name: (base, size)
        for name, (base, size, _t, _a, _st, port) in REGIONS.items()
        if port is None
    }


def probe_addrs(base, size, rng, n_random=3):
    """Base, top word and a few random interior words of a region."""
    addrs = [base, base + size - WORD]
    for _ in range(n_random):
        addrs.append(base + WORD * rng.randrange(size // WORD))
    return addrs


def tag_of(slave_idx, addr):
    """Unique non-zero response word for a (slave, address) pair.

    This is the transaction tag. It is a bijection in addr for a fixed
    slave and disjoint across slaves, so a response that arrives at the
    wrong master, in the wrong order, or from the wrong slave is visible.
    A fabric that returned silent zeros cannot produce it.
    """
    h = (addr ^ 0x811C9DC5) * 0x01000193
    return ((h + 0x9E3779B9 * (slave_idx + 1)) & 0xFFFFFFFF) | 1


# ---------------------------------------------------------------------------
# Signal access
# ---------------------------------------------------------------------------


def val(sig):
    s = str(sig.value)
    if any(c not in "01" for c in s):
        raise AssertionError("non-binary value {!r} on {}".format(s, sig._path))
    return int(s, 2)


def popcount(x):
    return bin(x).count("1")


# ---------------------------------------------------------------------------
# Behavioural slave models (S1-S4)
# ---------------------------------------------------------------------------


class Slave:
    """One fabric slave port.

    S1: rules 1-4 from the slave side. gnt whenever ready; exactly one
    rvalid per grant, at least one cycle after it; in order.
    S2: address/we/be/wdata are captured in the grant cycle only.
    S3: in-order even with the two masters interleaved -- the queue is FIFO.
    S4: no limit imposed by the model; the fabric is the one that throttles.
    """

    def __init__(self, idx, latency=1):
        self.idx = idx
        self.latency = latency          # int or callable() -> int, >= 1
        self.ready = True               # drives s_gnt_i[idx]
        self.err_fn = lambda addr: 0
        self.pending = []               # FIFO of [remaining, rdata, err]
        self.captured = []              # (addr, we, be, wdata) per grant
        self.grants = 0

    def _latency(self):
        return self.latency() if callable(self.latency) else self.latency

    def accept(self, addr, we, be, wdata):
        self.grants += 1
        self.captured.append((addr, we, be, wdata))
        lat = max(1, self._latency())
        # In-order and at most one response per cycle (S1 rule 3, S3).
        if self.pending:
            lat = max(lat, self.pending[-1][0] + 1)
        self.pending.append([lat, tag_of(self.idx, addr), self.err_fn(addr)])

    def tick(self):
        """Advance one cycle. Returns (rvalid, rdata, err) for this cycle."""
        for p in self.pending:
            p[0] -= 1
        due = [p for p in self.pending if p[0] <= 0]
        assert len(due) <= 1, "slave model scheduled two responses in one cycle"
        if not due:
            return (0, 0, 0)
        p = due[0]
        self.pending.remove(p)
        return (1, p[1], p[2])


def pad_latencies(latencies):
    """Extend a latency tuple to N_SLAVES, padding with 1.

    Call sites choose latencies to create response-ordering variety, not to
    state a requirement, so a tuple shorter than the port count is a stale
    literal rather than an error. Padding here means adding a fabric port
    costs one edit -- the soc_bus.v header -- instead of one per call site,
    which is what turned a five-entry SLAVE_INDEX into a suite nobody could
    run. A tuple LONGER than the port count is still an error, because that
    means a port was removed and the call site was not revisited.
    """
    lat = tuple(latencies)
    assert len(lat) <= N_SLAVES, (
        f"{len(lat)} latencies for {N_SLAVES} slave ports; the fabric lost a "
        "port and this call site still names it")
    return lat + (1,) * (N_SLAVES - len(lat))


class SlaveArray:
    """Drives the slave-side input buses as one vector each."""

    def __init__(self, dut, latencies=()):
        self.dut = dut
        lat = pad_latencies(latencies)
        self.slaves = [Slave(i, lat[i]) for i in range(N_SLAVES)]

    def __getitem__(self, i):
        return self.slaves[i]

    async def run(self):
        dut = self.dut
        while True:
            await RisingEdge(dut.clk_i)
            await Timer(T_DRIVE, unit="ns")
            gnt = rvalid = err = 0
            for s in self.slaves:
                if s.ready:
                    gnt |= 1 << s.idx
                rv, rdata, e = s.tick()
                if rv:
                    rvalid |= 1 << s.idx
                    err |= e << s.idx
                    getattr(dut, "s_rdata_{}_i".format(s.idx)).value = rdata
            dut.s_gnt_i.value = gnt
            dut.s_rvalid_i.value = rvalid
            dut.s_err_i.value = err

            await Timer(T_SAMPLE - T_DRIVE, unit="ns")
            req = val(dut.s_req_o)
            for s in self.slaves:
                if (req >> s.idx) & 1 and s.ready:
                    # S2: the payload is valid in this cycle and only here.
                    s.accept(
                        val(dut.s_addr_o),
                        val(dut.s_we_o),
                        val(dut.s_be_o),
                        val(dut.s_wdata_o),
                    )


# ---------------------------------------------------------------------------
# Master agents
# ---------------------------------------------------------------------------


class Xact:
    def __init__(self, addr, we=0, be=0xF, wdata=0, exp_rdata=None, exp_err=0):
        self.addr = addr
        self.we = we
        self.be = be
        self.wdata = wdata
        self.exp_rdata = exp_rdata   # None = do not care (rule 3: err => rdata meaningless)
        self.exp_err = exp_err

    def __repr__(self):
        return "Xact(addr=0x{:08x}, we={})".format(self.addr, self.we)


class Master:
    """A protocol-legal Ibex-style master.

    Rule 1: req and the payload are held until gnt.
    Rule 2: after a grant the payload may change in the next cycle, and this
            driver does change it, which is what makes the fabric's duty to
            have captured it in the grant cycle observable.
    Rule 3: exactly one rvalid per grant, never in the grant cycle.
    Rule 4: responses in issue order.
    """

    def __init__(self, dut, name, read_only=False):
        self.dut = dut
        self.name = name
        self.read_only = read_only
        self.queue = []
        self.cur = None
        self.issued = []      # granted, awaiting response, in order
        self.grants = 0
        self.rvalids = 0
        self.outstanding = 0
        self.max_outstanding = 0
        self.grant_cycles = []
        self.idle_randomize = False
        self.cycle = 0
        self.rng = random.Random(0xB0 + len(name))
        self._sig = {
            s: getattr(dut, "{}_{}".format(name, s))
            for s in (
                "req_i", "addr_i", "gnt_o", "rvalid_o", "rdata_o", "err_o"
            )
        }
        if not read_only:
            for s in ("we_i", "be_i", "wdata_i"):
                self._sig[s] = getattr(dut, "{}_{}".format(name, s))

    # -- queue API ----------------------------------------------------------
    def push(self, xact):
        self.queue.append(xact)

    def idle(self):
        return not self.queue and self.cur is None and self.outstanding == 0

    # -- driving ------------------------------------------------------------
    def _drive(self, x):
        self._sig["req_i"].value = 1 if x else 0
        if x is not None:
            self._sig["addr_i"].value = x.addr
            if not self.read_only:
                self._sig["we_i"].value = x.we
                self._sig["be_i"].value = x.be
                self._sig["wdata_i"].value = x.wdata
        elif self.idle_randomize:
            # Rule 2 explicitly allows the payload to change once the
            # previous request has been granted; randomising it while req is
            # low is the strongest legal form of that.
            self._sig["addr_i"].value = self.rng.randrange(1 << 32) & ~3
            if not self.read_only:
                self._sig["we_i"].value = self.rng.randrange(2)
                self._sig["be_i"].value = self.rng.randrange(16)
                self._sig["wdata_i"].value = self.rng.randrange(1 << 32)

    async def run(self):
        dut = self.dut
        while True:
            await RisingEdge(dut.clk_i)
            await Timer(T_DRIVE, unit="ns")
            self.cycle += 1
            if self.cur is None and self.queue:
                self.cur = self.queue.pop(0)
            self._drive(self.cur)

            await Timer(T_SAMPLE - T_DRIVE, unit="ns")
            gnt = val(self._sig["gnt_o"])
            rvalid = val(self._sig["rvalid_o"])
            before = self.outstanding

            if self.cur is not None and gnt:
                self.grants += 1
                self.outstanding += 1
                self.grant_cycles.append(self.cycle)
                self.issued.append(self.cur)
                self.cur = None

            if rvalid:
                # Rule 3: a response comes one or more cycles AFTER the
                # grant, so something must already have been outstanding.
                assert before > 0, (
                    "{}: rvalid with nothing outstanding (a response in its "
                    "own grant cycle, or an unmatched response) at cycle {}"
                    .format(self.name, self.cycle)
                )
                self.rvalids += 1
                self.outstanding -= 1
                x = self.issued.pop(0)
                rdata = val(self._sig["rdata_o"])
                err = val(self._sig["err_o"])
                assert err == x.exp_err, (
                    "{}: err {} for {} at cycle {}, expected {}".format(
                        self.name, err, x, self.cycle, x.exp_err)
                )
                if x.exp_rdata is not None:
                    # Rules 4 and routing: the tag identifies the slave and
                    # the address, so a wrong value here is a reorder, a
                    # crossover between masters, or a wrong decode.
                    assert rdata == x.exp_rdata, (
                        "{}: rdata 0x{:08x} for {} at cycle {}, expected "
                        "0x{:08x}".format(
                            self.name, rdata, x, self.cycle, x.exp_rdata)
                    )

            # Rule 3 aggregate and the MAX_OUT restriction from the header.
            assert self.rvalids <= self.grants, (
                "{}: {} rvalids for {} grants at cycle {}".format(
                    self.name, self.rvalids, self.grants, self.cycle)
            )
            assert 0 <= self.outstanding <= MAX_OUT, (
                "{}: {} outstanding at cycle {}, limit is {}".format(
                    self.name, self.outstanding, self.cycle, MAX_OUT)
            )
            self.max_outstanding = max(self.max_outstanding, self.outstanding)


# ---------------------------------------------------------------------------
# Always-on bus monitor
# ---------------------------------------------------------------------------


class BusMonitor:
    """Checks the fabric-to-slave side on every cycle of every test.

    * S2 says the address, we, be and wdata buses are broadcast and are
      valid in the cycle where a slave's req and gnt are both high. There is
      one such bus, so at most one master can be granted in a cycle and at
      most one slave request can be asserted at a time.
    * In a grant cycle the broadcast payload must be the granted master's
      payload, and the instruction port is read-only so its we must be 0.
    * allowed_req is an optional set of legal s_req_o values, used by the
      decode tests to demand one specific target and nothing else.
    """

    def __init__(self, dut):
        self.dut = dut
        self.allowed_req = None
        self.cycle = 0

    async def run(self):
        dut = self.dut
        while True:
            await RisingEdge(dut.clk_i)
            await Timer(T_SAMPLE, unit="ns")
            self.cycle += 1
            req = val(dut.s_req_o)
            assert popcount(req) <= 1, (
                "s_req_o = 0b{:05b} at cycle {}: more than one slave "
                "selected, but there is a single broadcast payload bus (S2)"
                .format(req, self.cycle)
            )
            if self.allowed_req is not None:
                assert req in self.allowed_req, (
                    "s_req_o = 0b{:05b} at cycle {}, only {} permitted here"
                    .format(req, self.cycle,
                            ["0b{:05b}".format(v) for v in sorted(self.allowed_req)])
                )

            mi = val(dut.mi_req_i) and val(dut.mi_gnt_o)
            md = val(dut.md_req_i) and val(dut.md_gnt_o)
            assert not (mi and md), (
                "both masters granted in cycle {}: the payload bus can only "
                "carry one request (S2)".format(self.cycle)
            )
            if mi:
                assert val(dut.s_addr_o) == val(dut.mi_addr_i), (
                    "cycle {}: s_addr_o 0x{:08x} != mi_addr_i 0x{:08x} in the "
                    "instruction grant cycle (S2)".format(
                        self.cycle, val(dut.s_addr_o), val(dut.mi_addr_i))
                )
                assert val(dut.s_we_o) == 0, (
                    "cycle {}: s_we_o high for an instruction-port grant; "
                    "that port is read-only".format(self.cycle)
                )
            if md:
                assert val(dut.s_addr_o) == val(dut.md_addr_i), (
                    "cycle {}: s_addr_o 0x{:08x} != md_addr_i 0x{:08x} in the "
                    "data grant cycle (S2)".format(
                        self.cycle, val(dut.s_addr_o), val(dut.md_addr_i))
                )
                assert val(dut.s_we_o) == val(dut.md_we_i), (
                    "cycle {}: s_we_o != md_we_i in the data grant cycle (S2)"
                    .format(self.cycle)
                )
                assert val(dut.s_be_o) == val(dut.md_be_i), (
                    "cycle {}: s_be_o != md_be_i in the data grant cycle (S2)"
                    .format(self.cycle)
                )
                assert val(dut.s_wdata_o) == val(dut.md_wdata_i), (
                    "cycle {}: s_wdata_o != md_wdata_i in the data grant "
                    "cycle (S2)".format(self.cycle)
                )


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


class Env:
    def __init__(self, dut, latencies=()):
        self.dut = dut
        self.slaves = SlaveArray(dut, latencies)
        self.mi = Master(dut, "mi", read_only=True)
        self.md = Master(dut, "md", read_only=False)
        self.mon = BusMonitor(dut)

    def start(self):
        cocotb.start_soon(self.slaves.run())
        cocotb.start_soon(self.mi.run())
        cocotb.start_soon(self.md.run())
        cocotb.start_soon(self.mon.run())

    async def drain(self, limit=4000):
        for _ in range(limit):
            await RisingEdge(self.dut.clk_i)
            await Timer(T_CHECK, unit="ns")
            if self.mi.idle() and self.md.idle():
                return
        raise AssertionError(
            "fabric did not drain in {} cycles: mi outstanding {} queue {}, "
            "md outstanding {} queue {}".format(
                limit, self.mi.outstanding, len(self.mi.queue),
                self.md.outstanding, len(self.md.queue))
        )


async def setup(dut, latencies=(), start=True):
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    dut.rst_ni.value = 0
    dut.mi_req_i.value = 0
    dut.mi_addr_i.value = 0
    dut.md_req_i.value = 0
    dut.md_addr_i.value = 0
    dut.md_we_i.value = 0
    dut.md_be_i.value = 0
    dut.md_wdata_i.value = 0
    dut.s_gnt_i.value = 0
    dut.s_rvalid_i.value = 0
    dut.s_err_i.value = 0
    for i in range(N_SLAVES):
        getattr(dut, "s_rdata_{}_i".format(i)).value = 0
    for _ in range(5):
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.rst_ni.value = 1
    env = Env(dut, latencies)
    if start:
        env.start()
    return env


async def single(env, master, xact, allowed_req):
    """Run one transaction alone with a fixed legal s_req_o set."""
    env.mon.allowed_req = allowed_req
    master.push(xact)
    await env.drain(limit=200)
    env.mon.allowed_req = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_memory_map_is_self_consistent(dut):
    """The map this suite derives its expectations from must be coherent.

    If REGIONS, MASKS and PORTS disagree, every decode expectation below is
    built on sand, so this runs first and fails loudly.
    """
    spans = []
    for name, (base, size, _t, _a, _st, _p) in REGIONS.items():
        assert size > 0 and (size & (size - 1)) == 0, (
            "{}: size 0x{:x} is not a power of two".format(name, size))
        assert base % size == 0, (
            "{}: base 0x{:08x} is not aligned to its size 0x{:x}".format(
                name, base, size))
        mask = MASKS[name]
        assert (~mask) & ADDR_MAX == size - 1, (
            "{}: MASK 0x{:08x} does not describe size 0x{:x}".format(
                name, mask, size))
        assert base & mask == base
        assert (base + size - WORD) & mask == base
        spans.append((base, base + size - 1, name))

    spans.sort()
    for (lo0, hi0, n0), (lo1, _hi1, n1) in zip(spans, spans[1:]):
        assert hi0 < lo1, "{} and {} overlap".format(n0, n1)
        assert lo0 <= hi0

    assert set(SLAVE_INDEX) == set(PORTS.values()), (
        "the fabric ports in the memory map {} do not match the slave index "
        "order {} stated in the soc_bus.v specification header".format(
            sorted(PORTS.values()), sorted(SLAVE_INDEX))
    )
    assert len(set(SLAVE_INDEX.values())) == N_SLAVES

    dut._log.info(
        "memory map: %d regions, %d with a fabric port, %d unmapped gaps",
        len(REGIONS), len(PORTS), len(gaps()))


@cocotb.test()
async def test_idle_masters_produce_no_slave_traffic(dut):
    """No master request means no slave request, in reset and out of it.

    Rule 1 makes a slave request the consequence of a master request. A
    slave selected with no master behind it would capture a phantom payload
    (S2) and would then owe a response (rule 3) that no master is counting,
    which breaks the one-rvalid-per-grant accounting for every later
    transaction on that slave.

    This is the only reset-related property asserted anywhere in this file:
    the master's own reset behaviour is not the fabric's contract, and
    neither the LSU protocol nor the memory map says anything about a
    request asserted while rst_ni is low, so nothing is claimed about it.
    """
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    dut.rst_ni.value = 0
    dut.mi_req_i.value = 0
    dut.mi_addr_i.value = REGIONS["RAM"][0]
    dut.md_req_i.value = 0
    dut.md_addr_i.value = REGIONS["ROM"][0]
    dut.md_we_i.value = 1
    dut.md_be_i.value = 0xF
    dut.md_wdata_i.value = 0xDEADBEEF
    dut.s_gnt_i.value = (1 << N_SLAVES) - 1
    dut.s_rvalid_i.value = 0
    dut.s_err_i.value = 0
    for i in range(N_SLAVES):
        getattr(dut, "s_rdata_{}_i".format(i)).value = 0

    for cycle in range(20):
        if cycle == 10:
            await Timer(T_DRIVE, unit="ns")
            dut.rst_ni.value = 1
        await RisingEdge(dut.clk_i)
        await Timer(T_SAMPLE, unit="ns")
        assert val(dut.s_req_o) == 0, (
            "s_req_o = 0b{:05b} in cycle {} with neither master requesting"
            .format(val(dut.s_req_o), cycle)
        )
        assert val(dut.mi_rvalid_o) == 0, (
            "mi_rvalid_o in cycle {} with nothing ever granted".format(cycle))
        assert val(dut.md_rvalid_o) == 0, (
            "md_rvalid_o in cycle {} with nothing ever granted".format(cycle))


@cocotb.test()
async def test_decode_every_mapped_region(dut):
    """Property 1: an access in a region raises that region's port and no other.

    Driven from PORTS and REGIONS. Every probe is checked from the cycle the
    request is asserted to the cycle it is granted, so a transient selection
    of the wrong slave fails too.
    """
    rng = random.Random(1)
    env = await setup(dut)
    probes = 0
    for region, (base, size) in port_regions().items():
        idx = SLAVE_INDEX[region]
        bit = 1 << idx
        for addr in probe_addrs(base, size, rng):
            assert region_of(addr) == region
            for master in (env.mi, env.md):
                x = Xact(addr, exp_rdata=tag_of(idx, addr), exp_err=0)
                if master is env.md:
                    x.we = rng.randrange(2)
                    x.be = rng.randrange(16)
                    x.wdata = rng.randrange(1 << 32)
                await single(env, master, x, allowed_req={0, bit})
                probes += 1
    assert probes == 2 * 5 * len(PORTS)
    assert env.mi.rvalids == env.mi.grants > 0
    assert env.md.rvalids == env.md.grants > 0
    dut._log.info("decode: %d probes over %d ported regions", probes, len(PORTS))


@cocotb.test()
async def test_unmapped_gap_addresses_error(dut):
    """Property 2, part 1: addresses in no region reach no slave and error.

    The gaps are computed by walking the sorted regions, so this covers
    whatever holes the current memory map has. Requirement: s_req_o stays
    zero for the whole transaction (no aliasing onto a real slave) and the
    master still gets exactly one rvalid with err high (rule 3). A fabric
    that answered with a silent zero, or that never answered at all, fails.
    """
    rng = random.Random(2)
    env = await setup(dut)
    n = 0
    for lo, hi in gaps():
        span = hi - lo + 1
        cands = [lo, (hi + 1 - WORD) & ~3]
        for _ in range(2):
            cands.append((lo + WORD * rng.randrange(span // WORD)) & ~3)
        for addr in cands:
            assert region_of(addr) is None, (
                "0x{:08x} is not actually in a gap".format(addr))
            await single(env, env.mi, Xact(addr, exp_err=1), allowed_req={0})
            await single(env, env.md,
                         Xact(addr, we=1, be=0xF, wdata=rng.randrange(1 << 32),
                              exp_err=1),
                         allowed_req={0})
            n += 2
    for s in env.slaves.slaves:
        assert s.grants == 0, (
            "slave {} was handed {} unmapped accesses".format(s.idx, s.grants))
    assert env.mi.rvalids == env.mi.grants == n // 2
    assert env.md.rvalids == env.md.grants == n // 2
    dut._log.info("unmapped: %d gap accesses over %d gaps", n, len(gaps()))


@cocotb.test()
async def test_reserved_regions_error(dut):
    """Property 2, part 2: mapped-but-portless regions also error.

    NPU, CLINT, PLIC, DEBUG and the QSPI windows exist in memmap.yaml but
    carry no fabric port. They must behave exactly like a gap: no slave
    selected, one rvalid, err high. Derived from the `port is None` column,
    so promoting one of them to a real port in the YAML turns this into a
    failure that has to be looked at.
    """
    rng = random.Random(3)
    env = await setup(dut)
    n = 0
    reserved = portless_regions()
    assert reserved, "the memory map has no portless region left to check"
    for name, (base, size) in reserved.items():
        for addr in probe_addrs(base, size, rng, n_random=2):
            await single(env, env.mi, Xact(addr, exp_err=1), allowed_req={0})
            await single(env, env.md, Xact(addr, we=1, exp_err=1),
                         allowed_req={0})
            n += 2
    for s in env.slaves.slaves:
        assert s.grants == 0, (
            "slave {} was handed {} reserved-region accesses".format(
                s.idx, s.grants))
    dut._log.info("reserved: %d accesses over %d portless regions",
                  n, len(reserved))


@cocotb.test()
async def test_one_rvalid_per_grant(dut):
    """Property 3: grants and rvalids balance, over a randomised stream.

    The per-cycle invariants (cumulative rvalids never ahead of grants, no
    rvalid without something outstanding) are enforced continuously by the
    master agents; this test supplies the traffic and checks the totals.
    Latencies differ per slave so responses from different targets are in
    flight at once.
    """
    rng = random.Random(4)
    env = await setup(dut, latencies=(1, 2, 5, 3, 2))
    env.mi.idle_randomize = True
    env.md.idle_randomize = True

    regions = list(port_regions().items())
    for _ in range(120):
        region, (base, size) = regions[rng.randrange(len(regions))]
        addr = base + WORD * rng.randrange(size // WORD)
        env.mi.push(Xact(addr, exp_rdata=tag_of(SLAVE_INDEX[region], addr)))
        region, (base, size) = regions[rng.randrange(len(regions))]
        addr = base + WORD * rng.randrange(size // WORD)
        env.md.push(Xact(addr, we=rng.randrange(2), be=rng.randrange(16),
                         wdata=rng.randrange(1 << 32),
                         exp_rdata=tag_of(SLAVE_INDEX[region], addr)))
    await env.drain(limit=4000)

    assert env.mi.grants == 120 and env.md.grants == 120
    assert env.mi.rvalids == env.mi.grants, (
        "mi: {} rvalids for {} grants".format(env.mi.rvalids, env.mi.grants))
    assert env.md.rvalids == env.md.grants, (
        "md: {} rvalids for {} grants".format(env.md.rvalids, env.md.grants))
    total_slave_grants = sum(s.grants for s in env.slaves.slaves)
    assert total_slave_grants == env.mi.grants + env.md.grants, (
        "slaves saw {} requests, masters were granted {}".format(
            total_slave_grants, env.mi.grants + env.md.grants))


@cocotb.test()
async def test_in_order_slow_then_fast(dut):
    """Property 4: responses come back in issue order, worst case first.

    A slow target followed by a fast one on the same master is exactly the
    case the same-slave restriction in the soc_bus.v header exists to make
    safe: if the fabric let the fast request pass, its answer would overtake
    the slow one and rule 4 would be broken. The tags make the order
    observable; the assertion lives in the master agent's response check.
    """
    rng = random.Random(5)
    slow = SLAVE_INDEX["APB"]
    fast = SLAVE_INDEX["RAM"]
    lat = [1] * N_SLAVES
    lat[slow] = 9
    env = await setup(dut, latencies=tuple(lat))

    slow_base, slow_size = port_regions()["APB"]
    fast_base, fast_size = port_regions()["RAM"]
    for _ in range(12):
        for master in (env.mi, env.md):
            a0 = slow_base + WORD * rng.randrange(slow_size // WORD)
            a1 = slow_base + WORD * rng.randrange(slow_size // WORD)
            b0 = fast_base + WORD * rng.randrange(fast_size // WORD)
            b1 = fast_base + WORD * rng.randrange(fast_size // WORD)
            master.push(Xact(a0, exp_rdata=tag_of(slow, a0)))
            master.push(Xact(a1, exp_rdata=tag_of(slow, a1)))
            master.push(Xact(b0, exp_rdata=tag_of(fast, b0)))
            master.push(Xact(b1, exp_rdata=tag_of(fast, b1)))
    await env.drain(limit=4000)
    assert env.mi.rvalids == 48 and env.md.rvalids == 48
    # Vacuity guard: the slow target must really have been slow enough to
    # overtake, i.e. more than one request was in flight at some point.
    assert env.mi.max_outstanding > 1 and env.md.max_outstanding > 1, (
        "no master ever had two requests outstanding, so nothing could have "
        "been reordered and this test proved nothing"
    )


@cocotb.test()
async def test_response_routing(dut):
    """Property 5: no response ever crosses between the two masters.

    The masters run concurrently against different slaves with different
    latencies, and each transaction's expected rdata is the tag of the
    (slave, address) it was issued to. The instruction master uses only ROM
    and the data master only RAM here, and their tag sets are therefore
    disjoint, so a crossed response is a tag the receiving master never
    issued and the agent's ordered comparison fails on it.
    """
    rng = random.Random(6)
    lat = [1] * N_SLAVES
    lat[SLAVE_INDEX["ROM"]] = 7
    lat[SLAVE_INDEX["RAM"]] = 1
    env = await setup(dut, latencies=tuple(lat))
    env.mi.idle_randomize = True
    env.md.idle_randomize = True

    rom_base, rom_size = port_regions()["ROM"]
    ram_base, ram_size = port_regions()["RAM"]
    mi_tags, md_tags = set(), set()
    for _ in range(80):
        a = rom_base + WORD * rng.randrange(rom_size // WORD)
        t = tag_of(SLAVE_INDEX["ROM"], a)
        mi_tags.add(t)
        env.mi.push(Xact(a, exp_rdata=t))
        b = ram_base + WORD * rng.randrange(ram_size // WORD)
        u = tag_of(SLAVE_INDEX["RAM"], b)
        md_tags.add(u)
        env.md.push(Xact(b, we=rng.randrange(2), be=rng.randrange(16),
                         wdata=rng.randrange(1 << 32), exp_rdata=u))
    assert not (mi_tags & md_tags), "tag ranges are not disjoint"
    await env.drain(limit=4000)
    assert env.mi.rvalids == 80 and env.md.rvalids == 80
    assert env.slaves[SLAVE_INDEX["ROM"]].grants == 80
    assert env.slaves[SLAVE_INDEX["RAM"]].grants == 80


@cocotb.test()
async def test_gnt_follows_the_slave(dut):
    """Property 6: a stable request is not required to change, and is not
    granted before the target slave grants.

    Rule 1 says the slave answers gnt when it is ready, which may be any
    number of cycles later, and the master holds req and the payload until
    then. S2 says the payload is only valid in the cycle req and gnt are
    both high. A fabric that granted a master while the target slave was
    withholding gnt would let the master move on (rule 2) before the slave
    had captured anything.
    """
    env = await setup(dut)
    ram = SLAVE_INDEX["RAM"]
    base = REGIONS["RAM"][0]

    for master in (env.mi, env.md):
        # The slave's ready flag is only ever changed at T_CHECK, after both
        # the slave model and the master agent have sampled this cycle, so
        # the model's gnt and its accept decision can never disagree.
        env.slaves[ram].ready = False
        addr = base + 0x40
        master.push(Xact(addr, exp_rdata=tag_of(ram, addr)))
        stalled = 0
        for _ in range(12):
            await RisingEdge(dut.clk_i)
            await Timer(T_CHECK, unit="ns")
            assert val(getattr(dut, master.name + "_gnt_o")) == 0, (
                "{} granted while the target slave withheld gnt".format(
                    master.name)
            )
            assert val(dut.s_req_o) == 1 << ram, (
                "the stalled request stopped being presented to its slave"
            )
            stalled += 1
        assert master.grants == 0 and master.rvalids == 0
        assert stalled == 12
        # The request must survive the stall unchanged and complete.
        env.slaves[ram].ready = True
        await env.drain(limit=100)
        assert master.grants == 1 and master.rvalids == 1
        master.grants = 0
        master.rvalids = 0
        assert env.slaves[ram].captured[-1][0] == addr


@cocotb.test()
async def test_no_starvation(dut):
    """Property 7: neither master is starved.

    Both masters request continuously against the same always-ready,
    one-cycle slave, which is the pure arbitration case: no target switch,
    no latency asymmetry. The soc_bus.v header claims round robin, so the
    bound checked here is that each master is granted at least once in every
    BOUND consecutive cycles of the measurement window. BOUND is 8, which is
    deliberately loose: it also tolerates the grant pauses that the MAX_OUT
    limit itself imposes. The gap actually observed is logged.
    """
    BOUND = 8
    env = await setup(dut)
    ram = SLAVE_INDEX["RAM"]
    base, size = port_regions()["RAM"]
    rng = random.Random(7)
    for m in (env.mi, env.md):
        for _ in range(200):
            a = base + WORD * rng.randrange(size // WORD)
            m.push(Xact(a, exp_rdata=tag_of(ram, a)))

    for _ in range(300):
        await RisingEdge(dut.clk_i)
        await Timer(T_CHECK, unit="ns")

    for m in (env.mi, env.md):
        assert m.grants > 0, "{} was never granted".format(m.name)
        cycles = m.grant_cycles
        start = cycles[0]
        worst = max(b - a for a, b in zip(cycles, cycles[1:]))
        dut._log.info("%s: %d grants, first at cycle %d, largest gap %d cycles",
                      m.name, len(cycles), start, worst)
        assert start <= BOUND, (
            "{}: first grant only at cycle {}, bound is {}".format(
                m.name, start, BOUND))
        assert worst <= BOUND, (
            "{}: {} cycles between consecutive grants, bound is {}".format(
                m.name, worst, BOUND))


@cocotb.test()
async def test_payload_broadcast(dut):
    """Property 8: the broadcast payload is the granted master's payload.

    S2 makes this the whole contract between the fabric and a slave, and the
    BusMonitor checks it on every grant cycle of every test in this file.
    Here it is exercised deliberately with values chosen to catch a stuck or
    swapped lane, and the slave models' capture logs are compared against
    what the masters actually issued.
    """
    rng = random.Random(8)
    env = await setup(dut, latencies=(1, 2, 3, 1, 4))
    regions = list(port_regions().items())
    expect = {i: [] for i in range(N_SLAVES)}

    patterns = [0x00000000, 0xFFFFFFFF, 0xAAAAAAAA, 0x55555555, 0xDEADBEEF]
    for i in range(60):
        region, (base, size) = regions[i % len(regions)]
        idx = SLAVE_INDEX[region]
        addr = base + WORD * rng.randrange(size // WORD)
        we = i % 2
        be = [0x0, 0x1, 0x3, 0xF, 0x8, 0x5][i % 6]
        wdata = patterns[i % len(patterns)]
        env.md.push(Xact(addr, we=we, be=be, wdata=wdata,
                         exp_rdata=tag_of(idx, addr)))
        expect[idx].append((addr, we, be, wdata))
    await env.drain(limit=2000)
    for idx, exp in expect.items():
        got = env.slaves[idx].captured
        assert got == exp, (
            "slave {} captured {} != issued {}".format(idx, got[:4], exp[:4]))

    # The instruction port carries no write signals at all; its grants must
    # broadcast we = 0, which the BusMonitor asserts. Drive some to make the
    # check non-vacuous, interleaved with data-port writes.
    env.md.push(Xact(REGIONS["RAM"][0], we=1, be=0xF, wdata=0xFFFFFFFF,
                     exp_rdata=tag_of(SLAVE_INDEX["RAM"], REGIONS["RAM"][0])))
    for i in range(20):
        addr = REGIONS["ROM"][0] + WORD * i
        env.mi.push(Xact(addr, exp_rdata=tag_of(SLAVE_INDEX["ROM"], addr)))
        addr = REGIONS["RAM"][0] + WORD * i
        env.md.push(Xact(addr, we=1, be=0xF, wdata=0xFFFFFFFF,
                         exp_rdata=tag_of(SLAVE_INDEX["RAM"], addr)))
    await env.drain(limit=2000)
    assert env.mi.rvalids == 20


@cocotb.test()
async def test_max_outstanding(dut):
    """Property 9: never more than MAX_OUT outstanding per master.

    The bound is asserted every cycle by the master agents. This test drives
    the case that can reach it -- both masters hammering a slow slave, so
    grants run ahead of responses -- and then checks that the bound was
    actually touched, otherwise the assertion above it would be vacuous.
    """
    rng = random.Random(9)
    env = await setup(dut, latencies=(6, 6, 6, 6, 6))
    base, size = port_regions()["RAM"]
    ram = SLAVE_INDEX["RAM"]
    for m in (env.mi, env.md):
        for _ in range(40):
            a = base + WORD * rng.randrange(size // WORD)
            m.push(Xact(a, exp_rdata=tag_of(ram, a)))
    await env.drain(limit=4000)
    for m in (env.mi, env.md):
        assert m.rvalids == 40
        assert m.max_outstanding == MAX_OUT, (
            "{}: peak outstanding was {}, expected to reach the {} the "
            "header allows".format(m.name, m.max_outstanding, MAX_OUT)
        )


@cocotb.test()
async def test_two_cycle_memories_at_full_rate(dut):
    """docs/50's SoC, driven at the fabric: the RAM and the boot ROM answer
    TWO cycles after the grant and everything else answers in one.

    The suite already proves the fabric correct at arbitrary latency --
    test_one_rvalid_per_grant runs five different ones and
    test_max_outstanding runs six. What none of them drives is the
    configuration the part actually has after docs/50, at the rate the
    part actually runs it: a request every cycle to a two-cycle memory, so
    the memory's pipeline is permanently full and the master is at the
    outstanding limit for most of the run.

    THE VACUITY GUARD IS THE POINT OF THE TEST. `max_outstanding == 2`
    asserts that two requests really were in flight at a two-cycle slave;
    without it a fabric that quietly serialised every access would pass
    every other assertion in this file, because serialising breaks no rule
    -- it only destroys the throughput docs/50 depends on. The grant count
    per cycle is checked for the same reason and against the same failure.
    """
    rng = random.Random(11)
    ram = SLAVE_INDEX["RAM"]
    rom = SLAVE_INDEX["ROM"]
    lat = [1] * N_SLAVES
    lat[ram] = 2
    lat[rom] = 2
    env = await setup(dut, latencies=tuple(lat))

    rom_base, rom_size = port_regions()["ROM"]
    ram_base, ram_size = port_regions()["RAM"]

    # PHASE 1: the instruction port alone, fetching linearly out of the
    # two-cycle boot ROM with the data port idle. This is the fetch stream
    # of an idle-dominated part and it is the only case in which the
    # outstanding limit can be reached at this latency: with both masters
    # asking, round-robin hands each of them every other cycle, and every
    # other cycle at two cycles of latency is an occupancy of one.
    n = 40
    for i in range(n):
        a = rom_base + WORD * (i % (rom_size // WORD))
        env.mi.push(Xact(a, exp_rdata=tag_of(rom, a)))
    await env.drain(limit=4000)
    assert env.mi.rvalids == n
    assert env.mi.max_outstanding == MAX_OUT, (
        "one master alone at a two-cycle slave peaked at {} outstanding, "
        "not {}. The fabric is serialising, which breaks no rule and costs "
        "half the fetch bandwidth.".format(env.mi.max_outstanding, MAX_OUT))

    # PHASE 2: both masters, .text in the two-cycle ROM and .data in the
    # two-cycle RAM, which is what soc_top.v's link map does. Correctness
    # only: the occupancy assertion above does not apply here, and the
    # reason it does not is the arbitration and not the latency.
    for _ in range(n):
        a = rom_base + WORD * rng.randrange(rom_size // WORD)
        env.mi.push(Xact(a, exp_rdata=tag_of(rom, a)))
        b = ram_base + WORD * rng.randrange(ram_size // WORD)
        env.md.push(Xact(b, we=rng.randrange(2), be=0xF,
                         wdata=rng.randrange(1 << 32),
                         exp_rdata=tag_of(ram, b)))
    await env.drain(limit=4000)
    assert env.mi.rvalids == 2 * n and env.md.rvalids == n
    total = env.slaves[rom].grants + env.slaves[ram].grants
    assert total == 3 * n, (
        "the two two-cycle memories saw {} requests for {} grants".format(
            total, 3 * n))


@cocotb.test()
async def test_slave_error_propagates(dut):
    """Rule 3: err belongs to the response it arrives with.

    A slave that reports an error must have that error delivered to the
    master that issued the request, in the same cycle as that request's
    rvalid and not any other. The models flag an error on a deterministic
    subset of addresses, and both masters issue a mix of erroring and clean
    accesses concurrently.
    """
    rng = random.Random(10)
    env = await setup(dut, latencies=(1, 4, 2, 3, 5))

    def bad(addr):
        return 1 if (addr >> 4) & 1 else 0

    for s in env.slaves.slaves:
        s.err_fn = bad

    regions = list(port_regions().items())
    n_err = 0
    for _ in range(60):
        for m in (env.mi, env.md):
            region, (base, size) = regions[rng.randrange(len(regions))]
            idx = SLAVE_INDEX[region]
            addr = base + WORD * rng.randrange(size // WORD)
            e = bad(addr)
            n_err += e
            m.push(Xact(addr, we=(0 if m is env.mi else rng.randrange(2)),
                        be=0xF, wdata=rng.randrange(1 << 32),
                        exp_rdata=tag_of(idx, addr), exp_err=e))
    await env.drain(limit=4000)
    assert env.mi.rvalids == 60 and env.md.rvalids == 60
    assert n_err > 0, "no erroring access was generated"
    dut._log.info("error propagation: %d of 120 responses carried err", n_err)


# ---------------------------------------------------------------------------
# The clock-gate enable (docs/76)
# ---------------------------------------------------------------------------

# soc_bus.v's own register list, in the order its header's G1 to G5 name
# them. The two arrays are indexed because cocotb reaches a Verilog memory
# one element at a time. NS = 7 is six slave ports plus the internal error
# slave, which is soc_bus.v's own localparam and is derived here from the
# port width rather than written down.
_SCALAR_REGS = ("issue_en", "last_was_d", "err_rvalid",
                "cnt_i", "cnt_d", "lock_i", "lock_d")


def _state(dut):
    """Every flip-flop in soc_bus, as one comparable tuple."""
    vals = []
    for name in _SCALAR_REGS:
        vals.append(int(getattr(dut, name).value))
    for s in range(N_SLAVES + 1):
        vals.append(int(dut.q_owner[s].value))
        vals.append(int(dut.q_fill[s].value))
    return tuple(vals)


@cocotb.test()
async def test_the_clock_enable_is_low_only_when_no_register_moves(dut):
    """F10, executed rather than proved: the enable is COMPLETE.

    soc_top.v replaces this module's clock with ICG(clk_i, clk_en_o). That
    is sound if and only if the enable is low only in cycles where no
    register would have changed anyway, because then the gated instance and
    the ungated one have the same state in every cycle and F1 to F9 --
    the fairness bound F9 included -- transport unchanged rather than
    having to be restated for a slave whose clock is off.

    This samples the whole of soc_bus's state at every edge of a busy mixed
    workload and asserts that statement directly. It is weaker than the
    k-induction proof, which quantifies over every reachable state; it is
    stronger in one respect, which is that it runs against the RTL a
    simulator elaborates rather than against the one yosys reads.
    """
    rng = random.Random(2026)
    env = await setup(dut, latencies=(1, 2, 4, 3, 7, 11))

    regions = list(port_regions().items())
    for _ in range(120):
        for m in (env.mi, env.md):
            region, (base, size) = regions[rng.randrange(len(regions))]
            idx = SLAVE_INDEX[region]
            addr = base + WORD * rng.randrange(size // WORD)
            m.push(Xact(addr, we=(0 if m is env.mi else rng.randrange(2)),
                        be=0xF, wdata=rng.randrange(1 << 32),
                        exp_rdata=tag_of(idx, addr)))

    shut = 0
    seen = 0
    prev = None
    prev_en = None
    for _ in range(6000):
        await RisingEdge(dut.clk_i)
        await Timer(T_CHECK, unit="ns")
        now = _state(dut)
        if prev is not None and prev_en == 0:
            assert now == prev, (
                "clk_en_o was low for the cycle ending at this edge and the "
                "fabric's state moved anyway: {} -> {}. The gate soc_top.v "
                "builds on this signal would have lost that transition."
                .format(prev, now))
        if prev_en == 0:
            shut += 1
        seen += 1
        prev = now
        prev_en = int(dut.clk_en_o.value)
        if env.mi.idle() and env.md.idle():
            break

    assert seen > 200, "the workload was too short to say anything"
    assert shut > 0, (
        "clk_en_o was never low in {} cycles, so this test proved nothing "
        "about a gate that never closes".format(seen))
    dut._log.info("clock enable: shut on %d of %d cycles, no state moved "
                  "in any of them", shut, seen)


@cocotb.test()
async def test_the_clock_enable_closes_while_a_slow_slave_is_working(dut):
    """And it closes in the case that is worth having, not only when idle.

    soc_bus.v's own header says the enable deliberately contains no
    "something is outstanding" term: a master waiting on the NPU register
    window waits about 172 cycles, and the fabric has nothing to do for any
    of them but the last. A gate that only closed with the fabric
    completely empty would leave that on the table, so the property is that
    the enable goes low WHILE a transaction is in flight.

    The bound below is deliberately loose -- more than half the wait -- so
    that the test states the effect and not the arithmetic of one latency.
    """
    slow = 40
    env = await setup(dut, latencies=(slow, 1, 1, 1, 1, 1))
    base, size = port_regions()["RAM"]
    env.mi.push(Xact(base, exp_rdata=tag_of(SLAVE_INDEX["RAM"], base)))

    shut = 0
    for _ in range(slow + 20):
        await RisingEdge(dut.clk_i)
        await Timer(T_CHECK, unit="ns")
        if int(dut.clk_en_o.value) == 0:
            shut += 1
        if env.mi.idle():
            break
    assert env.mi.rvalids == 1, "the slow slave never answered"
    assert shut > slow // 2, (
        "the fabric held its clock enable high for all but {} of a {}-cycle "
        "wait; the gate is then worth only the fully idle case".format(
            shut, slow))
    dut._log.info("one %d-cycle access: the enable was low on %d of its "
                  "cycles", slow, shut)
