#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
#
# Every check the GitHub workflows run, run here instead.
#
#   scripts/ci_local.sh              every job
#   scripts/ci_local.sh licence      one of them
#   scripts/ci_local.sh checkers     the flow's own gates, over the run trees
#   scripts/ci_local.sh suite        the whole pytest suite, ~8 min
#   scripts/ci_local.sh all --record append a row to ci-local-log.tsv
#
# WHY THIS EXISTS, AND IT IS NOT CONVENIENCE
#
# Three documents said these checks "run in CI". They did not, and the
# reason recorded here was WRONG IN THE DIRECTION THAT MATTERS.
#
# *Corrected 2026-09-11.* This read: "Every workflow run on this
# repository since 2026-09-03 was refused before starting -- 'the job
# was not started because recent account payments have failed or your
# spending limit needs to be increased' -- so the SPDX policy check has
# never executed there once, and neither has the paper's claim checker.
# Nine non-starts, not nine failures."
#
# 53 of 61 runs in that window EXECUTED. The licence job among them
# failed, and it failed on `ModuleNotFoundError: No module named 'yaml'`
# -- an uninstalled dependency, not a billing wall. One day's refusals
# were read backwards across a week, which turned a fixable workflow
# defect into an account problem nobody could act on.
#
# And the billing wall that does exist is in front of PRIVATE minutes
# only. The public mirror's first push started a run six seconds later.
# So "CI cannot run" was never true of a public repository, which is
# what a Tiny Tapeout submission is.
#
# THE WORKFLOWS NOW CALL THIS SCRIPT. That is the point of it. One
# definition of what a check is, so "CI runs the checks" and "I ran the
# checks" cannot drift apart, and so the checks keep working while the
# runner does not.
#
# A SKIP IS NOT A PASS. Two things genuinely cannot run on the machine
# this project is developed on -- there is no TeX and no pandoc, and apt
# needs a password -- so they report SKIP with the reason, and the
# summary prints the count. A runner that reported green while silently
# not building the paper would be the exact defect this repository
# keeps finding in itself.

set -u
cd "$(dirname "$0")/.."
JOB="${1:-all}"
RECORD=0
for a in "$@"; do [ "$a" = "--record" ] && RECORD=1; done

PY=.venv/bin/python
[ -x "$PY" ] || PY=python3

pass=0; fail=0; skip=0
failed_names=""

run() {   # run <name> <command...>
    local name=$1; shift
    printf '  %-46s ' "$name"
    if out=$("$@" 2>&1); then
        echo "ok"; pass=$((pass+1))
    else
        echo "FAIL"; fail=$((fail+1)); failed_names="$failed_names $name"
        printf '%s\n' "$out" | tail -12 | sed 's/^/      /'
    fi
}

skipped() {  # skipped <name> <reason>
    printf '  %-46s skip  (%s)\n' "$1" "$2"; skip=$((skip+1))
}

# ---------------------------------------------------------------- licence
job_licence() {
    echo "== licence"
    run "every source file carries the right SPDX tag" \
        python3 scripts/spdx_check.py
    run "the four licence texts are present and canonical" bash -c '
        set -eu
        for f in CERN-OHL-W-2.0 Apache-2.0 CC-BY-4.0 ISC; do
            test -s "LICENSES/$f.txt"
        done
        echo "3b83ef96387f14655fc854ddc3c6bd57  LICENSES/Apache-2.0.txt" | md5sum -c - >/dev/null
        grep -q "CERN Open Hardware Licence Version 2 - Weakly Reciprocal" \
            LICENSES/CERN-OHL-W-2.0.txt'
    run "the map, the memo and the tree agree" bash -c '
        set -eu
        grep -q "SIGNED 2026-09-09" docs/14-licensing-decision.md
        test -f LICENSES.md && test -f .reuse/dep5
        test ! -e tt/LICENSE.PENDING.md && test -f tt/LICENSE
        cmp LICENSES/CERN-OHL-W-2.0.txt tt/LICENSE
        cmp LICENSES/Apache-2.0.txt tt/LICENSES/Apache-2.0.txt'
    # A CHECK MUST NOT WRITE WHAT IT VERIFIES, and this one did. It ran
    # three generators IN PLACE and then diffed, so on any run where a
    # generator's output had legitimately changed it left the tree
    # modified -- including tt/, which docs/34 freezes for a shuttle.
    # That happened on 2026-09-11: this check rewrote tt/docs/info.md,
    # tt/MANIFEST.sha256 and tt/README.md as a side effect of being run.
    #
    # It now refuses on a dirty tree first, so that restoring afterwards
    # cannot destroy uncommitted work, and restores what the generators
    # wrote whether it passed or failed. The drift is still detected;
    # the tree is not the place it is detected in.
    run "the generators still emit the tag they should" bash -c '
        set -eu
        paths="hw/rtl hw/soc/rtl hw/soc/tb/sw sw/golden tt"
        if [ -n "$(git status --porcelain -- $paths)" ]; then
            echo "refusing: these paths are already modified, and this check"
            echo "restores them afterwards. Commit or stash first:"
            git status --short -- $paths
            exit 1
        fi
        rc=0
        python3 regmap/generate.py >/dev/null
        python3 regmap/generate_memmap.py >/dev/null
        python3 scripts/gen_tt_submission.py >/dev/null
        python3 scripts/spdx_check.py >/dev/null
        git diff --exit-code -- $paths || rc=1
        git checkout -- $paths
        exit $rc'
}

# ------------------------------------------------------------------- docs
job_suite() {
    echo "== suite"
    # THE WHOLE PYTEST SUITE, and the header used to say "every check the
    # GitHub workflows run" while the only pytest invocation in this file
    # was the doc-link one. "The checks pass" then meant SPDX, links and
    # the claim table, and nothing about the hardware. Added 2026-09-10.
    # It is about eight minutes.
    run "the whole pytest suite" "$PY" -m pytest sw/tests -q
}

job_docs() {
    echo "== docs"
    run "link integrity across the corpus" \
        "$PY" -m pytest sw/tests/test_doc_links.py -q
    if command -v pandoc >/dev/null 2>&1; then
        run "build the site (pandoc) and gate on the manifest" bash -c '
            set -eu
            python3 scripts/build_docs.py --out _site --renderer pandoc >/dev/null
            python3 scripts/ci_gate_docs.py _site pandoc'
    else
        skipped "build the site (pandoc)" "no pandoc on this machine"
    fi
    run "build the site (builtin) and gate on the manifest" bash -c '
        set -eu
        python3 scripts/build_docs.py --out _site_builtin --renderer builtin >/dev/null
        python3 scripts/ci_gate_docs.py _site_builtin builtin
        test -s _site_builtin/index.html'
    # --strict, which nothing passed until 2026-09-11. The builder has
    # carried the flag since it was written and every invocation in this
    # repository omitted it, so "the site builds" never meant "every
    # cross-reference resolved". ci_gate_docs.py deliberately runs WITHOUT
    # it (its own comment says why: it wants to read the manifest rather
    # than be stopped before writing one), which left the flag inert
    # everywhere.
    run "every cross-reference in the corpus resolves (--strict)" bash -c '
        set -eu
        out=$(mktemp -d)
        trap "rm -rf $out" EXIT
        python3 scripts/build_docs.py --out "$out" --renderer builtin \
            --strict --quiet' 
}

# ------------------------------------------------------------------ paper
job_paper() {
    echo "== paper"
    run "re-derive the numbers the paper registers" \
        python3 paper/check_claims.py
    run "no claim may be unattributed" python3 - <<'PY'
import sys, pathlib
sys.path.insert(0, "paper")
from check_claims import load
bad = []
for c in load(pathlib.Path("paper/claims.yaml")):
    if c.get("check") == "manual":
        if not c.get("artefact"):
            bad.append(c["id"])
    elif not (c.get("cmd") or c.get("path") or c.get("file")
              or c.get("glob") or c.get("pattern")):
        bad.append(c["id"])
if bad:
    print("claims with nothing behind them: " + ", ".join(bad)); sys.exit(1)
print("every claim names a command or an artefact")
PY
    run "the paper source is structurally sound" \
        python3 scripts/tex_lint.py paper/main.tex
    # The renderer exits non-zero on a macro it does not know, so this
    # is a real gate and not a convenience: a new command in the source
    # fails here rather than appearing as raw LaTeX in the reading copy.
    run "the reading copy renders with no unknown macro" \
        python3 paper/render_html.py paper/main.tex paper/main.html
    if command -v pdflatex >/dev/null 2>&1; then
        run "build the paper" make -C paper
        run "the bibliography is not empty" bash -c '
            set -eu
            test -s paper/main.bbl
            ! grep -qE "Citation .* undefined" paper/main.log'
    else
        skipped "build the paper" "no TeX on this machine; tex_lint above is not a compile"
        skipped "the bibliography is not empty" "needs the build"
    fi
}

# --------------------------------------------------------------- checkers
#
# THE INSTRUMENT THAT FINDS INSTRUMENTS THAT CANNOT FAIL, and until
# 2026-09-10 it was called by nothing.
#
# hw/openlane/checker_audit.py was written for docs/36 to detect one
# specific shape: a LibreLane Checker.* step that runs, reports green and
# gates nothing, because its reach is configuration and the configuration
# is not visible in any report. It found that shape three times in this
# tree. It was then never wired to a runner, and so it did not find the
# fourth: hw/openlane/aer_fifo/config.json carried none of the three keys
# and ROADMAP gate G0's evidence run, trial-03-signoff, had setup bound
# to the typical corner alone and max cap and max slew bound to the
# match-none empty string. A detector nothing calls is the same defect
# one level up. This job calls it.
#
# WHAT IT ASSERTS, AND WHY IT IS NOT "exit 0".
#
# checker_audit.py exits 1 whenever ANY in-flow checker is PARTIAL or
# NO-GATE, and two of them always are, by disposition rather than by
# oversight: Checker.LintWarnings is off by an explicitly named boolean
# whose default upstream chose (docs/36 section 3.3), and
# Checker.WireLength has no WIRE_LENGTH_THRESHOLD in either PDK (docs/36
# section 3.4). docs/71 section 9 corrected five documents that had
# written "exit 0" for exactly this reason. So the exit status is not
# the gate here.
#
# The gate is the SET. For each run tree below, the checkers that do not
# gate must be exactly the ones dispositioned in the table, in the order
# checker_audit.py prints them. That fails in BOTH directions on purpose:
# a checker that stops gating fails the job, and a disposition that
# quietly disappears also fails it, because a shrinking list is a green
# result getting wider without anyone saying so. Adding a row, or
# changing one, is a deliberate edit with a reason next to it.
#
# THE TWO UNBOUND RUN TREES ARE IN THE TABLE ON PURPOSE. sky-14-6x2-rcmodel
# is the script's own self-test -- its docstring says so -- and it is the
# only place in this repository where a real, non-synthetic violation sits
# at a corner the wildcards do not reach: 3,930 max-slew violations
# reported as a clean flow. trial-03-signoff is the G0 evidence run, left
# standing with its marker rather than re-run (docs/64). If either ever
# reports a full set of gates, the run tree has been replaced by something
# else and the job says so.
#
# A SKIP IS NOT A PASS here either. Run trees under hw/openlane/*/runs
# and hw/soc/pnr/runs are gitignored, so a fresh clone has none of them,
# and checker_audit.py imports librelane, which the repository venv does
# not carry -- it needs the flow venv, whose path its own docstring gives
# and which FLOW_PY overrides.
FLOW_PY="${FLOW_PY:-$HOME/Documents/caravel-lif-crossbar/.venv-flow/bin/python}"

# run tree | the checkers dispositioned as not gating, verbatim from
# checker_audit.py's "NOT gating in full:" line | what the run is
CHECKER_RUNS="\
hw/openlane/pilot_ihp/runs/signoff-6x2-gated|Checker.LintWarnings, Checker.WireLength|docs/36 s.1, the pilot sign-off run
hw/openlane/pilot_ihp/runs/submission-6x2-gated|Checker.LintWarnings, Checker.WireLength|docs/36 s.1, the submission-path run
hw/soc/pnr/runs/s71boot|Checker.LintWarnings, Checker.WireLength|docs/71, the most recent SoC layout
hw/openlane/pilot_sky130/runs/sky-14-6x2-rcmodel|Checker.LintWarnings, Checker.WireLength, Checker.SetupViolations, Checker.MaxSlewViolations, Checker.MaxCapViolations|checker_audit.py's own self-test; sky130 does not close and the checker was pointed at no corner (docs/18 s.3.3, pilot_sky130/config.json //capslew)
hw/openlane/aer_fifo/runs/trial-03-signoff|Checker.LintWarnings, Checker.WireLength, Checker.SetupViolations, Checker.MaxSlewViolations, Checker.MaxCapViolations|the 2026-08-25 G0 evidence run, made before aer_fifo/config.json bound the three keys on 2026-09-10; left standing, not re-run, docs/12 s.4.7a
hw/openlane/aer_fifo/runs/g0gates2|Checker.LintWarnings, Checker.WireLength|ROADMAP gate G0's evidence run since 2026-09-11: the same design the tree contains, with all four corner checkers live. THE ROW ABOVE IS ITS CONTROL -- the two run trees differ in exactly the three keys, and if this row ever grows a corner checker back, a config edit has silently unbound one"

job_checkers() {
    echo "== checkers"

    # THE FORMAL DISPOSITIONS RUN FIRST, and they run whether or not
    # librelane is installed.
    #
    # They were added below the early return on 2026-09-11 and that put
    # them behind a `return` that fires on every machine without a
    # librelane interpreter -- which is every CI runner and every clone.
    # The one gate written that day to be runnable anywhere was the one
    # place it could never run. It needs no librelane and no PDK: it
    # reads formal-dispositions.tsv and the sby work directories, and on
    # a machine with neither it reports zero of everything and exits 0.
    run "every non-PASS formal directory is dispositioned" \
        bash scripts/verify.sh --dispositions

    if [ ! -x "$FLOW_PY" ]; then
        skipped "the flow's own gates still gate" \
                "no librelane interpreter at $FLOW_PY; set FLOW_PY"
        return
    fi
    while IFS='|' read -r rundir want why; do
        [ -n "$rundir" ] || continue
        name="checkers bind as dispositioned: $(basename "$rundir")"
        if [ ! -f "$rundir/resolved.json" ]; then
            skipped "$name" "no run tree at $rundir; runs/ is gitignored"
            continue
        fi
        run "$name" env RUN_DIR="$rundir" WANT="$want" WHY="$why" \
                     FLOW_PY="$FLOW_PY" bash -c '
            # checker_audit.py exits 1 by contract whenever anything is
            # PARTIAL or NO-GATE, which is the normal state here, so the
            # status is discarded and the REPORT is parsed. A missing
            # summary line is a crashed audit and must not read as an
            # empty set of ungated checkers -- that would be the exact
            # false green this whole job exists to catch.
            out=$("$FLOW_PY" hw/openlane/checker_audit.py "$RUN_DIR" 2>&1) || true
            summary=$(printf "%s\n" "$out" | \
                sed -n "s/^ *\([0-9]* of [0-9]*\) in-flow checkers gate fully\./\1/p")
            if [ -z "$summary" ]; then
                echo "checker_audit.py wrote no summary line for $RUN_DIR:"
                printf "%s\n" "$out" | tail -15
                exit 1
            fi
            got=$(printf "%s\n" "$out" | sed -n "s/^ *NOT gating in full: //p")
            if [ "$got" != "$WANT" ]; then
                echo "$RUN_DIR ($WHY)"
                echo "  the set of checkers that do not gate has CHANGED."
                echo "  dispositioned: ${WANT:-<none>}"
                echo "  this run tree: ${got:-<none>}"
                echo "  audit says:    $summary in-flow checkers gate fully"
                exit 1
            fi
            echo "$RUN_DIR: $summary gate; not gating: ${got:-<none>}"'
    done <<CHECKER_TABLE_END
$CHECKER_RUNS
CHECKER_TABLE_END

}

# ----------------------------------------------------------------- mirror
job_mirror() {
    echo "== mirror"
    # THE PUBLISHED SUBSET, WHICH UNTIL NOW NO JOB TOUCHED.
    #
    # scripts/gen_public_mirror.py decides what the public repository
    # contains, and it grew two guards on 2026-09-10 that nothing ran.
    # That matters more here than for most scripts: the mirror is the only
    # artefact in this repository a stranger reads, and a defect in the
    # generator is invisible locally and visible to everyone else. The
    # shuttle page told an operator to write the wrong FAULT_CLR value for
    # a day for exactly this reason.
    #
    # This does NOT check the published repository -- nothing here can
    # reach it. It checks that the generator still runs, still selects the
    # files it claims to, and still refuses what it is supposed to refuse.
    # Regenerating and pushing is a separate act, by a person.
    run "the mirror generator runs and selects its files" bash -c '
        set -eu
        out=$(mktemp -d)
        trap "rm -rf $out" EXIT
        python3 scripts/gen_public_mirror.py --out "$out" | tail -2
        python3 scripts/gen_public_mirror.py --out "$out" --check'
}

case "$JOB" in
    licence)  job_licence ;;
    docs)     job_docs ;;
    paper)    job_paper ;;
    suite)    job_suite ;;
    checkers) job_checkers ;;
    mirror)   job_mirror ;;
    all)      job_licence; echo; job_docs; echo; job_paper; echo; job_checkers
              echo; job_mirror; echo; job_suite ;;
    *) echo "usage: $0 [licence|docs|paper|checkers|mirror|suite|all] [--record]" >&2
       exit 2 ;;
esac

echo
echo "$pass passed, $fail failed, $skip skipped"
[ "$skip" -gt 0 ] && echo "A SKIP IS NOT A PASS -- see the reasons above."
[ -n "$failed_names" ] && echo "failed:$failed_names"

if [ "$RECORD" = "1" ]; then
    REC=ci-local-log.tsv
    head=$(git rev-parse --short HEAD)
    dirty=$(git status --short | wc -l)
    [ -f "$REC" ] || printf 'utc\thead\tjob\tpassed\tfailed\tskipped\tnotes\n' > "$REC"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$(date -u +%Y-%m-%dT%H:%MZ)" "$head" "$JOB" "$pass" "$fail" "$skip" \
        "tree-dirty=$dirty,pandoc=$(command -v pandoc >/dev/null && echo yes || echo no),tex=$(command -v pdflatex >/dev/null && echo yes || echo no)" \
        >> "$REC"
    echo "recorded in $REC"
fi

[ "$fail" = "0" ]
