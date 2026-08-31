#!/usr/bin/env bash
# Find the fastest clock a configuration closes SETUP at, at every
# sg13g2 corner, with the pilot's 5% derate.
#
#   sweep_ibex.sh <config> [lo_ns] [hi_ns] [steps] [gate]
#
#   gate = setup_all   (default) setup over every path group
#          setup_sync            setup over the clk_i path group only
#
# Method: bisection on the clock period. Each probe RE-SYNTHESISES at
# that period -- ABC is given the same number the SDC then checks -- so
# what is measured is "the design closes at P", not "a netlist optimised
# for 20 ns happens to have positive slack at P". Those are different
# claims and only the first is a frequency.
#
# ---------------------------------------------------------------------
# WHAT THIS GATE DOES NOT COVER, STATED HERE AND ON EVERY LINE IT PRINTS.
#
# HOLD IS NOT IN THE GATE. On a synthesis netlist there is no placement,
# no routing, no clock tree and no hold-fixing buffer, and the SDC
# charges 0.25 ns of clock uncertainty against the hold check as a
# stand-in for skew that has not been built yet. Hold therefore fails at
# the fast corner at every period, by an amount that does not vary with
# the period, and gating on it would return "closes nowhere" for every
# configuration -- a statement about the stage, not about the design.
# The pilot closes hold in place-and-route (PL_RESIZER_HOLD_SLACK_MARGIN
# 0.1, GRT_RESIZER_HOLD_SLACK_MARGIN 0.05 in
# hw/openlane/pilot_ihp/config.signoff-6x2.json), which is where it is
# closable. So hold is carried as an obligation on the next stage, and
# every line below prints it rather than dropping it.
#
# This is a deliberate narrowing, so it is named: the summary line says
# "closes SETUP", never "closes". docs/28 section 4.4a is what an
# unnamed narrowing costs.
# ---------------------------------------------------------------------

set -euo pipefail

CFG=${1:?config name}
LO=${2:-3}
HI=${3:-20}
STEPS=${4:-7}
GATE=${5:-setup_all}
case "$GATE" in setup_all|setup_sync) ;; *) echo "bad gate: $GATE" >&2; exit 2;; esac

SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SWEEP_ROOT=$SOC_DIR/out/sweep-$CFG-$GATE
mkdir -p "$SWEEP_ROOT"
SUMMARY=$SWEEP_ROOT/sweep.txt
: > "$SUMMARY"

# echoes: "<gate_slack> <gate_corner> <hold_slack> <hold_corner>"
probe () {
  local p=$1
  "$SOC_DIR/flow/syn_ibex.sh" "$CFG" "$p" "$SWEEP_ROOT/p$p" \
      > "$SWEEP_ROOT/syn_$p.log" 2>&1
  "$SOC_DIR/flow/sta_ibex.sh" "$CFG" "$p" "$SWEEP_ROOT/p$p" \
      > "$SWEEP_ROOT/sta_$p.log" 2>&1
  awk -v gate="$GATE" '
    $1=="GATE" && $2==gate     { gs=$3; gc=$4 }
    $1=="GATE" && $2=="hold"   { hs=$3; hc=$4 }
    END { print gs, gc, hs, hc }' "$SWEEP_ROOT/sta_$p.log"
}

report () {  # $1=period $2..=probe fields
  local p=$1 gs=$2 gc=$3 hs=$4 hc=$5 verdict
  if [ "$(python3 -c "print(1 if $gs>=0 else 0)")" = 1 ]; then
    verdict=MET; else verdict=VIOLATED; fi
  printf "  period=%-6s %s=%-9s (%-4s) %s   [hold=%s (%s), NOT in gate]\n" \
         "$p" "$GATE" "$gs" "$gc" "$verdict" "$hs" "$hc" | tee -a "$SUMMARY"
  [ "$verdict" = MET ]
}

echo "== sweeping $CFG on gate '$GATE', bisection over [$LO, $HI] ns, $STEPS steps"
echo "== hold is reported but NOT gated: it is a place-and-route obligation"

best=""
read -r gs gc hs hc <<< "$(probe "$HI")"
if report "$HI" "$gs" "$gc" "$hs" "$hc"; then best=$HI; else
  echo "FATAL: $CFG does not meet $GATE even at $HI ns" >&2; exit 1
fi
hold_note="$hs at $hc"

lo=$LO; hi=$HI
for ((i=0; i<STEPS; i++)); do
  mid=$(python3 -c "print(f'{($lo+$hi)/2:.2f}')")
  read -r gs gc hs hc <<< "$(probe "$mid")"
  if report "$mid" "$gs" "$gc" "$hs" "$hc"; then best=$mid; hi=$mid
  else lo=$mid; fi
done

freq=$(python3 -c "print(f'{1000/$best:.1f}')")
line="BEST $CFG gate=$GATE period=$best ns freq=$freq MHz \
SETUP-ONLY; hold NOT met pre-P&R ($hold_note)"
echo "$line" | tee -a "$SUMMARY"
