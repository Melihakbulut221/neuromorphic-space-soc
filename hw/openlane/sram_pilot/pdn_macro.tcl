# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: CERN-OHL-W-2.0

# PDN grid definition for the RM_IHPSG13 macro run.
#
# Measured reason this file has to exist (run macro-01, 2026-08-25):
# LibreLane 3.0.5's stock pdn_cfg.tcl defines the macro grid as
#
#     define_pdn_grid -macro -default -name macro ...
#     add_pdn_connect -grid macro -layers "$PDN_VERTICAL_LAYER $PDN_HORIZONTAL_LAYER"
#
# i.e. it only bonds TopMetal1 to TopMetal2 above the macro. Every power
# pin of RM_IHPSG13_1P_512x32_c2_bm_bist (VDD!, VSS!, VDDARRAY!) is on
# Metal4, so with the stock grid nothing ever reaches them: pdngen exits
# happily and OpenROAD.IRDropReport then fails with
#
#     [WARNING PSM-0039] Unconnected instance u_sram/VDD! ...
#     [WARNING PSM-0039] Unconnected instance u_sram/VDDARRAY! ...
#     [ERROR PSM-0069] Check connectivity failed on VPWR.
#
# This is the first point in the flow that notices; placement, CTS,
# global routing and detailed routing all complete on a macro whose
# supplies are floating.
#
# The fix is one extra connect rule bonding the macro's Metal4 pin layer
# up to the vertical strap layer, which pdngen stacks through
# Via4/Metal5/TopVia1. It is not reachable through any config variable in
# LibreLane 3.0.5 -- the macro grid is hard-coded in pdn_cfg.tcl -- so it
# has to come in through PDN_CFG.
#
# Sourcing the stock file rather than copying it keeps the standard-cell
# grid, rails and core-ring behaviour exactly as LibreLane defines them,
# and keeps this file correct if those defaults change.

source $::env(SCRIPTS_DIR)/openroad/common/pdn_cfg.tcl

add_pdn_connect \
    -grid macro \
    -layers "Metal4 $::env(PDN_VERTICAL_LAYER)"
