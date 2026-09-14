// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: Apache-2.0

/* The boot flow's register block and its image format, docs/68.
 *
 * The same split soc_timers.h, soc_gpio.h, soc_qspi.h and soc_scrub.h
 * state: the BASE comes from soc_memmap.h, generated from
 * regmap/memmap.yaml, so no address is written down twice; the OFFSETS
 * within the block are the block's own register map, which
 * hw/soc/rtl/soc_boot.v's header states and the map has never described.
 *
 * The IMAGE FORMAT below is not a register map at all -- it is a
 * contract between hw/soc/flow/gen_boot_image.py, which writes the
 * image into the flash at build time, and hw/soc/tb/sw/boot.c, which
 * reads it back at run time. It is here so that the two have one
 * declaration of it and not two.
 */
#ifndef SOC_BOOT_H
#define SOC_BOOT_H

#include "soc_memmap.h"

/* ---- BOOTREG, hw/soc/rtl/soc_boot.v --------------------------------- */

#define BOOT_BSTRAP (SOC_BOOTREG_BASE + 0x00u)  /* r   the sampled pins  */
#define BOOT_BSTAT  (SOC_BOOTREG_BASE + 0x04u)  /* r   the boot counter  */
#define BOOT_BRPT   (SOC_BOOTREG_BASE + 0x08u)  /* rw  the boot report   */
#define BOOT_EPOCH  (SOC_BOOTREG_BASE + 0x0Cu)  /* rw  the epoch word    */

/* BSTRAP. The low sixteen bits are the pins; the high half is the
 * block's own description of itself. */
#define BOOT_STRAP_SRC(v)   ((v) & 0x3u)        /* 0 = CS0, 1 = CS1      */
#define BOOT_STRAP_NOBOOT   (1u << 2)           /* stay in the ROM       */
#define BOOT_STRAP_SPARE    (1u << 3)
#define BOOT_STRAP_WDOGDIS  (1u << 16)          /* the watchdog's pin    */
#define BOOT_STRAP_NSTRAP(v) (((v) >> 24) & 0xFu)
#define BOOT_STRAP_VALID    (1u << 31)

/* BSTAT. CNT is the number of boots since power-on NOT COUNTING THIS
 * ONE, so the power-on boot reads zero; LIMIT is a constant of the
 * netlist and no register reaches it (soc_boot.v's LIMIT parameter).
 * LAST is set on the last boot the loader is allowed to attempt and
 * OVER on any boot past it -- both are the comparison the loader would
 * otherwise write down a second time. */
#define BOOT_STAT_CNT(v)    ((v) & 0xFFu)
#define BOOT_STAT_LAST      (1u << 8)
#define BOOT_STAT_OVER      (1u << 9)
#define BOOT_STAT_LIMIT(v)  (((v) >> 16) & 0xFFu)
/* TMRERR and TMRCNT are the watchdog-replica report BSTAT carries and
 * nothing decoded. hw/soc/rtl/soc_boot.v puts TMRERR at bit 31 and
 * TMRCNT in the four bits below it; hw/soc/tb/cocotb/test_soc_boot.py
 * lines 415-416 already decode them that way, and until 2026-09-14 the
 * C side did not, so a counter that is sticky and saturating had no
 * reader outside the testbench. */
#define BOOT_STAT_TMRERR    (1u << 31)
#define BOOT_STAT_TMRCNT(v) (((v) >> 27) & 0xFu)

/* BRPT, the report the loader writes before it hands over or gives up.
 * It is EVIDENCE and never authority -- nothing in the hardware or in
 * the loader branches on it, soc_boot.v's header says why -- so its
 * layout is a software convention and this header is the only place it
 * is declared.
 *
 *   [3:0]    CAUSE    why the last boot ended the way it did
 *   [7:4]    IMAGE    which image the loader was working on, 0 or 1
 *   [15:8]   WDOGRST  WDOGSTAT.RSTCNT as the loader read it, so that a
 *                     disagreement with BSTAT.CNT is visible in
 *                     telemetry (soc_boot.v's header says why the two
 *                     counters exist)
 *   [23:16]  BOOTCNT  BSTAT.CNT as the loader read it
 *   [31:24]  MAGIC    0xB0, so a report the loader never wrote is
 *                     distinguishable from one that says CAUSE = 0
 */
#define BOOT_RPT_MAGIC      0xB0u
#define BOOT_RPT(cause, image, wrst, bcnt) \
    (((uint32_t)BOOT_RPT_MAGIC << 24) | (((uint32_t)(bcnt) & 0xFFu) << 16) \
     | (((uint32_t)(wrst) & 0xFFu) << 8) | (((uint32_t)(image) & 0xFu) << 4) \
     | ((uint32_t)(cause) & 0xFu))
#define BOOT_RPT_IS_VALID(v)  ((((v) >> 24) & 0xFFu) == BOOT_RPT_MAGIC)
#define BOOT_RPT_CAUSE(v)     ((v) & 0xFu)
#define BOOT_RPT_IMAGE(v)     (((v) >> 4) & 0xFu)
#define BOOT_RPT_WDOGRST(v)   (((v) >> 8) & 0xFFu)
#define BOOT_RPT_BOOTCNT(v)   (((v) >> 16) & 0xFFu)

/* The causes, in the order the loader can reach them. Every one of them
 * is a place the loader stops trying THIS image; docs/68 section 6 is
 * what it does next. */
#define BOOT_CAUSE_OK        0x0u  /* an image was loaded and entered   */
#define BOOT_CAUSE_NOFLASH   0x1u  /* the device did not identify       */
#define BOOT_CAUSE_MAGIC     0x2u  /* the header's magic word is wrong  */
#define BOOT_CAUSE_HDRCSUM   0x3u  /* the header does not check         */
#define BOOT_CAUSE_GEOM      0x4u  /* load, length or entry out of RAM  */
#define BOOT_CAUSE_CSUM      0x5u  /* the body does not check           */
#define BOOT_CAUSE_ECC       0x6u  /* the copy raised an uncorrectable  */
#define BOOT_CAUSE_TIMEOUT   0x7u  /* a controller wait did not end     */
#define BOOT_CAUSE_NOBOOT    0x8u  /* the NOBOOT strap: nothing tried   */
#define BOOT_CAUSE_GIVEUP    0x9u  /* past the attempt limit            */

/* ---- the image header ----------------------------------------------
 *
 * Eight words at the front of each image in the flash, written by
 * hw/soc/flow/gen_boot_image.py. GR716B validates an application image
 * with "header, code, data checksum, and header checksum" (docs/08
 * section 2.4) and this is that, at this part's scale.
 *
 * The header checksum is defined so that THE EIGHT WORDS SUM TO ZERO
 * modulo 2^32. That is one comparison at run time and it needs no
 * constant in the loader; an all-zero header, which is what an erased
 * flash region reads as after the magic check, fails on the magic
 * first and would pass this, which is why the magic is checked first
 * and separately.
 */
#define BOOT_IMG_MAGIC   0x3142534Eu   /* "NSB1" little-endian          */
#define BOOT_IMG_WORDS   8
#define BOOT_IMG_BYTES   (BOOT_IMG_WORDS * 4)

#define BOOT_IMG_W_MAGIC 0
#define BOOT_IMG_W_LOAD  1             /* RAM byte address              */
#define BOOT_IMG_W_BYTES 2             /* body length, a multiple of 4  */
#define BOOT_IMG_W_ENTRY 3             /* RAM byte address              */
#define BOOT_IMG_W_CSUM  4             /* sum of the body words         */
#define BOOT_IMG_W_VER   5             /* build identity, not checked   */
#define BOOT_IMG_W_RSVD  6
#define BOOT_IMG_W_HCSUM 7

/* How many heartbeats the NOBOOT strap's monitor prints before it takes
 * the same exit every failure takes. boot.c's comment is the argument
 * for the bound existing at all. */
#ifndef BOOT_NOBOOT_TICKS
#define BOOT_NOBOOT_TICKS 4
#endif

#endif /* SOC_BOOT_H */
