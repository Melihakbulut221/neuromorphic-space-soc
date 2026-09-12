# 61 — The SoC placed and routed with the accelerator in it

`docs/57-power-under-a-duty-cycle.md` section 16 asked for one thing and
put it above everything else in the record:

> **HARDEN THE SoC THAT EXISTS.** `docs/47` through `docs/53` are six
> documents of area, timing and now power for a `soc_top` that is
> **missing 50.7 % of its cells and 69.8 % of its flip-flops**. … **It is
> the cheapest thing in this record that makes six documents' numbers
> true again.**

**This is that run.** `soc_top` — Ibex, the fabric, the peripherals, the
six RM_IHPSG13 macros and, for the first time, `soc_npu` with the frozen
pilot inside it — has been synthesised, floorplanned, placed,
clock-tree-synthesised, routed, extracted and timed at three corners, on
the recipe `docs/47` used and against the checker configuration
`docs/47`, `docs/48`, `docs/49` and `docs/50` all report 17 of 19
against.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged, with the
derivation stated; **[assumption]** = chosen, and named so it can be
argued with; **[planned]** = intended, with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by blob hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was modified.
`hw/rtl/pilot_top.v`, `lif_core.v`, `aer_fifo.v`, `scrub.v` and
`tmr_voter.v` are **read** and instantiated in place, exactly as
`hw/soc/flow/sim_soc.sh` already read them — `soc_npu.v` instantiates the
frozen submission rather than copying it, which is why they are in the
synthesis source list at all. No run under `hw/openlane/` was created,
resumed or written. Section 16 lists every file.

**And no RTL file in this repository was modified either.** Section 16.
What changed is four flow scripts, one configuration, one generator, one
new script, one guard test and this document.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Does the accelerator fit in `docs/47`'s floorplan?** | **Yes, and the die does not have to grow.** The same die, the same core box, the same six macro origins and the same two orientations hold **1.5761 times the standard-cell area** — 624,429.9180 um2 against 396,177.6420 **[fact]**. `PL_TARGET_DENSITY_PCT` moves 40 → 48 by `floorplan.py`'s own rule and **that is the only key in the whole configuration that changes**. Sections 6 and 7 |
| **What is the design, measured?** | **42,518 cells, 5,263 flip-flops, 624,429.9180 um2** as synthesised, against `docs/47`'s **27,565 / 3,085 / 396,177.6420** — **×1.5425, ×1.7061, ×1.5761** **[fact]**. The **+26 flip-flops** over `docs/57` section 9's NPU-inclusive figure are exactly `docs/58`'s published cost for the `mtime` codeword **[fact against fact]**. Section 5 |
| **Does it close?** | **No, and it is not measurably further away than the design that had no accelerator in it.** At `nom_slow_1p08V_125C`, 20 ns, 5 % derate, extracted parasitics: **−3.5789 ns on 2,175 endpoints** against `docs/47`'s **−3.2029 on 2,003** **[fact]**. **The delta is −0.3760 ns and `docs/44` section 5.2 measured this flow's resolution at about 0.4 ns, so it is inside the noise floor and is NOT reported as a regression.** TNS is **−2,981.09 against −2,075.11**, which is outside any noise floor and is reported. **Hold now closes at all three corners** — `docs/47`'s −0.2015 ns on 3 fast-corner endpoints becomes **+0.0981 on 0** — and **detailed-routing DRC is 0**. Max slew and max cap are worse: **29 / 8 / 6 against 14 / 0 / 1** and **15 / 15 / 15 against 10 / 10 / 12**. Section 8 |
| **Do the checkers still gate?** | **17 of 19, the same four as `docs/47`, `docs/48`, `docs/49` and `docs/50`**, recomputed from the installed LibreLane's own step classes against this run's `resolved.json`. `Checker.SetupViolations`, `HoldViolations`, `MaxSlewViolations` and `MaxCapViolations` each examined **three corners**. The two that do not gate are `Checker.LintWarnings` and `Checker.WireLength`, named rather than repaired, as in all four. Section 10 |
| **Did the instrument reproduce before it moved?** | **Yes, eight ways, four of them byte-exact.** `docs/47`'s **−3.2029 on 2,003 endpoints** and its whole three-corner block; its **27,565 / 3,085 / 396,177.6420**; `docs/49` section 3.1's **444 / 1,559** violator split, from a script that is now in the tree; `docs/48` section 2's CTS span **1,851.8 × 790.0 at (388.8, 582.1) over 27,558 cells**; `floorplan.py` still emitting `config.json` **byte for byte**; `checker_audit.py`'s **17 of 19**; and `docs/42`'s clean fault-injection run at **18,682 cycles, sig `9c07ef12`**, from the repaired `fi_core.sh`. Section 2 |
| **Where did the accelerator's flip-flops go in the clock tree?** | **Onto the ungated net, all 2,178 of them, and clock-tree synthesis says so directly.** `clk_i_regs` goes from **762 sinks to 2,940** while `u_ibex.clk` stays at **2,323** **[fact, `CTS-0010` and `CTS-0011`]**. `docs/57` section 9 measured the accelerator's idle power ratio at **5.588x** and attributed it to 2,152 ungated flip-flops; this is the same fact in the layout, counted by a different tool, with `docs/58`'s 26 added. Sections 7.3 and 11 |
| **Which of the four measured remedies survive?** | **One outright, one with its mechanism changed, one moot, one unresolved.** Section 9 |
| **Is `docs/48`'s floorplan conclusion still true?** | **Its result is not refuted and its mechanism is gone.** That document's argument rested on `PL_TARGET_DENSITY_PCT` 40 against a **18.9 %** utilization — *"the placer was never density-constrained in FP-0, and that is why the sizing lever does not exist"*. Utilization is now **29.85 %**, the routability optimiser **stops on its iteration cap instead of on convergence**, and `docs/48`'s own "cells / their own bounding box" predictor falls from **27.1 % to 19.3 %** with **no cost at post-CTS** — so that predictor is now measured wrong. **FP-A and FP-B were not re-run and nothing here says what they would do.** Sections 6.3, 7.2 and 9.1 |
| **`fi_core.sh`?** | **Repaired, cheaply, and the repair is checked rather than announced.** `docs/42`'s clean run comes back at **18,682 cycles with signature `9c07ef12`** — the figure `docs/42`, `docs/43` and `docs/44` all publish, reproduced exactly **[fact]**. `docs/46`'s supervisor comes back with the same answer word `216f8ce6` and the same injection window **9,376..67,296**, at **69,085 cycles against `docs/57`'s 69,106**, and that difference is reported rather than explained. **No campaign was re-run.** Section 12 |
| **What stops this being a sign-off?** | **The same three things as `docs/47`, unchanged and unchangeable here: no Magic DRC, no KLayout DRC, no KLayout XOR and no Netgen LVS**, because `docs/12` sections 7.5 and 8 record **1,106,478 / 2,316 / 359** errors over ONE RM_IHPSG13 macro and a **NO-GO**, and `docs/54` found the KLayout exit shut as well. Section 14 |
| **May a frequency be published?** | **No.** `docs/53` section 9.2 refused it on three grounds, `docs/05` section 4 rule 5 binds, and none of the three grounds moved. Slack against the 20 ns constraint is what this document reports. Section 8.4 |

---

## 2. Reproducing every instrument before moving it

`docs/44` section 5.2 set the rule and `docs/45`, `docs/47`, `docs/48`,
`docs/49`, `docs/50` and `docs/57` have all followed it. **Eight
instruments are used in this document and all eight were reproduced
first**, in this session, against the published figures.

| What | Published | Measured here |
|---|---|---|
| `docs/47` section 8.2, the sign-off block | −3.2029 / 2,003 / −2,075.11 slow; +5.7231 typ; +10.6634 fast; hold −0.2015 on 3 at fast; slew 14 / 0 / 1; cap 10 / 10 / 12 | **every figure**, `signoff_report.py hw/soc/pnr/runs/full3` **[fact]** |
| `docs/47` section 6.1, the hardened netlist | 27,565 cells, 3,085 flip-flops, 396,177.6420 um2 | **the same three**, `hw/soc/out/s47-sram/area.rpt` **[fact]** |
| `docs/47` section 7.3, the checker audit | **17 of 19**, not gating: `LintWarnings`, `WireLength` | **17 of 19, the same two** **[fact]** |
| `docs/49` section 3.1, the violator split | 444 behind the macro, worst −3.2029; 1,559 behind four read-address bits, worst −2.0227; 217 check-bit captures | **444 (405 + 31 + 8) and 1,559 (868 + 509 + 181 + 1), worst −3.2029 and −2.0227, 217 check bits** — and the total −2,075.11 **[fact]** |
| `docs/48` section 2, the standard-cell span at CTS | 1,851.8 × 790.0 um over 27,558 cells at (388.8, 582.1) | **1,851.8 × 790.0 over 27,558 at (388.8, 582.1)**, to the last digit printed **[fact]** |
| `docs/48` section 4, the floorplan generator | `--channel 700.08 --density 40` emits `config.json` byte for byte | **byte for byte, after the generator gained `--cell-area`** **[fact]** |
| `docs/42` section 5 / `docs/43` / `docs/44`, the clean FI run | **18,682 cycles, sig `9c07ef12`** | **18,682, `9c07ef12`** **[fact]**, from `fi_core.sh` repaired |
| `docs/46` section 7.1 / `docs/57` section 2, the supervisor | `sig = 216f8ce6`, window 9,376..67,296 | **`216f8ce6`, 9,376..67,296** **[fact]** |

**Two of the eight did not come for free and both are recorded rather
than smoothed over.**

- **`docs/49` section 3.1's split needed a script that did not exist.**
  That document resolved the violator list against the netlist with a
  script written for the occasion; so did `docs/50` section 6.3. This
  document needed it a third time, so it is in the tree as
  `hw/soc/pnr/violator_census.py`, and the check that it is the same
  instrument is that it reproduces `docs/49`'s table on `full3`
  unchanged. It also finds something that table did not report:
  **496 of the 2,003 violating endpoints are captured at an SRAM macro's
  own input pins** — `A_ADDR`, `A_BM`, `A_DIN` — with a worst slack of
  **−1.8718** **[fact]**. Not an error in `docs/49`, which partitioned by
  launch; a category that partition made invisible.
- **`docs/46`'s supervisor is 69,085 cycles here against `docs/57`'s
  69,106 and `docs/46`'s 69,100** **[fact]**. The answer word and the
  injection window are identical in all three, so it is the same program
  on the same design up to window close at cycle 67,296; the difference
  is in the tail after it, and **this document did not isolate it**.
  `docs/57` recorded the same shape — its own 69,106 against `docs/46`'s
  69,100 — and attributed that six to campaign build settings. **The
  number used anywhere in this document is this run's.**

---

## 3. The defect, and why it was silent for ten documents

### 3.1 What was wrong

`docs/51` put `u_npu` inside `hw/soc/rtl/soc_top.v`. **Four flow scripts
build that file and one of them was updated.**

| Script | What it builds | State before this document |
|---|---|---|
| `flow/sim_soc.sh` | the whole-SoC simulation | **updated by `docs/51`.** Correct throughout |
| `flow/fi_core.sh` | `docs/42`, `docs/43`, `docs/46`'s campaigns | **did not elaborate at all** — `soc_top.v:624: error: Unknown module type: soc_npu` **[fact, `docs/57` section 3.1]** |
| `flow/syn_soc_top.sh` | the netlist `docs/45` and `docs/47` measure | **did not elaborate at all** — `ERROR: Module '\soc_npu' … is not part of the design` **[fact, `docs/57` section 3.2]** |
| `flow/pnr_soc_top.sh` | the resolved LibreLane config | same source list, same gap |

### 3.2 Why one of them was loud and three were silent, which is the finding

`fi_core.sh` is **run**, so it failed. The other three are **not run
between documents** — their output is a netlist and a run directory that
sit on disk and get reported from. So:

> **`hw/soc/pnr/runs/full3` did not become wrong when `docs/51` landed.
> It stayed exactly as correct as it had been, for a design that had
> stopped existing.** Every area, timing and power figure in `docs/45`,
> `docs/47`, `docs/48`, `docs/49`, `docs/50` and `docs/53` is a figure
> for that design, and nothing in the flow, in a metrics file or in a
> checker could have said so. **A stale artefact reports no error.**

`docs/51` section 11's own last line — *"`docs/47`'s sign-off does not
include this block"* — is correct and was written at the time. What
happened is that **two documents later it was no longer being carried**,
and `docs/53` section 7.2 multiplied that layout's energy per cycle by an
accelerator's cycle count. `docs/57` section 3.2 and `docs/59` section 7
found the same fact independently, an hour apart, from the source list
and from the DEF.

### 3.3 The fix, and the guard that makes the next one loud

The source lists are repaired in all three scripts (section 16). **That
is not the interesting half.** The interesting half is that four
hand-maintained lists of the same design's files is a defect generator,
and `docs/45` section 9 item 4 already proposed the structural repair —
*"derive the source list from the top rather than reading everything"* —
and declined it because it would make five documents' per-block numbers
reproducible only against a different recipe. **That decision is not
revisited here** and section 18 carries it forward.

What is added instead is the cheap defence:
`sw/tests/test_soc_synthesis_guards.py::test_every_flow_that_builds_soc_top_reads_every_module_it_instantiates`.
It reads `soc_top.v`'s instantiations out of the RTL, keeps the ones
whose file exists in `hw/soc/rtl/` or the frozen `hw/rtl/`, and asserts
that all four flows name each of them **on a non-comment line** — and
then does the transitive step that made this one expensive, because
`soc_npu.v` instantiates `pilot_top`, `aer_fifo`, `tmr_voter` and
`soc_npu_ser`, and a list with `soc_npu.v` and no `pilot_top.v` fails one
level deeper down.

**It is mutation-tested against the defect it exists for.** Run against
the four scripts as they stood at `abcde58`, the assertion fires **nine
times**: `soc_npu`, `pilot_top` and `aer_fifo` absent from
`syn_soc_top.sh`, `pnr_soc_top.sh` and `fi_core.sh` **[fact]**. It also
asserts that at least eight of `soc_top.v`'s children were examined, so a
file-layout change cannot turn it vacuous quietly.

**What the guard does NOT do** is check that the four lists are the same
list. They are not and must not be: `sim_soc.sh` reads `soc_mem.v` and
the synthesis flows must not, `syn_soc_top.sh` has four implementations
of `soc_mem` behind one variable, and `fi_core.sh` adds a testbench.

---

## 4. What was built

| File | Change |
|---|---|
| `hw/soc/flow/syn_soc_top.sh` | the six accelerator sources, with both include paths. **No knob, and section 5.1 is why there cannot be one** |
| `hw/soc/flow/pnr_soc_top.sh` | the same six, in the list it merges into the resolved config |
| `hw/soc/flow/fi_core.sh` | the same six, plus `-I hw/rtl`. Section 12 |
| `hw/soc/pnr/config.json` | **one key**: `VERILOG_INCLUDE_DIRS` gains `hw/rtl`, for `npu_regs.vh` |
| `hw/soc/pnr/floorplan.py` | `--cell-area`, so the floorplan is sized against the netlist it is for and not against a constant. The generator still emits `config.json` byte for byte |
| `hw/soc/pnr/config-npu.json` | the floorplan variant this run hardens. Generated; **differs from `config.json` in `PL_TARGET_DENSITY_PCT` and nothing else**, under the generator's own assertion |
| `hw/soc/pnr/violator_census.py` | the violator resolution `docs/49` and `docs/50` each wrote and threw away |
| `sw/tests/test_soc_synthesis_guards.py` | one test, section 3.3 |
| `docs/61-soc-with-the-accelerator.md` | this document |
| `docs/00-index.md` | one row, which `sw/tests/test_doc_links.py` requires |

**No RTL, no testbench and no formal file was modified** **[fact,
`git status`]**.

---

## 5. The design that exists

### 5.1 There is no "without the NPU" configuration and there cannot be one

`soc_top.v` instantiates `u_npu` **unconditionally**. So a `SOC_NPU=0`
mode in `syn_soc_top.sh` would not reproduce `docs/47`'s netlist — it
would fail to elaborate, which is exactly what the script did before this
change. **The only artefact of the design `docs/45` to `docs/53` measure
is the netlist already on disk at
`hw/soc/out/s47-sram/soc_top.netlist.v`**, and that is what every
reproduction in section 2 reads. The sources are therefore added
unconditionally and the script's header says so.

**One consequence is named rather than left to be discovered.**
`docs/50` section 2's control — *"the netlist is then byte-identical to
the one `docs/47` hardened"* — can no longer be re-derived from HEAD's
RTL at `SOC_MEM_RDREG=0`. It is a statement about a netlist that is
preserved as a file, and it stays true of that file.

### 5.2 The area

`SOC_MEM=sram hw/soc/flow/syn_soc_top.sh 20`, same Liberty, same typical
corner, same `abc.constr` (`sg13g2_buf_4` driving, 5 fF load), same 20 ns
`-D` target, same deferred flatten, same `stat -liberty`. **The recipe is
`docs/45`'s recipe and that is the whole point of comparing.**

| | `docs/47`, `hw/soc/out/s47-sram` | **this run, `hw/soc/out/s61-sram`** | ratio |
|---|---:|---:|---:|
| cells | 27,565 | **42,518** | **1.5425x** |
| flip-flops | 3,085 | **5,263** | **1.7061x** |
| standard-cell area, um2 | 396,177.6420 | **624,429.9180** | **1.5761x** |
| kGE at 7.2576 um2 | 54.588 | **86.038** | |

**[fact, `stat -liberty` on two syntheses; the ratios are arithmetic]**

**Three cross-checks, and all three are against numbers somebody else
measured.**

1. **`docs/57` section 9 predicted 41,543 / 5,237 / 619,892.406** for the
   same recipe on `7721719`'s RTL. This is **+975 cells, +26 flip-flops
   and +4,537.512 um2** on top of that **[fact against fact]** — and
   `7721719` is the commit before `docs/58`, whose published cost is
   **exactly +26 flip-flops**. The flip-flop arithmetic closes to zero.
2. **`docs/51` section 11 measured `soc_npu` standalone at 12,421 cells,
   2,008 flip-flops and 209,739.0834 um2.** The whole-design delta here
   is **+14,953 cells, +2,178 flip-flops and +228,252.276 um2**, of
   which `docs/58`'s +26 flip-flops are not the accelerator's; the
   remaining **+2,152** is `docs/57` section 9's figure, and that
   document already reconciled it against `docs/51`'s 2,008 — six for the
   sixth fabric port, the rest the parameter set `soc_top.v` elaborates
   the block with.
3. **Clock-tree synthesis counts the same 2,178 independently.** Section
   7.3.

**And one thing that did NOT change**: the netlist is still flat and
still anonymous. **42,511 of 42,518 cells are `_NNNNN_` and the only cell
carrying an RTL path is `u_ibex.core_clock_gate_i.u_icg`** **[fact]** —
`docs/59` section 6's finding is unchanged, and a per-block region map of
this die is still not extractable.

---

## 6. The floorplan, which is the decision this document had to take

### 6.1 The question

`docs/59` section 5 measured the design occupying a **700.08 um** channel
at **34.84 %** density with **thirteen cells and no flip-flops** above
it. Half again as many cells has to go somewhere, and the options are a
taller channel, a different macro arrangement or a bigger die — each with
an area cost.

**`docs/48`'s evidence points both ways and that is why this was a
decision and not a calculation.** It measured two smaller floorplans and
both were worse; its stated mechanism was that FP-0's sparseness *"is not
slack the placer was wasting; it is the room the placer needs"*, which
argues for **more** room, not less. But it also measured that the placer
was **never density-constrained** in FP-0 — `PL_TARGET_DENSITY_PCT` 40
against a utilization of 18.9 % — and an unconstrained optimum does not
improve when the box grows. **More room can only buy feasibility.**

### 6.2 So the cheapest experiment is the one that answers it

> **KEEP `docs/47`'s FLOORPLAN AND SEE WHETHER IT STILL FITS**, because
> if it does, the area cost of the accelerator's floorplan is **zero**,
> and if it does not, the failure says which direction to grow in.

`hw/soc/pnr/floorplan.py` generated the configuration, because
`docs/48`'s three reasons for a generator all still hold and one of them
has bitten this project once already: **the macro sizes are read from the
installed PDK's LEF and site alignment is asserted rather than
arranged.** The generator gained one option — `--cell-area` — and the
reason is in its own header: a floorplan sized against a cell area the
design no longer has **is exactly the defect `docs/47` section 6.1 made
once in the other direction**, when it sized the channel against
LibreLane's own synthesis rather than the netlist it hardened.

```
floorplan.py --channel 700.08 --cell-area 624429.9180 \
             --write hw/soc/pnr/config-npu.json
```

| | FP-0, `docs/47` and `docs/48` | **this run** |
|---|---|---|
| arrangement | two rows of RAM, RAM, ROM | **the same** |
| channel height | 700.08 um, 185 rows | **the same** |
| die | 2306.40 × 2075.22 = 4.7863 mm2 | **the same** |
| core | 2186.40 × 1984.50, 525 rows | **the same** |
| six macro origins and orientations | — | **the same** |
| placeable, core − macro | 2,092,010.95 um2 | **the same** |
| standard cells as synthesised | 396,177.6420 um2 | **624,429.9180** |
| **standard cells / placeable** | **18.94 %** | **29.85 %** |
| `PL_TARGET_DENSITY_PCT` | 40 | **48** |

**[fact for every geometric figure; the two densities are arithmetic on a
measured cell area]**

**`PL_TARGET_DENSITY_PCT` is the only key that moves, and it moves by
`docs/48`'s own rule and not by judgement.** `floorplan.py` has emitted
`round(utilization) + 18` since that document; at FP-0's 18.94 % the rule
gives 37 and `docs/47` chose 40, so the rule has never bound before.
Here it gives **48**. The generator's assertion is unchanged and it
fired: **the file differs from `config.json` in `PL_TARGET_DENSITY_PCT`
and in the generated provenance note, and in nothing else** **[fact]**.

**And the strongest available control still passes.** At
`--channel 700.08 --density 40` — with the default `--cell-area`, which
is still `docs/47`'s 396,177.6420 — the generator emits
`hw/soc/pnr/config.json` **byte for byte**, die, core box, six macro
origins and two orientations, computed from the LEF without being told
what they should come out as **[fact]**.

### 6.3 What the run's own configuration says it changed

`hw/soc/pnr/runs/npu1/resolved.json` against
`hw/soc/pnr/runs/full3/resolved.json`, key by key:

```
  VERILOG_FILES          50 -> 56   (the six accelerator sources)
  VERILOG_INCLUDE_DIRS   +hw/rtl    (npu_regs.vh)
  PL_TARGET_DENSITY_PCT  40 -> 48
```

**[fact, and there is no fourth]** — the six macro `instances`
dictionaries compare **equal**, `DIE_AREA` and `CORE_AREA` are identical,
`SYNTH_HIERARCHY_MODE` is still `flatten`, `RUN_POST_GRT_DESIGN_REPAIR`
and `RUN_POST_GRT_RESIZER_TIMING` are both `True`, and all four
`*_VIOLATION_CORNERS` are `["*"]`.

**The derate is audited where it can be audited, not in
`resolved.json`.** `docs/31` sections 3.2 and 10.3 measured that the file
records the integer `5` whether or not the float was applied; this run's
flow log reads **`[INFO] Setting timing derate to: 5.0%`** **[fact]**,
which is the observable difference.

---

## 7. The run, stage by stage

LibreLane v3.0.5, OpenROAD 26Q1-2938-g0e2d771c5e, `ihp-sg13g2` at
`c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c`, rootless, on a shared
20-thread host. The netlist is `hw/soc/flow/syn_soc_top.sh`'s, for
`docs/47` section 6.2's reasons, which are unchanged: `deferred_flatten`
reintroduces the CHERIoT logic behind an unfolded constant and `flatten`
stops at `Checker.YosysUnmappedCells` on `soc_tmr_bank`'s
`keep_hierarchy`. **Neither of those is a property of the cell count, so
neither was re-measured.**

**It is two run directories and the reason is not `docs/47`'s.** That
document needed `full2` and `full3` because `RUN_POST_GRT_DESIGN_REPAIR`
and `RUN_POST_GRT_RESIZER_TIMING` default to `False` and it turned them
on mid-flow. `config.json` has carried both as `True` since, so **the two
runs here have identical configurations**: `npu1` carries the flow from
the netlist to post-GRT antenna repair, and `npu2` resumes from `npu1`'s
`35-openroad-repairantennas` state with
`-F OpenROAD.ResizerTimingPostGRT` and carries it to sign-off, because
the first attempt was interrupted in that step. **The split is an
accident of this session and not a variable**; section 15 says so again
where the runtimes are, because a reader comparing stage tables must
treat `npu1` + `npu2` as one flow. The comparisons below are against
`full2` up to global routing and against `full3` after it, which is the
same partition `docs/48`, `docs/49` and `docs/50` use.

### 7.1 Setup slack at `nom_slow_1p08V_125C`, stage by stage

| Stage | `full2` / `full3` | **`npu1` / `npu2`** | delta |
|---|---:|---:|---:|
| `OpenROAD.STAPrePNR`, no placement, overall group | −49.2780 | **−83.5941** | −34.3161 |
| `STAMidPNR`, post-global-placement | −75.1255 | **−137.5770** | −62.4515 |
| `STAMidPNR-1`, post-CTS, before the timing resizer | **−10.7556** | **−10.5783** | **+0.1773** |
| `STAMidPNR-2`, post-CTS resizer, placement parasitics | −0.1577 | **−0.0277** | +0.1300 |
| `STAMidPNR-3`, after global routing and post-GRT repair | −2.5778 | **−2.9441** | −0.3663 |
| **`STAPostPNR`, extracted parasitics, sign-off** | **−3.2029** | **−3.5789** | **−0.3760** |

**[fact, the `or_metrics_out.json` of each step in each run;
`STAMidPNR-3` is `full3`'s step 07 and not `full2`'s step 35, so both
sides of that row have had the post-GRT repair the other rows have not]**

> **THE LAST FOUR ROWS ARE THE ONES THAT MATTER AND NONE OF THEM MOVES
> BY MORE THAN 0.3760 ns.** `docs/44` section 5.2 measured this flow's
> resolution at about **0.4 ns**, and every document since has refused to
> claim a movement smaller than that. **A design with 57.6 % more
> standard-cell area, 70.6 % more flip-flops and 52.7 % more routed nets, in the
> same die, is not measurably slower from clock-tree synthesis onward.**
>
> **AND THE FIRST TWO ROWS ARE HUGE, WHICH IS THE POINT OF SHOWING
> THEM.** Before there is a clock tree the design is 34.3 ns worse; after
> the post-CTS resizer it is 0.13 ns better. **Almost all of the
> accelerator's arithmetic is inside paths the resizer fixes**, which is
> what a block built out of 8-bit LIF datapaths and queue pointers ought
> to look like and is not something this document assumed in advance. The
> `STAPrePNR` row is also dominated by the asynchronous reset-recovery
> group rather than by `clk_i` — `docs/47` section 5.3 measured
> `setup_async −49.2780` against `setup_sync +3.8711` on the same
> netlist — so its growth is 2,178 more reset sinks and should not be
> read as a datapath statement.

### 7.2 Placement

| | `full2` | **`npu1`** |
|---|---:|---:|
| standard-cell area at global placement, um2 | 396,287 | **624,575** |
| standard-cell utilization | **0.189429** | **0.298552** |
| instance utilization, macros included | 0.609182 | **0.661796** |
| global-placement HPWL, um | **2.100780e+06** | **2.630032e+06** |
| routability optimisation | *"Weighted routing congestion is lower than target … end routability optimization"* | **`GPL-0055` reverting to the minimum-congestion iteration; minimum observed 1.0112 against a target of 1.0100** |
| routability artificial inflation | 6,970.39 (+1.56 %) | **12,522.40 (+1.79 %)** |
| synthesised-cell span at CTS | **1,851.8 × 790.0** at (388.8, 582.1), 27,558 cells | **2,176.8 × 1,489.3** at (65.3, 412.0), 42,511 cells |
| cells / their own bounding box | **27.1 %** | **19.3 %** |

**[fact; the last row is arithmetic on two measured spans and two
measured cell areas]**

**Three readings, and the third is a correction to `docs/48`.**

**THE DESIGN LEFT THE CHANNEL.** `docs/59` section 5.1 measured 97.06 %
of the cells inside the 700.08 um channel, thirteen above it and no
flip-flops. Here the synthesised cells span **412.0 to 1,901.3 um in
y** — the channel is 687.18 to 1,387.26 — so the placer has used the full
height of the core, including the pockets beside both macro rows.
`docs/48` section 5 called that "exile" when FP-A did it and it was a
symptom there; here it is the design using room that FP-0 had and was not
using.

**THE PLACER IS NOW CONGESTION-LIMITED, WHICH IT WAS NOT.** In `full2`
the routability optimiser converged and stopped; here it exhausts its
iterations and reverts to the least-congested one it saw, at **1.0112
against a target of 1.0100** **[fact, `GPL-0050` against `GPL-0055` and
`GPL-0056`]**. **That is `docs/48` section 5's mechanism changing state.**
That document's second numbered finding was that *"the placer was never
density-constrained in FP-0, and that is why the sizing lever does not
exist"*. It is constrained now — marginally, at the very last iteration —
and section 9.1 is what follows.

**AND `docs/48`'s OWN PREDICTOR IS MEASURED WRONG.** That document
offered "cells / their own bounding box" as the mechanism by which the
two alternative floorplans were worse: **27.0 % in FP-0, 14.4 % in FP-A
and 11.9 % in FP-B**, both worse in timing. Here the same quantity falls
to **19.3 %** — between FP-A and FP-0 — and post-CTS slack **does not get
worse** (section 7.1). **A spread-out placement is not by itself a slow
one**, and that correlation should not be carried forward as a rule.

### 7.3 The clock tree, which counts the accelerator's flip-flops independently

| Clock net | `full2` sinks | **`npu1` sinks** | `full2` avg sink wire | **`npu1` avg sink wire** |
|---|---:|---:|---:|---:|
| `clk_i`, the six macros | 7 | **7** | 2,643.87 um | **2,629.78 um** |
| `clk_i_regs`, everything ungated | **762** | **2,940** | 778.10 um | **1,090.01 um** |
| `u_ibex.clk`, behind the gate | **2,323** | **2,323** | 996.17 um | **802.66 um** |

**[fact, `CTS-0010`, `CTS-0011` and `CTS-0101` in the two CTS logs]**

> **EVERY ONE OF THE 2,178 NEW FLIP-FLOPS IS ON THE UNGATED NET, AND
> CLOCK-TREE SYNTHESIS IS THE ONE THAT SAYS SO.** 762 + 2,323 = 3,085 and
> 2,940 + 2,323 = 5,263, exactly the two synthesis flip-flop counts
> **[fact]**. `u_ibex.clk`'s sink count does not move by one, because
> `sg13g2_lgcp_1` is bound inside `ibex_top` and gates Ibex and nothing
> else.
>
> **`docs/57` section 9 measured the consequence in milliwatts — the
> accelerator's idle power ratio is 5.588x and it has no gate — from an
> unrouted netlist, and called that projection "the weakest number in
> this document".** This is the same fact, in the layout, counted by a
> different tool: **the ungated population goes from 24.7 % of the
> design's flip-flops to 55.9 %** **[estimate, arithmetic on four
> measured sink counts]**. It does not make the power projection strong;
> it removes any doubt about the mechanism behind it.

**And `u_ibex.clk`'s average sink wire length went DOWN, 996.17 → 802.66
um.** `docs/47` section 8.4 offered that figure as evidence that the
design had been placed too far apart. With 57.6 % more cell area in the
same box, the tree over Ibex's own 2,323 flip-flops got **19.4 %
shorter** **[fact]** — because the placer had a reason to keep them
together. `clk_i_regs` went the other way, 778.10 → 1,090.01, and it is
carrying 2,178 more sinks.

---

## 8. Sign-off

### 8.1 The three-corner block

`OpenROAD.STAPostPNR`, three corners, **extracted parasitics** from
`OpenROAD.RCX`, 5 % derate applied as a float, 0.25 ns of clock
uncertainty, 20 ns. Slack in ns.

| Corner | setup ws | setup vio | setup TNS | hold ws | hold vio | max cap | max slew |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`nom_slow_1p08V_125C`** | **−3.5789** | **2,175** | **−2,981.09** | +0.6034 | **0** | **15** | **29** |
| `nom_typ_1p20V_25C` | +5.0703 | 0 | 0.0000 | +0.2854 | **0** | **15** | **8** |
| `nom_fast_1p32V_m40C` | +10.1244 | 0 | 0.0000 | **+0.0981** | **0** | **15** | **6** |

**[fact, `hw/soc/pnr/runs/npu2/14-openroad-stapostpnr/summary.rpt`]**

Against `docs/47`'s, criterion by criterion:

| | `docs/47`, `full3` | **`npu2`** | delta |
|---|---:|---:|---:|
| **setup worst slack, slow** | **−3.2029** | **−3.5789** | **−0.3760** |
| violating setup endpoints | 2,003 | **2,175** | +172 |
| **setup TNS, slow** | −2,075.11 | **−2,981.09** | **−905.98, 43.7 % worse** |
| setup worst slack, typ | +5.7231 | +5.0703 | −0.6528 |
| setup worst slack, fast | +10.6634 | +10.1244 | −0.5390 |
| **hold worst slack, fast** | **−0.2015** | **+0.0981** | **+0.2996** |
| **hold violations, all corners** | **3** | **0** | **−3** |
| max slew, slow / typ / fast | 14 / 0 / 1 | **29 / 8 / 6** | worse at all three |
| max cap, slow / typ / fast | 10 / 10 / 12 | **15 / 15 / 15** | worse at all three |

**[fact for both columns; the deltas are differences of measurements]**

> **THE SETUP NUMBER DID NOT MOVE AND THIS DOCUMENT DOES NOT CLAIM THAT
> IT DID, IN EITHER DIRECTION.** −0.3760 ns is **inside `docs/44`
> section 5.2's measured 0.4 ns of instrument resolution**, and
> `docs/49` section 6.1 refused to claim +0.1191 ns on exactly this
> ground. **What may be said is the negative: adding 57.6 % of standard-cell
> area, 70.6 % of the flip-flops and 52.7 % of the routed nets to this design,
> in the same die, did not measurably move its worst setup path.**
>
> **THE TNS DID MOVE, BY 905.98 ns, AND THAT IS OUTSIDE ANY NOISE
> FLOOR.** Section 9.3 is where it went, and it is not the accelerator:
> **2,133 of the 2,175 violating endpoints launch from two bits of one
> register-file read address**, and 21 launch from anywhere inside
> `u_npu`.
>
> **AND HOLD CLOSED ON ITS OWN.** `docs/47` failed hold at the fast
> corner on 3 endpoints; `docs/48` needed a max-capacitance constraint to
> close it and paid −1.65 ns of setup for the package. **Here it closes
> with no key changed**, at **+0.0981 ns**, through the identical
> `HOLD_VIOLATION_CORNERS = ["*"]` binding under which `full3` failed
> (section 10). The mechanism is not claimed: the netlist, the
> placement, the clock tree and the routing all changed at once, and
> `docs/49` section 6.3 refused to attribute the same movement for the
> same reason.

### 8.2 What did close, and it is not a short list

| Check | `full3` | **`npu2`** |
|---|---|---|
| Detailed-routing DRC | **0** after 17 reported iterations | **0** after 24 **[fact]** |
| Disconnected pins | 0 | **0** |
| Power-grid violations | 0 on VPWR and VGND | **0 on both** |
| Antenna, post-route | 1 violating net, 1 pin | **1 violating net, 1 pin** |
| Illegal overlaps | 0 | **0** |
| Nets routed | 37,156 signal + 2 special | **56,747 + 2** |
| Vias | 286,273, all single-cut | **422,780, all single-cut** |
| Routed wirelength | 3,095,532 um | **4,049,894 um**, +30.8 % |
| **Longest net** | **2,332.02 um** | **2,315.01 um** |
| Hold, all three corners | 3 violations at fast | **0 at all three** |

**[fact, the two `final/metrics.json`]**

**The detailed router's first count is not the interesting one and its
last is.** It starts at **32,412 violations** against `full3`'s 22,887
and reaches **0**, on a design with 52.7 % more routed nets in the same routing
resource **[fact, the `DRT-0199` sequences]**. `docs/48` measured the
other outcome on FP-A: a floorplan whose global router **had not
produced a single line of log after 33 minutes**, twice. This one
global-routes in **33.4 seconds** and detailed-routes in **49 minutes
25 seconds**.

**And the longest net got SHORTER.** `docs/47` section 8.4 offered
`route__wirelength__max = 2,332.02 um` as *"the sharpest piece of
evidence"* that the floorplan had spread the design out. With 57.6 %
more cell area in the same die the longest net is **2,315.01 um**
**[fact]** — 0.7 % shorter. `docs/48` section 5's fourth numbered
finding already said that number describes the die rather than the
placement; this is a second measurement of the same thing.

### 8.3 The cell census, and the die

| | `full3` | **`npu2`** | ratio |
|---|---:|---:|---:|
| total instances, fill included | 169,747 | **175,185** | 1.032x |
| standard cells, fill excluded | 37,623 | **57,399** | **1.526x** |
| **sequential cells** | **3,085** | **5,263** | **1.706x** |
| timing-repair buffers | 7,910 | **11,454** | 1.448x |
| clock buffers | 383 | **595** | 1.554x |
| buffers and inverters, all classes | 11,380 | **16,412** | 1.442x |
| integrated clock gates | **1** | **1** | — |
| antenna cells | 606 | **668** | |
| antenna diodes inserted | 514 | **501** | |
| **fill and decap** | **132,118** | **117,780** | **0.892x** |
| standard-cell area placed, um2 | 531,370.63 | **818,684.50** | **1.541x** |
| macro area, um2 | 2,246,899.85 | **2,246,899.85** | **1.000x** |
| **die area, um2** | **4,786,287.41** | **4,786,287.41** | **1.000x** |
| channel density | **34.84 %** | **50.44 %** | |
| cells above the channel | **13** | **2,485** | |
| memory / logic, placed | 4.2285x | **2.7445x** | |
| transistors on this die | 4,223,084 | **4,352,524** | 1.031x |
| of which SRAM bitcells and macro periphery | **87.5 %** | **84.9 %** | |

**[fact, `floorplan_map.py --run hw/soc/pnr/runs/npu2 --no-write`, whose
eight geometry self-checks and ten cross-checks against this run's own
`metrics.json` all pass]**

**The fill count went DOWN and that is the whole story of the
floorplan.** 132,118 filler cells became **117,780**, because 287,313
um2 more of real logic is standing where filler used to be **[fact]**.
The die is the same die to the last database unit, the macros have not
moved, and **the design paid for the accelerator in filler**.

**And the transistor count barely moved**, because 84.9 % of this die is
still SRAM bitcell: 4.22 million to **4.35 million**, +3.1 %, for +57.6 %
of standard-cell area **[fact]**. `docs/59` section 12's framing — *"one
very large memory, one small strip of logic"* — is still what this chip
looks like, but the strip is no longer a strip: it fills the channel and
2,485 cells of it now sit above the memories where thirteen did.

### 8.4 No frequency

`docs/53` section 9.2 refused to publish one on three grounds and
`docs/05` section 4 rule 5 binds every external claim. **None of the
three grounds moved and this document adds a fourth.** The layout fails
setup, max slew and max cap; it has no DRC, LVS or XOR result; the
workload that would justify a target has still not been sized against a
mission; and **the netlist has still never been simulated**, so nothing
has executed the design these numbers describe.

**What may be said is the slack against the constraint**: this design
misses a **20 ns** period by **3.5789 ns at the slow corner on 2,175 of
its endpoints**, and it is not measurably further from that constraint
than the design without its accelerator was.

---

## 9. The four remedies, re-asked

`docs/47` to `docs/50` measured four things against a design that no
longer exists. **Each is re-asked here, and the answers are not the
same shape.**

| | What it was | What it is now |
|---|---|---|
| **`docs/48`'s floorplan** | FP-0 optimal; two alternatives worse | **result untouched, mechanism gone, and the untested direction has changed sign.** 9.1 |
| **`docs/48`'s two spent flow settings** | `deferred_flatten` and both `RUN_POST_GRT_*`, worth 0 ns each | **still spent, and their reasons are structural rather than numerical, so they are inherited rather than re-measured.** 9.2 |
| **`docs/49`'s `SYNPRE`** | acts on a cone disjoint from the binding path; *"the most a perfect, free `SYNPRE` could do to the worst slack is nothing"* | **REVERSED BY MEASUREMENT, on the reversal condition `docs/49` itself wrote.** 9.3 |
| **`docs/50`'s read register** | +0.7772 ns, by emptying a 444-endpoint macro launch group; costs 21 % of wall-clock | **moot for the worst slack — the group is already down to 9 — and its price is now unmeasured.** 9.4 |

### 9.1 `docs/48`'s floorplan: the result stands, the mechanism does not, and the untested direction has reversed

**What survives.** `docs/48`'s headline — *"Was the floorplan the
problem? No, and this is the clearest negative result in the SoC
record"* — is **strengthened, not weakened**. This document is the
hardest test that argument has had: the same die, the same channel, the
same six macro origins, **1.5761 times the cell area**, and the design
places, clock-trees, routes to **0 DRC** and lands within the noise
floor of `docs/47`'s slack. **The floorplan cost of the accelerator is
zero square micrometres** and section 6.2's experiment is what
established it.

**What does not survive is the argument underneath it.** `docs/48`
section 5 gave two mechanisms and this run contradicts both:

1. *"THE PLACER WAS NEVER DENSITY-CONSTRAINED IN FP-0, AND THAT IS WHY
   THE SIZING LEVER DOES NOT EXIST."* It is constrained now. The
   routability optimiser in `full2` **converged and stopped**
   (`GPL-0050`); here it **exhausted its iterations and reverted to the
   least-congested one it had seen**, at a weighted congestion of
   **1.0112 against a target of 1.0100** **[fact, `GPL-0055` and
   `GPL-0056`]**. That is marginal and it is a change of state.
2. *"SHRINKING THE DIE DID NOT COMPACT THE LOGIC, IT SPREAD IT"*, with
   **cells / their own bounding box** offered as the measure — 27.0 % in
   FP-0 against 14.4 % and 11.9 % in the two worse floorplans. **Here
   that number falls to 19.3 %, between the two, and the design is not
   slower** (section 7.1). **The correlation is measured wrong and
   should not be carried forward as a predictor.**

**And the direction nobody has tested has reversed.** `docs/48` measured
two floorplans **smaller** than FP-0 and both were worse; it never
measured one larger, because at 18.9 % utilization there was no reason
to. **The channel is now 50.44 % dense** — `floorplan_map.py` on this
run's own DEF, against `docs/59`'s **34.84 %** on `full3` **[fact for
both]** — and 2,485 cells sit above it where thirteen did.
**A taller channel is now the one floorplan question in this record
that has never been asked**, and section 18 ranks it.

**What was NOT measured and must not be inferred.** FP-A and FP-B were
**not** re-run against this design. `docs/48`'s finding that they are
worse is a finding about a 396,178 um2 cell population, and **this
document says nothing about what a 624,430 um2 population would do in
them.** It is plausible that a tight channel is now less bad, because
the exile mechanism `docs/48` diagnosed was cells being pushed into the
ROM pockets and this design **fills those pockets anyway** — 2,062 cells
to the right of the macros against 963 **[fact]**. Plausible is not
measured.

### 9.2 `docs/48`'s two spent settings: still spent, and inherited on structural grounds

`SYNTH_HIERARCHY_MODE: deferred_flatten` and both `RUN_POST_GRT_*` keys.

- **Both post-GRT keys are `True` in this run's `resolved.json`**
  **[fact]**, so their value is already inside every number above, as it
  was inside `docs/47`'s. **Remaining value: 0 ns**, unchanged and not
  re-measurable — there is nothing to turn on.
- **`deferred_flatten` is rejected on the same structural grounds and
  those grounds are not a function of cell count.** `soc_top.v` drives
  `ibex_top`'s `cheriot_enable_i` with a constant; a mode that optimises
  with the module boundary intact does not fold it, and `docs/44`
  section 5.1 is the whole subject of what that constant does to a
  timing report. The alternative, `flatten`, still stops at
  `Checker.YosysUnmappedCells` on `soc_tmr_bank`'s `keep_hierarchy`,
  which `docs/41` requires and LibreLane cannot release after technology
  mapping. **Both mechanisms are properties of the flow and the RTL, not
  of the design's size, so they are inherited and not re-run.**

> **ONE FIGURE IS SCOPED RATHER THAN INHERITED.** `docs/47` section 6.2
> measured `deferred_flatten` as **13.84 ns slower** and 32 % larger on
> the design of the day. **That number is for a `soc_top` with no
> accelerator in it and this document does not carry it forward** —
> the reason for the choice survives, the price tag does not.

### 9.3 `docs/49`'s `SYNPRE`: the reversal condition it wrote for itself is now met

`docs/49` section 3.2 is the sharpest negative result in the physical
record and it rests entirely on **which endpoints violate**:

> The 444 endpoints behind the macros have a worst slack of −3.2029 and
> the 1,559 `SYNPRE` can reach have −2.0227 — **so the most a perfect,
> free `SYNPRE` could do to the worst slack is nothing.**

`hw/soc/pnr/violator_census.py` on this run, against this run's own
netlist:

| Launch point | `full3` | **`npu2`** |
|---|---:|---:|
| `…register_file_i.raddr_b_i[3]` | **0** | **1,718**, worst **−3.5789** |
| `…register_file_i.raddr_b_i[2]` | 0 | **415**, worst −3.5530 |
| `…register_file_i.raddr_a_i[2]` | 868, worst −2.0227 | 0 |
| `…register_file_i.raddr_a_i[0]` | 509, worst −1.7387 | 0 |
| `…register_file_i.raddr_b_i[1]` | 181, worst −1.5937 | 0 |
| **`u_ram…u_b0/A_DOUT[15, 13, 1]`** | **444**, worst **−3.2029** | **0** |
| `u_ram…u_b2/A_DOUT[1]` | 0 | **9**, worst −2.5276 |
| **`u_npu.u_node0.u_lif.ev_axon_r[1]`** | — | **21**, worst **−0.3690** |
| `u_busstat` internal | 1 | 12, worst −1.3924 |
| **total** | **2,003** | **2,175** |

**[fact, both columns from the same script against each run's own
netlist; the `full3` column reproduces `docs/49` section 3.1]**

And the worst path itself, resolved against the netlist:

```
Startpoint  _75872_  = u_ibex.gen_regfile_ff.register_file_i.raddr_b_i[3]
Endpoint    _73439_  = u_ibex…g_rf_flops[9].g_chk.rf_chk_q[2]
```

**[fact, `npu2/14-openroad-stapostpnr/nom_slow_1p08V_125C/max.rpt`
resolved with `violator_census.py`'s own netlist loader]**

> **THE BINDING PATH IS NOW A REGISTER-FILE READ ADDRESS THROUGH THE
> 32-WAY READ MULTIPLEXER, WHICH IS EXACTLY THE CONE `SYNPRE`
> RESTRUCTURES.** `docs/49` section 14 wrote its own reversal condition
> and it is worth quoting in full because it has come true:
>
> > **The reversal condition is specific and it is item 1**: if the
> > memory read is registered and the binding path becomes the
> > read-address group, `SYNPRE` acts directly on the new worst path and
> > this measurement has to be redone.
>
> **The second clause is true and the first is not.** Nothing registered
> the memory read here. **The macro launch group emptied on its own** —
> 444 endpoints to 9 — for the reason `docs/50` section 6.3 item 2
> already identified: a violating endpoint is reported once, under its
> **worst** launch, and the read-address cone got worse than the macro
> read arc (−2.0227 to −3.5789) and swallowed it.
>
> **SO `docs/49`'s CONCLUSION IS NOW SCOPED TO A DESIGN THAT NO LONGER
> EXISTS, AND `SYNPRE` HAS TO BE RE-MEASURED.** Its area price also
> changes: **+27,237.7728 um2 was +6.9 % of `docs/47`'s standard cells
> and is +4.4 % of this design's** **[estimate, arithmetic on a measured
> area]**. `docs/49` section 5 measured it worth **+3.4641 ns at
> post-CTS** on the same structure — *"the largest single-change
> improvement measured on this design"* — before routing gave it back.
> **Nothing here re-measures it and this document does not claim it
> would work.** Section 18 item 2.

**And the accelerator is not the problem, which is the other half of
this census.** `u_npu` launches **21 of 2,175** violating endpoints with
a worst slack of **−0.3690**, and captures **74 of 2,175** with a worst
of −2.6354 **[fact]**. A block that is 57.6 % of the standard-cell area
carries **1.0 % of the violating launches**.

### 9.4 `docs/50`'s read register: moot for the worst slack, and its price is now unmeasured

`docs/50` measured **+0.7772 ns** — the only setup improvement in
`docs/47` to `docs/50` that survived the noise floor — and its mechanism
was named precisely: *"The macro group is not smaller. It is empty."*
It removed the 444 endpoints launched by `u_ram…u_b0/A_DOUT`.

**That group is now 9 endpoints, and nothing built here removed it.**
So the change cannot buy what it bought: **there are 9 endpoints left to
empty and their worst slack is −2.5276 against the binding path's
−3.5789**, so removing every one of them moves the worst slack by
nothing. **This is `docs/49`'s own argument, in the same shape, applied
to `docs/50`'s remedy.**

**Two things follow that are not "so it is dead".**

1. **The memory interface has moved from the launch side to the capture
   side, not out of the population.** 303 of the 2,175 endpoints are
   captured at an SRAM macro's own input pins — `A_ADDR`, `A_BM`,
   `A_DIN` — with a worst slack of **−2.9768**, against 496 at −1.8718
   in `full3` **[fact]**. Fewer endpoints, **1.1 ns worse**. A register
   on the read return does nothing for those; they are paths *into* the
   macro.
2. **Its cost has to be re-measured and must not be inherited.**
   `docs/50` section 7 priced it at **+46,789 cycles, +25.23 %** on the
   bring-up program and concluded that the part would have to close at
   53.97 MHz to break even. **That program ran on a design with no
   accelerator in it.** The whole-SoC program now spends **3,594 cycles
   per inference polling a slave that takes 176 cycles to answer**
   (`docs/57` section 10.1), and `docs/57` measured that during that
   window `u_ram` is selected on **0.31 %** of cycles. **An extra cycle
   of memory read latency is charged differently against a workload that
   is mostly waiting for the NPU**, in the cheap direction, and nobody
   has measured by how much. Section 18.

### 9.5 A fifth lever, which `docs/48` found and this run makes more attractive

Not one of the four, and it changed too. `docs/48` sections 6 and 7
measured a **`set_max_capacitance` of 0.0648 pF** end to end: **worth
−1.65 ns of setup at sign-off**, and it **closed hold and closed max
slew completely** — 14 slow-corner and 1 fast-corner slew violations to
**0 at all three corners**.

| | `docs/47` | `docs/48`'s `cap2` | **`npu2`** |
|---|---|---|---|
| hold violations | **3** at fast | **0** | **0** |
| max slew, slow / typ / fast | 14 / 0 / 1 | **0 / 0 / 0** | **29 / 8 / 6** |

**[fact, three runs]**

> **HALF OF WHAT THAT CONSTRAINT BOUGHT HAS ARRIVED FOR FREE AND THE
> OTHER HALF HAS GOT WORSE.** Hold closes here with no key changed, so
> the constraint is no longer needed for it. Max slew is **twice as bad
> at the slow corner and has appeared at the typical corner, where
> `docs/47` had none** — so the constraint's remaining value is larger
> than it was. **Its setup price of −1.65 ns is a measurement on a
> design that no longer exists and is not carried forward.** Section 18
> item 3.

---

## 10. The checkers, re-audited

`hw/openlane/checker_audit.py`, which recomputes from the installed
LibreLane's own step classes and this run's own `resolved.json` whether
each checker **can** fail. `hw/openlane/` is read and not written.

```
    registered Checker.* steps: 21
    of which the Classic flow runs: 19

GATES  Checker.SetupViolations   [corners] SETUP_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, violating nom_slow_1p08V_125C
GATES  Checker.HoldViolations    [corners] HOLD_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, all 0
GATES  Checker.MaxSlewViolations [corners] MAX_SLEW_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, violating all three
GATES  Checker.MaxCapViolations  [corners] MAX_CAP_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, violating all three

    17 of 19 in-flow checkers gate fully.
    NOT gating in full: Checker.LintWarnings, Checker.WireLength
    registered but not in the Classic flow: Checker.KLayoutAntenna,
                                            Checker.KLayoutDensity
```

**[fact, `checker_audit.py hw/soc/pnr/runs/npu2`]**

**Seventeen of nineteen, the same seventeen and the same two**, as
`docs/47` section 7.3, `docs/48` section 9, `docs/49` section 10 and
`docs/50` section 9. The two that do not gate are the two those
documents name and neither is repaired here: `WIRE_LENGTH_THRESHOLD` is
unset in both PDKs, and `ERROR_ON_LINTER_WARNINGS` is a policy with a
named key.

> **THE ONE LINE THAT MATTERS IS `Checker.HoldViolations`: "corners
> measured 3, all 0".** `docs/50` section 9 makes the same point about
> the same checker and it is worth making again, because **a criterion
> that goes from failing to passing is exactly where a checker that
> stopped looking would hide.** It examined three corners here and it
> examined three corners in `full3`, where it reported the fast corner
> violating and stopped the flow. **The gate did not move; the design
> did.**

**And the flow still exits non-zero, naming every failing corner**:

```
One or more deferred errors were encountered:
Setup violations found in the following corners:
* nom_slow_1p08V_125C
Max Slew violations found in the following corners:
* nom_fast_1p32V_m40C
* nom_slow_1p08V_125C
* nom_typ_1p20V_25C
Max Cap violations found in the following corners:
* nom_fast_1p32V_m40C
* nom_slow_1p08V_125C
* nom_typ_1p20V_25C
```

**[fact, the flow log]** — three criteria named where `docs/47` named
four, and **hold is the one missing.**

**The two metrics nothing judges are read out here rather than left in a
file**, as `docs/47` section 8.6 did:

- **`design__max_fanout_violation__count` = 477**, against `docs/47`'s
  293 **[fact]**. There is **no max-fanout checker step in the Classic
  flow at all**, and `MAX_FANOUT_CONSTRAINT` is the PDK's 10 against the
  library's declared `default_max_fanout : 8`.
- **`design__violations` = 0 and `flow__errors__count` = 0** in the
  `final/metrics.json` of a run that fails setup, max slew and max cap
  **[fact]**. **The aggregate metric still does not aggregate** —
  `docs/23` section 3.2's finding, reproduced a fifth time — and the
  only reason this run is not reported clean is that four checkers were
  bound to `["*"]` before it started.
- **`route__wirelength__max` = 2,315.01 um** and `Checker.WireLength`
  skipped, because the threshold is unset in both PDKs.

**One more that nothing judges and that grew**:
`timing__unannotated_net__count` is **398 against `full3`'s 200**
**[fact]** — nets the extractor gave no parasitic. The flow filters them
out of the STA and reports the count; nothing gates it, and this
document did not investigate which nets they are.

---

## 11. The second clock gate, priced rather than built

`docs/57` section 16 item 2 named it and this document's section 7.3 is
the layout-level evidence for it: **2,940 of 5,263 flip-flops now have a
clock nothing turns off**, against 762 of 3,085 before.

**What it would cost.**

| | |
|---|---|
| **area** | One `sg13g2_lgcp_1` is **27.216 um2** **[fact, the Liberty, and the run's own `design__instance__area__class:clock_gate_cell` reports exactly that for the one gate in the design]** — **0.0044 % of this design's standard-cell area** per domain. The area is not the cost. |
| **the enable** | For the accelerator it is cheaper than for the peripherals and `soc_npu.v` already has the terms: the block is idle when its two AER queues are empty, no APB access is outstanding and `pilot_top` is not busy. Unlike the fabric case it does **not** need `core_sleep_o`. **[estimate — the signals exist; nothing here has built or timed the enable]** |
| **the real cost, and it has already failed once here** | `docs/57` section 16 states it: `soc_bus.v`'s no-starvation property **F9** and its response-ownership queues assume every slave answers, and a slave whose clock is off does not. **That proof has already broken in this repository for a related reason**: `docs/50` section 8.1 found `hw/soc/formal/soc_bus.sby` **failing since `docs/47`**, undetected across three documents, because that document added `issue_en` — one flop that keeps the request path shut for a cycle after reset — and F9's two-cycle fairness bound had no room for it. The counterexample was at depth 3. **A gated slave is the same shape of change and a larger one**, and it is a formal re-proof and a fabric change, not a gate. |
| **what breaks that a proof would not catch** | The NPU is an **interrupt source** (`irq_fast[SOC_IRQLINE_NPUCFG]`) and a **BUSSTAT source** on three lines (`npu_cor_ev`, `npu_det_ev`, `npu_tmr_ev`). A gated accelerator cannot raise any of them while gated, so the enable has to include "no event pending to report", which is a fourth term and the one most likely to be got wrong. **[estimate]** |

> **THE RECOMMENDATION IS NOT TO BUILD IT NOW.** The shuttle closes
> 2026-09-21. Re-proving `soc_bus.sby` against a slave that may be asleep
> is a formal job whose last relative took three documents to be noticed
> failing, and this document has just moved every physical number the
> project reports. **Section 18 ranks it, with the condition that
> `soc_bus.sby` is green at HEAD before anything gates a slave.**

---

## 12. `fi_core.sh`

`docs/57` section 3.1 found that it had not elaborated since `docs/51`
and deliberately did not fix it, because *"a repair to the
fault-injection flow is a change to the instrument three campaigns are
reported from and belongs in its own change with its own re-run"*.

**It was cheap and it is done.** Six sources and one include path,
copied from `sim_soc.sh` with its rule about the SECDED codec — there is
one codec in this repository, `ibex_sources()` emits it in the `secded`
configuration, so this list emits it only in the other one.

| | Published | Rebuilt and re-run here |
|---|---|---|
| `FI_WORKLOAD=workload`, clean run | **18,682 cycles, sig `9c07ef12`** (`docs/42`, `docs/43`, `docs/44`) | **18,682, `9c07ef12`** **[fact]** |
| `FI_WORKLOAD=supervisor`, clean run | `sig = 216f8ce6`, window 9,376..67,296 (`docs/46`, `docs/57`) | **`216f8ce6`, 9,376..67,296**, 69,085 cycles **[fact]** |
| the `SOC_MEM_RDREG` arm check | `g_rd1` at 0, and both arms never present | **`g_rd1`, and the check still fires** **[fact]** |

> **WHAT THIS DOES NOT DO IS RE-RUN THE CAMPAIGNS, AND THAT IS SAID HERE
> RATHER THAN LEFT TO BE ASSUMED.** `docs/42`, `docs/43` and `docs/46`
> report outcome distributions over hundreds of injections into a design
> that now has **2,178 more flip-flops and a sixth fabric port in it**.
> What is restored is that those campaigns **can** be rebuilt. Whether
> they produce the same distribution is a separate measurement with its
> own cost, and nothing here has taken it. The two clean runs above are
> the check that the instrument is the same instrument, not that the
> results are the same results.
>
> **And the site table is unchanged**: `hw/soc/fi/targets.py` generates
> `fi_targets.vh` into the output directory and its sites are all inside
> Ibex and the fabric. **No campaign in this repository injects into the
> accelerator through `fi_core.sh`** — `flow/fi_npu.sh` is the one that
> does, and `docs/52`, `docs/55` and `docs/56` are its documents.

---

## 13. Corrections, and what is now scoped to a design that no longer exists

**The blanket statement first, because it is the point of the
document.**

> **EVERY AREA, TIMING AND POWER FIGURE IN `docs/45`, `docs/47`,
> `docs/48`, `docs/49`, `docs/50`, `docs/53`, `docs/59` AND `docs/60` IS
> A FIGURE FOR A `soc_top` WITH NO ACCELERATOR IN IT.** None of them is
> an error of measurement and every one of them was correct when it was
> taken. **They are now scoped**: they describe a design that has
> 27,565 cells where the design has 42,518, and this document is the
> replacement for the physical half of them. Where a conclusion depends
> on the *shape* of the design rather than on its size — `docs/47`
> section 6.2's rejection of both LibreLane hierarchy modes, `docs/48`
> section 3's two spent settings, `docs/59` section 6's refusal to draw a
> block map — it survives, and section 9 says which.

Then the specific ones.

1. **`docs/47` section 6.1's "18.9 %" standard cells over placeable
   area is 29.85 % for this design** **[fact]**, and `docs/59` section
   5.2's channel density of **34.84 % is 50.44 %** **[fact,
   `floorplan_map.py` on this run]**.
2. **`docs/59` section 5.1's "thirteen cells sit above the channel, and
   not one flip-flop" is 2,485 cells and 26,290.66 um2** **[fact]**.
   *"The upper half of the die outside the macros is, for practical
   purposes, empty"* was true of `full3` and is not true here. Below the
   channel goes 1,094 → **3,221** and the strip right of the macros
   963 → **2,062**.
3. **`docs/59` section 7's "the neuromorphic accelerator this SoC exists
   for has never been placed" is no longer true.** It is placed, routed
   and extracted in `hw/soc/pnr/runs/npu2`. **`docs/img/soc-floorplan-map.svg`
   and `.json` were deliberately NOT regenerated**: they are `docs/59`'s
   artefacts and they are labelled as `full3`'s, and replacing them
   silently would put a new die under an old document's argument.
   Section 18 item 6.
4. **`docs/47` section 1's "the memory is 4.29 times the logic" —
   corrected once by `docs/59` section 11 to 4.2285 against placed cells
   — is 2.7445 for this design** **[fact, `floorplan_map.py`]**. The
   transistor count goes **4,223,084 → 4,352,524** and the macros' share
   of it **87.5 % → 84.9 %** **[fact]**.
5. **`docs/48` section 5's "cells / their own bounding box" is not a
   predictor of timing.** Section 7.2.
6. **`docs/48` section 5's "the placer was never density-constrained in
   FP-0" no longer holds.** Section 9.1.
7. **`docs/49` section 3.2's disjoint-cone result is reversed for this
   design, on `docs/49` section 14's own stated condition.** Section 9.3.
   **This is not an error in `docs/49`**, which measured what it
   measured and wrote down what would falsify it.
8. **`docs/50` section 6.2's +0.7772 ns is not available on this
   design** and its 25.23 % cycle cost is unmeasured here. Section 9.4.
9. **`docs/48` section 7.3's max-capacitance package is worth less on
   one axis and more on the other.** Section 9.5.
10. **`docs/57` section 9's mechanism is confirmed by a second
    instrument and its number is not.** The clock-tree sink counts —
    `clk_i_regs` **762 → 2,940** with `u_ibex.clk` unchanged at 2,323
    **[fact]** — are an independent confirmation that the accelerator's
    flip-flops are ungated. **The 5.588x idle power ratio and the
    projected 31.0 mW remain [estimate] and remain unmeasured**, because
    no power was measured here. Section 18 item 1.
11. **`docs/57` section 3.1's `fi_core.sh` defect is closed** and
    `docs/57` section 12 item 9's *"the reproduction sections of
    `docs/42`, `docs/43` and `docs/46` are stale"* is closed **as far as
    the build goes and no further**. Section 12.
12. **`docs/60-soc-datasheet.md`'s physical section is superseded.**
    Its revision history already carries the caveat — *"Physical and
    timing data are from the `full3` place-and-route run of `docs/47`,
    which does not contain the NPU subsystem"* — and section 8 here is
    the data that removes it. **The datasheet is not edited by this
    document**; it is a separate deliverable with its own rules and
    `docs/05` section 4 rule 5 applies to it more tightly than to
    anything else in the corpus.
13. **`docs/47` section 8.4's reading of the 996.17 um average clock
    sink wire length gets a second data point rather than a
    correction.** That figure was offered as evidence the design had
    been placed too far apart; filling the same box with 57.6 % more
    cell area takes it to **802.66 um** **[fact]**, which is consistent
    with that reading and is the first measurement of it.

---

## 14. What this does NOT cover

Stated at length, because this document moves every physical number the
project has and a moved number travels further than its caveats.

- **THIS IS NOT A PHYSICAL SIGN-OFF AND IT HAS NO DRC, LVS OR XOR
  RESULT.** `RUN_MAGIC_DRC`, `RUN_KLAYOUT_DRC`, `RUN_KLAYOUT_XOR` and
  `RUN_LVS` are all **0** in this run's `resolved.json` **[fact]**, and
  the run's own log says so on the way out. **The reason is a property
  of the PDK and not of this design and it has not moved**: `docs/12`
  sections 7.5 and 8 measured **1,106,478 Magic DRC errors, 2,316
  KLayout DRC errors and 359 Netgen LVS errors over ONE RM_IHPSG13
  macro**, every one of them inside vendor geometry this project does not
  author, and recorded **NO-GO on RM_IHPSG13 integration**;
  `docs/54` section 7 examined the KLayout half in detail and the exit
  stayed shut, because the deck that returns 0 is the PDK's *unverified*
  residual set. **Six macros' worth of that is not a result and was not
  re-derived.** Nothing on this die has ever been checked for
  manufacturability, and six rectangles on it are known to fail the
  checker that would check them.
- **NO FREQUENCY IS PUBLISHED AND NONE MAY BE DERIVED FROM THIS
  DOCUMENT.** `docs/53` section 9.2 refused one on three grounds and
  `docs/05` section 4 rule 5 binds. Slack against the **20 ns**
  constraint is what is reported.
- **NOTHING HERE WAS SIMULATED.** `docs/49` section 12's *"nothing has
  ever simulated `soc_top`'s netlist"* is unchanged, and it is now a
  larger gap: the netlist contains the accelerator and the accelerator's
  correctness evidence is all at RTL. **The macros are blackboxes and
  the ROM has no contents**, which is the same obstacle `docs/45`
  section 9 item 5 and `docs/47` section 11 item 2 both name.
- **NO POWER NUMBER IS MEASURED HERE.** `docs/57`'s activity-annotated
  figures are for the `full3` netlist. This run's netlist and SPEF make
  that measurement possible for the first time on a design that can
  perform an inference, and **it was not taken** — it needs the VCD
  pipeline of `docs/57` section 15 re-run against this netlist, and that
  is section 18 item 1. **`docs/57` section 9's projected 49.7 mW busy
  and 31.0 mW idle remain [estimate] and remain the weakest numbers in
  that document.**
- **ONE FLOORPLAN, ONE ARRANGEMENT, ONE DENSITY, ONE PERIOD.** FP-A and
  FP-B were **not** re-run against this design and this document says
  nothing about what they would do. `docs/48`'s conclusion about them is
  discussed in section 9.1 and is **neither confirmed nor refuted**
  here.
- **THE CAMPAIGNS ARE NOT RE-RUN.** Section 12. `docs/42`, `docs/43`,
  `docs/46`, `docs/52`, `docs/55` and `docs/56` all report outcome
  distributions measured against a design that has since changed, and
  restoring the build is not re-measuring the result.
- **NO PER-BLOCK ATTRIBUTION IS POSSIBLE IN THIS DATABASE EITHER.**
  42,511 of 42,518 synthesised cells are anonymous **[fact]**;
  `docs/59` section 6's refusal to draw a per-block region map stands
  unchanged, and so do its three routes out of it, none of which was
  taken.
- **THE FAST CORNER'S MACRO LIBERTY IS CHARACTERISED AT −55 C WHERE THE
  STANDARD CELLS ARE AT −40 C.** `docs/47` section 9's caveat, unchanged
  and applying to every fast-corner figure below.
- **`docs/50`'s BYTE-IDENTICAL CONTROL CANNOT BE RE-DERIVED FROM HEAD.**
  Section 5.1.
- **THE SUPERVISOR'S CYCLE COUNT MOVED BY 21 AND THIS DOCUMENT DID NOT
  ISOLATE IT.** Section 2.

---

## 15. Cost

Quoted as costs and not as benchmarks, on a shared 20-thread host that
was running another project's tool for part of the session.

| | `docs/47`, `full2` + `full3` | **this document, `npu1` + `npu2`** |
|---|---:|---:|
| synthesis, `SOC_MEM=sram` | not quoted | **44.1 s** |
| summed step runtime, part 1 | **22.2 min** (35 steps) | **39.1 min** (35 steps) |
| summed step runtime, part 2 | **61.1 min** (28 steps) | **96.8 min** (25 steps) |
| **total** | **83.3 min** | **135.9 min**, **1.63x** |
| of which post-CTS timing resizer | 12 min 07.7 s | **22 min 09.9 s** |
| of which post-GRT timing resizer | 22 min 27.7 s | **27 min 53.2 s** |
| of which detailed routing | 22 min 51.8 s | **49 min 25.2 s** |
| of which global routing | **8.0 s** | **33.4 s** |
| of which `Magic.WriteLEF` | 7 min 43.6 s | **9 min 37.6 s** |
| global placement | 13.6 s | **42.1 s** |
| clock-tree synthesis | 18.3 s | **35.6 s** |
| disk | 1.1 GB + 2.4 GB | **about 1.6 GB + 3.6 GB**, both gitignored |

**[fact for every figure that carries a unit to the tenth of a second]**

**Two costs that are not runtime and are worth stating.**

- **The run is two directories and the second was not planned.** `npu1`
  carries the flow from the netlist to post-GRT antenna repair; `npu2`
  resumes from `npu1`'s `35-openroad-repairantennas` state with
  `-F OpenROAD.ResizerTimingPostGRT` and carries it to sign-off. **The
  split is an accident of this session and not a configuration
  difference**: unlike `docs/47`'s `full2`/`full3`, where the second run
  turned two keys on, **the two runs here have identical configurations
  and `npu2`'s first step is a re-run of a step `npu1` had begun**. Any
  reader comparing stage tables should treat `npu1` + `npu2` as one
  flow, and the post-GRT resizer's 27 min 53 s is a complete run of that
  step and not a resumption of a partial one.
- **The whole exercise, end to end**, including the synthesis, the two
  `fi_core.sh` rebuilds and their clean runs, the guard test, the
  violator census and this document: **about four hours**, of which
  **2 h 16 min is LibreLane**.

---

## 16. Files touched

Section 4 lists them. To restate the frozen ones explicitly: **nothing
under `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was
written** **[fact, `git status`]**. `hw/rtl/pilot_top.v`, `lif_core.v`,
`aer_fifo.v`, `scrub.v`, `tmr_voter.v`, `secded_enc.v` and
`secded_dec.v` are read and instantiated; `hw/openlane/checker_audit.py`
and `hw/openlane/signoff_report.py` are executed and not modified. No run
directory under `hw/openlane/` was created, resumed or touched.
`hw/soc/out/`, `hw/soc/pnr/runs/` and `hw/soc/pnr/config.resolved.json`
are gitignored.

---

## 17. Reproducing this

```
# 0. the instruments, before anything is claimed to move
V=$HOME/Documents/caravel-lif-crossbar/.venv-flow/bin/python
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/full3   # -3.2029 / 2003
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/full3   # 17 of 19
awk '$NF=="cells"{c=$1} $NF~/^sg13g2_(s?df|dl[hl])/{f+=$1} \
     /Chip area for module/{gsub(/[^0-9.]/,"",$NF); a=$NF+0} \
     END{print c,f,a}' hw/soc/out/s47-sram/area.rpt      # 27565 3085 396177.642
python3 hw/soc/pnr/violator_census.py hw/soc/pnr/runs/full3
#   2003 endpoints, worst -3.2029, sum -2075.11; 444 behind the macro,
#   1559 behind four read-address bits -- docs/49 section 3.1
PDK_ROOT=$HOME/.ciel python3 hw/soc/pnr/floorplan.py \
    --channel 700.08 --density 40 --write /tmp/fp0.json
diff <(python3 -c "import json;d=json.load(open('/tmp/fp0.json'));\
      d.pop('//floorplan48');print(json.dumps(d,indent=4))") \
     <(python3 -m json.tool --indent 4 hw/soc/pnr/config.json)  # identical

# 1. the design that exists
SOC_MEM=sram hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s61-sram
#   42,518 cells, 5,263 flops, 624,429.9180 um2   (44 s)
grep -c "\\u_npu" hw/soc/out/s61-sram/soc_top.netlist.v   # not zero any more

# 2. the floorplan, sized against THAT netlist and nothing else
PDK_ROOT=$HOME/.ciel python3 hw/soc/pnr/floorplan.py \
    --channel 700.08 --cell-area 624429.9180 \
    --write hw/soc/pnr/config-npu.json
#   29.85 % pre-repair, PL_TARGET_DENSITY_PCT 48; the generator asserts
#   that it changed that key and no other

# 3. the run. It is two directories only because this session's first
#    was interrupted; the configurations are identical.
python3 -c "import json,os; json.dump({'nl': os.path.abspath(
  'hw/soc/out/s61-sram/soc_top.netlist.v'), 'metrics': {}},
  open('hw/soc/pnr/state/syn_soc_top.state.json','w'), indent=1)"

SYN_NETLIST=$PWD/hw/soc/out/s61-sram/soc_top.netlist.v \
PNR_CONFIG=$PWD/hw/soc/pnr/config-npu.json \
hw/soc/flow/pnr_soc_top.sh npu1 --overwrite \
    -F Yosys.JsonHeader -S Yosys.Synthesis \
    -S Checker.YosysUnmappedCells -S Checker.YosysSynthChecks \
    -S Checker.NetlistAssignStatements \
    -i hw/soc/pnr/state/syn_soc_top.state.json

# resuming, if it is interrupted (this session's npu2):
SYN_NETLIST=... PNR_CONFIG=... hw/soc/flow/pnr_soc_top.sh npu2 --overwrite \
    -F OpenROAD.ResizerTimingPostGRT \
    -i hw/soc/pnr/runs/npu1/35-openroad-repairantennas/state_out.json

# 4. the reports
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/npu2   # -3.5789 / 2175
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/npu2   # 17 of 19
python3 hw/soc/pnr/violator_census.py hw/soc/pnr/runs/npu2 --top 10
python3 hw/soc/pnr/floorplan_map.py --run hw/soc/pnr/runs/npu2 --no-write
#   --no-write is not optional here: docs/img/ is docs/59's artefact and
#   it is a map of full3

# the derate, audited where it can be audited and NOT in resolved.json,
# which records the integer 5 either way -- docs/31 sections 3.2, 10.3
grep -m1 "timing derate" hw/soc/out/s61-pnr-npu1.log      # 5.0%

# what the configuration actually changed, asserted rather than described
python3 -c "
import json
a=json.load(open('hw/soc/pnr/runs/full3/resolved.json'))
b=json.load(open('hw/soc/pnr/runs/npu2/resolved.json'))
print(sorted(k for k in a if a[k]!=b[k] and not k.startswith('//')))"
#   ['PL_TARGET_DENSITY_PCT', 'VERILOG_FILES', 'VERILOG_INCLUDE_DIRS']

# 5. the fault-injection flow, rebuilt
FI_WORKLOAD=workload   hw/soc/flow/fi_core.sh hw/soc/out/s61-fi-wl
FI_WORKLOAD=supervisor hw/soc/flow/fi_core.sh hw/soc/out/s61-fi-sup
vvp hw/soc/out/s61-fi-wl/tb_soc_fi.vvp  +armed=0   # 18,682, sig 9c07ef12
vvp hw/soc/out/s61-fi-sup/tb_soc_fi.vvp +armed=0   # sig 216f8ce6, 9376..67296

# 6. the guards
.venv/bin/python -m pytest sw/tests/test_soc_synthesis_guards.py
.venv/bin/python -m pytest sw/tests/test_doc_links.py
```

`hw/soc/out/`, `hw/soc/pnr/runs/` and `hw/soc/pnr/config.resolved.json`
are gitignored, so the durable record is this document, the generated
`hw/soc/pnr/config-npu.json` and the two scripts.

---

## 18. What the next block should be

**The ranking has changed, because three of the items in `docs/49`
section 14, `docs/50` section 12 and `docs/53` section 9.3 were ranked
against a design that did not exist.**

1. **`report_power` against THIS netlist, with `docs/57`'s own
   pipeline.** It is the same argument `docs/53` section 15 item 1 made
   and `docs/57` answered: the smallest piece of work that closes the
   largest gap. `docs/57` section 9's **1.465x busy and 5.588x idle**
   are ratios taken from an *unrouted* netlist and applied to a total
   that is 36.1 % wire switching, and that document called the resulting
   **49.7 mW and 31.0 mW** *"the weakest number in this document"*.
   **A routed netlist with extracted parasitics and an accelerator in it
   now exists**, `hw/soc/flow/power_soc_top.sh` is in the tree, and
   `docs/51`'s program is the only one that exercises the block. **It is
   one VCD and a matrix of `report_power` runs, and it turns the
   project's headline power figure from a projection into a
   measurement.** It also decides whether profile 1 of `docs/05` is
   still met, which section 11.1 of `docs/57` currently answers with an
   estimate.
2. **`SYNPRE`, re-measured, because `docs/49` wrote the condition and it
   is met.** Section 9.3. `IBEX_RF_SYNPRE=1` is one environment variable
   on `syn_soc_top.sh`, the area price is now +4.4 % rather than +6.9 %,
   and the cone it restructures is the cone the binding path runs
   through. **`docs/49` section 5 measured it worth +3.4641 ns at
   post-CTS and routing took all of it back; the question is whether
   that still happens when the path it fixes is the worst one.** Two
   runs, and the formal properties C6 and C7 it needs are already
   proved.
3. **The max-capacitance constraint, against max slew.** Section 9.5.
   `docs/48` section 11 item 3 and `docs/49` section 14 item 4 both left
   **0.1080 pF and 0.1800 pF** — the library's own next two
   characterisation loads — unrun, and `docs/48` declined to compose
   0.0648 pF for a reason that was about 0.0648 pF and not about the
   search. **Max slew is now 29 / 8 / 6 where it was 14 / 0 / 1**, and
   hold no longer needs the package.
4. **A taller channel — the one floorplan direction never tested.**
   Section 9.1. `docs/48` measured two floorplans smaller than FP-0 and
   none larger, because at 18.9 % there was no reason to. The channel is
   now **50.44 % dense**, the routability optimiser stops on its
   iteration cap, and detailed routing takes **49 minutes against 23**.
   `floorplan.py --channel` is the whole experiment and the area cost is
   arithmetic: **+3.78 um of die height per row of channel**. It should
   be run **after** items 2 and 3, because both change the cell count
   the floorplan would be sized against.
5. **`hw/soc/formal/soc_bus.sby` green at HEAD, and only then the second
   clock gate.** Section 11. `docs/50` section 8.1 found that suite
   failing for three documents; nothing may gate a fabric slave until it
   is known to pass on the design as it stands, and **this document did
   not check it.**
6. **`docs/59`'s map, regenerated against this die, in its own
   document.** Section 13 item 3. `floorplan_map.py --run
   hw/soc/pnr/runs/npu2` already produces every number, its eight
   geometry self-checks and its ten metric cross-checks **all pass on
   this run** **[fact]**, and the only thing not done is writing the SVG
   — because the artefact in `docs/img/` belongs to a document whose
   argument is about `full3`.
7. **The campaigns, re-run.** Section 12. `docs/42`, `docs/43` and
   `docs/46` can be rebuilt again and have not been re-measured;
   `docs/52`, `docs/55` and `docs/56` used `fi_npu.sh`, which was never
   broken, but their outcome distributions are also for a `soc_top` that
   has since changed.
8. **One source list, derived from the top.** `docs/45` section 9 item 4
   proposed it and declined it; **this document is the bill for
   declining it**, and section 3.3's guard is a smoke alarm and not a
   sprinkler. The cost `docs/45` named — five documents' per-block
   numbers becoming reproducible only against a different recipe — has
   to be weighed against ten documents of physical data being reported
   from a netlist nobody could rebuild.
9. **`.A_REN(req_i && !do_write)`.** `docs/57` section 8.3: six AND
   gates, **0.147 mW**, *"the cheapest measured saving in this document
   by two orders of magnitude in cost"*, ~~and still not done. It is one
   line in `hw/soc/rtl/soc_mem_sram.v` and it would invalidate nothing
   above except by changing the netlist.~~ **DONE 2026-09-12**, and it
   was fourteen lines rather than one: the six data macros plus the
   eight row-port macros, which carry the same `!A_MEN & A_REN`
   idle state for the same reason and which `docs/57` did not price. The
   sentence about invalidating nothing holds and now applies -- every
   layout in this repository predates it, alongside the five RTL defects
   of 2026-09-11 and the two changes of 2026-09-12. `docs/60` section 9
   carries the marker for all of them.

**And what is still blocked, unchanged by this document.** DRC, LVS and
XOR, on `docs/12`'s NO-GO and `docs/54`'s closed exit. A gate-level
simulation of `soc_top`, on the boot ROM's contents. ECC on the
memories. **None of the three moved and none of them is nearer.**
