"""Single-bit fault-injection campaign over hw/rtl/pilot_top.v.

This is the instrument the pilot's fault-tolerance claims rest on. The
pilot exists to show that upsets in a neuromorphic node are caught; this
suite is what turns "caught" into a number, per structure, so the next
hardening wave has a ranking to act on instead of an intuition.

The method is adapted from the sibling programme's campaign
(/home/hasanmelih/Documents/radhard-edge-ai: its docs/27, its
hw/tb/test_fi_campaign.py and the harness lessons recorded in its
docs/25 section 3). The method is inherited; none of its conclusions
are, because the two designs share no datapath -- that one is a
requantising MAC row behind an AXI port, this one is a time-multiplexed
LIF core behind an event queue.

Per injection:

  1. Hardware reset, then a full bring-up: STATE_CLR, the seven
     configuration registers, the four ECC-checked weight words, enable.
     Every register on the reset net is therefore clean at the start of
     every injection, and the three arrays that are deliberately NOT on
     the reset net (lif_core's vmem / rmem / wmem, docs/10 section 3) are
     rewritten by the bring-up. The two aer_fifo storage arrays are
     written by nothing at bring-up, so they get a sentinel fill.
  2. The fixed stimulus is pushed through the parallel AER input pins in
     three bursts (docs/10 section 7.1 event words). Pins, not the serial
     port: a serial frame is 170 clock cycles long, which would smear a
     one-cycle injection across the whole run, while a pin strobe places
     the event a known handful of cycles from a known edge.
  3. One bit of one named architectural flip-flop is XORed at a
     seeded-random cycle inside a measured busy window. The deposit lands
     3 ns after a clock edge; an on-edge deposit is overwritten by that
     same edge's non-blocking update before anything samples it. That is
     the sibling programme's recorded harness lesson, reproduced here
     rather than rediscovered.
  4. The rest of the stimulus runs, so masking has a chance to happen.
     Outputs are drained through the serial EVQ_OUT register -- the full
     16-bit event word plus VALID, not the four-bit AER_OUT_ID nibble, so
     a corrupted TYPE field cannot hide.
  5. The run is classified against sw/golden.

Everything the campaign OBSERVES is what a bench with an SPI master and a
logic analyser would observe: the serial register port and the five
status pins. Only the stimulus reaches into the hierarchy, which is the
rule test_pilot_top.py's FSM-upset test already states -- no pin injects
an upset, and a demonstrator that cannot be provoked in simulation is a
claim rather than a result.

Classification (exactly one class per injection, decided in this order):

  HANG       the run did not complete inside its cycle budget and nothing
             was flagged. Detected by a bounded poll of the BUSY pin, so
             a hang costs a timeout, never the suite.
  DETECTED   the design raised an error indication: STATUS.ERR_CFG,
             STATUS.DED_SEEN, STATUS.OVF_SEEN, or a nonzero CNT_DED /
             CNT_EVQ_OVF / CNT_AXON_OOR.
  SDC        the output differs from the golden model and nothing was
             flagged. The dangerous class.
  CORRECTED  the output matches the golden model and a correction counter
             moved (CNT_SEC, CNT_TMR): the upset happened, was masked,
             and still reached telemetry.
  MASKED     the output matches the golden model and nothing moved.

The golden model decides right from wrong, always. The design's own flags
only decide whether a wrong answer was announced -- they are never
allowed to declare an answer correct. Every record additionally carries
`out_ok`, so the share of DETECTED outcomes that also corrupted the
output is reportable rather than buried.

One consequence of that rule is worth stating before the numbers are
read. Since the memory hardening of 2026-08-26, lif_core corrects
single-bit upsets in wmem / vmem / rmem and reports them on four LEVEL
outputs (wmem_sec, wmem_ded, state_sec, state_ded). Until 2026-08-27
hw/rtl/pilot_top.v left all four UNCONNECTED, so those corrections
reached no counter and no pin and this classifier -- which reads only
what the chip reports -- had to call them MASKED rather than CORRECTED.
They are wired now and the same injections classify CORRECTED, which is
why the histogram moved without the design computing anything
differently. The rule that produced the earlier number is unchanged and
is the point: a correction the mission cannot see is a correction the
mission cannot report, and this campaign will keep saying MASKED until
it can see it. docs/16 section 4.1 carries both numbers.

The compared output is the whole observable result of the run: the
ordered stream of 16-bit event words drained from EVQ_OUT, and the final
neuron state file (V and R for every neuron) read back through
N_ADDR / N_DATA. State is part of the comparison because this is a
stateful design: an upset that leaves V wrong but produces no wrong spike
in an eight-command run has not been masked, it has been deferred.
`spikes_ok` and `state_ok` are recorded separately so the two can be told
apart in the report.

Three further per-record facts, because the five classes cannot carry
them:

  telemetry_ok  the counters and status pins read what a clean run of the
                same bring-up reads. False here with a correct output is a
                false alarm; false here with a primed counter is an erased
                record.
  latent        an architectural register still holds a corrupted value
                after the run, inheritable by the next command sequence
                even though this run was clean.
  e10_*         for double-bit weight-word injections, whether the
                degraded output is exactly the fail-operational zero
                substitution of docs/10 section 11.2 rather than garbage.

Sentinels (the sibling programme's aliasing lesson, adapted). Two things
could otherwise make a corrupted read look correct:

  * both aer_fifo storage arrays are pre-filled with 0xF0F0, an event word
    whose TYPE field is the reserved encoding 2'b11. A pointer upset that
    fetches an unwritten slot therefore yields something the dispatcher
    drops and the drain sees as a non-golden word, instead of aliasing a
    stale copy of a legitimate event;
  * the workload is chosen so the golden final V is distinct and nonzero
    for every neuron, so an upset that writes the right value to the wrong
    neuron cannot pass the state comparison.

Both are asserted, not assumed, in test_00_control.

Not every question this campaign has to answer is a rate. `test_04`
holds the DIRECTED cases: multi-step injections that place a fault and
then an upset in the structure that is supposed to catch it, at the one
cycle where the second one matters. Those cases exist because the two
bounded-wait counters report through a pulse that is high for one cycle
in a whole run, and a drawn phase finds that cycle essentially never --
so a rate over them would report robustness that was never tested. They
are logged in the same schema and counted in the same histogram, with a
`case` field naming the construction and a `script` field recording
every deposit including how many bits each one moved. Read docs/16
section 5.8 with them.

Reproducibility: one seed (CAMPAIGN_SEED) drives every randomised
injection cycle. Targets, bits and phase counts are an explicit curated
list -- no hierarchy scraping -- so the map reads directly as a hardening
priority list and the injection count is a constant rather than a
function of how the elaborator happens to name things.

Run:  cd hw/tb && make -f Makefile.fi
Log:  hw/tb/fi_campaign_results.json (one record per injection)
Doc:  docs/16-fault-injection-campaign.md
"""

import json
import random
import re
import sys
import time
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "sw")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from golden.lif_core import LIFConfig, LIFCore  # noqa: E402
from golden.regmap_gen import ADDR  # noqa: E402

# ---------------------------------------------------------------------
# campaign constants
# ---------------------------------------------------------------------
CAMPAIGN_SEED = 0x16F1_2026
RNG = random.Random(CAMPAIGN_SEED)

# A SECOND, independent stream for targets added after the campaign of
# record was frozen. Everything drawn from RNG must keep drawing the same
# numbers in the same order, or the 255 records docs/16 reports are not
# comparable with the run that follows them. Appending a target to
# target_list() would shift every later draw, so the groups named in
# EXT_GROUPS draw from EXT_RNG instead and the campaign of record is
# untouched: measured, the first 255 records of an extended run are
# field-for-field identical to the 255 of the unextended one.
EXT_RNG = random.Random(CAMPAIGN_SEED ^ 0xECC_0001)

# Added 2026-08-27, after the memory hardening of hw/rtl/lif_core.v. The
# hardening put 80 new flip-flops into the design -- the SECDED check
# fields wchk (8 bits per 16 weights) and smem (6 bits per neuron) -- and
# a check field is state like any other: an upset in it is an upset in
# the codeword. A protection whose own storage is unmeasured is a claim,
# which is the same mistake the configuration-TMR domain made in a
# different form, so the check fields are targets now.
#
# Extended again 2026-08-30 with the two BOUNDED-WAIT COUNTERS, for the
# same reason one step further out. `fetch_wait` and `oh_wait` (and, in
# the first version of this extension, the `fetch_timeout` /
# `oh_timeout` pulses that have since been retired -- see target_list
# item 14) exist only to convert a silent hang into a
# host-visible fault -- they were added after this campaign found a
# deadlock in D_FETCH (docs/16 section 5.1) and another in oh_req
# (section 5.7). They were then left out of the target list, so the
# structures that catch the failure class this chip exists to rule out
# were themselves unmeasured against it, and an upset that disables one
# puts the design back where it was with nothing to say so. docs/16
# section 7.3 named that as the next campaign's first item; this is it.
EXT_GROUPS = ("lif_wchk", "lif_wchk_unread", "lif_smem",
              "wdog_fetch", "wdog_oh", "evq_par")

CLK_NS = 10          # 100 MHz simulation clock, as every other suite
HALF = 20            # serial half period: SER_SCK = clk/4, the fast limit

# pilot-only registers (pilot_top.v section 5, deviation D5)
ADDR_ECC_INJ_POS = 0x0A0
ADDR_TMR_INJ = 0x0A4
ADDR_CNT_TMR = 0x0A8

ST_ERR_CFG, ST_DED_SEEN, ST_OVF_SEEN = 1 << 4, 1 << 5, 1 << 6
CTRL_EN, CTRL_STATE_CLR, CTRL_SOFT_RST, CTRL_SCRUB_EN = 1, 2, 4, 8
INJ_SINGLE, INJ_DOUBLE = 1, 2

# FAULT_CLR is deliberately not used anywhere in this file. Every
# injection starts from a hardware reset, which clears the counters, the
# stickies and FAULT_ADDR outright, so clearing them over the serial port
# would be four frames of ceremony per injection with no effect on the
# state the campaign starts from.

TYPE_SPIKE = 0 << 14

# aer_fifo storage sentinel: TYPE = 2'b11, the reserved encoding the
# dispatcher drops (pilot_top.v section 4). Distinct from every event word
# this workload can legitimately produce.
FIFO_SENTINEL = 0xF0F0

COUNTERS = ("cnt_sec", "cnt_ded", "cnt_ovf", "cnt_oor", "cnt_tmr")
PINS = ("err", "sec_seen", "ded_seen", "tmr_seen")

# ---------------------------------------------------------------------
# workload
# ---------------------------------------------------------------------
# Chosen against the golden model, not by hand, under five constraints:
# the run must emit in all three bursts (so a fault has something to
# corrupt before, during and after the injection window); no burst may
# emit more than the five-entry output path holds (so the clean run never
# backpressures and BUSY means "working", not "stalled"); the final V must
# be distinct and nonzero for every neuron (the sentinel rule); at least
# one neuron must end refractory; and several distinct neurons must spike.
# test_00_control asserts every one of them.
CFG = LIFConfig(thresh=16, v_reset=-4, leak_shift=3, syn_shift=2,
                refr_period=2, leak_en=True)

# Three bursts of AER commands. ("S", axon) is a SPIKE, ("T", None) a
# TICK. A burst is pushed back to back on the pins; the campaign waits for
# idle and drains between bursts.
BURSTS = [
    [("S", 0), ("S", 1), ("T", None)],
    [("S", 2), ("S", 3)],
    [("T", None), ("S", 1), ("T", None)],
]

# Per-geometry workload constants: the weight seed and the busy window of
# each burst in clock cycles.
#
# Both depend on the geometry and neither can be derived from it. The
# weight seed has to satisfy the five constraints above, which are a
# property of the resulting spike train and not of the matrix dimensions;
# the busy windows are how long the design takes to consume a burst, which
# scales with the neuron count. The 8 x 8 entry is the campaign of record
# and is frozen: seed 10 and (28, 19, 28) are the numbers docs/16 reports
# and the numbers hw/tb/fi_campaign_results.json was produced with.
#
# The windows are held as constants rather than measured at run time so
# the random draw consumes the same numbers on every run even if a future
# change moves the real windows by a cycle. test_00_control measures them
# anyway and fails if a constant here has grown past the real window,
# which would let a drawn delay land on an idle design.
#
# To add a geometry: find a weight seed for which test_00_control's five
# workload constraints hold (they are checked against sw/golden alone, so
# a short offline search is enough), put it here with windows of (1, 1, 1),
# run test_00_control, and copy the windows it logs.
WORKLOAD = {
    # (n_neurons, n_axons): (weight seed, busy window per burst)
    (8, 8): (10, (28, 19, 28)),
    (4, 8): (4, (18, 12, 18)),
}

# Set from WORKLOAD by campaign_setup once the elaborated geometry has
# been read back. The defaults are the campaign of record's, so a module
# imported and inspected without a simulator still describes it.
GEOMETRY = (8, 8)
WL_SEED = 10
BURST_WINDOW = (28, 19, 28)

BUSY_BUDGET = 2000      # cycles a burst may stay busy before it is a HANG
DRAIN_LIMIT = 24        # EVQ_OUT reads per burst before giving up

CLASSES = ("MASKED", "CORRECTED", "DETECTED", "SDC", "HANG")
RESULTS = []
WALL = {}


# ---------------------------------------------------------------------
# pin plumbing (pilot_top's own port list, not the Tiny Tapeout wrapper)
# ---------------------------------------------------------------------
async def clk_edges(dut, n):
    for _ in range(n):
        await RisingEdge(dut.clk)


def pin(dut, name):
    """X-safe single-bit sample of an output pin."""
    return 1 if str(getattr(dut, name).value) == "1" else 0


async def spi_byte(dut, tx):
    """One mode-0 byte, MSB first. Returns the byte shifted out on MISO."""
    rx = 0
    for i in range(7, -1, -1):
        dut.ser_mosi.value = (tx >> i) & 1
        await Timer(HALF, unit="ns")
        dut.ser_sck.value = 1
        await Timer(1, unit="ns")
        rx = (rx << 1) | pin(dut, "ser_miso")
        await Timer(HALF - 1, unit="ns")
        dut.ser_sck.value = 0
    return rx


async def frame(dut, write, addr, data=0):
    """One 40-bit serial frame: command byte, then 32 data bits.

    The chip-select setup and the inter-frame gap are both one full
    SER_SCK period, the documented minimum of pilot_top.v section 2.
    """
    dut.ser_cs_n.value = 0
    await Timer(2 * HALF, unit="ns")
    await spi_byte(dut, ((1 if write else 0) << 7) | ((addr >> 2) & 0x7F))
    out = 0
    for shift in (24, 16, 8, 0):
        out = (out << 8) | await spi_byte(dut, (data >> shift) & 0xFF)
    await Timer(HALF, unit="ns")
    dut.ser_cs_n.value = 1
    await Timer(2 * HALF, unit="ns")
    return out


async def wr(dut, addr, data):
    await frame(dut, True, addr, data)


async def rd(dut, addr):
    return await frame(dut, False, addr)


async def hard_reset(dut):
    """Assert rst_n, release it, leave the clock running.

    Costs no serial frames and clears everything on the reset net: every
    configuration register, every counter, every sticky bit, the three TMR
    replicas, both queue pointer pairs and lif_core's control state. It
    deliberately does NOT clear lif_core's vmem / rmem / wmem (docs/10
    section 3 keeps them off the reset net) or the two aer_fifo storage
    arrays; the bring-up rewrites the first three and the sentinel fill
    covers the last two.
    """
    dut.rst_n.value = 0
    await clk_edges(dut, 5)
    dut.rst_n.value = 1
    await clk_edges(dut, 5)


async def pin_event(dut, kind, axon):
    """Push one AER command through the parallel input pins.

    The strobe is edge triggered behind a two-flop synchronizer, so it is
    held for two cycles and released for two, and the address and the TICK
    select are placed two cycles ahead of the rising edge -- the minimum
    the synchronizer depth allows. Six cycles per command, against roughly
    twelve to consume one, is what keeps a burst a burst: the input queue
    actually holds entries while the injection lands, which is the only
    condition under which an upset in queue storage or a queue pointer
    means anything.
    """
    dut.aer_in_tick.value = 1 if kind == "T" else 0
    dut.aer_in_addr.value = (axon or 0) & 0xF
    await clk_edges(dut, 2)
    dut.aer_in_stb.value = 1
    await clk_edges(dut, 2)
    dut.aer_in_stb.value = 0
    await clk_edges(dut, 2)


async def pulse_scrub(dut):
    """One rising edge on the SCRUB_STB pin: the ECC re-check request."""
    await clk_edges(dut, 2)
    dut.scrub_stb.value = 1
    await clk_edges(dut, 3)
    dut.scrub_stb.value = 0
    await clk_edges(dut, 3)


async def wait_idle(dut, budget=BUSY_BUDGET):
    """Poll the BUSY pin for at most `budget` cycles. Never blocks."""
    for _ in range(budget):
        if not pin(dut, "busy"):
            return True
        await RisingEdge(dut.clk)
    return False


async def drain(dut, limit=DRAIN_LIMIT):
    """Pop every presented EVQ_OUT word. Full 16-bit words, bounded."""
    words = []
    for _ in range(limit):
        word = await rd(dut, ADDR["EVQ_OUT"])
        if not word & (1 << 31):
            return words
        words.append(word & 0xFFFF)
    return words


# ---------------------------------------------------------------------
# hierarchy access (stimulus only)
# ---------------------------------------------------------------------
_IDX = re.compile(r"^([^\[]+)\[(\d+)\]$")


def resolve(dut, path):
    """Resolve a dotted hierarchical path, with [n] for memory words."""
    h = dut
    for part in path.split("."):
        m = _IDX.match(part)
        h = getattr(h, m.group(1))[int(m.group(2))] if m else getattr(h, part)
    return h


# Names the target list and the directed scripts still carry, and which
# the design deliberately no longer has. Nothing else may go missing: a
# target that stops resolving is otherwise a hard error, because a
# campaign that quietly shrinks reports a fault tolerance it did not
# measure (target_list item 9 records what that cost once already).
#
# `fetch_timeout` and `oh_timeout` were the one-cycle report pulses of
# the two bounded waits. pilot_top.v header section 8.1 retired them on
# 2026-08-30 -- the expiry terms are wires now, and the same wire ends
# the wait and latches sticky_errcfg on one edge -- so there is no
# storage at those names to deposit into. They stay listed, and they
# stay drawn for, for two reasons: removing an entry from target_list
# would move every injection phase drawn after it and make the surviving
# records incomparable with the run that measured the defect, and a
# resolvable name here is exactly how the campaign notices the pulse
# registers coming back.
RETIRED_TARGETS = ("fetch_timeout", "oh_timeout")


# The dual-rail valid flags of hw/rtl/pilot_top.v section 8.2 and its two
# copies, by the instance names of their rails. A target that matches is
# a rail's own storage; the checked wire the consumer reads is not a
# target and must never become one (test_05 asserts both).
_RAIL_INSTANCES = ("u_ohv_", "u_rdv_", "u_op_")


def _is_rail(target):
    return any(n in str(target) for n in _RAIL_INSTANCES)


def state_present(dut, path):
    """True when `path` still names something a deposit can land in."""
    try:
        resolve(dut, path)
    except (AttributeError, IndexError, KeyError):
        return False
    return True


def read_defined(handle, path):
    """int(handle) with a message that names the path when it is X.

    Every target this campaign deposits into is written by the bring-up or
    by the sentinel fill, so an X here means the bring-up missed
    something, which must fail loudly rather than be XORed away.
    """
    s = str(handle.value)
    if any(c not in "01" for c in s):
        raise AssertionError(f"{path} is not fully defined ({s}); the "
                             "bring-up does not cover this target")
    return int(s, 2)


def xor_now(dut, path, bits):
    """XOR one or more bits into a flip-flop at the current sim time.

    The caller is responsible for standing 3 ns past a clock edge; see
    `deposit`. Returns the deposited value.
    """
    h = resolve(dut, path)
    v = read_defined(h, path)
    for b in (bits if isinstance(bits, tuple) else (bits,)):
        v ^= 1 << b
    h.value = v
    return v


def force_now(dut, path, value):
    """Write an absolute value into a flip-flop at the current sim time.

    Used ONLY by the directed watchdog cases of test_04, and deliberately
    reported as what it is. `xor_now` with one bit is a single-event
    upset; this is not necessarily one. Clearing a 6-bit counter that
    holds 20, or driving it to its 6-bit maximum, takes as many bit flips
    as the two values differ in, and the returned popcount is recorded in
    the log so no reader has to take "an upset cleared the counter" on
    trust. Some of those cases are outside the single-bit fault model of
    docs/16 section 7.4 and section 5.8 says which ones.
    """
    h = resolve(dut, path)
    old = read_defined(h, path)
    h.value = value
    return bin(old ^ value).count("1")


async def deposit(dut, path, bits):
    """XOR one or more bits into a flip-flop, 3 ns after a clock edge.

    Off the edge on purpose: a deposit made at the edge is overwritten by
    that same edge's non-blocking update before anything samples it, so
    the injection would silently do nothing. Recorded harness lesson from
    the sibling programme (its docs/25 section 3).
    """
    await RisingEdge(dut.clk)
    await Timer(3, unit="ns")
    xor_now(dut, path, bits)


async def fill_fifo_sentinel(dut):
    """Pre-load both aer_fifo storage arrays with the reserved-TYPE word."""
    await RisingEdge(dut.clk)
    await Timer(3, unit="ns")
    for i in range(len(dut.u_evq_in.mem)):
        dut.u_evq_in.mem[i].value = FIFO_SENTINEL
    for i in range(len(dut.u_evq_out.mem)):
        dut.u_evq_out.mem[i].value = FIFO_SENTINEL


# ---------------------------------------------------------------------
# golden model plumbing
# ---------------------------------------------------------------------
def make_weights(n_axons, n_neurons, seed=None):
    # The default is read at call time, not bound at definition time:
    # campaign_setup selects it from WORKLOAD once it knows the geometry.
    rng = random.Random(WL_SEED if seed is None else seed)
    return [[rng.randint(-8, 7) for _ in range(n_neurons)]
            for _ in range(n_axons)]


def pack_words(weights):
    """weights[axon][neuron] -> 64-bit ECC data words (docs/10 section 5)."""
    flat = [w for row in weights for w in row]
    words = []
    for base in range(0, len(flat), 16):
        word = 0
        for k, w in enumerate(flat[base:base + 16]):
            word |= (w & 0xF) << (4 * k)
        words.append(word)
    return words


def golden_run(n_neurons, n_axons, weights, poison_word=None):
    """Reference result of the campaign stimulus.

    Returns (per-burst event-word lists, [(V, R)] final state). The event
    words are what EVQ_OUT presents: {TYPE = 2'b00, 4'b0, ID[9:0]} with
    PASS_TILE_OFF = 0, so the word equals the emitted neuron id.
    """
    core = LIFCore(n_neurons, n_axons, weights, CFG)
    if poison_word is not None:
        core.poison_word(poison_word)
    per_burst = []
    for burst in BURSTS:
        spikes = []
        for kind, axon in burst:
            if kind == "S":
                spikes.extend(core.synaptic_event(axon))
            else:
                core.tick()
        per_burst.append([TYPE_SPIKE | s for s in spikes])
    return per_burst, [core.get_state(j) for j in range(n_neurons)]


# ---------------------------------------------------------------------
# bring-up, run, observe, classify
# ---------------------------------------------------------------------
async def bring_up(dut, words, ecc_inj=None, scrub_en=False):
    """Reset, clear state, configure, load weights, enable.

    ecc_inj, when given, is (word_index, position, INJ_SINGLE|INJ_DOUBLE):
    the design's own ECC injection port arms one corrupted codeword at the
    instant that word is committed, which is the only way to corrupt a
    weight word before the loader copies it into lif_core.
    """
    await hard_reset(dut)
    await fill_fifo_sentinel(dut)

    await wr(dut, ADDR["CTRL"], CTRL_STATE_CLR)
    await wr(dut, ADDR["CFG_THRESH"], CFG.thresh & 0xFFFF)
    await wr(dut, ADDR["CFG_VRESET"], CFG.v_reset & 0xFFFF)
    await wr(dut, ADDR["CFG_LEAK"], CFG.leak_shift)
    await wr(dut, ADDR["CFG_SYNSHIFT"], CFG.syn_shift)
    await wr(dut, ADDR["CFG_REFR"], CFG.refr_period)
    await wr(dut, ADDR["CFG_FLAGS"], 2 if CFG.leak_en else 0)
    await wr(dut, ADDR["PASS_TILE_OFF"], 0)

    await wr(dut, ADDR["W_ADDR"], 0)
    for wi, word in enumerate(words):
        if ecc_inj is not None and ecc_inj[0] == wi:
            await wr(dut, ADDR_ECC_INJ_POS, ecc_inj[1])
            await wr(dut, ADDR["ECC_INJ"], ecc_inj[2])
        await wr(dut, ADDR["W_DATA_LO"], word & 0xFFFF_FFFF)
        await wr(dut, ADDR["W_DATA_HI"], (word >> 32) & 0xFFFF_FFFF)

    await wr(dut, ADDR["CTRL"], CTRL_EN | (CTRL_SCRUB_EN if scrub_en else 0))
    assert not pin(dut, "busy"), "the bring-up left the pilot busy"


async def inject_after_busy(dut, path, bits, delay):
    """Wait for BUSY, count `delay` cycles, deposit. Bounded."""
    for _ in range(BUSY_BUDGET):
        await RisingEdge(dut.clk)
        # Sample one nanosecond past the edge: at the RisingEdge callback
        # busy still reads its pre-update value, which would place the
        # whole injection window one cycle late and make the first busy
        # cycle unreachable.
        await Timer(1, unit="ns")
        if pin(dut, "busy"):
            break
    else:
        raise AssertionError("BUSY never rose after the first burst event")
    await clk_edges(dut, delay)
    await deposit(dut, path, bits)


async def run_script(dut, steps):
    """A multi-step directed injection inside one burst's busy window.

    The random campaign draws ONE deposit at ONE drawn cycle, which is
    the right instrument for measuring a rate and the wrong one for
    asking whether a safety net survives the fault it exists to catch.
    That question needs two deposits placed against each other -- the
    fault, and then the upset in the net at the one cycle where it
    matters -- and the second of the two is a single cycle in a 63-cycle
    window, which a drawn delay would find roughly never. So the
    directed cases construct it.

    Steps, executed in order, each standing 3 ns past a clock edge:

      ("wait", n)                  advance n clock cycles
      ("xor", path, bits)          a genuine single-event deposit
      ("xor?", path, bits)         the same, into a RETIRED_TARGETS name:
                                   deposited if the design still has that
                                   state, and otherwise logged as "no
                                   state" and skipped. This is what makes
                                   a report case measure the repair of
                                   section 8.1 rather than assume it --
                                   the same script reproduces the erased
                                   report on a design that still has the
                                   pulse register, and records that there
                                   is nothing to erase on one that does
                                   not
      ("force", path, value)       an absolute write; the popcount of the
                                   change is logged, because it is not
                                   necessarily one bit
      ("until", path, value, n)    advance until the named flop reads
                                   `value`, at most n cycles. This is an
                                   OBSERVATION of internal state used to
                                   PLACE a deposit, not to classify one:
                                   nothing in the record depends on it
                                   except where the deposit landed.

    Returns the log, including whether every `until` found its cycle.
    """
    for _ in range(BUSY_BUDGET):
        await RisingEdge(dut.clk)
        await Timer(3, unit="ns")
        if pin(dut, "busy"):
            break
    else:
        raise AssertionError("BUSY never rose for a directed injection")

    log = []
    for step in steps:
        kind = step[0]
        if kind == "wait":
            for _ in range(step[1]):
                await RisingEdge(dut.clk)
                await Timer(3, unit="ns")
            log.append(f"wait {step[1]}")
        elif kind == "xor":
            v = xor_now(dut, step[1], step[2])
            log.append(f"xor {step[1]} bit {step[2]} -> {v}")
        elif kind == "xor?":
            assert step[1] in RETIRED_TARGETS, \
                f"'xor?' is only for a declared retirement, not {step[1]}"
            if state_present(dut, step[1]):
                v = xor_now(dut, step[1], step[2])
                log.append(f"xor {step[1]} bit {step[2]} -> {v}")
            else:
                log.append(f"NO SUCH STATE {step[1]}")
        elif kind == "force":
            n = force_now(dut, step[1], step[2])
            log.append(f"force {step[1]} = {step[2]} ({n} bit(s) flipped)")
        elif kind == "until":
            _, path, want, budget = step
            hit = False
            for _ in range(budget + 1):
                if read_defined(resolve(dut, path), path) == want:
                    hit = True
                    break
                await RisingEdge(dut.clk)
                await Timer(3, unit="ns")
            log.append(f"until {path} == {want}: {'hit' if hit else 'MISSED'}")
            if not hit:
                log.append("NOT CONSTRUCTED")
        else:
            raise AssertionError(f"unknown directed step {step}")
    return log


async def run_stimulus(dut, inj_burst=None, path=None, bits=None, delay=0,
                       script=None, script_log=None):
    """Push the three bursts, injecting inside `inj_burst`'s busy window.

    Returns (completed, drained event words). `completed` is False when a
    burst never went idle inside its budget; the remaining bursts are then
    skipped, because pushing more events into a stalled pilot only
    overflows the input queue and would relabel a hang as a detection.
    """
    words = []
    for b, burst in enumerate(BURSTS):
        injector = None
        if b == inj_burst:
            injector = cocotb.start_soon(
                run_script(dut, script) if script is not None
                else inject_after_busy(dut, path, bits, delay))
        for kind, axon in burst:
            await pin_event(dut, kind, axon)
        if injector is not None:
            got_log = await injector
            if script_log is not None and got_log:
                script_log.extend(got_log)
        ok = await wait_idle(dut)
        words.extend(await drain(dut))
        if not ok:
            return False, words
    return True, words


async def measure_window(dut, burst, quiet=8):
    """Cycles from the first BUSY rise of a burst to the last BUSY fall.

    Measured concurrently with the pushes, because a burst is pushed while
    the first of its commands is still being consumed and BUSY can dip for
    a cycle between two commands. The span, not the longest unbroken high
    stretch, is what an injection delay is drawn from: an upset does not
    wait for the design to be busy, and a delay that lands in a one-cycle
    dip is a legitimate sample.
    """
    span = {"n": 0}

    async def monitor():
        for _ in range(BUSY_BUDGET):
            await RisingEdge(dut.clk)
            await Timer(1, unit="ns")
            if pin(dut, "busy"):
                break
        else:
            raise AssertionError("BUSY never rose while measuring a burst")
        n, low = 0, 0
        while low < quiet and n < BUSY_BUDGET:
            await RisingEdge(dut.clk)
            await Timer(1, unit="ns")
            n += 1
            low = 0 if pin(dut, "busy") else low + 1
        span["n"] = n - low

    task = cocotb.start_soon(monitor())
    for kind, axon in burst:
        await pin_event(dut, kind, axon)
    await task
    await drain(dut)
    return span["n"]


async def read_observations(dut, n_neurons, completed):
    """Everything a bench can see, in the order a bench must read it.

    STATUS and the counters first. They survive CTRL.SOFT_RST -- they sit
    on the hardware reset net, not on the block reset -- but reading them
    before the recovery keeps the record of what the pilot reported while
    the fault was still live. The state file needs N_ADDR, which is in the
    configuration-lock set, so a pilot parked with BUSY high has to be
    un-parked first. SOFT_RST is the documented recovery for exactly that
    fault and it keeps the neuron state file, which is not on the block
    reset net either.
    """
    obs = {
        "status": await rd(dut, ADDR["STATUS"]),
        "cnt_sec": await rd(dut, ADDR["CNT_SEC"]),
        "cnt_ded": await rd(dut, ADDR["CNT_DED"]),
        "cnt_ovf": await rd(dut, ADDR["CNT_EVQ_OVF"]),
        "cnt_oor": await rd(dut, ADDR["CNT_AXON_OOR"]),
        "cnt_tmr": await rd(dut, ADDR_CNT_TMR),
        "pins": {n: pin(dut, n) for n in PINS},
    }
    if not completed:
        await wr(dut, ADDR["CTRL"], CTRL_SOFT_RST)
        await wait_idle(dut, 200)
    state = []
    for j in range(n_neurons):
        await wr(dut, ADDR["N_ADDR"], j)
        word = await rd(dut, ADDR["N_DATA"])
        v = word & 0xFFFF
        state.append((v - 0x10000 if v >= 0x8000 else v, (word >> 16) & 0xF))
    obs["state"] = state
    return obs


def classify(completed, obs, out_ok):
    detected = bool(obs["status"] & (ST_ERR_CFG | ST_DED_SEEN | ST_OVF_SEEN)
                    or obs["cnt_ded"] or obs["cnt_ovf"] or obs["cnt_oor"])
    corrected = bool(obs["cnt_sec"] or obs["cnt_tmr"])
    if not completed and not detected:
        return "HANG"
    if detected:
        return "DETECTED"
    if not out_ok:
        return "SDC"
    if corrected:
        return "CORRECTED"
    return "MASKED"


async def injection(dut, geo, group, target, bits, burst, delay,
                    ecc_inj=None, scrub=False, poison_word=None,
                    expect_tel=None, latent_regs=(), script=None):
    """One complete injection: bring-up, stimulus, observation, class.

    target None means the fault is delivered by the design's own ECC
    injection port during the bring-up instead of by a flip-flop deposit.
    latent_regs is a list of (name, address, expected value) read back
    after the run to record corruption this run masked but the next
    command sequence would inherit.
    """
    n_neurons, n_axons, weights, words = geo
    exp_bursts, exp_state = golden_run(n_neurons, n_axons, weights)
    exp_events = [w for b in exp_bursts for w in b]

    await bring_up(dut, words, ecc_inj=ecc_inj, scrub_en=scrub)
    extra = {}
    if script is not None:
        slog = []
        completed, got = await run_stimulus(dut, burst, script=script,
                                            script_log=slog)
        extra["script"] = slog
        extra["constructed"] = "NOT CONSTRUCTED" not in slog
    elif target is None:
        completed, got = await run_stimulus(dut)
    else:
        completed, got = await run_stimulus(dut, burst, target, bits, delay)

    if scrub:
        # The design's re-check request. With CTRL.SCRUB_EN set a
        # correctable stored word is repaired in place, so the readback
        # says whether the scrubber loop actually closed.
        await pulse_scrub(dut)
        lo = await rd(dut, ADDR["W_DATA_LO"])
        hi = await rd(dut, ADDR["W_DATA_HI"])
        extra["stored_repaired"] = ((hi << 32) | lo) == words[-1]

    latent = {}
    for name, addr, want in latent_regs:
        latent[name] = (await rd(dut, addr)) != want
    if latent_regs:
        extra["latent"] = any(latent.values())
        extra["latent_regs"] = latent

    obs = await read_observations(dut, n_neurons, completed)

    spikes_ok = got == exp_events
    state_ok = [tuple(s) for s in obs["state"]] == exp_state
    cls = classify(completed, obs, spikes_ok and state_ok)

    want_tel = {k: 0 for k in COUNTERS}
    want_tel.update(expect_tel or {})
    tel = {k: obs[k] for k in COUNTERS}
    extra["telemetry_ok"] = tel == want_tel
    if poison_word is not None:
        e10_bursts, e10_state = golden_run(n_neurons, n_axons, weights,
                                           poison_word=poison_word)
        extra["e10_events_ok"] = got == [w for b in e10_bursts for w in b]
        extra["e10_state_ok"] = \
            [tuple(s) for s in obs["state"]] == e10_state

    rec = {
        "group": group, "target": target,
        "bit": list(bits) if isinstance(bits, tuple) else bits,
        "burst": burst, "delay": delay, "class": cls,
        "completed": completed,
        "out_ok": spikes_ok and state_ok,
        "spikes_ok": spikes_ok, "state_ok": state_ok,
        "status": obs["status"], "counters": tel, "pins": obs["pins"],
        "got_events": got, "exp_events": exp_events,
        "state": [list(s) for s in obs["state"]],
    }
    rec.update(extra)
    RESULTS.append(rec)
    return rec


def phases(n, pin_first=True, rng=None):
    """Seeded injection phases as (burst, delay) pairs.

    With pin_first, phase 0 is pinned to the first busy cycle of the first
    burst, which is the only cycle several one-cycle-live signals are
    reachable at. Queue storage and pointers use pin_first=False: at the
    first busy cycle only one event has been written, so a pinned phase
    would deposit into slots the burst is about to overwrite.

    `rng` selects the stream. The default is the campaign of record's;
    EXT_GROUPS draw from EXT_RNG so that adding a target cannot move the
    phases of the targets that were measured before it.
    """
    rng = RNG if rng is None else rng
    out = [(0, 0)] if pin_first else []
    while len(out) < n:
        b = rng.randrange(len(BURSTS))
        out.append((b, rng.randrange(BURST_WINDOW[b])))
    return out[:n]


# ---------------------------------------------------------------------
# target list
# ---------------------------------------------------------------------
def spread(count, k):
    """k evenly spread indices of a `count`-entry array."""
    if count <= k or k < 2:
        return list(range(min(count, max(k, 1))))
    return sorted({(i * (count - 1)) // (k - 1) for i in range(k)})


def target_list(n_neurons, n_axons, q_depth):
    """(group, path, bits, phases, pin_first) built from the geometry.

    An explicit curated list, not a hierarchy scrape: every entry is a
    named architectural register, so the resulting map reads directly as a
    hardening priority list and the injection count is a constant rather
    than a function of how the elaborator names things. Wide registers are
    sampled at low / mid / high bit positions rather than exhaustively.
    """
    nb = max(1, (n_neurons - 1).bit_length())          # NEUR_W
    ab = max(1, (n_axons - 1).bit_length())            # AXON_W
    wb = max(1, ab + nb - 4)                           # WORD_W
    syn = n_axons * n_neurons
    ptr = list(range((q_depth - 1).bit_length() + 1))  # aer_fifo AW+1

    t = []

    # 1. lif_core FSM state register (docs/10 section 11.4). The five legal
    #    encodings are the even-parity words of a 4-bit vector, so every
    #    single-bit upset is guaranteed to land on an illegal word and must
    #    park the core in S_SAFE with err_cfg raised.
    t += [("lif_fsm", "u_lif.state", [0, 1, 2, 3], 3, True)]

    # 2. membrane potential array: an unprotected flip-flop file, 16 bits
    #    per neuron. Second in size only to the synapse file below, and
    #    unlike it, live state rather than a reloadable image.
    t += [("lif_vmem", f"u_lif.vmem[{j}]", [0, 4, 11, 15], 2, True)
          for j in spread(n_neurons, 3)]

    # 3. refractory counters: the other half of the neuron state file.
    t += [("lif_rmem", f"u_lif.rmem[{j}]", [0, 1, 3], 2, True)
          for j in spread(n_neurons, 2)]

    # 4. synapse weight storage as the datapath sees it: lif_core's
    #    flip-flop synapse file. It is NOT ECC protected in the pilot
    #    (lif_core.v header: Candidate A storage class, no SRAM macro,
    #    therefore no ECC path). test_02 covers the ECC-protected staging
    #    word that feeds it.
    #
    #    The sampled indices are deliberately split. The stimulus drives
    #    only the low axons, so only part of the crossbar is read during a
    #    run; sampling evenly across the whole synapse file would report a
    #    masking rate that is really a statement about the workload. Four
    #    indices are drawn from the rows the workload actually reads, and
    #    one from a row it never reads -- that one is a control and must
    #    come back MASKED.
    used = max(a for b in BURSTS for k, a in b if k == "S") + 1
    live = used * n_neurons
    t += [("lif_wmem", f"u_lif.wmem[{i}]", [0, 3], 2, True)
          for i in spread(live, 4)]
    t += [("lif_wmem_unread", f"u_lif.wmem[{(live + syn) // 2}]",
           [0, 3], 2, True)]

    # 5. scan and emission state: the small routing registers the sibling
    #    programme found dominate SDC rate rather than fault magnitude.
    #    Whether that carries over to a LIF scan is a question this
    #    campaign is here to answer, not to assume.
    #
    #    `out_pend` is TWO RAILS since 2026-08-30 (hw/rtl/lif_core.v
    #    header section OUTPUT FLAG RAILS), so the injector is
    #    retargeted onto the rails' storage for the same reason item 9
    #    retargeted the pointers: a deposit into the CHECKED wire
    #    measures a node nothing claims to protect. The two rails share
    #    each drawn phase and are injected one at a time, so no phase
    #    moves and only this target's own records do, 3 to 6.
    t += [("lif_scan", "u_lif.jj", list(range(nb)), 2, True),
          ("lif_scan", "u_lif.ev_axon_r", list(range(ab)), 2, True),
          ("lif_scan", ("u_lif.u_op_a.bits", "u_lif.u_op_b.bits"),
           [0], 3, True),
          ("lif_scan", "u_lif.out_event", [0, 2, 14], 2, True)]

    # 6. configuration TMR replicas (pilot_top.v section 4), one bit per
    #    voted field: THETA low, THETA high, V_RESET, S_LEAK, CFG_FLAGS.
    #    A real replica-flop deposit, not the TMR_INJ read-path emulation,
    #    because only a flop deposit tests what an upset does to the
    #    stored replica -- including the fact that nothing resynchronizes
    #    it afterwards.
    #
    #    The target is the bank's storage register `bits`, not its output
    #    `q` (the `cfg_a/b/c` wires in pilot_top): since 2026-08-26 the
    #    replicas are pilot_cfg_bank instances (pilot_top.v header section
    #    9), so `cfg_a` is a continuously driven net and a deposit on it
    #    models an upset at the voter input, not in the flip-flop. Icarus
    #    happens to let such a deposit persist until the driver
    #    re-evaluates, so both spellings classify the same here, but only
    #    this one is a flop deposit and only this one is portable.
    #
    #    Bit positions are unchanged by the move. Each bank stores
    #    `value ^ POL` and presents `bits ^ POL`, and XOR with a constant
    #    is bit-wise, so flipping bit i of `bits` still flips exactly bit
    #    i of the value the voter sees.
    t += [(f"cfg_tmr_{r}", f"u_cfg_{r}.bits", [0, 12, 16, 32, 43], 1, True)
          for r in ("a", "b", "c")]

    # 7. register-bank configuration registers outside the TMR domain.
    t += [("regbank_cfg", "cfg_axon", [0, 3], 2, True),
          ("regbank_cfg", "ctrl_en", [0], 2, True),
          ("regbank_cfg", "ctrl_scrub_en", [0], 1, True),
          ("regbank_cfg", "node_id", [0], 1, True),
          ("regbank_cfg", "n_addr", [0], 1, True),
          ("regbank_cfg", "w_addr", list(range(wb)), 1, True),
          ("regbank_cfg", "scratch", [0, 31], 1, True),
          ("regbank_cfg", "ecc_inj_pos", [0], 1, True),
          ("regbank_cfg", "tmr_inj", [0, 8], 1, True)]

    # 8. fault counters and sticky status bits: the telemetry the mission
    #    reads. An upset here does not corrupt an inference, it corrupts
    #    the record of what happened -- which for a chip built to measure
    #    upset rates is the product.
    t += [("regbank_cnt", "cnt_sec", [0, 7], 1, True),
          ("regbank_cnt", "cnt_ded", [0, 7], 1, True),
          ("regbank_cnt", "cnt_oor", [0, 7], 1, True),
          ("regbank_cnt", "cnt_tmr", [0, 7], 1, True),
          ("regbank_cnt", "fault_addr", list(range(wb)), 1, True),
          ("regbank_cnt", "u_evq_in.drop_cnt", [0, 7], 1, True),
          ("regbank_cnt", "sticky_errcfg", [0], 1, True),
          ("regbank_cnt", "sticky_ded", [0], 1, True),
          ("regbank_cnt", "sticky_ovf", [0], 1, True),
          ("regbank_cnt", "sticky_sec", [0], 1, True),
          ("regbank_cnt", "sticky_tmr", [0], 1, True),
          ("regbank_cnt", "sticky_sync", [0], 1, True)]

    # 9. AER queue pointers, both queues. Each pointer carries one extra
    #    wrap bit, so the whole width is walked rather than sampled.
    #
    #    The target is the REPLICA STORAGE, `u_{w,r}ptr_{a,b,c}.bits`, and
    #    one deposit lands in one replica: that, and only that, is a
    #    single-event upset in a pointer. Until 2026-08-29 this group
    #    named `{u_evq_in,u_evq_out}.{wr,rd}_ptr`, which since the pointer
    #    TMR of hw/rtl/aer_fifo.v is the VOTED wire rather than storage --
    #    the same trap the configuration TMR hit on 2026-08-26 and for the
    #    same reason (item 6 above). Two things were wrong with it, not
    #    one:
    #
    #      * it is not a flip-flop, so no physical upset corresponds to
    #        the deposit; and
    #      * Icarus holds a deposit on a driven net until the driver
    #        RE-EVALUATES, and the voter's inputs stop changing as soon as
    #        the pointer stops moving, so the deposit persisted for the
    #        rest of the run. It modelled a permanent stuck-at on the
    #        voter output node, not a transient at the voter input.
    #
    #    That is why the group kept reporting its pre-TMR result -- 23 SDC
    #    and 1 HANG of 24 on 2026-08-29 [fact] -- against three replicas
    #    and a majority vote. It was a measurement of a node nothing
    #    claims to protect. Retargeted, the same 24 phases classify 72
    #    injections and the campaign pass criteria in test_04 require
    #    every one of them to be CORRECTED.
    #
    #    The three replicas are injected AT THE SAME DRAWN PHASES rather
    #    than drawing their own, so `phases()` still consumes exactly the
    #    numbers it consumed before this change and the groups drawn after
    #    this one -- evq_mem, evq_hold, dispatch -- keep the phases docs/16
    #    reports. Only the pointer group's own records move.
    #
    #    Bit positions are per replica, not per pointer. Banks A and B
    #    store the pointer and its complement, so bit i of `bits` is bit i
    #    of the pointer; bank C stores an XOR mixing, so bit i of `bits`
    #    decodes to two or three wrong pointer bits (aer_fifo.v,
    #    aer_ptr_bank header). Both are single-replica faults and a
    #    bitwise majority masks each of them, which is the point of the
    #    mixing rather than a weakness of it.
    t += [("evq_ptr",
           tuple(f"{q}.u_{p}ptr_{r}.bits" for r in ("a", "b", "c")),
           ptr, 2, False)
          for q in ("u_evq_in", "u_evq_out") for p in ("w", "r")]

    # 10. AER queue storage, every slot of both queues.
    t += [("evq_mem", f"{q}.mem[{i}]", [0, 14], 2, False)
          for q in ("u_evq_in", "u_evq_out") for i in range(q_depth)]

    # 11. the EVQ_OUT show-ahead adapter (pilot_top.v section 8) and the
    #     queue's own registered read port.
    #
    #     `oh_valid` is TWO RAILS since 2026-08-30 (pilot_top.v header
    #     section 8.2), so the injector is retargeted onto the rails'
    #     storage exactly as item 9 retargeted the pointer group: a
    #     deposit into the voted or checked WIRE measures a node nothing
    #     claims to protect, and that mistake cost this campaign a day
    #     of wrong numbers once already. The two rails share one drawn
    #     phase and are injected one at a time, so `phases()` consumes
    #     the same numbers it consumed before and no group drawn after
    #     this one moves; only `oh_valid`'s own records do, from 2 to 4.
    #     Bit 0 is the flag in both rails -- pilot_flag_rail stores the
    #     complement in rail B, so the DEPOSIT is still one bit and the
    #     rails still disagree afterwards, which is the whole mechanism.
    t += [("evq_hold", ("u_ohv_a.bits", "u_ohv_b.bits"), [0], 2, True),
          ("evq_hold", "oh_req", [0], 2, True),
          ("evq_hold", "oh_data", [0, 2, 14], 2, True),
          ("evq_hold",
           ("u_evq_out.u_rdv_a.bits", "u_evq_out.u_rdv_b.bits"),
           [0], 2, True),
          ("evq_hold", "u_evq_out.rd_data", [0, 14], 1, False)]

    # 12. event dispatcher. dstate gets five phases rather than two
    #     because its outcome depends entirely on which state the upset
    #     lands in: D_IDLE and D_ISSUE both have a one-bit neighbour that
    #     is D_FETCH, and D_FETCH has no exit but a queue read that was
    #     never requested. Two samples per bit would put a wide error bar
    #     on the only structure in the design that can deadlock.
    t += [("dispatch", "dstate", [0, 1], 5, True),
          ("dispatch", "evw", [0, 2, 14, 15], 2, True)]

    # 13. The SECDED CHECK FIELDS of the coded memory files. Added
    #     2026-08-27, after the hardening of hw/rtl/lif_core.v; they draw
    #     from EXT_RNG so the twelve groups above keep the phases docs/16
    #     reports.
    #
    #     A check field is storage, and hardening pays for it in
    #     flip-flops: +32 for wchk (8 SECDED check bits per 16 weights)
    #     and +48 for smem (6 bits per neuron state word) at 8 x 8. If an
    #     upset in one of those 80 bits could corrupt an inference the
    #     protection would be importing the risk it removes, so the
    #     question has to be asked with a deposit rather than answered
    #     with an argument -- the code is systematic and a single-bit
    #     error in the check field is a single-bit error in the codeword,
    #     but that is a property of the code, not evidence about this
    #     instantiation of it.
    #
    #     `wchk` and `smem` are flat packed vectors (lif_core.v header
    #     section 5), so the bit index is global: check bit b of weight
    #     codeword w is wchk[w*8 + b], and check bit b of neuron j is
    #     smem[j*6 + b].
    wpw, st_c = 16, 6
    n_wword = (syn + wpw - 1) // wpw
    live_wword = (live + wpw - 1) // wpw
    t += [("lif_wchk", "u_lif.wchk", [w * 8 + b for b in (0, 3, 7)], 2, True)
          for w in range(live_wword)]
    # The same control the wmem group carries, for the same reason: a
    # codeword the workload never reads must come back MASKED, or the
    # lif_wchk rate would be a statement about the stimulus.
    if n_wword > live_wword:
        t += [("lif_wchk_unread", "u_lif.wchk", [(n_wword - 1) * 8], 2, True)]
    t += [("lif_smem", "u_lif.smem", [j * st_c + b for b in (0, 2, 5)],
           2, True)
          for j in spread(n_neurons, 3)]

    # 14. THE TWO BOUNDED-WAIT COUNTERS -- the safety nets themselves.
    #     Added 2026-08-30; docs/16 section 7.3 named them as the next
    #     campaign's first item and this is that item. They draw from
    #     EXT_RNG (EXT_GROUPS above) and are appended AFTER item 13, so
    #     every phase drawn by the twelve groups of the campaign of
    #     record and by the three check-field groups is untouched:
    #     measured, the first 335 records of this run are field-for-field
    #     identical to the 335 of the previous one.
    #
    #     Each net is two registers with different jobs and different
    #     exposure, so they are targeted separately rather than as one
    #     group:
    #
    #       * the WAIT COUNTER (`fetch_wait`, `oh_wait`, 6 bits each) is
    #         live only while a wait is in progress, and is re-zeroed on
    #         every successful fetch, so its corrupted values are
    #         short-lived. Sampled low / mid / high.
    #       * the TIMEOUT PULSE (`fetch_timeout`, `oh_timeout`, one bit
    #         each) WAS the report itself, and was targeted here with
    #         three phases each between 2026-08-30 and the repair later
    #         the same day. All six injections came back DETECTED on a
    #         run whose output was correct -- a fabricated configuration
    #         error, six times out of six -- and test_04 constructed the
    #         opposite direction and erased a real report. pilot_top.v
    #         header section 8.1 retired both pulses: the expiry terms
    #         are now the wires `fetch_expire` / `oh_expire`, and the
    #         same wire ends the wait and latches sticky_errcfg on one
    #         edge.
    #
    #         There is therefore nothing left here to inject INTO, and
    #         the six records are gone rather than passing. The entries
    #         stay in this list (RETIRED_TARGETS): test_01 draws their
    #         phases and skips them, so the six disappear without moving
    #         the phase of any other target, and the day a pulse
    #         register comes back the six injections come back with it,
    #         at the same phases they were measured at.
    t += [("wdog_fetch", "fetch_wait", [0, 2, 5], 2, True),
          ("wdog_fetch", "fetch_timeout", [0], 3, True),
          ("wdog_oh", "oh_wait", [0, 2, 5], 2, True),
          ("wdog_oh", "oh_timeout", [0], 3, True)]

    # 15. THE QUEUE ENTRY-PARITY CHECK FIELD. Added with the hardening of
    #     the queue storage (hw/rtl/aer_fifo.v, section "entry parity"),
    #     and for the same reason item 13 targets `wchk` and `smem`: a
    #     check field is storage, the hardening pays for it in flip-flops,
    #     and if an upset in one of those bits could corrupt an inference
    #     the protection would be importing the risk it removes. The
    #     question is asked with a deposit rather than answered with an
    #     argument.
    #
    #     The expected answer is a REPORTED FALSE DISCARD, not a
    #     corruption: the check bit is inside the codeword it protects, so
    #     an upset in it makes a good event fail its check and be dropped
    #     with par_err raised and the consumer's bounded wait expiring.
    #     One event lost and announced, which is the same outcome as the
    #     case the field exists to catch and is why it is acceptable to
    #     add unprotected state here at all.
    #
    #     `bits` is the packed per-slot vector inside the aer_par_bank
    #     instance, so the bit index IS the slot index, and the targets
    #     are the storage register rather than the checked wire -- the
    #     distinction items 9 and 11 were rewritten for. It draws from
    #     EXT_RNG and is appended last, so every phase drawn by the
    #     twelve groups of the campaign of record and by items 13 and 14
    #     is untouched.
    t += [("evq_par", f"{q}.u_par.bits", spread(q_depth, 2), 2, False)
          for q in ("u_evq_in", "u_evq_out")]

    return t


# Registers read back after a run to detect corruption the run masked but
# the next command sequence would inherit. N_ADDR is deliberately absent:
# the state readback writes it, so its evidence cannot survive to be read.
def latent_map(n_axons):
    return {
        "cfg_axon": [("CFG_AXON", ADDR["CFG_AXON"], n_axons)],
        "ctrl_en": [("CTRL", ADDR["CTRL"], CTRL_EN)],
        "ctrl_scrub_en": [("CTRL", ADDR["CTRL"], CTRL_EN)],
        "node_id": [("NODE_ID", ADDR["NODE_ID"], 0)],
        "w_addr": [("W_ADDR", ADDR["W_ADDR"], 0)],
        "scratch": [("SCRATCH", ADDR["SCRATCH"], 0)],
        "ecc_inj_pos": [("ECC_INJ_POS", ADDR_ECC_INJ_POS, 0)],
        "tmr_inj": [("TMR_INJ", ADDR_TMR_INJ, 0)],
    }


# ---------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------
async def campaign_setup(dut):
    """Start the clock, quiesce the pins, read the geometry back.

    The geometry is read out of the design rather than passed in, and the
    workload constants are selected from it here. Every cocotb test in
    this file calls this first, so WL_SEED and BURST_WINDOW are set before
    any weight matrix is built or any injection phase is drawn.
    """
    global GEOMETRY, WL_SEED, BURST_WINDOW
    cocotb.start_soon(Clock(dut.clk, CLK_NS, unit="ns").start())
    dut.ser_cs_n.value = 1
    dut.ser_sck.value = 0
    dut.ser_mosi.value = 0
    dut.aer_in_stb.value = 0
    dut.aer_in_tick.value = 0
    dut.aer_in_addr.value = 0
    dut.aer_out_ack.value = 0
    dut.scrub_stb.value = 0
    await hard_reset(dut)
    n_neurons = await rd(dut, ADDR["CFG_NEUR"])
    n_axons = await rd(dut, ADDR["CFG_AXON"])
    assert (n_neurons, n_axons) in WORKLOAD, \
        f"no workload for geometry {n_neurons}x{n_axons}: this campaign " \
        f"needs a weight seed whose spike train satisfies the five " \
        f"constraints of test_00_control, and busy windows to draw " \
        f"injection phases inside. Add an entry to WORKLOAD; the " \
        f"supported set is {sorted(WORKLOAD)}"
    GEOMETRY = (n_neurons, n_axons)
    WL_SEED, BURST_WINDOW = WORKLOAD[GEOMETRY]
    weights = make_weights(n_axons, n_neurons)
    return (n_neurons, n_axons, weights, pack_words(weights))


@cocotb.test(timeout_time=300, timeout_unit="sec")
async def test_00_control(dut):
    """The campaign's own honesty check, before any injection.

    Six things have to be true or every number that follows is noise: the
    workload is worth running; an uninjected run reproduces the golden
    model exactly with no flag and no counter; the sentinel rules hold;
    the pins and the register view agree; the busy windows the random draw
    is scaled to are no longer than the real ones; and the injection
    mechanism demonstrably reaches a target.
    """
    geo = await campaign_setup(dut)
    n_neurons, n_axons, weights, words = geo
    dut._log.info(f"geometry {n_neurons}x{n_axons}, weight seed {WL_SEED}")

    exp_bursts, exp_state = golden_run(n_neurons, n_axons, weights)
    exp_events = [w for b in exp_bursts for w in b]

    # -- the workload is worth running --------------------------------
    assert all(b for b in exp_bursts), \
        "the stimulus must emit in every burst, so a fault has something " \
        "to corrupt before, during and after the injection window"
    assert len({v for v, _ in exp_state}) == n_neurons, \
        "golden final V must be distinct per neuron (the sentinel rule): " \
        "otherwise a value written to the wrong neuron reads as correct"
    assert all(v != 0 for v, _ in exp_state), \
        "golden final V must be nonzero everywhere, so a zeroing fault " \
        "cannot alias the correct answer"
    assert any(r > 0 for _, r in exp_state), \
        "at least one neuron must end refractory, or rmem is untested"
    assert max(len(b) for b in exp_bursts) < 5, \
        "no burst may fill the five-entry output path, or BUSY would mean" \
        " 'stalled' rather than 'working'"
    assert len({w for b in exp_bursts for w in b}) >= 3, \
        "several distinct neurons must spike, or the event stream is a " \
        "weak oracle"
    dut._log.info(f"workload: golden events {exp_events}, "
                  f"golden final state {exp_state}")

    # -- an uninjected run is golden-exact ----------------------------
    await bring_up(dut, words)
    completed, got = await run_stimulus(dut)
    obs = await read_observations(dut, n_neurons, completed)
    assert completed, "the control run did not complete"
    assert got == exp_events, f"control events {got} != golden {exp_events}"
    assert [tuple(s) for s in obs["state"]] == exp_state, \
        f"control state {obs['state']} != golden {exp_state}"
    assert obs["status"] & (ST_ERR_CFG | ST_DED_SEEN | ST_OVF_SEEN) == 0, \
        f"the control run raised a flag: STATUS {obs['status']:#x}"
    assert not any(obs[k] for k in COUNTERS), \
        f"the control run moved a counter: {obs}"
    assert not any(obs["pins"].values()), \
        f"the control run set a fault pin: {obs['pins']}"
    assert classify(completed, obs, True) == "MASKED", \
        "a clean run must classify MASKED"

    # -- the pins and the register view agree, so the campaign's
    #    zero-frame pin reads cross-check the reads it classifies on ---
    assert obs["pins"]["err"] == bool(obs["status"]
                                      & (ST_ERR_CFG | ST_OVF_SEEN))

    # -- the sentinel actually sits in the queue storage ---------------
    # Every slot of both arrays, read back after a bring-up rather than
    # assumed from the fill. The control run above has since written real
    # events over the fill, so this needs the fresh bring-up it is
    # checking; the same bring-up starts the window measurement below.
    # If any slot were something else the whole aliasing argument of the
    # module docstring would be a claim rather than a property: a pointer
    # upset that fetches an unwritten slot has to yield a word the
    # dispatcher drops, not a stale copy of a legitimate event.
    await bring_up(dut, words)
    for q in ("u_evq_in", "u_evq_out"):
        mem = resolve(dut, q).mem
        for i in range(len(mem)):
            got = read_defined(mem[i], f"{q}.mem[{i}]")
            assert got == FIFO_SENTINEL, \
                f"{q}.mem[{i}] reads {got:#06x} after a bring-up, not the " \
                f"sentinel {FIFO_SENTINEL:#06x}: the fill did not cover " \
                f"this slot and a fault fetching it could alias a " \
                f"legitimate event"
    assert FIFO_SENTINEL >> 14 == 0b11, \
        "the sentinel must carry the reserved TYPE encoding"
    assert FIFO_SENTINEL not in exp_events, \
        "the sentinel must not alias a golden event word"

    # -- the busy windows the random draw uses are inside the real ones -
    measured = [await measure_window(dut, b) for b in BURSTS]
    dut._log.info(f"measured burst busy windows: {measured} cycles; "
                  f"the campaign draws inside {list(BURST_WINDOW)}")
    for w, m in zip(BURST_WINDOW, measured):
        assert w <= m, \
            f"BURST_WINDOW {BURST_WINDOW} draws past the measured busy " \
            f"window {measured}: injections would land on an idle design"

    # -- the injection mechanism demonstrably reaches a target ---------
    # The FSM encoding is the one prediction the design states outright:
    # every single-bit upset of `state` is an illegal word, so the core
    # must park and raise err_cfg. If this comes back MASKED the deposit
    # is not landing and the whole campaign is measuring nothing.
    probe = await injection(dut, geo, "control_probe", "u_lif.state", 0, 0, 0)
    assert probe["class"] == "DETECTED", \
        f"a deposit into lif_core.state must be DETECTED, got {probe}"
    RESULTS.clear()          # the probe is a self-test, not a data point
    WALL["t0"] = time.time()


@cocotb.test(timeout_time=1800, timeout_unit="sec")
async def test_01_structural_injections(dut):
    """Every curated architectural target, seeded phases, one bit each."""
    geo = await campaign_setup(dut)
    n_neurons, n_axons = geo[0], geo[1]
    lat = latent_map(n_axons)
    q_depth = len(dut.u_evq_in.mem)

    for group, path, bits, n_phase, pin_first in \
            target_list(n_neurons, n_axons, q_depth):
        # A tuple of paths is a set of targets that share one drawn phase
        # -- the three replicas of a TMR domain, injected one at a time.
        # The draw happens once, so adding a replica cannot move the
        # phases of any group drawn after this one (target_list item 9).
        paths = path if isinstance(path, tuple) else (path,)
        rng = EXT_RNG if group in EXT_GROUPS else RNG
        # A target the design no longer has. Only the declared retirements
        # may vanish; anything else that stops resolving is a shrinking
        # campaign and fails here rather than reporting a smaller total
        # as if nothing had changed. The phases are drawn either way, so
        # a retirement moves no other target's injection window.
        live = [p for p in paths if state_present(dut, p)]
        missing = [p for p in paths if p not in live]
        assert all(p in RETIRED_TARGETS for p in missing), \
            f"target {missing} does not resolve in the design and is not " \
            f"a declared retirement (RETIRED_TARGETS): the campaign " \
            f"would silently stop measuring it"
        if missing:
            dut._log.info(f"retired target {missing} ({group}): no state "
                          f"to deposit into, phases drawn and skipped")
        for bit in bits:
            for b, d in phases(n_phase, pin_first, rng):
                for one in live:
                    await injection(dut, geo, group, one, bit, b, d,
                                    latent_regs=lat.get(one, ()))
    dut._log.info(f"structural injections: {len(RESULTS)}")


@cocotb.test(timeout_time=900, timeout_unit="sec")
async def test_02_ecc_weight_word(dut):
    """The ECC-protected weight word, through both of its fault paths.

    Path A (ecc_port_*): the design's own injection port corrupts the
    stored 72-bit codeword at the instant the word is committed, which is
    the only way to reach the loader before it copies the word into
    lif_core. This is the path a bench uses, and it is what the pilot's
    SECDED claim is about: a single-bit upset must be corrected on the
    read path so the inference is untouched, and a double-bit upset must
    be detected and substituted with zeros (E10, docs/10 section 11.2)
    rather than loaded as garbage. The CLASS of a double is still decided
    against the CLEAN golden -- a degraded answer is not the answer the
    operator asked for -- and e10_events_ok records separately whether the
    degradation was exactly the specified one.

    Path B (ecc_ff): a deposit into the staging flip-flops after the load,
    followed by a SCRUB_STB pulse. The weights have already reached
    lif_core, so this measures the scrubber loop and the observability of
    the stored word, not the inference.
    """
    geo = await campaign_setup(dut)
    n_words = len(geo[3])

    single_pos = [0, 7, 19, 31, 33, 47, 58, 63, 64, 67, 70, 71]
    for k, pos in enumerate(single_pos):
        wi = k % n_words
        rec = await injection(dut, geo, "ecc_port_single", None, None,
                              None, 0, ecc_inj=(wi, pos, INJ_SINGLE),
                              expect_tel={"cnt_sec": 1})
        rec["ecc_word"], rec["ecc_pos"] = wi, pos

    # ECC_INJ.DOUBLE flips POS and POS+1 mod 72, a valid double error for
    # any Hsiao code (pilot_top.v section 4).
    for k, pos in enumerate([0, 20, 55, 70]):
        wi = k % n_words
        rec = await injection(dut, geo, "ecc_port_double", None, None,
                              None, 0, ecc_inj=(wi, pos, INJ_DOUBLE),
                              poison_word=wi, expect_tel={"cnt_ded": 1})
        rec["ecc_word"], rec["ecc_pos"] = wi, pos

    for bit in (0, 17, 40, 63):
        await injection(dut, geo, "ecc_ff", "ecc_data", bit, 0, 0,
                        scrub=True, expect_tel={"cnt_sec": 1})
    for bit in (0, 3, 7):
        await injection(dut, geo, "ecc_ff", "ecc_check", bit, 0, 0,
                        scrub=True, expect_tel={"cnt_sec": 1})
    dut._log.info(f"after the ECC domain: {len(RESULTS)} injections")


@cocotb.test(timeout_time=600, timeout_unit="sec")
async def test_03_telemetry_erasure(dut):
    """Can an upset erase the radiation record it exists to keep?

    Every other counter injection in this campaign starts from a counter
    that reads zero, so it can only measure spurious counting. This test
    primes the telemetry first -- one real corrected single-bit weight
    error, so CNT_SEC reads 1 and the SEC pin is lit -- and then upsets the
    counter and its sticky bit. telemetry_ok is False when the record no
    longer matches what actually happened, in either direction.
    """
    geo = await campaign_setup(dut)
    primed = {"cnt_sec": 1}
    for target, bit in (("cnt_sec", 0), ("cnt_sec", 1), ("sticky_sec", 0),
                        ("cnt_ded", 0), ("sticky_ded", 0), ("cnt_tmr", 0)):
        for b, d in phases(1):
            await injection(dut, geo, "telemetry_primed", target, bit, b, d,
                            ecc_inj=(0, 5, INJ_SINGLE), expect_tel=primed)
    dut._log.info(f"after the telemetry domain: {len(RESULTS)} injections")


# ---------------------------------------------------------------------
# directed watchdog cases (test_04)
# ---------------------------------------------------------------------
# The dispatcher FSM encodings, repeated here rather than imported,
# because the campaign is not allowed to include the RTL and a wrong
# constant would silently construct the wrong experiment. test_04
# asserts that every `until` step found the cycle it was looking for, so
# a constant that stops matching fails the test instead of reporting a
# robustness the design does not have.
D_IDLE, D_FETCH = 0, 1
WAIT_MAX = 63          # FETCH_WAIT_MAX and OH_WAIT_MAX, 6 bits of ones


def watchdog_cases():
    """The six constructed cases of docs/16 section 5.8, per safety net.

    Each entry is (group, case, note, steps). The steps run inside burst
    0's busy window; `run_script` documents the step grammar.

    The pattern is the same on both ends of the pipe because the two
    nets are the same circuit twice:

      clear_midwait  an upset zeroes the counter while it is counting.
                     Does the timeout still fire, or does the wait
                     restart forever?
      fire_early     an upset drives the counter to its bound while a
                     REAL fault is being waited out. Fires early -- does
                     that cost anything?
      fire_spurious  the same, with no fault present, on a legitimate
                     one-cycle wait. This is the dangerous direction:
                     the net firing on a design that was working.
      report_kept    the CONTROL for the two cases below, and it is
                     written
                     to be exact: byte-for-byte the same steps, INCLUDING
                     the 64-cycle poll that waits for the pulse, with
                     only the final deposit removed. The poll is part of
                     the control on purpose. It reads internal state and
                     changes nothing in the design, but it does hold up
                     `run_stimulus` for 64 cycles before the drain
                     begins, and a control that skipped it would differ
                     from the case below in TWO things -- the deposit
                     and the harness timing -- which is how a first
                     version of it came out golden while the case it
                     controls came out corrupted. As written, the two
                     records differ in exactly one deposit, and any
                     difference between them is that deposit.
      report_erased  THE CASE. The fault happens, the net catches it,
                     and an upset lands on the one-cycle report in the
                     one cycle it is high. The recovery still happens.
                     Does anything tell the host it did?

    The fault is planted the same way in both nets and by a genuine
    single-bit XOR: `dstate` D_IDLE -> D_FETCH with no read outstanding
    (docs/16 section 5.1), and `oh_req` set with no read outstanding
    (section 5.7). Only the upset in the net itself is ever a `force`.

    2026-08-30, after the repair of pilot_top.v header section 8.1. The
    two cases that deposit into the report -- report_erased and
    report_fabricated -- are unchanged in every step except that the
    deposit is now a `xor?`, and the cycle they are placed at is now
    found by polling the expiry WIRE (`fetch_expire` / `oh_expire`)
    rather than the pulse register that used to follow it one cycle
    later. `wait 1` restores that cycle, so on a design that still has
    the pulse the deposit lands exactly where it landed when the defect
    was measured, and on the repaired design the script runs to the same
    place and finds nothing to deposit into. Both are recorded; test_04
    asserts which one it got. report_kept carries the same `wait 1` so
    that it stays byte-identical to report_erased but for the deposit.
    """
    return [
        # ---- the dispatcher's D_FETCH bound -------------------------
        ("wdog_fetch_dir", "clear_midwait",
         "counter zeroed 20 cycles into a real bounded wait",
         [("until", "dstate", D_IDLE, 60),
          ("xor", "dstate", 0),
          ("wait", 20),
          ("force", "fetch_wait", 0)]),
        ("wdog_fetch_dir", "fire_early",
         "counter driven to its bound 10 cycles into a real wait",
         [("until", "dstate", D_IDLE, 60),
          ("xor", "dstate", 0),
          ("wait", 10),
          ("force", "fetch_wait", WAIT_MAX)]),
        ("wdog_fetch_dir", "fire_spurious",
         "counter driven to its bound during a LEGITIMATE D_FETCH",
         [("until", "dstate", D_FETCH, 60),
          ("force", "fetch_wait", WAIT_MAX)]),
        ("wdog_fetch_dir", "report_kept",
         "control: the same deadlock, the net left alone",
         [("until", "dstate", D_IDLE, 60),
          ("xor", "dstate", 0),
          ("until", "fetch_expire", 1, 90),
          ("wait", 1)]),
        ("wdog_fetch_dir", "report_erased",
         "real deadlock, and the timeout pulse erased in its one cycle",
         [("until", "dstate", D_IDLE, 60),
          ("xor", "dstate", 0),
          ("until", "fetch_expire", 1, 90),
          ("wait", 1),
          ("xor?", "fetch_timeout", 0)]),
        ("wdog_fetch_dir", "report_fabricated",
         "no fault; the timeout pulse set for one cycle",
         [("wait", 5), ("xor?", "fetch_timeout", 0)]),

        # ---- the show-ahead adapter's oh_req bound -------------------
        ("wdog_oh_dir", "clear_midwait",
         "counter zeroed 20 cycles into a real bounded wait",
         [("xor", "oh_req", 0),
          ("wait", 20),
          ("force", "oh_wait", 0)]),
        ("wdog_oh_dir", "fire_early",
         "counter driven to its bound 10 cycles into a real wait",
         [("xor", "oh_req", 0),
          ("wait", 10),
          ("force", "oh_wait", WAIT_MAX)]),
        ("wdog_oh_dir", "fire_spurious",
         "counter driven to its bound during a LEGITIMATE oh_req wait",
         [("until", "oh_req", 1, 200),
          ("force", "oh_wait", WAIT_MAX)]),
        ("wdog_oh_dir", "report_kept",
         "control: the same deadlock, the net left alone",
         [("xor", "oh_req", 0),
          ("until", "oh_expire", 1, 90),
          ("wait", 1)]),
        ("wdog_oh_dir", "report_erased",
         "real deadlock, and the timeout pulse erased in its one cycle",
         [("xor", "oh_req", 0),
          ("until", "oh_expire", 1, 90),
          ("wait", 1),
          ("xor?", "oh_timeout", 0)]),
        ("wdog_oh_dir", "report_fabricated",
         "no fault; the timeout pulse set for one cycle",
         [("wait", 5), ("xor?", "oh_timeout", 0)]),
    ]


@cocotb.test(timeout_time=600, timeout_unit="sec")
async def test_04_watchdog_directed(dut):
    """What happens when the watchdog itself is upset.

    The two bounded waits are the only structures in the pilot whose
    entire job is to make a hang visible, so a random-phase rate over
    them answers the wrong question: it measures how OFTEN an upset in
    the net matters, when what is needed is whether the net still works
    WHEN it matters. The five cases per net construct that directly.

    Written 2026-08-30, this test recorded and did not judge: its one
    hard criterion was the safety property the nets actually promise --
    that the wait stays bounded -- and that held even where the report
    did not. What it measured was a real weakness in the report, and a
    criterion written around a weakness is a criterion written to pass.

    The weakness is closed (pilot_top.v header section 8.1), so the
    criteria at the end of this test now judge as well as record. The
    bound is still the first of them and still the one that matters
    most; the three that follow are the repair, each written so that the
    mutation which undoes it fails here with the pre-repair record in
    the message.
    """
    geo = await campaign_setup(dut)
    by_case = {}
    for group, case, note, steps in watchdog_cases():
        rec = await injection(dut, geo, group, case, None, 0, None,
                              script=steps)
        rec["case"], rec["note"] = case, note
        rec["errcfg"] = bool(rec["status"] & ST_ERR_CFG)
        # False when a `xor?` step found no state at the retired name --
        # i.e. when the design has no one-cycle report to corrupt.
        rec["deposit_landed"] = not any(s.startswith("NO SUCH STATE")
                                        for s in rec["script"])
        by_case[(group, case)] = rec
        assert rec["constructed"], \
            f"the directed case {group}/{case} did not construct: a " \
            f"cycle it had to land on never occurred, so its outcome " \
            f"says nothing about the safety net. Script log: " \
            f"{rec['script']}"
        dut._log.info(f"{group:<16}{case:<18}{rec['class']:<10}"
                      f"ERR_CFG={int(rec['errcfg'])} "
                      f"out_ok={int(rec['out_ok'])} "
                      f"completed={int(rec['completed'])}")

    # The one criterion. A bounded wait promises exactly one thing: the
    # wait ends. Everything else the net does -- the report, the counter,
    # the sticky -- is downstream of that and is measured rather than
    # required here, because the measurement found a case where the
    # downstream part fails and a criterion written to pass would have
    # hidden it. If any of these HANGs, the bound itself is breakable by
    # a single upset and the fix is not optional.
    hung = [r for r in RESULTS
            if r["group"].startswith("wdog_") and not r["completed"]]
    assert not hung, \
        f"a bounded wait failed to bound: {[(r['group'], r.get('case')) for r in hung]}"

    # ---- the report, after the repair of section 8.1 -----------------
    # Until 2026-08-30 this test recorded and did not judge, because what
    # it measured was a weakness and a criterion written around a
    # weakness is a criterion written to pass. The weakness is closed
    # now, and the criteria below are what keep it closed. Each one is
    # written so that RESTORING the one-cycle pulse register -- the exact
    # mutation, verified against a scratch copy of pilot_top.v -- fails
    # it with the pre-repair record in the message.
    for net, report in (("wdog_fetch_dir", "fetch_timeout"),
                        ("wdog_oh_dir", "oh_timeout")):
        kept = by_case[(net, "report_kept")]
        erased = by_case[(net, "report_erased")]
        fab = by_case[(net, "report_fabricated")]
        spur = by_case[(net, "fire_spurious")]

        # 1. There is no separate report to erase. The two records differ
        #    by one deposit and nothing else, so any difference between
        #    them IS that deposit -- and there is no longer a deposit.
        assert not erased["deposit_landed"], \
            f"{net}: `{report}` still exists as state a single deposit " \
            f"can land in, so the report is separable from the recovery " \
            f"again. Script: {erased['script']}"
        assert erased["class"] == kept["class"] == "DETECTED" \
            and erased["errcfg"] and kept["errcfg"], \
            f"{net}: a real deadlock recovered by the bounded wait must " \
            f"reach the host. control {kept['class']} " \
            f"STATUS {kept['status']:#04x}, case {erased['class']} " \
            f"STATUS {erased['status']:#04x} -- an erased report reads " \
            f"SDC at 0x06 against a control at 0x16 (docs/16 5.8)"

        # 2. And no deposit fabricates one either. With nothing to set,
        #    the run is uninjected and must come back exactly as clean as
        #    test_00's control run.
        assert not fab["deposit_landed"] and fab["class"] == "MASKED" \
            and not fab["errcfg"], \
            f"{net}: a single deposit fabricated a configuration error " \
            f"on a run that was working: {fab['class']} " \
            f"STATUS {fab['status']:#04x}"

        # 3. A spurious expiry costs the report and nothing else. The
        #    D_IDLE capture arm of pilot_top.v is what makes this true on
        #    the dispatcher side; the adapter has always had it.
        assert spur["out_ok"], \
            f"{net}: a spurious expiry on a legitimate wait lost an " \
            f"event -- the fetched word was dropped instead of being " \
            f"captured in D_IDLE: {spur['got_events']} != " \
            f"{spur['exp_events']}"
    dut._log.info(f"after the directed watchdog cases: {len(RESULTS)} "
                  f"injections")


@cocotb.test(timeout_time=120, timeout_unit="sec")
async def test_05_summary(dut):
    """Aggregate, dump the per-injection log, enforce the pass criteria."""
    await Timer(10, unit="ns")
    wall = time.time() - WALL.get("t0", time.time())

    groups, extra = {}, {}
    for r in RESULTS:
        assert r["class"] in CLASSES, f"unclassified injection: {r}"
        g = groups.setdefault(r["group"], {c: 0 for c in CLASSES})
        g[r["class"]] += 1
        # Per-group facts the five classes cannot carry, kept beside the
        # histogram rather than inside it so every number the report
        # quotes comes out of this log and not out of a later analysis.
        e = extra.setdefault(r["group"], {k: 0 for k in (
            "n", "sdc_stream", "sdc_state_only", "tel_differs", "latent")})
        e["n"] += 1
        e["sdc_stream"] += r["class"] == "SDC" and not r["spikes_ok"]
        e["sdc_state_only"] += r["class"] == "SDC" and r["spikes_ok"]
        e["tel_differs"] += not r.get("telemetry_ok", True)
        e["latent"] += bool(r.get("latent"))

    total = len(RESULTS)
    hist = {c: sum(g[c] for g in groups.values()) for c in CLASSES}
    dut._log.info(f"campaign: {total} injections, seed "
                  f"0x{CAMPAIGN_SEED:08X}, {wall:.1f} s wall")
    dut._log.info(f"{'group':<20}" + "".join(f"{c:>11}" for c in CLASSES)
                  + f"{'SDC %':>9}{'stream':>8}{'state':>7}")
    for name in sorted(groups):
        g, e = groups[name], extra[name]
        dut._log.info(f"{name:<20}" + "".join(f"{g[c]:>11}" for c in CLASSES)
                      + f"{100.0 * g['SDC'] / e['n']:>8.1f}%"
                      + f"{e['sdc_stream']:>8}{e['sdc_state_only']:>7}")
    dut._log.info(f"{'TOTAL':<20}" + "".join(f"{hist[c]:>11}" for c in CLASSES)
                  + f"{100.0 * hist['SDC'] / max(total, 1):>8.1f}%")

    det_wrong = sum(1 for r in RESULTS
                    if r["class"] == "DETECTED" and not r["out_ok"])
    latent = sum(1 for r in RESULTS if r.get("latent"))
    state_only = sum(1 for r in RESULTS
                     if r["spikes_ok"] and not r["state_ok"])
    tel_bad = sum(1 for r in RESULTS if not r.get("telemetry_ok", True))
    dut._log.info(f"DETECTED with a corrupted output: {det_wrong} of "
                  f"{hist['DETECTED']}")
    dut._log.info(f"corruption visible only in retained neuron state: "
                  f"{state_only}")
    dut._log.info(f"latent register corruption after the run: {latent}")
    # telemetry_ok compares against the SAME bring-up with no deposit, so
    # a difference means the counters moved because of this injection. In
    # the two telemetry groups that is corruption of the record; anywhere
    # else it is the design correctly counting the event it was given.
    dut._log.info(f"telemetry differs from the same bring-up undeposited: "
                  f"{tel_bad} (by group: "
                  + ", ".join(f"{k}={extra[k]['tel_differs']}"
                              for k in sorted(extra)
                              if extra[k]["tel_differs"]) + ")")

    # The 8 x 8 log keeps the documented path: it is the campaign of
    # record and docs/16 section 8 calls it the acceptance baseline. Any
    # other geometry writes beside it rather than over it.
    stem = "fi_campaign_results"
    if GEOMETRY != (8, 8):
        stem += f"_{GEOMETRY[0]}x{GEOMETRY[1]}"
    out = Path(__file__).parent / f"{stem}.json"
    out.write_text(json.dumps({
        "seed": CAMPAIGN_SEED,
        "geometry": {"n_neurons": GEOMETRY[0], "n_axons": GEOMETRY[1]},
        "workload": {"weight_seed": WL_SEED, "thresh": CFG.thresh,
                     "v_reset": CFG.v_reset, "leak_shift": CFG.leak_shift,
                     "syn_shift": CFG.syn_shift,
                     "refr_period": CFG.refr_period,
                     "bursts": [[list(c) for c in b] for b in BURSTS],
                     "burst_window": list(BURST_WINDOW)},
        "wall_seconds": round(wall, 1),
        "total": total, "histogram": hist, "groups": groups,
        "group_detail": extra,
        "detected_with_wrong_output": det_wrong,
        "state_only_divergence": state_only,
        "latent_register_corruption": latent,
        "telemetry_mismatch": tel_bad,
        "injections": RESULTS}, indent=1))
    dut._log.info(f"per-injection log written to {out}")

    # -- campaign pass criteria ---------------------------------------
    assert total == sum(hist.values())
    assert total >= 200, f"the campaign shrank to {total} injections"
    # Every mechanism the design makes an explicit promise about must keep
    # it, or this is a report on a broken build rather than on fault
    # tolerance: the HD-2 FSM encoding, the configuration TMR domain, and
    # both halves of the SECDED weight word.
    fsm = groups.get("lif_fsm", {})
    assert fsm and fsm["DETECTED"] == sum(fsm.values()), \
        f"every lif_core FSM upset must be DETECTED, got {fsm}"
    tmr = {c: sum(groups.get(f"cfg_tmr_{r}", {}).get(c, 0)
                  for r in ("a", "b", "c")) for c in CLASSES}
    assert tmr["SDC"] == 0 and tmr["CORRECTED"] > 0, \
        f"a single TMR replica upset must never be SDC, got {tmr}"
    ecc = groups.get("ecc_port_single", {})
    assert ecc and ecc["SDC"] == 0 and ecc["CORRECTED"] == sum(ecc.values()), \
        f"a single-bit weight-word upset must always be CORRECTED, got {ecc}"
    dbl = groups.get("ecc_port_double", {})
    assert dbl and dbl["DETECTED"] == sum(dbl.values()), \
        f"a double-bit weight-word upset must be DETECTED, got {dbl}"
    # The memory hardening of 2026-08-26 (hw/rtl/lif_core.v header section
    # MEMORY HARDENING) makes one promise and it is checkable here: every
    # bit of wmem, vmem, rmem and of the two check fields now sits inside
    # a systematic SECDED codeword, so ANY single-bit upset in any of them
    # is corrected on the read path and no single-bit upset in any of them
    # may produce a silent corruption. This is the criterion that would
    # fail if a future edit -- a wider word, a bypassed decoder, a read
    # port that forgets to decode -- quietly took the protection away.
    coded = {c: sum(groups.get(g, {}).get(c, 0) for g in (
        "lif_wmem", "lif_wmem_unread", "lif_vmem", "lif_rmem",
        "lif_wchk", "lif_wchk_unread", "lif_smem")) for c in CLASSES}
    assert sum(coded.values()) > 0 and coded["SDC"] == 0, \
        f"a single-bit upset in a coded memory file must never be SDC, " \
        f"got {coded}"
    # The pointer TMR of hw/rtl/aer_fifo.v, on the same footing. This one
    # is written in two halves because the failure it exists to catch is
    # not a broken voter but a MIS-TARGETED INJECTOR: before 2026-08-29
    # this group deposited into the voted wire, which is not storage, and
    # reported 23 SDC and 0 CORRECTED out of 24 against a working TMR
    # (target_list item 9). A campaign that measures nothing must fail
    # rather than report zeros, so:
    #
    #   (a) every pointer target is a replica's storage register. A future
    #       edit that re-points this group at `wr_ptr` or `rd_ptr` fails
    #       here even on a simulator that would classify such a deposit
    #       the same way; and
    #   (b) every one of those upsets is corrected -- masked at the
    #       outputs AND counted in CNT_TMR. Not merely "no SDC": an upset
    #       that never reached the flip-flop would come back MASKED, which
    #       is exactly the quiet nothing this criterion is here to catch.
    ptr_paths = sorted({r["target"] for r in RESULTS
                        if r["group"] == "evq_ptr"})
    assert ptr_paths and all(p.endswith(".bits") for p in ptr_paths), \
        f"every evq_ptr target must be a pointer replica's storage " \
        f"register (aer_ptr_bank.bits), not the voted wire, or the group " \
        f"is measuring a node the TMR does not claim to protect: " \
        f"{ptr_paths}"
    ptr = groups.get("evq_ptr", {})
    assert ptr and ptr["CORRECTED"] == sum(ptr.values()), \
        f"a single-replica AER pointer upset must always be CORRECTED -- " \
        f"masked by the vote and counted in CNT_TMR -- got {ptr}"
    # The show-ahead valid flag's two rails (pilot_top.v header section
    # 8.2), on the same two-part footing as the pointers and for the
    # same reason: the failure to catch is a mis-targeted injector, not
    # a broken detector.
    #
    #   (a) every valid-flag target is a rail's storage register. An
    #       edit that re-points this at the checked wire `oh_valid`
    #       would measure a node the rails do not claim to protect and
    #       would report the pre-hardening result against a working
    #       detector, which is exactly what the pointer group did for a
    #       day (target_list item 9); and
    #   (b) every one of those upsets is DETECTED. Two rails detect and
    #       do not correct, so the held event is still lost and the run
    #       is still wrong -- the promise is that it is never wrong
    #       SILENTLY, which is the SDC-to-DETECTED move docs/16 section
    #       6.2 costed this hardening at.
    # All three dual-rail flags at once: oh_valid (u_ohv_*), the two
    # queues' rd_valid (u_rdv_*) and lif_core's out_pend (u_op_*).
    rail_paths = sorted({r["target"] for r in RESULTS
                         if _is_rail(r["target"])})
    assert len(rail_paths) == 6 and all(p.endswith(".bits")
                                        for p in rail_paths), \
        f"every valid-flag target must be a rail's storage register " \
        f"(*_flag_rail.bits), not the checked wire the consumer reads. " \
        f"Six are expected -- two rails each for oh_valid, EVQ_OUT's " \
        f"rd_valid and out_pend -- and these were found: {rail_paths}"
    rail = {c: 0 for c in CLASSES}
    for r in RESULTS:
        if _is_rail(r["target"]):
            rail[r["class"]] += 1
    assert rail["DETECTED"] == sum(rail.values()), \
        f"an upset in one rail of a dual-rail valid flag must always be " \
        f"DETECTED -- the rails disagree, the consumer reads the flag " \
        f"low rather than trusting it, and sticky_errcfg latches. Two " \
        f"rails detect and do not correct, so the run may still be " \
        f"wrong; what it may never be is silent -- got {rail}"
    # The queue entry parity (hw/rtl/aer_fifo.v, section "entry parity"),
    # on the same two-part footing as the pointers and the rails and for
    # the same reason: the failure to catch is a mis-targeted injector,
    # not a broken checker.
    #
    #   (a) every evq_mem target is a queue STORAGE word, not the
    #       registered read port, and every evq_par target is the check
    #       field's own storage register. `u_evq_out.rd_data` is
    #       deliberately in the evq_hold group and not here: it is
    #       downstream of the check and nothing claims to protect it.
    #   (b) no single-bit upset in a stored event word may be SILENT.
    #       One check bit detects every odd-weight error, so a corrupted
    #       entry is discarded on the read, the consumer's bounded wait
    #       expires and STATUS.ERR_CFG latches -- DETECTED, with the
    #       event still lost, which is the SDC-to-announced-drop move
    #       docs/16 section 6.2 item 4 costed this hardening at. A slot
    #       the workload never reads stays MASKED, and that is why this
    #       is written as "no SDC" rather than "all DETECTED".
    mem_paths = sorted({r["target"] for r in RESULTS
                        if r["group"] == "evq_mem"})
    assert mem_paths and all(".mem[" in p for p in mem_paths), \
        f"every evq_mem target must be a stored queue word, or the " \
        f"group is measuring something the entry parity does not " \
        f"protect: {mem_paths}"
    par_paths = sorted({r["target"] for r in RESULTS
                        if r["group"] == "evq_par"})
    assert len(par_paths) == 2 and all(p.endswith("u_par.bits")
                                       for p in par_paths), \
        f"every evq_par target must be the parity bank's storage " \
        f"register, not the checked wire: {par_paths}"
    qmem = {c: sum(groups.get(g, {}).get(c, 0)
                   for g in ("evq_mem", "evq_par")) for c in CLASSES}
    assert sum(qmem.values()) > 0 and qmem["SDC"] == 0, \
        f"a single-bit upset in a queue entry or in its check bit must " \
        f"never be a silent corruption: the check discards the entry and " \
        f"the consumer's bounded wait reports it. Got {qmem}"
    # The two bounded-wait counters (target_list item 14 and test_04).
    # Presence here, outcome in test_04. What must not happen silently
    # is the groups disappearing, which is how the nets came to be
    # unmeasured in the first place -- and, since the repair of section
    # 8.1 retired two targets out of these groups, exactly the failure
    # this check has to keep telling apart from that repair.
    for g in ("wdog_fetch", "wdog_oh", "wdog_fetch_dir", "wdog_oh_dir"):
        assert groups.get(g), \
            f"the safety-net group {g} is missing: the structures that " \
            f"convert a silent hang into a reported one must stay in " \
            f"the target list (docs/16 section 7.3)"
    # Whatever else an upset in a bounded wait does, the wait must stay
    # bounded -- that is the whole promise of the structure and it is the
    # one thing this campaign will not let regress.
    wdog = {c: sum(groups[g][c] for g in groups if g.startswith("wdog_"))
            for c in CLASSES}
    assert wdog["HANG"] == 0, \
        f"an upset in a bounded-wait counter re-opened the silent-hang " \
        f"failure class the counter exists to close: {wdog}"
