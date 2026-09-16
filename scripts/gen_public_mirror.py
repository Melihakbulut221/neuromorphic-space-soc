#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Materialise the published subset of this repository as a public mirror.

    python3 scripts/gen_public_mirror.py --out ../nssoc-public
    python3 scripts/gen_public_mirror.py --out ../nssoc-public --check

`docs/14-licensing-decision.md` section 11 was signed on 2026-09-09 with
option C: publish a defined scope. It also chose a CURATED MIRROR over
making this repository public, and the deciding question named in
section 9 stage 2 was whether the existing git history is publishable
as-is. This script is the answer that does not require auditing 300
commit messages: the mirror carries the TREE, not the history, as one
commit that names the source revision it was taken from.

WHAT IS HELD BACK, AND HOW THE HOLE IS FILLED

`LICENSES.md` section 2.1 holds three things, none of which is a
technical result:

    docs/05 section 3   market and product-line positioning
    docs/06             funding and shuttle commercials
    docs/13             the NLnet application text

Twenty-two documents cite `docs/06` or `docs/13` in prose, and
`sw/tests/test_doc_links.py` fails on a reference that names a file
which does not exist. Deleting them would therefore either break the
mirror's own suite or force edits to twenty-two documents, and editing a
document to hide that it once cited something is the opposite of what
this corpus does.

So the two files are replaced by STUBS that keep the filename, say what
was held and why, and point at the memo. Every citation still resolves,
every reader can see exactly what is missing, and the index does not
move. `docs/05` keeps its file and loses section 3 the same way.

WHAT THIS SCRIPT DOES NOT DO

It does not push. It does not create a GitHub repository. It writes a
directory and a commit; publishing is an act that belongs to the owner.

*Corrected 2026-09-12: this ended "which is the same rule
`.github/workflows/docs.yml` states for the documentation site".
That workflow was deleted in 74fdddf and folded into
`.github/workflows/checks.yml`, which builds the site and gates on its
manifest and deploys nothing. The rule is unchanged; the file that
stated it is gone.*
"""

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Whole files that do not travel. Each is replaced by a stub, because a
# missing file breaks a citation and a citation is evidence.
HELD_FILES = {
    "docs/06-funding-and-shuttle.md": (
        "Funding and shuttle plan",
        "grant timetable, shuttle commercials and cost figures",
    ),
    "docs/13-nlnet-application.md": (
        "NLnet Restack application package",
        "the drafted text of a funding application that has not been "
        "submitted",
    ),
}

# Sections cut out of a file that otherwise travels: (path, start heading,
# end heading, what it held).
HELD_SECTIONS = [(
    "docs/05-market-positioning.md",
    "## 3. Positioning of this project",
    "## 4. Positioning language rules (binding)",
    "product-line positioning, price bands and customer profiles",
)]

STUB = """# {number} — {title} (held back)

**This document is not published.** It is one of the three things
`LICENSES.md` section 2.1 holds back from the public mirror, and it is
held for scope rather than for licence: it carries {what}, which is
commercial material and not a research result.

The file exists here so that citations resolve. {count} documents in
this corpus refer to `{stem}` in prose, and
`sw/tests/test_doc_links.py` fails on a reference naming a file that
does not exist. Removing it would have meant editing those documents to
hide that they once cited it, and a record that edits away its own
citations is not the record this project keeps.

Everything technical that this document fed into is published. The
decision to hold it, the argument for that decision and the full list of
what else is held are in `docs/14-licensing-decision.md` section 11 and
`LICENSES.md` section 2.1.
"""

# Fragments cut out of a file that otherwise travels whole: a clause,
# not a section. Each is (path, REGEX, replacement, why).
#
# THE PATTERNS DO NOT CONTAIN THE TEXT THEY REDACT, and that is the
# whole design. The first version of this table held the literal
# strings -- whereupon this file, which is itself published, carried
# every secret it was written to remove. The sweep that caught it is
# the same one that found the fragments: grep the OUTPUT, not the
# inputs. So each pattern is anchored on innocuous surrounding text and
# matches the sensitive span structurally.
#
# Found by the pre-publication audit of 2026-09-14, after two prior
# publications had carried both.
HELD_FRAGMENTS = [
    (
        "ROADMAP.md",
        r'(refusing to start jobs on this account -- )\*"[^"]*"\*',
        r"\1*(the exact wording is the owner's account status and is not "
        r"published: it names a billing condition on the account, not a "
        r"fault in this repository)*",
        "personal financial status of a named individual",
    ),
    (
        "scripts/ci_local.sh",
        r"(was refused before starting -- )'[^']*'",
        r"\1'(account status, not published)'",
        "the same wording, quoted a second time",
    ),
    (
        "docs/07-design-review.md",
        r"EUR \d+(?:\.\d+)?k NLnet ask",
        "NLnet ask *(figure held; `docs/06` carries it)*",
        "the headline grant figure, which is the class docs/06 is held for",
    ),
]

SECTION_STUB = """{start}

**Section held back.** This section carried {what} and is not published,
for the reason `LICENSES.md` section 2.1 gives: it is commercial
material rather than a research result. The heading is kept so that the
document's own section numbering, and every cross-reference to a later
section of this file, still resolve.

Section 4 below — the binding positioning-language rules — **is**
published, and is the section the rest of the corpus actually cites.

---

"""

MIRROR_README_NOTE = """
---

## About this mirror

This repository is a published subset of a private development
repository, generated by `scripts/gen_public_mirror.py` from revision
`{rev}`.

**It carries the tree, not the history.** `docs/14-licensing-decision.md`
section 9 stage 2 named the deciding question — whether the existing git
history is publishable as-is — and a curated mirror is the answer that
does not require auditing every commit message. What that costs is
honest to state: you cannot see how the design got here from this
repository, only where it arrived. The document corpus is where the
history actually lives, and it is published in full apart from the three
items in `LICENSES.md` section 2.1.

Three things are held back and each leaves a marker rather than a hole:
`docs/06` and `docs/13` are stubs that say what they held, and
`docs/05` section 3 is a stub heading inside a published document. No
technical result, negative result, withdrawn claim or measurement is
held back.
"""


def tracked():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, check=True,
                         capture_output=True, text=True).stdout
    return [l for l in out.split("\n") if l]


def head_rev():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout.strip()


def citation_count(stem):
    """How many documents cite this one, for the stub to state.

    COUNT THE CITATION, NOT THE NUMERAL. This searched for the bare
    number -- "06" -- anywhere in a document's text, so every date in
    2026-09-06, every table row reading 06 and every hash containing it
    counted as a citation. The two stubs went out saying 74 and 88
    where the true figures are 19 and 14, four and eight times over
    [fact, 2026-09-16]. A citation in this corpus is written "docs/NN",
    which is what is matched now.
    """
    number = stem.split("-")[0]
    needle = "docs/" + number
    n = 0
    for p in sorted((ROOT / "docs").glob("*.md")):
        if p.name.startswith(number + "-"):
            continue
        if needle in p.read_text(encoding="utf-8"):
            n += 1
    return n


def executable_paths():
    """The paths git records as mode 100755.

    A generated tree that carries a script's CONTENT and not its MODE
    produces a repository whose every entry point is unrunnable. That is
    what happened on 2026-09-10: the mirror's first CI run died in 75
    seconds on `scripts/ci_local.sh: Permission denied`, exit 126, and
    all 67 executables in this repository had arrived as 0644. The bytes
    were right and the tree was useless.
    """
    out = subprocess.run(["git", "ls-files", "-s"], cwd=ROOT, check=True,
                         capture_output=True, text=True).stdout
    return {line.split("\t", 1)[1] for line in out.split("\n")
            if line.startswith("100755") and "\t" in line}


def build():
    """Return the mirror as {relative path: bytes}."""
    files = {}
    for rel in tracked():
        if rel in HELD_FILES:
            continue
        src = ROOT / rel
        try:
            files[rel] = src.read_bytes()
        except FileNotFoundError:
            continue

    for rel, (title, what) in HELD_FILES.items():
        stem = Path(rel).stem
        number = stem.split("-")[0]
        files[rel] = STUB.format(
            number=number, title=title, what=what, stem="docs/" + number,
            count=citation_count(stem)).encode()

    for rel, start, end, what in HELD_SECTIONS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        a, b = text.index(start), text.index(end)
        files[rel] = (text[:a] + SECTION_STUB.format(start=start, what=what)
                      + text[b:]).encode()

    for rel, pattern, replacement, why in HELD_FRAGMENTS:
        text = files[rel].decode("utf-8")
        redacted, n = re.subn(pattern, replacement, text, flags=re.S)
        assert n == 1, (
            "held fragment in {} matched {} times, expected 1 ({}). A "
            "fragment that has been reworded upstream must fail the "
            "build, because the alternative is that it travels."
            .format(rel, n, why))
        files[rel] = redacted.encode()

    # The docs workflow explains, at length, why it does not deploy to
    # Pages, and the first reason it gives is that the repository is
    # private. In the mirror that sentence is FALSE. A generated tree
    # that carries a stale reason for a still-correct behaviour is the
    # failure shape this corpus names most often -- a claim read wider
    # than what it looked at -- so the reason is rewritten here rather
    # than left to be believed.
    # THE ABSENCE OF THE FILE MUST BE AN ERROR, and on 2026-09-10 it was
    # not. This block used to read `if wf in files:`, so when the three
    # workflows were replaced by one and `docs.yml` was deleted, the
    # guard did not fire -- it was skipped, silently, and the generator
    # wrote 511 files as though nothing were owed. A check that cannot
    # fail when the thing it checks is absent is not a check, and this
    # repository has now found that shape in its own mirror generator as
    # well as in its licence checker and its verification recorder.
    wf = ".github/workflows/checks.yml"
    if wf not in files:
        raise SystemExit(
            f"gen_public_mirror.py: {wf} is not in the published set. This "
            "script rewrites a sentence in it that is FALSE in the mirror, "
            "so its absence is a defect and not a no-op. If the workflows "
            "have moved again, re-read them and update this block.")
    text = files[wf].decode()
    marker = "# The two environment differences are handled by the script"
    if marker not in text:
        raise SystemExit(
            "gen_public_mirror.py: the checks workflow no longer carries the "
            "line this script anchors on; re-read it before regenerating")
    # AND THE SAME DEFECT AGAIN, twenty lines below its own fix. The
    # assertion above anchors on `marker`, but the rewrite below never
    # touched that line: it replaced a DIFFERENT two-line string, the
    # billing paragraph, with no check that the replacement happened. Edit
    # a word of that paragraph in the workflow and the marker still
    # matches, the guard still passes, `str.replace` finds nothing,
    # returns the string unchanged -- and the mirror ships the
    # unrewritten copy carrying a sentence that is false in it. Which is
    # exactly what the block above exists to prevent, one string over.
    # Found and repaired 2026-09-10.
    #
    # A replacement is now a mutation that must be OBSERVED: capture the
    # text, replace, and fail if the two are equal. That holds even if
    # someone later rewrites the search string and forgets the guard,
    # because it tests the effect rather than the precondition.
    # The quoted paragraph is GitHub's own message about the OWNER's
    # account, and the 2026-09-14 audit ruled it personal financial
    # status that should not travel. It is matched STRUCTURALLY -- the
    # pattern is anchored on the innocuous line above it and never
    # contains the wording -- because this file is published too, and a
    # redaction table that quotes what it redacts publishes it twice.
    billing_re = r'(are non-starts, on\n#\n)#   "[^"]*"'
    if not re.search(billing_re, text, re.S):
        raise SystemExit(
            "gen_public_mirror.py: the checks workflow no longer carries the "
            "billing paragraph this script rewrites. That paragraph explains "
            "a run history belonging to the DEVELOPMENT repository, which is "
            "not this one's; if it has been reworded or removed, re-read the "
            "workflow and update this block rather than shipping it as-is.")
    before = text
    text = re.sub(
        billing_re,
        r"\1#   (the exact wording is the owner's account status and is\n"
        r"#    not published; it names a billing condition on the account)\n"
        "#\n"
        "# IN THIS MIRROR that history is the DEVELOPMENT repository's and\n"
        "# not this one's: this repository has its own runner, its own\n"
        "# billing and no run history at all at the moment of generation.\n"
        "# The paragraph is kept rather than deleted because it is why the\n"
        "# checks live in a script instead of in this file, and that reason\n"
        "# holds wherever the file is.", text)
    if text == before:
        raise SystemExit(
            "gen_public_mirror.py: the mirror rewrite of the billing "
            "paragraph in " + wf + " changed nothing. The generator must "
            "not emit an unrewritten copy; re-read the workflow and fix the "
            "replacement.")
    files[wf] = text.encode()

    readme = files["README.md"].decode()
    files["README.md"] = (readme.rstrip() + "\n"
                          + MIRROR_README_NOTE.format(rev=head_rev())).encode()
    return files


def write(out, files):
    out.mkdir(parents=True, exist_ok=True)
    execs = executable_paths()
    for rel, data in sorted(files.items()):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        # The mode is part of the file. See executable_paths().
        p.chmod(0o755 if rel in execs else 0o644)
    return len(files)


def check_modes(out, files):
    """Every path git calls executable must be executable in the mirror."""
    execs = executable_paths()
    bad = []
    for rel in sorted(files):
        p = out / rel
        if not p.is_file():
            continue
        want = rel in execs
        have = bool(p.stat().st_mode & 0o111)
        if want != have:
            bad.append(f"{'not executable' if want else 'executable'}: {rel}")
    return bad


def check(out, files):
    bad = check_modes(out, files)
    for rel, data in sorted(files.items()):
        p = out / rel
        if not p.is_file():
            bad.append(f"missing: {rel}")
        elif p.read_bytes() != data:
            bad.append(f"differs: {rel}")
    # Ignore what a run inside the mirror leaves behind. Reporting a
    # .pytest_cache as "not generated" would train a reader to skim this
    # list, and a list that is skimmed is not a check.
    transient = {".git", ".pytest_cache", "__pycache__", ".venv", "_site",
                 "runs", "out", "node_modules"}
    extra = set()
    for p in out.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(out)
        if any(part in transient for part in rel.parts):
            continue
        if str(rel) not in files:
            extra.add(str(rel))
    for rel in sorted(extra):
        bad.append(f"not generated: {rel}")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--commit", action="store_true",
                    help="git init the output and make one commit")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    if out == ROOT:
        raise SystemExit("--out must not be this repository")
    files = build()

    if args.check:
        bad = check(out, files)
        if bad:
            print("\n".join(bad))
            return 1
        print(f"{out} matches the generator ({len(files)} files)")
        return 0

    n = write(out, files)
    digest = hashlib.sha256(
        b"".join(k.encode() + files[k] for k in sorted(files))
    ).hexdigest()
    print(f"{n} files written to {out}")
    print(f"tree digest {digest[:16]}")
    print(f"source revision {head_rev()[:12]}")

    if args.commit:
        env = {"GIT_AUTHOR_NAME": "Hasan Melih Akbulut",
               "GIT_COMMITTER_NAME": "Hasan Melih Akbulut",
               "GIT_AUTHOR_EMAIL":
                   "57303760+Melihakbulut221@users.noreply.github.com",
               "GIT_COMMITTER_EMAIL":
                   "57303760+Melihakbulut221@users.noreply.github.com"}
        import os
        env = {**os.environ, **env}
        if not (out / ".git").exists():
            subprocess.run(["git", "init", "-q", "-b", "main"], cwd=out,
                           check=True, env=env)
        subprocess.run(["git", "add", "-A"], cwd=out, check=True, env=env)
        msg = (
            "Publish the neuromorphic space SoC\n\n"
            "The tree of the development repository at revision "
            f"{head_rev()[:12]}, curated to the scope LICENSES.md section 2\n"
            "defines. Generated by scripts/gen_public_mirror.py; regenerate\n"
            "rather than editing here.\n\n"
            "No history, by decision: docs/14 section 9 stage 2 asked "
            "whether the\nexisting commit history is publishable as-is and a "
            "curated mirror is\nthe answer that does not require auditing "
            "it. The corpus in docs/ is\nwhere the design's history actually "
            "lives.\n"
        )
        subprocess.run(["git", "commit", "-q", "-m", msg], cwd=out,
                       check=True, env=env)
        rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=out,
                             capture_output=True, text=True, env=env)
        print(f"committed {rev.stdout.strip()} on branch main")
    return 0


if __name__ == "__main__":
    sys.exit(main())
