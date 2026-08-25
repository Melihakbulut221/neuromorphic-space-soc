# SG13G2 flow bring-up, `aer_fifo` trial harden, and the RM_IHPSG13 decision

Evidence file for ROADMAP gate **G0** ("sg13g2 trial harden DRC/LVS clean")
and for the **2026-09-07** internal go/no-go on the RM_IHPSG13 SRAM macro
(ROADMAP work item 2, budgeted in docs/06 section B.6.1). It answers three
questions:

1. Does an IHP SG13G2 RTL-to-GDS flow run to signoff in this rootless
   environment, and against which pinned tool and PDK versions?
2. What does a real block (`hw/rtl/aer_fifo.v`) cost on SG13G2, and does
   it close DRC, LVS and antenna?
3. Can an RM_IHPSG13 SRAM macro be hardened in the same flow, inside the
   Tiny Tapeout block geometry the pilot would use?

Convention used throughout: **[fact]** = measured in this environment or
read out of the installed PDK; **[estimate]** = derived or judged.
Sections 2-7 are measured unless a paragraph is marked otherwise.

**Headline, 2026-08-25.**

- **G0 is met.** `aer_fifo` hardened end to end on SG13G2: Magic DRC 0,
  KLayout DRC 0, Netgen LVS 0 errors on every count, XOR 0, antenna 0,
  timing clean on all three corners. Run `trial-03-signoff`, 80 stages,
  11.3 minutes of tool time. Section 4. **[fact]**
- **The RM_IHPSG13 macro run was made, and it splits cleanly in two.**
  One `RM_IHPSG13_1P_512x32_c2_bm_bist` in a registered wrapper, placed
  inside an 854.40 x 340.20 um die — the *interpolated* 4x2 Tiny Tapeout
  block this document used to print; the measured 4x2 block is
  854.40 x 313.74 um and 8.4 % smaller (6.5):
  - **Physical implementation passes.** Detailed routing into the
    macro's 188 bottom-edge Metal2 pins closed with 0 DRC errors and 0
    antenna violations, and timing closed at 50 MHz with 13.07 ns
    slow-corner slack. The pin-access failure this document previously
    predicted as most likely did not happen. Two flow-side integration
    defects did and both were worked around in
    `hw/openlane/sram_pilot/`: LibreLane's default macro PDN grid never
    reaches the macro's Metal4 supply pins, and Magic GDS streamout
    aborts because the macro GDS carries no prBoundary layer.
    Sections 7.2-7.4. **[fact]**
  - **Signoff fails.** Magic DRC **1,106,478 error boxes** (the report
    prints "Should be divided by 3 or 4" beneath that total, so roughly
    277,000-369,000 distinct violations **[estimate]**) and KLayout DRC
    **2,316** errors, **100 % of both inside the macro** and none in the
    surrounding design; Netgen LVS **359** errors, driven by the
    CDL-versus-GDS hierarchy naming and by a bus-delimiter mismatch
    (`A_DIN[16]` extracted versus `A_DIN<16>` in the CDL). Section 7.5.
    **[fact]**
- **Recommendation: NO-GO on RM_IHPSG13 for TTIHP26b, decidable now
  rather than on 2026-09-07.** The gate as docs/06 B.6.1 worded it is
  already answered, under conditions easier than it asks for, and both
  blocking causes are upstream of this repository. Separately, the macro
  named for that gate in docs/06 B.6 did not fit the block it was gated
  against; docs/06 has since been corrected on both counts. Sections 8
  and 10.1.

Run trees under `hw/openlane/*/runs/` are **gitignored** and do not
travel with the repository. Every number below is therefore quoted here
in full, with the run tag and step directory it came from, so this file
remains the evidence after the trees are deleted.

---

## 1. Scope

Design under test for the bring-up: `hw/rtl/aer_fifo.v` at `WIDTH=16`,
`DEPTH=64` — the EVQ geometry of docs/10 section 7.1. It was picked as
the bring-up vehicle because it is small enough to iterate on, it is
already verified (11 cocotb tests, four SymbiYosys proofs), and it is
memory-shaped: a 1024-bit storage array in flip-flops is exactly the
thing the SRAM-macro decision is about.

Design under test for the macro decision: `hw/openlane/sram_pilot/`, one
`RM_IHPSG13_1P_512x32_c2_bm_bist` in a registered wrapper and nothing
else, on the interpolated 4x2 die (6.5). It is flow-experiment scaffolding, deliberately kept out of
`hw/rtl/`; it is not part of any pilot submission.

Non-goals: this is not a timing exploration and not a Tiny Tapeout tile
submission. No ECC wrapper is built around the macro here — the decision
this document has to inform is whether the macro closes at all, and that
question is answered without one.

Everything this work *produced* lives in `hw/openlane/`, but the claim
an earlier revision made here — "nothing outside that directory and this
file was modified" — was not true, and the exceptions are load-bearing
rather than incidental:

- **`.gitignore`** gained `hw/openlane/runs/` and `hw/openlane/*/runs/`.
  Section 9's statement that run trees are gitignored is a statement
  about that file, not about this one; without the entry, a 1.6 GB tree
  of build output would be staged on the next `git add`.
- **`ROADMAP.md`** gate G0 carried a status note saying "no retained run
  has yet reached a DRC result and LVS has not executed". Section 4.1
  retired it; the integrator has since replaced it with the
  `trial-03-signoff` result and a pointer to this file. That change was
  requested in section 10.1 and has been made.
- **`docs/06-funding-and-shuttle.md`** sections B.6 and B.6.1 were
  rewritten in response to the errata this document raises in 6.5 and
  10.1 — the `1024x8` macro that does not fit, and the tile count.

Both `.gitignore` and `ROADMAP.md` are integrator-owned, so those two
edits were requested here and made there rather than made from this
workstream. The general rule this replaces the old sentence with: this
document owns `hw/openlane/` and itself, and every change it needs
elsewhere is named — here, in 10.1, or in both.

---

## 2. Toolchain

### 2.1 Rootless chain

No root, no container, no system package installation. Binaries are
user-local builds or extracted release tarballs; each is fronted by a
one-line shim in `~/.local/opt/llbin` that sets the environment that
binary — and only that binary — needs. The shims exist because the
OpenROAD build ships its own newer glibc: exporting its `LD_LIBRARY_PATH`
globally segfaults every other host binary. `hw/openlane/run_trial.sh`
therefore does `unset LD_LIBRARY_PATH` before dispatching and lets each
shim re-establish its own.

This chain is inherited, not invented here: it was built for
`tt-um-lif-crossbar` and has already carried a full SKY130 MVP to a
DRC/LVS/antenna-clean GDS in a sibling project on this machine. The
SG13G2 work in this document is the first use of it on a non-SKY130 PDK.

### 2.2 Pinned versions [fact]

Recorded 2026-08-25 in this environment.

| Component | Version | How it is reached |
|---|---|---|
| LibreLane | v3.0.5 | `~/Documents/caravel-lif-crossbar/.venv-flow/bin/librelane` |
| Ciel (PDK manager) | v2.6.1 | same venv |
| Python | 3.12.3 | same venv |
| OpenROAD | 26Q1-2938-g0e2d771c5e | shim -> ORFS install tree |
| Yosys | 0.67 (2d1509d1b) | shim -> oss-cad-suite |
| KLayout | 0.30.9 | shim (sets `RUBYLIB`, `KLAYOUT_PATH`) |
| Magic | 8.3.678 | shim -> `~/.local/opt/magic-8.3.678` |
| Netgen | 1.5.272 | shim |
| IHP-Open-PDK | `c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c` | ciel, under `~/.ciel` |
| Standard-cell library | `sg13g2_stdcell` (84 Liberty cells) | in the PDK |

The Yosys build string is read from the synthesis report of
`trial-03-signoff` (`06-yosys-synthesis/reports/stat.json`), which is the
authority on what actually ran.

The PDK version is **not** chosen by us. Every LibreLane release ships
`librelane/pdk_hashes.yaml` naming the IHP-Open-PDK commit it was tested
against; for v3.0.5 that is `c4b8b4e5...`. `run_trial.sh` reads the pin
out of the installed wheel and refuses to run against anything else, so
the assertion stays correct across LibreLane upgrades instead of
hard-coding a hash that goes stale silently.

Answering the "which release or branch" question from the brief
directly: the supported 2026 path is **whatever commit the LibreLane
release pins**, consumed through ciel, not a Git tag of IHP-Open-PDK
chosen independently. ciel 2.6.1 carries `ihp-sg13g2` as a first-class
family (`ciel/families.py`), so `--pdk-family ihp-sg13g2` works the same
way `sky130` does. Volare is not involved; ciel is its successor and is
what LibreLane 3.x calls. **[fact]**

### 2.3 PDK install, outside the repository [fact]

```
export PDK_ROOT=$HOME/.ciel                 # NOT inside the repo
ciel ls-remote --pdk-family ihp-sg13g2      # list published versions
ciel enable --pdk-family ihp-sg13g2 c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c
```

`ciel enable` downloads into
`$PDK_ROOT/ciel/ihp-sg13g2/versions/<hash>/` (787 MB) and repoints the
`$PDK_ROOT/ihp-sg13g2` symlink at it. Both the LibreLane ciel wrapper and
the PDK's own `config.tcl` files resolve through that symlink, so exactly
one version is live at a time.

Installed content:

```
~/.ciel/ihp-sg13g2/
  libs.ref/   sg13g2_stdcell  sg13g2_io  sg13g2_sram  sg13g2_pr
  libs.tech/  librelane  klayout  magic  netgen  openroad  ngspice  xschem  ...
```

### 2.4 Three traps

**(a) `--pdk` must be on the command line.** LibreLane's ciel wrapper
resolves and installs the PDK from the CLI option (default `sky130A`)
*before* the config file is parsed, then points `PDK_ROOT` at that
version's directory. With the default, `"PDK": "ihp-sg13g2"` in
`config.json` is then looked up inside the sky130 tree and the run dies
with "PDK not found". `run_trial.sh` always passes
`--pdk ihp-sg13g2 --scl sg13g2_stdcell`. **[fact]**

**(b) A stale enabled version does not announce itself.** This
environment had an older IHP-Open-PDK (`22f2a25f...`) enabled from an
earlier attempt while the LibreLane-pinned `c4b8b4e5...` sat downloaded
but not linked. Nothing in the flow would have complained; it would
simply have hardened against an untested PDK. Hence the assertion in
`run_trial.sh`:

```
$ PDK_ROOT=/nonexistent hw/openlane/run_trial.sh
PDK version mismatch.
  enabled: <none>
  pinned:  c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c  (librelane v3.0.5)
Fix with: ciel enable --pdk-family ihp-sg13g2 c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c
      or: ENABLE_PDK=1 hw/openlane/run_trial.sh
```

**(c) Config keys fail in three different ways, and only one of them is
visible where you would look for it.** This was probed directly with a
throwaway config carrying one deprecated key, one invented key, and the
PDK's own `MACRO_BLOCKAGES_LAYER`, run to `Verilator.Lint`.

- A **renamed** key is honoured and warns. `GRT_REPAIR_ANTENNAS`,
  carried over from the SKY130 config, is declared in
  `librelane/flows/classic.py` as
  `deprecated_names=["GRT_REPAIR_ANTENNAS"]` on the live variable
  `RUN_ANTENNA_REPAIR`. Setting `"GRT_REPAIR_ANTENNAS": false` produced
  `RUN_ANTENNA_REPAIR = False` in `resolved.json` — it changes
  behaviour — together with the console line "The configuration variable
  'GRT_REPAIR_ANTENNAS' is deprecated. Please check the docs for the
  usage on the replacement variable 'RUN_ANTENNA_REPAIR'." It is neither
  ignored nor silent. **[fact — measured]**
- An **unknown key in the user config** warns and is dropped:
  "An unknown key 'THIS_KEY_DOES_NOT_EXIST_ANYWHERE' was provided." It
  does not appear in `resolved.json`. **[fact — measured]**
- An **unknown key set by the PDK itself is silent everywhere.** The
  PDK's `libs.tech/librelane/config.tcl` sets
  `MACRO_BLOCKAGES_LAYER "Metal1 Metal2 Metal3 Metal4 Metal5 TopMetal1"`,
  and that string appears **nowhere in LibreLane 3.0.5** — zero hits
  across the installed package. It never reaches `resolved.json`, and
  neither `trial-03-signoff` nor `macro-03` logged a single "An unknown
  key" line: the warning path applies to the user config, not to values
  injected from the PDK Tcl. Anything a reader infers from its presence
  in the PDK config — for instance, that the PDN generator will keep off
  those layers over a macro — is not true of this tool version.
  Section 7.3 is what that costs in practice. **[fact — measured]**

Cutting across all three: **none of these warnings reaches
`warning.log`.** That file is written by the flow's step-warning
collector, which does not exist yet when the config is compiled. In every
probe run `warning.log` was **empty** while the console carried the
warnings. Reading `warning.log` after the fact is therefore *not* a way
to find a bad config key.

The working rule is therefore: after any config change, read
**`<run>/resolved.json`** — the fully resolved configuration, written
**once per run at the run root**. A key that is absent there had no
effect, whatever the PDK or an older OpenLane config suggests.

There is **no per-step `resolved.json`**, and an earlier revision of
this document sent the reader looking for one in both this section and
section 9. What a step directory holds is `config.json`, which is the
**subset** of the resolved configuration that that step consumes. On
`trial-03-signoff`: exactly one `resolved.json`, at the run root, with
**411 keys**; and **76** step `config.json` files carrying **79 to 123**
keys each **[fact — counted]**. The difference is not academic, because
the subset is small enough to give false negatives on the very keys this
section is about:

| Key | In `<run>/resolved.json` | In a step `config.json` |
|---|---|---|
| `RUN_ANTENNA_REPAIR` | `true` | **in none of the 76** |
| `SYNTH_PARAMETERS` | `["WIDTH=16", "DEPTH=64"]` | only in `05-yosys-jsonheader` and `06-yosys-synthesis` |
| `CLOCK_PERIOD`, `FP_CORE_UTIL`, `PDK` | present | present in the steps that use them |

So the deprecated-name check in (a) above — "`GRT_REPAIR_ANTENNAS`
became `RUN_ANTENNA_REPAIR = False`" — is confirmable at the run root
and **nowhere else in the tree**. Looking for it per step would have
reported the key as absent and led to the opposite conclusion. Step
`config.json` is still useful, for the narrower question "which values
did *this* step actually see"; it is not the place to check whether a
key took effect at all.

---

## 3. Configuration

`hw/openlane/aer_fifo/config.json`, run by `hw/openlane/run_trial.sh`.
The rationale for each choice is carried inline in the config file as
`//`-prefixed comments so it travels with the settings; the load-bearing
ones:

- **`CLOCK_PERIOD: 30`** (33 MHz). Deliberately loose. The recorded
  lesson from the sibling SKY130 project is that an unreachable
  constraint manufactures thousands of phantom violations and buries the
  real integration failures underneath them. The experiment here is PDK
  and flow integration, not frequency. What the block *can* do is read
  off the achieved slack (section 4.4) rather than asserted up front.
- **`FP_SIZING: relative`, `FP_CORE_UTIL: 40`.** Let the flow pick the
  die and measure the achieved utilization; that number is what feeds the
  tile budget in docs/06 section B.6.
- **`SYNTH_PARAMETERS: WIDTH=16, DEPTH=64`.** These are the module
  defaults, pinned explicitly so the numbers below are a property of this
  config and not of the RTL header. They are **not** cosmetic: see
  section 4.7.
- **`RUN_HEURISTIC_DIODE_INSERTION: false`.** Measured decision, see
  section 4.5.

The macro run uses a second config, `hw/openlane/sram_pilot/config.json`,
described where its settings are earned in section 7.

---

## 4. Trial harden results — `aer_fifo` [fact]

All numbers in this section come from run tag **`trial-03-signoff`**,
executed 2026-08-25, 08:50:58 to 09:02:18 local, from
`hw/openlane/aer_fifo/config.json` exactly as committed, via
`hw/openlane/run_trial.sh --run-tag trial-03-signoff`. The Classic flow
reported **80 stages** and produced **76 numbered step directories**;
the four that did not run are gated off by default or by this config —
Repair Design (Post-Global Routing), Heuristic Diode Insertion (4.5),
Resizer Timing Optimizations (Post-Global Routing), and Equivalence
Check. Summed step runtime **680.4 s = 11.3 minutes** on 20 threads.

### 4.1 Outcome

| Signoff check | Step | Result |
|---|---|---|
| Magic DRC | `64-magic-drc` | **0 errors** |
| KLayout DRC (deep, `no_recommended`) | `65-klayout-drc` | **0 errors** |
| Netgen LVS | `70-netgen-lvs` | **0** on all seven LVS counters |
| Magic illegal overlap | `69-checker-illegaloverlap` | 0 |
| KLayout XOR (Magic GDS vs KLayout GDS) | `62-klayout-xor` | 0 differences |
| Antenna, post-detailed-routing | `46-openroad-checkantennas-1` | 0 violating nets, 0 violating pins |
| Detailed-routing DRC | `44-openroad-detailedrouting` | 0 |
| Disconnected pins | `48-odb-reportdisconnectedpins` | 0 (0 critical) |
| Power-grid connectivity | `56-openroad-irdropreport` | 0 violations on VPWR and VGND |
| Setup / hold / max-slew / max-cap | `55-openroad-stapostpnr` | 0 violations, all three corners |

The seven Netgen counters are
`design__lvs_error__count`, `..._device_difference__count`,
`..._net_difference__count`, `..._property_fail__count`,
`..._unmatched_device__count`, `..._unmatched_net__count`,
`..._unmatched_pin__count`, all **0**, from
`final/metrics.json`. **This is the artifact ROADMAP G0 asks for.**

### 4.2 Synthesis

From `06-yosys-synthesis/reports/stat.json`: **4,164 cells**, Yosys area
**89,320.455 um2**, of which sequential **52,467.005 um2**. Cell mix, the
part that matters:

| Cell | Count | Why |
|---|---|---|
| `sg13g2_dfrbpq_1` | 1,071 | 1,024 memory bits + 47 control/pointer bits |
| `sg13g2_mux2_1` | 1,025 | read mux tree |
| `sg13g2_tiehi` | 1,024 | one per memory bit, purely to hold `RESET_B` inactive |
| `sg13g2_a22oi_1` | 497 | |
| `sg13g2_nand4_1` | 149 | |
| `sg13g2_nor3_1` | 95 | |
| others (19 types) | 303 | |

The 1,024 tie-high cells are not a synthesis mistake; they are what
SG13G2 costs for an unreset array. Section 5.

### 4.3 Floorplan and area

From `13-openroad-floorplan/or_metrics_out.json` and
`final/metrics.json`:

| Quantity | Value |
|---|---|
| Die bounding box | 0 0 **484.115 x 502.835** um |
| Die area | 243,430 um2 = **0.2434 mm2** |
| Core area | 223,171 um2 |
| Core bounding box (floorplan) | 5.76 15.12 478.08 **487.62** um |
| Placement utilization (target 40 %) | **40.03 %** |
| Utilization after fill insertion | 51.35 % |

The core margins are not free parameters: 5.76 um is 12 x the 0.48 um
`CoreSite` width, 15.12 um is 4 x the 3.78 um row height.

The core bounding box row is corrected in this revision. An earlier
revision printed `5.76 15.12 478.08 483.84`, which is
`trial-01`/`trial-02-nohdi`'s core box, inside a table whose header says
every number comes from `trial-03-signoff`. The two are not
interchangeable and the table contradicted itself: 472.32 x 468.72 =
221,386 um2, which is the superseded runs' core area, not the 223,171
um2 on the row above. `trial-03-signoff`'s box is 472.32 x 472.50 =
**223,171 um2**, which closes against its own core-area row exactly.
Both figures read from `13-openroad-floorplan/or_metrics_out.json` in
the respective run trees **[fact]**. Section 4.7 is the general form of
this trap: the run tag has to be stated, because "the same design" is
not the same netlist — and, as this row shows, not the same floorplan
either.

Instance counts through the flow: 4,164 after synthesis; **6,008
non-fill instances** in the final layout, after CTS and timing repair
have added to it; 18,166 instances in total once the 12,158 fill cells
are counted. Timing repair contributed **1,668 buffers** (22,039.5 um2),
of which 1,095 are hold buffers and **0 are setup buffers** — a direct
consequence of the loose clock. CTS added 121 clock buffers and 52 clock
inverters (3,196.97 um2 together).

### 4.4 Timing, all three corners

From `55-openroad-stapostpnr/summary.rpt`, post-layout, parasitics from
OpenRCX:

| Corner | Setup worst slack | Hold worst slack | Violations |
|---|---|---|---|
| `nom_slow_1p08V_125C` | **18.0553 ns** | 0.6397 ns | 0 |
| `nom_typ_1p20V_25C` | 20.1784 ns | 0.3024 ns | 0 |
| `nom_fast_1p32V_m40C` | 21.4717 ns | **0.1130 ns** | 0 |

Setup TNS and hold TNS are 0 at every corner. Clock skew is 0.264-0.277
ns for setup and -0.265 to -0.273 ns for hold. 68 nets are unannotated by
the parasitics extractor, all of which the flow's own filter classifies
as expected (`timing__unannotated_net_filtered__count = 0`).

Read as frequency: at the slow corner the whole launch-to-capture path
consumes 30 - 18.0553 = **11.945 ns**, i.e. about **83.7 MHz**. That
clears the 50 MHz Tiny Tapeout envelope of docs/06 B.2 with roughly 40 %
margin. **[estimate — this is a single-point extrapolation from a run
closed at 30 ns; re-closing at 12 ns would buffer differently and the
achieved number would move.]**

Note that `TIMING_VIOLATION_CORNERS` defaults to `*typ*` in this PDK
(section 5), so the slow and fast columns above are analysed but do not
by themselves gate the flow. They are reported here because for silicon
they should.

### 4.5 Antenna, and why heuristic diode insertion is off

This is the one place where the config makes a non-default choice, so it
carries the most evidence.

Sequence in `trial-03-signoff`, all with
`RUN_HEURISTIC_DIODE_INSERTION: false`:

| Step | Antenna-violating nets / pins |
|---|---|
| `40-openroad-checkantennas` (after global routing) | 10 / 10 |
| `42-openroad-repairantennas` (post-GRT repair, 0 diodes inserted) | 0 / 0 |
| `46-openroad-checkantennas-1` (**after detailed routing**) | **0 / 0** |

Detailed routing itself inserted **3 `sg13g2_antennanp` cells, 16.33
um2**, through `DRT_ANTENNA_REPAIR_ITERS` (3 iterations, default). The
post-global-routing `OpenROAD.RepairAntennas` step inserted **zero**
diodes; the repair that mattered was the router rerouting.

The comparison run `trial-01` used the same RTL with
`RUN_HEURISTIC_DIODE_INSERTION: true`. There,
`Odb.HeuristicDiodeInsertion` placed diodes ahead of routing and the
design finished with **4,641 `sg13g2_antennanp` cells, 25,261.9 um2 =
11.4 % of the 221,386 um2 core area**, to reach the same
zero-violating-nets result.

So: 3 diodes and 16.33 um2 with the heuristic off, 4,641 diodes and
25,261.9 um2 with it on, identical antenna outcome. Off is right for
this design. **[fact]**

Two honesty notes about this comparison. First, `trial-01` differs from
the committed config in more than the diode flag — see 4.7 — so the
4,641 figure is "the heuristic on this design", not a controlled A/B.
Second, an intermediate run `trial-02-nohdi` was made with the heuristic
off but was killed during detailed routing and never produced a
post-detailed-routing antenna number; it is retained only for the
global-routing row and is not the basis of any claim here.

### 4.6 Routing

From `44-openroad-detailedrouting` and `50-odb-reportwirelength`:

| Quantity | Value |
|---|---|
| Signal nets routed | 5,958 (+2 special) |
| DRC errors per DRT iteration | 58 -> 6 -> 3 -> 0 -> 0 |
| Final routed wirelength | 317,493 um |
| Global-route estimate | 412,106 um |
| Longest net | 1,295.77 um |
| Vias | 37,181, **all single-cut** |
| Detailed-routing runtime | 2 min 38 s |

The router emits `[DRT-0349] LEF58_ENCLOSURE with no CUTCLASS is not
supported. Skipping for layer ...` for Cont, Via1-Via4, TopVia1 and
TopVia2. This is a tech-LEF/tool-version gap, not a design problem, and
it is worth knowing about because it means those enclosure rules are
checked by the signoff DRC decks and not by the router. Both DRC decks
came back clean here, so nothing was actually missed on this design.

Power, from `55-openroad-stapostpnr` at the typical corner, 1.20 V,
33 MHz: total **4.159 mW** (internal 3.355, switching 0.796, leakage
0.0076). Worst IR drop 1.01 mV on VPWR (0.084 %) and 1.90 mV on VGND;
`VSRC_LOC_FILES` is unset, so these are indicative rather than signoff
numbers.

### 4.7 What the earlier runs prove, and what they do not

Four runs exist under `hw/openlane/aer_fifo/runs/`. Only one of them is
evidence for anything in this document, and saying why is the point of
this subsection.

| Run | Config actually used | Reached | Status |
|---|---|---|---|
| `trial-01` | `SYNTH_PARAMETERS` unset, `RUN_HEURISTIC_DIODE_INSERTION: true` | killed at `65-magic-drc`, log 0 bytes | superseded; cited only for the diode comparison in 4.5 |
| `trial-02-nohdi` | `SYNTH_PARAMETERS` unset, heuristic false | killed during `44-openroad-detailedrouting` | superseded; no signoff data |
| `trial-03-signoff` | the committed config, verbatim | all 80 stages | **the evidence** |
| `config-recheck` | the committed config after the comment edits | `--to Yosys.Synthesis` | reproducibility check, see below |

`resolved.json` in both `trial-01` and `trial-02-nohdi` records
`"SYNTH_PARAMETERS": null`. Neither of them ever executed the config that
`hw/openlane/aer_fifo/config.json` now contains, and `trial-01` used the
opposite value of the one flag the config argues about. Before
`trial-03-signoff`, the repository contained a configuration that had
never been run.

That is not only a bookkeeping point. `WIDTH=16, DEPTH=64` are the module
defaults, so pinning them should be a no-op — and it is not:

| | `trial-01` / `trial-02` (parameters unset) | `trial-03-signoff` (parameters pinned) |
|---|---|---|
| Cells after synthesis | 4,160 | **4,164** |
| Yosys area (um2) | 89,266.061 | **89,320.455** |
| `sg13g2_mux2_1` | 1,024 | 1,025 |

Four cells and 54 um2 of difference, from `chparam`-ing a parameter to
the value it already had. The lesson for anyone quoting numbers out of a
run tree: the run tag has to be stated, because "the same design" is not
the same netlist.

**Reproducibility check.** The `//`-prefixed comments in the config were
edited after `trial-03-signoff` finished, so a fourth run
(`config-recheck`, `--to Yosys.Synthesis`) was made from the file
exactly as it now stands. Its `resolved.json` is identical to
`trial-03-signoff`'s — no key added, none removed, no value changed,
including the run-directory paths — and synthesis reproduces 4,164 cells
at 89,320.455 um2. LibreLane drops `//`-prefixed keys without even the
"An unknown key was provided" warning it gives for a genuine typo
(2.4c), which is why the comments can be carried in the config at all.
The committed config is the config that produced section 4. **[fact]**

---

## 5. What `sg13g2_stdcell` is like, measured [fact]

docs/06 section B.7 item 3 asked for the cell-variant gap to be
quantified at the first harden. It is large:

| | `sg13g2_stdcell` | `sky130_fd_sc_hd` |
|---|---|---|
| Liberty cells | **84** | **428** |
| Distinct functions (drive suffix stripped) | 49 | — |
| Row height | 3.78 um (`CoreSite`, 0.48 um site width) | 2.72 um |
| Core voltage | 1.20 V | 1.80 V |
| Routing layers offered to the router | Metal2 .. TopMetal2 | met1 .. met5 |

Consequences seen in this run, not predicted:

- **There is no plain D flip-flop.** Every sequential cell in the
  library is a reset flop or a latch. The complete set is **14 cells —
  9 flip-flops and 5 latches** — enumerated by counting the Liberty
  `ff()` and `latch()` groups in
  `sg13g2_stdcell_typ_1p20V_25C.lib` **[fact]**:

  | Kind | Cells |
  |---|---|
  | flip-flop (`ff()`), 9 | `dfrbp_1/2`, `dfrbpq_1/2`, `sdfrbp_1/2`, `sdfrbpq_1/2`, `sdfbbp_1` |
  | latch (`latch()`), 5 | `dlhq_1`, `dlhr_1`, `dlhrq_1`, **`dllr_1`**, **`dllrq_1`** |

  An earlier revision listed twelve of these as if the list were
  complete and omitted `dllr_1` and `dllrq_1`. The omission is not
  cosmetic: those two are the **active-low-enable** latches. The three
  `dlh*` cells declare `enable : "GATE"` in their Liberty `latch()`
  group and the two `dll*` cells declare `enable : "GATE_N'"`
  **[fact — read from the `latch()` groups]**. So a latch-RAM strategy
  (docs/06 B.4 carries latch RAM as the fallback storage style, and
  section 6.2 below is the argument for why a flop array is expensive)
  that only knows about the `dlh*` half is working with three cells
  where the library offers five, and has no negative-phase latch for a
  two-phase array at all.

  Synthesis therefore mapped the 1,024 unreset FIFO memory
  bits to `sg13g2_dfrbpq_1` and had to tie each `RESET_B` high —
  **1,024 `sg13g2_tiehi` cells, 7,432 um2** (1,024 x 7.2576), purely to
  hold a reset pin inactive. Any block with a large unreset array pays
  this on SG13G2. **[fact]**
- **Drive strengths are sparse.** Most combinational functions exist
  only at `_1` and `_2`; buffers reach `_16`, inverters `_16`, but there
  is no `_4`/`_8` for the majority of gates. Resizer-based timing repair
  has correspondingly less to work with, which argues for the loose
  constraint of section 3 rather than against it. **[fact]**
- **No well-tap or end-cap cells exist**; the PDK config sets
  `FP_TAPCELL_DIST 0` and skips insertion. **[fact]**
- **`TIMING_VIOLATION_CORNERS` defaults to `*typ*`** in the PDK's SCL
  config, i.e. only the typical corner gates the flow's own checkers. The
  slow and fast corners are still *analysed* (section 4.4 reports all
  three), but a violation there would not by itself fail the flow. Worth
  overriding for anything going to silicon. **[fact]**

---

## 6. RM_IHPSG13 SRAM macro inventory — paper study

Everything in section 6 is read out of the installed PDK
(`c4b8b4e5...`). Section 7 is the run that tests it.

### 6.1 What ships [fact]

27 macros, all under `~/.ciel/ihp-sg13g2/libs.ref/sg13g2_sram/`.
Every one of the 27 has a complete view set: LEF, GDS, CDL, Verilog,
datasheet, and three Liberty corners (81 `.lib` files total). There are
no partial entries.

Areas are `W x H` from the LEF `SIZE` statement; `bit/um2` is
`words x bits / area`, recomputed for this revision.

| Macro | Words x bits | kbit | W x H (um) | Area (um2) | bit/um2 |
|---|---|---|---|---|---|
| `RM_IHPSG13_1P_256x8_c3_bm_bist` | 256 x 8 | 2 | 236.80 x 74.10 | 17,547 | 0.117 |
| `RM_IHPSG13_1P_256x16_c2_bm_bist` | 256 x 16 | 4 | 236.80 x 118.78 | 28,127 | 0.146 |
| `RM_IHPSG13_1P_512x8_c3_bm_bist` | 512 x 8 | 4 | 236.80 x 110.38 | 26,138 | 0.157 |
| `RM_IHPSG13_1P_64x64_c2_bm_bist` | 64 x 64 | 4 | 784.48 x 64.36 | 50,489 | 0.081 |
| `RM_IHPSG13_1P_1024x8_c2_bm_bist` | 1024 x 8 | 8 | 146.88 x 336.46 | 49,419 | 0.166 |
| `RM_IHPSG13_1P_256x32_c2_bm_bist` | 256 x 32 | 8 | 416.64 x 118.78 | 49,488 | 0.166 |
| `RM_IHPSG13_1P_512x16_c2_bm_bist` | 512 x 16 | 8 | 236.80 x 191.34 | 45,309 | 0.181 |
| `RM_IHPSG13_1P_256x48_c2_bm_bist` | 256 x 48 | 12 | 596.48 x 118.78 | 70,850 | 0.173 |
| `RM_IHPSG13_1P_1024x16_c2_bm_bist` | 1024 x 16 | 16 | 236.80 x 336.46 | 79,674 | 0.206 |
| `RM_IHPSG13_1P_256x64_c2_bm_bist` | 256 x 64 | 16 | 784.48 x 118.78 | 93,181 | 0.176 |
| `RM_IHPSG13_1P_512x32_c2_bm_bist` | 512 x 32 | 16 | 416.64 x 191.34 | 79,720 | 0.206 |
| `RM_IHPSG13_1P_1024x32_c2_bm_bist` | 1024 x 32 | 32 | 416.64 x 336.46 | 140,183 | 0.234 |
| `RM_IHPSG13_1P_4096x8_c3_bm_bist` | 4096 x 8 | 32 | 236.80 x 618.30 | 146,413 | 0.224 |
| `RM_IHPSG13_1P_512x64_c2_bm_bist` | 512 x 64 | 32 | 784.48 x 191.34 | 150,102 | 0.218 |
| `RM_IHPSG13_1P_1024x64_c2_bm_bist` | 1024 x 64 | 64 | 784.48 x 336.46 | 263,946 | 0.248 |
| `RM_IHPSG13_1P_4096x16_c3_bm_bist` | 4096 x 16 | 64 | 416.64 x 618.30 | 257,609 | 0.254 |
| `RM_IHPSG13_1P_2048x64_c2_bm_bist` | 2048 x 64 | 128 | 784.48 x 626.70 | 491,634 | 0.267 |
| `RM_IHPSG13_1P_8192x32_c4` | 8192 x 32 | 256 | 1520.16 x 618.30 | 939,915 | 0.279 |
| `RM_IHPSG13_2P_256x8_c2_bm_bist` | 256 x 8 | 2 | 278.51 x 136.97 | 38,148 | 0.054 |
| `RM_IHPSG13_2P_64x32_c2` | 64 x 32 | 2 | 702.83 x 74.87 | 52,621 | 0.039 |
| `RM_IHPSG13_2P_256x16_c2_bm_bist` | 256 x 16 | 4 | 419.95 x 136.97 | 57,521 | 0.071 |
| `RM_IHPSG13_2P_512x8_c2_bm_bist` | 512 x 8 | 4 | 261.17 x 219.77 | 57,397 | 0.071 |
| `RM_IHPSG13_2P_256x32_c2_bm_bist` | 256 x 32 | 8 | 702.83 x 136.97 | 96,267 | 0.085 |
| `RM_IHPSG13_2P_512x16_c2_bm_bist` | 512 x 16 | 8 | 402.61 x 219.77 | 88,482 | 0.093 |
| `RM_IHPSG13_2P_1024x16_c2_bm_bist` | 1024 x 16 | 16 | 402.61 x 385.37 | 155,154 | 0.106 |
| `RM_IHPSG13_2P_512x32_c2_bm_bist` | 512 x 32 | 16 | 685.49 x 219.77 | 150,650 | **0.109** |
| `RM_IHPSG13_2P_1024x32_c2_bm_bist` | 1024 x 32 | 32 | 685.49 x 385.37 | 264,167 | **0.124** |

(The two bold entries and the `1P_256x32` row are corrections to an
earlier revision of this table, which carried 0.106, 0.122 and 0.165.)

Naming: `RM_IHPSG13_<1P|2P>_<words>x<bits>_c<colmux>[_bm][_bist]`.
`_bm` = per-bit write mask (`A_BM`), `_bist` = a second BIST-side port
set (`A_BIST_*`) multiplexed onto the array by `A_BIST_EN`. 25 of the 27
carry both; `RM_IHPSG13_1P_8192x32_c4` and `RM_IHPSG13_2P_64x32_c2` have
neither and expose only the plain port. **[fact]**

Two-port macros cost roughly **2x the area per bit** of the equivalent
single-port part (e.g. 512x32: 150,650 um2 dual-port vs 79,720 um2
single-port). This matches the TT per-tile density note in docs/06
section B.4 and confirms it independently from the PDK rather than from
the TT documentation. **[fact]**

### 6.2 Density argument for the macro [fact]

The concrete reason to care, from this project's own numbers. `aer_fifo`
stores 1,024 bits. Synthesis spent, per stored bit, one
`sg13g2_dfrbpq_1` (48.9888 um2) + one `sg13g2_tiehi` (7.2576 um2) + one
`sg13g2_mux2_1` (18.144 um2) = **74.39 um2/bit**, i.e. **0.01344
bit/um2** — and that is before routing area, control logic, or
utilization derating.

| Storage style | bit/um2 | vs flop array |
|---|---|---|
| Flop array as synthesized here | 0.01344 | 1.0x |
| `RM_IHPSG13_1P_256x8_c3` (smallest macro) | 0.117 | **8.7x** |
| `RM_IHPSG13_1P_1024x16_c2` | 0.206 | **15.3x** |
| `RM_IHPSG13_1P_8192x32_c4` (largest) | 0.279 | **20.7x** |

So the macro is worth 9-20x in silicon area. Section 7 is about whether
the open-PDK views close DRC and LVS in this flow.

### 6.3 What LibreLane integration requires [fact]

The variable names below were read from LibreLane 3.0.5's step
definitions, not from documentation, and every one of them was
subsequently exercised by the run in section 7.

**Views.** A `MACROS` entry per instance, of the `librelane.config.Macro`
shape: `gds`, `lef`, `instances` (name + `location` + `orientation`),
`lib` (keyed by corner ID), plus optionally `nl`/`pnl`/`spef`/`spice`/`vh`.
All required files exist in the PDK for all 27 macros. In practice a
`vh` blackbox declaration is also needed, because `Verilator.Lint` runs
before synthesis and will fail on an undeclared module (section 7.1).

**Placement.** `MACRO_PLACEMENT_CFG` or the per-instance `location` in
the `MACROS` entry; `FP_MACRO_HORIZONTAL_HALO` /
`FP_MACRO_VERTICAL_HALO` (both default 10 um) to keep rows off the macro
edge; `GRT_MACRO_EXTENSION` (default 0) for routing-guide extension
around it. `FP_SIZING` must become `absolute` with an explicit
`DIE_AREA` — a relative-sized die does not reserve room for a fixed
block.

**Power.** `PDN_MACRO_CONNECTIONS` (list of
`<instance_rx> <vdd_net> <gnd_net> <vdd_pin> <gnd_pin>` strings) and
`PDN_CONNECT_MACROS_TO_GRID` (default true). Note the LibreLane 3.x
spelling: the variables are `PDN_*`, not the older `FP_PDN_*`. This is
**not** sufficient on its own for these macros; see 7.3.

**Timing.** `lib` views per corner in the `MACROS` entry;
`STA_MACRO_PRIORITIZE_NL` (default true) controls whether the
post-layout netlist or the Liberty is used; `RSZ_DONT_TOUCH_LIST` to
keep the resizer off the macro pins; `CTS_MACRO_CLUSTERING_*` if the
macro clock is part of the tree.

**Signoff.** `MAGIC_MACRO_STD_CELL_SOURCE` (default `macro`) selects
whether Magic reads the standard cells out of the macro GDS or the PDK;
the default does not work with these macros, see 7.4. LibreLane 3.0.5's
Classic flow signs off LVS with `Magic.SpiceExtraction` + `Netgen.LVS`
— not with the PDK's KLayout LVS deck, which is also shipped.
`EXTRA_SPICE_MODELS` is how the macro CDL reaches Netgen.

### 6.4 Properties of the macro views

Each of these was checked against the installed files. Where section 7
tested a prediction, it says so.

**(a) Corner-name mismatch between macro and standard cells.**
The standard cells ship `fast_1p32V_m40C`; the SRAM macros ship
`fast_1p32V_m55C`. The slow (`slow_1p08V_125C`) and typical
(`typ_1p20V_25C`) names match exactly; only the fast corner differs, and
it differs in temperature (-40 C vs -55 C), not voltage. LibreLane keys
`LIB` by corner ID, so the macro's -55 C file has to be mapped onto the
`nom_fast_1p32V_m40C` corner ID — which is what
`hw/openlane/sram_pilot/config.json` does. That is a hold-corner
analysis run with a macro characterized 15 C colder than the cells
around it. Direction of the error is favourable for hold on the macro's
own arcs (colder is faster in this regime) but it is a documented
approximation, not a clean corner. **[fact for the mismatch; the sign of
the error is an [estimate]]**

**(b) Three supplies, all on Metal4, and the LEF and Liberty disagree
about their names.** The LEF pins are `VDD!`, `VSS!`, `VDDARRAY!` — with
the trailing `!` global-net marker. The Liberty `pg_pin` names are
`VDD`, `VDDARRAY`, `VSS` — without it. PDN hookup and
`Odb.SetPowerConnections` match on LEF names; power and PG-aware STA
match on Liberty names.

Both lists also have to be reconciled with the standard-cell world, and
the direction matters: in this PDK the **standard-cell LEF pins are
`VDD`/`VSS`** (`SCL_POWER_PINS` / `SCL_GROUND_PINS` in
`libs.tech/librelane/config.tcl`), while **`VPWR`/`VGND` are the
top-level design power and ground net names** (`VDD_PIN` / `GND_PIN`,
which `set_power_nets.tcl` turns into `VDD_NET` / `GND_NET`). So the
macro's `VDD!` differs from the standard cells' `VDD` by one character,
and neither is the net name.

All three supply pins are on **Metal4**: `VSS!` 36 rectangles, `VDD!` 36,
`VDDARRAY!` 32. `VDDARRAY!` is a *third* supply (the array supply,
separate from the support-logic supply) with no counterpart anywhere in
the standard-cell PDN, so it needs its own `PDN_MACRO_CONNECTIONS` entry
rather than falling out of the default hookup. The Metal4 placement is
the load-bearing fact — see 7.3. **[fact]**

**(c) All 188 signal pins are on the bottom edge, on Metal2, with one
access point each.** Measured on `RM_IHPSG13_1P_512x32_c2_bm_bist`: 191
LEF pins, of which 3 are the supplies above and **188 are signal pins
(156 inputs, 32 outputs)**. Every signal pin has exactly one rectangle,
every rectangle is a **0.26 x 0.26 um square with its lower edge at
y = 0**, and every one is on Metal2. Zero signal pins on the top, left,
or right edges; the pin rectangles span **x = 3.29 to x = 413.35**
across a 416.64 um wide macro, i.e. a 410.06 um band with 3.29 um of
clearance at each end. (An earlier revision of this table said "0.00 to
413.61". That is not what the LEF says: re-measured by parsing every
`PIN`/`PORT`/`RECT` triple in
`libs.ref/sg13g2_sram/lef/RM_IHPSG13_1P_512x32_c2_bm_bist.lef`, the
minimum left edge is 3.29 and the maximum right edge is 413.35
**[fact]**. The correction is cosmetic for the conclusion — the pins
are still crowded onto one edge — but the old numbers happen to look
like "flush to both corners", which is a different and wrong mental
picture of the pin row.) Metal2 is `RT_MIN_LAYER` and `FP_IO_VLAYER`
for this PDK, so the
router's lowest available layer is the only way in. The macro's
`SYMMETRY X Y R90` allows flipping so the pin edge can face the logic,
but it cannot spread the pins out.

An earlier revision of this document called this "the single most likely
place a macro harden fails" and said only a routed run could settle it.
The routed run has now been done and **the prediction was wrong**:
detailed routing converged to zero DRC errors in four of its own
iterations, on the first run, with no pin-access tuning of any kind
(section 7.2). The geometry is still worth knowing — it is the reason
the macro must sit above a band of standard cells rather than in a
corner — but it is no longer the risk. **[fact for the geometry; the
superseded prediction is recorded so the correction is visible]**

**(d) Metal1 is fully blocked, Metal4 is not, and the GDS extends below
the LEF outline.** The macro's `OBS` section carries 1,603 rectangles:
**1 on Metal1** (covering the entire footprint), **1,496 on Metal2** and
**106 on Metal3**. Nothing is obstructed on Metal4 or above, which is
what lets the router and the PDN cross the macro on the upper layers.

Separately, the **GDS extends 0.225 um below the LEF `SIZE` origin**:
the LEF abstract says the cell occupies `(0,0)-(416.64,191.34)`, and the
GDS bounding box is `(0,-0.225)-(416.64,191.34)`. Exactly one layer is
responsible — **31/0, `NWell.drawing`**; every other layer in the file
stays at y >= 0. (An earlier revision also named layer 189/4,
`prBoundary.boundary`; that layer is **not present anywhere in the macro
GDS**, which is a separate problem in its own right — see 7.4.) The
governing rule is `NW.b`, minimum NWell space or notch 0.62 um
(`libs.tech/klayout/tech/drc/rule_decks/feol/5_1_nwell.drc`); NWell
regions closer than that are merged rather than flagged. A macro halo
has to cover the 0.225 um overhang plus that spacing at the bottom edge;
the LibreLane default `FP_MACRO_*_HALO` of 10 um does so comfortably,
and did in section 7. A hand-tuned tight halo would not. **[fact]**

**(e) `A_DLY` must be tied high — but the datasheets do not all say so
with the same force.** The wording splits the family in two:

- **16 of 27** datasheets carry the sentence "IMPORTANT: Input port
  `*_DLY` must always be tied to '1'." and describe the pin as
  "MANDATORY setting: Tie to 1".
- **The other 11** describe the same pin as "recommended setting: Tie to
  1" and carry no IMPORTANT sentence.

`RM_IHPSG13_1P_512x32_c2_bm_bist` — the part section 6.5 recommends and
section 7 hardens — is in the **second** group. So is every other
`_64`-wide 1P part, plus `1P_1024x8`, `1P_1024x16`, `1P_2048x64`,
`1P_256x48`, `1P_4096x8` and `1P_4096x16`. Whether that is a meaningful
distinction or an inconsistency in the generator is not knowable from
the files; the safe engineering reading is to tie it high everywhere,
which is what `hw/openlane/sram_pilot/sram_pilot.v` does.

Either way it is easy to get wrong in an RTL wrapper and it will not
show up in a behavioural simulation: the PDK's `FUNCTIONAL` model passes
`A_DLY` down to a core instance that declares it as
`input wire A_DLY; // Delay selection signals` (line 49) and never reads
it again anywhere in the file **[fact — grepped]**.

Name that instance precisely, because the obvious name is wrong.
`RM_IHPSG13_1P_core_behavioral_bm_bist` is a **file name**, not a module
name: `libs.ref/sg13g2_sram/verilog/RM_IHPSG13_1P_core_behavioral_bm_bist.v`
declares **`module SRAM_1P_behavioral_bm_bist`**, and no module called
`RM_IHPSG13_1P_core_behavioral_bm_bist` exists anywhere in the installed
PDK **[fact — `grep -r "module RM_IHPSG13_1P_core_behavioral_bm_bist"`
over `~/.ciel/ihp-sg13g2/` returns nothing]**. Both the `FUNCTIONAL` and
the non-`FUNCTIONAL` arm of
`RM_IHPSG13_1P_512x32_c2_bm_bist.v` instantiate
`SRAM_1P_behavioral_bm_bist` as `i_SRAM_1P_behavioral_bm_bist`. An
earlier revision of this document used the file name as the module name
in this paragraph and in section 7.1; both are corrected. The
distinction matters in practice: a blackbox or a `-y` library search
keyed on the file name resolves nothing.
**[fact]**

**(f) The LVS path is the known-weak one, and the PDK does not
pre-arrange it.** Three separate observations:

- Neither `libs.tech/netgen/ihp-sg13g2_setup.tcl` nor the KLayout LVS
  deck `libs.tech/klayout/tech/lvs/sg13g2.lvs` mentions `RM_IHPSG13` or
  declares any black box. Macro LVS has to be set up by hand — in this
  flow, through `EXTRA_SPICE_MODELS`. **[fact]**
- The CDLs are real transistor netlists. For 512x32: **353 MOSFET
  statements, 12 resistors and 3,617 subcircuit instantiations across
  145 `.SUBCKT` definitions**. But across the 27 macros, **162
  subcircuits — exactly 6 per macro — are declared with no devices and
  no instances at all**: for 512x32 those are
  `..._1P_BITKIT_CORNER`, `..._1P_BITKIT_EDGE_TB`, `..._2P_BITKIT_EDGE_TB`,
  `..._1P_BITKIT_TAP`, `..._2P_BITKIT_TAP` and `..._1P_BITKIT_TAP_LR`
  (note that the 1P macro's CDL contains 2P-named subcircuits). In the
  GDS the corresponding cells *do* carry layout — `RM_IHPSG13_1P_BITKIT_TAP`
  has 25 shapes. **[fact]**
- The GDS cell names and the CDL subcircuit names do not agree. GDS has
  `RM_IHPSG13_1P_BITKIT_TAP`; the CDL for the same macro has
  `RM_IHPSG13_512x32_c2_1P_BITKIT_TAP`, with the configuration infix. Of
  the 142 cells in the macro GDS, the `RSC_IHPSG13_*` leaf cells match
  the CDL by name and the `RM_IHPSG13_1P_*` cells do not. A hierarchical
  LVS cannot match those by name; it would have to run flat or with an
  explicit name map. **[fact]**

  This is consistent with, and gives a local mechanism for, the upstream
  reports already cited in docs/04 section 1.2 (IHP-Open-PDK issue #239
  on SRAM LVS failures; the ORFS discussion on merging bitkit cells).
  Section 7.5 reports what actually happened.

**(g) Timing is usable and the read is slow.** The Liberty models are
complete: 25 `timing()` groups — 12 `setup_rising`, 12 `hold_rising`,
2 `min_pulse_width` (on `A_CLK` and `A_BIST_CLK`) and the one
`rising_edge` read arc — plus a `memory()` group declaring
`type : ram; address_width : 9; word_width : 32`.

The read arc `A_CLK -> A_DOUT` is a 7 x 6 lookup table over input slew
and output load, and the number that matters is the **worst** corner of
that table, not the best:

| Corner | `cell_rise` min | `cell_rise` **max** | `cell_fall` max |
|---|---|---|---|
| `typ_1p20V_25C` | 3.808 ns | **4.007 ns** | 3.927 ns |
| `slow_1p08V_125C` | 6.382 ns | **6.688 ns** | 6.552 ns |
| `fast_1p32V_m55C` | 2.338 ns | 2.464 ns | 2.417 ns |

At a 20 ns period (50 MHz, the TT envelope of docs/06 B.2) the
slow-corner read consumes **33 % of the cycle** before any logic. An
earlier revision quoted 3.81 ns and 6.38 ns and called them "the arc";
those are the table minima — smallest load, fastest input slew — and
understate the real figure by about 5 %. The measured post-layout
consequence is in section 7.2.

`min_pulse_width` is corner-dependent: 0.21 ns typical, 0.40 ns slow.
Note also `interface_timing : false` in the Liberty header. **[fact]**

### 6.5 Fit against the Tiny Tapeout tile grid

**The geometry in this subsection is no longer interpolated, and the
numbers have moved.** An earlier revision of this document took two
measured points from docs/06 section B.2 (1x1 = 202.08 x 154.98 um,
8x4 = 1724.16 x 710.64 um), fitted a 217.44 x 185.22 um tile pitch to
them, and derived every other shape from that fit. The fit is wrong on
the vertical axis: `docs/15-pilot-tile-plan.md` section 4.3 read the
shapes straight out of `tt-support-tools`
`tech/ihp-sg13g2/tile_sizes.yaml` and the matching
`tech/ihp-sg13g2/def/tt_block_<shape>_pgvdd.def` templates, which is
what the shuttle flow actually uses, and the two-row shapes come out
**313.74 um** tall rather than the interpolated 340.20. docs/15 is the
authority for tile geometry in this repository; this subsection now
quotes it.

| Shape | Block size **[fact, `tile_sizes.yaml`]** | Area | Interpolated size this document used to print |
|---|---|---|---|
| 1x1 | 202.08 x 154.98 um | 0.0313 mm2 | same (it was one of the fit points) |
| 2x2 | 419.52 x **313.74** um | 0.1316 mm2 | 419.52 x 340.20, 0.143 mm2 (+8.4 %) |
| 4x2 (the "8 tiles" of the ROADMAP) | 854.40 x **313.74** um | 0.2681 mm2 | 854.40 x 340.20, 0.291 mm2 (+8.4 %) |
| 3x4 | 636.96 x 710.64 um | 0.4526 mm2 | not derived |
| 4x4 | 854.40 x 710.64 um | 0.6072 mm2 | same |
| 8x4 | 1724.16 x 710.64 um | 1.2253 mm2 | same (the other fit point) |

The four-row shapes were right because 710.64 was a fit point; every
two-row shape was 8.4 % too generous. Two consequences follow, and the
first one costs this document a claim:

**The macro run in section 7 was floorplanned on the interpolated
block, not on the real one.** `hw/openlane/sram_pilot/config.json` sets
`DIE_AREA` to `0 0 854.40 340.20`, so section 7.2's "854.40 x 340.20 um
= 290,667 um2, exactly the 4x2 block" is wrong on the last three words:
a real 4x2 block is 854.40 x 313.74 = **268,060 um2**, and the run used
a die **8.4 % larger** than the shape it was standing in for. The
macro itself still fits the real block — it occupies
y = 105.84 to 297.18, and 297.18 + a 10 um halo = 307.18 < 313.74
**[fact, arithmetic on the placement in section 7]** — so the routing,
antenna, timing and DRC/LVS results of section 7 stand as results about
that macro in that flow. What does not stand is reading them as "at the
4x2 tile shape". Re-running `sram_pilot` at `0 0 854.40 313.74` before
quoting it as a tile-shape result is one command and has not been done
**[fact — not attempted]**.

Fit against the **real** 4x2 block (854.40 x 313.74 um):

| Macro | Size | Vertical room left | Verdict |
|---|---|---|---|
| `1P_1024x32` (32 kbit) | 416.64 x 336.46 | **-22.7 um** | **infeasible** — taller than the block |
| `1P_1024x16` (16 kbit) | 236.80 x 336.46 | **-22.7 um** | **infeasible**, same reason |
| `1P_1024x8` (8 kbit) | 146.88 x 336.46 | **-22.7 um** | **infeasible**, same reason |
| `1P_512x64` (32 kbit) | 784.48 x 191.34 | 122.4 um, but only 69.9 um horizontally | tight |
| `1P_512x32` (16 kbit) | 416.64 x 191.34 | 122.4 um | **feasible**, best candidate |
| `1P_512x16` (8 kbit) | 236.80 x 191.34 | 122.4 um | comfortable |
| `1P_256x32` (8 kbit) | 416.64 x 118.78 | 194.96 um | comfortable |

The tall 1024-word parts are ruled out by the 313.74 um block height,
not by area — and the corrected geometry makes that verdict stronger,
not weaker: on the interpolated block they were short by 3.7 um of
clearance, on the real block they do not fit inside the block at all.
**The 8-tile pilot's realistic macro is `RM_IHPSG13_1P_512x32`
(16 kbit) or `RM_IHPSG13_1P_512x16` (8 kbit).** **[fact for the macro
and block dimensions; the "best candidate" judgement is a [decision],
and the 512x32 half of it is supported by the placed-and-routed run in
section 7 subject to the die-size caveat above]**

**Errata against docs/06 — now applied there.** The `1P_1024x8` row
above was not a hypothetical. docs/06 section B.6 named "One RM_IHPSG13
1024x8 macro (~2 tiles)" as the content of the 8-tile upgrade pilot, and
B.6.1 worded the 2026-09-07 gate as "the RM_IHPSG13 1024x8 macro with
its ECC wrapper passes DRC/LVS in the local rootless flow **inside the
4x2 floorplan**". `RM_IHPSG13_1P_1024x8_c2_bm_bist` is 336.46 um tall
against a 313.74 um block: the combination is geometrically impossible,
by 22.7 um rather than by the 3.74 um of clearance the interpolated
figure suggested. docs/06 B.6 and B.6.1 have since been rewritten — the
macro is named `1P_512x32`/`1P_512x16`, the flip-flop-RAM pilot is 4x2 =
8 tiles on docs/15's measurement, the SRAM-macro variant is 12 tiles,
and the gate now decides macro content rather than tile count.

For scale in the other direction: the `aer_fifo` die from section 4.3 is
484.115 x 502.835 um = 243,430 um2 = 0.2434 mm2, against the measured
1x1 block of 202.08 x 154.98 um = 31,318 um2. That is **7.8 tile-areas
for a single 1024-bit FIFO** at 40 % target utilization. A flop-based
memory strategy does not fit a Tiny Tapeout budget. **[fact — both
areas are measured, the 1x1 figure from docs/06 B.2]**

---

## 7. The RM_IHPSG13 decision run [fact]

This is the experiment docs/06 B.6.1 asks for, minus the ECC wrapper:
one `RM_IHPSG13_1P_512x32_c2_bm_bist` hardened inside the interpolated
4x2 Tiny Tapeout block, through the same `run_trial.sh` chain. Read
6.5 first for what "4x2" means here: the die used is 26.46 um taller
than the real shape.

Files: `hw/openlane/sram_pilot/{config.json, sram_pilot.v,
RM_IHPSG13_1P_512x32_c2_bm_bist_bb.v, pdn_macro.tcl}`.
Command: `hw/openlane/run_trial.sh --design sram_pilot`.

Design: `clk`, `rst_n`, `en`, `we`, `addr[8:0]`, `din[31:0]`,
`dout[31:0]`. Every macro input is driven from a flop or a constant and
`A_DOUT` is captured in a flop, so the router faces a real pin-access
problem while synthesis has almost nothing to optimise. `A_DLY` is tied
high (6.4e). The BIST port set is parked: `A_BIST_EN` low, the rest at
0. `A_BM` is all-ones.

Floorplan: `DIE_AREA` = `0 0 854.40 340.20`, the interpolated 4x2 block
verbatim (the measured shape is `0 0 854.40 313.74`; 6.5). Macro origin `(380.16, 105.84)` orientation `N`, which is
site-aligned (`380.16 = 5.76 + 780 x 0.48`, `105.84 = 15.12 + 24 x
3.78`) and puts the macro's single pin edge at the bottom, facing an
89.9 um band of standard-cell rows below it.

### 7.1 Three runs, and what each one bought

| Run | Change | Reached | What it established |
|---|---|---|---|
| `macro-01` | first attempt | died at `56-openroad-irdropreport` | routing and timing close; the PDN does not reach the macro (7.3) |
| `macro-02` | + `PDN_CFG` fix | died at `57-magic-streamout` | PDN clean; Magic cannot bbox the macro GDS (7.4) |
| `macro-03` | + `MAGIC_MACRO_STD_CELL_SOURCE: PDK` | see 7.5 | the signoff answer |

A fourth failure preceded all of them and is worth one line because it
will hit anyone repeating this: `Verilator.Lint` runs before synthesis
and fails with "Cannot find file containing module:
RM_IHPSG13_1P_512x32_c2_bm_bist" if the macro has no `vh` view. The PDK's
own behavioural `.v` cannot be used for this — it instantiates module
`SRAM_1P_behavioral_bm_bist`, which lives in a different file
(`RM_IHPSG13_1P_core_behavioral_bm_bist.v`; note that the file name is
not the module name, 6.4e) — so
`RM_IHPSG13_1P_512x32_c2_bm_bist_bb.v` transcribes the port list with an
empty body.

### 7.2 Placement, routing and timing: clean

From `macro-03`'s `final/metrics.json`. `macro-02` produced identical
placement, routing and timing numbers — the two runs differ only in the
streamout setting, which is downstream of everything in this subsection.

| Quantity | Value |
|---|---|
| Die | 854.40 x 340.20 um = 290,667 um2 — the interpolated 4x2 block, 8.4 % larger than the measured 268,060 um2 (6.5) |
| Instances | 1 macro + 589 standard cells (75 flops, 30 clock buffers, 5 clock inverters, 217 timing-repair buffers of which 128 hold buffers, 261 combinational, 1 inverter) + 12,837 fill |
| Utilization incl. macro | 34.2 % (standard cells alone 5.3 %) |
| Global-route antenna check | 0 violating nets / 0 violating pins |
| Detailed-routing DRC per iteration | 111 -> 20 -> 15 -> **0** |
| Nets routed | 661 signal + 2 special |
| Routed wirelength | 15,612 um; longest net 328.275 um |
| Post-detailed-routing antenna | **0 / 0** |
| Disconnected pins | 0 |

**Detailed routing into the 188 bottom-edge Metal2 pins succeeded.** The
router needed four iterations and converged; no manual pin-access help,
no `GRT_MACRO_EXTENSION`, no obstruction tuning. The failure this
document previously predicted as most likely (6.4c) did not occur.

Timing, post-layout, at `CLOCK_PERIOD: 20` (50 MHz), from
`55-openroad-stapostpnr/summary.rpt`:

| Corner | Setup worst slack | Hold worst slack | Violations |
|---|---|---|---|
| `nom_slow_1p08V_125C` | **13.0667 ns** | 0.9184 ns | 0 |
| `nom_typ_1p20V_25C` | 15.0912 ns | 0.4793 ns | 0 |
| `nom_fast_1p32V_m40C` | 15.3085 ns | **0.2384 ns** | 0 |

The worst setup path is the register-to-register path through the macro
read arc, and at the slow corner it consumes 20 - 13.0667 = **6.93 ns**,
which is the 6.688 ns Liberty arc of 6.4g plus wire and the capture
flop's setup. That is a measured confirmation of the "read consumes a
third of a 50 MHz cycle" figure, and it means an ECC decode stage cannot
be put in the same cycle as the read without dropping below 50 MHz.
**[fact for the slack; the ECC implication is an [estimate]]**

### 7.3 Defect 1: the default macro PDN never reaches the macro

`macro-01` failed at IR-drop analysis:

```
[WARNING PSM-0039] Unconnected instance u_sram/VDD! at (588.480um, 133.725um).
[WARNING PSM-0039] Unconnected instance u_sram/VDDARRAY! at (588.480um, 224.242um).
[ERROR PSM-0069] Check connectivity failed on VPWR.
```

preceded by dozens of `PSM-0038 Unconnected shape on net VPWR ... layer:
Metal4` at the macro's own pin coordinates.

Cause, read from `librelane/scripts/openroad/common/pdn_cfg.tcl`: the
stock macro grid is

```
define_pdn_grid -macro -default -name macro -starts_with POWER -halo ...
add_pdn_connect -grid macro -layers "$PDN_VERTICAL_LAYER $PDN_HORIZONTAL_LAYER"
```

which for this PDK bonds **TopMetal1 to TopMetal2** and nothing else. All
three macro supply pins are on **Metal4** (6.4b). The standard-cell grid
is Metal1 rails plus TopMetal1/TopMetal2 straps. Nothing in the default
configuration ever descends to Metal4, so the macro's supplies are left
floating.

Three things make this worse than it sounds:

1. `pdngen` itself exits successfully and `check_power_grid` writes empty
   error files. Placement, CTS, global routing and **detailed routing all
   complete** on a design whose SRAM has no power.
2. The first step that notices is `OpenROAD.IRDropReport`, which is 35
   steps later and is a step some flows skip.
3. The PDK sets `MACRO_BLOCKAGES_LAYER` including Metal4, which reads
   like a statement that this layer is managed over macros. LibreLane
   3.0.5 does not implement that variable at all (2.4c).

Fix, in `hw/openlane/sram_pilot/pdn_macro.tcl`, wired in through
`PDN_CFG`:

```tcl
source $::env(SCRIPTS_DIR)/openroad/common/pdn_cfg.tcl
add_pdn_connect -grid macro -layers "Metal4 $::env(PDN_VERTICAL_LAYER)"
```

`pdngen` stacks that through Via4/Metal5/TopVia1. After the fix,
`macro-02` reports zero power-grid violations on both nets and
`[INFO PSM-0040] All shapes on net ... are connected.`

There is no config variable for this in LibreLane 3.0.5 — the macro grid
is hard-coded in the shipped Tcl — so `PDN_CFG` is the only way in.
Sourcing the stock file rather than copying it keeps the standard-cell
grid behaviour intact. **Any RM_IHPSG13 integration in this tool version
needs this file or an equivalent.**

### 7.4 Defect 2: Magic cannot stream out the macro GDS

`macro-02` then failed at `Magic.StreamOut`:

```
Failed to extract PR boundary from GDSII view of macro
'RM_IHPSG13_1P_512x32_c2_bm_bist'. Ensure that the GDSII view has a
PR boundary layer.
```

Cause: with the default `MAGIC_MACRO_STD_CELL_SOURCE: macro`,
LibreLane first runs `scripts/magic/get_bbox.tcl` over the macro GDS and
reads its `FIXED_BBOX` property. sg13g2's Magic tech derives that from
the prBoundary layer, `calma 189 4`
(`libs.tech/magic/ihp-sg13g2-cifout.tech`). **The macro GDS contains no
189/4 layer** — confirmed by a KLayout layer scan of all 27 files' worth
of geometry in `RM_IHPSG13_1P_512x32_c2_bm_bist.gds`, where 31/0
(NWell), 235/4 and 25 other layers are present and 189/4 is not. The
property comes back empty and LibreLane raises.

Magic also logs, while reading the same file:

```
Error while reading cell "RM_IHPSG13_1P_COLCTRL2" (byte position 437810):
Unknown layer/datatype in boundary, layer=235 type=4
```

so 235/4 is unknown to the sg13g2 Magic tech as well. Neither error is
fatal to the layout — it is the missing prBoundary that stops the flow.

Workaround, used in the committed config:
`"MAGIC_MACRO_STD_CELL_SOURCE": "PDK"`. This takes the `get_bbox` path
out of the flow entirely and lets Magic read the standard cells from the
PDK GDS while treating the macro as a hierarchical instance. With it,
`Magic.StreamOut` completes.

The cost of the workaround is not free and should be stated: `PDK` mode
changes which cell definitions Magic uses inside the macro, so the
extracted view is no longer guaranteed to be exactly the vendor GDS
hierarchy. For a production tapeout the right fix is upstream — either
the macro GDS gains a 189/4 prBoundary, or LibreLane learns to fall back
to the LEF `SIZE` when the property is absent.

### 7.5 Signoff on the macro run: it does not close

With both workarounds in place, `macro-03` executed all 80 stages —
18.4 minutes of tool time, of which Magic DRC alone was 14 min 37 s —
and ended with three deferred errors:

```
1106478 Magic DRC errors found.
2316 KLayout DRC errors found.
359 LVS errors found.
```

**What 1,106,478 counts, and what it does not.** Read the last two
lines of `64-magic-drc/reports/drc.magic.rpt` together, because the
first without the second overstates the result:

```
[INFO] COUNT: 1106478
[INFO] Should be divided by 3 or 4
```

The figure is a count of **error boxes**, not of distinct violations:
Magic's `drc listall why` emits one box per offending edge or corner,
and the flow's own reporter prints the divisor caveat beneath the total
**[fact — both lines read from the report]**. Dividing gives roughly
**277,000 to 369,000 distinct violations [estimate — the report gives a
range, not a divisor]**. Every use of "1,106,478" in this document is
the raw box count, and is written that way from here on. The caveat
changes the number by a factor of 3-4 and changes nothing about the
conclusion: the smallest reading is still ~277,000 violations against a
required zero, so section 8's NO-GO does not depend on which end of the
range is right. It is corrected because quoting a tool's raw count as
an error count is exactly the kind of number that gets repeated into an
external document where the caveat is not available.

**Magic DRC: 1,106,478 error boxes, and every single one is inside the
macro.** Each error box in `64-magic-drc/reports/drc.magic.rpt` was
tested against the macro footprint `(380.16, 105.84)-(796.80, 297.18)`:
1,106,478 inside, **0 outside**. The standard-cell area, the PDN and the
routing are clean; the vendor SRAM layout is what the deck objects to.
By rule (box counts, same divisor caveat):

| Count | Rule |
|---|---|
| 414,720 | `NW.c` — N-well overlap of P-diffusion |
| 339,862 | `NW.d` — N-diffusion spacing to N-well |
| 165,888 | `Cnt.c` — P-diffusion overlap of P-diffusion contact |
| 66,048 | `Gat.c` — poly overhang of transistor |
| 61,440 | `M2.d` — Metal2 minimum area |
| 51,752 | "Can't overlap those layers" |
| 4,806 | `Cnt.c` — N-diffusion variant |
| 1,170 | `LU.d` / `LU.d1` — tie-diffusion extension |
| 728 | "This layer can't abut or partially overlap between subcells" |
| 64 | `LU.b` — N-diff distance to P-tap |

The top two rules and the abut/overlap messages point at one mechanism:
Magic appears to be evaluating the bitcell array **without merging
geometry across subcell boundaries**. `NW.b` in the KLayout deck says
explicitly that "NWell regions separated by less than this value will be
merged"; a 16 kbit bitcell array built from abutted cells with shared
wells and contacts (the GDS carries `RM_IHPSG13_1P_MATRIX_128x64`
instantiated from `RM_IHPSG13_1P_BITKIT_CELL`) will produce exactly this
error signature if the checker treats each instance as an island.
**[estimate — this is an inference from the rule histogram, not a
verified root cause.]** Whether the mechanism is that or something else,
the measured consequence is not in doubt: **Magic DRC cannot sign off a
design containing this macro in this flow.**

**KLayout DRC: 2,316 errors, also all inside the macro**, and the
contrast with Magic is the interesting part. The deep-mode KLayout deck
evaluates **173** rules and reports errors in exactly **three** of them,
zero in the other 170:

| Count | Rule |
|---|---|
| 1,022 | `Sdiod.d` |
| 1,022 | `Sdiod.e` |
| 272 | `Cnt.c.digibnd` |

Every item is attributed to one of **57 distinct cells, all of them
inside the macro hierarchy** (`RM_IHPSG13_1P_MATRIX_128x64`,
`RM_IHPSG13_1P_COLDEC2`, `RSC_IHPSG13_DFNQX2` and 54 others). Two
signoff decks over the same GDS disagree by nearly three orders of
magnitude, which by itself says
the macro's DRC status in the open flow is a tooling question that needs
resolving upstream before it can be a project decision.

**Netgen LVS: 359 errors**, broken down from `final/metrics.json`:

| Counter | Value |
|---|---|
| `design__lvs_net_difference__count` | 181 |
| `design__lvs_unmatched_pin__count` | 158 |
| `design__lvs_unmatched_device__count` | 13 |
| `design__lvs_unmatched_net__count` | 7 |
| `design__lvs_device_difference__count` | 0 |
| `design__lvs_property_fail__count` | 0 |
| **`design__lvs_error__count`** | **359** |

Final verdict in the report: `Netlists do not match.` followed by
`Top level cell failed pin matching.` Two concrete causes are visible in
`70-netgen-lvs/reports/lvs.netgen.rpt`, and both were predicted in 6.4f:

1. **Hierarchy names disagree, so Netgen flattens the whole macro.** The
   log carries a long run of
   `Flattening unmatched subcell RM_IHPSG13_512x32_c2_1P_<x> in circuit
   RM_IHPSG13_1P_512x32_c2_bm_bist`, including
   `..._BITKIT_CELL (16384 instances)`,
   `..._BITKIT_EDGE_LR (512 instances)` and
   `..._BITKIT_16x2_SRAM (512 instances)`. The CDL carries the
   `512x32_c2` configuration infix and the extracted layout does not, so
   nothing matches by name and the comparison degenerates to flat.
2. **Bus index delimiters disagree.** The extracted side names bits
   `A_DIN[16]`, `A_BM[15]`, `A_DOUT[14]`; the CDL side names the same
   bits `A_DIN<16>`, `A_BM<15>`, `A_DOUT<14>`. The PDK's Netgen setup
   does not normalise between the two, so **none** of the macro's 188
   bus pins match — which is where most of the 158 unmatched pins come
   from.

Cause 2 is a setup problem and looks tractable: a `readnet`-time name
map or a Netgen setup addition should fix it, at the cost of some hours
and a careful check that the fix does not mask a real mismatch. Cause 1
is upstream (it is the same defect as IHP-Open-PDK issue #239, cited in
docs/04 section 1.2) and is not fixable from this repository. The Magic
DRC result is upstream too.

For contrast, the same Netgen setup on the same PDK signed off
`aer_fifo` with all seven counters at zero (section 4.1), so the LVS
path itself is sound; it is the macro views that it cannot digest.

### 7.6 Two further observations from the run

**PDN vias.** After the `PDN_CFG` fix, pdngen still emits exactly six
`[PDN-0110] No via inserted between Metal4 and TopMetal1 ...` warnings —
two on VGND, four on VPWR, all at Metal4 shapes inside the macro
footprint. Six crossings could not take a via stack, presumably where a
Metal5 landing was unavailable. Connectivity still checks out
(`check_power_grid` clean on both nets, `PSM-0040` on both), so this is
a robustness note rather than a failure: a production integration should
widen the macro's supply straps or add explicit `add_pdn_stripe` rules
on Metal5 rather than rely on the automatic stack.

**Global placement diverged.** `[GPL-0323] Divergence detected between
consecutive iterations`, then `[GPL-0998] reverting to snapshot with min
hpwl` at iteration 2, overflow 0.150. With 589 standard cells at 5.3 %
utilization around a large fixed block, the density-driven placer has
almost nothing to work with. It recovered and the result routed, but a
real pilot with this floorplan should either raise utilization or set
`PL_TARGET_DENSITY_PCT` explicitly rather than accept a diverged
placement.

### 7.7 What the macro run settles

| Open question carried by the paper study before this run | Answer |
|---|---|
| 1. Detailed routing into 188 bottom-edge Metal2 pins, one 0.26 um access point each — "highest risk" | **Passes.** 0 DRC errors after 4 DRT iterations, 0 antenna violations, inside an 854.40 x 340.20 um die (the interpolated 4x2 block, 8.4 % larger than the measured one — 6.5). The risk assessment was wrong. |
| 2. LVS, given no PDK macro setup, disagreeing CDL/GDS names, device-free CDL subcircuits | **Fails, 359 errors**, by exactly the predicted mechanism plus a bus-delimiter mismatch that was not predicted. |
| 3. Three-supply PDN hookup including `VDDARRAY!` — "mechanical, but must be got right" | **Passes, but not mechanically.** It needs a `PDN_CFG` override that no config variable exposes, because all three supplies are on Metal4 and the stock macro grid stops at TopMetal1. |
| 4. Fast-corner temperature mismatch | Handled by mapping the -55 C Liberty onto the -40 C corner ID. Timing closed at 50 MHz with 13.07 ns slow-corner slack. Still an approximation, still not a blocker. |
| (not previously asked) DRC | **Fails.** 1,106,478 Magic error boxes (~277,000-369,000 distinct violations after the report's own "divide by 3 or 4" caveat, 7.5) and 2,316 KLayout errors, 100 % of them inside the macro, with the two decks disagreeing by 2-3 orders of magnitude. |

Summary in one line: **the macro integrates and routes; it does not sign
off.** Everything this project controls worked. Everything that failed
is in the vendor views or in the open signoff decks reading them.

---

## 8. Recommendation for the 2026-09-07 go/no-go

**Recommendation: NO-GO on RM_IHPSG13 SRAM macro integration for
TTIHP26b. Submit the flip-flop-RAM pilot. Decide this now rather than on
2026-09-07.**

### 8.1 The evidence

The go/no-go was defined in docs/06 B.6.1 as: take the 8-tile upgrade
only if, by 2026-09-07, "the RM_IHPSG13 ... macro with its ECC wrapper
passes DRC/LVS in the local rootless flow inside the 4x2 floorplan".

The experiment has now been run, without the ECC wrapper — i.e. under
conditions strictly easier than the gate asks for — and the answer is:

- DRC: **fails**, 1,106,478 Magic error boxes (~277,000-369,000 distinct
  violations, 7.5) and 2,316 KLayout errors, all inside the macro (7.5).
  The required result is zero, so the divisor caveat does not soften it.
- LVS: **fails**, 359 errors, driven by CDL/GDS hierarchy naming and bus
  delimiters (7.5).
- Everything else passes: placement, PDN (with an override), CTS,
  routing, antenna, timing at 50 MHz (7.2, 7.3).

Adding an ECC wrapper cannot improve any of the three failing numbers;
it adds logic outside the macro, and the failures are inside it. So the
gate as written is already decided, 13 days early.

### 8.2 Why "no-go" and not "fix it"

Both blocking failures sit outside anything this repository controls:

- **DRC.** The errors are 100 % inside vendor geometry that this project
  does not author and cannot edit. No LibreLane or PDK config setting
  changes them. The two available exits are a Magic tech-file change or
  moving signoff to the KLayout deck, and the KLayout deck also returns
  2,316 errors, so it is not a free exit either.
- **LVS.** The hierarchy-name half is IHP-Open-PDK issue #239, already
  cited in docs/04 section 1.2 as an open integration issue on the
  foundry SRAM macros. The bus-delimiter half is fixable locally; the
  hierarchy half is not.

docs/04 section 1.2 also records the mitigating context, and it is worth
repeating so this recommendation is not misread: these are
flow-integration issues, not silicon issues — the same macros are
production items in the commercial PDK. Nothing here says the RM_IHPSG13
parts are bad. It says the open flow cannot currently sign off a design
that contains one.

Neither is a wait-for-a-fix item on a 2026-09-21 timescale.

### 8.3 Why the schedule makes this easy

docs/06 B.6.1 puts total remaining capacity at **~55-80 h** to the
2026-09-21 close and the default 2x2 pilot at **49-79 h**, i.e. no
slack. It budgets **25-50 h** for macro integration on top. Against that
budget, this document has consumed a few hours to reach a definitive
negative. Spending the remaining 25-50 h chasing an upstream PDK defect
would consume the entire pilot capacity and still not guarantee a
signoff-clean GDS.

**The value of deciding now is the 13 days.** The flip-flop-RAM pilot is
unblocked immediately, and section 4 has already demonstrated that
exactly that flow — flop-based storage, `sg13g2_stdcell`, this
toolchain — reaches DRC/LVS clean.

### 8.4 What to do instead, and what to keep

1. **Submit the flip-flop / latch-RAM pilot** on the flow proven in
   section 4. No macro dependency.
2. **docs/06 B.6 and B.6.1 needed fixing regardless of the decision**:
   the macro named there, `RM_IHPSG13 1024x8`, does not fit the 4x2
   block it was gated against (6.5 errata). Even a future go must name
   `1P_512x32` or `1P_512x16`. **Done** — see 10.1 item 1.
3. **Keep `hw/openlane/sram_pilot/`.** It is a working macro-integration
   harness for this PDK: MACROS entry with the cross-corner Liberty map,
   blackbox `vh`, site-aligned placement, the `PDN_CFG` Metal4 fix, and
   the streamout workaround. Re-running it against a newer IHP-Open-PDK
   or LibreLane is a single command and answers "has upstream fixed it
   yet" in 20 minutes.
4. **Re-open the question for TTIHP27a** (the pre-silicon-gated run of
   docs/06 B.6.2), where there is time to engage upstream. The two
   issues to track are IHP-Open-PDK #239 and the Magic-versus-KLayout
   DRC divergence measured in 7.5.
5. **Carry the timing result forward.** The macro's read arc consumes
   6.93 ns of a 20 ns cycle post-layout (7.2). Any future ECC-wrapped
   memory design should assume read and ECC decode are separate pipeline
   stages. **[estimate]**

### 8.5 What would change this recommendation

A go would need all three of: a Magic (or KLayout) DRC deck that returns
zero on an unmodified RM_IHPSG13 GDS; a Netgen setup that matches the
CDL hierarchy to the extracted layout; and enough remaining capacity to
absorb the integration on top of the pilot. As of 2026-08-25 none of the
three holds. If upstream closes the first two before TTIHP27a, the third
becomes the only question and the harness in
`hw/openlane/sram_pilot/` is ready for it.

---

## 9. Reproduction

```
# one-time, outside the repository
export PDK_ROOT=$HOME/.ciel
ciel enable --pdk-family ihp-sg13g2 c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c

# G0 evidence: full aer_fifo flow to DRC/LVS  (~11 min, 20 threads)
hw/openlane/run_trial.sh --run-tag trial-03-signoff

# the macro decision run  (~18 min; ends with 3 deferred errors by design)
hw/openlane/run_trial.sh --design sram_pilot --run-tag macro-03

# synthesis + STA only (fast, ~1 min)
hw/openlane/run_trial.sh -T OpenROAD.STAPrePNR
```

Run outputs land in `hw/openlane/<design>/runs/<tag>/` and are
**gitignored** (`.gitignore`: `hw/openlane/*/runs/`), so they do not
survive a fresh clone. **`<run>/resolved.json`** — one file, at the run
root — is the authority on what a config key actually became; check it
after any config change, since a key that LibreLane does not recognise
never reaches it and the warning does not reach `warning.log` either
(section 2.4c). Do not look for a per-step `resolved.json`: there is
none. Step directories carry `config.json`, which is only the subset of
the resolution that that step consumes, and it omits keys as central as
`RUN_ANTENNA_REPAIR` entirely (2.4).

Environment overrides, if the tool locations differ: `SHIMS`, `VENV`,
`OSS_CAD`, `PDK_ROOT`.

---

## 10. Open items

### 10.1 Errata this document raised against other files — both closed

Both were outside this file's ownership and were recorded here rather
than edited there. Both have since been applied by the owners; the
entries are kept so the trail is visible.

1. **docs/06 B.6 and B.6.1 named a macro that does not fit.** The
   8-tile upgrade content was given as "One RM_IHPSG13 1024x8 macro
   (~2 tiles)" and the 2026-09-07 gate was worded against "the
   RM_IHPSG13 1024x8 macro ... inside the 4x2 floorplan".
   `RM_IHPSG13_1P_1024x8_c2_bm_bist` is 336.46 um tall; the 4x2 block is
   313.74 um tall (6.5), so the macro does not fit inside the block at
   all. **Applied**: docs/06 B.6 now names `RM_IHPSG13_1P_512x32` or
   `1P_512x16`, records the flip-flop-RAM pilot as 4x2 = 8 tiles and the
   SRAM-macro variant as 12 tiles, and B.6.1's gate decides macro
   content rather than tile count. This held independently of the
   section 8 recommendation.
2. **ROADMAP gate G0 can be closed.** The status note said "no retained
   run has yet reached a DRC result and LVS has not executed". Run
   `trial-03-signoff` (section 4.1) reaches Magic DRC 0, KLayout DRC 0
   and Netgen LVS 0 on all seven counters. **Applied**: the integrator
   has replaced the note with the `trial-03-signoff` result and a
   citation to this file.
3. **The tile geometry this document derived was superseded.** 6.5's
   interpolated pitch overestimated every two-row block by 8.4 %.
   **Applied**: 6.5 now quotes `docs/15-pilot-tile-plan.md` section 4.3,
   which reads the shapes out of `tt-support-tools`
   `tile_sizes.yaml` and the DEF templates. docs/15 is the authority for
   tile geometry; this file defers to it.

### 10.2 Things this document knows are unfinished

4. **The macro run was floorplanned on the interpolated 4x2 block, not
   on the measured one.** `hw/openlane/sram_pilot/config.json` sets
   `DIE_AREA` to `0 0 854.40 340.20`; the real 4x2 shape is
   `0 0 854.40 313.74` (6.5). The macro and its halo still fit inside
   the real block, so section 7's DRC/LVS/routing conclusions are
   unaffected, but a re-run at the true die is what would let section 7
   be quoted as a tile-shape result. One command; not done
   **[fact — not attempted]**.
5. **The KLayout LVS deck was never exercised.** LibreLane 3.0.5's
   Classic flow signs LVS off with Magic extraction + Netgen. The PDK
   also ships `libs.tech/klayout/tech/lvs/sg13g2.lvs`, which the flow
   does not call. Given how far the two DRC decks diverged on the macro
   (7.5), the LVS decks may diverge too. Untested.
6. **`TIMING_VIOLATION_CORNERS` is left at the PDK default `*typ*`.**
   Section 4.4 reports all three corners and all three are clean, so
   nothing is hidden today, but anything going to silicon should
   override it so slow and fast actually gate the flow.
7. **`VSRC_LOC_FILES` is unset**, so the IR-drop numbers in 4.6 are
   indicative only. Fine for a bring-up, not for a tapeout.
8. **`DRT-0349 LEF58_ENCLOSURE with no CUTCLASS`** is emitted for Cont,
   Via1-4, TopVia1 and TopVia2 on every run. Those enclosure rules are
   therefore enforced only by the signoff decks, not by the router. Both
   decks were clean on `aer_fifo`, so nothing was missed there; on a
   denser design it could cost a re-route late.
9. **The bus-delimiter half of the LVS failure (7.5, cause 2) has not
   been attempted.** It looks tractable and would be the first thing to
   try if the macro question is re-opened. Estimated a few hours
   **[estimate]**; it would not by itself make LVS pass, because the
   hierarchy-name cause remains.
10. **`MAGIC_MACRO_STD_CELL_SOURCE: PDK` is a workaround with a cost**
   (7.4): it changes which cell definitions Magic uses inside the macro,
   so the extracted view is not guaranteed to be the vendor hierarchy.
   Acceptable for a decision run, not for signoff.
11. **Run trees are gitignored and large.** As left on this machine:
   `trial-01` 404 MB, `trial-02-nohdi` 174 MB, `trial-03-signoff`
   439 MB, `macro-01` 64 MB, `macro-02` 67 MB, `macro-03` 421 MB —
   1.6 GB under `hw/openlane/` in total, none of it tracked. Everything
   cited in this document is quoted here in full for that reason. If a
   number is needed that is not quoted, the run has to be repeated with
   the commands in section 9. The trees can be deleted at any time
   without losing anything this document asserts.
