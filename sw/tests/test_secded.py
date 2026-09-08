# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Tests for the (72, 64) SECDED golden model (sw/golden/secded.py).

Coverage, matching the acceptance criteria of docs/09 target #2:

  * the parity-check matrix really is a Hsiao matrix (distinct, nonzero,
    odd-weight columns; balanced rows) - the property everything else
    rests on;
  * decode(encode(x)) == x, and syndrome == 0 exactly for codewords;
  * EXHAUSTIVE single-bit correction: every one of the 72 codeword bit
    positions, for several data patterns;
  * double-bit detection with no miscorrection: every adjacent pair, plus
    every pair at all (2556 of them) for one pattern, plus sampled
    distant pairs for other patterns;
  * fault-counter semantics of docs/10 sections 10 and 11.2 (CNT_SEC,
    CNT_DED, FAULT_ADDR, STATUS.DED_SEEN), including the split between
    the two clear ports: FAULT_CLR (0x88) owns the fault block and
    STATUS_CLR (0x14) owns the sticky DED_SEEN bit.

What this file deliberately does NOT check is where those clear bits SIT.
The tests below exercise the FAULT_CLR_* and STATUS_DED_SEEN constants as
the model's own vocabulary, so they hold whatever numeric values the
constants happen to have; a bit that drifted away from regmap/regmap.yaml
would keep every test here green. Anchoring the constants to the
generated register map is a register-map question and lives with the
other single-source checks, in sw/tests/test_regmap.py (see
test_secded_fault_clr_constants_are_the_yaml_bit_positions and its
neighbours).

Test names deliberately avoid the test_e<n>_* form: those are reserved by
sw/tests/test_traceability.py for the numbered spec equations E1..E10.
"""

import itertools
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from golden.secded import (
    CHECK_BITS,
    CHECK_COLUMNS,
    CODE_BITS,
    COLUMNS,
    DATA_BITS,
    DATA_MASK,
    EccCounters,
    FAULT_CLR_ALL,
    FAULT_CLR_CNT_DED,
    FAULT_CLR_CNT_SEC,
    FAULT_CLR_FAULT_ADDR,
    ROW_MASKS,
    STATUS_DED_SEEN,
    check_bits,
    column_of_bit,
    decode,
    encode,
    flip,
    parity,
    syndrome,
)

# Data patterns used across the fault-injection tests: the two extremes,
# two stripe patterns that stress every XOR tree, and reproducible random
# words. Kept small because several tests are quadratic in the number of
# codeword bits.
_RNG = random.Random(20260825)
PATTERNS = [
    0x0000000000000000,
    0xFFFFFFFFFFFFFFFF,
    0xAAAAAAAAAAAAAAAA,
    0x5555555555555555,
    0x0123456789ABCDEF,
] + [_RNG.getrandbits(DATA_BITS) for _ in range(5)]


def popcount(value):
    return bin(value).count("1")


# ---------------------------------------------------------------------
# Matrix structure: the Hsiao preconditions
# ---------------------------------------------------------------------


def test_matrix_shape():
    assert DATA_BITS == 64 and CHECK_BITS == 8 and CODE_BITS == 72
    assert len(COLUMNS) == DATA_BITS
    assert len(CHECK_COLUMNS) == CHECK_BITS
    assert len(ROW_MASKS) == CHECK_BITS


def test_matrix_columns_are_distinct_nonzero_and_odd():
    columns = [column_of_bit(i) for i in range(CODE_BITS)]
    assert len(set(columns)) == CODE_BITS, "columns must be distinct (SEC)"
    assert all(col != 0 for col in columns), "a zero column is undetectable"
    assert all(popcount(col) % 2 == 1 for col in columns), (
        "odd column weight is what separates 1-bit from 2-bit syndromes")
    assert all(col < (1 << CHECK_BITS) for col in columns)


def test_matrix_column_weight_distribution():
    weights = sorted(popcount(col) for col in COLUMNS)
    assert weights.count(3) == 56
    assert weights.count(5) == 8
    assert len(weights) == 64


def test_matrix_rows_are_balanced():
    # 26 data bits per check bit, plus its own identity bit: weight 27 on
    # every row, so all eight XOR trees have the same depth.
    for i, mask in enumerate(ROW_MASKS):
        assert popcount(mask) == 26, f"row {i} weight {popcount(mask)}"
    assert sum(popcount(m) for m in ROW_MASKS) + CHECK_BITS == 216


def test_row_and_column_views_agree():
    for j, col in enumerate(COLUMNS):
        for i in range(CHECK_BITS):
            assert ((col >> i) & 1) == ((ROW_MASKS[i] >> j) & 1)


def test_check_columns_are_the_identity_block():
    assert CHECK_COLUMNS == tuple(1 << i for i in range(CHECK_BITS))
    for i in range(CHECK_BITS):
        assert column_of_bit(DATA_BITS + i) == (1 << i)


# ---------------------------------------------------------------------
# Encode / decode identity and syndrome definition
# ---------------------------------------------------------------------


def test_encode_layout():
    for data in PATTERNS:
        code = encode(data)
        assert code >> 72 == 0
        assert code & DATA_MASK == data, "data field must be systematic"
        assert (code >> DATA_BITS) == check_bits(data)


def test_encode_decode_identity():
    words = list(PATTERNS) + [_RNG.getrandbits(DATA_BITS) for _ in range(200)]
    for data in words:
        result = decode(encode(data))
        assert result.data == data
        assert result.sec == 0 and result.ded == 0
        assert result.syndrome == 0
        assert result.err_index is None


def test_encode_is_linear():
    # A linear code: the encoder of the RTL is a pure XOR tree, so this
    # must hold bit for bit.
    for _ in range(200):
        a = _RNG.getrandbits(DATA_BITS)
        b = _RNG.getrandbits(DATA_BITS)
        assert encode(a ^ b) == encode(a) ^ encode(b)


def test_syndrome_zero_exactly_for_codewords():
    for data in PATTERNS:
        assert syndrome(encode(data)) == 0
    for _ in range(500):
        word = _RNG.getrandbits(CODE_BITS)
        if syndrome(word) == 0:
            assert word == encode(word & DATA_MASK)
        else:
            assert word != encode(word & DATA_MASK)


def test_syndrome_of_single_error_is_the_column():
    for data in (PATTERNS[0], PATTERNS[4]):
        code = encode(data)
        for bit in range(CODE_BITS):
            assert syndrome(flip(code, [bit])) == column_of_bit(bit)


# ---------------------------------------------------------------------
# Single-bit correction: exhaustive over positions
# ---------------------------------------------------------------------


def test_single_bit_correction_is_exhaustive_over_positions():
    for data in PATTERNS:
        code = encode(data)
        for bit in range(CODE_BITS):
            result = decode(flip(code, [bit]))
            assert result.sec == 1, f"bit {bit} of 0x{data:016X} not corrected"
            assert result.ded == 0
            assert result.data == data, f"bit {bit}: correction produced wrong data"
            assert result.err_index == bit
            assert result.syndrome == column_of_bit(bit)
            assert parity(result.syndrome) == 1


def test_single_bit_correction_restores_the_whole_codeword():
    # A corrected data field must re-encode to the original codeword, i.e.
    # the decoder lands back on the transmitted codeword, not merely on a
    # codeword.
    for data in PATTERNS:
        code = encode(data)
        for bit in range(CODE_BITS):
            result = decode(flip(code, [bit]))
            assert encode(result.data) == code


def test_check_bit_error_does_not_touch_the_data_field():
    for data in PATTERNS:
        code = encode(data)
        for i in range(CHECK_BITS):
            result = decode(flip(code, [DATA_BITS + i]))
            assert result.sec == 1 and result.ded == 0
            assert result.data == data
            assert result.err_index == DATA_BITS + i


# ---------------------------------------------------------------------
# Double-bit detection: no miscorrection anywhere
# ---------------------------------------------------------------------


def _assert_detected_not_corrected(code, pair, data):
    corrupted = flip(code, pair)
    result = decode(corrupted)
    assert result.ded == 1, f"pair {pair} of 0x{data:016X} not detected"
    assert result.sec == 0, f"pair {pair} miscorrected (sec asserted)"
    assert result.syndrome != 0
    assert parity(result.syndrome) == 0, "two odd columns XOR to even parity"
    assert result.err_index is None
    # the data field is passed through untouched: no silent repair
    assert result.data == corrupted & DATA_MASK
    # and the result is never a valid codeword masquerading as clean
    assert syndrome(corrupted) != 0


def test_double_bit_detection_all_adjacent_pairs():
    for data in PATTERNS:
        code = encode(data)
        for bit in range(CODE_BITS - 1):
            _assert_detected_not_corrected(code, (bit, bit + 1), data)


def test_double_bit_detection_every_pair_for_one_pattern():
    # All C(72, 2) = 2556 pairs, i.e. the complete double-error space for
    # this data word.
    data = 0x0123456789ABCDEF
    code = encode(data)
    pairs = list(itertools.combinations(range(CODE_BITS), 2))
    assert len(pairs) == 2556
    for pair in pairs:
        _assert_detected_not_corrected(code, pair, data)


def test_double_bit_detection_sampled_distant_pairs():
    rng = random.Random(0x5ECDED)
    for data in PATTERNS:
        code = encode(data)
        # deterministic stride sample across the whole word, always with a
        # distance of at least 8 between the two flips
        for lo in range(CODE_BITS):
            for gap in (8, 17, 31, 47, 63):
                hi = lo + gap
                if hi < CODE_BITS:
                    _assert_detected_not_corrected(code, (lo, hi), data)
        for _ in range(200):
            lo = rng.randrange(CODE_BITS - 1)
            hi = rng.randrange(lo + 1, CODE_BITS)
            _assert_detected_not_corrected(code, (lo, hi), data)


def test_double_bit_in_check_field_is_detected():
    for data in PATTERNS:
        code = encode(data)
        for pair in itertools.combinations(range(DATA_BITS, CODE_BITS), 2):
            _assert_detected_not_corrected(code, pair, data)


def test_data_check_cross_pairs_are_detected():
    data = 0xA5A5A5A5DEADBEEF
    code = encode(data)
    for j in range(DATA_BITS):
        for i in range(CHECK_BITS):
            _assert_detected_not_corrected(code, (j, DATA_BITS + i), data)


# ---------------------------------------------------------------------
# Injection helper
# ---------------------------------------------------------------------


def test_flip_cancels_repeated_positions():
    code = encode(0x0123456789ABCDEF)
    assert flip(code, []) == code
    assert flip(code, [5, 5]) == code
    assert flip(code, [5, 9, 5]) == flip(code, [9])


def test_flip_rejects_out_of_range_positions():
    code = encode(0)
    with pytest.raises(ValueError):
        flip(code, [CODE_BITS])
    with pytest.raises(ValueError):
        flip(code, [-1])


# ---------------------------------------------------------------------
# Input discipline (plain ints only, like the LIF golden model)
# ---------------------------------------------------------------------


def test_model_rejects_non_int_and_out_of_range_inputs():
    with pytest.raises(TypeError):
        encode(1.0)
    with pytest.raises(TypeError):
        encode(True)
    with pytest.raises(ValueError):
        encode(1 << DATA_BITS)
    with pytest.raises(ValueError):
        encode(-1)
    with pytest.raises(ValueError):
        syndrome(1 << CODE_BITS)
    with pytest.raises(ValueError):
        column_of_bit(CODE_BITS)


def test_model_returns_plain_ints():
    result = decode(encode(0x0123456789ABCDEF))
    assert type(result.data) is int
    assert type(result.sec) is int and type(result.ded) is int
    assert type(result.syndrome) is int


# ---------------------------------------------------------------------
# Fault-counter semantics (docs/10 sections 10, 11.2)
# ---------------------------------------------------------------------


def test_counters_start_clear():
    counters = EccCounters()
    assert counters.cnt_sec == 0
    assert counters.cnt_ded == 0
    assert counters.fault_addr == 0
    assert counters.ded_seen == 0


def test_counters_count_sec_and_ded_separately():
    counters = EccCounters()
    code = encode(0x0123456789ABCDEF)
    for bit in range(CODE_BITS):
        counters.observe(decode(flip(code, [bit])), word_index=bit)
    assert counters.cnt_sec == CODE_BITS
    assert counters.cnt_ded == 0
    assert counters.ded_seen == 0
    assert counters.fault_addr == 0, "a corrected error must not latch FAULT_ADDR"

    counters.observe(decode(flip(code, [3, 40])), word_index=1234)
    assert counters.cnt_sec == CODE_BITS, "DED must not bump CNT_SEC"
    assert counters.cnt_ded == 1
    assert counters.ded_seen == 1
    assert counters.fault_addr == 1234


def test_clean_reads_do_not_move_any_counter():
    counters = EccCounters()
    for data in PATTERNS:
        counters.observe(decode(encode(data)), word_index=7)
    assert counters.cnt_sec == 0 and counters.cnt_ded == 0
    assert counters.ded_seen == 0 and counters.fault_addr == 0


def test_fault_addr_latches_the_last_ded_and_ded_seen_is_sticky():
    counters = EccCounters()
    code = encode(0)
    counters.observe(decode(flip(code, [0, 1])), word_index=11)
    counters.observe(decode(flip(code, [2, 3])), word_index=22)
    assert counters.fault_addr == 22, "FAULT_ADDR holds the most recent DED"
    counters.observe(decode(flip(code, [9])), word_index=33)  # corrected
    assert counters.fault_addr == 22, "a SEC must not disturb FAULT_ADDR"
    assert counters.ded_seen == 1, "DED_SEEN is sticky until STATUS_CLR"
    assert counters.cnt_ded == 2 and counters.cnt_sec == 1


def _counters_with_one_sec_and_one_ded(word_index=5):
    counters = EccCounters()
    code = encode(0)
    counters.observe(decode(flip(code, [0, 1])), word_index=word_index)  # DED
    counters.observe(decode(flip(code, [7])), word_index=word_index)     # SEC
    assert (counters.cnt_sec, counters.cnt_ded) == (1, 1)
    assert counters.fault_addr == word_index and counters.ded_seen == 1
    return counters


def test_fault_clr_clears_the_fault_block_but_not_ded_seen():
    # FAULT_CLR is at 0x88 and owns the fault block (0x70..0x80).
    # STATUS.DED_SEEN is STATUS bit 5 and is NOT in that block, so it
    # survives this write - hw/rtl/npu_regbank.v implements exactly this.
    counters = _counters_with_one_sec_and_one_ded()
    counters.fault_clr()
    assert counters.cnt_sec == 0 and counters.cnt_ded == 0
    assert counters.fault_addr == 0
    assert counters.ded_seen == 1, "FAULT_CLR must not clear STATUS.DED_SEEN"


def test_status_clr_clears_ded_seen_but_not_the_fault_block():
    # The mirror image: STATUS_CLR (0x14) clears the sticky STATUS bit and
    # leaves the counters and the latched address alone.
    counters = _counters_with_one_sec_and_one_ded(word_index=9)
    counters.status_clr()
    assert counters.ded_seen == 0
    assert counters.cnt_sec == 1 and counters.cnt_ded == 1
    assert counters.fault_addr == 9, "STATUS_CLR must not clear FAULT_ADDR"


def test_clearing_both_registers_returns_the_block_to_its_reset_state():
    counters = _counters_with_one_sec_and_one_ded()
    counters.fault_clr()
    counters.status_clr()
    assert counters.cnt_sec == 0 and counters.cnt_ded == 0
    assert counters.fault_addr == 0 and counters.ded_seen == 0


def test_fault_clr_mask_selects_individual_registers():
    counters = _counters_with_one_sec_and_one_ded(word_index=77)
    counters.fault_clr(FAULT_CLR_CNT_SEC)
    assert counters.cnt_sec == 0
    assert counters.cnt_ded == 1 and counters.fault_addr == 77

    counters.fault_clr(FAULT_CLR_CNT_DED)
    assert counters.cnt_ded == 0 and counters.fault_addr == 77

    counters.fault_clr(FAULT_CLR_FAULT_ADDR)
    assert counters.fault_addr == 0
    assert counters.ded_seen == 1, "no FAULT_CLR bit reaches DED_SEEN"

    # Bits [31:5] are ignored by the hardware: writing them changes nothing.
    counters = _counters_with_one_sec_and_one_ded(word_index=77)
    counters.fault_clr(~FAULT_CLR_ALL & 0xFFFFFFFF)
    assert counters.cnt_sec == 1 and counters.cnt_ded == 1
    assert counters.fault_addr == 77 and counters.ded_seen == 1


def test_status_clr_only_acts_on_its_own_bit():
    counters = _counters_with_one_sec_and_one_ded()
    # A STATUS_CLR write that does not select bit 5 leaves DED_SEEN set:
    # the other sticky STATUS bits belong to the register bank.
    counters.status_clr(~STATUS_DED_SEEN & 0xFFFFFFFF)
    assert counters.ded_seen == 1
    counters.status_clr(STATUS_DED_SEEN)
    assert counters.ded_seen == 0


def test_reset_clears_everything():
    counters = _counters_with_one_sec_and_one_ded()
    counters.reset()
    assert counters.cnt_sec == 0 and counters.cnt_ded == 0
    assert counters.fault_addr == 0 and counters.ded_seen == 0


def test_ded_seen_is_re_set_by_a_later_ded_after_status_clr():
    counters = _counters_with_one_sec_and_one_ded()
    counters.status_clr()
    counters.fault_clr()
    counters.observe(decode(flip(encode(0), [4, 5])), word_index=64)
    assert counters.ded_seen == 1 and counters.cnt_ded == 1
    assert counters.fault_addr == 64


def test_clear_masks_reject_bad_arguments():
    counters = EccCounters()
    with pytest.raises(TypeError):
        counters.fault_clr(1.0)
    with pytest.raises(ValueError):
        counters.fault_clr(-1)
    with pytest.raises(ValueError):
        counters.fault_clr(1 << 32)
    with pytest.raises(TypeError):
        counters.status_clr(1.0)
    with pytest.raises(ValueError):
        counters.status_clr(1 << 32)


def test_counters_saturate_instead_of_wrapping():
    # House convention: a wrapped fault counter would erase the record it
    # exists to keep. Narrow width so the test stays cheap.
    counters = EccCounters(width=3)
    code = encode(0)
    for _ in range(20):
        counters.observe(decode(flip(code, [1])), word_index=0)
        counters.observe(decode(flip(code, [1, 2])), word_index=0)
    assert counters.cnt_sec == 7
    assert counters.cnt_ded == 7


def test_counters_reject_bad_arguments():
    with pytest.raises(ValueError):
        EccCounters(width=0)
    with pytest.raises(TypeError):
        EccCounters(width=8.0)
    counters = EccCounters()
    with pytest.raises(ValueError):
        counters.observe(decode(encode(0)), word_index=-1)
