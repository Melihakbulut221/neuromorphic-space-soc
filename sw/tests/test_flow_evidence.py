"""Flow-evidence drift guard: docs/12 section 4 against the retained run tree.

ROADMAP gate G0 ("sg13g2 trial harden DRC/LVS clean") is claimed by
docs/12-sg13g2-flow-bringup.md section 4, whose numbers were read once,
by hand, out of a LibreLane run directory. Nothing re-read them
afterwards. This file does, mechanically, so that G0 is auditable rather
than merely asserted: it parses the numbers the document CLAIMS and
compares them with the artifacts the run actually LEFT BEHIND.

Same discipline as the two guards this repository already has:

  * sw/tests/test_regmap.py cross-checks the register tables in docs/10
    against the generated register map;
  * sw/tests/test_traceability.py ties every numbered spec equation to a
    test.

Nothing here hard-codes a sign-off number. Both sides are read at run
time - the document is the claim, ``final/metrics.json`` and the step
report files are the evidence - so a doc edit and an artifact change are
each caught on their own.

Two classes of test live here, and the split is deliberate:

  * document-only tests (no ``pytest.skip``). They hold on a fresh clone
    and check that the document still claims what G0 needs: every
    sign-off row still reads zero, the seven Netgen counters are still
    named, the stage arithmetic still adds up, the timing table still
    covers three corners with zero violations. Relaxing the claim now
    takes a conscious edit here.
  * artifact tests, which need the run tree. Run outputs are git-ignored
    (.gitignore, ``hw/openlane/*/runs/``), so on a fresh clone there is
    nothing to audit and those tests skip with the run tag, the path and
    the command that regenerates them. They must never fail merely for
    being run somewhere the tree was not kept.

The one artifact test that fails rather than skips is
``test_documented_run_tag_is_retained``: run trees present but not the
documented one is a document pointing at evidence that is not there, and
it would otherwise be a way to silence the whole audit by editing a
string. See its docstring for the trade-off that carries.

Regenerating the evidence, from the repository root::

    hw/openlane/run_trial.sh --run-tag trial-03-signoff

Scope: section 4 sign-off and provenance only - the DRC/LVS/antenna/
timing claims of 4.1 and 4.4, the run tag and stage count of the section
preamble, and the config that produced them. The area, cell-mix and
routing tables (4.2, 4.3, 4.6) are descriptive rather than gating and
are not guarded here.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "12-sg13g2-flow-bringup.md"
DESIGN_DIR = ROOT / "hw" / "openlane" / "aer_fifo"
RUNS_DIR = DESIGN_DIR / "runs"
CONFIG = DESIGN_DIR / "config.json"

# Sign-off check -> the metric keys that carry it, keyed by the step
# directory named in the document's own table (the stable column: the
# prose label is editorial, the step name is what the flow produced).
# PER_DOC marks a row whose metric keys are themselves read out of the
# document, so that the set of counters cannot silently shrink.
PER_DOC = "per-document"

STEP_METRICS = {
    "64-magic-drc": ("magic__drc_error__count",),
    "65-klayout-drc": ("klayout__drc_error__count",),
    "70-netgen-lvs": PER_DOC,
    "69-checker-illegaloverlap": ("magic__illegal_overlap__count",),
    "62-klayout-xor": ("design__xor_difference__count",),
    "46-openroad-checkantennas-1": ("antenna__violating__nets",
                                    "antenna__violating__pins"),
    "44-openroad-detailedrouting": ("route__drc_errors",),
    "48-odb-reportdisconnectedpins": ("design__disconnected_pin__count",
                                      "design__critical_disconnected_pin__count"),
    "56-openroad-irdropreport": ("design__power_grid_violation__count__net:VPWR",
                                 "design__power_grid_violation__count__net:VGND"),
    "55-openroad-stapostpnr": PER_DOC,
}

# Per-corner violation counters behind the "Setup / hold / max-slew /
# max-cap" row of 4.1 and the "Violations" column of 4.4. Formatted with
# the corner names the document lists, never with a hard-coded corner.
CORNER_VIOLATION_KEYS = (
    "timing__setup_vio__count__corner:{corner}",
    "timing__hold_vio__count__corner:{corner}",
    "design__max_slew_violation__count__corner:{corner}",
    "design__max_cap_violation__count__corner:{corner}",
)

_WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


# ----------------------------------------------------------------------
# Document side
# ----------------------------------------------------------------------

def _doc():
    assert DOC.is_file(), (
        f"flow evidence document not found at {DOC}. ROADMAP gate G0 cites "
        f"it; without the document there is no claim left to audit.")
    text = DOC.read_text(encoding="utf-8")
    assert text.strip(), (
        f"{DOC} is empty. If another process is rewriting it, rerun; "
        f"otherwise the G0 evidence has been lost.")
    return text


def _slice(text, start, end):
    """The text between two headings, both of which must be present."""
    assert start in text, f"heading {start!r} missing from {DOC.name}"
    after = text.split(start, 1)[1]
    assert end in after, f"heading {end!r} missing after {start!r}"
    return after.split(end, 1)[0]


def _section_4_preamble():
    return _slice(_doc(), "## 4. Trial harden results", "### 4.1")


def _run_tag():
    """The run tag section 4 says every number in it comes from."""
    text = _section_4_preamble()
    m = re.search(r"come from run tag \*\*`([^`]+)`\*\*", text)
    assert m, "section 4 no longer states the run tag its numbers come from"
    return m.group(1)


def _table_rows(table, columns, key_column):
    """Markdown table body rows, split on the pipe, header rules dropped.

    A body row is a line of exactly `columns` cells whose `key_column`
    cell is backticked. Both the header row and the |---|---| rule fail
    that test, so neither needs special-casing, and a cell containing a
    backticked word of its own (the KLayout DRC row's `no_recommended`)
    is no longer mistaken for the key.
    """
    rows = []
    for line in table.splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [c.strip() for c in line[1:-1].split("|")]
        if len(cells) != columns:
            continue
        key = cells[key_column]
        if not (key.startswith("`") and key.endswith("`")):
            continue
        rows.append(cells)
    return rows


def _signoff_rows():
    """Section 4.1 rows as (label, step directory, result cell)."""
    table = _slice(_doc(), "### 4.1", "### 4.2")
    rows = [(label, step.strip("`"), result)
            for label, step, result in _table_rows(table, 3, key_column=1)]
    assert rows, "section 4.1 sign-off table did not parse"
    return rows


def _netgen_counter_names():
    """The seven LVS counters section 4.1 names under its table.

    The document writes them elided - ``design__lvs_error__count``, then
    ``..._device_difference__count`` and so on - so the ellipsis is
    expanded back to the common ``design__lvs`` prefix here.

    Whitespace is normalized before the sentence is cut out, so
    rewrapping the paragraph is not a change this test notices.
    """
    text = re.sub(r"\s+", " ", _slice(_doc(), "### 4.1", "### 4.2"))
    tail = text.split("The seven Netgen counters are", 1)
    assert len(tail) == 2, "section 4.1 no longer lists the Netgen counters"
    marker = "from `final/metrics.json`"
    assert marker in tail[1], (
        "section 4.1 no longer says where the Netgen counters were read")
    prose = tail[1].split(marker, 1)[0]
    names = []
    for token in re.findall(r"`([^`]+)`", prose):
        if token.startswith("..."):
            token = "design__lvs" + token[3:]
        if token.startswith("design__lvs"):
            names.append(token)
    return names


def _corner_rows():
    """Section 4.4 rows as dicts: corner, setup_ws, hold_ws, violations.

    Each slack also carries the number of decimals the document actually
    quotes, so the artifact comparison rounds the run's value to the
    precision that was written down rather than to a fixed four places.
    Requoting a slack more or less precisely then stays a passing edit,
    while requoting it as a DIFFERENT number does not.
    """
    table = _slice(_doc(), "### 4.4", "### 4.5")
    rows = []
    for corner, setup, hold, vio in _table_rows(table, 4, key_column=0):
        rows.append({
            "corner": corner.strip("`"),
            "setup_ws": _quoted(setup),
            "hold_ws": _quoted(hold),
            "violations": int(_quoted(vio)[0]),
        })
    assert rows, "section 4.4 timing table did not parse"
    return rows


def _quoted(cell):
    """(value, decimals) of the single number in a markdown cell."""
    plain = cell.replace("*", "").replace(",", "").strip()
    m = re.fullmatch(r"(-?\d+(?:\.(\d+))?)(\s*ns)?", plain)
    assert m, f"cell {cell!r} is not a single number"
    return float(m.group(1)), len(m.group(2) or "")


def _agrees(measured, quoted):
    """Does the run's value round to the number the document quotes?"""
    value, decimals = quoted
    return round(measured, decimals) == value


def _integers(cell):
    return [int(n) for n in re.findall(r"-?\d+", cell.replace(",", ""))]


# ----------------------------------------------------------------------
# Artifact side
# ----------------------------------------------------------------------

def _retained_run_tags():
    if not RUNS_DIR.is_dir():
        return []
    return sorted(p.name for p in RUNS_DIR.iterdir() if p.is_dir())


def _skip_no_run(path, tag):
    pytest.skip(
        f"sign-off run tree absent: {path} does not exist. Run outputs are "
        f"git-ignored (.gitignore, 'hw/openlane/*/runs/'), so a fresh clone "
        f"has no artifacts to audit and the claims in {DOC.name} section 4 "
        f"cannot be rechecked here. Regenerate with "
        f"'hw/openlane/run_trial.sh --run-tag {tag}' from the repository "
        f"root, then rerun this file.")


@pytest.fixture(scope="module")
def run_dir():
    """The run tree section 4 says its numbers came from.

    No run trees at all -> skip. Some run trees but not the documented
    one -> skip here and fail once, in
    test_documented_run_tag_is_retained, so the diagnosis is reported by
    a named test instead of nine identical fixture errors.
    """
    tag = _run_tag()
    path = RUNS_DIR / tag
    if path.is_dir():
        return path
    if not _retained_run_tags():
        _skip_no_run(path, tag)
    pytest.skip(
        f"documented run tag {tag!r} is not among the retained runs "
        f"{_retained_run_tags()}; see the failure reported by "
        f"test_documented_run_tag_is_retained")


@pytest.fixture(scope="module")
def metrics(run_dir):
    path = run_dir / "final" / "metrics.json"
    if not path.is_file():
        _skip_no_run(path, _run_tag())
    return json.loads(path.read_text(encoding="utf-8"))


def _metric(metrics, key):
    assert key in metrics, (
        f"metric {key} absent from final/metrics.json; the document claims a "
        f"number this run does not report")
    return metrics[key]


# ----------------------------------------------------------------------
# Document-only: what G0 is being told. Holds on a fresh clone.
# ----------------------------------------------------------------------

def test_evidence_document_exists():
    assert DOC.is_file(), f"ROADMAP G0 evidence document missing: {DOC}"


def test_signoff_table_covers_exactly_the_known_steps():
    """Every 4.1 row maps to metric keys, and every mapping has a row.

    A row added to the document without a metric behind it, or a mapping
    left here after its row was deleted, fails rather than passing
    unchecked.
    """
    steps = [step for _, step, _ in _signoff_rows()]
    assert len(steps) == len(set(steps)), f"duplicate step rows: {steps}"
    assert set(steps) == set(STEP_METRICS), (
        f"section 4.1 rows and the metric mapping disagree; "
        f"document only: {sorted(set(steps) - set(STEP_METRICS))}, "
        f"mapping only: {sorted(set(STEP_METRICS) - set(steps))}")


def test_every_signoff_row_still_claims_zero():
    """G0 is a zero-error claim. Every number in every result cell is 0.

    Relaxing any of them - "2 errors, waived" - fails here, which is the
    point: the ROADMAP gate would then be describing something else.
    """
    for label, step, result in _signoff_rows():
        values = _integers(result)
        assert values, f"{step} ({label}): result cell states no number"
        assert all(v == 0 for v in values), (
            f"{step} ({label}): document no longer claims zero: {result!r}")


def test_seven_netgen_counters_are_named():
    names = _netgen_counter_names()
    assert len(names) == 7, (
        f"section 4.1 names {len(names)} LVS counters, not seven: {names}")
    assert len(set(names)) == 7, f"duplicate counter names: {names}"
    for name in names:
        assert name.startswith("design__lvs"), name
        assert name.endswith("__count"), name


def test_stage_arithmetic_is_self_consistent():
    """80 stages reported = 76 step directories + the four gated off."""
    text = _section_4_preamble()
    m = re.search(r"reported \*\*(\d+) stages\*\* and produced "
                  r"\*\*(\d+) numbered step directories\*\*", text)
    assert m, "section 4 no longer states its stage and step-directory counts"
    stages, step_dirs = int(m.group(1)), int(m.group(2))
    skipped = re.search(r"the (\w+) that did not run", text)
    assert skipped, "section 4 no longer accounts for the stages that did not run"
    n_skipped = _WORD_NUMBERS[skipped.group(1).lower()]
    assert step_dirs + n_skipped == stages, (
        f"{step_dirs} step directories + {n_skipped} not run != {stages} stages")


def test_timing_table_claims_zero_violations_on_three_corners():
    rows = _corner_rows()
    assert len(rows) == 3, f"section 4.4 lists {len(rows)} corners, not three"
    corners = [row["corner"] for row in rows]
    assert len(set(corners)) == 3, f"duplicate corners: {corners}"
    for row in rows:
        name = row["corner"]
        assert row["violations"] == 0, (
            f"{name}: document claims {row['violations']} violations")
        assert row["setup_ws"][0] > 0, (
            f"{name}: setup slack {row['setup_ws'][0]} is not positive")
        assert row["hold_ws"][0] > 0, (
            f"{name}: hold slack {row['hold_ws'][0]} is not positive")


# ----------------------------------------------------------------------
# Artifact: what the run actually produced. Skips without the run tree.
# ----------------------------------------------------------------------

def test_documented_run_tag_is_retained():
    """A retained run tree must include the tag section 4 cites.

    Skips when no run tree was kept at all, which is the fresh-clone
    case and the state docs/12 section 10 item 11 explicitly allows
    ("the trees can be deleted at any time"). When runs ARE present, a
    documented tag that is not among them fails here, so that renaming
    the tag in the document is not a way to turn the whole artifact
    audit into a silent skip.

    The one false positive this rule can produce is pruning only the
    sign-off run while keeping the superseded ones. The remedy is in
    the message, and it is a deliberate trade: a loud failure when the
    evidence for G0 specifically is the tree that went away is the
    behaviour worth having.
    """
    tag = _run_tag()
    retained = _retained_run_tags()
    if not retained:
        _skip_no_run(RUNS_DIR / tag, tag)
    assert tag in retained, (
        f"{DOC.name} section 4 attributes its numbers to run tag {tag!r}, "
        f"but {RUNS_DIR} retains only {retained}. Either the tag was renamed "
        f"in the document without moving the evidence, or the sign-off run "
        f"was deleted while superseded runs were kept. Remedy: regenerate it "
        f"with 'hw/openlane/run_trial.sh --run-tag {tag}', or remove the "
        f"remaining trees too so this file skips as it does on a fresh "
        f"clone.")


def test_signoff_step_directories_exist(run_dir):
    """Each step the document cites left a directory in the run tree."""
    for _, step, _ in _signoff_rows():
        assert (run_dir / step).is_dir(), (
            f"{run_dir.name} has no {step}/; the document cites a step this "
            f"run did not produce")


def test_signoff_metrics_match_the_document(run_dir, metrics):
    """The zeros claimed in 4.1 are the zeros in final/metrics.json."""
    corners = [row["corner"] for row in _corner_rows()]
    for label, step, result in _signoff_rows():
        keys = STEP_METRICS[step]
        if keys is PER_DOC:
            if step == "70-netgen-lvs":
                keys = tuple(_netgen_counter_names())
            else:
                keys = tuple(template.format(corner=corner)
                             for corner in corners
                             for template in CORNER_VIOLATION_KEYS)
        claimed = _integers(result)
        for key in keys:
            got = _metric(metrics, key)
            assert got in claimed, (
                f"{step} ({label}): document claims {result!r} but "
                f"{key} = {got}")
            assert got == 0, f"{step} ({label}): {key} = {got}, expected 0"


def test_netgen_lvs_counters_are_zero(metrics):
    """All seven counters exist in the artifact and all seven read zero."""
    for name in _netgen_counter_names():
        assert _metric(metrics, name) == 0, f"{name} = {metrics[name]}"


def test_timing_slacks_and_violations_match_the_document(metrics):
    """Section 4.4 corner by corner: the slacks the document quotes are
    the run's slacks rounded to four decimals, and every violation
    counter for that corner is zero."""
    for row in _corner_rows():
        corner = row["corner"]
        for column, key in (("setup_ws", f"timing__setup__ws__corner:{corner}"),
                            ("hold_ws", f"timing__hold__ws__corner:{corner}")):
            measured = _metric(metrics, key)
            assert _agrees(measured, row[column]), (
                f"{corner}: document says {column} {row[column][0]} ns to "
                f"{row[column][1]} decimals, run says {measured} ns")
        for template in CORNER_VIOLATION_KEYS:
            key = template.format(corner=corner)
            assert _metric(metrics, key) == row["violations"], (
                f"{corner}: {key} = {metrics[key]}, document claims "
                f"{row['violations']}")
        for key in (f"timing__setup__tns__corner:{corner}",
                    f"timing__hold__tns__corner:{corner}"):
            assert _metric(metrics, key) == 0, f"{key} = {metrics[key]}"


def test_metrics_report_exactly_the_documented_corners(metrics):
    """The document says "all three corners". The run analysed exactly
    those three, so the claim covers the whole set and not a subset."""
    documented = {row["corner"] for row in _corner_rows()}
    prefix = "timing__setup__ws__corner:"
    found = {k[len(prefix):] for k in metrics if k.startswith(prefix)}
    assert found == documented, (
        f"run analysed corners {sorted(found)}, document lists "
        f"{sorted(documented)}")


def test_numbered_step_directory_count_matches_the_document(run_dir):
    text = _section_4_preamble()
    m = re.search(r"\*\*(\d+) numbered step directories\*\*", text)
    assert m, "section 4 no longer states a step-directory count"
    claimed = int(m.group(1))
    found = sorted(p.name for p in run_dir.iterdir()
                   if p.is_dir() and re.match(r"^\d+-", p.name))
    assert len(found) == claimed, (
        f"{run_dir.name} has {len(found)} numbered step directories, "
        f"document claims {claimed}")


def test_raw_drc_reports_agree_with_the_metrics(run_dir, metrics):
    """Cross-check the two DRC decks against their own report files, not
    only against the summary metrics the same flow wrote."""
    magic = run_dir / "64-magic-drc" / "reports" / "drc.magic.rpt"
    assert magic.is_file(), f"missing {magic}"
    m = re.search(r"COUNT:\s*(\d+)", magic.read_text(encoding="utf-8"))
    assert m, f"{magic.name} carries no COUNT line"
    assert int(m.group(1)) == 0, f"Magic DRC report COUNT: {m.group(1)}"
    assert int(m.group(1)) == _metric(metrics, "magic__drc_error__count")

    klayout = run_dir / "65-klayout-drc" / "reports" / "drc.klayout.json"
    assert klayout.is_file(), f"missing {klayout}"
    per_rule = json.loads(klayout.read_text(encoding="utf-8"))
    assert per_rule, "KLayout DRC report lists no rules at all"
    offenders = {rule: n for rule, n in per_rule.items() if n}
    assert not offenders, f"KLayout DRC rules with violations: {offenders}"
    assert sum(per_rule.values()) == _metric(metrics, "klayout__drc_error__count")


def test_flow_ran_to_completion_without_errors(run_dir, metrics):
    """The zeros only mean anything if the flow finished. Section 4 says
    all stages ran; the run tree has to agree."""
    error_log = run_dir / "error.log"
    assert error_log.is_file(), f"missing {error_log}"
    assert error_log.read_text(encoding="utf-8").strip() == "", (
        f"{error_log} is not empty:\n{error_log.read_text(encoding='utf-8')[:2000]}")
    flow_log = run_dir / "flow.log"
    assert flow_log.is_file(), f"missing {flow_log}"
    assert flow_log.read_text(encoding="utf-8").rstrip().endswith("Flow complete."), (
        "flow.log does not end with 'Flow complete.'")
    assert _metric(metrics, "flow__errors__count") == 0
    assert _metric(metrics, "design__violations") == 0


def test_committed_config_is_the_config_that_produced_the_evidence(run_dir):
    """Section 4 says its numbers come from hw/openlane/aer_fifo/config.json
    "exactly as committed". Every key of the committed config must appear
    in the run's resolved.json with the same value.

    ``//``-prefixed keys are the config's own comments: LibreLane drops
    them silently (docs/12 section 2.4c), so they are skipped here too.
    ``dir::`` values are paths relative to the config file, which the
    flow expands to absolute; they are compared by tail, so relocating
    the checkout does not manufacture a failure while pointing the key at
    a different file still does.
    """
    assert CONFIG.is_file(), f"missing {CONFIG}"
    resolved_path = run_dir / "resolved.json"
    assert resolved_path.is_file(), f"missing {resolved_path}"
    committed = json.loads(CONFIG.read_text(encoding="utf-8"))
    resolved = json.loads(resolved_path.read_text(encoding="utf-8"))

    def same(want, got):
        if isinstance(want, str) and want.startswith("dir::"):
            target = (CONFIG.parent / want[len("dir::"):]).resolve()
            assert target.is_relative_to(ROOT), (
                f"config path {want!r} points outside the repository")
            tail = target.relative_to(ROOT).as_posix()
            return isinstance(got, str) and Path(got).as_posix().endswith(tail)
        if isinstance(want, list):
            return (isinstance(got, list) and len(want) == len(got)
                    and all(same(w, g) for w, g in zip(want, got)))
        return want == got

    for key, value in committed.items():
        if key.startswith("//"):
            continue
        assert key in resolved, (
            f"committed config key {key} is absent from {run_dir.name}/"
            f"resolved.json: this run did not execute the committed config")
        assert same(value, resolved[key]), (
            f"{key}: committed config has {value!r}, run resolved to "
            f"{resolved[key]!r}")
