# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""The artefact manifest must cover what the paper cites.

WHY THIS EXISTS. `docs/80` pins artefacts by digest so that a number in
the paper can be traced to the bytes it came from, and
`scripts/artefact_digests.py --check` re-verifies them. But nothing ran
either. There was no test naming the script and `scripts/verify.sh` did
not call it, so the manifest was a thing a person runs -- and a manifest
nobody runs is a manifest that silently stops covering what it is for.

The specific failure it permits: `paper/claims.yaml` names artefact
paths under gitignored run trees, and nothing compared the two files, so
the next claim added could go unpinned exactly as several already had.

WHAT THIS DOES NOT DO. It does not run `--check`. That re-hashes
artefacts which are gitignored and mostly absent on a fresh clone, and a
test that fails on a clean checkout is a test people delete. It checks
the relationship between the two FILES, which is true in any checkout.
"""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs" / "80-artefact-digests.tsv"
CLAIMS = ROOT / "paper" / "claims.yaml"

# The directory prefixes that name a build artefact rather than a source
# file. docs/80 section 2's own list.
ARTEFACT_ROOTS = ("hw/soc/pnr/runs/", "hw/soc/out/", "hw/openlane/",
                  "formal/eqy/out/")


def _cited_artefacts():
    text = CLAIMS.read_text(errors="ignore")
    pat = re.compile(r"(?:" + "|".join(re.escape(r) for r in ARTEFACT_ROOTS)
                     + r")[^\s\"',\]}]+")
    return {m.group(0) for m in pat.finditer(text)}


def test_the_manifest_and_the_claims_registry_both_exist():
    """Neither file may quietly disappear: each is the other's check."""
    assert MANIFEST.is_file(), "docs/80's manifest is gone"
    assert CLAIMS.is_file(), "paper/claims.yaml is gone"


def test_every_run_tree_the_paper_cites_is_named_in_the_manifest():
    """A claim may point into a gitignored tree only if that tree is pinned.

    The unit is the RUN, not the file. claims.yaml cites individual
    reports inside a run directory and the manifest pins a selection of
    files from it; requiring an exact path match would fail on the
    difference between `runs/s77gate/final/metrics.json` and the rows
    that pin `runs/s77gate/...`. What must hold is that the run the
    paper leans on appears in the manifest at all -- otherwise the
    digest record does not reach the evidence.
    """
    manifest = MANIFEST.read_text(errors="ignore")
    cited = _cited_artefacts()
    assert cited, "claims.yaml cites no artefact paths at all -- the " \
                  "pattern above has probably stopped matching"

    def run_of(p):
        m = re.match(r"(hw/soc/pnr/runs/[^/]+)", p)
        return m.group(1) if m else None

    runs = {r for r in (run_of(p) for p in cited) if r}
    missing = sorted(r for r in runs if r not in manifest)
    assert not missing, (
        "paper/claims.yaml leans on {} run tree(s) that docs/80's "
        "manifest does not name: {}. Either pin them with "
        "scripts/artefact_digests.py or stop citing them -- a claim "
        "pointing into a gitignored directory that nothing pins is a "
        "claim a reader cannot reach.".format(len(missing), missing))


def test_the_manifest_is_not_empty_and_is_tab_separated():
    """A manifest that has become a blank file passes every other check."""
    rows = [r for r in MANIFEST.read_text(errors="ignore").split("\n")
            if r.strip() and not r.lstrip().startswith("#")]
    assert len(rows) > 50, (
        "docs/80's manifest has {} rows; it pinned hundreds. A manifest "
        "that shrank is the failure this file exists to notice."
        .format(len(rows)))
    assert all("\t" in r for r in rows[:20]), \
        "the manifest has stopped being tab-separated"
