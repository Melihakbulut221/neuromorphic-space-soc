#!/usr/bin/env bash
# Multi-corner OpenSTA on the WHOLE-DESIGN soc_top netlist.
#
#   sta_soc_top.sh <period_ns> [out_dir]
#
# Reads <out_dir>/soc_top.sta.v, which flow/syn_soc_top.sh wrote with
# -noexpr -nohex -nodec and splitnets, and reports setup and hold at all
# three sg13g2 corners with the pilot's 5 % derate applied as a float.
#
# THREE THINGS ARE SHARED WITH flow/sta_ibex.sh ON PURPOSE, because a
# whole-design number measured under a different constraint set could
# not be compared with the per-block numbers docs/38, docs/43 and
# docs/44 quote:
#
#   sta/ibex.sdc.in        the constraint set. Its name says `ibex` and
#                          its content is LibreLane's base.sdc with the
#                          ihp-sg13g2 defaults substituted in: a clock on
#                          clk_i, 20 % IO delay on every other port, a
#                          sg13g2_buf_4 driver, 6 fF of load, 0.25 ns of
#                          uncertainty, 0.15 ns of transition, ideal
#                          clocks and a 5 % derate written as a float.
#                          Nothing in it names an Ibex port. It is used
#                          here unedited.
#   sta/ibex_sta.tcl.in    the per-corner script, with @TOP@ = soc_top.
#   flow/sta_verdict.awk   the verdict rule, which is therefore one rule
#                          and not two copies of one.
#
# NO TIE-OFF FILE, and that is the point of the exercise rather than an
# omission. sta/ibex_tieoffs.sdc exists because flow/sta_ibex.sh times
# `ibex_top` standalone, where `cheriot_enable_i` is a free primary input
# that soc_top.v in fact drives with a constant -- docs/44 section 5.1.
# At this level that input is not a port at all; the constant is inside
# the design and the synthesiser has already propagated it. There is
# nothing left to case-analyse.
#
# WHAT THIS FLOW CANNOT SEE, stated here and not only in the document:
# the netlist it reads has the memory macro stand-in of
# flow/syn_soc_top.sh at the two memory boundaries, so every path into or
# out of a memory is bounded by a standard-cell flip-flop and not by an
# SRAM macro's setup and clock-to-Q. And, as everywhere else under
# hw/soc/, there is no placement, no routing, no clock tree and no
# resizer.

set -euo pipefail

PERIOD=${1:?period in ns}
SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT=${2:-$SOC_DIR/out/soc-top}

[ -s "$OUT/soc_top.sta.v" ] || {
  echo "missing $OUT/soc_top.sta.v: run flow/syn_soc_top.sh first" >&2
  exit 1; }

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${STA:?}" "${SG13G2_TYP:?}" "${SG13G2_SLOW:?}" "${SG13G2_FAST:?}"

# SOC_MEM=sram: the netlist carries six RM_IHPSG13 instances and OpenSTA
# needs their Liberty or link_design fails with an unresolved reference.
# It is per corner, and the FAST one is a cross-corner map -- the macros
# ship fast_1p32V_m55C where the standard cells ship fast_1p32V_m40C, so
# the macro is characterised 15 C colder than the cells around it.
# docs/12 section 6.4a; the same map hw/openlane/sram_pilot makes.
#
# Default off, so a stub or blackbox netlist is timed exactly as docs/45
# timed it and its numbers reproduce.
SOC_MEM=${SOC_MEM:-stub}

sed -e "s|@PERIOD@|$PERIOD|g" "$SOC_DIR/sta/ibex.sdc.in" > "$OUT/soc_top.sdc"

CORNERS="typ slow fast"

# SOC_RESET_CUT=1 applies sta/soc_top_reset_cut.sdc, which false-paths
# the two reset nets so the rest of the design can be timed. Default off,
# so the reported number is the whole design as synthesised; docs/45
# section 6 quotes both and says what each one is about.
if [ "${SOC_RESET_CUT:-0}" = 1 ]; then
  RESET_CUT="source $SOC_DIR/sta/soc_top_reset_cut.sdc"
else
  RESET_CUT="# SOC_RESET_CUT=0: the reset nets are timed with the design"
fi

: > "$OUT/sta.log"
for corner in $CORNERS; do
  case $corner in
    typ)  LIB=$SG13G2_TYP  ;;
    slow) LIB=$SG13G2_SLOW ;;
    fast) LIB=$SG13G2_FAST ;;
  esac
  if [ "$SOC_MEM" = sram ]; then
    case $corner in
      typ)  MLIBS=$SRAM_TYP  ;;
      slow) MLIBS=$SRAM_SLOW ;;
      fast) MLIBS=$SRAM_FAST ;;
    esac
    for l in $MLIBS; do
      [ -f "$l" ] || { echo "missing macro liberty $l" >&2; exit 1; }
    done
    # One line, because the sed substitution that places it is one line.
    MACROLIB="foreach macro_lib { $MLIBS } { read_liberty \$macro_lib }"
  else
    MACROLIB="# SOC_MEM=$SOC_MEM: no macro in this netlist"
  fi
  sed -e "s|@TOP@|soc_top|g" \
      -e "s|@TIEOFFS@|$RESET_CUT|g" \
      -e "s|@MACROLIB@|$MACROLIB|g" \
      -e "s|@LIB@|$LIB|g" \
      -e "s|@CORNER@|$corner|g" \
      -e "s|@NETLIST@|$OUT/soc_top.sta.v|g" \
      -e "s|@SDC@|$OUT/soc_top.sdc|g" \
      -e "s|@OUT@|$OUT|g" \
      "$SOC_DIR/sta/ibex_sta.tcl.in" > "$OUT/soc_top_sta_$corner.tcl"
  "$STA" -no_splash -exit "$OUT/soc_top_sta_$corner.tcl" >> "$OUT/sta.log" 2>&1 || {
    echo "OpenSTA failed at corner $corner; see $OUT/sta.log" >&2
    tail -30 "$OUT/sta.log" >&2
    exit 1
  }
done

group_slack () {  # $1 = report file
  if [ ! -s "$1" ]; then echo "-"; return; fi
  awk '/slack \((MET|VIOLATED)\)/ { v=$1 } END { print (v=="" ? "-" : v) }' "$1"
}

{
  for corner in $CORNERS; do
    printf "GROUP setup_sync  %-5s %s\n" "$corner" \
           "$(group_slack "$OUT/path_${corner}_setup_sync.rpt")"
    printf "GROUP setup_async %-5s %s\n" "$corner" \
           "$(group_slack "$OUT/path_${corner}_setup_async.rpt")"
  done
} > "$OUT/groups.rpt"

awk -v cfg=soc_top -v per="$PERIOD" -v corners="$CORNERS" \
    -f "$SOC_DIR/flow/sta_verdict.awk" \
    "$OUT/groups.rpt" "$OUT/sta.log" | tee "$OUT/slack.rpt"
