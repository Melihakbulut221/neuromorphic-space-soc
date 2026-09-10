#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

# Run every cocotb suite in the repository and report one line per suite.
#
#   scripts/run_cocotb.sh              every suite
#   scripts/run_cocotb.sh soc          only suites whose name contains "soc"
#
# Why this exists: `pytest` at the repository root runs sw/tests only. The
# cocotb suites are separate Makefiles under hw/tb, hw/soc/tb/cocotb and
# tt/test and are not reached by it, so quoting a pytest total as "the
# tests pass" is wider than what was measured. This script is the other
# half.
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

# Extra arguments appended to both make invocations in run_one, set by a
# caller immediately before it and cleared immediately after. Only tt/test
# uses it, to force GATES on the command line where it beats the
# environment; see the tt/test block at the bottom.
EXTRA_MAKE_ARGS=""

run_one() {
    local dir=$1 mk=$2 name=$3
    # The results-file glob. Every suite under hw/tb and hw/soc/tb/cocotb
    # writes results_<something>.xml, which is why that is the default.
    # tt/test does not: its Makefile is generated from the upstream Tiny
    # Tapeout template and leaves cocotb's own default, results.xml, and
    # tt/.gitignore lists `test/results.xml` by that exact name. Renaming
    # it with COCOTB_RESULTS_FILE would leave an untracked file inside a
    # frozen directory, so the collector is told the name instead.
    local pattern="${4:-results_*.xml}"
    # Clean first. A .vvp left by the pinned oss-cad-suite Icarus (14.0) is
    # refused by a system iverilog (12.0) with "VVP input file 14.0 can not
    # be run with run time version 12.0", which presents as a build failure
    # of the current source rather than as stale output. Observed on
    # Makefile.soc_busstat.
    (cd "$dir" && timeout 300 make -f "$mk" $EXTRA_MAKE_ARGS clean >/dev/null 2>&1)
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
    log=$(cd "$dir" && timeout 900 make -f "$mk" $EXTRA_MAKE_ARGS 2>&1)
    local rc=$?
    # ALL XMLs written during this run, not the newest one: a parameterised
    # suite (TAG=...) writes several, and taking one made the total drift
    # between runs -- soc_gptimer once read 10, then 3 -- while "0 failed"
    # stayed true. Sum them.
    local xmls
    xmls=$(find "$dir" -maxdepth 1 -name "$pattern" -newer "$marker" -print 2>/dev/null)
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

# Modules that share another suite's Makefile, run as
# `make -f Makefile.<parent> MODULE=<module>`.
#
# WHY A TABLE AND NOT MORE MAKEFILES. Both of these exist to be run twice
# -- once against the tree and once against a copy of the RTL from before
# a fix -- so their headers document a command line with MODULE= on it,
# and a Makefile of their own would be a second place to keep the sources
# and parameters in step. The completeness check below is what makes the
# table safe: a module that is neither some Makefile's default nor listed
# here is an ERROR, not a silent skip.
#
#   dir|parent makefile|module|sim build|results file
EXTRA_MODULES="\
hw/soc/tb/cocotb|Makefile.soc_npu|test_soc_npu_defects|sim_build_npu_defects|results_soc_npu_defects.xml
hw/soc/tb/cocotb|Makefile.soc_wdog|test_soc_wdog_strap|sim_build_soc_wdog_strap|results_soc_wdog_strap.xml
hw/soc/tb/cocotb|Makefile.soc_uart|test_soc_uart_defects|sim_build_uart_defects|results_soc_uart_defects.xml"

for spec in "hw/tb:Makefile" "hw/soc/tb/cocotb:Makefile"; do
    dir=${spec%%:*}
    [ -d "$ROOT/$dir" ] || continue
    echo "== $dir"
    # `Makefile.*` AND a plain `Makefile`. hw/tb/Makefile is the aer_fifo
    # suite -- 
    # the block ROADMAP gate G0 signed off on and the one whose pointers
    # are triplicated -- and the glob does not match a name with no dot in
    # it, so this runner's own header sentence ("every cocotb suite in the
    # repository") excluded it from the day it was written. Same shape as
    # the tt/test block below, found the same way and fixed here instead
    # of there because this loop is where it belongs.
    for mk in "$ROOT/$dir"/Makefile "$ROOT/$dir"/Makefile.*; do
        [ -f "$mk" ] || continue
        name=$(basename "$mk")
        # A plain `Makefile` leaves cocotb's own default results file
        # name, `results.xml`, exactly as tt/test's does -- so the
        # collector has to be told, or it finds no XML, prints NO XML
        # against a suite whose own summary said 20 passed, and counts
        # zero. Measured: that is what the first version of this loop
        # did.
        pattern='results_*.xml'
        case "$name" in
            Makefile) name=$(basename "$dir"); pattern='results.xml' ;;
            *)        name=${name#Makefile.} ;;
        esac
        [ -z "$FILTER" ] || case "$name" in *"$FILTER"*) ;; *) continue ;; esac
        if [ "${RUN_FROZEN:-0}" != "1" ]; then
            case " $SKIP_DEFAULT " in
                *" $name "*) printf '  %-28s skipped (see SKIP_DEFAULT)\n' "$name"; continue ;;
            esac
        fi
        run_one "$ROOT/$dir" "$(basename "$mk")" "$name" "$pattern"
    done
    # A HERE-STRING, NOT A PIPE. `... | while read` puts the loop in a
    # subshell, and run_one's pass_total / fail_total / suite_fail
    # increments would be lost with it: every extra suite would run, print
    # its line, and contribute nothing to the totals or the exit code.
    # That is the same shape of defect this block exists to close.
    while IFS='|' read -r xdir xmk xmod xbuild xres; do
        [ -n "$xdir" ] || continue
        [ "$xdir" = "$dir" ] || continue
        [ -z "$FILTER" ] || case "$xmod" in *"$FILTER"*) ;; *) continue ;; esac
        saved_args=$EXTRA_MAKE_ARGS
        EXTRA_MAKE_ARGS="$EXTRA_MAKE_ARGS MODULE=$xmod SIM_BUILD=$xbuild COCOTB_RESULTS_FILE=$xres"
        run_one "$ROOT/$dir" "$xmk" "$xmod" "$xres"
        EXTRA_MAKE_ARGS=$saved_args
    done <<< "$EXTRA_MODULES"
done

# ------------------------------------------------- completeness check
#
# EVERY test_*.py IN THOSE TWO DIRECTORIES MUST BE REACHED BY SOMETHING.
#
# This runner's header claims it runs every cocotb suite in the
# repository, and on 2026-09-11 three did not run: `test_aer_fifo`, whose
# Makefile is named `Makefile` and so was outside the glob;
# `test_soc_npu_defects` and `test_soc_wdog_strap`, each written to fail
# against the RTL as it was before a fix and each reachable only by
# typing MODULE= by hand. All three were green, all three were invisible,
# and an edit re-opening the defect two of them exist to catch would have
# passed every check in the tree.
#
# The loop above and the table above it fix those three. This check is
# what stops the fourth: a new test module that no Makefile defaults to
# and the table does not name is an ERROR here, in the runner, at the
# moment it is added -- not a suite that quietly never runs. A module
# deliberately left out belongs in SKIP_MODULES with the reason, which is
# a decision someone has to write down.
SKIP_MODULES=""

missing=""
for dir in hw/tb hw/soc/tb/cocotb; do
    [ -d "$ROOT/$dir" ] || continue
    for tf in "$ROOT/$dir"/test_*.py; do
        [ -f "$tf" ] || continue
        mod=$(basename "$tf" .py)
        case " $SKIP_MODULES " in *" $mod "*) continue ;; esac
        # Reached if some Makefile in this directory names it as MODULE or
        # COCOTB_TEST_MODULES, or the table above lists it.
        if grep -qhE "^(MODULE|COCOTB_TEST_MODULES)[[:space:]]*[?:]?=[[:space:]]*(.*[[:space:]])?$mod([[:space:]]|\$)" \
                "$ROOT/$dir"/Makefile "$ROOT/$dir"/Makefile.* 2>/dev/null; then
            continue
        fi
        case "$EXTRA_MODULES" in *"|$mod|"*) continue ;; esac
        missing="$missing $dir/$mod"
    done
done

if [ -n "$missing" ]; then
    echo
    echo "UNREACHED cocotb test modules -- no Makefile defaults to them and"
    echo "EXTRA_MODULES does not name them:"
    for m in $missing; do echo "    $m"; done
    echo
    echo "A suite nothing runs is not evidence. Give it a Makefile, add it to"
    echo "EXTRA_MODULES with its parent makefile and its own SIM_BUILD and"
    echo "results file, or put it in SKIP_MODULES with the reason."
    suite_fail=$((suite_fail + 1))
fi

# ------------------------------------------------------------- tt/test
#
# THE SUBMISSION'S OWN SUITE, and until 2026-09-10 no harness in this
# repository reached it.
#
# tt/test is what the Tiny Tapeout `test` workflow runs. Its badge is the
# third one on the first line of tt/README.md and ROADMAP treats its green
# state as evidence for P1. The loop above iterates hw/tb and
# hw/soc/tb/cocotb only, so the sentence at the top of this file -- "every
# cocotb suite in the repository" -- excluded the five tests that decide
# the badge on the thing being taped out. It costs about four seconds.
#
# tt/test is FROZEN and GENERATED (scripts/gen_tt_submission.py, from the
# upstream template at 6598bef4d315), so it cannot carry its own guards
# and cannot be edited to acquire them. Three consequences, all handled
# here rather than there:
#
#   1. It is ONE Makefile named `Makefile`, so the Makefile.* glob above
#      does not see it. Hence a block of its own rather than a third
#      entry in the spec list.
#
#   2. Its results file is `results.xml`. See run_one's `pattern`.
#
#   3. GATES, and this is the one that matters. The template selects
#      gate level with `ifneq ($(GATES),yes)`, which reads the
#      ENVIRONMENT, and unlike hw/tb/Makefile.gl it does not check the
#      simulator version. Makefile.gl's check is a hard error for a
#      measured reason: the ihp-sg13g2 cell models drive their outputs
#      from delayed_D, delayed_CLK and delayed_RESET_B, the
#      negative-timing-check outputs of $setuphold and $recrem, which
#      Icarus 12 does not implement and warns about once per cell. Every
#      sg13g2_dfrbpq_1 output then sits at x for the whole run and the
#      design reads back zeros. On THIS suite that is 1 of 5 passing
#      (docs/15 section 5.4, and tt/test/README.md carries the note so it
#      travels with the submission); in hw/tb it was 21 of 21 failing
#      (docs/24 section 3.1). Both read exactly like a dead netlist and
#      neither is one, and the only thing that says otherwise is a
#      compile warning cocotb prints thousands of lines earlier. The
#      iverilog on PATH on this machine IS 12.0.
#
#      So `GATES=` is forced on the make command line, where it beats an
#      exported GATES=yes -- a caller who has GATES=yes in the
#      environment for hw/tb/Makefile.gl must not silently convert this
#      suite into an unguarded gate-level run. Gate level here is opt-in
#      through TT_GATES=1, and then this block applies the version check
#      Makefile.gl has and tt/test does not, plus the two things the
#      template's own README says are needed: a gate_level_netlist.v,
#      which nothing in this repository produces, and a PDK_ROOT for the
#      cell models. Anything missing is a REFUSAL counted as a suite
#      that is not clean, not a quiet fall back to RTL.
#
#   TT_GATES=1 scripts/run_cocotb.sh tt   run it against the netlist
TT_DIR="$ROOT/tt/test"
tt_name="tt-submission"
tt_wanted=1
[ -z "$FILTER" ] || case "$tt_name" in *"$FILTER"*) ;; *) tt_wanted=0 ;; esac

if [ -f "$TT_DIR/Makefile" ] && [ "$tt_wanted" = "1" ]; then
    echo "== tt/test"
    tt_args="GATES="
    tt_ok=1
    if [ "${TT_GATES:-0}" = "1" ]; then
        # Same discovery order as hw/tb/Makefile.gl: the plain Icarus 13
        # install first, then whatever is on PATH. The guard, not the
        # path, is what protects the result.
        tt_iverilog=""
        for cand in "$HOME/.local/opt/iverilog13/usr/bin/iverilog" \
                    "$(command -v iverilog 2>/dev/null || true)"; do
            [ -n "$cand" ] && [ -x "$cand" ] && { tt_iverilog=$cand; break; }
        done
        tt_major=$("${tt_iverilog:-false}" -V 2>/dev/null |
                   sed -n '1s/.*version \([0-9]*\).*/\1/p')
        if [ ! -f "$TT_DIR/gate_level_netlist.v" ]; then
            printf '  %-28s REFUSED: TT_GATES=1 but tt/test/gate_level_netlist.v is absent.\n' "$tt_name"
            printf '      Nothing in this repository produces it. Take it from the GDS action'"'"'s\n'
            printf '      tt_submission artefact or a local harden (tt/test/README.md), and delete\n'
            printf '      it afterwards -- a stale one silently tests the previous revision.\n'
            tt_ok=0
        elif [ -z "$tt_major" ] || [ "$tt_major" -lt 13 ] 2>/dev/null; then
            printf '  %-28s REFUSED: %s is Icarus %s; gate level needs >= 13.\n' \
                   "$tt_name" "${tt_iverilog:-<no iverilog found>}" "${tt_major:-?}"
            printf '      Icarus 12 leaves sg13g2_dfrbpq_1'"'"'s delayed_CLK undriven, so every flop\n'
            printf '      in the netlist is clocked by z, the design reads back zeros and the suite\n'
            printf '      reports 1 of 5 -- a dead MODEL that looks like a dead netlist. tt/test has\n'
            printf '      no version guard of its own; this is it. hw/tb/Makefile.gl section 3b.\n'
            tt_ok=0
        elif [ -z "${PDK_ROOT:-}" ]; then
            printf '  %-28s REFUSED: TT_GATES=1 needs PDK_ROOT; the template reads the sg13g2\n' "$tt_name"
            printf '      cell models from $PDK_ROOT/ihp-sg13g2/libs.ref/.\n'
            tt_ok=0
        else
            tt_args="GATES=yes"
            printf '  %-28s gate level, %s (Icarus %s)\n' \
                   "$tt_name" "$tt_iverilog" "$tt_major"
            PATH="$(dirname "$tt_iverilog"):$PATH"
        fi
        [ "$tt_ok" = "1" ] || suite_fail=$((suite_fail + 1))
    fi
    if [ "$tt_ok" = "1" ]; then
        # The template carries none of the venv re-invocation
        # hw/tb/Makefile.pilot has, because it is upstream's file. cocotb
        # lives in hw/.venv here, so put it on PATH when the caller has
        # not already.
        tt_path_save="$PATH"
        command -v cocotb-config >/dev/null 2>&1 || PATH="$ROOT/hw/.venv/bin:$PATH"
        EXTRA_MAKE_ARGS="$tt_args"
        run_one "$TT_DIR" Makefile "$tt_name" 'results.xml'
        EXTRA_MAKE_ARGS=""
        PATH="$tt_path_save"
    fi
fi

echo
echo "cocotb: $pass_total passed, $fail_total failed, $suite_fail suite(s) not clean"
[ "$fail_total" = "0" ] && [ "$suite_fail" = "0" ]
