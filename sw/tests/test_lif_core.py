# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Tests for the bit-exact LIF core golden model (lif_core.py).

Each test_e<n>_* function exercises the correspondingly numbered equation
of docs/10-npu-mvp-spec.md section 4 / 11.2; the traceability meta-test
enforces the mapping.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from golden import (
    LIFConfig,
    LIFCore,
    leak_value,
    sat16,
    V_MAX,
    V_MIN,
    WEIGHTS_PER_WORD,
)


def single(w, thresh=100, **cfg_kwargs):
    """1-axon, 1-neuron core with weight w."""
    return LIFCore(1, 1, [[w]], LIFConfig(thresh=thresh, **cfg_kwargs))


# -- E1: 4-bit signed weight decode and range --------------------------------

def test_e1_weight_range_accepted_at_extremes():
    # (E1) w in [-8, +7]; both rails are legal codes.
    core = LIFCore(2, 1, [[-8, 7]], LIFConfig(thresh=1000))
    assert core.synaptic_event(0) == []
    assert core.v == [-8, 7]


def test_e1_weight_out_of_range_rejected():
    # (E1) codes outside the 4-bit signed range are construction errors.
    with pytest.raises(ValueError):
        LIFCore(1, 1, [[8]], LIFConfig(thresh=100))
    with pytest.raises(ValueError):
        LIFCore(1, 1, [[-9]], LIFConfig(thresh=100))


def test_e1_negative_weight_inhibits():
    # (E1) signed decode: a negative weight drives V downward.
    core = single(-8, thresh=100)
    core.synaptic_event(0)
    core.synaptic_event(0)
    assert core.v == [-16]


def test_e1_float_weights_rejected():
    # Golden-path discipline: no floating point anywhere in the core.
    with pytest.raises(TypeError):
        LIFCore(1, 1, [[1.0]], LIFConfig(thresh=100))


# -- E2: synaptic contribution shift -----------------------------------------

def test_e2_contribution_shift_hand_computed():
    # (E2) c = w * 2**S_SYN: w=7, S_SYN=3 -> c=56, two events -> V=112.
    core = single(7, thresh=32767, syn_shift=3)
    core.synaptic_event(0)
    assert core.v == [56]
    core.synaptic_event(0)
    assert core.v == [112]


def test_e2_contribution_extremes():
    # (E2) c in [-1024, +896] at S_SYN=7.
    core = LIFCore(1, 2, [[-8], [7]], LIFConfig(thresh=32767, syn_shift=7))
    core.synaptic_event(0)
    assert core.v == [-1024]
    core.reset_state()
    core.synaptic_event(1)
    assert core.v == [896]


def test_e2_shift_zero_is_identity():
    # (E2) S_SYN=0: the raw weight is the contribution.
    core = single(5, thresh=32767, syn_shift=0)
    core.synaptic_event(0)
    assert core.v == [5]


# -- E3: saturating 16-bit integration ---------------------------------------

def test_e3_sat16_function_rails():
    # (E3) sat16 clamps exactly at the 16-bit signed rails.
    assert sat16(V_MAX) == V_MAX
    assert sat16(V_MAX + 1) == V_MAX
    assert sat16(V_MIN) == V_MIN
    assert sat16(V_MIN - 1) == V_MIN
    assert sat16(0) == 0


def test_e3_negative_rail_clamps_no_wraparound():
    # (E3) inhibition drives V to exactly -32768 and holds; a two's
    # complement wrap to positive would be a spec violation.
    core = single(-8, thresh=32767, syn_shift=7, leak_en=False)  # c = -1024
    for _ in range(32):
        core.synaptic_event(0)
    assert core.v == [V_MIN]  # 32 * -1024 = -32768 exactly
    for _ in range(100):
        core.synaptic_event(0)
    assert core.v == [V_MIN]  # clamped, never wraps


def test_e3_positive_overflow_saturates_then_spikes():
    # (E3)+(E4) V=32256 after 36 events of +896; event 37 sums to 33152,
    # saturates to +32767 and must spike (THETA=32767). An unsaturated
    # 16-bit wrap would give -32384 and silently lose the spike.
    core = single(7, thresh=32767, syn_shift=7, leak_en=False)  # c = +896
    for _ in range(36):
        assert core.synaptic_event(0) == []
    assert core.v == [32256]
    assert core.synaptic_event(0) == [0]
    assert core.v == [0]  # reset (E5)


# -- E4: spike condition, checked after the update ----------------------------

def test_e4_threshold_boundary_is_geq():
    # (E4) spike iff V' >= THETA: crossing to exactly THETA spikes;
    # THETA-1 does not.
    core = single(5, thresh=10, leak_en=False)
    assert core.synaptic_event(0) == []  # V = 5 < 10
    assert core.synaptic_event(0) == [0]  # V = 10 >= 10
    core = single(4, thresh=9, leak_en=False)
    core.synaptic_event(0)
    assert core.v == [4]
    assert core.synaptic_event(0) == []  # V = 8 = THETA-1: no spike
    assert core.v == [8]


def test_e4_check_after_update_not_one_event_late():
    # (E4) the compare uses the just-updated V', so a single event that
    # crosses threshold spikes on that event — not on the next one
    # (regression for the known check-one-step-early bug class).
    core = single(7, thresh=7)
    assert core.synaptic_event(0) == [0]  # first event, immediate spike


def test_e4_check_runs_even_for_zero_contribution():
    # (E4) evaluated on every non-gated event, including c == 0: a debug
    # state write above THETA fires on the next event touching the neuron.
    core = single(0, thresh=100, leak_en=False)
    core.set_state(0, 100)
    assert core.synaptic_event(0) == [0]
    assert core.v == [0]


# -- E5: reset on spike --------------------------------------------------------

def test_e5_reset_value_and_refractory_load():
    # (E5) on spike: V = V_RESET, R = T_REFR.
    core = single(7, thresh=10, v_reset=-3, refr_period=2, leak_en=False)
    core.synaptic_event(0)
    assert core.synaptic_event(0) == [0]  # 14 >= 10
    assert core.get_state(0) == (-3, 2)


def test_e5_emitted_id_includes_tile_offset():
    # (E5) emitted id = TILE_OFF + j (multi-pass tiling, spec section 9).
    core = LIFCore(2, 1, [[7, 7]], LIFConfig(thresh=7), tile_offset=32)
    assert core.synaptic_event(0) == [32, 33]


# -- E6: leak as right-shift toward zero ---------------------------------------

def test_e6_leak_hand_computed_values():
    # (E6) m = max(|V| >> S_LEAK, 1), applied toward zero.
    assert leak_value(100, 3) == 88  # m = 12
    assert leak_value(-100, 3) == -88  # symmetric
    assert leak_value(7, 3) == 6  # 7 >> 3 = 0 -> min step 1
    assert leak_value(-7, 3) == -6
    assert leak_value(1, 3) == 0  # reaches zero, never crosses
    assert leak_value(-1, 3) == 0
    assert leak_value(0, 3) == 0
    assert leak_value(100, 0) == 0  # S_LEAK = 0 clears in one tick
    assert leak_value(V_MIN, 0) == 0  # |-32768| exact at full magnitude
    assert leak_value(V_MIN, 15) == V_MIN + 1


def test_e6_leak_applied_on_tick():
    # (E6) tick applies the leak to the stored potential.
    core = single(7, thresh=32767, syn_shift=4, leak_shift=2)  # c = 112
    core.synaptic_event(0)
    assert core.v == [112]
    core.tick()
    assert core.v == [112 - (112 >> 2)]  # 84


def test_e6_leak_reaches_zero_in_bounded_ticks():
    # (E6) graceful degradation (spec 11.3): any corrupted V returns to 0
    # in bounded time thanks to the minimum step of 1.
    core = single(0, thresh=32767, leak_shift=3)
    core.set_state(0, V_MAX)
    for ticks in range(1, 200):
        core.tick()
        if core.v[0] == 0:
            break
    assert core.v == [0]
    assert ticks < 120  # order-100 bound at S_LEAK = 3, spec 11.3


def test_e6_leak_never_flips_sign():
    # (E6) the sign never flips on the way to zero.
    core = single(0, thresh=32767, leak_shift=1)
    core.set_state(0, -5)
    seen = []
    for _ in range(10):
        core.tick()
        seen.append(core.v[0])
    assert seen == [-3, -2, -1, 0, 0, 0, 0, 0, 0, 0]


def test_e6_leak_disable_flag():
    # (E6) gated by CFG_FLAGS.LEAK_EN.
    core = single(7, thresh=32767, leak_shift=0, leak_en=False)
    core.synaptic_event(0)
    core.tick()
    assert core.v == [7]


def test_e6_tick_never_spikes():
    # (spec 4.2) TICK events never emit: leak moves toward zero and
    # V_RESET < THETA is enforced, so no crossing is possible.
    core = single(7, thresh=10, leak_en=True)
    core.synaptic_event(0)  # V = 7
    assert core.tick() is None
    assert core.v[0] < 10


# -- E7: refractory gating and countdown ---------------------------------------

def test_e7_refractory_gates_and_counts_down():
    # (E7) events during refractory are discarded; TICK decrements R;
    # integration resumes when R reaches 0.
    core = single(7, thresh=50, syn_shift=3, refr_period=2, leak_en=False)
    assert core.synaptic_event(0) == [0]  # 56 >= 50, R := 2
    assert core.get_state(0) == (0, 2)
    assert core.synaptic_event(0) == []  # gated, no state change
    assert core.get_state(0) == (0, 2)
    core.tick()
    assert core.get_state(0) == (0, 1)
    assert core.synaptic_event(0) == []  # still gated
    core.tick()
    assert core.get_state(0) == (0, 0)
    assert core.synaptic_event(0) == [0]  # 56 >= 50 again


def test_e7_leak_applies_during_refractory():
    # (E7)/(E6) leak is independent of R: during refractory V still decays.
    core = single(7, thresh=50, syn_shift=3, refr_period=3,
                  v_reset=40, leak_shift=1)
    core.synaptic_event(0)  # spike, V = 40, R = 3
    core.tick()
    assert core.get_state(0) == (20, 2)


def test_e7_refr_zero_disables_refractory():
    # (E7) T_REFR = 0: back-to-back spikes are legal.
    core = single(7, thresh=7, refr_period=0, leak_en=False)
    assert core.synaptic_event(0) == [0]
    assert core.synaptic_event(0) == [0]


# -- E10: uncorrectable ECC word -> zero substitution --------------------------

def test_e10_poisoned_word_contributes_zero():
    # (E10) every weight in an uncorrectable 16-weight word contributes 0;
    # neurons in healthy words are unaffected (fail-operational).
    n = 2 * WEIGHTS_PER_WORD  # 32 neurons: axon 0 spans words 0 and 1
    core = LIFCore(n, 1, [[7] * n], LIFConfig(thresh=5, leak_en=False))
    assert core.word_index(0, 0) == 0
    assert core.word_index(0, WEIGHTS_PER_WORD) == 1
    core.poison_word(0)
    spikes = core.synaptic_event(0)
    assert spikes == list(range(WEIGHTS_PER_WORD, n))  # only word-1 neurons
    assert core.v[:WEIGHTS_PER_WORD] == [0] * WEIGHTS_PER_WORD


def test_e10_processing_continues_after_ded():
    # (E10) the core keeps processing after a DED: a different axon whose
    # weights live in a healthy word still works (fail-operational).
    core = LIFCore(WEIGHTS_PER_WORD, 2,
                   [[7] * WEIGHTS_PER_WORD, [7] * WEIGHTS_PER_WORD],
                   LIFConfig(thresh=5, leak_en=False))
    core.poison_word(core.word_index(0, 0))
    assert core.synaptic_event(0) == []  # dead word, no spikes
    assert core.synaptic_event(1) == list(range(WEIGHTS_PER_WORD))


# -- configuration validation (spec section 6, ERR_CFG conditions) -------------

@pytest.mark.parametrize("kwargs", [
    {"thresh": 0},
    {"thresh": V_MAX + 1},
    {"thresh": 100, "v_reset": 100},  # must be < THETA
    {"thresh": 100, "v_reset": V_MIN - 1},
    {"thresh": 100, "leak_shift": 16},
    {"thresh": 100, "leak_shift": -1},
    {"thresh": 100, "syn_shift": 8},
    {"thresh": 100, "refr_period": 16},
])
def test_config_validation_rejects_out_of_range(kwargs):
    with pytest.raises(ValueError):
        LIFConfig(**kwargs)


def test_config_validation_rejects_floats():
    with pytest.raises(TypeError):
        LIFConfig(thresh=100.0)


def test_axon_out_of_range_rejected():
    # spec section 6: hardware drops and counts CNT_AXON_OOR; the golden
    # model treats it as a stimulus error.
    core = single(7, thresh=100)
    with pytest.raises(ValueError):
        core.synaptic_event(1)
    with pytest.raises(ValueError):
        core.synaptic_event(-1)


def test_state_clr_matches_spec_reset_state():
    # spec section 3: post-STATE_CLR state is V = 0, R = 0.
    core = single(7, thresh=10, refr_period=3, leak_en=False)
    core.synaptic_event(0)
    core.synaptic_event(0)
    core.reset_state()
    assert core.get_state(0) == (0, 0)


# -- tile_offset bound (spec sections 7.1, 9, 10: 10-bit event-word ID) --------

def test_tile_offset_negative_rejected():
    # No hardware can emit a negative id; PASS_TILE_OFF is unsigned.
    with pytest.raises(ValueError):
        LIFCore(1, 1, [[0]], LIFConfig(thresh=100), tile_offset=-1)


def test_tile_offset_above_id_field_rejected():
    # PASS_TILE_OFF is bits [9:0]: 1024 is not programmable.
    with pytest.raises(ValueError):
        LIFCore(1, 1, [[0]], LIFConfig(thresh=100), tile_offset=1024)


def test_tile_offset_plus_neurons_overflow_rejected():
    # 1023 + 2 > 1024: neuron j = 1 would emit id 1024, which does not
    # fit the 10-bit ID field of the frozen event word.
    with pytest.raises(ValueError):
        LIFCore(2, 1, [[0, 0]], LIFConfig(thresh=100), tile_offset=1023)


def test_tile_offset_boundary_1024_accepted_and_emits_max_id():
    # Boundary: tile_offset 1023 + n_neurons 1 = exactly 1024 is legal;
    # the neuron emits id 1023, the largest representable event id.
    core = LIFCore(1, 1, [[7]], LIFConfig(thresh=5), tile_offset=1023)
    assert core.synaptic_event(0) == [1023]
