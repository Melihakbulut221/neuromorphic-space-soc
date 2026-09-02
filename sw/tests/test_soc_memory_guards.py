"""Does the memory response register stay off, and do the four `soc_mem`
implementations still agree about it?

WHY THIS FILE EXISTS

`docs/50` adds one parameter, `RDREG`, to a module that FOUR different
files declare:

  * ``hw/soc/rtl/soc_mem.v``       the behavioural model, simulation and
                                   the cocotb suite;
  * ``hw/soc/rtl/soc_mem_sram.v``  the RM_IHPSG13 build, place-and-route
                                   and every timing number about the part;
  * the ``SRAM MACRO STAND-IN``    inside ``hw/soc/flow/syn_soc_top.sh``,
                                   which is what ``SOC_MEM=stub`` times;
  * the ``BLACKBOX DECLARATION``   in the same script, which is what
                                   ``SOC_MEM=blackbox`` measures area on.

``sw/tests/test_soc_synthesis_guards.py`` already checks that the four
agree on the PORT list. Nothing checked that they agree on the PARAMETER
list, and a parameter one of them does not declare is an elaboration
error only for the configurations somebody happens to run: `soc_top.v`
passes ``.RDREG(MEM_RDREG)`` to both memories, so a stand-in that lost
the parameter would break `SOC_MEM=stub` while `SOC_MEM=sram` -- the one
that is hardened -- kept working. That is the shape `docs/41` section 6.6
counts, and it is cheap to close.

**And the default has to stay off.** `MEM_RDREG = 1` is a change to the
part's PERFORMANCE, not only to its timing: `docs/50` section 5 measures
the bring-up program at 232,232 cycles against 185,443, and section 6
measures what that costs against what the higher clock buys. A parameter
that can turn that on is a parameter someone turns on, and the design
that ships is the one whose cycle count is published. `docs/50`'s
recommendation is that it stays off; this file is what makes "stays off"
a check rather than an intention.

WHAT THIS FILE DOES **NOT** COVER

  * Whether the registered arm is CORRECT. That is
    ``hw/soc/tb/cocotb/test_soc_mem.py``, which runs the same seven
    protocol tests at both values of the parameter and measures the
    latency it got rather than trusting the one it asked for.
  * Whether the SRAM build's arm is correct, at either value. It cannot
    be simulated without the PDK's macro models and nothing here
    simulates it; the evidence for that file is the netlist `docs/50`
    hardens and the parameter check below.
  * The fabric. `soc_bus.v` is UNCHANGED by `docs/50` and the reason is
    measured rather than assumed -- see ``hw/soc/tb/soc_bus_probe.v``.
  * Anything about area, timing or placement.

Run with the repository-root suite::

    .venv/bin/python -m pytest sw/tests/test_soc_memory_guards.py
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOC_RTL = ROOT / "hw" / "soc" / "rtl"
SOC_FLOW = ROOT / "hw" / "soc" / "flow"
SOC_TB = ROOT / "hw" / "soc" / "tb"

# The two here-documents in flow/syn_soc_top.sh, by the comment line that
# opens each. test_soc_synthesis_guards.py finds them the same way.
STANDIN_MARKERS = ("// BLACKBOX DECLARATION", "// SRAM MACRO STAND-IN")


def _params(text):
    """Parameter names of the first module declaration in `text`, in
    declaration order."""
    body = text.split("#(", 1)[1].split(") (", 1)[0]
    return re.findall(r"parameter\s+(?:integer\s+)?(\w+)\s*=", body)


def _standin(marker):
    script = (SOC_FLOW / "syn_soc_top.sh").read_text()
    start = script.index(marker)
    block = script[start:script.index("\nEOF", start)]
    return block[block.index("module soc_mem"):]


def test_the_four_soc_mem_declarations_agree_on_the_parameter_list():
    """`soc_top.v` instantiates `soc_mem` twice and names RDREG in both,
    so every file that can answer to that module name has to declare it.
    A missing parameter is an elaboration error in the configuration that
    reads that file and in no other, which means `SOC_MEM=sram` can be
    green while `SOC_MEM=stub` is broken."""
    real = _params((SOC_RTL / "soc_mem.v").read_text())
    assert "RDREG" in real, "hw/soc/rtl/soc_mem.v no longer declares RDREG"

    others = {
        "hw/soc/rtl/soc_mem_sram.v": _params(
            (SOC_RTL / "soc_mem_sram.v").read_text()),
    }
    for marker in STANDIN_MARKERS:
        others["syn_soc_top.sh " + marker.strip("/ ")] = _params(
            _standin(marker))

    for name, got in others.items():
        assert got == real, (
            "{} declares {} but hw/soc/rtl/soc_mem.v declares {}".format(
                name, got, real))


def test_the_response_register_defaults_to_off_everywhere():
    """Four declarations and one instantiation, and every one of them has
    to default to the SoC that `docs/47` to `docs/49` measured. `docs/50`
    section 6 is the reason: the registered memory is slower on the
    bring-up workload than the unregistered one is, at every clock the
    layout can reach, so `MEM_RDREG = 1` is a measurement configuration
    and not the design."""
    for path in ("hw/soc/rtl/soc_mem.v", "hw/soc/rtl/soc_mem_sram.v"):
        text = (ROOT / path).read_text()
        assert re.search(r"parameter\s+RDREG\s*=\s*1'b0", text), (
            "{}'s RDREG no longer defaults to 0".format(path))
    for marker in STANDIN_MARKERS:
        assert re.search(r"parameter\s+RDREG\s*=\s*1'b0", _standin(marker)), (
            "the {} in hw/soc/flow/syn_soc_top.sh no longer defaults RDREG "
            "to 0".format(marker.strip("/ ")))

    top = (SOC_RTL / "soc_top.v").read_text()
    assert re.search(r"parameter\s+MEM_RDREG\s*=\s*1'b0", top), (
        "soc_top.v's MEM_RDREG no longer defaults to 0")


def test_nothing_in_the_design_turns_the_response_register_on():
    """The knob exists in three flows and all three default it off.
    Nothing else
    in the repository may set it, and in particular no configuration file
    and no committed script may hard-code it on: the netlist that is
    hardened has to be the netlist whose cycle count is published."""
    # The three flows that OFFER the knob. Each defaults it to 0 and the
    # test above checks the defaults; what is forbidden is a fourth place
    # that sets it, or any of these three hard-coding it on.
    allowed = {
        SOC_FLOW / "syn_soc_top.sh",
        SOC_FLOW / "sim_soc.sh",
        SOC_FLOW / "fi_core.sh",
    }
    pattern = re.compile(r"SOC_MEM_RDREG\s*=\s*1|MEM_RDREG\s*\(\s*1'b1")
    offenders = []
    for path in list(ROOT.glob("hw/**/*.sh")) + list(ROOT.glob("hw/**/*.v")) \
            + list(ROOT.glob("hw/**/*.json")) + list(ROOT.glob("sw/**/*.py")):
        if path in allowed or "/runs/" in str(path) or "/out/" in str(path):
            continue
        if path == Path(__file__):
            continue
        # Comment lines are prose, not settings. Without this the check
        # fires on any file that merely EXPLAINS the knob, which turns a
        # guard into a reason not to document anything.
        body = "\n".join(
            line for line in path.read_text(errors="ignore").split("\n")
            if not line.lstrip().startswith(("#", "//"))
        )
        if pattern.search(body):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, (
        "these files turn the memory response register on: {}. It defaults "
        "to 0 and docs/50 recommends it stays there.".format(offenders))


def test_both_generate_arms_are_named_so_a_build_can_be_interrogated():
    """`docs/49` section 8.1 found that Icarus discards `-P` on a
    hierarchical path in silence, and the repair was to read the arm name
    out of the compiled object. That repair only works while the arms
    HAVE names, and while both memory files use the SAME names -- the
    check in flow/sim_soc.sh greps for one string whichever model is in
    the build."""
    for path in ("hw/soc/rtl/soc_mem.v", "hw/soc/rtl/soc_mem_sram.v"):
        text = (ROOT / path).read_text()
        for arm in ("g_rd1", "g_rd2"):
            assert re.search(r"begin\s*:\s*" + arm, text), (
                "{} has no generate arm called {}".format(path, arm))
    for marker in STANDIN_MARKERS[1:]:   # the stand-in only; the blackbox
        block = _standin(marker)         # has no body to put arms in
        for arm in ("g_rd1", "g_rd2"):
            assert re.search(r"begin\s*:\s*" + arm, block), (
                "the {} has no generate arm called {}".format(
                    marker.strip("/ "), arm))


def test_the_simulation_checks_that_the_parameter_override_took_effect():
    """The same obligation `test_soc_regfile_guards.py` puts on SYNPRE.
    A knob that looks applied and is not is the failure `docs/49` section
    8.1 recorded, and the defence is that flow/sim_soc.sh reads the
    elaborated design rather than trusting its own command line."""
    text = (SOC_FLOW / "sim_soc.sh").read_text()
    assert "check_arm" in text, (
        "flow/sim_soc.sh no longer has the compiled-object arm check")
    assert re.search(r"check_arm\s+SOC_MEM_RDREG", text), (
        "flow/sim_soc.sh no longer checks which memory arm it built")
    assert 'grep -qa' in text, (
        "flow/sim_soc.sh's arm check no longer reads the compiled object")


def test_the_fabric_probe_is_an_observer_and_nothing_else():
    """`hw/soc/tb/soc_bus_probe.v` is the evidence for the one protocol
    decision `docs/50` makes -- that the fabric needs no change -- and it
    is compiled into the design under test. A probe that drove anything
    would be changing the measurement it exists to make."""
    text = (SOC_TB / "soc_bus_probe.v").read_text()
    body = "\n".join(l for l in text.split("\n") if not l.strip().startswith("//"))
    for forbidden in ("force ", "release ", "assign ", "deposit"):
        assert forbidden not in body, (
            "hw/soc/tb/soc_bus_probe.v contains '{}': it is supposed to "
            "observe and nothing else".format(forbidden.strip()))
    # It may only write its own integers.
    lhs = set(re.findall(r"^\s*(\w+)\s*=", body, re.M))
    declared = set(re.findall(r"^\s*integer\s+([\w, ]+);", body, re.M))
    declared = {n.strip() for group in declared for n in group.split(",")}
    assert lhs <= declared, (
        "hw/soc/tb/soc_bus_probe.v assigns to {}, which are not its own "
        "counters".format(sorted(lhs - declared)))
    assert "SOC_PROBE" in (SOC_FLOW / "sim_soc.sh").read_text(), (
        "flow/sim_soc.sh no longer has a way to compile the probe in")
