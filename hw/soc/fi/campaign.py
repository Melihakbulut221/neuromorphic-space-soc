#!/usr/bin/env python3
"""The core fault-injection campaign of docs/42: draw, run, classify.

    hw/soc/fi/campaign.py --build hw/soc/out/fi-core [--draws 100] [--jobs 18]

`hw/soc/flow/fi_core.sh` builds and elaborates once; this drives `vvp`
on the result, one process per injection, and classifies what comes
back.  It decides nothing from the RTL: every input to a class is a
field of the RECORD line `hw/soc/tb/tb_soc_fi.v` prints, and every one
of those is a pin, a console character or a word the program itself
published.

WHAT DECIDES RIGHT FROM WRONG

The golden run, always -- an undeposited run of the same program on the
same design, recorded once at the start and re-recorded to prove it
reproduces.  `docs/42` section 3 argues why that and not an ISA
simulator, and says what it does and does not license.

The program's own self-checks are a DETECTION channel and never an
oracle.  A run whose `fail_mask` is zero has not been declared correct
by this campaign; it has been declared unnoticed by the program, which
is a different and much weaker statement.  That is the same separation
`docs/16` section 1.6 draws with `out_ok`.

THE CLASSES

`docs/16` section 1.6's five, in its order, exactly one per injection:

    HANG       the run did not complete inside its budget and nothing
               announced anything
    DETECTED   something announced: the watchdog escalated, the program
               reported a failed self-check, the core took a trap the
               golden run does not take, or an Ibex alert pin fired
    SDC        the result differs from golden and nothing announced
    CORRECTED  the result matches golden and a correction mechanism
               moved
    MASKED     the result matches golden and nothing moved

CORRECTED is structurally unreachable in this design and that is a
finding rather than an omission: `small-pmp` has no correction
mechanism inside the core at all -- no lockstep, no register-file ECC,
no voter -- so there is nothing that could move.  docs/42 section 5
says so in the table rather than quietly dropping the column.

THE PAIR IS THE MEASUREMENT

Every injection is run TWICE: once with the watchdog armed and once
with `wdog_dis_i` held high, which is soc_wdog.v W1's bootstrap pin and
the only thing in the design that can stop the block.  The disarmed run
is the same machine with the same upset and no backstop, so it is what
says whether a machine the watchdog reset was in fact dead.

Without it, "the watchdog escalated" is not a catch rate.  It cannot
distinguish a backstop that saved a hung core from one that reset a
core that was about to finish correctly, and those lead to opposite
decisions.  docs/41 section 8.3 makes the same argument with its
unhardened counterfactual.

AND A CATCH IS A PORT EVENT, NEVER A TIMEOUT

`wdog_first` is the cycle of a transition on `nmi_o`, `wdog_rst_o` or
`wdog_no`.  A run that ends because the simulation budget expired has
no such transition and can never be counted as caught.  The budget is
additionally checked to be long enough for four complete escalation
ladders after the LAST cycle any injection can be drawn at, so "the
watchdog did not fire" means it had four chances and took none of
them -- not that the simulation stopped first.
"""

import argparse
import concurrent.futures
import csv
import os
import random
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import targets                                        # noqa: E402

# The escalation ladder, MEASURED off the golden run rather than
# written down.
#
# It used to be the constant (127 + 1) * 16, from fi_workload.c's
# FI_WDOG_RELOAD and soc_top.v's WDOG_PRESCALE.  docs/43 gave the
# workload a second build with a different reload -- the windowed one,
# whose kick cadence forces a longer timeout -- and a campaign whose
# budget came from a remembered number would then have computed "the
# watchdog had four ladders in which to fire" from the wrong ladder.
# The testbench now reports the reload the program armed and the
# block's prescaler, and the two numbers below come from that record.
DEFAULT_TIMEOUT_CLK = (127 + 1) * 16

SEED = 0x42F12026


# =====================================================================
# running one simulation
# =====================================================================
def parse_record(text):
    rec = {}
    for line in text.splitlines():
        if not line.startswith("RECORD "):
            continue
        body = line[len("RECORD "):]
        if body.strip() == "end":
            rec["_end"] = True
            continue
        if body.startswith("console_tail="):
            rec["console_tail"] = body[len("console_tail="):].strip()
            continue
        for kv in body.split():
            if "=" not in kv:
                continue
            k, v = kv.split("=", 1)
            rec[k] = v
    return rec


class Runner:
    def __init__(self, vvp, image, budget):
        self.vvp = vvp
        self.image = image
        self.budget = budget

    def run(self, site=None, bit=0, cycle=0, armed=True, dumpsites=False):
        cmd = [self.vvp, self.image]
        if site is not None:
            cmd += ["+site=%d" % site, "+bit=%d" % bit, "+cycle=%d" % cycle]
        cmd += ["+armed=%d" % (1 if armed else 0),
                "+budget=%d" % self.budget]
        if dumpsites:
            cmd += ["+dumpsites"]
        out = subprocess.run(cmd, capture_output=True, text=True,
                             check=True).stdout
        rec = parse_record(out)
        if "_end" not in rec:
            raise RuntimeError("simulation produced no complete RECORD:\n"
                               + out[-2000:])
        rec["_raw"] = out
        return rec


# =====================================================================
# the observable facts, derived only from a RECORD
# =====================================================================
def i(rec, key):
    return int(rec[key], 10)


def answer(rec):
    """Everything this campaign treats as the run's RESULT.

    Deliberately NOT the cycle count.  Unlike the watchdog campaign of
    docs/41, where the deadline IS the function and a displaced event is
    a wrong answer, a processor that produces the right value forty
    cycles late has produced the right value.  `cycles` is carried as a
    separate per-record fact so a purely temporal perturbation is
    visible and is not miscounted as data corruption.
    """
    return (rec["sig"], rec["mask"], i(rec, "rounds"),
            rec["exit"], rec["magic"],
            i(rec, "console_chars"), rec["console_hash"],
            i(rec, "console_framing"),
            # core_sleep_o at the end of the run.  The clean run ends
            # asleep and stays asleep; a core that posts the right
            # answer and then spins for ever is a different machine and
            # a bench watching that pin would say so.  See the comment
            # on `done_q` in tb_soc_fi.v for the upset that put it here.
            i(rec, "slept"))


def completed(rec):
    return i(rec, "done") == 1


def wdog_fired(rec):
    return (i(rec, "wdog1") + i(rec, "wdog2") + i(rec, "wdog3")) > 0


def wdog_stage(rec):
    if i(rec, "wdog3"):
        return 3
    if i(rec, "wdog2"):
        return 2
    if i(rec, "wdog1"):
        return 1
    return 0


def sw_flagged(rec, golden):
    """The program's own self-checks reported a failure.

    Stated over what the program publishes, not over how it computes it:
    a nonzero fail mask, or an exit code that is not the golden one.
    crt0.S's runaway-trap guard posts 0xdead0001, which is caught here
    as well.
    """
    return rec["mask"] != golden["mask"] or rec["exit"] != golden["exit"]


def trap_seen(rec, golden):
    """The core took an exception the golden run does not take.

    This is a RISC-V architectural announcement, not a design-internal
    one: an instruction faulted and the machine entered a handler.  The
    golden run takes none, which is why fi_workload.c has no deliberate
    trap in it.
    """
    return i(rec, "traps") > i(golden, "traps")


def corrected(rec):
    """A correction mechanism inside the core moved.

    docs/43's substituted register file corrects a single-bit upset on
    the way out and scrubs it out of the storage, and it counts the
    cycles in which it did.  That counter is the ONLY thing in this
    design that can make docs/16's CORRECTED class reachable -- docs/42
    reported it at 0 of 1,300 and said so explicitly, because
    `small-pmp` had no correction mechanism at all.

    IT IS READ HIERARCHICALLY OUT OF THE SIMULATION AND IT IS NOT A
    PIN.  `ibex_register_file_ff` carries upstream's port list, which
    has no error output, so in silicon a corrected upset is
    indistinguishable from no upset.  This function therefore measures
    what the mechanism DID; it does not claim an operator could see it.
    docs/43 section 9 states that separation where it reports the
    column, and section 12 ranks closing it.
    """
    return i(rec, "rf_sec") > 0


def uncorrectable(rec):
    """The codec saw a syndrome it could not correct: two bits in one
    register between two scrubs, or three.  Detected and not repaired,
    and with nowhere to report it to."""
    return i(rec, "rf_ded") > 0


def alert_seen(rec):
    """One of Ibex's own alert pins fired.

    `bool(...)` and not the bare `or` chain: the value is written into
    records.csv, and an int there serialises as 0/1 while every other
    flag serialises as False/True.  The first version returned the int,
    which classified correctly and then made `--replay` read every alert
    as absent -- a report that disagreed with the run that produced it.
    """
    return bool(i(rec, "alert_minor") or i(rec, "alert_int")
                or i(rec, "alert_bus") or i(rec, "dblfault"))


def classify(rec, golden):
    """Exactly one class, in docs/16 section 1.6's order."""
    ann_wdog = wdog_fired(rec)
    ann_sw = sw_flagged(rec, golden)
    ann_trap = trap_seen(rec, golden)
    ann_alert = alert_seen(rec)
    announced = ann_wdog or ann_sw or ann_trap or ann_alert
    out_ok = completed(rec) and answer(rec) == answer(golden)

    if not completed(rec) and not announced:
        cls = "HANG"
    elif announced:
        cls = "DETECTED"
    elif not out_ok:
        cls = "SDC"
    elif corrected(rec):
        # Reachable for the first time in this repository's core
        # campaigns.  docs/42 reported this column at 0 of 1,300 and
        # kept it in the table rather than dropping it, precisely so
        # that a later design which could reach it would be visibly
        # different.  This is that design.
        cls = "CORRECTED"
    else:
        cls = "MASKED"
    return cls, {
        "out_ok": out_ok,
        "done": completed(rec),
        "ann_wdog": ann_wdog,
        "ann_sw": ann_sw,
        "ann_trap": ann_trap,
        "ann_alert": ann_alert,
        "wdog_stage": wdog_stage(rec),
        "wdog_first": i(rec, "wdog_first"),
        "cycles": i(rec, "cycles"),
        "rf_sec": i(rec, "rf_sec"),
        "rf_ded": i(rec, "rf_ded"),
        "wdog_early": i(rec, "wdog_early"),
        "wdog_budget": i(rec, "wdog_budget"),
    }


# The DISARMED run's verdict -- what the machine did with no backstop --
# is one of three, and the distinction between the last two is the whole
# point of the exercise:
#
#   OK     it finished and the answer is golden
#   WRONG  it finished, and the answer is not golden.  A watchdog CANNOT
#          catch this by construction: the program kept kicking, on time,
#          with a corrupted result.
#   DEAD   it never finished inside the budget.  This is the set a
#          watchdog can do something about.
#
# It is computed inline where the pair is classified, from the disarmed
# record's own `out_ok` and `done`.


# =====================================================================
# the draw
# =====================================================================
def draws(stratum, n, window):
    """`n` (site, bit, cycle) triples for one stratum.

    A bit is drawn UNIFORMLY OVER THE STRATUM'S FLIP-FLOPS, not over its
    sites: `x1` and `pmpcfg0` are one site each but 32 bits and 6, and
    weighting by site would over-sample the narrow ones by five to one.
    The cycle is drawn uniformly inside the MEASURED window of the clean
    run.

    The seed is derived per (stratum, index) rather than consumed from
    one stream, so adding or removing a stratum does not re-roll every
    draw after it.  docs/41 section 8.1 records why that matters: it is
    what makes the armed and disarmed runs of the same campaign, and two
    campaigns at different sample sizes, comparable draw by draw.
    """
    sites = targets.stratum_sites(stratum)
    total = sum(s.width for s in sites)
    out = []
    lo, hi = window
    for k in range(n):
        rng = random.Random("%d:%s:%d" % (SEED, stratum, k))
        pick = rng.randrange(total)
        acc = 0
        chosen = None
        for s in sites:
            if pick < acc + s.width:
                chosen = (s, pick - acc)
                break
            acc += s.width
        site, bit = chosen
        cycle = rng.randrange(lo, hi)
        out.append((targets.SITES.index(site), site, bit, cycle))
    return out



def weighted_rate(rows, col, cls):
    """The design-weighted rate of one class, and its 95 % half-width.

    See the comment at the call site: the campaign draws equally from
    strata of very unequal size, so the core-level figure is the
    bit-weighted combination of the per-stratum rates and its variance
    is the weighted combination of theirs.
    """
    total_bits = sum(targets.stratum_bits(s) for s in targets.STRATA)
    p = 0.0
    var = 0.0
    for stratum in targets.STRATA:
        sub = [r for r in rows if r["stratum"] == stratum]
        if not sub:
            continue
        n = len(sub)
        w = targets.stratum_bits(stratum) / total_bits
        ph = sum(1 for r in sub if r[col] == cls) / n
        p += w * ph
        var += w * w * ph * (1 - ph) / n
    return p, 1.959963985 * (var ** 0.5)


def wilson(k, n):
    """95 % Wilson score interval.

    Reported instead of k/n alone because this campaign's per-stratum
    samples are in the low hundreds at best and `docs/16` section 7.1
    records the last campaign's numbers being read more precisely than
    they could carry.
    """
    if n == 0:
        return (0.0, 0.0)
    z = 1.959963985
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return ((c - s) / d, (c + s) / d)


# =====================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True,
                    help="directory hw/soc/flow/fi_core.sh wrote")
    ap.add_argument("--directed", default=None,
                    help="a records.csv (or any CSV with site, bit and "
                         "cycle columns) whose injections are re-run "
                         "VERBATIM against this build, so that a named "
                         "set from an earlier campaign -- docs/42's "
                         "three uncaught x23 draws, or its whole DEAD "
                         "set -- can be asked of a hardened design")
    ap.add_argument("--directed-filter", default=None,
                    help="only rows whose `truth` column equals this, "
                         "e.g. DEAD")
    ap.add_argument("--replay", default=None,
                    help="re-print the report from an existing records.csv "
                         "without re-running 2,600 simulations")
    ap.add_argument("--draws", type=int, default=100,
                    help="injections per stratum")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--vvp", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    build = os.path.abspath(args.build)
    out_dir = os.path.abspath(args.out or build)
    os.makedirs(out_dir, exist_ok=True)

    vvp = args.vvp
    if vvp is None:
        soc = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        printed = subprocess.run(
            ["make", "--no-print-directory", "-f",
             os.path.join(soc, "tools.soc.mk"), "printvars"],
            capture_output=True, text=True, check=True).stdout
        for line in printed.splitlines():
            if line.startswith("VVP="):
                vvp = line.split("=", 1)[1].strip().strip('"')
    if not vvp:
        sys.exit("could not resolve VVP")

    image = os.path.join(build, "tb_soc_fi.vvp")
    if not os.path.exists(image):
        sys.exit("missing %s: run hw/soc/flow/fi_core.sh first" % image)

    log = open(os.path.join(out_dir, "campaign.log"),
               "a" if args.replay else "w")

    def say(fmt, *a):
        line = fmt % a if a else fmt
        print(line)
        log.write(line + "\n")
        log.flush()

    if args.replay:
        with open(args.replay, newline="") as f:
            rows = []
            for r in csv.DictReader(f):
                for k in ("bit", "cycle", "wdog_stage", "wdog_first",
                          "wdog_latency", "armed_cycles", "disarmed_cycles",
                          "armed_rf_sec", "armed_rf_ded", "disarmed_rf_sec",
                          "wdog_early", "wdog_budget", "timeout_clk"):
                    if k in r:
                        r[k] = int(r[k])
                for k in ("armed_out_ok", "disarmed_out_ok", "armed_done",
                          "disarmed_done", "ann_sw", "ann_trap", "ann_alert",
                          "ann_wdog"):
                    r[k] = r[k] in ("True", "1")
                rows.append(r)
        report(say, rows)
        log.close()
        return

    # =================================================================
    # CONTROL 1: the elaborated design is the one targets.py describes
    # =================================================================
    probe_runner = Runner(vvp, image, 200000)
    dump = probe_runner.run(dumpsites=True)
    elaborated = []
    for line in dump["_raw"].splitlines():
        if line.startswith("SITE "):
            _, idx, stratum, name, width, path = line.split(None, 5)
            elaborated.append((int(idx), stratum, name, int(width),
                               path.strip()))
        elif line.startswith("SITECOUNT "):
            count = int(line.split()[1])
    if count != len(targets.SITES):
        sys.exit("the testbench elaborated %d sites, targets.py lists %d"
                 % (count, len(targets.SITES)))
    for idx, stratum, name, width, path in elaborated:
        want = targets.SITES[idx]
        got = (stratum, name, width, path)
        exp = (want.stratum, want.name, want.width,
               "dut.u_ibex." + want.path)
        if got != exp:
            sys.exit("site %d disagrees.\n  elaborated %s\n  targets.py %s"
                     % (idx, got, exp))
    say("control 1: %d sites, every path, index and width agrees with "
        "targets.py", count)

    # =================================================================
    # CONTROL 2: the golden run, and the window it measures
    # =================================================================
    golden = probe_runner.run(armed=True)
    if not completed(golden):
        sys.exit("the clean run did not complete:\n" + golden["_raw"][-2000:])
    for k, v in (("mask", "00000000"), ("exit", "00000000"),
                 ("magic", "600dc0de")):
        if golden[k] != v:
            sys.exit("the clean run's %s is %s, expected %s"
                     % (k, golden[k], v))
    if wdog_fired(golden):
        sys.exit("the clean run escalated the watchdog: %s.  The campaign "
                 "cannot attribute an escalation to an injection if the "
                 "workload produces one on its own." % golden)
    if i(golden, "traps") or alert_seen(golden):
        sys.exit("the clean run took a trap or raised an alert; every "
                 "announcement channel must be silent in it")
    if i(golden, "console_framing"):
        sys.exit("the clean run has console framing errors")

    # The escalation ladder, from the block and the program rather than
    # from a constant.  See DEFAULT_TIMEOUT_CLK.
    timeout_clk = (i(golden, "wdog_rld") + 1) * i(golden, "wdog_pre")
    ladder_clk = 2 * timeout_clk

    win_open, win_close = i(golden, "win_open"), i(golden, "win_close")
    if not (0 < win_open < win_close <= i(golden, "cycles")):
        sys.exit("the measured injection window is not sane: %d..%d of %d"
                 % (win_open, win_close, i(golden, "cycles")))
    say("control 2: clean run %d cycles, sig %s, %d console characters, "
        "no announcement of any kind",
        i(golden, "cycles"), golden["sig"], i(golden, "console_chars"))
    say("           measured injection window %d..%d (%d cycles, %.0f %% "
        "of the run)", win_open, win_close, win_close - win_open,
        100.0 * (win_close - win_open) / i(golden, "cycles"))

    # THE KICK CADENCE, MEASURED.  soc_wdog.v W7 rejects a kick that
    # arrives too early, and the bound it is checked against is a
    # fraction of the period -- so what a given program can live inside
    # is the ratio of its longest interval between kicks to its
    # shortest.  That is a property of the software and it is measured
    # here rather than assumed, because docs/43 section 4 found the
    # unmodified workload at a ratio of 57 where WINS = 1 permits 2.
    kmin, kmax = i(golden, "kick_min"), i(golden, "kick_max")
    say("           kick cadence: %d kicks, interval %d..%d clocks, "
        "jitter ratio %.3f; timeout %d clocks (reload %d, prescale %d)",
        i(golden, "kicks"), kmin, kmax,
        (kmax / float(kmin)) if kmin > 0 else float("inf"),
        timeout_clk, i(golden, "wdog_rld"), i(golden, "wdog_pre"))
    if i(golden, "wdog_early") or i(golden, "wdog_budget"):
        sys.exit("the clean run violated the cadence contract "
                 "(%d early kicks, %d budget overruns).  The campaign "
                 "cannot attribute an escalation to an injection if the "
                 "workload produces one on its own."
                 % (i(golden, "wdog_early"), i(golden, "wdog_budget")))
    if corrected(golden) or uncorrectable(golden):
        sys.exit("the clean run corrected or detected a register-file "
                 "error with nothing injected; the correction counter "
                 "cannot then attribute anything to an injection")

    # =================================================================
    # CONTROL 3: it reproduces, and the watchdog is invisible when it
    # never fires
    # =================================================================
    again = probe_runner.run(armed=True)
    if answer(again) != answer(golden) or i(again, "cycles") != i(golden, "cycles"):
        sys.exit("the clean run is not reproducible")
    disarmed_golden = probe_runner.run(armed=False)
    if answer(disarmed_golden) != answer(golden):
        sys.exit("the clean run differs with the watchdog held off; the "
                 "armed and disarmed columns would not be comparable")
    say("control 3: the clean run reproduces exactly, and is identical "
        "with the watchdog held off")

    # =================================================================
    # The budget, and why it is this
    # =================================================================
    budget = 2 * i(golden, "cycles") + 6 * ladder_clk
    need = win_close + 4 * ladder_clk + i(golden, "cycles")
    if budget < need:
        budget = need
    runner = Runner(vvp, image, budget)
    say("           budget %d cycles: the latest cycle an injection can "
        "be drawn at is %d, a full escalation ladder is %d clocks, so "
        "every run that does not escalate had at least %.1f ladders in "
        "which to do so",
        budget, win_close, ladder_clk,
        (budget - win_close) / float(ladder_clk))

    # =================================================================
    # CONTROL 4: the injector reaches the design, in both directions
    # =================================================================
    # Positive: bit 20 of x2, the stack pointer.  RAM is 32 KiB at zero
    # (regmap/memmap.yaml), so setting bit 20 puts every subsequent
    # stack access outside every mapped region and the machine cannot
    # continue as if nothing happened.  A campaign in which this comes
    # back MASKED is a campaign whose deposits are not landing --
    # docs/41 section 8.1's fourth honesty check.
    sp_site = next(k for k, s in enumerate(targets.SITES) if s.name == "x2")
    pos = runner.run(site=sp_site, bit=20, cycle=(win_open + win_close) // 2)
    pcls, _ = classify(pos, golden)
    if i(pos, "hit") != 1:
        sys.exit("the positive control did not reach a target")
    if pcls == "MASKED":
        sys.exit("flipping bit 20 of the stack pointer classified MASKED. "
                 "The deposit is not landing and the campaign would "
                 "measure nothing.")
    say("control 4a: bit 20 of x2 (the stack pointer) at cycle %d "
        "classifies %s, so deposits land", (win_open + win_close) // 2, pcls)

    # Negative: mcycle.  fi_workload.c never reads it, so an upset there
    # cannot change the answer.  A campaign in which nothing is ever
    # MASKED is a campaign whose oracle is too tight.
    mc_site = next(k for k, s in enumerate(targets.SITES)
                   if s.name == "mcycle")
    neg = runner.run(site=mc_site, bit=40,
                     cycle=(win_open + win_close) // 2)
    ncls, _ = classify(neg, golden)
    say("control 4b: bit 40 of mcycle, which this program never reads, "
        "classifies %s", ncls)

    # =================================================================
    # Directed replay: somebody else's injections, against this build
    # =================================================================
    #
    # The point of this mode is that a delta between two designs is only
    # a delta if the two were asked the same question.  The stratified
    # draw already gives the same (site, bit) pairs across builds -- the
    # seed is derived per (stratum, index) -- but the CYCLE is drawn
    # inside the MEASURED window, so a build whose workload changed
    # draws different cycles.  Replaying an explicit list removes that
    # last degree of freedom: same site, same bit, same cycle, different
    # design.
    if args.directed:
        with open(args.directed, newline="") as f:
            want = []
            for r in csv.DictReader(f):
                if (args.directed_filter and
                        r.get("truth") != args.directed_filter):
                    continue
                want.append((r["site"], r["path"], int(r["bit"]),
                             int(r["cycle"]),
                             r.get("truth", ""), r.get("armed_cls", "")))
        # KEYED ON THE PATH AND NOT ON THE NAME, and that is a defect
        # this mode had rather than a design choice.  Site NAMES are not
        # unique across strata -- `rdata_q` is the fetch FIFO's 96-bit
        # instruction queue in one stratum and the load/store unit's
        # 24-bit data register in another -- so a name lookup silently
        # replayed one into the other.  Bit 87 of a 24-bit register XORs
        # a mask entirely outside the register: the testbench reports
        # hit = 1, the value does not change, and the run comes back
        # MASKED.  Two of docs/42's DEAD records were replayed that way
        # and looked exactly like a hardening that had fixed them.  The
        # path is unique, it is already in the records, and the deposit
        # is verified below the way the campaign verifies it.
        by_path = {s.path: k for k, s in enumerate(targets.SITES)}
        say("")
        say("directed replay of %d injections from %s", len(want),
            args.directed)
        say("%-10s %5s %8s  %-10s %-10s  %-10s %-10s %-8s %s"
            % ("site", "bit", "cycle", "was(armed)", "was(truth)",
               "now(armed)", "now(dis)", "now(truth)", "escalated"))
        out_rows = []
        for name, path, bit, cycle, was_truth, was_cls in want:
            if path not in by_path:
                sys.exit("path %s is not in this build's site list" % path)

        # docs/74: the pair is run through the same pool as the campaign
        # proper.  Until then this loop was serial, which for docs/43's
        # replays of a few dozen records was a minute and for a replay of
        # a whole 1,400-record campaign would be a working day.  The
        # records are classified below in their file order, as before.
        def directed_job(item):
            name, path, bit, cycle, was_truth, was_cls = item
            idx = by_path[path]
            a = runner.run(site=idx, bit=bit, cycle=cycle, armed=True)
            d = runner.run(site=idx, bit=bit, cycle=cycle, armed=False)
            return a, d

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
            pairs = list(ex.map(directed_job, want))

        for (name, path, bit, cycle, was_truth, was_cls), (a, d) in zip(want, pairs):
            idx = by_path[path]
            # The same verification the campaign does, for the same
            # reason: a deposit that missed has to be a hard failure and
            # never a quiet MASKED.
            for rec in (a, d):
                if i(rec, "hit") != 1:
                    sys.exit("a directed deposit missed: %s bit %d"
                             % (path, bit))
                if i(rec, "width") <= bit:
                    sys.exit("bit %d is outside %s's %d bits"
                             % (bit, path, i(rec, "width")))
                before = int(rec["before"], 16)
                after = int(rec["after"], 16)
                if after != before ^ (1 << bit):
                    sys.exit("a directed deposit did not flip exactly the "
                             "requested bit: %s bit %d" % (path, bit))
            acls, af = classify(a, golden)
            dcls, df = classify(d, golden)
            t = "OK" if df["out_ok"] else ("WRONG" if df["done"] else "DEAD")
            how = []
            if af["wdog_early"]:
                how.append("W7 early")
            if af["wdog_budget"]:
                how.append("W8 budget")
            if af["ann_wdog"] and not how:
                how.append("expiry")
            if af["rf_sec"]:
                how.append("regfile corrected %d" % af["rf_sec"])
            say("%-10s %5d %8d  %-10s %-10s  %-10s %-10s %-8s %s"
                % (name, bit, cycle, was_cls, was_truth, acls, dcls, t,
                   ", ".join(how) if how else "-"))
            out_rows.append({"site": name, "bit": bit, "cycle": cycle,
                             "was_armed_cls": was_cls, "was_truth": was_truth,
                             "armed_cls": acls, "disarmed_cls": dcls,
                             "truth": t,
                             "armed_out_ok": af["out_ok"],
                             "ann_wdog": af["ann_wdog"],
                             "wdog_stage": af["wdog_stage"],
                             "rf_sec": af["rf_sec"], "rf_ded": af["rf_ded"],
                             "wdog_early": af["wdog_early"],
                             "wdog_budget": af["wdog_budget"]})
        dpath = os.path.join(out_dir, "directed.csv")
        with open(dpath, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
        say("directed records: %s", dpath)
        log.close()
        return

    # =================================================================
    # The campaign
    # =================================================================
    plan = []
    for stratum in targets.STRATA:
        for site_idx, site, bit, cycle in draws(stratum, args.draws,
                                                (win_open, win_close)):
            plan.append((stratum, site_idx, site, bit, cycle))
    say("")
    say("campaign: %d injections, %d strata x %d, each run twice "
        "(watchdog armed and held off) = %d simulations",
        len(plan), len(targets.STRATA), args.draws, 2 * len(plan))

    def job(item):
        stratum, site_idx, site, bit, cycle = item
        a = runner.run(site=site_idx, bit=bit, cycle=cycle, armed=True)
        d = runner.run(site=site_idx, bit=bit, cycle=cycle, armed=False)
        return item, a, d

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for n, (item, a, d) in enumerate(ex.map(job, plan), 1):
            results.append((item, a, d))
            if n % 100 == 0:
                say("  ... %d of %d", n, len(plan))

    # =================================================================
    # Classify
    # =================================================================
    rows = []
    for (stratum, site_idx, site, bit, cycle), a, d in results:
        for rec in (a, d):
            if i(rec, "hit") != 1:
                sys.exit("a deposit missed its target: site %d bit %d"
                         % (site_idx, bit))
            before = int(rec["before"], 16)
            after = int(rec["after"], 16)
            if after != before ^ (1 << bit):
                sys.exit("a deposit did not flip exactly the requested "
                         "bit: site %d bit %d, %032x -> %032x"
                         % (site_idx, bit, before, after))
            if i(rec, "width") <= bit:
                sys.exit("bit %d is outside site %d's %d bits"
                         % (bit, site_idx, i(rec, "width")))
        acls, afacts = classify(a, golden)
        dcls, dfacts = classify(d, golden)
        if dfacts["out_ok"]:
            t = "OK"
        elif dfacts["done"]:
            t = "WRONG"
        else:
            t = "DEAD"
        rows.append({
            "stratum": stratum, "site": site.name, "path": site.path,
            "bit": bit, "cycle": cycle,
            "armed_cls": acls, "disarmed_cls": dcls,
            "truth": t,
            "armed_out_ok": afacts["out_ok"],
            "disarmed_out_ok": dfacts["out_ok"],
            "armed_done": afacts["done"], "disarmed_done": dfacts["done"],
            "wdog_stage": afacts["wdog_stage"],
            "wdog_first": afacts["wdog_first"],
            "wdog_latency": (afacts["wdog_first"] - cycle
                             if afacts["wdog_first"] >= 0 else -1),
            "ann_sw": afacts["ann_sw"], "ann_trap": afacts["ann_trap"],
            "ann_alert": afacts["ann_alert"],
            "ann_wdog": afacts["ann_wdog"],
            "armed_cycles": afacts["cycles"],
            "disarmed_cycles": dfacts["cycles"],
            # docs/43.  The register file's correction counter and the
            # watchdog's two new violation counters, per record, so
            # that "the escalation happened" can be attributed to an
            # ordinary expiry, to W7's window or to W8's budget rather
            # than lumped together.
            "armed_rf_sec": afacts["rf_sec"],
            "armed_rf_ded": afacts["rf_ded"],
            "disarmed_rf_sec": dfacts["rf_sec"],
            "wdog_early": afacts["wdog_early"],
            "wdog_budget": afacts["wdog_budget"],
            "timeout_clk": timeout_clk,
        })

    csv_path = os.path.join(out_dir, "records.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    say("records: %s", csv_path)

    report(say, rows)
    log.close()


CLASSES = ["MASKED", "CORRECTED", "SDC", "DETECTED", "HANG"]


def report(say, rows):
    """Everything printed after the campaign, from the rows alone.

    Deliberately takes nothing but the records, so `--replay` on a saved
    records.csv reproduces the whole report without re-running 2,600
    simulations -- and so no number in it can come from anywhere but the
    data.
    """
    say("")
    say("=" * 74)
    say("1. CLASSIFICATION, WATCHDOG ARMED -- the SoC as it is built")
    say("=" * 74)
    say("%-12s %5s  %s" % ("stratum", "n",
                           "".join("%10s" % c for c in CLASSES)))
    for stratum in targets.STRATA:
        sub = [r for r in rows if r["stratum"] == stratum]
        if not sub:
            # A stratum with no rows is a records.csv from an
            # older site list, replayed. Skip it rather than
            # dividing by zero.
            continue
        counts = [sum(1 for r in sub if r["armed_cls"] == c) for c in CLASSES]
        say("%-12s %5d  %s" % (stratum, len(sub),
                               "".join("%10d" % c for c in counts)))
    counts = [sum(1 for r in rows if r["armed_cls"] == c) for c in CLASSES]
    say("%-12s %5d  %s" % ("ALL", len(rows),
                           "".join("%10d" % c for c in counts)))

    say("")
    say("=" * 74)
    say("2. CLASSIFICATION, WATCHDOG HELD OFF -- the core with no backstop")
    say("=" * 74)
    say("%-12s %5s  %s" % ("stratum", "n",
                           "".join("%10s" % c for c in CLASSES)))
    for stratum in targets.STRATA:
        sub = [r for r in rows if r["stratum"] == stratum]
        if not sub:
            # A stratum with no rows is a records.csv from an
            # older site list, replayed. Skip it rather than
            # dividing by zero.
            continue
        counts = [sum(1 for r in sub if r["disarmed_cls"] == c)
                  for c in CLASSES]
        say("%-12s %5d  %s" % (stratum, len(sub),
                               "".join("%10d" % c for c in counts)))
    counts = [sum(1 for r in rows if r["disarmed_cls"] == c) for c in CLASSES]
    say("%-12s %5d  %s" % ("ALL", len(rows),
                           "".join("%10d" % c for c in counts)))

    # docs/16 section 1.6: "detected is recoverable, not harmless".  A
    # DETECTED record says something announced, not that the answer
    # survived, so the split is reported rather than left to be assumed.
    det = [r for r in rows if r["disarmed_cls"] == "DETECTED"]
    say("")
    say("of the %d DETECTED with the watchdog held off, %d also produced "
        "a wrong or missing answer", len(det),
        sum(1 for r in det if not r["disarmed_out_ok"]))

    say("")
    say("=" * 74)
    say("3. SDC RATE PER STRATUM (watchdog held off), 95 % Wilson interval")
    say("=" * 74)
    say("%-12s %5s %6s %6s %8s   %s"
        % ("stratum", "bits", "n", "SDC", "rate", "95 % interval"))
    for stratum in targets.STRATA:
        sub = [r for r in rows if r["stratum"] == stratum]
        if not sub:
            # A stratum with no rows is a records.csv from an
            # older site list, replayed. Skip it rather than
            # dividing by zero.
            continue
        k = sum(1 for r in sub if r["disarmed_cls"] == "SDC")
        lo, hi = wilson(k, len(sub))
        say("%-12s %5d %6d %6d %7.1f %%   %.1f .. %.1f %%"
            % (stratum, targets.stratum_bits(stratum), len(sub), k,
               100.0 * k / len(sub), 100 * lo, 100 * hi))
    k = sum(1 for r in rows if r["disarmed_cls"] == "SDC")
    lo, hi = wilson(k, len(rows))
    say("%-12s %5d %6d %6d %7.1f %%   %.1f .. %.1f %%"
        % ("unweighted", sum(targets.stratum_bits(s) for s in targets.STRATA),
           len(rows), k, 100.0 * k / len(rows), 100 * lo, 100 * hi))

    # The design-weighted figure, with the interval an equal-n
    # stratified estimator actually has.
    #
    # An equal-n campaign does NOT estimate the whole core's rate by its
    # own average: 100 draws in a 15-bit stratum and 100 in a 992-bit one
    # are not 200 draws from the core.  The estimator is
    #
    #     p = sum_h  (bits_h / bits) * p_h
    #     var(p) = sum_h (bits_h / bits)^2 * p_h (1 - p_h) / n_h
    #
    # and reporting the first without the second is exactly how a number
    # comes to be quoted more precisely than it can carry -- docs/16
    # section 7.1.
    say("")
    for label, col in (("held off", "disarmed_cls"), ("armed", "armed_cls")):
        for cls in ("SDC", "HANG"):
            p, half = weighted_rate(rows, col, cls)
            say("design-weighted %-5s rate, watchdog %-8s: %.1f %% "
                "+/- %.1f (95 %%)", cls, label, 100 * p, 100 * half)
    say("  (each stratum's measured rate weighted by its share of the "
        "%d injectable RTL bits)",
        sum(targets.stratum_bits(s) for s in targets.STRATA))

    say("")
    say("=" * 74)
    say("4. WHAT THE MACHINE DOES WITH NO BACKSTOP, AND WHAT THE WATCHDOG")
    say("   DOES ABOUT IT.  Rows are the DISARMED run's verdict; columns")
    say("   are whether the ARMED run saw a transition on nmi_o,")
    say("   wdog_rst_o or wdog_no.")
    say("=" * 74)
    say("%-8s %6s %10s %10s %10s   %s"
        % ("truth", "n", "escalated", "quiet", "caught %", "95 % interval"))
    for t in ("OK", "WRONG", "DEAD"):
        sub = [r for r in rows if r["truth"] == t]
        if not sub:
            say("%-8s %6d" % (t, 0))
            continue
        k = sum(1 for r in sub if r["ann_wdog"])
        lo, hi = wilson(k, len(sub))
        say("%-8s %6d %10d %10d %9.1f %%   %.1f .. %.1f %%"
            % (t, len(sub), k, len(sub) - k, 100.0 * k / len(sub),
               100 * lo, 100 * hi))

    say("")
    say("   The same three, per stratum, with the caught count beside the")
    say("   DEAD column.  This is the ranking a hardening decision would")
    say("   be made off: WRONG is what protection inside the core would")
    say("   have to address, DEAD is what the backstop already does.")
    say("%-12s %5s %7s %7s %7s %9s"
        % ("stratum", "n", "OK", "WRONG", "DEAD", "DEAD caught"))
    for stratum in targets.STRATA:
        sub = [r for r in rows if r["stratum"] == stratum]
        if not sub:
            # A stratum with no rows is a records.csv from an
            # older site list, replayed. Skip it rather than
            # dividing by zero.
            continue
        d = [r for r in sub if r["truth"] == "DEAD"]
        say("%-12s %5d %7d %7d %7d %9s"
            % (stratum, len(sub),
               sum(1 for r in sub if r["truth"] == "OK"),
               sum(1 for r in sub if r["truth"] == "WRONG"),
               len(d),
               "%d/%d" % (sum(1 for r in d if r["ann_wdog"]), len(d))
               if d else "-"))

    dead = [r for r in rows if r["truth"] == "DEAD"]
    wrong = [r for r in rows if r["truth"] == "WRONG"]
    ok = [r for r in rows if r["truth"] == "OK"]
    say("")
    say("  OK    the disarmed run finished with the golden answer: the "
        "upset did not break the machine")
    say("  WRONG the disarmed run finished with a WRONG answer: the "
        "program kept kicking, on time, with a corrupted result.  A "
        "watchdog cannot catch this and is not supposed to.")
    say("  DEAD  the disarmed run never finished: a loop, a stall or a "
        "trap storm.  This is the set the backstop exists for.")

    if dead:
        k = sum(1 for r in dead if r["ann_wdog"])
        lo, hi = wilson(k, len(dead))
        say("")
        say("WATCHDOG CATCH RATE over the set a watchdog can act on "
            "(DEAD): %d of %d = %.1f %% [%.1f .. %.1f %%]",
            k, len(dead), 100.0 * k / len(dead), 100 * lo, 100 * hi)
        rec = sum(1 for r in dead if r["armed_out_ok"])
        say("  of those, %d ended with the golden answer anyway: the "
            "stage-2 reset restarted the program and it completed "
            "correctly", rec)
        st = {}
        for r in dead:
            st[r["wdog_stage"]] = st.get(r["wdog_stage"], 0) + 1
        say("  highest stage reached: %s",
            ", ".join("stage %d: %d" % (k2, v) for k2, v in sorted(st.items())))
        lats = [r["wdog_latency"] for r in dead if r["wdog_latency"] >= 0]
        if lats:
            lats.sort()
            say("  cycles from the deposit to the first escalation: "
                "min %d, median %d, max %d (one timeout is %d clocks)",
                lats[0], lats[len(lats) // 2], lats[-1],
                rows[0].get("timeout_clk", DEFAULT_TIMEOUT_CLK))
    if wrong:
        k = sum(1 for r in wrong if r["ann_wdog"])
        say("")
        say("SILENT CORRUPTION THE BACKSTOP CANNOT SEE: %d of %d WRONG "
            "runs escalated nothing.  These are the injections that "
            "produce a wrong answer and keep running.",
            len(wrong) - k, len(wrong))
        ks = sum(1 for r in wrong if r["ann_sw"])
        kt = sum(1 for r in wrong if r["ann_trap"])
        say("  of the %d, the program's own self-checks noticed %d and "
            "the core took an unexpected trap in %d", len(wrong), ks, kt)
    if ok:
        k = sum(1 for r in ok if r["ann_wdog"])
        say("")
        say("SPURIOUS ESCALATIONS: %d of %d injections that the machine "
            "would have survived escalated the watchdog anyway", k, len(ok))

    say("")
    say("=" * 74)
    say("5. WHAT ANNOUNCED IT (watchdog armed, injections whose armed run")
    say("   did not produce the golden answer)")
    say("=" * 74)
    bad = [r for r in rows if not r["armed_out_ok"]]
    say("%-28s %6s" % ("channel", "n"))
    say("%-28s %6d" % ("the watchdog escalated",
                       sum(1 for r in bad if r["ann_wdog"])))
    say("%-28s %6d" % ("the program's self-checks",
                       sum(1 for r in bad if r["ann_sw"])))
    say("%-28s %6d" % ("an unexpected trap",
                       sum(1 for r in bad if r["ann_trap"])))
    say("%-28s %6d" % ("an Ibex alert pin",
                       sum(1 for r in bad if r["ann_alert"])))
    say("%-28s %6d" % ("NOTHING (silent)",
                       sum(1 for r in bad if not (r["ann_wdog"] or r["ann_sw"]
                                                  or r["ann_trap"]
                                                  or r["ann_alert"]))))
    say("%-28s %6d" % ("total wrong or dead", len(bad)))

    say("")
    say("=" * 74)
    say("6. WHAT THE HARDENING DID, PER MECHANISM (docs/43)")
    say("=" * 74)
    have = [r for r in rows if "armed_rf_sec" in r]
    if not have:
        say("  this records.csv predates docs/43 and carries none of "
            "these columns")
    else:
        rf = [r for r in have if r["armed_rf_sec"] > 0]
        rfd = [r for r in have if r["armed_rf_ded"] > 0]
        ew = [r for r in have if r["wdog_early"] > 0]
        bd = [r for r in have if r["wdog_budget"] > 0]
        say("register file, single-bit corrected  %6d of %d injections"
            % (len(rf), len(have)))
        say("register file, UNCORRECTABLE seen    %6d" % len(rfd))
        say("W7, a kick rejected as too early     %6d" % len(ew))
        say("W8, a phase out of kicks             %6d" % len(bd))
        say("")
        say("  of the %d the register file corrected, %d ended with the "
            "golden answer" % (len(rf), sum(1 for r in rf
                                            if r["armed_out_ok"])))
        # The mechanism that escalated, for every record that escalated.
        esc = [r for r in have if r["ann_wdog"]]
        say("  of the %d escalations, %d involved an early kick and %d a "
            "spent budget; the rest are ordinary expiries"
            % (len(esc), sum(1 for r in esc if r["wdog_early"] > 0),
               sum(1 for r in esc if r["wdog_budget"] > 0)))

    say("")
    say("=" * 74)
    say("7. THE WORST SITES (watchdog held off), by SDC plus HANG")
    say("=" * 74)
    per = {}
    for r in rows:
        key = (r["stratum"], r["site"])
        d = per.setdefault(key, {"n": 0, "bad": 0, "sdc": 0, "hang": 0})
        d["n"] += 1
        if r["disarmed_cls"] == "SDC":
            d["sdc"] += 1
            d["bad"] += 1
        if r["disarmed_cls"] == "HANG":
            d["hang"] += 1
            d["bad"] += 1
    ranked = sorted(per.items(), key=lambda kv: -kv[1]["bad"] / kv[1]["n"])
    say("%-12s %-24s %5s %5s %5s %8s"
        % ("stratum", "site", "n", "SDC", "HANG", "bad %"))
    for (stratum, site), d in ranked[:20]:
        if d["bad"] == 0:
            break
        say("%-12s %-24s %5d %5d %5d %7.0f %%"
            % (stratum, site, d["n"], d["sdc"], d["hang"],
               100.0 * d["bad"] / d["n"]))


if __name__ == "__main__":
    main()
