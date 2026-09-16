#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Combinational depth between flip-flops, straight out of a netlist.

    logic_depth.py <netlist.v> [--top N] [--hist]

WHY NOT STA.  `docs/83` measured that wire is 3.6 % of a violating path
and that the median path is 88 stages deep, which points at synthesis
rather than at placement.  The obvious next question --- is that depth a
synthesis CHOICE or a structure? --- cannot be asked of the flow's
pre-place STA: with no placement there are no wire loads, OpenSTA uses
its default fanout estimate, and every path comes back at over a hundred
nanoseconds with four stages.  It cannot be asked cheaply of a full
layout either, at four hours a variant.

DEPTH CAN BE ASKED OF THE NETLIST ALONE.  The number of combinational
cells on the longest path between two sequential elements is fixed by
synthesis, is what abc's delay target actually moves, and does not
depend on where anything is placed.  This computes it: a longest-path
count over the combinational DAG, from every start point (a flip-flop's
Q, an input port, a macro's output) to every end point (a flip-flop's
data or enable pin, an output port, a macro's input).

WHAT A LEVEL IS AND IS NOT.  One level is one standard cell, buffers
included, because a buffer abc inserted to meet a delay target is a
level the signal really passes through.  A level is not a nanosecond:
cells differ by a factor of three in delay and the loads differ by more.
Use this to compare two netlists of the same design, which is what it
is for; use STA on a placed design to compare against a constraint.
"""

import argparse
import collections
import re
import sys

INST = re.compile(r"(?m)^[ \t]*(\S+)\s+(\\?\S+?)\s*\((.*?)\);[ \t]*$", re.S)
PIN = re.compile(r"\.(\w+)\(([^()]*)\)")
NET = re.compile(r"\\\S+|[A-Za-z_][\w$]*")

# sg13g2 output pins. Everything else on a cell is an input.
OUT_PINS = {"X", "Y", "Q", "Q_N", "ZN", "GCLK"}
# A cell is sequential if it has a clock pin; these are the families.
SEQ = re.compile(r"^sg13g2_(dfrbp|dfrbpq|dfbbp|dlhq|dlhrq|sdfbbp|lgcp)")
MACRO = re.compile(r"^RM_IHPSG13")


def parse(path):
    text = open(path, errors="ignore").read()
    cells = {}
    for m in INST.finditer(text):
        kind, name, body = m.group(1), m.group(2).lstrip("\\"), m.group(3)
        if not (kind.startswith("sg13g2_") or MACRO.match(kind)):
            continue
        pins = {}
        for pin, val in PIN.findall(body):
            pins[pin] = [n.lstrip("\\") for n in NET.findall(val)]
        cells[name] = (kind, pins)
    return cells


def build(cells):
    """driver[net] = cell, loads[net] = [cells]."""
    driver, loads = {}, collections.defaultdict(list)
    for name, (kind, pins) in cells.items():
        for pin, nets in pins.items():
            out = pin in OUT_PINS or (MACRO.match(kind) and pin.endswith("DOUT"))
            for n in nets:
                if out:
                    driver[n] = name
                else:
                    loads[n].append(name)
    return driver, loads


def depths(cells, driver):
    """Longest combinational level count reaching each cell's output."""
    memo = {}
    order = []

    def comb(name):
        kind = cells[name][0]
        return not SEQ.match(kind) and not MACRO.match(kind)

    sys.setrecursionlimit(100000)

    def level(name, stack):
        """Levels of combinational logic ending at this cell's output."""
        if name in memo:
            return memo[name]
        if name in stack:                 # combinational loop: stop, count 0
            return 0
        if not comb(name):
            memo[name] = 0                # a flop's Q starts a new path
            return 0
        stack.add(name)
        best = 0
        for pin, nets in cells[name][1].items():
            if pin in OUT_PINS:
                continue
            for n in nets:
                d = driver.get(n)
                if d is not None and d != name:
                    best = max(best, level(d, stack))
        stack.discard(name)
        memo[name] = best + 1
        order.append(name)
        return memo[name]

    for name in cells:
        level(name, set())
    return memo


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("netlist")
    ap.add_argument("--top", type=int, default=10,
                    help="print the N deepest endpoints")
    ap.add_argument("--hist", action="store_true")
    a = ap.parse_args()

    cells = parse(a.netlist)
    if not cells:
        sys.exit("no sg13g2 or macro instances in %s" % a.netlist)
    driver, _ = build(cells)
    memo = depths(cells, driver)

    # Endpoints: the data-side pins of sequential cells and of macros.
    ends = []
    for name, (kind, pins) in cells.items():
        if not (SEQ.match(kind) or MACRO.match(kind)):
            continue
        for pin, nets in pins.items():
            if pin in OUT_PINS or pin in ("CLK", "CLK_N", "RESET_B", "SET_B",
                                          "A_CLK", "B_CLK"):
                continue
            for n in nets:
                d = driver.get(n)
                if d is not None:
                    ends.append((memo.get(d, 0), name, pin, d))
    ends.sort(reverse=True)

    total_comb = sum(1 for n, (k, _) in cells.items()
                     if not SEQ.match(k) and not MACRO.match(k))
    seq = sum(1 for n, (k, _) in cells.items() if SEQ.match(k))
    print("  netlist: %s" % a.netlist)
    print("  cells: %d combinational, %d sequential, %d endpoints"
          % (total_comb, seq, len(ends)))
    if not ends:
        return 0
    lv = [e[0] for e in ends]
    lv.sort()
    print("  LOGIC DEPTH between sequential elements:")
    print("    max %d   p99 %d   p90 %d   median %d   mean %.1f"
          % (lv[-1], lv[int(0.99 * len(lv)) - 1], lv[int(0.90 * len(lv)) - 1],
             lv[len(lv) // 2], sum(lv) / len(lv)))
    print("    endpoints deeper than 40 levels: %d (%.2f %%)"
          % (sum(1 for x in lv if x > 40), 100 * sum(1 for x in lv if x > 40) / len(lv)))
    print("  deepest %d endpoints:" % a.top)
    for d, name, pin, drv in ends[:a.top]:
        print("    %4d  %s/%s  <- %s" % (d, name[:52], pin, drv[:28]))
    if a.hist:
        h = collections.Counter((x // 10) * 10 for x in lv)
        for k in sorted(h):
            print("    %3d-%3d  %6d" % (k, k + 9, h[k]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
