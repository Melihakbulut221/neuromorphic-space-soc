# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: CERN-OHL-W-2.0

# PDN configuration for a design containing RM_IHPSG13 SRAM macros.
#
# THIS FILE IS NOT OPTIONAL AND IT IS NOT A TUNING. Without it the six
# macros of hw/soc/rtl/soc_mem_sram.v have no power, and the flow does
# not notice until IR drop, thirty-five steps after the damage is done.
#
# The mechanism, measured by hw/openlane/sram_pilot in docs/12 section
# 7.3 and reproduced here rather than rediscovered:
#
#   librelane/scripts/openroad/common/pdn_cfg.tcl builds the macro grid
#   with
#       define_pdn_grid -macro -default -name macro ...
#       add_pdn_connect -grid macro \
#           -layers "$PDN_VERTICAL_LAYER $PDN_HORIZONTAL_LAYER"
#   and this PDK sets PDN_VERTICAL_LAYER to TopMetal1 and
#   PDN_HORIZONTAL_LAYER to TopMetal2. So the stock macro grid bonds
#   TopMetal1 to TopMetal2 and nothing else -- while ALL THREE
#   RM_IHPSG13 supply pins (VDD!, VSS!, VDDARRAY!) are on Metal4. The
#   grid never descends to them.
#
# What that failure looks like, and why it is worth a file: pdngen exits
# successfully, check_power_grid writes empty error files, and
# placement, clock-tree synthesis, global routing and DETAILED ROUTING
# all complete on a design whose memories are unpowered. The first step
# that objects is OpenROAD.IRDropReport, with
#
#   [WARNING PSM-0039] Unconnected instance <macro>/VDD! at ...
#   [ERROR PSM-0069] Check connectivity failed on VPWR.
#
# The PDK does declare MACRO_BLOCKAGES_LAYER, and reading it as "the PDN
# keeps off those layers over a macro" is false: docs/12 section 6.4
# found that the string appears NOWHERE in LibreLane 3.0.5 and the key
# is silently inert.
#
# There is no configuration variable for the macro grid's layers in
# LibreLane 3.0.5 -- it is hard-coded in the shipped Tcl -- so sourcing
# the stock file and adding the missing connect is the only way in.
# ANY RM_IHPSG13 INTEGRATION IN THIS TOOL VERSION NEEDS THIS FILE OR AN
# EQUIVALENT.

source $::env(SCRIPTS_DIR)/openroad/common/pdn_cfg.tcl

add_pdn_connect \
    -grid macro \
    -layers "Metal4 $::env(PDN_VERTICAL_LAYER)"

# ---------------------------------------------------------------------
# The ROM's two check macros, added 2026-09-13.
# ---------------------------------------------------------------------
#
# They are the narrowest parts in the design at 236.80 um, and the grid
# above does not reach all of their supply pins. Measured, on run
# s83romecc2: OpenROAD.IRDropReport failed with [PSM-0069] Check
# connectivity failed on VPWR, and every [PSM-0038] unconnected shape it
# listed lies in one of the two check macros' y bands -- 60.480 to
# 251.820 and 1821.960 to 2013.300 -- each broken at 206.355 to 212.995,
# whose centre is 209.675 um against a horizontal strap at 210.160
# (PDN_HOFFSET 13.6, PDN_HPITCH 75.6, core bottom 45.36). The Metal4 was
# cut around the horizontal strap instead of bonded to it.
#
# WHY THIS IS A SECOND GRID AND NOT A SECOND LAYER ON THE FIRST. Adding
# "Metal4 $::env(PDN_HORIZONTAL_LAYER)" to the `macro` grid above was
# tried first, on run s83romecc3, and it took the flow down far earlier
# -- OpenROAD.GeneratePDN, step 13, [PDN-0179] Unable to repair all
# channels. That grid covers every macro in the design, including four
# RAM macros 784.48 um wide whose channels it then could not close. The
# fix has to reach the two narrow macros and leave the six wide ones
# exactly as they were, so it is scoped by instance.
#
# On a configuration whose netlist has no check macros -- every `rom0`
# build, which is all of them before this date -- `-instances` matches
# nothing and this grid is not created, so the six-macro flow is
# untouched and its runs stay comparable.
set _chk0 [[ord::get_db_block] findInst "u_rom.g_rom_1024x32_ecc.u_c0"]
if {$_chk0 != "NULL" && $_chk0 != ""} {
    define_pdn_grid \
        -macro \
        -name rom_chk \
        -instances {u_rom.g_rom_1024x32_ecc.u_c0 u_rom.g_rom_1024x32_ecc.u_c1} \
        -halo "0 0 0 0"
    add_pdn_connect -grid rom_chk \
        -layers "Metal4 $::env(PDN_VERTICAL_LAYER)"
    add_pdn_connect -grid rom_chk \
        -layers "Metal4 $::env(PDN_HORIZONTAL_LAYER)"
}
