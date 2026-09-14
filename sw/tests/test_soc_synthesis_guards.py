# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Does the watchdog's W6 protection survive synthesis?

WHY THIS FILE EXISTS AND WHY IT IS SEPARATE

A synthesiser deletes deliberately redundant logic, and this repository
has been burned by exactly that twice. `hw/rtl/pilot_top.v` header
section 9 records the configuration TMR merging away entirely -- three
identical flip-flop banks written from the same expression are one bank
after `opt_dff` + `opt_merge`, and the voter above them then votes three
copies of the same corrupted value.
`docs/38-ibex-bringup.md` section 8.5 records the other shape: an
unguarded lockstep whose second core the optimiser removed, measured as
a 15,455 um2 gap between what the design asked for and what it got.

Every functional test in this repository would pass on a netlist with
one replica instead of three. `hw/soc/tb/cocotb/test_soc_wdog.py` would
pass. `hw/soc/formal/soc_wdog.sby` would pass -- it proves properties of
the RTL, and RTL is what it reads. Even the fault-injection campaign in
`hw/soc/tb/cocotb/test_soc_wdog_fi.py` would pass, because it deposits
into RTL registers that exist in the RTL whatever the netlist holds.
This file is the only check in the SoC tree that looks at the thing the
foundry would receive, and it is not a substitute for any of those, nor
they for it. `sw/tests/test_synthesis_guards.py` does the same job for
the frozen NPU pilot; nothing here touches `hw/rtl` except to read
`tmr_voter.v`, which the watchdog instantiates in place.

WHAT THIS FILE DOES **NOT** COVER, stated because a green check is only
as wide as what it examined and this repository has been bitten eight
times by that shape:

  * It examines `soc_wdog` synthesised on its own, with the default
    parameters of the file. `soc_top.v` instantiates it inside
    `soc_gptimer`; the guard on that composition is
    `test_the_watchdog_inside_the_gptimer_keeps_its_replicas`, which is
    the same census one level up. Section 5 goes one level further and
    checks that the whole SoC still ELABORATES as one design, which is
    what `docs/45-soc-top-synthesis.md` made possible; it does not
    census the replicas there, so the statement "no test in this file
    counts the watchdog's flip-flops inside a synthesised `soc_top`"
    is still true.
  * It counts FLIP-FLOPS and nothing else. It deliberately asserts
    nothing about the other cells in each replica: `docs/33` measured
    that `dfflibmap` erases the polarity coding at technology mapping,
    that this is harmless in this flow because no merge pass runs after
    mapping, and that a test which failed on it would be recording the
    tool rather than the design.
  * It says nothing about placement or routing. No SoC block has been
    through either. A merge that happened in an OpenROAD optimisation
    pass would be invisible here.
  * It says nothing about whether the replicas are CORRECT. Three banks
    that all store the wrong function are three banks.
    `hw/soc/formal/soc_wdog_tmr.sby` is where the round trip, the
    agreement and the masking are proved.
  * It says nothing about the unprotected state. `counter`, `reload` and
    `pre` are single points by decision, argued in `soc_wdog.v` W6 and
    priced in `docs/41-watchdog-hardening.md` section 7.

Run with the repository-root suite::

    .venv/bin/python -m pytest sw/tests/test_soc_synthesis_guards.py
"""

import importlib.util
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOC_RTL = ROOT / "hw" / "soc" / "rtl"
PILOT_RTL = ROOT / "hw" / "rtl"

TOP = "soc_wdog"

# The three files the watchdog elaborates from. tmr_voter.v is READ out
# of hw/rtl and never modified; docs/34-pilot-freeze.md pins it by git
# blob hash and test_the_voter_is_the_blob_the_pilot_freeze_pins checks
# that this is still the file that hash names.
SOURCES = [
    SOC_RTL / "soc_wdog.v",
    SOC_RTL / "soc_tmr_bank.v",
    PILOT_RTL / "tmr_voter.v",
]

# docs/34-pilot-freeze.md section 2, the row for hw/rtl/tmr_voter.v. The
# document prints the first twelve hex digits.
TMR_VOTER_PINNED_BLOB = "e52580002bf6"
# Superseded 2026-09-09 by the licence headers, docs/34 section 9.3:
TMR_VOTER_SUPERSEDED_BLOB = "62b5f4d2a1ea"


# =====================================================================
# the geometry, DERIVED from the RTL rather than written down here
# =====================================================================
def _int_param(text, name):
    m = re.search(r"parameter\s+integer\s+" + name + r"\s*=\s*(\d+)", text)
    assert m, "no integer parameter {} in soc_wdog.v".format(name)
    return int(m.group(1))


def _geometry():
    """Flip-flop budget of soc_wdog at its own default parameters.

    Recomputed from the parameter declarations and the field widths in
    the source, so a width change moves the expected count with it
    instead of turning this file red for the wrong reason. The FIELD
    LIST is written out here on purpose: it is the specification of what
    W6 protects, and if a field is added to the protected word without a
    line appearing here the counts stop agreeing.
    """
    text = (SOC_RTL / "soc_wdog.v").read_text()
    width = _int_param(text, "WIDTH")
    prescale = _int_param(text, "PRESCALE")
    rst_cycles = _int_param(text, "RST_CYCLES")

    pre_w = 1 if prescale <= 1 else math.ceil(math.log2(prescale))
    rst_w = 1 if rst_cycles <= 1 else math.ceil(math.log2(rst_cycles + 1))
    cnt_w = 8   # saturating reset counter
    tmc_w = 4   # saturating TMR mismatch counter

    # The protected word, W6: everything whose corruption is permanent
    # or silent.
    kick_w = 8  # W8's kick-budget down-counter
    prot_w = (1     # dis_q
              + 1   # dis_seen
              + 1   # nmi_pend
              + 1   # rst_seen
              + 1   # tmr_err
              + tmc_w
              + cnt_w
              + rst_w
              # docs/43, W7 and W8. Four more fields in the same word,
              # by the same criterion: software writes them once per
              # phase, nothing else rewrites them, and their corruption
              # toward zero is silent.
              + 4   # win_s
              + 1   # early_seen
              + 1   # bud_arm
              + 1)  # bud_seen

    # The W6 report: the sticky mismatch flag and the saturating
    # mismatch counter. Counted separately because it is the part of
    # the protected word that only EXISTS when there is redundancy to
    # report on -- at HARDEN = 0 the mismatch wire is a constant zero
    # and the optimiser correctly deletes these five flip-flops.
    report = 1 + tmc_w

    # The strap synchroniser and its hold-off, W1. Two flip-flops of
    # two-stage synchroniser on `dis_i` plus a two-bit saturating
    # `dis_arm`, all in the power-on domain and all outside the
    # protected word on purpose: a synchroniser that is voted is not a
    # synchroniser, and the hold-off counter is dead two clocks after
    # reset release, so its corruption changes nothing that is still
    # being read. `soc_wdog.v` says both in place.
    strap_sync = 2 + 2  # dis_sync0, dis_sync1, dis_arm[1:0]

    # Deliberately unprotected, W6's second list plus W8's down-counter
    # and W1's synchroniser.
    unprot = width + width + pre_w + kick_w + strap_sync
    # reload, counter, pre, kick_left, dis_sync0/1, dis_arm

    # W9's `in_reset_q`, docs/75. It is counted apart from `unprot`
    # because it is not unprotected by the same argument: `reload`,
    # `counter`, `pre` and `kick_left` are left alone because the block
    # rewrites them, and this one is left alone because it CANNOT be
    # replicated -- one bit has two storage functions and three replicas
    # need three (hw/rtl/pilot_top.v section 8.2) -- and because putting
    # it in the protected word would put it back behind the very decode
    # W9 exists to get the reset out from behind. It exists at HARDEN =
    # 0 as well: it is outside the `g_prot_tmr` generate.
    rstreq = 1

    return prot_w, report, unprot, rstreq


PROT_W, REPORT_FF, UNPROT_FF, RSTREQ_FF = _geometry()

REPLICAS = ("g_prot_tmr.u_prot_a.",
            "g_prot_tmr.u_prot_b.",
            "g_prot_tmr.u_prot_c.")


# =====================================================================
# tool discovery -- the same rule sw/tests/test_synthesis_guards.py uses
# =====================================================================
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


def _sg13g2_liberty():
    pattern = (".ciel/ciel/ihp-sg13g2/versions/*/ihp-sg13g2/libs.ref/"
               "sg13g2_stdcell/lib/sg13g2_stdcell_typ_1p20V_25C.lib")
    libs = sorted(Path.home().glob(pattern))
    return libs[-1] if libs else None


def _run_yosys(script, workdir):
    result = subprocess.run(
        [YOSYS, "-p", script], capture_output=True, text=True,
        cwd=workdir, timeout=900)
    assert result.returncode == 0, (
        "yosys failed:\n" + result.stdout[-3000:] + result.stderr[-3000:])
    return result.stdout


# =====================================================================
# netlist census -- flip-flops indexed by the public net they drive
# =====================================================================
_FF_PREFIXES = ("$_DFF", "$_SDFF", "$_ALDFF", "$_DFFE", "$_SDFFE", "$_DFFSR")


def _is_flop(cell_type):
    if cell_type.startswith(_FF_PREFIXES):
        return True
    if cell_type == "TRELLIS_FF":                # synth_ecp5
        return True
    if re.match(r"^sg13g2_s?df", cell_type):     # sg13g2 mapped
        return True
    return False


class Census:
    """Flip-flops of one synthesis result, indexed by INSTANCE PATH.

    The instance path is what identifies a replica bank after a
    post-mapping flatten -- yosys renames a flattened cell
    `$flatten\\<hierarchical.path>.<cell>` and that prefix is the only
    thing in the netlist that still says which replica a flip-flop
    belongs to.

    Indexing by the net a flip-flop drives does NOT work here and the
    reason is worth recording, because it produced a plausible wrong
    answer first. Replica A's stored word and its output port are the
    same net (POL_A is zero and MIX is off, so `q_o = bits`), and in
    replicas B and C the bits where POL is zero alias with the encoder
    output. yosys names a flip-flop after whichever aliased public net
    it resolves first, so a by-net census reported 0, 11 and 11 for the
    three replicas of a netlist that in fact holds 22, 22 and 22.
    """

    def __init__(self, design):
        self.total = 0
        # EVERY cell, not only the flip-flops. docs/56 H5's whole
        # mechanism is combinational -- it costs no state at all -- so
        # a flip-flop census is blind to whether it is in the netlist,
        # and `cells` is what its mutation guard compares.
        self.cells = 0
        self.by_instance = []
        self.by_src = []
        for mod in design["modules"].values():
            for cell_name, cell in mod["cells"].items():
                self.cells += 1
                if not _is_flop(cell["type"]):
                    continue
                self.total += 1
                self.by_instance.append(cell_name)
                # The `src` attribute survives the post-mapping flatten
                # that erases the instance path, and it is the only thing
                # left in the netlist that says which FILE a flip-flop
                # came from. docs/55 uses it to tie the campaign's site
                # list to the netlist, which nothing had done before:
                # every other check in this file counts flip-flops
                # without asking whether they are the ones the campaign
                # believes it is injecting into.
                self.by_src.append(str(cell.get("attributes", {})
                                       .get("src", "")))

    def in_instance(self, needle):
        return sum(1 for n in self.by_instance if needle in n)

    def from_file(self, needle):
        return sum(1 for s in self.by_src if needle in s)


def _census(script_body, workdir):
    out = Path(workdir) / "census.json"
    _run_yosys(script_body + " write_json {};".format(out), workdir)
    return Census(json.loads(out.read_text()))


def _strobe_cone(script_body, workdir, tag):
    """The flip-flops the die's AER strobe pin depends on, by name.

    docs/56 H5 gates `aer_in_stb` with `ev_state == E_PIN_S`, so a
    netlist that carries the gate has the event engine's state register
    in this cone and one that does not carries only the strobe flag.
    That is the whole of H5 stated as a structure rather than as a size,
    and docs/76 section 9.2 is why the size no longer works.
    """
    out = Path(workdir) / ("cone_%s.json" % tag)
    _run_yosys(script_body + " write_json {};".format(out), workdir)
    gl = _gl()
    nl = gl.JsonNetlist(str(out))
    bits = nl.net("obs_aer_in_stb_o")
    assert len(bits) == 1, (
        "obs_aer_in_stb_o is {} bits in the netlist, not 1".format(len(bits)))
    insts = gl.cone_flops(nl.driver, nl.cells, bits[0])
    return {nl.q_name(i) or i for i in insts}


# =====================================================================
# the SECOND instrument: the voter's fan-in cone
# =====================================================================
#
# docs/75. `Census.in_instance` above counts a replica by the INSTANCE
# PATH yosys bakes into a flattened cell name. That is exact in this
# file's recipes -- `flatten` runs after `dfflibmap`, so the flip-flop
# dfflibmap builds behind an inverter for a reset-to-one bit is created
# inside the bank module and is prefixed like every other -- and it was
# right every time it has been quoted (docs/41, docs/55, docs/56,
# docs/69, and docs/75 section 3 re-measures all of them). It has one
# blind spot and it is not small: **the instance path does not survive
# the netlist LibreLane writes**. In `hw/soc/pnr/runs/*/final/nl/
# soc_top.nl.v` every cell is `_00268_` and the only thing that says
# which replica a flip-flop belongs to is what it drives.
#
# So this file gets a second instrument, and it is the SAME code the
# gate-level campaign of docs/74 uses on the shipped netlist --
# `hw/soc/fi/gl_netlist.py`, imported rather than reimplemented, for
# the reason test_the_verdict_rule_is_one_file_and_not_two_copies_of_one
# gives about the STA verdict. It walks back from the net the voter
# reads and reports the flip-flops it finds, which depends on no name
# and no instance path.
#
# It is not a replacement for the count. It answers a question the
# count cannot: a count of three says three banks of the right SIZE
# exist, and says nothing about whether they are three DIFFERENT banks.
# A voter wired to one replica twice passes every count in this file
# and is exactly the failure the protection exists to prevent. The
# disjointness assertion below is the one that catches it, and
# test_a_voter_wired_to_one_replica_twice_is_caught_only_by_the_cone
# is the mutation that proves the pair is not decoration.
_GL_NETLIST = ROOT / "hw" / "soc" / "fi" / "gl_netlist.py"


def _gl():
    spec = importlib.util.spec_from_file_location("gl_netlist", _GL_NETLIST)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cones(script_body, workdir, structure, tag="cone"):
    """The three replica banks of one structure, by fan-in cone.

    Returns (sets, rows): the flip-flop instance sets in voter order,
    and gl_netlist's own rows, which carry the net each cone started
    from and the width it turned out to have. A caller MUST check the
    width: a cone of zero over a net that is not in the netlist is a
    census that failed, not a replica that merged, and reading one as
    the other is the shape docs/40 section 11 records."""
    out = Path(workdir) / ("cone_%s.json" % tag)
    _run_yosys(script_body + " write_json {};".format(out), workdir)
    rows = _gl().tmr_census_named(str(out), structure)
    return [set(r["cone_insts"]) for r in rows], rows


def _assert_three_disjoint_cones(sets, rows, width, what):
    names = [r["bank"] for r in rows]
    for r in rows:
        assert r["width"] == width, (
            "the cone census of {} could not find replica {}: it looked "
            "for the net the voter reads and found {} bits, not {}. That "
            "is a census that failed, and it must NOT be read as a "
            "replica that merged -- the net it anchors on is {}."
            .format(what, r["bank"], r["width"], width, r["net"]))
        assert r["cone"] == width, (
            "replica {} of {} has {} flip-flops in the fan-in cone of "
            "the net the voter reads, not {}.".format(
                r["bank"], what, r["cone"], width))
    for i in range(3):
        for j in range(i + 1, 3):
            shared = sets[i] & sets[j]
            assert not shared, (
                "replicas {} and {} of {} SHARE {} flip-flops. Three "
                "banks of the right size are not three banks if the "
                "voter is reading the same storage twice: the vote is "
                "then a majority over two distinct values and a single "
                "upset in the shared bank is not masked. This is what "
                "hw/rtl/pilot_top.v section 9 records happening to the "
                "pilot, and a per-replica flip-flop COUNT cannot see "
                "it.".format(names[i], names[j], what, len(shared)))
    union = set().union(*sets)
    assert len(union) == 3 * width, (
        "{}: three cones of {} over {} distinct flip-flops, expected {}"
        .format(what, width, len(union), 3 * width))


# ---------------------------------------------------------------------
# the recipes
# ---------------------------------------------------------------------
def _read(sources):
    return "read_verilog -I {} {};".format(
        SOC_RTL, " ".join(str(s) for s in sources))


def _asic_script(sources, force_flatten=False, chparam=""):
    """The recipe hw/soc/flow/syn_soc.sh runs, in the shape
    sw/tests/test_synthesis_guards.py states it.

    The trailing `attrmap -modattr -remove keep_hierarchy; flatten` is
    LibreLane's SYNTH_HIERARCHY_MODE = deferred flatten: flatten after
    mapping, so nothing it produces can be merged.

    force_flatten strips keep_hierarchy BEFORE synthesis, which
    simulates a front end that does not read yosys attributes. What is
    then holding the three replicas apart is the POL/MIX storage
    transform alone.
    """
    lib = _sg13g2_liberty()
    script = _read(sources) + " hierarchy -top {};".format(TOP)
    if chparam:
        script += " " + chparam
    if force_flatten:
        script += " attrmap -modattr -remove keep_hierarchy;"
    script += " synth -top {} -flatten;".format(TOP)
    if lib is not None:
        script += " dfflibmap -liberty {0}; abc -liberty {0};".format(lib)
    script += " attrmap -modattr -remove keep_hierarchy; flatten; opt_clean;"
    return script


def _ecp5_script(sources, force_flatten=False):
    script = _read(sources) + " hierarchy -top {};".format(TOP)
    if force_flatten:
        script += " attrmap -modattr -remove keep_hierarchy;"
    return script + (
        " synth_ecp5 -top {};".format(TOP)
        + " attrmap -modattr -remove keep_hierarchy; flatten; opt_clean;")


@pytest.fixture(scope="module")
def workdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture(scope="module")
def asic(workdir):
    return _census(_asic_script(SOURCES), workdir)


@pytest.fixture(scope="module")
def ecp5(workdir):
    return _census(_ecp5_script(SOURCES), workdir)


# ---------------------------------------------------------------------
# a copy of the sources with every yosys attribute deleted from the TEXT
# ---------------------------------------------------------------------
_ATTRS = ("(* keep_hierarchy *)", "(* keep *)")


def _sources_without_any_attribute(workdir):
    """Delete the attributes rather than strip them with `attrmap`.

    `attrmap` removes what it is told to remove at the point it runs;
    deleting the text means no pass can honour the attribute and none
    can re-derive it. What is left holding the replicas apart is the
    POL/MIX transform and nothing else, which is the claim
    `hw/soc/rtl/soc_tmr_bank.v` makes and the only one this file can
    check without a second flow.
    """
    dst = Path(workdir) / "noattr"
    dst.mkdir(exist_ok=True)
    out = []
    for src in SOURCES:
        text = src.read_text()
        for attr in _ATTRS:
            text = text.replace(attr, "")
        target = dst / src.name
        target.write_text(text)
        out.append(target)
    # The include search path still points at the real hw/soc/rtl, and
    # nothing in these three files includes anything, so no attribute
    # can sneak back in through a header.
    return out


@pytest.fixture(scope="module")
def asic_noattr(workdir):
    return _census(
        _asic_script(_sources_without_any_attribute(workdir),
                     force_flatten=True),
        workdir)


@pytest.fixture(scope="module")
def ecp5_noattr(workdir):
    return _census(
        _ecp5_script(_sources_without_any_attribute(workdir),
                     force_flatten=True),
        workdir)


# =====================================================================
# 1. the protected word is three physical banks
# =====================================================================
def _assert_three_replicas(census, flow):
    found = {r: census.in_instance(r) for r in REPLICAS}
    assert all(v == PROT_W for v in found.values()), (
        "the watchdog's protected word collapsed in the {} netlist: "
        "expected {} flip-flops per replica, found {}. Three replicas "
        "written from the same expression are one bank after opt_dff + "
        "opt_merge, and the voter above them then votes three copies of "
        "the same upset value -- which is what hw/rtl/pilot_top.v "
        "section 9 records happening to the pilot's configuration TMR. "
        "Total flip-flops in this netlist: {}.".format(
            flow, PROT_W, found, census.total))


@needs_yosys
def test_the_protected_word_is_three_banks_in_the_asic_flow(asic):
    _assert_three_replicas(asic, "ASIC (yosys/LibreLane-shaped)")


@needs_yosys
def test_the_protected_word_is_three_banks_in_the_ecp5_flow(ecp5):
    _assert_three_replicas(ecp5, "synth_ecp5")


# =====================================================================
# 1b. and three DIFFERENT banks, by the voter's fan-in cone
# =====================================================================
@needs_yosys
def test_the_watchdogs_three_replicas_are_three_disjoint_cones(workdir):
    """docs/75 section 4. The census above and this one on one netlist.

    The pair is the point. The count says each replica is PROT_W
    flip-flops; the cone says the three sets of PROT_W flip-flops the
    voter actually reads are disjoint. Neither implies the other, and
    the mutation below is a design that passes the first and fails the
    second."""
    sets, rows = _cones(_asic_script(SOURCES), workdir, "wdog_block", "wdog")
    _assert_three_disjoint_cones(sets, rows, PROT_W, "the watchdog's "
                                 "protected word")


@needs_yosys
def test_the_boot_words_three_replicas_are_three_disjoint_cones(workdir):
    sets, rows = _cones(_boot_script(BOOT_SOURCES), workdir,
                        "boot_block", "boot")
    _assert_three_disjoint_cones(sets, rows, BOOT_PROT_W,
                                 "the boot block's decision word")


@needs_yosys
def test_the_npu_cause_banks_three_replicas_are_three_disjoint_cones(workdir):
    sets, rows = _cones(_npu_script(NPU_SOURCES), workdir, "npu_block", "npu")
    _assert_three_disjoint_cones(sets, rows, NPU_PROT_W,
                                 "the NPU cause bank")


@needs_yosys
def test_the_two_instruments_agree_on_every_replica_of_every_structure(
        asic, boot_asic, npu_asic, workdir):
    """The count and the cone, side by side, on all nine replicas.

    This is the check docs/75 section 3 is: the published counts of
    docs/41, docs/55, docs/56 and docs/69 were all taken with
    `in_instance`, and the question that document had to answer was
    whether an instrument that undercounts on the shipped netlist had
    been undercounting here too. It had not, and this is the assertion
    that keeps it that way rather than a sentence in a document.
    """
    for tag, script, sources, structure, replicas, width, census in (
            ("wdog", _asic_script, SOURCES, "wdog_block", REPLICAS,
             PROT_W, asic),
            ("boot", _boot_script, BOOT_SOURCES, "boot_block",
             BOOT_REPLICAS, BOOT_PROT_W, boot_asic),
            ("npu", _npu_script, NPU_SOURCES, "npu_block", NPU_REPLICAS,
             NPU_PROT_W, npu_asic)):
        _, rows = _cones(script(sources), workdir, structure, tag + "2")
        for r, replica in zip(rows, replicas):
            assert r["cone"] == census.in_instance(replica) == width, (
                "{} {}: the cone census says {} flip-flops and the "
                "instance-path census says {}; both should say {}. A "
                "disagreement here is a finding either way -- it means "
                "one of the two instruments is reading storage the "
                "other is not."
                .format(tag, r["bank"], r["cone"],
                        census.in_instance(replica), width))


@needs_yosys
def test_a_voter_wired_to_one_replica_twice_is_caught_only_by_the_cone(
        workdir):
    """The mutation that says the cone census is not decoration.

    `.in_b(qa)` on the voter is a design with three intact banks whose
    vote is a majority over TWO distinct values, so an upset in replica
    A is not masked -- which is the whole failure W6 exists to prevent.
    `(* keep *)` on `soc_tmr_bank`'s storage keeps replica B's
    flip-flops in the netlist even though nothing reads them, so:

      * the per-replica count is still PROT_W, PROT_W, PROT_W;
      * the total flip-flop budget is unchanged;
      * every functional test, every proof in hw/soc/formal and every
        RTL fault-injection campaign in this repository still passes,
        because they all read `soc_wdog.v` as it is committed and this
        mutation is only ever made in a scratch copy;

    and the cone census reports replicas A and B sharing all PROT_W of
    their flip-flops. It is the docs/33 shape one more time: the
    evidence has to be about the thing that was broken."""
    sources = _mutated(workdir, "vote_ab",
                       [(".in_b     (qb),", ".in_b     (qa),")])
    census = _census(_asic_script(sources), workdir)

    # First: the guards that were there before docs/75 all pass on it.
    for r in REPLICAS:
        assert census.in_instance(r) == PROT_W, (
            "the mutation was supposed to leave three banks of {} "
            "standing and did not; it no longer demonstrates what it "
            "was written to demonstrate".format(PROT_W))
    assert census.total == UNPROT_FF + RSTREQ_FF + 3 * PROT_W

    # And the cone census does not.
    sets, rows = _cones(_asic_script(sources), workdir, "wdog_block", "vote")
    with pytest.raises(AssertionError) as caught:
        _assert_three_disjoint_cones(sets, rows, PROT_W, "the mutant")
    assert "SHARE" in str(caught.value), str(caught.value)
    assert len(sets[0] & sets[1]) == PROT_W, (
        "the mutant's voter should read replica A on two of its three "
        "inputs, so those two cones should be the same {} flip-flops; "
        "the cone census found {} shared"
        .format(PROT_W, len(sets[0] & sets[1])))


@needs_yosys
def test_no_flip_flop_is_lost_when_every_attribute_is_deleted_asic(
        asic_noattr):
    """The POL/MIX transform on its own, in a flow that cannot read a
    yosys attribute even if it wanted to.

    This is a TOTAL and not a per-replica census, and that is forced
    rather than chosen: with keep_hierarchy deleted the banks are
    flattened during `synth` and the instance path they would have been
    counted by no longer exists. The total is the thing that matters
    anyway -- a replica that merged is a replica whose flip-flops are
    gone -- and it is strictly wider, because it would also catch
    storage lost anywhere else in the block. It is the same assertion
    `sw/tests/test_synthesis_guards.py` makes for the pilot under the
    name test_no_flip_flop_is_lost_when_every_attribute_is_deleted.
    """
    expected = UNPROT_FF + RSTREQ_FF + 3 * PROT_W
    assert asic_noattr.total == expected, (
        "with every keep and keep_hierarchy deleted from the text, "
        "soc_wdog mapped to {} flip-flops instead of {}. Something in "
        "this block is being held together by an attribute alone, and "
        "an attribute is not portable to a front end that does not read "
        "yosys's.".format(asic_noattr.total, expected))


@needs_yosys
def test_no_flip_flop_is_lost_when_every_attribute_is_deleted_ecp5(
        ecp5_noattr):
    """The same question of a completely different technology mapper,
    because a defence that is really a property of one recipe is not a
    defence. docs/18 makes the cross-flow argument at length."""
    assert ecp5_noattr.total == UNPROT_FF + RSTREQ_FF + 3 * PROT_W


# =====================================================================
# 2. the whole flip-flop budget, so nothing else quietly vanished either
# =====================================================================
@needs_yosys
def test_the_flip_flop_budget_is_the_unprotected_state_plus_three_replicas(
        asic):
    """A per-replica census can pass while the block loses storage
    somewhere else. This asserts the total against the two numbers W6
    is a decision about: what is protected, three times, plus what is
    deliberately not."""
    expected = UNPROT_FF + RSTREQ_FF + 3 * PROT_W
    assert asic.total == expected, (
        "soc_wdog mapped to {} flip-flops, expected {} = {} unprotected "
        "(reload + counter + pre + kick_left) + {} for W9's registered "
        "reset request + 3 x {} protected. If the protected word grew "
        "or shrank, _geometry() in this file has to grow or shrink with "
        "it -- that is the point of it being derived.".format(
            asic.total, expected, UNPROT_FF, RSTREQ_FF, PROT_W))


# =====================================================================
# 3. the mutations. A guard that cannot fail is not a guard.
# =====================================================================
def _mutated(workdir, name, replacements, strip_attributes=False):
    """A scratch copy of the sources with one edit, so the mutation is
    never made in the tree."""
    dst = Path(workdir) / name
    dst.mkdir(exist_ok=True)
    out = []
    hit = 0
    for src in SOURCES:
        text = src.read_text()
        for old, new in replacements:
            if old in text:
                hit += text.count(old)
                text = text.replace(old, new)
        if strip_attributes:
            for attr in _ATTRS:
                text = text.replace(attr, "")
        target = dst / src.name
        target.write_text(text)
        out.append(target)
    assert hit, "mutation {} matched nothing; the source moved".format(name)
    return out


@needs_yosys
def test_removing_the_mix_transform_from_one_replica_collapses_half_of_it(
        workdir):
    """The replication bound, measured rather than argued.

    With MIX off, a replica stores `v_i ^ POL[i]` -- one of the only two
    storage functions a single bit has. POL_A is zero and POL_C is
    0xAAAA..., so on every bit where POL_C is 0 replica C stores exactly
    what replica A stores and structural hashing merges the pair. The
    surviving flip-flop count therefore drops by the number of zero bits
    in POL_C over the protected width, which is what makes this mutation
    a measurement of the bound and not just a red test.

    Neither this mutation nor its inverse is visible to any simulation
    or any proof in this repository: `.MIX(0)` on a replica is
    functionally identical RTL, bit for bit at every port.
    """
    intact = UNPROT_FF + RSTREQ_FF + 3 * PROT_W
    # POL_C = 0xAAAA...: bit i is 1 for odd i, so the bits on which
    # replica C would store exactly what replica A stores are the even
    # ones.
    collided = len([i for i in range(PROT_W) if not ((0xAAAA_AAAA >> i) & 1)])

    sources = _mutated(
        workdir, "nomix_c",
        [(".POL(POL_C), .MIX(1))", ".POL(POL_C), .MIX(0))")],
        strip_attributes=True)
    census = _census(_asic_script(sources, force_flatten=True), workdir)
    assert census.total == intact - collided, (
        "with MIX off on replica C, {} of its {} bits should collide "
        "with replica A and be merged away, giving {} flip-flops; found "
        "{}".format(collided, PROT_W, intact - collided, census.total))

    # And with the mixing off on BOTH mixed replicas exactly ONE
    # FLIP-FLOP PER PROTECTED BIT is lost, which is the pigeonhole
    # stated as a measurement: polarity offers exactly two storage
    # functions per bit and there are three replicas, so on every bit
    # one of the three has to collide. On the bits where POL_C is zero
    # replica C collides with A; on the others it collides with B.
    #
    # This used to be written as `2 * collided` and it was wrong in a
    # way that could only show up when the width changed. At PROT_W =
    # 22 the two expressions are equal, because POL_C is zero on
    # exactly half of an even number of bits. docs/43 widened the
    # protected word to 29 for W7 and W8, and 2 * 15 is 30 where the
    # answer is 29. The design was right and the arithmetic was wrong,
    # and the comment above it had said the right thing all along.
    both = _mutated(
        workdir, "nomix_bc",
        [(".POL(POL_B), .MIX(1))", ".POL(POL_B), .MIX(0))"),
         (".POL(POL_C), .MIX(1))", ".POL(POL_C), .MIX(0))")],
        strip_attributes=True)
    census2 = _census(_asic_script(both, force_flatten=True), workdir)
    assert census2.total == intact - PROT_W, (
        "with MIX off on both mixed replicas exactly one flip-flop per "
        "protected bit should be merged away, giving {}; found {}"
        .format(intact - PROT_W, census2.total))


@needs_yosys
def test_harden_zero_removes_the_replicas(workdir):
    """The mutation that proves this file is measuring the protection
    at all, rather than counting flip-flops that were going to be there
    anyway. HARDEN = 0 is also the configuration the area cost in
    docs/41 section 6 is measured against."""
    census = _census(
        _asic_script(SOURCES, chparam="chparam -set HARDEN 0 {};".format(TOP)),
        workdir)
    expected = UNPROT_FF + RSTREQ_FF + PROT_W - REPORT_FF
    assert census.total == expected, (
        "HARDEN = 0 should leave one plain bank: {} unprotected + {} "
        "for W9's registered reset request + {} protected - {} report "
        "(the mismatch flag and counter have nothing to report on and "
        "are correctly optimised away) = {} flip-flops, found {}".format(
            UNPROT_FF, RSTREQ_FF, PROT_W, REPORT_FF, expected,
            census.total))
    for r in REPLICAS:
        assert census.in_instance(r) == 0


# =====================================================================
# 3b. the fault counters, docs/44
# =====================================================================
#
# soc_busstat has no redundancy for a synthesiser to collapse, so this
# is not the docs/41 section 9.4 question in its usual form. It is the
# same question in another one: FOUR SATURATING COUNTERS THAT NOTHING
# ELSE IN THE DESIGN READS. Every functional test drives the event
# lines by hand and reads the registers back, and every one of them
# would pass on a netlist in which a counter had been reduced to its
# sticky bit -- because the RTL still has the flip-flops whatever the
# netlist holds. The count here is arithmetic on the block's own
# parameters, so widening CNT_W moves the expectation with it.
BUSSTAT = SOC_RTL / "soc_busstat.v"


def _busstat_cnt_w():
    """CNT_W read out of the module header, not written down here."""
    m = re.search(r"parameter\s+integer\s+CNT_W\s*=\s*(\d+)",
                  BUSSTAT.read_text())
    assert m, "soc_busstat.v no longer declares CNT_W"
    return int(m.group(1))


def _busstat_nsrc():
    """NSRC, likewise DERIVED.

    It was written down here as 4 until docs/55 added three sources, and
    a literal would have made this test fail for the right reason with
    the wrong message -- or, worse, have been edited to 7 without anyone
    asking whether the three new counters had actually survived. The
    arithmetic below is what says they did.
    """
    m = re.search(r"localparam\s+integer\s+NSRC\s*=\s*(\d+)",
                  BUSSTAT.read_text())
    assert m, "soc_busstat.v no longer declares NSRC"
    return int(m.group(1))


BUSSTAT_NSRC = _busstat_nsrc()


@needs_yosys
def test_the_fault_counters_survive_synthesis(workdir):
    """docs/44 section 6. An operator's only view of a corrected upset
    is these flip-flops; a mapper that deleted one would leave a block
    that still answers every APB read with a plausible number."""
    cnt_w = _busstat_cnt_w()
    script = ("read_verilog -I {} {};".format(SOC_RTL, BUSSTAT)
              + " hierarchy -top soc_busstat;"
                " synth -top soc_busstat -flatten;")
    lib = _sg13g2_liberty()
    if lib is not None:
        script += " dfflibmap -liberty {0}; abc -liberty {0};".format(lib)
    script += " flatten; opt_clean;"
    census = _census(script, workdir)
    expected = BUSSTAT_NSRC * cnt_w + BUSSTAT_NSRC + BUSSTAT_NSRC
    assert census.total == expected, (
        "expected {} counters x {} bits + {} sticky + {} enable = {} "
        "flip-flops, found {}".format(
            BUSSTAT_NSRC, cnt_w, BUSSTAT_NSRC, BUSSTAT_NSRC,
            expected, census.total))


def test_the_fault_lines_are_connected_in_soc_top():
    """The failure this whole block exists to prevent, in its purest
    form. `pilot_top.v` records it: four ECC status wires left
    unconnected, so the codes corrected and nothing on the chip said so,
    and a campaign measured 84 corrections and had to classify every one
    MASKED -- with every proof and every test green.

    soc_busstat's own suite drives its inputs by hand, so it would pass
    on a soc_top that wired them to zero. This is the check that they
    come from somewhere."""
    top = (SOC_RTL / "soc_top.v").read_text()
    for pat in (".rf_ecc_err_o           (rf_ecc_err)",
                ".rf_ecc_err_i (rf_ecc_err)",
                ".tmr_ev_o (wdog_tmr_ev)",
                ".tmr_ev_i (wdog_tmr_ev)",
                # docs/55. The NPU connection's three, and the same
                # failure is available here in the same form: soc_npu.v
                # brought `ptr_mismatch` and `par_err` out of both queue
                # instances and connected them TO NOTHING for a whole
                # document, and docs/52 section 10 then measured 79
                # absorbed upsets that no operator could see.
                ".q_cor_o (npu_cor_ev)",
                ".q_det_o (npu_det_ev)",
                ".cfg_tmr_o (npu_tmr_ev)",
                ".npu_cor_i (npu_cor_ev)",
                ".npu_det_i (npu_det_ev)",
                ".npu_tmr_i (npu_tmr_ev)",
                # docs/58. The CLINT's, and the same failure is
                # available in the same form: soc_clint.v could compute
                # the syndrome, correct the counter and drive the pin
                # into nothing, and every test in this repository
                # outside the campaign would still pass.
                ".mt_ecc_o (clint_mt_ecc_ev)",
                ".mt_ecc_i (clint_mt_ecc_ev)"):
        assert pat in top, (
            "soc_top.v no longer connects a fault line: {}".format(pat))
    for tied in ("rf_ecc_err_i (3'b0", "tmr_ev_i (1'b0",
                 "npu_cor_i (1'b0", "npu_det_i (1'b0", "npu_tmr_i (1'b0",
                 "mt_ecc_i (1'b0"):
        assert tied not in top, \
            "a fault line in soc_top.v has been tied off: {}".format(tied)


def test_the_npu_queues_report_their_protection_somewhere():
    """`aer_fifo` DETECTS and CORRECTS, and until docs/55 soc_npu.v
    threw all four of its reports away -- `rv_mismatch` was not even
    brought out of the instance.

    This is a TEXTUAL check and it is here because no other check in
    this repository can fail on it. Every cocotb test, every proof and
    the whole fault-injection campaign would pass on a soc_npu.v that
    left these unconnected: that is precisely the state docs/51 shipped
    and docs/52 measured. The failure mode has a name in this project --
    `pilot_top.v` left four ECC status wires unconnected and a campaign
    then classified 84 corrections as MASKED with every gate green."""
    npu = (SOC_RTL / "soc_npu.v").read_text()
    for pat in (".rv_mismatch (inj_rv_mm)", ".rv_mismatch (cap_rv_mm)",
                ".ptr_mismatch (inj_ptr_mm)", ".ptr_mismatch (cap_ptr_mm)"):
        assert pat in npu, (
            "soc_npu.v no longer brings a queue fault report out of its "
            "aer_fifo instance: {}".format(pat))
    assert ".rv_mismatch ()" not in npu, (
        "an aer_fifo rv_mismatch port in soc_npu.v is unconnected again")
    # And each one reaches BOTH destinations: a sticky bit software can
    # read in this block's own cause register, and a saturating counter
    # in BUSSTAT.
    for pat in ("assign q_cor_o = q_cor_ev;", "assign q_det_o = q_det_ev;",
                "assign cfg_tmr_o = prot_mismatch;",
                "sticky_ev[C_Q_COR    - C_STICKY0] = q_cor_ev;",
                "sticky_ev[C_Q_DET    - C_STICKY0] = q_det_ev;",
                "sticky_ev[C_CFG_TMR  - C_STICKY0] = prot_mismatch;"):
        assert pat in npu, (
            "soc_npu.v no longer routes a queue or bank fault report to "
            "both of its destinations: {}".format(pat))


def test_the_ibex_top_patch_applies_to_the_pinned_output():
    """The fault port reaches the SoC through three hunks that
    hw/soc/flow/ibex_fault_port.py applies to hw/soc/gen/ibex_top.v.
    Every anchor is asserted to occur exactly once, so a pin that moves
    the port list stops the build rather than patching the wrong place;
    this runs that check without building."""
    gen = ROOT / "hw" / "soc" / "gen" / "ibex_top.v"
    if not gen.is_file():
        pytest.skip("hw/soc/gen is empty: run flow/sv2v_ibex.sh first")
    sys.path.insert(0, str(ROOT / "hw" / "soc" / "flow"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ibex_fault_port",
        ROOT / "hw" / "soc" / "flow" / "ibex_fault_port.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    src = gen.read_text()
    for mode in ("secded", "upstream"):
        out = mod.patch(src, mode)
        assert out != src
        assert "rf_ecc_err_o" in out
        # The patch is three hunks and nothing else.
        added = len(out.splitlines()) - len(src.splitlines())
        assert added <= 7, (
            "the ibex_top patch has grown to {} added lines; it is "
            "supposed to be the smallest thing that reaches the "
            "SoC".format(added))


# =====================================================================
# 3b. THE NPU CONNECTION'S CAUSE BANK -- docs/55 H3
#
# The same question as section 1 asks of the watchdog, on a second
# block, and it has to be asked again rather than inherited: this bank
# is a different width, a different reset domain and a different
# instantiating module, and the only thing it shares with the
# watchdog's is `soc_tmr_bank.v` itself.
#
# WHAT MAKES IT WORTH A SEPARATE CENSUS. docs/52 measured the
# unprotected version producing a FALSE FAULT REPORT in 16 of 100 draws
# -- a fabricated event, not a missed one -- and a fault channel that
# invents events is worse than one that is lossy because it will be
# believed. The protection against that is three banks. Every cocotb
# test, every formal task and the whole fault-injection campaign would
# pass on a netlist holding ONE, because all three deposit into or
# reason about RTL. This is the only check that looks at the netlist.
# =====================================================================
NPU_SOURCES = [
    SOC_RTL / "soc_npu.v",
    SOC_RTL / "soc_npu_ser.v",
    SOC_RTL / "soc_tmr_bank.v",
    PILOT_RTL / "tmr_voter.v",
    PILOT_RTL / "aer_fifo.v",
    PILOT_RTL / "pilot_top.v",
]

NPU_REPLICAS = ("g_cfg_tmr.u_cfg_a.",
                "g_cfg_tmr.u_cfg_b.",
                "g_cfg_tmr.u_cfg_c.")


def _npu_prot_w():
    """soc_npu.v's PROT_W, DERIVED from the two literals it is built
    from rather than written down here.

    The RTL says `PROT_W = P_MASK + NCAUSE` and `P_MASK = P_STICKY +
    NSTICKY`, which are not literals; `NCAUSE` and `C_INJ_OVF` are. So
    the arithmetic is redone here from those two, exactly as
    hw/soc/fi/npu_targets.py redoes it, and a cause bit added to the
    block moves this expectation with it instead of turning the file
    red for the wrong reason."""
    text = (SOC_RTL / "soc_npu.v").read_text()

    def lp(name):
        m = re.search(r"localparam\s+integer\s+" + name + r"\s*=\s*(\d+)\s*;",
                      text)
        assert m, "no `localparam integer {} = <literal>;` in " \
                  "soc_npu.v".format(name)
        return int(m.group(1))

    ncause = lp("NCAUSE")
    nsticky = ncause - lp("C_INJ_OVF")
    return 2 + nsticky + ncause


NPU_PROT_W = _npu_prot_w()


def _npu_script(sources, force_flatten=False, chparam=""):
    """The connection alone, with the frozen pilot BLACK-BOXED.

    That is the same scope docs/51 section 11 measured at 717 flip-flops
    and the same scope hw/soc/flow/fi_npu_coverage.sh censuses, and it
    is chosen for a mechanical reason as well as a principled one:
    elaborating the whole die costs about a minute and this file already
    runs yosys eleven times.

    `blackbox` comes BEFORE `hierarchy` here and takes a bare name,
    which works because this script does not use `read_verilog -defer`.
    hw/soc/flow/syn_soc.sh does, and has to spell the pattern
    differently; its comment records why.
    """
    lib = _sg13g2_liberty()
    script = "read_verilog -I {} -I {} {};".format(
        SOC_RTL, PILOT_RTL, " ".join(str(s) for s in sources))
    script += " blackbox pilot_top;"
    if chparam:
        script += " " + chparam
    script += " hierarchy -top soc_npu;"
    if force_flatten:
        script += " attrmap -modattr -remove keep_hierarchy;"
    script += " synth -top soc_npu -flatten;"
    if lib is not None:
        script += " dfflibmap -liberty {0}; abc -liberty {0};".format(lib)
    script += " attrmap -modattr -remove keep_hierarchy; flatten; opt_clean;"
    return script


@pytest.fixture(scope="module")
def npu_asic(workdir):
    return _census(_npu_script(NPU_SOURCES), workdir)


@needs_yosys
def test_the_npu_cause_bank_is_three_banks_in_the_netlist(npu_asic):
    found = {r: npu_asic.in_instance(r) for r in NPU_REPLICAS}
    assert all(v == NPU_PROT_W for v in found.values()), (
        "the NPU cause bank collapsed in the netlist: expected {} "
        "flip-flops per replica, found {}. Three replicas written from "
        "the same expression are one bank after opt_dff + opt_merge, and "
        "the voter above them then votes three copies of the same upset "
        "value. Total flip-flops in this netlist: {}.".format(
            NPU_PROT_W, found, npu_asic.total))


@needs_yosys
def test_the_npu_cause_bank_survives_every_attribute_being_deleted(workdir):
    """The POL/MIX storage transform on its own, with `keep` and
    `keep_hierarchy` deleted from the TEXT of the sources so that no
    pass can honour them and none can re-derive them.

    A TOTAL census and not a per-replica one, for the reason
    test_no_flip_flop_is_lost_when_every_attribute_is_deleted_asic gives:
    with keep_hierarchy gone the banks are flattened during `synth` and
    the instance path they would be counted by no longer exists. The
    total is strictly wider anyway -- it would also catch storage lost
    somewhere else in the connection."""
    dst = Path(workdir) / "npu_noattr"
    dst.mkdir(exist_ok=True)
    stripped = []
    for src in NPU_SOURCES:
        text = src.read_text()
        for attr in _ATTRS:
            text = text.replace(attr, "")
        target = dst / src.name
        target.write_text(text)
        stripped.append(target)
    with_attrs = _census(_npu_script(NPU_SOURCES), workdir)
    without = _census(_npu_script(stripped, force_flatten=True), workdir)
    assert without.total == with_attrs.total, (
        "the NPU connection maps to {} flip-flops with every keep and "
        "keep_hierarchy deleted from the text, against {} with them. "
        "Something in this block is held together by an attribute alone, "
        "and an attribute is not portable to a front end that does not "
        "read yosys's.".format(without.total, with_attrs.total))


@needs_yosys
def test_removing_the_mix_transform_from_one_npu_replica_collapses_it(
        workdir):
    """A guard that cannot fail is not a guard.

    `.MIX(0)` on replica C is FUNCTIONALLY IDENTICAL RTL, bit for bit at
    every port, so no simulation and no proof in this repository can see
    it. What it does is make C store `v[i] ^ POL_C[i]` -- one of the only
    two storage functions a single bit has -- and POL_C is zero on every
    odd bit, so on exactly those bits C stores what A stores and
    structural hashing merges the pair. The count that comes back is the
    pigeonhole measured rather than argued."""
    dst = Path(workdir) / "npu_mut_mix"
    dst.mkdir(exist_ok=True)
    mutated = []
    hits = 0
    for src in NPU_SOURCES:
        text = src.read_text()
        old = ".POL(POL_C), .MIX(1))"
        if old in text:
            hits += text.count(old)
            text = text.replace(old, ".POL(POL_C), .MIX(0))")
        for attr in _ATTRS:
            text = text.replace(attr, "")
        target = dst / src.name
        target.write_text(text)
        mutated.append(target)
    assert hits == 1, (
        "the .MIX(1) anchor on the NPU cause bank's replica C matched {} "
        "times and must match once; the source moved".format(hits))
    base = _census(_npu_script(NPU_SOURCES, force_flatten=True), workdir)
    mut = _census(_npu_script(mutated, force_flatten=True), workdir)
    lost = base.total - mut.total
    assert lost > 0, (
        "turning the MIX transform off on replica C of the NPU cause "
        "bank lost NO flip-flops ({} either way). Either the replicas "
        "are being held apart by something else -- which would mean this "
        "file is not measuring what it claims -- or they had already "
        "merged.".format(base.total))
    # POL_C is 0xAAAA..., which is zero on every EVEN bit index, so those
    # are the bits on which C would store exactly what A stores.
    expected = (NPU_PROT_W + 1) // 2
    assert lost == expected, (
        "expected the mutation to lose {} flip-flops -- one for each of "
        "the {} even bits of the {}-bit word, where POL_C is zero and a "
        "polarity-only replica C stores what replica A stores -- and it "
        "lost {}".format(expected, expected, NPU_PROT_W, lost))


@needs_yosys
def test_the_aer_strobe_gate_is_in_the_netlist_and_costs_no_flip_flop(
        workdir):
    """docs/56 H5 is the one hardening in this repository whose whole
    mechanism is COMBINATIONAL, and that is exactly why it needs a
    census of its own.

    Every other guard here is checked by counting flip-flops, and this
    one adds none: the pin becomes `aer_in_stb && (ev_state == E_PIN_S)`
    and the redundancy it uses was already in the netlist. So a mapper
    that folded the gate away, or an edit that removed it, would leave
    the flip-flop count IDENTICAL -- and the campaign, which deposits
    into RTL, and the cocotb suite, which drives RTL, would both go on
    passing on a part whose die can be strobed by one upset again.

    The check is the mutation: build the design with the gate removed
    and require the STROBE'S FAN-IN CONE to lose the event engine's
    state, at exactly the same flip-flop count. That says two things at
    once -- the gate is physically present, and it costs no state.

    IT USED TO BE A CELL COUNT AND docs/76 HAD TO CHANGE IT, which is
    worth stating because the replacement is stronger and the reason it
    was needed is a real property of this flow. The assertion was
    `base.cells > mut.cells`: removing a combinational gate must make
    the netlist smaller. Measured on the design docs/76 builds, it
    INVERTED -- the mutant came out 39 cells LARGER. The mechanism is
    named in docs/76 section 9.2: `aer_stb_state` is a bare
    `ev_state == E_PIN_S` comparison, and yosys's mapper decides
    whether to DUPLICATE `ev_state` and materialise that comparison as
    a register of its own on cost grounds that the mutation changes.
    The intact and mutated designs therefore differ by a register
    duplication as well as by the gate, and the sign of the cell delta
    is the mapper's decision rather than the gate's cost.
    A cone census cannot be inverted that way: it asks what the die's
    strobe pin actually depends on, which is the whole content of H5.
    `hw/soc/fi/gl_netlist.py` is the same walker docs/75 uses on the
    shipped netlist, imported rather than reimplemented."""
    dst = Path(workdir) / "npu_mut_stb"
    dst.mkdir(exist_ok=True)
    old = ("assign aer_in_stb_q = aer_in_stb && aer_stb_state;\n"
           "  assign aer_stb_mm   = aer_in_stb ^ aer_stb_state;")
    new = ("assign aer_in_stb_q = aer_in_stb;\n"
           "  assign aer_stb_mm   = 1'b0;\n"
           "  wire _unused_stb = &{1'b0, aer_stb_state, 1'b0};")
    mutated = []
    hits = 0
    for src in NPU_SOURCES:
        text = src.read_text()
        hits += text.count(old)
        text = text.replace(old, new)
        target = dst / src.name
        target.write_text(text)
        mutated.append(target)
    assert hits == 1, (
        "the AER strobe gate matched {} times in the NPU sources and "
        "must match once; soc_npu.v moved".format(hits))

    base = _census(_npu_script(NPU_SOURCES), workdir)
    mut = _census(_npu_script(mutated), workdir)
    assert base.total == mut.total, (
        "removing the AER strobe gate changed the FLIP-FLOP count "
        "({} -> {}). H5 is combinational and must cost no state; if it "
        "does, this test is measuring something else".format(
            base.total, mut.total))

    base_cone = _strobe_cone(_npu_script(NPU_SOURCES), workdir, "stb_base")
    mut_cone = _strobe_cone(_npu_script(mutated), workdir, "stb_mut")
    # THE NAME IS NOT ASSERTED, ONLY THAT THERE IS SOMETHING BESIDES THE
    # STROBE FLAG. `aer_stb_state` is a bare `ev_state == E_PIN_S`
    # comparison and the mapper may keep it as combinational logic over
    # `ev_state` or materialise it as a register of its own; both were
    # observed while docs/76 was written, on the SAME RTL at two
    # settings of an unrelated parameter. What cannot vary is that a
    # strobe which is gated depends on more than the flag, and a strobe
    # which is not depends on the flag alone.
    extra = {n for n in base_cone if "aer_in_stb" not in str(n)}
    assert extra, (
        "the die's strobe pin depends on nothing but the strobe flag: "
        "its fan-in cone is {}. The gate has been optimised away or is "
        "no longer there, and NOTHING ELSE in this repository can fail "
        "on that -- the campaign and the cocotb suite both drive the "
        "RTL.".format(sorted(str(n) for n in base_cone)))
    assert all(("ev_state" in str(n)) or ("aer_stb_state" in str(n))
               for n in extra), (
        "the strobe's cone carries state this test does not recognise "
        "as the event engine's: {}".format(sorted(str(n) for n in extra)))
    assert not {n for n in mut_cone if "aer_in_stb" not in str(n)}, (
        "the mutation was supposed to leave the strobe depending on the "
        "flag alone and did not: {}. This test is then measuring "
        "nothing.".format(sorted(str(n) for n in mut_cone)))


@needs_yosys
def test_npu_harden_zero_removes_the_replicas(workdir):
    """`HARDEN = 0` is the baseline docs/55 section 7 prices the
    redundancy against, and this is the check that it IS a baseline: it
    has to hold the same state once rather than three times.

    IT IS EXACTLY 2 x PROT_W, AND THE PREDICTION THAT IT WOULD BE ONE
    MORE THAN THAT WAS WRONG. docs/41 section 6.3 measured the watchdog's
    HARDEN = 0 at 53 flip-flops and not 58, because with `prot_mismatch`
    a constant its `tmr_err` and `tmr_count` fields are dead and the
    optimiser deletes them. The same reasoning says this bank's CFG_TMR
    sticky bit should go the same way, and it does NOT: HARDEN = 0 holds
    all PROT_W bits.

    The difference is the CLEAR PATH, and it is a consequence of a
    decision made for an unrelated reason. The watchdog's `tmr_err` is
    not clearable, so its next value is `tmr_err | 0`, which is `d == q`,
    which `opt_dff` folds into the reset value. This block's sticky bits
    ARE write-1-to-clear -- IRQ_CAUSE is an interrupt cause register and
    a bit in it that could not be acknowledged would hold an enabled line
    asserted for ever -- so the next value is `q & ~clr`, and proving
    THAT constant needs a fixpoint no optimiser here runs.

    So the clearability decision costs one flip-flop in a configuration
    nothing ships. It is recorded because the wrong number was written
    here first and this test is what found it, which is the whole reason
    docs/41 section 6.1 derives its counts instead of writing them
    down."""
    base = _census(_npu_script(NPU_SOURCES), workdir)
    plain = _census(
        _npu_script(NPU_SOURCES, chparam="chparam -set HARDEN 0 soc_npu;"),
        workdir)
    for r in NPU_REPLICAS:
        assert plain.in_instance(r) == 0, (
            "HARDEN = 0 still holds flip-flops under {}".format(r))
    lost = base.total - plain.total
    expected = 2 * NPU_PROT_W
    assert lost == expected, (
        "HARDEN = 0 lost {} flip-flops; expected {} = three replicas of "
        "{} bits minus one plain bank of the same width. If it lost {} "
        "instead, the CFG_TMR sticky bit has become removable -- which "
        "would mean it is no longer clearable, and this docstring is "
        "then the record of why that matters.".format(
            lost, expected, NPU_PROT_W, expected + 1))


@needs_yosys
def test_the_npu_instantiates_the_frozen_voter_and_three_distinct_banks():
    """A second, TEXTUAL check on the same thing, because the census
    cannot see a change of parameters at the instance: three replicas
    given the same POL and MIX would census as three banks under
    keep_hierarchy and collapse without it. docs/41 section 6.6 lists
    that gap and pairs the same two checks for the watchdog."""
    npu = (SOC_RTL / "soc_npu.v").read_text()
    assert "tmr_voter #(.WIDTH(PROT_W)) u_cfg_vote" in npu
    banks = re.findall(
        r"soc_tmr_bank\s*#\(\.W\(PROT_W\),\s*\.RST_VAL\(64'd0\),"
        r"\s*\.POL\((POL_[ABC])\),\s*\.MIX\((\d)\)\)", npu)
    assert len(banks) == 3, (
        "soc_npu.v instantiates {} soc_tmr_bank replicas, expected "
        "three".format(len(banks)))
    assert len(set(banks)) == 3, (
        "two of the NPU cause bank's replicas have the same (POL, MIX): "
        "{}. They would present the same stored function to opt_merge "
        "and hash away.".format(banks))
    # And the polarities are the ones the transform needs: A true, B and
    # C mixed and mutually inverse.
    assert ("POL_A", "0") in banks
    assert ("POL_B", "1") in banks and ("POL_C", "1") in banks
    assert "POL_B = 64'h5555555555555555" in npu
    assert "POL_C = 64'hAAAAAAAAAAAAAAAA" in npu


@needs_yosys
def test_the_transport_is_the_campaign_site_list_in_the_netlist(npu_asic):
    """A DIFFERENT QUESTION FROM EVERY OTHER CHECK IN THIS FILE, and one
    nothing in this repository had asked.

    Every other census here counts flip-flops. This one asks whether the
    flip-flops in the netlist are THE ONES THE FAULT-INJECTION CAMPAIGN
    BELIEVES IT IS INJECTING INTO. The campaign deposits into RTL, and
    docs/52 section 13's last bullet says so plainly -- "the campaign
    cannot fail because a flip-flop vanished in synthesis". So a bound
    whose counter the mapper had deleted would be reported as working by
    the campaign, by every cocotb test and by the formal proof, and the
    part would ship without it. That is docs/38 section 8.5's lockstep
    and hw/rtl/pilot_top.v section 9's configuration TMR, in a third
    place.

    `soc_npu_ser.v` is the whole of one stratum, so its declared bit
    count and its mapped flip-flop count are comparable directly. Both
    sides are DERIVED: the left from hw/soc/fi/npu_targets.py, the right
    from the `src` attributes of the netlist.
    """
    sys.path.insert(0, str(ROOT / "hw" / "soc" / "fi"))
    import npu_targets

    declared = npu_targets.stratum_bits("ser")
    mapped = npu_asic.from_file("soc_npu_ser.v")
    assert mapped == declared, (
        "hw/soc/fi/npu_targets.py's `ser` stratum declares {} bits and "
        "the mapped netlist holds {} flip-flops from soc_npu_ser.v. The "
        "campaign injects into the RTL, so it would report a mechanism "
        "working whose flip-flops the mapper had removed -- which is "
        "exactly what docs/38 section 8.5 measured costing an unguarded "
        "lockstep 15,455 um2.".format(declared, mapped))


@needs_yosys
def test_both_guards_survive_synthesis_at_their_full_width(workdir):
    """The two counters docs/55 added and the one docs/56 added, by
    name, in the mapped netlist.

    The count above is a total and a total can hide a redistribution.
    These are the three structures whose loss would be silent everywhere
    else, so they are checked individually and against the widths the
    RTL derives rather than against numbers written here.

    docs/56's `oh_guard` is the one most likely to go: three bits
    against the others' eight and nine, a next value that is a small
    function of two flags, and on a healthy part it counts to two and
    clears -- exactly the shape an optimiser is entitled to try to fold.
    Nothing else in this repository could fail if it did. The campaign
    deposits into RTL, the cocotb tests drive RTL, and soc_npu.v has no
    proof at all.
    """
    # A by-NAME census needs the names, which the post-mapping flatten
    # erases -- so this one stops before `dfflibmap` and counts the
    # generic flip-flop cells, which still carry the public net they
    # drive. It is a weaker netlist than the one above and it is the
    # strongest one in which these two signals still have names.
    out = Path(workdir) / "guards.json"
    script = ("read_verilog -I {} -I {} {};".format(
                  SOC_RTL, PILOT_RTL,
                  " ".join(str(s) for s in NPU_SOURCES))
              + " blackbox pilot_top; hierarchy -top soc_npu;"
                " synth -top soc_npu -flatten; opt_clean;"
                " write_json {};".format(out))
    _run_yosys(script, workdir)
    design = json.loads(out.read_text())

    width = {}
    for mod in design["modules"].values():
        for name, net in mod.get("netnames", {}).items():
            width[name] = len(net["bits"])

    text = (SOC_RTL / "soc_npu_ser.v").read_text()
    m = re.search(r"localparam\s+integer\s+GUARD_W\s*=\s*\$clog2", text)
    assert m, "soc_npu_ser.v no longer derives GUARD_W with $clog2"

    # `oh_guard`'s floor is DERIVED from the bound it has to reach, not
    # written down: soc_npu.v sizes it as the width of OH_MAX, and a
    # narrower net could not count that far.
    npu = (SOC_RTL / "soc_npu.v").read_text()

    def _lpi(name):
        m = re.search(r"localparam\s+integer\s+" + name + r"\s*=\s*(\d+)\s*;",
                      npu)
        assert m, "no `localparam integer {} = <literal>;` in " \
                  "soc_npu.v".format(name)
        return int(m.group(1))

    oh_max = _lpi("OH_WAIT") + _lpi("OH_SLACK")

    for sig, floor in (("u_ser.guard", 4), ("win_guard", 4),
                       ("oh_guard", max(1, oh_max.bit_length()))):
        got = width.get(sig)
        assert got is not None, (
            "{} is not a net in the synthesised connection at all. A "
            "bounded wait whose counter the mapper deleted is a bounded "
            "wait that does not exist, and nothing else in this "
            "repository would notice.".format(sig))
        assert got >= floor, (
            "{} is {} bits wide in the netlist, which is too narrow to "
            "reach its bound".format(sig, got))

# =====================================================================
# 4. the composition, one level up
# =====================================================================
@needs_yosys
def test_the_watchdog_inside_the_gptimer_keeps_its_replicas(workdir):
    """`soc_top.v` does not instantiate `soc_wdog` directly; it
    instantiates `soc_gptimer`, which instantiates the watchdog. A
    census of the watchdog on its own says nothing about what happens
    when the optimiser can see the shell's logic as well, and the shell
    is where the register decode and the read multiplexer live."""
    lib = _sg13g2_liberty()
    sources = SOURCES + [SOC_RTL / "soc_gptimer.v"]
    script = ("read_verilog -I {} {};".format(
        SOC_RTL, " ".join(str(s) for s in sources))
        + " hierarchy -top soc_gptimer;"
          " synth -top soc_gptimer -flatten;")
    if lib is not None:
        script += " dfflibmap -liberty {0}; abc -liberty {0};".format(lib)
    script += " attrmap -modattr -remove keep_hierarchy; flatten; opt_clean;"
    census = _census(script, workdir)
    found = {r: census.in_instance("u_wdog." + r) for r in REPLICAS}
    assert census.total > 0
    assert all(v == PROT_W for v in found.values()), (
        "the watchdog's replicas did not survive synthesis inside "
        "soc_gptimer: expected {} each, found {}".format(PROT_W, found))


# =====================================================================
# 5. what the design actually instantiates, checked textually
# =====================================================================
def test_nothing_in_the_design_instantiates_the_watchdog_unhardened():
    """HARDEN exists for measurement. A parameter that can turn a
    defence off is a parameter someone turns off, and the only thing
    standing between that and silicon is this test."""
    text = (SOC_RTL / "soc_wdog.v").read_text()
    assert re.search(r"parameter\s+integer\s+HARDEN\s*=\s*1", text), (
        "soc_wdog.v's HARDEN parameter no longer defaults to 1")
    assert ".HARDEN" not in (SOC_RTL / "soc_gptimer.v").read_text(), (
        "soc_gptimer.v overrides soc_wdog's HARDEN parameter. Nothing in "
        "the design may: HARDEN = 0 is the unprotected block.")
    # soc_top.v's GPTIMER instantiation and not the whole file: since
    # docs/67 the memories take `.HARDEN(MEM_HARDEN)` from soc_top's own
    # defaulted parameter, which test_soc_memory_guards.py guards.
    top = (SOC_RTL / "soc_top.v").read_text()
    m = re.search(r"soc_gptimer\s*#\((.*?)\)\s*u_timer0", top, re.S)
    assert m, "soc_top.v no longer instantiates soc_gptimer with parameters"
    assert ".HARDEN" not in m.group(1), (
        "soc_top.v overrides the watchdog's HARDEN through soc_gptimer. "
        "Nothing in the design may: HARDEN = 0 is the unprotected block.")


def test_the_voter_is_the_blob_the_pilot_freeze_pins():
    """The watchdog votes with `hw/rtl/tmr_voter.v` itself rather than a
    copy of it, so the SoC's majority gate is the one
    `formal/tmr_voter.sby` proves exhaustively and
    `hw/tb/test_tmr_voter.py` checks against an independent Python
    model. This asserts the file is still the blob
    `docs/34-pilot-freeze.md` section 2 pins -- which is both a check
    that the pilot freeze holds and a check that the SoC did not quietly
    fork the primitive."""
    out = subprocess.run(
        ["git", "hash-object", str(PILOT_RTL / "tmr_voter.v")],
        cwd=ROOT, capture_output=True, text=True, check=True)
    assert out.stdout.strip().startswith(TMR_VOTER_PINNED_BLOB), (
        "hw/rtl/tmr_voter.v is {} and docs/34 pins {}...".format(
            out.stdout.strip(), TMR_VOTER_PINNED_BLOB))


def test_the_watchdog_instantiates_that_voter_and_three_distinct_banks():
    """Textual, and complementary to the census above rather than a
    weaker version of it: the census proves three banks EXIST in the
    netlist, this proves they are three banks the source asked for with
    three different storage transforms. A future edit that made all
    three `MIX(1)` with the same POL would still census as three banks
    under keep_hierarchy and would be one bank without it."""
    text = (SOC_RTL / "soc_wdog.v").read_text()
    assert "tmr_voter #(.WIDTH(PROT_W))" in text
    banks = re.findall(r"soc_tmr_bank\s*#\((.*?)\)\s*\n\s*u_prot_([abc])",
                       text, re.S)
    assert len(banks) == 3, "expected three soc_tmr_bank instances"
    signatures = {re.sub(r"\s+", "", params) for params, _ in banks}
    assert len(signatures) == 3, (
        "two replicas carry the same storage transform, so they are one "
        "bank to structural hashing: {}".format(signatures))


# =====================================================================
# 4b. W9: the reset request cannot be asserted by the decode alone
# =====================================================================
#
# docs/75 section 6. Everything above this line asks whether the
# REDUNDANCY survived synthesis. This asks the opposite question about
# the same word: whether the DECODE of it can reach the system reset
# without going through a flip-flop.
#
# It could, until docs/75. `rst_req_o` was `(rst_hold != 0)`, five bits
# of a combinational decode of the voted word, and `soc_top.v` builds
# `rst_raw_n = rst_ni && !wdog_rst_req` and hangs every flip-flop in the
# SoC off it asynchronously -- under a comment asserting that the
# request is registered, which it was not. `docs/74` section 10.2
# measured what that costs on the sign-off netlist: 174 of 174 upsets
# into the replica banks were masked by the vote AND restarted the SoC,
# because masking an upset changes the W6 report, changing the word
# moves twenty-nine flip-flops per replica through two XOR trees, and a
# transient of two of the three voter inputs is a majority.
#
# THIS IS A NETLIST PROPERTY AND NOTHING ELSE CAN SEE IT. `rst_req_o =
# in_reset` and `rst_req_o = in_reset && in_reset_q` are the same
# function of the same state on every cycle -- W9a in
# hw/soc/formal/soc_wdog_props.v proves the two operands equal by
# k-induction -- so no simulation, no proof and no RTL fault-injection
# campaign in this repository can tell them apart. It is exactly the
# `.MIX(0)` shape of section 3, and it gets the same treatment: a check
# on the mapped netlist, with the mutations that make it fail.
#
# The check is a SAT proof and not a structural search, because a
# structural search would be recording `abc`'s factoring. What is
# asserted is the logical statement -- no assignment to the mapped
# netlist's combinational inputs asserts `rst_req_o` while `in_reset_q`
# is zero -- and `abc` may implement it however it likes.
def _wdog_netlist(workdir, sources, name):
    nl = Path(workdir) / (name + ".nl.v")
    _run_yosys(_asic_script(sources) + " write_verilog -noattr {};".format(nl),
               workdir)
    return nl


def _sat_reset_gated(workdir, nl):
    """Prove, on the MAPPED netlist, that in_reset_q = 0 forces
    rst_req_o = 0. Returns (ok, output).

    `read_liberty` without `-lib` brings the cells' own functions in, so
    the SAT solver sees through the standard cells rather than treating
    them as black boxes; `async2sync` is needed because yosys's SAT pass
    cannot import an asynchronous-reset flip-flop, and it changes only
    how the reset is modelled, not the combinational cone this proves a
    property of."""
    lib = _sg13g2_liberty()
    script = ("read_liberty -ignore_miss_func {}; read_verilog {}; "
              "hierarchy -top {}; flatten; opt_clean; async2sync; "
              "sat -seq 1 -verify -prove rst_req_o 1'b0 "
              "-set in_reset_q 1'b0;".format(lib, nl, TOP))
    result = subprocess.run([YOSYS, "-p", script], capture_output=True,
                            text=True, cwd=workdir, timeout=900)
    return result.returncode == 0, result.stdout + result.stderr


@needs_yosys
@pytest.mark.skipif(_sg13g2_liberty() is None,
                    reason="no sg13g2 liberty; there is no mapped netlist "
                           "to prove anything about")
def test_no_transient_of_the_voted_word_can_reach_the_system_reset(workdir):
    """W9, on the netlist the foundry would receive."""
    ok, out = _sat_reset_gated(workdir, _wdog_netlist(workdir, SOURCES, "w9"))
    assert ok, (
        "on the mapped netlist there is an assignment that asserts "
        "rst_req_o while W9's in_reset_q flip-flop is zero. That means "
        "a combinational decode of the voted protected word can reach "
        "soc_top.v's asynchronous rst_raw_n on its own, which is what "
        "docs/74 section 10.2 measured resetting the SoC on 174 of 174 "
        "CORRECTED upsets.\n" + out[-3000:])


@needs_yosys
@pytest.mark.skipif(_sg13g2_liberty() is None, reason="no sg13g2 liberty")
def test_the_reset_gate_mutations_both_fail_the_proof(workdir):
    """Two mutations, because the guard has two ways to be vacuous.

    M1 removes the gate. `in_reset_q` then drives nothing, opt_clean
    deletes it, and the proof cannot even be stated -- so the guard has
    to fail on a MISSING signal and not pass on one. This is the
    pre-docs/75 design, exactly.

    M2 keeps the flip-flop and ORs it in instead of ANDing it. The
    signal exists, the flip-flop count is unchanged, and the proof
    fails. This is the mutation that says the proof is about the
    LOGIC and not about whether a name is present.
    """
    m1 = _mutated(workdir, "w9_ungated",
                  [("assign rst_req_o = in_reset && in_reset_q;",
                    "assign rst_req_o = in_reset;")])
    census1 = _census(_asic_script(m1), workdir)
    assert census1.total == UNPROT_FF + 3 * PROT_W, (
        "M1 should lose exactly W9's flip-flop; found {} against the "
        "repaired design's {}".format(
            census1.total, UNPROT_FF + RSTREQ_FF + 3 * PROT_W))
    ok1, out1 = _sat_reset_gated(workdir, _wdog_netlist(workdir, m1, "m1"))
    assert not ok1, "M1 passed the W9 proof, so the proof proves nothing"
    assert "in_reset_q" in out1

    m2 = _mutated(workdir, "w9_ored",
                  [("assign rst_req_o = in_reset && in_reset_q;",
                    "assign rst_req_o = in_reset || in_reset_q;")])
    census2 = _census(_asic_script(m2), workdir)
    assert census2.total == UNPROT_FF + RSTREQ_FF + 3 * PROT_W, (
        "M2 was supposed to keep every flip-flop and only change the "
        "gate; it did not, so it no longer demonstrates what it was "
        "written to demonstrate")
    ok2, out2 = _sat_reset_gated(workdir, _wdog_netlist(workdir, m2, "m2"))
    assert not ok2, "M2 passed the W9 proof, so the proof proves nothing"
    assert "proof did fail" in out2


def test_the_top_level_reset_path_is_still_the_one_W9_was_written_for():
    """W9 is a statement about a composition, so the composition is
    asserted here rather than assumed.

    If a later edit registered `wdog_rst_req` inside `soc_top.v`, or
    stopped using it asynchronously, W9 would still be correct and would
    no longer be load-bearing -- and this test failing is how a reader
    would find that out."""
    text = (SOC_RTL / "soc_top.v").read_text()
    assert "wire rst_raw_n = rst_ni && !wdog_rst_req;" in text, (
        "soc_top.v no longer builds the raw reset the way soc_wdog.v's "
        "W9 argument is written against")
    assert re.search(r"always @\(posedge clk_i or negedge rst_raw_n\)", text), (
        "soc_top.v no longer uses rst_raw_n as an ASYNCHRONOUS reset, "
        "which is the whole reason a glitch on it mattered")
    wdog = (SOC_RTL / "soc_wdog.v").read_text()
    assert "assign rst_req_o = in_reset && in_reset_q;" in wdog


# =====================================================================
# 5. the composition, at the top
#
# docs/45-soc-top-synthesis.md is the first time `soc_top` was
# synthesised as one design; docs/41 section 10 item 7, docs/43 section
# 11 and docs/44 section 10's last line had each recorded that it never
# had been. The checks below guard the three things that made it
# possible and would silently stop being true.
# =====================================================================
SOC_FLOW = ROOT / "hw" / "soc" / "flow"


def _soc_mem_ports():
    """The port list of hw/soc/rtl/soc_mem.v, as (direction, width, name)
    triples in declaration order."""
    text = (SOC_RTL / "soc_mem.v").read_text()
    body = text.split("(", 1)[1].split(");", 1)[0]
    ports = []
    for m in re.finditer(
            r"\b(input|output)\s+(?:wire|reg)?\s*(\[[^\]]*\])?\s*(\w+)",
            body):
        ports.append((m.group(1),
                      re.sub(r"\s+", "", m.group(2) or ""),
                      m.group(3)))
    return ports


def _soc_mem_params():
    """The parameter names of hw/soc/rtl/soc_mem.v, in declaration order.

    Read rather than written down, for the reason the docstring of
    test_the_memory_boundary_models_declare_soc_mems_ports gives about
    ports: `soc_top.v` names these on both memory instances, so a copy
    that goes stale stops an elaboration somewhere and not everywhere.
    sw/tests/test_soc_memory_guards.py checks the four declarations in the
    tree against each other; this is the fifth, and it is generated so it
    cannot disagree."""
    text = (SOC_RTL / "soc_mem.v").read_text()
    body = text.split("#(", 1)[1].split(") (", 1)[0]
    return re.findall(r"parameter\s+(?:integer\s+)?(\w+)\s*=", body)


def _generated_mem_ports(marker):
    """The same, for one of the two memory boundary models that
    hw/soc/flow/syn_soc_top.sh writes into its output directory. The
    models live inside the script as here-documents, so they are read
    out of the script rather than out of a build."""
    script = (SOC_FLOW / "syn_soc_top.sh").read_text()
    start = script.index(marker)
    block = script[start:script.index("\nEOF", start)]
    body = block.split("module soc_mem", 1)[1]
    body = body.split(") (", 1)[1].split(");", 1)[0]
    ports = []
    for m in re.finditer(
            r"\b(input|output)\s+(?:wire|reg)?\s*(\[[^\]]*\])?\s*([\w, ]+)",
            body):
        for name in m.group(3).split(","):
            name = name.strip()
            if name:
                ports.append((m.group(1),
                              re.sub(r"\s+", "", m.group(2) or ""),
                              name))
    return ports


def test_the_memory_boundary_models_declare_soc_mems_ports():
    """`soc_top.v` instantiates `soc_mem` twice, and the whole-design
    synthesis of docs/45 replaces both instances -- by a blackbox for
    the area measurement and by an SRAM macro stand-in for the timing
    one. Every path into or out of a memory crosses that boundary, so if
    `soc_mem.v` grows, loses or renames a port and a model does not
    follow, the measurement quietly becomes a measurement of a different
    boundary. Two failure modes, and only the first is loud: a port the
    model does not declare stops elaboration, and a port whose WIDTH the
    model gets wrong does not.

    This is deliberately a check on the port list and nothing else. The
    stand-in is NOT functionally equivalent to soc_mem.v and is not
    supposed to be -- docs/45 section 3.2 states what it does and does
    not reproduce, and a test that asserted more than the interface
    would be asserting something the flow does not claim."""
    real = _soc_mem_ports()
    for marker in ("// BLACKBOX DECLARATION",
                   "// SRAM MACRO STAND-IN"):
        model = _generated_mem_ports(marker)
        assert [(d, w, n) for d, w, n in model] == real, (
            "the {} in hw/soc/flow/syn_soc_top.sh no longer declares "
            "soc_mem.v's ports.\n  soc_mem.v: {}\n  model:     {}".format(
                marker.strip("/ "), real, model))


def test_the_whole_design_flow_uses_the_block_flows_recipe():
    """docs/45's whole-design area is compared against the per-block
    areas of docs/38, docs/39, docs/40, docs/41 and docs/44, and a
    comparison between two differently measured things is not a
    comparison. The three scripts have to agree on the mapping
    constraint; this fails if one of them drifts."""
    constraint = ("set_driving_cell sg13g2_buf_4\n"
                  "set_load 0.005\n")
    for name in ("syn_soc_top.sh", "syn_soc.sh", "syn_ibex.sh"):
        assert constraint in (SOC_FLOW / name).read_text(), (
            "hw/soc/flow/{} no longer writes the abc constraint the "
            "other two write".format(name))


def test_every_flow_that_builds_soc_top_reads_every_module_it_instantiates():
    """The defect `docs/57` and `docs/59` found independently, made loud.

    `docs/51` added `u_npu` to `soc_top.v` and updated ONE of the four
    source lists that build that file. `flow/sim_soc.sh` was the one; the
    other three -- `syn_soc_top.sh`, `pnr_soc_top.sh` and `fi_core.sh` --
    were not, and the consequences ran for ten documents:

      * `fi_core.sh` stopped elaborating outright, so `docs/42`,
        `docs/43` and `docs/46`'s campaigns could not be rebuilt. Loud,
        and still not noticed for six documents.
      * `syn_soc_top.sh` and `pnr_soc_top.sh` stopped elaborating too --
        but nothing re-ran them, so `hw/soc/pnr/runs/full3` and every
        area, timing and power number in `docs/45`, `docs/47`, `docs/48`,
        `docs/49`, `docs/50` and `docs/53` stayed on disk as the sign-off
        of a design missing 50.7 % of its cells. SILENT, which is worse.

    So this test is not about the NPU. It is about the shape: a module
    `soc_top.v` instantiates that some flow cannot resolve. It reads the
    instantiations out of the RTL and asserts each one whose file exists
    in `hw/soc/rtl/` or the frozen `hw/rtl/` is named by all four lists.

    What it does NOT do is check that the four lists are the SAME list.
    They are not and must not be: `sim_soc.sh` reads `soc_mem.v` and the
    synthesis flows must not, `fi_core.sh` adds a testbench, and
    `docs/45` section 9 item 4 is the standing proposal to derive one
    list from the top -- which would delete this test and is a decision
    about comparability rather than a tidy-up.
    """
    top = (SOC_RTL / "soc_top.v").read_text()
    instantiated = set(re.findall(
        r"^\s{2,}([a-z][a-z0-9_]*)\s+(?:#\s*\(|u_[a-z0-9_]+\s*\()",
        top, re.M))
    # `soc_mem` is deliberately substituted: syn_soc_top.sh has four
    # implementations of it and pnr_soc_top.sh reads the SRAM one, so it
    # is not checked by file name.
    substituted = {"soc_mem"}
    assert "soc_npu" in instantiated, (
        "the pattern stopped matching soc_top.v's instantiations; this "
        "test would then pass vacuously")

    # Comments are stripped before the search, so a module named only in
    # a header paragraph does not satisfy the check. `pnr_soc_top.sh`
    # builds part of its list in a `for f in soc_bus soc_apb_bridge ...`
    # loop, so the token and not the file name is what is looked for.
    def code(path):
        return "\n".join(ln for ln in (SOC_FLOW / path).read_text()
                         .splitlines() if not ln.lstrip().startswith("#"))

    flows = {name: code(name)
             for name in ("syn_soc_top.sh", "pnr_soc_top.sh", "fi_core.sh",
                          "sim_soc.sh")}
    checked = []
    for mod in sorted(instantiated - substituted):
        if not ((SOC_RTL / f"{mod}.v").is_file()
                or (PILOT_RTL / f"{mod}.v").is_file()):
            continue        # an Ibex module or a library cell
        checked.append(mod)
        for name, text in flows.items():
            assert re.search(r"\b" + mod + r"\b", text), (
                "hw/soc/flow/{} does not read {}.v, which "
                "hw/soc/rtl/soc_top.v instantiates. That is the defect "
                "docs/57 section 3 and docs/61 are about: the flow "
                "either fails to elaborate, or -- worse -- keeps "
                "reporting from a netlist somebody built before the "
                "module existed.".format(name, mod))
    assert len(checked) >= 8, (
        "only {} of soc_top.v's children were checked; the file layout "
        "moved and this test is now nearly vacuous".format(len(checked)))

    # And the transitive half, which is what made this one expensive:
    # soc_npu.v instantiates the FROZEN pilot rather than copying it, and
    # a list that has soc_npu.v and not pilot_top.v fails one level down.
    npu = (SOC_RTL / "soc_npu.v").read_text()
    for mod in ("pilot_top", "aer_fifo", "tmr_voter", "soc_npu_ser"):
        assert re.search(r"^\s+" + mod + r"\s+", npu, re.M), (
            "soc_npu.v no longer instantiates {}; this test's transitive "
            "list is stale".format(mod))
        for name, text in flows.items():
            assert re.search(r"\b" + mod + r"\b", text), (
                "hw/soc/flow/{} does not read {}.v, which "
                "hw/soc/rtl/soc_npu.v instantiates".format(name, mod))


def test_the_verdict_rule_is_one_file_and_not_two_copies_of_one():
    """`flow/sta_ibex.sh`'s header states the rule at length -- every
    check reported is also judged, the verdict names its own scope,
    there is no bare pass token -- and docs/45 needed the same rule for
    a second design. Two copies of a verdict rule that must agree and
    that nothing compares is the defect docs/44 section 5.4 refused for
    a parity matrix, one level up. So the rule lives in
    flow/sta_verdict.awk and both flows call it."""
    rule = (SOC_FLOW / "sta_verdict.awk").read_text()
    assert "ALL_CHECKS_MET" in rule and "NOT_MET" in rule
    for name in ("sta_ibex.sh", "sta_soc_top.sh"):
        text = (SOC_FLOW / name).read_text()
        assert "sta_verdict.awk" in text, (
            "hw/soc/flow/{} does not use the shared verdict "
            "rule".format(name))
        assert "ALL_CHECKS_MET" not in text.split("# ---", 1)[-1] or \
            "-f \"$SOC_DIR/flow/sta_verdict.awk\"" in text, (
            "hw/soc/flow/{} looks like it has grown its own copy of the "
            "verdict rule".format(name))


@needs_yosys
def test_the_whole_soc_elaborates_as_one_design(workdir):
    """The thing that had never been done. `hierarchy -check -top
    soc_top` over the whole source list -- Ibex, the fabric, both
    memories, every peripheral -- and it must resolve every reference.

    It runs with the memory BLACKBOXED, which is what makes it a test
    rather than an overnight job: soc_top.v's two soc_mem instances are
    16,384 and 2,048 words of behavioural register array, and deriving
    them is most of the elaboration time. The blackbox has soc_mem's
    ports, so an unresolved reference anywhere else still fails.

    What this does NOT check: it does not synthesise, so it says nothing
    about area, timing, or what the optimiser does. docs/45 is the
    measurement; this is the guard that the design still elaborates as
    one design."""
    gen = ROOT / "hw" / "soc" / "gen"
    if not gen.is_dir() or not list(gen.glob("*.v")):
        pytest.skip("hw/soc/gen is empty: run flow/sv2v_ibex.sh first")
    genp = ROOT / "hw" / "soc" / "genp" / "ibex_top.v"
    if not genp.is_file():
        pytest.skip("hw/soc/genp/ibex_top.v is absent: run a SoC flow first")

    bb = Path(workdir) / "soc_mem_bb.v"
    real = _soc_mem_ports()
    decls = ",\n".join(
        "  {} wire {} {}".format(d, w, n) for d, w, n in real)
    # THE PARAMETER LIST IS DERIVED FROM soc_mem.v AND NOT WRITTEN HERE.
    # It used to be four literal lines, and docs/50 found what that costs:
    # soc_top.v gained `.RDREG(MEM_RDREG)` on both memory instances and
    # this blackbox did not follow, so the elaboration this test performs
    # failed with "does not have a parameter named 'RDREG'" -- a stale
    # fifth copy of a list that four other files already have to agree on.
    # An empty default of the right shape is enough for a blackbox: the
    # test elaborates, it does not simulate.
    params = ",\n".join(
        "                 parameter {} = 0".format(n)
        for n in _soc_mem_params())
    bb.write_text(
        "module soc_mem #(\n" + params + ") (\n"
        + decls + "\n);\nendmodule\n")

    ibex = [p for p in sorted(gen.glob("*.v"))
            if p.name not in ("ibex_register_file_ff.v", "ibex_top.v")]
    ibex.append(genp)
    soc = [SOC_RTL / n for n in (
        "prim_clock_gating.v", "ibex_regfile_secded.v", "soc_bus.v",
        "soc_apb_bridge.v", "soc_uart.v", "soc_gpio.v", "soc_qspi.v", "soc_pnp.v",
        "soc_apb_pnp.v", "soc_clint.v", "soc_gptimer.v", "soc_wdog.v",
        "soc_busstat.v", "soc_scrub.v", "soc_boot.v", "soc_tmr_bank.v", "soc_npu.v",
        "soc_npu_ser.v")]
    # This list is a FIFTH copy of the four the flow-list guard below
    # checks, and docs/65 found it the way docs/57 found the other four:
    # soc_gpio.v was added to every flow and this test still failed,
    # because nothing checks this list against soc_top.v. It is kept
    # explicit rather than derived so that the guard cannot pass on a
    # list generated from the file it is guarding; the price is that a
    # new peripheral is a one-line edit here as well.
    # THE FROZEN PILOT IS PART OF THE DESIGN AS OF docs/51. soc_npu.v
    # instantiates hw/rtl/pilot_top.v unmodified, so this elaboration
    # reads it and the four blocks it is built from out of the directory
    # docs/34 pins by blob hash. They are READ here exactly as
    # hw/soc/flow/sim_soc.sh reads them and are never written.
    soc += [PILOT_RTL / n for n in
            ("tmr_voter.v", "secded_enc.v", "secded_dec.v",
             "pilot_top.v", "lif_core.v", "aer_fifo.v", "scrub.v")]

    # hw/soc/rtl/prim_clock_gating.v binds a real PDK cell, so the
    # library has to supply sg13g2_lgcp_1's interface exactly as the
    # flow's `read_liberty -lib` does. When the PDK is not installed a
    # one-cell declaration stands in, so this check does not silently
    # skip on a machine without it.
    lib = _sg13g2_liberty()
    if lib is not None:
        prelude = "read_liberty -lib {};".format(lib)
    else:
        icg = Path(workdir) / "sg13g2_lgcp_1.v"
        icg.write_text("module sg13g2_lgcp_1 (input CLK, input GATE,\n"
                       "                      output GCLK);\nendmodule\n")
        prelude = "read_verilog -lib {};".format(icg)

    script = (
        prelude
        + " read_verilog -lib {};".format(bb)
        + " read_verilog -defer -I {} -I {} {};".format(
            SOC_RTL, PILOT_RTL,
            " ".join(str(p) for p in ibex + soc + [SOC_RTL / "soc_top.v"]))
        + " hierarchy -check -top soc_top;")
    out = _run_yosys(script, workdir)
    assert "soc_top" in out


# =====================================================================
# 6. the memories, the reset gate, and the place-and-route flow
#
# docs/47-soc-place-and-route.md is the first time anything under
# hw/soc/ was placed and routed. It brought three things into the tree
# that can silently stop being true, and each of them is silent in a
# different way:
#
#   * hw/soc/rtl/soc_mem_sram.v is a DROP-IN for soc_mem.v. A port it
#     gets wrong in WIDTH does not stop elaboration -- the same failure
#     mode section 5 guards for the two generated boundary models.
#   * hw/soc/rtl/soc_bus.v's request gate. Reverting it to `rst_ni &&`
#     costs 2.49 ns and 8.8 MHz pre-layout and NOTHING functional; no
#     cocotb test, no formal job and no fault-injection campaign in this
#     repository would notice.
#   * hw/soc/pnr/config.json's checker keys. Every one of them exists
#     because a checker in its shipped configuration examines less than
#     a reader assumes, and a run with them missing looks exactly like a
#     run with them present and passing. docs/28 4.4 and 4.4a, docs/34
#     8.5, docs/36, docs/23.
#
# WHAT THIS SECTION DOES NOT COVER: it reads files. It does not place,
# route or time anything, and it is not a substitute for
# hw/openlane/checker_audit.py, which recomputes from the installed
# LibreLane's own step classes whether a checker can in fact fail. This
# section asserts the configuration is present; that script asserts it
# BINDS.
# =====================================================================
SOC_PNR = ROOT / "hw" / "soc" / "pnr"


def test_the_sram_memory_declares_soc_mems_ports():
    """hw/soc/rtl/soc_mem_sram.v declares a module called `soc_mem` and
    is read INSTEAD OF soc_mem.v by the place-and-route flow and by
    SOC_MEM=sram. Exactly one of the two files may be in any build, so
    nothing ever compares them at elaboration; if soc_mem.v grows,
    loses, renames or re-widens a port and this file does not follow,
    the layout is of a different design from the simulation.

    Ports only, in name, width, direction and ORDER. The two files are
    NOT functionally equivalent and soc_mem_sram.v's header says so at
    length -- no contents, no ECC, different read-during-write -- so a
    test asserting more than the interface would assert something
    neither file claims."""
    real = _soc_mem_ports()
    text = (SOC_RTL / "soc_mem_sram.v").read_text()
    body = text.split("module soc_mem", 1)[1]
    body = body.split(") (", 1)[1].split(");", 1)[0]
    got = []
    for m in re.finditer(
            r"\b(input|output)\s+(?:wire|reg)?\s*(\[[^\]]*\])?\s*(\w+)",
            body):
        got.append((m.group(1),
                    re.sub(r"\s+", "", m.group(2) or ""),
                    m.group(3)))
    assert got == real, (
        "hw/soc/rtl/soc_mem_sram.v no longer declares soc_mem.v's "
        "ports.\n  soc_mem.v:      {}\n  soc_mem_sram.v: {}".format(
            real, got))


def test_the_fabric_does_not_gate_its_request_path_with_the_reset_net():
    """The regression guard for docs/47 section 5, and the one thing in
    this file that would cost frequency rather than correctness.

    docs/45 section 7.2 measured what `wire can_issue_i = rst_ni && ...`
    does at the top level: it puts rst_sys_n -- 2,766 flip-flop reset
    pins, the largest net in the SoC -- into a purely COMBINATIONAL
    datapath, and the worst synchronous setup path became worse
    (-60.6191 ns at the slow corner) than the worst asynchronous
    recovery path (-53.3681). Replacing it with a locally registered
    `issue_en` moved the synchronous group to +4.3006 on the identical
    memory model and moved the closing period from 18.20 ns to 15.71 ns.

    Nothing functional would catch a revert. The behaviour of
    `issue_en` is strictly more conservative than `rst_ni` -- the fabric
    stays closed one extra cycle after reset release -- so every cocotb
    test, every formal property and every fault-injection campaign
    passes either way."""
    text = (SOC_RTL / "soc_bus.v").read_text()
    body = re.sub(r"//[^\n]*", "", text)
    for m in re.finditer(r"wire\s+can_issue_[id]\s*=\s*(\w+)", body):
        assert m.group(1) == "issue_en", (
            "hw/soc/rtl/soc_bus.v gates its request path with '{}' "
            "rather than the locally registered issue_en. docs/47 "
            "section 5 measured what that costs.".format(m.group(1)))
    assert re.search(r"reg\s+issue_en\b", body), (
        "hw/soc/rtl/soc_bus.v no longer declares issue_en")
    assert len(re.findall(r"wire\s+can_issue_[id]\s*=", body)) == 2, (
        "hw/soc/rtl/soc_bus.v no longer has exactly two can_issue gates; "
        "this guard needs updating rather than deleting")


def _pnr_config():
    return json.loads((SOC_PNR / "config.json").read_text())


def test_the_pnr_flow_binds_every_timing_checker_to_every_corner():
    """The four keys of docs/28 section 4.4a, docs/34 section 8.5 and
    docs/36, asserted in the configuration before a run rather than
    audited after one.

    Two DIFFERENT mechanisms, and the second is the one that catches
    people out. SETUP_VIOLATION_CORNERS has no default, so unset it
    falls through to the PDK's TIMING_VIOLATION_CORNERS = ['*typ*'] and
    the slow corner is gated by nothing. MAX_CAP_VIOLATION_CORNERS and
    MAX_SLEW_VIOLATION_CORNERS take corner_override = [''] from their
    step classes, which is truthy, so they NEVER consult
    TIMING_VIOLATION_CORNERS at all and raising that key is inert; the
    [''] then filters to an empty wildcard list and the checkers warn
    instead of failing."""
    cfg = _pnr_config()
    for key in ("SETUP_VIOLATION_CORNERS", "HOLD_VIOLATION_CORNERS",
                "MAX_CAP_VIOLATION_CORNERS", "MAX_SLEW_VIOLATION_CORNERS"):
        assert cfg.get(key) == ["*"], (
            "hw/soc/pnr/config.json: {} is {!r}, not ['*']".format(
                key, cfg.get(key)))


def test_the_pnr_flow_writes_the_derate_as_a_float():
    """docs/28 section 4.4: the PDK ships TIME_DERATING_CONSTRAINT as
    the integer 5 and LibreLane's base.sdc computes the derate with Tcl
    integer division, so `expr 5 / 100` is 0 and the flow applies NO
    derate while logging '5%'. The written SDC then contains no
    set_timing_derate line at all, and the cost measured on the pilot
    was 0.9910 ns of slack.

    `5` and `5.0` are the same number in JSON's data model and not in
    this flow's, so the test is on the TYPE."""
    cfg = _pnr_config()
    v = cfg.get("TIME_DERATING_CONSTRAINT")
    assert isinstance(v, float) and v == 5.0, (
        "hw/soc/pnr/config.json: TIME_DERATING_CONSTRAINT is {!r} of "
        "type {}; it must be the float 5.0".format(v, type(v).__name__))
    raw = (SOC_PNR / "config.json").read_text()
    assert re.search(r'"TIME_DERATING_CONSTRAINT"\s*:\s*5\.0', raw), (
        "the JSON text does not spell the derate 5.0, so a reader "
        "auditing the file cannot see the thing that matters")


def test_every_macro_instance_the_pnr_config_places_exists_in_the_rtl():
    """hw/soc/pnr/config.json names each of the six SRAM macro
    instances by its full hierarchical path and gives it a location and
    an orientation. OpenROAD.CheckMacroInstances catches a name that is
    absent, but only after synthesis, and a name that is PRESENT and
    wrong -- the ROM's two macros swapped, say -- is caught by nothing
    at all.

    The instance paths are a property of soc_mem_sram.v: `u_ram` and
    `u_rom` are soc_top.v's instance names, the middle component is the
    generate block label, and the leaf is the macro instance. That is
    why the generate branches in soc_mem_sram.v are three independent
    `if`s and not an if/else-if chain -- an `else if` would nest the
    ROM inside an anonymous `genblk1` whose name the tool invents."""
    cfg = _pnr_config()
    sram = (SOC_RTL / "soc_mem_sram.v").read_text()
    top = (SOC_RTL / "soc_top.v").read_text()

    placed = {}
    for macro, spec in cfg["MACROS"].items():
        for inst in spec["instances"]:
            placed[inst] = macro
    assert len(placed) == 6, "expected six macro instances, got {}".format(
        sorted(placed))

    for inst, macro in placed.items():
        parts = inst.split(".")
        assert len(parts) == 3, (
            "{!r} is not <soc_top instance>.<generate label>.<macro "
            "instance>".format(inst))
        outer, block, leaf = parts
        assert re.search(r"\bsoc_mem\b[^;]*?\b" + re.escape(outer) + r"\b",
                         top, re.S), (
            "soc_top.v has no soc_mem instance called {!r}".format(outer))
        assert "begin : " + block in sram, (
            "soc_mem_sram.v has no generate block labelled "
            "{!r}".format(block))
        body = sram.split("begin : " + block, 1)[1].split("\n  end", 1)[0]
        assert re.search(re.escape(macro) + r"\s+" + re.escape(leaf) + r"\b",
                         body), (
            "soc_mem_sram.v's {} block does not instantiate {} as "
            "{}".format(block, macro, leaf))


def test_the_macro_blackboxes_declare_the_pdk_models_ports():
    """The two _bb.v files in hw/soc/pnr/ exist because Verilator.Lint
    runs before synthesis and cannot find a module it has no source
    for, and because the PDK's own behavioural model instantiates a
    core module from a second file. They are transcribed from the PDK
    models by machine.

    This test SKIPS without the PDK rather than passing, because a
    check that cannot see the thing it compares against is not a check.
    Same rule the rest of this file follows for yosys."""
    pdk = Path(os.environ.get("PDK_ROOT", Path.home() / ".ciel")) / \
        "ihp-sg13g2" / "libs.ref" / "sg13g2_sram" / "verilog"
    if not pdk.is_dir():
        pytest.skip("the ihp-sg13g2 PDK is not installed")

    cfg = _pnr_config()
    for macro in cfg["MACROS"]:
        bb = SOC_PNR / "{}_bb.v".format(macro)
        assert bb.is_file(), "missing blackbox {}".format(bb)
        model = pdk / "{}.v".format(macro)
        assert model.is_file(), "missing PDK model {}".format(model)

        def decls(text):
            head = text.split("module " + macro, 1)[1]
            head = head.split("`ifdef", 1)[0].split("endmodule", 1)[0]
            return re.findall(
                r"\b(input|output)\s*(\[[^\]]*\])?\s*(\w+)\s*;", head)

        want = [(d, re.sub(r"\s+", "", w or ""), n)
                for d, w, n in decls(model.read_text())]
        got = [(d, re.sub(r"\s+", "", w or ""), n)
               for d, w, n in decls(bb.read_text())]
        assert want and got == want, (
            "hw/soc/pnr/{}_bb.v does not declare the PDK model's "
            "ports.\n  pdk: {}\n  bb:  {}".format(macro, want, got))


def test_the_pnr_flow_cannot_write_into_the_frozen_pilot():
    """docs/34 pins the TTIHP26b submission by blob hash and the
    shuttle closes 2026-09-21. This is a check on the SCRIPT rather
    than on a run: pnr_soc_top.sh must keep its config and its run
    directories outside hw/openlane/, and must say so in a way that
    fails rather than in a comment."""
    text = (SOC_FLOW / "pnr_soc_top.sh").read_text()
    assert "hw/openlane" in text and "refusing" in text, (
        "hw/soc/flow/pnr_soc_top.sh no longer refuses to run inside "
        "the frozen hw/openlane/")
    assert 'PNR=$SOC_DIR/pnr' in text, (
        "hw/soc/flow/pnr_soc_top.sh no longer keeps its config under "
        "hw/soc/pnr/")
    cfg_dir = str(SOC_PNR.resolve())
    assert "hw/openlane" not in cfg_dir


def test_the_pnr_flow_supplies_only_the_source_list():
    """pnr_soc_top.sh merges VERILOG_FILES into a resolved copy of
    config.json, because flow/ibex_sources.sh is the one place that
    knows which of hw/soc/gen/ibex_register_file_ff.v and
    hw/soc/rtl/ibex_regfile_secded.v belongs in a build. docs/34
    section 8.5's trap was a generator that silently deleted a
    hand-added fix from a config, so the generator here asserts that
    VERILOG_FILES is the only key it touches -- and this test asserts
    the assertion is still in the script."""
    text = (SOC_FLOW / "pnr_soc_top.sh").read_text()
    assert 'assert added == {"VERILOG_FILES"}' in text, (
        "pnr_soc_top.sh no longer asserts it added only VERILOG_FILES")
    assert "assert not changed" in text, (
        "pnr_soc_top.sh no longer asserts it changed no existing key")
    assert "VERILOG_FILES" not in _pnr_config(), (
        "hw/soc/pnr/config.json carries VERILOG_FILES; the script "
        "supplies it and would now be overriding a hand-written list")


# =====================================================================
# 7. the floorplan generator
#
# docs/48-soc-floorplan-and-drive.md measured a second and a third
# floorplan against docs/47's, and hw/soc/pnr/floorplan.py is what
# emitted them. It replaces a hand-edited config.json for a reason that
# is a property of the tool rather than a preference: LibreLane's
# `-c KEY=VALUE` inserts the value as a STRING and re-parses it with
# permissive typing, so a list arrives split on its commas and a
# dictionary cannot be passed at all. A floorplan variant is therefore
# a whole config file, and a generator that writes whole config files
# is a generator that can quietly change a key nobody looked at.
#
# Three things are guarded and each is silent in its own way:
#
#   * THE GENERATOR REPRODUCES docs/47's FLOORPLAN. At --channel 700.08
#     --density 40 it must emit config.json byte for byte, from the
#     PDK's LEF rather than from a transcription. If it stops doing
#     that, every comparison in docs/48 is between two floorplans
#     rather than between one floorplan and its own variant.
#   * SITE ALIGNMENT. docs/47 section 6.1 established that the core box
#     is an integer number of 0.48 um sites and 3.78 um rows and every
#     macro origin likewise. Losing it does not fail the flow; it makes
#     OpenROAD.CutRows start off-grid.
#   * pnr_soc_top.sh's REFUSAL. PNR_CONFIG selects the variant, and an
#     arbitrary path would walk around the refusal that keeps this
#     script out of the frozen hw/openlane/.
#
# WHAT THIS SECTION DOES NOT COVER: it does not place anything. A
# floorplan that is site-aligned, halo-clear and inside the core can
# still be a bad floorplan, and docs/48 measures two that are.
# =====================================================================


def _floorplan_py(*args):
    """Run hw/soc/pnr/floorplan.py, skipping if the PDK is not
    installed -- the macro dimensions are READ from the LEF, and a test
    that cannot see what it reads is not a check."""
    pdk_root = os.environ.get("PDK_ROOT", os.path.expanduser("~/.ciel"))
    lef = (Path(pdk_root) / "ihp-sg13g2" / "libs.ref" / "sg13g2_sram" /
           "lef" / "RM_IHPSG13_1P_2048x64_c2_bm_bist.lef")
    if not lef.exists():
        pytest.skip("ihp-sg13g2 PDK not installed at {}".format(pdk_root))
    env = dict(os.environ, PDK_ROOT=pdk_root)
    return subprocess.run(
        [sys.executable, str(SOC_PNR / "floorplan.py"), *args],
        capture_output=True, text=True, env=env)


def test_the_floorplan_generator_reproduces_the_hardened_floorplan():
    """hw/soc/pnr/floorplan.py --channel 700.08 --density 40 must emit
    hw/soc/pnr/config.json exactly, apart from the provenance note it
    adds. That is the whole argument that docs/48's floorplans differ
    from docs/47's in the floorplan and in nothing else: the generator
    computes docs/47's die, core box, six macro origins and two
    orientations from the PDK's LEF SIZE statements, without being told
    what they should come out as."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "cfg.json"
        r = _floorplan_py("--channel", "700.08", "--density", "40",
                          "--write", str(out))
        assert r.returncode == 0, r.stderr
        got = json.loads(out.read_text())
    note = got.pop("//floorplan48", None)
    assert note is not None, "the generator no longer records its provenance"
    assert got == _pnr_config(), (
        "hw/soc/pnr/floorplan.py no longer reproduces config.json at "
        "the channel height docs/47 hardened. Every floorplan "
        "comparison in docs/48 rests on it doing so.")


def test_the_floorplan_generator_keeps_the_core_on_the_site_grid():
    """docs/47 section 6.1: the core box is an integer number of sites
    and rows and every macro origin is too. The generator asserts it and
    this test asserts the assertion fires, by asking for a channel
    height that is NOT on the admissible 0.78 + 3.78k grid and checking
    that the tool snaps it and says so rather than emitting an off-grid
    floorplan."""
    r = _floorplan_py("--channel", "500.00")
    assert r.returncode == 0, r.stderr
    assert "snapped" in r.stdout, (
        "hw/soc/pnr/floorplan.py accepted an off-grid channel height "
        "without snapping it")
    m = re.search(r"channel\s+([\d.]+) um", r.stdout)
    assert m, r.stdout
    channel = float(m.group(1))
    assert abs(((channel - 0.78) / 3.78) - round((channel - 0.78) / 3.78)) < 1e-6, (
        "hw/soc/pnr/floorplan.py emitted a channel of {} um, which does "
        "not put the upper macro row on a row boundary".format(channel))


def test_the_pnr_flow_refuses_a_config_outside_its_own_directory():
    """PNR_CONFIG selects a floorplan variant. The refusal that keeps
    hw/soc/flow/pnr_soc_top.sh out of the frozen hw/openlane/ is a check
    on the CONFIG DIRECTORY, so a PNR_CONFIG pointing anywhere else
    would walk around it. The script must refuse."""
    text = (SOC_FLOW / "pnr_soc_top.sh").read_text()
    assert "PNR_CONFIG" in text, (
        "hw/soc/flow/pnr_soc_top.sh no longer accepts PNR_CONFIG")
    assert 'refusing: PNR_CONFIG must be under' in text, (
        "hw/soc/flow/pnr_soc_top.sh no longer refuses a PNR_CONFIG "
        "outside hw/soc/pnr/, which is the refusal that keeps it out "
        "of the frozen hw/openlane/")
    r = subprocess.run(
        ["bash", str(SOC_FLOW / "pnr_soc_top.sh"), "guardtest"],
        capture_output=True, text=True,
        env=dict(os.environ, PNR_CONFIG="/etc/hostname"))
    assert r.returncode != 0, (
        "hw/soc/flow/pnr_soc_top.sh accepted a PNR_CONFIG outside "
        "hw/soc/pnr/")
    # The script checks its toolchain BEFORE it checks PNR_CONFIG, so on
    # a machine without the rootless shims it exits non-zero for the
    # wrong reason and this test would pass without having tested
    # anything. That is what it did on a GitHub runner on 2026-09-10:
    # "missing shims at /home/runner/.local/opt/llbin". Assert the
    # refusal is the one we asked for, and skip where it cannot be
    # reached -- a green result for the wrong reason is worse than a
    # skip that says why.
    if "missing shims" in (r.stdout + r.stderr):
        pytest.skip("the flow's toolchain check fires first on this "
                    "machine, so the PNR_CONFIG refusal is unreachable "
                    "here: " + (r.stdout + r.stderr).strip().splitlines()[0])
    assert "refusing" in (r.stderr + r.stdout)


# =====================================================================
# 8. the CLINT's time base, docs/58 H6
#
# A different shape of guard from every one above it, and the difference
# is worth stating rather than glossing. Sections 1 to 7 guard
# DELIBERATELY REDUNDANT logic -- three banks that store the same word,
# which is exactly what a synthesiser is built to collapse into one. H6
# is not redundant: mtime's eight check bits are the input to a decoder
# whose output feeds real flip-flops, so no structural pass can merge
# them away. What CAN happen here is the opposite failure, and it is
# recorded honestly below: the census counts the same 171 flip-flops for
# a corrector, for a detector, and for a codec wired the wrong way
# round. Only the fault-injection campaign can tell those apart, and
# `test_the_census_cannot_tell_a_corrector_from_a_detector` measures
# that rather than asserting it -- which is `docs/43` section 9.4's
# lesson pointed at this file.
# =====================================================================
CLINT = SOC_RTL / "soc_clint.v"
SECDED_ENC = PILOT_RTL / "secded_enc.v"
SECDED_DEC = PILOT_RTL / "secded_dec.v"

CLINT_SOURCES = [CLINT, SECDED_ENC, SECDED_DEC]


def _clint_geometry():
    """soc_clint's flip-flop budget at TICK_DIV = 1, DERIVED.

    Every width is read out of the register declarations rather than
    written here, so a width change moves the expectation with it. Three
    facts the arithmetic needs and the file states:

      * `tick_cnt` is 32 flip-flops of prescaler that are DEAD at
        TICK_DIV = 1 -- `tick` is the constant 1 and nothing assigns
        the counter -- so the optimiser removes it. That is why
        `docs/40` section 9 measured 163 and not 195, and it is stated
        in soc_clint.v's H6 section.
      * the check field's width comes from secded_enc.v's CHECK_W, which
        an elaboration guard in that file fixes at 8. It is read from
        there rather than from the CLINT, because the CLINT does not
        name it.
      * the response registers -- rdata_o, rvalid_o, err_o -- are
        declared as `output reg` and are flip-flops like any other.
    """
    text = CLINT.read_text()

    def width(name):
        m = re.search(r"(?:output\s+)?reg\s*(?:\[\s*(\d+)\s*:\s*(\d+)\s*\])?"
                      r"\s*" + name + r"\s*[;,]", text)
        assert m, "no reg declaration for {} in soc_clint.v".format(name)
        if m.group(1) is None:
            return 1
        return int(m.group(1)) - int(m.group(2)) + 1

    live = ("mtime_q", "mtimecmp", "msip", "rdata_o", "rvalid_o", "err_o")
    base = sum(width(n) for n in live)

    m = re.search(r"parameter\s+DATA_W\s*=\s*(\d+)", SECDED_ENC.read_text())
    assert m, "secded_enc.v no longer declares DATA_W"
    assert int(m.group(1)) == width("mtime_q"), (
        "secded_enc.v is fixed at {} data bits and mtime is {}; the codec "
        "cannot cover the counter".format(m.group(1), width("mtime_q")))
    chk = width("mtime_chk_q")
    m = re.search(r"parameter\s+CHECK_W\s*=\s*(\d+)", SECDED_ENC.read_text())
    assert m and int(m.group(1)) == chk, (
        "soc_clint.v holds {} check bits and secded_enc.v produces {}"
        .format(chk, m.group(1) if m else "?"))
    return base, chk


CLINT_BASE_FF, CLINT_CHK_FF = _clint_geometry()


def _clint_script(sources, chparam="", mtime_only=False):
    """The recipe hw/soc/flow/syn_soc.sh runs, restricted to the CLINT.

    Restricted deliberately: syn_soc.sh reads every SoC block and then
    selects one as the top, and its own header records that this makes
    `soc_clint` 29.3328 um2 and 5 cells BIGGER than reading the CLINT
    alone. That effect is real and `docs/45` section 4.3 measures it;
    what it means here is that this file's counts are counts of the
    CLINT and the numbers in `docs/58` section 7 are the flow's, and the
    two are not interchangeable. FLIP-FLOP counts are unaffected, which
    is why this file counts flip-flops.
    """
    lib = _sg13g2_liberty()
    script = ("read_verilog -I {} {};".format(
        SOC_RTL, " ".join(str(s) for s in sources)))
    if chparam:
        script += " chparam {} soc_clint;".format(chparam)
    script += (" hierarchy -check -top soc_clint;"
               " synth -flatten -top soc_clint; opt -purge;")
    if lib is not None:
        script += " dfflibmap -liberty {0}; opt; abc -liberty {0};".format(lib)
    script += " flatten; setundef -zero; opt_clean -purge;"
    return script


def _clint_mutant(workdir, name, replacements):
    dst = Path(workdir) / name
    dst.mkdir(exist_ok=True)
    out = []
    hit = 0
    for src in CLINT_SOURCES:
        text = src.read_text()
        for old, new in replacements:
            if old in text:
                hit += text.count(old)
                text = text.replace(old, new)
        target = dst / src.name
        target.write_text(text)
        out.append(target)
    assert hit, "mutation {} matched nothing; soc_clint.v moved".format(name)
    return out


@needs_yosys
def test_the_mtime_codeword_survives_synthesis(workdir):
    """H6's eight check flip-flops are in the artifact.

    They are the whole of the added state: 8 flip-flops where tripling
    mtime and mtimecmp would have added 256, which is the trade
    `docs/58` section 4 argues and section 7 prices."""
    census = _census(_clint_script(CLINT_SOURCES), workdir)
    expected = CLINT_BASE_FF + CLINT_CHK_FF
    assert census.total == expected, (
        "expected {} flip-flops of architectural and response state plus "
        "{} check bits = {}, found {}".format(
            CLINT_BASE_FF, CLINT_CHK_FF, expected, census.total))


@needs_yosys
def test_harden_zero_removes_the_check_bits_and_nothing_else(workdir):
    """The baseline `docs/58` section 7 measures against, and the proof
    that the guard above can fail.

    `docs/41` section 6.5's rule: the baseline has to come from the SAME
    source list and the SAME recipe, or the hardening is credited with
    whatever else changed. Here the source list does not move at all --
    secded_enc.v and secded_dec.v are read in both configurations and
    simply have no instance at HARDEN = 0."""
    census = _census(
        _clint_script(CLINT_SOURCES, chparam="-set HARDEN 0"), workdir)
    assert census.total == CLINT_BASE_FF, (
        "the unhardened CLINT should hold {} flip-flops, found {}".format(
            CLINT_BASE_FF, census.total))


@needs_yosys
def test_the_codec_is_in_the_mapped_netlist_and_not_only_in_the_rtl(workdir):
    """Both cones, by instance path, after the post-mapping flatten.

    Reported and not merely counted, because the ENCODER is the half a
    reader would expect to disappear: its output goes to eight
    flip-flops whose only consumer is the decoder, and a pass that could
    prove the inductive invariant `chk == encode(mtime)` would be
    entitled to delete the pair. Nothing in this flow can prove a
    sequential invariant, so nothing does -- but that is a property of
    the tool and this is the measurement that says it held."""
    census = _census(_clint_script(CLINT_SOURCES), workdir)
    enc = census.in_instance("u_mtime_enc")
    dec = census.in_instance("u_mtime_dec")
    # Neither codec has any state of its own -- both modules are purely
    # combinational -- so the FLIP-FLOP count under them is zero by
    # construction and counting it would prove nothing.
    assert enc == 0 and dec == 0, (
        "secded_enc and secded_dec are combinational; a flip-flop under "
        "one of them means the module changed: enc={} dec={}".format(
            enc, dec))
    # What is asserted is that the cones are there at all.
    assert census.from_file("secded_enc.v") == 0
    assert census.cells > 0
    text = (Path(workdir) / "census.json").read_text()
    assert "u_mtime_enc" in text, (
        "no cell in the mapped netlist lies under u_mtime_enc: the "
        "encoder was optimised away")
    assert "u_mtime_dec" in text, (
        "no cell in the mapped netlist lies under u_mtime_dec: the "
        "decoder was optimised away")


@needs_yosys
def test_the_census_cannot_tell_a_corrector_from_a_detector(workdir):
    """WHAT THIS FILE DOES NOT COVER, measured rather than claimed.

    `docs/43` section 9.4 found all twenty formal tasks green on a
    design whose three banks the synthesiser had collapsed into one, and
    concluded that formal cannot see what only the census can. This is
    the mirror of that sentence and it belongs in the census's own file:
    the mutation below turns H6 from a CORRECTOR into a DETECTOR -- the
    syndrome is still computed and still announced on mt_ecc_o, but the
    counter ticks from the STORED value instead of the corrected one, so
    an upset is reported and then kept for ever. It is the detect-only
    design `docs/58` section 4 prices and rejects.

    It costs the same flip-flops, and this test asserts that it does.
    The check that fails on it is
    `hw/soc/tb/cocotb/test_soc_clint_fi.py`, whose 128 mtime draws go
    from 128 CORRECTED to 0."""
    detector = _clint_mutant(workdir, "clint_detect_only", [
        ("wire [63:0] mtime_ticked = tick ? (mtime + 64'd1) : mtime;",
         "wire [63:0] mtime_ticked = tick ? (mtime_q + 64'd1) : mtime_q;"),
        ("wr_mtimeh ? wmerge(mtime[63:32], be_i, wdata_i) "
         ": mtime_ticked[63:32],",
         "wr_mtimeh ? wmerge(mtime_q[63:32], be_i, wdata_i) "
         ": mtime_ticked[63:32],"),
        ("wr_mtimel ? wmerge(mtime[31:0], be_i, wdata_i)  "
         ": mtime_ticked[31:0]};",
         "wr_mtimel ? wmerge(mtime_q[31:0], be_i, wdata_i)  "
         ": mtime_ticked[31:0]};"),
    ])
    census = _census(_clint_script(detector), workdir)
    assert census.total == CLINT_BASE_FF + CLINT_CHK_FF, (
        "the detect-only mutation changed the flip-flop count, so this "
        "test is no longer measuring what it says it measures: {} "
        "against {}".format(census.total, CLINT_BASE_FF + CLINT_CHK_FF))


def test_nothing_in_the_design_instantiates_the_clint_unhardened():
    """The same rule the watchdog's HARDEN carries. A parameter that can
    turn a defence off is a parameter someone turns off, and the only
    thing standing between that and silicon is this test."""
    text = CLINT.read_text()
    assert re.search(r"parameter\s+integer\s+HARDEN\s*=\s*1", text), (
        "soc_clint.v's HARDEN parameter no longer defaults to 1")
    top = (SOC_RTL / "soc_top.v").read_text()
    m = re.search(r"soc_clint\s*#\((.*?)\)\s*u_clint", top, re.S)
    assert m, "soc_top.v no longer instantiates soc_clint with parameters"
    assert "HARDEN" not in m.group(1), (
        "soc_top.v overrides soc_clint's HARDEN parameter. Nothing in "
        "the design may: HARDEN = 0 is the unprotected counter.")


def test_the_clint_corrects_on_every_path_that_reads_the_counter():
    """Textual, and complementary to the census rather than a weaker
    version of it.

    The census proves the check bits and the two cones EXIST. This
    proves they are wired the way round that corrects: `mtime` -- the
    decoder's output -- is what ticks, what the comparator sees and what
    a bus read returns, and `mtime_next` -- the value about to be
    stored -- is what the encoder covers. Both of the wrong-way-round
    edits are functionally identical in a fault-free machine, so every
    cocotb test outside the campaign, every property in
    soc_clint_props.v and every count in this file would pass on them:

      * encode over `mtime_q` instead of `mtime_next` and the code
        follows the corruption into consistency, so the upset is never
        seen and never repaired;
      * tick from `mtime_q` instead of `mtime` and the block detects
        without correcting.

    The second is measured in
    `test_the_census_cannot_tell_a_corrector_from_a_detector`.
    """
    text = CLINT.read_text()
    assert ".data_in   (mtime_next)" in text, (
        "soc_clint.v's encoder no longer covers the value about to be "
        "stored")
    assert ".code_in  ({mtime_chk_q, mtime_q})" in text, (
        "soc_clint.v's decoder no longer reads the stored codeword")
    assert ".data_out (mtime)" in text
    # The three consumers, each reading the CORRECTED wire.
    for pat in ("assign irq_timer_o    = (mtime >= mtimecmp);",
                "wire [63:0] mtime_ticked = tick ? (mtime + 64'd1) : mtime;",
                "REG_MTIMEL:    rdata_o <= mtime[31:0];",
                "REG_MTIMEH:    rdata_o <= mtime[63:32];"):
        assert pat in text, (
            "a consumer of the counter in soc_clint.v no longer reads the "
            "corrected value: {}".format(pat))
    # And the raw register reaches NOTHING except the codec and its own
    # next-state assignment. Anything else is a path the correction does
    # not cover.
    allowed = (
        "reg [63:0] mtime_q;",
        "  reg [63:0] mtime_q;",
        ".code_in  ({mtime_chk_q, mtime_q}),",
        "      mtime_q     <= 64'd0;",
        "      mtime_q     <= mtime_next;",
        "    assign mtime          = mtime_q;",
    )
    for line in text.splitlines():
        if "mtime_q" not in line:
            continue
        stripped = line.split("//")[0].rstrip()
        if not stripped.strip():
            continue
        assert stripped.strip() in [a.strip() for a in allowed], (
            "mtime_q -- the RAW, possibly corrupt register -- is read "
            "somewhere the correction does not cover:\n  {}".format(
                stripped.strip()))


# =====================================================================
# 9. The memory codec and the scrubber, docs/67
#
# hw/soc/rtl/soc_mem_ecc.v under hw/soc/rtl/soc_mem_sram.v, with the
# six macros as blackboxes: the census the whole-SoC synthesis cannot
# give, because the flattened netlist loses every instance path but the
# macros'. The scope is the RAM wrapper alone at WORDS = 8192 -- the
# arm the design instantiates -- and the ROM wrapper at WORDS = 2048.
# =====================================================================
MEM_ECC = SOC_RTL / "soc_mem_ecc.v"
MEM_SRAM = SOC_RTL / "soc_mem_sram.v"
MEM_BB = [SOC_PNR / "RM_IHPSG13_1P_2048x64_c2_bm_bist_bb.v",
          SOC_PNR / "RM_IHPSG13_1P_1024x32_c2_bm_bist_bb.v",
          SOC_PNR / "RM_IHPSG13_1P_512x16_c2_bm_bist_bb.v"]
MEM_SOURCES = [MEM_ECC, MEM_SRAM, SECDED_ENC, SECDED_DEC]


def _mem_script(sources, words, harden, ro, ecc_byte):
    """The recipe hw/soc/flow/syn_soc.sh runs, restricted to the memory
    wrapper with the macros read as blackboxes, the way
    flow/syn_soc_top.sh reads them at SOC_MEM=sram."""
    lib = _sg13g2_liberty()
    script = "".join("read_verilog -lib {}; ".format(b) for b in MEM_BB)
    script += " read_verilog -I {} -I {} {};".format(
        SOC_RTL, PILOT_RTL, " ".join(str(s) for s in sources))
    script += (" chparam -set WORDS {} -set HARDEN {} -set RO {} "
               "-set ECC_BYTE {} soc_mem;".format(words, harden, ro, ecc_byte))
    script += " hierarchy -top soc_mem; synth -top soc_mem -flatten;"
    if lib is not None:
        script += " dfflibmap -liberty {0}; abc -liberty {0};".format(lib)
    script += " attrmap -modattr -remove keep_hierarchy; flatten; opt_clean;"
    return script


def _mem_geometry(words, ecc_byte):
    """The wrapper's flip-flop budget at HARDEN = 1, DERIVED from the RTL:

      soc_mem_ecc   rv0, er0, rd0        3   (er0 is a constant at RO = 0
                                              and is removed, so 2)
                    row_q                AW
                    sptr, stick, srd_q   AW + 16 + 1
      the wrapper   bank_q               2 (RAM) or 1 + half_q (ROM)
    """
    aw = int(math.log2(words))
    ecc = 2 + aw + aw + 16 + 1      # rv0, rd0, row_q, sptr, stick, srd_q
    if ecc_byte:
        return ecc, 2               # bank_q[1:0]
    return ecc + 1, 2               # er0 is live at RO = 1; bank_q, half_q


def _mem_census(workdir, tag, **kw):
    return _census(_mem_script(MEM_SOURCES, **kw), workdir)


@needs_yosys
def test_the_ram_codec_and_scrubber_survive_synthesis(workdir):
    """The RAM wrapper at the design's parameters: the scrubber's state
    and the response registers are in the netlist, and BOTH codec cones
    -- four encoders and four decoders by instance path -- are there
    after the post-mapping flatten. The encoder is the half a reader
    would expect to disappear (docs/58 section 9.4's argument, one
    memory over); nothing in this flow proves the sequential invariant
    that would license deleting it, and this is the measurement that
    says it held."""
    census = _mem_census(workdir, "ram", words=8192, harden=1, ro=0, ecc_byte=1)
    ecc, wrap = _mem_geometry(8192, True)
    assert census.total == ecc + wrap, (
        "expected {} flip-flops of codec state plus {} of wrapper state, "
        "found {}".format(ecc, wrap, census.total))
    text = (Path(workdir) / "census.json").read_text()
    for lane in range(4):
        for inst in ("g_enc_byte.g_lane[%d].u_enc" % lane,
                     "g_dec_byte.g_lane[%d].u_dec" % lane):
            assert inst in text, (
                "no cell in the mapped netlist lies under {}: a codec cone "
                "was optimised away".format(inst))
    assert "g_scrub" in text, "the scrubber left no cell in the netlist"


@needs_yosys
def test_the_rom_codec_and_scrubber_survive_synthesis(workdir):
    """The ROM wrapper: one encoder, one decoder, four macros, and the
    scrubber's state -- with er0 live, because a write to a ROM is
    answered with err."""
    census = _mem_census(workdir, "rom", words=2048, harden=1, ro=1, ecc_byte=0)
    ecc, wrap = _mem_geometry(2048, False)
    assert census.total == ecc + wrap, (
        "expected {} + {} flip-flops, found {}".format(ecc, wrap, census.total))
    text = (Path(workdir) / "census.json").read_text()
    assert "g_enc_word.u_enc" in text and "g_dec_word.u_dec" in text
    for leaf in ("u_b0", "u_b1", "u_c0", "u_c1"):
        assert "g_rom_1024x32_ecc." + leaf in text, (
            "the ROM's {} macro is not in the netlist".format(leaf))


@needs_yosys
def test_harden_zero_removes_the_codec_and_the_scrubber_and_nothing_else(workdir):
    """The baseline docs/67 measures the codec against: the SAME files
    with HARDEN = 0 hold one word per row in the same four macros with no
    code and no scrubber -- the response registers and the bank select
    and nothing more. docs/41 section 6.5's rule, and the proof that the
    two guards above can fail."""
    census = _mem_census(workdir, "ram0", words=8192, harden=0, ro=0, ecc_byte=1)
    # rv0, row_q (evt_addr_o still reports the last row at HARDEN = 0,
    # so the register that feeds it is live), bank_q[1:0]; rd0 and er0
    # feed nothing and are removed.
    aw = int(math.log2(8192))
    assert census.total == 1 + aw + 2, (
        "the unhardened RAM wrapper should hold {} flip-flops, found "
        "{}".format(1 + aw + 2, census.total))
    text = (Path(workdir) / "census.json").read_text()
    assert "u_enc" not in text and "u_dec" not in text and "g_scrub" not in text


@needs_yosys
def test_docs47s_arm_is_still_the_wrapper_it_was(workdir):
    """WORDS = 16384 at HARDEN = 0 is the mapping docs/47 through docs/66
    hardened -- two words per row, a half select, no codec -- and
    hw/soc/pnr/config.json still names its instances. It has to keep
    elaborating, with its four macros and its five flip-flops (rv0,
    er0 is constant, bank_q[1:0], half_q), because the day it does not
    is the day docs/47's floorplan can no longer be reproduced."""
    census = _mem_census(workdir, "docs47", words=16384, harden=0, ro=0, ecc_byte=1)
    assert census.total == 4, (
        "docs/47's RAM wrapper should hold 4 flip-flops, found {}".format(
            census.total))
    text = (Path(workdir) / "census.json").read_text()
    for leaf in ("u_b0", "u_b1", "u_b2", "u_b3"):
        assert "g_ram_2048x64." + leaf in text


@needs_yosys
def test_the_census_cannot_tell_a_corrector_from_a_launderer(workdir):
    """WHAT THIS FILE DOES NOT COVER, measured rather than claimed, in
    the shape docs/58 section 9.4 established for the CLINT.

    The mutation below makes the scrubber write back the RAW row instead
    of the corrected one: the syndrome is re-encoded into a valid
    codeword over the wrong value, and the memory becomes soc_clint.v
    H6's "ECC counter that silently does nothing" -- an upset is
    corrected on every read until the scrubber reaches it, and then it
    is made permanent. It costs the same flip-flops and the same cones,
    and this test asserts that it does. The check that fails on it is
    hw/soc/tb/cocotb/mutate_soc_mem.py's `wb_raw`, in the suite, and
    sw/tests/test_soc_memory_guards.py, in the text."""
    dst = Path(workdir) / "mem_wb_raw"
    dst.mkdir(exist_ok=True)
    mutated = []
    for src in MEM_SOURCES:
        text = src.read_text()
        if src == MEM_ECC:
            old = "  wire [31:0] enc_in = req_i ? wdata_i : rd_word;"
            assert old in text
            text = text.replace(
                old, "  wire [31:0] enc_in = req_i ? wdata_i : row_dout_i[31:0];")
        target = dst / src.name
        target.write_text(text)
        mutated.append(target)
    census = _census(_mem_script(mutated, words=8192, harden=1, ro=0, ecc_byte=1),
                     workdir)
    ecc, wrap = _mem_geometry(8192, True)
    assert census.total == ecc + wrap, (
        "the launderer mutation changed the flip-flop count, so this test "
        "is no longer measuring what it says it measures")


def test_the_pnr_macro_blackboxes_cover_the_shipped_wrapper():
    """Three blackboxes for three macro types, and every type the RTL
    instantiates in any arm has one, or synthesis at SOC_MEM=sram and the
    JSON header of the layout die on an unknown module."""
    sram = MEM_SRAM.read_text()
    used = set(re.findall(r"\b(RM_IHPSG13_1P_\w+_bm_bist)\s+u_", sram))
    have = {b.name[:-len("_bb.v")] for b in MEM_BB}
    assert used == have, (
        "the wrapper instantiates {} but hw/soc/pnr/ has blackboxes for "
        "{}".format(sorted(used), sorted(have)))
    flow = (SOC_FLOW / "syn_soc_top.sh").read_text()
    for name in have:
        assert name + "_bb.v" in flow, (
            "flow/syn_soc_top.sh does not read {}_bb.v at SOC_MEM=sram".format(name))


# =====================================================================
# 9. the boot block's decision word, docs/69
# =====================================================================
#
# `soc_boot.v`'s B1 triples eighteen bits and leaves seventy-four alone,
# and this section is the only check in the repository that looks at
# whether the three replicas are three replicas in the netlist. Every
# functional test, the whole of hw/soc/formal/soc_boot.sby and all 572
# injections of hw/soc/tb/cocotb/test_soc_boot_fi.py would pass on a
# netlist in which yosys had hashed the three banks into one -- docs/43
# section 9.4 found exactly that on a design where twenty formal tasks
# stayed green -- because every one of them works against the RTL,
# where the replicas exist whatever the mapper did with them.
BOOT_RTL_FILE = SOC_RTL / "soc_boot.v"

BOOT_SOURCES = [
    BOOT_RTL_FILE,
    SOC_RTL / "soc_tmr_bank.v",
    PILOT_RTL / "tmr_voter.v",
]

BOOT_REPLICAS = ("g_prot_tmr.u_prot_a.",
                 "g_prot_tmr.u_prot_b.",
                 "g_prot_tmr.u_prot_c.")


def _boot_geometry():
    """soc_boot's flip-flop budget, DERIVED from its own parameters.

    The field list is written out here on purpose, exactly as
    `_geometry()` does for the watchdog: it is the specification of what
    B1 protects, and if a field is added to the word without a line
    appearing here the counts stop agreeing. The two widths that move it
    are parameters of the module and are read out of it.
    """
    text = BOOT_RTL_FILE.read_text()

    def p(name):
        m = re.search(r"parameter\s+integer\s+" + name + r"\s*=\s*(\d+)", text)
        assert m, "no integer parameter {} in soc_boot.v".format(name)
        return int(m.group(1))

    nstrap = p("NSTRAP")
    cnt_w = p("CNT_W")
    tmc_w = 4

    # The decision word: everything written once per power cycle or
    # maintained by hardware, and `sys_q`, which the campaign moved in.
    decision = (2          # dly
                + 1        # valid_q
                + nstrap   # strap_q
                + 1        # wdis_q
                + 1        # armed_q
                + 1        # sys_q
                + cnt_w)   # cnt_q

    # The report B1 added. Counted separately because it is the part of
    # the word that only EXISTS when there is redundancy to report on:
    # at HARDEN = 0 the banked width drops to the decision bits, so
    # these five are not dead flip-flops the optimiser has to notice --
    # they are never instantiated. docs/41 section 6.5's rule applied to
    # the baseline's flip-flop count rather than to its area.
    report = 1 + tmc_w

    # Deliberately unprotected, B1's second list.
    unprot = 2 * nstrap + 2 + 32 + 32   # sync0/1, wsync0/1, brpt, epoch

    return decision, report, unprot


BOOT_DEC_W, BOOT_REPORT_FF, BOOT_UNPROT_FF = _boot_geometry()
BOOT_PROT_W = BOOT_DEC_W + BOOT_REPORT_FF


def _boot_script(sources, force_flatten=False, chparam=""):
    lib = _sg13g2_liberty()
    script = "read_verilog -I {} {};".format(
        SOC_RTL, " ".join(str(s) for s in sources))
    script += " hierarchy -top soc_boot;"
    if chparam:
        script += " " + chparam
    if force_flatten:
        script += " attrmap -modattr -remove keep_hierarchy;"
    script += " synth -top soc_boot -flatten;"
    if lib is not None:
        script += " dfflibmap -liberty {0}; abc -liberty {0};".format(lib)
    script += " attrmap -modattr -remove keep_hierarchy; flatten; opt_clean;"
    return script


def _boot_sources_without_any_attribute(workdir):
    dst = Path(workdir) / "boot_noattr"
    dst.mkdir(exist_ok=True)
    out = []
    for src in BOOT_SOURCES:
        text = src.read_text()
        for attr in _ATTRS:
            text = text.replace(attr, "")
        target = dst / src.name
        target.write_text(text)
        out.append(target)
    return out


@pytest.fixture(scope="module")
def boot_asic(workdir):
    return _census(_boot_script(BOOT_SOURCES), workdir)


@needs_yosys
def test_the_boot_decision_word_is_three_banks_in_the_netlist(boot_asic):
    found = {r: boot_asic.in_instance(r) for r in BOOT_REPLICAS}
    assert all(v == BOOT_PROT_W for v in found.values()), (
        "the boot block's decision word collapsed in the netlist: "
        "expected {} flip-flops per replica, found {}. Three replicas "
        "written from the same expression are one bank after opt_dff + "
        "opt_merge, and the voter above them then votes three copies of "
        "the same upset value. Total flip-flops in this netlist: "
        "{}.".format(BOOT_PROT_W, found, boot_asic.total))


@needs_yosys
def test_the_boot_flip_flop_budget_is_the_unprotected_state_plus_three(
        boot_asic):
    """The total, against the two numbers B1 is a decision about: what
    is protected, three times, plus what is deliberately not."""
    expected = BOOT_UNPROT_FF + 3 * BOOT_PROT_W
    assert boot_asic.total == expected, (
        "soc_boot mapped to {} flip-flops, expected {} = {} unprotected "
        "(the two synchronisers, the report and the epoch) + 3 x {} "
        "protected".format(boot_asic.total, expected, BOOT_UNPROT_FF,
                           BOOT_PROT_W))


@needs_yosys
def test_the_boot_word_survives_every_attribute_being_deleted(workdir):
    """The POL/MIX storage transform on its own, with `keep` and
    `keep_hierarchy` deleted from the TEXT of the sources so that no
    pass can honour them and none can re-derive them.

    A total and not a per-replica census, and that is forced rather than
    chosen: with keep_hierarchy deleted the banks are flattened during
    `synth` and the instance path they would be counted by no longer
    exists."""
    census = _census(
        _boot_script(_boot_sources_without_any_attribute(workdir),
                     force_flatten=True),
        workdir)
    expected = BOOT_UNPROT_FF + 3 * BOOT_PROT_W
    assert census.total == expected, (
        "with every keep and keep_hierarchy deleted from the text, "
        "soc_boot mapped to {} flip-flops instead of {}. Something in "
        "this block is held together by an attribute alone, and an "
        "attribute is not portable to a front end that does not read "
        "yosys's.".format(census.total, expected))


@needs_yosys
def test_boot_harden_zero_is_exactly_the_block_docs_68_shipped(workdir):
    """`HARDEN = 0` is the baseline docs/69 section 7 prices B1 against,
    and this is the check that it IS that baseline.

    It has to hold the decision bits ONCE and hold the report NOT AT
    ALL, which comes to 92 flip-flops -- the number docs/68 section 9.1
    measured for the block before any of this. That the two agree is
    what makes the area delta a measurement of B1 rather than of B1 plus
    whatever else the refactor changed, and it is stronger than the
    watchdog's version of the same check: soc_wdog.v leaves its report
    fields in the bank at HARDEN = 0 and RELIES on the optimiser
    noticing they are constant (docs/41 section 6.3's 53 rather than
    58), whereas soc_boot.v narrows the banked width so they are never
    instantiated. docs/55's own HARDEN = 0 measurement is the record of
    that reliance not holding for a third block."""
    census = _census(
        _boot_script(BOOT_SOURCES, chparam="chparam -set HARDEN 0 soc_boot;"),
        workdir)
    expected = BOOT_UNPROT_FF + BOOT_DEC_W
    assert census.total == expected, (
        "HARDEN = 0 should leave one plain bank of the decision bits "
        "only: {} unprotected + {} decision = {} flip-flops, found "
        "{}".format(BOOT_UNPROT_FF, BOOT_DEC_W, expected, census.total))
    assert expected == 92, (
        "the HARDEN = 0 configuration is {} flip-flops and docs/68 "
        "section 9.1 measured the unprotected block at 92. The baseline "
        "the area delta is quoted against has stopped being the block "
        "that document shipped.".format(expected))
    for r in BOOT_REPLICAS:
        assert census.in_instance(r) == 0


@needs_yosys
def test_removing_the_mix_transform_from_one_boot_replica_collapses_it(
        workdir):
    """A guard that cannot fail is not a guard.

    With MIX off, a replica stores `v_i ^ POL[i]` -- one of the only two
    storage functions a single bit has -- so on every bit where POL_C is
    zero replica C stores exactly what replica A stores and structural
    hashing merges the pair. `.MIX(0)` is functionally IDENTICAL RTL,
    bit for bit at every port, so this mutation is invisible to every
    simulation, every proof and the whole fault-injection campaign. Only
    the census sees it."""
    dst = Path(workdir) / "boot_mix0"
    dst.mkdir(exist_ok=True)
    sources = []
    hit = 0
    for src in BOOT_SOURCES:
        text = src.read_text()
        old = ".POL(POL_C), .MIX(1))"
        if old in text:
            hit += text.count(old)
            text = text.replace(old, ".POL(POL_C), .MIX(0))")
        for attr in _ATTRS:
            text = text.replace(attr, "")
        target = dst / src.name
        target.write_text(text)
        sources.append(target)
    assert hit == 1, "the replica C instantiation moved in soc_boot.v"

    census = _census(_boot_script(sources, force_flatten=True), workdir)
    base = BOOT_UNPROT_FF + 3 * BOOT_PROT_W
    # POL_C is 0xAAAA..., zero on every EVEN bit, and those are the bits
    # on which replica C would then store what replica A stores.
    merged = sum(1 for i in range(BOOT_PROT_W) if (0xAAAA_AAAA >> i) & 1 == 0)
    assert census.total == base - merged, (
        "turning MIX off on replica C left {} flip-flops; expected {} = "
        "{} minus the {} even bits on which POL_C is zero and C "
        "therefore stores exactly what A stores. If nothing was lost, "
        "this file is not measuring the anti-merge transform.".format(
            census.total, base - merged, base, merged))


@needs_yosys
def test_the_boot_block_instantiates_the_frozen_voter_and_three_banks():
    """A second, TEXTUAL check on the same thing, because the census
    cannot see a change of parameters at the instance: three replicas
    given the same POL and MIX would census as three banks under
    keep_hierarchy and collapse without it. docs/41 section 6.6 lists
    that gap and pairs the same two checks for the watchdog."""
    boot = BOOT_RTL_FILE.read_text()
    assert "tmr_voter #(.WIDTH(PBANK_W)) u_prot_vote" in boot
    banks = re.findall(
        r"soc_tmr_bank\s*#\(\.W\(PBANK_W\),\s*\.RST_VAL\(64'd0\),"
        r"\s*\.POL\((POL_[ABC])\),\s*\.MIX\((\d)\)\)", boot)
    assert len(banks) == 3, (
        "soc_boot.v instantiates {} soc_tmr_bank replicas, expected "
        "three".format(len(banks)))
    assert len(set(banks)) == 3, (
        "two of the boot block's replicas have the same (POL, MIX): {}. "
        "They would present the same stored function to opt_merge and "
        "hash away.".format(banks))
    assert ("POL_A", "0") in banks
    assert ("POL_B", "1") in banks and ("POL_C", "1") in banks
    assert "POL_B = 64'h5555555555555555" in boot
    assert "POL_C = 64'hAAAAAAAAAAAAAAAA" in boot


def test_nothing_in_the_design_instantiates_the_boot_block_unhardened():
    """`HARDEN` exists to be measured against, not to be shipped at
    zero. soc_top.v must not set it and no flow may override it."""
    top = (SOC_RTL / "soc_top.v").read_text()
    m = re.search(r"soc_boot\s*#\((.*?)\)\s*u_boot", top, re.S)
    assert m, "soc_top.v no longer instantiates soc_boot as u_boot"
    assert "HARDEN" not in m.group(1), (
        "soc_top.v sets soc_boot's HARDEN parameter; that parameter is a "
        "measurement knob and the design ships at its default of 1")
    for name in ("sim_soc.sh", "syn_soc_top.sh", "pnr_soc_top.sh"):
        text = (SOC_FLOW / name).read_text()
        assert "soc_boot.HARDEN" not in text, (
            "{} overrides soc_boot's HARDEN".format(name))


# ---------------------------------------------------------------------
# Every P&R configuration must declare every vendor macro the RTL builds
# ---------------------------------------------------------------------

def _macros_the_rtl_instantiates():
    """Vendor macro module names instantiated anywhere in the RTL.

    A vendor macro is instantiated by bare module name at the start of a
    line, which is what this matches. It is deliberately not a full
    Verilog parse: the names are distinctive (RM_/RSC_IHPSG13) and a
    parser here would be a second thing to keep right.
    """
    names = set()
    for d in (SOC_RTL, ROOT / "hw" / "rtl"):
        for v in sorted(d.glob("*.v")):
            for m in re.finditer(r"^\s+((?:RM|RSC)_IHPSG13[A-Za-z0-9_]*)\s",
                                 v.read_text(), re.M):
                names.add(m.group(1))
    return names


def test_every_pnr_config_declares_every_macro_the_rtl_instantiates():
    """The defect that stopped the default place-and-route flow for
    seven days without anybody finding out.

    `hw/soc/rtl/soc_mem_sram.v` gained two
    RM_IHPSG13_1P_512x16_c2_bm_bist as the ROM's (39,32) check macros on
    2026-09-05, commit ed51de0. `hw/soc/pnr/config.json` -- the config
    `flow/pnr_soc_top.sh` uses when PNR_CONFIG is unset -- went on
    declaring two macros, so Verilator.Lint failed with two MODMISSING
    errors and the Classic flow quit at stage 3.

    IT WENT UNNOTICED FOR 56 RUNS, and the reason is the interesting
    part: every documented invocation passes `-F Yosys.JsonHeader`,
    which starts the flow at step 5 and skips the lint step and its
    three checkers. Of the 56 soc_top run trees, three have a
    `01-verilator-lint` directory, and the one that predates this test
    linted cleanly on 2026-09-01 -- four days before the macros existed.
    A stage that is skipped by every caller is a stage that can rot
    silently, and this is what it rotted into.

    WHAT THIS CHECKS AND WHAT IT DOES NOT. It checks DECLARATION, not
    correctness: that every macro the RTL instantiates has an entry, not
    that the entry points at the right GDS or the right Liberty views. A
    config may also declare macros the RTL does not instantiate, which
    costs nothing -- an unused blackbox is an unused blackbox -- so that
    direction is not an error here.
    """
    wanted = _macros_the_rtl_instantiates()
    assert wanted, (
        "no vendor macro instantiation found in the RTL at all. Either "
        "the memories stopped using\nthem or this test's pattern has "
        "stopped matching; either way it is guarding nothing.")

    # EXPERIMENT RECORDS, not live configurations. Each of these was
    # written for one measurement, ran once against the netlist of its
    # day, and is kept so that measurement can be re-read -- docs/64's
    # rule. Bringing them forward would change what they record and
    # settle nothing, because none of them will be run again.
    #
    # Every one is a `rom0` configuration: it hardens a netlist that does
    # not instantiate the ROM's check macros, so two macros is the RIGHT
    # number for it and adding a third would be the actual error.
    #
    # A config is listed here with the document it belongs to. Anything
    # NOT listed is live and must be complete.
    RECORDS = {
        "config-npu.json": "docs/55's accelerator arm, 2026-09-04",
        "config-synpre.json": "docs/49 and docs/62's SYNPRE arm, 2026-09-04",
        "config-lvs-a-asconfigured.json": "docs/79's LVS arm A, 2026-09-09",
        "config-lvs-b-blackbox.json": "docs/79's LVS arm B, 2026-09-09",
        "config-lvs-c-ignorecells.json": "docs/79's LVS arm C, 2026-09-09",
        "config-lvs-d-delimiters.json": "docs/79's LVS arm D, 2026-09-09",
        "config-lvs-e-normalised.json": "docs/79's LVS arm E, 2026-09-10",
        "config-lvs-f-equateclasses.json": "docs/79's LVS arm F, 2026-09-10",
    }

    tracked = _tracked_pnr_configs()

    missing = {}
    for cfg in sorted((ROOT / "hw" / "soc" / "pnr").glob("config*.json")):
        if cfg.name == "config.resolved.json":
            continue          # a resolved snapshot, not a hand-edited config
        if cfg.name not in tracked:
            continue          # local scratch; it is nobody's contract
        if cfg.name in RECORDS:
            continue
        try:
            declared = set((json.loads(cfg.read_text()).get("MACROS")
                            or {}).keys())
        except ValueError:
            continue
        if not declared:
            continue          # a config that hardens no macro at all
        gap = wanted - declared
        if gap:
            missing[cfg.name] = sorted(gap)

    # The other direction: a name in RECORDS that no longer exists is a
    # hole, and one that has SINCE been completed is a record somebody
    # brought forward -- both need a person, not a silent pass.
    stale = sorted(n for n in RECORDS
                   if not (ROOT / "hw" / "soc" / "pnr" / n).is_file())
    assert not stale, (
        "these configurations are listed as experiment records and no "
        "longer exist: {}.\nDelete the entry with the file, or restore "
        "the file.".format(", ".join(stale)))

    assert not missing, (
        "these place-and-route configurations do not declare every vendor "
        "macro the RTL\ninstantiates, so Verilator.Lint fails with "
        "MODMISSING and the flow quits at stage 3:\n\n  {}\n\nThe RTL "
        "instantiates: {}\n\nThis is only invisible while every caller "
        "passes -F to start past the lint step.".format(
            "\n  ".join(f"{k}: missing {', '.join(v)}"
                        for k, v in sorted(missing.items())),
            ", ".join(sorted(wanted))))


def _sg13g2_tech_lef():
    pattern = (".ciel/ciel/ihp-sg13g2/versions/*/ihp-sg13g2/libs.ref/"
               "sg13g2_stdcell/lef/sg13g2_tech.lef")
    lefs = sorted(Path.home().glob(pattern))
    return lefs[-1] if lefs else None


# The seven cut layers the detailed router announces it is NOT checking.
# Read off hw/soc/pnr/runs/s83romecc5/38-openroad-detailedrouting, and
# identically in every soc_top run since docs/47.
DRT_0349_LAYERS = {"Cont", "Via1", "Via2", "Via3", "Via4",
                   "TopVia1", "TopVia2"}


def test_the_router_skips_every_enclosure_rule_this_pdk_declares():
    """`[DRT-0349] LEF58_ENCLOSURE with no CUTCLASS is not supported.
    Skipping for layer X` -- seven times, in every detailed-routing log
    this repository has ever produced. docs/67 records it as the PDK's
    rather than the design's, and it is: sg13g2_tech.lef states plain LEF
    `ENCLOSURE` on all seven cut layers and qualifies none of them with
    `CUTCLASS`, so OpenROAD's router declines all seven.

    The point of a guard here is NOT to make the router check them --
    nothing in this repository can. It is that the caveat stops being
    true the moment the PDK adds a CUTCLASS, and a caveat that has
    silently stopped being true is worse than no caveat: every layout
    result in the corpus is stated with this exclusion attached. So this
    reads the PDK and fails when the premise moves, which is the stage
    that can actually satisfy it.

    A note on the parse: PREFERENCLOSURE contains ENCLOSURE as a
    substring and is a different rule. Matching the substring would have
    made this pass for the wrong reason."""
    lef = _sg13g2_tech_lef()
    if lef is None:
        pytest.skip("sg13g2_tech.lef not installed")

    # Only TOP-LEVEL layer definitions count. A VIA definition also
    # contains `LAYER Metal1 ;` followed by its own ENCLOSURE, indented;
    # matching those attributed enclosure rules to seven metal layers
    # that have no cut rules at all and made this guard fail for a reason
    # that had nothing to do with its subject.
    layer, is_cut, declared, qualified = None, False, {}, set()
    for line in lef.read_text(errors="ignore").split("\n"):
        m = re.match(r"^LAYER\s+(\S+)", line)           # column 0, not indented
        if m:
            layer, is_cut = m.group(1), False
            continue
        if re.match(r"^\s*TYPE\s+CUT\b", line):
            is_cut = True
            continue
        if is_cut and re.match(r"^\s*ENCLOSURE\b", line):   # not PREFERENCLOSURE
            declared.setdefault(layer, 0)
            declared[layer] += 1
            if "CUTCLASS" in line:
                qualified.add(layer)

    unchecked = set(declared) - qualified
    assert unchecked == DRT_0349_LAYERS, (
        "the set of cut layers whose ENCLOSURE the router will skip has "
        "moved: expected {}, found {}. Every layout result in this corpus "
        "is stated with that exclusion attached -- re-read docs/67 before "
        "changing this set.".format(
            sorted(DRT_0349_LAYERS), sorted(unchecked)))
    assert not qualified, (
        "{} now carries CUTCLASS, so the router no longer skips it and "
        "the corpus-wide caveat is narrower than it was".format(
            sorted(qualified)))
    # And the rules really are declared -- a PDK that dropped ENCLOSURE
    # altogether would also make `unchecked` empty, which is a different
    # world and must not read as this one.
    assert sum(declared.values()) >= len(DRT_0349_LAYERS), (
        "the PDK declares fewer ENCLOSURE statements than it has cut "
        "layers; this guard's premise no longer holds")


def _tracked_pnr_configs():
    """The P&R configs a CHECKOUT carries, usable where there is no git.

    docs/78 section 4 states the principle for the SPDX check and it
    applies to every guard: "a generated tree is a plain directory until
    it is committed, and a check that cannot run there is a check that
    does not run where it is most needed". The public mirror is exactly
    that tree, and `git ls-files` raises there rather than answering.

    Falling back to "everything present" is correct rather than lax: the
    mirror is BUILT from `git ls-files`, so in a non-git tree every
    config on disk is by construction a tracked one. In a git tree the
    fallback is never taken and untracked scratch is still excluded.
    """
    import subprocess as _sp
    cfg_dir = ROOT / "hw" / "soc" / "pnr"
    on_disk = {p.name for p in cfg_dir.glob("config*.json")}
    try:
        out = _sp.run(["git", "ls-files", "hw/soc/pnr/config*.json"],
                      cwd=ROOT, check=True, capture_output=True,
                      text=True).stdout.split()
    except (OSError, _sp.CalledProcessError):
        return on_disk           # not a git tree; see the docstring
    names = {pathlib.PurePosixPath(t).name for t in out}
    return names if names else on_disk
