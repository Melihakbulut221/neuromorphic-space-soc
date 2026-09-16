<!--
SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
SPDX-License-Identifier: CC-BY-4.0
-->
# 85 — What page 68 was hiding

The owner opened the published thesis, looked at one page, and wrote
*"sayfa 68'de yazılar üst üste gelmiş"* — the writing on page 68 is on
top of itself. It was. Every macro in the floorplan figure printed its
name across its own dimensions, and it had done so in two published
revisions of the document.

This records what the one report turned out to be the visible end of.
Chasing it properly meant building the check the owner had just
performed by eye, running it over both documents, and then reading what
it could not see. **Four separate defects came out, of four different
kinds, and only the first was the one reported.**

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file in this repository on the stated date.

---

## 1. Verdict first

| | |
|---|---|
| **What was reported** | one figure, one page, names over dimensions |
| **What it was** | offsets given in data coordinates where points were meant: 14 um above centre on an axis 2,000 um tall |
| **What a systematic scan then found** | a micro sign printing as a t-cedilla in 46 places; three fragments of editing instructions typeset as body text; a table overrunning its float page onto the folio |
| **What the scan could not find, and a human could** | all four, which is the point of section 7 |
| **Gates added** | two, in both document Makefiles: no overfull box, and no text over other text |
| **Gate proved to fire** | yes, on a page built to collide (section 6) |
| **State of both documents** | 0 overfull boxes, 0 colliding word pairs, 0 t-cedillas, 533 tests, SPDX clean |

**The reason all four survived to publication is the same reason.**
Every one of them is invisible in the source and invisible in the
build log. LaTeX does not warn that a PDF it is placing has text over
text; it does not warn that `\micro` resolved to the wrong glyph,
because a glyph is a glyph; and the one defect it *did* warn about — an
890 pt overfull box — was a single line in a 36,000-line log that no
gate read. **The source compiled, the log was never read, and the page
was wrong.**

---

## 2. The reported defect: points and micrometres

`thesis/figures/make_layout_figures.py` draws the eight vendor macros
from the sign-off DEF and labels each with its name above centre and
its size below. The offsets were written as

```python
ax.annotate(name, (cx, cy + 14.0), ...)     # 14 WHAT?
ax.annotate(detail, (cx, cy - 10.0), ...)
```

In an axis whose y span is 2,115 um, 14 um is **0.66 % of the height**
— roughly a third of a point on the printed page. The two labels
therefore landed on the same line. The fix is one keyword:

```python
ax.annotate(name, (cx, cy), textcoords="offset points",
            xytext=(0, 5), ...)
```

`textcoords="offset points"` is what the code meant all along; without
it matplotlib reads the offset in data units, which for this figure is
micrometres of silicon. **[fact, 2026-09-16]**

Two further collisions in the same figure came out of fixing the first,
and are recorded because they are the same class: the small ROM check
macros' dimension text was wider than the macro it described and spilled
over its neighbours, and the die and core captions crossed the die
outline and ran under a RAM bank. Both are now inside the empty channel
between the macro rows, which is the one region of that die with room.

---

## 3. The scan, and what it cost to make it trustworthy

`scripts/pdf_overlap_check.py` takes every word's bounding box from
`pdftotext -bbox` and reports pairs that overlap. The naive version of
that test is useless, and the two iterations it took to become useful
are worth more than the tool.

**First version: fourteen false pairs per page.** Two stacked lines of a
two-line label overlap in *area* by a surprising amount. A descender
from the upper line reaches into the ascender band of the lower one,
and because the lines sit directly above each other the horizontal
overlap is total — so the product looked like a third of the smaller
word on type that was perfectly fine.

**The discriminator is the vertical share, not the area.** Stacked
lines touch at their edges; colliding text sits on the same baseline.
The tool now requires **both** that the overlapping area exceed a
fraction of the smaller box *and* that the overlapping height exceed a
fraction of the shorter box. Normal type lands under 0.30 on the second
test. The page-68 defect was at 1.00.

| | area share | height share | verdict |
|---|---|---|---|
| two lines of one label | 0.37 | 0.22 | type, correctly passed |
| name over its own dimensions (page 68, before) | 1.00 | 1.00 | the defect |
| region box over a macro label (paper, page 8) | 0.66 | 0.88 | the defect |
| folio under an overrunning caption (paper, page 4) | 0.83 | 0.97 | the defect |

**Second version: a blind spot that excused the worst case.** To keep
kerned pairs quiet the tool skipped any two words whose tops and bottoms
agreed to within a point, as "the same line of type". That rule is not
merely unnecessary — words set side by side do not overlap horizontally
at all, so they never reach either threshold — it is **actively
wrong**, because two words printed at the *same* baseline in the *same*
size are the worst collision a page can have, and they are exactly what
the rule excused. It was found by building a page that overprints two
words deliberately and watching the tool pass it. The rule is gone.

---

## 4. Three fragments of editing instructions, typeset as body text

The scan over the thesis log turned up one overfull box, **890 pt too
wide**, in the peripheral-slots table. The cause was not the table. A
line reading

> and append to the caption of `\cref{tab:arch-slots}`: ...

sat between two rows of the table body. It carries no `&`, so TeX read
it as the opening cell of a row that did not end until the next `\\`,
merged two rows into one, and produced a cell a foot wide.

Two more of the same shape were in the corpus, found by grepping for
the shape rather than the text:

| file | what leaked | where its content had already landed |
|---|---|---|
| `thesis/chapters/arch.tex` | *"and append to the caption of tab:arch-slots: ..."* | nowhere — the caption never got it |
| `thesis/chapters/results.tex` | *"and at line 53: Antenna violating nets & 2 ..."* | the row already existed in the geometric sign-off block |
| `thesis/chapters/harden.tex` | *"and at line 793: Every campaign is single-bit ..."* | already applied, verbatim, in `sec:harden-open` |

**Two of the three had been applied and had leaked anyway**, which is
the instructive part: the edit succeeded and its own description was
left behind in the file. The third had not been applied at all, so its
content — why `docs/60` counts seven registers for the SCRUB slot where
this table counts fourteen, both correct on their own dates — is now in
the caption where it was meant to go.

---

## 5. The micro sign, wrong in 46 places

The thesis set its lengths with siunitx's `\micro\metre`. Under `T1`
encoding with `lmodern`, that prints **ţ**, a t-cedilla. The published
document described a *"700.08 ţm standard-cell channel"*.

siunitx's own `text-micro` and `math-micro` keys do not fix it. They
were set, the document was rebuilt, and the glyph did not change —
under `detect-all` or without it, with `textcomp` loaded or not, in all
four combinations. **[fact, 2026-09-16]** What works is declaring the
unit outright, which is what the SoC paper had already been doing:

```latex
\usepackage{upgreek}
\DeclareSIUnit{\um}{\text{\ensuremath{\upmu}}m}
```

46 occurrences of `\micro\metre` became `\um`. A further 46 occurrences
of a hand-set `$\mu$m` — math-italic mu, where a unit symbol must be
upright — became `\upmu`, so that both spellings now print the same
mark. The rebuilt document contains **zero** t-cedillas.

---

## 6. A table that pushed its own caption onto the page number

The SoC paper's formal-property table is a full-page float. Its
description column was 5.6 cm on a 15.9 cm text block, which left three
centimetres unused, wrapped half the rows to three lines, and made the
table tall enough that its seven-line caption ran off the bottom of the
page — **through the folio**, which is how the scan found it: a lone
digit `4` printed inside `hw/soc/formal` at 83 % overlap. Widening the
column to 7.0 cm returns the rows to two lines and the caption to the
page. Nothing about the content changed.

---

## 7. Where the gates go, and why not in the test suite

Both properties are properties **of the rendered page**, so they are
checked where a rendered page first exists: in the recipe that builds
it, in `thesis/Makefile` and `paper-soc/Makefile`, beside the undefined
-citation check that was already there.

```make
	@grep -q 'Overfull' $(DOC).log && { ... exit 1; } || true
	@python3 ../scripts/pdf_overlap_check.py $(DOC).pdf --quiet
```

They are not in `sw/tests` because the suite does not build LaTeX and
should not start; a test that skipped when no PDF was present would be
a guard that never fires, which this project has been bitten by before
(`docs/78`). The stage that can satisfy the property is the build, so
the guard sits at the build.

**The gates are satisfiable today.** Both documents build with zero
overfull boxes and zero colliding pairs, so neither gate is a standing
red light that the next person learns to ignore.

---

## 8. Three pre-correction figures, closed

`docs/83` corrected its own wire-share measurement on 2026-09-16 and
the SoC paper, published the same day, honestly named three places in
the corpus that still carried the pre-correction numbers. Naming them
is not fixing them. All three are now corrected:

| where | was | is |
|---|---|---|
| `docs/83` section 5 | roughly 88 stages | roughly 78 stages |
| `docs/84` opening | median 88 gate stages | median 78 gate stages |
| `docs/00-index` row for `docs/83` | 3.6 % wire at the median | 1.9 % wire at the median |

The pre-correction figures now survive in exactly one place, the
correction blockquote in `docs/83` section 3, which is where `docs/64`
says a superseded measurement belongs. The paper's own paragraph has
been updated to say so rather than to name three open items that are
closed.

---

## 9. What none of this catches

**Text over a graphic.** A label on a filled rectangle is legible or
not depending on the fill, and the checker has no opinion. The region
boxes in the die map sit on a tinted region on purpose.

**Text pushed off the page.** That is what the overfull gate is for,
and the two gates are only useful together.

**A figure that is wrong rather than illegible.** Every number in the
die maps comes from the sign-off DEF and the netlist, and nothing here
checks that the DEF is the one the document claims. `docs/50` section 16
is the project's record of what that failure looks like.

**Prose that says the wrong thing clearly.** Section 8 exists because a
human read three documents against each other. No gate in this
repository would have found those, and the seventeen errors corrected
in the thesis the day before were found the same way.

---

*2026-09-16. Nothing was built for this document; it is a record of a
typographic pass over two already-published deliverables and the two
gates that came out of it.*
