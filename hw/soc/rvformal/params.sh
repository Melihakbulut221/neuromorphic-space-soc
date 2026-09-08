#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

# Guard: hw/soc/rvformal/checks.cfg.in copies soc_top.v's ibex_top
# parameter list, and a copy that drifts is a proof about a core the SoC
# does not build.
#
# This is the same guard hw/soc/formal/Makefile's `wdog_tmr_params`
# target applies to soc_wdog_tmr.sby's copy of the TMR masks, and
# formal/tmr_voter_cfg.mk applies to the pilot's configuration domain.
# It runs FIRST, before anything is generated, so a moved parameter is
# an error at setup and not nineteen green checks about the wrong core.
#
# WHY THE PARAMETERS ARE COPIED AT ALL, and why into a .cfg file rather
# than into the wrapper where a reader would look for them. riscv-formal
# instantiates `rvfi_wrapper` with a fixed port list, so no parameter can
# be passed in from outside; and the core is elaborated by yosys-slang,
# which leaves `ibex_top` non-parametric, so an override at the
# instantiation is an error rather than an override. `read_slang -G` in
# checks.cfg.in is the only route. sv2v does not preserve ibex_pkg's
# enum NAMES either (docs/38 section 4.4), so the values are bare
# integers on both sides and a wrong one is a silently different core.
# Reading them back out of soc_top.v is the only thing that makes the
# copy checkable.
#
# Usage: params.sh <hw/soc dir>

set -euo pipefail

SOC_DIR=$(cd "${1:?hw/soc dir}" && pwd)
TOP="$SOC_DIR/rtl/soc_top.v"
WRAP="$SOC_DIR/rvformal/checks.cfg.in"

test -f "$TOP"  || { echo "no such file: $TOP"  >&2; exit 2; }
test -f "$WRAP" || { echo "no such file: $WRAP" >&2; exit 2; }

# Every parameter ibex_top declares, so a parameter ADDED upstream and
# set in soc_top.v but forgotten here is caught as well as a value that
# moved. The list is checked for completeness against soc_top.v below.
PARAMS="BaseIsa PMPEnable PMPGranularity PMPNumRegions MHPMCounterNum \
MHPMCounterWidth RV32E RV32M RV32B RV32ZC RegFile BranchTargetALU \
WritebackStage ICache ICacheECC BranchPredictor DbgTriggerEn SecureIbex \
ICacheScramble"

# soc_top.v: the instantiation block only -- `ibex_top #(` up to the
# closing `)` of the parameter list. Reading the whole file would match
# a parameter name in a comment.
extract_rtl () {
  awk '/ibex_top *#\(/ {inblk=1} inblk {print} inblk && /^[[:space:]]*\) *u_ibex/ {exit}' "$1" |
  sed -e 's://.*::' |
  grep -oE '\.[A-Za-z0-9_]+ *\( *[0-9]+ *\)' |
  sed -e 's/[ ().]//g' -e 's/\([A-Za-z0-9_]*[A-Za-z]\)\([0-9]*\)$/\1 \2/' |
  awk '{print $1, $2}' | sort
}

# checks.cfg.in: the `-G NAME=VALUE` tokens on the read_slang line only.
# Anchored on that command so a -G written in a comment is not counted;
# riscv-formal's config reader drops comment lines, but this guard reads
# the template and not what the reader kept.
extract_cfg () {
  grep -E '^read_slang ' "$1" |
  grep -oE ' -G [A-Za-z0-9_]+=[0-9]+' |
  sed -e 's/ -G //' -e 's/=/ /' | sort
}

TOP_VALS=$(extract_rtl "$TOP")
WRAP_VALS=$(extract_cfg "$WRAP")

fail=0

for p in $PARAMS; do
  t=$(echo "$TOP_VALS"  | awk -v k="$p" '$1==k {print $2}')
  w=$(echo "$WRAP_VALS" | awk -v k="$p" '$1==k {print $2}')
  if [ -z "$t" ]; then
    echo "params.sh: $p is not set in $TOP -- the list in this script is stale" >&2
    fail=1
  elif [ -z "$w" ]; then
    echo "params.sh: $p has no -G in $WRAP but IS set in soc_top.v" >&2
    fail=1
  elif [ "$t" != "$w" ]; then
    echo "params.sh: $p differs -- soc_top.v has $t, checks.cfg.in has $w" >&2
    fail=1
  fi
done

# And the other direction: a parameter set in one file and not named in
# PARAMS above would otherwise be invisible to the loop.
for side in TOP WRAP; do
  eval "vals=\$${side}_VALS"
  n_listed=$(echo "$vals" | awk 'NF' | wc -l)
  n_expect=$(echo "$PARAMS" | wc -w)
  if [ "$n_listed" -ne "$n_expect" ]; then
    echo "params.sh: $side sets $n_listed parameters, this script knows $n_expect" >&2
    echo "$vals" >&2
    fail=1
  fi
done

test $fail -eq 0 || exit 1
echo "== rvformal parameter guard: checks.cfg.in still elaborates the core soc_top.v instantiates ($(echo "$PARAMS" | wc -w) parameters)"
