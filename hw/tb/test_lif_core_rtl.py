# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""LIF core RTL lockstep suite: hw/rtl/lif_core.v against the golden model.

The golden model sw/golden/lif_core.py is the normative executable form of
the equations in docs/10-npu-mvp-spec.md section 4. This suite imports it
directly and runs it step for step alongside the RTL: identical
configuration, identical weights, identical event and tick streams. After
every command the whole neuron state file (V and R for all N_NEURONS,
through the N_ADDR/N_DATA debug port) and the emitted spike stream are
compared against the model. Any divergence fails on the step that caused
it, naming the neuron.

Directed cases, each mirroring a golden-model test in sw/tests/:
  - saturation at both 16-bit rails, including the spike that a two's
    complement wraparound would silently lose (E3 + E4)
  - leak toward zero on negative membranes, |-32768| at full magnitude,
    and the minimum step of 1 (E6)
  - refractory suppression, countdown, and leak during refractory (E6, E7)
  - tile_offset in emitted ids, including the id-1023 boundary (E5, E9)
  - back-to-back events on one neuron, with and without refractory (E7)
  - the threshold check running on a zero contribution (E4)
  - ascending scan order of emissions within one event (E8)
  - a partial E9 tile matching a golden core built at the tile width
  - TICK emitting nothing (spec section 4.2)
  - output backpressure: no spike is dropped or reordered (spec 7.2)
Then 2000 randomized lockstep steps at a fixed seed, plus a sweep of
randomized configurations (one of them under random backpressure).

Lockstep alone leaves the control interface unverified -- the golden
model has no notion of valid/ready, of a command arbiter, or of a stall.
A second group of directed tests covers what it cannot:
  - command arbitration: STATE_CLR over both channels, SPIKE over TICK,
    one command in flight at a time (spec 4.3 E8 rule 1)
  - input handshake: no accepted command lost, no deadlock with both
    channels held, a held spike does not swallow STATE_CLR
  - output handshake: out_valid never retracted, the held word frozen
  - the debug-write interlock
  - the spec 11.4 SAFE state: every illegal FSM encoding parks the core
    and latches ERR_CFG
Each of those names the mutant it kills; formal/lif_ctrl.sby proves the
same properties over the whole input space.

E10 (uncorrectable-word zero substitution) is out of scope for this build:
the pilot stores synapses in flip-flops, so no ECC path exists to poison.
The model's poisoned_words set is left empty, which makes the two sides
bit-identical by construction on that equation.

The suite reads N_NEURONS and N_AXONS back from the DUT and builds the
golden core to match, so it follows any geometry the Makefile compiles.
The directed cases address specific neuron and axon indices and therefore
need N_NEURONS >= 4 and N_AXONS >= 4; that is the only restriction, and
the rest of the specification's 1..1024 range works unchanged. Every
tile offset used by a directed case is derived from N_NEURONS rather than
hardcoded, because the legal offset range is [0, 1024 - N_NEURONS] (spec
section 9): a fixed offset of 32 or 64 makes the golden core refuse to
construct above N_NEURONS 992 or 960 respectively, which are inside the
legal range, not outside it.

Verified at 4x4, 8x4, 32x32 (the pilot default) and 64x16 for the whole
suite, and at 961x4, 1000x4 and 1024x4 for the geometry-sensitive cases.

Mutation evidence [fact, measured 25 August 2026]. The handshake group
exists because the lockstep group did not constrain the control
interface. Seven single-edit mutants of hw/rtl/lif_core.v were built and
run against the suite:

  1 ev_ready drops its !state_clr qualifier
  2 tick_ready drops its !ev_valid qualifier
  3 S_IDLE arbitration takes the event before the clear
  4 the clear is qualified with !out_pend (a held spike swallows it)
  5 ev_ready is qualified with !tick_valid (both readys mutually
    exclusive, so both channels held is a deadlock)
  6 the FSM default arm resumes in S_IDLE and latches nothing
  7 S_SAFE is entered but ERR_CFG is never latched

Before this group existed, mutants 1-5 all passed the suite 16/16.
After it, all seven fail it, and all seven also fail formal/lif_ctrl.sby
(1-5 on prove, 6-7 on bmc_safe -- see the H8 note in
formal/lif_ctrl_props.v for why prove cannot catch 6 and 7). Reproduce
by pointing the suite at a mutated copy without editing the tree:

    make -f Makefile.lif LIF_SRC=/path/to/mutant.v \\
         SIM_BUILD=sim_build_mut COCOTB_RESULTS_FILE=results_mut.xml

Run: cd hw/tb && make -f Makefile.lif
"""

import random
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "sw")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from golden.lif_core import (  # noqa: E402  (path setup must precede import)
    LIFConfig,
    LIFCore,
    V_MAX,
    V_MIN,
)

CLK_PERIOD_NS = 10
SETTLE_NS = 1  # read past the non-blocking update / combinational settle


def s16(x):
    """Interpret a 16-bit read as signed two's complement."""
    return x - 0x10000 if x & 0x8000 else x


def u16(x):
    return x & 0xFFFF


def u4(x):
    return x & 0xF


def zeros(n_axons, n_neurons):
    return [[0] * n_neurons for _ in range(n_axons)]


class LifHarness:
    """Port-level driver, spike monitor and lockstep comparator."""

    def __init__(self, dut):
        self.dut = dut
        self.n_neurons = int(dut.N_NEURONS.value)
        self.n_axons = int(dut.N_AXONS.value)
        self.spikes = []       # ids accepted on the output handshake
        self.ecc = {name: 0 for name in self.ECC_FLAGS}
        self._mon_on = True
        self._bp_on = False

    # -- bring-up ----------------------------------------------------------

    async def start(self):
        # cocotb reaps every start_soon task when a test ends, so the clock
        # and the monitor are (re)started per harness, not once per module.
        d = self.dut
        cocotb.start_soon(Clock(d.clk, CLK_PERIOD_NS, unit="ns").start())
        d.cfg_thresh.value = 256
        d.cfg_vreset.value = 0
        d.cfg_leak_shift.value = 3
        d.cfg_syn_shift.value = 0
        d.cfg_refr.value = 0
        d.cfg_leak_en.value = 1
        d.cfg_tile_off.value = 0
        d.state_clr.value = 0
        d.w_wr_en.value = 0
        d.w_wr_axon.value = 0
        d.w_wr_neuron.value = 0
        d.w_wr_data.value = 0
        d.ev_valid.value = 0
        d.ev_axon.value = 0
        d.tick_valid.value = 0
        d.out_ready.value = 1
        d.dbg_addr.value = 0
        d.dbg_wr_en.value = 0
        d.dbg_wr_v.value = 0
        d.dbg_wr_r.value = 0
        d.rst_n.value = 0
        for _ in range(3):
            await RisingEdge(d.clk)
        d.rst_n.value = 1
        await RisingEdge(d.clk)
        await Timer(SETTLE_NS, unit="ns")
        assert d.busy.value == 0, "reset must leave the core idle"
        assert d.out_valid.value == 0, "reset must clear the output register"
        cocotb.start_soon(self._spike_monitor())
        cocotb.start_soon(self._ecc_monitor())

    # -- output monitor ----------------------------------------------------

    async def _spike_monitor(self):
        """Capture every accepted output handshake.

        Sampled in the active region at the clock edge, so the values read
        are the ones the edge itself transferred (pre non-blocking update),
        exactly what a downstream aer_fifo latches.
        """
        d = self.dut
        while self._mon_on:
            await RisingEdge(d.clk)
            if d.out_valid.value == 1 and d.out_ready.value == 1:
                word = int(d.out_event.value)
                assert word >> 14 == 0, \
                    f"emitted TYPE must be SPIKE (00), got word 0x{word:04X}"
                assert (word >> 10) & 0xF == 0, \
                    f"reserved event bits must be zero, got 0x{word:04X}"
                self.spikes.append(word & 0x3FF)

    def take_spikes(self):
        got = list(self.spikes)
        self.spikes.clear()
        return got

    # -- memory ECC flag monitor --------------------------------------------

    ECC_FLAGS = ("state_sec", "state_ded", "wmem_sec", "wmem_ded")

    async def _ecc_monitor(self):
        """Count every cycle each memory ECC flag is asserted.

        The four flags are combinational level outputs qualified by the
        cycle the scan consumes the word (hw/rtl/lif_core.v), so they are
        sampled at the clock edge in the active region, the same rule the
        spike monitor follows and the same rule a register block counting
        them would follow.
        """
        d = self.dut
        while self._mon_on:
            await RisingEdge(d.clk)
            for name in self.ECC_FLAGS:
                if getattr(d, name).value == 1:
                    self.ecc[name] += 1

    def take_ecc(self):
        got = dict(self.ecc)
        for k in self.ecc:
            self.ecc[k] = 0
        return got

    # -- backpressure driver ------------------------------------------------

    def start_backpressure(self, rng, p_ready=0.5):
        self._bp_on = True
        cocotb.start_soon(self._backpressure(rng, p_ready))

    async def _backpressure(self, rng, p_ready):
        d = self.dut
        while True:
            await RisingEdge(d.clk)
            if not self._bp_on:
                d.out_ready.value = 1
                return
            d.out_ready.value = 1 if rng.random() < p_ready else 0

    async def stop_backpressure(self):
        if not self._bp_on:
            return
        self._bp_on = False
        await RisingEdge(self.dut.clk)   # let the driver restore out_ready
        await Timer(SETTLE_NS, unit="ns")

    # -- configuration, weights, state --------------------------------------

    def apply_config(self, cfg, tile_off=0):
        d = self.dut
        d.cfg_thresh.value = u16(cfg.thresh)
        d.cfg_vreset.value = u16(cfg.v_reset)
        d.cfg_leak_shift.value = cfg.leak_shift
        d.cfg_syn_shift.value = cfg.syn_shift
        d.cfg_refr.value = cfg.refr_period
        d.cfg_leak_en.value = 1 if cfg.leak_en else 0
        d.cfg_tile_off.value = tile_off

    async def load_weights(self, weights):
        """Fill the whole flip-flop synapse file, one weight per cycle."""
        d = self.dut
        for a in range(self.n_axons):
            for j in range(self.n_neurons):
                d.w_wr_axon.value = a
                d.w_wr_neuron.value = j
                d.w_wr_data.value = u4(weights[a][j])
                d.w_wr_en.value = 1
                await RisingEdge(d.clk)
        d.w_wr_en.value = 0
        await Timer(SETTLE_NS, unit="ns")

    # -- raw cycle-level helpers (directed handshake tests) -----------------

    async def cycle(self):
        """Advance one clock and settle, so combinational ports are stable."""
        await RisingEdge(self.dut.clk)
        await Timer(SETTLE_NS, unit="ns")

    async def settle(self):
        await Timer(SETTLE_NS, unit="ns")

    def idle_inputs(self):
        d = self.dut
        d.ev_valid.value = 0
        d.tick_valid.value = 0
        d.state_clr.value = 0
        d.dbg_wr_en.value = 0
        d.w_wr_en.value = 0

    async def wait_for(self, cond, limit, what):
        """Poll a condition once per cycle; fail rather than hang."""
        for _ in range(limit):
            if cond():
                return
            await self.cycle()
        assert cond(), f"{what}: not satisfied within {limit} cycles"

    async def _wait_idle(self):
        d = self.dut
        while d.busy.value == 1:
            await RisingEdge(d.clk)
            await Timer(SETTLE_NS, unit="ns")

    async def _drain_busy(self):
        """Wait out a command that has just been accepted (busy is high)."""
        d = self.dut
        while d.busy.value == 1:
            await RisingEdge(d.clk)
            await Timer(SETTLE_NS, unit="ns")

    async def state_clr(self):
        d = self.dut
        await self._wait_idle()
        d.state_clr.value = 1
        await RisingEdge(d.clk)
        d.state_clr.value = 0
        await Timer(SETTLE_NS, unit="ns")
        await self._drain_busy()

    async def read_state(self, j):
        d = self.dut
        d.dbg_addr.value = j
        await Timer(SETTLE_NS, unit="ns")
        return s16(int(d.dbg_v.value)), int(d.dbg_r.value)

    async def write_state(self, j, v, r=0):
        d = self.dut
        await self._wait_idle()
        d.dbg_addr.value = j
        d.dbg_wr_v.value = u16(v)
        d.dbg_wr_r.value = r
        d.dbg_wr_en.value = 1
        await RisingEdge(d.clk)
        d.dbg_wr_en.value = 0
        await Timer(SETTLE_NS, unit="ns")

    # -- command drivers ----------------------------------------------------

    async def send_event(self, axon):
        d = self.dut
        while d.ev_ready.value != 1:
            await RisingEdge(d.clk)
            await Timer(SETTLE_NS, unit="ns")
        d.ev_axon.value = axon
        d.ev_valid.value = 1
        await RisingEdge(d.clk)          # the accepting edge
        d.ev_valid.value = 0
        await Timer(SETTLE_NS, unit="ns")
        await self._drain_busy()

    async def send_tick(self):
        d = self.dut
        while d.tick_ready.value != 1:
            await RisingEdge(d.clk)
            await Timer(SETTLE_NS, unit="ns")
        d.tick_valid.value = 1
        await RisingEdge(d.clk)          # the accepting edge
        d.tick_valid.value = 0
        await Timer(SETTLE_NS, unit="ns")
        await self._drain_busy()

    # -- lockstep comparison -------------------------------------------------

    async def check_state(self, model, ctx):
        for j in range(self.n_neurons):
            v, r = await self.read_state(j)
            assert v == model.v[j], \
                f"{ctx}: V[{j}] RTL {v} != model {model.v[j]}"
            assert r == model.r[j], \
                f"{ctx}: R[{j}] RTL {r} != model {model.r[j]}"

    def check_spikes(self, expected, ctx):
        got = self.take_spikes()
        assert got == expected, f"{ctx}: spikes RTL {got} != model {expected}"

    async def step_event(self, model, axon, ctx):
        await self.send_event(axon)
        self.check_spikes(model.synaptic_event(axon), ctx)
        await self.check_state(model, ctx)

    async def step_tick(self, model, ctx):
        await self.send_tick()
        model.tick()
        self.check_spikes([], ctx + ": TICK must not emit")
        await self.check_state(model, ctx)

    # -- pass setup ----------------------------------------------------------

    async def reconfigure(self, weights, cfg, tile_off=0):
        """Start a new pass: load configuration and weights, STATE_CLR, and
        return a golden core in the matching post-clear state. This is the
        bring-up order of spec section 11.1 (no hardware reset needed)."""
        await self._wait_idle()
        self.apply_config(cfg, tile_off)
        await self.load_weights(weights)
        await self.state_clr()
        self.take_spikes()
        model = LIFCore(self.n_neurons, self.n_axons, weights, cfg,
                        tile_offset=tile_off)
        await self.check_state(model, "after STATE_CLR")
        return model


async def setup(dut, weights, cfg, tile_off=0):
    """Reset the DUT and bring up an identically configured golden core.

    Called once per cocotb test: it starts the clock, and cocotb reaps the
    clock task when the test ends. Further passes inside one test go
    through LifHarness.reconfigure so only one clock driver ever exists.
    """
    h = LifHarness(dut)
    await h.start()
    model = await h.reconfigure(weights, cfg, tile_off)
    return h, model


# -- bring-up ----------------------------------------------------------------

@cocotb.test()
async def test_state_clr_zeroes_the_state_file(dut):
    """CTRL.STATE_CLR gives the post-clear state of spec section 3
    (V = 0, R = 0 everywhere), which is where the golden model starts."""
    cfg = LIFConfig(thresh=256)
    h, model = await setup(dut, zeros(int(dut.N_AXONS.value),
                                      int(dut.N_NEURONS.value)), cfg)
    for j in range(h.n_neurons):
        assert await h.read_state(j) == (0, 0)
    # A second clear after real traffic must return to the same state.
    await h.write_state(0, 1234, 5)
    await h.state_clr()
    model.reset_state()
    await h.check_state(model, "second STATE_CLR")
    h.check_spikes([], "STATE_CLR must not emit")


# -- E3 saturation, both rails, and the spike a wraparound would lose ---------

@cocotb.test()
async def test_e3_negative_rail_clamps_no_wraparound(dut):
    """(E3) inhibition drives V to exactly -32768 and holds it there.
    A two's complement wrap would turn the rail into a large positive
    value and fire a spurious spike (sw/tests test_e3_negative_rail_*)."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = zeros(n_ax, n_ne)
    w[0][0] = -8                                   # c = -1024 at S_SYN = 7
    cfg = LIFConfig(thresh=V_MAX, syn_shift=7, leak_en=False)
    h, model = await setup(dut, w, cfg)
    for k in range(32):                            # 32 * -1024 = -32768
        await h.step_event(model, 0, f"neg rail event {k}")
    assert model.v[0] == V_MIN
    assert (await h.read_state(0))[0] == V_MIN, "RTL missed the negative rail"
    for k in range(40):                            # clamped, never wraps
        await h.step_event(model, 0, f"neg rail hold {k}")
    assert (await h.read_state(0))[0] == V_MIN


@cocotb.test()
async def test_e3_positive_overflow_saturates_then_spikes(dut):
    """(E3)+(E4) the wraparound case from sw/tests: after 36 events of
    +896 the 37th sums to 33152, saturates to +32767 and must spike at
    THETA = 32767. An unsaturated 16-bit wrap would give -32384 and lose
    the spike silently."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = zeros(n_ax, n_ne)
    w[0][0] = 7                                    # c = +896 at S_SYN = 7
    cfg = LIFConfig(thresh=V_MAX, syn_shift=7, leak_en=False)
    h, model = await setup(dut, w, cfg)
    for k in range(36):
        await h.step_event(model, 0, f"pos rail event {k}")
    assert model.v[0] == 32256
    assert (await h.read_state(0))[0] == 32256
    await h.step_event(model, 0, "saturating event")   # spike, then reset
    assert (await h.read_state(0))[0] == 0
    # The positive rail itself: with V_RESET one below THETA the neuron is
    # re-armed after every spike, so it saturates and fires on every event.
    cfg2 = LIFConfig(thresh=V_MAX, syn_shift=7, v_reset=V_MAX - 1,
                     leak_en=False)
    model2 = await h.reconfigure(w, cfg2)
    await h.write_state(0, V_MAX - 1)
    model2.set_state(0, V_MAX - 1)
    for k in range(8):
        await h.step_event(model2, 0, f"pos rail hold {k}")
    assert (await h.read_state(0))[0] == V_MAX - 1


# -- E4 threshold check runs after the update, even on a zero contribution ----

@cocotb.test()
async def test_e4_check_after_update_and_on_zero_contribution(dut):
    """(E4) the compare uses the just-updated value, on every non-gated
    event including c == 0. A debug state write above THETA therefore
    fires on the next event touching that neuron."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = zeros(n_ax, n_ne)
    w[0][1] = 7
    cfg = LIFConfig(thresh=7, leak_en=False)
    h, model = await setup(dut, w, cfg)
    # neuron 1 crosses on the very first event, not one event later
    await h.step_event(model, 0, "immediate spike")
    # neuron 0 has weight 0: the check still runs on it
    await h.write_state(0, 7)
    model.set_state(0, 7)
    await h.step_event(model, 0, "zero-contribution spike")


# -- E6 leak toward zero -----------------------------------------------------

@cocotb.test()
async def test_e6_leak_toward_zero_on_negative_membranes(dut):
    """(E6) the sign never flips and the minimum step of 1 drives every
    nonzero potential to zero in bounded time; the sequence for V = -5 at
    S_LEAK = 1 is the hand-computed one from sw/tests."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    cfg = LIFConfig(thresh=V_MAX, leak_shift=1)
    h, model = await setup(dut, zeros(n_ax, n_ne), cfg)
    await h.write_state(0, -5)
    model.set_state(0, -5)
    await h.write_state(1, 5)
    model.set_state(1, 5)
    seen = []
    for k in range(10):
        await h.step_tick(model, f"leak tick {k}")
        seen.append((await h.read_state(0))[0])
    assert seen == [-3, -2, -1, 0, 0, 0, 0, 0, 0, 0], seen


@cocotb.test()
async def test_e6_leak_at_full_negative_magnitude(dut):
    """(E6) |-32768| = 32768 is evaluated at 16-bit unsigned width:
    S_LEAK = 0 clears the rail in one tick, S_LEAK = 15 moves it by
    exactly one step. A signed-magnitude bug would move it the wrong way
    or overflow."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    cfg0 = LIFConfig(thresh=V_MAX, leak_shift=0)
    h, model = await setup(dut, zeros(n_ax, n_ne), cfg0)
    await h.write_state(0, V_MIN)
    model.set_state(0, V_MIN)
    await h.write_state(1, V_MAX)
    model.set_state(1, V_MAX)
    await h.step_tick(model, "S_LEAK=0 clears in one tick")
    assert (await h.read_state(0)) == (0, 0)

    cfg15 = LIFConfig(thresh=V_MAX, leak_shift=15)
    model2 = await h.reconfigure(zeros(n_ax, n_ne), cfg15)
    await h.write_state(0, V_MIN)
    model2.set_state(0, V_MIN)
    await h.step_tick(model2, "S_LEAK=15 minimum step at the rail")
    assert (await h.read_state(0))[0] == V_MIN + 1

    # bounded return to rest from full scale at the spec 11.3 working point
    cfg3 = LIFConfig(thresh=V_MAX, leak_shift=3)
    model3 = await h.reconfigure(zeros(n_ax, n_ne), cfg3)
    await h.write_state(0, V_MAX)
    model3.set_state(0, V_MAX)
    for k in range(120):
        await h.step_tick(model3, f"decay tick {k}")
        if model3.v[0] == 0:
            break
    assert model3.v[0] == 0
    assert (await h.read_state(0))[0] == 0


@cocotb.test()
async def test_tick_never_emits(dut):
    """spec section 4.2: TICK processing emits nothing, even from a state
    parked just under threshold."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    cfg = LIFConfig(thresh=10, leak_shift=3)
    h, model = await setup(dut, zeros(n_ax, n_ne), cfg)
    for j in range(h.n_neurons):
        await h.write_state(j, 9)
        model.set_state(j, 9)
    for k in range(12):
        await h.step_tick(model, f"silent tick {k}")


# -- E7 refractory -----------------------------------------------------------

@cocotb.test()
async def test_e7_refractory_gates_and_counts_down(dut):
    """(E7) events during refractory are discarded with no state change;
    TICK decrements R; integration resumes when R reaches zero. Mirrors
    sw/tests test_e7_refractory_gates_and_counts_down."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = zeros(n_ax, n_ne)
    w[0][0] = 7                                   # c = 56 at S_SYN = 3
    cfg = LIFConfig(thresh=50, syn_shift=3, refr_period=2, leak_en=False)
    h, model = await setup(dut, w, cfg)
    await h.step_event(model, 0, "spike loads R")
    assert (await h.read_state(0)) == (0, 2)
    await h.step_event(model, 0, "gated event 1")
    assert (await h.read_state(0)) == (0, 2), "gated event changed state"
    await h.step_tick(model, "countdown 1")
    assert (await h.read_state(0)) == (0, 1)
    await h.step_event(model, 0, "gated event 2")
    await h.step_tick(model, "countdown 2")
    assert (await h.read_state(0)) == (0, 0)
    await h.step_event(model, 0, "refractory released")
    assert model.v[0] == 0


@cocotb.test()
async def test_e7_leak_applies_during_refractory(dut):
    """(E6)/(E7) leak is independent of R: V decays while the neuron is
    refractory (sw/tests test_e7_leak_applies_during_refractory)."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = zeros(n_ax, n_ne)
    w[0][0] = 7
    cfg = LIFConfig(thresh=50, syn_shift=3, refr_period=3, v_reset=40,
                    leak_shift=1)
    h, model = await setup(dut, w, cfg)
    await h.step_event(model, 0, "spike to V_RESET = 40")
    assert (await h.read_state(0)) == (40, 3)
    await h.step_tick(model, "leak during refractory")
    assert (await h.read_state(0)) == (20, 2)


# -- E5 / E9 tile offset -----------------------------------------------------

@cocotb.test()
async def test_e5_tile_offset_in_emitted_ids(dut):
    """(E5)(E9) the emitted id is TILE_OFF + j, in ascending scan order
    (E8). Checked at a mid-range offset and at the top of the frozen
    10-bit id field, where the last neuron must emit exactly 1023.

    The mid-range offset is derived from the geometry, not fixed: the
    legal range is [0, 1024 - N_NEURONS] (spec section 9), so a hardcoded
    32 would make this test unbuildable for N_NEURONS >= 993 -- inside
    the specification's own 1..1024 range."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = zeros(n_ax, n_ne)
    w[0][0] = 7
    w[0][1] = 7
    w[0][n_ne - 1] = 7
    cfg = LIFConfig(thresh=7, leak_en=False)
    mid = min(32, 1024 - n_ne)                    # legal at every geometry
    h, model = await setup(dut, w, cfg, tile_off=mid)
    await h.send_event(0)
    expect = model.synaptic_event(0)
    assert expect == [mid, mid + 1, mid + n_ne - 1], expect
    h.check_spikes(expect, f"tile_off = {mid}")
    await h.check_state(model, f"tile_off = {mid}")

    top = 1024 - n_ne                             # largest legal offset
    model2 = await h.reconfigure(w, cfg, tile_off=top)
    await h.send_event(0)
    expect2 = model2.synaptic_event(0)
    assert expect2[-1] == 1023, expect2
    h.check_spikes(expect2, "tile_off at the 10-bit boundary")
    await h.check_state(model2, "tile_off at the 10-bit boundary")


@cocotb.test()
async def test_e9_partial_tile_matches_a_narrower_core(dut):
    """(E9) a tile narrower than the physical core is run by zeroing the
    unused weight columns, not by a runtime neuron count. The emitted
    stream must then be bit-identical to a golden core built at exactly
    the tile width, and the unused neurons must stay at rest forever.
    This is the property the missing CFG_NEUR port relies on.

    The offset is derived from the geometry for the same reason as in
    test_e5_tile_offset_in_emitted_ids: a hardcoded 64 would fail to
    construct for N_NEURONS >= 961."""
    rng = random.Random(4711)
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    width = max(1, n_ne - (n_ne // 4))            # partial tile width
    tile_off = min(64, 1024 - n_ne)               # legal at every geometry
    w_full = [[rng.randrange(-8, 8) if j < width else 0
               for j in range(n_ne)] for _ in range(n_ax)]
    cfg = LIFConfig(thresh=17, v_reset=-2, leak_shift=2, syn_shift=3,
                    refr_period=1, leak_en=True)
    h = LifHarness(dut)
    await h.start()
    await h.reconfigure(w_full, cfg, tile_off=tile_off)
    narrow = LIFCore(width, n_ax, [row[:width] for row in w_full], cfg,
                     tile_offset=tile_off)
    emitted = 0
    for step in range(300):
        ctx = f"partial tile step {step}"
        if rng.random() < 0.75:
            axon = rng.randrange(n_ax)
            await h.send_event(axon)
            expect = narrow.synaptic_event(axon)
        else:
            await h.send_tick()
            narrow.tick()
            expect = []
        emitted += len(expect)
        h.check_spikes(expect, ctx)
        for j in range(width):                    # in-tile neurons track
            assert await h.read_state(j) == (narrow.v[j], narrow.r[j]), \
                f"{ctx}: neuron {j} diverged from the narrow core"
        for j in range(width, n_ne):              # unused neurons stay at rest
            assert await h.read_state(j) == (0, 0), \
                f"{ctx}: unused neuron {j} left the rest state"
    assert emitted > 0, "partial-tile stimulus never spiked"


# -- E8 scan order and back-to-back traffic ----------------------------------

@cocotb.test()
async def test_e8_emissions_are_in_ascending_scan_order(dut):
    """(E8) within one synaptic event the emissions come out in ascending
    neuron index, whatever the weight pattern."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = zeros(n_ax, n_ne)
    for j in range(n_ne):
        w[3][j] = 7 if j % 3 == 0 else 0
    cfg = LIFConfig(thresh=7, leak_en=False)
    h, model = await setup(dut, w, cfg)
    await h.send_event(3)
    expect = model.synaptic_event(3)
    assert expect == sorted(expect) and expect == list(range(0, n_ne, 3))
    h.check_spikes(expect, "ascending scan order")
    await h.check_state(model, "ascending scan order")


@cocotb.test()
async def test_back_to_back_events_on_one_neuron(dut):
    """Consecutive events on the same neuron with no idle time between
    them: every event spikes at T_REFR = 0, every second event spikes at
    THETA = 2 * c, and with T_REFR = 2 the refractory gate takes over."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = zeros(n_ax, n_ne)
    w[0][0] = 7
    h = LifHarness(dut)
    await h.start()
    for thresh, refr, label in ((7, 0, "every event"),
                                (14, 0, "every second event"),
                                (7, 2, "refractory gated")):
        cfg = LIFConfig(thresh=thresh, refr_period=refr, leak_en=False)
        model = await h.reconfigure(w, cfg)
        spiked = 0
        for k in range(40):
            await h.send_event(0)
            emitted = model.synaptic_event(0)
            spiked += len(emitted)
            h.check_spikes(emitted, f"{label}: event {k}")
            await h.check_state(model, f"{label}: event {k}")
        if label == "every event":
            assert spiked == 40, spiked
            assert model.v[0] == 0
        elif label == "every second event":
            assert spiked == 20, spiked
        else:
            assert 0 < spiked < 40, spiked


# -- output backpressure -----------------------------------------------------

@cocotb.test()
async def test_backpressure_loses_no_spike(dut):
    """spec section 7.2: a full output queue stalls the pipeline, it never
    drops a spike. Every neuron spikes on every event, so each event
    produces N_NEURONS emissions that must all survive random
    backpressure, in order."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = [[7] * n_ne for _ in range(n_ax)]
    cfg = LIFConfig(thresh=7, leak_en=False)
    h, model = await setup(dut, w, cfg)
    rng = random.Random(20260825)
    h.start_backpressure(rng, p_ready=0.35)
    for k in range(12):
        await h.step_event(model, k % n_ax, f"backpressured event {k}")
    await h.stop_backpressure()
    for k in range(4):
        await h.step_event(model, 0, f"post-backpressure event {k}")


# -- command arbitration and input handshake ---------------------------------
#
# The lockstep comparison above constrains the arithmetic and the neuron
# state file, and nothing else. The golden model has no notion of
# valid/ready, of an arbiter, or of a stall, and the lockstep drivers wait
# politely for each ready before asserting a valid, so they never present
# the arbiter with a decision to make. A mutation experiment made that
# concrete: five independent mutants of ev_ready, tick_ready, the
# state_clr priority and the held-spike interaction all survived the
# entire lockstep suite. The tests below drive the cases the lockstep
# drivers cannot reach, and each one names the mutant it kills. The same
# properties are proven over the whole input space by formal/lif_ctrl.sby.

@cocotb.test()
async def test_arbitration_state_clr_outranks_both_channels(dut):
    """(spec 4.3 E8 rule 1, RTL contract) STATE_CLR is the top priority.
    Presented together with a synaptic event and a tick, it must win, and
    both input channels must show ready low so the source does not
    believe its event was taken.

    Kills two mutants: ev_ready dropping its !state_clr qualifier (the
    ready assertions below), and an arbiter that lets the event outrank
    the clear (the state file is then never cleared, and the event emits
    a spike that must not exist)."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = zeros(n_ax, n_ne)
    w[0][0] = 7
    cfg = LIFConfig(thresh=7, leak_en=False)
    h, model = await setup(dut, w, cfg)
    d = dut

    # Two witnesses that a clear really ran. Neuron 1 is left refractory,
    # so a mis-arbitrated synaptic event would gate it and leave V behind.
    await h.write_state(0, 1234, 0)
    await h.write_state(1, -77, 2)
    await h._wait_idle()

    d.ev_axon.value = 0
    d.ev_valid.value = 1
    d.tick_valid.value = 1
    d.state_clr.value = 1
    await h.settle()
    assert d.ev_ready.value == 0, \
        "ev_ready must be low while STATE_CLR is requested"
    assert d.tick_ready.value == 0, \
        "tick_ready must be low while STATE_CLR is requested"

    await RisingEdge(d.clk)          # the edge that consumes the clear
    h.idle_inputs()
    await h.settle()

    # Nothing is accepted for the whole clear scan.
    for k in range(n_ne):
        assert d.ev_ready.value == 0 and d.tick_ready.value == 0, \
            f"a command was offered a grant during the clear, cycle {k}"
        await h.cycle()
    await h._wait_idle()

    model.reset_state()
    await h.check_state(model, "STATE_CLR won the arbitration")
    h.check_spikes([], "the coincident event must not have been processed")

    # The core is alive afterwards: the same event now runs normally.
    await h.step_event(model, 0, "event after the arbitrated clear")


@cocotb.test()
async def test_arbitration_spike_outranks_tick_and_loses_neither(dut):
    """(spec 4.3 E8) SPIKE outranks TICK. With both channels driven the
    event must be granted and the tick must NOT be, because the core can
    only run one command and a granted-but-unrun tick is a lost event.

    The check is end-to-end, not just a ready assertion: the test models
    the source, applying model.tick() exactly when it observes a
    completed tick handshake. A tick_ready that forgets its !ev_valid
    qualifier therefore shows up twice -- as the assertion below, and as
    a neuron state file that has leaked one tick more than the RTL."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = zeros(n_ax, n_ne)
    w[0][0] = 7
    w[0][2] = 7
    cfg = LIFConfig(thresh=7, v_reset=-4, leak_shift=1, leak_en=True)
    h, model = await setup(dut, w, cfg)
    d = dut
    await h.write_state(1, -60, 0)
    model.set_state(1, -60, 0)
    await h._wait_idle()

    d.ev_axon.value = 0
    d.ev_valid.value = 1
    d.tick_valid.value = 1
    await h.settle()
    assert d.ev_ready.value == 1, \
        "an idle core must grant the offered synaptic event"
    assert d.tick_ready.value == 0, \
        "a tick offered together with an event must not also be granted"

    await RisingEdge(d.clk)          # the accepting edge
    ev_taken = (d.ev_valid.value == 1 and d.ev_ready.value == 1)
    tick_taken = (d.tick_valid.value == 1 and d.tick_ready.value == 1)
    h.idle_inputs()
    await h.settle()
    assert ev_taken, "the event handshake did not complete"

    expect = model.synaptic_event(0) if ev_taken else []
    if tick_taken:                    # a source that saw a grant expects it
        model.tick()
    await h._drain_busy()
    h.check_spikes(expect, "SPIKE over TICK")
    await h.check_state(
        model, "SPIKE over TICK: a granted tick must also have been run")

    # The tick is served as soon as it is the only offer.
    await h.step_tick(model, "tick after the event")


@cocotb.test()
async def test_no_deadlock_with_both_channels_held(dut):
    """Deadlock freedom at the input interface, and the documented
    consequence of the hard priority.

    With ev_valid and tick_valid held high forever the core must keep
    making progress on the event channel -- an arbiter that made the two
    readys mutually exclusive would leave both low and stall the core
    permanently. The tick is starved for as long as an event is offered;
    that is the SPIKE-over-TICK deviation recorded in the RTL header, and
    the reason the host must serialize the two channels. Once ev_valid
    drops, the tick is granted immediately.

    Kills the mutant that qualifies ev_ready with !tick_valid."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    cfg = LIFConfig(thresh=V_MAX, leak_en=False)    # quiet: no emissions
    h, _ = await setup(dut, zeros(n_ax, n_ne), cfg)
    d = dut

    d.ev_axon.value = 0
    d.ev_valid.value = 1
    d.tick_valid.value = 1
    await h.settle()
    accepted = 0
    budget = 5 * (n_ne + 2)
    for _ in range(budget):
        await RisingEdge(d.clk)
        if d.ev_valid.value == 1 and d.ev_ready.value == 1:
            accepted += 1
        assert d.tick_ready.value == 0, \
            "tick_ready rose while a synaptic event was still offered"
    await h.settle()
    assert accepted >= 3, (
        f"only {accepted} events accepted in {budget} cycles with both "
        "channels held: the input interface is not making progress")

    d.ev_valid.value = 0                       # tick_valid stays high
    await h.settle()
    await h.wait_for(lambda: d.tick_ready.value == 1, n_ne + 4,
                     "tick_ready after ev_valid dropped")
    await RisingEdge(d.clk)                    # the tick accepting edge
    d.tick_valid.value = 0
    await h.settle()
    await h._drain_busy()
    h.check_spikes([], "no emission from this stimulus")


@cocotb.test()
async def test_held_spike_does_not_swallow_state_clr(dut):
    """(RTL contract) A spike still waiting in the output holding register
    does not block STATE_CLR: the clear runs and the held spike drains
    normally afterwards. The pulse is not queued, so a clear that the
    core declined to sample here would be lost outright.

    Kills the mutant that qualifies the clear with !out_pend."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = zeros(n_ax, n_ne)
    w[0][n_ne - 1] = 7                 # only the last neuron spikes
    cfg = LIFConfig(thresh=7, v_reset=-5, refr_period=3, leak_en=False)
    h, model = await setup(dut, w, cfg)
    d = dut

    d.out_ready.value = 0              # the sink refuses everything
    await h.settle()
    await h.wait_for(lambda: d.ev_ready.value == 1, n_ne + 4, "idle core")
    d.ev_axon.value = 0
    d.ev_valid.value = 1
    await RisingEdge(d.clk)
    h.idle_inputs()
    await h.settle()

    # The scan retires with the spike still held: the FSM is back in idle
    # (ev_ready high) but busy stays high because the output is occupied.
    await h.wait_for(
        lambda: d.ev_ready.value == 1 and d.out_valid.value == 1,
        2 * n_ne + 8, "scan retired with a spike still held")
    assert d.busy.value == 1, "a held spike must keep busy asserted"
    assert (await h.read_state(n_ne - 1)) == (-5, 3), \
        "the last neuron did not spike"

    d.state_clr.value = 1              # the clear, while the spike waits
    await RisingEdge(d.clk)
    d.state_clr.value = 0
    await h.settle()
    for _ in range(n_ne + 4):
        await h.cycle()
    assert d.out_valid.value == 1, "the held spike was dropped by the clear"
    for j in range(n_ne):
        assert await h.read_state(j) == (0, 0), \
            f"STATE_CLR was swallowed by the held spike: neuron {j}"

    d.out_ready.value = 1              # release: the spike drains intact
    await h.cycle()
    await h._wait_idle()
    # tile_off is 0 for this pass, so the id is the neuron index itself.
    h.check_spikes([n_ne - 1], "the held spike drained after the clear")


@cocotb.test()
async def test_no_command_is_granted_while_one_is_in_flight(dut):
    """(spec 4.3 E8 rule 1) All neuron updates for command k complete
    before command k+1 begins. At the interface that means both readys
    are low for every cycle of every scan -- event, tick and clear."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = zeros(n_ax, n_ne)
    w[0][0] = 7
    cfg = LIFConfig(thresh=7, leak_en=False)
    h, _ = await setup(dut, w, cfg)
    d = dut

    async def watch_scan(start, label):
        await h.wait_for(lambda: d.ev_ready.value == 1, n_ne + 4, label)
        start()
        await RisingEdge(d.clk)          # the accepting edge
        h.idle_inputs()
        await h.settle()
        seen = 0
        while d.busy.value == 1:
            assert d.ev_ready.value == 0, f"{label}: ev_ready rose mid-scan"
            assert d.tick_ready.value == 0, \
                f"{label}: tick_ready rose mid-scan"
            seen += 1
            await h.cycle()
        assert seen >= n_ne - 1, \
            f"{label}: scan lasted {seen} cycles, expected about {n_ne}"

    def start_event():
        d.ev_axon.value = 0
        d.ev_valid.value = 1

    def start_tick():
        d.tick_valid.value = 1

    def start_clear():
        d.state_clr.value = 1

    await watch_scan(start_event, "synaptic event")
    h.take_spikes()
    await watch_scan(start_tick, "tick")
    await watch_scan(start_clear, "state clear")
    h.check_spikes([], "tick and clear emit nothing")


@cocotb.test()
async def test_output_handshake_never_retracts_or_mutates(dut):
    """(spec 7.2) The output side obeys valid/ready: once out_valid is
    asserted it stays asserted, and out_event is frozen, until out_ready
    takes the word. Sampled on every cycle of a fully backpressured scan
    in which every neuron spikes."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = [[7] * n_ne for _ in range(n_ax)]
    cfg = LIFConfig(thresh=7, leak_en=False)
    h, model = await setup(dut, w, cfg)
    d = dut

    d.out_ready.value = 0
    await h.settle()
    await h.wait_for(lambda: d.ev_ready.value == 1, n_ne + 4, "idle core")
    d.ev_axon.value = 0
    d.ev_valid.value = 1
    await RisingEdge(d.clk)
    h.idle_inputs()
    await h.settle()

    prev_valid, prev_event, held = 0, None, 0
    for _ in range(3 * n_ne + 16):
        await h.cycle()
        v = int(d.out_valid.value)
        e = int(d.out_event.value)
        if prev_valid:
            assert v == 1, "out_valid retracted without out_ready"
            assert e == prev_event, "the held event word changed"
            held += 1
        prev_valid, prev_event = v, e
    assert held >= 4, f"the output only stalled for {held} cycles"

    d.out_ready.value = 1
    await h.cycle()
    await h._wait_idle()
    h.check_spikes(model.synaptic_event(0), "backpressured event drained")
    await h.check_state(model, "backpressured event drained")


@cocotb.test()
async def test_debug_write_outside_idle_is_dropped_not_raced(dut):
    """(RTL contract) The debug state write is interlocked: the vmem/rmem
    write lives inside the S_IDLE arm of the FSM, so a write issued
    mid-scan cannot race the scan's own write-back. Its failure mode is a
    dropped write, and this test pins that down -- the addressed neuron
    (not the one the scan is updating) keeps exactly the value it had."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    # All-zero weights and an unreachable threshold, so the occupying scan
    # is a no-op on every neuron: any change to the state file during it
    # can only have come from the debug port. Neuron 2 is left refractory
    # as well, so E7 gates it even from the scan's own write-back.
    cfg = LIFConfig(thresh=V_MAX, leak_en=False)
    h, _ = await setup(dut, zeros(n_ax, n_ne), cfg)
    d = dut

    await h.write_state(2, 4242, 7)
    assert (await h.read_state(2)) == (4242, 7)

    await h.wait_for(lambda: d.ev_ready.value == 1, n_ne + 4, "idle core")
    d.ev_axon.value = 0
    d.ev_valid.value = 1
    await RisingEdge(d.clk)
    h.idle_inputs()
    await h.settle()
    assert d.busy.value == 1, "the occupying scan did not start"

    d.dbg_addr.value = 2
    d.dbg_wr_v.value = u16(-1)
    d.dbg_wr_r.value = 0
    d.dbg_wr_en.value = 1
    for _ in range(max(2, n_ne // 2)):
        await h.cycle()
    d.dbg_wr_en.value = 0
    await h._wait_idle()
    assert (await h.read_state(2)) == (4242, 7), \
        "a mid-scan debug write reached the state file"

    # In idle the same write does land.
    await h.write_state(2, -1, 0)
    assert (await h.read_state(2)) == (-1, 0)


# -- FSM fault response (spec section 11.4) ----------------------------------

S_IDLE_ENC = 0b0000
S_SAFE_ENC = 0b1001
ILLEGAL_ENCODINGS = [0b0001, 0b0010, 0b0100, 0b1000,
                     0b0111, 0b1011, 0b1101, 0b1110,
                     0b1010, 0b1100, 0b1111]


@cocotb.test()
async def test_safe_state_on_corrupted_fsm_encoding(dut):
    """(spec section 11.4) Default-case recovery goes to a SAFE state that
    latches STATUS.ERR_CFG -- it does not resume silently in IDLE.

    The FSM uses five even-parity codewords of a 4-bit vector, so every
    single-bit upset lands on an odd-parity word that no legal transition
    can produce. This test injects each of those, plus the three unused
    even-parity words, directly into the state register (the upset the
    encoding exists for cannot be produced from the ports) and checks the
    full SAFE contract: parked, ERR_CFG asserted, busy, both input
    channels refusing, neuron state frozen, nothing emitted. Only reset
    leaves the state -- CTRL.SOFT_RST in the pilot integration.

    The same behavior is proven over an arbitrary starting encoding by
    formal/lif_ctrl_props.v H8; this test is the concrete trace, which no
    reset-rooted formal cover task can produce."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = zeros(n_ax, n_ne)
    w[0][0] = 7
    cfg = LIFConfig(thresh=7, leak_en=False)
    h, _ = await setup(dut, w, cfg)
    d = dut

    for enc in ILLEGAL_ENCODINGS:
        # Fresh, known-good starting point for each injection.
        d.rst_n.value = 0
        await h.cycle()
        d.rst_n.value = 1
        await h.cycle()
        await h.state_clr()
        await h.write_state(0, 999, 4)
        await h._wait_idle()
        assert d.err_cfg.value == 0, "reset must clear ERR_CFG"
        h.take_spikes()

        d.state.value = enc                    # the injected upset
        await h.settle()
        assert int(d.state.value) == enc, "state deposit did not take"

        await RisingEdge(d.clk)                # the edge that sees it
        await h.settle()
        assert int(d.state.value) == S_SAFE_ENC, (
            f"encoding 0b{enc:04b} recovered to 0b{int(d.state.value):04b}, "
            "expected the SAFE state 0b1001")
        assert d.err_cfg.value == 1, \
            f"encoding 0b{enc:04b} did not latch ERR_CFG"

        # Parked: no command is accepted, nothing is emitted, state frozen.
        d.ev_axon.value = 0
        d.ev_valid.value = 1
        d.tick_valid.value = 1
        d.state_clr.value = 1
        for _ in range(2 * n_ne + 6):
            assert d.ev_ready.value == 0, "SAFE state granted an event"
            assert d.tick_ready.value == 0, "SAFE state granted a tick"
            assert d.busy.value == 1, "SAFE state dropped busy"
            assert d.err_cfg.value == 1, "ERR_CFG is not sticky"
            assert int(d.state.value) == S_SAFE_ENC, "SAFE state was left"
            await h.cycle()
        h.idle_inputs()
        await h.settle()
        assert (await h.read_state(0)) == (999, 4), \
            "the neuron state file moved while parked in SAFE"
        h.check_spikes([], "SAFE state emitted something")

        # Only reset leaves it.
        d.rst_n.value = 0
        await h.cycle()
        d.rst_n.value = 1
        await h.cycle()
        assert int(d.state.value) == S_IDLE_ENC, "reset did not reach IDLE"
        assert d.err_cfg.value == 0, "reset did not clear ERR_CFG"
        assert d.busy.value == 0, "reset did not leave the core idle"

    # The core is fully functional after the recovery.
    model = await h.reconfigure(w, cfg)
    for k in range(4):
        await h.step_event(model, 0, f"event after SAFE recovery {k}")


# -- memory ECC fault response (lif_core.v, MEMORY HARDENING) ----------------
#
# The docs/16 fault-injection campaign ranked lif_core's three memory
# files as the whole residual silent-corruption risk of the pilot: wmem
# 56.2% SDC over 256 flip-flops, vmem 91.7% over 128, rmem 100.0% over
# 32. The tests below inject exactly the fault that campaign injects --
# one stored bit, XORed 3 ns past a clock edge so the deposit is not
# overwritten by the same edge's non-blocking update -- into each of the
# five coded structures, and check that the protection acts.
#
# What "acts" means is stated per structure rather than in general,
# because the two files answer differently:
#   vmem, rmem, smem   corrected on both read ports, announced on
#                      state_sec, AND scrubbed: the next scan that visits
#                      the neuron writes the corrected word back, so the
#                      raw storage is repaired, not merely masked. That
#                      last part is checked against the RAW array, not
#                      through dbg_v, because dbg_v reads through the
#                      decoder and would look right either way.
#   wmem, wchk         corrected on the read the datapath uses and
#                      announced on wmem_sec. The scan never writes wmem,
#                      so there is no scrub; the raw array stays wrong
#                      until the host reloads the image, which is checked
#                      too.
# Double-bit errors are checked separately: the synapse file degrades to
# the E10 zero substitution of docs/10 section 11.2, bit-exact against a
# golden core with that word poisoned, and the neuron state file reports
# without inventing a substitution it has no golden reference for.
#
# Every case also asserts that the deposit LANDED (the raw storage really
# differs from the golden value before the correction is checked). Without
# that, a test whose handle path was wrong would pass by doing nothing --
# the honesty check docs/16 section 1.8 makes of the campaign itself.


async def deposit(dut, handle, bits):
    """XOR one or more bits into a storage element, 3 ns past an edge.

    Off the edge on purpose: a deposit made AT the edge is overwritten by
    that same edge's non-blocking update before anything samples it, so
    the injection silently does nothing. Same rule, same offset, as
    hw/tb/test_fi_campaign.py.
    """
    await RisingEdge(dut.clk)
    await Timer(3, unit="ns")
    v = int(handle.value)
    for b in bits:
        v ^= 1 << b
    handle.value = v
    await Timer(SETTLE_NS, unit="ns")


def state_word_bits(j, bit):
    """Bit index inside the flat smem check field of neuron j."""
    return j * 6 + bit


def weight_word(lin):
    """SECDED codeword index of linear synapse index lin.

    16 weights per codeword, which is WEIGHTS_PER_WORD and word_index() in
    sw/golden/lif_core.py -- the same word the model poisons.
    """
    return lin // 16


@cocotb.test()
async def test_ecc_single_bit_upset_in_vmem_is_corrected_and_scrubbed(dut):
    """(MEMORY HARDENING) A single flipped bit anywhere in a membrane
    potential is corrected on both read ports, announced, and repaired in
    place by the next scan.

    Four bit positions are walked: bit 0 (the one the campaign found the
    leak quantisation could sometimes absorb by accident), bits 4 and 11,
    and bit 15, the sign bit, whose flip is the largest error the word can
    carry and which no leak can mask."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    cfg = LIFConfig(thresh=1000, v_reset=-4, leak_shift=3, syn_shift=1,
                    refr_period=2, leak_en=True)
    h, model = await setup(dut, random_weights(random.Random(7), n_ax, n_ne),
                           cfg)
    for k, bit in enumerate((0, 4, 11, 15)):
        j = k % n_ne
        # A distinct, nonzero starting potential per neuron, so a fault
        # that writes the right value to the wrong neuron cannot pass.
        for m in range(n_ne):
            v = -300 - 37 * m
            await h.write_state(m, v, 0)
            model.set_state(m, v, 0)
        h.take_ecc()

        await deposit(dut, dut.vmem[j], (bit,))
        assert int(dut.vmem[j].value) != u16(model.v[j]), \
            f"the deposit into vmem[{j}] bit {bit} did not land"

        # Corrected on the debug read port, before anything scans.
        assert (await h.read_state(j)) == (model.v[j], model.r[j]), \
            f"vmem[{j}] bit {bit}: the debug port did not correct"

        # Corrected on the scan read port: one TICK, in lockstep.
        await h.step_tick(model, f"tick after vmem[{j}] bit {bit}")
        flags = h.take_ecc()
        assert flags["state_sec"] >= 1, \
            f"vmem[{j}] bit {bit}: the correction was not announced"
        assert flags["state_ded"] == 0, \
            f"vmem[{j}] bit {bit}: a single-bit error was called uncorrectable"

        # Scrubbed: the RAW storage now holds the corrected word.
        assert int(dut.vmem[j].value) == u16(model.v[j]), \
            (f"vmem[{j}] bit {bit}: the scan masked the upset but did not "
             "write the corrected word back")
        h.take_ecc()
        await h.step_event(model, 0, f"event after vmem[{j}] bit {bit}")
        assert h.take_ecc()["state_sec"] == 0, \
            f"vmem[{j}] bit {bit}: the error was still there after the scrub"


@cocotb.test()
async def test_ecc_single_bit_upset_in_rmem_is_corrected_and_scrubbed(dut):
    """(MEMORY HARDENING) The refractory counter was the worst structure
    in the campaign -- 12 of 12 injections silently corrupted -- because R
    reads zero most of the time, so a flip almost always SETS a spurious
    refractory count, which then gates E1..E5 for that neuron on every
    following event (E7).

    Both directions are exercised: a flip that invents a refractory
    period on a running neuron, and a flip inside a real one."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    cfg = LIFConfig(thresh=64, v_reset=-8, leak_shift=3, syn_shift=2,
                    refr_period=10, leak_en=False)
    w = zeros(n_ax, n_ne)
    for m in range(n_ne):
        w[0][m] = 7                       # every neuron integrates on axon 0
    h, model = await setup(dut, w, cfg)

    for bit, r_start in ((0, 0), (1, 0), (3, 0), (0, 10), (3, 10)):
        for m in range(n_ne):
            v = 11 + 7 * m
            await h.write_state(m, v, r_start)
            model.set_state(m, v, r_start)
        j = bit % n_ne
        h.take_ecc()

        await deposit(dut, dut.rmem[j], (bit,))
        assert int(dut.rmem[j].value) != model.r[j], \
            f"the deposit into rmem[{j}] bit {bit} did not land"
        assert (await h.read_state(j)) == (model.v[j], model.r[j]), \
            f"rmem[{j}] bit {bit}: the debug port did not correct"

        # An event: without the correction a spurious R would suppress
        # this neuron's update entirely (E7), which the lockstep sees.
        await h.step_event(model, 0, f"event after rmem[{j}] bit {bit}")
        flags = h.take_ecc()
        assert flags["state_sec"] >= 1, \
            f"rmem[{j}] bit {bit}: the correction was not announced"
        assert flags["state_ded"] == 0
        assert int(dut.rmem[j].value) == u4(model.r[j]), \
            f"rmem[{j}] bit {bit}: the corrected word was not written back"


@cocotb.test()
async def test_ecc_single_bit_upset_in_the_state_check_field_is_corrected(dut):
    """(MEMORY HARDENING) The check field is storage too, and an upset in
    it must not be mistaken for an upset in the data it protects. All six
    bits of one neuron's check word are walked: five Hamming bits and the
    overall-parity bit, whose syndrome is zero and which the decoder has
    to recognise as "the parity bit itself took the hit"."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    cfg = LIFConfig(thresh=500, v_reset=0, leak_shift=2, syn_shift=0,
                    refr_period=3, leak_en=True)
    h, model = await setup(dut, zeros(n_ax, n_ne), cfg)
    for bit in range(6):
        j = bit % n_ne
        for m in range(n_ne):
            await h.write_state(m, -100 - 13 * m, (m + 1) % 4)
            model.set_state(m, -100 - 13 * m, (m + 1) % 4)
        h.take_ecc()

        before = int(dut.smem.value)
        await deposit(dut, dut.smem, (state_word_bits(j, bit),))
        assert int(dut.smem.value) != before, \
            f"the deposit into smem check bit {bit} of neuron {j} did not land"

        assert (await h.read_state(j)) == (model.v[j], model.r[j]), \
            f"smem check bit {bit}: the debug port did not correct"
        await h.step_tick(model, f"tick after smem check bit {bit}")
        flags = h.take_ecc()
        assert flags["state_sec"] >= 1, \
            f"smem check bit {bit}: the correction was not announced"
        assert flags["state_ded"] == 0
        # The scrub covers the check field as well as the data.
        h.take_ecc()
        await h.step_tick(model, f"second tick after smem check bit {bit}")
        assert h.take_ecc()["state_sec"] == 0, \
            f"smem check bit {bit}: the check field was not repaired"


@cocotb.test()
async def test_ecc_double_bit_upset_in_a_state_word_is_detected(dut):
    """(MEMORY HARDENING) Two flipped bits in one neuron's state word are
    detected and never miscorrected. There is no fail-operational
    substitution for a membrane potential -- any value this module could
    invent would be a spec deviation with no golden reference -- so the
    contract is report, not repair, and this test pins that down: the flag
    fires and the data field comes back exactly as stored."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    cfg = LIFConfig(thresh=900, v_reset=0, leak_shift=4, leak_en=True)
    h, model = await setup(dut, zeros(n_ax, n_ne), cfg)
    for pair in ((0, 5), (3, 15), (11, 12)):
        j = pair[0] % n_ne
        await h.write_state(j, -4096, 0)
        model.set_state(j, -4096, 0)
        h.take_ecc()

        await deposit(dut, dut.vmem[j], pair)
        corrupted = int(dut.vmem[j].value)
        assert corrupted != u16(model.v[j]), "the double deposit did not land"

        v_rd, r_rd = await h.read_state(j)
        assert u16(v_rd) == corrupted, \
            (f"vmem[{j}] bits {pair}: a double-bit error was silently "
             "'corrected' into a different value")
        assert r_rd == model.r[j]

        await h.send_tick()
        flags = h.take_ecc()
        assert flags["state_ded"] >= 1, \
            f"vmem[{j}] bits {pair}: the double-bit error was not detected"
        assert flags["state_sec"] == 0, \
            f"vmem[{j}] bits {pair}: a double-bit error was reported corrected"
        # Resynchronise: the host's documented recovery is STATE_CLR.
        await h.state_clr()
        model.reset_state()
        h.take_spikes()
        await h.check_state(model, "STATE_CLR after a double-bit state error")


@cocotb.test()
async def test_ecc_single_bit_upset_in_wmem_is_corrected(dut):
    """(MEMORY HARDENING) wmem is the largest structure in the design and
    the campaign's rank-1 source of expected silent corruption. A single
    flipped bit in a synapse codeword leaves the weight the datapath
    integrates equal to the weight that was loaded.

    The raw array is deliberately NOT repaired -- the scan never writes
    wmem, so nothing scrubs it -- and this test checks that too, together
    with the reload that does repair it (docs/16 section 5.4)."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    cfg = LIFConfig(thresh=40, v_reset=-2, leak_shift=3, syn_shift=2,
                    refr_period=0, leak_en=False)
    w = zeros(n_ax, n_ne)
    for m in range(n_ne):
        w[0][m] = ((m % 7) - 3) or 5
    h, model = await setup(dut, w, cfg)

    for bit in (0, 1, 2, 3):
        lin = 0 * n_ne + (bit % min(n_ne, 16))   # inside codeword 0
        j = lin % n_ne
        await h.state_clr()
        model.reset_state()
        h.take_spikes()
        h.take_ecc()

        await deposit(dut, dut.wmem[lin], (bit,))
        assert int(dut.wmem[lin].value) != u4(w[0][j]), \
            f"the deposit into wmem[{lin}] bit {bit} did not land"

        for step in range(3):
            await h.step_event(model, 0,
                               f"event {step} after wmem[{lin}] bit {bit}")
        flags = h.take_ecc()
        assert flags["wmem_sec"] >= 1, \
            f"wmem[{lin}] bit {bit}: the correction was not announced"
        assert flags["wmem_ded"] == 0, \
            f"wmem[{lin}] bit {bit}: a single-bit error was called uncorrectable"
        # No scrub on this file: the raw nibble is still wrong.
        assert int(dut.wmem[lin].value) != u4(w[0][j]), \
            "the scan wrote wmem, which it must never do"

        # The host reload repairs it, which is the documented mitigation.
        await h.load_weights(w)
        assert int(dut.wmem[lin].value) == u4(w[0][j]), \
            "a full weight reload did not repair the synapse file"
        h.take_ecc()
        await h.step_event(model, 0, f"event after reload, bit {bit}")
        assert h.take_ecc()["wmem_sec"] == 0, \
            "the reload left the codeword still carrying an error"


@cocotb.test()
async def test_ecc_single_bit_upset_in_the_weight_check_field_is_corrected(dut):
    """(MEMORY HARDENING) The synapse check field, walked across the low,
    middle and high bits of codeword 0's eight check bits."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    cfg = LIFConfig(thresh=32, v_reset=0, leak_shift=3, syn_shift=2,
                    leak_en=False)
    w = zeros(n_ax, n_ne)
    for m in range(n_ne):
        w[0][m] = 6
    h, model = await setup(dut, w, cfg)
    for bit in (0, 3, 7):
        await h.state_clr()
        model.reset_state()
        h.take_spikes()
        h.take_ecc()

        before = int(dut.wchk.value)
        await deposit(dut, dut.wchk, (bit,))
        assert int(dut.wchk.value) != before, \
            f"the deposit into wchk bit {bit} did not land"

        for step in range(3):
            await h.step_event(model, 0, f"event {step} after wchk bit {bit}")
        flags = h.take_ecc()
        assert flags["wmem_sec"] >= 1, \
            f"wchk bit {bit}: the correction was not announced"
        assert flags["wmem_ded"] == 0
        await h.load_weights(w)          # recomputes the check field


@cocotb.test()
async def test_ecc_double_bit_upset_in_a_weight_word_degrades_to_e10(dut):
    """(MEMORY HARDENING, E10) Two flipped bits in one synapse codeword
    are detected, never miscorrected, and every one of that word's sixteen
    weights contributes exactly zero from then on.

    That is docs/10 section 11.2's fail-operational substitution, and it
    is checked the only way it is worth checking: in lockstep against a
    golden core built with exactly that word poisoned. The word index is
    the same on both sides -- LIFCore.word_index() and this module's
    codeword index are both floor(linear / 16) -- which is why E10 can be
    compared at all rather than merely asserted.

    Before this hardening the lif_core header recorded E10 as having no
    hardware to attach to in the flip-flop build. It has now."""
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    cfg = LIFConfig(thresh=24, v_reset=-1, leak_shift=3, syn_shift=2,
                    refr_period=1, leak_en=True)
    w = zeros(n_ax, n_ne)
    for m in range(n_ne):
        w[0][m] = 4 + (m % 3)
        if n_ax > 1:
            w[1][m] = -2 - (m % 2)
    h, _ = await setup(dut, w, cfg)

    lin = 0
    word = weight_word(lin)
    # A golden core that has the same word poisoned from the start.
    poisoned = LIFCore(n_ne, n_ax, w, cfg)
    poisoned.poison_word(word)

    await h.state_clr()
    h.take_spikes()
    h.take_ecc()
    await deposit(dut, dut.wmem[lin], (0, 2))
    assert int(dut.wmem[lin].value) != u4(w[0][lin % n_ne]), \
        "the double deposit into wmem did not land"

    for step in range(6):
        axon = step % min(n_ax, 2)
        await h.step_event(poisoned, axon, f"E10 event {step}")
    flags = h.take_ecc()
    assert flags["wmem_ded"] >= 1, \
        "a double-bit error in a synapse codeword was not detected"
    assert flags["wmem_sec"] == 0, \
        "a double-bit error in a synapse codeword was reported corrected"

    # And the recovery: reloading the image from a protected source
    # removes the poison, and the core is bit-exact against a clean model.
    await h.load_weights(w)
    await h.state_clr()
    h.take_spikes()
    h.take_ecc()
    clean = LIFCore(n_ne, n_ax, w, cfg)
    for step in range(6):
        await h.step_event(clean, step % min(n_ax, 2),
                           f"event {step} after the E10 recovery")
    assert h.take_ecc()["wmem_ded"] == 0, \
        "the reload did not clear the uncorrectable word"


@cocotb.test()
async def test_ecc_flags_stay_silent_without_an_injected_fault(dut):
    """(MEMORY HARDENING, transparency) The whole point of the hardening
    is that it is invisible when nothing is wrong. Every other test in
    this file already checks that through the golden model; this one
    checks the other half, which the lockstep cannot see: that no ECC flag
    fires at all across a run with no injection.

    A design that reported a correction on every cycle would still pass
    every lockstep test in this suite."""
    rng = random.Random(20260826)
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    cfg = LIFConfig(thresh=48, v_reset=-6, leak_shift=2, syn_shift=3,
                    refr_period=3, leak_en=True)
    h, model = await setup(dut, random_weights(rng, n_ax, n_ne), cfg)
    h.take_ecc()
    for step in range(120):
        roll = rng.random()
        ctx = f"clean step {step}"
        if roll < 0.05:
            j = rng.randrange(n_ne)
            v = rng.randint(V_MIN, V_MAX)
            r = rng.choice([0, 1, 15])
            await h.write_state(j, v, r)
            model.set_state(j, v, r)
            h.check_spikes([], ctx)
        elif roll < 0.80:
            await h.step_event(model, rng.randrange(n_ax), ctx)
        else:
            await h.step_tick(model, ctx)
    flags = h.take_ecc()
    assert flags == {"state_sec": 0, "state_ded": 0,
                     "wmem_sec": 0, "wmem_ded": 0}, \
        f"a fault-free run raised memory ECC flags: {flags}"


# -- randomized lockstep -----------------------------------------------------

def random_config(rng):
    """A configuration inside the golden validation ranges (spec 6)."""
    thresh = rng.choice([1, 5, 17, 64, 256, 1000, 8192, V_MAX])
    v_reset = rng.choice([0, 0, -1, -100, thresh - 1, max(V_MIN, -thresh)])
    v_reset = max(V_MIN, min(v_reset, thresh - 1))
    return LIFConfig(
        thresh=thresh,
        v_reset=v_reset,
        leak_shift=rng.randrange(0, 16),
        syn_shift=rng.randrange(0, 8),
        refr_period=rng.choice([0, 0, 1, 2, 5, 15]),
        leak_en=rng.random() < 0.75,
    )


def random_weights(rng, n_axons, n_neurons, density=0.6):
    return [[rng.randrange(-8, 8) if rng.random() < density else 0
             for _ in range(n_neurons)]
            for _ in range(n_axons)]


@cocotb.test()
async def test_random_lockstep_2000_steps(dut):
    """2000 randomized steps at a fixed seed. Every step is compared: the
    emitted spike stream and the entire neuron state file.

    Occasional debug state writes park neurons on the 16-bit rails and
    just under or just over THETA, so the random walk reaches the
    saturation and leak-at-full-magnitude paths instead of hovering
    around rest, and exercises the spec 4.4 note that a state write above
    threshold fires on the next event touching that neuron."""
    rng = random.Random(20260825)
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    w = random_weights(rng, n_ax, n_ne)
    cfg = LIFConfig(thresh=64, v_reset=-8, leak_shift=3, syn_shift=3,
                    refr_period=2, leak_en=True)
    h, model = await setup(dut, w, cfg)
    extremes = [V_MIN, V_MIN + 1, -1, 0, 1, cfg.thresh - 1, cfg.thresh,
                V_MAX - 1, V_MAX]
    n_events = 0
    n_ticks = 0
    n_pokes = 0
    n_spikes = 0
    for step in range(2000):
        roll = rng.random()
        ctx = f"random step {step}"
        if roll < 0.03:
            j = rng.randrange(n_ne)
            v = rng.choice(extremes) if rng.random() < 0.7 \
                else rng.randint(V_MIN, V_MAX)
            r = rng.choice([0, 0, 0, 1, 3, 15])
            await h.write_state(j, v, r)
            model.set_state(j, v, r)
            expect = []
            n_pokes += 1
        elif roll < 0.82:
            axon = rng.randrange(n_ax)
            await h.send_event(axon)
            expect = model.synaptic_event(axon)
            n_events += 1
        else:
            await h.send_tick()
            model.tick()
            expect = []
            n_ticks += 1
        n_spikes += len(expect)
        h.check_spikes(expect, ctx)
        await h.check_state(model, ctx)
    dut._log.info(
        "random lockstep: %d events, %d ticks, %d state writes, "
        "%d spikes matched", n_events, n_ticks, n_pokes, n_spikes)
    # Stimulus-quality floor, scaled with the geometry: a run that matched
    # only because nothing ever fired would prove nothing.
    assert n_spikes > 10 * n_ne, \
        f"stimulus produced only {n_spikes} spikes, too few to be meaningful"


@cocotb.test()
async def test_random_lockstep_config_sweep(dut):
    """Six randomized configurations, weight sets and tile offsets, 250
    lockstep steps each; the last one runs under random output
    backpressure so the stall path is exercised in lockstep too."""
    rng = random.Random(861024)
    n_ax = int(dut.N_AXONS.value)
    n_ne = int(dut.N_NEURONS.value)
    total_spikes = 0
    h = LifHarness(dut)
    await h.start()
    for run in range(6):
        cfg = random_config(rng)
        w = random_weights(rng, n_ax, n_ne, density=rng.choice([0.2, 0.6, 1.0]))
        tile_off = rng.randrange(0, 1024 - n_ne + 1)
        model = await h.reconfigure(w, cfg, tile_off=tile_off)
        if run == 5:
            h.start_backpressure(rng, p_ready=0.4)
        for step in range(250):
            ctx = f"run {run} step {step}"
            if rng.random() < 0.75:
                axon = rng.randrange(n_ax)
                await h.send_event(axon)
                expect = model.synaptic_event(axon)
            else:
                await h.send_tick()
                model.tick()
                expect = []
            total_spikes += len(expect)
            h.check_spikes(expect, ctx)
            await h.check_state(model, ctx)
        await h.stop_backpressure()
    dut._log.info("config sweep: %d spikes matched", total_spikes)
    assert total_spikes > 3 * n_ne, \
        f"stimulus produced only {total_spikes} spikes across the sweep"
