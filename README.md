# Neuromorphic Space SoC

A fault-tolerant system-on-chip for on-board AI inference in small-satellite
missions, implemented on a 130 nm technology with an open-source RTL-to-GDS
flow. The architecture class follows the Frontgrade Gaisler GR801 (public
product brief, April 2026): a RISC-V management processor, an event-driven
neuromorphic inference engine, on-chip SRAM, and a set of spacecraft
interfaces — retargeted from STM 28 nm FDSOI to a 130 nm node at a scale
that is realistic for an open PDK and a small team.

## Reference architecture (GR801, public brief)

| Block | GR801 (28 nm FDSOI) | This project (130 nm, targets under study) |
|---|---|---|
| Management CPU | NOEL-V FT, RV64GC single core | RV32 core, selection in research phase |
| AI engine | Akida 1.0, 8 nodes x 4 engines, 1/2/4-bit weights | Event-driven SNN fabric, sizing in research phase |
| On-chip RAM | 8 MB shared + 3.2 MB Akida-private | Hundreds of kB class, ECC-protected |
| External memory | QSPI controller, 2 chip selects | QSPI controller |
| Interfaces | PCIe Gen3 x4, SpaceWire router 4x, GbE, CAN FD 2x, SPI, 2x I2C, 3x UART, CPI, 16 GPIO | Subset: SpaceWire codec, CAN, SPI, I2C, UART, GPIO, optional 8-bit CPI; PCIe/GbE out of scope |
| Hardening | ECC on CPU/memories, fault detection on Akida memories | Layered: control TMR, memory ECC + scrub, fault counters |

## Status

Research phase complete and independently reviewed; design phase started
(NPU specification, golden model, register map, first RTL block with
simulation and formal proofs). `ROADMAP.md` is the phased plan.

## Documents

- `docs/00-reference-brief.md` — GR801 public-brief summary and initial scaling observations
- `docs/01-reference-decomposition.md` — GR801 architecture decomposition and 28 nm to 130 nm scaling analysis
- `docs/02-npu-architecture.md` — event-driven inference engine options and recommendation
- `docs/03-cpu-and-ip-survey.md` — management CPU and interface IP survey (licensing, verification fit)
- `docs/04-technology-and-flow.md` — 130 nm technology selection, memory strategy, flow and cost
- `docs/05-market-positioning.md` — mission profile, competitive landscape, positioning rules
- `docs/06-funding-and-shuttle.md` — NLnet grant plan and TTIHP26b shuttle logistics
- `docs/07-design-review.md` — independent review of the research phase and design wave 1
- `docs/08-gr801-datasheet-notes.md` — GR801/GRLIB programmer-visible conventions and proximity checklist
- `docs/09-formal-verification-plan.md` — formal verification program (RTL formal, golden-model refinement, software track)
- `docs/10-npu-mvp-spec.md` — NPU MVP micro-architecture specification v0.1
- `docs/11-verification-harness.md` — how to run the simulation and formal harness
- `docs/regmap-npu.md` — generated register-map documentation (single source: `regmap/regmap.yaml`)
- `ROADMAP.md` — phased plan with gates
