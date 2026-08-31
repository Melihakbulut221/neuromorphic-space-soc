"""soc_apb_bridge suite: AMBA 3 APB compliance on the peripheral side.

The expectations here come from two places and nowhere else:

  * the AMBA 3 APB protocol -- every transfer is IDLE, then SETUP for
    exactly one cycle with PSEL high and PENABLE low, then ACCESS with both
    high held until PREADY, with PADDR, PWRITE, PWDATA and PSTRB stable from
    SETUP through the whole ACCESS phase, PENABLE never high while PSEL is
    low, and PRDATA and PSLVERR meaningful only in the cycle PREADY is high.
    The fabric side of the bridge speaks the Ibex req/gnt/rvalid protocol
    quoted in the header of hw/soc/rtl/soc_bus.v: rule 3 gives exactly one
    rvalid per granted request, carrying rdata and err in that cycle;
  * the memory map, read programmatically from sw/golden/memmap_gen.py,
    which is generated from regmap/memmap.yaml. The APB window base and
    size and every peripheral slot address are taken from APB_BASE,
    REGIONS["APB"] and APB_SLOTS, so no address literal appears in a check
    and moving the window in the YAML moves what is demanded here.

The RTL was read for the port names and for the fact that rst_ni is active
low. Nothing below restates the state encoding or any other implementation
detail.

The APB slave model deliberately drives garbage on PRDATA and PSLVERR in
every cycle in which it is not asserting PREADY, and drives PREADY randomly
while it is not in an ACCESS phase. The specification makes all three
signals meaningless in those cycles, so a bridge that sampled any of them
early is caught rather than accidentally passing.

check_apb_protocol() is a continuous monitor. It runs for the whole of every
test in this file, so the state-machine, PENABLE-versus-PSEL and payload
stability rules are checked on every cycle of every scenario, not only in a
dedicated test.

WHAT THIS SUITE DOES NOT COVER
------------------------------
  * The per-slot PSEL decode. This bridge drives a single psel_o plus the
    window offset; which peripheral that offset selects is decided in
    soc_top.v and is not exercised here at all. test_paddr_is_window_offset
    checks the offset, not the selection.
  * Everything in APB4 and APB5 that this port does not have: PPROT,
    PWAKEUP, the user signalling, and parity. Only PSEL, PENABLE, PADDR,
    PWRITE, PWDATA, PSTRB, PRDATA, PREADY and PSLVERR exist here.
  * What a peripheral does with PSTRB. The bridge only has to carry the
    byte lanes; whether a register bank honours them is that block's suite.
  * Read data integrity beyond a single captured word, and any notion of
    burst, locking or back-pressure other than PREADY wait states.
  * Reset asserted in the middle of a transfer, and any behaviour with
    rst_ni low other than that no transfer starts and no rvalid appears.
    APB says nothing about reset mid-transfer, so nothing is claimed.
  * More than one outstanding fabric request. The bridge header states it
    accepts one at a time and withholds gnt otherwise, which S4 permits;
    this suite checks that only one transfer is ever in flight, it does not
    check a pipelined variant that does not exist.
  * Gate-level and timing behaviour, X-propagation, clock gating and power.
  * The wait-state counts a real peripheral will produce. The wait states
    here are model-driven (0, 1, several, and a randomised mix), not
    measured from soc_uart.v or any other slot.
"""

import random
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
from golden.memmap_gen import APB_BASE, APB_SLOTS, REGIONS  # noqa: E402

APB_SIZE = REGIONS["APB"][1]
PADDR_BITS = 20                      # the port is [19:0]
WORD = 4

CLK_NS = 10
T_DRIVE = 1    # fabric-side master applies this cycle's stimulus
T_RESP = 5     # APB slave model responds to this cycle's PSEL/PENABLE
T_SAMPLE = 8   # monitors sample the settled cycle
T_CHECK = 9    # test-level polling, after every monitor has run


def val(sig):
    s = str(sig.value)
    if any(c not in "01" for c in s):
        raise AssertionError("non-binary value {!r} on {}".format(s, sig._path))
    return int(s, 2)


def read_data(offset):
    """The word a peripheral at this window offset returns.

    A bijection in the offset that is never zero, so a captured word proves
    both that PRDATA was sampled in the right cycle and that PADDR carried
    the right offset to the peripheral in the first place.
    """
    h = ((offset ^ 0x5F3A7) * 0x01000193) & 0xFFFFFFFF
    return (h ^ 0xA5A50000) | 1


# ---------------------------------------------------------------------------
# APB slave model
# ---------------------------------------------------------------------------


class ApbSlave:
    """A protocol-legal APB completer with configurable wait states.

    PREADY is asserted after `waits` ACCESS cycles. PRDATA and PSLVERR are
    driven with the real values only in that cycle; in every other cycle
    they are garbage, because the specification makes them meaningless
    there. PREADY itself is randomised outside the ACCESS phase for the same
    reason: a master is required to sample it only in ACCESS.
    """

    def __init__(self, dut, waits=0, seed=0):
        self.dut = dut
        self.waits = waits            # int or callable() -> int
        self.err_fn = lambda off: 0
        self.rng = random.Random(seed)
        self.idle_noise = True
        self.acc = 0
        self.this_waits = None
        self.transfers = 0            # PREADY handshakes seen
        self.seen = []                # (offset, pwrite, pwdata, pstrb) per transfer

    def _waits(self):
        return self.waits() if callable(self.waits) else self.waits

    async def run(self):
        dut = self.dut
        while True:
            await RisingEdge(dut.clk_i)
            await Timer(T_RESP, unit="ns")
            psel = val(dut.psel_o)
            penable = val(dut.penable_o)
            if psel and penable:
                if self.acc == 0:
                    self.this_waits = self._waits()
                self.acc += 1
                ready = self.acc > self.this_waits
            else:
                self.acc = 0
                ready = self.rng.randrange(2) if self.idle_noise else 0

            if psel and penable and ready:
                off = val(dut.paddr_o)
                dut.prdata_i.value = read_data(off)
                dut.pslverr_i.value = self.err_fn(off)
                self.transfers += 1
                self.seen.append((off, val(dut.pwrite_o), val(dut.pwdata_o),
                                  val(dut.pstrb_o)))
            else:
                # Meaningless in this cycle; make that visible.
                dut.prdata_i.value = self.rng.randrange(1 << 32)
                dut.pslverr_i.value = self.rng.randrange(2)
            dut.pready_i.value = 1 if ready else 0


# ---------------------------------------------------------------------------
# Continuous APB protocol monitor
# ---------------------------------------------------------------------------


class ApbMonitor:
    """AMBA 3 APB state machine, PENABLE/PSEL and payload stability.

    Runs on every cycle of every test. The rules checked are:
      1. IDLE -> SETUP (PSEL, no PENABLE) for exactly one cycle -> ACCESS
         (PSEL and PENABLE) held until PREADY, then IDLE or a new SETUP.
      2. PENABLE is never high while PSEL is low.
      3. PADDR, PWRITE, PWDATA and PSTRB are stable from the SETUP cycle
         through the whole ACCESS phase.
    """

    FIELDS = ("paddr_o", "pwrite_o", "pwdata_o", "pstrb_o")

    def __init__(self, dut):
        self.dut = dut
        self.prev = None
        self.cycle = 0
        self.setups = 0
        self.access_cycles = 0

    def _sample(self):
        dut = self.dut
        s = {f: val(getattr(dut, f)) for f in self.FIELDS}
        s["psel"] = val(dut.psel_o)
        s["penable"] = val(dut.penable_o)
        s["pready"] = val(dut.pready_i)
        return s

    def _stable(self, prev, cur, why):
        for f in self.FIELDS:
            assert prev[f] == cur[f], (
                "cycle {}: {} changed from 0x{:x} to 0x{:x} {}".format(
                    self.cycle, f, prev[f], cur[f], why)
            )

    async def run(self):
        dut = self.dut
        while True:
            await RisingEdge(dut.clk_i)
            await Timer(T_SAMPLE, unit="ns")
            self.cycle += 1
            cur = self._sample()

            # Rule 2.
            assert not (cur["penable"] and not cur["psel"]), (
                "cycle {}: PENABLE high while PSEL low".format(self.cycle))

            if cur["psel"] and not cur["penable"]:
                self.setups += 1
            if cur["psel"] and cur["penable"]:
                self.access_cycles += 1

            prev = self.prev
            if prev is not None:
                if prev["psel"] and not prev["penable"]:
                    # SETUP: exactly one cycle, then ACCESS with the same
                    # payload (rules 1 and 3).
                    assert cur["psel"] and cur["penable"], (
                        "cycle {}: SETUP was not followed by ACCESS "
                        "(PSEL={}, PENABLE={})".format(
                            self.cycle, cur["psel"], cur["penable"])
                    )
                    self._stable(prev, cur, "between SETUP and ACCESS")
                elif prev["psel"] and prev["penable"]:
                    if not prev["pready"]:
                        # ACCESS is held until PREADY, payload unchanged.
                        assert cur["psel"] and cur["penable"], (
                            "cycle {}: ACCESS phase left before PREADY "
                            "(PSEL={}, PENABLE={})".format(
                                self.cycle, cur["psel"], cur["penable"])
                        )
                        self._stable(prev, cur, "during a wait state")
                    else:
                        # After PREADY the only legal next states are IDLE
                        # and a new SETUP.
                        assert not (cur["psel"] and cur["penable"]), (
                            "cycle {}: stayed in ACCESS after PREADY instead "
                            "of returning to IDLE or SETUP".format(self.cycle)
                        )
                else:
                    # IDLE: ACCESS can only be entered through SETUP.
                    assert not cur["penable"], (
                        "cycle {}: entered ACCESS directly from IDLE"
                        .format(self.cycle)
                    )
            self.prev = cur


# ---------------------------------------------------------------------------
# Fabric-side master
# ---------------------------------------------------------------------------


class Xact:
    def __init__(self, addr, we=0, be=0xF, wdata=0):
        self.addr = addr
        self.we = we
        self.be = be
        self.wdata = wdata

    @property
    def offset(self):
        return self.addr & ((1 << PADDR_BITS) - 1)

    def __repr__(self):
        return "Xact(addr=0x{:08x}, we={})".format(self.addr, self.we)


class FabricMaster:
    """Ibex-native master: holds req and payload until gnt (rule 1), then
    expects exactly one rvalid (rule 3), never in the grant cycle."""

    def __init__(self, dut, err_fn):
        self.dut = dut
        self.err_fn = err_fn
        self.queue = []
        self.cur = None
        self.issued = []
        self.grants = 0
        self.rvalids = 0
        self.outstanding = 0
        self.max_outstanding = 0
        self.cycle = 0
        self.rng = random.Random(0x5EED)

    def push(self, x):
        self.queue.append(x)

    def idle(self):
        return not self.queue and self.cur is None and self.outstanding == 0

    async def run(self):
        dut = self.dut
        while True:
            await RisingEdge(dut.clk_i)
            await Timer(T_DRIVE, unit="ns")
            self.cycle += 1
            if self.cur is None and self.queue:
                self.cur = self.queue.pop(0)
            if self.cur is not None:
                dut.req_i.value = 1
                dut.addr_i.value = self.cur.addr
                dut.we_i.value = self.cur.we
                dut.be_i.value = self.cur.be
                dut.wdata_i.value = self.cur.wdata
            else:
                # Rule 2 of the fabric protocol permits the payload to move
                # once the previous request has been granted.
                dut.req_i.value = 0
                dut.addr_i.value = self.rng.randrange(1 << 32) & ~3
                dut.we_i.value = self.rng.randrange(2)
                dut.be_i.value = self.rng.randrange(16)
                dut.wdata_i.value = self.rng.randrange(1 << 32)

            await Timer(T_SAMPLE - T_DRIVE, unit="ns")
            gnt = val(dut.gnt_o)
            rvalid = val(dut.rvalid_o)
            before = self.outstanding

            if self.cur is not None and gnt:
                self.grants += 1
                self.outstanding += 1
                self.issued.append(self.cur)
                self.cur = None

            if rvalid:
                assert before > 0, (
                    "cycle {}: rvalid with nothing outstanding".format(
                        self.cycle)
                )
                self.rvalids += 1
                self.outstanding -= 1
                x = self.issued.pop(0)
                rdata = val(dut.rdata_o)
                err = val(dut.err_o)
                exp_err = self.err_fn(x.offset)
                assert err == exp_err, (
                    "cycle {}: err_o {} for {}, expected {} from PSLVERR in "
                    "that transfer's PREADY cycle".format(
                        self.cycle, err, x, exp_err)
                )
                assert rdata == read_data(x.offset), (
                    "cycle {}: rdata_o 0x{:08x} for {}, expected the "
                    "0x{:08x} the completer drove on PRDATA in the PREADY "
                    "cycle".format(
                        self.cycle, rdata, x, read_data(x.offset))
                )

            assert self.rvalids <= self.grants, (
                "cycle {}: {} rvalids for {} grants".format(
                    self.cycle, self.rvalids, self.grants)
            )
            self.max_outstanding = max(self.max_outstanding, self.outstanding)


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


class Env:
    def __init__(self, dut, waits=0, seed=0, err_fn=None):
        self.dut = dut
        self.slave = ApbSlave(dut, waits, seed)
        if err_fn is not None:
            self.slave.err_fn = err_fn
        self.master = FabricMaster(dut, lambda off: self.slave.err_fn(off))
        self.mon = ApbMonitor(dut)

    def start(self):
        cocotb.start_soon(self.slave.run())
        cocotb.start_soon(self.mon.run())
        cocotb.start_soon(self.master.run())

    async def drain(self, limit=4000):
        for _ in range(limit):
            await RisingEdge(self.dut.clk_i)
            await Timer(T_CHECK, unit="ns")
            if self.master.idle():
                return
        raise AssertionError(
            "bridge did not drain in {} cycles: {} outstanding, {} queued"
            .format(limit, self.master.outstanding, len(self.master.queue))
        )


async def setup(dut, waits=0, seed=0, err_fn=None, start=True):
    cocotb.start_soon(Clock(dut.clk_i, CLK_NS, unit="ns").start())
    dut.rst_ni.value = 0
    dut.req_i.value = 0
    dut.addr_i.value = 0
    dut.we_i.value = 0
    dut.be_i.value = 0
    dut.wdata_i.value = 0
    dut.prdata_i.value = 0
    dut.pready_i.value = 0
    dut.pslverr_i.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk_i)
    await Timer(T_DRIVE, unit="ns")
    dut.rst_ni.value = 1
    env = Env(dut, waits, seed, err_fn)
    if start:
        env.start()
    return env


def slot_addrs(rng, per_slot=1):
    """One address per peripheral slot, from APB_SLOTS, plus interior words."""
    out = []
    for name, (addr, _slot, _irq, _status) in APB_SLOTS.items():
        assert APB_BASE <= addr < APB_BASE + APB_SIZE, (
            "{} at 0x{:08x} is outside the APB window".format(name, addr))
        out.append(addr)
        for _ in range(per_slot - 1):
            out.append(addr + WORD * rng.randrange(256))
    return out


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@cocotb.test()
async def test_apb_window_is_self_consistent(dut):
    """The window this suite derives its offsets from must be coherent."""
    assert APB_BASE == REGIONS["APB"][0]
    assert APB_SIZE == (1 << PADDR_BITS), (
        "the APB window is 0x{:x} bytes but paddr_o is {} bits wide, so the "
        "offset the bridge carries can no longer address the window"
        .format(APB_SIZE, PADDR_BITS)
    )
    assert REGIONS["APB"][5] == "apb"
    for name, (addr, slot, _irq, _status) in APB_SLOTS.items():
        assert APB_BASE <= addr < APB_BASE + APB_SIZE, name
        assert (addr - APB_BASE) & ((1 << PADDR_BITS) - 1) == addr - APB_BASE
    dut._log.info("APB window 0x%08x size 0x%x, %d slots",
                  APB_BASE, APB_SIZE, len(APB_SLOTS))


@cocotb.test()
async def test_idle_bridge_starts_no_transfer(dut):
    """With no fabric request there is no APB transfer and no rvalid.

    The completer is driving PREADY randomly throughout, which the
    specification permits because PREADY only means anything in an ACCESS
    phase. A bridge that started a transfer, or produced a response, without
    a request would break the one-rvalid-per-granted-request rule.
    """
    env = await setup(dut, waits=0)
    for cycle in range(40):
        await RisingEdge(dut.clk_i)
        await Timer(T_CHECK, unit="ns")
        assert val(dut.psel_o) == 0, (
            "cycle {}: PSEL asserted with no fabric request".format(cycle))
        assert val(dut.penable_o) == 0, (
            "cycle {}: PENABLE asserted with no fabric request".format(cycle))
        assert val(dut.rvalid_o) == 0, (
            "cycle {}: rvalid_o with nothing granted".format(cycle))
    assert env.slave.transfers == 0
    assert env.master.grants == 0


@cocotb.test()
async def test_paddr_is_window_offset(dut):
    """paddr_o carries addr_i[19:0], the offset inside the 1 MiB window.

    Every peripheral slot address in APB_SLOTS is driven, plus the window
    base and its top word. The expected value is computed as addr - APB_BASE
    from the generated map and cross-checked against the bit-slice reading
    of the same requirement, so the two can never drift apart silently.
    """
    rng = random.Random(11)
    env = await setup(dut, waits=1)
    addrs = slot_addrs(rng, per_slot=2)
    addrs += [APB_BASE, APB_BASE + APB_SIZE - WORD]
    seen = []
    for addr in addrs:
        env.master.push(Xact(addr, we=addr & 1))
        seen.append(addr)
    await env.drain(limit=4000)

    assert env.slave.transfers == len(addrs)
    assert len(env.slave.seen) == len(addrs)
    for addr, (off, _w, _d, _s) in zip(seen, env.slave.seen):
        expect = addr - APB_BASE
        assert expect == (addr & ((1 << PADDR_BITS) - 1)), (
            "0x{:08x}: the two readings of the offset requirement disagree"
            .format(addr))
        assert off == expect, (
            "0x{:08x}: paddr_o was 0x{:05x}, the window offset is 0x{:05x}"
            .format(addr, off, expect))
    dut._log.info("paddr offset: %d addresses over %d slots",
                  len(addrs), len(APB_SLOTS))


@cocotb.test()
async def test_zero_wait_states(dut):
    """PREADY high in the first ACCESS cycle.

    The transfer must still pass through a one-cycle SETUP -- the monitor
    enforces that -- and must return exactly one rvalid carrying the PRDATA
    of the PREADY cycle.
    """
    rng = random.Random(12)
    env = await setup(dut, waits=0)
    for addr in slot_addrs(rng):
        env.master.push(Xact(addr))
    n = len(APB_SLOTS)
    await env.drain(limit=2000)
    assert env.master.rvalids == n and env.master.grants == n
    assert env.slave.transfers == n
    # One ACCESS cycle per transfer when there are no wait states.
    assert env.mon.access_cycles == n, (
        "{} ACCESS cycles for {} zero-wait transfers".format(
            env.mon.access_cycles, n)
    )
    assert env.mon.setups == n


@cocotb.test()
async def test_one_wait_state(dut):
    """PREADY low for one ACCESS cycle, then high."""
    rng = random.Random(13)
    env = await setup(dut, waits=1)
    for addr in slot_addrs(rng):
        env.master.push(Xact(addr))
    n = len(APB_SLOTS)
    await env.drain(limit=2000)
    assert env.master.rvalids == n
    assert env.slave.transfers == n
    assert env.mon.access_cycles == 2 * n, (
        "{} ACCESS cycles for {} one-wait transfers".format(
            env.mon.access_cycles, n)
    )


@cocotb.test()
async def test_many_wait_states(dut):
    """PREADY low for many cycles.

    The ACCESS phase must be held with PSEL and PENABLE high and the whole
    payload frozen for the entire stall, which the monitor checks cycle by
    cycle, and the transfer must then complete normally.
    """
    WAITS = 11
    rng = random.Random(14)
    env = await setup(dut, waits=WAITS)
    addrs = slot_addrs(rng)[:6]
    for addr in addrs:
        env.master.push(Xact(addr, we=1, be=0x9, wdata=0x0BADF00D))
    await env.drain(limit=2000)
    assert env.master.rvalids == len(addrs)
    assert env.slave.transfers == len(addrs)
    assert env.mon.access_cycles == (WAITS + 1) * len(addrs), (
        "{} ACCESS cycles for {} transfers of {} wait states".format(
            env.mon.access_cycles, len(addrs), WAITS)
    )


@cocotb.test()
async def test_random_wait_states(dut):
    """A randomised mix of wait states over a long stream."""
    rng = random.Random(15)
    wrng = random.Random(16)
    env = await setup(dut, waits=lambda: wrng.randrange(0, 7), seed=17)
    addrs = slot_addrs(rng, per_slot=6)
    rng.shuffle(addrs)
    for i, addr in enumerate(addrs):
        env.master.push(Xact(addr, we=i % 2, be=rng.randrange(16),
                             wdata=rng.randrange(1 << 32)))
    await env.drain(limit=8000)
    assert env.master.rvalids == len(addrs)
    assert env.master.grants == len(addrs)
    assert env.slave.transfers == len(addrs)
    assert env.mon.setups == len(addrs)
    dut._log.info("random wait states: %d transfers, %d ACCESS cycles",
                  len(addrs), env.mon.access_cycles)


@cocotb.test()
async def test_write_payload_reaches_the_completer(dut):
    """PWRITE, PWDATA and PSTRB carry the request's we, wdata and be.

    A write request on the fabric side is an APB write: PWRITE high, the
    write data on PWDATA and the byte lanes on PSTRB, all stable from SETUP
    to the end of ACCESS (the monitor's rule 3). The patterns include the
    all-zero and all-ones lanes so a stuck or swapped lane shows up.
    """
    rng = random.Random(18)
    env = await setup(dut, waits=lambda: rng.randrange(0, 4), seed=19)
    patterns = [0x00000000, 0xFFFFFFFF, 0xAAAAAAAA, 0x55555555,
                0x0BADC0DE, 0x12345678]
    strobes = [0x0, 0xF, 0x1, 0x8, 0x3, 0xC, 0x5, 0xA]
    expect = []
    addrs = slot_addrs(rng, per_slot=3)
    for i, addr in enumerate(addrs):
        we = i % 2
        wdata = patterns[i % len(patterns)]
        be = strobes[i % len(strobes)]
        env.master.push(Xact(addr, we=we, be=be, wdata=wdata))
        expect.append((addr - APB_BASE, we, wdata, be))
    await env.drain(limit=8000)
    assert env.slave.seen == expect, (
        "completer saw {} but the fabric issued {}".format(
            env.slave.seen[:4], expect[:4])
    )


@cocotb.test()
async def test_pslverr_propagates(dut):
    """PSLVERR in the PREADY cycle becomes err_o with that transfer's rvalid.

    PSLVERR is meaningless in every other cycle and the completer drives it
    randomly there, so a bridge that sampled it outside the PREADY cycle
    would report errors on clean transfers and miss real ones. The error is
    a deterministic function of the window offset, and both erroring and
    clean transfers are interleaved.
    """
    rng = random.Random(20)

    def bad(off):
        return 1 if (off >> 12) & 1 else 0

    env = await setup(dut, waits=lambda: rng.randrange(0, 5), seed=21,
                      err_fn=bad)
    addrs = slot_addrs(rng, per_slot=4)
    n_err = sum(bad(a - APB_BASE) for a in addrs)
    assert 0 < n_err < len(addrs), (
        "the error function did not split the address set: {} of {}".format(
            n_err, len(addrs))
    )
    for i, addr in enumerate(addrs):
        env.master.push(Xact(addr, we=i % 2, wdata=rng.randrange(1 << 32)))
    await env.drain(limit=8000)
    assert env.master.rvalids == len(addrs)
    dut._log.info("pslverr: %d of %d transfers returned an error",
                  n_err, len(addrs))


@cocotb.test()
async def test_prdata_is_captured_in_the_pready_cycle(dut):
    """rdata_o is the PRDATA of the PREADY cycle and of no other cycle.

    The completer drives a fresh random word on PRDATA in every cycle in
    which PREADY is low, including the SETUP cycle and every wait state, and
    the real word only in the PREADY cycle. The per-response comparison in
    the master agent is therefore an exact statement of this rule; this test
    supplies the wait-state depths that make an early or late sample land on
    garbage.
    """
    rng = random.Random(22)
    env = await setup(dut, waits=0, seed=23)
    done = 0
    for waits in (0, 1, 2, 5, 9):
        env.slave.waits = waits
        addrs = slot_addrs(rng)[:5]
        for addr in addrs:
            env.master.push(Xact(addr))
        done += len(addrs)
        await env.drain(limit=2000)
        assert env.master.rvalids == done, (
            "{} wait states: {} rvalids for {} requests".format(
                waits, env.master.rvalids, done)
        )
    assert env.slave.transfers == done


@cocotb.test()
async def test_one_rvalid_per_request(dut):
    """Exactly one rvalid per granted request and none without one.

    Back-to-back requests with no idle cycle between them: the fabric-side
    master re-asserts req in the cycle after each grant, so the bridge is
    driven at its maximum rate. The running invariants (rvalids never ahead
    of grants, no rvalid with nothing outstanding, responses matched to
    requests in order) are in the master agent and hold every cycle; the
    totals are checked here.
    """
    rng = random.Random(24)
    env = await setup(dut, waits=lambda: rng.randrange(0, 3), seed=25)
    addrs = slot_addrs(rng, per_slot=8)
    for i, addr in enumerate(addrs):
        env.master.push(Xact(addr, we=i % 3 == 0, be=0xF,
                             wdata=rng.randrange(1 << 32)))
    await env.drain(limit=8000)
    assert env.master.grants == len(addrs)
    assert env.master.rvalids == len(addrs)
    assert env.slave.transfers == len(addrs)
    assert env.master.max_outstanding == 1, (
        "the bridge accepts one request at a time, but {} were outstanding"
        .format(env.master.max_outstanding)
    )
    # Every SETUP the monitor counted belongs to one granted request.
    assert env.mon.setups == len(addrs), (
        "{} SETUP cycles for {} requests".format(env.mon.setups, len(addrs))
    )

    # Nothing more may appear once the stream has drained.
    for cycle in range(20):
        await RisingEdge(dut.clk_i)
        await Timer(T_CHECK, unit="ns")
        assert val(dut.rvalid_o) == 0, (
            "trailing rvalid {} cycles after the last response".format(cycle))
        assert val(dut.psel_o) == 0, (
            "trailing PSEL {} cycles after the last transfer".format(cycle))
