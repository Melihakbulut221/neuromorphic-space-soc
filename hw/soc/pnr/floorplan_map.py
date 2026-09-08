#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Extract a floorplan region map of soc_top from the signed-off DEF.

docs/59 is the document this script exists for: an annotated map of the
die, of the kind a reader gets from a labelled die photograph, showing
what the chip is made of and where each piece sits.  The rule that made
it worth writing a script rather than drawing a picture is the rule this
repository applies to every other number:

  EVERY RECTANGLE ON THE MAP IS READ OUT OF THE LAYOUT.  The die box,
  the core box, the placeable rows, all six macro rectangles, the
  standard-cell bounding box, the cell-density field and the top-metal
  power stripes are parsed from
  hw/soc/pnr/runs/full3/final/def/soc_top.def and from the PDK's own
  LEF.  Nothing on the map is positioned by hand and nothing is scaled
  to look right.  A floorplan diagram is exactly the artefact where a
  plausible drawing gets believed, so this one is generated or it is
  not published.

What the script does NOT do, and why the map is honest about it:

  * It cannot colour the logic by block.  hw/soc/pnr/runs/full3
    hardened with SYNTH_HIERARCHY_MODE=flatten and SYNTH_AUTONAME=0, so
    169,747 of the DEF's component names are `_NNNNN_`, `FILLER_*`,
    `ANTENNA_*`, `hold*`, `fanout*`, `rebuffer*`, `wire*` or `clkbuf_*`
    and only a few hundred still carry a dotted RTL path.  --hier-report
    prints exactly how many, so the claim is checked and not assumed.
    Drawing an Ibex box or an NPU box on this die would be fiction.

  * It draws placement, not routing.  The 3,095,532 um of routed wire
    are in the same DEF and are not on the map; the map would become a
    grey rectangle.

Usage:

    floorplan_map.py                       # write the SVG and the JSON
    floorplan_map.py --hier-report         # what survived flattening
    floorplan_map.py --run <dir> --out-svg <f.svg> --out-json <f.json>

Reads nothing but the DEF, the LEF files named by the run's
resolved.json, and the run's own metrics.json (for cross-checking only:
no metric is copied onto the map).  Standard library only.
"""

import argparse
import collections
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RUN = os.path.join(HERE, "runs", "full3")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))   # repo root
DEFAULT_SVG = os.path.join(ROOT, "docs", "img", "soc-floorplan-map.svg")
DEFAULT_JSON = os.path.join(ROOT, "docs", "img", "soc-floorplan-map.json")


# --------------------------------------------------------------------------
# LEF: cell sizes
# --------------------------------------------------------------------------

MACRO_RE = re.compile(r"^\s*MACRO\s+(\S+)")
SIZE_RE = re.compile(r"^\s*SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)")


def read_lef_sizes(paths):
    """Return {master: (w_um, h_um)} from every MACRO ... SIZE in the LEFs."""
    sizes = {}
    for path in paths:
        cur = None
        with open(path, "r", errors="replace") as fh:
            for line in fh:
                m = MACRO_RE.match(line)
                if m:
                    cur = m.group(1)
                    continue
                if cur is not None:
                    m = SIZE_RE.match(line)
                    if m:
                        sizes[cur] = (float(m.group(1)), float(m.group(2)))
                        cur = None
    return sizes


# --------------------------------------------------------------------------
# DEF
# --------------------------------------------------------------------------

COMP_RE = re.compile(
    r"^\s*-\s+(\S+)\s+(\S+)\s+.*?\+\s+(?:FIXED|PLACED|COVER)\s+"
    r"\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\w+)"
)
ROW_RE = re.compile(
    r"^ROW\s+(\S+)\s+(\S+)\s+(-?\d+)\s+(-?\d+)\s+(\w+)\s+DO\s+(\d+)\s+BY\s+(\d+)"
    r"\s+STEP\s+(\d+)\s+(\d+)"
)

# Orientations that transpose a cell's LEF SIZE.
ROTATED = {"E", "W", "FE", "FW", "R90", "R270"}


class Def(object):
    pass


def read_def(path):
    """Parse the pieces of the DEF the map needs, in one streaming pass."""
    d = Def()
    d.path = path
    d.units = None
    d.die = None
    d.rows = []
    d.components = []          # (name, master, x_dbu, y_dbu, orient)
    d.pins = []                # (name, direction, x_dbu, y_dbu, layer)
    d.special = collections.defaultdict(list)   # layer -> [(net, x0,y0,x1,y1)]
    d.special_vias = collections.Counter()      # layer -> via placements
    d.n_components_declared = None
    d.n_nets_declared = None
    d.n_pins_declared = None

    section = None
    sn_net = None
    sn_tokens = []

    with open(path, "r", errors="replace") as fh:
        for line in fh:
            if d.units is None and line.startswith("UNITS DISTANCE MICRONS"):
                d.units = float(line.split()[3])
                continue
            if d.die is None and line.startswith("DIEAREA"):
                nums = [int(v) for v in re.findall(r"-?\d+", line)]
                d.die = (nums[0], nums[1], nums[2], nums[3])
                continue
            if line.startswith("ROW "):
                m = ROW_RE.match(line)
                if m:
                    d.rows.append(
                        (
                            m.group(1), m.group(2),
                            int(m.group(3)), int(m.group(4)), m.group(5),
                            int(m.group(6)), int(m.group(7)),
                            int(m.group(8)), int(m.group(9)),
                        )
                    )
                continue
            if line.startswith("COMPONENTS "):
                d.n_components_declared = int(line.split()[1])
                section = "components"
                continue
            if line.startswith("END COMPONENTS"):
                section = None
                continue
            if line.startswith("PINS "):
                d.n_pins_declared = int(line.split()[1])
                section = "pins"
                pin_buf = []
                continue
            if line.startswith("END PINS"):
                section = None
                continue
            if line.startswith("SPECIALNETS "):
                section = "specialnets"
                continue
            if line.startswith("END SPECIALNETS"):
                _flush_special(d, sn_net, sn_tokens)
                sn_net, sn_tokens = None, []
                section = None
                continue
            if line.startswith("NETS "):
                d.n_nets_declared = int(line.split()[1])
                section = "skip"
                continue
            if line.startswith("END NETS"):
                section = None
                continue

            if section == "components":
                m = COMP_RE.match(line)
                if m:
                    d.components.append(
                        (m.group(1), m.group(2),
                         int(m.group(3)), int(m.group(4)), m.group(5))
                    )
            elif section == "pins":
                pin_buf.append(line)
                if line.rstrip().endswith(";"):
                    _flush_pin(d, "".join(pin_buf))
                    pin_buf = []
            elif section == "specialnets":
                stripped = line.strip()
                if stripped.startswith("- "):
                    _flush_special(d, sn_net, sn_tokens)
                    sn_net = stripped.split()[1]
                    sn_tokens = stripped.split()[2:]
                else:
                    sn_tokens.extend(stripped.split())
                if stripped.endswith(";"):
                    _flush_special(d, sn_net, sn_tokens)
                    sn_tokens = []

    return d


PIN_NAME_RE = re.compile(r"-\s+(\S+)\s")
PIN_DIR_RE = re.compile(r"\+\s+DIRECTION\s+(\w+)")
PIN_PLACE_RE = re.compile(r"\+\s+(?:FIXED|PLACED|COVER)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)")
PIN_LAYER_RE = re.compile(r"\+\s+LAYER\s+(\S+)")


def _flush_pin(d, blob):
    blob = " ".join(blob.split())
    name = PIN_NAME_RE.search(blob)
    place = PIN_PLACE_RE.search(blob)
    if not (name and place):
        return
    direction = PIN_DIR_RE.search(blob)
    layer = PIN_LAYER_RE.search(blob)
    d.pins.append(
        (
            name.group(1),
            direction.group(1) if direction else "?",
            int(place.group(1)), int(place.group(2)),
            layer.group(1) if layer else "?",
        )
    )


def _flush_special(d, net, tokens):
    """Turn one SPECIALNETS wiring statement into axis-aligned rectangles.

    A special wire is a centre-line path of a stated width; a segment
    between two points therefore covers a rectangle inflated by half the
    width.  Points may abbreviate an unchanged coordinate as `*`.  Via
    placements (one point followed by a via name) carry no extent here
    and are counted, not drawn.
    """
    if not net or not tokens:
        return
    i = 0
    layer = None
    width = 0
    last = None
    while i < len(tokens):
        t = tokens[i]
        if t in ("ROUTED", "NEW", "FIXED", "COVER"):
            i += 1
            if i < len(tokens):
                layer = tokens[i]
                i += 1
            if i < len(tokens) and re.match(r"^-?\d+$", tokens[i]):
                width = int(tokens[i])
                i += 1
            last = None
            continue
        if t == "+":
            i += 1
            continue
        if t in ("SHAPE", "USE", "STYLE", "MASK"):
            i += 2
            continue
        if t == "RECT":
            i += 1
            nums = []
            while i < len(tokens) and len(nums) < 6:
                if tokens[i] == "(":
                    i += 1
                    continue
                if tokens[i] == ")":
                    i += 1
                    if len(nums) >= 4:
                        break
                    continue
                nums.append(tokens[i])
                i += 1
            continue
        if t == "(":
            j = i + 1
            coords = []
            while j < len(tokens) and tokens[j] != ")":
                coords.append(tokens[j])
                j += 1
            i = j + 1
            # Before the first ROUTED/NEW the parenthesised groups are the
            # net's connections -- ( PIN VGND ), ( * VSS! ) -- not points.
            if layer is None or len(coords) < 2:
                continue
            if not all(c == "*" or re.fullmatch(r"-?\d+", c)
                       for c in coords[:2]):
                continue
            if coords[0] == "*" and last is None:
                continue
            x = last[0] if coords[0] == "*" else int(coords[0])
            y = last[1] if coords[1] == "*" else int(coords[1])
            pt = (x, y)
            if last is not None and width > 0:
                h = width // 2
                x0, x1 = sorted((last[0], pt[0]))
                y0, y1 = sorted((last[1], pt[1]))
                d.special[layer].append((net, x0 - h, y0 - h, x1 + h, y1 + h))
            last = pt
            continue
        # A bare token here is a via name after a single point.  A via
        # covers real metal but the DEF states no extent for it, so it is
        # counted and not drawn -- that is the honest treatment.
        d.special_vias[layer] += 1
        i += 1
        last = None


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------
#
# By MASTER NAME only.  The split is checkable against the run's own
# metrics.json (design__instance__count__class:*), and check_classes()
# below does check it, because a classification that drifts from the
# tool's own is a classification that is decorating rather than
# reporting.  The one class this cannot reproduce is the tool's
# clock-buffer / data-buffer split: that is a connectivity property, not
# a name property, and the map does not claim it.

def classify(master):
    if master.startswith("RM_IHPSG13"):
        return "macro"
    if master.startswith("sg13g2_fill") or master.startswith("sg13g2_decap"):
        return "fill"
    if master.startswith("sg13g2_antenna"):
        return "antenna"
    if master.startswith("sg13g2_dfrbpq") or master.startswith("sg13g2_sdfb"):
        return "sequential"
    if master.startswith("sg13g2_lgcp"):
        return "clockgate"
    if (master.startswith("sg13g2_buf")
            or master.startswith("sg13g2_inv")
            or master.startswith("sg13g2_dlygate")):
        return "buffer"
    return "combinational"


LOGIC = ("sequential", "combinational", "buffer", "clockgate")


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------

def rect_union_area(rects):
    """Exact area of a union of axis-aligned rectangles, by x-sweep."""
    if not rects:
        return 0
    xs = sorted({r[0] for r in rects} | {r[2] for r in rects})
    total = 0
    for a, b in zip(xs, xs[1:]):
        if b <= a:
            continue
        spans = sorted((r[1], r[3]) for r in rects if r[0] <= a and r[2] >= b)
        covered = 0
        cy0 = cy1 = None
        for y0, y1 in spans:
            if cy1 is None or y0 > cy1:
                if cy1 is not None:
                    covered += cy1 - cy0
                cy0, cy1 = y0, y1
            else:
                cy1 = max(cy1, y1)
        if cy1 is not None:
            covered += cy1 - cy0
        total += (b - a) * covered
    return total


def row_rects(d, site_h_dbu):
    out = []
    for (_n, _s, x, y, _o, num, by, sx, sy) in d.rows:
        w = sx * (num - 1) + sx if sx else 0
        h = sy * (by - 1) + site_h_dbu if sy else site_h_dbu
        out.append((x, y, x + w, y + h))
    return out


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def extract(run_dir, verbose=True):
    def_path = os.path.join(run_dir, "final", "def", "soc_top.def")
    res_path = os.path.join(run_dir, "resolved.json")
    if not os.path.exists(def_path):
        sys.exit("no DEF at %s" % def_path)

    resolved = {}
    if os.path.exists(res_path):
        with open(res_path) as fh:
            resolved = json.load(fh)

    lefs = list(resolved.get("CELL_LEFS") or [])
    for mac in (resolved.get("MACROS") or {}).values():
        lefs.extend(mac.get("lef") or [])
    lefs = [p for p in lefs if os.path.exists(p)]
    if not lefs:
        sys.exit("resolved.json named no readable LEF; cannot size cells")

    sizes = read_lef_sizes(lefs)
    d = read_def(def_path)
    if d.units is None:
        sys.exit("DEF has no UNITS DISTANCE MICRONS statement")
    U = d.units

    # Row pitch is measured from the DEF's own ROW STEP, not assumed.
    ys = sorted({r[3] for r in d.rows})
    site_h_dbu = min(b - a for a, b in zip(ys, ys[1:])) if len(ys) > 1 else 0
    sxs = {r[7] for r in d.rows if r[7]}
    site_w_dbu = min(sxs) if sxs else 0

    die = d.die
    die_w, die_h = die[2] - die[0], die[3] - die[1]

    # Per-instance rectangles.
    missing = set()
    by_class = collections.defaultdict(list)   # class -> [(x0,y0,x1,y1,master,name)]
    for (name, master, x, y, orient) in d.components:
        sz = sizes.get(master)
        if sz is None:
            missing.add(master)
            continue
        w = int(round(sz[0] * U))
        h = int(round(sz[1] * U))
        if orient in ROTATED:
            w, h = h, w
        by_class[classify(master)].append((x, y, x + w, y + h, master, name))
    if missing:
        sys.exit("no LEF SIZE for: %s" % ", ".join(sorted(missing)))

    def area_of(cls):
        return sum((r[2] - r[0]) * (r[3] - r[1])
                   for r in by_class[cls]) / (U * U)

    def bbox_of(rects):
        if not rects:
            return None
        return (min(r[0] for r in rects), min(r[1] for r in rects),
                max(r[2] for r in rects), max(r[3] for r in rects))

    def group(rects):
        b = bbox_of(rects)
        ar = sum((r[2] - r[0]) * (r[3] - r[1]) for r in rects) / (U * U)
        bb = [v / U for v in b]
        span = [bb[2] - bb[0], bb[3] - bb[1]]
        return {
            "count": len(rects),
            "area_um2": ar,
            "bbox_um": bb,
            "span_um": span,
            "bbox_area_um2": span[0] * span[1],
            "density_in_bbox": ar / (span[0] * span[1]),
        }

    logic = [r for c in LOGIC for r in by_class[c]]
    placed_nonfill = logic + by_class["antenna"]
    # The cells that came out of synthesis, as against the ones the
    # placer, CTS and the resizer added afterwards.  Yosys ran with
    # SYNTH_AUTONAME=0, so a synthesised cell is exactly one whose
    # instance name is `_NNNNN_`; every tool-inserted cell has a name
    # from the tool that inserted it.  docs/48 section 2 draws the same
    # line and reports the span it gives; this reproduces it.
    synth = [r for r in placed_nonfill if re.fullmatch(r"_\d+_", r[5])]

    rows = row_rects(d, site_h_dbu)
    row_area = rect_union_area(rows)
    row_bbox = bbox_of(rows)

    core = resolved.get("CORE_AREA")

    # Power grid: stripe extent per layer, as a union so overlaps are not
    # double-counted.  The top-metal geometry is kept in microns for the
    # map; the thin-metal grid is 46,000 segments and is reported as a
    # number rather than drawn, because drawn it is a solid block.
    pdn = {}
    pdn_rects = {}
    for layer in sorted(set(d.special) | set(d.special_vias)):
        rects = d.special.get(layer, [])
        geo = [(r[1], r[2], r[3], r[4]) for r in rects]
        pdn[layer] = {
            "segments": len(geo),
            "via_placements": d.special_vias.get(layer, 0),
            "union_area_um2": rect_union_area(geo) / (U * U),
            "nets": sorted({r[0] for r in rects}),
        }
        if layer.startswith("TopMetal"):
            pdn_rects[layer] = [
                (g[0] / U, g[1] / U, g[2] / U, g[3] / U) for g in geo]

    # The channel: the widest horizontal band of the core that no macro
    # occupies.  Derived from the macro rectangles rather than named, so
    # it stays right if the floorplan changes.  docs/47 section 6.1 calls
    # this the channel and sized it at 700.08 um.
    bands = sorted((r[1], r[3]) for r in by_class["macro"])
    merged = []
    for lo, hi in bands:
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    gaps = [(merged[i][1], merged[i + 1][0]) for i in range(len(merged) - 1)]
    ch = max(gaps, key=lambda g: g[1] - g[0]) if gaps else None

    def in_band(rects, lo, hi):
        sel = [r for r in rects if lo <= r[1] < hi]
        return {
            "count": len(sel),
            "area_um2": sum((r[2] - r[0]) * (r[3] - r[1])
                            for r in sel) / (U * U),
        }

    regions = {}
    if ch:
        chan_rows = [r for r in rows if ch[0] <= r[1] < ch[1]]
        band = in_band(placed_nonfill, ch[0], ch[1])
        band["flops"] = in_band(by_class["sequential"], ch[0], ch[1])["count"]
        band["y_um"] = [ch[0] / U, ch[1] / U]
        band["height_um"] = (ch[1] - ch[0]) / U
        band["placeable_um2"] = rect_union_area(chan_rows) / (U * U)
        band["density"] = band["area_um2"] / band["placeable_um2"]
        band["share_of_cells"] = band["count"] / len(placed_nonfill)
        regions["channel"] = band
        below = in_band(placed_nonfill, 0, ch[0])
        below["flops"] = in_band(by_class["sequential"], 0, ch[0])["count"]
        above = in_band(placed_nonfill, ch[1], die[3])
        above["flops"] = in_band(by_class["sequential"], ch[1], die[3])["count"]
        regions["below_the_channel"] = below
        regions["above_the_channel"] = above
        # The vertical strip of core to the right of the last macro column.
        rx = max(r[2] for r in by_class["macro"])
        sel = [r for r in placed_nonfill if r[0] >= rx]
        regions["right_of_the_macros"] = {
            "x_from_um": rx / U,
            "width_um": (core[2] * U - rx) / U if core else None,
            "count": len(sel),
            "area_um2": sum((r[2] - r[0]) * (r[3] - r[1])
                            for r in sel) / (U * U),
        }

    macros = []
    for (x0, y0, x1, y1, master, name) in sorted(
            by_class["macro"], key=lambda r: (r[5])):
        macros.append({
            "instance": name,
            "master": master,
            "x_um": x0 / U, "y_um": y0 / U,
            "w_um": (x1 - x0) / U, "h_um": (y1 - y0) / U,
            "area_um2": (x1 - x0) * (y1 - y0) / (U * U),
        })

    e = {
        "source_def": def_path,
        "def_units_per_micron": U,
        "die_um": [die[0] / U, die[1] / U, die[2] / U, die[3] / U],
        "die_area_um2": die_w * die_h / (U * U),
        "core_um": core,
        "core_area_um2": (
            (core[2] - core[0]) * (core[3] - core[1]) if core else None),
        "site_um": [site_w_dbu / U, site_h_dbu / U],
        "rows": {
            "count": len(d.rows),
            "union_area_um2": row_area / (U * U),
            "bbox_um": [v / U for v in row_bbox] if row_bbox else None,
        },
        "macros": macros,
        "macro_area_um2": area_of("macro"),
        "counts": {c: len(v) for c, v in sorted(by_class.items())},
        "areas_um2": {c: area_of(c) for c in sorted(by_class)},
        "logic_cells": group(logic),
        "nonfill_cells": group(placed_nonfill),
        "synthesised_cells": group(synth),
        "regions": regions,
        "pdn": pdn,
        "pins": [
            {"name": p[0], "dir": p[1], "x_um": p[2] / U, "y_um": p[3] / U,
             "layer": p[4]}
            for p in d.pins
        ],
        "declared": {
            "components": d.n_components_declared,
            "nets": d.n_nets_declared,
            "pins": d.n_pins_declared,
        },
    }
    for k in ("logic_cells", "nonfill_cells", "synthesised_cells"):
        e[k]["density_in_rows"] = (
            e[k]["area_um2"] / e["rows"]["union_area_um2"])
    e["macro_fraction_of_die"] = e["macro_area_um2"] / e["die_area_um2"]
    e["memory_over_logic"] = e["macro_area_um2"] / e["nonfill_cells"]["area_um2"]

    e["transistors"] = transistor_census_of(by_class, resolved)
    e["_rects"] = by_class          # not serialised
    e["_rows"] = rows
    e["_units"] = U
    e["_pdn_rects"] = pdn_rects
    return e, d


def check_classes(e, run_dir):
    """Compare the name-based classification with the tool's own metrics."""
    mpath = os.path.join(run_dir, "final", "metrics.json")
    if not os.path.exists(mpath):
        return []
    with open(mpath) as fh:
        m = json.load(fh)
    c = e["counts"]
    checks = [
        ("macros", c["macro"], m.get("design__instance__count__macros")),
        ("fill cells", c["fill"],
         m.get("design__instance__count__class:fill_cell")),
        ("antenna diodes", c["antenna"],
         m.get("design__instance__count__class:antenna_cell")),
        ("sequential cells", c["sequential"],
         m.get("design__instance__count__class:sequential_cell")),
        ("clock gates", c["clockgate"],
         m.get("design__instance__count__class:clock_gate_cell")),
        ("buffers+inverters", c["buffer"],
         sum(m.get("design__instance__count__class:" + k, 0) for k in
             ("buffer", "clock_buffer", "timing_repair_buffer",
              "inverter", "clock_inverter"))),
        ("standard cells, no fill",
         sum(v for k, v in c.items() if k not in ("macro", "fill")),
         m.get("design__instance__count__stdcell")),
        ("standard-cell area um2", round(e["nonfill_cells"]["area_um2"]),
         m.get("design__instance__area__stdcell")),
        ("macro area um2", round(e["macro_area_um2"]),
         m.get("design__instance__area__macros")),
        ("total instances", sum(c.values()),
         m.get("design__instance__count")),
    ]
    return checks


# --------------------------------------------------------------------------
# Transistors
# --------------------------------------------------------------------------
#
# A die photograph comes with a transistor count, and a reader's sense of
# scale is set by it.  Guessing one from a cell count would be exactly the
# kind of plausible number this document exists to refuse, so it is counted
# out of the PDK's own CDL netlists: every `M` card is one device, every
# `X` card is expanded, and the SRAM macro is flattened the same way as a
# NAND gate.  The only judgement left is what a `.SUBCKT` with no devices
# in it means, and there is none of those that matters.

def _cdl_cards(path):
    """Yield logical CDL cards, continuation lines already joined."""
    cur = []
    with open(path, "r", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line.startswith("*") or not line.strip():
                continue
            if line.startswith("+"):
                cur.append(line[1:].strip())
                continue
            if cur:
                yield " ".join(cur)
            cur = [line.strip()]
    if cur:
        yield " ".join(cur)


def read_cdl(path):
    """Return {subckt: (n_mosfets, [child subckt names])}."""
    defs = {}
    name = None
    devs = 0
    kids = []
    for card in _cdl_cards(path):
        up = card.upper()
        if up.startswith(".SUBCKT"):
            name = card.split()[1]
            devs, kids = 0, []
            continue
        if up.startswith(".ENDS"):
            if name is not None:
                defs[name] = (devs, kids)
            name = None
            continue
        if name is None:
            continue
        if card[0] in "Mm":
            m = re.search(r"\bm\s*=\s*([0-9]+)", card)
            devs += int(m.group(1)) if m else 1
        elif card[0] in "Xx":
            toks = card.split()
            child = toks[toks.index("/") + 1] if "/" in toks else toks[-1]
            kids.append(child)
    return defs


def count_transistors(defs, top, _seen=None):
    """Flatten one subckt to a MOSFET count."""
    memo = _seen if _seen is not None else {}
    if top in memo:
        return memo[top]
    if top not in defs:
        return 0                      # a device model, not a subcircuit
    memo[top] = 0                     # break any cycle rather than recurse
    devs, kids = defs[top]
    total = devs + sum(count_transistors(defs, k, memo) for k in kids)
    memo[top] = total
    return total


def transistor_census_of(by_class, resolved):
    """Transistors on this die, by cell master, from the PDK CDL."""
    roots = set()
    for p in (resolved.get("CELL_LEFS") or []):
        roots.add(os.path.dirname(os.path.dirname(p)))
    for mac in (resolved.get("MACROS") or {}).values():
        for p in (mac.get("lef") or []):
            roots.add(os.path.dirname(os.path.dirname(p)))
    defs = {}
    files = []
    for r in roots:
        cdl = os.path.join(r, "cdl")
        if not os.path.isdir(cdl):
            continue
        for f in sorted(os.listdir(cdl)):
            if f.endswith(".cdl"):
                files.append(os.path.join(cdl, f))
                defs.update(read_cdl(os.path.join(cdl, f)))
    if not defs:
        return None
    per_master = {}
    used = collections.Counter()
    for cls, rects in by_class.items():
        for r in rects:
            used[r[4]] += 1
    missing = []
    for master, n in used.items():
        t = count_transistors(defs, master)
        if t == 0 and master not in defs:
            missing.append(master)
        per_master[master] = t
    per_class = collections.Counter()
    for cls, rects in by_class.items():
        for r in rects:
            per_class[cls] += per_master.get(r[4], 0)
    return {
        "cdl_files_read": len(files),
        "subcircuits": len(defs),
        "masters_without_a_cdl_subcircuit": sorted(missing),
        "per_master": {m: {"instances": used[m], "transistors_each":
                           per_master[m],
                           "transistors": used[m] * per_master[m]}
                       for m in sorted(used)},
        "by_class": dict(per_class),
        "total": sum(per_class.values()),
    }


def self_check(e):
    """Assert the properties a correct extraction must have.

    A map is a picture, and a picture cannot be diffed.  These are the
    statements that would be false if the parse, the orientation
    handling or the LEF lookup were wrong, and three of them are also
    statements about the layout that the flow itself checks -- so a
    disagreement here is either a bug in this file or a bug in the run,
    and either is worth knowing.
    """
    U = e["_units"]
    dx0, dy0, dx1, dy1 = [v * U for v in e["die_um"]]
    cx0, cy0, cx1, cy1 = [v * U for v in e["core_um"]]
    macros = e["_rects"]["macro"]
    cells = [r for c in e["_rects"] if c != "macro" for r in e["_rects"][c]]
    rows = e["_rows"]
    out = []

    def check(name, ok, detail=""):
        out.append((name, ok, detail))

    check("every macro is inside the core box",
          all(r[0] >= cx0 and r[1] >= cy0 and r[2] <= cx1 and r[3] <= cy1
              for r in macros))
    over = [(a[5], b[5]) for i, a in enumerate(macros) for b in macros[i + 1:]
            if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]]
    check("no macro overlaps another macro", not over, str(over[:3]))
    check("every standard cell is inside the die box",
          all(r[0] >= dx0 and r[1] >= dy0 and r[2] <= dx1 and r[3] <= dy1
              for r in cells))
    # Cells over macros: the flow's own magic__illegal_overlap__count is 0,
    # so this must find none either.
    bad = 0
    for r in cells:
        for m in macros:
            if r[0] < m[2] and m[0] < r[2] and r[1] < m[3] and m[1] < r[3]:
                bad += 1
                break
    check("no standard cell overlaps a macro", bad == 0, "%d overlap" % bad)
    rowy = {y for (_x0, y, _x1, _y1) in rows}
    offrow = sum(1 for r in cells if r[1] not in rowy)
    check("every standard cell sits on a DEF ROW y", offrow == 0,
          "%d off-row" % offrow)
    check("the macro area union equals the sum of the six rectangles",
          abs(rect_union_area([(r[0], r[1], r[2], r[3]) for r in macros])
              / (U * U) - e["macro_area_um2"]) < 1e-6)
    check("the placeable row union is smaller than the core box",
          e["rows"]["union_area_um2"] < e["core_area_um2"])
    check("core + margins reconstruct the die box",
          abs((cx0 - dx0) - (dx1 - cx1)) < 1e-6
          and abs((cy0 - dy0) - (dy1 - cy1)) < 1e-6)
    return out


HIER_BUCKETS = (
    ("FILLER_", "filler, placed by FillInsertion"),
    ("ANTENNA_", "antenna diode, placed by RepairAntennas"),
    ("clkbuf_", "clock buffer, inserted by CTS"),
    ("hold", "hold-fix buffer, inserted by the resizer"),
    ("fanout", "max-fanout buffer, inserted by the resizer"),
    ("rebuffer", "setup rebuffer, inserted by the resizer"),
    ("wire", "long-wire buffer, inserted by the resizer"),
    ("input", "input port buffer"),
    ("output", "output port buffer"),
    ("net", "net repair cell"),
    ("max_cap", "max-cap repair cell"),
    ("split", "load-splitting buffer"),
)


def hier_report(e):
    """How much of the RTL hierarchy survived into the signed-off DEF."""
    names = [r[5] for rs in e["_rects"].values() for r in rs]
    buckets = collections.Counter()
    dotted = []
    anon = 0
    for n in names:
        if re.fullmatch(r"_\d+_", n):
            anon += 1
            continue
        hit = None
        for pre, _desc in HIER_BUCKETS:
            if n.startswith(pre):
                hit = pre
                break
        if hit:
            buckets[hit] += 1
            continue
        if "." in n:
            dotted.append(n)
        else:
            buckets["<other>"] += 1
    roots = collections.Counter(n.split(".")[0] for n in dotted)
    return {
        "total": len(names),
        "anonymous_NNNNN": anon,
        "tool_inserted": dict(buckets),
        "dotted_rtl_paths": len(dotted),
        "dotted_roots": dict(roots.most_common()),
    }


# --------------------------------------------------------------------------
# SVG
# --------------------------------------------------------------------------

PALETTE = {
    "page": "#ffffff",
    "ink": "#111111",
    "faint": "#8a8a8a",
    "die": "#3a3a3a",
    "core": "#c02f2f",
    "rows": "#e9edf2",
    "rowline": "#b9c4d0",
    "ram": "#2f5d8c",
    "ramfill": "#cfe0f0",
    "rom": "#6b3f8c",
    "romfill": "#e2d5f0",
    "logic": "#1d6b3f",
    "seq": "#b8541c",
    "pdn1": "#c98a00",
    "pdn2": "#8a5b00",
    "bboxline": "#1d6b3f",
    "warn": "#a01c1c",
}

DENSITY_RAMP = ("#eef5ef", "#cfe6d5", "#a8d3b6", "#77bb93", "#46a06e",
                "#238049", "#0d5c31")


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def fmt(v, n=1):
    return ("{:,.%df}" % n).format(v)


def build_svg(e, run_dir, hier, bin_um=18.0):
    U = e["_units"]
    dx0, dy0, dx1, dy1 = e["die_um"]
    dw, dh = dx1 - dx0, dy1 - dy0

    # Layout: a map panel at true scale, a PDN panel at true scale, and a
    # text column.  Everything below is page geometry, in SVG user units;
    # only `sx`/`sy` couple it to the layout.
    PAGE_W = 1480
    MAP_X, MAP_Y, MAP_W = 56, 150, 880
    s = MAP_W / dw                       # SVG units per micron
    MAP_H = dh * s

    def X(um):
        return MAP_X + (um - dx0) * s

    def Y(um):
        return MAP_Y + MAP_H - (um - dy0) * s

    # The legend and the notes are laid out first so the page can be sized
    # to them.  An SVG with a hardcoded height is an SVG that silently
    # clips the paragraph nobody re-read.
    legend = []
    legend_bottom = _legend(legend, MAP_X + MAP_W + 40, MAP_Y - 2, e, hier)
    notes = _notes(e, hier)
    wrapped = [_wrap(n, 178) for n in notes]
    nlines = sum(len(w) for w in wrapped)
    ny = max(MAP_Y + MAP_H, legend_bottom) + 46
    PAGE_H = int(math.ceil(ny - 22 + nlines * 16.5 + 40 + 30))

    o = []
    a = o.append
    a('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
      'width="%d" height="%d" font-family="Helvetica,Arial,sans-serif">'
      % (PAGE_W, PAGE_H, PAGE_W, PAGE_H))
    a('<rect x="0" y="0" width="%d" height="%d" fill="%s"/>'
      % (PAGE_W, PAGE_H, PALETTE["page"]))

    # ---- title -----------------------------------------------------------
    a('<text x="56" y="52" font-size="27" font-weight="bold" fill="%s">'
      'soc_top floorplan region map</text>' % PALETTE["ink"])
    a('<text x="56" y="80" font-size="14.5" fill="%s">'
      'Every rectangle extracted from %s by hw/soc/pnr/floorplan_map.py. '
      'Nothing is drawn by hand.</text>'
      % (PALETTE["faint"], esc(os.path.relpath(e["source_def"], ROOT))))
    a('<text x="56" y="101" font-size="14.5" fill="%s">'
      'Die %s &#215; %s um = %s mm2. DEF UNITS DISTANCE MICRONS %d. '
      'IHP SG13G2, 130 nm. %s instances, %s transistors, %s of them in '
      'the six SRAM macros.</text>'
      % (PALETTE["faint"], fmt(dw, 2), fmt(dh, 2),
         fmt(e["die_area_um2"] / 1e6, 4), int(U),
         fmt(sum(e["counts"].values()), 0),
         fmt(e["transistors"]["total"], 0),
         "%.1f %%" % (100.0 * e["transistors"]["by_class"]["macro"]
                      / e["transistors"]["total"])))
    a('<text x="56" y="122" font-size="14.5" font-weight="bold" fill="%s">'
      'THIS LAYOUT DOES NOT SIGN OFF. See the %d red notes at the foot '
      'of the map.</text>' % (PALETTE["warn"], len(notes)))

    # ---- die -------------------------------------------------------------
    a('<g>')
    a('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="#fbfbfc" '
      'stroke="%s" stroke-width="2"/>'
      % (X(dx0), Y(dy1), dw * s, dh * s, PALETTE["die"]))

    # ---- placeable rows (union of the DEF's ROW statements) --------------
    a('<g fill="%s" stroke="none">' % PALETTE["rows"])
    for (x0, y0, x1, y1) in _merge_rowbands(e["_rows"], U):
        a('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f"/>'
          % (X(x0), Y(y1), (x1 - x0) * s, (y1 - y0) * s))
    a('</g>')

    # ---- cell density field ---------------------------------------------
    logic = [r for c in LOGIC for r in e["_rects"][c]]
    grid, gnx, gny, gx0, gy0 = _density(logic, e, bin_um)
    binpx = bin_um * s
    peak = max(grid.values()) if grid else 1.0
    shades = collections.defaultdict(list)
    for (ix, iy), v in sorted(grid.items()):
        idx = min(len(DENSITY_RAMP) - 1,
                  int(math.ceil((v / peak) * len(DENSITY_RAMP))) - 1)
        if idx >= 0:
            shades[idx].append((ix, iy))
    for idx in sorted(shades):
        a('<g fill="%s" stroke="none">' % DENSITY_RAMP[idx])
        for (ix, iy) in shades[idx]:
            a('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f"/>'
              % (X(gx0 + ix * bin_um), Y(gy0 + (iy + 1) * bin_um),
                 binpx + 0.4, binpx + 0.4))
        a('</g>')

    # ---- top-metal power stripes ----------------------------------------
    for layer, colour, op in (("TopMetal2", PALETTE["pdn2"], 0.30),
                              ("TopMetal1", PALETTE["pdn1"], 0.35)):
        rects = e["_pdn_rects"].get(layer, [])
        if not rects:
            continue
        a('<g fill="%s" fill-opacity="%.2f" stroke="none">' % (colour, op))
        for (x0, y0, x1, y1) in rects:
            a('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f"/>'
              % (X(x0), Y(y1), max(0.7, (x1 - x0) * s),
                 max(0.7, (y1 - y0) * s)))
        a('</g>')

    # ---- macros ----------------------------------------------------------
    for m in e["macros"]:
        is_ram = "2048x64" in m["master"]
        stroke = PALETTE["ram"] if is_ram else PALETTE["rom"]
        fill = PALETTE["ramfill"] if is_ram else PALETTE["romfill"]
        a('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s" '
          'fill-opacity="0.94" stroke="%s" stroke-width="1.8"/>'
          % (X(m["x_um"]), Y(m["y_um"] + m["h_um"]),
             m["w_um"] * s, m["h_um"] * s, fill, stroke))
        cx = X(m["x_um"] + m["w_um"] / 2.0)
        cy = Y(m["y_um"] + m["h_um"] / 2.0)
        short = m["instance"].split(".")[-1]
        kind = "RAM 16 KiB" if is_ram else "ROM 4 KiB"
        a('<text x="%.1f" y="%.1f" font-size="15" font-weight="bold" '
          'text-anchor="middle" fill="%s">%s</text>'
          % (cx, cy - 20, stroke, esc(kind)))
        a('<text x="%.1f" y="%.1f" font-size="12.5" text-anchor="middle" '
          'font-family="monospace" fill="%s">%s</text>'
          % (cx, cy - 2, stroke, esc(m["master"].replace("RM_IHPSG13_", ""))))
        a('<text x="%.1f" y="%.1f" font-size="12.5" text-anchor="middle" '
          'fill="%s">%s &#215; %s um = %s um2</text>'
          % (cx, cy + 17, PALETTE["ink"], fmt(m["w_um"], 2),
             fmt(m["h_um"], 2), fmt(m["area_um2"], 0)))
        a('<text x="%.1f" y="%.1f" font-size="12" text-anchor="middle" '
          'font-family="monospace" fill="%s">%s at (%s, %s)</text>'
          % (cx, cy + 34, PALETTE["faint"], esc(short),
             fmt(m["x_um"], 2), fmt(m["y_um"], 2)))

    # ---- die pins --------------------------------------------------------
    # 18 DEF PINS, drawn where the DEF places them.  A die photograph's
    # pads; this design has none, so these are the routed port shapes on
    # the die edge.
    for p in e["pins"]:
        col = PALETTE["pdn1"] if p["dir"] == "INOUT" else PALETTE["core"]
        a('<circle cx="%.1f" cy="%.1f" r="3.4" fill="%s" stroke="#ffffff" '
          'stroke-width="1"/>' % (X(p["x_um"]), Y(p["y_um"]), col))
    east = [p for p in e["pins"] if p["x_um"] > dx1 - 5]
    if east:
        ey = sorted(east, key=lambda p: p["y_um"])
        a('<text x="%.1f" y="%.1f" font-size="11.5" text-anchor="end" '
          'fill="%s">%d of the 16 signal ports are on this edge</text>'
          % (X(dx1) - 8, Y(ey[-1]["y_um"]) - 8, PALETTE["core"], len(east)))

    # ---- core boundary ---------------------------------------------------
    if e["core_um"]:
        cx0, cy0_, cx1, cy1_ = e["core_um"]
        a('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="none" '
          'stroke="%s" stroke-width="1.6" stroke-dasharray="7 4"/>'
          % (X(cx0), Y(cy1_), (cx1 - cx0) * s, (cy1_ - cy0_) * s,
             PALETTE["core"]))

    # ---- the two standard-cell spans -------------------------------------
    # Outer: every placed standard cell except fill.  Inner: only the
    # cells that came out of synthesis.  They differ by 400 um in x and
    # 550 um in y, and that difference is what CTS and the resizer did.
    nb = e["nonfill_cells"]["bbox_um"]
    a('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="none" '
      'stroke="%s" stroke-width="1.4" stroke-dasharray="2 4"/>'
      % (X(nb[0]), Y(nb[3]), (nb[2] - nb[0]) * s, (nb[3] - nb[1]) * s,
         PALETTE["seq"]))
    sb = e["synthesised_cells"]["bbox_um"]
    a('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="none" '
      'stroke="%s" stroke-width="2" stroke-dasharray="6 3"/>'
      % (X(sb[0]), Y(sb[3]), (sb[2] - sb[0]) * s, (sb[3] - sb[1]) * s,
         PALETTE["bboxline"]))

    # ---- callouts on the map --------------------------------------------
    # The channel is the only part of the die that is not macro, so the
    # callout goes in it, on a backing panel, wrapped to the width of the
    # box it is describing.
    head = ("ALL THE LOGIC IS IN THIS BOX: %s x %s um, %s synthesised "
            "cells, %.1f %% dense"
            % (fmt(e["synthesised_cells"]["span_um"][0], 1),
               fmt(e["synthesised_cells"]["span_um"][1], 1),
               fmt(e["synthesised_cells"]["count"], 0),
               100 * e["synthesised_cells"]["density_in_bbox"]))
    body = _wrap(
        "Ibex, the bus fabric, the CLINT, the GPTIMER and its watchdog, "
        "BUSSTAT, the UART, the APB bridge and the two PnP tables are all "
        "inside it, unlabelled and unlabellable - see note 1.", 96)
    warn = _wrap(
        "soc_npu is NOT on this die: the run's own VERILOG_FILES names 50 "
        "sources and not one of them is the NPU - see note 5.", 96)
    cx0, cy0c = X(sb[0]) + 6, Y(sb[3]) + 8
    nl = 1 + len(body) + len(warn)
    a('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#ffffff" '
      'fill-opacity="0.86" stroke="%s" stroke-width="0.8"/>'
      % (cx0, cy0c, 672, nl * 16.5 + 14, PALETTE["bboxline"]))
    a('<text x="%.1f" y="%.1f" font-size="13.5" font-weight="bold" fill="%s">'
      '%s</text>' % (cx0 + 9, cy0c + 19, PALETTE["bboxline"], esc(head)))
    k = 1
    for seg in body:
        a('<text x="%.1f" y="%.1f" font-size="12" fill="%s">%s</text>'
          % (cx0 + 9, cy0c + 19 + k * 16.5, PALETTE["ink"], esc(seg)))
        k += 1
    for seg in warn:
        a('<text x="%.1f" y="%.1f" font-size="12" font-weight="bold" '
          'fill="%s">%s</text>'
          % (cx0 + 9, cy0c + 19 + k * 16.5, PALETTE["warn"], esc(seg)))
        k += 1

    a('<text x="%.1f" y="%.1f" font-size="12.5" fill="%s">'
      'outer dotted box: all %s placed standard cells except fill, '
      '%s &#215; %s um &#8212; the resizer and CTS reach this far'
      '</text>'
      % (X(nb[0]) + 4, Y(nb[1]) + 14, PALETTE["seq"],
         fmt(e["nonfill_cells"]["count"], 0),
         fmt(e["nonfill_cells"]["span_um"][0], 1),
         fmt(e["nonfill_cells"]["span_um"][1], 1)))

    if e["core_um"]:
        a('<text x="%.1f" y="%.1f" font-size="12.5" fill="%s">'
          'core %s &#215; %s um (dashed red); die edge to core edge '
          '60.00 um left and right, 45.36 um top and bottom</text>'
          % (X(e["core_um"][0]) + 2, Y(e["core_um"][3]) - 6, PALETTE["core"],
             fmt(e["core_um"][2] - e["core_um"][0], 2),
             fmt(e["core_um"][3] - e["core_um"][1], 2)))

    a('</g>')

    # ---- text column -----------------------------------------------------
    o.extend(legend)

    # ---- red notes -------------------------------------------------------
    a('<rect x="56" y="%.1f" width="%d" height="%.1f" fill="#fdf2f2" '
      'stroke="%s" stroke-width="1.2"/>'
      % (ny - 22, PAGE_W - 112, nlines * 16.5 + 40, PALETTE["warn"]))
    a('<text x="70" y="%.1f" font-size="15" font-weight="bold" fill="%s">'
      'WHAT THIS MAP WOULD LET YOU BELIEVE, AND SHOULD NOT</text>'
      % (ny - 2, PALETTE["warn"]))
    line = 0
    for w in wrapped:
        for k, seg in enumerate(w):
            a('<text x="%d" y="%.1f" font-size="12.5" fill="%s">%s</text>'
              % (70 if k == 0 else 87, ny + 20 + line * 16.5,
                 PALETTE["ink"], esc(seg)))
            line += 1

    a('</svg>')
    return "\n".join(o)


def _notes(e, hier):
    return [
        "1. There are no logic blocks on this map because there are none in "
        "the layout. The run hardened with SYNTH_HIERARCHY_MODE=flatten and "
        "SYNTH_AUTONAME=0, so %s of %s component names are `_NNNNN_` and "
        "only %s still carry an RTL path, %s of them tie cells under u_ram "
        "and u_rom. Per-block regions cannot be extracted from this DEF; "
        "they are not merely unshown."
        % (fmt(hier["anonymous_NNNNN"], 0), fmt(hier["total"], 0),
           fmt(hier["dotted_rtl_paths"], 0),
           fmt(hier["dotted_roots"].get("u_ram", 0)
               + hier["dotted_roots"].get("u_rom", 0), 0)),
        "2. The design does not meet timing. 2,003 setup violations at "
        "nom_slow_1p08V_125C with -3.2029 ns worst slack, 3 hold violations "
        "at nom_fast_1p32V_m40C, 14 max-slew and 12 max-cap violations, and "
        "one net routed 2,332.02 um across a die 2,306.40 um wide "
        "(docs/47 sections 8.2 and 8.4).",
        "3. It has never been through Magic DRC, LVS or XOR. RUN_MAGIC_DRC, "
        "RUN_KLAYOUT_DRC, RUN_KLAYOUT_XOR and RUN_LVS are all 0, because "
        "RM_IHPSG13 is a no-go on this PDK version: 1,106,478 Magic DRC, "
        "2,316 KLayout DRC and 359 LVS errors over ONE macro, every one "
        "inside vendor geometry (docs/12 sections 7.5 and 8, docs/54 section "
        "7). Nothing here is evidence that this layout is manufacturable.",
        "4. The green field is standard-cell density, not activity, not "
        "power and not congestion. Fill and decap cells are excluded from "
        "it; they occupy the rest of the pale row area, and they are %.1f %% "
        "of the placed instances and %.1f %% of the placed cell area."
        % (100.0 * e["counts"]["fill"] / sum(e["counts"].values()),
           100.0 * e["areas_um2"]["fill"]
           / (e["areas_um2"]["fill"] + e["nonfill_cells"]["area_um2"])),
        "5. The NPU is not on this die. hw/soc/rtl/soc_top.v instantiates "
        "u_npu, but the run's own resolved.json lists 50 VERILOG_FILES and "
        "none of them is soc_npu.v, soc_npu_ser.v or pilot_top.v: soc_npu "
        "was integrated in docs/51, after this run. docs/51 section 11 "
        "prices it at 12,421 cells and 209,739.0834 um2, which is %.1f %% of "
        "every standard cell on this die put together. This map is of an SoC "
        "that is a block short."
        % (100.0 * 209739.0834 / e["nonfill_cells"]["area_um2"]),
    ]


def _wrap(text, n):
    """Greedy word wrap.  SVG has no reflow, so the wrapping is done here
    rather than left to a renderer that will not do it."""
    out, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > n:
            out.append(cur)
            cur = word
        else:
            cur = word if not cur else cur + " " + word
    if cur:
        out.append(cur)
    return out


def _merge_rowbands(rows, U):
    """Rows share y bands; merge each band's x spans so the SVG has tens of
    rectangles rather than 1,403."""
    bands = collections.defaultdict(list)
    for (x0, y0, x1, y1) in rows:
        bands[(y0, y1)].append((x0, x1))
    out = []
    for (y0, y1), spans in bands.items():
        spans.sort()
        cur = list(spans[0])
        for x0, x1 in spans[1:]:
            if x0 <= cur[1]:
                cur[1] = max(cur[1], x1)
            else:
                out.append((cur[0] / U, y0 / U, cur[1] / U, y1 / U))
                cur = [x0, x1]
        out.append((cur[0] / U, y0 / U, cur[1] / U, y1 / U))
    # Vertically merge identical x spans in adjacent bands.
    cols = collections.defaultdict(list)
    for (x0, y0, x1, y1) in out:
        cols[(x0, x1)].append((y0, y1))
    merged = []
    for (x0, x1), ys in cols.items():
        ys.sort()
        cy0, cy1 = ys[0]
        for y0, y1 in ys[1:]:
            if y0 <= cy1 + 1e-9:
                cy1 = max(cy1, y1)
            else:
                merged.append((x0, cy0, x1, cy1))
                cy0, cy1 = y0, y1
        merged.append((x0, cy0, x1, cy1))
    return merged


def _density(rects, e, bin_um):
    """Cell area per square bin, in um2, keyed by integer bin index.

    Each cell contributes its area to the bin its centre falls in.  At an
    18 um bin against a 3.78 um row and cells 0.48-5 um wide the error
    from not clipping is below one cell width per bin edge, and the field
    is a field, not a measurement of any one bin.
    """
    U = e["_units"]
    dx0, dy0 = e["die_um"][0], e["die_um"][1]
    grid = collections.Counter()
    for (x0, y0, x1, y1, _m, _n) in rects:
        cx = (x0 + x1) / 2.0 / U
        cy = (y0 + y1) / 2.0 / U
        ix = int((cx - dx0) // bin_um)
        iy = int((cy - dy0) // bin_um)
        grid[(ix, iy)] += (x1 - x0) * (y1 - y0) / (U * U)
    nx = int(math.ceil((e["die_um"][2] - dx0) / bin_um))
    ny = int(math.ceil((e["die_um"][3] - dy0) / bin_um))
    # Normalise to occupancy fraction of a bin.
    for k in list(grid):
        grid[k] = grid[k] / (bin_um * bin_um)
    return grid, nx, ny, dx0, dy0


def _legend(o, x, y, e, hier):
    a = o.append

    def head(t):
        nonlocal y
        y += 24
        a('<text x="%d" y="%d" font-size="14" font-weight="bold" fill="%s">'
          '%s</text>' % (x, y, PALETTE["ink"], esc(t)))
        y += 6

    def row(label, value, colour=None, swatch=None):
        nonlocal y
        y += 18
        if swatch:
            a('<rect x="%d" y="%d" width="13" height="11" fill="%s" '
              'stroke="#666" stroke-width="0.6"/>' % (x, y - 10, swatch))
        a('<text x="%d" y="%d" font-size="12.5" fill="%s">%s</text>'
          % (x + (20 if swatch else 0), y, colour or PALETTE["ink"],
             esc(label)))
        a('<text x="%d" y="%d" font-size="12.5" text-anchor="end" '
          'font-family="monospace" fill="%s">%s</text>'
          % (x + 476, y, colour or PALETTE["ink"], esc(value)))

    die_a = e["die_area_um2"]
    head("Area, from the DEF and the PDK LEF")
    row("die  2306.40 x 2075.22 um", "%s um2" % fmt(die_a, 0))
    row("core 2186.40 x 1984.50 um",
        "%s um2  %.1f%%" % (fmt(e["core_area_um2"], 0),
                            100 * e["core_area_um2"] / die_a))
    row("placeable rows (union of 1,403 ROWs)",
        "%s um2  %.1f%%" % (fmt(e["rows"]["union_area_um2"], 0),
                            100 * e["rows"]["union_area_um2"] / die_a),
        swatch=PALETTE["rows"])
    row("6 SRAM macros",
        "%s um2  %.1f%%" % (fmt(e["macro_area_um2"], 2),
                            100 * e["macro_area_um2"] / die_a),
        swatch=PALETTE["ramfill"])
    row("   4 x 1P_2048x64 (64 KiB RAM)",
        "%s um2" % fmt(4 * e["macros"][0]["area_um2"], 2))
    row("   2 x 1P_1024x32 (8 KiB ROM)",
        "%s um2" % fmt(2 * [m for m in e["macros"]
                            if "1024x32" in m["master"]][0]["area_um2"], 2))
    row("standard cells, excluding fill",
        "%s um2  %.1f%%" % (fmt(e["nonfill_cells"]["area_um2"], 2),
                            100 * e["nonfill_cells"]["area_um2"] / die_a),
        swatch=DENSITY_RAMP[4])
    row("fill and decap cells",
        "%s um2  %.1f%%" % (fmt(e["areas_um2"]["fill"], 2),
                            100 * e["areas_um2"]["fill"] / die_a))
    row("memory / logic, at this stage",
        "%.2f x" % e["memory_over_logic"])

    t = e.get("transistors")
    if t:
        head("Transistors, flattened from the PDK CDL netlists")
        for k, label in (("macro", "in the six SRAM macros"),
                         ("fill", "in fill and decap cells"),
                         ("combinational", "in combinational cells"),
                         ("sequential", "in flip-flops"),
                         ("buffer", "in buffers and inverters"),
                         ("clockgate", "in the one clock gate")):
            row(label, "%s  %.1f %%" % (fmt(t["by_class"].get(k, 0), 0),
                                        100.0 * t["by_class"].get(k, 0)
                                        / t["total"]))
        row("total on this die", fmt(t["total"], 0))

    head("Instances, classified by LEF master name")
    for label, key in (("sequential (dfrbpq)", "sequential"),
                       ("combinational and ties", "combinational"),
                       ("buffers, inverters, delay gates", "buffer"),
                       ("integrated clock gate", "clockgate"),
                       ("antenna diodes", "antenna"),
                       ("fill and decap", "fill"),
                       ("SRAM macros", "macro")):
        row(label, fmt(e["counts"][key], 0))
    row("total DEF COMPONENTS", fmt(sum(e["counts"].values()), 0))

    ch = e["regions"].get("channel")
    if ch:
        head("The channel, the only region with logic in it")
        row("y %s to %s um" % (fmt(ch["y_um"][0], 2), fmt(ch["y_um"][1], 2)),
            "%s um tall" % fmt(ch["height_um"], 2))
        row("placeable area inside it",
            "%s um2" % fmt(ch["placeable_um2"], 0))
        row("standard cells in it",
            "%s  %.1f %% of all" % (fmt(ch["count"], 0),
                                    100 * ch["share_of_cells"]))
        row("flip-flops in it",
            "%s of %s" % (fmt(ch["flops"], 0), fmt(e["counts"]["sequential"], 0)))
        row("density inside the channel", "%.2f %%" % (100 * ch["density"]),
            colour=PALETTE["warn"])
        row("cells above the channel",
            fmt(e["regions"]["above_the_channel"]["count"], 0))
        row("cells below the channel",
            fmt(e["regions"]["below_the_channel"]["count"], 0))

    head("The standard-cell strip")
    for label, key in (("synthesised cells only", "synthesised_cells"),
                       ("every placed cell but fill", "nonfill_cells")):
        g = e[key]
        row(label, "%s cells" % fmt(g["count"], 0))
        row("   origin", "(%s, %s) um" % (fmt(g["bbox_um"][0], 1),
                                          fmt(g["bbox_um"][1], 1)))
        row("   span", "%s x %s um" % (fmt(g["span_um"][0], 1),
                                       fmt(g["span_um"][1], 1)))
        row("   cell area / that box", "%.2f %%" % (100 * g["density_in_bbox"]))
        row("   cell area / placeable rows",
            "%.2f %%" % (100 * g["density_in_rows"]))

    head("Power grid, from DEF SPECIALNETS (2 nets: VPWR, VGND)")
    for layer in ("Metal1", "Metal2", "Metal3", "Metal4", "Metal5",
                  "TopMetal1", "TopMetal2"):
        p = e["pdn"].get(layer)
        if not p:
            continue
        sw = {"TopMetal1": PALETTE["pdn1"],
              "TopMetal2": PALETTE["pdn2"]}.get(layer)
        if p["segments"]:
            row("%s  %s segments" % (layer, fmt(p["segments"], 0)),
                "%s um2" % fmt(p["union_area_um2"], 0), swatch=sw)
        else:
            row("%s  vias only" % layer,
                "%s placements" % fmt(p["via_placements"], 0), swatch=sw)
    row("drawn on the map",
        "TopMetal1, TopMetal2 only")

    head("What survived flattening")
    row("component names `_NNNNN_`", fmt(hier["anonymous_NNNNN"], 0),
        colour=PALETTE["warn"])
    row("names inserted by the tools", fmt(sum(hier["tool_inserted"].values()), 0))
    row("names still carrying an RTL path", fmt(hier["dotted_rtl_paths"], 0),
        colour=PALETTE["warn"])
    row("   of which under u_ram / u_rom",
        fmt(hier["dotted_roots"].get("u_ram", 0)
            + hier["dotted_roots"].get("u_rom", 0), 0))
    return y


# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", default=DEFAULT_RUN,
                    help="LibreLane run directory (default: %(default)s)")
    ap.add_argument("--out-svg", default=DEFAULT_SVG)
    ap.add_argument("--out-json", default=DEFAULT_JSON)
    ap.add_argument("--bin", type=float, default=18.0,
                    help="density bin edge in um (default: %(default)s)")
    ap.add_argument("--hier-report", action="store_true",
                    help="print the surviving-hierarchy census and exit")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)

    e, _d = extract(args.run)
    hier = hier_report(e)

    if args.hier_report:
        print("hierarchy surviving into %s" % e["source_def"])
        print("  total components          %8d" % hier["total"])
        print("  anonymous `_NNNNN_`       %8d  (%.2f %%)"
              % (hier["anonymous_NNNNN"],
                 100.0 * hier["anonymous_NNNNN"] / hier["total"]))
        for pre, desc in HIER_BUCKETS:
            n = hier["tool_inserted"].get(pre, 0)
            if n:
                print("  %-24s  %8d  %s" % (pre + "*", n, desc))
        n = hier["tool_inserted"].get("<other>", 0)
        if n:
            print("  %-24s  %8d" % ("<other>", n))
        print("  dotted RTL paths          %8d  (%.3f %%)"
              % (hier["dotted_rtl_paths"],
                 100.0 * hier["dotted_rtl_paths"] / hier["total"]))
        for root, n in hier["dotted_roots"].items():
            print("      %-30s %6d" % (root, n))
        return 0

    return _finish(e, args, hier)


def _finish(e, args, hier):
    U = e["_units"]
    print("floorplan_map.py: %s" % e["source_def"])
    print("  DEF UNITS DISTANCE MICRONS %d" % U)
    print("  die   %.2f x %.2f um = %.4f mm2"
          % (e["die_um"][2] - e["die_um"][0], e["die_um"][3] - e["die_um"][1],
             e["die_area_um2"] / 1e6))
    print("  core  %s" % e["core_um"])
    print("  site  %.2f x %.2f um, %d ROWs, union %.2f um2"
          % (e["site_um"][0], e["site_um"][1], e["rows"]["count"],
             e["rows"]["union_area_um2"]))
    print("  macros")
    for m in e["macros"]:
        print("    %-34s %-38s (%9.2f, %9.2f)  %8.2f x %8.2f = %14.2f um2"
              % (m["instance"], m["master"], m["x_um"], m["y_um"],
                 m["w_um"], m["h_um"], m["area_um2"]))
    print("  macro area total   %16.2f um2  (%.2f %% of die)"
          % (e["macro_area_um2"], 100 * e["macro_fraction_of_die"]))
    print("  standard cells (no fill) %10d  %14.4f um2"
          % (e["nonfill_cells"]["count"], e["nonfill_cells"]["area_um2"]))
    print("  fill and decap           %10d  %14.4f um2"
          % (e["counts"]["fill"], e["areas_um2"]["fill"]))
    print("  memory / logic           %10.4f x" % e["memory_over_logic"])
    for key in ("synthesised_cells", "nonfill_cells"):
        g = e[key]
        print("  %-18s %6d cells  origin (%7.1f, %7.1f)  span %7.1f x %7.1f"
              "  %5.2f %% of its box  %5.2f %% of the rows"
              % (key, g["count"], g["bbox_um"][0], g["bbox_um"][1],
                 g["span_um"][0], g["span_um"][1],
                 100 * g["density_in_bbox"], 100 * g["density_in_rows"]))
    for name, g in sorted(e["regions"].items()):
        print("  region %-22s %6d cells  %12.2f um2%s"
              % (name, g["count"], g["area_um2"],
                 "  %.2f %% dense" % (100 * g["density"])
                 if "density" in g else ""))
    t = e.get("transistors")
    if t:
        print("  transistors, flattened from %d PDK CDL files, %d subcircuits"
              % (t["cdl_files_read"], t["subcircuits"]))
        for k in sorted(t["by_class"], key=lambda k: -t["by_class"][k]):
            print("    %-15s %12d  %5.1f %%"
                  % (k, t["by_class"][k],
                     100.0 * t["by_class"][k] / t["total"]))
        print("    %-15s %12d" % ("TOTAL", t["total"]))
        if t["masters_without_a_cdl_subcircuit"]:
            print("    NOT COUNTED (no CDL subcircuit): %s"
                  % ", ".join(t["masters_without_a_cdl_subcircuit"]))
    print("  PDN")
    for layer in sorted(e["pdn"]):
        p = e["pdn"][layer]
        print("    %-11s %6d segments  %6d vias  union %12.2f um2  nets %s"
              % (layer, p["segments"], p["via_placements"],
                 p["union_area_um2"], ",".join(p["nets"]) or "-"))
    print("  geometry self-check")
    for name, ok, detail in self_check(e):
        print("    [%s] %s%s" % ("ok " if ok else "FAIL", name,
                                 "  " + detail if detail and not ok else ""))
    print("  cross-check against the run's own metrics.json")
    ok = True
    for label, mine, theirs in check_classes(e, args.run):
        mark = "ok " if mine == theirs else "DIFF"
        ok = ok and mine == theirs
        print("    [%s] %-20s script %8s   metrics %8s"
              % (mark, label, mine, theirs))
    if not ok:
        print("    NOTE: a DIFF above means the map and the flow disagree; "
              "the map is wrong until it is explained.")

    svg = build_svg(e, args.run, hier, bin_um=args.bin)

    if args.no_write:
        return 0
    for path in (args.out_svg, args.out_json):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(args.out_svg, "w") as fh:
        fh.write(svg)
    pub = {k: v for k, v in e.items() if not k.startswith("_")}
    pub["hierarchy"] = hier
    pub["class_crosscheck"] = [
        {"quantity": q, "script": a, "metrics_json": b}
        for (q, a, b) in check_classes(e, args.run)
    ]
    with open(args.out_json, "w") as fh:
        json.dump(pub, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print("  wrote %s  (%d bytes)" % (args.out_svg, len(svg)))
    print("  wrote %s" % args.out_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
