#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

# Run every cocotb suite in the repository and report one line per suite.
#
#   scripts/run_cocotb.sh              every suite
#   scripts/run_cocotb.sh soc          only suites whose name contains "soc"
#
# Why this exists: `pytest` at the repository root runs sw/tests only. The
# cocotb suites are separate Makefiles under hw/tb and hw/soc/tb/cocotb and
# are not reached by it, so quoting a pytest total as "the tests pass" is
# wider than what was measured. This script is the other half.
#
# It parses each suite's results XML rather than trusting the make exit
# code, because a cocotb suite can report TESTS=n PASS=n and then segfault
# in Icarus teardown -- observed on Makefile.soc_clint and reproducible on
# committed RTL. That is a tool defect, not a design one, and the XML is
# the evidence that survives it.
#
# Stale results_*.xml files from mutation experiments live in the same
# directories and are gitignored. They are deliberately NOT scanned: this
# script only reads the XML each suite writes on this run, deleting it
# first so a stale file cannot be mistaken for a result.

set -u
cd "$(dirname "$0")/.."
ROOT=$(pwd)
FILTER="${1:-}"

# ONE RUN AT A TIME, and the reason is measured rather than hypothetical.
#
# Every suite is counted by "the results XMLs written since this marker",
# which orders by TIME and not by owner. Two concurrent runs therefore
# each count the other's output: on 2026-09-08 two overlapping runs of
# scripts/verify.sh recorded 558 and 624 cocotb tests for a 401-test
# repository, and both landed in verification-log.tsv looking exactly
# like measurements.
#
# That is the same defect docs/66 recorded one scale down -- a suite
# counting the previous suite's XML because the marker was a second-
# resolution timestamp -- and the marker file fixed the timestamp half
# without touching the ownership half. This is the ownership half.
#
# It FAILS rather than waits. A verification runner that silently queues
# behind another has a wall time that depends on what else is running,
# and the caller who asked for a measurement gets one late instead of
# being told it cannot have one now.
LOCK="$ROOT/.run_cocotb.lock"
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "run_cocotb.sh: another run holds $LOCK." >&2
    echo "Counting is by 'XMLs newer than a marker', which cannot tell two" >&2
    echo "concurrent runs apart, so this one refuses rather than inflate." >&2
    exit 2
fi

fail_total=0
pass_total=0
suite_fail=0

run_one() {
    local dir=$1 mk=$2 name=$3
    # Clean first. A .vvp left by the pinned oss-cad-suite Icarus (14.0) is
    # refused by a system iverilog (12.0) with "VVP input file 14.0 can not
    # be run with run time version 12.0", which presents as a build failure
    # of the current source rather than as stale output. Observed on
    # Makefile.soc_busstat.
    (cd "$dir" && timeout 300 make -f "$mk" clean >/dev/null 2>&1)
    # The results file is NOT always results_<makefile-suffix>.xml: the
    # hw/tb suites set COCOTB_RESULTS_FILE to results_<module>_<TAG>.xml, so
    # guessing the name reports a passing suite as missing. Collect every
    # XML written during this run instead, which is exact because the run is
    # serial.
    # A marker file, touched AFTER the pause, is what "written during this
    # run" is measured against. It used to be `date +%s` taken BEFORE the
    # pause and compared with -newermt at one-second granularity, and
    # docs/66 measured what that costs: the previous suite's XML, written
    # in the same second the timestamp was taken, was counted again under
    # this suite's name -- soc_qspi reported 47 tests for a 16-test suite
    # because soc_npu's 31 had landed 3 s earlier. A fast suite after a
    # slow one is exactly the shape the race needed.
    local marker
    marker=$(mktemp "$dir/.run_cocotb.XXXXXX")
    sleep 1
    touch "$marker"
    local log
    log=$(cd "$dir" && timeout 900 make -f "$mk" 2>&1)
    local rc=$?
    # ALL XMLs written during this run, not the newest one: a parameterised
    # suite (TAG=...) writes several, and taking one made the total drift
    # between runs -- soc_gptimer once read 10, then 3 -- while "0 failed"
    # stayed true. Sum them.
    local xmls
    xmls=$(find "$dir" -maxdepth 1 -name 'results_*.xml' -newer "$marker" -print 2>/dev/null)
    rm -f "$marker"
    if [ -z "$xmls" ]; then
        printf '  %-28s NO XML (make rc=%s)\n' "$name" "$rc"
        suite_fail=$((suite_fail + 1))
        printf '%s\n' "$log" | tail -3 | sed 's/^/      /'
        return
    fi
    read -r t f < <(printf '%s\n' "$xmls" | python3 -c '
import sys, xml.etree.ElementTree as ET
t = f = 0
for p in sys.stdin.read().split():
    try:
        r = ET.parse(p).getroot()
        cases = [e for e in r.iter() if e.tag.endswith("testcase")]
        t += len(cases)
        f += sum(1 for c in cases if any(ch.tag.endswith(("failure", "error")) for ch in c))
    except Exception:
        t = f = -1; break
print(t, f)')
    pass_total=$((pass_total + t - f))
    fail_total=$((fail_total + f))
    if [ "$f" != "0" ]; then
        printf '  %-28s %s tests, %s FAILED\n' "$name" "$t" "$f"
        suite_fail=$((suite_fail + 1))
    elif [ "$rc" != "0" ]; then
        # XML clean but make returned non-zero: the teardown-crash case.
        printf '  %-28s %s tests, all pass (make rc=%s, see header)\n' "$name" "$t" "$rc"
    else
        printf '  %-28s %s tests, all pass\n' "$name" "$t"
    fi
}

# Suites that WRITE INTO A FROZEN DIRECTORY are skipped by default.
# hw/tb/Makefile.fi regenerates hw/tb/fi_campaign_results.json, which
# docs/34-pilot-freeze.md pins by git blob hash for the TTIHP26b
# submission; running it here rewrote that file's wall_seconds field and
# dirtied the frozen tree. The campaign is reproducible on demand and its
# result is committed, so a verification runner has no business re-deriving
# it. Same for the two gate-level suites, which need artefacts from a
# hardening run rather than from the source tree.
#
#   RUN_FROZEN=1 scripts/run_cocotb.sh   include them anyway
SKIP_DEFAULT="fi gl glfi"

for spec in "hw/tb:Makefile" "hw/soc/tb/cocotb:Makefile"; do
    dir=${spec%%:*}
    [ -d "$ROOT/$dir" ] || continue
    echo "== $dir"
    for mk in "$ROOT/$dir"/Makefile.*; do
        [ -f "$mk" ] || continue
        name=$(basename "$mk"); name=${name#Makefile.}
        [ -z "$FILTER" ] || case "$name" in *"$FILTER"*) ;; *) continue ;; esac
        if [ "${RUN_FROZEN:-0}" != "1" ]; then
            case " $SKIP_DEFAULT " in
                *" $name "*) printf '  %-28s skipped (see SKIP_DEFAULT)\n' "$name"; continue ;;
            esac
        fi
        run_one "$ROOT/$dir" "$(basename "$mk")" "$name"
    done
done

echo
echo "cocotb: $pass_total passed, $fail_total failed, $suite_fail suite(s) not clean"
[ "$fail_total" = "0" ] && [ "$suite_fail" = "0" ]
