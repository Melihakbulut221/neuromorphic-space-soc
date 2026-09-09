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

WHAT IS NOT COVERED is in `docs/80` section 5 and it is a long list. The
two that matter most here: the intermediate steps of a run (only
`final/` and `resolved.json` are pinned, so a reader cannot check the
router's per-iteration trajectory that `docs/71` section 5.2 calls its
sharpest evidence), and everything under `hw/tb/`, which is already
tracked and needs no digest.
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
    ("pilot-signoff", "31,32,34,79",
     "the frozen pilot sign-off harden. docs/34 freezes it, docs/32 runs "
     "gate-level fault injection on its netlist, docs/79 section 1.2 "
     "measures replica placement from its DEF",
     _run(f"{PILOT}/signoff-6x2")),

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
     [("text", "formal/eqy/out/*.pass"),
      ("text", "formal/eqy/out/*.failed"),
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
# 74, 118 and 136 -- because the artefacts run from 345 bytes to 161 MB
# and the whole set is 1.9 GB. This file pins their IDENTITY so that the
# evidence behind docs/71, docs/74, docs/75, docs/77 and docs/79 cannot
# be silently swapped. It does NOT make the artefacts available and it
# does NOT establish that any of them is correct.
#
# sha256 is over the file's bytes. `metrics` is `k=v;k=v`, read out of the
# artefact by this script's own extractors, and is a legibility aid, not a
# check -- the digest is the check.
#
#   scripts/artefact_digests.py --check    re-verify. MISSING is not FAILED
#   scripts/artefact_digests.py --write    rebuild on a machine that has the runs
"""


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
    body = [HEADER, "\t".join(COLUMNS)]
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

    verified, missing, changed, extractor = [], [], [], []
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
    if not quiet:
        for r in verified:
            print(f"VERIFIED  {r['path']}")
        for r in missing:
            print(f"MISSING   {r['path']}")

    n = len(rows)
    print(f"\n{len(verified)} verified, {len(missing)} missing, "
          f"{len(changed)} changed, {len(extractor)} extractor-drift, "
          f"of {n} pinned")

    if len(missing) == n:
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


def do_list():
    rows = read_manifest()
    pinned = {}
    for r in rows:
        pinned.setdefault(r["group"], []).append(r)
    for name, cites, what, items in GROUPS:
        have = pinned.get(name, [])
        on_disk = sum(1 for r in have if (ROOT / r["path"]).is_file())
        print(f"{name}  [docs/{cites.replace(',', ', docs/')}]")
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
