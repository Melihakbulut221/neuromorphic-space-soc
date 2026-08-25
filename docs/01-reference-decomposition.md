# GR801 architecture decomposition and 28 nm to 130 nm scaling analysis

Status: research phase, document 01. Builds on `docs/00-reference-brief.md`.

Convention used throughout: statements labeled **[fact]** come from a cited
public source; statements labeled **[estimate]** are derived numbers with the
derivation shown. Where a range is given, both endpoints of the assumption
are stated.

## 1. Sources

- GR801 product page, Frontgrade Gaisler (product brief, "Development"
  status): https://www.gaisler.com/products/gr801
- GRAIN line launch and SNSA commercialization contract (April 2025):
  https://www.gaisler.com/news-events/frontgrade-gaisler-launches-new-grain-line-and-wins-snsa-contract-to-commercialize-first-energy-efficient-neuromorphic-ai-for-space-applications
- BrainChip / Frontgrade Gaisler partnership announcement:
  https://www.gaisler.com/news-events/brainchip-and-frontgrade-gaisler-to-augment-space-grade-microprocessors-with-ai-capabilities
- Akida 1.0 (AKD1000) architecture analysis (Putra et al., arXiv:2504.00957):
  https://arxiv.org/pdf/2504.00957
- Akida MetaTF hardware user guide (layer types, quantization, mapping,
  multi-pass): https://doc.brainchipinc.com/user_guide/akida.html
- Akida hardware overview, Open Neuromorphic:
  https://open-neuromorphic.org/neuromorphic-computing/hardware/akida-brainchip/
- BrainChip on 4-bit weight sufficiency:
  https://brainchip.com/blog/4-bits-are-enough/
- NOEL-V product page: https://www.gaisler.com/products/noel-v
- AKD1000 PCIe board coverage (process, clock, power class):
  https://www.cnx-software.com/2022/01/21/brainchip-akd1000-pcie-board-ai-inference-and-training-at-the-edge/
- Open-PDK memory generator densities (ORRAM paper, includes DFFRAM and
  OpenRAM comparisons on SkyWater 130 nm): https://arxiv.org/html/2607.12244
- Pre-hardened OpenRAM macros for sky130 (1/2/4 kB blocks):
  https://armleo-openlane.readthedocs.io/en/merge-window-4/tutorials/openram.html

## 2. GR801 decomposition

### 2.1 System overview [fact]

GR801 is the first device of Frontgrade Gaisler's GRAIN line: a
radiation-hardened SoC for AI inference in space, combining a NOEL-V RISC-V
management processor with BrainChip's Akida 1.0 neuromorphic engine on
STMicroelectronics 28 nm FDSOI, funded in part by a Swedish National Space
Agency commercialization contract announced April 2025
(https://www.gaisler.com/news-events/frontgrade-gaisler-launches-new-grain-line-and-wins-snsa-contract-to-commercialize-first-energy-efficient-neuromorphic-ai-for-space-applications).
The product brief lists the device as under development with no availability
guarantee (https://www.gaisler.com/products/gr801).

### 2.2 Akida 1.0 neuromorphic engine

Facts from the GR801 brief (https://www.gaisler.com/products/gr801):

- Eight neural processing nodes connected in a mesh network.
- Each node contains four convolutional or fully connected engines.
- Each node supports 128 4x4 MACs, for a total of 1024 MACs per clock.
- Hardware support for 1-, 2-, or 4-bit hybrid quantized weights.
- Multi-pass processing enables execution of networks larger than the
  physical fabric.
- 3.2 MB RAM private to the Akida unit.
- Event-based computing to minimize power consumption.

Additional context from the commercial Akida 1.0 silicon (AKD1000), useful
for understanding the node internals even though GR801 instantiates a
smaller configuration [fact, different chip]:

- AKD1000 contains 80 NPUs grouped 4 per node (20 nodes); each NPU holds
  8 neural processing engines and 100 KB of local SRAM split as 40 KB
  weight and 60 KB event/spike buffer (https://arxiv.org/pdf/2504.00957).
  Total NPU-local SRAM is therefore 8 MB on AKD1000.
- AKD1000 is fabricated in TSMC 28 nm and clocks at 300 MHz
  (https://arxiv.org/pdf/2504.00957,
  https://www.cnx-software.com/2022/01/21/brainchip-akd1000-pcie-board-ai-inference-and-training-at-the-edge/).
- Supported layer types in Akida 1.0: InputData, InputConvolutional,
  Convolutional, SeparableConvolutional, FullyConnected; inputs and weights
  are integer-only, and multi-pass mapping is exposed in the toolchain as
  partial reconfiguration of the NP fabric
  (https://doc.brainchipinc.com/user_guide/akida.html).
- 4-bit weights and activations are the recommended operating point, with
  8-bit first layers (https://brainchip.com/blog/4-bits-are-enough/).

Interpretation [estimate]: the GR801 Akida instance (8 nodes, 1024 MACs,
3.2 MB private RAM) is roughly a 40 percent slice of AKD1000's fabric
(20 nodes, 8 MB NPU SRAM), i.e. Gaisler already scaled Akida down for the
space part. The architectural essentials that survive any scaling are:
(a) event-driven activation with sparsity exploitation, (b) low-bit
quantized weights, (c) per-node local SRAM adjacent to the MACs,
(d) a mesh/interconnect between nodes, (e) multi-pass execution to decouple
model size from fabric size. These five properties, not the instance size,
define the architecture class this project reproduces.

### 2.3 NOEL-V management processor [fact]

NOEL-V is Gaisler's RV64GC, dual-issue-capable, fault-tolerant (ECC on
caches and register files) processor written in VHDL, distributed in GRLIB
(https://www.gaisler.com/products/noel-v). In GR801 it is a single core
used for system management and configuration of the neuromorphic engine
(https://www.gaisler.com/products/gr801). Clock frequency for GR801 is not
disclosed.

### 2.4 Memory subsystem [fact]

- 8 MB on-chip RAM (system side) plus 3.2 MB Akida-private RAM: 11.2 MB
  total on-chip SRAM.
- QSPI external memory controller with 2 chip selects.
- NOEL-V, on-chip memory and all buffers protected with error correction;
  Akida memories have fault detection with flexible fault handling.

Source: https://www.gaisler.com/products/gr801.

### 2.5 Interfaces [fact]

PCIe Gen 3 x4 (root/endpoint), 10/100/1000 Ethernet (GMII), 8-bit camera
parallel interface (CPI), SpaceWire router with 4 external ports at
200 Mbps, 2x CAN FD, 1x SPI (2 CS), 2x I2C, 3x UART, 16x GPIO
(https://www.gaisler.com/products/gr801).

### 2.6 Hardening and platform [fact]

STM 28 nm FDSOI (platform-level radiation resilience is part of the
positioning), ECC on processor and memories, fault detection on Akida
memories, ESCC9030 screening path for the flight model, TID 50 krad(Si)
guaranteed by platform with 100 krad(Si) testing planned, package
23x23 mm 441-ball BGA (https://www.gaisler.com/products/gr801,
https://www.gaisler.com/news-events/frontgrade-gaisler-launches-new-grain-line-and-wins-snsa-contract-to-commercialize-first-energy-efficient-neuromorphic-ai-for-space-applications).

## 3. Quantitative scaling: 28 nm FDSOI to 130 nm bulk

**Re-baseline note (2026-08-25) — all 130 nm densities in this document
are SKY130-derived.** Every 130 nm figure in this section, and every
budget derived from it in Section 3.4, Section 4 and the conclusion,
comes from SkyWater sky130 sources (sky130_fd_sc_hd standard cells,
OpenRAM sky130 macros), even where the text reads generically as "an
open 130 nm PDK". `docs/04-technology-and-flow.md` has since selected
**IHP SG13G2 as the primary PDK** with SKY130 as the fallback, and the
SG13G2 numbers differ materially in both directions. Comparison for the
25 mm2 case, sourced from `docs/04-technology-and-flow.md` and
`docs/06-funding-and-shuttle.md` appendix B.3:

| 25 mm2 case | IHP SG13G2 (primary) | SKY130 (fallback; basis of this document) |
|---|---|---|
| Logic density | ~138 kGE/mm2 raw, measured from the PDK (docs/06 B.3) — about 2x less dense than SKY130 HD; the 150-250 kGE management-core budget needs ~1.5-3.0 mm2 placed at 60-70% utilization [estimate] | ~260-270 kGE/mm2 raw (Section 3.1); 0.8-1.7 mm2 placed, budgeted 1.5-2.5 mm2 (Section 3.4) [estimate] |
| SRAM density | ~25-40 KiB/mm2 incl. periphery, `RM_IHPSG13_1P_*` foundry macros (docs/04 section 3.1) [estimate, band assumed until measured] | ~57 kbit/mm2, i.e. ~7 KiB/mm2, OpenRAM 2 kB macro (Section 3.2) [estimate] |
| Resulting SRAM budget | 256-512 KiB with roughly a third of the die in SRAM (docs/04 section 3.2) — 2-4x this document's open-PDK figure [estimate] | ~115 KB at ~16 mm2 SRAM area (Section 3.4) [estimate] |

The SG13G2 SRAM column is an assumed band, not a measurement: docs/04
open question 2 (extract real `RM_IHPSG13_1P_*` density/timing from the
open PDK LEF/liberty and re-baseline the SRAM budget table) is the
pending authority for it. Until that re-baseline lands, no area or SRAM
number from this document should be quoted without naming its PDK.

### 3.1 Logic density [estimate]

- 130 nm open-PDK reference (SkyWater sky130, high-density library): the
  hd standard-cell site gives a NAND2-equivalent area of roughly
  3.7-3.8 um2, i.e. about 260-270 kGE/mm2 raw, or roughly
  **150-190 kGE/mm2 placed** at 60-70 percent utilization.
- 28 nm planar processes are commonly quoted at roughly 3-4 MGE/mm2 raw.
- **Logic density ratio: roughly 12-15x raw-to-raw** (3.0-4.0 MGE/mm2
  against 260-270 kGE/mm2) in favor of 28 nm; utilization derating
  applies to both nodes and leaves the ratio essentially unchanged. Ideal
  geometric scaling (130/28)^2 would be ~21.6x; the shortfall reflects
  the relatively conservative sky130 hd cell library, not the node.

These are derived numbers, not vendor-published densities for the specific
ST 28 nm FDSOI process, which is not public at that level of detail.

### 3.2 SRAM density: the dominant constraint

Bitcell facts and estimates:

- 28 nm 6T bitcells are approximately **0.127 um2** (published foundry
  class figure for 28 nm-generation 6T cells) [fact, generation-level].
- 130 nm 6T bitcells are approximately **2.5 um2** [fact,
  generation-level].
- **Bitcell ratio: ~20x** (2.5 / 0.127 = 19.7) [estimate from the above].

Macro-level reality at 130 nm with open PDKs is much worse than the bitcell
ratio suggests, because open-source memory compilers do not achieve
foundry-compiler array efficiency:

- OpenRAM-generated sky130 macro density is macro-size dependent: the
  published 1 kB macro (sky130_sram_1kbyte_1rw1r_32x256_8, 479.78 x
  397.5 um) computes to ~43 kbit/mm2 (23.3 um2/bit), while the 2 kB macro
  (sky130_sram_2kbyte_1rw1r_32x512_8, 683.1 x 416.54 um) reaches
  ~57.6 kbit/mm2 (17.4 um2/bit)
  (https://github.com/VLSIDA/sky130_sram_macros) — about **7-9x worse
  than the raw 130 nm bitcell** would allow with a good compiler
  [estimate from published macro dimensions]. The tables below use
  57 kbit/mm2, i.e. they assume the larger macro; open-PDK SRAM budgets
  shrink roughly 25 percent if only the 1 kB macro proves usable.
- Standard-cell-based alternatives are worse still: DFFRAM achieves about
  14-15 kbit/mm2 and the ORRAM generator about 28 kbit/mm2 on sky130
  (https://arxiv.org/html/2607.12244) [fact].
- A foundry-quality 130 nm SRAM compiler (commercial access, NDA) at
  ~70 percent array efficiency would give roughly **270-280 kbit/mm2**
  (3.6 um2/bit) [estimate].

Consequence for GR801's 11.2 MB (94 Mbit) of on-chip SRAM [estimate]:

| Technology / compiler | Density | Area for 11.2 MB |
|---|---|---|
| 28 nm foundry macro (~0.2-0.25 um2/bit) | ~4-5 Mbit/mm2 | ~19-24 mm2 |
| 130 nm foundry compiler (~3.6 um2/bit) | ~0.28 Mbit/mm2 | ~340 mm2 |
| 130 nm open PDK, OpenRAM (~17.5 um2/bit) | ~57 kbit/mm2 | ~1,650 mm2 |

The memory alone makes a 1:1 retarget absurd; the effective memory-density
gap between GR801's platform and an open-PDK 130 nm flow is **70-90x**, not
20x. Memory, not logic, sets the scaling factor for this project.

### 3.3 Clock frequency [estimate]

- Gate-delay scaling (FO4-based) from 28 nm FDSOI to 130 nm bulk is
  roughly 4-6x.
- AKD1000 runs at 300 MHz in TSMC 28 nm [fact,
  https://arxiv.org/pdf/2504.00957]; the equivalent pipeline retargeted to
  130 nm would land near 50-75 MHz.
- Open-flow (OpenROAD/OpenLane) sky130 tapeouts routinely close timing in
  the 25-50 MHz range; 100 MHz is achievable for short, well-pipelined
  paths but should not be the baseline.
- **Realistic envelope: 50 MHz system clock target, 100 MHz stretch goal
  for the neural fabric datapath only.** Event-based operation means
  throughput degrades more gracefully with clock than a dense MAC array
  would, since work scales with event counts, not frames.

### 3.4 What fits at 10 / 25 / 50 mm2 [estimate]

Assumptions: 15 percent of the die for pad ring, power and clock
infrastructure; RV32 management core plus bus and peripherals at
150-250 kGE — about 0.8-1.7 mm2 at the placed density of Section 3.1,
budgeted here at 1.5-2.5 mm2 to cover routing congestion, ECC/TMR
overhead and clock/reset distribution; neural fabric control and MACs
sized to match the memory that feeds them; remainder to SRAM. Two SRAM
scenarios: open-PDK OpenRAM (57 kbit/mm2) and foundry-compiler access
(280 kbit/mm2).

| Die | SRAM area budget | Total SRAM (open PDK) | Total SRAM (foundry compiler) | Fraction of GR801's 11.2 MB |
|---|---|---|---|---|
| 10 mm2 | ~5 mm2 | ~36 KB | ~175 KB | 0.3% / 1.5% |
| 25 mm2 | ~16 mm2 | ~115 KB | ~560 KB | 1.0% / 4.9% |
| 50 mm2 | ~35 mm2 | ~250 KB | ~1.2 MB | 2.2% / 10.7% |

Compute side, same dies: a 4-bit event-driven MAC plus its share of node
control is small relative to memory; 64-128 physical MACs cost well under
2 mm2 of logic at 130 nm. At 50-100 MHz that is 3-13 GMAC/s peak versus
GR801's 1024 MACs per clock (0.3-0.5 TMAC/s class at an assumed
300-500 MHz), i.e. **roughly 1-4 percent of GR801's peak compute** — which
is consistent with the 1-5 percent memory fraction. The scaled design is a
proportionally shrunk instance of the same architecture, not a crippled
one: multi-pass execution (Section 2.2) is exactly the mechanism that lets
a small fabric run networks sized for a larger one, at the cost of latency
and QSPI bandwidth.

Conclusion [estimate]: a 25 mm2-class die on an open 130 nm PDK supports
about 100-128 KB of SRAM, a 64-128 MAC event-driven fabric, an RV32
management core and the low-speed interface set. That is the honest
envelope; 10 mm2 forces the SRAM below 64 KB (open PDK) and starts
compromising the architecture, while 50 mm2 buys margin but raises cost
and yield risk for a first spin. These are SKY130 figures despite the
generic "open 130 nm PDK" wording: on the SG13G2 primary PDK the SRAM
budget rises 2-4x and the logic area roughly doubles — see the
re-baseline note at the head of Section 3.

## 4. Recommended scaled architecture envelope

**Supersession note (2026-08-25).** The 4-node fabric recommended below
was superseded by `docs/02-npu-architecture.md` section 4, which
selected Candidate B: a single 512-neuron time-multiplexed core whose
AER event interface and configuration map are frozen as if it were one
node of a mesh, with the multi-node mesh (Candidate C) deferred to a
later phase. Recorded reasons: lower verification burden than four
interacting nodes plus a NoC, the SRAM budget concentrated in one ECC
macro group instead of distributed across four nodes, and scale-out
preserved as a later instantiation through the frozen AER interface
rather than a redesign. The text below is retained unmodified as the
original decision record; the re-baseline note at the head of Section 3
applies to its numbers as well.

Target: 25 mm2 class, sky130-class open PDK, open RTL-to-GDS flow.

- **Neural fabric**: 4 neural processing nodes, each with one engine of
  16 MACs (4x4, matching the GR801 node's MAC granularity) and 16-24 KB
  local SRAM (weights + event buffer, ECC or parity per bank), connected
  by a lightweight packet interconnect (ring or 2x2 mesh — decision in
  `docs/02-npu-architecture.md`). Total: 64 MACs/clock, 64-96 KB fabric
  SRAM. 1/2/4-bit weight support; 4-bit as the primary operating point,
  8-bit first layer handled by multi-pass or in software.
- **Multi-pass** is mandatory, not optional: of the 64-96 KB fabric SRAM,
  only the weight share is resident model storage — the AKD1000 node
  splits its local SRAM roughly 40/60 between weights and event buffers
  (Section 2.2), which puts resident weights near **30-60 KB**. Models
  beyond roughly **60-120k parameters at 4 bits** must stream weight
  slices from QSPI. QSPI bandwidth therefore bounds large-model latency
  and must be modeled early.
- **Management CPU**: RV32IMC-class core in Verilog (candidate survey in
  `docs/03-cpu-and-ip-survey.md`), TMR or lockstep on the control path,
  16-32 KB ECC instruction/data memory drawn from the shared budget.
- **System SRAM**: 32-64 KB shared, ECC with hardware scrubbing.
- **Clocking**: 50 MHz system target, 100 MHz stretch for the fabric.
- **Interfaces**: SpaceWire codec with 1-2 links at up to 100 Mbps, 1x CAN
  (FD if an adequately verified open core is available), 1x SPI, 1x I2C,
  2x UART, 16x GPIO, optional 8-bit CPI front end feeding an
  event-conversion stage.
- **Hardening**: architecture-level only (bulk 130 nm gives no FDSOI-style
  SEL immunity): TMR on FSMs and CSRs, ECC + scrub on all SRAM, fault
  counters and error reporting registers, watchdog. Positioning is
  "fault-tolerant by design", never "radiation-hardened by platform".

## 5. GR801 block mapping: keep / shrink / drop

| GR801 block | Decision | Justification |
|---|---|---|
| Event-based processing model | Keep | Node-independent architectural idea; the power argument is strongest at low clock rates |
| 1/2/4-bit quantized weights | Keep | Multiplies effective SRAM capacity 2-8x; the single most valuable idea at 130 nm |
| Multi-pass execution | Keep | Decouples model size from fabric size; essential when fabric SRAM is ~1% of GR801's |
| 8 nodes x 4 engines, 1024 MACs | Shrink | 4 nodes x 1 engine, 64 MACs; matches the 1-5% memory fraction that fits — superseded, see the errata note below this table |
| Mesh interconnect | Shrink | Full mesh is overkill for 4 nodes; ring or 2x2 grid with same packet semantics |
| 3.2 MB Akida-private RAM | Shrink | 64-96 KB distributed per-node; open-PDK SRAM density forces this |
| 8 MB system RAM | Shrink | 32-64 KB shared ECC SRAM plus QSPI-resident model storage |
| NOEL-V RV64GC FT single core | Shrink | RV32IMC management core; RV64GC is oversized for a config/management role and VHDL breaks the fault-injection flow |
| QSPI controller, 2 CS | Keep | Cheap, essential for multi-pass weight streaming and boot |
| SpaceWire router, 4x 200 Mbps | Shrink | Codec with 1-2 links at 100 Mbps; a router is a product in itself |
| 2x CAN FD | Shrink | 1x CAN; covers CubeSat bus use cases at low area |
| SPI / I2C / UART / GPIO | Keep | Trivial area, required for any spacecraft integration |
| CPI (8-bit camera input) | Keep | Simple parallel capture; the natural sensor input for the inference use case |
| PCIe Gen 3 x4 | Drop | SerDes/PHY not feasible at 130 nm with open IP and open flows |
| Gigabit Ethernet (GMII) | Drop | Same PHY problem; no CubeSat-class requirement justifies it |
| ECC on CPU and memories | Keep | Carries the entire hardening story on bulk silicon; extend with scrubbing |
| Akida memory fault detection | Keep | Fault counters and flexible fault handling map directly to the scaled fabric |
| FDSOI platform radiation immunity | Drop | Not transferable to bulk 130 nm; replaced by architecture-level mitigation and honest positioning |
| ESCC9030 flight screening, 441-ball BGA | Drop | Out of scope for an open-flow project; modest package, test-chip qualification path instead |

**Errata (2026-08-25).** The "4 nodes x 1 engine, 64 MACs" target in the
row above was superseded by `docs/02-npu-architecture.md` section 4,
which selected a single 512-neuron time-multiplexed core (Candidate B)
and deferred the multi-node mesh to a later phase. Reasons recorded
there: verification burden of four interacting nodes plus a NoC, SRAM
budget concentration in one ECC macro group rather than four distributed
ones, and the AER interface frozen mesh-ready so later scale-out is an
instantiation, not a redesign. The row is kept as originally issued for
decision-record integrity; see also the supersession note at the head of
Section 4.

## 6. Open questions for the roadmap

1. Fabric microarchitecture: ring vs 2x2 mesh, event/packet format, and
   whether engines are convolution-capable or fully-connected-first
   (drives `docs/02-npu-architecture.md`).
2. SRAM strategy: OpenRAM macros vs DFFRAM-class fabric RAM vs pursuing
   commercial 130 nm compiler access; this single choice swings total SRAM
   by ~5x at fixed die size (drives `docs/04-technology-and-flow.md`).
3. PDK selection — resolved by `docs/04-technology-and-flow.md`: primary
   IHP SG13G2 (foundry `RM_IHPSG13_1P_*` SRAM macros in the open PDK),
   fallback SkyWater sky130; gf180mcu was evaluated there and excluded on
   node grounds (180 nm). The sky130-vs-gf180mcu framing originally posed
   here is obsolete. What remains open is the quantitative re-baseline of
   this document's budgets on SG13G2 (docs/04 open question 2, the
   RM_IHPSG13 LEF/liberty density extraction; see the re-baseline note at
   the head of Section 3).
4. Management core selection: which RV32 core (Verilog, verifiable,
   fault-injection-observable), and TMR vs lockstep for its control path
   (drives `docs/03-cpu-and-ip-survey.md`).
5. QSPI bandwidth vs multi-pass latency: build the analytical model
   (weights streamed per pass x passes per inference / QSPI throughput at
   50 MHz) and validate against one reference network.
6. Achievable clock: run trial synthesis and P&R of a representative
   node datapath through the open flow to replace the 50/100 MHz estimate
   with data.
7. ECC granularity: word-level SECDED vs per-bank parity plus retry in the
   fabric SRAMs — area cost vs the fault-handling semantics inherited from
   the Akida fault-detection model.
8. Reference workload: pick 1-2 benchmark networks (e.g. keyword spotting,
   small visual classification) in the ~60-120k 4-bit parameter class
   (the single-pass envelope derived in Section 4), plus one deliberately
   oversized network to exercise multi-pass, to size the node SRAM split
   (weights vs events) with real numbers.
9. SpaceWire IP: identify an open or licensable codec whose verification
   status is compatible with the project's fault-injection methodology.
10. Radiation validation path: what claims can honestly be made from
    fault-injection campaigns alone, and what would a minimal beam test of
    a test structure add (ties into positioning in
    `docs/05-market-positioning.md`).
