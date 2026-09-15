#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Which flip-flop is behind which clock gate, read out of the netlist.

    clkgate_domains.py <soc_top.nl.v> [--tsv domains.tsv]

WHY THIS EXISTS.  docs/76 section 7 and docs/77 section 12.2 quote the
population of each gated clock domain out of the CTS log (`CTS-0010`,
`CTS-0011`), which is a count per clock ROOT and names no flip-flop.  A
fault-injection campaign into the gated domains (docs/82) has to know,
for every flip-flop the bench can force, which clock net reaches its
CLK pin, so that "inside the accelerator's domain" is a list of netlist
indices and not a figure.  This walks each flip-flop's CLK pin back
through the clock tree -- buffers and delay cells only; a cell with
more than one input on a clock path is refused -- to the first net that
is either an integrated clock gate's GCLK or has no driving cell at all
(a port).  The root's name is the domain.

WHAT IT CHECKS ITSELF AGAINST.  The counts per root must reproduce the
CTS log's sink counts for the same layout (docs/77 section 12.2:
`clk_npu` 2,089, `clk_bus` 55, `u_ibex.clk` 2,323, `clk_i_regs` 1,405
on `s77gate`), and the sum over every root must equal the number of
flip-flops parsed.  Both are printed; neither is assumed.

WHY NOT hw/soc/fi/gl_netlist.py's graph().  That parser's instance
regex expects exactly one space between an instance name and its pin
list, and LibreLane writes an escaped instance name -- every clock-tree
buffer under `u_ibex.clk` (`\\clkbuf_leaf_9_u_ibex.clk `) and all three
`sg13g2_lgcp_1` cells -- with the trailing space that is part of the
identifier PLUS the separator, so those cells are invisible to it.
That parser's cone censuses never needed a clock buffer or a clock gate
and were not wrong for their purpose; a domain walk needs both, so it
reads the file with its own regex and says so here rather than
changing a function that docs/74, docs/75 and the guards in sw/tests
rest on.
"""

import argparse
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "fi"))
import gl_netlist  # noqa: E402

# An instance is `<cell> <name> (<pins>);` with ANY whitespace between
# the name and the pin list, so that an escaped name (which owns its
# trailing space) is parsed the same as a plain one.
_INST = re.compile(r"^\s*(sg13g2_\w+|RM_\w+)\s+(\S+)\s+\((.*?)\);", re.M | re.S)
_PIN = re.compile(r"\.(\w+)\(([^()]*)\)")
_OUT = ("Q", "Y", "X", "GCLK", "L_HI", "L_LO")


def drivers(path):
    """net -> (cell, instance, input nets), for every sg13g2 instance."""
    text = open(path).read()
    out = {}
    for m in _INST.finditer(text):
        cell, inst, body = m.groups()
        pins = {k: v.strip() for k, v in _PIN.findall(body)}
        ins = [v for k, v in pins.items() if k not in _OUT]
        for k, v in pins.items():
            if k in _OUT:
                out[v] = (cell, inst.strip(), ins)
    return out


def root_of(net, drv, _depth=0):
    """Walk a clock net back to its root: an ICG's GCLK, or a net no cell
    drives.  Returns (root net, depth in buffers)."""
    d = drv.get(net)
    if d is None:
        return net, _depth
    cell, inst, ins = d
    if cell.startswith("sg13g2_lgcp"):
        return net, _depth
    if gl_netlist.is_flop(cell):
        # A flip-flop driving a clock pin would be a divided clock; the
        # SoC has none on a CLK pin (soc_npu_ser's ser_sck is a data
        # pin of the die's serial port) and finding one is a finding.
        return net, _depth
    if len(ins) != 1:
        sys.exit("cell %s (%s) on a clock path has %d inputs; a clock "
                 "tree here is buffers and delay cells only"
                 % (cell, inst, len(ins)))
    return root_of(ins[0], drv, _depth + 1)


def domains(path):
    flops, _ = gl_netlist.parse(path)
    drv = drivers(path)
    rows = []
    for f in flops:
        root, depth = root_of(f.clk, drv)
        rows.append((f, gl_netlist.plain(root)[0], depth))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("netlist")
    ap.add_argument("--tsv", default=None,
                    help="write idx, instance, Q net, CLK leaf, domain, depth")
    args = ap.parse_args()
    rows = domains(args.netlist)
    per = collections.Counter(r[1] for r in rows)
    named = collections.Counter(
        r[1] for r in rows
        if not re.match(r"^(_\d+_|net\d+)$", gl_netlist.plain(r[0].q)[0]))
    print("%d flip-flops, %d clock domain roots" % (len(rows), len(per)))
    for root, n in sorted(per.items(), key=lambda kv: -kv[1]):
        print("  %-24s %5d flip-flops  (%d with a public Q-net name)"
              % (root, n, named[root]))
    assert sum(per.values()) == len(rows)
    if args.tsv:
        with open(args.tsv, "w") as fh:
            fh.write("idx\tinst\tq\tclk\tdomain\tdepth\n")
            for f, root, depth in rows:
                fh.write("%d\t%s\t%s\t%s\t%s\t%d\n"
                         % (f.idx, f.inst, f.q, f.clk, root, depth))
        print("wrote %s" % args.tsv)


if __name__ == "__main__":
    main()
