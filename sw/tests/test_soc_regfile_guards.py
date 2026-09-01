"""Does the register-file protection survive synthesis, and is the
substitution still a drop-in?

WHY THIS FILE EXISTS AND WHY IT IS SEPARATE

Two questions, neither of which anything else in this repository asks.

**1. The netlist.** `docs/41` section 9.4 is the sharpest statement of
why a census is not optional: all twenty formal tasks stayed green on a
design where the synthesiser had collapsed three banks into one, and the
only check that could see it counted flip-flops in the mapped netlist.
The same shape applies here in a different way. `hw/soc/formal/
regfile_secded.sby` proves the code, `hw/soc/tb/cocotb/
test_ibex_regfile_secded.py` injects into the storage, and the campaign
of `docs/43` section 8 runs the whole SoC -- and every one of them would
pass on a netlist in which the check flip-flops had been optimised away,
because they all read the RTL, where the flip-flops exist whatever the
netlist holds.

The specific risk is real rather than theoretical: `chk_q` is, in a
fault-free design, a pure function of `data_q`, both are written from
the same enable in the same cycle, and the scrub's write-back is
`encode(decode(stored))` -- which IS the identity on a clean codeword.
A synthesiser that proved either of those would delete the protection
and leave a register file that still passes every functional test.

**2. The interface.** The substitution in `hw/soc/flow/ibex_sources.sh`
works because `hw/soc/rtl/ibex_regfile_secded.v` declares upstream's
module name with upstream's port list. If upstream's port list moves,
that stops being true. A port added or removed fails at elaboration, so
the build catches it -- but only when the build is run, and only for
whoever runs it. These tests read the pristine sv2v output and compare,
so a `make fetch-ibex` at a newer commit turns the suite red with a
message that says which port moved.

WHAT THIS FILE DOES **NOT** COVER, stated because a green check is only
as wide as what it examined and `docs/41` section 6.6 lists nine times
this repository has been bitten by that:

  * It examines `ibex_register_file_ff` synthesised ON ITS OWN, at
    soc_top.v's parameters. `docs/43` section 7 measures it inside
    `ibex_top` as well and reports a larger number there; the two are
    different quantities and neither supersedes the other.
  * It counts FLIP-FLOPS and asserts nothing about the other cells.
    The XOR trees are functional logic, not redundancy, so a mapper that
    restructured them would be doing its job.
  * It says nothing about placement, routing or timing. No block under
    `hw/soc/` has been through any of them.
  * It says nothing about whether the code is CORRECT. Two hundred and
    seventeen check flip-flops holding the wrong function are two
    hundred and seventeen check flip-flops.
    `hw/soc/formal/regfile_secded.sby` is where the code is proved.
  * It compares the port LIST and not the port MEANING. A port whose
    semantics changed upstream without its name changing is invisible
    to this and to the build, and `docs/43` section 3 names it as an
    accepted risk.

Run with the repository-root suite::

    .venv/bin/python -m pytest sw/tests/test_soc_regfile_guards.py
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOC_RTL = ROOT / "hw" / "soc" / "rtl"
SOC_GEN = ROOT / "hw" / "soc" / "gen"
PILOT_RTL = ROOT / "hw" / "rtl"

TOP = "ibex_register_file_ff"
HARDENED = SOC_RTL / "ibex_regfile_secded.v"
UPSTREAM = SOC_GEN / (TOP + ".v")

CODEC = [PILOT_RTL / "secded_enc.v", PILOT_RTL / "secded_dec.v"]

# The geometry, derived rather than written down.
NUM_WORDS = 32
DATA_W = 32
DATA_FF = (NUM_WORDS - 1) * DATA_W          # 992: x1..x31, x0 has none
SCRUB_PTR_FF = 5                            # ceil(log2(32))

# The check field is EIGHT bits in the RTL and SEVEN in the netlist, and
# the difference is not a bug. The codec is (72,64); tying its upper 32
# data bits to zero shortens it, and H_ROW7's low half is
# 0x00000000 -- so over a 32-bit word that check bit is identically zero
# and the optimiser deletes one flip-flop per register. What remains is
# (39,32), which is the MINIMAL SECDED width for 32 data bits, arrived
# at by arithmetic and not by design.
#
# `test_the_eighth_check_bit_does_not_exist_over_32_data_bits` derives
# that from the matrix in the source rather than trusting this comment,
# and `hw/soc/formal/regfile_secded.sby` property C4 proves it.
CHK_W_NETLIST = 7
CHK_FF = (NUM_WORDS - 1) * CHK_W_NETLIST    # 217


def _find_yosys():
    on_path = shutil.which("yosys")
    if on_path:
        return on_path
    candidates = [Path.home() / ".local" / "bin" / "yosys"]
    candidates += sorted(
        Path.home().glob("Downloads/oss-cad-suite*/oss-cad-suite/bin/yosys"))
    candidates += sorted(Path.home().glob("oss-cad-suite/bin/yosys"))
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None


YOSYS = _find_yosys()
needs_yosys = pytest.mark.skipif(YOSYS is None, reason="yosys not available")
needs_gen = pytest.mark.skipif(
    not (SOC_GEN / (TOP + ".v")).is_file(),
    reason="hw/soc/gen is not populated: run hw/soc/flow/sv2v_ibex.sh")


def _sg13g2_liberty():
    pattern = (".ciel/ciel/ihp-sg13g2/versions/*/ihp-sg13g2/libs.ref/"
               "sg13g2_stdcell/lib/sg13g2_stdcell_typ_1p20V_25C.lib")
    libs = sorted(Path.home().glob(pattern))
    return libs[-1] if libs else None


_FF_PREFIXES = ("$_DFF", "$_SDFF", "$_ALDFF", "$_DFFE", "$_SDFFE", "$_DFFSR")


def _is_flop(cell_type):
    if cell_type.startswith(_FF_PREFIXES):
        return True
    if cell_type == "TRELLIS_FF":
        return True
    if re.match(r"^sg13g2_s?df", cell_type):
        return True
    return False


def _census(workdir, sources, chparam="", ecp5=False):
    """Flip-flops of one synthesis result, and their instance paths.

    The recipe is hw/soc/flow/syn_regfile.sh's, which is
    hw/soc/flow/syn_soc.sh's, which is syn_ibex.sh's."""
    lib = _sg13g2_liberty()
    out = Path(workdir) / "census.json"
    script = "read_verilog {};".format(
        " ".join(str(s) for s in sources))
    script += " hierarchy -top {};".format(TOP)
    script += (" chparam -set BaseIsa 0 -set RV32E 0 -set DataWidth 32"
               " -set DummyInstructions 0 {};".format(TOP))
    if chparam:
        script += " " + chparam
    if ecp5:
        script += " synth_ecp5 -top {};".format(TOP)
    else:
        script += " synth -top {} -flatten;".format(TOP)
        if lib is not None:
            script += " dfflibmap -liberty {0}; abc -liberty {0};".format(lib)
    script += " flatten; opt_clean; write_json {};".format(out)
    r = subprocess.run([YOSYS, "-p", script], capture_output=True, text=True,
                       cwd=workdir, timeout=1800)
    assert r.returncode == 0, ("yosys failed:\n" + r.stdout[-3000:]
                               + r.stderr[-3000:])
    design = json.loads(out.read_text())
    names = []
    for mod in design["modules"].values():
        for cell_name, cell in mod["cells"].items():
            if _is_flop(cell["type"]):
                names.append(cell_name)
    return names


@pytest.fixture(scope="module")
def workdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# =====================================================================
# 1. the netlist
# =====================================================================


@needs_yosys
def test_the_check_flip_flops_survive_synthesis(workdir):
    """The census, and the whole reason this file exists.

    Every functional test in this repository would pass on a netlist
    with the check field optimised away."""
    ff = _census(workdir, [HARDENED] + CODEC)
    assert len(ff) == DATA_FF + CHK_FF + SCRUB_PTR_FF, (
        "expected {} data + {} check + {} scrub pointer = {} flip-flops, "
        "got {}".format(DATA_FF, CHK_FF, SCRUB_PTR_FF,
                        DATA_FF + CHK_FF + SCRUB_PTR_FF, len(ff)))


@needs_yosys
def test_the_check_flip_flops_survive_a_second_technology_mapper(workdir):
    """Two mappers, because one mapper's behaviour is the tool and not
    the design. `sw/tests/test_soc_synthesis_guards.py` makes the same
    move for the watchdog's replicas."""
    ff = _census(workdir, [HARDENED] + CODEC, ecp5=True)
    assert len(ff) == DATA_FF + CHK_FF + SCRUB_PTR_FF, len(ff)


@needs_yosys
def test_harden_zero_removes_them_all(workdir):
    """The mutation, because a guard that cannot fail is not a guard.

    At HARDEN = 0 the file builds the plain register file and the check
    field does not exist. If the count above were being met by something
    other than the protection, this would still report the same number.
    """
    ff = _census(workdir, [HARDENED] + CODEC,
                 chparam="chparam -set HARDEN 0 {};".format(TOP))
    assert len(ff) == DATA_FF, (
        "HARDEN = 0 should leave exactly the {} architectural "
        "flip-flops, got {}".format(DATA_FF, len(ff)))


@needs_yosys
def test_scrub_zero_removes_the_pointer_and_nothing_else(workdir):
    """SCRUB = 0 keeps correction on read and drops the walking
    write-back, so what the scrub costs is separable from what the code
    costs. `docs/43` section 7 quotes both."""
    ff = _census(workdir, [HARDENED] + CODEC,
                 chparam="chparam -set SCRUB 0 {};".format(TOP))
    assert len(ff) == DATA_FF + CHK_FF, len(ff)


@needs_yosys
@needs_gen
def test_upstreams_own_file_measures_the_data_flip_flops_only(workdir):
    """The baseline, from upstream's file, measured with the same
    recipe in the same run.

    `docs/41` section 6.5 records what quoting a delta against a
    remembered number cost once. This is the number the delta in
    `docs/43` section 7 is taken against, produced here rather than
    recalled."""
    ff = _census(workdir, [SOC_GEN / (TOP + ".v")])
    assert len(ff) == DATA_FF, len(ff)


@needs_yosys
def test_the_bench_counters_still_cost_nothing_and_the_port_now_exists(workdir):
    """`docs/43`'s version of this test asserted that the correction
    report was deleted by `opt_clean`, and said in its own docstring
    that a future change giving it a port would fail here -- "and that
    failure would be the good news".

    `docs/44` is that change. The test is now in two halves:

      * The four INTERNAL counters still drive nothing and are still
        deleted. They are a bench instrument that
        `hw/soc/tb/tb_soc_fi.v` reads hierarchically, and `docs/43`'s
        campaign is reported off them, so they are kept -- and kept
        free.
      * `rf_ecc_err_o` EXISTS on the module. That is the operator
        channel, and the reason the first half is no longer the whole
        story."""
    ff = _census(workdir, [HARDENED] + CODEC)
    named = [n for n in ff if "sec_cycles" in n or "ded_cycles" in n
             or "sec_seen" in n or "ded_seen" in n]
    assert not named, (
        "the BENCH counters survive into the netlist; they drive "
        "nothing and should cost nothing: {}".format(named[:4]))
    assert "rf_ecc_err_o" in _ports(HARDENED.read_text(), TOP), (
        "the register file has no fault port, so a corrected upset is "
        "again indistinguishable from no upset (docs/43 section 10)")


@needs_yosys
def test_the_correction_masks_columns_are_folded_and_cost_no_cells(workdir):
    """`docs/44`'s fast correction derives the H columns by
    instantiating `secded_enc` on the thirty-two unit vectors, rather
    than writing the matrix into this project's file a second time --
    which is the duplication `docs/38` section 8.5 refused and
    `docs/43` section 6.1 promised not to commit.

    That is only free if the synthesiser folds all thirty-two of them.
    If a front end ever stopped folding them, the register file would
    grow thirty-two parity trees and nothing else would notice."""
    lib = _sg13g2_liberty()
    if lib is None:
        pytest.skip("sg13g2 liberty not present")
    cells = {}
    for tag, chparam in (("fast", "chparam -set FASTCORR 1 {};".format(TOP)),
                         ("slow", "chparam -set FASTCORR 0 {};".format(TOP))):
        out = Path(workdir) / ("fold_%s.json" % tag)
        script = "read_verilog {};".format(
            " ".join(str(x) for x in [HARDENED] + CODEC))
        script += " hierarchy -top {};".format(TOP)
        script += (" chparam -set BaseIsa 0 -set RV32E 0 -set DataWidth 32"
                   " -set DummyInstructions 0 {};".format(TOP))
        script += " " + chparam
        script += " synth -top {} -flatten;".format(TOP)
        script += " dfflibmap -liberty {0}; abc -liberty {0};".format(lib)
        script += " flatten; opt_clean; write_json {};".format(out)
        r = subprocess.run([YOSYS, "-p", script], capture_output=True,
                           text=True, cwd=workdir, timeout=1800)
        assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
        design = json.loads(out.read_text())
        cells[tag] = sum(len(m["cells"]) for m in design["modules"].values())
    # Thirty-two unfolded parity trees would be thousands of cells. The
    # bound is deliberately loose -- this is a check that the constants
    # FOLDED, not a re-measurement of the area, which
    # hw/soc/flow/syn_regfile.sh does exactly.
    assert cells["fast"] < cells["slow"] + 1500, (
        "the derived H columns did not fold to constants: FASTCORR = 1 "
        "is {} cells against FASTCORR = 0's {}".format(
            cells["fast"], cells["slow"]))


def test_the_eighth_check_bit_does_not_exist_over_32_data_bits():
    """Derived from the matrix in the source, not from this file.

    `hw/soc/rtl/ibex_regfile_secded.v` shortens the (72,64) code by
    tying the upper 32 data bits to zero. Whether that costs seven check
    flip-flops per register or eight depends on whether any row of H is
    empty over the low 32 columns -- and one is. The count above depends
    on it, so it is read out of `hw/rtl/secded_enc.v` here rather than
    trusted, and proved in `hw/soc/formal/regfile_secded.sby`."""
    text = (PILOT_RTL / "secded_enc.v").read_text()
    rows = re.findall(r"localparam \[63:0\] H_ROW(\d) = 64'h([0-9A-Fa-f]{16});",
                      text)
    assert len(rows) == 8, "expected eight H rows, found {}".format(len(rows))
    empty = [int(i) for i, v in rows if (int(v, 16) & 0xFFFFFFFF) == 0]
    assert empty == [7], (
        "the shortened code's check width is derived from which H rows "
        "are empty over the low 32 columns; expected exactly row 7, "
        "found {}".format(empty))
    assert 8 - len(empty) == CHK_W_NETLIST


# =====================================================================
# 2. the interface
# =====================================================================


def _ports(text, module):
    """The port name list of a non-ANSI Verilog module header.

    Line comments are stripped before the split. Upstream's sv2v output
    has none inside a port list; this project's substitute does, because
    the line where its own port begins is the line a reader most needs
    the reason on. A parser that split a comment containing a comma into
    two port names would fail with a message about a port that does not
    exist, which is how this was found.
    """
    m = re.search(r"\bmodule\s+" + module + r"\s*\((.*?)\);", text,
                  re.S)
    assert m, "no module {} header found".format(module)
    body = re.sub(r"//[^\n]*", "", m.group(1))
    return [p.strip() for p in body.split(",") if p.strip()]


@needs_gen
def test_the_substitute_declares_upstreams_ports_in_upstreams_order():
    """The whole substitution rests on this.

    `ibex_top` connects every port by name, so a port added or removed
    upstream fails at elaboration -- but only when somebody builds.
    Comparing the two headers turns that into a test failure with the
    name of the port that moved."""
    ours = _ports(HARDENED.read_text(), TOP)
    theirs = _ports((SOC_GEN / (TOP + ".v")).read_text(), TOP)
    # docs/44 WEAKENED this check from equality to "upstream's list is a
    # prefix", and that weakening is a cost rather than a tidy-up. The
    # substitute now declares one port upstream does not have --
    # `rf_ecc_err_o`, the fault line docs/43 section 10 said did not
    # exist -- so exact equality is no longer the right statement. What
    # is still checked, and is what the substitution actually rests on,
    # is that every upstream port is present, in upstream's order, at
    # the front; and that the ONLY additions are the ones named here, so
    # this cannot become a licence to append anything.
    OURS_OWN = ["rf_ecc_err_o"]
    assert ours[:len(theirs)] == theirs, (
        "the substituted register file's port list has diverged from "
        "the pinned Ibex.\n  ours:     {}\n  upstream: {}".format(
            ours, theirs))
    assert ours[len(theirs):] == OURS_OWN, (
        "the substitute has grown a port this test does not know "
        "about: {}".format(ours[len(theirs):]))


@needs_gen
def test_the_substitute_accepts_every_parameter_ibex_top_overrides():
    """`ibex_top` overrides five parameters by name. A substitute that
    did not declare one of them would fail to build; one that declared
    it with a different DEFAULT would build and be silently different in
    any flow that did not override it -- which is every standalone
    measurement in `docs/43` section 7."""
    ours = HARDENED.read_text()
    theirs = (SOC_GEN / (TOP + ".v")).read_text()
    for name in ("BaseIsa", "RV32E", "DataWidth", "DummyInstructions",
                 "WordZeroVal", "CapWidth", "CapWordZeroVal"):
        assert re.search(r"parameter[^;]*\b" + name + r"\b", ours), \
            "the substitute does not declare parameter {}".format(name)
        assert re.search(r"parameter[^;]*\b" + name + r"\b", theirs), \
            "upstream no longer declares parameter {}".format(name)


# docs/34-pilot-freeze.md section 2, the rows for the two codec files.
# The document prints the first twelve hex digits.
SECDED_PINNED_BLOBS = {
    "secded_enc.v": "b5710b8a679c",
    "secded_dec.v": "f7c7ec187a0d",
}


def test_the_codec_is_still_the_blob_the_pilot_freeze_pins():
    """The register file reads the codec out of `hw/rtl` in place, so the
    SoC's SECDED is the one `formal/secded.sby` proves and
    `hw/tb/test_secded.py` checks against `sw/golden/secded.py`.

    That is only true while the file is the file. This is the same check
    `sw/tests/test_soc_synthesis_guards.py` makes for `tmr_voter.v`, for
    the same two reasons: it says the TTIHP26b freeze still holds, and
    it says the SoC has not quietly forked the primitive."""
    for name, pinned in SECDED_PINNED_BLOBS.items():
        got = subprocess.run(["git", "hash-object", str(PILOT_RTL / name)],
                             capture_output=True, text=True, cwd=str(ROOT))
        assert got.returncode == 0, got.stderr
        assert got.stdout.strip().startswith(pinned), (
            "hw/rtl/{} is no longer the blob docs/34 section 2 pins: "
            "{} against {}".format(name, got.stdout.strip()[:12], pinned))


def test_the_codec_is_read_from_hw_rtl_and_not_copied():
    """`docs/38` section 8.5 declined SecureIbex partly because
    `RegFileLockstepECC` would put a second SECDED implementation on a
    die that already carries this project's own. Building register-file
    protection here does not undo that argument, and the way it does not
    is that there is still exactly one codec.

    A copy under `hw/soc/rtl/` would be the second one, so there must
    not be a copy."""
    strays = [p for p in SOC_RTL.glob("*.v")
              if "secded_enc" in p.name or "secded_dec" in p.name]
    assert not strays, (
        "a copy of the SECDED codec has appeared under hw/soc/rtl: "
        "{}".format([p.name for p in strays]))
    text = (ROOT / "hw" / "soc" / "flow" / "ibex_sources.sh").read_text()
    assert "rtl/secded_enc.v" in text and "rtl/secded_dec.v" in text, \
        "the build no longer reads the codec out of hw/rtl"


def test_exactly_one_register_file_reaches_any_build():
    """Two files declaring `ibex_register_file_ff` in one build is a
    redeclaration error in Icarus and a silent first-wins in some other
    front ends. The exclusion is done by construction in
    `ibex_sources.sh`; this is the check that it still is."""
    text = (ROOT / "hw" / "soc" / "flow" / "ibex_sources.sh").read_text()
    assert "ibex_register_file_ff.v" in text, \
        "ibex_sources.sh no longer names the file it excludes"
    assert "continue" in text, \
        "ibex_sources.sh no longer excludes anything"


def test_nothing_in_the_design_builds_the_register_file_unprotected():
    """HARDEN and SCRUB exist so the area can be measured against the
    same source file. Nothing in the design may set either to zero, and
    this is the textual check that nothing does -- the same one
    `sw/tests/test_soc_synthesis_guards.py` makes for the watchdog's
    HARDEN."""
    for path in list(SOC_RTL.glob("*.v")) + \
            list((ROOT / "hw" / "soc" / "flow").glob("*.sh")):
        text = path.read_text()
        for bad in (".HARDEN(0)", ".SCRUB(0)", ".FASTCORR(0)",
                    "ibex_register_file_ff.HARDEN=0",
                    "ibex_register_file_ff.SCRUB=0"):
            assert bad not in text, \
                "{} builds the register file unprotected".format(path.name)


def test_nothing_in_the_design_builds_the_measurement_configurations():
    """`SYNPRE` is not a feature. `docs/44` section 5.5 measures the
    syndrome tree hoisted past the read multiplexer -- 1.87 ns of the
    read path recovered for one parity tree per register -- and then
    declines it, because the SoC's 20 ns target is met with margin in
    both and eleven per cent of the core is the wrong thing to spend to
    widen a margin that is not binding.

    A parameter that ships disabled and is never measured again is the
    liability `docs/43` section 12 item 5 names. This is the check that
    it stays a measurement: the only thing allowed to set it is
    `hw/soc/flow/syn_regfile.sh`, which exists to measure it, and
    `hw/soc/flow/syn_ibex.sh`, which passes it through from an
    environment variable that defaults to 0."""
    allowed = {"syn_regfile.sh", "syn_ibex.sh"}
    for path in list(SOC_RTL.glob("*.v")) + \
            list((ROOT / "hw" / "soc" / "flow").glob("*.sh")):
        if path.name in allowed:
            continue
        text = path.read_text()
        assert "SYNPRE 1" not in text and ".SYNPRE(1)" not in text, \
            "{} builds the hoisted syndrome, which nothing ships".format(
                path.name)
    syn = (ROOT / "hw" / "soc" / "flow" / "syn_ibex.sh").read_text()
    assert "IBEX_RF_SYNPRE:-0" in syn, \
        "syn_ibex.sh no longer defaults the hoisted syndrome off"
