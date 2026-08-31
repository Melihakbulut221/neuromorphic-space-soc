/* Register offsets for the blocks docs/40-interrupts-timers-watchdog.md
 * adds, and the machine-mode CSR bit positions the tests use.
 *
 * WHY THESE ARE LITERALS AND THE ADDRESSES ARE NOT. Every BASE address
 * in this file comes from soc_memmap.h, which regmap/generate_memmap.py
 * emits from regmap/memmap.yaml -- so no address is written down twice
 * and moving a block in the map moves it here. The OFFSETS WITHIN a
 * block are a different thing: they are that block's register map, they
 * live in its RTL header, and the map has never described them. This is
 * the same split hw/soc/tb/sw/test_ibex.c already uses for the UART
 * (SOC_UART0_BASE from the map, +0x00/+0x04/+0x08/+0x0C from
 * grip.pdf table 126).
 *
 * The CLINT offsets are the standard RISC-V ones; the GPTIMER offsets
 * are GRLIB's (grip.pdf table 463); WDOGSTAT and the key are this
 * project's documented extension, hw/soc/rtl/soc_wdog.v W5.
 */
#ifndef SOC_TIMERS_H
#define SOC_TIMERS_H

#include "soc_memmap.h"

/* ---- CLINT, hw/soc/rtl/soc_clint.v ---------------------------------- */
#define CLINT_MSIP      (SOC_CLINT_BASE + 0x0000u)
#define CLINT_MTIMECMPL (SOC_CLINT_BASE + 0x4000u)
#define CLINT_MTIMECMPH (SOC_CLINT_BASE + 0x4004u)
#define CLINT_MTIMEL    (SOC_CLINT_BASE + 0xBFF8u)
#define CLINT_MTIMEH    (SOC_CLINT_BASE + 0xBFFCu)
/* An offset the block does not implement. soc_clint.v faults it. */
#define CLINT_UNMAPPED  (SOC_CLINT_BASE + 0x0100u)

/* ---- GPTIMER, hw/soc/rtl/soc_gptimer.v ------------------------------ */
#define GPT_SCALER      (SOC_TIMER0_BASE + 0x000u)
#define GPT_SCRELOAD    (SOC_TIMER0_BASE + 0x004u)
#define GPT_CONFIG      (SOC_TIMER0_BASE + 0x008u)
#define GPT_TIMER(n)    (SOC_TIMER0_BASE + 0x10u * (n))
#define GPT_CNT(n)      (GPT_TIMER(n) + 0x0u)
#define GPT_RLD(n)      (GPT_TIMER(n) + 0x4u)
#define GPT_CTRL(n)     (GPT_TIMER(n) + 0x8u)

/* GRLIB timer control bits, grip.pdf table 463. */
#define GPT_EN  (1u << 0)
#define GPT_RS  (1u << 1)
#define GPT_LD  (1u << 2)
#define GPT_IE  (1u << 3)
#define GPT_IP  (1u << 4)
#define GPT_CH  (1u << 5)

/* Two general timers plus the watchdog: NGEN = 2 in soc_top.v, so the
 * watchdog is timer 3 and WDOGSTAT sits one slot past it. */
#define GPT_NGEN      2
#define WDOG_TIMER    (GPT_NGEN + 1)
#define WDOG_CNT      GPT_CNT(WDOG_TIMER)
#define WDOG_RLD      GPT_RLD(WDOG_TIMER)
#define WDOG_CTRL     GPT_CTRL(WDOG_TIMER)
#define WDOG_STAT     (SOC_TIMER0_BASE + 0x10u * (WDOG_TIMER + 1))

/* Every write to a watchdog register carries this in bits 31:16 or has
 * no effect at all (soc_wdog.v W5). */
#define WDOG_KEY      0xA51Fu
#define WDOG_W(v)     ((WDOG_KEY << 16) | ((v) & 0xFFFFu))

/* WDOGSTAT read fields. */
#define WDOG_ST_NMI       (1u << 0)
#define WDOG_ST_WDOGRST   (1u << 1)
#define WDOG_ST_ESCALATED (1u << 2)
#define WDOG_ST_DISABLED  (1u << 3)
#define WDOG_ST_RSTCNT(v) (((v) >> 8) & 0xFFu)

/* ---- machine CSR bits ----------------------------------------------- */
#define MSTATUS_MIE (1u << 3)
#define MIE_MSIE    (1u << SOC_IRQID_MSOFT)
#define MIE_MTIE    (1u << SOC_IRQID_MTIMER)
#define MIE_FAST(l) (1u << (SOC_FAST_IRQ_BASE + (l)))

#endif /* SOC_TIMERS_H */
