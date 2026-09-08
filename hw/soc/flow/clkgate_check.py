#!/usr/bin/env python3
"""Does a clock gate change anything? Two whole-SoC dumps, cycle by cycle.

    clkgate_check.py equiv  <base.vcd> <gated.vcd> --clock <path>
                            --scope <path> [--scope ...] [--exclude <path>]
    clkgate_check.py duty   <gated.vcd> --clock <path>
                            --enable <path> [--enable ...]

WHY THIS EXISTS, and what it is a substitute for.

`hw/soc/formal/soc_bus_props.v` F10 proves that the fabric's clock-gate
enable is COMPLETE: in every cycle where it is low, no register in
`soc_bus` changes value.  That is a theorem, it is proved by k-induction,
and every one of its five terms is load-bearing under mutation.  It is
what licenses `soc_top.v` to replace the fabric's clock with a gated one
without restating F1 to F9.

NO SUCH PROOF IS AVAILABLE FOR THE ACCELERATOR.  `soc_npu.v`'s enable has
to cover 2,152 flip-flops inside `hw/rtl/pilot_top.v`, which
`docs/34-pilot-freeze.md` pins by blob hash for the TTIHP26b shuttle:
the die's internals cannot be modified, its property set is `formal/` and
is not this work's to extend, and the only thing reachable from outside
it is its clock.  So the statement that the gate changes nothing is made
by MEASUREMENT instead, and this is the instrument:

    the same program, on the same design, built twice -- once with
    CLKGATE = 0 and once with CLKGATE = 1 -- and every signal under the
    gated scope compared at every clock edge of the whole run.

A difference of one bit in one cycle is a failure.  Zero differences over
N cycles is not a proof and this script does not call it one: it is the
statement that the enable is complete ON THE WORKLOADS MEASURED, which is
what `soc_npu.v`'s `wake_hold` counter exists to put margin around.

WHAT IS COMPARED.  Every VCD identifier whose path lies at or under a
`--scope`, by PATH and not by identifier -- the two dumps assign
identifiers independently and a gated build has signals an ungated one
does not.  A path present in only one dump is reported and not compared;
the count of such paths is part of the result, because a comparison that
silently skipped the interesting half would report success.

WHEN IT IS COMPARED.  At every rising edge of `--clock`, AFTER the whole
timestamp has been applied.  A VCD orders the changes inside a timestamp
by identifier rather than by cause, so a per-line comparison would be a
comparison of dump-identifier sort order; buffering the timestamp removes
the question.  This is the same rule `hw/soc/flow/vcd_activity.py` states
for the same reason.

The `duty` mode reports, per enable signal, the fraction of cycles it was
LOW -- which is the fraction of clock edges the gate removed, and is the
number the power measurement is a consequence of.
"""

import argparse
import hashlib
import sys
from collections import defaultdict


def parse_header(fh):
    """id -> [(path, width)], leaving fh at the first value change."""
    ids = defaultdict(list)
    scope = []
    while True:
        line = fh.readline()
        if not line:
            break
        s = line.strip()
        if s.startswith("$scope"):
            p = s.split()
            if len(p) >= 3:
                scope.append(p[2])
        elif s.startswith("$upscope"):
            if scope:
                scope.pop()
        elif s.startswith("$var"):
            p = s.split()
            if p[1] in ("parameter", "integer", "real", "time", "realtime"):
                continue
            ids[p[3]].append((".".join(scope + [p[4]]), int(p[2])))
        elif s.startswith("$enddefinitions"):
            break
    return ids


def under(path, scopes, excludes):
    for e in excludes:
        if path == e or path.startswith(e + "."):
            return False
    for s in scopes:
        if path == s or path.startswith(s + "."):
            return True
    return False


class Walker:
    """Streams a VCD and yields (cycle, {path: value}) at each rising edge.

    Only the selected paths are tracked.  Values are kept as the VCD's own
    strings, so no width normalisation is needed for a comparison between
    two dumps of the same design -- but the SHORTEST path wins when one
    identifier aliases several, exactly as vcd_activity.py does it, so a
    port and the net behind it are one signal and not two.
    """

    def __init__(self, path, clock, scopes, excludes):
        self.fh = open(path, "r", buffering=1 << 22)
        ids = parse_header(self.fh)
        self.clk_id = None
        self.track = {}          # ident -> canonical path
        self.paths = set()
        for ident, entries in ids.items():
            # AN EXCLUSION APPLIES TO THE NET, NOT TO ONE OF ITS NAMES.
            # A VCD identifier usually carries several aliases -- a
            # top-level wire, the port it drives, the net inside the
            # instance -- and the first version of this loop tested
            # `under()` per alias and then took the shortest survivor.
            # Excluding `tb_soc.dut.clk_bus` therefore did not exclude
            # that net: it pushed the comparison onto the next-shortest
            # alias, `tb_soc.dut.u_bus.clk_i`, and reported the same
            # 25,029 differing cycles under a different name. Measured
            # while docs/76 was written, on a run whose only purpose was
            # to show a zero. The exclusion is now decided over ALL of
            # an identifier's aliases before any of them is chosen.
            if any(any(p == e or p.startswith(e + ".") for e in excludes)
                   for p, _w in entries):
                for p, _w in entries:
                    if p == clock:
                        self.clk_id = ident
                continue
            best = None
            for p, _w in entries:
                if p == clock:
                    self.clk_id = ident
                if under(p, scopes, []) and (best is None or len(p) < len(best)):
                    best = p
            if best is not None:
                self.track[ident] = best
                self.paths.add(best)
        if self.clk_id is None:
            sys.exit(f"{path}: clock {clock} is not in the dump")
        self.value = {p: "x" for p in self.paths}
        self.cycle = -1
        self.clk = "x"

    def edges(self):
        pending = []
        clk_id, track, value = self.clk_id, self.track, self.value
        for line in self.fh:
            c = line[0]
            if c == "#":
                if pending:
                    rising = False
                    for ident, new in pending:
                        if ident == clk_id:
                            rising = self.clk == "0" and new == "1"
                            self.clk = new
                        p = track.get(ident)
                        if p is not None:
                            value[p] = new
                    pending = []
                    if rising:
                        self.cycle += 1
                        yield self.cycle
                continue
            if c in "01xzXZ":
                pending.append((line[1:].strip(), c))
            elif c in "bB":
                v, _, ident = line[1:].strip().partition(" ")
                pending.append((ident.strip(), v))
            elif c in "rR":
                v, _, ident = line[1:].strip().partition(" ")
                pending.append((ident.strip(), v))
            # $dumpvars / $end and friends: no leading value character
        if pending:
            for ident, new in pending:
                if ident == clk_id:
                    if self.clk == "0" and new == "1":
                        self.cycle += 1
                        self.clk = new
                        yield self.cycle
                        return
                    self.clk = new
                p = track.get(ident)
                if p is not None:
                    value[p] = new


def norm(v):
    """VCD leaves off leading zeros and left-extends; make two dumps of the
    same design comparable without knowing the width."""
    v = v.strip()
    if v and v[0] in "01":
        return v.lstrip("0") or "0"
    return v


def cmd_equiv(args):
    a = Walker(args.base, args.clock, args.scope, args.exclude)
    b = Walker(args.gated, args.clock, args.scope, args.exclude)
    only_a = sorted(a.paths - b.paths)
    only_b = sorted(b.paths - a.paths)
    common = sorted(a.paths & b.paths)
    print(f"paths under {args.scope}: {len(a.paths)} in the baseline, "
          f"{len(b.paths)} in the gated build, {len(common)} compared")
    for p in only_a:
        print(f"  baseline only: {p}")
    for p in only_b:
        print(f"  gated only:    {p}")

    ea, eb = a.edges(), b.edges()
    va, vb = a.value, b.value
    cycles = 0
    bad = 0
    first = None
    diffpaths = defaultdict(int)
    while True:
        ca = next(ea, None)
        cb = next(eb, None)
        if ca is None or cb is None:
            break
        cycles += 1
        # A digest first: the whole point is that this is normally equal,
        # and hashing is far cheaper than comparing several hundred
        # strings per cycle over four hundred thousand cycles.
        ha = hashlib.blake2b(
            b"\0".join(norm(va[p]).encode() for p in common), digest_size=8).digest()
        hb = hashlib.blake2b(
            b"\0".join(norm(vb[p]).encode() for p in common), digest_size=8).digest()
        if ha != hb:
            bad += 1
            for p in common:
                if norm(va[p]) != norm(vb[p]):
                    diffpaths[p] += 1
                    if first is None:
                        first = (ca, p, va[p], vb[p])
    print(f"cycles compared: {cycles}")
    print(f"cycles differing: {bad}")
    if first:
        c, p, x, y = first
        print(f"first difference: cycle {c} {p}: baseline {x!r} gated {y!r}")
        for p, n in sorted(diffpaths.items(), key=lambda kv: -kv[1])[:20]:
            print(f"  {n:>9} cycles  {p}")
    if len(a.paths) != len(b.paths) - len(only_b):
        pass
    return 1 if bad else 0


def cmd_duty(args):
    # The window signal, if any, is tracked alongside the enables so that
    # the same walk answers "how often is the gate shut" and "how often is
    # it shut WHILE THE CORE IS ASLEEP" -- which are different numbers and
    # the second is the one a duty-cycled mission is about.
    gate_path, gate_val = (None, None)
    if args.window:
        gate_path, gate_val = args.window.split("=")
    scopes = list(args.enable) + ([gate_path] if gate_path else [])
    w = Walker(args.vcd, args.clock, scopes, [])
    for p in scopes:
        if p not in w.paths:
            sys.exit(f"{args.vcd}: {p} is not in the dump")
    want = list(args.enable)
    low = {p: 0 for p in want}
    lowin = {p: 0 for p in want}
    # docs/77 section 11: the number of SLEEP INTERVALS, not just the
    # number of slept cycles. It is what prices the repair this document
    # does not take -- a slave that refuses its grant while asleep costs
    # one cycle per interval and nothing per slept cycle -- and docs/76
    # section 7 quoted an interval count for the supervisor that nothing
    # in this file could produce. A "wake" is a low-to-high edge of the
    # enable sampled at a clock edge, and the first cycle counts as one
    # if the run starts with the gate shut.
    wakes = {p: 0 for p in want}
    prev = {p: None for p in want}
    n = 0
    nin = 0
    for _c in w.edges():
        n += 1
        inwin = gate_path is None or norm(w.value[gate_path]) == gate_val
        if inwin:
            nin += 1
        for p in want:
            v = norm(w.value[p])
            if v == "0":
                low[p] += 1
                if inwin:
                    lowin[p] += 1
            if prev[p] == "0" and v != "0":
                wakes[p] += 1
            prev[p] = v
    print(f"cycles: {n}")
    for p in want:
        print(f"  {p}: low on {low[p]} of {n} cycles "
              f"({100.0 * low[p] / n:.4f} %), so the gate removes that "
              f"fraction of its domain's clock edges")
        mean = (low[p] / wakes[p]) if wakes[p] else float("nan")
        print(f"      {wakes[p]} sleep intervals, mean {mean:.1f} cycles "
              f"-- one cycle each is what a wakefulness-qualified grant "
              f"would cost (docs/77 section 11)")
    if gate_path:
        print(f"window {gate_path}={gate_val}: {nin} cycles "
              f"({100.0 * nin / n:.4f} % of the run)")
        for p in want:
            pc = 100.0 * lowin[p] / nin if nin else 0.0
            print(f"  {p}: low on {lowin[p]} of those {nin} "
                  f"({pc:.4f} %)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("equiv")
    e.add_argument("base")
    e.add_argument("gated")
    e.add_argument("--clock", required=True)
    e.add_argument("--scope", action="append", required=True)
    e.add_argument("--exclude", action="append", default=[])
    e.set_defaults(fn=cmd_equiv)

    d = sub.add_parser("duty")
    d.add_argument("vcd")
    d.add_argument("--clock", required=True)
    d.add_argument("--enable", action="append", required=True)
    d.add_argument("--window", help="restrict a second count to the cycles in "
                                    "which a one-bit signal holds a value, "
                                    "e.g. tb.dut.core_sleep_o=1")
    d.set_defaults(fn=cmd_duty)

    args = ap.parse_args()
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
