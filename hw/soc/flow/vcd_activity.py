#!/usr/bin/env python3
"""Toggle-rate extraction from a whole-SoC VCD, for activity-annotated power.

    vcd_activity.py <vcd> --clock tb_soc.dut.clk_i --scope tb_soc.dut \
                    --window name:first:last [--window ...] \
                    --json out.json

WHAT THIS MEASURES AND WHY IT IS NOT A SAIF.

`docs/47`'s sign-off `report_power` runs with no activity annotation at
all: OpenSTA's default is that every top-level input and every register
output toggles 0.1 times per clock period at a 50 % duty cycle, and
everything combinational is propagated from those.  `docs/53` section
7.1 item 3 labelled the resulting number "an estimate wearing a
measurement's clothes".  This script replaces the 0.1 with a number the
design actually produced.

It cannot produce a SAIF, and the reason is a property of the netlist
rather than a choice made here: `hw/soc/flow/syn_soc_top.sh` runs
`synth -flatten` and `abc`, so of 33,832 nets in
`hw/soc/pnr/runs/full3/final/nl/soc_top.nl.v` only 617 carry a name a
simulation could match, and not one flip-flop instance does.  A VCD
therefore cannot be matched to that netlist pin by pin.  What CAN be
matched is:

  * the three top-level ports, by name;
  * the six SRAM macro instances, by name -- they are the only named
    cells in the netlist, and their control pins are what the macro
    Liberty's `when` conditions switch on;
  * the population statistic that OpenSTA's 0.1 is a stand-in for --
    the mean toggle rate of the design's registers.

So this script reports, per window: the per-port activity and duty, the
per-macro control-pin activity and duty derived from the behavioural
memory's own ports, and the mean activity and duty of every register in
the design, together with the per-block breakdown of the same.

REGISTERS ARE IDENTIFIED BY BEHAVIOUR, NOT BY DECLARATION.  A bit is
counted as a register output if every one of its transitions inside the
window falls on a rising edge of the clock.  A `reg` in an `always @(*)`
block is therefore not counted as one, and a `wire` driven by a
flip-flop through nothing but a rename is.  The alternative -- trusting
the VCD's `$var reg` versus `$var wire` -- is a statement about Verilog
declarations and not about the design.

WHAT IT DOES NOT MEASURE.  Glitches: this is an RTL simulation with no
delays, so a combinational node that would glitch three times in silicon
transitions once here.  Every combinational figure below is therefore a
lower bound, and it is one reason section "what this does not cover" in
the accompanying document refuses to call any of this a silicon
measurement.
"""

import argparse
import json
import re
import sys
from collections import defaultdict


class Sig:
    __slots__ = ("path", "width", "bits", "value", "vtype")

    def __init__(self, path, width, vtype="wire"):
        self.path = path
        self.width = width
        self.vtype = vtype
        self.bits = None      # list of per-bit accumulators, allocated lazily
        self.value = None     # current value string, msb first, length width


class Bit:
    __slots__ = ("tr", "tr_on_edge", "high_time", "last_t", "last_v")

    def __init__(self):
        self.tr = 0            # transitions inside the window
        self.tr_on_edge = 0    # of those, ones landing on a posedge of the clock
        self.high_time = 0     # time units at 1 inside the window
        self.last_t = 0
        self.last_v = "x"


def parse_header(fh):
    """Return (id -> [(path, width)]), timescale_ps.  Leaves fh at the first
    value change."""
    ids = defaultdict(list)
    scope = []
    timescale_ps = 1000
    tok_re = re.compile(r"\S+")
    buf = ""
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
            # $var wire 32 ! addr [31:0] $end
            p = s.split()
            vtype = p[1]
            # `parameter`, `integer`, `real` and `time` are simulation
            # objects and not nets. Counting them would put constants and
            # loop counters into a population that is supposed to be the
            # design's flip-flops.
            if vtype in ("parameter", "integer", "real", "time", "realtime"):
                continue
            width = int(p[2])
            ident = p[3]
            name = p[4]
            ids[ident].append((".".join(scope + [name]), width, vtype))
        elif s.startswith("$timescale"):
            buf = s
            while "$end" not in buf:
                buf += " " + fh.readline().strip()
            m = re.search(r"(\d+)\s*([munpf]?s)", buf)
            if m:
                mult = {"s": 10**12, "ms": 10**9, "us": 10**6,
                        "ns": 1000, "ps": 1, "fs": 0}[m.group(2)]
                timescale_ps = int(m.group(1)) * mult
        elif s.startswith("$enddefinitions"):
            break
    return ids, timescale_ps


def expand(val, width):
    """VCD binary value -> width-long msb-first string, VCD left-extension."""
    if len(val) >= width:
        return val[-width:]
    pad = val[0]
    if pad in "10":
        pad = "0"
    return pad * (width - len(val)) + val


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vcd")
    ap.add_argument("--clock", required=True, help="full VCD path of the clock")
    ap.add_argument("--scope", required=True, help="only signals under this path")
    ap.add_argument("--window", action="append", default=[],
                    metavar="NAME:FIRST:LAST[:GATEPATH=V]",
                    help="cycle window, inclusive of FIRST, exclusive of LAST; "
                         "LAST=-1 means to the end of the dump. An optional "
                         "fourth field restricts the window to the cycles in "
                         "which a one-bit signal holds a value -- "
                         "core_sleep_o=1 is the design's own statement that "
                         "the core is in WFI, which is what makes an idle "
                         "measurement a measurement rather than a choice of "
                         "cycle numbers.")
    ap.add_argument("--derive", action="append", default=[],
                    metavar="NAME=EXPR",
                    help="a virtual one-bit signal, sampled at every rising "
                         "clock edge with the values the design presents AT "
                         "that edge -- which is what a synchronous macro pin "
                         "sees. EXPR is a Python expression over V['<vcd "
                         "path>'], each of which is the integer value of that "
                         "signal, or None if it is x/z. This is how the six "
                         "SRAM macros' A_MEN, A_WEN and A_REN are recovered "
                         "from a simulation that runs the BEHAVIOURAL "
                         "hw/soc/rtl/soc_mem.v: the expressions are copied "
                         "from hw/soc/rtl/soc_mem_sram.v's own port map, so "
                         "the derivation is the design's and not this "
                         "script's.")
    ap.add_argument("--span", action="append", default=[], metavar="SCOPE",
                    help="also report the first and last cycle at which any "
                         "bit under SCOPE transitions")
    ap.add_argument("--json", required=True)
    ap.add_argument("--progress", type=int, default=0)
    args = ap.parse_args()

    windows = []
    for w in args.window:
        parts = w.split(":")
        name, first, last = parts[0], int(parts[1]), int(parts[2])
        gate_path, gate_val = None, None
        if len(parts) > 3 and parts[3]:
            gate_path, gate_val = parts[3].split("=")
        windows.append((name, first, last, gate_path, gate_val))
    if not windows:
        windows = [("all", 0, -1, None, None)]

    derives = []
    for d in args.derive:
        name, expr = d.split("=", 1)
        derives.append((name, compile(expr, f"<derive {name}>", "eval")))

    fh = open(args.vcd, "r", buffering=1 << 22)
    ids, timescale_ps = parse_header(fh)

    # Which identifiers are in scope, and which one is the clock.
    prefix = args.scope + "."
    sel = {}
    clk_id = None
    for ident, entries in ids.items():
        for path, width, vtype in entries:
            if path == args.clock:
                clk_id = ident
            if path == args.scope or path.startswith(prefix):
                # An identifier can alias several paths (a port and the net
                # it connects to).  Keep the SHORTEST path, which is the
                # outermost name, so a signal is counted once.  The TYPE
                # kept is `reg` if any alias declares it one: a flip-flop
                # output seen through a port is still a flip-flop output.
                cur = sel.get(ident)
                if cur is None or len(path) < len(cur.path):
                    t = vtype if cur is None else (
                        "reg" if "reg" in (cur.vtype, vtype) else vtype)
                    sel[ident] = Sig(path, width, t)
                elif vtype == "reg":
                    cur.vtype = "reg"
    if clk_id is None:
        sys.exit(f"clock {args.clock} not in the dump")

    # Gate identifiers, resolved the same way.
    gate_id = {}
    for (_n, _f, _l, gp, _gv) in windows:
        if gp is None:
            continue
        for ident, entries in ids.items():
            for path, width, _vt in entries:
                if path == gp and width == 1:
                    gate_id[gp] = ident
        if gp not in gate_id:
            sys.exit(f"gate {gp} not in the dump as a one-bit signal")
    gate_now = {gp: "x" for gp in gate_id}

    # Span identifiers: which selected signals sit under each --span scope.
    span_of = {}
    for sc in args.span:
        span_of[sc] = [None, None]     # first cycle, last cycle
    span_ids = defaultdict(list)
    for ident, sig in sel.items():
        for sc in args.span:
            if sig.path == sc or sig.path.startswith(sc + "."):
                span_ids[ident].append(sc)

    # Signals a derived expression may read: every selected path, by name.
    path_ident = {sig.path: ident for ident, sig in sel.items()}

    # One accumulator set per window.
    nwin = len(windows)
    for sig in sel.values():
        sig.bits = [[Bit() for _ in range(sig.width)] for _ in range(nwin)]
        sig.value = "x" * sig.width

    cycle = -1          # incremented on each rising edge of the clock
    t = 0
    clk_v = "x"
    win_open = [False] * nwin
    win_first_t = [0] * nwin
    win_last_t = [0] * nwin
    win_cycles = [0] * nwin

    # Derived signals: per window, transitions between consecutive samples
    # and the number of sampled cycles at 1.
    dstate = [None] * len(derives)          # last sampled value, global
    dtr = [[0] * len(derives) for _ in range(nwin)]
    dhigh = [[0] * len(derives) for _ in range(nwin)]
    dprev = [[None] * len(derives) for _ in range(nwin)]

    class VMap(dict):
        def __missing__(self, key):
            ident = path_ident.get(key)
            if ident is None:
                raise KeyError(f"derive: no such signal {key}")
            v = sel[ident].value
            if "x" in v or "z" in v:
                return None
            return int(v, 2)

    def close_bit_time(sig, wi, now):
        for b in sig.bits[wi]:
            if b.last_v == "1":
                b.high_time += now - b.last_t
            b.last_t = now

    # ONE TIMESTAMP IS PROCESSED AS A UNIT, and that is not an
    # optimisation. Whether a transition lands on a rising clock edge is
    # what separates a register output from a combinational node here,
    # and a VCD orders the changes inside a timestamp by identifier, not
    # by cause -- so a per-line test would classify every flip-flop in
    # the design by whether its dump identifier happens to sort before
    # or after the clock's. Buffering the timestamp removes the question.
    pending = []

    def flush(now):
        nonlocal cycle, clk_v
        if not pending:
            return
        rising = False
        for ident, new in pending:
            if ident == clk_id:
                if clk_v == "0" and new == "1":
                    rising = True
                clk_v = new
            gp = ident_gate.get(ident)
            if gp is not None:
                gate_now[gp] = new
        if rising and derives:
            vm = VMap()
            for di, (dn, code) in enumerate(derives):
                try:
                    val = eval(code, {"V": vm})
                except KeyError:
                    val = None
                dstate[di] = None if val is None else (1 if val else 0)
        if rising:
            cycle += 1
            for wi in range(nwin):
                name, first, last, gp, gv = windows[wi]
                inside = cycle >= first and (last < 0 or cycle < last)
                if inside and gp is not None:
                    inside = gate_now[gp] == gv
                if inside and not win_open[wi]:
                    win_open[wi] = True
                    win_first_t[wi] = now
                    for sig in sel.values():
                        v = sig.value
                        for i, b in enumerate(sig.bits[wi]):
                            b.last_t = now
                            b.last_v = v[i]
                elif not inside and win_open[wi]:
                    win_open[wi] = False
                    win_last_t[wi] += now - win_first_t[wi]
                    for sig in sel.values():
                        close_bit_time(sig, wi, now)
                if win_open[wi]:
                    win_cycles[wi] += 1
                    for di in range(len(derives)):
                        v = dstate[di]
                        if v == 1:
                            dhigh[wi][di] += 1
                        pv = dprev[wi][di]
                        if pv is not None and v is not None and pv != v:
                            dtr[wi][di] += 1
                        dprev[wi][di] = v
        for ident, new in pending:
            sig = sel.get(ident)
            if sig is None:
                continue
            old = sig.value
            if old == new:
                continue
            for sc in span_ids.get(ident, ()):
                sp = span_of[sc]
                if sp[0] is None:
                    sp[0] = cycle
                sp[1] = cycle
            for wi in range(nwin):
                if not win_open[wi]:
                    continue
                bits = sig.bits[wi]
                for i in range(sig.width):
                    if old[i] == new[i]:
                        continue
                    b = bits[i]
                    if b.last_v == "1":
                        b.high_time += now - b.last_t
                    b.last_t = now
                    b.last_v = new[i]
                    if old[i] in "01" and new[i] in "01":
                        b.tr += 1
                        if rising:
                            b.tr_on_edge += 1
            sig.value = new
        pending.clear()

    ident_gate = {v: k for k, v in gate_id.items()}

    line = fh.readline()
    nline = 0
    while line:
        nline += 1
        if args.progress and nline % args.progress == 0:
            print(f"  ... {nline/1e6:.1f} M lines, t={t}, cycle={cycle}",
                  file=sys.stderr)
        c = line[0]
        if c == "#":
            flush(t)
            t = int(line[1:])
        elif c in "01xzXZ":
            s = line.strip()
            v, ident = s[0].lower(), s[1:]
            if ident == clk_id or ident in ident_gate or ident in sel:
                sig = sel.get(ident)
                pending.append((ident, v if sig is None or sig.width == 1
                                else expand(v, sig.width)))
        elif c in "bB":
            sp = line.find(" ")
            ident = line[sp + 1:].strip()
            sig = sel.get(ident)
            if sig is not None:
                pending.append((ident, expand(line[1:sp].lower(), sig.width)))
        line = fh.readline()
    flush(t)

    # Close any window still open at the end of the dump.
    for wi in range(nwin):
        if win_open[wi]:
            win_open[wi] = False
            win_last_t[wi] += t - win_first_t[wi]
            for sig in sel.values():
                close_bit_time(sig, wi, t)

    out = {"vcd": args.vcd, "scope": args.scope, "clock": args.clock,
           "timescale_ps": timescale_ps, "windows": {}}

    for wi, (name, first, last, gp, gv) in enumerate(windows):
        span = win_last_t[wi]
        cycles = win_cycles[wi]
        rows = {}
        for sig in sel.values():
            for i, b in enumerate(sig.bits[wi]):
                if sig.width == 1:
                    path = sig.path
                else:
                    path = f"{sig.path}[{sig.width - 1 - i}]"
                rows[path] = {
                    "tr": b.tr,
                    "edge": b.tr_on_edge,
                    "high": b.high_time,
                    "t": sig.vtype,
                }
        drows = {}
        for di, (dn, _c) in enumerate(derives):
            drows[dn] = {"tr": dtr[wi][di], "high_cycles": dhigh[wi][di]}
        out["windows"][name] = {
            "derived": drows,
            "first_cycle": first, "last_cycle": last,
            "gate": (f"{gp}={gv}" if gp else None),
            "cycles": cycles, "span_time": span,
            "bits": rows,
        }

    out["spans"] = {k: v for k, v in span_of.items()}
    with open(args.json, "w") as f:
        json.dump(out, f)
    for k, v in span_of.items():
        print(f"span {k}: cycles {v[0]} .. {v[1]}")
    for wi, (name, first, last, gp, gv) in enumerate(windows):
        w = out["windows"][name]
        print(f"{name}: {w['cycles']} cycles, {len(w['bits'])} bits, "
              f"span {w['span_time']} time units")


if __name__ == "__main__":
    main()
