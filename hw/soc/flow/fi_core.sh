#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

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

# ---- THE ACCELERATOR, WHICH WAS MISSING ------------------------------
#
# docs/51 put `u_npu` inside soc_top.v and this source list was not
# updated, so from that commit until docs/61 this script did not
# elaborate at all:
#
#   hw/soc/rtl/soc_top.v:624: error: Unknown module type: soc_npu
#
# docs/57 section 3.1 found it and deliberately did not fix it, because a
# repair to the instrument three campaigns are reported from belongs in
# its own change. This is that repair, and what it does NOT do is stated
# where it can be seen: THE CAMPAIGNS OF docs/42, docs/43 AND docs/46 ARE
# NOT RE-RUN BY IT. What is restored is that they CAN be rebuilt. Whether
# the design they would now run on -- which has 2,178 more flip-flops in
# it and a sixth fabric port -- produces the same outcome distribution is
# a separate measurement with its own cost, and docs/61 did not take it.
#
# The six files and the two include paths are flow/sim_soc.sh's, exactly:
# soc_npu.v includes rtl/soc_npu_regs.vh and hw/rtl/pilot_top.v includes
# hw/rtl/npu_regs.vh. hw/rtl/ is READ and never modified; soc_npu.v
# INSTANTIATES the frozen pilot rather than copying it.
NPU_SRC=("$SOC_DIR/rtl/soc_npu.v"
         "$SOC_DIR/rtl/soc_npu_ser.v"
         "$PILOT_RTL/pilot_top.v"
         "$PILOT_RTL/lif_core.v"
         "$PILOT_RTL/aer_fifo.v"
         "$PILOT_RTL/scrub.v")
# One SECDED codec in this repository, and two consumers of it: the
# register-file codec at IBEX_REGFILE=secded and lif_core's weight-word
# ECC. ibex_sources() emits the pair in the secded configuration, so this
# list emits it only in the other one -- Icarus refuses a module declared
# twice in one compilation unit. flow/sim_soc.sh states the same rule for
# the same pair and this is a copy of it, not a second policy.
if [ "${IBEX_REGFILE:-secded}" != secded ]; then
  NPU_SRC+=("$PILOT_RTL/secded_enc.v" "$PILOT_RTL/secded_dec.v")
fi

# SOC_MEM_RDREG=1 builds the same campaign against docs/50's registered
# memory read return -- soc_top.v's MEM_RDREG. It DEFAULTS TO 0 and
# nothing sets it; docs/50 section 7 uses it to price the extra cycle on
# docs/46's supervisor, which is the second workload this repository has
# and the only one with a frame schedule.
#
# It is a GENERATED `defparam` IN A SECOND ROOT and not `-P`, for the
# reason hw/soc/flow/sim_soc.sh's header gives at length: Icarus's -P
# reaches root modules only and a hierarchical path that names no root is
# discarded in silence (docs/49 section 8.1). The arm check after
# elaboration is the same one, and it is what makes a discarded override
# a failed run rather than a run of the other design.
SOC_MEM_RDREG=${SOC_MEM_RDREG:-0}

# SOC_MEM_HARDEN=0 is docs/67's counterfactual -- the memories as plain
# arrays with no check bits and no scrubber -- and SOC_SCRUB_IVL is the
# scrubbers' interval at reset (empty: the design's default; 0: every
# idle cycle, so the scrubber walks the whole RAM inside one run). Both
# reach soc_top by the same generated defparam root, for the same
# reason, and both are checked after elaboration below. The default
# build is the design.
SOC_MEM_HARDEN=${SOC_MEM_HARDEN:-1}
SOC_SCRUB_IVL=${SOC_SCRUB_IVL:-}
# SOC_ROM_HARDEN, docs/74: soc_top.v's ROM_HARDEN follows MEM_HARDEN
# unless overridden, and the layout netlist of docs/70 to docs/73 was
# synthesised with ROM_HARDEN = 0 (docs/68 section 8: the ROM's check
# macros are instantiated and placed by nothing). A gate-level campaign
# on that netlist needs the RTL of the SAME configuration to compare
# against, so this knob exists. Empty (the default) leaves the design's
# own value, which is what every campaign before docs/74 ran.
SOC_ROM_HARDEN=${SOC_ROM_HARDEN:-}
# SOC_CLKGATE, docs/76: soc_top.v's CLKGATE, the fabric's and the
# accelerator's clock gates. 0 is the ungated baseline the gates' cost is
# measured against and it is how the two builds of the equivalence check
# are made from one source tree. Defaults to the design.
SOC_CLKGATE=${SOC_CLKGATE:-1}
DEFPARAMS=""
[ "$SOC_MEM_RDREG" = 0 ] || DEFPARAMS="$DEFPARAMS
  defparam tb_soc_fi.dut.MEM_RDREG = $SOC_MEM_RDREG;"
[ "$SOC_MEM_HARDEN" = 1 ] || DEFPARAMS="$DEFPARAMS
  defparam tb_soc_fi.dut.MEM_HARDEN = $SOC_MEM_HARDEN;"
[ -z "$SOC_ROM_HARDEN" ] || DEFPARAMS="$DEFPARAMS
  defparam tb_soc_fi.dut.ROM_HARDEN = $SOC_ROM_HARDEN;"
[ -z "$SOC_SCRUB_IVL" ] || DEFPARAMS="$DEFPARAMS
  defparam tb_soc_fi.dut.SCRUB_IVL_RST = $SOC_SCRUB_IVL;"
[ "$SOC_CLKGATE" = 1 ] || DEFPARAMS="$DEFPARAMS
  defparam tb_soc_fi.dut.CLKGATE = $SOC_CLKGATE;"
MEM_ROOT=()
MEM_SRC=()
if [ -n "$DEFPARAMS" ]; then
  cat > "$OUT/soc_param_override.v" <<EOF
// GENERATED by hw/soc/flow/fi_core.sh.
//   SOC_MEM_RDREG=$SOC_MEM_RDREG  SOC_MEM_HARDEN=$SOC_MEM_HARDEN
//   SOC_SCRUB_IVL=${SOC_SCRUB_IVL:-default}  SOC_ROM_HARDEN=${SOC_ROM_HARDEN:-default}
//   SOC_CLKGATE=$SOC_CLKGATE
// NOT PART OF THE DESIGN. A second elaboration root whose only content
// is defparams -- see the header.
module soc_param_override;$DEFPARAMS
endmodule
EOF
  MEM_ROOT=(-s soc_param_override)
  MEM_SRC=("$OUT/soc_param_override.v")
fi
# The testbench reads the memories' check arrays and the SCRUB block's
# counters hierarchically, and those names exist only in the hardened
# build -- the same rule as FI_REGFILE_SECDED above.
MEM_DEFINE=()
[ "$SOC_MEM_HARDEN" = 1 ] && MEM_DEFINE=(-DFI_MEM_HARDENED)
# The ROM's check array exists only when the ROM is hardened; the
# testbench's ROM check-bit deposit is compiled out otherwise.
[ "$SOC_ROM_HARDEN" = 0 ] && MEM_DEFINE+=(-DFI_ROM_PLAIN)

# FI_EXTRA_SRC and FI_EXTRA_ROOT, docs/74: additional source files and
# additional elaboration roots, both empty by default. The gate-level
# campaign's flop-set reconciliation needs the RTL's site registers
# traced per cycle on the clean run, and it does that from a SECOND
# ROOT that reads `tb_soc_fi.dut...` hierarchically -- the same shape as
# soc_param_override above -- so that tb_soc_fi.v, the instrument every
# campaign since docs/42 is reported from, is not edited to carry it.
FI_EXTRA_SRC=${FI_EXTRA_SRC:-}
FI_EXTRA_ROOT=${FI_EXTRA_ROOT:-}
EXTRA_ROOT=()
EXTRA_SRC=()
[ -z "$FI_EXTRA_ROOT" ] || EXTRA_ROOT=(-s "$FI_EXTRA_ROOT")
# shellcheck disable=SC2206
[ -z "$FI_EXTRA_SRC" ] || EXTRA_SRC=($FI_EXTRA_SRC)

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
  -I "$PILOT_RTL" \
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
  ${MEM_DEFINE+"${MEM_DEFINE[@]}"} \
  -s tb_soc_fi \
  ${MEM_ROOT+"${MEM_ROOT[@]}"} \
  ${MEM_SRC+"${MEM_SRC[@]}"} \
  ${EXTRA_ROOT+"${EXTRA_ROOT[@]}"} \
  ${EXTRA_SRC+"${EXTRA_SRC[@]}"} \
  "$SOC_DIR/tb/tb_soc_fi.v" \
  "$SOC_DIR/rtl/soc_top.v" \
  "$SOC_DIR/rtl/soc_bus.v" \
  "$SOC_DIR/rtl/soc_apb_bridge.v" \
  "$SOC_DIR/rtl/soc_mem.v" \
  "$SOC_DIR/rtl/soc_mem_ecc.v" \
  "$SOC_DIR/rtl/soc_scrub.v" \
  "$SOC_DIR/rtl/soc_boot.v" \
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
  "${NPU_SRC[@]}" \
  "$PILOT_RTL/tmr_voter.v" \
  "$SOC_DIR/rtl/prim_clock_gating.v" \
  $(ibex_sources "$SOC_DIR") \
  2>&1 | tee "$OUT/iverilog.log"

# THE OVERRIDE IS ASSERTED, NOT ASSUMED. `g_rd1` and `g_rd2` are the two
# arms of soc_mem.v's RDREG generate and exactly one exists in any
# elaborated design; grep -a on the object rather than `strings | grep`,
# because this script runs under `set -o pipefail` and `grep -q` closes
# the pipe on its first match.
want=g_rd1; other=g_rd2
[ "$SOC_MEM_RDREG" = 0 ] || { want=g_rd2; other=g_rd1; }
grep -qa "\"$want\"" "$OUT/tb_soc_fi.vvp" || {
  echo "== the SOC_MEM_RDREG override did not take: $want absent from the" >&2
  echo "   elaborated design at SOC_MEM_RDREG=$SOC_MEM_RDREG" >&2; exit 1; }
if grep -qa "\"$other\"" "$OUT/tb_soc_fi.vvp"; then
  echo "== both RDREG arms elaborated; that cannot happen" >&2; exit 1
fi
echo "== memory read return: $want (SOC_MEM_RDREG=$SOC_MEM_RDREG)"
want=g_ecc; other=g_plain
[ "$SOC_MEM_HARDEN" = 1 ] || { want=g_plain; other=g_ecc; }
grep -qa "\"$want\"" "$OUT/tb_soc_fi.vvp" || {
  echo "== the SOC_MEM_HARDEN override did not take: $want absent from the" >&2
  echo "   elaborated design at SOC_MEM_HARDEN=$SOC_MEM_HARDEN" >&2; exit 1; }
# With SOC_ROM_HARDEN set to the other value the ROM legitimately carries
# the other arm (docs/74's configuration: RAM hardened, ROM plain), so the
# exclusion below is a check on the RAM's arm only in that case.
if [ -z "$SOC_ROM_HARDEN" ] || [ "$SOC_ROM_HARDEN" = "$SOC_MEM_HARDEN" ]; then
  if grep -qa "\"$other\"" "$OUT/tb_soc_fi.vvp"; then
    echo "== both memory codec arms elaborated; that cannot happen" >&2; exit 1
  fi
fi
echo "== memory codec: $want (SOC_MEM_HARDEN=$SOC_MEM_HARDEN, scrub interval ${SOC_SCRUB_IVL:-default})"

echo "== elaborated $OUT/tb_soc_fi.vvp"
