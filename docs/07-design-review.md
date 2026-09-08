# 07 — Independent design review: research phase close-out

Date: 25 August 2026
Status: review complete; findings open. This document closes the research
phase (documents 00-06) and reviews the first design wave (documents
08-11, `regmap/`, `sw/golden/`, `hw/`, `formal/`) as committed at
`83cbeea` ("Research phase and design wave 1"). Nothing is fixed in this
document; each finding carries a required disposition, and the numbered
action list in section 5 is input to `ROADMAP.md`.

Conventions, as in documents 01-06: statements about the reviewed text and
artifacts are verified facts (quoted or reproduced from the repository at
the reviewed commit, from the cited public sources, or from tool runs);
severity ratings and disposition scopes are engineering judgment. Where a
number was recomputed, the arithmetic is shown.

---

## 1. Scope and method

The review was run as an independent verification pass over the full
repository at commit `83cbeea`:

- all documents `docs/00` through `docs/06` and `docs/08` through
  `docs/11`, plus `README.md` and the generated `docs/regmap-npu.md`;
- the design artifacts: `sw/golden/` (golden model), `hw/rtl/aer_fifo.v`
  and `hw/rtl/npu_regs.vh`, `formal/aer_fifo_props.v` and the SymbiYosys
  jobs, `regmap/regmap.yaml` and its generator.

Candidate findings were collected across five dimensions: cross-document
consistency, source verification (re-reading the cited external sources),
plan realism (effort and calendar arithmetic), design-artifact audit
(executing the golden model, elaborating the RTL, re-running the checks),
and compliance/positioning (against the binding rules in `docs/05`).
Every candidate was then adversarially re-verified against primary
evidence, independently and more than once; a finding is reported in
section 2 only if at least two of three independent verification passes
upheld it. Candidates that failed re-verification are recorded in
section 3 with the reason, so they are not re-raised later.

Where the evidence is a tool run, it was reproduced locally in the
project's rootless toolchain (Icarus 12, the `sw/golden` venv); where it
is a source citation, the source was re-fetched and re-read. Line numbers
refer to the files at commit `83cbeea`.

Two findings raised independently on the same defect (the `README.md`
document index, flagged under both cross-document consistency and
compliance) are merged into a single finding (F-14).

---

## 2. Findings

Nineteen findings survived verification: 5 high, 8 medium, 6 low.

| # | Severity | File | One-line summary |
|---|---|---|---|
| F-1 | High | `docs/01` | 25 mm² envelope is sky130-derived but consumed downstream as PDK-independent; never re-baselined after the IHP decision |
| F-2 | High | `docs/02` | SRAM density anchor (1.5-3 mm²/Mb) contradicts the project's own macro data by 1.6-12x; Candidate B feasibility rests on it |
| F-3 | High | `docs/10` | MVP claims to sit "inside the envelope of docs/01 section 4" but exceeds every number in that envelope |
| F-4 | High | `docs/06` | B.5 misrepresents the cited 112 Gb/s transceiver paper on process, irradiation, and LET figures |
| F-5 | High | `docs/06` | Recommended 8-tile TTIHP26b pilot has zero effort quantification against a 27-day hard deadline |
| F-6 | Medium | `docs/01` | 4-node fabric vs single-core decision diverged silently between docs/01, docs/02, docs/10 |
| F-7 | Medium | `docs/09` | S1 (CVA6+seL4) rejection arithmetic computed on the fallback PDK, not the primary |
| F-8 | Medium | `docs/04` | Recommended positioning claim embeds >=100 krad figures, conflicting with docs/05 binding rule 3 |
| F-9 | Medium | `docs/04` | "SG13G2 circuits irradiated to 1.2-2 Mrad / SET 20-65.2" is supported by neither of its two citations |
| F-10 | Medium | `docs/04` | Section 2 attributes the no-SEL-to-65 result to SG13G2, contradicting the document's own section 1.2 attribution |
| F-11 | Medium | `docs/06` | docs/06 and docs/04 make contradictory PDK-maturity statements citing the same source |
| F-12 | Medium | `docs/06` | The "second run after pilot results" gate is impossible by the document's own dates |
| F-13 | Medium | `sw/golden/network.py` | Output tiling has an unstated 1024-neuron hard limit from the frozen 10-bit event ID; golden model models configurations the hardware cannot represent |
| F-14 | Low | `README.md` | Document index lists a nonexistent file, omits five committed ones; architecture table status column stale |
| F-15 | Low | `docs/04` | "256-512 KiB with roughly a third of the die in SRAM" fails the document's own density band at the upper end |
| F-16 | Low | `docs/03` | Phase-1 interface scope (UART count, CPI) mismatches docs/01 and docs/08 |
| F-17 | Low | `docs/09` | Formal budget framed as "comparable to one interface IP adaptation"; it is 1.3-2.7x the largest one |
| F-18 | Low | `hw/rtl/aer_fifo.v` | Stated DEPTH contract admits DEPTH=1, which fails elaboration |
| F-19 | Low | `hw/rtl/aer_fifo.v` | "Plain Verilog-2001" claim is false: `$clog2` is IEEE 1364-2005 |

### F-1 (high) — docs/01's physical envelope is sky130-specific and was never re-baselined after the IHP-primary decision

`docs/01-reference-decomposition.md:228`, dimension: cross-document
consistency.

The conclusion "a 25 mm²-class die on an open 130 nm PDK supports about
100-128 KB of SRAM" (line 228) is phrased as generic to any open 130 nm
PDK, but every input to it is SkyWater sky130: OpenRAM at ~57 kbit/mm²
(section 3.2) and sky130 HD logic density at 150-190 kGE/mm² placed
(sections 3.1/3.4). `docs/04` then selects IHP SG13G2 as primary, and the
envelope does not survive in either direction:

- SRAM: docs/04 section 3.1 puts SG13G2 foundry macros (`RM_IHPSG13_*`)
  at ~25-40 KiB/mm², from which docs/04's own table gives 256-512 KiB at
  25 mm² — 2-4x the docs/01 number.
- Logic: docs/06 B.3 measures SG13G2 at ~138 kGE/mm² raw, about 2x less
  dense than sky130 HD, so the 150-250 kGE budget needs ~1.5-3.0 mm²
  against docs/01's 1.5-2.5 mm² allocation.

docs/01 never mentions IHP or SG13G2 (zero occurrences), and its open
question 3 still frames PDK selection as "sky130 vs gf180mcu" — yet
docs/09 and docs/10 cite docs/01's numbers as current. No re-baselined
envelope exists anywhere at HEAD. This is the root cause behind F-2, F-3,
F-7 and F-15: every downstream physical-budget statement mixes numbers
from two PDKs without saying so.

Impact: any area, SRAM, or block-count decision that quotes docs/01 —
including the NPU sizing that docs/10 freezes — is quantitatively
unfounded on the chosen technology.

Required disposition: re-issue docs/01 sections 3.1, 3.4 and 4 as a
two-column budget (SG13G2 primary / sky130 fallback), sourcing the SG13G2
column from docs/04's macro band and docs/06 B.3's measured logic
density, and close docs/01 open question 3 with a pointer to docs/04.
Until that lands, `ROADMAP.md` must not inherit any numeric budget from
docs/01. The pending RM_IHPSG13 LEF re-baseline (docs/04 open question 2)
is the authority for the SRAM column.

### F-2 (high) — docs/02's SRAM density anchor contradicts the project's own macro data; Candidate B's feasibility claim rests on it

`docs/02-npu-architecture.md:225`, dimension: cross-document consistency.

Lines 224-226 anchor all candidate sizing on "compiled single-port SRAM
at this node class runs very roughly 1.5-3 mm² per Mb". The project's own
published data never gets near that figure: docs/01 section 3.2 gives
17.4 um²/bit (~17.4 mm²/Mbit) for open-PDK sky130 OpenRAM and ~3.6
mm²/Mbit for a commercial 130 nm compiler; docs/04 section 3.1's SG13G2
band (25-40 KiB/mm²) is 3.2-5.1 mm²/Mbit. The anchor is off by 1.6-12x
depending on the comparison.

Consequence, recomputed: Candidate B's physical row ("~156 KB SRAM ~ 2-4
mm² plus logic ... inside the SoC budget but only just", lines 310-312)
becomes ~22 mm² at docs/01's open-PDK density — infeasible on the PDK
docs/01 assumed — and 4-6.2 mm² at docs/04's IHP band, i.e. feasible but
materially tighter than stated. The document does note its anchors "must
be replaced with real macro data in `04-technology-and-flow.md`"
(line 227), but the replacement never happened and the recommendation was
consumed downstream (docs/10) with the optimistic anchor embedded.

Impact: the recommended architecture (Candidate B at 512 neurons) is out
of reach of OpenRAM-density sky130 and only viable on SG13G2 foundry
macros (or commercial sky130 SRAM); no document states this condition,
and the sky130 fallback ladder in docs/02 section 6 therefore understates
what falling back costs.

Required disposition: replace the anchor with the per-PDK density bands
from docs/01/docs/04, recompute the Candidate A/B/C physical rows, and
state explicitly that Candidate B at 512 neurons requires the SG13G2
foundry macros, with the 256-neuron half-size point as the sky130-
fallback configuration.

### F-3 (high) — docs/10's grounding claim is false: the MVP exceeds every number in the docs/01 envelope it cites

`docs/10-npu-mvp-spec.md:7`, dimension: cross-document consistency.

Lines 6-8 state the MVP is specified "inside the envelope of
`docs/01-reference-decomposition.md` section 4". docs/01 section 4
specifies: 4 neural processing nodes of 16 MACs each (64 MACs/clock
total), 64-96 KB fabric SRAM, resident weights near 30-60 KB, and models
beyond roughly 60-120k parameters at 4 bits streaming from QSPI. The
docs/10 defaults are one node, 512 neurons, 256k resident 4-bit synapses
= 128 KB of weight data and 144 KB physical SRAM (section 5) — 1.5-2.25x
the fabric-SRAM envelope, 2-4x the resident-weight bound, and 2-4x the
single-pass parameter bound. It also exceeds docs/01 section 3.4's
total-SoC SRAM figure for the 25 mm² open-PDK case (~115 KB) before the
CPU's 16-32 KB and the 32-64 KB system SRAM are added. The divergence is
acknowledged nowhere in either document.

Impact: the MVP spec's authority chain is broken at its first sentence;
a reader auditing the spec against its stated envelope must conclude
either the spec or the envelope is wrong, with no recorded resolution.

Required disposition: coupled to F-1. Either the re-baselined docs/01
SG13G2 column makes the 144 KB configuration fit (in which case docs/10's
sentence should cite the re-baselined section), or docs/10's grounding
sentence must state that it supersedes the docs/01 envelope, with the
SG13G2 macro-density justification cited. The current wording must not
survive to v0.2.

### F-4 (high) — docs/06 B.5 misrepresents the cited transceiver paper on three counts

`docs/06-funding-and-shuttle.md:327`, dimension: source verification.

The bullet states: "A 112 Gb/s radiation-hardened optical transceiver in
IHP 130 nm SiGe BiCMOS (SG13G2 family) survived X-ray TID to 1.2
Mrad(Si) and showed no SEL under heavy ions up to LET 65.2 MeV cm2/mg",
citing
https://www.researchgate.net/publication/351632595_A_112_Gbs_Radiation-Hardened_Mid-Board_Optical_Transceiver_in_130-nm_SiGe_BiCMOS_for_Intra-Satellite_Links.
Re-reading the source (Giannakopoulos et al., Frontiers in Physics 2021):

1. The ICs were designed in the IHP process **SG13RH** — the rad-hard
   sibling PDK — not "SG13G2 family".
2. The transceiver was never irradiated. The 1.2 Mrad figure is prior
   technology characterization quoted from a reference ("the chosen
   technology has already been evaluated for radiation hardness ... TID
   levels as high as 1.2 MRad"); there is no X-ray test and no
   "survived" result in the paper.
3. The SEL statement is prior RH-library characterization at LET 62, not
   65.2: "Up to the same LET value [62 MeV cm2/mg], all RH standard
   cells are free from single-event latch-ups." The string "65.2" and
   the word "X-ray" do not appear in the paper.

Impact: the bullet is presented as checked fact (document header: "All
web facts checked on 2026-08-24") and feeds the radiation-attractiveness
argument in funding material. Under the project's own facts-vs-estimates
and export-safe rules this is a load-bearing misattribution of SG13RH
RHBD results to the SG13G2 open PDK — precisely the attribution error
docs/04 section 1.2 warns against.

Required disposition: rewrite the bullet to match the source: transceiver
designed in SG13RH; the paper cites prior technology characterization
(SiGe HBTs to 1.2 Mrad(Si) TID; RH standard-cell library SEU/SEL-free up
to LET 62 MeV cm2/mg) and reports no irradiation of the transceiver
itself. Remove "SG13G2 family", "survived X-ray TID", and "65.2". This
must land before any of the B.5 text is reused in the NLnet application.

### F-5 (high) — the recommended 8-tile pilot has no effort quantification against a 27-day hard deadline

`docs/06-funding-and-shuttle.md:358`, dimension: plan realism.

The recommended TTIHP26b pilot (line 358) comprises one RM_IHPSG13
1024x8 macro as ECC-wrapped weight memory, a 32-neuron event-driven SNN
slice, a minimal sequencer or SERV-class RV32 control, and fault counters
plus a SpaceWire-lite/UART host link. At HEAD the only product RTL is
`hw/rtl/aer_fifo.v` (96 lines) plus the generated `npu_regs.vh`; no SNN
slice, ECC wrapper, SERV integration, UART, or sg13g2 harden exists.
TTIHP26b closes 2026-09-21 — 27 days from today — the developer is solo
and time-sliced across other projects, and no document attaches a single
hour figure to the pilot. The documents' own unit estimates for
comparable work already saturate a full-time month: UART adaptation 20-40
h and SpaceWire codec 80-115 h (docs/03 verdict table; "SpaceWire-lite"
is defined nowhere), first formal targets 22-44 h (docs/09 C.3), plus the
docs/06 B.7 template/PDK port deltas, precheck, and an SRAM-macro
integration that Tiny Tapeout itself warns "is not trivial" (quoted at
docs/06 line 310) and whose open LVS/GDS-merge issues docs/04 calls
"exactly the kind of issue that costs weeks at tapeout time" and names
the primary fallback trigger — still unreproduced locally. The SNN-slice
RTL itself is unquantified anywhere.

For completeness, the area claim was checked and holds: 8 IHP tiles = 8 x
202.08 x 154.98 um = 0.2506 mm², ~34.6 kGE raw at docs/06's own 138
kGE/mm² (~21-24 kGE at the stated ~70 % utilization);
`RM_IHPSG13_1P_1024x8_c2_bm_bist` exists in IHP-Open-PDK (49,419 um²,
matching the "~2 tiles" claim), and the remaining ~6 tiles plausibly hold
the time-multiplexed 32-neuron slice, SERV (2-5 kGE per docs/03), and
counters/UART. The defect is the schedule, not the area.

Impact: EUR 560 and the project's only 2026 silicon opportunity are
committed to a scope with no demonstrated path to the deadline; a late
slip would forfeit both the learning goal (SRAM-macro integration) and
the shuttle fee.

Required disposition: before committing the EUR 560, produce an
hour-budgeted work breakdown for the pilot against the 27 remaining days;
set an explicit mid-window go/no-go date (2026-09-07) conditioned on the
SRAM-macro integration closing DRC/LVS in the local rootless flow; and
promote the already-listed fallback (B.6 "Minimal pilot", 2x2 tiles with
latch-based weights, reusing the tt-um-lif-crossbar lineage) from
contingency to default, with the 8-tile macro pilot as the stretch goal.

### F-6 (medium) — the NPU sizing decision diverged silently across docs/01, docs/02 and docs/10

`docs/01-reference-decomposition.md:274`, dimension: cross-document
consistency.

docs/01's keep/shrink table (line 274) records the architecture decision
as "4 nodes x 1 engine, 64 MACs", and section 4 describes 4 neural
processing nodes on a lightweight packet interconnect, delegating only
the topology choice ("ring or 2x2 mesh — decision in
docs/02-npu-architecture.md") — not the node count. docs/02 section 4
then recommends Candidate B: one single time-multiplexed core, with the
mesh deferred to Candidate C "in a later phase, contingent on an
event-camera payload", without referencing docs/01's 4-node
recommendation. docs/10 freezes N_NEURONS = 512, single core. At HEAD the
two decision records contradict each other and no document acknowledges
the supersession.

Impact: decision-record integrity. Anyone auditing the architecture
lineage finds two active, conflicting decisions; the ROADMAP would
inherit the ambiguity.

Required disposition: add an errata note to docs/01 section 5 (or amend
the table row) recording that docs/02 superseded the 4-node fabric with a
single mesh-ready core, and why (verification burden, SRAM budget).

### F-7 (medium) — docs/09's S1 rejection arithmetic uses the fallback PDK after the primary decision

`docs/09-formal-verification-plan.md:377`, dimension: cross-document
consistency.

The S1 (CVA6 + seL4) rejection (lines 377-384) computes cache area with
"document 01 anchors of 150-190 kGE/mm² placed and open-PDK SRAM at ~57
kbit/mm²": 48 KB caches ~ 7-9 mm² "with OpenRAM-class macros (1.5-2 mm²
only if commercial 130 nm SRAM compiler access materializes)" and
"roughly half the total SRAM budget". On the chosen primary PDK this is
wrong in both directions: the SG13G2 open PDK ships foundry SRAM macros
(no commercial access needed) at ~25-40 KiB/mm² = 205-328 kbit/mm²,
putting the caches at ~1.3-2.1 mm², and 48 KB is 9-19 % — not half — of
docs/04's 256-512 KiB budget at 25 mm². Logic goes the other way: at
docs/06 B.3's 138 kGE/mm², "210 kGE logic = 1.1-1.4 mm²" becomes
~2.2-2.5 mm².

Impact: the S1 verdict itself likely survives (the MB-class seL4 RAM
requirement is the decisive argument and is PDK-independent), but the
stated area fractions justifying it are computed on the fallback PDK,
which weakens the decision record if challenged.

Required disposition: recompute the S1 area table for SG13G2 (primary)
using docs/04's macro band, keep the sky130 column as fallback, and let
the external-RAM/MB-class argument carry the rejection explicitly.

### F-8 (medium) — docs/04's recommended positioning claim conflicts with docs/05 binding rule 3

`docs/04-technology-and-flow.md:148`, dimension: cross-document
consistency / compliance.

docs/04 lines 147-151 recommend "the correct claim for this project" as:
'"implemented on a 130 nm process family with published TID/SEL
characterization (no SEL to 65 MeV·cm²/mg, standard-cell CMOS to ~110
krad(Si), 500 krad+ device-level)"'. docs/05 section 4 rule 3 — binding
for all public text — says: never claim, target, or advertise TID ratings
at or above 100 krad(Si), and public positioning stays strictly below
those thresholds "in wording as well as in fact"; rule 1 fixes the design
target statement at "LEO / 10-30 krad(Si) class". A recommended
datasheet-level claim sentence is positioning wording; quoting family-
level 110/500 krad figures inside it is exactly what rule 3 excludes,
platform attribution notwithstanding.

Impact: if the docs/04 sentence is copied into any public or funding
text, the project violates its own compliance rule set on first contact.

Required disposition: rewrite the recommended claim to cite the family
characterization without >=100 krad figures in the claim sentence itself
(e.g. "process family with published ESCC-track TID/SEL
characterization; device target LEO 10-30 krad(Si) class, fault-tolerant
by architecture"), leaving the numeric platform data in the sourced-facts
section only.

### F-9 (medium) — docs/04's "SG13G2 circuits irradiated" sentence is supported by neither of its citations

`docs/04-technology-and-flow.md:157`, dimension: source verification.

Lines 157-160 claim "third-party literature reports SG13G2 circuits
irradiated to 1.2-2 Mrad(Si) TID and heavy-ion SET testing at 20-65.2
MeV·cm²/mg on this technology", citing the transceiver paper
(https://www.researchgate.net/publication/351632595) and JICG transistor
work (https://www.sciencedirect.com/science/article/pii/S0168900220312298).
Citation 1 is explicitly SG13RH and irradiated no circuits (see F-4).
Citation 2 is transistor/test-structure work, not circuits: JI MOS
transistors verified against TID-induced leakage above 1.3 Mrad(Si), and
CMOS inverters with a SET/SEU LET threshold above 130 MeV cm²/mg — which
supports neither "1.2-2 Mrad circuits irradiated" nor the "20-65.2"
range. Neither source contains the 20-65.2 range at all. The "[fact that
these publications exist]" hedge covers existence, not the sentence's
substantive content.

Impact: same class as F-4 — an unsupported radiation claim in the
document that anchors the technology decision.

Required disposition: replace with source-accurate phrasing (transceiver
work in SG13RH citing HBT TID to 1.2 Mrad(Si); JICG structures in 130 nm
SiGe BiCMOS verified above 1.3 Mrad(Si), inverter SET LET threshold above
130 MeV·cm²/mg). Drop "SG13G2 circuits irradiated" and the 20-65.2
range, or cite a source that actually contains them.

### F-10 (medium) — docs/04 section 2 attributes the no-SEL-to-65 result to SG13G2, against its own section 1.2

`docs/04-technology-and-flow.md:214`, dimension: source verification.

Lines 213-215 argue: "SG13G2's published no-SEL-to-65 heavy-ion result
directly retires the scariest bulk-CMOS risk." The only cited source for
the no-SEL result (the AMICSA paper, Cirillo et al.) reports it for the
SGB25RH/SG13RH standard-cell test vehicles; SG13G2 does not appear in
that paper, and the document's own lines 143-147 say the published
numbers "characterize the family's 130 nm CMOS, not the open SG13G2 PDK
specifically". No SG13G2-specific published SEL result is cited anywhere
in the repository, so the sentence overclaims against its source and
contradicts the document's own attribution rule two pages earlier.

Impact: an internal inconsistency in the document's headline rationale
for the primary-PDK decision; easily quoted onward in the wrong form.

Required disposition: change to family-level attribution consistent with
section 1.2 ("the SG13 family's published no-SEL-to-65 result
(SG13RH/SG13S standard-cell test vehicles) ..."), noting the result
transfers to SG13G2 only via the shared 130 nm CMOS backbone.

### F-11 (medium) — contradictory PDK-maturity statements citing the same source

`docs/06-funding-and-shuttle.md:294`, dimension: cross-document
consistency.

docs/06 B.4: "IHP-Open-PDK is mature and actively released (June 2026
release documented at https://ihp-open-pdk-docs.readthedocs.io/ ...)".
docs/04 lines 110-112, tagged [fact]: "IHP's own documentation still
describes the open PDK as an early-access version not yet scheduled for
production purposes" — same source, same research window (checked
2026-08-24). One of the two characterizations is wrong, and the status
feeds the tapeout-gate fallback trigger in docs/04 section 2. The B.4
verdict ("production-grade for TT-scale designs") is the version quoted
in funding material.

Required disposition: verify the current wording on ihp-open-pdk-docs and
align both documents; if the early-access caveat stands, the docs/06 B.4
bullet must carry it.

### F-12 (medium) — the full-SoC second-run gate is impossible by the document's own dates

`docs/06-funding-and-shuttle.md:359`, dimension: plan realism.

The full-SoC row's verdict (line 359) and the B.6 recommendation
(lines 363-364) gate the 32-tile run on "a second run (TTIHP27a) after
pilot results". The same document's own timeline: TTIHP27a expected close
~2027-03; TTIHP26b chips 2027-06-25, boards 2027-08-16; B.1 notes the
~9-11 month fab-to-board lag. No pilot silicon result can exist before
TTIHP27a closes; the earliest results-gated second run is TTIHP27b
(~autumn 2027). The funding timeline compounds it: NLnet work start
~2027-02/04 with first disbursements only after first published
milestones (A.7), so a March 2027 tile purchase would be out-of-pocket,
not grant-funded as line 415 implies.

Required disposition: either redefine the full-SoC gate as pre-silicon
evidence (clean sg13g2 harden, macro integration closed, formal/CI green
from the pilot flow) if TTIHP27a is the target, or retarget the
results-gated second run to TTIHP27b or an IHP MPW, and update the
combined timeline and the WP3 wording accordingly.

### F-13 (medium) — golden-model output tiling has an unstated 1024-neuron hard limit from the frozen event word

`sw/golden/network.py:80`, dimension: design artifacts.

docs/10 freezes the event word at "[9:0] ID" (section 7.1) and
`PASS_TILE_OFF` at bits [9:0] (section 10), both under the section 8
freeze. Tiled output layers (equation E9) emit id TILE_OFF + j, so the
total layer width is hard-capped at 1024 neurons — but section 9's
limitation paragraph states only that the axon dimension is not
splittable, E9 claims equivalence to "a hypothetical single core wide
enough for the whole layer" unconditionally, and `NetworkRunner`
validates fan-in but bounds neither `layer.n_neurons` nor the tile base.
Reproduced: `NetworkRunner` with a 1536-wide layer at core_neurons=512
runs and returns max emitted id 1535, whose third tile base (1024) is
not programmable into PASS_TILE_OFF[9:0]. Additionally `LIFCore`
(`sw/golden/lif_core.py:115`) accepts a negative `tile_offset` and emits
negative ids no hardware can produce.

Impact: the golden model models configurations the frozen hardware
interface cannot represent, breaking the bit-exact-vs-RTL contract at
its edges — exactly the class of divergence the golden-model-first
discipline exists to prevent.

Required disposition: state the layer-width bound (<= 1024) in docs/10
section 9's limitation paragraph; validate in `NetworkRunner` (tile base
+ tile width <= 1024) and in `LIFCore` (0 <= tile_offset <= 1023,
tile_offset + n_neurons <= 1024) so the golden model refuses
configurations the frozen event word cannot carry. Must land before any
RTL is verified against the model.

### F-14 (low) — README document index is broken and stale at HEAD

`README.md:36`, dimensions: cross-document consistency and compliance
(raised independently under both; merged here).

Line 36 lists `docs/07-design-review.md`, which did not exist at HEAD
(this document resolves that entry), with no "pending" caveat of the
kind the Status section gives `ROADMAP.md`. The index ends at 07 and
omits the five committed design-wave documents (`docs/08` through
`docs/11`, `docs/regmap-npu.md`) and the regmap/hw/sw/formal trees. The
architecture table (lines 15-16) still says "selection in research
phase" / "sizing in research phase" although docs/03 recommends Ibex and
docs/10 freezes 512 neurons at v0.1.

Required disposition: update the Documents section to the actual file
set, mark `ROADMAP.md` pending, and refresh the status column of the
architecture table.

### F-15 (low) — docs/04's SRAM budget row contradicts its own density band

`docs/04-technology-and-flow.md:302`, dimension: cross-document
consistency.

The row "~25 mm² full-custom die | IHP MPW, 25 mm² | 256-512 KiB on
SG13G2 with roughly a third of the die in SRAM [estimate]" fails its own
section 3.1 band (~25-40 KiB/mm²): one third of 25 mm² (8.3 mm²) yields
208-333 KiB; 512 KiB requires 12.8-20.5 mm², i.e. 51-82 % of the die.
The [estimate] tag does not cover a contradiction with the document's
own figure two paragraphs earlier.

Required disposition: tighten the row to ~200-330 KiB at one third of
the die, or change the die-fraction wording for the 512 KiB endpoint.

### F-16 (low) — docs/03's phase-1 interface scope mismatches docs/01 and docs/08

`docs/03-cpu-and-ip-survey.md:346`, dimension: cross-document
consistency.

UART effort is costed "for three instances" (line 346) — GR801's count —
where docs/01 section 4 specifies 2x UART and docs/08 section 3.1
instantiates exactly APBUART0/APBUART1. CPI is "in scope, from-scratch"
(line 370) and counted in the 320-555 h phase-1 roll-up, while docs/01
marks the CPI front end optional and docs/08 defers the decision to the
NPU architecture work. Three documents disagree on what phase 1
contains, and the roll-up number is what the ROADMAP will inherit.

Required disposition: restate the docs/03 roll-up against the docs/01
scaled interface set (2x UART; CPI as an optional line item with its
40-80 h broken out) so the ROADMAP effort number inherits a consistent
scope.

### F-17 (low) — docs/09's formal-budget comparison understates the program's relative cost

`docs/09-formal-verification-plan.md:543`, dimension: plan realism.

C.3 frames the 155-310 h formal total as "comparable to one interface IP
adaptation (document 03 roll-up)". docs/03's largest phase-1 adaptation
is 80-115 h (SpaceWire codec); 155-310 h is 1.35-2.7x that, and the only
docs/03 figure in range (150-250 h clean-room CAN FD) is explicitly
excluded from phase 1. This is the sole place any document relates one
effort pool to another, so the mislabel propagates directly into the
ROADMAP's picture of relative cost.

Required disposition: correct the sentence to the accurate relation
(roughly two to three of the largest interface adaptations; 30-55 % of
the entire docs/03 phase-1 interface roll-up).

### F-18 (low) — `aer_fifo` DEPTH contract admits DEPTH=1, which fails elaboration

`hw/rtl/aer_fifo.v:74`, dimension: design artifacts.

The header (line 23) states "DEPTH must be a power of two", which admits
DEPTH=1. Then AW = $clog2(1) = 0 and the memory index part-selects
`wr_ptr[AW-1:0]` / `rd_ptr[AW-1:0]` degenerate to `[-1:0]`. Reproduced
under Icarus 12: "aer_fifo.v:74: error: part select wr_ptr[-1:0] is out
of order" (and the same at line 78; the zero-width replications in
`formal/aer_fifo_props.v` lines 60-61 break the same way). DEPTH >= 2 is
fine.

Required disposition: tighten the contract to "power of two, >= 2", or
guard the index width (e.g. AW = (DEPTH <= 2) ? 1 : $clog2(DEPTH) with
adjusted full/empty logic).

### F-19 (low) — "Plain Verilog-2001" claim is false: `$clog2` is IEEE 1364-2005

`hw/rtl/aer_fifo.v:24`, dimension: design artifacts.

Line 24 claims "Plain Verilog-2001, Icarus-clean" (repeated as
"Verilog-2001" in `docs/11-verification-harness.md` line 20), but
line 31 uses `$clog2`, introduced in IEEE 1364-2005 (clause 17.11.1).
Icarus and Yosys accept it, so all local gates pass, but the
language-compliance claim is wrong and will surface in any strict -2001
flow or a linter pinned to that standard.

Required disposition: change the claim to "Verilog-2005" in both files,
or replace `$clog2` with a 1364-2001-legal constant function and keep
the claim.

---

## 3. Reviewed and rejected

The following candidates were raised during the review and did not
survive adversarial re-verification. They are recorded so they are not
re-raised without new evidence.

- **R-1** — "The sky130 fallback's 4x-smaller NPU consequence is recorded
  nowhere": rejected — docs/02 records the 256-neuron half-size point as
  the explicit fallback configuration (lines 287, 311, and the section 6
  ladder "drop to Candidate B's 256-neuron/64k"); the consequence is
  documented, though F-2's disposition tightens its framing.
- **R-2** — "The 128-MACs-per-node / 1024-MACs-per-clock figure is not in
  the GR801 brief but is listed as a brief fact": rejected — the figure
  was found in the cited vendor material on re-verification; the docs/01
  section 2.2 sourcing stands.

  **AMENDED 2026-09-09, and the amendment is the more interesting half.**
  The rejection is correct and now names its artefact: the sentence is on
  <https://www.gaisler.com/products/gr801> verbatim, and
  `docs/ref-gr801-product-page.md` records the fetch date, the HTTP
  status and a SHA-256 of the bytes. It was cleared here on a
  re-verification that named nothing, which is a clearance a reader
  cannot check — and this corpus does not otherwise accept those.

  **But R-2 was a real defect wearing the wrong label, and rejecting the
  label dismissed the defect.** The finding said the figure was not in
  the brief; that is true. The rejection said the figure was in the
  cited material; that is also true. Both are true because `docs/01`
  section 2.2 put items from **two different documents** under one
  heading naming one of them and citing the other. The review answered
  the question the finding asked instead of asking why both answers could
  be right, and a defect that had been correctly spotted survived its own
  review for a year of documents. It is fixed at `docs/01` section 2.2,
  where the list is now split by source.
- **R-3** — "The EUR 27.5k NLnet ask and docs/04's EUR 20-65k MVP
  envelope are unreconciled": rejected — the two numbers cover different
  phases by design; docs/06 B.6 and docs/04 section 5 place the MVP die
  on a separately funded IHP MPW, and no document claims the grant buys
  the MVP die.
- **R-4** — "No document rolls up combined effort against the timeline":
  rejected as a defect at HEAD — the roll-up is the declared deliverable
  of `ROADMAP.md` at the end of the research phase (README Status); its
  absence is scheduled work, and the stale README listing is F-14. The
  obligation transfers to the ROADMAP (section 5, item 5).
- **R-5** — "Open-licensing resolution is anchored to the wrong deadline
  (NLnet 2026-11-03 instead of the TT close 2026-09-21)": rejected — the
  TT submission mechanism licenses the pilot's template repository at
  submission time independently of action item 5's whole-repository
  decision; the two deadlines govern different artifacts, and the pilot
  schedule risk is F-5.
- **R-6** — "The formal proof's 'reset-mid-traffic' claim is overstated
  because async2sync only samples rst_n at clock edges": rejected — the
  claim is accurate within the standard clocked formal model (`rst_n`
  free after the assumed initial reset state); no document claims
  coverage of sub-clock-edge asynchronous pulses, which is outside any
  SymbiYosys clocked proof.
- **R-7** — "No LICENSE file at HEAD contradicts the NLnet open-licensing
  commitment": rejected — the repository is private at HEAD and docs/06
  A.6 plus action item 5 record the licensing decision as an open, owned
  action with a deadline; a pending decision in a private research repo
  is not a documentation defect.

---

## 4. Verdict

The research phase's method is sound and most of its load-bearing
conclusions survive independent review: the GR801 decomposition and
keep/shrink logic, the Candidate B architecture choice, the IHP-primary /
sky130-fallback technology decision, the Ibex recommendation, the shape
of the formal program, and the golden-model-first design discipline all
stand. The facts-vs-estimates convention did its job — most findings were
locatable precisely because the documents show their sources and
arithmetic.

Three systemic weaknesses cut across the findings. First, the
quantitative physical baseline was never re-issued after the PDK
decision: docs/01's sky130-derived envelope is still cited as current by
every downstream document, and the documents silently mix sky130 and
SG13G2 numbers (F-1, F-2, F-3, F-7, F-15). Until the two-column
re-baseline lands, no area or SRAM number in this repository should be
quoted without naming its PDK. Second, radiation claims drift from their
sources in three places (F-4, F-9, F-10), and the recommended positioning
sentence violates the project's own binding claim rules (F-8) — for a
project whose differentiation is honest radiation positioning, these are
the most reputationally dangerous defects found. Third, the shuttle plan
contains calendar and effort arithmetic that does not close (F-5, F-12),
with a hard external deadline 27 days out.

Verdict: **the research phase is sound enough to base the ROADMAP on**,
conditional on the blocking items below being resolved before or at
ROADMAP issue. None of the findings overturns a phase-level decision;
they are baseline, claims-hygiene, and schedule corrections. The design
wave 1 artifacts (regmap flow, golden model, first RTL and proofs) are in
good shape; their findings (F-13, F-18, F-19) are contract tightenings,
not rework.

---

## 5. Actions feeding ROADMAP.md

### Blocking (resolve before or at ROADMAP issue)

1. **Re-baseline the physical budget** (F-1, F-3, F-15): re-issue
   docs/01 sections 3.1/3.4/4 as a two-column SG13G2/sky130 table from
   docs/04's macro band and docs/06 B.3's logic density; fix docs/10's
   grounding sentence against the result; correct the docs/04 line 302
   row. The ROADMAP must not inherit any docs/01 number until this
   lands.
2. **Recompute the NPU candidate physics** (F-2): replace the docs/02
   density anchor with per-PDK bands, recompute Candidate A/B/C rows,
   and state the SG13G2-macro condition on the 512-neuron configuration
   with the 256-neuron point as the sky130 fallback.
3. **Correct the radiation and PDK claims before any text is reused
   publicly** (F-4, F-8, F-9, F-10, F-11): fix the docs/06 B.5
   transceiver bullet, the docs/04 line 157 literature sentence, the
   docs/04 line 214 attribution, the docs/04 recommended claim wording
   per docs/05 rule 3, and align the PDK-maturity statements. Deadline:
   before the NLnet drafting window opens (calls reopen 2026-09-03).
4. **Fix the shuttle plan arithmetic** (F-5, F-12): hour-budgeted pilot
   work breakdown against 2026-09-21 with a 2026-09-07 go/no-go on
   SRAM-macro DRC/LVS closure; default to the 2x2 latch-RAM pilot with
   the 8-tile macro pilot as stretch; redefine the full-SoC second-run
   gate (pre-silicon evidence for TTIHP27a, or retarget to TTIHP27b/IHP
   MPW).
5. **Make the ROADMAP the roll-up**: restate the docs/03 phase-1
   interface scope (2x UART, CPI optional; F-16) and the docs/09 budget
   comparison (F-17), then roll up interfaces (320-555 h), formal
   (155-310 h), software, NPU RTL, and the pilot against the NLnet and
   shuttle clocks in one table — the roll-up no research document
   contains (R-4).
6. **Record the architecture supersession** (F-6): errata note in
   docs/01 section 5 that docs/02 superseded the 4-node fabric with a
   single mesh-ready core, with reasons.

### Non-blocking (track in the ROADMAP backlog)

7. **Recompute the docs/09 S1 area table on SG13G2** (F-7); the
   rejection verdict stands on the MB-class seL4 RAM argument.
8. **Enforce the tiling bound in the golden model** (F-13): docs/10
   section 9 limitation note plus `NetworkRunner`/`LIFCore` validation.
   Gate: must land before RTL is verified against the model.
9. **Tighten the `aer_fifo` contract** (F-18, F-19): DEPTH >= 2 (or
   guarded index width) and the Verilog-2005 claim correction in
   `hw/rtl/aer_fifo.v` and docs/11.
10. **Refresh the README** (F-14): document index to the actual file
    set, ROADMAP marked pending, architecture-table status column
    updated.
