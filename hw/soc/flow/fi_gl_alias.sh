#!/usr/bin/env bash
# Every name each of the core's nets carries before synthesis chooses
# one -- docs/74.
#
#   fi_gl_alias.sh [out_dir]
#
# WHY.  The mapped netlist keeps ONE public name per net, and which one
# yosys keeps is whichever alias survived opt_clean: the IF/ID
# instruction register's bits come out named after the register file's
# read-address port, `mepc` after `crash_dump_o`, the CSRs after the
# wire their `rdata_o` drives.  hw/soc/fi/gl_map.py identifies most
# flip-flops by their per-cycle trace, but a register that never changes
# in the clean run has a trace that says nothing, and for those the only
# handle is a name.  This script produces the set of names each net had,
# so that "the netlist's `mie_q[3]` is the RTL's `u_mie_csr.rdata_q[3]`"
# is read out of the elaborated design rather than guessed.
#
# It is hw/soc/flow/fi_coverage.sh's elaboration -- the same sources,
# the same parameters, ibex_top flattened -- stopped before anything
# renames, with the design written as JSON.  gl_map.py --alias reads it.

set -euo pipefail

SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT=${1:-$SOC_DIR/out/fi-core-gl}
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)

# shellcheck source=hw/soc/flow/ibex_sources.sh
. "$SOC_DIR/flow/ibex_sources.sh"
eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${YOSYS:?}" "${SG13G2_TYP:?}"

cat > "$OUT/fi_alias.ys" <<YS
read_liberty -lib $SG13G2_TYP
read_verilog -defer $SOC_DIR/rtl/prim_clock_gating.v
read_verilog -defer $(ibex_sources "$SOC_DIR" | tr '\n' ' ')

chparam -set BaseIsa          0   ibex_top
chparam -set RV32E            0   ibex_top
chparam -set RV32M            2   ibex_top
chparam -set RV32B            0   ibex_top
chparam -set RV32ZC           0   ibex_top
chparam -set RegFile          0   ibex_top
chparam -set BranchTargetALU  0   ibex_top
chparam -set WritebackStage   0   ibex_top
chparam -set ICache           0   ibex_top
chparam -set ICacheECC        0   ibex_top
chparam -set ICacheScramble   0   ibex_top
chparam -set BranchPredictor  0   ibex_top
chparam -set DbgTriggerEn     0   ibex_top
chparam -set SecureIbex       0   ibex_top
chparam -set PMPEnable        1   ibex_top
chparam -set PMPGranularity   0   ibex_top
chparam -set PMPNumRegions    4   ibex_top
chparam -set MHPMCounterNum   0   ibex_top
chparam -set MHPMCounterWidth 40  ibex_top

hierarchy -check -top ibex_top
proc
flatten
opt_expr
opt_clean
write_json $OUT/fi_alias.json
YS

"$YOSYS" -q -s "$OUT/fi_alias.ys" > "$OUT/fi_alias.log" 2>&1 || {
  echo "yosys failed; see $OUT/fi_alias.log" >&2; exit 1; }
echo "== wrote $OUT/fi_alias.json ($(wc -c < "$OUT/fi_alias.json") bytes)"
