#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Attribute every box in a Magic DRC report to a macro, or to nothing.

    classify_magic_drc.py <run-dir> [--lef-dir DIR]

`docs/12` section 7.5 measured RM_IHPSG13 as un-signoff-able in this PDK
version: 1,106,478 Magic errors inside ONE macro's own footprint and 0
outside. Every Magic result in this repository is therefore read as two
numbers, inside and outside, and never as a total. The classifications
in `hw/soc/pnr/runs/*/classification.txt` were produced by a script that
was never committed, so the numbers `docs/77` and `paper/main.tex` cite
could not be re-derived from this checkout. This is that script.

It reads the run's own final DEF for macro origins and orientations and
the PDK LEF for macro sizes, so it cannot be told a placement that the
run did not have. Two extents are reported because they answer different
questions: the LEF footprint is the box the floorplan reserves, and the
drawn extent adds the 0.225um NWell overhang the vendor's geometry
actually occupies, which is what decides whether a box on a macro edge
belongs to the macro or to the design.
"""
import argparse
import collections
import pathlib
import re
import sys

# Measured 2026-09-13 on the eight-macro layout: 31 of the 33 boxes this
# constant turns into "straddling" overlap by EXACTLY 0.0050um, at three
# different macro right edges -- 904.48, 1729.12 and 2006.08 -- so the
# markers sit 0.220um from the LEF edge and this 0.225 model overshoots
# them by five nanometres. Change the constant to 0.220 and all 31 become
# "outside". The drawn-extent split is therefore decided by a modelling
# choice of 5nm, and the LEF-footprint split above it is the robust
# number. That is why this script prints both and lists the marginal
# boxes rather than picking one.
NWELL_OVERHANG = 0.225


def parse_report(path):
    """-> [(rule, x1, y1, x2, y2)], in report order."""
    out, rule = [], None
    for line in path.read_text(errors="ignore").split("\n"):
        if line.startswith("---") or line.startswith("soc_top"):
            continue
        if re.match(r"^\s*[\d.]+um\s", line):
            v = [float(t[:-2]) for t in line.split()]
            if rule and len(v) == 4:
                out.append((rule, *v))
        elif line.strip() and not line.lstrip().startswith("[INFO]"):
            rule = line.strip()
    return out


def parse_def(path):
    """-> {instance: (cell, x_um, y_um, orient)} for FIXED macros."""
    txt = path.read_text(errors="ignore")
    m = re.search(r"UNITS DISTANCE MICRONS (\d+)", txt)
    dbu = float(m.group(1)) if m else 1000.0
    macros = {}
    pat = re.compile(
        r"^\s*-\s+(\S+)\s+(RM_IHPSG13\S*)\s.*?\+\s+(?:FIXED|PLACED)\s*\(\s*"
        r"(-?\d+)\s+(-?\d+)\s*\)\s+(\w+)", re.S | re.M)
    for mt in pat.finditer(txt):
        inst, cell, x, y, orient = mt.groups()
        macros[inst] = (cell, int(x) / dbu, int(y) / dbu, orient)
    return macros


def lef_sizes(lef_dir):
    """-> {cell: (w, h)} from every LEF under lef_dir."""
    sizes = {}
    for lef in pathlib.Path(lef_dir).rglob("*.lef"):
        txt = lef.read_text(errors="ignore")
        for mt in re.finditer(r"MACRO (\S+)(.*?)END \1", txt, re.S):
            sm = re.search(r"SIZE\s+([\d.]+)\s+BY\s+([\d.]+)", mt.group(2))
            if sm:
                sizes[mt.group(1)] = (float(sm.group(1)), float(sm.group(2)))
    return sizes


def boxes(macros, sizes, pad):
    out = {}
    for inst, (cell, x, y, orient) in macros.items():
        if cell not in sizes:
            continue
        w, h = sizes[cell]
        if orient in ("N", "S", "FN", "FS"):
            bw, bh = w, h
        else:                       # E, W, FE, FW rotate the footprint
            bw, bh = h, w
        out[inst] = (x - pad, y - pad, x + bw + pad, y + bh + pad)
    return out


# A macro edge lands on a binary-float sum -- 120.0 + 626.7 is
# 687.1800000000001 -- while the report parses the touching box's edge as
# exactly 687.18. Without a tolerance a box that merely TOUCHES an edge,
# overlapping it over zero area, is counted as straddling it. That is one
# box in s77gate's 123 and it is the difference between reproducing the
# committed classification and quietly disagreeing with the number the
# paper cites. One picometre is far below any geometry in this PDK.
TOUCH_EPS = 1e-6


def classify(box, placed):
    x1, y1, x2, y2 = box
    straddle = None
    for inst, (mx1, my1, mx2, my2) in placed.items():
        if (x1 >= mx1 - TOUCH_EPS and y1 >= my1 - TOUCH_EPS
                and x2 <= mx2 + TOUCH_EPS and y2 <= my2 + TOUCH_EPS):
            return "inside", inst
        if not (x2 <= mx1 + TOUCH_EPS or x1 >= mx2 - TOUCH_EPS
                or y2 <= my1 + TOUCH_EPS or y1 >= my2 - TOUCH_EPS):
            straddle = inst
    return ("straddle", straddle) if straddle else ("outside", None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--lef-dir", default=None)
    a = ap.parse_args()
    run = pathlib.Path(a.run_dir)

    rpts = sorted(run.rglob("drc.magic.rpt"))
    if not rpts:
        sys.exit("no drc.magic.rpt under {}".format(run))
    rpt = rpts[0]
    defs = sorted(run.rglob("final/def/*.def")) or sorted(run.rglob("*.def"))
    if not defs:
        sys.exit("no DEF under {} -- classification needs the placement "
                 "the run actually had".format(run))
    lef_dir = a.lef_dir or (pathlib.Path.home() / ".ciel/ciel/ihp-sg13g2")

    errors = parse_report(rpt)
    macros = parse_def(defs[0])
    sizes = lef_sizes(lef_dir)
    if not macros:
        sys.exit(
            "found NO macros in {} -- refusing to report. A classifier that "
            "finds no macro calls every box 'outside', which is both the most "
            "useful-looking answer here and the most wrong: docs/12 section "
            "7.5's whole finding is that these markers are INSIDE the vendor "
            "macro. Silence would have been safer than that number.".format(
                defs[0]))
    missing = {c for c, *_ in macros.values()} - set(sizes)
    if missing:
        sys.exit("no LEF SIZE for {} -- refusing to classify against a "
                 "footprint this script guessed".format(sorted(missing)))

    print("report                : {}".format(rpt))
    print("placement             : {}".format(defs[0]))
    print("total error boxes     : {}".format(len(errors)))
    print("macros placed         : {}".format(len(macros)))

    for label, pad in (("the LEF footprint (the box the floorplan reserves)", 0.0),
                       ("the DRAWN extent (LEF box + {}um NWell overhang)"
                        .format(NWELL_OVERHANG), NWELL_OVERHANG)):
        placed = boxes(macros, sizes, pad)
        tally = collections.Counter()
        per = collections.Counter()
        marginal = []
        for rule, *box in errors:
            kind, inst = classify(box, placed)
            tally[kind] += 1
            if kind == "inside":
                per[inst] += 1
            elif kind == "straddle":
                mx1, my1, mx2, my2 = placed[inst]
                ox = min(box[2], mx2) - max(box[0], mx1)
                oy = min(box[3], my2) - max(box[1], my1)
                if min(ox, oy) < 0.010:
                    marginal.append((box, inst, ox, oy))
        print("\n=== against {} ===".format(label))
        print("  fully inside a macro: {}".format(tally["inside"]))
        print("  straddling an edge  : {}".format(tally["straddle"]))
        print("  fully outside       : {}".format(tally["outside"]))
        if marginal:
            # The 0.225um overhang is itself a model of the vendor's
            # geometry, so a box overlapping it by nanometres is inside
            # the model's own uncertainty and is reported rather than
            # silently assigned. This is where this script and the
            # uncommitted one that wrote s77gate's classification.txt
            # disagree, by exactly one box of 123: a 0.005um sliver.
            print("  of the straddles, {} overlap by less than 10nm and are "
                  "arguable either way:".format(len(marginal)))
            for box, inst, ox, oy in marginal:
                print("      {} overlaps {} by {:.4f} x {:.4f} um".format(
                    box, inst, ox, oy))
        if pad:
            print("\n=== per macro instance (drawn extent, fully-inside boxes) ===")
            for inst in sorted(macros):
                print("  {:34s} {}".format(inst, per[inst]))

    placed = boxes(macros, sizes, NWELL_OVERHANG)
    print("\n=== by rule (drawn extent) ===")
    print("  {:>8s} {:>10s} {:>9s} {:>9s}  rule".format(
        "total", "in-macro", "straddle", "outside"))
    byrule = collections.defaultdict(collections.Counter)
    for rule, *box in errors:
        byrule[rule][classify(box, placed)[0]] += 1
    for rule in sorted(byrule, key=lambda r: -sum(byrule[r].values())):
        c = byrule[rule]
        print("  {:8d} {:10d} {:9d} {:9d}  {}".format(
            sum(c.values()), c["inside"], c["straddle"], c["outside"], rule))


if __name__ == "__main__":
    main()
