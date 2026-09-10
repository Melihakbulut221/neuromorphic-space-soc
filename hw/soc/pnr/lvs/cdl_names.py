#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Normalise an RM_IHPSG13 CDL's node names to the spelling Magic emits.

WHY THIS EXISTS. Netgen compares the Magic-extracted layout netlist
(circuit 1) against the powered Verilog netlist plus the vendor CDLs
(circuit 2). For the RM_IHPSG13 macros the two views spell the same pin
two different ways, and BOTH differences have to go before the
comparison converges:

    circuit 1 (Magic, from the macro LEF)   A_DIN[63]   VDD    VSS    VDDARRAY
    circuit 2 (vendor CDL)                  A_DIN<63>   VDD!   VSS!   VDDARRAY!

Netgen 1.5.272 has no directive that equates either difference.
`::netgen::help` lists exactly two pin-correspondence directives:
`equate pins`, which matches two pin lists BY POSITION, and
`equate classes ... <pins>`, which needs the correspondence written out
by hand. Position is useless here -- the CDL declares the 2048x64's 355
pins in a different order from the LEF and exactly 1 of the 355
positions agrees -- so `equate pins`, which is what the PDK's own netgen
setup calls under -blackbox, would assert 354 wrong correspondences and
return a clean LVS that had checked nothing.

So the spelling is normalised in the netlist instead. Two rewrites, each
a pure relabeling:

  --brackets   '<' -> '[' and '>' -> ']' everywhere. The vendor CDLs
               contain no '[' or ']' of their own (asserted below), so
               the map is injective and no two names can collide.
               Measured worth: net difference 1746 -> 18.

  --no-bang    'VDD!' -> 'VDD', 'VSS!' -> 'VSS', 'VDDARRAY!' ->
               'VDDARRAY'. The '!' is netgen's global-net marker and
               Magic's ext2spice does not emit it, so the CDL's three
               supply pins are promoted to globals and appear as three
               extra nets per macro instance -- 6 instances x 3 = the 18
               above. Checked before doing it: every use of a '!' name
               in both CDLs is inside a subcircuit that declares that
               name as a port (0 implicit global references), and no
               scope contains both 'X' and 'X!', so dropping the marker
               changes no connectivity and merges no two nodes.

Neither rewrite touches hierarchy, device count, device parameters or
connectivity. The check to run if this is ever doubted:
`diff <(tr '<>' '[]' < orig | sed 's/VDD!/VDD/g;s/VSS!/VSS/g;s/VDDARRAY!/VDDARRAY/g') rewritten`
is empty by construction.

    usage: cdl_names.py [--brackets] [--no-bang] <in.cdl> <out.cdl>
"""
import sys

args = [a for a in sys.argv[1:] if a.startswith("--")]
pos = [a for a in sys.argv[1:] if not a.startswith("--")]
src, dst = pos
text = open(src, errors="surrogateescape").read()

if "--brackets" in args:
    assert "[" not in text and "]" not in text, (
        f"{src} already contains square brackets; the rewrite would not be "
        "injective and this script must not be used on it")
    text = text.replace("<", "[").replace(">", "]")

if "--no-bang" in args:
    for n in ("VDDARRAY", "VDD", "VSS"):
        text = text.replace(n + "!", n)
    assert "!" not in text, f"{src}: a '!' name other than the three supplies survives"

open(dst, "w", errors="surrogateescape").write(text)
print(f"{src} -> {dst}  ({' '.join(args)})")
