#!/usr/bin/env bash
# Census the NPU connection's flip-flops, and say which of them the
# campaign's site list reaches.
#
#   fi_npu_coverage.sh [out_dir]
#
# WHY THIS EXISTS.  `hw/soc/fi/npu_targets.py` is a list a person wrote,
# and a list a person wrote is a list a person can leave something off.
# The campaign's own honesty checks cannot catch that class: control 1
# verifies that every site it NAMES elaborates, which is the opposite
# question from whether every flip-flop that elaborates is NAMED.
#
# docs/42 section 4.2 records what asking the second question found on
# the core: three whole structures missing, 128 flip-flops of debug CSRs
# among them, and a naming difference between two tools.  None of it was
# reachable from inside the campaign.  hw/soc/flow/fi_coverage.sh is this
# file's sibling and this one follows it exactly.
#
# TWO CENSUSES, BECAUSE THERE ARE TWO DESIGNS IN THE DUT.
#
#   the connection  soc_npu with `pilot_top` BLACK-BOXED, which is the
#                   same scope docs/51 section 11 measured at 717
#                   flip-flops.  This is the coverage figure.
#   the frozen die  pilot_top alone, at soc_npu.v's parameters.  This is
#                   NOT a coverage figure and hw/soc/fi/npu_coverage.py
#                   says so where it prints it: `die_ser` is one stratum
#                   over the die's serial front end, and docs/16 is the
#                   campaign that measured the whole block.
#
# It is a census of the RTL, not of the netlist.  Synthesis may merge,
# duplicate or delete flip-flops after this point, and the script reports
# the sites this campaign injects into that `opt_clean` removes -- which
# is one concrete way an RTL campaign and a gate-level campaign would
# differ here.  docs/32 is what closing that gap looked like for the die.

set -euo pipefail

SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PILOT_RTL=$(cd "$SOC_DIR/../rtl" && pwd)
RTL=$SOC_DIR/rtl
OUT=${1:-$SOC_DIR/out/fi-npu}

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${YOSYS:?}" "${SG13G2_TYP:?}"

mkdir -p "$OUT"

# soc_tmr_bank.v joins this list with docs/55: the connection's control
# and cause registers are now three replicas of that bank under
# hw/rtl/tmr_voter.v, which was already read here.
SRC="$RTL/soc_npu.v $RTL/soc_npu_ser.v $RTL/soc_tmr_bank.v \
     $PILOT_RTL/aer_fifo.v \
     $PILOT_RTL/pilot_top.v $PILOT_RTL/lif_core.v $PILOT_RTL/scrub.v \
     $PILOT_RTL/secded_enc.v $PILOT_RTL/secded_dec.v \
     $PILOT_RTL/tmr_voter.v"

# `attrmap -modattr -remove keep_hierarchy` before `flatten` is load
# bearing and not tidy: aer_fifo.v carries the attribute on its pointer
# banks, its parity bank and its rd_valid rails as one of its two
# anti-merge defences, so without this line `flatten` skips all of them
# and the census misses 58 flip-flops per queue while reporting a clean
# total.  hw/soc/flow/syn_soc.sh's own comment records the same trap
# costing the hardened watchdog a wrong area number.
#
# `memory_map` is here for the same reason at a different scale: without
# it aer_fifo's `mem` stays a $mem cell and the 256 bits of queue storage
# -- which is the largest single structure in this campaign -- would be
# reported as covered by nothing because they would not be flip-flops.
mkcensus () {
  local top=$1 bb=$2 out=$3
  {
    echo "read_liberty -lib $SG13G2_TYP"
    echo "read_verilog -I$RTL -I$PILOT_RTL $SRC"
    [ -n "$bb" ] && echo "blackbox $bb"
    echo "hierarchy -check -top $top"
    echo "proc"
    echo "memory_map"
    echo "attrmap -modattr -remove keep_hierarchy"
    echo "flatten"
    echo "opt_expr"
    echo "opt_dff"
    echo "opt_clean"
    echo "select -set flops t:\$adff t:\$adffe t:\$dff t:\$dffe t:\$sdff t:\$sdffe t:\$dffsr"
    echo "dump -o $out @flops"
    echo "stat"
  } > "$OUT/$top.census.ys"
  "$YOSYS" -q -s "$OUT/$top.census.ys" > "$OUT/$top.census.log" 2>&1 || {
    echo "yosys failed; see $OUT/$top.census.log" >&2; exit 1; }
}

# THE BLACK-BOX IS ASSERTED, NOT ASSUMED.  `blackbox` on a module the
# reader has already elaborated is a no-op that warns and exits zero, and
# docs/49 section 8.1 is four pages on a flow step that "elaborates,
# exits zero and changes nothing".  If pilot_top's own registers appear
# in the connection census, the black-box did not take and every number
# below would be about a different design.
mkcensus soc_npu pilot_top "$OUT/npu_flops.il"
if grep -qa 'connect \\Q \\u_node0\.' "$OUT/npu_flops.il"; then
  echo "== the pilot_top black-box did not take: the connection census" >&2
  echo "   contains the die's own flip-flops" >&2
  exit 1
fi
echo "== the connection census black-boxed the frozen pilot"

mkcensus pilot_top "" "$OUT/die_flops.il"

python3 "$SOC_DIR/fi/npu_coverage.py" \
    "$OUT/npu_flops.il" "$OUT/die_flops.il" \
  | tee "$OUT/fi_npu_coverage.txt"
