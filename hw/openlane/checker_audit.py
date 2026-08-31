#!/usr/bin/env python3
"""Audit every LibreLane checker in a run: does it gate, and on what?

WHY THIS EXISTS
---------------
Three times in this project a checker has been found green because it
was looking at nothing:

  * `docs/23`  -- `design__violations` does not aggregate hold, so a
    hold violation did not reach the flow's own summary metric.
  * `docs/28` section 4.4a -- `Checker.SetupViolations` resolves its
    corners as `SETUP_VIOLATION_CORNERS or TIMING_VIOLATION_CORNERS`,
    both PDKs ship `["*typ*"]`, and the first key was unset. Setup had
    never been checked at the slow corner. Four published "the corner
    closes" claims came from runs that did not gate it.
  * `docs/34` section 8.5, closed by `docs/36` -- `MAX_CAP_VIOLATION_CORNERS`
    and `MAX_SLEW_VIOLATION_CORNERS` both resolve to the match-none
    wildcard `[""]`, so both checkers warn and can never fail.

The common shape is that a checker's *reach* is configuration, the
configuration's default is not visible in any report, and a run that
gates nothing looks exactly like a run that gates everything and
passes. Prose cannot keep up with that: the answer changes with the
LibreLane version, with the PDK, and with the design's own config. So
it is computed here instead, from the installed LibreLane's own step
classes and from the run's own `resolved.json`.

WHAT IT REPORTS
---------------
For every `Checker.*` step registered by the installed LibreLane, and
for every one of those the Classic flow actually runs:

  * how the checker is gated -- by a boolean `ERROR_ON_*` variable, by
    a numeric threshold, or by a list of corner wildcards;
  * the value that binds in THIS run;
  * the metric it reads and that metric's value;
  * a verdict -- GATES, PARTIAL or NO-GATE -- with the reason.

PARTIAL is the `docs/28` 4.4a shape exactly: the wildcard list is not
empty, but it matches fewer corners than the metric was measured at, so
the checker is green over a subset. Where violations sit at a corner
the wildcards do not reach, the line ends in `WARNS ONLY, DOES NOT
FAIL`. Pointed at `sky-14-6x2-rcmodel` the script reproduces that
finding from the run alone, which is the self-test for this file.

NO-GATE is not automatically a defect. `Checker.LintWarnings` is off by
an explicitly named boolean whose default upstream chose; that is a
policy, not an oversight. What the script guarantees is that no such
case is invisible.

Exit status is 1 if any in-flow checker is PARTIAL or NO-GATE, so this
is usable as a gate in its own right once the remaining cases are
dispositioned.

Run it with the FLOW's interpreter, not the repository venv -- it
imports librelane:

    ~/Documents/caravel-lif-crossbar/.venv-flow/bin/python \\
        hw/openlane/checker_audit.py hw/openlane/pilot_ihp/runs/<tag>

With two or more run directories it prints one block each, which is how
a PDK-to-PDK or before-to-after comparison is made.
"""

import fnmatch
import json
import os
import sys

try:
    from librelane.steps import Step
    from librelane.steps.checker import MetricChecker, TimingViolations
    from librelane.flows.flow import Flow
except ImportError:  # pragma: no cover - depends on the caller's interpreter
    sys.exit(
        "librelane is not importable. Run this with the flow venv's python, "
        "e.g. ~/Documents/caravel-lif-crossbar/.venv-flow/bin/python"
    )


def classic_checker_ids():
    flow = Flow.factory.get("Classic")
    return [s.id for s in flow.Steps if s.id.startswith("Checker.")]


def all_checker_ids():
    return sorted(k for k in Step.factory.list() if k.startswith("Checker."))


def metric_value(metrics, name):
    """The metric, plus its per-corner spread if the checker is per-corner."""
    per_corner = {
        k.split(":", 1)[1]: v
        for k, v in metrics.items()
        if k.startswith(f"{name}__corner:")
    }
    return metrics.get(name), per_corner


def audit_one(cls, resolved, metrics):
    """Return (how, binds, verdict, detail) for one checker class."""
    # --- not a MetricChecker at all -----------------------------------
    # Checker.NetlistAssignStatements is a plain Step: it greps the
    # netlist itself rather than reading a metric, and gates on its own
    # ERROR_ON_* variable. Handled first so the MetricChecker machinery
    # below can assume it is looking at a MetricChecker.
    if not issubclass(cls, MetricChecker):
        var = next(
            (v for v in cls.config_vars if v.name.startswith("ERROR_ON_")), None
        )
        if var is None:
            return "unconditional", "-", "GATES", "no ERROR_ON_* variable"
        binds = resolved.get(var.name, var.default)
        return (
            "boolean",
            str(binds),
            "GATES" if binds else "NO-GATE",
            f"{var.name} = {binds}; reads the netlist directly, not a metric",
        )

    # --- corner-gated -------------------------------------------------
    if issubclass(cls, TimingViolations):
        own = cls.get_corner_variable().name
        value = resolved.get(own)
        source = own
        if not value:
            value = resolved.get(cls.base_corner_var_name)
            source = cls.base_corner_var_name
        wildcards = [w for w in (value or []) if w != ""]
        _, per_corner = metric_value(metrics, cls.metric_name)
        violating = {c for c, v in per_corner.items() if v and v > 0}
        matched = {
            c
            for c in per_corner
            if any(fnmatch.fnmatchcase(c, w) for w in wildcards)
        }
        # A checker can be green three ways, and only one of them is
        # "the design passes". The other two are the docs/28 4.4a shape:
        # the wildcard list is empty, or it is non-empty but misses the
        # corners where the violations are. Both are called out by name.
        hidden = sorted(violating - matched)
        detail = f"{source} = {json.dumps(value)}"
        if not wildcards:
            verdict = "NO-GATE"
            detail += " reduces to no wildcard; every corner lands in " \
                      "warn_violating_corner"
        elif per_corner and matched < set(per_corner):
            verdict = "PARTIAL"
            detail += (
                f" matches {len(matched)} of {len(per_corner)} measured "
                f"corners; unchecked: {', '.join(sorted(set(per_corner) - matched))}"
            )
        else:
            verdict = "GATES"
        if per_corner:
            detail += f"; corners measured {len(per_corner)}"
            detail += (
                f", violating {', '.join(sorted(violating))}"
                if violating
                else ", all 0"
            )
            if hidden:
                detail += (
                    f"  <-- WARNS ONLY, DOES NOT FAIL, AT: {', '.join(hidden)}"
                )
        else:
            detail += "; metric absent"
        return "corners", json.dumps(value), verdict, detail

    # --- threshold-gated ----------------------------------------------
    # get_threshold is an instance method on the subclasses that override
    # it, but every override in checker.py reads self.config only, so a
    # tiny shim is enough to evaluate it without constructing a Step.
    threshold = None
    overrides_threshold = cls.get_threshold is not MetricChecker.get_threshold
    if overrides_threshold:
        shim = object.__new__(cls)
        shim.config = resolved
        try:
            threshold = cls.get_threshold(shim)
        except Exception as e:  # pragma: no cover - defensive
            return "threshold", "?", "UNKNOWN", f"could not evaluate: {e}"
        if threshold is None:
            return (
                "threshold",
                "None",
                "NO-GATE",
                "threshold is unset, so MetricChecker.run() skips the check "
                "and only warns",
            )

    # --- boolean-gated -------------------------------------------------
    var = getattr(cls, "error_on_var", None)
    value, _ = metric_value(metrics, cls.metric_name)
    shown = "n/a" if value is None else value
    if var is None:
        return (
            "unconditional",
            "-",
            "GATES",
            f"no ERROR_ON_* variable; metric {cls.metric_name} = {shown}",
        )
    binds = resolved.get(var.name, var.default)
    verdict = "GATES" if binds else "NO-GATE"
    detail = f"{var.name} = {binds}; metric {cls.metric_name} = {shown}"
    if value is None:
        detail += " (metric absent: the producing step did not run)"
    if overrides_threshold:
        detail += f"; threshold {threshold}"
    return "boolean", str(binds), verdict, detail


def report(run_dir):
    resolved_path = os.path.join(run_dir, "resolved.json")
    metrics_path = os.path.join(run_dir, "final", "metrics.json")
    if not os.path.exists(resolved_path):
        sys.exit(f"no resolved.json in {run_dir}")
    resolved = json.load(open(resolved_path))
    metrics = json.load(open(metrics_path)) if os.path.exists(metrics_path) else {}

    in_flow = classic_checker_ids()
    registered = all_checker_ids()

    print(f"=== {run_dir}")
    print(f"    registered Checker.* steps: {len(registered)}")
    print(f"    of which the Classic flow runs: {len(in_flow)}")
    if not metrics:
        print("    NOTE: no final/metrics.json; metric columns will read n/a")
    print()
    rows = []
    for sid in in_flow:
        cls = Step.factory.get(sid)
        rows.append((sid,) + audit_one(cls, resolved, metrics))

    width = max(len(r[0]) for r in rows)
    for sid, how, _binds, verdict, detail in rows:
        print(f"{verdict:8s} {sid:{width}s}  [{how}] {detail}")

    nogate = [r[0] for r in rows if r[3] in ("NO-GATE", "PARTIAL")]
    print()
    print(f"    {len(rows) - len(nogate)} of {len(rows)} in-flow checkers gate fully.")
    if nogate:
        print("    NOT gating in full: " + ", ".join(nogate))
    absent = [i for i in registered if i not in in_flow]
    if absent:
        print("    registered but not in the Classic flow: " + ", ".join(absent))
    return 1 if nogate else 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__)
        return 1
    rc = 0
    for i, run_dir in enumerate(args):
        if i:
            print()
        rc |= report(run_dir)
    return rc


if __name__ == "__main__":
    sys.exit(main())
