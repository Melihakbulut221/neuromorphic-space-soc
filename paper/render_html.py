#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Render paper/main.tex to readable HTML on a machine with no TeX.

    python3 paper/render_html.py paper/main.tex paper/main.html

THIS IS NOT A TYPESETTER AND THE OUTPUT IS NOT THE PAPER. It is a
faithful rendering of the document's text, tables and references, made
because there is no TeX installation here -- pdflatex, xelatex,
lualatex, latexmk and tectonic are all absent, apt wants a password, and
the continuous integration that would have built the PDF has not been
able to start since 2026-09-03.

What it handles is exactly the macro set this document uses and nothing
else, which is why it can be faithful at all: the command census is 45
distinct control sequences and eight environments. Anything outside that
set is passed through visibly rather than silently dropped, so a macro
this renderer does not know shows up in the output as itself and is
impossible to miss.

The HTML says all of this at the top of the page, because a reader who
prints it to PDF must not mistake it for the typeset article.
"""

import html
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- units
UNITS = [
    (r"\\micro\\meter\\squared", "&micro;m&sup2;"),
    (r"\\micro\\meter", "&micro;m"),
    (r"\\nano\\second", "ns"),
    (r"\\pico\\farad", "pF"),
    (r"\\milli\\meter\\squared", "mm&sup2;"),
    (r"\\milli\\watt", "mW"),
    (r"\\mega\\hertz", "MHz"),
    (r"\\meter\\squared", "m&sup2;"),
    (r"\\second", "s"),
    (r"\\meter", "m"),
    (r"\\percent", "%"),
]


def unit(s):
    for pat, rep in UNITS:
        s = re.sub(pat, rep, s)
    return s.strip()


def group(n):
    """39969214 -> 39,969,214, leaving decimals and non-numbers alone."""
    m = re.fullmatch(r"(-?)(\d+)(\.\d+)?", n.strip())
    if not m:
        return n
    sign, ip, fp = m.group(1), m.group(2), m.group(3) or ""
    if len(ip) >= 4:            # siunitx group-minimum-digits=4
        ip = f"{int(ip):,}"
    return sign + ip + fp


def braces(s, i):
    """Return (content, index after the closing brace) for s[i] == '{'."""
    assert s[i] == "{", s[i:i + 20]
    depth, j = 0, i
    while j < len(s):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    raise ValueError("unbalanced brace")


SIMPLE = {
    "textbf": "strong", "emph": "em", "texttt": "code", "file": "code",
    "textsc": "span class='sc'", "textit": "em", "mathbf": "strong",
}


def inline(s, ctx):
    """Expand inline markup. ctx carries labels, cites and counters."""
    out, i = [], 0
    while i < len(s):
        ch = s[i]
        if ch != "\\":
            out.append(html.escape(ch) if ch not in "<>&" else html.escape(ch))
            i += 1
            continue
        m = re.match(r"\\([a-zA-Z]+)\*?", s[i:])
        if not m:
            # an escaped special: \% \& \_ \# \$ \{ \}
            if i + 1 < len(s) and s[i + 1] in "%&_#${}":
                out.append(html.escape(s[i + 1]))
                i += 2
                continue
            out.append(html.escape(ch))
            i += 1
            continue
        name = m.group(1)
        j = i + m.end()
        if name in SIMPLE and j < len(s) and s[j] == "{":
            arg, j = braces(s, j)
            tag = SIMPLE[name]
            close = tag.split()[0]
            # textify, not inline: a nested argument needs the same
            # thin-space and quote substitutions as the surrounding
            # text, and calling inline directly left "130\,nm" raw.
            out.append(f"<{tag}>{textify(arg, ctx)}</{close}>")
        elif name == "SI" and j < len(s) and s[j] == "{":
            val, j = braces(s, j)
            u, j = braces(s, j) if j < len(s) and s[j] == "{" else ("", j)
            # NOT rstrip("&nbsp;") -- that strips the CHARACTER SET
            # & n b s p ;, so "25 ns" came out as "25". Found by reading
            # the output, which is the only way this class of bug is
            # ever found.
            u = unit(u)
            out.append(f"{group(val)}&nbsp;{u}" if u else group(val))
        elif name == "SIrange" and j < len(s) and s[j] == "{":
            a, j = braces(s, j)
            b, j = braces(s, j)
            u, j = braces(s, j)
            out.append(f"{group(a)}&ndash;{group(b)}&nbsp;{unit(u)}")
        elif name == "num" and j < len(s) and s[j] == "{":
            val, j = braces(s, j)
            out.append(group(val))
        elif name == "cite" and j < len(s) and s[j] == "{":
            keys, j = braces(s, j)
            nums = []
            for k in (x.strip() for x in keys.split(",")):
                if k not in ctx["cites"]:
                    ctx["cites"][k] = len(ctx["cites"]) + 1
                nums.append(str(ctx["cites"][k]))
            out.append("[" + ", ".join(nums) + "]")
        elif name == "ref" and j < len(s) and s[j] == "{":
            key, j = braces(s, j)
            out.append(f'<a href="#{key}">{ctx["labels"].get(key, "?")}</a>')
        elif name == "label" and j < len(s) and s[j] == "{":
            key, j = braces(s, j)
            out.append(f'<span id="{key}"></span>')
        elif name == "footnote" and j < len(s) and s[j] == "{":
            arg, j = braces(s, j)
            ctx["notes"].append(inline(arg, ctx))
            out.append(f'<sup>{len(ctx["notes"])}</sup>')
        elif name == "thanks" and j < len(s) and s[j] == "{":
            arg, j = braces(s, j)
            ctx["notes"].append(inline(arg, ctx))
            out.append(f'<sup>{len(ctx["notes"])}</sup>')
        elif name in ("ldots",):
            out.append("&hellip;")
        elif name in ("times",):
            out.append("&times;")
        elif name in ("pm",):
            out.append("&plusmn;")
        elif name in ("to",):
            out.append("&rarr;")
        elif name in ("oplus",):
            out.append("&oplus;")
        elif name in ("S",):
            out.append("&sect;")
        elif name in ("quad",):
            out.append("&emsp;")
        elif name in ("bar", "overline"):
            # Inside maths the argument is often a bare token rather than
            # a braced group: `\bar x_1`. Take the group if there is one,
            # otherwise the next non-space character.
            if j < len(s) and s[j] == "{":
                arg, j = braces(s, j)
            else:
                while j < len(s) and s[j] == " ":
                    j += 1
                arg, j = (s[j], j + 1) if j < len(s) else ("", j)
            out.append(f"<span style='text-decoration:overline'>"
                       f"{inline(arg, ctx)}</span>")
        elif name in ("small", "centering", "maketitle", "toprule",
                      "midrule", "bottomrule", "addlinespace", "hline",
                      "arraybackslash", "raggedright", "noindent"):
            pass
        elif name == "multicolumn" and j < len(s) and s[j] == "{":
            _, j = braces(s, j)
            _, j = braces(s, j)
            arg, j = braces(s, j)
            out.append(inline(arg, ctx))
        elif name == "item":
            out.append("\u0001ITEM\u0001")
        else:
            # UNKNOWN: emit it visibly. A renderer that silently drops a
            # macro it does not know produces text that looks finished
            # and is not, which is the defect this whole paper is about.
            out.append(f'<span class="unknown">\\{name}</span>')
        i = j
    return "".join(out)


def textify(s, ctx):
    """Quotes, dashes and inline maths, then inline markup."""
    # Strip math mode, but only between UNESCAPED dollars. The first
    # version did not, so `\texttt{\$anyconst}` -- an escaped dollar in
    # a code span -- opened a maths group that swallowed the rest of the
    # line and left `\anyconst` looking like an unknown macro.
    s = re.sub(r"(?<!\\)\$([^$]*?)(?<!\\)\$", lambda m: m.group(1), s)
    s = s.replace("``", "\u201c").replace("''", "\u201d")
    s = s.replace("---", "\u2014").replace("--", "\u2013")
    s = s.replace("~", "\u00a0")
    s = s.replace("\\,", "\u2009")        # thin space

    s = s.replace("{,}", ",").replace("{.}", ".")
    return inline(s, ctx)


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: render_html.py <main.tex> <out.html>")
    src = Path(sys.argv[1]).read_text(encoding="utf-8")
    out_path = Path(sys.argv[2])

    title = re.search(r"\\title\{(.*?)\}\s*\n\s*\n", src, re.S)
    title = title.group(1) if title else "Paper"
    title = re.sub(r"\\\\", " ", title)
    title = title.replace("\\,", "\u2009").replace("~", "\u00a0").strip()
    title = re.sub(r"\s+", " ", title)

    body = src.split(r"\begin{document}", 1)[1].split(r"\end{document}")[0]
    body = re.sub(r"(?m)^\s*%.*$", "", body)

    ctx = {"labels": {}, "cites": {}, "notes": []}

    # PASS 1: number the sections and tables so that \ref resolves.
    sec = sub = tab = 0
    appendix = False
    for line in body.split("\n"):
        if re.match(r"\s*\\appendix", line):
            appendix, sec = True, 0
            continue
        if re.match(r"\s*\\section\{", line):
            sec += 1
            sub = 0
            continue
        if re.match(r"\s*\\section\*\{", line):
            continue
        if re.match(r"\s*\\subsection\{", line):
            sub += 1
            continue
        if re.match(r"\s*\\caption\{", line):
            tab += 1
            continue
        m = re.match(r"\s*\\label\{([^}]+)\}", line)
        if m:
            key = m.group(1)
            if key.startswith("tab:"):
                ctx["labels"][key] = str(tab)
            elif key.startswith("app:"):
                ctx["labels"][key] = chr(ord("A") + sec - 1)
            elif sub:
                ctx["labels"][key] = f"{sec}.{sub}"
            else:
                ctx["labels"][key] = str(sec)

    # PASS 2: render.
    out = []
    sec = sub = tab = 0
    appendix = False
    i, lines = 0, body.split("\n")
    para = []

    def flush():
        if para:
            text = " ".join(x.strip() for x in para if x.strip())
            if text:
                out.append(f"<p>{textify(text, ctx)}</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        st = line.strip()
        if not st:
            flush()
            i += 1
            continue
        m = re.match(r"\\(section|subsection|paragraph)\*?\{", st)
        if m:
            flush()
            kind = m.group(1)
            starred = st[len(kind) + 1:len(kind) + 2] == "*"
            # A heading may run over several source lines; accumulate
            # until its argument's braces balance rather than assuming
            # one line, which is how the first version of this failed.
            head = st
            while head.count("{") > head.count("}") and i + 1 < len(lines):
                i += 1
                head += " " + lines[i].strip()
            rest = head[head.index("{"):]
            arg, after = braces(rest, 0)
            if kind == "section" and not starred:
                sec += 1
                sub = 0
                num = (chr(ord("A") + sec - 1) if appendix else str(sec))
                out.append(f"<h2>{num}. {textify(arg, ctx)}</h2>")
            elif kind == "section":
                out.append(f"<h2>{textify(arg, ctx)}</h2>")
            elif kind == "subsection":
                sub += 1
                out.append(f"<h3>{sec}.{sub} {textify(arg, ctx)}</h3>")
            else:
                out.append(f"<p class='para'><strong>{textify(arg, ctx)}</strong>"
                           f" {textify(rest[after:], ctx)}</p>")
            i += 1
            continue
        if st.startswith(r"\appendix"):
            flush()
            appendix, sec = True, 0
            out.append("<hr><h2 class='appendix'>Appendices</h2>")
            i += 1
            continue
        m = re.match(r"\\begin\{(\w+\*?)\}", st)
        if m:
            flush()
            env = m.group(1)
            depth, block, i = 1, [], i + 1
            while i < len(lines) and depth:
                if re.match(rf"\\begin\{{{env}\}}", lines[i].strip()):
                    depth += 1
                if re.match(rf"\\end\{{{env}\}}", lines[i].strip()):
                    depth -= 1
                    if not depth:
                        break
                block.append(lines[i])
                i += 1
            i += 1
            out.append(render_env(env, block, ctx, lambda: None))
            continue
        if st.startswith(r"\bibliographystyle") or st.startswith(r"\bibliography"):
            flush()
            i += 1
            continue
        para.append(line)
        i += 1
    flush()

    bib = render_bib(Path(sys.argv[1]).parent / "refs.bib", ctx)
    notes = ""
    if ctx["notes"]:
        items = "".join(f"<li>{n}</li>" for n in ctx["notes"])
        notes = f"<hr><h2>Notes</h2><ol>{items}</ol>"

    out_path.write_text(PAGE.format(
        title=html.escape(title), body="\n".join(out), bib=bib, notes=notes),
        encoding="utf-8")
    unknown = "\n".join(out).count('class="unknown"')
    print(f"wrote {out_path} — {len(ctx['labels'])} labels, "
          f"{len(ctx['cites'])} citations, {unknown} unknown macro(s)")
    return 1 if unknown else 0


def render_env(env, block, ctx, _):
    text = "\n".join(block)
    if env == "verbatim":
        return f"<pre>{html.escape(text)}</pre>"
    if env == "abstract":
        return (f"<div class='abstract'><h2>Abstract</h2>"
                f"<p>{textify(' '.join(x.strip() for x in block), ctx)}</p></div>")
    if env == "quote":
        return f"<blockquote>{textify(' '.join(block), ctx)}</blockquote>"
    if env == "itemize":
        items = [x for x in re.split(r"\\item", text) if x.strip()]
        return "<ul>" + "".join(
            f"<li>{textify(x, ctx)}</li>" for x in items) + "</ul>"
    if env in ("tabular", "tabularx", "center", "table"):
        return render_table(text, ctx)
    return f"<p>{textify(text, ctx)}</p>"


def render_table(text, ctx):
    cap = re.search(r"\\caption\{", text)
    caption = ""
    if cap:
        arg, _ = braces(text, cap.end() - 1)
        caption = f"<figcaption>{textify(arg, ctx)}</figcaption>"
        text = text[:cap.start()] + text[cap.end() - 1 + len(arg) + 2:]
    lab = re.search(r"\\label\{([^}]+)\}", text)
    anchor = f'<span id="{lab.group(1)}"></span>' if lab else ""
    # strip the environment scaffolding
    text = re.sub(r"\\begin\{(tabular|tabularx|center|table)\*?\}"
                  r"(\[[^\]]*\])?(\{[^{}]*(\{[^{}]*\})?[^{}]*\})*", "", text)
    text = re.sub(r"\\end\{(tabular|tabularx|center|table)\*?\}", "", text)
    rows_html = []
    for raw in text.split(r"\\"):
        raw = re.sub(r"\\(toprule|midrule|bottomrule|addlinespace|hline|small|centering)\b",
                     "", raw).strip()
        if not raw:
            continue
        cells = re.split(r"(?<!\\)&", raw)
        tag = "th" if not rows_html else "td"
        rows_html.append("<tr>" + "".join(
            f"<{tag}>{textify(c.strip(), ctx)}</{tag}>" for c in cells) + "</tr>")
    if not rows_html:
        return ""
    return (f"<figure>{anchor}{caption}<table>"
            + "".join(rows_html) + "</table></figure>")


def render_bib(path, ctx):
    if not path.is_file() or not ctx["cites"]:
        return ""
    text = path.read_text(encoding="utf-8")
    entries = {}
    for m in re.finditer(r"@\w+\{([^,]+),(.*?)\n\}", text, re.S):
        key, body = m.group(1).strip(), m.group(2)
        f = {}
        for fm in re.finditer(r"(\w+)\s*=\s*\{(.*?)\},?\s*(?=\n\s*\w+\s*=|\Z)",
                              body, re.S):
            f[fm.group(1).lower()] = " ".join(fm.group(2).split())
        entries[key] = f
    items = []
    for key, n in sorted(ctx["cites"].items(), key=lambda kv: kv[1]):
        e = entries.get(key, {})
        bits = [e.get("author", ""), e.get("title", "")]
        for k in ("journal", "booktitle", "howpublished", "institution",
                  "publisher"):
            if e.get(k):
                bits.append(e[k])
                break
        for k in ("volume", "number", "pages", "year"):
            if e.get(k):
                bits.append(e[k])
        line = ", ".join(b for b in bits if b)
        line = re.sub(r"[{}\\]", "", line)
        note = re.sub(r"[{}\\]", "", e.get("note", ""))
        items.append(f"<li id='cite{n}'>{html.escape(line)}"
                     + (f" <span class='note'>{html.escape(note)}</span>"
                        if note else "") + "</li>")
    return "<hr><h2>References</h2><ol>" + "".join(items) + "</ol>"


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
 body{{max-width:46em;margin:2rem auto;padding:0 1.2rem;
   font:16px/1.62 Georgia,'Times New Roman',serif;color:#1b1b1b;background:#fff}}
 h1{{font-size:1.7rem;line-height:1.25;margin:0 0 .4rem}}
 h2{{font-size:1.25rem;margin:2.2rem 0 .6rem;border-bottom:1px solid #ddd;
   padding-bottom:.2rem}}
 h3{{font-size:1.05rem;margin:1.6rem 0 .4rem}}
 p{{margin:.7rem 0}} p.para{{margin-top:1.1rem}}
 code{{font:0.86em ui-monospace,Menlo,Consolas,monospace;
   background:#f4f4f4;padding:.05em .3em;border-radius:3px}}
 pre{{background:#f7f7f7;padding:.8rem 1rem;overflow-x:auto;
   font:0.82rem/1.45 ui-monospace,Menlo,Consolas,monospace;border-radius:4px}}
 table{{border-collapse:collapse;width:100%;font-size:.86rem;margin:.4rem 0}}
 th,td{{border-bottom:1px solid #ddd;padding:.35rem .5rem;
   text-align:left;vertical-align:top}}
 th{{border-bottom:2px solid #999;font-weight:600}}
 figure{{margin:1.6rem 0}} figcaption{{font-size:.85rem;color:#444;
   margin-bottom:.4rem;font-style:italic}}
 blockquote{{margin:1.2rem 0;padding-left:1rem;border-left:3px solid #ccc;
   color:#333}}
 .abstract{{background:#fafafa;border:1px solid #e3e3e3;padding:.6rem 1.1rem;
   margin:1.6rem 0;font-size:.95rem}}
 .abstract h2{{border:0;font-size:1rem;margin:.4rem 0}}
 .sc{{font-variant:small-caps}}
 .note{{color:#666;font-size:.85em}}
 .unknown{{background:#ffe8e8;color:#900;padding:0 .2em}}
 .banner{{background:#fff8e1;border:1px solid #e8d9a0;padding:.7rem 1.1rem;
   font-size:.88rem;margin-bottom:1.6rem;font-family:system-ui,sans-serif}}
 ol li,ul li{{margin:.3rem 0}}
 @media print{{body{{max-width:none;font-size:11pt}} .banner{{border:1px solid #999}}}}
</style></head><body>
<div class="banner"><strong>This is a rendering, not the typeset paper.</strong>
It was produced by <code>paper/render_html.py</code> from
<code>paper/main.tex</code> because there is no TeX installation on the
machine this work is developed on, and the continuous integration that
would have built the PDF has not been able to start since 3&nbsp;September
2026. Line breaks, floats, hyphenation and the bibliography's formatting
are this renderer's and not LaTeX's. The source is the deliverable; this
is for reading.</div>
<h1>{title}</h1>
{body}
{notes}
{bib}
</body></html>
"""


if __name__ == "__main__":
    sys.exit(main())
