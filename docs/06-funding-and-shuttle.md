# Funding and shuttle plan: NLnet grant and TTIHP26b

Research report for the neuromorphic space SoC (GR801-class retarget to
130 nm, see `docs/00-reference-brief.md`). All web facts checked on
2026-08-24; items that could not be fully verified are marked
**[unverified]** or **[estimate]**.

**Re-checked 2026-08-31.** Every external fact this document depends on
was re-read from primary sources on that date and the result is recorded
in `docs/37-external-check.md`. The three things that decide what happens
next — the 2026-09-21 close, the 2026-11-03 NLnet deadline, and the
availability of the 6x2 tile shape — all held. Six statements below did
not, and each is corrected in place with the superseded text kept and the
correction marked **Corrected 2026-08-31**: A.3 (Restack rules now
published), A.7 and the combined timeline (decision lag), B.1 (the close
carries a time of day), B.2 (analog-pin table and the tile-only cost
lines), B.4 (there is no June 2026 IHP release), and B.6 (the purchasable
tile shape is confirmed, and the cost lines omit the devkit and
shipping). Nothing in that check required a change to the design, the
flow, the pinned PDK or the pinned toolchain.

Two external clocks drive the plan:

- **TTIHP26b shuttle closes 2026-09-21 at 20:00 UTC** — 23:00
  Europe/Istanbul, not local midnight (B.1).
- **NLnet calls reopen 2026-09-03, next submission deadline 2026-11-03
  12:00 CEST** (https://nlnet.nl/propose/).

---

## Part A — NLnet funding

### A.1 Current call situation (August 2026)

NLnet is in a transition period. The apply page
(https://nlnet.nl/propose/) states there are currently **no open
calls**: calls reopen on **September 3rd 2026** with a submission
deadline of **November 3rd 2026, 12:00 CEST (noon)**. The long-running
NGI Zero programme is winding down — the thirteenth and final call of
the NGI Zero Commons Fund closed on June 1st 2026
(https://nlnet.nl/commonsfund/) — and NLnet is preparing successor
programmes under the "Open Internet Stack" umbrella
(https://nlnet.nl/news/2026/20260612-NGIZero-stocktaking.html):

| Fund | Scope | Fit for this project |
|---|---|---|
| **Restack** (https://nlnet.nl/restack/) | "Technology building blocks across the internet stack", explicitly including **"libre chips and hardware"**; EUR 7 million in small/medium R&D grants through 2030 | **Primary target.** Open silicon is named in scope. |
| CodeSupply | Maintenance/supply-chain support for existing code **[scope unverified — page thin as of Aug 2026]** | Not a fit for new silicon |
| ELFA (https://nlnet.nl/ELFA/) | "Encrypted Local First Architecture" — E2E-encrypted, local-first software | Not a fit (software only) |
| NGI Taler / NGI Fediversity pilots | Still open on the regular bi-monthly schedule | Not a fit (payments / hosting topics) |

**Conclusion: apply to Restack when the call opens on 2026-09-03;
submit well before the 2026-11-03 deadline.** The historic bi-monthly
cadence (Feb 1 / Apr 1 / Jun 1 / Aug 1 / Oct 1 / Dec 1) is suspended
during the transition; Nov 3 is the confirmed next deadline. Expect the
cadence to resume in some form afterwards **[unverified]**.

### A.2 Grant size

- Commons Fund and Restack both state a request range of **EUR 5,000 to
  50,000** for a first proposal, "with the possibility to scale up
  significantly if there is proven potential"
  (https://nlnet.nl/restack/, https://nlnet.nl/commonsfund/).
- Under the Commons Fund rules, follow-up proposals could go to
  EUR 150,000 per proposal with a EUR 500,000 lifetime cap per third
  party (https://nlnet.nl/commonsfund/guideforapplicants/). Restack
  follow-up limits are not yet published **[unverified]**.

### A.3 Eligibility (individual, Turkey-based)

**Corrected 2026-08-31 — the Restack rules are published and this
section no longer needs a proxy.**

**Superseded text**, kept as it stood: "From the NGI Zero Commons Fund
eligibility page (https://nlnet.nl/commonsfund/eligibility/) —
**Restack-specific rules are not yet published**, but NLnet's baseline
policy has been stable".

**Replacement.** Restack now publishes its own eligibility page, guide
for applicants and FAQ (https://nlnet.nl/restack/eligibility/,
https://nlnet.nl/restack/guideforapplicants/,
https://nlnet.nl/restack/faq/ — all three read 2026-08-31), and those
pages are the authority for the three bullets below. The Commons Fund
pages remain a valid cross-check but must no longer be cited as the
source of Restack's rules. `docs/13` sections 1.3 and 2.3 already work
from the Restack pages directly and are the more detailed record.

**What moved:** the source of authority only. The substance of the three
bullets was re-read against the Restack pages on 2026-08-31 and is
unchanged — including the geography clause, which the Restack
eligibility page states in the same words. Note one framing point the
Restack FAQ makes explicit: a "European dimension" is a **knock-out
criterion**, not a tiebreak. **[fact]**

~~Caveat, and it is why action item 6 and `docs/13` [D-13] stay open: the
Restack landing page still describes the fund as "currently being set
up" and its guide for applicants as **preliminary**, so these pages may
change at the 2026-09-03 call opening. Re-read them on or just after
that date.~~

> **RE-READ 2026-09-12, nine days late** — the date above was 2026-09-03
> and nothing in this repository noticed it pass. What the three pages
> say now **[fact, read 2026-09-12 from `nlnet.nl/restack/`,
> `/restack/eligibility` and `/restack/guideforapplicants`]**:
>
> - **The fund is open and the preliminary labels are gone.** The
>   landing page no longer says "currently being set up"; it says the
>   first call opened **2026-09-03** with a deadline of **2026-11-03,
>   12:00 CET (noon)**. Neither the eligibility page nor the guide for
>   applicants is labelled preliminary any more.
> - **The application link is live.** "Submit a proposal" now points at
>   `/propose`; it read "Coming soon" on 2026-08-31.
> - **The ceiling is higher than this document recorded.** The landing
>   page says proposals run **EUR 5,000 to EUR 50,000**, and the guide
>   adds that a FIRST proposal may request up to **50 kEUR**, a single
>   proposal may reach **150 kEUR**, and one third party may receive
>   **500 kEUR** over its lifetime.
> - **Eligibility is broader than assumed.** *"There are no categorical
>   exclusions of persons who may not receive support from Restack."*
>   EU and Horizon-Europe-associated applicants get priority only when
>   proposals are otherwise equal; a non-EU applicant is eligible on
>   exceptional quality, unique technical expertise and a clear European
>   dimension. **Open hardware development is explicitly in scope**, as
>   are security audits, formal proofs, documentation and standards
>   work — which is most of what this repository consists of.
> - **One requirement lands directly on this project and is already
>   met:** *"any software and hardware MUST be published under a
>   recognised open source license in its entirety."* `docs/14` signed
>   that on 2026-09-09 — CERN-OHL-W-2.0 for the hardware, Apache-2.0
>   for the tooling, CC-BY-4.0 for the documents — and both public
>   repositories carry the texts. **"In its entirety" is worth reading
>   twice against `docs/78`**, which publishes a CURATED mirror and
>   holds three documents back; none of the three is software or
>   hardware, so the clause is met as written, but a reader of that
>   sentence who expected the whole development repository would not
>   find it.
> - **Neither page states an hourly or daily rate**, so `docs/13`'s open
>   decision about the rate is not answered by re-reading — it is a
>   choice, not a lookup. No page-limit or proposal-length rule either.
>
> The exact deadline time is new and narrower than this document's
> "submit at least a week before 2026-11-03": **noon CET on the 3rd**,
> not the end of that day.

The rules, read off the Restack pages on 2026-08-31:

- **Individuals are eligible.** There are "no categorical exclusions of
  persons who may not receive support" — natural persons, companies,
  non-profits all qualify.
- Geography: "inhabitants of the EU and countries associated to Horizon
  Europe are given priority." **Türkiye is an associated country to
  Horizon Europe** for the 2021-2027 framework
  (https://research-and-innovation.ec.europa.eu/strategy/strategy-research-and-innovation/europe-world/international-cooperation/association-horizon-europe/turkiye_en,
  https://tubitak.gov.tr/en/node/14570), so a Turkey-based applicant
  falls inside the **priority group**, not the exception path.
  Association for the 2028-2034 period is still under negotiation as of
  2026 **[monitor]** — irrelevant for a 2026 application against the
  2021-2027 framework.
- Even for non-associated countries, projects "of exceptional quality"
  with "a clear European dimension" are eligible. This project's
  European dimension is strong regardless: the target PDK is from IHP
  (a German Leibniz institute), fabrication is in Frankfurt (Oder), and
  the output strengthens the European open-silicon commons.

### A.4 What NLnet funds — open-silicon precedents

NLnet has funded roughly 1,430 projects over the NGI period
(https://nlnet.nl/news/2026/20260612-NGIZero-stocktaking.html),
including a substantial open-hardware/silicon portfolio
(https://nlnet.nl/thema/Hardware.html). Verified precedent project
pages (all URLs return 200 as of 2026-08-24):

| Project | Relevance | URL |
|---|---|---|
| Libre-SOC | Full open SoC effort (~EUR 400k across grants), taped out at 180 nm | https://nlnet.nl/project/Libre-RISCV/ |
| Chips4Makers | Libre standard cells + 0.18 um ASIC manufacturing of Libre-SOC test chip | https://nlnet.nl/project/Chips4Makers/ |
| Coriolis2 | Open ASIC layout tooling (Sorbonne) for Libre-SOC | https://nlnet.nl/project/Coriolis2/ |
| FABulous Demo SoC | Open eFPGA fabric + RISC-V SoC built with open tools | https://nlnet.nl/project/FABulous-SoC/ |
| LunaPnR | Open place-and-route tool | https://nlnet.nl/project/LunaPnR/ |
| LibreSilicon | Open semiconductor process | https://nlnet.nl/project/LibreSilicon/ |
| LiteX | FPGA/ASIC SoC framework | https://nlnet.nl/project/LiteX/ |
| NaxRiscv | Out-of-order RISC-V with ASIC synthesis | https://nlnet.nl/project/NaxRiscv/ |

~~Notable gap: **no space/SpaceWire/satellite-silicon precedent was
found in the funded-projects list.**~~ **Withdrawn 2026-08-29 — this
sentence is wrong and must not be lifted into the application.** A
second search of the portfolio, recorded in
`docs/13-nlnet-application.md` section 1.6, found a directly comparable
funded project: **INA-ASIC**, a space-grade instrumentation amplifier
ASIC (NGI0 Commons Fund, start 2026-03), taped out on IHP's 130 nm open
PDK — the same PDK this project hardens on — and explicitly scoped to
be "robust to high radiation environments, making it applicable to low
earth orbit / high energy particle applications"
(https://nlnet.nl/project/INA-ASIC). Space silicon on the same open
process is therefore *inside* NLnet's precedent, not outside it.
`docs/13` section 1.6 lists four further precedents in the same
direction (GLOW-SG13G2, Borg II, PowerCommons, FPGA-Inject) and is the
authority on this question; the table above is a subset of what is
funded, not a survey. **[fact, per docs/13 section 1.6, re-checked
2026-08-29]**

The framing advice that followed the withdrawn sentence still stands,
but for a different reason and with less force: frame the project as an
**open-silicon commons building block** (open SNN IP, open
fault-tolerance IP, open flow on a European open PDK) whose first
application domain happens to be small satellites, because that is what
it is — not because a space framing is unprecedented. ASIC tapeouts,
standard cells, EDA tools and now radiation-tolerant silicon on IHP
130 nm are all squarely within precedent.

### A.5 Application format

Based on the historic NLnet form (the Restack form opens 2026-09-03 and
should be re-checked then **[re-verify at call opening]**):

- Contact info, project name, requested amount (EUR 5,000-50,000).
- **Abstract, advisory 1,200 characters, hard `maxlength` 1,500**
  — explain the whole project and expected outcomes. **Corrected
  2026-08-29:** this line previously read "maximum 1,200 characters",
  which presented an advisory number as a hard ceiling. The 1,200 is
  correct and it is the figure to write to, but it is the *placeholder*
  advisory printed in the field; the form's `maxlength` attribute is
  1500. `docs/13-nlnet-application.md` section 1.2 read both off the
  raw form markup and is the authority — it also shows that the same
  advisory/hard split applies to five other fields, with the two
  disagreeing by up to a factor of four, and that the advisory is what
  the application is written to. **[fact, per docs/13 section 1.2]**
  Longer outlines can go in attachments — but see docs/13 section 1.2
  on how blunt the attachment guidance is (confirmed in applicant
  reports, e.g.
  https://ar.al/2024/06/01/small-technology-foundation-funding-application-for-nlnet-foundation-ngi-zero-core-seventh-call/).
- Prior experience of the applicant.
- **"Compare your own project with existing or historical efforts"** —
  a dedicated field; for this project: GR801 (proprietary, 28 nm FDSOI),
  BrainChip Akida (proprietary IP), open SNN cores such as ODIN/ReckOn
  (open but not fault-tolerant, not SoC-integrated, not on an open PDK),
  Libre-SOC (open SoC but general-purpose, no fault tolerance or space
  interfaces).
- Budget plan: what the money will be used for, broken into work
  packages/activities with amounts.
- Two-stage evaluation (Commons Fund weights, likely similar for
  Restack **[unverified]**): technical excellence/feasibility 30%,
  relevance/impact/strategic potential 40%, cost effectiveness 30%;
  threshold 5.0/7.0. Stage 2 is an interactive Q&A on comparisons,
  sustainability, and budget justification
  (https://nlnet.nl/commonsfund/guideforapplicants/).
- On selection, a **Memorandum of Understanding** is negotiated (sample:
  https://nlnet.nl/foundation/request/sample_MoU.pdf) defining tasks,
  milestones, and payment per completed milestone (no upfront payment;
  payments follow delivered, published results).
- NLnet runs a monthly office hour for applicant questions
  (https://nlnet.nl/officehour/).

### A.6 Open-licensing mandate — and the private-repo tension

The licensing requirement is absolute: "any software and hardware must
be published under a recognised open source license **in its entirety**"
(https://nlnet.nl/commonsfund/guideforapplicants/); "project results
always become available under a free or open source license"
(https://nlnet.nl/commonsfund/). MoU milestone payments are tied to
published results.

**This repository is currently private.** An NLnet application is a
commitment that every funded artifact — RTL, testbenches, flow scripts,
documentation, bring-up results — is published under free licenses.
**Corrected 2026-08-29:** this line originally read "Apache-2.0 or
CERN-OHL-S for hardware sources, CC-BY for docs", written before the
licence question was analysed. `docs/14-licensing-decision.md` section 9
recommends **CERN-OHL-W-2.0 for RTL and hardware sources**, Apache-2.0
for software and CC-BY-4.0 for documentation, and gives the reason
CERN-OHL-S is the wrong choice here: conveying a product built from
CERN-OHL-S source obliges the integrator to release the source for the
whole product, which is the most likely single thing to stop a
newspace payload integrator adopting the block. CERN-OHL-W keeps
improvements flowing back without that demand, and W-covered source may
later be treated as S, so starting at W forecloses nothing.
`docs/14` is the authority; nothing in this document should be quoted
against it. Note that the docs/14 recommendation is a recommendation —
its section 10 decision table is not yet signed off. **[fact for what
docs/14 recommends]**

The sibling project's "public at tapeout" posture is **not compatible**
with an NLnet grant timeline: the repo (or a curated public mirror of
the funded scope) must be public no later than the MoU stage, and being
public at submission time materially helps evaluation (reviewers check
prior work). Decision required before applying (action item 5).

### A.7 Timeline: submission to decision to MoU

**Corrected 2026-08-31 — this section paired both announcements with the
wrong call round, and every date derived from it was three to four months
early.**

**Superseded text**, kept as it stood: "Observed 2026 data points for the
Commons Fund: the **December 2025 call** was announced on 2026-03-02 (44
projects, https://nlnet.nl/news/2026/20260302-announce-commons-fund.html)
and the **February 2026 call** on 2026-04-09 (57 projects,
https://nlnet.nl/news/2026/20260409-announce-commons-fund.html) — i.e.
**roughly 2-3 months from deadline to selection announcement**, including
one Q&A round. ... For the 2026-11-03 deadline: decision around
**January-February 2027**, MoU and start around **February-April 2027**."

**Why it moved.** Neither announcement decides the round this document
attributed to it. Each names its own round in as many words. The
2026-03-02 item reads "This is the selection for the **August** call of
the NGI Zero Commons Fund fund only"; the 2026-04-09 item reads "This is
the selection for the **October** call of the NGI Zero Commons Fund fund
only" **[fact — both sentences read verbatim from the announcement pages
on 2026-08-31]**. On NLnet's bi-monthly cadence those are the 2025-08-01
and 2025-10-01 deadlines, so the elapsed times are **213 days (7.0
months)** and **190 days (6.3 months)**, not two to three months. The
error was not a stale number; it was an attribution mistake that made the
observed lag look less than half its real size.

**Replacement, with fact and estimate separated.**

- **NLnet's advertised figure, quoted as NLnet's claim:** "You can expect
  the process to take between three and five months. This is counted from
  the date of the deadline of the open call, not from the date you have
  submitted a proposal" (https://nlnet.nl/restack/faq/, read 2026-08-31).
  **[fact that NLnet states this]** — it is not the observed rate.
- **Observed 2026 rate:** the two announcements above, each traced to the
  round it names, ran **6.3 and 7.0 months**. The wider set of 2026
  announcements falls in the **4.3-6.5 month** range (`docs/37`
  section 2). **[fact]**
- **Projection for a 2026-11-03 deadline:** decision **2027-03 to
  2027-06**, taking the full observed 4.3-7.0 month spread. MoU
  negotiation adds **1-2 months** before work formally starts, so MoU and
  start **2027-04 to 2027-08**. **[estimate — a projection from two
  verified data points and a range, not a commitment by the funder]**
- First disbursements only after first milestones are delivered and
  published. Unchanged.

**What moved:** the call round each announcement decides, and therefore
the observed lag (2-3 months to 6.3-7.0 months), the decision window
(2027-01/02 to 2027-03/06) and the MoU window (2027-02/04 to
2027-04/08). What did not move: NLnet's own advertised 3-5 months, which
is unchanged on the FAQ and is now labelled as the funder's claim rather
than as evidence.

**Consequence for the decision to apply, which is unchanged and if
anything stronger.** A later decision pushes the expected award closer to
the "budget of the programme has been fully allocated (expected early
2027)" horizon (A.1, `docs/13` section 1.3 item 3). That argues for
submitting into the November round rather than a later one, not against
it. What it does change is what may be promised about when funded work
starts: `docs/13` section 5's milestone plan and its 12-month default
must be read against an MoU in mid-2027, not early 2027.

### A.8 Skeleton application draft

**Working title:** "Open fault-tolerant neuromorphic SoC for small
satellites" (project short name to decide; repo name
`neuromorphic-space-soc` works).

**Abstract draft (1,142 characters, advisory limit 1,200, hard 1,500).
Superseded 2026-08-29 — do not submit this text.** The live abstract is
`docs/13-nlnet-application.md` section 3.4, inside its
`field:abstract` markers; that is the text the application uses and the
only one kept to character count. The draft below is retained as the
2026-08-24 starting point, and it carries one defect that must not be
copied out of it:

- **"clean-room" is not authorised.** The draft describes the engine as
  a "clean-room event-driven spiking neural network engine". Whether the
  engine is clean-room is undecided: `docs/02-npu-architecture.md` open
  question 2 asks whether to reuse Solderpad-licensed tinyODIN/ODIN
  Verilog directly, use it only as a golden reference, or stay fully
  clean-room, and it is still open — `docs/13` tracks the resolution as
  **[D-14]**, due 2026-09-02. The word is therefore a claim this project
  cannot currently make. The docs/13 section 3.4 abstract omits it
  deliberately and says so. Until D-14 closes, the engine is
  "event-driven", not "clean-room". **[fact — the open question is open
  in docs/02]**

> Small satellites increasingly need on-board AI inference, but the
> only radiation-tolerant neuromorphic SoC announced to date
> (Frontgrade Gaisler GR801) is proprietary, built on 28 nm FDSOI, and
> out of reach for university and small-team missions. This project
> develops an open-source, fault-tolerant SoC for event-driven neural
> inference on CubeSat-class satellites: a RISC-V management core, a
> clean-room event-driven spiking neural network engine with low-bit
> quantized weights, ECC-protected on-chip memory, and spacecraft
> interfaces (SpaceWire, CAN, SPI, I2C, UART), hardened by architecture
> (TMR control logic, memory scrubbing, fault counters) rather than by
> a proprietary process. All RTL, the verification suite, and the
> physical-design flow are published under free licenses and target
> IHP's open-source SG13G2 130 nm PDK, with silicon validation on
> affordable community shuttles (Tiny Tapeout) and radiation
> pre-screening of the fabricated parts. The result is a reusable,
> auditable European open-silicon building block: a reference design
> and IP set that lets any team fly inspectable AI hardware instead of
> black-box accelerators.

**Budget sketch (EUR 15-30k window; all figures [estimate]):**

| Work package | Content | EUR |
|---|---|---|
| WP1 SNN engine + hardening IP | Event-driven SNN fabric RTL, TMR/ECC/scrub blocks, verification suite (developer time, ~5 months) | 10,000 |
| WP2 SoC integration + flow | RV32 manager integration, SpaceWire/CAN/peripheral subset, LibreLane sg13g2 flow, docs (developer time, ~3 months) | 6,500 |
| WP3 Shuttle silicon | TTIHP26b pilot (~~8 tiles ~EUR 560 default, 12 tiles ~EUR 840 for the SRAM-macro variant~~ — **corrected 2026-08-31**: those were tile-only. Full order totals with one subsidised devkit and shipping are **EUR 675 at 8 tiles and EUR 955 at 12**, per B.2; the frozen submission is the 12-tile 6x2, so **EUR 955** is the figure) + follow-up TT run gated per B.6.2 (TTIHP27a on pre-silicon evidence, or silicon-results-gated TTIHP27b/IHP MPW; 16-32 tiles, EUR 1,120-2,240) + devkits/breakout PCBs | 3,500 |
| WP4 Bring-up hardware | Test boards, FPGA host board, instrumentation for characterization | 2,500 |
| WP5 Radiation pre-screening | TID (Co-60) campaign on shuttle parts, test-board mods, logistics; facility-dependent | 5,000 |
| **Total** | | **27,500** |

Rationale for the developer-time rates: NLnet funds individuals at
modest, justified rates; the budget must map to concrete published
milestones (MoU structure rewards small, verifiable work packages).

---

## Part B — TTIHP26b shuttle (Tiny Tapeout on IHP SG13G2)

### B.1 Shuttle confirmed, dates

TTIHP26b is **confirmed and currently open** — it is listed as an open
shuttle with a live countdown on https://tinytapeout.com/ alongside
SKY26c. Per the shuttle index (https://app.tinytapeout.com/shuttles/),
TTIHP26b **launched 2026-07-27 and closes 2026-09-21**, maps to IHP
fab run IHP-2609, with **chips expected 2027-06-25** and estimated
board delivery **2027-08-16** **[dates from the shuttle app as indexed
2026-08-24; re-confirmed 2026-08-31, see below]**.

**Corrected 2026-08-31 — the close carries a time of day this document
never recorded.**

**Superseded statement**, kept as it stood: "closes **2026-09-21**",
stated as a date with no time anywhere in this repository.

**Replacement.** The shuttle record gives
`"deadline":"2026-09-21T20:00:00+00:00"` — **20:00 UTC, i.e. 23:00
Europe/Istanbul on 2026-09-21**. Submission *and payment* must both be
complete before that instant. **[fact — read 2026-08-31 from the shuttle
application's own read-only API,
`https://tinytapeout.supabase.co/rest/v1/shuttles?slug=eq.ttihp26b`,
which is what the site itself computes the countdown from; the date is
cross-checked against the server-rendered https://tinytapeout.com/chips/,
which lists "TTIHP26b 2026-07-27 2026-09-21 IHP-2609 Open 2027-06-25
2027-08-16".]**

**What moved:** nothing about the date, which holds. What was added is
three hours that anyone planning to submit on the final day would
otherwise have assumed they had. A deadline whose hour is unknown is a
deadline missed by a day.

The same record confirms two things this document had not carried
**[fact, same source and date]**: capacity is not a risk —
`tiles_total: 240` against `tiles_used: 50`, so 190 tiles are free and a
12-tile buy cannot be squeezed out by a sell-out; and
`subsidized_pcbs_total: 100` against `subsidized_pcbs_sold: 12`, so **88
subsidised devkit PCBs remain**, which is worth EUR 200 on the order
(B.2). The record also carries `analog_total: 0` — there are no analog
slots on this run at all.

Reference cadence of prior IHP runs (two per year):

- TTIHP25a: closed 2025-03-28, delivery ~Feb 2026
  (https://tinytapeout.com/chips/ttihp25a/)
- TTIHP25b: autumn 2025 run (https://tinytapeout.com/chips/ttihp25b/)
- TTIHP26a: closed 2026-03-23 (https://tinytapeout.com/chips/ttihp26a/)
- TTIHP27a: expected ~March 2027 **[extrapolation, unannounced]** —
  closes before TTIHP26b silicon exists, so it can only serve as a
  pre-silicon-gated follow-up slot (B.6.2).

Fab-to-board lag on IHP runs is long (~9-11 months tapeout to boards);
prior runs were partially subsidized by SwissChips and the German BMBF
FMD-QNC project (https://tinytapeout.com/chips/ttihp25a/).

### B.2 Tile geometry and pricing: IHP vs SKY130

Hard numbers from the Tiny Tapeout build system
(`tt-support-tools/tech/*/tile_sizes.yaml`,
https://raw.githubusercontent.com/TinyTapeout/tt-support-tools/main/tech/ihp-sg13g2/tile_sizes.yaml
and
https://raw.githubusercontent.com/TinyTapeout/tt-support-tools/main/tech/sky130A/tile_sizes.yaml):

| Metric | SKY130 | IHP SG13G2 | Ratio |
|---|---|---|---|
| 1x1 tile | 161.00 x 111.52 um = 0.01795 mm2 | 202.08 x 154.98 um = 0.03132 mm2 | IHP 1.74x larger |
| Largest block def | 8x4 (1378.16 x 511.36 um = 0.705 mm2) | 8x4 (1724.16 x 710.64 um = 1.225 mm2) | — |
| Available shapes (IHP) | — | 1x1, 1x2, 2x1, 2x2, 3x1, 3x2, 3x4, 4x1, 4x2, 4x4, 5x4, 6x1, 6x2, 6x4, 8x1, 8x2, 8x4 | — |

- **Pricing:** **EUR 70 per tile** on IHP shuttles. Current prices:
  https://app.tinytapeout.com/calculator (per
  https://tinytapeout.com/faq/ and https://tinytapeout.com/specs/analog/).

**Corrected 2026-08-31 (a) — the analog-pin prices quoted here are
SKY130's, not IHP's.**

**Superseded text**, kept as it stood: "analog pins **EUR 40 each for the
first two, EUR 100 thereafter** (not needed here — digital-only design)".

**Replacement.** That is the **ChipFoundry/SKY130** table. The **IHP**
table is **EUR 200 per analog pin with no discounted allowance**. Read
verbatim on 2026-08-31 from the price literals in the shipped calculator
bundle `https://app.tinytapeout.com/_build/assets/invoice-D5ozDQq9.js`,
which is what the calculator computes from: IHP is
`{pcb:300, pcbDiscount:100, tile:70, analogPin:200, analogPinDiscount:40,
discountedAnalogPins:0, shipping:15, currency:"EUR", maxAnalogPins:16}`
against ChipFoundry's `{... analogPin:100, discountedAnalogPins:2,
analogPinDiscount:40 ...}`. The `analogPinDiscount:40` present in the IHP
object is inert, because `discountedAnalogPins` is `0`. **[fact]**

**What moved:** the number only. This changes no plan — the design is
digital-only, and TTIHP26b carries `analog_total: 0`, so there are no
analog slots to buy on this run (B.1). It is corrected because a wrong
number in a costing section is a wrong number, and the tile price it sits
next to is quoted downstream.

**Corrected 2026-08-31 (b) — every cost line in this document was
tile-only and understated the order by EUR 115 to EUR 315.**

**Superseded text**, kept as it stood: "So: 4 tiles ~EUR 280, 8 tiles
~EUR 560, 32 tiles ~EUR 2,240, **plus a devkit/PCB order**" — the
parenthetical acknowledged the devkit but never priced it, and the
figures were then quoted onward as if they were totals, in B.6, in the
A.8 WP3 budget row and in the action items.

**Replacement — the full IHP order arithmetic** (same bundle, same date;
one devkit per order, which is the normal case):

| Line | Price | Note |
|---|---:|---|
| Tile | EUR 70 each | unchanged |
| Devkit PCB | EUR 300 | ASIC + carrier board + demo board |
| Devkit PCB, subsidised | **EUR 100** | one per order, requires the order to include tiles; **88 of 100 left on 2026-08-31** (B.1), first-come |
| Shipping | EUR 15 per PCB | not per tile |

So the real totals, devkit included: **4 tiles = EUR 395 subsidised /
EUR 595 not; 8 tiles = EUR 675 / EUR 875; 12 tiles = EUR 955 /
EUR 1,155; 32 tiles = EUR 2,355 / EUR 2,555.** **[fact — arithmetic over
the bundle's own price literals and its discount rule, which applies the
subsidy to exactly one PCB when the order contains tiles.]**

**What moved:** the tile prices are unchanged and were never wrong; what
was missing is the devkit and the shipping line, which are not optional
for a project that wants the fabricated part in hand. **The figure that
matters for this project is EUR 955** — the frozen 6x2 submission, twelve
tiles at EUR 70 plus the subsidised devkit plus shipping. It has been
quoted as EUR 840 repeatedly across this repository. WP3's EUR 3,500
envelope absorbs either figure, so no budget decision changes.

Resuming the tile-geometry notes:

- **Max tiles per design:** block templates exist up to **8x4 = 32
  tiles**; whether 32 tiles are purchasable on a given shuttle is
  shuttle-dependent **[confirm in the calculator/dashboard]**.
- **IO per design (TT mux):** fixed regardless of tile count —
  **8 dedicated inputs (`ui_in`), 8 dedicated outputs (`uo_out`),
  8 bidirectional (`uio`)**, plus clock and reset supplied by the TT
  infrastructure; ~50 MHz practical clock ceiling
  (https://tinytapeout.com/faq/). A SpaceWire link (DS-encoded, 2 pins
  per direction) fits comfortably in this budget alongside UART/SPI.

### B.3 Density: SG13G2 vs SKY130 (the "2x" hypothesis is wrong)

Measured from the PDK libraries, not marketing figures:

- `sg13g2_stdcell` (IHP-Open-PDK,
  https://github.com/IHP-GmbH/IHP-Open-PDK): CoreSite 0.48 x 3.78 um;
  `sg13g2_nand2_1` = 1.92 x 3.78 um = 7.26 um2, i.e. **raw density
  ~138 kGE/mm2**.
- `sky130_fd_sc_hd`: raw density **266 kGE/mm2** (SkyWater docs,
  https://skywater-pdk.readthedocs.io/en/main/contents/libraries/foundry-provided.html).

So SG13G2 standard cells are about **2x less dense per mm2 than SKY130
HD** — the opposite of the "roughly 2x SKY130" working assumption.
However, the IHP TT tile is 1.74x larger, so **per-tile logic capacity
is roughly 0.9x of a SKY130 tile** (raw ~4.3 kGE per IHP tile vs
~4.8 kGE per SKY130 tile; practical capacity at the ~70% utilization
demonstrated on our prior SKY130 TT submission is ~2.5-3 kGE per IHP
tile). Plan tile budgets with SKY130 intuition, then add ~10% margin.
What SG13G2 gives back: a faster process (competitive timing at
50 MHz+ with margin) and the European fab/radiation story below.

### B.4 Digital flow maturity and SRAM on SG13G2 (2026)

- **PDK:** IHP-Open-PDK is actively developed and released
  (https://ihp-open-pdk-docs.readthedocs.io/;
  https://www.ihp-microelectronics.com/services/research-and-prototyping-service/fast-design-enablement/open-source-pdk).

  **Corrected 2026-08-31 — there is no June 2026 release.**

  **Superseded text**, kept as it stood: "IHP-Open-PDK is actively
  developed and released (**June 2026 release** documented at
  https://ihp-open-pdk-docs.readthedocs.io/ ...)".

  **Replacement.** The repository has exactly **one** GitHub release and
  **three** tags in total: v0.1.0, v0.2.0 and **v0.3.0, dated
  2026-03-11** and named `Open-Silicon-MPW-March2026`. Nothing has been
  tagged between March 2026 and today. **[fact — tag list and dates read
  2026-08-31 from https://github.com/IHP-GmbH/IHP-Open-PDK/tags.]** The
  v0.3.0 release body is empty and `CHANGELOG.md` is stale at
  "[Unreleased] - 2024-10-14", so **no published breaking-change list for
  v0.3.0 exists** and a tree diff would be the only route to one.

  **What moved:** a release that did not exist becomes a real one three
  months earlier. The claim it was supporting — that the open PDK is
  actively developed — survives unchanged; only the evidence for it was
  wrong.

  **Do not move the pinned PDK to v0.3.0, and do not read the paragraph
  above as suggesting it.** This project pins IHP-Open-PDK commit
  **`c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c` (2026-01-16)**, which
  v0.3.0 does supersede upstream. The pin is nevertheless **correct and
  must not move**, because it is exactly the commit Tiny Tapeout's own CI
  resolves for this shuttle: `tt-gds-action@ttihp26b` installs
  `librelane==3.0.5`, whose `pdk_hashes.yaml` names that commit, and this
  repository's own sign-off run records the same one
  (`tt/runs/wave6-6x2/resolved.json`, `PDK_ROOT =
  ~/.ciel/ciel/ihp-sg13g2/versions/c4b8b4e5...`). **[fact, verified
  2026-08-31; `docs/37` section 3.]** What matters for a shuttle
  submission is matching the fab run's PDK, not matching the newest tag;
  a design hardened against a PDK the shuttle does not use is a design
  signed off against geometry that will not be fabricated. The pin
  changes when Tiny Tapeout's pin changes, and not before.

- IHP's own documentation describes the current content as an
  "experimental preview" / "alpha release" that "is not intended to be
  used for production at this moment", to be tagged with a production
  version when ready (https://ihp-open-pdk-docs.readthedocs.io/,
  re-checked 2026-08-25) — the same caveat docs/04 carries. **[fact]**
  The underlying SG13G2 process and the commercial PDK are
  production-proven; the caveat applies to the open design-kit views,
  not the silicon.
- **LibreLane:** the TT flow itself hardens IHP projects with LibreLane
  (https://github.com/TinyTapeout/ttihp-verilog-template), and IHP
  publishes its own LibreLane full-chip templates
  (https://github.com/IHP-GmbH/ihp-sg13cmos5l-librelane-template).
  OpenROAD-flow-scripts carries an `ihp-sg13g2` platform
  (https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/tree/master/flow/platforms/ihp-sg13g2).
  DRC/LVS is KLayout-based; Magic/Netgen integration is newer and still
  maturing (https://wiki.f-si.org/index.php?title=IHP_Open_PDK_integration_with_Magic,_Netgen,_and_LibreLane).
  Verdict: the digital flow is proven at TT scale (hundreds of shipped
  designs per IHP shuttle), while the open PDK itself remains
  pre-production per the caveat above.
- **SRAM:** IHP ships compiled macros (`RM_IHPSG13_*`, e.g.
  `RM_IHPSG13_1P_1024x32_c2_bm_bist`) in the open PDK. TT documents
  per-tile densities when instantiating them
  (https://tinytapeout.com/specs/memory/): 1024x8 single-port
  ~5,390 bits/tile; **1024x32 single-port ~8,820 bits/tile**; 1024x32
  dual-port ~4,680 bits/tile — and warns that "integrating the IHP SRAM
  macro at this stage is not trivial." OpenRAM support for SG13G2
  exists in the ecosystem but its production-readiness is unclear
  **[unverified]**; plan on RM_IHPSG13 macros. Fallback options: DFF
  RAM (~320 FF/tile) and latch RAM (~512 bits/tile demonstrated on
  SKY130; SG13G2 figures unpublished **[estimate]**).
- **Hard ceiling for the memory strategy:** even at 8,820 bits/tile, a
  32-tile design fully packed with SRAM holds only ~35 KB. The
  "hundreds of kB, ECC-protected" SoC memory target of the reference
  brief **cannot be met on Tiny Tapeout**; TT is the pilot vehicle, not
  the product vehicle.

### B.5 Radiation attractiveness of SG13G2

Honest summary — the data is encouraging but mostly from the SiGe
BiCMOS side of the process, not from `sg13g2_stdcell` digital logic:

- A 112 Gb/s radiation-hardened optical transceiver was designed in
  **SG13RH** — the rad-hard sibling PDK of SG13G2, not the open PDK —
  in IHP 130 nm SiGe BiCMOS
  (https://www.researchgate.net/publication/351632595_A_112_Gbs_Radiation-Hardened_Mid-Board_Optical_Transceiver_in_130-nm_SiGe_BiCMOS_for_Intra-Satellite_Links).
  The paper reports **no irradiation of the transceiver itself**; it
  cites prior characterization of the technology: SiGe HBTs evaluated
  to TID levels of **1.2 Mrad(Si)**, and the RH standard-cell library
  free of SEU and SEL up to **LET 62 MeV cm2/mg**. **[fact — SG13RH
  results; they transfer to SG13G2 only via the shared 130 nm CMOS
  backbone, per docs/04 section 1.2]**
- SiGe HBTs have well-documented intrinsic TID tolerance
  (https://www.researchgate.net/publication/260356025_Radiation_Effects_in_SiGe_Technology),
  and 130 nm CMOS nodes generically show usable TID behavior in HEP
  applications (https://www.sciencedirect.com/science/article/abs/pii/S0168900207015501).
- IHP has developed radiation-hardened 130 nm library work targeting
  ~200 krad with SEL-aware design rules **[secondary source, primary
  paper not located in this pass — find and cite before using in the
  application]**.
- SG13G2 is used for monolithic pixel detectors beam-tested at CERN,
  indicating an active rad-effects research community around the node.

Positioning consequence: consistent with the reference brief, bulk
130 nm CMOS logic gets **no platform SEL/TID guarantee** — hardening is
architectural (TMR, ECC, scrubbing), and the TT pilot chip is itself
the cheapest instrument to produce first TID/SEE data for
`sg13g2_stdcell`-based logic. That measurement campaign is exactly the
NLnet WP5 budget line, and it is a contribution the open community
currently lacks.

### B.6 What fits in N tiles — recommended tile budget

Capacity model: ~4.3 kGE raw / ~2.5-3 kGE practical per IHP tile
(B.3), SRAM per B.4.

The 2x2 default this section previously recommended has been overtaken
by measurement. `docs/15-pilot-tile-plan.md` section 4 hardened the
actual pilot RTL through the complete `Classic` flow: the design places
**136,107 um2** of standard cells, and the tile geometry is now read
out of `tt-support-tools` `tech/ihp-sg13g2/tile_sizes.yaml` and the DEF
templates rather than interpolated, giving **126,685 um2** of placement
rows in a 2x2 block and **259,837 um2** in a 4x2 **[fact, docs/15
sections 4.1 and 4.3]**. 2x2 would need 107.4 % utilization — not tight
but impossible — and 4x2 closed at 52.38 % with zero DRC, LVS, antenna
and timing violations. **The flip-flop-RAM pilot is a 4x2 = 8-tile
design; that is measured, not projected.**

| Option | Tiles | Cost | Content | Verdict |
|---|---|---|---|---|
| **Default pilot (TTIHP26b)** | **4x2 = 8** | **EUR 675** (560 tiles + 100 subsidised devkit + 15 shipping) | 8 LIF neurons x 8 axons with flip-flop 4-bit weights, AER event queues, serial host port, (72, 64) SECDED weight-word codec, TMR-voted configuration, fault counters and four fault pins (docs/15 section 1) | **Default.** No SRAM-macro dependency. Hardened end to end at this shape: 52.38 % utilization, 0 DRC, 0 LVS, 0 antenna, 0 timing violations on three corners **[fact, docs/15 section 5.3]** |
| Superseded: 2x2 = 4 minimal pilot | 2x2 = 4 | EUR 395 (280 + 100 + 15) | 16-32 LIF neuron crossbar (tt-um-lif-crossbar lineage), latch/FF-based 4-bit weights, event interface, TMR/EDAC demonstrator counters | **Not available.** Needs 107.4 % of the 2x2 placement rows for the content above; the synthesis netlist alone is 85.1 % of a 2x2 before a single repair buffer **[fact, docs/15 section 4.3]** |
| SRAM-macro variant (only if the 2026-09-07 go/no-go passes) | 3x4 or 6x2 = 12 | **EUR 955** (840 + 100 + 15) | The 8-tile content above with the flip-flop synapse file replaced by one `RM_IHPSG13_1P_512x32` (16 kbit) or `1P_512x16` (8 kbit) macro under an ECC read path plus a scrubber, and the fault counters restored to their full 32-bit register-map width | **12 tiles, not 8.** Macro plus halo reserves 92,280 um2 and the logic needs 194,439 um2 of rows at 70 %, i.e. 286,719 um2 against 4x2's 259,837 = 110.3 % **[fact for the areas, estimate for the halo and the utilization; docs/15 section 6]**. ~~Confirm the purchasable shape with Tiny Tapeout: the template's `info.yaml` comment lists no four-row shape while `tile_sizes.yaml` carries 3x4~~ **Closed 2026-08-31 for 6x2 — see the note below the table.** 3x4 remains unconfirmed and is not the shape this project uses |
| Full-SoC attempt | 8x4 = 32 | EUR 2,355 (2,240 + 100 + 15) | RV32 manager + multi-node SNN + SpaceWire codec + ~16 KB ECC SRAM (4x 1024x32 macros ~ 15 tiles, ~45 kGE logic left) | Marginal; TTIHP27a only on pre-silicon evidence — TTIHP26b silicon arrives after TTIHP27a closes (B.6.2) |
| Product MVP | — | — | Hundreds-of-kB SRAM class | Not possible on TT; needs a dedicated IHP MPW slot (price list: https://www.ihp-microelectronics.com/services/research-and-prototyping-service/mpw-prototyping-service/schedule-price-list), potentially FMD/university-subsidized **[investigate]** |

**Corrected 2026-08-31 (a) — the Cost column was tile-only.**
**Superseded figures**, kept as they stood: "~EUR 560 + devkit",
"~EUR 280 + devkit", "~EUR 840 + devkit", "~EUR 2,240". Each named the
tile line and left the devkit unpriced. The replacements in the table
above are full order totals with one subsidised devkit and its shipping,
per the B.2 correction. **What moved:** every row gained EUR 115, and the
12-tile line — which is the shape this project actually submits — moved
from **EUR 840 to EUR 955**. Without the subsidy it is EUR 1,155. WP3
carries either. **[fact]**

**Corrected 2026-08-31 (b) — "confirm the purchasable shape with Tiny
Tapeout" is CLOSED for 6x2. Do not re-open it.**

**Superseded action**, kept as it stood: the 12-tile row above and B.6.1
condition 2 both carried "confirm the purchasable shape with Tiny
Tapeout" as an open item, on the reasoning that "the template's
`info.yaml` comment lists no four-row shape while `tile_sizes.yaml`
carries 3x4".

**Replacement.** 6x2 is confirmed purchasable, buildable and flown, at
four independent levels, all read 2026-08-31 **[fact]**:

1. `tt-support-tools` `tech/ihp-sg13g2/tile_sizes.yaml` defines
   `6x2: "0 0 1289.28 313.74"`, and the upstream file is **byte-identical
   to the copy vendored in this repository** at
   `tt/tt/tech/ihp-sg13g2/tile_sizes.yaml`;
2. the shipped purchase calculator's shape-to-tile map contains
   `"6x2":12`
   (`https://app.tinytapeout.com/_build/assets/invoice-D5ozDQq9.js`);
3. the `ttihp-verilog-template` `info.yaml` comment now lists 6x2
   explicitly;
4. TTIHP26a — the immediately preceding IHP run — **shipped a 6x2
   project**.

**What moved:** an open question becomes a closed fact for the one shape
this project cares about. The 3x4 alternative in the same table row is
*not* covered by this and stays unconfirmed; it is not the shape the
design is frozen at (`docs/23`, `docs/31`), so nothing depends on it.

**Corrected 2026-08-31 (c) — the claim about the template comment is
narrowed, not withdrawn.** The superseded wording said the comment
"lists no four-row shape". The comment now reads `# Valid values: 1x1,
1x2, 2x2, 3x2, 4x2, 6x2 or 8x2` — so it **does** list 6x2, and the defect
is narrower than stated: it still omits 3x4, 4x4, 5x4, 6x4, 8x4 and every
single-row shape that `tile_sizes.yaml` defines, and TTIHP26a shipped two
8x4 projects, so the omission is real but does not touch this project.
Separately, the same comment states "A single tile is about 167x108 uM",
which is the **SKY130** tile; the IHP tile is 202.08 x 154.98 um (B.2).
Do not size an IHP design from that comment. **[fact]**

The macro named in the earlier revision of this table, "one RM_IHPSG13
1024x8 macro (~2 tiles)", is withdrawn on geometry rather than on area.
`RM_IHPSG13_1P_1024x8_c2_bm_bist` is **336.46 um** tall **[fact,
installed PDK LEF `SIZE`]** and every two-row Tiny Tapeout block on this
technology — 1x2 through 8x2 — is **313.74 um** tall **[fact,
`tt-support-tools` `tech/ihp-sg13g2/tile_sizes.yaml`]**. The macro is
taller than the block it was gated against, before any halo, PDN ring or
core margin. Every 1024-word part in the family shares that height.
The parts that fit a two-row block are the 191.34 um `1P_512x32` and
`1P_512x16` and the 118.78 um `1P_256x32` (docs/12 section 6.5).

**Note on which shape actually ships, because the EUR 955 above depends
on it.** The recommendation below is the 2026-08-25 one and is superseded
on shape by later measurement: the design outgrew the 70 % planning
criterion and the frozen submission is **6x2 = 12 tiles**
(`docs/23-tile-shape-decision.md`, `docs/31-signoff-6x2.md`,
`docs/34-pilot-freeze.md`, and ROADMAP). That is a shape change, not a
content change — it is still the flip-flop-RAM pilot with no
RM_IHPSG13 dependency, so B.6.1's macro gate is unaffected. Those
documents are the authority on the shape; this section is not.

**Recommendation (revised 2026-08-25, after the flow run): the TTIHP26b
submission is the 4x2 = 8-tile flip-flop-RAM pilot — 8 neurons x 8
axons with the SECDED and TMR demonstrators on the real datapath, no
RM_IHPSG13 dependency. The submission tree exists at that shape and
closes to a GDS locally (docs/15). The SRAM-macro variant is a 12-tile
design and is gated by B.6.1. The full-SoC integration is gated per
B.6.2.**

### B.6.1 Effort budget and go/no-go against the 2026-09-21 close

As of 2026-08-25 there are **27 days** to the TTIHP26b close. The
developer is solo and time-sliced across other projects; sustainable
capacity for this pilot is taken as ~2-3 h/day, i.e. **~55-80 h
total** to the deadline **[estimate]**. At HEAD the verified RTL base
is one block (`hw/rtl/aer_fifo.v` plus the generated `npu_regs.vh`);
everything below is new work.

Hour budget for the **default pilot** (all figures [estimate]; unit
costs consistent with docs/03 and docs/09 where they exist). The budget
is unchanged from the revision that assumed 2x2: the tile-count
correction in B.6 changes the shape the design is placed in, not the
work it takes to build it, and the flow iterations were budgeted
loosely enough to absorb a bigger block.

| Item | Hours |
|---|---|
| Port TT pipeline to `ttihp-verilog-template`, pin the PDK, swap liberty/STA scripts (B.7 deltas 1-4, 6) | 8-12 |
| LIF crossbar slice + FF 4-bit weight storage + event interface, adapted from the tt-um-lif-crossbar lineage | 15-25 |
| TMR/EDAC demonstrator counters + register hookup | 6-10 |
| Verification of the new slice against the golden model; existing formal/CI jobs kept green | 10-16 |
| sg13g2 harden iterations, precheck, submission and payment | 10-16 |
| **Total** | **49-79** |

The total fits the ~55-80 h capacity only if the low-to-mid estimates
hold; the upper bound consumes the entire capacity. The default scope
therefore has **no slack for the SRAM macro**. The **SRAM-macro
variant** adds on top of the above: `RM_IHPSG13_1P_512x32` (or
`1P_512x16`) + ECC-read-path and scrubber integration closed through
DRC/LVS in the local rootless flow (~25-50 h, given the open
LVS/GDS-merge issues that docs/04 calls "exactly the kind of issue that
costs weeks at tapeout time"), sequencer or SERV integration
(~10-20 h), UART host link (20-40 h per the docs/03 verdict table), and
a larger floorplan/timing pass (~8-16 h) — **~65-125 h additional
[estimate]**, i.e. out of reach of the remaining capacity unless the
macro work closes early. It also costs a further ~EUR 280, because the
macro variant is 12 tiles rather than 8 (B.6).

**Go/no-go date: 2026-09-07** (14 days before close). **The gate
decides macro content, not tile count.** 4x2 = 8 tiles is what the
flip-flop-RAM pilot needs anyway and is what the submission tree is
built at; the question the gate answers is whether the synapse file
inside those tiles is flip-flops or an SRAM macro — and, if it is a
macro, whether the shuttle order is raised to 12 tiles to hold it.

The SRAM-macro variant is taken only if, by that date, all three hold:

1. an `RM_IHPSG13_1P_512x32` or `1P_512x16` macro with its ECC read
   path passes DRC **and** LVS in the local rootless flow at the block
   shape it would actually ship in (`1024x8` is withdrawn: it is taller
   than any two-row block, B.6);
2. ~~a 12-tile shape is purchasable for TTIHP26b — confirm with Tiny
   Tapeout, since `tile_sizes.yaml` carries 3x4 and the template's own
   `info.yaml` comment lists only two-row shapes (docs/15 section 6);~~
   **Satisfied 2026-08-31, and permanently.** 6x2 = 12 tiles is
   purchasable, buildable and has flown on TTIHP26a; see the correction
   note under the B.6 table for the four sources. This condition can be
   marked met without further contact with Tiny Tapeout, and should not
   be re-raised at the gate;
3. the ~65-125 h above fits what is left of the capacity.

Otherwise the 8-tile flip-flop-RAM pilot is submitted as it stands and
the macro-integration learning moves to the TTIHP27a pre-silicon track
(B.6.2).

**Status as of 2026-08-25, ahead of the gate date:** condition 1 has
been tested and fails. `docs/12-sg13g2-flow-bringup.md` sections 7 and
8 hardened one `RM_IHPSG13_1P_512x32_c2_bm_bist` in a registered
wrapper — i.e. without the ECC read path, strictly easier than the gate
asks for — and it places, routes and closes timing, but does not sign
off: Magic DRC and KLayout DRC both report errors that are 100 % inside
the vendor macro geometry, and Netgen LVS fails on CDL-versus-GDS
hierarchy naming (IHP-Open-PDK issue #239) plus a bus-delimiter
mismatch. Both blocking causes are upstream of this repository. The
recommendation recorded there is **NO-GO for TTIHP26b**; the gate can
be closed early on that evidence.

### B.6.2 Second-run gating — corrected

The earlier framing "second run (TTIHP27a) after pilot results" does
not close against this document's own dates: TTIHP26b silicon is
expected 2027-06-25 (boards ~2027-08-16), roughly three months
**after** the extrapolated TTIHP27a close (~2027-03). No pilot silicon
result can exist before TTIHP27a closes. **[fact — dates per B.1]**
The gate is therefore redefined:

- **TTIHP27a (target, ~2027-03):** gated on **pre-silicon evidence**
  only — a clean sg13g2 harden of the enlarged design, RM_IHPSG13
  macro integration closed through DRC/LVS, and the formal/CI suite
  green on the pilot flow. Funding reality: with MoU start ~2027-02/04
  and disbursements following published milestones (A.7), a TTIHP27a
  tile purchase would be out-of-pocket, not grant-funded.
- **Silicon-results-gated run:** retargeted to **TTIHP27b (~autumn
  2027 [extrapolated, unannounced])** or an IHP MPW slot, chosen after
  TTIHP26b bring-up data exists (boards ~2027-08-16).

### B.7 Deltas from the proven SKY130 rootless flow

The existing assets — a rootless LibreLane flow on SKY130 and a shipped
TT submission pipeline — carry over almost entirely. Concrete deltas:

1. **PDK install:** IHP-Open-PDK instead of open_pdks/sky130A; TT's
   IHP template CI pulls the right PDK snapshot automatically; for
   local rootless hardening, mirror the container-free approach with the
   commit ~~release~~ that TT's own CI resolves
   (https://github.com/IHP-GmbH/IHP-Open-PDK). ~~**[verify pin against
   the ttihp template's `config`]**~~ **Closed 2026-08-31.** The pin is
   **`c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c` (2026-01-16)**, verified
   against `librelane==3.0.5`'s `pdk_hashes.yaml`, against
   `tt-gds-action@ttihp26b`, and against this repository's own
   `tt/runs/wave6-6x2/resolved.json`. **Install that commit, not a
   release tag, and do not update it.** v0.3.0 (2026-03-11) is newer
   upstream and is the wrong thing to install here: the object is parity
   with the fab run, and a local harden against a PDK the shuttle does
   not use signs off geometry that will not be fabricated. See B.4.
   **[fact]**
2. **Template:** `ttihp-verilog-template`
   (https://github.com/TinyTapeout/ttihp-verilog-template) instead of
   the SKY130 template; same `info.yaml` / `tt_um_` top-level / GitHub
   Actions structure.
3. **Cell library:** `sky130_fd_sc_hd` to `sg13g2_stdcell` (9-track,
   3.78 um row height, 1.2 V core). Re-baseline synthesis area and the
   STA scripts' library/corner names; fewer cell variants and drive
   strengths than SKY130 **[quantify during first harden]**.
4. **Density planning:** ~0.9x gates per tile vs SKY130 (B.3) — add
   ~10% area margin when porting SKY130-sized blocks.
5. **Memory:** OpenRAM/DFF-RAM habits replaced by RM_IHPSG13 macro
   instantiation with ECC wrapper; known-nontrivial integration
   (https://tinytapeout.com/specs/memory/) — budget schedule for it.
6. **Signoff:** KLayout-based DRC/LVS instead of Magic/Netgen; the
   precheck differs from the SKY130 precheck accordingly.
7. **Simulation:** unchanged (Icarus/cocotb testbenches port as-is;
   sg13g2 Verilog cell models ship in the PDK).
8. **Timing:** faster process; the 50 MHz TT envelope is comfortable —
   keep the same STA discipline, swap liberty files.

---

## Combined timeline

| Date | Event | Source |
|---|---|---|
| 2026-09-03 | NLnet calls reopen (Restack et al.) | https://nlnet.nl/propose/ |
| **2026-09-07** | **Pilot go/no-go on macro content: the 12-tile SRAM-macro variant only if an `RM_IHPSG13_1P_512x32`/`1P_512x16` with its ECC read path closes DRC/LVS in the local rootless flow and a 12-tile shape is purchasable; otherwise submit the 8-tile flip-flop-RAM pilot. Already answerable NO-GO on the docs/12 evidence** | B.6.1 |
| **2026-09-21, 20:00 UTC (23:00 Europe/Istanbul)** | **TTIHP26b closes (submit + pay before this instant, not before local midnight)** — the time of day was added 2026-08-31; this row previously carried the date alone | shuttle record, read 2026-08-31 (B.1) **[fact]** |
| 2026-10 | Draft Restack application review window; office-hour question slot | https://nlnet.nl/officehour/ |
| **2026-11-03 12:00 CEST** | **NLnet submission deadline** | https://nlnet.nl/propose/ |
| ~2027-03/06 | NLnet selection decision — ~~`~2027-01/02`, "observed 2-3 month lag"~~ **corrected 2026-08-31**: the 2-3 month lag came from pairing two announcements with the wrong call rounds; the observed lag is 4.3-7.0 months, with the two round-attributed points at 6.3 and 7.0 | A.7 **[estimate, from verified data points]** |
| ~2027-04/08 | MoU signed, funded work starts — ~~`~2027-02/04`~~ **corrected 2026-08-31**, derived from the row above plus the unchanged 1-2 month MoU negotiation | A.7 **[estimate]** |
| ~2027-03 | TTIHP27a expected close — pre-silicon-gated follow-up option (B.6.2); precedes TTIHP26b silicon | **[extrapolated, unannounced]** |
| 2027-06-25 | TTIHP26b chips expected (fab run IHP-2609) | https://app.tinytapeout.com/shuttles/ |
| 2027-08-16 | TTIHP26b boards delivered (estimate); bring-up + radiation pre-screening begins | https://app.tinytapeout.com/shuttles/ |
| ~2027-09/10 | TTIHP27b expected close — earliest silicon-results-gated run (B.6.2) | **[extrapolated, unannounced]** |

Note the favorable coupling: the TTIHP26b submission (September 2026)
becomes concrete, citable evidence of capability in the NLnet
application (November 2026), and the NLnet grant, if awarded
(~~early 2027~~ **corrected 2026-08-31: mid-2027, per the decision and
MoU rows above**), funds the bring-up, the radiation campaign, and the
silicon-results-gated follow-up run (TTIHP27b or an IHP MPW, per
B.6.2). A pre-silicon TTIHP27a entry (~2027-03) would precede first
disbursements and be out-of-pocket (A.7) — and the corrected decision
window makes that more certain, not less, since 2027-03 is now the
*earliest* end of the decision range rather than a month after it.

## Action items

1. **Decide TTIHP26b entry and freeze pilot-block scope** (4x2 = 8-tile
   flip-flop-RAM content per B.6, with the SRAM-macro variant gated per
   B.6.1) — developer. Immediately; the shuttle closes 2026-09-21.
   Buying 8 tiles rather than 4 raises the shuttle line from ~EUR 280
   to ~EUR 560, which WP3 already carries.
2. **Port the TT pipeline to `ttihp-verilog-template` and produce a
   first sg13g2 harden of the pilot block** (deltas 1-4, 6 of B.7) —
   engineering. **Done**: `tt/` is generated and the design closes to a
   GDS at 4x2 locally (docs/15 sections 5.3 and 8).
3. **Prototype RM_IHPSG13 integration with the ECC read path** against
   the 2026-09-07 go/no-go (B.6.1) — engineering. **Done, negative**:
   `RM_IHPSG13_1P_512x32_c2_bm_bist` places, routes and closes timing
   but fails Magic DRC, KLayout DRC and Netgen LVS on causes that are
   entirely inside the vendor views (docs/12 sections 7 and 8). The
   8-tile flip-flop-RAM pilot is what is submitted.
4. **Purchase tiles and submit on app.tinytapeout.com** before
   **2026-09-21 20:00 UTC / 23:00 Europe/Istanbul** — developer.
   **Corrected 2026-08-31:** this item previously read "before
   2026-09-21; re-confirm deadline, price, and max-tile policy in the
   dashboard". The deadline, the price table and the capacity were all
   re-confirmed on 2026-08-31 from primary sources and are recorded in
   B.1, B.2 and `docs/37`, so the re-confirmation is done rather than
   pending. What remains for the purchase act itself: the order is
   **EUR 955** for the frozen 6x2 — twelve tiles at EUR 70, plus the
   devkit at the subsidised EUR 100, plus EUR 15 shipping — and **the
   subsidy must be claimed with the order**, one per order, while 88 of
   the first 100 remain. It is worth EUR 200 and is first-come, with no
   deadline of its own beyond the shuttle close. **What moved:** an
   open re-verification became a closed fact, the total went from
   EUR 840 to EUR 955, and the deadline gained a time of day.
5. **Resolve the licensing/publication decision**: make the repo (or a
   public mirror of the NLnet-funded scope) public before the NLnet
   submission — developer. **Corrected 2026-08-29:** this item
   originally named "Apache-2.0 / CERN-OHL-S / CC-BY". The licence
   analysis has since been done and
   `docs/14-licensing-decision.md` section 9 recommends
   **CERN-OHL-W-2.0** for RTL and hardware sources, Apache-2.0 for
   software and CC-BY-4.0 for documentation; see A.6 above for why S is
   the wrong reciprocity strength for this block. The decision itself
   is still open — docs/14 section 10 is a recommendation awaiting
   sign-off, and that sign-off is what this action item is for.
6. ~~**Write the Restack application when the call opens 2026-09-03**
   (skeleton in A.8, live drafts in `docs/13`); attach the architecture
   outline and budget; submit at least a week before 2026-11-03 —
   developer, with engineering supplying the comparison matrix and
   work-package estimates. **On or just after 2026-09-03, re-read the
   Restack eligibility page, guide for applicants and FAQ** — they are
   published but self-labelled preliminary (A.3), and the application
   link still reads "Coming soon" as of 2026-08-31. This is the same
   re-verification `docs/13` tracks as [D-13] and it remains open.~~
   **THE RE-READ IS DONE, 2026-09-12, nine days late.** Section A.3
   carries what the three pages say now. The writing and the submission
   are still open and the deadline is **2026-11-03 12:00 CET**, which is
   earlier in the day than this item assumed.
7. **Scope the radiation pre-screening**: identify a Co-60 TID facility
   and obtain quotes to firm up WP5; locate and cite the primary
   IHP rad-hard 130 nm library paper (B.5 gap) — developer.
8. **Track the TTIHP27a and TTIHP27b announcements** and the IHP
   MPW/FMD subsidy options for the follow-up runs (gating per B.6.2) —
   developer.
