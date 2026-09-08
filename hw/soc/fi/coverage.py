#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Attribute every elaborated flip-flop to a campaign site, or report it
as uncovered.

Reads the RTLIL `hw/soc/flow/fi_coverage.sh` dumps and matches each
flip-flop's Q signal against `targets.py`'s site paths.  It answers the
question the campaign's own controls cannot: not "does every site the
campaign names exist" -- `campaign.py`'s control 1 settles that -- but
"is every flip-flop that exists named by a site".

The two are different failures.  The first is a broken harness and is
loud.  The second is a quiet hole in the coverage of the result, and
`docs/41` section 6.6 lists eight occasions in this repository on which
a green check turned out to be narrower than the conclusion drawn from
it.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import targets                                        # noqa: E402


CELL = re.compile(r"^  cell \$(a?dffe?|sdffe?|dffsr) \S+\n(.*?)^  end$",
                  re.M | re.S)


def parse(path):
    """Every (signal, bits) the elaborated design stores in flip-flops.

    Each RTLIL flip-flop cell carries its own `WIDTH` parameter and one
    `connect \\Q`, so the width comes from the cell rather than from a
    wire declaration the dump does not contain.  Yosys writes flattened
    names with the hierarchy in them -- `\\u_ibex_core.if_stage_i.pc_id_o`
    -- which is exactly the string form `targets.py` uses, so the two are
    directly comparable.
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
        # The Q right-hand side is either `\name`, `\name [hi:lo]`,
        # `\name [bit]` or a braced concatenation.  In every case the
        # backslash-prefixed tokens are the signals, and the cell's
        # WIDTH is the number of bits it stores in them.
        names = re.findall(r"\\(\S+)", qm.group(1))
        if not names:
            continue
        # A concatenation is rare after `proc` and would divide the
        # width across its parts; attributing all of it to the first
        # would overstate that signal, so it is split evenly and the
        # case is reported rather than hidden.
        share = width // len(names)
        rest = width - share * len(names)
        for k, n in enumerate(names):
            out[n] = out.get(n, 0) + share + (rest if k == 0 else 0)
    return out


ANON = re.compile(r"(^|\.)genblk\d+\.")


def norm(path):
    """Drop Yosys's names for UNNAMED generate scopes.

    sv2v wraps some conditional generates in an anonymous block, and the
    two tools disagree about whether it is part of the path: Yosys emits
    `ex_block_i.genblk3.gen_multdiv_fast.multdiv_i.md_state_q` and Icarus
    resolves the same register without the `genblk3`.  They are the same
    flip-flop.  Normalising here rather than in `targets.py` keeps the
    site paths the ones a reader can search the RTL for, and confines the
    tool difference to the one place that has to reconcile two tools.
    """
    prev = None
    while prev != path:
        prev = path
        path = ANON.sub(lambda m: m.group(1), path)
    return path


def main():
    il = sys.argv[1]
    flops = {norm(k): v for k, v in parse(il).items()}

    # A site path is `u_ibex_core.if_stage_i.pc_id_o`; a flattened Yosys
    # name is the same string, because both are rooted at ibex_top.
    by_path = {s.path: s for s in targets.SITES}

    covered = {}
    uncovered = {}
    for name, bits in sorted(flops.items()):
        site = by_path.get(name)
        if site is not None:
            covered[name] = (site, bits)
        else:
            uncovered[name] = bits

    tot_bits = sum(b for _, b in covered.values()) + sum(uncovered.values())
    cov_bits = sum(b for _, b in covered.values())

    print("flip-flop signals elaborated : %d" % len(flops))
    print("  named by a campaign site   : %d" % len(covered))
    print("  not named                  : %d" % len(uncovered))
    print("")
    print("flip-flop BITS elaborated    : %d" % tot_bits)
    print("  covered by the campaign    : %d  (%.1f %%)"
          % (cov_bits, 100.0 * cov_bits / tot_bits if tot_bits else 0.0))
    print("  not covered                : %d" % (tot_bits - cov_bits))
    print("")
    named = set(by_path)
    missing = named - set(covered)
    if missing:
        # These are sites the Icarus testbench DOES elaborate and inject
        # into -- campaign.py's control 1 fails if one does not -- but
        # which Yosys's `opt_clean` removes because nothing in this
        # configuration reads them.  They are flip-flops in the RTL and
        # not in the netlist, which is one concrete way an RTL campaign
        # and a gate-level campaign would differ on this core.
        print("SITES THE CAMPAIGN INJECTS INTO THAT SYNTHESIS REMOVES:")
        for m in sorted(missing):
            print("  %s" % m)
        print("")
    print("FLIP-FLOPS THE CAMPAIGN DOES NOT INJECT INTO:")
    for name, bits in sorted(uncovered.items(), key=lambda kv: -kv[1]):
        print("  %5d  %s" % (bits, name))


if __name__ == "__main__":
    main()
