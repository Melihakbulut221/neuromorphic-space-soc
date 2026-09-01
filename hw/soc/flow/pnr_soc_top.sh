#!/usr/bin/env bash
# Place and route soc_top -- the WHOLE SoC -- through LibreLane on IHP
# SG13G2, with the six RM_IHPSG13 SRAM macros of soc_mem_sram.v.
#
#   pnr_soc_top.sh <run-tag> [librelane args...]
#
#   pnr_soc_top.sh probe -T OpenROAD.STAPrePNR   # lint+synth+STA, minutes
#   pnr_soc_top.sh full                          # the whole flow
#   pnr_soc_top.sh full -F OpenROAD.CTS          # resume from a step
#
# docs/45 section 9 item 1: "Until something is placed, the honest
# summary of this document is 'it synthesises, and the number that
# decides the part is not a synthesis number'." This is the script that
# places it. docs/47 is the run.
#
# =====================================================================
# THE PILOT IS FROZEN AND THIS SCRIPT CANNOT TOUCH IT
# =====================================================================
#
# docs/34 pins the TTIHP26b submission by git blob hash and the shuttle
# closes 2026-09-21. hw/openlane/ -- run_trial.sh, pilot_ihp/,
# sram_pilot/, aer_fifo/ and all 36 of their run directories -- is READ
# by this script and never written. Three things follow and all three
# are enforced rather than intended:
#
#   * the config lives in hw/soc/pnr/, not hw/openlane/;
#   * the run directories are hw/soc/pnr/runs/<tag>, gitignored, named
#     by --run-tag so LibreLane cannot pick one for itself;
#   * this script refuses to run if its config directory would land
#     inside hw/openlane/.
#
# The settings this config takes from hw/openlane/sram_pilot and
# hw/openlane/pilot_ihp are COPIED with their reasons restated, and
# hw/soc/pnr/pdn_macro.tcl is a new file with the same content as the
# pilot's rather than a reference to it, so nothing here depends on a
# frozen file staying where it is.
#
# =====================================================================
# THE TOOLCHAIN IS THE PILOT'S, ROOTLESS, AND IT IS ASSERTED
# =====================================================================
#
# Same discipline hw/openlane/run_trial.sh established in docs/12: no
# docker, no root, no system package install. Per-tool shim wrappers in
# ~/.local/opt/llbin that each set their own LD_LIBRARY_PATH (the
# OpenROAD build ships a newer glibc that segfaults host binaries if it
# leaks into the ambient environment), a LibreLane virtualenv, and an
# oss-cad-suite checkout for Yosys.
#
# Two traps this script asserts against rather than hoping about:
#
#   1. --pdk MUST be on the command line. LibreLane's ciel wrapper
#      resolves and installs the PDK from the CLI option (default
#      sky130A) BEFORE config.json is read, so "PDK": "ihp-sg13g2" in
#      the config is then looked up inside the sky130 tree and the run
#      dies with "PDK not found".
#   2. A STALE ENABLED PDK DOES NOT ANNOUNCE ITSELF. ciel exposes one
#      version through the $PDK_ROOT/<pdk> symlink and everything
#      resolves through it, so hardening against a PDK the tool was
#      never tested on looks exactly like hardening against the right
#      one. The pin is read out of the installed wheel's
#      pdk_hashes.yaml, not hard-coded here, and compared.
#
# =====================================================================
# WHY VERILOG_FILES IS NOT IN config.json
# =====================================================================
#
# The source list is about forty paths and its composition is a
# DECISION: flow/ibex_sources.sh chooses hw/soc/rtl/ibex_regfile_secded.v
# over hw/soc/gen/ibex_register_file_ff.v at IBEX_REGFILE=secded, and
# hw/soc/genp/ibex_top.v over hw/soc/gen/ibex_top.v at
# IBEX_FAULT_PORT=1, and exactly one of each pair may be in the list.
# Duplicating that logic in JSON would create a second place that has
# to agree with flow/syn_soc_top.sh and that nothing compares -- which
# is the defect docs/44 section 5.4 and docs/45 section 4.1 both refuse
# one level up.
#
# So this script merges the list into a RESOLVED COPY of config.json in
# the run directory, and then ASSERTS that VERILOG_FILES is the only key
# it added or changed. docs/34 section 8.5's trap was a generator that
# silently deleted a hand-added fix from a config; the assertion is what
# stops this one from being able to. The resolved config is written
# beside config.json, because LibreLane resolves `dir::` and the run
# directory relative to the config file it is handed.

set -euo pipefail

RUN_TAG=${1:?usage: pnr_soc_top.sh <run-tag> [librelane args...]}
shift || true

SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
REPO=$(cd "$SOC_DIR/../.." && pwd -P)
PNR=$SOC_DIR/pnr
# LibreLane resolves `dir::` against the config file's own directory and
# puts its run directories in <that directory>/runs/<tag>, so the
# resolved config has to sit beside config.json for the pdk_dir:: and
# dir:: paths in it to mean what they say. hw/soc/pnr/runs/ and
# hw/soc/pnr/config.resolved.json are gitignored; nothing generated is
# ever committed, by the rule docs/38 section 11 already applies.
RUN_DIR=$PNR/runs

case "$PNR" in
  */hw/openlane/*) echo "refusing: config dir is inside the frozen hw/openlane/" >&2
                   exit 1 ;;
esac

SHIMS="${SHIMS:-$HOME/.local/opt/llbin}"
VENV="${VENV:-$HOME/Documents/caravel-lif-crossbar/.venv-flow}"
OSS_CAD="${OSS_CAD:-$HOME/Documents/gt2n-soc/tools/oss-cad-suite/bin}"
export PDK_ROOT="${PDK_ROOT:-$HOME/.ciel}"

PDK=ihp-sg13g2
SCL=sg13g2_stdcell

[ -x "$SHIMS/openroad" ]     || { echo "missing shims at $SHIMS" >&2; exit 1; }
[ -x "$VENV/bin/librelane" ] || { echo "missing librelane venv at $VENV" >&2; exit 1; }

export PATH="$SHIMS:$VENV/bin:$OSS_CAD:$PATH"
# Deliberate: the shims set LD_LIBRARY_PATH themselves, per tool. An
# inherited value here would apply the OpenROAD glibc to every process.
unset LD_LIBRARY_PATH

# ---- the PDK pin, read out of the tool rather than written down ------
PIN="$("$VENV/bin/python" - "$PDK" <<'PY'
import sys, importlib.util, os, re
spec = importlib.util.find_spec("librelane")
path = os.path.join(os.path.dirname(spec.origin), "pdk_hashes.yaml")
want = sys.argv[1]
for line in open(path):
    m = re.match(r"\s*([\w.-]+)\s*:\s*(\S+)", line)
    if m and m.group(1) == want:
        print(m.group(2)); break
PY
)"
[ -n "$PIN" ] || { echo "no $PDK pin in this LibreLane's pdk_hashes.yaml" >&2; exit 1; }

ENABLED=""
if TARGET="$(readlink -e "$PDK_ROOT/$PDK" 2>/dev/null)"; then
    ENABLED="$(basename "$(dirname "$TARGET")")"
fi
if [ "$ENABLED" != "$PIN" ]; then
  echo "PDK version mismatch."
  echo "  enabled: ${ENABLED:-<none>}"
  echo "  pinned:  $PIN"
  echo "Fix with: ciel enable --pdk-family $PDK $PIN"
  exit 1
fi

# ---- the source list, from the one place that knows it ---------------
IBEX_REGFILE=${IBEX_REGFILE:-secded}
IBEX_FAULT_PORT=${IBEX_FAULT_PORT:-1}
export IBEX_REGFILE IBEX_FAULT_PORT
# shellcheck source=hw/soc/flow/ibex_sources.sh
. "$SOC_DIR/flow/ibex_sources.sh"

RTL=$SOC_DIR/rtl
PILOT_RTL=$(cd "$SOC_DIR/../rtl" && pwd -P)

for f in "$RTL/soc_memmap.vh" "$RTL/soc_pnp_rom.vh" "$RTL/soc_apb_pnp_rom.vh"; do
  [ -f "$f" ] || { echo "missing $f: run 'python regmap/generate_memmap.py'" >&2
                   exit 1; }
done

SRCS=$(
  echo "$RTL/prim_clock_gating.v"
  ibex_sources "$SOC_DIR"
  for f in soc_bus soc_apb_bridge soc_uart soc_pnp soc_apb_pnp soc_clint \
           soc_gptimer soc_wdog soc_busstat soc_tmr_bank; do
    echo "$RTL/$f.v"
  done
  # READ from the pilot's directory and never modified, exactly as
  # flow/syn_soc_top.sh reads them.
  echo "$PILOT_RTL/tmr_voter.v"
  # THE REAL MEMORIES. soc_mem.v is deliberately absent: two files
  # declaring `soc_mem` would be a redeclaration, and the behavioural
  # one is 589,824 registers.
  echo "$RTL/soc_mem_sram.v"
  echo "$RTL/soc_top.v"
)

RESOLVED=$PNR/config.resolved.json
"$VENV/bin/python" - "$PNR/config.json" "$RESOLVED" <<PY
import json, sys
src, dst = sys.argv[1], sys.argv[2]
base = json.load(open(src))
srcs = """$SRCS""".split()
assert srcs, "empty source list"
assert "VERILOG_FILES" not in base, \
    "config.json must not carry VERILOG_FILES; this script supplies it"
out = dict(base)
out["VERILOG_FILES"] = srcs
# THE ASSERTION. The generator may add VERILOG_FILES and nothing else.
added  = set(out) - set(base)
changed = {k for k in base if base[k] != out[k]}
assert added == {"VERILOG_FILES"}, f"generator added {added}"
assert not changed, f"generator changed {changed}"
json.dump(out, open(dst, "w"), indent=4)
print(f"resolved config: {dst}  ({len(srcs)} verilog files)")
PY

# ---- the netlist this flow hardens ----------------------------------
#
# LibreLane's own synthesis is NOT used, and hw/soc/pnr/config.json's
# "//hierarchy" note carries the measurement behind that: both of its
# hierarchy modes are wrong for this design, in opposite directions, and
# neither is fixable from a configuration file. The initial state
# written below names hw/soc/flow/syn_soc_top.sh's netlist, which folds
# soc_top.v's constants into ibex_top AND releases soc_tmr_bank's
# keep_hierarchy after technology mapping. It holds an absolute path, so
# it is GENERATED here and gitignored rather than committed.
#
#   SOC_MEM=sram hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s47-sram
#   hw/soc/flow/pnr_soc_top.sh <tag> -F Yosys.JsonHeader \
#       -S Yosys.Synthesis -S Checker.YosysUnmappedCells \
#       -S Checker.YosysSynthChecks -S Checker.NetlistAssignStatements \
#       -i hw/soc/pnr/state/syn_soc_top.state.json
SYN_NETLIST=${SYN_NETLIST:-$SOC_DIR/out/s47-sram/soc_top.netlist.v}
if [ -f "$SYN_NETLIST" ]; then
  mkdir -p "$PNR/state"
  "$VENV/bin/python" -c "import json,os,sys; json.dump({'nl': os.path.abspath(sys.argv[1]), 'metrics': {}}, open(sys.argv[2],'w'), indent=1)" \
      "$SYN_NETLIST" "$PNR/state/syn_soc_top.state.json"
  echo "netlist:   $SYN_NETLIST"
else
  echo "netlist:   $SYN_NETLIST not found; run flow/syn_soc_top.sh first"
  echo "           (needed only for the -i form above)"
fi

echo "run tag:   $RUN_TAG"
echo "run dir:   $RUN_DIR/$RUN_TAG"
echo "sources:   $(echo "$SRCS" | wc -l) verilog files"
echo "pdk:       $PDK @ $PIN"
echo "librelane: $("$VENV/bin/librelane" --version 2>/dev/null | head -1)"

exec librelane --pdk "$PDK" --scl "$SCL" \
     --run-tag "$RUN_TAG" \
     ${@+"$@"} "$RESOLVED"
