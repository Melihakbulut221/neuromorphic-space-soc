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


def _ecp5_script():
    return _read_sources() + (
        f" synth_ecp5 -top {TOP};"
        " attrmap -modattr -remove keep_hierarchy; flatten; opt_clean;")


def _declared_script():
    """Every flip-flop the RTL declares, one cell per bit, with no
    optimisation pass having had a chance to remove any of them."""
    return _read_sources() + (
        f" hierarchy -top {TOP}; proc; flatten; opt_expr; opt_clean;"
        " simplemap;")


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
def test_config_tmr_survives_a_flow_that_ignores_keep_hierarchy(asic, workdir):
    """keep_hierarchy is one attribute honoured by one tool. Strip it and
    the POL polarity coding must still keep replica A and replica B
    apart, so at most one bank's worth of flip-flops can be lost.

    Self-calibrating against the intact run, so growing the design does
    not need this number edited.
    """
    forced = _census(_asic_script(force_flatten=True), workdir)
    lost = asic.total - forced.total
    assert lost <= TMR_W, (
        f"with keep_hierarchy stripped the design lost {lost} flip-flops "
        f"({asic.total} -> {forced.total}); at most {TMR_W} may go. The "
        "per-replica POL polarity coding in hw/rtl/pilot_top.v is what "
        "bounds this, and losing more than one bank means it is gone.")


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
