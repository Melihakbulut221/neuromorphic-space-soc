# report_power on the signed-off netlist, with or without measured
# switching activity. Driven by hw/soc/flow/power_soc_top.sh.
#
# The library set, the netlist, the parasitics and the constraints are
# the ones LibreLane's OpenROAD.STAPostPNR step used, taken from
# `hw/soc/pnr/runs/<tag>/final/` rather than rebuilt, so the FIRST thing
# this script prints is the timing that identifies the run: if the worst
# slack does not match `docs/47` section 8.2 the instrument is not the
# one that document reports from and no power figure below it means
# anything.
#
# The three corners are named the same way LibreLane names them and the
# SRAM Liberty at the fast corner is characterised at -55 C while the
# standard cells are at -40 C -- `docs/47` section 9's caveat, carried
# here because it applies to power exactly as it applies to timing.

set PDK    $::env(PWR_PDK)
set CORNER $::env(PWR_CORNER)

switch $CORNER {
  nom_typ_1p20V_25C   { set SC typ_1p20V_25C  ; set IO typ_1p2V_3p3V_25C  ; set SR typ_1p20V_25C }
  nom_slow_1p08V_125C { set SC slow_1p08V_125C; set IO slow_1p08V_3p0V_125C; set SR slow_1p08V_125C }
  nom_fast_1p32V_m40C { set SC fast_1p32V_m40C; set IO fast_1p32V_3p6V_m40C; set SR fast_1p32V_m55C }
  default { puts "unknown corner $CORNER"; exit 1 }
}

set_cmd_units -time ns -capacitance pF -current mA -voltage V \
              -resistance kOhm -distance um
set sta_report_default_digits 6

define_corners $CORNER
read_liberty -corner $CORNER $PDK/libs.ref/sg13g2_stdcell/lib/sg13g2_stdcell_$SC.lib
read_liberty -corner $CORNER $PDK/libs.ref/sg13g2_io/lib/sg13g2_io_$IO.lib
read_liberty -corner $CORNER $PDK/libs.ref/sg13g2_sram/lib/RM_IHPSG13_1P_2048x64_c2_bm_bist_$SR.lib
read_liberty -corner $CORNER $PDK/libs.ref/sg13g2_sram/lib/RM_IHPSG13_1P_1024x32_c2_bm_bist_$SR.lib

read_verilog $::env(PWR_NL)
link_design soc_top

if { [string length $::env(PWR_SPEF)] } {
    read_spef -corner $CORNER $::env(PWR_SPEF)
}
read_sdc $::env(PWR_SDC)

# docs/47's run applies TIME_DERATING_CONSTRAINT = 5 as a float. It has
# no effect on power and is set anyway, so that the slack this script
# prints is comparable with that document's without a second reading.
set_timing_derate -early 0.95
set_timing_derate -late 1.05

puts "CORNER $CORNER"
puts [format "SLACK setup %.4f  hold %.4f" [worst_slack -max] [worst_slack -min]]

if { [string length $::env(PWR_ACT)] } {
    puts "ACTIVITY $::env(PWR_ACT)"
    source $::env(PWR_ACT)
} else {
    puts "ACTIVITY none -- OpenSTA default 0.1 / 0.5 on inputs and registers"
}

report_power -corner $CORNER

lassign [lrange [sta::design_power $CORNER] 0 3] di ds dl dt
puts [format "TOTAL %s %s internal %.6e switching %.6e leakage %.6e total %.6e" \
      $::env(PWR_TAG) $CORNER $di $ds $dl $dt]

# The six macros individually. They are the only cells in this netlist
# that still carry the name the RTL gave them -- everything else was
# renamed by `abc` -- so this is the one block-level attribution the
# hardened netlist can support without a second synthesis.
foreach m {u_ram.g_ram_2048x64.u_b0 u_ram.g_ram_2048x64.u_b1
           u_ram.g_ram_2048x64.u_b2 u_ram.g_ram_2048x64.u_b3
           u_rom.g_rom_1024x32.u_b0 u_rom.g_rom_1024x32.u_b1} {
    set c [get_cells $m]
    if { $c eq "" } { continue }
    lassign [lrange [sta::instance_power $c $CORNER] 0 3] i s l t
    puts [format "MACRO %s %s internal %.6e switching %.6e leakage %.6e total %.6e" \
          $::env(PWR_TAG) $m $i $s $l $t]
}

report_activity_annotation
exit
