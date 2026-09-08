// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: Apache-2.0

/* SCRUB, hw/soc/rtl/soc_scrub.v (docs/67): the memory codec's counters,
 * the scrubbers' control and the address of the last uncorrectable
 * word. Register offsets are the block's own and are defined here; the
 * slot base comes from the generated map.
 *
 *   SCR_RAMSEC   ROWS THE SCRUBBER REPAIRED in the RAM: the upset-rate
 *   SCR_ROMSEC   counter of each memory, one per row repaired.
 *   SCR_RAMRD    READS that returned a corrected word. Not upsets: one
 *   SCR_ROMRD    corrupt word read ten times before the scrubber reaches
 *                it raises this ten times. RD >> SEC means the interval
 *                is too long for the rate.
 *   SCR_RAMDED   Uncorrectable syndromes, on a read (which trapped) or
 *   SCR_ROMDED   on a scrub (which left the row alone). SCR_RAMADDR /
 *                SCR_ROMADDR hold the byte offset of the last one.
 *
 * STATUS bit 8 is the interrupt, as in BUSSTAT; the six sticky bits are
 * 5..0 in the order above. CLR is write-only, one bit per source.
 * CTRL[0] enables the RAM scrubber, CTRL[1] the ROM's, CTRL[31:16] is
 * the interval in idle cycles between scrub reads; all three are
 * restored by a system reset (enabled, enabled, SCRUB_IVL_RST). */
#ifndef SOC_SCRUB_H
#define SOC_SCRUB_H

#include "soc_memmap.h"

#define SCR_STATUS      (SOC_SCRUB_BASE + 0x000u)
#define SCR_IRQEN       (SOC_SCRUB_BASE + 0x004u)
#define SCR_RAMSEC      (SOC_SCRUB_BASE + 0x008u)
#define SCR_RAMRD       (SOC_SCRUB_BASE + 0x00Cu)
#define SCR_RAMDED      (SOC_SCRUB_BASE + 0x010u)
#define SCR_ROMSEC      (SOC_SCRUB_BASE + 0x014u)
#define SCR_ROMRD       (SOC_SCRUB_BASE + 0x018u)
#define SCR_ROMDED      (SOC_SCRUB_BASE + 0x01Cu)
#define SCR_CLR         (SOC_SCRUB_BASE + 0x020u)
#define SCR_CTRL        (SOC_SCRUB_BASE + 0x024u)
#define SCR_RAMADDR     (SOC_SCRUB_BASE + 0x028u)
#define SCR_ROMADDR     (SOC_SCRUB_BASE + 0x02Cu)

#define SCR_S_RAMSEC    (1u << 0)
#define SCR_S_RAMRD     (1u << 1)
#define SCR_S_RAMDED    (1u << 2)
#define SCR_S_ROMSEC    (1u << 3)
#define SCR_S_ROMRD     (1u << 4)
#define SCR_S_ROMDED    (1u << 5)
#define SCR_STATUS_IRQ  (1u << 8)

#define SCR_CTRL_RAM_EN (1u << 0)
#define SCR_CTRL_ROM_EN (1u << 1)
#define SCR_CTRL_IVL(n) (((uint32_t)(n) & 0xFFFFu) << 16)

#endif
