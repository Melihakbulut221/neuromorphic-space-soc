# 14 — Licensing and publication: decision memo

Date: 25 August 2026.
Status: **decision memo, not a decision.** Section 9 carries a
recommendation and a dated action plan; nothing in this document is
binding until the developer signs section 11.
Decision owner: developer. Prepared by: engineering.
Blocks: ROADMAP gate G2 ("repo license state consistent with what the
application promises") and, through it,
`docs/13-nlnet-application.md` fields D-6 and D-7.
Deadline: **2026-10-15**, so that the application package (docs/13
section 8) can be finalised with the answer already in hand.

Labels: **[fact]** = verified against a cited primary source on the
stated date; **[estimate]** = judgement; **[legal]** = a question this
memo deliberately does not answer because it needs qualified advice.

---

## 1. The question

This repository is private. `docs/06-funding-and-shuttle.md` A.6 records
the tension in one line: an NLnet grant is a commitment to publish every
funded artefact under a free licence, and the sibling programme's
"public at tapeout" posture does not fit that. docs/06 action item 5 and
ROADMAP P2 both name the decision and neither makes it.

Four things actually have to be decided, and they are separable:

1. **When** does anything become public — at application, at MoU
   signature, or at each delivery?
2. **What** becomes public — everything, or a defined funded scope?
3. **Under which licences** — separately for RTL, for documents, and for
   software, and consistent with what the dependencies allow.
4. **What does publication do to the export-safe posture** of
   `docs/05-market-positioning.md` section 4?

Sections 3 to 7 answer each; section 8 lays out the options as a whole;
section 9 recommends.

---

## 2. Where the repository stands today

- No `LICENSE` file at HEAD; repository private. The independent review
  (docs/07, rejected finding R-7) explicitly held that this is not a
  defect *while the decision is open and owned* — which is exactly the
  status this memo is here to end.
- Artefacts that would fall inside a plausible funded scope already
  exist: the register-map single source and its generator, the NPU
  golden model, `hw/rtl/aer_fifo.v` with its cocotb regression, the
  SymbiYosys proof and its PASS status, and documents 00-13.
- No third-party RTL has been vendored into the repository yet. That is
  a large advantage: the licence decision is still being made *before*
  any inbound obligation attaches, which is the only comfortable time to
  make it.

---

## 3. What NLnet actually requires, and when

Verified 2026-08-25 against nlnet.nl primary sources. **[fact]** for
every quotation below.

### 3.1 At application time: nothing must be public

- The application form has no required repository field. "Website" is an
  optional 100-character text field
  (`https://nlnet.nl/propose/`, form markup inspected 2026-08-25).
- Anonymity is explicitly permitted before selection: "You don't need to
  reveal your real name to us, prior to the project being granted."
  (`https://nlnet.nl/restack/faq/`)
- So: **publication is not a precondition of submitting.** docs/06 A.6's
  statement that the repo "must be public no later than the MoU stage"
  is correct; its stronger implication that submission itself requires it
  is not.

The countervailing pressure is evaluation, not eligibility. Stage 1
scores the proposal text; stage 2 involves "independent verification of
facts, methods and claims" and questions of the form "can you back up or
validate claim Y" (`https://nlnet.nl/restack/guideforapplicants/`).
A private repository means every claim in the experience field has to be
taken on trust or evidenced by attachment. **[estimate]** That is a
scoring handicap on a 30%-weighted technical-excellence criterion, not a
disqualification.

### 3.2 At MoU signature: the licence is named in the contract

The sample MoU (`https://nlnet.nl/foundation/request/sample_MoU.pdf`,
retrieved and text-extracted 2026-08-25) contains, as a term of the
agreement: "The source code of the Project shall be made publicly
available under GPLv3, or any later version." The licence is a *named
term of the MoU*, filled in per project.

Consequence: the licence choice cannot be deferred past MoU negotiation,
and it is much better to arrive at that negotiation with a considered
answer than to accept whatever the template suggests. A project that has
already published under its chosen licences negotiates from a fact.

The MoU carries two further obligations that are easy to miss and that
have a real cost:

- public progress reports "every two months, more often is never a bad
  thing", and
- "a public status page for the project to keep the wider internet
  community informed".

Both start at MoU signature, not at first delivery. They are budgeted in
docs/13 section 4 line T5.

### 3.3 At delivery: publication is the payment trigger

- "There is a donation amount attached to each task, which you unlock by
  **publishing** the associated results." (sample MoU, Annex I guidance)
- "All scientific outcomes must be published as open access, and any
  software and hardware must be published under a recognised open source
  license **in its entirety**."
  (`https://nlnet.nl/restack/guideforapplicants/`)
- No payment is made up front: "the grant is not paid out up front.
  Instead you divide your project into milestones and allocate an amount
  to each of these." (`https://nlnet.nl/restack/faq/`)

So the honest one-line answer to the question in the task: **not at
application, licence fixed at MoU, publication required at each
milestone.** In practice the first milestone lands a few months after
MoU signature, so the effective deadline for having a public repository
is MoU signature plus a couple of months — spring/summer 2027 on the
docs/13 timeline.

### 3.4 Two requirements that only bite later

- Follow-up funding above 50 kEUR requires that the earlier project's
  "deliverables have been made publicly available under recognised
  open/free licenses", that "any software artefacts delivered were WCAG
  compliant", and that security-audit findings were handled. **[fact]**
  The WCAG clause is written for web software; if any funded deliverable
  grows a graphical or web interface (a bring-up dashboard, a dataset
  browser), it inherits an accessibility obligation. Keep funded software
  command-line and file-based and the clause is inert. **[estimate]**
- Patents must be disclosed at application: "Yes, you must certainly
  disclose this." **[fact]** Nothing to disclose here at present; if that
  changes, it changes the application, not just the licence.

### 3.5 What NLnet explicitly does *not* require

This is the part that resolves most of the perceived tension:

> "This condition however does not in any way exclude the legitimate
> holders of copyrights and other associated rights of dealing with your
> project results under additional licenses, even proprietary ones."
> (`https://nlnet.nl/restack/faq/`) **[fact]**

The developer retains copyright and may additionally licence the same
work commercially. NLnet's requirement is that an open licence exists,
not that it is the only licence. Combined with "You can in fact make
money from what you build in any way, as long as the result of the work
funded by us is at least available under a free and open source license"
**[fact]**, the commercial path of `docs/05` section 3.2(c) survives
intact. Dual licensing is only possible if the developer holds or
controls all the copyright in the dual-licensed work — which is a reason
to keep third-party inbound code in clearly separated directories
(section 5).

---

## 4. What has to be open: scoping "in its entirety"

"In its entirety" attaches to the *project* defined in the MoU annex, not
to every file the developer owns. The practical rule:

- Everything named in the MoU milestones is public under the named
  licence, complete and buildable — no withheld headers, no "contact me
  for the constraints file".
- Work outside the funded scope may stay private, but only if the public
  scope stands on its own. A public RTL block that cannot be simulated,
  hardened or verified without a private script would breach the spirit
  and probably the letter of "in its entirety". **[estimate]**
- The partition must be mechanical, not editorial: a directory boundary
  and a CI job that builds the public tree from a clean checkout with no
  access to the private one. If that job is green, the scope claim is
  true; if it is not, the claim is aspiration.

Applied to this repository, the natural boundary is: the inference core,
the fault-tolerance IP, the golden model, the register-map flow, the
verification harness, the SG13G2 flow scripts, the bring-up software, the
radiation dataset, and the technical documents that describe them — all
public. Commercial positioning material, customer-facing pricing, and
product-line strategy are not funded artefacts and are not published;
note that `docs/05` section 3.2(c) already marks that motivation as
internal.

---

## 5. What the dependencies force

Verified 2026-08-25 by reading the licence files and source headers
directly. **[fact]** for each licence identification.

| Dependency | Licence | What it forces |
|---|---|---|
| Ibex (management core candidate) | Apache-2.0. `LICENSE` is the Apache 2.0 text; README: "Unless otherwise noted, everything in this repository is covered by the Apache License, Version 2.0". | Nothing restrictive. Apache-2.0 is inbound-compatible with a permissive or a reciprocal outbound licence. Keep it in its own directory with its notices intact; do not relicence it. |
| IHP Open PDK (SG13G2, incl. `RM_IHPSG13_*` macros) | Apache-2.0 (`LICENSE` in IHP-GmbH/IHP-Open-PDK). IHP describes the open content as "preview only" and not for production. | Do not vendor or redistribute PDK files; depend on a pinned upstream release. Check per-file headers before any redistribution of macro views — an Apache-2.0 repository can still contain differently-licensed third-party files. |
| tinyODIN / ODIN / ReckOn (open SNN references) | Solderpad v2.1 (per docs/03 and docs/02). | Reuse is permitted with attribution. But reuse decides whether the word "clean-room" may ever be used about this core — docs/02 open question 2, still open. See section 5.1. |
| Mohor CAN core | LGPL-2.1-or-later, from the source header: "under the terms of the GNU Lesser General Public License ... either version 2.1 of the License, or (at your option) any later version." | See section 5.2. Recommendation: keep it out of the funded scope. |
| Bosch CAN protocol | Patent, not copyright. Source header, verbatim: "The CAN protocol is developed by Robert Bosch GmbH and protected by patents. Anybody who wants to implement this CAN IP core on silicon has to obtain a CAN protocol license from Bosch." | A licence obligation that no open licence removes, and one NLnet would want disclosed. Another reason CAN stays outside the funded scope. |
| Tiny Tapeout templates | Apache-2.0 (`LICENSE` in TinyTapeout/ttihp-verilog-template). TT's FAQ: templates are Apache-2.0 by default and "You should update any copyright headers with your information." | A shuttle repository derived from the template is already under an open licence. Note that TT does **not** mandate publishing the design — the licence is permissive, so publication remains a separate, voluntary act. |
| GRLIB / NOEL-V and the GR801 brief | GRLIB is GPL with a paid commercial option; the FT variant is commercial-only (docs/03). Vendor documents are copyrighted. | Reference only. No GRLIB RTL enters the design. No manual text, table or register layout is copied — conventions may be *followed*, with the deviation documented, which is what `docs/08` already does. This is a copyright rule, not a licence choice, and it applies whether or not the repository is public. |

### 5.1 The "clean-room" claim is not free

docs/06's draft abstract called the engine "clean-room". docs/02 open
question 2 has not been answered: the project has not decided between
reusing Solderpad-licensed tinyODIN/ODIN RTL, using it only as a golden
reference, and implementing independently. Those are three different
licensing outcomes and three different truthful sentences. The word has
been removed from the docs/13 abstract for that reason (docs/13 D-14).
Deciding it is cheap now and expensive after RTL exists.

### 5.2 LGPL RTL is a bad fit for silicon

LGPL's central mechanism is the user's ability to replace the library
with a modified version and relink. There is no accepted equivalent for a
block fused into a fabricated die, and the obligation is at best unclear
and at worst read as requiring the netlist and the means to re-implement
the part. That ambiguity would sit inside a chip that also carries a
Bosch patent obligation, and it would complicate the dual-licensing
option of section 3.5. **[estimate]**, and the kind of estimate that
should be replaced by advice before any adoption **[legal]**.

Practical consequence: CAN is not in the funded scope in docs/13 anyway.
If it is adopted later, it lives in its own directory with its own
licence file and its own notice in the documentation, and the question
gets proper advice first.

---

## 6. Licence options

### 6.1 RTL and other hardware sources

| Option | What it does | For this project |
|---|---|---|
| **Apache-2.0** | Permissive, with an express patent grant and a patent-retaliation clause. Written for software; widely used for RTL (Ibex, OpenTitan, the IHP PDK, the TT templates). | Maximum adoption and zero inbound friction — every dependency above is already compatible. Costs all reciprocity: a competitor can take the fault-tolerance IP, improve it and close it. Simplest possible licence story. |
| **CERN-OHL-W-2.0** (weakly reciprocal) | Purpose-built for hardware. Modifications to the covered source must be released under the same licence; a larger product that *incorporates* the covered source need not be opened. The "Available Component" definition lets a design depend on generally available parts without dragging their sources in. | Improvements to the block flow back; a satellite integrator can still embed it in an otherwise-proprietary payload. That combination matches the intended users precisely — university programmes that will publish, and newspace integrators who will not. |
| **CERN-OHL-S-2.0** (strongly reciprocal) | Same family, but conveying a product built from the covered source obliges you to release the complete source for **the whole product**. | Strongest commons protection, and the most likely thing to stop an integrator adopting it: "put your entire satellite payload design under CERN-OHL-S" is a conversation most will decline. **[estimate]** Note the one-way compatibility: CERN-OHL-W covered source may be treated as CERN-OHL-S if all its available components satisfy the stricter definition, so starting at W does not permanently foreclose S for a future derivative. |

Assessment: **CERN-OHL-W-2.0 for RTL and hardware sources.** It is the
only one of the three designed for hardware, it keeps improvements
flowing back, and it does not impose a term the target adopters will
refuse. Apache-2.0 is the fallback if a specific collaboration or an
upstream contribution requires it — for example, code intended to be
merged into an Apache-2.0 upstream project should simply be Apache-2.0,
contributed upstream rather than mirrored.

Reciprocity is also the honest match to the project's own argument:
`docs/05` section 3.2(b) sells auditability as the differentiator. A
licence that lets a derivative be closed undercuts that argument;
weak reciprocity preserves it without making the block unusable.

### 6.2 Software

Golden model, register-map generator, host and bring-up software, test
harnesses, analysis scripts: **Apache-2.0.** It matches Ibex, OpenTitan
and the IHP PDK, it carries an explicit patent grant, and it is the
licence people expect on tooling they are meant to reuse. The golden
model is the executable specification of the RTL, so a permissive licence
here maximises the chance that someone else's implementation is checked
against it — which is the point.

### 6.3 Documents and data

- Technical documents (`docs/`): **CC-BY-4.0.** Attribution only. NLnet
  requires open access for scientific outcomes; CC-BY satisfies it and
  keeps the documents quotable. CC-BY-SA is the reciprocal alternative
  and would be defensible, but share-alike on documentation mostly
  creates friction for people who want to quote a table into their own
  differently-licensed report. **[estimate]**
- Radiation dataset and measurement data: **CC0-1.0** or **CC-BY-4.0**.
  Recommendation CC-BY-4.0 for consistency; the argument for CC0 is that
  facts are not copyrightable anyway and CC0 removes the argument.
  **[D]** — developer's call.
- Nothing derived from vendor documents is republished, per section 5.

### 6.4 Summary of the proposed licence set

| Artefact class | Proposed licence |
|---|---|
| RTL, testbenches, constraints, flow scripts producing hardware | CERN-OHL-W-2.0 |
| Golden model, generators, host/bring-up software, analysis scripts | Apache-2.0 |
| Documents in `docs/` | CC-BY-4.0 |
| Measurement datasets | CC-BY-4.0 (CC0-1.0 alternative) |
| Vendored third-party code, if any | unchanged, in its own directory, with its own notices |

Mechanics: SPDX identifiers in every file header, a `LICENSE` directory
holding the full texts, a `LICENSES.md` mapping paths to licences, and a
CI check that fails on a source file without an SPDX tag. That check is
also what makes the section 4 scope claim mechanically true.

---

## 7. The export-control interaction

**[legal]** throughout. This section frames the question and records the
project's own rules; it is not advice, and the decision in section 9
should be taken with advice on the points marked below.

What is settled and internal to the project:

- `docs/05` section 4 rule 2: the device is "fault-tolerant", never
  "rad-hard". Rule 3: never claim, target or advertise total-dose
  ratings at or above 100 krad(Si), and no language mapping the device
  into space-qualified rad-hard categories. Rule 1: the stated class is
  LEO, 10-30 krad(Si), pending test data. Rule 4: multi-market framing.
- These rules already assume public text — they were written for
  "README, datasheets, pitch material, shuttle submissions, conference
  abstracts". Publishing the repository does not create a new claim
  surface; it enlarges an existing one that is already governed.

What publication changes:

1. **Irreversibility.** Published RTL and published data cannot be
   withdrawn. Everything published must be inside the docs/05 envelope
   at the moment of publication, because there is no later correction
   that removes it from circulation. This argues for a publication
   checklist, not against publication.
2. **Direction of travel.** Publication tends to *reduce* exposure rather
   than increase it: dual-use regimes generally treat information already
   in the public domain differently from controlled technology, and the
   sibling programme's position is that its results are published
   research kept below the claim thresholds
   **[developer-supplied; confirm before relying on it]**. Whether that
   reasoning holds under the Turkish implementation of the relevant
   dual-use regime, and what obligations attach to the *act* of
   publishing, is precisely the question that needs advice. **[legal]**
3. **The dataset is the sharp edge.** RTL and documents stay inside the
   docs/05 envelope by construction. A measured total-dose dataset is
   different: the measurement could come back above the class the project
   advertises. Handling rule, decided in advance rather than under
   pressure: publish the measurement as measured, describe it as a
   measurement of a specific design in a specific library under a
   specific procedure, and do **not** convert it into a device rating, a
   marketing claim or a qualification statement. A number in a dataset is
   not a rating, and the distinction must be explicit in the dataset's
   own README.
4. **NLnet reinforces the same discipline.** The review team verifies
   claims independently; the application text and the repository text
   must agree, and both are governed by docs/05. There is no version of
   this project where an aggressive radiation claim is safe.

Net assessment: publication and the export-safe posture are compatible,
and are compatible *because* the positioning rules were set conservatively
before publication was on the table. The residual item is item 2, which
is a question for qualified advice and is listed as an action in
section 9 with a date. **[legal]**

---

## 8. The options

| Option | Description | Effect on NLnet | Effect on the sibling posture | Verdict |
|---|---|---|---|---|
| A | Stay private; do not apply to NLnet | n/a | Preserved | Rejected. Forfeits the funding, and Restack's budget is "expected [to be fully allocated] early 2027", so the option does not stay open. **[fact]** |
| B | Publish the entire repository now, everything under one licence | Strongest evaluation position | Abandons "public at tapeout" wholesale | Rejected as over-broad: it publishes commercial positioning material that is not a funded artefact and gains nothing for it |
| C | Publish a defined funded scope now, under the section 6.4 licence set; the rest stays private until its own gate | Satisfies every requirement; strong evaluation position; nothing to renegotiate at MoU | Preserves the tapeout gate for everything outside the funded scope | **Recommended** |
| D | Publish nothing until MoU signature | Legal minimum (section 3.1) | Preserves the posture longest | Rejected: gives up the stage-1 and stage-2 evidence benefit for a delay of a few months that buys nothing, and concentrates all the mechanical work (licence headers, scope split, CI) into the busiest possible moment |

On the sibling precedent specifically: "public at tapeout" is a sound
rule for a product whose competitive value is in the design itself and
whose funder is the developer. It is not compatible with a funder that
pays per published milestone, because the first milestones are RTL and
proofs — months or years before any tapeout. The two rules can coexist
only by scope: funded artefacts follow the funder's rule, unfunded
product work keeps the tapeout gate. That is option C, and it is why C
is a reconciliation rather than a surrender.

One thing option C does not do is preserve optionality. Publication is
one-way. If the application is unsuccessful, the funded-scope artefacts
stay public; the decision has to be worth taking on its own merits, not
only as a bet on the grant. The argument that it is: the project's stated
differentiator is auditability (docs/05 section 3.2(b)), the pilot design
goes to a community shuttle whose ecosystem norm is publication, and the
prior tt-um-lif-crossbar design is already public. A private repository
was the right default during a research phase whose facts were not yet
checked; that phase closed with the docs/07 review.

---

## 9. Recommendation and action plan

**Recommendation: option C.** Publish a defined funded scope now, under
CERN-OHL-W-2.0 for hardware sources, Apache-2.0 for software, CC-BY-4.0
for documents and data; keep commercial and product-line material
private; state the scope and the licences in the NLnet application so
that the MoU has nothing to negotiate.

Action plan. Dates are chosen to sit inside the docs/13 section 8
submission schedule and to keep the TTIHP26b close (2026-09-21) clear.

| Date | Action | Owner |
|---|---|---|
| 2026-08-31 | Sign or reject this memo (section 11). If rejected, docs/13 D-6 defaults to a blank website field and the application says explicitly when publication will occur | developer |
| 2026-09-02 | Decide docs/02 open question 2 — Solderpad reuse versus independent implementation — because it changes both the RTL provenance notices and whether "clean-room" may be written anywhere (docs/13 D-14) | developer |
| 2026-09-07 | Draw the scope boundary: list every path that is in the funded scope and every path that is not. One table, no ambiguity | engineering |
| 2026-09-14 | Land the licence mechanics on the in-scope tree: `LICENSE` directory with full texts, `LICENSES.md` path map, SPDX headers in every source file, third-party notices | engineering |
| 2026-09-18 | CI job: clean checkout of the public tree builds, simulates and proves with no access to private paths; SPDX tag check fails the build on an untagged source file | engineering |
| 2026-09-21 | TTIHP26b submission. The template is Apache-2.0 already; the shuttle repository is published with the same licence set and the same headers | developer |
| 2026-09-30 | Obtain advice on section 7 item 2: the publication/export interaction under the applicable Turkish rules, and whether any obligation attaches to the act of publishing **[legal]** | developer |
| 2026-10-05 | Make the public repository (or mirror) public with a README that states the scope, the licences and the docs/05 positioning rules verbatim | developer |
| 2026-10-15 | docs/13 D-6 and D-7 closed with real URLs; application text updated to describe the published state as a fact rather than a promise | developer |
| 2026-10-29 | Submit the application (docs/13 section 8) | developer |
| at MoU | Name the section 6.4 licences as MoU terms; stand up the public status page and the two-monthly reporting cadence required by the MoU | developer |
| at each milestone | Publish the milestone artefacts complete, then request payment | developer |

Explicitly deferred, not decided here:

- CAN core adoption and its LGPL and Bosch-patent consequences
  (section 5.2). Out of the funded scope; revisit with advice when the
  interface phase starts.
- Whether the public tree is the same repository made public or a curated
  mirror. Either satisfies NLnet. A single repository is less work and
  less prone to divergence; a mirror is safer if private history contains
  anything that should not be published. The deciding question is whether
  the existing git history is publishable as-is — check before
  2026-10-05. **[estimate]**
- CC0 versus CC-BY for datasets (section 6.3).

---

## 10. Consequences of accepting the recommendation

- ROADMAP gate G2 becomes satisfiable: the repository state and the
  application's promises agree, because the promise is in the past tense.
- The docs/13 experience and website fields gain verifiable URLs, which
  is worth real score on a 30%-weighted criterion. **[estimate]**
- Commercial optionality is preserved: the developer keeps copyright and
  may licence additionally, including proprietarily (section 3.5).
  This depends on not accepting third-party contributions into the
  dual-licensed tree without a contributor agreement or a matching
  licence grant — a governance item to set up before the repository
  attracts contributors. **[estimate]**
- The publication decision is irreversible, and it lands before the
  funding decision is known (section 8).
- Roughly 12-20 h of mechanical work (scope table, licence headers, CI
  check, README) lands in September, in the same window as the TTIHP26b
  close. The effort budget in docs/06 B.6.1 does not include it.
  **[estimate]** If that window is genuinely full, moving the licence
  mechanics to the first week of October is acceptable; moving the
  *decision* is not, because docs/02 open question 2 and the shuttle
  submission both need the answer.

---

## 11. Sign-off

| Item | Decision | Date | Signature |
|---|---|---|---|
| Option C: publish a defined funded scope now | accept / reject / amend | | |
| RTL and hardware sources: CERN-OHL-W-2.0 | accept / reject / amend | | |
| Software: Apache-2.0 | accept / reject / amend | | |
| Documents: CC-BY-4.0 | accept / reject / amend | | |
| Datasets: CC-BY-4.0 (CC0-1.0 alternative) | accept / reject / amend | | |
| Scope boundary table (due 2026-09-07) | approved | | |
| Export advice obtained (due 2026-09-30) | done / waived with reasons | | |

Until this table is completed, `docs/13-nlnet-application.md` D-6 and D-7
remain open and the application must not be submitted with a claim about
the repository's public state.
