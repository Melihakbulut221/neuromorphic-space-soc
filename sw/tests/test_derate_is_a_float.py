# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Is the timing derate a float everywhere it is written down?

WHY THIS FILE EXISTS

`docs/72` section 7.1 measured a re-run of one hardening step that came
out 1.744 ns and 1.623 ns BETTER than the flow it was reproducing, and
the cause was one character. OpenROAD computes the derate factor in Tcl
integer arithmetic, so `"TIME_DERATING_CONSTRAINT": 5` derates by 0 %
and prints "Setting timing derate to: 5%" while doing it, and
`"TIME_DERATING_CONSTRAINT": 5.0` derates by 5 %. The two configurations
look identical, the log says the same thing in both, and the timing is
1.7 ns apart.

`docs/72` section 14 item 4 and `docs/73` section 16 both list this
guard as OWED, in those words. This is it, two days late.

WHAT IT GUARDS AND WHAT IT CANNOT

It guards the TRACKED configurations -- the seventeen `config*.json`
files in `hw/openlane/`, `hw/soc/pnr/` and `tt/src/` that a person
edits. Those are the ones where a typed `5` would silently turn the
derate off for every run made afterwards, and they are checkable on any
clone with no run tree at all.

It does NOT guard the step directories, and cannot repair them. Every
`<run>/NN-step/config.json` LibreLane writes records the key as an int
`5` -- 1,529 of them in this working tree -- because the value has been
through a JSON round trip that dropped the decimal point. That is the
trap `docs/72` found, it is in build output this repository does not
own, and the second test below measures it rather than asserting it
away, so that a reader who re-runs a step from its own directory meets
the number instead of the surprise.
"""

import json
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
KEY = "TIME_DERATING_CONSTRAINT"


def _tracked_configs():
    """docs/78 section 4's principle: a generated tree is a plain
    directory until it is committed, and a check that cannot run there
    is a check that does not run where it is most needed. This raised
    in the public mirror, which is exactly that tree. Falling back to
    what is on disk is correct rather than lax -- the mirror is BUILT
    from `git ls-files`, so every config present there is tracked."""
    try:
        out = subprocess.run(["git", "ls-files", "*config*.json"], cwd=ROOT,
                             check=True, capture_output=True,
                             text=True).stdout
        paths = [ROOT / p for p in out.split("\n") if p.strip()]
        if paths:
            return paths
    except (OSError, subprocess.CalledProcessError):
        pass
    return sorted(ROOT.glob("**/*config*.json"))


def _carrying_the_key(paths):
    found = []
    for p in paths:
        try:
            d = json.loads(p.read_text())
        except (ValueError, OSError):
            continue
        if isinstance(d, dict) and KEY in d:
            found.append((p, d[KEY]))
    return found


def test_every_tracked_config_writes_the_derate_as_a_float():
    """The guard docs/72 section 14 item 4 asked for.

    A bool is rejected too: `True` is an int in Python and would sail
    through an isinstance check written the obvious way.
    """
    carrying = _carrying_the_key(_tracked_configs())
    assert carrying, (
        "no tracked configuration carries " + KEY + " at all. Either the "
        "key was renamed or\nthis test is looking in the wrong place; "
        "either way it is no longer guarding anything.")

    wrong = [(p.relative_to(ROOT).as_posix(), v) for p, v in carrying
             if isinstance(v, bool) or not isinstance(v, float)]
    assert not wrong, (
        "these tracked configurations write {} as something other than a "
        "float:\n  {}\n\nOpenROAD computes the derate factor in Tcl "
        "integer arithmetic. An int 5 derates by\n0 % and logs \"Setting "
        "timing derate to: 5%\" while doing it; 5.0 derates by 5 %. "
        "docs/72\nsection 7.1 measured the difference at 1.744 ns and "
        "1.623 ns on one step, which is\nlarger than most of the timing "
        "findings in this repository.".format(
            KEY, "\n  ".join(f"{p}: {v!r} ({type(v).__name__})"
                             for p, v in wrong)))


def test_the_step_directories_demote_it_and_that_is_recorded_not_fixed():
    """The half this repository does not own, measured.

    LibreLane writes a `config.json` into every step directory and the
    value arrives there as an int. Nothing here can change that, and a
    test that asserted otherwise would be red on every run tree forever.
    What it can do is state the number, so the trap is documented by a
    measurement rather than by a memory.
    """
    steps = sorted(ROOT.glob("hw/soc/pnr/runs/*/[0-9]*/config.json"))
    if not steps:
        pytest.skip(
            "no run trees on this machine -- hw/soc/pnr/runs/ is "
            "gitignored build output, so there are no step directories "
            "to measure. A skip here is evidence of nothing.")

    carrying = _carrying_the_key(steps)
    ints = [p for p, v in carrying if not isinstance(v, float)]
    floats = [p for p, v in carrying if isinstance(v, float)]

    assert carrying, (
        "step directories exist and none records " + KEY + ", so the "
        "demotion docs/72 found\ncannot be reproduced and this test "
        "measures nothing.")

    # NOT an assertion that they are all ints. If a future LibreLane
    # fixes the round trip, this must notice rather than stay green on a
    # sentence that has stopped being true.
    assert not floats or not ints, (
        "step directories disagree with each other: {} write {} as a "
        "float and {} as an int.\nThat is a change in the tool "
        "mid-history, and docs/72 section 7.1's account of the\nre-run "
        "needs re-reading against whichever kind the step it cites "
        "carries.".format(len(floats), KEY, len(ints)))

    if ints:
        print(f"\n{len(ints)} step config.json files demote {KEY} to an "
              f"int; 0 keep it a float.\nRe-running any of those steps "
              f"from its own directory derates by 0 %. docs/72 s.7.1.")
