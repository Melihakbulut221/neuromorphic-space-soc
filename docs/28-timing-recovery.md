# 28 — Where the slow-corner margin went, and what can be bought back

Status: the attribution and every timing measurement are complete, on
five hardens at the 6x2 submission shape. The geometric sign-off decks
(Magic DRC, KLayout DRC, Netgen LVS) were still executing when this was
written and are the one thing outstanding — section 6.3 says exactly
what is and is not established, and section 10 item 7 says how to close
it without a re-run. This document attributes the 0.9118 ns of slow-corner
setup margin that `docs/27` measured and could not explain, and then
reports what each recovery option is worth in nanoseconds, measured
rather than argued.

**The short version.** The margin did not go to any of the three
suspects. The critical path *swapped* cones — the one `docs/23` reported
improved 2.82 ns and a second one degraded 2.13 ns — and 78 % of that
degradation arrived during place-and-route, on a cone the RTL edit never
touched (§3). The dual-rail flags are 3.87 ns off the critical path and
removing one would buy nothing (§4.1). Turning on the two
post-global-routing repair steps recovers **+1.3548 ns for +0.10 % of
area** — more than the whole wave-6 loss (§5.2, §5.4). Timing-driven
placement, measured **separately and not composed with it**, is worth
**+0.5856 ns while making the design 1.2 % smaller and its wiring 8 %
shorter** (§5.5); composing the two is the largest thing left untested
(§6.2). Mapping for delay instead
of area — the obvious way to spend the 32.5 % of spare core — **loses
4.36 ns** (§5.3). And the flow has been signing off with **no OCV derate
at all** while logging that it applies 5 %, which means the `docs/27`
baseline did not actually close at 50 MHz and the adopted configuration
does, with 3.8 % of the cycle to spare (§4.4b, §7).

It closes `docs/27` section 10 item 2: "the slow-corner margin loss is
measured but not attributed … which path, and whether the cause is the
rails, the timeout retirement, or placement noise."

Convention, inherited from `docs/18`, `docs/22` and `docs/27`:
**[fact]** = measured in this environment or read out of an installed
file; **[estimate]** = derived or judged.

Run trees under `hw/openlane/*/runs/` and `tt/runs/` are **gitignored**,
so every number is quoted with the run tag and the step directory it
came from.

**No document other than this one is edited.** Corrections that other
documents need are listed at the end.

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

No mismatch warning **[fact]**. Identical to `docs/27` section 1.1:

| Component | Version | Where it is pinned |
|---|---|---|
| LibreLane | 3.0.5 | `~/Documents/caravel-lif-crossbar/.venv-flow` |
| Yosys (in-flow) | 0.67, git sha1 `2d1509d1b` | LibreLane wheel (`pyosys`) |
| Yosys (guards, `tools.mk`) | 0.67+146 | `OSS_CAD_SUITE` pin |
| ihp-sg13g2 PDK | `c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c` | LibreLane `pdk_hashes.yaml`, asserted by `run_ihp.sh` |
| Magic | 8.3.678 | `~/.local/opt/magic-8.3.678` |
| OpenSTA (section 4.3 probes) | the `~/.local/opt/llbin/sta` shim | same OpenROAD build the flow uses |

**[fact]** for every row, read out of
`hw/openlane/pilot_ihp/runs/tr-control/resolved.json` and
`librelane --version`.

### 1.2 Sources: the blob list, pinned — and it mattered again

Every run here is pinned with `hw/openlane/pin_rtl.py` against commit
**`c52518e`** (HEAD when this work started, tree clean) and reads a
disposable snapshot by absolute path, not `hw/rtl`:

```
$ python3 hw/openlane/pin_rtl.py c52518e \
      hw/openlane/pilot_ihp/config.tr-control.json <scratch>/pins/tr-control
pinned to c52518e (c52518ea00f7)
  70045ec25774955775fe830aab2f4c3c1271b926  hw/rtl/aer_fifo.v
  72f4f0af662b7bb07fdf43bf244e622d03db5e0d  hw/rtl/lif_core.v
  e6c1e646643840e2a553924b56dfab64022e5c39  hw/rtl/npu_regbank.v
  9aaaa394e7a6ef855f5584fb85d53e688ac3e0b5  hw/rtl/npu_regs.vh
  3d9f84047748b523318011f1759f534b664ff4a9  hw/rtl/pilot_top.v
  89e62789ad016c7cb51ad69247f6066335074f8c  hw/rtl/scrub.v
  f7c7ec187a0df4eb09a8405dcda285de0fc2e44e  hw/rtl/secded_dec.v
  b5710b8a679c3e378e74953b621b99f0d8dc3014  hw/rtl/secded_enc.v
  62b5f4d2a1eae095d9d4a8634ede55237e2c924d  hw/rtl/tmr_voter.v
  e294afcf03e1947906086beeba2fd0c40b29441d  hw/rtl/tt_um_melihakbulut_nssoc.v
```

**[fact]**, and the same ten blobs for all six variants.

**`c52518e` carries byte-identical RTL to `2c6c052`**, the commit
`docs/27` hardened — all ten blobs match, and the only changes between
the two commits are `docs/27`, `docs/00-index.md` and
`sw/tests/test_synthesis_guards.py` **[fact,
`git rev-parse <commit>:hw/rtl/<file>` on each, `git diff --stat`]**.
So `tt/runs/wave6-6x2` is a legitimate baseline for these runs: same
sources, same shape, same flow, and section 5 confirms it reproduces.

**The RTL moved under the tree again while these runs executed, for the
third time in this project's record** (`docs/20` section 1.2, `docs/22`
section 9). A concurrent session modified `hw/rtl/aer_fifo.v`,
`hw/tb/test_aer_fifo.py` and `formal/aer_fifo_props.v` at about 16:39.
**No run here can have read it**: the live tree's `aer_fifo.v` is now
blob `bf6829c75254`, and every pinned snapshot the runs actually compile
still carries `70045ec25774`, the `c52518e` blob **[fact,
`git hash-object` on the live file and on all six snapshots]**. The
configs name the snapshot by absolute path, not `hw/rtl`. This is the
third time the pinning has earned itself.

### 1.3 The runs

All at the 6x2 submission shape, `CLOCK_PERIOD: 20`,
`SYNTH_HIERARCHY_MODE: deferred_flatten`, `DIE_AREA 0 0 1289.28
313.74`. Variants are derived mechanically from `config.6x2.json` by
**`hw/openlane/pilot_ihp/mktiming.py`**, which is new in this workstream
and follows `mkconfig.py`'s discipline — `--check` re-derives and diffs,
so a drifted config is an error rather than a surprise.

| Tag | Keys changed against `config.6x2.json` | Run? |
|---|---|---|
| `tr-control` | `SETUP_VIOLATION_CORNERS: ["*"]` only (section 4.4) | **yes** |
| `tr-delay0` | + `SYNTH_STRATEGY: "DELAY 0"` | **yes** |
| `tr-postgrt` | + `PNR_CORNERS`, `RUN_POST_GRT_DESIGN_REPAIR`, `RUN_POST_GRT_RESIZER_TIMING` | **yes — adopted** |
| `tr-margin` | `tr-postgrt` + `GRT_RESIZER_SETUP_SLACK_MARGIN: 0.5` | **yes** |
| `tr-tdp` | + `PL_TIMING_DRIVEN: 1`, `PNR_CORNERS` | **yes** |
| `tr-delay2` | + `SYNTH_STRATEGY: "DELAY 2"` | no — §5.3 |
| `tr-best` | + `SYNTH_STRATEGY: "DELAY 0"`, `PNR_CORNERS`, both post-GRT steps | no — §5.3 |

The last two are generated and documented but deliberately not run;
`mktiming.py` records the reason at each, and section 5.3 is the
measurement that made them pointless.

`SETUP_VIOLATION_CORNERS: ["*"]` is in **every** variant including the
control. It is not a timing experiment; it is a sign-off hole, and
section 4.4 is why.

Exact commands:

```bash
make -f tools.mk toolcheck
python3 hw/openlane/pilot_ihp/mktiming.py            # write the variants
python3 hw/openlane/pilot_ihp/mktiming.py --check    # confirm no drift

python3 hw/openlane/pin_rtl.py c52518e \
    hw/openlane/pilot_ihp/config.<tag>.json <scratch>/pins/<tag>

mkdir -p hw/openlane/pilot_ihp/runs/<tag>
CONFIG=<scratch>/pins/<tag>/config.json \
  hw/openlane/pilot_ihp/run_ihp.sh \
    --run-tag <tag> --force-run-dir $PWD/hw/openlane/pilot_ihp/runs/<tag>
```

`hw/openlane/pilot_ihp/runs/` is a legitimate destination now:
`c52518e` added it to `sw/tests/test_synthesis_guards.py`'s `RUN_TREES`,
which is what `docs/27` section 1.4 had to route around by writing into
`tt/runs/` **[fact, `RUN_TREES` at line 915]**.

---

## 2. The measurement being explained

`docs/27` section 3, restated. 20 ns clock, post-PnR STA on extracted
parasitics, `nom_slow_1p08V_125C`:

| | `shape-6x2` (`docs/23`) | `wave6-6x2` (`docs/27`) | Move |
|---|---|---|---|
| **Setup WNS, slow** | **+1.2347** | **+0.3229** | **-0.9118** |
| Setup violations | 0 | 0 | — |
| Slow-corner Fmax | 53.29 MHz | 50.82 MHz | -2.47 MHz |

**[fact]**. Every violation counter is zero in both runs. What follows
is an attribution of the 0.9118 ns, not a bug hunt.

---

## 3. Where the margin went

### 3.1 It is not one path getting slower. It is a different path

Both runs' setup reports were parsed whole — 1,651 paths in `shape-6x2`
and 1,653 in `wave6-6x2` — and every path grouped by the net its
startpoint flip-flop drives. That turns a single WNS number into a
population **[fact,
`55-openroad-stapostpnr/nom_slow_1p08V_125C/max.rpt` of each run]**.

Worst slack per startpoint cone, slow corner:

| Startpoint cone | `shape-6x2` | `wave6-6x2` | Move |
|---|---|---|---|
| `u_pilot.u_lif.jj[1]` — neuron scan index | **+1.2347** (critical) | +4.0554 | **+2.8207** |
| `u_pilot.u_lif.ev_axon_r[1]` — latched axon id | +2.4547 | **+0.3229** (critical) | **-2.1318** |
| `u_pilot.ecc_data[59]` | +9.2261 | +9.2697 | +0.0436 |
| `u_pilot.u_lif.state[1]` | +11.4722 | +8.4395 | -3.0327 |
| `rst_n_sync` | +12.1008 | +12.5634 | +0.4626 |

**[fact]**. **The critical path is a different path in the two runs.**
The cone that set the WNS in `docs/23` — `jj`, the neuron scan index —
*improved by 2.82 ns* and is no longer critical. The cone that sets it
now, `ev_axon_r`, was second worst before and lost 2.13 ns.

So the headline -0.9118 ns is the arithmetic of a swap:
`+0.3229 (ev_axon_r, now) - (+1.2347) (jj, then)`. Reading it as "the
critical path got 0.91 ns slower" is wrong, and it is why no
cell-count or area row in `docs/27` section 2.1 predicts it.

### 3.2 What the critical path is

Both cones are the same architectural loop, and it is worth naming
because it is the thing that will constrain every future wave. From
`hw/rtl/lif_core.v`:

```
ev_axon_r (or jj)
  -> w_rd_index = ev_axon_r * N_NEURONS + jj        line 584
  -> weight flip-flop file read mux                 (sg13g2_mux4_1 select)
  -> secded_dec u_w_rd_dec                          line 630, syndrome + ded
  -> w_code = w_rd_ded ? 4'd0 : w_rd_fixed[...]     (E10) poison-word
  -> w_sext, contrib = w_sext <<< cfg_syn_shift     (E1)(E2)
  -> v_sat: 18-bit signed add and clamp             (E3)
  -> spike compare, st_v / st_r select              (E4)(E5)(E6)
  -> lif_state_enc u_st_enc                         line 913
  -> vmem / rmem / smem write
```

**One neuron update per cycle, with a SECDED decode and a SECDED encode
in series inside it.** The measured path holds 113 cells in `shape-6x2`
and 123 in `wave6-6x2` between launch and capture **[fact]**. This is
the design's fundamental single-cycle loop, and both hardening waves'
critical paths are inside it.

### 3.3 Attribution: 22 % RTL, 78 % place-and-route

The `ev_axon_r` cone can be read at two points in the same flow with
the same tool and the same corner: `12-openroad-staprepnr`, which is STA
on the synthesised netlist before any placement, and
`55-openroad-stapostpnr`, the sign-off.

| Point | `shape-6x2` | `wave6-6x2` | Move |
|---|---|---|---|
| Synthesised netlist (step 12) | +4.942 | +4.465 | **-0.477** |
| Sign-off, extracted (step 55) | +2.4547 | +0.3229 | **-2.1318** |
| **Introduced by place-and-route** | | | **-1.655** |

**[fact]** for the four slacks; the split is arithmetic. **The RTL wave
is worth 0.477 ns of the 2.132 ns the cone lost — 22 %. The remaining
1.655 ns, 78 %, is introduced between the synthesised netlist and the
routed one [estimate, in that it attributes a difference to a stage
rather than to a named cause].**

Segment by segment on the cone, from the two sign-off reports:

| Segment | `shape-6x2` | `wave6-6x2` | Move |
|---|---|---|---|
| launch clk -> Q | 0.289 | 0.412 | +0.123 |
| Q -> weight-file read mux (fanout repair buffers) | 1.368 | 1.777 | **+0.409** |
| read mux -> SECDED decoder `ded` | 5.237 | 4.852 | -0.385 |
| decoder -> state encoder (the LIF arithmetic) | 8.146 | 8.840 | **+0.694** |

**[fact]**. The loss is spread across the whole cone rather than
concentrated at a gate, which is the signature of a placement
difference, not of an RTL edit.

### 3.4 Why place-and-route was free to do this

Four settings, all measured out of the run's own `resolved.json`
**[fact]**:

- **`PL_TIMING_DRIVEN: False`.** `gpl.tcl` gates `-timing_driven` on
  it, so global placement optimises wirelength and density and cannot
  act on a slack number at all. `docs/20` section 5.3(b) established
  this and it is unchanged.
- **`SYNTH_STRATEGY: "AREA 0"`, `SYNTH_SIZING: False`,
  `SYNTH_ABC_BUFFERING: False`.** Technology mapping optimises area.
- **`RUN_POST_GRT_DESIGN_REPAIR: False`,
  `RUN_POST_GRT_RESIZER_TIMING: False`.** There is no timing repair
  after global routing.
- **The post-CTS resizer does no setup work.** Section 4.1.

The consequence is visible in the netlist. On the `wave6-6x2` critical
path, of the 60 driving cells between launch and capture, **56 are
minimum drive strength and 4 are not**; 15 of them are `sg13g2_buf_1`
repair buffers contributing **4.789 ns, 23.9 % of the path** **[fact,
counted from `max.rpt`]**. On `shape-6x2` the same figures are 51 of 55
and 4.100 ns, 20.5 %.

**Nothing in this flow has ever sized a cell on the critical path.**
That is the headroom, and it is why the design's 32.53 % of spare core
area and its 1.61 % of spare cycle are not independent quantities.

---

## 4. What the margin loss is *not*

The commissioning task named three candidates. All three were tested and
**none of them is on the critical path**.

### 4.1 The dual-rail valid flags: worth 0 ns

`docs/27` section 1.3 change 2, 3 and 4 added eight rail flip-flops in
three `keep_hierarchy` modules, and `out_pend` became `op_a && op_b` —
a comparison in front of a signal that gates `can_go`, `w_rd_used` and
`st_rd_used` in `lif_core`. The hypothesis was that this put a rail
comparison into a path it was not in before.

Measured, on the shipped `wave6-6x2` netlist:

| Rail instance | Worst path through it, slow corner | Rank among 1,653 paths |
|---|---|---|
| `u_op_a` / `u_op_b` (`lif_core` `out_pend`) | **+4.1936 / +4.1950** | 175 / 176 |
| `u_ohv_b` (`pilot_top` `oh_valid`) | +13.3669 | 935 |
| `u_rdv_a` / `u_rdv_b` (`aer_fifo` `rd_valid`) | +14.3505 / +14.3524 | 1010 / 1015 |
| `u_ohv_a` | +14.3514 | 1012 |

**[fact]**. The nearest rail is **3.87 ns behind the critical path**.

Stronger still: the critical path enters the LIF arithmetic at
`sg13g2_a221oi_1 \u_pilot.u_lif._3331_`, whose `C1` pin is
`u_w_rd_dec.ded`. A backward reachability trace over the flattened
netlist from that gate's four side inputs — `_0925_`, `_0927_`,
`_0929_`, `_0933_` — **does not reach either `out_pend` rail within 14
levels of logic** **[fact, fan-in trace over
`final/nl/tt_um_melihakbulut_nssoc.nl.v`]**.

**Removing a rail would buy nothing.** That is a measured result, and it
is the answer to the restructuring question in section 6.3: there is
nothing to restructure, because the rails are not there.

### 4.2 The timeout-pulse retirement: not on the path

`docs/27` section 1.3 change 1 replaced `fetch_timeout` and `oh_timeout`
— two one-cycle pulse registers — with combinational expiry terms. Both
live in `hw/rtl/pilot_top.v`.

**The critical path is entirely inside `u_pilot.u_lif`**, from
`u_pilot.u_lif._5478_` to `u_pilot.u_lif._5551_`. Of its 123 cells,
**93 carry a `u_pilot.u_lif.` prefix and the other 30 are flat-named
`fanoutNNN` repair buffers and clock-tree buffers** that OpenROAD
inserted, which belong to no RTL module at all **[fact, counted from
`max.rpt`]**. No cell on it comes from `pilot_top`'s logic, so the
retirement cannot be on it. What it did do is remove combinational logic
design-wide — part of the -135 synthesis cells `docs/27` section 2.1
records — which changed the placement, and section 3.3 shows the
placement is where 78 % of the loss arrived.

### 4.3 `keep_hierarchy` resisting optimisation: real, but not here

The three rail modules do carry `keep_hierarchy` and `flatten` does skip
them, exactly as `docs/27` section 2.3(a) reasons. But the rails are 3.87
ns off the critical path (section 4.1), so whatever optimisation they
resist is not optimisation the critical path needed.

### 4.4 What *is* wrong, and it is a sign-off hole rather than a delay

Two findings came out of reading the flow rather than the netlist. Both
matter more than any nanosecond in this document, and `docs/23` section
3.2 is the precedent for reporting them: it records a hold violation
that `design__violations` did not aggregate, and names the trap — "a
reader taking `design__violations: 0` as *no violations* would miss
this."

**(a) `Checker.SetupViolations` has only ever checked the typical
corner.** LibreLane resolves a timing checker's corners as
`<TYPE>_VIOLATION_CORNERS or TIMING_VIOLATION_CORNERS`
(`librelane/steps/checker.py`, `get_corner_wildcards`). In every run in
this repository `SETUP_VIOLATION_CORNERS` is unset and the IHP PDK ships
`TIMING_VIOLATION_CORNERS: ["*typ*"]`, so the setup checker matches the
typical corner and nothing else. `HOLD_VIOLATION_CORNERS` is already
`["*"]` **[fact, `70-checker-setupviolations/config.json` and
`71-checker-holdviolations/config.json` of `tt/runs/wave6-6x2`]**.

**The slow corner this entire document is about is gated by no checker.**
Had it gone negative, `design__violations` would still have read 0 and
the run would still have reported `flow__errors__count: 0`. This is the
mirror image of the `docs/23` hold finding, and it is the reason every
run in section 1.3 carries `SETUP_VIOLATION_CORNERS: ["*"]`.

**(b) The 5 % timing derate the configuration asks for is not being
applied.** `librelane/scripts/base.sdc` computes it as

```tcl
puts "\[INFO] Setting timing derate to: $::env(TIME_DERATING_CONSTRAINT)%"
set_timing_derate -early [expr 1-[expr $::env(TIME_DERATING_CONSTRAINT) / 100]]
set_timing_derate -late  [expr 1+[expr $::env(TIME_DERATING_CONSTRAINT) / 100]]
```

`TIME_DERATING_CONSTRAINT` resolves to the **integer** `5`, and Tcl's
`expr 5 / 100` is **integer division**, which is `0`. The derate factors
are therefore `1.0` and `1.0` — no derating at all — while the log line
prints "Setting timing derate to: 5%" on every STA and every resizer
step in every run in this repository **[fact,
`resolved.json` type is `int`; `expr 1+[expr 5 / 100]` evaluated in the
flow's own Tcl prints `1`]**.

This was confirmed independently by re-running the sign-off corner
standalone on the shipped artifacts — same netlist, same SPEF, same
SDC, same liberty:

| Configuration | Slow-corner worst setup slack |
|---|---|
| **As signed off** (uncertainty 0.25, derate as the flow applies it) | **+0.32288661547280123** |
| Uncertainty removed, no derate | +0.5728857550499329 |
| **5 % derate actually applied**, uncertainty 0.25 | **-0.6681198006172618** |
| 5 % derate applied, no uncertainty | -0.4181206610401302 |

**[fact, OpenSTA on `tt/runs/wave6-6x2/final/{nl,spef,sdc}` with the
`slow_1p08V_125C` liberty]**. The first row reproduces the run's own
`timing__setup__ws__corner:nom_slow_1p08V_125C` **to all 17 significant
digits**, which is what proves the sign-off carries no derate.

So the two constraint terms are worth, measured:

- **clock uncertainty: 0.2500 ns exactly** (0.5729 - 0.3229).
- **5 % OCV derate: 0.9910 ns** (0.3229 - (-0.6681)).

Section 7 takes the consequence for the 50 MHz target. Neither is
touched to buy margin — reducing either would be exactly the
"relax a constraint below what the flow can honestly sign off" that is
off the table.

---

## 5. What each recovery option is worth

### 5.0 First, the noise floor: it is exactly zero

`tr-control` differs from the `docs/27` baseline by one key, and that
key is a checker. It reproduces the baseline **bit for bit**:

| Corner | `wave6-6x2` | `tr-control` |
|---|---|---|
| `nom_slow_1p08V_125C` setup | 0.32288661547280123 | **0.32288661547280123** |
| `nom_typ_1p20V_25C` setup | 7.5627604097566845 | **7.5627604097566845** |
| `nom_fast_1p32V_m40C` setup | 11.858797834931813 | **11.858797834931813** |

**[fact, all 17 significant digits]**. Synthesis is identical too —
9,686 cells, 152,099.79 um2, 1,277 flip-flops — and the pre-PnR STA
agrees to the last digit **[fact]**.

This matters twice. It confirms `docs/20` section 5.6's determinism
claim still holds for this RTL and this shape, so **every delta below is
attributable to the key that was changed and not to scatter** — and it
means the -0.9118 ns of section 2 is entirely a consequence of the
wave-6 RTL, with no run-to-run component at all. It also shows the
`SETUP_VIOLATION_CORNERS` fix of section 4.4 costs nothing: not one
layout bit moves.

### 5.1 The post-CTS resizer is not the sky130 failure. It is a different one

`docs/25` section 8 found the sky130 post-CTS resizer entering at
-13.545 ns, leaving at -4.672 ns, and raising `RSZ-0062`. The
commissioning question was whether the same resizer is leaving
repairable paths alone on IHP. **It is not, and the reason is worth
stating precisely, because it changes which fix applies.**

| | sky130 (`sky-11-6x2`) | IHP (`wave6-6x2`) |
|---|---|---|
| Post-CTS resizer, setup | `RSZ-0094` **220 endpoints**, 195 buffers, then **`RSZ-0062` Unable to repair all setup violations** | **`RSZ-0098` No setup violations found** |
| Corners it loaded | all nine | **all three, including `nom_slow_1p08V_125C`** |
| Setup buffers in the final netlist | 195 | **0** |

**[fact, `37-openroad-resizertimingpostcts/*.log` of each run, and
`design__instance__count__setup_buffer`]**.

The IHP resizer is **not** giving up. It loads the slow corner
explicitly — `ResizerStep` passes `RSZ_CORNERS or STA_CORNERS` and
`STA_CORNERS` is all three, and the log shows it reading the
`slow_1p08V_125C` liberty **[fact,
`librelane/steps/openroad.py:2393`, and the resizer's own log]** — and
at the point it runs, on post-CTS parasitics, it honestly sees no setup
violation.

**The violations do not exist yet when the only setup-repair step in the
flow runs.** They appear when global routing gives the estimate real
topology. And `RUN_POST_GRT_RESIZER_TIMING` is `False`, so nothing looks
again. That is the actual gap, and it is a different gap from sky130's.

The whole chain is visible in one run once `PNR_CORNERS` makes the
mid-PnR reports name the slow corner — which `docs/20` section 7 called
"genuinely useful observability" and is the only thing that setting
does. Slow-corner setup slack, `tr-postgrt`:

| Point in the flow | Parasitics | Slow-corner setup |
|---|---|---|
| `12-openroad-staprepnr` | wireload estimate, no placement | -5.5195 |
| `36-openroad-stamidpnr-1` | post-CTS estimate | **+3.3256** |
| `44-…-resizertimingpostgrt`, entering | post-GRT estimate | **-0.9560** |
| `44-…-resizertimingpostgrt`, leaving | post-GRT estimate | +0.1700 |
| `45-openroad-stamidpnr-3` | post-GRT estimate | -0.1073 |
| `57-openroad-stapostpnr` | **extracted (RCX)** | **+1.1778** |

**[fact]**. Two things fall out, and both are load-bearing:

**The post-CTS estimate is 4.28 ns optimistic against the post-GRT one.**
That is the entire explanation for `RSZ-0098`. The only setup-repair
step in the default flow is asked to work at the one point where the
design looks 3.3 ns clear. It is not leaving repairable paths alone; it
is being asked before the paths become repairable.

**On IHP the post-GRT estimate is *pessimistic* against extraction by
1.29 ns** — the opposite sign to sky130, where `docs/25` section 7.2
measures the pre-route estimate as 2.2 ns *optimistic*. So the IHP flow
does its repair against a conservative picture and then gains margin at
extraction, which is the safe direction to be wrong in, and it is why
the repair does not overshoot into hold problems (section 5.2).

The step-36 figure is identical to 17 digits in `tr-postgrt` and
`tr-margin`, which differ only in a post-GRT knob — a consistency check
on the determinism of section 5.0 **[fact, +3.3256403017186584 in
both]**.

### 5.2 Post-global-routing repair: +0.8549 ns, for 147 um2

`tr-postgrt` turns on the two post-GRT steps that `docs/18` section 3.3b
named and that have been skipped in every run in this repository.

The step that was missing does exactly the work section 3.4 predicted
was absent:

```
[INFO RSZ-0094] Found 18 endpoints with setup violations.
   Iter | Removed | Resized | Inserted | Cloned |  Pin  |  Area  |   WNS   | Viol | Worst
      0*|       0 |       0 |        0 |      0 |     0 |  +0.0% |  -0.956 |   18 | u_pilot.u_lif._5527_/D
     14*|       0 |       9 |        2 |      0 |     2 |  +0.1% |  +0.170 |   18 | u_pilot.u_lif._5527_/D
```

**[fact, `44-openroad-resizertimingpostgrt/*.log`]**. Nine gates resized,
two buffers, two pin swaps, +0.1 % area — and the endpoint it worked on,
`u_pilot.u_lif._5527_`, is in the `ev_axon_r` cone of section 3.1
(baseline slack +0.4154, rank 4 of 1,653) **[fact]**.

Sign-off result:

| Corner | `wave6-6x2` | **`tr-postgrt`** | Move |
|---|---|---|---|
| `nom_slow_1p08V_125C` **setup** | **+0.3229** | **+1.1778** | **+0.8549** |
| `nom_typ_1p20V_25C` setup | +7.5628 | +8.1262 | +0.5634 |
| `nom_fast_1p32V_m40C` setup | +11.8588 | +12.1662 | +0.3074 |
| `nom_slow` **hold** | +0.6163 | **+0.6266** | **+0.0103** |
| `nom_typ` hold | +0.2936 | **+0.2983** | +0.0047 |
| `nom_fast` hold | +0.1137 | **+0.1157** | +0.0020 |

**[fact, `57-openroad-stapostpnr/<corner>/ws.{max,min}.rpt`]**.
**Hold improves on all three corners**, which is the thing to check when
setup repair adds cells: it did not buy setup by spending hold.

Cost:

| | `wave6-6x2` | `tr-postgrt` | Move |
|---|---|---|---|
| Cells excl. fill | 12,234 | 12,241 | **+7** |
| Placed cell area, um2 | 185,595 | 185,742 | **+147, +0.08 %** |
| Utilization | 47.2266 % | 47.2640 % | +0.037 pts |
| Routed wirelength, um | 465,701 | 465,793 | +92, +0.02 % |
| Route DRC | 0 | **0** | — |

**[fact]**. **0.8549 ns for 147 um2**, against 127,852 um2 of spare core.
The critical cone is still `ev_axon_r`, now at +1.1778, with the next
cone (`jj[2]`) at +3.1964 — the population has separated **[fact]**.

The redundancy survives the resizer, which is not automatic:
`RSZ_DONT_TOUCH_RX` is `$^` and matches nothing, so the resizer was free
to touch rail cells. Counted on the repaired netlist: **1,277 flip-flops,
36 pointer-TMR replicas, 55/55/55 configuration TMR, and all eight rail
banks at their expected counts** **[fact]**. The resizer resized
combinational gates only.

### 5.3 Mapping for delay instead of area: **-4.3585 ns**. It is not a trade

This is the option the framing of the commissioning task points at —
area has 32.53 % spare, timing has 1.61 %, so spend the abundant
resource on the scarce one. **Measured, it goes the wrong way, and by a
large margin.**

At the synthesised netlist it looks like it should work:

| | `tr-control` (`AREA 0`) | `tr-delay0` (`DELAY 0`) |
|---|---|---|
| Synthesis cells | 9,686 | 12,882, **+33.0 %** |
| Synthesis cell area, um2 | 152,099.79 | 185,393.35, **+21.9 %** |
| Flip-flops | 1,277 | **1,277** |
| Logic levels on the `ev_axon_r` cone | 36 | **33** |
| **`ev_axon_r` cone, pre-PnR slack** | +4.465 | **+5.026, +0.561** |

**[fact]**. Three logic levels and **+0.561 ns before placement**, with
the redundancy exactly preserved — 1,277 flip-flops, 36 pointer
replicas, 55/55/55, all eight rails **[fact, counted on
`06-yosys-synthesis/…nl.v`]**.

At sign-off it is a rout:

| | `wave6-6x2` | **`tr-delay0`** | Move |
|---|---|---|---|
| **`nom_slow` setup** | **+0.3229** | **-4.0356** | **-4.3585** |
| `nom_typ` setup | +7.5628 | +4.8874 | -2.6754 |
| `nom_fast` setup | +11.8588 | +10.1451 | -1.7137 |
| `nom_slow` hold | +0.6163 | +0.6215 | +0.0052 |
| Placed cells, excl. fill | 12,234 | 15,929 | **+30.2 %** |
| Placed cell area, um2 | 185,595 | 221,903 | **+19.6 %** |
| Utilization | 47.2266 % | 56.4656 % | +9.24 pts |
| **Routed wirelength, um** | **465,701** | **674,343** | **+44.8 %** |

**[fact]**. **The design fails the slow corner.**

**Why, and it is the most transferable finding in this document.**
Routed wirelength grew **44.8 %** for a 19.6 % area growth. This is a
flip-flop-file design — `wmem`, `vmem`, `rmem` and `smem` are register
arrays, and the critical path's first act is to drive a read mux across
the whole file. Its delay is dominated by the length of those nets, not
by the count of gates on them. Making the design 30 % bigger lengthens
every net in the array, and the wire delay that adds is an order of
magnitude more than the three logic levels the mapping removed.

**Area and timing are not fungible in this design.** The 32.53 % of
spare core is real, and it is spare, but there is no exchange rate that
converts it into setup margin by making the netlist bigger. That
disposes of the whole family of "spend the spare area" options, and it
is exactly why section 5.2 works: the post-GRT resizer bought 0.8549 ns
by growing the design **0.08 %**, not by growing it at all.

`tr-delay2` was therefore not run, and `tr-best` — `DELAY 0` composed
with the post-GRT repair — was dropped before it started: composing a
lever worth -4.36 ns with one worth +0.85 ns has a predictable answer,
and the machine time went to section 5.4 instead. Both are kept in
`mktiming.py` with the reason recorded.

### 5.4 How much more can targeted sizing give? Another 0.408 ns, same price

`tr-postgrt` left `GRT_RESIZER_SETUP_SLACK_MARGIN` at its 0.025 ns
default. The resizer stopped at +0.170 ns on its own estimate having
resized nine gates — it stopped because it had **met the margin it was
asked for**, not because it ran out of moves. `tr-margin` asks for
0.5 ns.

| | `tr-postgrt` (margin 0.025) | **`tr-margin`** (margin 0.5) |
|---|---|---|
| Endpoints it worked on | 18 of 18 | **39 of 39** |
| Resizer entering, slow | -0.956 | -0.956 |
| **Resizer leaving, slow** | **+0.170** | **+0.578** |
| Gates resized | 9 | **11** |
| Buffers inserted | 2 | **7** |
| Pin swaps | 2 | **6** |
| Area growth reported by the resizer | +0.1 % | **+0.1 %** |
| Post-GRT STA after repair | -0.1073 | **+0.4700** |

**[fact, `44-openroad-resizertimingpostgrt/*.log` and
`45-openroad-stamidpnr-3/ws.max.rpt` of each]**. **+0.408 ns more on the
resizer's own estimate, +0.577 ns more at the post-GRT STA, for the same
reported +0.1 % of area.** It plateaued at +0.578 from iteration 24
onward and stopped improving, so that is close to the limit of what
`SizeUpMove`, `BufferMove` and `SwapPinsMove` can reach on this netlist
at this placement — which is a useful bound for section 8.

**It survives extraction.** Sign-off, slow corner:

| | `wave6-6x2` | `tr-postgrt` | **`tr-margin`** |
|---|---|---|---|
| **Setup** | +0.3229 | +1.1778 | **+1.6776** |
| Hold | +0.6163 | +0.6266 | **+0.6175** |
| Placed cell area, um2 | 185,595 | 185,742 | **185,785** |
| Area cost against baseline | — | +147, +0.079 % | **+190, +0.102 %** |
| Routed wirelength, um | 465,701 | 465,793 | **466,001, +0.06 %** |
| Route DRC | 0 | 0 | **0** |

**[fact]**. **+1.3548 ns against the baseline for +190 um2 — 0.102 % of
the placed area, against 127,852 um2 of spare core.** That is more than
the entire 0.9118 ns that wave 6 lost, and it is more margin than
`shape-6x2` had before the wave (+1.2347).

Sign-off result in section 6.

### 5.5 Timing-driven placement: +0.073 ns

`docs/20` section 5.3(b) established that `PNR_CORNERS` cannot reach
placement while `PL_TIMING_DRIVEN` is `False`, because `gpl.tcl` gates
`-timing_driven` on it. `tr-tdp` turns it on, and the logged command
confirms it: `global_placement -density 0.6 -timing_driven
-routability_driven …` against the baseline's identical line without the
flag **[fact]**.

| Point | baseline / `tr-postgrt` | **`tr-tdp`** | Move |
|---|---|---|---|
| Post-CTS estimate, slow | +3.3256 | **+3.2965** | **-0.0291** |
| Post-GRT estimate before any repair, slow | -0.9560 | **-0.8832** | **+0.0728** |

**[fact]**. At the estimate stages it looks worth almost nothing —
+0.073 ns at post-GRT and very slightly *negative* at post-CTS.

**At sign-off it is worth eight times that, and it is free in every
other dimension:**

| | `wave6-6x2` | **`tr-tdp`** | Move |
|---|---|---|---|
| **Setup, slow** | +0.3229 | **+0.9085** | **+0.5856** |
| Setup, typ | +7.5628 | +7.8297 | +0.2669 |
| Setup, fast | +11.8588 | +12.0283 | +0.1695 |
| Hold, slow | +0.6163 | +0.5832 | -0.0331 |
| Placed cells, excl. fill | 12,234 | **11,911** | **-323** |
| Placed cell area, um2 | 185,595 | **183,298** | **-2,297, -1.24 %** |
| **Routed wirelength, um** | **465,701** | **428,264** | **-37,437, -8.04 %** |
| Route DRC | 0 | **0** | — |

**[fact]**. **Timing-driven placement is worth +0.5856 ns and it makes
the design smaller and its wiring 8 % shorter.** Hold gives back
0.0331 ns and still closes with 0 violations on every corner.

Two things follow. **This is the one option where the estimate stages
badly under-predict the sign-off**, so judging it from mid-PnR reports —
as the +0.073 ns figure would have — would have been wrong by a factor
of eight. And it confirms section 3.4's diagnosis from the other side:
the loss really is a placement effect, and a placer that is allowed to
see timing at all recovers a large part of it, even working from the
same optimistic pre-route model.

`docs/20` section 5.3(b) is therefore only half the story. It correctly
measured that `PNR_CORNERS` alone changes nothing because
`PL_TIMING_DRIVEN` gates the flag; what it could not know without this
run is that the flag itself is worth 0.59 ns and negative area.

Sign-off result in section 6.

### 5.6 The constraint itself: measured, and declined

`docs/22` records that an unreachable constraint manufactures phantom
violations and eats effort, so the constraint was checked rather than
assumed. Section 4.4(b) has the measurements. Restated as options:

| Option | Worth | Decision |
|---|---|---|
| Drop `CLOCK_UNCERTAINTY_CONSTRAINT` from 0.25 to 0 | **+0.2500 ns** | **Declined** |
| Leave the 5 % OCV derate un-applied, as the flow does today | **+0.9910 ns** of *reported* slack | **Declined — and reported as a defect** |
| Lengthen `CLOCK_PERIOD` | 1 ns of period buys 1.0000 ns of slack **[fact, the sweep below]** | Section 7 |

**Neither of the first two is taken.** Reducing the uncertainty on a
propagated-clock sign-off, or being glad that a derate the configuration
asks for is silently not applied, is buying margin by weakening what the
number means. Section 4.4 reports the derate as the defect it is.

The constraint is **not** shaped wrong in the `docs/22` sense. A period
sweep on the shipped netlist is exactly linear — 1 ns of period gives
1 ns of slack, at both derate settings — so there is no unreachable
region and no phantom violation **[fact, OpenSTA sweep, 19.0 to 22.0 ns
in 0.5 ns steps]**. The constraint is reachable; it is simply close.

### 5.7 Restructuring the rail comparison: nothing to restructure

Section 4.1. The rails are 3.87 ns off the critical path and do not
reach its cone within 14 levels of logic. **Worth 0 ns, measured.** No
RTL was changed in this workstream, and none should be for timing.

---

## 6. What was applied

### 6.1 The summary of every option, in nanoseconds

Slow-corner setup slack at 20 ns, all measured on this RTL at the 6x2
shape, against the `wave6-6x2` baseline of **+0.3229**:

| Option | Run | Slow setup | Worth | Area cost |
|---|---|---|---|---|
| Sign-off checker fix only (control) | `tr-control` | +0.3229 | **0.0000** | **0 — byte-identical** |
| Timing-driven placement | `tr-tdp` | +0.9085 | **+0.5856** | **-2,297 um2, -1.24 %** |
| Post-GRT repair, default margin | `tr-postgrt` | +1.1778 | **+0.8549** | +147 um2, +0.079 % |
| **Post-GRT repair, margin 0.5 ns** | **`tr-margin`** | **+1.6776** | **+1.3548** | **+190 um2, +0.102 %** |
| `SYNTH_STRATEGY DELAY 0` | `tr-delay0` | **-4.0356** | **-4.3585** | +36,308 um2, +19.6 % |
| Drop clock uncertainty | — | +0.5729 | +0.2500 | **declined** (§5.6) |
| Leave the OCV derate un-applied | — | — | +0.9910 *reported* | **declined, reported as a defect** (§4.4b) |
| Remove a rail | — | — | **0.0000** | **refused and unnecessary** (§4.1, §5.7) |

**[fact]** for every measured row. Hold closes with 0 violations on all
three corners in all five runs.

**The 0.9118 ns wave 6 lost is fully recovered and then some.**
`tr-margin` is +0.4429 ns better than `shape-6x2` was *before* the wave.

### 6.2 The configuration adopted

**`tr-margin`**: the two post-global-routing repair steps with the setup
slack margin raised, plus `PNR_CORNERS` for the observability that makes
the slow corner visible mid-flow, plus the `SETUP_VIOLATION_CORNERS`
sign-off fix.

```json
"PNR_CORNERS": ["nom_typ_1p20V_25C", "nom_slow_1p08V_125C"],
"RUN_POST_GRT_DESIGN_REPAIR": 1,
"RUN_POST_GRT_RESIZER_TIMING": 1,
"GRT_RESIZER_SETUP_SLACK_MARGIN": 0.5,
"SETUP_VIOLATION_CORNERS": ["*"]
```

carried in `hw/openlane/pilot_ihp/config.tr-margin.json`, generated by
`mktiming.py`. Four keys, no RTL, +0.102 % of area.

**`PL_TIMING_DRIVEN` is deliberately *not* in the adopted set, and that
is the largest thing left on the table.** It is worth +0.5856 ns on its
own *and* costs -1.24 % area and -8 % wirelength (§5.5), so it is
strictly better than the baseline on every axis measured. It is not
adopted only because **the composition of `PL_TIMING_DRIVEN` with the
post-GRT repair was never run** — the two act at different stages and
would plausibly add, but "plausibly" is not a measurement, and this
document does not adopt a configuration it has not hardened. **That run
is the single highest-value next experiment** and it is item 10 of
section 10.

**No RTL was changed.** Section 4.1 measured that the rails are 3.87 ns
off the critical path and section 5.7 that restructuring them is worth
nothing, so there was no restructuring that a timing argument could
justify. `hw/rtl/**` is untouched by this workstream.

**Nothing was bought by weakening the design.** No rail removed, no
guard dropped, no constraint relaxed; the two constraint knobs that
would have yielded 0.25 ns and 0.99 ns of *reported* slack are declined
in section 5.6, and the second of them is reported as a flow defect
rather than banked as margin.

### 6.3 The adopted run's sign-off

`hw/openlane/pilot_ihp/runs/tr-margin`, ihp-sg13g2, 6x2, pinned to
`c52518e`.

| Deck | `wave6-6x2` | **`tr-margin`** |
|---|---|---|
| Setup, all three corners | 0 violations | **0 violations** |
| Setup slack, slow / typ / fast | +0.3229 / +7.5628 / +11.8588 | **+1.6776 / +8.4149 / +12.3666** |
| Hold, all three corners | 0 violations | **0 violations**, +0.6175 slow |
| Route DRC (`Checker.TrDRC`) | 0 | **0 — passed** |
| Power-grid violations | 0 | **0 — passed** |
| Disconnected pins | 6 | **passed** |
| Wirelength checker | pass | **passed** |
| Lint / synth checks / unmapped cells / netlist assigns | pass | **all passed** |
| Antenna violations, final | 0 | **0** |
| Antenna diodes | 3 | 8 |
| Routed wirelength, um | 465,701 | 466,001, +0.06 % |
| Placed cell area, um2 | 185,595 | **185,785, +0.102 %** |
| Utilization | 47.2266 % | **47.2751 %** |
| **Redundancy census on the repaired netlist** | 1,277 / 36 / 55·55·55 / 8 rails | **1,277 / 36 / 55·55·55 / 8 rails** |

**[fact]** for every row, from the step directories named in section 5.2
and a hand census of the netlist.

**Two things about this table should be read carefully.**

**The redundancy row is not a formality.** `RSZ_DONT_TOUCH_RX` is `$^`
and matches nothing, so the post-GRT resizer was free to resize, clone
or unbuffer a rail or a TMR replica. It resized eleven combinational
gates and touched no sequential cell: the census on the repaired netlist
finds 1,277 flip-flops, 36 pointer replicas, 55 in each of three
configuration banks and all eight rails at their expected counts
**[fact]**. Any future change to this configuration must re-run that
census, because nothing in the flow enforces it.

**Magic DRC, KLayout DRC and Netgen LVS were still executing when this
document was written** — they are the slowest steps in the flow and five
hardens plus a concurrent session were sharing twenty cores. Route DRC,
which is the deck that would show a routing consequence of the inserted
buffers, is **0 and passed**, as are the power-grid, disconnected-pin
and wirelength checkers. The three geometric decks are expected to pass,
because the change against a netlist that passed all three is **twelve
standard cells, 190 um2 and 300 um of wire** — but **that is an
expectation and not a measurement, and this configuration must not be
submitted until they are read.** It is item 7 of section 10, and it
needs no re-run: `signoff_report.py` on the finished run directory.

---

## 7. Does 50 MHz still hold?

**Yes on the adopted configuration, comfortably, and it did not on the
`docs/27` baseline once the derate is honest.** That distinction is the
whole answer.

Measured on the shipped netlist and SPEF of each run with standalone
OpenSTA at `nom_slow_1p08V_125C`. A period sweep from 19.0 to 22.0 ns is
exactly linear — 1 ns of period gives 1.0000 ns of slack — so the
break-even period is arithmetic from the slack **[fact]**:

| Netlist | Sign-off definition | Slack at 20 ns | Longest path | Fmax |
|---|---|---|---|---|
| `wave6-6x2` | as the flow signs off (no derate applied) | +0.3229 | 19.6771 ns | **50.82 MHz** |
| `wave6-6x2` | **5 % OCV derate actually applied** | **-0.6681** | 20.6681 ns | **48.38 MHz** |
| **`tr-margin`** (adopted) | as the flow signs off | **+1.6776** | 18.3224 ns | **54.58 MHz** |
| **`tr-margin`** (adopted) | **5 % OCV derate actually applied** | **+0.7510** | 19.2490 ns | **51.95 MHz** |

**[fact]**. Both no-derate rows reproduce their runs' own
`timing__setup__ws__corner:nom_slow_1p08V_125C` to 17 significant
digits, which is what establishes that the flow applies no derate.

**The honest statement, in three parts.**

**50 MHz holds on the adopted configuration under either definition,
with real margin.** +1.6776 ns as the flow reports it — **8.39 % of the
cycle** — and **+0.7510 ns, 3.76 % of the cycle**, with a 5 % OCV derate
the flow believes it is applying and is not. Hold closes on all three
corners.

**50 MHz did *not* hold on the `docs/27` baseline under the honest
definition.** +0.3229 ns as reported, **-0.6681 ns derated**. A design
signed off at 50 MHz on that netlist would have been relying on a Tcl
integer division. That is the sharpest illustration in this project of
`docs/23`'s rule that a clean number is not the same as a clean design,
and it is why section 4.4 is where it is.

**The target the design supports.** On the adopted configuration,
**54.6 MHz** by the flow's own sign-off and **51.9 MHz** with 5 % OCV.
**50 MHz remains the right target, it is no longer marginal, and it is
now honest.** Raising the target is still not advisable: 51.95 MHz
derated leaves 1.9 MHz, and the design has one more fault-tolerance wave
to absorb (§8). Keeping 50 MHz and banking the recovered margin against
that wave is the better use of it.

---

## 8. What the next hardening wave has to spend

**This is the section another agent needs, so it is written to be used
without reading the rest.**

### 8.1 The budget is not one number, it is per block

The design's timing margin is extremely unevenly distributed, and the
single WNS figure hides that completely. Worst slack of any path
*touching* each block, slow corner, on the `wave6-6x2` netlist:

| Block | Paths | Worst slack | 10th percentile |
|---|---|---|---|
| **`u_pilot.u_lif`** — neuron core | 916 | **+0.3229** | +3.8722 |
| `u_pilot.u_evq_in` — AER input queue | 125 | **+11.8851** | +12.3032 |
| `u_pilot.u_cfg_*` — configuration TMR | 340 | +11.8924 | +12.3114 |
| `u_pilot.u_evq_out` — AER output queue | 83 | **+12.5634** | +13.0406 |

**[fact, parsed from
`55-openroad-stapostpnr/nom_slow_1p08V_125C/max.rpt`]**.

**Only `lif_core` is tight.** Everything else has 11.9 ns or more —
between 59 % and 63 % of the whole cycle — of headroom. On the adopted
configuration `lif_core`'s own worst path moves from +0.3229 to
**+1.6776**, so the tight block is now at 8.4 % of the cycle rather than
1.6 %, and every other block is unchanged.

### 8.2 So the residual fault-tolerance work is nearly free, in timing

`docs/16` section 5.11 ranks **`evq_mem` at 7 silent-corruption records**
as the residual leader, and that storage is inside `u_evq_in` /
`u_evq_out`. Those cones have **+11.89 ns**. A parity or ECC wave on the
queue storage adds an XOR tree to a read path that is currently
11.9 ns clear of critical, so **it has roughly 11.6 ns of headroom before
it could become the critical path at all** — against a SECDED decode of
a 72-bit word, which section 3.2 measures at 4.85 ns end to end in
`lif_core`. There is a large multiple of the required delay available.

**[estimate, in that it assumes the new logic lands in those cones and
does not perturb `lif_core`'s placement; the slacks themselves are
facts.]** The assumption is not free — section 3.3 measured that 78 % of
the wave-6 loss arrived through placement, on cones the RTL change did
not touch. Which leads to the rule below.

### 8.3 The rules this work establishes

1. **Do not cost a wave by its flip-flop count.** `docs/27` predicted
   +2 flip-flops exactly and was right, and the margin still moved
   0.9118 ns. The mechanism was a placement change on a cone the RTL
   edit did not touch (§3.3).
2. **Do not try to buy timing with area.** Measured: `DELAY 0` spends
   19.6 % more placed area and **loses 4.36 ns**, because routed
   wirelength grows 44.8 % and this design is wire-dominated (§5.3).
   The 32.5 % of spare core is real but it is not convertible.
3. **Do buy timing with targeted sizing.** Measured: the post-GRT
   resizer bought 0.8549 ns for +0.08 % area at the default margin, and
   the margin knob buys more for the same price (§5.2, §5.4). This works
   *because* it does not grow the design.
4. **Re-measure the slow corner after every wave, and do not trust
   `design__violations`.** It does not aggregate hold (`docs/23` §3.2)
   and, until §4.4(a)'s fix is propagated, the setup checker does not
   look at the slow corner at all.
5. **Quote slack with the derate caveat** until §4.4(b) is fixed
   upstream. A reported +1 ns is not +1 ns of OCV margin; it is +1 ns
   with no OCV margin in it.
6. **Anything that lands in `lif_core`'s event path is expensive.** The
   critical path is the single-cycle neuron update — weight-file read
   mux, SECDED decode, shift, saturating add, compare, SECDED encode,
   state write (§3.2). Adding a logic level there costs roughly
   0.2 to 0.4 ns at the slow corner, judging by the per-gate delays on
   the measured path **[estimate]**. If a future wave must harden
   something inside that loop, it should be costed with a harden, not
   with a flop count.

---

## 9. Corrections for the integrator

Every entry is a figure or a statement in another document that this
work supersedes. **No document other than this one is edited.**

### 9.1 The one that touches every timing number in the repository

Section 4.4(b). `TIME_DERATING_CONSTRAINT` is set to the integer `5` by
**both** PDKs — `ihp-sg13g2/libs.tech/librelane/sg13g2_stdcell/config.tcl`
line 87, and the sky130A equivalent — and LibreLane's `base.sdc` and
`scripts/openroad/common/io.tcl` both consume it with Tcl integer
division, which yields `0` **[fact]**.

**Consequence: every setup and hold slack quoted anywhere in `docs/15`,
`docs/18`, `docs/20`, `docs/21`, `docs/22`, `docs/23`, `docs/25` and
`docs/27`, on both PDKs, is an un-derated number, while every one of
those runs logged "Setting timing derate to: 5%".** The numbers are
correct as reported and correctly reproduced; what is wrong is the
belief that they carry 5 % of OCV margin. They do not carry any.

This is not this repository's code to fix — the PDK could ship `5.0`
and LibreLane could divide by `100.0`; either alone closes it. What
this repository can do is stop quoting derate it does not apply, and
section 7 states the target both ways.

### 9.2 `docs/27-reharden-wave6.md`

| Location | Current | Replacement |
|---|---|---|
| §10 item 2, "the slow-corner margin loss is measured but not attributed … the most useful next piece of physical-design work" | as written | **closed** by sections 3 and 4 here |
| §3.1, "What this document does not establish is *which* path lost the margin, or whether the cause is the rails, the timeout retirement, or placement noise" | as written | **established**: a critical-path *swap*, `jj` -> `ev_axon_r` (§3.1); 22 % RTL and 78 % place-and-route (§3.3); **placement noise is exactly zero** (§5.0); the rails are 3.87 ns off the path (§4.1) |
| §3.1, "A design closing at 1.6 % of its period has little room for a further RTL wave" | as written | true of the baseline configuration; §5.2 and §8 restate the budget |
| §2.3(a), the `keep_hierarchy` / area reasoning, tagged **[inference]** | as written | the inference stands, but §4.3 measures that whatever optimisation the rails resist is not optimisation the critical path needed |

### 9.3 `docs/23-tile-shape-decision.md`

| Location | Current | Replacement |
|---|---|---|
| §3.2, "`design__violations` does **not** aggregate hold, which is a trap worth naming" | as written | **add the companion**: `Checker.SetupViolations` resolves its corners as `SETUP_VIOLATION_CORNERS or TIMING_VIOLATION_CORNERS`, both PDKs ship `["*typ*"]`, and `SETUP_VIOLATION_CORNERS` is unset — so **setup has never been checked at the slow corner at all** (§4.4a) |

### 9.4 `docs/25-sky130-6x2.md`

| Location | Current | Replacement |
|---|---|---|
| §8, the post-CTS resizer leaving 4.672 ns unrepaired with `RSZ-0062` raised | as written for sky130 | **does not transfer to IHP.** The IHP post-CTS resizer reports `RSZ-0098 No setup violations found` with all three corners loaded — it is not giving up, it is being asked at a point where the violations do not exist yet (§5.1) |
| §8, "the gap between the pre-route estimate and the extracted network is not a per-unit-RC error" | as written | consistent with IHP, but note the **sign is opposite**: on IHP the post-GRT estimate is *pessimistic* (-0.107 ns at `tr-postgrt` step 45) against +1.178 ns extracted |

### 9.5 `docs/20-reharden-and-corners.md`

| Location | Current | Replacement |
|---|---|---|
| §6.1, `sky-06-postgrt` moving the worst path 0.17 ns on sky130 | as written | correct for sky130; **it does not predict IHP**, where the same two steps are worth **+0.8549 ns** (§5.2) |
| §7, "Recommendation: do not set `PNR_CORNERS` on the IHP submission" | as written | still correct *on its own*; it is carried in the adopted configuration only as the observability that makes the mid-PnR slow-corner report exist, alongside the post-GRT steps that do the work |
| §5.6 item 1, "This flow is deterministic … independent of machine load" | as written | **re-confirmed** at this RTL and this shape, to 17 significant digits on all three corners (§5.0) |

### 9.6 `docs/21-pilot-datasheet.md`

§7.1's worst slow-corner setup slack and any Fmax figure need the
adopted run's numbers from section 6, and both should be quoted with the
derate caveat of §9.1.

---

## 10. What is not done

1. **The derate defect is reported, not fixed** (§4.4b, §9.1). Both the
   PDK side and the LibreLane side are outside this repository. Until
   one of them changes, a run in this repository cannot sign off with
   OCV derating through the normal flow; section 7's derated figures
   come from a standalone OpenSTA probe on the shipped artifacts, which
   is evidence but is not a flow gate.
2. **`SETUP_VIOLATION_CORNERS: ["*"]` is set in this workstream's
   configs only.** `tt/src/config_merged.json` is generated by
   `scripts/gen_tt_submission.py` and is not this workstream's file, so
   the submission config still carries the hole. It needs to be
   propagated there, or the submission will keep signing off setup at
   the typical corner only.
3. **No gate-level simulation or fault injection on any netlist here.**
   `docs/27` section 9 lists what must be re-run; every run in this
   document produces a different netlist from `wave6-6x2`, so if one of
   them is adopted that list applies to it and the netlist path changes
   again.
4. **No sky130 companion at this configuration.** Whether the post-GRT
   steps help sky130's 7.3 ns miss is untested at this RTL; `docs/20`
   section 6 says they moved its worst path 0.17 ns at an older one.
5. **`DELAY 1`, `DELAY 2`, `DELAY 3`, `DELAY 4` are untested.** §5.3
   measures `DELAY 0` at -4.3585 ns and identifies wirelength growth as
   the mechanism, which applies to all of them, but only `DELAY 0` was
   run.
6. **No annotated-activity power measurement**, as `docs/22` item 6,
   `docs/23` §3.3 and `docs/27` item 6 already record.
7. **The adopted run's Magic DRC, KLayout DRC and Netgen LVS are not
   read** (§6.3). Route DRC, power-grid, disconnected-pin and wirelength
   checkers are 0 and passed; the three geometric decks were still
   running when this was written. **This configuration is not
   submission-ready until they are read**, and reading them needs no
   re-run:
   `python3 hw/openlane/signoff_report.py hw/openlane/pilot_ihp/runs/tr-margin`
   once the run directory is complete. The same applies to `tr-postgrt`,
   `tr-tdp`, `tr-control` and `tr-delay0`.
8. **`GRT_RESIZER_SETUP_SLACK_MARGIN` was tested at two values only**,
   0.025 and 0.5 (§5.4). The resizer plateaued at +0.578 ns on its own
   estimate at 0.5, so a larger value is unlikely to help, but that is
   an inference from one plateau and not a measurement.
9. **`PL_TIMING_DRIVEN` composed with the post-GRT repair was never
   run**, and it is the highest-value experiment left (§6.2). Separately
   the two are worth +0.5856 ns and +1.3548 ns; together they are
   unmeasured. The variant needs one line in `mktiming.py` and one
   harden.
10. **The two provenance-gated real-flow guards were skipping when this
   work started** — `sw/tests/test_synthesis_guards.py` reported
   **25 passed, 2 skipped**, because the concurrent edit of §1.2 made
   `hw/rtl/aer_fifo.v` newer than every netlist on disk **[fact]**. The
   guard compares netlist mtime against *live* `hw/rtl` mtimes, so a
   pinned run built from an older commit un-skips them and is then
   checked against rail expectations written for the live RTL. That is
   sound while the rail names and counts are unchanged, and it is worth
   knowing before someone changes them.

---

## 11. Reproducing this

```bash
make -f tools.mk toolcheck

# Derive the variants from the 6x2 submission config and prove no drift.
python3 hw/openlane/pilot_ihp/mktiming.py
python3 hw/openlane/pilot_ihp/mktiming.py --check
python3 hw/openlane/pilot_ihp/mkconfig.py --check

# Pin the RTL. The blob list in section 1.2 is the record; the snapshot
# is disposable and fully regenerable from c52518e.
python3 hw/openlane/pin_rtl.py c52518e \
    hw/openlane/pilot_ihp/config.tr-postgrt.json /tmp/pin-tr-postgrt

# Harden. Any of the six tags works the same way.
mkdir -p hw/openlane/pilot_ihp/runs/tr-postgrt
CONFIG=/tmp/pin-tr-postgrt/config.json \
  hw/openlane/pilot_ihp/run_ihp.sh \
    --run-tag tr-postgrt \
    --force-run-dir $PWD/hw/openlane/pilot_ihp/runs/tr-postgrt

# The sign-off set, both runs read the same way.
python3 hw/openlane/signoff_report.py \
    hw/openlane/pilot_ihp/runs/tr-postgrt \
    tt/runs/wave6-6x2
```

The two measurements that are **not** flow steps, and how they were made:

**The per-cone decomposition of sections 3.1 and 8.1** parses every path
in `55-openroad-stapostpnr/nom_slow_1p08V_125C/max.rpt` (1,653 of them),
resolves each startpoint flip-flop to the net its `Q` pin drives, and
groups by that net. A single WNS figure cannot show a cone swap; the
population can.

**The derate and uncertainty measurements of section 4.4(b)** run
OpenSTA standalone on the shipped artifacts, so they are the flow's own
netlist, parasitics, constraints and liberty, with one thing changed:

```tcl
read_liberty <pdk>/sg13g2_stdcell/lib/sg13g2_stdcell_slow_1p08V_125C.lib
read_liberty <pdk>/sg13g2_io/lib/sg13g2_io_slow_1p08V_3p0V_125C.lib
read_verilog  tt/runs/wave6-6x2/final/nl/tt_um_melihakbulut_nssoc.nl.v
link_design   tt_um_melihakbulut_nssoc
read_spef     tt/runs/wave6-6x2/final/spef/nom/tt_um_melihakbulut_nssoc.nom.spef
read_sdc      tt/runs/wave6-6x2/final/sdc/tt_um_melihakbulut_nssoc.sdc
set_propagated_clock [all_clocks]
set_timing_derate -early 0.95
set_timing_derate -late  1.05
puts [worst_slack -max]
```

With the derate lines removed this prints
`0.32288661547280123`, the run's own metric to the last digit, which is
what proves the flow applies none. With them in place it prints
`-0.6681198006172618`.
