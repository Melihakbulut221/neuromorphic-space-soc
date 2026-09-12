# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Do the three TMR structures survive into the netlist the foundry gets?

WHY THIS FILE EXISTS AND WHY IT IS NOT PART OF test_soc_synthesis_guards

`sw/tests/test_soc_synthesis_guards.py` synthesises each block on its
own, with this repository's own yosys recipe, and counts flip-flops by
the INSTANCE PATH a flattened cell name carries. `docs/75` section 3
re-measured every replica count that file has ever published --
`docs/41`'s 22, `docs/55`'s 21, `docs/56`'s 25, `docs/69`'s 23 -- with
an instrument that depends on no name at all, and every one of them was
right. The instance-path census is exact **in that flow**, because
`flatten` runs after `dfflibmap` there, so the flip-flop `dfflibmap`
builds behind an inverter for a reset-to-one bit is created inside the
bank module and is prefixed like every other cell in it.

It is not exact in the flow that produces the part. LibreLane flattens
`soc_top` before it maps, and in
`hw/soc/pnr/runs/*/final/nl/soc_top.nl.v` every cell is `_00268_`: the
instance path is gone, and with it every existing guard's ability to
say which replica a flip-flop belongs to. `docs/41` section 6.6 said so
in its own list of what the census cannot see ("It examines `soc_wdog`
alone ... It says nothing about placement or routing"), `docs/55`,
`docs/56` and `docs/69` repeated it, and **until `docs/75` nothing in
this repository checked the shipped netlist at all.** `docs/74` was the
first document to look, and it looked by hand.

This file is that check, and it asks a question the count cannot:

  * every replica is the width the voter reads -- so nothing merged;
  * the three replicas are DISJOINT sets of flip-flops -- so the voter
    is reading three different banks and not one bank twice. Three
    banks of the right size are not three banks if the vote is a
    majority over two distinct values, and no per-replica flip-flop
    COUNT can tell the difference.

WHAT IT DOES **NOT** COVER

  * It reads whatever netlists the working tree has kept.
    `hw/soc/out/` and `hw/soc/pnr/runs/` are git-ignored build products
    (.gitignore, `docs/38` section 11's rule), so on a fresh clone
    there is nothing to read and these tests SKIP with the command that
    regenerates them. A skip here is not evidence of anything.
  * It counts and partitions flip-flops. It says nothing about whether
    the three banks store the right function, which is
    `hw/soc/formal/soc_wdog_tmr.sby`, nor about whether the voter is
    the frozen one, which is
    `test_the_voter_is_the_blob_the_pilot_freeze_pins`.
  * It says nothing about timing, DRC, LVS or equivalence. The layouts
    it may read have none of those (`docs/71` section 11).
  * IT SAYS NOTHING ABOUT PLACEMENT, which is the one thing it reads a
    place-and-route run and still cannot see. It walks a netlist; where
    the cells ended up is in the DEF beside it.
    `sw/tests/test_replica_placement.py` is that level and it measures
    the replica banks as not separated. Added 2026-09-09, because a
    green result here reads as covering the part and does not.
  * The cone stops at flip-flops and at macros. A replica held in an
    SRAM macro would be invisible, and none is.

Run with the repository-root suite::

    .venv/bin/python -m pytest sw/tests/test_soc_shipped_netlist_guards.py
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GL_NETLIST = ROOT / "hw" / "soc" / "fi" / "gl_netlist.py"

# The widths are DERIVED from the RTL, by the same functions the
# block-level guards derive them with, so that widening a protected word
# moves this file's expectation with it. Importing that module also
# means there is one derivation of each width in the tree and not two.
_spec = importlib.util.spec_from_file_location(
    "soc_synthesis_guards", Path(__file__).with_name(
        "test_soc_synthesis_guards.py"))
_G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_G)

_gspec = importlib.util.spec_from_file_location("gl_netlist", GL_NETLIST)
GL = importlib.util.module_from_spec(_gspec)
_gspec.loader.exec_module(GL)

# structure key -> (what it is, expected width, the document that
# published a replica count for it)
STRUCTURES = {
    "wdog": ("the watchdog's protected word", _G.PROT_W, "docs/41"),
    "boot": ("the boot block's decision word", _G.BOOT_PROT_W, "docs/69"),
    "npu":  ("the NPU cause bank", _G.NPU_PROT_W, "docs/55 and docs/56"),
}

# The command is NAMED rather than spelled out. Writing it here would
# put the literal `SOC_ROM_HARDEN=0` into a tracked file, and
# test_the_memory_protection_defaults_on_and_nothing_turns_it_off in
# sw/tests/test_soc_memory_guards.py exists to make exactly that
# expensive -- which is the right behaviour and is how this comment came
# to be written.
REGENERATE = ("hw/soc/flow/syn_soc_top.sh, then hw/soc/flow/pnr_soc_top.sh "
              "for a layout; docs/75 section 11 gives both command lines "
              "with the environment they need")

# WIDTHS THESE WORDS USED TO CARRY, so that "this netlist predates a
# widening" and "something removed bits from a shipped netlist" stop
# looking identical to this file.
#
# Every path under hw/soc/pnr/runs/ and hw/soc/out/ is a git-ignored
# build product, so the retained netlists are whatever the machine last
# hardened -- and when the RTL gains a protected bit, every one of them
# is instantly narrower than the RTL. Without this table the guard goes
# red on a correct widening and stays red until someone spends
# seventeen hours re-hardening, which is how a guard gets deleted.
#
# A width is added here ONLY with the change that retired it, its date
# and its reason. A netlist at a width that is neither current nor
# listed is still an error, and always will be.
RETIRED_WIDTHS = {
    "npu": {
        25: ("25 until 2026-09-12, when E_DECIDE's bound added the "
             "C_EVT_TO cause bit: NCAUSE 14 -> 15 widens both the sticky "
             "field and the mask, so PROT_W went 25 -> 27"),
    },
}


def _netlists():
    """Every whole-SoC netlist the working tree has kept, newest first.

    Both kinds are read: LibreLane's final netlist, which is the object
    closest to silicon, and the synthesis netlist it was placed from.
    `docs/74` section 2.2 measured that the two have identical
    flip-flops with identical instance names, so a disagreement between
    them here would itself be a finding."""
    out = []
    for p in (ROOT / "hw" / "soc" / "pnr" / "runs").glob(
            "*/final/nl/soc_top.nl.v"):
        out.append(p)
    for p in (ROOT / "hw" / "soc" / "out").glob("*/soc_top.netlist.v"):
        out.append(p)
    return sorted(out, key=lambda p: p.stat().st_mtime, reverse=True)


@pytest.fixture(scope="module")
def netlists():
    found = _netlists()
    if not found:
        pytest.skip(
            "no whole-SoC netlist in the working tree. hw/soc/out/ and "
            "hw/soc/pnr/runs/ are git-ignored build products, so there "
            "is nothing here to audit on a fresh clone. Regenerate "
            "with:\n    " + REGENERATE)
    return found


def _census(path, which):
    return GL.tmr_census_named(str(path), which)


def _check(rows, what, width, where):
    sets = [set(r["cone_insts"]) for r in rows]
    for r in rows:
        assert r["width"] > 0, (
            "the cone census could not find replica {} of {} in {}: the "
            "net the voter reads is not in the netlist under any of the "
            "names it looked for. That is a census that FAILED and must "
            "not be read as a replica that merged."
            .format(r["bank"], what, where))
    got = {r["width"] for r in rows}
    assert len(got) == 1, (
        "{} in {}: the three replicas present {} to the voter, and three "
        "replicas of one word cannot be three different widths"
        .format(what, where, sorted(got)))
    w = got.pop()
    for r in rows:
        assert r["cone"] == w, (
            "replica {} of {} in {}: the voter reads {} bits from it and "
            "the fan-in cone of those bits holds {} flip-flops, not {}. "
            "A replica with fewer flip-flops than bits is a replica part "
            "of which was merged into another -- which is what "
            "hw/rtl/pilot_top.v section 9 records happening to the "
            "pilot's configuration TMR, and what every functional test "
            "and every proof in this repository would pass on."
            .format(r["bank"], what, where, r["width"], r["cone"], w))
    for i in range(3):
        for j in range(i + 1, 3):
            shared = sets[i] & sets[j]
            assert not shared, (
                "replicas {} and {} of {} in {} SHARE {} of their {} "
                "flip-flops. The vote above them is then a majority over "
                "fewer than three distinct values and a single upset in "
                "the shared storage is not masked."
                .format(rows[i]["bank"], rows[j]["bank"], what, where,
                        len(shared), w))
    assert len(set().union(*sets)) == 3 * w
    return w


@pytest.mark.parametrize("which", sorted(STRUCTURES))
def test_every_replica_in_every_retained_netlist_is_a_disjoint_cone(
        netlists, which):
    what, width, doc = STRUCTURES[which]
    seen = 0
    current = 0
    predating = []
    for path in netlists:
        rows = _census(path, which)
        if not any(r["width"] for r in rows):
            # A netlist of a configuration that does not contain this
            # block at all -- a HARDEN = 0 build, or one synthesised
            # without the NPU. Skipping it is right; skipping ALL of
            # them is not, and the count below is what says so.
            continue
        seen += 1
        w = _check(rows, what, width, path.name + " (" + path.parent.name
                   + ")")
        if w == width:
            current += 1
            continue
        # NOT THE CURRENT WIDTH. Two very different things look like
        # this and the guard has to tell them apart, which is why
        # RETIRED_WIDTHS exists rather than a tolerance.
        assert w in RETIRED_WIDTHS.get(which, {}), (
            "{} is {} bits in {} and the RTL says {}, and {} is not a "
            "width this word has\never carried. If the protected word "
            "was widened, declare the old width in\nRETIRED_WIDTHS with "
            "its date and the commit. If it was not, something REMOVED "
            "bits\nfrom a shipped netlist, which is the defect this file "
            "exists for.".format(what, w, path, width, w))
        predating.append((path, w))
    if not seen:
        pytest.skip("no retained netlist contains {} ({})".format(what, doc))

    # Amber, not green, and printed rather than swallowed: a run where
    # EVERY retained netlist predates the RTL is a run where this guard
    # checked the disjointness of three cones in a design the tree no
    # longer produces. That is exactly the state docs/60 section 9 and
    # paper/main.tex section 2 carry markers for, and it should be
    # visible here too rather than inferred from those.
    if predating:
        why = RETIRED_WIDTHS[which]
        print("\n{}: {} of {} retained netlists predate a widening of {}."
              .format(which, len(predating), seen, what))
        for path, w in predating:
            print("  {} bits in {} -- {}".format(
                w, path.parent.name, why.get(w, "no reason recorded")))
        if not current:
            print("  NONE is at the RTL's current {} bits. The "
                  "disjointness below is proved on a design\n  the tree "
                  "no longer produces. Regenerate with: {}".format(
                      width, REGENERATE))


def test_the_name_census_undercounts_and_the_cone_does_not(netlists):
    """The measurement `docs/74` section 6.6 made, kept as an assertion.

    Half of each mixed replica resets to one, `sg13g2` has no set
    flip-flop, `dfflibmap` builds one as a reset-to-zero flip-flop
    behind an inverter, and the cell that results is not the cell that
    carried the name -- so a census by Q-NET NAME reports 29 + 14 + 15
    where the truth is 29 + 29 + 29. That number is not a defect to be
    fixed: it is the reason this file's instrument is a cone, and it is
    asserted here so that a future PDK with a set flip-flop, which would
    make the two agree, is noticed rather than assumed.

    It is deliberately NOT asserted as an exact split. `POL_B` and
    `POL_C` decide which bits invert, so the 14/15 follows from the
    masks; what is asserted is the direction and the total."""
    checked = 0
    for path in netlists:
        rows = _census(path, "wdog")
        if not any(r["width"] for r in rows):
            continue
        checked += 1
        a, b, c = rows
        assert a["by_q_net"] == a["cone"] == _G.PROT_W, (
            "replica A stores the word unmixed at POL 0, so its "
            "flip-flops ARE the voter's input and both instruments "
            "should agree on it: {}".format(a))
        assert b["by_q_net"] + c["by_q_net"] == _G.PROT_W, (
            "the two mixed replicas should between them keep exactly "
            "one name per bit of the word -- POL_B is the complement of "
            "POL_C -- and they keep {} + {}"
            .format(b["by_q_net"], c["by_q_net"]))
        for r in (b, c):
            assert r["by_q_net"] < r["cone"], (
                "replica {} is fully named in {}. That is not a failure "
                "-- it would mean the technology no longer needs an "
                "inverter for a reset-to-one bit -- but docs/74 section "
                "6.6 and docs/75 section 3 are written against the "
                "opposite, and a reader should be told."
                .format(r["bank"], path))
    if not checked:
        pytest.skip("no retained netlist contains the watchdog")


def test_the_cone_census_fails_on_a_netlist_whose_replicas_were_merged(
        netlists, tmp_path):
    """A guard that does not fail on a merged design is not a guard.

    The mutation is made on a SCRATCH COPY of a retained netlist and it
    is the merge itself rather than a proxy for one: every flip-flop the
    voter reads through `qc` has its Q net renamed to the corresponding
    flip-flop's net in replica B, which is exactly what `opt_merge`
    leaves behind when two replicas present the same storage function --
    one bank, read twice. The flip-flop COUNT of the mutant is
    unchanged, which is the point.
    """
    src = None
    for path in netlists:
        if any(r["width"] for r in _census(path, "wdog")):
            src = path
            break
    if src is None:
        pytest.skip("no retained netlist contains the watchdog")

    rows = _census(src, "wdog")
    nl = GL.StructuralNetlist(str(src))
    b_q = [nl.q_name(i) for i in sorted(rows[1]["cone_insts"])]
    c_q = [nl.q_name(i) for i in sorted(rows[2]["cone_insts"])]
    assert len(b_q) == len(c_q) == _G.PROT_W

    text = src.read_text()
    # Rename by descending name length so that no replacement is a
    # prefix of a later one.
    for old, new in sorted(zip(c_q, b_q), key=lambda p: -len(p[0])):
        assert old != new
        text = text.replace(old, new)
    mutant = tmp_path / "merged.nl.v"
    mutant.write_text(text)

    # The flip-flops are all still there: this is a merge of what the
    # voter READS, and a count cannot see it.
    assert len(GL.parse(str(mutant))[0]) == len(GL.parse(str(src))[0])

    mrows = _census(mutant, "wdog")
    with pytest.raises(AssertionError) as caught:
        _check(mrows, "the mutant's protected word", _G.PROT_W, "the mutant")

    # WHICH of _check's assertions fires is not asserted, and that is
    # deliberate. Renaming a Q net onto another flip-flop's leaves two
    # cells driving one net; the parse takes the last, so some of the
    # mutant's cones come back SMALLER rather than overlapping, and
    # pinning the message would be pinning that arbitration rather than
    # the property. What is asserted is the property: the three cones no
    # longer cover 3 x PROT_W distinct flip-flops.
    union = set().union(*[set(r["cone_insts"]) for r in mrows])
    assert len(union) < 3 * _G.PROT_W, (
        "the merged mutant still presents {} distinct flip-flops to the "
        "voter, so it does not model a merge and this test proves "
        "nothing".format(len(union)))
    assert "merged" in str(caught.value) or "SHARE" in str(caught.value), \
        str(caught.value)


def test_every_asynchronous_reset_is_driven_by_a_flip_flop_that_dominates_it(
        netlists):
    """W9 on the shipped netlist, structurally.

    `docs/75` section 6 measured this over the whole SoC and it is the
    sharpest single number in that document: of the FIVE distinct
    asynchronous-reset fan-in source sets in `soc_top`, four are driven
    by nothing (the power-on port) or by one or two REGISTERED signals
    -- `rst_sys_n`, `u_npu.flush_pulse`, `u_npu.u_node0.soft_rst` -- and
    a flip-flop's output does not glitch. The fifth is `rst_raw_n`, the
    net every flip-flop in the SoC is ultimately held in reset by, and
    its combinational fan-in is **25 flip-flops of the watchdog's three
    replica banks**: five of A (bits 17 to 21, `rst_hold`) and ten each
    of B and C, whose mixed decode needs two stored bits per decoded
    bit. Nothing else is in it.

    What this asserts is the property, not the count: the one reset
    whose fan-in is a decode rather than a register must have W9's
    `in_reset_q` in that decode. It is a STRUCTURAL check and it is
    weaker than the SAT proof in
    test_no_transient_of_the_voted_word_can_reach_the_system_reset --
    the flip-flop being present in the cone does not by itself make it
    dominate -- and it is here because it is the only form of the
    question that can be asked of a netlist this file did not
    synthesise.
    """
    # ONLY netlists synthesised after the RTL was last edited. The
    # working tree keeps every build any session ever made -- 60-odd of
    # them here -- and most predate W9 by weeks; asserting a property of
    # today's RTL over an artifact of an older one would fail for the
    # right reason with the wrong message. The replica census above
    # deliberately does NOT filter this way: no wave has changed a
    # replica width, so every retained netlist is still evidence about
    # that, and 65 netlists agreeing is worth more than one.
    cutoff = (ROOT / "hw" / "soc" / "rtl" / "soc_wdog.v").stat().st_mtime
    fresh = [p for p in netlists if p.stat().st_mtime >= cutoff]
    if not fresh:
        pytest.skip(
            "no netlist in this tree was written after hw/soc/rtl/"
            "soc_wdog.v was last modified, so none of them can be "
            "evidence about W9. Regenerate with:\n    " + REGENERATE)

    checked = 0
    for path in fresh:
        groups = GL.reset_cones(str(path))
        wide = [g for g in groups if len(g["sources"]) > 2]
        if not wide:
            continue
        checked += 1
        assert len(wide) == 1, (
            "{}: {} asynchronous resets in this netlist are driven by a "
            "decode of more than two flip-flops. docs/75 found exactly "
            "one, the watchdog's, and a second is a second place where a "
            "combinational transient can reset the part: {}"
            .format(path, len(wide),
                    [sorted(set(g["sources"])) for g in wide]))
        src = wide[0]["sources"]
        named = sorted(set(n for n in src if not n.startswith("_")))
        assert any("u_prot_" in n for n in named), (
            "{}: the one wide reset cone is not the watchdog's; docs/75's "
            "reading of this netlist does not apply to it: {}"
            .format(path, named))
        assert any(n.endswith("in_reset_q") for n in named), (
            "{}: the system reset is driven by a combinational decode of "
            "{} flip-flops of the watchdog's replica banks and W9's "
            "in_reset_q is NOT among them. That is the pre-docs/75 "
            "design: docs/74 section 10.2 measured it restarting the SoC "
            "on 174 of 174 upsets the voter had already corrected. If "
            "this netlist simply predates docs/75, regenerate it:\n    "
            "{}".format(path, len(src), REGENERATE))
    if not checked:
        pytest.skip("no retained netlist has an asynchronous reset driven "
                    "by more than two flip-flops")


def test_the_cone_walker_stops_at_every_flip_flop(netlists):
    """The one way this instrument could overcount, asserted.

    `cone_flops` returns a flip-flop and does not walk through it. If it
    walked past a sequential cell it did not recognise it would report
    the storage BEHIND a replica as part of it, and every count in
    docs/75 would be too large. So: every instance the cone returns is a
    flip-flop this parse knows about, and the sets are the size the
    voter's input is wide."""
    for path in netlists:
        rows = _census(path, "wdog")
        if not any(r["width"] for r in rows):
            continue
        flops, _ = GL.parse(str(path))
        known = {f.inst: f.cell for f in flops}
        for r in rows:
            for inst in r["cone_insts"]:
                assert inst in known, (
                    "the cone returned {}, which this file's parse does "
                    "not know to be a flip-flop".format(inst))
                assert GL.is_flop(known[inst])
        return
    pytest.skip("no retained netlist contains the watchdog")
