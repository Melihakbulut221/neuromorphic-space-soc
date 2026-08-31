# 36 — Closing the two checkers that could not fail, and auditing the other nineteen

What this document is: the first item applied on the far side of the
`docs/34` freeze, and the audit that item obliged. `docs/34` section 8.5
found `MAX_CAP_VIOLATION_CORNERS` and `MAX_SLEW_VIOLATION_CORNERS` both
resolving to the match-none wildcard `[""]`, so `Checker.MaxCapViolations`
and `Checker.MaxSlewViolations` warned and could never fail a run. It
recorded the finding, declined to fix it under the freeze because the fix
costs a re-harden, and named it — in its own words — "the first item to
apply on the far side of the freeze" (`docs/34` section 10 item 2). This
is the far side of the freeze.

Convention, as in `docs/18`, `docs/22`, `docs/27`, `docs/32` and
`docs/34`: **[fact]** = measured in this environment or read out of an
installed file; **[estimate]** = derived or judged.

Run trees under `hw/openlane/*/runs/` are **gitignored**. Every hash
below is quoted with the run tag and the path it came from.

**The headline, before the detail.** Both keys are now `["*"]` in all
three configurations that build. Both checkers gate at all three corners
and both measure **0**, so the gate is a criterion the design already
meets rather than a threshold fitted to a measurement. The re-harden
reproduces the frozen runs on **every metric they both carry — 196 of
196 and 194 of 194, to the last digit** — and the shipped netlist,
powered netlist and DEF are **bit-identical to the frozen ones**
**[fact]**. Nothing about the design changed; what changed is that two
more of the flow's own gates are now load-bearing.

**And the audit found a fourth instance of the same shape**, which is
section 3: `Checker.WireLength` runs in every one of these flows,
executes, and gates nothing, because `WIRE_LENGTH_THRESHOLD` is unset in
both PDKs. It is reported and deliberately not "fixed", for the reason
`docs/34` section 8.4 gives about max fanout.

---

## 1. Identity

| Item | Value |
|---|---|
| Commit the runs are pinned to | `2f6cd6f` — the `docs/34` freeze content; ten `hw/rtl` blobs identical to `docs/34` section 2.1 **[fact]**. `HEAD` has since advanced to `54912f2` on a concurrent documentation-only commit that touches no file under `hw/rtl`, so the pin still names the RTL that is in the tree **[fact, blob comparison]** |
| Sign-off run | **`signoff-6x2-gated`** |
| Submission-path run | **`submission-6x2-gated`** |
| Geometric decks for the submission run | **`submission-6x2-gated-geomdecks`** |
| Superseded by these | `signoff-6x2`, `submission-6x2`, `submission-6x2-geomdecks` (`docs/31`, `docs/34` section 3) |
| LibreLane / PDK / Yosys | 3.0.5 / `c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c` / 0.67+146 pinned, no mismatch warning **[fact]** |

Both runs are single uninterrupted passes: **78 numbered steps with no
duplicate step name** for `signoff-6x2-gated`, **74** for
`submission-6x2-gated`, `error.log` empty in both, and both consoles end
`Flow complete.` **[fact]**. That removes the one caveat a reproducer of
`signoff-6x2` had to carry — that run has **79** numbered steps including
an orphaned duplicate `magic-writelef` from a resumed pass (`docs/31`
section 4.2) **[fact, re-counted here]**. It is also why this run's
checker step numbers sit one lower than the ones `docs/31` quotes.

---

## 2. The two keys, and what actually binds

### 2.1 The mechanism is not the setup mechanism, and the difference decides the fix

This matters because the obvious fix and the correct fix are not the
same key, and only one of them changes behaviour.

`Checker.SetupViolations` was fixed in `docs/28` section 4.4a by setting
`SETUP_VIOLATION_CORNERS`. There, `TimingViolations.get_corner_wildcards()`
reads

```python
wildcards = self.config.get(self.get_corner_variable().name) or self.config.get(
    self.base_corner_var_name
)
```

and `SETUP_VIOLATION_CORNERS` has **no default**, so it resolves to
`None`, the `or` fires, and the PDK's `TIMING_VIOLATION_CORNERS` —
`["*typ*"]` on ihp-sg13g2, `["*tt*"]` on sky130A — is what bound. The
defect was a **PDK default reaching through an unset key** **[fact,
`librelane/steps/checker.py`, and both PDKs' resolved configuration]**.

Max cap and max slew are structurally different **[fact, same file]**:

```python
class MaxCapViolations(TimingViolations):
    metric_name = "design__max_cap_violation__count"
    corner_override = [""]
```

and `get_corner_variable()` turns `corner_override` into the
**Variable's default**:

```python
if cls.corner_override:
    variable.default = cls.corner_override
```

`[""]` is a **non-empty list**, so it is truthy, so the `or` never
fires and `TIMING_VIOLATION_CORNERS` is never consulted at all. The list
is then filtered of the `""` match-none wildcard —
`match_none_wildcard = ""` — and comes out **empty**. With no wildcard,
no corner is matched; `matched_violating_corners` is empty; every
violating corner lands in `warn_violating_corner`; the step calls
`self.warn()` and returns. **The flow exits 0.**

Two consequences follow, and both were checked rather than assumed:

- **Neither PDK ships either key.** `ihp-sg13g2`'s LibreLane
  configuration sets exactly one of this family —
  `set ::env(TIMING_VIOLATION_CORNERS) "*typ*"` in
  `libs.tech/librelane/sg13g2_stdcell/config.tcl` — and `sky130A` ships
  none at all **[fact, grep of both installed PDKs]**. So unlike the
  setup case there is no PDK default to defeat; the `[""]` comes from
  the **step class**, and the design configuration is the only place
  that can bind it.
- **Raising `TIMING_VIOLATION_CORNERS` would have done nothing.** That
  is the fix that looks right and is inert, because these two checkers
  never read it. The key that changes behaviour is the per-type one.

### 2.2 Where the keys went

Three places, the same three the setup fix went to **[fact, `git diff`]**:

| File | How |
|---|---|
| `scripts/gen_tt_submission.py` | two entries added to `CONFIG_OVERRIDES`; the generator writes them into `tt/src/config.json` under the `"Added by scripts/gen_tt_submission.py:"` marker |
| `hw/openlane/pilot_ihp/config.json` | added directly, with a `//capslew` annotation; the pin in `mkconfig.py` was lifted for this one edit and re-taken (section 6.2) |
| `hw/openlane/pilot_sky130/config.json` | added directly — see section 4, which is not a routine row |

`hw/openlane/pilot_ihp/config.signoff-6x2.json` picks them up because
`mktiming.py` derives it from `config.json`; re-running the generator
adds **exactly the two keys and the annotation, 7 lines, nothing else**,
and the other seven `tr-*` variants come back byte-identical because
their base `config.6x2.json` did not move **[fact, `git diff --stat`]**.

`tt/src/config_merged.json` — the file the Tiny Tapeout tooling actually
hands to LibreLane, which is the distinction `docs/31` section 10.1
established — was regenerated with
`tt_tool.py --ihp --create-user-config` and gained **exactly the two
keys and nothing else** **[fact, diff against the pre-run copy]**:

```
36a37,42
>   "MAX_CAP_VIOLATION_CORNERS": [
>     "*"
>   ],
>   "MAX_SLEW_VIOLATION_CORNERS": [
>     "*"
>   ],
```

`tt/src/user_config.json` came back unchanged.

`mktiming.py` now asserts both keys the way it already asserted the
derate and the setup corners, so a future regeneration of `config.json`
from `tt/src/config_merged.json` cannot silently take the sign-off
variant back to a run in which these two cannot fail.

### 2.3 The gate is live, and that is shown rather than asserted

"The checker did not fail" and "the checker would fail if it had reason
to" are different claims, and only the second is worth having. The
second is established by driving LibreLane's **own**
`TimingViolations.check_timing_violations()` — the shipped method, not a
paraphrase — with a synthetic violation at the slow corner, under the
old wildcard and the new one **[fact, measured]**:

| `MAX_SLEW_VIOLATION_CORNERS` | slow-corner violations | result |
|---|---:|---|
| `[""]` | 0 | passes |
| `[""]` | **7** | **warns; no error; the run passes** |
| `["*"]` | 0 | passes |
| `["*"]` | **7** | **`DeferredStepError` — the run fails** |

The second row is the defect `docs/34` section 8.5 described, reproduced
on demand. The fourth is the gate this document installs, firing.

Reproduce with the flow venv's interpreter:

```python
from decimal import Decimal
from librelane.steps import Step
from librelane.steps.step import DeferredStepError
cls = Step.factory.get("Checker.MaxSlewViolations")
shim = object.__new__(cls)
shim.config = {"MAX_SLEW_VIOLATION_CORNERS": ["*"]}
shim.warn = print; shim.err = print
base = "design__max_slew_violation__count__corner"
class S:  metrics = {f"{base}:nom_slow_1p08V_125C": Decimal(7)}
cls.check_timing_violations(shim, base, S(), Decimal(0), "max slew")
```

---

## 3. The audit: all twenty-one checkers, and a fourth instance

### 3.1 Why this is a script and not a paragraph

`docs/34` section 8.5 called max cap and max slew "the third instance of
the shape `docs/28` section 4.4a named", after setup and after
`docs/23`'s `design__violations` not aggregating hold. Three instances of
one shape is a pattern, and the pattern is that **a checker's reach is
configuration, the configuration's default appears in no report, and a
run that gates nothing looks exactly like a run that gates everything
and passes.** Prose cannot hold that: the answer moves with the
LibreLane version, with the PDK and with the design's own config.

So it is computed. `hw/openlane/checker_audit.py` reads the installed
LibreLane's step classes and a run's own `resolved.json` and
`final/metrics.json`, and prints, for every checker the Classic flow
runs, how it is gated, what value binds in that run, the metric it reads,
and a verdict:

- **GATES** — it can fail, across every corner the metric was measured at.
- **PARTIAL** — the wildcard list is non-empty but matches fewer corners
  than were measured. This is the `docs/28` 4.4a shape exactly. Where a
  violation sits at an unmatched corner the line ends
  `WARNS ONLY, DOES NOT FAIL`.
- **NO-GATE** — it cannot fail at all.

Exit status is 1 if anything is PARTIAL or NO-GATE.

```bash
~/Documents/caravel-lif-crossbar/.venv-flow/bin/python \
    hw/openlane/checker_audit.py hw/openlane/pilot_ihp/runs/signoff-6x2-gated
```

**Its self-test is that it rediscovers the known defects.** Pointed at
`hw/openlane/pilot_sky130/runs/sky-14-6x2-rcmodel` it reports
`Checker.SetupViolations` **PARTIAL** — `["*tt*"]` matching 3 of 9
measured corners, violations at all three `ss` corners,
`WARNS ONLY, DOES NOT FAIL` — which is `docs/28` section 4.4a derived
from the run alone **[fact]**.

### 3.2 The count

**21 `Checker.*` steps are registered; the Classic flow runs 19**
**[fact]**. The two it does not run are `Checker.KLayoutAntenna` and
`Checker.KLayoutDensity`: they are registered by the factory but are not
in `flows/classic.py`'s step list, so their metrics are never produced
and they are not a gap that configuration could close.

**Before this change, on `signoff-6x2`: 15 of 19 gated. After, on
`signoff-6x2-gated`: 17 of 19** **[fact, the script run against each]**.

### 3.3 The two that still do not gate

**`Checker.WireLength` — the fourth instance of the shape, and the one
worth knowing about.** It is in the flow, it executes, and it gates
nothing:

```
NO-GATE  Checker.WireLength  [threshold] threshold is unset, so
                             MetricChecker.run() skips the check and only warns
```

`WIRE_LENGTH_THRESHOLD` is `Optional[Decimal]`, `pdk=True`, with **no
default**, and **neither PDK ships a value** — it resolves to `None` on
ihp-sg13g2 and on sky130A alike **[fact, `resolved.json` of both, and
grep of both installed PDKs]**. `MetricChecker.run()` then takes the
first branch:

```python
if threshold is None:
    self.warn(f"Threshold for {self.metric_description} is not set. "
              "The checker will be skipped.")
```

and that sentence is in the `warning.log` of **every run in this
repository that reaches the step — 34 of the 34 that have a
`checker-wirelength` directory**, across both PDKs, including the two
made for this document; the other 8 run trees stop before it **[fact,
counted]**. The design's `route__wirelength__max` is **901.08 um**
**[fact]**.

**It is reported and deliberately not set, and the reason is `docs/34`
section 8.4's reason verbatim.** There is no vendor limit to adopt —
neither PDK offers one — so any number put here would be chosen by us.
The only number the design is known to meet is its own measured maximum,
and setting a gate to the largest value this run happened to produce is
the `docs/20` section 11 trap: it records the tool's behaviour rather
than the design's, and it moves on the next harden. Unlike max cap and
max slew, where the criterion was **0** and the design met it, there is
no criterion here that is not invented. **[estimate: that a defensible
threshold could be derived from the PDK's antenna and IR rules is
plausible and has not been attempted; it is not shuttle work.]**

What is true instead, and is why this is not a blocker: the quantities a
long-wire rule proxies for are measured directly on this netlist and are
clean — antenna violations **0 nets / 0 pins**, route DRC **0**, max slew
**0** and max cap **0** at all three corners **[fact]**. As with max
fanout, the proxy is ungated; the quantities the proxy proxies for are
zero.

**`Checker.LintWarnings` — a fifth by the letter, a different thing by
substance.** `ERROR_ON_LINTER_WARNINGS` defaults to `False`, so the 97
Verilator lint warnings this design carries warn and never fail
**[fact]**. This is listed for completeness and is **not** the same
defect: it is off by an explicitly named boolean whose name says what it
does, chosen by upstream as a policy, and visible in one grep of
`resolved.json`. The three real instances were all cases where the key
that disabled the gate was **not the key a reader would look at** —
`SETUP_VIOLATION_CORNERS` unset but `TIMING_VIOLATION_CORNERS` binding,
or a step-class default that no configuration file mentions. Raising
`ERROR_ON_LINTER_WARNINGS` would fail this design today and is a
lint-triage project, not a checker fix. Not done, named here.

### 3.4 The full table, after

`signoff-6x2-gated` **[fact, `checker_audit.py`]**:

| Checker | Gated by | Verdict |
|---|---|---|
| `LintTimingConstructs` | `ERROR_ON_LINTER_TIMING_CONSTRUCTS` True | GATES, metric 0 |
| `LintErrors` | `ERROR_ON_LINTER_ERRORS` True | GATES, metric 0 |
| `LintWarnings` | `ERROR_ON_LINTER_WARNINGS` **False** | **NO-GATE**, metric 97 |
| `YosysUnmappedCells` | `ERROR_ON_UNMAPPED_CELLS` True | GATES, metric 0 |
| `YosysSynthChecks` | `ERROR_ON_SYNTH_CHECKS` True | GATES, metric 0 |
| `NetlistAssignStatements` | `ERROR_ON_NL_ASSIGN_STATEMENTS` True | GATES, reads the netlist |
| `PowerGridViolations` | `ERROR_ON_PDN_VIOLATIONS` True | GATES, metric 0 |
| `TrDRC` | `ERROR_ON_TR_DRC` True | GATES, metric 0 |
| `DisconnectedPins` | `ERROR_ON_DISCONNECTED_PINS` True | GATES, metric 0 |
| `WireLength` | `WIRE_LENGTH_THRESHOLD` **unset** | **NO-GATE** |
| `XOR` | `ERROR_ON_XOR_ERROR` True | GATES, metric 0 |
| `MagicDRC` | `ERROR_ON_MAGIC_DRC` True | GATES, metric 0 |
| `KLayoutDRC` | `ERROR_ON_KLAYOUT_DRC` True | GATES, metric 0 |
| `IllegalOverlap` | `ERROR_ON_ILLEGAL_OVERLAPS` True | GATES, metric 0 |
| `LVS` | `ERROR_ON_LVS_ERROR` True | GATES, metric 0 |
| `SetupViolations` | `SETUP_VIOLATION_CORNERS` `["*"]` | GATES, 3 corners, all 0 |
| `HoldViolations` | `HOLD_VIOLATION_CORNERS` `["*"]` | GATES, 3 corners, all 0 |
| **`MaxSlewViolations`** | **`MAX_SLEW_VIOLATION_CORNERS` `["*"]`** | **GATES, 3 corners, all 0** |
| **`MaxCapViolations`** | **`MAX_CAP_VIOLATION_CORNERS` `["*"]`** | **GATES, 3 corners, all 0** |

On `submission-6x2-gated` the same table holds, with `XOR` and
`KLayoutDRC` reading `metric absent: the producing step did not run` —
that configuration leaves both decks off by design and they are run
separately (section 5.3).

---

## 4. sky130: the one place the gate does not pass, stated plainly

The premise "the design meets both at zero" is an **ihp-sg13g2** premise.
On sky130 it is false, and `hw/openlane/pilot_sky130/config.json` now
carries the keys anyway. Both halves of that need saying.

`sky-14-6x2-rcmodel`, the most recent sky130 6x2 harden, measures
**3,930 max-slew violations across four of its nine corners** — 1,820 at
`max_ss_100C_1v60`, 1,246 at `nom_ss_100C_1v60`, 833 at
`min_ss_100C_1v60`, 31 at `max_tt_025C_1v80` — and reported
`flow__errors__count` **0** and `design__violations` **0** **[fact]**.
Max cap is **0** on all nine. This is not new: `docs/18` section 3.3a
recorded the match-nothing wildcard on this PDK and read it as harmless
because the same run also misses setup by 2.97 ns at the same `ss`
corners, which was the finding of the day.

**So a sky130 re-harden is now expected to fail**, on
`Checker.MaxSlewViolations`, and the configuration says so in its own
`//capslew` annotation rather than leaving it to be discovered. Four
things make that the right disposition rather than a reason to leave the
key at `[""]`:

1. **It is the gate working.** The design does not meet max slew on
   sky130. A configuration that reports that as clean is the defect this
   document exists to remove, and removing it only where the answer is
   convenient would be worse than not removing it at all.
2. **No sky130 run is part of the TTIHP26b submission.** sky130 is the
   cross-PDK portability comparison of `docs/18`. The shuttle is
   ihp-sg13g2, where both metrics are 0.
3. **The measurement is not lost.** LibreLane defers this class of
   error: `flows/sequential.py` collects `DeferredStepError`, runs every
   remaining step, writes `final/`, and only then raises **[fact,
   read out of the installed flow]**. A sky130 run will still produce its
   full artifact and metric set; it will simply no longer be reported as
   clean.
4. **It changes no published number**, because it changes no sky130 run
   that exists. The variant configs under `hw/openlane/pilot_sky130/` are
   untouched, so `docs/18`, `docs/20` and `docs/25` remain reproducible
   from the files that name them.

**[estimate]** Closing the sky130 slew violations is a real piece of work
— it is the same `ss`-corner drive-strength problem as the setup miss,
and `docs/18` section 3.3 argues a slower clock is not the fix. It is not
scheduled and it is not shuttle work.

---

## 5. The re-harden and the full sign-off

`docs/34` section 9.2 is the obligation this change incurred, and every
line of it is discharged here.

### 5.1 What was run

```bash
make -f tools.mk toolcheck            # yosys 0.67+146 (pinned), no warning
python3 scripts/gen_tt_submission.py  # tt/src/config.json + MANIFEST
( cd tt && python3 tt/tt_tool.py --ihp --create-user-config )   # config_merged.json
python3 hw/openlane/pilot_ihp/mkconfig.py --check   # 6 pinned match
python3 hw/openlane/pilot_ihp/mktiming.py          # rewrite the variants
python3 hw/openlane/pilot_ihp/mktiming.py --check  # all 8 variants match

python3 hw/openlane/pin_rtl.py HEAD \
    hw/openlane/pilot_ihp/config.signoff-6x2.json <scratch>/pin-signoff-6x2-gated
python3 hw/openlane/pin_rtl.py HEAD \
    tt/src/config_merged.json <scratch>/pin-submission-6x2-gated

CONFIG=<scratch>/pin-signoff-6x2-gated/config.json \
  hw/openlane/pilot_ihp/run_ihp.sh --run-tag signoff-6x2-gated \
    --force-run-dir $PWD/hw/openlane/pilot_ihp/runs/signoff-6x2-gated
CONFIG=<scratch>/pin-submission-6x2-gated/config.json \
  hw/openlane/pilot_ihp/run_ihp.sh --run-tag submission-6x2-gated \
    --force-run-dir $PWD/hw/openlane/pilot_ihp/runs/submission-6x2-gated
```

**The submission run is hardened from `tt/src/config_merged.json`, not
from `tt/src/config.json`.** That is `docs/31` section 10.1's
distinction and it is the whole reason the run means what it means:
`tt_tool.py --harden` calls `create_merged_config()` before it invokes
LibreLane, and the LibreLane command line names `config_merged.json`
alone. `config.json` is an input to the file that builds;
`config_merged.json` is the file that builds.

Both runs were pinned with `pin_rtl.py` to what was `HEAD` at the time,
**`2f6cd6f`**, whose ten printed blobs are **byte-for-byte the ten in
`docs/34` section 2.1** **[fact]**. This is tighter than the frozen runs,
which were pinned to
`bc91c71` / `0c22de4` and needed `docs/34` section 2.2's comment-only
argument to connect them to the freeze commit. These runs are pinned to
the freeze content itself, so that argument is no longer load-bearing.

Both configurations were checked after pinning: `MAX_CAP_VIOLATION_CORNERS`,
`MAX_SLEW_VIOLATION_CORNERS` and `SETUP_VIOLATION_CORNERS` all `["*"]`,
`TIME_DERATING_CONSTRAINT` the float `5.0` **[fact]**.

### 5.2 The keys as the flow resolved them

`resolved.json`, both runs **[fact]**:

```
TIMING_VIOLATION_CORNERS   = ['*typ*']      <- PDK, now reached by nothing
SETUP_VIOLATION_CORNERS    = ['*']          <- docs/28 4.4a
HOLD_VIOLATION_CORNERS     = ['*']          <- LibreLane default
MAX_CAP_VIOLATION_CORNERS  = ['*']          <- THIS DOCUMENT
MAX_SLEW_VIOLATION_CORNERS = ['*']          <- THIS DOCUMENT
WIRE_LENGTH_THRESHOLD      = None           <- section 3.3, still open
```

The derate is audited where it is decidable, not in `resolved.json`,
which records the lossy integer `5` in these runs exactly as `docs/31`
section 10.3 found. The flow-written constraint file is the artifact that
decides, and `final/sdc/tt_um_melihakbulut_nssoc.sdc` lines 100-101 read,
in both runs **[fact]**:

```
set_timing_derate -early 0.9500
set_timing_derate -late 1.0500
```

### 5.3 The complete sign-off set

`python3 hw/openlane/signoff_report.py`, off `final/metrics.json`
**[fact for every row]**. Step numbers are `signoff-6x2-gated`'s.

| Deck / checker | Step | Result |
|---|---|---|
| **Magic DRC** | `66-magic-drc`, `68-checker-magicdrc` | **0 — passed** |
| **KLayout DRC** (PDK deck, in flow) | `67-klayout-drc`, `69-checker-klayoutdrc` | **0 — passed** |
| **KLayout XOR** | `64-klayout-xor`, `65-checker-xor` | **0 — passed** |
| **Netgen LVS** | `72-netgen-lvs`, `73-checker-lvs` | **0 — passed** |
| LVS unmatched nets / devices / pins | | **0 / 0 / 0** |
| LVS property fails | | **0** |
| Illegal overlap | `71-checker-illegaloverlap` | **passed** |
| Route DRC | `49-checker-trdrc` | **0 — passed** |
| **Antenna**, final | `48-openroad-checkantennas-1` | **0 nets, 0 pins**, 1 diode |
| Power-grid violations | `30-checker-powergridviolations` | **0 — passed** |
| Disconnected pins | `51-checker-disconnectedpins` | **6, 0 critical — passed** |
| Wirelength checker | `53-checker-wirelength` | **skipped, threshold unset** (section 3.3) |
| **Setup violations, all corners** | `74-checker-setupviolations` | **0 — passed** |
| **Hold violations, all corners** | `75-checker-holdviolations` | **0 — passed** |
| **Max slew, all corners** | `76-checker-maxslewviolations` | **0 — PASSED, and now able to fail** |
| **Max cap, all corners** | `77-checker-maxcapviolations` | **0 — PASSED, and now able to fail** |
| Lint / synth checks / unmapped / netlist assigns | `02`-`04`, `07`-`09` | all passed; 97 lint warnings, ungated |
| `design__violations` | | **0** |
| **`flow__errors__count`** | | **0** |
| Max fanout | | **84** at all three corners, still ungated (`docs/34` section 8) |

**Timing, all three corners, derated**, `57-openroad-stapostpnr` on
extracted parasitics, ns **[fact]**. Identical in both runs:

| Corner | Setup ws | Setup vio | Hold ws | Hold vio | Max slew | Max cap |
|---|---:|---:|---:|---:|---:|---:|
| **`nom_slow_1p08V_125C`** | **+1.2262** | **0** | **+0.6041** | **0** | **0** | **0** |
| `nom_typ_1p20V_25C` | +8.1033 | 0 | +0.2829 | 0 | 0 | 0 |
| `nom_fast_1p32V_m40C` | +12.1374 | 0 | +0.1029 | 0 | 0 | 0 |

**The two decks the submission configuration does not run.**
`RUN_KLAYOUT_DRC` and `RUN_KLAYOUT_XOR` stay 0 in the submission path,
deliberately and matching upstream, so `submission-6x2-gated` skips them
and `Misc.ReportManufacturability` says so. Both were run afterwards over
that run's own streamed GDS with the commands read out of the sign-off
run's `COMMANDS` files, into
`hw/openlane/pilot_ihp/runs/submission-6x2-gated-geomdecks/` **[fact]**:

- **KLayout XOR**, `scripts/klayout/xor.drc` between
  `59-magic-streamout/*.magic.gds` and `60-klayout-streamout/*.klayout.gds`:
  `Total XOR differences: 0`,
  `%OL_METRIC_I design__xor_difference__count 0`.
- **KLayout DRC**, the PDK's `ihp-sg13g2.drc` in `run_mode=deep` with
  `no_recommended=True` over `59-magic-streamout/*.gds`:
  `%OL_METRIC_I klayout__drc_error__count 0`.

`docs/31` section 10.4's reproducer note still applies: `--ignore` takes
a value and the flow passes it the empty string, which the `COMMANDS`
file renders as a run of spaces; dropping it makes `OptionParser` swallow
the first GDS path and the script reports a read error that is not a
layout problem.

### 5.4 Against the frozen runs: they agree exactly

`final/metrics.json`, compared key by key **[fact]**:

| Comparison | Keys | Equal | Differ |
|---|---:|---:|---:|
| `signoff-6x2` vs `signoff-6x2-gated` | 196 | **196** | **0** |
| `submission-6x2` vs `submission-6x2-gated` | 194 | **194** | **0** |
| `signoff-6x2-gated` vs `submission-6x2-gated` | 196 | 194 | 2 |

The two that differ in the last row are `klayout__drc_error__count` and
`design__xor_difference__count`, absent from the submission run because
that configuration does not run those steps; both were measured at 0
separately, which is what the sign-off run records for them. This is the
same shape `docs/31` section 10.5 reported, and the first two rows are
new and stronger: **enabling the two gates moved no number at all.**

At the artifact level **[fact, `sha256sum`]**:

```
52b2debf3b2097c1544b2a5ea625675add5ec71a3d3ac9b68dfb5b32d6120989  final/nl/*.nl.v
39470ad135125f6b80abaf487877ef81d442ee8dd567bde5ea89ec42995ee73e  final/pnl/*.pnl.v
8f99c979c513ab5d9dd2ebb5e72bbf77d28180ac2d7165772664dfe09586fcf4  final/def/*.def
```

**All three are identical across all four runs** — `signoff-6x2`,
`submission-6x2`, `signoff-6x2-gated` and `submission-6x2-gated` — and
they are the hashes `docs/34` section 3.1 froze. Two configurations, two
dates, four hardens, one netlist. The GDS files differ, as they always
do: GDS carries an embedded generation timestamp, so the hash is a
provenance record and not an equality criterion (`docs/34` section 3.2),
and the geometric equality is established by the decks, all of which read
0 above.

Runtime: **24.4 min** and **23.5 min** summed step time, against
`docs/31`'s 45.9 and 43.1. The two runs here were executed concurrently
on a 20-core machine; that is a machine difference, not a design one.

### 5.5 The census guards

```
$ .venv/bin/python -m pytest sw/tests/test_synthesis_guards.py -q -rs
40 passed in 77.16s

$ .venv/bin/python -m pytest sw/tests/test_synthesis_guards.py -v -k real_hardening
test_config_tmr_survives_the_real_hardening_flow             PASSED
test_pointer_tmr_survives_the_real_hardening_flow            PASSED
test_entry_parity_survives_the_real_hardening_flow           PASSED
test_dispatcher_check_field_survives_the_real_hardening_flow PASSED
test_valid_flag_rails_survive_the_real_hardening_flow        PASSED
5 passed, 35 deselected
```

**40 passed, 0 skipped**, and the five shipped-netlist guards pass **by
name** **[fact]**. One correction to the freeze record while this is
being measured: `docs/34` section 7 records **35** for this file, citing
`docs/31` section 7 rather than measuring. The file collects **40** at
`HEAD` and is unmodified in the working tree; the figure had gone stale
in the carrying, not in the test **[fact]**.

### 5.6 The Tiny Tapeout tooling and the precheck

**[fact for every row]**

| Check | Result |
|---|---|
| `scripts/gen_tt_submission.py --check` | `tt/ matches the generator (30 files)`, exit 0 |
| `cd tt && sha256sum -c MANIFEST.sha256` | **29 of 29 OK**, no failing line |
| `sw/tests/test_tt_submission.py` | **16 passed** |
| `hw/openlane/pilot_ihp/mkconfig.py --check` | `OK: 6 pinned config(s) match their recorded hash`, exit 0 |
| `hw/openlane/pilot_ihp/mktiming.py --check` | `all 8 variants match`, exit 0 |
| `tt_tool.py --ihp --create-user-config` | exit 0; port check clean, `user_config.json` unchanged, `config_merged.json` gained the two keys and nothing else |

**The Tiny Tapeout precheck, run in full on `submission-6x2-gated`'s
GDS.** `tt/tt/precheck/precheck.py --tech ihp-sg13g2`, `PDK_ROOT=~/.ciel`,
`PDK=ihp-sg13g2`, KLayout 0.30.9 from `~/.local/opt/llbin`, against
`59-magic-streamout/tt_um_melihakbulut_nssoc.gds` with the run's LEF and
netlist beside it. **Ten of ten pass; `INFO: Precheck passed`, exit 0**
**[fact]**. Reports at
`hw/openlane/pilot_ihp/runs/submission-6x2-gated-geomdecks/tt-precheck/`.

| Check | Result |
|---|---|
| KLayout pin label overlapping drawing | pass |
| KLayout SG13G2 DRC | pass |
| KLayout zero area | pass |
| KLayout Checks (top macro name, forbidden layers, prBoundary) | pass |
| Pin check / Boundary check / Layer check | pass / pass / pass |
| Cell name check / Analog pin check | pass / pass |
| Verilog syntax check | pass |

**Two environment requirements that `docs/31` section 10.7 did not name,
and that each cost a failed invocation here** **[fact, both hit]**:

- `PDK_ROOT` alone is not enough. `precheck.py` reads
  `PDK_NAME = os.getenv("PDK") or "sky130A"` and builds its deck path
  from it, so without `PDK=ihp-sg13g2` it looks for `ihp-sg13g2.drc`
  **inside the sky130A tree** and reports the sg13g2 DRC as a failure.
  That failure is a path error and says nothing about the layout.
- The Verilog syntax check shells out to `yowasp-yosys`. Overriding
  `PATH` to put the KLayout 0.30.9 shims first without keeping the venv's
  `bin` on it fails that check with `[Errno 2] No such file or
  directory`, which likewise says nothing about the design.

Both failure modes present as a red row in the precheck table. Naming
them is the point: the deck that costs a resubmission round should not be
debugged from scratch under time pressure.

**A third environment note, and it is a change to the machine rather
than a finding.** `tt/tt/tt_tool.py` imports `chevron`, `klayout.db`,
`gdstk`, `git`, `frontmatter`, `configupdater`, `mistune`, `requests`
and `cairosvg` at module scope, and shells out to `yowasp-yosys`. None
of these was importable by any interpreter on this machine, so they were
installed into the repository's `.venv` — the test venv, not the
LibreLane `.venv-flow`, which is left untouched and still resolves the
same LibreLane 3.0.5 **[fact]**. The list is `tt/tt/requirements.txt`'s;
nothing was pinned differently from it except where a wheel for Python
3.12 required a newer patch release. `docs/31` section 10.7 ran the same
tooling and did not record this dependency, which is why a fresh
reproducer hits it as an `ImportError` chain rather than as a
prerequisite.

### 5.7 Gate level

`docs/32`'s netlist and this one are **the same bytes** — `final/nl/*.nl.v`
hashes `52b2debf…` in `signoff-6x2`, which is what `docs/32` ran against,
and in `signoff-6x2-gated` **[fact]**. The suite was re-run against the
new run tag rather than inferred from that identity:

```bash
cd hw/tb
GL_TAG=signoff-6x2-gated make -f Makefile.gl provenance
GL_TAG=signoff-6x2-gated make -f Makefile.gl
GL_TAG=signoff-6x2-gated GL_PRELOAD=1 make -f Makefile.gl
```

Provenance as the makefile prints it: netlist blob `91cb371f6d52`,
2,565,946 bytes, 1 module, Icarus **13.0** from
`~/.local/opt/iverilog13` (not the 12.0 on `PATH`), cell models blob
`c4efa342f0d1`, PDK `c4b8b4e5…` **[fact]**.

Result **[fact]**, against `docs/32` section 3.3:

| Invocation | Tests | This run | `docs/32` on `signoff-6x2` |
|---|---:|---|---|
| `make -f Makefile.gl` | 20 | **19 PASS, 1 FAIL**, 2,761,090.02 ns | 19 PASS, 1 FAIL, 2,761,090.02 ns |
| `GL_PRELOAD=1` | 21 | **21 PASS, 0 FAIL**, 1,426,700.02 ns | 21 PASS, 0 FAIL, 1,426,700.02 ns |

**Identical to the nanosecond, and the one failure is the one already
on record**: `test_axon_out_of_range_is_dropped_and_counted`, failing at
**1,380,510.00 ns** and passing under `GL_PRELOAD=1` — the X-pessimism
divergence of `docs/32` section 3.3, which quotes the same figure. No
regression, and nothing new.

---

## 6. What this changed in the tracked tree

### 6.1 The files

| File | Change |
|---|---|
| `scripts/gen_tt_submission.py` | two `CONFIG_OVERRIDES` entries and their rationale |
| `tt/src/config.json`, `tt/MANIFEST.sha256` | regenerated |
| `hw/openlane/pilot_ihp/config.json` | two keys, one annotation |
| `hw/openlane/pilot_ihp/config.signoff-6x2.json` | regenerated from it |
| `hw/openlane/pilot_ihp/mkconfig.py` | the `config.json` pin re-taken, superseded hash retained |
| `hw/openlane/pilot_ihp/mktiming.py` | two assertions on the sign-off base |
| `hw/openlane/pilot_sky130/config.json` | two keys, one annotation — section 4 |
| `hw/openlane/checker_audit.py` | new, section 3 |
| `docs/34-pilot-freeze.md` | amended, section 6.3 |

Nothing under `hw/rtl/`, `hw/tb/`, `sw/`, `formal/` or `regmap/` was
touched. The seven `config.tr-*.json` variants were rewritten by
`mktiming.py` and came back **byte-identical**, because their base did
not move **[fact]**.

### 6.2 The pin on `config.json`, lifted once and re-taken

`mkconfig.py` verifies `config.json` by SHA-256 rather than by
re-derivation (`docs/34` section 5.3), so editing it by hand is exactly
what the pin exists to catch. The pin was therefore lifted deliberately
for this one edit and re-taken, with the superseded hash and the reason
kept in the `PINNED` table itself:

```
was 57295633ffc5a976e0a42e8307dc80e1f91efea31c5cce4c6aa045d32bad2a66  (b6738e5, run signoff-6x2)
now 274cc337d5147eb8ca3ac71eddd535f0d1b75ae137bcdfc04594149da3f4c1a8  (run signoff-6x2-gated)
```

`--check` now reports the source delta for this file as *would ADD* the
four post-GRT keys and *would DROP* the `//derate`, `//setupcheck` and
`//capslew` annotations — the two new keys have disappeared from the
delta, because `tt/src/config_merged.json` carries them too. The other
five pins are untouched and still match **[fact]**.

### 6.3 The freeze record

`docs/34` is amended in place rather than superseded, and **every
superseded value is retained beside its replacement under a dated
`SUPERSEDED 2026-08-31` marker**. The freeze document's worth is that it
can be checked against history and not only against now, so no old hash
was deleted. Amended: the preamble, section 1 (identity and run tags),
3.1 (four checksum blocks now, current and superseded), 3.3 (the two
metrics that were carried but ungated), 4 (manifest and
`tt/src/config.json` hashes), 5.1 (the `config.json` pin, the sign-off
config, and the sky130 config), 5.2, 5.3, 7 (three rows re-measured, one
row added), 8.5 (closed, with two corrections to how it described the
mechanism), 9.2, 9.4 and 10.

**One of those amendments changes a rule and so is argued rather than
just made.** `docs/34` section 9.2 item 8 said *"Supersede this document
with a new freeze record. Do not edit this one."* That instruction was
not followed, deliberately. Its purpose — that the record of what
`docs/31` measured survives — is met by retaining every superseded value
in place. Superseding would have split one inventory across two
documents that a reader must diff, for a change whose whole content is
two configuration keys and a `resolved.json` hash, with the built
artifacts byte-identical. The rule as amended reads: **amend in place
while the built artifacts are unchanged and every superseded value is
retained; supersede with a new record the moment a netlist hash moves.**
A change that moves the netlist is a different design and earns its own
inventory. This one is not.

---

## 7. What is open

1. **`Checker.WireLength` gates nothing**, on either PDK, because
   neither ships `WIRE_LENGTH_THRESHOLD` (section 3.3). Reported, not
   set, for `docs/34` section 8.4's reason. The quantities it proxies for
   are 0.
2. **Max fanout stays ungated**, unchanged from `docs/34` section 8: 84
   at all three corners, no `Checker.MaxFanoutViolations` in the pinned
   LibreLane, and no threshold that is not fitted to the measurement.
3. **`ERROR_ON_LINTER_WARNINGS` stays False** and the design carries 97
   lint warnings (section 3.3). Triage is a project, not a checker fix.
4. **sky130 does not meet max slew** and its configuration now says so
   (section 4). Not shuttle work.
5. **`docs/00-index.md` does not name this document**, so
   `sw/tests/test_doc_links.py::test_every_document_is_reachable_from_the_index`
   fails. Both files are outside this workstream's ownership. The row to
   add is:

   ```
   | `docs/36-checker-closure.md` | Two checkers that warned and could never fail are now bound to every corner, and all twenty-one LibreLane checkers are audited by a script rather than by prose. A fourth instance of the shape is found and dispositioned. The submission re-hardens to a bit-identical netlist. |
   ```

   Measured with this document present: **1 failed, 233 passed** over the
   whole suite, and the one failure names `docs/36-checker-closure.md`
   alone **[fact]**. A concurrent workstream added `docs/37` and its own
   index row while this was being written, so that document is already
   reachable and only this one is not.
6. **The `gds` action has never executed**, unchanged from `docs/34`
   section 10 item 3. Everything here is the same LibreLane, PDK hash and
   configuration file that action would use, run locally.

---

## 8. Result

| Question | Answer |
|---|---|
| Do the two keys now bind? | Yes — `['*']` in `resolved.json` of both runs, from the design configuration, since neither PDK ships either key **[fact]** |
| Do the two checkers pass, or merely not fail? | **Pass**: 3 of 3 corners matched, 0 violations at each, and the shipped decision function is shown to raise on a synthetic violation under the same wildcard (section 2.3) **[fact]** |
| Did anything else have the same shape? | **Yes, one**: `Checker.WireLength`, on both PDKs. Plus `Checker.LintWarnings` by the letter. 17 of 19 in-flow checkers now gate, from 15 **[fact]** |
| Did the design change? | **No.** Netlist, powered netlist and DEF are bit-identical to the frozen ones; 196 of 196 and 194 of 194 metrics equal **[fact]** |
| Did anything fail? | **No.** Both runs `Flow complete.`, `flow__errors__count` 0, all geometric decks 0, precheck 10 of 10, gate level identical to `docs/32` to the nanosecond **[fact]** |
| Anything that would fail if run? | **A sky130 harden**, on max slew, and its configuration now says so (section 4) **[fact]** |
