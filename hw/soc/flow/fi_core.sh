#!/usr/bin/env bash
# Build everything the core fault-injection campaign of docs/42 needs,
# and elaborate it ONCE.
#
#   fi_core.sh [out_dir]
#
# The campaign runs hundreds of simulations of the same design with
# different plusargs, so elaboration is hoisted out of the loop: this
# script produces one `tb_soc_fi.vvp` and `hw/soc/fi/campaign.py` invokes
# `vvp` on it with +site, +bit, +cycle, +armed and +budget.  That is the
# whole reason the injection site is a runtime argument and a case
# statement rather than a compile-time define -- an elaboration per
# injection would cost more than the simulations do.
#
# Sources are exactly sim_soc.sh's: this project's hw/soc/rtl/soc_*.v,
# the sv2v-converted Ibex in hw/soc/gen/, hw/rtl/tmr_voter.v read and
# never modified, and a testbench.  The only differences are the
# testbench itself and the workload.

set -euo pipefail

SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PILOT_RTL=$(cd "$SOC_DIR/../rtl" && pwd)
OUT=${1:-$SOC_DIR/out/fi-core}

UART_SCALER=${UART_SCALER:-0}
UART_BIT_CYCLES=$(( 8 * (UART_SCALER + 1) ))

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${IVERILOG:?}" "${VVP:?}"

[ -d "$SOC_DIR/gen" ] || {
  echo "hw/soc/gen is empty: run flow/sv2v_ibex.sh first" >&2; exit 1; }

mkdir -p "$OUT"

SW_DEFINES=${SW_DEFINES:-}
# shellcheck disable=SC2086
"$SOC_DIR/flow/build_sw_fi.sh" "$OUT" "-DUART_SCALER_VAL=${UART_SCALER}u" $SW_DEFINES

# The site table.  Generated into the OUTPUT directory, not into the
# source tree: it is derived from hw/soc/fi/targets.py the way
# hw/soc/gen is derived from ext/ibex, and the repository's rule for
# both is fetched-or-generated, never vendored.
python3 "$SOC_DIR/fi/targets.py" "$OUT/fi_targets.vh" > "$OUT/fi_targets.txt"

NM=$SOC_DIR/tools/rvgcc/bin/riscv-none-elf-nm
sym () {
  local a
  a=$("$NM" "$OUT/fi_workload.elf" | awk -v s="$1" '$3 == s { print $1 }')
  [ -n "$a" ] || { echo "symbol not found: $1" >&2; exit 1; }
  echo "32'h$a"
}

"$IVERILOG" -g2005-sv -o "$OUT/tb_soc_fi.vvp" \
  -I "$SOC_DIR/rtl" \
  -I "$OUT" \
  -DSG13G2_ICG_BEHAVIOURAL \
  -DROM_HEX="\"$OUT/fi_workload.hex\"" \
  -DUART_BIT_CYCLES="$UART_BIT_CYCLES" \
  -DEXIT_CODE_ADDR="$(sym exit_code)" \
  -DEXIT_MAGIC_ADDR="$(sym exit_magic)" \
  -DTRAP_MCAUSE_ADDR="$(sym trap_mcause)" \
  -DTRAP_COUNT_ADDR="$(sym trap_count)" \
  -DNMI_COUNT_ADDR="$(sym nmi_count)" \
  -DFI_PHASE_ADDR="$(sym fi_phase)" \
  -DFI_SIG_ADDR="$(sym fi_sig)" \
  -DFI_MASK_ADDR="$(sym fi_mask)" \
  -DFI_ROUNDS_ADDR="$(sym fi_rounds_done)" \
  -s tb_soc_fi \
  "$SOC_DIR/tb/tb_soc_fi.v" \
  "$SOC_DIR/rtl/soc_top.v" \
  "$SOC_DIR/rtl/soc_bus.v" \
  "$SOC_DIR/rtl/soc_apb_bridge.v" \
  "$SOC_DIR/rtl/soc_mem.v" \
  "$SOC_DIR/rtl/soc_pnp.v" \
  "$SOC_DIR/rtl/soc_apb_pnp.v" \
  "$SOC_DIR/rtl/soc_uart.v" \
  "$SOC_DIR/rtl/soc_clint.v" \
  "$SOC_DIR/rtl/soc_gptimer.v" \
  "$SOC_DIR/rtl/soc_wdog.v" \
  "$SOC_DIR/rtl/soc_tmr_bank.v" \
  "$PILOT_RTL/tmr_voter.v" \
  "$SOC_DIR/rtl/prim_clock_gating.v" \
  "$SOC_DIR"/gen/*.v \
  2>&1 | tee "$OUT/iverilog.log"

echo "== elaborated $OUT/tb_soc_fi.vvp"
