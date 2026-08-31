/* GENERATED FILE - edit regmap/memmap.yaml and run regmap/generate_memmap.py */
#ifndef SOC_MEMMAP_H
#define SOC_MEMMAP_H

#define SOC_MEMMAP_VERSION "0.1"
#define SOC_VENDOR_ID    0x09u
#define SOC_BOOT_ADDR    0xC0000000u
#define SOC_RESET_VECTOR 0xC0000080u

#define SOC_RAM_BASE 0x00000000u
#define SOC_RAM_SIZE 0x00010000u
#define SOC_NPU_BASE 0x10000000u
#define SOC_NPU_SIZE 0x10000000u
#define SOC_ROM_BASE 0xC0000000u
#define SOC_ROM_SIZE 0x00002000u
#define SOC_QSPI3_BASE 0xD0000000u
#define SOC_QSPI3_SIZE 0x02000000u
#define SOC_QSPI4_BASE 0xD8000000u
#define SOC_QSPI4_SIZE 0x08000000u
#define SOC_CLINT_BASE 0xE0000000u
#define SOC_CLINT_SIZE 0x00010000u
#define SOC_PLIC_BASE 0xF8000000u
#define SOC_PLIC_SIZE 0x00400000u
#define SOC_DEBUG_BASE 0xFE000000u
#define SOC_DEBUG_SIZE 0x01000000u
#define SOC_APB_BASE 0xFF900000u
#define SOC_APB_SIZE 0x00100000u
#define SOC_PNP_BASE 0xFFFFF000u
#define SOC_PNP_SIZE 0x00001000u

#define SOC_UART0_BASE 0xFF900000u
#define SOC_UART1_BASE 0xFF901000u
#define SOC_GPIO_BASE 0xFF902000u
#define SOC_TIMER0_BASE 0xFF908000u
#define SOC_TIMER1_BASE 0xFF909000u
#define SOC_SPW_BASE 0xFF90D000u
#define SOC_CAN_BASE 0xFF911000u
#define SOC_SPI_BASE 0xFF912000u
#define SOC_I2C_BASE 0xFF913000u
#define SOC_QSPICTL_BASE 0xFF914000u
#define SOC_BUSSTAT_BASE 0xFF915000u
#define SOC_SCRUB_BASE 0xFF916000u
#define SOC_BOOTREG_BASE 0xFF917000u
#define SOC_CLKGATE_BASE 0xFF918000u
#define SOC_NPUCFG_BASE 0xFF919000u
#define SOC_APBPNP_BASE 0xFF9FF000u

#define SOC_APB_BASE 0xFF900000u

/* Interrupts. SOC_IRQ_<NAME> is the mcause value software reads in
   the handler, SOC_VEC_<NAME> the byte offset from mtvec at which
   the core enters, and SOC_IRQLINE_<NAME> the bit to set in mie.
   All three are Ibex's arithmetic on the `line` field of
   regmap/memmap.yaml, so the vector table in crt0.S, the RTL
   wiring and the C tests cannot disagree about any of them. */
#define SOC_FAST_IRQ_BASE  16u
#define SOC_FAST_IRQ_COUNT 15u
#define SOC_VECTOR_ENTRIES 32u
#define SOC_VECTOR_BYTES   128u

#define SOC_IRQLINE_UART0    0u
#define SOC_IRQ_UART0    0x80000010u
#define SOC_VEC_UART0    0x40u
#define SOC_IRQLINE_UART1    1u
#define SOC_IRQ_UART1    0x80000011u
#define SOC_VEC_UART1    0x44u
#define SOC_IRQLINE_GPIO     2u
#define SOC_IRQ_GPIO     0x80000012u
#define SOC_VEC_GPIO     0x48u
#define SOC_IRQLINE_TIMER0   3u
#define SOC_IRQ_TIMER0   0x80000013u
#define SOC_VEC_TIMER0   0x4Cu
#define SOC_IRQLINE_TIMER1   4u
#define SOC_IRQ_TIMER1   0x80000014u
#define SOC_VEC_TIMER1   0x50u
#define SOC_IRQLINE_SPW      5u
#define SOC_IRQ_SPW      0x80000015u
#define SOC_VEC_SPW      0x54u
#define SOC_IRQLINE_CAN      6u
#define SOC_IRQ_CAN      0x80000016u
#define SOC_VEC_CAN      0x58u
#define SOC_IRQLINE_SPI      7u
#define SOC_IRQ_SPI      0x80000017u
#define SOC_VEC_SPI      0x5Cu
#define SOC_IRQLINE_I2C      8u
#define SOC_IRQ_I2C      0x80000018u
#define SOC_VEC_I2C      0x60u
#define SOC_IRQLINE_QSPICTL  9u
#define SOC_IRQ_QSPICTL  0x80000019u
#define SOC_VEC_QSPICTL  0x64u
#define SOC_IRQLINE_BUSSTAT  10u
#define SOC_IRQ_BUSSTAT  0x8000001Au
#define SOC_VEC_BUSSTAT  0x68u
#define SOC_IRQLINE_SCRUB    11u
#define SOC_IRQ_SCRUB    0x8000001Bu
#define SOC_VEC_SCRUB    0x6Cu
#define SOC_IRQLINE_NPUCFG   12u
#define SOC_IRQ_NPUCFG   0x8000001Cu
#define SOC_VEC_NPUCFG   0x70u

#define SOC_IRQID_MSOFT    3u
#define SOC_IRQ_MSOFT    0x80000003u
#define SOC_VEC_MSOFT    0x0Cu
#define SOC_IRQID_MTIMER   7u
#define SOC_IRQ_MTIMER   0x80000007u
#define SOC_VEC_MTIMER   0x1Cu
#define SOC_IRQID_MEXT     11u
#define SOC_IRQ_MEXT     0x8000000Bu
#define SOC_VEC_MEXT     0x2Cu
#define SOC_IRQID_NMI      31u
#define SOC_IRQ_NMI      0x8000001Fu
#define SOC_VEC_NMI      0x7Cu

/* Device table words the program checks. Both are generated from
   the same source as the ROM contents, so a table that drifts from
   the map fails in simulation rather than in a driver. */
#define SOC_PNP_IDENT_WORD  0x4E530001u
#define SOC_PNP_ENDIAN_WORD 0x00000001u
#define SOC_PNP_IDENT_OFF   0xFF0u
#define SOC_PNP_ENDIAN_OFF  0xFF4u

#endif /* SOC_MEMMAP_H */
