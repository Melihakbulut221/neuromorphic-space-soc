# Cross-PDK portability: the 4x2 pilot hardened on SKY130A

Evidence file for one question that docs/12 and docs/15 left open: the
pilot has a clean IHP SG13G2 sign-off, but is that a property of the
*design* or a property of *that PDK*? The only way to find out is to
harden the same RTL on a second PDK and compare, which is what this
document records.

The immediate prompt is external. `gonsolo/Borg` runs two CI workflows
that are manufacturability gates of exactly this shape:
`gds-sky130.yaml` builds through `TinyTapeout/tt-gds-action@ttsky26a`
on `sky130A` and then runs the Tiny Tapeout precheck and `gl_test`;
`gds-wafer-space.yaml` runs LibreLane on GF180MCU and fails the build
unless the LibreLane manufacturability report shows exactly three
`Passed` results — Antenna, LVS and DRC **[fact, both files read from
`https://raw.githubusercontent.com/gonsolo/Borg/main/.github/workflows/`
on 2026-08-26]**. Section 5 applies that second gate's logic, literally,
to the run recorded here.

Convention: **[fact]** = measured in this environment or read out of an
installed file; **[estimate]** = derived or judged.

**Headline, 2026-08-26.**

- **The design is PDK-portable for manufacturability, and this was
  measured, not assumed.** `tt_um_melihakbulut_nssoc` hardened end to end
  on `sky130A` / `sky130_fd_sc_hd` inside the Tiny Tapeout 4x2 tile, from
  the *same RTL files*, at the *same 20 ns clock constraint*, with **zero
  PDK-specific RTL changes and zero PDK-specific flow workarounds**.
  Magic DRC **0**, KLayout DRC **0**, Netgen LVS **0** on all seven
  counters, antenna **0 nets / 0 pins**, detailed-route DRC **0**,
  Magic/KLayout XOR **0**. Run `sky-02-signoff`, 80 stages, 76 step
  directories, 18.6 minutes. Sections 3.1 and 4.3. **[fact]**
- **The wafer.space gate would have gone green.** LibreLane's own
  `manufacturability.rpt` for this run contains exactly three
  `Passed` lines and zero failure markers. Section 5. **[fact]**
- **Timing did *not* port, and that is the real finding.** At the same
  20 ns the design closes the typical corner with **+8.2312 ns** of setup
  slack but **misses the slow corner by -3.8504 ns**, with **536 setup
  violations** and **3,528 max-slew violations** summed over the three
  `ss` corners (worst single corner 1,526; a further 38 slew violations
  sit at `tt`). On IHP the same design at the same 20 ns closed *all three*
  of its corners, worst slack **+5.3141 ns**. Hold is clean on all nine
  sky130 corners. Section 3.3. **[fact]**
- **The flow does not tell you that.** `design__violations` is **0** and
  the run completes, because the PDK ships
  `TIMING_VIOLATION_CORNERS: ["*tt*"]` and
  `MAX_SLEW_VIOLATION_CORNERS: [""]` — the setup checker only looks at
  the typical corners and the max-slew checker is switched off by a
  match-nothing wildcard. Neither is something this configuration chose.
  Section 3.3a. **[fact]**
- **A slower clock is not the fix, and that was measured too.** A second
  full run at **26 ns** moves the worst slow-corner slack from -3.8504 ns
  to only **-3.2007 ns** — **6 ns of extra period buys 0.65 ns where it
  is needed**, because every place-and-route step except the resizer
  loads only `DEFAULT_CORNER`, and the `ss` corner is first evaluated on
  real parasitics at the final STA, after the last repair step has run.
  Section 3.3b. **[fact]**

Run trees under `hw/openlane/*/runs/` are **gitignored**. Every number
below is therefore quoted in full with the run tag and step directory it
came from, so this file remains the evidence after the trees are deleted.

---

## 1. Scope

**Question.** Does `tt_um_melihakbulut_nssoc` reach the same clean
result on `sky130A` that docs/15 section 5.3 records for
`ihp-sg13g2` — and if not, exactly which part fails to port?

**What this file owns.** `hw/openlane/pilot_sky130/` and itself. No
existing file was modified. In particular `hw/openlane/run_trial.sh` is
owned by docs/12 and was copied rather than edited (2.2).

**Non-goals.** This is not a sky130 shuttle submission, not a precheck
run, and not a re-verification: the functional evidence in docs/15
section 5.1 (22 cocotb tests) and the formal proofs are technology
independent and are not re-run here. There is no gate-level simulation
of the sky130 netlist.

---

## 2. What was run

### 2.1 Design under test, and why the wrapper rather than `pilot_top`

The brief allowed either `hw/rtl/pilot_top.v` or the Tiny Tapeout
wrapper. **The wrapper was chosen**, for three reasons, and the choice is
load-bearing:

1. **It keeps the experiment single-variable.** The IHP reference is a
   harden of `tt_um_melihakbulut_nssoc` inside a fixed 4x2 tile whose pin
   frame comes from a DEF template. Hardening `pilot_top` here would have
   changed the module *and* the floorplan style (relative sizing,
   auto-placed IOs) at the same time, and any difference in the result
   would then be unattributable.
2. **It is the module the gate builds.** `gds-sky130.yaml` invokes
   `tt-gds-action@ttsky26a` on the Tiny Tapeout top level, not on an
   internal module.
3. `pilot_top.v` is technology independent by construction (its own
   header says so) and carries no Tiny Tapeout port names, so wrapping it
   is what any sky130 submission would do anyway.

Sources are read from `hw/rtl/` directly, not from the generated
`tt/src/` copies, so the run cannot silently harden a stale copy.

**Which revision of the RTL, exactly [fact].** docs/12 section 4.7 makes
the point that "the same design" is not the same netlist and that a run
tag has to be stated; this run needs the stronger version of that,
because `hw/rtl/pilot_top.v` was edited by separate work **while these
runs were in flight** — file mtime **2026-08-26 03:34:23**, against
synthesis at **03:05:29** (`sky-02-signoff`) and **03:25:15**
(`sky-03-clk26`). Both runs therefore read the file **as committed at
`b2154b4`**, git blob `e5dd0472fcb489012ce1f360b9336a929a6a55f3`, and the
other six sources are unmodified from that commit. The two runs report
**byte-identical synthesis** — 5,248 cells, 66,597.6224 um2 both times —
which is the independent confirmation that they saw the same netlist.
**The working tree no longer matches what was hardened**, so every number
in this document belongs to `b2154b4` and has to be re-measured against
any later `pilot_top.v`.

### 2.2 Toolchain [fact]

Identical to docs/12 section 2.1 — the same rootless shim set, the same
LibreLane virtualenv, the same `unset LD_LIBRARY_PATH` discipline. No
root, no container, no system package installation, nothing installed
into the repository.

| Component | Version | How it is reached |
|---|---|---|
| LibreLane | v3.0.5 | `~/Documents/caravel-lif-crossbar/.venv-flow/bin/librelane` |
| Ciel (PDK manager) | v2.6.1 | same venv |
| OpenROAD | 26Q1-2938-g0e2d771c5e | shim -> ORFS install tree |
| Yosys | 0.67 (2d1509d1b) | shim -> oss-cad-suite |
| KLayout | 0.30.9 | shim |
| Magic | 8.3.678 | shim |
| Netgen | 1.5.272 | shim |
| **sky130 PDK (open_pdks)** | **`8afc8346a57fe1ab7934ba5a6056ea8b43078e71`** | ciel, under `~/.ciel` |
| Standard-cell library | `sky130_fd_sc_hd` (428 Liberty cells) | in the PDK |

`hw/openlane/pilot_sky130/run_sky130.sh` is a copy of
`hw/openlane/run_trial.sh` with the PDK/SCL pair changed and the version
assertion rewritten for the sky130 family. It is a copy and not an edit
because `run_trial.sh` belongs to docs/12 and this workstream does not
own it. The one substantive difference beyond the names: **`sky130A` is
a *variant* of the ciel *family* `sky130`**, so `ciel enable` and the
`pdk_hashes.yaml` lookup take `sky130` while LibreLane's `--pdk` takes
`sky130A`. `$PDK_ROOT` carries one symlink per variant — `sky130A` and
`sky130B` — into the same version directory, which is why both can be
present at once while `ihp-sg13g2` also stays enabled. The two names are
not interchangeable on the command line and the script keeps them
separate.

### 2.3 PDK availability: nothing was downloaded [fact]

The brief asked for this to be established rather than assumed.

```
$ ls -la ~/.ciel/sky130A
~/.ciel/sky130A -> ciel/sky130/versions/8afc8346a57fe1ab7934ba5a6056ea8b43078e71/sky130A
$ grep sky130 <librelane>/pdk_hashes.yaml
sky130: 8afc8346a57fe1ab7934ba5a6056ea8b43078e71
```

The enabled version **already equalled** the version LibreLane 3.0.5
pins, so `run_sky130.sh`'s assertion passed on the first try and nothing
was fetched. `~/.volare` does not exist on this machine; ciel is
LibreLane 3.x's PDK manager and volare is not involved (docs/12 section
2.2). The installation is the one the sibling project
`/home/hasanmelih/Documents/radhard-edge-ai/hw/openlane/` already uses —
that project's `run_trial.sh` asserts `[ -d "$PDK_ROOT/sky130A" ]`
against the same `$HOME/.ciel` — so this run reuses it and does not add
a second copy. `~/.ciel` holds `sky130A`, `sky130B` and `ihp-sg13g2`
side by side; the sg13g2 pin `c4b8b4e5...` is untouched by this work.

### 2.4 The configuration delta, key by key [fact]

`hw/openlane/pilot_sky130/config.json` against the submission's own
`tt/src/config_merged.json` (the file `tt_tool.py --create-user-config`
produces and the GDS action consumes). **Five keys differ for the PDK,
two are a deliberate superset, and one is explicit-but-default.**

| Key | ihp-sg13g2 | sky130A | Why |
|---|---|---|---|
| `PDK` | `ihp-sg13g2` | `sky130A` | |
| `STD_CELL_LIBRARY` | `sg13g2_stdcell` | `sky130_fd_sc_hd` | |
| `DIE_AREA` | `0 0 854.40 313.74` | `0 0 682.64 225.76` | the 4x2 entry of each tech's `tile_sizes.yaml` |
| `FP_DEF_TEMPLATE` | `.../ihp-sg13g2/def/tt_block_4x2_pgvdd.def` | `.../sky130A/def/tt_block_4x2_pg.def` | `def_suffix` is `pgvdd` there and `pg` here (`tt/tt/tech.py`) |
| `RT_MAX_LAYER` | `TopMetal1` | `met4` | each tech's `project_top_metal_layer` |
| `RUN_KLAYOUT_DRC`, `RUN_KLAYOUT_XOR` | `0` | **`1`** | superset, see below |
| `RUN_HEURISTIC_DIODE_INSERTION` | (default) | `false` (explicit) | also the LibreLane default; stated so the diode counts in 4.2 are attributable |

Everything else — `CLOCK_PERIOD: 20`, `PL_TARGET_DENSITY_PCT: 60`, the
margin multipliers, `FP_PDN_VPITCH: 38.87`, the hold-slack margins — is
copied verbatim from `tt/src/config.json`, which is technology
independent: `tt/tt/tech.py` gives `Sky130Tech` an **empty**
`librelane_config`, so upstream applies no sky130 overrides of its own
(unlike `GF180MCUDTech`, which overrides five keys).

**The KLayout superset is deliberate and it matters for section 5.** The
Tiny Tapeout defaults switch both KLayout steps off under the comment
"Save some time", so the IHP 4x2 run of docs/15 section 5.3 **never ran
the KLayout deck at all** — only the precheck would have. The docs/12
section 4.1 `aer_fifo` sign-off ran Magic DRC, the KLayout deck and the
Magic/KLayout XOR together, and that is the bar this run is held to. It
also matters because LibreLane's DRC verdict is the **conjunction** of
both decks (`librelane/steps/misc.py`, lines 91-130): with the Tiny
Tapeout defaults, `* DRC / Passed` would have been a statement about
Magic alone.

**One prerequisite, named because it fails confusingly.**
`FP_DEF_TEMPLATE` resolves into `tt/tt/`, which is the `tt-support-tools`
clone at commit `01d5d2814fa9dd61e9d211e0b235a4a592a9316a` and is
**gitignored** — `scripts/gen_tt_submission.py` clones it, the repository
does not vendor it. `tt/src/user_config.json` has the identical
dependency, so this is the project's existing convention rather than a
new one. A fresh checkout without that clone presents as a floorplan
error, not as a missing-file error.

---

## 3. Result, side by side

Both columns are the same seven RTL files, the same top module, the same
`CLOCK_PERIOD: 20`, the same 4x2 tile count.
sky130 column: run **`sky-02-signoff`**, 2026-08-26, via
`hw/openlane/pilot_sky130/run_sky130.sh --run-tag sky-02-signoff`.
IHP column: run **`tt-harden`**, docs/15 section 5.3, re-read here from
`tt/runs/tt-harden/final/metrics.json` rather than transcribed.

### 3.1 Sign-off [fact]

| Check | Step | **sky130A** | ihp-sg13g2 |
|---|---|---|---|
| Magic DRC | `64-magic-drc` | **0** | 0 |
| KLayout DRC (deep, `sky130A_mr.drc`) | `65-klayout-drc` | **0** | *not run* (`RUN_KLAYOUT_DRC: 0`) |
| Netgen LVS, all seven counters | `70-netgen-lvs` | **0** | 0 |
| Magic illegal overlap | `69-checker-illegaloverlap` | **0** | 0 |
| Magic/KLayout XOR | `62-klayout-xor` | **0** | *not run* |
| Antenna, post-detailed-routing | `46-openroad-checkantennas-1` | **0 nets / 0 pins** | 0 / 0 |
| Detailed-routing DRC | `44-openroad-detailedrouting` | **0** | 0 |
| Power-grid connectivity | `56-openroad-irdropreport` | 0 on VPWR and VGND | 0 |
| Disconnected pins | `48-odb-reportdisconnectedpins` | 6 (0 critical) | 6 (0 critical) |
| `flow__errors__count` | `final/metrics.json` | **0** | 0 |

The seven Netgen counters — `design__lvs_error__count`,
`..._device_difference__count`, `..._net_difference__count`,
`..._property_fail__count`, `..._unmatched_device__count`,
`..._unmatched_net__count`, `..._unmatched_pin__count` — are **all 0**
on sky130, exactly as on IHP.

That the *disconnected pin* count is 6 on both PDKs, with 0 critical, is
worth noting on its own: it is a property of the netlist (the Tiny
Tapeout wrapper ties off pins the design does not use), not of the
technology, and it reproduces to the instance.

### 3.2 Area and utilization [fact]

| Quantity | **sky130A** | ihp-sg13g2 | Ratio |
|---|---|---|---|
| Standard-cell row height | 2.72 um (site `unithd`, 0.46 um wide) | 3.78 um (`CoreSite`, 0.48 um wide) | 0.72 |
| Core voltage | 1.80 V | 1.20 V | — |
| Liberty cells in the SCL | **428** | **84** | 5.1x |
| 4x2 die | **154,113 um2** (682.64 x 225.76) | 268,059 um2 (854.40 x 313.74) | 0.575 |
| 4x2 core (placement rows) | **149,183 um2** | 259,837 um2 | 0.574 |
| Post-synthesis cells | **5,248** | 6,587 | 0.797 |
| Post-synthesis area | **66,597.62 um2** | 107,781.86 um2 | 0.618 |
| Flip-flops after synthesis | **1,045** | 1,037 | 1.008 |
| **Placed standard cells, final** | **84,801.3 um2** | **136,107 um2** | **0.623** |
| of which timing-repair buffers | 12,759.7 um2 (1,558 cells) | 25,494.1 um2 (1,954 cells) | 0.50 |
| of which clock buffers + inverters | 2,333.5 um2 (174 cells) | 2,814.1 um2 (146 cells) | 0.83 |
| of which well taps | 2,700.09 um2 (2,158 cells) | **0** (sg13g2 has no tap cells) | — |
| of which antenna diodes | 142.637 um2 (57 cells) | **0** | — |
| **Utilization** | **56.84 %** | 52.38 % | — |
| Non-fill instances | 9,195 | 8,687 | 1.06 |
| Fill cells | 18,989 | 13,865 | — |
| Place-and-route growth factor | **1.2733** | 1.2628 | — |

Three things this table says that are worth pulling out.

**The design shrinks by 37.7 % but the tile shrinks by 42.5 %, and it
still fits.** The sky130 4x2 tile is *smaller in absolute terms* than the
IHP 4x2 tile, so the same design lands at a **higher** utilization —
56.84 % against 52.38 %. It fits comfortably either way, but this is the
number to watch if the design grows: the sky130 tile has less absolute
headroom despite the denser library, and the 4x2 shape is not
interchangeable between the two shuttles.

**The place-and-route growth factor is nearly identical across PDKs
(1.2733 vs 1.2628, 0.8 % apart).** docs/15 section 4.1 established that
factor on IHP from `aer_fifo` and used it to predict this design to
within 1.7 %. That it survives a PDK change is a genuinely useful
calibration result and was not something this run set out to test.

**sky130 spends 2,700 um2 on well taps that sg13g2 does not need.**
docs/12 section 5 records that sg13g2 ships no well-tap or end-cap cells
and the PDK sets `FP_TAPCELL_DIST 0`. On sky130 the flow inserted 2,158
tap cells. That is 3.2 % of the core, and it is a fixed tax the IHP
numbers do not carry — worth knowing before anyone compares the two
utilization figures directly.

**Flip-flop mapping is not the same shape.** On sg13g2 all 1,037
sequential cells are `sg13g2_dfrbpq_1`, because that library has no plain
D flip-flop at all (docs/12 section 5). On sky130 the 1,045 split three
ways — **544 `dfxtp_2`** (no reset), **493 `dfrtp_2`** (reset), **8
`dfstp_2`** (set) — because the library offers all three. This is also
why the sky130 netlist carries **no tie-high cells for reset pins**,
where the `aer_fifo` study measured 1,024 `sg13g2_tiehi` doing exactly
that. The eight extra flops are a mapping difference, not a design
difference.

### 3.3 Timing — this is where portability stops [fact]

Post-route, with an inserted clock tree and OpenRCX parasitics, at
`CLOCK_PERIOD: 20`. From
`hw/openlane/pilot_sky130/runs/sky-02-signoff/55-openroad-stapostpnr/summary.rpt`.

**sky130A ships nine STA corners, not three.** `STA_CORNERS` is
`nom/min/max` interconnect crossed with `tt_025C_1v80`, `ss_100C_1v60`
and `ff_n40C_1v95`; the IHP PDK ships three `nom_*` corners only, so it
varies PVT but not RC. The sky130 run is therefore analysed *harder*
than the IHP run was, and that has to be said before the two are
compared.

| Corner | Worst setup | Worst hold | Setup vio | Hold vio | Max cap | Max slew |
|---|---|---|---|---|---|---|
| `nom_tt_025C_1v80` | **+8.2312** | +0.3158 | 0 | 0 | 0 | 11 |
| `min_tt_025C_1v80` | +8.6287 | +0.3144 | 0 | 0 | 0 | 0 |
| `max_tt_025C_1v80` | +7.9265 | +0.3173 | 0 | 0 | 0 | 27 |
| `nom_ss_100C_1v60` | **-3.3056** | +0.8898 | **179** | 0 | 0 | **1,195** |
| `min_ss_100C_1v60` | -2.5968 | +0.8841 | **178** | 0 | 0 | **807** |
| `max_ss_100C_1v60` | **-3.8504** | +0.8963 | **179** | 0 | 0 | **1,526** |
| `nom_ff_n40C_1v95` | +12.4846 | +0.1044 | 0 | 0 | 0 | 0 |
| `min_ff_n40C_1v95` | +12.7433 | **+0.1042** | 0 | 0 | 0 | 0 |
| `max_ff_n40C_1v95` | +12.2833 | +0.1042 | 0 | 0 | 0 | 0 |

Against the IHP reference at the same 20 ns:

| Corner | Worst setup | Worst hold | All four vio counters |
|---|---|---|---|
| `nom_slow_1p08V_125C` | **+5.3141** | +0.5876 | 0 |
| `nom_typ_1p20V_25C` | +10.6989 | +0.2711 | 0 |
| `nom_fast_1p32V_m40C` | +13.8460 | +0.0988 | 0 |

**Read as frequency [estimate — a single-point extrapolation from one
run, and a weak one on the sky130 side: 3.3b shows the flow optimized
this design against the typical corner only, so the slow-corner figure
below is what *this* run achieved, not what the design is capable of on
sky130]:**

| | sky130A | ihp-sg13g2 |
|---|---|---|
| Typical-corner path | 20 - 8.2312 = 11.769 ns -> **85.0 MHz** | 20 - 10.6989 = 9.301 ns -> 107.5 MHz |
| **Slow-corner path** | 20 + 3.8504 = 23.850 ns -> **41.9 MHz** | 20 - 5.3141 = 14.686 ns -> 68.1 MHz |

So as hardened here the design is roughly **38 % slower at the slow
corner** on sky130 than on IHP, and 50 MHz — the rate `tt/info.yaml`
declares and docs/06 section B.2 budgets — **is not met at
`ss_100C_1v60`**. How much of that 38 % is the process and how much is
the flow's single-corner optimization is *not* separated by this run;
3.3b is why that distinction has to be made. Hold is clean
everywhere, with the thinnest margin +0.1042 ns at the fast corners,
which is `PL_RESIZER_HOLD_SLACK_MARGIN: 0.1` working exactly as
configured — the same behaviour the IHP run showed at +0.0988 ns.

The critical path is unchanged in kind: it still runs through the SECDED
XOR trees on the weight-load path, not the neuron scan.

Power at typical, 1.80 V, 50 MHz: **4.960 mW** (3.530 internal, 1.431
switching, 0.16 uW leakage), against 4.255 mW at 1.20 V on IHP. Worst IR
drop 0.070 mV on VPWR and 0.082 mV on VGND, 0 power-grid violations;
`VSRC_LOC_FILES` is unset, so these are indicative rather than sign-off
numbers.

#### 3.3a Why the flow reported `design__violations: 0` anyway [fact]

536 setup violations and 3,566 max-slew violations across the nine
corners, and the run still finished with `design__violations: 0` and
`flow__errors__count: 0`. That is not a suppression this configuration
applied. Read out of the checker steps' own resolved configuration:

- `72-checker-setupviolations`: `SETUP_VIOLATION_CORNERS: null`, so it
  falls back to `TIMING_VIOLATION_CORNERS`, which the PDK sets to
  **`["*tt*"]`**. At the three `tt` corners the setup violation count is
  0, so the checker passes.
- `74-checker-maxslewviolations`: `MAX_SLEW_VIOLATION_CORNERS: [""]` —
  the **match-nothing wildcard** (`match_none_wildcard = ""` in
  `librelane/steps/checker.py`). The max-slew checker is therefore
  disabled outright, on every corner, by default.

docs/12 section 5 recorded the equivalent trap on IHP
(`TIMING_VIOLATION_CORNERS` defaults to `*typ*` there) and said it was
"worth overriding for anything going to silicon". This run is the
demonstration of why: on IHP the restriction hid nothing, because all
three corners were clean anyway; on sky130 it hides a 3.85 ns setup miss
and 1,526 slew violations, and the flow exits 0. **A green LibreLane run
is not a statement that timing closed.**

For completeness, the max-slew violators at the typical corner are
marginal — 11 pins at 0.7897 ns against a 0.75 ns
`MAX_TRANSITION_CONSTRAINT`, i.e. 5 % over — while at `max_ss` there are
1,526 of them. The constraint itself is the sky130 PDK default, not a
value this config set.

#### 3.3b Relaxing the clock does not fix it — measured [fact]

Because the brief's instruction was to keep the IHP clock "unless sky130
forces otherwise", and section 3.3 shows that it does, a second full run
was made at a relaxed constraint to find where the slow corner closes:

```
hw/openlane/pilot_sky130/run_sky130.sh --run-tag sky-03-clk26 -c CLOCK_PERIOD=26
```

`-c/--override-config` rather than a second config file, so that the
committed configuration stays the one section 3 was measured on and the
only difference between the two runs is visible on the command line.

**It does not close, and the reason is more interesting than the miss.**

| | `sky-02-signoff` (20 ns) | `sky-03-clk26` (26 ns) | Delta |
|---|---|---|---|
| Period | 20 ns | 26 ns | **+6.000 ns** |
| Worst setup, `nom_tt_025C_1v80` | +8.2312 | +11.7842 | +3.553 |
| Worst setup, `nom_ss_100C_1v60` | -3.3056 | -2.7008 | **+0.605** |
| Worst setup, `max_ss_100C_1v60` | -3.8504 | **-3.2007** | **+0.650** |
| Setup violations, all corners | 536 | **513** | -23 |
| Max-slew violations, `max_ss` | 1,526 | **1,750** | +224 |
| Timing-repair buffers | 1,558 (12,759.7 um2) | 1,547 (12,751.0 um2) | -11 |
| Placed standard cells | 84,801.3 um2 | 84,576.1 um2 | -0.27 % |

**Six nanoseconds of extra period bought 0.65 ns at the slow corner**,
and the repair-buffer count barely moved. The flow spent the relaxation
at the typical corner — where it was already 8 ns clear — and returned
almost none of it to the corner that was failing. Max-slew at `max_ss`
got *worse*.

The mechanism is in the tool, and it is readable in this run's own step
metrics rather than inferred:

- **Every place-and-route step is single-corner.**
  `OpenROADStep.run` sets `corners = PNR_CORNERS or [DEFAULT_CORNER]`
  (`librelane/steps/openroad.py:351`), and `PNR_CORNERS` resolves to
  `null` here, so `DEFAULT_CORNER` — `nom_tt_025C_1v80` — is the only
  corner loaded. Confirmed directly: the `or_metrics_out.json` of
  `36-openroad-stamidpnr-1`, `38-openroad-stamidpnr-2` and
  `43-openroad-stamidpnr-3` each contain **exactly one**
  `timing__setup_vio__count__corner:*` key, and it is the `tt` one.
  Nothing inside the PnR loop ever computes an `ss` number.
- **The resizer is the exception, and it runs too early to help.**
  `ResizerStep` overrides that with `RSZ_CORNERS or STA_CORNERS`
  (`openroad.py:2393`), so `37-openroad-resizertimingpostcts` really does
  load all nine corners — its log reads all three `ss` libraries
  **[fact, grepped]**. But it runs post-CTS on *estimated* parasitics and
  inserted only **22 setup buffers** against 779 hold buffers. The
  post-route extraction then moves the `ss` corner negative.
- **There is no repair step after routing.** LibreLane skips both
  `Repair Design (Post-Global Routing)` and `Resizer Timing Optimizations
  (Post-Global Routing)` by default, in this run as in the IHP one
  (docs/12 section 4) **[fact, `Skipping step` lines in the flow log]**.
- **So the nine-corner STA at `55-openroad-stapostpnr` is the first and
  only place the `ss` corner is evaluated on real parasitics**, and by
  then nothing downstream can act on it.

**What would actually be needed [estimate — not run here]:** put the slow
corner inside the optimization loop rather than only inside the final
report — `PNR_CORNERS` including `nom_ss_100C_1v60`, or `DEFAULT_CORNER`
moved to it — and re-close. Enabling the post-global-routing repair steps
would give the flow a second chance after extraction. `CLOCK_PERIOD` is
the wrong knob and this run is the evidence for that. Estimating the
achievable sky130 frequency from these two runs is not sound: both were
optimized against `tt`, so neither measures what the design can do when
`ss` is the target.

**Everything else in `sky-03-clk26` reproduces `sky-02-signoff`.** Magic
DRC 0, KLayout DRC 0, Netgen LVS 0, antenna 0/0, XOR 0, route DRC 0, and
the manufacturability report again carries exactly three `Passed` lines.
Placed area moved 0.27 %, utilization 56.69 % against 56.84 %, routed
wirelength 315,505 um against 315,780, 54 antenna diodes against 57,
max-fanout 75 against 77, power 3.818 mW against 4.960 mW (the period is
30 % longer, so the switching term drops). The manufacturability result
of section 3.1 is therefore not an artefact of one particular
constraint.

#### 3.3c Max-fanout, disclosed on both PDKs [fact]

`design__max_fanout_violation__count` is **77 on sky130** and **72 on
IHP**, identical across every corner on each (fanout is a netlist
topology property; PVT does not move it). Decomposed from
`55-openroad-stapostpnr/nom_tt_025C_1v80/checks.rpt`, the sky130 77 are
**72 CTS clock-tree buffers** (`clkbuf_leaf_*`, at 15 loads against a
limit of 10) and **5 resizer-inserted fanout buffers**. **Not one is an
RTL net** — every violator is a cell this flow inserted itself.

The *binding limit* differs between the PDKs even though the counts are
close. `sky130_fd_sc_hd__tt_025C_1v80.lib` declares **no**
`default_max_fanout` at all, so the design's
`MAX_FANOUT_CONSTRAINT: 10` binds; `sg13g2_stdcell_typ_1p20V_25C.lib`
declares `default_max_fanout: 8`, which is tighter than the same
constraint and binds instead (docs/12 section 4.4a). The Classic flow
instantiates no max-fanout checker step on either PDK, so neither number
gates anything. Max cap is 0 at all nine sky130 corners, which is what
max-fanout is a proxy for.

### 3.4 Routing and antenna [fact]

| Quantity | **sky130A** | ihp-sg13g2 |
|---|---|---|
| Routing layers offered to the router | met1 .. met4 (**4**) | Metal2 .. TopMetal1 (**5**) |
| Global-route wirelength | 433,423 um | 467,618 um |
| Final routed wirelength | **315,780 um** | 335,406 um |
| Longest net | **766.69 um** | 1,310.02 um |
| Detailed-route DRC, main route | 5,329 -> 3,261 -> 2,668 -> 353 -> 19 -> **0** (6 iterations) | 2,938 -> 1,192 -> 1,205 -> 45 -> **0** (5 iterations) |
| Antenna after global routing | **37 nets / 50 pins** | **0 / 0** |
| Antenna after detailed routing | **0 / 0** | 0 / 0 |
| Antenna diodes in the final layout | **57** (142.637 um2) | **0** |

---

## 4. What differed, and why

### 4.1 The library

`sky130_fd_sc_hd` has **428** Liberty cells against `sg13g2_stdcell`'s
**84**, three flip-flop flavours against one, and a 2.72 um row against
3.78 um. The consequences visible in this run are the ones section 3.2
lists: a 37.7 % smaller placed design, half the timing-repair buffer
area, no tie-high cells, and 2,700 um2 of well taps that sg13g2 does not
need. Richer library, denser result — and still a slower slow corner,
which is a process statement rather than a library one.

### 4.2 Antenna is the one place the two flows genuinely diverge [fact]

On IHP this design had **zero antenna violations at every stage** and
inserted **zero diodes**. On sky130 it had **37 violating nets and 50
violating pins after global routing**, and the repair sequence ran to
completion in two places:

- `42-openroad-repairantennas` (post-global-routing): 44 -> 17 -> 20 ->
  2 -> 1 -> **0** violations, inserting **32 diodes** and **59 jumpers**.
- `44-openroad-detailedrouting`'s own repair
  (`DRT_ANTENNA_REPAIR_ITERS: 3`, the default): after the main route
  reached 0 DRC errors, `check_antennas` found **22** violations, and
  three repair-and-reroute passes inserted **25 more diodes** (23 + 1 +
  1). Each pass reopened DRC errors that the router then closed again —
  804 -> 240 -> 199 -> 5 -> 0, then 20 -> 2 -> 1 -> 0, then 5 -> 0.

Final state: **57 antenna cells, 142.637 um2, 0.17 % of the core**, and
**0 violating nets / 0 violating pins** at `46-openroad-checkantennas-1`.

**Nothing was configured to make this happen.** `RUN_HEURISTIC_DIODE_INSERTION`
is `false` here, exactly as docs/12 section 4.5 measured it should be on
IHP; the repair that mattered was the router's, at defaults. The contrast
with docs/12's `aer_fifo` finding is instructive: there, turning the
*heuristic* on cost 4,641 diodes and 11.4 % of the core for the same
zero-violation result. Here the flow reached zero with 57 diodes and 0.17
% — so the docs/12 decision to leave the heuristic off transfers to
sky130 unchanged, and the evidence for it is now stronger, because on
sky130 there were real violations for the router to fix rather than none.

The cause is structural, not a design defect: sky130 gives the router
**four** metal layers to met4 where sg13g2 gives it **five** to
TopMetal1, on a die **42.5 % smaller**. Long met1/met2 runs before a
via-up are what antenna rules punish.

### 4.3 What did NOT need changing [fact]

The list is longer than the delta, and it is the actual portability
result:

- **No RTL change of any kind.** The same seven files, byte for byte,
  produced both layouts. `grep -niE "sg13g2|sky130"` over `hw/rtl/*.v`
  returns only comments.
- **Zero lint errors, and the same 90 warnings.** Verilator 5.051 with
  `LINTER_INCLUDE_PDK_MODELS: 1` reports `design__lint_error__count: 0`
  and `design__lint_warning__count: 90` on sky130 — the identical figure
  docs/15 section 5.2 measured for the current `hw/rtl` tree. Since that
  step feeds Verilator the *PDK's* blackbox models, the warning count
  proving PDK-independent is a small but real confirmation that the
  warnings belong to the RTL and not to the technology.
- **Zero unmapped instances.** `Checker.YosysUnmappedCells` reports
  `design__instance_unmapped__count: 0`, so the docs/15 section 4.2
  reasoning about *not* copying the sibling project's
  `SYNTH_HIERARCHY_MODE: deferred_flatten` workaround holds on sky130
  too.
- **No PDN, macro, blackbox or halo workaround.** docs/12 sections 7.2 to
  7.4 record three IHP-specific integration defects around the SRAM macro
  (PDN grid not reaching Metal4 macro pins, Magic streamout aborting on a
  missing prBoundary layer, corner-name mismatch). None of them has a
  sky130 analogue here, because this design instantiates no macro.
- **No config workaround for the flow itself.** The five PDK keys in 2.4
  are data, not fixes: each is looked up from the technology's own
  `tile_sizes.yaml` / `tech.py`. There is no equivalent of docs/12
  section 2.4's traps in this run.

---

## 5. The wafer.space gate, applied to this result

`gds-wafer-space.yaml` gates on LibreLane's own manufacturability report.

*(This section reproduces three non-ASCII marker characters literally,
against this repository's plain-text convention, because they are the
data: the gate is a `grep` for exact byte sequences, caveat 1 below turns
on two of them not being the same character, and paraphrasing any of them
would make the commands here wrong.)*

```yaml
- name: Verify manufacturability (Antenna / LVS / DRC)
  run: |
    got=$(grep -c 'Passed ✅' librelane.log || true)
    if [ "$got" -ne 3 ] || grep -q '❌' librelane.log; then
      echo "::error::Manufacturability check did not report 3x Passed (got $got)"
      exit 1
    fi
```

That text is produced by `Misc.ReportManufacturability`
(`librelane/steps/misc.py`), which is stage 80 of the Classic flow and
writes `manufacturability.rpt` as well as printing it. Ours, verbatim
from `76-misc-reportmanufacturability/manufacturability.rpt`:

```
* Antenna
Passed ✅

* LVS
Passed ✅

* DRC
Passed ✅
```

Applying the gate's own two conditions to that file:

| Gate condition | Required | **Measured** | |
|---|---|---|---|
| `grep -c 'Passed ✅'` | `== 3` | **3** | pass |
| `grep -q '❌'` | absent | **0 occurrences** | pass |

**Verdict: YES — the check would have gone green**, on these numbers:
Antenna 0 violating nets and 0 violating pins; LVS 0 on all seven
counters; DRC 0 from Magic and 0 from KLayout. **[fact]**

Three caveats, all real, and the first two are about the gate rather
than about us.

1. **The `❌` condition is dead code.** LibreLane's failure marker is
   `Failed 𐄂` (U+10102), not `❌` (U+274C), and `❌` appears nowhere in
   `misc.py`. The gate's only working test is the `-ne 3` count — which
   is sufficient, because a failure replaces a `Passed ✅` line, but the
   second condition never fires and would not add the safety it looks
   like it adds.
2. **The count is 3 only if the report is printed.** `misc.py` guards the
   `print` with `if not options.get_condensed_mode()`. A LibreLane run in
   condensed mode writes `manufacturability.rpt` but emits nothing to the
   log, so `got` would be 0 and the gate would fail a perfectly good
   design. Grepping the report file rather than the log would be
   strictly better.
3. **`* DRC / Passed` means whatever DRC steps ran.** `misc.py` treats a
   skipped deck as `N/A` and only fails on a positive count, so with the
   Tiny Tapeout default `RUN_KLAYOUT_DRC: 0` the DRC line is a statement
   about Magic alone. This run enabled both (2.4), so our green covers
   both decks. Anyone reproducing this against the stock Tiny Tapeout
   config is testing something weaker.

And the caveat about us: **the gate says nothing about timing.** Antenna,
LVS and DRC are all clean while the slow corner misses setup by 3.85 ns.
Section 6 is what follows from that.

---

## 6. What portability does and does not prove

**Proved, and now measured rather than argued:**

- The RTL is technology independent in the way that matters for
  manufacturing. Two PDKs with different row heights, different supply
  voltages, different metal stacks and a 5x difference in library size
  produce DRC-, LVS- and antenna-clean layouts from byte-identical
  sources, with no conditional code and no per-PDK patch.
- The *configuration* is portable too, and cheaply: five keys, all of
  them data looked up from the target technology's own files rather than
  tuned by hand.
- The design is not accidentally relying on an IHP-specific structure. If
  it were — an inferred latch, a cell the other library lacks, a
  hierarchy the other synthesis flattens differently — synthesis or LVS
  would have said so. Both were silent, and `design__instance_unmapped__count`
  is 0.
- The docs/15 place-and-route growth calibration (1.26) survives a PDK
  change to within 0.8 %, which makes it usable for planning a third
  technology rather than only this one.

**Not proved, and the list is longer than the first one:**

- **Timing does not port, and this run is the counter-example.** Same
  RTL, same constraint, +5.31 ns of slow-corner slack on IHP and -3.85 ns
  on sky130. Any statement of the form "the design runs at 50 MHz" is a
  statement about a PDK, not about the design. `tt/info.yaml`'s
  `clock_hz: 50000000` is correct for the IHP submission it describes and
  would be wrong on a sky130 shuttle without a re-close.
- **The sky130 frequency is not established by this work.** Section 3.3b
  showed that relaxing the period barely moves the failing corner,
  because the optimization loop never sees it. Both runs recorded here
  were optimized against `tt`, so **neither measures what the design can
  do on sky130 when `ss` is the target**. Quoting 41.9 MHz as a sky130
  capability would be wrong in the same way quoting 50 MHz would be; the
  honest statement is that the number is unknown until a run with the
  slow corner inside `PNR_CORNERS` is made, and that run has not been
  made.
- **This is not a sign-off on either PDK.** Only nominal-to-max
  interconnect corners with no signal-integrity analysis; no
  `VSRC_LOC_FILES`, so the IR numbers are indicative; no formal
  equivalence check between RTL and the final netlist (`Yosys.EQY` is
  gated off in both runs).
- **Nothing here was simulated.** The docs/15 section 5.4 gate-level
  smoke test ran against the *IHP* post-route netlist. The sky130 netlist
  has not been simulated at all, and the docs/15 section 5.4 Icarus trap
  (undriven `delayed_*` signals from unimplemented `$setuphold`) is a
  sg13g2 model property that may or may not have a sky130 analogue —
  untested.
- **This is not the Tiny Tapeout sky130 flow.** `gds-sky130.yaml` runs
  `tt-gds-action@ttsky26a`, which pins its own LibreLane and adds the
  precheck — the pin-placement check against the mux, top-level
  uniqueness, and its own DRC deck — plus `gl_test` at `CLOCK_MHZ: 4`.
  None of those ran here. A local Classic-flow close is strong evidence
  that the shape and the configuration are right; it is not the artefact
  that gets manufactured.
- **Two PDKs is two data points.** Both are open PDKs consumed through
  ciel and hardened by the same LibreLane. A commercial PDK, a different
  flow, or a technology with a macro requirement (docs/12 section 7 is
  what that looks like when it goes wrong) would each be a fresh
  question.
- **Portability is not a reason to port.** Nothing in this document
  argues that a sky130 tape-out is worth doing. It establishes that the
  option is open at a known cost — a clock re-close and a slower part —
  and that is the whole claim.

**The one-sentence version:** the design is manufacturably portable and
temporally not, which is exactly the distinction a gate that checks
Antenna, LVS and DRC cannot make for you.

---

## 7. Reproducing this

```
# nothing is installed; the PDK is already enabled at the LibreLane pin
export PDK_ROOT=$HOME/.ciel
ls -la $PDK_ROOT/sky130A     # -> ciel/sky130/versions/8afc8346.../sky130A

# the run recorded in section 3
hw/openlane/pilot_sky130/run_sky130.sh --run-tag sky-02-signoff

# the relaxed-clock run of section 3.3b
hw/openlane/pilot_sky130/run_sky130.sh --run-tag sky-03-clk26 -c CLOCK_PERIOD=26

# the gate of section 5, applied by hand
R=hw/openlane/pilot_sky130/runs/sky-02-signoff/76-misc-reportmanufacturability
grep -c 'Passed ✅' $R/manufacturability.rpt     # must be 3
```

If the PDK is not enabled, `run_sky130.sh` refuses to run and prints the
`ciel enable --pdk-family sky130 <hash>` line to fix it, or accepts
`ENABLE_PDK=1` to do it itself. `tt/tt/` must be present (2.4).

Files this document owns: `hw/openlane/pilot_sky130/config.json`,
`hw/openlane/pilot_sky130/run_sky130.sh`, and itself.
