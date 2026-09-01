#!/usr/bin/env bash
# Multi-corner OpenSTA on a synthesised Ibex netlist.
#
#   sta_ibex.sh <config> <period_ns> [out_root]
#
# Reads <out_root>/<config>/ibex_top.sta.v, which flow/syn_ibex.sh wrote
# with -noexpr -nohex -nodec and splitnets, and reports setup and hold
# at ALL THREE sg13g2 corners with the pilot's 5% derate applied as a
# float (docs/28 section 4.4).
#
# ---------------------------------------------------------------------
# THE VERDICT RULE. An earlier version of this script printed
#
#   RESULT small-pmp period=20 ns worst_setup=2.4337 (slow)
#          worst_hold=-0.0766 (fast) SETUP_MET_ALL_CORNERS
#
# -- a token that reads as a pass, on the same line as a negative
# number, because the token had been computed from the setup numbers
# only. That is this repository's recurring defect, now seen a fifth
# time: docs/28 section 4.4a (setup checker resolved to ["*typ*"]),
# docs/23 (design__violations not aggregating hold), docs/34 section 8.5
# and docs/36 section 3.3 (max-cap and max-slew checkers bound to no
# corner at all). Every instance is the same shape -- a green result
# only as wide as the thing it examined -- and the fix is always to
# widen the verdict, never to narrow the evidence.
#
# So: every check that is reported is also judged, and the verdict names
# its own scope. There is no bare pass token. The last line is either
#
#   VERDICT <cfg> period=<p> ALL_CHECKS_MET (setup+hold, 3 corners)
# or
#   VERDICT <cfg> period=<p> NOT_MET: <list of the checks that failed>
#
# and any caller that wants to gate on a subset has to say which subset
# it is gating on, in the gate, where a reader can see it.
# ---------------------------------------------------------------------

set -euo pipefail

CFG=${1:?config name}
PERIOD=${2:?period in ns}
SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT_ROOT=${3:-$SOC_DIR/out}
OUT=$OUT_ROOT/$CFG

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${STA:?}" "${SG13G2_TYP:?}" "${SG13G2_SLOW:?}" "${SG13G2_FAST:?}"

sed -e "s|@PERIOD@|$PERIOD|g" "$SOC_DIR/sta/ibex.sdc.in" > "$OUT/ibex.sdc"

CORNERS="typ slow fast"

# SOC_TIEOFFS=1 applies sta/ibex_tieoffs.sdc, which case-analyses the
# `cheriot_enable_i` constant soc_top.v drives. Default off, so docs/38's
# and docs/43's numbers reproduce unchanged; docs/44 section 5.1 says
# what turning it on is for and what it does not cover.
if [ "${SOC_TIEOFFS:-0}" = 1 ]; then
  TIEOFFS="source $SOC_DIR/sta/ibex_tieoffs.sdc"
else
  TIEOFFS="# SOC_TIEOFFS=0: ibex_top timed with every input free"
fi

: > "$OUT/sta.log"
for corner in $CORNERS; do
  case $corner in
    typ)  LIB=$SG13G2_TYP  ;;
    slow) LIB=$SG13G2_SLOW ;;
    fast) LIB=$SG13G2_FAST ;;
  esac
  sed -e "s|@TIEOFFS@|$TIEOFFS|g" \
      -e "s|@LIB@|$LIB|g" \
      -e "s|@CORNER@|$corner|g" \
      -e "s|@NETLIST@|$OUT/ibex_top.sta.v|g" \
      -e "s|@SDC@|$OUT/ibex.sdc|g" \
      -e "s|@OUT@|$OUT|g" \
      "$SOC_DIR/sta/ibex_sta.tcl.in" > "$OUT/ibex_sta_$corner.tcl"
  "$STA" -no_splash -exit "$OUT/ibex_sta_$corner.tcl" >> "$OUT/sta.log" 2>&1 || {
    echo "OpenSTA failed at corner $corner; see $OUT/sta.log" >&2
    tail -30 "$OUT/sta.log" >&2
    exit 1
  }
done

# Pull the per-path-group diagnostic slacks out of the report files.
# "No paths found" for a group yields an empty field, printed as "-",
# never as a zero or a pass.
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

# Aggregate. Setup AND hold must be met at EVERY corner for the verdict
# to be ALL_CHECKS_MET; the per-group numbers are echoed for diagnosis
# but the verdict is formed from the all-group numbers, so no group can
# fail behind a green line.
awk -v cfg="$CFG" -v per="$PERIOD" -v corners="$CORNERS" '
  FNR==NR {
    if ($1=="GROUP") g[$2 " " $3] = $4
    next
  }
  /^WORSTSLACK setup/ { su[$3]=$NF; if (ns=="" || $NF+0 < ns+0) { ns=$NF; nc=$3 } }
  /^WORSTSLACK hold/  { ho[$3]=$NF; if (nh=="" || $NF+0 < nh+0) { nh=$NF; hc=$3 } }
  END {
    n = split(corners, cs, " ")
    printf "  %-5s  %-10s %-10s | %-10s %-10s\n", \
           "corner", "setup", "hold", "setup_sync", "setup_async"
    for (i=1; i<=n; i++) {
      c = cs[i]
      printf "  %-5s  %-10s %-10s | %-10s %-10s\n", c, su[c], ho[c], \
             g["setup_sync " c], g["setup_async " c]
    }
    # Worst-across-corners per check, for callers that gate on a named
    # subset. A caller that reads GATE setup_sync is on record as having
    # gated on setup_sync and nothing else.
    ss = ""; sc = ""
    for (i=1; i<=n; i++) {
      c = cs[i]; v = g["setup_sync " c]
      if (v != "-" && (ss == "" || v+0 < ss+0)) { ss = v; sc = c }
    }
    printf "GATE setup_all  %s %s\n", ns, nc
    printf "GATE setup_sync %s %s\n", ss, sc
    printf "GATE hold       %s %s\n", nh, hc

    fails = ""
    if (ns+0 < 0) fails = fails sprintf("setup(%s,%s) ", ns, nc)
    if (nh+0 < 0) fails = fails sprintf("hold(%s,%s) ", nh, hc)
    printf "  worst setup %s at %s, worst hold %s at %s\n", ns, nc, nh, hc
    if (fails == "")
      printf "VERDICT %s period=%s ns ALL_CHECKS_MET (setup+hold, %d corners)\n", \
             cfg, per, n
    else
      printf "VERDICT %s period=%s ns NOT_MET: %s\n", cfg, per, fails
  }' "$OUT/groups.rpt" "$OUT/sta.log" | tee "$OUT/slack.rpt"
