# 13 — NLnet Restack application package

Date: 25 August 2026.
Status: submission-ready draft. Every field of the live NLnet form is
drafted here in paste-ready form. Fields that still need a decision from
the developer are marked **[D-n]** and collected in section 7.
Owner of the submission act: developer. Owner of the technical text:
engineering.

Scope: this document is the instantiation of `docs/06-funding-and-shuttle.md`
part A against the *actual* form on nlnet.nl, re-verified on 2026-08-25 by
fetching the form markup directly rather than trusting the summary in
docs/06. Where the live form disagrees with docs/06, the live form wins
and the delta is recorded in section 1.2. All positioning language obeys
the binding rules of `docs/05-market-positioning.md` section 4
(fault-tolerant wording, LEO 10-30 krad(Si) class, no claim at or above
100 krad(Si), multi-market framing, fact/estimate discipline).

Labels: **[fact]** = traceable to a cited source checked on the stated
date; **[estimate]** = inference or project judgement; **[D-n]** = open
decision for the developer.

---

## 1. What was verified on nlnet.nl, and what changed since docs/06

### 1.1 The live application form: fields and hard limits

Verified 2026-08-25 by retrieving `https://nlnet.nl/propose/` and reading
the form markup (`maxlength` attributes are the authoritative limits — the
prose on the page states none). **[fact]**

| Order | Field (form name) | Type | Hard limit | Required |
|---|---|---|---|---|
| 1 | Call (`call`) | select | — | yes |
| 2 | Name of the applicant (`requestor`) | text | 100 | no |
| 3 | Email address (`email`) | email | 100 | yes |
| 4 | Phone number (`phone`) | text | 100 | no |
| 5 | Organisation (`organization`) | text | 100 | no ("if any") |
| 6 | Country of residence (`country`) | text | 100 | no |
| 7 | Project name (`project`) | text | 100 | no |
| 8 | Website (`website`) | text | 100 | no |
| 9 | Abstract (`abstract`) | textarea | **1500** | no |
| 10 | Previous relevant experience (`experience`) | textarea | 10000 | no |
| 11 | Requested amount (`amount`) | numeric | — (placeholder "between 5000 and 50000") | no |
| 12 | Budget explanation + other funding sources (`use`) | textarea | 10000 | no |
| 13 | Comparison with existing or historical efforts (`comparison`) | textarea | 10000 | no |
| 14 | Significant technical challenges (`challenges`) | textarea | **12500** | no |
| 15 | Ecosystem and engagement (`ecosystem`) | textarea | 10000 | no |
| 16-18 | Attachments 1-3 | file | 50 MB total, HTML/PDF/ODF/plain text | no |
| 19 | Generative-AI disclosure (`used_ai`) | select | two options | **yes** |
| 20 | Prompt provenance (`ai_prompt`) + 3 file slots | textarea | 10000 | conditional |
| 21 | Privacy consent (`consent`) | checkbox | — | **yes** |
| 22 | Send me a copy (`want_copy`) | checkbox | — | pre-checked |
| 23 | OpenPGP key (`pgp`) | textarea | 10000 | no |

The call selector currently reads "There are currently no calls open".
The page states calls reopen **2026-09-03** with a deadline of
**2026-11-03, 12:00 CEST**. **[fact]**

Form guidance printed above the free-text fields, verbatim: "Please be
short and to the point in your answers; focus primarily on the what and
how, not so much on the why. Add longer descriptions as attachments."
**[fact]** The drafts in section 3 are written to that instruction: the
long-form architecture and verification material goes into attachments,
not into the textareas.

### 1.2 Deltas from docs/06 A.5 — what changed or was wrong

1. **The abstract limit is 1500 characters, not 1,200.** docs/06 A.5
   states 1,200 (sourced from a third-party applicant report). The live
   form's `maxlength` is 1500. The 1,142-character draft abstract in
   docs/06 A.8 was therefore sized against the wrong ceiling and left
   ~360 characters unused. **[fact]** The draft in section 3.4 uses the
   real budget.
2. **Three fields are not in docs/06's list at all**: technical
   challenges (12500), ecosystem and engagement (10000), and an explicit
   request for existing funding sources folded into the budget field.
   These are scored surface — the challenges field is the single largest
   field on the form and docs/06 does not mention it. **[fact]**
3. **A generative-AI disclosure is a required field.** NLnet publishes a
   policy at `https://nlnet.nl/foundation/policies/generativeAI/` which
   requires, verbatim: "If GenAI is used in the application process a
   prompt provenance log must be maintained. This log should list: the
   model used, dates and times of prompts, the prompts themselves, the
   unedited output." Non-compliance "may result in rejection of the
   proposal or ultimately in the termination of the running grant."
   **[fact]** See [D-10]; this field and any accompanying log are the
   developer's to complete.
4. **Restack now publishes its own eligibility page and guide for
   applicants** (`https://nlnet.nl/restack/eligibility/`,
   `https://nlnet.nl/restack/guideforapplicants/`). docs/06 A.2/A.3/A.5
   marked the Restack-specific rules "not yet published" and carried the
   Commons Fund rules as a proxy with **[unverified]** tags. Those tags
   can now be cleared: the Restack rules are identical in substance.
   **[fact]** Newly confirmed *for Restack*:
   - Evaluation weights 30% technical excellence/feasibility, 40%
     relevance/impact/strategic potential, 30% cost effectiveness; the
     total weighted score "has to be above 5.0 (out of 7) to pass to the
     next stage".
   - "a first proposal MAY request a grant allocation up to 50 kEuro";
     anything larger must be preceded by a successfully concluded smaller
     project. Maximum per proposal 150 kEuro; maximum per third party over
     the programme lifetime 500 kEuro.
   - Licensing: "All scientific outcomes must be published as open
     access, and any software and hardware must be published under a
     recognised open source license in its entirety."
   - "clear European Dimension" is a hard knock-out criterion in stage 1.
5. **Programme window and budget pressure.** Restack "runs between June
   1st 2026 and May 30th 2030, new calls will be announced until the
   budget of the programme has been fully allocated (**expected early
   2027**)". **[fact]** This is new information and it changes the
   calculus: the 2026-11-03 round may be one of the last with meaningful
   budget left. Waiting for a later round is not a safe default.
6. **Cadence after the transition is now known**: deadlines move to "the
   third day of every odd month"
   (`https://nlnet.nl/news/2026/20260803-phaseshift.html`). **[fact]**
   docs/06 marked this **[unverified]**.
7. **Decision lag is longer than docs/06 estimated.** The FAQ states:
   "You can expect the process to take between three and five months.
   This is counted from the date of the deadline of the open call".
   **[fact]** For 2026-11-03 that is **2027-02 to 2027-04** for the
   decision, with MoU negotiation after it — not the "~2027-01/02"
   in docs/06 A.7. The ROADMAP's "spring 2027" MoU assumption still
   holds, but with no margin; first disbursement realistically 2027-05 or
   later.
8. **Payment mechanics, verbatim from the sample MoU**
   (`https://nlnet.nl/foundation/request/sample_MoU.pdf`, retrieved and
   text-extracted 2026-08-25): "There is a donation amount attached to
   each task, which you unlock by publishing the associated results."
   Grants are structured as charitable donations; "[the grantee] is
   responsible for paying any and all taxes or other fees with regard to
   this grant". The MoU also obliges public progress reporting "every two
   months" and a "public status page for the project". **[fact]** The
   reporting obligation is an unbudgeted recurring cost — it is now a
   line item (see section 4, T5).
9. **Eligible-activity list does not name silicon fabrication or test
   equipment.** The Restack eligibility page lists research, FOSS/open
   hardware design and development, validation, formal security proofs
   and CI, documentation, standardisation, events, and "out-of-pocket
   costs for infrastructure essential to achieving the above". **[fact]**
   Shuttle tiles, boards, instrumentation and irradiation-facility time
   fall under the last category by construction, not by name. Precedent
   supports it (Chips4Makers was funded to have "a development version of
   the libre licensed Libre-SOC system-on-a-chip ... manufactured in a
   0.18um process", `https://nlnet.nl/project/Chips4Makers/` **[fact]**),
   but the radiation-campaign line is the one most likely to be
   questioned in stage 2. Mitigation: ask at an office hour before
   submitting ([D-12]).

### 1.3 Precedent correction: docs/06 A.4's "no space precedent" is wrong

docs/06 A.4 states: "no space/SpaceWire/satellite-silicon precedent was
found in the funded-projects list". That is no longer true, and the
counterexample is close to this project. **[fact, checked 2026-08-25]**

| Project | Why it matters here | URL |
|---|---|---|
| Space grade Instrumentation Amplifier ASIC (NGI0 Commons Fund, start 2026-03) | Analog front end taped out "on IHP's 130nm open source PDK"; "The INA will be made robust to high radiation environments, making it applicable to low earth orbit / high energy particle applications, where single even latch up can be problematic." Same PDK, same environment class, funded. | https://nlnet.nl/project/INA-ASIC |
| GLOW-SG13G2 (Gate Library for Open Flow — SG13G2) | Open standard-cell library and characterisation flow for exactly the PDK this project hardens on. Direct collaboration candidate. | https://nlnet.nl/project/GLOW-SG13G2 |
| Borg II (open GPU) | Reached silicon with a taped-out ASIC on IHP 130 nm — announced by NLnet as "to our knowledge the first open-source GPU design to do so". Evidence the flow closes at this scale. | https://nlnet.nl/project/Borg-GPU |
| PowerCommons | Open-toolchain synthesis flows targeting the IHP 130 nm open PDK. | https://nlnet.nl/project/PowerCommons |
| FPGA Fault Injection Testing (NGI0 Entrust, 2024-02 to 2025-05) | Fault-injection methodology funded as a first-class deliverable. | https://nlnet.nl/project/FPGA-Inject |

Consequences for the application:

- The framing advice in docs/06 A.4 ("do not lean on a space fund
  framing") stands, but for a different reason: not because space is
  unprecedented, but because Restack funds *building blocks for the open
  internet stack*, and the winning frame is "open, auditable
  fault-tolerance and event-driven inference IP on a European open PDK"
  with satellites as the lead application.
- The INA-ASIC project should be named in the comparison field as a
  complementary effort with an explicit offer to coordinate — NLnet's
  stage-2 questions include "have you considered collaborating with
  complementary effort Z" verbatim
  (`https://nlnet.nl/restack/guideforapplicants/`). **[fact]**
- The precedent table in docs/06 A.4 needs the same correction. That file
  is owned by the integrator; the correction is reported, not applied
  here.

### 1.4 Re-verification actions when the call opens

The form was inspected with **no call open**. Field sets and limits can
be call-specific. Before writing into the live form on or after
2026-09-03: re-fetch the page, re-read every `maxlength`, and confirm the
abstract ceiling is still 1500 and the field list unchanged. If the
abstract limit drops back to 1200, cut the two sentences flagged in
section 3.4. Owner: developer. **[D-13]**

---

## 2. Funded scope: what this grant actually buys

Stated plainly, because the review team does "independent verification of
facts, methods and claims" **[fact]** and an overclaimed scope is the
easiest way to fail stage 2:

- ROADMAP P3 rolls up **1015-1895 h** for the full SoC **[estimate,
  ROADMAP section 2]**. At any defensible rate, that is far beyond a
  first Restack proposal's 50 kEUR ceiling.
- Therefore the funded scope is **a building block set, not the SoC**:
  the event-driven inference core, the fault-tolerance IP set, the
  reproducible open flow that hardens them on SG13G2, silicon on a
  community shuttle, bring-up against a published test suite, and the
  first public total-ionising-dose data for `sg13g2_stdcell`-based
  digital logic.
- The full SoC integration (RV32 management subsystem, SpaceWire codec,
  CAN, the rest of the interface set) continues on the ROADMAP outside
  the grant and is described in the application as context, not as a
  deliverable.

This is also the framing that matches Restack's own words ("technology
building blocks", "libre chips") and keeps every milestone small enough
to be verifiable — which is what the MoU annex format rewards.

### 2.1 European dimension — the stage-1 knock-out

"clear European Dimension" is a hard eligibility criterion, checked
before any scoring **[fact]**. Türkiye is associated to Horizon Europe
for 2021-2027, which puts the applicant in the priority group rather
than the exception path (docs/06 A.3) **[fact]**, so the criterion is
satisfied on residence alone. The substantive case is stronger and is
carried by the ecosystem field: the target PDK is IHP's, a German
Leibniz institute's; fabrication is in Frankfurt (Oder); the flow is
LibreLane/OpenROAD; the nearest collaborators (GLOW-SG13G2, the
space-grade INA ASIC) are NLnet-funded European efforts on the same
process; and the output is a building block for the European
open-silicon commons. No sentence in the application needs to argue the
point defensively.

---

## 3. Field drafts (paste-ready)

Convention: text inside a `field:<name>` marker block is exactly what
gets pasted into the corresponding form field. Character counts for every
block are in section 9 and are reproducible with the command given there.
The paste blocks are ASCII except for a single "ü" in "Türkiye" in the
budget field; every character used is one UTF-16 code unit, which is the
unit an HTML `maxlength` counts, so the section 9 numbers are the numbers
the form will enforce.

### 3.1 Contact information

| Field | Value | Status |
|---|---|---|
| Name of the applicant | — | **[D-1]** legal name or alias. The FAQ states: "You don't need to reveal your real name to us, prior to the project being granted." **[fact]** Default recommendation: legal name, because the prior-work evidence (a shipped Tiny Tapeout design, public repositories) is attached to it and anonymity would break the strongest part of the experience field. |
| Email address | — | **[D-2]** a project address, not a personal one, so that MoU correspondence is separable. |
| Phone number | — | **[D-3]** international format required by the placeholder ("+"). |
| Organisation | — | **[D-4]** blank (individual) vs a registered entity. The FAQ: "No, you don't. You can apply as an individual ... It is not an issue if you have not yet established the entity when you apply." **[fact]** Tax handling differs (section 6, R-7); the recommendation is to apply as an individual and decide the entity question separately. |
| Country of residence | Türkiye | Fixed. Türkiye is associated to Horizon Europe for 2021-2027, so the applicant sits in the priority group, not the exception path (docs/06 A.3 sources, checked 2026-08-24). **[fact]** |

### 3.2 Project name (limit 100)

**[D-5]** — pick one. Recommendation: option A. It contains the two words
the fund cares about ("open", "fault-tolerant") and the application
domain, and it is not a claim.

| Option | Text | Note |
|---|---|---|
| A (recommended) | `Open fault-tolerant neuromorphic inference IP for small satellites` | 66 characters. Says building block, not SoC — matches the funded scope of section 2. |
| B | `Neuromorphic Space SoC` | Matches the repository name, but promises the whole SoC. |
| C | `SG13G2 open fault-tolerance and event-driven inference IP set` | Most precise, least legible to a non-specialist reviewer. |

### 3.3 Website (limit 100)

**[D-6]** — blocked on `docs/14-licensing-decision.md`. The field is
optional and there is no requirement to be public at application time
(see docs/14 section 3), but leaving it empty removes the reviewer's
cheapest route to the prior-work evidence. Options, in order of
preference: (a) public repository URL if the docs/14 recommendation is
accepted; (b) a single static project page listing the public artefacts;
(c) the existing public Tiny Tapeout project page for
`tt-um-lif-crossbar` as evidence of prior work; (d) blank.

### 3.4 Abstract (limit 1500)

Positioning check applied to every sentence: "fault-tolerant" is used and
"rad-hard" is not; the total-dose class is stated as LEO 10-30 krad(Si)
and no figure at or above 100 krad(Si) appears; the claim about GR801 is
the sourced one from docs/05 section 1 (proprietary, 28 nm FDSOI,
institutional price class), not a superlative that a reviewer could
falsify. The phrase "clean-room" from the docs/06 A.8 draft has been
**removed**: docs/02 open question 2 (reuse of Solderpad-licensed
tinyODIN/ODIN RTL versus a fully independent implementation) is still
open, so "clean-room" is not yet a fact this project can assert. See
[D-14].

<!-- field:abstract:begin -->
```text
Small satellites increasingly need on-board AI inference, but the reference device in this class, Frontgrade Gaisler's GR801, is proprietary, built on 28 nm FDSOI, and priced for institutional missions. This project builds an open, auditable building block for event-driven neural inference on CubeSat-class hardware: a spiking neural network core with low-bit quantized weights and an ECC-protected synapse memory, plus the fault-tolerance IP it needs to survive orbit - SECDED codec, TMR voter bank, memory scrubber, fault counters - hardened by architecture rather than by a proprietary process. Everything is published under free licenses: the RTL, the bit-exact golden model that serves as its executable specification, the cocotb regressions and SymbiYosys proofs, and a reproducible RTL-to-GDS flow on IHP's open SG13G2 130 nm PDK. The design goes to silicon on an affordable community shuttle, is brought up against the same published test suite, and is then pre-screened for total-ionising-dose behaviour in the LEO 10-30 krad(Si) class - a measurement for which the open-silicon community has no public data on this PDK today. The outcome is a reusable European open-silicon building block plus the evidence that it works: RTL, proofs, flow scripts, bring-up software and measured radiation data, so that any team can fly inspectable AI hardware instead of a black box.
```
<!-- field:abstract:end -->

If the limit reverts to 1200 ([D-13]), delete the sentence beginning "The
design goes to silicon" and fold "silicon on a community shuttle" into
the preceding sentence.

### 3.5 Previous relevant experience (limit 10000)

Every claim below is checkable, which is the point — stage 2 verifies.
Items marked [D-7] depend on what is public at submission time
(docs/14).

<!-- field:experience:begin -->
```text
I design fault-tolerant digital silicon with open tools, solo, and I ship it.

Silicon: tt-um-lif-crossbar, an 8x8 leaky-integrate-and-fire neuron crossbar on a 2x2 Tiny Tapeout tile in SkyWater 130 nm, taken through the open RTL-to-GDS flow and verified at 70.66% classification accuracy on the target task before submission. That design is the direct ancestor of the inference core proposed here: the neuron update datapath and the crossbar accumulation logic carry over.

Flow: I run LibreLane/OpenROAD, Yosys, Icarus/cocotb, SymbiYosys and KLayout rootless, without containers or root privileges, on my own machine. Nothing in this proposal depends on a tool I have not already driven to a signed-off result.

Method: I work spec-first. Before RTL exists there is a bit-exact integer golden model in Python that is the executable specification, a single-source register map that generates the Verilog header, the documentation and the model bindings from one YAML file, and a pytest suite that fails if any of them drift apart. For this project that harness is already live: the register map generator with its sync tests, a 512-neuron inference-core golden model with per-equation tests, an AER event-queue RTL block with a cocotb regression, and a SymbiYosys proof of that block's safety properties (no overflow or underflow, count coherent with pointers, order preserved, no loss or duplication) that passes unbounded induction.

Assurance: I wrote a formal verification programme for this SoC modelled on the seL4 proof stack - properties-as-specification per block, golden-model refinement, and an explicit assumption ledger recording what the proofs do not cover. Ten prioritised proof targets are defined; the first is green in CI.

Review discipline: the research phase of this project was put through an independent design review that produced twenty confirmed findings, including three misattributed radiation citations in my own funding material. All of them were corrected before this application was written, and the corrections are in the repository history. I would rather find those myself than have your reviewers find them.

Adjacent work: a 130 nm-class INT8 systolic accelerator MVP for telemetry anomaly detection, and prior physical-design work including MBIST, boundary scan and multi-corner static timing on other programmes.
```
<!-- field:experience:end -->

**[D-7]** — before pasting: (a) confirm the 70.66% figure and the
"before submission" wording against the tt-um-lif-crossbar record;
(b) add public URLs for the Tiny Tapeout design and, if docs/14 lands as
recommended, for this repository; (c) decide whether to name the adjacent
programmes explicitly or keep them generic as above.

### 3.6 Requested amount

**EUR 27,500.** Inside the 5,000-50,000 window; inside the
first-proposal ceiling of 50 kEUR **[fact]**. Consistent with the docs/06
A.8 sketch total, re-derived line by line in section 4 with explicit
rates, because the form says "Make rates explicit".

### 3.7 Budget explanation and other funding sources (limit 10000)

<!-- field:use:begin -->
```text
Rate: all developer time is budgeted at EUR 40/hour. That is a modest rate for verified digital design work in Europe and it is the same rate across every task; 410 hours of work are requested in total, alongside EUR 11,100 of out-of-pocket costs that cannot be substituted by effort.

Developer time - EUR 16,400 for 410 hours

T1. Event-driven inference core RTL, bit-exact against the published golden model (120 h, EUR 4,800). The core, its synapse memory interface, the AER event queues and the multi-pass sequencer, verified in lockstep against the Python model equation by equation.

T2. Fault-tolerance IP set (90 h, EUR 3,600). SECDED (72,64) weight-SRAM codec, TMR voter bank with a masking proof, scrub controller, fault counters. Each block gets a cocotb regression and a SymbiYosys proof; the SECDED proof is exhaustive over the full input space at depth 1, and the voter masking theorem is proven with a symbolic fault on one replica.

T3. Reproducible open hardening flow on IHP SG13G2 (80 h, EUR 3,200). LibreLane configuration, foundry SRAM macro integration with the ECC wrapper, DRC/LVS/STA closure, and a rootless build that a third party can re-run to reproduce the same GDS.

T4. Silicon bring-up (70 h, EUR 2,800). Host software against the register map, silicon-versus-model lockstep campaign on the fabricated part, fault-tolerance demonstrator exercise, published results memo.

T5. Documentation, dataset publication and public reporting (50 h, EUR 2,000). Integration guide, fault-tolerance report, the radiation dataset with its analysis scripts, and the two-monthly public progress reports and status page the MoU requires.

Out-of-pocket costs - EUR 11,100

H1. Shuttle tiles for the follow-up run: 32 tiles at EUR 70 = EUR 2,240.
H2. Development kits and carrier boards, 2 units at EUR 150 = EUR 300.
H3. Custom breakout and test PCB, two revisions, fabrication, assembly and components = EUR 800.
H4. Bring-up instrumentation: FPGA host board EUR 400, programmable supply with current logging EUR 900, logic analyser EUR 250, cabling and adapters EUR 150 = EUR 1,700.
H5. Total-ionising-dose pre-screen: Co-60 facility time EUR 3,500, test-fixture modification and spare parts EUR 400, shipping, customs and dosimetry EUR 900 = EUR 4,800.
H6. Import duties and shipping on hardware into Türkiye = EUR 760.
H7. Travel and admission to one European open-silicon event to present the results = EUR 500.

Total: EUR 16,400 + EUR 11,100 = EUR 27,500.

Other funding sources, past and present: none. This project has received no grant, contract or institutional funding to date. The research phase, the design work completed so far and the first community shuttle entry are self-funded out of pocket, and remain so whether or not this application succeeds. There is no co-funding to declare and no overlap with any other grant.

Note on cash flow: NLnet pays per completed and published milestone, so every item above is spent before it is reimbursed. The milestone plan is therefore ordered so that the largest out-of-pocket item, the irradiation campaign, sits after two smaller milestones have already been paid.
```
<!-- field:use:end -->

**[D-8]** — the EUR 40/hour rate is a placeholder that must be confirmed
or replaced by the developer before submission. It is the single number
stage 2 is most likely to interrogate ("the rate you have applied for
task B is very high compared to the perceived value of that task. Can you
explain, or would you like to reconsider?" is a verbatim example question
**[fact]**). Changing the rate changes the hours, not the total, unless
the scope moves with it.

**[D-15]** — H5 (EUR 4,800) rests on an unquoted facility price. docs/06
action item 7 already owns "identify a Co-60 TID facility and obtain
quotes". A real quote must replace the estimate before submission, or the
line must be re-scoped.

### 3.8 Comparison with existing or historical efforts (limit 10000)

<!-- field:comparison:begin -->
```text
Proprietary reference point, stated honestly. Frontgrade Gaisler's GR801 is the device this project is measured against: a radiation-hardened SoC on 28 nm FDSOI pairing a fault-tolerant NOEL-V RISC-V core with licensed BrainChip Akida neuromorphic IP, under development since the April 2026 product brief. GR801 is better than this project on almost every technical axis: an FDSOI platform with intrinsic latch-up immunity, 11.2 MB of on-chip SRAM, a SpaceWire router, PCIe and Gigabit Ethernet, a formal qualification path, and an institutional sales channel. I am not proposing to compete with it and I will not claim to. What GR801 structurally cannot do is let a mission integrator read the RTL, re-run the verification suite, or reproduce the fault-tolerance evidence, and it will not be affordable to a university CubeSat programme. Those two gaps are the entire reason for this project. The same holds for BrainChip's Akida silicon, which has flown in low Earth orbit as an unrated commercial part, and for the rest of the space edge-AI field (Microchip PIC64-HPSC, AMD Versal XQR, Teledyne e2v QLS1046-Space): all proprietary, none publishing RTL or fault-injection data.

Open spiking-neural-network hardware. ODIN and tinyODIN (UCLouvain) and ReckOn are the open reference designs in this space, released under Solderpad. They are excellent microarchitectures and tinyODIN is the reference this project verifies its own core against. What they are not: fault-tolerant (no ECC, no TMR, no scrubbing, no fault counters), not integrated into a system with a management processor and a documented register map, not taken through an open PDK to characterised silicon, and not accompanied by any radiation data. Research platforms such as Intel Loihi and SpiNNaker are not open silicon at all. The delta this project adds is the hardening layer, the assurance evidence, and the measurement.

NLnet-funded open-silicon efforts. Libre-SOC is the closest in ambition - a fully open SoC, taped out at 180 nm - but it is a general-purpose 64-bit application processor with no fault tolerance and no space-relevant interfaces; the two projects do not overlap in scope, and its precedent is that open SoC work of this shape can be delivered. Chips4Makers contributed libre standard cells and the 0.18 um manufacturing of the Libre-SOC test chip; Coriolis2, LunaPnR and Coloquinte build the layout tooling; GLOW-SG13G2 is building an open standard-cell library for exactly the IHP SG13G2 process this project hardens on. I am a consumer of that layer, not a competitor to it, and GLOW-SG13G2 is a direct collaboration opportunity: a fault-tolerant digital design is a demanding customer for a new cell library and I can feed characterisation results back. FABulous Demo SoC delivers an open eFPGA fabric with a RISC-V SoC - a different compute model, reconfigurable rather than fixed-function event-driven, and without a hardening story. PowerCommons targets the same IHP open PDK with open synthesis flows, and Borg II has already reached silicon on IHP 130 nm, which is useful evidence that this flow closes.

Closest funded precedent. The Space grade Instrumentation Amplifier ASIC project is building a programmable-gain instrumentation amplifier on IHP's 130 nm open PDK, made robust for low Earth orbit and high-energy-particle environments. That is the analog sensing front end of the same signal chain whose digital inference back end I am proposing. The two are complementary rather than overlapping, and I would like to coordinate: shared irradiation campaigns are dramatically cheaper per part than separate ones, and a common test-fixture and dose-reporting convention would make both datasets comparable.

Prior art of my own. tt-um-lif-crossbar, my 8x8 LIF crossbar on SkyWater 130 nm through Tiny Tapeout, is the ancestor of the core proposed here. This project is what happens when that tile grows a fault-tolerance layer, a formal verification programme, an open flow on a European PDK, and a measurement campaign.

Summary of the gap. There is open neuromorphic hardware, there is open fault-tolerance research, there are open flows and open PDKs, and there is proprietary radiation-hardened neuromorphic silicon. There is no open, fault-tolerant, event-driven inference block with published proofs, published flow scripts and published radiation data. That is what this proposal delivers.
```
<!-- field:comparison:end -->

### 3.9 Significant technical challenges (limit 12500)

The largest field on the form and the one docs/06 missed entirely. It is
also where the honest engineering risks belong; stage 2 asks "how will
you approach complicating factor X" **[fact]**.

<!-- field:challenges:begin -->
```text
1. Integrating the foundry SRAM macro with an ECC wrapper on an open PDK. The IHP open PDK ships compiled RM_IHPSG13 macros, and Tiny Tapeout's own documentation warns that "integrating the IHP SRAM macro at this stage is not trivial". The failure mode is not functional, it is signoff: LVS and GDS merge problems around hard macros are exactly the class of issue that consumes weeks at tapeout time. Approach: the macro plus its ECC wrapper is closed through DRC and LVS in the local flow as a standalone experiment against a fixed calendar gate, before any schedule depends on it, with a flip-flop and latch-based weight storage fallback that removes the macro from the critical path entirely. The fallback costs capacity, not correctness.

2. The open PDK is a preview, not a production kit. IHP describes the current open-source content as a preview that is not intended for production use, while the underlying SG13G2 process and the commercial PDK are manufacturing-proven. That gap is a real risk to any signoff claim. Approach: pin an exact PDK release, record the pin in the repository, re-run the whole flow from a clean checkout in CI so that any drift shows up as a diff rather than as a surprise, and report upstream anything that does not reproduce.

3. Proving what is actually load-bearing rather than what is easy to prove. The properties that matter for a part in orbit are single-event-upset recovery properties: that any control state machine, started from an arbitrary corrupted state, returns to a legal state within a bounded number of cycles without violating any interface contract; that a TMR voter masks any single corrupted replica; that a SECDED codec corrects every single-bit error and never silently miscorrects a double-bit error. Approach: unconstrained-initial-state induction for the recovery properties, exhaustive bounded proof over fully symbolic data with a weight-constrained symbolic error mask for the codec, and a symbolic single-replica fault for the voter. Where induction does not close, the invariant is strengthened rather than the property weakened, and anything that remains bounded is recorded as bounded in an explicit assumption ledger that ships with the proofs.

4. Keeping the specification, the model, the register map and the RTL in provable agreement. A bit-exact golden model is only a specification if nothing can drift away from it silently. Approach: one YAML register map generating the documentation, the Verilog header and the software bindings, with a test that fails if any generated artefact is stale; and a lockstep harness that runs the RTL and the model on the same stimulus and compares every architecturally visible value.

5. Observing a fault-tolerant part through a 24-pin community-shuttle interface. The shuttle mux gives 8 inputs, 8 outputs and 8 bidirectional pins - enough to run the part, not obviously enough to observe corrected-error counts, scrub progress, voter disagreements and neuron state during an irradiation run. Approach: design the observability first, not last: a compact serial telemetry channel that streams the fault counters and a selectable internal state window continuously, sized so that the radiation campaign reads real internal behaviour rather than a pass/fail light.

6. Getting radiation data that is worth publishing. Bulk 130 nm CMOS logic carries no platform-level latch-up or total-dose guarantee, and the encouraging published numbers for this technology family come from its rad-hard sibling library, not from the open standard cells. Approach: state that distinction plainly in every published document; design the campaign to answer a narrow, honest question - how does this specific digital design in this specific open standard-cell library behave under total ionising dose in the LEO 10-30 krad(Si) class - with dose steps, in-situ functional test, and full publication of the fixture, the procedure and the raw data including any null results. The value to the commons is the method and the dataset, not a rating.

7. Clock-domain crossings on the event interfaces. Address-event traffic crosses between the sensor-side and core-side domains, and lost or duplicated events are silent failures that no functional test reliably catches. Approach: gray-coded pointer proofs, multiclock bounded model checking across symbolic clock ratios, and a structural lint gate that fails the build on any unsynchronised crossing.

8. Doing this solo without the schedule collapsing. The full system this block belongs to is over a thousand hours of work and I am one person. Approach: the funded scope is deliberately a building block with independently valuable milestones, each of which is publishable on its own. If the later milestones slip, the earlier ones are still standing, published, and useful to someone else.
```
<!-- field:challenges:end -->

### 3.10 Ecosystem and engagement (limit 10000)

<!-- field:ecosystem:begin -->
```text
Upstream. The design sits on IHP's open SG13G2 PDK and the LibreLane/OpenROAD flow, and it is a demanding user of both: hard macros, ECC wrappers, multi-corner timing and a fault-tolerance structure that resists the optimiser's instinct to merge redundant logic. Every reproducible defect found goes upstream as an issue with a minimal test case - to IHP-Open-PDK, to LibreLane, and to Yosys or SymbiYosys where the proofs hit tool limits. Preventing triple-modular-redundancy structures from being optimised away is a shared problem for every open fault-tolerant design and the results belong upstream, not in my repository.

Sideways. GLOW-SG13G2 is building an open cell library for the same process; a hardened digital design is a useful stress case and I will feed characterisation and timing results back. The Space grade Instrumentation Amplifier ASIC project targets the same PDK for the same environment class, and I will propose a shared irradiation campaign and a common dose-reporting convention so that the two datasets are comparable rather than incommensurable. Tiny Tapeout is the vehicle that makes silicon affordable for this work at all, and every design I submit stays in its educational catalogue as a worked example of ECC, TMR and scrubbing that students can read.

Downstream. The intended users are university CubeSat programmes, small satellite integrators, and any harsh-environment embedded project that needs better-than-commercial fault behaviour without a qualification budget: industrial monitoring, high-energy-physics instrumentation, medical radiation environments. What they get is not a datasheet claim but the evidence: RTL, the executable specification, the proofs and their assumption ledger, the flow scripts that reproduce the layout, the bring-up software, and the raw radiation data. A block that can be audited is a block a mission can defend to its own reviewers.

Publication and promotion. Everything lands in a public repository under free licenses as it is produced, not in a drop at the end. A public status page and progress reports every two months, as the MoU requires. The radiation dataset is published with its analysis scripts and its fixture description, because there is no public total-ionising-dose data for digital logic in this open PDK today and that absence is itself a barrier to everyone else. I will present results at a European open-silicon event - FOSDEM, ORConf or an equivalent - and write the integration guide for someone who has never used an event-driven inference engine before.

Standards and conventions. The spacecraft-side interfaces follow the published ECSS SpaceWire specification, and the programmer-visible conventions deliberately stay close to the widely used ones in this domain so that existing flight software habits transfer, with every deviation documented rather than silently introduced.

Sustainability. This work is a building block, so its future does not depend on my continued attention: the licenses permit anyone to fork, extend and manufacture it, and the verification suite and flow scripts are what make that practical rather than theoretical. My own path forward is fault-tolerant silicon design and services around it, and an open, audited, silicon-proven IP set is the asset that makes that credible - which means my commercial interest and the commons interest point in the same direction.
```
<!-- field:ecosystem:end -->

### 3.11 Attachments

**[D-9]** — up to three files, 50 MB total, HTML/PDF/ODF/plain text
**[fact]**. Recommended set:

1. **Architecture and verification outline** (PDF, ~8-12 pages): the
   inference-core micro-architecture from `docs/10-npu-mvp-spec.md`, the
   fault-tolerance IP set, the ten formal targets from
   `docs/09-formal-verification-plan.md` part C, and the assumption
   ledger. This is where the "why" that the form tells you to keep out of
   the textareas goes.
2. **Budget and milestone plan** (PDF, 2 pages): sections 4 and 5 of this
   document, in the MoU annex format so it can be lifted directly into
   Annex I if selected.
3. **Evidence pack** (PDF, 2-4 pages): the SymbiYosys PASS output for the
   proven block, the cocotb regression summary, the register-map sync test
   output, and the prior Tiny Tapeout result.

None of these exist as PDFs yet. Producing them is ~6-10 h **[estimate]**
and must be scheduled before 2026-10-27 (section 8).

### 3.12 Generative-AI disclosure

**[D-10]** — required select field with two options: "I did not use
generative AI in writing this proposal" and "I have used generative AI in
writing this proposal". If the second is selected, NLnet's policy
requires a prompt provenance log listing the model, the dates and times
of prompts, the prompts themselves and the unedited output, submitted in
the accompanying text field or as attachments **[fact]**. The answer and
any log are the developer's to provide; this document records the
requirement only. Note that the policy makes non-compliance grounds for
rejection or termination, so the answer must be accurate.

### 3.13 Consent and PGP

- Privacy consent checkbox: required, must be ticked. **[fact]**
- "Send me a copy": pre-checked; leave it checked — the emailed copy is
  the only record of exactly what was submitted.
- OpenPGP key: optional. **[D-11]** — if supplied, the placeholder warns
  the key must be valid for at least three months after the deadline.

---

## 4. Budget breakdown

Rate: EUR 40/hour **[D-8]**, uniform across tasks. Totals in EUR.

### 4.1 Developer time — 410 h, EUR 16,400

| ID | Task | Hours | EUR | Grounding |
|---|---|---|---|---|
| T1 | Inference core RTL bit-exact to the golden model (core datapath, synapse memory interface, AER queues, multi-pass sequencer) | 120 | 4,800 | ROADMAP P3 item 1 estimates 200-350 h for the full NPU RTL; T1 is the core subset, the rest continues unfunded **[estimate]** |
| T2 | Fault-tolerance IP set: SECDED codec, TMR voter bank, scrub controller, fault counters — RTL, cocotb, formal | 90 | 3,600 | docs/09 C.3 priority rows 2-5 (SECDED, TMR voter, CDC, FSM any-state recovery) sum to 42-84 h of proof work alone; the balance is RTL and regression **[estimate]** |
| T3 | Reproducible SG13G2 hardening flow incl. SRAM macro + ECC wrapper signoff | 80 | 3,200 | docs/06 B.6.1 puts macro integration at 25-50 h; plus flow, CI and reproducibility **[estimate]** |
| T4 | Silicon bring-up: host software, silicon-vs-model lockstep, demonstrator exercise, results memo | 70 | 2,800 | ROADMAP P4 **[estimate]** |
| T5 | Documentation, dataset publication, two-monthly public reporting over the grant period | 50 | 2,000 | MoU reporting obligation, section 1.2 item 8 **[fact for the obligation, estimate for the hours]** |
| | **Subtotal** | **410** | **16,400** | |

### 4.2 Out-of-pocket — EUR 11,100

| ID | Item | Basis | EUR |
|---|---|---|---|
| H1 | Shuttle tiles, follow-up run | 32 x EUR 70/tile (docs/06 B.2 **[fact]**, re-confirm in the calculator) | 2,240 |
| H2 | Development kits / carrier boards | 2 x EUR 150 **[estimate]** | 300 |
| H3 | Custom breakout and test PCB | 2 revisions, fab + assembly + components **[estimate]** | 800 |
| H4 | Bring-up instrumentation | FPGA host board 400, programmable supply with current logging 900, logic analyser 250, cabling 150 **[estimate]** | 1,700 |
| H5 | TID pre-screen campaign | Co-60 facility time 3,500 **[estimate, quote pending — D-15]**, fixture mods and spares 400, shipping/customs/dosimetry 900 | 4,800 |
| H6 | Import duties and shipping into Türkiye | ~15% of H1-H4 **[estimate]** | 760 |
| H7 | One European open-silicon event (admission + travel + subsistence) | Explicitly eligible per the Restack activity list **[fact]** | 500 |
| | **Subtotal** | | **11,100** |

### 4.3 Total

**EUR 16,400 + EUR 11,100 = EUR 27,500.** Matches the docs/06 A.8 sketch
total; the internal distribution differs because the scope is now the
building-block slice of section 2 rather than the whole SoC, and because
the reporting obligation and the import/shipping costs are now
line items instead of being invisible.

Arithmetic check: 4,800 + 3,600 + 3,200 + 2,800 + 2,000 = 16,400.
2,240 + 300 + 800 + 1,700 + 4,800 + 760 + 500 = 11,100. Sum 27,500.

---

## 5. Milestone plan, mapped to the ROADMAP gates

MoU format: numbered tasks, each with an amount unlocked by publishing
the associated results **[fact]**. Every milestone below is publishable
standalone, so a slip in a later milestone does not strand an earlier one.

| M | Milestone (published artefact) | Unlocks | ROADMAP gate | Target |
|---|---|---|---|---|
| M1 | Inference core RTL public, bit-exact against the published golden model, cocotb lockstep green in CI | T1 = 4,800 | P3 workstream 1, feeds G3 | MoU + 3 months |
| M2 | Fault-tolerance IP set public with its SymbiYosys proofs and the assumption ledger; SECDED exhaustive result and TMR masking theorem reproducible from the repository | T2 = 3,600 | docs/09 C.3 rows 2-5, feeds G3 | MoU + 5 months |
| M3 | Reproducible SG13G2 hardening flow public (a clean checkout reproduces the GDS); design submitted to the shuttle | T3 + H1 = 5,440 | P5 shuttle entry, gated per docs/06 B.6.2 | MoU + 8 months |
| M4 | Silicon bring-up report: silicon-vs-model lockstep results, fault-tolerance demonstrator behaviour, flow lessons; bring-up software public | T4 + H2 + H3 + H4 = 5,600 | G4 | after boards arrive |
| M5 | Radiation pre-screen dataset and report public, including fixture, procedure, raw data and null results | H5 = 4,800 | P5 pre-screen | M4 + 3 months |
| M6 | Integration guide, dataset analysis scripts, final documentation set; results presented at a European open-silicon event | T5 + H6 + H7 = 3,260 | closes the funded scope | M5 + 2 months |

Sum: 4,800 + 3,600 + 5,440 + 5,600 + 4,800 + 3,260 = **27,500**.

Ordering rationale: the two cheapest, most certain milestones come first
so that some cash has arrived before the large out-of-pocket items (H1 at
M3, H5 at M5) have to be spent. Calendar targets are relative to MoU
signature rather than absolute, because the decision date itself is a
3-5 month window (section 1.2 item 7) and the silicon dates depend on a
shuttle whose schedule the project does not control.

**[D-16]** — M3 and M4 depend on a shuttle run whose date is not yet
announced (docs/06 B.6.2 gates the follow-up run on TTIHP27b or an IHP
MPW slot). Decide before submission whether to name a specific shuttle in
the MoU annex or to phrase the milestone as "submitted to the next
available IHP-process shuttle". Recommendation: the latter — naming a
shuttle that then slips converts a schedule risk into a contractual one.

---

## 6. Risk register

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-1 | Application not funded | Medium-high (competitive fund, cut-off depends on round quality **[estimate]**) | Project continues self-funded at ROADMAP pace | Scope is already deliverable without the grant, just slower; the fund's cadence allows re-submission on the third of any odd month |
| R-2 | Restack budget exhausted before a later round ("expected early 2027" **[fact]**) | Medium | No second chance in this programme | Submit into the 2026-11-03 round, not a later one |
| R-3 | Radiation-campaign line challenged as an ineligible cost | Medium | EUR 4,800 removed from the budget | Ask at an office hour before submitting ([D-12]); if it will not fly, re-scope M5 to a smaller in-house SEU fault-injection campaign and reduce the ask accordingly |
| R-4 | Cash-flow: everything is spent before it is reimbursed | High (structural — no upfront payment **[fact]**) | ~EUR 11,100 of personal exposure before the last milestone | Milestone ordering (section 5); H5 deferred behind three paid milestones |
| R-5 | Shuttle slip pushes M3-M6 beyond the MoU window | Medium | Milestones unpaid or renegotiated | Donations "may be claimed up to the reserved amount within a maximum of six months after the proposed end of the project" **[fact, sample MoU]**; propose end dates with that margin, and do not name a specific shuttle ([D-16]) |
| R-6 | SRAM macro integration does not close on the open PDK | Medium (docs/04 calls it the primary fallback trigger) | T3 and M3 slip | Flip-flop/latch weight-storage fallback keeps the core deliverable; the macro becomes a stretch, not a dependency |
| R-7 | Tax treatment of the donation in Türkiye | Certain to need handling | Effective value of the grant reduced | The grantee "is responsible for paying any and all taxes" **[fact, sample MoU]**; obtain local advice before signing, not after |
| R-8 | Publication obligation collides with the current private-repo posture | Certain | Blocks MoU signature, not submission | `docs/14-licensing-decision.md` — must be signed off before the application is sent |
| R-9 | A claim in the application fails stage-2 verification | Low if disciplined | Score damage or rejection | Every figure here is tagged fact or estimate and traceable; the docs/07 review already removed three misattributed radiation citations from the funding material; do not reintroduce any B.5 text that has not been corrected |
| R-10 | Positioning language drifts above the export-safe threshold in the public application | Low | Serious and irreversible once submitted and published | docs/05 section 4 rules applied sentence by sentence in section 3; re-check at final review ([D-17]) |

---

## 7. Open decisions

| ID | Decision | Owner | Needed by |
|---|---|---|---|
| D-1 | Applicant name: legal name or alias | developer | 2026-10-27 |
| D-2 | Contact email address | developer | 2026-10-27 |
| D-3 | Phone number | developer | 2026-10-27 |
| D-4 | Apply as individual or via an entity | developer | 2026-10-27 |
| D-5 | Project name (recommendation: option A) | developer | 2026-09-30 |
| D-6 | Website field value — depends on docs/14 | developer | 2026-10-15 |
| D-7 | Experience field: confirm the 70.66% figure, add public URLs, decide how explicitly to name adjacent programmes | developer | 2026-10-15 |
| D-8 | Confirm or replace the EUR 40/hour rate | developer | 2026-09-30 |
| D-9 | Produce the three attachments | engineering | 2026-10-27 |
| D-10 | Generative-AI disclosure answer and, if applicable, the provenance log | developer | at submission |
| D-11 | Supply an OpenPGP key or not | developer | at submission |
| D-12 | Ask the office hour whether irradiation-facility time and instrumentation are eligible out-of-pocket costs | developer | 2026-09-30 (one office hour is scheduled for 2026-08-26 16:00 CEST in NLnet's Matrix room **[fact]**; further dates at `https://nlnet.nl/officehour/`) |
| D-13 | Re-verify the form fields and limits after the call opens | developer | 2026-09-03 |
| D-14 | Resolve docs/02 open question 2 (Solderpad RTL reuse vs independent implementation) — determines whether the word "clean-room" may be used at all | developer | 2026-10-15 |
| D-15 | Obtain a real Co-60 facility quote to replace the H5 estimate | developer | 2026-10-15 |
| D-16 | Name a specific shuttle in the milestone plan, or keep it generic | developer | 2026-10-27 |
| D-17 | Final positioning-language pass against docs/05 section 4 before submitting | developer | 2026-10-27 |

---

## 8. Submission checklist and dates

| Date | Action | Owner |
|---|---|---|
| 2026-08-26 | Office hour (16:00 CEST, Matrix room) — put the eligibility question from D-12 to NLnet | developer |
| 2026-09-03 | Call opens. Re-fetch the form, re-verify fields and limits (D-13), select the Restack call | developer |
| 2026-09-30 | D-5, D-8, D-12 closed | developer |
| 2026-10-15 | D-6, D-7, D-14, D-15 closed; docs/14 signed off | developer |
| 2026-10-20 | Attachments drafted (D-9) | engineering |
| 2026-10-27 | Full package review: positioning pass (D-17), arithmetic re-check, all remaining decisions closed | developer |
| **2026-10-29** | **Submit.** Five days before the deadline, not on it | developer |
| 2026-11-03 12:00 CEST | Hard deadline **[fact]** | — |
| 2027-02 to 2027-04 | Expected decision window (3-5 months from the deadline **[fact]**) | — |

Rationale for submitting on 2026-10-29: the form accepts multiple
versions before the deadline and uses the last complete one **[fact]**,
so an early submission costs nothing and removes deadline-day risk.

---

## 9. Character counts (self-check)

Counts of the exact text inside each `field:<name>` marker block, code
fences excluded, trailing newline excluded.

| Field | Characters | Limit | Headroom |
|---|---|---|---|
| abstract | 1379 | 1500 | 121 |
| experience | 2353 | 10000 | 7647 |
| use | 3130 | 10000 | 6870 |
| comparison | 4403 | 10000 | 5597 |
| challenges | 4832 | 12500 | 7668 |
| ecosystem | 3400 | 10000 | 6600 |

Reproduce from the repository root:

```sh
count() { awk -v b="<!-- field:$1:begin -->" -v e="<!-- field:$1:end -->" \
  'index($0,b){s=1;next} index($0,e){s=0} s' docs/13-nlnet-application.md \
  | sed '/^```/d' | python3 -c \
  'import sys;print(len(sys.stdin.read().rstrip(chr(10))))'; }
for f in abstract experience use comparison challenges ecosystem; do
  printf '%-12s %s\n' "$f" "$(count $f)"; done
```

All six fields are inside their limits with headroom; the abstract, the
only tight one, has 121 characters spare against the verified 1500
ceiling — and 179 characters *over* the 1200 that docs/06 A.5 assumed,
which is why [D-13] matters.
