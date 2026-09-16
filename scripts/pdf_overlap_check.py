#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Find text that collides with other text in a built PDF.

    pdf_overlap_check.py <file.pdf> [--min-overlap 0.35] [--quiet]

WHY THIS EXISTS. A figure in the thesis printed every macro's name on
top of its own dimensions for two published revisions, and nobody saw
it: the LaTeX log was clean, because the collision was inside a PDF
that LaTeX only places, and the reader who found it was the owner
looking at page 68. The cause was an offset given in data coordinates
-- 14 micrometres on an axis 2,000 micrometres tall -- where the code
meant points.

WHAT IT CHECKS. Every word's bounding box, from `pdftotext -bbox`.
Two words collide when their boxes overlap by more than `--min-overlap`
of the smaller one's AREA *and* by more than `--min-vertical` of its
HEIGHT. Neighbours on a line of type need no special case, and an
earlier version of this tool made one and paid for it: words set side
by side do not overlap horizontally at all, so they never reach either
threshold, while two words printed at the SAME baseline in the same
size are the worst collision a page can have -- and those are exactly
the pairs a "tops and bottoms agree, so it is one line" rule excuses.

THE HEIGHT TEST IS THE ONE THAT MATTERS, and it is why the first
version of this tool reported fourteen pairs per page on a page that
was fine. Two stacked lines of a two-line label overlap in area a
surprising amount -- a descender from the line above reaches into the
ascender band of the line below, and since the two lines sit directly
on top of each other the horizontal overlap is total, so the product
looks like a third of the smaller word. What distinguishes that from a
real collision is the vertical share: stacked lines touch at their
edges, colliding text sits on the same baseline. Type set normally
lands under 0.3; the page-68 defect was 1.0.

WHAT IT CANNOT SEE. Text that overlaps a GRAPHIC rather than other
text: a label sitting on a filled rectangle is legible or not
depending on the fill, and this tool has no opinion. It also cannot
see text that has been pushed outside the page, which is what the
LaTeX log's overfull warnings are for; run both.
"""

import argparse
import collections
import re
import subprocess
import sys
import xml.etree.ElementTree as ET


def words(pdf):
    """(page, x0, y0, x1, y1, text) for every word, via pdftotext -bbox."""
    out = subprocess.run(["pdftotext", "-bbox", pdf, "-"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit("pdftotext failed on %s: %s" % (pdf, out.stderr.strip()))
    root = ET.fromstring(out.stdout)
    ns = {"x": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
    page_tag = "{%s}page" % ns["x"] if ns else "page"
    word_tag = "{%s}word" % ns["x"] if ns else "word"
    for n, page in enumerate(root.iter(page_tag), 1):
        for w in page.iter(word_tag):
            try:
                yield (n, float(w.get("xMin")), float(w.get("yMin")),
                       float(w.get("xMax")), float(w.get("yMax")),
                       (w.text or "").strip())
            except (TypeError, ValueError):
                continue


def collisions(pdf, min_overlap, min_vertical):
    by_page = collections.defaultdict(list)
    for n, x0, y0, x1, y1, t in words(pdf):
        if t:
            by_page[n].append((x0, y0, x1, y1, t))
    found = []
    for page, ws in sorted(by_page.items()):
        ws.sort(key=lambda w: (w[1], w[0]))
        for i, a in enumerate(ws):
            for b in ws[i + 1:]:
                if b[1] > a[3]:          # sorted by y0; no later word can meet
                    break
                ox = min(a[2], b[2]) - max(a[0], b[0])
                oy = min(a[3], b[3]) - max(a[1], b[1])
                if ox <= 0 or oy <= 0:
                    continue
                ha, hb = a[3] - a[1], b[3] - b[1]
                smaller = min((a[2] - a[0]) * ha, (b[2] - b[0]) * hb)
                low = min(ha, hb)
                if smaller <= 0 or low <= 0:
                    continue
                # BOTH tests: area, and the vertical share that tells a
                # collision from two lines stacked in the normal way.
                if ox * oy / smaller < min_overlap or oy / low < min_vertical:
                    continue
                found.append((page, a[4], b[4], ox * oy / smaller, oy / low))
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pdf")
    ap.add_argument("--min-overlap", type=float, default=0.35,
                    help="colliding area, as a fraction of the smaller box")
    ap.add_argument("--min-vertical", type=float, default=0.50,
                    help="colliding height, as a fraction of the shorter box")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    found = collisions(a.pdf, a.min_overlap, a.min_vertical)
    if not found:
        if not a.quiet:
            print("  %s: no text collides with other text" % a.pdf)
        return 0
    seen = collections.Counter(f[0] for f in found)
    print("  %s: %d colliding word pairs on %d pages"
          % (a.pdf, len(found), len(seen)))
    for page in sorted(seen):
        rows = [f for f in found if f[0] == page][:6]
        print("   page %d (%d pairs):" % (page, seen[page]))
        for _, w1, w2, frac, vert in rows:
            print("     %-26s over %-26s  area %3.0f %%  height %3.0f %%"
                  % (w1[:26], w2[:26], 100 * frac, 100 * vert))
    return 1


if __name__ == "__main__":
    sys.exit(main())
