#!/usr/bin/env python3
"""Extract the routing behaviour of a LibreLane run, the same way for every run.

`signoff_report.py` reads final/metrics.json and therefore only sees
routing as a single end-state number: `route__drc_errors`. That number
is 0 for every run in this repository that finished, and absent for
every run that did not, so it cannot distinguish "routed comfortably"
from "routed on the last iteration" from "was diverging when it was
stopped". The docs/22 section 5 sky130 failure and the docs/23 tile
shape decision both turn on exactly that distinction, so it is read out
of the logs here rather than re-grepped by hand per run.

Two things are extracted:

  * The TritonRoute optimization-iteration trace. OpenROAD's detailed
    router prints `DRT-0195 Start Nth optimization iteration` and then
    `DRT-0199 Number of violations = V` at the end of each. A healthy
    run's V falls monotonically to 0 within a handful of iterations; the
    sky130 4x2 run of docs/22 rose 218,483 -> 348,149 -> 364,603 and was
    killed. The step runs the router more than once (the second pass is
    the post-antenna-repair re-route), so the passes are kept separate:
    collapsing them makes a clean second pass look like a continuation
    of the first.

  * The global router's final congestion report, `GRT-0096`, per layer.
    Note that every config in this repository sets GRT_ALLOW_CONGESTION,
    inherited from the Tiny Tapeout defaults, so global routing does not
    fail on overflow -- it reports it and hands the mess to the detailed
    router. Overflow here is therefore a leading indicator of the
    detailed-route trace above, not an error in itself.

Usage:
    ./route_trace.py <run_dir> [<run_dir> ...]
"""

import glob
import os
import re
import sys

START = re.compile(r"DRT-0195\] Start (\d+)(?:st|nd|rd|th) optimization iteration")
VIOS = re.compile(r"DRT-0199\]\s+Number of violations = (\d+)")
# The router's within-iteration progress line. It is only reported here
# for an iteration that never produced a DRT-0199 summary, i.e. one the
# run was killed inside. Without it a diverging run that was stopped
# reads as no trace at all, which is how the docs/22 section 5 sky130
# failure presents on disk.
PROG = re.compile(r"Completing (\d+)% with (\d+) violations")


def find_log(run_dir, needle):
    hits = sorted(glob.glob(os.path.join(run_dir, "*" + needle, "*.log")))
    return hits[0] if hits else None


def drt_trace(run_dir):
    """[(pass_index, [(iteration_label, violations), ...]), ...]"""
    log = find_log(run_dir, "-openroad-detailedrouting")
    if log is None:
        return None, None
    passes, current, pending, prog = [], [], None, None
    for line in open(log, errors="replace"):
        m = START.search(line)
        if m:
            # A restart at iteration 0 means a new invocation of the
            # router, not a new iteration of the current one.
            if m.group(1) == "0" and current:
                passes.append(current)
                current = []
            pending, prog = m.group(1), None
            continue
        m = VIOS.search(line)
        if m:
            current.append((pending if pending is not None else "final", int(m.group(1))))
            pending, prog = None, None
            continue
        m = PROG.search(line)
        if m:
            prog = (m.group(1), int(m.group(2)))
    if pending is not None and prog is not None:
        current.append((f"{pending} (killed at {prog[0]}%)", prog[1]))
    if current:
        passes.append(current)
    return passes, log


def grt_congestion(run_dir):
    log = find_log(run_dir, "-openroad-globalrouting")
    if log is None:
        return None, None
    out, grab = [], False
    for line in open(log, errors="replace"):
        if "GRT-0096" in line:
            grab = True
            continue
        if grab:
            if not line.strip() or line.startswith("["):
                break
            out.append(line.rstrip())
    return out, log


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    for run_dir in sys.argv[1:]:
        print(f"=== {run_dir}")
        cong, log = grt_congestion(run_dir)
        if cong is None:
            print("    no global-routing log; the run did not reach GRT")
        else:
            print(f"    GRT-0096 final congestion, from {os.path.relpath(log, run_dir)}")
            for line in cong:
                print("      " + line)
        passes, log = drt_trace(run_dir)
        if passes is None:
            print("    no detailed-routing log; the run did not reach DRT")
            continue
        print(f"    TritonRoute iterations, from {os.path.relpath(log, run_dir)}")
        for i, p in enumerate(passes):
            trace = " -> ".join(f"{n}:{v}" for n, v in p)
            print(f"      pass {i}: {trace}")
        last = passes[-1][-1][1] if passes and passes[-1] else None
        print(f"    ends at {last} violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
