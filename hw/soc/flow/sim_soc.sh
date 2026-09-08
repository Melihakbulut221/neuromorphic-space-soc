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

# SOC_MEM_HARDEN=0 is docs/67's counterfactual: both memories as the
# plain arrays every document before it ran, no check bits, no scrubber,
# the SCRUB block present and counting nothing. IT DEFAULTS TO 1 -- the
# design -- and reaches soc_top's MEM_HARDEN by the same generated
# defparam as the knobs above, with the same arm check afterwards:
# soc_mem.v's g_ecc and g_plain are the two arms and exactly one exists.
#
# SOC_SCRUB_IVL is the scrubbers' interval at reset, soc_top's
# SCRUB_IVL_RST. Empty means the design's own default; a campaign sets 0
# so that the scrubber walks the whole RAM inside one run.
SOC_MEM_HARDEN=${SOC_MEM_HARDEN:-1}
SOC_SCRUB_IVL=${SOC_SCRUB_IVL:-}

# SOC_PROBE=1 compiles hw/soc/tb/soc_bus_probe.v in as a second root. It
# observes the fabric and drives nothing; docs/50 section 3 is what it is
# for and its own header says why. Off by default, because a run that
# prints counters is not the run whose log is diffed against the
# invariant.
# ---- the boot flow, docs/68 ----------------------------------------
#
# SOC_RAM_RANDOM is the POWER-UP MODEL and it is on by default. The RAM
# is an SRAM: it comes up undefined, and since docs/67 so does its SECDED
# check field, so a word nobody has written reads back as an
# UNCORRECTABLE rather than as a zero. tb_soc.v's +ram_random fills both
# arrays with pseudo-random bits before reset is released. Set it to 0
# to get the pre-docs/68 model, in which soc_mem.v's own initial block
# has already left every row a valid all-zero codeword -- which is a
# memory that is already initialised, and therefore a run in which the
# loader's RAM sweep proves nothing.
SOC_RAM_RANDOM=${SOC_RAM_RANDOM:-1}

# SOC_STRAP is the board's bootstrap wiring, tb_soc.v's +strap. 0 is the
# board this repository models: boot from the flash on chip select 0.
# 4 sets NOBOOT (hw/soc/tb/sw/soc_boot.h).
SOC_STRAP=${SOC_STRAP:-0}

# SOC_DED_WORD plants an uncorrectable in one RAM word on the edge after
# the loader writes it -- the fault BOOT_CAUSE_ECC exists for. Empty
# means none.
SOC_DED_WORD=${SOC_DED_WORD:-}

# BOOT_CORRUPT reaches flow/gen_boot_image.py through build_sw_soc.sh
# and breaks one thing in one of the two image slots. `none` is the
# design; see that script for the modes.
export BOOT_CORRUPT=${BOOT_CORRUPT:-none}

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
if [ "$SOC_MEM_HARDEN" != 1 ]; then
  DEFPARAMS="$DEFPARAMS
  defparam tb_soc.dut.MEM_HARDEN = $SOC_MEM_HARDEN;"
fi
if [ -n "$SOC_SCRUB_IVL" ]; then
  DEFPARAMS="$DEFPARAMS
  defparam tb_soc.dut.SCRUB_IVL_RST = $SOC_SCRUB_IVL;"
fi
# SOC_CLKGATE, docs/76: soc_top.v's CLKGATE, the fabric's and the
# accelerator's clock gates. 0 is the ungated build the bit-exact
# equivalence of docs/76 section 6 is measured against; the design ships
# 1 and sw/tests enforces it.
SOC_CLKGATE=${SOC_CLKGATE:-1}
if [ "$SOC_CLKGATE" != 1 ]; then
  DEFPARAMS="$DEFPARAMS
  defparam tb_soc.dut.CLKGATE = $SOC_CLKGATE;"
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

# tb_soc.v's power-up model and its fault injector reach into the RAM's
# CHECK FIELD, which exists only in the codec arm. A hierarchical name
# that does not resolve is an elaboration error, so the block is behind
# a define and the define follows SOC_MEM_HARDEN rather than being set
# by hand.
if [ "$SOC_MEM_HARDEN" != 0 ]; then
  RAM_POWERUP_DEF=-DRAM_POWERUP_ECC
else
  RAM_POWERUP_DEF=
fi

# The testbench's own give-up bound. It defaults to tb_soc.v's 5,000,000
# and is set down for the runs docs/68 expects NOT to terminate -- the
# NOBOOT strap and the unbootable device, both of which end in a reset
# loop that is the CORRECT behaviour and would otherwise cost an hour of
# simulation to observe.
SOC_TIMEOUT_CYCLES=${SOC_TIMEOUT_CYCLES:-}
if [ -n "$SOC_TIMEOUT_CYCLES" ]; then
  TIMEOUT_DEF="-DTIMEOUT_CYCLES=$SOC_TIMEOUT_CYCLES"
else
  TIMEOUT_DEF=
fi

SW_DEFINES=${SW_DEFINES:-}
# shellcheck disable=SC2086
"$SOC_DIR/flow/build_sw_soc.sh" "$OUT" "-DUART_SCALER_VAL=${UART_SCALER}u" $SW_DEFINES

# Symbol addresses come out of the ELF that was just built rather than
# being written down here, so neither file carries a constant that goes
# stale the next time the program is edited.
#
# THEY COME OUT OF THE APPLICATION'S ELF AND NOT THE ROM'S, since
# docs/68. exit_code, exit_magic and the trap records are the PROGRAM's
# symbols and the program now runs from RAM out of a flash image; the
# ROM holds the loader, whose symbols the testbench never reads.
NM=$SOC_DIR/tools/rvgcc/bin/riscv-none-elf-nm
sym () {
  local a
  a=$("$NM" "$OUT/app.elf" | awk -v s="$1" '$3 == s { print $1 }')
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
//   SOC_MEM_HARDEN=$SOC_MEM_HARDEN  SOC_SCRUB_IVL=${SOC_SCRUB_IVL:-default}
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
  ${TIMEOUT_DEF} \
  ${RAM_POWERUP_DEF} \
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
  "$SOC_DIR/rtl/soc_mem_ecc.v" \
  "$SOC_DIR/rtl/soc_scrub.v" \
  "$SOC_DIR/rtl/soc_boot.v" \
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
check_arm SOC_MEM_HARDEN "$SOC_MEM_HARDEN" g_ecc g_plain "memory codec"
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
VVP_ARGS=(+flash0="$OUT/flash0.hex" +strap="$SOC_STRAP")
if [ "$SOC_RAM_RANDOM" != 0 ]; then
  VVP_ARGS+=(+ram_random="$SOC_RAM_RANDOM")
fi
if [ -n "$SOC_DED_WORD" ]; then
  VVP_ARGS+=(+ded_word="$SOC_DED_WORD")
fi
# Anything else the testbench understands, unparsed: +errtrace, +trace,
# +bustrace, +vcd. They are observations and none of them changes the
# design, so they get one pass-through rather than one variable each.
# shellcheck disable=SC2206
[ -n "${SOC_VVP_ARGS:-}" ] && VVP_ARGS+=(${SOC_VVP_ARGS})
"$VVP" "$OUT/tb_soc.vvp" "${VVP_ARGS[@]}" 2>&1 | tee "$OUT/sim.log"

grep -q "^\[TB\] PASS" "$OUT/sim.log" || {
  echo "== SoC SIMULATION FAILED" >&2; exit 1; }
echo "== soc: PASS"
