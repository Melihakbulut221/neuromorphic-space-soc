# 20 — Re-harden after the TMR fix, and what the slow corner actually costs

Status: complete for the runs it reports; two follow-ups named in
section 9 are not run. Supersedes specific figures in `docs/15` and
`docs/18` — the exact list, with replacement numbers, is section 8.
Neither of those documents is edited here.

**Superseded in turn, 2026-08-29 — read this before quoting any area,
utilization, flip-flop or slack figure below.** This document reports
the `tmr-reharden` run of 2026-08-26, which hardened the netlist after
the configuration-TMR fix (`e45d52d`) and *before* two later rounds of
hardening: the `lif_core` memory ECC of 2026-08-27 and the AER pointer
TMR of 2026-08-29 (`c5a5a6e`). Every physical figure in the Headline and
in section 2 therefore describes a netlist that no longer exists —
including the 60.91 % utilization, the 158,268 um2 of placed cells, the
1,155 flip-flops, the +6.436 ns slow-corner slack, and the "4x2 still
fits, with 13.0 % of the core spare" conclusion drawn from them.

`docs/22-reharden-wave5.md` is the document that re-hardens the current
netlist and its **section 6.3 is a location-by-location correction list
for this document** — each row naming what this document says, what
replaces it, and which artifact the replacement was read from.

**Amended 2026-08-30: the replacement figures are now restated here.**
The reason this note originally withheld them no longer holds —
`tt/runs/wave5-ihp-b/` was still executing when it was written, and it
has since completed and is `docs/22` section 9. A second round has
landed on top of it: `docs/23-tile-shape-decision.md` hardened both
twelve-tile shapes and **moved the submission from 4x2 to 6x2**, so the
`docs/22` section 6.3 rows that correct a 4x2 figure toward another 4x2
figure are applied below *and* carried forward to the shape actually
being submitted. Each correction is placed beside the text it replaces,
with its source. Where `docs/22` section 6.3 (written at `c5a5a6e`) and
its section 9.5 (`0448282`) differ, section 9.5 is used and both values
are shown.

The *findings* of this document are not withdrawn and do not depend on
the superseded numbers: `PNR_CORNERS` does not close the sky130 slow
corner and cannot, post-global-routing repair does not close it either,
and the cause is a parasitic-model gap rather than a corner list
(sections 4 to 7). Those conclusions are about the flow, not about a
particular netlist's area. The sky130 side has its own separate problem
as of 2026-08-29 — the 4x2 no longer routes at all — which is
`docs/22` section 5, not this document.

Two jobs, both consequences of commit `e45d52d`:

1. **Re-harden.** Every area and timing figure in `docs/15` predates the
   configuration-TMR synthesis fix. `docs/15` section 4.5 says so and
   asks for this run. Section 2 is the result.
2. **The slow corner.** `docs/18` established that the sky130 harden
   closes DRC, LVS and antenna cleanly but misses the slow corner by
   3.85 ns, and named `PNR_CORNERS` as the untested fix. Sections 4
   to 7 test that. It does not work, and the reason it cannot work is
   more interesting than the failure.

### Headline

- **The IHP re-harden is clean.** 1,155 flip-flops, 158,268 um2 of
  placed cells, 60.91 % utilization, 0 route DRC, 0 Magic DRC, 0 Netgen
  LVS, 0 antenna violations, and **+6.436 ns** on the slow corner — 1.12
  ns *better* than the run it supersedes, despite being 16.3 % larger.
- **4x2 still fits, with 13.0 % of the core spare** beyond the `docs/15`
  70 % planning criterion, down from 25.2 % before the fix.

> *Both bullets superseded 2026-08-30.* The sign-off bullet reads
> **1,275 flip-flops, 185,755 um2 of placed cells, 71.4890 %
> utilization, +0.9121 ns** on the slow corner for the current RTL at
> 4x2, with the same zeros on every deck **[fact, `docs/22` sections 9.3
> and 9.5; `docs/22` section 6.3 gives the intermediate `c5a5a6e`
> figures 1,268 / 184,969 um2 / 71.1867 % / +1.1554 ns]**. **The
> "4x2 still fits, with 13.0 % of the core spare" bullet is retracted**:
> at the same criterion the design is **over budget by 5,527 um2,
> -2.13 % of the core**, and the spare series runs 25.2 % → 13.0 % →
> 0.68 % → 0.46 % → -1.70 % → **-2.13 %** **[fact for the placed areas
> and utilizations; the criterion arithmetic is an estimate on them]**.
> The submission has since moved to **6x2 = 12 tiles**, where the same
> netlist places 185,840 um2 at **47.2887 %** with **+127,502 um2**
> spare and closes the slow corner at **+1.2347 ns** **[fact, `docs/23`
> sections 2.1, 2.2 and 3.1]**.
- **`docs/15`'s "roughly 3 % low" note is itself wrong.** The measured
  growth is +16.3 % placed, +17.5 % at synthesis, and section 3
  decomposes it: about half is the TMR fix, about half is the
  `deferred_flatten` the fix forces.
- **`PNR_CORNERS` does not close the sky130 slow corner and cannot.** It
  made it 0.382 ns *worse*, at zero area cost. It governs no step in
  this configuration that optimises timing, and the layouts through
  global routing are byte-identical with and without it.
- **Post-global-routing repair does not close it either** (-3.176 ns),
  though it removes 42 % of the total negative slack for no area.
- **The real cause is a parasitic-model gap**, not a corner list: the
  PnR wire estimate is ~2.7 ns of WNS more optimistic than the OpenRCX
  extraction the sign-off uses, and only 0.56 ns of the miss is a
  genuine interconnect-corner effect. Section 6.2.
- **On IHP `PNR_CORNERS` changes literally nothing** — byte-identical
  layout and slack. Do not set it.

---

## 1. What was run, and against which sources

### 1.1 Toolchain

```
$ make -f tools.mk toolcheck
OSS_CAD_SUITE = /home/hasanmelih/Downloads/oss-cad-suite-linux-x64-20260804/oss-cad-suite
yosys version = 0.67+146 (pinned 0.67+146)
```

The hardening flow is the rootless LibreLane of `docs/12` section 2.1,
unchanged:

| Component | Version | Where it is pinned |
|---|---|---|
| LibreLane | 3.0.5 | `~/Documents/caravel-lif-crossbar/.venv-flow` |
| Yosys (in-flow) | 0.67 | LibreLane wheel |
| ihp-sg13g2 PDK | `c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c` | LibreLane `pdk_hashes.yaml`, asserted by the run script |
| sky130A PDK | `8afc8346a57fe1ab7934ba5a6056ea8b43078e71` | same |
| Magic | 8.3.678 | `~/.local/opt/magic-8.3.678` |

**[fact]** for every row; the PDK hashes are read out of the installed
wheel by `run_ihp.sh` / `run_sky130.sh` rather than hard-coded, so a
LibreLane upgrade cannot silently change them.

### 1.2 Sources, and a mid-run RTL edit

`docs/18` set the precedent that a run must be able to name the source
it consumed. That precedent earned its keep during this work.

Every run reported here synthesised the `hw/rtl` tree at commit
`fe89f0d`:

```
ac6edac5cb5e759359afe765c0c2f0f56c70acf6  hw/rtl/aer_fifo.v
460634409bf09d137d805bda0b5f775d7a96ff3b  hw/rtl/lif_core.v
9aaaa394e7a6ef855f5584fb85d53e688ac3e0b5  hw/rtl/npu_regs.vh
033eb1d6d3b119f9f41440c6e933c2df78b8a1b3  hw/rtl/pilot_top.v
f7c7ec187a0df4eb09a8405dcda285de0fc2e44e  hw/rtl/secded_dec.v
b5710b8a679c3e378e74953b621b99f0d8dc3014  hw/rtl/secded_enc.v
62b5f4d2a1eae095d9d4a8634ede55237e2c924d  hw/rtl/tmr_voter.v
e294afcf03e1947906086beeba2fd0c40b29441d  hw/rtl/tt_um_melihakbulut_nssoc.v
```

**[fact, `git hash-object`]**. `tt/src/*.v` carried the same eight blobs
at the time of the IHP re-harden, so the submission copies and `hw/rtl`
were not merely equivalent but identical.

**At 07:15:28 a concurrent session rewrote `hw/rtl/lif_core.v`**
(blob `4606344` → `2450904`) while the post-GRT experiment of section 6
was between its lint step and its synthesis step. The result:

| Time | Event |
|---|---|
| 07:15:10 | `01-verilator-lint` completes, **0 errors** |
| 07:15:28 | `hw/rtl/lif_core.v` rewritten by another session |
| 07:15:35 | `06-yosys-synthesis` starts, reads the **new** file |
| 07:15:4x | `08-checker-yosyssynthchecks` aborts: 4 undriven wires (`wmem_sec`, `wmem_ded`, `state_sec`, `state_ded`) — ECC logic that was not written yet |

**[fact, `pre_synth_chk.rpt` and the step directory mtimes]**. That run
was discarded. Lint and synthesis are separate processes reading the
same path, so *any* config that names `hw/rtl` has this window on every
run, and the run directory records no evidence of which version it read.

`hw/openlane/pin_rtl.py` closes the window: it materialises a named
commit's `hw/rtl` into a scratch directory, rewrites a config to read
from there by absolute path, and prints the blob of every file it wrote.
Every run from `sky-06` onward is pinned that way. The three runs that
had already started (`sky-04`, `sky-05`, `ihp-pnrcorners`) synthesised
at 06:34, 07:06 and 07:08, all before the edit, and all three report
**0 undriven wires** in `pre_synth_chk.rpt` **[fact]** — they are clean,
and their netlists match the pinned ones cell for cell.

### 1.3 The runs

| Tag | PDK | Config | Delta against baseline | Section |
|---|---|---|---|---|
| `tt-harden` | ihp-sg13g2 | `tt/src/config_merged.json` | the `docs/15` run, **superseded** | 2 |
| `tmr-reharden` | ihp-sg13g2 | same, + `SYNTH_HIERARCHY_MODE: deferred_flatten` | the re-harden | 2 |
| `sky-02-signoff` | sky130A | `pilot_sky130/config.json` | the `docs/18` run, **superseded** | 4 |
| `sky-04-tmr` | sky130A | same | post-fix sky130 baseline | 4 |
| `sky-05-pnrcorners` | sky130A | `+ PNR_CORNERS` | the `docs/18` hypothesis | 5 |
| `sky-06-postgrt` | sky130A | `+ PNR_CORNERS + post-GRT repair` | the follow-on hypothesis | 6 |
| `sky-07-repeat` | sky130A | `pilot_sky130/config.json`, RTL pinned | run-to-run control | 5.3 |
| `ihp-pnrcorners` | ihp-sg13g2 | `pilot_ihp/config.pnrcorners.json` | `PNR_CORNERS` on IHP | 7 |
| `ihp-synth-*` | ihp-sg13g2 | synthesis-only probes | area decomposition | 3 |

Variant configs are **generated**, not hand-copied
(`hw/openlane/pilot_sky130/mkvariant.py`,
`hw/openlane/pilot_ihp/mkconfig.py`), so that the named key delta is the
only thing that can differ between a baseline and its variant. Every
number quoted below is extracted by `hw/openlane/signoff_report.py`
rather than by hand-grep, so that two runs being compared are read the
same way.

---

## 2. The re-hardened IHP sign-off

`tt/runs/tmr-reharden`, ihp-sg13g2, 4x2 tile
(854.40 x 313.74 um), `CLOCK_PERIOD: 20`, the submission's own
`src/config_merged.json` — the configuration the Tiny Tapeout GDS action
would use. **[fact, `tt/runs/tmr-reharden/final/metrics.json`]**

`SYNTH_HIERARCHY_MODE: deferred_flatten` is required and is not
cosmetic; section 3.3 measures what it buys and what it costs.

### 2.1 Sign-off table, beside the superseded one

| Quantity | `docs/15` §4.1/4.6 (`tt-harden`) — **superseded** | Re-harden (`tmr-reharden`) | Delta |
|---|---|---|---|
| Mapped flip-flops | 1,037 | **1,155** | +118 |
| Synthesis cells | 6,587 | **7,791** | +18.3 % |
| Synthesis cell area | 107,782 um2 | **126,647 um2** | +17.5 % |
| Placed cells, excl. fill | 8,687 | **10,164** | +17.0 % |
| Instances incl. fill | 22,552 | 22,940 | +1.7 % |
| **Placed cell area** | 136,107 um2 | **158,268 um2** | **+16.3 %** |
| of which sequential | 50,801 um2 | 56,582 um2 | +11.4 % |
| of which timing-repair buffers | 25,494 um2 (1,954 cells) | 28,181 um2 (2,213 cells) | +10.5 % |
| of which clock buffers and inverters | 2,814 um2 | 3,422 um2 | +21.6 % |
| Die area | 268,059 um2 | 268,059 um2 | fixed by the tile |
| Core area | 259,837 um2 | 259,837 um2 | fixed by the tile |
| **Utilization** | 52.38 % | **60.91 %** | +8.53 pts |
| Routed wirelength | 335,406 um | 386,429 um | +15.2 % |
| Route (TritonRoute) DRC | 0 | **0** | — |
| **Magic DRC** | 0 | **0** | — |
| **KLayout DRC** | not run | **not run** | see 2.3 |
| **Netgen LVS** | 0 | **0** | — |
| LVS unmatched nets / devices / pins / properties | 0 / 0 / 0 / 0 | **0 / 0 / 0 / 0** | — |
| **Antenna-violating nets** | 0 | **0** | — |
| Antenna diodes inserted | 0 | **0** | — |
| Power-grid violations | 0 | **0** | — |
| Disconnected pins | 6 | 6 | the 6 unused TT wrapper inputs |
| Max-fanout counter | 72 | 77 | not gated; see `docs/15` §5.3 |
| `design__violations` | 0 | **0** | — |
| `flow__errors__count` | 0 | **0** | — |
| Worst IR drop, VPWR | 0.64 mV | 0.489 mV (0.04 %) | — |
| Summed step runtime | not comparable | 36.3 min | see below |

**Superseded 2026-08-30, column by column, and the table above is kept
as the `tmr-reharden` record.** Two hardening rounds and one shape
change have landed since. The replacement column for the current RTL at
4x2 is `wave5-ihp-b` (`docs/22` section 9.3); the column that describes
what is being submitted is `shape-6x2` (`docs/23` sections 2.1, 3.3
and 4.4):

| Quantity | `tmr-reharden` (above) | `wave5-ihp-b`, 4x2 at `0448282` | **`shape-6x2`, submitted** |
|---|---|---|---|
| Mapped flip-flops | 1,155 | **1,275** | **1,275** |
| Synthesis cells | 7,791 | **9,821** | **9,821** |
| Synthesis cell area | 126,647 um2 | **151,789.11 um2** | **151,789.11 um2** |
| Placed cells, excl. fill | 10,164 | **12,424** | **12,418** |
| Instances incl. fill | 22,940 | **23,685** | **33,801** |
| **Placed cell area** | 158,268 um2 | **185,755 um2** | **185,840 um2** |
| of which sequential | 56,582 um2 | **62,460.7 um2** | not quoted in the source |
| of which timing-repair buffers | 28,181 um2 (2,213) | **30,111.8 um2 (2,414)** | **(2,430 cells)** |
| of which clock buffers | 3,422 um2 | **3,365.71 um2** | not quoted in the source |
| Die area | 268,059 um2 | **268,059 um2** | **404,499 um2** |
| Core area | 259,837 um2 | **259,837 um2** | **392,988 um2** |
| **Utilization** | 60.91 % | **71.4890 %** | **47.2887 %** |
| Routed wirelength | 386,429 um | **480,088 um** | **469,914 um** |
| Route (TritonRoute) DRC | 0 | **0** | **0** |
| **Magic DRC** | 0 | **0** | **0** |
| **KLayout DRC** | not run | not re-run at `0448282`; **0** at `c5a5a6e` (§2.3) | **0** |
| **Netgen LVS**, all seven counters | 0 | **0** | **0** |
| **Antenna-violating nets / pins** | 0 / 0 | **0 / 0** | **0 / 0** |
| Antenna diodes inserted | 0 | **6** | **0** |
| Unmapped instances | 0 | **0** | **0** |
| Power-grid violations | 0 | **0** | **0** |
| Disconnected pins | 6 | **6** | not quoted in the source |
| Max-fanout counter | 77 | **85** | not quoted in the source |
| `design__violations` / `flow__errors__count` | 0 / 0 | **0 / 0** | **0 / 0** |
| Worst IR drop, VPWR | 0.489 mV | **1.277 mV** | **0.616 mV** |
| Total power, 50 MHz typical | not quoted | **5.191 mW** | **5.130 mW** |

**[fact, `docs/22` sections 9.3 and 9.5 and `docs/23` sections 2.1, 3.3
and 4.4.]** Four cells are left empty rather than filled by inference:
`docs/23` reports the repair-buffer *count* but not its area, and does
not break out clock-buffer or sequential area, the disconnected-pin
count or the max-fanout counter for the 6x2 run. The IR figures remain
indicative on every column — no `VSRC_LOC_FILES` — and the power figures
are the flow's own estimates from default switching activity, not
annotated-activity measurements.

Two readings worth keeping. The instance count including fill rises to
33,801 at 6x2 because the larger core is filled with decap and tap
cells, which is **not** design growth; and the placed cell area differs
between the two shapes by 85 um2, 0.05 %, because **only the denominator
changes** — synthesis is identical to the cell, since a floorplan input
cannot reach Yosys **[fact, `docs/23` section 2.1]**.

Runtime is deliberately not given a delta. `tt/runs/tt-harden` was
pruned from 553 MB to the artefacts `docs/15` cites, and 4 of its 34
surviving step directories still carry a `runtime.txt` **[fact]** — any
sum over it is an undercount of unknown size. Section 5.4 shows
separately that on this machine wall-clock is dominated by concurrency
rather than by work.

Manufacturability report: **Antenna Passed, LVS Passed, DRC Passed** —
three `Passed` lines, matching the `docs/12` §4.1 bar. **[fact,
`72-misc-reportmanufacturability`]**

On the flip-flop count: the RTL declares **1,161** (`docs/16` §7.4 and
`sw/tests/test_synthesis_guards.py`) and the mapped netlist carries
**1,155**, all `sg13g2_dfrbpq_1`. The six-flop gap is ordinary synthesis
optimisation of declared-but-constant or unused state and it is the same
kind of gap the pre-fix run had (1,161 declared, 110 merged, 1,037
mapped). The number that matters is that **all three 55-bit replicas are
present**: 1,155 - 1,045 = 110, exactly the two banks the merge used to
eat.

*Extended 2026-08-30, not corrected.* That account of the configuration
domain still holds, and the census has since been repeated on the
shipped netlist: **55 flip-flops under each of `u_cfg_a`, `u_cfg_b` and
`u_cfg_c`**. Two increments sit on top of it. The AER pointer TMR adds
**+24** — twelve pointer banks at **3** flip-flops each, 36 in total,
where the four queue pointers previously held 6 flip-flops per queue —
and the `lif_core` ECC status ports add **+9** in `pilot_top`'s own
scope, taking the count to 1,268 at `c5a5a6e`; the `0448282` deadlock
fix then adds the **+7** its commit message predicts, for **1,275**
**[fact, `docs/22` sections 2.2, 3, 9.2 and 9.3, counted by instance
path in the final netlists]**. Both replicated domains are now witnessed
in a shipped artefact by
`sw/tests/test_synthesis_guards.py`, which no longer skips.

### 2.2 Timing, three corners, post-route with OpenRCX parasitics

| Corner | `docs/15` §4.6 — **superseded** | Re-harden | Delta |
|---|---|---|---|
| `nom_slow_1p08V_125C` | +5.314 ns | **+6.436 ns** | **+1.122 ns** |
| `nom_typ_1p20V_25C` | +10.699 ns | **+11.423 ns** | +0.724 ns |
| `nom_fast_1p32V_m40C` | +13.846 ns | **+14.167 ns** | +0.321 ns |

Setup violations 0, hold violations 0, max-cap violations 0, max-slew
violations 0, on all three corners. Worst hold slack +0.646 ns on the
slow corner, +0.119 ns on the fast corner. **[fact,
`55-openroad-stapostpnr/summary.rpt`]**

**The re-hardened design is 1.12 ns *faster* on the slow corner than the
one it replaces, despite being 16.3 % larger.** That is worth stating
plainly because it is the opposite of the intuitive result. +6.436 ns of
slack at a 20 ns period is a 13.56 ns critical path and a post-route
slow-corner Fmax of about **73.7 MHz**, against `docs/15`'s 68.1 MHz.

**Superseded 2026-08-30.** The table above is `tmr-reharden` and is not
withdrawn; the corner figures for the current RTL are:

| Corner | `tmr-reharden` (above) | `wave5-ihp-b`, 4x2 at `0448282` | **`shape-6x2`, submitted** |
|---|---|---|---|
| `nom_slow_1p08V_125C` | +6.436 ns | **+0.9121 ns** | **+1.2347 ns** |
| `nom_typ_1p20V_25C` | +11.423 ns | **+7.8999 ns** | **+8.1297 ns** |
| `nom_fast_1p32V_m40C` | +14.167 ns | **+11.9855 ns** | **+12.1329 ns** |
| Worst hold, slow / fast | +0.646 / +0.119 ns | **+0.6218 / +0.1180 ns** | **+0.6039 / +0.1089 ns** |
| Setup / hold / max-cap / max-slew violations, all corners | 0 | **0** | **0** |

**[fact, `docs/22` sections 9.3 and 9.5 and `docs/23` section 3.1;
`docs/22` section 6.3 gives the intermediate `c5a5a6e` figures
+1.1554 / +8.0521 / +12.1355.]** Read as frequency, the slow-corner
Fmax is **52.4 MHz** at 4x2 and **53.3 MHz** at 6x2, not the 73.7 MHz
above **[estimate, arithmetic on a measured slack]**. The mechanism
paragraph below survives all of it, and has since been generalised: the
pointer TMR also closed *better* than the run it replaced. `docs/22`
section 2.3 states the rule — **on this design, netlist size does not
predict slack in either direction** — which is a caution against sizing
a future increment's timing from its area delta, in either direction.

The mechanism is visible in the netlist: before the fix, one merged
55-bit bank fanned out to all three voter inputs, so the voter's inputs
came from a single, heavily loaded driver set. Three real banks give
three independent drivers, each with a third of the load. The TMR fix
was made for correctness and it happens to have been free — better than
free — in timing. **[estimate on the mechanism; the slack numbers are
fact]**

### 2.3 What is *not* in this sign-off

**KLayout DRC did not run**, exactly as in `docs/15` §5.3, because the
Tiny Tapeout config sets `RUN_KLAYOUT_DRC: 0` and `RUN_KLAYOUT_XOR: 0`
under the comment "Save some time". Running the re-harden against the
submission config byte-for-byte was the higher priority — this is the
run that stands in for the GDS action — so the KLayout deck was left
off rather than the config forked. The sky130 runs of sections 4 to 6 do
run both decks and both report 0, so the deck is not untested on this
design, only untested *on this PDK*. Closing it properly is a named
follow-up (section 9).

*Closed 2026-08-30.* KLayout DRC has now run on the IHP tile and reports
**0**, twice. First on `ihp-klayoutdrc-w5`, a variant config differing
from the submission config in that one key, at `c5a5a6e` — which also
served as a reproducibility control, reproducing every other figure of
that run to the last digit **[fact, `docs/22` section 2.4]**. Then on
the 6x2 submission-shape run, whose config carries `RUN_KLAYOUT_DRC: 1`
outright so that one run per shape yields the whole sign-off set
**[fact, `docs/23` section 1.3 and
`hw/openlane/pilot_ihp/runs/shape-6x2/final/metrics.json`]**. The deck
was **not** re-run at `0448282` on 4x2, and `docs/22` open item 7 says
so. `RUN_KLAYOUT_XOR` is still 0 on IHP: not run, not claimed.

Also absent, unchanged from `docs/15` §5.3 and `docs/18` §7: no
signal-integrity analysis, no `VSRC_LOC_FILES` so the IR numbers are
indicative, and `Yosys.EQY` is gated off, so there is no formal
equivalence check between RTL and final netlist.

### 2.4 Does it still fit 4x2, and with how much margin

**Yes, and the flow closed it — this is a measurement, not a model.**

| Quantity | Value |
|---|---|
| 4x2 die | 854.40 x 313.74 um = 268,059 um2 |
| 4x2 core (inside the tile's margins) | 259,837 um2 |
| Placed cell area | 158,268 um2 |
| **Achieved utilization** | **60.91 %** |
| Free core area | 101,569 um2 (39.09 %) |

Two ways to read the margin, both worth having:

- **As the flow ran it.** 60.91 % against `PL_TARGET_DENSITY_PCT: 60`.
  The design is 1.5 % denser than the placer's own target and still
  closed with 0 route DRC, 0 antenna violations and 6.44 ns of setup
  slack on the slow corner. Not tight.
- **Against the `docs/15` §4.5 planning criterion of 70 %.** The design
  now needs 158,268 / 0.70 = **226,097 um2** of core; 4x2 provides
  259,837 um2. That is **13.0 % of the core area spare** beyond the
  criterion, and the design consumes **87.0 %** of the budget the
  criterion allows.

Before the fix the same calculation gave 194,439 um2 needed against
259,837 available — 74.8 % of the budget. **So the fix spent about half
the planning headroom: 25.2 % spare became 13.0 % spare.** The decision
does not change — 226,097 um2 does not fit 3x2's 193,261 um2 either, so
4x2 was and remains the minimum shape for this content — but the row
below it in the `docs/15` table is now much closer than it reads. The
8 x 16 row (128 synapses) modelled at 230,588 um2 pre-fix; scaled by the
measured +16.3 % it lands near 268,000 um2, i.e. **above** the 4x2 core.
That row should be treated as 6-tile until someone hardens it.
**[estimate — scaled model, not a run]**

> **Superseded 2026-08-30. The whole of this fit calculation, and the
> decision it draws.** The section is kept because it is the record of
> where the margin went, one increment at a time.
>
> | Quantity | §2.4 above (`tmr-reharden`) | `wave5-ihp-b`, 4x2 | **`shape-6x2`, submitted** |
> |---|---|---|---|
> | Placed cell area | 158,268 um2 | **185,755 um2** | **185,840 um2** |
> | Core offered | 259,837 um2 | **259,837 um2** | **392,988 um2** |
> | Core needed at the 70 % criterion | 226,097 um2 | **265,364 um2** | **265,486 um2** |
> | Spare against the criterion | +33,740 um2 (**+13.0 %**) | **-5,527 um2 (-2.13 %)** | **+127,502 um2 (+32.44 %)** |
> | Budget consumed | 87.0 % | **102.13 %** | **67.6 %** |
>
> **[fact for the placed areas and cores, `docs/22` section 9.4 and
> `docs/23` section 2.2; the criterion arithmetic is an estimate on
> measured areas.]**
>
> **"The decision does not change — 4x2 was and remains the minimum
> shape" is retracted.** It changed twice. First the design went over
> the criterion at 4x2 — while still *closing* the tile physically, with
> 0 DRC on every deck, which `docs/22` section 4.2 keeps carefully apart
> from the planning failure. Then `docs/23` hardened 6x2 and 3x4 end to
> end and moved the submission to **6x2**, and it did **not** decide on
> area: both twelve-tile shapes clear the criterion by more than thirty
> points, so utilization stopped being the discriminator. 6x2 won on
> **routing convergence** (one detailed-route pass of five iterations
> against 3x4's two passes of eleven), **antenna** (zero diodes against
> one), **timing** (no violation against 3x4's one 6.27 ps hold
> violation) and **clock skew** — the near-square die gives the clock
> tree a longer reach, and 3x4's worst hold skew is 65 % larger than
> 6x2's on the same netlist **[fact, `docs/23` sections 3.1, 3.2, 4.3
> and 4.4]**. Cost: **EUR 840, +EUR 280** against the 8-tile line.
>
> The 8 x 16 row estimate is superseded too. At the current growth factor
> of +36.5 % it needs about **314,701 um2** of rows **[estimate,
> `docs/22` section 9.5]**. "6-tile" was wrong in the direction this
> paragraph already suspected: it is a **12-tile** row.

---

## 3. Where the 16.3 % went

`docs/15` §4.5's superseding note predicts "about 2.9 % more" cell area
and says to treat the table as "roughly 3 % low". **The measured
increase is 16.3 % in placed cell area and 17.5 % in synthesis cell
area.** That note is itself superseded, and this section is why.

The 2.9 % figure is not wrong about what it measured — it is the
flip-flop-count effect alone, measured on a local Yosys 0.33 flat
synthesis. It omits two other terms that the real flow pays.

### 3.1 The decomposition

Four synthesis-only runs, same flow, same PDK, same `SYNTH_STRATEGY`
(`AREA 0`), varying one thing at a time. Only `SYNTH_HIERARCHY_MODE`
and the RTL commit differ; the resolved configs are otherwise identical
key-for-key **[fact, diffed]**.

| Point | RTL | `SYNTH_HIERARCHY_MODE` | Flops | Cells | Cell area |
|---|---|---|---|---|---|
| A | `be6ebd9` (the `docs/15` harden) | `flatten` | 1,037 | 6,587 | **107,782 um2** |
| B | `be6ebd9` | `deferred_flatten` | 1,038 | 7,088 | 116,369 um2 |
| C | `b2154b4` (last commit before the fix) | `deferred_flatten` | 1,045 | 7,102 | 116,926 um2 |
| D | `fe89f0d` (current) | `deferred_flatten` | 1,155 | 7,791 | **126,647 um2** |
| D′ | `fe89f0d` | `flatten` | 1,155 | 7,847 | 124,724 um2 |

**[fact]**, all five. A and D are the two hardened runs; B, C and D′ are
`-T Yosys.Synthesis` probes.

Reading A → D, the +17.5 % decomposes as:

| Term | Delta | Share of the +17.5 % |
|---|---|---|
| A → B: the **flow** change, `flatten` → `deferred_flatten` | +7.97 % | 46 % |
| B → C: wave-3 RTL churn unrelated to TMR | +0.48 % | 3 % |
| C → D: the **TMR fix** itself | +8.31 % | 48 % |

So roughly half the growth is the fix and half is the flow setting the
fix forces. `docs/15`'s 2.9 % accounts for neither: it is the
flip-flop-area term (110 flops x ~49 um2 = ~5,390 um2, about 5 % of the
old total) measured on a tool and a hierarchy mode that the submission
no longer uses.

The `deferred_flatten` penalty has a plain cause. LibreLane implements it
as a *second* synthesis: it maps hierarchically, writes the netlist, then
re-reads that **mapped** netlist and runs `synth -flatten` over it again
**[fact, `librelane/scripts/pyosys/synthesize.py:521-535`]**. The second
pass has lost the RTL-level structure the first pass had, so ABC does
worse. On RTL with no `keep_hierarchy` at all (point B) that costs 8 %.
On the current RTL the D vs D′ gap is only 1.5 %, because `flatten`
cannot flatten the protected banks either and is itself partly
hierarchical.

### 3.2 `deferred_flatten` is required — verified, not assumed

With `SYNTH_HIERARCHY_MODE: flatten` on the current RTL, synthesis
succeeds but the netlist carries three `$paramod$…\pilot_cfg_bank`
module types. The submission cannot ship that: it is what
`Checker.YosysUnmappedCells` exists to catch, and it is the documented
failure mode of the Tiny Tapeout GDS action ("Unmapped Yosys
instances"). Point D′ above is a `-T Yosys.Synthesis` probe precisely
because the flow cannot be taken further with that setting.

Note that this reverses a claim in `docs/15` §4.2, which argues at
length that this project should **not** carry the sibling project's
`deferred_flatten` workaround because "this project has no
`keep_hierarchy` attribute anywhere in `hw/rtl`". That was true when
written and stopped being true at `e45d52d`, which added exactly that
attribute. See section 8.

### 3.3 The `keep_hierarchy` attribute is load-bearing, and POL is not

`hw/rtl/pilot_top.v` documents two independent defences against the
replica merge and says POL — per-replica storage polarity — is the one
that "is plain Verilog and depends on no attribute in any tool". Two
probes, both `flatten`, both on pinned `fe89f0d` sources with only
`pilot_top.v` edited in the scratch copy:

| Probe | Flops | Cell area |
|---|---|---|
| `keep_hierarchy` present, POL as designed (= point D′) | **1,155** | 124,724 um2 |
| `keep_hierarchy` stripped, POL as designed | **1,100** | 119,675 um2 |
| `keep_hierarchy` stripped, `CFG_POL_B = CFG_POL_C = 0` | **1,045** | 108,569 um2 |

**[fact]**. Read the middle row: with the attribute gone, POL alone
recovers 55 of the 110 flip-flops and **loses the third bank entirely**.
The bottom row reproduces the pre-fix 1,045 exactly, which confirms the
merge is per-bit hashing of identical storage functions.

The reason is arithmetic and it is not fixable by choosing better POL
constants. A storage bit has exactly **two** polarities. `CFG_POL_A` is
all-zeros and `CFG_POL_B` is all-ones, so those two banks differ on
every bit; `CFG_POL_C` is `0x2AAAAAAAAAAAAA`, alternating, so on every
single bit position replica C's stored function is *identical to either
A's or B's*, and yosys hashes each of C's 55 bits into whichever of the
two it matches. **No assignment of `CFG_POL_C` can avoid this**: with
three replicas and two available polarities, one replica always
collides bit-for-bit.

So `keep_hierarchy` is not a redundant belt-and-braces layer, it is the
only thing holding replica C, and `deferred_flatten` — with its 8 % area
bill — is the price of the attribute surviving to the netlist. On a
front end that does not read yosys attributes, which is the case
`pilot_top.v`'s header names POL as the fallback for, the design
silently degrades from triple to **double** modular redundancy.

To be fair to the design: `sw/tests/test_synthesis_guards.py::test_config_tmr_survives_a_flow_that_ignores_keep_hierarchy`
already asserts precisely this bound — it strips the attribute and
requires `lost <= TMR_W`, one bank — so the guard is correct and needs
no change. What this measurement adds is that the design is **sitting
on** that bound rather than comfortably inside it (`lost` is 55, not 0),
and that the bound is not improvable: no assignment of `CFG_POL_C` can
reduce it. The prose in `hw/rtl/pilot_top.v` and in `docs/15` reads as
though it could. See section 8.3.

---

## 4. The sky130 baseline moves too

`docs/18`'s -3.8504 ns is measured on the **pre-fix** netlist
(`sky-02-signoff`, 1,045 flip-flops). The re-hardened netlist has to be
re-measured before any experiment against it means anything.

`sky-04-tmr`, sky130A, 4x2 (682.64 x 225.76 um), `CLOCK_PERIOD: 20`,
`hw/openlane/pilot_sky130/config.json` unchanged apart from the
`SYNTH_HIERARCHY_MODE` the RTL now requires.

| Quantity | `sky-02-signoff` (**superseded**) | `sky-04-tmr` |
|---|---|---|
| Mapped flip-flops | 1,045 | **1,155** |
| Synthesis cell area | 66,598 um2 | 80,069 um2 (+20.2 %) |
| Placed cells, excl. fill | 9,195 | 10,697 |
| Placed cell area | 84,801 um2 | **99,923 um2** (+17.8 %) |
| Utilization | 56.84 % | **66.98 %** |
| Routed wirelength | 315,780 um | 361,758 um |
| Antenna diodes | 25 | 69 |
| Route DRC / Magic DRC / KLayout DRC / KLayout XOR / Netgen LVS | 0 / 0 / 0 / 0 / 0 | **0 / 0 / 0 / 0 / 0** |
| Antenna-violating nets | 0 | **0** |
| **Worst setup, `max_ss_100C_1v60`** | **-3.8504 ns** | **-2.9659 ns** |
| Worst setup, `nom_ss_100C_1v60` | -3.3056 ns | -2.4380 ns |
| Worst setup, `nom_tt_025C_1v80` | +8.2312 ns | +8.7627 ns |
| Setup-violating endpoints, `max_ss` | 179 | 179 |
| Max-slew violations, `max_ss` | 1,526 | 1,999 |

**[fact]**. The same pattern as IHP: the corrected netlist is bigger and
**0.88 ns faster** on the failing corner. It still misses.

Two caveats on that comparison, both the same shape as the IHP one.
`sky-02-signoff` ran with `SYNTH_HIERARCHY_MODE: flatten` and
`sky-04-tmr` with `deferred_flatten` **[fact, both `resolved.json`]**,
so the +17.8 % is the fix *and* the flow setting the fix forces, not the
fix alone — section 3.1 decomposes the equivalent split on IHP as
roughly half and half. And `sky-02-signoff` predates the wave-3 RTL
churn. What the comparison is used for below is only the **baseline
slack the corner experiments are measured against**, and for that
purpose `sky-04-tmr` is the correct reference and `sky-02-signoff` is
superseded outright.

*Status note, 2026-08-30: this table is **not** superseded in value, and
that is itself the finding.* No later sky130 run replaced it at 4x2.
`sky-08-ptrtmr`, on the pointer-TMR RTL, reaches **123,766 um2 placed at
82.96 % placement utilization** and then **diverges in detailed
routing** — 218,483 violations after the 0th optimization iteration,
348,149 after the 1st, 364,603 after the 2nd, with routed wirelength
flat to within 0.5 %, which is congestion rather than slow progress. It
produced no routed netlist, no sign-off deck and no post-route slack, so
there is nothing here to replace **[fact, `docs/22` section 5]**. The
-2.9659 ns above therefore remains the last measured sky130 slack, and
the experiments of sections 5 to 7 keep their baseline.

At **twelve** tiles sky130 routes again: `sky-09-6x2` and `sky-10-3x4`
both converge monotonically to zero DRC and pass Magic, KLayout, the
XOR, all seven Netgen counters and antenna, with **zero global-route
overflow** against 4x2's 22,357 **[fact, `docs/23` sections 4.2, 4.3
and 5]**. The slow corner is still missed there, and by more:
**-5.4953 ns at 3x4** and **-7.3054 ns at 6x2**, 227 violating paths in
both. So the 4x2 divergence was a tile-size effect, and the corner miss
this document diagnoses is not — which is consistent with section 6.2's
parasitic-model account, though that account has **not** been re-tested
at twelve tiles **[planned, `docs/23` section 10 item 6]**.

---

## 5. `PNR_CORNERS`: the experiment, and why it cannot work

### 5.1 What was run

`sky-05-pnrcorners`, identical to `sky-04-tmr` except:

```json
"PNR_CORNERS": ["nom_tt_025C_1v80", "max_ss_100C_1v60"]
```

`max_ss_100C_1v60` is the corner that fails; `nom_tt_025C_1v80` is
`DEFAULT_CORNER` and is kept in the list so the baseline behaviour is a
subset of the variant rather than replaced by it. Confirmed active:
`13-openroad-floorplan`, `28-openroad-globalplacement`,
`43-openroad-stamidpnr-3` and `44-openroad-detailedrouting` each log
`Reading timing models for corner max_ss_100C_1v60` **[fact, grepped]**.

### 5.2 Result

| Quantity | `sky-04-tmr` | `sky-05-pnrcorners` | Delta |
|---|---|---|---|
| **Worst setup, `max_ss_100C_1v60`** | **-2.9659 ns** | **-3.3475 ns** | **-0.382 ns (worse)** |
| Worst setup, `nom_ss_100C_1v60` | -2.4380 ns | -2.7870 ns | -0.349 ns |
| Worst setup, `nom_tt_025C_1v80` | +8.7627 ns | +8.5931 ns | -0.170 ns |
| Setup-violating endpoints, `max_ss` | 179 | 179 | 0 |
| Placed cells, excl. fill | 10,697 | 10,672 | -25 |
| Placed cell area | 99,923 um2 | 99,861 um2 | -0.06 % |
| Utilization | 66.98 % | 66.94 % | -0.04 pts |
| Routed wirelength | 361,758 um | 363,194 um | +0.4 % |
| Antenna diodes | 69 | 51 | -18 |
| Route DRC / Magic DRC / KLayout DRC / XOR / LVS | 0 / 0 / 0 / 0 / 0 | **0 / 0 / 0 / 0 / 0** | — |
| Summed step runtime | 29.5 min | 16.0 min | not a cost signal — see 5.4 |

**The slow corner did not close. It got 0.382 ns worse, at essentially
zero area cost.**

Runtime is not reported as a cost. The summed step runtimes across the
four sky130 runs here are 29.5, 16.0, 15.3 and 11.0 minutes, and section
5.4 shows that the 29.5-minute run and the 11.0-minute run produced
**byte-identical output**. On this machine — which was also carrying
three concurrent LibreLane flows and a long-running formal job — wall
clock measures contention, not work. The honest statement is that
`PNR_CORNERS` adds one extra liberty parse per PnR step and nothing
else, so its true runtime cost is small and this setup cannot resolve
it.

### 5.3 Why: `PNR_CORNERS` governs no step that optimises timing

This is not a marginal effect that needs a better setting. It is
structural, and three independent pieces of evidence say so.

**(a) The steps that repair timing were already multi-corner.**
`OpenROADStep.run` takes `PNR_CORNERS or [DEFAULT_CORNER]`
(`librelane/steps/openroad.py:351`) — but `CTS` overrides it with
`CTS_CORNERS or STA_CORNERS` (`openroad.py:2548`) and **every**
`ResizerStep` overrides it with `RSZ_CORNERS or STA_CORNERS`
(`openroad.py:2393`). Both resolve to all nine corners in the baseline
run already. `PNR_CORNERS` does not reach them.

**(b) The steps `PNR_CORNERS` does govern do no timing optimisation.**
`PL_TIMING_DRIVEN` is `False` in this configuration, and `gpl.tcl` gates
`-timing_driven` on it; the logged command is
`global_placement -density 0.6 -routability_driven -pad_right 0
-pad_left 0 -init_wirelength_coef 0.25` — **no `-timing_driven`**
**[fact]**. Global routing and detailed routing are not timing-driven
either. Floorplan, placement, routing and the mid-PnR STA reports are
what `PNR_CORNERS` reaches, and none of them can act on a slack number.

**(c) The layouts are byte-identical.** MD5 of the output DEF at each
stage, `sky-04-tmr` against `sky-05-pnrcorners`:

| Step | Identical? |
|---|---|
| `34-openroad-detailedplacement` | **yes** |
| `35-openroad-cts` | **yes** |
| `37-openroad-resizertimingpostcts` | **yes** |
| `39-openroad-globalrouting` | **yes** |
| `42-openroad-repairantennas` | no |

**[fact]**. Placement, clock tree, post-CTS timing repair and global
routing produce the *same bits* with and without the slow corner in
`PNR_CORNERS`. The first divergence is inside the GRT antenna-repair
loop — a diode-insertion step, not a timing step — and from there the
detailed route differs (3 TritonRoute iterations against 4) and the
final slack lands 0.38 ns lower. `PNR_CORNERS` did not optimise
anything; it perturbed the antenna repair, and the perturbation happened
to land the wrong way.

`sky-07-repeat` re-runs the **baseline** config against pinned sources
to establish whether that 0.38 ns is a real effect or run-to-run
scatter. Its result is in section 5.4.

### 5.3a The evidence `docs/18` used could not support its conclusion

`docs/18` §3.3b argues that every PnR step is single-corner and cites,
as direct confirmation, that "the `or_metrics_out.json` of
`36-openroad-stamidpnr-1`, `38-openroad-stamidpnr-2` and
`43-openroad-stamidpnr-3` each contain **exactly one**
`timing__setup_vio__count__corner:*` key".

That observation is correct and the inference from it is not. The
mid-PnR STA script begins:

```tcl
foreach {corner_name corner_object} [lln::get_corner_dict] {
    lln::set_sta_cmd_corner $corner_name
    break
}
```

**[fact, `librelane/scripts/openroad/sta/corner.tcl:51-55`]** — it takes
the first corner out of the dictionary and `break`s. `STAMidPNR` writes
metrics for **exactly one corner no matter how many are loaded**, so a
single key in `or_metrics_out.json` is evidence about that `break`, not
about `PNR_CORNERS`. This run proves it directly: `43-openroad-stamidpnr-3`
logs `Reading timing models for corner max_ss_100C_1v60` *and*
`nom_tt_025C_1v80`, and still emits one corner's metrics — `nom_tt`'s
**[fact]**.

Which corner survives the `break` is not controllable from
`PNR_CORNERS` either, because it depends on the dictionary's iteration
order rather than on the list order. On sky130, `PNR_CORNERS:
["nom_tt_025C_1v80", "max_ss_100C_1v60"]` reported `nom_tt` — the
first. On IHP, `["nom_typ_1p20V_25C", "nom_slow_1p08V_125C"]` reported
`nom_slow` — the second (section 7). So `PNR_CORNERS` does not reliably
buy mid-PnR observability of the failing corner; on IHP it happened to,
on sky130 it happened not to.

### 5.4 The control run: the noise floor is zero

A 0.38 ns move is only a result if the flow does not move 0.38 ns on its
own. `sky-07-repeat` is the **baseline** config run a second time, in a
different run directory, under different machine load (three concurrent
LibreLane flows against `sky-04-tmr`'s two), against RTL pinned to
`fe89f0d` rather than read live from `hw/rtl`.

| Corner | `sky-04-tmr` | `sky-07-repeat` |
|---|---|---|
| `max_ss_100C_1v60` | -2.9659 | **-2.9659** |
| `nom_ss_100C_1v60` | -2.4380 | **-2.4380** |
| `min_ss_100C_1v60` | -1.7940 | **-1.7940** |
| `nom_tt_025C_1v80` | +8.7627 | **+8.7627** |
| `max_ff_n40C_1v95` | +12.6384 | **+12.6384** |
| Setup TNS, `max_ss` | -328.15 | **-328.15** |
| Max-slew violations, `max_ss` | 1,999 | **1,999** |

Identical to four decimal places on every one of the nine corners, and
so is everything else: 10,697 cells excluding fill, 99,923.3 um2 placed
cell area, 0.669803 utilization, 361,758 um routed wirelength, 69
antenna diodes, 98 on the max-fanout counter, 0 route DRC / 0 Magic DRC
/ 0 KLayout DRC / 0 XOR / 0 Netgen LVS — every figure matches
`sky-04-tmr` exactly.

Stronger still, the artefacts are byte-identical: the synthesis netlist
(`cb04dce3…`), the hierarchical netlist, and the output DEF at CTS,
post-CTS timing repair, global routing, **antenna repair** and detailed
routing all match by MD5 **[fact]**.

Two things follow.

1. **This flow is deterministic**, including the multi-threaded
   TritonRoute and the antenna-repair loop, independent of machine load.
   So the -0.382 ns in section 5.2 is a **real, reproducible consequence
   of setting `PNR_CORNERS`**, not scatter. It is a small effect
   delivered by an unintended mechanism, but it is not noise.
2. **`pin_rtl.py` reproduces the live-tree config exactly.** The pinned
   runs of sections 5.4 and 6 are directly comparable to the unpinned
   ones of sections 4 and 5, which is what makes the section 6 table
   legitimate after the mid-run RTL edit of section 1.2.

---

## 6. The follow-on hypothesis: repair after routing

`docs/18` §3.3b names a second candidate alongside `PNR_CORNERS`:
"Enabling the post-global-routing repair steps would give the flow a
second chance after extraction." Both are off by default and both are
logged as skipped in every run in this repository **[fact,
`Skipping step 'Repair Design (Post-Global Routing)'` and
`Skipping step 'Resizer Timing Optimizations (Post-Global Routing)'`]**.

`sky-06-postgrt` = `sky-05-pnrcorners` + `RUN_POST_GRT_DESIGN_REPAIR:
true` + `RUN_POST_GRT_RESIZER_TIMING: true`. RTL pinned to `fe89f0d`
(section 1.2).

### 6.1 Result

| Quantity | `sky-04-tmr` | `sky-05-pnrcorners` | `sky-06-postgrt` |
|---|---|---|---|
| **Worst setup, `max_ss_100C_1v60`** | **-2.9659 ns** | **-3.3475 ns** | **-3.1760 ns** |
| Setup TNS, `max_ss` | -328.15 ns | -339.03 ns | **-190.43 ns** |
| Setup-violating endpoints, `max_ss` | 179 | 179 | **178** |
| Worst setup, `nom_ss_100C_1v60` | -2.4380 ns | -2.7870 ns | -2.6141 ns |
| Worst setup, `nom_tt_025C_1v80` | +8.7627 ns | +8.5931 ns | +8.6551 ns |
| Max-slew violations, `max_ss` | 1,999 | 1,993 | 1,963 |
| Placed cell area | 99,923 um2 | 99,861 um2 | **99,925 um2** |
| Utilization | 66.980 % | 66.938 % | **66.981 %** |
| Placed cells, excl. fill | 10,697 | 10,672 | 10,694 |
| Routed wirelength | 361,758 um | 363,194 um | 356,739 um |
| Antenna diodes | 69 | 51 | 76 |
| Route DRC / Magic DRC / KLayout DRC / XOR / LVS | 0/0/0/0/0 | 0/0/0/0/0 | **0/0/0/0/0** |
| Antenna-violating nets | 0 | 0 | **0** |
| Max-fanout counter | 98 | 99 | 100 |
| `design__violations` | 0 | 0 | **0** |

**The slow corner did not close here either.** It sits 0.17 ns better
than the `PNR_CORNERS`-only run and 0.21 ns worse than the plain
baseline. **Total** negative slack is the one figure that moves
decisively — -190.43 ns against the baseline's -328.15 ns, a **42 %
reduction** — so the extra repair passes are doing real work on the bulk
of the violating population and almost none on the worst path. Area
cost: **1.3 um2** — 99,924.6 against 99,923.3, i.e. nothing.

### 6.2 Why not: the parasitic model, not a missing corner or a missing step

The repair steps are not failing to see the corner and they are not
failing to run. They are working from a parasitic estimate that does not
resemble the extraction the sign-off STA uses. The whole chain is
visible in one run:

| Point in the flow | Parasitics | Worst-corner setup slack |
|---|---|---|
| Entering the post-CTS resizer | pre-route wire-load estimate | **-9.598 ns** |
| Leaving the post-CTS resizer | same estimate | **+0.057 ns** |
| Entering the post-GRT resizer (`sky-06`) | global-routing estimate | **-0.363 ns** |
| Leaving the post-GRT resizer (`sky-06`) | same estimate | **+0.084 ns** |
| Sign-off STA, `nom_ss_100C_1v60` | **OpenRCX extraction, nom ruleset** | **-2.614 ns** |
| Sign-off STA, `max_ss_100C_1v60` | **OpenRCX extraction, max ruleset** | **-3.176 ns** |

**[fact]**, all six. The post-CTS resizer log confirms it loads
`sky130_fd_sc_hd__ss_100C_1v60.lib` and reports its work as 302 gate
upsizes, 19 pin swaps, 14 buffer insertions and 22 buffer removals —
**it closes the slow corner completely, on its own estimate**. The
post-GRT resizer, given a second chance on a better estimate, finds only
0.363 ns to fix and closes that too.

Read the last three rows together:

- **~2.7 ns is lost between the global-routing estimate and the OpenRCX
  extraction at the same PVT and the same nominal interconnect corner**
  (+0.084 → -2.614). Neither corner lists nor repair steps address this;
  the optimizer is being told the wires are much better than the
  extractor later says they are.
- **A further 0.56 ns is the interconnect ruleset** (-2.614 nom →
  -3.176 max). That part *is* a corner effect, and it is the smaller
  one.

The cause of the first term is legible in the configuration.
`LAYERS_RC` is **null** for sky130A **[fact, `resolved.json`]**, so
`set_rc.tcl` takes its "no custom RC" branch and calls `set_wire_rc`
with no `-corner`, which averages the tech-LEF layer values and applies
one number to every corner **[fact,
`librelane/scripts/openroad/common/set_rc.tcl`]**. There is no
`max`-interconnect model anywhere inside PnR — only in OpenRCX, which
runs after the last step that could act on it. For contrast,
`ihp-sg13g2` **does** ship `LAYERS_RC` (explicit per-metal `res`/`cap`
under a `"*"` wildcard) **[fact]**, and ships only a `nom_*` OpenRCX
ruleset, so the two models are much closer to each other there.

So the honest one-line diagnosis is: **on sky130A this flow optimises
against a wire model roughly 2.7 ns of WNS more optimistic than the one
it signs off against, and no arrangement of `PNR_CORNERS` or repair
steps can fix a model gap.** That replaces `docs/18` §3.3b's account,
which located the problem in *when* the corner is evaluated rather than
in *what RC* every evaluation uses.

### 6.3 What would actually be worth trying — not run here

**[estimate — none of these were run]**, in the order I would try them:

1. **Populate `LAYERS_RC` for sky130A** from the OpenRCX `max` ruleset,
   so the PnR estimate matches the corner the design is signed off at.
   This is the direct fix for the 2.7 ns term and it is a config change,
   not a flow change. `ihp-sg13g2` demonstrates the shape of it.
2. **`SIGNAL_WIRE_RC_LAYERS`**, which `set_rc.tcl` honours, is a cruder
   lever on the same quantity: the averaged estimate is over the
   *constrained routing layers*, and this design's `RT_MAX_LAYER` is
   `met4`, so the average is being pulled up by layers the router
   barely uses for long nets.
3. Only then `CLOCK_PERIOD`, and `docs/18` §3.3b's measurement of that
   knob (6 ns of period buys 0.65 ns) stands and is now explained: the
   period does not change the model gap.

`PNR_CORNERS` should be recorded as **tested and inert**, not as
untested.

---

## 7. `PNR_CORNERS` on IHP

`ihp-pnrcorners` = the re-harden of section 2 with
`PNR_CORNERS: ["nom_typ_1p20V_25C", "nom_slow_1p08V_125C"]` and nothing
else. The config is generated from `tt/src/config_merged.json` by
`hw/openlane/pilot_ihp/mkconfig.py`; the two resolved configs differ in
exactly four keys, three of which are the source paths and the run
directory **[fact, diffed]**:

```
DESIGN_DIR             tt/src                    | hw/openlane/pilot_ihp
VERILOG_FILES          tt/src/*.v                | hw/rtl/*.v      (same blobs)
VERILOG_INCLUDE_DIRS   null                      | hw/rtl
PNR_CORNERS            null                      | [nom_typ, nom_slow]
```

### 7.1 Result: no change whatsoever

| Quantity | `tmr-reharden` | `ihp-pnrcorners` |
|---|---|---|
| Worst setup, `nom_slow_1p08V_125C` | +6.4359 ns | **+6.4359 ns** |
| Worst setup, `nom_typ_1p20V_25C` | +11.4227 ns | **+11.4227 ns** |
| Worst setup, `nom_fast_1p32V_m40C` | +14.1670 ns | **+14.1670 ns** |
| Placed cells, excl. fill | 10,164 | **10,164** |
| Placed cell area | 158,268 um2 | **158,268 um2** |
| Utilization | 60.9107 % | **60.9107 %** |
| Routed wirelength | 386,429 um | **386,429 um** |
| Route DRC | 0 | **0** |

Not merely equal — **byte-identical**. MD5 of the output DEF at detailed
placement, CTS, post-CTS timing repair, global routing and **detailed
routing** matches in all five cases **[fact]**.

**So `PNR_CORNERS` does not improve the IHP margin, and it does not cost
anything either: zero area, zero layout change, and — since the output
is byte-identical — no work done differently beyond one extra liberty
parse per PnR step.** This is
a stronger version of the sky130 result. On sky130 the setting at least
perturbed the antenna-repair loop (section 5.3); on IHP even that
did not happen, because the IHP flow inserts no antenna diodes at all
(0 diodes, section 2.1) and so has no diode loop to perturb.

The one thing it changes is a report. `43-openroad-stamidpnr-3` in the
baseline emits `nom_typ_1p20V_25C = +10.996`; with `PNR_CORNERS` set it
emits `nom_slow_1p08V_125C = +5.661` instead — one corner either way,
because of the `break` in section 5.3a. That is genuinely useful
observability, and it is also how we know the IHP slow corner is already
+5.66 ns clear *before* extraction and only gains 0.78 ns from it.
Compare the sky130 chain in section 6.2, where the same transition costs
2.7 ns. It is worth being precise about why IHP is safe: **not because
its PnR parasitic estimate is accurate, but because its slow-corner
margin is 6.4 ns and the estimation error never gets a chance to
matter.** The post-CTS resizer on IHP reports `No setup violations
found` **[fact]** — it has nothing to do.

**Recommendation: do not set `PNR_CORNERS` on the IHP submission.** It
buys one changed line in a mid-PnR report at the cost of a
configuration key that a future reader will assume is load-bearing.

---

## 8. Corrections for the integrator

**Do not read this section as an edit to `docs/15` or `docs/18`.**
Neither file is modified by this work. These are the exact corrections
to apply.

Both files were being edited by another session while this work ran, so
the corrections are written against a named revision rather than against
line numbers: `docs/15` blob `c85d64ec`, `docs/18` blob `ae771090`, both
as of 2026-08-26 07:36. `docs/15` §4.2's `deferred_flatten` paragraph
was **already corrected by that other session** and is not listed below;
see 8.3 for the one thing that correction gets wrong.

### 8.1 `docs/15-pilot-tile-plan.md`

Every quantity below appears in several places — `136,107` occurs 8
times, `107,782` 7 times, `52.38` 5 times — so treat this as a
substitution table applied throughout, not as a list of single edits.
The occurrence counts are given so nothing is missed.

**Superseded 2026-08-30, and the substitutions below were applied
before it.** This list corrects `docs/15` from `tt-harden` to
`tmr-reharden`. `docs/15` has since been corrected twice more, so a
reader applying this table today would be substituting a value that is
itself two rounds old — the current post-synthesis cell area is
**151,789.11 um2**, the current placed area **185,755 um2** at 4x2 and
**185,840 um2** at 6x2, and the current mapped flip-flop count
**1,275** **[fact, `docs/22` sections 9.3 and 9.5, `docs/23`
section 2.1]**. `docs/22` section 6.1, as re-stated by its section 9.5,
is the current correction list for `docs/15`, and those corrections are
applied in `docs/15` itself. The table below is kept as the record of
the `tt-harden` → `tmr-reharden` step and of how many places each figure
had reached.

| Old value | Occurrences | New value | Source |
|---|---|---|---|
| 107,782 um2 (post-synthesis cell area) | 7 | **126,647 um2** | `tmr-reharden/06-yosys-synthesis/reports/stat.json` |
| 136,107 um2 (placed standard cells) | 8 | **158,268 um2** | `54-openroad-rcx`, `design__instance__area__class:standard_cell` |
| 25,494 um2 (timing-repair buffers) | 4 | **28,181 um2** (2,213 cells, was 1,954) | `final/metrics.json` |
| 2,814 um2 (clock buffers and inverters) | 2 | **3,422 um2** | `clock_buffer` + `clock_inverter` classes |
| 50,801 um2 (sequential cells) | 2 | **56,582 um2** | `final/metrics.json` |
| 1.2628 (PnR growth factor) | 2 | **1.2497** | 158,268 / 126,647 |
| 52.38 % (utilization) | 5 | **60.91 %** | `design__instance__utilization` |
| 194,439 um2 (8 x 8 at the 70 % criterion) | 3 | **226,097 um2** | 158,268 / 0.70 |
| 1,037 flip-flops | 4 — but **not** the two inside §4.2's quoted "original reasoning" block, which must stay as the record of the error | **1,155** | `final/metrics.json` |
| +5.314 ns / +10.699 ns / +13.846 ns | §4.6 table | **+6.436 / +11.423 / +14.167 ns** | `55-openroad-stapostpnr/summary.rpt` |
| 68 MHz slow-corner Fmax, 14.69 ns path | §4.6 | **73.7 MHz, 13.56 ns path** | derived |
| 467,618 um global-route wirelength | 1 | **542,894 um** | `39-openroad-globalrouting` |
| 335,406 um routed wirelength | §5.3 | **386,429 um**; longest net 1,310 um → **748.6 um** | `50-odb-reportwirelength` |
| detailed routing "2938 → 1192 → 1205 → 45 → 0" | §5.3 | **3389 → 1513 → 1463 → 33 → 0**, still 5 iterations | `44-openroad-detailedrouting` |
| `design__max_fanout_violation__count: 72` | §5.3 | **77** | `final/metrics.json` |

Prose that needs rewriting rather than substituting:

| Location | Correction |
|---|---|
| §4.1, "tool delta, this design +2.21 %" and the `aer_fifo` growth-factor calibration paragraph | Both are computed from the superseded pair. Re-derive or drop; the growth factor is now 1.2497 and the `aer_fifo`-derived prediction is no longer within 1.7 % |
| §4.5, 8 x 8 row, first column (105,245) | The tool changes with this column: 105,245 was local Yosys 0.33 `synth -flatten`, 126,647 is the flow's Yosys 0.67 with `deferred_flatten`. **A like-for-like local-Yosys re-measurement was not made.** If the column must stay local-Yosys, re-derive it rather than copying 126,647 |
| §4.5 superseding note, "about 2.9 % more", "roughly 3 % low" | **+17.5 % at synthesis, +16.3 % placed.** 2.9 % is the flip-flop term alone, measured on a tool and a hierarchy mode the submission no longer uses. Section 3.1 decomposes the real figure |
| §4.5, "the shape column does not move for any row" | Holds for 8 x 8. **Re-check 8 x 16**: scaled by +16.3 % it lands near 268,000 um2, above the 4x2 core, so that row is probably 6-tile now (section 2.4) **[estimate]** |
| §4.6, "the pre-layout estimate was +6.08 ns and 74 MHz … the clock tree and the parasitics cost the 0.77 ns difference" | The agreement argument no longer holds on these numbers; the post-route figure is now +6.436 ns. Re-derive or drop |
| §5.4, gate-level smoke 5/5 | **Stale** — run against the superseded netlist. Re-run against `tt/runs/tmr-reharden/final/nl/` before quoting it |

The 8 x 8 row's *shape* column does not move: **4x2 (8 tiles)** still,
and section 2.4 gives the margin. No other row of the §4.5 table was
re-measured, so the rest of that table remains an unverified model and
is now known to be low by roughly the same 16 %.

*Superseded 2026-08-30: the 8 x 8 row's shape column does move.* It
needs **265,364 um2** of rows at the current netlist against the
259,837 um2 the 4x2 core offers, so it is a **12-tile** row, and the
submission is at 6x2 **[fact, `docs/22` section 9.4, `docs/23`
section 6]**. The model is now known to be low by about **27 %**, not
16 % **[estimate, 135,840 modelled against 185,755 measured]**.

### 8.2 `docs/18-cross-pdk-portability.md`

| Location | Current text | Correction |
|---|---|---|
| §1 and §3.3, "-3.8504 ns", "536 setup violations" | pre-fix netlist | **-2.9659 ns** on the corrected netlist (`sky-04-tmr`). The 536/179 endpoint counts are unchanged |
| §3.3 table, `max_ss_100C_1v60` row | -3.8504 / +0.8963 / 179 / 1,526 | **-2.9659 / +0.9103 / 179 / 1,999** |
| §3.3 table, "Slow-corner path 23.850 ns → 41.9 MHz" | 41.9 MHz | **22.966 ns → 43.5 MHz** — and the caveat that this is not a capability number still stands, more strongly (section 5) |
| §3.3b mechanism, "**Every place-and-route step is single-corner**" | | **Not correct.** `CTS` takes `CTS_CORNERS or STA_CORNERS` (`openroad.py:2548`) and loads all nine, exactly as the resizer does. The single-corner set is floorplan, placement, routing, the mid-PnR STA reports and the antenna steps |
| §3.3b, "The resizer … runs too early to help and inserted only **22 setup buffers**" | | **Undercounts by an order of magnitude.** The post-CTS setup pass did 250 gate upsizes, 21 pin swaps, 22 buffer insertions and 14 buffer removals, and **drove worst-corner WNS from -9.612 ns to +0.052 ns** — it fully closed the corner on its own parasitic estimate (section 6.2) |
| §3.3b, "**What would actually be needed** … `PNR_CORNERS` including `nom_ss_100C_1v60`" | | **Tested; it does not work and structurally cannot** (section 5.3). Replace with the parasitic-model diagnosis of section 6.2 |
| §7 "Not proved", "the honest statement is that the number is unknown until a run with the slow corner inside `PNR_CORNERS` is made, and that run has not been made" | | **That run has now been made.** Rewrite: the number is unknown because the PnR wire-RC estimate and the OpenRCX extraction disagree by ~2.7 ns of WNS on this design, not because a corner was missing from a list |
| §3.3b, "`PNR_CORNERS` resolves to `null` here, so `DEFAULT_CORNER` … is the only corner loaded. Confirmed directly: the `or_metrics_out.json` of `36-`, `38-` and `43-openroad-stamidpnr` each contain **exactly one** `timing__setup_vio__count__corner:*` key" | | **The observation is right; the inference is not.** `STAMidPNR` writes metrics for one corner unconditionally — `corner.tcl:51-55` iterates the corner dict and `break`s on the first entry. A single key proves nothing about `PNR_CORNERS` (section 5.3a) |
| §3.3, area/util figures for `sky-02-signoff` | 56.84 %, 84,801 um2 | **66.98 %, 99,923 um2** (`sky-04-tmr`) |

*Extended 2026-08-30.* This list is superseded as the *complete* set of
corrections for `docs/18`, not in any of its rows. Two later lists sit
on top of it and are applied in `docs/18` itself: **`docs/22`
section 6.2**, which turns the sky130 sign-off column from a value
statement into a status statement, closes the IHP KLayout cell at 0 and
refreshes the IHP area, utilization and slack figures; and **`docs/23`
section 5**, which re-establishes the whole sky130 sign-off column at
twelve tiles and re-measures the slow-corner miss at -5.4953 ns (3x4)
and -7.3054 ns (6x2). Section 8.3 below is unaffected — it is about a
`docs/15` clause and a synthesis property, neither of which any later
run touches.

### 8.3 One clause in `docs/15`'s new correction overstates the guarantee

The `docs/15` §4.2 correction added on 2026-08-26 by the concurrent
session describes the fix as making

> each replica a `keep_hierarchy` `pilot_cfg_bank` instance carrying a
> per-replica storage polarity, **which is plain Verilog and depends on
> no attribute**

The clause in bold is false, and section 3.3 of this document measures
it. With `keep_hierarchy` removed and the polarities left exactly as
designed, the mapped count is **1,100, not 1,155** — replica C is
merged away bit by bit, because a storage bit has only two polarities
and `CFG_POL_C`'s per-bit value necessarily equals `CFG_POL_A`'s or
`CFG_POL_B`'s at every position. No choice of `CFG_POL_C` fixes that.

**The test suite already knows this and the prose does not.**
`sw/tests/test_synthesis_guards.py::test_config_tmr_survives_a_flow_that_ignores_keep_hierarchy`
strips the attribute and asserts `lost <= TMR_W` — at most one bank —
with the docstring "the POL polarity coding must still keep replica A
and replica B apart, so at most one bank's worth of flip-flops can be
lost." That bound is exactly right and this work measures the design
sitting on it: `lost` is 55, not 0. So the guard needs no change; only
the `docs/15` sentence does, and it should stop reading as though the
polarity protects all three replicas.

Suggested replacement for the clause: "…carrying a per-replica storage
polarity. The polarity alone keeps replicas A and B apart with no
attribute involved; **replica C depends on `keep_hierarchy`**, and
therefore on `SYNTH_HIERARCHY_MODE: deferred_flatten`, because a storage
bit has two polarities and three replicas cannot be given three distinct
ones — `sw/tests/test_synthesis_guards.py` encodes exactly this bound."

The same paragraph's flip-flop figures (1,045 → 1,155, "exactly 55 flops
under each replica") are confirmed by this work and need no change.

---

## 9. What is not done

1. **KLayout DRC has still never run on the IHP tile** (section 2.3).
   `hw/openlane/pilot_ihp/config.json` is a generated mirror of the
   submission config and a `RUN_KLAYOUT_DRC: 1` variant of it is a
   30-minute run. It should be done before the shuttle deadline, not
   because anything suggests it will fail but because the precheck runs
   the deck and a local failure is cheaper to find.
2. **The `docs/15` §4.5 tile-budget table is re-measured for one row
   only.** The other five rows are model output and are now known to
   be low by roughly 16 %; none of them changes shape.
3. **Gate-level simulation has not been re-run** against the
   re-hardened netlist (`docs/15` §5.4 is now stale).
4. **The three-replica polarity collision of section 3.3** is an RTL
   observation, not an RTL change. `hw/rtl` is another workstream's.

*Updated 2026-08-30.* Item 1 is **closed**: KLayout DRC ran on the IHP
tile and reports **0**, at `c5a5a6e` on `ihp-klayoutdrc-w5` and again on
the 6x2 submission-shape run **[fact, `docs/22` section 2.4, `docs/23`
section 1.3]**. It was **not** re-run at `0448282` on 4x2, which is
`docs/22` open item 7. Item 2 is **closed differently than it expected**:
the `docs/15` §4.5 table was not re-measured row by row, but its one
measured row left 4x2 — the design went 2.13 % over the criterion — and
the shape moved to 6x2 (`docs/23`). Item 3 is **still open and staler**;
the netlist to re-run the gate-level smoke against is now
`hw/openlane/pilot_ihp/runs/shape-6x2/final/nl/` **[`docs/23` section 10
item 3]**. Item 4 is unchanged. One open item that `docs/22` section 5.3
added and `docs/23` then closed: **a sky130 harden at a larger tile
count** — it was run at both twelve-tile shapes and both route
DRC-clean.

---

## 10. Reproducing this

```bash
make -f tools.mk toolcheck

# Section 2 — the IHP re-harden, submission config, from tt/
cd tt && librelane --pdk ihp-sg13g2 --scl sg13g2_stdcell \
    --run-tag tmr-reharden src/config_merged.json

# Sections 4-6 — sky130, baseline then variants
hw/openlane/pilot_sky130/mkvariant.py pnrcorners
hw/openlane/pilot_sky130/run_sky130.sh --run-tag sky-04-tmr
CONFIG=$PWD/hw/openlane/pilot_sky130/config.pnrcorners.json \
    hw/openlane/pilot_sky130/run_sky130.sh --run-tag sky-05-pnrcorners

# Anything that must be immune to a concurrent hw/rtl edit
python3 hw/openlane/pin_rtl.py fe89f0d \
    hw/openlane/pilot_sky130/config.postgrt.json /tmp/pin-sky06
mkdir -p hw/openlane/pilot_sky130/runs/sky-06-postgrt
CONFIG=/tmp/pin-sky06/config.json hw/openlane/pilot_sky130/run_sky130.sh \
    --run-tag sky-06-postgrt \
    --force-run-dir $PWD/hw/openlane/pilot_sky130/runs/sky-06-postgrt

# Section 7 — IHP with PNR_CORNERS
hw/openlane/pilot_ihp/mkconfig.py
CONFIG=$PWD/hw/openlane/pilot_ihp/config.pnrcorners.json \
    hw/openlane/pilot_ihp/run_ihp.sh --run-tag ihp-pnrcorners

# Section 3 — the synthesis-only area probes
CONFIG=$PWD/hw/openlane/pilot_ihp/config.flatten.json \
    hw/openlane/pilot_ihp/run_ihp.sh --run-tag ihp-synth-flatten \
    -T Yosys.Synthesis

# Every table above
python3 hw/openlane/signoff_report.py <run-dir> [<run-dir> ...]
```

`tt/runs/`, `hw/openlane/*/runs/` are gitignored. The scratch snapshots
`pin_rtl.py` writes are disposable and regenerable from the commit they
name.

---

## 11. Follow-ups closed: a second defence that needs no attribute, and the KLayout deck

Added 2026-08-27, after the sections above. Two of the section 9 open
items are now closed. Nothing above this line is edited; where a
conclusion here supersedes one above, it says so.

- Section 9 item 4 said the three-replica polarity collision of section
  3.3 "is an RTL observation, not an RTL change." It is now a change.
- Section 9 item 1 asked for a `RUN_KLAYOUT_DRC: 1` variant of the IHP
  config. It exists and it has been run.

### 11.1 What section 3.3 found, restated in one line

`keep_hierarchy` was the only thing holding replica C. Section 3.3
measured it (1,155 intact, 1,100 with the attribute stripped) and proved
it could not be fixed by choosing better `CFG_POL_C` constants: a
storage bit has two polarities, there are three replicas, so one replica
always collides bit for bit. The remedy therefore had to change what a
replica *stores*, not which constant it is XORed with.

### 11.2 The obvious candidate does not work, and the reason is worth keeping

A per-replica bit **rotation** — replica C's bit *i* stores
`cfg[(i+k) mod 55]`, which is neither `cfg[i]` nor its inverse — looks
like the answer and costs nothing but rewiring. It does not work.

What `opt_merge` hashes is the flip-flop's `(D, EN, reset-value)`
signature. That signature is indifferent to which bit position the cell
occupies in a vector. A rotation relabels which physical cell holds
which configuration bit and leaves the *set* of stored functions exactly
as it was, so replica C's cell for storage index *i* is bit-for-bit the
same cell as replica A's for index *(i+k) mod 55*, and the two hash
together. The rotated bank does not merge partially; it merges
completely, into A.

Measured, and this is why it is stated as fact rather than as reasoning:
replica C rotated by 7 with `CFG_POL_C = 0`, `keep_hierarchy` stripped,
gives **1,100** flip-flops — the identical number the unrotated
polarity design gives. **[fact]**

A per-replica **constant XOR mask** was also considered and is not a
separate mechanism at all: a constant XOR is a per-bit polarity choice,
which is what `POL` already is. It inherits the two-function ceiling by
definition, so it was not run.

### 11.3 The transform adopted: an invertible XOR mixing on replica C

`hw/rtl/pilot_top.v`, `pilot_cfg_bank`, new parameter `MIX`. With
`MIX = 1` the bank stores `enc(value) ^ POL` and presents
`dec(bits ^ POL)`, where `enc` is two unit-triangular XOR layers over
GF(2) on the 55-bit word:

```
LO = 27, HI = 28
layer 1:  e[i]      = v[i]      ^ v[LO+i]            i = 0 .. LO-1
layer 2:  e[LO+i]   = v[LO+i]   ^ e[(i+1) % LO]      i = 0 .. HI-1
```

and `dec` is the same two layers run backwards. Three properties, all
checked rather than asserted:

1. **Invertible.** A product of two unit-triangular matrices is
   unit-triangular in the block sense and always invertible. Verified
   independently: the matrix has full rank 55 over GF(2), and
   `dec(enc(e_k)) = e_k` on all 55 basis vectors, which is a complete
   proof for a linear map. **[fact]**
2. **Collision-free by construction, not by measurement.** Every output
   row has weight 2 or 3 — layer 1 gives `v[i] ^ v[LO+i]`, layer 2 gives
   a three-term XOR, and the rotation by one in layer 2 is what stops
   the term cancelling the bit's own value. No row has weight 1, so no
   stored bit of replica C can equal `x_i` or `~x_i` for any *i*, so no
   per-bit hash can match it against replica A or replica B. **[fact]**
3. **Functionally invisible.** `q` is the true configuration value on
   every bank, and `q_next = wr_en ? wr_d : q` is the same recurrence
   the polarity banks have, so the voted output is bit-identical to
   today's.

Only replica C carries `MIX = 1`. A and B are already bit-for-bit
distinct from each other by polarity, so the mixing is paid for once.

### 11.4 The measurement that is the point of the exercise

All five probes below are `flatten` on **pinned `fe89f0d` sources** with
only `pilot_top.v` edited in a scratch copy — the same protocol as
section 3.3, so the first three rows are that section's table reproduced
and the last two are new. "Stripped" means
`attrmap -modattr -remove keep_hierarchy` before synthesis, i.e. a front
end that does not read yosys attributes.

| Probe | ASIC flow | `synth_ecp5` | Per-bank, ECP5 |
|---|---|---|---|
| `keep_hierarchy` present, POL as designed | 1,155 | 1,155 | 55 / 55 / 55 |
| stripped, POL as designed | 1,100 | 1,100 | 55 / 55 / **0** |
| stripped, `CFG_POL_B = CFG_POL_C = 0` | 1,045 | 1,045 | 55 / **0** / **0** |
| stripped, replica C rotated by 7, `CFG_POL_C = 0` | 1,100 | 1,100 | 55 / 55 / **0** |
| **stripped, `MIX = 1` on replica C** | **1,155** | **1,155** | **55 / 55 / 66** |

**[fact]**, both flows, all five rows. The 66 in the last cell is not
66 replica bits: with the mixing in place some flip-flops outside the
bank resolve their name through `u_cfg_c`, so the instance-path count
over-reports. That is why the guard asserts `>= TMR_W` per bank and the
flip-flop total separately, and why 55 / 55 / **0** on the row above is
the reading that matters — zero cannot be an artefact of naming. The two flows agree at every
point. The bottom row is the requirement: with the attribute gone, all
three banks survive in both flows, and the count is identical to the
run with the attribute present.

The ECP5 column can be read per bank directly, which the ASIC column
cannot: `synth_ecp5` keeps the replica instance path in the cell names
even after the attribute is stripped, whereas the ASIC recipe's early
`flatten` erases it. For the ASIC column the per-bank claim rests on
conservation — the intact run has 55 flip-flops under each of
`u_cfg_a`, `u_cfg_b`, `u_cfg_c`, and stripping the attribute can only
ever remove cells, so an unchanged total means nothing merged.

There is corroborating direct evidence in the ASIC column as well, of
the presence/absence kind rather than the counting kind. Censusing the
stripped netlist by the public net each flip-flop drives:

| Stripped ASIC netlist | `cfg_a` | `u_cfg_b.bits` | `u_cfg_c.bits` |
|---|---|---|---|
| pinned, POL as designed | 51 | 4 | **absent** |
| pinned + `MIX = 1` | 51 | 4 | **29** |

**[fact]** These are undercounts — yosys names a flip-flop after
whichever public net resolves first, so an aliased replica hides behind
another's name, which is exactly why the assertions in
`sw/tests/test_synthesis_guards.py` count cells and not names. What they
do show unambiguously is that `u_cfg_c.bits` exists as its own driven
net after the mixing and does not exist at all before it.

On the current working tree, which carries another workstream's
`lif_core.v` change and so has a different absolute baseline, the same
five-way property holds at **1,235** flip-flops in all four
flow/attribute combinations. **[fact]**

### 11.5 The guard, and its mutation check

`sw/tests/test_synthesis_guards.py`:

- `test_config_tmr_survives_a_flow_that_ignores_keep_hierarchy` had the
  bound `lost <= TMR_W`, one bank. Section 3.3 observed that the design
  sat exactly on it. The bound is now `lost == 0`. This matters more
  than it looks: at `<= TMR_W` the file passed just as happily with the
  third bank gone, which is precisely what section 3.3 discovered by
  hand.
- `test_config_tmr_is_three_banks_without_keep_hierarchy_in_ecp5` is
  new, and asserts the per-bank count directly in the flow where the
  instance names survive.
- `test_the_two_flows_agree_without_keep_hierarchy` is new, the
  attribute-free companion to the existing two-flow canary.

Mutation-checked by reverting `.MIX(1)` on `u_cfg_c` alone in a scratch
tree and running the file against it with `NSSOC_RTL_DIR`: **2 failed,
11 passed**, and the two failures are exactly the two attribute-
independence tests. **[fact]** The ASIC one reports 1,235 -> 1,180,
`lost` 55; the ECP5 one reports the per-bank census collapsing to
`{u_cfg_a: 47, u_cfg_b: 52, u_cfg_c: 11}`.

Section 3.3's closing paragraph says the guard "is correct and needs no
change". That was right about the bound being a true statement and wrong
about it being sufficient, and this section supersedes it.

### 11.6 Cost

**Area, sg13g2, matched synthesis A/B on the same tree**, the only
difference being `.MIX(1)` on `u_cfg_c`, `yosys stat -liberty`:

| | with `MIX` | without | Delta |
|---|---|---|---|
| Chip area | 141,842.95 um2 | 140,352.35 um2 | **+1,490.60 um2, +1.06 %** |
| `sg13g2_xor2_1` | 443 | 354 | +89 |
| `sg13g2_mux2_1` | 269 | 299 | -30 |
| `sg13g2_mux4_1` | 90 | 87 | +3 |
| `sg13g2_dfrbpq_1` | 1,235 | 1,235 | 0 |

**[fact]** No flip-flop is added: the transform is combinational
rewiring on the write and read sides of one bank. The net is smaller
than the 110 XOR2 + 55 MUX2 the RTL asks for, because the encoder and
decoder share terms after `abc` and because making the hold explicit
lets some of the per-field enable muxing collapse — hence the *negative*
`mux2` delta.

**One hardening cost, stated because it is real and small.** A single
upset in replica C now decodes to two or three wrong bits at that
replica's output instead of one. Against a *single* fault this is
free — all the wrong bits are in one replica and a bitwise majority
masks every bit on which one replica disagrees, however many. Against a
*double* fault it is not quite free: two upsets in different replicas
are uncorrectable only if they land on the same bit of the voted word,
and widening replica C's error from one bit to about three raises that
coincidence probability for any (C, A) or (C, B) pair by roughly the
same factor. The absolute number stays small — of order 3/55 rather
than 1/55 for a pair — and it buys the third replica existing at all,
which is a first-order effect against a second-order one. **[estimate
on the factor; the widening from one bit to two or three is fact]**

The earlier revision of `hw/rtl/pilot_top.v`'s header used this
multi-bit widening to conclude that "no encoding can" do better than
polarity coding. That conclusion does not follow: it treats a multi-bit
error inside one replica as if it were a multi-replica error. The
header is corrected.

**Fmax.** There is no matched ASIC A/B for timing here, so the honest
answer comes from the flow that has one. ECP5 85F, speed grade 6, seed
0, 25 MHz target, the same tree with and without `.MIX(1)`:

| | with `MIX` | without | Delta |
|---|---|---|---|
| `TRELLIS_FF` | 1,235 | 1,235 | 0 |
| `TRELLIS_COMB` | 5,559 | 5,350 | +209 |
| Max frequency | **26.62 MHz** | 28.63 MHz | **-2.01 MHz, -7.0 %** |

Both PASS the 25 MHz target. **[fact]** The -7 % should not be read as
the transform's timing cost, because **the critical path is not in the
configuration bank in either run**: nextpnr reports it through the
weight memory and the `busy` logic in both cases (`u_pilot.u_lif.wmem`
in the no-`MIX` run). What the transform contributes is +209 LUT-level
cells of congestion in a design whose Fmax on this part is already
routing-dominated, and nextpnr Fmax at a fixed seed is not a
repeatable-to-1 % number. Treat -2 MHz as an upper bound on a
congestion effect rather than as a path delay. **[estimate]**

`make -C hw/fpga fit` with the transform in place still fits and still
passes on all three parts — 85k **26.62 MHz**, 45k **26.69 MHz**, 12k
**26.53 MHz**, all PASS at 25 MHz **[fact]** — so the 26.62 is a
property of the design on this toolchain rather than an 85k placement
fluke. Yosys still derives three distinct `$paramod$...pilot_cfg_bank`
module types, which is defence (c) intact.

The ECP5 absolute numbers here are far below the 46.45 MHz recorded in
`hw/rtl/pilot_top.v`'s cost table, because this tree carries another
workstream's `lif_core.v` change. The A/B is matched; the absolute
column is not comparable to that table.

The new logic sits on two paths inside the mixed bank only: `Q -> dec ->
mux -> enc -> D`, five gate levels, and `Q -> dec -> q`, two gate levels
added to the existing one. At `CLOCK_PERIOD: 20` on sg13g2 neither is
close to being critical; the IHP sign-off below carries +6 ns of slow-
corner slack.

### 11.7 Verification, unmodified

The transform is functionally invisible, so nothing in the test suite
was allowed to change to accommodate it. Run on the working tree with
the pinned toolchain (`yosys 0.67+146`):

| Suite | Result |
|---|---|
| `hw/tb/Makefile.pilot` | 23/23 PASS, including `test_tmr_masks_a_corrupted_config_replica` |
| `hw/tb/Makefile` (aer_fifo) | 11/11 PASS |
| `hw/tb/Makefile.lif` | 32/32 PASS |
| `hw/tb/Makefile.regbank` | 33/33 PASS |
| `hw/tb/Makefile.secded` | 12/12 across two tops |
| `hw/tb/Makefile.tmr` | 7/7 across three widths |
| `hw/tb/Makefile.scrub` | 14/14 across three geometries |
| `hw/tb/Makefile.fi` | 5/5 PASS |

**[fact]** The fault-injection campaign is the interesting one, because
it deposits into `u_cfg_c.bits` directly rather than at the voter input.
With the mixing in place a deposit on one storage bit of replica C now
corrupts two or three bits of that replica's output, and the campaign
still classifies **`cfg_tmr_c` 5/5 CORRECTED**, alongside `cfg_tmr_a`
5/5 and `cfg_tmr_b` 5/5. That is the single-fault argument of section
11.6 measured rather than asserted.

One stale comment is left behind and is not this workstream's to edit:
`hw/tb/test_fi_campaign.py` explains its choice of deposit target with
"Each bank stores `value ^ POL` ... XOR with a constant is bit-wise, so
flipping bit i of `bits` still flips exactly bit i of the value the
voter sees." That remains true of replicas A and B and is no longer
true of C. The classification is unaffected — the voter masks the whole
replica either way — but the sentence should be corrected when that file
is next touched.

Root `pytest`: **191 passed**. `hw/openlane/pilot_ihp/mkconfig.py
--check`: configs match. `scripts/gen_tt_submission.py` re-run so `tt/`
matches the RTL; it rewrote `tt/src/pilot_top.v` and
`tt/MANIFEST.sha256`.

`make -C formal everything` needed two attempts and the first failure is
worth recording so it is not mistaken for a regression. `aer_fifo_cover`
**reached all five cover statements** and then `yosys-smtbmc` died with
`FileNotFoundError: 'engine_0/trace4.vcd'` while writing the last
witness — a trace-dump race, not a property failure. Re-running the same
task unchanged gives `DONE (PASS, rc=0)` with the identical five reached
statements at the identical steps. **[fact]** Nothing in this
workstream touches `aer_fifo`.

