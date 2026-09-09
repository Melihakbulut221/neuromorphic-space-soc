#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Rewrite an RM_IHPSG13 CDL's bus delimiters from <n> to [n].

WHY THIS EXISTS. Netgen compares the Magic-extracted layout netlist
(circuit 1) against the powered Verilog netlist plus the vendor CDLs
(circuit 2).  For the RM_IHPSG13 macros the two views spell the same pin
two different ways:

    circuit 1 (Magic, from the macro LEF)   A_DIN[63]   VDD
    circuit 2 (vendor CDL)                  A_DIN<63>   VDD!

Netgen 1.5.272 has no directive that equates the two delimiter styles --
`::netgen::help` lists `equate pins` (which matches pin lists BY
POSITION) and `equate classes ... <pins>` (an explicit correspondence),
and nothing else.  Position is useless here: the CDL declares its 355
pins in a different order from the LEF, and exactly 1 of 355 positions
agrees, so `equate pins` would assert 354 wrong correspondences and
report a clean LVS that had checked nothing.

So the delimiters are normalised in the netlist instead.  This rewrite is
a pure relabeling: '<' -> '[' and '>' -> ']' everywhere in the file.  The
vendor CDL contains no '[' or ']' of its own (checked: 0 occurrences in
both files used here), so the map is injective and no two distinct names
can collide.  Connectivity, hierarchy, device count and device
parameters are untouched -- `diff <(tr '<>' '[]' < orig) rewritten` is
empty by construction, which is the check to run if this is ever doubted.

The trailing '!' on VDD!/VSS!/VDDARRAY! is NOT touched: netgen already
treats it as the global-net marker and matches those pins across the two
views without help.

    usage: cdl_delimiters.py <in.cdl> <out.cdl>
"""
import sys

src, dst = sys.argv[1], sys.argv[2]
text = open(src, errors="surrogateescape").read()
assert "[" not in text and "]" not in text, (
    f"{src} already contains square brackets; the rewrite would not be "
    "injective and this script must not be used on it")
open(dst, "w", errors="surrogateescape").write(text.replace("<", "[").replace(">", "]"))
print(f"{src} -> {dst}: {text.count('<')} '<' and {text.count('>')} '>' rewritten")
