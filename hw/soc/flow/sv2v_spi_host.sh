#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

# Convert OpenTitan's spi_host -- the docs/03 QSPI candidate -- from
# SystemVerilog to Verilog-2005 with the pinned sv2v, then prove the
# output elaborates in Icarus and synthesises in Yosys. docs/65.
#
#   sv2v_spi_host.sh [out_dir]          default hw/soc/gen_spi_host
#
# WHAT THIS ANSWERS. docs/38 section 10 item 7: "The docs/03 OpenTitan
# spi_host claim is untested. This document only establishes that sv2v
# carries Ibex. The SPI host shares the dependency and has not been
# through it." And docs/03 section 2.4: the CPU and the QSPI candidate
# "share one toolchain dependency; if the sv2v path is rejected during
# CPU bring-up, both fall back together ... and should be resolved by a
# single early prototype milestone." This script is that milestone for
# the second half.
#
# WHAT IT DOES, in the order the evidence is produced:
#
#   1. Computes the module closure of spi_host.sv by reading
#      instantiations out of the source -- 51 modules across
#      hw/ip/spi_host, hw/ip/tlul and hw/ip/prim{,_generic} -- rather
#      than trusting a hand-written list. A module the closure reaches
#      and the checkout lacks is an error here, not a missing-module
#      error three tools later.
#   2. Runs sv2v ONCE over the package list and the whole closure, the
#      same defines and include paths flow/sv2v_ibex.sh uses, into one
#      Verilog-2005 file. Ibex is converted one file at a time because
#      upstream's script does; this closure is converted together
#      because sv2v resolves package-scoped types across files and the
#      TileLink struct ports are exactly that.
#   3. Applies ONE mechanical rewrite to the GENERATED file, and states
#      it: sv2v renders the unpacked-array parameter default
#      `'{NumRegs{0}}` (spi_host.sv, spi_host_reg_top.sv, the RACL
#      policy vector) as `{NumRegs {0}}`, a replication of an UNSIZED
#      literal, which IEEE 1364-2005 does not allow and Icarus refuses
#      ("Concatenation operand "'sd0" has indefinite width"). Yosys
#      accepts it. The rewrite gives the literal a width. Patches to
#      OpenTitan: zero -- the same rule docs/63 applied to Ibex's RVFI
#      declaration and for the same reason: the checkout stays the
#      commit tools.soc.mk names.
#   4. Elaborates the result in Icarus with spi_host as the root and
#      NumCS = 2 (docs/03: "QSPI memory controller, 2 chip selects"),
#      under -g2005 as well as -g2005-sv, so the claim "Verilog-2005"
#      is checked by the strict front end and not only the permissive
#      one.
#   5. Synthesises it with the recipe flow/syn_soc.sh uses -- same
#      liberty, same corner, same abc constraint, same 20 ns target --
#      so its area is comparable with every block number in docs/39
#      onward, and reports cells, flip-flops and area.
#
# WHAT IT DOES NOT DO. It does not simulate a transaction, write a
# bridge, or connect anything to the SoC. It establishes that the
# candidate can be fetched, pinned, converted, elaborated and measured
# by this project's tools, which is the precondition docs/03 said had
# to be met before the block was chosen -- and it puts a measured area
# on the choice, which docs/65 section 5 reads.

set -euo pipefail

SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT=${1:-$SOC_DIR/gen_spi_host}
NUM_CS=${NUM_CS:-2}
PERIOD_NS=${SOC_PERIOD_NS:-20}

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${SV2V:?}" "${IVERILOG:?}" "${YOSYS:?}" "${SG13G2_TYP:?}" \
  "${OPENTITAN_DIR:?}" "${OPENTITAN_COMMIT:?}"

OT=$OPENTITAN_DIR
[ -f "$OT/hw/ip/spi_host/rtl/spi_host.sv" ] || {
  echo "OpenTitan not fetched: make -f hw/soc/tools.soc.mk fetch-opentitan" >&2
  exit 1; }
HEAD_COMMIT=$(git -C "$OT" rev-parse HEAD)
[ "$HEAD_COMMIT" = "$OPENTITAN_COMMIT" ] || {
  echo "OpenTitan checkout is at $HEAD_COMMIT, tools.soc.mk pins $OPENTITAN_COMMIT" >&2
  exit 1; }
[ -z "$(git -C "$OT" status --porcelain)" ] || {
  echo "OpenTitan checkout is dirty; it is a fetched tree, not a place to edit" >&2
  exit 1; }

rm -rf "$OUT"; mkdir -p "$OUT"

# ---- 1. the closure ---------------------------------------------------
python3 - "$OT" > "$OUT/closure.txt" <<'PY'
import re, sys, pathlib
OT = pathlib.Path(sys.argv[1])
dirs = [OT/"hw/ip/spi_host/rtl", OT/"hw/ip/prim/rtl", OT/"hw/ip/prim_generic/rtl",
        OT/"hw/ip/tlul/rtl", OT/"hw/ip/spi_device/rtl", OT/"hw/top_earlgrey/rtl",
        OT/"hw/top_earlgrey/rtl/autogen"]
def find(mod):
    for d in dirs:
        p = d / f"{mod}.sv"
        if p.is_file():
            return p
    return None
inst_re = re.compile(
    r"^\s*((?:prim|tlul|spi_host|spi_device)_[a-z0-9_]+)\s*"
    r"(?:#\s*\(|\b[a-z_][a-z0-9_]*\s*\()", re.M)
todo, seen, missing = ["spi_host"], {}, []
while todo:
    m = todo.pop()
    if m in seen:
        continue
    p = find(m)
    if p is None:
        missing.append(m); seen[m] = None; continue
    seen[m] = p
    txt = "\n".join(l for l in p.read_text().splitlines()
                    if not l.strip().startswith("//"))
    for x in inst_re.findall(txt):
        if x != m and not x.endswith("_pkg") and not x.endswith("_t"):
            todo.append(x)
if missing:
    sys.exit("modules the closure reaches and the checkout lacks: %s" % missing)
for m, p in sorted(seen.items()):
    print(p.relative_to(OT))
PY
N_MODS=$(wc -l < "$OUT/closure.txt")
echo "== closure: $N_MODS modules"

# The packages, in dependency order. Found by iterating sv2v's "could
# not find package" until it stopped, then frozen here so the run is
# deterministic.
PKGS=(
  hw/top_earlgrey/rtl/top_pkg.sv
  hw/ip/prim/rtl/prim_util_pkg.sv
  hw/ip/prim/rtl/prim_mubi_pkg.sv
  hw/ip/prim/rtl/prim_secded_pkg.sv
  hw/ip/prim/rtl/prim_subreg_pkg.sv
  hw/ip/prim/rtl/prim_alert_pkg.sv
  hw/ip/prim/rtl/prim_esc_pkg.sv
  hw/ip/prim/rtl/prim_count_pkg.sv
  hw/ip/prim/rtl/prim_cipher_pkg.sv
  hw/ip/prim_generic/rtl/prim_ram_1p_pkg.sv
  hw/ip/tlul/rtl/tlul_pkg.sv
  hw/top_earlgrey/rtl/autogen/top_racl_pkg.sv
  hw/ip/spi_device/rtl/spi_device_reg_pkg.sv
  hw/ip/spi_device/rtl/spi_device_pkg.sv
  hw/ip/spi_host/rtl/spi_host_reg_pkg.sv
  hw/ip/spi_host/rtl/spi_host_cmd_pkg.sv
)
for p in "${PKGS[@]}"; do
  [ -f "$OT/$p" ] || { echo "package missing from checkout: $p" >&2; exit 1; }
done

# ---- 2. sv2v ------------------------------------------------------------
echo "== sv2v $($SV2V --version): ${#PKGS[@]} packages + $N_MODS modules"
"$SV2V" --define=SYNTHESIS --define=YOSYS \
  -I"$OT/hw/ip/prim/rtl" -I"$OT/hw/dv/sv/dv_utils" \
  $(for p in "${PKGS[@]}"; do echo "$OT/$p"; done) \
  $(sed "s|^|$OT/|" "$OUT/closure.txt") \
  > "$OUT/spi_host_raw.v"
N_OUT=$(grep -c '^module ' "$OUT/spi_host_raw.v")
echo "== sv2v output: $N_OUT modules, $(wc -l < "$OUT/spi_host_raw.v") lines"
[ "$N_OUT" -ge "$N_MODS" ] || {
  echo "sv2v emitted $N_OUT modules for a closure of $N_MODS" >&2; exit 1; }

# ---- 3. the one rewrite, applied and counted ---------------------------
sed -e "s/{spi_host_reg_pkg_NumRegs {0}}/{spi_host_reg_pkg_NumRegs {1'b0}}/" \
  "$OUT/spi_host_raw.v" > "$OUT/spi_host.v"
N_FIX=$(diff "$OUT/spi_host_raw.v" "$OUT/spi_host.v" | grep -c '^>' || true)
echo "== rewrite: $N_FIX line(s) changed in the generated file (patches to OpenTitan: 0)"
[ "$N_FIX" -gt 0 ] || {
  echo "the rewrite matched nothing: upstream or sv2v changed and this" >&2
  echo "script's one documented fixup is stale" >&2; exit 1; }

# ---- 4. elaboration, strict and permissive -----------------------------
for std in 2005 2005-sv; do
  "$IVERILOG" -g$std -s spi_host -Pspi_host.NumCS=$NUM_CS \
    -o "$OUT/spi_host_$std.vvp" "$OUT/spi_host.v" 2>&1 | tee "$OUT/iverilog_$std.log"
  [ -s "$OUT/spi_host_$std.vvp" ] || {
    echo "== Icarus -g$std did not elaborate spi_host" >&2; exit 1; }
  echo "== Icarus -g$std: elaborated spi_host, NumCS=$NUM_CS"
done

# ---- 5. synthesis, flow/syn_soc.sh's recipe -----------------------------
cat > "$OUT/abc.constr" <<EOF
set_driving_cell sg13g2_buf_4
set_load 0.005
EOF
cat > "$OUT/syn.ys" <<EOF
read_liberty -lib $SG13G2_TYP
read_verilog $OUT/spi_host.v
chparam -set NumCS $NUM_CS spi_host
hierarchy -check -top spi_host
synth -flatten -top spi_host
opt -purge
dfflibmap -liberty $SG13G2_TYP
opt
abc -liberty $SG13G2_TYP -constr $OUT/abc.constr -D $PERIOD_NS
attrmap -modattr -remove keep_hierarchy
flatten
setundef -zero
opt_clean -purge
write_verilog -noattr $OUT/spi_host.netlist.v
check
tee -o $OUT/area.rpt stat -liberty $SG13G2_TYP
EOF
"$YOSYS" -q -l "$OUT/syn.log" -s "$OUT/syn.ys" > /dev/null
awk -v top="spi_host NumCS=$NUM_CS" -v ge=7.2576 '
  $NF == "cells"                      { cells = $1 }
  $NF ~ /^sg13g2_(s?df|dl[hl])/       { ff += $1 }
  /Chip area for module/              { gsub(/[^0-9.]/, "", $NF); area = $NF + 0 }
  END {
    printf "%-22s cells=%-6d flops=%-6d area_um2=%.4f  kGE=%.3f\n",
           top, cells, ff, area, area / ge / 1000.0
  }
' "$OUT/area.rpt"
echo "  report: $OUT/area.rpt   netlist: $OUT/spi_host.netlist.v   log: $OUT/syn.log"
echo "  opentitan @ $HEAD_COMMIT"
