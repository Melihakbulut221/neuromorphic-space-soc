"""Multi-pass execution tests (E9, docs/10 section 9).

The equivalence obligation: running a layer as several output-neuron
tile passes with the event stream replayed, then merging per-event in
tile order, is bit-identical to a single hypothetical core wide enough
for the whole layer. The single-pass reference below is driven directly
through LIFCore (an independent code path from the runner's merge).
"""

import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from golden import LayerSpec, LIFConfig, LIFCore, NetworkRunner


def random_layer(rng, n_axons, n_neurons, **cfg_kwargs):
    weights = [[rng.randrange(-8, 8) for _ in range(n_neurons)]
               for _ in range(n_axons)]
    return LayerSpec(weights, LIFConfig(**cfg_kwargs))


def random_frames(rng, n_timesteps, n_axons, max_events):
    return [[rng.randrange(n_axons) for _ in range(rng.randrange(max_events))]
            for _ in range(n_timesteps)]


def test_e9_tiled_equals_single_wide_core():
    # (E9) 40-neuron layer on an 8-neuron core (5 passes) versus one
    # 40-neuron core: identical per-timestep spike streams.
    rng = random.Random(7)
    layer = random_layer(rng, 32, 40, thresh=60, syn_shift=3,
                         leak_shift=2, refr_period=1)
    frames = random_frames(rng, 12, 32, 12)

    wide = LIFCore(40, 32, layer.weights, layer.config)
    reference = wide.run_frames(frames)

    runner = NetworkRunner([layer], core_neurons=8, core_axons=32)
    assert runner.layer_passes(layer) == 5
    assert runner.run(frames) == reference


def test_e9_uneven_tiling_equals_single_wide_core():
    # (E9) tile sizes that do not divide the layer (24 = 7+7+7+3).
    rng = random.Random(11)
    layer = random_layer(rng, 16, 24, thresh=40, syn_shift=2, leak_shift=1)
    frames = random_frames(rng, 10, 16, 10)

    reference = LIFCore(24, 16, layer.weights, layer.config).run_frames(frames)
    runner = NetworkRunner([layer], core_neurons=7, core_axons=16)
    assert runner.layer_passes(layer) == 4
    assert runner.run(frames) == reference


def test_e9_tiling_is_partition_invariant():
    # (E9) any tile width gives the same canonical stream: the per-neuron
    # trajectories are independent, only the merge differs.
    rng = random.Random(23)
    layer = random_layer(rng, 20, 30, thresh=50, syn_shift=3, leak_shift=2)
    frames = random_frames(rng, 8, 20, 8)
    outputs = [
        NetworkRunner([layer], core_neurons=w, core_axons=20).run(frames)
        for w in (1, 4, 13, 30, 512)
    ]
    assert all(out == outputs[0] for out in outputs)


def test_e9_multilayer_runner_equals_manual_core_chain():
    # (E9)/layer-serial: a 3-layer network through the runner equals
    # manually chaining one core per layer with big-enough cores.
    rng = random.Random(42)
    layers = [
        random_layer(rng, 16, 24, thresh=30, syn_shift=2, leak_shift=1),
        random_layer(rng, 24, 12, thresh=25, syn_shift=2, leak_shift=1),
        random_layer(rng, 12, 4, thresh=20, syn_shift=2, leak_shift=1),
    ]
    frames = random_frames(rng, 15, 16, 10)

    manual = frames
    for layer in layers:
        core = LIFCore(layer.n_neurons, layer.n_axons, layer.weights,
                       layer.config)
        manual = core.run_frames(manual)

    # Big core: one pass per layer.
    runner = NetworkRunner(layers, core_neurons=512, core_axons=512)
    assert runner.total_passes == 3
    assert runner.run(frames) == manual

    # Small core: tiling on top of layer-serial, same stream.
    tiled = NetworkRunner(layers, core_neurons=5, core_axons=512)
    assert tiled.total_passes == 5 + 3 + 1
    assert tiled.run(frames) == manual


def test_e9_pass_counting():
    layer = random_layer(random.Random(0), 8, 40, thresh=10)
    runner = NetworkRunner([layer], core_neurons=16, core_axons=8)
    assert runner.layer_passes(layer) == 3
    assert runner.total_passes == 3


def test_e9_layer_wider_than_event_id_space_rejected():
    # (E9) bound, spec section 9 limitation: emitted ids TILE_OFF + j must
    # fit the frozen 10-bit event-word ID field, so a 1025-wide layer —
    # whose last tile would need base + width = 1025 > 1024 — must be
    # refused at construction, not silently mis-executed.
    layer = LayerSpec([[0] * 1025 for _ in range(4)], LIFConfig(thresh=10))
    with pytest.raises(ValueError):
        NetworkRunner([layer], core_neurons=512, core_axons=4)


def test_e9_layer_width_exactly_1024_accepted():
    # (E9) boundary: 1024 = 2^10 neurons exactly fill the ID space
    # (ids 0..1023) and must be accepted and runnable; the last tile is
    # base 512 + width 512 = 1024, and the maximum emitted id is 1023.
    layer = LayerSpec([[7] * 1024, [0] * 1024],
                      LIFConfig(thresh=5, leak_en=False))
    runner = NetworkRunner([layer], core_neurons=512, core_axons=2)
    assert runner.layer_passes(layer) == 2
    assert runner.run([[0]]) == [list(range(1024))]


def test_axon_dimension_split_rejected():
    # spec section 9 limitation: fan-in > core_axons is not splittable in
    # v0.1 and must be refused, not silently mis-executed.
    layer = random_layer(random.Random(1), 32, 8, thresh=10)
    with pytest.raises(ValueError):
        NetworkRunner([layer], core_neurons=512, core_axons=16)


def test_layer_fanin_fanout_mismatch_rejected():
    rng = random.Random(2)
    l1 = random_layer(rng, 8, 10, thresh=10)
    l2 = random_layer(rng, 12, 4, thresh=10)  # expects 12, gets 10
    with pytest.raises(ValueError):
        NetworkRunner([l1, l2])
