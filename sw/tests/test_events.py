"""Event ordering and determinism tests (E8, docs/10 section 4.3)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from golden import LIFConfig, LIFCore


def test_e8_spikes_ascending_within_one_event():
    # (E8 rule 2) one event making several neurons cross emits their ids
    # in ascending scan order.
    core = LIFCore(4, 1, [[7, 7, 7, 7]], LIFConfig(thresh=7))
    assert core.synaptic_event(0) == [0, 1, 2, 3]


def test_e8_event_order_outranks_neuron_id_order():
    # (E8 rule 3) if event k spikes neuron 2 and event k+1 spikes neuron 0,
    # the output stream is [2, 0]: arrival order wins across events.
    weights = [
        [0, 0, 7, 0],  # axon 0 targets neuron 2
        [7, 0, 0, 0],  # axon 1 targets neuron 0
    ]
    core = LIFCore(4, 2, weights, LIFConfig(thresh=7))
    out = []
    for axon in (0, 1):
        out.extend(core.synaptic_event(axon))
    assert out == [2, 0]


def test_e8_fifo_order_changes_the_result():
    # (E8 rule 1) events are consumed strictly in FIFO order; interleaving
    # an inhibitory event changes whether the threshold is reached, so the
    # streams below must differ exactly as hand-computed.
    # axon 0: c = +48 (w=6, S_SYN=3); axon 1: c = -64 (w=-8, S_SYN=3).
    weights = [[6], [-8]]
    cfg = dict(thresh=90, syn_shift=3, leak_en=False)

    core = LIFCore(1, 2, weights, LIFConfig(**cfg))
    per_event = [core.synaptic_event(a) for a in (0, 0)]
    assert per_event == [[], [0]]  # 48, 96 >= 90 -> spike on event 2

    core = LIFCore(1, 2, weights, LIFConfig(**cfg))
    per_event = [core.synaptic_event(a) for a in (0, 1, 0)]
    assert per_event == [[], [], []]  # 48, -16, 32: no spike
    assert core.v == [32]


def test_e8_identical_streams_bit_identical_results():
    # (E8) the core is a deterministic function of (state, config,
    # weights, stream): two fresh cores fed the same stream agree on both
    # the output stream and the final state.
    weights = [[3, -7, 5], [-2, 6, 1], [7, 0, -8]]
    frames = [[0, 1, 2, 0], [2, 2], [], [1, 0, 1]]

    def run():
        core = LIFCore(3, 3, weights,
                       LIFConfig(thresh=20, syn_shift=2, leak_shift=1,
                                 refr_period=1))
        out = core.run_frames(frames)
        return out, core.v, core.r

    assert run() == run()


def test_e8_replay_after_state_clr_is_identical():
    # (E8) STATE_CLR returns the core to the defined initial state; a
    # replay of the same stream reproduces the same output bit-for-bit.
    weights = [[7, -4], [-3, 6]]
    frames = [[0, 1], [1], [0, 0, 1]]
    core = LIFCore(2, 2, weights,
                   LIFConfig(thresh=15, syn_shift=1, leak_shift=2))
    first = core.run_frames(frames)
    core.reset_state()
    second = core.run_frames(frames)
    assert first == second


def test_e8_duplicate_events_are_distinct_events():
    # (E8) two events with the same axon id in one timestep are two
    # separate updates, not a merged one.
    core = LIFCore(1, 1, [[5]], LIFConfig(thresh=10, leak_en=False))
    per_event = [core.synaptic_event(0), core.synaptic_event(0)]
    assert per_event == [[], [0]]  # 5, then 10 >= 10


def test_e8_tick_emits_nothing_and_orders_between_frames():
    # (E8 rule 4) the per-timestep driver runs events then one TICK; the
    # TICK contributes no spikes and its leak is visible to the next frame.
    core = LIFCore(1, 1, [[7]], LIFConfig(thresh=100, leak_shift=0))
    out = core.run_frames([[0], [0]])
    assert out == [[], []]
    # S_LEAK = 0 clears V at each frame boundary: frame 2 restarts from 0.
    assert core.v == [0]
