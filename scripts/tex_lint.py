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

Of the three special characters, `%` is the one that renders WRONG
rather than failing: `87%` prints `87` and eats the rest of the line.
Until 2026-09-10 the rule for it could not fire -- it was run against a
string a comment-stripper had already emptied of every character it
could match -- and what it matches now is narrower than the line above
implies. Read the PERCENT note in the source for the exact scope.

WHAT IT CANNOT CATCH, and the list is the reason the paper says the
build is unverified: a missing package, a macro that does not exist, a
table wider than the page, an option a package version rejects, a float
that will not place, anything about the bibliography style's output, and
-- see the PERCENT note -- a `%` written for a percent sign with a space
in front of it, which no rule can tell from a comment.
"""

import re
import sys
from pathlib import Path

SPECIALS = [
    (r"(?<!\\)&", "unescaped & (alignment tab)"),
    (r"(?<!\\)#", "unescaped # (parameter)"),
]

# The percent rule, and why it is not in the list above.
#
# It used to be, as `(?<!\\)%` run over the output of what was then a
# single strip_verbatim_and_comments() and is now strip_comments()
# below. That pass truncates every line at its first unescaped `%`, so
# by construction NO unescaped `%` survived into the string the rule was
# searching. The rule matched nothing, could match nothing, and had
# matched nothing since it was written; the
# docstring below still advertised it. Found and repaired 2026-09-10.
#
# The repair runs it against the source with verbatim blanked and
# COMMENTS KEPT, which needs a sharper pattern, because in LaTeX an
# unescaped `%` is not an error -- it is the comment marker, and this
# document opens with eleven lines of comment. What is a defect is a `%`
# the author meant as a percent sign: `87%` renders as `87` and silently
# swallows the rest of the line. So the rule fires only on an unescaped
# `%` GLUED to a preceding non-space character, which is where a percent
# sign appears and where a comment marker conventionally does not.
#
# NOT COVERED, and stated rather than implied: a `%` at the start of a
# line or after whitespace is indistinguishable from a deliberate comment
# by any rule that does not read the author's mind, so `50 %` written for
# "50 percent" passes here. Nor does this fire after a backslash, so the
# `\\%` in `... \\% ...` -- a line break followed by a comment -- is
# skipped with everything genuinely escaped as `\%`. Both are misses the
# rule accepts in order to be a rule whose output is read.
PERCENT = (r"(?<=\S)(?<!\\)%",
           "unescaped % glued to text (comment marker, not a percent sign)")


def strip_verbatim(text):
    """Blank out verbatim blocks, which are literal by definition.

    Replaced by newlines rather than deleted so that reported line
    numbers stay true.
    """
    def blank(m):
        return "\n" * m.group(0).count("\n")
    return re.sub(r"\\begin\{verbatim\}.*?\\end\{verbatim\}", blank, text,
                  flags=re.S)


def strip_comments(text):
    """Cut each line at its first unescaped `%`.

    A comment is already a comment, so the `&` and `#` rules must not
    look inside one. Nothing is joined or removed wholesale, so line
    numbers survive.
    """
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
    # Two subjects, because the two rules need different ones. `&` and
    # `#` must not see inside a comment; `%` must see nothing BUT what a
    # comment-stripper would have eaten, so it reads the source with only
    # verbatim blanked. See the PERCENT note at the top of this file.
    novrb = strip_verbatim(tex)
    body = strip_comments(novrb)
    lines = body.split("\n")
    raw_lines = novrb.split("\n")
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

    pat, what = PERCENT
    for m in re.finditer(pat, novrb):
        n = novrb[:m.start()].count("\n") + 1
        ctx = raw_lines[n - 1]
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
