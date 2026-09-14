# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

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

import json
import pathlib
import re
import subprocess
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


# =====================================================================
# docs/67: the codec, the scrubber and the SCRUB block
# =====================================================================
#
# Textual guards, complementary to the census in
# test_soc_synthesis_guards.py rather than a weaker version of it. The
# census proves the encoders, the decoders and the scrubber's state
# EXIST in the mapped netlist; these prove they are wired the way round
# that protects, that the protection cannot be switched off by an
# instantiation, and that the reports reach the block that counts them.
# Every wrong-way-round edit below is functionally invisible in a
# fault-free machine, which is why a text check and not a simulation is
# what stands between it and silicon.

SOC_TB = ROOT / "hw" / "soc" / "tb"
PILOT_RTL = ROOT / "hw" / "rtl"


def _ecc_text():
    return (SOC_RTL / "soc_mem_ecc.v").read_text()


def test_the_codec_is_read_from_hw_rtl_and_not_copied_into_the_memory():
    """One SECDED codec in this repository. The memory files instantiate
    hw/rtl/secded_enc.v and secded_dec.v and carry no H row of their
    own; every flow that builds them reads the two files out of hw/rtl/,
    which docs/34 freezes and nothing here modifies."""
    for name in ("soc_mem_ecc.v", "soc_mem.v", "soc_mem_sram.v", "soc_scrub.v"):
        text = "\n".join(l.split("//")[0] for l in
                         (SOC_RTL / name).read_text().splitlines())
        assert "H_ROW" not in text, (
            "{} carries an H row of its own: the codec is read from "
            "hw/rtl/ and never copied".format(name))
    ecc = _ecc_text()
    assert "secded_enc u_enc" in ecc and "secded_dec u_dec" in ecc
    assert "secded_enc u_init_enc" in (SOC_RTL / "soc_mem.v").read_text(), (
        "soc_mem.v no longer derives the ROM's check bits from the frozen "
        "encoder at load")
    for flow in ("sim_soc.sh", "fi_core.sh", "fi_npu.sh"):
        text = (SOC_FLOW / flow).read_text()
        assert "soc_mem_ecc.v" in text and "soc_scrub.v" in text, (
            "hw/soc/flow/{} does not read the memory codec or the SCRUB "
            "block".format(flow))
    for name in ("secded_enc.v", "secded_dec.v"):
        assert not (SOC_RTL / name).exists(), (
            "a copy of {} appeared under hw/soc/rtl/".format(name))


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


def test_the_memory_protection_defaults_on_and_nothing_turns_it_off():
    """The same rule the watchdog's, the CLINT's and the NPU's HARDEN
    carry: a parameter that can turn a defence off is a parameter
    someone turns off. MEM_HARDEN defaults to 1 in soc_top.v, both
    memory files default HARDEN to 1, soc_top passes MEM_HARDEN through
    and nothing else, and no committed flow, config or test hard-codes
    it to 0 outside the three measurement knobs."""
    top = (SOC_RTL / "soc_top.v").read_text()
    assert re.search(r"parameter\s+integer\s+MEM_HARDEN\s*=\s*1\b", top)
    assert re.search(r"parameter\s+integer\s+ROM_HARDEN\s*=\s*MEM_HARDEN\b", top)
    assert ".HARDEN(MEM_HARDEN), .ECC_BYTE(1'b1)) u_ram" in top
    assert ".HARDEN(ROM_HARDEN), .ECC_BYTE(1'b0)) u_rom" in top
    for name in ("soc_mem.v", "soc_mem_sram.v", "soc_mem_ecc.v"):
        text = (SOC_RTL / name).read_text()
        assert re.search(r"parameter\s+integer\s+HARDEN\s*=\s*1\b", text), (
            "{}'s HARDEN no longer defaults to 1".format(name))
    allowed = {SOC_FLOW / "syn_soc_top.sh", SOC_FLOW / "sim_soc.sh",
               SOC_FLOW / "fi_core.sh"}
    pattern = re.compile(r"SOC_MEM_HARDEN\s*=\s*0|SOC_ROM_HARDEN\s*=\s*0"
                         r"|MEM_HARDEN\s*\(\s*0\s*\)|ROM_HARDEN\s*\(\s*0\s*\)"
                         r"|MEM_HARDEN\s*=\s*0")
    offenders = []
    for path in (list(ROOT.glob("hw/**/*.sh")) + list(ROOT.glob("hw/**/*.v"))
                 + list(ROOT.glob("sw/**/*.py"))):
        if path in allowed or "/runs/" in str(path) or "/out/" in str(path) \
                or "/ext/" in str(path) or "/gen" in str(path):
            continue
        if path == Path(__file__):
            continue
        body = "\n".join(
            line for line in path.read_text(errors="ignore").split("\n")
            if not line.lstrip().startswith(("#", "//")))
        if pattern.search(body):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, (
        "these files turn the memory protection off: {}".format(offenders))
    # This used to read "config-ecc.json is the ONE configuration that
    # names ROM_HARDEN=0" and open only that file. Six configurations
    # name it -- config-ecc, config-ecc-clint, config-ecc-clint2,
    # config-timing, config-timing-drv, config-timing-ptd -- so the
    # assertion below passed while saying nothing about five of them.
    # That is this corpus's signature failure, a green check read wider
    # than what it opened, sitting inside the guard written to stop it.
    # Corrected 2026-09-13. The guard now finds them BY THE PROPERTY
    # instead of by name, and holds every one of them to two rules.
    # TRACKED configs only, and the reason is a defect this guard shipped
    # with. The first version walked the glob and asserted `len >= 6`,
    # which is what the developer's working tree happens to hold --
    # config-ecc-clint.json and config-ecc-clint2.json are git-ignored
    # scratch. The public mirror carries tracked files only, so it has
    # four, and the guard failed there while passing here: a check that
    # encodes one machine's untracked state is not a check. Caught by the
    # pre-publication audit of 2026-09-14, before the mirror was pushed.
    tracked = _tracked_pnr_configs()
    rom0 = []
    for path in sorted((ROOT / "hw" / "soc" / "pnr").glob("config*.json")):
        if path.name == "config.resolved.json" or path.name not in tracked:
            continue
        cfg = json.loads(path.read_text())
        params = cfg.get("SYNTH_PARAMETERS") or []
        if "ROM_HARDEN=0" not in params:
            continue
        rom0.append(path.name)
        # 1. It is DECLARED, never smuggled in beside other parameters.
        assert params == ["ROM_HARDEN=0"], (
            "{} hides ROM_HARDEN=0 among {}".format(path.name, params))
        # 2. With the ROM unhardened the RTL does not instantiate the
        #    512x16 check macros, so a config that turns the protection
        #    off must not also place them. Before 2026-09-13 no config
        #    could place them at all and this could not be violated;
        #    config-ecc-rom.json now can, which is exactly why the rule
        #    has to be written down.
        for kind, macro in (cfg.get("MACROS") or {}).items():
            if "512x16" in kind:
                assert not (macro.get("instances") or {}), (
                    "{} sets ROM_HARDEN=0 and still places {}".format(
                        path.name, kind))
    # A census, not a magic number: every tracked config that names
    # ROM_HARDEN=0 must be one of these, and all four must be present.
    # If a new one appears it has to be added here deliberately, which is
    # the point -- turning the ROM's protection off is a decision.
    assert set(rom0) == {"config-ecc.json", "config-timing.json",
                         "config-timing-drv.json", "config-timing-ptd.json"}, (
        "the set of tracked configs naming ROM_HARDEN=0 has moved: {}. "
        "Turning the ROM's protection off is a deliberate act; add it here "
        "with its reason rather than widening this assertion.".format(
            sorted(rom0)))
    # And the converse: the configuration that DOES place the check
    # macros must not be unhardening the ROM.
    eccrom = ROOT / "hw" / "soc" / "pnr" / "config-ecc-rom.json"
    if eccrom.exists():
        cfg = json.loads(eccrom.read_text())
        assert "ROM_HARDEN=0" not in (cfg.get("SYNTH_PARAMETERS") or [])
        placed = sum(len(m.get("instances") or {})
                     for k, m in cfg["MACROS"].items() if "512x16" in k)
        assert placed == 2, (
            "config-ecc-rom.json places {} check macros, not 2".format(placed))


def test_the_codec_corrects_on_every_path_that_reads_a_row():
    """The wrong-way-round edits, forbidden by text.

      * the encoders cover `enc_in`, which is the bus word on a bus
        cycle and the CORRECTED word on a scrub write-back -- encoding
        the raw row would launder an upset into a valid wrong codeword;
      * the read path returns the corrected word, never the raw row;
      * the scrubber writes back only lanes the decoder corrected and
        never an uncorrectable one;
      * an uncorrectable read answers with err;
      * every report line is derived, none is tied off."""
    ecc = _ecc_text()
    assert "wire [31:0] enc_in = req_i ? wdata_i : rd_word;" in ecc
    assert ".data_in   ({56'h0, enc_in[8*l +: 8]})," in ecc
    assert ".data_in   ({32'h0, enc_in})," in ecc
    assert "assign rd_word[8*l +: 8] = row_dout_i[8*l +: 8] ^ mask;" in ecc
    assert "assign rd_word  = row_dout_i[31:0] ^ mask;" in ecc
    assert "assign bm_wb[8*l +: 8]        = {8{sec[l]}};" in ecc
    assert "assign bm_wb[32+8*l +: 8]     = {8{sec[l]}};" in ecc
    assert "assign s_wb   = s_hit && sec_any;" in ecc
    assert "wire err0 = er0 || (rsp_rd && ded_any);" in ecc
    assert "assign sec_o      = s_wb;" in ecc
    assert "assign rd_o       = rsp_rd && sec_any;" in ecc
    assert "assign ded_o      = (rsp_rd || s_hit) && ded_any;" in ecc
    # The raw row reaches nothing but the decoders, the correction XOR
    # and the plain arm.
    for line in ecc.splitlines():
        code = line.split("//")[0]
        if "row_dout_i" not in code or "input" in code:
            continue
        assert ("secded_dec" in code or ".code_in" in code
                or "^ mask" in code or "g_dec_plain" in code
                or "assign rd_word = row_dout_i[31:0];" in code), (
            "the raw row is read somewhere the correction does not "
            "cover:\n  " + code.strip())


def test_the_scrubber_never_takes_the_port_from_the_bus():
    """The back-door port's whole argument: a scrub read only in an idle
    cycle, a write-back only in an idle cycle, and the bus's request
    owning every row-port signal in its own cycle."""
    ecc = _ecc_text()
    assert "assign s_go   = s_due && idle && !srd_q;" in ecc
    assert "assign s_hit  = srd_q && idle;" in ecc
    assert "assign row_addr_o = req_i ? bus_row : sptr_w;" in ecc
    assert "assign row_bm_o   = req_i ? bm_bus  : bm_wb;" in ecc
    assert "assign gnt_o = req_i;" in ecc
    assert "if (s_hit) sptr <= sptr +" in ecc


def test_the_reports_reach_the_scrub_block_and_its_line_is_wired():
    """Every event line of both memories arrives at soc_scrub.v, the
    scrubbers' control comes from it, and its interrupt is on the line
    the map assigns. pilot_top.v shipped four unconnected ECC status
    wires once; this is the check that neither memory does."""
    top = (SOC_RTL / "soc_top.v").read_text()
    for port, wire in (("sec_o", "ram_sec_ev"), ("rd_o", "ram_rd_ev"),
                       ("ded_o", "ram_ded_ev"), ("evt_addr_o", "ram_ded_addr"),
                       ("scrub_en_i", "scrub_ram_en"), ("scrub_ivl_i", "scrub_ivl")):
        assert re.search(r"\.%s\s*\(%s\)" % (port, wire), top), (
            "u_ram's {} is not wired to {}".format(port, wire))
    for port, wire in (("sec_o", "rom_sec_ev"), ("rd_o", "rom_rd_ev"),
                       ("ded_o", "rom_ded_ev"), ("evt_addr_o", "rom_ded_addr"),
                       ("scrub_en_i", "scrub_rom_en")):
        assert re.search(r"\.%s\s*\(%s\)" % (port, wire), top), (
            "u_rom's {} is not wired to {}".format(port, wire))
    for port, wire in (("ram_sec_i", "ram_sec_ev"), ("ram_rd_i", "ram_rd_ev"),
                       ("ram_ded_i", "ram_ded_ev"), ("ram_addr_i", "ram_ded_addr"),
                       ("rom_sec_i", "rom_sec_ev"), ("rom_rd_i", "rom_rd_ev"),
                       ("rom_ded_i", "rom_ded_ev"), ("rom_addr_i", "rom_ded_addr"),
                       ("ram_en_o", "scrub_ram_en"), ("rom_en_o", "scrub_rom_en"),
                       ("ivl_o", "scrub_ivl"), ("irq_o", "scrub_irq")):
        assert re.search(r"\.%s\s*\(%s\)" % (port, wire), top), (
            "u_scrub's {} is not wired to {}".format(port, wire))
    assert "irq_fast[SOC_IRQLINE_SCRUB]   = scrub_irq;" in top
    assert "soc_scrub #(.IVL_RST(SCRUB_IVL_RST)) u_scrub" in top


def test_the_scrubbers_ship_enabled():
    """docs/44 section 11's rule as a check: both enables reset to 1 in
    soc_scrub.v, the interval at reset is a named parameter soc_top.v
    sets, and the register that can stop a scrubber is in the system
    reset domain so a watchdog reset restores it."""
    scrub = (SOC_RTL / "soc_scrub.v").read_text()
    assert "ram_en_q <= 1'b1;" in scrub and "rom_en_q <= 1'b1;" in scrub
    assert "ivl_q    <= IVL_RST;" in scrub
    top = (SOC_RTL / "soc_top.v").read_text()
    assert re.search(r"parameter\s+\[15:0\]\s+SCRUB_IVL_RST\s*=\s*16'd255", top)
    assert "soc_scrub" in (SOC_FLOW / "syn_soc.sh").read_text()


def test_the_software_header_matches_the_block():
    """hw/soc/tb/sw/soc_scrub.h carries the offsets and bit numbers of
    soc_scrub.v; the two are compared here so a driver cannot read the
    wrong register."""
    scrub = (SOC_RTL / "soc_scrub.v").read_text()
    hdr = (SOC_TB / "sw" / "soc_scrub.h").read_text()
    regs = dict(re.findall(r"localparam \[11:0\] REG_(\w+)\s*=\s*12'h([0-9A-Fa-f]+);", scrub))
    for name, off in regs.items():
        m = re.search(r"#define SCR_%s\s+\(SOC_SCRUB_BASE \+ 0x([0-9A-Fa-f]+)u\)" % name, hdr)
        assert m, "soc_scrub.h has no SCR_{}".format(name)
        assert int(m.group(1), 16) == int(off, 16), (
            "SCR_{} is at 0x{} in the header and 0x{} in the RTL".format(
                name, m.group(1), off))
    bits = dict(re.findall(r"localparam integer S_(\w+)\s*=\s*(\d+);", scrub))
    for name, idx in bits.items():
        m = re.search(r"#define SCR_S_%s\s+\(1u << (\d+)\)" % name, hdr)
        assert m and int(m.group(1)) == int(idx), (
            "SCR_S_{} disagrees between the header and the RTL".format(name))


def test_the_pnr_floorplans_name_the_arms_the_rtl_has():
    """Several floorplans, several sets of instance paths, one wrapper.
    docs/47's config.json names the two-words-per-row arm; docs/67's
    config-ecc.json names the codec arm for the RAM and docs/47's for the
    ROM; config-ecc-rom.json names the codec arm throughout and PLACES
    the ROM's two check macros. Every path must be an arm
    soc_mem_sram.v still has, because a floorplan that names a label the
    RTL lost dies 35 steps into a run.

    Widened 2026-09-13. This used to iterate a hard-coded tuple of three
    config names, so the two configurations that actually place the
    check macros -- the whole point of the guard -- were outside it. It
    now walks every tracked config, which is the only version of this
    check that a new floorplan cannot be added behind."""
    sram = (SOC_RTL / "soc_mem_sram.v").read_text()
    labels = set(re.findall(r"begin\s*:\s*(g_r[ao]m_\w+)", sram))
    tracked = _tracked_pnr_configs()
    # docs/79's LVS arms are 2026-09-10 experiment snapshots and docs/64
    # keeps them as they were run; they predate the check macros.
    FROZEN = {"config.resolved.json"} | {
        n for n in tracked if n.startswith("config-lvs-") and "ecc" not in n}
    seen = 0
    for cfg in sorted((ROOT / "hw" / "soc" / "pnr").glob("config*.json")):
        if cfg.name not in tracked or cfg.name in FROZEN:
            continue
        seen += 1
        c = json.loads(cfg.read_text())
        for macro, spec in c["MACROS"].items():
            for inst in spec["instances"]:
                outer, block, leaf = inst.split(".")
                assert block in labels, (
                    "{} places {} but soc_mem_sram.v has no arm {}".format(
                        cfg.name, inst, block))
                body = sram.split("begin : " + block, 1)[1].split("\n  end", 1)[0]
                assert re.search(re.escape(macro) + r"\s+" + re.escape(leaf) + r"\b", body), (
                    "{} places {} as {} but that arm does not "
                    "instantiate it".format(cfg.name, inst, macro))
    assert seen >= 4, "the sweep found only {} configs".format(seen)
    # config-ecc.json builds through ROM_HARDEN=0, so its check macro
    # entry must stay empty; config-ecc-rom.json is the one that fills
    # it. The paired rule lives in the ROM_HARDEN guard above.
    ecc = json.loads((ROOT / "hw" / "soc" / "pnr" / "config-ecc.json").read_text())
    chk = ecc["MACROS"]["RM_IHPSG13_1P_512x16_c2_bm_bist"]
    assert chk["instances"] == {}, (
        "config-ecc.json builds through ROM_HARDEN=0, so the RTL does not "
        "instantiate the check macros and this floorplan must not place them")
    assert (ROOT / "hw" / "soc" / "pnr" / "RM_IHPSG13_1P_512x16_c2_bm_bist_bb.v").is_file()
