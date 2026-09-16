# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""No document ships with a template placeholder left in it.

WHY THIS GUARD EXISTS. `docs/82` was committed, pushed and MIRRORED TO
THE PUBLIC REPOSITORY carrying five unrendered placeholders --
`%%VERDICT%%` where its verdict table belongs, and four more where its
controls, its two result blocks and its suite results belong. Nothing
caught it: the link checker resolves references, the SPDX checker reads
headers, and neither looks at whether the body was filled in. A reader
who opened the published file found a section-1 heading followed by a
token.

The guard checks the PROPERTY and not one spelling: a run of two or
more percent signs around an upper-case word is what every templating
convention in this repository has used, and the check is applied to
every tracked Markdown file rather than to a list of the ones that have
gone wrong so far.

WHAT IT DELIBERATELY ALLOWS. Shell parameter expansion inside a fenced
code block -- `${spec%%:*}` is in `docs/82`'s own reproduction recipe --
is not a placeholder, and stripping fenced blocks before the scan is
what tells the two apart.
"""

import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLACEHOLDER = re.compile(r"%%[A-Z][A-Z0-9_]*%%|\{\{[A-Z][A-Z0-9_]*\}\}")
FENCE = re.compile(r"```.*?```", re.S)


def _tracked_markdown():
    """Every tracked .md, falling back to the tree when there is no git.

    docs/78's principle: a guard must work in the checkout a reader
    actually has, and a mirror is a checkout without this repository's
    history.
    """
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "*.md"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode == 0 and out.stdout.strip():
            return [ROOT / p for p in out.stdout.split()]
    except Exception:
        pass
    return [p for p in ROOT.rglob("*.md")
            if not any(part in (".git", "node_modules") for part in p.parts)]


def test_no_document_ships_an_unrendered_placeholder():
    bad = []
    for p in _tracked_markdown():
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        for m in PLACEHOLDER.finditer(FENCE.sub("", text)):
            bad.append("{}: {}".format(p.relative_to(ROOT), m.group(0)))
    assert not bad, (
        "these documents carry an unrendered template placeholder, which is "
        "how docs/82 reached the public mirror with its verdict table "
        "missing: {}".format(bad))
