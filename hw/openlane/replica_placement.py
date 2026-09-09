#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: CERN-OHL-W-2.0
"""How far apart the TMR replicas actually are on the die.

    python3 hw/openlane/replica_placement.py <run-dir> [--json]

WHY THIS EXISTS

`sw/tests/test_synthesis_guards.py` counts mapped flip-flops by instance
path and asserts three banks of 55. That is the instrument `docs/33`
built after the synthesiser merged the three replicas into one, and it
is the right instrument for a *synthesis* event. It establishes LOGICAL
redundancy: three banks exist in the netlist.

It says nothing about where they are. A majority vote over three
registers placed in adjacent rows is defeated by whatever corrupts two
adjacent registers, and nothing in this flow asks the placer to keep
them apart. Until this script there was no measurement either way, and
"the configuration state is protected by TMR" was being read as a
statement about the die when the evidence was about the netlist.

It is the same shape as the defect that motivated the census, one
abstraction level down: a check that passes, read wider than what it
looked at. The guard runs on the synthesis netlist and CANNOT see
placement, by construction -- a guard must sit at the stage that can
satisfy it.

WHAT IT MEASURES

Cell bounding boxes from the run's own final DEF, in micrometres:

  * centre-to-centre and edge-to-edge distance for every cross-replica
    flip-flop pair;
  * the same restricted to CORRESPONDING BITS, which is the pairing an
    upset must corrupt two of;
  * how many pairs abut, share a row, or sit within one site pitch;
  * where each bank sits, and whether a flop's nearest neighbour is in
    its own replica or another one.

WHAT IT DOES NOT MEASURE, AND THIS IS NOT A DETAIL

A distance is not a safety argument. No SEU or MBU cross-section,
charge-collection radius or LET threshold for IHP SG13G2 was measured
or is available here, and these are cell bounding boxes rather than
sensitive nodes. The numbers establish that a layout PERMITS a
common-mode upset of two replicas; they do not say one occurs at any
fluence, and they do not say what separation would prevent one.
"""

import argparse
import itertools
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# The flip-flop this flow maps to, and its geometry from the PDK LEF.
FF_CELL = "sg13g2_dfrbpq_1"
CELL_W, CELL_H = 12.96, 3.78          # 27 sites by 1 row
SITE, ROW_H = 0.48, 3.78

INST_RE = re.compile(r"^\s*(sg13g2_\w+)\s+(\\?\S+?)\s*\((.*?)\);", re.S | re.M)
PIN_RE = re.compile(r"\.(\w+)\(\s*(\\?[^)]*?)\s*\)")
COMP_RE = re.compile(
    r"^\s*-\s+(\S+)\s+(\S+)\s+.*?PLACED\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+(\w+)")


def read_netlist(path):
    txt = Path(path).read_text()
    out = []
    for m in INST_RE.finditer(txt):
        pins = {p: n.lstrip("\\").strip() for p, n in PIN_RE.findall(m.group(3))}
        out.append((m.group(1), m.group(2).lstrip("\\"), pins))
    return out


def bit_index(insts, replicas):
    """Attribute each replica flip-flop to the storage bit it holds.

    A flop's Q reaches a net named `<replica>.bits[i]` through at most a
    few inverters and buffers. Where it does not -- a MIX replica stores
    a transform of the value, so the net may be optimised away -- the
    flop is still attributed to its replica and left without an index,
    and the caller says so rather than guessing.
    """
    fwd = defaultdict(list)
    for cell, _name, pins in insts:
        if re.match(r"sg13g2_(inv|buf|dlygate)", cell):
            a, o = pins.get("A"), pins.get("Y") or pins.get("X")
            if a and o:
                fwd[a].append(o)
    idx, unindexed = {}, Counter()
    for cell, name, pins in insts:
        if cell != FF_CELL:
            continue
        rep = next((r for r in replicas if name.startswith(r + ".")), None)
        if rep is None:
            continue
        pat = re.compile(r"^" + re.escape(rep) + r"\.bits\[(\d+)\]$")
        seen, frontier, found = {pins["Q"]}, [pins["Q"]], None
        for _ in range(4):
            nxt = []
            for net in frontier:
                m = pat.match(net)
                if m:
                    found = int(m.group(1))
                    break
                for y in fwd[net]:
                    if y not in seen:
                        seen.add(y)
                        nxt.append(y)
            if found is not None:
                break
            frontier = nxt
        idx[name] = (rep, found)
        if found is None:
            unindexed[rep] += 1
    return idx, unindexed


def read_def(path, wanted):
    units, die, placed, total = None, None, {}, 0
    inside = False
    for line in Path(path).open():
        if line.startswith("UNITS DISTANCE MICRONS"):
            units = float(line.split()[3])
        elif line.startswith("DIEAREA"):
            die = [int(x) for x in re.findall(r"-?\d+", line)]
        elif line.startswith("COMPONENTS"):
            inside = True
        elif line.startswith("END COMPONENTS"):
            inside = False
        elif inside:
            m = COMP_RE.match(line)
            if not m:
                continue
            total += 1
            if m.group(1) in wanted:
                placed[m.group(1)] = (int(m.group(3)) / units,
                                      int(m.group(4)) / units)
    return units, die, placed, total


def c2c(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def edge(p, q):
    return math.hypot(max(0.0, abs(p[0] - q[0]) - CELL_W),
                      max(0.0, abs(p[1] - q[1]) - CELL_H))


def measure(run_dir, replicas):
    run = Path(run_dir)
    defs = sorted(run.glob("final/def/*.def")) or sorted(run.glob("*.def"))
    nls = sorted(run.glob("final/nl/*.nl.v")) or sorted(run.glob("*.nl.v"))
    if not defs or not nls:
        raise SystemExit(f"no final DEF or netlist under {run}")
    insts = read_netlist(nls[0])
    idx, unindexed = bit_index(insts, replicas)
    if not idx:
        raise SystemExit(
            f"no flip-flop under any of {replicas} in {nls[0].name}. A run "
            "hardened with SYNTH_HIERARCHY_MODE = flatten destroys instance "
            "paths and cannot be measured this way.")
    units, die, placed, total = read_def(defs[0], set(idx))

    pts = defaultdict(dict)      # replica -> bit or name -> (cx, cy, x, y)
    for name, (x, y) in placed.items():
        rep, bit = idx[name]
        pts[rep][bit if bit is not None else name] = (x + CELL_W / 2,
                                                      y + CELL_H / 2, x, y)

    pairs = []
    for r1, r2 in itertools.combinations(sorted(pts), 2):
        for k1, p in pts[r1].items():
            for k2, q in pts[r2].items():
                pairs.append((c2c(p, q), edge(p, q), r1, k1, r2, k2))
    pairs.sort()
    d = [a[0] for a in pairs]

    same = []
    common = set.intersection(*[{k for k in pts[r] if isinstance(k, int)}
                                for r in pts]) if len(pts) > 1 else set()
    for b in sorted(common):
        for r1, r2 in itertools.combinations(sorted(pts), 2):
            same.append((c2c(pts[r1][b], pts[r2][b]),
                         edge(pts[r1][b], pts[r2][b]), b, r1, r2))
    same.sort()

    own = other = 0
    for r in pts:
        for k, p in pts[r].items():
            mine = min((c2c(p, q) for kk, q in pts[r].items() if kk != k),
                       default=math.inf)
            theirs = min(c2c(p, q) for r2 in pts if r2 != r
                         for q in pts[r2].values())
            own, other = (own + 1, other) if mine < theirs else (own, other + 1)

    def gap_count(seq, thr):
        return sum(1 for a in seq if a[1] <= thr + 1e-9)

    res = {
        "run": str(run),
        "def": defs[0].name,
        "netlist": nls[0].name,
        "units_per_micron": units,
        "die_um": [v / units for v in die] if die else None,
        "components": total,
        "site_um": SITE, "row_height_um": ROW_H,
        "cell_um": [CELL_W, CELL_H],
        "flops_per_replica": {r: len(pts[r]) for r in sorted(pts)},
        "unindexed_per_replica": dict(unindexed),
        "cross_pairs": len(pairs),
        "min_c2c_um": round(d[0], 4) if d else None,
        "median_c2c_um": round(statistics.median(d), 4) if d else None,
        "max_c2c_um": round(d[-1], 4) if d else None,
        "min_edge_um": round(min(a[1] for a in pairs), 4) if pairs else None,
        "abutting_pairs": gap_count(pairs, 0.0),
        "pairs_within_one_site": gap_count(pairs, SITE),
        "same_bit_pairs": len(same),
        "same_bit_min_c2c_um": round(same[0][0], 4) if same else None,
        "same_bit_median_c2c_um":
            round(statistics.median([x[0] for x in same]), 4) if same else None,
        "same_bit_abutting": gap_count(same, 0.0),
        "nearest_is_own_replica": own,
        "nearest_is_another_replica": other,
        "closest": [
            {"a": f"{r1}[{k1}]", "b": f"{r2}[{k2}]",
             "c2c_um": round(cc, 4), "edge_um": round(ee, 4)}
            for cc, ee, r1, k1, r2, k2 in pairs[:8]],
    }
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", help="a LibreLane run directory")
    ap.add_argument("--replicas", default="u_pilot.u_cfg_a,u_pilot.u_cfg_b,"
                                          "u_pilot.u_cfg_c")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    res = measure(args.run, args.replicas.split(","))
    if args.json:
        print(json.dumps(res, indent=2))
        return 0
    print(f"{res['def']}  die {res['die_um']} um, {res['components']} components")
    print(f"site {res['site_um']} um, row {res['row_height_um']} um, "
          f"cell {res['cell_um'][0]} x {res['cell_um'][1]} um")
    print(f"flip-flops per replica: {res['flops_per_replica']}"
          + (f"  (unindexed: {res['unindexed_per_replica']})"
             if res['unindexed_per_replica'] else ""))
    print(f"\ncross-replica pairs: {res['cross_pairs']}")
    print(f"  centre-to-centre  min {res['min_c2c_um']}  "
          f"median {res['median_c2c_um']}  max {res['max_c2c_um']} um")
    print(f"  edge-to-edge      min {res['min_edge_um']} um "
          f"({res['abutting_pairs']} pairs abut, "
          f"{res['pairs_within_one_site']} within one {res['site_um']} um site)")
    print(f"\ncorresponding-bit pairs: {res['same_bit_pairs']}")
    print(f"  centre-to-centre  min {res['same_bit_min_c2c_um']}  "
          f"median {res['same_bit_median_c2c_um']} um")
    print(f"  {res['same_bit_abutting']} of them abut")
    if res["unindexed_per_replica"]:
        n = sum(res["unindexed_per_replica"].values())
        print(f"  UNDERCOUNT: {n} flip-flop(s) could not be attributed to a "
              f"bit, so the\n  corresponding-bit figures above are a LOWER "
              f"BOUND. A MIX replica stores a\n  transform of the value and "
              f"its bits[] nets may be optimised away; recovering\n  them "
              f"needs the decode network, which this script does not walk. "
              f"The\n  cross-replica figures are unaffected -- every "
              f"flip-flop is placed and counted.")
    print(f"\nnearest fellow replica flop is in its OWN replica for "
          f"{res['nearest_is_own_replica']}, in ANOTHER for "
          f"{res['nearest_is_another_replica']}")
    print("\nclosest pairs:")
    for c in res["closest"]:
        print(f"  {c['a']:16s} {c['b']:16s} c2c {c['c2c_um']:8.2f}  "
              f"edge {c['edge_um']:6.2f} um")
    print("\nA distance is not a safety argument: no cross-section, "
          "charge-collection radius\nor LET threshold for this process is "
          "measured or known here, and these are cell\nbounding boxes rather "
          "than sensitive nodes. See the module docstring.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
