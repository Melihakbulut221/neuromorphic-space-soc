# 71 — The same netlist laid out twice: the flow is bit-reproducible, and every delta in this corpus is a delta of netlists

`docs/70-boot-hardening-placed.md` section 15 opens its list of what to
do next with the item this document is the answer to:

> **Test whether this flow is reproducible run to run.** Section 11
> names it: every noise floor in this repository — `docs/44`'s 0.4 ns,
> `docs/68`'s area floor, this document's section 5.3 — is a floor over
> netlists that silently assumes the same netlist twice gives the same
> layout. **One re-run of `s70boot`'s netlist under a second tag
> settles it**, it costs one layout, and it decides whether section
> 6.1's −4.3009 ns is a property of a netlist or a draw.

**It is a property of the netlist.** The protected boot netlist —
`md5 a8d5ef81…`, byte-identical to `docs/69`'s and the one `docs/70`
placed — was laid out a second time with nothing changed: the same
file, the same `config-ecc.json`, the same floorplan, the same PDK, the
same tool binaries, the same machine. **`final/metrics.json` is
byte-identical, all 199 keys**; so are the routed DEF (72,036,030
bytes), the OpenDB database (110,756,704 bytes), both netlists, the
SDC, the three Liberty files, the abstract LEF, the extracted SPICE and
the rendered PNG. The GDS, the Magic database, the SPEF and the three
SDFs differ **only in the date stamps their writers put in them**. Of
the 62 steps, **58 are identical in every metric and every view**, and
the four that are not differ by a timestamp or by the run directory's
own name echoed into a report.

So the question `docs/70` section 11 left open closes in the direction
that leaves every earlier number standing: **this flow, on this
machine, is deterministic**, every difference the corpus has ever
reported between two layouts is a difference of the netlists it was
handed, `docs/70`'s −4.3009 ns is a regression and not a draw, and the
control pair of `docs/70` section 5.3 measured **netlist sensitivity**
and not tool noise. What that does to the phrase "noise floor" is
section 7.

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

**And nothing else was modified either, which is the whole point.** No
RTL, no flow script, no test, no configuration file: the value of this
document is that nothing changed between the two layouts, and a change
would have made the comparison meaningless. What changed on disk is
this document, one index row, and the dated in-place notes section 12
names; everything else this session produced is a gitignored run
directory. Section 13.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Is the second layout bit-identical to the first?** | **Yes.** `final/metrics.json`: 199 keys, **0 differ**, byte-identical. DEF, ODB, `nl.v`, `pnl.v`, SDC, LEF, three `.lib`, SPICE, `.vh`, `.h.json` and the PNG render: **byte-identical**. GDS, Magic GDS, KLayout GDS, `.mag`, SPEF and three SDFs: **identical once their date stamps are masked**, and nothing else in them differs **[fact]**. Section 5 |
| **By how much do the figures differ?** | **By zero, to the last digit stored**, for every figure the task named: setup worst slack **−9.1085 / −9.1085**, TNS **−19,989.82 / −19,989.82**, violating endpoints **3,361 / 3,361**, hold at the three corners **+0.0621 / +0.2735 / +0.5897** in both, placed cell area **876,321 / 876,321 um2**, timing-repair buffers **11,530 / 11,530**, routed wirelength **4,248,250 / 4,248,250 um** **[fact]**. Section 5.2 |
| **So what is the post-layout noise floor?** | **The tool's own is zero**, on this machine, for this netlist. `docs/44` section 5.2's 0.4 ns and `docs/70` section 5.3's 0.5031 ns, 0.0198 ns and 12,962 um2 are **not instrument noise**: they are the sensitivity of a deterministic mapper–placer–router chain to a change in its input. They remain the resolution to use **when the netlist changes**; they do not apply to a re-run. Section 7 |
| **Is `docs/70`'s −4.3009 ns real?** | **Yes.** Two layouts of the same netlist agree to the bit, so two layouts of different netlists differ because of the netlists. The regression is the flow's response to `docs/69`'s 414 cells, and `docs/70` section 6.2's mechanism — 102 setup repair buffers against 519 — is reproduced exactly here. Section 6 |
| **Did `docs/70`'s control pair measure tool noise?** | **No; it measured netlist sensitivity**, which is what it is now called. `docs/68`'s −0.0297 ns hold delta stays withdrawn as a measurement, for the same reason and with the sharper name. Section 7 |
| **Does the resume-from-state form lose anything?** | **No, and this is now a measurement rather than an argument.** `docs/70`'s `s70boot2` was resumed from `37-openroad-stamidpnr-3/state_out.json`; this document's `s71boot` ran all 62 steps uninterrupted in one directory. They are byte-identical at every step from 38 on. `docs/70` section 5.3's last paragraph is answered. Section 6.3 |
| **What determines reproducibility in this flow?** | **One seed, one thread count, both in one step.** LibreLane's `drt.tcl` passes `detailed_route -or_seed 42`, hard-coded and not a configuration variable, and it is the **only** OpenROAD script in the installed LibreLane that calls `set_thread_count`; `DRT_THREADS` is unset and defaults to `os.cpu_count()`, **20** here in both runs. No other OpenROAD command in this flow exposes a seed. STA parallelism is one process per corner. Section 3 |
| **Does the thread count matter?** | **Not at the two counts tried.** One bounded experiment — `s71boot`'s own step-37 state resumed with `_OPENLANE_MAX_CORES=10`, the router only — gives a routed database **byte-identical** to the 20-thread one, all 74 step metrics equal, in 35 m 42 s of step time against 36 m 19 s. Section 8 |
| **Did the checkers keep watching?** | **17 of 19, the same seventeen and the same two**, recomputed from the installed LibreLane's own step classes against the run's own `resolved.json`; `Checker.HoldViolations` bound to three corners and reporting `all 0`. **`checker_audit.py` exits 1**, which is what its own contract says it must do when any checker is NO-GATE, and five documents that wrote "exit 0" are corrected. Section 9 |
| **May a frequency be published?** | **No.** `docs/53` section 9.2's three grounds and `docs/05` section 4 rule 5 bind, and nothing here moves any of them. Slack against **20 ns** is what this document reports. Section 5.4 |

> **THE ONE-SENTENCE RESULT.** Given the same netlist, this flow gives
> the same layout to the byte — so every "noise floor" this corpus has
> measured is the flow's sensitivity to its input and not its
> sensitivity to being run, and every delta between two layouts is a
> delta the netlists caused.

---

## 2. Reproducing every instrument before moving it

`docs/44` section 5.2 set the rule and every physical document since
`docs/45` follows it. Everything below was measured in this session,
**before** the second layout was started, from `docs/70`'s own run
directories.

| What | Published | Measured here |
|---|---|---|
| `s70boot2` sign-off, slow corner | `docs/70` 6.1: **−9.1085 ns, TNS −19,989.82, 3,361 endpoints** | **−9.1085 / −19,989.815538 / 3,361** out of `runs/s70boot2/final/metrics.json` via `signoff_report.py` **[fact]** |
| `s70boot2` hold, three corners | `docs/70` 5.1: **+0.0621 / +0.2735 / +0.5897**, 0 violations | **+0.0621 / +0.2735 / +0.5897**, 0 / 0 / 0 **[fact]** |
| `s70boot2` area and census | `docs/70` 4.2: **876,321 um2, 60,868 cells, 5,873 sequential, 11,530 / 148,692 um2 repair buffers, 102 setup buffers, 4,248,250 um wirelength, 0 DRC, 1 antenna net, 674 diodes** | every figure, digit for digit **[fact]** |
| `s70boot2` stage table | `docs/70` 6.2: **−157.3530 / −12.5734 / −2.5962 / −8.1852** at steps 23 / 28 / 30 / 37 | **−157.353 / −12.5734 / −2.59617 / −8.18517** from each step's `or_metrics_out.json` **[fact]** |
| `s70boot2` checker audit | `docs/70` 8: **17 of 19**, `LintWarnings` and `WireLength` abstaining | **17 of 19**, the same two **[fact]** — and the exit status is **1**, section 9 |
| `s70boot2` step timers | `docs/70` 14: **33 m 53.01 s / 1 h 32 m 26.97 s**, detailed routing **1 h 20 m 23.49 s** | **33 m 53.01 s / 1 h 32 m 26.97 s / 1 h 20 m 23.49 s** from 59 `runtime.txt` files **[fact]** |
| the netlist | `docs/70` 2: **`md5 a8d5ef81…`**, byte-identical to `docs/69`'s | `a8d5ef81446ce6d2aa2eb4c1e0fdff79` for both `hw/soc/out/s70-rom0-syn/soc_top.netlist.v` and `hw/soc/out/s69-rom0-syn/soc_top.netlist.v` **[fact]** |
| the configuration | `docs/70` 3.1: `config-ecc.json` unchanged, not regenerated | `md5 bae01711…`, and `git status` clean at `27b60ba` **[fact]** |

**[fact for every row]**

---

## 3. What determines reproducibility in this flow, read before anything was run

The question `docs/70` section 11 asked cannot be answered by a layout
alone, because a layout that reproduces might do so by luck on a flow
that has no right to. So the flow was read first: which steps take a
seed, whether the seed is pinned, which steps are multi-threaded, and
what the resume form carries. All of it is in the installed LibreLane
v3.0.5 and the installed OpenROAD `26Q1-2938-g0e2d771c5e`, read in
place.

### 3.1 Seeds

| Step | Command | Seed | Where |
|---|---|---|---|
| `OpenROAD.GlobalPlacementSkipIO`, `OpenROAD.GlobalPlacement` | `global_placement` | **none exposed.** The installed binary's `help global_placement` lists 36 options and no seed | `librelane/scripts/openroad/gpl.tcl` |
| `OpenROAD.DetailedPlacement` | `detailed_placement` | none exposed | `common/dpl.tcl` |
| `OpenROAD.CTS` | `clock_tree_synthesis` | none exposed | `cts.tcl` |
| `OpenROAD.RepairDesign*`, `OpenROAD.ResizerTiming*` | `repair_design`, `repair_timing` | none exposed | `repair_design.tcl`, `rsz_timing.tcl` |
| `OpenROAD.GlobalRouting` | `global_route` | none exposed | `common/grt.tcl` |
| **`OpenROAD.DetailedRouting`** | `detailed_route` | **`-or_seed 42`, hard-coded** at `drt.tcl` line 89. The binary also accepts `-or_k`; LibreLane does not pass it. **There is no `DRT_SEED` configuration variable** in `librelane/config/` or `librelane/steps/`; the seed cannot be changed from a configuration file | `drt.tcl` |

**[fact, `grep -rn seed` over the installed package, and the binary's
own `help` output for each command]**

So the one command in the flow that has a seed has it pinned by the
tool vendor, and the rest have none to pin. That is the necessary
condition for reproducibility and it is not the sufficient one: a
multi-threaded algorithm with a fixed seed can still depend on the
order its threads finish in.

### 3.2 Threads

| Variable | Default in this flow | What it controls |
|---|---|---|
| `DRT_THREADS` | `None` in `resolved.json`; `OpenROAD.DetailedRouting.run()` substitutes `_get_process_limit()`, which is **`_OPENLANE_MAX_CORES` if set, else `os.cpu_count()`** — **20** on this machine, and `_OPENLANE_MAX_CORES` was not set in either session | `set_thread_count` inside `drt.tcl`, line 73 — **the only `set_thread_count` in LibreLane's OpenROAD scripts** |
| `STA_THREADS` | `None`; the same substitution | the worker count of a `ThreadPoolExecutor` whose jobs each **spawn a separate `openroad` process per corner**. Parallelism between processes, not inside one; each corner's STA is single-threaded |
| `KLAYOUT_DRC_THREADS`, `KLAYOUT_XOR_THREADS`, `KLAYOUT_DENSITY_THREADS` | `None` | steps that are **off** in `config-ecc.json` (`RUN_KLAYOUT_DRC`, `RUN_KLAYOUT_XOR` both 0; density not in the Classic flow) |

**[fact, `librelane/common/misc.py` line 426, `steps/openroad.py`
lines 774, 2001–2002 and 2162, `scripts/openroad/drt.tcl` line 73]**

The logs agree: `[INFO ORD-0030] Using 20 thread(s).` appears in
exactly one step's log in each of `s70boot2` and `s71boot` — the
detailed router's — and in no other OpenROAD log of either run
**[fact, `grep ORD-0030` over every step log]**. Every other OpenROAD
step ran at the binary's default thread count, which it does not
announce.

**So the whole question reduces to one step:** TritonRoute, 20
threads, seed 42. Everything upstream of it is single-threaded and
seedless, and everything downstream — fill, extraction, STA, stream-out
— is a function of the routed database. Whether a 20-thread
TritonRoute reproduces is the measurement of section 5; whether it
reproduces at a **different** thread count is section 8.

### 3.3 The resume form

`docs/61` section 17's `-F <step> -i <state_out.json>` form, which
`docs/67` section 14 and `docs/70` section 3.3 used, restores a
LibreLane `State`: the paths of every view the interrupted run had
produced (ODB, DEF, netlist, SDC, SPEF and the rest) plus the metrics
dictionary as of that step. It does **not** restore process-level
state — no OpenROAD process survives — so anything a step needed that
was not in a view would be lost. `docs/70` section 5.3 flagged exactly
this: *"the resume restores the step's own `state_out.json`, so the
comparison should be of netlists, but that is an argument and not a
measurement."*

This document's run was **not** resumed. It ran all 62 steps in one
directory, and section 6.3 compares its steps 38–62 against the
resumed `s70boot2`'s 01–25.

---

## 4. What was run

### 4.1 The command, and that it is `docs/70`'s

`docs/70` section 14 step 2, with the tag changed and nothing else:

```
SYN_NETLIST=$PWD/hw/soc/out/s70-rom0-syn/soc_top.netlist.v \
PNR_CONFIG=$PWD/hw/soc/pnr/config-ecc.json \
PNR_STATE=$PWD/hw/soc/pnr/state/s71boot.state.json \
hw/soc/flow/pnr_soc_top.sh s71boot --overwrite -F Yosys.JsonHeader \
    -S Yosys.Synthesis -S Checker.YosysUnmappedCells \
    -S Checker.YosysSynthChecks -S Checker.NetlistAssignStatements \
    -i $PWD/hw/soc/pnr/state/s71boot.state.json
```

LibreLane v3.0.5, OpenROAD `26Q1-2938-g0e2d771c5e`, `ihp-sg13g2` at
`c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c` enabled through
`$PDK_ROOT/ihp-sg13g2`, rootless, 61 Verilog files, three corners,
extracted parasitics, 5 % derate logged as `5.0%`, 20 ns **[fact, the
flow log]**. The netlist is the file `docs/70` placed, not a
re-synthesis of it: `md5 a8d5ef81…` before the run and after it.

**The configuration is asserted rather than described**, in the form
`docs/70` section 3.1 used:

```
keys differing between runs/s70boot/resolved.json and
runs/s71boot/resolved.json: []
```

**[fact]** — not one key, `VERILOG_FILES` included. The only file the
flow script writes outside the run directory is the gitignored
`hw/soc/pnr/config.resolved.json`, which it regenerates identically on
every invocation and asserts contains `config-ecc.json` plus
`VERILOG_FILES` and nothing else.

### 4.2 The machine, and what else was on it

One run, uninterrupted, on the machine `docs/70` used: 20 logical
CPUs, 31 GiB, load average **6.34** at launch with a process from an
unrelated project occupying about one core throughout **[fact,
`uptime`]**. `docs/70`'s two layouts ran **concurrently with each
other** on the same machine; this one ran alone. If the result depended
on scheduling, this is the comparison in which it would have shown.

**NO WALL-CLOCK FIGURE HERE IS A WALL-CLOCK FIGURE**, `docs/67` section
14's rule. The flow log's first and last lines are 22:13:33 and
23:37:55, which is 1 h 24 m 22 s of contended wall time and is quoted
only so that a reader knows the run was not interrupted; the flow's own
per-step `runtime.txt` is the instrument, section 14.

---

## 5. The result, step by step and then artefact by artefact

### 5.1 Sixty-two steps

Every step of `s71boot` was paired with the same-named step of
`docs/70`'s flow — steps 1–37 from `runs/s70boot`, steps 38–62 from
`runs/s70boot2` (numbered 01–25 there, because it was a resume). For
each pair, the step's `or_metrics_out.json` was compared key by key and
every design view it wrote — `.odb`, `.def`, `.nl.v`, `.pnl.v`, `.sdc`,
`.spef`, `.drc`, `.lef`, `.gds`, `.mag`, `.rpt`, `.json` other than the
state and config files — was compared by MD5.

> **58 of 62 paired steps are identical in every metric and every
> view** **[fact]**, and the four that are not are these:

| step | what differs | and what it is |
|---|---|---|
| `openroad-rcx` | `soc_top.nom.spef`, one line | `*DATE "21:36:16 …"` against `*DATE "23:25:42 …"`. With that line masked the two SPEFs — 2,745,004 lines each — are identical |
| `openroad-irdropreport` | `irdrop.rpt`, two lines | the `analyze_power_grid … -voltage_file <run dir>/net-VPWR.csv` command echoed into the report, with the run directory's own name in it |
| `magic-streamout` | `soc_top.gds`, `soc_top.magic.gds`, `soc_top.mag` | GDS `BGNLIB`/`BGNSTR` records carry creation and modification times: **231 records** per file, identical once masked. The `.mag` file carries **176,664 `timestamp` lines**, one per cell use, identical once masked, with **no other line differing** |
| `klayout-streamout` | `soc_top.klayout.gds` | the same, **392** timestamp records |

**[fact, the comparison script of section 14 and `diff`]**

Every step from `Yosys.JsonHeader` through `OpenROAD.STAPostPNR` —
floorplan, PDN, both global placements, both repair passes, detailed
placement, CTS, both resizers, global routing, antenna repair,
**detailed routing on 20 threads**, fill, extraction and sign-off STA —
wrote the same ODB, the same DEF and the same metrics both times.

### 5.2 The sign-off report, figure by figure

`final/metrics.json` is **byte-identical: 10,400 bytes, 199 keys, 0
differ** **[fact]**. The figures the task named, read out of both files
rather than inferred from the hash:

| figure | `s70boot2`, `docs/70` | `s71boot`, this document | difference |
|---|---:|---:|---:|
| setup worst slack, `nom_slow_1p08V_125C`, ns | −9.108500878019903 | −9.108500878019903 | **0** |
| setup TNS, slow, ns | −19,989.815538437644 | −19,989.815538437644 | **0** |
| setup violating endpoints, slow | 3,361 | 3,361 | **0** |
| setup worst slack, typ / fast, ns | +1.7820 / +8.0527 | +1.7820 / +8.0527 | 0 / 0 |
| hold worst slack, fast, ns | +0.062133189241183634 | +0.062133189241183634 | **0** |
| hold worst slack, typ / slow, ns | +0.2735 / +0.5897 | +0.2735 / +0.5897 | 0 / 0 |
| hold violating endpoints, hold TNS, all corners | 0, 0 | 0, 0 | 0 |
| max slew violations, s / t / f | 47 / 2 / 1 | 47 / 2 / 1 | 0 |
| max cap violations, s / t / f | 16 / 16 / 16 | 16 / 16 / 16 | 0 |
| clock skew, worst setup, ns | 0.9782 | 0.9782 | 0 |
| placed standard-cell area, um2 | 876,321 | 876,321 | **0** |
| cells excluding fill / sequential | 60,868 / 5,873 | 60,868 / 5,873 | 0 / 0 |
| instances including fill | 176,663 | 176,663 | 0 |
| timing-repair buffers, count / um2 | 11,530 / 148,692 | 11,530 / 148,692 | **0** |
| of which setup / hold buffers | 102 / 4 | 102 / 4 | 0 |
| clock buffers / inverters | 745 / 280 | 745 / 280 | 0 |
| routed wirelength, um | 4,248,250 | 4,248,250 | **0** |
| routed wirelength, each of the ten DRT iterations | 4,248,383 … 4,255,974 | the same ten | 0 |
| DRC errors, each of the ten DRT iterations | 378 / 47 / 41 / 0 / 0 / 37 / 20 / 18 / 18 / 0 | the same ten | 0 |
| detailed-routing DRC, final | 0 | 0 | 0 |
| antenna nets / pins / diodes | 1 / 1 / 674 | 1 / 1 / 674 | 0 |
| max-fanout violations, unannotated nets | 565 / 479 | 565 / 479 | 0 |
| utilisation | 0.719817 | 0.719817 | 0 |

**[fact, both `final/metrics.json`, printed at full stored precision
where the task asked for the figure]**

The DRT iteration rows are the sharpest of these: the ten per-iteration
DRC counts and wirelengths are the router's internal trajectory, and a
20-thread router that reached the same result by a different route
would have shown it there. It did not.

### 5.3 The artefacts

| `final/` file | bytes | result |
|---|---:|---|
| `def/soc_top.def` | 72,036,030 | **byte-identical** |
| `odb/soc_top.odb` | 110,756,704 | **byte-identical** |
| `nl/soc_top.nl.v` / `pnl/soc_top.pnl.v` | 10,831,575 / 15,790,283 | **byte-identical** |
| `sdc/soc_top.sdc` | 16,158 | byte-identical |
| `lef/soc_top.lef` | 41,823 | byte-identical |
| `lib/*/soc_top__<corner>.lib`, three | 81,783 / 81,825 / 81,784 | byte-identical |
| `spice/soc_top.spice` | 9,013,389 | byte-identical |
| `json_h/soc_top.h.json`, `vh/soc_top.vh` | 18,223,258 / 901 | byte-identical |
| `render/soc_top.png` | 180,201 | byte-identical |
| `metrics.json` | 10,400 | **byte-identical** |
| `gds/soc_top.gds`, `mag_gds/soc_top.magic.gds` | | identical after masking 231 timestamp records each |
| `klayout_gds/soc_top.klayout.gds` | | identical after masking 392 timestamp records |
| `mag/soc_top.mag` | 4,996,967 lines | identical after masking 176,664 `timestamp` lines |
| `spef/nom/soc_top.nom.spef` | 2,745,004 lines | identical after masking `*DATE` |
| `sdf/*/soc_top__<corner>.sdf`, three | 949,761 lines each | identical after masking `(DATE …)` |
| `metrics.csv` | | **one value rendered differently: `3782350` against `3.78235E+6`** for `route__wirelength__estimated`. The JSON stores the same number both times; the CSV writer formatted it differently. The value is identical, the text is not |

**[fact, `cmp` and the masking comparator of section 14]**

**The `metrics.csv` line is the only place in 23 artefacts where the
same number appears as different text**, and it is recorded so that a
reader who diffs the CSV first does not read a formatting choice as a
result.

### 5.4 No frequency

`docs/53` section 9.2 refused a frequency on three grounds and
`docs/05` section 4 rule 5 binds any published figure to a measurement
or a target. **Nothing here moves any of the three**; this document
reports the same −9.1085 ns of slack against 20 ns that `docs/70` did,
and converts nothing into a clock rate.

---

## 6. What the identity settles

### 6.1 The flow is deterministic on this machine

Two runs, three hours apart, one alone and one concurrent with another
layout, at different loads, produced the same database to the byte
through a 20-thread detailed router with a fixed seed. **That is the
sufficient condition section 3.1 said the fixed seed alone was not**,
measured on the one step where it could fail. Every step upstream of
the router is single-threaded and seedless, and reproduced; every step
downstream is a function of the routed database, and reproduced.

### 6.2 Every delta in the corpus is a delta of netlists

`docs/47` against `docs/48`'s floorplans, `docs/49`'s `SYNPRE`,
`docs/50`'s read register, `docs/61`'s accelerator, `docs/62`'s
re-measurement, `docs/67`'s ECC, `docs/68`'s boot block and `docs/70`'s
hardened one: each of those documents compared two layouts of two
netlists — or, for `docs/48`, two floorplans of one netlist — and each
read the difference as a property of what changed. **That reading
rested on the assumption `docs/70` section 11 named, and the assumption
is now checked.** A flow that gives the same layout for the same input
gives a different layout only for a different input.

So `docs/70` section 6.1's **−4.3009 ns is a regression** and not a
draw; `docs/70` section 6.2's mechanism — the post-GRT resizer
inserting 102 setup repair buffers against the baseline's 519 — is the
flow's deterministic response to `docs/69`'s 414 cells and 51
flip-flops; and `docs/70` section 15 item 2, *find out what the
post-GRT resizer did*, is a question about a reproducible event and is
now worth answering.

### 6.3 The resume form loses nothing

`docs/70`'s `s70boot2` was resumed from `s70boot`'s
`37-openroad-stamidpnr-3/state_out.json` into a fresh directory, after
its first detailed-routing attempt was interrupted. This document's
`s71boot` was never interrupted. **From step 38 to step 62, the resumed
run and the uninterrupted run are identical in every view and every
metric** — the routed ODB, the DEF, the netlists, the SPEF, the
sign-off STA — **[fact, section 5.1]**.

`docs/70` section 5.3 closed with: *"the resume restores the step's own
`state_out.json`, so the comparison should be of netlists, but that is
an argument and not a measurement."* **It is a measurement now.** The
`State` a resume restores carries everything the remaining steps
consume, and `docs/67`'s and `docs/70`'s resumed comparisons were
comparisons of netlists.

### 6.4 And the synthesis side was already known

Whether the front half of the pipeline — `syn_soc_top.sh`'s Yosys and
ABC recipe — reproduces was settled earlier and is only recalled here:
`docs/44` section 5.3a found all eight bisection probes of one
configuration producing a byte-identical netlist, and `docs/70`
section 2 found both of `docs/69`'s netlists byte-identical on
re-synthesis. **Netlist in, layout out, both halves reproduce.**

---

## 7. What "noise floor" now means, and what it does not

Every physical document since `docs/44` has quoted a "noise floor" and
used it as an instrument's resolution: a delta smaller than the floor
is not reported as an effect. **The number is still right to use that
way, and the name is wrong.** A noise floor is the spread an instrument
shows when its input does not change. This instrument, given an
unchanged input, shows a spread of **zero**.

What `docs/44` section 5.2 and `docs/70` section 5.3 measured is
something else: the spread the flow shows when its input changes in a
way that a designer would call no change at all — an unconnected port
removed by `opt_clean`, a combinational refactor worth one cell.
**That is sensitivity, not noise.** It is the property that ABC re-maps
a 45,000-cell design differently when anything about it changes and
that the placer and router then follow the new netlist to a new
layout, deterministically, into a result that differs from the old one
by 0.5031 ns of slack and 12,962 um2 of placed cells. It is chaotic
in the plain sense — small input changes, large output changes — and it
is perfectly repeatable.

Three consequences, each of which changes how a number is read and
none of which changes a verdict:

1. **The floors stand as thresholds for reading a delta between two
   different netlists.** `docs/62`'s −1.0109 ns at 2.0x the post-layout
   figure is still a regression; `docs/67`'s −0.6353 ns at 1.26x is
   still "outside, barely"; `docs/68`'s −0.0297 ns hold delta is still
   withdrawn. Nothing in `docs/70` section 10's table moves.
2. **They do not apply to a re-run.** A document that re-lays-out an
   unchanged netlist and finds it unchanged has not found "a result
   inside the noise"; it has found the flow working. A document that
   re-lays-out an unchanged netlist and finds it **changed** has found
   a tool, a PDK or a machine difference, and should say which — this
   document's section 11 lists the ones it did not vary.
3. **A delta measured against a noise floor of zero is exact, and
   that cuts both ways.** `docs/70`'s −4.3009 ns is exactly what those
   414 cells cost in this flow; it is also exactly what they cost **in
   this flow**, and section 6.2's mechanism — the resizer's iteration
   budget terminating differently — is the reason a different flow
   might charge a different amount for the same cells. Determinism
   makes the number sharp; it does not make it general.

**`docs/44` section 5.2's rule survives with its name changed.** *"A
whole-core setup slack from this flow is not an instrument with better
than about 0.4 ns of resolution"* becomes: a whole-core setup slack
from this flow is an exact measurement of one netlist, and two
netlists that differ at all may differ by 0.4 ns after synthesis and
0.5031 ns after layout for reasons unrelated to what was changed. The
in-place note section 12 adds says so.

---

## 8. The thread count

Section 3.2 reduced the question to one step and one parameter, and
two runs at the same parameter cannot answer whether the parameter
matters. So one bounded experiment was added, and it is labelled as
what it is: **not a third layout, not part of the comparison above,
and the only thing in this document that varies anything.**

`s71boot`'s own `37-openroad-stamidpnr-3/state_out.json` was resumed
under a third tag, `s71drt10`, with `_OPENLANE_MAX_CORES=10` in the
environment — the variable `_get_process_limit()` reads, section 3.2 —
and the flow stopped after `OpenROAD.DetailedRouting`. No file was
changed; the flow log records `Running TritonRoute with 10 threads…`
and the step log `[INFO ORD-0030] Using 10 thread(s).` **[fact]**.

**Identical.** The 10-thread router's `or_metrics_out.json` — 74 keys,
the ten per-iteration DRC counts and the ten wirelengths among them —
matches the 20-thread step's key for key, **0 differ**, and its ODB,
DEF, `nl.v`, `pnl.v`, DRC report and SDC are **byte-identical** to
`s71boot`'s step 38, and therefore to `s70boot2`'s **[fact, `md5sum`]**.
The step took **35 m 42.30 s** on 10 threads against **36 m 19.54 s** on
20 **[fact, `runtime.txt`]**, which says the router was not
compute-bound on this machine at either count and says nothing else.

So at the two points measured — 20 threads and 10 — TritonRoute's
result on this netlist does not depend on how many threads it was
given, with the seed LibreLane pins. That is an observation at two
points; the router's source was not read and no mechanism is claimed.
**A single thread, a different CPU count's default, and a different
machine were not tried**, section 11.

---

## 9. The checkers, re-audited, and an exit status corrected

`hw/openlane/checker_audit.py`, which recomputes from the installed
LibreLane's own step classes and the run's own `resolved.json` whether
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

**[fact, `runs/s71boot`; identical output for `runs/s70boot2`]**

**Seventeen of nineteen, the same seventeen and the same two**, as
`docs/47` 7.3, `docs/48` 9, `docs/49` 10, `docs/50` 9, `docs/61` 10,
`docs/62` 10, `docs/67` 5.3, `docs/68` 9.3 and `docs/70` 8. The four
corner checkers each examined three corners. **And the flow exits
non-zero naming setup at `nom_slow_1p08V_125C`, max slew at all three
corners and max cap at all three — hold in neither list** **[fact,
the flow log]**, as `docs/70` section 8 records for both its runs.

**The exit status.** `checker_audit.py` returns **1** on both
`s70boot2` and `s71boot` **[fact, `$?`]**. That is not a defect and it
is not new: the script's own docstring, line 51, says *"Exit status is
1 if any in-flow checker is PARTIAL or NO-GATE"*, `config-ecc.json`'s
`//gate_preamble` says the same, and with `LintWarnings` and
`WireLength` abstaining by policy the audit has exited 1 on every run
since `docs/47`. **Five documents nevertheless wrote "exit 0"**:
`docs/48` sections 2 and 9, `docs/49` sections 2 and 10, `docs/50`
section 9, `docs/62` section 10, and `docs/70` sections 1, 8, 10 and
14. In every case the 17-of-19 count beside it is correct and was
re-measured; the exit-status phrase is wrong, and each gets a dated
note, section 12. A reader who runs the reproduction recipes and gets
1 should not conclude the audit has changed.

**The derate**, audited where it can be audited: the flow log prints
`[INFO] Setting timing derate to: 5.0%` **[fact]** — `5.0%` and not
`5%`, `docs/28` section 4.4's distinction.

**The router check that did not run**, re-checked rather than
inherited: ten `[WARNING DRT-0349]` lines over seven layer names —
`Cont` 1, `Via1` 2, `Via2` 1, `Via3` 1, `Via4` 1, `TopVia1` 2,
`TopVia2` 2 — **[fact, `grep` over
`38-openroad-detailedrouting/openroad-detailedrouting.log`]**, the same
ten `docs/70` section 7 counted in five earlier runs. So `0
detailed-routing DRC errors` in section 5.2 means, as before, zero
among the rules the router checked.

**The census**, for completeness: `violator_census.py` on `s71boot`
reproduces `docs/70` section 6.3's protected-run table launch point
for launch point, and `u_boot` appears **zero** times in all three
corners' `violator_list.rpt` **[fact]**.

---

## 10. Which prior conclusions survive

| Conclusion | Where | Status after this document |
|---|---|---|
| `docs/70`'s −4.3009 ns setup regression | `docs/70` 6.1 | **Survives, and is now exact**: not a draw, section 6.2 |
| The post-GRT resizer inserted 102 setup buffers against 519 | `docs/70` 6.2 | **Survives**, reproduced to the buffer; the mechanism is deterministic and worth explaining, section 15 |
| `docs/68`'s −0.0297 ns hold delta is withdrawn as a measurement | `docs/70` 5.3 | **Survives, with a sharper reason**: it is inside the flow's netlist sensitivity, not inside its noise |
| The control pair's 0.5031 ns / 0.0198 ns / 12,962 um2 | `docs/70` 5.3 | **Survive as thresholds for reading a delta between two netlists; renamed** from noise floor to netlist sensitivity. They do not apply to a re-run. Section 7 |
| `docs/44`'s 0.4 ns synthesis floor | `docs/44` 5.2 | **Survives with the same renaming**; the synthesis side's determinism was already on record in `docs/44` 5.3a |
| `docs/62`'s −1.0109 ns is a regression; `docs/67`'s −0.6353 ns is outside, barely | `docs/70` 10 | **Unchanged** |
| The resume-from-state form preserves the comparison | `docs/70` 5.3, argued | **Now measured**, section 6.3 |
| Hold closes at three corners; 0 DRC; the die does not grow; DRT-0349 is the PDK's; `raddr_b_i` binds | `docs/70` 10 | **Survive**, reproduced to the bit |
| 17 of 19 in-flow checkers gate | every physical document since `docs/47` | **Survives**; the "exit 0" beside it in five documents is corrected to exit 1, section 9 |
| **Whether the flow is bit-reproducible has never been tested** | `docs/70` 11 and 15 item 1 | **Closed.** |

---

## 11. What this does NOT cover

Stated at length, in the discipline `docs/47` section 9, `docs/62`
section 13, `docs/67` section 11, `docs/68` section 12, `docs/69`
section 11 and `docs/70` section 11 set. Those lists stand unchanged
except where this document names an item.

- **THIS IS NOT A PHYSICAL SIGN-OFF. THERE IS NO DRC RESULT, NO LVS
  RESULT AND NO XOR RESULT, AND NOTHING HERE MAY BE READ AS THOUGH
  THERE WERE.** `RUN_MAGIC_DRC`, `RUN_KLAYOUT_DRC`, `RUN_KLAYOUT_XOR`
  and `RUN_LVS` are all **0** in `config-ecc.json` **[fact]**, for the
  reason `docs/12` sections 7.5 and 8 measured — a **NO-GO on
  RM_IHPSG13 for this PDK version**, Magic DRC 1,106,478 errors,
  KLayout deep-mode DRC 2,316, Netgen LVS 359 — and `docs/54` examined
  in full. Two byte-identical unchecked layouts are two unchecked
  layouts. **A layout that reproduces is not thereby manufacturable,
  and identity is not equivalence to the RTL** — `Yosys.EQY` is off and
  no gate-level simulation of `soc_top` exists.
- **ONE NETLIST.** The protected boot netlist, once. Determinism was
  measured on it and is claimed for this flow on this machine; a
  netlist that happened to sit at a tie in some heuristic could still
  break it, and nothing here says how likely that is.
- **ONE FLOORPLAN, ONE DENSITY, ONE CLOCK, ONE MODE.** `config-ecc.json`
  is `docs/67`'s single point, and `docs/48` is the reason it is fixed:
  both alternatives measured there were worse, and neither was sized
  for the design that now exists.
- **ONE MACHINE, ONE BINARY.** The same 20-CPU host, the same OpenROAD
  build, the same LibreLane wheel, the same PDK checkout. A different
  CPU count changes `DRT_THREADS`'s default, section 3.2; a different
  OpenROAD build changes everything. **Nothing here says a second
  machine reproduces this layout**, and `docs/12`'s tool pins are the
  only thing that makes the claim checkable elsewhere.
- **THE THREAD COUNT WAS VARIED ONCE**, section 8, from 20 to 10, on
  the detailed router only, and stopped after it. It is one point and
  not a sweep.
- **TWO RUNS.** Determinism was shown by one repetition. A flow that is
  deterministic 99 times in 100 would have passed this test with
  probability 0.99, and the number of repetitions it would take to
  bound that is not one.
- **THE SETUP REGRESSION IS STILL LOCALISED, NOT EXPLAINED.** This
  document makes `docs/70` section 6.2's question sharper — the event
  is reproducible — and does not answer it.
- **THE FAST CORNER'S MACRO LIBERTY IS CHARACTERISED AT −55 C** while
  the standard cells are at −40 C, `docs/12` section 6.4a; every hold
  figure here carries that mismatch, identically in both runs.
- **IR DROP IS INDICATIVE ONLY.** `VSRC_LOC_FILES` is unset.
- **NO BEHAVIOURAL EVIDENCE WAS ADDED AND NONE WAS NEEDED.** No RTL
  was modified; `docs/69`'s campaign and invariants are the evidence
  for this design. The Python suite was re-run as a check that the
  **tree** did not move, section 13.
- **NO WALL-CLOCK FIGURE IS A WALL-CLOCK FIGURE**, sections 4.2 and 14.

---

## 12. Corrections to earlier documents

Every one is a dated in-place note in the corrected file, by `docs/64`
section 2's rule; every original sentence stands. Section 13 names the
files.

- **`docs/44` section 5.2's 0.4 ns**, already amended by `docs/70`: a
  second note says the same netlist laid out twice gives a byte-identical
  sign-off report, so the figure — and `docs/70`'s post-layout
  figures — is the flow's sensitivity to a changed netlist and not
  instrument noise; it stands as the threshold for reading a delta
  between two netlists and does not apply to a re-run. Section 7.
- **`docs/70` section 5.3's control pair**: a note says the pair
  measured netlist sensitivity, that its 0.5031 ns / 0.0198 ns /
  12,962 um2 stand under that name, and that its closing sentence —
  the resume form is *"an argument and not a measurement"* — is now a
  measurement, section 6.3.
- **`docs/70` section 11's bit-reproducibility bullet and section 15
  item 1**: **closed**.
- **`docs/70` section 8, and the same phrase in `docs/48` sections 2
  and 9, `docs/49` sections 2 and 10, `docs/50` section 9 and `docs/62`
  section 10**: `checker_audit.py` exits **1** on 17 of 19 by its own
  contract, not 0. The count beside each is correct. Section 9.
- **`docs/00-index.md`**: one row, which `sw/tests/test_doc_links.py`
  requires.

---

## 13. Files touched

| file | change |
|---|---|
| `docs/71-layout-reproducibility.md` | this document |
| `docs/00-index.md` | one row |
| `docs/70-boot-hardening-placed.md` | dated notes: section 5.3 (netlist sensitivity; the resume form measured), section 8 (exit 1), section 11 (bullet closed), section 15 (item 1 closed) |
| `docs/44-margin-and-observability.md` | section 5.2, a second dated note: the floor is sensitivity, not noise |
| `docs/48-floorplan-and-capacitance.md`, `docs/49-synpre-and-the-binding-path.md`, `docs/50-memory-read-register.md`, `docs/62-synpre-remeasured.md` | one dated note each: the audit exits 1 |

**Nothing else in the repository is modified.** No RTL, no flow script,
no test, no configuration. `hw/soc/pnr/runs/s71boot/`,
`hw/soc/pnr/runs/s71drt10/`, `hw/soc/pnr/state/s71*.state.json`,
`hw/soc/out/s71-pnr-*.log` and `hw/soc/pnr/config.resolved.json` are
gitignored build products and are not checked in, `docs/38` section
11's rule; the durable record of the layout is this document, and the
layout itself is `docs/70`'s, byte for byte.

**Nothing in `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is
modified and `hw/tb/Makefile.fi` was not invoked. `docs/34`'s freeze is
untouched.**

The Python suite: **453 passed, 0 failed** **[fact, `.venv/bin/python -m pytest sw/tests -q`]** — `docs/70` section 2 reports 452 with that document present, and `sw/tests/test_doc_links.py` discovers the corpus, so this document adds exactly one test, as `docs/70` did.

---

## 14. Reproducing this

```
# 0. the instruments, before anything is claimed to move
V=$HOME/Documents/caravel-lif-crossbar/.venv-flow/bin/python
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/s70boot2      # -9.1085 / 3361
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/s70boot2      # 17 of 19, exit 1
md5sum hw/soc/out/s70-rom0-syn/soc_top.netlist.v               # a8d5ef81...

# 1. what determines reproducibility, read out of the installed tools
LL=$($V -c "import librelane,os;print(os.path.dirname(librelane.__file__))")
grep -rn "or_seed\|set_thread_count" $LL/scripts/openroad/     # drt.tcl 73, 89 only
grep -rn "DRT_SEED" $LL/                                       # nothing
sed -n 426p $LL/common/misc.py                                 # _OPENLANE_MAX_CORES or cpu_count
grep -rl ORD-0030 hw/soc/pnr/runs/s70boot2/*/*.log             # the DRT log only
echo 'help global_placement; help detailed_route' | \
  ~/.local/opt/llbin/openroad -no_init -no_splash -exit        # no seed; -or_seed -or_k

# 2. the layout, docs/70 section 14 step 2 with the tag changed
SYN_NETLIST=$PWD/hw/soc/out/s70-rom0-syn/soc_top.netlist.v \
PNR_CONFIG=$PWD/hw/soc/pnr/config-ecc.json \
PNR_STATE=$PWD/hw/soc/pnr/state/s71boot.state.json \
hw/soc/flow/pnr_soc_top.sh s71boot --overwrite -F Yosys.JsonHeader \
    -S Yosys.Synthesis -S Checker.YosysUnmappedCells \
    -S Checker.YosysSynthChecks -S Checker.NetlistAssignStatements \
    -i $PWD/hw/soc/pnr/state/s71boot.state.json

# 3. the configuration, asserted
python3 -c "
import json
a=json.load(open('hw/soc/pnr/runs/s70boot/resolved.json'))
b=json.load(open('hw/soc/pnr/runs/s71boot/resolved.json'))
print(sorted(k for k in set(a)|set(b) if a.get(k)!=b.get(k)))"   # []

# 4. the comparison
cmp hw/soc/pnr/runs/s70boot2/final/metrics.json \
    hw/soc/pnr/runs/s71boot/final/metrics.json                 # silent
cmp hw/soc/pnr/runs/s70boot2/final/def/soc_top.def \
    hw/soc/pnr/runs/s71boot/final/def/soc_top.def              # silent
cmp hw/soc/pnr/runs/s70boot2/final/odb/soc_top.odb \
    hw/soc/pnr/runs/s71boot/final/odb/soc_top.odb              # silent
diff hw/soc/pnr/runs/s70boot2/final/spef/nom/soc_top.nom.spef \
     hw/soc/pnr/runs/s71boot/final/spef/nom/soc_top.nom.spef   # the *DATE line
diff hw/soc/pnr/runs/s70boot2/final/mag/soc_top.mag \
     hw/soc/pnr/runs/s71boot/final/mag/soc_top.mag | \
  grep '^[<>]' | grep -vc timestamp                            # 0
# step by step: pair every NN-<step> of s70boot then s70boot2 with the
# same-named step of s71boot; compare or_metrics_out.json key by key
# and the md5 of every .odb .def .nl.v .pnl.v .sdc .spef .drc .lef
# .gds .mag .rpt; skip state_in/state_out/config/extra.json and
# *.process_stats.json, which carry the run directory's name or its
# timings. 58 of 62 identical; rcx, irdropreport, magic-streamout,
# klayout-streamout differ as section 5.1 says.
# GDS: mask BGNLIB (0x01) and BGNSTR (0x05) record bodies, then cmp.

# 5. the reports
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/s71boot       # identical to s70boot2
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/s71boot; echo $?   # 17 of 19, 1
python3 hw/soc/pnr/violator_census.py hw/soc/pnr/runs/s71boot --top 6
grep -c u_boot hw/soc/pnr/runs/s71boot/49-openroad-stapostpnr/*/violator_list.rpt  # 0 0 0
grep -h DRT-0349 hw/soc/pnr/runs/s71boot/38-*/*.log | sed 's/.*layer //' | sort | uniq -c
grep -m1 "timing derate" hw/soc/out/s71-pnr-boot.log          # 5.0%
grep "TritonRoute with" hw/soc/out/s71-pnr-boot.log           # 20 threads

# 6. the thread count, section 8: resume s71boot's own step 37 with
#    fewer threads and stop after the router
_OPENLANE_MAX_CORES=10 \
SYN_NETLIST=$PWD/hw/soc/out/s70-rom0-syn/soc_top.netlist.v \
PNR_CONFIG=$PWD/hw/soc/pnr/config-ecc.json \
PNR_STATE=$PWD/hw/soc/pnr/state/s71drt10.state.json \
hw/soc/flow/pnr_soc_top.sh s71drt10 --overwrite \
    -F OpenROAD.DetailedRouting -T OpenROAD.DetailedRouting \
    -i $PWD/hw/soc/pnr/runs/s71boot/37-openroad-stamidpnr-3/state_out.json

# 7. the guards
.venv/bin/python -m pytest sw/tests/test_doc_links.py -q
.venv/bin/python -m pytest sw/tests -q
```

**The step timers**, which are the only runtimes quoted and which are
not wall-clock:

| | steps 1–37 | steps 38–62 | total, 59 timed steps | detailed routing |
|---|---:|---:|---:|---:|
| `docs/70`, `s70boot` + `s70boot2` | 33 m 53.01 s | 1 h 32 m 26.97 s | 2 h 06 m 19.98 s | 1 h 20 m 23.49 s |
| this document, `s71boot` | 35 m 00.36 s | 49 m 21.70 s | **1 h 24 m 22.05 s** | **36 m 19.54 s** |

**[fact, each step's own `runtime.txt`]**

The two detailed-routing figures are the same computation on the same
input producing the same output — section 5 — and the second took 45 %
of the time the first did, because the first ran concurrently with a
second layout's detailed router on the same 20 CPUs and the second ran
beside one unrelated process. **That is the cleanest illustration this
repository has of why its wall-clock and even its per-step figures
measure the machine's load and not the flow**: the router's own
per-iteration trajectory — ten DRC counts, ten wirelengths — is
identical in both, and its runtime differs by a factor of 2.2. The two
steps-1–37 figures, single-threaded throughout, agree within 3 %.

---

## 15. What the next block should be

1. **Find out what the post-GRT resizer did.** `docs/70` section 15
   item 2, now with the caveat removed that made it uncertain whether
   the event would recur: it recurs exactly. `repair_timing`'s own
   report and its iteration budget are in
   `36-openroad-resizertimingpostgrt/` of `s71boot` and of `s70base`,
   102 setup buffers against 519, and reading them is the difference
   between "reported" and "explained". Because the flow is
   deterministic, any instrumentation of that step — a `-verbose`, a
   `-max_iterations` sweep — measures the mechanism and not a draw.
2. **Say what "noise floor" means everywhere it is quoted.** Section 7
   renames one concept; `docs/61` 9.1, `docs/62` 1, `docs/67` 5.3 and
   `docs/68` 9.2 quote the old name. None of their verdicts changes,
   and none of them needs a note beyond `docs/44`'s and `docs/70`'s,
   but the **v0.2 of `docs/60`** that five documents already owe
   should carry the distinction so that a reader of the datasheet does
   not learn it from this document.
3. **`docs/50`'s read register**, `docs/70` section 15 item 3, unchanged:
   the population behind the macro read return is 1,018 endpoints at
   −6.8564 and the mechanism that splits it has been priced twice on
   designs that no longer exist. It is now known that pricing it a
   third time will give a number that means something.
4. **Close the strap sampling window, or record that it stays open**,
   `docs/69` section 15 item 2, the sharpest thing still open inside
   the placed block.
5. **The report has no reader**, `docs/69` section 15 item 3.
6. **The remaining items of `docs/68` section 16 are unchanged.**
