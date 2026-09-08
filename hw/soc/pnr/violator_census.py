#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Census a sign-off run's setup violators by launch point and by capture.

docs/49 section 3.1 and docs/50 section 6.3 each answer the same question
about a different run -- WHICH flip-flops are violating, and what are
they -- and each of them answered it with a script that was written for
the occasion and thrown away.  docs/61 needed it a third time.  So it is
in the tree, and the check that it is the same instrument is that it
reproduces docs/49 section 3.1's table on `runs/full3` unchanged:

    violator_census.py hw/soc/pnr/runs/full3
      444 endpoints behind u_ram.g_ram_2048x64.u_b0/A_DOUT, worst -3.2029
    1,559 behind the four register-file read-address bits, worst -2.0227

WHY THE NETLIST IS NEEDED AT ALL.  `violator_list.rpt` names the launch
point in RTL terms when the launch is a macro pin or a port, and the
capture as `_NNNNN_/D` -- an anonymous Yosys cell, because
SYNTH_HIERARCHY_MODE is `flatten` and SYNTH_AUTONAME is off (docs/59
section 6).  What that flip-flop IS can only be had by resolving the
instance name against the netlist the run hardened and reading the
public name off its Q pin.  This script does that and nothing else: it
does not read metrics, it does not judge, and where a name does not
resolve it prints `<unresolved>` rather than guessing.

Usage:

    violator_census.py <run-dir> [--corner nom_slow_1p08V_125C]
                                 [--netlist PATH] [--top N]

The netlist defaults to the run's own `final/nl/*.nl.v`, which is the
netlist that run hardened -- never another run's, because two runs'
`_NNNNN_` numbering has nothing to do with each other and resolving one
against the other silently produces a plausible and wrong census.
"""

import argparse
import collections
import glob
import os
import re
import sys

VIOL = re.compile(
    r"\[setup\s+([\w-]+)\]\s+(\S+)\s+->\s+(\S+)\s*:\s*(-?[\d.]+)")
# A mapped cell, as yosys writes it in both the synthesis netlist and the
# run's own final netlist: optional leading space, the cell type, the
# instance name, then a pin list that runs to the closing `);`.
CELL = re.compile(r"^\s*(sg13g2_\w+)\s+(\\?\S+?)\s*\(")
QPIN = re.compile(r"\.Q\(\s*(.+?)\s*\)\s*[,;)]", re.S)


def load_netlist(path):
    """instance name -> the public name on its Q pin, where there is one.

    Line-based and streaming: the run's own final netlist is 50 MB and a
    whole-file regex over it costs minutes rather than seconds.
    """
    out = {}
    inst = None
    body = []
    with open(path, errors="replace") as fh:
        for line in fh:
            if inst is None:
                m = CELL.match(line)
                if not m:
                    continue
                inst = m.group(2).lstrip("\\")
                body = [line[m.end():]]
            else:
                body.append(line)
            if ");" in body[-1]:
                q = QPIN.search("".join(body))
                if q:
                    out[inst] = q.group(1).strip()
                inst = None
    return out


MACRO = re.compile(r"^u_(ram|rom)\.g_(ram|rom)_\d+x\d+\.u_b\d+$")


def resolve(pinpath, qname):
    """`<instance>/<pin>` -> a name a reader can act on.

    Three cases and they are kept apart rather than merged.  A hard macro
    is named in the report already and is returned with its pin, because
    the pin is the whole point -- A_DOUT is a launch and A_ADDR is a
    capture and they are different findings.  A mapped flip-flop is
    looked up and its Q name returned.  Anything else is returned as it
    stands, prefixed, so it is visible as unresolved rather than
    silently bucketed.
    """
    inst, _, pin = pinpath.rpartition("/")
    if not inst:
        return pinpath, None
    if MACRO.match(inst):
        return f"{inst}/{pin}", "SRAM macro pin"
    q = qname.get(inst)
    if q is not None:
        return q, None
    return "<unresolved> " + pinpath, "<unresolved>"


def rtl_group(name):
    """Coarse bucket for a resolved capture name, for the capture census."""
    n = name.lstrip("\\").strip()
    if n.startswith("<unresolved>"):
        return "<unresolved>"
    if n.startswith("_") or not n:
        return "<unresolved>"
    if ".g_chk." in n or "rf_chk_q" in n:
        return "register file, SECDED check bits"
    if "register_file_i" in n or "rf_reg_q" in n:
        return "register file, data bits"
    for pre in ("u_npu.", "u_ibex.", "u_clint.", "u_timer0.", "u_uart0.",
                "u_bus.", "u_busstat.", "u_rom.", "u_ram.", "u_apb.",
                "u_pnp.", "u_apbpnp."):
        if n.startswith(pre):
            return pre.rstrip(".")
    return n.split(".")[0] if "." in n else "top level"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--corner", default="nom_slow_1p08V_125C")
    ap.add_argument("--netlist", default=None)
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args()

    hits = glob.glob(os.path.join(
        a.run, "*stapostpnr*", a.corner, "violator_list.rpt"))
    if not hits:
        sys.exit(f"no {a.corner}/violator_list.rpt under {a.run}")
    rpt = sorted(hits)[-1]

    nl = a.netlist
    if nl is None:
        cand = glob.glob(os.path.join(a.run, "final", "nl", "*.nl.v"))
        if not cand:
            sys.exit(f"no final/nl/*.nl.v under {a.run}; pass --netlist")
        nl = cand[0]
    qname = load_netlist(nl)

    rows = []
    for line in open(rpt, errors="replace"):
        m = VIOL.search(line)
        if m:
            rows.append((m.group(1), m.group(2), m.group(3), float(m.group(4))))

    print(f"run      {a.run}")
    print(f"corner   {a.corner}")
    print(f"report   {rpt}")
    print(f"netlist  {nl}  ({len(qname)} flip-flops with a Q name)")
    print(f"violating setup endpoints  {len(rows)}")
    if not rows:
        return 0
    print(f"worst                      {min(r[3] for r in rows):.4f}")
    print(f"sum of violating slacks    {sum(r[3] for r in rows):.2f}")

    def census(title, key, limit):
        buckets = collections.defaultdict(list)
        for kind, launch, cap, slack in rows:
            buckets[key(launch, cap)].append(slack)
        print(f"\nby {title}")
        print(f"  {'':70s} {'count':>7s} {'worst':>9s} {'TNS':>12s}")
        items = sorted(buckets.items(), key=lambda kv: -len(kv[1]))
        for name, ss in items[:limit]:
            print(f"  {name[:70]:70s} {len(ss):7d} {min(ss):9.4f} "
                  f"{sum(ss):12.2f}")
        if len(items) > limit:
            rest = [s for _, ss in items[limit:] for s in ss]
            print(f"  {f'... {len(items) - limit} more':70s} {len(rest):7d} "
                  f"{min(rest):9.4f} {sum(rest):12.2f}")
        return buckets

    census("LAUNCH point, resolved",
           lambda lo, ca: resolve(lo, qname)[0].lstrip("\\"), a.top)
    census("CAPTURE group",
           lambda lo, ca: (resolve(ca, qname)[1]
                           or rtl_group(resolve(ca, qname)[0])), a.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
