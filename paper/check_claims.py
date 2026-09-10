#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
# SPDX-License-Identifier: Apache-2.0
"""Re-derive the numbers the paper prints.

    python3 paper/check_claims.py            check every claim
    python3 paper/check_claims.py --list     what is checked and how

WHY THIS EXISTS

The paper's thesis is that a green result gets read wider than what it
actually looked at. A paper making that argument while printing figures
that nobody re-derives would be the thesis committed in its own text.

So `paper/claims.yaml` names every number the paper prints and how it is
backed, and this script re-derives the ones that can be re-derived. It
is deliberately unforgiving in one direction: a claim it cannot check is
reported as UNCHECKED and counted, never quietly passed.

WHAT IT CANNOT DO, AND SAYS SO

Claims marked `manual` are read from an artefact by a person once. This
script does not verify them; it verifies that each one names an artefact
and what was read from it. That is weaker than a check and stronger than
a footnote, and the summary prints how many there are so the ratio is
visible.

Claims marked `needs_run_tree` depend on a LibreLane run directory,
which is gitignored build output. In a clone they are reported SKIPPED
with that reason, not passed.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    """A tiny YAML reader for the subset this file uses.

    IT MUST NOT BE MORE TOLERANT THAN YAML. On 2026-09-10 an
    unterminated quote made claims.yaml invalid, and this reader --
    which takes the rest of the line and shrugs -- accepted it, so the
    registry was broken for a day and every check still ran. It now
    refuses a file that PyYAML would refuse, when PyYAML is available,
    and says so when it is not.

    Deliberately not a dependency: this script has to run in a bare
    clone, and a checker that needs `pip install` before it can check
    anything is a checker that does not get run.
    """
    try:
        import yaml
    except ImportError:
        print("note: PyYAML absent, so claims.yaml is parsed leniently and "
              "a syntax error in it would go unnoticed", file=sys.stderr)
    else:
        try:
            yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            raise SystemExit(
                f"{path} is not valid YAML and the registry is therefore "
                f"not trustworthy:\n{exc}")

    claims, cur = [], None
    for raw in path.read_text().splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("claims:"):
            continue
        stripped = raw.strip()
        if stripped.startswith("- "):
            cur = {}
            claims.append(cur)
            stripped = stripped[2:]
        if cur is None or ":" not in stripped:
            continue
        k, _, v = stripped.partition(":")
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        elif v in ("true", "false"):
            v = v == "true"
        else:
            try:
                v = int(v)
            except ValueError:
                try:
                    v = float(v)
                except ValueError:
                    pass
        cur[k.strip()] = v
    return claims


def dig(obj, path):
    for part in path.split("."):
        if isinstance(obj, dict) and part in obj:
            obj = obj[part]
        else:
            # A key with dots in it, e.g. an instance path.
            for k in list(obj):
                if path.endswith(k):
                    return obj[k]
            return None
    return obj


def run(cmd):
    return subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True,
                          text=True)


def check(c):
    """Return (state, detail). State is PASS, FAIL, SKIP or UNCHECKED."""
    kind = c.get("check")

    if kind == "manual":
        if not c.get("artefact") or not c.get("read"):
            return "FAIL", "manual claim names no artefact or no reading"
        return "UNCHECKED", f"read once from {c['artefact']}"

    if kind == "blob":
        out = run(f"git hash-object {c['path']}")
        if out.returncode != 0:
            return "FAIL", out.stderr.strip()
        got = out.stdout.strip()[:len(str(c["value"]))]
        return ("PASS", got) if got == c["value"] else ("FAIL", f"{got} != {c['value']}")

    if kind == "file":
        p = ROOT / c["file"]
        if not p.is_file():
            return "FAIL", f"{c['file']} missing"
        return (("PASS", "present") if str(c["contains"]) in p.read_text()
                else ("FAIL", f"{c['contains']!r} not in {c['file']}"))

    if kind == "tsv":
        # The LAST row of an append-only log, by column name. Substring
        # matching anywhere in the file -- which is what this claim used
        # to do -- is green on any file that happens to contain the
        # digits, including in a superseded row the log deliberately
        # keeps standing.
        f = ROOT / c["file"]
        if not f.is_file():
            return "FAIL", f"{c['file']} missing"
        rows = [l for l in f.read_text().split("\n")
                if l.strip() and not l.startswith("#")]
        if len(rows) < 2:
            return "FAIL", "no data rows"
        head, last = rows[0].split("\t"), rows[-1].split("\t")
        if c["column"] not in head:
            return "FAIL", f"no column {c['column']!r}"
        got = last[head.index(c["column"])]
        return (("PASS", f"{got} (last row, {last[1]})")
                if str(got) == str(c["value"])
                else ("FAIL", f"{got} != {c['value']} in the last row"))

    if kind == "grep":
        # How many live documents still make a claim the evidence no longer
        # supports. The paper asserts that a sweep happened; this counts
        # what is left, so the assertion is checked rather than announced.
        import fnmatch
        pats = [x.strip() for x in c["pattern"].split("||")]
        globs = [g.strip() for g in c["paths"].split(",")]
        hits = []
        # A GLOB THAT MATCHES NOTHING IS A FAILURE, not a zero. On
        # 2026-09-10 an unterminated quote in claims.yaml swallowed the
        # rest of the line, so this claim's first glob was the literal
        # `"README.md` and matched no file -- and the check reported 0
        # hits and passed. It was reporting that its own paths were
        # broken, in the shape of a clean result.
        empty = [g for g in globs if not list(ROOT.glob(g))]
        if empty:
            # A glob into a gitignored build tree is EMPTY IN A CLONE and
            # that is not a broken claim, it is an absent artefact. The
            # first version could not tell the two apart and failed the
            # LVS claim on a GitHub runner where no run directory can
            # exist. `needs_run_tree` is the same distinction the `run`
            # and `json` kinds already make.
            if c.get("needs_run_tree"):
                return "SKIP", ("the run tree these globs point into is "
                                "gitignored build output and is not in "
                                "this checkout")
            return "FAIL", ("these path globs match no file, so the check "
                            "looked at nothing: " + ", ".join(empty))
        files = sorted({f for g in globs for f in ROOT.glob(g)})
        for f in files:
            rel = f.relative_to(ROOT)
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
                continue
            for i, line in enumerate(text.split("\n"), 1):
                if any(pat in line for pat in pats):
                    hits.append(f"{rel}:{i}")
        got = len(hits)
        detail = str(got) + ("" if not hits else "  " + ", ".join(hits[:4]))
        return (("PASS", detail) if got == int(c["value"])
                else ("FAIL", f"{detail} != {c['value']}"))

    if kind == "json":
        # A value read straight out of a file the run itself wrote. This is
        # the strongest evidence available for a claim about how something
        # was configured: the artefact is the configuration.
        f = ROOT / c["file"]
        if not f.is_file():
            return "SKIP", (f"{c['file']} is build output and is not in this "
                            "checkout")
        try:
            got = json.loads(f.read_text())[c["key"]]
        except KeyError:
            return "FAIL", f"key {c['key']!r} absent from {c['file']}"
        except json.JSONDecodeError as exc:
            return "FAIL", f"not JSON: {exc}"
        return (("PASS", repr(got)) if str(got) == str(c["value"])
                else ("FAIL", f"{got!r} != {c['value']!r}"))

    if kind == "absent":
        hits = list(ROOT.glob(c["glob"]))
        return (("PASS", "nothing matches, as claimed") if not hits
                else ("FAIL", f"{len(hits)} match {c['glob']}"))

    if kind == "run":
        if c.get("needs_run_tree"):
            probe = ROOT / "hw/openlane/pilot_ihp/runs/signoff-6x2/final/def"
            if not probe.is_dir():
                return "SKIP", ("the sign-off run tree is gitignored build "
                                "output and is not in this checkout")
        out = run(c["cmd"])
        if out.returncode != 0:
            return "FAIL", (out.stderr or out.stdout).strip()[:200]
        if "json_path" in c:
            try:
                got = dig(json.loads(out.stdout), c["json_path"])
            except json.JSONDecodeError as exc:
                return "FAIL", f"not JSON: {exc}"
        elif "regex" in c:
            m = re.search(c["regex"], out.stdout)
            got = m.group(1) if m else None
        else:
            got = out.stdout.strip()
        if got is None:
            return "FAIL", "value not found in output"
        try:
            ok = abs(float(got) - float(c["value"])) < 1e-6
        except (TypeError, ValueError):
            ok = str(got) == str(c["value"])
        return ("PASS", str(got)) if ok else ("FAIL", f"{got} != {c['value']}")

    return "FAIL", f"unknown check kind {kind!r}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    claims = load(ROOT / "paper" / "claims.yaml")
    if args.list:
        for c in claims:
            print(f"{c['id']:34s} {c.get('check','?'):9s} {c.get('text','')}")
        return 0

    tally = {"PASS": 0, "FAIL": 0, "SKIP": 0, "UNCHECKED": 0}
    bad = []
    for c in claims:
        state, detail = check(c)
        tally[state] += 1
        mark = {"PASS": "ok  ", "FAIL": "FAIL", "SKIP": "skip",
                "UNCHECKED": "man "}[state]
        print(f"{mark} {c['id']:34s} {detail}")
        if state == "FAIL":
            bad.append(c["id"])

    print(f"\n{tally['PASS']} re-derived, {tally['UNCHECKED']} read from a "
          f"named artefact by hand, {tally['SKIP']} need build output not in "
          f"this checkout, {tally['FAIL']} wrong")
    if tally["UNCHECKED"]:
        print("The hand-read claims are the paper's weakest evidence and the "
              "count is printed\nso the ratio is visible rather than implied.")
    if bad:
        print("\nwrong: " + ", ".join(bad))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
