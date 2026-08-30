# 00 — Index: what this is, what exists, and where to start

Entry point to the document corpus. It states what the project is, what
physically exists in this repository today as against what is planned,
how the twenty-odd documents relate to one another, and which of them to
read first depending on why you are reading.

Convention, as everywhere in this repository: **[fact]** = measured in
this environment or read out of a file in the working tree;
**[estimate]** = derived or judged; **[planned]** = an intention with a
date attached and no artifact behind it yet.

Every count below carries the command that produced it. They were
re-measured on 2026-08-26 against the working tree rather than copied
from another document, because several documents state totals that were
correct when they were written and have since been overtaken by later
work — see section 6.

---

## 1. What this project is

A fault-tolerant system-on-chip for on-board AI inference in
small-satellite missions, implemented on a 130 nm open PDK with an
open-source RTL-to-GDS flow, by a solo developer.

The architecture class follows the Frontgrade Gaisler GR801 as published
in its April 2026 product brief — a RISC-V management processor, an
event-driven neuromorphic inference engine, on-chip SRAM and a set of
spacecraft interfaces — retargeted from 28 nm FDSOI to 130 nm at a scale
an open PDK and one person can actually carry. It is a clean-room
retarget, not a clone: no Gaisler or BrainChip IP is used, and the
GR801 serves as the requirement set and the yardstick. The reference
analysis is `docs/00-reference-brief.md` and
`docs/01-reference-decomposition.md`; the positioning rules that bind
every external claim are `docs/05-market-positioning.md` section 4.

Three things distinguish it from a hobby tapeout, and each is a
falsifiable claim rather than a slogan:

- **Spec-first with frozen golden models.** The bit-exact integer models
  in `sw/golden/` are the specification; RTL is verified against them in
  lockstep, not against a testbench author's expectations. See
  `docs/10-npu-mvp-spec.md` and `docs/11-verification-harness.md`.
- **Formal proof where the property is provable.** Seven blocks carry
  SymbiYosys property sets. See `docs/09-formal-verification-plan.md`.
- **Fault tolerance that is measured, not asserted.** TMR, SECDED and
  scrubbing are demonstrated by a seeded upset campaign that reports an
  outcome distribution per structure, judged against the golden model.
  See `docs/16-fault-injection-campaign.md`.

## 2. What exists today, and what does not

### 2.1 Exists — artifacts in this working tree [fact]

| What | Where | Evidence |
|---|---|---|
| RTL: AER FIFO, LIF core, NPU register bank, SECDED encoder and decoder, TMR voter, scrub controller, pilot top level, Tiny Tapeout wrapper | `hw/rtl/` (**9 `.v` files, 5,366 lines**, plus the generated `npu_regs.vh` header for 10 files and 5,491 lines in total; re-counted 2026-08-29, was "10 files, 3,800 lines" on 2026-08-26) | `wc -l hw/rtl/*.v` |
| Bit-exact golden models: LIF core, network, SECDED, register-map generator | `sw/golden/` | `docs/10-npu-mvp-spec.md` |
| Python suite: **196 tests collected**, re-counted 2026-08-29 (was 185 at commit `fe89f0d`, where the suite ran 152 passed, 1 skipped in 87 s before this index's link check added 32 of them). Collection is not execution: the pass/skip split has not been re-run here | `sw/tests/` | `.venv/bin/python -m pytest --collect-only -q` at the repository root |
| cocotb suites: **145 test functions across 8 modules**, re-counted 2026-08-29 (was 129); seven of them reachable as `make -C hw/tb TB=<block>` | `hw/tb/` | `grep -c '@cocotb.test' hw/tb/test_*.py` |
| Formal: **45 SymbiYosys tasks across 7 property sets** (`aer_fifo` 4, `lif_ctrl` 8, `lif_mem` 8, `npu_regbank` 5, `scrub` 9, `secded` 3, `tmr_voter` 8), re-measured 2026-08-29 | `formal/` | the `[tasks]` sections of `formal/*.sby`; `make -C formal -n everything \| grep -c "sby -f"` counts them, `make -C formal everything` runs them all |
| Register map, single-sourced from `regmap/regmap.yaml`, with a sync test that fails if spec, generated document and RTL header drift apart | `regmap/`, `docs/regmap-npu.md` | `sw/tests/test_regmap.py` |
| IHP SG13G2 sign-off of a single block (`aer_fifo`) | `hw/openlane/aer_fifo/runs/trial-03-signoff/` | `final/metrics.json`: 0 Magic DRC, 0 KLayout DRC, 0 LVS errors, 0 antenna nets and pins, 0 XOR differences, 0 power-grid violations |
| IHP SG13G2 sign-off of the integrated 4x2 pilot at 52.4 % utilization. **The 52.4 % is the `tt-harden` run of 2026-08-25 and is three hardening waves stale; the current utilization is in `docs/22-reharden-wave5.md` and is not restated here because a further run was in progress on 2026-08-29** | `tt/runs/tt-harden/` | `final/metrics.json`: 0 Magic DRC, 0 LVS errors, 0 antenna nets and pins, 0 unmapped instances, 0 max-slew and 0 max-cap violations on all three corners |
| SKY130A harden of the same RTL, as a portability control | `hw/openlane/pilot_sky130/runs/sky-02-signoff/` | `final/metrics.json`: 0 Magic DRC, 0 KLayout DRC, 0 LVS errors, 0 antenna nets and pins, 0 XOR differences. Max-slew violations are *not* zero on this PDK; `docs/18-cross-pdk-portability.md` records why |
| A Tiny Tapeout submission tree for TTIHP26b, generated rather than hand-maintained | `tt/`, `scripts/gen_tt_submission.py` | `sw/tests/test_tt_submission.py` |
| A measured fault-injection outcome distribution for `pilot_top` | `hw/tb/fi_campaign_results.json` | `docs/16-fault-injection-campaign.md` |
| 27 markdown source files: 25 under `docs/` including this one, plus `README.md` and `ROADMAP.md`, re-counted 2026-08-29 | `docs/`, `README.md`, `ROADMAP.md` | `ls docs/*.md \| wc -l`; `_site/manifest.json` after `python3 scripts/build_docs.py` |

Two of the run directories above are git-ignored build output. On a
fresh clone they are absent and the artifact half of
`sw/tests/test_flow_evidence.py` skips rather than fails; the commands
that regenerate them are in that file's docstring and in
`docs/12-sg13g2-flow-bringup.md`.

### 2.2 Does not exist [fact]

- **No silicon.** Nothing has been fabricated. The TTIHP26b shuttle
  closes 2026-09-21 and its silicon is expected 2027-06-25 per
  `ROADMAP.md` section 1; every radiation and reliability statement in
  this repository is therefore pre-silicon.
- **No radiation test data.** No TID, proton or heavy-ion result exists.
  The fault-injection campaign is a simulation of single-bit upsets, not
  a beam test, and `docs/16-fault-injection-campaign.md` says so in its
  own limitations section.
- **No management CPU.** The RV32 core is surveyed in
  `docs/03-cpu-and-ip-survey.md` and not selected, integrated or
  verified.
- **No spacecraft interfaces.** SpaceWire, CAN, QSPI, SPI, I2C, UART and
  GPIO are scoped and costed; none is implemented.
- **No SRAM macro in any hardened design.** Every result above is
  flip-flop RAM. The RM_IHPSG13 macro study is in
  `docs/12-sg13g2-flow-bringup.md`.
- **No licence.** `docs/14-licensing-decision.md` is a decision memo with
  an unsigned decision section. Until it is signed the repository is
  unpublished and unlicensed, and that is why the documentation workflow
  in `.github/workflows/docs.yml` builds the site but deliberately does
  not publish it.
- **No funding.** `docs/13-nlnet-application.md` is a submission-ready
  draft. The NLnet Restack deadline is 2026-11-03.

### 2.3 Planned, with dates [planned]

The authoritative plan is `ROADMAP.md`; it carries the phase gates and
the external clocks. The near-term shape is: freeze and submit the pilot
before 2026-09-21, submit the NLnet application before 2026-11-03, build
the SoC through 2027, bring up pilot silicon from mid-2027. Effort
figures in `ROADMAP.md` phase P3 are tagged `[estimate]` and should be
read as such.

## 3. How the documents relate

The corpus is not a single narrative. It is five overlapping tracks laid
down in roughly chronological order, plus two review records that cut
across all of them.

**Research (00-06)** established what is being built and why. `docs/00`
summarises the GR801 brief; `docs/01` decomposes it and does the 28 nm
to 130 nm scaling; `docs/02`, `docs/03` and `docs/04` choose the
inference engine, the CPU and interface IP, and the technology and flow
respectively; `docs/05` fixes the positioning rules; `docs/06` covers
funding and the shuttle. Later measurement has superseded specific
figures in several of these, and where it has, the later document says
so explicitly — `docs/10` supersedes the `docs/01` physical envelope for
the NPU, and `docs/15` supersedes the `docs/06` tile arithmetic.

**Specification and verification (08-11)** turned the research into
something buildable. `docs/08` extracts the programmer-visible
conventions to stay close to; `docs/09` is the verification programme;
`docs/10` is the NPU specification the golden model implements;
`docs/11` is the operating manual for the whole harness and is the
document to read before running anything.

**Physical (12, 15, 18, 21)** is the evidence chain. `docs/12` brings up
the SG13G2 flow and hardens one block; `docs/15` states the pilot's die
content, pin contract and tile budget; `docs/18` hardens the same RTL on
SKY130A to separate design properties from PDK properties; `docs/21` is
the pre-silicon device datasheet that collects the pilot's
externally-visible behaviour in one place.

**Fault tolerance (16)** is the measurement that the hardening
mechanisms in the RTL actually cover the design, rather than merely
working when aimed at.

**Funding and licensing (13, 14)** are the two documents with an
external deadline and an unmade decision in them.

**Process (19)** compares this repository's CI against `gonsolo/borg`
and is where the case for this documentation site was made.

**Reviews (07, 17)** are the cross-cutting audits. `docs/07` closes the
research phase and design wave 1; `docs/17` closes design wave 2. Both
carry numbered findings with dispositions and both feed `ROADMAP.md`.
They are the fastest way to find out what is wrong with everything else.

## 4. Where to start

### 4.1 If you are evaluating the engineering

Read the two review records first — `docs/07-design-review.md` and
`docs/17-wave2-review-record.md`. They are adversarial by construction,
they cite line numbers, and they will tell you the weaknesses faster
than the documents that contain them will. Then:

1. `docs/10-npu-mvp-spec.md` — the specification, and the only place the
   update equations are normative.
2. `docs/11-verification-harness.md` — what is verified, how, and what
   each suite is entitled to claim.
3. `docs/09-formal-verification-plan.md` part C — the formal targets and
   which of them are green.
4. `docs/16-fault-injection-campaign.md` — the measured upset response,
   including the structures where the answer is bad.
5. `docs/12-sg13g2-flow-bringup.md` and
   `docs/18-cross-pdk-portability.md` — the physical results and the
   cross-PDK control.

The single most informative artifact is not a document: it is
`sw/tests/test_flow_evidence.py`, which re-reads the sign-off numbers
claimed in `docs/12` out of the run directory every time the suite runs,
so the gate is auditable rather than asserted.

### 4.2 If you are reproducing the results

Start at `docs/11-verification-harness.md`. It is the only document
written as instructions. In order:

1. Python golden-model suite — `.venv/bin/python -m pytest` from the
   repository root. 185 tests collect; at commit `fe89f0d` they ran 152
   passed, 1 skipped, and this index's link check adds 32 more
   [fact, 2026-08-26]. The one skip is an artifact test in
   `sw/tests/test_flow_evidence.py` that needs a run tree a fresh clone
   does not have.
2. cocotb suites — `make -C hw/tb TB=<block>` for `aer_fifo`, `regbank`,
   `lif`, `secded`, `tmr`, `pilot`, and `make -C hw/tb -f Makefile.scrub`
   for the scrub controller. These need `hw/.venv`, which is deliberately
   separate from the root virtualenv; `docs/11` section 3.2 explains why.
3. Formal — `make -C formal everything`. Tool discovery for the whole
   repository is in `tools.mk`.
4. Physical — `hw/openlane/run_trial.sh` and the per-target scripts under
   `hw/openlane/`; `docs/12-sg13g2-flow-bringup.md` pins the tool and PDK
   versions each result was produced with.

Everything is rootless. Nothing in this repository needs Docker,
`sudo`, or network access at run time.

### 4.3 If you are assessing this for funding

Read in this order:

1. `docs/13-nlnet-application.md` — the application package itself, with
   every form field drafted and every open decision collected in its
   section 7.
2. This document's section 2 — what exists against what is promised.
3. `docs/06-funding-and-shuttle.md` — the budget derivation and the
   shuttle logistics, noting that its tile arithmetic is superseded by
   `docs/15-pilot-tile-plan.md`.
4. `docs/14-licensing-decision.md` — the open-licensing decision, which
   is a precondition of NLnet funding and is **not yet made**.
5. `docs/05-market-positioning.md` section 4 — the rules that stop this
   project from overclaiming radiation tolerance, and against which any
   claim made to you should be checked.
6. `docs/07-design-review.md` and `docs/17-wave2-review-record.md` — the
   project's own account of its defects.

The two questions worth pressing are in section 2.2: there is no
silicon and no radiation data, and the licence is unsigned.

## 5. The documents

| Document | Purpose |
|---|---|
| `docs/00-index.md` | This page. |
| `docs/00-reference-brief.md` | GR801 public-brief summary and initial scaling observations. |
| `docs/01-reference-decomposition.md` | GR801 architecture decomposition and 28 nm to 130 nm scaling analysis. |
| `docs/02-npu-architecture.md` | Event-driven inference engine options, and the recommendation. |
| `docs/03-cpu-and-ip-survey.md` | Management CPU and interface IP survey: licensing and verification fit. |
| `docs/04-technology-and-flow.md` | 130 nm technology selection, memory strategy, flow and cost. |
| `docs/05-market-positioning.md` | Mission profile, competitive landscape, and the binding positioning rules. |
| `docs/06-funding-and-shuttle.md` | NLnet grant plan and TTIHP26b shuttle logistics. |
| `docs/07-design-review.md` | Independent review of the research phase and design wave 1. |
| `docs/08-gr801-datasheet-notes.md` | GR801/GRLIB programmer-visible conventions and a proximity checklist. |
| `docs/09-formal-verification-plan.md` | Formal verification programme: RTL formal, golden-model refinement, software track. |
| `docs/10-npu-mvp-spec.md` | NPU MVP micro-architecture specification v0.1 — normative. |
| `docs/11-verification-harness.md` | How to run and how to read every verification target in the repository. |
| `docs/12-sg13g2-flow-bringup.md` | IHP SG13G2 flow bring-up, `aer_fifo` trial harden, and the RM_IHPSG13 macro decision. |
| `docs/13-nlnet-application.md` | NLnet Restack application package, drafted field by field. |
| `docs/14-licensing-decision.md` | Open-licensing and publication decision memo — recommendation made, decision unsigned. |
| `docs/15-pilot-tile-plan.md` | Pilot die content, pin contract, tile budget and submission tree. |
| `docs/16-fault-injection-campaign.md` | Seeded upset campaign: measured outcome distribution and per-structure ranking. |
| `docs/17-wave2-review-record.md` | Independent review record for design wave 2, and the wave-3 plan. |
| `docs/18-cross-pdk-portability.md` | The same pilot RTL hardened on SKY130A, as a control on PDK-specific results. |
| `docs/19-ci-parity-borg.md` | CI parity assessment against `gonsolo/borg`'s six workflows. |
| `docs/20-reharden-and-corners.md` | Re-harden after the configuration-TMR fix, and why `PNR_CORNERS` cannot close the SKY130 slow corner. Supersedes area and timing figures in `docs/15` and `docs/18`. |
| `docs/21-pilot-datasheet.md` | Pre-silicon device datasheet for the submitted pilot. |
| `docs/22-reharden-wave5.md` | Re-harden after the wave-5 AER pointer TMR, and the tile budget it breaks. Supersedes area, utilization and timing figures in `docs/15`, `docs/18`, `docs/20` and `docs/21`; its section 6 is the location-by-location correction list. |
| `docs/23-tile-shape-decision.md` | Both twelve-tile shapes hardened and compared after `docs/22` put the design over the 4x2 budget. Decides **6x2**, on routing convergence, timing and clock skew rather than on area — both shapes clear the utilization criterion with room to spare. Records that 3x4 is not confirmed purchasable on TTIHP26b. |
| `docs/24-gate-level-simulation.md` | Gate-level simulation of the hardened netlist — the ROADMAP P1 bar item, and the direct check on the RTL-versus-netlist gap that has produced three separate defects in this project. Records which tests can run at gate level and which cannot. |
| `docs/25-sky130-6x2.md` | SKY130A at twelve tiles. Routes where 4x2 diverged, every manufacturability deck at zero on both PDKs, and the slow corner still missed — with a decomposition of the miss that supersedes the diagnosis in `docs/18`. |
| `docs/26-gate-level-fault-injection.md` | Fault injection on the hardened netlist rather than the RTL, with the validation that the method models a transient upset and not a stuck-at. 355 of 357 comparable injections agree with the RTL campaign; the two that do not are named and analysed. |
| `docs/27-reharden-wave6.md` | Re-harden after the timeout retirement and the three valid-flag rails. The netlist census guards pass by name rather than skipping, so the redundancy is confirmed present in the shipped netlist; records that the slow-corner margin has fallen to +0.32 ns — **corrected 2026-08-30: with the OCV derate `docs/28` found was never applied, that run is at -0.67 ns and does not close the slow corner**. |
| `docs/28-timing-recovery.md` | Where the slow-corner margin went and how it was recovered — and two flow defects found on the way: the OCV derate was silently zero on both PDKs, and the setup checker only ever examined the typical corner. Read this before quoting any timing figure produced before it. |
| `docs/29-queue-storage-protection.md` | One even-parity bit per queue entry, closing `evq_mem` — the last unprotected structure in the event path. Records why SECDED was deferred on codec area rather than on timing, and what parity still does not catch. |
| `docs/30-dispatcher-protection.md` | The dispatcher's five silent corruptions, and why they had to be detected rather than corrected: the replication bound proved for one bit generalises, and at two bits there are only six balanced coordinate functions, four of which the two rails already take. Two flip-flops for five records. |
| `docs/31-signoff-6x2.md` | Complete geometric and timing sign-off of the 6x2 pilot — and the finding that the submission path did not carry the settings that make it close, measured by hardening that path and watching it miss while every checker reported clean. |
| `docs/32-gate-level-refresh.md` | Gate level re-run against the current netlist: 370 of 370 comparable injections now classify identically with the RTL campaign, the new redundancy is exercised for the first time, and the one long-standing divergence is narrowed to the device boundary after its named hypothesis was tested and excluded. |
| `docs/33-rail-transform.md` | The dual-rail flags claimed two independent defences and the netlist carries one: `dfflibmap` folds the per-rail storage polarity away during technology mapping, because this library has no reset-to-1 flip-flop. The transform is measured to work where merging happens, proved unreachable at the netlist for a one-bit rail, and the three rail headers now say so. |
| `docs/regmap-npu.md` | Generated register-map documentation. Single source: `regmap/regmap.yaml`. |
| `README.md` | Project summary and repository layout. |
| `ROADMAP.md` | Phased plan with gates and external clocks. |

`sw/tests/test_doc_links.py` checks that this table names every document
in the corpus and that every cross-reference in every document names a
file that exists. A document added without an entry here fails that
test.

## 6. Counts that other documents state differently

`docs/11-verification-harness.md` opens with headline totals measured on
2026-08-25: 28 SymbiYosys tasks across five formal jobs, 109 distinct
cocotb tests across six suites, and 145 Python tests. All three were
correct on that date and all three have since been overtaken by the
`scrub` block and by wave-3 work. Re-measured on 2026-08-26 the same
quantities are 37 SymbiYosys tasks across six property sets, 129 cocotb
test functions across eight modules, and 153 collected Python tests of
which 152 pass and one skips — 185 collected once this index's own link
check is counted. **[fact]** Nothing about the verification
argument changes; only the arithmetic does. This section is a pointer,
not a correction — `docs/11` remains the authority on what each suite
means.

**Re-measured again 2026-08-29 [fact].** The 2026-08-26 formal figure
above has itself been overtaken, by the `lif_mem` property set and by
the tasks added with it. `make -C formal -n everything | grep -c
"sby -f"` now returns **45**, and the `[tasks]` sections of
`formal/*.sby` are **7** property sets, not six: `aer_fifo` 4,
`lif_ctrl` 8, `lif_mem` 8, `npu_regbank` 5, `scrub` 9, `secded` 3,
`tmr_voter` 8. The other two quantities in that line moved as well:
`grep -c '@cocotb.test' hw/tb/test_*.py` now totals **145** cocotb test
functions across the same eight modules (was 129), and
`.venv/bin/python -m pytest --collect-only -q` collects **196** Python
tests (was 185 at commit `fe89f0d`). Section 2.1's rows carry all three
new numbers; the 2026-08-26 line above is left as written because it was
correct on its date. **Collection is not execution** — the pass, skip
and fail split for the Python suite, and the pass result for the eight
formal tasks added since 2026-08-26, have not been re-run here and are
not claimed.

## 7. Reading this corpus as a site

`scripts/build_docs.py` renders every document in the table above into a
browsable, self-contained static site, resolving each bare `docs/NN`
cross-reference into a hyperlink and generating a table of contents per
document:

```
python3 scripts/build_docs.py --out _site
```

It uses pandoc when pandoc is on PATH and a built-in renderer otherwise,
and prints which one it used. `_site/` is build output and is not
tracked. `.github/workflows/docs.yml` builds the same site on every push
and uploads it as an artifact; it does not publish it, because
publication depends on `docs/14-licensing-decision.md`, which is
unsigned.
