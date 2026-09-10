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
    for name in ("index.html", "all-documents.html", "style.css"):
        if not (site / name).is_file():
            failures.append(f"missing {name}")

    for f in failures:
        print(f"FAIL: {f}")
    print(f"{manifest['documents']} documents, "
          f"{manifest['cross_references_resolved']} cross-references resolved, "
          f"backend {manifest['backend']}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
