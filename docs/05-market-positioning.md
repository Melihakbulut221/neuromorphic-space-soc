# Market positioning and competitive landscape

Research-phase report. This document places the project against the GR801
reference product and the wider space edge-AI silicon market, then states
the positioning rules that bind all external communication about this SoC.

Throughout the document, statements are labelled as **[fact]** (traceable to
a cited public source) or **[estimate]** (inference, industry heuristic, or
project judgment). Where a price or date is an estimate, no cited source
claims it.

---

## 1. The reference product: GR801 market position

### 1.1 What GR801 is and who it is for

GR801 is the first device of Frontgrade Gaisler's GRAIN (Gaisler Research
Artificial Intelligence NOEL-V) product line: a radiation-hardened SoC
combining a fault-tolerant NOEL-V RV64GC RISC-V management processor with a
licensed BrainChip Akida 1.0 neuromorphic accelerator on STMicroelectronics
28 nm FDSOI. The public product brief was released April 2026 with status
"under development" (https://www.gaisler.com/products/gr801). **[fact]**

Commercialization is backed by a Swedish National Space Agency (SNSA)
contract to bring the first neuromorphic SoC for space applications to
market
(https://www.frontgrade.com/news/frontgrade-gaisler-launches-new-grain-line-and-wins-snsa-contract-commercialize-first-energy,
https://riscv.org/blog/frontgrade-gaisler-to-commercialise-neuromorphic-ai-for-space/).
**[fact]** The Akida IP license for space deployment was announced by both
companies
(https://www.gaisler.com/news-events/frontgrade-gaisler-licenses-brainchips-akida-ip-to-deploy-ai-chips-into-space).
**[fact]** Advertised applications include lightning detection, cloud-cover
detection, change monitoring, collision avoidance, and rover traversability
mapping (https://www.eenewseurope.com/en/frontgrade-gaisler-to-commercialise-neuromorphic-ai-for-space/).
**[fact]**

Target customer profile: institutional space programs (ESA, national
agencies, primes) that already fly Gaisler LEON/NOEL silicon and buy
ESCC-qualified parts with full radiation lot data. Gaisler's flight
heritage (GR712RC, GR740 as the ESA Next Generation Microprocessor,
http://microelectronics.esa.int/gr740/index.html) makes GR801 the default
choice for missions that must show qualification paperwork to an agency
customer. **[estimate**, but strongly supported by Gaisler's ESA-anchored
product history**]**

### 1.2 Price class

No public list price exists for GR801, GR740, or GR716 flight parts;
Gaisler quotes on request (https://www.gaisler.com/products/gr740,
https://www.gaisler.com/products/gr716a). **[fact]**

Public reference points for the price class:

- Industry surveys place fully qualified space-grade processors at
  USD 10k-200k+ per unit, with rad-hard devices commonly "tens of
  thousands of dollars"
  (https://hubble.com/community/comparisons/why-radiation-hardening-matters-for-satellite-processors-and-what-it-costs/,
  https://www.deloitte.com/content/dam/insights/articles/2024/ca175595_radiation-semiconductors/di-tmtp23-radiation-semiconductors.pdf).
  **[fact** that these sources state these ranges**]**
- The cost drivers are structural: multi-year qualification campaigns
  amortized over unit volumes in the dozens-to-hundreds
  (https://hubble.com/community/comparisons/why-radiation-hardening-matters-for-satellite-processors-and-what-it-costs/).
  **[fact]**

Working assumption for this project: GR801 flight parts (GR801-AS, ESCC9030
screened) will land in the EUR 20k-100k class per unit, consistent with
GR740/GR712RC-class flight silicon; engineering models cheaper but still
thousands of EUR. **[estimate]** This is the number that matters for the
positioning argument in Section 3: a 6U CubeSat with a total payload budget
under EUR 500k cannot spend a large fraction of it on one component.

### 1.3 Qualification timeline

The brief specifies the GR801-AS flight model with ESCC9030 screening, TID
50 krad(Si) guaranteed by platform, 100 krad(Si) testing planned, SEL TBC
(https://www.gaisler.com/products/gr801). **[fact]** The device is "under
development" as of the April 2026 brief. **[fact]**

Typical Gaisler cadence from product brief to qualified flight parts has
been multi-year (GR740: ESA NGMP development through the 2010s, flight
parts shipping from late 2021, https://www.gaisler.com/products/gr740).
**[fact]** Expect GR801 engineering silicon first, with ESCC-qualified
flight models roughly 2-4 years after the brief, i.e. 2028-2030.
**[estimate]** This window matters: the qualified-neuromorphic-SoC market
is not served today, and low-cost alternatives that fly earlier can build
heritage before GR801 flight models are broadly available.

---

## 2. Competitive landscape: space edge-AI silicon

### 2.1 The players

| Product | Class | AI approach | Radiation posture | Access model |
|---|---|---|---|---|
| Frontgrade Gaisler GR801 | Rad-hard SoC, 28 nm FDSOI | Neuromorphic (Akida 1.0) | ESCC9030, 50 krad platform, 100 krad testing planned | Proprietary, quote-based, ESCC class |
| Microchip PIC64-HPSC | Rad-hard/rad-tolerant MPU, 8x SiFive X280 + vector | CNN/vector inference | Rad-hard variants, NASA/JPL program | Proprietary, NASA-anchored (USD 50M JPL contract) |
| Teledyne e2v QLS1046-Space (Qormino) | Rad-tolerant Arm Cortex-A72 module | CPU deep-learning inference | 100 krad TID, SEL/SEU under qualification | Proprietary module, quote-based |
| AMD Versal AI Edge XQRVE2302 | Space-grade adaptive SoC (FPGA + AI engines) | AIE-ML INT8/BF16 | Radiation-tolerant, Class B qualified | Proprietary, orderable, high-end price class |
| Frontgrade "certifiable COTS" / Series-300-style COTS | Screened commercial parts | Various | LEO/short-mission screening | Proprietary, mid price class |
| Intel Loihi (TechEdSat-13) | Research neuromorphic chip, flight experiment | SNN | Not space-qualified; flown as experiment | Research access only |
| BrainChip Akida AKD1000 (ANT61 Brain, Optimus-1) | COTS neuromorphic chip flown in LEO | SNN/event-based | COTS, no radiation rating | Commercial COTS |
| Unibap SpaceCloud iX10 | Board/system (AMD Ryzen + Radeon + PolarFire) | GPU/CPU inference | Radiation-tolerant system design | Proprietary system, board-level price |
| Aitech S-A1760 Venus | Board/system (NVIDIA Jetson TX2i) | GPU (CUDA) | Radiation-characterized COTS, >1.5 krad TID, LEO/short missions | Proprietary system |

Sources: GR801 (https://www.gaisler.com/products/gr801); PIC64-HPSC
architecture and JPL contract
(https://www.microchip.com/en-us/products/microprocessors/64-bit-mpus/pic64-hpsc,
https://www.microchip.com/en-us/about/news-releases/products/microchip-unveils-industrys-highest-performance-64-bit-hpsc-mpu,
https://spacedaily.com/t-nasa-hpsc-processor-500-times-faster-spaceflight-ai/);
QLS1046-Space
(https://semiconductors.teledyne-e2v.com/products/qormino/?model=QLS1046-Space,
https://www.signalintegrityjournal.com/articles/2846-teledyne-e2vs-peripheral-rich-quad-core-arm-cortex-a72-space-processor-gives-spaceborne-imaging-and-ai-a-major-boost);
Versal XQRVE2302
(https://www.amd.com/en/products/adaptive-socs-and-fpgas/versal/space-grade.html,
https://www.amd.com/en/blogs/2025/available-for-order-flight-qualified-amd-versal-a.html);
Loihi on TechEdSat-13, first orbital flight of a neuromorphic processor
(https://ntrs.nasa.gov/citations/20210026935); Akida AKD1000 in LEO on
Optimus-1 via the ANT61 Brain
(https://www.businesswire.com/news/home/20240304523354/en/BrainChip-Boosts-Space-Heritage-with-Launch-of-Akida-into-Low-Earth-Orbit,
https://brainchip.com/akida-in-space/); SpaceCloud iX10
(https://unibap.com/solutions/spacecloud-hardware/ix10,
https://unibap.com/wp-content/uploads/2024/04/ix10-101-product-overview.pdf);
S-A1760 Venus (https://aitechsystems.com/product/s-a1760-space-gpgpu/,
https://spacenews.com/aitechaeurs-s-a1760-venusac-brings-nvidia-based-ai-supercomputing-to-next-generation-space-applications/).
All rows **[fact]** as to product existence and stated specs; price-class
columns where implied are **[estimate]**.

### 2.2 Structure of the market

Three tiers are visible:

1. **Qualified rad-hard silicon** (GR801, PIC64-HPSC, Versal XQR,
   QLS1046-Space): institutional missions, long qualification cycles,
   tens-of-thousands-and-up unit prices. **[estimate** on prices, per
   Section 1.2 sources**]**
2. **Radiation-characterized COTS systems** (SpaceCloud iX10, S-A1760
   Venus, Series-300-style screening): LEO and short missions, board-level
   products built on commercial GPU/CPU silicon, thousands-to-tens-of-
   thousands per board. **[estimate]**
3. **Flight experiments with commercial neuromorphic parts** (Loihi on
   TechEdSat-13, AKD1000 on Optimus-1): demonstrations, not products.
   **[fact]**

### 2.3 The open/low-cost gap

Observations that define the gap this project targets:

- **No open-architecture device exists in any tier.** Every product above
  is proprietary silicon or a proprietary board. No vendor publishes RTL,
  verification suites, or fault-injection data. A mission integrator
  cannot independently audit the fault-tolerance claims of any of them.
  **[fact** by absence; no counterexample found in the survey**]**
- **No chip-level neuromorphic product exists below the rad-hard tier.**
  Between "USD 20k+ qualified SoC" (GR801, when released) and "unrated
  commercial AKD1000 on a custom board" there is nothing: no
  fault-tolerant-by-architecture, low-cost, chip-level event-driven
  inference device for CubeSat-class missions. **[fact** by absence in
  this survey; kept under review**]**
- **The COTS-systems tier proves LEO demand at low radiation ratings.**
  Aitech explicitly sells the S-A1760 at >1.5 krad TID for LEO/short
  missions (https://aitechsystems.com/product/s-a1760-space-gpgpu/);
  Unibap sells SpaceCloud into CubeSat/microsat programs
  (https://unibap.com/news/order-for-spacecloud-ix10-from-hawaii-space-flight-laboratory/).
  Missions accept modest ratings when the price and power fit. **[fact]**
- **Neuromorphic-in-space is validated but unserved at low cost.** NASA
  flew Loihi on a 3U CubeSat precisely because event-driven processors
  suit nano-satellite power budgets
  (https://ntrs.nasa.gov/citations/20210026935); BrainChip is building
  space heritage for Akida (https://brainchip.com/akida-in-space/). The
  demand signal exists; the affordable, fault-tolerant supply does not.
  **[fact** for the flights, **estimate** for the demand inference**]**

---

## 3. Positioning of this project

### 3.1 What this project is not

This project does not compete with GR801 head-on. It cannot and should
not: GR801 has a 28 nm FDSOI platform with intrinsic SEL immunity, an
ESCC9030 qualification path, licensed production-grade Akida IP, 11.2 MB
of on-chip SRAM, PCIe/GbE/SpaceWire-router I/O, and an institutional sales
channel. A solo-developer 130 nm open-flow chip matching that is not a
realistic goal, and claiming otherwise would destroy credibility.
**[estimate/judgment]**

### 3.2 The wedge

The realistic position is three-fold:

**(a) Ultra-low-cost fault-tolerant neuromorphic coprocessor for
CubeSat-class missions.** The customer is a university CubeSat program, a
newspace startup flying a 3U-16U bus, or a research payload that cannot
justify a EUR 20k+ part but wants better-than-COTS fault behavior.
The price target is the "expensive FPGA" class, not the "flight
processor" class: an order of magnitude (or two) below the rad-hard tier.
The value proposition is honest, architecture-level fault tolerance (TMR
control, ECC + scrubbing, fault counters, documented fault-injection
results) on a bulk 130 nm node — positioned exactly where Aitech's
Series-300-style "LEO and short missions" reasoning already proved buyers
exist. **[estimate/strategy]**

**(b) Open-architecture transparency as the differentiator.** No
competitor lets the integrator read the RTL, re-run the fault-injection
campaign, or extend the verification suite. For research missions and
agencies funding open hardware (and for buyers wary of black-box AI
accelerators in the loop), auditability is a feature the incumbents
structurally cannot offer. This is the one axis on which a solo open-flow
project is not merely "cheaper GR801" but categorically different.
**[estimate/strategy]**

**(c) Portfolio and credibility vehicle.** Independent of sales, a
completed GR801-class SoC — CPU + event-driven fabric + space interfaces,
taken through an open RTL-to-GDS flow with a documented hardening story —
is a demonstration of full-SoC capability that supports the developer's
broader fault-tolerant-silicon product line and services positioning.
This motivation is internal and does not appear in external marketing.
**[fact** about intent**]**

### 3.3 Relationship to GOLDFINCH-1: differentiation, not cannibalization

The developer's existing adjacent product, GOLDFINCH-1, is a 130 nm-class
INT8 systolic-array accelerator MVP for telemetry anomaly detection,
a TTSKY26d shuttle candidate. The two products must be kept distinct:

| | GOLDFINCH-1 | This SoC |
|---|---|---|
| Class | Minimal peripheral accelerator | Standalone SoC (CPU + fabric + I/O) |
| Compute model | Frame-based INT8 systolic MAC | Event-driven SNN fabric |
| Role in the system | Attaches to an existing OBC over a simple bus | Is the payload computer (RV32 manager on-die) |
| Workload | Batched telemetry vectors, periodic inference | Sparse event streams, always-on monitoring |
| Analogy in the market | "Tiny Versal AIE slice" | "Tiny GR801" |

Does the market need both? Yes, because the workloads split cleanly:

- **Frame-based / batched workloads** (telemetry windows, periodic
  spectral snapshots, scheduled image tiles) map to a systolic array with
  predictable utilization. GOLDFINCH-1 wins on simplicity and cost when an
  OBC already exists. **[estimate]**
- **Event-driven workloads** favor this SoC: sparse event streams where
  most cycles carry no information (event/DVS cameras, star-tracker
  anomaly flags, particle-detector hits, RF burst detection), and
  always-on low-power monitoring where the chip must idle at microwatts
  and wake on activity — the exact regime NASA cited for flying Loihi on
  TechEdSat-13 (https://ntrs.nasa.gov/citations/20210026935) and Gaisler
  cites for Akida's event-based computing
  (https://www.gaisler.com/products/gr801). Duty-cycled CubeSat power
  budgets (single-digit watts orbit-average) are where
  activity-proportional compute pays. **[fact** for the cited rationales,
  **estimate** for the mapping to this SoC**]**

Sales guidance: GOLDFINCH-1 is the entry product ("add anomaly detection
to your existing OBC"); this SoC is the step-up product ("replace the
payload computer with one fault-tolerant AI-native part"). A mission that
buys one is not the mission that buys the other in the same slot.
**[strategy]**

### 3.4 Mission profiles that favor this SoC

- Always-on health monitoring of bus telemetry with wake-on-anomaly,
  where orbit-average power must stay in the tens of milliwatts.
- Event-camera payloads (lightning mapping, sprite detection, debris
  streak detection) producing inherently sparse address-event streams.
- Attitude/collision-relevant event detection requiring on-board
  reaction faster than a ground loop.
- Long-idle mission phases (transfer, storage orbits) where a
  frame-based accelerator would burn its budget doing nothing.

All **[estimate]**: candidate profiles for validation in the roadmap
phase, aligned with the application classes Gaisler advertises for GR801
(https://www.eenewseurope.com/en/frontgrade-gaisler-to-commercialise-neuromorphic-ai-for-space/).

---

## 4. Positioning language rules (binding)

These rules were established in a prior export review for the developer's
existing product line and are restated here as binding policy for this SoC.
All public text — README, datasheets, pitch material, shuttle submissions,
conference abstracts — must comply.

1. **Radiation class: LEO / 10-30 krad(Si) class.** State the design
   target as LEO-class total dose in the 10-30 krad(Si) range, pending
   test data. Never state or imply a rating that has not been measured on
   silicon.
2. **"Fault-tolerant", never "rad-hard".** The chip is fault-tolerant by
   architecture (TMR, ECC, scrubbing, monitors) on a commercial bulk
   130 nm process. "Radiation-hardened" implies process-level and
   qualification claims this project does not make. This is also the
   honest engineering description: bulk CMOS has no intrinsic SEL
   immunity (see docs/00-reference-brief.md, observation 5).
3. **Export-control red lines.** Never claim, target, or advertise TID
   ratings at or above 100 krad(Si), and never use marketing language that
   maps the device onto space-qualified rad-hard categories in
   EAR 9A515 / dual-use 3A001-class threshold territory. Public
   positioning stays strictly below those thresholds; no SEL/SEE
   guarantee language beyond what measured data supports. When in doubt,
   the lower claim wins.
4. **Multi-market framing.** Public positioning is "fault-tolerant edge
   inference for harsh environments" — small-satellite LEO payloads as
   the lead market, with industrial/high-reliability terrestrial uses
   (radiation environments in medical/energy, safety-critical monitoring)
   named alongside. The device is not marketed as a military or
   strategic-space component.
5. **Fact/estimate discipline in public claims.** Any figure published
   externally (power, TID, SEU rates, fault coverage) must be traceable to
   measurement or clearly labelled as a design target, mirroring the
   fact/estimate separation used in these research documents.

Rule 1-3 rationale: the GR801 brief itself illustrates the other side of
the line — 50 krad platform-guaranteed with 100 krad testing planned under
ESCC9030 (https://www.gaisler.com/products/gr801) is precisely the claim
territory this project must stay out of, in wording as well as in fact.

---

## 5. Summary

- GR801 will own the institutional, ESCC-qualified neuromorphic-SoC
  segment at a tens-of-thousands-EUR price class **[estimate]**, with
  flight models plausibly 2028-2030 **[estimate]**.
- The competitive field (PIC64-HPSC, Versal XQR, QLS1046-Space, SpaceCloud,
  Aitech) leaves an empty cell: chip-level, fault-tolerant, event-driven
  inference at CubeSat prices with an open architecture. **[fact by
  absence in this survey]**
- This project fills that cell as a low-cost fault-tolerant neuromorphic
  SoC and credibility vehicle, deliberately not competing with GR801, and
  deliberately differentiated from GOLDFINCH-1 (peripheral frame-based
  accelerator vs. standalone event-driven SoC).
- All public language follows the binding rules of Section 4:
  fault-tolerant, LEO/10-30 krad class, below export-control claim
  thresholds, multi-market framing.
