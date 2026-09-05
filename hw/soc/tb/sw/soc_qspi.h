/* Register offsets, fields and the flash command set for the QSPI
 * controller docs/66 adds, hw/soc/rtl/soc_qspi.v.
 *
 * The same split soc_timers.h and soc_gpio.h state: the BASE comes from
 * soc_memmap.h, generated from regmap/memmap.yaml, so no address is
 * written down twice; the OFFSETS within the block are the block's own
 * register map, which its header states and the map has never
 * described.
 *
 * The command constants are the Winbond W25Q128JV's, datasheet Revision
 * M section 8.1.2, the part hw/soc/tb/flash_w25q128jv.v models. The
 * controller itself knows nothing of them.
 */
#ifndef SOC_QSPI_H
#define SOC_QSPI_H

#include "soc_memmap.h"

#define QSPI_CONF   (SOC_QSPICTL_BASE + 0x00u)  /* rw  DIV, CS         */
#define QSPI_CTRL   (SOC_QSPICTL_BASE + 0x04u)  /* rw  RST, IEN        */
#define QSPI_STAT   (SOC_QSPICTL_BASE + 0x08u)  /* r/w1c               */
#define QSPI_RX     (SOC_QSPICTL_BASE + 0x0Cu)  /* r   clears DR       */
#define QSPI_TX     (SOC_QSPICTL_BASE + 0x10u)  /* w                   */
#define QSPI_CMD    (SOC_QSPICTL_BASE + 0x14u)  /* rw  write starts    */
#define QSPI_ADDR   (SOC_QSPICTL_BASE + 0x18u)  /* rw  24 bits         */

#define QSPI_CONF_DIV(d)   ((uint32_t)(d) & 0xFu)
#define QSPI_CONF_CS(c)    (((uint32_t)(c) & 0xFu) << 8)

#define QSPI_CTRL_RST      (1u << 0)
#define QSPI_CTRL_IEN      (1u << 1)

#define QSPI_ST_BUSY       (1u << 0)
#define QSPI_ST_DR         (1u << 1)
#define QSPI_ST_DONE       (1u << 2)
#define QSPI_ST_LOST       (1u << 3)
#define QSPI_ST_TXE        (1u << 4)

#define QSPI_CMD_OP(o)     ((uint32_t)(o) & 0xFFu)
#define QSPI_CMD_DUMMY(n)  (((uint32_t)(n) & 0xFu) << 8)
#define QSPI_CMD_ADDR      (1u << 12)
#define QSPI_CMD_AQUAD     (1u << 13)
#define QSPI_CMD_DQUAD     (1u << 14)
#define QSPI_CMD_WRITE     (1u << 15)
#define QSPI_CMD_LEN(n)    (((uint32_t)(n) & 0xFFFFu) << 16)

/* W25Q128JV instructions, datasheet 8.1.2, with the dummy clocks each
 * read needs and the lanes it uses. */
#define FLASH_OP_WREN      0x06u   /* 8.2.1  Write Enable                */
#define FLASH_OP_VWREN     0x50u   /* 8.2.2  Volatile SR Write Enable    */
#define FLASH_OP_RDSR1     0x05u   /* 8.2.4  BUSY is bit 0, WEL bit 1    */
#define FLASH_OP_RDSR2     0x35u   /* 8.2.4  QE is bit 1                 */
#define FLASH_OP_WRSR2     0x31u   /* 8.2.5  one data byte               */
#define FLASH_OP_READ      0x03u   /* 8.2.6  1-1-1, no dummy             */
#define FLASH_OP_FAST      0x0Bu   /* 8.2.7  1-1-1, 8 dummy              */
#define FLASH_OP_QOUT      0x6Bu   /* 8.2.9  1-1-4, 8 dummy, needs QE    */
#define FLASH_OP_QIO       0xEBu   /* 8.2.11 1-4-4, 2 mode + 4 dummy     */
#define FLASH_OP_JEDEC     0x9Fu   /* 8.2.27 EF 40 18                    */
#define FLASH_OP_RSTEN     0x66u   /* 8.2.43                             */
#define FLASH_OP_RST       0x99u   /* 8.2.43                             */

#define FLASH_JEDEC_WORD   0x001840EFu   /* EF, 40, 18 in RX's lanes     */
#define FLASH_SR2_QE       (1u << 1)

/* The read commands as CMD words, LEN added by the caller. */
#define FLASH_CMD_READ     (QSPI_CMD_OP(FLASH_OP_READ) | QSPI_CMD_ADDR)
#define FLASH_CMD_FAST     (QSPI_CMD_OP(FLASH_OP_FAST) | QSPI_CMD_ADDR \
                            | QSPI_CMD_DUMMY(8))
#define FLASH_CMD_QOUT     (QSPI_CMD_OP(FLASH_OP_QOUT) | QSPI_CMD_ADDR \
                            | QSPI_CMD_DUMMY(8) | QSPI_CMD_DQUAD)
#define FLASH_CMD_QIO      (QSPI_CMD_OP(FLASH_OP_QIO) | QSPI_CMD_ADDR \
                            | QSPI_CMD_AQUAD | QSPI_CMD_DUMMY(6) \
                            | QSPI_CMD_DQUAD)

#endif /* SOC_QSPI_H */
