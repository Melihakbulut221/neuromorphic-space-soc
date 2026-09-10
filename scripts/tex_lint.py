#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Structural checks on the paper source, for a machine with no TeX.

    python3 scripts/tex_lint.py paper/main.tex

WHAT THIS IS NOT. It is not a compile, and nothing it says is evidence
that the document builds. There is no TeX installation on the machine
this paper is written on -- pdflatex, xelatex, lualatex, latexmk and
tectonic are all absent, apt needs a password, and the continuous
integration that would have built it has not started since 2026-09-03.

So this checks the class of defect that a compile would catch and that a
reader cannot see: a reference with no label, a citation with no entry,
an environment left open, a brace left unbalanced, a special character
left unescaped outside verbatim. Every one of those is a hard error or a
silent wrong rendering, and every one is decidable without a typesetter.

WHAT IT CANNOT CATCH, and the list is the reason the paper says the
build is unverified: a missing package, a macro that does not exist, a
table wider than the page, an option a package version rejects, a float
that will not place, and anything about the bibliography style's output.
"""

import re
import sys
from pathlib import Path

SPECIALS = [
    (r"(?<!\\)%", "unescaped % (comment marker)"),
    (r"(?<!\\)&", "unescaped & (alignment tab)"),
    (r"(?<!\\)#", "unescaped # (parameter)"),
]


def strip_verbatim_and_comments(text):
    """Remove what the specials rule must not look at.

    Verbatim is literal by definition, and a comment is already a
    comment. Both are replaced by blank lines rather than deleted so
    that reported line numbers stay true.
    """
    def blank(m):
        return "\n" * m.group(0).count("\n")
    text = re.sub(r"\\begin\{verbatim\}.*?\\end\{verbatim\}", blank, text,
                  flags=re.S)
    out = []
    for line in text.split("\n"):
        i, esc = 0, False
        cut = len(line)
        while i < len(line):
            if line[i] == "\\":
                esc = not esc
            else:
                if line[i] == "%" and not esc:
                    cut = i
                    break
                esc = False
            i += 1
        out.append(line[:cut])
    return "\n".join(out)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: tex_lint.py <main.tex>")
    tex_path = Path(sys.argv[1])
    tex = tex_path.read_text(encoding="utf-8")
    bib_path = tex_path.parent / "refs.bib"
    problems = []

    # 1. references and labels
    labels = set(re.findall(r"\\label\{([^}]+)\}", tex))
    refs = set(re.findall(r"\\(?:page)?ref\{([^}]+)\}", tex))
    for r in sorted(refs - labels):
        problems.append(f"\\ref{{{r}}} has no \\label")

    # 2. citations against the bibliography
    if bib_path.is_file():
        bib = bib_path.read_text(encoding="utf-8")
        keys = set(re.findall(r"^@\w+\{([^,]+),", bib, re.M))
        cited = set()
        for m in re.findall(r"\\cite\w*\{([^}]+)\}", tex):
            cited |= {c.strip() for c in m.split(",")}
        for c in sorted(cited - keys):
            problems.append(f"\\cite{{{c}}} is in no entry of refs.bib")
        if bib.count("{") != bib.count("}"):
            problems.append(
                f"refs.bib braces unbalanced by {bib.count('{') - bib.count('}')}")
    else:
        problems.append("refs.bib not found beside the document")

    # 3. environments
    begins = re.findall(r"\\begin\{(\w+\*?)\}", tex)
    ends = re.findall(r"\\end\{(\w+\*?)\}", tex)
    for env in sorted(set(begins) | set(ends)):
        b, e = begins.count(env), ends.count(env)
        if b != e:
            problems.append(f"environment {env}: {b} begin, {e} end")

    # 4. braces, over the whole file including verbatim
    if tex.count("{") != tex.count("}"):
        problems.append(
            f"braces unbalanced by {tex.count('{') - tex.count('}')}")

    # 5. special characters in body text.
    #
    # Two of the three are legitimate in context and the check has to
    # know where: `&` is the column separator inside a tabular-like
    # environment, and `#` is a parameter reference inside a macro
    # definition. A linter that reports both as errors is a linter
    # whose output gets skimmed, which is worse than no linter.
    body = strip_verbatim_and_comments(tex)
    lines = body.split("\n")
    ALIGN_ENVS = ("tabular", "tabularx", "tabular*", "array", "align",
                  "align*", "matrix", "pmatrix", "bmatrix", "cases")
    DEFINERS = (r"\\newcommand", r"\\renewcommand", r"\\providecommand",
                r"\\def", r"\\newcolumntype", r"\\newenvironment",
                r"\\renewenvironment", r"\\DeclareRobustCommand")
    depth = 0
    in_align = []
    for n, line in enumerate(lines, 1):
        for env in re.findall(r"\\begin\{(\w+\*?)\}", line):
            if env in ALIGN_ENVS:
                depth += 1
        inside = depth > 0
        for env in re.findall(r"\\end\{(\w+\*?)\}", line):
            if env in ALIGN_ENVS:
                depth = max(0, depth - 1)
        in_align.append(inside)
    for pat, what in SPECIALS:
        for m in re.finditer(pat, body):
            n = body[:m.start()].count("\n") + 1
            ctx = lines[n - 1]
            if what.startswith("unescaped &") and in_align[n - 1]:
                continue
            if what.startswith("unescaped #") and any(
                    re.search(d, ctx) for d in DEFINERS):
                continue
            problems.append(f"line {n}: {what}: {ctx.strip()[:70]}")

    # 6. the document must be closed
    if tex.count(r"\begin{document}") != 1 or tex.count(r"\end{document}") != 1:
        problems.append("document environment is not exactly one begin/end pair")

    for p in problems:
        print("FAIL:", p)
    unused = sorted(labels - refs)
    print(f"\n{len(labels)} labels, {len(refs)} references, "
          f"{len(unused)} labels never referenced (not an error)")
    print(f"{len(problems)} structural problem(s)")
    print("THIS IS NOT A COMPILE. See the module docstring for what it "
          "cannot catch.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
