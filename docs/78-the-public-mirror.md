# 78 — The public mirror: what is published, what is not, and what the shape costs

`docs/14` section 11 was signed on 2026-09-09 and its stage-1 mechanics
were executed the same day. That answered *what licence*. It did not
answer *what tree*, and section 9 stage 2 had deliberately left that
open with a date on it: **2026-10-05, decide whether the public tree is
this repository made public or a curated mirror, and the deciding
question is whether the existing git history is publishable as-is.**

This document is that decision, taken early because a paper and an
announcement both need a URL, and recording what the choice costs.

---

## 1. The decision

**A curated mirror, generated, carrying the tree and not the history.**

`scripts/gen_public_mirror.py` writes the published subset into a
directory and, with `--commit`, makes one commit on `main` that names
the source revision it was taken from. It does not push and it does not
create a repository. Publication stays an act of the owner.

*Corrected 2026-09-12: this sentence continued "which is the same rule
`.github/workflows/docs.yml` states for the documentation site and for
the same reason". That workflow was deleted in `74fdddf`, when three
workflows were folded into `.github/workflows/checks.yml`. The rule did
not change -- `checks.yml` builds the site, gates on its manifest and
deploys nothing -- but the file that stated it is gone, and section 3.2
below is about that very file, so this document now points at it twice
in the past tense. Nothing in the suite could catch either:
`test_doc_links.py` follows references to documents, not to workflow
files.*

### 1.1 Why not simply make this repository public

The deciding question section 9 named is a real one and the honest
answer is that **it has not been audited**. Three hundred-odd commit
messages written over three weeks, several of them recording what a
funding application would say and what a shuttle would cost, are not
something to publish on the strength of a memory of having written
them. Auditing them is a day's work with a poor failure mode: one
missed message is not recoverable after a push.

The mirror costs something real instead, and it is stated in the
mirror's own `README.md` rather than left for a reader to notice:
**you cannot see how the design got here from the published
repository, only where it arrived.**

That cost is smaller here than it would be in most projects, and the
reason is the corpus. Seventy-eight documents record the design's
history in more detail than any commit log — including, specifically,
the parts a commit log would not hold: the claims that were withdrawn,
the measurements that were re-attributed, the checks that were found to
be reading wider than what they looked at. `docs/64`'s rule that a
superseded measurement is left standing rather than rewritten is what
makes the corpus a history rather than a snapshot. **The history is
published; it is just not in `git log`.**

---

## 2. What is held back

Three items, from `LICENSES.md` section 2.1, none of them a technical
result:

| Held | What it carries | Why |
|---|---|---|
| `docs/05` section 3 | product-line positioning, price bands, customer profiles | commercial |
| `docs/06` | grant timetable, shuttle commercials, cost figures | commercial |
| `docs/13` | the drafted text of an unsubmitted funding application | commercial, and unsubmitted |

**Nothing technical is held.** No negative result, no withdrawn claim,
no measurement, no failing check. That is not a courtesy; it is the
condition under which the rest of the corpus means anything. A record
that publishes only what worked is a brochure.

### 2.1 The hole is filled with a marker, not left as a hole

Twenty-two documents cite `docs/06` or `docs/13` in prose, and
`sw/tests/test_doc_links.py` fails on a reference naming a file that
does not exist. Three ways out were available and two of them are
wrong:

1. **Delete the files and edit the twenty-two citations.** Rejected. A
   document edited to hide that it once cited something is the exact
   opposite of what this corpus does, and it would have been invisible
   in the published tree.
2. **Delete the files and exempt the references in the link test.**
   Rejected for the same reason plus one more: it turns a check that
   currently proves something into a check with a hole in it, and
   `docs/50` section 8.1's rule is *extend, do not relax*.
3. **Replace each file with a stub that keeps the filename and says
   what was held and why.** Taken.

`docs/05` keeps its file and loses section 3 the same way: the heading
survives, so the document's own numbering and every cross-reference to
a later section of it still resolve, and the stub says what the section
carried. Section 4 — the binding positioning-language rules, which is
the section the rest of the corpus actually cites — is published.

**Measured, not asserted:** the mirror's own `test_doc_links.py` runs in
the generated tree and passes **90 of 90**. That is the check the stubs
exist to satisfy, run where it matters rather than where it is
convenient.

---

## 3. Two defects the generator found, both in checks

Neither was in the mirror. Both were in things that had been passing.

### 3.1 `scripts/spdx_check.py` reported itself as tagged when it was not

The first version searched **the first 4,000 characters for the
identifier string**, anywhere, in any context. This file's own
docstring and its own regular expression both contain that string, so
**the checker read its own prose as its own licence** — and reported
`0 missing` while carrying no header at all.

It went unnoticed because it was invisible: the file passed. It surfaced
only when an unrelated edit to `tracked()` pushed the docstring past the
4,000-character window and the file abruptly turned up `MISSING`.

That is the failure shape this corpus names more than any other: **a
green result read wider than what it actually looked at**. The question
is never "did the check pass", it is "what could the check have seen" —
and this one could see any file that merely *mentioned* SPDX.

Narrowed: a tag counts only on a **comment line** within the **first
twelve lines**. That is where a header is and where prose about headers
is not. The docstring records the incident rather than describing the
new rule as if it had always been the rule.

### 3.2 The mirror would have carried a workflow whose stated reason was false

*Read in the past tense from 2026-09-12: `.github/workflows/docs.yml` no
longer exists -- `74fdddf` replaced it and two siblings with
`.github/workflows/checks.yml`. What follows is the record of a
decision made while it did, and the exclusion it produced still stands
in `gen_public_mirror.py`.*

`.github/workflows/docs.yml` explained at length why it did not deploy
to GitHub Pages, and the first reason it gives is **"this repository is
private"**. In the mirror that sentence is false, and the behaviour it
justifies — not deploying — is still correct for a *different* reason.

A generated tree carrying a stale reason for a still-correct behaviour
is the same failure shape as 3.1, one level up: a reader checks the
behaviour, finds it right, and inherits a false premise. The generator
rewrites that reason for the mirror, strikes the old one through rather
than deleting it so the two trees can be diffed, and says plainly what
turning the deploy on would take. It **refuses to run** if that line is
no longer in the file, rather than silently emitting an unrewritten
copy.

**AMENDED 2026-09-10, and the amendment is a defect this section
claimed the opposite of.** The three workflows have been replaced by
one, `.github/workflows/checks.yml`, whose checks live in
`scripts/ci_local.sh` so that the runner and the developer's machine
share one definition. The rewrite above was anchored on `docs.yml` and
was written as `if wf in files:` — so when that file was deleted **the
guard did not fire; it was skipped**, and the generator wrote 511 files
as though nothing were owed. The sentence above says it "refuses to run
if that line is no longer in the file". It refused if the line had
changed and **not** if the file had gone, and the second is the case
that actually arrived.

A check that cannot fail when the thing it checks is absent is not a
check. That is the third instance of this exact shape found in this
repository's own instruments — after the licence checker that read its
own prose as its own licence, and the verification recorder whose glob
could not reach the results it was counting — and it is the first one
found in a guard written to prevent the shape.

It now raises on absence, and it anchors on the paragraph in
`checks.yml` recording the billing history, which is the sentence that
belongs to the development repository and not to the mirror.

---

## 4. What the mirror is checked against

```bash
python3 scripts/gen_public_mirror.py --out ../nssoc-public
python3 scripts/gen_public_mirror.py --out ../nssoc-public --check
```

`--check` compares every generated file byte for byte and reports any
file in the output that the generator did not write, ignoring only the
caches a run inside the tree leaves behind — named, because a list that
includes noise is a list that gets skimmed.

Measured at `13402ad` **[fact, 2026-09-09]**:

| Check | Result |
|---|---|
| Files generated | 482 |
| `--check` against the written tree | matches |
| `scripts/spdx_check.py` in the mirror | 312 tagged, 170 by path, 0 missing, 0 wrong |
| `test_doc_links.py` in the mirror | 90 passed |
| Held-back files present as stubs | `docs/06`, `docs/13` |
| Held-back section present as a stub | `docs/05` section 3 |

The SPDX check runs in the mirror at all only because it was taught to
work **without git**: a generated tree is a plain directory until it is
committed, and a check that cannot run there is a check that does not
run where it is most needed.

---

## 5. What this does NOT cover

- ~~**NOTHING IS PUBLISHED BY THIS DOCUMENT OR BY THIS GENERATOR.**~~
  **PUBLISHED 2026-09-10**, on the owner's instruction, to
  <https://github.com/Melihakbulut221/nssoc> — 518 files, one commit,
  source revision `93757c9`, tree digest `8aece676a9c97684`. The
  generator still does not push; the push was a separate act, and the
  mirror's own checks were run in the generated tree first: SPDX 329
  tagged with 0 missing and 0 wrong, and 94 link tests.

  **One thing was found in the check before the push and is recorded
  rather than fixed.** `docs/37-external-check.md` is not in the held
  set and carries the shuttle's cost figures — EUR 70 per tile, EUR 955
  for the frozen 6x2 — which is the class `docs/06` is held for. It is
  published anyway, for a stated reason: those figures are **Tiny
  Tapeout's own published prices**, and `docs/37` verifies them against
  the vendor's public pricing asset, whose URL it prints. They are a
  fact-check of an external party's public numbers rather than this
  project's commercial material.

  **One fragment in it is genuinely this project's and is not covered by
  that reason**: the phrase *"WP3's 3,500 envelope absorbs either"*
  quotes a work-package budget line out of the held `docs/06`. It is one
  clause, it is published, and it is named here so the decision to leave
  it is on the record rather than in the gap between two documents. A
  reader who wants it removed regenerates with `docs/37` added to
  `HELD_SECTIONS`.
- **THE COMMIT HISTORY HAS STILL NOT BEEN AUDITED.** This decision routes
  around that question rather than answering it. If the repository is
  ever made public directly, the audit is still owed.
- **`docs/02` OPEN QUESTION 2 IS STILL OPEN**, and `docs/14` section 11.2
  is where it now bites: until it is answered, **no public description of
  this accelerator may claim independent implementation.** The mirror
  publishes `docs/02` with the question open, which is correct and is
  also a thing a reader will see.
- **THE STUBS ARE PROSE, NOT REDACTION.** They state what was held. A
  reader who wants the funding timetable can infer that one exists. That
  is intended; the alternative is a silent gap.
- **ONE GENERATION, ONE SOURCE REVISION.** The mirror at `13402ad` is what
  was checked. Nothing here says the next generation is clean; `--check`
  is how that is answered each time.
- **NO PAGES DEPLOY ANYWHERE**, in this repository or the mirror.

---

## 6. Reproducing this

```bash
python3 scripts/gen_public_mirror.py --out /tmp/nssoc-public --commit
cd /tmp/nssoc-public
python3 scripts/spdx_check.py                       # 0 missing, 0 wrong
<repo>/.venv/bin/python -m pytest sw/tests/test_doc_links.py -q   # 90 passed
cd <repo> && python3 scripts/gen_public_mirror.py --out /tmp/nssoc-public --check
```

---

## 7. Republished 2026-09-11

`24023bb` on the mirror, from `26f4494` here. **529 files**, tree digest
`3102e217587b13bb`; `--check` matches the generator **[fact]**.

Fifty-two paths moved, and one of them is the reason this section exists
rather than a line in a commit message. `tt/docs/info.md` — the shuttle
page an operator reads — told them to write `0x3F` to `FAULT_CLR` when
the mask has been eight bits since `docs/55` added two counters. The
correction was made in this repository on 2026-09-10 and **the published
copy went on saying `0x3F` for a day**, because regenerating the mirror
is a thing a person does and nothing was watching. The public copy now
carries `0xFF` and the superseded value left standing beside it with its
date, per `docs/64`.

`scripts/ci_local.sh mirror` is the answer to the general form: it runs
the generator and its `--check`, so a generator that has stopped
selecting what it claims to select is caught locally. It does **not**
check the published repository and cannot — nothing here can reach it.
**Regenerating and pushing is still an act, by a person, and the gap
between this repository and what a stranger reads is still measured in
whenever that last happened.**

Section 6's reproduction still holds; the pytest count in it was 90 when
it was written and is 95 today, which is a document count and not a
finding.
