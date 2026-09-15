#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""docs/73 section 3.4's third derivation, as a file rather than a paste.

    clint_closure.py <netlist.v> <members.json> <out.json>

docs/73 section 16 needed the CLINT's register-to-register closure on
the eight-macro netlist and section 3.4 had described it in prose and
run it from a scratch paste. This is that derivation, kept beside
clint_region.py whose Netlist it borrows, so that section 16.4's
recipe is reproducible from the repository.
"""
# docs/73 section 3.4's third derivation, reproduced for the eight-macro
# netlist: the register-to-register CLOSURE of the CLINT -- combinational
# cells in the backward cone of a CLINT flip-flop's D and in the forward
# cone of a CLINT flip-flop's Q, stopping at any flip-flop or macro --
# unioned with clint_region.py's exclusive fan-in set.
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clint_region import Netlist, is_seq, is_stdcell, norm
nl = Netlist(sys.argv[1]); excl = set(json.load(open(sys.argv[2]))); out = sys.argv[3]
# CLINT flip-flops: sequential cells with a Q net named under u_clint.
flops = set()
for c, (m, pins) in nl.cells.items():
    if not is_seq(m): continue
    for p, n in pins.items():
        if p in nl.outpins.get(m, set()) and norm(n).startswith("u_clint."):
            flops.add(c); break
print("CLINT flip-flops:", len(flops))
def comb(c):
    m = nl.cells[c][0]
    return is_stdcell(m) and not is_seq(m)
# backward cone from D-side inputs of CLINT flops
back = set(); stack = []
for f in flops:
    m, pins = nl.cells[f]
    for p, n in pins.items():
        if p in nl.outpins.get(m, set()): continue
        d = nl.driver.get(n)
        if d: stack.append(d[0])
while stack:
    c = stack.pop()
    if c in back or not comb(c): continue
    back.add(c)
    m, pins = nl.cells[c]
    for p, n in pins.items():
        if p in nl.outpins.get(m, set()): continue
        d = nl.driver.get(n)
        if d and d[0] not in back: stack.append(d[0])
# forward cone from Q of CLINT flops
fwd = set(); stack = []
for f in flops:
    m, pins = nl.cells[f]
    for p, n in pins.items():
        if p in nl.outpins.get(m, set()):
            for lc, _ in nl.loads.get(n, []): stack.append(lc)
while stack:
    c = stack.pop()
    if c in fwd or not comb(c): continue
    fwd.add(c)
    m, pins = nl.cells[c]
    for p, n in pins.items():
        if p in nl.outpins.get(m, set()):
            for lc, _ in nl.loads.get(n, []):
                if lc not in fwd: stack.append(lc)
closure = back & fwd
union = closure | excl | flops
print("backward cone:", len(back), " forward cone:", len(fwd), " closure:", len(closure), " exclusive:", len(excl), " union:", len(union))
area = sum(nl.area(c) for c in union)
print("union LEF area um2: %.4f" % area)
json.dump(sorted(union), open(out, "w"), indent=0)
print("wrote", out)
