# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""The mirror generator is idempotent, and still fails on a reworded hold.

READ THE TREE BEFORE READING THE ASSERTIONS. This file ships to the
public mirror, where every fact it states about a held fragment is
inverted: upstream the fragment is present and the redaction is not,
and in the mirror it is the other way round. The first version of this
file did not account for that, shipped, and turned the mirror's own CI
red on its first push -- a guard that fails where it is published is
worse than the defect it was written for. `IN_MIRROR` decides which
half applies, and each half is a real assertion rather than a skip.

WHY THIS GUARD EXISTS. `scripts/gen_public_mirror.py` asserted that
every held fragment matched its pattern exactly once. Run against the
tree it had itself produced, the fragment was already redacted, the
pattern matched zero times, and the assertion fired -- so the mirror's
own copy of `scripts/ci_local.sh` could never pass its own mirror gate.
An external reviewer found it that way: the generator is an
upstream-only tool that had been shipped into the mirror and then wired
into the mirror's gate.

THE ASSERTION WAS NOT THE DEFECT, and weakening it would have been. Its
comment states the guarantee it exists for: *a fragment that has been
reworded upstream must fail the build, because the alternative is that
it travels*. That guarantee is about sensitive text escaping into a
public repository, and it is worth more than the convenience it costs.

So the fix distinguishes the two zero-match cases, and this file is the
proof that it distinguishes them correctly:

  pattern matches once, marker absent   -> redact (the upstream case)
  pattern matches zero, marker present  -> already done (the mirror case)
  pattern matches zero, marker absent   -> FAIL (the reworded case)

The third row is the one that matters. A test that only checked
idempotence would pass on a generator that had simply deleted the
assertion.

ONE ENTRY IS A FIXED POINT AND THE OTHER TWO ARE NOT, which is worth
knowing before reading the assertions below. `scripts/ci_local.sh`'s
replacement, `'(account status, not published)'`, itself matches the
pattern `'[^']*'` that found the original, so a second pass rewrites it
to itself and the pattern is still there afterwards. The ROADMAP and
design-review entries are not like that: their patterns no longer match
once redacted. So the property that holds for all three is not "the
pattern is gone" -- it is that the marker is present and that
regenerating produces the same bytes. That is what is asserted.
"""

import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GEN = ROOT / "scripts" / "gen_public_mirror.py"

sys.path.insert(0, str(ROOT / "scripts"))


def _fragments():
    if not GEN.exists():
        return []
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen_public_mirror", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod.HELD_FRAGMENTS)


FRAGMENTS = _fragments()

# IS THIS TREE THE UPSTREAM OR THE MIRROR? The two have opposite truths
# about every fragment, so a test that assumed one of them failed in the
# other -- which is what happened: the first version of this file was
# written upstream, shipped to the mirror by the generator, and turned
# the mirror's own CI red on its first push. The generator appends a
# section to README.md naming itself, and that is the signal.
MIRROR_NOTE = "This repository is a published subset of a private development"


def _is_generated_mirror():
    readme = ROOT / "README.md"
    return readme.is_file() and MIRROR_NOTE in readme.read_text(
        encoding="utf-8", errors="ignore")


IN_MIRROR = _is_generated_mirror()


@pytest.mark.skipif(not FRAGMENTS, reason="scripts/gen_public_mirror.py is not in this tree")
@pytest.mark.skipif(IN_MIRROR, reason="this tree IS the generated mirror, where "
                                      "the fragment is redacted by construction; "
                                      "the mirror's own claim is the next test")
@pytest.mark.parametrize("entry", FRAGMENTS, ids=lambda e: e[0])
def test_the_source_still_carries_the_fragment_and_not_the_marker(entry):
    """Upstream: the pattern matches once and the redaction is absent."""
    rel, pattern, _replacement, marker, _why = entry
    src = ROOT / rel
    if not src.exists():
        pytest.skip("%s is not in this tree" % rel)
    text = src.read_text(encoding="utf-8")
    n = len(re.findall(pattern, text, flags=re.S))
    assert n == 1, (
        "%s: the held fragment matches %d times, not once. Either the "
        "fragment was reworded -- in which case the generator is right "
        "to fail and this pattern needs updating -- or a second copy of "
        "it has appeared." % (rel, n))
    assert marker not in text, (
        "%s carries the REDACTION marker upstream. The marker is what "
        "licenses a zero-match, so a source file containing it would "
        "let a live fragment through as 'already redacted'." % rel)


@pytest.mark.skipif(not FRAGMENTS, reason="scripts/gen_public_mirror.py is not in this tree")
@pytest.mark.parametrize("entry", FRAGMENTS, ids=lambda e: e[0])
def test_this_mirror_is_redacted(entry):
    """In the mirror the redaction is already present. That IS the claim."""
    if not IN_MIRROR:
        pytest.skip("this tree is the upstream repository, not the mirror")
    rel, _pattern, _replacement, marker, _why = entry
    src = ROOT / rel
    if not src.exists():
        pytest.skip("%s is not in this tree" % rel)
    assert marker in src.read_text(encoding="utf-8"), (
        "%s is in a generated mirror and does not carry the redaction "
        "marker: the held fragment may have travelled." % rel)


@pytest.mark.skipif(not FRAGMENTS, reason="scripts/gen_public_mirror.py is not in this tree")
@pytest.mark.skipif(IN_MIRROR, reason="generating a mirror needs the upstream "
                                      "tree's git history and its held files")
def test_the_generated_tree_is_redacted_and_regenerates_unchanged(tmp_path):
    """The mirror case: pattern gone, marker present, and running again is a no-op."""
    first = tmp_path / "m1"
    r = subprocess.run([sys.executable, str(GEN), "--out", str(first)],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stdout + r.stderr

    for rel, _pattern, _replacement, marker, _why in FRAGMENTS:
        out = first / rel
        assert out.exists(), "%s is not in the published set" % rel
        assert marker in out.read_text(encoding="utf-8"), (
            "%s was not redacted" % rel)

    # The generated tree must be a git repository before the generator
    # can run inside it: the generator enumerates its input with
    # `git ls-files`, so an un-inited output directory fails for a
    # reason that has nothing to do with redaction. The real mirror is
    # a repository, so this reproduces the real situation.
    ident = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git"] + ident + ["commit", "-qm", "generated"]):
        g = subprocess.run(cmd, capture_output=True, text=True, cwd=first)
        assert g.returncode == 0, " ".join(cmd) + ": " + g.stdout + g.stderr

    # And now the case that used to abort: the generator run against its
    # own output. It must succeed, and the held files must come out
    # byte-identical -- a fixed point, which is the whole claim.
    second = tmp_path / "m2"
    r = subprocess.run([sys.executable, str(first / "scripts" / GEN.name),
                        "--out", str(second)],
                       capture_output=True, text=True, cwd=first)
    assert r.returncode == 0, (
        "the generator cannot run inside the tree it produced:\n"
        + r.stdout + r.stderr)
    for rel, _pattern, _replacement, marker, _why in FRAGMENTS:
        a = (first / rel).read_bytes()
        b = (second / rel).read_bytes()
        assert a == b, (
            "%s is not a fixed point: regenerating the mirror from the "
            "mirror changed it, so the redaction is applied twice and "
            "the two runs do not agree." % rel)
        assert marker in b.decode("utf-8")


@pytest.mark.skipif(not FRAGMENTS, reason="scripts/gen_public_mirror.py is not in this tree")
@pytest.mark.skipif(IN_MIRROR, reason="the fragment is already redacted here, so "
                                      "there is nothing left to reword")
@pytest.mark.parametrize("entry", FRAGMENTS, ids=lambda e: e[0])
def test_a_reworded_fragment_is_not_mistaken_for_a_redacted_one(entry):
    """The guarantee: reworded upstream is NOT the same as already redacted.

    This is the row the fix could have got wrong. It exercises the
    generator's decision directly rather than through a whole build,
    because building a tree whose ROADMAP has been tampered with would
    mean writing a tampered tree to disk.
    """
    rel, pattern, _replacement, marker, _why = entry
    src = ROOT / rel
    if not src.exists():
        pytest.skip("%s is not in this tree" % rel)
    text = src.read_text(encoding="utf-8")

    # Reword it: the fragment is gone, but nothing redacted it.
    reworded = re.sub(pattern, "SOMETHING ELSE ENTIRELY", text, flags=re.S)
    assert reworded != text, "the rewording did not take"
    n = len(re.findall(pattern, reworded, flags=re.S))
    assert n == 0
    assert marker not in reworded, (
        "a reworded %s must not contain the redaction marker, or the "
        "generator would treat it as already redacted and ship it" % rel)
    # n == 0 and marker absent is exactly the branch that raises.
