#!/usr/bin/env bash
# Elaborate and run the sv2v-converted Ibex in Icarus Verilog.
#
#   sim_ibex.sh <config> [out_dir]
#
# config: small | small-pmp | small-pmp-sec  (same names as the
# synthesis flow, and the same parameter values -- the point is that the
# thing simulated and the thing measured are one thing).
#
# The RTL read here is hw/soc/gen/*.v, i.e. the sv2v output, NOT the
# SystemVerilog. That is the whole point of the exercise: Icarus is a
# Verilog-2005 simulator and this project's simulation flow is Icarus,
# so if sv2v's output does not elaborate and run here then the docs/03
# recommendation does not reach this project's flow.

set -euo pipefail

CFG=${1:?config name}
SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT=${2:-$SOC_DIR/out/sim-$CFG}

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${IVERILOG:?}" "${VVP:?}"

case "$CFG" in
  small)         PMP=0; SEC=0 ;;
  small-pmp)     PMP=1; SEC=0 ;;
  small-pmp-sec) PMP=1; SEC=1 ;;
  *) echo "unknown config: $CFG" >&2; exit 2 ;;
esac

mkdir -p "$OUT"

SWDEF=()
[ "$PMP" = 1 ] && SWDEF+=(-DHAVE_PMP)
"$SOC_DIR/flow/build_sw.sh" "$OUT" "${SWDEF[@]}"

# Hand the testbench the addresses of the trap handler's bookkeeping
# words, read out of the ELF that was just built rather than written
# down here, so a failing run can print mcause/mepc/trap_count without
# either file carrying a constant that can go stale.
NM=$SOC_DIR/tools/rvgcc/bin/riscv-none-elf-nm
sym () {
  local a
  a=$("$NM" "$OUT/test_ibex.elf" | awk -v s="$1" '$3 == s { print $1 }')
  [ -n "$a" ] || { echo "symbol not found: $1" >&2; exit 1; }
  echo "32'h$a"
}

# SG13G2_ICG_BEHAVIOURAL: rtl/prim_clock_gating.v binds the real
# sg13g2_lgcp_1 cell for synthesis. Icarus has no such cell unless the
# PDK simulation library is also read, and reading it here would put PDK
# models into a pure-RTL run. The behavioural branch is selected instead
# and the substitution is recorded in the log so no reader has to guess
# which clock gate ran.
"$IVERILOG" -g2005-sv -o "$OUT/tb_ibex_min.vvp" \
  -DSG13G2_ICG_BEHAVIOURAL \
  -DIBEX_PMPENABLE="$PMP" \
  -DIBEX_SECUREIBEX="$SEC" \
  -DPROG_HEX="\"$OUT/test_ibex.hex\"" \
  -DTRAP_MCAUSE_ADDR="$(sym trap_mcause)" \
  -DTRAP_MEPC_ADDR="$(sym trap_mepc)" \
  -DTRAP_COUNT_ADDR="$(sym trap_count)" \
  -s tb_ibex_min \
  "$SOC_DIR/tb/tb_ibex_min.v" \
  "$SOC_DIR/tb/ibex_min_system.v" \
  "$SOC_DIR/rtl/prim_clock_gating.v" \
  "$SOC_DIR"/gen/*.v \
  2>&1 | tee "$OUT/iverilog.log"

echo "== elaborated; running"
"$VVP" "$OUT/tb_ibex_min.vvp" 2>&1 | tee "$OUT/sim.log"

grep -q "^\[TB\] PASS" "$OUT/sim.log" || {
  echo "== SIMULATION FAILED for $CFG" >&2; exit 1; }
echo "== $CFG: PASS"
