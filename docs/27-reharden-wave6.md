# 27 — Re-harden after the wave-6 valid-flag rails, and what the flip-flop count did not predict

Status: complete. One IHP SG13G2 harden at the 6x2 submission shape,
pinned to `2c6c052`, clean on every sign-off deck. It supersedes the
`shape-6x2` netlist that `docs/23`, `docs/24` and `docs/26` report and
that `hw/tb/Makefile.gl` and `hw/tb/Makefile.glfi` still default to.
**No document other than this one is edited.** Section 8 lists, location
by location, what must change in the others.

It also closes `docs/23` open item 4 — "`tt/runs/` has no 6x2 harden" —
and re-closes the guard `docs/22` opened.

Convention, inherited from `docs/18` and `docs/22`: **[fact]** = measured
in this environment or read out of an installed file; **[estimate]** =
derived or judged.

Run trees under `hw/openlane/*/runs/` and `tt/runs/` are **gitignored**,
so every number below is quoted with the run tag and the step directory
it came from.

### Headline

- **The guard passes again, and it is no longer skipping.**
  `sw/tests/test_synthesis_guards.py` is **26 passed, 0 skipped**,
  against **25 passed, 1 skipped** immediately before this run.
  `test_pointer_tmr_survives_the_real_hardening_flow` **PASSED**: twelve
  pointer replica banks at three flip-flops each in the netlist
  LibreLane actually produced. The configuration TMR is still 55 in each
  of three banks. Section 7.
- **The flip-flop count is exactly as predicted: 1,275 -> 1,277, plus
  two.** All `sg13g2_dfrbpq_1`. `docs/16`'s mutation table independently
  publishes 1,277 as the ASIC total at this RTL, and synthesis reads
  1,277, so two counts derived by different routes agree **[fact]**.
- **Three things moved that the flip-flop count did not predict, and one
  of them matters.** Section 2.2 and section 3:
  1. **Synthesis cells FELL by 135** (9,821 -> 9,686) while synthesis
     cell area ROSE by 311 um2. Fewer cells, more area.
  2. **Antenna went from nothing to something**: 0 violating nets and
     0 diodes became **2 nets and 3 diodes**, which forced a **second
     detailed-route pass**. Routing effort doubled — 1 pass of 5
     iterations became **2 passes of 10** — for the same zero-DRC
     result. Section 4.
  3. **The slow-corner setup margin fell by 0.9118 ns**, from
     **+1.2347 ns to +0.3229 ns**. That is **74 % of the margin**, and
     it is the finding in this document that deserves attention.
     Every corner still closes with every violation counter at zero,
     so this is a margin erosion and not a failure. Section 3.
- **The sign-off is clean on every deck.** 0 route DRC, 0 Magic DRC,
  **0 KLayout DRC**, 0 Netgen LVS on all five counters, 0 antenna
  violations after repair, 0 power-grid violations, `design__violations:
  0`, `flow__errors__count: 0`.
- **The tile budget holds comfortably and gets marginally better.**
  **47.2266 %** utilization against `docs/23`'s 47.2889 %, and
  **+127,852 um2 of spare, +32.53 % of the core**, against a 70 %
  planning criterion. Section 6.
- **Total power is essentially unchanged**: 5.1186 mW against 5.1301 mW,
  **-0.22 %**. Section 5.

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

No mismatch warning **[fact]**. The hardening flow is the rootless
LibreLane of `docs/12` section 2.1, unchanged from `docs/22` section 1.1
and `docs/23`:

| Component | Version | Where it is pinned |
|---|---|---|
| LibreLane | 3.0.5 | `~/Documents/caravel-lif-crossbar/.venv-flow` |
| Yosys (in-flow) | 0.67, git sha1 `2d1509d1b` | LibreLane wheel (`pyosys`) |
| Yosys (guards, `tools.mk`) | 0.67+146 | `OSS_CAD_SUITE` pin |
| ihp-sg13g2 PDK | `c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c` | LibreLane `pdk_hashes.yaml`, asserted by `run_ihp.sh` |
| Magic | 8.3.678 | `~/.local/opt/magic-8.3.678` |

**[fact]** for every row. `run_ihp.sh` reads the PDK hash out of the
installed wheel and refuses to start on a mismatch, and the run's own
`resolved.json` records `PDK_ROOT` ending in that hash, so this run
cannot have hardened against an untested PDK **[fact,
`tt/runs/wave6-6x2/resolved.json`]**.

#### Does anything reach outside the pinned oss-cad-suite?

The commissioning task asked this explicitly. **Nothing that produced a
number in this document does**, but there is a latent path worth
recording:

- The shim `~/.local/opt/llbin/yosys` carries a fallback
  `REAL_YOSYS=/home/hasanmelih/Documents/gt2n-soc/tools/oss-cad-suite/bin/yosys`,
  which is **Yosys 0.67+94** — a *sibling project's* checkout, not the
  `tools.mk` pin (0.67+146) **[fact, both binaries' `-V`]**. That is
  precisely the class of path `tools.mk` was written to close.
- **It is not the path this run took.** LibreLane 3.0.5 invokes Yosys as
  `yosys -y <script>`, and the shim's `-y` branch dispatches to the venv
  Python, i.e. to the wheel's `pyosys`. The synthesis report's own
  provenance string is
  `"creator": "Yosys 0.67 (git sha1 2d1509d1b, ...)"` **[fact,
  `tt/runs/wave6-6x2/06-yosys-synthesis/reports/stat.json`]** — the
  wheel build, which is neither of the two `oss-cad-suite` checkouts on
  this machine.

So synthesis is pinned by the LibreLane wheel, the guards and formal are
pinned by `tools.mk`, and the sibling checkout is reachable only through
a fallback branch this flow does not take. **A latent path, not a live
hole.** It is recorded as section 10 item 1 rather than fixed, because
`~/.local/opt/llbin` is outside this repository.

The formal side of the same question is closed: all six makefiles in
`formal/` — `Makefile`, `ecc.mk`, `lif_ctrl.mk`, `lif_mem.mk`,
`npu_regbank.mk`, `scrub.mk` — carry exactly one
`include .../tools.mk` each, so a standalone `make -f <fragment>.mk`
resolves `SBY` through the pin instead of through `command -v`
**[fact, `grep -c "include.*tools.mk"` on each of the six]**.

### 1.2 Sources: the blob list, pinned

`docs/18` set the precedent that a run must name the source it consumed,
and `docs/20` section 1.2 records why: a concurrent session rewrote
`hw/rtl/lif_core.v` between a run's lint step and its synthesis step and
the run directory held no evidence of which version it read. `docs/22`
then had it happen again *during* its own runs. This run is pinned with
`hw/openlane/pin_rtl.py` against commit **`2c6c052`** and reads a
disposable snapshot by absolute path, not `hw/rtl`:

```
$ python3 hw/openlane/pin_rtl.py 2c6c052 \
      hw/openlane/pilot_ihp/config.6x2.json <scratch>/pin-ihp-6x2-w6
pinned to 2c6c052 (2c6c0525ee2a)
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

**[fact, `hw/openlane/pin_rtl.py`, which prints the blob of every file it
writes]**. The working tree was clean at `2c6c052` when the snapshot was
taken **[fact, `git status --short` empty]**.

Only seven of these ten are compiled — `VERILOG_FILES` names
`tt_um_melihakbulut_nssoc.v`, `pilot_top.v`, `lif_core.v`, `aer_fifo.v`,
`tmr_voter.v`, `secded_enc.v`, `secded_dec.v`; `pin_rtl.py` materialises
the whole directory so the include path resolves.

All seven compiled files carry **identical blobs in `hw/rtl/` and
`tt/src/`**, so the submission copies and the hardened sources are the
same files and not merely equivalent ones **[fact, `git hash-object` on
both trees]**.

### 1.3 What moved since the netlist this replaces

`shape-6x2` was pinned against **`e1361fe`**. Blob for blob against
`2c6c052`:

| File | `e1361fe` | `2c6c052` | |
|---|---|---|---|
| `aer_fifo.v` | `c6f26c165faa` | **`70045ec25774`** | **changed** |
| `lif_core.v` | `b196828f65c2` | **`72f4f0af662b`** | **changed** |
| `pilot_top.v` | `a1fdc4ce9ded` | **`3d9f84047748`** | **changed** |
| `npu_regbank.v` | `e6c1e6466438` | `e6c1e6466438` | same |
| `npu_regs.vh` | `9aaaa394e7a6` | `9aaaa394e7a6` | same |
| `scrub.v` | `89e62789ad01` | `89e62789ad01` | same |
| `secded_dec.v` | `f7c7ec187a0d` | `f7c7ec187a0d` | same |
| `secded_enc.v` | `b5710b8a679c` | `b5710b8a679c` | same |
| `tmr_voter.v` | `62b5f4d2a1ea` | `62b5f4d2a1ea` | same |
| `tt_um_melihakbulut_nssoc.v` | `e294afcf03e1` | `e294afcf03e1` | same |

**[fact, `git rev-parse <commit>:hw/rtl/<file>`]**. Three of the seven
compiled files moved. The four RTL changes they carry:

1. **The timeout-pulse retirement** — `pilot_top.v`, **minus two
   flip-flops**.
2. **`oh_valid` dual-railed** — `pilot_top.v` `pilot_flag_rail`, two
   rails replacing one flip-flop, **plus one**.
3. **`rd_valid` dual-railed** — `aer_fifo.v` `aer_flag_rail`, two rails
   replacing one flip-flop *per queue instance*, and the module is
   instantiated twice, **plus two**.
4. **`out_pend` dual-railed** — `lif_core.v` `lif_flag_rail`, two rails
   replacing one flip-flop, **plus one**.

Net **plus two flip-flops**, and three of the four add `keep_hierarchy`
rail instances. Section 2.2 reports what that did to everything else.

### 1.4 The run

| Tag | Path | PDK | Shape | Config |
|---|---|---|---|---|
| **`wave6-6x2`** | **`tt/runs/wave6-6x2`** | ihp-sg13g2 | 6x2 | `pilot_ihp/config.6x2.json`, pinned to `2c6c052` |

Exact commands:

```bash
make -f tools.mk toolcheck

python3 hw/openlane/pin_rtl.py 2c6c052 \
    hw/openlane/pilot_ihp/config.6x2.json <scratch>/pin-ihp-6x2-w6

mkdir -p tt/runs/wave6-6x2
CONFIG=<scratch>/pin-ihp-6x2-w6/config.json \
  hw/openlane/pilot_ihp/run_ihp.sh \
    --run-tag wave6-6x2 --force-run-dir $PWD/tt/runs/wave6-6x2
```

**It is written into `tt/runs/` and not into
`hw/openlane/pilot_ihp/runs/`, and that placement is deliberate.**
`sw/tests/test_synthesis_guards.py` scans exactly two trees for a real
hardening netlist — `hw/openlane/pilot_sky130/runs/` and `tt/runs/` —
and `hw/openlane/pilot_ihp/runs/` is **not** one of them **[fact,
`RUN_TREES`, line 894]**. `docs/22` section 1.3 records the same trap:
"a re-harden that landed only in the `pilot_ihp` tree would have
produced every number in section 2 and still left the guard skipping."
`docs/23` open item 4 then asked for exactly this run — "a `tt/runs/`
harden at 6x2 before submission would keep the guard's evidence and the
submission's shape aligned." **This run closes `docs/23` open item 4.**

The configuration is the submission's own geometry. `config.6x2.json` is
generated by `mkconfig.py` from `tt/src/config_merged.json`, and that
file now carries `DIE_AREA: "0 0 1289.28 313.74"` and the 6x2 pin frame,
so the submission config and the 6x2 variant are the same shape; the
variant differs only by `RUN_KLAYOUT_DRC: 1`, raised so that one run
produces the whole sign-off set **[fact, both files]**. The run's own
`resolved.json` confirms `SYNTH_HIERARCHY_MODE: deferred_flatten`,
`DIE_AREA: [0, 0, 1289.28, 313.74]`, `CLOCK_PERIOD: 20` and
`RUN_KLAYOUT_DRC: true` **[fact]**, and reports
`design__instance_unmapped__count: 0`.

Every number below is extracted with `hw/openlane/signoff_report.py` and
`hw/openlane/route_trace.py` rather than by hand-grep, so the two runs
being compared are read the same way.

### 1.5 The netlist

| | `shape-6x2` — superseded | **`wave6-6x2`** |
|---|---|---|
| Path | `hw/openlane/pilot_ihp/runs/shape-6x2/final/nl/tt_um_melihakbulut_nssoc.nl.v` | **`tt/runs/wave6-6x2/final/nl/tt_um_melihakbulut_nssoc.nl.v`** |
| git blob | `e8f72bde4c5a02101a226f5d98bde36c1229c084` | **`70a359bef803d4ffc55f2ea7ac1cf2bcc9045087`** |
| Size | 2,570,202 bytes | **2,546,508 bytes** |
| Modules | 1, fully flattened | **1, fully flattened** |

**[fact, `git hash-object`, `wc -c`, `grep -c '^module '`]**.

---

## 2. The re-hardened sign-off

`tt/runs/wave6-6x2`, ihp-sg13g2, 6x2 tile, completed with
`flow__errors__count: 0` and `design__violations: 0` **[fact,
`tt/runs/wave6-6x2/final/metrics.json`]**.

### 2.1 Sign-off table, beside the run it replaces

`shape-6x2` is the correct predecessor: same flow, same config file,
same shape, same extraction script — only the RTL differs.

| Quantity | `shape-6x2` (`docs/23` §2.1) — **superseded** | **`wave6-6x2`** | Move |
|---|---|---|---|
| **Mapped flip-flops** | 1,275 | **1,277** | **+2** |
| Flip-flop cell type | all `sg13g2_dfrbpq_1` | **all `sg13g2_dfrbpq_1`** | — |
| **Synthesis cells** | 9,821 | **9,686** | **-135, -1.37 %** |
| **Synthesis cell area, um2** | 151,789.11 | **152,099.79** | **+310.68, +0.20 %** |
| Placed cells, excl. fill | 12,418 | **12,234** | -184, -1.48 % |
| Instances incl. fill | 33,801 | **33,649** | -152 |
| of which fill cells | 21,383 | **21,415** | +32 |
| of which antenna cells | 0 | **3** | **+3** |
| Sequential cells | 1,275 | **1,277** | +2 |
| Timing-repair buffers | 2,430 | **2,379** | -51 |
| of which hold buffers | 1,406 | **1,390** | -16 |
| of which setup buffers | 0 | **0** | — |
| **Placed cell area, um2** | 185,840 | **185,595** | **-245, -0.13 %** |
| Area, sequential cells, um2 | 62,460.7 | **62,558.7** | +98.0 |
| Area, repair buffers, um2 | 30,391.2 | **29,875.9** | -515.3 |
| Area, clock buffers, um2 | 3,294.95 | **3,224.19** | -70.76 |
| Die area, um2 | 404,499 | **404,499** | — |
| Core area, um2 | 392,988 | **392,988** | — |
| **Utilization** | **47.2889 %** | **47.2266 %** | **-0.0623 pts** |
| Routed wirelength, um | 469,914 | **465,701** | -4,213, -0.90 % |
| Summed step runtime | 32.3 min | **33.5 min** | +1.2 min |

**[fact, `signoff_report.py` on each run's `final/metrics.json`, and
`06-yosys-synthesis/reports/stat.json` for the synthesis rows]**.

### 2.2 Sign-off decks — all clean, both runs

| Deck | `shape-6x2` | **`wave6-6x2`** |
|---|---|---|
| Route DRC (`Checker.TrDRC`) | 0 | **0** |
| **Magic DRC** | 0 | **0** |
| **KLayout DRC** | 0 | **0** |
| **Netgen LVS** | 0 | **0** |
| LVS unmatched nets / devices / pins | 0 / 0 / 0 | **0 / 0 / 0** |
| LVS property fails | 0 | **0** |
| Antenna violations, final | 0 | **0** |
| Antenna diodes inserted | **0** | **3** |
| Power-grid violations | 0 | **0** |
| Disconnected pins | 6 | **6** |
| Max-fanout violations | 82 | **84** |
| `design__violations` | 0 | **0** |
| `flow__errors__count` | 0 | **0** |
| Unmapped instances | 0 | **0** |

**[fact]**. The `disconnected pins: 6` figure is carried unchanged from
`shape-6x2` and is not new here; the `max-fanout violations` counter
moves 82 -> 84 and is, as in `docs/23`, a reported count that
`design__violations` does not aggregate.

### 2.3 Did anything move beyond the two flip-flops? Yes — three things

**The flip-flop count itself is exactly as predicted.** 1,275 -> 1,277.
`docs/16`'s mutation table publishes 1,277 as the ASIC total at this
RTL, derived from the yosys census rather than from a harden, and
synthesis here reads 1,277 **[fact, two independent routes to the same
number]**. The arithmetic of section 1.3 — minus two, plus one, plus
two, plus one — holds exactly.

**But the netlist is not "the same netlist plus two flip-flops."**

**(a) Fewer cells, more synthesis area.** Synthesis cells fell by 135
while synthesis cell area rose by 311 um2. Those move in opposite
directions, so the average cell got larger. The plain reading is that
the two effects are different changes: the timeout-pulse retirement
removed a counter and its comparison logic — many small combinational
cells — while the three rail pairs added `keep_hierarchy` instances that
`flatten` skips and `opt_merge` will not touch, so their flip-flops and
the logic feeding them survive optimisation intact. **[inference; the
directions are measured, the attribution to the two RTL changes is
reasoning, not a measurement.]**

This is the third time this project has found that hierarchy and area do
not follow the flop count. It went the *favourable* way here: placed
cell area fell 245 um2 and utilization improved 0.06 points.

**(b) Antenna appeared where there was none.** `shape-6x2` inserted zero
diodes; this run finds 2 violating nets at the first antenna check and
inserts 3 diodes. Section 4 takes the consequence apart — it is the
reason detailed routing took twice as many iterations.

**(c) The slow-corner setup margin fell by 0.9118 ns.** Section 3. This
is the one a reader should carry away, and it is not predicted by any
area or cell-count row above.

---

## 3. Timing

20 ns clock, post-PnR STA on extracted parasitics, all figures in ns.

| Corner | Metric | `shape-6x2` — superseded | **`wave6-6x2`** | Move |
|---|---|---|---|---|
| `nom_slow_1p08V_125C` | **setup WNS** | **+1.2347** | **+0.3229** | **-0.9118** |
| | setup violations | 0 | **0** | — |
| | hold WNS | +0.6039 | **+0.6163** | +0.0124 |
| | hold violations | 0 | **0** | — |
| `nom_typ_1p20V_25C` | setup WNS | +8.1297 | **+7.5628** | -0.5669 |
| | setup violations | 0 | **0** | — |
| | hold WNS | +0.2907 | **+0.2936** | +0.0029 |
| | hold violations | 0 | **0** | — |
| `nom_fast_1p32V_m40C` | setup WNS | +12.1329 | **+11.8588** | -0.2741 |
| | setup violations | 0 | **0** | — |
| | hold WNS | +0.1089 | **+0.1137** | +0.0048 |
| | hold violations | 0 | **0** | — |
| all three | max-slew violations | 0 | **0** | — |
| all three | max-cap violations | 0 | **0** | — |

**[fact, `signoff_report.py` on each run's `final/metrics.json`]**.

### 3.1 The slow-corner erosion, stated plainly

Slow-corner Fmax from the slow-corner WNS: **53.29 MHz -> 50.82 MHz**
**[estimate, arithmetic: `1000 / (20 - WNS)`]**.

Three things should be said, in both directions.

**It still closes, on every corner, on every counter.** Setup
violations 0, hold violations 0, max-slew 0, max-cap 0, at all three
PVT corners. `design__violations: 0` and `flow__errors__count: 0`. There
is no failing check in this run.

**The remaining margin is thin.** +0.3229 ns at a 20 ns period is
**1.61 % of the cycle**. `docs/22` recorded +1.1554 ns at 4x2 and
`docs/23` improved it to +1.2347 ns by moving to 6x2; this run gives
back more than the whole 6x2 gain and then some. A design closing at
1.6 % of its period has little room for a further RTL wave, for
PNR_CORNERS variation, or for the shuttle's own top-level assembly.

**Hold moved the other way, slightly.** Hold WNS improved on all three
corners, consistent with 16 fewer hold buffers being needed and with the
clock tree getting marginally less skewed at the fast corner
(-0.2862 ns -> -0.2815 ns). At the slow corner clock skew worsened
slightly (setup skew 0.2950 -> 0.3035 ns), which is a small part of the
setup story but not the whole of it **[fact,
`clock__skew__worst_*__corner:*`]**.

**What this document does not establish** is *which* path lost the
margin, or whether the cause is the rails, the timeout retirement, or
placement noise. That needs the slow-corner `violator_list.rpt` and a
path-level comparison, and it is section 10 item 2.

---

## 4. Routing and antenna — the one place the shape did not stay still

### 4.1 Global routing

`GRT_ALLOW_CONGESTION` is set, inherited from the Tiny Tapeout defaults,
so global routing reports overflow rather than failing on it. Overflow
here is a leading indicator, not an error (`docs/23` section 4.2).

| Layer | Resource | `shape-6x2` demand | **`wave6-6x2`** demand |
|---|---|---|---|
| Metal1 | 0 | 0 | **0** |
| Metal2 | 67,010 | 25,129 (37.50 %) | **24,316 (36.29 %)** |
| Metal3 | 85,880 | 30,427 (35.43 %) | **29,766 (34.66 %)** |
| Metal4 | 67,010 | 3,151 (4.70 %) | **3,416 (5.10 %)** |
| Metal5 | 83,424 | 4,775 (5.72 %) | **5,286 (6.34 %)** |
| TopMetal1 | 12,264 | 0 (0.00 %) | **14 (0.11 %)** |
| **Total** | **315,588** | **63,482 (20.12 %)** | **62,798 (19.90 %)** |
| **Total overflow** | — | **0** | **0** |

**[fact, `route_trace.py` on each run]**. Global routing got *slightly
easier*: 684 fewer demand cells, 0.22 points less usage, zero overflow
on both. Nothing here predicts section 4.2.

### 4.2 Detailed routing, and the second pass

| Run | Trace | Passes | Iterations | Ends at |
|---|---|---|---|---|
| `shape-6x2` — superseded | `4256 -> 2291 -> 2059 -> 134 -> 0` | **1** | **5** | 0 |
| **`wave6-6x2`** | `4405 -> 2007 -> 1773 -> 50 -> 4 -> 4 -> 0` then `47 -> 4 -> 0` | **2** | **10** | **0** |

**[fact, `route_trace.py`]**. Both converge monotonically to zero and
both finish `route__drc_errors: 0`, so **the routing result is the same
and the routing effort is not**: twice the passes, twice the iterations.

The cause is not congestion — section 4.1 shows congestion fell. It is
antenna repair:

| | `shape-6x2` | **`wave6-6x2`** |
|---|---|---|
| Antenna violating nets, first check (step 40) | 0 | **2** |
| Antenna violating pins, first check | 0 | **2** |
| **Antenna diodes inserted** | **0** | **3** |
| Antenna cell area, um2 | 0 | **16.33** |
| Antenna violating nets, re-check (step 46) | 0 | **0** |
| `route__antenna_violation__count`, final | 0 | **0** |

**[fact, per-step `or_metrics_out.json` in
`40-openroad-checkantennas`, `42-openroad-repairantennas`,
`44-openroad-detailedrouting` and `46-openroad-checkantennas-1`]**.

`docs/23` section 4.3 records that 6x2 "needs no second pass because the
antenna checker found nothing to repair". On this RTL the checker finds
two nets, three diodes go in, and the router runs again on the changed
netlist. **The second pass is a consequence of the antenna repair, not
of a routing difficulty**, and it clears in three iterations from 47
violations.

That sentence in `docs/23` is now false for the current RTL, and it is
in the corrections list as section 8.1.

---

## 5. Power

Flow estimate at 50 MHz on the typical corner, from default switching
activity — not an annotated-activity measurement. The `docs/22` section
7 and `docs/23` section 3.3 open item about that still stands.

| | `shape-6x2` | **`wave6-6x2`** | Move |
|---|---|---|---|
| Internal, mW | 4.2402 | **4.2319** | -0.20 % |
| Switching, mW | 0.87546 | **0.87233** | -0.36 % |
| Leakage, mW | 0.014350 | **0.014355** | +0.03 % |
| **Total, mW** | **5.1301** | **5.1186** | **-0.22 %** |
| Worst IR drop, V | 0.000616 | **0.000635** | +3.1 % |
| Power-grid violations | 0 | **0** | — |

**[fact, `power__*__total`, `ir__drop__worst`,
`design__power_grid_violation__count`]**. Power does not discriminate
between the two netlists: 11.5 uW of a 5.1 mW total. IR drop rises 33 uV
on a 1.2 V supply, which is not a consideration.

---

## 6. The tile budget

The criterion is `docs/15` section 4's, restated by `docs/23` section
2.2: the design should not need more than 70 % of the available
placement rows. It is checked rather than assumed, because it is the
criterion that put 4x2 over in `docs/22`.

| | `shape-6x2` | **`wave6-6x2`** |
|---|---|---|
| Placed cell area, um2 | 185,840 | **185,595** |
| Core offered, um2 | 392,988 | **392,988** |
| **Needed at the 70 % criterion, um2** | 265,486 | **265,136** |
| **Spare, um2** | **+127,502** | **+127,852** |
| **Spare as % of core** | **+32.44 %** | **+32.53 %** |
| **Utilization** | **47.2889 %** | **47.2266 %** |

**[fact]** for the placed areas and the core; the criterion itself is a
planning choice, not a measurement.

**The budget holds, with a very large margin, and it improved.** The
design places 245 um2 less than the netlist it replaces, so it needs
350 um2 less core at the criterion and has 350 um2 more spare. At
**47.23 % against a 70 % criterion the design uses 67.5 % of its
allowance**, and there is no plausible reading on which twelve tiles is
tight.

**The four RTL changes did not move the tile decision, and could not
have.** For 6x2 to fail the criterion the placed area would have to
reach 275,092 um2, a **+48 %** growth on this netlist **[estimate,
arithmetic]**. The wave-6 changes moved it by **-0.13 %**.

---

## 7. The guards

### 7.1 The suite

```
$ .venv/bin/python -m pytest sw/tests/test_synthesis_guards.py -q
26 passed in 69.66s
```

**26 passed, 0 skipped** **[fact]**. Immediately before this run, on the
same RTL and the same tree, the same command reported **25 passed, 1
skipped** **[fact, measured before the netlist was written]**. The skip
was `test_pointer_tmr_survives_the_real_hardening_flow`, and it skipped
because every LibreLane run on disk predated `hw/rtl/aer_fifo.v`. That
is the provenance condition working as designed, and this run is what
closes it.

### 7.2 The census on the shipped netlist

Counted on
`tt/runs/wave6-6x2/final/nl/tt_um_melihakbulut_nssoc.nl.v` — the netlist
that would be manufactured — with the same cell regex, the same
`_is_flop` predicate and the same instance-prefix rule the guard file
uses.

| Domain | Banks | Expected each | Found | Verdict |
|---|---|---|---|---|
| Configuration TMR | `u_cfg_a/b/c` | 55 | **55, 55, 55** | **PASS** |
| AER pointer TMR | 12 banks, both queues | 3 | **3 in every one of the twelve** | **PASS** |
| `oh_valid` rails | `u_ohv_a/b` | 1 | **1, 1** | **PASS** |
| `rd_valid` rails | `u_evq_in/out . u_rdv_a/b` | 1 | **1, 1, 1, 1** | **PASS** |
| `out_pend` rails | `u_lif.u_op_a/b` | 1 | **1, 1** | **PASS** |
| **Total mapped flip-flops** | | | **1,277**, all `sg13g2_dfrbpq_1` | |

**[fact]**. **No count is wrong.** 165 configuration replica flip-flops,
36 pointer replica flip-flops and 8 rail flip-flops are physically
present and distinct in the netlist LibreLane produced. There is no
synthesis-merge finding in this run.

The same census run against the superseded `shape-6x2` netlist reads
1,275 flip-flops, the same 55/55/55 and the same twelve 3s, and **zero
in all eight rail banks** **[fact]** — which is the direct demonstration
that the superseded netlist does not contain the current redundancy and
is not evidence for it.

### 7.3 A gap: the rails have no real-flow guard

This is a finding, and it is why section 7.2 is a hand-run census rather
than a quoted test result.

`sw/tests/test_synthesis_guards.py` has **two** tests that read a real
LibreLane netlist — `test_config_tmr_survives_the_real_hardening_flow`
and `test_pointer_tmr_survives_the_real_hardening_flow`. The eight rail
tests (`test_show_ahead_valid_*`, `test_read_valid_*`,
`test_out_pend_*`) all run against the **yosys model** fixtures
(`asic`, `ecp5`, `ecp5_forced`), not against the shipped netlist
**[fact, the fixture parameter of each test]**.

So the rails are guarded in the *recipe* and not in the *artifact*,
which is precisely the distinction
`test_config_tmr_survives_the_real_hardening_flow`'s own docstring exists
to make: "the model is close but not byte-identical … so it can agree
with itself while the shipped flow does something else."

The census in section 7.2 closes the question **for this run, by hand**.
It does not close it for the next one. A third real-flow test covering
the eight rails would; `sw/tests/**` is outside this workstream's
ownership and is not edited here. Section 10 item 3.

---

## 8. Corrections for the integrator

Every entry is a figure or a statement in another document that this run
supersedes. **No document other than this one is edited.** Sources are
`tt/runs/wave6-6x2` unless stated.

### 8.1 `docs/23-tile-shape-decision.md`

| Location | Current | Replacement | Source |
|---|---|---|---|
| §2.1 table, whole `shape-6x2` column | 1,275 / 9,821 / 151,789.11 / 12,418 / 33,801 / 2,430 / 1,406 / 185,840 / 47.2887 % / 469,914 | **1,277 / 9,686 / 152,099.79 / 12,234 / 33,649 / 2,379 / 1,390 / 185,595 / 47.2266 % / 465,701** | §2.1 above |
| §2.1, "Synthesis is identical across all three, to the cell and to two decimal places of area" | as written | still true of the three runs it describes; **no longer true across RTL waves** — synthesis cells fell 135 and area rose 311 um2 on the same shape | §2.1, §2.3 above |
| §2.2 table, 6x2 row | needed 265,486, spare +127,502, +32.44 % | **needed 265,136, spare +127,852, +32.53 %** | §6 above |
| §3.1 table, `shape-6x2` column | +1.2347 / +8.1297 / +12.1329 setup; +0.6039 / +0.2907 / +0.1089 hold | **+0.3229 / +7.5628 / +11.8588 setup; +0.6163 / +0.2936 / +0.1137 hold** | §3 above |
| §3.1, "Slow-corner Fmax … 6x2 **53.3 MHz**" | as written | **50.8 MHz** **[estimate]** | §3.1 above |
| §3.2, "6x2 does not raise the question at all" (of a non-zero violation counter) | as written | still true — every counter is zero — but the slow-corner **margin** fell 0.9118 ns to +0.3229 ns, 1.61 % of the cycle | §3.1 above |
| §3.3 power table, 6x2 column | 4.2402 / 0.8755 / 0.014350 / **5.1301** / IR 0.000616 | **4.2319 / 0.87233 / 0.014355 / 5.1186** / IR **0.000635** | §5 above |
| §4.2 table, IHP 6x2 column | 63,482 demand, **20.12 %** | **62,798 demand, 19.90 %** | §4.1 above |
| §4.3 table, IHP 6x2 row | `4256 -> 2291 -> 2059 -> 134 -> 0`, **1** pass, **5** iterations | **`4405 -> 2007 -> 1773 -> 50 -> 4 -> 4 -> 0` then `47 -> 4 -> 0`, 2 passes, 10 iterations**, still ends at 0 | §4.2 above |
| §4.3, "6x2 is the cleanest routing of any run in this project's record … clears them in five iterations, and **needs no second pass because the antenna checker found nothing to repair**" | as written | **retract for the current RTL**: the antenna checker finds 2 nets, 3 diodes are inserted, and a second pass runs. The comparative claim against 3x4 is untested on this RTL | §4.2 above |
| §4.4 antenna table, IHP 6x2 column | 0 nets, 0 diodes | **2 nets and 2 pins at the first check, 3 diodes, 0 after repair** | §4.2 above |
| §10 item 3, "The netlist to re-run [gate-level] against is now `hw/openlane/pilot_ihp/runs/shape-6x2/final/nl/`" | as written | **`tt/runs/wave6-6x2/final/nl/`** | §1.5, §9 above |
| §10 item 4, "**`tt/runs/` has no 6x2 harden**" | as written | **closed by `tt/runs/wave6-6x2`** | §1.4 above |

### 8.2 `docs/24-gate-level-simulation.md`

The whole document reports a gate-level run against a netlist that no
longer corresponds to the RTL. It is not a matter of individual figures.

| Location | Current | Replacement | Source |
|---|---|---|---|
| Title and status, "the 6x2 submission netlist" | as written | **add**: reports `shape-6x2`, superseded by `wave6-6x2`; the suite has **not** been re-run at gate level on the current RTL | §9 above |
| §1.1 table, Path | `hw/openlane/pilot_ihp/runs/shape-6x2/final/nl/…` | **`tt/runs/wave6-6x2/final/nl/…`** | §1.5 above |
| §1.1 table, git blob | `e8f72bde4c5a02101a226f5d98bde36c1229c084` | **`70a359bef803d4ffc55f2ea7ac1cf2bcc9045087`** | §1.5 above |
| §1.1 table, Size | 2,570,202 bytes | **2,546,508 bytes** | §1.5 above |
| §1.1 table, Instances | 33,801 total; 12,418 standard cells, 21,383 fill/decap | **33,649 total; 12,234 standard cells, 21,415 fill, 3 antenna** | §2.1 above |
| §1.1 table, Sequential cells | **1,275** | **1,277** | §2.1 above |
| Headline, "a 33,801-instance netlist" | as written | **33,649** | §2.1 above |
| §8 open items | as written | **add**: the 20 gate-level tests and the per-test simulated-time equality are unverified on `wave6-6x2` | §9 above |

### 8.3 `docs/26-gate-level-fault-injection.md`

Same situation: a 522-injection campaign against a superseded netlist.

| Location | Current | Replacement | Source |
|---|---|---|---|
| Status and §1.1, the netlist | `shape-6x2` | **`wave6-6x2`**, blob `70a359be…` | §1.5 above |
| §1.1 table, Sequential cells | **1,275** | **1,277** | §2.1 above |
| Headline and §3.3/§5.4/§6, "**1,275** flip-flops", "1,170 of the 1,275 (91.8 %)", "**334** of the netlist's 1,275", "**26 %**" | as written | the denominator is **1,277**; the named-net and coverage fractions must be **re-derived**, not adjusted — the two added flip-flops are rail instances with `keep_hierarchy` names | §2.1, §7.2 above |
| §1.1, instance counts | 33,801 / 12,418 / 21,383 | **33,649 / 12,234 / 21,415 + 3 antenna cells** | §2.1 above |
| Headline, "The pointer TMR now has functional netlist evidence: 72 of 72 CORRECTED"; "configuration TMR … 165 CORRECTED" | as written | the **structural** evidence is refreshed here (§7.2); the **functional** injection evidence is not, and is unverified on `wave6-6x2` | §9 above |
| Whole document | — | **add**: no rail has ever been injected into at gate level, because no netlist on disk carried one until `wave6-6x2` | §9 above |

### 8.4 `docs/21-pilot-datasheet.md`

| Location | Current | Replacement | Source |
|---|---|---|---|
| §7.1 / §7.2 tables, "Mapped flip-flops **1275**" | as written | **1277 `sg13g2_dfrbpq_1`** | §2.1 above |
| §7.1 / §7.2, post-synthesis cell area **151,789.11 um2** | as written | **152,099.79 um2** | §2.1 above |
| §7.1 / §7.2, placed standard-cell area **185,840 um2** | as written | **185,595 um2** | §2.1 above |
| §7.1 / §7.2, utilization **47.2887 %** / 47.29 % | as written | **47.2266 %** | §2.1, §6 above |
| §7.2, total power **5.130 mW** and its 4.2402 / 0.8755 / 0.014350 breakdown | as written | **5.119 mW**; 4.2319 / 0.87233 / 0.014355 | §5 above |
| §7.1, worst setup slack **+1.2347 ns** (or the 4x2 figure if still quoted) | as written | **+0.3229 ns** on `nom_slow_1p08V_125C` | §3 above |
| §7.1, source paths `hw/openlane/pilot_ihp/runs/shape-6x2/…` | as written | **`tt/runs/wave6-6x2/…`** throughout | §1.4 above |
| §7.1, "the twelve pointer banks, 36 in total, out of 1,275" | as written | **out of 1,277**; **add** a row for the eight valid-flag rails at 1 each | §7.2 above |
| §7.1, verification status quoting the synthesis-guard file | as written | **26 passed, 0 skipped** | §7.1 above |
| §7.2, 6x2 spare **+32.44 %** | as written | **+32.53 %** | §6 above |

### 8.5 `docs/15-pilot-tile-plan.md`

| Location | Current | Replacement | Source |
|---|---|---|---|
| §4.1 and §4.5 tables, 6x2 column | 1,275 / 151,789.11 / 185,840 / 47.2887 % / 33,801 | **1,277 / 152,099.79 / 185,595 / 47.2266 % / 33,649** | §2.1 above |
| §4.5 and §14, "185,840 um2 the submission netlist places" | as written | **185,595 um2** | §2.1 above |
| Headline and §4, "measured utilization **47.29 % at 6x2**" | as written | **47.23 %** | §6 above |
| §4.5 table, 6x2 row spare **+32.44 %** | as written | **+32.53 %** | §6 above |

### 8.6 `docs/16-fault-injection-campaign.md`

| Location | Current | Replacement | Source |
|---|---|---|---|
| §5.9 / the "Also stale as a result of this change" note, "the same `hw/openlane/pilot_ihp/runs/shape-6x2/` netlist … now predates `hw/rtl/aer_fifo.v`" | as written | **closed**: `tt/runs/wave6-6x2` postdates it and the guard passes | §7 above |
| The mutation table's "1,277 -> 1,275" ASIC totals | as written | **confirmed against a real harden**, not only the census: synthesis reads **1,277** | §2.1, §7.2 above |
| Any wave-6 ranking resting on gate-level records | as written | those records are from `shape-6x2` and are **not** refreshed here | §9 above |

### 8.7 `docs/25-sky130-6x2.md`

| Location | Current | Replacement | Source |
|---|---|---|---|
| §2 table, ihp-sg13g2 comparison column | 1,275 / 9,821 / 151,789.11 / 12,418 / 33,801 / 185,840 / 47.2887 % / 469,914 / 5.1301 | **1,277 / 9,686 / 152,099.79 / 12,234 / 33,649 / 185,595 / 47.2266 % / 465,701 / 5.1186** | §2.1, §5 above |
| Whole document | — | **add**: the four sky130 6x2 hardens are pinned to the pre-wave-6 RTL and are now one wave old; the cross-PDK claim is **not** re-measured here | §1.3 above |

### 8.8 `hw/tb/**` — not documents, but they name the netlist

Covered in full by section 9.

---

## 9. What must be re-run at gate level, against this netlist

Nothing in `hw/tb/**` is edited here — it is outside this workstream's
ownership. This section states exactly what must be re-run, so it can be
scheduled as its own task rather than assumed.

**The netlist to run against is
`tt/runs/wave6-6x2/final/nl/tt_um_melihakbulut_nssoc.nl.v`**, blob
`70a359bef803d4ffc55f2ea7ac1cf2bcc9045087`.

Both gate-level makefiles resolve their netlist through two overridable
variables, so **no makefile edit is required to re-run** — but the
default in each is wrong now, because it names the wrong tag *and* the
wrong tree:

```make
GL_TAG ?= shape-6x2
GL_RUN ?= $(REPO)/hw/openlane/pilot_ihp/runs/$(GL_TAG)
```

`wave6-6x2` lives in `tt/runs/`, so overriding `GL_TAG` alone is **not**
sufficient; `GL_RUN` must be set:

```bash
make -f hw/tb/Makefile.gl   GL_RUN=$PWD/tt/runs/wave6-6x2 sim
make -f hw/tb/Makefile.glfi GL_RUN=$PWD/tt/runs/wave6-6x2 sim
```

`GL_PDK_ROOT`, `GL_PDK`, `GL_SCL` and `GL_CELLS` are all derived from
the run's own `resolved.json`, so they follow `GL_RUN` automatically and
need no override **[fact, `hw/tb/Makefile.gl` section 2]**.

| File | Why it must re-run | Owner action |
|---|---|---|
| `hw/tb/Makefile.gl` | `GL_TAG` / `GL_RUN` default to the superseded netlist in a tree `wave6-6x2` is not in | re-point the default, or always pass `GL_RUN` |
| `hw/tb/test_pilot_gl.py` | `docs/24`'s 20 gate-level tests and their per-test simulated-time equality are unverified on this netlist | re-run |
| `hw/tb/Makefile.glfi` | same default problem | re-point the default, or always pass `GL_RUN` |
| `hw/tb/test_gl_fi.py` | the 522-injection campaign targeted `shape-6x2`; line 189 names the `e1361fe` pin in a comment | re-run; re-pin the comment to `2c6c052` |
| `hw/tb/gl_fi_results.json` | records `"netlist": ".../shape-6x2/final/nl/..."` | regenerate |
| `hw/tb/gl_fi_results_disagreement.json` | same | regenerate |
| `hw/tb/sim_build_gl_shape-6x2/`, `hw/tb/sim_build_glfi_shape-6x2/` | compiled against the superseded netlist | rebuild under new tag names; both already gitignored |

**Four substantive things change for that task, not just a path:**

1. **The injector's target map grows.** `docs/26` builds its map from
   the nets a `sg13g2_dfrbpq_1` `Q` pin drives and found 1,275; this
   netlist has **1,277**, so the coverage fractions must be re-derived
   rather than adjusted.
2. **Eight rail flip-flops are injectable and never have been.**
   `docs/16` sections 5.7 and 5.11 rank the valid-flag class as the
   design's worst remaining silent-corruption source. No netlist
   campaign has ever injected into a rail, because no netlist on disk
   carried one. This is the highest-value new coverage available.
3. **Three antenna diodes are in the netlist** that were not in
   `shape-6x2`. They are not sequential and do not enter the target map,
   but any instance-count assertion in the harness will see 33,649
   instead of 33,801.
4. **The two flip-flops the timeout retirement removed are gone**, so
   any injection target list carried forward from `docs/26` by name may
   reference flip-flops that no longer exist.

---

## 10. What is not done

1. **The `~/.local/opt/llbin/yosys` fallback still names a sibling
   project's checkout** (section 1.1). It is not on this flow's path and
   no number here came through it, but it is the same shape of hazard
   `tools.mk` was written for. The shim is outside this repository, so
   closing it is a decision for whoever owns `scripts/harden_local.sh`
   in the `gt2n-soc` tree.
2. **The slow-corner margin loss is measured but not attributed**
   (section 3.1). Which path, and whether the cause is the rails, the
   timeout retirement, or placement noise, needs the slow-corner
   `violator_list.rpt` from both runs and a path-level comparison. At
   1.61 % of the cycle this should be understood before another RTL
   wave, and it is the most useful next piece of physical-design work.
3. **The eight valid-flag rails have no real-flow guard** (section 7.3).
   They are counted by hand here. A third
   `*_survives_the_real_hardening_flow` test would close it;
   `sw/tests/**` is not this workstream's file.
4. **Gate-level simulation and gate-level fault injection are not
   re-run** (section 9). This is the largest open item and is stated as
   a schedulable task rather than attempted here.
5. **No sky130 companion run at this RTL.** `docs/25`'s four 6x2 hardens
   are pre-wave-6, so the cross-PDK claim is one wave old.
6. **No power analysis with annotated activity** (section 5), as
   `docs/22` open item 6 and `docs/23` section 3.3 already record.
7. **No 3x4 companion at this RTL.** `docs/23`'s shape comparison is not
   re-measured; the shape decision does not depend on it, since section 6
   shows 32 points of margin.

---

## 11. Reproducing this

```bash
make -f tools.mk toolcheck

# Pin the RTL and rewrite the config to read the snapshot by absolute path.
python3 hw/openlane/pin_rtl.py 2c6c052 \
    hw/openlane/pilot_ihp/config.6x2.json /tmp/pin-ihp-6x2-w6

# Harden. --force-run-dir is a LibreLane 3.0.5 option; the run MUST land
# in tt/runs/ for sw/tests/test_synthesis_guards.py to see it (section 1.4).
mkdir -p tt/runs/wave6-6x2
CONFIG=/tmp/pin-ihp-6x2-w6/config.json \
  hw/openlane/pilot_ihp/run_ihp.sh \
    --run-tag wave6-6x2 --force-run-dir $PWD/tt/runs/wave6-6x2

# The sign-off set and the routing trace, both runs read the same way.
python3 hw/openlane/signoff_report.py \
    tt/runs/wave6-6x2 \
    hw/openlane/pilot_ihp/runs/shape-6x2
python3 hw/openlane/route_trace.py \
    tt/runs/wave6-6x2 \
    hw/openlane/pilot_ihp/runs/shape-6x2

# The guards. 26 passed, 0 skipped.
.venv/bin/python -m pytest sw/tests/test_synthesis_guards.py -q
```

The `pin_rtl.py` snapshot is disposable and regenerable from `2c6c052`;
the blob list in section 1.2 is the record. `tt/runs/` is gitignored, so
the run directory is not committed and every figure above is quoted with
the step directory it came from.
