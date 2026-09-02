/* NPUCFG register map, for the bare-metal program.
 *
 * This is the FABRIC-LEVEL block's own map -- the event port and the
 * interrupt -- and it is written here rather than generated, exactly as
 * soc_timers.h is for the GPTIMER and for the same reason: regmap/
 * memmap.yaml says where a block lives and has never said what is
 * inside one (docs/40 section 8.1). The base address IS generated, from
 * soc_memmap.h, so nothing here knows where the slot is.
 *
 * The NODE register map is a different thing entirely and is NOT here.
 * It is docs/10 section 10, it has a single source in
 * regmap/regmap.yaml, and the program reaches it through the generated
 * npu_regs.h and the memory-mapped window at SOC_NPU_BASE.
 *
 * The block is hw/soc/rtl/soc_npu.v and its header is the contract.
 */

#ifndef SOC_NPUCFG_H
#define SOC_NPUCFG_H

#include "soc_memmap.h"

#define NPUCFG_ID        (SOC_NPUCFG_BASE + 0x000u)
#define NPUCFG_VERSION   (SOC_NPUCFG_BASE + 0x004u)
#define NPUCFG_CTRL      (SOC_NPUCFG_BASE + 0x008u)
#define NPUCFG_STATUS    (SOC_NPUCFG_BASE + 0x00Cu)
#define NPUCFG_IRQCAUSE  (SOC_NPUCFG_BASE + 0x010u)
#define NPUCFG_IRQMASK   (SOC_NPUCFG_BASE + 0x014u)
#define NPUCFG_EVQ_IN    (SOC_NPUCFG_BASE + 0x018u)
#define NPUCFG_EVQ_OUT   (SOC_NPUCFG_BASE + 0x01Cu)
#define NPUCFG_EVQ_STAT  (SOC_NPUCFG_BASE + 0x020u)
#define NPUCFG_GEOM      (SOC_NPUCFG_BASE + 0x024u)
#define NPUCFG_CNT       (SOC_NPUCFG_BASE + 0x028u)
#define NPUCFG_CNT_DROP  (SOC_NPUCFG_BASE + 0x02Cu)

/* an offset the block does not implement; reserved offsets are a bus
 * error, never a read of zero */
#define NPUCFG_UNIMPL    (SOC_NPUCFG_BASE + 0x800u)

#define NPUCFG_ID_WORD   0x4E505543u   /* "NPUC" */

/* CTRL */
#define NPUCFG_IN_EN     (1u << 0)
#define NPUCFG_OUT_EN    (1u << 1)
#define NPUCFG_FLUSH     (1u << 2)     /* self-clearing */
#define NPUCFG_SCRUB     (1u << 3)     /* self-clearing, pulses SCRUB_STB */

/* STATUS */
#define NPUCFG_ST_SER_BUSY   (1u << 0)
#define NPUCFG_ST_INJ_EMPTY  (1u << 1)
#define NPUCFG_ST_INJ_FULL   (1u << 2)
#define NPUCFG_ST_CAP_EMPTY  (1u << 3)
#define NPUCFG_ST_CAP_FULL   (1u << 4)
#define NPUCFG_ST_IN_RDY     (1u << 5)
#define NPUCFG_ST_OUT_VLD    (1u << 6)
#define NPUCFG_ST_NODE_BUSY  (1u << 7)
#define NPUCFG_ST_NODE_ERR   (1u << 8)
#define NPUCFG_ST_NODE_SEC   (1u << 9)
#define NPUCFG_ST_NODE_DED   (1u << 10)
#define NPUCFG_ST_NODE_TMR   (1u << 11)

/* IRQ_CAUSE. b0..b4 are LEVELS: a write to one is accepted and does
 * nothing, because the way to clear a level is to fix what raises it.
 * b5 and b6 are STICKY and write-1-to-clear. */
#define NPUCFG_C_EVT      (1u << 0)
#define NPUCFG_C_ERR      (1u << 1)
#define NPUCFG_C_SEC      (1u << 2)
#define NPUCFG_C_DED      (1u << 3)
#define NPUCFG_C_TMR      (1u << 4)
#define NPUCFG_C_INJ_OVF  (1u << 5)
#define NPUCFG_C_FETCH_ER (1u << 6)

/* EVQ_OUT */
#define NPUCFG_EVQ_VALID  (1u << 31)

/* The node register window. One docs/10 section 10 register block per
 * mesh node at NODE_ID * 0x1000, which is what docs/10 section 8 item 5
 * freezes as the per-node base address. */
#define NPU_NODE(n, off) \
  (SOC_NPU_BASE + ((uint32_t)(n) << 12) + (uint32_t)(off))

/* docs/10 section 7.1 event word */
#define NPU_EV_SPIKE(id)  ((uint16_t)(0u << 14 | ((id) & 0x3FFu)))
#define NPU_EV_TICK       ((uint16_t)(1u << 14))
#define NPU_EV_SYNC(id)   ((uint16_t)(2u << 14 | ((id) & 0x3FFu)))

#endif /* SOC_NPUCFG_H */
