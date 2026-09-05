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
# hw/rtl is READ from here and never modified. docs/34 freezes that
# directory and this flow reads seven files out of it: tmr_voter.v, the
# proved majority primitive the watchdog's W6 protection votes with, and
# since docs/51 the whole of pilot_top.v and the blocks it is built
# from, because soc_npu.v instantiates the frozen submission rather than
# a copy of it. npu_regs.vh is reached through the -I below.
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

# hw/rtl/secded_enc.v and hw/rtl/secded_dec.v are read by TWO consumers
# now -- the register-file codec (IBEX_REGFILE=secded) and the pilot's
# weight-word ECC -- and Icarus refuses a module declared twice in one
# compilation unit. ibex_sources adds them in the secded configuration,
# so this list adds them only in the other one. Both consumers get the
# same two files out of the frozen directory either way, which is the
# point: there is one SECDED codec in this repository.
if [ "${IBEX_REGFILE:-secded}" = secded ]; then
  NPU_SECDED=()
else
  NPU_SECDED=("$PILOT_RTL/secded_enc.v" "$PILOT_RTL/secded_dec.v")
fi

# SOC_RF_SYNPRE=1 builds the register file with the syndrome tree hoisted
# past the read multiplexer -- ibex_regfile_secded.v's SYNPRE. It
# DEFAULTS TO 0 and nothing sets it; docs/49 uses it to check that the
# whole-SoC run is cycle-identical with the hoisted read path, which is
# the behavioural half of a change whose logical half is properties C6
# and C7 of hw/soc/formal/regfile_secded.sby.
#
# It is a GENERATED `defparam` IN A SECOND ROOT MODULE and not a source
# edit, because the parameter is on an instance four levels down inside
# ibex_top and this flow's whole discipline is that nothing under
# hw/soc/ext or hw/soc/gen is modified to change the design.
#
# AND IT IS NOT `-P`, WHICH IS THE OBVIOUS WAY AND DOES NOT WORK.
# `iverilog -Ptb_soc.dut.u_ibex.gen_regfile_ff.register_file_i.SYNPRE=1`
# ELABORATES, EXITS 0, PRINTS NOTHING AND CHANGES NOTHING: Icarus's -P
# reaches root modules only, and a hierarchical path that names no root
# is discarded in silence. It was measured on a four-module toy --
# `-P` leaves the parameter at 0, the defparam below sets it -- and
# docs/49 section 8 records it, because a knob that looks applied and is
# not is exactly the shape docs/41 section 6.6 counts. The check after
# elaboration below is what makes it impossible to repeat here.
SOC_RF_SYNPRE=${SOC_RF_SYNPRE:-0}

# SOC_MEM_RDREG=1 is docs/50's knob and it reaches soc_top's own
# parameter by the same mechanism and for the same reason: a second
# elaboration root carrying a defparam, never `-P`.
#
# IT MOVES THE CYCLE COUNT, and that is the whole point of running it
# here. One extra cycle of read latency on the RAM and the boot ROM makes
# the whole-SoC run NOT cycle-identical, and it is not supposed to be:
# docs/50 reports the new count, its breakdown between the two memories
# and the fact that all 22 checks still pass and the escalation demo
# still runs.
#
# SOC_RAM_RDREG and SOC_ROM_RDREG are the ATTRIBUTION knobs and default
# to SOC_MEM_RDREG. They defparam the two soc_mem instances individually
# rather than soc_top's parameter, which is what lets docs/50 section 5
# split the cycle cost between instruction fetch and load/store instead
# of reporting one number for both. Setting them differently is a
# measurement configuration and not a design: nothing ships that way, and
# soc_top has one parameter for both memories.
SOC_MEM_RDREG=${SOC_MEM_RDREG:-0}
SOC_RAM_RDREG=${SOC_RAM_RDREG:-$SOC_MEM_RDREG}
SOC_ROM_RDREG=${SOC_ROM_RDREG:-$SOC_MEM_RDREG}

# SOC_PROBE=1 compiles hw/soc/tb/soc_bus_probe.v in as a second root. It
# observes the fabric and drives nothing; docs/50 section 3 is what it is
# for and its own header says why. Off by default, because a run that
# prints counters is not the run whose log is diffed against the
# invariant.
SOC_PROBE=${SOC_PROBE:-0}
PROBE_ROOT=()
PROBE_SRC=()
if [ "$SOC_PROBE" != 0 ]; then
  PROBE_ROOT=(-s soc_bus_probe)
  PROBE_SRC=("$SOC_DIR/tb/soc_bus_probe.v")
fi

RF_ROOT=()
RF_SRC=()
DEFPARAMS=""
if [ "$SOC_RF_SYNPRE" != 0 ] && [ "${IBEX_REGFILE:-secded}" = secded ]; then
  DEFPARAMS="$DEFPARAMS
  defparam tb_soc.dut.u_ibex.gen_regfile_ff.register_file_i.SYNPRE
             = $SOC_RF_SYNPRE;"
fi
if [ "$SOC_RAM_RDREG" = "$SOC_ROM_RDREG" ]; then
  if [ "$SOC_MEM_RDREG" != 0 ]; then
    DEFPARAMS="$DEFPARAMS
  defparam tb_soc.dut.MEM_RDREG = $SOC_MEM_RDREG;"
  fi
else
  DEFPARAMS="$DEFPARAMS
  defparam tb_soc.dut.u_ram.RDREG = $SOC_RAM_RDREG;
  defparam tb_soc.dut.u_rom.RDREG = $SOC_ROM_RDREG;"
fi
if [ -n "$DEFPARAMS" ]; then
  RF_ROOT=(-s soc_param_override)
  RF_SRC=("$OUT/soc_param_override.v")
fi

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
if [ ${#RF_SRC[@]} -gt 0 ]; then
  cat > "$OUT/soc_param_override.v" <<EOF
// GENERATED by hw/soc/flow/sim_soc.sh.
//   SOC_RF_SYNPRE=$SOC_RF_SYNPRE
//   SOC_MEM_RDREG=$SOC_MEM_RDREG (ram $SOC_RAM_RDREG, rom $SOC_ROM_RDREG)
// NOT PART OF THE DESIGN. A second elaboration root whose only content
// is defparams, which is the only way Icarus will set a parameter on an
// instance that is not a root -- see the header.
module soc_param_override;$DEFPARAMS
endmodule
EOF
fi

"$IVERILOG" -g2005-sv -o "$OUT/tb_soc.vvp" \
  -I "$SOC_DIR/rtl" \
  -I "$PILOT_RTL" \
  -DSG13G2_ICG_BEHAVIOURAL \
  -DROM_HEX="\"$OUT/test_soc.hex\"" \
  -DUART_BIT_CYCLES="$UART_BIT_CYCLES" \
  -DEXIT_CODE_ADDR="$(sym exit_code)" \
  -DEXIT_MAGIC_ADDR="$(sym exit_magic)" \
  -DTRAP_MCAUSE_ADDR="$(sym trap_mcause)" \
  -DTRAP_MEPC_ADDR="$(sym trap_mepc)" \
  -DTRAP_COUNT_ADDR="$(sym trap_count)" \
  -s tb_soc \
  ${RF_ROOT+"${RF_ROOT[@]}"} \
  ${RF_SRC+"${RF_SRC[@]}"} \
  ${PROBE_ROOT+"${PROBE_ROOT[@]}"} \
  ${PROBE_SRC+"${PROBE_SRC[@]}"} \
  "$SOC_DIR/tb/tb_soc.v" \
  "$SOC_DIR/rtl/soc_top.v" \
  "$SOC_DIR/rtl/soc_bus.v" \
  "$SOC_DIR/rtl/soc_apb_bridge.v" \
  "$SOC_DIR/rtl/soc_mem.v" \
  "$SOC_DIR/rtl/soc_pnp.v" \
  "$SOC_DIR/rtl/soc_apb_pnp.v" \
  "$SOC_DIR/rtl/soc_uart.v" \
  "$SOC_DIR/rtl/soc_gpio.v" \
  "$SOC_DIR/rtl/soc_qspi.v" \
  "$SOC_DIR/tb/flash_w25q128jv.v" \
  "$SOC_DIR/rtl/soc_clint.v" \
  "$SOC_DIR/rtl/soc_gptimer.v" \
  "$SOC_DIR/rtl/soc_wdog.v" \
  "$SOC_DIR/rtl/soc_busstat.v" \
  "$SOC_DIR/rtl/soc_tmr_bank.v" \
  "$SOC_DIR/rtl/soc_npu.v" \
  "$SOC_DIR/rtl/soc_npu_ser.v" \
  "$PILOT_RTL/pilot_top.v" \
  "$PILOT_RTL/lif_core.v" \
  "$PILOT_RTL/aer_fifo.v" \
  "$PILOT_RTL/scrub.v" \
  ${NPU_SECDED+"${NPU_SECDED[@]}"} \
  "$PILOT_RTL/tmr_voter.v" \
  "$SOC_DIR/rtl/prim_clock_gating.v" \
  $(ibex_sources "$SOC_DIR") \
  2>&1 | tee "$OUT/iverilog.log"

# THE OVERRIDE IS ASSERTED, NOT ASSUMED. `g_synpre` and `g_synpost` are
# the two arms of ibex_regfile_secded.v's SYNPRE generate, and exactly
# one of them exists in the elaborated design. Checking the compiled
# object rather than the command line is what turns a silently discarded
# override into a failed run -- see the header on -P.
#
# EVERY KNOB THAT SELECTS A GENERATE ARM IS CHECKED THE SAME WAY, and
# docs/50 adds the memory pipeline to the list. Each arm below is one
# side of a `generate if` in the RTL, exactly one of the pair exists in
# any elaborated design, and the arm's presence in the compiled object is
# the witness the exit status is not.
check_arm () {
  local knob=$1 val=$2 on=$3 off=$4 what=$5 want other
  if [ "$val" != 0 ]; then want=$on; other=$off; else want=$off; other=$on; fi
  # grep -a on the object, not `strings | grep`: this script runs under
  # `set -o pipefail` and `grep -q` closes the pipe on its first match,
  # so the producer dies of SIGPIPE and the check fails on success.
  grep -qa "\"$want\"" "$OUT/tb_soc.vvp" || {
    echo "== the $knob override did not take: $want absent from the" >&2
    echo "   elaborated design at $knob=$val" >&2; exit 1; }
  if grep -qa "\"$other\"" "$OUT/tb_soc.vvp"; then
    echo "== both $knob arms elaborated; that cannot happen" >&2; exit 1
  fi
  echo "== $what: $want ($knob=$val)"
}

if [ "${IBEX_REGFILE:-secded}" = secded ]; then
  check_arm SOC_RF_SYNPRE "$SOC_RF_SYNPRE" g_synpre g_synpost \
            "register file read path"
fi
if [ "$SOC_RAM_RDREG" = "$SOC_ROM_RDREG" ]; then
  check_arm SOC_MEM_RDREG "$SOC_MEM_RDREG" g_rd2 g_rd1 "memory read return"
else
  # The attribution configuration: one memory registered and one not, so
  # BOTH arms are in the design and the check above cannot apply. What is
  # checked instead is that both are there, which a build that ignored
  # the defparams would fail.
  grep -qa '"g_rd1"' "$OUT/tb_soc.vvp" && grep -qa '"g_rd2"' "$OUT/tb_soc.vvp" || {
    echo "== the per-memory RDREG defparams did not take" >&2; exit 1; }
  echo "== memory read return: ram=$SOC_RAM_RDREG rom=$SOC_ROM_RDREG (both arms present)"
fi

echo "== elaborated; running"
# The flash image on chip select 0, written by build_sw_soc.sh through
# flow/gen_flash_image.py alongside the ROM image it is checked against.
# tb_soc.v loads it into the modelled W25Q128JV with $readmemh; a run
# without it would see an erased device and fail checks 29 and 30.
"$VVP" "$OUT/tb_soc.vvp" +flash0="$OUT/flash0.hex" 2>&1 | tee "$OUT/sim.log"

grep -q "^\[TB\] PASS" "$OUT/sim.log" || {
  echo "== SoC SIMULATION FAILED" >&2; exit 1; }
echo "== soc: PASS"
