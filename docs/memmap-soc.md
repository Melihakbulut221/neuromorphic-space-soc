# SoC memory map v0.1

<!-- GENERATED FILE - edit regmap/memmap.yaml and run regmap/generate_memmap.py -->

The frozen physical address map of the SoC. The normative source
is `regmap/memmap.yaml`; this file is generated from it and
`sw/tests/test_memmap.py` fails if it is stale.

The interconnect this map sits on, and why it is not AMBA AHB, is
`docs/39-soc-bus-and-memory-map.md`. The proposal this freezes is
`docs/08-gr801-datasheet-notes.md` section 3.1.

## 1. Reset and trap vectors

| Property | Value | Why |
|---|---|---|
| `boot_addr_i` | `0xC0000000` | base of the ROM region |
| Reset vector | `0xC0000080` | Ibex resets to `{boot_addr_i[31:8], 8'h80}` |
| Trap vector alignment | 256 bytes | Ibex forces `mtvec[7:2]` to zero and has no direct mode |

Both are `docs/38-ibex-bringup.md` section 7.5 defects 3 and 4.
The generator refuses to emit a map whose boot region does not
contain the reset vector, is not executable, or is not
implemented, and refuses any region base that is not
256-byte aligned.

## 2. System bus regions

| Base | Last | Size | Name | Type | Attr | Status | Port | Description |
|---|---|---|---|---|---|---|---|---|
| `0x00000000` | `0x0000FFFF` | 64 KiB | RAM | memory | rwx | implemented | ram | System SRAM, 64 KiB. Data, stack and relocated .data live here |
| `0x10000000` | `0x1FFFFFFF` | 256 MiB | NPU | memory | rw | implemented | npu | NPU fabric window; per-node register windows and descriptor rings |
| `0xC0000000` | `0xC0001FFF` | 8 KiB | ROM | memory | rx | implemented | rom | On-chip boot ROM, 8 KiB. Holds the reset vector and .text |
| `0xD0000000` | `0xD1FFFFFF` | 32 MiB | QSPI3 | memory | rx | reserved | - | QSPI flash execute-in-place window, 3-byte addressing |
| `0xD8000000` | `0xDFFFFFFF` | 128 MiB | QSPI4 | memory | rx | reserved | - | QSPI flash execute-in-place window, 4-byte addressing |
| `0xE0000000` | `0xE000FFFF` | 64 KiB | CLINT | io | rw | implemented | clint | RISC-V core-local interruptor (msip, mtimecmp, mtime) |
| `0xF8000000` | `0xF83FFFFF` | 4 MiB | PLIC | io | rw | reserved | - | RISC-V platform interrupt controller, single hart, single context |
| `0xFE000000` | `0xFEFFFFFF` | 16 MiB | DEBUG | io | rw | reserved | - | RISC-V debug module |
| `0xFF900000` | `0xFF9FFFFF` | 1 MiB | APB | io | rw | implemented | apb | Peripheral bus bridge window, 1 MiB, 4 KiB slots |
| `0xFFFFF000` | `0xFFFFFFFF` | 4 KiB | PNP | io | r | implemented | pnp | System-bus device table; GRLIB PnP record layout, not AMBA AHB |

Address decode is a prefix compare: a region is selected when
`addr & MASK == BASE`. That is only a correct decode because every
region is a naturally aligned power of two, which the generator
enforces. Anything outside every region reaches the error slave
and returns a bus error, which the core takes as an access fault.

Provenance, one row per region:

| Name | Address taken from |
|---|---|
| RAM | RAM at 0x0 (NOELVSYS grip.pdf table 2293, GR740 UM 2.3) |
| NPU | project-specific (docs/08 section 3 row 21) |
| ROM | ROM at 0xC0000000 (NOELVSYS, GR740 UM 5.7.4) |
| QSPI3 | SPIMCTRL windows (GR716B UM 2.10) |
| QSPI4 | SPIMCTRL windows (GR716B UM 2.10) |
| CLINT | CLINT at 0xE0000000 (NOELVSYS) |
| PLIC | PLIC at 0xF8000000 (NOELVSYS) |
| DEBUG | debug module at 0xFE000000 (NOELVSYS) |
| APB | APB bridge 0 base 0xFF900000 (GR740 UM 2.3) |
| PNP | AHB PnP at 0xFFFFF000 (GRLIB grlib.pdf 5.3), layout only |

## 3. Peripheral bus slots

One 4 KiB slot per peripheral inside the 1 MiB
window at `0xFF900000`. The bridge decodes `PADDR[19:12]`.
Interrupt numbers are frozen here so the device table, the future
interrupt controller and the drivers cannot disagree
(`docs/08-gr801-datasheet-notes.md` section 4 item 7).

| Address | Slot | Name | IRQ | Line | Status | Description |
|---|---|---|---|---|---|---|
| `0xFF900000` | `0x000` | UART0 | 2 | 0 | implemented | Console UART, GRLIB APBUART register map, transmit only |
| `0xFF901000` | `0x001` | UART1 | 3 | 1 | reserved | Second UART |
| `0xFF902000` | `0x002` | GPIO | 4 | 2 | implemented | GRGPIO-style general purpose I/O, 16 pins |
| `0xFF908000` | `0x008` | TIMER0 | 8 | 3 | implemented | GPTIMER, last timer is the watchdog and is armed at reset |
| `0xFF909000` | `0x009` | TIMER1 | 12 | 4 | reserved | Second GPTIMER |
| `0xFF90D000` | `0x00D` | SPW | 16 | 5 | reserved | SpaceWire codec, GRSPW2-shaped registers, one DMA channel |
| `0xFF911000` | `0x011` | CAN | 18 | 6 | reserved | CAN 2.0B, SJA1000-shaped; documented divergence from GRCANFD |
| `0xFF912000` | `0x012` | SPI | 19 | 7 | reserved | SPICTRL-shaped SPI master |
| `0xFF913000` | `0x013` | I2C | 20 | 8 | reserved | I2CMST, the OpenCores I2C master register map |
| `0xFF914000` | `0x014` | QSPICTL | 21 | 9 | reserved | QSPI flash controller registers behind the XIP windows |
| `0xFF915000` | `0x015` | BUSSTAT | 22 | 10 | implemented | Fault counters and sticky status for the register file codec and the watchdog voter; AHBSTAT in spirit, not in name |
| `0xFF916000` | `0x016` | SCRUB | 23 | 11 | reserved | Memory scrubber control, MEMSCRUB-like |
| `0xFF917000` | `0x017` | BOOTREG | - | - | reserved | Bootstrap pin readback and boot report register, GRGPREG-like |
| `0xFF918000` | `0x018` | CLKGATE | - | - | reserved | Clock gate enable and status for NPU nodes and heavy peripherals |
| `0xFF919000` | `0x019` | NPUCFG | 24 | 12 | implemented | NPU fabric-level global configuration and status, and the AER event port; docs/51 |
| `0xFF9FF000` | `0x0FF` | APBPNP | - | - | implemented | Peripheral bus device table, two words per slot |

## 3a. Interrupts

Two namespaces, deliberately separate. **IRQ** is the GRLIB
plug-and-play source number carried in the identification word and
is what a platform interrupt controller would key on. **Line** is
the index of the Ibex fast local interrupt input the source is
physically wired to. Ibex gives each fast line a dedicated vector
and a fixed priority, so no controller is needed for the 13
sources this map defines.

`mcause` is the value software reads in the handler; `vector` is
the byte offset from `mtvec` at which the core enters. Both are
Ibex's, not this project's: a fast line *n* is interrupt ID
16+*n* and the core enters at `mtvec` + 4*ID.

| Source | IRQ | Line | `mcause` | Vector |
|---|---|---|---|---|
| UART0 | 2 | 0 | `0x80000010` | `mtvec+0x40` |
| UART1 | 3 | 1 | `0x80000011` | `mtvec+0x44` |
| GPIO | 4 | 2 | `0x80000012` | `mtvec+0x48` |
| TIMER0 | 8 | 3 | `0x80000013` | `mtvec+0x4C` |
| TIMER1 | 12 | 4 | `0x80000014` | `mtvec+0x50` |
| SPW | 16 | 5 | `0x80000015` | `mtvec+0x54` |
| CAN | 18 | 6 | `0x80000016` | `mtvec+0x58` |
| SPI | 19 | 7 | `0x80000017` | `mtvec+0x5C` |
| I2C | 20 | 8 | `0x80000018` | `mtvec+0x60` |
| QSPICTL | 21 | 9 | `0x80000019` | `mtvec+0x64` |
| BUSSTAT | 22 | 10 | `0x8000001A` | `mtvec+0x68` |
| SCRUB | 23 | 11 | `0x8000001B` | `mtvec+0x6C` |
| NPUCFG | 24 | 12 | `0x8000001C` | `mtvec+0x70` |

Core inputs that are not per-peripheral:

| Input | ID | `mcause` | Vector | Driven by |
|---|---|---|---|---|
| MSOFT | 3 | `0x80000003` | `mtvec+0x0C` | CLINT msip |
| MTIMER | 7 | `0x80000007` | `mtvec+0x1C` | CLINT mtime >= mtimecmp |
| MEXT | 11 | `0x8000000B` | `mtvec+0x2C` | unconnected; reserved for a PLIC |
| NMI | 31 | `0x8000001F` | `mtvec+0x7C` | watchdog stage 1 |

**2 of Ibex's 15 fast lines are unassigned** (13, 14). That number is the headroom the
platform-interrupt-controller decision is measured against:
`docs/40-interrupts-timers-watchdog.md` section 3 argues that a PLIC
buys nothing until it reaches zero, and the generator refuses a
`line` outside 0..14 so that exhausting it
is a build failure rather than a discovery.

The vector table is 32 entries of 4 bytes = 128 bytes at a 256-byte-aligned
base. Every synchronous exception enters at offset 0; only
interrupts are vectored. Ibex has no direct mode
(`docs/38-ibex-bringup.md` section 7.5 defect 3).

## 4. Device table

A read-only table at `0xFFFFF000`
in GRLIB's plug-and-play record *layout* (`grlib.pdf` section 5.3):
eight words per slave record from word `0x200`, master records from
word `0x000`, identification word
`vendor[31:24] device[23:12] version[9:5] irq[4:0]`, bank address
register `addr[31:20] prefetch[17] cacheable[16] mask[15:4] type[3:0]`.

**It is not an AMBA AHB plug-and-play table, because there is no AHB
in this SoC.** The layout is mirrored because a well-known layout is
what makes a device table readable; the bus underneath it is this
project's own. `docs/39-soc-bus-and-memory-map.md` section 3 is the
decision and section 7 states the claim this project does and does
not make.

Vendor code `0x09` is GRLIB's "various
contributions" bucket. The device IDs under it are assigned by this
project and are **not** registered with Frontgrade Gaisler, so a
GRLIB-aware tool will show a known vendor and an unrecognised
device. That is the truthful outcome; using Gaisler's own `0x01`
would not be.

**One field cannot express this map exactly.** An AHB-style bank
address register compares `addr[31:20]`, so its granularity is
1 MiB. These regions are smaller and their `mask` field is rounded
up to 1 MiB:

- RAM, 64 KiB at `0x00000000`
- ROM, 8 KiB at `0xC0000000`
- CLINT, 64 KiB at `0xE0000000`
- PNP, 4 KiB at `0xFFFFF000`

The exact byte size of every region is therefore carried in
user-defined word 1 of its record, which GRLIB leaves free, and the
region's `implemented`/`reserved` status in user-defined word 2. A
reader that trusts only the bank address register will over-state
three region sizes; a reader that uses word 1 will not.

