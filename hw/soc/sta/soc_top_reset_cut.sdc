# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: CERN-OHL-W-2.0

# The two reset nets of soc_top, cut, so that the rest of the design can
# be timed.
#
# WHY THIS FILE EXISTS
#
# Timed as one design at 20 ns, soc_top's worst setup path at the slow
# corner is -60.6191 ns and it starts at ONE FLIP-FLOP: `rst_sync[1]`,
# a minimum-drive `sg13g2_dfrbpq_1` whose Q is `rst_sys_n`, the system
# reset. That net reaches 2,766 `RESET_B` pins and three data pins with
# no buffer between it and any of them, and OpenSTA charges the driver
# 58.9033 ns of clock-to-Q for the capacitance. Both the synchronous and
# the asynchronous worst paths of the whole SoC are that one net.
#
# It is the same class of artefact docs/38 section 8.6 found in
# `small-pmp-sec` (a single `sg13g2_mux2_1` driving 1,447 reset pins,
# 30.85 ns) and docs/44 section 5.3 found in the hardened Ibex
# (`rst_ni` driving 2,328 pins from an input port, 10.9223 ns) -- an
# unbuffered high-fanout net in a netlist that has not been through a
# resizer. It is WORSE here for a structural reason and not a scale one:
# in `ibex_top` standalone the net is a primary input carrying
# `set_driving_cell sg13g2_buf_4`, and in the SoC it is the output of the
# weakest flip-flop in the library, because soc_top.v synchronises its
# own reset deassertion (soc_top.v's reset section, and soc_wdog.v W4).
#
# WHAT CUTTING IT MEASURES, AND WHAT IT DOES NOT
#
# It measures the design SUPPOSING the reset trees have been built. It is
# not a claim that they have been, it is not a prediction of what they
# will cost, and it does not close the check: a reset tree has its own
# recovery check and buffering it changes the number rather than removing
# the obligation. The unmodified recipe is run beside this one and both
# are reported, exactly as docs/44 section 5.1 does for its tie-offs.
#
# BOTH resets are cut and not only the large one. `rst_ni`, the power-on
# reset, reaches 199 pins from an input port; it is nowhere near binding
# and cutting it changes nothing that was measured. It is cut anyway so
# that this file means one thing -- "the reset trees are somebody else's
# problem" -- rather than two.
#
# Applied only when SOC_RESET_CUT=1. The default is off.

set_false_path -through [get_nets rst_sys_n]
set_false_path -from    [get_ports rst_ni]
