# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""The paper's HTML reading copy renders with no unknown macro.

WHY THIS GUARD EXISTS, AND WHY IT IS A DUPLICATE ON PURPOSE.
`scripts/ci_local.sh` has carried exactly this gate since it was
written, and the gate WORKS -- it caught the defect the moment it was
run. The problem is that it was not run. `\\mbox` entered
`paper/main.tex` on 2026-09-13 inside a dated correction note; the last
row of `ci-local-log.tsv` is 2026-09-10; and an external reviewer found
the renderer exiting 1 four days later, on a front-door command the
README tells readers to run.

So the finding was never "the gate is missing". It was "the gate is in
a place nobody runs". `pytest` runs on every change, and this file is
the same property checked where it will actually fire. That is
`docs/78`'s rule read the other way round: a guard must also sit where
it will be executed.

WHY ONE FILE AND NOT EVERY PAPER. `paper/render_html.py` is a renderer
for `paper/main.tex` and for nothing else: `ci_local.sh:195` invokes it
on that one path, no `.html` is tracked in this repository, and no
other paper directory has an HTML target. Pointed at `paper-soc` it
reports 34 unknown macros -- not a defect in `paper-soc`, which is a
PDF deliverable that uses tabularx and siunitx, but a measurement of
what this tool was built for. Widening the test to `paper*/main.tex`
would be exactly the scope creep this repository keeps correcting: a
green check read wider than the thing it checks.

WHAT IT DOES NOT CHECK. Whether the HTML is *correct*. A macro can be
handled and handled wrongly; that is what reading the output is for,
and `docs/85` records a defect that no automatic check would have
found.
"""

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
RENDERER = ROOT / "paper" / "render_html.py"
SOURCE = ROOT / "paper" / "main.tex"


def test_reading_copy_has_no_unknown_macro(tmp_path):
    if not RENDERER.exists() or not SOURCE.exists():
        pytest.skip("paper/render_html.py or paper/main.tex is not in this tree")
    out = tmp_path / "main.html"
    r = subprocess.run([sys.executable, str(RENDERER), str(SOURCE), str(out)],
                       capture_output=True, text=True, cwd=ROOT)
    report = (r.stdout + r.stderr).strip()
    assert r.returncode == 0, (
        "paper/main.tex does not render: %s\n"
        "An unknown macro means render_html.py has no handler for a "
        "construct the source uses. Add it to SIMPLE rather than "
        "editing the .tex: the LaTeX is not the thing that is wrong."
        % report)
    assert "0 unknown macro(s)" in report, report


def test_the_renderer_handles_the_thesis_citation_shape(tmp_path):
    """`\\dcite` wraps every docs/NN citation in an `\\mbox`.

    The thesis is not rendered to HTML by anything in this repository,
    so this is not a claim that it could be. It is the narrower claim
    that the construct `\\dcite` expands to survives the renderer, which
    is what makes `\\mbox` worth handling rather than stripping.
    """
    if not RENDERER.exists():
        pytest.skip("paper/render_html.py is not in this tree")
    src = tmp_path / "t.tex"
    src.write_text(
        "\\documentclass{article}\n\\begin{document}\n\\section{T}\n"
        "A \\mbox{\\texttt{docs/63}\\,section 8.4} B.\n\\end{document}\n")
    out = tmp_path / "t.html"
    r = subprocess.run([sys.executable, str(RENDERER), str(src), str(out)],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr
    html = out.read_text()
    assert "<code>docs/63</code>" in html, html
    assert "nobr" in html, "the mbox should survive as a non-breaking span"
