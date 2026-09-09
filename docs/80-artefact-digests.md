# 80 — The evidence is not in git, so its identity is: 149 artefacts pinned by SHA-256, and what that does not prove

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

**149 artefacts, 1.91 GB, pinned by SHA-256 in a 34.8 kB tracked file**
**[fact, 2026-09-09]**. Sixteen groups, each naming the documents that
rest on it. Each row carries the path, the size in bytes, the digest, and
a handful of metrics read out of the artefact itself so that the row is
legible to someone who cannot open the file.

**`--check` re-verifies against the working tree and distinguishes
MISSING from CHANGED**, which is the whole design of it: a fresh clone
has none of these files, reports 149 MISSING, and **exits 0**. Only a
file that is present and hashes differently is a failure.

**And it is one line of arithmetic wide.** The retained run tree on this
machine is **139 GB** — 36 SoC place-and-route runs, 37 pilot hardens,
302 build directories under `hw/soc/out/` **[fact, `du -sh`]**. This
manifest pins **1.4 % of it**, chosen by reading the documents for the
paths they actually rest on. Section 5 lists what that leaves out.

> **A DIGEST PROVES IDENTITY, NOT CORRECTNESS.** It says the file the
> author measured is the file the author still has. It does not say the
> file is right, it does not say the measurement was right, and **a
> reader who cannot obtain the artefact cannot check the claim — only
> that the author did not swap it afterwards.** Section 4.

---

## 2. What is pinned

`scripts/artefact_digests.py --write` walks a declared table of groups.
The table is in the script and each entry names its documents; this is
the summary **[fact, 2026-09-09]**:

| group | cites | rows | bytes | what it is |
|---|---|---:|---:|---|
| `pilot-signoff` | 31, 32, 34, 79 | 5 | 37,320,314 | the frozen pilot sign-off harden: `final/` netlist, DEF, GDS, `metrics.json`, `resolved.json` |
| `pilot-shape6x2` | 26, 27 | 5 | 37,370,513 | the 6x2 harden `docs/26`'s gate-level campaign injected into |
| `soc-s70boot2` | 70, 71 | 5 | 190,498,190 | `docs/70`'s boot-hardened layout |
| `soc-s71boot` | 71, 74, 75, 79 | 5 | 190,498,190 | the repeat of it, and **the unrepaired counterfactual** of `docs/75` |
| `soc-s75w9` | 75, 79 | 5 | 192,330,338 | the W9 repair, laid out |
| `soc-s76gate` | 76, 77 | 5 | 193,113,259 | `docs/76`'s clock-gated layout |
| `soc-s77base` | 77 | 5 | 193,113,259 | `docs/77`'s baseline, built to reproduce `s76gate` |
| `soc-s77gate` | 77 | 5 | 193,711,353 | `docs/77`'s split-enable repair |
| `soc-synth` | 71, 74, 75, 77 | 10 | 30,211,450 | five whole-SoC synthesis netlists and their area reports |
| `fi-rtl` | 42, 44, 74, 75 | 8 | 356,054 | the RTL campaigns and the golden runs the gate arms are compared against |
| `gl-74` | 74 | 17 | 163,741,063 | `docs/74`'s map, census and record files |
| `gl-75` | 75 | 15 | 487,240,566 | **the four arms of the two-by-two** |
| `equiv-79` | 79 | 10 | 430,142 | the `eqy` results and both negative controls, gate side extracted from the sign-off run |
| `sim-77` | 76, 77 | 7 | 8,601 | every signal at every edge, two builds one parameter apart |
| `power-77` | 76, 77 | 42 | 78,752 | two layouts, three corners, busy and idle, plus the self-comparison |
| **total** | | **149** | **1,910,022,044** | |

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

---

## 3. What a reader can do with this, in three cases

**Case 1 — the reader has the artefacts** (this machine, or a copy of
the run tree). `--check` is a real check and it is the one that matters:
149 verified, 0 changed, 3.4 seconds **[fact, 2026-09-09]**. If any file
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
readers and it is the case to be honest about. `--check` reports 149
MISSING and exits 0. What they gain is:

- **the shape of the evidence**: 149 files, what kind each is, which
  document rests on which, and how big the whole thing is;
- **the metrics, committed**: the numbers `docs/71` section 5.2 and
  `docs/77` section 9.2 print in prose now sit beside a digest in a
  machine-readable file, so a document that drifts from its own artefact
  can be caught by comparing two tracked files;
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

### 4.5 Two rows are machine-specific by construction

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

- **1.4 % OF THE RETAINED TREE.** 139 GB is on this machine and 1.91 GB
  is pinned. Thirty of the 36 SoC runs, 21 of the 23 pilot `pilot_ihp`
  hardens, all 14 `pilot_sky130` runs and 276 of the 302 `hw/soc/out/`
  build directories are **not** in the manifest. Everything `docs/47`
  through `docs/73` measured — `full3`, `npu2`, `s67`–`s70`, the
  floorplan variants, the CLINT placement probes, the `docs/25` sky130
  work — rests on artefacts nothing pins. The selection was made by
  reading `docs/26`, `docs/31`, `docs/32`, `docs/34`, `docs/71`,
  `docs/74`, `docs/75`, `docs/77` and `docs/79` for the paths they rest
  on. **It is a judgement about which claims are load-bearing, and a
  reader is entitled to disagree with it.**
- **ONLY `final/` AND `resolved.json` OF EACH RUN.** The 62 step
  directories are not pinned. That matters more than it sounds:
  `docs/71` section 5.2 calls the ten per-iteration DRC counts and
  wirelengths **the sharpest evidence in the document**, because they are
  the router's internal trajectory, and they live in step reports this
  manifest does not touch. `final/metrics.json` carries the same ten
  values as `route__drc_errors__iter:N`, so they are pinned as numbers;
  the step artefacts they were computed from are not.
- **NOTHING RUNS `--check` AUTOMATICALLY.** There is no test in
  `sw/tests/` that invokes it and `scripts/verify.sh` does not call it.
  So this manifest is a thing a person runs, not a gate, and on the day
  it was written the only protection it offers is against a change nobody
  is looking for. Adding a test is the obvious next step and is stated
  here rather than assumed.
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

## 6. Three things the manifest settled on the day it was written

None of these was the point of the exercise. All three came out of
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

| | |
|---|---|
| artefacts pinned | 149 |
| bytes pinned | 1,910,022,044 |
| bytes committed | 34,808 (the `.tsv`), 0.0018 % of what it pins |
| `--write` | 3.4 s |
| `--check` | 3.4 s |
| files over 100 MB | 10 of 149 |

**[fact, 2026-09-09, this machine, warm cache]**. Both modes are
dominated by hashing. Ten of the 149 files exceed 100 MB -- six GDS
streams and four 161 MB campaign maps -- and the extractors are written
so that neither kind is read twice: the DEF reader stops at `COMPONENTS`
and the map reader stops at `"entries"`. Before that second cut the
whole run took 6.6 s and peaked over a gigabyte of resident memory.

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

---

## 10. Files touched

| File | What |
|---|---|
| `scripts/artefact_digests.py` | new. The group table, the extractors, `--write` / `--check` / `--list` |
| `docs/80-artefact-digests.tsv` | new, generated, tracked. 149 rows |
| `docs/80-artefact-digests.md` | this document |

Nothing under `hw/rtl/`, `tt/`, `formal/`, `hw/openlane/` or `hw/tb/` was
touched; the freeze `docs/34` section 9.3 records is intact, and no test
count moved because no RTL and no harness changed.

---

## 11. Reproducing this

```bash
# the manifest, on a machine that has the run tree
python3 scripts/artefact_digests.py --write

# re-verify. On a clone this reports 149 MISSING and exits 0
python3 scripts/artefact_digests.py --check

# what is pinned, group by group, and what is on disk here
python3 scripts/artefact_digests.py --list

# the cross-check of section 6.1 against docs/75 section 3.2
md5sum hw/soc/pnr/runs/s71boot/final/nl/soc_top.nl.v

# the identity results of section 6.2 and 6.3, straight out of the file
awk -F'\t' '$4~/(s70boot2|s71boot|s76gate|s77base)\/final\//{print $6"  "$4}' \
    docs/80-artefact-digests.tsv | sort
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
