# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Resolve a run's small evidence: the live run tree first, the record second.

WHY THIS EXISTS. Every `runs/` tree is gitignored, for the good reason
that a 113 MB GDS does not belong in git. The consequence was that on a
clone a quarter of the suite skipped and no layout claim could be
checked at all. `scripts/collect_evidence.py` now commits the two small
files that carry most of the checkable numbers, and this is what the
tests read them through.

THE ORDER MATTERS AND SO DOES SAYING WHICH ONE ANSWERED. A live run
tree is the real thing and wins. The committed record is a record: it
proves what the run reported, not that the run can be reproduced here.
`source` says which was used so a test can report *checked against the
recorded artefact* rather than *checked*, which is a weaker claim and
deliberately so.

WHEN BOTH ARE PRESENT THEY MUST AGREE. A committed record that has
drifted from the tree it was taken from is worse than no record, so
`load` compares them and raises. `scripts/collect_evidence.py --check`
is the same comparison across every run at once.

WHAT IT DOES NOT DO. It does not make a netlist, a DEF or a GDS
appear. A test that needs one still skips, and `skip_reason` gives it a
message that names the digest in `docs/80-artefact-digests.tsv` the
absent file would have to match.
"""

import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECORDED = ROOT / "docs" / "evidence"

LIVE, RECORD = "run tree", "recorded evidence"


class Evidence:
    """One JSON artefact, with where it came from."""

    def __init__(self, data, source, path):
        self.data = data
        self.source = source
        self.path = path

    @property
    def is_live(self):
        return self.source == LIVE

    def qualify(self, claim):
        """`claim`, phrased for whichever source answered."""
        if self.is_live:
            return "%s (checked against %s)" % (claim, self.path)
        return ("%s (checked against the RECORDED artefact %s, not against "
                "a run: this tree has no %s)"
                % (claim, self.path.relative_to(ROOT), self.path.name))

    def __contains__(self, key):
        return key in self.data

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)

    def keys(self):
        return self.data.keys()

    def __iter__(self):
        return iter(self.data)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recorded_path(tag, name):
    return RECORDED / tag / name


def load(tag, name, live_path=None):
    """Evidence for `tag`/`name`, or None if neither source has it.

    `live_path` is where the run tree would keep it. When both exist
    they are compared, because a record that has drifted from its run
    is a record of nothing.
    """
    rec = recorded_path(tag, name)
    live = pathlib.Path(live_path) if live_path else None
    if live is not None and live.is_file():
        if rec.is_file() and _digest(rec) != _digest(live):
            raise AssertionError(
                "%s differs from %s. The committed record and the run tree "
                "disagree; re-run scripts/collect_evidence.py if the tree is "
                "the newer one, and read the diff before you do."
                % (rec.relative_to(ROOT), live))
        return Evidence(json.loads(live.read_text(encoding="utf-8")),
                        LIVE, live)
    if rec.is_file():
        return Evidence(json.loads(rec.read_text(encoding="utf-8")),
                        RECORD, rec)
    return None


def metrics(tag, run_dir=None):
    live = pathlib.Path(run_dir) / "final" / "metrics.json" if run_dir else None
    return load(tag, "metrics.json", live)


def resolved(tag, run_dir=None):
    live = pathlib.Path(run_dir) / "resolved.json" if run_dir else None
    return load(tag, "resolved.json", live)


def skip_reason(tag, what, regenerate=None):
    """A skip message that names what is absent and what would satisfy it."""
    msg = ("%s for run %r is not in this tree. Run outputs are gitignored, "
           "and this file is too large to record: docs/evidence/ carries "
           "metrics.json and resolved.json only."
           % (what, tag))
    digests = ROOT / "docs" / "80-artefact-digests.tsv"
    if digests.is_file():
        msg += (" If it is regenerated it must match its row in "
                "docs/80-artefact-digests.tsv.")
    if regenerate:
        msg += " Regenerate with: %s" % regenerate
    return msg
