"""Weight-SRAM ECC scrub controller suite (hw/rtl/scrub.v).

Two different things are checked here.

1. LOCKSTEP AGREEMENT with a cycle-accurate reference model. ``ScrubModel``
   below is written from the module contract -- the scrub.v header and
   docs/10 section 11.2 -- and reproduces the controller cycle for cycle:
   the five-state walk, the memory handshake, the writeback decision, the
   read-response watchdog, the window clamp and every fault counter. Every
   cycle driven through ``Harness.cycle`` compares all fourteen outputs
   against the model, so a divergence of one cycle on one bit fails the
   test that produced it. This is the docs/09 B.2 layer-1 refinement
   evidence for this block, in the same shape as
   ``hw/tb/test_lif_core_rtl.py`` for the LIF datapath.

   The model deliberately lives here rather than in ``sw/golden/``: it
   models a CONTROL path with no software-visible arithmetic and nothing
   in ``sw/`` consumes it. Promoting it to ``sw/golden/scrub.py`` with its
   own ``sw/tests`` suite is a reasonable later move; it is noted rather
   than done silently.

2. DIRECTED behaviour that random stimulus reaches slowly or not at all:
   a full clean sweep, a corrected word written back, an uncorrectable
   word NOT written back, a memory that never answers, an arbiter that
   never grants, a window shrunk under a walk in flight, counter
   saturation, FAULT_CLR coincident with a fault, the SAFE state reached
   by depositing each of the eleven illegal state encodings into the
   state register, and the ERR_CFG stickiness that keeps a parked
   scrubber visible to a host that clears its fault block.

The formal counterpart is ``formal/scrub.sby`` (property list in
``formal/scrub_props.v``). The two cover different ground: formal
quantifies over all stimulus, this file produces concrete traces --
including the SAFE-state trace, which no reset-rooted cover task can
produce because S_SAFE is unreachable from reset by design.

Fully port-driven apart from the deliberate state-register deposits in the
two encoding tests. Icarus-clean.
"""

import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

# State encoding, mirrored from hw/rtl/scrub.v. The five legal codewords
# are the even-parity words of a 4-bit vector, so every single-bit upset
# lands on an odd-parity word no legal transition can produce.
S_IDLE = 0b0000
S_READ = 0b0011
S_WAIT = 0b0101
S_WB = 0b0110
S_SAFE = 0b1001

LEGAL_ENCODINGS = (S_IDLE, S_READ, S_WAIT, S_WB, S_SAFE)
ILLEGAL_ENCODINGS = tuple(e for e in range(16) if e not in LEGAL_ENCODINGS)

SETTLE_NS = 1  # past the NBA update, house convention of test_aer_fifo.py

# Every output the model predicts. Named once, so a port added to the RTL
# without being added to the model shows up as a missing key rather than
# as a silently unchecked signal.
OUTPUTS = (
    "mem_req", "mem_we", "mem_addr", "ecc_take", "busy", "scrub_addr",
    "sweep_wrap", "cnt_sec", "cnt_ded", "ded_seen", "fault_addr",
    "err_to", "err_win", "err_cfg",
)

INPUTS = (
    "scrub_en", "scrub_step", "region_last", "fault_clr", "mem_gnt",
    "ecc_valid", "ecc_sec", "ecc_ded",
)


class ScrubModel:
    """Cycle-accurate reference model of the scrub controller.

    Re-derived from the contract rather than transliterated from the
    Verilog, which is what makes agreement between the two evidence
    instead of a tautology.

    Per cycle: read ``outputs(inp)`` (the combinational picture for this
    cycle), then call ``step(inp)`` to advance over the clock edge with
    the same inputs.
    """

    def __init__(self, aw, cnt_w, wd_w):
        self.aw = aw
        self.addr_mask = (1 << aw) - 1
        self.cnt_max = (1 << cnt_w) - 1
        self.wd_max = (1 << wd_w) - 1
        self.reset()

    def reset(self):
        """Asynchronous reset: the walk restarts at word 0, every counter
        and flag clears. Nothing else in the block has state."""
        self.state = S_IDLE
        self.addr = 0
        self.wd = 0
        self.step_pend = 0
        self.wrap = 0
        self.cnt_sec = 0
        self.cnt_ded = 0
        self.ded_seen = 0
        self.fault_addr = 0
        self.err_to = 0
        self.err_win = 0
        self.err_cfg = 0

    # -- combinational view -------------------------------------------
    def _win_ok(self, inp):
        return self.addr <= inp["region_last"]

    def _in_txn(self):
        return self.state in (S_READ, S_WAIT, S_WB)

    def events(self, inp):
        """The word-terminating events. All are gated on a legal working
        state, so a parked or corrupted controller produces none."""
        win = self._win_ok(inp)
        waiting = self.state == S_WAIT and win
        return {
            "win": self._in_txn() and not win,
            "to": waiting and not inp["ecc_valid"] and self.wd == self.wd_max,
            "sec": (waiting and inp["ecc_valid"]
                    and not inp["ecc_ded"] and inp["ecc_sec"]),
            "ded": waiting and inp["ecc_valid"] and inp["ecc_ded"],
            "ok": (waiting and inp["ecc_valid"]
                   and not inp["ecc_ded"] and not inp["ecc_sec"]),
        }

    def outputs(self, inp):
        return {
            "mem_req": int(self.state in (S_READ, S_WB) and self._win_ok(inp)),
            "mem_we": int(self.state == S_WB),
            "mem_addr": self.addr,
            "ecc_take": int(self.events(inp)["sec"]),
            "busy": int(self.state != S_IDLE),
            "scrub_addr": self.addr,
            "sweep_wrap": self.wrap,
            "cnt_sec": self.cnt_sec,
            "cnt_ded": self.cnt_ded,
            "ded_seen": self.ded_seen,
            "fault_addr": self.fault_addr,
            "err_to": self.err_to,
            "err_win": self.err_win,
            "err_cfg": self.err_cfg,
        }

    # -- sequential view ----------------------------------------------
    def step(self, inp):
        ev = self.events(inp)
        win = self._win_ok(inp)
        last = inp["region_last"]
        here = self.addr                     # the word being checked
        go = bool(inp["scrub_en"] or self.step_pend) and win
        start_word = self.state == S_IDLE and go
        fin_ok = (ev["to"] or ev["ded"] or ev["ok"]
                  or (self.state == S_WB and win and inp["mem_gnt"]))

        state, wd = self.state, self.wd
        if self.state == S_IDLE:
            wd = 0
            if go:
                state = S_READ
        elif self.state == S_READ:
            if not win:
                state = S_IDLE
            elif inp["mem_gnt"]:
                state, wd = S_WAIT, 0
        elif self.state == S_WAIT:
            if not win:
                state = S_IDLE
            elif inp["ecc_valid"]:
                state = (S_IDLE if (inp["ecc_ded"] or not inp["ecc_sec"])
                         else S_WB)
            elif self.wd == self.wd_max:
                state = S_IDLE
            else:
                wd = self.wd + 1
        elif self.state == S_WB:
            if (not win) or inp["mem_gnt"]:
                state = S_IDLE
        elif self.state == S_SAFE:
            state = S_SAFE
        else:
            # Illegal encoding: park and tell the host (docs/10 11.4).
            state = S_SAFE
            self.err_cfg = 1

        self.wrap = 0
        if fin_ok:
            self.wrap = int(here >= last)
            self.addr = 0 if here >= last else ((here + 1) & self.addr_mask)
        elif self.state == S_IDLE and not win:
            self.addr = 0

        if start_word:
            self.step_pend = int(inp["scrub_step"])
        elif inp["scrub_step"]:
            self.step_pend = 1

        # FAULT_CLR convention (house rule, hw/rtl/aer_fifo.v): a fault
        # coincident with the clear restarts the counter at 1 rather than
        # being swallowed by it.
        clr = bool(inp["fault_clr"])
        if clr:
            self.cnt_sec = 1 if ev["sec"] else 0
        elif ev["sec"] and self.cnt_sec != self.cnt_max:
            self.cnt_sec += 1
        if clr:
            self.cnt_ded = 1 if ev["ded"] else 0
        elif ev["ded"] and self.cnt_ded != self.cnt_max:
            self.cnt_ded += 1

        self.ded_seen = int(ev["ded"]) if clr else (self.ded_seen | int(ev["ded"]))
        if clr:
            self.fault_addr = here if ev["ded"] else 0
        elif ev["ded"]:
            self.fault_addr = here
        self.err_to = int(ev["to"]) if clr else (self.err_to | int(ev["to"]))
        self.err_win = int(ev["win"]) if clr else (self.err_win | int(ev["win"]))

        self.state, self.wd = state, wd


class Harness:
    """One cycle at a time, with every output compared against the model
    on every cycle.

    Inputs are NOT sticky: anything a cycle does not name is driven low
    for that cycle, except ``region_last``, which is a configuration
    register and holds its last value. A sticky ``scrub_step`` would
    silently re-arm the single-word request, which is exactly the kind of
    testbench artefact that hides a bug.
    """

    def __init__(self, dut):
        self.dut = dut
        self.aw = int(dut.AW.value)
        self.cnt_w = int(dut.CNT_W.value)
        self.wd_w = int(dut.WD_W.value)
        self.model = ScrubModel(self.aw, self.cnt_w, self.wd_w)
        self.region_last = (1 << self.aw) - 1
        self.inp = dict.fromkeys(INPUTS, 0)
        self.inp["region_last"] = self.region_last
        self.cycles = 0
        self.checks = 0

    def _apply(self, kw):
        inp = dict.fromkeys(INPUTS, 0)
        if "region_last" in kw:
            self.region_last = int(kw["region_last"])
        inp["region_last"] = self.region_last
        for key, value in kw.items():
            assert key in INPUTS, f"unknown input {key}"
            inp[key] = int(value)
        self.inp = inp
        for key in INPUTS:
            getattr(self.dut, key).value = inp[key]

    def sample(self):
        return {name: int(getattr(self.dut, name).value) for name in OUTPUTS}

    def compare(self, note=""):
        got = self.sample()
        want = self.model.outputs(self.inp)
        for name in OUTPUTS:
            assert got[name] == want[name], (
                f"cycle {self.cycles}{' (' + note + ')' if note else ''}: "
                f"{name} = {got[name]}, reference model says {want[name]}; "
                f"dut state=0b{int(self.dut.state.value):04b} "
                f"model state=0b{self.model.state:04b} inputs={self.inp}")
        self.checks += 1
        return got

    async def settle(self):
        await Timer(SETTLE_NS, unit="ns")

    async def cycle(self, note="", **kw):
        """Drive, settle, compare, take the edge, advance the model.
        Returns the outputs sampled for this cycle."""
        self._apply(kw)
        await self.settle()
        out = self.compare(note)
        await RisingEdge(self.dut.clk)
        self.model.step(self.inp)
        self.cycles += 1
        await self.settle()
        return out

    async def reset(self):
        self.dut.rst_n.value = 0
        self._apply({"region_last": self.region_last})
        for _ in range(3):
            await RisingEdge(self.dut.clk)
        await self.settle()
        self.model.reset()
        self.dut.rst_n.value = 1
        await RisingEdge(self.dut.clk)
        await self.settle()
        self.cycles = 0

    async def serve_word(self, sec=False, ded=False, gnt_delay=0,
                         resp_delay=0, scrub_en=1):
        """Run one whole word from S_IDLE with a memory model as the
        environment: it grants after ``gnt_delay`` refusals and answers
        ``resp_delay`` cycles after a granted read.

        The stimulus is decided from the state and address REGISTERS,
        which are stable before the inputs for the cycle are driven, so
        nothing here depends on a combinational output sampled with the
        previous cycle's inputs still applied.
        """
        last = self.region_last
        reads, writes, takes = [], [], 0
        gnt_left, resp_left = gnt_delay, resp_delay
        started = False
        budget = 6 * (gnt_delay + resp_delay + 4) + 16
        for _ in range(budget):
            state = int(self.dut.state.value)
            addr = int(self.dut.scrub_addr.value)
            if state != S_IDLE:
                started = True
            elif started:
                break
            gnt = 0
            if state in (S_READ, S_WB) and addr <= last:
                if gnt_left > 0:
                    gnt_left -= 1
                else:
                    gnt = 1
                    gnt_left = gnt_delay
            answer = 0
            if state == S_WAIT:
                if resp_left > 0:
                    resp_left -= 1
                else:
                    answer = 1
            out = await self.cycle(
                scrub_en=scrub_en, mem_gnt=gnt, ecc_valid=answer,
                ecc_sec=int(bool(answer) and sec),
                ecc_ded=int(bool(answer) and ded))
            takes += out["ecc_take"]
            if out["mem_req"] and gnt:
                (writes if out["mem_we"] else reads).append(out["mem_addr"])
        else:
            raise AssertionError("serve_word never returned to S_IDLE")
        return {"reads": reads, "writes": writes, "takes": takes}


async def setup(dut, region_last=None):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    h = Harness(dut)
    if region_last is not None:
        h.region_last = region_last
    await h.reset()
    return h


@cocotb.test()
async def test_reset_state(dut):
    """Reset parks the walk at word 0 with every counter and flag clear,
    no request on the memory port, BUSY low."""
    h = await setup(dut)
    assert int(dut.state.value) == S_IDLE
    for name, value in h.sample().items():
        assert value == 0, f"{name} is {value} after reset, expected 0"
    for _ in range(3):
        await h.cycle()


@cocotb.test()
async def test_clean_sweep_visits_every_word_once(dut):
    """A full sweep of a clean window: every word in [0, region_last] is
    read exactly once, in ascending order, no word is skipped or visited
    twice, no word is written, and the wrap pulse arrives exactly at the
    end of the window.

    A skipped word is the silent failure this block exists to prevent --
    upsets accumulate there until the pair is uncorrectable -- so the
    coverage of the walk is measured directly, not inferred."""
    last = min((1 << int(dut.AW.value)) - 1, 7)
    h = await setup(dut, region_last=last)

    reads, writes, wraps = [], 0, 0
    for _ in range(12 * (last + 1) + 24):
        state = int(dut.state.value)
        out = await h.cycle(scrub_en=1, mem_gnt=1,
                            ecc_valid=int(state == S_WAIT))
        if out["mem_req"]:
            if out["mem_we"]:
                writes += 1
            else:
                reads.append(out["mem_addr"])
        wraps += int(dut.sweep_wrap.value)
        if wraps == 2:
            break

    assert writes == 0, "a clean sweep must never write"
    expected = list(range(last + 1)) * 2
    assert reads[:len(expected)] == expected, (
        f"walk visited {reads[:len(expected)]}, expected {expected}")
    assert int(dut.cnt_sec.value) == 0
    assert int(dut.cnt_ded.value) == 0
    assert int(dut.ded_seen.value) == 0


@cocotb.test()
async def test_corrected_word_is_written_back(dut):
    """A single-bit error is corrected and rewritten in place at the same
    address, CNT_SEC counts it, and ecc_take fires exactly once so the
    external ECC path captures the corrected word exactly once."""
    h = await setup(dut, region_last=3)
    word = await h.serve_word(sec=True)

    assert len(word["reads"]) == 1, f"one read expected, got {word['reads']}"
    assert len(word["writes"]) == 1, "a corrected word must be rewritten once"
    assert word["writes"][0] == word["reads"][0], (
        f"writeback address {word['writes'][0]} != "
        f"read address {word['reads'][0]}")
    assert word["takes"] == 1, "exactly one capture per repaired word"
    assert int(dut.cnt_sec.value) == 1
    assert int(dut.cnt_ded.value) == 0
    assert int(dut.ded_seen.value) == 0
    assert int(dut.scrub_addr.value) == 1, "the walk moves on after a repair"


@cocotb.test()
async def test_uncorrectable_word_is_never_written_back(dut):
    """A double-bit detection is counted, latched in FAULT_ADDR and
    DED_SEEN, and the word is NOT rewritten.

    Rewriting it would store the decoder's output for an uncorrectable
    word, which is not the stored word: a detected error would become a
    silent, permanent one. That is the worst outcome available to this
    block, so it gets a directed test as well as SC4 in
    formal/scrub_props.v."""
    h = await setup(dut, region_last=3)
    await h.serve_word()                       # word 0 clean
    word = await h.serve_word(ded=True)        # word 1 uncorrectable

    assert word["writes"] == [], \
        "an uncorrectable word must never be rewritten"
    assert word["takes"] == 0, "and must never be captured"
    assert int(dut.cnt_ded.value) == 1
    assert int(dut.ded_seen.value) == 1
    assert int(dut.fault_addr.value) == 1, \
        "FAULT_ADDR must hold the index of the failing word"
    assert int(dut.cnt_sec.value) == 0
    assert int(dut.err_cfg.value) == 0, "a data fault is not a control fault"
    assert int(dut.scrub_addr.value) == 2, \
        "fail-operational: the walk carries on (docs/10 section 11.2)"


@cocotb.test()
async def test_read_response_timeout_abandons_the_word(dut):
    """A memory that never answers costs one abandoned word and an err_to
    flag, not a parked scrubber. S_WAIT is left after exactly 2**WD_W
    cycles with no assumption about the memory at all -- the
    unconditional half of the deadlock-freedom obligation (SC17)."""
    wd_w = int(dut.WD_W.value)
    h = await setup(dut, region_last=3)

    await h.cycle(scrub_en=1)                 # IDLE -> READ
    await h.cycle(scrub_en=1, mem_gnt=1)      # READ -> WAIT
    assert int(dut.state.value) == S_WAIT
    waited = 0
    while int(dut.state.value) == S_WAIT:
        await h.cycle(scrub_en=0)             # the memory never answers
        waited += 1
        assert waited <= (1 << wd_w) + 1, "S_WAIT is not bounded"
    assert waited == (1 << wd_w), (
        f"left S_WAIT after {waited} cycles, expected {1 << wd_w}")
    assert int(dut.err_to.value) == 1, "the timeout must be observable"
    assert int(dut.scrub_addr.value) == 1, "the walk must move on"
    assert int(dut.cnt_sec.value) == 0 and int(dut.cnt_ded.value) == 0


@cocotb.test()
async def test_starved_by_the_arbiter_holds_a_stable_request(dut):
    """The scrubber is background traffic: an arbiter that never grants
    starves it by design, and it must wait without mutating or
    withdrawing its request, then proceed the moment the grant arrives.
    Starvation is not deadlock and the block must not confuse them."""
    h = await setup(dut, region_last=3)
    await h.cycle(scrub_en=1)                 # IDLE -> READ
    for _ in range(20):
        out = await h.cycle(scrub_en=1, mem_gnt=0)
        assert out["mem_req"] == 1, "the request must be held"
        assert out["mem_we"] == 0
        assert out["mem_addr"] == 0, "and must not mutate under refusal"
        assert int(dut.state.value) == S_READ
    out = await h.cycle(scrub_en=1, mem_gnt=1)
    assert int(dut.state.value) == S_WAIT
    assert int(dut.mem_req.value) == 0, \
        "a granted request must be withdrawn, or an arbiter that grants " \
        "on consecutive cycles executes it twice"


@cocotb.test()
async def test_single_step_runs_exactly_one_word(dut):
    """scrub_step (the pilot's SCRUB_STB pin after its edge detector) runs
    exactly one word with the background walk disabled, and does not turn
    into a sweep."""
    h = await setup(dut, region_last=3)
    await h.cycle(scrub_step=1)               # latch the single-word request
    assert int(dut.state.value) == S_IDLE, "the strobe is latched, not acted on"
    await h.cycle()                           # IDLE -> READ on the latched pend
    assert int(dut.state.value) == S_READ, "the strobe must start one word"
    await h.cycle(mem_gnt=1)                  # READ -> WAIT
    await h.cycle(ecc_valid=1)                # clean -> IDLE
    assert int(dut.state.value) == S_IDLE
    assert int(dut.scrub_addr.value) == 1
    for _ in range(8):
        await h.cycle()
        assert int(dut.state.value) == S_IDLE, \
            "one strobe must run one word, not a sweep"


@cocotb.test()
async def test_strobe_coincident_with_a_word_start_is_not_lost(dut):
    """A strobe that lands on the cycle a word starts is retained, not
    swallowed -- the FAULT_CLR-style convention of hw/rtl/aer_fifo.v
    applied to the single-word request."""
    h = await setup(dut, region_last=3)
    await h.cycle(scrub_step=1)               # arm word 1
    await h.cycle(scrub_step=1)               # word starts AND re-arms
    assert int(dut.state.value) == S_READ
    await h.cycle(mem_gnt=1)
    await h.cycle(ecc_valid=1)                # word 0 retires
    assert int(dut.state.value) == S_IDLE
    await h.cycle()
    assert int(dut.state.value) == S_READ, \
        "the coincident strobe must still be pending"
    assert int(dut.scrub_addr.value) == 1


@cocotb.test()
async def test_window_shrink_under_a_walk_never_leaves_the_window(dut):
    """A host that shrinks region_last while a word is in flight gets the
    request withdrawn, err_win latched and the walk clamped back to 0 --
    and never, at any cycle, a request outside the configured window.

    This is the memory-isolation property of the block: SC1/SC2 prove it
    for all stimulus, this is the concrete trace."""
    aw = int(dut.AW.value)
    assert aw >= 2, "this suite is elaborated with at least a four-word window"
    wide = min((1 << aw) - 1, 7)
    h = await setup(dut, region_last=wide)

    while int(dut.scrub_addr.value) != 3:
        state = int(dut.state.value)
        out = await h.cycle(scrub_en=1, mem_gnt=1,
                            ecc_valid=int(state == S_WAIT))
        assert not (out["mem_req"] and out["mem_addr"] > wide)
    await h.cycle(scrub_en=1)                 # IDLE -> READ at word 3
    assert int(dut.state.value) == S_READ

    outside = 0
    for _ in range(6):
        out = await h.cycle(scrub_en=1, region_last=0)  # window is word 0 only
        outside += int(out["mem_req"] and out["mem_addr"] > 0)
    assert outside == 0, "the port must never address outside the window"
    assert int(dut.err_win.value) == 1, "the abandoned word must be visible"
    assert int(dut.scrub_addr.value) == 0, "the walk must clamp back inside"
    assert int(dut.err_cfg.value) == 0, "a configuration change is not an upset"


@cocotb.test()
async def test_counter_saturation_and_fault_clr(dut):
    """The fault counters saturate instead of wrapping -- a wrapped fault
    counter reads back as 'no errors', the worst lie a fault counter can
    tell -- and a FAULT_CLR coincident with a fault restarts the counter
    at 1 instead of swallowing the event."""
    cnt_max = (1 << int(dut.CNT_W.value)) - 1
    h = await setup(dut, region_last=3)

    if cnt_max <= 31:
        for _ in range(cnt_max + 3):
            await h.serve_word(sec=True)
        assert int(dut.cnt_sec.value) == cnt_max, "CNT_SEC must saturate"
    else:
        # A 16-bit counter is not saturated in simulation time; the
        # saturation clause is exhaustive in formal (SC19) and checked
        # here at the narrow elaborations.
        for _ in range(3):
            await h.serve_word(sec=True)
        assert int(dut.cnt_sec.value) == 3

    await h.cycle(fault_clr=1)
    assert int(dut.cnt_sec.value) == 0, "FAULT_CLR must clear CNT_SEC"

    # A fault coincident with the clear survives it.
    await h.cycle(scrub_en=1)                 # IDLE -> READ
    await h.cycle(scrub_en=1, mem_gnt=1)      # READ -> WAIT
    await h.cycle(scrub_en=1, ecc_valid=1, ecc_ded=1, fault_clr=1)
    assert int(dut.cnt_ded.value) == 1, \
        "a fault coincident with FAULT_CLR must restart the counter at 1"
    assert int(dut.ded_seen.value) == 1


@cocotb.test()
async def test_safe_state_on_corrupted_fsm_encoding(dut):
    """(docs/10 section 11.4) Every illegal state encoding parks the
    controller in S_SAFE on the next edge with ERR_CFG latched, and the
    parked controller drives NOTHING: no memory request, no capture, no
    counter movement, a frozen address. Only reset leaves it.

    The eleven illegal codewords are deposited directly into the state
    register, because the upset the encoding exists for cannot be produced
    from the ports. The reference model takes the same deposit, so the
    lockstep comparison covers the recovery path too.
    formal/scrub_props.v SC13/SC14/SC15 prove the same behaviour over an
    arbitrary starting encoding (task bmc_any); this is the concrete
    trace, which no reset-rooted cover task can produce."""
    h = await setup(dut, region_last=3)

    for enc in ILLEGAL_ENCODINGS:
        await h.reset()
        assert int(dut.err_cfg.value) == 0, "reset must clear ERR_CFG"
        addr_before = int(dut.scrub_addr.value)

        dut.state.value = enc                 # the injected upset
        h.model.state = enc                   # ... and the same in the model
        await h.settle()
        assert int(dut.state.value) == enc, "state deposit did not take"

        out = await h.cycle(scrub_en=1, note=f"enc 0b{enc:04b}")
        assert out["mem_req"] == 0, \
            "an illegal encoding must not drive the memory port even once"
        assert int(dut.state.value) == S_SAFE, (
            f"encoding 0b{enc:04b} recovered to "
            f"0b{int(dut.state.value):04b}, expected S_SAFE 0b1001")
        assert int(dut.err_cfg.value) == 1, "S_SAFE must latch ERR_CFG"
        assert int(dut.busy.value) == 1, "a parked controller is not idle"

        for _ in range(8):
            out = await h.cycle(scrub_en=1, mem_gnt=1, ecc_valid=1,
                                ecc_sec=1, note=f"parked 0b{enc:04b}")
            assert int(dut.state.value) == S_SAFE, "S_SAFE must be terminal"
            assert out["mem_req"] == 0, \
                "a corrupted scrubber must not drive the memory port"
            assert out["ecc_take"] == 0
            assert out["err_cfg"] == 1
            assert out["scrub_addr"] == addr_before, "S_SAFE freezes the walk"
            assert out["cnt_sec"] == 0

        await h.reset()                       # reset is the only way out
        assert int(dut.state.value) == S_IDLE
        assert int(dut.err_cfg.value) == 0


@cocotb.test()
async def test_legal_encodings_are_not_disturbed(dut):
    """The negative control for the test above: depositing each LEGAL
    codeword does not trip the fault path. Without it, a design that
    parked on every encoding would pass the SAFE test."""
    h = await setup(dut, region_last=3)
    for enc in (S_IDLE, S_READ, S_WAIT, S_WB):
        await h.reset()
        dut.state.value = enc
        h.model.state = enc
        await h.settle()
        await h.cycle(scrub_en=1, note=f"legal 0b{enc:04b}")
        assert int(dut.err_cfg.value) == 0, (
            f"legal encoding 0b{enc:04b} must not latch ERR_CFG")
        assert int(dut.state.value) != S_SAFE, (
            f"legal encoding 0b{enc:04b} must not park the controller")


@cocotb.test()
async def test_fault_clr_cannot_clear_err_cfg_while_parked(dut):
    """FAULT_CLR clears every fault record this block keeps except one.

    ERR_CFG is the only software-visible indication that an upset has
    parked the controller in S_SAFE. BUSY is high there, but BUSY is
    also high during every ordinary word, so it does not distinguish a
    parked scrubber from a working one; the address is frozen, but a
    frozen address is what a starved scrubber shows too; and the
    counters and the other stickies read exactly as they did before the
    upset, because a parked controller produces no events. ERR_CFG is
    the whole signal.

    So it must survive the host acknowledging the faults it can act on.
    If FAULT_CLR cleared ERR_CFG, a host that clears its fault block on
    a schedule -- which is the documented way to use FAULT_CLR -- would
    read the block back clean with the scrubber permanently dead behind
    it, and the weight image would silently stop being scrubbed.
    hw/rtl/scrub.v gives err_cfg_r no fault_clr clause at all: reset is
    the only way out of it, which is also the only way out of S_SAFE,
    and the two therefore cannot disagree. This test is what says so.

    Every other record is primed first, and the discriminating check is
    that the same FAULT_CLR cycle clears all six of them. Without the
    priming a FAULT_CLR that did nothing whatsoever would pass.
    """
    aw = int(dut.AW.value)
    assert aw >= 2, "this suite is elaborated with at least a four-word window"
    h = await setup(dut, region_last=3)

    # -- prime every record FAULT_CLR is supposed to clear --------------
    await h.serve_word(sec=True)              # word 0: CNT_SEC
    await h.serve_word(ded=True)              # word 1: CNT_DED, DED_SEEN,
    assert int(dut.fault_addr.value) == 1     #         FAULT_ADDR

    await h.cycle(scrub_en=1)                 # word 2: IDLE -> READ
    await h.cycle(scrub_en=1, mem_gnt=1)      #         READ -> WAIT
    while int(dut.state.value) == S_WAIT:     #  the memory never answers
        await h.cycle(scrub_en=0)
    assert int(dut.err_to.value) == 1, "ERR_TO priming did not take"

    await h.cycle(scrub_en=1)                 # word 3: IDLE -> READ
    assert int(dut.state.value) == S_READ
    await h.cycle(scrub_en=1, region_last=0)  # the window shrinks under it
    assert int(dut.err_win.value) == 1, "ERR_WIN priming did not take"
    await h.cycle(region_last=3)              # and is restored

    primed = h.sample()
    for name in ("cnt_sec", "cnt_ded", "ded_seen", "fault_addr",
                 "err_to", "err_win"):
        assert primed[name] != 0, \
            f"{name} is 0 before the clear: this test would pass on a " \
            f"FAULT_CLR that does nothing at all"
    assert primed["err_cfg"] == 0, "no control fault has happened yet"

    # -- the upset: park the controller in S_SAFE -----------------------
    # 0b0001 is one bit away from S_IDLE and, like every odd-parity word,
    # is an encoding no legal transition can produce.
    dut.state.value = 0b0001
    h.model.state = 0b0001
    await h.settle()
    await h.cycle(scrub_en=1)
    assert int(dut.state.value) == S_SAFE, "the deposit must park the block"
    assert int(dut.err_cfg.value) == 1, "S_SAFE must latch ERR_CFG"
    addr_parked = int(dut.scrub_addr.value)

    # -- the host acknowledges its faults -------------------------------
    await h.cycle(scrub_en=1, fault_clr=1)
    cleared = h.sample()
    for name in ("cnt_sec", "cnt_ded", "ded_seen", "fault_addr",
                 "err_to", "err_win"):
        assert cleared[name] == 0, \
            f"FAULT_CLR must clear {name}, which still reads {cleared[name]}"
    assert cleared["err_cfg"] == 1, \
        "FAULT_CLR must NOT clear ERR_CFG: it is the only indication a " \
        "host has that an upset parked the scrubber, and a host that " \
        "could acknowledge it away would run with a dead scrubber and a " \
        "clean-looking fault block"
    assert int(dut.state.value) == S_SAFE, \
        "and FAULT_CLR must not un-park the controller either"

    # It does not decay under repetition, and the parked block still
    # drives nothing while the clears arrive.
    for _ in range(8):
        out = await h.cycle(scrub_en=1, fault_clr=1, mem_gnt=1,
                            ecc_valid=1, ecc_sec=1)
        assert out["err_cfg"] == 1, "ERR_CFG must hold through every clear"
        assert out["mem_req"] == 0, "a parked scrubber drives no request"
        assert out["ecc_take"] == 0
        assert out["busy"] == 1
        assert out["scrub_addr"] == addr_parked, "S_SAFE freezes the walk"
        assert int(dut.state.value) == S_SAFE

    # Reset is the only way out, of S_SAFE and of ERR_CFG alike.
    await h.reset()
    assert int(dut.state.value) == S_IDLE
    assert int(dut.err_cfg.value) == 0


@cocotb.test()
async def test_random_lockstep(dut):
    """Constrained-random stimulus in lockstep with the reference model: a
    hostile arbiter, a memory that answers late or not at all, a host that
    moves the window and clears the counters mid-walk, and resets dropped
    into the middle of it. Every output is compared on every cycle."""
    seed = int(os.environ.get("SCRUB_SEED", "20260825"))
    rng = random.Random(seed)
    top = (1 << int(dut.AW.value)) - 1
    h = await setup(dut)

    n = 4000
    for _ in range(n):
        if rng.random() < 0.01:
            await h.reset()
            continue
        await h.cycle(
            scrub_en=int(rng.random() < 0.8),
            scrub_step=int(rng.random() < 0.05),
            region_last=rng.choice([0, 1, top, rng.randint(0, top)]),
            fault_clr=int(rng.random() < 0.02),
            mem_gnt=int(rng.random() < 0.6),
            ecc_valid=int(rng.random() < 0.5),
            ecc_sec=int(rng.random() < 0.3),
            ecc_ded=int(rng.random() < 0.15),
        )
    assert h.checks > n // 2, "the lockstep comparison did not run"
    dut._log.info("lockstep: %d full-output comparisons over %d driven "
                  "cycles, seed %d", h.checks, n, seed)
