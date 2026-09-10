#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Pin, by SHA-256, the run outputs this corpus's documents cite and git ignores.

WHY THIS EXISTS. `docs/71`, `docs/74`, `docs/75`, `docs/77` and `docs/79`
are built on artefacts that are not in the repository and never will be:
`runs/` (`.gitignore:4`), `hw/openlane/*/runs/` (`:40`),
`hw/soc/out/` (`:74`), `hw/soc/pnr/runs/` (`:118`) and `formal/eqy/out/`
(`:136`) are ignored on purpose, because one SoC layout is about 190 MB
and there are six of them. The consequence, stated by an external
review of this corpus on 2026-09-09, is sharp:

    a reader can verify that the guards work and cannot verify that
    anything was ever wrong -- the pre-fix netlist is untracked.

Every counterfactual in this project lives in an ignored directory. The
unrepaired layout `s71boot` that restarts on all 174 injections
(`docs/75` section 8.3), the four record CSVs of the two-by-two that
makes the reset a property of the RTL rather than of the mapping
(section 8.5), the two clock-gate layouts whose difference `docs/77`
section 9.3 decomposes -- none of them is in git. If any of them were
quietly replaced, nothing in the tree would notice.

This script does not fix that. It does the cheap part of it: it walks the
run trees and campaign outputs the documents name, and writes a TRACKED
manifest holding, for each artefact, its path, its size in bytes, its
SHA-256, and a handful of metrics read out of the artefact itself. The
artefacts stay ignored; their identity becomes a committed fact.

WHAT A DIGEST IS WORTH, AND WHAT IT IS NOT. `docs/80-artefact-digests.md`
says this at length and it is the point of the whole exercise, so it is
repeated here where someone reading the code will see it: a digest proves
IDENTITY, not CORRECTNESS. It says that the file the author measured is
the file the author still has. It does not say the file is right, and a
reader who cannot obtain the file cannot check any claim made about it --
only that the author did not swap it afterwards.

USAGE

    scripts/artefact_digests.py                 # --check, the default
    scripts/artefact_digests.py --check         # re-verify against disk
    scripts/artefact_digests.py --write         # rebuild the manifest
    scripts/artefact_digests.py --list          # groups, and what is on disk

MISSING IS NOT FAILED. This is the same rule `sw/tests/test_flow_evidence.py`
states in its docstring and for the same reason: run outputs are ignored,
so a fresh clone has NONE of them, and a check that failed there would be
a check nobody could run. `--check` therefore has three outcomes per row:

    VERIFIED   the file is on disk and its bytes hash to the pinned digest
    MISSING    the file is not on disk. Expected on a clone. Exit 0
    CHANGED    the file is on disk and does NOT hash to the pinned digest

and exits non-zero only for CHANGED. A whole manifest of MISSING prints
one line saying so and succeeds, because that is what a clone looks like.

A fourth outcome, EXTRACTOR, is reported when the bytes match but the
metrics recomputed from them do not match the pinned ones. That can only
mean this script's own extractors changed, so it is called what it is
rather than blamed on the artefact. It exits non-zero too: a manifest
whose metric columns no longer describe its own digests is not a record.

--write REFUSES TO SHRINK the manifest without --allow-shrink, and prints
what it would drop. Running --write on a machine that has only half the
run tree would otherwise silently delete half the evidence record, which
is precisely the thing this file was written to prevent.

WHAT IS COVERED, AND HOW IT WAS CHOSEN. The GROUPS table below is the
list, and every entry names the documents that cite it. It was built by
reading those documents for the paths they actually rest on, not by
walking the directories and taking everything: `hw/soc/out/` holds 90-odd
build directories and most of them are scaffolding for one probe.

TWO THINGS WERE WRONG WITH THAT TABLE ON 2026-09-10, AND BOTH ARE FIXED
HERE RATHER THAN NOTED.

  1. `paper/claims.yaml` said, above its section 8 block, that the deck
     and timing run directories "are gitignored build output, so these
     are pinned by digest in docs/80". They were not pinned at all. Not
     one of the seventeen directories section 8 rests on -- three deck
     runs, two bare-macro calibrations, seven LVS variants, three repair
     layouts, the OpenSTA sweep and the classifier that produced every
     classification -- appeared in the manifest, so the strongest
     numbers in the paper were the only ones with no seal on them.
     Eight groups at the end of GROUPS are that gap closed.

  2. The table pinned `signoff-6x2` and called it "the frozen pilot
     sign-off harden". `docs/34` section 3.1 has labelled that run
     SUPERSEDED since 2026-08-31: the freeze moved to `signoff-6x2-gated`
     and `submission-6x2-gated` when `docs/36` bound two more checker
     corner lists. The manifest was sealing the wrong tree. Both current
     runs are now pinned, both superseded runs are RETAINED with the word
     in their group name, and none of the four digests changed -- what
     was wrong was which of them the ledger called current.

The pilot rows also gained `final/pnl/`, which `_run` omits and `docs/34`
section 3.1 pins, because section 3.2's argument is about the netlist,
the POWERED netlist and the DEF being bit-identical across runs.

WHAT IS NOT COVERED is in `docs/80` section 5 and it is a long list. The
three that matter most here: the intermediate steps of a run (only
`final/`, `resolved.json` and -- since 2026-09-10, for the four timing
arms only -- the `*-openroad-stapostpnr` step are pinned, so a reader
still cannot check the router's per-iteration trajectory that `docs/71`
section 5.2 calls its sharpest evidence); the 13.3 GB of
`reports/drc.magic.lyrdb` the four deck runs wrote, which no document
cites and which duplicates the `.rpt` that is pinned; and everything
under `hw/tb/`, which is already tracked and needs no digest.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "docs" / "80-artefact-digests.tsv"

COLUMNS = ["group", "cites", "role", "path", "bytes", "sha256", "metrics"]


# ---------------------------------------------------------------------------
# What is pinned.
#
# Each group is (name, cites, what, [(role, glob), ...]). The glob is
# relative to the repository root and is resolved at --write time; a glob
# that matches nothing contributes nothing, which is how this file runs
# on a machine that kept some runs and not others.
# ---------------------------------------------------------------------------

def _run(tag):
    """The five artefacts of a LibreLane run that the documents cite.

    `final/` only. The step directories are 60-odd more and the reason
    they are not pinned is in `docs/80` section 5: `resolved.json` fixes
    the configuration, `final/metrics.json` fixes every number the
    sign-off tables quote, and the three files are what anyone would
    actually be handed.
    """
    return [
        ("netlist", f"{tag}/final/nl/*.nl.v"),
        ("def", f"{tag}/final/def/*.def"),
        ("gds", f"{tag}/final/gds/*.gds"),
        ("metrics", f"{tag}/final/metrics.json"),
        ("config", f"{tag}/resolved.json"),
    ]


def _pilot(tag):
    """A pilot harden, pinned as the SIX files `docs/34` section 3.1 pins.

    `_run` above omits `final/pnl/`. For the SoC that is right -- no
    document reads the powered netlist. For the pilot it is wrong:
    `docs/34` section 3.1 lists the powered netlist among the five
    checksums that make its freeze a freeze, and section 3.2's whole
    argument is that the netlist, the POWERED netlist and the DEF are
    bit-identical across the sign-off and submission runs while the GDS
    is not. A manifest that pinned two of those three could not carry
    that argument.
    """
    return [
        ("netlist", f"{PILOT}/{tag}/final/nl/*.nl.v"),
        ("netlist", f"{PILOT}/{tag}/final/pnl/*.pnl.v"),
        ("def", f"{PILOT}/{tag}/final/def/*.def"),
        ("gds", f"{PILOT}/{tag}/final/gds/*.gds"),
        ("metrics", f"{PILOT}/{tag}/final/metrics.json"),
        ("config", f"{PILOT}/{tag}/resolved.json"),
    ]


def _lvs(tag):
    """One Netgen LVS variant: the script that defines it, and its verdict.

    `lvs_script.lvs` is the file that MAKES this variant this variant --
    six configurations of the same comparison over the same layout --
    so it is pinned beside the report rather than left implicit in
    `config.json`. There is no `final/` here worth pinning: every one of
    these runs copies `s77gate`'s views forward unchanged -- verified,
    not assumed: `s77lvs-a` and `s77lvs-b` both carry
    `final/nl/soc_top.nl.v` at 50515ae4..., which is the digest already
    pinned for `soc-s77gate` -- so pinning them would add about 1.4 GB
    of duplicate rows for a layout the manifest already carries.
    """
    d = f"{PNR}/{tag}/01-netgen-lvs"
    return [
        ("text", f"{d}/COMMANDS"),
        ("text", f"{d}/lvs_script.lvs"),
        ("config", f"{d}/config.json"),
        ("log", f"{d}/netgen-lvs.log"),
        ("lvs", f"{d}/reports/lvs.netgen.rpt"),
    ]


def _magicdrc(tag, classified=True):
    """One Magic DRC deck run: the report, the log, and what it read.

    `state_in.json` is pinned because it is the file that says WHICH
    layout the deck was pointed at -- for both SoC runs it names
    `s77gate/final/gds/soc_top.gds` and `s77gate/final/def/soc_top.def`,
    and both of those are already pinned under `soc-s77gate`. That makes
    the chain from the layout section 7 measured to the deck result
    section 8 quotes a chain of digests rather than of assertions.
    `COMMANDS` does the same for the tool: it carries the pinned PDK
    version hash and the exact `magic` invocation.
    """
    items = [
        ("text", f"{PNR}/{tag}/COMMANDS"),
        ("config", f"{PNR}/{tag}/config.json"),
        ("config", f"{PNR}/{tag}/state_in.json"),
        ("drclog", f"{PNR}/{tag}/magic-drc.log"),
        ("text", f"{PNR}/{tag}/runtime.txt"),
        ("drcrpt", f"{PNR}/{tag}/reports/drc.magic.rpt"),
    ]
    if classified:
        items.insert(0, ("classification", f"{PNR}/{tag}/classification.txt"))
    return items


def _sta(tag):
    """The slow-corner sign-off STA of one layout.

    Every timing number in `paper/main.tex` section 8 is in these seven
    files: the worst path and its two minimum-strength gates in
    `max.rpt`, the 3,088 endpoints in `violator_list.rpt`, the
    `period_min = 24.68` in `clock.rpt`, and the 33 max-cap / 67
    max-slew counts in `summary.rpt`. The step index differs between
    runs -- 50 in `s77gate`, 49 in the three repair arms -- so the glob
    matches the step by name rather than by number.
    """
    d = f"{PNR}/{tag}/*-openroad-stapostpnr"
    c = f"{d}/nom_slow_1p08V_125C"
    return [
        ("sta", f"{d}/summary.rpt"),
        ("sta", f"{c}/clock.rpt"),
        ("sta", f"{c}/wns.max.rpt"),
        ("sta", f"{c}/tns.max.rpt"),
        ("sta", f"{c}/ws.max.rpt"),
        ("sta", f"{c}/violator_list.rpt"),
        ("sta", f"{c}/max.rpt"),
    ]


def _campaign(d, *names):
    return [(_role_of(n), f"{d}/{n}") for n in names]


def _role_of(name):
    if name.startswith("records") or name.endswith(".csv"):
        return "records"
    if name == "provenance.txt":
        return "provenance"
    if name.startswith("map."):
        return "map"
    if name.endswith(".v"):
        return "netlist"
    if name.endswith(".rpt"):
        return "report"
    if name.endswith(".log"):
        return "log"
    if name.endswith(".tsv"):
        return "table"
    return "text"


PILOT = "hw/openlane/pilot_ihp/runs"
PNR = "hw/soc/pnr/runs"
OUT = "hw/soc/out"

GROUPS = [
    # ---- the pilot, which is the thing that goes on a shuttle ----
    #
    # FOUR RUNS, TWO CURRENT AND TWO SUPERSEDED. docs/34 section 3.1
    # carries four checksum blocks and labels two of them SUPERSEDED
    # 2026-08-31: the freeze moved to the -gated pair when docs/36 bound
    # MAX_CAP_VIOLATION_CORNERS and MAX_SLEW_VIOLATION_CORNERS to ['*'].
    # Until 2026-09-10 this table pinned only `signoff-6x2` and called it
    # "the frozen pilot sign-off harden", which stopped being true nine
    # days before the manifest was first written. The superseded runs are
    # KEPT, with the word in the group name, because docs/64's rule is
    # that a superseded measurement is left standing with a marker -- and
    # because docs/79 section 1.2 and docs/32 measured `signoff-6x2`
    # specifically and their numbers are about that DEF and that netlist.
    ("pilot-signoff-gated", "31,34,36,79",
     "CURRENT. The frozen pilot sign-off harden as docs/34 section 3.1 "
     "records it since 2026-08-31. Its netlist, powered netlist and DEF "
     "are bit-identical to the superseded signoff-6x2 below; only the "
     "GDS and resolved.json move",
     _pilot("signoff-6x2-gated")),

    ("pilot-submission-gated", "31,34,36",
     "CURRENT. The run the shuttle's submission path builds. docs/34 "
     "section 3.2 rests on the three-way byte identity between this, "
     "signoff-6x2-gated and the two superseded runs",
     _pilot("submission-6x2-gated")),

    ("pilot-signoff-superseded", "31,32,34,79",
     "SUPERSEDED 2026-08-31 by signoff-6x2-gated (docs/34 section 3.1); "
     "RETAINED. docs/32 runs gate-level fault injection on this "
     "netlist and docs/79 section 1.2 measures replica placement from "
     "this DEF, so it is still the artefact those documents name",
     _pilot("signoff-6x2")),

    ("pilot-submission-superseded", "31,34",
     "SUPERSEDED 2026-08-31 by submission-6x2-gated; RETAINED. The "
     "fourth of docs/34 section 3.1's checksum blocks",
     _pilot("submission-6x2")),

    ("pilot-shape6x2", "26,27",
     "the 6x2 harden docs/26's gate-level campaign injected into, before "
     "the sign-off run existed",
     _run(f"{PILOT}/shape-6x2")),

    # ---- the SoC layouts ----
    ("soc-s70boot2", "70,71",
     "docs/70's boot-hardened layout. docs/71 hardens the same netlist a "
     "second time and compares the two artefact by artefact",
     _run(f"{PNR}/s70boot2")),

    ("soc-s71boot", "71,74,75,79",
     "the repeat of s70boot2 and the shipped netlist of docs/74 and "
     "docs/75. This is the UNREPAIRED layout: the counterfactual arm that "
     "restarts on all 174 injections",
     _run(f"{PNR}/s71boot")),

    ("soc-s75w9", "75,79",
     "the W9 repair, laid out. The arm whose resets-per-corrected-upset "
     "is 0.0000",
     _run(f"{PNR}/s75w9")),

    ("soc-s76gate", "76,77",
     "docs/76's clock-gated layout, which docs/77 section 9.1 reproduces "
     "as s77base",
     _run(f"{PNR}/s76gate")),

    ("soc-s77base", "77",
     "docs/77's baseline, built to reproduce s76gate and licence the "
     "comparison against s77gate",
     _run(f"{PNR}/s77base")),

    ("soc-s77gate", "77",
     "docs/77's split-enable repair. The pair with s77base is the whole "
     "of section 9",
     _run(f"{PNR}/s77gate")),

    # ---- the synthesis netlists, which are the campaign's other two arms ----
    ("soc-synth", "71,74,75,77",
     "whole-SoC synthesis netlists: no clock tree, no timing repair, no "
     "placement. docs/75 section 8.5 uses s70-rom0-syn and s75-rom0-syn "
     "as the second row of its two-by-two",
     [("netlist", f"{OUT}/s69-rom0-syn/soc_top.netlist.v"),
      ("report", f"{OUT}/s69-rom0-syn/area.rpt"),
      ("netlist", f"{OUT}/s70-rom0-syn/soc_top.netlist.v"),
      ("report", f"{OUT}/s70-rom0-syn/area.rpt"),
      ("netlist", f"{OUT}/s75-rom0-syn/soc_top.netlist.v"),
      ("report", f"{OUT}/s75-rom0-syn/area.rpt"),
      ("netlist", f"{OUT}/s76-rom0-gate/soc_top.netlist.v"),
      ("report", f"{OUT}/s76-rom0-gate/area.rpt"),
      ("netlist", f"{OUT}/s77-rom0-gate/soc_top.netlist.v"),
      ("report", f"{OUT}/s77-rom0-gate/area.rpt")]),

    # ---- the fault-injection record files ----
    ("fi-rtl", "42,44,74,75",
     "the RTL-level campaigns and the golden runs the gate-level arms are "
     "compared against",
     _campaign(f"{OUT}/fi-h1", "records.csv", "fi_targets.txt",
               "fi_coverage.txt")
     + _campaign(f"{OUT}/fi-h74rtl", "directed.csv", "golden_rtl.log",
                 "fi_targets.txt")
     + _campaign(f"{OUT}/fi-h75rtl", "golden_rtl.log", "fi_targets.txt")),

    ("gl-74", "74",
     "docs/74's gate-level campaign on s71boot: the map from RTL sites to "
     "netlist flip-flops, the census that found the Q-net instrument "
     "undercounting, and the record files",
     _campaign(f"{OUT}/gl74", "map.json", "map.txt", "census_by_name.txt",
               "instants.csv", "flops.tsv", "provenance.txt")
     + _campaign(f"{OUT}/gl74b", "records_gl.csv", "reconcile.txt",
                 "flops.tsv", "provenance.txt")
     + _campaign(f"{OUT}/gl74c", "records_gl_sweep.csv", "provenance.txt")
     + _campaign(f"{OUT}/gl74e", "records_rf_only.csv", "records_gl_rf.csv",
                 "provenance.txt")
     + _campaign(f"{OUT}/gl74s", "records_gl_wdog.csv", "provenance.txt")),

    ("gl-75", "75",
     "the four arms of docs/75 section 8.5's two-by-two, one plan of 174 "
     "injections on four netlists. gl75base is the unrepaired layout, "
     "gl75w9 the repair, gl75synbase and gl75syn the two synthesis "
     "netlists. THE COLUMN THAT DIFFERS IS THE RESET",
     _campaign(f"{OUT}/gl75base", "records_gl_wdog.csv", "flops.tsv",
               "provenance.txt")
     + _campaign(f"{OUT}/gl75w9", "records_gl_wdog.csv", "map.json",
                 "flops.tsv", "provenance.txt")
     + _campaign(f"{OUT}/gl75synbase", "records_gl_wdog.csv", "map.json",
                 "flops.tsv", "provenance.txt")
     + _campaign(f"{OUT}/gl75syn", "records_gl_wdog.csv", "map.json",
                 "flops.tsv", "provenance.txt")),

    # ---- docs/79's equivalence check, and docs/77's behaviour evidence ----
    ("equiv-79", "79",
     "the eqy jobs of docs/79 section 2, including the two negative "
     "controls. The gate side is EXTRACTED FROM THE SIGN-OFF RUN, so "
     "gate_*.v is a piece of the pilot-signoff netlist above",
     # The five `.log` files were added 2026-09-10. `paper/claims.yaml`
     # names them as the artefact behind `eqy.modules_proved` and
     # `eqy.controls_fail` -- "formal/eqy/out/*.log after `make -C
     # formal/eqy`" -- and the manifest was pinning the `.pass` and
     # `.failed` markers beside them but not the logs those verdicts
     # were read out of. Same defect as section 8's, one directory over,
     # found by comparing this table against `claims.yaml` line by line.
     [("text", "formal/eqy/out/*.pass"),
      ("text", "formal/eqy/out/*.failed"),
      ("log", "formal/eqy/out/*.log"),
      ("netlist", "formal/eqy/out/gate_*.v"),
      ("netlist", "formal/eqy/out/mutant_*.v")]),

    ("sim-77", "76,77",
     "every signal at every edge, two builds one parameter apart. This is "
     "docs/77 section 7's claim that the behaviour did not change",
     _campaign(f"{OUT}/h76-g2", "equiv-design.txt", "equiv-whole.txt",
               "sim.log")
     + _campaign(f"{OUT}/h77-b", "sim.log")
     + _campaign(f"{OUT}/h77-g", "equiv-design.txt", "equiv-vs-76.txt",
                 "sim.log")),

    ("power-77", "76,77",
     "docs/77 section 9.5's power, on two layouts at three corners, and "
     "the self-comparison that settles docs/76's busy-window question",
     [("report", f"{OUT}/pwr77-s76base/power.*.rpt"),
      ("report", f"{OUT}/pwr77-s76gate/power.*.rpt"),
      ("report", f"{OUT}/pwr77-s77base/power.*.rpt"),
      ("report", f"{OUT}/pwr77-s77gate/power.*.rpt"),
      ("report", f"{OUT}/pwr77self-s77base/power.*.rpt"),
      ("report", f"{OUT}/pwr77self-s77gate/power.*.rpt")]),

    # ---- paper section 8: the two checks that were switched off ----
    #
    # `paper/claims.yaml` said of these, before this block existed, that
    # "the run directories are gitignored build output, so these are
    # pinned by digest in docs/80". They were not. Every artefact below
    # is one a claim in that file names by path, or one the paper's own
    # table quotes a number out of. The `cites` token is `paper8` rather
    # than a document number because there is no docs/81: section 8 is
    # the only place these runs are written up.

    ("deck-magic-soc", "paper8",
     "the seventeen-hour Magic DRC over s77gate's own final mask data -- "
     "39,969,214 error boxes, every one of them inside one of the six "
     "vendor SRAM macros, ZERO outside -- and the abstracted-macro run "
     "that returns 123 boxes which the paper then shows do not exist. "
     "The classification is the evidence; the 1.7 GB report is what it "
     "was computed from and state_in.json is what it was run on",
     _magicdrc("s77gate-drc-full") + _magicdrc("s77gate-drc-abstract")),

    ("deck-inputs", "paper8",
     "THE INSTRUMENT, not its output: the classifier that produced every "
     "classification.txt, the four run scripts, the step and state JSONs "
     "they were driven with, and the two abstracted macro views whose "
     "blanket obstruction rectangles are the reason the abstracted run "
     "returns 123 violations that do not exist. 205 kB, git-ignored "
     "under runs/ like everything else here. A deck result whose "
     "classifier is unpinned is a number nobody can re-derive",
     [("text", f"{PNR}/magic-drc-inputs/classify.py"),
      ("text", f"{PNR}/magic-drc-inputs/socwide.py"),
      ("text", f"{PNR}/magic-drc-inputs/widem3.py"),
      ("text", f"{PNR}/magic-drc-inputs/mk_maglef.tcl"),
      ("text", f"{PNR}/magic-drc-inputs/run_*.sh"),
      ("config", f"{PNR}/magic-drc-inputs/*.json"),
      ("text", f"{PNR}/magic-drc-inputs/maglef/*.mag")]),

    ("deck-magic-bare", "paper8",
     "the two bare-macro calibration runs: the same deck over one "
     "RM_IHPSG13_1P_2048x64 and one 1024x32 with no design near them. "
     "8,808,860 and 2,210,913 boxes, which scale linearly with bit "
     "count off the earlier single-macro figure and are what makes the "
     "defect a property of the bitcell rather than of the context",
     _magicdrc("rm2048x64-drc-alone", classified=False)
     + _magicdrc("rm1024x32-drc-alone", classified=False)),

    ("deck-klayout", "paper8",
     "KLayout DRC on s77gate, its two bare-macro runs, and the POSITIVE "
     "CONTROL -- a top cell carrying deliberate metal width and spacing "
     "violations, which the same deck at the same version returns. "
     "Without the control the 0 is a deck declining to look",
     [("lyrdb", f"{PNR}/s77gate-klayoutdrc/reports/drc.klayout.lyrdb"),
      ("text", f"{PNR}/s77gate-klayoutdrc/reports/drc.klayout.json"),
      ("log", f"{PNR}/s77gate-klayoutdrc/klayout-drc.log"),
      ("text", f"{PNR}/s77gate-klayoutdrc/COMMANDS"),
      ("lyrdb", f"{PNR}/s77gate-klayoutdrc/bare/*.lyrdb"),
      ("log", f"{PNR}/s77gate-klayoutdrc/bare/*.log"),
      ("lyrdb", f"{PNR}/s77gate-klayoutdrc/control/ctrl.lyrdb"),
      ("log", f"{PNR}/s77gate-klayoutdrc/control/ctrl.log"),
      ("gds", f"{PNR}/s77gate-klayoutdrc/control/ctrl.gds"),
      ("text", f"{PNR}/s77gate-klayoutdrc/control/mk.py"),
      ("text", f"{PNR}/s77gate-klayoutdrc/analysis/*.txt"),
      ("text", f"{PNR}/s77gate-klayoutdrc/analysis/*.py")]),

    ("lvs-77", "paper8",
     "SEVEN Netgen LVS variants over one layout, of which three match "
     "uniquely and FOUR DO NOT. The four failures are the point: the "
     "62,256-device 61,912-net match in variant b was reached by "
     "abstracting the macros, not by relaxing the comparison, and the "
     "arms that were tried and failed are pinned so that a reader can "
     "see the search rather than only its result",
     _lvs("s77lvs-a-asconfigured")
     + _lvs("s77lvs-b-blackbox")
     + _lvs("s77lvs-b2-blackbox-checked")
     + [("config", f"{PNR}/s77lvs-b2-blackbox-checked/02-checker-lvs/"
                   f"config.json")]
     + _lvs("s77lvs-c-ignorecells")
     + _lvs("s77lvs-d-delimiters")
     + _lvs("s77lvs-e-normalised")
     + _lvs("s77lvs-f-equateclasses")),

    ("soc-timing-factorial", "paper8",
     "the 2x2 repair experiment, three arms laid out: s81drv is the "
     "explicit slew and cap limits alone (-5.2145, WORSE than the "
     "-4.6799 baseline), s81ptd is timing-driven placement alone "
     "(-3.3554), s81timing is both (-3.0306). The fourth arm is the "
     "baseline and it is soc-s77gate above",
     _run(f"{PNR}/s81ptd") + _run(f"{PNR}/s81drv")
     + _run(f"{PNR}/s81timing")),

    ("sta-slow-corner", "paper8",
     "the slow-corner sign-off STA of all four arms. Every timing "
     "number section 8 prints is in here: the worst path and its two "
     "minimum-strength gates, the 3,088 violating endpoints, the four "
     "period_min values 24.68 / 25.21 / 23.36 / 23.03, and the 33 "
     "max-cap and 67 max-slew counts",
     _sta("s77gate") + _sta("s81ptd") + _sta("s81drv") + _sta("s81timing")),

    ("sta-compare-81", "paper8",
     "the independent OpenSTA period sweep on the four final netlists "
     "and their extracted parasitics. It reproduces sign-off exactly at "
     "20 ns and answers the question the flow does not: 25, 25, 24 and "
     "24 ns are where the four arms close with zero violating "
     "endpoints. The drvscan files are the transition and capacitance "
     "scans behind the 4,316-pin finding",
     [("text", f"{PNR}/s81-sta-compare/sweep.tcl"),
      ("sweep", f"{PNR}/s81-sta-compare/sweep.*.txt"),
      ("text", f"{PNR}/s81-sta-compare/drvscan.tcl"),
      ("log", f"{PNR}/s81-sta-compare/drvscan.*.txt")]),
]


# ---------------------------------------------------------------------------
# Metrics: the few numbers that say WHICH artefact this is, read out of the
# artefact rather than copied from a document. They are not a check on the
# artefact -- the digest is that -- they are what makes a manifest row
# legible to someone who cannot open the file.
# ---------------------------------------------------------------------------

# metrics.json, compact name -> LibreLane key. The selection is the rows
# docs/71 section 5.2 and docs/77 section 9.2 actually tabulate.
SLOW = "corner:nom_slow_1p08V_125C"
TYP = "corner:nom_typ_1p20V_25C"
FAST = "corner:nom_fast_1p32V_m40C"

METRIC_KEYS = [
    ("die_um2", "design__die__area"),
    ("insts", "design__instance__count"),
    ("stdcells", "design__instance__count__stdcell"),
    ("flops", "design__instance__count__class:sequential_cell"),
    ("clkgates", "design__instance__count__class:clock_gate_cell"),
    ("stdcell_um2", "design__instance__area__stdcell"),
    ("util", "design__instance__utilization"),
    ("setup_ws_slow", f"timing__setup__ws__{SLOW}"),
    ("setup_ws_typ", f"timing__setup__ws__{TYP}"),
    ("setup_ws_fast", f"timing__setup__ws__{FAST}"),
    ("setup_tns_slow", f"timing__setup__tns__{SLOW}"),
    ("setup_vio_slow", f"timing__setup_vio__count__{SLOW}"),
    ("hold_ws_slow", f"timing__hold__ws__{SLOW}"),
    ("hold_ws_typ", f"timing__hold__ws__{TYP}"),
    ("hold_ws_fast", f"timing__hold__ws__{FAST}"),
    ("setup_bufs", "design__instance__count__setup_buffer"),
    ("hold_bufs", "design__instance__count__hold_buffer"),
    ("wirelength", "route__wirelength"),
    ("drc", "route__drc_errors"),
    ("slew_vio_slow", f"design__max_slew_violation__count__{SLOW}"),
    ("cap_vio_slow", f"design__max_cap_violation__count__{SLOW}"),
    ("antenna_nets", "antenna__violating__nets"),
]

CELL = re.compile(r"^\s*(sg13g2_\w+|RM_IHPSG13_\w+)\s+(\\?\S+?)\s*\(")
DEF_UNITS = re.compile(r"^UNITS\s+DISTANCE\s+MICRONS\s+(\d+)")
DEF_DIE = re.compile(r"^DIEAREA\s+(.*?);")
DEF_COMPONENTS = re.compile(r"^COMPONENTS\s+(\d+)\s*;")
PWR_TOTAL = re.compile(
    r"^TOTAL\s+(\S+)\s+(\S+)\s+internal\s+(\S+)\s+switching\s+(\S+)"
    r"\s+leakage\s+(\S+)\s+total\s+(\S+)")
EQUIV_COMPARED = re.compile(r"(\d+)\s+compared")
EQUIV_CYCLES = re.compile(r"^cycles compared:\s*(\d+)")
EQUIV_DIFF = re.compile(r"^cycles differing:\s*(\d+)")
PROV = re.compile(r"^(netlist md5|netlist size|flops|rom hex md5)\s+(\S+)")
CENSUS_FF = re.compile(r"^flip-flops parsed:\s*(\d+)")


def _num(v):
    """A JSON number rendered without losing what was stored."""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    return str(v)


def m_metrics_json(path):
    try:
        d = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    out = {"keys": len(d)}
    for short, key in METRIC_KEYS:
        if key in d:
            out[short] = _num(d[key])
    return out


def m_netlist(path):
    """Cells by kind, from a mapped Verilog netlist.

    Line-based and streaming for the same reason `hw/soc/pnr/violator_census.py`
    is: soc_top.nl.v is 10.8 MB and a whole-file regex over it is minutes
    rather than seconds.
    """
    cells = flops = macros = lines = 0
    try:
        with path.open(errors="replace") as fh:
            for line in fh:
                lines += 1
                m = CELL.match(line)
                if not m:
                    continue
                t = m.group(1)
                cells += 1
                if t.startswith("RM_IHPSG13"):
                    macros += 1
                elif "_df" in t or "_sdf" in t:
                    flops += 1
    except OSError:
        return {}
    out = {"lines": lines, "cells": cells, "flops": flops}
    if macros:
        out["macros"] = macros
    return out


def m_def(path):
    """UNITS, DIEAREA and the component count -- all in the DEF's header.

    Deliberately stops at COMPONENTS. Everything past it is 70 MB of
    placement that the digest already covers, and reading it would double
    the cost of --check for nothing.
    """
    out = {}
    try:
        with path.open(errors="replace") as fh:
            for line in fh:
                m = DEF_UNITS.match(line)
                if m:
                    out["units_per_um"] = int(m.group(1))
                    continue
                m = DEF_DIE.match(line)
                if m:
                    out["diearea"] = m.group(1).replace(" ", "")
                    continue
                m = DEF_COMPONENTS.match(line)
                if m:
                    out["components"] = int(m.group(1))
                    break
    except OSError:
        return {}
    return out


def m_records(path):
    """Rows, and the tally of the class column, from a campaign record CSV.

    The class column is `cls` in the gate-level records and `armed_cls` in
    the RTL ones. `wdog_rst_events` exists only where the event counter
    does -- `docs/75` section 8.3 is the document that added it -- and it
    is summed rather than tallied because it is the number that went to
    zero.
    """
    try:
        with path.open(errors="replace") as fh:
            head = fh.readline().rstrip("\n").split(",")
            idx = {n: i for i, n in enumerate(head)}
            cls_i = idx.get("cls", idx.get("armed_cls"))
            wd_i = idx.get("wdog_rst_events")
            rows = 0
            tally = {}
            wd = 0
            for line in fh:
                if not line.strip():
                    continue
                f = line.rstrip("\n").split(",")
                rows += 1
                if cls_i is not None and cls_i < len(f):
                    tally[f[cls_i]] = tally.get(f[cls_i], 0) + 1
                if wd_i is not None and wd_i < len(f):
                    try:
                        wd += int(f[wd_i])
                    except ValueError:
                        pass
    except OSError:
        return {}
    out = {"rows": rows, "cols": len(head)}
    for k in sorted(tally):
        out[k.lower()] = tally[k]
    if wd_i is not None:
        out["wdog_rst_events"] = wd
    return out


def m_provenance(path):
    out = {}
    try:
        for line in path.read_text(errors="replace").split("\n"):
            m = PROV.match(line)
            if m:
                out[m.group(1).replace(" ", "_")] = m.group(2)
    except OSError:
        return {}
    return out


MAP_KEYS = ("cycles", "rtl_rows", "gl_rows", "gl_row_shift", "rtl_bits",
            "gl_flops")
MAP_SCALAR = re.compile(r'\s*"(\w+)":\s*(-?\d+)\s*,?\s*$')


def m_map(path):
    """The header scalars of a gl_map.py map, without parsing the body.

    `hw/soc/out/gl74/map.json` is 161 MB and there are four of them.
    `json.loads` on one costs well over a gigabyte of heap to recover six
    integers, on a machine that may be running a harden at the time, so
    a file over 8 MB is read line by line and stopped at `"entries"` --
    which `gl_map.py` writes AFTER the header, so the scalars are all
    above the cut. The cost is that `entries` is not counted for the big
    maps. That is deliberate rather than overlooked: `entries` equals
    `rtl_bits` on every map in this tree, and the digest is the check.
    """
    if path.suffix != ".json":
        return m_text(path)
    try:
        if path.stat().st_size > (8 << 20):
            out = {}
            with path.open(errors="replace") as fh:
                for line in fh:
                    if '"entries"' in line:
                        break
                    m = MAP_SCALAR.match(line)
                    if m and m.group(1) in MAP_KEYS:
                        out[m.group(1)] = m.group(2)
            return {k: out[k] for k in MAP_KEYS if k in out}
        d = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    out = {k: _num(d[k]) for k in MAP_KEYS if k in d}
    if isinstance(d.get("entries"), list):
        out["entries"] = len(d["entries"])
    return out


def m_report(path):
    """Power reports carry their own totals; everything else gets lines."""
    out = m_text(path)
    try:
        for line in path.read_text(errors="replace").split("\n"):
            m = PWR_TOTAL.match(line)
            if m:
                out["window"] = m.group(1)
                out["corner"] = m.group(2)
                out["internal_w"] = m.group(3)
                out["switching_w"] = m.group(4)
                out["leakage_w"] = m.group(5)
                out["total_w"] = m.group(6)
                break
    except OSError:
        pass
    return out


def m_text(path):
    """Lines, plus whatever a known text artefact announces about itself."""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return {}
    lines = text.split("\n")
    out = {"lines": len(lines) - (1 if lines and lines[-1] == "" else 0)}
    for line in lines:
        m = EQUIV_CYCLES.match(line)
        if m:
            out["cycles"] = int(m.group(1))
            continue
        m = EQUIV_DIFF.match(line)
        if m:
            out["differing"] = int(m.group(1))
            continue
        m = CENSUS_FF.match(line)
        if m:
            out["flops_parsed"] = int(m.group(1))
            continue
        if line.startswith("paths under"):
            m = EQUIV_COMPARED.search(line)
            if m:
                out["compared"] = int(m.group(1))
    return out


# ---------------------------------------------------------------------------
# Section 8 of the paper: the two geometric decks, the LVS variants and the
# timing scope. These artefacts are a different shape from everything above
# -- most of them are not a LibreLane `final/` view at all, they are a
# report, a classification, a KLayout report database or an OpenSTA sweep --
# so they get their own extractors rather than falling through to `m_text`.
#
# The rule these follow is the one section 2.2 of `docs/80` already states
# for the DEF and the map readers: READ THE NUMBER THE DOCUMENT QUOTES, and
# read it in bounded time. `s77gate-drc-full/reports/drc.magic.rpt` is
# 1.7 GB and the only two things anyone quotes from it -- the top cell and
# the `[INFO] COUNT:` line -- are its first line and its second-to-last, so
# `m_drcrpt` seeks instead of streaming.
# ---------------------------------------------------------------------------

DRC_COUNT = re.compile(r"^\[INFO\] COUNT:\s*(\d+)")
DRC_DIVISOR = re.compile(r"^\[INFO\] (Should be divided by .*?)\s*$")
CLASS_TOTAL = re.compile(r"^total error boxes\s*:\s*(\d+)")
CLASS_HEAD = re.compile(r"^=== against the (LEF footprint|DRAWN extent)")
CLASS_ROW = re.compile(r"^  (fully inside a macro|straddling an edge|"
                       r"fully outside|outside the die box)\s*:\s*(\d+)")
CLASS_RULE = re.compile(r"^\s+\d+\s+\d+\s+\d+\s+\d+\s+\S")
LYRDB_TOP = re.compile(r"^\s*<top-cell>(.*)</top-cell>")
LYRDB_CAT = re.compile(r"<category>'([^']*)'</category>")
LYRDB_CELL = re.compile(r"<cell>([^<]*)</cell>")
INSIDE_MACRO = re.compile(r"^(RM_IHPSG13|RSC_IHPSG13)")
LVS_COUNT = re.compile(r"^Number of (devices|nets):\s*(\d+).*?\|"
                       r"Number of (?:devices|nets):\s*(\d+)")
LVS_RESULT = re.compile(r"^Final result:\s*(.+?)\.?\s*$")
SWEEP_ROW = re.compile(r"^PERIOD\s+([\d.]+) ns.*?WNS\s+(-?[\d.]+)\s+TNS\s+"
                       r"(-?[\d.]+)\s+violating_endpoints\s+(\d+)")
STA_MIN_PERIOD = re.compile(r"period_min = ([\d.]+) fmax = ([\d.]+)")
STA_CORNER = re.compile(r"^(nom_\w+):\s*(-?[\d.eE+-]+)\s*$")
STA_VIOLATOR = re.compile(r"^\[(?:setup|hold) ")
STA_START = re.compile(r"^Startpoint:\s*(\S+)")
STA_END = re.compile(r"^Endpoint:\s*(\S+)")

BIG = 8 << 20


def _newlines(path):
    """Count lines without decoding. 35 MB of `max.rpt` in about 20 ms."""
    n = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            n += chunk.count(b"\n")
    return n


def m_drcrpt(path):
    """A Magic DRC report's identity: its top cell and its own box count.

    Magic writes `[INFO] COUNT: N` and the divisor caveat as the last two
    lines of the report, and the cell name as the first. That is the
    entire measurement `paper/main.tex` section 8 quotes -- 39,969,214
    boxes for `s77gate-drc-full`, 123 for the abstracted run -- so this
    reads 4 kB from each end and never touches the 1.7 GB between them.

    THE DIVISOR CAVEAT IS PINNED AS TEXT ON PURPOSE. The report's own
    last line says the count "should be divided by 3 or 4", which is the
    difference between 40 million boxes and roughly 10 to 13 million
    distinct violations. Section 8 prints that caveat; carrying it in the
    metrics column means a reader without the file still sees it.
    """
    out = {}
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            first = fh.readline(4096).decode("utf-8", "replace").strip()
            fh.seek(max(0, size - 4096))
            tail = fh.read().decode("utf-8", "replace")
    except OSError:
        return {}
    if first:
        out["top_cell"] = first
    for line in tail.split("\n"):
        m = DRC_COUNT.match(line)
        if m:
            out["boxes"] = int(m.group(1))
            continue
        m = DRC_DIVISOR.match(line)
        if m:
            out["divisor_note"] = m.group(1)
    return out


def m_drclog(path):
    """A Magic DRC step log. Same `[INFO] COUNT:` line, small file.

    The two bare-macro calibration runs have no `classification.txt` --
    there is no design around the macro to classify against -- so the log
    is where 8,808,860 and 2,210,913 are read from, and those are the two
    numbers section 8's linearity argument rests on.
    """
    out = m_text(path)
    try:
        for line in path.read_text(errors="replace").split("\n"):
            m = DRC_COUNT.match(line)
            if m:
                out["boxes"] = int(m.group(1))
    except OSError:
        return {}
    return out


def m_classification(path):
    """The inside/outside split, out of the classifier's own output.

    This is the strongest row in the manifest for section 8, because the
    number the paper puts in bold is `drawn_outside`, and it is zero.
    Both splits are carried -- against the LEF footprint the floorplan
    reserves, and against the drawn extent that adds the macro's
    0.225 um NWell overhang -- because they are two different questions
    and the report answers both.
    """
    out = {}
    section = None
    rules = 0
    names = {"fully inside a macro": "inside",
             "straddling an edge": "straddle",
             "fully outside": "outside",
             "outside the die box": "outside_die"}
    try:
        for line in path.read_text(errors="replace").split("\n"):
            m = CLASS_TOTAL.match(line)
            if m:
                out["boxes"] = int(m.group(1))
                continue
            m = CLASS_HEAD.match(line)
            if m:
                section = "lef" if m.group(1).startswith("LEF") else "drawn"
                continue
            m = CLASS_ROW.match(line)
            if m and section:
                out[f"{section}_{names[m.group(1)]}"] = int(m.group(2))
                continue
            if CLASS_RULE.match(line):
                rules += 1
    except OSError:
        return {}
    if rules:
        out["rules"] = rules
    return out


def m_lyrdb(path):
    """A KLayout report database: rules declared, rules fired, cells named.

    `paper/main.tex` section 8 says "9,668 items in 3 of 173 rules; every
    item names a cell inside the vendor hierarchy". All three halves of
    that are read here. `outside_macro` is the one that can be non-zero:
    it counts base cell names that are neither `RM_IHPSG13*` nor
    `RSC_IHPSG13*`, which is the claim stated so that it could fail.

    Declared categories are counted before `<items>` and fired ones from
    inside them, because the database declares every rule in the deck
    whether or not it produced anything.
    """
    items = declared = 0
    fired = set()
    bases = set()
    top = None
    in_items = False
    try:
        with path.open(errors="replace") as fh:
            for line in fh:
                s = line.strip()
                if s == "<items>":
                    in_items = True
                    continue
                if not in_items:
                    if s == "<category>":
                        declared += 1
                        continue
                    m = LYRDB_TOP.match(line)
                    if m:
                        top = m.group(1)
                    continue
                if s == "<item>":
                    items += 1
                    continue
                m = LYRDB_CAT.search(line)
                if m:
                    fired.add(m.group(1))
                    continue
                m = LYRDB_CELL.search(line)
                if m:
                    bases.add(m.group(1).split(":")[0])
    except OSError:
        return {}
    out = {}
    if top:
        out["top_cell"] = top
    out["items"] = items
    out["rules_declared"] = declared
    out["rules_fired"] = len(fired)
    out["base_cells"] = len(bases)
    out["outside_macro"] = sum(1 for b in bases if not INSIDE_MACRO.match(b))
    return out


def m_lvs(path):
    """Netgen's verdict and its two device/net counts, streamed.

    Four of the seven LVS variants produce a 50 MB report ending in
    "Netlists do not match", so this reads line by line and keeps only
    the last `Final result:`. `mismatch_lines` is the count of rows
    Netgen marked `**Mismatch**`, which is what distinguishes the arms
    that failed from the three that matched uniquely.

    BOTH SIDES OF THE COUNT ARE CARRIED WHEN THEY DIFFER. Netgen prints
    the layout and the source netlist in two columns, and the whole
    finding in the failing arms is that one column is not the other:
    `s77lvs-a` reports 61,912 nets against 63,658. Recording only the
    left column would have made the failing arm's row look like the
    passing one's.
    """
    out = {}
    mismatch = 0
    try:
        with path.open(errors="replace") as fh:
            for line in fh:
                if "**Mismatch**" in line:
                    mismatch += 1
                m = LVS_COUNT.match(line)
                if m and m.group(1) not in out:
                    kind, c1, c2 = m.groups()
                    out[kind] = int(c1)
                    if c1 != c2:
                        out[f"{kind}_circuit2"] = int(c2)
                    continue
                m = LVS_RESULT.match(line)
                if m:
                    out["result"] = m.group(1)
    except OSError:
        return {}
    out["mismatch_lines"] = mismatch
    return out


def m_sweep(path):
    """An OpenSTA period sweep: the baseline point, and where it closes.

    `closes_at` is the smallest swept period at which the design reports
    zero violating endpoints, and it is absent from the row when no
    swept period closes -- which is the honest rendering of `s81drv`,
    the arm that still has eight endpoints at 25 ns.
    """
    out = {}
    rows = 0
    closes = None
    try:
        for line in path.read_text(errors="replace").split("\n"):
            m = SWEEP_ROW.match(line)
            if not m:
                continue
            rows += 1
            period, wns, tns, vio = m.groups()
            if period == "20.00":
                out["wns_20ns"] = wns
                out["tns_20ns"] = tns
                out["endpoints_20ns"] = int(vio)
            if int(vio) == 0 and closes is None:
                closes = period
    except OSError:
        return {}
    out["periods"] = rows
    if closes is not None:
        out["closes_at"] = closes
    return out


def m_sta(path):
    """OpenROAD sign-off STA reports, of five different shapes.

    `clock.rpt` carries `period_min`, the `wns/tns/ws.max.rpt` files
    carry one corner-tagged number each, `violator_list.rpt` carries one
    line per failing endpoint, and `max.rpt` carries every path in slack
    order -- 35 MB of it, so a file over 8 MB is line-counted in binary
    and scanned only down to the end of its first path block, which is
    the worst path and the only one section 8 discusses.
    """
    out = {}
    violators = 0
    n = -1
    try:
        big = path.stat().st_size > BIG
        with path.open(errors="replace") as fh:
            for n, line in enumerate(fh):
                if big and n > 200:
                    break
                m = STA_MIN_PERIOD.search(line)
                if m:
                    out["period_min"] = m.group(1)
                    out["fmax"] = m.group(2)
                    continue
                m = STA_CORNER.match(line)
                if m:
                    out[m.group(1)] = m.group(2)
                    continue
                m = STA_START.match(line)
                if m and "startpoint" not in out:
                    out["startpoint"] = m.group(1)
                    continue
                m = STA_END.match(line)
                if m and "endpoint" not in out:
                    out["endpoint"] = m.group(1)
                    continue
                if STA_VIOLATOR.match(line):
                    violators += 1
        out["lines"] = _newlines(path) if big else n + 1
    except OSError:
        return {}
    if violators:
        out["violators"] = violators
    return out


def m_none(path):
    """A GDS is 108 MB of binary and this script will not parse one.

    `docs/71` section 5.3 compares GDS files by masking their timestamp
    records; that comparator is not here, and the reason is stated rather
    than hidden: a raw digest of a GDS DIFFERS between two runs that
    produced identical geometry, because the stream carries the date. So
    the GDS rows below pin THE FILE, not the layout, and `docs/80`
    section 4 says what that does and does not settle.
    """
    return {}


EXTRACT = {
    "metrics": m_metrics_json,
    "netlist": m_netlist,
    "def": m_def,
    "gds": m_none,
    "config": lambda p: {"keys": _json_keys(p)},
    "records": m_records,
    "provenance": m_provenance,
    "map": m_map,
    "report": m_report,
    "table": m_text,
    "log": m_text,
    "text": m_text,
    # section 8. New roles rather than widened old ones, deliberately:
    # touching `m_text` would have changed the metrics of rows pinned on
    # 2026-09-09 and `--check` would have called it EXTRACTOR drift, which
    # is the outcome working exactly as designed and not a licence to
    # rewrite 149 rows to silence it.
    "classification": m_classification,
    "drcrpt": m_drcrpt,
    "drclog": m_drclog,
    "lyrdb": m_lyrdb,
    "lvs": m_lvs,
    "sweep": m_sweep,
    "sta": m_sta,
}


def _json_keys(path):
    try:
        d = json.loads(path.read_text())
    except (OSError, ValueError):
        return 0
    return len(d) if isinstance(d, dict) else 0


# ---------------------------------------------------------------------------
# Manifest I/O
# ---------------------------------------------------------------------------

HEADER = """\
# Artefact digests. Written by scripts/artefact_digests.py; described by
# docs/80-artefact-digests.md. DO NOT EDIT BY HAND.
#
# Every path below is git-ignored on purpose -- .gitignore lines 4, 40,
# 74, 118 and 136. This file pins their IDENTITY so that the evidence
# behind docs/71, docs/74, docs/75, docs/77 and docs/79 cannot be
# silently swapped. It does NOT make the artefacts available and it does
# NOT establish that any of them is correct.
#
# {census}
#
# sha256 is over the file's bytes. `metrics` is `k=v;k=v`, read out of the
# artefact by this script's own extractors, and is a legibility aid, not a
# check -- the digest is the check.
#
#   scripts/artefact_digests.py --check    re-verify. MISSING is not FAILED
#   scripts/artefact_digests.py --write    rebuild on a machine that has the runs
"""


def census(rows):
    """The size line, measured rather than remembered.

    An earlier header carried "345 bytes to 161 MB ... the whole set is
    1.9 GB" as a literal, and the manifest more than doubled underneath
    it. A number about the file belongs to the file: this recomputes it
    on every --write, so it cannot go stale without the row it counts
    also changing.
    """
    if not rows:
        return "The manifest is empty."
    sizes = sorted(int(r["bytes"]) for r in rows)
    total = sum(sizes)
    return (f"{len(sizes)} artefacts, {_si(sizes[0])} to {_si(sizes[-1])}, "
            f"{_si(total)} in total.")


def _si(n):
    """Decimal, because docs/80 counts in decimal.

    Binary units under decimal names would have printed 4.81 GB for the
    same 5.16 GB the document reports, and the two would have been read
    as a disagreement about the manifest rather than about the divisor.
    """
    for unit, scale in (("GB", 10 ** 9), ("MB", 10 ** 6), ("kB", 10 ** 3)):
        if n >= scale:
            return f"{n / scale:.3f} {unit}"
    return f"{n} bytes"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fmt_metrics(d):
    return ";".join(f"{k}={v}" for k, v in d.items())


def collect():
    """Walk the GROUPS table against the working tree. Returns rows."""
    rows = []
    for name, cites, _what, items in GROUPS:
        seen = set()
        for role, pattern in items:
            for path in sorted(ROOT.glob(pattern)):
                if not path.is_file():
                    continue
                rel = path.relative_to(ROOT).as_posix()
                if rel in seen:
                    continue
                seen.add(rel)
                metrics = EXTRACT.get(role, m_text)(path)
                rows.append({
                    "group": name,
                    "cites": cites,
                    "role": role,
                    "path": rel,
                    "bytes": str(path.stat().st_size),
                    "sha256": sha256(path),
                    "metrics": fmt_metrics(metrics),
                })
    return rows


def read_manifest():
    if not MANIFEST.is_file():
        return []
    rows = []
    for line in MANIFEST.read_text().split("\n"):
        if not line or line.startswith("#"):
            continue
        f = line.split("\t")
        if f == COLUMNS or len(f) != len(COLUMNS):
            continue
        rows.append(dict(zip(COLUMNS, f)))
    return rows


def write_manifest(rows):
    body = [HEADER.format(census=census(rows)), "\t".join(COLUMNS)]
    body += ["\t".join(r[c] for c in COLUMNS) for r in rows]
    MANIFEST.write_text("\n".join(body) + "\n")


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def do_write(allow_shrink, quiet):
    old = read_manifest()
    new = collect()
    old_paths = {r["path"] for r in old}
    new_paths = {r["path"] for r in new}
    dropped = sorted(old_paths - new_paths)
    added = sorted(new_paths - old_paths)

    if dropped and not allow_shrink:
        print(f"REFUSING to write: {len(dropped)} artefact(s) in the "
              f"manifest are not on this machine.")
        for p in dropped[:20]:
            print(f"  would drop  {p}")
        if len(dropped) > 20:
            print(f"  ... and {len(dropped) - 20} more")
        print("\nA manifest rebuilt where the run tree is incomplete deletes "
              "the record of\nevidence that still exists elsewhere. Use "
              "--check here. If the artefacts are\ngenuinely gone and the "
              "documents have been corrected, pass --allow-shrink.")
        return 1

    write_manifest(new)
    if not quiet:
        for p in added:
            print(f"  added    {p}")
        for p in dropped:
            print(f"  DROPPED  {p}")
        print(f"\n{len(new)} artefact(s) pinned in "
              f"{MANIFEST.relative_to(ROOT)}"
              f"  (+{len(added)}, -{len(dropped)})")
        total = sum(int(r["bytes"]) for r in new)
        print(f"{total / 1e9:.2f} GB of artefacts, "
              f"{MANIFEST.stat().st_size / 1024:.1f} kB of manifest")
    return 0


def do_check(quiet):
    rows = read_manifest()
    if not rows:
        print(f"no manifest at {MANIFEST.relative_to(ROOT)}; "
              f"run --write on a machine that has the run tree")
        return 1

    verified, missing, changed, extractor, vacuous = [], [], [], [], []
    for r in rows:
        path = ROOT / r["path"]
        if not path.is_file():
            missing.append(r)
            continue
        size = str(path.stat().st_size)
        digest = sha256(path)
        if size != r["bytes"] or digest != r["sha256"]:
            changed.append((r, size, digest))
            continue
        got = fmt_metrics(EXTRACT.get(r["role"], m_text)(path))
        if got != r["metrics"]:
            extractor.append((r, got))
        elif size == "0":
            vacuous.append(r)
        else:
            verified.append(r)

    for r, size, digest in changed:
        print(f"CHANGED   {r['path']}")
        print(f"          pinned {r['bytes']} bytes {r['sha256']}")
        print(f"          on disk {size} bytes {digest}")
    for r, got in extractor:
        print(f"EXTRACTOR {r['path']}")
        print("          bytes match the pinned digest, metrics do not.")
        print(f"          pinned  {r['metrics']}")
        print(f"          derived {got}")
    for r in vacuous:
        print(f"VACUOUS   {r['path']}")
        print("          the file is empty, so its digest is the digest of "
              "emptiness --")
        print("          every empty artefact in this manifest has the same "
              "one. The row")
        print("          shows the file existed under that name; the digest "
              "column shows")
        print("          nothing, and swapping this file for any other empty "
              "file is")
        print("          invisible here.")
    if not quiet:
        for r in verified:
            print(f"VERIFIED  {r['path']}")
        for r in missing:
            print(f"MISSING   {r['path']}")

    n = len(rows)
    print(f"\n{len(verified)} verified, {len(vacuous)} vacuous, "
          f"{len(missing)} missing, {len(changed)} changed, "
          f"{len(extractor)} extractor-drift, of {n} pinned")

    if len(missing) + len(vacuous) == n:
        print("\nEvery artefact is missing, which is what a fresh clone looks"
              " like: these paths\nare git-ignored run outputs (.gitignore"
              " lines 4, 40, 74, 118 and 136) and nothing\nin the repository"
              " regenerates them in less than a working day. MISSING is\nNOT"
              " FAILED. docs/80 section 3 says what a reader can do instead,"
              " and\nsection 4 says what this manifest still does not settle"
              " for them.")
    elif missing:
        print(f"\n{len(missing)} artefact(s) are not on this machine. Not an "
              "error: run trees are\nkept per machine and this one has part "
              "of the record.")

    return 1 if (changed or extractor) else 0


CITE_NAMES = {"paper8": "paper/main.tex section 8"}


def cite_label(cites):
    """`31,34` -> `docs/31, docs/34`; `paper8` -> the paper's section 8.

    The `cites` column used to be bare document numbers, so `--list`
    prefixed every one of them with `docs/`. Section 8's evidence has no
    document number -- it is written up in the paper and nowhere else --
    and printing `docs/paper8` would have been a citation to a file that
    does not exist.
    """
    return ", ".join(
        f"docs/{c}" if c.isdigit() else CITE_NAMES.get(c, c)
        for c in cites.split(","))


def do_list():
    rows = read_manifest()
    pinned = {}
    for r in rows:
        pinned.setdefault(r["group"], []).append(r)
    for name, cites, what, items in GROUPS:
        have = pinned.get(name, [])
        on_disk = sum(1 for r in have if (ROOT / r["path"]).is_file())
        print(f"{name}  [{cite_label(cites)}]")
        print(f"  {what}")
        print(f"  {len(items)} pattern(s), {len(have)} pinned, "
              f"{on_disk} on disk")
        for r in have:
            mark = "  " if (ROOT / r["path"]).is_file() else "??"
            print(f"    {mark} {int(r['bytes']):>12,}  {r['path']}")
        print()
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Pin, by SHA-256, the git-ignored run outputs this "
                    "corpus's documents cite.")
    ap.add_argument("--check", action="store_true",
                    help="re-verify the manifest against the working tree "
                         "(the default). MISSING is not FAILED.")
    ap.add_argument("--write", action="store_true",
                    help="rebuild the manifest from the working tree")
    ap.add_argument("--list", action="store_true",
                    help="print the groups, what they cite, and what is "
                         "on disk")
    ap.add_argument("--allow-shrink", action="store_true",
                    help="with --write, permit dropping artefacts that are "
                         "pinned but absent here")
    ap.add_argument("--quiet", action="store_true",
                    help="print only the problems and the summary")
    args = ap.parse_args()

    if args.write and args.check:
        ap.error("--write and --check are different questions; pick one")
    if args.list:
        return do_list()
    if args.write:
        return do_write(args.allow_shrink, args.quiet)
    return do_check(args.quiet)


if __name__ == "__main__":
    sys.exit(main())
