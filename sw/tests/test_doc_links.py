# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Link integrity across the markdown corpus.

Two properties, both of which the documentation site depends on and
neither of which anything else in the repository checks:

  1. Every cross-reference in every document names a file that exists.
     The corpus refers to itself constantly and in prose -- "docs/06
     section B.6", "`docs/12-sg13g2-flow-bringup.md`" -- so a renamed or
     deleted document leaves several hundred references pointing at
     nothing, silently, because none of them is a link.

  2. Every document is reachable from the index. docs/00-index.md is the
     entry point; a document that it does not name is a document a reader
     arriving at the front door cannot find.

Both are enforced against the tree as it is on disk. Nothing here lists
the documents: the corpus is discovered, so a document added tomorrow is
in scope tomorrow with no edit to this file.

The single deliberate exemption is references to a *sibling* programme's
documents. docs/16 and docs/17 cite the radiation-hardened edge-AI
project's own docs/25 and docs/27 as the source of the fault-injection
method. Those files are not in this repository and must not be linked
from this site. They are exempted only where the citing line names the
sibling programme -- see SIBLING_MARKERS -- so the exemption cannot be
used, accidentally or otherwise, to hide a genuinely broken reference to
one of our own documents.

Run with the repository-root suite::

    .venv/bin/python -m pytest sw/tests/test_doc_links.py
"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import build_docs  # noqa: E402  (path set above)

INDEX = ROOT / "docs" / "00-index.md"

# A line citing one of these is citing another repository, not this one.
SIBLING_MARKERS = ("radhard-edge-ai", "sibling")


def _sources():
    docs = sorted((ROOT / "docs").glob("*.md"))
    roots = [ROOT / "README.md", ROOT / "ROADMAP.md"]
    return docs + [p for p in roots if p.is_file()]


SOURCES = _sources()
SOURCE_IDS = [str(p.relative_to(ROOT)) for p in SOURCES]

# Every path this corpus is allowed to name, as a set of basenames plus
# the full relative paths, so both "docs/06" and "docs/06-...md" resolve.
DOC_FILENAMES = {p.name for p in (ROOT / "docs").glob("*.md")}
DOC_NUMBERS = {
    m.group(1)
    for m in (re.match(r"^(\d{2})-", n) for n in DOC_FILENAMES)
    if m
}


# How far back to look for a sibling-programme marker. The corpus is hard
# wrapped at about 72 columns, so the clause naming the sibling repository
# and the reference it introduces routinely land on different lines.
MARKER_LOOKBACK = 3


def _references(path):
    """Yield (line_number, context, reference) for one file.

    `context` is the citing line together with the MARKER_LOOKBACK lines
    before it, which is what the sibling-programme exemption is tested
    against.

    References inside fenced code blocks are skipped: a fenced block is a
    transcript or a command, and a path in one is not a cross-reference.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    line_no = 0
    for is_code, chunk in build_docs.split_fences(path.read_text(encoding="utf-8")):
        for raw in chunk.splitlines():
            line_no += 1
            if is_code:
                continue
            for m in build_docs.DOC_REF.finditer(raw):
                start = max(0, line_no - 1 - MARKER_LOOKBACK)
                context = "\n".join(lines[start:line_no])
                yield line_no, context, m.group(0)


def _resolves(reference):
    m = build_docs.DOC_REF.fullmatch(reference)
    assert m is not None, reference
    number, name = m.group(1), m.group(2)
    if name:
        return f"{number}{name}" in DOC_FILENAMES
    return number in DOC_NUMBERS


def _is_sibling_citation(context):
    low = context.lower()
    return any(marker in low for marker in SIBLING_MARKERS)


def _context_at(path, line_no):
    lines = path.read_text(encoding="utf-8").splitlines()
    start = max(0, line_no - 1 - MARKER_LOOKBACK)
    return "\n".join(lines[start:line_no])


# ----------------------------------------------------------------------
# Property 1: every cross-reference names a file that exists
# ----------------------------------------------------------------------


def test_corpus_is_not_empty():
    """Guard against the discovery above silently finding nothing."""
    assert len(SOURCES) >= 20, SOURCE_IDS
    assert INDEX in SOURCES


@pytest.mark.parametrize("path", SOURCES, ids=SOURCE_IDS)
def test_every_cross_reference_names_a_file_that_exists(path):
    broken = [
        f"{path.relative_to(ROOT)}:{line_no}: {ref} -> no such file"
        for line_no, line, ref in _references(path)
        if not _resolves(ref) and not _is_sibling_citation(line)
    ]
    assert not broken, "\n".join(broken)


def test_sibling_citations_are_exactly_the_known_ones():
    """The exemption must stay narrow.

    Every reference excused by SIBLING_MARKERS is listed here explicitly.
    A new unresolvable reference on a line that happens to mention the
    sibling programme therefore still fails, rather than being absorbed
    by the exemption.
    """
    excused = sorted(
        {
            (str(path.relative_to(ROOT)), ref)
            for path in SOURCES
            for _, line, ref in _references(path)
            if not _resolves(ref) and _is_sibling_citation(line)
        }
    )
    # The list is empty on purpose, and the reason is worth keeping.
    #
    # It used to hold three entries: bare `docs/25` and `docs/27` in
    # docs/16, and `docs/27` in docs/17, all citing the sibling
    # programme. That was safe only while this repository had no
    # documents at those numbers. On 2026-08-30 `docs/25-sky130-6x2.md`
    # landed, and the bare form in docs/16 silently began resolving to
    # it -- a citation of another project's work pointing at ours, in
    # the generated site, with nothing to say so. This test caught it.
    #
    # The fix was to write sibling citations in a path form the
    # generator cannot match (`radhard-edge-ai/docs/27`), which is now
    # the convention. Keeping this list empty means the next bare
    # sibling reference fails here rather than waiting for a number
    # collision to make it wrong.
    assert excused == [], excused


def test_named_references_use_the_real_filename():
    """"docs/12-sg13g2-flow-bringup.md" must match the file exactly.

    A reference that carries the full filename is checkable character by
    character, unlike a bare "docs/12". This is where a rename shows up.
    """
    wrong = []
    for path in SOURCES:
        for line_no, line, ref in _references(path):
            m = build_docs.DOC_REF.fullmatch(ref)
            if not m.group(2):
                continue
            filename = f"{m.group(1)}{m.group(2)}"
            if filename in DOC_FILENAMES:
                continue
            if _is_sibling_citation(line):
                continue
            near = sorted(n for n in DOC_FILENAMES if n.startswith(m.group(1)))
            wrong.append(
                f"{path.relative_to(ROOT)}:{line_no}: {ref}; "
                f"docs/ has {near or 'no such number'}"
            )
    assert not wrong, "\n".join(wrong)


# ----------------------------------------------------------------------
# Property 2: every document is reachable from the index
# ----------------------------------------------------------------------


def test_index_exists():
    assert INDEX.is_file(), f"{INDEX} is the entry point and must exist"


def test_every_document_is_reachable_from_the_index():
    index_text = INDEX.read_text(encoding="utf-8")
    missing = []
    for path in SOURCES:
        if path == INDEX:
            continue
        rel = (
            f"docs/{path.name}"
            if path.parent.name == "docs"
            else path.name
        )
        if rel not in index_text:
            missing.append(rel)
    assert not missing, (
        "not named in docs/00-index.md, so unreachable from the entry "
        f"point: {missing}"
    )


def test_index_names_no_document_that_does_not_exist():
    """The inverse: the index must not advertise a file that is gone."""
    index_text = INDEX.read_text(encoding="utf-8")
    dangling = sorted(
        {
            ref
            for _, line, ref in _references(INDEX)
            if not _resolves(ref) and not _is_sibling_citation(line)
        }
    )
    assert not dangling, dangling
    for name in ("README.md", "ROADMAP.md"):
        if name in index_text:
            assert (ROOT / name).is_file(), name


# ----------------------------------------------------------------------
# Property 3: the site generator turns those references into real links
# ----------------------------------------------------------------------


def test_generator_resolves_every_resolvable_reference(tmp_path):
    """Build the site and require that nothing resolvable is left bare.

    This is the end-to-end check: the two properties above are about the
    source text, this one is about what the reader actually gets.
    """
    out = tmp_path / "_site"
    rc = build_docs.build(out, renderer="builtin", strict=False, quiet=True)
    assert rc == 0

    import json

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["cross_references_resolved"] > 500, manifest

    # Everything the generator could not resolve must be a sibling citation.
    for item in manifest["unresolved"]:
        context = _context_at(ROOT / item["file"], item["line"])
        assert _is_sibling_citation(context), item

    # Every page the index links to was actually written.
    pages = set(manifest["pages"])
    index_html = (out / "index.html").read_text(encoding="utf-8")
    for href in re.findall(r'href="([^"#]+\.html)"', index_html):
        assert href in pages, f"index.html links to missing page {href}"
