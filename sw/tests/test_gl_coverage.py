# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Does the campaign-coverage attribution still land where docs/60
section 9.10.1 published it, and can it be made to move?

WHY THIS FILE EXISTS

`docs/60` section 9.10.1 published a table -- 1,003 of 5,873 flip-flops
in a block no fault-injection campaign in this repository has ever
injected into -- and then disclosed, in its own words, that the listing
which produced it *"is not committed to this tree"*. It called that an
owed artefact. `hw/soc/fi/gl_coverage.py` is the artefact, written from
that section's prose rather than recovered from the original listing,
which no longer exists.

So there are two different things to check and they are not worth the
same:

  * that the reimplementation reproduces the seven published figures.
    This is the weaker one. It says the description in `docs/60` was
    complete enough for someone to rebuild the instrument from it.
  * that the instrument MOVES when the thing it measures moves. A
    coverage number that reports 1,003 on a netlist in which eight
    uncovered flip-flops have been relabelled into a covered block is
    not measuring coverage. `docs/60` states the mutation and its
    answer -- 1,003 to 995 -- and this file runs it.

WHAT IT DOES **NOT** COVER

  * The netlist is a git-ignored build product, so on a fresh clone
    there is nothing to read and these tests SKIP with the command that
    regenerates them. A skip here is evidence of nothing.
  * It checks the attribution, not the coverage claim behind it. A
    block counts as covered if any campaign has ever injected anywhere
    in it; `docs/60` section 9.10.1's first caveat says the count of
    flip-flops that are not a site of any campaign is larger than
    1,003, and nothing here measures that.
  * `CAMPAIGNS` in `gl_coverage.py` is a hand-kept table of which block
    each document injected into. Nothing mechanically ties it to the
    campaigns. If a new campaign covers a block and the table is not
    updated, this file will keep agreeing with a stale answer.
"""

import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "hw" / "soc" / "fi" / "gl_coverage.py"
NETLIST = ROOT / "hw" / "soc" / "out" / "s70-rom0-syn" / "soc_top.netlist.v"

REGENERATE = ("hw/soc/flow/syn_soc.sh writes it; docs/60 section 9.10.1 "
              "names it as hw/soc/out/s70-rom0-syn/soc_top.netlist.v")


def run(*args):
    if not NETLIST.is_file():
        pytest.skip(f"{NETLIST.relative_to(ROOT)} is a git-ignored build "
                    f"product and is not in this tree. {REGENERATE}")
    return subprocess.run([sys.executable, str(TOOL), str(NETLIST), *args],
                          cwd=ROOT, capture_output=True, text=True,
                          timeout=3600)


def test_it_reproduces_every_published_figure():
    """--verify checks all seven against docs/60 and fails on any one."""
    p = run("--verify")
    assert p.returncode == 0, (
        "the reimplementation no longer agrees with docs/60 section "
        "9.10.1.\n\nThis is NOT to be closed by editing PUBLISHED in "
        "gl_coverage.py or by tuning\nthe instrument until it matches. "
        "Either the netlist moved -- in which case the\nnew numbers are "
        "a measurement and belong in docs/60 with a date, beside the "
        "old\nones -- or the instrument broke.\n\n" + p.stdout + p.stderr)
    assert "all 7 agree." in p.stdout


def test_relabelling_eight_flip_flops_moves_the_number():
    """The negative control docs/60 section 9.10.1 specifies.

    Eight `u_busstat.irqen` flip-flops renamed into `u_ibex` -- a block
    the core campaign injects into -- must move the uncovered count from
    1,003 to 995 and `u_busstat` from 144 to 136. If both stay put, the
    attribution is reading something other than the block a flip-flop is
    in, and the whole of section 9.10.1 rests on it."""
    p = run("--mutate", "u_busstat.irqen:u_ibex.mutant_irqen")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "**995**" in p.stdout, (
        "relabelling eight uncovered flip-flops into a covered block did "
        "not move the\nuncovered count to 995. A check that reports the "
        "same number either way is not\nmeasuring coverage.\n\n" + p.stdout)
    assert "| `u_busstat` | 136 |" in p.stdout, (
        "the uncovered total moved but u_busstat did not go 144 -> 136, "
        "so the eight\nflip-flops did not land where the mutation put "
        "them.\n\n" + p.stdout)


def test_the_unmutated_run_is_the_control_for_that():
    """The other direction: without --mutate the two numbers must be the
    ORIGINAL pair. A mutation test passes trivially if the tool prints
    995 and 136 all the time."""
    p = run()
    assert p.returncode == 0, p.stdout + p.stderr
    assert "**1,003**" in p.stdout and "| `u_busstat` | 144 |" in p.stdout, (
        "the unmutated run does not print 1,003 / 144, so the mutation "
        "test above\nproves nothing about the mutation.\n\n" + p.stdout)
    assert "**995**" not in p.stdout
