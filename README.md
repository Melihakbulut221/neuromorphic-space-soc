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

**The pilot is frozen and signed off; the SoC around it is not built.**
Read `docs/00-index.md` for the full what-exists-and-what-does-not, and
`ROADMAP.md` for the plan. In short, as of 2026-08-31:

*Exists, and is verified.* An event-driven LIF inference core, its AER
event queues, a register bank generated from a single-source map, a
SECDED codec, a TMR voter and a scrub controller — 6,856 lines of
Verilog. Verification is 234 Python tests against frozen bit-exact golden
models, 166 cocotb tests, 54 SymbiYosys proof tasks, a seeded
fault-injection campaign of 378 upsets classified against the golden
model, and a gate-level run in which 370 of 370 comparable injections
classify identically to RTL. `docs/34-pilot-freeze.md` pins the whole
artifact set by hash.

*Manufacturable, on every check an open flow can run.* The 6x2 pilot
signs off on IHP SG13G2 with Magic DRC, KLayout DRC, XOR, all four
Netgen LVS unmatched counters, antenna, power grid and illegal overlap
at zero,
setup and hold clean on three corners with a real 5 percent derate, and
the Tiny Tapeout precheck at 10 of 10. No silicon exists and the hosted
GDS action has not run.

*Exists, and is unhardened.* A management subsystem, begun after the
pilot froze and kept strictly separate from it. Ibex (`small-pmp`:
RV32IMC, PMP, no lockstep) is brought up through sv2v on the pinned
toolchain and runs a self-checking bare-metal program; a memory map
frozen as a single generated source; and a fabric that speaks Ibex's own
protocol internally with real AMBA 3 APB at the peripheral boundary,
proved compliant by k-induction. The bring-up program runs end to end
out of boot ROM through that fabric with the console decoded off a real
serial line. `docs/38` and `docs/39` are the records.

It now also has interrupts, timers and a watchdog: a RISC-V CLINT on the
system bus, a GRLIB-style GPTIMER on the peripheral bus, and a watchdog
that escalates through a non-maskable interrupt to a system reset to an
external pin, cannot be disabled or slowed by the software it watches,
and keeps its record through the reset it causes. A timer interrupt is
taken and returned from on the real fabric; the whole escalation ladder
runs end to end across three boots of the SoC in one simulation.
`docs/40` is the record, and it argues the decision *not* to build a
platform interrupt controller rather than assuming it.

The watchdog's own state is now protected, and `docs/41` is the record.
The eight fields nothing rewrites — the bootstrap latch, the stage-1
pending flag, the reset record and count, the reset stretch — are
bundled into one word and tripled under the pilot's own proved voter,
because six of them are single bits and three replicas cannot be held
apart over one bit. The counter, the reload and the prescaler are
deliberately left as single points, and the price of that is measured
rather than argued. It costs 1.85 % of the Ibex core, it is counted in
the mapped netlist rather than assumed to have survived synthesis, and
162 fault injections into the block's own flip-flops classify every
upset in the protected word as corrected — against a counterfactual run
on the unprotected block where two single-bit upsets left the watchdog
silently disarmed.

The rest of the SoC still has **no fault tolerance of any kind** — no
ECC, no scrubbing, no TMR outside that one word, no bus error latch, and
nothing on the CLINT's `mtime`, which `docs/41` section 7.4 ranks as the
next thing to protect. That is a deliberate ordering, not an oversight:
the fabric is being made correct before it is made survivable. Note what
it means in combination with the `small-pmp` choice, which declined
Ibex's lockstep: the management processor is still the least protected
block in the design and `docs/38` section 10 item 4 records what that
obliges — but the backstop it leaves the core is no longer itself
unprotected.

*Does not exist.* No silicon. No spacecraft interfaces. No SRAM macro in
any hardened design. No radiation test data. No bus error latch or
scrubber. No place-and-route, timing or gate-level result for anything
under `hw/soc/`. No licence. No funding.

The next block is the management core's own fault-injection campaign —
which `docs/38` made a consequence of declining lockstep rather than
deferred work, and which can now measure not only the core's silent-error
rate but how much of it the watchdog actually catches.

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
- `docs/12-sg13g2-flow-bringup.md` — IHP SG13G2 flow bring-up, trial harden and SRAM macro inventory
- `docs/13-nlnet-application.md` — NLnet Restack application draft
- `docs/14-licensing-decision.md` — open-licensing decision memo (NLnet terms, dependency licenses, export interaction)
- `docs/15-pilot-tile-plan.md` — pilot die content, pin contract and tile budget
- `docs/16-fault-injection-campaign.md` — seeded upset campaign, measured outcome distribution and per-structure ranking
- `docs/17-wave2-review-record.md` — independent review record for design wave 2
- `docs/regmap-npu.md` — generated register-map documentation (single source: `regmap/regmap.yaml`)
- `ROADMAP.md` — phased plan with gates

**`docs/00-index.md` is the canonical list and this one stops at 17 on
purpose.** The corpus is past thirty documents, and a second hand-kept
list is a list that drifts — this one already had, silently. The index is
generated against the directory and `sw/tests/test_doc_links.py` fails if
a document is missing from it or a cross-reference names a file that does
not exist, so it cannot go stale without the suite saying so. Start
there.

## Layout

- `hw/rtl/` — RTL blocks; `hw/tb/` — cocotb testbenches, one `Makefile.<block>` each
- `formal/` — SymbiYosys configurations and property files; `make -C formal everything` runs the full gate
- `sw/golden/` — bit-exact integer golden models (the abstract specification); `sw/tests/` — their pytest suite
- `regmap/` — the register map single source and its generators
- `hw/openlane/` — physical flow configurations for IHP SG13G2
