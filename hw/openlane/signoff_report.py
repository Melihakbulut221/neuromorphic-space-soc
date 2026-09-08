#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Extract one sign-off set from a LibreLane run directory.

Every number quoted in docs/20 comes out of this script rather than out
of a hand-grep, so that two runs being compared are read the same way.
It reads final/metrics.json plus the per-step or_metrics_out.json files
and prints a fixed set of keys; anything it cannot find prints as
'<absent>' rather than being silently dropped.

Usage:
    ./signoff_report.py <run_dir> [<run_dir> ...]
    ./signoff_report.py --json <run_dir>
"""

import glob
import json
import os
import sys

# (label, metrics.json key). None key means "computed below".
# (label, [candidate keys]). The first key that is present wins. There
# are alternatives because LibreLane's cell CLASSIFICATION is per-PDK:
# sky130A resolves cells into sequential/buffer/inverter/tap classes,
# ihp-sg13g2 lumps everything not a fill cell into `class:standard_cell`.
# Reading one key and reporting '<absent>' for the other PDK would make
# the two columns of the docs/20 tables silently non-comparable.
SCALARS = [
    ("instances, incl. fill", ["design__instance__count"]),
    ("cells, excl. fill", ["design__instance__count__stdcell"]),
    ("cells, sequential", ["design__instance__count__class:sequential_cell"]),
    ("timing-repair buffers", ["design__instance__count__class:timing_repair_buffer"]),
    ("of which setup buffers", ["design__instance__count__setup_buffer"]),
    ("of which hold buffers", ["design__instance__count__hold_buffer"]),
    ("area, die", ["design__die__area"]),
    ("area, core", ["design__core__area"]),
    ("area, cells excl. fill", ["design__instance__area__stdcell"]),
    ("area, sequential cells", ["design__instance__area__class:sequential_cell"]),
    ("area, repair buffers", ["design__instance__area__class:timing_repair_buffer"]),
    ("area, clock buffers", ["design__instance__area__class:clock_buffer"]),
    ("utilization", ["design__instance__utilization"]),
    ("route DRC", ["route__drc_errors"]),
    ("wirelength, routed", ["route__wirelength"]),
    ("antenna nets", ["route__antenna_violation__count"]),
    ("antenna pins", ["route__antenna_violation__count__pins"]),
    ("antenna diodes", ["antenna_diodes_count"]),
    ("Magic DRC", ["magic__drc_error__count"]),
    ("KLayout DRC", ["klayout__drc_error__count"]),
    ("KLayout XOR", ["design__xor_difference__count"]),
    ("Netgen LVS", ["design__lvs_error__count"]),
    ("LVS unmatched nets", ["design__lvs_unmatched_net__count"]),
    ("LVS unmatched devices", ["design__lvs_unmatched_device__count"]),
    ("LVS unmatched pins", ["design__lvs_unmatched_pin__count"]),
    ("LVS property fails", ["design__lvs_property_fail__count"]),
    ("disconnected pins", ["design__disconnected_pin__count"]),
    ("power-grid violations", ["design__power_grid_violation__count"]),
    ("max-fanout violations", ["design__max_fanout_violation__count"]),
    ("design__violations", ["design__violations"]),
    ("flow errors", ["flow__errors__count"]),
]

SLACK_PREFIXES = [
    ("setup ws", "timing__setup__ws__corner:"),
    ("setup vio", "timing__setup_vio__count__corner:"),
    ("hold ws", "timing__hold__ws__corner:"),
    ("hold vio", "timing__hold_vio__count__corner:"),
    ("max slew vio", "design__max_slew_violation__count__corner:"),
    ("max cap vio", "design__max_cap_violation__count__corner:"),
]


def load(run_dir):
    p = os.path.join(run_dir, "final", "metrics.json")
    if os.path.exists(p):
        return json.load(open(p)), p
    # Flow not finished, or final/ pruned: fold the step metrics in order.
    merged, src = {}, "step or_metrics_out.json files"
    for f in sorted(glob.glob(os.path.join(run_dir, "*", "or_metrics_out.json"))):
        try:
            merged.update(json.load(open(f)))
        except Exception:
            pass
    for f in sorted(glob.glob(os.path.join(run_dir, "*", "*.metrics.json"))):
        try:
            merged.update(json.load(open(f)))
        except Exception:
            pass
    return merged, src


def flop_count(run_dir, m):
    """Mapped flip-flops, from the synthesis cell-count report.

    design__instance__count__class:sequential is the post-route number and
    counts every sequential cell; the synthesis stat report is what the
    docs/15 and docs/16 flip-flop figures are quoted against, so both are
    reported and a divergence is visible rather than averaged away.
    """
    out = {}
    for f in glob.glob(os.path.join(run_dir, "*yosys-synthesis", "reports", "stat.json")):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        cells = d.get("design", {}).get("num_cells_by_type", {})
        ff = {k: v for k, v in cells.items() if "df" in k or "sdf" in k or "dl" in k}
        out["synth flip-flops"] = sum(ff.values())
        out["synth flip-flop types"] = ff
        out["synth cells"] = d.get("design", {}).get("num_cells")
        out["synth area"] = d.get("design", {}).get("area")
    return out


def runtime(run_dir):
    total = 0.0
    for f in glob.glob(os.path.join(run_dir, "*", "runtime.txt")):
        try:
            h, mnt, s = open(f).read().strip().split(":")
            total += int(h) * 3600 + int(mnt) * 60 + float(s)
        except Exception:
            pass
    return total


def report(run_dir):
    m, src = load(run_dir)
    print(f"=== {run_dir}")
    print(f"    metrics from: {src}")
    rt = runtime(run_dir)
    print(f"    summed step runtime: {rt/60:.1f} min")
    for k, v in flop_count(run_dir, m).items():
        print(f"    {k:34s} {v}")
    for label, keys in SCALARS:
        v = next((m[k] for k in keys if k in m), "<absent>")
        print(f"    {label:26s} {v}")
    corners = sorted(
        {k.split(":", 1)[1] for k in m if k.startswith("timing__setup__ws__corner:")}
    )
    if corners:
        print(f"    {'corner':22s}" + "".join(f"{lbl:>13s}" for lbl, _ in SLACK_PREFIXES))
        for c in corners:
            row = f"    {c:22s}"
            for _, pre in SLACK_PREFIXES:
                v = m.get(pre + c)
                s = "-" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v))
                row += f"{s:>13s}"
            print(row)
    print()
    return m


def main():
    args = sys.argv[1:]
    as_json = False
    if args and args[0] == "--json":
        as_json, args = True, args[1:]
    if not args:
        print(__doc__)
        return 1
    if as_json:
        print(json.dumps({d: load(d)[0] for d in args}, indent=2))
        return 0
    for d in args:
        report(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
