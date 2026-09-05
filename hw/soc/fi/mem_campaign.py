#!/usr/bin/env python3
"""The memory fault-injection campaign of docs/67: draw by REGION of the
program's own link map, run, classify -- on the hardened SoC and on the
same SoC with the memory codec off.

    hw/soc/fi/mem_campaign.py --build hw/soc/out/s67-fi-h1 \
        [--counterfactual hw/soc/out/s67-fi-h0] [--draws 40] [--jobs 18]

`hw/soc/flow/fi_core.sh` builds and elaborates once per configuration
(SOC_MEM_HARDEN=1, the design; SOC_MEM_HARDEN=0, the counterfactual;
SOC_SCRUB_IVL=0, the design with the scrubber walking every second idle
cycle). This drives `vvp` on those images with +mem/+midx/+mbit/+cycle
and classifies what comes back, from the RECORD lines
hw/soc/tb/tb_soc_fi.v prints and from nothing in the RTL.

WHY THE STRATA ARE REGIONS AND NOT MEMORIES

docs/41 section 3.1's criterion -- persistence times silence -- gives
four different answers for four kinds of word in the same 72 KiB, and a
uniform rate over the whole would describe none of them:

    ROM.text     an instruction. Never rewritten (nothing writes the
                 ROM), executed repeatedly, so an upset is persistent and
                 shows as a wrong instruction: a trap if it decodes as
                 illegal, a silently wrong answer if it does not.
    ROM.rodata   a constant the program reads. Persistent; silent.
    RAM.data     .data and .bss: the program's variables, including the
                 four words it publishes its answer in. Rewritten by the
                 program at its own cadence, which for a loop counter is
                 every iteration and for a result word once.
    RAM.stack    the live stack. Rewritten on every call; an upset in a
                 saved register or a return address survives exactly
                 until the frame is popped.
    RAM.pmpbuf   the PMP test buffer: written once, read to check.
    RAM.unused   a word the program never touches. An upset there has no
                 consequence at all, and the check bits stored beside it
                 are what the scrubber spends its walk on.
    ROM.unused   the ROM rows above the image. Fetched by nothing.
    RAM.chk      a CHECK bit of a used RAM row (the hardened build only):
    ROM.chk      state the codec ADDED, which an upset can hit exactly as
                 it can hit the data -- docs/58's mtime_chk argument.

The region boundaries are read from the ELF the build linked, not
written down, so a change to the workload moves the strata with it.

WHAT DECIDES RIGHT FROM WRONG. The golden run, always -- an undeposited
run of the same image, recorded once and re-recorded to prove it
reproduces -- exactly as hw/soc/fi/campaign.py does for the core. The
classes are docs/16 section 1.6's five, one per injection, in its
order; CORRECTED means the answer matched golden AND one of the SCRUB
block's counters moved, which is the only thing in this design that can
make the class reachable for a memory upset.

THE COUNTERFACTUAL IS THE SAME DRAWS ON THE UNHARDENED BUILD. The seed
is derived per (stratum, index), so the (region, word, bit, cycle) of
draw k is the same in both builds -- except the check-bit strata, which
the unhardened build does not have. docs/58 section 8.4's calibration is
the rule: the strata the codec does not touch have to come back
identical between the two builds, or the delta is a difference of two
things.

WHAT THIS CAMPAIGN DOES NOT COVER

  * RTL, single-bit, storage only: no transient in the codec's own
    gates, no multi-bit strike, no gate-level netlist. The uncorrectable
    class is reached only by the directed tests in test_soc_mem.py.
  * One workload (docs/42's dense kernel), one seed, one draw count.
    Every number is conditional on an upset having landed in the
    measured window. docs/16 section 7.5.
  * The scrub interval at which the design ships is measured in ONE
    build and the every-idle-cycle setting in another; nothing between
    them is.
  * The counters are read hierarchically, not over the bus.
"""

import argparse
import collections
import concurrent.futures
import csv
import os
import random
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign as core                                # noqa: E402

SEED = 0x67ECC001
CLASSES = ("HANG", "DETECTED", "SDC", "CORRECTED", "MASKED")

RAM_BASE, ROM_BASE = 0x00000000, 0xC0000000
RAM_WORDS, ROM_WORDS = 8192, 2048     # regmap/memmap.yaml, docs/67
STACK_WORDS = 256                      # the top 1 KiB of RAM, the live stack

Region = collections.namedtuple("Region", "name mem lo hi chk")
# mem: 0 RAM, 1 ROM; lo..hi: word indices inside the region; chk: the
# stratum injects into check bits (32..63 RAM, 32..38 ROM) of the same
# rows rather than into data bits.


# =====================================================================
# the strata, from the ELF
# =====================================================================
def sections(elf, readelf):
    out = subprocess.run([readelf, "-S", "-W", elf], capture_output=True,
                         text=True, check=True).stdout
    secs = {}
    for line in out.splitlines():
        m = re.match(r"\s*\[\s*\d+\]\s+(\.\S+)\s+\S+\s+([0-9a-f]{8})\s+"
                     r"[0-9a-f]+\s+([0-9a-f]{6})", line)
        if m:
            secs[m.group(1)] = (int(m.group(2), 16), int(m.group(3), 16))
    return secs


def strata(elf, readelf, hardened):
    secs = sections(elf, readelf)

    def words(name, base):
        addr, size = secs[name]
        return (addr - base) // 4, (addr - base + size + 3) // 4 - 1

    t0, t1 = words(".text", ROM_BASE)
    v0, v1 = words(".trapvec", ROM_BASE)
    r0, r1 = words(".rodata", ROM_BASE)
    d_lo = min(words(".data", RAM_BASE)[0], words(".bss", RAM_BASE)[0])
    d_hi = max(words(".bss", RAM_BASE)[1], words(".data", RAM_BASE)[1])
    p0, p1 = words(".pmpbuf", RAM_BASE)
    out = [
        Region("ROM.text",   1, t0, v1, False),
        Region("ROM.rodata", 1, r0, r1, False),
        Region("ROM.unused", 1, r1 + 1, ROM_WORDS - 1, False),
        Region("RAM.data",   0, d_lo, d_hi, False),
        Region("RAM.pmpbuf", 0, p0, p1, False),
        Region("RAM.stack",  0, RAM_WORDS - STACK_WORDS, RAM_WORDS - 1, False),
        Region("RAM.unused", 0, p1 + 1, RAM_WORDS - STACK_WORDS - 1, False),
    ]
    if hardened:
        out += [
            Region("RAM.chk", 0, d_lo, d_hi, True),          # the data rows' check bits
            Region("ROM.chk", 1, t0, v1, True),              # the code rows' check bits
        ]
    return out, secs


def draws(region, n, window):
    """n (word, bit, cycle) triples, seeded per (region, index) so the
    hardened and unhardened builds draw the same points."""
    lo, hi = window
    nbits = (32 if region.mem == 0 else 7) if region.chk else 32
    base_bit = 32 if region.chk else 0
    out = []
    for k in range(n):
        rng = random.Random("%d:%s:%d" % (SEED, region.name, k))
        word = rng.randrange(region.lo, region.hi + 1)
        bit = base_bit + rng.randrange(nbits)
        out.append((word, bit, rng.randrange(lo, hi)))
    return out


# =====================================================================
# one run
# =====================================================================
class Runner:
    def __init__(self, vvp, image, budget):
        self.vvp, self.image, self.budget = vvp, image, budget

    def run(self, mem=None, midx=0, mbit=0, cycle=0):
        cmd = [self.vvp, self.image, "+armed=1", "+budget=%d" % self.budget]
        if mem is not None:
            cmd += ["+mem=%d" % mem, "+midx=%d" % midx, "+mbit=%d" % mbit,
                    "+cycle=%d" % cycle]
        # Bytes, decoded with replacement: a run whose program was made
        # to print garbage -- an instruction word with one flipped bit,
        # on the unhardened build -- puts bytes on the console that are
        # not UTF-8, and the console tail is in the RECORD. The core
        # campaign never met one; this one did, on its first
        # counterfactual run, and lost 280 records to a decode error.
        out = subprocess.run(cmd, capture_output=True,
                             check=True).stdout.decode("utf-8", "replace")
        rec = core.parse_record(out)
        if "_end" not in rec:
            raise RuntimeError("no complete RECORD:\n" + out[-2000:])
        return rec


def scrub_counts(rec):
    return {k: core.i(rec, "scr_" + k)
            for k in ("ramsec", "ramrd", "ramded", "romsec", "romrd", "romded")}


def classify(rec, golden):
    """docs/16 section 1.6's five, for a memory upset."""
    ann = (core.wdog_fired(rec) or core.sw_flagged(rec, golden)
           or core.trap_seen(rec, golden) or core.alert_seen(rec))
    out_ok = core.completed(rec) and core.answer(rec) == core.answer(golden)
    sc = scrub_counts(rec)
    corrected = sc["ramsec"] + sc["ramrd"] + sc["romsec"] + sc["romrd"] > 0
    uncorrectable = sc["ramded"] + sc["romded"] > 0
    if not core.completed(rec) and not ann:
        cls = "HANG"
    elif ann:
        cls = "DETECTED"
    elif not out_ok:
        cls = "SDC"
    elif corrected:
        cls = "CORRECTED"
    else:
        cls = "MASKED"
    return cls, {"out_ok": out_ok, "done": core.completed(rec),
                 "ann_trap": core.trap_seen(rec, golden),
                 "ann_wdog": core.wdog_fired(rec),
                 "ann_sw": core.sw_flagged(rec, golden),
                 "corrected": corrected, "uncorrectable": uncorrectable,
                 "cycles": core.i(rec, "cycles"), **sc}


# =====================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True,
                    help="directory fi_core.sh wrote for the design "
                         "(SOC_MEM_HARDEN=1)")
    ap.add_argument("--tag", default="h1",
                    help="label for the records file, e.g. h1, h1s, h0")
    ap.add_argument("--unhardened", action="store_true",
                    help="the build was made with SOC_MEM_HARDEN=0: no "
                         "check-bit strata, and CORRECTED is unreachable")
    ap.add_argument("--draws", type=int, default=40)
    ap.add_argument("--jobs", type=int,
                    default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    build = os.path.abspath(args.build)
    out_dir = os.path.abspath(args.out or build)
    soc = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    printed = subprocess.run(
        ["make", "--no-print-directory", "-f",
         os.path.join(soc, "tools.soc.mk"), "printvars"],
        capture_output=True, text=True, check=True).stdout
    vvp = None
    for line in printed.splitlines():
        if line.startswith("VVP="):
            vvp = line.split("=", 1)[1].strip().strip('"')
    readelf = os.path.join(soc, "tools", "rvgcc", "bin", "riscv-none-elf-readelf")
    image = os.path.join(build, "tb_soc_fi.vvp")
    elf = os.path.join(build, "fi_workload.elf")
    for p in (vvp, image, elf, readelf):
        if not p or not os.path.exists(p):
            sys.exit("missing %s" % p)

    log = open(os.path.join(out_dir, "mem_campaign_%s.log" % args.tag), "w")

    def say(fmt, *a):
        line = fmt % a if a else fmt
        print(line)
        log.write(line + "\n")
        log.flush()

    # ---- the golden run and its window --------------------------------
    probe = Runner(vvp, image, 200000)
    golden = probe.run()
    if not core.completed(golden):
        sys.exit("the clean run did not complete")
    if (golden["mask"] != "00000000" or golden["exit"] != "00000000"
            or core.wdog_fired(golden) or core.i(golden, "traps")
            or core.alert_seen(golden)):
        sys.exit("the clean run is not clean: %s" % golden)
    if any(scrub_counts(golden).values()):
        sys.exit("the clean run reported a memory event: %s" % scrub_counts(golden))
    again = probe.run()
    if core.answer(again) != core.answer(golden):
        sys.exit("the clean run is not reproducible")
    win_open, win_close = core.i(golden, "win_open"), core.i(golden, "win_close")
    say("control 1: clean run %d cycles, sig %s, window %d..%d, no memory "
        "event on either report line, reproduces exactly",
        core.i(golden, "cycles"), golden["sig"], win_open, win_close)

    regions, secs = strata(elf, readelf, not args.unhardened)
    say("control 2: strata from %s", os.path.relpath(elf))
    for r in regions:
        say("           %-11s mem %d words %5d..%5d (%5d)%s", r.name, r.mem,
            r.lo, r.hi, r.hi - r.lo + 1, "  check bits" if r.chk else "")

    timeout_clk = (core.i(golden, "wdog_rld") + 1) * core.i(golden, "wdog_pre")
    budget = 2 * core.i(golden, "cycles") + 6 * 2 * timeout_clk
    runner = Runner(vvp, image, budget)

    # ---- controls 3 and 4: the deposit lands, and lands nowhere else ----
    #
    # Positive: bit 0 of the FIRST INSTRUCTION of a function the program
    # fetches inside the window. Bit 0 of an RV32 instruction is the low
    # bit of its opcode, so the flip turns a 32-bit instruction into a
    # compressed one and a fetch of it cannot go unnoticed: on the
    # unhardened build the run cannot classify MASKED, and on the
    # hardened build the fetch corrects it and the run classifies
    # CORRECTED. WHICH function is fetched is a property of the compiler
    # -- the first two versions of this control flipped a word the
    # program keeps in a register and a function it had inlined away,
    # and both were rightly MASKED -- so a list of candidates is tried in
    # order and the first one the build reacts to is the control; the
    # name and the word are printed. The addresses come from the ELF.
    nm = subprocess.run([readelf.replace("readelf", "nm"), elf],
                        capture_output=True, text=True, check=True).stdout
    syms = {l.split()[-1]: int(l.split()[0], 16) for l in nm.splitlines()
            if len(l.split()) == 3}
    picked = None
    for name in ("wdog_kick", "putc_", "puthex", "lcg", "mul_sw", "fib_rec",
                 "fib_iter", "round_once", "main"):
        if name not in syms:
            continue
        word = (syms[name] - ROM_BASE) // 4
        pos = runner.run(mem=1, midx=word, mbit=0,
                         cycle=(win_open + win_close) // 2)
        pcls, _ = classify(pos, golden)
        if core.i(pos, "hit") != 1:
            sys.exit("the positive control did not reach the ROM")
        before, after = int(pos["mem_before"], 16), int(pos["mem_after"], 16)
        if after != before ^ 1:
            sys.exit("the positive control did not flip the requested bit")
        say("control 3: bit 0 of %s's first instruction (ROM word %d) "
            "classifies %s", name, word, pcls)
        if pcls != "MASKED":
            picked = (name, word, pcls)
            break
    if picked is None:
        sys.exit("no candidate instruction word was reached inside the "
                 "window: the deposit is not landing, or the window is wrong")
    if not args.unhardened and picked[2] != "CORRECTED":
        sys.exit("a fetched instruction with one flipped bit classified %s on "
                 "the hardened build; the codec should have corrected it on "
                 "the fetch" % picked[2])
    u = next(r for r in regions if r.name == "RAM.unused")
    neg = runner.run(mem=0, midx=(u.lo + u.hi) // 2, mbit=17,
                     cycle=(win_open + win_close) // 2)
    ncls, _ = classify(neg, golden)
    say("control 4: bit 17 of an unused RAM word classifies %s", ncls)

    # ---- the campaign --------------------------------------------------
    plan = []
    for r in regions:
        for k, (word, bit, cycle) in enumerate(draws(r, args.draws,
                                                     (win_open, win_close))):
            plan.append((r, k, word, bit, cycle))
    say("")
    say("campaign: %d injections, %d strata x %d", len(plan), len(regions),
        args.draws)

    def job(item):
        r, k, word, bit, cycle = item
        return item, runner.run(mem=r.mem, midx=word, mbit=bit, cycle=cycle)

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for n, (item, rec) in enumerate(ex.map(job, plan), 1):
            r, k, word, bit, cycle = item
            if core.i(rec, "hit") != 1:
                sys.exit("a deposit missed: %s word %d bit %d" % (r.name, word, bit))
            before, after = int(rec["mem_before"], 16), int(rec["mem_after"], 16)
            want = before ^ (1 << (bit - 32 if bit >= 32 else bit))
            if after != want:
                sys.exit("a deposit did not flip the requested bit: %s word "
                         "%d bit %d" % (r.name, word, bit))
            cls, facts = classify(rec, golden)
            row = {"stratum": r.name, "index": k, "mem": r.mem, "word": word,
                   "bit": bit, "cycle": cycle, "cls": cls}
            row.update(facts)
            rows.append(row)
            if n % 100 == 0:
                say("  ... %d of %d", n, len(plan))

    path = os.path.join(out_dir, "mem_records_%s.csv" % args.tag)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    say("records: %s", path)

    # ---- the report ----------------------------------------------------
    say("")
    say("%-11s %5s %s %10s %10s %8s" % (
        "stratum", "n", "".join("%10s" % c for c in CLASSES),
        "traps", "uncorr", "n_sdc"))
    for r in regions:
        sub = [x for x in rows if x["stratum"] == r.name]
        counts = [sum(1 for x in sub if x["cls"] == c) for c in CLASSES]
        say("%-11s %5d %s %10d %10d %8d" % (
            r.name, len(sub), "".join("%10d" % c for c in counts),
            sum(1 for x in sub if x["ann_trap"]),
            sum(1 for x in sub if x["uncorrectable"]),
            sum(1 for x in sub if x["cls"] == "SDC")))
    counts = [sum(1 for x in rows if x["cls"] == c) for c in CLASSES]
    say("%-11s %5d %s" % ("ALL", len(rows), "".join("%10d" % c for c in counts)))
    log.close()


if __name__ == "__main__":
    main()
