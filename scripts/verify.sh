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
#
# ---------------------------------------------------------------------
# 2026-09-09: THE FORMAL COLUMNS CHANGED MEANING, AND THE OLD ONES WERE
# WRONG IN THE ONE WAY THIS FILE EXISTS TO PREVENT.
#
# Every row up to and including 2026-09-08T22:35Z reads formal_pass=118
# and formal_other=0. Both numbers came from
#
#     for d in hw/soc/formal/*/ formal/*/; do ...
#
# which is a two-level glob over two directories. riscv-formal does not
# put its jobs there. docs/63 ran 163 SymbiYosys tasks per phase into
# hw/soc/out/rvformal-upstream/ and hw/soc/out/rvformal-secded/, plus the
# engine sweep and the corrected-model run, and every one of those job
# directories is four to six levels down under hw/soc/out/. The glob
# could not reach a single one. So the six FAILs, the three ERRORs and
# the twenty-six jobs that were killed without any verdict at all -- all
# of them documented in docs/63 sections 8.3, 8.4, 8.5 and 20 -- were
# STRUCTURALLY invisible, and the log said formal_other=0 for a tree that
# had thirty-five non-passing formal jobs in it. A total that cannot see
# a failure is worse than no total, because it is read as evidence.
#
# The old rows are LEFT STANDING, unedited, per docs/64. They are not
# false about what they measured; they are false about what they were
# taken to mean. Read them as "118 of the pilot and SoC-fabric tasks
# passed", which is true, and not as "the formal work is green".
#
# What the columns mean from this row on:
#
#   formal_pass   task directories whose verdict is PASS *and* whose
#                 src/ copies still match the sources they were made
#                 from (see "stale verdicts" below)
#   formal_other  every task directory that is not that: FAIL, ERROR,
#                 UNKNOWN, TIMEOUT, killed-without-a-verdict, PASS-but-
#                 stale, and PASS-but-uncheckable
#
# On the tree as it stands that is 425 and 35, against the old 118 and 0.
# The notes field carries the breakdown so the two are never confused.
#
# HOW A TASK DIRECTORY IS FOUND. A SymbiYosys workdir is the directory
# holding config.sby, and sby writes one wherever it is told to. The
# enumeration is therefore "every directory in the tree containing both
# config.sby and logfile.txt", which is location-independent by
# construction -- a new campaign written to a new path is counted the day
# it is run, with no glob to remember to widen. .git and .venv are
# excluded because neither can hold a real run.
#
# HOW THE VERDICT IS READ. sby writes a marker FILE named after the
# outcome (PASS, FAIL, ERROR, UNKNOWN, TIMEOUT) into the workdir, and it
# is more reliable than the log line the old code grepped: two engine-
# sweep jobs, hw/soc/out/rvf-eng-{secded,upstream}-bmc3/.../reg_ch0, died
# on a config error before any "DONE (" line was ever printed, so the old
# grep returned the empty string and the old case statement's `"") ;;`
# arm dropped them silently -- not counted as pass, not counted as other,
# not counted at all. The marker is read first and the DONE line is the
# fallback; a directory with neither is STOPPED, which is a real outcome
# and is counted, not dropped. Those two are the only disagreement in the
# tree today [fact, 2026-09-09].
#
# STALE VERDICTS. A PASS marker means "this passed", not "this passed on
# the code that is here now". sby copies every input into <workdir>/src/
# before it runs, so the run's own inputs are on disk and can be compared
# against the files config.sby names. That comparison is the second thing
# added here, and it is the answer to the second half of the review: the
# old code read the DONE line and the mtime, and an mtime tells you when
# a job finished, never what it read.
#
#   clean      every src/ copy is byte-identical to its origin
#   comment    they differ, but not after comment and whitespace removal
#   stale      they differ in code -- the verdict is about other bytes
#   unchecked  no src/, or an origin that no longer exists on disk
#
# `stale` and `unchecked` are counted in formal_other; a verdict that
# cannot be shown to be about today's code is not a pass here.
#
# WHY COMMENT-ONLY DIFFERENCES ARE NORMALISED AWAY, which is a judgement
# and not a fact. docs/14 section 9 stage 1 added two SPDX lines to every
# file in hw/rtl/ on 2026-09-09, and the property files took theirs at
# the same time. A byte comparison therefore calls 314 of the 1954 file
# pairs in this tree different, and every single one of them is a licence
# header. Reporting 300-odd stale verdicts on that would train the reader
# to ignore the column within one run, which is how a check dies. The
# normalisation used is docs/34 section 2.2's strip-and-compare, verbatim
# -- the same command that was used to establish that those same SPDX
# additions were comment-only in the first place, so this file is not
# inventing a second standard for the same question. Its limits, said
# rather than assumed: it deletes `//` inside string literals too, it
# does not understand `include` or macro expansion, and it splits
# config.sby lines on whitespace so a path containing a space would be
# misread. Not one of the 279 distinct source files this comparison
# reads contains `//` inside a string literal, and not one [files] line
# in the 460 config.sby files carries a path with a space in it [fact,
# 2026-09-09, grep and awk over the tree]. A code edit that only moves a
# comment is accepted as not-stale on purpose.
#
# WHAT THIS STILL DOES NOT SEE, so that the next reader does not have to
# rediscover it:
#
#   - The workdir's config.sby is compared to nothing. If the tracked
#     .sby that generated it has since changed its depth, its engine or
#     its assumptions, the src/ copies can be identical and the verdict
#     still stale. Catching that means re-deriving each task's config
#     from the tracked .sby, which is sby's own task expansion, and that
#     is not attempted here.
#   - Only PASS directories are staleness-checked. A stale FAIL is still
#     not a pass, so the bucket is right either way, but the notes will
#     not tell you a FAIL is old.
#   - Origins are compared as they are on disk, not as committed. A
#     dirty working tree makes the comparison stricter, never looser;
#     tree-dirty in the notes is the other half of that reading.
#   - formal/eqy/out/ is NOT counted. Those five directories are Yosys
#     eqy equivalence checks, not sby tasks, they carry no config.sby,
#     and two of them are mutants whose FAIL is the intended result --
#     folding a tool with an inverted verdict convention into this total
#     would corrupt it in both directions. docs/64 is where they live.
#
# THE EXIT CODE IS NOW NONZERO ON THIS TREE, AND THAT IS THE ANSWER.
# formal_other is 35 and the gate below still includes it. Nothing here
# whitelists the known-and-explained failures of docs/63, because an
# allowlist maintained inside a counter is how a counter starts lying,
# and this file exists because of one that did. If the project wants a
# green gate it has to first decide, in a tracked artefact, which of the
# thirty-five are expected -- and that is a decision about the formal
# work, not about this script. Until then the failing directories are
# printed to stderr so the red is actionable rather than merely red.

set -u
cd "$(dirname "$0")/.."
REC=verification-log.tsv
MODE="${1:-record}"

# --dispositions RUNS THE FORMAL SCAN AND NOTHING ELSE, in about a
# second, and it exists so that formal-dispositions.tsv is a file someone
# can actually iterate on.
#
# The full run re-runs pytest and cocotb first and takes about twenty
# minutes. Nobody edits a 35-row disposition table three times under that,
# which means in practice nobody would have exercised the drift and hole
# checks at all -- and an unexercised guard is the thing this repository
# keeps finding. This mode writes no row and gates on the same
# fm_undisp the record mode does.
SKIP_SUITES=0
case "$MODE" in
    --dispositions) SKIP_SUITES=1 ;;
esac

if [ "$SKIP_SUITES" = 1 ]; then
    py_n=0; py_f=0; cc_n=0; cc_f=0; cc_dirty=0
fi

# THE EXIT STATUS IS NOT OPTIONAL. This used to be a bare pipeline into
# `tail -1`, so pytest's status was discarded and only its last line was
# parsed. A collection error, an import failure or the 1800 s timeout
# produces a last line with no "passed" in it, and the row went in as
# pytest_pass=0, pytest_fail=0 -- which then PASSED the gate at the end
# of this file, because zero failures is what it looks for. A recorder
# that logs a zero for "the suite did not run" is the shape this file
# exists to stop, and it had it. Found in audit 2026-09-10.
if [ "$SKIP_SUITES" = 0 ]; then
py_out=$(timeout 1800 .venv/bin/pytest -q 2>&1); py_rc=$?
py=$(printf '%s' "$py_out" | tail -1)
if ! printf '%s' "$py" | grep -qE '[0-9]+ (passed|failed|error)'; then
    printf '%s\n' "$py_out" | tail -15 >&2
    echo "verify.sh: pytest produced no summary line (rc=$py_rc)." >&2
    echo "No record written -- a zero here would look like a measurement." >&2
    exit 3
fi
py_n=$(printf '%s' "$py" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo 0)
py_f=$(printf '%s' "$py" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' || echo 0)
py_e=$(printf '%s' "$py" | grep -oE '[0-9]+ error' | grep -oE '[0-9]+' || echo 0)
py_f=$((py_f + py_e))

cc_out=$(timeout 3600 ./scripts/run_cocotb.sh 2>&1); cc_rc=$?
cc=$(printf '%s' "$cc_out" | tail -1)
# The runner's own third field is "N suite(s) not clean", and it was
# parsed by nothing: a total build failure prints "0 passed, 0 failed"
# and gated GREEN. Added 2026-09-10 with the pytest fix above.
cc_dirty=$(printf '%s' "$cc" | grep -oE '[0-9]+ suite\(s\) not clean' \
    | grep -oE '^[0-9]+' || echo 0)
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
fi   # SKIP_SUITES

# Formal is not re-run here: a full sby sweep is hours and the logs are
# already on disk from whoever ran it. This reads the verdicts that exist,
# checks each one is still about the code in the tree, and says how old
# they are, which is honest about what it is checking.

# docs/34 section 2.2's normalisation, verbatim: block comments, line
# comments and whitespace runs removed, blank lines dropped.
code_digest() {
    sed -e ':a' -e 'N' -e '$!ba' -e 's:/\*[^*]*\*\+\([^/*][^*]*\*\+\)*/::g' \
    | sed -e 's://.*::' -e 's:[[:space:]]\+: :g' -e 's:^ ::' -e 's: $::' \
    | grep -v '^$' | sha256sum
}

# Compare <workdir>/src/ against the files config.sby names. sby resolves
# a relative [files] path against the directory holding the .sby, which
# is the workdir's parent. Prints clean, comment, stale or unchecked.
src_state() {
    local d=$1 parent res=clean a b dest src origin
    parent=$(dirname "$d")
    [ -d "$d/src" ] || { echo unchecked; return; }
    while read -r a b; do
        [ -n "$a" ] || continue
        if [ -n "${b:-}" ]; then dest=$a; src=$b; else src=$a; dest=$(basename "$a"); fi
        case "$src" in /*) origin=$src ;; *) origin="$parent/$src" ;; esac
        if [ ! -f "$origin" ] || [ ! -f "$d/src/$dest" ]; then res=unchecked; continue; fi
        cmp -s "$origin" "$d/src/$dest" && continue
        if [ "$(code_digest <"$origin")" = "$(code_digest <"$d/src/$dest")" ]; then
            [ "$res" = clean ] && res=comment
        else
            echo stale; return
        fi
    done < <(awk '/^\[files\]/{f=1;next} /^\[/{f=0} f&&NF' "$d/config.sby")
    echo "$res"
}

fm_pass=0; fm_fail=0; fm_err=0; fm_stop=0; fm_misc=0
fm_stale=0; fm_unchk=0; fm_cmt=0; fm_dirs=0; fm_oldest=""
fm_bad=""
while IFS= read -r cfg; do
    d=${cfg%/config.sby}
    [ -f "$d/logfile.txt" ] || continue
    fm_dirs=$((fm_dirs+1))

    v=""
    for m in PASS FAIL ERROR UNKNOWN TIMEOUT; do
        [ -f "$d/$m" ] && { v=$m; break; }
    done
    if [ -z "$v" ]; then
        v=$(grep -oE 'DONE \([A-Z]+' "$d/logfile.txt" | tail -1); v=${v#DONE (}
    fi
    [ -z "$v" ] && v=STOPPED

    if [ "$v" = PASS ]; then
        case "$(src_state "$d")" in
            clean)     fm_pass=$((fm_pass+1)) ;;
            comment)   fm_pass=$((fm_pass+1)); fm_cmt=$((fm_cmt+1)) ;;
            stale)     fm_stale=$((fm_stale+1)); fm_bad="$fm_bad$v-STALE $d"$'\n' ;;
            unchecked) fm_unchk=$((fm_unchk+1)); fm_bad="$fm_bad$v-UNCHECKED $d"$'\n' ;;
        esac
    else
        case "$v" in
            FAIL)    fm_fail=$((fm_fail+1)) ;;
            ERROR)   fm_err=$((fm_err+1)) ;;
            STOPPED) fm_stop=$((fm_stop+1)) ;;
            *)       fm_misc=$((fm_misc+1)) ;;
        esac
        fm_bad="$fm_bad$v $d"$'\n'
    fi

    t=$(date -r "$d/logfile.txt" +%Y-%m-%d 2>/dev/null)
    [ -z "$fm_oldest" ] && fm_oldest=$t
    [ "$t" \< "$fm_oldest" ] && fm_oldest=$t
done < <(find . -name config.sby -not -path './.git/*' -not -path './.venv/*' | sort)
fm_other=$((fm_fail+fm_err+fm_stop+fm_misc+fm_stale+fm_unchk))

# THE DISPOSITIONS, READ AFTER THE COUNT AND NEVER BEFORE IT.
#
# formal-dispositions.tsv names the directories whose non-PASS verdict is
# a decision this project has recorded, with the document section that
# records it. It changes NO count above: fm_other stays the true number
# of directories that are not a fresh PASS, and always will, because the
# header of this file is right that an allowlist inside a counter is how
# a counter starts lying.
#
# What it adds is fm_undisp -- the non-PASS directories NOT dispositioned
# -- and that is what the gate at the end reads. So a new red turns the
# gate red on the run it appears, while the thirty-five that were
# decided in docs/63 stay counted, stay printed and stay amber.
#
# Two ways a disposition is checked, not one:
#   * VERDICT DRIFT. A row says STOPPED and the directory now says FAIL:
#     that is a new fact and this file must not absorb it silently.
#   * A HOLE. A row names a directory that now PASSES, or that no longer
#     exists as a task at all: the row is stale and hides a check.
DISP=formal-dispositions.tsv
fm_undisp=0
disp_drift=""
disp_stale=""
if [ -f "$DISP" ]; then
    while IFS= read -r bad_line; do
        [ -n "$bad_line" ] || continue
        bv=${bad_line%% *}
        bd=${bad_line#* }
        bd=${bd#./}
        want=$(awk -F'\t' -v p="$bd" '$1==p {print $2; exit}' "$DISP")
        if [ -z "$want" ]; then
            fm_undisp=$((fm_undisp+1))
        elif [ "$want" != "$bv" ]; then
            disp_drift="$disp_drift  $bd: dispositioned $want, now $bv"$'\n'
            fm_undisp=$((fm_undisp+1))
        fi
    done < <(printf '%s' "$fm_bad")

    # The other direction, with MISSING held apart from CHANGED --
    # docs/80 section 3's distinction, and it matters here for the same
    # reason. Every path in this file is a git-ignored run tree, so on a
    # clone none of them exists and every row would read as a hole: the
    # gate would be red on a fresh checkout, which is a gate nobody runs.
    # A row is a hole only when the directory IS on this machine and is
    # no longer classified as not-a-fresh-PASS.
    while IFS=$'\t' read -r dp dv _rest; do
        case "$dp" in ''|'#'*) continue ;; esac
        [ -d "$dp" ] || continue
        printf '%s' "$fm_bad" | grep -qF " ./$dp" || \
            disp_stale="$disp_stale  $dp (dispositioned $dv)"$'\n'
    done < "$DISP"
fi

if [ -n "$fm_bad" ]; then
    printf 'verify.sh: %d formal task directories are not a fresh PASS, %d of them undispositioned:\n' \
        "$fm_other" "$fm_undisp" >&2
    printf '%s' "$fm_bad" | sort >&2
fi
if [ -n "$disp_drift" ]; then
    printf 'verify.sh: a dispositioned directory CHANGED its verdict:\n%s' "$disp_drift" >&2
    printf 'A disposition records a decision about one outcome. A different outcome\n' >&2
    printf 'is a new fact and needs a new decision, in %s, with a date.\n' "$DISP" >&2
fi
if [ -n "$disp_stale" ]; then
    printf 'verify.sh: these dispositions no longer match anything:\n%s' "$disp_stale" >&2
    printf 'Either the directory now PASSES -- delete the row, it is hiding a check --\n' >&2
    printf 'or the task is gone and the row is a fossil. Both are edits to %s.\n' "$DISP" >&2
    fm_undisp=$((fm_undisp+1))
fi

head=$(git rev-parse --short HEAD)
dirty=$(git status --short | wc -l)
frozen=$(git status --short hw/rtl/ hw/tb/ tt/ formal/ hw/openlane/ | grep -vc '^??' || true)
fmnote="formal-dirs=$fm_dirs,formal-fail=$fm_fail,formal-error=$fm_err"
fmnote="$fmnote,formal-stopped=$fm_stop,formal-stale=$fm_stale"
fmnote="$fmnote,formal-unchecked=$fm_unchk,formal-src-comment-drift=$fm_cmt"
fmnote="$fmnote,formal-undispositioned=$fm_undisp"
line=$(printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s' \
    "$(date -u +%Y-%m-%dT%H:%MZ)" "$head" "$py_n" "$py_f" "$cc_n" "$cc_f" \
    "$fm_pass" "$fm_other" \
    "formal-logs-oldest=$fm_oldest,$fmnote,cocotb-suites-not-clean=$cc_dirty,tree-dirty=$dirty,frozen-dirty=$frozen${NOTE:+,$NOTE}")

if [ "$SKIP_SUITES" = 1 ]; then
    printf '%d formal task directories, %d not a fresh PASS, %d undispositioned\n' \
        "$fm_dirs" "$fm_other" "$fm_undisp"
elif [ "$MODE" = "--check" ]; then
    printf 'now:  %s\n' "$line"
    [ -f "$REC" ] && printf 'last: %s\n' "$(tail -1 "$REC")"
else
    [ -f "$REC" ] || printf 'utc\thead\tpytest_pass\tpytest_fail\tcocotb_pass\tcocotb_fail\tformal_pass\tformal_other\tnotes\n' > "$REC"
    printf '%s\n' "$line" >> "$REC"
    printf 'recorded: %s\n' "$line"
fi

# THE GATE READS fm_undisp, NOT fm_other, and the difference is the whole
# point of formal-dispositions.tsv. fm_other is the true count and is
# recorded in the row either way; what the exit code answers is "did
# anything become not-a-PASS that nobody has decided about". A gate that
# can never be green carries as little information as one that can never
# be red, and this one could never be green.
#
# cc_dirty IS IN THE GATE, and until 2026-09-11 it was parsed, recorded
# and read by nothing. Its own comment forty lines up says why it exists
# -- "a total build failure prints 0 passed, 0 failed and gated GREEN" --
# and then the gate did not look at it, so the condition it was added to
# catch still passed. The cocotb completeness check added the same day
# reports through exactly this field: a test module that no makefile
# runs makes run_cocotb.sh count a not-clean suite, and without this
# term that check could not turn any gate red either.
[ "$py_f" = "0" ] && [ "$cc_f" = "0" ] && [ "$cc_dirty" = "0" ] \
    && [ "$fm_undisp" = "0" ] && [ "$frozen" = "0" ]
