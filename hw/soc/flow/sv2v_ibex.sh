#!/usr/bin/env bash
# Convert the pinned Ibex checkout from SystemVerilog to Verilog-2005.
#
# This is a re-implementation of hw/soc/ext/ibex/syn/syn_yosys.sh's sv2v
# stage, not a call into it, for three reasons recorded in docs/38:
#
#  1. The upstream script sources syn_setup.sh, which upstream ships
#     without the cell-library variables set (they are exported by a Nix
#     devShell this project does not use), and hardwires Nangate45.
#  2. Upstream deletes the flip-flop register file and keeps the
#     latch-based one. This project keeps the flip-flop register file --
#     every architectural state element must be a nameable flop for the
#     fault-injection flow (docs/03 rule 1).
#  3. Upstream's output directory is timestamped; this project needs a
#     fixed path that a Makefile and a git status can both reason about.
#
# The sv2v invocation itself -- the defines, the package list, the
# include paths, and the prim_* -> prim_generic_* renaming -- is
# upstream's, verbatim, because that is the part being evaluated.
#
# Usage: sv2v_ibex.sh <ibex_dir> <out_dir> <sv2v_binary>

set -euo pipefail

IBEX_DIR=$(readlink -f "${1:?ibex dir}")
OUT_DIR=$(readlink -f "${2:?out dir}")
SV2V=$(readlink -f "${3:?sv2v binary}")

RTL="$IBEX_DIR/rtl"
VEN="$IBEX_DIR/vendor/lowrisc_ip"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

DEP_SOURCES=(
  "$VEN/ip/prim/rtl/prim_count.sv"
  "$VEN/ip/prim/rtl/prim_secded_inv_39_32_dec.sv"
  "$VEN/ip/prim/rtl/prim_secded_inv_39_32_enc.sv"
  "$VEN/ip/prim/rtl/prim_lfsr.sv"
  "$VEN/ip/prim_generic/rtl/prim_and2.sv"
  "$VEN/ip/prim_generic/rtl/prim_buf.sv"
  "$VEN/ip/prim_generic/rtl/prim_clock_mux2.sv"
  "$VEN/ip/prim_generic/rtl/prim_flop.sv"
)

fixup () {
  # Upstream: resolve the abstract prim_* wrappers onto the generic
  # implementations, which is what sv2v emits module bodies for.
  sed -i \
    -e 's/prim_and2/prim_generic_and2/g' \
    -e 's/prim_buf/prim_generic_buf/g' \
    -e 's/prim_clock_mux2/prim_generic_clock_mux2/g' \
    -e 's/prim_flop/prim_generic_flop/g' \
    "$1"
}

echo "== sv2v: vendored primitives"
for file in "${DEP_SOURCES[@]}"; do
  module=$(basename -s .sv "$file")
  "$SV2V" \
    --define=SYNTHESIS --define=YOSYS \
    "$VEN/ip/prim/rtl/prim_count_pkg.sv" \
    "$VEN/ip/prim/rtl/prim_cipher_pkg.sv" \
    -I"$VEN/ip/prim/rtl" \
    "$file" > "$OUT_DIR/${module}.v"
  fixup "$OUT_DIR/${module}.v"
done

echo "== sv2v: ibex core"
for file in "$RTL"/*.sv; do
  module=$(basename -s .sv "$file")
  case "$module" in *_pkg) continue;; esac
  "$SV2V" \
    --define=SYNTHESIS --define=YOSYS \
    "$RTL"/*_pkg.sv \
    "$VEN/ip/prim_generic/rtl/prim_ram_1p_pkg.sv" \
    "$VEN/ip/prim/rtl/prim_secded_pkg.sv" \
    "$VEN/ip/prim/rtl/prim_util_pkg.sv" \
    -I"$VEN/ip/prim/rtl" \
    -I"$VEN/dv/sv/dv_utils" \
    "$file" > "$OUT_DIR/${module}.v"
  fixup "$OUT_DIR/${module}.v"
done

# Not synthesised: the tracer is a simulation-only logger.
rm -f "$OUT_DIR/ibex_tracer.v" "$OUT_DIR/ibex_top_tracing.v"

# This project selects RegFileFF (ibex_pkg::RegFileFF = 0), so the
# latch-based and FPGA register files are removed instead of the FF one.
# See the header comment.
rm -f "$OUT_DIR/ibex_register_file_latch.v"
rm -f "$OUT_DIR/ibex_register_file_fpga.v"

echo "== sv2v output: $(ls "$OUT_DIR"/*.v | wc -l) files, $(cat "$OUT_DIR"/*.v | wc -l) lines"
