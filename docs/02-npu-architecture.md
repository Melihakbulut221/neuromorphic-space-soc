# Event-driven inference engine: architecture options and recommendation

Scope: this report surveys open-source and published event-driven SNN
accelerator designs, extracts what is publicly known about the Akida 1.0
architecture referenced by the GR801 brief, and proposes candidate
architectures for the clean-room event-driven fabric of this project on a
130 nm open-PDK flow. It ends with a recommendation, fallback conditions,
and open questions.

Conventions:

- **Fact** — taken from a cited public source or from this project's own
  verified prior work.
- **Estimate** — derived here (scaling arithmetic, area/FF budgets,
  workload fit). All tables of budgets in section 4 are estimates unless a
  cell cites a source.

Constraint carried over from `00-reference-brief.md`: the fault-injection
observability flow used in prior projects is Verilog-based; VHDL cores
break it. Every candidate below is required to be synthesizable Verilog
(Verilog-2005 subset acceptable to Icarus Verilog and Verilator).

---

## 1. Survey of existing designs

### 1.1 Akida 1.0 — the reference IP (proprietary, not reusable)

Facts from public sources:

- GR801 integrates Akida 1.0 as "eight neural processing nodes connected
  in a mesh network," each node containing "four convolutional or fully
  connected engines," with hardware support for 1/2/4-bit hybrid quantized
  weights, multi-pass processing for large networks, and 3.2 MB of RAM
  private to the Akida unit
  (https://www.gaisler.com/products/gr801, summarized in
  `docs/00-reference-brief.md`).
- The commercial AKD1000 chip is described as 80 NPUs organized in nodes
  of four, mesh-networked, with event-based processing that only computes
  on non-zero activations and direct node-to-node communication without
  CPU involvement
  (https://brainchip.com/technology/,
  https://www.embedded.com/brainchips-akida-npu-redefining-ai-processing-with-event-based-architecture/).
- AKD1000 carries 8 MB of SRAM for weights/activations; weights and
  activations of 1/2/4 bits (8-bit added in Akida 2.0); input encoded with
  pixel-to-event conversion and rank-order coding rather than classical
  LIF dynamics; on-chip continual learning restricted to a final
  fully-connected layer with binary weights; reported power in the tens of
  milliwatts (~30 mW figure reported)
  (https://open-neuromorphic.org/neuromorphic-computing/hardware/akida-brainchip/).
- Akida 1.0 layer support is restricted: only certain layer sequences are
  legal (e.g., Conv2D cannot feed Dense without Flatten), so the software
  stack (MetaTF) compiles a constrained network family, not arbitrary
  graphs (same source).
- Frontgrade Gaisler licensed Akida IP in December 2024 for space SoCs
  (https://www.businesswire.com/news/home/20241215304799/en/Frontgrade-Gaisler-Licenses-BrainChips-Akida-IP-to-Deploy-AI-Chips-into-Space);
  AKD1000 silicon has flown in LEO inside the ANT61 "Brain" computer on
  Optimus-1
  (https://www.hackster.io/news/brainchip-s-neuromorphic-akida-goes-orbital-as-optimus-1-takes-the-ant61-brain-computer-into-space-920ed9ba76cb).

Estimate (cross-check worth recording): AKD1000 has 8 MB across 80 NPUs,
i.e. ~100 KB per NPU; the GR801 configuration has 3.2 MB across 8 nodes x
4 engines = 32 engines, again ~100 KB per engine. The "engine plus ~100 KB
local SRAM" granularity is therefore a consistent, public-figure-derived
design point for an Akida-class node, and a useful sanity anchor when
sizing a clean-room node.

Reported workload result: a spiking DS-CNN on Akida reaches 91.73% on a
Google Speech Commands keyword-spotting task
(https://arxiv.org/pdf/2504.00957).

### 1.2 Open-source SNN cores (RTL available)

**ODIN** (UCLouvain, C. Frenkel). Single 256-neuron, 64k-synapse crossbar
neurosynaptic core, time-multiplexed; SDSP online learning in the
synapses; neurons configurable as LIF or 20-behavior Izhikevich. Silicon:
28 nm FDSOI, 0.086 mm² core, 12.7 pJ/SOP. Source is plain Verilog
(`neuron_core.v`, `synaptic_core.v`, `scheduler.v`, AER output, SPI
config), Solderpad v2.0 license, with documentation
(https://github.com/ChFrenkel/ODIN, https://arxiv.org/abs/1804.07858).
Facts. Key structural point: synapse weights live in a 64k x 4-bit SRAM
and neuron state in a small SRAM, with one physical update pipeline
time-multiplexed over all neurons — the architecture is
"SRAM plus a small datapath," not a physical crossbar.

**tinyODIN** (same author lineage; UCLouvain/UZH/KU Leuven/TU Delft
copyright). ODIN stripped of online learning and Izhikevich support: 256
twelve-bit LIF neurons, 64k 4-bit synapses in a crossbar-addressed SRAM,
AER out, SPI config. Verilog RTL plus SystemVerilog testbench, Solderpad
v2.1 (https://github.com/ChFrenkel/tinyODIN). Fact. This is the closest
existing open design to what this project needs for a first-pass engine:
inference-only, low-bit weights, event-driven, small, and in Verilog.

**ReckOn** (UCLouvain). Spiking recurrent neural network processor with
on-chip learning (modified e-prop) over second-long timescales; 28 nm
FDSOI, 0.45 mm² core, 5.3 pJ/SOP at 0.5 V; Verilog RTL with SV testbench,
Solderpad v2.1 (https://github.com/ChFrenkel/ReckOn). Fact. Relevant
because temporal workloads (keyword spotting, telemetry time series) map
naturally to recurrent spiking topologies; the cost is a more complex
state and training story.

**SNE** (ETH Zurich, PULP platform). "Sparse Neural Engine": a digital
energy-proportional accelerator for sparse event-based convolutions,
4-bit quantized eCNN, ~4.5 TOP/s/W reported, integrated in the Kraken
RISC-V SoC; RTL open at https://github.com/pulp-platform/sne
(https://arxiv.org/pdf/2204.10687). Fact. Relevant as the only open RTL
reference for *event-based convolution* (the Akida differentiator vs
plain fully-connected SNN cores). Caveat: PULP-style SystemVerilog with
Bender dependency management — usable with Verilator, likely painful with
Icarus; treat as an architectural reference, not a drop-in.

**RANC** (University of Arizona). Open ecosystem (C++ simulation + FPGA
emulation) behaviorally compatible with IBM TrueNorth's
core/crossbar/router architecture; scales to 259k neurons in emulation
(https://github.com/UA-RCL/RANC, https://arxiv.org/abs/2011.00624). Fact.
Useful as a mesh-of-cores architectural reference and as an independent
software simulator concept, though its RTL targets FPGA emulation rather
than ASIC hardening.

### 1.3 Large research architectures (lessons, not candidates)

- **Loihi** (Intel): 128 cores, up to 1024 digital spiking neurons per
  core, 33 MB SRAM, 14 nm, 60 mm²
  (https://open-neuromorphic.org/neuromorphic-computing/hardware/loihi-intel/).
  Lesson: even at 14 nm, neuromorphic scale is SRAM-dominated; the
  per-core structure is again "neuron/synapse SRAM + shared update
  logic + NoC."
- **TrueNorth** (IBM): cores time-multiplex one physical circuit over 256
  neurons — confirmation that time-multiplexing is the standard digital
  pattern (https://arxiv.org/pdf/1901.03690).
- **SpiNNaker / SpiNNaker2** (Manchester/Dresden): neurons in software on
  many small ARM cores (SpiNNaker2: 152 Cortex-M4F)
  (https://arxiv.org/pdf/1901.03690). Lesson: a software-neuron approach
  buys flexibility but pays in power and determinism; for this project it
  would also move all "SNN correctness" into firmware, which weakens the
  silicon-level differentiation and the fault-injection story. Not
  pursued.

### 1.4 Published SNN silicon at older / open nodes

- 180 nm mixed-signal SNN chip: 3.6 mm² core, 94.66% MNIST, ~1.06 mW
  average (https://pmc.ncbi.nlm.nih.gov/articles/PMC8272117/). Fact, but
  mixed-signal — not reproducible in a standard-cell open flow; cited only
  to bound what the node can do.
- 130 nm SNN character-recognition ASIC: ~1 mm x 1 mm, 16.7 mW
  (https://www.researchgate.net/publication/271425442_Spiking_neural_network_based_ASIC_for_character_recognition).
  Fact (older, thin publication) — order-of-magnitude anchor for digital
  SNN at exactly this node class.
- SKY130A open-PDK SNN accelerator (OpenLane flow): 3.7 uJ/inference at
  89 MHz (https://ceur-ws.org/Vol-3960/short6.pdf). Fact — direct evidence
  that a digital SNN inference engine closes timing and produces usable
  energy numbers in a 130 nm open PDK with the same tool family this
  project uses.
- Tiny Tapeout scale: a programmable recurrent SNN
  (https://arxiv.org/abs/2405.01419) and a stochastic LIF neuron
  (https://arxiv.org/pdf/2606.23532) have been taped out on SkyWater
  130 nm via open flows. Facts.
- In-house: **tt-um-lif-crossbar**, this developer's Tiny Tapeout chip —
  an 8x8 LIF-neuron crossbar on a 2x2 tile, with ~70.7% classification
  accuracy verified pre-tapeout through the open flow. Fact (project's own
  verified result). This is the direct ancestor of Candidate A and the
  source of the verified Verilog LIF neuron and crossbar update logic.
- Context: the developer's GOLDFINCH-1 accelerator project formally
  evaluated and rejected an SNN engine *for that product* because its
  small-MLP workloads favored a weight-stationary INT8 systolic array.
  That decision does not transfer here: the GR801 reference product is
  neuromorphic by definition, the workloads include temporal/event data,
  and event-driven sparsity is the power story. The two projects are
  deliberately different bets.

### 1.5 What CubeSat payloads actually need

- **Telemetry anomaly detection** is the most defensible on-board AI
  workload for small satellites: ESA's OPS-SAT CubeSat produced a public
  anomaly-detection benchmark (OPSSAT-AD) with 30 baseline ML methods,
  and the community now treats the older NASA SMAP/MSL sets as flawed
  (https://www.nature.com/articles/s41597-025-05035-3,
  https://arxiv.org/abs/2407.04730). Input dimensionality is small (tens
  of channels), models are small, and latency requirements are mild —
  this fits a fully-connected/recurrent SNN engine with kilobyte-class
  weights. Fact (benchmark), estimate (fit).
- **Event-based vision in space** is real but early: Falcon Neuro flew two
  DAVIS240C event sensors on the ISS for lightning/sprite detection
  (https://www.frontiersin.org/journals/remote-sensing/articles/10.3389/frsen.2024.1436898/full),
  event-sensor LEO lifetime has been studied
  (https://doi.org/10.3390/s25216599), and a 2026 survey maps the
  application space (star tracking, debris, Earth observation)
  (https://arxiv.org/html/2606.01280). Facts. An event camera front-end is
  the workload that genuinely requires event-based *convolution* and mesh
  scale; without it, a fully-connected engine covers the mission set.
- **Keyword spotting** (Google Speech Commands class) is not itself a
  spacecraft workload, but it is the standard public benchmark for
  low-power temporal SNN inference (Akida's own demos use it, 91.73%
  cited above) and doubles as a proxy for 1-D RF/telemetry temporal
  classification. Keeping GSC-subset KWS as an acceptance benchmark makes
  results comparable with the literature. Estimate/judgment.
- General context on neuromorphic computing for space missions:
  https://arxiv.org/pdf/2212.05236.

---

## 2. Design constraints for the 130 nm fabric

From `00-reference-brief.md` and the survey:

1. Total NPU memory must land in the ~100–300 KB range (the SoC-level
   budget is "hundreds of kB" including CPU and buffers). Estimate.
2. All memories ECC-capable (SECDED) with scrubbing; control logic
   TMR-able; fault counters observable over the debug/management
   interface. Project requirement.
3. Verilog only, simulable in Icarus/Verilator, so that the established
   force/release fault-injection flow and its observability
   instrumentation work unchanged. Project requirement.
4. Weights 4-bit baseline (1/2-bit optional packing), matching both Akida
   1.0 practice and tinyODIN/SNE precedent. Fact (precedent), decision
   (baseline).
5. The RV32 management core handles configuration, weight loading, and
   multi-pass sequencing; the NPU must not require a host CPU in the
   spike-processing loop (Akida precedent: node-to-node communication is
   CPU-free). Decision.

Rough physical anchors used in the estimates below (all estimates,
open-PDK 130 nm class): a placed DFF plus routing overhead ~30–60 um², so
10 kFF is on the order of 0.3–0.6 mm²; compiled single-port SRAM at this
node class runs very roughly 1.5–3 mm² per Mb, so 128 KB (1 Mb) of SRAM
is a 1.5–3 mm² commitment before ECC overhead (+22% bits for SECDED on
32-bit words). These anchors must be replaced with real macro data in
`04-technology-and-flow.md`.

---

## 3. Candidate architectures

### Candidate A — scaled physical LIF crossbar ("more of the proven tile")

Direct scale-up of tt-um-lif-crossbar: a physically parallel N x N
crossbar (weights in flip-flops, one hardware neuron per column),
N = 32 as the working point, executed layer-by-layer under a small
sequencer, with weight reload between layers for multi-layer networks.

| Item | Estimate |
|---|---|
| Synapse storage | 32x32 x 4 b = 4 kb in FFs (~4.1 kFF) |
| Neuron state | 32 x 16 b = 512 FF |
| Control/sequencer/IO | ~2–4 kFF |
| Total FF | ~7–9 kFF (~0.3–0.5 mm² placed) |
| SRAM | None required (optional weight-overlay buffer 8–16 KB) |
| Clock target | 25–50 MHz, easily met |

- Workloads: telemetry anomaly detection (small FC nets over tens of
  channels) — yes; KWS — marginal (needs external feature extraction and
  aggressive network shrinking; expect accuracy well below the 91.73%
  Akida reference); event-based vision — no.
- Verification burden: **low.** The neuron and crossbar are already
  verified silicon-bound RTL; new logic is the sequencer and reload path.
  Weeks, not months.
- Fault-tolerance observability: **best of the three.** Every synapse and
  membrane potential is a named FF — the existing force/release fault
  injector can target any bit directly, and TMR/partial-TMR can be applied
  selectively by instance. No SRAM macros to model or protect; the entire
  engine is scrub-free.
- Fundamental limit: FF-based weights do not scale. 64k synapses (the
  ODIN/tinyODIN working point) would need ~256 kb of FFs — roughly
  10–15 mm² by the anchor above — which is not a serious option. Candidate
  A is capped at roughly 2–8 k synapses and is therefore a floor, not a
  destination.

### Candidate B — single time-multiplexed neuron core (ODIN/tinyODIN class)

One event-driven core: synaptic weights in SRAM (crossbar-addressed),
neuron state in a small SRAM or FF file, one physical LIF update pipeline
time-multiplexed across all neurons, AER event queues in and out, SPI/APB
configuration from the RV32 core. Inference-only (no SDSP), 4-bit weights
with 1/2-bit packing. Multi-pass execution: the RV32 core (or a small
DMA) reloads the weight SRAM between layers/passes, following the Akida
multi-pass concept.

Working point: 512 neurons, 256k synapses (512 x 512).

| Item | Estimate |
|---|---|
| Weight SRAM | 256k x 4 b = 128 KB + SECDED ≈ 156 KB |
| Neuron state | 512 x 24 b ≈ 1.5 KB (SRAM or ~12 kFF file) |
| Event queues/scheduler | 2–4 KB FIFO + ~3 kFF |
| Control datapath | ~5–8 kFF |
| Total | ~160 KB SRAM, ~10–20 kFF |
| Half-size fallback point | 256 neurons / 64k synapses → 32 KB + ECC ≈ 40 KB SRAM (tinyODIN-equivalent) |

- Workloads: telemetry anomaly detection — yes, comfortably; KWS — yes
  (256–512 neuron FC/recurrent SNNs on GSC subsets are the standard
  literature configuration; tinyODIN-class capacity); small event-based
  vision — partial (event histograms/downsampled frames into FC layers;
  no native convolution, so vision accuracy will trail an eCNN).
- Verification burden: **moderate.** The time-multiplexed pipeline,
  scheduler, and AER queues are the new risk; however tinyODIN provides a
  permissively licensed (Solderpad v2.1) Verilog reference implementation
  of exactly this microarchitecture, which can serve as an executable
  golden model even if the project RTL is written fresh. Note the
  clean-room obligation applies to *Akida*; Solderpad-licensed academic
  RTL may be studied and even reused with attribution — a policy decision
  is flagged in the open questions.
- Fault-tolerance observability: **good, with known work.** SRAM demands
  ECC + scrubbing and a fault-counter interface (already the project's
  standard pattern); the scheduler/controller FSMs are small enough for
  full TMR; membrane-potential upsets degrade gracefully (a corrupted
  potential decays or triggers one spurious spike) which is a genuinely
  favorable property of LIF dynamics worth demonstrating in the
  fault-injection campaign. Injection into SRAM contents is supported by
  the existing flow via behavioral memory models in Verilog.
- Physical: ~156 KB SRAM ≈ 2–4 mm² plus logic — the dominant NPU cost,
  inside the SoC budget but only just; the 256-neuron half-size point
  exists precisely so the memory budget can be cut 4x without
  architectural change.

### Candidate C — small mesh of event-driven nodes (clean-room Akida-class)

2x2 mesh of nodes on an AER NoC; each node = one engine configurable as
fully-connected or event-based convolution (SNE demonstrates open-RTL
precedent for the conv mode), ~64 KB local weight/activation SRAM per
node (~100 KB Akida anchor, shrunk), shared multi-pass DMA from QSPI/main
SRAM, RV32 core orchestrating pass schedules.

| Item | Estimate |
|---|---|
| Per node: weight SRAM | 48 KB + ECC ≈ 58 KB |
| Per node: event/activation buffer | 8–16 KB |
| Per node: engine datapath + NoC port | ~10–15 kFF |
| Mesh total (4 nodes) | ~280–300 KB SRAM, ~50–70 kFF |
| NoC + DMA + config | ~10–15 kFF, 4–8 KB buffering |

- Workloads: all three — telemetry anomaly, KWS, and small event-based
  vision with native event convolution (e.g., 64x64 event-camera input,
  Falcon Neuro-class detection tasks). This is the only candidate that
  matches the GR801/Akida feature story rather than a subset of it.
- Verification burden: **high.** Four interacting engines, NoC
  arbitration, conv address generation, multi-pass DMA, and a compiler
  problem (mapping networks onto nodes) that does not exist for A or B.
  Realistically the largest single verification object in the whole SoC,
  larger than the RV32 subsystem.
- Fault-tolerance observability: workable but the hardest: distributed
  SRAM (4+ macro groups) means distributed scrubbers and per-node fault
  counters; NoC faults add a failure class (misrouted/dropped events)
  requiring new checkers (sequence counters, spike-count checksums per
  pass). All in Verilog by construction; SNE's SystemVerilog can inform
  the conv engine but should not be imported wholesale into the Icarus
  flow.
- Physical: ~300 KB SRAM ≈ 4.5–9 mm² by the anchors above — at or beyond
  the whole-SoC memory budget from `00-reference-brief.md`. As a v1
  target this over-reaches.

---

## 4. Recommendation

**Baseline: Candidate B**, architected from day one so that Candidate C
is its scale-out rather than a redesign:

1. Implement the single time-multiplexed core (512 neurons / 256k x 4-bit
   synapses, ECC SRAM, AER in/out, multi-pass reload) as the v1 engine.
   It covers the two workloads a CubeSat payload will actually be sold on
   (telemetry anomaly detection per OPSSAT-AD, KWS-class temporal
   classification), reuses the verified LIF neuron lineage from
   tt-um-lif-crossbar in the update pipeline, has an open Verilog
   reference microarchitecture (tinyODIN) to verify against, and fits the
   memory and observability budgets.
2. Freeze the AER event interface and the configuration map as if the
   core were one node of a mesh: node-addressed events, per-core fault
   counters, pass-schedule registers. Then Candidate C becomes
   "instantiate 2–4 cores plus a router and optionally swap one core's
   datapath for an event-conv engine" in a later phase, contingent on an
   event-camera payload actually being in the mission profile
   (see `05-market-positioning.md`).
3. Keep Candidate A alive as the **fallback**, not a parallel effort: the
   RTL substrate (LIF neuron, crossbar update) is shared.

Fallback conditions (trigger → action):

- **F1.** Compiled/generated SRAM macros on the chosen 130 nm PDK fail
  characterization, cannot support SECDED widths, or cannot be modeled in
  the Icarus fault-injection flow → drop to Candidate B's 256-neuron/64k
  point with DFF-based or latch-array memory, and if that still breaks
  area, drop to Candidate A (pure-FF 32x32 engine). The mission story
  narrows to telemetry anomaly detection only.
- **F2.** The time-multiplexed pipeline misses the verification gate
  (schedule) while the crossbar path is green → tape out Candidate A as
  the risk-reduction vehicle and carry B to the next shuttle.
- **F3.** KWS accuracy on the quantized 512-neuron network falls below a
  floor to be set in the benchmark definition (open question 8) →
  re-evaluate a ReckOn-style recurrent topology on the same engine before
  adding any hardware.
- **F4.** An event-camera payload is confirmed as a launch requirement →
  pull the Candidate C conv-engine study forward; do not retrofit
  convolution into the B datapath.

---

## 5. Open questions

1. **SRAM reality check (blocks sizing):** what macro sizes, port
   configurations, and ECC-friendly widths does the selected 130 nm open
   PDK actually provide, and at what mm²/Mb? (Feeds
   `04-technology-and-flow.md`; every budget in section 3 depends on it.)
2. **Reuse policy for Solderpad RTL:** does the project reuse
   tinyODIN/ODIN Verilog directly (legal under Solderpad v2.x with
   attribution), use it only as a golden reference model, or stay fully
   clean-room across the board for positioning reasons?
3. **Training/quantization toolchain:** Akida's MetaTF is proprietary;
   which open stack (e.g., snnTorch/Norse + QAT to 4/2/1-bit, or
   ANN-to-SNN conversion) produces deployable weights, and who owns the
   compiler from trained network to weight-SRAM image and pass schedule?
4. **Input encoding:** rate coding (as in the prior tile), rank-order
   coding (Akida's published choice), or direct event streams — and does
   one encoding serve both telemetry and audio front-ends, or does the
   engine need two input paths?
5. **Multi-pass ownership:** is layer/pass sequencing done by the RV32
   core (simple, slower, more observable) or a dedicated DMA/sequencer
   (faster, more RTL to verify), and what is the QSPI reload latency
   budget per pass?
6. **Neuron-state upset policy:** is graceful degradation of membrane
   potentials acceptable without protection (backed by a fault-injection
   measurement of accuracy-under-upset), or do mission requirements force
   parity/duplication on neuron state too?
7. **Mesh commitment point:** what concrete mission evidence (payload
   with an event camera, per `05-market-positioning.md`) would justify
   Candidate C's verification cost, and by which roadmap gate must that
   evidence exist?
8. **Benchmark definition:** fix the acceptance suite now — proposed:
   OPSSAT-AD subset (telemetry), GSC 10/12-class subset (KWS), and
   optionally N-MNIST or a Falcon Neuro-style event task (vision, only if
   C proceeds) — with accuracy floors and energy/inference targets per
   candidate.
9. **Clock and power targets:** the SKY130A precedent ran at 89 MHz and
   3.7 uJ/inference (https://ceur-ws.org/Vol-3960/short6.pdf); what
   frequency and energy-per-inference targets should gate this design,
   given the spacecraft power budget assumed in
   `05-market-positioning.md`?
10. **External event interface:** should the AER input be exposed at the
    chip boundary (native event-sensor connectivity, Falcon Neuro-class
    payloads) in v1, or only internal with SPI/QSPI-fed events, deferring
    the pad and protocol cost?
