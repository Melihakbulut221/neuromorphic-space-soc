#!/usr/bin/env bash
# Elaborate and run the whole SoC in Icarus Verilog.
#
#   sim_soc.sh [out_dir]
#   SW_DEFINES=-DWDOG_RESET_DEMO sim_soc.sh out/sim-soc-wdog
#
# The second form builds the same image with one behaviour changed --
# the NMI handler does not acknowledge -- and runs the watchdog's whole
# escalation ladder, three boots of the SoC in one simulation. See
# wdog_demo() in hw/soc/tb/sw/test_ibex.c.
#
# Sources: hw/soc/rtl/soc_*.v (this project's), hw/soc/gen/*.v (the
# sv2v-converted Ibex, exactly as sim_ibex.sh reads it) and
# hw/soc/tb/tb_soc.v. The RTL read here is the sv2v output, not the
# SystemVerilog, for the reason docs/38 gives: Icarus is this project's
# simulator.
#
# The UART divider is defined ONCE, here, and given to both the compiler
# and the simulator. The program writes it into the scaler register and
# the testbench's serial decoder assumes it; if the two disagreed the run
# would show framing errors rather than a clear message, so they are not
# allowed to disagree.

set -euo pipefail

SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# hw/rtl/tmr_voter.v is READ from here and never modified: it is the
# proved majority primitive the watchdog's W6 protection votes with, and
# docs/34 freezes the directory it lives in.
PILOT_RTL=$(cd "$SOC_DIR/../rtl" && pwd)
OUT=${1:-$SOC_DIR/out/sim-soc}

# GRLIB's APBUART scaler feeds an 8x oversampling clock, so the bit
# period is 8*(SCALER+1) system clocks. 0 is the fastest legal value and
# keeps the console out of the run time: the program prints a few hundred
# characters and each costs 80 cycles.
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

SW_DEFINES=${SW_DEFINES:-}
# shellcheck disable=SC2086
"$SOC_DIR/flow/build_sw_soc.sh" "$OUT" "-DUART_SCALER_VAL=${UART_SCALER}u" $SW_DEFINES

# Symbol addresses come out of the ELF that was just built rather than
# being written down here, so neither file carries a constant that goes
# stale the next time the program is edited.
NM=$SOC_DIR/tools/rvgcc/bin/riscv-none-elf-nm
sym () {
  local a
  a=$("$NM" "$OUT/test_soc.elf" | awk -v s="$1" '$3 == s { print $1 }')
  [ -n "$a" ] || { echo "symbol not found: $1" >&2; exit 1; }
  echo "32'h$a"
}

# SG13G2_ICG_BEHAVIOURAL: rtl/prim_clock_gating.v binds the real
# sg13g2_lgcp_1 cell for synthesis; Icarus has no such cell unless the
# PDK simulation library is read too, and reading it here would put PDK
# models into a pure-RTL run.
"$IVERILOG" -g2005-sv -o "$OUT/tb_soc.vvp" \
  -I "$SOC_DIR/rtl" \
  -DSG13G2_ICG_BEHAVIOURAL \
  -DROM_HEX="\"$OUT/test_soc.hex\"" \
  -DUART_BIT_CYCLES="$UART_BIT_CYCLES" \
  -DEXIT_CODE_ADDR="$(sym exit_code)" \
  -DEXIT_MAGIC_ADDR="$(sym exit_magic)" \
  -DTRAP_MCAUSE_ADDR="$(sym trap_mcause)" \
  -DTRAP_MEPC_ADDR="$(sym trap_mepc)" \
  -DTRAP_COUNT_ADDR="$(sym trap_count)" \
  -s tb_soc \
  "$SOC_DIR/tb/tb_soc.v" \
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

echo "== elaborated; running"
"$VVP" "$OUT/tb_soc.vvp" 2>&1 | tee "$OUT/sim.log"

grep -q "^\[TB\] PASS" "$OUT/sim.log" || {
  echo "== SoC SIMULATION FAILED" >&2; exit 1; }
echo "== soc: PASS"
