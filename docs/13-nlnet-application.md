# 13 — NLnet Restack application package

Date: 29 August 2026. Supersedes the 25 August draft.
Status: submission-ready draft. Every field of the live NLnet form is
drafted here in paste-ready form. Fields that still need a decision from
the developer are marked **[D-n]** and collected in section 7.
Owner of the submission act: developer. Owner of the technical text:
engineering.

Scope: this document is the instantiation of `docs/06-funding-and-shuttle.md`
part A against the *actual* form on nlnet.nl, re-verified on 2026-08-29 by
fetching the form markup directly rather than trusting the summary in
docs/06 — or the summary in the 25 August version of this document.
Where the live form disagrees with any document, the live form wins and
the delta is recorded in section 1. All positioning language obeys the
binding rules of `docs/05-market-positioning.md` section 4
(fault-tolerant wording, LEO 10-30 krad(Si) class, no claim at or above
100 krad(Si), multi-market framing, fact/estimate discipline).

Labels: **[fact]** = traceable to a cited source or a command run on the
stated date; **[estimate]** = inference or project judgement; **[D-n]** =
open decision for the developer.

**What changed in this revision, in one paragraph.** The form itself is
unchanged since 2026-08-25, but the previous check read only the
`maxlength` attributes and missed the *advisory* limits printed in each
field's placeholder, which are far lower — the abstract's placeholder
says 1200 where `maxlength` says 1500, and four of the six drafted fields
were over their advisory limits (section 1.2). Every field has been
rewritten to the advisory limits. The application now leads with the
method rather than the chip, for the reasons in section 2.1. Every
number has been re-derived from the repository by running the suites
rather than by quoting documents, several of which are stale (section
1.4 and section 10). The budget and milestone plan were rebuilt because
NLnet cannot pay for work completed before the grant and much of the
previously proposed scope will be finished before an MoU could be signed
(section 2.2).

---

## 1. What was verified on nlnet.nl on 2026-08-29

### 1.1 The live form: fields and hard limits — unchanged

Verified 2026-08-29 by retrieving `https://nlnet.nl/propose/` and reading
the raw form markup. **[fact]** Field names, order, types and `maxlength`
values are byte-for-byte what the 2026-08-25 check recorded. The deadline
text is unchanged: calls reopen **2026-09-03**, deadline **2026-11-03
12:00 CEST (noon)**. **[fact]** The call selector still reads "There are
currently no calls open"; Restack is listed in the sidebar under
"Upcoming funds". **[fact]**

| Order | Field (form name) | Type | `maxlength` | Placeholder advisory | Required |
|---|---|---|---|---|---|
| 1 | Call (`call`) | select | — | — | **yes** |
| 2 | Name of the applicant (`requestor`) | text | 100 | — | no |
| 3 | Email address (`email`) | email | 100 | — | **yes** |
| 4 | Phone number (`phone`) | text | 100 | placeholder `+` | no |
| 5 | Organisation (`organization`) | text | 100 | "(if any)" | no |
| 6 | Country of residence (`country`) | text | 100 | — | no |
| 7 | Project name (`project`) | text | 100 | — | no |
| 8 | Website (`website`) | text | 100 | `https://` | no |
| 9 | Abstract (`abstract`) | textarea | 1500 | **"(You have 1200 characters)"** | **yes** |
| 10 | Previous relevant experience (`experience`) | textarea | 10000 | "(Optional) … **max 2500 characters**" | no |
| 11 | Requested amount (`amount`) | numeric | — | "(between 5000 and 50000)" | no |
| 12 | Budget explanation + other funding (`use`) | textarea | 10000 | "**max 2500 characters, be concise**" | no |
| 13 | Comparison with existing efforts (`comparison`) | textarea | 10000 | "**max 4000 characters, be concise**" | no |
| 14 | Significant technical challenges (`challenges`) | textarea | 12500 | "(optional but recommended, **max 5000 characters**)" | no |
| 15 | Ecosystem and engagement (`ecosystem`) | textarea | 10000 | "**max 2500 characters, be concise**" | no |
| 16-18 | Attachments 1-3 (`attachment1..3`) | file | 50 MB total, HTML/PDF/ODF/plain text | — | no |
| 19 | Generative-AI disclosure (`used_ai`) | select | two options | — | **yes** |
| 20 | Prompt provenance (`ai_prompt`) + 3 file slots | textarea | 10000 | — | conditional |
| 21 | Privacy consent (`consent`) | checkbox | — | — | **yes** |
| 22 | Send me a copy (`want_copy`) | checkbox | — | pre-checked | no |
| 23 | OpenPGP key (`pgp`) | textarea | 10000 | key valid ≥3 months past the deadline | no |

Exactly five controls carry `required="required"`: `call`, `email`,
**`abstract`**, `used_ai`, `consent`. **[fact]** The 25 August table
recorded the abstract as optional; it is not. Everything else optional,
including the project name and the requested amount.

Form guidance, verbatim, printed above the free-text fields: "Please be
short and to the point in your answers; focus primarily on the what and
how, not so much on the why. Add longer descriptions as attachments (see
below). … Do stay concrete. Use plain text in your reply only, if you
need any HTML to make your point please include this as attachment."
**[fact]**

The abstract's own label is longer than the field name suggests and asks
two questions: "Can you explain the whole project and its expected
outcome(s). **Have you been involved with projects or organisations
relevant to this project before? And if so, can you tell us a bit about
your contributions?**" **[fact]** The abstract draft in section 3.4 now
answers the second question in its closing sentence; the 25 August draft
did not.

### 1.2 The finding this re-check produced: advisory limits, not just `maxlength`

The 25 August verification read `maxlength` and concluded the abstract
ceiling was 1500 "not 1,200", treating docs/06 as simply wrong. That was
half the picture. **The form states both a hard limit and a much lower
advisory limit, and they disagree by a factor of up to four.** **[fact]**

| Field | Advisory (placeholder) | Hard (`maxlength`) | 25 Aug draft | Over advisory by |
|---|---:|---:|---:|---:|
| abstract | 1200 | 1500 | 1379 | +179 |
| experience | 2500 | 10000 | 2353 | — |
| use | 2500 | 10000 | 3130 | **+630** |
| comparison | 4000 | 10000 | 4403 | **+403** |
| challenges | 5000 | 12500 | 4832 | — |
| ecosystem | 2500 | 10000 | 3400 | **+900** |

Four of six fields were over. docs/06's "1,200" for the abstract was not
wrong — it was the advisory number, sourced from an applicant who had
seen the placeholder. Both documents were half right.

**Why this is treated as binding rather than as guidance.** Three of the
placeholders say "be concise" in as many words; the printed guidance says
"be short and to the point"; the FAQ says a proposal should take "less
than an hour" to complete; and the foundation "processes thousands of
grant applications every year". Cost effectiveness is 30% of the score
and reviewer attention is the scarce resource in the room. Every field in
section 3 has been rewritten to the advisory limit. The hard limits are
recorded in section 9 as headroom, not as budget.

**Consequence for the attachment plan.** The attachment guidance is
blunter than the 25 August draft assumed, verbatim: "Attachments should
only contain background information, please make sure that **the proposal
without attachments is self-contained and concise**. Don't waste too much
time on this. Really." **[fact]** The previous plan — three PDFs
including an 8-12 page architecture document, budgeted at 6-10 h — is
over-engineered against that instruction and has been cut to two lean
attachments (section 3.11).

### 1.3 Everything else re-verified, and it all still holds

Re-fetched and re-read on 2026-08-29. No change from the 25 August
record on any of the following. **[fact]**

1. **Restack rules** (`https://nlnet.nl/restack/guideforapplicants/`):
   weights 30% technical excellence/feasibility, 40%
   relevance/impact/strategic potential, 30% cost effectiveness; "The
   total weighted score of projects has to be above 5.0 (out of 7) to
   pass to the next stage"; "a **first proposal** MAY request a grant
   allocation up to **50 kEuro**"; maximum 150 kEuro per proposal,
   500 kEuro per third party over the programme; "All scientific
   outcomes must be published as open access, and any software and
   hardware must be published under a recognised open source license in
   its entirety."
2. **The stage-1 knock-out criteria**, verbatim: proposals "should be in
   line with the goals of Restack", "should have **research** and
   **development** as their **primary** objective", and "should satisfy
   any other hard eligibility criteria specific to the sub-granting
   call, such as having a clear **European Dimension**". The FAQ is
   explicit: "It is a **knock-out criterion** for each project to have a
   'European dimension'." The middle criterion is new to this document's
   record and matters: a proposal that reads as productisation rather
   than R&D fails before it is scored.
3. **Programme size and budget pressure**: Restack "will competitively
   award **7 million euro** worth of grants"; it "runs between June 1st
   2026 and May 30th 2030, new calls will be announced until the budget
   of the programme has been fully allocated (**expected early 2027**)".
   The case for submitting into this round rather than a later one is
   unchanged and is the strongest scheduling fact in this document.
4. **Decision lag**: "You can expect the process to take between three
   and five months. This is counted from the date of the deadline of the
   open call". For 2026-11-03 that is **2027-02 to 2027-04**, MoU after
   that.
5. **Cadence**: deadlines are "the third day of every odd month"
   (`https://nlnet.nl/news/2026/20260803-phaseshift.html`).
6. **Payment mechanics** (`sample_MoU.pdf`, re-retrieved 2026-08-29):
   "There is a donation amount attached to each task, which you unlock
   by publishing the associated results"; public progress reporting
   "every two months" plus "a public status page for the project"; the
   grantee "is responsible for paying any and all taxes or other fees
   with regard to this grant"; "Donations may be claimed up to the
   reserved amount within a maximum of six months after the proposed end
   of the project".
7. **Eligible-activity list** (`https://nlnet.nl/restack/eligibility/`)
   still does not name silicon fabrication, instrumentation or
   irradiation-facility time. They fall under "out-of-pocket costs for
   infrastructure essential to achieving the above" by construction, not
   by name. Precedent supports it (Chips4Makers,
   `https://nlnet.nl/project/Chips4Makers/`), but this is still the line
   most likely to be questioned in stage 2. See [D-12].
8. **Precedent projects** all still live, all returning HTTP 200 on
   2026-08-29, and two now carry public source URLs that make the
   collaboration offer concrete: INA-ASIC at
   `https://github.com/SLICESemiconductor/Space_grade_Instrumentation_Amplifier_ASIC`
   and GLOW-SG13G2 at `https://github.com/dgrujic/glow_sg13g2`.
   The correction of docs/06 A.4's "no space precedent" stands
   (section 1.6).

### 1.4 Two things the 25 August draft did not record, and both bite

**(a) NLnet cannot pay for work already done.** FAQ, verbatim: "A grant
can only cover the period between the proposal being officially selected
and the agreed end of the Memorandum of Understanding. **We cannot make
donations for any effort completed prior to the grant.**" **[fact]** The
mitigation offered is: "Should we select your project, we can discuss
replacing those parts with other tasks (rather than reducing the
budget)," and the advice is "just to continue working on the project to
the extent possible, as if our foundation and the entire grant
application didn't exist."

This invalidates the 25 August task plan. Its T1 ("event-driven
inference core RTL") and T2 ("fault-tolerance IP set: SECDED codec, TMR
voter bank, scrub controller, fault counters") describe work that exists
at HEAD today and will be long finished by an MoU signature in mid-2027.
A reviewer doing "independent verification of facts, methods and claims"
would find the public repository and see it. Section 2.2 rebuilds the
scope around work that is genuinely ahead of the project.

**(b) The generative-AI policy has a second half that outlives the
submission.** The 25 August draft recorded only the application-stage
disclosure. The policy
(`https://nlnet.nl/foundation/policies/generativeAI/`, version 1.1,
valid from 2026-01-26) also governs **project development** for the life
of the grant. **[fact]** Verbatim requirements: "For any *substantive*
use of GenAI that materially affects outputs, public disclosure is
required"; a codebase "declares, typically in its 'readme', broadly how
GenAI is used"; "Generated content should be marked as such … Specify
which model was used, (including version), and how it was used."
Non-compliance "may result in rejection of the proposal or ultimately in
the termination of the running grant."

The FAQ is blunter than the policy: "**The short answer is: no.** …
Please grant us the courtesy of writing the proposal yourself. If you do
use generative AI to write (part of your) proposal, please put this in
the text **and explain why this was necessary**. Failure to do so is
likely to result in the proposal being rejected, and tarnishing your
reputation." **[fact]** Note that the required disclosure is not merely
a log — it is a log *and a justification*.

One clause of the policy is worth reading in the project's favour, since
it describes this project's method almost exactly: "NLnet is a strong
proponent of automation and of deterministic and reproducible generation
of source code, formal and symbolic proofs, etc. based on specifications
and scientific and engineering rigour." **[fact]** The generated register
map, the golden-model refinement and the SymbiYosys programme sit
squarely inside the thing the policy says it wants.

See [D-10] and the new [D-18]. Both are the developer's to answer, and
[D-18] is a standing obligation on the repository, not a form field.

### 1.5 Two more constraints that shape the plan

- **Default project duration is 12 months.** FAQ: "By default, we expect
  projects to be completed within 12 months — but qualified exceptions
  can be made." **[fact]** The milestone plan in section 5 fits inside
  12 months of MoU signature by construction, and section 5 says where
  the exception would have to be requested if the shuttle slips.
- **F&A costs are generally not eligible**, capped at 25% when they
  are. **[fact]** Nothing in this budget is an overhead line, which is
  worth one sentence of the budget field.

### 1.6 Precedent correction (unchanged, restated for completeness)

docs/06 A.4's "no space/SpaceWire/satellite-silicon precedent was found
in the funded-projects list" is wrong, and docs/06 has not been
corrected — the correction lives only here. **[fact, re-checked
2026-08-29]**

| Project | Why it matters here | URL |
|---|---|---|
| Space grade Instrumentation Amplifier ASIC (NGI0 Commons Fund, start 2026-03) | Analog front end taped out "on IHP's 130nm open source PDK"; "the INA will be made robust to high radiation environments, making it applicable to low earth orbit / high energy particle applications". Same PDK, same environment class, funded. | https://nlnet.nl/project/INA-ASIC |
| GLOW-SG13G2 | Open standard-cell library and characterisation flow for exactly the PDK this project hardens on. Direct collaboration candidate. | https://nlnet.nl/project/GLOW-SG13G2 |
| Borg II | Taped out on IHP 130 nm — announced by NLnet as "to our knowledge the first open-source GPU design to do so". Evidence the flow closes at this scale. | https://nlnet.nl/project/Borg-GPU |
| PowerCommons | Open synthesis flows targeting the IHP 130 nm open PDK. | https://nlnet.nl/project/PowerCommons |
| FPGA Fault Injection Testing (NGI0 Entrust, 2024-02 to 2025-05) | Fault-injection methodology funded as a first-class deliverable. Direct precedent for the spine of this proposal. | https://nlnet.nl/project/FPGA-Inject |

### 1.7 Re-verification action when the call opens

The form was inspected with **no call open**, twice now. Field sets and
limits can be call-specific. Before writing into the live form on or
after 2026-09-03: re-fetch the page, re-read every `maxlength` **and
every placeholder**, and confirm the advisory limits in section 1.2 are
unchanged. Owner: developer. **[D-13]**

---

## 2. Funded scope

### 2.1 The application leads with the method, not the chip

This is a change from the 25 August draft and it is a judgement, so the
reasoning is stated rather than assumed.

The most fundable thing this project has is no longer the chip. It is
the loop: **a fault-injection campaign that ranks structures by measured
silent-corruption contribution, hardening driven by that ranking, and a
mechanical check that the redundancy survived synthesis.** Four reasons,
in descending order of weight.

1. **It is the only framing that survives section 1.4(a).** The chip
   building blocks largely exist at HEAD and will be finished before an
   MoU exists. The method's next steps — gate-level injection,
   multi-bit upsets, the checker as a released tool, hardening the
   structures the ranking still names — are genuinely future work. A
   proposal must be fundable *when the money arrives*, not when it is
   written.
2. **It scores on the 40% criterion, and the chip scores on the 30%.**
   "Relevance/Impact/Strategic potential" is the heaviest weight, and
   stage 2 selects "projects … which not only satisfy the minimal
   criteria, but also have potentially a lasting impact". A hardened
   neuromorphic tile has a narrow constituency. A defect class that
   silently deletes redundancy from *any* yosys-synthesised design has
   the constituency of every open hardening effort in the fund's own
   portfolio — Borg II, Libre-SOC, FABulous, GLOW-SG13G2, the INA ASIC.
   This project has the measurement, the repair and the mechanical
   check, which is three more than a bug report.
3. **The evidence is strongest there.** The chip claims are targets:
   silicon is not fabricated, no radiation data exists. The method
   claims are measured today, with the log published: 287 injections, a
   ranking, a before/after on an identical re-run, a netlist that
   carried 362 references to one replica and none to the other two, a
   repair whose area and timing cost is measured, and a test that fails
   if the defect returns. A reviewer who checks one claim and finds it
   inflated discards the rest, and stage 2 does exactly that check;
   leading with the measured half is the disciplined choice.
4. **It de-risks the budget.** If the reviewers strike the irradiation
   line ([D-12], R-3), a chip-led proposal loses its point. A method-led
   proposal loses one milestone and keeps its spine.

**What the framing must not do**, and section 3 is written to avoid it:
Restack funds "technology building blocks" and "libre chips". A pure
methodology proposal is a worse fit than an IP block. So the method is
the spine and the fault-tolerant block is the instantiation that proves
it and carries it to silicon — both are in the abstract, in that order.
The "research and development as the primary objective" knock-out
(section 1.3 item 2) is satisfied more obviously by this framing than by
the previous one.

### 2.2 What the grant actually buys

- ROADMAP P3 rolls up **1015-1895 h** for the full SoC **[estimate,
  ROADMAP section 2]**. That is far beyond a first proposal's 50 kEUR
  ceiling at any defensible rate.
- The funded scope is therefore neither the SoC nor the already-built
  blocks. It is: gate-level and multi-bit fault injection; a second
  hardening wave against the current ranking; the redundancy-survival
  checker released as a tool other projects can run; the SRAM-macro and
  ECC-wrapper sign-off that a first attempt failed on upstream causes;
  silicon on a community shuttle with bring-up against the published
  suite; and the first public total-ionising-dose data for
  `sg13g2_stdcell`-based digital logic.
- The full SoC integration (RV32 management subsystem, SpaceWire codec,
  CAN, the rest of the interface set) continues on the ROADMAP outside
  the grant and appears in the application as context, never as a
  deliverable.

### 2.3 European dimension — the stage-1 knock-out

Türkiye is associated to Horizon Europe for 2021-2027, which puts the
applicant in the priority group rather than on the exception path
(docs/06 A.3) **[fact]**, so the criterion is satisfied on residence
alone. The substantive case is carried by the ecosystem field and is
stronger under the new framing: the target PDK is IHP's, a German
Leibniz institute's; fabrication is in Frankfurt (Oder); the flow is
LibreLane/OpenROAD and yosys; the checker's first users are
NLnet-funded European silicon projects on the same tools; and the output
is a building block for the European open-silicon commons. No sentence
in the application needs to argue the point defensively.

---

## 3. Field drafts (paste-ready)

Convention: text inside a `field:<name>` marker block is exactly what
gets pasted into the corresponding form field. Character counts are in
section 9 and reproducible with the command given there. The paste
blocks are ASCII except for a single "ü" in "Türkiye" in the budget
field; every character used is one UTF-16 code unit, which is the unit
an HTML `maxlength` counts, so the section 9 numbers are the numbers the
form will enforce.

### 3.1 Contact information

| Field | Value | Status |
|---|---|---|
| Name of the applicant | — | **[D-1]** legal name or alias. FAQ: "You don't need to reveal your real name to us, prior to the project being granted." **[fact]** Recommendation: legal name — the prior-work evidence (a shipped Tiny Tapeout design, public repositories) is attached to it and anonymity would break the strongest part of the experience field. |
| Email address | — | **[D-2]** a project address, not a personal one, so MoU correspondence is separable. |
| Phone number | — | **[D-3]** international format required by the placeholder. |
| Organisation | — | **[D-4]** blank (individual) vs a registered entity. FAQ: "You can apply as an individual … It is not an issue if you have not yet established the entity when you apply." **[fact]** Tax handling differs (R-7); recommendation is to apply as an individual and decide the entity question separately. |
| Country of residence | Türkiye | Fixed. Associated to Horizon Europe 2021-2027, so the applicant is in the priority group (docs/06 A.3). **[fact]** |

### 3.2 Project name (limit 100)

**[D-5]** — pick one. Recommendation changed from the 25 August draft to
match the method-led framing.

| Option | Text | Chars | Note |
|---|---|---:|---|
| A (recommended) | `Measured fault tolerance for open silicon` | 41 | Names the contribution. Legible to a non-specialist reviewer, and it is not a claim. |
| B | `Verifiable redundancy for open silicon: fault-injection-ranked hardening on SG13G2` | 81 | Most precise. Longer and more jargon-dense. |
| C | `Open fault-tolerant neuromorphic inference IP for small satellites` | 66 | The 25 August recommendation. Leads with the chip, which section 2.1 argues against. |
| D | `Neuromorphic Space SoC` | 22 | Matches the repository name, but promises the whole SoC. |

### 3.3 Website (limit 100)

**[D-6]** — blocked on `docs/14-licensing-decision.md`, which is
**unsigned and past its own first deadline** (section 7). The field is
optional and there is no requirement to be public at application time,
but leaving it empty removes the reviewer's cheapest route to the
prior-work evidence, and stage 2 does independent verification. Options
in order of preference: (a) public repository URL if the docs/14
recommendation is accepted; (b) a single static project page listing the
public artefacts; (c) the existing public Tiny Tapeout project page for
`tt-um-lif-crossbar`; (d) blank.

### 3.4 Abstract (advisory 1200, hard 1500) — required field

Positioning check applied sentence by sentence: "fault-tolerant" is used
and "rad-hard" is not; the total-dose class is stated as LEO
10-30 krad(Si) and no figure at or above 100 krad(Si) appears; no claim
is made about the AER pointer TMR, whose measurement is not yet in
(section 10). "Clean-room" does not appear — docs/02 open question 2
(reuse of Solderpad-licensed tinyODIN/ODIN RTL versus an independent
implementation) is still open, so the word is not a fact this project
can assert. See [D-14]. The closing sentence answers the second half of
the field's own label (section 1.1).

<!-- field:abstract:begin -->
```text
Open silicon can add redundancy and lose it silently. Synthesis merged this design's triple-redundant configuration register into one bank - 362 netlist references to one replica, none to the other two - while RTL fault injection kept reporting it as working. Any hardening effort on yosys can hit it.

The response is a method and a block. The method: fault injection that ranks structures by measured silent-corruption contribution, hardening driven by that ranking, and a check that counts redundant banks in the real netlist. On an identical 255-injection re-run, silent corruption fell from 35.7% to 18.8%. The block: an event-driven spiking neural network core with ECC-protected synapse memory, TMR and scrubbing, verified against a bit-exact golden model and hardened on IHP's open SG13G2 PDK.

The grant extends injection to gate level, hardens what the ranking still names, releases the check as a tool others can run on their own netlists, and takes the block to silicon on a community shuttle for a total-dose pre-screen in the LEO 10-30 krad(Si) class, where no public data exists. Everything is free-licensed. Prior silicon: tt-um-lif-crossbar, a spiking crossbar on Tiny Tapeout.
```
<!-- field:abstract:end -->

**On the two percentages, and why the abstract does not say 287.**
35.7% and 18.8% are the *same* 255 injections before and after the
memory hardening, which is the only honest way to state a reduction. The
design as it stands measures 17.1% silent corruption over the
287-injection campaign of record — **a different denominator, so it must
never be the number placed next to 35.7%.** That pairing (35.7% → 16.7%)
is circulating informally and would not survive a reviewer who reads
docs/16, which says in as many words that the 255-injection figure "is
the one to quote when comparing against the pre-hardening run, because
it is the same 255 experiments". The abstract therefore names 255
explicitly and leaves 287 to the experience field, where it appears as a
campaign size and not as a rate.

Section 10 records the further problem that `docs/16` currently states
16.7% / 48 SDC / 0 HANG where its own results file at HEAD says 17.1% /
49 SDC / 2 HANG. The application quotes neither, so it is unaffected
either way.

### 3.5 Previous relevant experience (advisory 2500, hard 10000)

Every claim is checkable, which is the point — stage 2 verifies. All
counts below were produced by running the suites on 2026-08-29, not by
quoting a document (section 9.2).

<!-- field:experience:begin -->
```text
I design fault-tolerant digital silicon with open tools, solo, and I ship it.

Silicon: tt-um-lif-crossbar, an 8x8 leaky-integrate-and-fire neuron crossbar on a 2x2 Tiny Tapeout tile in SkyWater 130 nm, taken through the open RTL-to-GDS flow. It is the direct ancestor of the core proposed here; the neuron update datapath and the crossbar accumulation logic carry over.

Where this project stands today, all of it checkable. Eight RTL blocks with a bit-exact Python golden model as their executable specification. 45 SymbiYosys proof tasks across seven property sets, including SECDED correctness exhaustive over the full input space, a TMR masking theorem under a symbolic single-replica fault, and unbounded k-induction on the event-queue safety properties. 144 cocotb tests and 195 Python tests, one of which fails if the register map, the generated Verilog header, the documentation and the model bindings drift apart. A 287-injection fault campaign whose log is published with the design. A clean IHP SG13G2 sign-off of the 4x2 pilot: zero DRC, zero LVS, zero timing violations across three corners at 69.68% utilisation. The same RTL hardens on SkyWater SKY130A and fits and routes on a Lattice ECP5.

Flow: LibreLane/OpenROAD, Yosys, Icarus/cocotb, SymbiYosys, nextpnr and KLayout, run rootless without containers or root privileges on my own machine. The toolchain checkout is pinned in the repository, because an unpinned one silently ran a formal gate with another project's tools and a result that cannot name the tool that produced it is evidence of nothing.

Method: spec-first. The golden model exists before the RTL and the RTL is checked against it equation by equation. The formal programme is modelled on the seL4 proof stack: properties-as-specification per block, golden-model refinement, and an explicit assumption ledger recording what the proofs do not cover.

Review discipline: the research phase was put through an independent design review that produced nineteen confirmed findings, including three misattributed radiation citations - one of them in my own funding material. All were corrected before this application was written and the corrections are in the repository history. I would rather find those myself than have your reviewers find them.

Adjacent work: a 130 nm-class INT8 accelerator for telemetry anomaly detection, and prior physical-design work including MBIST, boundary scan and multi-corner static timing.
```
<!-- field:experience:end -->

**[D-7]** — before pasting: (a) the tt-um-lif-crossbar accuracy figure
has been **removed** from this draft rather than repeated, because it
cannot be confirmed from this repository (section 10, item 6); decide
whether to reinstate it with the record in hand or leave it out; (b) add
public URLs for the Tiny Tapeout design and, if docs/14 lands as
recommended, for this repository; (c) decide whether to name the
adjacent programmes explicitly.

### 3.6 Requested amount

**EUR 29,500.** Inside the 5,000-50,000 window and inside the
first-proposal ceiling of 50 kEUR **[fact]**. Changed from the 25 August
figure of EUR 27,500 because the task set was rebuilt (section 2.2); the
out-of-pocket half is unchanged, the developer-time half went from 410 h
to 460 h. Re-derived line by line in section 4 with explicit rates,
because the form says "Make rates explicit".

### 3.7 Budget explanation and other funding sources (advisory 2500, hard 10000)

<!-- field:use:begin -->
```text
Rate: EUR 40/hour for all developer time, the same for every task. 460 hours requested, plus EUR 11,100 of out-of-pocket costs that effort cannot substitute for. No overhead or administrative lines.

Developer time - EUR 18,400 for 460 h

T1. Gate-level and multi-bit fault injection (110 h, EUR 4,400). Injection today targets named RTL flip-flops and is blind to anything synthesis changes - how a merged TMR bank went unnoticed. This moves it to the post-synthesis netlist and adds multi-bit and adjacent-cell upsets.

T2. Second hardening wave from the ranking (100 h, EUR 4,000). Queue storage, output adapter, event dispatcher; injection targets moved onto the replicated pointer banks so redundancy is measured rather than assumed; per-domain ECC counter attribution.

T3. Redundancy-survival checker as a standalone tool (60 h, EUR 2,400). The bank-counting check generalised so any yosys or LibreLane project can run it on its own netlist, published with the catalogue of repair constructions and their costs.

T4. SRAM macro and ECC wrapper sign-off on IHP SG13G2 (70 h, EUR 2,800). A first attempt failed with both blocking causes upstream of this repository; this closes them upstream.

T5. Silicon bring-up (70 h, EUR 2,800). Host software, silicon-vs-model lockstep on the fabricated part, fault-tolerance demonstrator, results memo.

T6. Documentation, dataset publication, public reporting (50 h, EUR 2,000). Integration guide, radiation dataset with analysis scripts, and the two-monthly public reports and status page the MoU requires.

Out-of-pocket - EUR 11,100

H1. 32 shuttle tiles at EUR 70 = 2,240.
H2. Development kits and carrier boards, 2 x 150 = 300.
H3. Breakout and test PCB, two revisions, fab, assembly, parts = 800.
H4. Bring-up instrumentation: FPGA host board 400, programmable supply with current logging 900, logic analyser 250, cabling 150 = 1,700.
H5. Total-ionising-dose pre-screen: Co-60 facility time 3,500, fixture mods and spares 400, shipping, customs and dosimetry 900 = 4,800.
H6. Import duties and shipping into Türkiye = 760.
H7. Travel and admission to one European open-silicon event = 500.

Total: 18,400 + 11,100 = EUR 29,500.

Other funding, past and present: none. The work so far and the first shuttle entry are self-funded and stay so whether or not this succeeds.

Cash flow: payment follows publication, so everything is spent before reimbursement. Milestones are ordered so the two largest out-of-pocket items sit behind ones already paid.
```
<!-- field:use:end -->

**[D-8]** — the EUR 40/hour rate is a placeholder and must be confirmed
or replaced before submission. It is the single number stage 2 is most
likely to interrogate ("the rate you have applied for task B is very
high compared to the perceived value of that task. Can you explain, or
would you like to reconsider?" is a verbatim example question
**[fact]**). Changing the rate changes the hours, not the total, unless
the scope moves with it.

**[D-15]** — H5 (EUR 4,800) still rests on an unquoted facility price.
docs/06 action item 7 owns "identify a Co-60 TID facility and obtain
quotes"; it is still open. A real quote must replace the estimate before
submission, or the line must be re-scoped.

### 3.8 Comparison with existing or historical efforts (advisory 4000, hard 10000)

<!-- field:comparison:begin -->
```text
The gap, stated first. There is open neuromorphic hardware, open fault-tolerance research, open flows and open PDKs, and proprietary radiation-hardened neuromorphic silicon. What does not exist is an open fault-tolerant design whose hardening was chosen by measurement, whose redundancy is checked mechanically against the netlist that gets fabricated, and whose proofs, flow scripts and radiation data are all published.

On method. Fault injection into RTL is standard practice and I claim nothing new about the technique. Two things here are not standard. First, injection produces a ranking of structures by measured silent-corruption contribution, and the hardening wave is chosen from that ranking rather than from intuition - which mattered: the structure a comparable campaign on a different accelerator predicted would dominate was not the one that did. Second, the redundancy is verified in the netlist rather than the RTL. That check exists because RTL injection reported this design's configuration TMR as working while yosys had merged the three replicas into one physical bank: opt_dff normalised them and opt_merge hashed them together, and the netlist that fed a harden carried 362 references to one replica and none to the other two. RTL simulation is structurally incapable of seeing a structure synthesis deletes, and marking the replicas "keep" does not fix it - the wire names survive, the storage does not. Every open hardening effort on this toolchain is exposed. NLnet has funded fault-injection methodology before (FPGA Fault Injection Testing) and open silicon on this PDK; this joins the two.

Open spiking-neural-network hardware. ODIN, tinyODIN (UCLouvain) and ReckOn are the open reference designs, released under Solderpad. They are excellent microarchitectures and tinyODIN is what I verify my core against. What they are not: fault-tolerant - no ECC, no TMR, no scrubbing, no fault counters - not taken through an open PDK to characterised silicon, and not accompanied by any radiation data. Intel Loihi and SpiNNaker are not open silicon at all.

Proprietary reference point, stated honestly. Frontgrade Gaisler's GR801 is the device this project is measured against: a radiation-hardened SoC on 28 nm FDSOI pairing a fault-tolerant NOEL-V RISC-V core with licensed BrainChip Akida IP. It is better than this project on almost every technical axis - an FDSOI platform with intrinsic latch-up immunity, 11.2 MB of on-chip SRAM, SpaceWire, PCIe, a qualification path and a sales channel. I am not proposing to compete with it and will not claim to. What it structurally cannot do is let an integrator read the RTL, re-run the verification, or reproduce the fault-tolerance evidence, and it will not be affordable to a university CubeSat programme. The same holds for Microchip PIC64-HPSC, AMD Versal XQR and Teledyne e2v QLS1046-Space: all proprietary, none publishing RTL or fault-injection data.

NLnet-funded open silicon. Libre-SOC is closest in ambition and taped out at 180 nm, but it is a general-purpose application processor with no fault tolerance; its precedent is that open SoC work of this shape can be delivered. GLOW-SG13G2 is building an open cell library for exactly the SG13G2 process I harden on: I am a consumer of that layer, not a competitor, and a hardened design is a demanding customer for a new library. Borg II has reached silicon on IHP 130 nm, evidence the flow closes. Every one of these synthesises with yosys, which is precisely the population the checker is for.

Closest funded precedent. The Space grade Instrumentation Amplifier ASIC is building a programmable-gain instrumentation amplifier on IHP's 130 nm open PDK, made robust for low earth orbit. That is the analog front end of the same signal chain whose digital back end I propose. I would like to coordinate: shared irradiation campaigns are far cheaper per part than separate ones, and a common fixture and dose-reporting convention would make both datasets comparable.
```
<!-- field:comparison:end -->

### 3.9 Significant technical challenges (advisory 5000, hard 12500)

The largest field on the form and the one docs/06 missed entirely. It is
where the honest engineering risks belong; stage 2 asks "how will you
approach complicating factor X" **[fact]**.

<!-- field:challenges:begin -->
```text
1. Injecting faults into a netlist rather than into RTL. This is the proposal's core technical problem. RTL injection has a stable target list: named architectural registers I can check by eye against the source. After synthesis those names are gone, retiming has moved state across boundaries, and one RTL register may be several cells or none. Approach: build the target list from the flow's own name-mapping output, keep the RTL campaign running in parallel as a cross-check, and treat any structure appearing in one list and not the other as a finding rather than noise - that divergence is the signal the method is after. Where mapping is lost, report the coverage honestly instead of quietly shrinking the denominator.

2. Multi-bit upsets need a physical adjacency model, not a logical one. A multi-bit upset hits cells near each other on the die, not bits near each other in a bus. Approach: derive adjacency from the placed design's coordinates rather than bit index, publish the model with the results, and state plainly that a model-derived multi-bit result is weaker evidence than a beam - a screening tool that says where to look, not a rating.

3. Redundancy that survives an optimiser determined to remove it. The three-replica configuration bank was merged into one, and the obvious fixes do not work: a keep attribute preserves the wire name while the storage still collapses, and per-replica polarity is provably bounded at two banks because a stored bit has only two polarities. What does work here is making each replica store a different invertible function of the same data, so no per-bit structural hash can match one replica to another. Approach for the tool: publish that catalogue - what fails, what works, what each costs in area and timing - and make the check count flip-flop cells in the final netlist rather than trust any attribute. It must never assert on a signal name, and never skip on the symptom it exists to catch.

4. Proving what is load-bearing rather than what is easy to prove. The properties that matter in orbit are upset-recovery properties: that a control state machine started from an arbitrary corrupted state returns to a legal state in bounded time without violating an interface contract; that a voter masks any single corrupted replica; that a SECDED codec corrects every single-bit error and never silently miscorrects a double. Approach: unconstrained-initial-state induction for recovery, exhaustive bounded proof over symbolic data with a weight-constrained symbolic error mask for the codec, and a free symbolic single-replica fault for the voter, so masking is a theorem about a faulty machine rather than a statement made beside one. Where induction does not close, strengthen the invariant rather than weaken the property, and record anything bounded in an assumption ledger shipped with the proofs.

5. Integrating the foundry SRAM macro on an open PDK. A first attempt has already failed, usefully: the design placed, routed and closed timing, but DRC errors sat entirely inside the vendor macro geometry and LVS failed on hierarchy naming and a bus-delimiter mismatch. Both causes are upstream of this repository. Approach: work them with the upstream projects rather than around them, against a fixed calendar gate, with flip-flop weight storage as a fallback that removes the macro from the critical path and costs capacity, not correctness.

6. Observing a fault-tolerant part through a 24-pin shuttle interface. Eight inputs, eight outputs and eight bidirectional pins is enough to run the part, not obviously enough to observe corrected-error counts, scrub progress, voter disagreements and neuron state during an irradiation run. This has already bitten once: the memory ECC held on 84 of 84 injections and nothing on the chip said so, because the telemetry outputs were unconnected. Approach: design observability first - a compact serial channel streaming the fault counters and a selectable state window - and treat an unwired counter as a defect, not a detail.

7. Getting radiation data worth publishing. Bulk 130 nm CMOS logic carries no platform-level latch-up or total-dose guarantee, and the encouraging published numbers for this technology family come from its rad-hard sibling library, not the open standard cells. Approach: state that distinction in every published document, and design the campaign around one narrow question - how does this specific design in this specific open standard-cell library behave under total ionising dose in the LEO 10-30 krad(Si) class - with dose steps, in-situ functional test, and full publication of fixture, procedure and raw data including null results. The value to the commons is the method and the dataset, not a rating.

8. Doing this solo without the schedule collapsing. Approach: every milestone is independently publishable and the cheapest and most certain come first, so a slip in the later ones leaves the earlier ones standing, published and useful to someone else.
```
<!-- field:challenges:end -->

### 3.10 Ecosystem and engagement (advisory 2500, hard 10000)

<!-- field:ecosystem:begin -->
```text
Upstream, and this is where the main contribution lands. The design sits on IHP's open SG13G2 PDK, yosys and the LibreLane/OpenROAD flow, and is a demanding user of all three: hard macros, ECC wrappers, multi-corner timing, and redundancy that resists the optimiser's instinct to merge it. Stopping triple-modular-redundancy from being optimised away is a shared problem for every open fault-tolerant design, so the checker, the catalogue of constructions that survive and the reproducible test cases go upstream - to yosys, LibreLane and IHP-Open-PDK - as issues with minimal reproducers, not a folder in my repository.

Sideways. The first users of that checker are open silicon projects already on this toolchain, several funded by NLnet: GLOW-SG13G2 is building an open cell library for the same process, and a hardened design is a useful stress case; Borg II has taken a design of this shape to silicon; the Space grade Instrumentation Amplifier ASIC targets the same PDK for the same environment class, and I will propose a shared irradiation campaign and a common dose-reporting convention. Tiny Tapeout makes this silicon affordable at all, and every design I submit stays in its educational catalogue as a worked example of ECC, TMR and scrubbing.

Downstream. The intended users are university CubeSat programmes, small satellite integrators, and any harsh-environment project needing better-than-commercial fault behaviour without a qualification budget. What they get is not a datasheet claim but the evidence: the campaign log, the ranking, RTL, the executable specification, the proofs and their assumption ledger, the flow scripts, the bring-up software and the radiation data. A block that can be audited is one a mission can defend to its reviewers.

Publication. Everything lands publicly under free licenses as it is produced, not in a drop at the end, with the public status page and two-monthly reports the MoU requires. The radiation dataset comes with its analysis scripts and fixture description, because no public total-dose data exists for digital logic in this PDK. I will present results at a European open-silicon event.

Sustainability. Its future does not depend on my attention: the licenses let anyone fork, extend and manufacture it, and the verification suite and flow scripts make that practical rather than theoretical. My own path is fault-tolerant silicon design and services around it, so my commercial interest and the commons interest point the same way.
```
<!-- field:ecosystem:end -->

### 3.11 Attachments

**[D-9]** — up to three files, 50 MB total, HTML/PDF/ODF/plain text
**[fact]**. Cut from three to two, because the form says attachments
"should only contain background information", the proposal must be
"self-contained and concise" without them, and "Don't waste too much
time on this. Really." **[fact]**

1. **Evidence pack** (PDF, 3-4 pages). The one attachment that earns its
   place, because stage 2 verifies claims and this makes verification
   cheap: the SymbiYosys task list with its PASS output, the cocotb and
   pytest summaries, the fault-injection distribution table, the
   before/after netlist flip-flop counts for the merged TMR bank, and
   the SG13G2 sign-off metrics.
2. **Budget and milestone plan** (PDF, 2 pages): sections 4 and 5 in the
   MoU annex format, so it can be lifted into Annex I if selected.

Neither exists as a PDF yet. Producing both is ~3-5 h **[estimate]**,
down from the 6-10 h the three-attachment plan needed, and must be
scheduled before 2026-10-27 (section 8).

### 3.12 Generative-AI disclosure — required field

**[D-10]** — required select with two options: "I did not use generative
AI in writing this proposal" and "I have used generative AI in writing
this proposal". If the second is selected, the policy requires a prompt
provenance log listing the model, the dates and times of prompts, the
prompts themselves and the unedited output, and the FAQ additionally
requires that the applicant "explain why this was necessary"
**[fact]**. The answer and any log are the developer's to provide; this
document records the requirement only, and the requirement is that the
answer be accurate — non-compliance is grounds for rejection or for
termination of a running grant.

**[D-18]** — new, and it is not a form field. The same policy governs
project development for the life of the grant: substantive use that
materially affects outputs requires public disclosure, a broad statement
in the repository readme of how such tools are used, and per-contribution
provenance for generated content **[fact]**. If the grant lands this
becomes a standing obligation on the repository, so the readme statement
and the contribution convention should be settled before the MoU rather
than after. It also interacts with the licensing decision, since the
policy requires that everything delivered "can be legally published
under a FLOS licence".

### 3.13 Consent and PGP

- Privacy consent checkbox: required, must be ticked. **[fact]**
- "Send me a copy": pre-checked; leave it checked — the emailed copy is
  the only record of exactly what was submitted, and the FAQ's
  resubmission procedure asks for the assigned number from it.
- OpenPGP key: optional. **[D-11]** — if supplied, the key must be valid
  for at least three months after the deadline.

---

## 4. Budget breakdown

Rate: EUR 40/hour **[D-8]**, uniform across tasks. Totals in EUR.

### 4.1 Developer time — 460 h, EUR 18,400

| ID | Task | Hours | EUR | Grounding |
|---|---|---:|---:|---|
| T1 | Gate-level and multi-bit fault injection | 110 | 4,400 | The existing RTL campaign is 287 injections and ~9 min of wall time; netlist injection needs a new target-mapping path and a re-validated harness **[estimate]**. The gap it closes is documented, not hypothetical: RTL injection reported the configuration TMR as working while the netlist had one bank **[fact]** |
| T2 | Second hardening wave against the current ranking: queue storage, output adapter, dispatcher; pointer-replica injection targets; per-domain ECC counters | 100 | 4,000 | The ranking exists and is measured; the remaining weighted contributors are queue storage (28), the adapter (15) and the dispatcher (6) **[fact for the rates, estimate for the hours]** |
| T3 | Redundancy-survival checker released as a standalone tool, plus upstream issues | 60 | 2,400 | The check exists for this design as 17 tests; generalising it to arbitrary designs and flows, documenting the construction catalogue and upstreaming is the new work **[estimate]** |
| T4 | SRAM macro + ECC wrapper sign-off on SG13G2 | 70 | 2,800 | docs/06 B.6.1 puts macro integration at 25-50 h; the recorded failure adds upstream coordination **[estimate]** |
| T5 | Silicon bring-up: host software, silicon-vs-model lockstep, demonstrator, results memo | 70 | 2,800 | ROADMAP P4 **[estimate]** |
| T6 | Documentation, dataset publication, two-monthly public reporting | 50 | 2,000 | MoU reporting obligation **[fact for the obligation, estimate for the hours]** |
| | **Subtotal** | **460** | **18,400** | |

### 4.2 Out-of-pocket — EUR 11,100 (unchanged)

| ID | Item | Basis | EUR |
|---|---|---|---:|
| H1 | Shuttle tiles, follow-up run | 32 x EUR 70/tile (docs/06 B.2 **[fact]**, re-confirm in the calculator) | 2,240 |
| H2 | Development kits / carrier boards | 2 x EUR 150 **[estimate]** | 300 |
| H3 | Custom breakout and test PCB | 2 revisions, fab + assembly + components **[estimate]** | 800 |
| H4 | Bring-up instrumentation | FPGA host board 400, programmable supply with current logging 900, logic analyser 250, cabling 150 **[estimate]** | 1,700 |
| H5 | TID pre-screen campaign | Co-60 facility time 3,500 **[estimate, quote pending — D-15]**, fixture mods and spares 400, shipping/customs/dosimetry 900 | 4,800 |
| H6 | Import duties and shipping into Türkiye | ~15% of H1-H4 **[estimate]** | 760 |
| H7 | One European open-silicon event | Explicitly eligible per the Restack activity list **[fact]** | 500 |
| | **Subtotal** | | **11,100** |

### 4.3 Total

**EUR 18,400 + EUR 11,100 = EUR 29,500.**

Arithmetic check: 4,400 + 4,000 + 2,400 + 2,800 + 2,800 + 2,000 =
18,400. 2,240 + 300 + 800 + 1,700 + 4,800 + 760 + 500 = 11,100. Sum
29,500.

No F&A or overhead line appears, which sidesteps the FAQ's "F&A costs
are generally not considered eligible expenses" **[fact]**.

---

## 5. Milestone plan

MoU format: numbered tasks, each with an amount unlocked by publishing
the associated results **[fact]**. Every milestone is publishable
standalone, so a slip in a later one does not strand an earlier one.
Every milestone is work that will still be ahead of the project when an
MoU is signed (section 1.4a).

| M | Milestone (published artefact) | Unlocks | Target |
|---|---|---:|---|
| M1 | Redundancy-survival checker released as a standalone tool, with the construction catalogue and measured costs; upstream issues filed | T3 = 2,400 | MoU + 2 months |
| M2 | Gate-level and multi-bit fault-injection campaign public: harness, target-mapping method, results and coverage statement, RTL-vs-netlist divergence findings | T1 = 4,400 | MoU + 5 months |
| M3 | Second hardening wave public with its re-measured campaign and updated ranking; pointer redundancy measured rather than assumed | T2 = 4,000 | MoU + 7 months |
| M4 | Reproducible SG13G2 hardening flow public including the SRAM macro and ECC wrapper (a clean checkout reproduces the GDS); design submitted to the next available IHP-process shuttle | T4 + H1 = 5,040 | MoU + 9 months |
| M5 | Silicon bring-up report: silicon-vs-model lockstep, fault-tolerance demonstrator behaviour, flow lessons; bring-up software public | T5 + H2 + H3 + H4 = 5,600 | after boards arrive |
| M6 | Total-ionising-dose pre-screen dataset and report public: fixture, procedure, raw data, null results | H5 = 4,800 | M5 + 3 months |
| M7 | Integration guide, analysis scripts, final documentation; results presented at a European open-silicon event | T6 + H6 + H7 = 3,260 | M6 + 2 months |

Sum: 2,400 + 4,400 + 4,000 + 5,040 + 5,600 + 4,800 + 3,260 = **29,500**.

**Ordering rationale.** M1 is the cheapest, most certain and most
broadly useful milestone, and it is the one that carries the fund-level
contribution, so it goes first — it is also the one that is finished and
published before any hardware money is spent. EUR 10,800 across M1-M3
has been paid before H1's EUR 2,240 at M4, and EUR 21,440 before H5's
EUR 4,800 at M6.

**On the 12-month default.** M1-M4 fit inside 12 months of MoU signature
**[estimate]**. M5-M7 depend on shuttle silicon, whose arrival the
project does not control: on current ROADMAP dates, silicon lands
2027-06-25 and boards around 2027-08, which is compatible with an MoU in
2027-05 only if the shuttle holds. The FAQ permits "qualified
exceptions" to the 12-month default and the MoU allows donations to be
claimed "within a maximum of six months after the proposed end of the
project" **[fact]**; the proposed end date should be set with that
margin rather than optimistically. **[D-16]** — decide whether to name a
specific shuttle in the MoU annex or keep it as "the next available
IHP-process shuttle". Recommendation: keep it generic. Naming a shuttle
that then slips converts a schedule risk into a contractual one.

---

## 6. Risk register

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-1 | Application not funded | Medium-high (competitive; cut-off depends on round quality **[estimate]**) | Project continues self-funded at ROADMAP pace | Scope is deliverable without the grant, just slower; re-submission possible on the third of any odd month |
| R-2 | Restack budget exhausted before a later round ("expected early 2027" **[fact]**) | Medium | No second chance in this programme | Submit into the 2026-11-03 round, not a later one |
| R-3 | Radiation-campaign line challenged as ineligible | Medium | EUR 4,800 removed | Ask at an office hour before submitting ([D-12]); if it will not fly, drop M6 and reduce the ask. The method-led framing means the proposal survives losing this milestone, which the chip-led framing did not |
| R-4 | Cash flow: everything spent before reimbursement | High (structural **[fact]**) | ~EUR 11,100 personal exposure | Milestone ordering (section 5); M1 is pure effort and pays first |
| R-5 | Shuttle slip pushes M4-M7 beyond the MoU window | Medium | Milestones unpaid or renegotiated | Six-month post-end claim window **[fact, sample MoU]**; propose end dates with that margin; do not name a shuttle ([D-16]) |
| R-6 | SRAM macro integration does not close on the open PDK | Medium-high (a first attempt already failed **[fact]**) | T4 and M4 slip | Both blocking causes are upstream and identified; flip-flop weight storage keeps the core deliverable. Presented in the application as evidence of a diagnosed problem, not as an unexamined risk |
| R-7 | Tax treatment of the donation in Türkiye | Certain to need handling | Effective grant value reduced | The grantee "is responsible for paying any and all taxes" **[fact, sample MoU]**; obtain local advice before signing, not after |
| R-8 | Publication obligation collides with the private-repo posture | Certain | Blocks MoU signature, not submission | `docs/14-licensing-decision.md` — **unsigned, and its own 2026-08-31 sign-off date is two days away**. Must be closed before the application is sent |
| R-9 | A claim fails stage-2 verification | Low if disciplined | Score damage or rejection | Every figure here is tagged and traceable; all counts re-run on 2026-08-29 (section 9.2); section 10 lists the documents whose numbers must not be quoted |
| R-10 | Positioning language drifts above the export-safe threshold | Low | Serious and irreversible once submitted and published | docs/05 section 4 applied sentence by sentence; re-check at final review ([D-17]). Specifically: do not import docs/04's "no SEL to 65 MeV·cm²/mg" claim sentence or docs/06's uncited ~200 krad figure |
| R-11 | The proposal is read as productisation rather than R&D and fails the stage-1 knock-out | Low under the section 2.1 framing **[estimate]** | Not reviewed at all | "Research and development as the primary objective" is a hard criterion **[fact]**; the method-led framing makes the R&D content the headline rather than a supporting argument |
| R-12 | A funded task turns out to be work already completed by MoU time | Medium (the decision is 3-5 months out and work continues) | Task struck or renegotiated | FAQ permits replacing such parts with other tasks rather than cutting the budget **[fact]**; every task in section 4.1 was chosen to be ahead of the project, and the ranking will name new targets by then |

---

## 7. Open decisions

**The one that blocks everything else** is at the top. The rest are
ordered by date.

| ID | Decision | Owner | Needed by | State |
|---|---|---|---|---|
| **D-0** | **Sign or reject `docs/14-licensing-decision.md`.** Its recommendation is CERN-OHL-W-2.0 for hardware sources, Apache-2.0 for software, CC-BY-4.0 for documents and data. Section 11 of that memo is an empty signature table and its own first deadline (2026-08-31) is upon us; the memo states that until it is signed, D-6 and D-7 stay open and "the application must not be submitted with a claim about the repository's public state". NLnet makes the licence a term of the MoU and publication the payment trigger for every milestone, so this is not a post-award detail. Note docs/06 names CERN-OHL-**S**; docs/14 recommends **-W** and gives the reason. Do not take licence names from docs/06. | developer | **2026-08-31** | **unsigned, overdue** |
| D-1 | Applicant name: legal name or alias | developer | 2026-10-27 | open |
| D-2 | Contact email address | developer | 2026-10-27 | open |
| D-3 | Phone number | developer | 2026-10-27 | open |
| D-4 | Apply as individual or via an entity | developer | 2026-10-27 | open |
| D-5 | Project name (recommendation: option A, changed) | developer | 2026-09-30 | open |
| D-6 | Website field value — depends on D-0 | developer | 2026-10-15 | blocked on D-0 |
| D-7 | Experience field: decide whether to reinstate the tt-um-lif-crossbar accuracy figure (see section 10 item 6), add public URLs, decide how explicitly to name adjacent programmes | developer | 2026-10-15 | open |
| D-8 | Confirm or replace the EUR 40/hour rate | developer | 2026-09-30 | open |
| D-9 | Produce the two attachments | engineering | 2026-10-27 | open |
| D-10 | Generative-AI disclosure answer for the form and, if applicable, the provenance log **and the explanation of why it was necessary** | developer | at submission | open |
| D-11 | Supply an OpenPGP key or not | developer | at submission | open |
| D-12 | Ask an office hour whether irradiation-facility time and instrumentation are eligible out-of-pocket costs (office hours are the last Wednesday of each month, 16:00 CET, NLnet's Matrix room; `https://nlnet.nl/officehour/`) | developer | 2026-09-30 | open |
| D-13 | Re-verify the form fields, `maxlength` values **and placeholders** after the call opens | developer | 2026-09-03 | open |
| D-14 | Resolve docs/02 open question 2 (Solderpad RTL reuse vs independent implementation) — determines whether "clean-room" may be used at all. docs/14 set 2026-09-02 for this | developer | 2026-09-02 | open |
| D-15 | Obtain a real Co-60 facility quote to replace the H5 estimate | developer | 2026-10-15 | open |
| D-16 | Name a specific shuttle in the milestone plan, or keep it generic (recommendation: generic) | developer | 2026-10-27 | open |
| D-17 | Final positioning-language pass against docs/05 section 4 before submitting | developer | 2026-10-27 | open |
| **D-18** | **Repository-level generative-AI disclosure convention** required by the policy for the life of the grant: the readme statement and the per-contribution provenance convention (section 3.12). Settle before the MoU, not after | developer | 2026-10-27 | **new** |
| **D-19** | **Confirm the requested amount changed from EUR 27,500 to EUR 29,500** and that the rebuilt task set of section 4.1 is the scope the developer intends to be bound to | developer | 2026-09-30 | **new** |
| **D-20** | **Accept or reject the method-led framing of section 2.1.** It changes the project name recommendation, the abstract and the milestone order. The alternative is the 25 August chip-led framing, which is recoverable from git history but does not survive section 1.4(a) unmodified | developer | 2026-09-30 | **new** |
| **D-21** | **Re-run `make -C formal everything` and confirm 45/45 PASS** before pasting the experience field. The AER pointer redundancy landed after the last full green run and two `aer_fifo` tasks were mid-flight when this revision was written (section 9.2). If any task does not close, say so in the challenges field rather than deleting the sentence | engineering | 2026-10-27 | **new, in progress** |

---

## 8. Submission checklist and dates

| Date | Action | Owner |
|---|---|---|
| **2026-08-31** | **D-0: sign or reject docs/14.** Everything downstream waits on it | developer |
| 2026-09-02 | D-14 closed (docs/02 open question 2) | developer |
| 2026-09-03 | Call opens. Re-fetch the form, re-verify fields, limits **and placeholders** (D-13), select the Restack call | developer |
| 2026-09-30 | D-5, D-8, D-12, D-19, D-20 closed | developer |
| 2026-10-15 | D-6, D-7, D-15 closed | developer |
| 2026-10-20 | Attachments drafted (D-9) | engineering |
| 2026-10-27 | Full package review: positioning pass (D-17), arithmetic re-check, character counts re-run, formal gate re-run (D-21), D-1..D-4, D-16, D-18 closed | developer |
| **2026-10-29** | **Submit.** Five days before the deadline, not on it | developer |
| 2026-11-03 12:00 CEST | Hard deadline **[fact]** | — |
| 2027-02 to 2027-04 | Expected decision window (3-5 months from the deadline **[fact]**) | — |

Rationale for 2026-10-29: the form accepts multiple versions before the
deadline and the last complete one is used **[fact]**, so early
submission costs nothing and removes deadline-day risk. The FAQ confirms
resubmission is routine: "There is no need for concern or to send us
emails, this happens all the time." **[fact]**

---

## 9. Character counts and the commands that produced every number

### 9.1 Field lengths

Counts of the exact text inside each `field:<name>` marker block, code
fences excluded, trailing newline excluded.

Measured on 2026-08-29 with the command below. **[fact]**

| Field | Characters | Advisory | Hard | Under advisory by | Hard headroom |
|---|---:|---:|---:|---:|---:|
| abstract | 1194 | 1200 | 1500 | 6 | 306 |
| experience | 2452 | 2500 | 10000 | 48 | 7548 |
| use | 2499 | 2500 | 10000 | 1 | 7501 |
| comparison | 3996 | 4000 | 10000 | 4 | 6004 |
| challenges | 4999 | 5000 | 12500 | 1 | 7501 |
| ecosystem | 2496 | 2500 | 10000 | 4 | 7504 |

Reproduce from the repository root:

```sh
count() { awk -v b="<!-- field:$1:begin -->" -v e="<!-- field:$1:end -->" \
  'index($0,b){s=1;next} index($0,e){s=0} s' docs/13-nlnet-application.md \
  | sed '/^```/d' | python3 -c \
  'import sys;print(len(sys.stdin.read().rstrip(chr(10))))'; }
for f in abstract experience use comparison challenges ecosystem; do
  printf '%-12s %s\n' "$f" "$(count $f)"; done
```

Every field is inside its *advisory* limit, with the hard limit left as
headroom rather than spent. If a later edit needs room, the abstract has
306 characters of hard headroom and the challenges field 7501 — but
spending them is a choice against the form's own instruction, not a free
move.

### 9.2 Provenance of every technical number in section 3

Run on 2026-08-29 at git HEAD `c5a5a6e`. **[fact]**

| Claim in the application | Command | Result |
|---|---|---|
| "45 SymbiYosys proof tasks across seven property sets" | enumerate the `[tasks]` blocks of `formal/*.sby` | 4 + 8 + 8 + 5 + 9 + 3 + 8 = **45** across 7 files |
| "144 cocotb tests" | `grep -c '@cocotb.test' hw/tb/test_*.py` | **144** across 8 modules |
| "195 Python tests" | `.venv/bin/python -m pytest -q` | **194 passed, 1 skipped** (195 collected) |
| The one skip | `pytest -q -rs` | `test_pointer_tmr_survives_the_real_hardening_flow` — "every LibreLane run on disk predates aer_fifo.v … re-harden to close this check". This is why the application makes no claim about the pointer redundancy |
| "On an identical 255-injection re-run, silent corruption fell from 35.7% to 18.8%"; "A 287-injection fault campaign" | `hw/tb/fi_campaign_results.json`; docs/16 sections 3.2 and 3.6 | 287 records in the log. 91/255 = 35.7% pre-hardening, 48/255 = 18.8% post-hardening on the same 255. **Current log totals: MASKED 79, CORRECTED 121, DETECTED 36, SDC 49, HANG 2 → 17.1%** |
| "362 netlist references to one replica, none to the other two" | `sw/tests/test_synthesis_guards.py` file header, citing `tt/runs/tt-harden/06-yosys-synthesis/` | 362 references to `cfg_a[`, zero to `cfg_b[` or `cfg_c[` |
| "84 of 84" ECC holds, "79 injections cross from MASKED to CORRECTED" | docs/16 section 4.1, cross-checked against the log | log confirms MASKED 79 and CORRECTED 121; 158−79 = 79 and 121−42 = 79 |
| "zero DRC, zero LVS, zero timing violations across three corners at 69.68% utilisation" | docs/15 section table for run `ihp-mix`, sourced from that run's `final/metrics.json` and `55-openroad-stapostpnr/summary.rpt` | 1,235 mapped flip-flops, 181,043 um² placed, 69.6756% utilisation, +0.6315 ns worst-corner setup slack, Magic DRC 0, Netgen LVS 0 |
| "eight RTL blocks" | `ls hw/rtl/*.v` minus the Tiny Tapeout wrapper | aer_fifo, lif_core, npu_regbank, pilot_top, scrub, secded_dec, secded_enc, tmr_voter |
| "nineteen confirmed findings" | docs/07 section 1 | "Nineteen findings survived verification: 5 high, 8 medium, 6 low." The 25 August draft said twenty |
| "one of them in my own funding material" | docs/07 F-4, F-9, F-10 | F-4 is in docs/06 (the funding document); F-9 and F-10 are in docs/04. The 25 August draft implied all three |

**Formal pass state at the time of writing — stated precisely, because
this is exactly the kind of claim stage 2 checks.** 43 of the 45 tasks
carried a `PASS` status on disk when this revision was written. The two
that did not — `aer_fifo_bmc` and `aer_fifo_cover` — needed
regenerating, because the AER pointer redundancy landed after the last
full green run and changed the properties those tasks check.

A full `make -C formal everything` was started on 2026-08-29 at 21:20.
By 22:15 it had returned `DONE (PASS)` for `aer_fifo_prove`,
`aer_fifo_prove_d4` and `aer_fifo_bmc`, with **no task reporting FAIL,
ERROR or UNKNOWN**, and `aer_fifo_cover` was at step 121 of its
150-step reachability depth after 36 minutes of solver time. That task
is now by far the most expensive in the suite: the pointer proofs put
six free per-cycle fault vectors into the state space, and the cover job
that used to take under four minutes has not closed in nine times that.
**[fact]**

Two consequences, both already applied. First, the application text says
"45 SymbiYosys proof tasks" — a count, which is true and verifiable from
`formal/*.sby` — and nowhere says "all green". Second, the cover job's
cost is itself worth knowing: it is the anti-vacuity check on the
pointer masking theorem, so if it does not close it is not a formality
being skipped.

**[D-21]** — let `make -C formal everything` run to completion and
confirm 45/45 before pasting. If a task does not close, say so in the
challenges field rather than deleting the sentence; a proof that is
recorded as bounded is evidence, and a proof that is quietly dropped is
the thing that costs a proposal its credibility.

---

## 10. Errors and stale numbers found elsewhere

Reported, not fixed — this document owns only itself. Ordered by how
badly each would damage the application if quoted.

1. **`docs/16-fault-injection-campaign.md` disagrees with its own
   results file.** Sections 3.6 and 4.1 state the campaign of record as
   39 DETECTED / 48 SDC / 0 HANG over 287 injections (16.7% SDC).
   `hw/tb/fi_campaign_results.json` at HEAD reads **36 DETECTED / 49 SDC
   / 2 HANG (17.1%)**. The AER pointer commit re-ran the campaign and
   did not update the prose. The extra SDC and the two HANGs are
   explained in `hw/rtl/aer_fifo.v` — the campaign's pointer targets now
   name the *voted wires* rather than the replica storage, so the
   campaign is measuring an unprotected node and says nothing about the
   new redundancy either way. Also stale in the same file: section 3.5's
   "34 telemetry mismatches" (log says 113) and "23
   detected_with_wrong_output" (log says 20).
2. **The AER pointer redundancy is in the RTL but is not yet
   demonstrated**, and three places read as though it were: docs/16
   section 5.2 and section 6 item 2, and docs/21 sections describing the
   pointers as the top-ranked silent corruptor. Nothing in the
   application claims it. Closing it needs the injection targets moved
   to the replica banks and a re-harden so
   `test_pointer_tmr_survives_the_real_hardening_flow` stops skipping.
3. **`docs/20-reharden-and-corners.md` headlines superseded physical
   numbers**: 1,155 flip-flops, 158,268 um², 60.91% utilisation,
   +6.436 ns. Those are the `tmr-reharden` run. docs/15 records the
   current `ihp-mix` run at 1,235 / 181,043 um² / 69.68% / +0.6315 ns
   and says explicitly that the earlier series is superseded. docs/20
   does not carry the correction. Anything quoting utilisation must use
   69.68% and the spare against the 70% planning criterion is **0.46%**,
   not 25%.
4. **`docs/00-index.md` is two hardening waves behind**: "37 SymbiYosys
   tasks across 6 property sets" (now 45 across 7), "six blocks carry
   property sets" (now seven), 52.4% utilisation, and a stale test
   count. `docs/19-ci-parity-borg.md` also states 37 tasks in two
   places.
5. **`hw/fpga/README.md` tables are pre-TMR-fix**: 1045 `TRELLIS_FF`,
   3449 `TRELLIS_COMB`, 47.87 MHz. Current is 1,235 / 5,559 /
   26.62 MHz per docs/20. The README's own later paragraph acknowledges
   part of the move but the tables above it were not updated.
6. **The 70.66% figure is unresolvable from this repository and
   collides with itself.** The 25 August draft claimed
   "70.66% classification accuracy" for tt-um-lif-crossbar. No artifact
   in this tree supports it; the underlying record lives in the
   `tt-um-lif-crossbar` tree. Separately, docs/15 and docs/17 both use
   **70.66%** for the *placement utilisation* of the same shipped chip.
   Two unrelated quantities of one design carrying the same number is a
   coincidence worth checking before either is published. The figure has
   been removed from the experience field pending [D-7].
7. **`docs/06-funding-and-shuttle.md` still carries three things that
   must not be lifted into the application**: "no space/SpaceWire/
   satellite-silicon precedent was found" (wrong, section 1.6); "Abstract,
   maximum 1,200 characters" presented as the hard limit (it is the
   advisory limit; the hard limit is 1500); and an A.8 abstract draft
   containing the word "clean-room", which D-14 has not authorised.
   B.6's physical numbers are also one generation stale.
8. **`docs/04-technology-and-flow.md` section 6 recommends a
   datasheet-level claim sentence containing "no SEL to
   65 MeV·cm²/mg".** No SG13G2-specific single-event-latch-up
   measurement exists anywhere in the repository, so that sentence sits
   against docs/05 section 4 rule 3's "no SEL/SEE guarantee language
   beyond what measured data supports". It must not reach public text.
   The same applies to docs/06's ~200 krad figure, which its own note
   marks as a secondary source with the primary paper not located.
9. **`ROADMAP.md`** still quotes the retracted 105,245 um² / 113.7% /
   88.5% tile arithmetic, still says "the default 2x2 pilot" six lines
   after the 4x2 decision, and still describes the formal programme as
   future work when seven property sets are live.
10. **`docs/21-pilot-datasheet.md` revision 0.1 predates three waves**
    of work and labels the pre-hardening 91 SDC / 35.7% distribution as
    the "current design". It is the single most quotable stale number in
    the repository and the one most likely to contradict the
    application if a reviewer reads both.
