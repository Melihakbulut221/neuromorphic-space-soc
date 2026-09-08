#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

# The memory read-return and write-in paths, timed on their own, at the
# slow corner, on a whole-design netlist flow/sta_soc_top.sh has already
# timed.
#
#   sta_mem_paths.sh <out_dir>        after SOC_MEM=sram sta_soc_top.sh
#
# docs/67 section 5's question is not "what is the worst path" -- the
# reset net and the register-file read address own that in every
# pre-layout netlist this repository has timed -- but WHERE THE DECODER
# LANDS: how much of the period the macro read arc plus the codec plus
# the fabric return now takes, against the same netlist without the
# codec. OpenSTA's headline cannot say, so this reports three path
# groups by name, in the same corner, with the same derate, from the
# same generated Tcl flow/sta_soc_top.sh wrote:
#
#   FROM_DOUT   worst path launched by ANY macro's A_DOUT pin: the read
#               return, macro arc included, through the bank multiplexer,
#               the codec, the fabric's response multiplexer and into
#               whatever flip-flop captures it
#   TO_MACRO    worst path captured at ANY macro's input pin: the
#               address, mask and data INTO a macro, which docs/61
#               section 9.4 found had moved from the launch side to the
#               capture side of the violating population
#   DOUT_TO_MACRO  worst path from a macro's A_DOUT to a macro's input:
#               the scrubber's write-back, which decodes the row just
#               read, re-encodes the corrected word and presents it to
#               A_DIN and A_BM in the same cycle -- a macro-to-macro
#               combinational path that did not exist before docs/67
#
# It reads <out_dir>/soc_top_sta_slow.tcl, which sta_soc_top.sh
# generated with the macro Liberty and the reset cut as they were, and
# appends the reports; nothing about corners, derate or constraints is
# restated here, so the numbers are in the same frame as slack.rpt's.

set -euo pipefail

OUT=${1:?out dir written by flow/syn_soc_top.sh and flow/sta_soc_top.sh}
SOC_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

[ -s "$OUT/soc_top_sta_slow.tcl" ] || {
  echo "missing $OUT/soc_top_sta_slow.tcl: run SOC_MEM=sram flow/sta_soc_top.sh first" >&2
  exit 1; }

eval "$(make --no-print-directory -f "$SOC_DIR/tools.soc.mk" printvars)"
: "${STA:?}"

# The generated per-corner script, minus its reports and its exit; the
# link, the SDC, the macro Liberty and the tie-offs are kept verbatim.
sed -e '/^puts "---- setup/,$d' "$OUT/soc_top_sta_slow.tcl" > "$OUT/mem_paths_slow.tcl"
cat >> "$OUT/mem_paths_slow.tcl" <<'EOF'

set douts [get_pins -hierarchical *A_DOUT*]
set mins  [get_pins -hierarchical {*A_ADDR* *A_DIN* *A_BM* *A_MEN *A_WEN *A_REN}]
puts "MEMPATHS dout_pins [llength $douts] macro_input_pins [llength $mins]"

puts "======== FROM_DOUT: worst path launched by a macro A_DOUT ========"
report_checks -path_delay max -from $douts -group_path_count 3 \
              -format full_clock_expanded -digits 4
puts "======== TO_MACRO: worst path captured at a macro input ========"
report_checks -path_delay max -to $mins -group_path_count 3 \
              -format full_clock_expanded -digits 4
puts "======== DOUT_TO_MACRO: worst path from an A_DOUT to a macro input ========"
report_checks -path_delay max -from $douts -to $mins -group_path_count 3 \
              -format full_clock_expanded -digits 4

# The machine-readable lines, from OpenSTA's own slack of the worst
# path in each group. get_property's slack is already in the Liberty
# time unit (ns); it is printed as such, not passed through format_time.
proc mempath {name paths} {
  if {[llength $paths] == 0} { puts "MEMPATHS $name none"; return }
  foreach path $paths {
    puts [format "MEMPATHS %s slack %.4f start %s end %s" $name \
          [get_property $path slack] \
          [get_full_name [get_property $path startpoint]] \
          [get_full_name [get_property $path endpoint]]]
  }
}
mempath FROM_DOUT [find_timing_paths -path_delay max -from $douts -group_path_count 1]
mempath TO_MACRO  [find_timing_paths -path_delay max -to $mins -group_path_count 1]
mempath DOUT_TO_MACRO [find_timing_paths -path_delay max -from $douts -to $mins -group_path_count 1]
exit
EOF

"$STA" -no_splash -exit "$OUT/mem_paths_slow.tcl" > "$OUT/mem_paths_slow.rpt" 2>&1 || {
  echo "OpenSTA failed; see $OUT/mem_paths_slow.rpt" >&2; tail -20 "$OUT/mem_paths_slow.rpt" >&2; exit 1; }
grep "^MEMPATHS" "$OUT/mem_paths_slow.rpt"
echo "  report: $OUT/mem_paths_slow.rpt"
