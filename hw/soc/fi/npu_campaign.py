#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""The NPU-connection fault-injection campaign of docs/52: draw, run,
classify.

    hw/soc/fi/npu_campaign.py --build hw/soc/out/fi-npu [--draws 100]
                              [--jobs 18]

`hw/soc/flow/fi_npu.sh` builds and elaborates once; this drives `vvp` on
the result, one process per injection, and classifies what comes back.
It decides nothing from the RTL: every input to a class is a field of the
RECORD line `hw/soc/tb/tb_soc_npu_fi.v` prints, and every one of those is
a pin, a console character, a word the program itself published, or a
bench observation that is LABELLED as one.

THIS FILE IS hw/soc/fi/campaign.py's SIBLING AND NOT ITS COPY.  Four
things are different and each one is the reason this campaign exists.

1. THE ORACLE.  docs/42 section 3 had to settle for "an undeposited run
   of the same program on the same design", and stated at length what
   that costs: it measures DEVIATION, not CORRECTNESS, and "an upset that
   leaves a register wrong in a way THIS PROGRAM never reads is MASKED
   here ... this is the single largest reason the measured SDC rate is a
   lower bound".

   Here the specification is executable and is compiled into the ROM.
   `hw/soc/flow/gen_npu_vectors.py` runs `sw/golden/lif_core.py` --
   docs/10 section 13's normative executable form of the section 4
   equations -- at BUILD TIME, and `fi_npu.c` compares the collected
   event stream and the WHOLE NEURON STATE FILE against its output.  So
   this campaign has BOTH oracles and reports them side by side:

     the run oracle    the whole published result against the golden
                       RUN.  docs/42's, unchanged, and still what
                       decides the class.
     the model oracle  `fi_mask` bits F_LEN, F_STREAM and F_STATE,
                       which are comparisons against the SPECIFICATION.

   `F_STATE` is the one that is not available anywhere else in this
   repository's SoC campaigns: it is an ARCHITECTURAL-STATE oracle.  An
   upset that leaves V or R wrong without producing a wrong spike is
   MASKED under an output-only oracle and is caught here.  Section 5.2 of
   docs/52 counts how many records it actually separated, and if the
   answer is zero it says zero.

2. THREE POPULATIONS, NOT ONE.  hw/soc/fi/npu_targets.py's header is the
   argument.  An upset in the transport corrupts one register access, an
   upset in the event path corrupts an inference, and an upset in the
   cause register corrupts what the operator is told.  The report ranks
   by CONSEQUENCE and not by rate, which is docs/41 section 3.1's
   criterion and docs/42 section 6.3's table.

3. ONE STRATUM IS INSIDE FROZEN SILICON.  `die_ser` is
   hw/rtl/pilot_top.v's own half of the serial transport.  Every table
   prints it apart, and the design-weighted figures are computed over the
   CONNECTION's bits alone, because a rate that mixed a design still open
   with a die docs/34 has committed would be a number nobody can act on.

4. THE CORRECTION MECHANISM HAS NO OPERATOR CHANNEL.  `aer_fifo`'s
   pointer voting and entry parity are the only protection in the
   connection, and soc_npu.v brings their reports out and connects them
   to nothing (docs/51 section 14 item 1).  This file therefore counts
   them, uses them to make docs/16's CORRECTED class reachable, and says
   in the report that a corrected upset is invisible in silicon --
   exactly the separation docs/43 draws for the register file's own
   correction counter.

THE PAIR IS THE COUNTERFACTUAL

Every injection is run TWICE, once with the watchdog armed and once with
`wdog_dis_i` held high.  docs/42 section 7.1 is the argument and it is
not re-made here; what IS different is the question it answers.  There it
asked whether the backstop reaches a corrupted CORE.  Here it asks
whether the backstop reaches a CPU that has stalled ON A PERIPHERAL: the
node register window holds the fabric response for 176 cycles BY DESIGN,
and an upset that loses that response leaves a two-stage in-order core
waiting for ever with no fault of its own.  Nothing in this repository
had measured that, and without the disarmed run "the watchdog escalated"
would not be a catch rate.

AND A CATCH IS A PORT EVENT, NEVER A TIMEOUT.  `wdog_first` is the cycle
of a transition on `nmi_o`, `wdog_rst_o` or `wdog_no`.  A run that ends
because the simulation budget expired has no such transition and can
never be counted as caught.
"""

import argparse
import concurrent.futures
import csv
import os
import random
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import npu_targets as targets                          # noqa: E402

# A seed of this campaign's own.  docs/42 uses 0x42F12026 and docs/16
# 0x16F12026; the convention is the document number in the top byte, so
# that two campaigns cannot silently share a draw sequence.
SEED = 0x52F12026

# fi_npu.c's fail-mask bits, and this is the one place they are written
# down outside the C.  They are here rather than parsed because the
# campaign has to be able to say WHICH check failed, and a bit number a
# reader has to go and look up is a bit number that gets misread.
F_BRINGUP = 1 << 0
F_LEN     = 1 << 1
F_STREAM  = 1 << 2
F_STATE   = 1 << 3
F_TELEM   = 1 << 4
F_CNT     = 1 << 5
F_TIMEOUT = 1 << 6

# The three that are comparisons against sw/golden/lif_core.py.
F_MODEL_SPIKES = F_LEN | F_STREAM
F_MODEL_STATE  = F_STATE
F_MODEL        = F_MODEL_SPIKES | F_MODEL_STATE


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


def verify_deposit(rec, site, bit):
    """The deposit landed, on the requested bit, inside the register.

    docs/41 section 8.1's fourth honesty check and docs/42 section 5.1
    control 5, and it is a HARD FAILURE rather than a skip: a deposit
    that missed must never be allowed to become a quiet MASKED record.

    IT IS CALLED FROM INSIDE THE WORKER AND NOT AFTER THE CAMPAIGN, and
    that is a change from hw/soc/fi/campaign.py rather than a
    transcription of it.  The first run of this campaign verified all
    1,400 simulations at the end, found an X-valued target in the queue
    storage on the first record it checked, and threw away thirty-seven
    minutes of wall time that had already been spent.  A check that can
    fail should fail on the first record.

    The X case is called out separately because it has a specific cause
    and a specific fix.  `aer_fifo`'s storage and its parity bank have no
    reset, so an unwritten slot is X, and `x ^ 1` is x: the deposit
    lands, changes nothing, and the run classifies MASKED.  tb_soc_npu_fi.v
    pre-fills both with the 0xF0F0 sentinel for exactly this reason and
    its header is the argument; this message is what says so when the
    fill does not cover something.
    """
    if i(rec, "hit") != 1:
        sys.exit("a deposit missed its target: %s (%s) bit %d"
                 % (site.name, site.path, bit))
    if i(rec, "width") <= bit:
        sys.exit("bit %d is outside %s's %d bits"
                 % (bit, site.name, i(rec, "width")))
    if "x" in rec["before"].lower() or "x" in rec["after"].lower():
        sys.exit("%s (%s) is X at the injection cycle: before=%s after=%s. "
                 "An injection into an X bit measures nothing -- see the "
                 "sentinel-fill section of tb_soc_npu_fi.v's header."
                 % (site.name, site.path, rec["before"], rec["after"]))
    if i(rec, "sentinel") != 1:
        sys.exit("the queue sentinel fill did not run before the deposit")
    before = int(rec["before"], 16)
    after = int(rec["after"], 16)
    if after != before ^ (1 << bit):
        sys.exit("a deposit did not flip exactly the requested bit: %s bit "
                 "%d, %032x -> %032x" % (site.name, bit, before, after))


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


def h(rec, key):
    return int(rec[key], 16)


def answer(rec):
    """Everything this campaign treats as the run's RESULT.

    The whole of what the program published, plus the console and
    `core_sleep_o`.  Wider than docs/42's, on purpose, because this
    program publishes more: the collected stream's signature, the event
    count, the hardware's own in/out counts, the cause register, the
    status word and three drop counters are all things a bench or an
    operator could read, and an upset that moved one of them left the
    part in a state the clean run did not end in.

    Deliberately NOT the cycle count, for docs/42 section 5's reason: an
    inference that produced the right answer forty cycles late produced
    the right answer.  `cycles` is carried as a separate per-record fact.
    """
    return (rec["sig"], rec["mask"], i(rec, "rounds"),
            rec["exit"], rec["magic"],
            i(rec, "console_chars"), rec["console_hash"],
            i(rec, "console_framing"),
            i(rec, "nev"), rec["cnt"], rec["cause"], rec["status"],
            rec["drop"], rec["ovf"], rec["oor"],
            # core_sleep_o at the end of the run.  tb_soc_fi.v's header
            # records the upset that put it in the compared result: a
            # core that posts the right answer and then spins for ever is
            # a different machine and a bench watching that pin says so.
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

    UNLIKE docs/42, THIS IS BACKED BY THE SPECIFICATION.  docs/42
    section 3 could only read a nonzero fail mask as "the program
    noticed", because its checks were dual computations with no external
    reference.  Three of the seven bits here -- F_LEN, F_STREAM and
    F_STATE -- are comparisons against constants sw/golden/lif_core.py
    produced at build time, so a run that sets one of them has a WRONG
    ANSWER and not merely an unhappy program.

    The distinction is used and not merely stated: `model_wrong()` below
    is the subset that is an answer, and the report keeps it apart from
    the announcement.
    """
    return rec["mask"] != golden["mask"] or rec["exit"] != golden["exit"]


def model_wrong(rec):
    """The GOLDEN MODEL says the inference was wrong.

    A strictly stronger statement than `sw_flagged`, which also fires on
    a bring-up complaint, a moved counter or a timeout.
    """
    return (h(rec, "mask") & F_MODEL) != 0


def model_state_only(rec):
    """The neuron state file is wrong and the spike stream is right.

    THIS IS THE CLASS docs/42 SECTION 9 SAYS ITS ORACLE CANNOT SEE.  An
    upset that leaves V or R wrong without producing a wrong spike inside
    this stimulus is MASKED under an output-only oracle; docs/16 section
    1.6 names it ("has not been masked; it has been deferred") and keeps
    `spikes_ok` and `state_ok` apart for exactly this reason.
    """
    m = h(rec, "mask")
    return (m & F_MODEL_STATE) != 0 and (m & F_MODEL_SPIKES) == 0


def trap_seen(rec, golden):
    """The core took an exception the golden run does not take.

    A RISC-V architectural announcement.  Reachable here in a way it is
    not in docs/42: the node register window RAISES A BUS ERROR on a
    reserved address, a sub-word write or a node index that is not
    instantiated (docs/51 section 6), so an upset in `win_err_q` or in
    the captured address is a load access fault at the core.
    """
    return i(rec, "traps") > i(golden, "traps")


def alert_seen(rec):
    """One of Ibex's own alert pins fired.

    `bool(...)` and not the bare `or` chain, for docs/42's reason: the
    value is written into records.csv, and an int there serialises as 0/1
    while every other flag serialises as False/True, so `--replay` would
    read every alert as absent.
    """
    return bool(i(rec, "alert_minor") or i(rec, "alert_int")
                or i(rec, "alert_bus") or i(rec, "dblfault"))


def npu_flagged(rec, golden):
    """THE BLOCK'S OWN ANNOUNCEMENT, read by a load the core executed.

    docs/16 section 1.6's DETECTED condition, carried across to this
    design: a fault bit in the cause register, a queue drop, or one of
    the die's own fault counters.  Every one of these is
    software-visible, which is the property that makes it an
    announcement rather than a bench observation.

    The cause register's EVT bit is deliberately excluded: it is a LEVEL
    that means "the capture queue is not empty" (docs/51 section 9) and
    it is not a fault report.

    THE MASK IS EVERY FAULT BIT THE BLOCK HAS AND IT IS DERIVED, not
    written out.  docs/52 ran with bits 1..6 listed one at a time;
    docs/55 added five more, and a hand-written mask would have gone on
    reporting "silent to every hardware channel" for events the block had
    just learned to announce -- which is the single most flattering way
    this campaign could have been wrong about its own hardening.
    `NCAUSE` is parsed out of hw/soc/rtl/soc_npu.v so that a bit added to
    the block cannot be left out of the set here, and
    hw/soc/tb/sw/soc_npucfg.h's NPUCFG_C_FAULTS is the same set on the
    software side, defined once there for the same reason.

    BUSSTAT's three NPU counters are NOT in this condition, and that is
    deliberate rather than an omission.  They are a second, independent
    view of the same events -- the cause register's Q_COR, Q_DET and
    CFG_TMR bits are what make a record DETECTED -- and folding both into
    one announcement test would make it impossible to say later whether
    the two agreed.  `bst_cor`, `bst_det` and `bst_tmr` are carried as
    their own columns and section 5 of docs/55 compares them.
    """
    C_FAULTS = ((1 << targets.NCAUSE) - 1) & ~1      # every bit but EVT
    return (bool(h(rec, "cause") & C_FAULTS)
            or h(rec, "drop") != h(golden, "drop")
            or h(rec, "ovf") != h(golden, "ovf")
            or h(rec, "oor") != h(golden, "oor")
            or i(rec, "npu_irq") != i(golden, "npu_irq"))


def corrected(rec):
    """A correction mechanism inside the connection moved.

    There is exactly one: `aer_fifo`'s triple-redundant queue pointers,
    which vote and reload every replica from the vote on the next edge.
    `ptr_mismatch` reports a corrected replica disagreement.

    IT IS READ HIERARCHICALLY OUT OF THE SIMULATION AND IT IS NOT A PIN.
    soc_npu.v brings `ptr_mismatch` out of both queue instances and
    connects it to nothing -- docs/51 section 14 item 1 -- so in silicon
    a corrected pointer upset is indistinguishable from no upset at all.
    This function therefore measures what the mechanism DID; it does not
    claim an operator could see it.  docs/43's `corrected()` carries the
    identical caveat for the register file and docs/52 section 8 ranks
    closing it.
    """
    return i(rec, "q_ptr_mm") > 0


def detected_no_channel(rec):
    """A DETECTION mechanism moved and had nowhere to report it.

    `aer_fifo`'s entry parity discards a corrupted queue entry and raises
    `par_err`; its dual-rail rd_valid drops the read answer and raises
    `rv_mismatch`.  Both are brought out of the instance in soc_npu.v and
    connected to nothing.

    This is NOT counted as an announcement, and that is the whole point:
    the event is gone, the queue is consistent, and no software and no
    pin says so.  docs/52 section 8 is the finding.
    """
    return i(rec, "q_par_err") > 0 or i(rec, "q_rv_mm") > 0


def classify(rec, golden):
    """Exactly one class, in docs/16 section 1.6's order."""
    ann_wdog = wdog_fired(rec)
    ann_sw = sw_flagged(rec, golden)
    ann_trap = trap_seen(rec, golden)
    ann_alert = alert_seen(rec)
    ann_npu = npu_flagged(rec, golden)
    announced = ann_wdog or ann_sw or ann_trap or ann_alert or ann_npu
    out_ok = completed(rec) and answer(rec) == answer(golden)

    if not completed(rec) and not announced:
        cls = "HANG"
    elif announced:
        cls = "DETECTED"
    elif not out_ok:
        cls = "SDC"
    elif corrected(rec):
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
        "ann_npu": ann_npu,
        "model_wrong": model_wrong(rec),
        "state_only": model_state_only(rec),
        "spikes_bad": bool(h(rec, "mask") & F_MODEL_SPIKES),
        "state_bad": bool(h(rec, "mask") & F_MODEL_STATE),
        "timed_out": bool(h(rec, "mask") & F_TIMEOUT),
        "bringup_bad": bool(h(rec, "mask") & F_BRINGUP),
        "silent_corr": corrected(rec),
        "silent_det": detected_no_channel(rec),
        "q_ptr_mm": i(rec, "q_ptr_mm"),
        "q_par_err": i(rec, "q_par_err"),
        "q_rv_mm": i(rec, "q_rv_mm"),
        "fetch_er": i(rec, "fetch_er"),
        # docs/55's mechanisms, at the bench.
        "ser_to": i(rec, "ser_to"),
        "win_to": i(rec, "win_to"),
        "win_orph": i(rec, "win_orph"),
        "tmr_ev": i(rec, "tmr_ev"),
        # docs/56 H4: the show-ahead adapter's bound, and the
        # longest run of cycles its request stayed outstanding.
        # The second is the OUTCOME the bound exists to prevent
        # and is the only column that can tell a record in which
        # the adapter recovered from one in which it wedged.
        "oh_to": i(rec, "oh_to"),
        "oh_req_max": i(rec, "oh_req_max"),
        # docs/56 H5: cycles in which the AER strobe flag and the
        # state that implies it disagreed, so the pin was held quiet.
        "aer_mm": i(rec, "aer_mm"),
        # ... and what an OPERATOR saw of them, read out of BUSSTAT by a
        # load the core executed.  The pair is the point: docs/52 section
        # 10's finding was not that the mechanisms failed, it was that
        # nothing could see them work, so a bench count with no matching
        # operator count would be the same finding again.
        "bst_cor": h(rec, "bst_cor"),
        "bst_det": h(rec, "bst_det"),
        "bst_tmr": h(rec, "bst_tmr"),
        "wdog_stage": wdog_stage(rec),
        "wdog_first": i(rec, "wdog_first"),
        "cycles": i(rec, "cycles"),
        "at_ser": i(rec, "at_ser"),
        "at_win": i(rec, "at_win"),
        "at_ev": i(rec, "at_ev"),
        "mask": rec["mask"],
    }


# =====================================================================
# the draw
# =====================================================================
def draws(stratum, n, window):
    """`n` (site, bit, cycle) triples for one stratum.

    A bit is drawn UNIFORMLY OVER THE STRATUM'S FLIP-FLOPS, not over its
    sites: `tx` is 40 bits and `ser_sck_o` is one, and weighting by site
    would over-sample the narrow ones forty to one.  The cycle is drawn
    uniformly inside the MEASURED window of the clean run.

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


def silent_wrong(row):
    """A CLASSIFIED row in which the inference was wrong and no HARDWARE
    channel said so.

    docs/52 section 6.2 defines this figure and computed it by hand off
    the records; docs/56 needs it per stratum to decide which of the
    event engine's five sub-strata carries the rate, so it lives here
    and the report prints it.

    `ann_sw` IS DELIBERATELY NOT IN THE LIST.  It is `fi_npu.c`'s own
    model check, and counting it would make every corrupted inference
    announced by construction -- the reason docs/52 section 6.2 says the
    SDC column must not be quoted on its own.  The four channels below
    are the ones that exist in silicon with no test program behind them.
    """
    return bool(row["model_wrong"]) and not (
        row["ann_npu"] or row["ann_trap"] or row["ann_alert"]
        or row["ann_wdog"])


def weighted_rate(rows, col, cls, strata):
    """The rate of one class over `strata`, weighted by their bits, and
    its 95 % half-width.

    The campaign draws equally from strata of very unequal size -- 100
    from a 13-bit register bank and 100 from a 304-bit queue store -- so
    the block-level figure is the bit-weighted combination of the
    per-stratum rates and its variance is the weighted combination of
    theirs.  docs/42 section 4.5 states the estimator and this is it.

    `strata` is a parameter and not `targets.STRATA` because the frozen
    die must not be inside a rate that a hardening decision is made
    against: docs/52 section 3 computes the connection's figure over the
    connection's bits and reports the die's separately.
    """
    total_bits = sum(targets.stratum_bits(s) for s in strata)
    p = 0.0
    var = 0.0
    for stratum in strata:
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
    samples are in the low hundreds at best and docs/16 section 7.1
    records an earlier campaign's numbers being read more precisely than
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


OPEN_STRATA = [s for s in targets.STRATA if s not in targets.FROZEN]


# =====================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True,
                    help="directory hw/soc/flow/fi_npu.sh wrote")
    ap.add_argument("--replay", default=None,
                    help="re-print the report from an existing records.csv "
                         "without re-running the simulations")
    ap.add_argument("--directed", default=None,
                    help="a records.csv whose injections are re-run "
                         "VERBATIM against this build -- same site, same "
                         "bit, same cycle, different design")
    ap.add_argument("--directed-filter", default=None,
                    help="only rows whose `truth` column equals this")
    ap.add_argument("--draws", type=int, default=100,
                    help="injections per stratum")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--vvp", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--tag", default="",
                    help="a label written into the log, for a build that "
                         "is not the design of record")
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

    image = os.path.join(build, "tb_soc_npu_fi.vvp")
    if not os.path.exists(image):
        sys.exit("missing %s: run hw/soc/flow/fi_npu.sh first" % image)

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
                          "q_ptr_mm", "q_par_err", "q_rv_mm", "fetch_er",
                          "ser_to", "win_to", "win_orph", "tmr_ev",
                          "oh_to", "oh_req_max", "aer_mm",
                          "bst_cor", "bst_det", "bst_tmr",
                          "at_ser", "at_win", "at_ev"):
                    if k in r:
                        r[k] = int(r[k])
                # EVERY BOOLEAN COLUMN, AND `frozen` IS ONE OF THEM.
                #
                # csv writes True as the string "True" and False as
                # "False", and a non-empty string is truthy -- so a
                # `frozen` left uncoerced makes `not r["frozen"]` false
                # for every row, the CONNECTION aggregate empty and the
                # FROZEN DIE aggregate 700 wide.  The per-stratum tables
                # and every design-weighted figure were unaffected,
                # because they select on `stratum`; the two summary rows
                # were wrong and nothing else was, which is exactly how
                # this survives being looked at.
                #
                # Caught by running --replay against the run's own log
                # and diffing, which is the check docs/44 section 9.2
                # makes of two campaigns and this file now makes of one
                # campaign against itself.  hw/soc/fi/campaign.py's
                # `alert_seen` docstring records the same defect in the
                # other direction: an int serialises as 0/1 while every
                # other flag serialises as False/True, and the replay
                # read every alert as absent.
                for k in ("armed_out_ok", "disarmed_out_ok", "armed_done",
                          "disarmed_done", "ann_sw", "ann_trap", "ann_alert",
                          "ann_wdog", "ann_npu", "model_wrong", "state_only",
                          "spikes_bad", "state_bad", "timed_out",
                          "bringup_bad", "silent_corr", "silent_det",
                          "frozen"):
                    if k in r:
                        r[k] = r[k] in ("True", "1")
                rows.append(r)
        report(say, rows, {})
        log.close()
        return

    if args.tag:
        say("BUILD TAG: %s", args.tag)

    # =================================================================
    # CONTROL 1: the elaborated design is the one npu_targets.py
    # describes
    # =================================================================
    probe_runner = Runner(vvp, image, 400000)
    dump = probe_runner.run(dumpsites=True)
    elaborated = []
    count = -1
    for line in dump["_raw"].splitlines():
        if line.startswith("SITE "):
            _, idx, stratum, name, width, path = line.split(None, 5)
            elaborated.append((int(idx), stratum, name, int(width),
                               path.strip()))
        elif line.startswith("SITECOUNT "):
            count = int(line.split()[1])
    if count != len(targets.SITES):
        sys.exit("the testbench elaborated %d sites, npu_targets.py lists %d"
                 % (count, len(targets.SITES)))
    for idx, stratum, name, width, path in elaborated:
        want = targets.SITES[idx]
        got = (stratum, name, width, path)
        exp = (want.stratum, want.name, want.width,
               "dut.u_npu." + want.path)
        if got != exp:
            sys.exit("site %d disagrees.\n  elaborated %s\n  npu_targets.py %s"
                     % (idx, got, exp))
    say("control 1: %d sites, %d bits, every path, index and width agrees "
        "with npu_targets.py", count, sum(s.width for s in targets.SITES))

    # CONTROL 1b: no target is a voted or otherwise continuously driven
    # wire.  docs/41 section 8.1 records this campaign's ancestor
    # depositing into a driven voter output twice and reporting the
    # result as if it said something about the replicas.  Every
    # `evq_ptr` target must end in `.bits`, which is aer_ptr_bank's and
    # aer_flag_rail's STORAGE and never their `q` output.
    for s in targets.stratum_sites("evq_ptr"):
        if s.name.endswith("drop_cnt"):
            continue
        if not s.path.endswith(".bits"):
            sys.exit("evq_ptr site %s is %s, which is not replica storage"
                     % (s.name, s.path))
    # AND THE SAME FOR docs/55's CAUSE BANK.  soc_tmr_bank's `q_o` is a
    # continuously driven function of `bits`, so a deposit there would be
    # overwritten in the same delta cycle and the record would say
    # nothing about the replicas -- which is what docs/41 section 8.1
    # records this campaign's ancestor doing twice.  The three cause-bank
    # sites are the only ones in `cfgreg` that name a submodule; the two
    # self-clearing pulses are plain registers in soc_npu.v by decision.
    n_replica = 0
    for s in targets.stratum_sites("cfgreg"):
        if "u_cfg_" not in s.path:
            continue
        n_replica += 1
        if not s.path.endswith(".bits"):
            sys.exit("cfgreg site %s is %s, which is not replica storage"
                     % (s.name, s.path))
    if n_replica != 3:
        sys.exit("the cause bank has %d replica sites and must have three; "
                 "a campaign that drew from two of three replicas would "
                 "under-report a vote it never made" % n_replica)
    say("control 1b: every replicated target is a `.bits` storage register "
        "and not a voted wire, in both queues and in all three replicas "
        "of the %d-bit cause bank", targets.PROT_W)

    # =================================================================
    # CONTROL 2: the golden run, and the window it measures
    # =================================================================
    golden = probe_runner.run(armed=True)
    if not completed(golden):
        sys.exit("the clean run did not complete:\n" + golden["_raw"][-3000:])
    for k, v in (("mask", "00000000"), ("exit", "00000000"),
                 ("magic", "600dc0de")):
        if golden[k] != v:
            sys.exit("the clean run's %s is %s, expected %s"
                     % (k, golden[k], v))
    if wdog_fired(golden):
        sys.exit("the clean run escalated the watchdog. The campaign cannot "
                 "attribute an escalation to an injection if the workload "
                 "produces one on its own.")
    if i(golden, "traps") or alert_seen(golden):
        sys.exit("the clean run took a trap or raised an alert; every "
                 "announcement channel must be silent in it")
    if i(golden, "console_framing"):
        sys.exit("the clean run has console framing errors")

    # CONTROL 2b: THE NPU'S OWN CHANNELS ARE SILENT TOO, and the queues'
    # protection has not fired.  A clean run in which a queue had already
    # discarded an entry or corrected a pointer would make every
    # CORRECTED record in the campaign unattributable.
    for k in ("cause", "drop", "ovf", "oor"):
        if h(golden, k) != 0:
            sys.exit("the clean run's %s is %s and must be zero: no fault "
                     "channel may be raised with nothing injected"
                     % (k, golden[k]))
    for k in ("q_ptr_mm", "q_par_err", "q_rv_mm", "fetch_er"):
        if i(golden, k) != 0:
            sys.exit("the clean run's %s is %d: the queues' protection "
                     "fired with nothing injected and could not then be "
                     "attributed to an injection" % (k, i(golden, k)))
    if i(golden, "npu_irq") != 0:
        sys.exit("the clean run raised the NPU interrupt; IRQ_MASK resets "
                 "to zero and this workload never writes it")
    say("control 2: clean run %d cycles, sig %s, %d console characters, "
        "%d events collected, CNT=%s, no announcement of any kind",
        i(golden, "cycles"), golden["sig"], i(golden, "console_chars"),
        i(golden, "nev"), golden["cnt"])
    say("control 2b: cause, both drop counters, the die's two fault "
        "counters, the interrupt line and all three queue-protection "
        "reports are zero in the clean run")

    win_open, win_close = i(golden, "win_open"), i(golden, "win_close")
    if not (0 < win_open < win_close <= i(golden, "cycles")):
        sys.exit("the measured injection window is not sane: %d..%d of %d"
                 % (win_open, win_close, i(golden, "cycles")))
    win_len = win_close - win_open
    say("           measured injection window %d..%d (%d cycles, %.0f %% "
        "of the run)", win_open, win_close, win_len,
        100.0 * win_len / i(golden, "cycles"))

    # CONTROL 2c: THE PROGRAM'S HANG DETECTOR HAS MARGIN.  fi_npu.c
    # bounds a barrier wait at FI_SPIN_MAX polls and publishes the
    # largest run of empty polls it actually saw.  If the bound is not
    # comfortably above the measurement, an injected run that was merely
    # slow would report F_TIMEOUT and be classified as a detected fault.
    spins = i(golden, "spins")
    say("control 2c: the clean run's longest empty-poll run is %d; "
        "fi_npu.c's FI_SPIN_MAX is 168, which is %.1fx it",
        spins, 168.0 / max(spins, 1))
    if spins * 4 > 168:
        sys.exit("the clean run came within 4x of the program's own hang "
                 "bound; raise FI_SPIN_MAX")

    # THE EXPOSURE ARITHMETIC, measured on the clean run.  docs/52
    # section 7.  A block that is slow is exposed for longer, and a
    # per-flip-flop rate cannot say that.
    ser_bits = targets.stratum_bits("ser")
    conn_bits = targets.connection_bits()
    say("")
    say("control 2d: EXPOSURE. Of the %d cycles of the measured window:",
        win_len)
    for name, key, strata in (("the serial transport", "ser_busy", ("ser",)),
                              ("the node window FSM", "win_busy", ("window",)),
                              ("the event engine", "ev_busy", ("engine",))):
        busy = i(golden, key)
        bits = sum(targets.stratum_bits(s) for s in strata)
        say("   %-22s busy %6d (%5.1f %% of the window) and %3d of the "
            "%d connection flip-flops (%4.1f %%)",
            name, busy, 100.0 * busy / win_len, bits, conn_bits,
            100.0 * bits / conn_bits)
    say("   [the transport is %.1f %% of the flip-flops and %.1f %% of the "
        "time: docs/52 section 7]",
        100.0 * ser_bits / conn_bits,
        100.0 * i(golden, "ser_busy") / win_len)
    say("")

    # =================================================================
    # CONTROL 3: it reproduces, and it is identical with the watchdog
    # held off
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
    timeout_clk = (i(golden, "wdog_rld") + 1) * i(golden, "wdog_pre")
    ladder_clk = 2 * timeout_clk
    budget = 2 * i(golden, "cycles") + 6 * ladder_clk
    need = win_close + 4 * ladder_clk + i(golden, "cycles")
    if budget < need:
        budget = need
    runner = Runner(vvp, image, budget)
    say("           budget %d cycles: the latest cycle an injection can be "
        "drawn at is %d, a full escalation ladder is %d clocks, so every "
        "run that does not escalate had at least %.1f ladders in which to "
        "do so", budget, win_close, ladder_clk,
        (budget - win_close) / float(ladder_clk))
    say("           kick cadence: %d kicks, interval %d..%d clocks; timeout "
        "%d clocks (reload %d, prescale %d)",
        i(golden, "kicks"), i(golden, "kick_min"), i(golden, "kick_max"),
        timeout_clk, i(golden, "wdog_rld"), i(golden, "wdog_pre"))
    if i(golden, "kick_max") >= timeout_clk:
        sys.exit("the clean run's longest interval between kicks is not "
                 "shorter than the timeout it arms; the workload would "
                 "escalate on its own")

    # =================================================================
    # CONTROL 4: the injector reaches the design, in both directions
    # =================================================================
    # POSITIVE.  Bit 15 of `cnt_in`, the event engine's own count of what
    # it has delivered to the die.  It only ever INCREMENTS, and it ends
    # the clean run at 22, so a flip of bit 15 is never undone by the
    # design's own writes: the program's cross-check of NPUCFG.CNT
    # against the stream it collected must fail.  MASKED is impossible if
    # the deposit landed, which is exactly what a positive control needs.
    #
    # THIS CONTROL WAS `ctrl_in_en` UNTIL docs/55 AND IT HAD TO CHANGE,
    # which is worth recording rather than quietly editing.  That
    # register is now a field of a TRIPLE-REDUNDANT word: a single
    # deposit into one replica is masked by the vote, so the old control
    # would have failed -- correctly -- on a design that had just been
    # hardened against exactly the thing the control was exercising.  The
    # fix is a new positive control on state that is still single, plus a
    # NEW control 4d that asserts the vote does mask it and does report
    # it.  Moving the old control's threshold until it passed would have
    # been the other option, and it is the one docs/52 section 5.1 says
    # makes docs/41 section 6.6's list longer.
    #
    # docs/42 section 8.5 item 1 records what a campaign in which the
    # deposit never landed looks like: almost entirely MASKED, which is
    # exactly what a healthy design looks like.  That is why this is a
    # gate and not a report.
    # THE CYCLE IS DERIVED FROM A MEASUREMENT AND NOT FROM A FRACTION OF
    # THE WINDOW.  The window opens before the bring-up, which is two
    # dozen 176-cycle serial frames, so an early draw lands on a register
    # the program has not written yet and then writes -- and MASKED is
    # then the correct answer to a control that requires it not to be.
    # The testbench reports the cycle at which `ctrl_in_en` first goes
    # high; the deposit is placed a quarter of the way from there to the
    # end of the window.  The first version of this control drew at
    # win_open + win_len/8, failed, and was right to.  docs/52 section
    # 6.1.
    mid = (win_open + win_close) // 2
    en_at = i(golden, "en_at")
    if not (win_open < en_at < win_close):
        sys.exit("the block's enable is not inside the measured window: "
                 "en_at=%d, window %d..%d" % (en_at, win_open, win_close))
    live_cycle = en_at + (win_close - en_at) // 4
    pos_site = next(k for k, s in enumerate(targets.SITES)
                    if s.name == "cnt_in")
    pos = runner.run(site=pos_site, bit=15, cycle=live_cycle)
    pcls, _ = classify(pos, golden)
    verify_deposit(pos, targets.SITES[pos_site], 15)
    if pcls == "MASKED":
        sys.exit("bit 15 of cnt_in, deposited mid-inference, classified "
                 "MASKED. That counter only increments and ends at 22, so "
                 "the flip cannot be undone: the deposit is not landing and "
                 "the campaign would measure nothing.")
    say("control 4a: the block is enabled at cycle %d; bit 15 of the "
        "engine's cnt_in at cycle %d classifies %s, so deposits land",
        en_at, live_cycle, pcls)

    # CONTROL 4d: THE CAUSE BANK'S VOTE MASKS A DEPOSIT AND REPORTS IT.
    #
    # New in docs/55, and it is the only control in this campaign that
    # exercises a mechanism this work built rather than one it measures.
    # A deposit into ONE replica of the protected word must be:
    #   * masked -- the inference still produces the golden answer;
    #   * corrected -- soc_tmr_bank is written from the vote on every
    #     edge, so the replica is repaired on the next cycle;
    #   * and ANNOUNCED, in two independent places: IRQ_CAUSE.CFG_TMR,
    #     which the program reads with a load, and BUSSTAT's CNT_NPUTMR,
    #     which it also reads with a load.
    #
    # A design whose three replicas had been merged into one by the
    # synthesiser would still pass this control, because it deposits into
    # RTL.  sw/tests/test_soc_synthesis_guards.py is the check that they
    # are three in the netlist, and neither is a substitute for the
    # other -- docs/41 section 6 makes that division and this is the same
    # one.
    tmr_site = next(k for k, s in enumerate(targets.SITES)
                    if s.name == "cfg_a")
    tpos = runner.run(site=tmr_site, bit=0, cycle=live_cycle)
    verify_deposit(tpos, targets.SITES[tmr_site], 0)
    tcls, tf = classify(tpos, golden)
    # THE ORACLE HERE IS THE MODEL AND NOT THE COMPARED RESULT, and the
    # first run of this control is why that is written down rather than
    # assumed.  `answer()` compares the WHOLE published result, and that
    # includes the cause register -- which this deposit is SUPPOSED to
    # move, because IRQ_CAUSE.CFG_TMR is the announcement the vote makes.
    # So `out_ok` is false on a record whose inference is exactly right,
    # and a control written against `out_ok` fails on a design that is
    # working.  That is docs/52 section 9's second finding -- "it
    # separates a wrong answer from a moved counter" -- turned into a
    # gate, and without the golden model this control could not be
    # written at all.
    say("control 4d: bit 0 of cause-bank replica A at cycle %d classifies "
        "%s. The MODEL says the inference is %s; the compared result "
        "differs only because the cause register moved (IRQ_CAUSE=%s). "
        "The voter fired %s time(s) and BUSSTAT.CNT_NPUTMR reads %s",
        live_cycle, tcls, "WRONG" if tf["model_wrong"] else "RIGHT",
        tpos["cause"], i(tpos, "tmr_ev"), tpos["bst_tmr"])
    if tf["model_wrong"]:
        sys.exit("a single-bit deposit into one replica of the protected "
                 "word produced a WRONG INFERENCE against "
                 "sw/golden/lif_core.py. The vote is not masking it.")
    if i(tpos, "nev") != i(golden, "nev") or tpos["sig"] != golden["sig"]:
        sys.exit("a single-bit deposit into one replica of the protected "
                 "word changed the event stream or the neuron state file")
    if not (h(tpos, "cause") & (1 << targets.C_CFG_TMR)):
        sys.exit("the vote masked the deposit and IRQ_CAUSE.CFG_TMR is "
                 "clear: the correction happened and the part did not say "
                 "so, which is exactly the finding docs/52 section 10 made "
                 "and this work exists to close")
    if i(tpos, "tmr_ev") == 0:
        sys.exit("a single-bit deposit into one replica of the protected "
                 "word produced no voter mismatch at all; the three "
                 "replicas are not three")
    if h(tpos, "bst_tmr") == 0:
        sys.exit("the voter fired and BUSSTAT's CNT_NPUTMR is still zero: "
                 "the fault line does not reach the counter, which is the "
                 "whole of docs/55 H2's claim")

    # A SECOND POSITIVE, INSIDE THE FROZEN DIE, because the two halves of
    # the design are reached by different hierarchical paths and a case
    # arm that works for one says nothing about the other.  Bit 31 of the
    # die's own receive shift register, mid-frame.
    die_site = next(k for k, s in enumerate(targets.SITES)
                    if s.name == "die_rx_sh")
    dpos = runner.run(site=die_site, bit=31, cycle=mid)
    dcls, _ = classify(dpos, golden)
    verify_deposit(dpos, targets.SITES[die_site], 31)
    say("control 4b: bit 31 of the die's rx_sh at cycle %d classifies %s, "
        "so deposits reach inside hw/rtl/pilot_top.v as well", mid, dcls)

    # NEGATIVE.  Bit 7 of the capture queue's drop counter.  Nothing in
    # this SoC can overflow the capture queue -- the engine writes it
    # only when it has room -- and soc_npu.v leaves `u_cap`'s drop count
    # UNCONNECTED, so no software and no pin can read it.  An upset there
    # must be possible to classify MASKED, or the oracle is too tight.
    #
    # AND IT IS THE ONE SITE IN THIS CAMPAIGN THAT DOES NOT EXIST IN THE
    # NETLIST.  hw/soc/flow/fi_npu_coverage.sh reports exactly eight bits
    # that `opt_clean` removes, and they are these, for the same reason
    # this control uses them: nothing reads them.  So MASKED here is
    # guaranteed by construction rather than measured, and the control is
    # weaker than docs/42's `mcycle` for that reason.  It is kept because
    # a campaign in which nothing can be MASKED is a campaign with an
    # oracle that is too tight, and this is the cheapest way to show that
    # is not the case.  docs/52 sections 6.1 and 9 say both halves.
    neg_site = next(k for k, s in enumerate(targets.SITES)
                    if s.name == "cap_drop_cnt")
    neg = runner.run(site=neg_site, bit=7, cycle=mid)
    verify_deposit(neg, targets.SITES[neg_site], 7)
    ncls, _ = classify(neg, golden)
    say("control 4c: bit 7 of the capture queue's UNCONNECTED drop "
        "counter classifies %s", ncls)
    if ncls != "MASKED":
        say("           (and that is worth a look: docs/52 section 6.4)")

    # =================================================================
    # Directed replay: somebody else's injections, against this build
    # =================================================================
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
        # KEYED ON THE PATH AND NOT ON THE NAME.  campaign.py's comment
        # records what a name lookup cost docs/43: site names are not
        # unique across strata, a replay went into the wrong register,
        # the deposit landed outside its width, and the record came back
        # MASKED looking exactly like a hardening that had fixed it.
        by_path = {s.path: k for k, s in enumerate(targets.SITES)}
        say("")
        say("directed replay of %d injections from %s", len(want),
            args.directed)
        say("%-14s %5s %8s  %-10s %-9s  %-10s %-10s %-8s %s"
            % ("site", "bit", "cycle", "was(armed)", "was(truth)",
               "now(armed)", "now(dis)", "now(truth)", "mechanism"))
        # RUN IN PARALLEL, exactly as the campaign below does.
        #
        # It was a serial loop until docs/55, which is fine for the three
        # records docs/52 section 7.2 replayed and is not fine for the
        # 616 this one does: at about eight seconds a simulation the
        # difference is two and a half hours against fifteen minutes.
        # The ORDER of the report is preserved by mapping over the plan
        # rather than collecting as they finish, so two runs of the same
        # replay produce diffable logs -- which is the property docs/52
        # section 5.4 item 3 had to add to `--replay` after finding it
        # missing.
        for _, path, _, _, _, _ in want:
            if path not in by_path:
                sys.exit("path %s is not in this build's site list" % path)

        def djob(item):
            _, path, bit, cycle, _, _ = item
            idx = by_path[path]
            a = runner.run(site=idx, bit=bit, cycle=cycle, armed=True)
            d = runner.run(site=idx, bit=bit, cycle=cycle, armed=False)
            # The same verification the campaign does, for the same
            # reason: a deposit that missed has to be a hard failure and
            # never a quiet MASKED that looks like a design that fixed it.
            verify_deposit(a, targets.SITES[idx], bit)
            verify_deposit(d, targets.SITES[idx], bit)
            return item, a, d

        out_rows = []
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=args.jobs) as ex:
            done = list(ex.map(djob, want))
        for (name, path, bit, cycle, was_truth, was_cls), a, d in done:
            acls, af = classify(a, golden)
            dcls, df = classify(d, golden)
            t = "OK" if df["out_ok"] else ("WRONG" if df["done"] else "DEAD")
            how = []
            if af["q_ptr_mm"]:
                how.append("ptr vote %d" % af["q_ptr_mm"])
            if af["q_par_err"]:
                how.append("entry parity %d" % af["q_par_err"])
            if af["q_rv_mm"]:
                how.append("rdv rails %d" % af["q_rv_mm"])
            if af["fetch_er"]:
                how.append("fetch bound %d" % af["fetch_er"])
            # docs/55's three mechanisms, named where they fired, so a
            # row that changed class between the two campaigns says WHY
            # rather than only THAT.
            if af["ser_to"]:
                how.append("frame bound %d" % af["ser_to"])
            if af["win_to"]:
                how.append("window bound %d" % af["win_to"])
            if af["win_orph"]:
                how.append("window orphan %d" % af["win_orph"])
            if af["tmr_ev"]:
                how.append("cause-bank vote %d" % af["tmr_ev"])
            if af["oh_to"]:
                how.append("show-ahead bound %d" % af["oh_to"])
            if af["aer_mm"]:
                how.append("AER strobe gate %d" % af["aer_mm"])
            if af["ann_wdog"]:
                how.append("watchdog stage %d" % af["wdog_stage"])
            say("%-14s %5d %8d  %-10s %-9s  %-10s %-10s %-8s %s"
                % (name, bit, cycle, was_cls, was_truth, acls, dcls, t,
                   ", ".join(how) if how else "-"))
            out_rows.append({"site": name, "path": path, "bit": bit,
                             "cycle": cycle,
                             "was_armed_cls": was_cls, "was_truth": was_truth,
                             "armed_cls": acls, "disarmed_cls": dcls,
                             "truth": t,
                             "armed_out_ok": af["out_ok"],
                             "model_wrong": af["model_wrong"],
                             "ann_wdog": af["ann_wdog"],
                             "ann_npu": af["ann_npu"],
                             "wdog_stage": af["wdog_stage"],
                             "q_ptr_mm": af["q_ptr_mm"],
                             "q_par_err": af["q_par_err"],
                             "q_rv_mm": af["q_rv_mm"],
                             "fetch_er": af["fetch_er"],
                             "ser_to": af["ser_to"],
                             "win_to": af["win_to"],
                             "win_orph": af["win_orph"],
                             "tmr_ev": af["tmr_ev"],
                             "oh_to": af["oh_to"],
                             "oh_req_max": af["oh_req_max"],
                             "aer_mm": af["aer_mm"],
                             "bst_cor": af["bst_cor"],
                             "bst_det": af["bst_det"],
                             "bst_tmr": af["bst_tmr"]})
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
        # Verified HERE, in the worker, so a bad deposit ends the
        # campaign at the first record rather than after every simulation
        # has been paid for.  See verify_deposit's docstring.
        verify_deposit(a, site, bit)
        verify_deposit(d, site, bit)
        return item, a, d

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for n, (item, a, d) in enumerate(ex.map(job, plan), 1):
            results.append((item, a, d))
            if n % 50 == 0:
                say("  ... %d of %d", n, len(plan))

    # =================================================================
    # Classify
    # =================================================================
    rows = []
    for (stratum, site_idx, site, bit, cycle), a, d in results:
        acls, af = classify(a, golden)
        dcls, df = classify(d, golden)
        if df["out_ok"]:
            t = "OK"
        elif df["done"]:
            t = "WRONG"
        else:
            t = "DEAD"
        rows.append({
            "stratum": stratum, "population": targets.POPULATION[stratum],
            "frozen": stratum in targets.FROZEN,
            "site": site.name, "path": site.path,
            "bit": bit, "cycle": cycle,
            "armed_cls": acls, "disarmed_cls": dcls,
            "truth": t,
            "armed_out_ok": af["out_ok"],
            "disarmed_out_ok": df["out_ok"],
            "armed_done": af["done"], "disarmed_done": df["done"],
            "ann_sw": af["ann_sw"], "ann_trap": af["ann_trap"],
            "ann_alert": af["ann_alert"], "ann_wdog": af["ann_wdog"],
            "ann_npu": af["ann_npu"],
            # The golden MODEL's verdict, and the split docs/16 section
            # 1.6 keeps: a wrong spike stream and a wrong neuron state
            # file are different failures and one of them is invisible to
            # an output-only oracle.
            "model_wrong": af["model_wrong"],
            "spikes_bad": af["spikes_bad"],
            "state_bad": af["state_bad"],
            "state_only": af["state_only"],
            "timed_out": af["timed_out"],
            "bringup_bad": af["bringup_bad"],
            "mask": af["mask"],
            # The queue protection, which is a BENCH observation.
            "silent_corr": af["silent_corr"],
            "silent_det": af["silent_det"],
            "q_ptr_mm": af["q_ptr_mm"], "q_par_err": af["q_par_err"],
            "q_rv_mm": af["q_rv_mm"], "fetch_er": af["fetch_er"],
            # docs/55: the two bounds and the cause bank's voter, at the
            # bench, beside what BUSSTAT told the program about them.
            "ser_to": af["ser_to"], "win_to": af["win_to"],
            "win_orph": af["win_orph"], "tmr_ev": af["tmr_ev"],
            "oh_to": af["oh_to"], "oh_req_max": af["oh_req_max"],
            "aer_mm": af["aer_mm"],
            "bst_cor": af["bst_cor"], "bst_det": af["bst_det"],
            "bst_tmr": af["bst_tmr"],
            "wdog_stage": af["wdog_stage"],
            "wdog_first": af["wdog_first"],
            "wdog_latency": (af["wdog_first"] - cycle
                             if af["wdog_first"] >= 0 else -1),
            "armed_cycles": af["cycles"],
            "disarmed_cycles": df["cycles"],
            # The exposure arithmetic, per record.
            "at_ser": af["at_ser"], "at_win": af["at_win"],
            "at_ev": af["at_ev"],
        })

    csv_path = os.path.join(out_dir, "records.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    say("records: %s", csv_path)

    report(say, rows, golden)
    log.close()


CLASSES = ["MASKED", "CORRECTED", "SDC", "DETECTED", "HANG"]


def _tbl(say, rows, col):
    say("%-10s %-22s %5s %5s  %s"
        % ("stratum", "population", "bits", "n",
           "".join("%10s" % c for c in CLASSES)))
    for stratum in targets.STRATA:
        sub = [r for r in rows if r["stratum"] == stratum]
        if not sub:
            continue
        counts = [sum(1 for r in sub if r[col] == c) for c in CLASSES]
        say("%-10s %-22s %5d %5d  %s"
            % (stratum, targets.POPULATION[stratum],
               targets.stratum_bits(stratum), len(sub),
               "".join("%10d" % c for c in counts)))
    for label, keep in (("CONNECTION", lambda r: not r["frozen"]),
                        ("FROZEN DIE", lambda r: r["frozen"])):
        sub = [r for r in rows if keep(r)]
        if not sub:
            continue
        counts = [sum(1 for r in sub if r[col] == c) for c in CLASSES]
        say("%-10s %-22s %5s %5d  %s"
            % (label, "", "", len(sub), "".join("%10d" % c for c in counts)))


def report(say, rows, golden):
    """Everything printed after the campaign, from the rows alone.

    Deliberately takes nothing but the records (and, where it has one,
    the golden record for context lines), so `--replay` on a saved
    records.csv reproduces the whole report without re-simulating and so
    no number in it can come from anywhere but the data.
    """
    conn = [r for r in rows if not r["frozen"]]

    # EVERY TABLE BELOW SELECTS ON `stratum`, so a record whose stratum
    # this build does not know about would be dropped from all of them
    # in silence.  That is not hypothetical: docs/56 split `engine` into
    # five, so replaying docs/52's or docs/55's records.csv against this
    # file leaves 100 rows matching nothing.  Say so loudly rather than
    # printing a total that is short by a stratum -- the same failure
    # this file's own coercion list records at line 630.
    unknown = sorted({r["stratum"] for r in rows} - set(targets.STRATA))
    if unknown:
        say("")
        say("!! %d of %d records name a stratum this build does not have: %s",
            sum(1 for r in rows if r["stratum"] in unknown), len(rows),
            ", ".join(unknown))
        say("!! THEY APPEAR IN NO TABLE BELOW. Every table selects on")
        say("!! `stratum`, so these rows are dropped rather than misfiled.")
        say("!! docs/56 split `engine` into %s.", ", ".join(targets.ENGINE_STRATA))

    say("")
    say("=" * 84)
    say("1. CLASSIFICATION, WATCHDOG ARMED -- the SoC as docs/51 built it")
    say("=" * 84)
    _tbl(say, rows, "armed_cls")

    say("")
    say("=" * 84)
    say("2. CLASSIFICATION, WATCHDOG HELD OFF -- the connection with no")
    say("   backstop anywhere in the SoC. THE COUNTERFACTUAL.")
    say("=" * 84)
    _tbl(say, rows, "disarmed_cls")

    det = [r for r in rows if r["disarmed_cls"] == "DETECTED"]
    say("")
    say("of the %d DETECTED with the watchdog held off, %d also produced a "
        "wrong or missing answer. docs/16 section 1.6: detected is "
        "recoverable, not harmless.", len(det),
        sum(1 for r in det if not r["disarmed_out_ok"]))

    say("")
    say("=" * 84)
    say("3. SDC RATE PER STRATUM (watchdog held off), 95 %% Wilson interval")
    say("=" * 84)
    say("%-10s %-22s %5s %5s %5s %8s   %s"
        % ("stratum", "population", "bits", "n", "SDC", "rate",
           "95 % interval"))
    for stratum in targets.STRATA:
        sub = [r for r in rows if r["stratum"] == stratum]
        if not sub:
            continue
        k = sum(1 for r in sub if r["disarmed_cls"] == "SDC")
        lo, hi = wilson(k, len(sub))
        say("%-10s %-22s %5d %5d %5d %7.1f %%   %.1f .. %.1f %%"
            % (stratum, targets.POPULATION[stratum],
               targets.stratum_bits(stratum), len(sub), k,
               100.0 * k / len(sub), 100 * lo, 100 * hi))

    say("")
    say("THE DESIGN-WEIGHTED FIGURES ARE OVER THE CONNECTION'S %d BITS AND")
    say("EXCLUDE THE FROZEN DIE. A rate that mixed a design still open with")
    say("silicon docs/34 has already committed would be a number nobody")
    say("could act on.")
    say("")
    for label, col in (("held off", "disarmed_cls"), ("armed", "armed_cls")):
        for cls in ("SDC", "HANG", "DETECTED", "CORRECTED"):
            p, half = weighted_rate(rows, col, cls, OPEN_STRATA)
            say("connection-weighted %-9s rate, watchdog %-8s: %5.1f %% "
                "+/- %.1f (95 %%)", cls, label, 100 * p, 100 * half)
    say("  (each stratum's measured rate weighted by its share of the %d "
        "injectable RTL bits the connection adds)",
        targets.connection_bits())
    die = [r for r in rows if r["frozen"]]
    if die:
        k = sum(1 for r in die if r["disarmed_cls"] == "SDC")
        lo, hi = wilson(k, len(die))
        say("  the frozen die's own transport, reported apart: %d of %d "
            "SDC = %.1f %% [%.1f .. %.1f]",
            k, len(die), 100.0 * k / len(die), 100 * lo, 100 * hi)

    say("")
    say("=" * 84)
    say("3b. THE SILENT WRONG INFERENCE, PER STRATUM, AND ITS CONTRIBUTION")
    say("    docs/52 section 6.2's table, which that document computed by")
    say("    hand off the records and this one prints. A record counts")
    say("    here when the golden MODEL says the inference was wrong AND")
    say("    no HARDWARE channel announced it -- the block's telemetry, a")
    say("    trap, an Ibex alert pin or the watchdog. The program's own")
    say("    model check is NOT a hardware channel: docs/52 section 6.2 is")
    say("    that a campaign counting it would be reporting that this")
    say("    program noticed, which is a statement about this program.")
    say("=" * 84)
    total_bits = sum(targets.stratum_bits(s) for s in OPEN_STRATA)
    say("%-10s %5s %7s %10s %9s   %s"
        % ("stratum", "bits", "share", "silent", "contrib", "95 % interval"))
    acc = 0.0
    for stratum in targets.STRATA:
        sub = [r for r in rows if r["stratum"] == stratum]
        if not sub:
            continue
        k = sum(1 for r in sub if silent_wrong(r))
        lo, hi = wilson(k, len(sub))
        if stratum in targets.FROZEN:
            say("%-10s %5d %7s %6d/%-3d %9s   %.1f .. %.1f %%   FROZEN",
                stratum, targets.stratum_bits(stratum), "-", k, len(sub),
                "-", 100 * lo, 100 * hi)
            continue
        share = targets.stratum_bits(stratum) / total_bits
        contrib = 100.0 * share * k / len(sub)
        acc += contrib
        say("%-10s %5d %6.1f %% %6d/%-3d %8.2f %%   %.1f .. %.1f %%",
            stratum, targets.stratum_bits(stratum), 100 * share,
            k, len(sub), contrib, 100 * lo, 100 * hi)
    say("%-10s %5d %6.1f %% %10s %8.2f %%",
        "CONNECTION", total_bits, 100.0, "", acc)

    say("")
    say("=" * 84)
    say("4. RANKED BY CONSEQUENCE, WHICH IS NOT RANKED BY RATE")
    say("   docs/41 section 3.1's criterion and docs/42 section 6.3's")
    say("   table: what a stratum contributes to the block's rate is its")
    say("   per-bit rate TIMES its share of the flip-flops, and the two")
    say("   orderings are usually different.")
    say("=" * 84)
    total = targets.connection_bits()
    say("%-10s %-22s %5s %7s %9s %9s %10s"
        % ("stratum", "population", "bits", "share", "wrong+dead",
           "contrib", "announced"))
    ranked = []
    for stratum in OPEN_STRATA:
        sub = [r for r in rows if r["stratum"] == stratum]
        if not sub:
            continue
        bad = sum(1 for r in sub
                  if r["disarmed_cls"] in ("SDC", "HANG"))
        ann = sum(1 for r in sub if r["disarmed_cls"] == "DETECTED")
        bits = targets.stratum_bits(stratum)
        share = bits / total
        ranked.append((share * bad / len(sub), stratum, bits, share,
                       bad, len(sub), ann))
    for contrib, stratum, bits, share, bad, n, ann in sorted(
            ranked, reverse=True):
        say("%-10s %-22s %5d %6.1f %% %6d/%-3d %8.2f %% %7d/%-3d"
            % (stratum, targets.POPULATION[stratum], bits, 100 * share,
               bad, n, 100 * contrib, ann, n))

    say("")
    say("=" * 84)
    say("5. WHAT THE MACHINE DOES WITH NO BACKSTOP, AND WHAT THE WATCHDOG")
    say("   DOES ABOUT IT. Rows are the DISARMED run's verdict; the")
    say("   `escalated` column is whether the ARMED run saw a transition")
    say("   on nmi_o, wdog_rst_o or wdog_no.")
    say("=" * 84)
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
    say("  OK    the disarmed run finished with the golden answer")
    say("  WRONG the disarmed run finished with a WRONG answer: the program")
    say("        kept accessing the NPU, and therefore kept kicking, with a")
    say("        corrupted result. A watchdog cannot catch this.")
    say("  DEAD  the disarmed run never finished. Here that is almost")
    say("        always a CPU stalled inside one load: the node window")
    say("        holds the fabric response for 176 cycles by design and an")
    say("        upset that loses it never returns rvalid.")
    say("")
    say("%-10s %5s %7s %7s %7s %11s"
        % ("stratum", "n", "OK", "WRONG", "DEAD", "DEAD caught"))
    for stratum in targets.STRATA:
        sub = [r for r in rows if r["stratum"] == stratum]
        if not sub:
            continue
        d = [r for r in sub if r["truth"] == "DEAD"]
        say("%-10s %5d %7d %7d %7d %11s"
            % (stratum, len(sub),
               sum(1 for r in sub if r["truth"] == "OK"),
               sum(1 for r in sub if r["truth"] == "WRONG"),
               len(d),
               "%d/%d" % (sum(1 for r in d if r["ann_wdog"]), len(d))
               if d else "-"))
    dead = [r for r in rows if r["truth"] == "DEAD"]
    wrong = [r for r in rows if r["truth"] == "WRONG"]
    ok = [r for r in rows if r["truth"] == "OK"]
    if dead:
        k = sum(1 for r in dead if r["ann_wdog"])
        lo, hi = wilson(k, len(dead))
        say("")
        say("WATCHDOG CATCH RATE over the set a watchdog can act on (DEAD): "
            "%d of %d = %.1f %% [%.1f .. %.1f %%]",
            k, len(dead), 100.0 * k / len(dead), 100 * lo, 100 * hi)
        rec = sum(1 for r in dead if r["armed_out_ok"])
        say("  of those, %d ended with the golden answer anyway after the "
            "stage-2 reset", rec)
        st = {}
        for r in dead:
            st[r["wdog_stage"]] = st.get(r["wdog_stage"], 0) + 1
        say("  highest stage reached: %s",
            ", ".join("stage %d: %d" % (k2, v) for k2, v in sorted(st.items())))
        lats = sorted(r["wdog_latency"] for r in dead
                      if r["wdog_latency"] >= 0)
        if lats:
            say("  cycles from the deposit to the first escalation: min %d, "
                "median %d, max %d", lats[0], lats[len(lats) // 2], lats[-1])
    if wrong:
        k = sum(1 for r in wrong if r["ann_wdog"])
        ks = sum(1 for r in wrong if r["ann_sw"])
        kn = sum(1 for r in wrong if r["ann_npu"])
        silent = sum(1 for r in wrong
                     if not (r["ann_wdog"] or r["ann_sw"] or r["ann_trap"]
                             or r["ann_alert"] or r["ann_npu"]))
        say("")
        say("SILENT CORRUPTION THE BACKSTOP CANNOT SEE: %d of %d WRONG runs "
            "escalated nothing.", len(wrong) - k, len(wrong))
        say("  of the %d, the program's own model check noticed %d and the "
            "block's own telemetry noticed %d; %d were announced by nothing "
            "at all", len(wrong), ks, kn, silent)
    if ok:
        k = sum(1 for r in ok if r["ann_wdog"])
        say("")
        say("SPURIOUS ESCALATIONS: %d of %d injections the machine would "
            "have survived escalated the watchdog anyway", k, len(ok))

    say("")
    say("=" * 84)
    say("6. WHAT THE GOLDEN MODEL BOUGHT")
    say("   docs/42 section 3's oracle is the undeposited run. This")
    say("   campaign has that AND sw/golden/lif_core.py's answer compiled")
    say("   into the ROM. These are the records the second one separated.")
    say("=" * 84)
    bad = [r for r in rows if not r["armed_out_ok"]]
    say("%-52s %6s" % ("the run oracle: differs from the golden RUN",
                       len(bad)))
    say("%-52s %6s" % ("  of which the MODEL says the inference was wrong",
                       sum(1 for r in bad if r["model_wrong"])))
    say("%-52s %6s" % ("    wrong spike stream", sum(1 for r in rows
                                                     if r["spikes_bad"])))
    say("%-52s %6s" % ("    wrong neuron state file", sum(1 for r in rows
                                                          if r["state_bad"])))
    say("%-52s %6s" % ("    WRONG STATE, RIGHT SPIKES -- the class an",
                       sum(1 for r in rows if r["state_only"])))
    say("%-52s %6s" % ("    output-only oracle cannot see (docs/42 s.9)", ""))
    say("%-52s %6s" % ("  of which the model says the inference was RIGHT",
                       sum(1 for r in bad if not r["model_wrong"])))
    say("")
    say("  A record in the last row deviated from the reference run in "
        "something")
    say("  other than the answer -- a counter, the block's end state, the "
        "console.")
    say("  docs/42's oracle could not have told those apart from a wrong "
        "inference.")

    say("")
    say("=" * 84)
    say("7. THE EXPOSURE ARITHMETIC: 176 CYCLES PER REGISTER ACCESS")
    say("   A stratum that is BUSY for more of the run is exposed for")
    say("   longer, whatever its flip-flop count. Rows are conditioned on")
    say("   whether the deposit landed while the transport was busy.")
    say("=" * 84)
    for stratum in ("ser", "die_ser"):
        sub = [r for r in rows if r["stratum"] == stratum]
        if not sub:
            continue
        for busy, label in ((1, "transport BUSY"), (0, "transport idle")):
            s2 = [r for r in sub if r["at_ser"] == busy]
            if not s2:
                say("%-10s %-16s n=0", stratum, label)
                continue
            counts = [sum(1 for r in s2 if r["disarmed_cls"] == c)
                      for c in CLASSES]
            say("%-10s %-16s n=%-4d %s"
                % (stratum, label, len(s2),
                   "".join("%10d" % c for c in counts)))
    say("")
    for stratum in ("window",) + targets.ENGINE_STRATA:
        sub = [r for r in rows if r["stratum"] == stratum]
        if not sub:
            continue
        key = "at_win" if stratum == "window" else "at_ev"
        for busy, label in ((1, "block BUSY"), (0, "block idle")):
            s2 = [r for r in sub if r[key] == busy]
            if not s2:
                say("%-10s %-16s n=0", stratum, label)
                continue
            counts = [sum(1 for r in s2 if r["disarmed_cls"] == c)
                      for c in CLASSES]
            say("%-10s %-16s n=%-4d %s"
                % (stratum, label, len(s2),
                   "".join("%10d" % c for c in counts)))

    say("")
    say("=" * 84)
    say("8. THE PROTECTION THAT IS THERE, AND WHAT AN OPERATOR CAN SEE OF")
    say("   IT. aer_fifo's pointer voting, entry parity and dual-rail")
    say("   rd_valid are the only protection in the connection, and")
    say("   soc_npu.v connects all three reports to NOTHING (docs/51")
    say("   section 14 item 1). These counts are BENCH observations.")
    say("=" * 84)
    say("%-46s %6d of %d"
        % ("pointer vote corrected a replica",
           sum(1 for r in rows if r["q_ptr_mm"] > 0), len(rows)))
    say("%-46s %6d"
        % ("  of those, ended with the golden answer",
           sum(1 for r in rows if r["q_ptr_mm"] > 0 and r["armed_out_ok"])))
    say("%-46s %6d"
        % ("entry parity discarded a queue entry",
           sum(1 for r in rows if r["q_par_err"] > 0)))
    say("%-46s %6d"
        % ("rd_valid rails disagreed",
           sum(1 for r in rows if r["q_rv_mm"] > 0)))
    say("%-46s %6d"
        % ("the engine's bounded fetch wait expired",
           sum(1 for r in rows if r["fetch_er"] > 0)))
    say("%-46s %6d"
        % ("the show-ahead adapter's read bound expired",
           sum(1 for r in rows if r.get("oh_to", 0) > 0)))
    say("%-46s %6d"
        % ("the AER strobe gate suppressed a strobe",
           sum(1 for r in rows if r.get("aer_mm", 0) > 0)))
    say("")
    # docs/56 section 5.1: the failure H4 answers is not one of docs/16's
    # five classes, it is a STALL of the event path that leaves the
    # inference short with every register looking sane.  The only column
    # that sees it is how long `oh_req` stayed outstanding, so it is
    # reported rather than left to be inferred from a class.
    runs = sorted(r.get("oh_req_max", 0) for r in rows)
    if runs and runs[-1]:
        say("  the longest run of cycles the show-ahead's request stayed")
        say("  outstanding, over every record: min %d, median %d, max %d",
            runs[0], runs[len(runs) // 2], runs[-1])
        say("  records in which it stayed outstanding for more than 64 "
            "cycles: %d", sum(1 for x in runs if x > 64))
    say("")
    say("  and of the records in which a mechanism moved, how many were")
    say("  ANNOUNCED to software by anything at all:")
    for label, key in (("pointer vote (no channel exists)", "q_ptr_mm"),
                       ("entry parity (no channel exists)", "q_par_err"),
                       ("rd_valid rails (no channel exists)", "q_rv_mm"),
                       ("the fetch bound (latches IRQ_CAUSE.FETCH_ER)",
                        "fetch_er"),
                       ("the show-ahead bound (latches IRQ_CAUSE.OH_TO)",
                        "oh_to"),
                       ("the AER strobe gate (latches IRQ_CAUSE.AER_MM)",
                        "aer_mm")):
        sub = [r for r in rows if r.get(key, 0) > 0]
        if not sub:
            say("    %-44s   -", label)
            continue
        ann = sum(1 for r in sub
                  if r["ann_sw"] or r["ann_npu"] or r["ann_trap"]
                  or r["ann_alert"] or r["ann_wdog"])
        say("    %-44s %3d of %3d", label, ann, len(sub))

    say("")
    say("=" * 84)
    say("9. WHAT ANNOUNCED IT (watchdog armed, injections whose armed run")
    say("   did not produce the golden answer)")
    say("=" * 84)
    say("%-42s %6s" % ("channel", "n"))
    say("%-42s %6d" % ("the program's model check (fi_mask)",
                       sum(1 for r in bad if r["ann_sw"])))
    say("%-42s %6d" % ("the block's own telemetry, read by a load",
                       sum(1 for r in bad if r["ann_npu"])))
    say("%-42s %6d" % ("an unexpected trap (a window bus error)",
                       sum(1 for r in bad if r["ann_trap"])))
    say("%-42s %6d" % ("the watchdog escalated",
                       sum(1 for r in bad if r["ann_wdog"])))
    say("%-42s %6d" % ("an Ibex alert pin",
                       sum(1 for r in bad if r["ann_alert"])))
    say("%-42s %6d" % ("NOTHING (silent)",
                       sum(1 for r in bad
                           if not (r["ann_wdog"] or r["ann_sw"]
                                   or r["ann_trap"] or r["ann_alert"]
                                   or r["ann_npu"]))))
    say("%-42s %6d" % ("total wrong or dead", len(bad)))

    say("")
    say("=" * 84)
    say("10. THE WORST SITES (watchdog held off), by SDC plus HANG")
    say("=" * 84)
    per = {}
    for r in rows:
        key = (r["stratum"], r["site"])
        d = per.setdefault(key, {"n": 0, "bad": 0, "sdc": 0, "hang": 0,
                                 "det": 0})
        d["n"] += 1
        if r["disarmed_cls"] == "SDC":
            d["sdc"] += 1
            d["bad"] += 1
        if r["disarmed_cls"] == "HANG":
            d["hang"] += 1
            d["bad"] += 1
        if r["disarmed_cls"] == "DETECTED":
            d["det"] += 1
    ranked = sorted(per.items(), key=lambda kv: -kv[1]["bad"] / kv[1]["n"])
    say("%-10s %-18s %5s %5s %5s %9s %8s"
        % ("stratum", "site", "n", "SDC", "HANG", "DETECTED", "bad %"))
    for (stratum, site), d in ranked[:24]:
        if d["bad"] == 0:
            break
        say("%-10s %-18s %5d %5d %5d %9d %7.0f %%"
            % (stratum, site, d["n"], d["sdc"], d["hang"], d["det"],
               100.0 * d["bad"] / d["n"]))

    say("")
    say("(%d records in all: %d into the connection, %d into the frozen "
        "die)", len(rows), len(conn), len(rows) - len(conn))


if __name__ == "__main__":
    main()
