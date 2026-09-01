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

import json
import math
import os
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
TMR_VOTER_PINNED_BLOB = "62b5f4d2a1ea"


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

    # Deliberately unprotected, W6's second list.
    # Deliberately unprotected, W6's second list plus W8's down-counter.
    unprot = width + width + pre_w + kick_w  # reload, counter, pre,
                                             # kick_left

    return prot_w, report, unprot


PROT_W, REPORT_FF, UNPROT_FF = _geometry()

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
        self.by_instance = []
        for mod in design["modules"].values():
            for cell_name, cell in mod["cells"].items():
                if not _is_flop(cell["type"]):
                    continue
                self.total += 1
                self.by_instance.append(cell_name)

    def in_instance(self, needle):
        return sum(1 for n in self.by_instance if needle in n)


def _census(script_body, workdir):
    out = Path(workdir) / "census.json"
    _run_yosys(script_body + " write_json {};".format(out), workdir)
    return Census(json.loads(out.read_text()))


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
    expected = UNPROT_FF + 3 * PROT_W
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
    assert ecp5_noattr.total == UNPROT_FF + 3 * PROT_W


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
    expected = UNPROT_FF + 3 * PROT_W
    assert asic.total == expected, (
        "soc_wdog mapped to {} flip-flops, expected {} = {} unprotected "
        "(reload + counter + pre) + 3 x {} protected. If the protected "
        "word grew or shrank, _geometry() in this file has to grow or "
        "shrink with it -- that is the point of it being derived.".format(
            asic.total, expected, UNPROT_FF, PROT_W))


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
    intact = UNPROT_FF + 3 * PROT_W
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
    expected = UNPROT_FF + PROT_W - REPORT_FF
    assert census.total == expected, (
        "HARDEN = 0 should leave one plain bank: {} unprotected + {} "
        "protected - {} report (the mismatch flag and counter have "
        "nothing to report on and are correctly optimised away) = {} "
        "flip-flops, found {}".format(
            UNPROT_FF, PROT_W, REPORT_FF, expected, census.total))
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
BUSSTAT_NSRC = 4


def _busstat_cnt_w():
    """CNT_W read out of the module header, not written down here."""
    m = re.search(r"parameter\s+integer\s+CNT_W\s*=\s*(\d+)",
                  BUSSTAT.read_text())
    assert m, "soc_busstat.v no longer declares CNT_W"
    return int(m.group(1))


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
                ".tmr_ev_i (wdog_tmr_ev)"):
        assert pat in top, (
            "soc_top.v no longer connects a fault line: {}".format(pat))
    assert "rf_ecc_err_i (3'b0" not in top and "tmr_ev_i (1'b0" not in top, \
        "a fault line in soc_top.v has been tied off"


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
    for name in ("soc_gptimer.v", "soc_top.v"):
        body = (SOC_RTL / name).read_text()
        assert ".HARDEN" not in body, (
            "{} overrides soc_wdog's HARDEN parameter. Nothing in the "
            "design may: HARDEN = 0 is the unprotected block.".format(name))


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
    bb.write_text(
        "module soc_mem #(parameter integer WORDS = 4096,\n"
        "                 parameter RO = 1'b0,\n"
        "                 parameter INIT_FILE = \"\",\n"
        "                 parameter integer INIT_WORD = 0) (\n"
        + decls + "\n);\nendmodule\n")

    ibex = [p for p in sorted(gen.glob("*.v"))
            if p.name not in ("ibex_register_file_ff.v", "ibex_top.v")]
    ibex.append(genp)
    soc = [SOC_RTL / n for n in (
        "prim_clock_gating.v", "ibex_regfile_secded.v", "soc_bus.v",
        "soc_apb_bridge.v", "soc_uart.v", "soc_pnp.v", "soc_apb_pnp.v",
        "soc_clint.v", "soc_gptimer.v", "soc_wdog.v", "soc_busstat.v",
        "soc_tmr_bank.v")]
    soc += [PILOT_RTL / n for n in
            ("tmr_voter.v", "secded_enc.v", "secded_dec.v")]

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
        + " read_verilog -defer -I {} {};".format(
            SOC_RTL,
            " ".join(str(p) for p in ibex + soc + [SOC_RTL / "soc_top.v"]))
        + " hierarchy -check -top soc_top;")
    out = _run_yosys(script, workdir)
    assert "soc_top" in out
