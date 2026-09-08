#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

# Synthesise one SoC block from hw/soc/rtl/ onto ihp-sg13g2 and report
# its cell count, flip-flop count and cell area.
#
#   syn_soc.sh <top_module> [out_dir]
#
# e.g.  flow/syn_soc.sh soc_bus
#       flow/syn_soc.sh soc_apb_bridge
#       flow/syn_soc.sh soc_uart
#       flow/syn_soc.sh soc_gpio
#       flow/syn_soc.sh soc_qspi
#       flow/syn_soc.sh soc_pnp
#       flow/syn_soc.sh soc_apb_pnp
#       flow/syn_soc.sh soc_clint
#       flow/syn_soc.sh soc_scrub
#       flow/syn_soc.sh soc_boot
#       flow/syn_soc.sh soc_mem_ecc         (the memory codec alone;
#                                            docs/67 section 5)
#       flow/syn_soc.sh soc_gptimer          (includes soc_wdog)
#       flow/syn_soc.sh soc_wdog
#       flow/syn_soc.sh soc_fabric_meas      (see below)
#
# Two environment variables, both additive and both off by default:
#
#   SOC_SYN_BLACKBOX   a space-separated list of modules to declare as
#                      black boxes before `hierarchy`. docs/51 section 11
#                      quotes "soc_npu, the connection only (pilot
#                      black-boxed)" and section 17's reproduction list
#                      had no way to produce that row; this is it:
#                        SOC_SYN_BLACKBOX=pilot_top flow/syn_soc.sh soc_npu
#                      The black box is ASSERTED and not assumed -- the
#                      script fails if the boxed module's own flip-flops
#                      turn up in the netlist, because `blackbox` on a
#                      module that has already been elaborated warns and
#                      exits zero, which is docs/49 section 8.1's shape.
#   SOC_CHPARAM        a `chparam` argument list applied before
#                      `hierarchy`, e.g. SOC_CHPARAM="-set HARDEN 0". It
#                      is what lets a hardened block's own unhardened
#                      configuration be measured with the identical
#                      recipe and the identical file list, which is the
#                      baseline docs/41 section 6.5 insists on: a
#                      baseline taken against an older file list credits
#                      the hardening with a refactor's saving.
#
# The recipe is deliberately identical to flow/syn_probe.sh's, which is
# itself syn_ibex.sh's: same liberty, same corner, same abc constraint
# file, same 20 ns delay target that hw/soc/out/small-pmp was
# synthesised with. That is the whole point -- the AHB cost probe under
# hw/soc/rtl/probe/ and the fabric that was actually built have to be
# measured the same way or the comparison in
# docs/39-soc-bus-and-memory-map.md section 6 means nothing.
#
# soc_fabric_meas is a MEASUREMENT WRAPPER, generated into the output
# directory rather than kept in hw/soc/rtl/. It instantiates soc_bus and
# soc_apb_bridge with every port brought out to the top, so the pair can
# be compared like for like against probe_ahbl_top, which contains the
# two Ibex-to-AHB bridges, the arbiter, the interconnect and the
# AHB-to-APB bridge. Bringing every port out is what stops the optimiser
# from deleting logic whose outputs go nowhere; the flop count in the
# report is the check that it did not.
#
# soc_mem.v and soc_top.v are excluded from the source list on purpose.
# soc_mem.v is a behavioural array standing in for an SRAM macro, so its
# area is a property of the model and not of the design; soc_top.v pulls
# in the whole of Ibex, which flow/syn_ibex.sh already measures.
#
# soc_top.v IS now measured, by flow/syn_soc_top.sh, which this script is
# not a substitute for and which is not a substitute for this one.
#
# ---------------------------------------------------------------------
# WHAT THIS SCRIPT MEASURES IS NOT ONLY THE BLOCK, and docs/45 section
# 4.3 is the measurement of that rather than a caution about it.
#
# Every SoC block is read into the design below and then one of them is
# selected as the top. Yosys is entitled to map a design differently when
# the design it was given is different, and it does:
#
#   soc_clint       reading soc_busstat.v, soc_tmr_bank.v and
#                   tmr_voter.v -- three files it does not instantiate --
#                   makes it 29.3328 um2 and 5 cells BIGGER.
#   soc_fabric_meas contains exactly soc_bus and soc_apb_bridge, neither
#                   of which has changed and both of which reproduce
#                   their own published numbers exactly. Editing
#                   soc_wdog.v and soc_gptimer.v moved it by 150.7464
#                   um2, 0.93 %. Restoring docs/40's whole source list
#                   reproduces docs/40's number to four decimal places.
#
# So a per-block area from this script reproduces against THE FILE LIST
# AS IT STOOD ON THE DAY, and not against the block. Every number in
# docs/39 section 6, docs/40 section 9, docs/41 section 6.5, docs/43
# section 7 and docs/44 section 7.2 inherits that. docs/45 section 9
# item 4 proposes the fix -- derive the list from the top -- and states
# why doing it is a decision about comparability rather than a tidy-up.
# ---------------------------------------------------------------------

set -euo pipefail

TOP=${1:?top module name, e.g. soc_bus}
SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
RTL=$SOC_DIR/rtl
# hw/rtl/tmr_voter.v is READ from here and never modified.
PILOT_RTL=$(cd "$SOC_DIR/../rtl" && pwd)
OUT=${2:-$SOC_DIR/out/soc-syn/$TOP}
PERIOD_NS=${SOC_PERIOD_NS:-20}

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${YOSYS:?}" "${SG13G2_TYP:?}"

for f in "$RTL/soc_memmap.vh" "$RTL/soc_pnp_rom.vh" "$RTL/soc_apb_pnp_rom.vh"; do
  [ -f "$f" ] || {
    echo "missing $f: run 'python regmap/generate_memmap.py' first" >&2
    exit 1; }
done

rm -rf "$OUT"; mkdir -p "$OUT"

# The measurement wrapper. Written here rather than tracked in rtl/
# because it is not part of the design: nothing instantiates it and
# nothing simulates it.
cat > "$OUT/soc_fabric_meas.v" <<'EOF'
// MEASUREMENT WRAPPER, generated by hw/soc/flow/syn_soc.sh.
// Not part of the design. soc_bus plus soc_apb_bridge with every port
// exposed, so the fabric can be area-compared like for like with
// hw/soc/rtl/probe/probe_ahbl_top.v.
`timescale 1ns / 1ps
module soc_fabric_meas (
    input  wire        clk_i, rst_ni,
    input  wire        mi_req_i,  input wire [31:0] mi_addr_i,
    output wire        mi_gnt_o, mi_rvalid_o, mi_err_o,
    output wire [31:0] mi_rdata_o,
    input  wire        md_req_i, md_we_i,
    input  wire [3:0]  md_be_i,
    input  wire [31:0] md_addr_i, md_wdata_i,
    output wire        md_gnt_o, md_rvalid_o, md_err_o,
    output wire [31:0] md_rdata_o,
    output wire [4:0]  s_req_o,
    output wire [31:0] s_addr_o, s_wdata_o,
    output wire        s_we_o,
    output wire [3:0]  s_be_o,
    input  wire [4:0]  s_gnt_i, s_rvalid_i, s_err_i,
    input  wire [31:0] s_rdata_0_i, s_rdata_1_i, s_rdata_3_i, s_rdata_4_i,
    input  wire [31:0] s_rdata_5_i,
    output wire        psel_o, penable_o, pwrite_o,
    output wire [19:0] paddr_o,
    output wire [31:0] pwdata_o,
    output wire [3:0]  pstrb_o,
    input  wire [31:0] prdata_i,
    input  wire        pready_i, pslverr_i
);
  wire [5:0] req, gnt, rvalid, err;
  wire [31:0] rdata_apb;
  wire abr_gnt, abr_rvalid, abr_err;

  assign s_req_o = {req[5], req[4], req[3], req[1], req[0]};
  assign gnt     = {s_gnt_i[4],    s_gnt_i[3],    s_gnt_i[2],    abr_gnt,
                    s_gnt_i[1],    s_gnt_i[0]};
  assign rvalid  = {s_rvalid_i[4], s_rvalid_i[3], s_rvalid_i[2], abr_rvalid,
                    s_rvalid_i[1], s_rvalid_i[0]};
  assign err     = {s_err_i[4],    s_err_i[3],    s_err_i[2],    abr_err,
                    s_err_i[1],    s_err_i[0]};

  soc_bus u_bus (
      .clk_i(clk_i), .rst_ni(rst_ni),
      .mi_req_i(mi_req_i), .mi_addr_i(mi_addr_i), .mi_gnt_o(mi_gnt_o),
      .mi_rvalid_o(mi_rvalid_o), .mi_rdata_o(mi_rdata_o), .mi_err_o(mi_err_o),
      .md_req_i(md_req_i), .md_addr_i(md_addr_i), .md_we_i(md_we_i),
      .md_be_i(md_be_i), .md_wdata_i(md_wdata_i), .md_gnt_o(md_gnt_o),
      .md_rvalid_o(md_rvalid_o), .md_rdata_o(md_rdata_o), .md_err_o(md_err_o),
      .s_req_o(req), .s_addr_o(s_addr_o), .s_we_o(s_we_o), .s_be_o(s_be_o),
      .s_wdata_o(s_wdata_o), .s_gnt_i(gnt), .s_rvalid_i(rvalid),
      .s_rdata_0_i(s_rdata_0_i), .s_rdata_1_i(s_rdata_1_i),
      .s_rdata_2_i(rdata_apb),   .s_rdata_3_i(s_rdata_3_i),
      .s_rdata_4_i(s_rdata_4_i), .s_rdata_5_i(s_rdata_5_i),
      .s_err_i(err)
  );

  soc_apb_bridge u_apb (
      .clk_i(clk_i), .rst_ni(rst_ni),
      .req_i(req[2]), .addr_i(s_addr_o), .we_i(s_we_o), .be_i(s_be_o),
      .wdata_i(s_wdata_o), .gnt_o(abr_gnt), .rvalid_o(abr_rvalid),
      .rdata_o(rdata_apb), .err_o(abr_err),
      .psel_o(psel_o), .penable_o(penable_o), .paddr_o(paddr_o),
      .pwrite_o(pwrite_o), .pwdata_o(pwdata_o), .pstrb_o(pstrb_o),
      .prdata_i(prdata_i), .pready_i(pready_i), .pslverr_i(pslverr_i)
  );
endmodule
EOF

cat > "$OUT/abc.constr" <<EOF
set_driving_cell sg13g2_buf_4
set_load 0.005
EOF

cat > "$OUT/soc_syn.ys" <<EOF
read_liberty -lib $SG13G2_TYP

read_verilog -I$RTL -I$PILOT_RTL -defer $RTL/soc_bus.v $RTL/soc_apb_bridge.v \
                          $RTL/soc_uart.v $RTL/soc_gpio.v $RTL/soc_qspi.v \
                          $RTL/soc_pnp.v $RTL/soc_apb_pnp.v \
                          $RTL/soc_clint.v $RTL/soc_gptimer.v $RTL/soc_wdog.v \
                          $RTL/soc_busstat.v $RTL/soc_scrub.v \
                          $RTL/soc_boot.v \
                          $RTL/soc_mem_ecc.v \
                          $RTL/soc_tmr_bank.v $RTL/soc_npu.v \
                          $RTL/soc_npu_ser.v \
                          $PILOT_RTL/pilot_top.v $PILOT_RTL/lif_core.v \
                          $PILOT_RTL/aer_fifo.v $PILOT_RTL/scrub.v \
                          $PILOT_RTL/secded_enc.v $PILOT_RTL/secded_dec.v \
                          $PILOT_RTL/tmr_voter.v \
                          $OUT/soc_fabric_meas.v

${SOC_CHPARAM:+chparam $SOC_CHPARAM $TOP}
hierarchy -check -top $TOP

# The blackbox comes AFTER hierarchy and the pattern carries a leading
# star, because \`read_verilog -defer\` stores a module as
# \`\$abstract\\name\` and \`hierarchy\` then derives it as
# \`\$paramod\$<hash>\\name\`. A bare \`blackbox name\` matches neither and
# yosys reports "Selection did not match any module" as a WARNING and
# exits zero -- which is precisely the shape docs/49 section 8.1 spends
# four pages on, and it is why the assertion below the run exists.
$(for m in ${SOC_SYN_BLACKBOX:-}; do echo "blackbox *$m"; done)

synth -flatten -top $TOP
opt -purge

dfflibmap -liberty $SG13G2_TYP
opt
abc -liberty $SG13G2_TYP -constr $OUT/abc.constr -D $PERIOD_NS

# The final flatten is LibreLane's SYNTH_HIERARCHY_MODE = deferred
# flatten: after mapping, so nothing it produces can be merged. It has
# to strip keep_hierarchy first, and that line is load bearing rather
# than tidy. hw/soc/rtl/soc_tmr_bank.v carries the attribute as one of
# its two anti-merge defences, so without this, flatten skips the three
# replica instances -- and stat -liberty then reports FOUR modules,
# whose per-module lines the awk below reads as one. Measured on the
# hardened watchdog before this line was added: cells and flops came out
# of the soc_wdog local report while the area came out of a submodule's,
# so the block read 715 cells / 204 flops / 6,188.50 um2 against a true
# 10,818.85 um2. A census that silently reads the wrong scope is the
# same defect docs/33 records one level up.
attrmap -modattr -remove keep_hierarchy
flatten
setundef -zero
opt_clean -purge

write_verilog -noattr $OUT/$TOP.netlist.v

check
tee -o $OUT/area.rpt stat -liberty $SG13G2_TYP
EOF

"$YOSYS" -l "$OUT/syn.log" -s "$OUT/soc_syn.ys" > /dev/null

# THE BLACK BOX IS ASSERTED AND NOT ASSUMED. `blackbox` on a module that
# the reader has already elaborated warns and exits zero, and a run that
# silently boxed nothing would report the WHOLE subsystem's area under
# the name of the connection alone. hw/soc/flow/fi_npu_coverage.sh makes
# the same check on its own census for the same reason.
for m in ${SOC_SYN_BLACKBOX:-}; do
  # `$paramod$<hash>\pilot_top  u_node0 (` -- the module name is a SUFFIX
  # of the type yosys writes, so the pattern anchors on the instance name
  # that follows it and not on a word boundary in front of it.
  grep -qE "$m[[:space:]]+[A-Za-z_][A-Za-z_0-9]*[[:space:]]*\(" \
       "$OUT/$TOP.netlist.v" || {
    echo "== the $m black box did not take: no instance of it survives in" >&2
    echo "   $OUT/$TOP.netlist.v, so this area is not the boxed scope." >&2
    exit 1; }
  echo "== black-boxed $m"
done

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
