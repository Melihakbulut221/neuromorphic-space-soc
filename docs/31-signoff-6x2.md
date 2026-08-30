# 31 — The geometric sign-off of the adopted configuration, and the configuration the shuttle would actually build

Status: complete. Two hardens at the 6x2 submission shape, pinned to
`bc91c71`. The adopted timing configuration passes every sign-off deck —
Magic DRC, KLayout DRC, the KLayout XOR, Netgen LVS, antenna, and setup
and hold on all three corners with a real 5 % OCV derate — and the
configuration the shuttle would actually build from **misses its slow
corner and would not say so**. Section 8 is the verdict.

This document does two things. It runs `docs/28` section 10 item 7 to
completion — the three geometric decks the adopted timing configuration
had never had read — on the **current** RTL rather than on the RTL
`docs/28` hardened, which has moved twice since. And it answers a
question `docs/28` section 10 item 2 raised and did not close: whether
any of the recovery is in the configuration the shuttle would actually
build from.

**The short version.**

- **None of the adopted settings are in the submission path.** Not one
  of the six keys — the derate fix, the setup-corner fix, and the four
  keys of `docs/28` section 6.2 — appears in `tt/src/config.json`,
  `tt/src/config_merged.json` or `tt/src/user_config.json`. Section 2.1.
- **Hardened, the submission path misses its slow corner.** Same RTL,
  same shape, same pin commit, run from `tt/src/`'s own configuration:
  **-0.7696 ns and 18 violating endpoints as the flow reports it,
  -1.8321 ns derated** — and the flow would have called that run clean,
  because with `SETUP_VIOLATION_CORNERS` unset the setup checker looks
  at the typical corner, which passes at +6.8753. **The adopted
  configuration is worth 3.0588 ns on this RTL, and the shuttle would
  take none of it.** Section 2.2.
- **The configuration signs off clean on the current RTL under the
  stricter definition.** Slow-corner setup **+1.2262 ns with a real 5 %
  OCV derate applied inside the flow**, 0 setup and 0 hold violations on
  all three corners with the setup checker pointed at all three.
  Section 4.
- **Applying the derate inside the loop bought margin rather than
  costing it.** The post-GRT resizer entered at -1.973 ns instead of
  -0.956 ns, worked 46 endpoints instead of 39, resized 49 gates instead
  of 11 — and the run finishes **+0.4752 ns better than `tr-margin` did
  derated**, while carrying 19 more flip-flops. Section 5.
- **Every geometric deck is zero, on current RTL.** Magic DRC 0,
  KLayout DRC 0, **KLayout XOR 0 — never run in this repository
  before** — Netgen LVS 0 on all four unmatched counters, antenna 0,
  route DRC 0, `flow__errors__count` 0. Section 4.2.
- **All five shipped-netlist guards pass by name, none skipping.**
  35 passed, 0 skipped, against 33 passed and 2 skipped before this
  run. Section 7.
- **The tile budget is comfortable**: 48.75 % utilization against a
  70 % criterion at twelve tiles, 201,400 um2 of core unoccupied.
  Section 6.
- **It is not submittable as it stands.** The design closes; the
  submission does not carry what makes it close. Section 8.

---

## 1. What was run, and against which sources

### 1.1 Toolchain

```
$ make -f tools.mk toolcheck
OSS_CAD_SUITE = /home/hasanmelih/Downloads/oss-cad-suite-linux-x64-20260804/oss-cad-suite
sby       = .../bin/sby
yosys     = .../bin/yosys
iverilog  = .../bin/iverilog
yosys version = 0.67+146 (pinned 0.67+146)
```

No mismatch warning **[fact]**.

| Component | Version | Where it is pinned |
|---|---|---|
| LibreLane | 3.0.5 | `~/Documents/caravel-lif-crossbar/.venv-flow` |
| Yosys (in-flow) | 0.67 | LibreLane wheel (`pyosys`) |
| Yosys (guards, `tools.mk`) | 0.67+146 | `OSS_CAD_SUITE` pin |
| ihp-sg13g2 PDK | `c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c` | LibreLane `pdk_hashes.yaml`, asserted by `run_ihp.sh` |
| Magic | 8.3.678 | `~/.local/opt/magic-8.3.678` |
| OpenSTA (the derate and Fmax probes) | the `~/.local/opt/llbin/sta` shim | same OpenROAD build the flow uses |

**[fact]**, read out of `hw/openlane/pilot_ihp/runs/signoff-6x2/resolved.json`
and `librelane --version`.

### 1.2 Provenance: the blob list

Both runs are pinned with `hw/openlane/pin_rtl.py` against commit
**`bc91c71`** (HEAD when this work started, tree clean) and read a
disposable snapshot by absolute path, not `hw/rtl`:

```
$ python3 hw/openlane/pin_rtl.py bc91c71 \
      hw/openlane/pilot_ihp/config.signoff-6x2.json <scratch>/pin-signoff-6x2
pinned to bc91c71 (bc91c71a1d73)
  ba4e5b0d2e0c934a7ebcd575866fb0eb73d722e4  hw/rtl/aer_fifo.v
  72f4f0af662b7bb07fdf43bf244e622d03db5e0d  hw/rtl/lif_core.v
  e6c1e646643840e2a553924b56dfab64022e5c39  hw/rtl/npu_regbank.v
  9aaaa394e7a6ef855f5584fb85d53e688ac3e0b5  hw/rtl/npu_regs.vh
  873b57d3572bf821bf71ea30dd6e18a16b30a0da  hw/rtl/pilot_top.v
  89e62789ad016c7cb51ad69247f6066335074f8c  hw/rtl/scrub.v
  f7c7ec187a0df4eb09a8405dcda285de0fc2e44e  hw/rtl/secded_dec.v
  b5710b8a679c3e378e74953b621b99f0d8dc3014  hw/rtl/secded_enc.v
  62b5f4d2a1eae095d9d4a8634ede55237e2c924d  hw/rtl/tmr_voter.v
  e294afcf03e1947906086beeba2fd0c40b29441d  hw/rtl/tt_um_melihakbulut_nssoc.v
```

**[fact]**, and the same ten blobs for `subpath-6x2`.

**The RTL has moved twice since `docs/28`.** Against `c52518e`, which
`docs/28` hardened, two blobs differ:

| File | `c52518e` | `bc91c71` | What moved |
|---|---|---|---|
| `hw/rtl/aer_fifo.v` | `70045ec25774` | `ba4e5b0d2e0c` | `docs/29`: queue entry parity (`aer_par_bank`) |
| `hw/rtl/pilot_top.v` | `3d9f84047748` | `873b57d3572b` | `docs/30`: `par_err` counter, dispatcher check field (`pilot_chk_bank`) |

**[fact, `git rev-parse <commit>:hw/rtl/<file>`]**. The other eight blobs
are byte-identical. So every number in `docs/28` section 6.3 is a number
about RTL that no longer exists, and re-reading its run directory would
not have closed the gap even though the decks in it did pass — section
5.1 quotes them for comparison and does not adopt them.

**The seven files the run synthesized** are the `VERILOG_FILES` list:
`tt_um_melihakbulut_nssoc.v`, `pilot_top.v`, `lif_core.v`, `aer_fifo.v`,
`tmr_voter.v`, `secded_enc.v`, `secded_dec.v`, plus `npu_regs.vh` as an
include. `npu_regbank.v` and `scrub.v` are materialised by the pin
script — it copies the whole of `hw/rtl` — and are not in the file list,
so they are not synthesized **[fact, `06-yosys-synthesis/config.json`]**.
`tt/src/*.v` carries byte-identical blobs to `hw/rtl/*.v` for all seven
sources and the include **[fact, `git hash-object` on both trees]**, so
the run and the submission tree agree on the RTL. They do not agree on
the configuration, which is section 2.

### 1.3 The two runs

| Tag | Configuration | Purpose | To |
|---|---|---|---|
| **`signoff-6x2`** | `config.signoff-6x2.json` | the adopted configuration, full sign-off | end of flow |
| `subpath-6x2` | `config.6x2.json` | **what the submission path builds**: no derate, no setup-corner fix, no post-GRT repair | `OpenROAD.STAPostPNR` |

Both at the 6x2 submission shape, `CLOCK_PERIOD: 20`,
`SYNTH_HIERARCHY_MODE: deferred_flatten`,
`DIE_AREA 0 0 1289.28 313.74`, `FP_DEF_TEMPLATE
tt_block_6x2_pgvdd.def`, pinned to `bc91c71`.

`config.signoff-6x2.json` is generated by
`hw/openlane/pilot_ihp/mktiming.py`, which `--check` re-derives and
diffs, and it is derived from **`config.json` and not from
`config.6x2.json`**. That distinction is the whole reason the run means
what it means, and section 3 is why.

Exact commands:

```bash
make -f tools.mk toolcheck
python3 hw/openlane/pilot_ihp/mktiming.py            # write the variants
python3 hw/openlane/pilot_ihp/mktiming.py --check    # confirm no drift

python3 hw/openlane/pin_rtl.py bc91c71 \
    hw/openlane/pilot_ihp/config.signoff-6x2.json <scratch>/pin-signoff-6x2

mkdir -p hw/openlane/pilot_ihp/runs/signoff-6x2
CONFIG=<scratch>/pin-signoff-6x2/config.json \
  hw/openlane/pilot_ihp/run_ihp.sh \
    --run-tag signoff-6x2 \
    --force-run-dir $PWD/hw/openlane/pilot_ihp/runs/signoff-6x2

python3 hw/openlane/signoff_report.py hw/openlane/pilot_ihp/runs/signoff-6x2
```

---

## 2. The recovery settings are not in the submission path

This is the finding that outranks every number in this document, so it
is stated before them.

### 2.1 The audit

Six keys are at issue: the two flow-defect fixes of `docs/28` section
4.4, and the four keys of the adopted configuration in `docs/28` section
6.2. Searched across the submission tree and this repository's own
configs **[fact, textual search of each file]**:

| Key | `tt/src/config.json` | `tt/src/config_merged.json` | `tt/src/user_config.json` | `pilot_ihp/config.json` | `config.tr-margin.json` | `config.signoff-6x2.json` |
|---|---|---|---|---|---|---|
| `TIME_DERATING_CONSTRAINT` (float) | **absent** | **absent** | **absent** | present | **absent** | present |
| `SETUP_VIOLATION_CORNERS` | **absent** | **absent** | **absent** | present | present | present |
| `PNR_CORNERS` | **absent** | **absent** | **absent** | **absent** | present | present |
| `RUN_POST_GRT_DESIGN_REPAIR` | **absent** | **absent** | **absent** | **absent** | present | present |
| `RUN_POST_GRT_RESIZER_TIMING` | **absent** | **absent** | **absent** | **absent** | present | present |
| `GRT_RESIZER_SETUP_SLACK_MARGIN` | **absent** | **absent** | **absent** | **absent** | present | present |

**Not one of the six keys is in the submission path.** `docs/28` section
10 item 2 recorded this for `SETUP_VIOLATION_CORNERS` alone; it is true
of all six.

**Said plainly: if the shuttle built from `tt/src/` as it stands today,
it would build without any of the margin the recovery bought, without
the derate, and with the setup checker gating the typical corner only.**
The GDS action reads `tt/src/config.json`; nothing in `hw/openlane/`
reaches it.

### 2.2 What that costs, measured rather than argued

`subpath-6x2` hardens the **same RTL, same shape, same pin commit**
from `config.6x2.json`, which is `mkconfig.py`'s mechanical derivation
of `tt/src/config_merged.json` and carries none of the six keys
**[fact, `resolved.json`: `SETUP_VIOLATION_CORNERS` unset,
`PNR_CORNERS` unset, `RUN_POST_GRT_RESIZER_TIMING: False`, and
`_env.tcl` `set ::env(TIME_DERATING_CONSTRAINT) 5`]**. It is the
submission path, run.

`55-openroad-stapostpnr`, extracted parasitics **[fact]**:

| Corner | `subpath-6x2` setup ws | Setup violations | Setup TNS | `signoff-6x2` setup ws |
|---|---:|---:|---:|---:|
| **`nom_slow_1p08V_125C`** | **-0.7696** | **18** | **-8.9932** | **+1.2262** |
| `nom_typ_1p20V_25C` | +6.8753 | 0 | 0.0000 | +8.1033 |
| `nom_fast_1p32V_m40C` | +11.4244 | 0 | 0.0000 | +12.1374 |

Hold closes on both runs at every corner, 0 violations
(`subpath-6x2` slow hold +0.6148) **[fact]**.

**The submission path does not close 50 MHz on the current RTL.** It
misses the slow corner by **-0.7696 ns as the flow reports it**, on
**18 violating endpoints**, and by **-1.8321 ns** with the 5 % OCV
derate applied — measured by standalone OpenSTA on the run's own
netlist, SPEF and SDC, with the same probe that reproduces
`tt/runs/wave6-6x2`'s figures to seventeen digits **[fact:
un-derated `-0.769622609648127`, derated `-1.832068770768804`]**.

**And nothing in that run would have said so.** With
`SETUP_VIOLATION_CORNERS` unset, `Checker.SetupViolations` resolves to
the PDK's `TIMING_VIOLATION_CORNERS: ["*typ*"]` and examines the typical
corner, which is clean at +6.8753. `docs/29` section 4.1 already
demonstrated this once — a run that reached `Magic.DRC` with
`flow__errors__count` clean while carrying 14 slow-corner setup
violations. On current RTL the figure is **18** **[fact, the
violation count above; that the checker would pass is an
`[estimate]`, since this run was stopped at `OpenROAD.STAPostPNR`
before the checkers, but it follows from the resolved corner list and
from `docs/29`'s measurement of the same configuration]**.

**So the adopted configuration is worth 3.0588 ns on this RTL**
(+1.2262 against -1.8321, both derated), and the shuttle as configured
today would take none of it.

### 2.3 Two further things the table shows

**`config.tr-margin.json` — the file `docs/28` names as carrying the
adopted configuration — does not carry the derate fix.** It was
generated by `mktiming.py` from `config.6x2.json` before commit
`4dabcbf` added `TIME_DERATING_CONSTRAINT: 5.0` to `config.json`, and
`config.6x2.json` was never regenerated. Re-running `tr-margin` today
would still harden with the derate silently integer-divided to zero.
The adopted configuration is therefore **split across two files that
were never merged**, and `config.signoff-6x2.json` is the first file in
this repository that holds all six keys at once. `mktiming.py` now
asserts both fixes are present in its base and exits rather than
generating a variant without them.

**`mkconfig.py --check` reports `config.json` as drifted** **[fact,
exit 1, `DRIFT: hw/openlane/pilot_ihp/config.json`]**. The two fixes
were hand-added to a file whose header says
`GENERATED by mkconfig.py ... Do not hand-edit; re-run the script.`
Anyone re-running `mkconfig.py` regenerates it from
`tt/src/config_merged.json`, which carries neither key, and silently
removes both fixes. That is not a hypothetical: it is the same class of
defect as the two `docs/28` reported, a correct setting that a tool
quietly reverts.

### 2.4 Why `tt/src/config.json` was not edited here

The commissioning of this work permitted editing `tt/src/config.json`
if the settings were found missing. They are missing, and the edit was
still not made, because **it does not fix the submission path and the
repository rejects it.** Measured:

- `tt/src/config.json` is **generated**. `scripts/gen_tt_submission.py`
  builds it from a verbatim upstream template plus a `CONFIG_OVERRIDES`
  dictionary that currently holds one entry,
  `SYNTH_HIERARCHY_MODE: deferred_flatten` **[fact, lines 233-235 and
  1632-1644]**.
- With the two fixes hand-added to `tt/src/config.json`,
  `python3 scripts/gen_tt_submission.py --check` reports
  **`differs from the generator: tt/src/config.json`** and instructs the
  reader to run the generator, which reverts the edit **[fact, measured
  and then reverted; the tree is unchanged]**.
- `sw/tests/test_tt_submission.py` gates the same property through
  `tt/MANIFEST.sha256` and `test_tree_matches_the_generator`. It passes
  today, 16 passed **[fact]**, and a hand edit fails it.

So a hand edit produces a submission config that is correct, fails the
repository's own drift gate, and is undone by the next generator run.
**The change that actually closes this is one entry in
`CONFIG_OVERRIDES` in `scripts/gen_tt_submission.py` followed by
`python3 scripts/gen_tt_submission.py`**, and `scripts/` is not this
workstream's file. Section 8 states it as the blocking item.

---

## 3. The configuration that was hardened

### 3.1 The six keys

```json
"TIME_DERATING_CONSTRAINT": 5.0,
"SETUP_VIOLATION_CORNERS": ["*"],
"PNR_CORNERS": ["nom_typ_1p20V_25C", "nom_slow_1p08V_125C"],
"RUN_POST_GRT_DESIGN_REPAIR": 1,
"RUN_POST_GRT_RESIZER_TIMING": 1,
"GRT_RESIZER_SETUP_SLACK_MARGIN": 0.5
```

plus `RUN_KLAYOUT_DRC: 1` and `RUN_KLAYOUT_XOR: 1`, which are read-only
decks over the streamed GDS and move no layout bit. Everything else,
including `CLOCK_PERIOD`, `PL_TARGET_DENSITY_PCT`, `DIE_AREA` and
`SYNTH_HIERARCHY_MODE`, is the submission's own value.

**`PL_TIMING_DRIVEN` is deliberately not set.** `docs/28` section 5.5
measures it at +0.5856 ns with negative area cost, and section 10 item 9
names its composition with the post-GRT repair as the one experiment
`docs/28` did not run. It is not adopted here for the same reason
`docs/28` did not adopt it: this document does not ship a knob it has
not hardened, and the run below closes without it. Confirmed off in the
run: `PL_TIMING_DRIVEN: False` **[fact, `resolved.json`]**.

Nothing was tuned. The four timing keys are `docs/28` section 6.2
verbatim, and no knob was moved after a number was read.

### 3.2 The derate really is applied, and `resolved.json` cannot tell you

`docs/28` section 4.4(b) established that the PDK ships
`TIME_DERATING_CONSTRAINT` as the integer `5` and that LibreLane's
`base.sdc` consumes it with Tcl integer division, so `expr 5 / 100` is
`0` and the derate factors are `1.0` and `1.0` while the log prints
"Setting timing derate to: 5%". Writing it as a float makes the division
real.

**The proof, at every level the value passes through [fact]:**

| Evidence | `tr-margin` (docs/28) | **`signoff-6x2`** |
|---|---|---|
| `resolved.json` | `"TIME_DERATING_CONSTRAINT": 5` | `"TIME_DERATING_CONSTRAINT": 5` |
| Step `_env.tcl` | `set ::env(TIME_DERATING_CONSTRAINT) 5` | **`... 5.0`** |
| Flow log line | `Setting timing derate to: 5%` | **`... 5.0%`** |
| **Flow-written SDC** | **no `set_timing_derate` line at all** | **`set_timing_derate -early 0.9500` / `-late 1.0500`** |
| `tclsh`: `expr 1+[expr $v / 100]` | `1` | **`1.05`** |

The written SDC is the artifact that decides, and it carries the derate
in `signoff-6x2` and does not exist in `tr-margin`.

**`resolved.json` is lossy for this key and must not be used to audit
it.** It records `5` in both runs — the float is flattened on
serialization — while `_env.tcl`, which is what Tcl actually reads,
records `5` and `5.0` respectively. Anyone verifying whether a run in
this repository derated must read `_env.tcl` or the written SDC, never
`resolved.json`. That is a third instance of the shape `docs/23` section
3.2 and `docs/28` section 4.4(a) name: a record that looks like evidence
and is not.

### 3.3 The setup checker is pointed at all three corners

`SETUP_VIOLATION_CORNERS: ["*"]` against the PDK's
`TIMING_VIOLATION_CORNERS: ["*typ*"]` **[fact, `resolved.json`]**. So a
negative slow corner fails this run, where in every run before `docs/28`
it would have been invisible. Section 4's zero setup-violation count
therefore means something it did not mean in `docs/15` through
`docs/27`.

---

## 4. Sign-off

`hw/openlane/pilot_ihp/runs/signoff-6x2`, ihp-sg13g2, 6x2, pinned to
`bc91c71`, LibreLane 3.0.5.

### 4.1 Timing, all three corners, derated

`57-openroad-stapostpnr`, post-PnR STA on extracted parasitics, **with
the 5 % OCV derate applied by the flow** (section 3.2), all figures in
ns **[fact]**:

| Corner | Setup ws | Setup vio | Hold ws | Hold vio | Max slew vio | Max cap vio |
|---|---:|---:|---:|---:|---:|---:|
| `nom_slow_1p08V_125C` | **+1.2262** | **0** | **+0.6041** | **0** | 0 | 0 |
| `nom_typ_1p20V_25C` | +8.1033 | 0 | +0.2829 | 0 | 0 | 0 |
| `nom_fast_1p32V_m40C` | +12.1374 | 0 | +0.1029 | 0 | 0 | 0 |

Corroborated three ways rather than from the worst-slack metric alone
**[fact]**: `summary.rpt` reports setup TNS and hold TNS **0.0000 at
every corner** and violation counts 0; `design__violations` is 0 and
`flow__errors__count` is 0; and `Checker.SetupViolations` — pointed at
`["*"]`, not at typical — passed.

**Fmax, derated.** A period sweep on the shipped netlist and parasitics
is exactly linear: 19.0 / 19.5 / 20.0 / 20.5 / 21.0 ns give
+0.2262 / +0.7262 / +1.2262 / +1.7262 / +2.2262 ns, i.e. 1 ns of period
buys 1.0000 ns of slack **[fact, standalone OpenSTA]**. So the longest
path is **18.7738 ns** and Fmax is **53.27 MHz**, derated. The design
runs at 50 MHz with **+1.2262 ns, 6.13 % of the cycle, of real OCV
margin.**

### 4.2 The complete sign-off set

Read with `python3 hw/openlane/signoff_report.py
hw/openlane/pilot_ihp/runs/signoff-6x2` off `final/metrics.json`, so
`tr-margin` and this run are read the same way **[fact]**. Step numbers
are `signoff-6x2`'s; `tr-margin` numbers its steps two lower, having no
XOR pair:

| Deck / checker | Step | `tr-margin` (`docs/28`) | **`signoff-6x2`** |
|---|---|---|---|
| **Magic DRC** | `67-magic-drc`, `69-checker-magicdrc` | 0 | **0 — passed** |
| **KLayout DRC** | `68-klayout-drc`, `70-checker-klayoutdrc` | 0 | **0 — passed** |
| **KLayout XOR** | `65-klayout-xor`, `66-checker-xor` | **not run** | **0 — passed** |
| **Netgen LVS** | `73-netgen-lvs`, `74-checker-lvs` | 0 | **0 — passed** |
| LVS unmatched nets | | 0 | **0** |
| LVS unmatched devices | | 0 | **0** |
| LVS unmatched pins | | 0 | **0** |
| LVS property fails | | 0 | **0** |
| Illegal overlap | `72-checker-illegaloverlap` | pass | **passed** |
| Route DRC | `49-checker-trdrc` | 0 | **0 — passed** |
| **Antenna**, final | `48-openroad-checkantennas-1` | 0 nets | **0 nets, 0 pins** |
| Antenna diodes inserted | | 8 | **1** |
| Power-grid violations | `30-checker-powergridviolations` | 0 | **0 — passed** |
| Disconnected pins | `51-checker-disconnectedpins` | 6 | **6, 0 critical — passed** |
| Wirelength checker | `53-checker-wirelength` | pass | **passed** |
| **Setup violations, all corners** | `75-checker-setupviolations` | 0 | **0 — passed** |
| **Hold violations, all corners** | `76-checker-holdviolations` | 0 | **0 — passed** |
| Max slew / max cap, all corners | `77`, `78` | 0 / 0 | **0 / 0 — passed** |
| Lint / synth checks / unmapped cells / netlist assigns | `02`-`04`, `07`-`09` | pass | **all passed** |
| `design__violations` | | 0 | **0** |
| **`flow__errors__count`** | | 0 | **0** |

**The three geometric decks that `docs/28` section 10 item 7 left
unread are read, and all three are zero.** The KLayout XOR is new: it
has never been run in this repository before, and it reports **0
differing geometry between the Magic and KLayout GDS streams**, which
is the deck the Tiny Tapeout precheck runs and the one whose failure
would have cost a resubmission round.

**The two `[fact]`s that need a caveat.**

**The 6 disconnected pins are deliberate**, not a defect: `ena`,
`ui_in[7]` and `uio_in[4]` through `uio_in[7]`, all unused inputs of
the Tiny Tapeout wrapper. `design__critical_disconnected_pin__count`
is **0** and `Checker.DisconnectedPins` passed **[fact,
`50-odb-reportdisconnectedpins/full_disconnected_pins_table.txt`]**.

**84 max-fanout violations are reported at the slow corner, and no
checker in this flow gates them.** The flow has
`Checker.MaxSlewViolations` and `Checker.MaxCapViolations` and no
max-fanout equivalent **[fact, the step list]**. The figure is **84 on
`signoff-6x2`, 84 on `tr-margin` and 84 on `subpath-6x2`** — stable
across configurations and RTL waves, so it is not a regression, but it
is the same shape of gap `docs/23` section 3.2 and `docs/28` section
4.4(a) name and it is recorded here rather than left in a metrics file.
It is item 3 of section 8.

Runtime: **45.9 min of summed step time over 78 steps**, against
`tr-margin`'s 136.2 min. Magic DRC is **35 min 30 s** of it and detailed
routing 4 min 24 s **[fact, `runtime.txt` files]**. The difference
against `tr-margin` is machine contention rather than the design:
`docs/28`'s five hardens shared twenty cores and its Magic DRC alone
took 1 h 43 m.

**One thing about this run directory a reproducer needs to know.** The
flow was executed in three passes. Two were terminated by process-group
signals from the harness driving them — not by the flow, which logged no
error — and each was resumed with `--from`, at `Magic.WriteLEF` and then
at `Magic.DRC`. The consequence visible on disk is a **duplicate
`62-magic-writelef` orphaned beside the `63-magic-writelef` that the
resumed flow actually used**. The step chain is nonetheless coherent:
both `64-odb-checkdesignantennaproperties` and `67-magic-drc` read their
DEF from `55-odb-cellfrequencytables`, the single routed database, and
every deck above ran against it **[fact, `state_in.json` of each]**. An
uninterrupted run produces the same numbers with one fewer directory;
nothing in the sign-off set depends on the interruption.

### 4.3 The redundancy census on the shipped netlist

`RSZ_DONT_TOUCH_RX` is `$^` and matches nothing **[fact,
`resolved.json`]**, so the post-GRT resizer was free to resize, clone or
unbuffer a rail or a replica. It resized 49 combinational gates and
inserted 20 buffers. Counted by hand on
`54-openroad-fillinsertion/tt_um_melihakbulut_nssoc.nl.v`, the netlist
`57-openroad-stapostpnr` signed off **[fact]**:

| Structure | Expected | Found | |
|---|---|---|---|
| Total mapped flip-flops | 1,296 | **1,296** | matches `docs/30` section 4.3 exactly |
| Configuration TMR, `u_cfg_a/b/c` | 55 each, 3 banks | **55 / 55 / 55** | pass |
| AER pointer TMR | 3 each, 12 banks | **3 in all twelve** | pass |
| Queue entry parity, `u_evq_*.u_par` | 4 each, 2 banks | **4 / 4** | pass |
| Dispatcher check field, `u_disp_chk` | 2 | **2** | pass |
| Valid-flag rails | `u_ohv_a/b` 1, `u_rdv_a/b` 2, `u_op_a/b` 1 | **1 / 1 / 2 / 2 / 1 / 1** | pass |

**No sequential cell was touched.** The same census on
`subpath-6x2`'s final netlist gives the same twenty-six numbers
**[fact]**, so the structures survive both configurations.

---

## 5. What the numbers mean

### 5.1 The margin is better than the adopted configuration's own, on more RTL

Slow-corner setup slack at 20 ns, slow corner, **all rows derated so
they are comparable**:

| Run | RTL | Configuration | Slow setup, derated |
|---|---|---|---:|
| `tt/runs/wave6-6x2` (`docs/27`) | `c52518e` | submission, pre-recovery | **-0.6681** |
| **`runs/subpath-6x2`** | **`bc91c71`** | **the submission path today** | **-1.8321** |
| `runs/tr-margin` (`docs/28` adopted) | `c52518e` | tr-margin, derate **not** applied in-flow | **+0.7510** |
| `trbest_parity` (`docs/29`) | `634ca3e` | `tr-best` (`DELAY 0`) | +0.4306 |
| `w8_disp_chk2` (`docs/30`) | wave 8 | `tr-best` (`DELAY 0`) | +1.0423 |
| **`runs/signoff-6x2`** | **`bc91c71`** | **adopted + derate in-flow** | **+1.2262** |

**[fact]**, measured in this workstream, for the `wave6-6x2`,
`subpath-6x2`, `tr-margin` and `signoff-6x2` rows. The `trbest_parity`
and `w8_disp_chk2` rows are **quoted** from `docs/29` section 4.2 and
`docs/30` section 6.2; their run trees were placed outside the
repository and are no longer on disk, which is independently visible in
that the provenance-gated guards skip without them **[fact]**.

Two of the four measured rows are reproductions rather than new
readings, and they are what validate the probe before it is used on
anything new **[fact, standalone OpenSTA on each run's own netlist,
SPEF and SDC]**:

- `wave6-6x2`: un-derated **`0.32288661547280123`**, reproducing that
  run's own `timing__setup__ws__corner` metric to all 17 digits, and
  derated **`-0.6681198006172618`**, reproducing `docs/28` section 7.
- `tr-margin`: derated **`0.7509779677344754`**, reproducing `docs/28`
  section 7's +0.7510.

**The adopted configuration, with the derate live inside the flow,
signs off +0.4752 ns better than it did with the derate absent — while
carrying 19 more flip-flops from two RTL waves.**

### 5.2 Why applying the derate bought margin instead of costing it

The derate is not only a reporting change. `PNR_CORNERS` puts the slow
corner inside the PnR loop, so once the derate is real the post-GRT
resizer optimises against a corner that is 1 ns harsher, and it responds
by working proportionally harder. Post-GRT resizer, same step, same
knob, **[fact,
`44-openroad-resizertimingpostgrt/*.log` of each run]**:

| | `tr-margin` (no derate) | **`signoff-6x2`** (derated) |
|---|---:|---:|
| Endpoints found with setup violations | 39 | **46** |
| Slack entering | -0.956 | **-1.973** |
| Slack leaving | +0.578 | **+0.519** |
| Gates resized | 11 | **49** |
| Buffers inserted | 7 | **20** |
| Pin swaps | 6 | **13** |
| Area growth reported by the resizer | +0.1 % | **+0.2 %** |

The resizer entered 1.017 ns worse — almost exactly the 0.9910 ns
`docs/28` section 4.4(b) measured the derate to be worth — and still
left at +0.519 ns against its 0.5 ns target, having spent 0.2 % of area
instead of 0.1 %. **The derate was not a tax on the result; it was
better information for the only step in this flow that repairs setup.**
That is a `[fact]` for the two columns and an `[estimate]` for the
attribution, since the RTL also moved between the two runs.

**The critical cone has swapped back.** `docs/28` section 3.1's central
finding was a cone swap: `docs/23`'s critical path started at
`u_pilot.u_lif.jj[1]`, and wave 6's started at
`u_pilot.u_lif.ev_axon_r[1]`. On this run the worst path launches from
**`u_pilot.u_lif.jj[0]`** again, and its endpoint,
`u_pilot.u_lif._5559_`, is exactly the endpoint the post-GRT resizer
reported as its worst throughout its 120 iterations **[fact,
`max.rpt` and `44-openroad-resizertimingpostgrt/*.log`]**. Both cones
are the same single-cycle neuron update `docs/28` section 3.2 names, so
this is a re-ordering inside one loop rather than a new critical
structure, and it is a further reason not to cost a wave by its
flip-flop count.

Between launch and capture the path holds **62 cells, 58 of them at
minimum drive, including 9 `sg13g2_buf_1` repair buffers** **[fact]**.
`docs/28` section 3.4's observation that this flow does not size cells
on the critical path is therefore **only partly closed**: the post-GRT
resizer sized 49 gates across 46 endpoints, but the path that ends up
worst afterwards is still a minimum-drive path. That is what a resizer
that has met its margin target looks like, and it is the honest reading
of the +0.519 ns plateau in section 5.2's table.

`docs/28` section 5.1's stage picture reproduces on this run, derated
**[fact, slow-corner setup at each stage]**:

| Point in the flow | Parasitics | Slow setup |
|---|---|---:|
| `12-openroad-staprepnr` | wireload estimate | -2.1839 |
| `31-openroad-stamidpnr` | post-global-placement | -10.7197 |
| `36-openroad-stamidpnr-1` | post-CTS estimate | **+2.2061** |
| `44-…-resizertimingpostgrt`, entering | post-GRT estimate | **-1.9730** |
| `44-…-resizertimingpostgrt`, leaving | post-GRT estimate | +0.5190 |
| `45-openroad-stamidpnr-3` | post-GRT estimate | +0.4067 |
| `57-openroad-stapostpnr` | **extracted (RCX)** | **+1.2262** |

Both of `docs/28` section 5.1's findings hold under the derate. The
post-CTS estimate is **4.18 ns optimistic** against the post-GRT one,
which is why the post-CTS resizer still reports
**`RSZ-0098 No setup violations found`** even now **[fact,
`37-openroad-resizertimingpostcts`]** — it is asked at the one point
where the design looks clear. And the post-GRT estimate is again
**pessimistic against extraction, by 0.82 ns**, the safe direction.

---

## 6. Tile budget

Twelve tiles at the 6x2 shape, `DIE_AREA 0 0 1289.28 313.74`
**[fact, `resolved.json`]**:

| | `tr-margin` (`docs/28`) | **`signoff-6x2`** | Move |
|---|---:|---:|---:|
| Die area, um2 | 404,499 | **404,499** | — |
| Core area, um2 | 392,988 | **392,988** | — |
| Placed cell area excl. fill, um2 | 185,785 | **191,588** | +5,803, +3.12 % |
| **Utilization** | 47.2751 % | **48.7516 %** | +1.48 pts |
| Cells excl. fill | 12,246 | **12,546** | +300 |
| Sequential cells | 1,277 | **1,296** | **+19** |
| Timing-repair buffers | 2,386 | 2,532 | +146 |
| of which setup buffers | 7 | **20** | +13 |
| Routed wirelength, um | 466,001 | **472,381** | +6,380, +1.37 % |
| Synthesis cells | 9,686 | **9,834** | +148 |
| Synthesis cell area, um2 | 152,099.79 | **155,462.93** | +3,363.14, +2.21 % |

**[fact]**.

**Against the 70 % planning criterion `docs/15`, `docs/22` and `docs/23`
use: 48.75 % used, 21.25 points spare.** In absolute terms
**201,400 um2 of the 392,988 um2 core is unoccupied**, and 83,504 um2 of
it is still below the criterion. The +19 flip-flops are exactly the two
RTL waves: 8 for the queue entry parity (`docs/29`), 2 for the
dispatcher check field and 9 for the `CNT_EVQ_PAR` counter and its edge
register (`docs/30`).

**Timing is still the binding budget, and it is one block's.** The
per-cone decomposition of `docs/28` section 3.1, re-run on this run's
1,664 sign-off paths **[fact,
`57-openroad-stapostpnr/nom_slow_1p08V_125C/max.rpt`]**:

The eight worst startpoint cones, by best slack of any path launching
from each:

| Rank | Startpoint | Worst slack, derated |
|---:|---|---:|
| 1 | `u_pilot.u_lif._5474_` | **+1.2262** |
| 2 | `u_pilot.u_lif._5478_` | +1.7509 |
| 3 | `u_pilot.u_lif._5475_` | +7.0837 |
| 4 | `u_pilot.u_lif._5460_` | +7.8998 |
| 5 | `u_pilot._5248_` | **+8.8980** |
| 6 | `u_pilot._5352_` | +9.2848 |
| 7 | `u_pilot._5367_` | +10.6283 |
| 8 | `u_pilot.u_evq_in.u_rptr_c._15_` | +10.8586 |

**The four tightest cones are all inside `u_pilot.u_lif`, and the first
cone outside it has +8.8980 ns — 44.5 % of the cycle — of slack.**
`docs/28` section 8.1's conclusion is unchanged by two RTL waves and by
the derate: only `lif_core` is tight. Neither the queue parity of
`docs/29` nor the dispatcher check field of `docs/30` appears in this
list; the first queue structure to appear is a pointer TMR replica at
rank 8, with **9.6 ns more slack than the critical path**.

**The tile budget is not the constraint and has not been close to it
since the move to 6x2.** `docs/28` section 5.3's rule still stands and
is the reason none of that spare area was spent: measured there, buying
timing by growing the netlist loses 4.36 ns, because this design is
wire-dominated. The +5,803 um2 here is the cost of RTL that had to
exist, plus 0.2 % of targeted resizing, not an attempt to trade area
for delay.

---

## 7. The census guards

Section 4.3 counts the netlist by hand. `sw/tests/test_synthesis_guards.py`
counts it automatically, and its five shipped-netlist guards are
provenance-gated: they **skip** unless a run on disk was *built from*
RTL declaring the module, because a netlist-shaped skip condition would
skip on exactly the symptom they exist to catch.

**Before this run, two of them skipped [fact]:**

```
$ .venv/bin/pytest sw/tests/test_synthesis_guards.py -q -rs
33 passed, 2 skipped
SKIPPED [1] ...:1313: no LibreLane run on disk was built from RTL declaring
            aer_par_bank, where the entry-parity check field lives
SKIPPED [1] ...:1363: no LibreLane run on disk was built from RTL declaring
            pilot_chk_bank, where the dispatcher check field lives
```

Those are exactly the two structures `docs/29` and `docs/30` added. The
runs that witnessed them were placed outside the repository and are
gone, so the guards had no witness on disk.

**After this run, all five pass by name [fact]:**

```
$ .venv/bin/pytest sw/tests/test_synthesis_guards.py -v -k real_hardening
test_config_tmr_survives_the_real_hardening_flow            PASSED
test_pointer_tmr_survives_the_real_hardening_flow           PASSED
test_entry_parity_survives_the_real_hardening_flow          PASSED
test_dispatcher_check_field_survives_the_real_hardening_flow PASSED
test_valid_flag_rails_survive_the_real_hardening_flow       PASSED
5 passed, 30 deselected

$ .venv/bin/pytest sw/tests/test_synthesis_guards.py -q -rs
35 passed in 110.79s
```

**35 passed, 0 skipped.** The five guards assert, by name and against
this run's shipped netlist:

| Guard | Asserts |
|---|---|
| `test_config_tmr_survives_the_real_hardening_flow` | **three configuration banks at 55** |
| `test_pointer_tmr_survives_the_real_hardening_flow` | **twelve pointer banks at 3** |
| `test_valid_flag_rails_survive_the_real_hardening_flow` | **eight valid-flag rails at 1** (six names, two of which appear once per queue instance) |
| `test_entry_parity_survives_the_real_hardening_flow` | **two parity banks at 4** |
| `test_dispatcher_check_field_survives_the_real_hardening_flow` | **the dispatcher check bank at 2** |

The run un-skips them because its yosys JSON header names
`aer_par_bank`, `aer_ptr_bank`, `pilot_chk_bank`, `aer_flag_rail`,
`lif_flag_rail` and `pilot_flag_rail` among the elaborated modules
**[fact, `05-yosys-jsonheader/*.h.json`]** — the provenance rule
`docs/30` section 7.3 settled on, which is about what the run was handed
and not about what came out.

**This closes a durability problem, not only a check.** `docs/28`
section 10 item 10 and `docs/30` section 7.3 both record the guards
skipping for want of a witness. `hw/openlane/pilot_ihp/runs/` is in
`RUN_TREES`, so `signoff-6x2` is a witness that stays put, and the two
newest structures are now guarded on every test run rather than on
whoever last hardened outside the tree.

---

## 8. Is this submittable as it stands?

**No — and what is missing is a configuration change and one re-harden,
not a measurement.**

### 8.1 What is established

The design, at 6x2, on the RTL at `bc91c71`, hardened with the adopted
timing configuration, **passes every sign-off deck this repository can
run**: Magic DRC 0, KLayout DRC 0, KLayout XOR 0, Netgen LVS 0 on all
four counters, route DRC 0, antenna 0, power grid 0, disconnected pins
passed, illegal overlap passed, and setup and hold at 0 violations on
all three corners **with a real 5 % OCV derate applied by the flow and
the setup checker pointed at every corner**. `flow__errors__count` is 0.
Slow-corner margin **+1.2262 ns, 6.13 % of the cycle, 53.27 MHz**.
Utilization 48.75 % against a 70 % criterion. The redundancy census is
intact and all five shipped-netlist guards pass by name.

**That is a submittable design.** It is not yet a submittable
submission.

### 8.2 What is missing, exactly

**1. The blocking item: the six keys are not in `tt/src/`.** Section 2.
The shuttle builds from `tt/src/config.json`, which carries none of
them, and `subpath-6x2` measures what that produces on this same RTL:
**-0.7696 ns and 18 violating endpoints at the slow corner, -1.8321 ns
derated** — reported by the flow as clean, because the setup checker
would be looking at the typical corner. **If the submission is made
today, this is what is fabricated.**

The fix is one entry in `CONFIG_OVERRIDES` in
`scripts/gen_tt_submission.py` followed by
`python3 scripts/gen_tt_submission.py`:

```python
CONFIG_OVERRIDES: "dict[str, object]" = {
    "SYNTH_HIERARCHY_MODE": "deferred_flatten",
    "TIME_DERATING_CONSTRAINT": 5.0,
    "SETUP_VIOLATION_CORNERS": ["*"],
    "PNR_CORNERS": ["nom_typ_1p20V_25C", "nom_slow_1p08V_125C"],
    "RUN_POST_GRT_DESIGN_REPAIR": 1,
    "RUN_POST_GRT_RESIZER_TIMING": 1,
    "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.5,
}
```

`scripts/` is outside this document's ownership, and section 2.4
measures why editing `tt/src/config.json` directly is not a substitute:
the generator reverts it and `sw/tests/test_tt_submission.py` fails on
it. **After that change the submission must be re-hardened**, because
no run in this repository will have been built from the file the
shuttle reads. `signoff-6x2` is the prediction of what that run gives,
not the run itself, and the two configurations differ only in path
resolution — an `[estimate]` that a re-harden turns into a `[fact]` in
about 50 minutes.

**2. `mkconfig.py` will silently revert the two flow-defect fixes.**
Section 2.3. `config.json` carries `TIME_DERATING_CONSTRAINT` and
`SETUP_VIOLATION_CORNERS` as hand edits to a generated file, and
`mkconfig.py --check` already reports it as drifted. Once item 1 puts
the keys in `tt/src/config_merged.json`, re-running `mkconfig.py`
regenerates `config.json` correctly and the drift closes by itself; until
then, anyone who runs it removes both fixes. `mktiming.py` now refuses
to generate `config.signoff-6x2.json` if either key is missing from its
base, which contains the blast radius but does not remove the trap.

**3. Max fanout is not gated.** Section 4.2. 84 violations at the slow
corner, stable across every run, and no `Checker.MaxFanout` exists in
this flow. Not a regression and not a blocker, but it is an ungated
number in a sign-off set and this document will not report it as though
a checker looked at it.

**4. Not re-verified against this netlist:** gate-level simulation and
gate-level fault injection. `docs/27` section 9 lists what a new netlist
requires, and this is a new netlist. A concurrent workstream is running
that campaign against this run directory as this is written; its results
are not this document's to report.

**5. `docs/00-index.md` does not name this document**, so
`test_doc_links.py` fails. Section 9.4 has the line to add.

### 8.3 The one-line answer

**The design closes. The submission does not carry what makes it
close.** Nothing in section 4 needs re-measuring; item 1 of section 8.2
needs doing, and then one re-harden to turn the estimate into a fact.
There are three weeks to the 2026-09-21 shuttle close, and the change is
seven lines.

---

## 9. Corrections for the integrator

**No document other than this one is edited.**

### 9.1 `docs/28-timing-recovery.md`

| Location | Current | Replacement |
|---|---|---|
| §6.3, "Magic DRC, KLayout DRC and Netgen LVS were still executing … this configuration must not be submitted until they are read" | as written | **read.** `tr-margin`'s own run directory has since completed: Magic DRC 0, KLayout DRC 0, Netgen LVS 0 with all four unmatched counters 0 **[fact, `final/metrics.json`]**. But `tr-margin` is a run of RTL that has moved twice since, so section 4 of this document supersedes it rather than confirming it. |
| §10 item 7 | open | **closed** by section 4 here, on current RTL |
| §10 item 2, "`SETUP_VIOLATION_CORNERS` is set in this workstream's configs only" | as written | **true of all six keys, not one** (§2.1 here), and still open |
| §6.2, "carried in `hw/openlane/pilot_ihp/config.tr-margin.json`" | as written | that file does **not** carry `TIME_DERATING_CONSTRAINT`, so a run from it as committed is un-derated (§2.2 here). `config.signoff-6x2.json` is the first file carrying all six keys |
| §5.3 / `mktiming.py`'s `tr-best` note, "composing a lever worth -4.36 ns with one worth +0.85 ns has a predictable answer" | as written | **not established.** `docs/29` and `docs/30` both hardened `config.tr-best.json` — `DELAY 0` composed with the post-GRT repair — and report +0.4306 and +1.0423 ns derated, not the large negative the composition argument predicts. The composition was never measured by `docs/28` and the two documents that did measure it did not note the contradiction. Section 9.3 |

### 9.2 `docs/21-pilot-datasheet.md`

§7.1's worst slow-corner setup slack and Fmax should quote this
document's run: **+1.2262 ns and 53.27 MHz at `nom_slow_1p08V_125C`,
derated**, on `signoff-6x2`. `docs/28` §9.1's derate caveat no longer
applies to this run: the derate is applied by the flow, and section 3.2
is the evidence.

### 9.3 `docs/29` and `docs/30`

Both describe `config.tr-best.json` as "the recovered configuration".
It is not the configuration `docs/28` section 6.2 adopted —
`config.tr-margin.json` is — and the two differ in two keys:
`tr-best` sets `SYNTH_STRATEGY: DELAY 0` and omits
`GRT_RESIZER_SETUP_SLACK_MARGIN`. **So no run before this one had ever
hardened the adopted configuration on the RTL those two waves
produced**, which is the gap this document closes. Their timing
conclusions are not disturbed by that — both waves close on either
configuration — but the label should be corrected, and `docs/28`
section 5.3's prediction about `DELAY 0` in composition is
contradicted by their own measurements (section 9.1).

### 9.4 `docs/00-index.md`

`docs/31` is not named there, and
`sw/tests/test_doc_links.py::test_every_document_is_reachable_from_the_index`
fails for that reason **[fact, measured; it also names `docs/32`, which
a concurrent workstream added]**. `docs/00-index.md` is outside this
document's ownership. The entry to add, in the format of the rows
above it:

```
| `docs/31-signoff-6x2.md` | The geometric sign-off of the adopted timing configuration on current RTL, with a real OCV derate applied inside the flow — and the finding that none of the recovery reaches `tt/src/`, so the shuttle as configured would build without it. |
```
