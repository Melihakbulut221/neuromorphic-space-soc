# 62 — `SYNPRE` on the path that binds, and the gain that was never there

`docs/61-soc-with-the-accelerator.md` section 18 item 2 asked for this
run and gave the reason in one sentence:

> **`docs/49` section 5 measured it worth +3.4641 ns at post-CTS and
> routing took all of it back; the question is whether that still happens
> when the path it fixes is the worst one.**

**This is that run, and the answer is that it does not happen, because
there is nothing to take back.** `SYNPRE` was built into the whole SoC —
Ibex, the fabric, the peripherals, the six RM_IHPSG13 macros and
`soc_npu` with the frozen pilot inside it — hardened on `docs/61`'s
floorplan, and carried to extracted parasitics and three-corner sign-off
STA. At post-CTS, the stage where `docs/49` measured the largest
single-change improvement ever recorded on this design, it is worth
**−0.2014 ns**: nothing, inside the noise. At sign-off it is worth
**−1.0109 ns**: a regression, outside it.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged, with the
derivation stated; **[assumption]** = chosen, and named so it can be
argued with; **[planned]** = intended, with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by blob hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was modified;
`hw/openlane/checker_audit.py` and `hw/openlane/signoff_report.py` are
**read and run** and never written. Section 15 lists every file.

**And no RTL file in this repository was modified either.** `SYNPRE` has
been a parameter of `hw/soc/rtl/ibex_regfile_secded.v` since `docs/44`
and a reachable one since `docs/49`; this document only sets it. Section
15.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **`docs/49`'s reversal condition was met. Is `SYNPRE` worth it now?** | **No, and this time it is not a null result — it is a regression.** At sign-off, `nom_slow_1p08V_125C`, 20 ns, 5 % derate, extracted parasitics: **−4.5898 ns on 2,607 endpoints** against `docs/61`'s **−3.5789 on 2,175** **[fact]**. **The delta is −1.0109 ns, which is 2.5 times `docs/44` section 5.2's measured 0.4 ns of instrument resolution, so unlike `docs/49` this document CAN report it and does.** TNS goes **−2,981.09 → −4,844.60**, 62.5 % worse. Section 8 |
| **What does it cost, on the design that now exists?** | **+30,850.4322 um2 and +1,589 cells, which is +4.9406 % of this design's standard-cell area** — measured, not scaled **[fact for both netlists; the ratio is arithmetic on them]**. **`docs/61` section 9.3 estimated +4.4 % and that estimate is wrong**, because it carried `docs/49`'s absolute +27,237.7728 um2 forward onto a new denominator; the same change on a different source list is a different absolute cost. Section 5 |
| **Where did `docs/49`'s +3.4641 ns at post-CTS go?** | **It never appeared. This is the finding.** Post-CTS, before the timing resizer, the same step in both runs: **−10.7797 against `docs/61`'s −10.5783**, a delta of **−0.2014 ns** — inside the noise floor, and in the wrong direction **[fact]**. `docs/49` measured **−10.7556 → −7.2915** on the smaller design. **The mechanism is visible as cells**: `docs/49`'s worst post-CTS path went from five `xnor2` to two; here it goes from **three to eleven** **[fact, both `28-openroad-stamidpnr-1/max.rpt`]**. Section 7.1 |
| **Why not, if the binding path really does run through the cone `SYNPRE` restructures?** | **Because it runs through that cone AND through the one `SYNPRE` cannot touch, and the second is the larger half.** The sign-off worst path launches at a register-file read address and captures at a register-file **SECDED check bit** — `raddr_b_i[1] → g_rf_flops[23].g_chk.rf_chk_q[2]` **[fact]** — and `rf_chk_q`'s D input is `u_enc_wr.check_out`, the **write** encoder, by `ibex_regfile_secded.v` lines 505 and 546 **[fact, the RTL]**. **`docs/61` and `docs/49` describe two halves of one path and both were right.** Section 3 |
| **Did it make the binding path shorter?** | **No. It made it longer.** `docs/61`'s worst path is **79 cells with 14 `xnor2`**, arriving at 24.9617 ns; this one is **113 cells with 17 `xnor2`**, arriving at 26.0195 **[fact, the two sign-off `max.rpt`]**. **A restructuring built to take XOR levels off this path put three more on it.** Section 8.3 |
| **Where does the binding path land afterwards?** | **In the same place, worse.** It does **not** move back to the macros: the macro launch group goes **9 → 3** **[fact]**. `SYNPRE`'s signature is present — **1,514 endpoints move from an address launch to a stored-data launch**, which is exactly `docs/49` section 6.2 item 2 — but **the read-address group is not emptied, it is split**: 1,050 endpoints still launch from `raddr_b_i[1]` and `raddr_a_i[2]`, and **the worst slack in the design is on one of them**. Section 9 |
| **Do the checkers still gate?** | **17 of 19, the same seventeen and the same two**, recomputed from the installed LibreLane's own step classes against this run's `resolved.json`. The four corner checkers each examined **three corners**. Section 10 |
| **Did the instrument reproduce before it moved?** | **Yes, thirteen ways.** `docs/61`'s sign-off block, its area, its violator census, its checker audit, its placement span, its three stage-table rows, its clock-tree sink counts and its whole cell census; `docs/49`'s own sign-off and netlist; the floorplan generator byte for byte; and `docs/49`'s formal and injection evidence. Section 2 |
| **Is the design still correct?** | **Yes, and the obligations were re-run rather than inherited.** C5, C6 and C7 pass on `bmc`, `prove`, `prove_abc` and `cover` with **9 of 9 covers reached**; the 124-injection register-file campaign is **identical field for field**; and the whole-SoC simulation is **cycle-identical to the baseline at HEAD**, differing in one line which is the output path. Section 11 |
| **What did it cost to find out?** | **230.0 minutes of summed step runtime against `docs/61`'s 135.9, 1.69x** **[fact]**, of which the post-CTS timing resizer alone is **2 h 04 min against 22 min, 5.60x**. `docs/49` section 7.1's finding — a `SYNPRE` netlist makes the targeted timing repair dramatically slower — reproduces. Section 14 |
| **May a frequency be published?** | **No.** `docs/53` section 9.2 refused it on three grounds, `docs/05` section 4 rule 5 binds, none of the three grounds moved, and this run is further from the constraint than `docs/61`'s. Slack against **20 ns** is what this document reports. Section 8.5 |

> **THE ONE-SENTENCE RESULT.** `docs/49` declined `SYNPRE` because it
> acted on a cone disjoint from the binding path, and wrote down the
> condition under which that would stop being true; `docs/61` met the
> condition; **and the re-measurement finds that `SYNPRE` is worse than
> it was when it was on the wrong cone.** `docs/49`'s conclusion is
> replaced rather than confirmed: the reason to decline `SYNPRE` is no
> longer that it cannot reach the binding path, it is that **it reaches
> the binding path and lengthens it.**

---

## 2. Reproducing every instrument before moving it

`docs/44` section 5.2 set the rule and `docs/45`, `docs/47`, `docs/48`,
`docs/49`, `docs/50`, `docs/57` and `docs/61` have all followed it.
**Thirteen instruments are used in this document and all thirteen were
reproduced first**, in this session, against the published figures.

| What | Published | Measured here |
|---|---|---|
| `docs/61` 8.1, the sign-off block | −3.5789 / 2,175 / −2,981.09 slow; +5.0703 typ; +10.1244 fast; hold +0.0981 on 0; slew 29 / 8 / 6; cap 15 / 15 / 15 | **every figure**, `signoff_report.py hw/soc/pnr/runs/npu2` **[fact]** |
| `docs/61` 5.2, the netlist | 42,518 cells, 5,263 flip-flops, 624,429.9180 um2 | **the same three**, `hw/soc/out/s61-sram/area.rpt` **[fact]** |
| `docs/61` 9.3, the violator census | 1,718 on `raddr_b_i[3]` worst −3.5789; 415 on `raddr_b_i[2]` worst −3.5530; 21 in `u_npu` worst −0.3690; 9 on `u_b2/A_DOUT[1]` worst −2.5276; 2,175 total | **every count and every slack, and the −2,981.09 sum**, `violator_census.py` **[fact]** |
| `docs/61` 10, the checker audit | **17 of 19**, not gating `LintWarnings`, `WireLength` | **17 of 19, the same two** **[fact]** |
| `docs/61` 7.1, three stage-table rows | post-global-placement −137.5770; post-CTS −10.5783; post-CTS resizer −0.0277 | **−137.577, −10.5783, −0.0276916** **[fact]** |
| `docs/61` 7.2, the placement | utilization 0.298552; instance utilization 0.661796; HPWL 2.630032e+06; minimum congestion 1.0112; inflation 12,522.40 (+1.79 %) | **every figure** **[fact]** |
| `docs/61` 7.2, the span at CTS | 2,176.8 × 1,489.3 at (65.3, 412.0) over 42,511 cells | **2,176.8 × 1,489.3 at (65.3, 412.0) over 42,511**, from the run's own CTS DEF **[fact]** |
| `docs/61` 7.3, the clock tree | `clk_i` 7 sinks, `clk_i_regs` 2,940, `u_ibex.clk` 2,323 | **7 / 2,940 / 2,323** **[fact, `CTS-0010` and `CTS-0011`]** |
| `docs/61` 8.3, the cell census | fill 117,780; memory/logic 2.7445; channel 50.44 % dense; 2,485 cells above it; 2,062 right of the macros; 4,352,524 transistors, 84.9 % macro | **every figure**, `floorplan_map.py --run hw/soc/pnr/runs/npu2 --no-write`, all eighteen checks passing **[fact]** |
| `docs/49` 6.1, its own sign-off | −3.0838 on 1,783; hold +0.0483; max slew 126 slow; max cap 24 | **every figure**, `signoff_report.py hw/soc/pnr/runs/syn2` **[fact]** |
| `docs/49` 4.1, its own netlist | 30,249 cells, 3,085 flip-flops, 423,415.4148 um2 | **the same three**, `hw/soc/out/s49-synpre/area.rpt` **[fact]** |
| `docs/48` 4 and `docs/61` 6.2, the generator | `--channel 700.08 --density 40` emits `config.json` byte for byte | **byte for byte** **[fact]** |
| `docs/49` 9.1 and 9.2, the evidence | four formal tasks PASS, 9 of 9 covers; 6 of 6 cocotb; 124 injections at 107 / 17 / 0 / 0 with 25 check-field draws | **every one** **[fact]**, section 11 |

**Two of the thirteen are worth a sentence rather than a row.**

- **`docs/61`'s CTS span was re-derived rather than re-read.** That
  document quotes it from its own measurement; here it is recomputed
  from `hw/soc/pnr/runs/npu1/27-openroad-cts/soc_top.def` by a
  fifteen-line script that counts only the `_NNNNN_` components, and it
  lands on **2,176.8 × 1,489.3 at (65.3, 412.0) over 42,511 cells** —
  `docs/61` section 7.2's row to the last digit printed, by an
  independent path.
- **The clock-tree sink counts are the check that `SYNPRE` adds no
  state, made by a tool that is not the synthesiser.** Section 7.3.

---

## 3. What binds, and why `docs/49` and `docs/61` are both right about it

This section is the one that decides the document.

### 3.1 The two cones, restated from the RTL

`docs/49` section 3.2 partitioned `hw/soc/rtl/ibex_regfile_secded.v` into
two places where the codec touches a flip-flop, and the partition is
still correct:

- **The read ports.** `raw_b = rf_data[raddr_b_i]`, `chk_b =
  rf_chk[raddr_b_i]`, then a decoder whose syndrome builds the correction
  mask, then `rdata_b_o` **[fact, lines 561, 562, 627 and 633]**. **This
  is what `SYNPRE` changes**: `g_synpre` puts one `secded_enc` beside
  every register so the parity tree runs in parallel with the 32-way read
  multiplexer instead of behind it **[fact, line 598]**.
- **The write port.** `wr_data = we_a_i ? wdata_a_i : scrub_data`, one
  `secded_enc u_enc_wr`, and its output is the D input of every
  `rf_chk_q` **[fact, lines 497, 505 and 546]**. **`SYNPRE` does not
  touch this and cannot**: there is one encoder, it is already in front
  of the storage, and there is nothing to hoist it past.

### 3.2 The binding path contains both, in series

`docs/61` section 9.3 reported the sign-off worst path as

```
Startpoint  _75872_  = u_ibex.gen_regfile_ff.register_file_i.raddr_b_i[3]
Endpoint    _73439_  = u_ibex...g_rf_flops[9].g_chk.rf_chk_q[2]
```

and concluded, correctly, that it **runs through the 32-way read
multiplexer `SYNPRE` restructures**. What that document did not say — and
what decides this one — is what the *other* end of it is.

> **A PATH THAT LAUNCHES AT A READ ADDRESS AND CAPTURES AT A CHECK-BIT
> FLIP-FLOP IS A READ AND A WRITE IN THE SAME CYCLE.** The address
> selects a word, the word leaves through `rdata_b_o`, the core computes
> with it, the result arrives back at `wdata_a_i`, **`u_enc_wr` re-encodes
> it**, and the new check word is captured in `rf_chk_q`. **`SYNPRE`'s
> cone is the first half and `docs/49`'s untouchable encoder is the
> second half, and they are on the same path.**
>
> **So `docs/49` section 3.2's disjoint-cone finding was never repealed
> by `docs/61`. It was half-repealed.** `docs/61` measured that the
> binding path had entered `SYNPRE`'s cone, which is true; it did not
> measure that the path had left the write encoder's, which it had not.

**And the measurement says the second half is the larger one.**
`docs/49` section 3.2 counted **eleven `sg13g2_xnor2_1` in series** as
the write encoder's parity chain on `docs/47`'s binding path **[fact,
that document, and its section 13 corrects an earlier count of 22 report
lines to 11 cells]**. `docs/61`'s binding path carries **14 `xnor2`
cells** **[fact, this session, `npu2/14-openroad-stapostpnr/
nom_slow_1p08V_125C/max.rpt`]**.

> **AT MOST THREE OF THOSE FOURTEEN ARE ON THE SIDE `SYNPRE` CAN REACH**
> **[estimate, 14 measured here minus `docs/49`'s 11 measured there; the
> two are different runs of a changed design and the subtraction is
> offered as a bound, not as a decomposition]**. **A restructuring that
> can address three XOR levels out of fourteen, on a path missing its
> constraint by 3.5789 ns, is not the lever that path needs — and
> section 8.3 measures that it did not even collect the three.**

**This is a structural argument and it was not treated as a reason to
skip the experiment**, for exactly `docs/49` section 3.2's reason:
`repair_timing` works on whichever path is worst when it runs, the
populations compete for one resizer budget, and 1,589 more cells change
the placement. The rest of this document is what happened when it was
run.

---

## 4. What was built

| File | Change |
|---|---|
| `hw/soc/pnr/config-synpre.json` | the floorplan variant this run hardens. **Generated** by `floorplan.py`; differs from `config-npu.json` in `PL_TARGET_DENSITY_PCT` and the generated provenance note, **and in nothing else**, under the generator's own assertion **[fact]** |
| `docs/62-synpre-remeasured.md` | this document |
| `docs/00-index.md` | one row, which `sw/tests/test_doc_links.py` requires |

**That is the whole list.** No RTL, no testbench, no formal file, no flow
script and no test was modified **[fact, `git status`]**. Everything else
this run needed already existed: `IBEX_RF_SYNPRE=1` on
`hw/soc/flow/syn_soc_top.sh` and `SOC_RF_SYNPRE=1` on
`hw/soc/flow/sim_soc.sh` are `docs/49`'s, `--cell-area` on
`floorplan.py` and `violator_census.py` are `docs/61`'s, and properties
C6 and C7 are `docs/49`'s.

> **THAT IS ITSELF A RESULT ABOUT THE PREVIOUS TWO DOCUMENTS.** `docs/49`
> built a knob it then recommended against using and left it reachable
> and guarded; `docs/61` put the violator census and the cell-area-aware
> floorplan generator in the tree rather than in a scratch directory.
> **The whole of this measurement is one environment variable, one
> generated configuration and one flow invocation**, and the reason is
> that two earlier documents each paid a little more than they had to.

---

## 5. The cost, recomputed rather than scaled

`SOC_MEM=sram IBEX_RF_SYNPRE=1 hw/soc/flow/syn_soc_top.sh 20`, same
Liberty, same typical corner, same `abc.constr`, same 20 ns `-D` target,
same deferred flatten, same `stat -liberty`. **`docs/45`'s recipe, which
is the whole point of comparing.**

| | `docs/61`, `hw/soc/out/s61-sram` | **this run, `hw/soc/out/s62-synpre`** | difference |
|---|---:|---:|---:|
| cells | 42,518 | **44,107** | **+1,589** |
| **flip-flops** | **5,263** | **5,263** | **0** |
| standard-cell area, um2 | 624,429.9180 | **655,280.3502** | **+30,850.4322** |
| kGE at 7.2576 um2 | 86.038 | **90.289** | |
| **as a fraction of the design's standard cells** | | | **+4.9406 %** |

**[fact for every row of both columns; the differences and the percentage
are arithmetic on them]**

**Three things to read out of that table, and the second is a correction
to `docs/61`.**

**1. THE FLIP-FLOP COUNT DOES NOT MOVE, AND THIS TIME A SECOND TOOL SAYS
SO.** `docs/49` section 4.1 item 1 made this check at the synthesiser;
here clock-tree synthesis makes it independently at the layout. Section
7.3.

**2. `docs/61` SECTION 9.3's "+4.4 %" IS WRONG AND THE ERROR IS
INSTRUCTIVE.** That document wrote:

> **+27,237.7728 um2 was +6.9 % of `docs/47`'s standard cells and is
> +4.4 % of this design's [estimate, arithmetic on a measured area]**

The arithmetic is right and the input is not: **+27,237.7728 um2 is the
cost of `SYNPRE` on `docs/47`'s source list**, and this design's source
list has six more files in it. The measured cost here is
**+30,850.4322 um2 — 13.3 % more absolute area than the figure carried
forward — and +4.9406 %, not +4.4 %** **[fact]**. `docs/61` labelled it
**[estimate]** and stated its derivation, so it is not a defect in that
document; it is what an inherited absolute number does when only the
denominator is re-measured.

**3. AND THE CELL COUNT MOVED THE OTHER WAY, WHICH IS `docs/45` SECTION
4.3 AGAIN.** The same parameter costs **+1,589 cells** here and
**+2,684 cells** on `docs/47`'s design **[fact, both syntheses]** —
**fewer cells for more area**. A block's measured size is a function of
the whole source list and not only of the block, and the direction is not
predictable from the block.

---

## 6. The floorplan

**No decision was taken here and that is deliberate.** `docs/61` section
6.2 established that this die holds the accelerator with no growth; the
question this document asks is about a netlist, so the floorplan is
generated by the same rule from the new cell area and nothing else is
touched.

```
floorplan.py --channel 700.08 --cell-area 655280.3502 \
             --write hw/soc/pnr/config-synpre.json
```

| | `docs/61`, `npu1`/`npu2` | **this run, `syp1`** |
|---|---|---|
| arrangement, channel, die, core, six macro origins and orientations | — | **all the same** |
| placeable, core − macro | 2,092,010.95 um2 | **the same** |
| standard cells as synthesised | 624,429.9180 | **655,280.3502** |
| **standard cells / placeable** | **29.85 %** | **31.32 %** |
| `PL_TARGET_DENSITY_PCT` | 48 | **49** |

**[fact for every geometric figure; the two densities are arithmetic on a
measured cell area]**

`floorplan.py` has emitted `round(utilization) + 18` since `docs/48`; at
31.32 % the rule gives **49**. **The generator's assertion fired and the
file differs from `config-npu.json` in `PL_TARGET_DENSITY_PCT` and the
provenance note and in nothing else** **[fact]**.

**And the control that matters is at the other end.** `resolved.json` for
`npu1` and `syp1`, compared key by key:

```
  PL_TARGET_DENSITY_PCT  48 -> 49
```

**[fact, and there is no second]** — `VERILOG_FILES` is the same
56-element list, `VERILOG_INCLUDE_DIRS` is the same, the six macro
`instances` dictionaries compare equal, `DIE_AREA` and `CORE_AREA` are
identical, both `RUN_POST_GRT_*` are `True`, and all four
`*_VIOLATION_CORNERS` are `["*"]`. **The netlist arrives through the
input state and not through the configuration**, which is why the source
list does not move.

**The derate is audited where `docs/31` sections 3.2 and 10.3 say it can
be** — not in `resolved.json`, which records the integer 5 either way.
This run's flow log reads **`[INFO] Setting timing derate to: 5.0%`**
**[fact]**.

---

## 7. The run, stage by stage, and where the 3.46 ns was supposed to be

LibreLane v3.0.5, OpenROAD 26Q1-2938-g0e2d771c5e, `ihp-sg13g2` at
`c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c`, rootless, on a shared
20-thread host that was running another project's OpenROAD throughout
**[fact, `ps`]** — the same caveat `docs/49` section 7.1 and `docs/61`
section 15 both state about their runtimes.

**It is one run directory and not two.** `docs/61` needed `npu1` and
`npu2` because its first attempt was interrupted; `syp1` carries the flow
from the netlist to sign-off in 62 steps without a resume. **The stage
comparisons below are against `npu1` up to global routing and `npu2`
after it, which is the partition `docs/61` itself uses and the step
indices line up exactly.**

### 7.1 Setup slack at `nom_slow_1p08V_125C`, stage by stage

| Stage | step | `npu1` / `npu2` | **`syp1`** | delta |
|---|---|---:|---:|---:|
| `STAMidPNR`, post-global-placement | 23 | −137.577 | **−134.137** | +3.440 |
| **`STAMidPNR-1`, post-CTS, before the timing resizer** | 28 | **−10.5783** | **−10.7797** | **−0.2014** |
| `STAMidPNR-2`, post-CTS resizer, placement parasitics | 30 | −0.0277, TNS −0.1395 | **+0.0039, TNS 0** | +0.0316 |
| **`STAMidPNR-3`, after global routing and post-GRT repair** | 37 / 02 | **−2.9441**, TNS −3,011.33 | **−4.0711**, TNS **−4,704.47** | **−1.1270** |
| **`STAPostPNR`, extracted parasitics, sign-off** | 49 / 14 | **−3.5789** | **−4.5898** | **−1.0109** |

**[fact, the `or_metrics_out.json` of each step in each run]**

> **THE SECOND ROW IS THE RESULT OF THIS DOCUMENT AND EVERYTHING ELSE
> FOLLOWS FROM IT.** `docs/49` section 5.2 called its own version of this
> row *"the largest single-change improvement measured anywhere on this
> design"* — **−10.7556 → −7.2915, +3.4641 ns, eight times the noise
> floor.** On the design where `SYNPRE` acts on the cone that binds, the
> same row moves by **−0.2014 ns**, which is inside `docs/44` section
> 5.2's measured 0.4 ns and is **not reported as a regression either**.
>
> **`docs/61` section 18 item 2 asked whether routing would still take
> the 3.46 ns back. The question does not arise: the 3.46 ns is not
> there at post-CTS to be taken.**
>
> **AND THE FOURTH ROW IS OUTSIDE ANY NOISE FLOOR AND GOES THE WRONG
> WAY.** After global routing and post-GRT repair `SYNPRE` is
> **1.1270 ns worse** — `docs/49` section 5.2 item 4 measured the same
> shape at **0.8160 ns worse** and called it *"where it gives the
> 3.46 ns back"*. **Here there is nothing to give back and it goes 1.13
> ns into debt anyway.** The spreading mechanism that document diagnosed
> is not conditional on there having been a gain.

### 7.2 The post-CTS worst path, which is the mechanism as cells

Both runs' `28-openroad-stamidpnr-1/max.rpt`, resolved against each run's
own netlist:

| | `npu1` | **`syp1`** |
|---|---|---|
| launch | `register_file_i.raddr_a_i[1]` | **`register_file_i.g_plain_rf.g_rf_flops[27].rf_reg_q[16]`** |
| capture | `s_rdata_clint[3]` | **`u_clint.g_mtime_secded.u_mtime_dec.check_raw[4]`** |
| cells on the path | **93** | **93** |
| **`xnor2` cells on the path** | **3** | **11** |
| data arrival, ns | 31.695845 | **31.914242** |
| data required, ns | 21.117573 | 21.134546 |

**[fact for every row; the launch and capture names are resolved with
`violator_census.py`'s own netlist loader, and the `xnor2` counts are
report lines halved, per `docs/49` section 13's correction]**

> **1. `SYNPRE` DID EXACTLY WHAT IT IS BUILT TO DO, AND IT IS VISIBLE IN
> THE LAUNCH POINT.** The baseline launches at a read **address**; the
> `SYNPRE` run launches at a register's **stored data**. That is
> `docs/49` section 6.2 item 2's signature — *"the syndrome no longer
> waits for the address to select a word, so the long path now starts at
> the word"* — reproduced at a different stage on a different design.
> **The parameter is not failing to take effect and section 11 has the
> independent confirmation.**
>
> **2. AND THE PATH IT PRODUCED IS THE SAME LENGTH WITH FOUR TIMES THE
> XOR.** 93 cells in both, arriving within 0.22 ns of each other, with
> **three `xnor2` becoming eleven** **[fact]**. `docs/49` measured this
> quantity going the other way — *"five `xnor2` cells on the path
> becoming two"* — and that is the whole difference between the two
> documents' results. **On `docs/47`'s design the post-CTS worst path
> was mostly syndrome tree and `SYNPRE` deleted it. On this design the
> post-CTS worst path had three XOR levels on it, so there was nothing
> to delete, and what `SYNPRE` put in front of the storage instead is
> longer than what it took out from behind the multiplexer.**
>
> **3. BOTH PATHS END IN `mtime`, WHICH IS THE MOST-DEFERRED ITEM IN
> THIS RECORD.** Ranked first by `docs/41` section 7.4 and `docs/44`
> section 11, second by `docs/43`, third by `docs/45`, fourth by
> `docs/47`, second by `docs/48`, third by `docs/49` section 14.
> `docs/49` section 5.2 already found `mtime` at both ends of its own
> post-CTS comparison. **A third document now measures that the stage
> where `SYNPRE` is supposed to pay is a stage whose worst path
> terminates in a 64-bit free-running counter at the far end of a
> broadcast bus**, and section 17 ranks it.

**And the post-CTS resizer closes the stage in both runs**, at −0.0277
with TNS −0.1395 and at **+0.0039 with TNS 0** **[fact]**. Neither number
survives the noise floor and neither is claimed; they are here because
`docs/49` section 5.1 reports the same row and a reader comparing the
three tables needs it.

### 7.3 Placement, and the density regime `docs/61` said had changed

| | `npu1` | **`syp1`** |
|---|---:|---:|
| standard-cell area at global placement, um2 | 624,575 | **655,436** |
| standard-cell utilization | 0.298552 | **0.313304** |
| instance utilization, macros included | 0.661796 | **0.668909** |
| **global-placement HPWL, um** | **2.630032e+06** | **3.289510e+06**, **+25.07 %** |
| routability iterations | 844 | **1,076** |
| minimum observed routing congestion | **1.0112** | **1.0561** |
| **final weighted routing congestion** (target 1.0100) | **0.9960** | **1.0424** |
| **routability artificial inflation** | **12,522.40 (+1.79 %)** | **69,787.13 (+9.67 %)** |
| synthesised-cell span at CTS | 2,176.8 × 1,489.3 at (65.3, 412.0), 42,511 cells | **2,182.6 × 1,500.7 at (60.0, 419.6), 44,100 cells** |
| cells / their own bounding box | 19.27 % | **20.01 %** |

**[fact; the last row and the HPWL percentage are arithmetic on measured
spans and areas]**

**Three readings, and the third is the one this document was warned to
look for.**

**HPWL RISES 25.07 %, WHICH IS `docs/49` SECTION 5.2 ITEM 3 AGAIN AND
SLIGHTLY WORSE.** That document measured **+23.2 %** for the same change
on a design 37 % smaller. **31 parity trees fanned out of all 32
registers' flip-flops is a lot of new connectivity**, and it costs the
same proportion of wire whatever else is on the die.

**BUT THE CELLS DID NOT SPREAD THIS TIME, AND THAT IS A CHANGE OF
MECHANISM RATHER THAN A REPRIEVE.** `docs/49` measured **27.0 % of their
own bounding box becoming 22.1 %** and named spreading as the mechanism.
Here the same quantity goes **19.27 % → 20.01 %** — it goes **up**
**[fact]**. **The cells cannot spread because there is nowhere left to
spread to**: `docs/61` section 7.2 already measured this design using the
full height of the core. So the wire has to go somewhere else, and it
goes into congestion.

**AND THAT IS THE THING `docs/61` PREDICTED WOULD COMPOUND, MEASURED.**
`docs/61` section 7.2 found the placer newly density-constrained — the
routability optimiser exhausting its iterations at **1.0112 against a
target of 1.0100** — and section 9.1 warned that adding cells to a design
in that regime is not the same as adding them to one that is not.

> **IT IS MEASURABLY WORSE AND THE SHARPEST FORM OF IT IS ONE ROW.**
> `npu1`'s routability optimiser finishes at a **final weighted
> congestion of 0.9960, below its target**; `syp1`'s finishes at
> **1.0424, above it** **[fact, `GPL-1005` in both logs]**. And the
> artificial inflation the optimiser had to add to get there goes
> **12,522.40 um2 (+1.79 %) → 69,787.13 um2 (+9.67 %), a factor of 5.57**
> **[fact, `GPL-1012`]**. **`docs/61` section 9.1's caution was
> justified: the same +4.94 % of cells that would have been free at
> `docs/48`'s 18.9 % utilization costs 5.6 times the inflation at
> 31.3 %.**

### 7.4 The clock tree, which counts the flip-flops that were not added

| Clock net | `npu1` sinks | **`syp1`** sinks |
|---|---:|---:|
| `clk_i`, the six macros | 7 | **7** |
| `clk_i_regs`, everything ungated | 2,940 | **2,940** |
| `u_ibex.clk`, behind the gate | 2,323 | **2,323** |

**[fact, `CTS-0010` and `CTS-0011` in the two CTS logs]**

> **NOT ONE SINK MOVES, AND THAT IS THE POINT OF PRINTING IT.**
> `docs/49` section 4.1 item 1 checked at the synthesiser that `SYNPRE`
> is pure combinational restructuring; **clock-tree synthesis is a
> different tool reading a different file and it agrees to the unit**.
> 2,940 + 2,323 = 5,263, which is both netlists' flip-flop count. A
> reader who distrusts the parameter having taken effect should read
> section 7.2's launch point and section 11's arm check instead — those
> are where the change is visible — and read this table as the check
> that it added no state while doing it.

---

## 8. Sign-off

### 8.1 The three-corner block

`OpenROAD.STAPostPNR`, three corners, **extracted parasitics** from
`OpenROAD.RCX`, 5 % derate applied as a float, 0.25 ns of clock
uncertainty, 20 ns. Slack in ns.

| Corner | setup ws | setup vio | setup TNS | hold ws | hold vio | max cap | max slew |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`nom_slow_1p08V_125C`** | **−4.5898** | **2,607** | **−4,844.60** | +0.3993 | **0** | **34** | **83** |
| `nom_typ_1p20V_25C` | +4.5151 | 0 | 0.0000 | +0.1516 | **0** | **34** | **3** |
| `nom_fast_1p32V_m40C` | +9.7342 | 0 | 0.0000 | **+0.0058** | **0** | **36** | **1** |

**[fact, `hw/soc/pnr/runs/syp1/49-openroad-stapostpnr/summary.rpt`]**

### 8.2 Against `docs/61`, criterion by criterion

| | `docs/61`, `npu2` | **`syp1`** | delta |
|---|---:|---:|---:|
| **setup worst slack, slow** | **−3.5789** | **−4.5898** | **−1.0109** |
| violating setup endpoints | 2,175 | **2,607** | **+432** |
| **setup TNS, slow** | −2,981.09 | **−4,844.60** | **−1,863.51, 62.5 % worse** |
| setup worst slack, typ | +5.0703 | +4.5151 | −0.5552 |
| setup worst slack, fast | +10.1244 | +9.7342 | −0.3902 |
| hold worst slack, fast | +0.0981 | +0.0058 | −0.0923 |
| **hold violations, all corners** | **0** | **0** | **0** |
| **max slew, slow / typ / fast** | 29 / 8 / 6 | **83 / 3 / 1** | **slow 2.9x worse** |
| **max cap, slow / typ / fast** | 15 / 15 / 15 | **34 / 34 / 36** | **worse at all three** |
| detailed-routing DRC | **0** after 24 iterations | **0** after 23 | — |
| routed wirelength, um | 4,049,894 | **4,599,796**, **+13.58 %** | |
| **longest net, um** | **2,315.01** | **2,789.72**, **+20.5 %** | |
| antenna violating nets | 1 | **0** | |
| antenna diodes | 501 | 603 | |
| standard cells excl. fill | 57,399 | **58,884** | |
| standard-cell area placed, um2 | 818,684 | **846,853**, +3.44 % | |
| timing-repair buffers | 11,454 | **11,213** | |
| fill and decap | 117,780 | **116,504** | |
| **sequential cells** | **5,263** | **5,263** | **0** |
| die area, um2 | 4,786,290 | **4,786,290** | **0** |
| disconnected pins / power-grid violations | 0 / 0 | **0 / 0** | |
| `design__violations` on a run that fails three criteria | **0** | **0** | |

**[fact for both columns; the deltas and percentages are arithmetic on
measurements]**

> **THIS DELTA IS REPORTABLE AND `docs/49`'s WAS NOT, AND THE DIFFERENCE
> IS THE WHOLE REASON THE RULE EXISTS.** `docs/44` section 5.2 measured
> this flow's resolution at about **0.4 ns**; `docs/49` section 6.1
> refused to claim **+0.1191 ns** and `docs/61` section 8.1 refused to
> claim **−0.3760 ns**, both on that ground. **−1.0109 ns is 2.5 times
> the noise floor and −1,863.51 ns of TNS is far outside any reading of
> it**, so this document states the regression plainly: **on the design
> that exists, on the floorplan `docs/61` established, `SYNPRE` costs
> about one nanosecond of worst-case setup slack and 62.5 % more total
> negative slack, for +4.94 % of standard-cell area.**
>
> **AND THE ELECTRICAL FIGURES COMPOUND, WHICH `docs/61` SECTION 9.5
> PREDICTED THEY WOULD.** That document measured max slew already worse
> than `docs/47`'s — 29 / 8 / 6 against 14 / 0 / 1 — and observed that
> `docs/49` had measured `SYNPRE` making slew dramatically worse
> (14 → 126). **The two do compound: 29 → 83 at the slow corner, and max
> cap 15 → 34** **[fact]**. Neither run sets
> `MAX_CAPACITANCE_CONSTRAINT`, so both counts are against the library's
> own `default_max_capacitance : 0.3` and are directly comparable, which
> is the condition `docs/49` section 6.3 established for this comparison.
>
> **TWO THINGS DID NOT GET WORSE AND ARE REPORTED BECAUSE THEY DIDN'T.**
> **Hold still closes at all three corners with no key changed** — the
> free closure `docs/61` section 8.1 found is not `SYNPRE`-sensitive —
> and **detailed routing still reaches 0 DRC**, from 32,902 starting
> violations against `npu2`'s 32,412 **[fact, the `DRT-0199`
> sequences]**, in **33 min 36 s against 49 min 25 s**.

### 8.3 The binding path, and the three XOR levels that were not collected

| | `docs/61`, `npu2` | **`syp1`** |
|---|---|---|
| launch | `register_file_i.raddr_b_i[3]` | **`register_file_i.raddr_b_i[1]`** |
| capture | `...g_rf_flops[9].g_chk.rf_chk_q[2]` | **`...g_rf_flops[23].g_chk.rf_chk_q[2]`** |
| cells on the path | **79** | **113** |
| **`xnor2` cells on the path** | **14** | **17** |
| data arrival, ns | 24.961651 | **26.019476** |
| data required, ns | — | 21.429699 |
| **slack** | **−3.5789** | **−4.5898** |

**[fact, the two sign-off `max.rpt`, resolved against each run's own
final netlist]**

> **IT IS THE SAME STRUCTURE IN BOTH RUNS — A REGISTER-FILE READ ADDRESS,
> THROUGH THE READ MULTIPLEXER AND THE CORE, INTO A REGISTER-FILE SECDED
> CHECK BIT — AND `SYNPRE` MADE IT LONGER BY EVERY MEASURE AVAILABLE.**
> 79 cells become **113**, 14 `xnor2` become **17**, and the arrival goes
> up by **1.0578 ns** **[fact]**.
>
> **A restructuring whose entire purpose is to remove XOR levels from
> this cone added three of them to the path that binds.** Section 3.2 is
> why: the path's XOR content is dominated by `u_enc_wr`, the write
> encoder, which `SYNPRE` does not touch and cannot; what `SYNPRE`
> changes is the read half, and section 7.3's **+25.07 % of HPWL** and
> **5.57x of routability inflation** land on every path in the design
> including this one.
>
> **`docs/49` SECTION 3.2's PREDICTION IS THEREFORE STILL CORRECT, ON A
> DESIGN IT WAS NOT MADE ABOUT.** That document wrote that *"the most a
> perfect, free `SYNPRE` could do to the worst slack is nothing"*, for a
> reason — disjoint cones — that `docs/61` retired. **The conclusion
> survives its own stated refutation, and this document supplies a
> second, independent reason for it: the cones are no longer disjoint,
> and `SYNPRE` is not free.**

### 8.4 What the flow says on the way out

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

**[fact, `hw/soc/out/s62-pnr-syp1.log`]** — **three criteria, the same
three `docs/61` named**, and hold is absent from both because it passes
in both.

### 8.5 No frequency

`docs/53` section 9.2 refused to publish one on three grounds, `docs/05`
section 4 rule 5 binds every external claim, and `docs/61` section 8.4
added a fourth. **None of the four moved.** The layout fails setup, max
slew and max cap; it has no DRC, LVS or XOR result; the workload that
would justify a target has still not been sized against a mission; and
the netlist has still never been simulated.

**What may be said is the slack against the constraint**: this design
misses a **20 ns** period by **4.5898 ns at the slow corner on 2,607 of
its endpoints**, which is **further from that constraint than the same
design without `SYNPRE`**.

---

## 9. Where the binding path lands, which was the other question

`hw/soc/pnr/violator_census.py` on `syp1`, against `syp1`'s own netlist,
beside `docs/61`'s column:

| Launch point | `npu2` | **`syp1`** |
|---|---:|---:|
| `...register_file_i.raddr_b_i[3]` | **1,718**, worst **−3.5789** | 0 |
| `...register_file_i.raddr_b_i[2]` | 415, worst −3.5530 | 0 |
| **`...g_plain_rf.g_rf_flops[26].rf_reg_q`** | **0** | **1,514**, worst **−3.8548** |
| **`...register_file_i.raddr_b_i[1]`** | **0** | **960**, worst **−4.5898** |
| `...register_file_i.raddr_a_i[2]` | 0 | **90**, worst −2.5126 |
| `u_ibex...cs_registers_i.csr_addr[8]` | 0 | **27**, worst −0.6682 |
| `u_npu.u_node0.u_lif.ev_axon_r[1]` | 21, worst −0.3690 | **10**, worst −0.2073 |
| **an SRAM macro's `A_DOUT`** | **9**, worst −2.5276 | **3**, worst −2.0691 |
| `u_clint.g_mtime_secded.u_mtime_dec.code_in[61]` | 0 | **3**, worst −0.8702 |
| `u_busstat` internal | 12, worst −1.3924 | 0 |
| **total** | **2,175** | **2,607** |

**[fact, both columns from the same script against each run's own
netlist; the `npu2` column reproduces `docs/61` section 9.3]**

**Three answers, and the first is the one that was asked for.**

**1. IT DOES NOT GO BACK TO THE MACROS.** The task this document answers
raised the possibility that emptying the read-address group would return
the constraint to the memories, which is where `docs/47` to `docs/49`
found it. **It does not**: the macro launch group goes **9 → 3** and its
worst slack **−2.5276 → −2.0691** **[fact]**. `docs/50`'s read register
is **more** moot than `docs/61` found it, not less.

**2. AND THE READ-ADDRESS GROUP IS NOT EMPTIED. IT IS SPLIT.**

> `SYNPRE`'s signature is unmistakable and it is the third measurement of
> it in this document: **1,514 endpoints move from an address launch to a
> stored-data launch** — `docs/49` section 6.2 item 2's finding, which is
> what hoisting the tree does. **But 1,050 endpoints still launch from
> read addresses** — 960 from `raddr_b_i[1]` and 90 from `raddr_a_i[2]`
> — **and the worst slack in the entire design, −4.5898, is on one of
> them** **[fact]**.
>
> **A restructuring that was supposed to take the read address off the
> critical path left 1,050 endpoints behind it and made the worst of them
> a nanosecond worse.** The 32-way multiplexer is still there; what
> `SYNPRE` removes from behind it is the syndrome tree, and section 3.2
> is the measurement that the syndrome tree was never the bulk of this
> path.

**3. THE MEMORY MOVED FURTHER ONTO THE CAPTURE SIDE, WHICH `docs/61`
SECTION 9.4 ITEM 1 ALREADY IDENTIFIED AS A SEPARATE POPULATION.**
Endpoints captured at an SRAM macro's own input pins — `A_ADDR`, `A_BM`,
`A_DIN` — go **303 at worst −2.9768 to 528 at worst −3.7516** **[fact]**.
**More endpoints and 0.77 ns worse.** These are paths *into* the macro; a
register on the read return does nothing for them and neither does
`SYNPRE`. It is now the third-largest capture group in the design.

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

**[fact, `checker_audit.py hw/soc/pnr/runs/syp1`, ~~exit 0~~ exit 1]** *(~~exit 0~~ exit 1; corrected 2026-09-05 by `docs/71-layout-reproducibility.md` section 9)*

**Seventeen of nineteen, the same seventeen and the same two**, as
`docs/47` section 7.3, `docs/48` section 9, `docs/49` section 10,
`docs/50` section 9 and `docs/61` section 10. `WIRE_LENGTH_THRESHOLD` is
unset in both PDKs and `ERROR_ON_LINTER_WARNINGS` is a policy with a
named key; neither is repaired here.

> **`docs/41` SECTION 6.6 CATALOGUES THE DEFECT THIS AUDIT EXISTS TO
> PREVENT, AND THE DIRECTION OF THIS DOCUMENT'S RESULT IS WHY IT STILL
> HAS TO BE RUN.** The audit's usual job is to stop a *closure* being
> read as wider than the gate behind it. **Here the result is a
> regression, so the audit is doing the opposite job: it establishes that
> `Checker.SetupViolations` examined three corners and named the same
> one, so the worse number is a worse number and not a checker that
> started looking harder.** `Checker.MaxSlewViolations` is the row where
> that could have hidden — 29 → 83 at the slow corner — and it is bound
> to `["*"]` in both runs with three corners measured in both.

**The two metrics nothing judges, read out here rather than left in a
file**, as `docs/47` section 8.6 and `docs/61` section 10 did:

- **`design__max_fanout_violation__count` = 471**, against `npu2`'s 477
  **[fact]**. There is no max-fanout checker step in the Classic flow.
- **`design__violations` = 0 and `flow__errors__count` = 0** in the
  `final/metrics.json` of a run that fails setup, max slew and max cap
  **[fact]** — `docs/23` section 3.2's finding, **reproduced a sixth
  time**.
- **`route__wirelength__max` = 2,789.72 um** with `Checker.WireLength`
  skipped. **That net is longer than the die is wide** (2,306.40 um)
  **[fact]** and 20.5 % longer than `npu2`'s. `docs/48` section 5's
  fourth finding held that this figure describes the die rather than the
  placement; **this is the first run in the record where it exceeds the
  die dimension, and that reading does not survive it.**
- **`timing__unannotated_net__count` = 428** against `npu2`'s 398
  **[fact]** — nets the extractor gave no parasitic. Nothing gates it and
  this document did not investigate which nets they are.

---

## 11. The verification obligations, re-discharged

`SYNPRE` changes the register file, so `docs/44`'s C5 and `docs/49`'s C6
and C7 apply. **They were re-run and not inherited**, and so was the
whole-SoC invariant.

### 11.1 The formal properties

`hw/soc/formal/regfile_secded.sby`, all four tasks, in this session:

| task | engine | result |
|---|---|---|
| `bmc`, depth 4 | `smtbmc yices` | **PASS** |
| `prove`, k-induction | `smtbmc yices` | **PASS**, basecase and induction |
| `prove_abc` | `abc pdr` | **PASS** |
| `cover` | `smtbmc yices` | **PASS, 9 of 9 reached** |

**[fact, `hw/soc/formal/regfile_secded_*/PASS`]** — `docs/49` section
9.1's result, unchanged, including the two covers that stop C6 and C7
holding vacuously. **C6 was not re-mutation-tested**; `docs/49` did that
and nothing in this document changed the property, the harness or the two
H matrices it compares.

### 11.2 The behavioural evidence, and the whole-SoC invariant

| | baseline at HEAD | **`SOC_RF_SYNPRE=1`** |
|---|---|---|
| register-file cocotb suite | — | **6 of 6 pass** |
| its 124-injection campaign | — | **107 CORRECTED, 17 MASKED, 0 SDC, 0 DETECTED, 25 draws into the check field** |
| whole-SoC run: checks / fail mask | 0x1b / 0 | **0x1b / 0** |
| watchdog stage 1 at cycle | 174,208 | **174,208** |
| core asleep after | 215,428 cycles | **215,428 cycles** |
| console | 760 characters, 0 framing errors | **760, 0** |
| NPU line | `0x0c events, cnt=0x000c0016, status=0x2a` | **identical** |
| the two `sim.log` files | | **differ in one line, which is the output path** |

**[fact]**

> **THE INJECTION CAMPAIGN IS `docs/49` SECTION 9.2's AND `docs/43`'s,
> FIELD FOR FIELD.** 107 / 17 / 0 / 0 and 25 check-field draws, on the
> third document to run it.
>
> **THE WHOLE-SoC ROW IS NOT `docs/49`'s AND MUST NOT BE COMPARED TO IT.**
> That document reports **22 checks, watchdog stage 1 at 174,128, asleep
> after 185,443 cycles, 587 console characters**. **Those figures are for
> a `soc_top` with no accelerator in it** — `docs/51` landed after
> `docs/49` — so the invariant this document has to hold constant is
> **HEAD's**, and HEAD's was measured here in the same session by running
> the baseline beside the change rather than by reading it out of an
> earlier document. **The whole-SoC invariant did not move: 27 checks,
> fail mask 0, and three cycle counts identical to the digit.**
>
> **AND THE ARM CHECK FIRED, WHICH IS WHY THAT ROW MEANS ANYTHING.**
> `docs/49` section 8.1 found that `iverilog -P` on a hierarchical path
> elaborates, exits 0 and changes nothing, and reported a
> "cycle-identical" result from a design without the change in it. The
> repair it built is a check of the compiled object, and it printed
> **`== register file read path: g_synpre (SOC_RF_SYNPRE=1)`** for the
> change and **`g_synpost (SOC_RF_SYNPRE=0)`** for the baseline
> **[fact]**. **The eleventh entry in `docs/41` section 6.6's list is
> still repaired.**

### 11.3 The repository's own guards

`sw/tests/test_soc_regfile_guards.py`,
`sw/tests/test_soc_synthesis_guards.py` and `sw/tests/test_doc_links.py`:
**135 passed** **[fact]**. The first of those is `docs/49`'s assertion
that nothing in the design *sets* `SYNPRE`, and it still passes, because
this document sets it in a flow invocation and not in the design.

---

## 12. Corrections to earlier documents

1. **`docs/61` section 9.3's "+4.4 %" area estimate is wrong and the
   measured figure is +4.9406 %**, on +30,850.4322 um2 rather than the
   +27,237.7728 um2 it carried forward from `docs/49` **[fact]**. Not an
   error of measurement — that document labelled it **[estimate]** and
   stated its derivation — but an inherited absolute number on a
   re-measured denominator. Section 5.
2. **`docs/61` section 9.3's reversal of `docs/49` is itself half
   right.** The binding path does run through the cone `SYNPRE`
   restructures; it **also** runs through `u_enc_wr`, the write encoder
   `docs/49` section 3.2 identified as untouchable, and that half carries
   most of the path's XOR **[fact for the path composition, estimate for
   the split]**. **`docs/49`'s conclusion is restored on a new
   mechanism** rather than reversed. Section 3.2.
3. **`docs/49` section 5.2 item 1's +3.4641 ns at post-CTS is scoped to
   `docs/47`'s design and does not generalise.** On this design the same
   stage moves **−0.2014 ns** **[fact]**. That document called it *"the
   largest single-change improvement measured anywhere on this design"*
   and the qualifier was doing more work than it looked like.
4. **`docs/49` section 5.2 item 3's spreading mechanism has changed form
   and not gone away.** "Cells / their own bounding box" goes **up** here
   (19.27 % → 20.01 %) where that document measured it going down
   (27.0 % → 22.1 %), because the design already fills the core; **the
   +25.07 % of HPWL arrives as congestion instead** — final weighted
   congestion **0.9960 → 1.0424** and routability inflation **+1.79 % →
   +9.67 %** **[fact]**. This is also the second measurement, after
   `docs/61` section 7.2, that "cells / their own bounding box" is not a
   predictor of anything.
5. **`docs/49` section 7's third finding — that `SYNPRE` makes
   `RepairDesignPostGRT` behave like the baseline — does not hold on this
   design.** That step found **94 capacitance violations and inserted 109
   buffers in 128 nets** there against the baseline's 101 / 110 / 127;
   here it finds **128 and inserts 132 in 148 nets** against `npu1`'s
   **77 / 76 / 101** **[fact]**. `SYNPRE` now makes measurably more work
   for the global repair step, which is one of the three reasons that
   document gave for declining to compose it with a capacitance
   constraint — and the reason is stronger, not weaker.
6. **`docs/48` section 5's fourth finding, that `route__wirelength__max`
   describes the die rather than the placement, does not survive this
   run.** It is **2,789.72 um on a die 2,306.40 um wide** **[fact]**,
   where every previous run in the record produced a figure just under
   the die dimension. Section 10.
7. **`docs/23` section 3.2's finding that `design__violations` does not
   aggregate is reproduced a sixth time.** Section 10.
8. **`docs/61` section 18 item 2's framing of the question is superseded
   by its answer.** It asked whether routing would still take the
   +3.4641 ns back; the measurement is that the gain does not appear at
   post-CTS at all, so the question of what routing does to it does not
   arise. Section 7.1.

---

## 13. What this does NOT cover

- **`SYNPRE` WAS MEASURED AT ONE POINT IN THE CONFIGURATION SPACE**,
  `docs/61`'s floorplan with `docs/61`'s keys and one generated density.
  It was not combined with a different channel, a different `abc -D`, a
  resynthesis at a different clock target or a max-capacitance
  constraint. **`docs/49` section 7 declined the capacitance composition
  on three measured grounds and section 12 item 5 above finds one of them
  stronger here; the run was not made and this document does not claim
  what it would do.**
- **ONE NETLIST, ONE PLACEMENT, ONE CLOCK TREE, ONE ROUTING SOLUTION.**
  `docs/44` section 5.2 measured this flow's mapper noise at about 0.4 ns
  on a 22,000-cell design; nothing has re-measured it at 44,000, and the
  −1.0109 ns is reported against that older figure rather than against a
  repeated run of this configuration, which does not exist. **The
  regression is 2.5x that noise floor and would survive a considerably
  larger one, but it has not been reproduced.**
- **THE DECOMPOSITION OF THE BINDING PATH'S XOR CONTENT IS AN ESTIMATE.**
  Section 3.2's "at most three of fourteen" subtracts a count made by
  `docs/49` on `docs/47`'s design from a count made here on `docs/61`'s.
  The netlist is flat and anonymous — `docs/59` section 6 and `docs/61`
  section 5.2 — so **the path cannot be attributed to modules cell by
  cell in this database**, and it was not.
- **THIS IS NOT A PHYSICAL SIGN-OFF.** `RUN_MAGIC_DRC`,
  `RUN_KLAYOUT_DRC`, `RUN_KLAYOUT_XOR` and `RUN_LVS` are all **0**
  **[fact]**, for the reason `docs/12` sections 7.5 and 8 measured —
  1,106,478 Magic DRC, 2,316 KLayout DRC and 359 Netgen LVS errors over
  **one** RM_IHPSG13 macro, and a recorded **NO-GO** — and `docs/54`
  section 7 found the KLayout exit shut as well. Nothing on this die has
  ever been checked for manufacturability.
- **NOTHING HERE WAS SIMULATED AT THE GATE LEVEL.** `docs/49` section
  12's *"nothing has ever simulated `soc_top`'s netlist"* is unchanged.
  Section 11's evidence is RTL.
- **NO POWER NUMBER WAS MEASURED.** `docs/61` section 18 item 1's
  obligation is untouched, and this run's netlist and SPEF do not change
  that.
- **NO CAMPAIGN WAS RE-RUN.** `docs/61` section 12's statement stands:
  `docs/42`, `docs/43`, `docs/46`, `docs/52`, `docs/55` and `docs/56`
  report distributions for a design that has since changed. Section 11.2
  re-runs the **register file's** 124-injection campaign, which is a
  check that `SYNPRE` changes no fault outcome, and nothing else.
- **THE FAST CORNER'S MACRO LIBERTY IS CHARACTERISED AT −55 C WHERE THE
  STANDARD CELLS ARE AT −40 C** (`docs/12` section 6.4a), so every
  fast-corner figure carries `docs/47` section 9's 15 C mismatch.
- **`SYNPRE` PROTECTS NOTHING NEW AND DETECTS NOTHING NEW.** It is a
  timing restructuring of a correction path, proved equal (section 11.1),
  and section 11.2's campaign is a check that nothing moved rather than
  evidence of anything gained.
- **ONE CLOCK, ONE MODE, NO SCAN, NO TEST.**

---

## 14. Cost

Quoted as costs and not as benchmarks, on a shared 20-thread host that
was running another project's OpenROAD throughout **[fact, `ps`]**.

| | `docs/61`, `npu1` + `npu2` | **`syp1`** | ratio |
|---|---:|---:|---:|
| synthesis, `SOC_MEM=sram IBEX_RF_SYNPRE=1` | 44.1 s | **39.5 s** | |
| **summed step runtime** | **135.9 min** | **230.0 min** | **1.69x** |
| **post-CTS timing resizer** | **22 min 09.9 s** | **2 h 04 min 04 s** | **5.60x** |
| post-GRT timing resizer | 27 min 53.2 s | **43 min 43.3 s** | 1.57x |
| detailed routing | 49 min 25.2 s | **33 min 36.4 s** | **0.68x** |
| global routing | 33.4 s | **31.8 s** | |
| clock-tree synthesis | 35.6 s | **36.3 s** | |
| global placement | 42.1 s | **32.9 s** | |
| RCX + sign-off STA | — | **10.4 s + 50.3 s** | |
| `Magic.WriteLEF` | 9 min 37.6 s | **7 min 30.0 s** | |
| **the whole exercise end to end** | about 4 h | **about 4.5 h**, of which **3 h 50 min is summed LibreLane step runtime** | |

**[fact for every figure that carries a unit to the tenth of a second]**

> **THE 5.60x ON ONE STEP IS `docs/49` SECTION 7.1's FINDING REPRODUCED
> ON A DIFFERENT STEP AND A DIFFERENT DESIGN.** That document measured
> **16.9x** on the post-GRT resizer and wrote: *"whatever `SYNPRE` costs
> in area, it costs more in the flow"*. Here the post-GRT resizer is only
> 1.57x and the **post-CTS** resizer is 5.60x, so the step that absorbs
> it moved; the statement did not. **A +4.94 % netlist made the targeted
> timing repair take an hour and three-quarters longer** **[fact, two
> `runtime.txt` on a shared host]**.
>
> **And detailed routing got FASTER, which is worth recording because it
> is the opposite of what section 7.3's congestion figures predict.**
> 33 min 36 s against 49 min 25 s, from **more** starting violations
> (32,902 against 32,412) to the same 0 **[fact]**. **This document did
> not investigate it** and does not offer a mechanism; on a shared host
> a single runtime comparison is weak evidence in either direction.

---

## 15. Files touched

| File | Change |
|---|---|
| `hw/soc/pnr/config-synpre.json` | generated by `floorplan.py`; one key differs from `config-npu.json` |
| `docs/62-synpre-remeasured.md` | this document |
| `docs/00-index.md` | one row |

**No file under `hw/rtl/`, `hw/tb/`, `tt/`, `formal/`, `hw/openlane/`,
`hw/soc/rtl/`, `hw/soc/flow/`, `hw/soc/formal/` or `sw/` was modified**
**[fact, `git status`]**. In particular **`hw/soc/rtl/ibex_regfile_secded.v`
is untouched**: `SYNPRE` and its `g_synpre` block have been in that file
since `docs/44`, `docs/49` made them reachable from two flows, and this
document only set the variable.

`hw/rtl/pilot_top.v`, `lif_core.v`, `aer_fifo.v`, `scrub.v`,
`tmr_voter.v`, `secded_enc.v` and `secded_dec.v` are **read** and
instantiated in place. `hw/openlane/checker_audit.py` and
`hw/openlane/signoff_report.py` are **executed** and not modified. No run
directory under `hw/openlane/` was created, resumed or touched.
`hw/soc/out/`, `hw/soc/pnr/runs/`, `hw/soc/pnr/config.resolved.json` and
`hw/soc/tb/cocotb/sim_build*/` are gitignored.

---

## 16. Reproducing this

```
V=$HOME/Documents/caravel-lif-crossbar/.venv-flow/bin/python
export PDK_ROOT=$HOME/.ciel

# ---- 0. the instruments, before anything is claimed to move ----------
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/npu2   # -3.5789 / 2175
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/npu2   # 17 of 19
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/syn2   # -3.0838 / 1783
python3 hw/soc/pnr/violator_census.py hw/soc/pnr/runs/npu2 --top 12
#   1,718 raddr_b_i[3] worst -3.5789; 415 raddr_b_i[2]; 9 on a macro
python3 hw/soc/pnr/floorplan_map.py --run hw/soc/pnr/runs/npu2 --no-write
#   fill 117,780; channel 50.44 %; 4,352,524 transistors; 18 of 18 checks
awk '$NF=="cells"{c=$1} $NF~/^sg13g2_(s?df|dl[hl])/{f+=$1} \
     /Chip area for module/{gsub(/[^0-9.]/,"",$NF); a=$NF+0} \
     END{print c,f,a}' hw/soc/out/s61-sram/area.rpt   # 42518 5263 624429.918
python3 hw/soc/pnr/floorplan.py --channel 700.08 --density 40 \
        --write /tmp/fp0.json                          # byte for byte

# ---- 1. the netlist --------------------------------------------------
SOC_MEM=sram IBEX_RF_SYNPRE=1 hw/soc/flow/syn_soc_top.sh 20 \
        hw/soc/out/s62-synpre
#   44,107 cells, 5,263 flops, 655,280.3502 um2  -> +4.9406 %

# ---- 2. the floorplan, sized against THAT netlist --------------------
python3 hw/soc/pnr/floorplan.py --channel 700.08 --cell-area 655280.3502 \
        --write hw/soc/pnr/config-synpre.json
#   31.32 % pre-repair, PL_TARGET_DENSITY_PCT 49; the generator asserts
#   that it changed that key and no other

# ---- 3. the run, one directory, no resume ----------------------------
python3 -c "import json,os; json.dump({'nl': os.path.abspath(
  'hw/soc/out/s62-synpre/soc_top.netlist.v'), 'metrics': {}},
  open('hw/soc/pnr/state/syn_soc_top.state.json','w'), indent=1)"

SYN_NETLIST=$PWD/hw/soc/out/s62-synpre/soc_top.netlist.v \
PNR_CONFIG=$PWD/hw/soc/pnr/config-synpre.json \
hw/soc/flow/pnr_soc_top.sh syp1 --overwrite \
    -F Yosys.JsonHeader -S Yosys.Synthesis \
    -S Checker.YosysUnmappedCells -S Checker.YosysSynthChecks \
    -S Checker.NetlistAssignStatements \
    -i hw/soc/pnr/state/syn_soc_top.state.json
#   230.0 min of summed step runtime; the post-CTS resizer alone is 2 h 04

# what the configuration actually changed, asserted rather than described
python3 -c "
import json
a=json.load(open('hw/soc/pnr/runs/npu1/resolved.json'))
b=json.load(open('hw/soc/pnr/runs/syp1/resolved.json'))
print(sorted(k for k in a if a[k]!=b[k] and not k.startswith('//')))"
#   ['PL_TARGET_DENSITY_PCT']

grep -m1 "timing derate" hw/soc/out/s62-pnr-syp1.log     # 5.0%

# ---- 4. the reports --------------------------------------------------
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/syp1   # -4.5898 / 2607
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/syp1   # 17 of 19
python3 hw/soc/pnr/violator_census.py hw/soc/pnr/runs/syp1 --top 14
python3 hw/soc/pnr/floorplan_map.py --run hw/soc/pnr/runs/syp1 --no-write
#   --no-write is not optional: docs/img/ is docs/59's artefact

# the stage table, both runs, same step indices
for r in npu1 syp1; do for s in 23-openroad-stamidpnr \
    28-openroad-stamidpnr-1 30-openroad-stamidpnr-2; do
  python3 -c "
import json;m=json.load(open('hw/soc/pnr/runs/$r/$s/or_metrics_out.json'))
print('$r','$s',m['timing__setup__ws__corner:nom_slow_1p08V_125C'])"; done; done

# ---- 5. the evidence -------------------------------------------------
cd hw/soc/formal && make regfile && cd ../../..   # 4 tasks, 9 of 9 covers
cd hw/soc/tb/cocotb && make -f Makefile.ibex_regfile_secded \
     EXTRA_COMPILE_ARGS=-Pibex_register_file_ff.SYNPRE=1 \
     SIM_BUILD=sim_build_regfile_s62 \
     COCOTB_RESULTS_FILE=results_regfile_s62.xml && cd ../../../..
#   6 of 6; 124 injections: 107 CORRECTED, 17 MASKED, 0 SDC, 0 DETECTED

hw/soc/flow/sim_soc.sh                 hw/soc/out/s62-sim-base
SOC_RF_SYNPRE=1 hw/soc/flow/sim_soc.sh hw/soc/out/s62-sim-synpre
diff hw/soc/out/s62-sim-{base,synpre}/sim.log   # one line, the path
grep "register file read path" hw/soc/out/s62-sim-synpre.log   # g_synpre

# ---- 6. the guards ---------------------------------------------------
.venv/bin/python -m pytest sw/tests/test_soc_regfile_guards.py \
    sw/tests/test_soc_synthesis_guards.py sw/tests/test_doc_links.py
```

`hw/soc/out/` and `hw/soc/pnr/runs/` are gitignored, so the durable
record is this document and the generated `hw/soc/pnr/config-synpre.json`.

---

## 17. What the next block should be

**`SYNPRE` is now closed, and that is the first item.**

> **DO NOT MEASURE `SYNPRE` AGAIN ON THIS DESIGN.** `docs/44` declined it
> and wrote a reversal condition; `docs/49` measured it, declined it and
> wrote a sharper one; `docs/61` met that condition; **this document met
> the obligation and the answer is a nanosecond in the wrong direction
> for +4.94 % of the area and 1.69x of the flow.** Three documents have
> now priced the same parameter and the price has gone up each time.
> **The reversal condition this document writes is narrow and it is not
> about the register file**: `SYNPRE` becomes worth re-measuring only if
> the **write encoder** stops terminating the binding path — section 3.2
> — and nothing in this record proposes to move it.

1. **`report_power` against a routed netlist with the accelerator in
   it.** `docs/61` section 18 item 1, **untouched here and still first**.
   `docs/57` section 9's **49.7 mW busy and 31.0 mW idle** are ratios
   from an unrouted netlist and that document called them its weakest
   numbers; `hw/soc/pnr/runs/npu2` is the artefact that makes them
   measurable and `hw/soc/flow/power_soc_top.sh` is in the tree.
   **Nothing in this document changes that ranking and this run is not
   the netlist to measure it on** — `npu2` is the design, `syp1` is an
   experiment that failed.
2. **`mtime`, and it should stop being deferred.** Ranked by `docs/41`,
   `docs/44`, `docs/43`, `docs/45`, `docs/47`, `docs/48` and `docs/49`,
   and **this document measures it at both ends of the post-CTS binding
   path in both runs** (section 7.2). And the two-hour post-CTS resizer
   names its current worst endpoint 830 times: **577 of those are
   `u_clint.g_mtime_secded.u_mtime_dec.check_raw` or `s_rdata_clint`,
   241 are register-file check bits and 7 are in `u_npu`** **[fact,
   resolving every `_NNNNN_/D` in the step log against the netlist]**.
   It is the most-deferred item in the record and it is now the only
   structural candidate left that the physical documents have repeatedly
   named and nobody has priced.
3. **The max-capacitance constraint, against max slew.** `docs/61`
   section 18 item 3, unchanged: **0.1080 pF and 0.1800 pF are still
   unrun**, max slew on the design that exists is **29 / 8 / 6**, and
   hold no longer needs the package. **This document adds one input to
   it**: section 12 item 5 measures `RepairDesignPostGRT` finding 66 %
   more capacitance violations and inserting 74 % more buffers on a
   `SYNPRE` netlist, which sharpens `docs/49` section 7's
   reason for not composing the two — but the constraint on the
   **baseline** netlist is untouched by any of that.
4. **A taller channel.** `docs/61` section 18 item 4, and **this document
   strengthens the case for it rather than answering it**. That document
   ranked it after items 2 and 3 *"because both change the cell count the
   floorplan would be sized against"*; **item 2 there is now closed, so
   one of the two reasons to wait is gone.** Section 7.3 measures the
   placer going from a final weighted congestion **below** its target to
   **above** it on +4.94 % of cells, which is the clearest evidence in
   the record that this die's channel is the binding resource.
5. **`hw/soc/formal/soc_bus.sby` green at HEAD, then the second clock
   gate.** `docs/61` section 18 item 5, untouched here and **still not
   checked**. `docs/50` section 8.1 found that suite failing for three
   documents.
6. **`docs/59`'s map regenerated against `npu2`'s die**, `docs/61`
   section 18 item 6. `floorplan_map.py` produces every number and passes
   all eighteen of its checks on both `npu2` and `syp1` **[fact]**; only
   the SVG is unwritten.
7. **The campaigns, re-run**, and **one source list derived from the
   top** — `docs/61` section 18 items 7 and 8, unchanged.
8. **`.A_REN(req_i && !do_write)`** — `docs/57` section 8.3's six AND
   gates and 0.147 mW, *"the cheapest measured saving in this document"*,
   still one line and still not done.

**And what is still blocked, unchanged by this document.** DRC, LVS and
XOR, on `docs/12`'s NO-GO and `docs/54`'s closed exit. A gate-level
simulation of `soc_top`, on the boot ROM's contents. ECC on the memories.
**None of the three moved and none of them is nearer.**
