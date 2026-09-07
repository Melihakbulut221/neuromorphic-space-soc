#!/usr/bin/env bash
# Build the gate-level core fault-injection bench of docs/74 and
# elaborate it ONCE.
#
#   fi_core_gl.sh <netlist.v> <rtl_build_dir> [out_dir]
#
# `netlist.v` is a mapped soc_top -- the sign-off layout's
# `final/nl/soc_top.nl.v` -- and `rtl_build_dir` is a directory
# hw/soc/flow/fi_core.sh wrote for the SAME configuration, whose
# workload image, ELF symbols and site table this build reuses so the
# two benches run the same bytes and publish the same words. Nothing
# from the RTL build is simulated here: the design under test is the
# netlist, the sg13g2 cell models and the RM_IHPSG13 macro models, all
# resolved out of the pinned PDK.
#
# ICARUS 13, NOT THE PINNED oss-cad-suite ICARUS 12. docs/24 section 3
# measured why: Icarus 12 leaves sg13g2_dfrbpq_1's delayed_CLK undriven,
# so every flip-flop in the netlist clocks on z and a campaign reports
# 100 % MASKED on a dead design. hw/tb/Makefile.gl carries the same
# guard for the pilot; this script carries it for the SoC.
#
# The SRAM macros are compiled with -DFUNCTIONAL, which selects the
# PDK's zero-delay behavioural core (SRAM_1P_behavioral_bm_bist) and
# leaves out the specify block and its delayed-pin wrapper.

set -euo pipefail

SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PILOT_RTL=$(cd "$SOC_DIR/../rtl" && pwd)
NETLIST=${1:?netlist.v}
RTL_BUILD=${2:?rtl build dir}
OUT=${3:-$SOC_DIR/out/fi-core-gl}

# Absolute, all three: the ROM image's path is baked into the compiled
# object by -DROM_HEX, and a relative one resolves against wherever vvp
# happens to be started.
NETLIST=$(cd "$(dirname "$NETLIST")" && pwd)/$(basename "$NETLIST")
RTL_BUILD=$(cd "$RTL_BUILD" && pwd)
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)

UART_SCALER=${UART_SCALER:-0}
UART_BIT_CYCLES=$(( 8 * (UART_SCALER + 1) ))

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${SG13G2_VLOG:?}" "${SG13G2_SRAM_DIR:?}"

GL_IVERILOG=${GL_IVERILOG:-$HOME/.local/opt/iverilog13/usr/bin/iverilog}
[ -x "$GL_IVERILOG" ] || { echo "no Icarus 13 at $GL_IVERILOG" >&2; exit 1; }
major=$("$GL_IVERILOG" -V 2>/dev/null | sed -n '1s/.*version \([0-9]*\).*/\1/p')
[ "${major:-0}" -ge 13 ] || {
  echo "$GL_IVERILOG is Icarus $major; the gate-level bench needs >= 13" >&2
  echo "(Icarus 12 clocks every sg13g2 flip-flop on z: docs/24 section 3)" >&2
  exit 1; }
GL_VVP=$(dirname "$GL_IVERILOG")/vvp

SRAM_V=$SG13G2_SRAM_DIR/verilog
for f in "$SRAM_V/RM_IHPSG13_1P_2048x64_c2_bm_bist.v" \
         "$SRAM_V/RM_IHPSG13_1P_1024x32_c2_bm_bist.v" \
         "$SRAM_V/RM_IHPSG13_1P_core_behavioral_bm_bist.v" \
         "$SG13G2_VLOG" "$NETLIST" \
         "$RTL_BUILD/fi_workload.hex" "$RTL_BUILD/fi_workload.elf"; do
  [ -f "$f" ] || { echo "missing $f" >&2; exit 1; }
done

mkdir -p "$OUT"

# The flip-flop list and the force/release cases, from the netlist.
python3 "$SOC_DIR/fi/gl_netlist.py" "$NETLIST" \
  --emit "$OUT/fi_gl_sites.vh" --list "$OUT/flops.tsv"
cp "$RTL_BUILD/fi_workload.hex" "$OUT/fi_workload.hex"

# Provenance, written beside the build so a record names its bytes.
{
  echo "netlist   $NETLIST"
  echo "netlist md5 $(md5sum < "$NETLIST" | cut -c1-32)"
  echo "netlist size $(wc -c < "$NETLIST")"
  echo "cells     $SG13G2_VLOG"
  echo "cells md5 $(md5sum < "$SG13G2_VLOG" | cut -c1-32)"
  echo "sram      $SRAM_V"
  echo "rtl build $RTL_BUILD"
  echo "rom hex md5 $(md5sum < "$RTL_BUILD/fi_workload.hex" | cut -c1-32)"
  echo "iverilog  $GL_IVERILOG ($("$GL_IVERILOG" -V 2>/dev/null | head -1))"
  echo "flops     $(($(wc -l < "$OUT/flops.tsv") - 1))"
} > "$OUT/provenance.txt"
cat "$OUT/provenance.txt"

NM=$SOC_DIR/tools/rvgcc/bin/riscv-none-elf-nm
sym () {
  local a
  a=$("$NM" "$RTL_BUILD/fi_workload.elf" | awk -v s="$1" '$3 == s { print $1 }')
  [ -n "$a" ] || { echo "symbol not found: $1" >&2; exit 1; }
  echo "32'h$a"
}

# The register-file shadow (fi_gl_rf.vh) exists only once gl_map.py has
# derived the mapping; the bench compiles without it and reports
# rf_sec = -1 until then.
RF_DEFINE=()
[ -f "$OUT/fi_gl_rf.vh" ] && RF_DEFINE=(-DFI_GL_RF)
# The watchdog voter shadow (fi_gl_wdog.vh, gl_netlist.py --emit-wdog),
# the same way.
[ -f "$OUT/fi_gl_wdog.vh" ] && RF_DEFINE+=(-DFI_GL_WDOG)

"$GL_IVERILOG" -g2005-sv -o "$OUT/tb_soc_fi_gl.vvp" \
  -I "$OUT" \
  -DFUNCTIONAL \
  -DROM_HEX="\"$OUT/fi_workload.hex\"" \
  -DROM_INIT_WORD=32 \
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
  ${RF_DEFINE+"${RF_DEFINE[@]}"} \
  -s tb_soc_fi_gl \
  "$SOC_DIR/tb/tb_soc_fi_gl.v" \
  "$SOC_DIR/tb/fi_rf_shadow.v" \
  "$PILOT_RTL/secded_dec.v" \
  "$NETLIST" \
  "$SG13G2_VLOG" \
  "$SRAM_V/RM_IHPSG13_1P_2048x64_c2_bm_bist.v" \
  "$SRAM_V/RM_IHPSG13_1P_1024x32_c2_bm_bist.v" \
  "$SRAM_V/RM_IHPSG13_1P_core_behavioral_bm_bist.v" \
  2>&1 | tee "$OUT/iverilog.log"

echo "vvp $GL_VVP" >> "$OUT/provenance.txt"
echo "== elaborated $OUT/tb_soc_fi_gl.vvp (shadow: ${RF_DEFINE[*]:-absent})"
