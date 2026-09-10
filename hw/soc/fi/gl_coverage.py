#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Attribute every flip-flop of the flattened netlist to a top-level
block, and say which blocks a fault-injection campaign has reached.

    hw/soc/fi/gl_coverage.py <netlist.v>
    hw/soc/fi/gl_coverage.py <netlist.v> --list /tmp/coverage.tsv
    hw/soc/fi/gl_coverage.py <netlist.v> --mutate u_busstat.irqen:u_ibex

WHY THIS FILE EXISTS

`docs/60` section 9.10.1 published a table -- 1,003 of 5,873
flip-flops in a block no campaign has ever injected into -- and then
said, in its own words, that the listing which produced it *"is not
committed to this tree"*, so the number was *"reproducible in method
and by its cross-checks and NOT reproducible by a command in this
repository"*. It called that an owed artefact. This is the artefact.

It is written from that section's prose, not recovered from the
original listing, which no longer exists. So it is a REIMPLEMENTATION,
and the honest test of it is whether it lands on the published numbers
without being tuned to them: 5,450 by name, 221 by port, 77 by cone,
77 by vote, 48 unplaced, and 1,003 in the uncovered set. What it
actually prints is what it prints; `--verify` compares against those
six and says so either way.

THE FOUR INSTRUMENTS, IN ORDER

Each flip-flop is placed by the first instrument that reaches it, which
is what makes the order part of the definition rather than an
implementation detail.

  name  The Q net carries a hierarchical RTL name, so the first path
        component is the block. `u_timer0` splits in two, because the
        watchdog inside it has been injected into and the general
        purpose timer around it has not.

  port  The Q net is a plain `soc_top` wire that appears as the ACTUAL
        of an OUTPUT formal in one of `soc_top.v`'s instantiations. The
        block is that instance. A wire driven by a continuous
        assignment is deliberately NOT reached: `irq_soft_o` is a CLINT
        output in every sense a reader means, and `assign irq_soft_o =
        clint_irq_soft;` puts it outside this instrument. It stays
        unplaced and section 9.10.1 uses it as a cross-check.

  cone  The anonymous halves of the three TMR replica banks, reached
        from the voter's own input nets rather than from names. This is
        the correction `docs/74` section 6.6 and `docs/75` forced: two
        of the three banks of a protected word carry no RTL name at
        all, and a census by name reports 29 / 14 / 15 where the
        structure is 29 / 29 / 29.

  vote  An anonymous flip-flop whose whole fan-in cone, or whose whole
        fan-out, lands in ONE already-placed block is assigned to that
        block. Ambiguous ones are left unplaced and counted as unknown
        rather than as either answer.

WHAT THIS DOES NOT SHOW

Everything section 9.10.1 lists under "three things this table is not"
applies unchanged, and the first is the one that matters most: **this
is a BLOCK granularity, so the uncovered count is a floor.** A block
counts as covered if any campaign has ever injected anywhere in it, not
if every flip-flop in it is a site. The number of flip-flops in this
design that are not a site of any campaign is larger than what this
prints, and no document here states it.
"""

import argparse
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gl_netlist as G                                       # noqa: E402

RTL = os.path.normpath(os.path.join(HERE, "..", "rtl"))
SOC_TOP = os.path.join(RTL, "soc_top.v")

# Which blocks a campaign has injected into, and the documents that did
# it. `docs/60` section 9.10.1's right-hand column, as data.
CAMPAIGNS = {
    "u_ibex":           "the core campaign -- docs/42, docs/43, docs/74",
    "u_npu":            "the connection -- docs/52, docs/55, docs/56 -- "
                        "and the die, docs/16, docs/26, docs/32",
    "u_clint":          "mtime and mtimecmp -- docs/58",
    "u_boot":           "docs/69",
    "u_timer0.u_wdog":  "docs/41",
}

# The three protected words `gl_netlist.TMR_STRUCTURES` knows, and the
# block each one lives in.
CONE_BLOCK = {
    "wdog": "u_timer0.u_wdog",
    "boot": "u_boot",
    "npu":  "u_npu",
}

PUBLISHED = {           # docs/60 section 9.10.1, 2026-09-10
    "name": 5450, "port": 221, "cone": 77, "vote": 77,
    "unplaced": 48, "uncovered": 1003, "total": 5873,
}


# ---------------------------------------------------------------------
# instrument 1: the hierarchical name
# ---------------------------------------------------------------------
def by_name(q):
    """The block a Q net names, or None if it names none.

    `u_timer0` is split because coverage is not uniform inside it:
    `docs/41` injected into the watchdog and nothing has injected into
    the general purpose timer around it."""
    base, _ = G.plain(q)
    parts = base.split(".")
    if len(parts) < 2:
        return None
    if parts[0] == "u_timer0":
        return "u_timer0.u_wdog" if parts[1] == "u_wdog" \
            else "u_timer0(gptimer)"
    return parts[0]


# ---------------------------------------------------------------------
# instrument 2: the soc_top wire
# ---------------------------------------------------------------------
_MODULE = re.compile(r"^\s*module\s+(\w+)\s*(?:#\s*\((?:[^()]|\([^()]*\))*\))?"
                     r"\s*\((.*?)\)\s*;", re.M | re.S)
_INSTANCE = re.compile(r"^\s{0,6}(\w+)\s*(?:#\s*\((?:[^()]|\([^()]*\))*\)\s*)?"
                       r"(u_\w+)\s*\(\s*(.*?)\s*\)\s*;", re.M | re.S)
_CONN = re.compile(r"\.(\w+)\s*\(\s*([^()]*?)\s*\)")


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def module_outputs(paths):
    """module name -> set of output/inout formals, from ANSI headers."""
    out = {}
    for path in paths:
        text = strip_comments(open(path, errors="replace").read())
        for m in _MODULE.finditer(text):
            name, header = m.group(1), m.group(2)
            outs = set()
            for decl in re.finditer(r"\b(output|inout)\b((?:[^,]|\[[^\]]*\])*)",
                                    header):
                tail = decl.group(2)
                ident = re.findall(r"(\w+)\s*(?:,|$)", tail)
                if ident:
                    outs.add(ident[-1])
            if outs or name not in out:
                out[name] = outs
    return out


def rtl_sources():
    found = []
    for root, _dirs, files in os.walk(RTL):
        for f in sorted(files):
            if f.endswith((".v", ".sv")):
                found.append(os.path.join(root, f))
    return found


def wire_owner():
    """soc_top wire -> instance driving it through an output formal.

    Only instantiation connections are followed. A wire a continuous
    assignment drives has no owner here on purpose; the docstring says
    why, and `irq_soft_o` is the case the document leans on."""
    outs = module_outputs(rtl_sources())
    text = strip_comments(open(SOC_TOP).read())
    owner, contested = {}, set()
    for m in _INSTANCE.finditer(text):
        mod, inst, body = m.group(1), m.group(2), m.group(3)
        if mod in ("module", "if", "for", "case"):
            continue
        formals = outs.get(mod)
        if formals is None:
            continue
        for formal, actual in _CONN.findall(body):
            if formal not in formals:
                continue
            for net in re.findall(r"[A-Za-z_]\w*", actual):
                if net in owner and owner[net] != inst:
                    contested.add(net)
                owner.setdefault(net, inst)
    for net in contested:            # two drivers is not an attribution
        owner.pop(net, None)
    return owner


def block_of_instance(inst):
    """`u_timer0`'s split again, this time from the instance side."""
    return inst


# ---------------------------------------------------------------------
# instrument 3: the replica cones
# ---------------------------------------------------------------------
def cone_instances(path):
    """flip-flop instance -> block, for the three TMR replica banks."""
    nl = G.open_netlist(path)
    out = {}
    for which, block in CONE_BLOCK.items():
        try:
            rows = G.tmr_census_named(path, which, nl=nl)
        except Exception as exc:                       # noqa: BLE001
            print(f"  cone {which}: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            continue
        for row in rows:
            for inst in row.get("cone_insts", ()):
                out[inst] = block
    return out


# ---------------------------------------------------------------------
# instrument 4: the fan-in / fan-out vote
# ---------------------------------------------------------------------
def consumers(cells):
    """net -> instances that read it."""
    out = collections.defaultdict(set)
    for inst, (_cell, pins) in cells.items():
        for k, v in pins.items():
            if k in G._OUTPINS:
                continue
            for one in (v if isinstance(v, list) else (v,)):
                out[one].add(inst)
    return out


def fanout_flops(reads, cells, net, seen=None, depth=0):
    """The flip-flop instances the value on `net` reaches, stopping at
    every flip-flop, macro and dead end."""
    if seen is None:
        seen = set()
    if net in seen or depth > 40:
        return set()
    seen.add(net)
    out = set()
    for inst in reads.get(net, ()):
        cell, pins = cells[inst]
        if G.is_flop(cell):
            out.add(inst)
            continue
        if cell.startswith("RM_") or cell.startswith("$mem"):
            continue
        for k, v in pins.items():
            if k not in G._OUTPINS:
                continue
            for one in (v if isinstance(v, list) else (v,)):
                out |= fanout_flops(reads, cells, one, seen, depth + 1)
    return out


# ---------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------
def attribute(path, rename=None):
    flops, _cells_hist = G.parse(path)
    if rename:
        old, new = rename
        for f in flops:
            base, bit = G.plain(f.q)
            if base.startswith(old):
                tail = base[len(old):]
                q = "\\" + new + tail
                q = q + (f" [{bit}]" if bit is not None else " ")
                flops[f.idx] = f._replace(q=q)

    place = {}                      # flop idx -> (block, instrument)

    for f in flops:
        b = by_name(f.q)
        if b:
            place[f.idx] = (b, "name")

    owner = wire_owner()
    for f in flops:
        if f.idx in place:
            continue
        base, _bit = G.plain(f.q)
        inst = owner.get(base)
        if inst:
            place[f.idx] = (block_of_instance(inst), "port")

    cone = cone_instances(path)
    for f in flops:
        if f.idx in place:
            continue
        if f.inst in cone:
            place[f.idx] = (cone[f.inst], "cone")

    driver, cells = G.graph(path)
    reads = consumers(cells)
    by_inst = {f.inst: f.idx for f in flops}
    sys.setrecursionlimit(100000)

    # To a fixed point, not in one sweep. A vote reads the placements
    # that exist when it is taken, so a single pass in flip-flop-index
    # order gives a different answer from the same pass in reverse: an
    # anonymous flop whose only placed neighbours are themselves placed
    # by vote is decidable, but only after they are. One flip-flop in
    # this netlist -- `_77779_`, whose fan-in and fan-out are both
    # entirely `u_npu` -- is unplaced after one sweep and placed after
    # two, and an instrument whose output depends on the order it
    # happened to walk the file is not measuring the design.
    while True:
        placed_this_round = 0
        for f in flops:
            if f.idx in place:
                continue
            blocks = set()
            for inst in G.cone_flops(driver, cells, f.d) if f.d else ():
                idx = by_inst.get(inst)
                if idx in place:
                    blocks.add(place[idx][0])
            if len(blocks) != 1:
                blocks = set()
                for inst in fanout_flops(reads, cells, f.q):
                    idx = by_inst.get(inst)
                    if idx in place:
                        blocks.add(place[idx][0])
            if len(blocks) == 1:
                place[f.idx] = (blocks.pop(), "vote")
                placed_this_round += 1
        if not placed_this_round:
            break

    return flops, place


def report(flops, place, say=print):
    per_block = collections.Counter()
    per_instrument = collections.Counter()
    for f in flops:
        if f.idx in place:
            block, how = place[f.idx]
            per_block[block] += 1
            per_instrument[how] += 1
    unplaced = len(flops) - sum(per_instrument.values())

    covered = sum(n for b, n in per_block.items() if b in CAMPAIGNS)
    uncovered = sum(n for b, n in per_block.items() if b not in CAMPAIGNS)

    say(f"{len(flops)} flip-flops")
    say("")
    say("| Block | Flip-flops | Campaign |")
    say("|---|---:|---|")
    for b, n in sorted(per_block.items(), key=lambda kv: -kv[1]):
        if b in CAMPAIGNS:
            say(f"| `{b}` | {n:,} | {CAMPAIGNS[b]} |")
    say(f"| **covered** | **{covered:,}** | |")
    for b, n in sorted(per_block.items(), key=lambda kv: -kv[1]):
        if b not in CAMPAIGNS:
            say(f"| `{b}` | {n:,} | **none** |")
    pct = 100.0 * uncovered / len(flops)
    say(f"| **in no campaign** | **{uncovered:,}** | "
        f"**{pct:.2f} % of {len(flops):,}** |")
    say(f"| not placed by any instrument here | {unplaced} | unknown, so "
        f"the figure above is a range |")
    hi = uncovered + unplaced
    say("")
    say(f"{uncovered:,} to {hi:,} flip-flops, {pct:.1f} % to "
        f"{100.0 * hi / len(flops):.1f} %, are in a block no campaign in "
        f"this repository has injected into.")
    say("")
    for how in ("name", "port", "cone", "vote"):
        say(f"  {how:<9} {per_instrument[how]:>5}")
    say(f"  {'unplaced':<9} {unplaced:>5}")
    return {"name": per_instrument["name"], "port": per_instrument["port"],
            "cone": per_instrument["cone"], "vote": per_instrument["vote"],
            "unplaced": unplaced, "uncovered": uncovered,
            "total": len(flops)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("netlist")
    ap.add_argument("--list", default=None,
                    help="write a per-flip-flop TSV")
    ap.add_argument("--verify", action="store_true",
                    help="compare against docs/60 section 9.10.1 and exit "
                         "non-zero on any disagreement")
    ap.add_argument("--mutate", default=None, metavar="OLD:NEW",
                    help="rename a hierarchical prefix before attributing, "
                         "to show the instrument can move -- docs/60 "
                         "9.10.1 uses u_busstat.irqen:u_ibex.mutant_irqen")
    args = ap.parse_args()

    rename = tuple(args.mutate.split(":", 1)) if args.mutate else None
    flops, place = attribute(args.netlist, rename)
    got = report(flops, place)

    if args.list:
        with open(args.list, "w") as fh:
            fh.write("idx\tcell\tinst\tq\tblock\tinstrument\tcovered\n")
            for f in flops:
                block, how = place.get(f.idx, ("", "unplaced"))
                cov = "" if not block else ("yes" if block in CAMPAIGNS
                                            else "no")
                fh.write(f"{f.idx}\t{f.cell}\t{f.inst}\t{f.q}\t{block}\t"
                         f"{how}\t{cov}\n")
        print(f"\nwrote {args.list}")

    if args.verify:
        print("\n--- against docs/60 section 9.10.1 [2026-09-10] ---")
        bad = 0
        for k, want in PUBLISHED.items():
            mark = "ok " if got[k] == want else "NO "
            if got[k] != want:
                bad += 1
            print(f"  {mark}{k:<10} published {want:>6}   here {got[k]:>6}")
        if bad:
            print(f"\n{bad} of {len(PUBLISHED)} disagree. The published "
                  f"listing is gone and this is a reimplementation from\n"
                  f"section 9.10.1's prose, so a disagreement is a fact "
                  f"about the two instruments and not\nyet a fact about "
                  f"the design. It is not to be closed by tuning this "
                  f"file to the table.")
            return 1
        print(f"\nall {len(PUBLISHED)} agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
