# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: CERN-OHL-W-2.0

# The constants soc_top.v drives into ibex_top, as a case analysis.
#
# WHY THIS FILE EXISTS
#
# hw/soc/flow/sta_ibex.sh synthesises and times `ibex_top` STANDALONE,
# with every input a free primary port carrying 20 % of the period as
# input delay. That is the right default for a block whose environment
# is not yet fixed, and it was the right default in docs/38. It stopped
# being harmless in docs/43, and docs/44 section 5.1 is what happened:
#
#   Every one of the ten worst setup paths at the slow corner, in BOTH
#   the upstream and the SECDED configuration, starts at
#   `cheriot_enable_i[0]`.
#
# `cheriot_enable_i` is a four-bit multi-bit-encoded configuration input
# and soc_top.v drives it with the constant `4'b1010` -- ibex_pkg's
# IbexMuBiOff, the CHERIoT half of this dual-ISA core held off. In the
# SoC there is no such path. It is a path of the measurement.
#
# So a document that quotes a slack difference between two builds and
# attributes it to a structure has to say which paths it is talking
# about. This file is how: it applies the SoC's own tie-offs, so the
# reported numbers are about logic that exists.
#
# WHAT IS AND IS NOT DONE HERE, and the line is drawn on purpose.
#
# Only `cheriot_enable_i` is constrained. soc_top.v ties many more
# inputs -- test_en_i, ram_cfg_*, hart_id_i, boot_addr_i, debug_req_i,
# the scramble ports, fetch_enable_i, mcounteren_writable_i, scan_rst_ni
# -- and constraining all of them would report a still-smaller design.
# It would also be a bigger claim than this file wants to make: several
# of those are legitimately variable on a real part (boot_addr_i is a
# strap on most SoCs), and a case analysis that quietly assumed them
# constant would be the same defect in the other direction. THIS FILE
# CONSTRAINS THE ONE INPUT THAT WAS MEASURED TO DOMINATE, and the
# unconstrained recipe is still run beside it: flow/sta_ibex.sh reports
# both and docs/44 section 5 quotes both.
#
# Applied only when SOC_TIEOFFS=1. The default is unchanged, so
# docs/38's and docs/43's numbers reproduce from this flow untouched.

set_case_analysis 0 [get_ports {cheriot_enable_i[0]}]
set_case_analysis 1 [get_ports {cheriot_enable_i[1]}]
set_case_analysis 0 [get_ports {cheriot_enable_i[2]}]
set_case_analysis 1 [get_ports {cheriot_enable_i[3]}]
