# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""ROADMAP.md must not contradict the licence state it directs work from.

WHY THIS EXISTS. On 2026-09-10, a day after `docs/14` was signed and its
stage-1 mechanics were executed, `ROADMAP.md` still said the memo was
unsigned, that there was no root `LICENSE`, that `tt/LICENSE.PENDING.md`
refused to carry one, and that "the push is blocked, and the block has
not moved since 2026-08-25". All four were false. Three other files --
`README.md`, `LICENSES.md` and `scripts/ci_local.sh` -- asserted the
negation, and the one file that directs the remaining work was the one
still wrong.

Nothing caught it because nothing was looking. The licence state is
machine-readable in four places; this is the check that makes them agree.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _inside_strike(text, pos):
    """Is `pos` inside a `~~ ... ~~` span?

    Count the markers before it -- and be careful WHERE you measure from.
    The first version took the position of the matched LINE, and a
    paragraph struck as `~~**The push is blocked...` opens its span at
    exactly that index, so the opening marker was not counted and a
    correctly struck sentence read as live. Measure from the keyword.
    """
    return text.count("~~", 0, pos) % 2 == 1


def _line_at(text, pos):
    """The whole line containing `pos`, for a legible failure message."""
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return text[start:end if end != -1 else len(text)].strip()


def _signed():
    memo = (ROOT / "docs" / "14-licensing-decision.md").read_text(encoding="utf-8")
    return re.search(r"^\*\*SIGNED (\d{4}-\d{2}-\d{2})", memo, re.M)


def test_the_licence_state_is_the_same_in_every_file_that_states_it():
    """Four files carry it. They must agree."""
    signed = _signed()
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    if signed:
        # Every live assertion that it is UNSIGNED must be struck through.
        #
        # This corpus strikes a whole PARAGRAPH by wrapping it in a single
        # `~~ ... ~~` pair, so a line-by-line test flags the middle of a
        # correctly struck block. The first version of this test did
        # exactly that. Track the spans instead.
        for m in re.finditer(r"\bis (?:still )?unsigned\b", roadmap):
            assert _inside_strike(roadmap, m.start()), (
                "docs/14 is signed ({}) but ROADMAP.md still asserts it is "
                "unsigned, unstruck:\n  {}".format(
                    signed.group(1), _line_at(roadmap, m.start())))
        assert (ROOT / "LICENSE").is_file(), "docs/14 is signed but there is no root LICENSE"
        assert (ROOT / "tt" / "LICENSE").is_file(), "docs/14 is signed but tt/LICENSE is missing"
        assert not (ROOT / "tt" / "LICENSE.PENDING.md").exists(), (
            "docs/14 is signed and tt/LICENSE.PENDING.md is back")
        assert "signed" in readme.lower(), "README does not record the signature"
    else:
        assert not (ROOT / "LICENSE").is_file(), (
            "a root LICENSE exists while docs/14 carries no signature line")


def test_the_roadmap_does_not_call_the_push_blocked_by_the_licence():
    """The specific sentence that outlived its own facts by a day."""
    if not _signed():
        return
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    for m in re.finditer(r"The push is blocked", roadmap):
        assert _inside_strike(roadmap, m.start()), (
            "ROADMAP.md still says the push is blocked, unstruck, while "
            "docs/14 is signed:\n  " + _line_at(roadmap, m.start()))


# =====================================================================
# the formal task count, which had been corrected once and wrongly
# =====================================================================

FORMAL = ROOT / "hw" / "soc" / "formal"


def _formal_tasks():
    """-> (jobs, tasks), counted from the [tasks] sections themselves."""
    jobs = sorted(FORMAL.glob("*.sby"))
    tasks = 0
    for j in jobs:
        in_tasks = False
        for line in j.read_text(errors="ignore").split("\n"):
            st = line.strip()
            if st.startswith("["):
                in_tasks = (st == "[tasks]")
                continue
            if in_tasks and st:
                tasks += 1
    return len(jobs), tasks


def test_the_newest_formal_count_in_the_documents_matches_the_tree():
    """The LATEST dated count must be true; the older ones must not be.

    docs/64's rule is that a superseded measurement is left standing with
    a dated marker, so this cannot assert that every count in these files
    is current -- most of them are deliberately not. What it asserts is
    that the NEWEST one is, which is the only one a reader takes as a
    description of the tree.

    WHY IT EXISTS. On 2026-09-14 the tree carried 64 tasks across 15
    jobs. docs/00-index.md said 52 across fourteen. ROADMAP.md corrected
    that to 56 across 14 -- and the correction was ALSO wrong, because
    clkgate_wake.sby's six tasks (docs/77) postdate both. A roadmap
    correcting an index with a number that was already stale is the
    defect ROADMAP's own 2026-09-12 amendment was written about, and it
    recurred one cell away from it. Nothing was looking, so it accrued a
    third paragraph instead of a check.
    """
    jobs, tasks = _formal_tasks()
    assert jobs and tasks, "no .sby jobs found under hw/soc/formal"

    # Every "N tasks across M jobs/property sets" in either file, with the
    # position of the last one -- the newest, by the append-only rule.
    pat = re.compile(r"\*\*(\d+)\s+tasks across (\d+)\s+(?:jobs|property sets)\*\*"
                     r"|\*\*(\d+)\*\*\s+SymbiYosys tasks across (\w+) property")
    for name in ("docs/00-index.md", "ROADMAP.md"):
        text = (ROOT / name).read_text(errors="ignore")
        # Both files also count the PILOT's formal/ directory, which is a
        # different tree with its own number. Keep only the counts whose
        # neighbourhood names the SoC's, or the guard compares 64 against
        # the pilot's 54 and fails for the wrong reason.
        hits = [m for m in pat.finditer(text)
                if re.search(r"hw/soc/formal|SoC:",
                             text[max(0, m.start() - 400):m.end() + 200])]
        assert hits, "{} states no hw/soc/formal task count at all".format(name)
        last = hits[-1]
        got_tasks = int(last.group(1) or last.group(3))
        assert got_tasks == tasks, (
            "{}'s NEWEST formal count says {} tasks; the tree has {} "
            "across {} jobs. Older counts above it are left standing on "
            "purpose (docs/64); this is the one that must be true. "
            "Re-count with the [tasks] sections, not with a document."
            .format(name, got_tasks, tasks, jobs))
