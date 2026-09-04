#!/usr/bin/env bash
# Drive riscv-formal against this project's Ibex. docs/63.
#
#   flow/rvformal.sh setup                 build the work tree and
#                                          generate one .sby per check
#   flow/rvformal.sh run  [-jN] [check..]  run them (default: all)
#   flow/rvformal.sh report                summarise every status file
#
# Environment:
#   IBEX_REGFILE  upstream (DEFAULT HERE) or secded. docs/63 phase 1 is
#                 the stock core; phase 2 is the substituted register
#                 file of docs/43 section 6 and the delta between the
#                 two runs is the measurement. The default is the
#                 opposite of the SoC flows' default ON PURPOSE, and
#                 hw/soc/flow/ibex_sources.sh explains why the two
#                 families of flow default differently.
#   RVF_OUT       work tree. Default hw/soc/out/rvformal-$IBEX_REGFILE,
#                 so the two phases cannot overwrite each other's
#                 evidence.
#   RVF_JOBS      -j for the check makefile. Default: nproc.
#   RVF_INSN_FIX  0 (default) uses riscv-formal's instruction models
#                 exactly as fetched. 1 substitutes the two corrected
#                 copies in hw/soc/rvformal/insns/ for `div` and `rem`,
#                 whose upstream versions compute an UNSIGNED result --
#                 docs/63 section 7.5, which is a defect in the
#                 specification and not in the core.
#   RVF_LIVENESS_DEPTH
#                 check cycle for the `liveness` check only. Default 50,
#                 which is what docs/63 section 8 reports. It is
#                 overridable and nothing else is, because the
#                 instruction after a given one can be a 37-cycle
#                 divide and closing that costs a deeper unrolling than
#                 the rest of the set put together.
#
# WHY A WORK TREE AND NOT A DIRECTORY IN THE CHECKOUT
#
# riscv-formal's checks/genchecks.py derives its base directory as
# `cwd/../..` and its core name as the last path component of cwd, so
# the configuration it reads MUST sit two levels below a directory that
# also contains checks/ and insns/. Upstream's own cores live in
# <riscv-formal>/cores/<name>/. Putting ours there would make
# hw/soc/ext/riscv-formal a checkout with our files in it, and the rule
# hw/soc/tools.soc.mk applies to every fetched thing -- pinned, verified,
# gitignored, never vendored, `git status` clean -- would stop being
# true of it, exactly as docs/38 section 4.2 insists it stays true of
# hw/soc/ext/ibex.
#
# So the layout genchecks needs is BUILT, out of symlinks to the pristine
# checkout plus copies of the two tracked files:
#
#   $RVF_OUT/checks  -> ext/riscv-formal/checks     (symlink)
#   $RVF_OUT/insns   -> ext/riscv-formal/insns      (symlink)
#   $RVF_OUT/cores/ibex/wrapper.sv                  (copy of the tracked)
#   $RVF_OUT/cores/ibex/{checks,cover}.cfg          (expanded from .in)
#
# Everything under $RVF_OUT is generated and gitignored. The tracked
# sources are hw/soc/rvformal/ and this file.

set -euo pipefail

SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REPO=$(cd "$SOC_DIR/../.." && pwd)

# Tools through tools.soc.mk, never off PATH. tools.mk exists because a
# formal gate once resolved `sby` through a glob and silently ran a
# sibling project's toolchain; the same rule applies here and this is
# where it is applied.
eval "$(make -s -f "$SOC_DIR/tools.soc.mk" printvars)"

IBEX_REGFILE=${IBEX_REGFILE:-upstream}
export IBEX_REGFILE
export IBEX_GEN=genrvfi
export IBEX_FAULT_PORT=0

RVF_DIR=$SOC_DIR/ext/riscv-formal
RVF_OUT=${RVF_OUT:-$SOC_DIR/out/rvformal-$IBEX_REGFILE}
# ABSOLUTE, always. sby runs yosys from inside each check's src/
# directory and the generated script names the RTL by the path this
# variable holds; a relative RVF_OUT produces a read command that
# resolves against the wrong directory and fails with "Bad command",
# which names nothing. Found by passing a relative path.
mkdir -p "$(dirname "$RVF_OUT")"
RVF_OUT=$(cd "$(dirname "$RVF_OUT")" && pwd)/$(basename "$RVF_OUT")
CORE=ibex
RVF_JOBS=${RVF_JOBS:-$(nproc)}
# The one check depth that is a decision rather than a constant, and
# checks.cfg.in says why. 50 is what docs/63 section 8 reports.
RVF_LIVENESS_DEPTH=${RVF_LIVENESS_DEPTH:-50}
# Whether to substitute hw/soc/rvformal/insns/ for the two upstream
# instruction models docs/63 section 7.5 found a signedness defect in.
# DEFAULT 0 -- upstream's specification, unmodified, which is what the
# run docs/63 section 8 reports and what a reader checking this project
# against riscv-formal would expect to reproduce. Setting it to 1 is an
# experiment about the SPECIFICATION and it has to be asked for.
RVF_INSN_FIX=${RVF_INSN_FIX:-0}

. "$SOC_DIR/flow/ibex_sources.sh"

need_checkout () {
  if [ ! -d "$RVF_DIR/checks" ]; then
    echo "riscv-formal is not fetched. Run:" >&2
    echo "  make -f hw/soc/tools.soc.mk fetch-riscv-formal" >&2
    exit 2
  fi
}

# The pinned sby, put on PATH under its own name because the makefile
# genchecks.py writes calls a bare `sby`. Named, printed, and then
# CHECKED -- so this is not the glob resolution tools.mk was written to
# stop, it is the opposite of it.
put_sby_on_path () {
  test -x "$SBY" || { echo "ERROR: sby not found at '$SBY'." >&2; exit 2; }
  PATH="$(dirname "$SBY"):$PATH"
  export PATH
  local resolved
  resolved=$(command -v sby || true)
  if [ "$resolved" != "$SBY" ]; then
    echo "ERROR: 'sby' on PATH resolves to '$resolved', not the pinned" >&2
    echo "       '$SBY'. Refusing to run." >&2
    exit 2
  fi
  echo "== sby = $SBY"
}

cmd_setup () {
  need_checkout
  echo "== riscv-formal = $RVF_DIR @ $(git -C "$RVF_DIR" rev-parse HEAD)"
  echo "== RVF_INSN_FIX=$RVF_INSN_FIX  RVF_LIVENESS_DEPTH=$RVF_LIVENESS_DEPTH"
  echo "== ibex sources = $SOC_DIR/$IBEX_GEN, register file: $IBEX_REGFILE"

  rm -rf "$RVF_OUT"
  mkdir -p "$RVF_OUT/cores/$CORE"
  ln -s "$RVF_DIR/checks" "$RVF_OUT/checks"

  # insns/ is built entry by entry rather than symlinked whole, because
  # two of the models are substituted. Same rule as everywhere else here:
  # the checkout stays pristine and the substitution is a file list.
  mkdir -p "$RVF_OUT/insns"
  local f b
  for f in "$RVF_DIR"/insns/*; do ln -s "$f" "$RVF_OUT/insns/$(basename "$f")"; done
  if [ "$RVF_INSN_FIX" = 1 ]; then
    for f in "$SOC_DIR"/rvformal/insns/*.v; do
      b=$(basename "$f")
      test -f "$RVF_DIR/insns/$b" || {
        echo "ERROR: $b is not an upstream model; nothing to substitute." >&2
        exit 2; }
      rm -f "$RVF_OUT/insns/$b"
      ln -s "$f" "$RVF_OUT/insns/$b"
      echo "== insn model SUBSTITUTED: $b (docs/63 section 7.5)"
    done
  else
    echo "== insn models: upstream's, unmodified (RVF_INSN_FIX=0)."
    echo "   docs/63 section 7.5: insn_div and insn_rem compute an"
    echo "   UNSIGNED result and their checks FAIL against a correct core."
  fi

  # riscv-formal ships the per-ISA instruction lists generated; regenerate
  # them only if one is missing, and never write into the checkout.
  if [ ! -f "$RVF_DIR/insns/isa_rv32imc.txt" ]; then
    echo "ERROR: $RVF_DIR/insns/isa_rv32imc.txt is missing from the" >&2
    echo "       pinned checkout. Refusing to generate into it." >&2
    exit 2
  fi

  cp "$SOC_DIR/rvformal/wrapper.sv" "$RVF_OUT/cores/$CORE/wrapper.sv"

  # The parameter guard runs BEFORE anything is generated, so a moved
  # parameter is an error here and not seventy-nine green checks about a
  # different core.
  "$SOC_DIR/rvformal/params.sh" "$SOC_DIR"

  # The one rewritten file, docs/63 section 3. It lands in the work tree
  # and NOT in hw/soc/genrvfi/, so that directory stays exactly what
  # sv2v wrote and `diff` against a fresh conversion stays empty.
  python3 "$SOC_DIR/flow/rvfi_slangfix.py" "$SOC_DIR/$IBEX_GEN" "$RVF_OUT/rtl"

  # The core's file list, from the same function every other SoC flow
  # uses -- which is what makes phase 2 of docs/63 one environment
  # variable and not a second harness. Two substitutions on it:
  #   - genrvfi/ibex_top.v -> the rewritten copy above
  #   - the formal clock-gate model, which ibex_top instantiates and
  #     upstream leaves to the integrator
  local srcs
  srcs=$(ibex_sources "$SOC_DIR" | grep -v "/$IBEX_GEN/ibex_top\.v\$")
  srcs="$srcs
$RVF_OUT/rtl/ibex_top.v
$SOC_DIR/rvformal/prim_clock_gating_formal.v"

  # The two configurations, expanded from the one tracked template.
  # Python and not sed: the file list is multi-line and a sed `r`
  # against a here-string is the kind of construction that works until
  # a path contains the delimiter.
  RVF_SRCS="$srcs" RVF_LIVENESS_DEPTH="$RVF_LIVENESS_DEPTH" \
  python3 - "$SOC_DIR/rvformal/checks.cfg.in" \
                             "$RVF_OUT/cores/$CORE" <<'CFGPY'
import os, sys
tmpl = open(sys.argv[1]).read()
# read_slang takes its file list on one command line, so the newlines
# the source function emits become spaces here.
files = " ".join(os.environ["RVF_SRCS"].split())
for mode, name in (("bmc", "checks"), ("cover", "cover")):
    out = (tmpl.replace("@MODE@", mode)
                .replace("@IBEX_FILES@", files)
                .replace("@LIVENESS_DEPTH@", os.environ["RVF_LIVENESS_DEPTH"]))
    with open(os.path.join(sys.argv[2], name + ".cfg"), "w") as f:
        f.write(out)
CFGPY

  ( cd "$RVF_OUT/cores/$CORE" && python3 "$RVF_DIR/checks/genchecks.py" checks )
  ( cd "$RVF_OUT/cores/$CORE" && python3 "$RVF_DIR/checks/genchecks.py" cover  )

  echo "== work tree: $RVF_OUT/cores/$CORE"
  echo "== bmc   checks: $(ls "$RVF_OUT/cores/$CORE/checks"/*.sby | wc -l)"
  echo "== cover checks: $(ls "$RVF_OUT/cores/$CORE/cover"/*.sby  | wc -l)"
}

cmd_run () {
  need_checkout
  put_sby_on_path
  local jobs="-j$RVF_JOBS"
  case "${1:-}" in -j*) jobs=$1; shift;; esac
  local which=${RVF_WHICH:-both}
  local set
  for set in checks cover; do
    case "$which" in
      both) ;;
      "$set") ;;
      *) continue;;
    esac
    test -d "$RVF_OUT/cores/$CORE/$set" || { echo "run 'setup' first" >&2; exit 2; }
    echo "== running $set $jobs"
    # -k so one failure does not hide the other 200 results. The exit
    # status is deliberately not the gate: cmd_report is, because a
    # riscv-formal run whose value is in WHICH checks failed must not be
    # reduced to one bit.
    ( cd "$RVF_OUT/cores/$CORE/$set" && make -k $jobs -f makefile "$@" ) || true
  done
  cmd_report
}

cmd_report () {
  python3 - "$RVF_OUT/cores/$CORE" <<'PY'
import os, sys, glob
# sby writes "<STATUS> <returncode> <elapsed seconds>" into status.
# Read field 0 and not field -1: the first version of this read the last
# one and reported every check's runtime as its verdict, which is a
# report that cannot say FAIL. Caught by running it.
root = sys.argv[1]
for setname in ("checks", "cover"):
    d = os.path.join(root, setname)
    if not os.path.isdir(d):
        continue
    rows = {}
    for sby in sorted(glob.glob(os.path.join(d, "*.sby"))):
        name = os.path.basename(sby)[:-4]
        st = os.path.join(d, name, "status")
        if not os.path.exists(st):
            # NOT "NOT RUN": a job that was started and stopped leaves
            # no status file either, and 40 minutes of solver time
            # reported as "not run" is a label narrower than the thing
            # it describes. docs/63 section 8.4.
            rows[name] = ("NO STATUS", 0)
            continue
        f = open(st).read().split()
        rows[name] = (f[0], int(f[2])) if len(f) >= 3 else ("EMPTY", 0)
    tally = {}
    for v, _ in rows.values():
        tally[v] = tally.get(v, 0) + 1
    # The third field is sby's ELAPSED CLOCK time for that job, not CPU
    # time, so this sum is job-seconds under whatever -j the run used and
    # is not a core-hours figure. docs/63 section 9.
    secs = sum(t for _, t in rows.values())
    slow = sorted(rows.items(), key=lambda kv: -kv[1][1])[:5]
    print(f"== {setname}: {len(rows)} checks  " +
          "  ".join(f"{k}={v}" for k, v in sorted(tally.items())) +
          f"  job-seconds(wall)={secs}")
    print("   slowest: " + ", ".join(f"{n} {t}s" for n, (_, t) in slow))
    for name, (v, t) in sorted(rows.items()):
        if v != "PASS":
            print(f"   {v:8s} {name} ({t}s)")
PY
}

case "${1:-}" in
  setup)  shift; cmd_setup "$@" ;;
  run)    shift; cmd_run "$@" ;;
  report) shift; cmd_report "$@" ;;
  *) echo "usage: rvformal.sh {setup|run|report}" >&2; exit 2 ;;
esac
