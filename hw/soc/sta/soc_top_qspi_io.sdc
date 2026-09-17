# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: CERN-OHL-W-2.0

# The QSPI pins, constrained against the flash this repository models.
#
# WHY THIS FILE EXISTS
#
# `hw/soc/rtl/soc_qspi.v:472` samples `io_i` straight into `cur` with no
# intermediate flop, on the same `clk_i` edge that raises `sck_q`. The
# data the flash launched on the previous SCK falling edge therefore has
# ONE SCK HALF-PERIOD to complete a round trip: clk_i to pad, pad to
# board, the part's clock-low-to-output-valid, board back, pad back, and
# setup at `cur`.
#
# Nothing in this repository stated that budget until 2026-09-18. There
# was no `set_input_delay` on `qspi_io_i` anywhere, so the flow fell
# back on LibreLane's blanket IO_PCT synthetic delay, which is a
# fraction of the clock period and not a model of a flash. An external
# review called it a silicon bring-up risk rather than a simulation
# bug, and it is right: every cocotb test passes because the testbench
# model and the RTL agree about the edge, and a board does not.
#
# WHAT IT ASSUMES, AND THE ASSUMPTION IS THE POINT
#
# tCLQV comes from the part. The board allowance does not come from
# anywhere: there is no board, no pad ring (`soc_qspi.v:186` -- each IO
# lane leaves the module as three wires) and no pad model, because the
# PDK's IO library is not instantiated anywhere in this design. So the
# allowance below is a STATED ASSUMPTION and not a measurement, it is
# one number at the top of this file so that it can be replaced by a
# measurement, and a reader who has a board should replace it.
#
#   T_CLQV       6.0 ns   hw/soc/tb/flash_w25q128jv.v:113, the W25Q128JV's
#                         clock-low-to-output-valid, the part's own max
#   T_CLQX       1.5 ns   :114, its output-hold, which bounds the min
#   T_DVCH       1.0 ns   :108, its input setup
#   T_CHDX       2.0 ns   :109, its input hold
#   T_BOARD      2.0 ns   ASSUMED, each way: pad driver, package, trace,
#                         pad receiver. Replace with a measurement.
#
# THE ARITHMETIC THE HEADER OF soc_qspi.v NOW CARRIES
#
#   SCK          = clk_i / (2 * (DIV + 1))          soc_qspi.v:73
#   half period  = (DIV + 1) * CLOCK_PERIOD         soc_qspi.v:130-131
#   required     >= T_CLQV + 2 * T_BOARD + setup
#   so           DIV >= ceil((T_CLQV + 2*T_BOARD) / CLOCK_PERIOD) - 1
#
# At CLOCK_PERIOD = 20 ns (hw/soc/pnr/config.json:15) that is
# ceil(10/20) - 1 = 0, so DIV = 0 is legal under these assumptions with
# 10 ns of the 20 left for setup and for whatever the assumption is
# wrong about. At a shorter period it is not: at 10 ns the requirement
# becomes DIV >= 0 with nothing left over, and at 5 ns DIV >= 1.
#
# WHAT IT MEASURES, AND WHAT IT STILL DOES NOT DO
#
# Re-timed 2026-09-18 against the sign-off netlist
# `hw/soc/pnr/runs/s83romecc5/final/nl/soc_top.nl.v` at the typical
# corner, OpenSTA 3.1.0, 20 ns period, with this file sourced:
#
#   qspi_io_i[*] -> capture flop     slack +9.4682 ns (MET)
#   -> qspi_sck_o                    slack +16.7764 ns (MET)
#
# So the path closes with 9.47 ns of margin under the assumptions
# above -- which is the answer the ceiling in soc_qspi.v's header could
# not give, because a ceiling is not a budget.
#
# It does NOT change the design, and it is not yet part of a
# place-and-route sign-off: this was a standalone OpenSTA run on the
# netlist a completed run left behind, not a flow that built a layout
# with these constraints in it. Folding it into the LibreLane
# configuration is a separate change with its own measurement, because
# a constraint the router sees can move the router.

set qspi_clk       [get_clocks clk_i]
set qspi_t_clqv    6.0
set qspi_t_board   2.0
set qspi_in_max    [expr {$qspi_t_clqv + 2 * $qspi_t_board}]
set qspi_in_min    1.5

# Inputs: the four IO lanes when the flash is driving them. The maximum
# is the part's tCLQV plus the round trip; the minimum is the part's
# tCLQX, its output-hold, which bounds how early the new value can
# appear and is what a hold check on this path needs.
if {[llength [get_ports -quiet qspi_io_i*]] > 0} {
    set_input_delay -clock $qspi_clk -max $qspi_in_max [get_ports qspi_io_i*]
    set_input_delay -clock $qspi_clk -min $qspi_in_min [get_ports qspi_io_i*]
}

# Outputs: SCK, the four lanes when this block drives them, and the chip
# selects. The external requirement is the part's setup and hold around
# its own sampling edge -- tDVCH 1.0 ns and tCHDX 2.0 ns, both from
# hw/soc/tb/flash_w25q128jv.v:108-109, which are the numbers the
# simulation model enforces -- plus the same board assumption as above.
set qspi_t_dvch    1.0
set qspi_t_chdx    2.0
set qspi_out_max   [expr {$qspi_t_dvch + $qspi_t_board}]
set qspi_out_min   [expr {-1.0 * ($qspi_t_chdx + $qspi_t_board)}]

foreach p {qspi_sck_o qspi_io_o* qspi_io_oe_o* qspi_cs_no*} {
    if {[llength [get_ports -quiet $p]] > 0} {
        set_output_delay -clock $qspi_clk -max $qspi_out_max [get_ports $p]
        set_output_delay -clock $qspi_clk -min $qspi_out_min [get_ports $p]
    }
}
