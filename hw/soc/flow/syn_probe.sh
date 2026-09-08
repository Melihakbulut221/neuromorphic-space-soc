#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

# Synthesise one module from hw/soc/rtl/probe/ onto ihp-sg13g2 and report
# its cell count, flip-flop count and cell area.
#
#   syn_probe.sh <top_module> [out_dir]
#
# Works for any module in hw/soc/rtl/probe/, e.g.
#
#   flow/syn_probe.sh ibex2ahbl
#   flow/syn_probe.sh ahbl_interconnect
#   flow/syn_probe.sh ahbl_arbiter
#   flow/syn_probe.sh ahbl2apb
#   flow/syn_probe.sh probe_ahbl_top
#
# The Yosys recipe is the same one syn_ibex.sh drives through
# syn/ibex_syn.ys.in: map at the typical corner, dfflibmap, abc with the
# same drive/load constraint and the same delay target, then flatten,
# setundef -zero, opt_clean -purge, stat -liberty. The delay target
# defaults to 20 ns, which is what hw/soc/out/small-pmp was synthesised
# with, so the areas are comparable with the Ibex numbers. Override with
# PROBE_PERIOD_NS.
#
# The Ibex-specific parts of that recipe are deliberately absent: there
# is no chparam block (these modules take their parameter defaults) and
# no keep_hierarchy anchors (there is no deliberate redundancy here to
# protect from the optimiser).
#
# Everything under hw/soc/rtl/probe/ is a COST PROBE. It is synthesised
# and area-measured only, it is not functionally verified in any way, and
# it is not instantiated in the SoC.

set -euo pipefail

TOP=${1:?top module name, e.g. probe_ahbl_top}
SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PROBE_DIR=$SOC_DIR/rtl/probe
OUT=${2:-$SOC_DIR/out/probe/$TOP}
PERIOD_NS=${PROBE_PERIOD_NS:-20}

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${YOSYS:?}" "${SG13G2_TYP:?}"

test -d "$PROBE_DIR" || { echo "no such directory: $PROBE_DIR" >&2; exit 2; }
test -n "$(echo "$PROBE_DIR"/*.v)" || { echo "no sources in $PROBE_DIR" >&2; exit 2; }

rm -rf "$OUT"; mkdir -p "$OUT"

cat > "$OUT/abc.constr" <<EOF
set_driving_cell sg13g2_buf_4
set_load 0.005
EOF

cat > "$OUT/probe_syn.ys" <<EOF
read_liberty -lib $SG13G2_TYP

read_verilog -defer $PROBE_DIR/*.v

hierarchy -check -top $TOP

synth -flatten -top $TOP
opt -purge

dfflibmap -liberty $SG13G2_TYP
opt
abc -liberty $SG13G2_TYP -constr $OUT/abc.constr -D $PERIOD_NS

flatten
setundef -zero
opt_clean -purge

write_verilog -noattr $OUT/$TOP.netlist.v

check
tee -o $OUT/area.rpt stat -liberty $SG13G2_TYP
EOF

"$YOSYS" -l "$OUT/syn.log" -s "$OUT/probe_syn.ys" > /dev/null

# ---- report ---------------------------------------------------------------
# Flip-flops are counted from the mapped cell histogram: every sequential
# cell in sg13g2 has a name starting with sg13g2_df or sg13g2_sdf.
awk -v top="$TOP" -v ge=7.2576 '
  $NF == "cells"                      { cells = $1 }
  $NF ~ /^sg13g2_(s?df|dl[hl])/       { ff += $1 }
  /Chip area for module/              { gsub(/[^0-9.]/, "", $NF); area = $NF + 0 }
  END {
    printf "%-22s cells=%-6d flops=%-6d area_um2=%.4f  kGE=%.3f\n",
           top, cells, ff, area, area / ge / 1000.0
  }
' "$OUT/area.rpt"

echo "  report: $OUT/area.rpt   netlist: $OUT/$TOP.netlist.v   log: $OUT/syn.log"
