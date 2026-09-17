# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""The recorded evidence is complete, is real JSON, and has not drifted.

WHY THIS GUARD EXISTS. `docs/evidence/` is the answer to the review's
largest finding: every `runs/` tree is gitignored, so on a clone no
layout claim could be checked and a quarter of the suite skipped. The
two small files per run that carry the checkable numbers are now
committed, and the tests read them through `sw/tests/evidence.py`.

That introduces a new way to be wrong: a record that has drifted from
the run it claims to record. On a machine with the run trees this
compares them and fails on any difference. On a machine without them --
a clone, the mirror, CI -- there is nothing to compare against and the
comparison honestly skips, while the completeness and shape checks
still run.

WHY THESE FILES ARE NOT IN docs/80-artefact-digests.tsv. That file's
own header says every path in it is gitignored on purpose: its job is
to pin what git cannot see. These files are tracked, so git pins them
already -- an edit is a diff -- and listing them there would be a
second, weaker copy of a guarantee git gives for free. What git cannot
tell you is whether the committed copy still matches the run tree it
was taken from, and that is what this file checks.
"""

import json
import pathlib

import pytest

import evidence as ev

ROOT = pathlib.Path(__file__).resolve().parents[2]
COLLECTOR = ROOT / "scripts" / "collect_evidence.py"


def _runs():
    if not COLLECTOR.is_file():
        return {}
    import importlib.util
    spec = importlib.util.spec_from_file_location("collect_evidence", COLLECTOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return dict(mod.RUNS)


RUNS = _runs()
NAMES = ("metrics.json", "resolved.json")
CASES = [(tag, name) for tag in sorted(RUNS) for name in NAMES]


@pytest.mark.skipif(not RUNS, reason="scripts/collect_evidence.py is not in this tree")
@pytest.mark.parametrize("tag,name", CASES, ids=lambda v: v)
def test_every_cited_run_has_its_evidence_committed(tag, name):
    path = ev.recorded_path(tag, name)
    assert path.is_file(), (
        "%s is not committed. Every run a document cites must carry its "
        "own metrics.json and resolved.json under docs/evidence/, or the "
        "claims that name it cannot be checked from a clone. Run "
        "scripts/collect_evidence.py on a machine that has the run tree."
        % path.relative_to(ROOT))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and data, "%s is empty" % path


@pytest.mark.skipif(not RUNS, reason="scripts/collect_evidence.py is not in this tree")
def test_the_record_matches_the_run_tree_where_both_exist():
    """A record that has drifted from its run is a record of nothing.

    ONE test and not thirty. The first version parametrised over every
    run and file, which reads well on a machine holding the run trees
    and turns into thirty identical skips on every machine that does
    not -- a clone, the mirror, CI. Thirty skips saying the same thing
    is not thirty facts, and this repository's own rule is that a skip
    must carry a reason worth reading. Where the trees ARE present this
    still names every file it compared.
    """
    checked, absent = [], []
    for tag in sorted(RUNS):
        base = ROOT / RUNS[tag] / tag
        for name in NAMES:
            live = base / ("final/metrics.json" if name == "metrics.json"
                           else "resolved.json")
            if not live.is_file():
                absent.append("%s/%s" % (tag, name))
                continue
            # evidence.load raises on a mismatch, naming both paths.
            got = ev.load(tag, name, live)
            assert got is not None and got.is_live
            checked.append("%s/%s" % (tag, name))
    if not checked:
        pytest.skip(
            "no run tree for any of the %d cited runs is on this machine, "
            "so there is nothing to compare the records against. runs/ is "
            "gitignored build output; the records are what make the claims "
            "checkable here, and this comparison is what a machine holding "
            "the runs does. %d files were looked for."
            % (len(RUNS), len(absent)))
    assert checked, "nothing compared"


@pytest.mark.skipif(not RUNS, reason="scripts/collect_evidence.py is not in this tree")
def test_the_sign_off_metrics_carry_the_keys_the_documents_read():
    """The sign-off run's record is the one most claims lean on."""
    m = ev.metrics("s83romecc5")
    assert m is not None, "docs/evidence/s83romecc5/metrics.json is absent"
    for key in ("design__instance__count",
                "design__instance__utilization",
                "route__drc_errors"):
        assert key in m, (
            "%s is not in the recorded sign-off metrics; the documents "
            "read it, so its absence makes them uncheckable" % key)
