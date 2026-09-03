#!/usr/bin/env python3
"""Turn `vcd_activity.py`'s toggle counts into an OpenSTA annotation.

    power_activity.py act.json --window busy --scope tb_soc.dut \
        --exclude tb_soc.dut.u_npu --tcl act_busy.tcl [--report]

THE ANNOTATION MODEL, stated because it is the whole of what separates
this number from `docs/47`'s.

OpenSTA's `report_power` gives every top-level input port and every
register output a default activity of **0.1 transitions per clock period
at a 50 % duty cycle** and propagates that through the combinational
logic; `set_power_activity -input -activity 0.1 -duty 0.5` reproduces
the default figure to every digit, which is how the default was
established rather than assumed.  This script replaces the 0.1 and the
0.5 with three measured things:

  1. **The register population's mean.**  `-input -activity A -duty D`,
     where A is the mean toggles per clock cycle over every bit in the
     design that behaves as a register in the dump, and D is their mean
     time at 1.  This is the term the default 0.1 stands in for.
  2. **The top-level input ports**, each with its own measured pair.
  3. **The six SRAM macro control pins**, each with its own measured
     pair, on the macro instances by name.  The macro Liberty's internal
     power is `when`-conditioned on `A_MEN`, `A_WEN` and `A_REN` -- an
     unselected macro burns nothing per clock edge and a selected one
     burns 122 to 156 pJ -- so the duty cycle of those three pins is the
     difference between a memory that is being used and a memory that is
     merely powered.

WHAT IT DOES NOT DO.  It does not annotate a single internal pin of the
logic, because there is no name to annotate: `syn_soc_top.sh`'s
`synth -flatten` and `abc` leave 617 named nets out of 33,832 and not one
named flip-flop.  Combinational activity is therefore OpenSTA's
propagation from a measured seed rather than a measurement, and glitch
power is absent from both this and the default.
"""

import argparse
import json
import sys
from collections import defaultdict


def load(path):
    with open(path) as f:
        return json.load(f)


def population(data, scope, exclude, ref_window):
    """Bits that behave as registers over the reference window: at least one
    transition, and every transition on a rising clock edge."""
    w = data["windows"][ref_window]
    regs, moving, dead = [], [], []
    for path, r in w["bits"].items():
        if any(path == e or path.startswith(e + ".") or path.startswith(e + "[")
               for e in exclude):
            continue
        if r["tr"] == 0:
            dead.append(path)
            continue
        moving.append(path)
        # A FLIP-FLOP OUTPUT, as closely as an RTL dump can say so:
        # declared `reg`, and every transition on a rising clock edge.
        # The second half is necessary and not sufficient -- an RTL
        # simulation has no delays, so a combinational net settles in the
        # same timestamp as the flip-flop that drives it and is "on the
        # edge" too. The first half is what separates them, and it is a
        # statement about a Verilog declaration rather than about
        # hardware, which is why the report prints both populations and
        # the document quotes the power at both.
        if r.get("t") == "reg" and r["edge"] == r["tr"]:
            regs.append(path)
    return regs, moving, dead


def block_of(path, scope):
    rest = path[len(scope) + 1:] if path.startswith(scope + ".") else path
    head = rest.split(".")[0]
    return head if "." in rest else "(top)"


def stats(data, window, paths):
    w = data["windows"][window]
    cycles = w["cycles"]
    span = w["span_time"] or 1
    tr = sum(w["bits"][p]["tr"] for p in paths)
    high = sum(w["bits"][p]["high"] for p in paths)
    n = len(paths)
    return {
        "n": n,
        "cycles": cycles,
        "transitions": tr,
        "activity": (tr / n / cycles) if n and cycles else 0.0,
        "duty": (high / n / span) if n else 0.0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json")
    ap.add_argument("--window", required=True)
    ap.add_argument("--ref-window", default="all")
    ap.add_argument("--scope", required=True)
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--port", action="append", default=[],
                    metavar="PORT=VCDPATH")
    ap.add_argument("--macro-pin", action="append", default=[],
                    metavar="INST/PIN=DERIVEDNAME")
    ap.add_argument("--pin", action="append", default=[],
                    metavar="INST/PIN=VCDPATH",
                    help="annotate a named cell pin from a signal in the "
                         "dump. The one that matters is the enable of "
                         "u_ibex.core_clock_gate_i.u_icg -- the sg13g2_lgcp_1 "
                         "integrated clock gate that Ibex instantiates and "
                         "that hw/soc/rtl/prim_clock_gating.v binds. It is "
                         "the only clock gate in the design and it covers "
                         "2,464 of its 3,085 flip-flops.")
    ap.add_argument("--tcl")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--blocks", action="store_true")
    args = ap.parse_args()

    data = load(args.json)
    regs, moving, dead = population(data, args.scope, args.exclude,
                                    args.ref_window)
    w = data["windows"][args.window]
    cycles = w["cycles"]

    s_reg = stats(data, args.window, regs)
    s_comb = stats(data, args.window, moving)

    if args.report:
        print(f"window {args.window}: {cycles} cycles")
        print(f"  register bits      {s_reg['n']:6d}  "
              f"activity {s_reg['activity']:.6f}  duty {s_reg['duty']:.4f}  "
              f"transitions {s_reg['transitions']}")
        print(f"  all moving bits    {s_comb['n']:6d}  "
              f"activity {s_comb['activity']:.6f}  duty {s_comb['duty']:.4f}  "
              f"transitions {s_comb['transitions']}")
        print(f"  never-moving bits  {len(dead):6d}")

    if args.blocks:
        byblock = defaultdict(list)
        for p in regs:
            byblock[block_of(p, args.scope)].append(p)
        rows = []
        for b, ps in byblock.items():
            st = stats(data, args.window, ps)
            rows.append((b, st["n"], st["activity"], st["duty"],
                         st["transitions"]))
        rows.sort(key=lambda r: -r[4])
        print(f"  {'block':<18}{'regbits':>8}{'activity':>12}"
              f"{'duty':>8}{'transitions':>14}{'share':>8}")
        tot = sum(r[4] for r in rows) or 1
        for b, n, a, d, t in rows:
            print(f"  {b:<18}{n:>8}{a:>12.6f}{d:>8.3f}{t:>14}"
                  f"{100.0 * t / tot:>7.2f}%")

    if args.tcl:
        out = []
        out.append(f"# generated by power_activity.py from {args.json}")
        out.append(f"# window {args.window}: {cycles} cycles, "
                   f"{s_reg['n']} register bits")
        out.append(f"set_power_activity -input -activity "
                   f"{s_reg['activity']:.6f} -duty {s_reg['duty']:.6f}")
        for spec in args.port:
            port, path = spec.split("=", 1)
            r = w["bits"].get(path)
            if r is None:
                sys.exit(f"port path not in the dump: {path}")
            a = r["tr"] / cycles if cycles else 0.0
            d = r["high"] / (w["span_time"] or 1)
            out.append(f"set_power_activity -input_ports [get_ports {port}] "
                       f"-activity {a:.6f} -duty {d:.6f}")
        for spec in args.pin:
            lhs, path = spec.split("=", 1)
            r = w["bits"].get(path)
            if r is None:
                sys.exit(f"pin path not in the dump: {path}")
            a = r["tr"] / cycles if cycles else 0.0
            d = r["high"] / (w["span_time"] or 1)
            out.append(f"set_power_activity -pins [get_pins {{{lhs}}}] "
                       f"-activity {a:.6f} -duty {d:.6f}")
        for spec in args.macro_pin:
            lhs, dname = spec.split("=", 1)
            dr = w.get("derived", {}).get(dname)
            if dr is None:
                sys.exit(f"derived signal not in the dump: {dname}")
            a = dr["tr"] / cycles if cycles else 0.0
            d = dr["high_cycles"] / cycles if cycles else 0.0
            out.append(f"set_power_activity -pins [get_pins {{{lhs}}}] "
                       f"-activity {a:.6f} -duty {d:.6f}")
        with open(args.tcl, "w") as f:
            f.write("\n".join(out) + "\n")
        print(f"wrote {args.tcl} ({len(out) - 2} annotations)")

    if args.report:
        for dname, dr in sorted(w.get("derived", {}).items()):
            a = dr["tr"] / cycles if cycles else 0.0
            d = dr["high_cycles"] / cycles if cycles else 0.0
            print(f"  derived {dname:<12} activity {a:.6f}  duty {d:.6f}")


if __name__ == "__main__":
    main()
