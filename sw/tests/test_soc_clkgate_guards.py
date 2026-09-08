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

import re
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
    for d in sorted(out.glob("s76*gate")):
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
