#!/usr/bin/env bash
# Build everything the NPU-connection fault-injection campaign of docs/52
# needs, and elaborate it ONCE.
#
#   fi_npu.sh [out_dir]
#
# The campaign runs hundreds of simulations of the same design with
# different plusargs, so elaboration is hoisted out of the loop: this
# script produces one `tb_soc_npu_fi.vvp` and `hw/soc/fi/npu_campaign.py`
# invokes `vvp` on it with +site, +bit, +cycle, +armed and +budget.  That
# is why the injection site is a runtime argument and a case statement
# rather than a compile-time define -- an elaboration per injection would
# cost more than the simulations do.  hw/soc/flow/fi_core.sh's header
# makes the same argument and this file is its sibling.
#
# SOURCES ARE EXACTLY sim_soc.sh's.  This project's hw/soc/rtl/soc_*.v,
# the sv2v-converted Ibex in hw/soc/gen/, and SEVEN FILES READ OUT OF THE
# FROZEN hw/rtl/ AND NEVER WRITTEN: pilot_top.v, lif_core.v, aer_fifo.v,
# scrub.v, secded_enc.v, secded_dec.v and tmr_voter.v, plus npu_regs.vh
# through an include path.  docs/34 pins those by git blob hash and the
# TTIHP26b shuttle closes 2026-09-21; docs/51 section 16 lists them.
#
# THE DIE IS INSIDE THE DESIGN UNDER TEST AND THAT IS THE POINT.  The
# campaign injects into the connection AND into the die's own half of the
# serial transport, and hw/soc/fi/npu_targets.py keeps the two in
# separate strata because they lead to different decisions: one is a
# design still open and the other is silicon already committed.

set -euo pipefail

SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PILOT_RTL=$(cd "$SOC_DIR/../rtl" && pwd)
OUT=${1:-$SOC_DIR/out/fi-npu}

UART_SCALER=${UART_SCALER:-0}
UART_BIT_CYCLES=$(( 8 * (UART_SCALER + 1) ))

# The Ibex source list.  IBEX_REGFILE defaults to `secded`, which is the
# design docs/43 and docs/44 ship and the one soc_top.v is measured at
# today.  IBEX_FAULT_PORT is forced on for the reason fi_core.sh gives:
# soc_top.v connects `u_ibex.rf_ecc_err_o` unconditionally, so an
# unpatched ibex_top fails at elaboration with the port's name in the
# message.
IBEX_FAULT_PORT=1
export IBEX_FAULT_PORT
# shellcheck source=hw/soc/flow/ibex_sources.sh
. "$SOC_DIR/flow/ibex_sources.sh"

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${IVERILOG:?}" "${VVP:?}"

[ -d "$SOC_DIR/gen" ] || {
  echo "hw/soc/gen is empty: run flow/sv2v_ibex.sh first" >&2; exit 1; }

mkdir -p "$OUT"

# hw/rtl/secded_enc.v and hw/rtl/secded_dec.v are read by TWO consumers
# -- the register-file codec (IBEX_REGFILE=secded) and the pilot's
# weight-word ECC -- and Icarus refuses a module declared twice in one
# compilation unit. `ibex_sources` adds them in the secded configuration,
# so this list adds them only in the other one. Both consumers get the
# same two files out of the frozen directory either way, which is the
# point: there is one SECDED codec in this repository. Copied verbatim
# from hw/soc/flow/sim_soc.sh, whose comment this is.
if [ "${IBEX_REGFILE:-secded}" = secded ]; then
  NPU_SECDED=()
else
  NPU_SECDED=("$PILOT_RTL/secded_enc.v" "$PILOT_RTL/secded_dec.v")
fi

# SOC_NPU_SRC and SOC_NPU_SER_SRC substitute a SCRATCH COPY of one of
# the two connection files, which is the mechanism docs/51 section 17
# already established for its fourteen mutations and the one
# hw/soc/tb/cocotb/Makefile.soc_npu exposes.
#
# THIS CAMPAIGN USES IT FOR A COUNTERFACTUAL AND NOT FOR A MUTATION.
# "The protection works" is not a measurement unless the same experiment
# on the design WITHOUT it produces a different number -- docs/41
# section 8.3 -- and the connection has exactly one recovery mechanism of
# its own: the bounded wait on an injection-queue fetch, which expires,
# returns the engine to idle and latches IRQ_CAUSE.FETCH_ER. It is not a
# parameter that can be turned off (FETCH_MAX is constrained to 1..15),
# so the counterfactual is a copy of soc_npu.v with the expiry term
# removed, replayed against the records where the bound actually fired.
# docs/52 section 6.5.
#
# The substituted file is NOT in the source tree and the campaign log
# carries the tag, because a build that is not the design of record must
# not be able to write a records.csv that looks like one.
NPU_SRC=${SOC_NPU_SRC:-$SOC_DIR/rtl/soc_npu.v}
NPU_SER_SRC=${SOC_NPU_SER_SRC:-$SOC_DIR/rtl/soc_npu_ser.v}
[ -f "$NPU_SRC" ] || { echo "SOC_NPU_SRC does not exist: $NPU_SRC" >&2; exit 1; }
[ -f "$NPU_SER_SRC" ] || {
  echo "SOC_NPU_SER_SRC does not exist: $NPU_SER_SRC" >&2; exit 1; }

SW_DEFINES=${SW_DEFINES:-}
# shellcheck disable=SC2086
"$SOC_DIR/flow/build_sw_npu_fi.sh" "$OUT" \
    "-DUART_SCALER_VAL=${UART_SCALER}u" $SW_DEFINES

# The site table.  Generated into the OUTPUT directory, not into the
# source tree: it is derived from hw/soc/fi/npu_targets.py the way
# hw/soc/gen is derived from ext/ibex, and the repository's rule for both
# is fetched-or-generated, never vendored.
python3 "$SOC_DIR/fi/npu_targets.py" "$OUT/fi_npu_targets.vh" \
    > "$OUT/fi_npu_targets.txt"

NM=$SOC_DIR/tools/rvgcc/bin/riscv-none-elf-nm
sym () {
  local a
  a=$("$NM" "$OUT/fi_npu.elf" | awk -v s="$1" '$3 == s { print $1 }')
  [ -n "$a" ] || { echo "symbol not found: $1" >&2; exit 1; }
  echo "32'h$a"
}

"$IVERILOG" -g2005-sv -o "$OUT/tb_soc_npu_fi.vvp" \
  -I "$SOC_DIR/rtl" \
  -I "$PILOT_RTL" \
  -I "$OUT" \
  -DSG13G2_ICG_BEHAVIOURAL \
  -DROM_HEX="\"$OUT/fi_npu.hex\"" \
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
  -DFI_NEV_ADDR="$(sym fi_nev)" \
  -DFI_CAUSE_ADDR="$(sym fi_cause)" \
  -DFI_STATUS_ADDR="$(sym fi_status)" \
  -DFI_DROP_ADDR="$(sym fi_drop)" \
  -DFI_OVF_ADDR="$(sym fi_ovf)" \
  -DFI_OOR_ADDR="$(sym fi_oor)" \
  -DFI_CNT_ADDR="$(sym fi_cnt)" \
  -DFI_SPINS_ADDR="$(sym fi_spins)" \
  -DFI_BSTCOR_ADDR="$(sym fi_bst_cor)" \
  -DFI_BSTDET_ADDR="$(sym fi_bst_det)" \
  -DFI_BSTTMR_ADDR="$(sym fi_bst_tmr)" \
  -s tb_soc_npu_fi \
  "$SOC_DIR/tb/tb_soc_npu_fi.v" \
  "$SOC_DIR/rtl/soc_top.v" \
  "$SOC_DIR/rtl/soc_bus.v" \
  "$SOC_DIR/rtl/soc_apb_bridge.v" \
  "$SOC_DIR/rtl/soc_mem.v" \
  "$SOC_DIR/rtl/soc_pnp.v" \
  "$SOC_DIR/rtl/soc_apb_pnp.v" \
  "$SOC_DIR/rtl/soc_uart.v" \
  "$SOC_DIR/rtl/soc_gpio.v" \
  "$SOC_DIR/rtl/soc_qspi.v" \
  "$SOC_DIR/rtl/soc_clint.v" \
  "$SOC_DIR/rtl/soc_gptimer.v" \
  "$SOC_DIR/rtl/soc_wdog.v" \
  "$SOC_DIR/rtl/soc_busstat.v" \
  "$SOC_DIR/rtl/soc_tmr_bank.v" \
  "$NPU_SRC" \
  "$NPU_SER_SRC" \
  "$PILOT_RTL/pilot_top.v" \
  "$PILOT_RTL/lif_core.v" \
  "$PILOT_RTL/aer_fifo.v" \
  "$PILOT_RTL/scrub.v" \
  ${NPU_SECDED+"${NPU_SECDED[@]}"} \
  "$PILOT_RTL/tmr_voter.v" \
  "$SOC_DIR/rtl/prim_clock_gating.v" \
  $(ibex_sources "$SOC_DIR") \
  2>&1 | tee "$OUT/iverilog.log"

# THE FROZEN DIRECTORY IS ASSERTED CLEAN AFTER THE BUILD, NOT ASSUMED.
#
# docs/49 section 8.1 is the reason this check is here rather than a
# comment: a flow step that "elaborates, exits zero and changes nothing"
# is indistinguishable from one that worked.  Seven files in hw/rtl/ are
# read by the line above; if any of them has been modified, every number
# this campaign produces is about a die that is not the submission.
# `git diff --quiet` against the index is what docs/51's
# sw/tests/test_soc_npu_guards.py asserts, and it is asserted again here
# because a campaign is a different consumer from a test suite.
ROOT=$(cd "$SOC_DIR/../.." && pwd)
if command -v git >/dev/null 2>&1 && [ -d "$ROOT/.git" ]; then
  if ! git -C "$ROOT" diff --quiet -- hw/rtl; then
    echo "== hw/rtl/ is MODIFIED against the index. docs/34 pins the" >&2
    echo "   TTIHP26b submission by blob hash and this campaign would" >&2
    echo "   be measuring a die that is not it. Refusing to elaborate." >&2
    exit 1
  fi
  echo "== hw/rtl/ is clean against the index"
fi

if [ "$NPU_SRC" != "$SOC_DIR/rtl/soc_npu.v" ] ||
   [ "$NPU_SER_SRC" != "$SOC_DIR/rtl/soc_npu_ser.v" ]; then
  echo "== NOT THE DESIGN OF RECORD:" > "$OUT/SUBSTITUTED"
  echo "   soc_npu.v     <- $NPU_SRC" >> "$OUT/SUBSTITUTED"
  echo "   soc_npu_ser.v <- $NPU_SER_SRC" >> "$OUT/SUBSTITUTED"
  cat "$OUT/SUBSTITUTED"
else
  rm -f "$OUT/SUBSTITUTED"
fi

echo "== elaborated $OUT/tb_soc_npu_fi.vvp"
