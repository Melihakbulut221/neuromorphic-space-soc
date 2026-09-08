# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Spec-model-test sync enforcement (docs/10 section 13).

Every numbered equation tag (En) appearing in docs/10-npu-mvp-spec.md
must have at least one test named test_e<n>_* in this suite, and the
test suite must not reference equation numbers the spec does not define.
"""

import re
import sys
from pathlib import Path

SW_DIR = Path(__file__).resolve().parents[1]
SPEC = SW_DIR.parents[0] / "docs" / "10-npu-mvp-spec.md"
TEST_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(SW_DIR))


def _spec_equations():
    text = SPEC.read_text(encoding="utf-8")
    return {int(n) for n in re.findall(r"\(E(\d+)\)", text)}


def _tested_equations():
    found = set()
    for path in TEST_DIR.glob("test_*.py"):
        for n in re.findall(r"def test_e(\d+)_", path.read_text(encoding="utf-8")):
            found.add(int(n))
    return found


def test_spec_file_exists():
    assert SPEC.is_file(), f"spec not found at {SPEC}"


def test_every_spec_equation_has_a_test():
    spec = _spec_equations()
    tested = _tested_equations()
    assert spec, "no numbered equations found in the spec"
    missing = spec - tested
    assert not missing, f"spec equations without a test_e<n>_* test: E{sorted(missing)}"


def test_no_test_references_undefined_equation():
    extra = _tested_equations() - _spec_equations()
    assert not extra, f"tests reference equations the spec does not define: E{sorted(extra)}"


def test_expected_equation_set_is_complete():
    # The v0.1 contract is exactly E1..E10; a spec edit that renumbers or
    # drops an equation must be a conscious change here too.
    assert _spec_equations() == set(range(1, 11))
