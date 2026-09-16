#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""How much of a timing path is wire, and how deep is it?

    path_composition.py <max.rpt> [--top N] [--all]

WHY THIS EXISTS.  `docs/73` section 16 concluded that a placement
requirement it could not satisfy was therefore a FLOORPLAN requirement.
Before building a floorplan to satisfy it, the obvious question is how
much a floorplan could buy, and the report already on disk answers it:
a floorplan moves wire, and on this design wire is **1.9 % of a
violating path at the median** and 3.0 % at the most wire-bound path in
the whole report (`docs/83` section 3).  The same measurement on
`s71boot`, a different macro set and a different pocket, gives 1.9 %
and 2.8 %.  Three floorplans have been measured in this project and
they differ in a quantity that is under five per cent of every path
that violates.

HOW IT DECOMPOSES.  OpenSTA prints one line per pin with an incremental
delay.  A line for an OUTPUT pin (`/X`, `/Y`, `/Q`, `/ZN`) carries the
CELL arc's delay; a line for any other pin carries the delay of the NET
that reached it.  The data path is everything after the launch
flip-flop's `Q`, so the split is:

    stages = output-pin lines between the launch Q and "data arrival time"
    cell   = their delays summed
    net    = every other line's delay in that same window

This counts the clock network into neither, which is what makes the
percentage comparable between layouts with different clock trees.

WHAT IT IS NOT.  It is not a proof that no floorplan helps; it is the
SIZE OF THE PRIZE.  The prize is at most the net delay, and the deficit
is the slack.  When the first is 0.971 ns at the median and the second
is 7.5758 ns on the worst path, the arithmetic is the argument.
"""

import argparse
import re
import statistics
import sys

# An OpenSTA path line: [fanout] [cap] slew delay time dir description
ROW = re.compile(r"\s*(?:\d+\s+)?(?:[\d.]+)?\s*(?:[\d.]+)?\s+"
                 r"([\d.]+)\s+([\d.]+)\s+([v^])\s+(\S+)")
OUTPIN = re.compile(r"/(X|Y|Q|ZN)$")
LAUNCH_Q = re.compile(r"/Q$")
SLACK = re.compile(r"(-?\d+\.\d+)\s+slack")


def paths(report):
    """Yield (slack, stages, net_ns, cell_ns) for every path in a report."""
    with open(report, errors="ignore") as f:
        text = f.read()
    for block in text.split("Startpoint: ")[1:]:
        # CUT AT "data arrival time". Everything after it in an OpenSTA
        # block is the CAPTURE clock's path -- the clock edge at the
        # period, then the clock tree again -- and counting it into the
        # data path is how the first version of this tool inflated every
        # number it produced (docs/83 section 3, corrected 2026-09-16).
        head = block.split("data arrival time", 1)[0]
        rows = []
        for line in head.splitlines():
            m = ROW.match(line)
            if m:
                rows.append((float(m.group(1)), m.group(4)))
        launch = [i for i, (_, n) in enumerate(rows) if LAUNCH_Q.search(n)]
        if not launch:
            continue                      # a path with no launch flop (input)
        data = rows[launch[0]:]
        cell = sum(d for d, n in data if OUTPIN.search(n))
        net = sum(d for d, n in data if not OUTPIN.search(n))
        stages = sum(1 for _, n in data if OUTPIN.search(n))
        m = SLACK.search(block)
        yield (float(m.group(1)) if m else 0.0, stages, net, cell)


def summarise(label, sel):
    if not sel:
        print("  %-16s no paths" % label)
        return
    share = [p[2] / (p[2] + p[3]) for p in sel if (p[2] + p[3]) > 0]
    print("  %-16s n=%5d  stages med %3d (%d..%d)  net med %6.3f ns  "
          "cell med %7.3f ns  WIRE SHARE med %4.1f %% max %4.1f %%"
          % (label, len(sel),
             statistics.median([p[1] for p in sel]),
             min(p[1] for p in sel), max(p[1] for p in sel),
             statistics.median([p[2] for p in sel]),
             statistics.median([p[3] for p in sel]),
             100 * statistics.median(share), 100 * max(share)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("report", help="an OpenSTA max.rpt with full path detail")
    ap.add_argument("--top", type=int, default=100,
                    help="also summarise the N worst violating paths")
    ap.add_argument("--all", action="store_true",
                    help="summarise every path, not only the violating ones")
    a = ap.parse_args()

    rows = list(paths(a.report))
    if not rows:
        sys.exit("no paths with a launch flip-flop in %s -- is this a "
                 "summary report rather than a full one?" % a.report)
    viol = [p for p in rows if p[0] < 0]
    print("  report: %s" % a.report)
    print("  paths: %d, violating: %d" % (len(rows), len(viol)))
    if a.all:
        summarise("all paths", rows)
    summarise("all violating", viol)
    summarise("worst %d" % a.top, sorted(viol)[:a.top])
    if viol:
        w = min(viol)
        print("  worst path: slack %.4f  stages %d  net %.4f ns  "
              "cell %.4f ns  data %.4f ns" % (w[0], w[1], w[2], w[3], w[2] + w[3]))
        print("  even with ideal wire that path is %.4f ns of cell delay."
              % w[3])
    return 0


if __name__ == "__main__":
    sys.exit(main())
