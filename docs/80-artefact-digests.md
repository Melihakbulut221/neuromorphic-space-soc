# 80 — The evidence is not in git, so its identity is: 329 artefacts pinned by SHA-256, and what that does not prove

> **AMENDED 2026-09-10.** The manifest was 149 rows when this document
> was written. It is 329 now, and the two reasons are in section 13,
> which is the part of this document worth reading first if you read it
> before. In short: the paper's section 8 rested on seventeen run
> directories that **nothing here pinned**, while `paper/claims.yaml` said in a
> comment that they were pinned here; and the four pilot rows sealed the
> run `docs/34` section 3.1 has labelled **SUPERSEDED since 2026-08-31**
> while calling it "the frozen pilot sign-off harden". No digest in the
> original 149 rows changed. What was wrong was the coverage and the
> label, which is the failure mode this document exists to make visible
> and did not catch on itself.
>
> Every number below that carries a `[fact, 2026-09-09]` marker is the
> measurement **as taken that day** and is left standing rather than
> rewritten, per `docs/64`. The 2026-09-10 figure is printed beside it.

An external review of this corpus, 2026-09-09, put the gap in one
sentence:

> Today a reader can verify that the guards work and cannot verify that
> anything was ever wrong: the pre-fix netlist is untracked.

It is correct, and it is the sharper half of a complaint `docs/79`
section 3 had already made about itself — *the gate side is not in git,
publishing the digests would be the cheap fix and has not been done.*
This document is the cheap fix. It is not the expensive one, and section
4 is about the difference.

---

## 0. Read this first

**Every counterfactual in this project lives in a git-ignored
directory.** The unrepaired layout that restarts on all 174 injections
(`docs/75` section 8.3), the four record files of the two-by-two that
makes the reset a property of the RTL rather than of the mapping
(section 8.5), the pre-repair clock-gate layout whose difference from the
repaired one `docs/77` section 9.3 decomposes gate by gate, the DEF
`docs/79` measured replica separation from — none of them is in the
repository, and none of them ever will be. The five `final/` artefacts
of one SoC layout are 190 MB, there are six layouts, and the run
directories they sit in are 81 GB between them.

The consequence is not that the claims are unsupported. It is that the
support is **unilateral**: a reader could check the guards, the tests,
the formal jobs and the RTL, and had no way to check that the artefact
those documents measured is the artefact the author still has.
`scripts/artefact_digests.py` and `docs/80-artefact-digests.tsv` close
exactly that much and no more.

---

## 1. Verdict first

**329 artefacts, 5.16 GB, pinned by SHA-256 in a 70.8 kB tracked file**
**[fact, 2026-09-10]**. Twenty-six groups, each naming the documents —
or, for eight of them, the paper section — that rests on it. Each row
carries the path, the size in bytes, the digest, and a handful of
metrics read out of the artefact itself so that the row is legible to
someone who cannot open the file.

*Was **149 artefacts, 1.91 GB, 34.8 kB** in sixteen groups **[fact,
2026-09-09]**. Section 13 says what the other 180 rows are and why they
were missing.*

**`--check` re-verifies against the working tree and distinguishes
MISSING from CHANGED**, which is the whole design of it: a fresh clone
has none of these files, reports 329 MISSING, and **exits 0**. Only a
file that is present and hashes differently is a failure.

**And it is one line of arithmetic wide.** The retained run tree on this
machine is **182 GB** — 54 SoC place-and-route runs, 37 pilot hardens,
302 build directories under `hw/soc/out/` **[fact, 2026-09-10, `du
-sb`]**. This manifest pins **2.8 % of it**, chosen by reading the
documents and the paper for the paths they actually rest on. Section 5
lists what that leaves out.

*Was **139 GB** and **1.4 %** **[fact, 2026-09-09, `du -sh`]**. The tree
grew by the section 8 runs themselves — the four Magic deck runs alone
wrote 13.3 GB of `.lyrdb` report database, which section 5 says is
deliberately not pinned — not by anything being copied.*

> **A DIGEST PROVES IDENTITY, NOT CORRECTNESS.** It says the file the
> author measured is the file the author still has. It does not say the
> file is right, it does not say the measurement was right, and **a
> reader who cannot obtain the artefact cannot check the claim — only
> that the author did not swap it afterwards.** Section 4.

---

## 2. What is pinned

`scripts/artefact_digests.py --write` walks a declared table of groups.
The table is in the script and each entry names its documents; this is
the summary **[fact, 2026-09-10]**:

| group | cites | rows | bytes | what it is |
|---|---|---:|---:|---|
| `pilot-signoff-gated` | 31, 34, 36, 79 | 6 | 40,834,302 | **CURRENT.** The frozen pilot sign-off harden: `final/` netlist, powered netlist, DEF, GDS, `metrics.json`, `resolved.json` |
| `pilot-submission-gated` | 31, 34, 36 | 6 | 40,834,121 | **CURRENT.** The run the shuttle's submission path builds |
| `pilot-signoff-superseded` | 31, 32, 34, 79 | 6 | 40,834,246 | **SUPERSEDED 2026-08-31, RETAINED.** `signoff-6x2` — still the artefact `docs/32` and `docs/79` name |
| `pilot-submission-superseded` | 31, 34 | 6 | 40,834,071 | **SUPERSEDED 2026-08-31, RETAINED.** `submission-6x2` |
| `pilot-shape6x2` | 26, 27 | 5 | 37,370,513 | the 6x2 harden `docs/26`'s gate-level campaign injected into |
| `soc-s70boot2` | 70, 71 | 5 | 190,498,190 | `docs/70`'s boot-hardened layout |
| `soc-s71boot` | 71, 74, 75, 79 | 5 | 190,498,190 | the repeat of it, and **the unrepaired counterfactual** of `docs/75` |
| `soc-s75w9` | 75, 79 | 5 | 192,330,338 | the W9 repair, laid out |
| `soc-s76gate` | 76, 77 | 5 | 193,113,259 | `docs/76`'s clock-gated layout |
| `soc-s77base` | 77 | 5 | 193,113,259 | `docs/77`'s baseline, built to reproduce `s76gate` |
| `soc-s77gate` | 77 | 5 | 193,711,353 | `docs/77`'s split-enable repair, and the layout **all of section 8 is about** |
| `soc-synth` | 71, 74, 75, 77 | 10 | 30,211,450 | five whole-SoC synthesis netlists and their area reports |
| `fi-rtl` | 42, 44, 74, 75 | 8 | 356,054 | the RTL campaigns and the golden runs the gate arms are compared against |
| `gl-74` | 74 | 17 | 163,741,063 | `docs/74`'s map, census and record files |
| `gl-75` | 75 | 15 | 487,240,566 | **the four arms of the two-by-two** |
| `equiv-79` | 79 | 15 | 441,434 | the `eqy` results, **the five job logs `paper/claims.yaml` names**, and both negative controls |
| `sim-77` | 76, 77 | 7 | 8,601 | every signal at every edge, two builds one parameter apart |
| `power-77` | 76, 77 | 42 | 78,752 | two layouts, three corners, busy and idle, plus the self-comparison |
| `deck-magic-soc` | paper §8 | 14 | 1,717,896,891 | the seventeen-hour Magic DRC and the abstracted-macro run. **39,969,214 boxes, 0 outside**, against **123 boxes that do not exist** |
| `deck-inputs` | paper §8 | 17 | 204,687 | **the instrument, not its output**: `classify.py`, the four run scripts, their step and state JSONs, and the two abstracted macro views |
| `deck-magic-bare` | paper §8 | 12 | 445,438,196 | the two bare-macro calibrations: 8,808,860 and 2,210,913 boxes with no design near them |
| `deck-klayout` | paper §8 | 24 | 5,267,397 | KLayout DRC on the SoC, on both bare macros, and **the positive control** |
| `lvs-77` | paper §8 | 36 | 204,425,047 | **seven** Netgen LVS variants, of which three match uniquely and four do not |
| `soc-timing-factorial` | paper §8 | 15 | 588,391,810 | the three non-baseline arms of the 2×2 repair experiment, laid out |
| `sta-slow-corner` | paper §8 | 28 | 158,030,228 | slow-corner sign-off STA of all four arms: worst paths, violator lists, `period_min` |
| `sta-compare-81` | paper §8 | 10 | 6,950,305 | the independent OpenSTA period sweep and the transition/capacitance scans |
| **total** | | **329** | **5,162,654,323** | |

*The 2026-09-09 table had sixteen rows and totalled **149 artefacts,
1,910,022,044 bytes**, with `pilot-signoff` in place of the four pilot
rows above at 5 rows and 37,320,314 bytes. It is superseded rather than
wrong in its own terms: every digest it carried is still in the file.*

### 2.1 What a row looks like

```
gl-75  75  records  hw/soc/out/gl75w9/records_gl_wdog.csv  19712
  f88b983e079bcc9a8e3e75e63c13dfa4c9e6e2dcc753e4829f41f5c611bf2606
  rows=174;cols=18;corrected=174;wdog_rst_events=0
```

Seven tab-separated columns: group, the documents that cite it, a role,
the path, the size, the digest, and the metrics. The metrics are
`k=v;k=v` and they are **read out of the artefact by the script's own
extractors** — the class tally and the event count above are counted from
the CSV, not copied from `docs/75` section 8.4. They are a legibility
aid. **The digest is the check.**

### 2.2 What the metrics are, per kind of artefact

| role | metrics |
|---|---|
| `metrics` (a run's `final/metrics.json`) | 22 keys: die area, instances, standard cells, flip-flops, clock gates, utilisation, setup and hold worst slack at all three corners, setup TNS and violating endpoints, repair buffers, routed wirelength, DRC, slew and cap violations, antenna nets. The rows `docs/71` section 5.2 and `docs/77` section 9.2 tabulate |
| `netlist` | lines, mapped cells, sequential cells, macros — streamed line by line for the reason `hw/soc/pnr/violator_census.py` gives, that `soc_top.nl.v` is 10.8 MB |
| `def` | `UNITS DISTANCE MICRONS`, `DIEAREA`, the component count. **Header only**, deliberately: everything past `COMPONENTS` is 70 MB the digest already covers |
| `records` | rows, columns, the tally of the class column, and the sum of `wdog_rst_events` where the column exists |
| `provenance` | the campaign's own `netlist md5`, `netlist size`, `rom hex md5` and flop count |
| `map` | cycles, RTL rows, gate rows, the cycle shift, RTL bits, gate flops. A map over 8 MB is read down to its `"entries"` key and no further: four of them are 161 MB and `json.loads` on one costs over a gigabyte of heap to recover six integers |
| `report` | for a power report, the window, the corner, and internal / switching / leakage / total watts off its `TOTAL` line |
| `gds` | **none.** Section 4.3 |

Seven roles were added on 2026-09-10 for section 8's artefacts, which
are a different shape — a deck report, a classification, a KLayout
report database, an OpenSTA sweep:

| role | metrics |
|---|---|
| `classification` | total error boxes, and the inside / straddling / outside split **twice**: against the LEF footprint the floorplan reserves, and against the drawn extent that adds the macro's 0.225 µm NWell overhang. Plus boxes outside the die, and how many rules fired. `drawn_outside` is the number section 8 puts in bold |
| `drcrpt` | the top cell, the report's own `[INFO] COUNT:`, and **the divisor caveat as text** — the report's last line says the count "should be divided by 3 or 4", and a reader without the file should see that beside the count. Read from the first 4 kB and the last 4 kB, so a 1.7 GB report costs nothing |
| `drclog` | lines, and the same `COUNT:`. This is where the two bare-macro figures come from: those runs have no classification, because there is no design around the macro to classify against |
| `lyrdb` | top cell, items, **rules declared and rules fired** (173 and 3), distinct base cell names (60), and `outside_macro` — the count of base names that are neither `RM_IHPSG13*` nor `RSC_IHPSG13*`. That last one is the claim written so that it could come back non-zero, and on the positive control it does |
| `lvs` | Netgen's `Final result:` verbatim, the device and net counts, **both columns when they differ**, and the number of rows Netgen marked `**Mismatch**` |
| `sweep` | the number of swept periods, the 20 ns point (worst slack, TNS, violating endpoints), and `closes_at` — the smallest swept period with zero violating endpoints. **Absent from the row when nothing closes**, which is the honest rendering of `s81drv` |
| `sta` | `period_min` and `fmax` from `clock.rpt`; the corner-tagged number from `wns/tns/ws.max.rpt`; the violating-endpoint count from `violator_list.rpt`; the worst path's start and end point from `max.rpt`. A file over 8 MB is line-counted in binary and scanned only to the end of its first path block — 35 MB of `max.rpt` in about 20 ms |

**These are new roles rather than widened old ones, and that is
deliberate.** Teaching `m_text` to recognise `[INFO] COUNT:` would have
changed the metrics of rows pinned on 2026-09-09, and `--check` would
have called it `EXTRACTOR` drift — correctly. That outcome exists to
catch exactly this, and the response to it is to not do it, not to
rewrite 149 rows until it goes quiet.

---

## 3. What a reader can do with this, in three cases

**Case 1 — the reader has the artefacts** (this machine, or a copy of
the run tree). `--check` is a real check and it is the one that matters:
329 verified, 0 changed, 30 seconds **[fact, 2026-09-10]**; it was 149
verified, 0 changed, 3.4 seconds **[fact, 2026-09-09]**. If any file
under a pinned path is ever replaced, edited or regenerated, this says
so and exits non-zero. That is the case the review asked for: *the
pre-fix netlist is untracked* becomes *the pre-fix netlist is untracked
and cannot be quietly changed.*

**Case 2 — the reader can obtain the artefact from the author.** Then
the digest is worth what a digest is worth: it establishes that what
arrived is what was measured. The reader can then do their own work on
it — re-run `hw/soc/fi/gl_netlist.py --wdog-census`, re-run the
placement measurement, diff two netlists — and every conclusion they
reach is about the object the documents are about. **Without the
digests, that transfer proves nothing**, because the sender chooses what
to send.

**Case 3 — the reader has a clone and nothing else.** This is most
readers and it is the case to be honest about. `--check` reports 329
MISSING and exits 0. What they gain is:

- **the shape of the evidence**: 329 files, what kind each is, which
  document rests on which, and how big the whole thing is;
- **the metrics, committed**: the numbers `docs/71` section 5.2 and
  `docs/77` section 9.2 print in prose now sit beside a digest in a
  machine-readable file, so a document that drifts from its own artefact
  can be caught by comparing two tracked files. Since 2026-09-10 that
  covers the paper's section 8 as well, and it covers it more than
  anywhere else: **`0` outside the macros, `9668` items in `3` of `173`
  rules, `62256` devices and `61912` nets, `24.68 / 25.21 / 23.36 /
  23.03` nanoseconds, `closes_at=25.00` — every headline number in that
  section is now a field in a tracked file that was read out of the
  artefact, not typed**;
- **an anchor in git history**: from the commit that carries this
  manifest onwards, a swapped artefact is a detectable act rather than
  an undetectable one.

What they do **not** gain is any ability to check that the artefacts are
right. Section 4.

---

## 4. What a digest does not prove

### 4.1 Identity is not correctness, and this is the whole of it

A SHA-256 says two byte strings are the same. It says nothing about
whether `s71boot`'s netlist implements the RTL, whether the 174 records
were classified correctly, whether the campaign's oracle is the right
oracle, or whether the layout would work on silicon. **If an artefact
was already wrong on 2026-09-09, this manifest pins the wrong one and
will go on reporting VERIFIED forever.** It is a seal, not a proof.

### 4.2 It is a seal a reader cannot break open

The plainest statement of the limit: **a reader who cannot obtain the
artefact cannot check the claim, only that the author did not swap it.**
Every entry here is a promise about a file that reader will never see.
The manifest converts *trust the author's measurement* into *trust the
author's measurement, and observe that the author has not changed the
thing measured since committing this* — which is strictly more than
nothing and strictly less than verification.

And it is **self-notarised**. The digests were computed by the author, on
the author's machine, from the author's files, after the documents were
written. Nothing external timestamps them. The only thing that makes
them evidence at all is the git commit that carries this file, and its
date is the earliest moment from which anything is pinned. **Everything
before that date is still taken on the author's word.**

### 4.3 A GDS digest pins the file, not the layout

`docs/71` section 5.3 compares GDS files by masking 231 timestamp
records and then running `cmp`, and that is not an aesthetic choice: a
GDS stream carries `BGNLIB` and `BGNSTR` dates, so **two runs producing
byte-identical geometry produce GDS files with different digests.** The
manifest shows it. `s70boot2` and `s71boot` — which `docs/71` proves are
the same layout — have the same digest for `final/def/soc_top.def`,
`final/nl/soc_top.nl.v` and `final/metrics.json`, and **different**
digests for `final/gds/soc_top.gds` **[fact, `docs/80-artefact-digests.tsv`]**.

So the eight `gds` rows pin the files that were streamed. They do not,
on their own, say two layouts are the same, and the masking comparator
that would is not in this script. Nothing here supersedes `docs/71`
section 5.3; that section did the comparison and this one does not.

### 4.4 The metrics column is not independent corroboration

It is derived from the same bytes, by this script, at the same moment as
the digest. If the extractor is wrong, both the pinned metric and the
recomputed one are wrong in the same way and `--check` says VERIFIED.
The metrics are there so that a reader without the file can read the
row; they are not a second opinion.

The one thing they do catch is **extractor drift**: bytes matching the
pinned digest while the recomputed metrics do not can only mean this
script changed, so `--check` reports that as `EXTRACTOR` rather than
blaming the artefact, and exits non-zero. A manifest whose metric
columns no longer describe its own digests is not a record.

### 4.5 A manifest can be complete, current and green while pinning the wrong thing

Added 2026-09-10, because it happened here.

`--check` answers one question: *do the files named in this manifest
still hash to what this manifest says.* It cannot answer *is this
manifest naming the files the documents rest on*, and on 2026-09-09 the
answer to the second question was no in two different ways at once —
seventeen run directories absent, and one run pinned under a description that
had been false for nine days. **Both were invisible to `--check`, which
reported 149 verified and exited 0 throughout.**

This is the same defect this corpus keeps finding in its own
instruments, arriving one level up: a green result read wider than what
the instrument looked at. The check was never wrong. The reading of it
was. Section 12 item 1 asked for a test that runs `--check`; what this
episode says is that such a test would not have caught either of these,
and what is actually needed is a check that the manifest still names
what the documents and `paper/claims.yaml` cite. Section 12 item 5.

### 4.6 Two rows are machine-specific by construction

`resolved.json` and `provenance.txt` contain absolute paths — the run
directory, the PDK in `~/.ciel`, the `iverilog` install. A second
machine that reproduced a run byte for byte would still get a different
digest for those two, and `--check` would correctly call it CHANGED.
They are pinned anyway, because `provenance.txt` is the file that ties a
campaign arm to the netlist md5 it ran on and is therefore load-bearing
for `docs/74` and `docs/75`, and because a CHANGED row that turns out to
be a path is a five-second diagnosis whereas an unpinned provenance file
is a missing link.

---

## 5. What this does NOT cover

- **2.8 % OF THE RETAINED TREE.** 182 GB is on this machine and 5.16 GB
  is pinned **[fact, 2026-09-10]**. 27 of the 54 SoC runs are named
  somewhere in the manifest; 21 of the 23 pilot `pilot_ihp` hardens, all
  14 `pilot_sky130` runs and 276 of the 302 `hw/soc/out/` build
  directories are **not**. Everything `docs/47` through `docs/73`
  measured — `full3`, `npu2`, `s67`–`s70`, the floorplan variants, the
  CLINT placement probes, the `docs/25` sky130 work — rests on artefacts
  nothing pins. The selection was made by reading `docs/26`, `docs/31`,
  `docs/32`, `docs/34`, `docs/71`, `docs/74`, `docs/75`, `docs/77`,
  `docs/79`, `paper/main.tex` section 8 and `paper/claims.yaml` for the
  paths they rest on. **It is a judgement about which claims are
  load-bearing, and a reader is entitled to disagree with it.** *Was
  1.4 % of 139 GB, 30 of 36 SoC runs unpinned **[fact, 2026-09-09]**.*
- **MOSTLY `final/` AND `resolved.json` OF EACH RUN.** The 62 step
  directories are not pinned, with one exception added 2026-09-10: the
  `*-openroad-stapostpnr` step of the four timing arms, because
  `paper/main.tex` section 8 quotes the worst path, the violator list
  and `period_min` out of it and `final/metrics.json` does not carry
  those. Everything else in every step directory is unpinned, and that
  matters more than it sounds: `docs/71` section 5.2 calls the ten
  per-iteration DRC counts and wirelengths **the sharpest evidence in
  the document**, because they are the router's internal trajectory, and
  they live in step reports this manifest still does not touch.
  `final/metrics.json` carries the same ten values as
  `route__drc_errors__iter:N`, so they are pinned as numbers; the step
  artefacts they were computed from are not.
- **13.3 GB OF MAGIC REPORT DATABASE IS DELIBERATELY NOT PINNED.** Each
  of the four Magic deck runs writes both `reports/drc.magic.rpt` and
  `reports/drc.magic.lyrdb` — the same errors twice, once as text and
  once as a database in KLayout's `.lyrdb` format. The `.rpt` is pinned because
  `classification.txt` names it by absolute path as the file the
  classifier read; the `.lyrdb` is 13.3 GB across the four runs, is
  named by no document and by no claim, and pinning it would have
  tripled the manifest's cost to seal a second copy of something already
  sealed. **A reader who thinks that is the wrong call is looking at the
  right question**: the `.lyrdb` is what a KLayout user would actually
  open, and it is unsealed.
- **THE SEVEN LVS RUNS' `final/` VIEWS ARE NOT PINNED**, because they
  are byte-for-byte copies of `s77gate`'s: `s77lvs-a` and `s77lvs-b`
  both carry `final/nl/soc_top.nl.v` at `50515ae4…`, which is the digest
  already pinned under `soc-s77gate` **[fact, `sha256sum`]**. Pinning
  them would have added about 1.4 GB of duplicate rows. The same goes
  for the 144 MB `views/soc_top.drc.mag` each Magic run writes, and for
  the 40 MB `reports/lvs.netgen.json` beside each Netgen report.
- **`s77gate-sta-periodsweep` IS NOT PINNED.** It is an earlier and
  partly superseded version of the sweep that became `s81-sta-compare`,
  no claim names it, and nothing in the paper reads it. It is on this
  machine and it is unsealed; it is named here so that a reader who
  finds the directory knows it was seen and left out rather than
  missed.
- **NOTHING RUNS `--check` AUTOMATICALLY.** There is no test in
  `sw/tests/` that invokes it and `scripts/verify.sh` does not call it.
  So this manifest is a thing a person runs, not a gate, and on the day
  it was written the only protection it offers is against a change nobody
  is looking for. Adding a test is the obvious next step and is stated
  here rather than assumed. *Still true on 2026-09-10, and section 4.5
  says why the obvious test is not the one that was needed.*
- **NOTHING CHECKS THAT THE MANIFEST STILL COVERS WHAT IS CITED.** This
  is the gap section 4.5 is about and it is not closed by this
  amendment. `paper/claims.yaml` names **19 distinct artefact paths under
  git-ignored directories**; every one of them now resolves to at least
  one pinned row **[fact, 2026-09-10, the script in section 11]**. But
  nothing in the tree compares those two files, so the next claim added
  there can go unpinned exactly as these did. Section 12 item 5.
- **A CHANGED ROW DOES NOT SAY WHAT CHANGED.** It prints the pinned and
  the on-disk size and digest. For a 108 MB GDS that is the entire
  diagnosis available from this script.
- **NO ARTEFACT IS MADE AVAILABLE.** This does not publish, mirror, or
  upload anything. `scripts/gen_public_mirror.py` (`docs/78`) carries the
  tracked tree and would carry this manifest with it; it would not carry
  a single artefact the manifest names.
- **THE CAMPAIGN VCDs ARE NOT PINNED.** `docs/77` section 7 compares
  2.7 GB of dump per build. The comparison's **output** is pinned
  (`h77-g/equiv-vs-76.txt`, 5,146 signals, 415,345 cycles, 0 differing);
  the dumps are not, and they are also the largest single thing in the
  tree.
- **ONE MACHINE, ONE MOMENT.** Every digest was taken on 2026-09-09 on
  the machine `docs/71` section 4.2 describes.

---

## 6. Five things the manifest settled, three on the day it was written and two on 2026-09-10

None of these was the point of the exercise. All of them came out of
sorting the digest column, which is what a manifest is for.

**6.1 `docs/75` section 3.2's netlist is this netlist.** That section
quotes `md5 2e43d08ff422be8ce7a0efd17b1cc3da`, 10,831,575 bytes for
`s71boot`'s `final/nl/soc_top.nl.v`. The file on disk on 2026-09-09 has
exactly that md5 and that size **[fact, `md5sum`]**, and is now pinned as
`c261069c1eaec0db24cefc1d5dba9dce447f0e075479e57311c1b19a7b5d9272`. The
document and the artefact agree, which had never been checked
mechanically because nothing was in a position to check it.

**6.2 `docs/71` section 5.3's byte-identity still holds, four days
on.** `s70boot2` and `s71boot` share a digest for the netlist, the DEF
and `metrics.json`, and differ on the GDS for the reason section 4.3
gives. That is `docs/71`'s result, re-derived by a different instrument
that knew nothing about it.

**6.3 `docs/77` section 9.1 was more true than it claimed.** That section
says `s77base` **reproduces `s76gate` on every metric this document
reads** and lists them. The digests say more: `s76gate` and `s77base`
have **identical netlist, DEF and `metrics.json` digests** and different
GDS digests — two separate runs, streamed at different times, whose
placement and routing came out byte for byte the same. That is a
stronger statement than the document makes.

> **IT IS RECORDED HERE AND `docs/77` IS NOT EDITED.** A superseded or
> strengthened measurement is left standing with a dated marker
> (`docs/64`); it is not rewritten in place. `docs/77` section 9.1 says
> what its author checked, and what its author checked was the metrics.
> The byte identity is this document's observation, dated 2026-09-09, and
> anyone restating `docs/77` should cite both.

### 6.4 The two extra checker bindings moved nothing measurable, and now that is a digest

Added 2026-09-10, out of pinning the two runs the manifest had been
missing.

`docs/34` section 4 argues that the two keys `docs/36` added —
`MAX_CAP_VIOLATION_CORNERS` and `MAX_SLEW_VIOLATION_CORNERS`, both
`["*"]` — are different in kind from the six recovery keys: *the six buy
timing margin, these two buy none — they make two checkers able to
fail.* That was an argument from what the keys do.

The manifest now says it as an observation. `signoff-6x2` and
`signoff-6x2-gated` have the **same digest for `final/metrics.json`**,
`f3889ee38760ac90…`, and so do `submission-6x2` and
`submission-6x2-gated` at `39a17f64239eebc1…` **[fact,
`docs/80-artefact-digests.tsv`]**. Two hardens, one with the checkers
bound at every corner and one without, and **not a single metric in the
file differs**. The gating changed what could be reported, not what was
built.

Across all four runs the netlist, the **powered** netlist and the DEF
are one digest each — `52b2debf…`, `39470ad1…`, `8f99c979…` — which is
`docs/34` section 3.2's central claim re-derived by an instrument that
knew nothing about it. What separates sign-off from submission in
`metrics.json` is not a value but **two extra keys**:
`klayout__drc_error__count` and `design__xor_difference__count` exist in
the sign-off runs and not in the submission runs, because the geometric
decks ran there **[fact, `json.load`, both files]**. Zero differing
values among the keys they share.

### 6.5 The decks are chained to the layout by digest, not by assertion

Section 8 of the paper says the decks were run "over this design's own
final mask data". That was a sentence. It is now a chain of pinned
files:

- `s77gate-drc-full/state_in.json` and `s77gate-drc-abstract/state_in.json`
  name `s77gate/final/gds/soc_top.gds` and `s77gate/final/def/soc_top.def`
  as their inputs, and both of those are pinned under `soc-s77gate`;
- `s77gate-klayoutdrc/COMMANDS` carries the whole `klayout` invocation
  including the same `s77gate/final/gds/soc_top.gds` and the PDK version
  hash `c4b8b4e5…`;
- the seven LVS runs carry `s77gate`'s `final/nl/soc_top.nl.v` forward
  byte for byte — `50515ae4…`, the digest already pinned under
  `soc-s77gate` **[fact, `sha256sum`]**.

So a reader with the artefacts can establish, without trusting the
prose, that the deck that returned zero and the layout `docs/77` section
9 measured are the same layout. **A reader without the artefacts still
cannot**, and section 4.2 is the reason.

---

## 7. The check, and why MISSING is not FAILED

`sw/tests/test_flow_evidence.py` states the rule in its own docstring and
this script follows it: run outputs are git-ignored, a fresh clone has
none of them, and **a check that failed there would be a check nobody
could run**, so the audit would be deleted by the first person who found
it inconvenient.

Four outcomes per row, and only two of them are failures **[fact, all
four exercised 2026-09-09, section 9]**:

| outcome | meaning | exit |
|---|---|---|
| `VERIFIED` | present, and the bytes hash to the pinned digest | 0 |
| `MISSING` | not on this machine. **Expected on a clone** | 0 |
| `CHANGED` | present, and does **not** hash to the pinned digest | 1 |
| `EXTRACTOR` | bytes match, recomputed metrics do not — this script changed | 1 |

A run where every row is MISSING prints one paragraph saying that is what
a clone looks like, and succeeds. A run with some rows missing says how
many and does not treat it as an error, because run trees are kept per
machine.

**And `--write` refuses to shrink the manifest.** Rebuilding it on a
machine that has half the run tree would silently delete half the
evidence record — which is precisely the failure this file exists to
prevent, arriving from the direction of the tool. It prints what it would
drop and exits 1; `--allow-shrink` is the deliberate override.

---

## 8. Cost

| | 2026-09-10 | 2026-09-09 |
|---|---|---|
| artefacts pinned | 329 | 149 |
| bytes pinned | 5,162,654,323 | 1,910,022,044 |
| bytes committed | 70,811 (the `.tsv`), 0.0014 % of what it pins | 34,808, 0.0018 % |
| `--write` | 33-38 s | 3.4 s |
| `--check` | 30-34 s | 3.4 s |
| peak resident | 27.7 MB | — |
| files over 100 MB | 15 of 329 | 10 of 149 |

**[fact, this machine; the right column 2026-09-09 warm cache, the left
column 2026-09-10 over five runs of `/usr/bin/time`, `--check` at
29.7 / 30.4 / 31.6 / 33.7 s and `--write` at 32.6 / 37.8 s. The spread
is page cache, not the script: the four Magic deck reports alone are
2.16 GB and this machine does not hold them]**. Both modes are dominated by hashing and the eightfold rise in
cost is the 2.7 GB of section 8 artefacts, not the new extractors:
`--check` reads 5.16 GB where it used to read 1.91 GB.

Fifteen of the 329 files exceed 100 MB — six GDS streams, four 161 MB
campaign maps, three more layouts from the timing factorial, one 1.7 GB
and one 357 MB deck report — and the extractors are written so that none
of them is read twice. The DEF reader stops at `COMPONENTS`, the map
reader stops at `"entries"`, the STA reader counts newlines in binary
and scans only the first path block of a 35 MB `max.rpt`, and
**`m_drcrpt` reads 8 kB of a 1.7 GB report**: 4 kB at the front for the
top cell, 4 kB at the back for the `[INFO] COUNT:` line. Peak resident
memory over the whole 329-row `--check` is 27.7 MB. Before the map cut
the 149-row run took 6.6 s and peaked over a gigabyte.

---

## 9. Verification

Everything in section 7's table was exercised rather than asserted, on a
scratch tree holding only the script and the manifest:

```
--check, full tree               149 verified, 0 missing, 0 changed   exit 0
--check, empty tree                0 verified, 149 missing, 0 changed exit 0
--check, one artefact swapped      1 changed                          exit 1
--check, one pinned metric edited  1 extractor-drift                  exit 1
--write, incomplete tree           REFUSED, "would drop" 147 paths    exit 1
```

**[fact, 2026-09-09]**. The swap used for the CHANGED case is the one
this whole document is about: `gl75base/records_gl_wdog.csv` copied over
`gl75w9/records_gl_wdog.csv` — the unrepaired arm's records put where the
repaired arm's belong. **Same 19,712 bytes, different digest, caught.**
That substitution is invisible to every other instrument in this
repository: same row count, same column count, same 174 CORRECTED, and
the only column that differs is the one `docs/75` section 8.4 exists to
report.

And the EXTRACTOR outcome fired for real rather than only in the
rehearsal. The first version of this script parsed all four 161 MB
campaign maps with `json.loads`; narrowing that to a header read
(section 2.2) dropped one metric, `entries`, from four rows, and
`--check` reported **4 extractor-drift, 145 verified, exit 1** against
the manifest written minutes earlier — naming the script rather than the
artefacts, which is what it is for. The manifest was rebuilt and the four
`entries` values are gone from it; they equalled `rtl_bits` in all four,
which is why the narrowing was taken.

### 9.1 Re-exercised on 2026-09-10, against the 329-row manifest

Adding 180 rows and seven extractors is exactly the kind of change that
can turn a check green by widening it, so all four outcomes were run
again rather than assumed to still work **[fact, 2026-09-10]**:

```
--check, full tree               329 verified, 0 missing, 0 changed   exit 0
--check, empty tree                0 verified, 329 missing, 0 changed exit 0
--check, one artefact swapped    328 verified, 1 changed              exit 1
--check, one pinned metric edited 328 verified, 1 extractor-drift     exit 1
--write, empty tree              REFUSED, "would drop" 329 paths      exit 1
```

**The swap is the same test as 2026-09-09's and it was chosen for the
same property, on a section 8 row this time.**
`s77lvs-e-normalised/01-netgen-lvs/reports/lvs.netgen.rpt` was copied
over `s77lvs-d-delimiters/01-netgen-lvs/reports/lvs.netgen.rpt`. The two
files are **50,730,503 bytes each** and their manifest rows carry
**character-for-character identical metrics** —
`devices=62256;nets=61912;nets_circuit2=61930;result=Netlists do not
match;mismatch_lines=24` — because the two variants differ in how
Netgen's name delimiters are configured and not in what Netgen
concluded. Every column of the manifest except one is blind to the
substitution. The digest is not:

```
CHANGED   hw/soc/pnr/runs/s77lvs-d-delimiters/01-netgen-lvs/reports/lvs.netgen.rpt
          pinned 50730503 bytes 1bf20e91431ca4d12fd43a883dcf0dadc23dc3d6f920e5888e8fd6e1b30debf9
          on disk 50730503 bytes c04e72d1dac2e17e6d65b149c362d83c0c66d4a8247bfee0ca302d4a5d3200ee
```

The file was restored from a copy taken before the swap, its digest
re-checked against `1bf20e91…`, and `--check` returned to 329 verified,
exit 0.

**The EXTRACTOR case was fired on a new extractor**, because a new
extractor that could not drift would be an instrument that could not
return red. `boxes=39969214` was edited to `boxes=39969215` in the
`s77gate-drc-full/classification.txt` row of the `.tsv` — one digit, in
the number the paper's deck table is built on — and `--check` reported:

```
EXTRACTOR hw/soc/pnr/runs/s77gate-drc-full/classification.txt
          bytes match the pinned digest, metrics do not.
          pinned  boxes=39969215;lef_inside=39969214;...
          derived boxes=39969214;lef_inside=39969214;...
```

328 verified, 1 extractor-drift, exit 1. The `.tsv` was restored from
the copy taken before the edit.

**What this does NOT establish.** All four outcomes fire, and that is a
statement about the four *outcomes*, not about the 163 new rows. Nothing
here shows that the group table names the right files — section 4.5 is
the whole point that it did not, for nine days, and no run of `--check`
would have said so. The swap test exercises one row of 329.

---

## 10. Files touched

| File | What |
|---|---|
| `scripts/artefact_digests.py` | new 2026-09-09. The group table, the extractors, `--write` / `--check` / `--list`. **Amended 2026-09-10**: four pilot groups where there was one, eight section 8 groups, five eqy logs, seven new extractors, and `cite_label` so that `--list` can print a paper section instead of `docs/paper8` |
| `docs/80-artefact-digests.tsv` | new, generated, tracked. 149 rows; **329 since 2026-09-10** |
| `docs/80-artefact-digests.md` | this document |

Nothing under `hw/rtl/`, `tt/`, `formal/`, `hw/openlane/` or `hw/tb/` was
touched; the freeze `docs/34` section 9.3 records is intact, and no test
count moved because no RTL and no harness changed. The same is true of
the 2026-09-10 amendment: it adds globs to a table and reads files that
already existed. `formal/eqy/out/` is git-ignored build output, not the
frozen `formal/` sources.

**One thing outside these three files is now stale because of this
change, and it is not fixed here.** `docs/34` section 4's list of
corrections refers to "`docs/80`'s digest row for `pilot-signoff`". That
group is called `pilot-signoff-superseded` as of 2026-09-10, and the
metric it was cited for — `stdcell_um2=191588;util=0.487516` — is now
carried by **all four** pilot rows, current and superseded alike **[fact,
`grep -c`, 4 matches]**. `tt/README.md` and `scripts/gen_tt_submission.py`
cite the same figure by its value rather than by the group name and are
unaffected. Section 13.3.

---

## 11. Reproducing this

```bash
# the manifest, on a machine that has the run tree
python3 scripts/artefact_digests.py --write

# re-verify. On a clone this reports 329 MISSING and exits 0
python3 scripts/artefact_digests.py --check

# what is pinned, group by group, and what is on disk here
python3 scripts/artefact_digests.py --list

# the cross-check of section 6.1 against docs/75 section 3.2
md5sum hw/soc/pnr/runs/s71boot/final/nl/soc_top.nl.v

# the identity results of section 6.2 and 6.3, straight out of the file
awk -F'\t' '$4~/(s70boot2|s71boot|s76gate|s77base)\/final\//{print $6"  "$4}' \
    docs/80-artefact-digests.tsv | sort

# section 6.4: the four pilot runs, one digest per artefact kind.
# nl, pnl and def collapse to one value each across all four
awk -F'\t' '$1~/^pilot-(signoff|submission)/{split($4,q,"runs/"); \
    printf "%-12s %-30s %s\n", $3, q[2], substr($6,1,16)}' \
    docs/80-artefact-digests.tsv | sort -k1,1

# every headline number of paper section 8, out of the manifest alone
awk -F'\t' '$2=="paper8"{print $4"\n    "$7}' docs/80-artefact-digests.tsv \
  | grep -B1 -E 'boxes=|items=|result=|closes_at=|period_min='

# section 13.4's coverage comparison: every git-ignored artefact path
# `paper/claims.yaml` cites must resolve to a row in the manifest.
# Prints 19 OK and one MISS -- `hw/openlane/replica_placement.py`, a
# tracked script rather than an artefact. THIS IS NOT A TEST. Nothing
# runs it; it is what section 12 item 5 asks to be made into one.
python3 - <<'PY'
import re, fnmatch
pinned = {l.split("\t")[3] for l in open("docs/80-artefact-digests.tsv")
          if not l.startswith("#") and len(l.split("\t")) == 7
          and not l.startswith("group")}
IGN = ("hw/soc/pnr/runs/", "hw/soc/out/", "hw/openlane/", "formal/eqy/out/")
cited = {t for m in re.finditer(
             r'(?:artefact|file|paths|cmd|pattern):\s*"?([^"\n]+)',
             open("paper/claims.yaml").read())
           for t in re.findall(r'[\w./*-]+', m.group(1)) if t.startswith(IGN)}
for c in sorted(cited):
    hits = [p for p in pinned
            if p == c or p.startswith(c.rstrip("/") + "/")
            or ("*" in c and fnmatch.fnmatch(p, c))]
    print(("OK   " if hits else "MISS "), c, f"({len(hits)} row(s))")
PY

# section 13's swap test, which must print CHANGED and exit 1
D=hw/soc/pnr/runs/s77lvs-d-delimiters/01-netgen-lvs/reports/lvs.netgen.rpt
E=hw/soc/pnr/runs/s77lvs-e-normalised/01-netgen-lvs/reports/lvs.netgen.rpt
cp -p "$D" /tmp/d-backup && cp "$E" "$D"
python3 scripts/artefact_digests.py --check --quiet   # 1 changed, exit 1
cp -p /tmp/d-backup "$D"
python3 scripts/artefact_digests.py --check --quiet   # 329 verified, exit 0
```

---

## 12. What the next block should be

1. **A test that runs `--check`.** Section 5 says nothing does. It
   belongs in `sw/tests/`, it must skip-or-pass on MISSING and fail on
   CHANGED, and it should assert that the manifest still names the
   artefacts the documents cite — a manifest that quietly loses a row is
   the same hole one level up.
2. **Widen the selection, or state the boundary in each document.**
   `docs/47` through `docs/73` rest on unpinned artefacts. Either they
   get pinned or each of those documents should say that its evidence is
   unsealed. The second is cheaper and more honest than pretending the
   line drawn here was principled rather than practical.
3. **The masking GDS comparator.** Section 4.3 is a limitation with a
   known fix: `docs/71` section 14 already describes the comparator, and
   moving it into the tree would let the manifest carry a second digest
   per GDS — of the masked stream — that means *this geometry* rather
   than *this file*.
4. **Decide whether the artefacts are published at all.** A digest that
   no reader can ever redeem is a promissory note. The pilot sign-off
   GDS is 20.8 MB and would fit anywhere; the six SoC layouts would not.
   `docs/78`'s mirror carries no artefacts today and this document does
   not propose that it should — but the question is now stated, which it
   was not before.
5. **A check that the manifest still covers what is cited.** Added
   2026-09-10 and it is now the first item on this list, not the fifth.
   Items 1 to 4 are all about making the seal stronger; section 4.5 is
   about the seal being on the wrong box, and **no amount of item 1
   would have caught it**. What is needed is small and mechanical: walk
   `paper/claims.yaml` for every `artefact:`, `file:` and `paths:` value
   under a git-ignored directory, walk the documents for
   `hw/soc/pnr/runs/…` and `hw/soc/out/…` paths, and fail if any of them
   is absent from `docs/80-artefact-digests.tsv`. It is roughly forty
   lines. Section 13.4 says what it would have caught on 2026-09-09 and
   what it still would not.
6. **Decide what `pilot-signoff-superseded` is for.** It is retained
   because `docs/32` and `docs/79` measured it, and because `docs/64`
   says a superseded measurement stays. But a ledger that only ever
   grows by retention becomes a ledger nobody reads. There is no policy
   here for when a superseded row may leave, and `--write --allow-shrink`
   is the only mechanism, which is a blunt one.

---

## 13. The 2026-09-10 amendment: what was not sealed, and what was sealed under the wrong name

This section exists because the two defects it records are exactly the
kind this document was written to prevent, and it did not prevent them
on itself. Section 4.5 is the general statement; this is the particulars.

### 13.1 The paper's section 8 rested on sixteen unpinned run trees

`paper/main.tex` section 8 is the part of the paper that a reader is
least able to re-derive and most likely to want to: a seventeen-hour
Magic DRC, a KLayout deck, a Netgen LVS search, a 2x2 timing repair and
an independent static-timing sweep. Every one of those lives in
`hw/soc/pnr/runs/`, which `.gitignore:118` ignores. Seventeen
directories: three deck runs, two bare-macro calibrations, seven LVS
variants, three repair layouts, the OpenSTA sweep and the
`magic-drc-inputs` tree that holds the classifier. An eighteenth piece
of evidence, the slow-corner STA step of `s77gate`, sits inside a run
whose `final/` was pinned and whose step directories were not.

`paper/claims.yaml` said so, and said what followed from it:

> the run directories are gitignored build output, so these are pinned
> by digest in `docs/80` and read from the run's own metrics here

**They were not pinned by digest in `docs/80`.** Of the 149 rows written
on 2026-09-09, not one was in any of the seventeen directories. The
strongest numbers in the paper — `0` error boxes outside the vendor
macros, `Circuits match uniquely` — were the only significant numbers in
the corpus with no seal at all, and a file in the repository asserted
the opposite.

Eight groups and 156 rows now cover them, and 24 more went to the pilot
and `equiv-79` for the reasons in 13.2 and 13.4:

| what section 8 says | where it now is |
|---|---|
| 39,969,214 boxes, **0 outside**, 0 straddling, 0 outside the die | `deck-magic-soc`, in the metrics of `s77gate-drc-full/classification.txt` and re-readable from the 1.7 GB report beside it |
| the classifier reproduces the earlier single-macro report's 1,106,478 | **not pinned.** That report is from an earlier experiment and is not in the manifest — see "what this still does not cover" below |
| the classifier itself, and the four scripts that drove the decks | `deck-inputs`. `classify.py` is 5,620 bytes and was unpinned; a deck number whose classifier can be edited is not a measurement |
| the abstraction whose obstruction rectangles caused the 123 | `deck-inputs`, `maglef/RM_IHPSG13_1P_2048x64_c2_bm_bist.mag` and its 1024x32 sibling |
| 8,808,860 and 2,210,913 boxes for the bare macros | `deck-magic-bare`, in the two `magic-drc.log` rows |
| 123 boxes from the abstracted run, all artefacts | `deck-magic-soc`, `s77gate-drc-abstract/classification.txt`: `boxes=123;…;drawn_outside=103` |
| 9,668 KLayout items in 3 of 173 rules, every one naming a vendor cell | `deck-klayout`, `items=9668;rules_declared=173;rules_fired=3;base_cells=60;outside_macro=0` |
| the positive control returns its deliberate violations | `deck-klayout`, `control/ctrl.lyrdb` and `control/ctrl.gds` and the script that built them |
| **Circuits match uniquely**, 62,256 devices, 61,912 nets | `lvs-77`, and so are the **four variants that did not match** |
| the four `period_min` values 24.68 / 25.21 / 23.36 / 23.03 | `sta-slow-corner`, one `clock.rpt` per arm |
| 3,088 violating endpoints, worst slack −4.6799 | `sta-slow-corner`, `violator_list.rpt` and `wns.max.rpt` |
| closes at 25 ns, and the repaired arms at 24 | `sta-compare-81`, `closes_at=25.00` and `closes_at=24.00` |
| −5.2145 / −3.3554 / −3.0306 for the three repair arms | `soc-timing-factorial`, each arm's `final/metrics.json` |

**The four failing LVS variants are pinned deliberately and they are the
part of this worth arguing about.** A manifest that sealed only
`s77lvs-b-blackbox` would let a reader verify the result and not the
search: it would show that *a* configuration matched uniquely and hide
that six were tried, that four failed, and that the one which matched
did so by abstracting the macros rather than by loosening the
comparison. Pinning the failures costs 204 MB and is the difference
between publishing a result and publishing an experiment.

### 13.2 The ledger sealed a submission tree that had been superseded for nine days

`docs/34` section 3.1 carries four checksum blocks. Two are headed
**CURRENT** — `signoff-6x2-gated` and `submission-6x2-gated` — and two
are headed **SUPERSEDED 2026-08-31**, which is the day `docs/36` bound
`MAX_CAP_VIOLATION_CORNERS` and `MAX_SLEW_VIOLATION_CORNERS` to `['*']`
and the freeze moved to the re-hardened pair.

The 2026-09-09 manifest had one pilot group. It pinned `signoff-6x2` and
described it as *"the frozen pilot sign-off harden. docs/34 freezes
it"*. That sentence was false when it was written: what `docs/34`
freezes is `signoff-6x2-gated`, and what goes to the shuttle is
`submission-6x2-gated`, neither of which the manifest had heard of.

**No digest was wrong.** Every one of the five pinned values still
verifies against `docs/34` section 3.1's superseded block, character for
character, and `--check` never had anything to complain about. The
defect was one level up: the ledger sealed a real file under a label
that said it was the current one.

What was done, and why it is retention rather than replacement:

- `pilot-signoff-gated` and `pilot-submission-gated` are new, and are
  the two runs `docs/34` calls CURRENT;
- `pilot-signoff` was **renamed** `pilot-signoff-superseded` and
  `submission-6x2` added as `pilot-submission-superseded`. The word is
  in the group name rather than only in the script's prose, because the
  `.tsv` is what a reader greps and the `.py` is not;
- **the superseded rows are kept.** `docs/64`'s rule is that a
  superseded measurement is left standing with a dated marker, and there
  is a second reason here: `docs/32` ran gate-level fault injection on
  `signoff-6x2`'s netlist and `docs/79` section 1.2 measured replica
  placement from `signoff-6x2`'s DEF. Those documents are about that
  run. Dropping its digest would unseal two documents to tidy up a
  label;
- all four now pin **six** artefacts rather than five, adding
  `final/pnl/`, because `docs/34` section 3.2's argument is about the
  netlist, the powered netlist **and** the DEF being bit-identical
  across runs, and a manifest carrying two of the three could not
  express it. Section 6.4 is what that bought.

### 13.3 One consequence outside these files, stated rather than fixed

`docs/34` section 4 refers to "`docs/80`'s digest row for
`pilot-signoff`" as the thing that had carried `191,588 um2` and
`48.7516 %` all along. There is no group of that name as of 2026-09-10.
The figure itself is unaffected and is now carried by four rows rather
than one — `stdcell_um2=191588;util=0.487516` appears in the
`final/metrics.json` row of every pilot run, current and superseded
**[fact, `grep -c`, 4 matches]** — so the sentence needs a name changed
and nothing re-measured. It is `docs/34`'s sentence and is not edited
here.

`tt/README.md` and `scripts/gen_tt_submission.py` cite the same figure
by value rather than by group name and are unaffected.

**And at commit `cf2ece6`, `docs/34` section 4's own manifest hash was
stale by one revision.** That section pinned `tt/MANIFEST.sha256` at
`8d8988a12ad321f8314f9f2a68c94b7681f69f9da2ce8d5876a067f4ade5b07c` and
said the tree was **29 files**, while `git show
HEAD:tt/MANIFEST.sha256 | sha256sum` at that commit gave
`b9068f6ae359ca96f87d254e2f72557e1366e9df6591bbdfd67ec8f207834df3` over
**30** entries **[fact, `git show`, `sha256sum`, `wc -l`]**. The pinned
value was the **pre-SPDX** one: `git show 4c07d8d:tt/MANIFEST.sha256 |
sha256sum` reproduces `8d8988a1…` exactly. Commit `13402ad` added the
licence headers, replaced `LICENSE.PENDING.md` with `LICENSE` and
`LICENSES/Apache-2.0.txt`, and regenerated the manifest; its own message
says the freeze was re-pinned and the superseded values retained, and
section 4's self-hash was the one thing missed. `sha256sum -c` passed on
all 30 files throughout, so nothing was ever broken — the document's pin
was one revision behind its own tree.

**`docs/34` has since repaired it, in the same working tree and by its
own owner rather than by this document.** Section 4 now carries the
whole chain — `f3a68f9d…` at 31 files as current, with `b9068f6a…`
(30), `8d8988a1…` (29) and `0cea3939…` (29) retained beneath it and each
dated — which is the same rule this section 13 is applying to the pilot
runs, arriving from the other direction. **`docs/80` pins nothing under
`tt/`, because `tt/` is tracked in git and a digest ledger for tracked
files is what git already is**, so this ledger did not catch it and
could not have. It was found by reading the two documents side by side,
which is the method section 13.4 says has no mechanism behind it.

### 13.4 What would have caught these, and what still would not

A test that runs `--check` — section 12 item 1, written on 2026-09-09 —
would have reported 149 verified and exit 0 every day of the nine.
Neither defect is visible to it, and saying so is the point: *the
question is never whether the check passed, it is what the check could
have seen.*

What would have caught 13.1 is a forty-line comparison of
`paper/claims.yaml` against `docs/80-artefact-digests.tsv`. Every
artefact path in `claims.yaml` under a git-ignored directory should
resolve to a row in the manifest. As of 2026-09-10 **all 19 do** — the
comparison is written out in section 11 and its one non-match is
`hw/openlane/replica_placement.py`, which is a tracked script rather
than an artefact. Five of the 19 were found missing by exactly this
comparison while writing this section: the `formal/eqy/out/*.log` files
that `claims.yaml` names as the evidence for `eqy.modules_proved` and
`eqy.controls_fail`, pinned now under `equiv-79`. **Nothing enforces
any of it**; it was run by hand, once.

What would have caught 13.2 is harder and is not proposed as a
mechanism: it needs the manifest to know that `docs/34` labels one of
its runs SUPERSEDED, which means parsing prose. **The honest answer is
that 13.2 was caught by a person reading `docs/34` section 3.1 beside
the group table**, that this took about ten minutes, and that nothing in
this repository would have prompted anyone to do it.

**What is still not covered, and is the nearest thing to 13.1 left
standing:** the paper's classifier-validation claim — *"run against the
retained report of the earlier single-macro experiment it returns
1,106,478 boxes"* — names a report that is in none of the sixteen
directories and is not in this manifest. It is the one number in section
8's four-part argument for the deck that has no pinned artefact behind
it.
