# 64 — Reconciling seven numbers the corpus stated two ways

`docs/60-soc-datasheet.md` section 14 is a list of seven places where
this repository disagrees with itself about a figure, found because
writing a datasheet is the first thing that forced every number to be
read against every other. It recorded them and, by the precedent of
`docs/21-pilot-datasheet.md` section 10, did not correct them. This
document is the correction: each of the seven is resolved to one
traceable value, the losing statements are corrected in place in the
document that owns them, and the correction is left visible.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash. Nothing in `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or
`hw/openlane/` was modified, nothing was re-synthesised, placed or
simulated, and no campaign was re-run. Every number below is read out of
a committed file, out of `git log -p` on one, or out of a document that
names its source. Section 6 lists every file edited.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| How many of the seven were a document transcribing a number wrongly? | **None.** Every disagreement is two correct statements about two different inputs — an earlier run, a different source list, a different content, a different estimator — quoted without saying so. Section 3 |
| Which value wins for the campaign? | **378 injections, 6 SDC, 1.6 %**, the log at blob `312d3c76` that the freeze commit `b6738e5` pins **[fact]**. `docs/16` and `docs/21` quoted real earlier logs (`2c6c052` and `0448282`) and now say so. Section 3.1 |
| Was any number overwritten? | **No.** Every corrected statement is struck through or followed by a dated "corrected … because" sentence, by the rule `docs/15-pilot-tile-plan.md` section 4.2 and `docs/38-ibex-bringup.md` section 10 set. Section 2 |
| Which items were already resolved before this pass? | **One.** The duplicated index row was removed in the commit that added `docs/60` itself, `62f1aff`, so that item was stale as committed **[fact]**. Section 3.7 |
| Which items were superseded but never amended? | **The five "no power number" lines.** `docs/53` found the file and `docs/57` measured the power; neither touched the five documents that say it does not exist. All five are now amended. Section 3.4 |
| Where is the record kept? | Here, with an index row, rather than as a column in `docs/60` section 14 — that section is a datasheet's list of findings and stays as written; it now carries a one-line *Resolved* pointer under each item. Section 2 |

---

## 2. Method, and where the record lives

**How a correction is made.** The original sentence stays where it was.
It is struck through with `~~ ~~` where a short phrase is wrong, or left
whole and followed by a dated note where the sentence was true of the
input it described. The note says what the value is now, why the old
one was written, and names the file that settles it. That is the form
`docs/15` used to retract its 4x2 verdict and `docs/38` used to close
its open decision, and `docs/21` section 6.2 used to replace its own
255-injection headline; nothing here departs from it.

**Why the record is this document and not a column in `docs/60`.**
`docs/60` section 14 is a datasheet's list of what it found, kept there
by `docs/21` section 10's precedent so that a datasheet does not quietly
pick a side. The evidence that settles item 1 is a walk through thirteen
commits of one file; the evidence for item 2 is seven re-syntheses
reported in `docs/45`. Neither belongs inside a datasheet. Each item in
`docs/60` section 14 now ends with a *Resolved* line naming the
document that was corrected and the section of this record, and
`docs/60`'s revision history carries the amendment as 0.1a.

**Standard of evidence.** Every number a correction asserts is tagged
and traceable to a file in the tree, named in the table in section 4.
Where a document's claim could not be checked against what is on disk,
the claim was left alone and the note says only what the file shows.

---

## 3. The seven, resolved

### 3.1 The pilot campaign: 335, 366 and 378

**As found.** `hw/tb/fi_campaign_results.json` at HEAD holds
`"total": 378`. `docs/16-fault-injection-campaign.md`'s header table,
"current log" paragraph, section 3 headline and section 8 closing note
say the file holds the **366-injection** wave-6 log with **18 SDC
(4.9 %)** — and the section 8 note says **361**, disagreeing with the
rest of its own document. `docs/21-pilot-datasheet.md` section 6.2 calls
the **335-injection** run with **26 SDC (7.8 %)** its "campaign of
record". `docs/30-dispatcher-protection.md` section 5 and
`docs/33-rail-transform.md` section 7 cite 378.

**Why each outlier says what it says.** The file's full history, read
with `git log -p -- hw/tb/fi_campaign_results.json` **[fact]**:

| Commit | Date | `total` | SDC | `wall_seconds` | Document of record |
|---|---|---:|---:|---:|---|
| `b2154b4` | 2026-08-25 | 255 | 91 | 182.3 | `docs/16` section 3.1 |
| `e45d52d` | 2026-08-26 | 255 | 91 | 363.9 | `docs/16` section 3.1 |
| `0723367` | 2026-08-27 | 255 | 48 | 971.7 | `docs/16` section 3.2 |
| `02e61f6` | 2026-08-29 | 287 | 48 | 1,036.6 | `docs/16` section 3.3 |
| `2d59ec2` | 2026-08-29 | 287 | 48 | 509.5 | `docs/16` section 3.3 |
| `c5a5a6e` | 2026-08-29 | 287 | 49 | 555.6 | `docs/16` section 3.3 |
| **`0448282`** | 2026-08-29 | **335** | **26** | 891.6 | `docs/16` section 3.4, **`docs/21` section 6.2** |
| `a13a93f` | 2026-08-30 | 365 | 28 | 566.8 | `docs/16` section 3.5 |
| `3458d36` | 2026-08-30 | 361 | 23 | 706.3 | `docs/16` section 5.10 |
| **`2c6c052`** | 2026-08-30 | **366** | **18** | 567.7 | **`docs/16` section 5.11, its last revision** |
| `634ca3e` | 2026-08-30 | 374 | 11 | 1,755.1 | `docs/29-queue-storage-protection.md` |
| `bc91c71` | 2026-08-30 | 378 | 6 | 443.1 | `docs/30-dispatcher-protection.md` section 5 |
| **`b6738e5`** | 2026-08-31 | **378** | **6** | 445.7 | `docs/33-rail-transform.md` section 7; **the freeze commit** |

Both outliers are real. `docs/21` was last edited at `4dabcbf` on
2026-08-30 and quotes the file as it stood at `0448282`, which it names
**[fact]**. `docs/16` was last edited at `2c6c052`, the commit that
wrote the 366-injection log, and its 366 / 18 / 568 s headline matches
that commit's file to the field (`wall_seconds` 567.7) **[fact]**. The
two waves after it — queue-entry parity in `docs/29`, dispatcher
detection in `docs/30` — were each documented in their own document and
`docs/16` was not edited again. The "361" in `docs/16` section 8 is one
revision older still, from `3458d36`, and was missed when the rest of
the document moved to 366.

**Resolution.** The committed log is the campaign of record: **378
injections, 97 MASKED (25.7 %), 193 CORRECTED (51.1 %), 82 DETECTED
(21.7 %), 6 SDC (1.6 %), 0 HANG, 445.7 s** **[fact, the file at HEAD,
blob `312d3c76`]**. It will not move again: `hw/tb/` is frozen by
`docs/34` and `hw/tb/Makefile.fi` writes this file. `docs/60` section 9
already quoted it.

**Corrected in place.** `docs/16`: a dated note above the "Eight runs"
heading with the full sequence; the header table's injection row; the
"holds the 366-injection log" sentence, struck through; the section 3
headline's "and it is the current log", struck through; the section 8
"361" sentence, struck through. `docs/21`: a dated note above the
section 6.2 headline, the headline relabelled "campaign at `0448282`",
the 7.8 % statement in section 6.4 and the `state_only_divergence` count
in section 6.5 each annotated with the 378-injection value. Every
366-injection and 335-injection figure is left standing as the record of
the run it describes, and the rule against pairing rates whose
denominators differ — `docs/21` section 6.2's own — is restated for
7.8 % against 1.6 %.

**Not corrected, noted.** `docs/30` section 5 quotes 461 s of wall time
for the 378-injection run where the file at `bc91c71` says 443.1. Wall
time is the one figure `docs/16` section 8 says never to quote, and the
two are the same log run on two loads; it is left alone.

### 3.2 The CLINT's area: 16,683.48 and 16,712.82

**As found.** `docs/40-interrupts-timers-watchdog.md` section 9: 1,038
cells / 16,683.48 um2. `docs/45-soc-top-synthesis.md` section 6.2:
1,043 / 16,712.8164. Same file, same recipe, no stated cause at either.

**Why.** `docs/45` section 4.3 had already measured the cause without
either quoting row saying so: `hw/soc/flow/syn_soc.sh` reads every SoC
block before selecting a top, so a block's mapped area is a function of
the whole source list. Removing the three files `docs/44` added —
`soc_busstat.v`, `soc_tmr_bank.v`, `tmr_voter.v` — from the list brings
`soc_clint` back to **16,683.4836 exactly**, and `soc_clint.v` itself
has not changed since `dbbef96`, the commit that published the first
number **[fact, `docs/45` section 4.3, seven re-syntheses]**.
`docs/51-npu-integration.md` section 11 states the same cause for the
fabric, which is what `docs/60` item 3 asked the CLINT rows to do.

**Resolution.** Both numbers stand; **16,712.8164 is the one to quote
for the SoC as it stands**, 16,683.48 is the figure for the list at
`dbbef96`. A dated note sits under the table in `docs/40` section 9 and
under the table in `docs/45` section 6.2, each naming the other and
`docs/45` section 4.3. No re-measurement.

### 3.3 The Ibex core: 313,733.20 and 316,051.66

**As found.** `docs/43-core-hardening.md` section 7.1: 313,733.1960 um2.
`docs/44-margin-and-observability.md` section 7.1, `docs/45` sections 4
and 6.2, and `docs/60` section 5: 316,051.6590 um2.

**What the content difference is.** `docs/44` section 7.1 re-measures
`docs/43`'s register file byte-identically at 313,733.1960 and then
measures the core as shipped — `FASTCORR = 1` with the fault-report port
live — at 316,051.6590 **[fact, `docs/44` section 7.1, one session]**.
The 2,318.4630 um2 between them is the fast-correction read path plus
the report cone that `docs/44` added, and `docs/44` section 7.1 itself
warns which of its rows may be subtracted from which **[estimate, the
difference of two measurements]**. `docs/44`, `docs/45` and `docs/60`
already label their figure "as shipped"; `docs/43` did not say its
figure was not.

**Resolution.** **316,051.6590 um2 is the shipped core**; 313,733.1960 is
the register-file protection alone. A dated note under the table in
`docs/43` section 7.1 says so and names `docs/44` section 7.1. Nothing
else needed changing.

### 3.4 "No power number", five times

**As found.** `docs/47-soc-place-and-route.md` section 9,
`docs/48-floorplan-and-capacitance.md` section 8,
`docs/49-synpre-and-the-binding-path.md` section 12 and
`docs/50-memory-read-register.md` section 10 each end with the line
"one clock, one mode, no scan, no test, no power number";
`docs/45-soc-top-synthesis.md` section 8 says "no power estimate".
`hw/soc/pnr/runs/full3/19-openroad-stapostpnr/<corner>/power.rpt` exists
for all three corners **[fact, present on disk; the run tree is
gitignored]** — 27.774 / 34.835 / 46.095 mW at slow / typ / fast on a
default activity assumption, found by `docs/53-workload-and-the-clock.md`
section 7.1. `docs/57-power-under-a-duty-cycle.md` section 5 then
measured it at RTL activity: 33.890 mW computing, 5.539 mW waiting, at
typ, on a layout with no NPU in it.

**Amended or only superseded?** Only superseded, all five. `docs/57`
section 12 corrects nine statements across `docs/45` to `docs/53` and
names the five for their "one clock, one mode" clause, and `docs/53`
section 7.1 quotes all five lines; neither edited any of the five files,
whose last commits (`3cea98f`, `3afd6bf`, `ade7935`, `4dbabc3`,
`b844857`) predate both **[fact, `git log -1` on each]**.

**Resolution.** Each of the five lines is struck through in place —
`~~no power number~~`, and in `docs/47` also the "no dynamic or leakage
power figure" clause — and followed by a dated note giving both figures
and naming `docs/53` section 7.1 and `docs/57` sections 4 and 5. The
`docs/45` note is worded as *superseded* rather than *corrected*: at
synthesis there was no layout and no power estimate could have been
made, but the sentence has been read as "there is no figure" and there
is one. The same note records that "one mode" is also wrong, per
`docs/57` section 4's clock gate over 2,464 of 3,085 flip-flops.

### 3.5 The watchdog's zero-spurious-escalation headline

**As found.** `docs/41-watchdog-hardening.md` section 1's verdict row —
"126 of 126 CORRECTED, 0 SDC, 0 HANG, 0 disarmed" — and section 8.3's
"**0 and 0** across all 126 injections" for extra escalation ladders.
`docs/43-core-hardening.md` section 8.4 measured **7 spurious
escalations in 1,232 survivable upsets** on the windowed mode and says
`docs/41`'s headline "is therefore gone". `docs/41` did not say so.

**Why both are right.** `docs/41`'s campaign injects into the
watchdog's own flip-flops; `docs/43`'s injects into the core, under the
windowed mode (W7) that `docs/43` added to the block afterwards, and
the seven escalations are core corruptions that pushed a healthy
program's kick over the window **[fact, `docs/43` section 8.4,
`hw/soc/out/fi-h2/campaign.log`]**. The zero is a property of the
earlier experiment and does not describe the block as shipped.

**Resolution.** The retirement is now stated where the claim is made: a
dated *superseded in part* note in `docs/41`'s verdict row and after the
section 8.3 sentence, each giving `docs/43`'s figure and section.

### 3.6 The event engine: 1.71 and 0.58 points

**As found.** `docs/52-npu-connection-fault-injection.md` section 6.2:
`engine` 1.71 points. `docs/56-npu-event-engine-hardening.md` section
3.4: 0.58 points, for the same RTL.

**Which scheme each uses.** `docs/52` draws 100 injections
proportionally over the 140-bit stratum, gets 9 silent wrong inferences,
and weights 9 % by 140 of the connection's **738** bits: 1.71.
`docs/56` splits the stratum into five sub-strata, draws 100 into each,
weights each by its own width to 4.713 bit-equivalents of 140 — 3.37 %
— and weights that by 140 of **809** bits, the connection having grown
under `docs/55`'s hardening: 0.58 **[fact, both documents' own
arithmetic]**. Two things differ, the estimator and the denominator; on
809 bits `docs/52`'s own 9 % would weight to 1.56, not 1.71
**[estimate]**. `docs/55`'s campaign of record measured the unsplit
stratum at 8 of 100, so the design did not move between the two.

**Resolution.** `docs/56` section 3.4 already carried the sentence.
`docs/52` now carries it too, under the section 6.2 table, naming both
estimators and both denominators and pointing at `docs/56` section 8 as
the place where a genuine before-and-after — replayed draws — exists.

### 3.7 The duplicated index row

**As found.** `docs/60` item 2 says `docs/00-index.md` lists
`docs/56-npu-event-engine-hardening.md` twice.

**Resolution.** It did, at `af5f40a`, and it did not at `62f1aff` — the
commit that added `docs/60` itself — nor at any commit since **[fact,
`git show <commit>:docs/00-index.md | grep -c`, eight commits]**. The
statement was stale in the same commit that made it. `docs/60` item 2
now says so; nothing in the index needed changing beyond this
document's own row.

---

## 4. Traceability

| Item | Value to quote | Settled by | Tag |
|---|---|---|---|
| 1 | 378 injections, 6 SDC (1.6 %), 445.7 s | `hw/tb/fi_campaign_results.json` at HEAD, blob `312d3c76`; history by `git log -p` | [fact] |
| 1 | `docs/16`'s 366 / 18 was the file at `2c6c052`; `docs/21`'s 335 / 26 was the file at `0448282` | `git show <commit>:hw/tb/fi_campaign_results.json` | [fact] |
| 2 | 16,712.8164 um2 for the SoC as it stands; 16,683.48 for the `dbbef96` list | `docs/45` section 4.3, seven re-syntheses under `hw/soc/flow/syn_soc.sh` | [fact] |
| 3 | 316,051.6590 um2 shipped; 313,733.1960 register file alone; 2,318.4630 of content | `docs/44` section 7.1, one session | [fact]; difference [estimate] |
| 4 | 34.835 mW typ (default activity); 33.890 computing / 5.539 waiting (measured activity), no NPU in the layout | `hw/soc/pnr/runs/full3/19-openroad-stapostpnr/*/power.rpt`; `docs/53` section 7.1; `docs/57` section 5 | [fact] |
| 5 | 7 spurious escalations in 1,232 survivable upsets under W7 | `docs/43` section 8.4, `hw/soc/out/fi-h2/campaign.log` | [fact] |
| 6 | 1.71 (proportional draw, 738 bits) and 0.58 (split draw, 809 bits) are one quantity under two estimators | `docs/52` section 6.2, `docs/56` section 3.4 | [fact]; 1.56 [estimate] |
| 7 | One row | `docs/00-index.md` at `62f1aff` and after | [fact] |

---

## 5. What this document does not do

- **Nothing was re-run.** No campaign, no synthesis, no place-and-route.
  Items 2 and 3 in particular could have been "settled" by a fresh
  measurement, and that would have produced a third number for each
  without explaining the first two; the explanation was already on disk.
- **It does not sweep the corpus for other stale figures.** The seven
  are the ones `docs/60` found. `docs/21` section 10 lists six more from
  an earlier pass, some of which (`hw/fpga/README.md`'s pre-fix
  figures, the 1,036 / 1,037 flip-flop count) are still as that section
  describes them.
- **It does not judge `docs/21` sections 6.4 and 6.5 against the
  378-injection log beyond the two counts it annotates.** Those
  sections argue from per-structure records; the committed file's
  top-level keys give `state_only_divergence` 4, `latent_register_corruption`
  15 and `telemetry_mismatch` 194 **[fact]**, and which structures those
  sit in is not read out here.

---

## 6. Files edited

All under `docs/`; nothing outside it.

| File | What changed |
|---|---|
| `docs/16-fault-injection-campaign.md` | Dated note above "Eight runs"; header row; three sentences struck through and annotated |
| `docs/21-pilot-datasheet.md` | Dated note above the section 6.2 headline; headline relabelled; two annotations in 6.4 and 6.5 |
| `docs/40-interrupts-timers-watchdog.md` | Note under the section 9 table |
| `docs/45-soc-top-synthesis.md` | Note under the section 6.2 table; section 8 line struck through and annotated |
| `docs/43-core-hardening.md` | Note under the section 7.1 table |
| `docs/47-soc-place-and-route.md`, `docs/48-floorplan-and-capacitance.md`, `docs/49-synpre-and-the-binding-path.md`, `docs/50-memory-read-register.md` | The "no power number" line struck through and annotated |
| `docs/41-watchdog-hardening.md` | Verdict row and section 8.3 annotated |
| `docs/52-npu-connection-fault-injection.md` | Note under the section 6.2 table |
| `docs/60-soc-datasheet.md` | Section 14: a *Resolved* line under each item; revision 0.1a |
| `docs/00-index.md` | This document's row |

---

## 7. References

| Document | What it holds |
|---|---|
| `docs/60-soc-datasheet.md` section 14 | The seven disagreements as found |
| `docs/21-pilot-datasheet.md` section 10 | The precedent for recording a disagreement rather than picking a side |
| `docs/15-pilot-tile-plan.md`, `docs/38-ibex-bringup.md` | The precedent for correcting in place with the original left visible |
| `docs/34-pilot-freeze.md` | Why `hw/tb/fi_campaign_results.json` will not change again |
| `docs/45-soc-top-synthesis.md` section 4.3 | Area as a function of the source list |
| `docs/44-margin-and-observability.md` section 7.1 | The core's area, by content |
| `docs/53-workload-and-the-clock.md` section 7.1, `docs/57-power-under-a-duty-cycle.md` | The power number that five documents said did not exist |
| `docs/43-core-hardening.md` section 8.4 | The seven spurious escalations |
| `docs/56-npu-event-engine-hardening.md` section 3.4 | The two estimators |
