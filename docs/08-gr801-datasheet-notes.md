# GR801 datasheet notes: public documentation status and Gaisler SoC conventions

Purpose: establish what GR801 documentation actually exists publicly, extract
the programmer-visible conventions GR801 will almost certainly inherit from
the Gaisler/GRLIB SoC lineage, and turn both into a concrete "GR801-proximity
checklist" for this project's bus, memory map, and register-map design.

Claims are tagged: **[fact]** — stated in a cited public document;
**[inference]** — derived from Gaisler's documented conventions but not
stated for GR801 specifically; **[estimate/proposal]** — this project's
engineering judgment.

Research date: 2026-08-24.

---

## 1. Does a real GR801 datasheet exist publicly?

**No. [fact]** As of 2026-08-24, the GR801 product page
(https://www.gaisler.com/products/gr801) lists exactly one document in its
downloads section: the **GR801 Product Brief**, revision April 2026, dated
2026-04-23
(https://download.gaisler.com/products/gr801/doc/Product_Brief_GR801.pdf).
It is filed under the site's "data sheet and user's manual" category, but it
is a two-page marketing brief, not a datasheet. No advance datasheet, no
advance user's manual, and no GR801-specific application notes are public.
The page carries the standard disclaimer that it "describes a running
development and no guarantees can be given concerning future product
availability."

For calibration, sibling products at a comparable maturity show the same
pattern: the GR765 (octa-core LEON5FT/NOEL-V, also "under development",
https://www.gaisler.com/products/gr765) likewise exposes only a product
brief (https://download.gaisler.com/products/gr765/doc/Product_Brief_GR765.pdf),
while shipping parts expose full manuals — GR740 has a 506-page combined
data sheet and user's manual, and GR716B has a 773-page advance user's
manual. **[fact]** The expectation is therefore that a GR801 advance
datasheet/user's manual will appear on the same downloads page when the
design matures; until then, the deepest public technical source for GR801
remains the product brief. **[inference]**

A local copy of the brief is archived at
`/home/hasanmelih/Downloads/Product_Brief_GR801.pdf`; its content is
summarized in `docs/00-reference-brief.md` and decomposed in
`docs/01-reference-decomposition.md` and is not repeated here.

### 1.1 What the secondary public record adds

Searched: Gaisler/Frontgrade press releases, BrainChip announcements,
SNSA/ESA program pages, and conference channels (DASIA, OBDP, AMICSA
2025-2026). Findings:

- **BrainChip partnership and IP license. [fact]** Frontgrade Gaisler first
  announced a collaboration to explore integrating Akida into
  fault-tolerant space-grade microprocessors
  (https://www.gaisler.com/news-events/brainchip-and-frontgrade-gaisler-to-augment-space-grade-microprocessors-with-ai-capabilities;
  the page shows no date), then formally licensed the Akida IP in December
  2024 (https://www.gaisler.com/news-events/frontgrade-gaisler-licenses-brainchips-akida-ip-to-deploy-ai-chips-into-space;
  date per the syndicated copy,
  https://www.nasdaq.com/press-release/frontgrade-gaisler-licenses-brainchips-akida-ip-deploy-ai-chips-space-2024-12-15).
- **GRAIN line launch and SNSA contract, 2025-04-02. [fact]** GRAIN =
  "Gaisler Research Artificial Intelligence NOEL-V". The Swedish National
  Space Agency awarded a contract to commercialize GR801 as the first
  neuromorphic SoC for space; KTH is building a demonstration application
  with a neuromorphic sensor connected to GR801
  (https://www.gaisler.com/news-events/frontgrade-gaisler-launches-new-grain-line-and-wins-snsa-contract-to-commercialize-first-energy-efficient-neuromorphic-ai-for-space-applications;
  also https://riscv.org/blog/frontgrade-gaisler-to-commercialise-neuromorphic-ai-for-space/).
- **ESA NeuroSpace activity 4000145267 (completed). [fact]** An ESA
  Discovery early-technology activity with Frontgrade Gaisler as prime:
  FPGA prototyping of neuromorphic IP integrated with a rad-hard
  microprocessor, targeting sub-watt to few-watt inference against the
  40-100 W of conventional rad-tolerant AI solutions
  (https://activities.esa.int/4000145267). No architecture detail beyond
  the brief is disclosed.
- **VAIAS project, announced 2025-12-09. [fact]** Rapidity Space (with RISE,
  ESA Phi-Lab Sweden, Vinnova) is building a neuromorphic event-based
  semantic segmentation demonstrator on GR801 and extending LLVM with
  improved SIMD/SWAR support and NOEL-V optimizations
  (https://www.gaisler.com/news-events/rapidity-space-and-frontgrade-gaisler-collaborate-in-the-vaias-project-to-advance-energy-efficient-and-fault-tolerant-ai-for-space-missions).
  Practical signal: the management CPU is expected to carry real pre/post-
  processing load, not only configuration. **[inference]**
- **Conference papers: none found. [fact as of the search date]** No
  DASIA/OBDP/AMICSA 2025-2026 paper with register-level or block-level GR801
  detail surfaced in web searches. If OBDP 2026 proceedings appear later,
  they are the most likely venue for first implementation details.
  **[estimate]**

Bottom line: nothing public goes deeper than the product brief on GR801
itself. The deepest usable information is indirect — Gaisler's own SoC
conventions, which are extensively documented for GR740, GR716B, and GRLIB,
and which GR801 as a GRLIB-based NOEL-V design will follow. **[inference]**

---

## 2. Gaisler SoC conventions from the closest documented parts

Sources used throughout this section:

- **GR740 Data Sheet and User's Manual**, rev 2.10, Feb 2026 (quad-core
  LEON4FT):
  https://download.gaisler.com/products/gr740/doc/GR740-UM-DS-2-10.pdf
- **GR716B Advanced User's Manual**, rev 0.11, Jul 2026 (LEON3FT
  microcontroller):
  https://download.gaisler.com/products/gr716b/doc/GR716B-UM-0-11-2026-07-06.pdf
- **GR765 Product Brief**, April 2026 (octa-core, NOEL-V mode):
  https://download.gaisler.com/products/gr765/doc/Product_Brief_GR765.pdf
- **GRLIB IP Library User's Manual** (grlib.pdf), version 2026.2, Jun 2026:
  https://download.gaisler.com/products/GRLIB/doc/grlib.pdf
- **GRLIB IP Core User's Manual** (grip.pdf, 2449 pages), version 2026.2,
  Jun 2026, including the NOELVSYS subsystem chapter:
  https://download.gaisler.com/products/GRLIB/doc/grip.pdf

GR716B is SPARC-based, but its bus, peripheral, and boot conventions are
ISA-independent GRLIB conventions; the NOELVSYS chapter of grip.pdf gives
the NOEL-V-specific counterparts that GR801 (a GRAIN "NOEL-V" product by
name) will use. **[inference]**

### 2.1 Bus architecture and plug-and-play discovery [fact]

All Gaisler SoCs use AMBA 2.0 AHB for the system bus and APB for
peripherals, with GRLIB's plug-and-play (PnP) extension (grlib.pdf sections
5.3 and 5.5):

- **AHB PnP:** a read-only configuration table at a fixed address,
  typically **0xFFFFF000**. Master records occupy 0xFFFFF000-0xFFFFF7FF,
  slave records 0xFFFFF800-0xFFFFFFFC; each record is eight 32-bit words:
  one identification register — **vendor ID [31:24], device ID [23:12],
  version [9:5], IRQ [4:0]** — three user-defined words, and four bank
  address registers (BARs) with ADDR [31:20], prefetchable/cacheable flags,
  MASK [15:4], and TYPE [3:0] (0001 = APB I/O, 0010 = AHB memory,
  0011 = AHB I/O). Capacity: 64 masters, 63-64 slaves.
- **Top of the AHB PnP area:** word at 0xFFFFFFF0 holds the GRLIB build ID
  (low half-word) and a **SoC device ID** (high half-word); bit 0 of
  0xFFFFFFF4 reports endianness (0 = big endian, 1 = little endian).
- **APB PnP:** per APB bridge, a table at bridge base + 0xFF000
  ("0x---FF000"), two words per slave (identification register + one BAR);
  APB decode compares HADDR(19:8) against ADDR/MASK, so the minimum APB
  slot is 256 bytes and each bridge spans 1 MB of AHB space.
- **Vendor IDs** are assigned by Gaisler in `lib/grlib/amba/devices.vhd`:
  Frontgrade Gaisler 0x01, ESA 0x04, OpenCores.org 0x08, "Various
  contributions" 0x09, among others.
- Accesses to unused AHB space return AMBA ERROR; accesses to unoccupied
  ranges behind an APB bridge have no effect (GR740 UM section 2.3).

### 2.2 Memory map layout style [fact]

Three documented maps establish the family style:

- **GR740** (UM section 2.3): RAM low, ROM high, peripherals at top.
  SDRAM behind L2 at 0x00000000-0x7FFFFFFF; **PROM at
  0xC0000000-0xCFFFFFFF**; memory-mapped I/O area 0xD0000000; APB bridge 0
  at **0xFF900000** (APBUART0 at 0xFF900000, APBUART1 0xFF901000, GRGPIO0
  0xFF902000, IRQ(A)MP 0xFF904000, GPTIMER0-4 0xFF908000-0xFF90C000,
  SpaceWire router AMBA interfaces 0xFF90D000-0xFF910FFF, GRETH
  0xFF940000, APB PnP 0xFF9FF000); APB bridge 1 at 0xFFA00000 (GRCAN0/1
  0xFFA01000/0xFFA02000, SPICTRL 0xFFA03000, GRCLKGATE 0xFFA04000,
  AHBSTAT 0xFFA06000, GRGPREG bootstrap register 0xFFA09000); AHB PnP at
  0xFFFFF000. The UM explicitly notes (section 5.7.4) that older LEON
  systems used ROM at 0x0 / RAM at 0x40000000 while GR740 uses **RAM at
  0x0 / ROM at 0xC0000000**.
- **GR716B** (UM section 2.10), the microcontroller-class map: internal
  boot PROM (AHBROM) at 0x00000000; external PROM 0x01000000; **SPI
  memories memory-mapped** at 0x02000000/0x04000000 (3-byte address) and
  0x10000000/0x18000000 (4-byte address); local data RAM 0x30000000, local
  instruction RAM 0x31000000; external SRAM 0x40000000; peripherals on APB
  bridges at 0x80000000+ (IRQAMP 0x80002000, GPTIMER0 with watchdog
  0x80003000, AHBUART remote-access debug UART 0x8000F000, APBUART0-5 from
  0x80300000, SPICTRL0/1 0x80309000/0x8030A000, GRGPIO 0x8030C000).
- **NOELVSYS**, the packaged NOEL-V system-on-chip subsystem GR801's CPU
  side descends from (grip.pdf chapter 116, table 2293): main memory
  (RAM) "typically at 0x00000000, ROM at 0xC0000000"; **core-local
  interrupt controller (CLINT) at 0xE0000000**; **platform interrupt
  controller (PLIC) at 0xF8000000**; **console APBUART at 0xFF900000**;
  **GPTIMER at 0xFF908000**; debug module 0xFE000000; AHB trace buffer
  0xFFF00000; AMBA PnP at 0xFFFFF000. Standard peripherals bundled with
  every NOELVSYS: CLINT/PLIC, GPTIMER, console APBUART, plus a GRVERSION
  register slave.

### 2.3 Register conventions [fact]

- Registers are 32-bit, memory-mapped, one 256 B-minimum (typically 4 KB)
  APB slot per peripheral instance; multiple instances are consecutive
  slots (six APBUARTs at 0x80300000 + n*0x1000 in GR716B).
- LEON systems are big-endian SPARC; NOEL-V systems are little-endian
  RISC-V, and the PnP area advertises endianness (grlib.pdf section 5.3).
  GR801 as a NOEL-V part will be little-endian. **[inference]**
- Version discovery is via the PnP version field per core plus the SoC
  device ID / build ID words, not via per-peripheral ID registers.
- Fault visibility convention: an **AHBSTAT** core per bus latches the
  address/master/type of correctable and uncorrectable errors and raises
  an interrupt (present in GR740 at 0xFFA06000/0xFFA07000 and GR716B at
  0x8000A000/0x80306000); memory scrubbers (MEMSCRUB in GR740 at
  0xFFE01000) are separate cores with their own register slots.

### 2.4 Boot and ROM flow [fact]

- **GR716B** (UM sections 2.2.5-2.2.6 and chapter 51) is the family's
  richest boot reference: an on-chip **Boot ROM at 0x00000000** runs at
  reset, in three phases — processor module initialization (RAM self-test,
  boot report), **standby mode** (waiting for remote boot over SpaceWire,
  CANopen, UART, SPI, or I2C), and a **load sequence** that validates an
  Application Software (ASW) image with header, code, data checksum, and
  header checksum, optionally from redundant memories, then jumps to it.
  The watchdog is staged through the whole flow (separate boot, remote,
  restart, and application timeouts). Bootstrap pins select boot source,
  self-test, and can bypass the ROM entirely ("direct boot"), in which
  case the reset address is taken from bootstraps.
- **GR740** has no boot ROM: the processors reset with PC = 0xC0000000
  (external PROM), overridable via processor boot-address registers, and
  support SpaceWire RMAP-based remote boot with the processor held via
  BREAK (UM sections 6.2.18 and 2.2; application note GRLIB-AN-0002).
- **GR765** advertises **GRBOOT**, a qualified bootloader with standby
  support, plus optional hardware-authenticated boot (ECDSA + ML-DSA
  hybrid), with QSPI and PROM as boot memories (product brief). In RISC-V
  mode it supports "any debug solution supporting the RISC-V debug
  specification" — i.e., the NOEL-V line pairs GRLIB conventions with
  standard RISC-V debug rather than the SPARC DSU.

### 2.5 GRLIB peripheral register interfaces [fact]

All from grip.pdf version 2026.2; offsets are within the peripheral's APB
slot. These are the register maps GR801's peripherals will expose, since
the same cores (or their FT variants) are instantiated across the whole
product family. **[inference]**

| Core | Register map (offsets) |
|---|---|
| **APBUART** (table 126) | 0x00 data, 0x04 status, 0x08 control, 0x0C scaler, 0x10 FIFO debug, 0x14 FIFO debug control, 0x18 capability |
| **GPTIMER** (table 463) | 0x00 scaler value, 0x04 scaler reload, 0x08 configuration, 0x0C latch configuration; per timer n: 0xn0 counter, 0xn4 reload, 0xn8 control, 0xnC latch. The **last timer acts as the watchdog**, enabled at reset, driving the WDOG output (section 40.2) |
| **GRGPIO** (table 923) | 0x00 data, 0x04 output, 0x08 direction, 0x0C interrupt mask, 0x10 polarity, 0x14 edge, 0x18 bypass, 0x1C capability; optional interrupt-map registers from 0x20 and logical-OR/AND write aliases from 0x50 for atomic bit set/clear |
| **SPICTRL** (table 2377) | 0x00/0x04 capability, 0x20 mode, 0x24 event, 0x28 mask, 0x2C command, 0x30 transmit, 0x34 receive, 0x38 slave select |
| **I2CMST** (table 1869) | 0x00 clock prescale, 0x04 control, 0x08 transmit/receive (W/R), 0x0C command/status (W/R) — the OpenCores I2C-master register map |
| **GRSPW2** (table 1392) | 0x00 CTRL, 0x04 STS, 0x08 default address, 0x0C clock divisor, 0x10 destination key, 0x14 time-code; per DMA channel n (0x20 + n*0x20): DMACTRL, DMAMAXLEN, DMATXDESC, DMARXDESC, DMAADDR — descriptor-table DMA in memory |
| **GRCANFD** (table 611) | 0x000 configuration, 0x004 status, 0x008 control, capability, SYNC filters; 0x040 nominal / 0x044 data bit-rate; interrupt block at 0x100 (pending/mask/clear); TX channel at 0x200 and RX channel at 0x300 as circular DMA buffers (control, address, size, write pointer, read pointer, interrupt) |
| **SPIMCTRL** (GR716B usage) | SPI memory controller that maps flash contents directly into AHB address windows (3-byte and 4-byte address regions) and supports boot from SPI memory |
| **GRETH** | AHB-master Ethernet MAC with descriptor-based DMA (listed for completeness; Ethernet is out of scope per docs/01 and docs/03) |

---

## 3. GR801-proximity checklist

Standing directive: stay architecturally close to GR801. GR801's own
programmer-visible interface is unpublished, so "close" operationally means
**close to the documented GRLIB/NOELVSYS conventions of section 2**, which
is what GR801 software (GRBOOT-style loaders, GRMON-style tools, driver
stacks) is built against. **[inference]** Each row: **mirror** (adopt the
convention as documented), **simplify** (keep the software-visible shape,
cut internals), or **diverge** (documented departure). Effort notes are
rough RTL+verification estimates for this project's scale. **[estimate]**

| # | Convention | Decision | Justification and effort |
|---|---|---|---|
| 1 | AMBA AHB system bus + APB peripheral bus | **Simplify** | Single AHB-lite layer (CPU + NPU DMA + debug masters) with one AHB/APB bridge instead of GR740's five-bus hierarchy; APB slave semantics identical, so drivers port unchanged. Effort: moderate — bus fabric is on the critical path of everything. |
| 2 | GRLIB AHB PnP table at 0xFFFFF000, 8-word records | **Mirror** (as static ROM) | A constant-value read-only table is nearly free in gates and makes the SoC discoverable by GRLIB-aware tools and our own scripts. Generate from the SoC config, do not hand-maintain. Effort: low. |
| 3 | APB PnP at bridge base + 0xFF000, 2-word records | **Mirror** (static) | Same argument; one table for the single bridge. Effort: low. |
| 4 | Vendor/device ID scheme | **Simplify** | Real vendor IDs are assigned by Gaisler; using 0x01 (Gaisler) would be misrepresentation. Use an unassigned/contrib vendor code (e.g. 0x09 "Various contributions" or a clearly-project-local value) with project-assigned device IDs, documented in the register map. Effort: nil. |
| 5 | SoC device ID + build ID at 0xFFFFFFF0, endianness word at 0xFFFFFFF4 | **Mirror** | Cheap, and gives fault-injection campaigns and boot software a single authoritative identity/version word. Effort: nil. |
| 6 | Memory map skeleton: RAM at 0x0, ROM/PROM at 0xC0000000, peripherals at top of the 4 GB space | **Mirror** | Adopt the NOELVSYS map (grip.pdf table 2293) as the frame; see section 3.1. Costs nothing and keeps bare-metal conventions (linker scripts, crt0) aligned with the NOEL-V world. Effort: nil — it is a decision, not a block. |
| 7 | Interrupt architecture: RISC-V CLINT at 0xE0000000 + PLIC at 0xF8000000 (NOELVSYS) | **Simplify** | Keep the standard RISC-V programming model and the NOELVSYS addresses: CLINT (msip, mtimecmp, mtime) is mandatory for the RV32 core; implement a minimal PLIC (single hart, single context, fixed 32 sources). Do not adopt the SPARC-side IRQ(A)MP. Effort: low-moderate; reuse of an existing Verilog CLINT/PLIC is likely. |
| 8 | Timer/watchdog: GPTIMER register map, last-timer-is-watchdog, watchdog live at reset | **Mirror** | The convention (scaler + per-timer counter/reload/control at 0xn0) is trivially implementable and encodes a good safety default: watchdog armed from reset, staged timeouts through boot as in GR716B. Effort: low. |
| 9 | UART: APBUART register map (data/status/control/scaler) | **Mirror** | Simplest core in the set; implementing to the APBUART map costs no more than inventing one and keeps console tooling compatible. FIFO-debug and capability registers optional. Effort: low. |
| 10 | GPIO: GRGPIO map (data/output/direction/mask/polarity/edge) | **Mirror** | First six registers cover the GR801-class 16x GPIO; add the logical-OR/AND aliases only if atomic bit ops prove necessary. Effort: low. |
| 11 | SPI master: SPICTRL map (mode/event/mask/command/tx/rx) | **Mirror** (subset) | Register-compatible subset without automated periodic transfers (AM registers). Effort: low. |
| 12 | I2C: I2CMST = OpenCores I2C register map | **Mirror** | GRLIB's own I2CMST is the OpenCores map, so adopting the actual OpenCores core (or a clean equivalent) is simultaneously GR801-proximate and open-source-native. Effort: low. |
| 13 | SpaceWire: GRSPW2 register skeleton + descriptor-table DMA | **Simplify** | Own DS codec (per docs/03), but expose GRSPW2-shaped registers: CTRL/STS/DEFADDR/CLKDIV/DKEY/TC and **one** DMA channel (DMACTRL/MAXLEN/TXDESC/RXDESC). Keeps a future RMAP/router path open and lets GRSPW driver knowledge transfer. Effort: moderate — the DMA engine dominates. |
| 14 | CAN: GRCANFD map with circular-buffer DMA channels | **Diverge** (documented) | docs/03 selected the SJA1000-style Mohor core (CAN 2.0B, no FD): its register interface is SJA1000-shaped, not GRCANFD-shaped, and wrapping it to GRCANFD semantics (DMA channels) would exceed the core's own cost. Record divergence in the register map; revisit only if a verified open CAN FD core lands. Effort saved: high. |
| 15 | QSPI: SPIMCTRL-style memory-mapped flash windows + boot capability | **Mirror** (in spirit) | Map QSPI flash as XIP AHB windows (3-byte and 4-byte regions like GR716B) plus a small control slot; this is what makes multi-pass weight streaming and ASW boot storage uniform memory reads. Effort: moderate. |
| 16 | Boot flow: on-chip boot ROM, bootstrap pins, standby/remote boot, checksummed ASW image, staged watchdog (GR716B ch. 51; GRBOOT) | **Simplify** | Implement: boot ROM at the reset vector, bootstrap-selected source (QSPI / UART loader), GR716B-style image header + checksum validation, boot report register, staged watchdog. Omit: CANopen/SpW/I2C remote boot, redundant-image voting, self-test beyond RAM ECC init (first silicon). Effort: moderate, mostly software-in-ROM. |
| 17 | Debug: RISC-V debug module at 0xFE000000 (NOELVSYS) | **Mirror** | GR765 explicitly endorses standard RISC-V debug in NOEL-V mode; a standard debug module (as used by Ibex/VexRiscv ecosystems) at the NOELVSYS address is both GR801-proximate and open-tooling-native. Do not implement the SPARC DSU or AHBUART. Effort: low-moderate (mostly integration). |
| 18 | Fault visibility: AHBSTAT-style error latch + separate scrubber registers + PnP-discoverable fault counters | **Mirror** (in spirit) | One AHBSTAT-like slot latching {address, master, correctable} per error plus per-memory ECC counters and a MEMSCRUB-like scrubber slot carries the project's entire hardening-observability story in the family's idiom. Effort: low-moderate. |
| 19 | Clock gating unit (GRCLKGATE slot) | **Simplify** | A single clock-gate enable/status register slot for NPU nodes and heavy peripherals; the event-driven power argument needs demonstrable gating. Effort: low. |
| 20 | Endianness and register width: little-endian, 32-bit registers, one 4 KB slot per peripheral | **Mirror** | Matches NOEL-V/RISC-V and every table in section 2.5. Effort: nil. |
| 21 | NPU register interface (Akida-equivalent) | **Diverge** (necessarily) | Akida's register interface is proprietary and unpublished; no public GR801 document describes it. Design the SNN fabric's config/DMA interface natively, but in the family idiom: APB config slot + AHB-master descriptor DMA like GRSPW2/GRCANFD, PnP-registered, ECC/fault counters per node. Effort: the project's core work (docs/02). |

### 3.1 Memory map skeleton [proposal]

Frame: NOELVSYS physical map (grip.pdf table 2293) with GR740 APB slot
numbering where slots exist, single APB bridge. All addresses are proposals
to be frozen in the register-map document.

| Range | Block | Convention source |
|---|---|---|
| 0x00000000 - 0x0000FFFF (grows) | System SRAM, ECC (32-64 KB) | RAM at 0x0 (NOELVSYS, GR740) |
| 0x10000000 - 0x1FFFFFFF | NPU fabric window: per-node SRAM apertures + descriptor rings | project-specific (row 21) |
| 0xC0000000 - 0xC0001FFF | On-chip boot ROM (reset vector) | ROM at 0xC0000000 (NOELVSYS, GR740) |
| 0xD0000000 - 0xD1FFFFFF | QSPI flash XIP window, 3-byte addressing | SPIMCTRL windows (GR716B) |
| 0xD8000000 - 0xDFFFFFFF | QSPI flash XIP window, 4-byte addressing | SPIMCTRL windows (GR716B) |
| 0xE0000000 - 0xE000FFFF | CLINT (msip, mtimecmp, mtime) | NOELVSYS |
| 0xF8000000 - 0xF83FFFFF | PLIC (minimal, 32 sources) | NOELVSYS |
| 0xFE000000 - 0xFEFFFFFF | RISC-V debug module | NOELVSYS |
| 0xFF900000 - 0xFF9FFFFF | APB bridge (single) | GR740 bridge 0 base |
| 0xFF900000 | APBUART0 (console) | GR740 / NOELVSYS |
| 0xFF901000 | APBUART1 | GR740 |
| 0xFF902000 | GRGPIO-style GPIO (16x) | GR740 |
| 0xFF908000 | GPTIMER0 (last timer = watchdog) | GR740 / NOELVSYS |
| 0xFF909000 | GPTIMER1 | GR740 |
| 0xFF90D000 | SpaceWire (GRSPW2-shaped) | GR740 SpW AMBA interface slot |
| 0xFF911000 | CAN (SJA1000-shaped; divergent, row 14) | slot only |
| 0xFF912000 | SPICTRL (SPI master) | map from GR740 bridge 1 |
| 0xFF913000 | I2CMST | family style |
| 0xFF914000 | QSPI control registers | family style |
| 0xFF915000 | AHBSTAT-style error latch + ECC counters | GR740/GR716B |
| 0xFF916000 | Scrubber control (MEMSCRUB-like) | GR740 |
| 0xFF917000 | Bootstrap/boot-report register (GRGPREG-like) | GR740/GR716B |
| 0xFF918000 | Clock-gate control (GRCLKGATE-like) | GR740/GR716B |
| 0xFF919000 | NPU global config/status (fabric-level) | project-specific |
| 0xFF9FF000 | APB PnP table | bridge base + 0xFF000 |
| 0xFFFFF000 - 0xFFFFFFFF | AHB PnP table (+ device ID / build ID / endianness words at 0xFFFFFFF0) | GRLIB |

CPI capture (if retained per docs/01) takes an AHB-master DMA slot in the
0xFF91x000 range plus a data path into the NPU window; decision deferred to
the NPU architecture work.

---

## 4. Items feeding the ROADMAP and the register-map design

1. **Freeze the memory map skeleton** (section 3.1) as the first section of
   the register-map document; every subsequent block design keys off it.
   Record NOELVSYS table 2293 as the normative reference.
2. **Write the PnP generator early**: a script that emits the AHB/APB PnP
   ROM contents (and a Markdown register-map index) from a single SoC
   configuration file. It doubles as the single source of truth for
   addresses, device IDs, and IRQ assignments. Small task, large
   consistency payoff.
3. **Adopt the GRLIB register maps verbatim for APBUART, GPTIMER, GRGPIO,
   SPICTRL, I2CMST** (rows 8-12); the register-map document should cite
   grip.pdf table numbers (126, 463, 923, 2377, 1869) per block and mark
   any omitted registers as reserved-read-zero.
4. **Specify the GRSPW2-subset SpaceWire register interface** (row 13)
   before RTL: which CTRL/STS bits are implemented, one DMA channel,
   descriptor format identical to GRSPW2 unless a concrete cost forces
   change. This is the highest-risk mirror row.
5. **Document the CAN divergence** (row 14) in the register map and add a
   ROADMAP checkpoint: re-evaluate CAN FD via CTU CAN FD or successors at
   the next phase gate; carry the Bosch licensing line item from docs/03.
6. **Boot ROM specification** (row 16): define the ASW image header
   (magic, entry, length, data checksum, header checksum), boot report
   register format, bootstrap pin table, and the staged watchdog timeouts,
   explicitly modeled on GR716B UM chapter 51. Schedule ROM software with
   the same weight as an RTL block.
7. **Interrupt map**: fix the 32 PLIC source assignments in the register
   map now (UARTs, timers, GPIO, SpW, CAN, SPI, I2C, QSPI, AHBSTAT,
   scrubber, NPU nodes) — GRLIB carries IRQ numbers in PnP records, so the
   generator from item 2 should own this table too.
8. **Watchdog policy**: adopt "watchdog armed at reset, staged through
   boot" (GR716B) as a project requirement, not an option; it interacts
   with the fault-injection observability flow and must be testable in
   simulation.
9. **NPU register interface design task** (row 21): define the per-node
   APB/AHB split, descriptor format (align with the GRSPW2/GRCANFD
   descriptor idiom), and per-node fault counters, as part of the docs/02
   follow-on architecture work.
10. **Monitor Gaisler's GR801 downloads page** (
    https://www.gaisler.com/products/gr801) at each phase gate: the first
    advance datasheet or user's manual will supersede every [inference] in
    this document, and its memory map should be diffed against section 3.1
    the day it appears.
