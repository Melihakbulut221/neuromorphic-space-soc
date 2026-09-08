#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

# Run every suite and RECORD the result, rather than reporting it.
#
#   scripts/verify.sh            run all three and write the record
#   scripts/verify.sh --check    re-run and diff against the last record
#
# Why this exists: until 2026-09-08 the totals quoted in commit messages
# -- "484 pytest, 398 cocotb, 58 formal" -- had no artefact behind them.
# The fault-injection campaigns track their records.csv in git and can be
# audited afterwards; the suites could not, so those totals were an
# assertion where every other number in this repository is a measurement
# naming its artefact (docs/21 section 0). This closes that.
#
# What it records is the COUNT and the outcome, not the logs: a JUnit XML
# per cocotb suite is build output and belongs in .gitignore, but "on this
# commit, these suites reported these totals" is evidence and belongs in
# the tree. The file is one line per run, appended, never rewritten.
#
# A ROW IS NEVER EDITED, INCLUDING A WRONG ONE. Two rows for 1ecf509 read
# 558 and 624 cocotb tests against a repository that has 401, because two
# runs overlapped and each counted the other's output; the runner now
# refuses to run twice at once, and the fix is described where it lives.
# Those two rows stay, because a log that quietly loses its own bad
# measurements is not a log -- docs/64's rule. Set NOTE to say so in the
# next row rather than by rewriting the last:
#
#   NOTE="supersedes ..." scripts/verify.sh

set -u
cd "$(dirname "$0")/.."
REC=verification-log.tsv
MODE="${1:-record}"

py=$(timeout 1800 .venv/bin/pytest -q 2>&1 | tail -1)
py_n=$(printf '%s' "$py" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo 0)
py_f=$(printf '%s' "$py" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' || echo 0)

cc_out=$(timeout 3600 ./scripts/run_cocotb.sh 2>&1); cc_rc=$?
cc=$(printf '%s' "$cc_out" | tail -1)
# Exit 2 is the runner refusing a concurrent run. Recording 0 passed for
# that would put a zero in the log that looks like a measurement, which
# is the shape this whole file exists to stop.
if [ "$cc_rc" = "2" ]; then
    printf '%s\n' "$cc_out" | tail -3 >&2
    echo "verify.sh: no record written -- the cocotb count would not be one." >&2
    exit 2
fi
cc_n=$(printf '%s' "$cc" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo 0)
cc_f=$(printf '%s' "$cc" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' || echo 0)

# Formal is not re-run here: a full sby sweep is hours and the logs are
# already on disk from whoever ran it. This reads the verdicts that exist
# and says how old they are, which is honest about what it is checking.
fm_pass=0; fm_other=0; fm_oldest=""
for d in hw/soc/formal/*/ formal/*/; do
    [ -f "$d/logfile.txt" ] || continue
    v=$(grep -oE 'DONE \([A-Z]+' "$d/logfile.txt" | tail -1)
    case "$v" in *PASS) fm_pass=$((fm_pass+1)) ;; "") ;; *) fm_other=$((fm_other+1)) ;; esac
    t=$(date -r "$d/logfile.txt" +%Y-%m-%d 2>/dev/null)
    [ -z "$fm_oldest" ] && fm_oldest=$t
    [ "$t" \< "$fm_oldest" ] && fm_oldest=$t
done

head=$(git rev-parse --short HEAD)
dirty=$(git status --short | wc -l)
frozen=$(git status --short hw/rtl/ hw/tb/ tt/ formal/ hw/openlane/ | grep -vc '^??' || true)
line=$(printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s' \
    "$(date -u +%Y-%m-%dT%H:%MZ)" "$head" "$py_n" "$py_f" "$cc_n" "$cc_f" \
    "$fm_pass" "$fm_other" \
    "formal-logs-oldest=$fm_oldest,tree-dirty=$dirty,frozen-dirty=$frozen${NOTE:+,$NOTE}")

if [ "$MODE" = "--check" ]; then
    printf 'now:  %s\n' "$line"
    [ -f "$REC" ] && printf 'last: %s\n' "$(tail -1 "$REC")"
else
    [ -f "$REC" ] || printf 'utc\thead\tpytest_pass\tpytest_fail\tcocotb_pass\tcocotb_fail\tformal_pass\tformal_other\tnotes\n' > "$REC"
    printf '%s\n' "$line" >> "$REC"
    printf 'recorded: %s\n' "$line"
fi

[ "$py_f" = "0" ] && [ "$cc_f" = "0" ] && [ "$fm_other" = "0" ] && [ "$frozen" = "0" ]
