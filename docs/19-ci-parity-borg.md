# CI parity against gonsolo/borg

Answer to the question "does our design pass the CI checks used by
[gonsolo/borg](https://github.com/gonsolo/borg)?" — specifically its
`gds-ihp`, `gds-wafer-space`, `gds-sky130`, `book`, `test` and `fpga`
workflows.

Convention, as everywhere in this repository: **[fact]** = measured in
this environment on 2026-08-26, or read out of an installed file or a
live API response; **[estimate]** = derived or judged.

Borg is a much larger and more mature project than this one: an
open-source GPU with a Chisel/Scala RTL flow, a Nix-pinned toolchain, a
RISC-V CPU that boots mainline Linux on real ULX3S hardware, a Vulkan
driver, a published book, NLnet funding and a Zenodo DOI. Nothing below
should be read as a claim that this project is ahead of it overall. The
question asked is narrower — would our design survive their six CI
gates — and that is the only question answered.

---

## 1. What borg's six checks actually assert

Read from `.github/workflows/` at `gonsolo/borg@main` via
`gh api repos/gonsolo/borg/contents/.github/workflows/<file>`, and the
targets they invoke from the repository `Makefile`, `src/config.json`
and `asic/wafer.space/Makefile`. **[fact]**

| Workflow | Runner | Command | The assertion |
|---|---|---|---|
| `test.yaml` | self-hosted `gonsolo-workstation` | `nix develop --command make test-all` | `scripts/test_runner.py` runs 11 suites: `generate_verilog`, `generate_verilog_sim`, `lint`, Chisel `borg` and `hutt`, `software`, `simulation common`, cocotb `soc-core` and `soc-borg`, and two golden-image render comparisons (arcilator and verilator, `vkcube-cts-uart`, compared to a reference PPM with `--max-diff 1 --max-fail-pixels 2`). Exit 0 from all of them. |
| `book.yaml` | `ubuntu-24.04` | `python3 docs/build_book.py`, then `pandoc` per file | Resolves code snippets into `docs/book/*.md`, converts each to standalone HTML with `--toc`, injects a Mermaid ESM loader and a dark stylesheet, and deploys `_site` to GitHub Pages. |
| `fpga.yaml` | `ubuntu-24.04` + Nix | `make generate_verilog_ulx3s` | Chisel elaborates the full ULX3S SoC (Hutt + Borg + MemoryController) to Verilog and the output is uploaded. **Emission only — no synthesis, no place-and-route, no bitstream, no timing.** It prints `nextpnr-ecp5 --version` and `yosys --version` but does not run them. |
| `gds-ihp.yaml` | self-hosted | `nix develop --command make gds-ihp` → `tt_tool.py --harden --ihp --no-docker` | The harden completes with exit 0. Nothing else. |
| `gds-wafer-space.yaml` | self-hosted | `make librelane SLOT=0p5x1` in `asic/wafer.space/` (GF180MCU, LibreLane) | An explicit gate step: the job counts the "Passed" lines in `librelane.log` and requires exactly 3, and fails if any failure marker appears. The three are Antenna, LVS and DRC. |
| `gds-sky130.yaml` | `ubuntu-24.04` | `TinyTapeout/tt-gds-action@ttsky26a` with `pdk: sky130A`, then `precheck`, then `gl_test` at `CLOCK_MHZ: 4` | The hosted Tiny Tapeout GDS build, the full precheck deck, and a gate-level cocotb run on the action-produced netlist. |

Two things in that table are load-bearing and are easy to miss.

**`gds-ihp` deliberately asserts very little, and borg says so.** Its
header comment states that the hosted path — `gds`, `precheck` and
`gl_test` via `TinyTapeout/tt-gds-action` — was removed so the badge is
"gated by a single, fast job instead of paying for a redundant ~4-5h
hosted run on every trigger", and that "IHP is currently a
diagnostic-only build anyway (8x4 tiles, not a real ttihp26b shuttle
option; a `CLOCK_UNCERTAINTY_CONSTRAINT` not yet validated as
sign-off-safe -- see `src/config.json`)". `src/config.json` is blunter
still: `CLOCK_UNCERTAINTY_CONSTRAINT: 0.05` is "NOT proven safe for real
silicon", it "makes CI green ... but is very plausibly removing real
margin rather than fixing a bug -- do not treat a green gds-ihp badge as
sign-off-safe while this is in effect." **[fact]** A green `gds-ihp`
badge therefore means "a harden ran to completion", not "this is
manufacturable".

**`gds-wafer-space` is the only one of the six that asserts a
manufacturability result.** It is also the only one that states its gate
as a machine-checked condition in the workflow rather than leaving it to
a human reading a log. That pattern is worth copying regardless of
anything else in this document; see section 6.

## 2. What is actually green for borg right now

Read live from `gh run list --repo gonsolo/borg` and
`gh api repos/gonsolo/borg/actions/workflows/<file>/runs`. **[fact, as
of 2026-08-26 00:0x UTC]** A fair comparison needs their real status,
not the aspiration in their workflow files.

| Workflow | Latest conclusion | Run | Notes |
|---|---|---|---|
| `test` | success | `32897833928`, 1h31m46s, 2026-08-25 | Green, but four of the ten preceding runs are `cancelled` at the 6h GitHub-hosted ceiling (`32849854953` 6h00m23s, `32847896456` 6h00m29s, `32845665197` 6h00m20s, `32463325493` 6h00m21s). Commit `ci(test): run on self-hosted workstation instead of GitHub-hosted runner` is the fix, and it is two days old. |
| `book` | success | `32897833823`, 1m14s | Consistently green, 36s–75s, every push. The most reliable check they have. Published at `https://gonsolo.github.io/Borg/`. |
| `fpga` | success (last completed) | `32849854947`, 5h26m36s | Three runs are `in_progress` at 3h09m, 4h05m and 4h56m as of this writing — the queue is backed up. Completed runs take 3h19m–5h26m to emit Verilog. |
| `gds-ihp` | success | `32481339590`, 3h27m13s, 2026-08-21 | Manual `workflow_dispatch` only (or a `v*` tag). Three runs total in history: one success, one cancelled, one failure. |
| `gds-wafer-space` | success | `32849867662`, 1h53m20s, 2026-08-25 | Preceded by two failures (`32845720829`, `32779722224`) on the KLayout GR.2 sealring issue their flake comments describe. |
| `gds-sky130` | **never run** | — | `gh api repos/gonsolo/borg/actions/workflows/gds-sky130.yaml/runs` returns `total_count: 0`. There is no sky130 badge in their README either — it carries five badges, not six. **[fact]** |

So of the six, borg is green on five and has never executed the sixth.
`gds-sky130` is an unexercised workflow file for them as much as it is a
gap for us, and it should not be scored as something they have and we
lack.

## 3. Our status, measured

Everything in this section was run for this document, not read off a
previous record.

### 3.1 `test`

Three tiers, all green. **[fact]**

| Tier | Command | Result |
|---|---|---|
| Python golden models and evidence checks | `.venv/bin/python -m pytest -q` (root; `pytest.ini` sets `testpaths = sw/tests`) | **145 passed** in 0.50s, 0 failed |
| Cocotb RTL | `cd hw/tb && make -f <Makefile{,.regbank,.lif,.secded,.tmr,.scrub,.pilot,.fi}>` | **183 test cases, 0 failures, 15 skipped, 168 passed** across 8 suites and 13 elaborations |
| Formal | `make -C formal everything` | **37 of 37 SymbiYosys tasks `DONE (PASS)`, 0 FAIL, 0 ERROR** |

Cocotb per-suite, counted from the `results*.xml` written by this run
(the terminal summary only shows the last elaboration of a
multi-parameter suite, so the XML is the correct source):
`Makefile` (aer_fifo) 11, `Makefile.regbank` 33, `Makefile.lif` 24,
`Makefile.secded` 12 (enc/dec split, 3+9 skips by construction),
`Makefile.tmr` 7 x 3 widths (1 skip per width, by construction),
`Makefile.scrub` 14 x 3 geometries, `Makefile.pilot` 23, `Makefile.fi`
5. Every skip is a parameterisation guard, not a disabled test.
**[fact]**

The 37 formal tasks are the `[tasks]` sections of the six `.sby` files:
`aer_fifo` 4, `lif_ctrl` 8, `npu_regbank` 5, `scrub` 9, `secded` 3,
`tmr_voter` 8. They cover 528 `assert`/`cover` statements across the six
`*_props.v` files, and they run on both the `smtbmc` and `abc` engines.
**[fact]**

`sw/tests/test_flow_evidence.py` deserves a separate mention: its 16
tests are not unit tests of the design, they re-derive the sign-off
numbers quoted in docs/12 and docs/15 from the retained
`metrics.json` artefacts and fail if the prose and the artefacts
disagree. It passes. **[fact]** That is a check borg does not have an
equivalent of, and it is the reason section 3.2 can be trusted.

### 3.2 `gds-ihp`

We have no hosted Tiny Tapeout action run. What we have is the same
flow, run locally through the rootless LibreLane toolchain of docs/12,
against the submission's own `src/config_merged.json` as produced by
`tt_tool.py --create-user-config` — the exact configuration the GDS
action would consume, not a private one. Verified against
`tt/runs/tt-harden/final/metrics.json`. **[fact]**

| Metric | Value |
|---|---|
| `design__violations` | 0 |
| `flow__errors__count` | 0 |
| `magic__drc_error__count` | 0 |
| `route__drc_errors` | 0 (5 iterations: 2938 → 1192 → 1205 → 45 → 0) |
| `design__lvs_error__count` and all six other LVS counters | 0 |
| `antenna__violating__nets` / `__pins` | 0 / 0, with 0 diodes inserted |
| Post-route STA, 3 PVT corners | 0 setup, 0 hold, 0 max-cap, 0 max-slew |
| `design__instance__utilization` | 0.523819 at 4x2 tiles |
| `design__max_fanout_violation__count` | **72** — disclosed, not gated by LibreLane, discussed in docs/15 section 5.3 |

The comparison with borg's IHP configuration is worth stating precisely,
because it runs the other way from what the badge status suggests.
Reading `tt/runs/tt-harden/resolved.json` against borg's
`src/config.json`: **[fact]**

| Knob | Ours | Borg's |
|---|---|---|
| `CLOCK_PERIOD` | 20 ns (50 MHz) | 250 ns (4 MHz) |
| `CLOCK_UNCERTAINTY_CONSTRAINT` | **0.25** (never overridden; resolves to the template default) | **0.05** (overridden, self-documented as not sign-off-safe) |
| `PL_RESIZER_HOLD_SLACK_MARGIN` | 0.1 | 0.1 |
| Tiles | 4x2 (a real ttihp26b shuttle shape) | 8x4 (`IHP_TILES` diagnostic, "not a real ttihp26b shuttle option") |

We close all three corners at 12.5x their clock frequency with 5x their
hold uncertainty margin, on a shape the shuttle actually offers. That is
a smaller and far simpler design, so it is not a like-for-like
engineering comparison — but on the specific axis borg flagged as its
own weakness, we did not have to relax the knob. **[fact for both
configurations; the "not like-for-like" caveat is an estimate.]**

Two honest caveats, both already recorded in docs/15 section 5.3: our
LibreLane is 3.0.5 where the TTIHP26b dev container pins
`librelane==3.0.0.dev44` (the PDK commit is identical), and a local
`Classic` harden is not the Tiny Tapeout precheck — precheck adds the
pin-placement check against the mux, the top-level-uniqueness check, and
the KLayout DRC deck that the TT config disables with
`RUN_KLAYOUT_DRC: 0`.

Against the precheck's top-level-uniqueness check specifically, we have
read the GDS back: exactly one top-level cell,
`tt_um_melihakbulut_nssoc`, bounding box 854.40 x 313.74 um, which is
the 4x2 geometry to the micron. **[fact, gdstk]**

### 3.3 `gds-wafer-space`

We have no GF180MCU flow, no `asic/wafer.space/`, and no `chip_top` with
pads, sealring and SRAM macros. The workflow as written cannot run here.

Its *gate rule* — Antenna, LVS and DRC must all pass, three passes and
no failures — can be applied to our numbers on our own PDK, and it is
satisfied twice over. The `aer_fifo` sg13g2 sign-off run of docs/12
(gate G0), from
`hw/openlane/aer_fifo/runs/trial-03-signoff/final/metrics.json`:
**[fact]**

| Gate | Result |
|---|---|
| Antenna | `antenna__violating__nets` 0, `antenna__violating__pins` 0 (3 `sg13g2_antennanp` cells inserted by detailed routing) |
| LVS | `design__lvs_error__count` 0, and 0 on all six other Netgen counters |
| DRC | `magic__drc_error__count` 0, `klayout__drc_error__count` 0, `route__drc_errors` 0, `design__xor_difference__count` 0 |

That run also carries `design__violations: 0`, `flow__errors__count: 0`,
0 max-cap and 0 max-slew violations on all three corners, and 0
power-grid violations. It discloses `design__max_fanout_violation__count:
90`, which docs/12 section 4.4a decomposes: 89 of the 90 are CTS clock
buffers held to `sg13g2_stdcell`'s `default_max_fanout` of 8, which is a
library default and not the design constraint.

Note that this run has `klayout__drc_error__count: 0` where the
`tt-harden` run does not run KLayout at all — the sg13g2 `aer_fifo`
config leaves the KLayout deck enabled, the Tiny Tapeout template
disables it. So the KLayout deck has been exercised on this project's
RTL, on this PDK, in this toolchain; just not on the TT submission
geometry.

### 3.4 `gds-sky130`

Our target is IHP `sg13g2` / ttihp26b, not sky130. We have no sky130
harden and no sky130 evidence, so this check does not describe our
design today.

A sky130 pilot harden is **in progress concurrently** in
`hw/openlane/pilot_sky130/` (a `config.json`, a `run_sky130.sh` and a
`runs/` tree exist as of this writing). It is not this document's work
and its results are not folded in here. When it lands, the correct claim
will still be narrower than borg's workflow: `gds-sky130.yaml` runs the
hosted `tt-gds-action`, the full precheck and a gate-level cocotb run,
and a local harden is only the first of those three.

The honest position: this is the one check where borg has a workflow
file and we do not — and they have never run it either (section 2).

### 3.5 `fpga`

We have no FPGA flow. `hw/fpga/` currently contains a single file,
`ulx3s.lpf`; an FPGA target is **in progress concurrently** and is not
this document's work.

Worth calibrating what the bar is, though: borg's `fpga` job runs
`make generate_verilog_ulx3s`, which is Chisel elaboration to Verilog
and an artefact upload. It installs `nextpnr-ecp5` and `yosys` and
prints their versions, but does not invoke them. It does not synthesise,
place, route, produce a bitstream, or check timing. It is an "the RTL
still elaborates for this target" check. **[fact]** Our RTL is
hand-written Verilog, so the elaboration step that job protects against
does not have an analogue here; the equivalent bar for us would be
"`yosys` reads the ULX3S top and emits a netlist", which is a
substantially smaller job than the name `fpga` suggests. **[estimate]**

### 3.6 `book`

We have 20 markdown documents in `docs/`, 13,633 lines total, counting
everything except this document. (The corpus was 19 documents when this
assessment began; `docs/18-cross-pdk-portability.md` was added by
concurrent work while it was running, and it does not change any figure
below.) Assessed for pandoc-readiness without building anything:
**[fact]**

| Property | Count | Consequence |
|---|---|---|
| `pandoc` installed locally | no | Not a blocker — borg's workflow installs it with `apt-get` in CI |
| `graphviz` / `dot` installed | yes (`/usr/bin/dot`) | Available if ever needed |
| Markdown links | **0** | No internal links to break. Nothing can 404. |
| Image references | **0** | No missing images. `docs/` contains no non-`.md` files at all. |
| Mermaid or graphviz blocks | **0** | The Mermaid loader borg injects would be dead weight for us |
| Fenced code blocks | 9 (6 `text`, 1 `tcl`, 1 `sh`, 1 `yaml`) | Trivial to render |
| Bare `docs/NN` cross-references in prose | **603** | The actual gap |

Our documents are prose and tables. They would convert cleanly — there
is nothing in them that pandoc can fail on, and there is no broken link
or missing asset because there are no links or assets. The gap is not
conversion, it is navigation: 603 cross-references of the form "docs/06
section B.6" are plain text and would stay plain text, and there is no
`docs/00_index.md` equivalent to land on.

Effort to close: a `.github/workflows/book.yaml` modelled on borg's,
minus `build_book.py` and minus the Mermaid injection, is roughly 40
lines and an afternoon. An index page is another hour. Turning the 575
cross-references into anchors is a scripted rewrite plus a proofread and
is the only part that is not trivial — call it a day, and it is
optional. **[estimate]**

## 4. Verdict per check

| Check | What it asserts | Borg's status | Our status | Evidence | Verdict for us |
|---|---|---|---|---|---|
| `test` | 11 suites exit 0 under `make test-all` | Green (`32897833928`); four of the preceding ten runs hit the 6h hosted timeout | 145 pytest + 183 cocotb (0 fail) + 37/37 formal, all green, ~40 min wall | `pytest -q`; `make -f Makefile.*` in `hw/tb`; `make -C formal everything` | **Pass today** |
| `gds-ihp` | An IHP harden completes, exit 0 | Green (`32481339590`), but self-described as diagnostic-only on a non-shuttle 8x4 shape with an unvalidated `CLOCK_UNCERTAINTY_CONSTRAINT` | Full `Classic` flow at 4x2 completes with `flow__errors__count: 0`, locally, on the action's own config | `tt/runs/tt-harden/final/metrics.json`; `tt/runs/tt-harden/resolved.json` | **Pass if we ran it** — the assertion is met locally; it has never run in CI |
| `gds-wafer-space` | Antenna + LVS + DRC all pass, machine-checked | Green (`32849867662`), after two failures | Cannot run: no GF180MCU flow, no `chip_top`, no pads or sealring. The gate *rule* is satisfied on sg13g2 (0/0/0) and on ttihp26b | `hw/openlane/aer_fifo/runs/trial-03-signoff/final/metrics.json` | **Not applicable** as written; the underlying gate passes on our PDK |
| `gds-sky130` | Hosted TT GDS + precheck + gl_test on sky130A | **Never executed** (`total_count: 0`); no badge in their README | No sky130 evidence. A local harden is in progress concurrently | `gh api .../workflows/gds-sky130.yaml/runs` | **Cannot pass yet** — and neither, so far, can borg |
| `book` | Docs build to HTML and deploy to Pages | Green every push, 36–75s; live at `gonsolo.github.io/Borg` | No workflow, no site. 19 docs that would convert cleanly: 0 links, 0 images, 0 mermaid | `grep` over `docs/*.md`; `pandoc` absent locally but installed by CI | **Cannot pass yet** — nothing exists to run; ~1 day to close |
| `fpga` | Chisel elaborates the ULX3S SoC to Verilog | Green (`32849854947`), 3h19m–5h26m per run; three runs currently backed up | No FPGA flow; `hw/fpga/` holds one `.lpf`. In progress concurrently | `ls hw/fpga/` | **Cannot pass yet** |

## 5. Where we are genuinely ahead, and where we are behind

### 5.1 Ahead

**Formal verification.** We have 37 SymbiYosys proof tasks over 528
properties, all passing. Borg has none. This was checked rather than
assumed: `gh api search/code?q=repo:gonsolo/borg+extension:sby` returns
0; `docs/A2_gap_analysis.md` contains no occurrence of "formal",
"assert property" or "model check"; the one `assert` in
`BorgSequencer.scala` is the word "deasserts" in a comment. **[fact]**
Their verification is simulation and golden-image comparison, which is
appropriate for a rasteriser and says nothing bad about them — but a
bounded model check is a different kind of evidence and they do not have
it.

**Fault injection.** `hw/tb/test_fi_campaign.py` flips one bit of one
architectural flip-flop at a time across 19 target groups, 255
injections, judged only against `sw/golden/lif_core.py`: 83 MASKED, 42
CORRECTED, 39 DETECTED, 91 SDC, 0 HANG. Borg's repository contains no
fault-injection, SEU or radiation material — again checked, not assumed.
**[fact]**

Re-running it for this document also demonstrated that the campaign is
deterministic: `hw/tb/fi_campaign_results.json` was regenerated and the
only field that changed was `wall_seconds` (182.3 to 213.1, this machine
being busier). Every one of the 255 verdicts and the whole histogram
reproduced exactly. **[fact]** This is a rad-hard-oriented design and they are building a
GPU, so the asymmetry is expected; it is still a capability we have and
they do not.

**Mutation-tested benches.** `hw/tb/results_mut_m1..m8*.xml` are eight
deliberate RTL mutants, each of which the suite catches (1–2 failures
per mutant). That is evidence the tests have teeth, which most projects
at this scale cannot produce.

**Evidence that is checked by CI rather than asserted in prose.**
`sw/tests/test_flow_evidence.py` fails if docs/12 or docs/15 drift from
the retained `metrics.json`. Borg's documentation is not mechanically
tied to its run artefacts.

**Sign-off margin on IHP.** Section 3.2: default hold uncertainty at 50
MHz on a real shuttle shape, against a relaxed one at 4 MHz on a
diagnostic shape. On a much smaller design, but it is the axis they
themselves flagged.

### 5.2 Behind

**No hosted Tiny Tapeout action run.** This is the single biggest gap
and it is not a small one. Every GDS number we have is from a local
harden. The artefact that gets manufactured is the one the action
produces, and precheck runs three checks our local flow does not run at
all. Borg has executed the real hosted path historically; we have not
executed it once.

**No FPGA target.** Borg's RTL runs on real ULX3S hardware, boots
mainline Linux on it, and renders. That is a class of validation — real
clock, real memory, real I/O — that no amount of simulation substitutes
for, and we have none of it.

**No docs site.** They have a published, continuously-deployed book. We
have 19 files in a directory.

**No toolchain reproducibility.** See section 6. This is the one where
their approach is straightforwardly better than ours.

**Scale and maturity.** Borg's `test-all` covers Chisel unit tests,
a software suite, a Vulkan CTS slice, RV32 boot, and two golden-image
render comparisons against reference PPMs at a 1-LSB tolerance. Ours
covers a much smaller design. A green `test` on both repositories does
not mean the two checks are comparable in weight; theirs is heavier.
They also have a Zenodo DOI, a `CITATION.cff`, NLnet funding and a
public roadmap.

## 6. What to copy from borg

**The Nix flake, first and by a wide margin.** Their `flake.nix` pins
`nixpkgs` to a specific commit — not a branch — of their own integration
branch, and the comment block enumerates six toolchain fixes carried
there with the upstream issue or PR for each: librelane 3.0.4→3.0.8,
yosys 0.67→0.68 (YosysHQ/yosys#6050), an or-tools Python 3.14 fix,
openroad 26Q2→26Q3 (The-OpenROAD-Project/OpenROAD#10743, a GRT-0183 heap
underflow in antenna-repair routing), an sv-lang build fix, and klayout
0.30.10→0.30.11 (KLayout/klayout#2425, a `.separation()` regression that
spuriously flagged GR.2 at sealring reflex corners). The flake also
resolves a real cocotb `PYTHONPATH` hazard between two Python versions
in one shell, with a comment recording that CI caught it twice.
**[fact]**

Set that against our situation, all of it observed while producing this
document. **[fact]**

- `hw/tb/Makefile` carries a PATH-rewriting re-invocation of itself
  because "make < 4.4 does not pass exported PATH to `$(shell ...)`".
- The first test run for this document failed twice before it ran:
  `python` is not on PATH at all, and `python3` has no pytest. The suite
  only executed once `.venv/bin/python` was located by hand.
- Our LibreLane is 3.0.5 against the dev container's pinned
  `3.0.0.dev44`.
- Most pointedly: `sby` is **not on PATH**. `formal/Makefile` therefore
  falls through to its `wildcard` fallback, and the 37 proofs reported
  in section 3.1 were executed by
  `/home/hasanmelih/Documents/gt2n-soc/tools/oss-cad-suite/bin/sby` —
  a toolchain checkout belonging to a **different project on this
  machine**, selected by glob order. The proofs pass, and there is no
  reason to doubt them, but which binary proved them is an accident of
  the filesystem. Nothing in this repository pins it, and nothing would
  notice if that directory were deleted or upgraded.

Every one of those is the problem the flake solves.

Adopting Nix wholesale is a large change and is not the recommendation.
The recommendation is to evaluate a `flake.nix` that pins the four tools
that actually decide our results — yosys, iverilog, SymbiYosys, and
LibreLane with its PDK commit — and to keep borg's habit of recording
*why* each pin is where it is, with the upstream bug number. Even
without Nix, that comment block is a format worth stealing.

**Second: assert the gate in CI, not in prose.** `gds-wafer-space.yaml`
does not upload a log for a human to read; it greps for exactly three
passes and fails the job otherwise. We have the numbers to gate on and
we gate on none of them. `sw/tests/test_flow_evidence.py` is the right
instinct already — it just is not wired to a workflow, because we have
no workflows at all.

**Third, and cheapest: the `book` workflow.** Ours would be borg's minus
`build_book.py` and minus the Mermaid injection. Section 3.6.

## 7. Summary

Of borg's six checks: we pass `test` today. We would pass `gds-ihp`'s
assertion if we ran it, and on a better-conditioned configuration than
theirs. `gds-wafer-space` does not apply to us as written, though its
Antenna/LVS/DRC gate passes on both of our hardened blocks.
`gds-sky130`, `book` and `fpga` we cannot pass yet — and `gds-sky130`
has never run for borg either.

The gap that matters is not any of the six badges. It is that borg's
results are reproducible by a stranger with `nix develop` and ours are
reproducible by this machine.
