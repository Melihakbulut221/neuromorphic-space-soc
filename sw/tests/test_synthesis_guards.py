"""Synthesis guards: structures whose FUNCTION is to exist physically must
survive synthesis, and only the netlist can say whether they did.

Why this file exists
--------------------
Until 2026-08-26 the configuration TMR domain of hw/rtl/pilot_top.v was
three `reg [54:0]` vectors written from the same expression on the same
cycle. yosys `opt_dff` normalised the three into identical enable
flip-flops and `opt_merge` then hashed them into one bank, so the voter
read a single physical register three times. The netlist that fed the
4x2 harden -- tt/runs/tt-harden/06-yosys-synthesis/ -- carries 362
references to `cfg_a[` and none at all to `cfg_b[` or `cfg_c[`.

The docs/16 fault-injection campaign injects at RTL level, where the
three vectors are still distinct signals, and reported the configuration
TMR as 15/15 CORRECTED. That measurement was true of the RTL and false
of the netlist. RTL simulation is structurally incapable of seeing a
structure that synthesis deletes, which is the gap these tests close.

Two traps this file is written to avoid
---------------------------------------
1. Never assert on a signal NAME. Marking the three replicas `(* keep *)`
   was measured on this design to leave the flip-flop count unchanged at
   1045 while filling the netlist with 110 references of the form
   `assign \\u_pilot.cfg_b[3] = \\u_pilot.cfg_a[3] ;` -- the wire name
   survives, the storage does not. Every assertion below counts
   flip-flop CELLS.
2. Never assert only on the structure that was fixed. A merge hazard is
   generic, so test_no_flip_flops_are_lost_to_optimisation compares the
   whole design's flip-flop population before and after optimisation and
   fails on ANY new loss, wherever it appears.
3. Never leave a bound where the design is already sitting on it. Added
   2026-08-27. The keep_hierarchy-stripped test used to allow one bank's
   worth of loss, and the design lost exactly one bank -- so the test
   passed while the property it was named for, three banks without the
   attribute, was false. A bound that a passing design touches is a
   bound that records the tool's behaviour, not the design's intent.
   That test now allows zero loss, and hw/rtl/pilot_top.v was changed to
   earn it. docs/20 section 11.

Running against a different RTL tree
------------------------------------
Set NSSOC_RTL_DIR to point the whole file at another copy of hw/rtl.
That is how the mutation check is run: restore the pre-fix pilot_top.v
in a scratch tree and confirm these tests fail.
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
RTL = Path(os.environ.get("NSSOC_RTL_DIR", ROOT / "hw" / "rtl"))
TOP = "tt_um_melihakbulut_nssoc"

# Exactly the file set hw/fpga/Makefile and hw/openlane/*/config.json read.
SOURCES = [
    "tt_um_melihakbulut_nssoc.v",
    "pilot_top.v",
    "lif_core.v",
    "aer_fifo.v",
    "tmr_voter.v",
    "secded_enc.v",
    "secded_dec.v",
]

# hw/rtl/pilot_top.v localparam TMR_W: the width of one configuration
# replica, and therefore the flip-flop count each bank must show.
TMR_W = 55
REPLICAS = ("u_cfg_a", "u_cfg_b", "u_cfg_c")

# The second replicated domain: the AER queue pointers of hw/rtl/aer_fifo.v.
#
# docs/16 section 5.2 measured these twelve flip-flops as the highest-rate
# silent corruptor in the design -- 22 of 24 injections corrupted the
# drained event stream with nothing flagged -- and they are now three
# aer_ptr_bank instances per pointer behind a voter. The merge hazard is
# sharper here than in the configuration domain, not softer: all three
# replicas are loaded from ONE net (the voted next pointer), which is
# exactly the signature opt_merge hashes on, so without the per-replica
# storage transform the collapse is not a possibility but the expected
# outcome.
#
# Two queue instances, two pointers each, three replicas each. The width
# is EVQ_*_DEPTH's address width plus the wrap bit: pilot_top defaults
# both queues to 4 entries, so AW = 2 and each bank is 3 flip-flops.
PTR_W = 3
PTR_QUEUES = ("u_evq_in", "u_evq_out")
PTR_BANKS = ("u_wptr_a", "u_wptr_b", "u_wptr_c",
             "u_rptr_a", "u_rptr_b", "u_rptr_c")
PTR_REPLICAS = tuple(f"{q}.{b}" for q in PTR_QUEUES for b in PTR_BANKS)

# The dual-rail valid flags. One bit each, so unlike the banks above
# these carry exactly two rails and not three: over a single bit there
# are only two storage functions, a third replica is bit-for-bit
# identical to one of the other two, and synthesis merges it. That is a
# proof rather than a budget, and it is why this list has an a and a b
# and no c -- see the rail headers in the three files below.
#
# u_rdv is inside aer_fifo, which pilot_top instantiates twice, so the
# read-valid rails appear once per queue and the expected count for
# those two names is two rather than one.
RAIL_W = 1
RAILS = {
    "u_ohv_a": 1,   # pilot_top, show-ahead adapter valid
    "u_ohv_b": 1,
    "u_rdv_a": 2,   # aer_fifo read-valid, one pair per queue instance
    "u_rdv_b": 2,
    "u_op_a": 1,    # lif_core out_pend
    "u_op_b": 1,
}
_RAIL_RTL = ("pilot_top.v", "aer_fifo.v", "lif_core.v")

# Flip-flops the design declares, counted after `proc` and before any
# optimisation pass has run. Asserted rather than hardcoded: the tests
# below measure it every time and compare against the mapped netlist.
# The recorded value is 1161 on 2026-08-26 [fact].

# Flip-flops that legitimately disappear during optimisation: bits that
# are constant or unreachable given this build's parameters (for example
# the top bit of the 11-bit CFG_AXON register, which N_AXONS = 8 pins).
# Measured at 6 both before and after the TMR fix, so the fix restored
# exactly the 110 replica flip-flops and changed nothing else [fact].
# Raising this budget is how a future collapse would be hidden; do not
# raise it without a netlist-level reason recorded next to the change.
DEAD_BIT_BUDGET = 8


# =====================================================================
# tool discovery
# =====================================================================
def _find_yosys():
    on_path = shutil.which("yosys")
    if on_path:
        return on_path
    candidates = [Path.home() / ".local" / "bin" / "yosys"]
    candidates += sorted(Path.home().glob("Downloads/oss-cad-suite*/oss-cad-suite/bin/yosys"))
    candidates += sorted(Path.home().glob("oss-cad-suite/bin/yosys"))
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None


YOSYS = _find_yosys()

needs_yosys = pytest.mark.skipif(YOSYS is None, reason="yosys not available")


def _sg13g2_liberty():
    """The IHP liberty hw/openlane hardens against, when ciel has it."""
    pattern = (".ciel/ciel/ihp-sg13g2/versions/*/ihp-sg13g2/libs.ref/"
               "sg13g2_stdcell/lib/sg13g2_stdcell_typ_1p20V_25C.lib")
    libs = sorted(Path.home().glob(pattern))
    return libs[-1] if libs else None


def _read_sources():
    files = " ".join(str(RTL / name) for name in SOURCES)
    return f"read_verilog -I {RTL} {files};"


def _run_yosys(script, workdir):
    result = subprocess.run(
        [YOSYS, "-p", script], capture_output=True, text=True,
        cwd=workdir, timeout=900)
    assert result.returncode == 0, (
        "yosys failed:\n" + result.stdout[-3000:] + result.stderr[-3000:])
    return result.stdout


# =====================================================================
# netlist census
# =====================================================================
_FF_PREFIXES = ("$_DFF", "$_SDFF", "$_ALDFF", "$_DFFE", "$_SDFFE", "$_DFFSR")


def _is_flop(cell_type):
    if cell_type.startswith(_FF_PREFIXES):
        return True
    if cell_type == "TRELLIS_FF":                    # synth_ecp5
        return True
    if re.match(r"^sg13g2_s?df", cell_type):         # sg13g2 mapped
        return True
    # sky130_fd_sc_hd mapped: dfxtp, dfrtp, dfstp, dfbbn, sdfrtp, edfxbp.
    # The latch family is dl*, so it does not match, and no combinational
    # cell in the library carries a "df".
    if re.match(r"^sky130_fd_sc_hd__[a-z]*df", cell_type):
        return True
    return False


class Census:
    """Flip-flops of one synthesis result, indexed two ways.

    by_instance  cell name -> the hierarchy path yosys baked into it,
                 which is what identifies a replica bank after the
                 post-mapping flatten.
    by_q         the public net each flip-flop drives, which is what
                 identifies a named register. Aliased names make this
                 an undercount, never an overcount, so it is only ever
                 used with >= assertions.
    """

    def __init__(self, design):
        self.total = 0
        self.by_instance = []
        self.by_q = {}
        for mod in design["modules"].values():
            bit_to_name = {}
            for net, info in mod.get("netnames", {}).items():
                if info.get("hide_name"):
                    continue
                for idx, bit in enumerate(info["bits"]):
                    bit_to_name.setdefault(bit, f"{net}[{idx}]")
            for cell_name, cell in mod["cells"].items():
                if not _is_flop(cell["type"]):
                    continue
                self.total += 1
                self.by_instance.append(cell_name)
                q = cell["connections"].get("Q") or cell["connections"].get("q")
                if q:
                    name = bit_to_name.get(q[0])
                    if name:
                        base = re.sub(r"\[\d+\]$", "", name)
                        self.by_q[base] = self.by_q.get(base, 0) + 1

    def in_instance(self, needle):
        return sum(1 for n in self.by_instance if needle in n)

    def under(self, *bases):
        """Flip-flops driving a named register, an ARRAY of that name, or
        any of the given alias spellings.

        Two reasons this is not just ``by_q[name]``:

        * an array becomes one public net per word after ``memory_map``
          (``vmem[0]``, ``vmem[1]``, ...), so its bits are spread over
          several keys rather than sitting under one;
        * yosys names a flip-flop after whichever public net it happens to
          resolve first, and a continuous assignment that taps a register
          makes the tap's name an equally valid answer. ``lif_core.wmem``
          is exactly that case: since the synapse codewords are assembled
          with constant-index taps, the mapped netlist calls those 256
          flip-flops ``w_data_all``. Both spellings name the same storage,
          so both are accepted and the CELL count is what is asserted.
        """
        total = 0
        for key, count in self.by_q.items():
            for base in bases:
                if key == base or key.startswith(base + "["):
                    total += count
                    break
        return total


def _census(script_body, workdir):
    out = Path(workdir) / "census.json"
    _run_yosys(script_body + f" write_json {out};", workdir)
    return Census(json.loads(out.read_text()))


# ---------------------------------------------------------------------
# the three synthesis recipes under test
# ---------------------------------------------------------------------
def _asic_script(force_flatten=False):
    """LibreLane-shaped ASIC synthesis.

    The final `attrmap -modattr -remove keep_hierarchy; flatten` is
    LibreLane's own SYNTH_HIERARCHY_MODE = deferred_flatten: flatten
    AFTER mapping, so the surviving banks appear as instance paths in
    the flat netlist. No optimisation pass runs after that flatten, so
    it cannot itself merge anything.

    force_flatten strips keep_hierarchy BEFORE synthesis instead, which
    simulates a future flow that ignores the attribute. What is left
    holding the replicas apart is then the POL polarity coding alone.
    """
    lib = _sg13g2_liberty()
    script = _read_sources() + f" hierarchy -top {TOP};"
    if force_flatten:
        script += " attrmap -modattr -remove keep_hierarchy;"
    script += f" synth -top {TOP} -flatten;"
    if lib is not None:
        script += f" dfflibmap -liberty {lib}; abc -liberty {lib};"
    script += " attrmap -modattr -remove keep_hierarchy; flatten; opt_clean;"
    return script


def _ecp5_script(force_flatten=False):
    script = _read_sources() + f" hierarchy -top {TOP};"
    if force_flatten:
        script += " attrmap -modattr -remove keep_hierarchy;"
    return script + (
        f" synth_ecp5 -top {TOP};"
        " attrmap -modattr -remove keep_hierarchy; flatten; opt_clean;")


def _declared_script():
    """Every flip-flop the RTL declares, one cell per bit, with no
    optimisation pass having had a chance to remove any of them.

    keep_hierarchy is stripped before the flatten, and that is load
    bearing rather than tidy. `flatten` skips a module carrying the
    attribute, so a bank module survives as a MODULE DEFINITION and is
    counted once however many times it is instantiated. The
    configuration domain hid this: its three banks carry three different
    parameter sets, so yosys derives three module types and three
    instances, and the count came out right by coincidence. The pointer
    banks do not -- twelve instances share three derived types -- so
    without this line the declared census reads 9 pointer flip-flops for
    the 36 the RTL declares, and
    test_no_flip_flops_are_lost_to_optimisation, whose whole job is
    comparing the two numbers, silently compares the wrong one. Measured
    2026-08-29: adding this line changes nothing at all on the pre-TMR
    sources (1241 either way) and takes the post-TMR declared count from
    1239 to 1266, which is 1241 - 12 + 36 + 1 [fact].
    """
    return _read_sources() + (
        f" hierarchy -top {TOP}; proc;"
        " attrmap -modattr -remove keep_hierarchy; flatten;"
        " opt_expr; opt_clean; simplemap;")


@pytest.fixture(scope="module")
def workdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture(scope="module")
def asic(workdir):
    return _census(_asic_script(), workdir)


@pytest.fixture(scope="module")
def ecp5(workdir):
    return _census(_ecp5_script(), workdir)


@pytest.fixture(scope="module")
def declared(workdir):
    return _census(_declared_script(), workdir)


@pytest.fixture(scope="module")
def asic_forced(workdir):
    """The ASIC recipe with keep_hierarchy stripped BEFORE synthesis:
    a front end that does not read yosys attributes."""
    return _census(_asic_script(force_flatten=True), workdir)


@pytest.fixture(scope="module")
def ecp5_forced(workdir):
    return _census(_ecp5_script(force_flatten=True), workdir)


# =====================================================================
# 1. the configuration TMR domain is three physical banks
# =====================================================================
def _assert_three_banks(census, flow):
    found = {r: census.in_instance(f"{r}.") for r in REPLICAS}
    assert all(v == TMR_W for v in found.values()), (
        f"configuration TMR collapsed in the {flow} netlist: expected "
        f"{TMR_W} flip-flops per replica, found {found}. Three replicas "
        f"written from the same expression are one register bank after "
        f"opt_dff + opt_merge, and the voter then votes three copies of "
        f"the same upset value. See hw/rtl/pilot_top.v header section 9. "
        f"Total flip-flops in this netlist: {census.total}.")


@needs_yosys
def test_config_tmr_is_three_banks_in_the_asic_flow(asic):
    _assert_three_banks(asic, "ASIC (yosys/LibreLane-shaped)")


@needs_yosys
def test_config_tmr_is_three_banks_in_the_ecp5_flow(ecp5):
    _assert_three_banks(ecp5, "synth_ecp5")


# =====================================================================
# 1b. the AER queue pointers are twelve physical banks
# =====================================================================
def _assert_pointer_banks(census, flow, exact=True):
    found = {r: census.in_instance(f"{r}.") for r in PTR_REPLICAS}
    ok = (all(v == PTR_W for v in found.values()) if exact
          else all(v >= PTR_W for v in found.values()))
    assert ok, (
        f"AER pointer TMR collapsed in the {flow} netlist: expected "
        f"{PTR_W} flip-flops per replica bank, found {found}. All three "
        f"replicas of a pointer are loaded from the same voted net, so "
        f"opt_dff + opt_merge hash them into one bank unless the "
        f"per-replica storage transform keeps them apart -- and a voter "
        f"reading one physical pointer three times agrees with itself "
        f"while the queue silently re-emits, duplicates, loses and "
        f"fabricates events (docs/16 section 5.2). See the pointer TMR "
        f"section of hw/rtl/aer_fifo.v. Total flip-flops in this "
        f"netlist: {census.total}.")


# =====================================================================
# 1c. the show-ahead valid flag is two physical rails
# =====================================================================
# hw/rtl/pilot_top.v header section 8.2. docs/16 section 6.2 ranked the
# EVQ_OUT show-ahead adapter first for wave 6 because four of its six
# silent-corruption records sit in two one-bit valid flags, and this is
# the half of that pair which lives in pilot_top.v.
#
# It is TWO rails and not three replicas, and the reason is a proof
# rather than a budget. What holds replicas apart without depending on
# an attribute is that each stores a different FUNCTION of the value;
# over one bit there are exactly two such functions, x and ~x. Two
# rails take one each and are provably non-collidable. A third has
# nothing left to take. The configuration domain measured the same
# bound at 55 bits (test_config_tmr_survives_a_flow_that_ignores_
# keep_hierarchy) and escaped it with the MIX layer, which needs at
# least four bits and so does not exist here.
#
# Two rails detect and do not correct. That is a design decision
# recorded in the RTL, not something this file can check; what this
# file checks is that the second rail is physically there, because a
# merged pair is a single flip-flop that agrees with itself and
# reports nothing -- and, unlike the configuration collapse, it is
# invisible to simulation in BOTH directions, since two rails that
# store the same function never disagree in RTL either.
#
# Mutation-checked 2026-08-30 [fact]: with `.POL(1'b1)` on u_ohv_b
# changed to `.POL(1'b0)` -- functionally identical RTL, no simulation
# can tell -- the ECP5 attribute-free census reads u_ohv_a 0 and
# u_ohv_b 1, and the ASIC total goes 1274 -> 1273, so
# test_show_ahead_valid_is_two_rails_without_keep_hierarchy_in_ecp5 and
# test_config_tmr_survives_a_flow_that_ignores_keep_hierarchy both fail
# and nothing else in this file does.
# Extended 2026-08-30 to the other two flags of the same class, on the
# same construction and with the same mutation check: the queues'
# registered read-valid (hw/rtl/aer_fifo.v, u_rdv_a / u_rdv_b, one pair
# per queue INSTANCE and therefore four rails in the pilot) and the
# neuron core's output holding flag (hw/rtl/lif_core.v, u_op_a /
# u_op_b). Each of the three files carries its own six-line rail module
# rather than sharing one: aer_fifo.v must elaborate alone for
# formal/aer_fifo.sby and hw/tb/Makefile, and lif_core.v cannot
# instantiate a module declared in its own parent. The duplication is
# deliberate and each module's header says so.
OH_RAILS = ("u_ohv_a", "u_ohv_b")
RV_RAILS = tuple(f"{q}.u_rdv_{r}"
                 for q in ("u_evq_in", "u_evq_out") for r in ("a", "b"))
OP_RAILS = ("u_lif.u_op_a", "u_lif.u_op_b")


def _assert_rails(census, flow, rails, what, exact=True):
    found = {r: census.in_instance(f"{r}.") for r in rails}
    ok = (all(v == 1 for v in found.values()) if exact
          else all(v >= 1 for v in found.values()))
    assert ok, (
        f"{what} collapsed in the {flow} netlist: expected 1 flip-flop "
        f"per rail, found {found}. Two one-bit flip-flops written from "
        f"the same enable and the same datum are one flip-flop after "
        f"opt_dff + opt_merge, and a mismatch detector reading one "
        f"flip-flop twice never fires -- in the netlist OR in RTL "
        f"simulation, which is why only this census can see it. What "
        f"separates them is the POL polarity of the rail module. Total "
        f"flip-flops in this netlist: {census.total}.")


def _assert_two_rails(census, flow, exact=True):
    _assert_rails(census, flow, OH_RAILS,
                  "the show-ahead valid flag's two rails "
                  "(pilot_flag_rail, hw/rtl/pilot_top.v section 8.2)",
                  exact)


@needs_yosys
def test_show_ahead_valid_is_two_rails_in_the_asic_flow(asic):
    _assert_two_rails(asic, "ASIC (yosys/LibreLane-shaped)")


@needs_yosys
def test_show_ahead_valid_is_two_rails_in_the_ecp5_flow(ecp5):
    _assert_two_rails(ecp5, "synth_ecp5")


@needs_yosys
def test_show_ahead_valid_is_two_rails_without_keep_hierarchy_in_ecp5(
        ecp5_forced):
    """The attribute-free case, asked of synth_ecp5 for the same reason
    the pointer test is: that flow keeps the instance path in the cell
    names once keep_hierarchy is gone, so each rail can be counted where
    it lives. The ASIC side of the question is covered by
    test_config_tmr_survives_a_flow_that_ignores_keep_hierarchy, which
    allows zero lost flip-flops across the whole design; a merged rail
    is exactly one lost flip-flop there."""
    _assert_two_rails(ecp5_forced,
                      "synth_ecp5, keep_hierarchy stripped", exact=False)


@needs_yosys
def test_read_valid_is_two_rails_per_queue_in_the_asic_flow(asic):
    """Both queue instances, four rails. aer_fifo is instantiated twice,
    so a merge that hashed EVQ_IN's rail A into EVQ_OUT's would be a
    cross-instance collapse the per-instance path still catches."""
    _assert_rails(asic, "ASIC (yosys/LibreLane-shaped)", RV_RAILS,
                  "an aer_fifo read-valid rail pair")


@needs_yosys
def test_read_valid_is_two_rails_per_queue_in_the_ecp5_flow(ecp5):
    _assert_rails(ecp5, "synth_ecp5", RV_RAILS,
                  "an aer_fifo read-valid rail pair")


@needs_yosys
def test_read_valid_rails_survive_a_flow_that_ignores_keep_hierarchy(
        ecp5_forced):
    _assert_rails(ecp5_forced, "synth_ecp5, keep_hierarchy stripped",
                  RV_RAILS, "an aer_fifo read-valid rail pair", exact=False)


@needs_yosys
def test_out_pend_is_two_rails_in_the_asic_flow(asic):
    _assert_rails(asic, "ASIC (yosys/LibreLane-shaped)", OP_RAILS,
                  "the lif_core output-holding flag's two rails")


@needs_yosys
def test_out_pend_is_two_rails_in_the_ecp5_flow(ecp5):
    _assert_rails(ecp5, "synth_ecp5", OP_RAILS,
                  "the lif_core output-holding flag's two rails")


@needs_yosys
def test_out_pend_rails_survive_a_flow_that_ignores_keep_hierarchy(
        ecp5_forced):
    _assert_rails(ecp5_forced, "synth_ecp5, keep_hierarchy stripped",
                  OP_RAILS, "the lif_core output-holding flag's two rails",
                  exact=False)


@needs_yosys
def test_pointer_tmr_is_three_banks_per_pointer_in_the_asic_flow(asic):
    _assert_pointer_banks(asic, "ASIC (yosys/LibreLane-shaped)")


@needs_yosys
def test_pointer_tmr_is_three_banks_per_pointer_in_the_ecp5_flow(ecp5):
    _assert_pointer_banks(ecp5, "synth_ecp5")


@needs_yosys
def test_pointer_tmr_survives_a_flow_that_ignores_keep_hierarchy(ecp5_forced):
    """The attribute-free case for the pointers, asked of synth_ecp5
    because that flow keeps the replica instance path in the cell names
    even once keep_hierarchy is gone, so each bank can be counted where
    it lives. The ASIC side of the same question is
    test_config_tmr_survives_a_flow_that_ignores_keep_hierarchy, which
    allows zero lost flip-flops across the whole design and therefore
    covers this domain too.

    What is holding the banks apart here is one XOR layer: replica a
    stores the pointer true, replica b its complement, replica c a
    mixing in which every stored bit is a function of two or three
    pointer bits. Polarity alone provably cannot hold three replicas --
    a storage bit has two polarities -- and the configuration domain
    measured exactly that bound before its own MIX was added.
    """
    _assert_pointer_banks(ecp5_forced, "synth_ecp5, keep_hierarchy stripped",
                          exact=False)


@needs_yosys
def test_the_two_flows_agree_on_the_flip_flop_count(asic, ecp5):
    """A canary, not a specification. Today both flows map every
    architectural register to flip-flops and agree exactly, so a
    divergence means one of them is optimising something away that the
    other keeps -- which is the shape of the defect this file exists
    for, and worth a look wherever it appears.

    One legitimate way to break this: synth_ecp5 inferring a block RAM
    (DP16KD) for lif_core.wmem or an aer_fifo mem[], which would move
    real storage out of the flip-flop count on the FPGA side only. If
    that is what happened, relax this test to compare the configuration
    TMR domain rather than the whole design -- do not relax the two
    per-flow bank tests above, which are the ones that matter.
    """
    assert asic.total == ecp5.total, (
        f"ASIC netlist has {asic.total} flip-flops, ECP5 has {ecp5.total}. "
        "Find the structure that survives in one flow and not the other "
        "before assuming this is a memory-inference difference.")


# =====================================================================
# 2. the architectural layer holds without the attribute
# =====================================================================
@needs_yosys
def test_config_tmr_survives_a_flow_that_ignores_keep_hierarchy(asic,
                                                               asic_forced):
    """keep_hierarchy is one attribute honoured by one tool. Strip it and
    the per-replica storage transform must still keep the banks apart, so
    no flip-flop at all may be lost.

    History, because the bound here moved and the reason matters. This
    test used to allow `lost <= TMR_W`, one bank, on the reasoning that
    POL polarity coding separates A from B and C was a bonus. That bound
    was correct and the design sat exactly on it: measured 2026-08-26 on
    pinned sources, 1,155 -> 1,100, replica C entirely merged away. A
    storage bit has two polarities and there are three replicas, so no
    choice of CFG_POL_C could have done better. `MIX = 1` on replica C
    (hw/rtl/pilot_top.v, pilot_cfg_bank) makes each of its stored bits an
    XOR of two or three configuration bits, which no per-bit hash can
    match against x_i or ~x_i, and the loss went to zero. The tight bound
    is the point of the test: at `<= TMR_W` this file would have passed
    just as happily with the third bank gone.

    Self-calibrating against the intact run, so growing the design does
    not need this number edited.

    Both replicated domains are inside this number. The configuration
    banks are 55 flip-flops each and the twelve AER pointer banks are
    PTR_W each, so a loss that is a multiple of 55 points at
    hw/rtl/pilot_top.v and a small loss at hw/rtl/aer_fifo.v; either way
    the answer is in a storage transform and not in an attribute.
    """
    lost = asic.total - asic_forced.total
    assert lost == 0, (
        f"with keep_hierarchy stripped the design lost {lost} flip-flops "
        f"({asic.total} -> {asic_forced.total}); none may go. The intact "
        f"run has {TMR_W} flip-flops under each of {REPLICAS} and "
        f"{PTR_W} under each of the twelve pointer banks, so an "
        "equal total here is what says every one of those banks is still "
        "physically distinct. Losing a multiple of "
        f"{TMR_W} means a configuration replica was hashed into another "
        "one (check the MIX storage transform in hw/rtl/pilot_top.v); a "
        f"smaller loss points at the pointer banks in hw/rtl/aer_fifo.v.")


@needs_yosys
def test_config_tmr_is_three_banks_without_keep_hierarchy_in_ecp5(ecp5_forced):
    """The same property in the FPGA flow, and here it can be asserted
    directly rather than by conservation of flip-flops: synth_ecp5 keeps
    the replica instance path in the cell names even when the attribute
    is gone, so each bank can be counted where it lives.

    Measured on pinned fe89f0d sources, before the MIX transform:
    u_cfg_a 55, u_cfg_b 55, u_cfg_c 0 -- the polarity coding held two
    banks and lost the third. Mutation-checked 2026-08-26 by reverting
    `.MIX(1)` on u_cfg_c alone: this test and the ASIC one above are the
    only two in the file that fail.
    """
    found = {r: ecp5_forced.in_instance(f"{r}.") for r in REPLICAS}
    assert all(v >= TMR_W for v in found.values()), (
        f"configuration TMR collapsed in the synth_ecp5 netlist once "
        f"keep_hierarchy was stripped: expected at least {TMR_W} "
        f"flip-flops per replica, found {found}. Total flip-flops: "
        f"{ecp5_forced.total}. Nothing but the per-replica storage "
        "transform holds the banks apart in this run.")


@needs_yosys
def test_the_two_flows_agree_without_keep_hierarchy(asic_forced, ecp5_forced):
    """Companion to test_the_two_flows_agree_on_the_flip_flop_count, for
    the attribute-free case. Same canary, same caveat about block-RAM
    inference."""
    assert asic_forced.total == ecp5_forced.total, (
        f"with keep_hierarchy stripped the ASIC netlist has "
        f"{asic_forced.total} flip-flops and ECP5 has {ecp5_forced.total}.")


# =====================================================================
# 3. nothing ELSE is being merged away
# =====================================================================
@needs_yosys
def test_no_flip_flops_are_lost_to_optimisation(declared, asic):
    """The catch-all. Every flip-flop the RTL declares must still be in
    the mapped netlist, except for a small budget of genuinely constant
    or unreachable bits. This is the assertion that would have caught
    the configuration TMR collapse without anyone knowing to look for
    it, and it covers every future replicated structure for free.
    """
    lost = declared.total - asic.total
    assert lost <= DEAD_BIT_BUDGET, (
        f"synthesis removed {lost} flip-flops: the RTL declares "
        f"{declared.total} and the mapped netlist has {asic.total}, "
        f"against a budget of {DEAD_BIT_BUDGET} constant or unreachable "
        "bits. Something replicated is being merged or folded away. "
        "Find it in the netlist before raising the budget.")


# The redundant and fault-tolerance structures of this design, with the
# flip-flop width each must show. Widths are the RTL declarations in
# hw/rtl/pilot_top.v, hw/rtl/lif_core.v and
# hw/rtl/tt_um_melihakbulut_nssoc.v for the default 8x8 build.
HARDENED_REGISTERS = {
    # SECDED (72,64) codeword: data and check field, docs/10 section 5.
    # If yosys ever proved the check field a function of the data it
    # could fold it, and the decoder would report a clean codeword for
    # a corrupted one.
    "u_pilot.ecc_data": 64,
    "u_pilot.ecc_check": 8,
    # saturating fault counters, docs/16 -- the evidence a flight part
    # returns, so a folded counter is a silent loss of the measurement
    "u_pilot.cnt_sec": 8,
    "u_pilot.cnt_ded": 8,
    "u_pilot.cnt_oor": 8,
    "u_pilot.cnt_tmr": 8,
    "u_pilot.fi_drop": 8,
    # clock-domain-crossing synchronizers: two flops each, and a merge
    # that collapsed a pair to one flop would reintroduce metastability
    "u_pilot.sck_s": 2,
    "u_pilot.mosi_s": 2,
    "u_pilot.ain_s": 2,
    "u_pilot.ain_tick_s": 2,
    "u_pilot.aack_s": 2,
    "u_pilot.scr_s": 2,
    "u_pilot.ain_addr_s0": 4,
    "u_pilot.ain_addr_s1": 4,
    # FSM state vectors. lif_core uses the HD-2 encoding docs/16 credits
    # for 12/12 DETECTED on FSM upsets; a re-encoding to fewer bits
    # would delete that Hamming distance.
    "u_pilot.u_lif.state": 4,
    "u_pilot.dstate": 2,
    # The lif_core memory codes have their own section below (LIF_MEMORY)
    # rather than entries here: their arrays are spread over one public
    # net per word, and the synapse file's flip-flops are named after the
    # codeword tap rather than after wmem, so an exact-name lookup would
    # read zero for a structure that is entirely present.
}


@needs_yosys
def test_hardened_registers_keep_their_full_width(asic):
    """Per-register widths in the mapped netlist. Q-net names are an
    undercount when yosys aliases a name away, so this asserts >= and
    leans on test_no_flip_flops_are_lost_to_optimisation for the exact
    total."""
    short = {}
    for name, width in HARDENED_REGISTERS.items():
        got = asic.by_q.get(name, 0)
        if got < width:
            short[name] = f"{got}/{width}"
    assert not short, (
        "hardened registers lost flip-flops in the mapped netlist: "
        f"{short}. Each of these exists to be physically present; a "
        "narrower register means synthesis folded part of it away.")


# =====================================================================
# 3b. the lif_core memory hardening is physically there
# =====================================================================
# hw/rtl/lif_core.v codes its three memory files after the docs/16
# fault-injection campaign ranked them as the whole residual
# silent-corruption risk of the pilot. Widths are the RTL declarations at
# the default 8x8 pilot build:
#
#   wmem  4 b x N_AXONS x N_NEURONS          = 256   data,  unchanged
#   vmem  16 b x N_NEURONS                   = 128   data,  unchanged
#   rmem  4 b x N_NEURONS                    =  32   data,  unchanged
#   wchk  8 b per 16-weight SECDED codeword  =  32   check, added
#   smem  6 b per neuron state codeword      =  48   check, added
#
# The specific hazard here is not the one section 1 exists for. These are
# not replicas, so opt_merge has nothing to hash them against. The hazard
# is that a check field is a pure FUNCTION of the data field in every
# reachable state, so a tool able to reason across sequential state could
# replace the storage with the encoder and leave a decoder that reports a
# clean word for a corrupted one -- protection that passes every RTL test
# and corrects nothing in silicon. Nothing in yosys does that today. This
# test is what says so tomorrow, and it is the same argument
# HARDENED_REGISTERS already makes for u_pilot.ecc_check.
#
# It is deliberately a separate assertion from
# test_no_flip_flops_are_lost_to_optimisation: that one would catch the
# loss as a total, this one names the structure, and a future geometry
# change moves both numbers together only if they are both derived.
LIF_MEMORY = {
    # (aliases the mapped netlist may use, expected flip-flops)
    "synapse weights (wmem)":     (("u_pilot.u_lif.wmem",
                                    "u_pilot.u_lif.w_data_all"), 256),
    "membrane potentials (vmem)": (("u_pilot.u_lif.vmem",), 128),
    "refractory counters (rmem)": (("u_pilot.u_lif.rmem",), 32),
    "synapse check field (wchk)": (("u_pilot.u_lif.wchk",), 32),
    "state check field (smem)":   (("u_pilot.u_lif.smem",), 48),
}


def _assert_lif_memory(census, flow):
    found = {name: census.under(*aliases)
             for name, (aliases, _) in LIF_MEMORY.items()}
    short = {name: f"{found[name]}/{width}"
             for name, (_, width) in LIF_MEMORY.items()
             if found[name] < width}
    assert not short, (
        f"the lif_core memory hardening is short of flip-flops in the "
        f"{flow} netlist: {short}. A check field that does not exist as "
        f"storage is a decoder that always reports a clean word, which "
        f"passes every RTL test and corrects nothing in silicon. See the "
        f"MEMORY HARDENING section of hw/rtl/lif_core.v. Total flip-flops "
        f"in this netlist: {census.total}.")


@needs_yosys
def test_lif_memory_files_and_check_fields_survive_the_asic_flow(asic):
    _assert_lif_memory(asic, "ASIC (yosys/LibreLane-shaped)")


# Total flip-flops of the five coded structures: 416 data + 80 check.
LIF_MEMORY_FF = sum(width for _, width in LIF_MEMORY.values())


@needs_yosys
def test_lif_memory_survives_the_ecp5_flow(ecp5):
    """The same question of the FPGA flow, asked by instance path instead
    of by net name, because the two flows leave different evidence behind
    and each has to be asked in the terms it answers in.

    synth_ecp5 packs flip-flops into slices and resolves many of their Q
    nets to names the RTL never used -- measured on this design, a per-
    structure net-name census reads 384 of the 496 coded flip-flops while
    the design's total is identical to the ASIC flow's. Counting names
    there would fail on a naming artifact and say nothing about storage.
    What synth_ecp5 does keep is the hierarchy in the cell INSTANCE names,
    which the ASIC flow loses instead (abc renumbers every cell to
    `_NNNN_`). So this test counts cells under the u_lif instance and the
    ASIC one counts them by net name; between them the structure is
    checked in both flows with neither test leaning on the other's
    weakness.
    """
    got = ecp5.in_instance("u_lif.")
    assert got >= LIF_MEMORY_FF, (
        f"the lif_core instance holds {got} flip-flops in the synth_ecp5 "
        f"netlist, fewer than the {LIF_MEMORY_FF} of its coded memory "
        f"files alone (416 data + 80 check), so part of the hardening is "
        f"not there. See the MEMORY HARDENING section of "
        f"hw/rtl/lif_core.v. Total flip-flops in this netlist: "
        f"{ecp5.total}.")


@needs_yosys
def test_the_ecc_check_fields_are_not_folded_into_their_encoders(asic):
    """The sharp form of the same question, stated as the ratio the codes
    were chosen for rather than as five separate widths.

    hw/rtl/lif_core.v picks its two codes on overhead: SECDED (72,64) over
    the synapse file is 12.5 percent, and the (26,20) code over the
    combined 20-bit neuron state word is 30 percent -- and it is that
    second ratio which lets rmem, the structure with the worst measured
    per-bit rate in the design, ride for free on check bits vmem had to
    pay for anyway. If synthesis folded either check field away the ratio
    would read zero here while every functional test still passed, because
    an RTL simulation cannot see a register that is not in the netlist.
    """
    data = (asic.under("u_pilot.u_lif.wmem", "u_pilot.u_lif.w_data_all")
            + asic.under("u_pilot.u_lif.vmem")
            + asic.under("u_pilot.u_lif.rmem"))
    check = (asic.under("u_pilot.u_lif.wchk")
             + asic.under("u_pilot.u_lif.smem"))
    assert data == 416, (
        f"the coded data fields hold {data} flip-flops, expected 416 "
        "(wmem 256 + vmem 128 + rmem 32 at the 8x8 pilot build)")
    assert check == 80, (
        f"the coded check fields hold {check} flip-flops, expected 80 "
        "(wchk 32 + smem 48). A check field is a pure function of its "
        "data field, so this is the number a sequential-equivalence "
        "optimisation would take to zero without breaking a single "
        "functional test.")


@needs_yosys
def test_reset_synchronizer_is_still_two_stages(workdir):
    """rst_sync in hw/rtl/tt_um_melihakbulut_nssoc.v is a two-flop
    reset-deassert synchronizer. Optimisation renames its second stage,
    so counting Q names undercounts it. Assert the chain structurally
    instead: one flip-flop drives rst_sync[0], and a second flip-flop is
    clocked from that same net. A collapse to a single stage would put
    an asynchronous reset release straight onto the design's setup
    window.
    """
    out = Path(workdir) / "rstsync.json"
    _run_yosys(_asic_script() + f" write_json {out};", workdir)
    design = json.loads(out.read_text())

    for mod in design["modules"].values():
        names = mod.get("netnames", {})
        if "rst_sync" not in names:
            continue
        stage0_bit = names["rst_sync"]["bits"][0]
        drivers, loads = [], []
        for cell_name, cell in mod["cells"].items():
            if not _is_flop(cell["type"]):
                continue
            conns = cell["connections"]
            if stage0_bit in conns.get("Q", []):
                drivers.append(cell_name)
            if stage0_bit in conns.get("D", []):
                loads.append(cell_name)
        assert drivers, "no flip-flop drives rst_sync[0]"
        assert loads, (
            "rst_sync[0] does not feed a second flip-flop: the two-stage "
            "reset synchronizer collapsed to one stage")
        return
    pytest.fail("rst_sync is not in the netlist at all")


# =====================================================================
# 4. the real flow, not this file's model of it
# =====================================================================
# Where a LibreLane run of this design lands. tt/runs/ is the Tiny
# Tapeout harden -- gitignored, so that glob is empty on a fresh
# checkout and only hw/openlane/pilot_sky130/runs/ answers.
RUN_TREES = (
    ROOT / "hw" / "openlane" / "pilot_sky130" / "runs",
    ROOT / "hw" / "openlane" / "pilot_ihp" / "runs",
    ROOT / "tt" / "runs",
)
# pilot_ihp was absent from this tuple until 2026-08-30, and that was a
# real hole rather than a missing line. A re-harden placed there would
# have produced every sign-off number a document could quote while
# leaving these guards skipping, because a skip means "no witness on
# disk" and cannot distinguish that from "nobody looked in the right
# directory". The wave-6 re-harden was routed into tt/runs to work
# around it. Any new run tree has to be added here or the guards stop
# guarding without saying so.

# One cell instantiation in a mapped netlist: a type, an instance name
# that may be an escaped identifier, then the port list.
_NETLIST_CELL = re.compile(r"^\s*([A-Za-z]\w*)\s+(\\?\S+)\s*\(", re.M)


def _hardening_netlists():
    """Final netlists of runs configured the way this design requires.

    A run only counts as a witness if its own resolved.json says
    SYNTH_HIERARCHY_MODE = deferred_flatten. Under LibreLane's default
    ("flatten") yosys flattens BEFORE mapping and abc renumbers every
    cell to `_NNNN_`, so no instance path survives for anything to be
    counted under -- a pre-fix run cannot answer this question and must
    not be read as answering it. hw/openlane/pilot_sky130/runs/sky-03-*
    is exactly such a run and is still on disk.

    The discriminator is the run's configuration, deliberately not a
    marker in the netlist: a netlist-shaped skip condition would skip
    on the very symptom these tests exist to catch.
    """
    found = []
    for tree in RUN_TREES:
        if not tree.is_dir():
            continue
        for run in sorted(tree.iterdir()):
            resolved = run / "resolved.json"
            nl_dir = run / "final" / "nl"
            if not resolved.is_file() or not nl_dir.is_dir():
                continue
            cfg = json.loads(resolved.read_text())
            if cfg.get("SYNTH_HIERARCHY_MODE") != "deferred_flatten":
                continue
            found.extend((run, nl) for nl in sorted(nl_dir.glob("*.nl.v")))
    return found


def test_config_tmr_survives_the_real_hardening_flow():
    """The tests above run a MODEL of LibreLane synthesis; this one reads
    what LibreLane actually produced, after placement and CTS have also
    had a chance to touch the netlist.

    The model is close but not byte-identical -- before the fix it read
    1045 flip-flops where the real 4x2 run read 1037 -- so it can agree
    with itself while the shipped flow does something else. Only the
    final netlist is the artifact that becomes silicon.

    This does NOT duplicate Checker.YosysUnmappedCells. That checker
    fails when the $paramod module types reach the mapped netlist, which
    is the crash this design's SYNTH_HIERARCHY_MODE setting avoids; a
    run that reaches final/ has already passed it. What no checker looks
    at is whether the three banks are still three banks, which is the
    property the design needs and the one measured here.

    Skips when no such run is on disk: the hardening is not part of the
    test suite's own work, so this reports on the latest one a developer
    or CI happened to leave behind.
    """
    netlists = _hardening_netlists()
    if not netlists:
        pytest.skip(
            "no deferred_flatten LibreLane run with a final netlist; "
            "produce one with hw/openlane/pilot_sky130/run_sky130.sh")

    for run, nl in netlists:
        text = nl.read_text()
        cells = _NETLIST_CELL.findall(text)
        flops = [name for ctype, name in cells if _is_flop(ctype)]
        found = {r: sum(1 for n in flops if f"{r}." in n) for r in REPLICAS}
        assert all(v == TMR_W for v in found.values()), (
            f"configuration TMR collapsed in {nl.relative_to(ROOT)}: "
            f"expected {TMR_W} flip-flops per replica, found {found}. "
            f"This is the shipped netlist of run {run.name}, so unlike "
            f"the recipe tests above this is the structure that would "
            f"have been fabricated. See hw/rtl/pilot_top.v header "
            f"section 9. Total flip-flops in this netlist: {len(flops)}.")


# The RTL file whose banks the test below counts. Its modification time
# is the provenance discriminator: a run produced before it cannot be
# expected to contain the structure it introduced.
_PTR_RTL = RTL / "aer_fifo.v"


def test_pointer_tmr_survives_the_real_hardening_flow():
    """The pointer banks in the netlist LibreLane actually produced, the
    same question test_config_tmr_survives_the_real_hardening_flow asks
    of the configuration domain.

    Skipped unless a run POSTDATES hw/rtl/aer_fifo.v, and that condition
    is deliberately about provenance rather than about the netlist. A
    skip that looked for the banks and gave up when they were missing
    would skip on precisely the symptom this file exists to catch. Every
    run on disk when the pointer TMR was written predates it -- the
    configuration domain needed its own re-harden for the same reason,
    which is what tt/runs/tmr-reharden is -- so this reports nothing
    until someone re-hardens, and then reports on the real artifact.
    """
    netlists = _hardening_netlists()
    if not netlists:
        pytest.skip(
            "no deferred_flatten LibreLane run with a final netlist; "
            "produce one with hw/openlane/pilot_sky130/run_sky130.sh")

    rtl_mtime = _PTR_RTL.stat().st_mtime
    fresh = [(run, nl) for run, nl in netlists
             if nl.stat().st_mtime >= rtl_mtime]
    if not fresh:
        pytest.skip(
            f"every LibreLane run on disk predates {_PTR_RTL.name}, which "
            "is where the pointer banks are declared; re-harden to close "
            "this check")

    for run, nl in fresh:
        text = nl.read_text()
        cells = _NETLIST_CELL.findall(text)
        flops = [name for ctype, name in cells if _is_flop(ctype)]
        found = {r: sum(1 for n in flops if f"{r}." in n)
                 for r in PTR_REPLICAS}
        assert all(v == PTR_W for v in found.values()), (
            f"AER pointer TMR collapsed in {nl.relative_to(ROOT)}: "
            f"expected {PTR_W} flip-flops per replica bank, found "
            f"{found}. This is the shipped netlist of run {run.name}, so "
            f"this is the structure that would have been fabricated. See "
            f"the pointer TMR section of hw/rtl/aer_fifo.v. Total "
            f"flip-flops in this netlist: {len(flops)}.")


def test_valid_flag_rails_survive_the_real_hardening_flow():
    """The eight dual-rail valid flags, in the netlist LibreLane produced.

    Until this test existed the rails were covered only by the yosys-model
    tests above, and their count in the shipped netlist was checked by
    hand once, in docs/27 section 7.2. That is the wrong shape of evidence
    for this defect class. The failure mode is a rail built at the same
    polarity as its twin: functionally identical RTL, which every
    simulation in this repository passes and no amount of testing can
    distinguish. Only counting cells in the real netlist sees it, so the
    count has to be automatic or it will drift.

    Same provenance rule as the pointer guard: skip on the age of the
    run, never on the absence of the banks, because a netlist-shaped skip
    condition would skip on precisely the symptom being looked for.
    """
    netlists = _hardening_netlists()
    if not netlists:
        pytest.skip(
            "no deferred_flatten LibreLane run with a final netlist; "
            "produce one with hw/openlane/pilot_ihp/run_ihp.sh or the "
            "sky130 equivalent")

    newest_rtl = max((RTL / f).stat().st_mtime for f in _RAIL_RTL)
    fresh = [(run, nl) for run, nl in netlists
             if nl.stat().st_mtime >= newest_rtl]
    if not fresh:
        pytest.skip(
            "every LibreLane run on disk predates one of "
            f"{', '.join(_RAIL_RTL)}, where the rails are declared; "
            "re-harden to close this check")

    for run, nl in fresh:
        flops = [name for ctype, name in _NETLIST_CELL.findall(nl.read_text())
                 if _is_flop(ctype)]
        found = {r: sum(1 for n in flops if f"{r}." in n) for r in RAILS}
        assert found == RAILS, (
            f"a dual-rail valid flag collapsed in {nl.relative_to(ROOT)}: "
            f"expected {RAILS}, found {found}. This is the shipped "
            f"netlist of run {run.name}, so it is the structure that "
            f"would have been fabricated. A missing rail means synthesis "
            f"proved the two equivalent and merged them, which is what "
            f"happens if both are built at the same polarity -- see the "
            f"rail headers in hw/rtl/{', hw/rtl/'.join(_RAIL_RTL)}. "
            f"Total flip-flops in this netlist: {len(flops)}.")
