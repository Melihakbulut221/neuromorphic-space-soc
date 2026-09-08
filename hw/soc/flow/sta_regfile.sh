#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

# Time the register file's READ PATH, on its own, at every corner.
#
#   sta_regfile.sh [dir_written_by_syn_regfile.sh]
#
# =====================================================================
# WHY THIS EXISTS, AND WHY THE WHOLE-CORE NUMBER COULD NOT ANSWER IT
# =====================================================================
#
# docs/43 section 7.4 priced the register-file protection in time by
# synthesising the whole of ibex_top twice and subtracting the reported
# worst setup slacks: +2.4337 ns became +1.7411 ns, and the difference
# was attributed to "the decoder on the register read path".
#
# docs/44 section 5.1 shows why that subtraction cannot carry the
# attribution:
#
#   1. Every one of the ten worst setup paths at the slow corner, in
#      BOTH configurations, starts at `cheriot_enable_i[0]` -- an input
#      port that soc_top.v drives with the constant 4'b1010. It is not a
#      path of the design; it is a path of the measurement. And a
#      register-file decoder cannot be on it in any case, because its
#      inputs come from flip-flops and a primary input cannot reach
#      them.
#   2. The whole-core figure is not stable to the size of the effect. A
#      source change that is provably OFF the read path -- adding an
#      output port the enclosing build does not connect -- moves the
#      reported slack by 0.44 ns and the area by 480 um2, because ABC
#      re-maps a 22,000-cell design differently when anything about it
#      changes. The instrument's noise is most of the signal.
#
# So the recovery is measured HERE, where the thing that changed is the
# whole design: `ibex_register_file_ff` alone, from the flip-flops to
# `rdata_a_o` and `rdata_b_o`, which IS the read path. Nothing else in
# this netlist can move.
#
# The whole-core numbers are still reported by docs/44 -- section 5.3
# gives them, with their noise beside them -- because what a design pays
# is what the design pays. This is the number that says WHY.
#
# =====================================================================
# THE RECIPE IS THE SAME ONE
# =====================================================================
#
# Constraints are hw/soc/sta/ibex.sdc.in, unaltered and unspecialised:
# the same 20 ns period, the same sg13g2_buf_4 driving cell, the same
# 6 fF load, the same 20 % IO delay, the same 0.25 ns uncertainty and
# the same 5.0 % derate that docs/28 section 4.4 argues for and that
# sta_ibex.sh applies to the core. All three corners are checked and all
# three are reported, for the reason sta_ibex.sh's header gives at
# length: a verdict is only as wide as the checks it aggregates.
#
# Every path in this netlist is either flop-to-output or input-to-flop,
# so the 20 % IO delay is a large part of every number and the SLACKS
# are not comparable to the core's. THE DIFFERENCES BETWEEN THE ROWS
# ARE, which is what this script is for, and the arrival time at
# rdata_a_o is printed beside the slack so a reader can see the raw
# quantity rather than only the derived one.

set -euo pipefail

SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT=${1:-$SOC_DIR/out/soc-syn/regfile}
PERIOD_NS=${SOC_PERIOD_NS:-20}

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${STA:?}" "${SG13G2_TYP:?}" "${SG13G2_SLOW:?}" "${SG13G2_FAST:?}"

[ -f "$OUT/harden1.sta.v" ] || {
  echo "no netlists in $OUT: run flow/syn_regfile.sh first" >&2; exit 1; }

sed -e "s|@PERIOD@|$PERIOD_NS|g" "$SOC_DIR/sta/ibex.sdc.in" > "$OUT/rf.sdc"

printf "  %-10s %-6s %-12s %-12s %s\n" \
       config corner "worst_setup" "worst_hold" "arrival rdata_a_o"

TAGS=${TAGS:-upstream harden0 scrub0 slowcorr harden1}

for tag in $TAGS; do
  [ -f "$OUT/$tag.sta.v" ] || continue
  for corner in typ slow fast; do
    case $corner in
      typ)  LIB=$SG13G2_TYP  ;;
      slow) LIB=$SG13G2_SLOW ;;
      fast) LIB=$SG13G2_FAST ;;
    esac
    cat > "$OUT/$tag.$corner.sta.tcl" <<EOF
read_liberty $LIB
read_verilog $OUT/$tag.sta.v
link_design ibex_register_file_ff
read_sdc $OUT/rf.sdc
puts [format "WORSTSETUP %s" [sta::format_time [sta::worst_slack_cmd max] 4]]
puts [format "WORSTHOLD %s"  [sta::format_time [sta::worst_slack_cmd min] 4]]
puts "---- the read path, worst first ----"
report_checks -path_delay max -to [get_ports rdata_a_o*] \
              -group_path_count 1 -format full_clock_expanded -digits 4
exit
EOF
    "$STA" -no_splash -exit "$OUT/$tag.$corner.sta.tcl" \
         > "$OUT/$tag.$corner.sta.log" 2>&1 || {
      echo "OpenSTA failed on $tag at $corner; see $OUT/$tag.$corner.sta.log" >&2
      exit 1; }
    awk -v tag="$tag" -v corner="$corner" '
      /^WORSTSETUP/ { su = $2 }
      /^WORSTHOLD/  { ho = $2 }
      /data arrival time/ && arr == "" { arr = $1 }
      END { printf "  %-10s %-6s %-12s %-12s %s\n", tag, corner, su, ho, arr }
    ' "$OUT/$tag.$corner.sta.log"
  done
done

echo "  full paths in $OUT/<config>.<corner>.sta.log"
