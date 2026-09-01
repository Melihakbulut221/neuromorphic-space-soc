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
