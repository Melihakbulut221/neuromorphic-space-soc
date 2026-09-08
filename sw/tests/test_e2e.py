# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""End-to-end functional test: a 3-layer toy SNN classifying two
synthetic rate-coded patterns well above chance (docs/10 section 13).

Pattern A drives the even input axons, pattern B the odd ones, with
noise. Layer 1 holds hand-designed even/odd feature detectors, layers 2
and 3 aggregate them into two output neurons; the decision is the spike
count argmax. Everything is integer: stimulus generation uses only
randrange on a seeded generator.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from golden import LayerSpec, LIFConfig, NetworkRunner, spike_counts

N_IN = 16
T_STEPS = 12
N_TRIALS_PER_CLASS = 20


def build_network():
    # Layer 1: 16 -> 8. Neurons 0..3 detect even axons, 4..7 odd axons.
    w1 = []
    for axon in range(N_IN):
        even = axon % 2 == 0
        row = [(4 if even else -4)] * 4 + [(-4 if even else 4)] * 4
        w1.append(row)
    l1 = LayerSpec(w1, LIFConfig(thresh=96, syn_shift=2, leak_shift=1))

    # Layer 2: 8 -> 6. Neurons 0..2 aggregate the even group, 3..5 odd.
    w2 = []
    for axon in range(8):
        even_group = axon < 4
        row = [(6 if even_group else -6)] * 3 + [(-6 if even_group else 6)] * 3
        w2.append(row)
    l2 = LayerSpec(w2, LIFConfig(thresh=64, syn_shift=2, leak_shift=1))

    # Layer 3: 6 -> 2. Output 0 = class A (even), output 1 = class B (odd).
    w3 = []
    for axon in range(6):
        a_group = axon < 3
        row = [7 if a_group else -7, -7 if a_group else 7]
        w3.append(row)
    l3 = LayerSpec(w3, LIFConfig(thresh=48, syn_shift=2, leak_shift=1))

    return [l1, l2, l3]


def make_trial(rng, cls):
    """Rate-coded frames: active axons fire with p=3/4, inactive with
    p=1/4 (integer randrange only). Class 0 activates even axons."""
    frames = []
    for _ in range(T_STEPS):
        timestep = []
        for axon in range(N_IN):
            active = (axon % 2) == cls  # class 0: even axons, class 1: odd
            gate = 3 if active else 1
            if rng.randrange(4) < gate:
                timestep.append(axon)
        frames.append(timestep)
    return frames


def classify(runner, frames):
    counts = spike_counts(runner.run(frames), 2)
    if counts[0] == counts[1]:
        return None  # tie counts as a miss
    return 0 if counts[0] > counts[1] else 1


def run_trials(runner):
    correct = 0
    total = 0
    for cls in (0, 1):
        for i in range(N_TRIALS_PER_CLASS):
            rng = random.Random(1000 + 100 * cls + i)
            frames = make_trial(rng, cls)
            if classify(runner, frames) == cls:
                correct += 1
            total += 1
    return correct, total


def test_e2e_two_pattern_classification_above_chance():
    runner = NetworkRunner(build_network(), core_neurons=512, core_axons=512)
    correct, total = run_trials(runner)
    assert total == 2 * N_TRIALS_PER_CLASS
    # Chance is 50 percent; require a solid margin over it.
    assert correct >= int(0.8 * total), f"only {correct}/{total} correct"


def test_e2e_result_identical_under_forced_multipass():
    # The same network executed on a 4-neuron core (tiling every layer)
    # must classify identically trial by trial (E9 at network level).
    big = NetworkRunner(build_network(), core_neurons=512, core_axons=512)
    small = NetworkRunner(build_network(), core_neurons=4, core_axons=16)
    assert small.total_passes == 2 + 2 + 1
    for cls in (0, 1):
        for i in range(5):
            rng = random.Random(1000 + 100 * cls + i)
            frames = make_trial(rng, cls)
            assert big.run(frames) == small.run(frames)


def test_e2e_deterministic_across_runs():
    runner = NetworkRunner(build_network())
    first = run_trials(runner)
    second = run_trials(runner)
    assert first == second
