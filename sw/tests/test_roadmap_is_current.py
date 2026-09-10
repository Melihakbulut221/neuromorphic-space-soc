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
