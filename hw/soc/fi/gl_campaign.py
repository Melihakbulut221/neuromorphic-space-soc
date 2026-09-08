#!/usr/bin/env python3
"""The core fault-injection campaign of docs/42 and docs/43, replayed on
the mapped netlist -- docs/74.

    gl_campaign.py run --build hw/soc/out/gl74 --map map.json \\
        --records hw/soc/out/fi-h1/records.csv --rtl-golden <log> \\
        [--jobs N] [--armed all|subset] [--subset 100]
    gl_campaign.py sweep --build ... --map ... [--draws 3]
    gl_campaign.py reconcile --build ... --map ... \\
        --records <fi-h1/records.csv> --head <fi-h74rtl/directed.csv>

WHAT IT DOES, AND WHAT IT DOES NOT DECIDE

`run` takes an RTL campaign's records verbatim -- site, bit, cycle --
and re-injects each one into the netlist flip-flop hw/soc/fi/gl_map.py
identified as that RTL bit's twin, at the same cycle (shifted by the
one clock the mapping measured), with the watchdog held off and, for
the records where it matters, armed.  It classifies every gate-level
record with hw/soc/fi/campaign.py's own `classify`, unchanged, against
a gate-level clean run, so the class scheme, the announcement channels
and the oracle are the RTL campaign's and not a second opinion.

`sweep` injects into the flip-flops the netlist has and the RTL site
table does not: the re-encoded state machines, the merged instruction
register and whatever else synthesis made.  docs/32 section 5.3 did the
same for the pilot's new redundancy.

`reconcile` puts three campaigns side by side, record for record: the
RTL campaign of record (docs/43's `fi-h1`), the same records replayed
on the HEAD RTL the netlist was synthesised from, and the gate-level
replay.  docs/32 section 5's standard: for every RTL injection with a
netlist twin, the gate-level injection at the same cycle must classify
the same way, and any that does not is a finding.

THE CONTROLS, EACH OF WHICH IS A WAY TO REPORT A NUMBER WHILE MEASURING
NOTHING (docs/42 section 5.1, docs/52 section 5.1)

  1. the elaborated netlist bench has exactly the flop count the parse
     found;
  2. the gate-level clean run completes, is silent in every channel and
     publishes the same signature, mask, rounds, exit, magic, console
     length and console hash as the RTL clean run;
  3. it reproduces, and is identical with the watchdog held off;
  4. a force lands (the value DURING the force is the complement of the
     value before it), a positive control cannot classify MASKED, a
     negative control can;
  5. (--trace-check) for a handful of records, the whole mapped flop
     state after the injection is identical, cycle for cycle, between
     the RTL deposit and the gate-level force -- which is what makes the
     force an upset and not a different fault.
"""

import argparse
import collections
import concurrent.futures
import csv
import json
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import campaign                                        # noqa: E402
import targets                                         # noqa: E402
from gl_map import read_flops, read_trace, site_layout  # noqa: E402
from gl_netlist import plain, graph, wdog_replicas, parse as parse_netlist  # noqa: E402

# Mappings the campaign injects through.  `alias` is a name-only
# mapping of a bit that never changes in the clean run; it is injected
# because the RTL campaign injected it, and reported apart.
INJECT_HOW = ("trace+name", "trace&alias", "trace", "alias", "merged")

GL_VVP = os.path.expanduser("~/.local/opt/iverilog13/usr/bin/vvp")
SEED = 0x74F12026


class GLRunner:
    def __init__(self, vvp, image, budget, rld, pre):
        self.vvp, self.image, self.budget = vvp, image, budget
        self.rld, self.pre = rld, pre

    def run(self, site=None, cycle=0, armed=True, trace=None, dumpsites=False,
            zero=1):
        cmd = [self.vvp, "-n", self.image]
        if site is not None:
            cmd += ["+site=%d" % site, "+cycle=%d" % cycle]
        cmd += ["+armed=%d" % (1 if armed else 0), "+budget=%d" % self.budget,
                "+wdog_rld=%d" % self.rld, "+wdog_pre=%d" % self.pre,
                "+zero=%d" % zero]
        if trace:
            cmd += ["+trace=%s" % trace]
        if dumpsites:
            cmd += ["+dumpsites"]
        t0 = time.time()
        out = subprocess.run(cmd, capture_output=True, text=True,
                             check=True).stdout
        rec = campaign.parse_record(out)
        if "_end" not in rec:
            raise RuntimeError("no complete RECORD:\n" + out[-2000:])
        rec["_raw"] = out
        rec["_wall"] = time.time() - t0
        return rec


def read_records(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_map(path):
    m = json.load(open(path))
    ent = {(e["stratum"], e["name"], e["bit"]): e for e in m["entries"]}
    return m, ent


def rtl_golden_record(path):
    return campaign.parse_record(open(path).read())


def answer_fields(rec):
    return dict(zip(("sig", "mask", "rounds", "exit", "magic", "console_chars",
                     "console_hash", "console_framing", "slept"),
                    campaign.answer(rec)))


def say_factory(log_path, append=False):
    log = open(log_path, "a" if append else "w")

    def say(fmt, *a):
        line = fmt % a if a else fmt
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()
    return say, log


def wilson(k, n):
    return campaign.wilson(k, n)


# =====================================================================
def controls(args, say, flops, m, golden_rtl):
    build = os.path.abspath(args.build)
    image = os.path.join(build, "tb_soc_fi_gl.vvp")
    if not os.path.exists(image):
        sys.exit("missing %s" % image)
    rld, pre = campaign.i(golden_rtl, "wdog_rld"), campaign.i(golden_rtl, "wdog_pre")
    probe = GLRunner(args.vvp, image, 200000, rld, pre)

    # control 1
    d = probe.run(dumpsites=True)
    count = None
    for line in d["_raw"].splitlines():
        if line.startswith("SITECOUNT "):
            count = int(line.split()[1])
    if count != len(flops):
        sys.exit("the bench elaborated %s sites, flops.tsv lists %d"
                 % (count, len(flops)))
    say("control 1: the bench elaborated %d flip-flops, the netlist parse "
        "lists %d", count, len(flops))

    # control 2
    golden = probe.run(armed=True)
    if not campaign.completed(golden):
        sys.exit("the gate-level clean run did not complete:\n" + golden["_raw"][-2000:])
    for k, v in (("mask", "00000000"), ("exit", "00000000"), ("magic", "600dc0de")):
        if golden[k] != v:
            sys.exit("the clean run's %s is %s, expected %s" % (k, golden[k], v))
    if campaign.wdog_fired(golden) or campaign.i(golden, "traps") \
            or campaign.alert_seen(golden) or campaign.i(golden, "console_framing"):
        sys.exit("the gate-level clean run is not silent in every channel: %s"
                 % golden)
    a_gl, a_rtl = answer_fields(golden), answer_fields(golden_rtl)
    if a_gl != a_rtl:
        sys.exit("the gate-level clean run does not publish the RTL clean "
                 "run's answer:\n  gate level %s\n  RTL        %s" % (a_gl, a_rtl))
    say("control 2: gate-level clean run %d cycles (RTL %d), sig %s, %d "
        "console characters, hash %s, window %d..%d (RTL %d..%d); the "
        "published answer is identical to the RTL clean run's in every "
        "compared field",
        campaign.i(golden, "cycles"), campaign.i(golden_rtl, "cycles"),
        golden["sig"], campaign.i(golden, "console_chars"), golden["console_hash"],
        campaign.i(golden, "win_open"), campaign.i(golden, "win_close"),
        campaign.i(golden_rtl, "win_open"), campaign.i(golden_rtl, "win_close"))
    if campaign.i(golden, "rf_sec") > 0 or campaign.i(golden, "rf_ded") > 0:
        sys.exit("the shadow decoder saw a correction or an uncorrectable "
                 "error on the clean run")
    say("           register-file shadow: %s (rf_sec=%s rf_ded=%s)",
        "present" if golden.get("rf_shadow") == "1" else "ABSENT",
        golden["rf_sec"], golden["rf_ded"])

    # control 3
    again = probe.run(armed=True)
    if campaign.answer(again) != campaign.answer(golden) or \
            campaign.i(again, "cycles") != campaign.i(golden, "cycles"):
        sys.exit("the gate-level clean run is not reproducible")
    dis = probe.run(armed=False)
    if campaign.answer(dis) != campaign.answer(golden):
        sys.exit("the clean run differs with the watchdog held off")
    say("control 3: the clean run reproduces exactly, and is identical with "
        "the watchdog held off")

    # the budget, campaign.py's formula on the gate-level clean run
    timeout_clk = (rld + 1) * pre
    ladder = 2 * timeout_clk
    win_close = campaign.i(golden, "win_close")
    budget = 2 * campaign.i(golden, "cycles") + 6 * ladder
    need = win_close + 4 * ladder + campaign.i(golden, "cycles")
    if budget < need:
        budget = need
    say("           budget %d cycles (RTL campaign %d): ladder %d clocks "
        "from the RTL clean run's reload %d and prescale %d, passed in; "
        "%.1f ladders after the latest drawn cycle",
        budget, 2 * campaign.i(golden_rtl, "cycles") + 6 * ladder, ladder,
        rld, pre, (budget - win_close) / float(ladder))
    runner = GLRunner(args.vvp, image, budget, rld, pre)

    # control 4
    ent = m["ent"]
    shift = m["gl_row_shift"]
    mid_rtl = (campaign.i(golden_rtl, "win_open") + campaign.i(golden_rtl, "win_close")) // 2
    e = ent[("regfile", "x2", 20)]
    pos = runner.run(site=e["gl"], cycle=mid_rtl + shift, armed=True)
    if campaign.i(pos, "hit") != 1 or campaign.i(pos, "during") == \
            int(pos["before"], 16):
        sys.exit("the positive control's force did not take")
    pcls, _ = campaign.classify(pos, golden)
    if pcls == "MASKED":
        sys.exit("flipping bit 20 of the stack pointer classified MASKED at "
                 "gate level; the force is not reaching the design")
    say("control 4a: bit 20 of x2 (flop #%d, %s) at RTL cycle %d = gate-level "
        "cycle %d classifies %s, persisted after release: %s",
        e["gl"], flops[e["gl"]]["q"], mid_rtl, mid_rtl + shift, pcls,
        pos["persist"])
    e = ent[("csr_cnt", "mcycle", 40)]
    if e["gl"] is None:
        say("control 4b: bit 40 of mcycle has no netlist twin (%s); the "
            "negative control uses bit 8 instead", e["how"])
        e = ent[("csr_cnt", "mcycle", 8)]
    neg = runner.run(site=e["gl"], cycle=mid_rtl + shift, armed=True)
    ncls, _ = campaign.classify(neg, golden)
    say("control 4b: bit %d of mcycle (flop #%d), which this program never "
        "reads, classifies %s", e["bit"], e["gl"], ncls)
    return runner, golden, budget, timeout_clk


def trace_check(args, say, runner, m, flops, golden_rtl):
    """Control 5: the same injection at both levels leaves the mapped
    flops in the same state, cycle for cycle, afterwards."""
    recs = read_records(args.records)
    ent = m["ent"]
    shift = m["gl_row_shift"]
    inst = {}
    if args.instants:
        for x in read_records(args.instants):
            if x["actual_row"] != "":
                inst[(x["path"], int(x["bit"]), int(x["cycle"]))] = int(x["actual_row"])
    rng = random.Random(SEED)
    live = [r for r in recs if ent.get((r["stratum"], r["site"], int(r["bit"])), {}).get("how") in ("trace+name", "trace&alias")
            and (not inst or (r["path"], int(r["bit"]), int(r["cycle"])) in inst)]
    rng.shuffle(live)
    picks = live[:args.trace_check]
    rtl_build = os.path.abspath(args.rtl_build)
    rtl_vvp = args.rtl_vvp
    layout, _ = site_layout()
    by_site = {(s.stratum, s.name): (k, off) for k, s, off in layout}
    mapped = [(e["rtl_flat"], e["gl"], e["pol"]) for e in m["entries"]
              if e["gl"] is not None and e["how"] in ("trace+name", "trace&alias", "trace")]
    out_dir = os.path.abspath(args.out or args.build)
    results = []
    for r in picks:
        e = ent[(r["stratum"], r["site"], int(r["bit"]))]
        cyc = int(r["cycle"])
        actual = inst.get((r["path"], int(r["bit"]), cyc), cyc)
        tr_gl = os.path.join(out_dir, "tc_gl_%s_%s_%d.trace" % (r["stratum"], r["site"], cyc))
        tr_rtl = os.path.join(out_dir, "tc_rtl_%s_%s_%d.trace" % (r["stratum"], r["site"], cyc))
        g = runner.run(site=e["gl"], cycle=actual + shift, armed=False, trace=tr_gl)
        site_idx = by_site[(r["stratum"], r["site"])][0]
        cmd = [rtl_vvp, "-n", os.path.join(rtl_build, "tb_soc_fi.vvp"),
               "+site=%d" % site_idx, "+bit=%s" % r["bit"], "+cycle=%d" % cyc,
               "+armed=0", "+budget=%d" % runner.budget, "+trace=%s" % tr_rtl]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        rc, nr = read_trace(tr_rtl)
        gc, ng = read_trace(tr_gl)
        # align as the mapping did: gate-level row t is RTL row t - shift
        if shift < 0:
            rc2 = [c[-shift:] for c in rc]
            gc2 = [c[:len(c) + shift] for c in gc]
        else:
            rc2 = [c[:len(c) - shift] if shift else c for c in rc]
            gc2 = [c[shift:] for c in gc]
        n = min(len(rc2[0]), len(gc2[0]))
        diff_bits = 0
        first_diff = None
        for rf, gi, pol in mapped:
            a = rc2[rf][:n]
            b = gc2[gi][:n]
            if pol:
                b = b.translate(str.maketrans("01", "10"))
            if a != b:
                diff_bits += 1
                d0 = next(i for i in range(n) if a[i] != b[i])
                if first_diff is None or d0 < first_diff:
                    first_diff = d0
        results.append((r, g, n, diff_bits, first_diff, nr, ng))
        say("control 5: %s.%s[%s] at RTL cycle %d (landed on row %d) -> gate-level edge %d: "
            "RTL rows %d, gate-level rows %d, %d aligned; mapped flops "
            "differing anywhere: %d of %d%s; gate-level class %s, RTL class "
            "of record %s",
            r["stratum"], r["site"], r["bit"], cyc, actual, actual + shift, nr, ng, n,
            diff_bits, len(mapped),
            "" if first_diff is None else " (first at row %d)" % first_diff,
            campaign.classify(g, m["golden"])[0], r["disarmed_cls"])
        os.remove(tr_gl)
        os.remove(tr_rtl)
    return results


# =====================================================================
def cmd_run(args):
    build = os.path.abspath(args.build)
    out_dir = os.path.abspath(args.out or build)
    os.makedirs(out_dir, exist_ok=True)
    say, log = say_factory(os.path.join(out_dir, "gl_campaign.log"))
    flops = read_flops(os.path.join(build, "flops.tsv"))
    m, ent = load_map(args.map)
    m["ent"] = ent
    golden_rtl = rtl_golden_record(args.rtl_golden)
    t_start = time.time()
    say("gate-level campaign, docs/74: build %s, map %s, records %s",
        build, args.map, args.records)
    say("provenance:\n%s", open(os.path.join(build, "provenance.txt")).read().rstrip())
    runner, golden, budget, timeout_clk = controls(args, say, flops, m, golden_rtl)
    m["golden"] = golden
    shift = m["gl_row_shift"]

    if args.trace_check:
        trace_check(args, say, runner, m, flops, golden_rtl)

    recs = read_records(args.records)
    # The instant each RTL deposit actually landed on (cmd_instants),
    # keyed like the records; the replay cycle is that row plus the
    # design alignment, not the record's own cycle field.
    instants = {}
    if args.instants:
        for x in read_records(args.instants):
            if x["actual_row"] != "":
                instants[(x["path"], int(x["bit"]), int(x["cycle"]))] = int(x["actual_row"])
    prior = {}
    if args.redo_from:
        for x in read_records(args.redo_from):
            prior[(x["path"], int(x["bit"]), int(x["cycle"]))] = x
    # which records are replayed, and how
    plan = []
    skipped = collections.Counter()
    for r in recs:
        key = (r["stratum"], r["site"], int(r["bit"]))
        e = ent.get(key)
        if e is None:
            skipped["not in the site table"] += 1
            continue
        if e["gl"] is None or e["how"] not in INJECT_HOW:
            skipped[e["how"]] += 1
            continue
        rk = (r["path"], int(r["bit"]), int(r["cycle"]))
        if instants and rk not in instants:
            skipped["no measured instant"] += 1
            continue
        want = (instants[rk] if instants else int(r["cycle"])) + shift
        if prior:
            pr = prior.get(rk)
            if pr is not None and int(pr["gl_cycle"]) == want and not args.redo_all:
                skipped["already replayed at this cycle"] += 1
                continue
        plan.append((r, e, want))
    say("")
    say("replay: %d RTL records, %d have a netlist twin and are replayed, "
        "%d do not: %s", len(recs), len(plan), len(recs) - len(plan),
        ", ".join("%s %d" % (k, v) for k, v in sorted(skipped.items())))

    # the armed run: every record, or the records where the RTL campaign
    # says the watchdog is in play plus a calibration subset
    rng = random.Random(SEED)
    armed_set = set()
    if args.armed == "all":
        armed_set = set(range(len(plan)))
    else:
        for k, (r, e, _w) in enumerate(plan):
            if r["armed_cls"] != r["disarmed_cls"] or r["ann_wdog"] in ("True", "1") \
                    or r["truth"] == "DEAD":
                armed_set.add(k)
        rest = [k for k in range(len(plan)) if k not in armed_set]
        rng.shuffle(rest)
        armed_set.update(rest[:args.subset])
    say("armed runs: %d of %d (%s)", len(armed_set), len(plan), args.armed)
    say("each replayed cycle is shifted by %d (the mapping's measured "
        "reset-release offset)", shift)

    def job(k):
        r, e, cyc = plan[k]
        d = runner.run(site=e["gl"], cycle=cyc, armed=False)
        a = runner.run(site=e["gl"], cycle=cyc, armed=True) if k in armed_set else None
        return k, a, d

    rows = []
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for k, a, d in ex.map(job, range(len(plan))):
            r, e, cyc = plan[k]
            for rec in (a, d):
                if rec is None:
                    continue
                if campaign.i(rec, "hit") != 1:
                    sys.exit("a force did not land: record %d" % k)
                if campaign.i(rec, "during") == int(rec["before"], 16):
                    sys.exit("a force did not flip the flop: record %d" % k)
            dcls, df = campaign.classify(d, golden)
            row = {
                "stratum": r["stratum"], "site": r["site"], "path": r["path"],
                "bit": r["bit"], "cycle": r["cycle"], "gl_cycle": cyc,
                "gl_force_ps": d.get("force_ps", ""),
                "gl_idx": e["gl"], "gl_net": flops[e["gl"]]["q"], "how": e["how"],
                "pol": e["pol"],
                "rtl_armed_cls": r["armed_cls"], "rtl_disarmed_cls": r["disarmed_cls"],
                "rtl_truth": r["truth"],
                "gl_disarmed_cls": dcls,
                "gl_truth": "OK" if df["out_ok"] else ("WRONG" if df["done"] else "DEAD"),
                "gl_disarmed_out_ok": df["out_ok"], "gl_disarmed_done": df["done"],
                "gl_disarmed_cycles": df["cycles"], "gl_disarmed_rf_sec": df["rf_sec"],
                "gl_disarmed_rf_ded": df["rf_ded"],
                "gl_disarmed_ann_sw": df["ann_sw"], "gl_disarmed_ann_trap": df["ann_trap"],
                "gl_disarmed_ann_alert": df["ann_alert"],
                "gl_persist": d["persist"],
                "gl_disarmed_wall": "%.1f" % d["_wall"],
            }
            if a is not None:
                acls, af = campaign.classify(a, golden)
                row.update({
                    "gl_armed_cls": acls, "gl_armed_out_ok": af["out_ok"],
                    "gl_armed_done": af["done"], "gl_ann_wdog": af["ann_wdog"],
                    "gl_wdog_stage": af["wdog_stage"], "gl_wdog_first": af["wdog_first"],
                    "gl_wdog_latency": (af["wdog_first"] - cyc
                                        if af["wdog_first"] >= 0 else -1),
                    "gl_armed_cycles": af["cycles"], "gl_armed_rf_sec": af["rf_sec"],
                    "gl_armed_wall": "%.1f" % a["_wall"],
                })
            else:
                row.update({k2: "" for k2 in ("gl_armed_cls", "gl_armed_out_ok",
                                              "gl_armed_done", "gl_ann_wdog",
                                              "gl_wdog_stage", "gl_wdog_first",
                                              "gl_wdog_latency", "gl_armed_cycles",
                                              "gl_armed_rf_sec", "gl_armed_wall")})
            rows.append(row)
            done += 1
            if done % 50 == 0:
                say("  ... %d of %d (%.0f s elapsed)", done, len(plan),
                    time.time() - t_start)
    rows.sort(key=lambda x: (targets.STRATA.index(x["stratum"]), x["site"], int(x["bit"]), int(x["cycle"])))
    path = os.path.join(out_dir, args.records_out or "records_gl.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    say("records: %s", path)
    say("wall: %.1f s for %d disarmed and %d armed simulations, %d jobs, "
        "on a machine shared with other work (contended)",
        time.time() - t_start, len(plan), len(armed_set), args.jobs)
    log.close()


# =====================================================================
def cmd_sweep(args):
    """The flip-flops the netlist has under u_ibex. and the RTL site
    table does not: injected on their own, at cycles drawn per flop."""
    build = os.path.abspath(args.build)
    out_dir = os.path.abspath(args.out or build)
    say, log = say_factory(os.path.join(out_dir, "gl_sweep.log"))
    flops = read_flops(os.path.join(build, "flops.tsv"))
    m, ent = load_map(args.map)
    m["ent"] = ent
    golden_rtl = rtl_golden_record(args.rtl_golden)
    runner, golden, budget, timeout_clk = controls(args, say, flops, m, golden_rtl)
    twins = set(e["gl"] for e in m["entries"] if e["gl"] is not None)
    gl_cols, _ = read_trace(args.gl_trace or os.path.join(build, "golden_gl.trace"))
    rtl_cols, _ = read_trace(args.rtl_trace)
    rtl_set = set(rtl_cols) | set(c.translate(str.maketrans("01", "10")) for c in rtl_cols)
    core = [f for f in flops if plain(f["q"])[0].startswith("u_ibex.")]
    extra = []
    for f in core:
        if f["idx"] in twins:
            continue
        col = gl_cols[f["idx"]]
        if col.count(col[0]) == len(col):
            kind = "constant"
        elif col in rtl_set:
            kind = "duplicate"
        else:
            kind = "new"
        extra.append((f, kind))
    kinds = collections.Counter(k for _, k in extra)
    say("netlist flip-flops under u_ibex. that are no RTL bit's twin: %d "
        "(%s)", len(extra), ", ".join("%s %d" % kv for kv in sorted(kinds.items())))
    todo = [(f, k) for f, k in extra if k != "constant" or args.constants]
    lo, hi = campaign.i(golden_rtl, "win_open"), campaign.i(golden_rtl, "win_close")
    shift = m["gl_row_shift"]
    plan = []
    for f, kind in todo:
        rng = random.Random("%d:%d" % (SEED, f["idx"]))
        for k in range(args.draws):
            plan.append((f, kind, rng.randrange(lo, hi)))
    say("sweep: %d flip-flops x %d draws = %d injections, watchdog held off",
        len(todo), args.draws, len(plan))

    def job(item):
        f, kind, cyc = item
        return item, runner.run(site=f["idx"], cycle=cyc + shift, armed=False)

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for n, (item, d) in enumerate(ex.map(job, plan), 1):
            f, kind, cyc = item
            if campaign.i(d, "hit") != 1 or campaign.i(d, "during") == int(d["before"], 16):
                sys.exit("a force did not land: flop %d" % f["idx"])
            cls, df = campaign.classify(d, golden)
            rows.append({"gl_idx": f["idx"], "gl_net": f["q"], "kind": kind,
                         "cycle": cyc, "gl_cycle": cyc + shift, "cls": cls,
                         "truth": "OK" if df["out_ok"] else ("WRONG" if df["done"] else "DEAD"),
                         "out_ok": df["out_ok"], "done": df["done"],
                         "ann_sw": df["ann_sw"], "ann_trap": df["ann_trap"],
                         "ann_alert": df["ann_alert"], "rf_sec": df["rf_sec"],
                         "persist": d["persist"], "cycles": df["cycles"],
                         "wall": "%.1f" % d["_wall"]})
            if n % 25 == 0:
                say("  ... %d of %d", n, len(plan))
    path = os.path.join(out_dir, "records_gl_sweep.csv")
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    say("records: %s", path)
    # a per-name summary
    per = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        per[(plain(r["gl_net"])[0], r["kind"])][r["cls"]] += 1
    say("")
    say("%-78s %-9s %s" % ("netlist name", "kind", "  ".join("%9s" % c for c in campaign.CLASSES)))
    for (name, kind), c in sorted(per.items()):
        say("%-78s %-9s %s" % (name, kind, "  ".join("%9d" % c[cl] for cl in campaign.CLASSES)))
    log.close()


# =====================================================================
def cmd_wdog(args):
    """The watchdog's protected word at gate level: every replica
    flip-flop of the three banks, upset once each with the watchdog
    armed, and the voter watched through the bench's shadow.

    docs/41 section 8.2 and docs/43 section 9.2 measured this at RTL
    (126 of 126, then 168 of 168 CORRECTED, through WDOGSTAT's TMR
    count).  Here the class is the same test on the netlist: golden
    answer AND the voted word's own tmr_count moved -> CORRECTED; golden
    answer and no count -> MASKED; anything else as campaign.py says.
    tmr_count is a field of the protected word and in silicon is read
    over the bus (WDOGSTAT); the bench reads the voted word directly."""
    build = os.path.abspath(args.build)
    out_dir = os.path.abspath(args.out or build)
    say, log = say_factory(os.path.join(out_dir, "gl_wdog.log"))
    flops = read_flops(os.path.join(build, "flops.tsv"))
    m, ent = load_map(args.map)
    m["ent"] = ent
    golden_rtl = rtl_golden_record(args.rtl_golden)
    runner, golden, budget, timeout_clk = controls(args, say, flops, m, golden_rtl)
    if golden.get("wd_shadow") != "1":
        sys.exit("this build has no watchdog shadow (fi_gl_wdog.vh)")
    say("clean run: voter mismatch cycles %s, tmr_count %s, tmr_err %s",
        golden["wd_mismatch"], golden["wd_tmr_count"], golden["wd_tmr_err"])
    netlist = open(os.path.join(build, "provenance.txt")).read().split("\n")[0].split()[1]
    nf, _ = parse_netlist(netlist)
    d, c = graph(netlist)
    a, b, cc = wdog_replicas(nf, d, c)
    say("replica flip-flops by voter cone: A %d, B %d, C %d (named: %d, %d, %d)",
        len(a), len(b), len(cc),
        *[sum(1 for f in bank if not plain(f.q)[0].startswith("_")) for bank in (a, b, cc)])
    shift = m["gl_row_shift"]
    lo, hi = campaign.i(golden_rtl, "win_open"), campaign.i(golden_rtl, "win_close")
    # THE DRAW'S KEY, and it is a choice with a reason (docs/75 section 7).
    #
    # docs/74 keyed the per-flop generator on the flip-flop's INDEX IN
    # THE NETLIST, which is exact for one netlist and is not stable
    # across two: W9 added one flip-flop to soc_wdog, every index after
    # it moved by one, and the same seed would have drawn different
    # cycles for the repaired design than for the baseline. A
    # counterfactual whose two arms were injected at different cycles is
    # not a counterfactual.
    #
    # --plan position keys on (bank, position within the bank) instead,
    # which is the same physical bit in any netlist that holds the same
    # word in three banks of the same width, and the check below is what
    # says the two orderings really are the same bit: replica A's
    # flip-flops carry `u_prot_a.bits [k]`, so position must equal bit,
    # and in B and C the NAMED half must appear at the same positions
    # with the same bit numbers.
    #
    # The default is unchanged so that docs/74's 174 records reproduce.
    if args.plan == "position":
        for bank, fs in (("A", a), ("B", b), ("C", cc)):
            named = [(i, plain(f.q)) for i, f in enumerate(fs)
                     if not plain(f.q)[0].startswith("_")]
            say("plan check: bank %s, %d of %d flip-flops named, at "
                "positions %s", bank, len(named), len(fs),
                ",".join("%d:%s" % (i, n[1]) for i, n in named))
    plan = []
    for bank, fs in (("A", a), ("B", b), ("C", cc)):
        for pos, f in enumerate(fs):
            key = ("%d:wdog:%s:%d" % (SEED, bank, pos) if args.plan == "position"
                   else "%d:wdog:%d" % (SEED, f.idx))
            rng = random.Random(key)
            for k in range(args.draws):
                plan.append((bank, f, rng.randrange(lo, hi)))
    say("sweep: %d replica flip-flops x %d draws = %d injections, watchdog "
        "ARMED, plan keyed by %s",
        len(a) + len(b) + len(cc), args.draws, len(plan), args.plan)
    g_cnt = int(golden["wd_tmr_count"])

    def job(item):
        bank, f, cyc = item
        return item, runner.run(site=f.idx, cycle=cyc + shift, armed=True)

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for n, (item, r) in enumerate(ex.map(job, plan), 1):
            bank, f, cyc = item
            if campaign.i(r, "hit") != 1 or campaign.i(r, "during") == int(r["before"], 16):
                sys.exit("a force did not land: flop %d" % f.idx)
            cls, df = campaign.classify(r, golden)
            moved = int(r["wd_tmr_count"]) != g_cnt or int(r["wd_mismatch"]) > int(golden["wd_mismatch"])
            if cls == "MASKED" and moved:
                cls = "CORRECTED"
            rows.append({"bank": bank, "gl_idx": f.idx, "gl_net": f.q, "cycle": cyc,
                         "gl_cycle": cyc + shift, "cls": cls,
                         "out_ok": df["out_ok"], "done": df["done"],
                         "ann_wdog": df["ann_wdog"], "ann_sw": df["ann_sw"],
                         "ann_trap": df["ann_trap"], "persist": r["persist"],
                         "wd_mismatch": r["wd_mismatch"], "wd_tmr_count": r["wd_tmr_count"],
                         "wd_tmr_err": r["wd_tmr_err"], "cycles": df["cycles"],
                         # docs/75. The classifier samples the watchdog
                         # pins at clock edges and so cannot see a
                         # reset that came and went inside one cycle;
                         # this counts EVENTS on wdog_rst_o, which is
                         # the channel an operator would have to watch
                         # to be told. docs/74 section 10.2 established
                         # the 174 restarts from the RUN LENGTHS
                         # instead, because the counter did not exist
                         # when those sweeps ran.
                         "wdog_rst_events": r.get("wdog_rst_events", "-1"),
                         "wall": "%.1f" % r["_wall"]})
            if n % 25 == 0:
                say("  ... %d of %d", n, len(plan))
    path = os.path.join(out_dir, "records_gl_wdog.csv")
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    say("records: %s", path)
    say("")
    say("%-6s %5s %s" % ("bank", "n", "".join("%10s" % c2 for c2 in campaign.CLASSES)))
    for bank in ("A", "B", "C"):
        sub = [r for r in rows if r["bank"] == bank]
        say("%-6s %5d %s" % (bank, len(sub), "".join("%10d" % sum(1 for r in sub if r["cls"] == c2) for c2 in campaign.CLASSES)))
    say("%-6s %5d %s" % ("all", len(rows), "".join("%10d" % sum(1 for r in rows if r["cls"] == c2) for c2 in campaign.CLASSES)))
    say("mismatch cycles seen by the shadow: min %s, max %s; tmr_count after: %s",
        min(int(r["wd_mismatch"]) for r in rows), max(int(r["wd_mismatch"]) for r in rows),
        collections.Counter(r["wd_tmr_count"] for r in rows))
    say("persisted after release: %d of %d", sum(1 for r in rows if r["persist"] == "1"), len(rows))
    # docs/75's headline number: resets per corrected upset.
    ev = collections.Counter(r["wdog_rst_events"] for r in rows)
    corrected = [r for r in rows if r["cls"] == "CORRECTED"]
    reset = [r for r in corrected if r["wdog_rst_events"] not in ("0", "-1")]
    say("wdog_rst_o events: %s", dict(ev))
    if any(r["wdog_rst_events"] != "-1" for r in rows):
        say("resets per corrected upset: %d of %d corrected upsets also "
            "asserted wdog_rst_o (%s)", len(reset), len(corrected),
            "%.4f" % (len(reset) / len(corrected)) if corrected else "n/a")
    else:
        say("resets per corrected upset: NOT MEASURED -- this build's "
            "bench does not count wdog_rst_o events")
    log.close()


# =====================================================================
def cmd_instants(args):
    """Where each RTL deposit actually landed, measured.

    tb_soc_fi.v waits `while (cycles < arg_cycle) @(posedge clk)` and
    deposits a quarter cycle later; `cycles` is incremented by another
    process on the same edge, and which of the two the simulator runs
    first is a race the bench does not resolve.  Measured with a probe
    root on two of docs/43's records: x16[13] at 5756 landed at 5756,
    fetch_addr_q[4] at 9609 landed at 9610.  A gate-level replay that
    took the record's cycle at its word would then inject one design
    clock early on every record the RTL landed late, and control 5
    caught exactly that on the fetch address.  So every record is re-run
    on the RTL build with the trace root and a budget just past its
    cycle, and the row on which the injected register first differs
    from the clean run is the instant of record.  It is written beside
    the records as instants.csv and the gate-level replay uses it."""
    out_dir = os.path.abspath(args.out or args.build)
    recs = read_records(args.records)
    rtl_build = os.path.abspath(args.rtl_build)
    layout, _ = site_layout()
    by_site = {(s.stratum, s.name): (k, off) for k, s, off in layout}
    clean, _ = read_trace(args.rtl_trace)
    tmp = os.path.join(out_dir, "instants_tmp")
    os.makedirs(tmp, exist_ok=True)

    def job(k):
        r = recs[k]
        site_idx, off = by_site[(r["stratum"], r["site"])]
        cyc = int(r["cycle"])
        tr = os.path.join(tmp, "i%d.trace" % k)
        cmd = [args.rtl_vvp, "-n", os.path.join(rtl_build, "tb_soc_fi.vvp"),
               "+site=%d" % site_idx, "+bit=%s" % r["bit"], "+cycle=%d" % cyc,
               "+armed=0", "+budget=%d" % (cyc + 4), "+trace=%s" % tr]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        col = off + int(r["bit"])
        rows = [line.rstrip("\n") for line in open(tr) if line.strip()]
        os.remove(tr)
        w = len(rows[0])
        c = clean[col]
        actual = None
        for t in range(len(rows)):
            if rows[t][w - 1 - col] != c[t]:
                actual = t
                break
        return k, actual

    rows_out = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for k, actual in ex.map(job, range(len(recs))):
            r = recs[k]
            rows_out.append({"stratum": r["stratum"], "site": r["site"], "path": r["path"],
                             "bit": r["bit"], "cycle": r["cycle"],
                             "actual_row": "" if actual is None else actual,
                             "late": "" if actual is None else actual - int(r["cycle"])})
    path = os.path.join(out_dir, "instants.csv")
    with open(path, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        wr.writeheader()
        wr.writerows(rows_out)
    late = collections.Counter(r["late"] for r in rows_out)
    print("instants: %s -> %s" % (path, dict(late)))


# =====================================================================
def cmd_reconcile(args):
    build = os.path.abspath(args.build)
    out_dir = os.path.abspath(args.out or build)
    say, log = say_factory(os.path.join(out_dir, "reconcile.txt"))
    m, ent = load_map(args.map)
    flops = read_flops(os.path.join(build, "flops.tsv"))
    rec43 = read_records(args.records)
    head = read_records(args.head) if args.head else []
    gl = read_records(os.path.join(out_dir, "records_gl.csv"))
    key = lambda r: (r["path"], int(r["bit"]), int(r["cycle"]))
    # directed.csv carries site, bit and cycle but not the path, and is
    # in the input file's order; it is joined by order, with the three
    # fields asserted equal on every row.
    h = {}
    if head:
        if len(head) != len(rec43):
            sys.exit("the HEAD replay has %d rows, the record %d" % (len(head), len(rec43)))
        for r, x in zip(rec43, head):
            if (r["site"], r["bit"], r["cycle"]) != (x["site"], x["bit"], x["cycle"]):
                sys.exit("HEAD replay row out of order: %s" % (x,))
            h[key(r)] = x
    g = {key(r): r for r in gl}

    say("RECONCILIATION, docs/74: %d records of docs/43's campaign of record, "
        "%d replayed on the HEAD RTL, %d replayed on the netlist",
        len(rec43), len(head), len(gl))

    # 1. the HEAD RTL against docs/43 (the design grew; did the core's
    #    records move?)
    if head:
        say("")
        say("1. THE HEAD RTL AGAINST docs/43's RECORD (same records, same "
            "instrument, the SoC of docs/44 to docs/73 around the core)")
        moved = [(r, h[key(r)]) for r in rec43 if key(r) in h and
                 (r["armed_cls"] != h[key(r)]["armed_cls"] or
                  r["disarmed_cls"] != h[key(r)]["disarmed_cls"] or
                  r["truth"] != h[key(r)]["truth"])]
        say("   records with a HEAD replay: %d; whose armed class, held-off "
            "class or truth changed: %d", sum(1 for r in rec43 if key(r) in h),
            len(moved))
        per = collections.defaultdict(lambda: [0, 0])
        for r in rec43:
            if key(r) in h:
                per[r["stratum"]][0] += 1
        for r, hr in moved:
            per[r["stratum"]][1] += 1
        for st in targets.STRATA:
            if st in per:
                say("   %-12s %4d replayed, %3d changed", st, per[st][0], per[st][1])
        say("   held-off histogram, docs/43 then HEAD: %s / %s",
            dict(collections.Counter(r["disarmed_cls"] for r in rec43)),
            dict(collections.Counter(x["disarmed_cls"] for x in head)))
        for r, hr in moved:
            say("   %-12s %-24s bit %2s cycle %5s: docs/43 %s/%s/%s -> HEAD %s/%s/%s%s",
                r["stratum"], r["site"], r["bit"], r["cycle"],
                r["armed_cls"], r["disarmed_cls"], r["truth"],
                hr["armed_cls"], hr["disarmed_cls"], hr["truth"],
                "  (regfile corrected %s)" % hr["rf_sec"] if hr.get("rf_sec") not in (None, "", "0") else "")

    # 2. the netlist against the HEAD RTL, record for record
    say("")
    say("2. THE NETLIST AGAINST THE RTL IT WAS SYNTHESISED FROM, RECORD FOR "
        "RECORD (the RTL class is the HEAD replay's where one exists, "
        "docs/43's otherwise)")
    comparable = []
    for r in rec43:
        k = key(r)
        if k not in g:
            continue
        ref = h.get(k, r)
        comparable.append((r, ref, g[k]))
    ident_d = [t for t in comparable if t[1]["disarmed_cls"] == t[2]["gl_disarmed_cls"]]
    with_armed = [t for t in comparable if t[2]["gl_armed_cls"]]
    ident_a = [t for t in with_armed if t[1]["armed_cls"] == t[2]["gl_armed_cls"]]
    ident_t = [t for t in comparable if t[1]["truth"] == t[2]["gl_truth"]]
    say("   comparable (an RTL record with a netlist twin, replayed): %d", len(comparable))
    say("   held-off class identical: %d of %d", len(ident_d), len(comparable))
    say("   truth (OK/WRONG/DEAD) identical: %d of %d", len(ident_t), len(comparable))
    say("   armed class identical: %d of %d that were run armed", len(ident_a), len(with_armed))
    say("")
    say("   per stratum: comparable / held-off identical / armed run / armed identical")
    per = collections.defaultdict(lambda: [0, 0, 0, 0])
    for r, ref, gr in comparable:
        d = per[r["stratum"]]
        d[0] += 1
        d[1] += ref["disarmed_cls"] == gr["gl_disarmed_cls"]
        if gr["gl_armed_cls"]:
            d[2] += 1
            d[3] += ref["armed_cls"] == gr["gl_armed_cls"]
    for st in targets.STRATA:
        if st in per:
            say("   %-12s %4d %4d %4d %4d", st, *per[st])
    say("")
    say("   the two histograms over the comparable set, watchdog held off:")
    say("   %-10s %s" % ("", "".join("%10s" % c for c in campaign.CLASSES)))
    say("   %-10s %s" % ("RTL", "".join("%10d" % sum(1 for t in comparable if t[1]["disarmed_cls"] == c) for c in campaign.CLASSES)))
    say("   %-10s %s" % ("netlist", "".join("%10d" % sum(1 for t in comparable if t[2]["gl_disarmed_cls"] == c) for c in campaign.CLASSES)))
    say("")
    say("   by how the twin was identified: comparable / identical")
    per2 = collections.defaultdict(lambda: [0, 0])
    for r, ref, gr in comparable:
        per2[gr["how"]][0] += 1
        per2[gr["how"]][1] += ref["disarmed_cls"] == gr["gl_disarmed_cls"]
    for how, d in sorted(per2.items()):
        say("   %-14s %4d %4d", how, *d)

    say("")
    say("3. EVERY DISAGREEMENT (held-off class, truth, or armed class)")
    n = 0
    for r, ref, gr in comparable:
        dd = ref["disarmed_cls"] != gr["gl_disarmed_cls"]
        dt = ref["truth"] != gr["gl_truth"]
        da = bool(gr["gl_armed_cls"]) and ref["armed_cls"] != gr["gl_armed_cls"]
        if not (dd or dt or da):
            continue
        n += 1
        say("   %-12s %-22s bit %2s cycle %5s  flop #%s %s (%s%s)",
            r["stratum"], r["site"], r["bit"], r["cycle"], gr["gl_idx"],
            gr["gl_net"], gr["how"], ", inverted" if gr["pol"] == "1" else "")
        say("      RTL     held-off %-9s armed %-9s truth %-5s out_ok %s done %s rf_sec %s",
            ref["disarmed_cls"], ref["armed_cls"], ref["truth"],
            ref.get("disarmed_out_ok", ref.get("armed_out_ok")), ref.get("disarmed_done", ""),
            ref.get("disarmed_rf_sec", ref.get("rf_sec", "")))
        say("      netlist held-off %-9s armed %-9s truth %-5s out_ok %s done %s rf_sec %s "
            "persist %s ann sw/trap/alert %s/%s/%s cycles %s",
            gr["gl_disarmed_cls"], gr["gl_armed_cls"] or "-", gr["gl_truth"],
            gr["gl_disarmed_out_ok"], gr["gl_disarmed_done"], gr["gl_disarmed_rf_sec"],
            gr["gl_persist"], gr["gl_disarmed_ann_sw"], gr["gl_disarmed_ann_trap"],
            gr["gl_disarmed_ann_alert"], gr["gl_disarmed_cycles"])
    say("   disagreements: %d", n)

    # 4. what was not comparable
    say("")
    say("4. RTL RECORDS WITHOUT A NETLIST TWIN, BY SITE AND REASON")
    per3 = collections.defaultdict(lambda: collections.Counter())
    for r in rec43:
        if key(r) in g:
            continue
        e = ent.get((r["stratum"], r["site"], int(r["bit"])))
        per3[(r["stratum"], r["site"])][e["how"] if e else "not in the site table"] += 1
    tot = 0
    for (st, site), c in sorted(per3.items()):
        say("   %-12s %-26s %s", st, site, ", ".join("%s %d" % kv for kv in sorted(c.items())))
        tot += sum(c.values())
    say("   total: %d", tot)

    # 5. what the redundancy did
    say("")
    say("5. THE SYNTHESISED REDUNDANCY, AS THE NETLIST BEHAVED")
    rf = [t for t in comparable if t[0]["stratum"] in ("regfile", "regfile_ecc")]
    say("   register-file data and check-bit records replayed: %d", len(rf))
    for st in ("regfile", "regfile_ecc"):
        sub = [t for t in rf if t[0]["stratum"] == st]
        corr = sum(1 for t in sub if t[2]["gl_disarmed_cls"] == "CORRECTED")
        corr_rtl = sum(1 for t in sub if t[1]["disarmed_cls"] == "CORRECTED")
        sdc = sum(1 for t in sub if t[2]["gl_disarmed_cls"] == "SDC")
        det = sum(1 for t in sub if t[2]["gl_disarmed_cls"] == "DETECTED")
        hang = sum(1 for t in sub if t[2]["gl_disarmed_cls"] == "HANG")
        mask = sum(1 for t in sub if t[2]["gl_disarmed_cls"] == "MASKED")
        say("   %-12s n %3d: netlist CORRECTED %d (RTL %d), MASKED %d, SDC %d, "
            "DETECTED %d, HANG %d", st, len(sub), corr, corr_rtl, mask, sdc, det, hang)
    sec = [t for t in rf if int(t[2]["gl_disarmed_rf_sec"]) > 0]
    say("   records in which the shadow decoder saw a correction: %d; of "
        "those, golden answer: %d", len(sec),
        sum(1 for t in sec if t[2]["gl_disarmed_out_ok"] == "True"))
    ded = [t for t in comparable if int(t[2]["gl_disarmed_rf_ded"]) > 0]
    say("   records in which it saw an uncorrectable syndrome: %d", len(ded))
    log.close()


# =====================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "sweep", "wdog", "instants", "reconcile"])
    ap.add_argument("--build", required=True)
    ap.add_argument("--map", required=True)
    ap.add_argument("--records", default=None)
    ap.add_argument("--head", default=None)
    ap.add_argument("--rtl-golden", default=None,
                    help="the RTL clean run's log (its RECORD lines)")
    ap.add_argument("--rtl-trace", default=None)
    ap.add_argument("--gl-trace", default=None,
                    help="the clean run's gate-level trace (default: <build>/golden_gl.trace)")
    ap.add_argument("--rtl-build", default=None)
    ap.add_argument("--rtl-vvp", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--vvp", default=GL_VVP)
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--armed", choices=["all", "subset"], default="subset")
    ap.add_argument("--subset", type=int, default=100)
    ap.add_argument("--trace-check", type=int, default=0)
    ap.add_argument("--draws", type=int, default=3)
    ap.add_argument("--plan", choices=["index", "position"], default="index",
                    help="what the per-flop draw is keyed on: the "
                         "flip-flop's index in the netlist (docs/74, "
                         "exact for one netlist) or its position within "
                         "its replica bank (docs/75, the same bit in two "
                         "netlists that differ elsewhere)")
    ap.add_argument("--constants", action="store_true")
    ap.add_argument("--instants", default=None,
                    help="instants.csv from `instants`: replay at the measured row")
    ap.add_argument("--redo-from", default=None,
                    help="a records_gl.csv of an earlier pass; records already "
                         "replayed at the wanted cycle are skipped")
    ap.add_argument("--redo-all", action="store_true")
    ap.add_argument("--records-out", default=None)
    args = ap.parse_args()
    if args.cmd == "run":
        cmd_run(args)
    elif args.cmd == "sweep":
        cmd_sweep(args)
    elif args.cmd == "wdog":
        cmd_wdog(args)
    elif args.cmd == "instants":
        cmd_instants(args)
    else:
        cmd_reconcile(args)


if __name__ == "__main__":
    main()
