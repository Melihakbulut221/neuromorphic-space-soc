#!/usr/bin/env python3
"""Emit the NPU end-to-end demonstration's stimulus AND its expected
answer, computed by the golden model, as a C header for the boot ROM.

WHY THIS EXISTS, which is the whole point of the file.

The program in hw/soc/tb/sw/test_ibex.c runs an inference on the NPU and
has to decide whether the answer is right. It must NOT decide that by
asking the hardware -- a check against what the silicon happened to
produce proves that the silicon is self-consistent and nothing else.
docs/10 section 13 makes sw/golden/lif_core.py the normative executable
form of the section 4 equations, so the answer is computed HERE, from
that model, at build time, and the program compares against a constant.

Nothing in this file reads any RTL, and the stimulus is chosen before
the answer is known.

Run:  python3 hw/soc/flow/gen_npu_vectors.py hw/soc/out/sim-soc

Emits two headers into <out>, both build output rather than tracked
sources, so neither can go stale against its source:

  npu_regs.h     the NODE register map -- every offset, reset value and
                 field position of regmap/regmap.yaml, in C. The same
                 single source that produces hw/rtl/npu_regs.vh for the
                 die and sw/golden/regmap_gen.py for the tests. No
                 offset of that map is written by hand anywhere in the
                 program.
  npu_vectors.h  this demonstration's stimulus and the golden model's
                 answer to it.

The NPUCFG block's OWN register map is not here: it is
hw/soc/tb/sw/soc_npucfg.h, hand-written, exactly as soc_timers.h is for
the GPTIMER, because regmap/memmap.yaml describes where a block lives
and has never described what is inside one (docs/40 section 8.1).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sw"))

from golden.lif_core import LIFConfig, LIFCore      # noqa: E402
from golden.regmap_gen import ADDR, FIELDS, RESET   # noqa: E402

# ---------------------------------------------------------------------
# The pilot as soc_top.v elaborates it
# ---------------------------------------------------------------------
N_NEURONS = 8
N_AXONS = 8
WEIGHTS_PER_WORD = 16          # docs/10 section 5

# docs/10 section 7.1 TYPE encoding
TYPE_SPIKE = 0 << 14
TYPE_TICK = 1 << 14
TYPE_SYNC = 2 << 14

# ---------------------------------------------------------------------
# The stimulus
#
# Chosen to exercise the arithmetic rather than to be easy: a synaptic
# shift so weights are scaled (E2), a threshold low enough that several
# neurons fire (E4), a reset potential below zero so V_RESET is visibly
# not zero (E5), leak enabled with a shift that takes more than one tick
# to return (E6), and a refractory period so gating happens (E7). An
# empty frame is in the list because a TICK with no synaptic event is
# the case where E6 and E7 run alone.
#
# These are hw/tb/test_pilot_top.py's CFG and FRAMES, deliberately
# unchanged: the pilot's own suite already establishes that this
# stimulus produces spikes worth comparing, and running the SAME
# stimulus through the SoC makes the two results directly comparable.
# ---------------------------------------------------------------------
CFG = LIFConfig(thresh=20, v_reset=-4, leak_shift=2, syn_shift=2,
                refr_period=2, leak_en=True)
FRAMES = [[0, 1], [2], [1, 1, 3], [], [0, 2, 3], [3]]
WEIGHT_SEED = 20260921


def make_weights(n_axons, n_neurons, seed=WEIGHT_SEED):
    """Deterministic weight matrix. Same construction and same seed as
    hw/tb/test_pilot_top.py, so the SoC run and the pilot's own run are
    the same inference on the same numbers."""
    import random
    rng = random.Random(seed)
    return [[rng.randint(-8, 7) for _ in range(n_neurons)]
            for _ in range(n_axons)]


def pack_words(weights, n_neurons):
    """weights[axon][neuron] -> 64-bit ECC data words.

    docs/10 section 5: linear index (a * N_NEURONS + j), axon-major,
    sixteen 4-bit weights per 64-bit word, weight k at bits [4k+3:4k].
    """
    flat = [w for row in weights for w in row]
    words = []
    for base in range(0, len(flat), WEIGHTS_PER_WORD):
        word = 0
        for k, w in enumerate(flat[base:base + WEIGHTS_PER_WORD]):
            word |= (w & 0xF) << (4 * k)
        words.append(word)
    return words


def build():
    weights = make_weights(N_AXONS, N_NEURONS)
    core = LIFCore(N_NEURONS, N_AXONS, weights, CFG)
    per_frame = core.run_frames(FRAMES)

    # The injected stream, one frame at a time: the frame's spikes in
    # arrival order, then a TICK, then a SYNC whose ID field carries the
    # frame number.
    #
    # SYNC IS THE REASON THE STREAM IS SELF-DELIMITING. docs/10 section
    # 7.1 makes it the frame barrier: when the node consumes it, every
    # prior event is fully processed and the barrier is echoed
    # downstream. So the program does not have to guess how many spikes
    # a frame produces or how long to wait -- it reads until the echo.
    inject = []
    expect = []
    for k, frame in enumerate(FRAMES):
        for axon in frame:
            inject.append(TYPE_SPIKE | axon)
        inject.append(TYPE_TICK)
        inject.append(TYPE_SYNC | k)
        for sid in per_frame[k]:
            expect.append(TYPE_SPIKE | sid)
        # hw/rtl/pilot_top.v echoes the CONSUMED word, so the barrier
        # comes back carrying its own frame number.
        expect.append(TYPE_SYNC | k)

    frame_len = [len(f) + 2 for f in FRAMES]
    expect_len = [len(s) + 1 for s in per_frame]
    state = [core.get_state(j) for j in range(N_NEURONS)]
    return weights, per_frame, inject, expect, frame_len, expect_len, state


def emit(out):
    (weights, per_frame, inject, expect,
     frame_len, expect_len, state) = build()
    words = pack_words(weights, N_NEURONS)

    n_spikes = sum(len(s) for s in per_frame)
    if n_spikes == 0:
        sys.exit("the stimulus produces no spikes; it would check nothing")

    L = []
    L.append("/* GENERATED by hw/soc/flow/gen_npu_vectors.py. Do not edit. */")
    L.append("/*")
    L.append(" * The NPU end-to-end demonstration's stimulus and its EXPECTED")
    L.append(" * ANSWER, the latter computed by sw/golden/lif_core.py, which")
    L.append(" * docs/10 section 13 makes the normative executable form of the")
    L.append(" * section 4 equations. The program checks the hardware against")
    L.append(" * these constants and never against itself.")
    L.append(" */")
    L.append("#ifndef NPU_VECTORS_H")
    L.append("#define NPU_VECTORS_H")
    L.append("")
    L.append("#include <stdint.h>")
    L.append("")
    L.append("/* geometry, as soc_top.v elaborates the pilot */")
    L.append(f"#define NPUV_N_NEURONS {N_NEURONS}")
    L.append(f"#define NPUV_N_AXONS   {N_AXONS}")
    L.append("")
    L.append("/* docs/10 section 6 configuration, by generated register offset */")
    for name, value in [
        ("CFG_THRESH", CFG.thresh & 0xFFFF),
        ("CFG_VRESET", CFG.v_reset & 0xFFFF),
        ("CFG_LEAK", CFG.leak_shift),
        ("CFG_SYNSHIFT", CFG.syn_shift),
        ("CFG_REFR", CFG.refr_period),
        ("CFG_FLAGS", (1 if CFG.leak_en else 0) << 1),
        ("CFG_AXON", N_AXONS),
        ("PASS_TILE_OFF", 0),
    ]:
        L.append(f"#define NPUV_OFF_{name:<14} 0x{ADDR[name]:03X}u")
        L.append(f"#define NPUV_VAL_{name:<14} 0x{value:08X}u")
    L.append("")
    L.append(f"/* {len(words)} weight words, docs/10 section 5 packing, "
             "low half then high half */")
    L.append(f"#define NPUV_N_WWORDS {len(words)}")
    L.append("/* W_ADDR after loading the whole array. hw/rtl/pilot_top.v")
    L.append(" * deviation D3 makes W_ADDR a WORD INDEX sized exactly to the")
    L.append(" * array -- it counts 0 .. N_AXONS*N_NEURONS/16 - 1 -- so the")
    L.append(" * auto-increment on the last W_DATA_HI commit wraps it back to")
    L.append(" * zero. That is the specified behaviour and not an overflow. */")
    L.append(f"#define NPUV_WADDR_AFTER_LOAD {0}u")
    L.append(f"static const uint32_t npuv_wlo[{len(words)}] = {{")
    L.append("    " + ", ".join(f"0x{w & 0xFFFFFFFF:08X}u" for w in words))
    L.append("};")
    L.append(f"static const uint32_t npuv_whi[{len(words)}] = {{")
    L.append("    " + ", ".join(f"0x{(w >> 32) & 0xFFFFFFFF:08X}u"
                                for w in words))
    L.append("};")
    L.append("")
    L.append(f"#define NPUV_N_FRAMES {len(FRAMES)}")
    L.append(f"/* injected event words, {len(inject)} in all, "
             "grouped by npuv_inj_len */")
    L.append(f"#define NPUV_N_INJECT {len(inject)}")
    L.append(f"static const uint16_t npuv_inject[{len(inject)}] = {{")
    L.append("    " + ", ".join(f"0x{e:04X}u" for e in inject))
    L.append("};")
    L.append(f"static const uint8_t npuv_inj_len[{len(frame_len)}] = {{"
             + ", ".join(str(n) for n in frame_len) + "};")
    L.append("")
    L.append(f"/* THE ANSWER: {n_spikes} spikes and {len(FRAMES)} barrier "
             "echoes, in stream order (E8) */")
    L.append(f"#define NPUV_N_EXPECT {len(expect)}")
    L.append(f"static const uint16_t npuv_expect[{len(expect)}] = {{")
    L.append("    " + ", ".join(f"0x{e:04X}u" for e in expect))
    L.append("};")
    L.append(f"static const uint8_t npuv_exp_len[{len(expect_len)}] = {{"
             + ", ".join(str(n) for n in expect_len) + "};")
    L.append("")
    L.append("/* the whole neuron state file afterwards: N_DATA words, "
             "[15:0] V and [19:16] R */")
    L.append(f"static const uint32_t npuv_state[{N_NEURONS}] = {{")
    L.append("    " + ", ".join(f"0x{((r & 0xF) << 16) | (v & 0xFFFF):08X}u"
                                for v, r in state))
    L.append("};")
    L.append("")
    L.append("#endif /* NPU_VECTORS_H */")
    L.append("")

    out.write_text("\n".join(L))
    print(f"wrote {out} "
          f"({len(inject)} events in, {len(expect)} expected out, "
          f"{n_spikes} of them spikes)")


def emit_regs(out):
    """The node register map in C, from the same YAML the die's own
    header comes from."""
    L = ["/* GENERATED by hw/soc/flow/gen_npu_vectors.py from",
         " * regmap/regmap.yaml. Do not edit. This is the NODE register",
         " * map of docs/10 section 10 -- the same single source that",
         " * produces hw/rtl/npu_regs.vh and sw/golden/regmap_gen.py.",
         " */",
         "#ifndef NPU_REGS_H",
         "#define NPU_REGS_H",
         ""]
    for name in sorted(ADDR):
        L.append(f"#define NPU_{name:<16} 0x{ADDR[name]:03X}u")
    L.append("")
    for name in sorted(RESET):
        L.append(f"#define NPU_RST_{name:<12} 0x{RESET[name]:08X}u")
    L.append("")
    for reg in sorted(FIELDS):
        for f in sorted(FIELDS[reg]):
            L.append(f"#define NPU_BIT_{reg}_{f:<8} {FIELDS[reg][f]}u")
    L += ["", "#endif /* NPU_REGS_H */", ""]
    out.write_text("\n".join(L))
    print(f"wrote {out} ({len(ADDR)} node registers)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: gen_npu_vectors.py <out_dir>")
    d = Path(sys.argv[1])
    d.mkdir(parents=True, exist_ok=True)
    emit_regs(d / "npu_regs.h")
    emit(d / "npu_vectors.h")
