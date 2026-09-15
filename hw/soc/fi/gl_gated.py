#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Gate-level fault injection INSIDE the gated clock domains -- docs/82.

    gl_gated.py emit-cg  <netlist.v> <fi_gl_cg.vh>
    gl_gated.py golden   --build <dir> --rtl-golden <log>
    gl_gated.py direct   --build <dir> --arm <name> [--stop-after 64]
    gl_gated.py plan     --build <gated dir> --npu N --bus M --out plan.csv
    gl_gated.py campaign --build <dir> --arm <name> --plan plan.csv
    gl_gated.py report   --plan plan.csv --arms name=records.csv ...

WHAT IT IS FOR.  docs/76 section 14 item 2 and docs/77 section 17 item
2 ask for one experiment that neither document ran: raise a fault line
inside a block whose clock is stopped and watch whether the clock comes
back and the upset is recorded.  docs/77's T2 is the bound -- a frozen
term true in cycle N has the block clocked at the end of N+1 -- and it
was proved on an abstraction and executed at RTL on a fault-free
workload, where the case it is about is unreachable.  This is the
gate-level version, on the layouts docs/77 built, with docs/74's bench.

WHAT IS DIFFERENT FROM docs/74's CAMPAIGN, AND WHY

  * The injection primitive holds the force until the flip-flop's OWN
    clock rises (+own_clk=1, hw/soc/tb/tb_soc_fi_gl.v).  docs/74's
    force-for-one-free-clock-edge is an upset only because the cell
    samples D inside the window; a cell behind a closed gate samples
    nothing, and releasing after one free-clock edge would hand Q back
    to a primitive that still holds the old value -- a transient, not
    an upset.  A particle flips a storage node and the node stays
    flipped until the next clock; holding the force until that clock is
    the same thing seen from the cell's output.  For a flip-flop on a
    running clock the two primitives release at the same edge.

  * The sites are chosen by CLOCK DOMAIN (hw/soc/flow/clkgate_domains.py)
    and not by RTL stratum, and the arms are matched by Q-NET NAME and
    not by trace: the three netlists are three syntheses of RTL that
    differs only at the enable, and the flip-flops inside soc_npu and
    soc_bus keep their names through all three.  A flip-flop whose name
    did not survive in one arm is not injected in any.

  * Nothing here classifies CORRECTED.  The register-file shadow is not
    built for these arms (docs/74 section 6's mapping is a trace against
    the RTL, and the RTL these netlists came from is not fi-h74rtl's),
    and no site here is in the register file.  The classifier is
    campaign.py's, unchanged; a MASKED record whose accelerator cause
    word or bus-statistics counter moved is reported beside the class
    as RECORDED, the way docs/74 section 10.2 reports the watchdog's
    W6 count, and it is a bench observation and not a class.

THE CONTROLS (docs/42 section 5.1's discipline)

  1. the bench elaborated exactly the flip-flops the parse found;
  2. the clean run publishes the RTL clean run's answer and is silent;
  3. it reproduces and is identical with the watchdog held off;
  4. every force is asserted to have flipped the flip-flop (during !=
     before), and a flip-flop whose own clock never rose again is
     reported as never released rather than as persisted;
  5. the domain census reproduces the CTS log's sink counts
     (clkgate_domains.py prints them; docs/82 quotes both).
"""

import argparse
import collections
import concurrent.futures
import csv
import json
import os
import random
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import campaign                                                # noqa: E402
from gl_map import read_flops                                  # noqa: E402
from gl_netlist import plain, tmr_census_named, open_netlist, cone_flops  # noqa: E402

GL_VVP = os.path.expanduser("~/.local/opt/iverilog13/usr/bin/vvp")
SEED = 0x82F12026

# soc_npu.v at the revision the three arms were synthesised from
# (5384ee5, docs/77): P_STICKY = 2, NSTICKY = 9, C_STICKY0 = 5,
# C_Q_COR = 9, C_Q_DET = 10, C_CFG_TMR = 11, so in the 25-bit protected
# word the sticky field is bits 10:2 and the cause bank's own voter
# mismatch is sticky bit 6, word bit 8.  HEAD has grown a fifteenth
# cause since (C_EVT_TO) and is NOT what these netlists contain; the
# widths are checked against the netlist's own declarations in emit_cg.
NPU_PROT_W = 25
NPU_P_STICKY = 2
NPU_NSTICKY = 9
NPU_STICKY_CFG_TMR = 11 - 5
NPU_STICKY_Q_COR = 9 - 5
NPU_STICKY_Q_DET = 10 - 5


# =====================================================================
# the clock-gate shadow
# =====================================================================
def _vec_width(text, name):
    """Width of `wire [W-1:0] \\<name> ;` in a structural netlist, or 0."""
    m = re.search(r"^\s*wire \[(\d+):0\] \\%s ;" % re.escape(name), text, re.M)
    return int(m.group(1)) + 1 if m else 0


def emit_cg(netlist, path):
    text = open(netlist).read()
    gates = bool(re.search(r"^\s*wire clk_npu;", text, re.M)) and \
        bool(re.search(r"^\s*wire clk_bus;", text, re.M))
    npu_en = "\\g_clkgate.u_npu_cg.en_i " in text
    bus_en = ".GATE(bus_clk_en)" in text
    wa = _vec_width(text, "u_npu.g_cfg_tmr.u_cfg_a.bits")
    wb = _vec_width(text, "u_npu.g_cfg_tmr.qb")
    wc = _vec_width(text, "u_npu.g_cfg_tmr.qc")
    if not (wa == wb == wc == NPU_PROT_W):
        sys.exit("the accelerator's cause word is %d/%d/%d bits wide in %s, "
                 "expected %d" % (wa, wb, wc, netlist, NPU_PROT_W))
    bs = [_vec_width(text, "u_busstat.cnt[%d]" % k) for k in (4, 5, 6)]
    if bs != [16, 16, 16]:
        sys.exit("busstat counters 4..6 are %s bits wide, expected 16" % bs)
    L = ["// GENERATED by hw/soc/fi/gl_gated.py emit-cg -- do not edit.",
         "// netlist: %s" % netlist,
         "  assign cg_have_gates = 1'b%d;" % (1 if gates else 0)]
    if gates and npu_en and bus_en:
        L += ["  assign cg_bus_en  = dut.bus_clk_en;",
              "  assign cg_npu_en  = dut.\\g_clkgate.u_npu_cg.en_i ;",
              "  assign cg_clk_bus = dut.clk_bus;",
              "  assign cg_clk_npu = dut.clk_npu;"]
    else:
        # CLKGATE = 0: no gate, no enable; the free clock stands in so
        # that the edge counters count what that arm's flip-flops see.
        L += ["  assign cg_bus_en  = 1'b1;",
              "  assign cg_npu_en  = 1'b1;",
              "  assign cg_clk_bus = clk;",
              "  assign cg_clk_npu = clk;"]
    L += ["  wire [%d:0] cgn_qa, cgn_qb, cgn_qc, cgn_vote;" % (NPU_PROT_W - 1)]
    for k in range(NPU_PROT_W):
        L.append("  assign cgn_qa[%d] = dut.\\u_npu.g_cfg_tmr.u_cfg_a.bits [%d];" % (k, k))
        L.append("  assign cgn_qb[%d] = dut.\\u_npu.g_cfg_tmr.qb [%d];" % (k, k))
        L.append("  assign cgn_qc[%d] = dut.\\u_npu.g_cfg_tmr.qc [%d];" % (k, k))
    L += ["  assign cgn_vote = (cgn_qa & cgn_qb) | (cgn_qa & cgn_qc) | (cgn_qb & cgn_qc);",
          "  assign cg_npu_word = {%d'h0, cgn_vote};" % (32 - NPU_PROT_W),
          "  reg [31:0] cgn_mm = 32'h0;",
          "  always @(posedge clk) if (rst_n && ((cgn_qa != cgn_vote) || "
          "(cgn_qb != cgn_vote) || (cgn_qc != cgn_vote))) cgn_mm <= cgn_mm + 32'd1;",
          "  assign cg_npu_mismatch_cycles = cgn_mm;"]
    for name, k in (("cg_bs_cor", 4), ("cg_bs_det", 5), ("cg_bs_tmr", 6)):
        for b in range(16):
            L.append("  assign %s[%d] = dut.\\u_busstat.cnt[%d] [%d];" % (name, b, k, b))
    with open(path, "w") as fh:
        fh.write("\n".join(L) + "\n")
    print("wrote %s (gates: %s, enables: npu %s bus %s, cause word %d bits, "
          "busstat 3 x 16)" % (path, gates, npu_en, bus_en, NPU_PROT_W))


# =====================================================================
# running the bench
# =====================================================================
class Runner:
    def __init__(self, vvp, image, budget, rld, pre):
        self.vvp, self.image, self.budget = vvp, image, budget
        self.rld, self.pre = rld, pre

    def run(self, site=None, cycle=0, armed=True, own_clk=0, stop_after=-1,
            cgtrace=None, dumpsites=False):
        cmd = [self.vvp, "-n", self.image]
        if site is not None:
            cmd += ["+site=%d" % site, "+cycle=%d" % cycle]
        cmd += ["+armed=%d" % (1 if armed else 0), "+budget=%d" % self.budget,
                "+wdog_rld=%d" % self.rld, "+wdog_pre=%d" % self.pre,
                "+own_clk=%d" % own_clk]
        if stop_after >= 0:
            cmd += ["+stop_after=%d" % stop_after]
        if cgtrace:
            cmd += ["+cgtrace=%s" % cgtrace]
        if dumpsites:
            cmd += ["+dumpsites"]
        t0 = time.time()
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        rec = campaign.parse_record(out)
        if "_end" not in rec:
            raise RuntimeError("no complete RECORD:\n" + out[-2000:])
        rec["_raw"] = out
        rec["_wall"] = time.time() - t0
        rec["_cmd"] = " ".join(cmd)
        return rec


def say_factory(path, append=False):
    log = open(path, "a" if append else "w")

    def say(fmt, *a):
        line = fmt % a if a else fmt
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()
    return say, log


def load_golden(build, rtl_golden=None):
    """The arm's clean-run facts (`golden`).  Before `golden` has finished
    its third control, the armed clean run's own log is enough for a
    short run's window and budget; the campaign refuses that fall-back
    because it classifies against the held-off clean run."""
    p = os.path.join(build, "golden.json")
    if os.path.exists(p):
        return json.load(open(p))
    if not rtl_golden:
        sys.exit("no %s yet; run `golden` first (or pass --rtl-golden for a "
                 "direct test)" % p)
    gl = campaign.parse_record(open(os.path.join(build, "golden_gl.log")).read())
    rtl = campaign.parse_record(open(rtl_golden).read())
    rld, pre = campaign.i(rtl, "wdog_rld"), campaign.i(rtl, "wdog_pre")
    ladder = 2 * (rld + 1) * pre
    budget = max(2 * campaign.i(gl, "cycles") + 6 * ladder,
                 campaign.i(gl, "win_close") + 4 * ladder + campaign.i(gl, "cycles"))
    return {"budget": budget, "rld": rld, "pre": pre,
            "win_open": campaign.i(gl, "win_open"), "win_close": campaign.i(gl, "win_close"),
            "cycles": campaign.i(gl, "cycles"), "golden": gl, "partial": True}


def make_runner(args, g):
    image = os.path.join(os.path.abspath(args.build), "tb_soc_fi_gl.vvp")
    return Runner(args.vvp, image, g["budget"], g["rld"], g["pre"])


def ii(rec, k):
    return int(rec.get(k, "-1"))


# =====================================================================
def cmd_golden(args):
    build = os.path.abspath(args.build)
    say, log = say_factory(os.path.join(build, "gl_gated_controls.log"))
    flops = read_flops(os.path.join(build, "flops.tsv"))
    golden_rtl = campaign.parse_record(open(args.rtl_golden).read())
    rld, pre = campaign.i(golden_rtl, "wdog_rld"), campaign.i(golden_rtl, "wdog_pre")
    say("docs/82 controls: build %s", build)
    say("provenance:\n%s", open(os.path.join(build, "provenance.txt")).read().rstrip())
    probe = Runner(args.vvp, os.path.join(build, "tb_soc_fi_gl.vvp"), 200000, rld, pre)
    t0 = time.time()
    # control 1 needs the elaborated count and nothing else: ten cycles
    d = Runner(args.vvp, probe.image, 10, rld, pre).run(dumpsites=True)
    count = None
    for line in d["_raw"].splitlines():
        if line.startswith("SITECOUNT "):
            count = int(line.split()[1])
    if count != len(flops):
        sys.exit("the bench elaborated %s sites, flops.tsv lists %d" % (count, len(flops)))
    say("control 1: the bench elaborated %d flip-flops, the netlist parse lists %d "
        "(%.1f s)", count, len(flops), d["_wall"])
    golden = probe.run(armed=True, cgtrace=os.path.join(build, "golden_cg.trace"))
    open(os.path.join(build, "golden_gl.log"), "w").write(golden["_raw"])
    if not campaign.completed(golden):
        sys.exit("the gate-level clean run did not complete:\n" + golden["_raw"][-2000:])
    if campaign.wdog_fired(golden) or campaign.i(golden, "traps") \
            or campaign.alert_seen(golden) or campaign.i(golden, "console_framing"):
        sys.exit("the clean run is not silent in every channel")
    a_gl = campaign.answer(golden)
    a_rtl = campaign.answer(golden_rtl)
    if a_gl != a_rtl:
        sys.exit("the gate-level clean run does not publish the RTL clean run's "
                 "answer:\n  gate level %s\n  RTL        %s" % (a_gl, a_rtl))
    say("control 2: gate-level clean run %d cycles (RTL %d), sig %s, %d console "
        "characters, hash %s, window %d..%d (RTL %d..%d); the published answer "
        "is identical to the RTL clean run's in every compared field (%.1f s)",
        campaign.i(golden, "cycles"), campaign.i(golden_rtl, "cycles"),
        golden["sig"], campaign.i(golden, "console_chars"), golden["console_hash"],
        campaign.i(golden, "win_open"), campaign.i(golden, "win_close"),
        campaign.i(golden_rtl, "win_open"), campaign.i(golden_rtl, "win_close"),
        golden["_wall"])
    say("           clock-gate shadow: %s (gates %s); cause word %s, voter "
        "mismatch cycles %s; busstat NPUCOR/NPUDET/NPUTMR %s/%s/%s",
        "present" if golden.get("cg_shadow") == "1" else "ABSENT",
        golden.get("cg_gates"), golden.get("cg_npu_word"), golden.get("cg_npu_mismatch"),
        golden.get("cg_bs_cor"), golden.get("cg_bs_det"), golden.get("cg_bs_tmr"))
    again = probe.run(armed=True)
    if campaign.answer(again) != a_gl or campaign.i(again, "cycles") != campaign.i(golden, "cycles"):
        sys.exit("the clean run is not reproducible")
    dis = probe.run(armed=False)
    open(os.path.join(build, "golden_gl_disarmed.log"), "w").write(dis["_raw"])
    if campaign.answer(dis) != a_gl:
        sys.exit("the clean run differs with the watchdog held off")
    say("control 3: the clean run reproduces exactly, and is identical with the "
        "watchdog held off (%d cycles)", campaign.i(dis, "cycles"))
    timeout_clk = (rld + 1) * pre
    ladder = 2 * timeout_clk
    win_close = campaign.i(golden, "win_close")
    budget = 2 * campaign.i(golden, "cycles") + 6 * ladder
    need = win_close + 4 * ladder + campaign.i(golden, "cycles")
    budget = max(budget, need)
    say("           budget %d cycles, campaign.py's formula on the gate-level "
        "clean run (ladder %d from reload %d and prescale %d)", budget, ladder, rld, pre)
    # the enable trace: how often each gate is shut on the clean run
    tr = [line.strip() for line in open(os.path.join(build, "golden_cg.trace")) if line.strip()]
    n = len(tr)
    npu_low = sum(1 for x in tr if x[0] == "0")
    bus_low = sum(1 for x in tr if x[1] == "0")
    lo, hi = campaign.i(golden, "win_open"), campaign.i(golden, "win_close")
    win = tr[lo:hi]
    say("           enable trace: %d cycles; npu enable low %d (%.4f %%), bus enable "
        "low %d (%.4f %%); inside the window %d..%d: npu low %d of %d, bus low %d of %d",
        n, npu_low, 100.0 * npu_low / n, bus_low, 100.0 * bus_low / n, lo, hi,
        sum(1 for x in win if x[0] == "0"), len(win),
        sum(1 for x in win if x[1] == "0"), len(win))
    # sleep intervals of the accelerator's enable, as docs/77 counts them
    wakes = sum(1 for k in range(1, n) if tr[k - 1][0] == "0" and tr[k][0] == "1")
    bwakes = sum(1 for k in range(1, n) if tr[k - 1][1] == "0" and tr[k][1] == "1")
    first_low = next((k for k, x in enumerate(tr) if x[0] == "0"), -1)
    say("           npu enable: first low at cycle %d, wakes after that %d; bus "
        "enable wakes %d", first_low, wakes, bwakes)
    json.dump({"budget": budget, "rld": rld, "pre": pre,
               "win_open": lo, "win_close": hi,
               "cycles": campaign.i(golden, "cycles"),
               "golden": {k: v for k, v in golden.items() if not k.startswith("_")},
               "golden_disarmed": {k: v for k, v in dis.items() if not k.startswith("_")},
               "npu_first_low": first_low, "npu_wakes": wakes, "bus_wakes": bwakes,
               "npu_low": npu_low, "bus_low": bus_low, "trace_cycles": n},
              open(os.path.join(build, "golden.json"), "w"), indent=1)
    say("wall: %.1f s for four clean runs", time.time() - t0)
    log.close()


# =====================================================================
ANON_POS = 100   # anonymous replica flip-flops are keyed from here up


def cause_bank_sites(build, flops):
    """The accelerator's cause-bank replica flip-flops, by the voter's
    fan-in cone (docs/75's instrument), each keyed by the physical bit
    it holds where the netlist says which: a NAMED replica flip-flop
    (`u_cfg_a.bits [k]`, `qb [k]`, `qc [k]`) is bit k of its replica in
    every arm, because the three netlists were mapped from one
    soc_tmr_bank.v at one width.  An anonymous one (the flip-flop yosys
    built behind an inverter or into the mixing, `_NNNNN_`) is keyed
    ANON_POS plus its ordinal in cone order, which is deterministic for
    a netlist and is NOT the same physical bit from one arm to the next;
    the direct test says which sites paired by name and which did not.

    docs/75 section 8.1 keyed the watchdog's replicas on the lowest word
    bit each feeds and checked that a named flip-flop's name agrees with
    it.  That check does not transfer to this bank: replicas B and C
    carry MIX = 1, so one stored bit reaches several word bits through
    mix_dec's XOR tree and the lowest of them is generally below the
    bit's own index (bank B's `bits [1]` reaches word bit 0 first).  The
    cone is still what says a flip-flop IS a replica bit; it is not what
    says which one."""
    netlist = open(os.path.join(build, "provenance.txt")).read().split("\n")[0].split()[1]
    nl = open_netlist(netlist)
    by_inst = {f["inst"]: f for f in flops}
    out = []
    for row in tmr_census_named(netlist, "npu", nl=nl):
        bank = row["bank"][-1]  # a, b, c
        pos = {}
        for k in range(row["width"]):
            for inst in cone_flops(nl.driver, nl.cells, "\\%s [%d]" % (row["net"], k)):
                pos.setdefault(inst, k)
        anon = 0
        for inst, k in sorted(pos.items(), key=lambda kv: (kv[1], kv[0])):
            f = by_inst[inst]
            name, bit = plain(f["q"])
            if not name.startswith("_") and bit is not None:
                out.append((bank.upper(), bit, f, k))
            else:
                out.append((bank.upper(), ANON_POS + anon, f, k))
                anon += 1
    return out


def cmd_direct(args):
    build = os.path.abspath(args.build)
    out_dir = os.path.abspath(args.out or build)
    say, log = say_factory(os.path.join(out_dir, "gl_direct.log"))
    flops = read_flops(os.path.join(build, "flops.tsv"))
    g = load_golden(build, args.rtl_golden)
    runner = make_runner(args, g)
    sites = cause_bank_sites(build, flops)
    if args.banks:
        sites = [s for s in sites if s[0] in args.banks.upper()]
    if args.limit:
        # the first N NAMED bits of each bank, so that two arms limited
        # the same way inject the same physical bits; the anonymous
        # flip-flops are keyed from ANON_POS and are left out by this
        sites = [s for s in sites if s[1] < args.limit]
    per_bank = collections.Counter(b for b, _, _, _ in sites)
    named = collections.Counter(b for b, k, _, _ in sites if k < ANON_POS)
    say("docs/82 direct test (T2), arm %s, build %s", args.arm, build)
    say("cause-bank replica flip-flops by voter cone: %s (keyed by name %s, "
        "by cone ordinal %s)", dict(per_bank), dict(named),
        {b: per_bank[b] - named.get(b, 0) for b in per_bank})
    # the MIX property, reported rather than asserted (cause_bank_sites)
    say("named flip-flops whose lowest cone bit is below their own bit: %d of %d",
        sum(1 for b, k, f, ck in sites if k < ANON_POS and ck != k),
        sum(1 for b, k, f, ck in sites if k < ANON_POS))
    sites = [(b, k, f) for b, k, f, _ in sites]
    lo, hi = g["win_open"], g["win_close"]
    if args.early:
        # A run cut 64 edges after the injection still has to reach the
        # injection edge, so its cost is the edge index; the accelerator
        # is asleep for the whole window (cmd_golden measures it), and
        # nothing about T2 depends on where in the program the upset
        # lands, so the draw is confined to the window's first cycles.
        hi = min(hi, lo + args.early)
    plan = []
    for b, k, f in sites:
        rng = random.Random("%d:direct:%s:%d" % (SEED, b, k))
        for d in range(args.draws):
            plan.append((b, k, f, rng.randrange(lo, hi)))
    say("plan: %d flip-flops x %d draw(s) = %d injections, watchdog held off, "
        "own_clk=%d, stop_after=%d, cycles drawn in %d..%d keyed on (bank, bit)",
        len(sites), args.draws, len(plan), args.own_clk, args.stop_after, lo, hi)

    def job(item):
        b, k, f, cyc = item
        return item, runner.run(site=f["idx"], cycle=cyc, armed=False,
                                own_clk=args.own_clk, stop_after=args.stop_after)

    rows = []
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for n, (item, r) in enumerate(ex.map(job, plan), 1):
            b, k, f, cyc = item
            if ii(r, "hit") != 1 or ii(r, "during") == int(r["before"], 16):
                sys.exit("a force did not land: flop %d" % f["idx"])
            rows.append(row_of(args.arm, "cause_%s" % b, k, f, cyc, r, g))
            if n % 25 == 0:
                say("  ... %d of %d (%.0f s)", n, len(plan), time.time() - t0)
    path = os.path.join(out_dir, args.records_out or "records_direct.csv")
    write_rows(path, rows)
    say("records: %s", path)
    summarise_direct(say, rows)
    say("wall: %.1f s for %d simulations at %d jobs (contended)",
        time.time() - t0, len(plan), args.jobs)
    log.close()


def row_of(arm, kind, pos, f, cyc, r, g, cls=None, df=None):
    word_b = int(r.get("cg_npu_word_before", "0"), 16)
    word_a = int(r.get("cg_npu_word", "0"), 16)
    sticky_b = (word_b >> NPU_P_STICKY) & ((1 << NPU_NSTICKY) - 1)
    sticky_a = (word_a >> NPU_P_STICKY) & ((1 << NPU_NSTICKY) - 1)
    own_first = ii(r, "own_first")
    npu_first = ii(r, "cg_npu_first")
    row = {"arm": arm, "kind": kind, "pos": pos, "gl_idx": f["idx"], "gl_net": f["q"],
           "cycle": cyc, "hit": r["hit"], "before": int(r["before"], 16),
           "during": r["during"], "after": int(r["after"], 16),
           "persist": r["persist"], "released": r.get("released", ""),
           "own_first": own_first,
           "own_latency": (own_first - cyc) if own_first >= 0 else -1,
           "own_edges": ii(r, "own_edges"),
           "npu_first": npu_first,
           "npu_latency": (npu_first - cyc) if npu_first >= 0 else -1,
           "npu_edges": ii(r, "cg_npu_edges"),
           "bus_first": ii(r, "cg_bus_first"), "bus_edges": ii(r, "cg_bus_edges"),
           "en_before": r.get("cg_en_before", ""), "en_during": r.get("cg_en_during", ""),
           "word_before": "%07x" % word_b, "word_after": "%07x" % word_a,
           "sticky_before": "%03x" % sticky_b, "sticky_after": "%03x" % sticky_a,
           "sticky_new": "%03x" % (sticky_a & ~sticky_b),
           "cfg_tmr_recorded": int(bool((sticky_a >> NPU_STICKY_CFG_TMR) & 1)),
           "npu_mismatch": ii(r, "cg_npu_mismatch"),
           "bs_cor_delta": ii(r, "cg_bs_cor") - ii(r, "cg_bs_cor_before"),
           "bs_det_delta": ii(r, "cg_bs_det") - ii(r, "cg_bs_det_before"),
           "bs_tmr_delta": ii(r, "cg_bs_tmr") - ii(r, "cg_bs_tmr_before"),
           "cycles": ii(r, "cycles"), "done": r["done"],
           "wall": "%.1f" % r["_wall"]}
    if cls is not None:
        row.update({"cls": cls,
                    "truth": "OK" if df["out_ok"] else ("WRONG" if df["done"] else "DEAD"),
                    "out_ok": df["out_ok"], "ann_sw": df["ann_sw"], "ann_trap": df["ann_trap"],
                    "ann_alert": df["ann_alert"], "ann_wdog": df["ann_wdog"],
                    "recorded": int(row["sticky_new"] != "000" or row["bs_cor_delta"] > 0
                                    or row["bs_det_delta"] > 0 or row["bs_tmr_delta"] > 0)})
    return row


def write_rows(path, rows):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def summarise_direct(say, rows):
    say("")
    say("%-8s %4s %s" % ("bank", "n", "  latency of the block's own clock after the force (edges), "
                                     "-1 = never clocked again"))
    for kind in sorted(set(r["kind"] for r in rows)):
        sub = [r for r in rows if r["kind"] == kind]
        lat = collections.Counter(r["own_latency"] for r in sub)
        say("%-8s %4d %s" % (kind, len(sub), "  ".join("%s:%d" % kv for kv in sorted(lat.items()))))
    say("")
    say("recorded in the cause word (C_CFG_TMR sticky set after): %d of %d",
        sum(r["cfg_tmr_recorded"] for r in rows), len(rows))
    say("busstat NPUTMR increments per injection: %s",
        dict(collections.Counter(r["bs_tmr_delta"] for r in rows)))
    say("voter mismatch cycles seen: %s", dict(collections.Counter(r["npu_mismatch"] for r in rows)))
    say("released (own clock rose again): %d of %d; persisted after release: %d",
        sum(1 for r in rows if r["released"] == "1"), len(rows),
        sum(1 for r in rows if r["released"] == "1" and r["persist"] == "1"))
    say("enable {npu,bus} before the force: %s; one delta after it: %s",
        dict(collections.Counter(r["en_before"] for r in rows)),
        dict(collections.Counter(r["en_during"] for r in rows)))
    say("gated-net clk_npu: first edge after the force at latency %s",
        dict(collections.Counter(r["npu_latency"] for r in rows)))


# =====================================================================
def read_domains(build):
    out = {}
    with open(os.path.join(build, "domains.tsv")) as fh:
        hdr = fh.readline().rstrip("\n").split("\t")
        for line in fh:
            row = dict(zip(hdr, line.rstrip("\n").split("\t")))
            out[int(row["idx"])] = row
    return out


def cmd_plan(args):
    """Sites and cycles, drawn once from the GATED arm and applied to every
    arm by Q-net name."""
    build = os.path.abspath(args.build)
    g = load_golden(build, args.rtl_golden)
    flops = read_flops(os.path.join(build, "flops.tsv"))
    dom = read_domains(build)
    tr = [line.strip() for line in open(os.path.join(build, "golden_cg.trace")) if line.strip()]
    lo, hi = g["win_open"], g["win_close"]
    public = lambda f: not re.match(r"^(_\d+_|net\d+)$", plain(f["q"])[0])
    npu = [f for f in flops if dom[f["idx"]]["domain"] == "clk_npu" and public(f)]
    bus = [f for f in flops if dom[f["idx"]]["domain"] == "clk_bus" and public(f)]
    # the accelerator is asleep for the whole window on this workload;
    # the plan asserts it rather than assuming it
    npu_awake = [k for k in range(lo, hi) if tr[k][0] == "1"]
    bus_asleep = [k for k in range(lo, hi) if tr[k][1] == "0"]
    rows = []
    rng = random.Random("%d:plan:npu" % SEED)
    for f in rng.sample(npu, min(args.npu, len(npu))):
        c = random.Random("%d:plan:npu:%s" % (SEED, f["q"])).randrange(lo, hi)
        rows.append({"kind": "npu", "gl_net": f["q"], "cycle": c,
                     "asleep": int(tr[c][0] == "0")})
    rng = random.Random("%d:plan:bus" % SEED)
    for f in rng.sample(bus, min(args.bus, len(bus))):
        c = random.Random("%d:plan:bus:%s" % (SEED, f["q"])).choice(bus_asleep)
        rows.append({"kind": "bus", "gl_net": f["q"], "cycle": c, "asleep": 1})
    write_rows(args.out, rows)
    print("plan: %d npu sites of %d public clk_npu flip-flops (%d awake cycles in "
          "the window %d..%d), %d bus sites of %d public clk_bus flip-flops at "
          "cycles drawn from %d asleep cycles; %s"
          % (sum(1 for r in rows if r["kind"] == "npu"), len(npu), len(npu_awake),
             lo, hi, sum(1 for r in rows if r["kind"] == "bus"), len(bus),
             len(bus_asleep), args.out))


def cmd_campaign(args):
    build = os.path.abspath(args.build)
    out_dir = os.path.abspath(args.out or build)
    say, log = say_factory(os.path.join(out_dir, "gl_campaign_gated.log"))
    flops = read_flops(os.path.join(build, "flops.tsv"))
    g = load_golden(build)
    golden = g["golden_disarmed"]
    runner = make_runner(args, g)
    by_name = {}
    for f in flops:
        by_name.setdefault(f["q"].strip(), f)
    plan = list(csv.DictReader(open(args.plan)))
    todo, missing = [], []
    for p in plan:
        f = by_name.get(p["gl_net"].strip())
        if f is None:
            missing.append(p["gl_net"])
            continue
        todo.append((p, f))
    say("docs/82 campaign, arm %s, build %s: %d planned sites, %d present by "
        "Q-net name, %d absent%s", args.arm, build, len(plan), len(todo), len(missing),
        (": " + ", ".join(missing)) if missing else "")
    say("watchdog held off, own_clk=%d, budget %d", args.own_clk, g["budget"])
    if args.limit:
        todo = todo[:args.limit]
        say("limited to the first %d", len(todo))

    def job(item):
        p, f = item
        return item, runner.run(site=f["idx"], cycle=int(p["cycle"]), armed=False,
                                own_clk=args.own_clk)

    rows = []
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for n, (item, r) in enumerate(ex.map(job, todo), 1):
            p, f = item
            if ii(r, "hit") != 1 or ii(r, "during") == int(r["before"], 16):
                sys.exit("a force did not land: flop %d" % f["idx"])
            cls, df = campaign.classify(r, golden)
            rows.append(row_of(args.arm, p["kind"], p.get("asleep", ""), f,
                               int(p["cycle"]), r, g, cls, df))
            if n % 10 == 0:
                say("  ... %d of %d (%.0f s)", n, len(todo), time.time() - t0)
            # written incrementally so a killed run keeps its records
            write_rows(os.path.join(out_dir, "records_gated.csv"), rows)
    path = os.path.join(out_dir, "records_gated.csv")
    write_rows(path, rows)
    say("records: %s", path)
    summarise_campaign(say, rows)
    say("wall: %.1f s for %d simulations at %d jobs (contended); per simulation "
        "min %.1f, median %.1f, max %.1f",
        time.time() - t0, len(rows), args.jobs,
        min(float(r["wall"]) for r in rows),
        sorted(float(r["wall"]) for r in rows)[len(rows) // 2],
        max(float(r["wall"]) for r in rows))
    log.close()


def summarise_campaign(say, rows):
    say("")
    say("%-6s %4s %s %s" % ("kind", "n", "".join("%10s" % c for c in campaign.CLASSES),
                            "  recorded  released  own-latency"))
    for kind in ("npu", "bus"):
        sub = [r for r in rows if r["kind"] == kind]
        if not sub:
            continue
        lat = collections.Counter(r["own_latency"] for r in sub)
        say("%-6s %4d %s %9d %9d  %s" % (
            kind, len(sub),
            "".join("%10d" % sum(1 for r in sub if r["cls"] == c) for c in campaign.CLASSES),
            sum(r["recorded"] for r in sub),
            sum(1 for r in sub if r["released"] == "1"),
            " ".join("%s:%d" % kv for kv in sorted(lat.items()))))


# =====================================================================
def cmd_report(args):
    plan = list(csv.DictReader(open(args.plan)))
    arms = collections.OrderedDict()
    for spec in args.arms:
        name, path = spec.split("=", 1)
        arms[name] = {(r["gl_net"].strip(), int(r["cycle"])): r
                      for r in csv.DictReader(open(path))}
    say, log = say_factory(args.out) if args.out else (lambda f, *a: print(f % a if a else f), None)
    key = lambda p: (p["gl_net"].strip(), int(p["cycle"]))
    common = [p for p in plan if all(key(p) in a for a in arms.values())]
    say("docs/82 report: %d planned records, %d run on every arm (%s)",
        len(plan), len(common), ", ".join(arms))
    for kind in ("npu", "bus"):
        sub = [p for p in common if p["kind"] == kind]
        if not sub:
            continue
        say("")
        say("%s: %d records" % (kind, len(sub)))
        say("  %-12s %s %s" % ("arm", "".join("%10s" % c for c in campaign.CLASSES),
                               "  recorded  released  never-clocked"))
        for name, a in arms.items():
            rs = [a[key(p)] for p in sub]
            say("  %-12s %s %9d %9d %9d" % (
                name, "".join("%10d" % sum(1 for r in rs if r["cls"] == c) for c in campaign.CLASSES),
                sum(int(r["recorded"]) for r in rs),
                sum(1 for r in rs if r["released"] == "1"),
                sum(1 for r in rs if r["own_latency"] == "-1")))
        names = list(arms)
        diff = [p for p in sub if len(set(arms[n][key(p)]["cls"] for n in names)) > 1]
        say("  class differs between arms on %d of %d", len(diff), len(sub))
        for p in diff:
            say("    %-60s cycle %5s: %s", p["gl_net"], p["cycle"],
                "  ".join("%s %s/%s rec %s lat %s" % (
                    n, arms[n][key(p)]["cls"], arms[n][key(p)]["truth"],
                    arms[n][key(p)]["recorded"], arms[n][key(p)]["own_latency"]) for n in names))
        rdiff = [p for p in sub if len(set(arms[n][key(p)]["recorded"] for n in names)) > 1]
        say("  RECORDED differs between arms on %d of %d", len(rdiff), len(sub))
        for p in rdiff:
            say("    %-60s cycle %5s: %s", p["gl_net"], p["cycle"],
                "  ".join("%s rec %s sticky_new %s bs %s/%s/%s lat %s" % (
                    n, arms[n][key(p)]["recorded"], arms[n][key(p)]["sticky_new"],
                    arms[n][key(p)]["bs_cor_delta"], arms[n][key(p)]["bs_det_delta"],
                    arms[n][key(p)]["bs_tmr_delta"], arms[n][key(p)]["own_latency"]) for n in names))
    if log:
        log.close()


# =====================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["emit-cg", "golden", "direct", "plan", "campaign", "report"])
    ap.add_argument("pos", nargs="*")
    ap.add_argument("--build", default=None)
    ap.add_argument("--arm", default="arm")
    ap.add_argument("--rtl-golden", default=None)
    ap.add_argument("--plan", default=None)
    ap.add_argument("--arms", nargs="*", default=[])
    ap.add_argument("--out", default=None)
    ap.add_argument("--vvp", default=GL_VVP)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--draws", type=int, default=1)
    ap.add_argument("--own-clk", type=int, default=1)
    ap.add_argument("--stop-after", type=int, default=64)
    ap.add_argument("--npu", type=int, default=60)
    ap.add_argument("--bus", type=int, default=20)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--banks", default="",
                    help="direct: restrict to these replica banks, e.g. A or ABC")
    ap.add_argument("--early", type=int, default=0,
                    help="direct: draw cycles from the first N cycles of the window")
    ap.add_argument("--records-out", default=None)
    args = ap.parse_args()
    if args.cmd == "emit-cg":
        emit_cg(args.pos[0], args.pos[1])
    elif args.cmd == "golden":
        cmd_golden(args)
    elif args.cmd == "direct":
        cmd_direct(args)
    elif args.cmd == "plan":
        cmd_plan(args)
    elif args.cmd == "campaign":
        cmd_campaign(args)
    else:
        cmd_report(args)


if __name__ == "__main__":
    main()
