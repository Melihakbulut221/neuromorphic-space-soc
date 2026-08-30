# 23 — The twelve-tile shape decision: 3x4 against 6x2, measured

Status: complete. Both twelve-tile shapes are hardened end to end on
ihp-sg13g2 and on sky130A, four full sign-offs, all four clean on every
deck. The submission is moved from **4x2 to 6x2**. One repository guard
now fails as a direct consequence and is left failing; section 9.

Supersedes the tile figures in `docs/15` section 4 and the shape
estimates in the wave-6 brief. **No document from `docs/00` to `docs/22`
is edited here**, and `docs/06` section B.6's open question about
purchasability is answered as far as the public tooling allows and left
open where it cannot be.

### Headline

- **The estimates were wrong by a factor, and in the safe direction.**
  The planning estimate for this decision was 60.2 % utilization on 3x4
  and 67.4 % on 6x2. Measured: **41.92 % on 3x4** and **47.29 % on
  6x2**. Section 2.3 reproduces the estimate's arithmetic exactly and
  shows what happened — the 70 % criterion was applied twice, so both
  estimates are the true figure divided by 0.70.
- **Both shapes hold the design with room to spare, so utilization does
  not decide this.** Against the 70 % planning criterion 3x4 is
  **+178,050 um2 spare** and 6x2 is **+127,502 um2 spare**, where 4x2 is
  **-5,527 um2 short**. Both are comfortable; the 5.4-point gap between
  them buys nothing.
- **Routing decides it, and 6x2 routes better.** 6x2 converged in **one
  detailed-route pass of five iterations**, 4,256 -> 2,291 -> 2,059 ->
  134 -> 0, and needed **zero antenna diodes**. 3x4 needed **two passes
  and eleven iterations** and one diode. Neither shows anything like the
  sky130 4x2 trajectory. Section 4.
- **Timing decides it too.** 6x2 closes with **zero setup, hold,
  max-slew and max-cap violations on all three corners** and the best
  slow-corner slack of any harden of the current netlist, **+1.2347 ns**
  against 4x2's +0.9121 and 3x4's +1.0593. 3x4 carries **one hold
  violation of -6.27 ps** at the fast corner — small, and the flow did
  not stop for it, but it is the first non-zero violation counter in an
  IHP sign-off here. Section 3.
  *Corrected 2026-08-30: all four slacks in this bullet are un-derated,
  because the flow never applied the 5 % OCV derate it reported
  applying (`docs/28` §4.4b). Derated they are 6x2 **+0.2913**, 3x4
  **+0.0919**, 4x2 **-0.0675** — so **4x2 does not close the slow
  corner at all** and the 3x4 hold violation grows to -57.71 ps. The
  ranking, and therefore this bullet's conclusion, is unchanged and
  better supported. Section 3.1's correction note has the derivation.*
- **Cross-PDK portability is measurable again.** `docs/22` section 5
  could not re-measure it because sky130 4x2 stopped routing. At twelve
  tiles it routes: sky130 **6x2 and 3x4 both close DRC-clean on every
  deck**, global-route overflow **0** against 4x2's **22,357**. The
  sky130 slow-corner setup miss that `docs/18` records is still there
  and is now **-7.31 ns**. Section 5.
- **3x4's purchasability on TTIHP26b could not be confirmed, and that is
  not the reason 6x2 wins.** 6x2 would win on the measurement alone.
  The availability question is section 7 and is left open as a question
  for Tiny Tapeout rather than answered from the tooling.
- **The cost is EUR 840 against the EUR 560 `docs/06` carries**, a
  **+EUR 280** delta, identical for either shape. Section 8.

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

No mismatch warning. The flow is the rootless LibreLane of `docs/12`
section 2.1, unchanged from `docs/20` section 1.1 and `docs/22` section
1.1:

| Component | Version | Where it is pinned |
|---|---|---|
| LibreLane | 3.0.5 | `~/Documents/caravel-lif-crossbar/.venv-flow` |
| Yosys (in-flow) | 0.67 | LibreLane wheel |
| Yosys (guards, `tools.mk`) | 0.67+146 | `OSS_CAD_SUITE` pin |
| ihp-sg13g2 PDK | `c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c` | LibreLane `pdk_hashes.yaml`, asserted by `run_ihp.sh` |
| sky130A PDK | `8afc8346a57fe1ab7934ba5a6056ea8b43078e71` | same, asserted by `run_sky130.sh` |
| Magic | 8.3.678 | `~/.local/opt/magic-8.3.678` |
| tt-support-tools | `01d5d2814fa9dd61e9d211e0b235a4a592a9316a` | `tt/tt/` clone; also upstream `main` HEAD, section 7.2 |

**[fact]** for every row. Both run scripts read the PDK hash out of the
installed wheel and refuse to start on a mismatch.

### 1.2 Sources: the blob list, pinned

Every run here is pinned with `hw/openlane/pin_rtl.py` against commit
**`e1361fe`** and reads a disposable snapshot by absolute path, never
`hw/rtl`, per the `docs/20` section 1.2 mechanism:

```
c6f26c165faa81c97a27bce6644bc670f3b36542  hw/rtl/aer_fifo.v
b196828f65c271d849cad0ad21536c561d2079af  hw/rtl/lif_core.v
e6c1e646643840e2a553924b56dfab64022e5c39  hw/rtl/npu_regbank.v
9aaaa394e7a6ef855f5584fb85d53e688ac3e0b5  hw/rtl/npu_regs.vh
a1fdc4ce9dedb0f3635749953cb3e929a39d7703  hw/rtl/pilot_top.v
89e62789ad016c7cb51ad69247f6066335074f8c  hw/rtl/scrub.v
f7c7ec187a0df4eb09a8405dcda285de0fc2e44e  hw/rtl/secded_dec.v
b5710b8a679c3e378e74953b621b99f0d8dc3014  hw/rtl/secded_enc.v
62b5f4d2a1eae095d9d4a8634ede55237e2c924d  hw/rtl/tmr_voter.v
e294afcf03e1947906086beeba2fd0c40b29441d  hw/rtl/tt_um_melihakbulut_nssoc.v
```

**[fact, `hw/openlane/pin_rtl.py e1361fe`, which prints the blob of every
file it writes]**. This is the same RTL `docs/22` section 9 hardened —
`e1361fe` is the commit that recorded that run and changed no source —
so the netlist here is directly comparable to `wave5-ihp-b` and the
whole difference between the runs is the tile shape.

**The tree moved under this work, for the fourth time, and again it did
not matter.** A concurrent session committed **`d2ab1b6`** ("Finish the
wave-5 re-harden record, and correct the shortfall figure") while these
runs were executing. It touches `docs/22-reharden-wave5.md` and nothing
else: `git diff --stat e1361fe d2ab1b6` is one file, and
`git ls-tree e1361fe:hw/rtl` and `git ls-tree d2ab1b6:hw/rtl` are
identical blob for blob **[fact]**. Every number below is therefore
current at `d2ab1b6` as well as at `e1361fe`.

### 1.3 The runs

| Tag | Path | PDK | Shape | Config |
|---|---|---|---|---|
| `shape-3x4` | `hw/openlane/pilot_ihp/runs/shape-3x4` | ihp-sg13g2 | 3x4 | `pilot_ihp/config.3x4.json`, pinned |
| `shape-6x2` | `hw/openlane/pilot_ihp/runs/shape-6x2` | ihp-sg13g2 | 6x2 | `pilot_ihp/config.6x2.json`, pinned |
| `sky-10-3x4` | `hw/openlane/pilot_sky130/runs/sky-10-3x4` | sky130A | 3x4 | `pilot_sky130/config.3x4.json`, pinned |
| `sky-09-6x2` | `hw/openlane/pilot_sky130/runs/sky-09-6x2` | sky130A | 6x2 | `pilot_sky130/config.6x2.json`, pinned |

The two IHP configs are generated by `hw/openlane/pilot_ihp/mkconfig.py`
from the submission's own `tt/src/config_merged.json`, as `docs/20`
section 2 established. **Exactly three keys differ from the baseline**:
`DIE_AREA` and `FP_DEF_TEMPLATE`, both copied out of
`tt/tt/tech/ihp-sg13g2/` so they cannot drift from the tile definition
tt-support-tools itself would use, and `RUN_KLAYOUT_DRC`, raised to 1 so
that one run per shape yields the whole sign-off set instead of needing
the separate second pass `docs/22` section 2.4 had to make. Everything
else — `CLOCK_PERIOD: 20`, `PL_TARGET_DENSITY_PCT: 60`,
`SYNTH_HIERARCHY_MODE: deferred_flatten`, the margin multipliers, the
PDN pitch — is the submission's value **[fact, `mkconfig.py --check`
reports no drift]**. `deferred_flatten` is required and not cosmetic;
`docs/20` section 3.3 measures what it costs and nothing here revisits
it. Both runs report `design__instance_unmapped__count: 0`.

The two sky130 configs are generated by
`hw/openlane/pilot_sky130/mkvariant.py` from that directory's 4x2
baseline, with the same two geometry keys taken from
`tt/tt/tech/sky130A/`. That baseline already runs the KLayout deck and
the XOR, per its own `//signoff` comment.

Every number below is extracted with `hw/openlane/signoff_report.py`
and `hw/openlane/route_trace.py` rather than by hand-grep, so runs being
compared are read the same way. `route_trace.py` is new here and section
4.1 says why it had to exist.

### 1.4 The shapes themselves

Read straight out of `tt/tt/tech/*/tile_sizes.yaml`, not computed from a
tile pitch **[fact]**:

| | IHP 4x2 | **IHP 3x4** | **IHP 6x2** | sky 4x2 | **sky 3x4** | **sky 6x2** |
|---|---|---|---|---|---|---|
| `DIE_AREA` | 854.40 x 313.74 | 636.96 x 710.64 | 1289.28 x 313.74 | 682.64 x 225.76 | 508.76 x 511.36 | 1030.40 x 225.76 |
| Die area, um2 | 268,059 | **452,649** | **404,499** | 154,113 | **260,160** | **232,623** |
| Aspect | 2.72 | **1.12** | **4.11** | 3.02 | **1.01** | **4.56** |
| Tiles | 8 | **12** | **12** | 8 | **12** | **12** |

3x4 is **11.90 %** more IHP silicon than 6x2 for the same tile count and
the same price. On sky130 the same comparison is **+11.84 %**. That the
two ratios nearly coincide is read off the two files, not carried from
one to the other.

---

## 2. Area and utilization

### 2.1 The sign-off table, both shapes beside the 4x2 they replace

`wave5-ihp-b` is the correct predecessor: same RTL, same flow, same
submission config, 4x2. It is `docs/22` section 9.

| Quantity | `wave5-ihp-b` (4x2) | **`shape-3x4`** | **`shape-6x2`** |
|---|---|---|---|
| Mapped flip-flops | 1,275 | **1,275** | **1,275** |
| Flip-flop cell type | all `sg13g2_dfrbpq_1` | all `sg13g2_dfrbpq_1` | all `sg13g2_dfrbpq_1` |
| Synthesis cells | 9,821 | 9,821 | 9,821 |
| Synthesis cell area, um2 | 151,789.11 | 151,789.11 | 151,789.11 |
| Placed cells, excl. fill | 12,424 | **12,449** | **12,418** |
| Instances incl. fill | 23,685 | **37,923** | **33,801** |
| Sequential cells | 1,275 | 1,275 | 1,275 |
| Timing-repair buffers | 2,414 | **2,417** | **2,430** |
| of which hold buffers | 1,388 | **1,402** | **1,406** |
| **Placed cell area, um2** | 185,755 | **186,014** | **185,840** |
| Die area, um2 | 268,059 | **452,649** | **404,499** |
| Core area, um2 | 259,837 | **443,784** | **392,988** |
| **Utilization** | **71.4890 %** | **41.9155 %** | **47.2887 %** |
| Routed wirelength, um | 480,088 | **464,085** | **469,914** |
| Summed step runtime | 37.2 min | 55.8 min | 32.3 min |

Synthesis is identical across all three, to the cell and to two decimal
places of area, which is the expected result and worth stating: the tile
shape is a floorplan input and cannot reach Yosys. The placed cell area
differs by **259 um2 across the three, 0.14 %**, which is resizer noise,
not a shape effect. **What changes is the denominator, and only the
denominator** **[fact]**.

The instance count including fill rises sharply with die area — 23,685
at 4x2 to 33,801 at 6x2 to 37,923 at 3x4 — because the extra rows are
filled with decap and tap cells. That is not design growth.

### 2.2 Against the 70 % planning criterion

The criterion is `docs/15` section 4's: the design should not need more
than 70 % of the available placement rows. At 185,840 um2 placed the
design needs **265,486 um2** of core.

| Shape | Core offered | Needed at 70 % | Spare | Spare as % of core |
|---|---|---|---|---|
| 4x2 | 259,837 | 265,364 | **-5,527 um2** | **-2.13 %** |
| **3x4** | **443,784** | 265,734 | **+178,050 um2** | **+40.12 %** |
| **6x2** | **392,988** | 265,486 | **+127,502 um2** | **+32.44 %** |

**[fact]** for the cores and the placed areas; the criterion itself is a
planning choice, not a measurement.

Both twelve-tile shapes clear the criterion with a very large margin.
3x4's extra 50,796 um2 of core is real, and it is worth **7.68 points**
of additional spare — but the design is already 32 points clear at 6x2.
**Utilization cannot decide this comparison**, and the rest of this
document is about what can.

### 2.3 The estimate was high by exactly 1/0.70, and here is the arithmetic

The estimate this work was asked to check was 60.2 % on 3x4 and 67.4 %
on 6x2. Measured: 41.92 % and 47.29 %. The estimate is high by 18.3 and
20.1 points respectively, which is not a small modelling difference and
is worth explaining rather than just correcting.

Scaling `wave5-ihp`'s core-to-die ratio, 259,837 / 268,059 = 0.96933,
onto the two dies gives estimated cores of 438,764 um2 (3x4) and 392,092
um2 (6x2). The measured cores are 443,784 and 392,988 — the 6x2 estimate
is within **0.23 %** and the 3x4 estimate within **1.13 %**, so the
core-scaling step was sound. Then:

```
264,241 / 438,764 = 60.22 %      264,241 / 392,092 = 67.39 %
```

which reproduces **60.2 %** and **67.4 %** to the last digit printed
**[fact, arithmetic]**. 264,241 um2 is `docs/22` section 4's "core
needed at 70 %" for the `c5a5a6e` netlist.

So the numerator was the **area required at the 70 % criterion**, not
the **placed cell area**. Dividing a 70 %-inflated requirement by the
core gives utilization / 0.70, and 41.92 / 0.70 = 59.9 and 47.29 / 0.70
= 67.6. **The criterion was applied twice.** **[inference, but the
arithmetic reproduces both published figures exactly, which makes any
other explanation a coincidence to four significant figures.]**

The error was conservative — it made both shapes look tighter than they
are — so no decision taken on it was unsafe. It is recorded because the
same scaling appears in `docs/15` section 4.5's growth-factor column and
should be re-derived rather than reused.

---

## 3. Timing

### 3.1 All three IHP corners, both shapes

20 ns clock, post-PnR STA on extracted parasitics, all figures in ns.

| Corner | Metric | `wave5-ihp-b` (4x2) | **`shape-3x4`** | **`shape-6x2`** |
|---|---|---|---|---|
| `nom_slow_1p08V_125C` | setup WNS | +0.9121 | **+1.0593** | **+1.2347** |
| | setup violations | 0 | 0 | 0 |
| | hold WNS | +0.6218 | +0.6092 | +0.6039 |
| | hold violations | 0 | 0 | 0 |
| `nom_typ_1p20V_25C` | setup WNS | +7.8999 | +7.9845 | **+8.1297** |
| | setup violations | 0 | 0 | 0 |
| | hold WNS | +0.3004 | +0.2166 | +0.2907 |
| | hold violations | 0 | 0 | 0 |
| `nom_fast_1p32V_m40C` | setup WNS | +11.9855 | +12.0483 | **+12.1329** |
| | setup violations | 0 | 0 | 0 |
| | hold WNS | +0.1180 | **-0.0063** | +0.1089 |
| | **hold violations** | **0** | **1** | **0** |
| all three | max-slew violations | 0 | 0 | 0 |
| all three | max-cap violations | 0 | 0 | 0 |

**[fact, `signoff_report.py` on each run's `final/metrics.json`]**

Slow-corner Fmax, from the slow-corner WNS: 4x2 **52.4 MHz**, 3x4
**52.8 MHz**, 6x2 **53.3 MHz**.

> **Corrected 2026-08-30 — every slack in the table above is an
> un-derated number, and one of the three shapes stops closing when the
> derate is applied.**
>
> `docs/28` section 4.4(b) establishes that this flow has never applied
> the 5 % on-chip-variation derate its configuration asks for.
> `TIME_DERATING_CONSTRAINT` is the integer `5` in both PDKs and
> LibreLane's `base.sdc` computes the factor as `expr 5 / 100`, Tcl
> integer division, which is `0`; the factors are 1.0 and 1.0 while the
> log reports "Setting timing derate to: 5%". The table is correct as
> reported. What is wrong is the belief that it carries 5 % of OCV
> margin — it carries none.
>
> All three runs were re-derived by re-running the sign-off corners
> standalone on their own shipped netlist, parasitics, constraints and
> liberty, the method of `docs/28` section 11, which reproduces each
> run's own metric to 17 significant digits before the derate lines are
> added **[fact]**:
>
> | | `wave5-ihp-b` (4x2) | `shape-3x4` | **`shape-6x2`** |
> |---|---|---|---|
> | **Slow setup, derated** | **-0.0675** | **+0.0919** | **+0.2913** |
> | Slow hold, derated | +0.5683 | +0.5104 | +0.5546 |
> | Fast hold, derated | +0.0846 | **-0.0577** | +0.0898 |
> | Slow-corner Fmax, derated **[estimate]** | **49.8 MHz** | **50.2 MHz** | **50.7 MHz** |
>
> **[fact for the slacks, standalone OpenSTA on each run's
> `final/{nl,spef,sdc}`; estimate for the frequencies, on the linearity
> `docs/28` section 5.6 measures.]**
>
> **What moved, and it is not the decision.**
>
> - **4x2 does not close the slow corner derated**, at -0.0675 ns, and
>   so does not reach 50 MHz. Its "setup violations 0" row is a
>   statement about a sign-off with no OCV margin in it.
> - **3x4 and 6x2 both still close the slow corner derated**, 3x4 by
>   0.46 % of the cycle and 6x2 by 1.46 %. Both still reach 50 MHz; 3x4
>   by 0.2 MHz.
> - **3x4's fast-corner hold violation grows by an order of magnitude**,
>   from -6.27 ps to **-57.71 ps**. Section 3.2 treats it as small; that
>   remains true in absolute terms, but the derate is the direction it
>   moves in and the figure below it in section 3.2 is the un-derated
>   one.
> - **The ordering is unchanged and the shape decision is reinforced.**
>   6x2 remains the best slow corner of the three by the same margins,
>   and it is now the only one of the three that is clean on every
>   corner *and* has more than half a percent of derated cycle in hand.
>   A correction that could have overturned the decision strengthens it.

### 3.2 The 3x4 hold violation

One path, at the fast corner only:

```
$ grep hold hw/openlane/pilot_ihp/runs/shape-3x4/55-openroad-stapostpnr/nom_fast_1p32V_m40C/violator_list.rpt
[hold reg-reg] u_pilot._5015_/Q -> u_pilot._4972_/D : -0.006266
```

`timing__hold__tns__corner:nom_fast_1p32V_m40C = -0.006266`, so the
total negative slack is that one path and nothing else **[fact]**.

Three things should be said about it plainly, in both directions.

**It is small.** 6.27 ps at a 20 ns period is 0.031 % of the cycle. It
is one register-to-register path out of 1,275 flip-flops, and the hold
resizer inserted 1,402 hold buffers on this run without catching it.

**The flow did not stop for it.** `Checker.HoldViolations` ran at step
71 with `HOLD_VIOLATION_CORNERS: ['*']` and raised nothing; the run
reports `flow__errors__count: 0` and `design__violations: 0`. That last
metric does **not** aggregate hold, which is a trap worth naming: a
reader taking `design__violations: 0` as "no violations" would miss
this. It was found by reading the per-corner counters out of
`signoff_report.py`, which is the reason that script prints them.

**It is nevertheless the first non-zero violation counter in an IHP
sign-off in this project.** `docs/15`, `docs/20` and `docs/22` all
record zeros across the board. Whether 6.27 ps of hold at the fast
corner would survive the Tiny Tapeout precheck and the shuttle's own
top-level assembly is not something this repository can answer, and
guessing is not appropriate at a shuttle deadline. 6x2 does not raise
the question at all.

**Why the bigger die is the one with the hold problem** is worth a
sentence, because it is counter-intuitive. Hold failures come from paths
that are too *fast* relative to the clock arrival at the capture
register, so they are a clock-skew problem, not a delay-budget problem.
Spreading the same 12,449 cells over 443,784 um2 instead of 392,988
gives the clock tree a longer reach, and the skew figures say so
directly: worst hold skew at the fast corner is **-0.4715 ns on 3x4**
against **-0.2862 ns on 6x2**, so 3x4's clock tree is **65 % more
skewed** than 6x2's on the same netlist **[fact,
`clock__skew__worst_hold__corner:nom_fast_1p32V_m40C`]**. The extra area
3x4 offers is not free; it is paid for in clock distribution. The near-
square die is the worse shape for this design's clock tree, not the
better one, which is the opposite of what an aspect-ratio argument alone
would predict.

### 3.3 Power

Flow estimate at 50 MHz on the typical corner, from default switching
activity — not an annotated-activity measurement, and the `docs/22`
section 7 open item about that still stands.

| | 4x2 | **3x4** | **6x2** |
|---|---|---|---|
| Internal, mW | 4.2581 | 4.2694 | 4.2402 |
| Switching, mW | 0.9269 | 0.8787 | 0.8755 |
| Leakage, mW | 0.005983 | 0.017484 | 0.014350 |
| **Total, mW** | **5.1910** | **5.1655** | **5.1301** |
| Worst IR drop, V | 0.001277 | 0.000458 | 0.000616 |
| Power-grid violations | 0 | 0 | 0 |

**[fact]**. The three are within **1.2 %** of each other, so power does
not discriminate between the shapes either. Leakage rises about
three-fold at twelve tiles because the larger core is filled with more
decap and tap cells; at 17 uW against a 5.1 mW total it is not a
consideration. IR drop *improves* at both twelve-tile shapes, which is
the expected consequence of the same current drawn through more power
straps.

---

## 4. Routing behaviour

This is the section the decision turns on. `docs/22` section 5 and the
4x2 budget failure were both congestion, so a utilization number that
does not model routing is exactly the wrong instrument.

### 4.1 How this is measured

`signoff_report.py` reads `final/metrics.json`, where routing appears as
a single end-state number, `route__drc_errors`. That number is 0 for
every run in this repository that finished and absent for every run that
did not, so it cannot tell "routed comfortably" from "routed on the last
iteration" from "was diverging when it was killed" — which is precisely
the distinction this decision needs. `hw/openlane/route_trace.py` is
added here to read the trajectory out of the logs the same way for every
run: the `GRT-0096` final congestion table, and the `DRT-0195` /
`DRT-0199` optimization-iteration trace. It keeps the router's separate
invocations apart (the second is the post-antenna-repair re-route) and
it reports the within-iteration progress line for an iteration that
never produced a summary, so a killed run reads as a trajectory instead
of as no data.

### 4.2 Global routing

Every config in this repository sets `GRT_ALLOW_CONGESTION`, inherited
from the Tiny Tapeout defaults, so global routing does not fail on
overflow — it reports it and hands the result to the detailed router.
Overflow here is a leading indicator, not an error.

| | IHP 4x2 | **IHP 3x4** | **IHP 6x2** | sky 4x2 | **sky 3x4** | **sky 6x2** |
|---|---|---|---|---|---|---|
| Total resource | 208,224 | 355,003 | 315,588 | 86,645 | 152,422 | 134,772 |
| Total demand | 62,867 | 62,562 | 63,482 | 95,569 | 52,586 | 60,337 |
| **Total usage** | **30.19 %** | **17.62 %** | **20.12 %** | **110.30 %** | **34.50 %** | **44.77 %** |
| **Total overflow** | **0** | **0** | **0** | **22,357** | **0** | **0** |
| Worst layer | Metal3 54.98 % | Metal2 37.21 % | Metal3 35.43 % | met1 133.91 % | — | — |

**[fact, `route_trace.py` on each run]**

The sky130 4x2 column is the failure `docs/22` section 5 reports, and it
is what a congestion failure looks like: demand exceeding supply on
met1 by a third, 22,357 grid cells of overflow. **No twelve-tile run in
either PDK has a single cell of overflow.** IHP 3x4 is the least
congested of all six at 17.62 %, which is the honest point in its
favour.

### 4.3 Detailed routing

Violations at the end of each TritonRoute optimization iteration.
`pass 0` is the first invocation; `pass 1` and `pass 2` are the
re-routes after antenna repair.

| Run | Trace | Passes | Iterations | Ends at |
|---|---|---|---|---|
| IHP 4x2 `wave5-ihp-b` | `5311 -> 2625 -> 2438 -> 96 -> 5 -> 0` then `235 -> 18 -> 13 -> 0` | 2 | 10 | **0** |
| **IHP 3x4** | `5290 -> 2617 -> 2403 -> 28 -> 5 -> 5 -> 0` then `31 -> 1 -> 1 -> 0` | **2** | **11** | **0** |
| **IHP 6x2** | `4256 -> 2291 -> 2059 -> 134 -> 0` | **1** | **5** | **0** |
| sky130 4x2 `sky-08` | `218,483 -> 348,149 -> 364,603`, killed | — | 3+ | **killed, rising** |
| **sky130 3x4** | `5745 -> 2621 -> 2529 -> 256 -> 4 -> 0` then `332 -> 29 -> 25 -> 0` | **2** | **10** | **0** |
| **sky130 6x2** | `6998 -> 3185 -> 2954 -> 196 -> 0` then `756 -> 181 -> 108 -> 9 -> 0` then `79 -> 19 -> 10 -> 9 -> 9 -> 0` | **3** | **16** | **0** |

**[fact, `route_trace.py`]**, except the sky130 4x2 row, which is quoted
from `docs/22` section 5 table: the run directory on disk now holds a
log truncated inside the 0th iteration at 60 % complete with 105,645
violations, consistent with that record but not a full copy of it.

**Every twelve-tile run converges monotonically to zero.** None of the
six shows the sky130 4x2 trajectory, where the count *rose* across
iterations. That trajectory is the thing to look for and it is absent.

On IHP, 6x2 is the cleanest routing of any run in this project's record:
it enters detailed routing with 19.5 % fewer violations than 3x4, clears
them in five iterations, and needs no second pass because the antenna
checker found nothing to repair. **3x4 needs two passes and eleven
iterations, one more than the 4x2 that this whole exercise is replacing**,
despite having 12.6 points less global-route congestion than 4x2 and
2.5 points less than 6x2. More space did not buy easier routing: the
extra core is in the vertical direction, away from a pin frame that is
still on the perimeter, so the router gets longer average nets rather
than more room for the ones it had. The same geometry shows up in the
clock skew of section 3.2, from the same cause.

### 4.4 Antenna

| | IHP 4x2 | **IHP 3x4** | **IHP 6x2** | sky 3x4 | sky 6x2 |
|---|---|---|---|---|---|
| Antenna violations, post-route | 0 | **0** | **0** | 0 | 0 |
| Diodes inserted | 6 | **1** | **0** | 16 | 37 |

**[fact]**. `RUN_HEURISTIC_DIODE_INSERTION` is false throughout, so
these are repair diodes placed in response to a measured violation, not
prophylactic ones — the `docs/12` section 4.5 distinction. **6x2 needed
none at all.**

---

## 5. Cross-PDK portability, re-measured

`docs/18`'s claim is that this design is not sky130-specific. `docs/22`
section 5 could not re-test it: sky130 4x2 no longer routed, so there
was no netlist to measure. At twelve tiles there is.

| Quantity | sky 4x2 `sky-08` | **sky 3x4 `sky-10`** | **sky 6x2 `sky-09`** |
|---|---|---|---|
| Mapped flip-flops | — | **1,275** | **1,275** |
| Flip-flop cell types | — | 546 `dfrtp_2`, 105 `dfstp_2`, 624 `dfxtp_2` | same |
| Synthesis cells | — | 7,736 | 7,736 |
| Synthesis cell area, um2 | — | 99,875.79 | 99,875.79 |
| Placed cells, excl. fill | — | 13,686 | 13,461 |
| Instances incl. fill | — | 50,913 | 42,828 |
| Placed cell area, um2 | 123,766 | 126,380 | 126,187 |
| Die area, um2 | 154,113 | 260,160 | 232,623 |
| Core area, um2 | 149,183 | 254,599 | 225,802 |
| **Utilization** | **82.96 %, did not route** | **49.639 %** | **55.884 %** |
| Route DRC | **did not converge** | **0** | **0** |
| Magic DRC | — | **0** | **0** |
| KLayout DRC | — | **0** | **0** |
| KLayout XOR | — | **0** | **0** |
| Netgen LVS | — | **0** | **0** |
| Antenna violations | — | **0** | **0** |
| Total power, mW | — | 6.4423 | 6.3367 |
| Slow-corner setup WNS, ns | — | **-5.4953** | **-7.3054** |
| Slow-corner setup violations | — | 227 | 227 |
| Slow-corner hold WNS, ns | — | +0.8969 | +0.9083 |

**[fact]**

Three conclusions.

**The portability claim is alive again, and it is a stronger claim than
it was.** Both sky130 twelve-tile shapes complete the whole sign-off:
detailed routing, Magic DRC, the KLayout deck, the Magic/KLayout XOR,
Netgen LVS on all seven counters, and the antenna checks, all zero.
`docs/18` had never run the XOR to a zero on a shape this size. What
`docs/22` section 5 recorded as a portability failure was a **tile-size
failure**: sky130's 4x2 offers 149,183 um2 of core where IHP's offers 259,837,
and the design outgrew the smaller one first.

**The `docs/18` slow-corner setup miss is confirmed and is worse.**
`docs/18` records -3.85 ns at `max_ss_100C_1v60` on the 4x2 netlist.
This design misses that corner by **-5.4953 ns at 3x4** and **-7.3054 ns
at 6x2**, 227 violating paths in both. That is not a shape effect being
discovered; it is the same corner the sky130 runs have always missed,
now measured on a larger netlist. **[fact]**. Nothing in this project
targets sky130 silicon, so it is a portability observation, not a
blocker — but it should not be quoted as "closes on sky130".

**6x2 misses that corner by 1.81 ns more than 3x4 does.** This is the
one measurement in the whole document where 3x4 is materially ahead of
6x2. It is on a PDK the project is not taping out in, at a corner it
does not close in either shape, so it does not change the decision — but
it is recorded rather than dropped, because dropping the one result that
disfavours the recommendation is how a document stops being evidence.

---

## 6. The decision

**Recommendation: 6x2.** Update the submission from 4x2 to 6x2.

The case, in order of weight:

1. **Both shapes hold the design, so the tie-breaks decide.** 3x4 is
   40.1 points of core clear of the criterion and 6x2 is 32.4; neither
   is close to
   the 70 % line, and 4x2 is 2.13 % over it. Utilization has stopped
   being the discriminator (section 2.2).
2. **6x2 routes better.** One detailed-route pass of five iterations
   against 3x4's two passes of eleven; zero antenna diodes against one
   (sections 4.3, 4.4). Neither resembles the sky130 4x2 divergence, so
   this is a preference between two safe options rather than a rejection
   of an unsafe one.
3. **6x2 has no timing violations and 3x4 has one.** 6.27 ps of hold at
   the fast corner is small and the flow did not stop for it, but zero
   is available for the same money and the same tile count
   (section 3.2).
4. **6x2 closes the slow corner better**, +1.2347 ns against 3x4's
   +1.0593 ns and 4x2's +0.9121 ns — the best of the three, though all
   three close (section 3.1). The `docs/15` section 4.6 figure of
   +5.314 ns is not a counterexample: it is a 136,107 um2 netlist from
   before the memory ECC and the pointer TMR, not this one.
   *Corrected 2026-08-30: "though all three close" is withdrawn.* With
   the 5 % OCV derate the flow reports and does not apply (`docs/28`
   §4.4b), **only 6x2 and 3x4 close the slow corner — +0.2913 and
   +0.0919 ns — and 4x2 misses it at -0.0675 ns** (section 3.1's
   correction note). The clause this criterion actually rests on, that
   6x2 is the best of the three, is unchanged; what changes is that the
   gap to 4x2 is now the difference between closing and not.
5. **6x2 is confirmed purchasable and 3x4 is not** (section 7). This is
   listed last on purpose. It is decisive if the first four were a tie,
   and they are not a tie — **6x2 wins on the measurement alone**, and
   would be the recommendation even if 3x4 were confirmed available
   tomorrow.

**What 3x4 is better at**, stated so the trade is visible: 5.37 points
more utilization headroom (50,796 um2 more core), 2.5 points less
global-route congestion, and 1.81 ns less slow-corner setup violation on
sky130 — a PDK this project is not taping out in and does not close that
corner in at either shape. **None of these is worth a hold violation
and a second route pass at a shuttle deadline.**

**What would change this recommendation.** 6x2 crosses the 70 %
criterion at 275,092 um2 placed, which is **48 % more** than today's
185,840; 3x4 does not cross until 310,649 um2, **67 % more**. So a wave
that grows this design by more than about half would reopen the
comparison, and only then. Nothing on the roadmap
implies growth on that scale before this shuttle closes, and the SRAM
macro variant that `docs/06` section B.6 sizes at 12 tiles is a `docs/06`
go/no-go that has already been recorded as no-go for TTIHP26b. If that
reverses, this decision should be re-taken with the macro in the
floorplan, because a hard macro plus halo changes the congestion picture
that section 4 rests on entirely.

---

## 7. The open question: is 3x4 purchasable on TTIHP26b?

**Status: UNCONFIRMED. Not answered here, and not guessed.** It does not
gate the recommendation, because 6x2 wins on measurement and 6x2's
availability is not in doubt. It is documented because `docs/06` section
B.6 raises it and because a future wave that wants 3x4 will need it
settled.

### 7.1 What is confirmed

- **3x4 is a valid shape in the tooling.**
  `tt/tt/tech/ihp-sg13g2/tile_sizes.yaml` carries
  `3x4: "0 0 636.96 710.64"` and
  `tt/tt/tech/ihp-sg13g2/def/tt_block_3x4_pgvdd.def` exists **[fact,
  local clone at `01d5d281`]**.
- **The only tile validation in tt-support-tools is membership.**
  `project_info.py` lines 109-118 reject `tiles` only when it is not a
  key of `tile_sizes.yaml`. There is no shuttle allowlist and no
  per-shuttle override anywhere in the codebase **[fact, read at
  `01d5d281`]**.
- **The local clone is at upstream HEAD.** `git ls-remote` returns
  `01d5d2814fa9dd61e9d211e0b235a4a592a9316a` for `HEAD`, the same commit
  the clone is pinned at, dated 2026-08-20 **[fact]**. Nothing relevant
  has changed upstream.
- **The TTIHP26b shuttle repository's own pinned tooling carries 3x4.**
  `TinyTapeout/tinytapeout-ihp-26b` pins tt-support-tools at
  `d869909e41a25b09f39545588bf5256ca1f94d5c` (2026-07-28), and at that
  commit `tech/ihp-sg13g2/` contains both the `3x4` tile size and
  `tt_block_3x4_pgvdd.def` **[fact, accessed 2026-08-30]**.
- **Tiny Tapeout's own billing code prices 3x4 at twelve tiles.** The
  store's shared pricing module carries
  `{"1x1":1,"1x2":2,"2x2":4,"3x2":6,"4x2":8,"6x2":12,"8x2":16,"3x4":12,"4x4":16,"5x4":20,"6x4":24,"8x4":32}`,
  and the store sells a tile *count* with no shape selector and no shape
  whitelist in the submission path **[fact, accessed 2026-08-30]**.
- **The template comment that raised the doubt is stale, and provably
  incomplete.** `ttihp-verilog-template@main` `info.yaml` reads
  `tiles: "1x1"          # Valid values: 1x1, 1x2, 2x2, 3x2, 4x2, 6x2 or 8x2`.
  That line was last edited 2025-02-28, and **4x4, 5x4 and 8x4 have all
  shipped on IHP silicon despite being absent from it**: `4x4` twice and
  `5x4` once on ttihp25b, `8x4` twice on ttihp26a **[fact, shuttle index
  JSON, accessed 2026-08-30]**. So its omission of 3x4 is weak evidence.

### 7.2 What is not confirmed

- **No IHP shuttle has ever shipped a 3x4 or a 6x4 project.** Across
  ttihp0p2, 25a, 25b and 26a — roughly 1,023 projects — the four-row
  shapes that shipped are 4x4, 5x4 and 8x4 only **[fact]**.
- **No document, page or config enumerates the purchasable shapes for
  TTIHP26b specifically.** `tinytapeout.com/chips/ttihp26b/` returns 404
  and has not been written; the FAQ and specs pages say nothing about
  four-row tiles on IHP **[fact, accessed 2026-08-30]**.
- The `"3x4": 12` billing entry is in a **single global table shared
  across the IHP, ChipFoundry and GF shuttles**, and the GF template
  openly offers 3x4. Its presence therefore proves the store can price a
  3x4 on *some* shuttle, not on this one **[fact about the code;
  the limitation is the honest reading of it]**.
- Whether the four-row IHP projects that did ship were ordinary store
  purchases or special arrangements could not be established either way.

### 7.3 The question to put to Tiny Tapeout

Not answerable from the tooling. It needs a human answer, via the Tiny
Tapeout Discord or an issue on `TinyTapeout/ttihp-verilog-template`:

> The `info.yaml` comment in `ttihp-verilog-template@main` says valid
> tiles are `1x1, 1x2, 2x2, 3x2, 4x2, 6x2 or 8x2`, but
> `tech/ihp-sg13g2/tile_sizes.yaml` and the `def/` directory — at the
> commit `tinytapeout-ihp-26b` pins — also carry `3x4`, `4x4`, `5x4`,
> `6x4` and `8x4`, and ttihp25b/26a shipped `4x4`, `5x4` and `8x4`
> projects. Is **3x4 (12 tiles, 636.96 x 710.64 um)** purchasable on
> **TTIHP26b** at the standard 12 x EUR 70? Or are four-row shapes on
> IHP limited to specific sizes or available by arrangement?

**This is not on the critical path.** The submission is at 6x2, which
needs no answer. If the answer arrives before 2026-09-21 and is yes, the
section 6 recommendation still stands: 3x4 loses on routing and timing,
not on availability.

---

## 8. Cost

| | Tiles | Rate | Tile cost | Against `docs/06` |
|---|---|---|---|---|
| `docs/06` B.6 default (4x2) | 8 | EUR 70 | **EUR 560** | baseline |
| **6x2, recommended** | **12** | EUR 70 | **EUR 840** | **+EUR 280** |
| 3x4, not recommended | 12 | EUR 70 | EUR 840 | +EUR 280 |

**[fact for the shape-to-tile mapping and the EUR 70 IHP tile rate, read
from Tiny Tapeout's own pricing module 2026-08-30; `docs/06` B.6 carries
the same EUR 560 / EUR 840 figures.]**

**The two shapes cost exactly the same.** This is a pure engineering
choice with no price attached, which is why section 6 does not weigh
cost between them.

The **+EUR 280** delta against the `docs/06` WP3 line is the real budget
consequence, and it is the delta `docs/06` B.6 already anticipated —
that row reads "12 tiles, not 8" and prices it at EUR 840. What has
changed is the *reason*: B.6 attached the 12-tile cost to the SRAM-macro
variant, gated on a go/no-go recorded as no-go. **The flip-flop pilot
now needs twelve tiles on its own**, without the macro, because two
waves of hardening — the `lif_core` memory ECC and the AER pointer TMR —
grew it past 4x2. The line item does not change; its justification does.
The DevKit PCB and shipping are unaffected.

---

## 9. What changed in the repository, and the one guard now failing

### 9.1 Changed

| File | Change |
|---|---|
| `scripts/gen_tt_submission.py` | `TILES = "4x2"` -> `"6x2"`, with the rationale; the `info.yaml` and `README.md` prose that quoted `docs/15`'s 52.38 % re-stated against this document's measurements |
| `tt/info.yaml` | regenerated: `tiles: "6x2"` |
| `tt/README.md`, `tt/MANIFEST.sha256` | regenerated |
| `tt/src/user_config.json`, `tt/src/config_merged.json` | regenerated by `tt_tool.py --ihp --create-user-config`; `DIE_AREA` now `0 0 1289.28 313.74` and `FP_DEF_TEMPLATE` the 6x2 DEF |
| `hw/openlane/pilot_ihp/mkconfig.py` | `SHAPES` table added; `FP_DEF_TEMPLATE` now rebases the *path* and keeps the *file* from the submission config instead of hard-coding the 4x2 DEF name |
| `hw/openlane/pilot_ihp/config*.json` | regenerated; all four now carry the 6x2 geometry, plus the two new shape variants |
| `hw/openlane/pilot_sky130/mkvariant.py`, `config.3x4.json`, `config.6x2.json` | the two sky130 shape variants |
| `hw/openlane/route_trace.py` | new; section 4.1 |

The `mkconfig.py` hard-coded DEF name is worth flagging as a trap that
was live rather than hypothetical: it was correct only while the
submission was 4x2, and had it not been fixed, `config.json` would have
silently paired a 6x2 `DIE_AREA` from the submission with a 4x2 pin
frame. `mkconfig.py --check` reports no drift after the fix.

### 9.2 Failing, and deliberately left failing

```
$ .venv/bin/python -m pytest sw/tests/ -q
1 failed, 195 passed in 67.98s
FAILED sw/tests/test_tt_submission.py::test_tile_shape_is_the_documented_decision
```

`sw/tests/test_tt_submission.py` line 181 asserts
`info_yaml["project"]["tiles"] == "4x2"` with the message
"docs/15-pilot-tile-plan.md decides 4x2 = 8 tiles". The guard is doing
exactly its job: the documented decision moved and the guard caught the
submission moving with it. It is a one-line change — `"4x2"` to `"6x2"`
and the message to cite `docs/23` — but `sw/tests/**` is outside this
workstream's ownership and is not edited here.

**This is a blocking item for the test suite, not for the submission.**
Everything else passes, including
`test_generated_tree_matches_the_generator`, so the regenerated tree is
internally consistent. It should be the first thing fixed by whoever
owns `sw/tests`.

---

## 10. Open items

1. **The `sw/tests` tile guard**, section 9.2. One line, not this
   workstream's file.
2. **3x4 purchasability**, section 7.3. Not on the critical path now
   that the submission is 6x2, but it should be asked before a future
   wave plans around it.
3. **Gate-level simulation against the 6x2 netlist.** `docs/20` section
   8.1 and `docs/22` open item 4 both flag the smoke test as stale. The
   netlist to re-run it against is now
   `hw/openlane/pilot_ihp/runs/shape-6x2/final/nl/`.
4. **`tt/runs/` has no 6x2 harden.** Both IHP runs here land in
   `hw/openlane/pilot_ihp/runs/`, and `docs/22` section 1.3 records that
   `sw/tests/test_synthesis_guards.py` scans `tt/runs/` as well. That
   guard currently passes against the `wave5-ihp-b` netlist, which is
   the same RTL at a different shape, so nothing is stale in substance —
   but a `tt/runs/` harden at 6x2 before submission would keep the
   guard's evidence and the submission's shape aligned.
5. **No power analysis with annotated activity.** Section 3.3's figures
   are flow estimates from defaults, as `docs/22` open item 6 already
   records.
6. **The sky130 slow-corner setup miss is unaddressed**, section 5. It
   is not a blocker for an IHP shuttle, and `docs/18` section 6's
   `PNR_CORNERS` hypothesis was never re-tested at twelve tiles.

---

## 11. Reproducing this

```bash
make -f tools.mk toolcheck

# Generate the four shape configs from the submission config and the
# sky130 baseline. Both --check clean afterwards.
python3 hw/openlane/pilot_ihp/mkconfig.py
python3 hw/openlane/pilot_sky130/mkvariant.py 3x4
python3 hw/openlane/pilot_sky130/mkvariant.py 6x2

# Pin the RTL so a concurrent hw/rtl edit cannot change a run under it
# (docs/20 section 1.2). Each prints the blob of every file it writes.
python3 hw/openlane/pin_rtl.py e1361fe hw/openlane/pilot_ihp/config.3x4.json     /tmp/pin-ihp-3x4
python3 hw/openlane/pin_rtl.py e1361fe hw/openlane/pilot_ihp/config.6x2.json     /tmp/pin-ihp-6x2
python3 hw/openlane/pin_rtl.py e1361fe hw/openlane/pilot_sky130/config.3x4.json  /tmp/pin-sky-3x4
python3 hw/openlane/pin_rtl.py e1361fe hw/openlane/pilot_sky130/config.6x2.json  /tmp/pin-sky-6x2

# The four hardens. Sections 2, 3, 4 and 5.
mkdir -p hw/openlane/pilot_ihp/runs/shape-3x4
CONFIG=/tmp/pin-ihp-3x4/config.json hw/openlane/pilot_ihp/run_ihp.sh \
    --run-tag shape-3x4 --force-run-dir $PWD/hw/openlane/pilot_ihp/runs/shape-3x4

mkdir -p hw/openlane/pilot_ihp/runs/shape-6x2
CONFIG=/tmp/pin-ihp-6x2/config.json hw/openlane/pilot_ihp/run_ihp.sh \
    --run-tag shape-6x2 --force-run-dir $PWD/hw/openlane/pilot_ihp/runs/shape-6x2

mkdir -p hw/openlane/pilot_sky130/runs/sky-10-3x4
CONFIG=/tmp/pin-sky-3x4/config.json hw/openlane/pilot_sky130/run_sky130.sh \
    --run-tag sky-10-3x4 --force-run-dir $PWD/hw/openlane/pilot_sky130/runs/sky-10-3x4

mkdir -p hw/openlane/pilot_sky130/runs/sky-09-6x2
CONFIG=/tmp/pin-sky-6x2/config.json hw/openlane/pilot_sky130/run_sky130.sh \
    --run-tag sky-09-6x2 --force-run-dir $PWD/hw/openlane/pilot_sky130/runs/sky-09-6x2

# Every sign-off table above
python3 hw/openlane/signoff_report.py \
    tt/runs/wave5-ihp-b \
    hw/openlane/pilot_ihp/runs/shape-3x4 \
    hw/openlane/pilot_ihp/runs/shape-6x2 \
    hw/openlane/pilot_sky130/runs/sky-10-3x4 \
    hw/openlane/pilot_sky130/runs/sky-09-6x2

# Every routing table above
python3 hw/openlane/route_trace.py \
    tt/runs/wave5-ihp-b \
    hw/openlane/pilot_ihp/runs/shape-3x4 \
    hw/openlane/pilot_ihp/runs/shape-6x2 \
    hw/openlane/pilot_sky130/runs/sky-08-ptrtmr \
    hw/openlane/pilot_sky130/runs/sky-10-3x4 \
    hw/openlane/pilot_sky130/runs/sky-09-6x2

# The submission move
python3 scripts/gen_tt_submission.py
python3 scripts/gen_tt_submission.py --check
(cd tt && python3 tt/tt_tool.py --ihp --create-user-config)
.venv/bin/python -m pytest sw/tests/ -q
```

`--force-run-dir` is a hidden LibreLane 3.0.5 option
(`librelane/flows/cli.py`); without it a run lands in
`<config-dir>/runs/<tag>`, which for a pinned config is the disposable
snapshot directory.

Two environment notes for `tt_tool.py --create-user-config`, neither of
which is recorded in `docs/12`:

- It needs the tt-support-tools Python dependencies, which are **not**
  in this repository's `.venv`. A throwaway virtualenv with `chevron`,
  `klayout`, `GitPython`, `PyYAML`, `python-frontmatter`, `mistune`,
  `cairosvg`, `gdstk`, `configupdater`, `requests`, `matplotlib` and
  `numpy` is enough for this one subcommand.
- `tt/tt/project.py` line 144 hard-codes the binary name
  `yowasp-yosys`. Rather than install a second Yosys build, put a shim
  of that name on `PATH` that `exec`s the `OSS_CAD_SUITE` Yosys this
  repository already pins in `tools.mk`, so the port check runs against
  the same 0.67+146 as every other guard here.

`tt/runs/`, `hw/openlane/*/runs/` and `tt/src/*config*.json` are
gitignored. The `pin_rtl.py` snapshots are disposable and regenerable
from `e1361fe`; the blob table in section 1.2 is the record, not the
path.
