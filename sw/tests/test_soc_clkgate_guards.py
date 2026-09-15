# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Textual and netlist guards for the fabric's and the accelerator's clock gates.

`docs/76-the-second-and-third-clock-gates.md` adds two `sg13g2_lgcp_1`
integrated clock gates to `soc_top.v` -- one on `soc_bus`, one on
`soc_npu` and the frozen die inside it -- beside the one `ibex_top`
already carried and that `docs/57` found. What a simulation can check
about them is checked by the cocotb suite and the whole-SoC equivalence
of `docs/76` section 6; what a proof can check is
`hw/soc/formal/soc_bus_props.v` F10. This file is the third kind: the
things neither can see.

Four classes of check:

  1. **The design ships gated.** `CLKGATE` defaults to 1 in `soc_top.v`
     and in `soc_npu.v`, nothing in the design sets it to 0, and the only
     way to build the ungated configuration is a measurement knob on a
     flow script. Same discipline `sw/tests/test_soc_memory_guards.py`
     applies to `MEM_HARDEN` and `test_soc_boot_guards.py` to `HARDEN`,
     and for the same reason: a counterfactual that anything in the
     design can select is a counterfactual that will eventually ship.

  2. **The gate is a real cell and not a behavioural stand-in.** The two
     new instances go through `hw/soc/rtl/prim_clock_gating.v`, which is
     the file `docs/57` section 4.1 found binding `sg13g2_lgcp_1`. A
     hand-written `assign gclk = clk & en` would simulate identically,
     would synthesise into a glitching AND gate, and nothing else in this
     repository would notice.

  3. **The enable is not a policy.** Neither block's enable may read
     `core_sleep_o` or any other block's state. A gate whose enable came
     from somewhere else would be a power-management decision made in one
     file about another, and its completeness could not be proved in the
     module it belongs to -- which is the whole of why F10 is provable.

  4b. **The slow half of the accelerator's enable is a function of its
     own registers**, and it is a fan-in cone census rather than a
     reading of the source. `docs/77` splits `soc_npu.v`'s enable into a
     combinational half (`req_i | psel_i`, the only two things that can
     rise and fall while the block's clock is stopped) and a registered
     half, and the whole safety argument for the second is that a term
     which is a function of registers that are not being clocked cannot
     pulse and vanish. That is `hw/soc/formal/clkgate_wake.sby`'s
     assumption A2, and this file is where it is discharged: elaborate
     the module, flatten it, walk the fan-in cone of `npu_act_slow` cut
     at every sequential cell, and fail if ANY input port is reachable.
     It is what found `C_INJ_OVF` -- the one fault line that carries
     `psel_i` -- which no reading of the file had noticed.

  4. **The census survives synthesis** -- three integrated clock gates in
     a netlist, and the fabric's and the accelerator's flip-flops on the
     gated nets rather than on `clk_i_regs`. `docs/33` is the record of
     what a header claim without a census is worth, and `docs/75` is the
     record of a census that counted the right number of the wrong thing.
     The netlist half skips when no build output is present, exactly as
     `sw/tests/test_flow_evidence.py` does.

Run with the repository-root suite::

    .venv/bin/python -m pytest sw/tests/test_soc_clkgate_guards.py
"""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOC_RTL = ROOT / "hw" / "soc" / "rtl"
SOC_FLOW = ROOT / "hw" / "soc" / "flow"
SOC_FORMAL = ROOT / "hw" / "soc" / "formal"

TOP = (SOC_RTL / "soc_top.v").read_text()
BUS = (SOC_RTL / "soc_bus.v").read_text()
NPU = (SOC_RTL / "soc_npu.v").read_text()
ICG = (SOC_RTL / "prim_clock_gating.v").read_text()
BUS_PROPS = (SOC_FORMAL / "soc_bus_props.v").read_text()


def _body(src, module):
    """The text of one module, without its header comment."""
    at = src.index("module " + module)
    return src[at:src.index("endmodule", at)]


# ---------------------------------------------------------------------
# 1. The design ships gated
# ---------------------------------------------------------------------

def test_clkgate_defaults_to_the_design_in_both_modules():
    assert re.search(r"parameter\s+integer\s+CLKGATE\s*=\s*1\b", TOP), (
        "soc_top.v's CLKGATE no longer defaults to 1, so the design as "
        "elaborated by every flow that does not set it is the UNGATED one")
    assert re.search(r"parameter\s+integer\s+CLKGATE\s*=\s*1\b", NPU), (
        "soc_npu.v's CLKGATE no longer defaults to 1")


def test_the_top_level_forwards_one_parameter_and_not_two():
    """soc_top.v passes its own CLKGATE to soc_npu.

    There is no configuration in which the fabric's gate is wanted and the
    accelerator's is not, so there is one knob. Two would be two things to
    get out of step, and an enable without a gate -- or a gate without an
    enable -- is not a state this design has a name for.
    """
    assert re.search(r"\.CLKGATE\s*\(\s*CLKGATE\s*\)", TOP), (
        "soc_top.v no longer forwards its own CLKGATE to soc_npu")
    assert len(re.findall(r"parameter\s+integer\s+CLKGATE", TOP)) == 1, (
        "soc_top.v declares more than one clock-gate parameter")


def test_nothing_in_the_design_selects_the_ungated_configuration():
    """Only a flow script may set CLKGATE = 0, and only two do.

    The ungated build exists to be the like-for-like baseline the gates'
    area and power are measured against -- docs/41 section 6.5's rule --
    and for the two-build bit-exact equivalence of docs/76 section 6. It
    is not a configuration of the part.
    """
    offenders = []
    for p in sorted(SOC_RTL.glob("*.v")) + sorted(SOC_RTL.glob("*.vh")):
        text = p.read_text()
        for m in re.finditer(r"\.CLKGATE\s*\(\s*(\d+)\s*\)", text):
            if m.group(1) != "1" and "CLKGATE" not in m.group(0)[:-1]:
                offenders.append((p.name, m.group(0)))
        if re.search(r"defparam[^;]*CLKGATE\s*=\s*0", text):
            offenders.append((p.name, "defparam CLKGATE = 0"))
    assert not offenders, (
        "the RTL selects the ungated configuration somewhere: {}".format(
            offenders))

    allowed = {"syn_soc_top.sh", "sim_soc.sh", "fi_core.sh"}
    setters = set()
    for p in sorted(SOC_FLOW.glob("*.sh")):
        if re.search(r"SOC_CLKGATE", p.read_text()):
            setters.add(p.name)
    assert setters <= allowed, (
        "a flow script this test does not know about carries the ungated "
        "knob: {}. Add it here with the reason, or remove it.".format(
            sorted(setters - allowed)))


def test_the_wake_hold_is_the_value_the_design_ships():
    """soc_npu.v's HOLD_CYCLES.

    It is not a correctness term -- soc_npu.v's own section says so -- but
    it is the margin that covers a settling chain inside the frozen die
    that no term of `npu_act` names, and docs/76 section 6 measures the
    equivalence AT THIS VALUE. Changing it silently would move what that
    measurement was a measurement of.
    """
    assert re.search(r"parameter\s+integer\s+HOLD_CYCLES\s*=\s*4\b", NPU), (
        "soc_npu.v's HOLD_CYCLES is no longer 4, which is the value "
        "docs/76 section 6's bit-exact equivalence was measured at")


# ---------------------------------------------------------------------
# 2. The gate is a real cell
# ---------------------------------------------------------------------

def test_both_new_gates_go_through_prim_clock_gating():
    """And therefore through the PDK cell, not through an AND gate.

    hw/soc/rtl/prim_clock_gating.v exists to bind sg13g2_lgcp_1 rather
    than the behavioural latch upstream ships; docs/57 section 4.1 is
    where that file was first read. An `assign` here would simulate
    identically and synthesise into a glitching combinational gate on a
    clock net.
    """
    body = _body(TOP, "soc_top")
    insts = re.findall(r"prim_clock_gating\s+(\w+)\s*\(", body)
    assert sorted(insts) == ["u_bus_cg", "u_npu_cg"], (
        "soc_top.v no longer instantiates exactly the two gates docs/76 "
        "adds, through prim_clock_gating: found {}".format(insts))
    for net in ("clk_bus", "clk_npu"):
        assert not re.search(r"assign\s+" + net + r"\s*=\s*clk_i\s*&", body), (
            "{} is being built out of an AND gate somewhere".format(net))
    assert "sg13g2_lgcp_1" in ICG, (
        "prim_clock_gating.v no longer binds the PDK's integrated clock "
        "gate, so nothing in this design has one")


def test_the_ungated_arm_is_a_wire_and_not_a_second_design():
    body = _body(TOP, "soc_top")
    assert "assign clk_bus = clk_i;" in body and "assign clk_npu = clk_i;" in body, (
        "the CLKGATE = 0 arm no longer bypasses the gates with a plain "
        "wire, so the baseline is not the same design minus the gates")


# ---------------------------------------------------------------------
# 3. The enable is a property of the block, not a policy
# ---------------------------------------------------------------------

def test_neither_enable_reads_another_block_s_state():
    """`core_sleep_o` in particular.

    docs/57 section 16 proposed exactly that -- "the enable for a
    peripheral domain is core_sleep_o and !s_req and the absence of a
    pending response". It is NOT what was built, and the reason is F10:
    an enable that reads the core's sleep state is a statement about the
    core, cannot be proved complete inside soc_bus, and would be wrong the
    first time a slave had work to do with the core asleep -- which is
    what a DMA or a wake-on-event path is.
    """
    for name, src, mod in (("soc_bus.v", BUS, "soc_bus"),
                           ("soc_npu.v", NPU, "soc_npu")):
        body = _body(src, mod)
        assert "core_sleep" not in body, (
            "{}'s body reads core_sleep, so its clock enable is a policy "
            "about the core rather than a statement about itself".format(
                name))


def test_the_fabric_enable_is_purely_combinational():
    """soc_bus.v's clk_en_o is an `assign`, so it can open the gate in the
    same cycle a request arrives and the slave never answers late.

    A registered enable would cost one cycle on every wake, on the one
    block every access in the SoC passes through.
    """
    body = _body(BUS, "soc_bus")
    assert re.search(r"assign\s+clk_en_o\s*=", body), (
        "soc_bus.v's clk_en_o is no longer a combinational assign")
    assert not re.search(r"clk_en_o\s*<=", body), (
        "soc_bus.v's clk_en_o is now registered, which costs a cycle on "
        "every wake of the block every access passes through")


def test_the_completeness_property_still_names_every_register():
    """F10 is only a theorem about the registers it enumerates.

    soc_bus.v has no bulk to sample -- q_owner and q_fill are arrays --
    so soc_bus_props.v lists them, and a register added to the RTL without
    a line in F10 would be a register the gate could silently freeze.
    """
    body = _body(BUS, "soc_bus")
    declared = set()
    for m in re.finditer(r"^\s*reg\s*(?:\[[^\]]*\]\s*)?([A-Za-z_]\w*)"
                         r"((?:\s*,\s*[A-Za-z_]\w*)*)", body, re.M):
        declared.add(m.group(1))
        for extra in re.findall(r"[A-Za-z_]\w*", m.group(2)):
            declared.add(extra)
    assert declared, "no registers found in soc_bus.v; the parse broke"
    at = BUS_PROPS.index("// F10:")
    f10 = BUS_PROPS[at:BUS_PROPS.index("// F10b.", at)]
    missing = sorted(r for r in declared if r not in f10)
    assert not missing, (
        "soc_bus.v declares {} but F10 does not mention them, so the "
        "clock-gate completeness proof does not cover them".format(missing))


# ---------------------------------------------------------------------
# 4. The census, on a netlist if one has been built
# ---------------------------------------------------------------------

def _netlists():
    out = ROOT / "hw" / "soc" / "out"
    found = []
    # docs/76 built s76*gate and docs/77 builds s77*gate; the census is
    # the same census and either answers it.
    for d in sorted(list(out.glob("s76*gate")) + list(out.glob("s77*gate"))):
        nl = d / "soc_top.netlist.v"
        if nl.is_file():
            found.append(nl)
    return found


@pytest.mark.parametrize("nl", _netlists() or [None])
def test_three_integrated_clock_gates_survive_synthesis(nl):
    """The count, on the netlist rather than in the header.

    docs/57 found the first gate by grepping the signed-off netlist for
    `sg13g2_lgcp_1` and finding one where six documents said there were
    none. This is that grep, kept as a test.
    """
    if nl is None:
        pytest.skip("no hw/soc/out/s76*gate netlist in this tree; "
                    "SOC_MEM=sram hw/soc/flow/syn_soc_top.sh 20 <out> builds one")
    text = nl.read_text()
    names = sorted(re.findall(r"sg13g2_lgcp_1\s+\\(\S+)", text))
    assert len(names) == 3, (
        "{} has {} integrated clock gates, not 3: {}".format(
            nl, len(names), names))
    assert names == ["g_clkgate.u_bus_cg.u_icg",
                     "g_clkgate.u_npu_cg.u_icg",
                     "u_ibex.core_clock_gate_i.u_icg"], names


# ---------------------------------------------------------------------
# 4b. The slow half of the accelerator's enable, by fan-in cone
# ---------------------------------------------------------------------
#
# docs/77 section 6. `hw/soc/formal/clkgate_wake.sby` proves that the
# registered-wake enable is complete FROM TWO SIDE CONDITIONS, and A2 is
# "`slow` is a function of the block's state". This is where A2 is
# discharged on the design rather than assumed about it.
#
# The walk cuts at every sequential cell, so what it reaches are the
# module's own input ports and nothing else. An input port in that cone
# would be a term that can rise and fall with the clock stopped, and a
# registered wake would then be able to miss it -- which is precisely
# the failure the split exists to avoid.

PILOT_RTL = ROOT / "hw" / "rtl"

# The source list is hw/soc/tb/cocotb/Makefile.soc_npu's, which is the
# list soc_npu is elaborated from everywhere else in this repository.
_NPU_SOURCES = [
    SOC_RTL / "soc_npu.v",
    SOC_RTL / "soc_npu_ser.v",
    SOC_RTL / "soc_tmr_bank.v",
    PILOT_RTL / "pilot_top.v",
    PILOT_RTL / "lif_core.v",
    PILOT_RTL / "aer_fifo.v",
    PILOT_RTL / "scrub.v",
    PILOT_RTL / "secded_enc.v",
    PILOT_RTL / "secded_dec.v",
    PILOT_RTL / "tmr_voter.v",
]

# Every yosys cell type whose outputs are STATE rather than a function of
# this cycle's inputs. The walk stops at each of them; a type missing
# from this set would make the census too STRICT (it would walk through
# a register and report inputs that are not really in the combinational
# cone), never too permissive, so the failure mode is a false alarm.
_SEQUENTIAL = {
    "$dff", "$adff", "$sdff", "$dffe", "$adffe", "$sdffe", "$dffsr",
    "$dffsre", "$aldff", "$aldffe", "$dlatch", "$adlatch", "$dlatchsr",
    "$sr", "$mem", "$mem_v2", "$memrd", "$memrd_v2", "$memwr",
    "$memwr_v2", "$meminit", "$meminit_v2", "$fsm", "$scopeinfo",
}


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


def _elaborate_npu(tmp_path, src_override=None, params=None):
    """soc_npu, flattened, as JSON. keep_hierarchy is dropped for the walk.

    `params` overrides module parameters with `chparam` after the
    hierarchy is set, which is how the WAKE_GNT = 1 arm is elaborated
    without a second source file; the module keeps its name.

    soc_tmr_bank and the pilot's own blocks carry `keep_hierarchy` so that
    `opt_merge` cannot fold the TMR replicas together -- docs/33's whole
    subject -- and with it in place `flatten` leaves them as instances a
    cone walk would have to cross conservatively. Dropping it HERE
    changes nothing about the shipped netlist: this elaboration is thrown
    away, and hw/soc/flow/syn_soc_top.sh is untouched.
    """
    srcs = list(_NPU_SOURCES)
    if src_override is not None:
        srcs[0] = src_override
    out = tmp_path / "soc_npu_flat.json"
    chparam = "".join("chparam -set {} {} soc_npu; ".format(k, v)
                      for k, v in sorted((params or {}).items()))
    script = (
        "read_verilog -I {inc1} -I {inc2} {files}; "
        "hierarchy -top soc_npu; {chparam}proc; "
        "setattr -mod -unset keep_hierarchy; flatten; opt_clean; "
        "write_json {out};".format(
            inc1=SOC_RTL, inc2=PILOT_RTL, chparam=chparam,
            files=" ".join(str(p) for p in srcs), out=out))
    r = subprocess.run([YOSYS, "-p", script], capture_output=True,
                       text=True, timeout=900)
    assert r.returncode == 0, (
        "yosys failed:\n" + r.stdout[-3000:] + r.stderr[-3000:])
    return json.loads(out.read_text())


def _input_ports_in_cone(design, wire):
    """Which input ports of soc_npu the combinational cone of `wire` reaches."""
    m = design["modules"]["soc_npu"]
    assert wire in m["netnames"], (
        "{} is not a net of the elaborated soc_npu; the enable has been "
        "renamed or restructured and this census no longer measures "
        "what docs/77 section 6 says it does".format(wire))
    driver = {}
    for _name, c in m["cells"].items():
        if c["type"] in _SEQUENTIAL:
            continue
        d = c.get("port_directions", {})
        ins, outs = [], []
        for port, bits in c["connections"].items():
            (outs if d.get(port) == "output" else ins).extend(bits)
        for b in outs:
            driver.setdefault(b, []).append(ins)
    inputs = {}
    for name, p in m.get("ports", {}).items():
        if p["direction"] in ("input", "inout"):
            for b in p["bits"]:
                inputs[b] = name
    seen, hit = set(), set()
    stack = [b for b in m["netnames"][wire]["bits"] if isinstance(b, int)]
    while stack:
        b = stack.pop()
        if b in seen:
            continue
        seen.add(b)
        if b in inputs:
            hit.add(inputs[b])
        for ins in driver.get(b, []):
            stack.extend(x for x in ins if isinstance(x, int))
    return hit


@needs_yosys
def test_the_slow_half_of_the_npu_enable_reaches_no_input_port(tmp_path):
    """A2, discharged on the design.

    `npu_act_slow` may depend on this block's registers and on nothing
    else. `clk_i`, `clk_free_i` and `rst_ni` are not activity terms and
    are excluded by name; anything else is a term that can move while the
    clock is stopped, and a registered wake can miss such a term by one
    cycle at the moment it matters.
    """
    design = _elaborate_npu(tmp_path)
    reached = _input_ports_in_cone(design, "g_clkgate.npu_act_slow")
    reached -= {"clk_i", "clk_free_i", "rst_ni"}
    assert not reached, (
        "soc_npu.v's npu_act_slow depends combinationally on {} -- it is "
        "no longer a function of the block's registers alone, so "
        "hw/soc/formal/clkgate_wake.sby's assumption A2 does not hold of "
        "this design and the registered wake may miss it".format(
            sorted(reached)))


@needs_yosys
def test_the_fast_half_of_the_npu_enable_is_exactly_the_two_transient_inputs(
        tmp_path):
    """And the fast half is `req_i | psel_i` and nothing more.

    Adding a term here is not free: it is the half that lands on the
    clock-gating check's timing path, and docs/77 section 9 measures that
    the accelerator's check misses at the slow corner because `req_i`
    alone already arrives after its required time. Removing one is worse
    -- a bus or APB transaction accepted at an edge the gate removed.
    """
    design = _elaborate_npu(tmp_path)
    reached = _input_ports_in_cone(design, "g_clkgate.npu_act_fast")
    reached -= {"clk_i", "clk_free_i", "rst_ni"}
    assert reached == {"req_i", "psel_i"}, (
        "soc_npu.v's npu_act_fast is {} and docs/77 built it as exactly "
        "req_i and psel_i".format(sorted(reached)))


@needs_yosys
def test_the_cone_census_fails_when_a_transient_term_is_moved_to_the_slow_half(
        tmp_path):
    """The census can fail, and this is the mutation that makes it.

    docs/76 section 4.4's rule: a property that cannot fail is not a
    property. `C_INJ_OVF` is `inj_wr_en && inj_full` and `inj_wr_en`
    carries `psel_i`, so putting it back into the slow half is exactly
    the mistake the mask in soc_npu.v exists to prevent -- and it is the
    mistake the design shipped before docs/77, where the whole of
    `|sticky_ev` was in one combinational term.
    """
    mutant = tmp_path / "soc_npu_mut.v"
    body = NPU.replace("| (|(sticky_ev & STICKY_FROZEN))",
                       "| (|sticky_ev)")
    assert body != NPU, (
        "the mask this mutation removes is not in soc_npu.v any more")
    mutant.write_text(body)
    design = _elaborate_npu(tmp_path, src_override=mutant)
    reached = _input_ports_in_cone(design, "g_clkgate.npu_act_slow")
    reached -= {"clk_i", "clk_free_i", "rst_ni"}
    assert reached, (
        "unmasking C_INJ_OVF no longer puts an input port in the slow "
        "half's cone, so this census would not catch the mistake it was "
        "written for")


def test_the_wake_bit_is_on_the_ungated_clock():
    """And soc_top.v hands it the ungated one.

    A wake bit on the gated clock is a bit that cannot start the clock it
    is gated by. It is one flip-flop and it is the whole of docs/77's
    change, so both halves of the wiring are asserted here rather than
    left to a reading.
    """
    body = _body(NPU, "soc_npu")
    assert re.search(r"input\s+wire\s+clk_free_i", body), (
        "soc_npu.v no longer takes the ungated clock as a port")
    assert re.search(r"always\s*@\(posedge\s+clk_free_i", body), (
        "soc_npu.v's wake bit is no longer clocked by the ungated clock, "
        "so it cannot start the clock it gates")
    top = _body(TOP, "soc_top")
    assert re.search(r"\.clk_free_i\s*\(\s*clk_i\s*\)", top), (
        "soc_top.v no longer hands soc_npu the UNGATED clk_i for its "
        "wake bit")
    assert re.search(r"\.clk_i\s*\(\s*clk_npu\s*\)", top), (
        "soc_top.v no longer hands soc_npu the GATED clock for the rest")


# ---------------------------------------------------------------------
# 5. docs/77 section 18: the wakefulness-qualified grant, built and OFF
# ---------------------------------------------------------------------
#
# docs/77 section 11 priced the one change that could close the
# accelerator's clock-gating check by construction -- refuse the grant
# and the APB completion in a cycle the block is not clocked, and take
# `req_i | psel_i` off the enable -- and section 18 builds it behind
# soc_npu.v's WAKE_GNT. Two things are guarded: that it ships OFF, for
# the reason CLKGATE = 0 is guarded plus one more (it moves the
# whole-SoC cycle count the corpus quotes as an invariant); and that at
# WAKE_GNT = 1 the enable really does read no input, which is the
# by-construction claim, discharged by the same cone census as A2.

def test_wake_gnt_defaults_off_and_is_forwarded():
    """The design ships WAKE_GNT = 0, in both modules, and soc_top.v
    forwards its own value to soc_npu -- the one place the parameter
    is read."""
    assert re.search(r"parameter\s+integer\s+WAKE_GNT\s*=\s*0\b", TOP), (
        "soc_top.v's WAKE_GNT no longer defaults to 0: the whole-SoC cycle "
        "count docs/68 section 8 quotes as an invariant moves with it, and "
        "docs/77 section 18 says what the default should be and why")
    assert re.search(r"parameter\s+integer\s+WAKE_GNT\s*=\s*0\b", NPU), (
        "soc_npu.v's WAKE_GNT no longer defaults to 0")
    assert re.search(r"\.WAKE_GNT\s*\(\s*WAKE_GNT\s*\)", TOP), (
        "soc_top.v no longer forwards its own WAKE_GNT to soc_npu")


def test_nothing_in_the_design_selects_the_wake_qualified_grant():
    """Only the three flow scripts that carry SOC_CLKGATE may carry
    SOC_WAKE_GNT, and nothing in the RTL sets the parameter itself."""
    offenders = []
    for p in sorted(SOC_RTL.glob("*.v")) + sorted(SOC_RTL.glob("*.vh")):
        text = p.read_text()
        for m in re.finditer(r"\.WAKE_GNT\s*\(\s*(\d+)\s*\)", text):
            if m.group(1) != "0":
                offenders.append((p.name, m.group(0)))
        if re.search(r"defparam[^;]*WAKE_GNT\s*=\s*[1-9]", text):
            offenders.append((p.name, "defparam WAKE_GNT != 0"))
    assert not offenders, (
        "the RTL selects the wakefulness-qualified grant somewhere: "
        "{}".format(offenders))
    allowed = {"syn_soc_top.sh", "sim_soc.sh", "fi_core.sh"}
    setters = {p.name for p in sorted(SOC_FLOW.glob("*.sh"))
               if re.search(r"SOC_WAKE_GNT", p.read_text())}
    assert setters <= allowed, (
        "a flow script this test does not know about carries the knob: "
        "{}. Add it here with the reason, or remove it.".format(
            sorted(setters - allowed)))


@needs_yosys
def test_at_wake_gnt_the_enable_and_the_acceptance_read_no_input_port(
        tmp_path):
    """The by-construction claim, as a cone census.

    At WAKE_GNT = 1 `clk_en_o` is `wake_q || (wake_hold != 0)` and the
    grant and the APB completion are qualified by the same term. The
    walk cuts at every sequential cell, so an input port in any of the
    three cones would be a path from outside the block to the GATE pin
    -- which is exactly the path docs/77 section 3 measures as the
    -5.0198 ns, and exactly what this configuration exists to remove.
    """
    design = _elaborate_npu(tmp_path, params={"WAKE_GNT": 1})
    for wire in ("clk_en_o", "may_accept", "pready_o"):
        reached = _input_ports_in_cone(design, wire)
        reached -= {"clk_i", "clk_free_i", "rst_ni"}
        assert not reached, (
            "at WAKE_GNT = 1, soc_npu.v's {} depends combinationally on {}: "
            "the enable is not a function of the block's registers alone, "
            "and the clock-gating check does not close by construction"
            .format(wire, sorted(reached)))


@needs_yosys
def test_at_the_default_the_enable_reads_exactly_the_two_transient_inputs(
        tmp_path):
    """And the complement, so that the two configurations cannot be
    confused: at WAKE_GNT = 0 the enable's cone reaches `req_i` and
    `psel_i` and nothing else, which is docs/77 section 5.1's fast half
    and the reason the check misses there."""
    design = _elaborate_npu(tmp_path)
    reached = _input_ports_in_cone(design, "clk_en_o")
    reached -= {"clk_i", "clk_free_i", "rst_ni"}
    assert reached == {"req_i", "psel_i"}, (
        "at WAKE_GNT = 0 soc_npu.v's clk_en_o reaches {}; docs/77 built "
        "it to reach exactly req_i and psel_i".format(sorted(reached)))
