/* Register offsets and fields for the GPIO port docs/65 adds,
 * hw/soc/rtl/soc_gpio.v.
 *
 * The same split soc_timers.h states: the BASE comes from soc_memmap.h,
 * which regmap/generate_memmap.py emits from regmap/memmap.yaml, so no
 * address is written down twice; the OFFSETS within the block are the
 * block's own register map -- GRLIB's GRGPIO, grip.pdf table 923 -- and
 * the map has never described them.
 *
 * What the block implements of that map, and what it leaves out, is in
 * soc_gpio.v's header; CAP reports it and check 28 reads CAP.
 */
#ifndef SOC_GPIO_H
#define SOC_GPIO_H

#include "soc_memmap.h"

#define GPIO_NBITS      16u
#define GPIO_PINS       ((1u << GPIO_NBITS) - 1u)

/* grip.pdf table 923 */
#define GPIO_DATA       (SOC_GPIO_BASE + 0x000u)   /* r   synchronised pins */
#define GPIO_OUTPUT     (SOC_GPIO_BASE + 0x004u)   /* rw                    */
#define GPIO_DIR        (SOC_GPIO_BASE + 0x008u)   /* rw  1 = output        */
#define GPIO_IMASK      (SOC_GPIO_BASE + 0x00Cu)   /* rw  1 = may interrupt */
#define GPIO_IPOL       (SOC_GPIO_BASE + 0x010u)   /* rw  level: 1 = high; edge: 1 = rising */
#define GPIO_IEDGE      (SOC_GPIO_BASE + 0x014u)   /* rw  1 = edge          */
#define GPIO_BYPASS     (SOC_GPIO_BASE + 0x018u)   /* r   reads zero        */
#define GPIO_CAP        (SOC_GPIO_BASE + 0x01Cu)   /* r                     */
#define GPIO_IAVAIL     (SOC_GPIO_BASE + 0x040u)   /* r   every line        */
#define GPIO_IFLAG      (SOC_GPIO_BASE + 0x044u)   /* wc  write 1 to clear  */
#define GPIO_OUTPUT_OR  (SOC_GPIO_BASE + 0x054u)   /* w   OUTPUT |= wdata   */
#define GPIO_DIR_OR     (SOC_GPIO_BASE + 0x058u)
#define GPIO_IMASK_OR   (SOC_GPIO_BASE + 0x05Cu)
#define GPIO_OUTPUT_AND (SOC_GPIO_BASE + 0x064u)   /* w   OUTPUT &= wdata   */
#define GPIO_DIR_AND    (SOC_GPIO_BASE + 0x068u)
#define GPIO_IMASK_AND  (SOC_GPIO_BASE + 0x06Cu)
#define GPIO_OUTPUT_XOR (SOC_GPIO_BASE + 0x074u)   /* w   OUTPUT ^= wdata   */
#define GPIO_DIR_XOR    (SOC_GPIO_BASE + 0x078u)
#define GPIO_IMASK_XOR  (SOC_GPIO_BASE + 0x07Cu)

/* grip.pdf table 931, the capability register. */
#define GPIO_CAP_PU         (1u << 18)   /* pulse register present         */
#define GPIO_CAP_IER        (1u << 17)   /* input enable register present  */
#define GPIO_CAP_IFL        (1u << 16)   /* interrupt flag register present */
#define GPIO_CAP_IRQGEN(v)  (((v) >> 8) & 0x1Fu)
#define GPIO_CAP_NLINES(v)  ((v) & 0x1Fu)

#endif /* SOC_GPIO_H */
