#!/usr/bin/env bash
# Measure the architectural register file on its own, five ways.
#
#   syn_regfile.sh [out_dir]
#
# WHY A SEPARATE SCRIPT AND WHY FOUR CONFIGURATIONS
#
# docs/41 section 6.5 records a measurement defect worth not repeating:
# the cost of a hardening was very nearly quoted against the number the
# PREVIOUS document had measured, which would have credited the
# hardening with a saving that a refactor in the same commit had made.
# The rule that came out of it is that the baseline has to be the same
# source, measured now, with only the thing being priced turned off.
#
# For a register file substituted into Ibex there are two candidate
# baselines and they are not the same:
#
#   upstream   hw/soc/gen/ibex_register_file_ff.v, the sv2v output of
#              the pinned Ibex. This is what the design contained
#              before docs/43 and what docs/38's 275,682.6198 um2
#              includes.
#   harden0    hw/soc/rtl/ibex_regfile_secded.v with HARDEN = 0. Same
#              file as the hardened build, same generate structure,
#              protection switched off.
#
# The difference between those two is THIS PROJECT'S REWRITE of a file
# it did not write, and it is not part of the cost of the protection.
# The difference between `harden0` and `harden1` is. Both are reported,
# and docs/43 section 7 quotes the second and names the first.
#
# `scrub0` is the third: correction on read with the walking write-back
# removed, so that what the scrub costs is separable from what the code
# costs.
#
# `slowcorr` is the fifth and it is docs/44's: HARDEN = 1 with
# FASTCORR = 0, which is the read path docs/43 shipped -- the frozen
# decoder's own `data_out`, its 64-wide OR, its subtract and its
# multiplexer. `harden1` is the same file with FASTCORR = 1. The pair is
# what prices docs/44 section 5's timing recovery in area, and the sign
# of the difference is not assumed in advance: replacing a multiplexer
# with thirty-two comparators can cost area as easily as save it.
#
# The recipe is syn_soc.sh's, which is syn_ibex.sh's: same liberty, same
# corner, same abc constraint file, same 20 ns delay target.

set -euo pipefail

SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# hw/rtl/secded_enc.v and hw/rtl/secded_dec.v are READ from here and
# never modified, exactly as hw/rtl/tmr_voter.v is.
PILOT_RTL=$(cd "$SOC_DIR/../rtl" && pwd)
OUT=${1:-$SOC_DIR/out/soc-syn/regfile}
PERIOD_NS=${SOC_PERIOD_NS:-20}

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${YOSYS:?}" "${SG13G2_TYP:?}"

[ -f "$SOC_DIR/gen/ibex_register_file_ff.v" ] || {
  echo "hw/soc/gen is empty: run flow/sv2v_ibex.sh first" >&2; exit 1; }

rm -rf "$OUT"; mkdir -p "$OUT"

cat > "$OUT/abc.constr" <<EOF
set_driving_cell sg13g2_buf_4
set_load 0.005
EOF

# The parameters ibex_top passes at soc_top.v's configuration. They are
# written here rather than left at the module defaults because a
# register file measured at the wrong DataWidth is a different register
# file, and because upstream's file and this project's have to be given
# the same ones or the comparison means nothing.
run () {
  local tag=$1 srcs=$2 params=$3
  cat > "$OUT/$tag.ys" <<EOF
read_liberty -lib $SG13G2_TYP
read_verilog -defer $srcs

chparam -set BaseIsa           0  ibex_register_file_ff
chparam -set RV32E             0  ibex_register_file_ff
chparam -set DataWidth        32  ibex_register_file_ff
chparam -set DummyInstructions 0  ibex_register_file_ff
$params

hierarchy -check -top ibex_register_file_ff
synth -flatten -top ibex_register_file_ff
opt -purge
dfflibmap -liberty $SG13G2_TYP
opt
abc -liberty $SG13G2_TYP -constr $OUT/abc.constr -D $PERIOD_NS
flatten
setundef -zero
opt_clean -purge
write_verilog -noattr $OUT/$tag.netlist.v
splitnets
clean
write_verilog -noattr -noexpr -nohex -nodec $OUT/$tag.sta.v
check
tee -o $OUT/$tag.area.rpt stat -liberty $SG13G2_TYP
EOF
  "$YOSYS" -l "$OUT/$tag.syn.log" -s "$OUT/$tag.ys" > /dev/null
  awk -v tag="$tag" -v ge=7.2576 '
    $NF == "cells"                { cells = $1 }
    $NF ~ /^sg13g2_(s?df|dl[hl])/ { ff += $1 }
    /Chip area for module/        { gsub(/[^0-9.]/, "", $NF); area = $NF + 0 }
    END {
      printf "%-10s cells=%-6d flops=%-6d area_um2=%.4f  kGE=%.3f\n",
             tag, cells, ff, area, area / ge / 1000.0
    }
  ' "$OUT/$tag.area.rpt"
}

SEC_SRCS="$SOC_DIR/rtl/ibex_regfile_secded.v $PILOT_RTL/secded_enc.v $PILOT_RTL/secded_dec.v"

run upstream "$SOC_DIR/gen/ibex_register_file_ff.v" ""
run harden0  "$SEC_SRCS" "chparam -set HARDEN 0 ibex_register_file_ff"
run scrub0   "$SEC_SRCS" "chparam -set HARDEN 1 ibex_register_file_ff
chparam -set SCRUB 0 ibex_register_file_ff"
run slowcorr "$SEC_SRCS" "chparam -set HARDEN 1 ibex_register_file_ff
chparam -set FASTCORR 0 ibex_register_file_ff"
run harden1  "$SEC_SRCS" "chparam -set HARDEN 1 ibex_register_file_ff"
# docs/44 section 5.5's alternative, measured rather than argued: the
# syndrome's XOR tree hoisted to the other side of the read multiplexer,
# at the cost of one parity tree per register. NOTHING BUILDS THIS; the
# row exists so that the trade is a pair of numbers.
run synpre   "$SEC_SRCS" "chparam -set HARDEN 1 ibex_register_file_ff
chparam -set SYNPRE 1 ibex_register_file_ff"

echo "  reports in $OUT"
