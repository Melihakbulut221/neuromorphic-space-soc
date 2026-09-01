#!/usr/bin/env bash
# Census the core's flip-flops, and say which of them the campaign's
# site list reaches.
#
#   fi_coverage.sh [out_dir]
#
# WHY THIS EXISTS.  `hw/soc/fi/targets.py` is a list a person wrote, and
# a list a person wrote is a list a person can leave something off.  The
# way a structure comes to be unmeasured in this repository has twice
# been an omission rather than a decision -- docs/41 section 8 says so
# in the test that checks its own target list is complete -- and the
# campaign's own honesty checks cannot catch that class: they verify
# that every site it names elaborates, not that every flip-flop that
# elaborates is named.
#
# So this asks the other question.  Yosys elaborates `ibex_top` at
# soc_top.v's exact parameters, flattens it, and reports every
# flip-flop that survives, by the name of the signal it stores.  The
# Python at the end attributes each one to a campaign site, or reports
# it as uncovered.  What comes out is a coverage figure and, more
# usefully, the list of what is NOT in the campaign -- which docs/42
# section 9 quotes rather than paraphrases.
#
# It is a census of the RTL, not of the netlist.  Synthesis may merge,
# duplicate or delete flip-flops after this point; docs/38 section 8.4
# counts 2,106 in the mapped `small-pmp` netlist and section 4.2 of
# docs/42 is where the two numbers are put side by side.

set -euo pipefail

SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT=${1:-$SOC_DIR/out/fi-core}

# The same source list the campaign elaborates, with the register file
# selected by IBEX_REGFILE. A census of the upstream core against a site
# list written for the hardened one would report 248 uncovered
# flip-flops that do not exist, or none that do.
# shellcheck source=hw/soc/flow/ibex_sources.sh
. "$SOC_DIR/flow/ibex_sources.sh"

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${YOSYS:?}" "${SG13G2_TYP:?}"

mkdir -p "$OUT"

# The parameters are soc_top.v's, in the integer encodings of
# ext/ibex/rtl/ibex_pkg.sv -- the same ones hw/soc/flow/syn_ibex.sh
# passes for `small-pmp` and the same ones the testbench elaborates.
# Enum names do not survive sv2v (docs/38 section 4.4), so a wrong
# integer here would silently census a different core.
cat > "$OUT/fi_flops.ys" <<EOF
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
opt_dff
opt_clean
select -set flops t:\$adff t:\$adffe t:\$dff t:\$dffe t:\$sdff t:\$sdffe t:\$dffsr %u
dump -o $OUT/fi_flops.il @flops
stat
EOF

"$YOSYS" -q -s "$OUT/fi_flops.ys" > "$OUT/fi_flops.log" 2>&1 || {
  echo "yosys failed; see $OUT/fi_flops.log" >&2; exit 1; }

FI_REGFILE=${IBEX_REGFILE:-secded} \
  python3 "$SOC_DIR/fi/coverage.py" "$OUT/fi_flops.il" \
  | tee "$OUT/fi_coverage.txt"
