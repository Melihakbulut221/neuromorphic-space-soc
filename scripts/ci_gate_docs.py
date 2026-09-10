#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Gate on a built documentation site, the way the workflow used to inline.

    python3 scripts/ci_gate_docs.py _site pandoc

Lifted out of .github/workflows/docs.yml so that the workflow and
scripts/ci_local.sh run the SAME check rather than two copies of it. A
gate that exists twice is a gate that disagrees with itself eventually.
"""

import json
import pathlib
import sys


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: ci_gate_docs.py <site-dir> <expected-backend>")
    site = pathlib.Path(sys.argv[1])
    expected_backend = sys.argv[2]
    manifest = json.loads((site / "manifest.json").read_text())

    sources = sorted(pathlib.Path("docs").glob("*.md"))
    expected = len(sources) + 2          # README.md and ROADMAP.md

    failures = []
    if manifest["documents"] != expected:
        failures.append(
            f"built {manifest['documents']} documents, expected {expected}")
    if manifest["backend"] != expected_backend:
        failures.append(
            f"backend was {manifest['backend']}, expected {expected_backend}")
    if manifest["cross_references_resolved"] < 500:
        failures.append(
            f"only {manifest['cross_references_resolved']} cross-references "
            "resolved; the corpus carries several hundred")

    # THE UNRESOLVED LIST, which this gate did not read until 2026-09-10.
    #
    # `cross_references_resolved` counts SUCCESSES. The corpus resolves
    # 7916 of them, so the floor of 500 above is a smoke test for a build
    # that collapsed, not a link check: a reference whose target is
    # deleted moves that count by one and adds an entry to a field this
    # gate never opened. The gate whose job is to notice a broken
    # cross-reference would have gone green on the day one broke.
    #
    # scripts/build_docs.py calls the field `unresolved` -- not
    # `unresolved_references`, not `cross_references_unresolved` -- and it
    # holds one {file, line, reference} object per reference whose target
    # is missing from disk. Note also that ci_local.sh runs build_docs.py
    # WITHOUT --strict, so the builder's own non-zero exit on unresolved
    # references is not in play here; this is the only place the list is
    # looked at.
    #
    # Its ABSENCE is a failure and not a pass. A manifest written by a
    # build_docs.py that stopped emitting the field would otherwise be
    # read as "nothing unresolved", which is the shape docs/36 closed two
    # checkers on and scripts/gen_public_mirror.py names in its own
    # workflow guard: a check that cannot tell a clean subject from a
    # missing one.
    if "unresolved" not in manifest:
        failures.append(
            "manifest carries no 'unresolved' field; this gate cannot tell "
            "a corpus with no broken cross-references from a build that "
            "stopped reporting them. If build_docs.py renamed the field, "
            "re-read the manifest dict and update this gate.")
        unresolved = []
    else:
        unresolved = manifest["unresolved"]
        for u in unresolved:
            failures.append(
                "unresolved cross-reference: "
                f"{u.get('file', '?')}:{u.get('line', '?')}: "
                f"{u.get('reference', u)}")

    for name in ("index.html", "all-documents.html", "style.css"):
        if not (site / name).is_file():
            failures.append(f"missing {name}")

    for f in failures:
        print(f"FAIL: {f}")
    print(f"{manifest['documents']} documents, "
          f"{manifest['cross_references_resolved']} cross-references resolved, "
          f"{len(unresolved)} unresolved, "
          f"backend {manifest['backend']}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
