# External fact re-check, 2026-08-31

Every external fact this project depends on was last read on 2026-08-25
or earlier. This document re-reads them from primary sources on
**2026-08-31**, 21 days before the TTIHP26b close.

Scope: TTIHP26b shuttle parameters, NLnet Restack call parameters, the
IHP open PDK production caveat, and time-sensitive changes in the pinned
toolchain. Every row cites the URL and the date read. This document does
not correct any other file; section 6 names what needs correcting and
where.

**Headline: the three things that decide what happens next — the
2026-09-21 close, the 2026-11-03 NLnet deadline, and the availability of
the 6x2 tile shape — all hold.** Four subsidiary facts moved; one of
them (the NLnet decision lag) is materially wrong in this repository.

A note on method. `app.tinytapeout.com` is a single-page application and
renders nothing to a plain fetch; the countdown on `tinytapeout.com`
serves a `44 DAYS 44 HOURS` placeholder until JavaScript runs. The
shuttle numbers below were therefore read from the application's own
public read-only API (`https://tinytapeout.supabase.co/rest/v1/shuttles`,
the endpoint and anonymous key that the shipped client bundle uses) and
cross-checked against `https://tinytapeout.com/chips/`, which is
server-rendered. Prices were read from the shipped calculator bundle
`https://app.tinytapeout.com/_build/assets/invoice-D5ozDQq9.js`, which
carries the price table as a literal. Both are primary in the sense that
matters: they are what the site itself computes from.

---

## 1. TTIHP26b

| Claim in this repository | Source, read 2026-08-31 | What it says today | Agrees? |
|---|---|---|---|
| Closes **2026-09-21** (docs/06 B.1, B.9 timeline) | `https://tinytapeout.supabase.co/rest/v1/shuttles?slug=eq.ttihp26b` | `"deadline":"2026-09-21T20:00:00+00:00"` | **Yes, with a refinement.** The close carries a time the repository does not record: **20:00 UTC**, i.e. **23:00 Europe/Istanbul on 2026-09-21**. Not midnight local. **[fact]** |
| Launched 2026-07-27 | same record | `"created_at":"2026-07-27T15:25:00+00:00"` | Yes **[fact]** |
| Fab run **IHP-2609** | `https://tinytapeout.com/chips/` | "TTIHP26b — Launched 2026-07-27, closes 2026-09-21, IHP-2609 fab run, status open" | Yes **[fact]** |
| Chips expected **2027-06-25** | `https://tinytapeout.com/chips/` | "expecting chips 2027-06-25" | Yes **[fact]** |
| Boards delivered **2027-08-16** | `https://tinytapeout.com/chips/` | "delivery ~2027-08-16" | Yes **[estimate, as TT labels it]** |
| **EUR 70 per tile** on IHP | `https://app.tinytapeout.com/_build/assets/invoice-D5ozDQq9.js` | IHP price object: `{pcb:300, pcbDiscount:100, tile:70, analogPin:200, analogPinDiscount:40, discountedAnalogPins:0, shipping:15, currency:"EUR", maxAnalogPins:16}` | Yes for the tile **[fact]**. Two adjacent numbers are wrong — see the two rows below. |
| Analog pins "EUR 40 each for the first two, EUR 100 thereafter" (docs/06 B.2) | same bundle | That is the **ChipFoundry/SKY130** table (`{analogPin:100, discountedAnalogPins:2, analogPinDiscount:40}`). The **IHP** table is **EUR 200 per pin with zero discounted allowance**. | **No — wrong table quoted.** Immaterial to this project (digital-only, and TTIHP26b carries `analog_total: 0`, so there are no analog slots on this run at all), but wrong as written. **[fact]** |
| "8 tiles ~EUR 560", "12 tiles ~EUR 840" (docs/06 B.2, B.6, WP3) | same bundle | Tile cost only. The **devkit PCB is EUR 300**, reduced to **EUR 100** for one subsidised PCB per order, plus **EUR 15 shipping per PCB**. | **Incomplete.** For the frozen 6x2 = 12 tiles: **EUR 955** with the subsidised devkit (840 + 100 + 15), **EUR 1,155** without. WP3's 3,500 envelope absorbs either. **[fact]** |
| **6x2 is an offered shape** (docs/06 B.6 leaves this as an open question; docs/23 and docs/31 freeze the design at 6x2) | four independent sources, all read 2026-08-31 | (a) `tt-support-tools` `tech/ihp-sg13g2/tile_sizes.yaml` via the GitHub contents API: `6x2: "0 0 1289.28 313.74"`, **byte-identical to the vendored copy** at `tt/tt/tech/ihp-sg13g2/tile_sizes.yaml`; (b) the calculator's shape-to-tile map includes `"6x2":12`; (c) the template comment now lists 6x2 (next row); (d) TTIHP26a actually **shipped one 6x2 project** (`ttihp26a` shuttle index) | **Yes — and this closes the open question.** docs/06 B.6 action item "confirm the purchasable shape with Tiny Tapeout" is answered: 6x2 is purchasable, buildable and has flown on the immediately preceding IHP run. **[fact]** |
| The template's `info.yaml` comment omits shapes the shuttle ships (docs/06 B.6, docs/23) | `TinyTapeout/ttihp-verilog-template` `info.yaml` via the GitHub contents API | Comment reads: `# Valid values: 1x1, 1x2, 2x2, 3x2, 4x2, 6x2 or 8x2` | **Still true, but narrowed in our favour.** The comment **does** list 6x2. It still omits 3x4, 4x4, 5x4, 6x4, 8x4 and every single-row shape that `tile_sizes.yaml` defines — and TTIHP26a shipped two 8x4 projects, so the omission is still a real defect, just not one that touches our shape. Separately, the same comment says "A single tile is about 167x108 uM", which is the **SKY130** tile; the IHP tile is 202.08 x 154.98 um. **[fact]** |
| Shuttle capacity is not a risk | shuttle record | `tiles_total: 240`, `tiles_used: 50` — **190 tiles free** | Yes. A 12-tile buy is not at risk of a sell-out. **[fact]** |
| Subsidised PCBs | shuttle record | `subsidized_pcbs_total: 100`, `subsidized_pcbs_sold: 12` — **88 remaining** | Not previously recorded. Worth EUR 200 on the devkit line, first-come. **[fact]** |
| TTIHP27a expected ~2027-03 (docs/06 B.6.2, tagged as an extrapolation) | `https://tinytapeout.com/chips/` | Future runs listed are **TTGF26c** (submission Q4 2026) and **TTSKY26d** (deadline December 2026, delivery June 2027). **No IHP run after 26b is announced.** | The extrapolation is still unsupported, and correctly tagged as such in docs/06. No action beyond continuing to treat the pre-silicon follow-up slot as speculative. **[fact that it is unannounced]** |
| Pinned TT tooling has not drifted | GitHub API, read 2026-08-31 | `tt-support-tools` `main` HEAD is **`01d5d2814fa9`, 2026-08-20** — exactly the commit `scripts/gen_tt_submission.py` pins as `SUPPORT_TOOLS_COMMIT`. `tt-gds-action` tag `ttihp26b` resolves to `651ea05e19e8`, 2026-07-30, and `main` has nothing newer. | **Yes, no drift.** The generated `tt/info.yaml` is against current upstream. **[fact]** |

### 1.1 Submission procedure and precheck

No change found. `tt/.github/workflows/gds.yaml` pins every job to
`TinyTapeout/tt-gds-action/...@ttihp26b`, and that tag has not moved
since 2026-07-30 (GitHub API, read 2026-08-31). The precheck steps
invoked by the tag are the same ones docs/19 section 5 already
enumerates. No new precheck requirement was introduced for this shuttle.
**[fact]**

---

## 2. NLnet Restack

The live form was read as raw HTML, so the `maxlength` attributes below
are read off the DOM rather than a markdown conversion — the same method
that caught the 1,200-versus-1,500 error on 2026-08-29.

| Claim in this repository | Source, read 2026-08-31 | What it says today | Agrees? |
|---|---|---|---|
| Calls reopen **2026-09-03** | `https://nlnet.nl/propose/` | "New calls for several funds will open up September 3rd 2026 with a deadline of November 3rd 2026 12:00 CEST (noon)." | Yes **[fact]** |
| Deadline **2026-11-03 12:00 CEST** | same, and `https://nlnet.nl/news/2026/20260803-phaseshift.html` | verbatim as above | Yes **[fact]** |
| **EUR 5,000-50,000** | `https://nlnet.nl/restack/`, `https://nlnet.nl/restack/faq/`, and the live form's amount placeholder `(between 5000 and 50000)` | "We are seeking project proposals between 5.000 and 50.000 €" | Yes, three independent places **[fact]** |
| **Individuals eligible** | `https://nlnet.nl/restack/faq/` | "Do I need to have a legal entity like a company to apply? No, you don't. You can apply as an individual... It is not an issue if you have not yet established the entity when you apply." | Yes **[fact]** |
| **Türkiye in the priority group** as a Horizon Europe associated country | `https://nlnet.nl/restack/eligibility/`; `https://research-and-innovation.ec.europa.eu/strategy/strategy-research-and-innovation/europe-world/international-cooperation/association-horizon-europe_en` | Eligibility page: "Given equal proposals, inhabitants of the EU and countries associated to Horizon Europe are given priority." The Commission's live list of 22 associated countries includes **Türkiye**, with no withdrawal or suspension noted. | Yes **[fact]**. Caveat: the Commission pages carry no revision stamp, so this is "on the current live list", not "confirmed unchanged on a dated revision". Note also that the Restack FAQ makes "European dimension" a separate **knock-out criterion**, not a tiebreak — docs/06 A.3 already frames this correctly. |
| Fund is **EUR 7m** and **fully allocated expected early 2027** | `https://nlnet.nl/restack/`, `https://nlnet.nl/restack/guideforapplicants/` | "The Restack Consortium will competitively award 7 million euro worth of grants... new calls will be announced until the budget of the programme has been fully allocated (expected early 2027)." | Yes **[fact]**. This remains the strongest argument for submitting into the November round rather than a later one. |
| **Decision lag 3-5 months** | `https://nlnet.nl/restack/faq/` for the claim; `https://nlnet.nl/news/` for the observations | NLnet still states "between three and five months... counted from the date of the deadline". But the 2026 announcements, each traced to the call round it names, run **6-7 months**: the **2026-03-02** announcement decides the **August 2025** call (verified: "This is the selection for the August call of the NGI Zero Commons Fund fund only") = **7.0 months**; the **2026-04-09** announcement decides the **October 2025** call (verified: "for the October call", application numbers `2025-10-`) = **6.3 months**. Later 2026 items fall in the 4.3-6.5 range. | **NLnet's stated figure is confirmed as NLnet's claim. The repository's derived window is wrong.** See section 6. **[fact for the two verified data points; estimate for the projection]** |
| Form fields and limits **unchanged since 2026-08-25** | raw HTML of `https://nlnet.nl/propose/` | The 23-row field table in **docs/13 section 1.2 matches the live form field for field**, including `abstract` at **hard `maxlength="1500"` with placeholder "(You have 1200 characters)"**, and exactly five required controls: `call`, `email`, `abstract`, `used_ai`, `consent`. | **Yes — docs/13 is current and correct.** No field added, removed or re-limited. **[fact]** |
| **Generative-AI disclosure** requirement | the live form; `https://nlnet.nl/foundation/policies/generativeAI/` | Required select `used_ai` with two options, plus the `ai_prompt` provenance textarea and three file slots. Policy is **version 1.1**, "came into force on: December 8, 2025", "valid as of: January 26, 2026". | **Has not moved.** Still mandatory, still requires a prompt provenance log (model, dates, verbatim prompts, unedited output). docs/13 sections 1.5(b) and 3.12 and decision items D-10/D-18 already carry this correctly. **[fact]** |
| **Open-licensing terms** | `https://nlnet.nl/commonsfund/guideforapplicants/` and `https://nlnet.nl/restack/guideforapplicants/` | Identical sentence in both: "All scientific outcomes must be published as open access, and any software and hardware must be published under a recognised open source license in its entirety." | **Has not moved.** The private-repo tension in docs/06 A.6 stands exactly as stated. **[fact]** |
| "Restack-specific rules are **not yet published**" (docs/06 A.3) | `https://nlnet.nl/restack/eligibility/`, `/guideforapplicants/`, `/faq/` | All three now exist, plus the main page. The Commons Fund is no longer needed as a proxy. | **No — this has changed.** docs/13 already cites the Restack pages directly; docs/06 A.3 has not caught up. Note the Restack landing page still says "This fund is currently being set up... **preliminary** guide for applicants", so the pages may change again at the 2026-09-03 opening. **[fact]** |
| Anything new since 2026-08-25 | `https://nlnet.nl/news/` | Latest item of any kind is **2026-08-17**. **Nothing posted between 2026-08-25 and today.** | No changed deadline, no new procedure in the window. **[fact]** |

---

## 3. The IHP open PDK

| Claim in this repository | Source, read 2026-08-31 | What it says today | Agrees? |
|---|---|---|---|
| Open PDK is an "experimental preview" / "alpha release" that "is not intended to be used for production at this moment", to be tagged with a production version when ready (docs/06 B.4, docs/04) | `https://ihp-open-pdk-docs.readthedocs.io/en/latest/` | Verbatim, unchanged: "IHP Open Source PDK are currently treating the current content as an experimental preview / alpha release." ... "the open source PDK is not intended to be used for production at this moment." ... "The PDK will be tagged with a production version when ready to do production design." Status banner still renders **Experimental Preview**. | **Yes — the caveat stands in full.** **[fact]** |
| same, as stated in the repo README | `IHP-GmbH/IHP-Open-PDK` `README.md` via the GitHub contents API | "# Current status -- Preview ... the open source PDK is not intended to be used for production at this moment." | **Yes, with a wording drift.** The README has dropped the phrases "experimental preview / alpha release" (now "preview only") and dropped the future-production-tag sentence. The load-bearing sentence is identical in both. The docs site retains everything, so quoting the docs site remains safe. **[fact]** |
| "June 2026 release documented at ihp-open-pdk-docs.readthedocs.io" (docs/06 B.4) | `https://api.github.com/repos/IHP-GmbH/IHP-Open-PDK/releases` and `/tags` | **There is no June 2026 release.** The repository has exactly **one** GitHub release and **three** tags in total: v0.1.0 (2024-05-28), v0.2.0 (2024-11-11), **v0.3.0 (2026-03-11, named `Open-Silicon-MPW-March2026`)**. Nothing between March 2026 and today. | **No — this is wrong.** The newest release is v0.3.0 of 2026-03-11. **[fact]** |
| Has the version this project pins been superseded? | `librelane` 3.0.5 `librelane/pdk_hashes.yaml`; `TinyTapeout/tt-gds-action` tag `ttihp26b` `precheck/action.yml`; `tt/runs/wave6-6x2/resolved.json` | This project pins IHP-Open-PDK commit **`c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c`** (2026-01-16). That commit **predates v0.3.0**, so yes, it has been superseded upstream. **But it is exactly the commit Tiny Tapeout's own CI resolves for this shuttle**, via `tt-gds-action@ttihp26b` → `librelane==3.0.5` → `pdk_hashes.yaml`. | **Superseded upstream, correctly pinned locally.** Matching the shuttle is what matters, not matching the newest tag. **Do not move to v0.3.0.** Verified against the actual sign-off run: `tt/runs/wave6-6x2/resolved.json` records `PDK_ROOT = ~/.ciel/ciel/ihp-sg13g2/versions/c4b8b4e5...`. **[fact]** |
| — (not previously recorded) | release body; `CHANGELOG.md` | The v0.3.0 release body is **empty** and `CHANGELOG.md` is stale at "[Unreleased] - 2024-10-14". | There is **no published breaking-change list** for v0.3.0. If a future workstream ever considers moving the pin, a tree diff is the only route. **[fact]** |

---

## 4. Toolchain, checked for deprecations

| Item | Source, read 2026-08-31 | Status | Action |
|---|---|---|---|
| `volare` → `ciel` | `github.com/efabless/volare` now redirects to `chipfoundry/volare`; its README reads "Volare development has moved to the FOSSi Foundation: Check out Ciel... This repository is preserved as-is for archival purposes." | Deprecated in favour of `fossi-foundation/ciel`. Note neither repo carries GitHub's `archived: true` flag, so automated checks will not catch this. | **None.** This project already uses ciel — `resolved.json` resolves `PDK_ROOT` under `~/.ciel/`. **[fact]** |
| OpenLane 2 → LibreLane | `efabless/openlane2` redirects to `chipfoundry/openlane2`, last pushed 2025-12-02, README points at `github.com/librelane/librelane` | Superseded. TT's IHP flow is LibreLane at three levels (`tt-gds-action` installs `librelane==3.0.5`; `tt-support-tools/project.py` shells out to `python -m librelane` and stamps `"FLOW_NAME": "LibreLane"`). | **None.** This project is already on LibreLane. **[fact]** |
| LibreLane version | `librelane/librelane` releases | Latest is **3.0.11 (2026-08-24)**; this project and TT CI both use **3.0.5**. | **None — deliberately.** `tt-gds-action@ttihp26b` defaults to 3.0.5. Upgrading would break parity with the shuttle. docs/19 section 5 already records the 3.0.5-versus-dev-container-3.0.0.dev44 delta and correctly notes the PDK commit is identical; that record is confirmed. **[fact]** |
| oss-cad-suite / yosys pin | `tools.mk` | Pins `oss-cad-suite-linux-x64-20260804`, yosys `0.67+146`, with a warning-not-failure version check. | No external change found that bears on this. Not re-verified against upstream releases; out of scope for this check. |

---

## 5. Requires a decision or an action

1. **TTIHP26b closes 2026-09-21 at 20:00 UTC — 23:00 Europe/Istanbul —
   not at local midnight.** 21 days from today. Submission *and payment*
   must be complete before that instant. The repository records the date
   without the time; anyone planning to submit on the final day is
   working with three hours less than the date alone implies.
   **Deadline: 2026-09-21 20:00 UTC.**

2. **Claim a subsidised devkit PCB with the tile order.** 88 of 100 are
   left as of today. It is EUR 100 instead of EUR 300, one per order,
   and it requires the order to include tiles. There is no separate
   deadline, but it is first-come and the shuttle has three weeks to
   run. Total for the frozen 6x2: **EUR 955** with the subsidy.
   **Deadline: at purchase, effectively 2026-09-21.**

3. **Replan the NLnet decision window from 2027-02/04 to 2027-03/06.**
   Two verified 2026 announcements show 6.3 and 7.0 months from deadline
   to selection, against NLnet's advertised 3-5. This does not change
   whether to apply — it changes what can be promised about when work
   starts, and it pushes the expected decision closer to the "budget
   fully allocated (expected early 2027)" horizon, which strengthens
   rather than weakens the case for the November round.
   **No deadline; affects docs/13 section 4 scheduling.**

4. **Re-read the Restack pages on or just after 2026-09-03.** They are
   published but self-labelled "preliminary", and the application link
   still reads "Coming soon". docs/06 A.5 already carries this as a
   re-verify item; it remains open. **Deadline: 2026-09-03.**

Nothing found in this check requires a change to the design, the flow,
the pinned PDK, or the pinned toolchain.

---

## 6. Documents that now need correcting

Another workstream owns these files; nothing here was edited.

| Document | Location | What is wrong | What it should say |
|---|---|---|---|
| **docs/06** | A.7, "Timeline: submission to decision to MoU" | "roughly **2-3 months** from deadline to selection announcement" — the two 2026 announcements were each paired with the wrong call round. The 2026-03-02 item decides the **August 2025** call, not December 2025; the 2026-04-09 item decides the **October 2025** call, not February 2026. | Observed lag is **6-7 months**. Decision on a 2026-11-03 submission: **2027-03 to 2027-06**. NLnet's own advertised 3-5 months should be quoted as NLnet's claim, not as the observed rate. |
| **docs/06** | B.9 timeline row `~2027-01/02` | Derived from the same error | `~2027-03/06` |
| **docs/06** | A.3, "Restack-specific rules are not yet published" | No longer true | Cite `https://nlnet.nl/restack/eligibility/`, `/guideforapplicants/`, `/faq/` directly, and note they are self-labelled preliminary until 2026-09-03 |
| **docs/06** | B.2, analog pin pricing | Quotes the ChipFoundry/SKY130 table | IHP is **EUR 200 per analog pin, no discounted allowance**; and TTIHP26b has `analog_total: 0`, so there are no analog slots on this run |
| **docs/06** | B.2 and B.6 cost lines, and the WP3 budget row | Tile cost only | Add **devkit EUR 300 / EUR 100 subsidised** and **EUR 15 shipping per PCB**. 6x2 = **EUR 955** subsidised, **EUR 1,155** not |
| **docs/06** | B.4, "June 2026 release" | No such release exists | Newest IHP-Open-PDK release is **v0.3.0, 2026-03-11**; only one release and three tags exist in total. The production caveat is unchanged and still applies |
| **docs/06** | B.6 table row for the 12-tile variant, and B.9 action item 3 | Carries "confirm the purchasable shape with Tiny Tapeout" as open | **Closed.** 6x2 is in `tile_sizes.yaml`, in the calculator's shape map, in the template comment, and shipped on TTIHP26a |
| **docs/06** | B.1 and the B.9 timeline row for 2026-09-21 | Date without time | Add **20:00 UTC / 23:00 Europe/Istanbul** |
| **docs/06** | B.6 note that the template comment "lists no four-row shape" | Still true for 3x4 and the other four-row shapes, but the comment **does** now list 6x2 | Narrow the claim to the four-row shapes and the single-row shapes; note the comment also misstates the tile size as the SKY130 167x108 um |
| **docs/13** | Section 1.5 item 4, and the timeline row `2027-02 to 2027-04` | The quotation of NLnet's 3-5 months is accurate and should stay; the **derived window** is optimistic | Keep the quote tagged `[fact]`, retag the derived window as `[estimate]` and widen it to **2027-03 to 2027-06**, citing the two verified announcements |

**docs/13 section 1.2 needs no correction.** Its 23-row field table was
re-read against the raw form today and matches field for field,
including the abstract's advisory 1,200 against hard `maxlength` 1,500
and the five required controls. The correction made on 2026-08-29 holds.

**docs/19 section 5 needs no correction.** Its record of the LibreLane
3.0.5 versus dev-container 3.0.0.dev44 delta, and its statement that the
PDK commit is identical across the two, were both verified today against
`librelane` `pdk_hashes.yaml` and against this repository's own
`tt/runs/wave6-6x2/resolved.json`.

**docs/04's PDK caveat needs no correction.** The "early access version
not intended for production" language is unchanged at every source.
