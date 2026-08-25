"""SECDED (72, 64) RTL vs golden-model cross-check.

Refinement evidence in the sense of docs/09 track 2: identical stimulus
into hw/rtl/secded_enc.v / hw/rtl/secded_dec.v and into the frozen Python
model sw/golden/secded.py, compared per transaction. Both DUTs are purely
combinational, so there is no clock and no reset - each vector is applied
and read back after a settle delay.

One module file serves two elaborations because cocotb has a single
toplevel per run. hw/tb/Makefile.secded sets SECDED_DUT to `enc` or `dec`
and runs the simulator twice; the tests of the other DUT are skipped in
each run.

Completeness note: the encoder and the decoder's syndrome path are linear
over GF(2), so agreeing with the model on the 64 one-hot data words plus
the zero word proves agreement on all 2^64 inputs. The one-hot sweeps
below are therefore exhaustive for those paths, not samples. The
correction path is nonlinear (the syndrome-to-column match), so it is
swept exhaustively over all 72 single-bit error positions and over the
double-bit pairs listed in each test.
"""

import itertools
import os
import random
import sys
from pathlib import Path

import cocotb
from cocotb.triggers import Timer

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sw"))

from golden.secded import (  # noqa: E402
    CODE_BITS,
    COLUMNS,
    DATA_BITS,
    DATA_MASK,
    check_bits,
    column_of_bit,
    decode,
    encode,
    flip,
)

DUT_KIND = os.environ.get("SECDED_DUT", "dec")
# Skip flags: the tests of the DUT this run did not elaborate.
SKIP_ENC_TESTS = DUT_KIND != "enc"
SKIP_DEC_TESTS = DUT_KIND != "dec"

SETTLE_NS = 1

PATTERNS = [
    0x0000000000000000,
    0xFFFFFFFFFFFFFFFF,
    0xAAAAAAAAAAAAAAAA,
    0x5555555555555555,
    0x0123456789ABCDEF,
]


def _rng(seed):
    return random.Random(seed)


async def drive_enc(dut, data):
    """Apply one data word to secded_enc; return (check_out, code_out)."""
    dut.data_in.value = data
    await Timer(SETTLE_NS, unit="ns")
    return int(dut.check_out.value), int(dut.code_out.value)


async def drive_dec(dut, code):
    """Apply one received word to secded_dec; return the decoded tuple."""
    dut.code_in.value = code
    await Timer(SETTLE_NS, unit="ns")
    return (int(dut.data_out.value), int(dut.syndrome.value),
            int(dut.sec.value), int(dut.ded.value))


def _assert_dec_matches(got, code, note=""):
    data_out, syndrome, sec, ded = got
    expect = decode(code)
    assert syndrome == expect.syndrome, (
        f"{note}syndrome 0x{syndrome:02X}, model 0x{expect.syndrome:02X} "
        f"for code 0x{code:018X}")
    assert sec == expect.sec, f"{note}sec {sec}, model {expect.sec}"
    assert ded == expect.ded, f"{note}ded {ded}, model {expect.ded}"
    assert data_out == expect.data, (
        f"{note}data 0x{data_out:016X}, model 0x{expect.data:016X}")


# ---------------------------------------------------------------------
# Encoder
# ---------------------------------------------------------------------


@cocotb.test(skip=SKIP_ENC_TESTS)
async def test_enc_h_matrix_is_exhaustive_over_the_basis(dut):
    """One-hot sweep: check_out for data = 1 << j must be H column j.

    The encoder is linear, so these 64 vectors plus the zero word pin the
    whole 2^64-input function to the model's matrix.
    """
    check, code = await drive_enc(dut, 0)
    assert check == 0, "the all-zero word must encode to zero check bits"
    assert code == 0
    for j in range(DATA_BITS):
        check, code = await drive_enc(dut, 1 << j)
        assert check == COLUMNS[j], (
            f"data bit {j}: check 0x{check:02X}, model column "
            f"0x{COLUMNS[j]:02X}")
        assert check == check_bits(1 << j)
        assert code == encode(1 << j)


@cocotb.test(skip=SKIP_ENC_TESTS)
async def test_enc_matches_model_on_patterns_and_random_words(dut):
    rng = _rng(0x5ECDED0)
    words = list(PATTERNS) + [rng.getrandbits(DATA_BITS) for _ in range(500)]
    for data in words:
        check, code = await drive_enc(dut, data)
        assert check == check_bits(data), f"check bits diverged for 0x{data:016X}"
        assert code == encode(data), f"codeword diverged for 0x{data:016X}"
        assert code & DATA_MASK == data, "the code must stay systematic"
        assert code >> DATA_BITS == check


@cocotb.test(skip=SKIP_ENC_TESTS)
async def test_enc_is_linear(dut):
    """encode(a ^ b) == encode(a) ^ encode(b) in the RTL, as in the model."""
    rng = _rng(0x5ECDED1)
    for _ in range(100):
        a = rng.getrandbits(DATA_BITS)
        b = rng.getrandbits(DATA_BITS)
        _, code_a = await drive_enc(dut, a)
        _, code_b = await drive_enc(dut, b)
        _, code_ab = await drive_enc(dut, a ^ b)
        assert code_ab == (code_a ^ code_b)


# ---------------------------------------------------------------------
# Decoder: clean words and the syndrome path
# ---------------------------------------------------------------------


@cocotb.test(skip=SKIP_DEC_TESTS)
async def test_dec_clean_words_pass_through(dut):
    rng = _rng(0x5ECDED2)
    words = list(PATTERNS) + [rng.getrandbits(DATA_BITS) for _ in range(300)]
    for data in words:
        code = encode(data)
        got = await drive_dec(dut, code)
        assert got == (data, 0, 0, 0), (
            f"clean word 0x{code:018X} decoded to {got}")
        _assert_dec_matches(got, code)


@cocotb.test(skip=SKIP_DEC_TESTS)
async def test_dec_syndrome_path_is_exhaustive_over_the_basis(dut):
    """With the check field forced to zero, the syndrome is exactly the
    encoder function of the data field. Sweeping the 64 one-hot data words
    pins the decoder's copy of the H matrix to the model's, and hence to
    the encoder's."""
    for j in range(DATA_BITS):
        _, syndrome, sec, ded = await drive_dec(dut, 1 << j)
        assert syndrome == COLUMNS[j], (
            f"data bit {j}: syndrome 0x{syndrome:02X}, model column "
            f"0x{COLUMNS[j]:02X}")
        assert (sec, ded) == (1, 0), "a one-hot data word is one error from 0"
    for i in range(CODE_BITS - DATA_BITS):
        _, syndrome, sec, ded = await drive_dec(dut, 1 << (DATA_BITS + i))
        assert syndrome == column_of_bit(DATA_BITS + i)
        assert (sec, ded) == (1, 0)


# ---------------------------------------------------------------------
# Decoder: exhaustive single-bit correction
# ---------------------------------------------------------------------


@cocotb.test(skip=SKIP_DEC_TESTS)
async def test_dec_single_bit_correction_all_positions(dut):
    """Every one of the 72 bit positions, for every data pattern."""
    for data in PATTERNS:
        code = encode(data)
        for bit in range(CODE_BITS):
            corrupted = flip(code, [bit])
            got = await drive_dec(dut, corrupted)
            _assert_dec_matches(got, corrupted, f"bit {bit}: ")
            data_out, syndrome, sec, ded = got
            assert sec == 1 and ded == 0, f"bit {bit} not corrected"
            assert data_out == data, f"bit {bit} corrected to the wrong word"
            assert syndrome == column_of_bit(bit)


@cocotb.test(skip=SKIP_DEC_TESTS)
async def test_dec_single_bit_correction_random_words(dut):
    rng = _rng(0x5ECDED3)
    for _ in range(40):
        data = rng.getrandbits(DATA_BITS)
        code = encode(data)
        for bit in range(CODE_BITS):
            corrupted = flip(code, [bit])
            data_out, _, sec, ded = await drive_dec(dut, corrupted)
            assert (sec, ded) == (1, 0)
            assert data_out == data


# ---------------------------------------------------------------------
# Decoder: double-bit detection without miscorrection
# ---------------------------------------------------------------------


@cocotb.test(skip=SKIP_DEC_TESTS)
async def test_dec_double_bit_adjacent_pairs(dut):
    """All adjacent pairs - the physically most likely multi-bit upset."""
    for data in PATTERNS:
        code = encode(data)
        for bit in range(CODE_BITS - 1):
            corrupted = flip(code, [bit, bit + 1])
            got = await drive_dec(dut, corrupted)
            _assert_dec_matches(got, corrupted, f"pair ({bit},{bit + 1}): ")
            data_out, syndrome, sec, ded = got
            assert ded == 1 and sec == 0, f"pair ({bit},{bit + 1}) miscorrected"
            assert data_out == corrupted & DATA_MASK, "silent repair on a DED"


@cocotb.test(skip=SKIP_DEC_TESTS)
async def test_dec_double_bit_every_pair_for_one_pattern(dut):
    """All C(72, 2) = 2556 pairs: the complete double-error space for one
    data word."""
    data = 0x0123456789ABCDEF
    code = encode(data)
    for lo, hi in itertools.combinations(range(CODE_BITS), 2):
        corrupted = flip(code, [lo, hi])
        got = await drive_dec(dut, corrupted)
        _, _, sec, ded = got
        assert ded == 1 and sec == 0, f"pair ({lo},{hi}) not detected"
        _assert_dec_matches(got, corrupted, f"pair ({lo},{hi}): ")


@cocotb.test(skip=SKIP_DEC_TESTS)
async def test_dec_double_bit_sampled_distant_pairs(dut):
    """Distant pairs across all patterns: deterministic strides plus a
    seeded random sample."""
    rng = _rng(0x5ECDED4)
    for data in PATTERNS:
        code = encode(data)
        for lo in range(CODE_BITS):
            for gap in (8, 31, 63):
                hi = lo + gap
                if hi < CODE_BITS:
                    corrupted = flip(code, [lo, hi])
                    got = await drive_dec(dut, corrupted)
                    _, _, sec, ded = got
                    assert ded == 1 and sec == 0, f"pair ({lo},{hi}) missed"
                    _assert_dec_matches(got, corrupted, f"pair ({lo},{hi}): ")
        for _ in range(100):
            lo = rng.randrange(CODE_BITS - 1)
            hi = rng.randrange(lo + 1, CODE_BITS)
            corrupted = flip(code, [lo, hi])
            got = await drive_dec(dut, corrupted)
            _, _, sec, ded = got
            assert ded == 1 and sec == 0, f"pair ({lo},{hi}) missed"
            _assert_dec_matches(got, corrupted, f"pair ({lo},{hi}): ")


# ---------------------------------------------------------------------
# Decoder: agreement outside the guaranteed distance
# ---------------------------------------------------------------------


@cocotb.test(skip=SKIP_DEC_TESTS)
async def test_dec_matches_model_on_arbitrary_words(dut):
    """Fully random received words, i.e. arbitrary error weight. The code
    has minimum distance 4, so no correction claim is made beyond weight 2
    (a triple error can alias onto a single-error syndrome); what is
    checked here is that the RTL and the model behave identically, which is
    what the refinement argument needs."""
    rng = _rng(0x5ECDED5)
    for _ in range(1500):
        word = rng.getrandbits(CODE_BITS)
        got = await drive_dec(dut, word)
        _assert_dec_matches(got, word)


@cocotb.test(skip=SKIP_DEC_TESTS)
async def test_dec_matches_model_on_triple_bit_errors(dut):
    rng = _rng(0x5ECDED6)
    for data in PATTERNS:
        code = encode(data)
        for _ in range(200):
            bits = rng.sample(range(CODE_BITS), 3)
            corrupted = flip(code, bits)
            got = await drive_dec(dut, corrupted)
            _assert_dec_matches(got, corrupted, f"triple {sorted(bits)}: ")
            _, _, sec, ded = got
            assert sec + ded >= 1, "a weight-3 error must not look clean"
