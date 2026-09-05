# 13 — NLnet Restack application package

Date: 29 August 2026. **Rewritten 5 September 2026** against the
evidence that now exists.
Status: submission-ready draft. Every field of the live NLnet form is
drafted here in paste-ready form. Fields that still need a decision from
the developer are marked **[D-n]** and collected in section 7.
Owner of the submission act: developer. Owner of the technical text:
engineering.

Scope: this document is the instantiation of `docs/06-funding-and-shuttle.md`
part A against the *actual* form on nlnet.nl, verified on 2026-08-29 by
fetching the form markup directly. Where the live form disagrees with
any document, the live form wins and the delta is recorded in section 1.
All positioning language obeys the binding rules of
`docs/05-market-positioning.md` section 4 (fault-tolerant wording, LEO
10-30 krad(Si) class, no claim at or above 100 krad(Si), multi-market
framing, and rule 5's requirement that any published figure be traceable
to measurement or clearly labelled a target).

Labels: **[fact]** = traceable to a cited source or a command run on the
stated date; **[estimate]** = inference or project judgement; **[D-n]** =
open decision for the developer.

> **What changed in this revision, and why it had to change.**
>
> The 29 August draft was written when the strongest claim this project
> could make was a frozen pilot tile, a 255-injection before-and-after,
> and a synthesis defect. Between 2026-08-31 and 2026-09-05 —
> **six calendar days** — `docs/35` through `docs/68` landed **[fact,
> `git log --diff-filter=A -- docs/`; `docs/68` is in the working tree
> and not yet committed at the time of writing]**. The project now has
> seven fault-injection campaigns with paired counterfactuals across five
> named populations, formal proof against the RISC-V ISA, a
> placed-and-routed SoC, power measured under a mission duty cycle, and
> a documented practice of publishing the results that came out
> negative.
>
> **Three consequences, in descending order of how much they change the
> application.**
>
> 1. **Section 1.4(a) — NLnet cannot pay for work completed before the
>    grant — now strikes four of the six previously proposed tasks, not
>    two.** T2's second hardening wave has been run four times over;
>    gate-level injection exists for the pilot; the SRAM blocker has
>    been examined again and narrowed. Section 4 rebuilds the task set
>    around what is genuinely ahead of a mid-2027 MoU.
> 2. **The evidence the application rests on is now measured at SoC
>    scale**, not at block scale, and the fields in section 3 are
>    rewritten from measurements rather than from documents. Section 9.2
>    re-derives every figure.
> 3. **Two prohibitions bind every field.** `docs/53` section 9.2 and
>    `docs/60`: **no clock frequency may be published.** `docs/12`
>    section 8 and `docs/54`: **nothing may imply the SoC is
>    manufacturable today** — the SRAM macros cannot be signed off on
>    this PDK version and the SoC layout has never been through Magic
>    DRC, LVS or XOR. The pilot is a separate and defensible claim and
>    the fields keep the two apart sentence by sentence.
>
> The requested amount moves from EUR 29,500 to **EUR 29,685**, because
> H1 was corrected against `docs/37`'s finding that every tile-only
> figure in this repository omitted the devkit and the shipping. See
> [D-19].

---

## 1. What was verified on nlnet.nl

### 1.1 The live form: fields and hard limits

Verified 2026-08-29 by retrieving `https://nlnet.nl/propose/` and reading
the raw form markup. **[fact]** The deadline text: calls reopen
**2026-09-03**, deadline **2026-11-03 12:00 CEST (noon)**. **[fact]**

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
**`abstract`**, `used_ai`, `consent`. **[fact]**

Form guidance, verbatim, printed above the free-text fields: "Please be
short and to the point in your answers; focus primarily on the what and
how, not so much on the why. Add longer descriptions as attachments (see
below). … Do stay concrete. Use plain text in your reply only, if you
need any HTML to make your point please include this as attachment."
**[fact]**

The abstract's own label asks two questions: "Can you explain the whole
project and its expected outcome(s). **Have you been involved with
projects or organisations relevant to this project before? And if so,
can you tell us a bit about your contributions?**" **[fact]** The
abstract draft in section 3.4 answers the second in its closing
sentence.

### 1.2 Advisory limits, not just `maxlength`

**The form states both a hard limit and a much lower advisory limit, and
they disagree by a factor of up to four.** **[fact]**

| Field | Advisory (placeholder) | Hard (`maxlength`) |
|---|---:|---:|
| abstract | 1200 | 1500 |
| experience | 2500 | 10000 |
| use | 2500 | 10000 |
| comparison | 4000 | 10000 |
| challenges | 5000 | 12500 |
| ecosystem | 2500 | 10000 |

**Why this is treated as binding rather than as guidance.** Three of the
placeholders say "be concise" in as many words; the printed guidance
says "be short and to the point"; the FAQ says a proposal should take
"less than an hour" to complete; and the foundation "processes thousands
of grant applications every year". Cost effectiveness is 30 % of the
score and reviewer attention is the scarce resource. **Every field in
section 3 is written to the advisory limit.** The hard limits are
recorded in section 9 as headroom, not as budget.

**Attachment guidance, verbatim**: "Attachments should only contain
background information, please make sure that **the proposal without
attachments is self-contained and concise**. Don't waste too much time
on this. Really." **[fact]** Hence two lean attachments, section 3.11.

### 1.3 Everything else verified, and it all still holds

Re-fetched and re-read on 2026-08-29 and cross-checked by `docs/37` on
2026-08-31. **[fact]**

1. **Restack rules** (`https://nlnet.nl/restack/guideforapplicants/`):
   weights 30 % technical excellence/feasibility, 40 %
   relevance/impact/strategic potential, 30 % cost effectiveness; "The
   total weighted score of projects has to be above 5.0 (out of 7) to
   pass to the next stage"; "a **first proposal** MAY request a grant
   allocation up to **50 kEuro**"; "All scientific outcomes must be
   published as open access, and any software and hardware must be
   published under a recognised open source license in its entirety."
2. **Stage-1 knock-out criteria**, verbatim: proposals "should be in
   line with the goals of Restack", "should have **research** and
   **development** as their **primary** objective", and "should satisfy
   any other hard eligibility criteria specific to the sub-granting
   call, such as having a clear **European Dimension**". The FAQ: "It is
   a **knock-out criterion** for each project to have a 'European
   dimension'." A proposal that reads as productisation rather than R&D
   fails before it is scored.
3. **Programme size and budget pressure**: Restack "will competitively
   award **7 million euro** worth of grants"; new calls run "until the
   budget of the programme has been fully allocated (**expected early
   2027**)". This is the strongest scheduling fact in this document and
   the reason to submit into this round rather than a later one.
4. **Decision lag.** NLnet states "between three and five months …
   counted from the date of the deadline of the open call" **[fact that
   NLnet states this]**. Its own 2026 announcements do not run at that
   rate: the **2026-03-02** announcement decides the **August 2025**
   call (**213 days, 7.0 months**) and the **2026-04-09** announcement
   decides the **October 2025** call (**190 days, 6.3 months**); the
   wider 2026 set falls in a **4.3-6.5 month** band (`docs/37` section
   2). **Expected decision on a 2026-11-03 submission: 2027-03 to
   2027-06, MoU after that. [estimate — a projection from two verified
   data points, explicitly not what the funder advertises.]** The
   milestone arithmetic in section 5 is read against an MoU in mid-2027.
5. **Cadence**: deadlines are "the third day of every odd month".
6. **Payment mechanics** (`sample_MoU.pdf`): "There is a donation amount
   attached to each task, which you unlock by publishing the associated
   results"; public progress reporting "every two months" plus "a public
   status page for the project"; the grantee "is responsible for paying
   any and all taxes or other fees with regard to this grant"; donations
   "may be claimed up to the reserved amount within a maximum of six
   months after the proposed end of the project".
7. **Eligible-activity list** does not name silicon fabrication,
   instrumentation or irradiation-facility time. They fall under
   "out-of-pocket costs for infrastructure essential to achieving the
   above" by construction, not by name. Precedent supports it
   (Chips4Makers), but this is the line most likely to be questioned in
   stage 2. See [D-12].
8. **Precedent projects** all live and returning HTTP 200 on
   2026-08-29, two with public source URLs. The correction of `docs/06`
   A.4's "no space precedent" stands (section 1.6).

### 1.4 Two things that shape the plan, and one of them now bites harder

**(a) NLnet cannot pay for work already done.** FAQ, verbatim: "A grant
can only cover the period between the proposal being officially selected
and the agreed end of the Memorandum of Understanding. **We cannot make
donations for any effort completed prior to the grant.**" **[fact]** The
mitigation offered: "Should we select your project, we can discuss
replacing those parts with other tasks (rather than reducing the
budget)," with the advice "just to continue working on the project to
the extent possible, as if our foundation and the entire grant
application didn't exist."

**This clause is now the single largest constraint on what may be
proposed, and it is a consequence of the project's own rate of
progress.** The 25 August draft lost T1 and T2 to it. The 29 August
draft's replacement task set has lost four of six in one week:

| 29 August task | State on 2026-09-05 | Verdict |
|---|---|---|
| T1 Gate-level and multi-bit fault injection | Gate level exists for the pilot and agrees with RTL on **370 of 370** comparable injections (`docs/32`). Multi-bit does not exist anywhere; SoC-scale gate level does not exist | **Rescoped, not struck** — section 4.1 T1 |
| T2 Second hardening wave from the ranking: queue storage, output adapter, dispatcher | Queue storage closed (`docs/29`), dispatcher closed (`docs/30`), and four further waves have run since on structures that did not exist when the task was written (`docs/55`, `docs/56`, `docs/58`, `docs/67`) | **Struck.** Done, and more than was asked |
| T3 Redundancy-survival checker as a standalone tool | Not started. The check exists for this design only | **Kept unchanged** |
| T4 SRAM macro and ECC wrapper sign-off | Re-examined. `docs/54` reproduces the count three ways, shows it is 100 % a property of the vendor cell as shipped, refutes the working hypothesis about the marker, and drafts two upstream reports. **The blocker has not moved** | **Rescoped to the upstream work** — section 4.1 T4 |
| T5 Silicon bring-up | Ahead of the project | **Kept** |
| T6 Documentation, dataset publication, reporting | Ahead of the project | **Kept** |

A reviewer doing "independent verification of facts, methods and claims"
would find the public repository and see all of this. Section 2.2
rebuilds the scope around work that will still be ahead of the project
when an MoU exists.

**(b) The generative-AI policy has a second half that outlives the
submission.** The policy
(`https://nlnet.nl/foundation/policies/generativeAI/`, version 1.1,
valid from 2026-01-26) governs **project development** for the life of
the grant. **[fact]** Verbatim: "For any *substantive* use of GenAI that
materially affects outputs, public disclosure is required"; a codebase
"declares, typically in its 'readme', broadly how GenAI is used";
"Generated content should be marked as such … Specify which model was
used, (including version), and how it was used." Non-compliance "may
result in rejection of the proposal or ultimately in the termination of
the running grant."

The FAQ is blunter: "**The short answer is: no.** … Please grant us the
courtesy of writing the proposal yourself. If you do use generative AI
to write (part of your) proposal, please put this in the text **and
explain why this was necessary**. Failure to do so is likely to result
in the proposal being rejected, and tarnishing your reputation."
**[fact]** The required disclosure is a log *and a justification*.

One clause reads in the project's favour: "NLnet is a strong proponent
of automation and of deterministic and reproducible generation of source
code, formal and symbolic proofs, etc. based on specifications and
scientific and engineering rigour." **[fact]** The generated register and
memory maps, the golden-model refinement and the SymbiYosys programme
sit squarely inside what the policy says it wants.

See [D-10] and [D-18].

### 1.5 Two more constraints

- **Default project duration is 12 months**, with "qualified exceptions"
  possible. **[fact]** The milestone plan in section 5 fits M1-M4 inside
  12 months of MoU signature by construction.
- **F&A costs are generally not eligible**, capped at 25 % when they
  are. **[fact]** Nothing in this budget is an overhead line.

### 1.6 Precedent correction

`docs/06` A.4's "no space/SpaceWire/satellite-silicon precedent was found
in the funded-projects list" is wrong, and `docs/06` has not been
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

The form was inspected with no call open. Field sets and limits can be
call-specific. Before writing into the live form: re-fetch the page,
re-read every `maxlength` **and every placeholder**, and confirm the
advisory limits in section 1.2 are unchanged. Owner: developer.
**[D-13]**

---

## 2. Funded scope

### 2.1 The application leads with the method, and the method now has a much larger record behind it

The 29 August draft argued for a method-led rather than a chip-led
framing. **That judgement stands and the evidence for it has grown by an
order of magnitude.** The four reasons are unchanged in shape and
stronger in substance.

1. **It is the only framing that survives section 1.4(a)**, and that
   clause has just struck four of six tasks. The chip's building blocks
   do not merely exist — the SoC around them has been synthesised,
   placed, routed, powered and measured. The method's next steps are
   genuinely future work; the chip's are largely past.
2. **It scores on the 40 % criterion.** A hardened neuromorphic tile has
   a narrow constituency. A defect class that silently deletes
   redundancy from *any* yosys-synthesised design has the constituency
   of every open hardening effort in the fund's own portfolio. This
   project has the measurement, the repair, the mechanical check and now
   a second contribution of the same shape: **the open PDK's SRAM
   macros cannot be signed off**, which blocks every open design on
   SG13G2 that wants a memory, and `docs/54` has narrowed it to one
   answerable question.
3. **The evidence is strongest there, and it is now strong in a
   specific way that is rare.** The method is not "we injected faults".
   It is: **every protective mechanism is reported against a replay of
   the same upsets with that mechanism removed by an asserted
   substitution.** `docs/42` established the pattern and every campaign
   since has run it. That is what turns "the watchdog escalated" into a
   catch rate, and it is what produced this project's most useful
   results — including the ones where the answer was no.
4. **It de-risks the budget.** If the reviewers strike the irradiation
   line ([D-12]), a method-led proposal loses one milestone and keeps
   its spine.

**What is new in this revision's framing, and it is the sharpest thing
the application has:** this project publishes the mechanisms that did
not work, in the same document as the ones that did, with the same
denominators.

- `docs/43` built a **windowed watchdog** because `docs/42`'s
  measurement asked for one. It caught **0 of 30** dead machines and
  produced **7 spurious escalations**. `docs/46` re-ran it against a
  second workload — a PMP-isolated partitioned supervisor — and
  measured its benefit at **0.25 % [0.07-0.89]** against its cost at
  **0.27 % [0.08-1.00]**, from one site each, and recommended removing
  it.
- `docs/49` built **SYNPRE** after `docs/48` promoted it from declined
  to first, and found it acts on a cone disjoint from the binding path,
  so a perfect free version could do **nothing** to the worst slack.
  `docs/62` re-asked it when the cone changed and measured it **worse
  than when it was on the wrong cone**. Three documents priced the same
  parameter and the price rose each time.
- `docs/48` built two more floorplans to test `docs/47`'s own closing
  hypothesis and **refuted it**: both were worse at every stage
  measured.

A reviewer who checks one claim and finds it inflated discards the rest,
and stage 2 does exactly that check. A project whose record contains its
own refutations is the cheapest kind to verify.

**What the framing must not do:** Restack funds "technology building
blocks" and "libre chips", so a pure methodology proposal is a worse fit
than an IP block. The method is the spine and the fault-tolerant SoC is
the instantiation that proves it and carries it to silicon — both are in
the abstract, in that order.

### 2.2 What the grant actually buys

- The funded scope is neither the SoC nor the already-built blocks. It
  is: **multi-bit and gate-level fault injection at SoC scale**; the
  **redundancy-survival checker released as a tool** others can run on
  their own netlists; **closing the SoC's timing constraint or replacing
  the target with a workload-derived requirement**; **the open PDK's
  SRAM sign-off blocker worked upstream**; **silicon on a community
  shuttle with bring-up against the published suite**; and **the first
  public total-ionising-dose data for `sg13g2_stdcell`-based digital
  logic**.
- The remaining interface set — SpaceWire, CAN, SPI, I2C — continues on
  the ROADMAP outside the grant and appears in the application as
  context, never as a deliverable. Two of the four candidate cores are
  LGPL and `docs/14` section 5.2 argues that is a bad fit for silicon;
  that decision is not one to make with a funder's money.
- `ROADMAP.md` P3 no longer carries an hour roll-up to cite here, and
  the reason is worth stating because it is the honest one: **this
  project measures the area, timing, power and fault response of
  everything it builds and has never recorded how long any of it took.**
  The task hours in section 4.1 are therefore **[estimate]** with no
  measured base under them, and section 6 R-13 carries that as a risk
  rather than hiding it.

### 2.3 European dimension — the stage-1 knock-out

Türkiye is associated to Horizon Europe for 2021-2027, which puts the
applicant in the priority group rather than on the exception path
(`docs/06` A.3, re-verified `docs/37`) **[fact]**, so the criterion is
satisfied on residence alone. The substantive case is carried by the
ecosystem field: the target PDK is IHP's, a German Leibniz institute's;
fabrication is in Frankfurt (Oder); the flow is LibreLane/OpenROAD and
yosys; the checker's first users are NLnet-funded European silicon
projects on the same tools; and the SRAM sign-off blocker is a defect in
a European open PDK that this project has already characterised twice.

---

## 3. Field drafts (paste-ready)

Convention: text inside a `field:<name>` marker block is exactly what
gets pasted into the corresponding form field. Character counts are in
section 9 and reproducible with the command given there.

**Two prohibitions were applied to every block, sentence by sentence.**
No clock frequency appears anywhere (`docs/53` section 9.2, `docs/60`).
Nothing states or implies that the SoC is manufacturable today: the
pilot's sign-off and the SoC's absence of one are kept in separate
sentences, and the SoC's is stated as a limitation rather than omitted
(`docs/12` section 8, `docs/54`).

### 3.1 Contact information

| Field | Value | Status |
|---|---|---|
| Name of the applicant | — | **[D-1]** legal name or alias. Recommendation: legal name — the prior-work evidence is attached to it. |
| Email address | — | **[D-2]** a project address, not a personal one. |
| Phone number | — | **[D-3]** international format. |
| Organisation | — | **[D-4]** blank (individual) vs a registered entity. Recommendation: apply as an individual and decide the entity question separately. |
| Country of residence | Türkiye | Fixed. Associated to Horizon Europe 2021-2027. **[fact]** |

### 3.2 Project name (limit 100)

**[D-5]** — pick one.

| Option | Text | Chars | Note |
|---|---|---:|---|
| A (recommended) | `Measured fault tolerance for open silicon` | 41 | Names the contribution. Legible to a non-specialist, and it is not a claim. |
| B | `Verifiable redundancy for open silicon: fault-injection-ranked hardening on SG13G2` | 81 | Most precise. Longer and more jargon-dense. |
| C | `Open fault-tolerant neuromorphic inference IP for small satellites` | 66 | Chip-led, which section 2.1 argues against. |
| D | `Neuromorphic Space SoC` | 22 | Matches the repository name, but promises the whole SoC. |

### 3.3 Website (limit 100)

**[D-6]** — blocked on `docs/14-licensing-decision.md`. That memo was
rewritten 2026-09-05 to be decidable in one sitting, and its section 0
records that it now blocks the **TTIHP26b shuttle push on 2026-09-21**
before it blocks this application. If it is signed for the shuttle, this
field has a real URL by the end of September. Options in order of
preference: (a) public repository URL; (b) a static project page listing
the public artefacts; (c) the existing public Tiny Tapeout project page
for `tt-um-lif-crossbar`; (d) blank.

### 3.4 Abstract (advisory 1200, hard 1500) — required field

Positioning check applied sentence by sentence: "fault-tolerant" is used
and "rad-hard" is not; the total-dose class is stated as LEO
10-30 krad(Si); no figure at or above 100 krad(Si) appears; no clock
frequency appears; nothing implies the SoC is manufacturable.
"Clean-room" does not appear — `docs/02` open question 2 is still open
(`docs/14` section 5.1), so the word is not a fact this project can
assert. See [D-14]. The closing sentence answers the second half of the
field's own label.

<!-- field:abstract:begin -->
```text
Open silicon can add redundancy and lose it silently: synthesis merged this design's triple-redundant configuration register into one bank - 362 netlist references to one replica, none to the other two - while RTL injection reported it working. Any yosys design can hit it.

The method: injection that ranks structures by measured silent corruption; hardening chosen from that ranking; every mechanism replayed against the same upsets without it; and a netlist check that counts redundant banks, not source names. Seven campaigns. It also refutes: a windowed watchdog the measurement asked for caught 0 of 30 dead machines, and that is published.

The chip: an open fault-tolerant SoC on IHP's SG13G2 - a RISC-V core with ECC-protected register file, memory and time base, and an event-driven spiking engine - verified against bit-exact golden models and against the ISA with riscv-formal.

The grant takes injection to multi-bit and gate level at SoC scale, releases the check as a tool, works the SRAM blocker upstream, and reaches silicon for a total-dose pre-screen in the LEO 10-30 krad(Si) class, where no public data exists. Free-licensed. Prior silicon: tt-um-lif-crossbar on Tiny Tapeout.
```
<!-- field:abstract:end -->

**On the 362, and why the abstract still leads with it.** It is the
oldest measured claim in the application and the most transferable: it
is a property of the toolchain, not of this design. It is checkable in
one command from the published repository
(`sw/tests/test_synthesis_guards.py` cites the run directory), and it is
the claim that gives the tool of T2 its constituency.

**On what the abstract no longer says.** The 29 August draft quoted
"silent corruption fell from 35.7 % to 18.8 %" on an identical
255-injection re-run. That pairing is still true of those 255
experiments, but `docs/64` has since named the **378-injection file at
blob `312d3c76` the campaign of record** for the pilot, and the SoC-scale
campaigns of `docs/42`, `docs/43`, `docs/52`, `docs/55`, `docs/56` and
`docs/58` are both larger and more recent. Quoting a superseded pairing
next to newer work invites exactly the stage-2 finding this project
cannot afford, so the abstract quotes a **count of campaigns** and one
**negative result**, and leaves the rates to the experience field where
their denominators can be stated.

### 3.5 Previous relevant experience (advisory 2500, hard 10000)

Every claim is checkable, which is the point — stage 2 verifies. Counts
were produced by running the suites on 2026-09-05, not by quoting a
document (section 9.2).

<!-- field:experience:begin -->
```text
I design fault-tolerant digital silicon with open tools, solo, and I ship it.

Silicon: tt-um-lif-crossbar, an 8x8 leaky-integrate-and-fire neuron crossbar on a 2x2 Tiny Tapeout tile in SkyWater 130 nm, through the open RTL-to-GDS flow. It is the direct ancestor of the inference engine here.

Where this project stands, all of it checkable. A RISC-V SoC: an Ibex core with a SECDED-protected register file, an APB peripheral bus proved compliant by k-induction, protected memory and monotonic time base, an escalating watchdog, GPIO, a QSPI flash controller verified against a behavioural W25Q128JV built from the vendor datasheet, and a spiking inference engine fed its weights from that flash. Verification: 437 Python tests against frozen bit-exact golden models, 373 cocotb tests, and 110 SymbiYosys proof tasks over 22 property sets. riscv-formal against the core passes 70 of 79 bounded checks and 79 of 79 cover obligations; it found five defects and not one is in Ibex's execution - three are mine, one is a deviation in Ibex's trace port, and one is in riscv-formal itself, whose division and remainder models compute an unsigned result.

Fault tolerance is measured, not asserted: seven injection campaigns, each mechanism replayed against the same upsets with it removed. Design-weighted silent corruption in the core fell from 2.8% +/- 1.6 to 1.3% +/- 0.4; 128 of 128 upsets in the time base are corrected where the unprotected design displaced the clock 95 times and announced none.

Physical: the 6x2 pilot tile signs off on IHP SG13G2 with every geometric counter at zero and three corners met with a 5% derate the flow itself omits. The full SoC is placed and routed whole with six SRAM macros and zero detailed-route DRC errors - but it misses its timing constraint, and the vendor macros cannot be signed off on this PDK version, which is a defect I have characterised twice and reported upstream.

I also publish what did not work: a windowed watchdog my own measurement asked for caught 0 of 30 dead machines and was removed, written up beside the mechanisms that worked, with the same denominators.

Method: spec-first. Golden models before RTL. An assumption ledger shipped with the proofs. Review discipline: an independent review of the research phase produced nineteen confirmed findings, including three misattributed radiation citations, one in my own funding material. All corrected before this application.
```
<!-- field:experience:end -->

**[D-7]** — before pasting: (a) the `tt-um-lif-crossbar` accuracy figure
stays **removed** (section 10 item 6); (b) add public URLs for the Tiny
Tapeout design and, if `docs/14` lands, for this repository; (c) decide
whether to name the adjacent programmes explicitly.

**[D-22, updated]** — the timing sentence now cites the frozen `6x2`
sign-off rather than any superseded run, and the derate clause is backed
by `docs/31`. **Do not quote a derated corner as met from any run whose
slow corner has not been re-derived.** The SoC sentence is deliberately
negative and must stay so.

### 3.6 Requested amount

**EUR 29,685.** Inside the 5,000-50,000 window and inside the
first-proposal ceiling of 50 kEUR **[fact]**. Changed from EUR 29,500
because H1 was corrected: `docs/37` established that every tile-only
cost figure in this repository omits the **EUR 300 devkit PCB** and
**EUR 15 shipping**, and H1 had inherited that omission. See [D-19].
Re-derived line by line in section 4.

### 3.7 Budget explanation and other funding sources (advisory 2500, hard 10000)

<!-- field:use:begin -->
```text
Rate: EUR 40/hour, the same for every task. 460 hours, plus EUR 11,285 of out-of-pocket costs effort cannot replace. No overhead lines.

Developer time - EUR 18,400 for 460 h

T1. Multi-bit and gate-level fault injection at SoC scale (120 h, EUR 4,800). Every campaign so far is single-bit and at register-transfer level; gate level exists only for the small tile, where 370 of 370 comparable injections agreed. This moves both to a placed design of 42,518 cells and adds multi-bit upsets, adjacency taken from placement, not bit index.

T2. Redundancy-survival checker as a standalone tool (60 h, EUR 2,400). The bank-counting check generalised so any yosys or LibreLane project can run it on its netlist, published with the catalogue of repair constructions and their costs, plus upstream issues with reproducers.

T3. Closing the timing constraint, or replacing the target (90 h, EUR 3,600). Four candidate remedies are measured and closed, two of which made it worse. What is left is register-transfer work, and a workload-derived requirement to replace a target whose provenance is a tile, not a mission.

T4. The PDK's SRAM signoff blocker, worked upstream (70 h, EUR 2,800). No design on this open PDK can sign off with a vendor memory macro. I have characterised it twice and narrowed it to one question a foundry must answer. This works it upstream, not around it.

T5. Silicon bring-up (70 h, EUR 2,800). Host software, silicon-vs-model lockstep on the fabricated part, demonstrator, results memo.

T6. Documentation, dataset publication, public reporting (50 h, EUR 2,000). Integration guide, radiation dataset with analysis scripts, and the two-monthly reports and status page the MoU requires.

Out-of-pocket - EUR 11,285

H1. Shuttle tiles, devkit and shipping, follow-up run = 2,555.
H2. Spare carrier board = 150.
H3. Breakout and test PCB, two revisions, fab and assembly = 800.
H4. Instrumentation: FPGA host 400, logging supply 900, logic analyser 250, cabling 150 = 1,700.
H5. TID pre-screen: Co-60 facility 3,500, fixture and spares 400, shipping and dosimetry 900 = 4,800.
H6. Import duties = 780.
H7. Travel to one European open-silicon event = 500.

Total: 18,400 + 11,285 = EUR 29,685.

Other funding, past or present: none. The work so far and the first shuttle entry are self-funded.

Cash flow: payment follows publication, so everything is spent before reimbursement. Milestones are ordered so the largest out-of-pocket items sit behind ones already paid.
```
<!-- field:use:end -->

**[D-8]** — the EUR 40/hour rate is a placeholder and must be confirmed
or replaced before submission. It is the number stage 2 is most likely
to interrogate. Changing the rate changes the hours, not the total,
unless the scope moves with it.

**[D-15]** — H5 (EUR 4,800) still rests on an unquoted facility price.
`docs/06` action item 7 owns "identify a Co-60 TID facility and obtain
quotes"; it is still open. A real quote must replace the estimate before
submission, or the line must be re-scoped.

### 3.8 Comparison with existing or historical efforts (advisory 4000, hard 10000)

<!-- field:comparison:begin -->
```text
The gap, first. Open neuromorphic hardware exists; open fault-tolerance research, open flows and open PDKs exist; proprietary radiation-hardened neuromorphic silicon exists. What does not is an open fault-tolerant design whose hardening was chosen by measurement, whose redundancy is checked mechanically against the netlist that gets fabricated, and whose proofs, flow scripts, negative results and radiation data are all published.

On method. RTL fault injection is standard practice and I claim nothing new about it. Three things here are not. First, injection produces a ranking of structures by measured silent-corruption contribution, and the hardening is chosen from that ranking rather than from intuition - which matters, because the instinct is measurably wrong: the largest structure in the engine's event path is 41% of its flip-flops and contributed zero, while nine of 140 flip-flops carried 96% of the silent corruption in their stratum. Second, every mechanism is reported against a replay of the same upsets with it removed by an asserted substitution, because "the watchdog escalated" is not a catch rate until the same upset on the same machine with no backstop says whether the machine was dead. Third, the redundancy is verified in the netlist rather than the RTL. That check exists because RTL injection reported this design's configuration TMR working while yosys had merged the three replicas into one bank: the netlist that fed a harden carried 362 references to one replica and none to the other two. RTL simulation cannot see a structure synthesis deletes, and marking the replicas "keep" does not fix it: the wire names survive, the storage does not. Every open hardening effort on this toolchain is exposed. NLnet has funded fault-injection methodology before (FPGA Fault Injection Testing) and open silicon on this PDK; this joins the two.

Open spiking-neural-network hardware. ODIN, tinyODIN and ReckOn (UCLouvain) are the open reference designs, released under Solderpad. Excellent microarchitectures. What they are not: fault-tolerant - no ECC, no TMR, no scrubbing, no fault counters - not taken through an open PDK to characterised silicon, and not accompanied by radiation data. Loihi and SpiNNaker are not open silicon at all.

Proprietary reference, stated honestly. Frontgrade Gaisler's GR801 is what this project is measured against: a radiation-hardened SoC on 28 nm FDSOI pairing a fault-tolerant NOEL-V RISC-V core with licensed BrainChip Akida IP. It is better than this project on almost every technical axis - FDSOI with intrinsic latch-up immunity, megabytes of on-chip SRAM against this design's tens of kilobytes, SpaceWire, PCIe, a qualification path and a sales channel. I am not proposing to compete with it. What it cannot do is let an integrator read the RTL, re-run the verification, or reproduce the fault-tolerance evidence, and it will not be affordable to a university CubeSat programme. The same holds for Microchip PIC64-HPSC and AMD Versal XQR.

NLnet-funded open silicon. Libre-SOC is closest in ambition and taped out at 180 nm, but is a general-purpose processor with no fault tolerance; its precedent is that open SoC work of this shape can be delivered. GLOW-SG13G2 is building an open cell library for the process I harden on: I am a consumer of that layer, not a competitor. Borg II has reached silicon on IHP 130 nm, evidence the flow closes. All synthesise with yosys, the population the checker is for - and any that ever wants an on-chip memory macro hits the blocker T4 addresses.

Closest funded precedent. The Space grade Instrumentation Amplifier ASIC is building a programmable-gain amplifier on IHP's open PDK, made robust for low earth orbit - the analog front end of the same signal chain whose digital back end I propose. I would like to coordinate: shared irradiation campaigns are far cheaper per part than separate ones, and a common fixture and dose-reporting convention would make both datasets comparable.
```
<!-- field:comparison:end -->

### 3.9 Significant technical challenges (advisory 5000, hard 12500)

The largest field on the form and where the honest engineering risks
belong; stage 2 asks "how will you approach complicating factor X"
**[fact]**. Six items, cut down from eight to fit the advisory limit:
netlist injection and multi-bit adjacency are now one item because they
share a method, and the solo-schedule risk was dropped from here because
it is not a technical challenge and is already answered where it
belongs, in the milestone ordering of section 5 and the cash-flow line
of the budget field.

<!-- field:challenges:begin -->
```text
1. Injecting faults into a netlist rather than RTL, at SoC scale, and modelling multi-bit upsets physically. RTL injection has a stable target list of named registers; after synthesis those names are gone, one register may be several cells or none, and the design is 42,518 cells. A multi-bit upset hits cells near each other on the die, not bits near each other in a bus. Approach: build the target list from the flow's own name mapping, keep the RTL campaign as a cross-check, treat any structure in one list and not the other as a finding rather than noise, and derive adjacency from placed coordinates already parsed out of the design's own DEF by a self-checking script. On the small tile 370 of 370 comparable injections classified identically; it will degrade with scale. Where mapping is lost, report coverage rather than shrink the denominator - one site census read 64.9% from a regex that folded eight queue slots into one. A model-derived multi-bit result is weaker evidence than a beam: a screening tool that says where to look, not a rating.

2. Redundancy that survives an optimiser determined to remove it. The three-replica configuration bank was merged into one, and the obvious fixes fail: a keep attribute preserves the wire name while the storage collapses, and per-replica polarity is bounded at two banks because a stored bit has two polarities. What works is each replica storing a different invertible function of the same data, so no per-bit structural hash matches one replica to another - with a measured limit: for a one-bit rail the transform is provably unreachable at the netlist, since the library has no reset-to-1 flip-flop. Approach for the tool: publish the catalogue - what fails, what works, what each costs - and count flip-flop cells in the final netlist, trusting no attribute and never skipping on the symptom it exists to catch.

3. Proving what is load-bearing rather than what is easy. The properties that matter in orbit are recovery properties: a state machine started from an arbitrary corrupted state returns to a legal state in bounded time without violating an interface contract; a voter masks any single corrupted replica; a codec corrects every single-bit error and never silently miscorrects a double. Approach: unconstrained-initial-state induction for recovery, exhaustive bounded proof with a weight-constrained symbolic error mask for the codec, and a free symbolic fault for the voter. Where induction does not close, strengthen the invariant rather than weaken the property. One gap is open and documented: the property that a protected register reads back what was written closes at one bound and times out at the next under all six engines the suite offers, with three routes ranked.

4. The open PDK cannot sign off a design containing its own SRAM macro. Not my design's defect, and it blocks every open project on this process that wants on-chip memory. Both blocking decks were characterised: over a million geometry error boxes from one and thousands from the other, all inside vendor geometry with my flow contributing zero, plus an LVS hierarchy-naming failure already open upstream. One deck in the same release returns zero on the same file, but it is the unverified residual set: swapping decks trades a verified deck for an unverified one. Approach: work it upstream against a fixed calendar gate, with the load-bearing question stated rather than assumed - is a 0.02 um enclosure inside the vendor's own SRAM marker a qualified rule? A vendor drawing a marker is not a foundry qualifying the geometry under it. Fallback: flip-flop storage, which costs capacity, not correctness.

5. Observing a fault-tolerant part through a 24-pin shuttle interface. That is enough to run the part, not obviously enough to observe corrected-error counts, scrub progress, voter disagreements and neuron state during an irradiation run. This has bitten twice: memory ECC held on 84 of 84 injections and nothing on the chip said so, because the telemetry outputs were unconnected; and 79 upsets were absorbed by mechanisms no software or pin could see. Approach: design observability first, treat an unwired counter as a defect, and keep the counter block that records corrections, uncorrectables and voter disagreements in a domain a watchdog reset cannot erase.

6. Getting radiation data worth publishing. Bulk 130 nm CMOS carries no platform-level latch-up or total-dose guarantee, and the encouraging published numbers for this technology family come from its rad-hard sibling library, not the open standard cells. Approach: state that distinction in every published document, and design the campaign around one question - how does this design in this open standard-cell library behave under total ionising dose in the LEO 10-30 krad(Si) class - with dose steps, in-situ functional test, and full publication of fixture, procedure and raw data including null results. The value to the commons is the method and the dataset, not a rating.
```
<!-- field:challenges:end -->

### 3.10 Ecosystem and engagement (advisory 2500, hard 10000)

<!-- field:ecosystem:begin -->
```text
Upstream, where the main contribution lands. The design sits on IHP's open SG13G2 PDK, yosys and the LibreLane/OpenROAD flow, and is a demanding user of all three: hard macros, ECC wrappers, multi-corner timing, and redundancy that resists merging. Two shared defects came out of that use. Stopping triple-modular redundancy being optimised away is a problem for every open fault-tolerant design; and no design on this PDK can sign off with a vendor SRAM macro, a wall in front of every open project that needs on-chip memory. Both go upstream - to yosys, LibreLane and IHP-Open-PDK - as issues with reproducers, with the checker and the catalogue of constructions that survive, not as a folder in my repo. Two reports are drafted.

Sideways. The checker's first users are open silicon projects already on this toolchain, several NLnet-funded: GLOW-SG13G2 is building an open cell library for the same process, and a hardened design is a useful stress case; Borg II has taken a design of this shape to silicon; the Space grade Instrumentation Amplifier ASIC targets the same PDK for the same environment class, and I will propose a shared irradiation campaign and a common dose convention. Tiny Tapeout makes this silicon affordable, and every design I submit stays in its catalogue as a worked example of ECC, TMR and scrubbing.

Downstream. The users are university CubeSat programmes, small satellite integrators, and harsh-environment projects needing better-than-commercial fault behaviour without a qualification budget. What they get is not a datasheet claim but the evidence: campaign logs, rankings, counterfactual runs, RTL, executable specifications, proofs and ledger, flow scripts, bring-up software and radiation data - including the mechanisms that did not work. A block that can be audited is one a mission can defend to its reviewers.

Publication: everything lands publicly under free licenses as produced, not in a drop at the end, with the status page and two-monthly reports the MoU requires. The radiation dataset comes with analysis scripts and a fixture description, because no public total-dose data exists for digital logic in this PDK. Results go to a European open-silicon event.

Sustainability: the licenses let anyone fork, extend and manufacture it, and the suite and flow scripts make that practical, so its future does not depend on my attention. My own path is fault-tolerant silicon design and services around it, so my commercial interest and the commons align.
```
<!-- field:ecosystem:end -->

### 3.11 Attachments

**[D-9]** — up to three files, 50 MB total, HTML/PDF/ODF/plain text
**[fact]**. Two, because the form says attachments "should only contain
background information", the proposal must be "self-contained and
concise" without them, and "Don't waste too much time on this. Really."
**[fact]**

1. **Evidence pack** (PDF, 3-4 pages). The one attachment that earns its
   place, because stage 2 verifies claims and this makes verification
   cheap: the SymbiYosys task lists with their PASS output, the cocotb
   and pytest summaries, the seven campaigns' outcome tables **with
   their counterfactual columns**, the before/after netlist flip-flop
   counts for the merged TMR bank, the pilot's SG13G2 sign-off metrics,
   and — deliberately — the three negative results of section 2.1 with
   their numbers.
2. **Budget and milestone plan** (PDF, 2 pages): sections 4 and 5 in the
   MoU annex format, so it can be lifted into Annex I if selected.

Neither exists as a PDF yet. Producing both is ~3-5 h **[estimate]** and
must be scheduled before 2026-10-27 (section 8).

### 3.12 Generative-AI disclosure — required field

**[D-10]** — required select with two options. If the second is
selected, the policy requires a prompt provenance log listing the model,
the dates and times of prompts, the prompts themselves and the unedited
output, and the FAQ additionally requires that the applicant "explain
why this was necessary" **[fact]**. The answer and any log are the
developer's to provide; this document records the requirement only, and
the requirement is that the answer be accurate — non-compliance is
grounds for rejection or for termination of a running grant.

**[D-18]** — not a form field. The same policy governs project
development for the life of the grant: substantive use that materially
affects outputs requires public disclosure, a broad statement in the
repository readme of how such tools are used, and per-contribution
provenance for generated content **[fact]**. Settle the readme statement
and the contribution convention before the MoU. It interacts with the
licensing decision, since the policy requires that everything delivered
"can be legally published under a FLOS licence".

### 3.13 Consent and PGP

- Privacy consent checkbox: required, must be ticked. **[fact]**
- "Send me a copy": pre-checked; leave it checked — the emailed copy is
  the only record of exactly what was submitted.
- OpenPGP key: optional. **[D-11]** — if supplied, valid for at least
  three months after the deadline.

---

## 4. Budget breakdown

Rate: EUR 40/hour **[D-8]**, uniform across tasks. Totals in EUR.

### 4.1 Developer time — 460 h, EUR 18,400

| ID | Task | Hours | EUR | Grounding |
|---|---|---:|---:|---|
| T1 | Multi-bit and gate-level fault injection at SoC scale | 120 | 4,800 | The gap is documented, not hypothetical. Every SoC-scale campaign in the record is RTL and single-bit; gate level exists only for the pilot, where `docs/32` measures **370 of 370** comparable injections classifying identically. The SoC placed with the accelerator is **42,518 cells and 5,263 flip-flops** **[fact, docs/61]**, and `docs/59` already parses 169,747 cell positions out of the DEF with eighteen self- and cross-checks, so the adjacency model has a foundation. Hours **[estimate]** |
| T2 | Redundancy-survival checker released as a standalone tool, plus upstream issues | 60 | 2,400 | The check exists for this design as tests; generalising it to arbitrary designs and flows, documenting the construction catalogue — including `docs/33`'s measured limit, that the transform is provably unreachable at the netlist for a one-bit rail — and upstreaming is the new work. Unchanged from the 29 August draft, which is itself evidence that it was correctly scoped **[estimate]** |
| T3 | Closing the SoC's timing constraint, or replacing the target with a workload-derived requirement | 90 | 3,600 | **Four candidate remedies have been measured and closed**: the floorplan (`docs/48`, both alternatives worse), `SYNPRE` (`docs/49` and `docs/62`, worse both times), the RAM read register (`docs/50`, closes the path and makes the part 21.04 % slower in wall time), and the library capacitance constraint (`docs/48`). What is left is RTL, and `docs/53` argues the parallel obligation is to derive a requirement rather than move a number. Genuinely ahead of the project **[estimate]** |
| T4 | The PDK's SRAM sign-off blocker, worked upstream | 70 | 2,800 | `docs/12` section 8 and `docs/54`. The blocker has been characterised twice, reproduced three ways including from the bare vendor macro alone, and narrowed to one question this project refuses to answer for itself. Two upstream reports are drafted and not filed. `docs/06` B.6.1's 25-50 h for macro integration is the nearest prior figure; upstream coordination is the addition **[estimate]** |
| T5 | Silicon bring-up: host software, silicon-vs-model lockstep, demonstrator, results memo | 70 | 2,800 | `ROADMAP.md` P4. Cheaper than it looks: `docs/51` argued and then built the connection so that **there is one implementation of the die's host protocol and it is the one in the SoC's own regression** **[estimate]** |
| T6 | Documentation, dataset publication, two-monthly public reporting | 50 | 2,000 | MoU reporting obligation **[fact for the obligation, estimate for the hours]** |
| | **Subtotal** | **460** | **18,400** | |

### 4.2 Out-of-pocket — EUR 11,285

| ID | Item | Basis | EUR |
|---|---|---|---:|
| H1 | Shuttle tiles, devkit and shipping, follow-up run | 32 x EUR 70 = 2,240, **plus an unsubsidised devkit PCB at EUR 300 and EUR 15 shipping** — the correction `docs/37` forced, since every tile-only figure in this repository omitted both **[fact for the unit prices, docs/37; estimate for the tile count]** | 2,555 |
| H2 | Spare carrier board | 1 x EUR 150 **[estimate]**; the devkit itself is now in H1 | 150 |
| H3 | Custom breakout and test PCB | 2 revisions, fab + assembly + components **[estimate]** | 800 |
| H4 | Bring-up instrumentation | FPGA host board 400, programmable supply with current logging 900, logic analyser 250, cabling 150 **[estimate]** | 1,700 |
| H5 | TID pre-screen campaign | Co-60 facility time 3,500 **[estimate, quote pending — D-15]**, fixture mods and spares 400, shipping/customs/dosimetry 900 | 4,800 |
| H6 | Import duties into Türkiye | ~15 % of H1-H4 **[estimate]** | 780 |
| H7 | One European open-silicon event | Explicitly eligible per the Restack activity list **[fact]** | 500 |
| | **Subtotal** | | **11,285** |

### 4.3 Total

**EUR 18,400 + EUR 11,285 = EUR 29,685.**

Arithmetic check: 4,800 + 2,400 + 3,600 + 2,800 + 2,800 + 2,000 =
18,400. Hours 120 + 60 + 90 + 70 + 70 + 50 = 460, and 460 x 40 = 18,400.
2,555 + 150 + 800 + 1,700 + 4,800 + 780 + 500 = 11,285. Sum 29,685.

No F&A or overhead line appears, which sidesteps the FAQ's "F&A costs
are generally not considered eligible expenses" **[fact]**.

---

## 5. Milestone plan

MoU format: numbered tasks, each with an amount unlocked by publishing
the associated results **[fact]**. Every milestone is publishable
standalone. Every milestone is work that will still be ahead of the
project when an MoU is signed (section 1.4a) — which, given what the
last week did to the previous task set, is a claim to re-test at
submission and again at MoU. See [D-23].

| M | Milestone (published artefact) | Unlocks | Target |
|---|---|---:|---|
| M1 | Redundancy-survival checker released as a standalone tool, with the construction catalogue and measured costs; upstream issues filed | T2 = 2,400 | MoU + 2 months |
| M2 | The PDK's SRAM sign-off blocker reported upstream with reproducers, and either closed or documented with a stated foundry question and a measured fallback | T4 = 2,800 | MoU + 4 months |
| M3 | Multi-bit and gate-level fault-injection campaign public at SoC scale: harness, adjacency model, target-mapping method, results and an explicit coverage statement | T1 = 4,800 | MoU + 7 months |
| M4 | Timing constraint closed, or the target replaced by a requirement derived from a sized workload, with the measurement either way; design submitted to the next available IHP-process shuttle | T3 + H1 = 6,155 | MoU + 9 months |
| M5 | Silicon bring-up report: silicon-vs-model lockstep, fault-tolerance demonstrator behaviour, flow lessons; bring-up software public | T5 + H2 + H3 + H4 = 5,450 | after boards arrive |
| M6 | Total-ionising-dose pre-screen dataset and report public: fixture, procedure, raw data, null results | H5 = 4,800 | M5 + 3 months |
| M7 | Integration guide, analysis scripts, final documentation; results presented at a European open-silicon event | T6 + H6 + H7 = 3,280 | M6 + 2 months |

Sum: 2,400 + 2,800 + 4,800 + 6,155 + 5,450 + 4,800 + 3,280 = **29,685.**

**Ordering rationale.** M1 is the cheapest, most certain and most broadly
useful milestone, and it carries the fund-level contribution, so it goes
first — and it is finished and published before any hardware money is
spent. M2 is second because it is the other fund-level contribution and
because it is pure effort with an upstream counterparty, so its risk is
scheduling rather than engineering. EUR 10,000 across M1-M3 is unlocked
before H1's EUR 2,555 inside M4, and EUR 21,605 across M1-M5 before
H5's EUR 4,800 at M6.

**On the 12-month default.** M1-M4 fit inside 12 months of MoU signature
**[estimate]**. M5-M7 depend on shuttle silicon, whose arrival the
project does not control. `docs/37` records that **no IHP run after
TTIHP26b is announced** **[fact]**, which makes M4's "next available
IHP-process shuttle" the right wording and makes naming one a mistake.
The FAQ permits "qualified exceptions" to the 12-month default and the
MoU allows donations to be claimed "within a maximum of six months after
the proposed end of the project" **[fact]**; set the proposed end date
with that margin. **[D-16]** — keep the shuttle generic.
Recommendation: keep it generic.

---

## 6. Risk register

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-1 | Application not funded | Medium-high (competitive **[estimate]**) | Project continues self-funded at ROADMAP pace | Scope is deliverable without the grant, just slower; re-submission possible on the third of any odd month |
| R-2 | Restack budget exhausted before a later round ("expected early 2027" **[fact]**) | Medium | No second chance in this programme | Submit into the 2026-11-03 round |
| R-3 | Radiation-campaign line challenged as ineligible | Medium | EUR 4,800 removed | Ask at an office hour before submitting ([D-12]); if it will not fly, drop M6 and reduce the ask. The method-led framing survives losing this milestone |
| R-4 | Cash flow: everything spent before reimbursement | High (structural **[fact]**) | ~EUR 11,285 personal exposure | Milestone ordering (section 5); M1 and M2 are pure effort and pay first |
| R-5 | Shuttle slip pushes M4-M7 beyond the MoU window | Medium, and **higher than in August**: no IHP run after 26b is announced **[fact, docs/37]** | Milestones unpaid or renegotiated | Six-month post-end claim window **[fact]**; propose end dates with margin; do not name a shuttle ([D-16]) |
| R-6 | The SRAM sign-off blocker does not close upstream | **Medium-high, and now measured rather than feared** | T4 and M2 slip | Both blocking causes are upstream and identified; `docs/54` has narrowed one to a single answerable question and drafted the reports. M2 is written so that a **documented negative with a stated foundry question and a measured fallback** is a completed milestone, which is how this project already treats a negative result |
| R-7 | Tax treatment of the donation in Türkiye | Certain to need handling | Effective grant value reduced | The grantee "is responsible for paying any and all taxes" **[fact]**; obtain local advice before signing |
| R-8 | Publication obligation collides with the private-repo posture | **Certain, and now blocking a nearer deadline than this one** | Blocks the TTIHP26b push on 2026-09-21, then MoU signature | `docs/14`, rewritten 2026-09-05 to be decidable in one sitting. Its section 0 records that it blocks the shuttle before it blocks the grant. **Must be closed for the shuttle, which settles it for the application** |
| R-9 | A claim fails stage-2 verification | Low if disciplined | Score damage or rejection | Every figure here is tagged and traceable; counts re-run 2026-09-05 (section 9.2); section 10 lists the documents whose numbers must not be quoted |
| R-10 | Positioning language drifts above the export-safe threshold | Low | Serious and irreversible once submitted | `docs/05` section 4 applied sentence by sentence; re-check at final review ([D-17]). Specifically: do not import `docs/04`'s "no SEL to 65 MeV·cm²/mg" sentence or `docs/06`'s uncited ~200 krad figure, **do not publish any clock frequency** (`docs/53` section 9.2, `docs/60`), and **do not write a sentence that implies the SoC is manufacturable today** (`docs/12` section 8, `docs/54`) |
| R-11 | The proposal is read as productisation rather than R&D and fails the stage-1 knock-out | Low under the section 2.1 framing **[estimate]** | Not reviewed at all | "Research and development as the primary objective" is a hard criterion **[fact]**; T1-T4 are all open questions with stated methods and no assured answer |
| R-12 | A funded task turns out to be work already completed by MoU time | **High, and demonstrated: four of six tasks were struck or rescoped in one week** | Task struck or renegotiated | The FAQ permits replacing such parts with other tasks rather than cutting the budget **[fact]**. Every task in section 4.1 was chosen against this, and [D-23] makes re-testing it a scheduled action rather than a hope |
| R-13 | The task hours have no measured base | **Certain [fact]** | Stage 2 questions the rate or the scope; the plan proves optimistic or pessimistic and nothing predicts which | This project has never recorded developer hours (section 2.2). The mitigation is to say so if asked, not to invent a base. Starting a time record now would give the MoU-stage conversation something real to stand on, and is the one cheap action available before submission |

---

## 7. Open decisions

**The one that blocks everything else** is at the top. The rest are
ordered by date.

| ID | Decision | Owner | Needed by | State |
|---|---|---|---|---|
| **D-0** | **Sign or reject `docs/14-licensing-decision.md`.** Rewritten 2026-09-05 so it can be signed in one sitting: eleven rows, defaults marked. Its recommendation is CERN-OHL-W-2.0 for hardware sources, Apache-2.0 for software, CC-BY-4.0 for documents and data. **The binding deadline is no longer this application's — it is the TTIHP26b shuttle close, 2026-09-21 20:00 UTC**, because a Tiny Tapeout submission is a public repository and the tree refuses to ship without a licence. NLnet makes the licence a term of the MoU and publication the payment trigger for every milestone. Note `docs/06` names CERN-OHL-**S**; `docs/14` recommends **-W** and gives the reason | developer | **2026-09-21, effectively now** | **unsigned, overdue** |
| D-1 | Applicant name: legal name or alias | developer | 2026-10-27 | open |
| D-2 | Contact email address | developer | 2026-10-27 | open |
| D-3 | Phone number | developer | 2026-10-27 | open |
| D-4 | Apply as individual or via an entity | developer | 2026-10-27 | open |
| D-5 | Project name (recommendation: option A) | developer | 2026-09-30 | open |
| D-6 | Website field value — depends on D-0 | developer | 2026-10-15 | blocked on D-0 |
| D-7 | Experience field: public URLs, and how explicitly to name adjacent programmes | developer | 2026-10-15 | open |
| D-8 | Confirm or replace the EUR 40/hour rate | developer | 2026-09-30 | open |
| D-9 | Produce the two attachments | engineering | 2026-10-27 | open |
| D-10 | Generative-AI disclosure answer and, if applicable, the provenance log **and the explanation of why it was necessary** | developer | at submission | open |
| D-11 | Supply an OpenPGP key or not | developer | at submission | open |
| D-12 | Ask an office hour whether irradiation-facility time and instrumentation are eligible out-of-pocket costs (last Wednesday of each month, 16:00 CET, NLnet's Matrix room) | developer | 2026-09-30 | open |
| D-13 | Re-verify the form fields, `maxlength` values **and placeholders** now that the call has opened | developer | **overdue — the call opened 2026-09-03** | open |
| D-14 | Resolve `docs/02` open question 2 (Solderpad RTL reuse vs independent implementation) — determines whether "clean-room" may be used at all. `docs/14` section 5.1 records that its 2026-09-02 date has passed | developer | **overdue** | open |
| D-15 | Obtain a real Co-60 facility quote to replace the H5 estimate | developer | 2026-10-15 | open |
| D-16 | Keep the shuttle generic in the milestone plan (recommendation: generic, and `docs/37`'s "no IHP run after 26b is announced" strengthens it) | developer | 2026-10-27 | open |
| D-17 | Final positioning-language pass against `docs/05` section 4 **plus the two prohibitions** before submitting | developer | 2026-10-27 | open |
| D-18 | Repository-level generative-AI disclosure convention for the life of the grant | developer | 2026-10-27 | open |
| **D-19** | **Confirm the requested amount, now EUR 29,685** (was EUR 29,500, and EUR 27,500 before that), and that the rebuilt task set of section 4.1 is the scope the developer intends to be bound to. The change is one line: H1 gains the devkit and shipping every tile-only figure in this repository omitted, per `docs/37` | developer | 2026-09-30 | **changed** |
| D-20 | Accept or reject the method-led framing of section 2.1. **Recommendation: accept, and note it is now the only framing section 1.4(a) leaves standing** | developer | 2026-09-30 | open |
| **D-21** | **Confirm the verification counts immediately before pasting.** They were measured 2026-09-05 at HEAD `ed51de0` (section 9.2) and this project has changed them four times in ten days. Re-run `pytest sw/tests`, `scripts/run_cocotb.sh` and the two formal makefiles, and paste what they return | engineering | 2026-10-27 | **open** |
| **D-22** | **Re-check the experience field's physical sentences against whichever runs are current at submission.** The pilot sentence cites the frozen `6x2` sign-off; the SoC sentence is deliberately negative and must stay negative while `docs/12` section 8 stands | engineering | 2026-10-27 | open |
| **D-23** | **Re-test section 1.4(a) at submission and again at MoU.** Four of six tasks were struck or rescoped in one week. Before pasting, walk section 4.1 against HEAD and move anything that has since been built. This is a scheduled action, not a hope, and R-12 is why | engineering | 2026-10-27 | **new** |

---

## 8. Submission checklist and dates

| Date | Action | Owner |
|---|---|---|
| **now** | **D-0: sign or reject `docs/14`.** The shuttle needs it in sixteen days; everything downstream waits on it | developer |
| **now** | D-13: the call opened 2026-09-03; re-fetch the form and re-verify fields, limits and placeholders | developer |
| 2026-09-21 20:00 UTC | TTIHP26b closes. Slot bought, tree licensed, pushed, GDS action and hosted precheck run | developer |
| 2026-09-30 | D-5, D-8, D-12, D-14, D-19, D-20 closed | developer |
| 2026-10-15 | D-6, D-7, D-15 closed | developer |
| 2026-10-20 | Attachments drafted (D-9) | engineering |
| 2026-10-27 | Full package review: positioning pass **and the two prohibitions** (D-17), arithmetic re-check, character counts re-run, verification counts re-run (D-21), physical sentences re-checked (D-22), **scope re-tested against HEAD (D-23)**, D-1..D-4, D-16, D-18 closed | developer |
| **2026-10-29** | **Submit.** Five days before the deadline, not on it | developer |
| 2026-11-03 12:00 CEST | Hard deadline **[fact]** | — |
| 2027-03 to 2027-06 | Expected decision window **[estimate, section 1.3 item 4]** | — |

Rationale for 2026-10-29: the form accepts multiple versions before the
deadline and the last complete one is used **[fact]**, so early
submission costs nothing and removes deadline-day risk.

---

## 9. Character counts and the commands that produced every number

### 9.1 Field lengths

Counts of the exact text inside each `field:<name>` marker block, code
fences excluded, trailing newline excluded. **Re-run these after any
edit** — every field in this revision was rewritten.

Reproduce from the repository root:

```sh
count() { awk -v b="<!-- field:$1:begin -->" -v e="<!-- field:$1:end -->" \
  'index($0,b){s=1;next} index($0,e){s=0} s' docs/13-nlnet-application.md \
  | sed '/^```/d' | python3 -c \
  'import sys;print(len(sys.stdin.read().rstrip(chr(10))))'; }
for f in abstract experience use comparison challenges ecosystem; do
  printf '%-12s %s\n' "$f" "$(count $f)"; done
```

Measured on 2026-09-05 with that command. **[fact]**

| Field | Characters | Advisory | Hard | Under advisory by | Hard headroom |
|---|---:|---:|---:|---:|---:|
| abstract | **1197** | 1200 | 1500 | 3 | 303 |
| experience | **2436** | 2500 | 10000 | 64 | 7564 |
| use | **2484** | 2500 | 10000 | 16 | 7516 |
| comparison | **3995** | 4000 | 10000 | 5 | 6005 |
| challenges | **4999** | 5000 | 12500 | 1 | 7501 |
| ecosystem | **2498** | 2500 | 10000 | 2 | 7502 |

Every field is inside its *advisory* limit, with the hard limit left as
headroom rather than spent. **[D-21a]** — re-run the command above at
final review and refill this table from its output; never fill it by
hand. Four fields sit within five characters of their advisory limit, so
any edit at all needs a re-count.

### 9.2 Provenance of every technical number in section 3

Run on 2026-09-05 at git HEAD `ed51de0`. **[fact]**

| Claim in the application | Source | Result |
|---|---|---|
| "437 Python tests" | `.venv/bin/python -m pytest sw/tests -q` at the repository root | **437 passed in 533.01 s**, exit 0 |
| "373 cocotb tests" | `scripts/run_cocotb.sh`, as recorded in `docs/00-index.md` section 6 on 2026-09-05 | **373 across every suite, 0 failures** |
| "110 SymbiYosys proof tasks over 22 property sets" | counted 2026-09-05 from the files themselves, **not from `docs/00-index.md`, which is now behind on both trees**. Pilot: `make -C formal -n everything \| grep -c "sby -f"` returns **54**, over **8** `.sby` files (the index still says 45 over 7; `tmr_voter_cfg.sby` is the eighth). SoC: the `[tasks]` sections of `hw/soc/formal/*.sby` total **56** over **14** files (the index says 52; `soc_boot.sby`'s four are the difference) | 54 + 56 = **110**; 8 + 14 = **22**. **This is a count, not a claim that all are green** — the same discipline the 29 August draft applied for the same reason, and [D-21] is where the pass state gets confirmed |
| "riscv-formal … 70 of 79 bounded checks and 79 of 79 cover obligations" | `docs/63` sections 5 and 6 | 70 / 79 bmc PASS, 79 / 79 cover PASS, at check cycle 20 for 66 instructions |
| "five defects and not one is in Ibex's execution" | `docs/63` section 7 | Three in this project's harness, one in Ibex's RVFI trace port (`rvfi_intr`, `rvfi_pc_wdata` on `mret`), one in riscv-formal's `insn_div.v` / `insn_rem.v`, confirmed on four counterexamples across two runs |
| "seven injection campaigns, each mechanism replayed against the same upsets with it removed" | `docs/60` section 8 collects them; the pattern is established in `docs/42` and applied in `docs/43`, `docs/46`, `docs/52`, `docs/55`, `docs/56`, `docs/58` | Seven RTL campaigns over five named populations, every denominator stated |
| "2.8 % ± 1.6 to 1.3 % ± 0.4" | `docs/42` section 6 and `docs/43` section 8; re-run byte-identically in `docs/44` | Design-weighted SDC over the Ibex core, same stratified draws |
| "128 of 128 … 95 times and announced none" | `docs/58` sections 9 and 10 | 342 injections; 128/128 into `mtime` and 16/16 into the check bits CORRECTED, against 95 undetected clock displacements on the unprotected design, worst case 2^63 ticks |
| "370 of 370 comparable injections" | `docs/32` | Gate level against RTL on the pilot netlist |
| "the largest structure … 41 % of its flip-flops and contributed zero"; "nine flip-flops out of 140 carried 96 %" | `docs/52` section 5 (`evq_data`, 98 of 100 MASKED) and `docs/56` section 3 | Both are the same finding at two scales: rank by consequence, not by size |
| "362 netlist references to one replica, none to the other two" | `sw/tests/test_synthesis_guards.py` header, citing `tt/runs/tt-harden/06-yosys-synthesis/` | 362 references to `cfg_a[`, zero to `cfg_b[` or `cfg_c[` |
| "84 of 84" ECC holds with nothing on the chip saying so; "79 upsets absorbed … no software or pin could see one" | `docs/16` section 4.1; `docs/52` section 11 | 74 pointer-vote corrections all golden and all invisible, plus five rail disagreements |
| "0 of 30 dead machines … 7 spurious escalations" | `docs/43` section 8.4 | The windowed watchdog, on the campaign that recommended it |
| "0.25 % [0.07-0.89] against 0.27 % [0.08-1.00]" | `docs/46` sections 7 and 9 | Second workload, 812 stratified injections, each run twice |
| "42,518 cells and 5,263 flip-flops" | `docs/61` section 3 | `soc_top` with the accelerator, placed on `docs/47`'s floorplan |
| "169,747 cell positions … eighteen self- and cross-checks" | `docs/59` sections 3 and 4 | Parsed from the `full3` run's own `final/def/soc_top.def` |
| "21.04 % slower in wall time" | `docs/50` section 7 | Cycles times period, both measured |
| pilot sign-off: "every geometric counter at zero", "three corners with a 5 % derate the flow itself omits" | `docs/31` and `docs/34`; the derate defect is `docs/28` section 4.4(b) | Magic DRC, KLayout DRC, XOR, all four Netgen LVS counters, antenna, power grid and illegal overlap all zero; precheck 10 of 10 |
| SoC layout: "zero detailed-route DRC errors", "misses its timing constraint", "cannot be signed off on this PDK version" | `docs/47` sections 3 and 5; `docs/61`; `docs/12` section 8; `docs/54` | 0 detailed-routing DRC, 0 disconnected pins, 0 power-grid violations; setup missed at the slow corner; **no Magic DRC, no LVS, no XOR has ever been run on the SoC** |
| "nineteen confirmed findings" | `docs/07` section 1 | "Nineteen findings survived verification: 5 high, 8 medium, 6 low." |
| "one of them in my own funding material" | `docs/07` F-4 | F-4 is in `docs/06`, the funding document |

**Two figures deliberately absent from every field, and why.**

- **No clock frequency.** `docs/53` section 9.2 refuses to publish the
  one the layout reached, on three grounds of which the first is that it
  is the number a failing layout reached and the second is `docs/05`
  section 4 rule 5. `docs/60`, the SoC datasheet, publishes none either.
  This application publishes none.
- **No claim of manufacturability for the SoC.** The pilot's sign-off
  and the SoC's absence of one are in separate sentences of the
  experience field, and the SoC's limitation is stated rather than
  omitted.

---

## 10. Errors and stale numbers found elsewhere

Reported, not fixed — this document owns only itself. Ordered by how
badly each would damage the application if quoted.

1. **`docs/16-fault-injection-campaign.md`'s campaign-of-record
   arithmetic was reconciled by `docs/64` and the earlier figures are
   still quotable from older documents.** `docs/64` traces the 335 / 366
   / 378 disagreement to two stale-but-real earlier logs and names the
   frozen file at blob `312d3c76` — **378 injections, 6 SDC** — as the
   campaign of record **[fact, confirmed by reading
   `hw/tb/fi_campaign_results.json` at HEAD: total 378, histogram MASKED
   97 / CORRECTED 193 / DETECTED 82 / SDC 6 / HANG 0]**. **The
   application quotes none of these rates** (section 3.4), which is why
   the reconciliation does not reach the fields.
2. **`docs/21-pilot-datasheet.md` revision 0.1 predates several waves**
   and labels a pre-hardening distribution as the "current design". It
   remains the most quotable stale number in the repository. `docs/64`
   corrected the campaign count where it is quoted; the surrounding
   prose has not been re-baselined.
3. **`docs/06-funding-and-shuttle.md` still carries four things that
   must not be lifted into the application**: "no space/SpaceWire/
   satellite-silicon precedent was found" (wrong, section 1.6);
   "Abstract, maximum 1,200 characters" presented as the hard limit (it
   is the advisory limit); an A.8 abstract draft containing the word
   "clean-room", which [D-14] has not authorised; and cost figures that
   omit the devkit and shipping, which is the error section 4.2 H1
   corrects.
4. **`docs/04-technology-and-flow.md` section 6 recommends a
   datasheet-level claim sentence containing "no SEL to
   65 MeV·cm²/mg".** No SG13G2-specific single-event-latch-up
   measurement exists anywhere in the repository, so that sentence sits
   against `docs/05` section 4 rule 3. It must not reach public text.
   The same applies to `docs/06`'s ~200 krad figure.
5. **`docs/00-index.md` section 2.2's "does not exist" list has been
   corrected three times in place** and is now accurate — GPIO, QSPI and
   the placed SoC with macros all carry dated corrections. It is worth
   reading before any field is pasted, because it is the fastest
   inventory of what may and may not be claimed. **Its section 6 is a
   different matter and is now stale on both formal trees** (section 9.2
   row 3): it records 45 tasks over 7 property sets for the pilot and 52
   over 14 for the SoC, which were correct on their dates and are now 54
   over 8 and 56 over 14. Both were counted from the files on
   2026-09-05. Nothing about the verification argument changes; only the
   arithmetic does, which is what that section says about itself.
6. **The 70.66 % figure is unresolvable from this repository and
   collides with itself.** A 25 August draft claimed "70.66 %
   classification accuracy" for `tt-um-lif-crossbar`; no artifact here
   supports it, and `docs/15` and `docs/17` both use **70.66 %** for the
   *placement utilisation* of the same chip. Two unrelated quantities
   carrying one number is a coincidence worth checking before either is
   published. The figure stays removed pending [D-7].
7. **`hw/fpga/README.md` tables are pre-TMR-fix.** Not quoted here.
8. **`ROADMAP.md` was rewritten 2026-09-05** and no longer carries the
   retracted tile arithmetic, the superseded "default 2x2 pilot", or the
   description of the formal programme as future work — all three of
   which the 29 August revision of this document reported. Its P3 hour
   roll-up is now **retired rather than restated**, and section 2.2
   above explains what that means for the task hours in section 4.1.
