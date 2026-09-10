# 34 — The pilot freeze: the exact artifact set that constitutes the TTIHP26b submission

> **AMENDED 2026-08-31 — the frozen artifact set has moved once, and
> deliberately.** `docs/36-checker-closure.md` applied section 10 item 2:
> `MAX_CAP_VIOLATION_CORNERS` and `MAX_SLEW_VIOLATION_CORNERS` are now
> `["*"]` in all three configurations that build, so the two checkers of
> section 8.5 gate instead of warning. That forced the section 9.2
> re-harden, and the runs this document pins are now
> **`signoff-6x2-gated`**, **`submission-6x2-gated`** and
> **`submission-6x2-gated-geomdecks`**.
>
> **Every superseded hash is retained, marked `SUPERSEDED 2026-08-31`,
> rather than overwritten** — a freeze record that can only be checked
> against now is not a freeze record. Sections 1, 3, 4, 5, 7, 8.5, 9.2,
> 9.4 and 10 carry the amendment; sections 2 and 6 are unchanged and
> still govern. **Section 9.2 item 8 is the one rule that changed** —
> this document was amended in place instead of superseded, and the
> reason is argued there rather than assumed.
>
> **The design did not change.** The re-harden reproduces the superseded
> runs on **196 of 196** and **194 of 194** metrics, and
> `final/nl/*.nl.v`, `final/pnl/*.pnl.v` and `final/def/*.def` are
> **bit-identical across all four runs** **[fact, `docs/36` section
> 5.4]**. What changed is that two more of the flow's own gates are
> load-bearing.

Status: FROZEN at commit `b6738e5`, amended as above. This document
answers one question, and it is written so that the answer can be
checked by running commands rather than by believing prose: **is what I
am submitting the thing that was verified?**

`docs/31-signoff-6x2.md` is the sign-off — what was measured, and what
it means. This document is the inventory — which bytes were measured,
how to confirm the bytes in front of you are those bytes, and what
changing any of them costs. Section 9 is the freeze rule.

Convention, inherited from `docs/18`, `docs/22`, `docs/27` and `docs/32`:
**[fact]** = measured in this environment or read out of an installed
file; **[estimate]** = derived or judged.

Run trees under `hw/openlane/*/runs/` are **gitignored**, so every hash
below is quoted with the run tag and the path it came from. A reader who
does not have the run tree can still verify sections 2, 4, 5, 6 and 8,
which cover everything that is tracked in git; sections 3 and 7 need the
run directories.

**What this document does not do.** It changes no RTL, no testbench, no
formal script and no submission source. Its only executable change is to
`hw/openlane/pilot_ihp/mkconfig.py`, which section 5 explains. Nothing
in it obliges a re-harden. **[Amendment: `docs/36` did oblige one, and
paid it. No RTL moved there either — the netlist is the same bytes.]**

---

## 1. Identity

| Item | Value |
|---|---|
| Freeze commit | `b6738e5` (`ROADMAP.md` P1, `docs/33` merged) |
| Design name | `tt_um_melihakbulut_nssoc` |
| Shuttle | TTIHP26b, ihp-sg13g2, **6x2 = 12 tiles**, deadline **2026-09-21** |
| Die area | `0 0 1289.28 313.74` um, `tt_block_6x2_pgvdd.def` pin frame |
| Sign-off run | **`signoff-6x2-gated`** (`docs/36` section 5) — *SUPERSEDED 2026-08-31: `signoff-6x2` (`docs/31` sections 4–7)* |
| Submission-path run | **`submission-6x2-gated`** (`docs/36` section 5) — *SUPERSEDED 2026-08-31: `submission-6x2` (`docs/31` section 10.4)* |
| Geometric decks for the submission run | **`submission-6x2-gated-geomdecks`** (`docs/36` section 5.3, 5.6) — *SUPERSEDED 2026-08-31: `submission-6x2-geomdecks` (`docs/31` section 10.7)* |
| RTL the runs are pinned to | **`2f6cd6f`**, the freeze content itself — *SUPERSEDED 2026-08-31: `bc91c71` / `0c22de4`, see section 2.2* |

**The two runs are the same design.** The sign-off run was hardened from
`config.signoff-6x2.json`; the submission-path run was hardened from the
configuration the Tiny Tapeout tooling itself derives and hands to
LibreLane. They produce a **bit-identical netlist, powered netlist and
DEF** (section 3.2), which is what licenses `docs/31` to report one set
of numbers for both.

**AMENDED 2026-08-31.** That equality now spans **four** runs, not two:
the two `-gated` runs above produce the same three artifacts, byte for
byte, as the two they supersede **[fact, `docs/36` section 5.4]**. Two
configurations, two dates, four hardens, one netlist.

**One caveat is retired by the amendment.** The superseded runs were
pinned to `bc91c71` / `0c22de4`, so connecting them to this freeze
commit needed section 2.2's comment-only argument. The `-gated` runs are
pinned to `2f6cd6f`, whose `hw/rtl` blobs are the ten in section 2.1
**[fact, `pin_rtl.py` output]**. Section 2.2 is retained as the record
of how the earlier runs were connected; it is no longer load-bearing.

---

## 2. The RTL, pinned by git blob

### 2.1 The ten blobs

Every file in `hw/rtl/` at the freeze commit **[fact,
`git rev-parse HEAD:<path>`]**:

```
5a350525cc48  hw/rtl/aer_fifo.v
fad5e7572ffb  hw/rtl/lif_core.v
af8f65b69645  hw/rtl/npu_regbank.v
f7ff6df7af43  hw/rtl/npu_regs.vh
e2512de1f69a  hw/rtl/pilot_top.v
60ad5696d0a2  hw/rtl/scrub.v
df9de408d4dd  hw/rtl/secded_dec.v
36c294ea08d1  hw/rtl/secded_enc.v
e52580002bf6  hw/rtl/tmr_voter.v
c554cb817fbb  hw/rtl/tt_um_melihakbulut_nssoc.v
```

To check a working tree against this list:

```bash
for f in hw/rtl/*; do echo "$(git hash-object "$f" | cut -c1-12)  $f"; done
```

**AMENDED 2026-09-09. Every one of the ten blobs above moved, and the
netlist did not.** `docs/14` section 11 was signed and stage 1 of its
section 9 added two SPDX comment lines to every file in `hw/rtl/`. That
is the case section 9.3 covers, and section 9.2's amendment rule is why
this record is amended rather than superseded: **the built artifacts of
section 3 are unchanged, so their inventory is not split across two
documents.** The superseded list, which is the list `docs/31` hardened
from and every run record from `docs/15` to `docs/41` cites:

```
25c86327f3c5  hw/rtl/aer_fifo.v          89e62789ad01  hw/rtl/scrub.v
ab6dc8b4569b  hw/rtl/lif_core.v          f7c7ec187a0d  hw/rtl/secded_dec.v
e6c1e6466438  hw/rtl/npu_regbank.v       b5710b8a679c  hw/rtl/secded_enc.v
9aaaa394e7a6  hw/rtl/npu_regs.vh         62b5f4d2a1ea  hw/rtl/tmr_voter.v
1874313e1c1b  hw/rtl/pilot_top.v         e294afcf03e1  hw/rtl/tt_um_melihakbulut_nssoc.v
```

**The comment-only claim is not taken on this document's word.** Section
2.2's strip-and-compare was run across all ten files, old revision
against new, and every one matched **[fact, 2026-09-09]**. Three of the
ten are a stronger check than the other seven: `aer_fifo.v`,
`lif_core.v` and `pilot_top.v` reproduce
`da858e4be4e71784`, `d83b62b7ca295bdb` and `f15b6f56e3da32cd` — the
exact code digests section 2.2 recorded at the freeze, from the same
command. **The normalisation is therefore the same normalisation**, which
is what makes the other seven digests worth reading.

Two consequences follow and both were discharged in the same change.
`tt/src/` was regenerated so that section 2.3 still holds — checked, no
`DIFFERS` line — and `tt/MANIFEST.sha256` with it. And the three places
outside this document that pin one of these blobs were re-pinned:
`sw/tests/test_soc_regfile_guards.py` for the two codecs and
`sw/tests/test_soc_synthesis_guards.py` for the voter, each keeping its
superseded value beside the new one. **The historical run records were
not edited**: `docs/15`, `docs/18`, `docs/20`, `docs/22` to `docs/28`,
`docs/31` and `docs/41` cite the superseded hashes because those are the
bytes those runs read, and `docs/64`'s rule is that a superseded
measurement is left standing rather than rewritten.

**Seven of the ten are synthesized.** `VERILOG_FILES` lists
`tt_um_melihakbulut_nssoc.v`, `pilot_top.v`, `lif_core.v`, `aer_fifo.v`,
`tmr_voter.v`, `secded_enc.v`, `secded_dec.v`, with `npu_regs.vh` as an
include. `npu_regbank.v` and `scrub.v` are present in the directory and
are **not** in the file list, so they are not synthesized **[fact,
`docs/31` section 1.2]**.

### 2.2 The RTL moved after the sign-off run, and the move is comment-only

The runs were pinned to `bc91c71` (and `0c22de4`, which carries the same
ten blobs). Three files differ at the freeze commit **[fact]**:

| File | at `0c22de4` | at `b6738e5` |
|---|---|---|
| `hw/rtl/aer_fifo.v` | `ba4e5b0d2e0c` | `25c86327f3c5` |
| `hw/rtl/lif_core.v` | `72f4f0af662b` | `ab6dc8b4569b` |
| `hw/rtl/pilot_top.v` | `873b57d3572b` | `1874313e1c1b` |

**These are the `docs/33` rail-header rewrites and they change no code.**
That is not taken on the document's word. Stripping block comments, line
comments and whitespace from both revisions and comparing gives an exact
match on all three **[fact, measured at the freeze]**:

| File | code SHA-256, first 16 hex, **equal at both revisions** |
|---|---|
| `aer_fifo.v` | `da858e4be4e71784` |
| `lif_core.v` | `d83b62b7ca295bdb` |
| `pilot_top.v` | `f15b6f56e3da32cd` |

These three hex values are the output of the exact command below and
have no meaning apart from it — a different whitespace normalisation
gives different digests. **What is load-bearing is that the two columns
are equal**, which any comment-stripping normalisation reproduces.

The check, reproducible against any two revisions:

```bash
strip() { sed -e ':a' -e 'N' -e '$!ba' -e 's:/\*[^*]*\*\+\([^/*][^*]*\*\+\)*/::g' \
          | sed -e 's://.*::' -e 's:[[:space:]]\+: :g' -e 's:^ ::' -e 's: $::' \
          | grep -v '^$'; }
for f in aer_fifo.v lif_core.v pilot_top.v; do
  a=$(git show 0c22de4:hw/rtl/$f | strip | sha256sum | cut -c1-16)
  b=$(git show HEAD:hw/rtl/$f    | strip | sha256sum | cut -c1-16)
  [ "$a" = "$b" ] && echo "$f: code identical ($a)" || echo "$f: CODE DIFFERS"
done
```

**Consequence.** The netlist in section 3 was synthesized from source
whose *code* is the code at the freeze commit. It is a **[fact]** that
the two revisions are textually equal after comment removal; that Yosys
therefore produces the identical netlist is an **[estimate]**, though a
strong one — Verilog comments are discarded by the lexer, and no
attribute in these files is carried in a comment. Nothing in this
repository has re-synthesized `b6738e5` to turn it into a `[fact]`, and
section 9 does not require it.

### 2.3 `tt/src/` carries the same blobs

The submission tree is not a different source. All seven Verilog files
and the include are **byte-identical** to `hw/rtl/` at the freeze commit
**[fact]**:

```bash
for f in tt/src/*.v tt/src/*.vh; do b=$(basename "$f"); \
  [ "$(git hash-object "$f")" = "$(git hash-object hw/rtl/$b)" ] \
  && echo "same: $b" || echo "DIFFERS: $b"; done
```

---

## 3. The built artifacts

### 3.1 Checksums

**[fact, `sha256sum`.]** Paths are relative to
`hw/openlane/pilot_ihp/runs/`.

**CURRENT — `signoff-6x2-gated`, taken 2026-08-31 (`docs/36`):**

```
52b2debf3b2097c1544b2a5ea625675add5ec71a3d3ac9b68dfb5b32d6120989  signoff-6x2-gated/final/nl/tt_um_melihakbulut_nssoc.nl.v
39470ad135125f6b80abaf487877ef81d442ee8dd567bde5ea89ec42995ee73e  signoff-6x2-gated/final/pnl/tt_um_melihakbulut_nssoc.pnl.v
8f99c979c513ab5d9dd2ebb5e72bbf77d28180ac2d7165772664dfe09586fcf4  signoff-6x2-gated/final/def/tt_um_melihakbulut_nssoc.def
1c9f2dd7f65cc248fe8ce2b5856f8a941d0e4cf3f09a0e1ed7df9147eaf98260  signoff-6x2-gated/final/gds/tt_um_melihakbulut_nssoc.gds
274e69513700395332037b27c1964317db278f5cfa75531ea5d8e5346c4dbbcc  signoff-6x2-gated/resolved.json
```

**CURRENT — `submission-6x2-gated`, taken 2026-08-31 (`docs/36`):**

```
52b2debf3b2097c1544b2a5ea625675add5ec71a3d3ac9b68dfb5b32d6120989  submission-6x2-gated/final/nl/tt_um_melihakbulut_nssoc.nl.v
39470ad135125f6b80abaf487877ef81d442ee8dd567bde5ea89ec42995ee73e  submission-6x2-gated/final/pnl/tt_um_melihakbulut_nssoc.pnl.v
8f99c979c513ab5d9dd2ebb5e72bbf77d28180ac2d7165772664dfe09586fcf4  submission-6x2-gated/final/def/tt_um_melihakbulut_nssoc.def
4091b468bcc43313625ffbd5ab66fb47c2e434b0ffd456562958366e7e68c998  submission-6x2-gated/final/gds/tt_um_melihakbulut_nssoc.gds
1a8611663478256ba8bb2c1d6ef96eb25dc9e3cb54863cff5a5c10680cd285bf  submission-6x2-gated/resolved.json
```

**SUPERSEDED 2026-08-31, taken at the original freeze — `signoff-6x2`:**

```
52b2debf3b2097c1544b2a5ea625675add5ec71a3d3ac9b68dfb5b32d6120989  signoff-6x2/final/nl/tt_um_melihakbulut_nssoc.nl.v
39470ad135125f6b80abaf487877ef81d442ee8dd567bde5ea89ec42995ee73e  signoff-6x2/final/pnl/tt_um_melihakbulut_nssoc.pnl.v
8f99c979c513ab5d9dd2ebb5e72bbf77d28180ac2d7165772664dfe09586fcf4  signoff-6x2/final/def/tt_um_melihakbulut_nssoc.def
f5e2e35e1d2faac04fa731c09645aa0ae80045ca137250415a0af311e38ac98b  signoff-6x2/final/gds/tt_um_melihakbulut_nssoc.gds
c280970d1eb1478a0398e7e60aa69af387dac927dc744cd325c58ed76bbe7726  signoff-6x2/resolved.json
```

**SUPERSEDED 2026-08-31 — `submission-6x2`:**

```
52b2debf3b2097c1544b2a5ea625675add5ec71a3d3ac9b68dfb5b32d6120989  submission-6x2/final/nl/tt_um_melihakbulut_nssoc.nl.v
39470ad135125f6b80abaf487877ef81d442ee8dd567bde5ea89ec42995ee73e  submission-6x2/final/pnl/tt_um_melihakbulut_nssoc.pnl.v
8f99c979c513ab5d9dd2ebb5e72bbf77d28180ac2d7165772664dfe09586fcf4  submission-6x2/final/def/tt_um_melihakbulut_nssoc.def
664326bf142635dd14f2b369b9cc8a935123f859f3100886da0f226e220a9372  submission-6x2/final/gds/tt_um_melihakbulut_nssoc.gds
0b73090bf441af7a92e17ea03313631b79f9eef567eee5211418e1a3907c1c5e  submission-6x2/resolved.json
```

**Read the four blocks together and the amendment states itself.** The
netlist, powered-netlist and DEF hashes are **the same three values in
all four runs**. Only the GDS hashes and the `resolved.json` hashes
move: the GDS because it carries a generation timestamp (section 3.2),
`resolved.json` because it now records
`MAX_CAP_VIOLATION_CORNERS` and `MAX_SLEW_VIOLATION_CORNERS` as `['*']`
where it recorded `['']` **[fact]**. **That pair of keys is the entire
difference between the superseded artifact set and the current one.**

### 3.2 What the equality and the inequality mean

**The netlist, the powered netlist and the DEF are bit-identical across
the two runs** — same hash, three artifacts, two independently
configured hardens **[fact]**. This is the strongest single statement in
the freeze: the design the sign-off decks were read against and the
design the submission path builds are the same design, not two designs
that agree numerically.

**The two GDS files differ**, and that is expected: GDS carries an
embedded generation timestamp, so two streamouts of identical geometry
never hash equal. `docs/31` section 10.5 establishes the geometric
equality by the decks rather than by the hash — Magic DRC, KLayout DRC
and the KLayout XOR were all read against `submission-6x2`'s stream in
`submission-6x2-geomdecks` and are all 0 **[fact]**. **The GDS hash is
therefore a provenance record, not an equality criterion**, and a reader
who re-streams will get a third hash without anything being wrong.

`resolved.json` differs because the two runs resolve different
configuration file paths; every functional key that matters is compared
key by key in `docs/31` section 10.

### 3.3 The metrics both runs carry

**[fact, `final/metrics.json` of each; identical values in both.]**

| Metric | Value |
|---|---|
| `timing__setup__ws__corner:nom_slow_1p08V_125C` | **+1.226180081066267 ns** |
| `timing__setup__ws__corner:nom_typ_1p20V_25C` | +8.103343114768531 |
| `timing__setup__ws__corner:nom_fast_1p32V_m40C` | +12.137398096789024 |
| `timing__hold__ws` (worst of three corners) | +0.102949152117101 |
| `timing__setup__tns` / `timing__hold__tns`, all corners | 0 / 0 |
| `magic__drc_error__count` | 0 |
| `design__lvs_error__count` | 0 |
| `route__drc_errors` | 0 |
| `antenna__violating__nets` / `__pins` | 0 / 0 |
| `design__violations` | 0 |
| `flow__errors__count` | 0 |
| `design__instance__count` | 33,564 |
| `design__instance__utilization` | 0.487516 |
| `design__instance__area` | 392,988 um2 |

`klayout__drc_error__count` 0 and `design__xor_difference__count` 0 are
carried by the sign-off run (in-flow) and by the geometric-deck
directory (for the submission stream) **[fact]**.

**AMENDED 2026-08-31.** Every value in the table above is unchanged in
`signoff-6x2-gated` and `submission-6x2-gated`. The comparison was made
key by key rather than row by row: **196 of 196 metrics equal** between
`signoff-6x2` and `signoff-6x2-gated`, and **194 of 194** between
`submission-6x2` and `submission-6x2-gated`, with **zero differences in
either** **[fact, `docs/36` section 5.4]**. Two rows are added, and they
are the point of the amendment — they were carried before and were
gated by nothing:

| Metric | Value | Gated at |
|---|---|---|
| `design__max_slew_violation__count__corner:*` | **0** at all three corners | **all corners** (was: none) |
| `design__max_cap_violation__count__corner:*` | **0** at all three corners | **all corners** (was: none) |

The derate is in the flow-written constraint file, not merely in the
configuration — `final/sdc/tt_um_melihakbulut_nssoc.sdc` lines 100–101
**[fact]**:

```
set_timing_derate -early 0.9500
set_timing_derate -late 1.0500
```

---

## 4. The submission tree

`tt/` is pinned in full by `tt/MANIFEST.sha256`, **31 files**, and the
manifest itself hashes to **[fact]**:

```
f3a68f9d5afaa6fbf674ed9ae1244d2e5dd1f7eb40b649e3433b9b0d08d914de  tt/MANIFEST.sha256
```

**AMENDED 2026-09-10, and the amendment is overdue by a day.** Every
superseded value below is retained; the chronology of this pin is
**[fact, `git show <rev>:tt/MANIFEST.sha256 | sha256sum`]**:

| Manifest SHA-256 | Manifested files | Dated | What moved into it |
|---|---:|---|---|
| **`f3a68f9d5afaa6fbf674ed9ae1244d2e5dd1f7eb40b649e3433b9b0d08d914de`** | **31** | **2026-09-10, current** | `README.md`, `info.yaml`, `docs/info.md`, and `LICENSES/CERN-OHL-W-2.0.txt` added |
| `b9068f6ae359ca96f87d254e2f72557e1366e9df6591bbdfd67ec8f207834df3` | 30 | 2026-09-09 | `docs/14` stage 1: the SPDX header on every file in `src/`, `LICENSE.PENDING.md` out, `LICENSE` and `LICENSES/Apache-2.0.txt` in |
| `8d8988a12ad321f8314f9f2a68c94b7681f69f9da2ce8d5876a067f4ade5b07c` | 29 | 2026-08-31 | `docs/36`'s two keys into `src/config.json` |
| `0cea3939f4cc03ff98162602892bbfc5760fe6ce7855a27a7c8cd64e904ba747` | 29 | before 2026-08-31 | — |

**The 2026-09-09 row was never written into this section**, and that is
the part worth stating plainly rather than quietly correcting. Section
2.1 was amended that day, `tt/src/` was regenerated that day, and this
section went on pinning the pre-SPDX tree — so from 2026-09-09 the
section 9.4 procedure, which is this document's own mechanical answer to
"is what I am submitting what was verified", **failed on its own two
`sha256sum` lines** for anyone who ran it. The manifest was right; the
record of it was a day stale. A pin that is only sometimes maintained is
worse than no pin, because it is read as verification.

What moved on 2026-09-10, and nothing else did **[fact, `git diff --stat
-- tt/`]**:

| File | Now | Superseded 2026-09-10 |
|---|---|---|
| `tt/README.md` | `c1c0d15135a43c05421e23156eef2bf5751ad4c5b11633342cc275d080370840` | `87faee259c44eb6273c82337fc8fb52851cf8d103d711e0687fb3018a91f7b09` |
| `tt/info.yaml` | `dc230e13b33ef4e33d8b23c0e048ecb12daf6529f8b0e9a87f7c2d1904ff27d6` | `55a701b8d232a969886279ef0aada43bede71ce02e48956b5829429c091bbab0` |
| `tt/docs/info.md` | `408d3f3b27a2f6dfeca9468de91b0842761af0c9f1abcc927865f9211f85500a` | `7f714dc5dc63931c0323a64c51868c257ca0feeee935ade700cf66ec72423f2a` |
| `tt/LICENSES/CERN-OHL-W-2.0.txt` | `c1432111d0aeefc9d1ced8105d2d4ed07d5dcb1fd43abb5d4616c4f9ef96e08f` | did not exist |

Four defects, all in prose and one in a missing licence text, none in
the netlist path:

1. `tt/README.md` claimed `src/config.json` was byte-identical to
   upstream and named `--diff-template` as the proof. It has carried the
   appended `CONFIG_OVERRIDES` keys since 2026-08-26 — **this section
   says so two paragraphs down** — and `--diff-template` compared the
   generator's recorded copy of the upstream file rather than the built
   one, so the named proof could not have seen the difference. The claim
   is corrected and the comparison now runs against the built bytes.
2. `tt/README.md` and `tt/info.yaml` quoted 185,840 um2 and 47.29 % —
   the `docs/23` tile-shape A/B run, superseded by `docs/27` and then by
   the frozen `signoff-6x2`. Both now carry **191,588 um2** and
   **48.7516 %**, which is what section 3.3 above, `docs/31` section 6
   and `docs/80`'s digest rows for the pilot sign-off have carried
   all along. *(Group renamed 2026-09-11: the digest groups are
   `pilot-signoff-gated` and `pilot-signoff-superseded`, split when
   `docs/80` was re-measured; there is no group called
   `pilot-signoff` any more, and this sentence named one.)*
3. `tt/LICENSES/` held `Apache-2.0.txt` alone while every file in
   `tt/src/` carries `SPDX-License-Identifier: CERN-OHL-W-2.0`, so the
   published repository did not resolve its own tags. The text is now
   emitted at `tt/LICENSES/CERN-OHL-W-2.0.txt` as well as at `LICENSE`.
4. `tt/docs/info.md` told an operator that `FAULT_CLR` = `0x3F` clears
   everything and listed three pilot-only registers. The die decodes
   five and allocates clear bits 6 and 7, so that write clears six of
   eight counters and the two it leaves — `CNT_EVQ_OUT_OVF` and
   `CNT_EVQ_PAR` — are then read as live. `regmap/regmap.yaml` was
   corrected for this on 2026-09-09; the datasheet did not follow
   because the mask and the register list were typed into
   `scripts/gen_tt_submission.py` by hand and nothing compared them to
   anything. They are now read from `regmap/regmap.yaml` and from the
   `SA_*` and `PILOT_BIT_FAULT_CLR_*` constants in
   `hw/rtl/pilot_top.v`, and the generator exits non-zero if the three
   disagree.

**No re-harden is owed, and the reason is the same one section 9.3
gives.** Nothing under `tt/src/` moved: `git diff --stat -- tt/src` is
empty, the ten blobs of section 2.1 are untouched, and section 2.3 still
reports no `DIFFERS` line. The four files that moved are `README.md`,
`info.yaml`, `docs/info.md` and a licence text — none of them is read by
Yosys, LibreLane or the `gds` action, and `info.yaml`'s only functional
fields (`tiles`, `top_module`, `source_files`, `clock_hz`, the pinout)
are byte-for-byte what they were; only a comment block moved. The
netlist equality at the end of section 9.4 was re-run all the same and
all four paths still print
`52b2debf3b2097c1544b2a5ea625675add5ec71a3d3ac9b68dfb5b32d6120989`
**[fact, 2026-09-10]**.

*SUPERSEDED 2026-08-31, retained:
`0cea3939f4cc03ff98162602892bbfc5760fe6ce7855a27a7c8cd64e904ba747`.
Exactly two of the 29 manifested files moved, and only one of them by
content: `src/config.json` gained the two `docs/36` keys, and the
manifest line for it changed with it **[fact]**.*

| File | Now | Superseded 2026-08-31 |
|---|---|---|
| `tt/src/config.json` | `56d3738469a2cfaecfed57dc4901e66df2c90b657f08ee54b6fbb5ffc04c9407` | `0cfb05a9c3367f0a8f3012554b3fe694b5adfe546dff728deb9dc3b4f15c2c0b` |

*That row still holds: `src/config.json` did not move on 2026-09-09 or
on 2026-09-10, and `56d37384…` is its line in the current manifest
**[fact]**.*

Verified 2026-09-10: **31 of 31 OK, exit 0**, and
`gen_tt_submission.py --check` reports `tt/ matches the generator (32
files)` **[fact]**. *Superseded 2026-09-10: verified 2026-08-31, **29 of
29 OK, exit 0**, `tt/ matches the generator (30 files)`.*

`gen_tt_submission.py --check` reports **32 files**, not 31, and the two
numbers do not contradict: the generator's set is the 31 manifested
files **plus `MANIFEST.sha256` itself**, which it writes last from the
other 31 **[fact, `scripts/gen_tt_submission.py`]**. `src/user_config.json`
and `src/config_merged.json` are produced by the Tiny Tapeout tooling
rather than by this generator and are in neither count.

```bash
cd tt && sha256sum -c MANIFEST.sha256
sha256sum tt/MANIFEST.sha256
python3 scripts/gen_tt_submission.py --check   # tt/ matches the generator
```

`tt/src/config.json` is the file the shuttle's `gds` action reads. It
carries all six recovery keys **[fact, `docs/31` section 10.1]** —
`TIME_DERATING_CONSTRAINT` as the float `5.0`, `SETUP_VIOLATION_CORNERS`
`["*"]`, `PNR_CORNERS`, `RUN_POST_GRT_RESIZER_TIMING`,
`RUN_POST_GRT_DESIGN_REPAIR` and `GRT_RESIZER_SETUP_SLACK_MARGIN` — all
under the `"Added by scripts/gen_tt_submission.py:"` marker. This is the
single most consequential line item in the freeze, because `docs/31`
section 2 measured what happens without them: **-0.7696 ns at the slow
corner, reported as clean.**

**AMENDED 2026-08-31: it carries eight keys, not six.**
`MAX_CAP_VIOLATION_CORNERS` and `MAX_SLEW_VIOLATION_CORNERS`, both
`["*"]`, were added under the same marker by `docs/36`. They are
deliberately not counted among the six: the six buy timing margin, these
two buy none — they make two checkers able to fail. The file the
shuttle's `gds` action reads therefore now gates max cap and max slew at
every corner **[fact]**, and so does `tt/src/config_merged.json`, which
is the file the tooling actually hands to LibreLane.

---

## 5. The flow configuration, and the generator that writes it

### 5.1 The pinned set

`hw/openlane/pilot_ihp/mkconfig.py` derives six configs from
`tt/src/config_merged.json`. All six are frozen and their bytes are
recorded **inside the generator** as of this document **[fact]**:

```
274cc337d5147eb8ca3ac71eddd535f0d1b75ae137bcdfc04594149da3f4c1a8  config.json          <- MOVED 2026-08-31
02e10806e47085484f8352909ea4dd8b43183f0d2ed78c098be16f714805c248  config.6x2.json
205ecf4ffe7fedd40ec6935999cc3abe2990070e1b55f100758050f7ef98f86f  config.3x4.json
f36e11436a57c2b29128d40c04abfb1c72be502db5d45814f61b63d6d8b7c7ce  config.pnrcorners.json
297779e2e1d7a1e48583e2761571c6abb6a1a470968529281d3cc1a01be96f3c  config.flatten.json
ab81ff37f1e693e840542660a4b1586d6dc94ae0d893fc28125111bfd52df9b4  config.klayoutdrc.json
```

*SUPERSEDED 2026-08-31, `config.json` only:
`57295633ffc5a976e0a42e8307dc80e1f91efea31c5cce4c6aa045d32bad2a66`,
the bytes run `signoff-6x2` was hardened from. **The pin was lifted for
exactly one edit and re-taken**, and the superseded hash is also kept in
`mkconfig.py`'s own `PINNED` table beside the reason, so the record
survives without this document. The other five are untouched and
`--check` still matches all six **[fact]**.*

`mktiming.py` derives eight more from `config.json` and
`config.6x2.json`, including **`config.signoff-6x2.json`**, the file the
sign-off run was hardened from. Its bytes moved with the base
**[fact]**:

```
e7676a2dae3888f668b53f7e3a43eb7ae2d04db660b02529964b68c2df508bff  config.signoff-6x2.json
```

*SUPERSEDED 2026-08-31:
`cb8c804dd4b7824e1639e710440550a9d92092d90f2a13fc8cec55483ccb79e3`.
Seven lines added — the two keys and the `//capslew` annotation — and
nothing else. **The seven `config.tr-*.json` variants were rewritten by
the same command and came back byte-identical**, because their base
`config.6x2.json` did not move **[fact]**.*

One config outside the six also moved, and is recorded here because
section 9.2 covers it: `hw/openlane/pilot_sky130/config.json`, now
`cb07c80f806ffeb20729b8557c67eae746de308ac9ec994239825dda2ce83df6`,
*superseded 2026-08-31:
`0d5690aec322cd43415b13e8e3a14b049d6c53062da28de9b5c9c391f714a195`*. It
builds nothing on this shuttle; `docs/36` section 4 is why it changed and
why a sky130 harden is now expected to fail.

Both generators self-check:

```bash
python3 hw/openlane/pilot_ihp/mkconfig.py --check    # exit 0
python3 hw/openlane/pilot_ihp/mktiming.py --check    # all 8 variants match
```

### 5.2 Why `--check` used to report six drifted files, and what was done

`docs/31` section 10.8 recorded six drifted files and judged the drift
benign. It was benign, and it was still a defect in the gate: a `--check`
that reports six failures nobody is expected to act on is not a gate.

The cause **[fact]**: `mkconfig.py` copies `tt/src/config_merged.json`
through. When `docs/31` section 10.1 put the six recovery keys into that
file, the *derivation* of all six targets grew those keys while the
*files on disk* — each generated earlier, each the recorded input of a
run — did not. Nothing had been edited. The source had moved underneath
six frozen artifacts.

Re-deriving them was not available, because each is load-bearing:

| File | Recorded input of | What re-deriving costs |
|---|---|---|
| `config.6x2.json` | run `subpath-6x2` (`docs/31` §2.2); `mktiming.py`'s base for all seven `tr-*` variants | The **control** that measures the un-fixed submission path. Regenerated, it carries all six keys and reproduces the *fixed* configuration — `docs/31` §2.2's -0.7696 ns becomes unreproducible from the file that names it. Also drifts all seven `tr-*` variants at once. |
| `config.3x4.json` | run `shape-3x4` (`docs/23`) | `docs/23` attributes its deltas to the tile shape *because* the two shape configs differ in two keys and nothing else. |
| `config.pnrcorners.json` | run `ihp-pnrcorners` (`docs/20` §5) | The derivation would add `PNR_CORNERS` to the baseline side — the one key the A/B exists to isolate. |
| `config.flatten.json` | run `ihp-synth-flatten` (`docs/20` §3) | Synthesis-only probe; its numbers are quoted against this exact base. |
| `config.klayoutdrc.json` | runs `ihp-klayoutdrc`, `ihp-klayoutdrc-w5` (`docs/20` §11, `docs/22`) | "Identical apart from `RUN_KLAYOUT_DRC`" is the whole claim. |
| `config.json` | `mktiming.py`'s base for `config.signoff-6x2.json` | See 5.3. |

**The fix: each target now declares its status.** A *pinned* target is
verified by SHA-256 rather than by re-derivation, is skipped by the write
mode, and has its provenance and its reason recorded beside the hash.
A *derived* target keeps the original byte-diff rule. Today all six are
pinned. `--check` additionally prints, for every pinned file, the exact
key delta the current source would introduce, so the divergence stays
**named** instead of becoming invisible:

```
pinned  config.6x2.json  (source delta: would ADD GRT_RESIZER_SETUP_SLACK_MARGIN = 0.5; ...)
OK: 6 pinned config(s) match their recorded hash, 0 derived config(s) match tt/src/config_merged.json
```

This is strictly stronger than the old gate in both directions. Before,
a hand edit to any of the six was indistinguishable from source drift —
both printed `DRIFT:`. Now a hand edit prints `PIN-MISMATCH` with the
expected and found hashes and the run the file belongs to, and exits 1;
verified by mutating a pinned file at the freeze **[fact]**. And
re-running the generator can no longer silently undo anything, because
the write mode refuses to touch a pinned file and says why.

`--regenerate-pinned` lifts the pins when the freeze does. It prints
the three things doing so obliges: update the hashes, re-run
`mktiming.py`, and re-harden anything whose numbers are still quoted.

**AMENDED 2026-08-31 — the gate was exercised for real, and it worked.**
`docs/36` needed one of the six changed by hand. The pin caught it, the
hash was re-taken with the superseded value and the reason recorded in
the `PINNED` table, `mktiming.py` was re-run, and the affected run was
re-hardened — which is precisely the three-item obligation the paragraph
above names, paid in that order **[fact]**. The other five never moved.
A pin whose lifting is this legible is doing its job; the case to watch
for is a pin lifted without the re-harden, and the freeze rule of
section 9.2 is what forbids that.

### 5.3 `config.json` is pinned too, and the reason is measured

`config.json` is the subtle case. Its on-disk bytes are stale relative to
the source — the derivation would add the four post-GRT keys — so the
naive reading is that it should simply be regenerated.

It is pinned instead, for a measured reason **[fact, measured at the
freeze by regenerating into a scratch copy]**:

- **Re-deriving `config.json` produces a functionally identical file.**
  Compared as parsed JSON with `//`-prefixed annotations excluded: zero
  keys added, zero removed, zero values changed. The only differences are
  key **order** and the loss of the `//derate` and `//setupcheck`
  annotations, neither of which LibreLane reads.
  **[Amended 2026-08-31: `//capslew` joins the annotations that would be
  lost. The two keys `docs/36` added are in the derivation as well, since
  `tt/src/config_merged.json` now carries them, so they do not appear in
  the delta and the "functionally identical" reading is unchanged
  **[fact, `mkconfig.py --check`]**.]**
- **But `mktiming.py` builds `config.signoff-6x2.json` by copying this
  file's key order.** Regenerating `config.json` and then re-running
  `mktiming.py` changes the bytes of the frozen sign-off config, and
  takes `mktiming.py --check` from `all 8 variants match` to `1 drifted`
  **[fact, measured]**.

So the trade is: no functional gain, against mutating the file the
sign-off run was hardened from. Under a freeze that is not a trade. The
measurement is recorded here precisely so that pinning cannot be
mistaken for concealing a real difference — there is no real difference,
and that is checkable.

---

## 6. Toolchain and PDK

| Component | Version | Where it is pinned |
|---|---|---|
| LibreLane | 3.0.5 | `~/Documents/caravel-lif-crossbar/.venv-flow` |
| ihp-sg13g2 PDK | `c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c` | LibreLane `pdk_hashes.yaml`, asserted by `run_ihp.sh` |
| Yosys (in-flow) | 0.67 | LibreLane wheel (`pyosys`) |
| Yosys (guards, formal, gate level) | 0.67+146 | `OSS_CAD_SUITE` in `tools.mk` |
| oss-cad-suite | `oss-cad-suite-linux-x64-20260804` | `tools.mk`, overridable |
| Magic | 8.3.678 | `~/.local/opt/magic-8.3.678` |
| KLayout (precheck deck) | 0.30.9 | `docs/31` section 10.7 |
| OpenROAD / OpenSTA probes | `~/.local/opt/llbin/` shims | same build the flow uses |

Verified at the freeze **[fact]**:

```bash
make -f tools.mk toolcheck
# yosys version = 0.67+146 (pinned 0.67+146), no mismatch warning
```

---

## 7. Evidence counts as they stand at the freeze

Measured at the freeze unless a document is cited.

| Quantity | Count | How to re-derive |
|---|---|---|
| Python tests collected | **231** (230 before this document; `test_doc_links.py` parametrises per document) | `.venv/bin/python -m pytest --collect-only -q` **[fact]** |
| Python tests passing | **231 passed, 0 failed** | `.venv/bin/python -m pytest -q` **[fact]** |
| — the state this document found | **227 passed, 3 failed.** All three were `test_doc_links.py`, failing because `ROADMAP.md` already cited `docs/34-pilot-freeze.md` and the file did not exist. Creating it closed all three; no test was edited. | **[fact, measured before and after]** |
| Shipped-netlist census guards | **40 passing, 0 skipped**, the five shipped-netlist guards by name — *SUPERSEDED 2026-08-31: this row read **35**, carried from `docs/31` section 7 rather than measured. The file collects 40 at `b6738e5` and is unmodified; the figure had gone stale in the carrying, not in the test* | `.venv/bin/python -m pytest sw/tests/test_synthesis_guards.py -q -rs` **[fact, `docs/36` section 5.5]** |
| cocotb test functions | **166** across 10 modules | `grep -c '@cocotb.test' hw/tb/test_*.py` **[fact]** |
| Formal property sets / tasks | **7 `.sby` files, 45 tasks** (`aer_fifo` 4, `lif_ctrl` 8, `lif_mem` 8, `npu_regbank` 5, `scrub` 9, `secded` 3, `tmr_voter` 8) | counted at `b6738e5`, not in the working tree — see the note below **[fact for the counts; the pass result is not re-run here and is not claimed]** |
| Gate-level functional | **20 of 31 tests run at gate level**, none regressed, one known X-pessimism divergence. Re-run 2026-08-31 against `signoff-6x2-gated`: **19 PASS / 1 FAIL at 2,761,090.02 ns**, and **21 PASS / 0 FAIL at 1,426,700.02 ns** under `GL_PRELOAD=1` — identical to `docs/32` to the nanosecond | `docs/32` section 3; `docs/36` section 5.7 **[fact]** |
| Gate-level fault injection | **561 injections, 370 like-for-like with the RTL campaign, all 370 classify identically** | `docs/32` section 5 |
| Flip-flops in the shipped netlist | **1,296**, census intact | `docs/31` section 4.3, `docs/32` |
| Tiny Tapeout precheck | **10 of 10 pass**, `INFO: Precheck passed`. Re-run 2026-08-31 on `submission-6x2-gated`'s GDS: **10 of 10, exit 0** | `docs/31` section 10.7; `docs/36` section 5.6 **[fact]** |
| `tt/` manifest | **29 of 29 files OK** | `cd tt && sha256sum -c MANIFEST.sha256` **[fact]** |
| Checkers that can fail a run | **17 of the 19 the Classic flow runs** — *SUPERSEDED 2026-08-31: **15 of 19**, before `docs/36` bound max cap and max slew.* The two that still cannot are `Checker.WireLength` and `Checker.LintWarnings`, both dispositioned in `docs/36` section 3.3 | `~/…/.venv-flow/bin/python hw/openlane/checker_audit.py <run>` **[fact, `docs/36` section 3]** |

**A note on where these counts were taken, because it changes one row.**
A concurrent workstream had uncommitted work in `formal/` and
`ROADMAP.md` while this document was written. The formal counts above
are therefore read from **`b6738e5` itself** (`git show b6738e5:<path>`)
rather than from the working tree, which at the time carried an
in-progress `aer_fifo.sby` at 6 tasks and a new `tmr_voter_cfg.sby`
neither of which is committed. Counted in the tree the total reads 47;
**at the freeze commit it is 45**, and 45 is the number this record
pins. The Python-suite result was measured in the working tree, which is
sound because none of the concurrent files is one this freeze pins and
none is collected differently by `pytest`. Every other count in this
table comes from a tracked file or a run directory and is unaffected.

---

## 8. Max fanout: measured, and deliberately left ungated

`docs/31` section 8.2 item 3 and section 10.9 item 1 record 84 max-fanout
violations gated by no checker. This section closes that item by
measuring what the 84 is. **The conclusion is that the gate cannot
honestly be enabled, and the reason is a finding about the flow rather
than a defect in the design.**

### 8.1 What the 84 actually is

`design__max_fanout_violation__count` is **84 at all three corners**, in
`signoff-6x2` and `submission-6x2` alike **[fact, `final/metrics.json`]**.
The violator list is in
`57-openroad-stapostpnr/<corner>/checks.rpt` under `max fanout`, and it
is **identical at all three corners** **[fact]**:

| Class | Count | What it is |
|---|---|---|
| `clkbuf_leaf_<n>_clk/X` | **83** | CTS-inserted clock-tree leaf buffers, fanout 11–19 |
| `u_pilot.u_lif._3564_/Y` | **1** | one logic net, fanout 9 |

**83 of the 84 are the clock tree.** They are not a data path, not a
reset and not a clock enable — they are the leaf buffers CTS built,
each driving 11 to 19 flip-flop clock pins.

**The 84th is an artifact of antenna repair.** The net is
`\u_pilot.u_lif._1166_`, driven by an `sg13g2_nor3_1`. Of its nine
loads, **three are `sg13g2_antennanp` diodes** — antenna-repair cells
that present a pin but no logic **[fact, counted in
`final/nl/tt_um_melihakbulut_nssoc.nl.v`]**. Its **logic fanout is 6**,
under the limit. Of the four antenna cells in the whole design, three
sit on this one net.

### 8.2 The limit is 8, and it does not come from the configuration

Every one of the 84 rows reports **`Limit 8`** **[fact, the report]**.
The configuration's own value is different: the flow-written SDC carries

```
set_max_fanout 10.0000 [current_design]     # final/sdc/...sdc line 105
```

**[fact]**, from `MAX_FANOUT_CONSTRAINT: 10` in `resolved.json`
**[fact]** — which is not a value this project chose but LibreLane's
fallback, applied by `config/pdk_compat.py` because the IHP PDK does not
define the variable **[fact]**. The binding limit is instead the
liberty's

```
default_max_fanout : 8;
```

the **only** `max_fanout` statement in `sg13g2_stdcell_typ_1p20V_25C.lib`
**[fact]**. OpenSTA takes the tighter of the two, so the design-level 10
is never reached.

**Therefore `MAX_FANOUT_CONSTRAINT` is inert in the direction that would
help.** It is already looser than the library default; raising it cannot
lower the count, and lowering it below 8 only raises it. There is no
value of the one configuration key available that reduces 84
**[estimate, and a tightly bounded one: it follows from the three facts
above — the reported limit, the SDC value, and the liberty default]**.
An attempt to turn this into a direct `[fact]` with an OpenSTA probe
over the shipped netlist was abandoned because the available OpenSTA
build segfaults inside `sta::CheckFanouts::check` on this input; the
structural reproduction in 8.3 was done instead.

### 8.3 The count reproduced independently of the tool

Fanout is purely structural — it counts load pins, and depends on no
parasitic and no corner, which is why the number is identical at all
three corners. Counting load pins directly on
`final/nl/tt_um_melihakbulut_nssoc.nl.v`, with pin directions read from
the liberty, over all 33,564 instances **[fact, measured at the freeze]**:

| Threshold | Nets exceeding it |
|---|---|
| > 8 | **84** — reproduces the tool exactly |
| > 10 | 83 |
| > 12 | 80 |
| > 16 | 37 |
| > 19 | **0** |

**The maximum fanout anywhere in the design is 19.**

### 8.4 Why no gate is enabled

**There is no fanout checker to enable.** LibreLane 3.0.5 registers 21
checker steps; none of them reads
`design__max_fanout_violation__count`, and `flows/classic.py` wires up
`Checker.SetupViolations`, `HoldViolations`, `MaxSlewViolations` and
`MaxCapViolations` and nothing for fanout **[fact, read out of the
installed package]**. The metric is emitted by
`scripts/openroad/sta/corner.tcl` and registered as a first-class
aggregated metric in `common/metrics/library.py`; it simply has no
consumer. Adding `Checker.MaxFanoutViolations` is about nine lines
against the existing `TimingViolations` base — but those nine lines are
in the **pinned toolchain**, not in this repository, and patching an
installed LibreLane three weeks before a shuttle would un-pin the one
component every number in `docs/31` is quoted against.

**And if it existed it would fail this design.** `MetricChecker`'s
threshold is 0. A fanout checker at threshold 0 sees 84 and errors.

**The only threshold the design meets is 19, and setting it would be the
`docs/20` section 11 trap verbatim.** 19 is not a design intent; it is
the largest number CTS happened to produce on this run. It would move on
the next harden, and a gate that is re-fitted to the measurement each
time records the tool's behaviour rather than the design's. It is not
set.

**What is true instead, and is the reason this is not a blocker.** Max
fanout is a *proxy* design rule — a cheap stand-in for the transition
and capacitance limits it exists to protect. Those limits are measured
directly on this netlist and are clean: `design__max_slew_violation__count`
**0** and `design__max_cap_violation__count` **0**, at all three corners
**[fact]**. The clock tree the 83 belong to is separately measured
healthy — worst setup skew 0.3499 ns and worst hold skew -0.4132 ns at
the slow corner, against a 20 ns period, with 0 setup and 0 hold
violations at every corner under a real 5 % derate **[fact]**. **The
proxy is violated; the quantities the proxy proxies for are zero.**
Recording that is the honest disposition, and it is why this section
exists rather than a threshold.

One further data point that the flow itself provides: at pre-PnR STA the
count is **275**; post-PnR it is 84 **[fact, `12-openroad-staprepnr`
versus `57-openroad-stapostpnr`]**. Synthesis and design repair do drive
logic fanout down — to exactly one surviving logic net, which 8.1 shows
is an antenna artifact. The 83 that remain were **created afterwards by
CTS**, which optimises for skew and insertion delay and does not consult
the liberty's generic per-cell default.

### 8.5 An adjacent finding: max slew and max cap are not gated either

> **CLOSED 2026-08-31 by `docs/36-checker-closure.md`.** Both keys are
> `["*"]` in all three configurations that build, both checkers gate at
> all three corners, both measure 0, and the re-harden this required
> reproduced the artifact set bit for bit. The section is kept as
> written, in the present tense of the freeze, because it is the record
> of what was true then; read it with that closure in mind.
>
> Two corrections the closure work produced, and they matter to anyone
> reasoning from this section:
>
> - **The mechanism below is described slightly wrong.** This section
>   implies the same shape as the setup defect. It is not. `[""]` is a
>   **non-empty** list, so `get_corner_wildcards()`'s `or` is already
>   satisfied and these two checkers **never consult
>   `TIMING_VIOLATION_CORNERS` at all** — unlike setup, where an unset
>   key let the PDK's value through. The `[""]` comes from
>   `corner_override` in the **step class**, and **neither PDK ships
>   either key** **[fact, `docs/36` section 2.1]**. The practical
>   consequence is that raising `TIMING_VIOLATION_CORNERS` would have
>   been inert; only the per-type key changes behaviour.
> - **A fourth instance of the shape exists**, and this section did not
>   look for it: `Checker.WireLength` runs in every flow here, executes,
>   and gates nothing, because `WIRE_LENGTH_THRESHOLD` is unset in both
>   PDKs. `docs/36` section 3.3 reports it and declines to set it, for
>   the reason section 8.4 above gives about max fanout.

Found while establishing 8.4, and recorded because a freeze record
should not leave it for someone else to rediscover.

`resolved.json` carries **[fact]**:

```
SETUP_VIOLATION_CORNERS = ['*']        <- set by this project (docs/28 4.4a)
HOLD_VIOLATION_CORNERS  = ['*']        <- LibreLane default
MAX_CAP_VIOLATION_CORNERS  = ['']
MAX_SLEW_VIOLATION_CORNERS = ['']
```

`Checker.MaxCapViolations` and `Checker.MaxSlewViolations` both declare
`corner_override = [""]`, and `TimingViolations.get_corner_wildcards()`
filters out the `""` match-none wildcard **[fact, `steps/checker.py`]**.
With an empty wildcard list no corner is *matched*, so a violation lands
in `warn_violating_corner` rather than `err_violating_corner` and the
step **warns instead of failing**.

**This is the third instance of the shape `docs/28` section 4.4a named**
— after setup, and after `docs/23`'s `design__violations` not
aggregating hold. A green checker is only as wide as the corners it was
pointed at.

**It changes no number in the sign-off.** Both metrics are 0 at all
three corners, so the gate's verdict is not in doubt; what is wrong is
that `docs/31` section 4.2 reports the row as "passed" when what
happened is that a checker looked at nothing and found nothing.

**It is deliberately not fixed here.** The one-line fix is
`MAX_CAP_VIOLATION_CORNERS` and `MAX_SLEW_VIOLATION_CORNERS` set to
`["*"]` in the configuration. Unlike the fanout case the design does
meet it — 0 at every corner, which is the same zero criterion every
other deck is held to, so it is not a threshold fitted to the
measurement. But adding it now would change the configuration the
submission builds from, and no run in this repository would have been
built from the changed file: section 9 says that costs a re-harden.
**It is recorded as the first item to apply on the far side of the
freeze** (section 10), where it costs one flow run and buys two real
gates.

---

## 9. The freeze rule

### 9.1 What does not void the freeze

Nothing here touches a byte that section 2, 3, 4 or 5 pins.

- **Documentation.** New documents, edits to existing ones, the
  `docs/00-index.md` row. Re-run `pytest sw/tests/test_doc_links.py`.
- **Tests, at any level**, added or repaired, provided they do not edit
  `hw/rtl/`, `tt/src/` or a config in section 5.1. Re-run the suite.
- **Analysis over existing run trees.** Section 8 is itself an example:
  it reads reports and netlists and changes nothing.
- **Comment-only edits to `hw/rtl/`** — see 9.3, which is a qualified
  yes, not a free pass.

### 9.2 What forces a full re-harden and a gate-level re-run

Any change to:

- **`hw/rtl/**` other than comments**, i.e. any change that survives the
  strip in section 2.2;
- **`tt/src/*.v`, `tt/src/*.vh`, `tt/src/config.json`**, or anything else
  under `tt/` that `MANIFEST.sha256` covers;
- **any of the six configs in section 5.1**, or the eight `mktiming.py`
  derives, including via `--regenerate-pinned`;
- **the toolchain or PDK versions in section 6**, LibreLane and the PDK
  hash especially.

The obligation, in order — this is `docs/27` section 9 applied to this
freeze:

1. Re-pin with `pin_rtl.py` and re-harden to end of flow.
2. Re-read every geometric deck: Magic DRC, KLayout DRC, KLayout XOR,
   Netgen LVS, antenna, route DRC.
3. Re-check setup and hold at all three corners with
   `SETUP_VIOLATION_CORNERS = ["*"]` — **and, amended 2026-08-31, max cap
   and max slew at all three with `MAX_CAP_VIOLATION_CORNERS` and
   `MAX_SLEW_VIOLATION_CORNERS` = `["*"]`** — and the derate proven in
   the flow-written SDC, not merely in the config. Confirm with
   `hw/openlane/checker_audit.py` that the checkers that ought to gate
   do, rather than reading the absence of a failure as a pass.
4. Re-run the netlist census (**40** guards, amended 2026-08-31; the
   figure in section 7 read 35 and was stale) — a new netlist is not
   covered by the old census.
5. Re-run gate-level functional and gate-level fault injection against
   the new netlist. `docs/32` section 1.4 is the warning about pointing
   those suites at a new netlist without re-pointing their baseline.
6. Re-run the Tiny Tapeout precheck on the new GDS.
7. Regenerate `tt/` and `MANIFEST.sha256`; re-run
   `gen_tt_submission.py --check`.
8. **Supersede this document** with a new freeze record. Do not edit
   this one — its hashes are the record of what `docs/31` measured.

   **AMENDED 2026-08-31, and the amendment is a change of rule, so it is
   argued rather than just applied.** `docs/36` amended this document in
   place instead of superseding it. The rule's purpose is that the record
   of what `docs/31` measured must survive; that purpose is met by
   retaining every superseded hash beside its replacement under a dated
   `SUPERSEDED` marker, which is what was done. Superseding would have
   split one inventory into two documents that a reader must diff, for a
   change whose entire content is **two configuration keys and a
   `resolved.json` hash** — the netlist, powered netlist and DEF did not
   move a byte. **The rule as it now stands: amend in place while the
   built artifacts are unchanged and every superseded value is retained;
   supersede with a new record the moment a netlist hash moves.** A
   change that moves the netlist is a different design and deserves its
   own inventory; this one was not.

Cost, from this run's own timings: about **46 minutes** of summed step
time for the harden **[fact, `docs/31` section 4.2]**, plus the
gate-level campaign, whose runtime `docs/32` section 8 records.
*(Amended 2026-08-31: `docs/36`'s two hardens summed **24.4** and
**23.5** minutes of step time, run concurrently on a 20-core machine.
That is a machine difference, not a scope difference — the step lists
are the same. Budget the 46 minutes.)*

### 9.3 The one qualified case: comment-only RTL edits

A comment-only edit does not change the netlist, and section 2.2 gives
the command that decides whether an edit is comment-only. But it is not
free:

- `tt/src/*.v` must be regenerated and `MANIFEST.sha256` updated, or the
  submission tree stops matching `hw/rtl` and section 2.3 fails.
- Section 2.1's blob list in this document becomes stale, so the freeze
  record must be amended even though no re-harden is owed.

`docs/33` is exactly this case, already absorbed: the blobs in section
2.1 are the post-`docs/33` blobs, and section 2.2 carries the proof.

### 9.4 The mechanical answer to "is what I am submitting what was verified"

Run this. Every line is a claim in this document.

```bash
make -f tools.mk toolcheck                                   # section 6
for f in hw/rtl/*; do echo "$(git hash-object "$f" | cut -c1-12)  $f"; done
                                                             # section 2.1
for f in tt/src/*.v tt/src/*.vh; do b=$(basename "$f"); \
  [ "$(git hash-object "$f")" = "$(git hash-object hw/rtl/$b)" ] \
  || echo "DIFFERS: $b"; done                                # section 2.3
( cd tt && sha256sum -c MANIFEST.sha256 ) | grep -v ': OK$'  # section 4
sha256sum tt/MANIFEST.sha256                                 # section 4
python3 scripts/gen_tt_submission.py --check                 # section 4
python3 hw/openlane/pilot_ihp/mkconfig.py --check            # section 5
python3 hw/openlane/pilot_ihp/mktiming.py --check            # section 5
.venv/bin/python -m pytest -q                                # section 7
```

Expected: no mismatch warning; the ten blobs of section 2.1; no
`DIFFERS` line; no failing manifest line; the manifest hash of section 4;
`tt/ matches the generator`; `OK: 6 pinned config(s) ...`; `all 8
variants match`; and a green suite **apart from the one known
`test_doc_links.py` index failure of section 10 item 7 [amended
2026-08-31]**.

**AMENDED 2026-09-10. Every line above was run at the re-pin and the
expected output has moved twice** **[fact]**:

- `sha256sum tt/MANIFEST.sha256` now prints `f3a68f9d…` and
  `sha256sum -c` prints **31 of 31 OK**, per the amended section 4.
  `gen_tt_submission.py --check` prints `tt/ matches the generator (32
  files)`. The other seven lines print exactly what this section already
  says, unchanged: the same ten blobs, no `DIFFERS` line, `OK: 6 pinned
  config(s) … 0 derived config(s)`, `all 8 variants match`, `yosys
  version = 0.67+146 (pinned 0.67+146)`.
- **The `test_doc_links.py` exception is retired.** `docs/00-index.md`
  names `docs/36`, and `pytest sw/tests/test_doc_links.py -q` is **94
  passed** **[fact, 2026-09-10]**. Section 10 item 7 is closed below.
- **A different suite failure stands in its place, and it is the
  intended kind.** `sw/tests/test_tt_submission.py::test_pilot_only_registers_and_fault_clr_bits_are_documented`
  fails with `Pinned: ['CNT_EVQ_OUT_OVF', 'CNT_EVQ_PAR']. Now: []`. That
  test deliberately pins the gap in the frozen datasheet — the two
  pilot-only registers it omitted and the stale `0x3F` clear mask — and
  says in its own words that if the gap closes, the pin is to be deleted
  rather than widened. Section 4's 2026-09-10 amendment closed it. The
  failing assertion is therefore a **retirement notice, not a
  regression**: `FROZEN_INFO_MD_MISSING`, `FROZEN_INFO_MD_STALE_CLEAR`
  and `docs/21` section 10 item 7 are owed a deletion, in files this
  document does not own. Until that is done, one failure of the last
  line above is expected and is this one.

  The measured run was **9 failed, 495 passed, 1 skipped in 1567.94 s**
  **[fact, `.venv/bin/python -m pytest -q`, 2026-09-10]**, and the other
  eight belong to work in flight elsewhere in the same working tree, not
  to this amendment: seven in
  `sw/tests/test_soc_synthesis_guards.py` reading `soc_wdog` at 136
  flip-flops against a derived budget of 132, and one in
  `sw/tests/test_flow_evidence.py` on an `aer_fifo` configuration. None
  of the eight touches `hw/rtl/`, `tt/` or anything this document pins;
  they are named here so that "9 failed" is not read as this section's
  expected output once they land.

Add one line, which the amendment makes checkable and which nothing else
here checks — that the two gates of `docs/36` are actually bound:

```bash
~/Documents/caravel-lif-crossbar/.venv-flow/bin/python \
  hw/openlane/checker_audit.py hw/openlane/pilot_ihp/runs/signoff-6x2-gated
```

Expected: `17 of 19 in-flow checkers gate fully`, and
`NOT gating in full: Checker.LintWarnings, Checker.WireLength` — those
two and no others.

If the run tree is present, add:

```bash
sha256sum hw/openlane/pilot_ihp/runs/{signoff,submission}-6x2{,-gated}/final/nl/*.nl.v
```

**All four must print
`52b2debf3b2097c1544b2a5ea625675add5ec71a3d3ac9b68dfb5b32d6120989`**
*(amended 2026-08-31; before the amendment this was two paths, the same
hash)*. **That single equality is the tightest statement the freeze can
make**: the netlist the decks were read against and the netlist the
submission path builds are the same bytes — now across two
configurations and two dates.

---

## 10. What is open at the freeze, and none of it blocks the submission

1. **Max fanout stays ungated**, for the measured reasons in section 8.
   The design's maximum is 19 against a library default of 8; the only
   available knob is inert; no checker exists in the pinned LibreLane;
   and the quantities the rule proxies for are 0.
2. ~~**Max cap and max slew are gated at no corner** (section 8.5). One
   configuration line fixes it, the design meets it at zero, and it
   costs a re-harden — so it is the first item on the far side of the
   freeze rather than a change made under it.~~
   **CLOSED 2026-08-31, `docs/36`.** Both keys set, both checkers gate
   at all three corners, both 0. The re-harden was paid: netlist,
   powered netlist and DEF bit-identical, 196 of 196 and 194 of 194
   metrics equal, all geometric decks 0, precheck 10 of 10, gate level
   identical to `docs/32` to the nanosecond **[fact]**. The estimate that
   the fix would be one configuration line and would cost nothing but a
   re-harden was correct.
   **Replaced by a smaller open item**: `Checker.WireLength` gates
   nothing on either PDK, because neither ships `WIRE_LENGTH_THRESHOLD`
   (`docs/36` section 3.3). Reported, not set — there is no vendor limit
   to adopt and any number chosen here would be fitted to the
   measurement, which is item 1's trap. The quantities it proxies for —
   antenna, route DRC, max slew, max cap — are all 0.
3. **The `gds` action has never executed.** Everything in section 3 is
   the same LibreLane, PDK hash and configuration file that action would
   use, run locally. The action itself is not something this repository
   can run, and it is the last unmeasured step **[`docs/31` section 10.9
   item 5]**.
4. **Owner actions**, unchanged from `ROADMAP.md` P1: register the
   project for TTIHP26b as 6x2 tiles, pay before 2026-09-21, and make
   the submission repository public at tapeout per the export strategy.
5. **`RUN_KLAYOUT_DRC` and `RUN_KLAYOUT_XOR` stay 0 in the submission
   configuration**, deliberately, matching upstream. Both decks were run
   here and both are 0, and the shuttle's precheck runs the KLayout DRC
   deck regardless **[`docs/31` section 10.9 item 4]**. Re-run
   2026-08-31 over `submission-6x2-gated`'s own stream, into
   `submission-6x2-gated-geomdecks`: both **0** **[fact, `docs/36`
   section 5.3]**.
6. **Added 2026-08-31: sky130 does not meet max slew**, and
   `hw/openlane/pilot_sky130/config.json` now gates it, so a sky130
   re-harden is expected to fail. Not a shuttle item — sky130 is the
   `docs/18` portability comparison, the shuttle is ihp-sg13g2 where the
   metric is 0, and LibreLane defers this class of error so a failing
   run still writes its full artifact set. `docs/36` section 4.
7. ~~**Added 2026-08-31: `docs/00-index.md` does not name `docs/36`**, so
   `sw/tests/test_doc_links.py::test_every_document_is_reachable_from_the_index`
   fails, 1 failed against 233 passed. `docs/36` section 7 item 5 carries
   the row to add. Both files are outside that document's ownership;
   this is the same disposition `docs/31` section 10.8 item 5 recorded
   for `docs/32`.~~
   **CLOSED 2026-09-10.** The index names `docs/36` and
   `pytest sw/tests/test_doc_links.py -q` is **94 passed** **[fact]**.
8. **Added 2026-09-10: the frozen-datasheet pin in
   `sw/tests/test_tt_submission.py` is owed a deletion.** Section 4's
   amendment corrected `tt/docs/info.md`, which is what
   `FROZEN_INFO_MD_MISSING` and `FROZEN_INFO_MD_STALE_CLEAR` were
   waiting for; the test now fails by design and says so in its own
   assertion text. `docs/21` section 10 item 7 is the written record
   that goes with them. All three are outside this document's
   ownership — same disposition as item 7 above, and as `docs/31`
   section 10.8 item 5. Nothing about the submission depends on it: the
   datasheet the shuttle reads is now correct, and the pin is the
   scaffolding that was holding the door open until it was.
