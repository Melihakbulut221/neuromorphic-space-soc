#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Build a browsable static site from the repository's markdown corpus.

Inputs are read from disk at build time: every `docs/*.md`, plus `README.md`
and `ROADMAP.md`. Nothing about their content is embedded here, so the
generator stays correct while those files are being edited.

What it does that plain `pandoc file.md` does not:

  1. Resolves cross-references. The corpus refers to its own documents as
     bare prose -- "docs/06 section B.6", "`docs/12-sg13g2-flow-bringup.md`"
     -- with no markdown link syntax anywhere. Every such reference whose
     target exists is rewritten into a real hyperlink before conversion. A
     reference whose target does not exist is left as plain text: this
     generator never emits a link it cannot resolve. `sw/tests/
     test_doc_links.py` is the gate that decides whether an unresolvable
     reference is acceptable.
  2. Emits a table of contents per document.
  3. Emits `all-documents.html`, a generated listing of every source file
     with its title and one-line purpose, so a document cannot be absent
     from the site merely because the hand-written index has not caught up
     with it yet.

Rendering backend. `--renderer auto` (the default) uses pandoc when it is
on PATH and the built-in renderer otherwise; the choice is printed in the
build summary. The built-in renderer is a markdown subset covering exactly
what this corpus uses -- ATX headings, paragraphs, GFM pipe tables, fenced
and inline code, bold, italic, links, ordered and unordered lists, block
quotes and horizontal rules. Pure standard library, no network, no root.

Usage:
    python3 scripts/build_docs.py [--out _site] [--renderer auto|pandoc|builtin]
                                  [--strict] [--quiet]
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# A cross-reference to a document of this repository. Matches the bare form
# ("docs/06") and the full-filename form ("docs/06-funding-and-shuttle.md").
# The leading lookbehind keeps it from firing inside a longer path and the
# trailing lookahead keeps "docs/00_index.md" -- a mention of another
# project's file -- from being read as a reference to ours.
DOC_REF = re.compile(r"(?<![\w/.\-])docs/(\d{2})(-[a-z0-9\-]+\.md)?(?![\w\-])")

# Root-level documents that the corpus also refers to by name.
ROOT_REF = re.compile(r"(?<![\w/.\-])(README|ROADMAP)\.md(?![\w\-])")

FENCE = re.compile(r"^\s*(```+|~~~+)")


# --------------------------------------------------------------------------
# Source model
# --------------------------------------------------------------------------


@dataclass
class Document:
    """One markdown source file and everything derived from it."""

    path: Path  # absolute
    rel: str  # repository-relative, e.g. "docs/06-funding-and-shuttle.md"
    slug: str  # output basename without extension
    number: str | None  # "06" for docs/NN-*.md, None for README/ROADMAP
    text: str = ""
    title: str = ""
    purpose: str = ""
    headings: list[tuple[int, str, str]] = field(default_factory=list)
    resolved: str = ""
    refs_out: int = 0
    refs_unresolved: list[tuple[int, str]] = field(default_factory=list)

    @property
    def out_name(self) -> str:
        return f"{self.slug}.html"


def discover(root: Path) -> list[Document]:
    """Collect the corpus from disk, in reading order."""
    docs: list[Document] = []
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        for path in sorted(docs_dir.glob("*.md")):
            stem = path.stem
            m = re.match(r"^(\d{2})-", stem)
            number = m.group(1) if m else None
            # docs/00-index.md becomes the landing page.
            slug = "index" if stem == "00-index" else stem
            docs.append(
                Document(
                    path=path,
                    rel=f"docs/{path.name}",
                    slug=slug,
                    number=number,
                )
            )
    for name in ("README.md", "ROADMAP.md"):
        path = root / name
        if path.is_file():
            docs.append(
                Document(path=path, rel=name, slug=path.stem, number=None)
            )
    for doc in docs:
        doc.text = path_read(doc.path)
        doc.title = extract_title(doc.text) or doc.rel
        doc.purpose = extract_purpose(doc.text)
        doc.headings = extract_headings(doc.text)
    return docs


def path_read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_title(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return strip_inline_markup(line[2:].strip())
    return ""


def extract_purpose(text: str) -> str:
    """First sentence of the first prose paragraph after the H1.

    A one-line statement of what the document is for, taken from the
    document itself rather than restated here. Truncated at the first
    sentence boundary so the index listing stays scannable.
    """
    lines = text.splitlines()
    i = 0
    while i < len(lines) and not lines[i].startswith("# "):
        i += 1
    i += 1
    para: list[str] = []
    in_fence = False
    while i < len(lines):
        line = lines[i]
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            if line.strip():
                if line.startswith(("#", "|", ">", "<!--")):
                    if para:
                        break
                    i += 1
                    continue
                para.append(line.strip())
            elif para:
                break
        i += 1
    if not para:
        return ""
    prose = strip_inline_markup(" ".join(para))
    prose = re.sub(r"\s+", " ", prose).strip()
    # First sentence: a period/colon followed by whitespace and a capital or
    # end of string. Abbreviations inside the corpus ("nm.", "v0.1") do not
    # match because the period there is not followed by space+capital.
    m = re.search(r"(?<=[.:;])\s+(?=[A-Z(])", prose)
    if m:
        prose = prose[: m.start()]
    prose = prose.rstrip(" .;:")
    if len(prose) > 220:
        cut = prose.rfind(" ", 0, 217)
        prose = prose[: cut if cut > 0 else 217] + "..."
    return prose


def strip_inline_markup(s: str) -> str:
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"\*\*([^*]*)\*\*", r"\1", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    return s.strip()


def extract_headings(text: str) -> list[tuple[int, str, str]]:
    """(level, text, anchor id) for every ATX heading outside code fences."""
    out: list[tuple[int, str, str]] = []
    seen: dict[str, int] = {}
    in_fence = False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if not m:
            continue
        level = len(m.group(1))
        label = strip_inline_markup(m.group(2))
        if not label:
            continue
        out.append((level, label, slugify(label, seen)))
    return out


def slugify(label: str, seen: dict[str, int]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "section"
    n = seen.get(base, 0)
    seen[base] = n + 1
    return base if n == 0 else f"{base}-{n}"


# --------------------------------------------------------------------------
# Cross-reference resolution
# --------------------------------------------------------------------------


def build_targets(docs: list[Document]) -> tuple[dict[str, Document], dict[str, Document]]:
    """Map "06" and "06-funding-and-shuttle.md" alike onto their document."""
    by_number: dict[str, Document] = {}
    by_filename: dict[str, Document] = {}
    for doc in docs:
        if not doc.rel.startswith("docs/"):
            continue
        by_filename[doc.path.name] = doc
        # docs/00-index.md shares the number 00 with docs/00-reference-brief.md
        # and must not capture it: the corpus's bare "docs/00" references all
        # predate the index and mean the reference brief.
        if doc.number is not None and doc.slug != "index":
            by_number.setdefault(doc.number, doc)
    return by_number, by_filename


def split_fences(text: str) -> list[tuple[bool, str]]:
    """Split into (is_code, chunk) runs so fenced blocks are left untouched."""
    out: list[tuple[bool, str]] = []
    buf: list[str] = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        if FENCE.match(line):
            out.append((in_fence, "".join(buf)))
            buf = [line]
            in_fence = not in_fence
            continue
        buf.append(line)
    out.append((in_fence, "".join(buf)))
    return [(c, t) for c, t in out if t]


# Inline code spans are matched one line at a time and only in the simple
# single-backtick form. Pairing backticks across a whole chunk looks tidier
# but is wrong on this corpus: one stray backtick anywhere flips the parity
# of everything after it, and hundreds of lines of prose then look like code
# and are skipped. Line scope confines any such damage to its own line.
CODE_SPAN = re.compile(r"`[^`\n]+`")

# A reference cited with a line number, as the review documents do:
# `docs/01-reference-decomposition.md:228`. The line number is dropped --
# the site has no per-line anchors -- but the reference still resolves.
LINE_SUFFIX = re.compile(r":\d+$")


def resolve_refs(doc: Document, by_number, by_filename, root_docs) -> None:
    """Rewrite in-repo references into markdown links, in place on the doc.

    Three forms are handled:

      `docs/12-sg13g2-flow-bringup.md`  -- a code span that is exactly one
          reference becomes a link whose text is still code.
      docs/06                           -- bare prose reference.
      `ROADMAP.md`, `README.md:36`      -- root-level document, same rules.

    A reference to the document being processed is left alone; a reference
    whose target is missing from disk is recorded in doc.refs_unresolved and
    also emitted unchanged. This function never emits a broken link.
    """
    count = 0
    unresolved: list[tuple[int, str]] = []

    def target_for(text: str):
        text = LINE_SUFFIX.sub("", text)
        m = DOC_REF.fullmatch(text)
        if m:
            num, name = m.group(1), m.group(2)
            if name:
                return by_filename.get(f"{num}{name}")
            return by_number.get(num)
        m = ROOT_REF.fullmatch(text)
        if m:
            return root_docs.get(m.group(0))
        return None

    def is_reference(text: str) -> bool:
        text = LINE_SUFFIX.sub("", text)
        return bool(DOC_REF.fullmatch(text) or ROOT_REF.fullmatch(text))

    def rewrite_plain(segment: str, line: int) -> str:
        nonlocal count

        def sub(m: re.Match) -> str:
            nonlocal count
            dest = target_for(m.group(0))
            if dest is None:
                unresolved.append((line, m.group(0)))
                return m.group(0)
            if dest is doc:
                return m.group(0)
            count += 1
            return f"[{m.group(0)}]({dest.out_name})"

        return ROOT_REF.sub(sub, DOC_REF.sub(sub, segment))

    out_lines: list[str] = []
    line_no = 0
    for is_code, chunk in split_fences(doc.text):
        for raw in chunk.splitlines(keepends=True):
            line_no += 1
            if is_code:
                out_lines.append(raw)
                continue
            body = raw.rstrip("\n")
            tail = raw[len(body) :]
            pos = 0
            pieces: list[str] = []
            for m in CODE_SPAN.finditer(body):
                pieces.append(rewrite_plain(body[pos : m.start()], line_no))
                inner = m.group(0)[1:-1]
                dest = target_for(inner)
                if dest is not None and dest is not doc:
                    count += 1
                    pieces.append(f"[`{inner}`]({dest.out_name})")
                else:
                    if dest is None and is_reference(inner):
                        unresolved.append((line_no, inner))
                    pieces.append(m.group(0))
                pos = m.end()
            pieces.append(rewrite_plain(body[pos:], line_no))
            out_lines.append("".join(pieces) + tail)

    doc.resolved = "".join(out_lines)
    doc.refs_out = count
    doc.refs_unresolved = unresolved


# --------------------------------------------------------------------------
# Built-in markdown renderer
# --------------------------------------------------------------------------

INLINE = re.compile(
    r"(?P<code>`+[^`]*`+)"
    r"|(?P<link>\[(?P<ltext>(?:[^\[\]]|\[[^\]]*\])*)\]\((?P<lurl>[^()\s]*)\))"
    r"|(?P<auto><(?P<aurl>https?://[^>\s]+)>)"
    # Bare URLs. The research documents cite sources this way and GFM
    # turns them into links, so the built-in renderer must too.
    # A URL inside a markdown link destination is never reached: the link
    # alternative above matches first at that position and consumes it.
    r"|(?P<bare>(?<![\w<])https?://[^\s<>\"`\]]+)"
)

# Sentence punctuation at the end of a bare URL belongs to the sentence.
URL_TAIL = re.compile(r"[.,;:!?]+$")


def inline_html(text: str) -> str:
    """Render one run of inline markdown.

    Code spans, links and autolinks are lifted out to placeholders before
    emphasis is applied, so that bold spanning a code span -- which this
    corpus writes constantly, as in **[fact, `docs/15` section 4]** --
    is still recognised as one run.
    """
    held: list[str] = []

    def hold(rendered: str) -> str:
        held.append(rendered)
        return f"\x00{len(held) - 1}\x01"

    def sub(m: re.Match) -> str:
        if m.group("code"):
            body = m.group("code").strip("`")
            return hold(f"<code>{html.escape(body, quote=False)}</code>")
        if m.group("link"):
            url = html.escape(m.group("lurl"), quote=True)
            return hold(f'<a href="{url}">{inline_html(m.group("ltext"))}</a>')
        if m.group("auto"):
            url = html.escape(m.group("aurl"), quote=True)
            return hold(f'<a href="{url}">{url}</a>')
        raw = m.group("bare")
        trimmed = URL_TAIL.sub("", raw)
        while trimmed.endswith(")") and trimmed.count("(") < trimmed.count(")"):
            trimmed = trimmed[:-1]
        url = html.escape(trimmed, quote=True)
        return hold(f'<a href="{url}">{url}</a>') + raw[len(trimmed) :]

    body = emphasis(html.escape(INLINE.sub(sub, text), quote=False))
    return re.sub(r"\x00(\d+)\x01", lambda m: held[int(m.group(1))], body)


def emphasis(text: str) -> str:
    text = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(
        r"(?<![\w*])\*(?=[^\s*])([^*]+?)(?<=[^\s*])\*(?![\w*])",
        r"<em>\1</em>",
        text,
    )
    return text


LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")


def render_markdown(text: str, headings: list[tuple[int, str, str]]) -> str:
    """Render the corpus's markdown subset to HTML."""
    anchors = {(lvl, lbl): hid for lvl, lbl, hid in headings}
    seen: dict[str, int] = {}
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        fence = FENCE.match(line)
        if fence:
            marker = fence.group(1)[0] * 3
            body: list[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith(marker):
                body.append(lines[i])
                i += 1
            i += 1
            code = html.escape("\n".join(body), quote=False)
            out.append(f"<pre><code>{code}\n</code></pre>")
            continue

        if not line.strip():
            i += 1
            continue

        # Indented code block. The verification and flow documents record
        # terminal transcripts this way rather than in fences, so dropping
        # them into paragraphs would re-wrap command output into prose.
        if line.startswith("    "):
            body = []
            while i < n and (lines[i].startswith("    ") or not lines[i].strip()):
                body.append(lines[i][4:] if lines[i].startswith("    ") else "")
                i += 1
            while body and not body[-1].strip():
                body.pop()
            out.append(
                "<pre><code>"
                + html.escape("\n".join(body), quote=False)
                + "\n</code></pre>"
            )
            continue

        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            level = len(m.group(1))
            label = strip_inline_markup(m.group(2))
            hid = anchors.get((level, label))
            if hid is None:
                hid = slugify(label, seen)
            out.append(
                f'<h{level} id="{html.escape(hid, quote=True)}">'
                f"{inline_html(m.group(2))}</h{level}>"
            )
            i += 1
            continue

        if re.match(r"^\s*([-*_])(\s*\1){2,}\s*$", line):
            out.append("<hr>")
            i += 1
            continue

        # GFM pipe table: a header row followed by a delimiter row.
        if line.lstrip().startswith("|") and i + 1 < n and is_delim(lines[i + 1]):
            rows = []
            header = split_row(line)
            i += 2
            while i < n and lines[i].lstrip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            out.append(render_table(header, rows))
            continue

        if line.lstrip().startswith(">"):
            body = []
            while i < n and (lines[i].lstrip().startswith(">") or lines[i].strip()):
                body.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append(
                "<blockquote>"
                + render_markdown("\n".join(body), headings)
                + "</blockquote>"
            )
            continue

        if LIST_ITEM.match(line):
            block, i = collect_list(lines, i)
            out.append(block)
            continue

        para: list[str] = []
        while i < n and lines[i].strip():
            if (
                FENCE.match(lines[i])
                or lines[i].startswith("#")
                or LIST_ITEM.match(lines[i])
                or lines[i].lstrip().startswith("|")
            ):
                break
            para.append(lines[i].strip())
            i += 1
        if para:
            out.append("<p>" + inline_html(" ".join(para)) + "</p>")
        else:
            i += 1

    return "\n".join(out)


def is_delim(line: str) -> bool:
    s = line.strip()
    return bool(s.startswith("|") and re.fullmatch(r"[|:\-\s]+", s) and "-" in s)


def split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    # Split on unescaped pipes only.
    cells = re.split(r"(?<!\\)\|", s)
    return [c.strip().replace("\\|", "|") for c in cells]


def render_table(header: list[str], rows: list[list[str]]) -> str:
    width = len(header)
    parts = ["<table>", "<thead><tr>"]
    parts += [f"<th>{inline_html(c)}</th>" for c in header]
    parts.append("</tr></thead>")
    if rows:
        parts.append("<tbody>")
        for row in rows:
            cells = (row + [""] * width)[:width]
            parts.append(
                "<tr>" + "".join(f"<td>{inline_html(c)}</td>" for c in cells) + "</tr>"
            )
        parts.append("</tbody>")
    parts.append("</table>")
    return "".join(parts)


def collect_list(lines: list[str], i: int) -> tuple[str, int]:
    """Render one list block, honouring indentation for nesting."""
    n = len(lines)
    base_m = LIST_ITEM.match(lines[i])
    assert base_m is not None
    base_indent = len(base_m.group(1))
    ordered = bool(re.match(r"\d", base_m.group(2)))
    items: list[list[str]] = []

    while i < n:
        line = lines[i]
        if not line.strip():
            # A blank line ends the list unless the next line continues it.
            # When it does continue, the blank line is kept: it is what
            # separates an item's lead paragraph from a nested table or
            # sub-list, and dropping it flattens both back into prose.
            if i + 1 < n and (
                LIST_ITEM.match(lines[i + 1])
                or (
                    lines[i + 1].strip()
                    and len(lines[i + 1]) - len(lines[i + 1].lstrip()) > base_indent
                )
            ):
                if items:
                    items[-1].append("")
                i += 1
                continue
            i += 1
            break
        m = LIST_ITEM.match(line)
        indent = len(line) - len(line.lstrip())
        if m and indent <= base_indent:
            items.append([m.group(3)])
            i += 1
            continue
        if not items:
            break
        if indent > base_indent or not m:
            items[-1].append(line[base_indent:] if indent >= base_indent else line.strip())
            i += 1
            continue
        break

    tag = "ol" if ordered else "ul"
    parts = [f"<{tag}>"]
    for item in items:
        body = "\n".join(item)
        if any(LIST_ITEM.match(l) for l in item[1:]) or "\n\n" in body:
            parts.append("<li>" + render_markdown(dedent_block(body), []) + "</li>")
        else:
            flat = " ".join(l.strip() for l in item if l.strip())
            parts.append("<li>" + inline_html(flat) + "</li>")
    parts.append(f"</{tag}>")
    return "".join(parts), i


def dedent_block(text: str) -> str:
    lines = text.splitlines()
    widths = [len(l) - len(l.lstrip()) for l in lines[1:] if l.strip()]
    cut = min(widths) if widths else 0
    return "\n".join(
        [lines[0]] + [l[cut:] if len(l) >= cut else l for l in lines[1:]]
    )


# --------------------------------------------------------------------------
# Page assembly
# --------------------------------------------------------------------------

STYLE = """\
:root { color-scheme: dark; }
body { max-width: 62rem; margin: 0 auto; padding: 1.5rem 1.25rem 5rem;
       font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica,
                    Arial, sans-serif;
       line-height: 1.65; color: #c9d1d9; background: #0d1117; }
a { color: #58a6ff; text-decoration: none; }
a:hover { text-decoration: underline; }
h1, h2, h3, h4, h5, h6 { color: #e6edf3; line-height: 1.3; }
h1 { font-size: 1.8rem; border-bottom: 1px solid #30363d; padding-bottom: .3em; }
h2 { font-size: 1.35rem; margin-top: 2.2em; border-bottom: 1px solid #21262d;
     padding-bottom: .3em; }
h3 { font-size: 1.1rem; margin-top: 1.8em; }
nav.site { display: flex; flex-wrap: wrap; gap: .4rem 1rem; font-size: .85rem;
           padding-bottom: .8rem; margin-bottom: 1.4rem;
           border-bottom: 1px solid #21262d; }
nav.site .sep { color: #484f58; }
nav.toc { background: #161b22; border: 1px solid #30363d; border-radius: 6px;
          padding: .9rem 1.2rem; margin: 1.6rem 0 2.2rem; font-size: .92rem; }
nav.toc p.label { margin: 0 0 .5rem; font-weight: 600; color: #e6edf3;
                  font-size: .8rem; letter-spacing: .06em;
                  text-transform: uppercase; }
nav.toc ul { list-style: none; margin: 0; padding-left: 0; }
nav.toc ul ul { padding-left: 1.1rem; }
nav.toc li { margin: .18rem 0; }
pre { background: #161b22; border: 1px solid #30363d; border-radius: 6px;
      padding: .9rem 1rem; overflow-x: auto; }
code { font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo,
       monospace; font-size: .87em; background: #161b22; border-radius: 3px;
       padding: .12em .35em; }
pre code { background: none; padding: 0; }
a code { color: #58a6ff; }
table { border-collapse: collapse; margin: 1.2em 0; font-size: .92rem;
        display: block; overflow-x: auto; max-width: 100%; }
th, td { border: 1px solid #30363d; padding: .42rem .7rem;
         text-align: left; vertical-align: top; }
th { background: #161b22; font-weight: 600; color: #e6edf3; }
tr:nth-child(even) td { background: #10151c; }
blockquote { margin: 1em 0; padding: .1rem 1rem; border-left: 3px solid #30363d;
             color: #9aa4ae; }
hr { border: none; border-top: 1px solid #21262d; margin: 2em 0; }
ul, ol { padding-left: 1.5rem; }
li { margin: .25rem 0; }
footer { margin-top: 3.5rem; padding-top: 1rem; border-top: 1px solid #21262d;
         font-size: .82rem; color: #7d8590; }
.purpose { color: #9aa4ae; }
@media (max-width: 600px) { body { padding: 1rem .8rem 3rem; } }
"""

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
{nav}
{body}
<footer>{footer}</footer>
</body>
</html>
"""


def nav_bar(doc: Document | None, docs: list[Document]) -> str:
    items = ['<a href="index.html">Index</a>', '<a href="all-documents.html">All documents</a>']
    ordered = [d for d in docs if d.slug != "index"]
    if doc is not None and doc in ordered:
        k = ordered.index(doc)
        if k > 0:
            items.append(f'<a href="{ordered[k-1].out_name}">Previous</a>')
        if k + 1 < len(ordered):
            items.append(f'<a href="{ordered[k+1].out_name}">Next</a>')
    if doc is not None:
        items.append(f"<span class=\"sep\">source: <code>{html.escape(doc.rel)}</code></span>")
    return '<nav class="site">' + '<span class="sep">|</span>'.join(items) + "</nav>"


def toc_html(headings: list[tuple[int, str, str]]) -> str:
    body = [h for h in headings if 2 <= h[0] <= 3]
    if len(body) < 2:
        return ""
    parts = ['<nav class="toc"><p class="label">Contents</p><ul>']
    depth = 2
    for level, label, hid in body:
        while depth < level:
            parts.append("<ul>")
            depth += 1
        while depth > level:
            parts.append("</ul>")
            depth -= 1
        parts.append(
            f'<li><a href="#{html.escape(hid, quote=True)}">'
            f"{html.escape(label, quote=False)}</a></li>"
        )
    while depth > 2:
        parts.append("</ul>")
        depth -= 1
    parts.append("</ul></nav>")
    return "".join(parts)


# Pandoc puts the table of contents in the document template, so `--toc`
# alone produces nothing when the output is a fragment. This template asks
# for the fragment plus the TOC, in the same markup the built-in renderer
# emits, so the two backends produce interchangeable pages.
PANDOC_TEMPLATE = """$if(toc)$
<nav class="toc"><p class="label">Contents</p>
$toc$
</nav>
$endif$
$body$
"""


def run_pandoc(markdown: str, title: str, workdir: Path) -> str | None:
    """Convert with pandoc, returning the HTML body fragment, or None."""
    src = workdir / "page.md"
    src.write_text(markdown, encoding="utf-8")
    template = workdir / "fragment.html"
    if not template.exists():
        template.write_text(PANDOC_TEMPLATE, encoding="utf-8")
    cmd = [
        "pandoc",
        str(src),
        # tex_math_dollars is on by default in pandoc's gfm reader. This
        # corpus is full of currency and of shell transcripts, so a line
        # such as "USD $400 ... $1,200" or a pair of `$ command` prompts
        # parses as inline LaTeX and is rendered character by character
        # as emphasis. Measured on docs/04: 144 spurious <em> elements and
        # several mangled figures. Both extensions are off here.
        "--from=gfm-tex_math_dollars-tex_math_gfm",
        "--to=html5",
        "--toc",
        "--toc-depth=3",
        # Without this pandoc hard-wraps its output at 72 columns, which
        # breaks tag attributes across lines. Harmless in a browser, but it
        # makes the two backends' output impossible to compare mechanically.
        "--wrap=none",
        f"--template={template}",
        f"--metadata=title:{title}",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        sys.stderr.write(f"warning: pandoc failed for {title}: {res.stderr.strip()[:300]}\n")
        return None
    return res.stdout


def all_documents_page(docs: list[Document]) -> str:
    rows = [
        "<h1>All documents</h1>",
        "<p class=\"purpose\">Generated from the files present in the working "
        "tree at build time. The purpose column is the first sentence of each "
        "document, taken from the document itself.</p>",
        "<table><thead><tr><th>Document</th><th>Title</th><th>Purpose</th>"
        "<th>Lines</th></tr></thead><tbody>",
    ]
    for doc in docs:
        lines = doc.text.count("\n") + 1
        rows.append(
            "<tr>"
            f'<td><a href="{doc.out_name}"><code>{html.escape(doc.rel)}</code></a></td>'
            f"<td>{html.escape(doc.title)}</td>"
            f'<td class="purpose">{html.escape(doc.purpose)}</td>'
            f"<td>{lines}</td>"
            "</tr>"
        )
    rows.append("</tbody></table>")
    return "\n".join(rows)


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def build(out_dir: Path, renderer: str, strict: bool, quiet: bool) -> int:
    docs = discover(REPO_ROOT)
    if not docs:
        sys.stderr.write("error: no markdown sources found\n")
        return 2

    by_number, by_filename = build_targets(docs)
    root_docs = {d.path.name: d for d in docs if not d.rel.startswith("docs/")}

    for doc in docs:
        resolve_refs(doc, by_number, by_filename, root_docs)

    use_pandoc = False
    if renderer in ("auto", "pandoc"):
        use_pandoc = shutil.which("pandoc") is not None
        if renderer == "pandoc" and not use_pandoc:
            sys.stderr.write("error: --renderer pandoc but pandoc is not on PATH\n")
            return 2
    backend = "pandoc" if use_pandoc else "builtin"

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    (out_dir / "style.css").write_text(STYLE, encoding="utf-8")

    workdir = out_dir / ".work"
    workdir.mkdir()

    total_refs = 0
    unresolved: list[tuple[str, int, str]] = []

    for doc in docs:
        total_refs += doc.refs_out
        for line, ref in doc.refs_unresolved:
            unresolved.append((doc.rel, line, ref))

        body = None
        if use_pandoc:
            body = run_pandoc(doc.resolved, doc.title, workdir)
        if body is None:
            body = toc_html(doc.headings) + render_markdown(doc.resolved, doc.headings)

        page = PAGE.format(
            title=html.escape(doc.title, quote=False),
            nav=nav_bar(doc, docs),
            body=body,
            footer=(
                f"Rendered from <code>{html.escape(doc.rel)}</code> by "
                f"<code>scripts/build_docs.py</code> ({backend} backend). "
                f"{doc.refs_out} cross-reference(s) resolved on this page."
            ),
        )
        (out_dir / doc.out_name).write_text(page, encoding="utf-8")

    (out_dir / "all-documents.html").write_text(
        PAGE.format(
            title="All documents",
            nav=nav_bar(None, docs),
            body=all_documents_page(docs),
            footer=f"{len(docs)} source files, {total_refs} cross-references resolved.",
        ),
        encoding="utf-8",
    )

    if not (out_dir / "index.html").exists():
        # No docs/00-index.md on disk: fall back to the generated listing so
        # the site still has a landing page.
        shutil.copyfile(out_dir / "all-documents.html", out_dir / "index.html")

    shutil.rmtree(workdir)

    manifest = {
        "backend": backend,
        "documents": len(docs),
        "cross_references_resolved": total_refs,
        "unresolved": [
            {"file": f, "line": ln, "reference": r} for f, ln, r in unresolved
        ],
        "pages": sorted(p.name for p in out_dir.glob("*.html")),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    if not quiet:
        print(f"backend:               {backend}")
        print(f"source documents:      {len(docs)}")
        print(f"pages written:         {len(list(out_dir.glob('*.html')))}")
        print(f"cross-references:      {total_refs} resolved")
        print(f"unresolved references: {len(unresolved)}")
        for f, ln, r in unresolved:
            print(f"  {f}:{ln}: {r}")
        print(f"output:                {out_dir}")

    if strict and unresolved:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(REPO_ROOT / "_site"), type=Path)
    ap.add_argument(
        "--renderer",
        default="auto",
        choices=("auto", "pandoc", "builtin"),
        help="auto uses pandoc when present, the built-in renderer otherwise",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero if any cross-reference could not be resolved",
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    return build(Path(args.out), args.renderer, args.strict, args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
