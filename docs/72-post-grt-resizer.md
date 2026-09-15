# 72 — What the post-GRT resizer did: no cap bound, the loop gave up after twenty CLINT endpoints, and the 4 ns was in the parasitics it was handed

`docs/71-layout-reproducibility.md` section 15 opens its list of what
to do next with the item this document is the answer to:

> **Find out what the post-GRT resizer did.** `docs/70` section 15
> item 2, now with the caveat removed that made it uncertain whether
> the event would recur: it recurs exactly. `repair_timing`'s own
> report and its iteration budget are in
> `36-openroad-resizertimingpostgrt/` of `s71boot` and of `s70base`,
> 102 setup buffers against 519, and reading them is the difference
> between "reported" and "explained".

**It is not a cap.** No configured limit bound in either run: the
setup repair used **0.1 %** of area in the hardened run and **0.4 %**
in the baseline against a 50 % buffer ceiling, no utilisation limit was
set, the endpoint budget was 100 %, and both loops ended the same way —
OpenROAD's own rule that stops `repair_timing` when the total negative
slack has not moved by 0.01 % of its starting value for two hundred
iterations. **The hardened loop reached that rule after 20 of 3,365
endpoints**, because the worst endpoint and the nineteen after it, all
of them the CLINT's read-data and time-base registers, could not be
improved by any move it has: each of the nineteen was tried for 51
passes, every change was reverted, the negative slack did not move from
iteration 257 to iteration 1,200, and the loop aborted with 3,345
endpoints unvisited. The baseline's loop chased its worst endpoint productively for
2,005 iterations, from −9.783 to −3.272 ns, and aborted at 2,300 after
**7** endpoints — the same rule, at a height set by what the path
would give.

**And the resizer was handed a different problem before it made a
different choice.** At the resizer's own timing analysis, on the
parasitics the global router estimated, the two designs were **2.477 ns
apart at iteration 0** — −9.783 ns against −12.260 — where after
clock-tree repair they had been 0.3414 ns apart. The global router is
not congested in either run: zero overflow on every layer, 22.9 %
against 22.6 % track usage, 0.7 % less wire in the hardened run. What
differs is one stage on the hardened design's worst path: a
`sg13g2_nor4_1`, the only drive strength the resizer had used, in the
standard-cell channel at (1911.84, 1224.72) um, driving a 180 fF net to
a gate in the pocket above the upper ROM macro at (1973.76, 1776.60) —
614 um of wire across a 336 um macro — with a 4.69 ns transition
against the library's 2.51 ns limit and **3.73 ns of delay on one
gate**. The baseline's worst path crosses the same macro twice, through
a buffer and an inverter that repair steps had placed there, and its
heaviest stage costs 1.32 ns.

So the 4.0739 ns `docs/70` section 6.2 localised between step 30 and
step 37 decomposes, on the resizer's own numbers, into **2.477 ns it
was handed and 2.092 ns it failed to recover** — the baseline recovered
6.511 ns from its start, the hardened run 4.419 — and neither part is a
knob. **No knob experiment was run, because none of the five knobs the
step takes bound, and the one rule that did bind is not a knob and had
nothing left to give.** What was run instead is the instrumentation
`docs/71` section 15 asked for: the flow's own step, re-executed on
each run's own saved state with OpenROAD's `repair_setup` debug trace
enabled and nothing else changed. It reproduces both steps to the byte
and prints, per endpoint, why the loop stopped. On the way it found
that the step-rerun form does not reproduce the flow unless one lossy
configuration key is corrected by hand, which is `docs/31` section 3.2's
finding in a fourth place.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged, with the
derivation stated; **[assumption]** = chosen, and named so it can be
argued with; **[planned]** = an intention with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by blob hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was modified,
and `hw/tb/Makefile.fi` was not invoked. `hw/openlane/checker_audit.py`
and `hw/openlane/signoff_report.py` are **read and run** and never
written.

**And no RTL, flow script, test or configuration file was modified
either.** `config-ecc.json` is `docs/67`'s and was not touched; the two
instrumentation runs of section 7 used a copy of LibreLane's own step
script and a copy of each step's own `config.json`, both in a scratch
directory outside the repository, and wrote nothing into any run
directory. What changed on disk is this document, one index row, and
the dated in-place notes section 12 names. Section 13.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Why did the resizer stop at 102 buffers in the hardened run and 519 in the baseline?** | **Because it stopped improving, not because it hit a limit.** Both `repair_timing -setup` calls ended with `RSZ-0062 Unable to repair all setup violations` after OpenROAD's fix-rate rule fired twice in a row — at iterations 1,100 and 1,200 in the hardened run, 2,200 and 2,300 in the baseline. Neither reached the 50 % buffer ceiling (0.1 % and 0.4 % of area used), the unset utilisation limit, the 100 % endpoint budget, or the 10,000-pass limit **[fact, the two step logs, the two `resolved.json`, and `RepairSetup.cc` at the installed commit]**. Sections 3 and 4 |
| **What did the hardened loop do with its 1,200 iterations?** | **257 on the worst endpoint, then 51 each on nineteen more, all reverted.** `s_rdata_clint[2]` was driven from −12.260 to −7.990 ns; then `s_rdata_clint[9]`, `[22]`, `[25]`, `[16]`, `[17]`, `[23]`, `[26]`, `u_clint.err_o`, `[27]`, `[20]`, `[24]`, `[21]`, four `u_mtime_dec.check_raw` bits, `[14]`, `[1]` — every one "stuck after 51 non-improving passes", every change restored from the journal. TNS −7,308.7 at iteration 300, −7,308.7 at iteration 1,000. **20 of 3,365 endpoints were visited** **[fact, the `repair_setup` debug trace of section 7]**. The baseline visited **7**, of which one — the worst-endpoint chase — took 2,005 iterations and recovered 6.5 ns. Section 7 |
| **Was a knob binding?** | **No.** `GRT_RESIZER_SETUP_MAX_BUFFER_PCT` 50 against 0.17 % and 0.86 % of instances inserted; `GRT_RESIZER_SETUP_MAX_UTIL_PCT` unset; `GRT_RESIZER_SETUP_REPAIR_TNS_PCT` unset, so 100 %; `GRT_RESIZER_SETUP_SLACK_MARGIN` 0.025 ns, reached by neither; buffering, buffer removal and cloning all on. Identical in both `resolved.json`. The rule that bound is `inc_fix_rate_threshold_ = 0.0001` in OpenROAD's source, not a LibreLane variable, and it bound **after** progress had stopped, so raising it would have bought iterations and no slack. Section 5 |
| **Was the global router congested?** | **No.** Zero overflow on every layer in both runs; total usage 22.86 % against 22.61 %; wirelength 5,347,404 against 5,310,590 um; two and three overflow iterations. `docs/48`'s routability inflation is not in play. Section 6.1 |
| **So what differed before the resizer ran?** | **The worst path's parasitics.** At the resizer's own iteration-0 analysis: −9.783 against −12.260 ns, 2.477 ns apart, where step 30 had them 0.3414 apart. On the hardened path one `nor4_1` drives 180 fF across the upper ROM macro from the channel into the pocket above it — 3.73 ns, 4.69 ns transition — and the baseline's heaviest stage is 1.32 ns **[fact, section 7's pre-repair reports]**. Both worst paths are the CLINT read and both cross the macro twice; the difference is which cell was left driving the crossing. Sections 6.2 to 6.4 |
| **Where is the 4.07 ns?** | **2.477 ns in the hand the resizer was dealt, 2.092 ns in the hand it played**, on its own analysis: start −9.783 / −12.260, end −3.272 / −7.841, recovery 6.511 / 4.419 **[fact]**. Step 37 then reports −4.1113 / −8.1852, sign-off −4.8076 / −9.1085. Section 8 |
| **Does the instrumented re-run reproduce the flow?** | **To the byte, once one key is corrected.** The hardened step re-executed with the debug trace on gives 53 of 53 metrics equal and a byte-identical netlist, DEF, ODB and SDC; the baseline likewise: 52 of 52 metrics, netlist, DEF, ODB and SDC identical. **Before the correction it did not**: the step's own `config.json` records `TIME_DERATING_CONSTRAINT` as `5`, the re-run derated by 0 %, and iteration 0 read 1.744 ns and 1.623 ns better than the flow. Section 7.1 |
| **Was the one bounded experiment run?** | **No, and section 5 says why**: there is no knob whose change is a hypothesis. The one run this document adds per netlist is the instrumentation, with nothing varied. |
| **Did the checkers keep watching?** | **17 of 19, exit 1**, on `s71boot` and `s70base2`, re-run here. The two scratch step runs are single steps and have no checker stage. Section 9 |
| **May a frequency be published?** | **No.** `docs/53` section 9.2's three grounds bind. Slack against **20 ns** is what is reported. Section 8.3 |

> **THE ONE-SENTENCE RESULT.** The resizer inserted a fifth of the
> buffers because it gave up a fifth of the way in: handed a worst path
> 2.5 ns worse than the baseline's — one single-drive gate driving a net
> across the ROM macro — it spent 918 of its 1,200 iterations on
> nineteen CLINT registers it could not move, and OpenROAD's
> no-progress rule ended it with 3,345 endpoints never visited.

---

## 2. Reproducing every instrument before moving it

`docs/44` section 5.2's rule. Everything below was read out of the
existing run directories in this session, before anything was
executed.

| What | Published | Measured here |
|---|---|---|
| setup repair buffers, post-GRT resizer | `docs/70` 6.2: **519 / 102** | `[INFO RSZ-0040] Inserted 519 buffers.` in `s70base/36-…/openroad-resizertimingpostgrt.log`; `Inserted 102 buffers.` in `s71boot`'s; `design__instance__count__setup_buffer` **519 / 102** in the two `or_metrics_out.json` **[fact]** |
| the stage table | `docs/70` 6.2: **−2.2548 / −2.5962** at step 30, **−4.1113 / −8.1852** at step 37 | `timing__setup__ws` at `nom_slow_1p08V_125C`: **−2.2548 / −2.5962** and **−4.1113 / −8.1852**; TNS −2,812.66 / −3,801.1 and −7,548.86 / −17,872.4; endpoints 2,712 / 2,897 and 3,118 / 3,357 **[fact]** |
| sign-off, slow corner | `docs/70` 6.1: **−4.8076 / 3,108** and **−9.1085 / 3,361** | `signoff_report.py` on `s70base2` and `s71boot`: **−4.8076 / 3,108**, **−9.1085 / 3,361** **[fact]** |
| checker audit | `docs/71` 9: **17 of 19, exit 1** | 17 of 19 on both, `LintWarnings` and `WireLength` abstaining, `$?` = **1** on both **[fact]** |
| the configuration | `docs/70` 3.1: no key differs | `keys differing between runs/s70base/resolved.json and runs/s71boot/resolved.json: []` **[fact]** |
| the netlists | `docs/70` 2, `docs/71` 2 | `md5 aaf14e6d…` for `hw/soc/out/s70-rom0-syn-h0/soc_top.netlist.v`, `a8d5ef81…` for `hw/soc/out/s70-rom0-syn/soc_top.netlist.v` **[fact]** |
| the step timers | `docs/70` 14, `docs/71` 14 | step 36: **21 m 38.29 s / 9 m 52.82 s**; step 37: 7 m 37.22 s / 2 m 36.45 s; step 31: 9.03 s / 16.06 s **[fact, `runtime.txt`]** |
| the resume form loses nothing | `docs/71` 6.3 | not re-measured; it is why section 7 can run one step on a saved state and call the result the flow's |

**[fact for every row]**

The 519 and the 102 are the first numbers in this document because
`docs/71` section 6.2 made them exact: the flow is deterministic, so
what the two logs record is what this step does to these two netlists,
every time.

---

## 3. The step, read before anything was run

### 3.1 What LibreLane asks for

`OpenROAD.ResizerTimingPostGRT` runs
`librelane/scripts/openroad/rsz_timing_postgrt.tcl`: read the ODB left
by antenna repair, `set_propagated_clock`, the RC layer values, a fresh
`global_route -congestion_iterations 50`, `estimate_parasitics
-global_routing`, then two `repair_timing` calls, then detailed
placement and a second global route, then the views. The setup call, as
both logs print it **[fact, `+ repair_timing …` in each log]**:

```
repair_timing -verbose -setup -setup_margin 0.025 -max_buffer_percent 50
```

— no `-repair_tns`, no `-max_utilization`, no `-max_passes`, no
`-max_iterations`, no `-skip_*`. Those come from five variables of the
step and they are identical in the two `resolved.json` files:

| Variable | Value, both runs | What it becomes |
|---|---|---|
| `GRT_RESIZER_SETUP_SLACK_MARGIN` | 0.025 ns | `-setup_margin`: an endpoint is done when its slack is at least this |
| `GRT_RESIZER_SETUP_MAX_BUFFER_PCT` | 50 | `-max_buffer_percent`: buffers may be inserted up to half the instance count |
| `GRT_RESIZER_SETUP_MAX_UTIL_PCT` | `null` | `-max_utilization` not passed; no limit |
| `GRT_RESIZER_SETUP_REPAIR_TNS_PCT` | `null` | `-repair_tns` not passed; OpenROAD's default `repair_tns_end_percent 1.0`, all violating endpoints |
| `GRT_RESIZER_SETUP_BUFFERING` / `_BUFFER_REMOVAL` / `_GATE_CLONING` | `true` | no `-skip_buffering`, `-skip_buffer_removal`, `-skip_gate_cloning` |

**[fact, `resolved.json` of both runs and `rsz_timing_postgrt.tcl` in
the installed LibreLane v3.0.5]**. `docs/47` set none of these; all five
are LibreLane's defaults inherited by `config-ecc.json`. The hold call
adds `-hold_margin 0.05` from `GRT_RESIZER_HOLD_SLACK_MARGIN`, which
`docs/47` did set, and is not this document's subject: it found 3 and 4
hold endpoints and inserted 4 buffers in each run **[fact]**.

OpenROAD's own defaults for what LibreLane does not pass, read out of
`src/rsz/src/Resizer.tcl` at the installed commit `0e2d771c5e`:
`max_passes 10000`, `max_iterations -1` (off), `max_repairs_per_pass
1`, `repair_tns_end_percent 1.0` **[fact]**.

### 3.2 How `repair_timing -setup` decides to stop

`src/rsz/src/RepairSetup.cc` and `RepairSetup.hh` at commit
`0e2d771c5e`, the commit the installed `26Q1-2938-g0e2d771c5e` binary
reports, read in full **[fact]**. The command runs two **phases** by
default, `LEGACY` then `LAST_GASP`, and the character after the
iteration number in the verbose table is the phase's marker: `*` for
the first, `+` for the second. A row is printed every ten iterations
and, forced, whenever an endpoint's inner loop exits, which is why the
same iteration number can appear two or three times.

**The `LEGACY` phase** takes the violating endpoints sorted worst
first. For endpoint 1 it re-targets the current worst endpoint on every
pass, so the first entry is a chase of the WNS wherever it moves. For
each endpoint it runs passes of one repair each until one of:

| Exit | Rule in the source | What it means |
|---|---|---|
| slack met | `end_slack >= setup_slack_margin` | done with this endpoint |
| no move possible | `repairEndpoint()` returns `false` | nothing in the move sequence applies; journal restored if past pass 1 |
| **stuck** | `decreasing_slack_passes > 50`, `decreasing_slack_max_passes = 50` | 51 consecutive passes in which the change did not improve WNS (endpoint 1) or the endpoint's own slack (the rest); **all of them restored from the journal** |
| over area | `overMaxArea()` — the `-max_buffer_percent` / `-max_utilization` ceiling | whole repair ends |
| **no progress** | `terminateProgress()`: every 100 iterations after iteration 1,000, `(prev_tns − curr_tns) / initial_tns < fix_rate_threshold`, threshold `0.0001` doubled every 1,000 iterations | ends this endpoint; **a second consecutive firing aborts the phase** — `two_cons_terminations` |
| pass limit | `pass > max_passes`, 10,000 | never reached here |

**The `LAST_GASP` phase** then walks the remaining violators once with
a reduced move set (size-up and pin swap, VT swap where the library has
it), accepts a move only if **both** WNS and TNS improve, and is
subject to the same no-progress rule. `RSZ-0062` is printed afterwards
if the worst slack is still below the margin.

Every one of those rules is printed by name at
`set_debug_level RSZ repair_setup 2`, and section 7 is that trace.
Without it the verbose table already shows which rule fired: the fix-rate
test can only fire at a multiple of 100 past 1,000, and a phase that
ends at 1,200 or 2,300 with its TNS column unchanged across the two
preceding hundreds ended by it.

---

## 4. What the two reports say

### 4.1 The trajectories

The verbose table, both runs, worst setup slack on the resizer's own
analysis (both PNR corners, GRT parasitics), every hundredth iteration
and the forced rows at the phase exits **[fact, the two step logs]**:

| iteration | baseline WNS | baseline TNS | baseline buffers | hardened WNS | hardened TNS | hardened buffers |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | −9.783 | −8,522.1 | 0 | **−12.260** | −12,810.3 | 0 |
| 100 | −7.556 | −5,683.5 | 43 | −8.722 | −8,225.4 | 54 |
| 200 | −7.106 | −5,305.4 | 64 | −8.035 | −7,313.4 | 95 |
| 257 | | | | −7.990 | −7,313.0 | 95 — endpoint 1 stuck |
| 300 | −6.664 | −4,986.1 | 92 | **−7.987** | **−7,308.7** | 131 |
| 500 | −5.982 | −4,555.6 | 127 | −7.987 | −7,308.7 | 127 |
| 1,000 | −4.583 | −3,185.0 | 250 | −7.987 | −7,308.7 | 110 |
| 1,100 | −4.367 | −2,931.1 | 271 | −7.987 | −7,308.7 | 102 — **fix rate 0.01 % < 0.02 %** |
| 1,200 | −4.199 | −2,686.9 | 290 | −7.987 | −7,308.7 | 102 — **0.00 %: `LEGACY` aborts** |
| 1,400 | −3.957 | −2,478.2 | 320 | **−7.841** | −7,261.3 | **102 — final** |
| 1,500 | −3.833 | −2,323.6 | 339 | | | |
| 2,000 | −3.278 | −1,750.7 | 505 | | | |
| 2,100 | **−3.272** | **−1,744.3** | 521 | | | |
| 2,200 | −3.272 | −1,744.3 | 519 — **fix rate 0 %** | | | |
| 2,300 | −3.272 | −1,744.3 | 519 — **`LEGACY` aborts** | | | |
| 2,500 | **−3.272** | −1,721.7 | **519 — final** | | | |

The TNS column is the table's `StTNS`, the startpoint-summed figure the
loop's own test uses; the `EnTNS` column, summed over endpoints, runs
from −20,085.0 to −6,302.9 in the baseline and from −20,775.3 to
−16,994.1 in the hardened run **[fact]**. The area column never leaves
+0.4 % in the baseline and +0.1 % in the hardened run against the 50 %
ceiling.

**Three things are visible without the trace.** First, both phases end
on the no-progress rule and at the first opportunity after progress
stopped: the baseline's TNS froze at 2,100 and it aborted at 2,300; the
hardened run's froze at 300, the rule cannot fire before 1,100, and it
aborted at 1,200. Second, the hardened buffer count **falls** from 131
to 102 between iterations 300 and 1,100 while TNS does not move: those
are buffers inserted and then restored from the journal, which is what
"stuck" looks like from the outside. Third, the `Viol Endpts` column
stays at 3,367 and 3,365 for the whole of both `LEGACY` phases: the
counter is only decremented in `LAST_GASP`, so it records nothing about
how many endpoints the first phase reached.

### 4.2 The summaries

| | baseline | hardened |
|---|---:|---:|
| `RSZ-0094` endpoints with setup violations | 3,367 | 3,365 |
| `RSZ-0099` repaired ... out of | 3,367 (100.00 %) | 3,365 (100.00 %) |
| `RSZ-0059` buffers removed | 17 | 3 |
| **`RSZ-0040` buffers inserted** | **519** | **102** |
| `RSZ-0051` instances resized, all up | 1,536 | 168 |
| `RSZ-0043` pins swapped | 316 | 52 |
| `RSZ-0062` unable to repair all setup violations | yes | yes |
| hold: endpoints / buffers | 3 / 4 | 4 / 4 |
| step runtime | 21 m 38.29 s | 9 m 52.82 s |

**[fact, both step logs and `runtime.txt`]**

`RSZ-0099`'s "100.00 %" is the endpoint **budget**, not the count
reached; the number reached is only in the trace, section 7.

---

## 5. Whether a knob explains it

| Knob | Value | Did it bind? |
|---|---|---|
| `-max_buffer_percent` 50 | 50 % of 59,979 instances | **No.** 102 buffers are 0.17 %; 519 are 0.86 %. `overMaxArea()` is never the exit in either trace |
| `-max_utilization` | not passed | **No.** Nothing to bind |
| `-repair_tns` | not passed, 100 % | **No.** The budget was 3,365 and 3,367 endpoints; the `LEGACY` phases visited 20 and 7 |
| `-setup_margin` 0.025 | 0.025 ns | **No.** No endpoint the `LEGACY` phase touched reached it; the final WNS is −7.841 and −3.272 |
| `-max_passes`, `-max_iterations` | 10,000 / off, and not exposed by LibreLane | **No.** The longest inner loop was 2,005 passes, the baseline's chase |
| **`inc_fix_rate_threshold_`** | 0.0001 of initial TNS per 100 iterations, doubled per 1,000 | **Yes, in both runs** — and it is a constant in `RepairSetup.hh`, not an argument of `repair_timing` and not a LibreLane variable |

**[fact]**

So the "cap" the task asked about exists, is the same in both runs, and
is not configurable. It also would not have mattered: it fired after
900 iterations of zero change in the hardened run, and the eighteen
"stuck after 51 non-improving passes" lines before it say that the
endpoints being tried had no improving move at all. Doubling the
iteration allowance would have produced more stuck endpoints. **That is
why no knob experiment was run.** `docs/48` section 5's lesson was that
the third and fourth floorplan added nothing the first had not; a
resume with `-max_iterations` raised, or the buffer ceiling raised, is
a run whose result the trace already states, and `docs/71` section 15's
suggestion of a `-max_iterations` sweep is answered without one.

---

## 6. What differed before the resizer ran

### 6.1 Not the router

`OpenROAD.GlobalRouting`, step 31, and the same command re-run inside
step 36 before `repair_timing` **[fact, `GRT-0096`, `GRT-0018`,
`GRT-0014`, `GRT-0102` in each log]**:

| | baseline | hardened |
|---|---:|---:|
| step 31: total wirelength | 5,347,404 um | 5,310,590 um |
| step 31: routed nets / clock nets | 59,444 / 641 | 59,758 / 650 |
| step 31: overflow iterations | 2 | 3 |
| step 31: usage Metal2 / Metal3 / Metal4 / Metal5 / TopMetal1 / TopMetal2 | 40.87 / 39.95 / 20.80 / 9.08 / 4.51 / 1.99 % | 40.84 / 41.14 / 18.98 / 8.64 / 3.66 / 3.40 % |
| step 31: total usage | **22.86 %** | **22.61 %** |
| step 31: max H / max V / total overflow, every layer | 0 / 0 / 0 | 0 / 0 / 0 |
| step 33 `repair_design`: slew / cap / fanout violations found | 57 / 60 / 0 | 31 / 69 / 2 |
| step 33: buffers inserted, nets | 70 in 117 | 83 in 99, and 3 resized |
| step 32: antenna-violating nets before repair | 261 | 296 |
| step 36, the route the resizer worked on: wirelength / nets | 5,450,421 um / 59,514 | 5,423,104 um / 59,841 |

The hardened design has 0.7 % less wire, no overflow, and 0.25 points
less usage. `docs/48`'s finding that the placer is not density-bound at
this utilisation (0.688 against a 48 % target at step 24, both runs)
stands; routability inflation is not what moved.

### 6.2 The resizer's own starting point

The row at iteration 0 is the resizer's analysis of the design it was
handed, after step 36's own global route and parasitic estimate and
before any move:

| | baseline | hardened | difference |
|---|---:|---:|---:|
| step 30, post-CTS repair, placement parasitics (`docs/70` 6.2) | −2.2548 | −2.5962 | 0.3414 |
| **step 36 iteration 0, GRT parasitics, resizer's own STA** | **−9.783** | **−12.260** | **2.477** |
| iteration-0 TNS, startpoint-summed | −8,522.1 | −12,810.3 | |
| iteration-0 endpoints | 3,367 | 3,365 | |
| section 7's pre-repair `report_wns` / `report_tns`, same state | −9.78 / −20,085.02 | −12.26 / −20,775.27 | |

**[fact]**

Global-route parasitics cost the baseline's worst path 7.53 ns and the
hardened one's 9.66 ns relative to the placement estimate. That is the
same phenomenon `docs/47` section 8.5 measured as "real wire
capacitance costs 6.72 ns" on the first floorplan; here it lands
unevenly on two placements of the same block.

### 6.3 The path, and the one stage that is the difference

Section 7's pre-repair report, the worst `clk_i` path at
`nom_slow_1p08V_125C` on GRT parasitics, decomposed **[fact; the
report prints two decimals]**:

| | baseline | hardened |
|---|---|---|
| launch → capture | `raddr_b_i[1]` → `s_rdata_clint[25]` | `raddr_a_i[1]` → `s_rdata_clint[2]` |
| arrival / required / slack | 31.54 / 21.75 / **−9.78** | 34.07 / 21.81 / **−12.26** |
| driver stages, of which buffers | 90, 27 (10.21 ns) | 75, 24 (10.31 ns) |
| cell delay / net delay | 31.46 / 0.00 | 33.86 / 0.01 |
| stages driving ≥ 50 fF, their delay | 26, 12.72 ns | 28, **19.45 ns** |
| stages driving ≥ 100 fF, their delay | 14, 7.01 ns | 14, **11.77 ns** |
| heaviest stage | `_40335_/Y` `nand4_1`, 80 fF, 1.32 ns | **`_52172_/Y` `nor4_1`, 180 fF, slew 4.69 ns, 3.73 ns** |
| next | `xnor2_1` 100 fF 1.04; `buf_1` 200 fF 0.96; `inv_2` 110 fF 0.89 | `fanout534` `buf_1` 200 fF 1.56; `a221oi_1` 100 fF 1.42; `xnor2_1` 100 fF 1.04 |

The two paths are the same structure `docs/48` section 7a named — the
register file's read address, the ALU, the data address into the
fabric's combinational request mux (`soc_bus.v`: `s_addr_o = d_wins ?
md_addr_i : mi_addr_i`), the CLINT's address decode and read mux, and
its registered response `rdata_o` **[fact, `hw/soc/rtl/soc_bus.v` and
`soc_clint.v`, read]** — at 75 to 95 stages, with 0.3 % of the delay in
wire and the rest in cells driving wire. One stage separates the two
columns: **2.41 of the 2.48 ns is `_52172_`**.

That net, `_17942_`, in the hardened run **[fact, step-36 netlist and
DEF]**:

| pin | cell | placed at | region |
|---|---|---|---|
| `_52172_/Y`, the driver | `sg13g2_nor4_1` before the resizer, `nor4_2` after | (1911.84, 1224.72) um | the standard-cell channel, below the upper macro row |
| `_68120_/…`, the load | `sg13g2_nand2b_1` | (1973.76, 1776.60) | **the pocket above the upper ROM macro** |
| `ANTENNA_21` | `sg13g2_antennanp`, step 35's diode | (1973.76, 1772.82) | the pocket |
| `rebuffer14105` | `sg13g2_buf_1`, inserted by this step | (1917.60, 1236.06) | the channel |

The upper ROM, `u_rom.g_rom_1024x32.u_b1`, sits at (1769.28, 1387.26)
and is 416.64 × 336.46 um **[fact, `config-ecc.json` and the LEF]**;
the net runs 62 um across and 552 um up, over the macro, to a gate in
the pocket the shorter ROM leaves under the core's top edge. 180 fF is
legal — the library's `default_max_capacitance` is 0.3 pF, `docs/48`
section 6.3 — so `repair_design` has no reason to touch it; the 4.69 ns
transition is not legal against `default_max_transition 2.5074`, and
step 33's `repair_design` reported 31 slew violations repaired two
steps earlier, on the route it had then. Whether this net was among
them, or crossed the limit only on step 36's re-route after the
antenna diode was added, was not measured; what is measured is that
the resizer met it at 4.69 ns.

### 6.4 The pocket, which both runs use and one run's binding path pays for

`docs/48` section 5 found the placer exiling cells into the ROM pockets
when the channel is short of room. On `docs/67`'s floorplan, counting
placed instances by region from each run's DEF **[fact]**:

| region, step 26 (after detailed placement) | baseline | hardened |
|---|---:|---:|
| the channel between the macro rows | 45,966 | 45,619 |
| pocket above the upper ROM | 2,208 | 2,222 |
| pocket below the lower ROM | 3,049 | 3,568 |
| the 60.48 um strip beside the ROMs | 424 | 441 |
| elsewhere | 173 | 436 |
| **total standard cells** | **51,820** | **52,286** |
| flip-flops in the upper pocket | 265 | 308 |
| `s_rdata_clint` flip-flops: upper pocket / channel / other | 20 / 12 / 0 | 16 / 14 / 2 |
| nets with a pin in the upper pocket **and** in the channel | 134 | 140 |
| macro crossings on the pre-repair worst path | 2 | 2 |
| macro crossings on the step-37 worst path | 0 | 2 |

The 466 extra cells of the hardened netlist did not go into the
channel; the channel holds 347 fewer cells than the baseline's and the
pockets and the strip hold 813 more. **Both runs split the CLINT's
32-bit read-data register across the macro**, and both worst paths
cross it twice before repair. In the baseline the two crossings are
driven by a `buf_1` and an `inv_2` — cells that earlier repair steps
put there — and cost 0.96 and 0.89 ns; in the hardened run one crossing
is driven by the `nor4_1` of section 6.3 and costs 3.73 ns. After
repair the baseline's worst path no longer crosses the macro at all;
the hardened run's still does, twice, and its heaviest stage is now the
other crossing: `_68128_/Y`, a `sg13g2_nand3_1` at (1939.68, 1772.82)
in the pocket driving 184 fF down to `_68129_` at (1935.36, 1360.80) in
the channel, 412 um, 1.98 ns at a 2.49 ns transition **[fact, step-37
`max.rpt` and the DEF]**. `nand3` ships in one drive strength
(`docs/48` 6.3); the resizer's size-up move has nothing to offer it.

This is `docs/71` section 7's netlist sensitivity, seen at the cell: a
netlist 0.9 % larger is placed differently, the difference lands on
which gate is left driving a net that crosses a macro, and that gate is
the binding path. It is not a property of the boot block's 51
flip-flops, which are on none of these paths (`docs/70` 6.3), and it is
not a property of the resizer, which met an unrepairable stage and said
so.

---

## 7. The instrumentation, and the trap on the way to it

### 7.1 What was run, and what had to be corrected first

`docs/71` section 15 item 1: *"Because the flow is deterministic, any
instrumentation of that step … measures the mechanism and not a
draw."* The step was re-executed for each run **on its own saved
state** — `36-openroad-resizertimingpostgrt/state_in.json`, which
points at step 35's ODB — through LibreLane's own step runner,
`python -m librelane.steps run`, with the step class's script path
redirected to a copy of `rsz_timing_postgrt.tcl` that differs from the
original in three additions and no changes: a `report_wns`,
`report_tns` and `report_checks` before `repair_timing`, the same three
after the setup call, and `set_debug_level RSZ repair_setup 2` around
it. No `repair_timing` argument was altered. Output went to a scratch
directory; nothing was written under `hw/soc/pnr/runs/`. Section 14
has the commands.

**The first attempt did not reproduce the flow, and the reason is
`docs/31` section 3.2's.** The step's own `config.json` records
`"TIME_DERATING_CONSTRAINT": 5` — the float `5.0` of `config-ecc.json`
flattened on serialisation, exactly as `resolved.json` is — and the
re-run's log read `Setting timing derate to: 5%` where the flow's
reads `5.0%`. With the derate silently at zero the resizer's iteration
0 was **−10.516 ns on 3,346 endpoints** for the hardened design and
**−8.160 on 3,326** for the baseline: 1.744 and 1.623 ns better than
the flow, on the same ODB, same libraries and same route
**[fact, both scratch logs and `_env.tcl`]**. The global route itself
was byte-identical in wirelength and net count. Correcting the copy of
each `config.json` to `5.0` (and `OUTPUT_CAP_LOAD` to its original
`6.0`, which happened to survive integer division) restored `5.0%` and
the flow's iteration-0 row exactly.

> **So the step-rerun form — `librelane.steps run` on a step directory's
> own `config.json` — is a fourth place the lossy key bites**, after
> `resolved.json`, `docs/28`'s and `docs/31`'s. A reader who re-runs a
> step this way to reproduce a number will get one 1.6 to 1.7 ns
> better and no warning. Section 12 adds a dated note to `docs/31`.

### 7.2 It reproduces the flow to the byte

Hardened run, instrumented step against the flow's step 36 **[fact]**:
`or_metrics_out.json` **53 keys, 0 differ** — 102 setup buffers, 4 hold
buffers, 60,200 instances, 872,652 um2, 3,782,350 um estimated wire;
`soc_top.nl.v`, `soc_top.def`, `soc_top.odb`, `soc_top.sdc`
**byte-identical**; every row of the verbose table identical; the
`RSZ-0059/0040/0051/0043/0062` lines identical. Step time 11 m 03.71 s
against 9 m 52.82 s, the difference being the trace and three reports.
Baseline, the same comparison against `s70base`'s step 36: `or_metrics_out.json`
**52 keys, 0 differ** — 519 setup buffers, 4 hold buffers; `soc_top.nl.v`,
`soc_top.def`, `soc_top.odb`, `soc_top.sdc` **byte-identical**; the
`RSZ` lines and the final row (−3.272 / −1,721.7 / −6,302.9 / 3,102)
identical **[fact]**. Step time 19 m 22.43 s against the flow's
21 m 38.29 s — the instrumented copy ran faster than the original on a
host whose load differs from run to run, which is `docs/71` section 14's
point about step timers made once more.

The debug trace therefore describes the flow's own run.

### 7.3 The hardened trace

`LEGACY*` phase, every endpoint it visited, the WNS and TNS at the
moment it was taken up, and how its inner loop ended **[fact, the
trace]**:

| # | endpoint | register | WNS at entry | endpoint slack | TNS | exit |
|---:|---|---|---:|---:|---:|---|
| 1 | `_80296_/D` | `s_rdata_clint[2]` | −12.260 | −12.260 | −20,775.3 | chased the worst endpoint to −7.990 over 257 iterations, then **stuck after 51 non-improving passes** on `s_rdata_clint[26]` |
| 2 | `_80303_/D` | `s_rdata_clint[9]` | −7.990 | −6.881 | −17,581.4 | stuck after 51 |
| 3 | `_80316_/D` | `s_rdata_clint[22]` | −7.987 | −6.282 | −17,490.4 | stuck after 51 |
| 4 | `_80319_/D` | `s_rdata_clint[25]` | −7.987 | −6.227 | −17,490.4 | stuck after 51 |
| 5 | `_80310_/D` | `s_rdata_clint[16]` | −7.987 | −6.197 | −17,490.4 | stuck after 51 |
| 6 | `_80311_/D` | `s_rdata_clint[17]` | −7.987 | −6.227 | −17,490.4 | stuck after 51 |
| 7 | `_80317_/D` | `s_rdata_clint[23]` | −7.987 | −6.169 | −17,490.4 | stuck after 51 |
| 8 | `_80320_/D` | `s_rdata_clint[26]` | −7.987 | −7.987 | −17,490.4 | stuck after 51 |
| 9 | `_77697_/D` | `u_clint.err_o` | −7.987 | −6.048 | −17,490.4 | stuck after 51 |
| 10 | `_80321_/D` | `s_rdata_clint[27]` | −7.987 | −7.949 | −17,490.4 | stuck after 51 |
| 11 | `_80314_/D` | `s_rdata_clint[20]` | −7.987 | −7.935 | −17,486.8 | stuck after 51 |
| 12 | `_80318_/D` | `s_rdata_clint[24]` | −7.987 | −7.642 | −17,486.8 | stuck after 51 |
| 13 | `_80315_/D` | `s_rdata_clint[21]` | −7.987 | −7.426 | −17,485.5 | stuck after 51 |
| 14 | `_77629_/D` | `u_mtime_dec.check_raw[4]` | −7.987 | −7.579 | −17,485.5 | stuck after 51 |
| 15 | `_80308_/D` | `s_rdata_clint[14]` | −7.987 | −7.379 | −17,474.7 | stuck after 51 |
| 16 | `_77626_/D` | `u_mtime_dec.check_raw[1]` | −7.987 | −7.873 | −17,474.7 | stuck after 51 |
| 17 | `_77627_/D` | `u_mtime_dec.check_raw[2]` | −7.987 | −7.561 | −17,468.5 | stuck after 51 |
| 18 | `_80295_/D` | `s_rdata_clint[1]` | −7.987 | −7.157 | −17,468.5 | **`Exiting at iteration 1100 because incr fix rate 0.01% is < 0.02%`** |
| 19 | `_77625_/D` | `u_mtime_dec.check_raw[0]` | −7.987 | −7.562 | −17,465.7 | stuck after 51 |
| 20 | `_77631_/D` | `u_mtime_dec.check_raw[6]` | −7.987 | −7.370 | −17,465.7 | **`Exiting at iteration 1200 because incr fix rate 0.00% is < 0.02%`**, then `Exiting due to no TNS progress for two opto cycles` |

Twenty endpoints of 3,365. Every one of them is a register of
`u_clint` or the fabric's registered response from it; `u_boot` is not
among them, as `docs/70` section 6.3 said it would not be. Eighteen
"stuck" lines: 18 × 51 = 918 iterations in which every change the
resizer made was undone. The TNS column moves by 0.1 to 11 ns per
endpoint, which is what "0.01 % of −20,775" means, and the rule that
tests it fires the first two times it can.

`LAST_GASP+` phase, from iteration 1,200 **[fact]**: 3,353 violating
endpoints remain; **156 visited, 48 moves accepted, 150 rejected**
(a move must improve both WNS and TNS); `Exiting at iteration 1300 …
[endpoint 62/3353]` and `… 1400 … [endpoint 156/3353]`. WNS −7.987 →
−7.841, endpoints 3,353 → 3,347. That 0.146 ns is the whole of what the
second phase found.

### 7.4 The baseline trace

`LEGACY*` phase, every endpoint it visited **[fact, the trace]**:

| # | endpoint | register | WNS at entry | endpoint slack | TNS | exit |
|---:|---|---|---:|---:|---:|---|
| 1 | `_79820_/D` | `s_rdata_clint[25]` | −9.783 | −9.783 | −20,085.0 | chased the worst endpoint for **2,005 iterations**, from −9.783 to −3.272; ended on `u_ram…u_b0/A_MEN`, the RAM's memory-enable pin, with `No change possible` |
| 2 | `_79813_/D` | `s_rdata_clint[18]` | −3.272 | −3.240 | −7,211.9 | no change possible |
| 3 | `_79814_/D` | `s_rdata_clint[19]` | −3.272 | −2.583 | −7,211.9 | no change possible |
| 4 | `_79815_/D` | `s_rdata_clint[20]` | −3.272 | −2.553 | −7,164.2 | no change possible |
| 5 | `_79816_/D` | `s_rdata_clint[21]` | −3.272 | −2.795 | −7,164.2 | **`Exiting at iteration 2200 because incr fix rate -0.04% is < 0.04%`** |
| 6 | `_79800_/D` | `s_rdata_clint[5]` | −3.272 | −2.604 | −7,173.2 | stuck after 51 non-improving passes |
| 7 | `_79798_/D` | `s_rdata_clint[3]` | −3.272 | −2.205 | −7,173.2 | **`Exiting at iteration 2300 because incr fix rate 0.03% is < 0.04%`**, then `Exiting due to no TNS progress for two opto cycles` |

Seven endpoints of 3,367, and the same registers: the CLINT's
read-data flops are the worst endpoints in the baseline too, at −3.272
instead of −7.987. The threshold reads 0.04 % here because
`terminateProgress()` doubles it at iterations 1,000 and 2,000; the
2,200 window went slightly backwards (−0.04 %) and the 2,300 window
gained 0.03 %, both under it.

**So the two `LEGACY` phases are the same phase**: one long chase of the
worst endpoint, then a handful of CLINT registers that cannot be
moved, then the no-progress rule. The chase is where they differ —
2,005 productive iterations against 257 — and the chase ends, in both,
when the worst path has no improving move left. In the baseline that
point is −3.272 ns on the memory-enable path into the RAM; in the
hardened run it is −7.987 ns on the CLINT read path whose crossing
stage section 6.3 names.

`LAST_GASP+` phase, from iteration 2,300 **[fact]**: 3,120 violating
endpoints remain; **70 visited, 133 moves accepted, 63 rejected**;
`Exiting at iteration 2400 … [endpoint 22/3120]` and `… 2500 …
[endpoint 70/3120]`. WNS unchanged at −3.272; endpoints 3,120 → 3,102;
the accepted moves are on the register file's check bits, the RAM's
byte masks and `crash_dump_o`, the TNS population rather than the WNS
path.

---

## 8. Where the 4.07 ns is

### 8.1 The decomposition

On the resizer's own analysis, both runs, the same corners and the same
parasitics on each side **[fact, iteration 0 and the final row of each
table]**:

| | baseline | hardened | difference |
|---|---:|---:|---:|
| iteration 0 | −9.783 | −12.260 | **−2.477: handed** |
| final, after `LAST_GASP` | −3.272 | −7.841 | −4.569 |
| **recovered by the step** | **6.511** | **4.419** | **−2.092: not recovered** |
| step 37, LibreLane's STA on the re-routed design | −4.1113 | −8.1852 | −4.0739 |
| sign-off, extracted parasitics (`docs/70` 6.1) | −4.8076 | −9.1085 | −4.3009 |

Of the 2.092 ns the hardened resizer did not recover, the trace says
where it went: the baseline loop was still improving WNS at iteration
2,000 and stopped at −3.272 because nothing improved it further; the
hardened loop stopped improving WNS at iteration 257, at −7.990, for
the same reason, four nanoseconds higher. Both are "no further
improvement". The two designs simply hit that wall at different heights,
and the height is set by which gates are left driving the macro-crossing
nets on the CLINT read path.

### 8.2 What the hardened resizer could not do, in one cell

The stage that binds the hardened design after repair is `_68128_`, a
`sg13g2_nand3_1` in the ROM pocket driving 184 fF into the channel.
The move sequence is `UnbufferMove SizeUpMove SwapPinsMove BufferMove
CloneMove SplitLoadMove` **[fact, `RSZ-0100`]**. Size-up has no
`nand3_2` to go to. Buffering a fanout-1 net of 184 fF splits the wire
but adds a stage, and the trace's nineteen "stuck" endpoints — all
downstream of these crossings — are the record of buffers being
inserted and restored because they did not improve the endpoint. Pin
swap and cloning do not shorten a wire. What would is a placement in
which the CLINT's read mux and its response register are on the same
side of the ROM macro, and that is not a `repair_timing` move.

*Tried 2026-09-06 by `docs/73-clint-placement-probe.md`. The
condition is necessary and not sufficient: with the response register
and the exclusive part of its mux moved to the channel and the decode
that selects it, and the mtime SECDED decoder, left in the pocket, the
register-file read crosses the ROM four times instead of two, the
worst path moves into the CLINT's time base with four crossings and
three 300–740 fF stages, and the resizer's loop gives up at −10.67
instead of −7.99 after the same rule. The constraint has to capture
the registers together with their drivers; one that captures one
without the other moves the crossing to the cut.*

### 8.3 No frequency

`docs/53` section 9.2 refused a frequency on three grounds and `docs/05`
section 4 rule 5 binds any published figure to a measurement or a
target. **Nothing here moves any of the three.** This document reports
slack against **20 ns** — −9.1085 and −4.8076 ns at sign-off, unchanged
from `docs/70` — and converts nothing into a clock rate.

---

## 9. The checkers, re-audited

`hw/openlane/checker_audit.py`, on `runs/s71boot` and `runs/s70base2`,
read and not written:

```
    17 of 19 in-flow checkers gate fully.
    NOT gating in full: Checker.LintWarnings, Checker.WireLength
    registered but not in the Classic flow: Checker.KLayoutAntenna,
                                            Checker.KLayoutDensity
```

**[fact; exit status 1 on both, by the script's own contract, `docs/71`
section 9]**. `Checker.HoldViolations` bound to three corners and
reporting `all 0`; `SetupViolations` violating at `nom_slow_1p08V_125C`;
`MaxSlew` and `MaxCap` violating at all three. `signoff_report.py` on
the same two runs reproduces every figure of `docs/70` sections 5.1 and
6.1 — section 2 — and the derate line reads `5.0%` in both flow logs.

**The two scratch step runs of section 7 are single steps and pass
through no checker**; they are not layouts and no figure from them is
a sign-off figure. Their function is to reproduce step 36 and print its
trace, and section 7.2 is the evidence that they did.

---

## 10. Which prior conclusions survive

| Conclusion | Where | Status after this document |
|---|---|---|
| `docs/70`'s −4.3009 ns is a regression, not a draw | `docs/71` 6.2 | **Survives, and is now explained**: 2.477 ns handed to the resizer and 2.092 ns it could not recover, section 8 |
| The post-GRT resizer inserted 102 setup buffers against 519 | `docs/70` 6.2 | **Survives, and the "why" is closed**: not a cap; the loop aborted on OpenROAD's no-progress rule after 20 endpoints it could not improve |
| "The design 0.67 % larger left the resizer a different set of legal placements" | `docs/70` 6.2, one of two readings | **This one, sharpened**: a different placement of the CLINT read path across the ROM macro, section 6.4 |
| "`repair_design`'s and `repair_timing`'s own iteration budget terminated differently" | `docs/70` 6.2, the other reading | **Not as a budget.** The same rule ended both; it ended one earlier because there was nothing to do |
| `docs/48`'s floorplan is HPWL-optimal and the placer is not density-bound | `docs/48` 5 | **Survives** (utilisation 0.688 at step 24, both runs) — with the addition that the pockets it leaves are where the CLINT's read logic goes, in both runs |
| `docs/48` 6.3: five of six heavy cells have no larger version | `docs/48` 6.3 | **Survives, and is the mechanism's other half**: the binding stage after repair is a one-drive `nand3_1` |
| `docs/31` 3.2: `resolved.json` is lossy for the derate | `docs/31` 3.2 | **Survives, and extends to the step's own `config.json`**, section 7.1 |
| `u_boot` is on none of the violating paths | `docs/70` 6.3 | **Survives**: none of the 20 + 156 endpoints the hardened phases visited, none of the 7 + 70 the baseline's did |
| The flow is deterministic; a resume loses nothing | `docs/71` 6.1, 6.3 | **Used, not re-measured**: the step re-run on a saved state reproduces the flow's step to the byte |
| Every noise floor is netlist sensitivity | `docs/71` 7 | **Survives with an example at the cell**: section 6.4 |

---

## 11. What this does NOT cover

Stated at length, in the discipline `docs/47` section 9, `docs/62`
section 13, `docs/67` section 11, `docs/68` section 12, `docs/69`
section 11, `docs/70` section 11 and `docs/71` section 11 set. Those
lists stand unchanged except where this document names an item.

- **THIS IS NOT A PHYSICAL SIGN-OFF. THERE IS NO DRC RESULT, NO LVS
  RESULT AND NO XOR RESULT, AND NOTHING HERE MAY BE READ AS THOUGH
  THERE WERE.** `RUN_MAGIC_DRC`, `RUN_KLAYOUT_DRC`, `RUN_KLAYOUT_XOR`
  and `RUN_LVS` are all **0** in `config-ecc.json` **[fact]**, for the
  reason `docs/12` sections 7.5 and 8 measured — a **NO-GO on
  RM_IHPSG13 for this PDK version** — and `docs/54` examined in full.
  No layout was produced by this document at all. **`Yosys.EQY` is off**
  and no gate-level simulation of `soc_top` exists. *The latter since
  2026-09-06 no longer: `docs/74-core-gate-level-campaign.md`.*
- **NO NEW LAYOUT AND NO EXPERIMENT.** Two single steps were re-executed
  on saved states with nothing varied. Nothing here says what a
  different placement, a placement constraint on `u_clint`, a
  registered bus request or a different resizer phase sequence would
  measure; section 15 prices none of them.
- **ONE STAGE IS ATTRIBUTED, NOT THE WHOLE 2.477 ns.** Section 6.3's
  3.73 ns stage accounts for 2.41 ns of the 2.48 ns difference between
  two paths that are otherwise 90 and 75 stages long; the remaining
  stages differ in both directions and were not paired one to one.
- **WHY STEP 33 LEFT A 4.69 ns TRANSITION IS NOT MEASURED.** Section
  6.3: `repair_design` ran on an earlier route, before the antenna
  diode on that net was placed and before step 36's own re-route; which
  of those produced the violation the resizer met was not separated.
- **THE PRE-REPAIR PATH REPORTS PRINT TWO DECIMALS**, OpenSTA's default;
  every figure from section 7's reports is quoted at that precision and
  no four-decimal figure is claimed from them. Four-decimal figures come
  from the flow's own `max.rpt` and `or_metrics_out.json`.
- **THE RESIZER'S OWN STA IS NOT THE FLOW'S STA.** Iteration-0 and
  final WNS are over `PNR_CORNERS` on the resizer's incremental
  parasitics; step 37's −4.1113 / −8.1852 are LibreLane's report on
  the re-routed design. The two differ by 0.3 to 0.8 ns in both runs
  and are never mixed in one subtraction here.
- **THE `EST-0026` WARNINGS ARE NOT INTERPRETED.** The hardened run's
  steps 33 and 36 print 1,001 `Missing route to pin … in net …` lines
  over 153 nets during their **second** global route, after
  `repair_design` and `repair_timing` respectively; the baseline prints
  none, and step 37's fresh parasitic estimate prints none in either run
  **[fact, `grep -c`]**. They occur after every number this document
  reads from those steps and before none.
- **ONE NETLIST PAIR, ONE FLOORPLAN, ONE MACHINE, ONE BINARY.** The
  source read is the installed OpenROAD's commit; a different build
  may stop by a different rule.
- **THE FAST CORNER'S MACRO LIBERTY IS CHARACTERISED AT −55 C**,
  `docs/12` section 6.4a; nothing here touches hold.
- **NO BEHAVIOURAL EVIDENCE WAS ADDED AND NONE WAS NEEDED.** No RTL was
  modified. The Python suite was re-run as a check that the tree did
  not move, section 13.
- **NO WALL-CLOCK FIGURE IS A WALL-CLOCK FIGURE.** The step timers in
  sections 2, 4.2 and 7.2 are the flow's own `runtime.txt`, on a host
  carrying one unrelated process; `docs/71` section 14 is the
  demonstration of what they do and do not measure.

---

## 12. Corrections to earlier documents

Every one is a dated in-place note in the corrected file, by `docs/64`
section 2's rule; every original sentence stands.

- **`docs/70` section 6.2's** *"Why it did less is not established by
  this document"* and its two readings; **section 11's** bullet *"THE
  SETUP REGRESSION'S MECHANISM IS LOCALISED, NOT EXPLAINED"*; **section
  15 item 2**: closed, with the mechanism in one sentence each.
- **`docs/71` section 11's** bullet *"THE SETUP REGRESSION IS STILL
  LOCALISED, NOT EXPLAINED"* and **section 15 item 1**: closed, and the
  `-max_iterations` sweep it suggested is recorded as answered by the
  trace rather than run.
- **`docs/31` section 3.2**: a note that a step directory's own
  `config.json` is lossy for the derate in the same way as
  `resolved.json`, that `librelane.steps run` on it therefore does not
  reproduce the flow's step, and by how much: 1.744 and 1.623 ns at the
  resizer's iteration 0 here.
- **`docs/00-index.md`**: one row, which `sw/tests/test_doc_links.py`
  requires.

---

## 13. Files touched

| file | change |
|---|---|
| `docs/72-post-grt-resizer.md` | this document |
| `docs/00-index.md` | one row |
| `docs/70-boot-hardening-placed.md` | dated notes: section 6.2, section 11 (bullet closed), section 15 (item 2 closed) |
| `docs/71-layout-reproducibility.md` | dated notes: section 11 (bullet closed), section 15 (item 1 closed) |
| `docs/31-signoff-6x2.md` | section 3.2, a dated note: the step's own `config.json` is lossy too |

**Nothing else in the repository is modified.** No RTL, no flow script,
no test, no configuration. The two instrumented step runs, the
instrumented copy of `rsz_timing_postgrt.tcl`, the two corrected copies
of the step `config.json` files and the runner script live in this
session's scratch directory and are not part of the repository; the
run directories `hw/soc/pnr/runs/s70base`, `s70base2` and `s71boot`
were read and not written.

**Nothing in `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is
modified and `hw/tb/Makefile.fi` was not invoked. `docs/34`'s freeze is
untouched.**

The Python suite: **454 passed, 0 failed** **[fact, `.venv/bin/python -m pytest sw/tests -q`]** — `docs/71` section 13 reports 453 with that document present, and `sw/tests/test_doc_links.py` discovers the corpus, so this document adds exactly one test.

---

## 14. Reproducing this

```
# 0. the instruments
V=$HOME/Documents/caravel-lif-crossbar/.venv-flow/bin/python
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/s71boot        # -9.1085 / 3361
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/s70base2       # -4.8076 / 3108
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/s71boot; echo $?   # 17 of 19, 1
python3 -c "
import json
a=json.load(open('hw/soc/pnr/runs/s70base/resolved.json'))
b=json.load(open('hw/soc/pnr/runs/s71boot/resolved.json'))
print(sorted(k for k in set(a)|set(b) if a.get(k)!=b.get(k)))"   # []

# 1. the step's report, both runs
for r in s70base s71boot; do
  L=hw/soc/pnr/runs/$r/36-openroad-resizertimingpostgrt/openroad-resizertimingpostgrt.log
  grep -E '^\+ repair_timing|RSZ-00(94|99|59|40|51|43|62)' $L      # 519 / 102, RSZ-0062 both
  grep -E '^ +[0-9]+[*+] \||^ *final' $L | awk -F'|' 'NF>=12' | \
    awk '$1 ~ /00\*$|00\+$|final/'                                # the hundreds and the phase exits
  grep -E 'GRT-00(96|18|14)' hw/soc/pnr/runs/$r/31-openroad-globalrouting/*.log
  cat hw/soc/pnr/runs/$r/36-openroad-resizertimingpostgrt/runtime.txt
done
python3 -c "
import json
for r in ['s70base','s71boot']:
  m=json.load(open(f'hw/soc/pnr/runs/{r}/resolved.json'))
  print({k:m[k] for k in m if k.startswith('GRT_RESIZER_SETUP')})"   # identical

# 2. the stopping rules, at the installed binary's commit
grep -m1 OpenROAD hw/soc/pnr/runs/s71boot/36-*/openroad-resizertimingpostgrt.log
curl -sL https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD/0e2d771c5e/src/rsz/src/RepairSetup.cc \
  | grep -n 'terminateProgress\|decreasing_slack_max_passes\|two_cons_terminations\|special_markers'
curl -sL https://raw.githubusercontent.com/The-OpenROAD-Project/OpenROAD/0e2d771c5e/src/rsz/src/RepairSetup.hh \
  | grep -n 'interval_\|fix_rate_threshold_'
echo 'help repair_timing' | ~/.local/opt/llbin/openroad -no_init -no_splash -exit

# 3. the instrumented step re-run: the flow's own step, on the flow's own
#    saved state, with the trace on. Runs outside the repository.
S=/some/scratch/dir; LL=$($V -c "import librelane,os;print(os.path.dirname(librelane.__file__))")
#    a. a copy of the step script with report_wns/report_tns/report_checks
#       before and after the setup repair_timing and
#       'set_debug_level RSZ repair_setup 2' around it; no argument changed
#    b. a copy of runs/<r>/36-*/config.json with
#       "TIME_DERATING_CONSTRAINT": 5  ->  5.0   and  "OUTPUT_CAP_LOAD": 6 -> 6.0
#       (without (b) the re-run derates by 0 % and reads 1.7 ns better)
cat > $S/run_step_instr.py <<'EOF'
import sys, click
import librelane.steps.openroad as OR
import librelane.steps.__main__ as M
script, cfg, state_in, out = sys.argv[1:5]
OR.ResizerTimingPostGRT.get_script_path = lambda self: script
grp = [v for v in vars(M).values() if isinstance(v, click.Group)][0]
grp.main(args=["run", "-c", cfg, "-i", state_in, "-o", out, "--hide-progress-bar"], standalone_mode=False)
EOF
export PATH=$HOME/.local/opt/llbin:$PATH
for r in s71boot s70base; do
  $V $S/run_step_instr.py $S/rsz_timing_postgrt_instr.tcl $S/config36_$r.json \
     hw/soc/pnr/runs/$r/36-openroad-resizertimingpostgrt/state_in.json $S/step36_$r
done
#    reproduction: 53 metrics equal, nl.v/def/odb/sdc byte-identical
cmp hw/soc/pnr/runs/s71boot/36-*/soc_top.odb $S/step36_s71boot/soc_top.odb   # silent
#    the trace
grep -E 'Doing endpoint|stuck after|Exiting|no TNS progress|remain' $S/step36_s71boot/openroad-resizertimingpostgrt.log
grep -c 'Move accepted' $S/step36_s71boot/openroad-resizertimingpostgrt.log   # 48

# 4. the path and the pocket
sed -n '/^Startpoint/,/slack/p' hw/soc/pnr/runs/s71boot/37-openroad-stamidpnr-3/max.rpt | head -300
grep -E '^ *- (_52172_|_68120_|_68128_|_68129_|ANTENNA_21) ' hw/soc/pnr/runs/s71boot/36-*/soc_top.def
grep SIZE $PDK_ROOT/ihp-sg13g2/libs.ref/sg13g2_sram/lef/RM_IHPSG13_1P_1024x32_c2_bm_bist.lef
# region census: classify every PLACED instance in the step-26 DEF by the
# boxes the macro origins in config-ecc.json and the LEF sizes define

# 5. the guards
.venv/bin/python -m pytest sw/tests/test_doc_links.py -q
.venv/bin/python -m pytest sw/tests -q
```

---

## 15. What the next block should be

1. **Put the CLINT's read mux and its response register on one side of
   the ROM.** Section 6.4: both runs split `s_rdata_clint` across the
   upper macro, and the binding stage in the hardened run is a one-drive
   gate driving a macro-crossing net. This is a placement question
   before it is a timing one, and it has a cheap first probe that is
   not a new floorplan: the flow's own `PL_SOFT_OBSTRUCTIONS` or a
   region constraint on `u_clint`'s cells, measured to step 37 on the
   hardened netlist with everything else held. `docs/48`'s lesson
   applies — one probe, not four — and the metric is section 6.4's
   crossing count on the worst path, not the WNS alone. *Done
   2026-09-06 by `docs/73-clint-placement-probe.md`, in two forms. A
   `dbRegion` fence on the derived CLINT set does not route on this
   floorplan — the channel has no 38,000 um2 to give, 3,076 cells
   spread into the macro gaps and the global router ends with 420
   overflow — and the flow's own `MANUAL_GLOBAL_PLACEMENTS`, which
   moves the set and nothing else, routes and reaches sign-off. The
   crossing count on the read path went from 2 to 4, not to 0, because
   the set's boundary cut the co-placed cluster; the worst path moved
   into the time base at −15.1863 at step 37 against −8.1852. The set
   derivation had a defect that shaped both layouts; the corrected set
   and the block's register-to-register closure are derived there and
   the layout that would move the whole cluster is named, not run.*
2. **`docs/50`'s read register, now unblocked.** `docs/70` section 15
   item 3 deferred it until the resizer's behaviour was understood. It
   is: a whole-design setup delta must be read together with the
   worst path's structure — which gate drives which crossing — and a
   4 ns swing on a 51-flop change does not mean the instrument is
   broken, it means the binding path moved by one cell. A re-measurement
   of the read register should report that structure beside its slack.
   *Measured 2026-09-15 on the eight-macro design: `docs/50` section 16. The macro read return stops being a violating launch group (360 endpoints to 17, their TNS -864.88 to -28.87) and the design's setup TNS improves 21.9 %, at the cost of 325.7 ps of the sign-off layout's 29.6 ps hold margin at the fast corner, which takes hold negative. It stays at its default of 0.*

3. **`docs/69`'s strap sampling window**, `docs/70` section 15 item 4,
   likewise unblocked and unchanged.
4. **Guard the step-rerun form.** Section 7.1: a test that a step
   directory's `config.json` round-trips `TIME_DERATING_CONSTRAINT` as
   a float, or a note in `pnr_soc_top.sh`, so that the next reader who
   re-runs a step from its own directory does not get 1.7 ns for free.
   `docs/31` section 3.2's note is the record; ~~the guard is owed.~~
   **DONE 2026-09-12: `sw/tests/test_derate_is_a_float.py`.** It takes
   the first form -- every tracked `config*.json` must write the key as
   a float, seventeen files, checkable on a clone with no run tree --
   and adds the half this repository does not own as a measurement
   rather than an assertion: **1,529 step `config.json` files demote it
   to an int and 0 keep it a float**, printed on every run so the trap
   is a number rather than a memory. The test is mutation-checked in
   both directions.
5. **The one-cycle bus read is the structure under all of this.**
   `soc_bus.v` presents the master's address combinationally and
   `soc_clint.v` decodes and registers the response in the same cycle,
   so the Ibex ALU, the fabric and the peripheral's read mux share one
   period. A registered request phase in the fabric is a latency cost
   on every load and a `docs/50`-class change; it is named here as the
   thing the paths have in common, not priced.
6. **The remaining items of `docs/68` section 16 and `docs/71` section
   15 are unchanged.**
