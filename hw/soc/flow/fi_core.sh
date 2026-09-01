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

# The Ibex source list, with the register file selected. IBEX_REGFILE
# defaults to `secded`: hw/soc/rtl/ibex_regfile_secded.v replaces
# hw/soc/gen/ibex_register_file_ff.v, and nothing in hw/soc/ext or
# hw/soc/gen is modified to do it. IBEX_REGFILE=upstream reproduces the
# design docs/38 to docs/42 measured.
#
# IBEX_FAULT_PORT is forced on here, and this flow cannot run without it:
# soc_top.v connects `u_ibex.rf_ecc_err_o` unconditionally, so an
# unpatched ibex_top fails at elaboration with the port's name in the
# message. That is the coupling, and it is loud rather than silent
# (docs/44 section 4).
IBEX_FAULT_PORT=1
export IBEX_FAULT_PORT
# shellcheck source=hw/soc/flow/ibex_sources.sh
. "$SOC_DIR/flow/ibex_sources.sh"

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${IVERILOG:?}" "${VVP:?}"

[ -d "$SOC_DIR/gen" ] || {
  echo "hw/soc/gen is empty: run flow/sv2v_ibex.sh first" >&2; exit 1; }

mkdir -p "$OUT"

# Which workload.  docs/42 and docs/43 ran one program; docs/46 adds a
# second, and the campaign's value depends on the two being run by the
# SAME instrument -- tb_soc_fi.v, hw/soc/fi/targets.py and campaign.py
# are identical for both, and the only thing that differs is the four
# words the program publishes.
#
#   workload    hw/soc/tb/sw/fi_workload.c   -- docs/42's dense kernel
#   supervisor  hw/soc/tb/sw/fi_supervisor.c -- docs/46's static
#                                               partitioned supervisor
FI_WORKLOAD=${FI_WORKLOAD:-workload}
case "$FI_WORKLOAD" in
  workload)   SW_BUILD=build_sw_fi.sh;  IMG=fi_workload ;;
  supervisor) SW_BUILD=build_sw_sup.sh; IMG=fi_supervisor ;;
  *) echo "FI_WORKLOAD must be 'workload' or 'supervisor'" >&2; exit 1 ;;
esac

SW_DEFINES=${SW_DEFINES:-}
# shellcheck disable=SC2086
"$SOC_DIR/flow/$SW_BUILD" "$OUT" "-DUART_SCALER_VAL=${UART_SCALER}u" $SW_DEFINES

# The site table.  Generated into the OUTPUT directory, not into the
# source tree: it is derived from hw/soc/fi/targets.py the way
# hw/soc/gen is derived from ext/ibex, and the repository's rule for
# both is fetched-or-generated, never vendored.
FI_REGFILE=${IBEX_REGFILE:-secded} \
  python3 "$SOC_DIR/fi/targets.py" "$OUT/fi_targets.vh" > "$OUT/fi_targets.txt"

# The testbench reads the substituted register file's correction
# counters hierarchically, and those names exist only in the hardened
# build.  A define rather than a `defparam` because a hierarchical
# reference to a name that does not exist is an elaboration error in
# Icarus, not a warning.
RF_DEFINE=()
[ "${IBEX_REGFILE:-secded}" = "secded" ] && RF_DEFINE=(-DFI_REGFILE_SECDED)

NM=$SOC_DIR/tools/rvgcc/bin/riscv-none-elf-nm
sym () {
  local a
  a=$("$NM" "$OUT/$IMG.elf" | awk -v s="$1" '$3 == s { print $1 }')
  [ -n "$a" ] || { echo "symbol not found: $1" >&2; exit 1; }
  echo "32'h$a"
}

# The same lookup, but for a symbol only the FI_BUSSTAT build defines,
# and 0 when it is absent. tb_soc_fi.v prints the software-visible fault
# counters only when the address is nonzero, so the default build is
# unchanged and the demonstration build needs no second testbench.
#
# A MISSING symbol is 0 here and so is a MISSPELLED one, which is why
# the testbench prints the address beside the values: a silent zero
# looks exactly like a counter that never moved, and a report that
# cannot tell those apart is the failure this feature exists to remove.
sym_opt () {
  local a
  a=$("$NM" "$OUT/$IMG.elf" | awk -v s="$1" '$3 == s { print $1 }')
  if [ -n "$a" ]; then echo "32'h$a"; else echo "32'h0"; fi
}

"$IVERILOG" -g2005-sv -o "$OUT/tb_soc_fi.vvp" \
  -I "$SOC_DIR/rtl" \
  -I "$OUT" \
  -DSG13G2_ICG_BEHAVIOURAL \
  -DROM_HEX="\"$OUT/$IMG.hex\"" \
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
  -DFI_BST_SEC_ADDR="$(sym_opt fi_bst_sec)" \
  -DFI_BST_RD_ADDR="$(sym_opt fi_bst_rd)" \
  -DFI_BST_DED_ADDR="$(sym_opt fi_bst_ded)" \
  -DFI_BST_TMR_ADDR="$(sym_opt fi_bst_tmr)" \
  "${RF_DEFINE[@]}" \
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
  "$SOC_DIR/rtl/soc_busstat.v" \
  "$SOC_DIR/rtl/soc_tmr_bank.v" \
  "$PILOT_RTL/tmr_voter.v" \
  "$SOC_DIR/rtl/prim_clock_gating.v" \
  $(ibex_sources "$SOC_DIR") \
  2>&1 | tee "$OUT/iverilog.log"

echo "== elaborated $OUT/tb_soc_fi.vvp"
