#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
#
# Every check the GitHub workflows run, run here instead.
#
#   scripts/ci_local.sh              all three jobs
#   scripts/ci_local.sh licence      one of them
#   scripts/ci_local.sh suite        the whole pytest suite, ~8 min
#   scripts/ci_local.sh all --record append a row to ci-local-log.tsv
#
# WHY THIS EXISTS, AND IT IS NOT CONVENIENCE
#
# Three documents said these checks "run in CI". They do not. Every
# workflow run on this repository since 2026-09-03 was refused before
# starting -- "the job was not started because recent account payments
# have failed or your spending limit needs to be increased" -- so the
# SPDX policy check has never executed there once, and neither has the
# paper's claim checker. Nine non-starts, not nine failures.
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
    run "the generators still emit the tag they should" bash -c '
        set -eu
        python3 regmap/generate.py >/dev/null
        python3 regmap/generate_memmap.py >/dev/null
        python3 scripts/gen_tt_submission.py >/dev/null
        python3 scripts/spdx_check.py >/dev/null
        git diff --exit-code -- hw/rtl hw/soc/rtl hw/soc/tb/sw sw/golden tt'
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

case "$JOB" in
    licence) job_licence ;;
    docs)    job_docs ;;
    paper)   job_paper ;;
    suite)   job_suite ;;
    all)     job_licence; echo; job_docs; echo; job_paper; echo; job_suite ;;
    *) echo "usage: $0 [licence|docs|paper|suite|all] [--record]" >&2; exit 2 ;;
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
