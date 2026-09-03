#!/usr/bin/env bash
# Activity-annotated power for soc_top, from a whole-SoC simulation.
#
#   power_soc_top.sh extract <vcd> <tb> <out_dir> [window ...]
#   power_soc_top.sh report  <out_dir> <window> [--nl <netlist>] [--no-spef]
#
# WHY THIS SCRIPT EXISTS.  `docs/47`'s sign-off runs `report_power` with
# no activity annotation at all: LibreLane's `corner.tcl` calls
# `report_power -corner $corner_name` and nothing before it reads a VCD
# or a SAIF, so every switching figure in
# `runs/full3/19-openroad-stapostpnr/*/power.rpt` rests on OpenSTA's
# default -- 0.1 transitions per clock period at a 50 % duty cycle on
# every input port and every register output.  `docs/53` section 7.1
# item 3 named that and section 15 item 1 asked for this.  The whole of
# what this script adds is a measured number in place of the 0.1.
#
# THREE THINGS IT DOES NOT DO, all of them consequences of the netlist
# rather than choices:
#
#   1. It does not read the VCD into OpenSTA.  `syn_soc_top.sh` runs
#      `synth -flatten` and `abc`; of the 33,832 nets in the hardened
#      netlist 617 carry a name and not one flip-flop instance does, so
#      `read_power_activities -vcd` would annotate under 2 % of the
#      design.  What is annotated instead is named in
#      `power_activity.py`.
#   2. It does not model glitches.  The dump is a zero-delay RTL
#      simulation, so a combinational node that would switch three times
#      in silicon switches once here.
#   3. IT DOES NOT INCLUDE THE NPU.  `hw/soc/pnr/runs/full3` was
#      hardened from `hw/soc/out/s47-sram/soc_top.netlist.v`, which
#      `syn_soc_top.sh` produced before `docs/51` put `u_npu` inside
#      `soc_top.v` -- that script's source list still has no
#      `soc_npu.v`.  `docs/51` section 11 says so in its last line:
#      "docs/47's sign-off does not include this block."  Every power
#      figure from the `full3` netlist is therefore the power of the SoC
#      WITHOUT its accelerator, and the accompanying document prices the
#      difference separately.
#
# THE PILOT IS FROZEN.  This script reads hw/rtl/ and writes nothing
# outside its own output directory.

set -euo pipefail

SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
REPO=$(cd "$SOC_DIR/../.." && pwd -P)
RUN=${PWR_RUN:-$SOC_DIR/pnr/runs/full3}
PDK_DIR=${PWR_PDK:-$HOME/.ciel/ciel/ihp-sg13g2/versions/c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c/ihp-sg13g2}
STA=${PWR_STA:-$HOME/.local/opt/llbin/sta}

usage () { sed -n '2,8p' "${BASH_SOURCE[0]}" >&2; exit 2; }

cmd=${1:-}; shift || usage

case "$cmd" in

extract)
  VCD=${1:?vcd}; TB=${2:?testbench top, e.g. tb_soc}; OUT=${3:?out dir}
  shift 3
  mkdir -p "$OUT"
  D=$TB.dut
  # The six macro control pins, derived from the BEHAVIOURAL memory's own
  # ports with the expressions copied out of hw/soc/rtl/soc_mem_sram.v's
  # port map. The simulation runs soc_mem.v; the netlist has the macros;
  # this is the bridge, and it is the design's arithmetic rather than
  # this script's.
  #   RAM: widx = addr_i[15:2], bank = widx[13:12] = addr_i[15:14]
  #   ROM: widx = addr_i[12:2], bank = widx[10]    = addr_i[12]
  #
  # The four JOINT states are derived as well as the three pins, because
  # the macro Liberty's A_CLK internal power is `when`-conditioned on all
  # three at once -- 122.394 pJ for a read, 155.368 for a write, 0.5559
  # for a DESELECTED macro whose A_REN is high, and 0 for one whose A_REN
  # is low. A_REN is `!do_write` in soc_mem_sram.v, so it is high on
  # every macro on every cycle the SoC is not writing, selected or not,
  # and that third number is paid six times over on every clock edge of
  # an idle part. Marginal duty cycles cannot express that; the joint
  # states can, and hw/soc/flow/macro_energy.py is what reads them.
  DER=()
  for k in 0 1 2 3; do
    SELK="(V['$D.u_ram.req_i'] and ((V['$D.u_ram.addr_i']>>14)&3)==$k)"
    DER+=(--derive "ram_men$k=1 if $SELK else 0")
    DER+=(--derive "ram_rd$k=1 if ($SELK and not V['$D.u_ram.do_write']) else 0")
    DER+=(--derive "ram_wr$k=1 if ($SELK and V['$D.u_ram.do_write']) else 0")
    DER+=(--derive "ram_dr$k=1 if (not $SELK and not V['$D.u_ram.do_write']) else 0")
    DER+=(--derive "ram_dw$k=1 if (not $SELK and V['$D.u_ram.do_write']) else 0")
  done
  DER+=(--derive "ram_wen=1 if V['$D.u_ram.do_write'] else 0")
  DER+=(--derive "ram_ren=0 if V['$D.u_ram.do_write'] else 1")
  for k in 0 1; do
    SELK="(V['$D.u_rom.req_i'] and ((V['$D.u_rom.addr_i']>>12)&1)==$k)"
    DER+=(--derive "rom_men$k=1 if $SELK else 0")
    DER+=(--derive "rom_rd$k=1 if ($SELK and not V['$D.u_rom.do_write']) else 0")
    DER+=(--derive "rom_wr$k=1 if ($SELK and V['$D.u_rom.do_write']) else 0")
    DER+=(--derive "rom_dr$k=1 if (not $SELK and not V['$D.u_rom.do_write']) else 0")
    DER+=(--derive "rom_dw$k=1 if (not $SELK and V['$D.u_rom.do_write']) else 0")
  done
  DER+=(--derive "rom_wen=1 if V['$D.u_rom.do_write'] else 0")
  DER+=(--derive "rom_ren=0 if V['$D.u_rom.do_write'] else 1")

  WIN=()
  if [ $# -eq 0 ]; then
    WIN=(--window all:0:-1
         --window busy:0:-1:"$D.core_sleep_o=0"
         --window idle:0:-1:"$D.core_sleep_o=1")
  else
    for w in "$@"; do WIN+=(--window "$w"); done
  fi

  exec python3 "$SOC_DIR/flow/vcd_activity.py" "$VCD" \
       --clock "$D.clk_i" --scope "$D" \
       "${WIN[@]}" "${DER[@]}" \
       --span "$D.u_npu" --span "$D.u_npu.cnt_in" --span "$D.u_npu.cnt_out" \
       --json "$OUT/activity.json"
  ;;

annotate)
  OUT=${1:?out dir}; WINDOW=${2:?window}; TB=${3:-tb_soc}
  D=$TB.dut
  MP=()
  i=0
  for inst in u_ram.g_ram_2048x64.u_b0 u_ram.g_ram_2048x64.u_b1 \
              u_ram.g_ram_2048x64.u_b2 u_ram.g_ram_2048x64.u_b3; do
    MP+=(--macro-pin "$inst/A_MEN=ram_men$i")
    MP+=(--macro-pin "$inst/A_WEN=ram_wen")
    MP+=(--macro-pin "$inst/A_REN=ram_ren")
    i=$((i + 1))
  done
  i=0
  for inst in u_rom.g_rom_1024x32.u_b0 u_rom.g_rom_1024x32.u_b1; do
    MP+=(--macro-pin "$inst/A_MEN=rom_men$i")
    MP+=(--macro-pin "$inst/A_WEN=rom_wen")
    MP+=(--macro-pin "$inst/A_REN=rom_ren")
    i=$((i + 1))
  done
  exec python3 "$SOC_DIR/flow/power_activity.py" "$OUT/activity.json" \
       --window "$WINDOW" --ref-window "${PWR_REF:-all}" \
       --scope "$D" --exclude "$D.u_npu" \
       --port "rst_ni=$D.rst_ni" --port "wdog_dis_i=$D.wdog_dis_i" \
       --pin "u_ibex.core_clock_gate_i.u_icg/GATE=$D.u_ibex.clock_en" \
       "${MP[@]}" --report --blocks --tcl "$OUT/act.$WINDOW.tcl"
  ;;

report)
  OUT=${1:?out dir}; WINDOW=${2:?window or the word "default"}
  shift 2
  NL=$RUN/final/nl/soc_top.nl.v
  SPEF=$RUN/final/spef/nom/soc_top.nom.spef
  SDC=$RUN/final/sdc/soc_top.sdc
  while [ $# -gt 0 ]; do
    case "$1" in
      --nl)      NL=$2; shift 2 ;;
      --sdc)     SDC=$2; shift 2 ;;
      --no-spef) SPEF=""; shift ;;
      *) usage ;;
    esac
  done
  ACT=""
  [ "$WINDOW" = default ] || ACT=$OUT/act.$WINDOW.tcl
  [ -z "$ACT" ] || [ -f "$ACT" ] || { echo "no $ACT: run 'annotate' first" >&2; exit 1; }
  for CORNER in nom_slow_1p08V_125C nom_typ_1p20V_25C nom_fast_1p32V_m40C; do
    PWR_CORNER=$CORNER PWR_NL=$NL PWR_SPEF=$SPEF PWR_SDC=$SDC \
    PWR_ACT=$ACT PWR_PDK=$PDK_DIR \
    PWR_TAG="$WINDOW" \
      "$STA" -no_splash -exit "$SOC_DIR/flow/power_report.tcl" \
      > "$OUT/power.$WINDOW.$CORNER.rpt" 2>&1 || {
        echo "sta failed for $CORNER; see $OUT/power.$WINDOW.$CORNER.rpt" >&2
        exit 1; }
    grep -E "^(TOTAL|GROUP|MACRO) " "$OUT/power.$WINDOW.$CORNER.rpt" \
      | sed "s/^/$CORNER /"
  done
  ;;

*) usage ;;
esac
