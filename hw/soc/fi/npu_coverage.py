#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Attribute every elaborated flip-flop of the NPU connection to a
campaign site, or report it as uncovered.

    npu_coverage.py <connection.il> [<die.il>]

Reads the RTLIL `hw/soc/flow/fi_npu_coverage.sh` dumps and matches each
flip-flop's Q signal against `npu_targets.py`'s site paths.

IT ASKS THE QUESTION THE CAMPAIGN'S OWN CONTROLS CANNOT.  `npu_campaign.py`
control 1 verifies that every site the list NAMES elaborates.  That is the
opposite question from whether every flip-flop that elaborates is NAMED,
and only the second one is about coverage.  docs/42 section 4.2 records
what asking it found on the core: three whole structures missing, 128
flip-flops of debug CSRs among them, none of which the campaign's own
controls could have caught.

The second file, if given, is the same census of the FROZEN die.  Its
number is reported and is deliberately NOT a coverage figure: `die_ser`
is one stratum over `hw/rtl/pilot_top.v`'s serial front end and nothing
else, because docs/16 already measured the whole block with its own
target list and re-measuring it at lower resolution here would be worse
than not measuring it.  Printing the ratio is what stops "the die is in
the campaign" being read as "the die is covered by the campaign".
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import npu_targets as targets                          # noqa: E402


CELL = re.compile(r"^  cell \$(a?dffe?|sdffe?|dffsr) \S+\n(.*?)^  end$",
                  re.M | re.S)


def parse(path):
    """Every (signal, bits) the elaborated design stores in flip-flops.

    Each RTLIL flip-flop cell carries its own `WIDTH` parameter and one
    `connect \\Q`, so the width comes from the cell rather than from a
    wire declaration the dump does not contain.  Yosys writes flattened
    names with the hierarchy in them -- `\\u_inj.u_wptr_a.bits` -- which
    is exactly the string form npu_targets.py uses, so the two are
    directly comparable.  hw/soc/fi/coverage.py does the same for the
    core and this is its sibling.
    """
    text = open(path).read()
    out = {}
    for m in CELL.finditer(text):
        body = m.group(2)
        wm = re.search(r"parameter \\WIDTH (\d+)", body)
        qm = re.search(r"connect \\Q (.+)", body)
        if not wm or not qm:
            continue
        width = int(wm.group(1))
        # The Q right-hand side is `\name`, `\name [hi:lo]`, `\name [bit]`
        # or a braced concatenation.  The backslash-prefixed tokens are
        # the signals, and an ARRAY INDEX IS PART OF THE NAME: after
        # `memory_map` the queue's storage is eight signals called
        # `u_inj.mem[0]` .. `[7]`, which is exactly what the site list
        # calls them.  An earlier version of this regex stripped the
        # index, folded all eight into one 128-bit `u_inj.mem`, and then
        # reported every one of the sixteen queue-storage sites as
        # "removed by synthesis" while reporting 256 bits as uncovered.
        # Both halves of that were wrong and they cancelled into a
        # coverage figure of 64.9 % that looked like a real hole.
        names = re.findall(r"\\(\S+)", qm.group(1))
        if not names:
            continue
        share = width // len(names)
        rest = width - share * len(names)
        for k, n in enumerate(names):
            out[n] = out.get(n, 0) + share + (rest if k == 0 else 0)
    return out


def main():
    il = sys.argv[1]
    flops = parse(il)

    open_sites = {s.path: s for s in targets.SITES
                  if s.stratum not in targets.FROZEN}

    covered = {}
    uncovered = {}
    for name, bits in sorted(flops.items()):
        site = open_sites.get(name)
        if site is not None:
            covered[name] = (site, bits)
        else:
            uncovered[name] = bits

    tot_bits = sum(b for _, b in covered.values()) + sum(uncovered.values())
    cov_bits = sum(b for _, b in covered.values())

    print("THE CONNECTION -- hw/soc/rtl/soc_npu.v with the frozen pilot")
    print("black-boxed, which is the same scope docs/51 section 11 measured")
    print("")
    print("flip-flop signals elaborated : %d" % len(flops))
    print("  named by a campaign site   : %d" % len(covered))
    print("  not named                  : %d" % len(uncovered))
    print("")
    print("flip-flop BITS elaborated    : %d" % tot_bits)
    print("  covered by the campaign    : %d  (%.1f %%)"
          % (cov_bits, 100.0 * cov_bits / tot_bits if tot_bits else 0.0))
    print("  not covered                : %d" % (tot_bits - cov_bits))
    print("")
    print("the site list declares       : %d bits over %d sites"
          % (targets.connection_bits(), len(open_sites)))
    print("")

    missing = set(open_sites) - set(covered)
    if missing:
        # Sites the Icarus testbench DOES elaborate and inject into --
        # npu_campaign.py control 1 fails if one does not -- but which
        # Yosys's opt_clean removes because nothing reads them.  They are
        # flip-flops in the RTL and not in the netlist, which is one
        # concrete way an RTL campaign and a gate-level campaign would
        # differ on this block.  docs/42 section 4.2 names three on the
        # core and section 4.4 says which way the bias runs: it can only
        # INFLATE the masked fraction.
        print("SITES THE CAMPAIGN INJECTS INTO THAT SYNTHESIS REMOVES:")
        for m in sorted(missing):
            s = open_sites[m]
            print("  %5d  %s  (%s)" % (s.width, m, s.stratum))
        print("")
    if uncovered:
        print("FLIP-FLOPS THE CAMPAIGN DOES NOT INJECT INTO:")
        for name, bits in sorted(uncovered.items(), key=lambda kv: -kv[1]):
            print("  %5d  %s" % (bits, name))
        print("")

    # Partial widths: a site the census finds but at a different width.
    for name, (site, bits) in sorted(covered.items()):
        if bits != site.width:
            print("WIDTH DIFFERENCE: %s is %d bits in the site list and %d "
                  "after opt_clean" % (name, site.width, bits))

    if len(sys.argv) > 2:
        die = parse(sys.argv[2])
        die_bits = sum(die.values())
        named = {s.path.split(".", 1)[1]: s
                 for s in targets.stratum_sites("die_ser")}
        hit = sum(b for n, b in die.items() if n in named)
        print("")
        print("THE FROZEN DIE -- hw/rtl/pilot_top.v at soc_npu.v's "
              "parameters")
        print("")
        print("flip-flop BITS elaborated    : %d" % die_bits)
        print("  named by the die_ser stratum : %d  (%.1f %%)"
              % (hit, 100.0 * hit / die_bits if die_bits else 0.0))
        print("")
        print("THAT IS NOT A COVERAGE FIGURE AND MUST NOT BE READ AS ONE.")
        print("`die_ser` is one stratum over the die's serial front end,")
        print("chosen so that the same 40-bit frame can be measured on both")
        print("sides of one pin boundary. docs/16 measured the whole block,")
        print("with its own target list and 255 injections, and docs/32")
        print("confirmed the result against the netlist. Nothing here")
        print("supersedes either.")


if __name__ == "__main__":
    main()
