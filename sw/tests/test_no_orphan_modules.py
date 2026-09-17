# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Every module under hw/rtl/ is built into something, or says why not.

WHY THIS GUARD EXISTS. `README.md` said "6,883 lines of Verilog ...
*Exists, and is verified*", and the command behind that number,
`wc -l hw/rtl/*.v`, is exactly right. What the sentence around it does
not carry is that 1,268 of those lines -- `npu_regbank.v` at 936 and
`scrub.v` at 332 -- are instantiated in no design this repository
builds, and that fourteen of the fifty-four proof tasks prove them. An
external reviewer found it and named the right fix: state the scope,
do not shrink the set.

Stating it once fixes today. This makes the next one fail.

WHAT REACHABILITY MEANS HERE. A module is built if it is reachable by
instantiation from either root -- `tt_um_melihakbulut_nssoc`, the
frozen Tiny Tapeout submission, or `soc_top`, the system-on-chip --
following instantiations through `hw/rtl/` and `hw/soc/rtl/` together,
because the SoC instantiates pilot modules and the pilot does not
instantiate SoC ones. Anything left over must appear in
`hw/known-unbuilt.txt` with a reason -- beside the frozen tree,
not inside it.

WHAT IT DELIBERATELY DOES NOT DO. It does not parse Verilog. It finds
`module NAME` declarations and then looks for each name used in an
instantiation position elsewhere, which over-approximates reachability:
a module named in a comment would count as built. That direction is the
safe one. A test that under-approximated would fail on correct code and
be disabled within a week, and this repository already has a document
about guards that nobody runs.

WHAT IT DOES NOT CHECK. Whether a built module is built *correctly*,
and whether an unbuilt one should be. `docs/11` section 1's `Built
into` column is where a reader sees the answer; this only makes sure
the column cannot silently go stale.
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
RTL = ROOT / "hw" / "rtl"
SOC_RTL = ROOT / "hw" / "soc" / "rtl"
# NOT under hw/rtl/: that tree is frozen by docs/34 and pinned by
# tt/MANIFEST.sha256, and the first version of this guard put its
# own ledger inside it -- caught immediately by
# test_soc_npu_guards.py, which is the freeze doing its job.
LEDGER = ROOT / "hw" / "known-unbuilt.txt"

ROOTS = ("tt_um_melihakbulut_nssoc", "soc_top")

MODULE_RE = re.compile(r"(?m)^\s*module\s+([A-Za-z_]\w*)")
# An instantiation position: NAME followed by #( or by an identifier and
# an open paren. Deliberately loose -- see the docstring.
COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)


def _sources():
    files = []
    for d in (RTL, SOC_RTL):
        if d.is_dir():
            files += sorted(d.rglob("*.v"))
    return files


def _declared():
    """module name -> the file that declares it, for hw/rtl/ only."""
    out = {}
    for f in sorted(RTL.glob("*.v")):
        for m in MODULE_RE.finditer(f.read_text(errors="ignore")):
            out[m.group(1)] = f
    return out


def _instantiations(text, known):
    """Which known module names appear in an instantiation position."""
    body = COMMENT_RE.sub(" ", text)
    found = set()
    for name in known:
        pat = re.compile(r"(?<![\w.])" + re.escape(name)
                         + r"\s*(?:#\s*\(|[A-Za-z_]\w*\s*\()")
        if pat.search(body):
            found.add(name)
    return found


def _ledger():
    entries = {}
    if not LEDGER.is_file():
        return entries
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, why = line.partition("\t")
        entries[name.strip()] = why.strip()
    return entries


@pytest.mark.skipif(not RTL.is_dir(), reason="hw/rtl/ is not in this tree")
def test_every_hw_rtl_module_is_built_or_declared_unbuilt():
    declared = _declared()
    assert declared, "no modules found under hw/rtl/"

    # Reachability, breadth-first from the two roots.
    texts = {f: f.read_text(errors="ignore") for f in _sources()}
    decl_all = {}
    for f, t in texts.items():
        for m in MODULE_RE.finditer(t):
            decl_all[m.group(1)] = f

    reachable, frontier = set(), [r for r in ROOTS if r in decl_all]
    assert frontier, (
        "neither root module was found: looked for %s" % (ROOTS,))
    while frontier:
        name = frontier.pop()
        if name in reachable:
            continue
        reachable.add(name)
        f = decl_all.get(name)
        if f is None:
            continue
        for child in _instantiations(texts[f], decl_all):
            if child not in reachable:
                frontier.append(child)

    ledger = _ledger()
    orphans = sorted(n for n in declared if n not in reachable)
    undeclared = [n for n in orphans if n not in ledger]
    assert not undeclared, (
        "modules under hw/rtl/ are instantiated in no design this "
        "repository builds and are not declared in %s: %s\n"
        "Either wire them in, or add a line naming the module and the "
        "reason. Do not delete the file and do not move it out of "
        "hw/rtl/ to make a line count look better: the fix is to state "
        "the scope, not to shrink the set."
        % (LEDGER.relative_to(ROOT), ", ".join(undeclared)))

    # The other direction: a ledger row for a module that IS built is a
    # fossil, and it hides the thing the ledger exists to show.
    fossils = sorted(n for n in ledger if n in reachable)
    assert not fossils, (
        "%s names modules that ARE built: %s. A stale row here reads as "
        "'this is orphaned' about code that is in the part."
        % (LEDGER.relative_to(ROOT), ", ".join(fossils)))

    missing = sorted(n for n in ledger if n not in declared)
    assert not missing, (
        "%s names modules that hw/rtl/ does not declare: %s"
        % (LEDGER.relative_to(ROOT), ", ".join(missing)))


@pytest.mark.skipif(not LEDGER.is_file(), reason="no known-unbuilt ledger")
def test_every_unbuilt_row_carries_a_reason():
    for name, why in _ledger().items():
        assert len(why) > 40, (
            "%s: an unbuilt module needs a reason, not a placeholder. "
            "The row said %r." % (name, why))
