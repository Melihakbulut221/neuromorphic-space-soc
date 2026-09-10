# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0

"""Spec-model-test sync enforcement (docs/10 section 13).

Every numbered equation tag (En) appearing in docs/10-npu-mvp-spec.md
must have at least one test in this suite that is named test_e<n>_* AND
that actually asserts something, and the suite must not reference
equation numbers the spec does not define.

WHAT THIS FILE USED TO CHECK, AND WHY THAT WAS NOT ENOUGH
---------------------------------------------------------
Until this revision the scan was one regular expression over the raw
text of each test file, `def test_e(\\d+)_`, and an equation counted as
covered the moment a function with the right NAME existed. A function
body of `pass` satisfied it. So did a body that computed something and
threw it away. The claim the corpus makes on the strength of this file
is not about names:

  * docs/10 section 13: "Every numbered equation maps to at least one
    pytest in sw/tests/; the mapping is enforced mechanically by
    sw/tests/test_traceability.py::test_every_spec_equation_has_a_test,
    which parses this document for equation tags and fails if any tag
    lacks a matching test_e<n>_* test."
  * docs/21 section 4: "each is bound to at least one test in sw/tests/
    by a traceability check that fails if any tag lacks a matching
    test."
  * docs/11 section: "test_traceability.py is the piece that keeps the
    model files honest."

"Bound to a test" and "bound to a function whose name starts with the
right five characters" are different claims, and only the second one was
enforced. A check that cannot distinguish a test from an empty function
named like one is a check that cannot go red for the defect it exists to
find -- the eighth instrument in this tree found to have that shape.

WHAT IT CHECKS NOW
------------------
The scan is over the ABSTRACT SYNTAX TREE rather than the text, and each
matching function is required to contain at least one assertion. Two
consequences worth stating:

  * A `def test_e91_...` written inside a STRING is no longer a test.
    The old text scan counted one, which is not a hypothetical: the
    negative control at the bottom of this file embeds exactly such a
    string, and under the old scan it would have registered four
    equations the spec does not define and failed the file it was added
    to.
  * "Assertion" means an `assert` statement anywhere in the function, or
    a `with pytest.raises(...)` / `pytest.warns(...)` block, which is how
    three real tests in this suite check what they check
    (test_e1_weight_out_of_range_rejected, test_e1_float_weights_rejected
    and test_e9_layer_wider_than_event_id_space_rejected assert by
    raising and would otherwise be reported as empty).

WHAT IT STILL CANNOT SEE, SAID PLAINLY
--------------------------------------
  * Whether the assertion is about the equation the name claims. A test
    named test_e4_* that asserts 1 == 1 passes every check here. This
    file measures that a test exists, is named for an equation, and can
    fail; it does not and cannot measure that it tests the right thing.
    docs/10's own table of equation to test is the human half of that.
  * An assertion inside a nested function that is never called counts.
    The walk is over the whole function body including nested defs,
    because a test that delegates to a local helper is normal and
    excluding those would report real tests as empty.
  * A test that asserts and is then skipped, xfailed or parameterised to
    an empty set. That is a pytest-run property, not a source property,
    and the run itself is the place it shows.
  * Assertions made by a helper in another module. A test whose body is
    one call to a shared checker is reported as empty here even though
    it checks something. No test in this suite has that shape today; if
    one is added, this file will say so and the choice will have to be
    made deliberately.

THE NEGATIVE CONTROL AT THE BOTTOM is the part that makes the rest
worth reading: it feeds the scanner a synthetic module containing a
name-only test, a test that computes and asserts nothing, and two tests
that do assert, and requires the scanner to accept exactly the second
pair. Without it, "the traceability check is stronger now" would be a
claim with nothing behind it, since every real test in the tree already
passes the stronger form and the file would be green either way.
"""

import ast
import re
import sys
from pathlib import Path

SW_DIR = Path(__file__).resolve().parents[1]
SPEC = SW_DIR.parents[0] / "docs" / "10-npu-mvp-spec.md"
TEST_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(SW_DIR))

# A test claims an equation by its name: test_e<n>_something.
_TEST_NAME = re.compile(r"^test_e(\d+)_")

# Context managers that are assertions in their own right. Anything else
# in a `with` is setup.
_ASSERTING_CONTEXTS = frozenset({"raises", "warns", "deprecated_call"})


def _spec_equations():
    text = SPEC.read_text(encoding="utf-8")
    return {int(n) for n in re.findall(r"\(E(\d+)\)", text)}


def _assertions_in(func):
    """How many assertions a function body contains.

    Counted, not merely detected, so a failure message can say "asserts
    nothing" and mean it.
    """
    count = 0
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            count += 1
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                call = item.context_expr
                if not isinstance(call, ast.Call):
                    continue
                func_node = call.func
                if isinstance(func_node, ast.Attribute):
                    name = func_node.attr
                elif isinstance(func_node, ast.Name):
                    name = func_node.id
                else:
                    continue
                if name in _ASSERTING_CONTEXTS:
                    count += 1
    return count


def _equation_tests(paths):
    """{equation number: [(file name, function name, assertion count)]}.

    Parsed, not matched: a function definition is a function definition
    and a string that looks like one is a string.
    """
    found = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            m = _TEST_NAME.match(node.name)
            if m:
                found.setdefault(int(m.group(1)), []).append(
                    (path.name, node.name, _assertions_in(node)))
    return found


def _test_files(directory=None):
    return sorted((directory or TEST_DIR).glob("test_*.py"))


def _named_equations(tests):
    """Equations some function is NAMED for, whatever it does."""
    return set(tests)


def _attested_equations(tests):
    """Equations that have at least one test that can fail."""
    return {n for n, cases in tests.items()
            if any(count > 0 for _f, _name, count in cases)}


def _tests_without_assertions(tests):
    return sorted((f, name) for cases in tests.values()
                  for f, name, count in cases if count == 0)


def test_spec_file_exists():
    assert SPEC.is_file(), f"spec not found at {SPEC}"


def test_every_spec_equation_has_a_test():
    spec = _spec_equations()
    tests = _equation_tests(_test_files())
    named = _named_equations(tests)
    attested = _attested_equations(tests)
    assert spec, "no numbered equations found in the spec"
    unnamed = spec - named
    assert not unnamed, \
        f"spec equations with no test_e<n>_* test at all: E{sorted(unnamed)}"
    # An equation whose only tests assert nothing is NOT covered. The
    # message separates the two cases because the repairs differ: one
    # needs a test written, the other needs a test finished.
    empty = spec - attested
    assert not empty, (
        "spec equations whose only test_e<n>_* tests contain no assertion, "
        f"so nothing about them can fail: E{sorted(empty)} -- "
        f"{[f'{f}::{n}' for f, n in _tests_without_assertions(tests)]}")


def test_every_equation_test_asserts_something():
    """Not the same question as the one above.

    The test above asks whether every EQUATION is attested; this asks
    whether every TEST is a test. An equation with four good tests and
    one empty one passes there and fails here, which is the right way
    round: the empty one is dead weight that reads as coverage.
    """
    tests = _equation_tests(_test_files())
    assert tests, "no test_e<n>_* tests found at all"
    barren = _tests_without_assertions(tests)
    assert not barren, (
        "these tests are named for a spec equation and assert nothing, so "
        "they cannot fail: " + ", ".join(f"{f}::{n}" for f, n in barren))


def test_no_test_references_undefined_equation():
    tests = _equation_tests(_test_files())
    extra = _named_equations(tests) - _spec_equations()
    assert not extra, f"tests reference equations the spec does not define: E{sorted(extra)}"


def test_expected_equation_set_is_complete():
    # The v0.1 contract is exactly E1..E10; a spec edit that renumbers or
    # drops an equation must be a conscious change here too.
    assert _spec_equations() == set(range(1, 11))


def test_a_name_without_an_assertion_does_not_count_as_coverage(tmp_path):
    """The negative control: the scanner is shown a module it must reject
    in part and accept in part, and required to draw the line in the
    right place.

    This is the check that proves the strengthening is real. Every test
    in this suite already asserts something, so the four checks above
    are green before and after the change and neither state distinguishes
    a scanner that reads bodies from one that reads names. Here the empty
    tests exist on purpose and the scanner has to notice them.

    E91 to E94 are used because the spec defines E1 to E10, so if this
    synthetic source were ever picked up as real -- which is exactly what
    the old regular expression over raw text would have done, since the
    source below is a string in a file this scan reads --
    test_no_test_references_undefined_equation fails loudly rather than
    this control quietly measuring the wrong thing.
    """
    fake = tmp_path / "test_synthetic_equations.py"
    fake.write_text(
        "import pytest\n"
        "\n"
        "\n"
        "def test_e91_named_only():\n"
        "    pass\n"
        "\n"
        "\n"
        "def test_e92_computes_and_checks_nothing():\n"
        "    # assert would go here, and does not\n"
        "    value = 2 + 2\n"
        "    print(value)\n"
        "\n"
        "\n"
        "def test_e93_actually_asserts():\n"
        "    assert 2 + 2 == 4\n"
        "\n"
        "\n"
        "def test_e94_asserts_by_raising():\n"
        "    with pytest.raises(ValueError):\n"
        "        raise ValueError('checked')\n"
        "\n"
        "\n"
        "def helper_e95_not_a_test():\n"
        "    pass\n",
        encoding="utf-8")

    tests = _equation_tests([fake])

    # Named: the four test_e* functions and not the helper.
    assert _named_equations(tests) == {91, 92, 93, 94}, \
        f"the name scan picked up {sorted(_named_equations(tests))}"

    # Attested: only the two that can fail.
    assert _attested_equations(tests) == {93, 94}, (
        "the scanner counted a test with no assertion as coverage: it "
        f"attested {sorted(_attested_equations(tests))}")

    # And it names the two barren ones, since the failure message of the
    # real checks is built from this.
    assert _tests_without_assertions(tests) == [
        (fake.name, "test_e91_named_only"),
        (fake.name, "test_e92_computes_and_checks_nothing"),
    ]

    # The shape of the real check, run against the synthetic module: an
    # equation whose only test is a name with no assertion is reported
    # missing even though the name is right there.
    pretend_spec = {91, 92, 93, 94}
    assert pretend_spec - _attested_equations(tests) == {91, 92}, \
        "an equation whose only test is a name with no assertion was " \
        "reported as covered"

    # The assertion counter distinguishes one assertion from several, so
    # a message that says "asserts nothing" is not saying "I could not
    # parse this".
    counts = {name: count for cases in tests.values() for _f, name, count in cases}
    assert counts["test_e93_actually_asserts"] == 1
    assert counts["test_e94_asserts_by_raising"] == 1
    assert counts["test_e91_named_only"] == 0
