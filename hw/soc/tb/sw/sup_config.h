// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: Apache-2.0

/* Static configuration shared by hw/soc/tb/sw/fi_supervisor.c and
 * hw/soc/tb/sw/sup_crt0.S.
 *
 * It exists so that the two files cannot disagree about the tick period,
 * the number of partitions or the size of a partition's memory. The
 * assembly needs the tick period (it reprograms mtimecmp) and the C
 * needs all of it; a second copy of any of these numbers would be a
 * defect waiting for a build that changed one of them.
 *
 * Every value here is overridable from the build, because docs/46
 * measures the program at more than one setting and a number that can
 * only be changed by editing a source file is a number that gets
 * changed by editing a source file.
 */
#ifndef SUP_CONFIG_H
#define SUP_CONFIG_H

/* Partitions in the static schedule. Four, because Ibex is built here
 * with PMPNumRegions = 4 (soc_top.v) and a supervisor with more
 * partitions than regions has to reprogram more than one region per
 * switch; four keeps the switch cost to the single region that actually
 * differs between partitions. */
#ifndef SUP_NTASK
#define SUP_NTASK 4
#endif

/* Bytes of RAM per partition: its work area and its stack. A power of
 * two and naturally aligned, because the region is described to PMP in
 * NAPOT form and a NAPOT region whose base is not naturally aligned does
 * not encode a slightly wrong region, it encodes a much larger one
 * (link_soc.ld says the same thing about __pmp_buf). */
#ifndef SUP_TASK_MEM
#define SUP_TASK_MEM 1024
#endif

/* Frames of the static schedule the program runs before it publishes
 * its answer. */
#ifndef SUP_FRAMES
#define SUP_FRAMES 6
#endif

/* The frame period, in system clocks, as a deadline on CLINT mtime.
 * soc_clint.v is instantiated with TICK_DIV = 1, so one mtime tick is
 * one CPU clock and this number is directly comparable with everything
 * else the campaign counts.
 *
 * THE VALUE IS A SCHEDULABILITY DECISION AND NOT A TUNING KNOB. It is
 * set to twice the measured worst-case frame execution time -- a 50 %
 * CPU margin, which is the conventional early-development budget for a
 * spacecraft management processor. docs/46 section 5.1 records the
 * measurement it comes from and section 10 records that the number is a
 * convention rather than a requirement anybody wrote down for this
 * project.
 *
 * The default is the value that rule produced: the worst-case frame of
 * the work-triggered build measured 4,456 clocks, so the period is
 * 8,912. */
#ifndef SUP_TICK_PERIOD
#define SUP_TICK_PERIOD 8912
#endif

/* Watchdog reload, in the block's own arithmetic: the timeout is
 * (SUP_WDOG_RELOAD + 1) * WDOG_PRESCALE clocks and soc_top.v
 * instantiates WDOG_PRESCALE = 16.
 *
 * As in fi_workload.c, the reset default is the maximum and this write
 * is what makes the escalation ladder observable inside a campaign run
 * at all. The value is chosen from the measured kick cadence, in
 * docs/46 section 6.2, and the compile-time guards in fi_supervisor.c
 * refuse a windowed build whose timeout falls outside the band the
 * measured cadence leaves open at the declared WINS -- above the
 * longest interval and below twice the shortest.
 *
 * The default is section 6.2's value for the time-triggered build:
 * T = 835 * 16 = 13,360 clocks, 21 % above the measured longest
 * interval and 17 % below the ceiling WINS = 1 imposes. A build with a
 * different frame period, or a work-triggered one, has a different
 * cadence and must pass its own. */
#ifndef SUP_WDOG_RELOAD
#define SUP_WDOG_RELOAD 834u
#endif

#endif /* SUP_CONFIG_H */
