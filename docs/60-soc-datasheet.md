# 60 — Neuromorphic Space SoC: preliminary device datasheet

Device: `soc_top` — an RV32IMC management core, a system fabric, an
on-chip memory subsystem, a core-local interruptor, a general-purpose
timer with a three-stage watchdog, a bus-fault and upset-telemetry
block, a console UART, two plug-and-play device tables, and a
spiking-neural-network node built around the frozen TTIHP26b pilot die.

Technology: IHP SG13G2, 130 nm bulk CMOS, open PDK, open RTL-to-GDS
flow.

Revision 0.1, 3 September 2026. Status: **preliminary, pre-silicon,
pre-sign-off**.

---

## 0. Read this page before any number in this document

**This datasheet describes a part that does not exist.** There is no
silicon, no test chip, no engineering sample and no schedule for one.
Three further statements have to travel with every figure below, and
they belong on the first page rather than in an appendix, because each
one changes what the rest of the document is worth.

**1. Nothing here has been geometrically verified.** The one
place-and-route run this document reports has **no DRC result, no LVS
result and no XOR result**, and the reason is not schedule. The design
needs six `RM_IHPSG13` SRAM macros; running the three decks over one
such macro returns **1,106,478 Magic DRC error boxes, 2,316 KLayout
deep-mode DRC errors and 359 Netgen LVS errors**
**[fact, `docs/12-sg13g2-flow-bringup.md` sections 7.5 and 8]**, and
`docs/12` section 8 records that as a **NO-GO on RM_IHPSG13 for this
PDK version**. `docs/54-klayout-deck-and-the-macro.md` examined the
2,316 in detail and closed the second exit as well: the deck that
returns zero on the contested rule is the PDK's own *unverified*
residual set, so swapping to it trades a verified deck for an
untested one. **A layout that has not been DRC'd or LVS'd is not
evidence that it is manufacturable or that it implements its own
netlist.** It is evidence about timing and area, and that is all this
document offers it as (`docs/47-soc-place-and-route.md` section 9).

**2. It does not meet its own timing constraint, and it fails three
other sign-off criteria.** At the 20 ns SDC period the flow is
constrained at, on extracted parasitics with the 5 % derate applied,
the design misses setup at the slow corner by **−3.2029 ns on 2,003
endpoints**, misses hold at the fast corner by **−0.2015 ns on 3
endpoints**, and reports **max-capacitance violations at all three
corners and max-slew violations at two**
**[fact, `docs/47` section 8.2]**. Three of those five failing criteria
are visible only because four configuration keys were set before the
run rather than audited after it; in the shipped flow configuration
they would have been warnings and `design__violations` would have read
zero.

**3. This datasheet publishes no clock frequency, and that is
deliberate.** `docs/53-workload-and-the-clock.md` section 9.2 refused
to write down the frequency the layout reached, on three grounds, and
section 9.4 restated the binding rule:
`docs/05-market-positioning.md` section 4 rule 5 requires that any
externally published figure be *"traceable to measurement or clearly
labelled as a design target"*, and a derived Fmax from a run that fails
setup, max slew and max cap and has never seen a geometry deck is
neither. **The 20 ns period appears below only as the flow constraint
every slack in this document was measured against.** It is not
converted into a rating and no rating is implied.

`docs/53` also established what the mission requirement actually is,
and it is not throughput. Of the four mission profiles in
`docs/05` section 3.4, **exactly one states a number and it is stated
in milliwatts**. The transport is a **27x** architectural factor
against the clock's **1.16x**. A datasheet for this part that led with
a clock speed would be repeating the mistake `docs/53` was written to
correct, so this one leads with what the part is, what it does not do,
and what its fault tolerance has been measured to be.

### 0.1 How every quantity is tagged

Following `docs/21-pilot-datasheet.md` section 0, which this document
takes as its evidence standard:

- **[measured]** — obtained from a tool run or a file in this
  repository, and the artefact is named.
- **[target]** — a design goal, not demonstrated on the object it
  describes.
- **[TBD]** — not known, and not estimated here.
- **[in flux]** — measured, but against an artefact that is being
  regenerated or a source file that is being edited as this is
  written. Section 13 lists every one of them.

Where a figure is arithmetic on measured figures rather than a reading,
it is tagged **[estimate]** and the arithmetic is stated.

### 0.2 Single sources of truth

This datasheet takes:

- `regmap/memmap.yaml` as the single source for the memory map, the
  peripheral slot assignment and the interrupt namespaces. Its
  generated form is `docs/memmap-soc.md`, and `sw/tests/test_memmap.py`
  fails when that file is stale. **No address, slot, source number or
  interrupt line in this document is retyped into prose that could
  drift from it** — sections 7 and 8 cite it and reproduce only what a
  reader needs to orient.
- `regmap/regmap.yaml` as the single source for the NPU node register
  block, generated into `docs/regmap-npu.md` and into
  `hw/rtl/npu_regs.vh` and `hw/soc/rtl/soc_npu_regs.vh`.
- `hw/soc/rtl/` and `hw/rtl/` as the single source for behaviour.
- the run trees under `hw/soc/pnr/runs/` as the single source for what
  a layout of this design contains.

Where a prose document in this repository disagrees with one of those,
this datasheet follows the source and **section 14 records the
disagreement**.

### 0.3 What this document does not cover

- **Any silicon property whatever.** No die has been fabricated.
- **Package, pinout, pad ring, I/O levels, thermal or lifetime data.**
  None of these exist; `soc_top` has no pad ring and no package.
- **Radiation test data.** No total-dose, cross-section, LET-threshold
  or latch-up figure has been measured for this design or for anything
  built on this PDK by this project. Section 9's campaigns are
  *conditional* outcomes given that an upset lands somewhere, and say
  nothing about how often that happens.
- **Gate-level behaviour.** `soc_top` has never been simulated as a
  netlist (`docs/47` section 9). Every fault-injection result in
  section 9 is at RTL.
- **Equivalence between the RTL and the placed netlist.**
  `Yosys.EQY` is off and `hw/soc/formal/` has never been pointed at
  `soc_top`.
- **Software.** There is a bring-up program and a supervisor workload;
  there is no BSP, no driver library and no operating system port.

---

## 1. Features

### Processor

- **32-bit RISC-V management core**, lowRISC Ibex, `small-pmp`
  configuration: RV32IMC (`BaseIsa` RV32I, `RV32M` = RV32MFast,
  `RV32B` none, `RV32ZC` = Zca), two-stage pipeline, flip-flop
  register file, no instruction cache, no branch-target ALU, no
  writeback stage **[measured, `hw/soc/rtl/soc_top.v` parameter block]**
- **Physical memory protection**, 4 regions, granularity 0
  **[measured, same]**
- Vendored **pristine** from lowRISC at commit
  `34b0705760ef3dfa00e99637432473d2be8f22f3`, Apache-2.0, converted to
  Verilog-2005 by sv2v with **zero patches to Ibex**
  **[measured, `docs/38-ibex-bringup.md`]**
- **Register file protected by a (39,32) SECDED codec** with a
  background scrub walking `x1`–`x31`
  **[measured, `hw/soc/rtl/ibex_regfile_secded.v`, `docs/43-core-hardening.md`]**
- **`SecureIbex` is 0**: no lockstep, no shadow register file, no
  dummy instructions, no memory-interface ECC. This is a recorded
  decision, not an omission — section 5.1

### Memory and interconnect

- **64 KiB system SRAM** and **8 KiB boot ROM**, 72 KiB total
  **[measured, `regmap/memmap.yaml`]**
- **System fabric on Ibex's own request/grant/response protocol**, two
  masters (instruction and data ports), **six slave ports**, round-robin
  arbitration with a proved no-starvation property, two outstanding
  requests **[measured, `docs/39-soc-bus-and-memory-map.md`, `docs/51-npu-integration.md` section 10.2]**
- **Peripheral bus is real AMBA 3 APB**, 1 MiB window, sixteen 4 KiB
  slots, proved by k-induction **[measured, `docs/39`]**
- **An error slave**: every unmapped address raises a bus error that
  Ibex takes as an access fault. There is no silent read of zero
  anywhere in the map **[measured, `docs/39`]**
- **Two plug-and-play device tables** in GRLIB's record *layout* — one
  for the system bus at `0xFFFFF000`, one for the peripheral bus. The
  layout is mirrored; **AHB is not claimed and there is no AHB in this
  SoC** **[measured, `docs/memmap-soc.md` section 4]**

### Timing, interrupts and supervision

- **RISC-V CLINT**: 64-bit free-running `mtime`, `mtimecmp`, `msip`,
  on the system bus rather than behind the APB bridge so that an
  `mtime` read costs one cycle **[measured, `docs/40-interrupts-timers-watchdog.md`]**
- **GPTIMER**: GRLIB register map, a 16-bit prescaler and two 32-bit
  general-purpose timers, one shared maskable interrupt
  **[measured, `hw/soc/rtl/soc_gptimer.v`]**
- **Three-stage watchdog** in its own power-on reset domain: stage 1
  raises a **non-maskable** interrupt, stage 2 asserts system reset,
  stage 3 latches an external pin. **Armed at reset, not disableable by
  software, with a fixed time base no register reaches** and keyed
  register writes **[measured, `hw/soc/rtl/soc_wdog.v` W1–W5, `docs/40` section 5]**
- **The watchdog's own persistent state is triple-redundant in the
  netlist and continuously voted** (the replicas are **not**
  placement-separated — section 9.9), and it survives the reset it
  causes, so a
  watchdog reset is distinguishable from a power cycle
  **[measured, `docs/41-watchdog-hardening.md`]**
- **Thirteen interrupt sources on Ibex's fifteen fast local interrupt
  lines**, no platform interrupt controller, **two lines spare**
  **[measured, `regmap/memmap.yaml`]**

### Fault tolerance and observability

- **BUSSTAT**: four saturating counters and four sticky status bits for
  register-file single-bit corrections, corrected read cycles,
  uncorrectable syndromes and watchdog voter mismatches, with a
  maskable interrupt. **The record lives in the power-on domain and
  survives the system reset the watchdog causes**
  **[measured, `docs/44-margin-and-observability.md` section 6.2]**
- **Seven RTL fault-injection campaigns** covering the management core,
  the NPU connection, the event engine, the watchdog and the NPU node,
  with per-structure outcome distributions and stated Wilson bounds.
  Section 9

### Neuromorphic node

- **The frozen TTIHP26b pilot instantiated, not copied**, out of
  `hw/rtl/`, with a test that fails if `hw/rtl/` has been modified
  **[measured, `docs/51` and `sw/tests/test_soc_npu_guards.py`]**
- **8 neurons, 8 axons, 64 four-bit signed synapses**, event-driven
  leaky-integrate-and-fire, `(72,64)` Hsiao SECDED on the weight word,
  55 configuration bits triplicated in the netlist, four fault pins
  **[measured, `docs/21-pilot-datasheet.md`]**
- **A 256 MiB fabric window carrying sixteen 4 KiB per-node register
  windows**, of which **one node is instantiated** and the other
  fifteen decode and fault **[measured, `regmap/memmap.yaml`, `docs/51` section 6]**
- **A hardware serial master** driving the die exactly as external
  silicon would: one 40-bit mode-0 frame per register transaction,
  **176 clock cycles per register access** **[measured, `docs/51` section 8.1]**
- **An AER event engine** with two `aer_fifo` queues carrying the die's
  own pointer voting, entry parity and drop counting, and a 14-bit
  interrupt cause register **[measured, `hw/soc/rtl/soc_npu.v`, `hw/soc/tb/sw/soc_npucfg.h`]**

### What is deliberately absent

- **No spacecraft interfaces of any kind.** No SpaceWire, CAN, SPI,
  I2C, QSPI or GPIO. **Eleven of the sixteen peripheral slots are
  reserved addresses with nothing behind them.** Section 4
  *Corrected 2026-09-05:* a 16-pin GPIO port is built and verified in
  `docs/65-gpio-and-the-interface-ip-assessment.md`, so the count is
  **ten of sixteen**; SpaceWire, CAN, SPI, I2C and QSPI remain absent
  and that document prices each.
  *Corrected again 2026-09-05:* a register-mode QSPI flash controller
  with two chip selects is built and verified in
  `docs/66-qspi-flash-controller.md`, so the count is **nine of
  sixteen**; the two execute-in-place windows stay reserved
- **No DMA, no descriptor rings, no third bus master.** Section 4
- **No clock gating, no power domains, no retention, no sleep mode.**
  One clock, one mode. Section 4 and section 11.3

---

## 2. Introduction

This document is the SoC-level counterpart to
`docs/21-pilot-datasheet.md`. That one describes a single frozen
neuromorphic tile submitted to a shuttle. This one describes the part
that tile becomes a node of: a management processor, an interconnect, a
memory system, a supervision subsystem and the neuromorphic node
itself, brought together under one top level.

`docs/21` was written on 2026-08-26 and covers a design that has since
been frozen and pinned by blob hash
(`docs/34-pilot-freeze.md`, commit `b6738e5`, shuttle TTIHP26b closing
**2026-09-21**). Everything on the SoC side of the project — twenty
documents, `docs/38` through `docs/56` — has been written since, and
until now it existed only as scattered sections. This document collects
it.

**A preliminary datasheet for a design under development is a real
artefact and it is written for a specific reader**: somebody who has to
decide whether to spend the next block of effort on this design, and
who needs to know what is measured, what is estimated, what is
constrained, and what has never been looked at. It is not written for
somebody choosing a part to buy, because there is no part to buy.

Everything that would let a reader mistake it for the second kind of
document has been removed or, where removal would be dishonest, kept
and labelled. In particular there is no ordering information, no
package drawing, no absolute-maximum-ratings table, no recommended
operating conditions table and no frequency rating, because every one
of those would be fabricated.

---

## 3. Description

The SoC is organised as one processor, one system fabric with six slave
ports, and one peripheral bus behind a bridge.

```
                +-------------------------------------------+
                |            Ibex RV32IMC, PMP=4            |
                |   SECDED register file + scrub  (5.1)     |
                +------+------------------------+-----------+
                       | instr port             | data port
                       v                        v
   +-------------------+------------------------+-------------------+
   |        SYSTEM FABRIC, 2 masters, 6 slave ports, round-robin     |
   |        Ibex-native req/gnt/rvalid; unmapped -> error slave      |
   +--+--------+---------+-----------+---------------+--------+------+
      |        |         |           |               |        |
      v        v         v           v               v        v
   +--+--+  +--+--+  +---+---+  +----+-----+   +-----+---+ +--+---+
   | RAM |  | ROM |  | CLINT |  |   NPU    |   |   APB   | | PNP  |
   |64KiB|  |8KiB |  |mtime  |  | 256 MiB  |   | bridge  | |table |
   +-----+  +-----+  |mtimecmp| | window   |   +----+----+ +------+
                     |msip   |  +----+-----+        |
                     +-------+       |              |  16 x 4 KiB slots
                                     |              |  5 filled, 11 empty
                                     v              v
                    +----------------+---+   +------+-----------------+
                    |    soc_npu         |   | UART0 | TIMER0+WDOG    |
                    |  node window       |   | BUSSTAT | NPUCFG       |
                    |  serial master     |<--+ APBPNP                 |
                    |  AER event engine  |   +------------------------+
                    |  two aer_fifo qs   |
                    |  +--------------+  |
                    |  | pilot_top    |  |   the frozen TTIHP26b die,
                    |  | 8 x 8 SNN    |  |   instantiated from hw/rtl/
                    |  +--------------+  |
                    +--------------------+
```

The **management core** is a two-stage Ibex with physical memory
protection and a SECDED-protected architectural register file. It is
the least hardened block in the design by design intent: `SecureIbex`
is 0, so there is no lockstep and no shadow register file, and the
watchdog is the backstop.

The **fabric** is not AMBA. AHB-Lite has exactly one master by
definition and Ibex alone presents two, so the interconnect speaks
Ibex's own protocol and the peripheral bus behind the bridge speaks
real AMBA 3 APB. Every unmapped address in the 4 GiB space reaches an
error slave that returns a bus error, which the core takes as a load or
store access fault; there is no address in this design that returns a
plausible zero.

The **supervision subsystem** is the part of this design that behaves
least like a general-purpose SoC. The watchdog is armed out of
power-on reset, cannot be disabled by software, has a time base that no
register reaches, requires a key in the upper half-word of every
register write, escalates in three stages rather than resetting, and
keeps its own state in the power-on domain so that it survives the
reset it causes. Its persistent state is triplicated in the netlist and
the voter runs every cycle rather than on write, so a second
**independent** upset has a one-cycle window rather than an unbounded
one.

**Corrected 2026-09-09.** That sentence said *coincident* and bounded
the exposure at one cycle, which is a bound on **accumulation over
time** and on nothing else. `docs/79` measured this design's replicas
touching on the die, and two cells that touch can be reached by one
event in one cycle — a case the one-cycle window does not bound at all,
because there is no interval between the two upsets to bound.

The **NPU node** is the frozen pilot die, instantiated out of `hw/rtl/`
rather than copied, driven over a hardware serial master that shifts
40-bit mode-0 frames into it exactly as external silicon would. Its
event path uses the die's parallel AER pins inbound and its serial
`EVQ_OUT` register outbound, because the die's pin contract gives SYNC
no inbound pin and gives the outbound pins no TYPE field. The CPU-side
interface is shaped for a sixteen-node mesh, of which one node exists.

The **memory subsystem** is 72 KiB. In simulation it is behavioural
(`hw/soc/rtl/soc_mem.v`); in the place-and-route flow it is six
`RM_IHPSG13` SRAM macros (`hw/soc/rtl/soc_mem_sram.v`), which no
simulation ever reads. **The memory is 4.29 times the logic by area**
in that layout.

---

## 4. What this device does not do

This section is in the body rather than in a footnote because for this
part it is load-bearing. A reader who takes the block diagram above at
face value will over-estimate the design in four specific ways.

### 4.1 It has no spacecraft interfaces at all

There is **no SpaceWire, no CAN, no SPI, no I2C, no QSPI and no
GPIO**, in the sense that matters: there is no RTL for any of them.
*Corrected 2026-09-05:* there is RTL for GPIO — `hw/soc/rtl/soc_gpio.v`,
GRGPIO-shaped, 16 pins, in slot `0x002` on fast line 2, with sixteen
pins on `soc_top` and check 28 of the bring-up program driving them
(`docs/65-gpio-and-the-interface-ip-assessment.md`). The paragraphs
below describe the design at revision 0.1 and are left as written; the
slot table's GPIO row moves to the implemented line and the reserved
count becomes ten.
*Corrected again 2026-09-05:* there is RTL for QSPI --
`hw/soc/rtl/soc_qspi.v`, a register-mode controller with two chip
selects in slot `0x014` on fast line 9, five pins and four three-wire
lanes on `soc_top`, and a second bring-up image that feeds the NPU its
weights through it from a modelled flash
(`docs/66-qspi-flash-controller.md`). The QSPICTL row moves to the
implemented line and the reserved count becomes nine; the two QSPI
execute-in-place windows are still reserved.
`hw/soc/rtl/` contains twenty-two files and none of them is a link
layer, a serial controller or a pin multiplexer
**[measured, the directory listing]**.

What exists is the **address space they will occupy**. The memory map
freezes a slot, a plug-and-play device ID, an interrupt source number
and an Ibex fast-interrupt line for each of them, so that adding one
later cannot renumber anything. Today those addresses reach the error
slave.

| Peripheral slots | Count |
|---|---:|
| Total slots defined in `regmap/memmap.yaml` | **16** |
| Implemented — UART0, TIMER0 (with watchdog), BUSSTAT, NPUCFG, APBPNP | **5** |
| **Reserved, decoding to a bus error** — UART1, GPIO, TIMER1, SPW, CAN, SPI, I2C, QSPICTL, SCRUB, BOOTREG, CLKGATE | **11** |

**[measured, `regmap/memmap.yaml` `apb_slots`, cross-checked against
its generated form `docs/memmap-soc.md` section 3]**

The same holds one level up: of the ten system-bus regions, **four are
reserved** — both QSPI execute-in-place windows, the PLIC region and
the RISC-V debug module. There is no debug module. There is no JTAG.

The one console interface that does exist, UART0, is **transmit
only**.

At the top level this is visible in the port list. `soc_top`'s only
functional inputs are `clk_i`, `rst_ni` and the watchdog bootstrap pin
`wdog_dis_i`; its only functional output is `uart_tx_o`. Everything
else on the port list is an observation output for a testbench or a
scope **[measured, `hw/soc/rtl/soc_top.v` lines 96–131]**.

### 4.2 The NPU is one node of sixteen, and it is the pilot

The NPU window is 256 MiB. Its low 64 KiB is sixteen 4 KiB per-node
register windows at `NODE_ID * 0x1000`. **One node is instantiated.**
The other fifteen decode and raise a bus error, as does everything
above `0x1000FFFF` including the whole area a descriptor ring would
live in.

The node itself is the pilot geometry: **8 neurons, 8 axons, 64
synapses of 4 signed bits**. The architecture it is a slice of is
specified at 512 x 512 (`docs/10-npu-mvp-spec.md` section 2). There is
no on-chip learning, no convolution, and no weight width other than 4
bits.

**Descriptor rings are not built**, and `docs/51` section 12 prices
rather than defers them: a ring is a bus master, `soc_bus.v` has two
hardcoded master ports and a fairness property written for two, so a
third master is a fabric change plus a re-proof. At this scale it would
also save nothing, because the CPU is not the bottleneck — the
transport is.

### 4.3 It has one clock and one mode

There is **no clock gating, no clock-domain crossing, no retention, no
sleep state and no wake-on-event path that does not run the whole
SoC**. The CLKGATE peripheral slot is a reserved address.

This is the design's one measured requirement gap and it is four orders
of magnitude wide. `docs/05` section 3.4 profile 4 is long-idle mission
phases and the differentiation argument is *"the chip must idle at
microwatts and wake on activity"*. On the telemetry profile's own duty
cycle this design is **0.0044 % busy and 100 % powered**
**[estimate, `docs/53` sections 6.2 and 7.3]**. Section 11.3 gives the
power figures that statement rests on and what they are worth.

### 4.4 It is not a flight part, and it is not radiation-hardened

Binding on every public description of this design
(`docs/05-market-positioning.md` section 4):

- **It is fault-tolerant by architecture, not radiation-hardened by
  process.** IHP SG13G2 is a commercial bulk 130 nm technology with no
  intrinsic single-event-latch-up immunity. Every tolerance property in
  section 9 comes from ECC, TMR, bounded waits, parity, dual rails and
  monitors.
- **The design target is LEO-class total dose, 10–30 krad(Si)**
  **[target]**, pending test data. No total-dose, upset-rate,
  cross-section or latch-up figure has been measured and none is
  claimed.
- **There is no screening, no qualification, no lot traceability and
  no reliability programme**, because there is no lot.

---

## 5. Functional overview

Area figures in this section are all from one recipe, so they can be
compared with each other: Yosys `stat -liberty` on `ihp-sg13g2` at the
typical corner, `abc` at a 20 ns delay target, `sg13g2_buf_4` driving,
5 fF load. One gate equivalent is `sg13g2_nand2_1` = **7.2576 um2**.
They are **synthesis** areas and not layout areas; section 11 gives the
layout.

### 5.1 Management core (`hw/soc/ext/ibex`, `hw/soc/gen/`)

lowRISC Ibex at commit
`34b0705760ef3dfa00e99637432473d2be8f22f3`, Apache-2.0, checked out
pristine and converted to Verilog-2005 by sv2v v0.0.13 into
`hw/soc/gen/` — **34 files, 15,873 lines, 30 of 30 RTL modules and 8 of
8 vendored primitives converted, zero errors and zero patches to Ibex**
**[measured, `docs/38-ibex-bringup.md`]**.

Configuration, read from the instantiation in `hw/soc/rtl/soc_top.v`:

| Parameter | Value |
|---|---|
| ISA | RV32IMC — `BaseIsa` RV32I, `RV32M` RV32MFast, `RV32B` none, `RV32ZC` Zca |
| `RegFile` | 0, flip-flop register file |
| `PMPEnable` / `PMPNumRegions` / `PMPGranularity` | 1 / 4 / 0 |
| `WritebackStage`, `BranchTargetALU`, `ICache`, `BranchPredictor` | all 0 |
| `MHPMCounterNum` | 0 |
| `SecureIbex`, `ICacheScramble` | 0 |

**[measured, `hw/soc/rtl/soc_top.v`]**

| Configuration | Cells | Flip-flops | Area, um2 | kGE |
|---|---:|---:|---:|---:|
| `small`, no PMP | 15,736 | 1,950 | 232,049 | 31.97 |
| **`small-pmp`, the baseline** | 18,921 | 2,106 | **275,682.6198** | 37.99 |
| `small-pmp-sec`, `SecureIbex` = 1 | 40,236 | 4,975 | 585,233 | 80.64 |
| **as shipped: SECDED register file + telemetry port** | 22,338 | 2,328 | **316,051.6590** | 43.55 |

**[measured, `docs/38` section 8.4 for the first three rows,
`docs/45-soc-top-synthesis.md` section 6.2 for the fourth]**

**`SecureIbex` is 0 and that is a decision with a recorded date.** It
is one switch that turns on lockstep, reset-all, dummy instructions,
register-file lockstep ECC and memory-interface ECC together; they are
localparams and are not separable. Enabling it would have cost
**+309,550 um2, more than doubling the core**, and would additionally
have required a memory subsystem carrying 39-bit words, which
`soc_mem.v` does not. The consequence, stated in `docs/38` section 10
item 4 in its own words, is that *"the management processor is
therefore the least hardened block in the design"* — and the watchdog
of section 5.6 is the backstop that decision creates.

**The register file is protected and the scrub is what makes it
observable.** `hw/soc/rtl/ibex_regfile_secded.v` wraps `x1`–`x31` in a
(39,32) SECDED codec with a background scrub pointer that walks the
file and re-encodes what it finds. The cost is **+38,050.5762 um2
(+13.80 %) and +222 flip-flops** on the core
**[measured, `docs/43-core-hardening.md`]**, and the effect is section
9.2's.

Five defects were found during bring-up and **all five were in this
project's testbench or build code, none in Ibex**
(`docs/38` section 7.5). Two of them constrain the memory map and are
enforced by the generator rather than by convention:

- **Ibex resets to `{boot_addr_i[31:8], 8'h80}`.** The reset vector is
  not free. `regmap/memmap.yaml` names the boot region and derives
  `RESET_VECTOR` rather than letting it be written down twice.
- **Ibex's `mtvec` is 256-byte aligned and vectored-only**, stricter
  than the RISC-V specification: `mtvec[7:2]` reads as zero regardless
  of what is written and MODE is hardwired. Every region base in the
  map is therefore required to be 256-byte aligned, so that a trap
  vector can be placed at the base of any region without the map being
  the thing that breaks it.

### 5.2 System fabric (`hw/soc/rtl/soc_bus.v`)

**Not AMBA, and the reason is a category argument rather than an area
one.** AHB-Lite has exactly one master by definition; Ibex alone
presents two, an instruction port and a data port. The fabric therefore
speaks Ibex's own request/grant/response protocol, quoted rule by rule
from `ext/ibex/doc/03_reference/load_store_unit.rst`, and the
peripheral bus behind the bridge speaks real AMBA 3 APB. An AHB-Lite
cost probe was built and measured anyway: **+15.9 % on the fabric,
+0.85 % of the CPU** — so **area was not the reason**
**[measured, `docs/39-soc-bus-and-memory-map.md`]**.

| Property | Value |
|---|---|
| Masters | 2 — Ibex instruction port, Ibex data port |
| Slave ports | **6** — `ram`, `rom`, `clint`, `npu`, `apb`, `pnp`, plus an internal error slave |
| Arbitration | round-robin; no-starvation is a proved property, and the measured worst gap between grants over a 300-cycle contention window is **2 cycles** against an asserted bound of 8 |
| Outstanding | `MAX_OUT` = 2, matching Ibex's `NUM_REQS` = 2 |
| Master restriction | all of one master's outstanding requests must go to one slave; there is no reorder buffer |
| Unmapped access | bus error, taken by Ibex as a load or store access fault |
| Latency | RAM 1 cycle; APB peripherals 3 cycles minimum |

**[measured, `docs/39`; six-port extension and its proof
`docs/51` section 10.2]**

| Block | Cells | Flops | Area, um2 | % of `small-pmp` Ibex |
|---|---:|---:|---:|---:|
| `soc_bus`, six ports | 868 | 55 | 10,928.8872 | 3.96 % |
| `soc_bus`, five ports, re-measured as a control | 812 | 49 | 9,917.3592 | 3.60 % |
| `soc_apb_bridge` | 201 | 94 | 6,437.4912 | 2.34 % |

**[measured, `docs/51` section 11 for the first two rows,
`docs/45` section 6.2 for the third]**

**A slave port costs +56 cells, +6 flip-flops and 1,011.53 um2**, and
the six flip-flops are checkable arithmetic rather than a figure to be
believed: the fabric keeps one response-ownership queue per slave, four
entries of one bit plus a two-bit write index **[estimate, the
difference of two measurements, `docs/51` section 11]**.

One RTL change was made to this block for physical reasons and it is
priced. `docs/45` found `rst_sys_n` driving 2,766 flip-flop reset pins
**and two data pins** — the request gates — which made the worst
synchronous setup path worse than the worst asynchronous recovery path.
Replacing that gate with a locally registered `issue_en` costs **one
flip-flop and one cycle of latency at boot**, is strictly more
conservative than what it replaced, and moved the synchronous path
group from **−60.6191 ns to +4.3006 ns** on an identical memory model
**[measured, `docs/47` sections 5.2 and 5.3]**.

### 5.3 Memory subsystem (`hw/soc/rtl/soc_mem.v`, `soc_mem_sram.v`)

| Region | Size | Base | Attributes |
|---|---:|---|---|
| RAM | 64 KiB | `0x00000000` | read, write, execute |
| ROM | 8 KiB | `0xC0000000` | read, execute; holds the reset vector at `0xC0000080` |

*Corrected 2026-09-05:* the RAM is **32 KiB** since
`docs/67-memory-protection.md`: the same four macros hold one
SECDED-protected word per 64-bit row instead of two unprotected ones,
and both memories are corrected on read and scrubbed. The map is
`regmap/memmap.yaml` as generated.

**[measured, `regmap/memmap.yaml`]**

There are **two implementations of the same module name**, and which
one a reader is looking at decides what the numbers mean.
`soc_mem.v` is behavioural and is what every simulation, cocotb suite
and formal job reads. `soc_mem_sram.v` is a drop-in with the same
module name and port list built on six `RM_IHPSG13` macros, and **no
simulation ever reads it** — it exists for the place-and-route flow.
Section 11.1 carries its physical consequences.

`MEM_RDREG` is a parameter that inserts one pipeline register on the
memory read-return path. **It defaults to 0 and the measurement is why**
(`docs/50-memory-read-register.md`): it does exactly what it was built
to do — of the layout's 2,003 violating setup endpoints, the 444
launched by an SRAM macro's `A_DOUT` pin become zero, and worst setup
slack improves by **+0.7772 ns**, the first setup improvement in four
documents that exceeds the flow's measured ~0.4 ns noise floor — **and
the part gets 25.23 % slower in wall-clock cycles**, because Ibex is a
two-stage core with no cache and a load stalls the pipeline outright.
The break-even would need a clock the design does not reach. The
register is built, measured, kept in the tree behind a default-off
parameter, and not used.

### 5.4 Core-local interruptor (`hw/soc/rtl/soc_clint.v`)

Standard RISC-V CLINT layout in a 64 KiB system-bus region at
`0xE0000000`.

| Offset | Register | Width | Notes |
|---|---|---|---|
| `0x0000` | `msip` | 1 bit | drives machine software interrupt, ID 3 |
| `0x4000` | `mtimecmp` | 64 | drives machine timer interrupt, ID 7 |
| `0xBFF8` | `mtime` | 64 | free-running, never reloaded or restarted |

Every other offset in the window is a bus error; there is one hart and
no hart-1 aliasing. `TICK_DIV` is 1, so one `mtime` tick is one CPU
clock, and `mtime` stops if the system clock stops — there is no
independent oscillator. **[measured, `docs/40-interrupts-timers-watchdog.md`]**

The block sits on the **system bus rather than behind the APB bridge**,
which costs **+1,421.92 um2, +0.52 % of the core**, and buys a
one-cycle `mtime` read instead of the bridge's three-cycle minimum
**[measured, `docs/40`]**.

Two behaviours a driver author must plan for. `mtip` is **high out of
reset**, because `mtimecmp` resets to zero and `mtime` is therefore at
or above it from cycle zero; this is harmless only because `mie.MTIE`
resets clear. And the naive two-store 64-bit `mtimecmp` update
**glitches**, demonstrably — software must use the architectural
three-store sequence, and there is a cocotb test that fails if it does
not.

| Block | Cells | Flops | Area, um2 |
|---|---:|---:|---:|
| `soc_clint` | 1,043 | 163 | 16,712.8164 |

**[measured, `docs/45` section 6.2] [in flux]** — `hw/soc/rtl/soc_clint.v`
is being edited in the working tree as this is written; see section 13.
`docs/40` section 9 reports 1,038 cells and 16,683.48 um2 for the same
block from an earlier session; section 14 records the difference.

**`mtime` and `mtimecmp` are unprotected**, 128 flip-flops of them, and
have been the top-ranked item for the next hardening wave since
`docs/44`. Tripling them the way the watchdog's state is tripled is
estimated at roughly **+27,000 um2, about +10 % of the core**
**[estimate, `docs/41` section 10]**.

### 5.5 General-purpose timer (`hw/soc/rtl/soc_gptimer.v`)

GRLIB GPTIMER register map on the APB, at slot `0x008`
(`0xFF908000`).

| Offset | Register |
|---|---|
| `0x000` | `SCALER` — prescaler value, 16 bits |
| `0x004` | `SCRELOAD` — prescaler reload |
| `0x008` | `CONFIG` — `TIMERS[2:0]`, `IRQ[7:3]`, `SI[8]`, `DF[9]` |
| `0x00C` | `LATCHCFG` |
| `0x010` + `0x010`*n | timer *n* counter, reload and control, n = 1..3 |
| `0x040` | `WDOGSTAT` — the watchdog's own status |

**[measured, `hw/soc/rtl/soc_gptimer.v` localparam block]**

Two general-purpose 32-bit timers (`NGEN` = 2) plus **the watchdog as
the third**, which is GRLIB's convention. One shared maskable interrupt
for the whole block, and `SI` reads **0** — reported honestly, because
the frozen map allocates this slot exactly one source number. The
`DH`/`DF` latch registers are not implemented and read zero.

| Block | Cells | Flops | Area, um2 |
|---|---:|---:|---:|
| `soc_gptimer`, watchdog included | 2,205 | 300 | 33,528.0708 |

**[measured, `docs/45` section 6.2]**

### 5.6 Watchdog (`hw/soc/rtl/soc_wdog.v`)

This is not a timer with a reset on the end, and the difference is the
point of the block. Its specification is eight numbered properties in
its own file header, and the formal properties in
`hw/soc/formal/soc_wdog_props.v` and the cocotb suite are written
against them.

| Id | Property |
|---|---|
| **W1** | **Armed at reset and not disableable by software.** `EN` reads 1 out of power-on reset; a write of 0 is accepted by the bus and ignored. The only thing that can stop it is `wdog_dis_i`, a bootstrap pin sampled once when power-on reset releases and never again. It is tied low in this SoC, and `WDOGSTAT.DISABLED` reports what it sampled |
| **W2** | **Its time base is not software-programmable.** Its own fixed divider, reached by no register. The longest timeout it can be talked into is a constant of the netlist, `2^WIDTH * PRESCALE` = **2^16 x 16 = 1,048,576 clocks**. There is deliberately no clamp register: a bound enforced by the width of a counter cannot be misconfigured and one enforced by a comparator can |
| **W3** | **Three-stage escalation.** Stage 1, counter reaches zero: raise `nmi_o` into Ibex's `irq_nm_i` and reload — non-maskable on purpose, because the state this fires in is one where `mstatus.MIE` is quite likely already zero. Stage 2, counter reaches zero again with stage 1 unacknowledged: assert system reset for `RST_CYCLES`; the core is not involved and cannot prevent it. Stage 3, after `ESCALATE` = 2 watchdog resets since power-on: assert `wdog_no`, the external pin, latched until power-on reset |
| **W4** | **Its state survives the reset it causes.** Everything in the file is in the power-on reset domain. After a watchdog reset the boot code reads `WDOGSTAT` and finds `WDOGRST` set and `RSTCNT` non-zero, so a watchdog reset is distinguishable from a power cycle. Demonstrated across three boots in one simulation |
| **W5** | **Keyed writes.** `wdata[31:16]` must equal `KEY` = `0xA51F` for *any* register write, not just the kick, so a runaway cannot hold off stage 2 by clearing the acknowledge |
| **W6** | **The persistent, silent state is triple-redundant in the netlist and continuously voted.** The replicas are not placement-separated; sections 9.5 and 9.9 |
| **W7** | **A windowed kick mode.** Built, measured, and **recommended for removal** — section 9.6 |
| **W8** | **A kick-budget mode.** Built, measured, kept |

**[measured, `hw/soc/rtl/soc_wdog.v` header, `docs/40` section 5,
`docs/41-watchdog-hardening.md`, `docs/46-watchdog-window-decision.md`]**

**What is protected and what is not was ranked rather than assumed.**
The criterion is state that is *persistent and silent* on corruption.
Protected: `dis_q`, `dis_seen`, `nmi_pend`, `rst_seen`, `rst_count`,
`rst_hold`, `tmr_err`, `tmr_count` — **22 bits**, bundled into one word
and tripled through `soc_tmr_bank.v`, which derives from the pilot's
own `pilot_cfg_bank` and carries the same polarity-and-mix storage
transform. Deliberately unprotected: `counter` (16), `reload` (16),
`pre` (4) — 36 flip-flops the block rewrites itself every tick or kick,
which bounds what an upset in them can do.

**The voter runs every cycle rather than on write.** That makes it a
continuous scrubber and bounds a second **independent** upset's exposure
to one clock cycle. *Corrected 2026-09-09: it does not bound a
common-mode upset. `docs/79` measured the replica cells abutting, and
cells that touch are reached in the same cycle by the same event.*

**Survival through synthesis was measured, not assumed**: **102 mapped
flip-flops** — 36 unprotected plus 3 x 22 protected — counted after
stripping every `keep` and `keep_hierarchy` attribute from the source
text, and mutation testing shows that removing the mix transform from
one or both replicas costs 11 or 22 flip-flops to structural merging
**[measured, `docs/41`]**. `hw/rtl/tmr_voter.v` is **instantiated in
place, not copied**, and is pinned to the pilot's blob hash.

Cost: **+5,091.06 um2, +88.9 % on the watchdog module, +1.85 % of the
core** — 1.6 % of what `SecureIbex` lockstep would have cost
**[measured, `docs/41`]**.

### 5.7 Bus and upset telemetry (`hw/soc/rtl/soc_busstat.v`)

The block exists because of a sentence in `docs/43` section 6.5: a
SECDED register file corrects silently, and *"in silicon, a corrected
upset is indistinguishable from no upset at all"*. A part whose stated
purpose is to survive an upset environment and which cannot say how
often it is being hit has no way to tell a healthy part from one about
to fail.

APB slot `0x015` (`0xFF915000`), source number 22, fast line 10 —
addresses the frozen map has carried since `docs/39`, so nothing about
the slot or the interrupt is new here; what is new is that something
decodes it. The name avoids "AHBSTAT" because there is no AHB.

| Offset | Register | Function |
|---|---|---|
| `0x00` | `STATUS` | four sticky bits, plus bit 8 = the interrupt line |
| `0x04` | `IRQEN` | one enable per source; **resets to 0**, in the system domain |
| `0x08` | `CNT_RFSEC` | register-file single-bit upsets the scrub repaired. **This is the upset-rate counter** — the scrub walks `x1`–`x31` and re-encodes, so an upset the program does not overwrite first is counted exactly once |
| `0x0C` | `CNT_RFRD` | cycles a read port returned a corrected word — an upper bound, not a count |
| `0x10` | `CNT_RFDED` | uncorrectable syndromes |
| `0x14` | `CNT_TMRERR` | watchdog voter mismatches |
| `0x18` | `CLR` | write-1-to-clear per source, write-only |

**[measured, `docs/44-margin-and-observability.md` section 6.2]**

All four counters saturate. **The record — counters and stickies — is
in the power-on domain and survives the system reset the watchdog
causes**, which is W4's argument applied to telemetry. `IRQEN` is
deliberately in the *system* domain and clears on every system reset,
so that an armed interrupt cannot fire on a fresh boot before software
has configured it.

| Block | Cells | Flops | Area, um2 | % of `small-pmp` Ibex |
|---|---:|---:|---:|---:|
| `soc_busstat`, at `docs/44` | 442 | 72 | 7,060.5486 | 2.56 % |

**[measured, `docs/45` section 6.2]**. `docs/55-npu-connection-hardening.md`
added the NPU fault lines to this block at a further **+4,796.1396 um2**
**[measured, `docs/55`]**; that increment is not folded into the row
above, because the row is a measurement of a file that has since
changed and folding it would produce a number no run has ever reported.

Its operator visibility was demonstrated rather than asserted: software
`lw` reads of `CNT_RFSEC` reproduced four of `docs/42`'s
fault-injection records correctly.

### 5.8 Console UART (`hw/soc/rtl/soc_uart.v`)

GRLIB APBUART register map at slot `0x000` (`0xFF900000`), source
number 2, fast line 0. **Transmit only.** 241 cells, 52 flip-flops,
4,359.7764 um2 **[measured, `docs/45` section 6.2]**.

### 5.9 Device tables (`hw/soc/rtl/soc_pnp.v`, `soc_apb_pnp.v`)

Two read-only tables in GRLIB's plug-and-play record *layout*: one for
the system bus at `0xFFFFF000`, eight words per slave record; one for
the peripheral bus at the bridge base + `0xFF000`, two words per slot.

**The layout is mirrored and AHB is not claimed.** A well-known layout
is what makes a device table readable; the bus underneath it is this
project's own. Vendor code is **`0x09`**, GRLIB's "various
contributions" bucket, and the device IDs under it are assigned by this
project and are **not registered with Frontgrade Gaisler** — so a
GRLIB-aware tool will show a known vendor and an unrecognised device,
which is the truthful outcome.

One field cannot express this map exactly: an AHB-style bank address
register compares `addr[31:20]`, so its granularity is 1 MiB, and four
regions are smaller than that. The exact byte size of every region is
therefore carried in user-defined word 1 and its implemented/reserved
status in word 2. **A reader that trusts only the bank address register
will over-state three region sizes**
**[measured, `docs/memmap-soc.md` section 4]**.

152 + 100 cells, 28 + 0 flip-flops, 2,585.3310 + 905.2722 um2
**[measured, `docs/45` section 6.2]**.

### 5.10 Neuromorphic node (`hw/soc/rtl/soc_npu.v` and the frozen die)

The subsystem has two bus faces, a transport, an event engine, two
queues and the die.

**The die is instantiated, not copied.** `pilot_top` is elaborated out
of `hw/rtl/`; there is no copy anywhere under `hw/soc/`, a Python guard
asserts it, and `hw/soc/flow/fi_npu.sh` refuses to elaborate if
`git diff` over `hw/rtl/` is non-empty.

**The connection is a serial master and the argument is not purity.**
`hw/soc/rtl/soc_npu_ser.v` shifts one 40-bit mode-0 frame per register
transaction into the die exactly as external silicon would, honouring
the die's three host obligations by construction. One register access
costs **176 clock cycles, of which 171 is the frame**
**[measured, `docs/51` section 8.1]**.

**The die's two ports are not symmetric, and the pin contract is why.**
Inbound, the event word the die builds from its pins has a TYPE field
of `00` or `01` and never `10`, so **SYNC — the frame barrier that
makes the stream self-delimiting — cannot be injected over the pins at
all** and goes over the serial `EVQ_IN` register instead. Outbound,
`AER_OUT_ID` is four bits and carries no TYPE, so **a SYNC echo and a
spike from neuron 0 are the same four bits**; the pin is used as a
notification and the word is read from the die's `EVQ_OUT` register.
`aer_out_ack` is tied low and never used, because the serial read is
itself the pop and two pop paths into a one-entry show-ahead register
would be two ways to lose the same event.

> **The consequence is an asymmetry of about 44x, and it is the tile's
> pin budget showing through rather than a design choice.** An inbound
> SPIKE or TICK costs **4 clock cycles** on the pins; an outbound event
> costs a **176-cycle frame** **[measured, `docs/51` section 4]**.

**The CPU-side interface is shaped for a mesh.** One 4 KiB register
window per node at `NODE_ID * 0x1000`, sixteen of them; a 16-bit event
stream in each direction with valid/ready; one interrupt with a cause
register, because a cause register scales to sixteen nodes on one wire
and a wire per node does not. **Five of the fourteen cause bits come
straight off the die's fault pins**, which is the pilot's
fault-visibility convention paying for itself somewhere it was not
designed for.

| Block | Cells | Flops | Area, um2 | % of `small-pmp` Ibex |
|---|---:|---:|---:|---:|
| `soc_npu_ser`, the transport | 581 | 134 | 10,773.5670 | 3.91 % |
| one `aer_fifo`, 16 x 8 | 671 | 186 | 15,465.3408 | 5.61 % |
| **`soc_npu`, connection only**, die black-boxed | 2,723 | 717 | **57,805.4988** | 20.97 % |
| `pilot_top` at 8 x 8, this recipe | 9,560 | 1,294 | 152,717.1786 | 55.40 % |
| **`soc_npu`, whole subsystem** | **12,421** | **2,008** | **209,739.0834** | **76.08 %** |

**[measured, `docs/51` section 11]**. Two hardening waves have since
added **+8,014.4694 um2** (`docs/55`) and **+1,471.3650 um2**
(`docs/56-npu-event-engine-hardening.md`) to the connection; those are
increments against re-measured baselines in their own documents and are
not folded into the table.

**More than half the connection is the two queues** — 30,930.68 um2,
53.5 % of it — and they are `hw/rtl/aer_fifo.v`, the proved queue the
die itself uses, with its entry parity, its pointer voting and its drop
counter. A cheaper queue was available and was not taken; the
alternative is a second set of pointer, parity and drop semantics in
this repository **[estimate, arithmetic on measured rows, `docs/51`
section 11]**.

**No frequency has been measured for any of this RTL.** `soc_npu` has
never been through STA at any corner and is **not in the
place-and-route run of section 11** — which matters, because at 76 % of
the core by cell area it would change the floorplan question rather
than fit inside its answer.

---

## 6. Signal description

**There is no pad ring and no package.** What follows is the port list
of the `soc_top` module, which is what a floorplan or a future pad ring
would have to serve. Nothing here has an electrical characteristic
attached to it; section 12 says so again.

### 6.1 Clock and reset

| Signal | Direction | Function |
|---|---|---|
| `clk_i` | in | System clock. One clock domain; there is no second clock and no crossing |
| `rst_ni` | in | **Power-on reset, active low, asynchronously asserted.** The only reset the watchdog obeys |

`rst_ni` reaches the watchdog. Everything else in the SoC runs on an
internal `rst_sys_n` that the watchdog can pull — that is its stage 2,
and it is the reason its own state must be outside that domain. The
internal reset is **asynchronously asserted and synchronously
deasserted** through a two-stage synchroniser, because `rst_req` is a
registered signal in this clock domain and would otherwise deassert on
a clock edge, which is a recovery violation at every flip-flop in the
design **[measured, `hw/soc/rtl/soc_top.v`]**.

### 6.2 Functional inputs and outputs

| Signal | Direction | Function |
|---|---|---|
| `wdog_dis_i` | in | **Watchdog bootstrap pin.** Sampled once when power-on reset releases and never again. Held low in this SoC; a board that ties it high has no watchdog, and `WDOGSTAT.DISABLED` reports it |
| `uart_tx_o` | out | Console UART transmit. **There is no receive pin** |
| `wdog_no` | out | Watchdog **stage 3**, active low, latched until power-on reset |

**Three functional pins, and one of them is a bootstrap input.** That
is the whole external functional interface of this design.

### 6.3 Observation outputs

These exist so a testbench or a scope sees what the design is doing
without a host reading registers. **Nothing in the SoC reads them
back**, and a floorplan is free to drop them.

| Signal | What it reports |
|---|---|
| `uart_irq_o` | UART interrupt |
| `wdog_rst_o` | watchdog stage 2 is asserting system reset |
| `nmi_o` | watchdog stage 1 is pending |
| `irq_timer_o`, `irq_soft_o` | CLINT `mtime` >= `mtimecmp`, CLINT `msip` |
| `gptimer_irq_o` | the GPTIMER's shared timer interrupt |
| `npu_irq_o` | NPUCFG cause AND mask |
| `npu_ser_sck_o`, `npu_ser_cs_n_o`, `npu_ser_mosi_o`, `npu_ser_miso_o` | **the die's own serial pins**, brought out so a bench sees exactly what external silicon would see |
| `npu_aer_in_stb_o`, `npu_aer_out_vld_o` | the die's event strobe and output-valid pins |
| `alert_minor_o`, `alert_major_internal_o`, `alert_major_bus_o`, `double_fault_seen_o`, `core_sleep_o` | Ibex's own alert and status outputs. `core_sleep_o` reports the core's `wfi` state and **is not a power-management output** — see section 4.3 |

**[measured, `hw/soc/rtl/soc_top.v` lines 96–131]**

---

## 7. Memory map and interrupts

**The normative source is `regmap/memmap.yaml`.** Its generated form is
`docs/memmap-soc.md`, `sw/tests/test_memmap.py` fails when that file is
stale, and every address, slot index, plug-and-play device ID,
interrupt source number and Ibex interrupt line in this SoC is derived
from it — including `hw/soc/rtl/soc_memmap.vh`,
`hw/soc/tb/sw/soc_memmap.h` and the linker script
`hw/soc/tb/sw/memmap.ld`. **This datasheet does not reproduce the map**;
it states its shape and its properties and points at the file.

### 7.1 Properties the map guarantees

- **Every region is a naturally aligned power of two**, so address
  decode is a prefix compare against a constant mask and never a
  magnitude comparison. Regions may not overlap. The generator exits
  non-zero rather than emit a map that cannot be decoded cheaply.
- **Every region base is 256-byte aligned**, because Ibex forces
  `mtvec[7:2]` to zero, so a trap vector can be placed at the base of
  any region without the map being what truncates it.
- **The reset vector is derived, not written down.** `boot_region` is
  ROM and `RESET_VECTOR` = base + `0x80`, and the generator refuses a
  map whose boot region does not contain, or cannot execute, its own
  reset vector.
- **Everything outside every region is a bus error.**

### 7.2 Shape of the map

Ten system-bus regions, **six implemented and four reserved**: RAM,
NPU, ROM, CLINT, APB and the system-bus device table are implemented;
the two QSPI execute-in-place windows, the PLIC region and the RISC-V
debug module are frozen addresses with nothing behind them.

Sixteen peripheral slots inside a 1 MiB APB window, **five implemented
and eleven reserved** — section 4.1 lists both sides.

The NPU window is 256 MiB of which the low 64 KiB is sixteen node
windows; **three decode rules fault rather than alias**, plus a fourth
that is easy to miss: a **sub-word write faults**, because the serial
frame is 32 bits and carries no byte enable, and a slave that accepted a
byte store would have to widen it and write three bytes of a register
the master never named.

### 7.3 Interrupts, and why there are two namespaces

The map keeps **two separate namespaces and they must not be
conflated**, because they are different sizes and a future controller
would key on one while today's wiring keys on the other.

| | |
|---|---|
| **`irq`** | a GRLIB plug-and-play **source number**, five bits wide because that is the width of the field in the identification word. The numbers in use run to **24** |
| **`line`** | the **wire index**: which of Ibex's fifteen fast local interrupt inputs the source is physically connected to. Indices in use run to **12** |

Ibex gives each fast line a dedicated vector at `mtvec + 4*(16+line)`
and a fixed hardware priority, so **no interrupt controller is needed**.
Thirteen sources are defined; **lines 13 and 14 are unassigned**, and
that headroom is the quantity the platform-interrupt-controller
decision is measured against. The generator refuses a line outside
0..14, so exhausting the budget is a build failure rather than a
discovery.

Four core inputs are architectural rather than per-peripheral:

| Input | ID | `mcause` | Driven by |
|---|---:|---|---|
| MSOFT | 3 | `0x80000003` | CLINT `msip` |
| MTIMER | 7 | `0x80000007` | CLINT `mtime` >= `mtimecmp` |
| MEXT | 11 | `0x8000000B` | **unconnected**, tied low, reserved for a PLIC |
| NMI | 31 | `0x8000001F` | **watchdog stage 1** |

The full source-to-vector table is `docs/memmap-soc.md` section 3a.

---

## 8. Register maps

### 8.1 The NPU node block

**Generated from `regmap/regmap.yaml`.** Its documentation form is
`docs/regmap-npu.md`; its C form for the SoC's own software is emitted
at build time; its Verilog forms are `hw/rtl/npu_regs.vh` and
`hw/soc/rtl/soc_npu_regs.vh`. `sw/tests/test_regmap.py` cross-checks
name, offset, access and literal reset value against the normative list
in `docs/10-npu-mvp-spec.md` section 10 and fails on divergence.

It is a 12-bit byte-address space — one 4 KiB window per node — of
32-bit word-aligned registers, with `ID` reading `0x4E505531`, the
ASCII string `NPU1` with vendor byte `0x4E` leading, and a `VERSION`
word beside it. Six blocks: `sys`, `cfg`, `pass`, `mem`, `fault`,
`aer`. **`docs/21-pilot-datasheet.md` section 5 is the programmer's
view of it as the die implements it, including five documented
deviations**, and is not restated here.

Reached from the SoC at `0x10000000 + node*0x1000 + offset`, over the
serial transport, at 176 cycles per access.

### 8.2 NPU fabric controller (NPUCFG)

Hand-written, as the GPTIMER's software header is, and its map lives in
`hw/soc/tb/sw/soc_npucfg.h`. APB slot `0x019` (`0xFF919000`), source
number 24, fast line 12, `mcause 0x8000001C`.

| Offset | Register |
|---|---|
| `0x000` | `ID` — reads `0x4E505543`, ASCII `NPUC` |
| `0x004` | `VERSION` |
| `0x008` | `CTRL` — `IN_EN`, `OUT_EN`, `FLUSH` (self-clearing), `SCRUB` (self-clearing, pulses the die's `SCRUB_STB`) |
| `0x00C` | `STATUS` — transport busy, both queues' empty/full, the die's `IN_RDY`/`OUT_VLD`, and the die's `BUSY`, `ERR`, `SEC`, `DED`, `TMR` pins |
| `0x010` | `IRQCAUSE` |
| `0x014` | `IRQMASK` |
| `0x018` / `0x01C` / `0x020` | `EVQ_IN` / `EVQ_OUT` / `EVQ_STAT` |
| `0x024` | `GEOM` — the elaborated node geometry |
| `0x028` / `0x02C` | `CNT` / `CNT_DROP` |

**[measured, `hw/soc/tb/sw/soc_npucfg.h`]**

`IRQCAUSE` is **fourteen bits and the mix of levels and stickies is a
decision**. A level has state behind it, so the way to clear it is to
fix the state; a refused write has no state behind it and must be
latched or nobody can observe it. Writing 1 to a level bit is accepted
and does nothing.

| Bit | Name | Kind | Meaning |
|---:|---|---|---|
| 0 | `EVT` | level | the capture queue is not empty |
| 1 | `ERR` | level | the die's ERR pin |
| 2 | `SEC` | level | the die's SEC pin |
| 3 | `DED` | level | the die's DED pin |
| 4 | `TMR` | level | the die's TMR pin |
| 5 | `INJ_OVF` | sticky, W1C | an `EVQ_IN` write was refused by a full queue |
| 6 | `FETCH_ER` | sticky, W1C | an injection-queue fetch expired |
| 7 | `SER_TO` | sticky, W1C | a serial frame did not complete within its bound |
| 8 | `WIN_TO` | sticky, W1C | a node-window response did not arrive within its bound |
| 9 | `Q_COR` | sticky, W1C | a queue mechanism corrected something |
| 10 | `Q_DET` | sticky, W1C | a queue mechanism detected something it could not correct |
| 11 | `CFG_TMR` | sticky, W1C | the connection's own configuration voter disagreed |
| 12 | `OH_TO` | sticky, W1C | the show-ahead adapter's bounded wait expired |
| 13 | `AER_MM` | sticky, W1C | the AER strobe and its qualifier disagreed |
| 14 | `EVT_TO` | sticky, W1C | the event engine's `E_DECIDE` wait expired and the event in flight was discarded |

Bits 7 through 13 were added by the hardening waves of `docs/55` and
`docs/56` and each is traceable to a measured failure in section 9.4
and 9.5. **Bit 14 was added 2026-09-11** and is a different kind of
thing from all of them: it does not report a fault the part detected,
it reports a DECISION the part made. `E_DECIDE` used to wait
indefinitely for a die that would not take an event when there was also
nothing to drain -- `CTRL.OUT_EN` off, a capture queue software had
stopped reading, or a die not taking events at all -- and because the
engine is one state machine, that stopped every LATER event too. It now
waits `DECIDE_MAX` cycles (4,095 by default, enforced at elaboration to
be at least eight times the block's longest legitimate transient) and
then discards the event and raises this bit.

**The event is lost, and that is the whole price.** It is the only loss
this engine is permitted, because it is the only one that reports
itself: a part that discarded reads `EVT_TO`, a part that is merely busy
reads nothing, and the two were previously indistinguishable from
outside because the second one never ended. The bit is sticky and
write-1-to-clear like every other fault bit, so a discard cannot happen
without a record. Cost, measured on `flow/syn_soc_top.sh` against the
same recipe with the change reverted: the protected word goes from 25 to
27 bits, so **+6 flip-flops in the three replica banks and +12 in the
unprotected guard counter, +18 in total** and +1,368.85 um2. **Every bit except `EVT` is a fault bit**, and the software
header defines that set once rather than letting a program spell it out
and then go on reporting a clean part after a bit is added.

### 8.3 BUSSTAT, GPTIMER and the watchdog

Sections 5.5, 5.6 and 5.7 carry these. They are hand-written maps, not
generated, and the files are their own normative statements:
`hw/soc/rtl/soc_busstat.v`, `hw/soc/rtl/soc_gptimer.v` and
`hw/soc/rtl/soc_wdog.v`.

### 8.4 CLINT

Section 5.4. Three registers at the standard RISC-V offsets; every
other offset in the window faults.

---

## 9. Fault tolerance

> **EVERY LAYOUT-DERIVED AND CAMPAIGN-DERIVED NUMBER IN THIS SECTION
> PREDATES THE 2026-09-11 RTL REPAIR. Added 2026-09-12, and the reason
> it is added late is itself the finding.**
>
> On 2026-09-11 five defects were repaired across three sources --
> `soc_npu.v`, `soc_wdog.v` and `soc_uart.v` -- and on 2026-09-12 the
> power-on reset was release-synchronised in `soc_top.v` and the event
> engine's `E_DECIDE` wait was bounded. Between them the design gains
> **25 flip-flops** at `soc_top`: five from the repair, two from the
> reset synchroniser, eighteen from the bound and its cause bit
> **[fact, `flow/syn_soc_top.sh` run against the same recipe with each
> change reverted]**.
>
> **No layout in this repository contains any of them.** `s71boot`,
> `s75w9`, `s77gate` and every other `soc_top` run this section rests on
> were hardened before, so section 9.10's 5,873 flip-flops, every
> per-block census, and every campaign figure below describes a netlist
> the tree no longer produces. *Those numbers remain true of the runs
> they name*, which is what `docs/80`'s digest manifest pins and what
> `docs/64`'s rule keeps. What is no longer true is the implicit reading
> that they describe the design as it now stands.
>
> **`paper/main.tex` section 2 carried this marker from 2026-09-11 and
> this document did not**, for a day, while publishing the same
> superseded netlist under the same numbers. The paper is read by
> strangers and the datasheet is read by whoever would build against
> this part, so if either had to have it first it was this one. It went
> to the paper because the paper was what someone was editing that day
> -- which is not a reason, it is an account of how the gap happened.


**This is the section of this datasheet with the most measurement
behind it, and it is the only section where this design has something
that a commercial datasheet for a comparable part usually does not: the
fault-tolerance claims are measured rather than asserted.** Seven RTL
fault-injection campaigns have been run against five different
populations, every one of them reports a per-structure distribution
rather than a single headline, and several of them explicitly refuse to
quote an improvement their own instrument says is not distinguishable
from noise.

### 9.1 What is protected, and by what

| Structure | Mechanism | Reported through |
|---|---|---|
| Ibex architectural register file `x1`–`x31` | (39,32) SECDED, single-bit corrected inline, plus a background scrub that walks the file and re-encodes | `BUSSTAT.CNT_RFSEC`, `CNT_RFRD`, `CNT_RFDED`, stickies, interrupt |
| Watchdog persistent state, 22 bits | Triplicated **in the netlist**, voted every cycle, with a per-replica storage transform; replicas not placement-separated (section 9.9) | `BUSSTAT.CNT_TMRERR`, `WDOGSTAT` |
| Watchdog software runaway | Three-stage escalation: NMI, then reset, then an external pin | `nmi_o`, `wdog_rst_o`, `wdog_no`, `WDOGSTAT.RSTCNT` |
| NPU serial transport | Bounded frame wait with timeout | `NPUCFG.IRQCAUSE.SER_TO` |
| NPU node window | Bounded response wait plus an orphan-response check | `IRQCAUSE.WIN_TO` |
| NPU connection configuration and cause bank | Triplicated in the netlist, 21 bits; replicas not placement-separated | `IRQCAUSE.CFG_TMR` |
| NPU event queues | `aer_fifo`'s pointer voting, entry parity, dual-rail valid flags and drop counting | `IRQCAUSE.Q_COR`, `Q_DET`, `INJ_OVF`, `CNT_DROP` |
| NPU show-ahead adapter | Bounded wait with timeout | `IRQCAUSE.OH_TO` |
| NPU AER input strobe | Strobe-versus-qualifier agreement check | `IRQCAUSE.AER_MM` |
| Die weight word | (72,64) Hsiao SECDED, corrected inline, double-bit detected with zero substitution | die `CNT_SEC`, `CNT_DED`, SEC and DED pins, into `IRQCAUSE` |
| Die configuration, 55 bits | Triplicated in the netlist, majority voted; measured **not** placement-separated on the frozen layout (`docs/79`) | die `CNT_TMR`, TMR pin, into `IRQCAUSE` |
| Die neuron-core FSM | Hamming-distance-2 parity state encoding, park in a safe state | die `ERR` pin, into `IRQCAUSE` |
| Die neuron state and synapse array | SECDED check fields | die counters |
| Unmapped address, sub-word write to the node window | Error slave; Ibex access fault | `mcause` |

**Every mechanism in that table has been fault-injected and the
outcomes are below. None of them has been exercised in a beam.**

### 9.2 How to read the numbers, and the rules the campaigns set

Five rules, taken from the campaigns' own documents, and every one of
them exists because breaking it produces a plausible number that is
wrong:

1. **Nothing here is a rate.** These are *conditional* outcomes given
   that an upset lands somewhere. Deriving an upset rate, a
   cross-section or a total-dose figure from them is not possible and
   is not attempted.
2. **A stratum reading 0 of 100 is not a rate of zero.** It is a rate
   **below about 3.7 %** at this sample size, and every campaign says so
   in its own words.
3. **Do not pair figures across campaigns whose populations differ.**
   The NPU connection was measured over **738**, then **809**, then
   **824** injectable bits as guard and redundancy flip-flops were
   added; the management core over **2,198** and then **2,451**. Each
   document labels its own design-weighted figure "the number not to
   quote" against its predecessor.
4. **Do not compare a hardened block's cost against another document's
   published baseline.** Costs below are measured against a
   `HARDEN=0` build of the *same file* in the *same session*, because
   `docs/43` section 7.3 measured that quoting across documents
   understates a cost.
5. **Every DETECTED outcome assumes somebody is looking.** A detected
   fault that no software polls and no scope watches is indistinguishable
   from a silent one.

Outcome classes, common to all campaigns: **MASKED** (no effect),
**CORRECTED** (a mechanism repaired it and counted it), **DETECTED**
(the design flagged it), **SDC** (silent data corruption: wrong output
or wrong retained state, nothing flagged), **HANG**.

### 9.3 The management core

**Population: the Ibex core as instantiated in `soc_top`, in the
`small-pmp` configuration — 2,198 injectable RTL flip-flop bits across
116 sites in 13 architectural strata, before hardening; 2,451 bits in
14 strata after.** The census is machine-generated and reports
**100 % of elaborated flip-flop bits covered by the campaign**. It is
RTL, single-bit, flip-flop-only. Nothing outside `u_ibex` — not the
fabric, the memories, the CLINT, the timers, the UART or the watchdog's
own state — is in this population. *Added 2026-09-10:* the CLINT and
the watchdog have populations of their own in `docs/58` and `docs/41`,
and **section 9.10 states what the whole design's denominator is** —
5,873 flip-flops, of which 1,003 to 1,051 are in a block no campaign in
this repository has injected into at all.

**Before hardening [measured, `docs/42-core-fault-injection.md`]:**
1,300 injections, 13 strata of 100, each run twice — 2,600 simulations,
**53 minutes** on 18 concurrent processes.
Artefact `hw/soc/out/fi-core/campaign.log`.

| | watchdog held off | watchdog armed |
|---|---:|---:|
| Design-weighted SDC | **2.8 % ± 1.6** | 2.7 % ± 1.6 |
| Design-weighted HANG | **2.1 % ± 1.8** | 1.4 % ± 1.5 |
| CORRECTED | **0 of 1,300** | 0 of 1,300 |

**CORRECTED reads zero because there was no correction mechanism in the
core at all**, which is the finding that motivated the register-file
codec. The three worst strata were `fetch_fifo` (9 SDC of 100),
`controller` and `id_ctrl` (8 each of 100, over 15 and 71 bits), and
`regfile` (3 SDC and 4 HANG of 100 over 992 bits — the largest
structure in the core).

**The watchdog was measured against this campaign and it works.** Of 36
records that left the machine genuinely dead, **33 escalated —
91.7 % [78.2–97.1]** — and 26 of those 33 then completed with the
golden answer. **Zero spurious escalations in 1,106 survivable
injections.** Twenty-seven injections flipped from a wrong answer with
the watchdog held off to the golden answer with it armed, and **none
went the other way**.

**After hardening [measured, `docs/43-core-hardening.md`]:** 1,400
injections, 14 strata of 100, each run twice, twice over — 5,600
simulations in **1 h 17 m**. Artefacts `hw/soc/out/fi-h1/` and
`fi-h2/`.

| Stratum | n | MASKED | CORRECTED | SDC | DETECTED | HANG |
|---|---:|---:|---:|---:|---:|---:|
| `regfile`, before | 100 | 78 | 0 | **3** | 15 | **4** |
| `regfile`, after | 100 | 6 | **94** | **0** | 0 | **0** |
| `regfile_ecc`, the new check bits and scrub pointer | 100 | 4 | **96** | **0** | 0 | **0** |

Design-weighted, held off: SDC **2.8 % ± 1.6 → 1.3 % ± 0.4**, HANG
**2.1 % ± 1.8 → 0.3 % ± 0.2**.

> **And part of that improvement is the denominator.** The campaign
> added a 253-bit `regfile_ecc` stratum, so the register file's share
> of the design fell from 45.1 % to 40.5 %. `docs/43` states this
> against its own headline. **The like-for-like comparison is the
> `regfile` row above**, which is 3 SDC and 4 HANG of 100 going to
> zero and zero on the identical stratum.

Cost: **+38,050.5762 um2 (+13.80 %) and +222 flip-flops** on the core,
and **−9.3 % on the pre-layout closing period**
**[measured, `docs/43`]**. `docs/44` subsequently corrected the
attribution of that timing loss: the worst path both before and after
was a **false path from a tied-off configuration input**, and the real
limiter was an unbuffered reset net, not the codec. On the paths that
actually exist, the codec costs **2.7928 ns** on the read path at the
slow corner.

### 9.4 The neuromorphic node

**Population: the frozen die's own architectural flip-flops at the
8 x 8 geometry — `pilot_top` and everything under it, oracled
bit-for-bit against `sw/golden/lif_core.py`.** This is the pilot's
campaign and it is owned by
`docs/16-fault-injection-campaign.md`. Nothing in the SoC around the
die is in this population.

**Read out of `hw/tb/fi_campaign_results.json` at commit `7721719`
[measured]:** seed `0x16f12026`, 8 x 8 geometry, `EVQ` depth 4,
**378 injections**, 445.7 s of wall time.

| Outcome | Count | Share |
|---|---:|---:|
| MASKED | 97 | 25.7 % |
| CORRECTED | 193 | 51.1 % |
| DETECTED | 82 | 21.7 % |
| **SDC** | **6** | **1.6 %** |
| HANG | 0 | 0 % |

**`docs/16`'s headline for the committed log is 366 injections with 18
SDC.** The two do not agree and section 14 records it; this datasheet
follows the file, as section 0.2 requires.

**Every hardened structure in the die held, with zero counterexamples
[measured, the `groups` object of the same file]:**

| Structure | Group | Result |
|---|---|---|
| AER queue pointer TMR | `evq_ptr` | **72 / 72 CORRECTED** |
| Membrane potentials | `lif_vmem` | 24 / 24 CORRECTED |
| Neuron-state check field | `lif_smem` | 18 / 18 CORRECTED |
| Refractory counters | `lif_rmem` | 12 / 12 CORRECTED |
| Synapse check field | `lif_wchk` | 12 / 12 CORRECTED |
| Synapse weights | `lif_wmem` | 13 CORRECTED + 3 MASKED of 16, 0 SDC |
| SECDED single-bit port | `ecc_port_single` | 12 / 12 CORRECTED |
| SECDED storage loop | `ecc_ff` | 7 / 7 CORRECTED |
| SECDED double-bit port | `ecc_port_double` | 4 / 4 DETECTED, never miscorrected |
| Configuration TMR | `cfg_tmr_a`/`b`/`c` | 15 / 15 CORRECTED |
| Neuron-core FSM | `lif_fsm` | 12 / 12 DETECTED |
| Dispatcher bounded wait | `wdog_fetch_dir` | 5 / 5 DETECTED |
| Show-ahead bounded wait | `wdog_oh_dir` | 5 / 5 DETECTED |

**All six remaining silent corruptions come from structures the die
does not claim to protect:** the neuron scan and emission state
(`lif_scan`, 3 of 24), the `EVQ_OUT` show-ahead adapter (`evq_hold`,
2 of 18), and the register-bank configuration (`regbank_cfg`, 1 of 16).
**Every other group returned zero SDC.**

**One correction in the die's history is worth carrying into an SoC
datasheet**, because it is the failure mode a redundant structure has
that no RTL campaign can see. Until 2026-08-26 the die's three
configuration replicas were three `reg` vectors written from the same
expression; synthesis proved them equivalent and **merged all three
into one**, so the voter read one physical bank three times while a
fault-injection campaign scored it 15/15 CORRECTED. The fix is a
per-replica module instance with a different polarity in each, and it
is the reason `soc_tmr_bank.v` in this SoC carries the same transform
and the reason `docs/41`'s watchdog TMR **counted mapped flip-flop
cells** rather than trusting the attribute
**[measured, `docs/21` section 6.3]**.

### 9.5 The NPU connection

**Population: the connection path only — the transport, the node
window, NPUCFG, the event engine and the two queues. The frozen die is
excluded and tracked separately as a control stratum.** The document is
emphatic about it: every design-weighted figure is computed over the
connection's bits with the die excluded.

| Campaign | Population | Injections |
|---|---:|---|
| `docs/52-npu-connection-fault-injection.md`, before hardening | **738 bits** | 700, 7 strata of 100, each run twice — 1,400 simulations, **31 m 34 s** |
| `docs/55-npu-connection-hardening.md`, after | **809 bits** | 700 the same way, plus a **616-record directed replay of `docs/52`'s exact draws** |
| `docs/56-npu-event-engine-hardening.md`, engine split and hardened | **824 bits** | 1,100, 11 strata of 100, each run twice — 2,200 simulations, **59 m 13 s** |

**`docs/52` refused its own best-looking number and the refusal is the
useful part.** The SDC column reads **0 of 700**, and the document's
own section heading says that number must not be quoted on its own:
every corrupted inference in that workload is DETECTED *by
construction*, because the program checks its answer, so SDC is
structurally unreachable for it. **Reporting "0 % SDC" would be
reporting that this program noticed.** The substitute figure it built
instead is a *silent wrong inference*: **41 of 700 inferences
corrupted, of which 38 were silent to every hardware channel** — no
pin, no counter, no cause bit.

**What the hardening changed, measured on the same 616 draws
[measured, `docs/55` section 8.3]:**

| | before | after |
|---|---:|---:|
| Dead machines | **7** | **0** |
| Queue mechanism firings that announce themselves | 2 of 80 | **75 of 81** |
| Silent wrong inference | 36 of 616 | 29 of 616 |

Each of the seven dead machines is named to the mechanism that now
catches it: four to the transport frame bound, two to the node-window
response bound, one to the window's orphan-response check.

> **And `docs/55` refuses the 19 %.** 36 to 29 of 616 looks like a
> 19 % improvement and that document declines to claim it, because it
> carries an instrument that says how much of it is real: the frozen
> die's own stratum, which **cannot have changed**, shows **15 verdict
> changes out of 100** from workload-cycle drift alone. The 7-record
> delta is not distinguishable from that. **What is claimed is the
> 7 dead machines going to 0 and the 2-of-80 going to 75-of-81**,
> both of which are far outside the drift.

The connection-weighted silent-wrong-inference figures are
**4.17 % ± 1.60** (`docs/52`), **2.56 % ± 1.25** (`docs/55`) and
**1.53 %** (`docs/56`). **They must not be paired**, for rule 3's
reason: 738, 809 and 824 bits.

Cost: **+8,014.4694 um2 on the connection and +4,796.1396 um2 in
BUSSTAT = 12,810.6090 um2, 4.65 % of the unprotected core**
**[measured, `docs/55`, baselines re-measured at commit `07f0dd6`
rather than quoted]**.

### 9.6 The event engine, and the strongest per-bit result in the design

`docs/55` named the event engine as the next block and attached a
condition: **split its 140-bit stratum first**, because hardening an
undifferentiated stratum protects the average rather than the failure.
`docs/56` did that, into `ev_seq` (19 bits), `ev_data` (64), `ev_cnt`
(32), `ev_pin` (6) and `ev_oh` (22), and the split found what the
average had hidden:

> **One flip-flop, `aer_in_stb`, produced a silent wrong inference in
> 18 of 18 draws — a phantom spike the die accepted as real. That is
> the highest per-bit rate measured anywhere in this block**
> **[measured, `docs/56` split baseline]**.

Two guards were added: a bounded wait on the show-ahead adapter and a
strobe-versus-qualifier agreement gate on the AER input. In the
campaign of record that site reads **0 of 100 silent** — 17 of the
original 18 failures now announce themselves on
`IRQCAUSE.AER_MM`, and **1 of 18 remains a genuinely lost real event,
named rather than netted off**, because the gate holds the strobe quiet
and cannot tell a corrupted flag from a corrupted state.

Cost: **+15 flip-flops, +113 cells, 1,471.3650 um2 — 0.53 % of the
unprotected core**. The strobe gate itself costs **zero flip-flops**,
proved by mutation: 801 flip-flops with or without it
**[measured, `docs/56`, baselines re-measured at commit `4b77af1`]**.

The whole-SoC behavioural invariant is **215,428 cycles with 27 of 27
checks passing, unchanged across that wave** — the drift `docs/55` had
to calibrate against is exactly zero here.

### 9.7 The watchdog's own state

**Population: the watchdog block's own flip-flops, 162 injections
[measured, `docs/41-watchdog-hardening.md` section 8.2].**

- **126 of 126 injections into the protected 22-bit word came back
  CORRECTED.** Zero SDC, zero HANG, zero disarms.
- **The counterfactual is what makes that mean something.** On a
  `HARDEN=0` build of the same file, **2 of 32 injections left the
  watchdog reading disarmed**, and one of those two was the campaign's
  only HANG — which is the failure the block exists to prevent.

**One earlier headline about this block has been retired and it is
retired here too.** `docs/41` reported zero spurious escalations;
`docs/43` section 8.4 measured **7 spurious escalations in 1,232
survivable upsets, 0.6 % [0.3–1.2]**, on the windowed kick mode W7, and
states plainly that `docs/41`'s headline is gone.

**W7 is recommended for removal and W8 is kept.** `docs/46` measured a
second, more realistic workload — a statically partitioned,
PMP-isolated supervisor — and found that a time-triggered kick has a
jitter ratio of **1.412**, which admits exactly one window setting, and
that a **work-triggered dispatch has a ratio of 2.104, for which no
window setting is feasible at all**. Its 812-injection campaign found
W7 converting 2 silent corruptions into announced failures and causing
about 2 spurious escalations — a benefit of 0.25 % [0.07–0.89] against
a cost of 0.27 % [0.08–1.00], **statistically indistinguishable, both
from single sites**. The kick budget W8 caught **4 of 4** of `docs/42`'s
hang-class faults, where the window caught **0 of 4**.

### 9.8 What is not protected

- **The whole of Ibex except its register file.** The fetch FIFO, the
  IF/ID pipeline register, the controller, the CSR file, the PMP
  configuration, the load-store unit and the multiplier-divider are
  unprotected, and section 9.3's residual 1.3 % ± 0.4 lives in them.
  There is no lockstep and no shadow register file, by decision.
- **`mtime` and `mtimecmp`**, 128 flip-flops, ranked first for the next
  hardening wave since `docs/44` and still unaddressed.
- **The memory contents.** `soc_mem.v` stores no check bits. The SCRUB
  peripheral slot is a reserved address; there is no memory scrubber.
  The 72 KiB of RAM and ROM are the largest storage in the design and
  **nothing checks a word read out of them**.
  *Corrected 2026-09-05:* done in `docs/67-memory-protection.md` — four
  (16,8) byte codewords per RAM row, one (39,32) word codeword per ROM
  word, a scrubber under each memory and the SCRUB slot implemented as
  their counters.
- **The fabric and the APB bridge**, other than the error slave's
  refusal to alias.
- **The die's own event path, queue storage and register-bank
  configuration**, which is where section 9.4's six remaining silent
  corruptions come from.
- **Telemetry in both directions.** BUSSTAT's counters saturate and are
  themselves unprotected. `docs/21` section 6.4's host-side rule
  applies here unchanged and costs nothing: **treat any disagreement
  between a counter reading non-zero and its sticky bit as a detected
  fault of the telemetry itself.**

### 9.9 Bounds on all of section 9

- **EVERY TRIPLICATED ROW IN THIS SECTION IS A NETLIST PROPERTY, NOT A
  PROPERTY OF A DIE.** *Added 2026-09-09.*
  `docs/79-replica-placement-and-equivalence.md` measured the frozen
  pilot's three replica banks on the sign-off layout's own DEF: the
  three banks share one region, **103 of the 165 configuration
  flip-flops have their nearest fellow in a different replica** against
  a median separation of 113.47 um, and 49 cross-replica pairs abut. The
  picture reproduces on this design's own `soc_top` layouts across three
  triplicated structures and three hardens. No placement constraint was
  applied and none is available before the shuttle. **A distance is not
  a safety argument in either direction** — nothing measured here says a
  common-mode upset occurs at any fluence, and nothing says a different
  separation would prevent one. What it removes is the evidence for
  reading any row above as a statement about the manufactured part.
- **The fault model is single-bit, flip-flop-only, at RTL, with zero
  delay.** No multi-bit upsets, no single-event transients in
  combinational logic — so every codec, voter and multiplexer is
  outside the model entirely — no stuck-at faults, no latch-up, no
  gate-level and no timing-aware injection.
- **`soc_top` has never been simulated as a netlist**, so the class of
  defect that only a netlist reveals — section 9.4's collapsed replicas
  — is covered here by cell-counting guards and by mutation testing,
  not by a gate-level campaign.
  *Corrected 2026-09-10:* it has been, since
  `docs/74-core-gate-level-campaign.md`, on the sign-off layout's own
  netlist (`hw/soc/out/s70-rom0-syn/soc_top.netlist.v`,
  `md5 a8d5ef81446ce6d2aa2eb4c1e0fdff79`, 5,873 flip-flops, six
  behavioural SRAM macros, Icarus 13). The bullet is left standing
  because the rest of it still holds where it matters: that campaign
  replayed `docs/43`'s core records and injected into the watchdog's
  replica banks, and it is **not** a whole-SoC gate-level campaign —
  section 9.10 says how much of the design any campaign of any kind has
  ever pointed at.
- **Small samples.** One to five injections per bit position; 4 to 32
  per group in the die's campaign, 100 per stratum elsewhere. Every
  interval quoted is a Wilson interval and every zero is a ceiling.
- **One workload per campaign**, one geometry, one configuration.
- **Nothing here is a rate**, restated because it is the single
  easiest figure in this document to misuse.

### 9.10 Two SoC-wide denominators, added 2026-09-10

Every campaign above states its own population, and section 9.2 rule 3
forbids pairing figures across populations that differ. What no
document in this repository stated until this section is the pair of
numbers that bound section 9 as a whole when a reader turns it into the
sentence *"the SoC was fault-injected"*: **how much of the design any
campaign has ever pointed at**, and **how much of the manufactured die
a flip-flop-only fault model can reach at all**. Both are properties of
the placed design of record — the run `hw/soc/pnr/runs/s71boot`, whose
netlist is `hw/soc/out/s70-rom0-syn/soc_top.netlist.v`,
`md5 a8d5ef81446ce6d2aa2eb4c1e0fdff79`, the netlist `docs/74`
simulated and `docs/70` and `docs/71` placed. Neither number is a
result; both are denominators, and their only job is to stop the
numerator being read as the whole.

#### 9.10.1 About a fifth of the design's flip-flops are in a block no campaign has ever injected into

The design has **5,873 flip-flops** — `python3 hw/soc/fi/gl_netlist.py
hw/soc/out/s70-rom0-syn/soc_top.netlist.v` prints `5873 flip-flops`,
and the flow's own `hw/soc/pnr/runs/s71boot/final/metrics.json` carries
`design__instance__count__class:sequential_cell = 5873` from the
placed database. Attributed to the top-level instance each belongs to:

| Block | Flip-flops | Campaign that has injected into it |
|---|---:|---|
| `u_ibex` | 2,320 | the core campaign — `docs/42`, `docs/43`, `docs/74` |
| `u_npu` | 2,090 | the connection — `docs/52`, `docs/55`, `docs/56` — and the die, `docs/16`, `docs/26`, `docs/32` |
| `u_clint` | 170 | `mtime` and `mtimecmp` — `docs/58` |
| `u_boot` | 143 | `docs/69` |
| `u_timer0.u_wdog` | 99 | `docs/41` |
| **covered** | **4,822** | |
| `u_qspi` | 186 | **none** |
| `u_timer0`, the GPTIMER half | 169 | **none** |
| `u_gpio` | 144 | **none** |
| `u_busstat` | 144 | **none** |
| `u_apb` | 97 | **none** |
| `u_scrub` | 78 | **none** |
| `u_bus` | 55 | **none** |
| `u_uart0` | 52 | **none** |
| `u_ram` | 47 | **none** |
| `u_pnp` | 28 | **none** |
| `u_rom` | 3 | **none** |
| **in no campaign** | **1,003** | **17.08 % of 5,873** |
| not placed by any instrument used here | 48 | unknown, so the figure above is a range |

**So: 1,003 to 1,051 flip-flops, 17.1 % to 17.9 % of the design, are in
a block no fault-injection campaign in this repository has ever
injected into.** The flip-flop counts are **[measured, 2026-09-10]**
from the netlist named above; the percentages are **[estimate]** in
this document's section 0.1 sense — arithmetic on those counts over the
denominator 5,873, and nothing else. `u_ram`, `u_rom` and `u_scrub`
are in that set on purpose and not by oversight: `docs/67`'s campaign
injects into the **contents** of the two memories, 1,000 draws by
region of the link map, and a memory word is not a flip-flop of this
netlist. Their control, ECC and scrubber flip-flops have never been a
site.

**Three things this table is not.**

1. **It is a block granularity, so 1,003 is a floor and not the count
   of un-injected flip-flops.** A block counts as covered here if any
   campaign has ever injected into it, not if every flip-flop in it is
   a site. `docs/58` injects into `mtime`'s 72 stored bits and
   `mtimecmp`'s 64, which is 136 of `u_clint`'s 170; `docs/41` injects
   into the watchdog's own state; the core campaign's site list is 2,451
   RTL bits and `docs/74` found 131 of them with no netlist twin. The
   number of flip-flops in this design that are not a site of any
   campaign is **larger than 1,003**, and no document here states it.
2. **It says nothing about protection.** Section 9.1 is the protection
   table and section 9.8 is the list of what is unprotected. A block
   can be injected into and unprotected — most of `u_ibex` is — and a
   block can be unmeasured without being unprotected.
3. **It is not a rate**, per section 9.2 rule 1, and the blocks are of
   very unequal size, so the percentage is a share of flip-flops and not
   a share of anything that arrives from space.

**What is in the uncovered set, and the claim that is too strong.**
The whole of `soc_busstat` is in it — all 144 flip-flops, which is
every counter and sticky bit **the SoC's own upset telemetry reports
through**: `CNT_RFSEC`, `CNT_RFRD`, `CNT_RFDED`, `CNT_TMRERR`, the NPU
fault lines `docs/55` added and the eight `docs/58` added. Section 9.8
already says those counters are unprotected; this section adds that
they have also never been injected into, so *"treat any disagreement
between a counter reading non-zero and its sticky bit as a detected
fault of the telemetry itself"* — `docs/21` section 6.4's host-side
rule, restated in 9.8 — is the only defence the part has for them and
it has never been tested against a fault in them.
**It is not true that the uncovered set contains every fault counter in
the design**, and this section states the narrower claim on purpose:
`WDOGSTAT.RSTCNT` is in `u_timer0.u_wdog`, the `NPUCFG` cause bank and
the queue drop counters are in `u_npu`, and the die's `CNT_SEC`,
`CNT_DED` and `CNT_TMR` are in the die — three blocks a campaign has
injected into.

**How the attribution was made, and where it is weaker than the
number looks.** Four instruments, in order, and each flip-flop is
placed by the first one that reaches it:

- **name**, 5,450 of 5,873: the Q net carries a hierarchical RTL name,
  so the first path component is the block.
- **port**, 221: the Q net is a `soc_top` wire — `s_rdata_npu`,
  `pwdata`, `gpio_o`, `paddr` and eleven others — and the block is the
  instance whose output drives that wire in `hw/soc/rtl/soc_top.v`.
- **cone**, 77: the anonymous halves of the three TMR replica banks,
  reached from the voter's own input nets. This is the correction
  `docs/74` section 6.6 and `docs/75` forced, and it matters here for
  the same reason it mattered there.
- **fan-in / fan-out vote**, 77: an anonymous flip-flop all of whose
  fan-in cone, or all of whose fan-out, lands in one block is assigned
  to that block; ambiguous ones are left unplaced.

**48 are left unplaced and they are counted as unknown rather than as
either answer.** Three independent checks say the attribution is not
inventing blocks: `u_uart0` reads 52 and `u_pnp` reads 28, which are
`docs/45` section 6.2's separately synthesised block counts **exactly**;
and `u_clint`'s 170 plus the one unplaced flip-flop on `irq_soft_o`,
which is a CLINT output, is `docs/45`'s 163 plus the 8 `docs/58` added.

**Reproducing the census, and the instrument's own limit.** The name
census is one committed tool and one pipeline:

```bash
python3 hw/soc/fi/gl_netlist.py \
    hw/soc/out/s70-rom0-syn/soc_top.netlist.v --list /tmp/flops.tsv
awk -F'\t' 'NR>1 { q=$4; gsub(/^\\/,"",q); sub(/ ?\[[0-9]+\]$/,"",q)
    n=split(q,p,"."); if (n<2) b="<no hierarchical name>"
    else if (p[1]=="u_timer0") b=(p[2]=="u_wdog")?"u_timer0.u_wdog":"u_timer0(gptimer)"
    else b=p[1]; c[b]++ } END { for (k in c) printf "%6d  %s\n", c[k], k }' \
    /tmp/flops.tsv | sort -rn
```

and the three cone counts are
`python3 hw/soc/fi/gl_netlist.py <netlist> --tmr-census wdog` and the
same for `boot` and `npu`, which print `cone 29 / by_q_net 29 / 14 / 15`
and its two analogues.

**That name census alone answers 1,251, and 1,251 is wrong high.**
It reports 4,622 flip-flops in the five covered blocks and therefore
**1,251 in no campaign, 21.30 %** — and it is the census by Q-net name
that `docs/74` section 6.6 caught undercounting a replica bank and
`docs/75` convicted in general. It undercounts here too: **423 of the
5,873 carry no hierarchical name at all**, and of those 423, 200 belong
to blocks a campaign has injected into, 175 to blocks none has, and 48
no instrument used here places. **A reader who runs only the pipeline
above will get 21.3 % and should not publish it**; the answer this
section stands behind is 17.1 % to 17.9 %.
**The listing that performs the port, cone-beyond-`--tmr-census` and
vote steps is not committed to this tree**, so 9.10.1's 1,003 is
reproducible in method and by its cross-checks and is **not**
reproducible by a command in this repository. That is an owed artefact
and this sentence is the whole of the disclosure; the 1,251, the 5,873
and the three cone counts are each reproducible by a committed tool
today.

> **DISCHARGED 2026-09-11.** The paragraph above stands as it was
> written and is no longer true. `hw/soc/fi/gl_coverage.py` performs all
> four steps and is committed:
>
> ```bash
> python3 hw/soc/fi/gl_coverage.py \
>     hw/soc/out/s70-rom0-syn/soc_top.netlist.v --verify
> ```
>
> It is a **reimplementation from this section's prose**, not the
> original listing, which is gone. That makes the agreement worth more
> than a re-run would have been and worth less than a re-execution:
> **all seven published figures come back — 5,450 name, 221 port, 77
> cone, 77 vote, 48 unplaced, 1,003 uncovered, 5,873 total** — from a
> tool written against the description rather than against the numbers.
> `--verify` exits non-zero on any disagreement and its own failure text
> forbids closing one by tuning the tool.
>
> One thing the reimplementation found that the prose did not state:
> **the vote step has to be run to a fixed point.** A vote reads the
> placements that exist when it is taken, so a single sweep in
> flip-flop-index order places 76 and leaves 49 unplaced, and the same
> rule iterated places 77 and leaves 48. The flip-flop at issue is
> `_77779_`, whose fan-in cone and fan-out are both entirely `u_npu`
> and which is therefore not ambiguous at all — only undecided until
> its neighbours are decided. An instrument whose answer depends on the
> order it walked the file is measuring the file.
>
> The mutation below reproduces too: renaming `u_busstat.irqen` into
> `u_ibex` moves the attribution from **1,003 to 995** and `u_busstat`
> from 144 to 136, under `--mutate u_busstat.irqen:u_ibex.mutant_irqen`.
> `sw/tests/test_gl_coverage.py` runs both directions.

**Both instruments were mutated to show they can move.** Renaming the
eight flip-flops of `u_busstat.irqen` to `u_ibex.mutant_irqen` in a
copy of the netlist moves the name census from 1,251 to 1,243 and the
full attribution from 1,003 to 995. A check that reported the same
number on a netlist in which eight uncovered flip-flops had been
relabelled into a covered block would not be measuring coverage.

#### 9.10.2 The flip-flop-only fault model makes 96.7 % of the manufactured cells non-sites

Section 9.9 already says the fault model is single-bit, flip-flop-only,
at RTL and with zero delay, and that every codec, voter and multiplexer
is therefore outside it. This is that sentence as a number, on the
placed design rather than on the RTL:

| Denominator, from `hw/soc/pnr/runs/s71boot/final/metrics.json` | Instances | Flip-flops | Sites | **Non-sites** |
|---|---:|---:|---:|---:|
| every placed instance — `design__instance__count` | 176,663 | 5,873 | 3.32 % | **96.68 %** |
| standard cells excluding fill — `design__instance__count__stdcell` | 60,868 | 5,873 | 9.65 % | **90.35 %** |

The three instance counts are **[measured, 2026-09-10]**, read out of
the run's own metrics and confirmed against its DEF; the two
percentages are **[estimate]**, being 5,873 divided by each
denominator.

```bash
python3 -m json.tool hw/soc/pnr/runs/s71boot/final/metrics.json \
  | grep -E 'design__instance__count(__stdcell|__class:(sequential_cell|fill_cell|macro))?"'
```

which prints 176,663, 60,868, 5,873, 115,789 and 6; and the same
figures come out of the run's own DEF, which is the artefact the
metrics are derived from:

```bash
awk '/^COMPONENTS/{f=1;next} /^END COMPONENTS/{f=0}
     f&&/^ *-/{n++; if ($3 ~ /^sg13g2_dfrbp/) ff++}
     END {printf "instances %d  flip-flops %d  non-sites %.4f %%\n", n, ff, 100.0*(n-ff)/n}' \
  hw/soc/pnr/runs/s71boot/final/def/soc_top.def
```

→ `instances 176663  flip-flops 5873  non-sites 96.6756 %`. Retyping
100 of the `sg13g2_dfrbpq_1` instances to `sg13g2_buf_1` in a copy of
that DEF moves it to 96.7322 %, which is the mutation that shows the
count can be wrong.

**Read the first row for what it is.** 115,789 of those 176,663
instances are fill and decap and 792 are antenna diodes: cells that are
manufactured, occupy the die and hold no state, so a fault model that
only flips flip-flops was never going to reach them and their presence
in the denominator is not a finding. **The 96.7 % must not be read as
"96.7 % of the logic is unmodelled."** The row that carries the
engineering is the second: **of the standard cells this design is
actually built from, 90.35 % are not a site of any campaign in this
document** — 37,087 multi-input combinational cells, 11,530 timing-repair
buffers, 2,787 buffers, 1,773 inverters, 745 clock buffers, 280 clock
inverters, and the six SRAM macros whose contents `docs/67` injects
into and whose peripheral logic nothing does.

What that bounds is stated narrowly, because the tempting version is
not supported. It does **not** say 90 % of upsets are missed: a
combinational cell has no state, a single-event transient in one is
captured only if it arrives at a flip-flop inside a setup-hold window,
and this repository has measured no cross-section, no charge-collection
radius and no LET threshold for this process — the same prohibition
`docs/79` places on converting micrometres into a coincidence
probability applies here to converting cell counts into a fault share.
What it does say is that **every mechanism in section 9.1's table is
implemented partly in cells this fault model cannot fault**: the (39,32)
and (72,64) decoders, every majority voter, the parity trees and the
dual-rail comparators are combinational, and `docs/74` counts the SECDED
decoder alone at 528 combinational cells, none of them a site. A voter
that is itself upset is outside every number in section 9.

---

## 10. Performance, in the units the mission states

`docs/53-workload-and-the-clock.md` turned the four prose mission
profiles of `docs/05` section 3.4 into cycles per second and measured
what this design delivers per cycle. **It is the only place in this
repository where a requirement and a measurement are put next to each
other**, and it is the reason this datasheet has no frequency rating.

### 10.1 What the design delivers per cycle

| Quantity | Value |
|---|---|
| One node-window register access | **176 clock cycles**, of which 171 is the serial frame **[measured]** |
| Per serial frame, whole-system | **182.57 cycles** **[estimate, solved from two measured workloads; the model predicts four other measured workloads to within 0.8 %]** |
| Per inbound pin event | **6.86 cycles** **[estimate, same]** |
| Bring-up program, whole | **215,428 cycles**, 27 of 27 checks passing **[measured, `docs/56`]** |
| One six-frame inference | **3,378 cycles** **[measured, `docs/53` section 4.1]** |

**The serial transport is 93 to 98 % of every workload measured, and it
is a 27x factor per event against the clock's 1.16x.** The replacement
is already specified — a symmetric mesh link at one event per cycle,
`docs/10` section 8 item 2 — and it is a factor of **182**.

### 10.2 The requirement against the delivery

| Profile, `docs/05` section 3.4 | Requirement | Result |
|---|---|---|
| Event-camera payload, at a flown instrument's measured rate | the heaviest of the four | **5.9 % of the cycle budget**, and **10.2 % at two standard deviations above its mean** **[estimate, on a measured event rate and measured per-event costs]** |
| Telemetry health monitoring, nine channels | the lightest | **0.004 %** — four to five orders of margin |
| Reaction faster than a ground loop | a latency requirement | **13.06 us** for one frame and **78.38 us** for the whole six-frame inference — met by **five orders of magnitude** |
| Long idle phases | **"idle at microwatts and wake on activity"** | **NOT MET**, by four orders of magnitude. Section 11.3 |

**[estimate throughout, `docs/53` section 6; the cycle counts are
measured and the periods and rates are the arithmetic on them]**

> **Three of four profiles are met with two to five orders of magnitude
> of margin. The fourth is a power requirement the design does not meet
> and the mechanism is named: one clock, one mode, no gating.** That
> claim — a derived requirement against a measurement — is the
> strongest thing this project can say externally, and it is worth more
> than a frequency.

### 10.3 Why no frequency appears in this datasheet

Restating section 0's third point with its three grounds, because this
is where a reader would look for the number:

1. **The derived requirement is not a frequency at all.** It is "the
   part must carry N serial frames per second", and at the geometry
   that exists N is capped by the fabric and not by the clock. A
   requirement written as a frequency would be a requirement written in
   the units of the answer.
2. **`docs/05` section 4 rule 5 forbids it.** A figure published
   externally must be traceable to measurement or clearly labelled as a
   design target. The number the layout reached is a measured
   *non-closure* from a run that fails setup on 2,003 endpoints, fails
   max slew at the slow corner and fails max cap at all three, on a
   layout that has never seen Magic DRC, KLayout DRC or Netgen LVS.
3. **Two parts in one project would carry two clocks, and one of them
   is being fabricated.** The shuttle tile declares one figure and this
   design would carry another; a reader would take away that the
   project cannot say what its clock is, when the correct answer is
   that they are different parts on different schedules.

**The 20 ns SDC period is kept as a flow constraint and not as a
requirement**, because four rounds of measurement were made against it
and changing it would make every slack in the corpus incomparable for
no gain.

---

## 11. Electrical characteristics

### 11.1 Timing

**All figures below are from one run: `hw/soc/pnr/runs/full3`,
LibreLane v3.0.5, OpenROAD 26Q1-2938-g0e2d771c5e, `ihp-sg13g2` at
`c4b8b4e5…`, at a 20 ns SDC period, on extracted parasitics from
`OpenROAD.RCX`, with a 5 % timing derate applied as a float and 0.25 ns
of clock uncertainty.** Slack in ns.

| Corner | setup worst | setup violations | setup TNS | hold worst | hold violations | max cap | max slew |
|---|---:|---:|---:|---:|---:|---:|---:|
| `nom_slow_1p08V_125C` | **−3.2029** | **2,003** | **−2,075.11** | +0.4082 | 0 | **10** | **14** |
| `nom_typ_1p20V_25C` | +5.7231 | 0 | 0.0000 | +0.0367 | 0 | **10** | 0 |
| `nom_fast_1p32V_m40C` | +10.6634 | 0 | 0.0000 | **−0.2015** | **3** | **12** | **1** |

**[measured, `hw/soc/pnr/runs/full3/19-openroad-stapostpnr/summary.rpt`,
reported in `docs/47` section 8.2 and independently reproduced in
`docs/53` section 2]**

**It fails setup, hold, max capacitance and max slew.** Four
observations a reader needs with that table:

- **Three of those five failures are visible only because four
  configuration keys were set before the run rather than audited after
  it** — `TIME_DERATING_CONSTRAINT` as a float, and the setup, hold,
  max-cap and max-slew violation-corner keys all bound to every corner.
  In the shipped flow configuration setup at the slow corner, max cap
  and max slew would have printed warnings and the flow would have
  exited zero.
- **`design__violations` reads 0 and `flow__errors__count` reads 0** in
  the `final/metrics.json` of that same run. **The aggregate metric
  does not aggregate.** Reading it would have said this layout is fine.
- **`design__max_fanout_violation__count` is 293** and there is no
  max-fanout checker step in the flow at all. `Checker.WireLength` is
  skipped because neither PDK sets a threshold — and the longest net is
  **2,332.02 um in a 2,306 um die**, which arrives from the one checker
  that cannot fail.
- **The fast corner carries a 15 C mismatch** between the SRAM macros,
  characterised at −55 C, and the standard cells around them at −40 C.
  The PDK ships no −40 C macro file, so the cross-corner map is forced.
  The hold result at that corner should be read with that in mind.

**What did close, and it is not a short list:**

| Check | Result |
|---|---|
| Detailed-routing DRC | **0** after 5 iterations |
| Disconnected pins | **0** |
| Power-grid violations | **0** on both rails |
| Antenna, post-route | 1 violating net, 1 violating pin; 514 diodes and 606 antenna cells inserted |
| Nets routed | 37,156 signal + 2 special; **286,273 vias, all single-cut** |
| Routed wirelength | **3,095,532 um** |
| Hold at slow and typ | +0.4082 and +0.0367, zero violations |
| Reset recovery, all corners | **no violation** — the asynchronous group went from −49.2780 ns pre-layout to +14.7319 ns post-clock-tree, a swing of 64.0099 ns, built by `repair_design` without being asked |

**[measured, `final/metrics.json` of the same run]**

**The critical path has been the same structure across three
documents**: it starts in Ibex's register-file read-address input and
passes through the fabric's broadcast address bus. The design's
2,611 violating setup endpoints *before* layout were exactly the reset
fanout, and after layout the binding check is a datapath at 2,003
endpoints.

### 11.2 On-chip variation

The derate in the run above **is applied**, as a float. That is worth
stating because it was not always true: this flow's
`TIME_DERATING_CONSTRAINT` was an integer, and LibreLane's `base.sdc`
computes the factor in Tcl integer arithmetic, so a configuration
reporting "Setting timing derate to: 5%" applied a factor of 1.0
**[fact, `docs/28` section 4.4b, corrected in this flow before the
first run]**. Every figure in section 11.1 carries the 5 % derate.

### 11.3 Power

> ~~**[in flux] — read section 13 before quoting anything in this
> subsection.** An activity-annotated power measurement against this
> netlist is being produced as this datasheet is written, and it will
> supersede the figures below. That work is not on disk yet and is
> therefore not cited by number here.~~
>
> **IT IS ON DISK, AND IT LANDED THREE DOCUMENTS AGO. Corrected
> 2026-09-12.** `docs/57-power-under-a-duty-cycle.md` measured this
> netlist against the whole-SoC run's own toggle rates, and `docs/76`
> and `docs/77` then measured layouts that contain the accelerator. The
> table below is `report_power` **with no switching activity annotated
> at all** and must not be quoted as the part's power.
>
> How wrong it is, measured rather than estimated: the unannotated
> figure is right to **2.8 %** on the busy case and wrong by a factor of
> **6.29** on the idle one, because the design has a clock gate six
> documents had said it did not. What to quote instead, at the typical
> corner and 20 ns:
>
> | | layout without the accelerator (`full3`, `docs/57`) | layouts with it (`docs/76` s.8, `docs/77` s.9.5) |
> |---|---:|---:|
> | busy | 33.890 mW | 22.142 mW computing (`docs/77`) |
> | idle, core gated in WFI | **5.539 mW** | **8.287 / 8.315 mW** |
> | orbit-average at 0.0044 % duty | 5.540 mW | 8.289 mW |
>
> `docs/77` publishes no busy figure as a property of the design,
> because it measures the busy totals as a placement's rather than the
> part's. The table below is left standing per `docs/64` -- it is what
> `report_power` said on its date -- and it is now labelled rather than
> merely warned about. **A "[in flux]" marker is a promise with a
> deadline, and this one outlived the work it was waiting for by two
> days without anything noticing; nothing in the suite reads a
> subsection's own status flag.**

| Corner | internal | switching | leakage | **total** |
|---|---:|---:|---:|---:|
| `nom_slow_1p08V_125C` | 16.922 mW | 10.751 mW | 0.102 mW | **27.774 mW** |
| `nom_typ_1p20V_25C` | 20.950 mW | 13.787 mW | 0.098 mW | **34.835 mW** |
| `nom_fast_1p32V_m40C` | 28.422 mW | 17.331 mW | 0.342 mW | **46.095 mW** |

**[measured, `hw/soc/pnr/runs/full3/19-openroad-stapostpnr/<corner>/power.rpt`,
the same run whose timing is section 11.1's; first quoted in `docs/53`
section 7.1]**

**Four things must travel with those numbers and the third is the one
that decides how much weight they carry.**

1. **They are at the 20 ns SDC period**, which is the target and not
   the period the design closes at. They describe the design running
   faster than it does.
2. **The split at typ is 60 % internal, 40 % switching, 0.3 % leakage.**
   By group: combinational 46.0 %, sequential 31.4 %, macro 11.7 %,
   clock 11.0 %. **The six SRAM macros are 4.068 mW of it**, which is
   the one term a duty cycle would not remove by clock gating alone.
3. **`report_power` was run with no activity annotation.** The flow
   calls `report_power -corner $corner_name` and nothing before it
   reads a VCD or a SAIF, so the switching figures rest on OpenSTA's
   default propagated activity and not on the toggle rates of any
   program this repository has ever run. **This is an estimate wearing
   a measurement's clothes and it is labelled here as what it is.**
4. **It is nonetheless the only power figure this design has ever had**,
   and what it is worth is its order of magnitude: **tens of
   milliwatts**, which is the unit the one quantified mission
   requirement is stated in. A figure whose order of magnitude can be
   trusted answers a requirement stated to an order of magnitude and
   answers nothing else.

**Energy per inference is invariant under the clock to within
0.045 %** **[estimate, `docs/53` section 7.2]**: it is cycles times
energy per cycle, the cycle count is a property of the design and the
transport, and the only term the clock changes is leakage, which is
0.3 % of the total. **A 3,378-cycle inference costs 2.353 uJ at the
typical corner**, and 2.354 uJ if the clock is 14 % slower.

**And the design idles at 27.8 to 46.1 mW.** At the telemetry profile's
own duty cycle it is 0.0044 % busy and 100 % powered. **That is the one
requirement gap this project has measured and it is four orders of
magnitude wide.** Nothing in this design is aimed at it, and no clock
change is a step towards it.

### 11.4 Supply, I/O and everything else

**[TBD], and no estimate is offered.** Supply voltage and current on
silicon, I/O levels, drive strength, input thresholds, pin capacitance,
electrostatic-discharge ratings, latch-up ratings, absolute maximum
ratings, recommended operating conditions, junction temperature and
thermal resistance. **There is no pad ring, no package and no silicon**,
so none of these has an object to be a property of.

---

## 12. Physical characteristics

**These describe one layout of one netlist, and section 12.3 says what
that layout is not.**

### 12.1 The floorplan

| | |
|---|---:|
| Die | **2306.40 x 2075.22 um = 4,786,290 um2 = 4.7863 mm2** |
| Core | 4,338,910 um2 |
| **Six SRAM macros** | **2,246,899.85 um2, 46.9 % of the die** |
| Standard cells, as synthesised | 396,177.6420 um2, 27,565 cells |
| Utilization, macros included | 62.03 % |
| Utilization, standard cells alone | 21.24 % |

**[measured, `OpenROAD.Floorplan` metrics and LEF `SIZE` arithmetic,
`docs/47` section 6.1]**

**Two macro rows facing a central 700.08 um standard-cell channel, and
the arrangement is forced rather than chosen.** Every `RM_IHPSG13` part
puts **all** of its signal pins on one edge — 352 of them on the
2048x64 and 190 on the 1024x32 — so a macro whose pin edge faces
another macro is a macro the router reaches the long way round. The
lower row is placed mirrored so both rows' pins face the channel.

**Every standard cell in the design sits in that channel or in the two
pockets the shorter ROM macros leave**: 2,092,010 um2 of placeable area
for 396,178 um2 of cells, **18.9 % before repair and clock-tree
buffers** **[estimate, arithmetic on two measurements]**. That is
sparse, and section 11.1's setup failure is where it is charged for.
The channel was sized against a 32 % larger synthesis of the same RTL
than the one actually hardened, so **the die is bigger than this design
needs and nothing has explored what a tighter one would do.**

The core box is site-aligned by construction: 2186.40 um is exactly
4,555 `sg13g2` sites and 1984.50 um is exactly 525 rows, and every
macro origin is an integer number of sites and rows from the core's
corner.

### 12.2 The memories, and why there are six of them

| | |
|---|---|
| RAM, 64 KiB | **four `RM_IHPSG13_1P_2048x64_c2_bm_bist`** |
| ROM, 8 KiB | **two `RM_IHPSG13_1P_1024x32_c2_bm_bist`** |

*Corrected 2026-09-05:* the same four RAM macros now hold 32 KiB of
protected words, and the protected ROM adds two
`RM_IHPSG13_1P_512x16_c2_bm_bist` for its check bits, which
`docs/67-memory-protection.md` section 5 costs from the LEF and has
not placed.
| Macro area against standard cells | **2,246,899.85 um2 against 523,809.64 um2 — the memory is 4.29 times the logic** |

**[measured, LEF `SIZE`, `docs/47` section 4]**

**The denser part was excluded rather than not chosen.**
`RM_IHPSG13_1P_8192x32_c4` is the densest 32-bit part in the library
and would have built 64 KiB in two instances instead of four. It is
also the only 1P part in the family with **no byte-mask port at all**,
so it cannot serve a byte enable without a read-modify-write, which is
a protocol change and not a wrapper. Ibex emits `sb` and `sh`.

**A real SRAM's read arc is the single largest delay in this design and
it is a function of macro depth.** Across the eighteen 1P parts,
`A_CLK` to `A_DOUT` at the slow corner spans **5.2678 ns to
9.6611 ns**, and density improves in the same direction — so **depth
trades area against read delay and the trade is 4.4 ns wide**
**[measured, eighteen Liberty files]**. The parts chosen charge
**9.2941 ns and 7.5512 ns**, which is 46 % and 38 % of a 20 ns cycle
spent inside the macro before the first gate of the read return path.

The macro *input* side is faster than a flip-flop, not slower:
`A_ADDR` setup at the slow corner is **−0.1980 ns**. Its hold is
**+1.3801 ns**, larger than any standard cell in the library, and
section 11.1's fast-corner hold failure is downstream of that.

### 12.3 What the layout is, and what it is not

| Quantity | Value |
|---|---:|
| Standard cells, placed | **37,017**, of which 7,910 are timing-repair buffers and 383 are clock buffers |
| Sequential cells | **3,085**, unchanged from synthesis |
| Fill cells | 132,118 |
| Antenna cells | 606, 3,298.58 um2 |
| Flow runtime | 22.2 min for 35 steps to post-CTS, then 61.1 min for 28 steps to sign-off |
| Peak memory, detailed routing | 3,503 MB |

**[measured, `docs/47` section 8.6; wall times on a shared 20-thread
host, quoted as costs]**

> **THERE IS NO DRC RESULT, NO LVS RESULT AND NO XOR RESULT FOR THIS
> LAYOUT.** `RUN_MAGIC_DRC`, `RUN_KLAYOUT_DRC`, `RUN_KLAYOUT_XOR` and
> `RUN_LVS` are all 0 in the flow configuration, and the reason is a
> prior measured result rather than a schedule. Over **one**
> `RM_IHPSG13` macro in a registered wrapper the three decks return
> **1,106,478 Magic DRC error boxes** — every one inside the macro
> footprint and none outside — **2,316 KLayout deep-mode DRC errors**
> in three of 173 rules, and **359 Netgen LVS errors**, of which 158
> are unmatched pins because the extracted bus delimiters are `[15]`
> where the CDL's are `<15>` and the GDS cell names carry no
> configuration infix where the CDL's do. `docs/12` sections 7.5 and 8
> record that as a **NO-GO on RM_IHPSG13 for this PDK version**, tied
> to IHP-Open-PDK issue #239.

`docs/54-klayout-deck-and-the-macro.md` examined the 2,316 and closed
the remaining exit:

- **1,022 of them are counted twice** — two rules flag the identical
  1,022 polygons, symmetric difference zero — and the whole family is
  an **artefact**: the rules check a Schottky diode against a layer the
  macro has **zero drawn polygons of** and the deck synthesises from
  NWell, and 2,303 of the 9,275 flagged shapes are boolean-clip
  remnants smaller than any drawn contact in the file.
- **272 of them are real geometry in a contested scope.** 99.93 % sit
  at exactly 0.02 um of contact enclosure against a 0.05 um
  requirement — systematic, and flat and deep agree, so it is not a
  hierarchy artefact. All of it is inside a vendor-drawn SRAM marker
  layer covering 66.9 % of the macro that the deck reads and then
  **never uses in any rule**. It is not waivable on that evidence.
- **The deck that returns zero is the PDK's own *unverified* residual
  set**, which its README calls "not verified or tested", against the
  main set the same README calls "intended for foundry precheck
  purposes". **Swapping decks trades a verified deck for an untested
  one and is not the exit.**
- **And even with both DRC defects fixed upstream, LVS still fails**,
  for a hierarchy-naming reason that is not fixable from this
  repository. A design that passes DRC and fails LVS is not signed off.

**What that costs this document is real and is not being minimised.** A
first layout that has not been DRC'd or LVS'd is not evidence that it
is manufacturable or that it implements its netlist. It is evidence
about timing and area, and that is all it is offered as.

**What is geometrically verified in this project is the pilot**, which
is standard-cell-only and contains no `RM_IHPSG13` instance: on the
submitted 6x2 shape it reports Magic DRC 0, KLayout DRC 0, Netgen LVS 0
on all seven counters, antenna 0 nets and 0 pins with zero repair
diodes, and 0 power-grid violations **[measured, `docs/21` section 7.2,
`docs/23` sections 2.1, 3.3 and 4.4]**. The Magic/KLayout XOR is not
run on IHP and is not claimed there either.

### 12.4 One thing the layout does not contain

**`soc_npu` is not in it.** The netlist that was placed and routed is
`soc_top` as of `docs/45`; the NPU subsystem is 76 % of the core by
cell area and would change the floorplan question rather than fit
inside its answer. **Every figure in sections 11 and 12 therefore
describes a design that has no neuromorphic node in it**, which is the
single largest caveat on this document's physical numbers.

---

## 13. Figures in flux, and figures that are TBD

### 13.1 [in flux]

Measured, but against an artefact that is being regenerated or a source
file that is being edited as this is written. **Do not quote these
against a fixed value.**

| Quantity | Where | Why it will move |
|---|---|---|
| **Power at all three corners**, section 11.3 | 27.774 / 34.835 / 46.095 mW | The figures are `report_power` with **no activity annotation**. An activity-annotated measurement against this netlist is in progress; the testbench already dumps a VCD behind a plusarg and the netlist is on disk, so the input exists. **The order of magnitude — tens of milliwatts — is what should be quoted until it lands, and nothing finer** |
| **CLINT area and register behaviour**, section 5.4 | 1,043 cells / 163 flops / 16,712.8164 um2 | `hw/soc/rtl/soc_clint.v` and `hw/soc/rtl/soc_top.v` are modified in the working tree as this is written and are not the committed files this row was measured from |
| **Floorplan geometry**, section 12.1 | die, core, channel, utilization | The floorplan is a **first** floorplan and was not swept. Its shape is forced by the macros' single-edge pin geometry, but the die dimensions, the channel height, the macro ordering within a row and the target placement density are one point in a space nobody has explored, and section 11.1 is the evidence that the point matters. Work on this is in progress |
| **Cocotb and formal test counts**, section 15 | 131 test functions, 33 formal tasks | Collection counts against the working tree, which three concurrent editors are changing. **Collection is not execution** |

Where one of the three items above is superseded by a document that
does not yet exist on disk, this datasheet names the quantity and not
the document, because a cross-reference to a file that has not been
written is a broken link.

### 13.2 [TBD]

Not known, and no estimate is offered.

- **Every silicon property.** There is no die.
- **DRC, LVS and XOR for this design.** Section 12.3. Blocked on the
  PDK, not on effort.
- **RTL-to-netlist equivalence for `soc_top`.** `Yosys.EQY` is off and
  `hw/soc/formal/` has never been pointed at the top level.
- **Gate-level simulation of `soc_top`.** Never run. The macros are
  blackboxes in the placed netlist and the ROM has no contents, so it
  would need the PDK's behavioural macro models and a way to load an
  image.
- **Gate-level fault injection.** Every campaign in section 9 is at
  RTL. The one class of defect that only a netlist reveals is section
  9.4's collapsed replicas, and it is covered here by cell-counting
  guards and mutation testing rather than by a campaign.
- **Any physical figure for a layout that contains `soc_npu`.** Section
  12.4.
- **Timing, area or power for the NPU subsystem.** It has never been
  through STA at any corner.
- **IR drop.** The supply-location file is unset, so the report's
  voltages have nothing behind them; only its **connectivity** result
  is used, which is what catches an unpowered macro.
- **Multi-mode and multi-corner analysis beyond the three PVT corners,
  scan insertion, DFT, ATPG, memory BIST usage, and any test coverage
  figure.** One clock, one mode, no scan, no test.
- **Total ionising dose, single-event upset cross-section, LET
  threshold, single-event latch-up and single-event functional
  interrupt.** All require beam data this project does not have.
- **Package, thermal, operating temperature range, lifetime and
  reliability.**
- **Anything about the shuttle die's behaviour in silicon.** Silicon is
  expected 2027-06-25 with boards around 2027-08, and that is a
  schedule, not a measurement.

---

## 14. Disagreements between repository documents found while writing this

Recorded, not corrected — these files are owned elsewhere.
`docs/21-pilot-datasheet.md` section 10 is the precedent for keeping
this section in a datasheet rather than quietly picking a side.

**Resolved 2026-09-05.** Each item below has since been corrected in
place in the document that owns it, with the original statement left
visible, and `docs/64-document-reconciliation.md` records the evidence
and names the file that settles each one. The list is kept as written;
the *Resolved* line under each item is what changed.

1. **The pilot fault-injection campaign is reported three different
   ways and the file disagrees with the document that owns it.**
   `docs/16-fault-injection-campaign.md` section 3 and its header table
   state that `hw/tb/fi_campaign_results.json` holds the
   **366-injection** wave-6 log, 568 s, with **18 SDC (4.9 %)**. The
   file at commit `7721719` reports `"total": 378`, `wall_seconds`
   445.7, and a histogram of MASKED 97 / CORRECTED 193 / DETECTED 82 /
   **SDC 6** / HANG 0. **`docs/30-dispatcher-protection.md` and
   `docs/33-rail-transform.md` both cite 378 injections and 445.7 s**,
   so the file and two documents agree and `docs/16`'s headline is the
   outlier. Separately, **`docs/21-pilot-datasheet.md` section 6.2
   still names the 335-injection run with 26 SDC (7.8 %) as its
   "campaign of record"**, which is two waves behind both. This
   document follows the file, per section 0.2. **`docs/16` owns the
   campaign and is where this should be settled.**
   *Resolved 2026-09-05:* both outliers quoted real earlier logs —
   `docs/21`'s at `0448282`, `docs/16`'s at `2c6c052` — and neither is
   a transcription error. Both are corrected in place; the committed
   file, blob `312d3c76` (378 injections, 6 SDC), is the campaign of
   record and this section already quoted it. `docs/64` section 3.1.

2. **`docs/00-index.md` lists `docs/56-npu-event-engine-hardening.md`
   twice**, as two adjacent table rows with different purpose text.
   Only one such document exists. **[measured,
   `grep -c 'docs/56-npu-event-engine-hardening.md' docs/00-index.md`
   returns 2]**. This document's own index row is added after both.
   *Resolved:* the duplicate row was removed in the commit that added
   this document, `62f1aff`, so the statement above was stale as
   committed; the count is 1 at every commit since **[fact, `git show
   <commit>:docs/00-index.md | grep -c`]**. `docs/64` section 3.7.

3. **The CLINT's area is published as two different numbers.**
   `docs/40-interrupts-timers-watchdog.md` section 9 says 1,038 cells
   and 16,683.48 um2; `docs/45-soc-top-synthesis.md` section 6.2 says
   1,043 and 16,712.8164 for the same block. The recipe is the same and
   the sessions are different. Neither is wrong and they are not
   distinguished where they are quoted. The same pattern recurs for the
   five-port fabric, where `docs/39` publishes 808 cells / 9,688.29 um2
   and `docs/51` section 11 re-measures the same configuration at HEAD
   as 812 / 9,917.36 — but **`docs/51` states the difference and names
   the cause**, which is what the CLINT rows do not do.
   *Resolved:* a note beside each CLINT row — `docs/40` section 9,
   `docs/45` section 6.2 — names the cause, the source list, and points
   at `docs/45` section 4.3 where both figures reproduce exactly.
   Neither number changed. `docs/64` section 3.2.

4. **The Ibex core's shipped area is quoted as two different numbers
   for two different contents, and they are easy to confuse.**
   `docs/43-core-hardening.md` reports **313,733.1960 um2** for the core
   with the SECDED register file; `docs/44` and `docs/45` report
   **316,051.6590 um2** for the core with the register file *and* the
   telemetry report cone. Both are correct for what they measure and
   the difference is 2,318.5 um2 of content, not of method — but a
   reader who takes either as "the core" will be wrong about the other.
   *Resolved:* `docs/43` section 7.1 now says its figure is not the
   shipped core and names `docs/44` section 7.1's 316,051.6590 and
   what the 2,318.4630 um2 of content is. Neither number changed.
   `docs/64` section 3.3.

5. **`docs/41-watchdog-hardening.md`'s zero-spurious-escalation
   headline is superseded and the supersession lives in a different
   document.** `docs/43` section 8.4 measured 7 spurious escalations in
   1,232 survivable upsets on the windowed mode and says plainly that
   `docs/41`'s headline is gone. `docs/41` does not say so.
   *Resolved:* it does now — the retirement is stated in `docs/41`
   section 1's verdict row and section 8.3, with the `docs/43` figure.
   `docs/64` section 3.5.

6. **Five documents state "no power number" while the file was in the
   run directory they report from.** `docs/45` section 8, `docs/47`
   section 9, `docs/48` section 8, `docs/49` section 12 and `docs/50`
   section 10 all end with the line "one clock, one mode, no scan, no
   test, no power number", and `OpenROAD.STAPostPNR` had written a
   `power.rpt` per corner in the very run four of them quote timing
   from. `docs/53` section 7.1 found it. **The five documents have not
   been amended**, so a reader who consults any of them will be told
   the figure does not exist.
   *Resolved:* all five lines are struck through in place and each
   names `docs/53` section 7.1 and `docs/57` section 5. `docs/57` had
   superseded all five and amended none. `docs/64` section 3.4.

7. **The event engine's design-weighted contribution is stated as two
   numbers that are not a before and after.** `docs/52` gives 1.71
   points and `docs/56` gives 0.58 for the same design, and the
   difference is the stratification scheme rather than any change to
   the RTL. `docs/56` section 3.4 flags this itself and says neither
   figure is wrong; it is recorded here because the two appear in
   adjacent documents and invite exactly the subtraction that is
   forbidden.
   *Resolved:* `docs/52` section 6.2's table now carries the sentence
   beside the 1.71, naming both estimators and both denominators;
   `docs/56` section 3.4 already had it. `docs/64` section 3.6.

---

## 15. Verification status, and how to reproduce it

### 15.1 What exists

| Suite | Scope | Figure |
|---|---|---|
| `sw/tests/` | golden models, register-map and memory-map sync, synthesis guards, submission guards | **295 collected, 295 passed** on 2026-09-01 **[measured, `docs/00-index.md` section 6]** |
| `hw/soc/tb/cocotb/` | eleven modules of the SoC, including the NPU subsystem with the frozen die inside it | **131 test functions collected** across 11 modules **[measured, `grep -c '@cocotb.test'`, 2026-09-03] [in flux]** |
| `hw/soc/formal/` | eight property sets — register file, APB bridge, fabric, BUSSTAT, CLINT, NPU serial transport, watchdog, watchdog TMR | **33 SymbiYosys tasks collected** **[measured, the `[tasks]` sections] [in flux]** |
| `hw/soc/fi/` | seven fault-injection campaigns, section 9 | see section 9 |
| `hw/tb/`, `formal/` | the frozen die's own suites, untouched by this work | `docs/21` section 7.1 |

**Collection is not execution.** The two [in flux] rows are counts of
what is declared, made against a working tree that three editors are
changing; they are not a statement that anything passed today. The
Python row is an execution and says which date.

The end-to-end demonstration is one program: **215,428 cycles, 27 of 27
checks**, running from the boot ROM through the fabric, the CLINT, the
timers, the watchdog, the UART, BUSSTAT and the NPU node, and comparing
an inference against a golden answer that
`hw/soc/flow/gen_npu_vectors.py` computed at **build** time from
`sw/golden/lif_core.py` and compiled into the ROM image. **The program
never asks the hardware what the answer is.**

### 15.2 What the checkers do not cover

Stated because a green check read as wider than the thing it examined
is this repository's recurring defect, and it has been counted:
`docs/41` section 6.6 counts eight instances of it across the corpus
and `docs/45` section 8 counts fourteen under a wider reading. The four
that are defects in the place-and-route flow are configured out in
section 11.1's run and named there.

### 15.3 Reproducing

```
# Golden models, register-map and memory-map sync, synthesis guards
.venv/bin/python -m pytest sw/tests/ -q

# SoC block simulation, one module at a time
cd hw/soc/tb/cocotb && make -f Makefile.soc_npu     # and the other ten

# SoC formal
for f in hw/soc/formal/*.sby; do sby -f "$f"; done

# The management core's fault-injection campaign
hw/soc/fi/campaign.py --build hw/soc/out/fi-core --draws 100 --jobs 18

# The NPU connection's campaign
hw/soc/flow/fi_npu.sh          # refuses to run if hw/rtl/ is modified

# The die's own campaign
cd hw/tb && make -f Makefile.fi

# Synthesis and pre-layout STA of the whole SoC
hw/soc/flow/syn_soc_top.sh
hw/soc/flow/sta_soc_top.sh

# Place and route
hw/soc/flow/pnr_soc_top.sh     # refuses to run if its configuration
                               # directory is inside hw/openlane/
```

Area and flip-flop figures come from the run trees under
`hw/soc/out/` and `hw/soc/pnr/runs/`, both of which are gitignored, so
**the run tag and the metric key are the record rather than the path**.

### 15.4 The freeze this design is built around

`docs/34-pilot-freeze.md` pins the TTIHP26b submission by blob hash at
commit `b6738e5`; the shuttle closes **2026-09-21**. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` has been
modified by any of the SoC work, `hw/rtl/tmr_voter.v` is **read and
instantiated in place** by the watchdog rather than copied, and both
`hw/soc/flow/pnr_soc_top.sh` and `hw/soc/flow/fi_npu.sh` refuse to run
if that stops being true. **This document modifies nothing.**

---

## 16. Revision history

| Date | Revision | Changes |
|---|---|---|
| 2026-09-10 | **0.1d** | Section 9.10 added: the two SoC-wide denominators that bound the whole of section 9 — 1,003 to 1,051 of the placed design's 5,873 flip-flops are in a block no campaign has injected into (`soc_busstat` entire, and with it every counter the SoC's own upset telemetry reports through), and the flip-flop-only fault model leaves 96.68 % of the 176,663 placed instances and 90.35 % of the 60,868 standard cells outside the model. No campaign figure in section 9 changed; what changed is that the numerators now have a stated denominator. Section 9.9's *"`soc_top` has never been simulated as a netlist"* is corrected in place against `docs/74` and left standing. |
| 2026-09-05 | **0.1a** | Section 14: the seven disagreements are resolved in the documents that own them, each correction left visible in place, and recorded in `docs/64-document-reconciliation.md`. No figure in this datasheet changed; section 9 already followed the committed campaign log. |
| 2026-09-05 | **0.1c** | Sections 1 and 4.1: the "no QSPI" statements are corrected in place. `docs/66-qspi-flash-controller.md` builds the register-mode QSPI controller; the whole-SoC invariant is unchanged at 217,634 with the block present and the program as it was, and that document explains why the new checks are a second image. |
| 2026-09-05 | **0.1b** | Sections 1 and 4.1: the "no GPIO" statements are corrected in place. `docs/65-gpio-and-the-interface-ip-assessment.md` builds the GPIO port; the whole-SoC invariant this datasheet quotes at 215,428 cycles is 217,634 with that document's check 28 in the program, and unchanged with the block present and the program as it was. |
| 2026-09-03 | **0.1** | Initial release. Covers `soc_top` at commit `7721719`: the management core, the fabric, the memory subsystem, the CLINT, the GPTIMER and watchdog, BUSSTAT, the UART, the device tables and the NPU subsystem with the frozen pilot inside it. Physical and timing data are from the `full3` place-and-route run of `docs/47`, which does **not** contain the NPU subsystem. Power is `report_power` without activity annotation and is tagged [in flux]. No frequency figure is published. No DRC, LVS or XOR result exists. |

---

## 17. References

| Document | What it holds |
|---|---|
| `regmap/memmap.yaml` | The memory map, the peripheral slots and both interrupt namespaces — single source of truth |
| `regmap/regmap.yaml` | The NPU node register map — single source of truth |
| `docs/memmap-soc.md`, `docs/regmap-npu.md` | Their generated forms |
| `docs/05-market-positioning.md` section 4 | The five binding positioning rules, including rule 5 |
| `docs/08-gr801-datasheet-notes.md` | The GRLIB conventions this map and these register blocks mirror |
| `docs/10-npu-mvp-spec.md` | The normative neuron model and the frozen node register list |
| `docs/12-sg13g2-flow-bringup.md` sections 7 and 8 | The RM_IHPSG13 evaluation and the NO-GO |
| `docs/16-fault-injection-campaign.md` | The die's fault-injection campaign and its bounds |
| `docs/21-pilot-datasheet.md` | The frozen die's own datasheet, including its programmer's model |
| `docs/34-pilot-freeze.md` | What is frozen, by hash, and until when |
| `docs/38-ibex-bringup.md` | The core, its configuration, its five bring-up defects and the `SecureIbex` decision |
| `docs/39-soc-bus-and-memory-map.md` | The fabric, why it is not AHB, and the map freeze |
| `docs/40-interrupts-timers-watchdog.md` | The CLINT, the GPTIMER, the watchdog and the PLIC decision |
| `docs/41-watchdog-hardening.md` | The watchdog's TMR, measured through synthesis |
| `docs/42-core-fault-injection.md`, `docs/43-core-hardening.md` | The core measured, then hardened and re-measured |
| `docs/44-margin-and-observability.md` | The instrument's noise floor, and BUSSTAT |
| `docs/45-soc-top-synthesis.md` | The whole SoC synthesised, with the per-block area breakdown |
| `docs/46-watchdog-window-decision.md` | Why the windowed kick mode is recommended for removal |
| `docs/47-soc-place-and-route.md` | The layout, the timing, and what it does not cover |
| `docs/48-floorplan-and-capacitance.md` | Three floorplans, and the max-capacitance finding |
| `docs/49-synpre-and-the-binding-path.md` | The binding path, decomposed |
| `docs/50-memory-read-register.md` | The change that improved the sign-off and made the part slower |
| `docs/51-npu-integration.md` | The connection decision, the transport, and the measured area |
| `docs/52`, `docs/55`, `docs/56` | The NPU connection measured, hardened, and its event engine split and hardened |
| `docs/53-workload-and-the-clock.md` | The workload sized, the power figure found, and the refusal to publish a frequency |
| `docs/54-klayout-deck-and-the-macro.md` | The 2,316 examined, and the second exit closed |
| `hw/soc/rtl/`, `hw/rtl/` | Behaviour, single source of truth |
| `sw/golden/` | The bit-exact executable specification |






