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
installed file; **[estimate]** = derived or judged; **[planned]** = an
intention with a date and no artifact (docs/00-index.md).

**Superseded in part, and the corrections are applied in place — read
this before any number below.** Sections 3.1, 3.2, 3.4, 4 and 5 report
run `sky-02-signoff`, which hardened the netlist **before** the
configuration-TMR synthesis fix. `docs/20-reharden-and-corners.md`
re-hardened the corrected netlist on both PDKs, ran the experiment this
document proposed, and its section 8.2 lists exactly what changes here.
Those corrections are applied below, each attributed to the run it came
from. Two consequences have to be carried through the whole file:

- **Every sky130 figure that states what the design *costs* — slack, area,
  utilization — is now quoted from `sky-04-tmr`**, hardened 2026-08-26
  06:35 to 07:04 with `hw/openlane/pilot_sky130/config.json` unchanged
  apart from the `SYNTH_HIERARCHY_MODE: deferred_flatten` the fix forces
  **[fact, `runs/sky-04-tmr/resolved.json`]**. Pre-fix figures are kept
  only where they are one half of a like-for-like comparison that would
  stop being like-for-like if one half were replaced — the PDK ratios of
  3.2 and the clock A/B of 3.3b — and each of those is labelled at the
  point of use.
- **`sky-04-tmr` is not the current design either, and the two PDKs have
  now diverged in *revision* as well as in technology.** A concurrent
  workstream hardened the `lif_core` memories with SECDED after that run
  — `hw/rtl/lif_core.v` last written **2026-08-26 07:33** — adding a
  `wchk` check field and an `smem` state codeword. The current RTL maps
  to **1,235 flip-flops against `sky-04-tmr`'s 1,155**, the extra 80
  being exactly 32 + 48 **[fact, measured with this repository's own
  synthesis recipe]**.

  **The IHP side has since been re-hardened against that RTL, twice. The
  sky130 side has not been re-hardened at all.** The current IHP run is
  `ihp-mix` (`hw/openlane/pilot_ihp/runs/ihp-mix/`, `final/metrics.json`
  timestamped 2026-08-27 01:26), same `ihp-sg13g2`, same 4x2 tile, same
  `CLOCK_PERIOD: 20`, closed to a GDS with `flow__errors__count: 0`:
  **181,043 um2 placed at 69.6756 % utilization** and a worst-corner
  setup slack of **+0.6315 ns**, against `sky-04-tmr`-era IHP figures of
  158,268 um2, 60.91 % and +6.4359 ns **[fact,
  `.../ihp-mix/final/metrics.json`,
  `design__instance__area__stdcell` and `design__instance__utilization`,
  and `.../ihp-mix/55-openroad-stapostpnr/summary.rpt`;
  `docs/15-pilot-tile-plan.md` section 4 is the full record]**. The
  intermediate run `ihp-memecc` (2026-08-27 00:03) measured 180,651 um2,
  69.52 % and +0.4035 ns. Sign-off stayed clean at both steps: Magic DRC
  0, Netgen LVS 0, antenna 0 nets / 0 pins, detailed-route DRC 0.

  *Corrected 2026-08-30 — the timing half of "sign-off stayed clean at
  both steps".* Both slacks are un-derated: this flow has never applied
  the 5 % OCV derate its configuration asks for, on either PDK
  (`docs/28` §4.4b). Re-derived on each run's own shipped artifacts,
  **`ihp-mix` is -0.3607 ns and `ihp-memecc` is -0.5999 ns at the slow
  corner** — **neither closes it** **[fact, standalone OpenSTA on
  `final/{nl,spef,sdc}`, the method of `docs/28` §11]**. The geometric
  half of the sentence — Magic DRC, LVS, antenna, route DRC — is
  unaffected and stays clean. What moved is that the IHP column of this
  document's central comparison was, at these two runs, a column that
  missed its own slow corner; section 3.3's correction note carries the
  full table. The document's thesis is untouched: sky130 misses by
  4.19 ns derated and IHP by 0.36, so the PDK gap this file measures is
  still an order of magnitude.

  **So every sky130 figure in this document — area, utilization, slack,
  diode count, wirelength, max-fanout — is a
  pre-memory-hardening measurement, and is now two RTL revisions behind
  the IHP figures it sits next to.** Where this file previously placed
  the two columns side by side as a like-for-like PDK comparison, that
  reading no longer holds and each such place now says so. Nothing here
  is scaled to guess what the hardening costs on sky130; the only honest
  way to get those numbers is to re-run
  `hw/openlane/pilot_sky130/run_sky130.sh`, which has **not** been done
  **[planned — no date and no artifact]**.

- **`ihp-mix` is the last word, and it was pinned so that it stays one.**
  `hw/rtl/pilot_top.v` was rewritten at **2026-08-27 00:17**, fourteen
  minutes after `ihp-memecc` finished, giving replica C of the
  configuration TMR an invertible XOR *mixing* transform (`MIX = 1`) in
  place of a polarity, so that it survives a forced flatten with no
  `keep_hierarchy` at all; a synthesis-only probe measured **+0.92 % cell
  area with the flip-flop count unchanged at 1,235** **[fact, run tags
  `memecc-synthcheck` and `memecc-synthcheck3` under
  `hw/openlane/pilot_ihp/runs/`; the RTL's own matched A/B in
  `hw/rtl/pilot_top.v` header section 9 measures +1.06 %, and `docs/20`
  section 11.6 tabulates it]**. That was the third time an `hw/rtl` write
  landed inside a quarter of an hour of a harden completing, so `ihp-mix`
  was run against sources pinned by `hw/openlane/pin_rtl.py` to a
  `git stash create` snapshot, commit-ish
  **`e4c850b3c7c3631e66721825ce829022c960a12e`** — the discipline section
  2.1 had to apply retrospectively to `sky-02-signoff` and that `docs/20`
  section 1.2 applies to every run from `sky-06` onward. The blobs it
  consumed:

  ```
  13c523519d55d80bcf0da0b54677a53ab9fb2e22  hw/rtl/pilot_top.v
  b196828f65c271d849cad0ad21536c561d2079af  hw/rtl/lif_core.v
  ac6edac5cb5e759359afe765c0c2f0f56c70acf6  hw/rtl/aer_fifo.v
  62b5f4d2a1eae095d9d4a8634ede55237e2c924d  hw/rtl/tmr_voter.v
  f7c7ec187a0df4eb09a8405dcda285de0fc2e44e  hw/rtl/secded_dec.v
  b5710b8a679c3e378e74953b621b99f0d8dc3014  hw/rtl/secded_enc.v
  e294afcf03e1947906086beeba2fd0c40b29441d  hw/rtl/tt_um_melihakbulut_nssoc.v
  9aaaa394e7a6ef855f5584fb85d53e688ac3e0b5  hw/rtl/npu_regs.vh
  ```

  **[fact, `git ls-tree e4c850b3:hw/rtl`]** — the first seven are
  `VERILOG_FILES` and the eighth is reached through the pinned
  `VERILOG_INCLUDE_DIRS`. `pilot_top.v` at
  `13c52351` is the revision carrying `MIX = 1` on `u_cfg_c`;
  `lif_core.v` at `b196828f` is the SECDED-hardened one. The IHP figures
  above are therefore settled for the RTL that run consumed, rather than
  provisional, which is a change from every earlier revision of this
  preamble. (`hw/rtl/pilot_top.v` has moved again since, on 2026-08-29,
  to connect the `lif_core` ECC status ports; that write costs `ihp-mix`
  nothing precisely because `ihp-mix` is pinned, and `docs/15` section 5.2
  carries it.) **`docs/15` section 4 no
  longer marks the tile budget open** — it records it as closed at 4x2
  with 0.46 % of the core spare, and records why the earlier reasoning
  ("the +0.92 % synthesis delta is larger than the 0.68 % spare, so the
  criterion is a coin toss") was wrong rather than merely uncertain:
  +0.92 % at synthesis landed as **+0.22 % of placed area**, because
  placement absorbed about three quarters of it. A synthesis-area delta
  is not a placed-area delta, and this document should not treat one as a
  proxy for the other on the sky130 side either.

The one finding that does **not** move with the RTL revision is section
3.3b's diagnosis, because it is a property of the flow and the PDK — a
parasitic model, not a netlist. That is why it is the durable result.

> **Superseded 2026-08-30 in three ways, and the preamble above is kept
> as the state it described.** Read this before the sky130 columns
> below.
>
> 1. **The sky130 side was re-hardened at 4x2, and it stopped routing.**
>    Run `sky-08-ptrtmr` on the pointer-TMR RTL reaches
>    **123,766 um2 placed at 82.96 % placement utilization** and then
>    diverges in detailed routing — 218,483 violations after the 0th
>    optimization iteration, 348,149 after the 1st, 364,603 after the
>    2nd, still rising when it was stopped **[fact, `docs/22`
>    section 5]**. It reached no sign-off deck, so it supersedes the
>    sky130 columns below **in status, not in value**: their zeros were
>    true of `sky-04-tmr` and are not statements about the current RTL at
>    4x2.
> 2. **At twelve tiles sky130 routes again, and the portability claim is
>    back and stronger.** `docs/23` section 5 hardens sky130 **6x2** and
>    **3x4** end to end: detailed routing, Magic DRC, the KLayout deck,
>    the Magic/KLayout XOR, Netgen LVS on all seven counters and the
>    antenna checks, **all zero on both**, with **zero global-route
>    overflow** against 4x2's 22,357 **[fact]**. What section 5 of
>    `docs/22` recorded as a portability failure was a **tile-size
>    failure**: sky130's 4x2 core is 149,183 um2 against IHP's 259,837,
>    and the design outgrew the smaller one first.
> 3. **The submission is no longer 4x2.** It is **6x2 = 12 tiles**
>    (`docs/23` sections 6 and 9.1), so this document's title and its
>    "same 4x2 tile count" framing describe the shape the comparison was
>    made at, not the shape being taped out. The IHP side has also
>    hardened twice more since `ihp-mix`: **185,755 um2 at 71.4890 %**
>    with **+0.9121 ns** slow-corner setup at 4x2 (`wave5-ihp-b`,
>    `0448282`), and **185,840 um2 at 47.2887 %** with **+1.2347 ns** on
>    the 6x2 submission shape **[fact, `docs/22` sections 9.3 and 9.5,
>    `docs/23` sections 2.1 and 3.1]**.
>
> One bookkeeping note, so that no figure is silently dropped.
> `docs/22` section 6.2 is written against `c5a5a6e` and its section 9.5
> excludes section 6.2 as a block from the `0448282` re-statement, on
> the grounds that no sky130 run exists at either commit — while listing
> the same IHP *quantities* individually as superseded. Both commits are
> therefore quoted below wherever section 6.2's replacement text carries
> an IHP number, `c5a5a6e` first and `0448282` beside it.

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
  20 ns the design closes the typical corner with **+8.7627 ns** of setup
  slack but **misses the slow corner by -2.9659 ns**, with **536 setup
  violations** and **4,756 max-slew violations** summed over the three
  `ss` corners (worst single corner 1,999; a further 251 slew violations
  sit at `tt`). On IHP the same RTL at the same 20 ns closed *all three*
  of its corners, worst slack **+6.4359 ns**. Hold is clean on all nine
  sky130 corners. Run `sky-04-tmr`; the superseded pre-fix figure was
  -3.8504 ns. Section 3.3. **[fact]** *The IHP half of that comparison
  has since moved to **+0.6315 ns** on the memory-hardened, `MIX`-carrying
  RTL (`ihp-mix`; `ihp-memecc` read +0.4035 ns), which sky130 has not been
  re-hardened against — the sign of the finding is unchanged, its size is
  not; see the preamble and section 3.3.*
- **The flow does not tell you that.** `design__violations` is **0** and
  the run completes, because the PDK ships
  `TIMING_VIOLATION_CORNERS: ["*tt*"]` and
  `MAX_SLEW_VIOLATION_CORNERS: [""]` — the setup checker only looks at
  the typical corners and the max-slew checker is switched off by a
  match-nothing wildcard. Neither is something this configuration chose.
  Section 3.3a. **[fact]**
- **A slower clock is not the fix, and that was measured too.** A second
  full run at **26 ns**, on the pre-fix netlist, moves the worst
  slow-corner slack from -3.8504 ns to only **-3.2007 ns** — **6 ns of
  extra period buys 0.65 ns where it is needed**. That measurement
  stands; `docs/20-reharden-and-corners.md` section 6.3 says so and
  supplies the reason, which is not the reason this document first gave.
  Section 3.3b. **[fact]**
- **The cause is a parasitic-model gap, not a corner missing from a
  list.** The steps that repair timing — CTS and every resizer — already
  load all nine corners, and the post-CTS setup pass *closes* the slow
  corner on its own wire estimate. `LAYERS_RC` is null for sky130A, so
  place-and-route optimizes against one averaged wire-RC number roughly
  **2.7 ns of WNS more optimistic** than the OpenRCX extraction sign-off
  uses; only **0.56 ns** of the miss is a genuine interconnect-corner
  effect. `PNR_CORNERS`, which this document originally proposed as the
  fix, has since been run and makes the corner **0.382 ns worse** at
  essentially zero area cost, and post-global-routing repair does not
  close it either. `docs/20-reharden-and-corners.md` sections 5 and 6 are
  the experiment; section 3.3b here is the summary. **[fact]**

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

Both are the **pre-fix** netlist, and that is deliberate for 3.1, 3.2
and 3.4: what those sections measure is a *difference between two PDKs*,
and the difference is only attributable if both columns hardened the same
RTL. Section 3.3 is the exception — a slack figure is a statement about
the design, not about a ratio — so it is re-stated there on the corrected
netlist from run **`sky-04-tmr`**, and the corresponding IHP figures come
from the re-harden **`tmr-reharden`**
(`docs/20-reharden-and-corners.md` sections 4 and 2.2).

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
technology, and it reproduces to the instance. That count is **still 6**
on every later run of both PDKs **[fact, `docs/22` section 9.3]**.

*Superseded in status 2026-08-30, and one cell superseded in value.*

- **The sky130A column is a `sky-04-tmr`-era result.** Every zero in it
  was measured and none of it is withdrawn, but it is **not established
  on the current RTL at 4x2**: `sky-08-ptrtmr` diverged in detailed
  routing and reached none of these steps **[fact, `docs/22`
  section 5]**. At twelve tiles the whole column is re-established —
  sky130 6x2 and 3x4 both return **0** on Magic DRC, the KLayout deck,
  the Magic/KLayout XOR, all seven Netgen counters, antenna and
  detailed-route DRC **[fact, `docs/23` section 5]**.
- **The ihp-sg13g2 "KLayout DRC — *not run*" cell is now a zero.** The
  deck was run on a variant config that differs from the submission
  config in that one key: `ihp-klayoutdrc-w5` reports
  `klayout__drc_error__count: 0` at `c5a5a6e` **[fact, `docs/22`
  section 2.4]**, and the 6x2 submission-shape run reports **0** as well,
  from a config that carries `RUN_KLAYOUT_DRC: 1` outright **[fact,
  `docs/23` section 1.3 and
  `hw/openlane/pilot_ihp/runs/shape-6x2/final/metrics.json`]**. The
  Magic/KLayout XOR is still **not run on IHP** and is not claimed.

### 3.2 Area and utilization [fact]

**The absolute figures in this table are superseded; the ratio column is
not.** Both columns predate the configuration-TMR fix. On the corrected
netlist the placed standard-cell area is **99,923.3 um2 at 66.98 %
utilization** on sky130A (run `sky-04-tmr`,
`hw/openlane/pilot_sky130/runs/sky-04-tmr/final/metrics.json`,
`design__instance__area__stdcell` and `design__instance__utilization`)
and **158,268 um2 at 60.91 %** on ihp-sg13g2 (run `tmr-reharden`,
`docs/20-reharden-and-corners.md` sections 4 and 8.1) **[fact]**. The
cross-PDK ratio therefore moves from 0.623 to **0.631** **[estimate,
arithmetic on the two measured areas]** — i.e. the PDK comparison this
table exists to make survives the fix almost unchanged, while the
headroom statement below gets sharper: sky130 sits **6.1 points above**
the IHP utilization rather than 4.5. Both of those figures predate the
`lif_core` SECDED work of the preamble.

**That pair, `sky-04-tmr` against `tmr-reharden`, is the last
like-for-like one this document has, and it should stay the pair that is
quoted.** On IHP the memory hardening and `MIX` have since been measured
— run `ihp-mix`, **181,043 um2 at 69.6756 %** **[fact,
`hw/openlane/pilot_ihp/runs/ihp-mix/final/metrics.json`]**, after
`ihp-memecc`'s 180,651 um2 at 69.52 %. On sky130 neither has: no run
exists against that RTL. Dividing 99,923.3 by 181,043 gives **0.552** and
would make sky130 look **2.7 points** *below* IHP in utilization rather
than 6.1 above, but that number is not a PDK ratio — it is a PDK
difference and two RTL revisions of design growth, added together, and
the terms cannot be separated from it. **Do not quote 0.552 as a
cross-PDK figure.** The like-for-like comparison is restored by one
command, `hw/openlane/pilot_sky130/run_sky130.sh --run-tag sky-07-memecc`
or similar, and until it is run the honest statement about the sky130
cost of the memory hardening and of `MIX` is that it is unmeasured
**[planned — no date and no artifact]**.

**Superseded 2026-08-30. The sky130 run was made, and it did not
route.** Three corrections to the two paragraphs above, none of which
touches the `sky-04-tmr` / `tmr-reharden` ratio they exist to protect.

- **"On sky130 neither has: no run exists against that RTL" is no longer
  true.** `sky-08-ptrtmr` exists and reaches **123,766 um2 at 82.96 %
  placement utilization**, then diverges in detailed routing and yields
  **no routed area and no sign-off figure** **[fact, `docs/22`
  section 5]**. The like-for-like gap it was meant to close is still
  open at 4x2, and it is now blocked behind a routing problem rather
  than a scheduling one.
- **The latest IHP figures.** `docs/22` section 6.2 gives
  **184,969 um2 at 71.1867 %** (`wave5-ihp`, `c5a5a6e`); at `0448282`
  the same run series reads **185,755 um2 at 71.4890 %**
  (`wave5-ihp-b`), and on the 6x2 submission shape **185,840 um2 at
  47.2887 %** **[fact, `docs/22` sections 9.3 and 9.5, `docs/23`
  section 2.1]**. **The instruction above still stands**: the
  `sky-04-tmr` / `tmr-reharden` pair remains the only like-for-like one
  this document has, and it should stay the quoted ratio. Do not divide
  any of these three by a sky130 area.
- **"sky130 sits 6.1 points above the IHP utilization"** is unchanged as
  a statement about that pair. On the current RTL at 4x2 the placement
  utilizations are **82.96 % sky130 against 71.19 %** (`c5a5a6e`) or
  **71.49 %** (`0448282`) IHP — about **11.5 to 11.8 points above**
  **[estimate, arithmetic on measured utilizations]**. At twelve tiles
  the sign of that gap survives and the magnitude collapses: **55.88 %
  sky130 6x2 against 47.29 % IHP 6x2**, 8.6 points **[fact, `docs/23`
  sections 2.1 and 5]**. The mechanism is the one this section already
  names — the sky130 tile is smaller in absolute terms at every shape,
  so the same design lands denser on it.

There is now a measured reason to expect that a sky130 re-run would not
be predictable from synthesis. On IHP, `MIX` cost **+0.92 % of synthesis
area** and only **+0.22 % of placed area**: the extra XOR2 cells arrived
with *less* resizer repair, not more, and placement absorbed roughly
three quarters of the delta **[fact, `docs/15` section 4 head, comparing
`ihp-memecc` and `ihp-mix`]**. Section 3.2's own place-and-route growth
factors (1.2733 sky130, 1.2628 IHP) are averages over a whole design and
say nothing about an increment of a percent. So the sky130 cost is
unmeasured in the strong sense: it cannot be bounded by scaling the
sky130 synthesis area either.

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
`hw/openlane/pilot_sky130/runs/sky-04-tmr/55-openroad-stapostpnr/summary.rpt`
— the **corrected** netlist, 1,155 flip-flops. `sky-02-signoff`, the
pre-fix run the rest of this document reports, sat at **-3.8504 ns** on
the same corner; that number is superseded and
`docs/20-reharden-and-corners.md` section 4 tabulates the move. The
endpoint counts did not change with the fix: 536 setup-violating
endpoints summed over the nine corners, 179 at the worst one, before and
after.

**sky130A ships nine STA corners, not three.** `STA_CORNERS` is
`nom/min/max` interconnect crossed with `tt_025C_1v80`, `ss_100C_1v60`
and `ff_n40C_1v95`; the IHP PDK ships three `nom_*` corners only, so it
varies PVT but not RC. The sky130 run is therefore analysed *harder*
than the IHP run was, and that has to be said before the two are
compared.

| Corner | Worst setup | Worst hold | Setup vio | Hold vio | Max cap | Max slew |
|---|---|---|---|---|---|---|
| `nom_tt_025C_1v80` | **+8.7627** | +0.3176 | 0 | 0 | 0 | 81 |
| `min_tt_025C_1v80` | +9.1180 | +0.3141 | 0 | 0 | 0 | 13 |
| `max_tt_025C_1v80` | +8.4664 | +0.3206 | 0 | 0 | 0 | 157 |
| `nom_ss_100C_1v60` | **-2.4380** | +0.9046 | **179** | 0 | **1** | **1,625** |
| `min_ss_100C_1v60` | -1.7940 | +0.8962 | **178** | 0 | 0 | **1,132** |
| `max_ss_100C_1v60` | **-2.9659** | +0.9103 | **179** | 0 | **1** | **1,999** |
| `nom_ff_n40C_1v95` | +12.8409 | +0.1112 | 0 | 0 | 0 | 0 |
| `min_ff_n40C_1v95` | +12.9474 | **+0.1089** | 0 | 0 | 0 | 0 |
| `max_ff_n40C_1v95` | +12.6384 | +0.1134 | 0 | 0 | 0 | 0 |

Against the IHP reference at the same 20 ns, run `tmr-reharden`
(`docs/20-reharden-and-corners.md` sections 2.2 and 7.1) — **the
like-for-like column, because it hardened the same RTL revision as
`sky-04-tmr`**:

| Corner | Worst setup | All four vio counters |
|---|---|---|
| `nom_slow_1p08V_125C` | **+6.4359** | 0 |
| `nom_typ_1p20V_25C` | +11.4227 | 0 |
| `nom_fast_1p32V_m40C` | +14.1670 | 0 |

Hold is clean on all three there too, worst **+0.646 ns** at the slow
corner and **+0.119 ns** at the fast one.

**The IHP column has since moved twice and the sky130 column has not
moved at all.** On the memory-hardened, `MIX`-carrying RTL, run
`ihp-mix`
(`hw/openlane/pilot_ihp/runs/ihp-mix/55-openroad-stapostpnr/summary.rpt`)
**[fact]**:

| Corner | Worst setup | Worst hold | All four vio counters | `ihp-memecc`, for the step before |
|---|---|---|---|---|
| `nom_slow_1p08V_125C` | **+0.6315** | +0.6278 | 0 | +0.4035 |
| `nom_typ_1p20V_25C` | +7.7094 | +0.3041 | 0 | +7.5537 |
| `nom_fast_1p32V_m40C` | +11.9259 | +0.1180 | 0 | +11.8083 |

IHP still closes all three corners at 20 ns with every violation counter
at zero, so the qualitative finding of this section survives: sky130
misses a corner that IHP meets. What does not survive is the *size* of
the gap as this document states it, because **5.80 ns of the IHP margin
has gone, net, since `tmr-reharden`, and sky130 has not been asked to pay
the same bill** (preamble). The memory hardening took 6.03 ns of it; the
`MIX` step gave 0.23 ns back — a larger netlist closed *better* on every
corner — which is worth noting here only as a caution about
extrapolating slack from netlist size, on either PDK. Any arithmetic below that subtracts an IHP slack from a
sky130 slack is quoted on the `tmr-reharden` / `sky-04-tmr` pair and
should stay that way until a sky130 run exists on the current RTL.

**Superseded 2026-08-30.** The reference table above is still correct
for `tmr-reharden` and is not withdrawn. Three corrections:

- **The IHP column has now moved four times, not twice**, and the
  current values are, in order: `ihp-mix` +0.6315 / +7.7094 / +11.9259;
  `wave5-ihp` (`c5a5a6e`) **+1.1554 / +8.0521 / +12.1355**;
  `wave5-ihp-b` (`0448282`) **+0.9121 / +7.8999 / +11.9855**; and on the
  6x2 submission shape **+1.2347 / +8.1297 / +12.1329**, the best slow
  corner of any harden of this netlist. Every setup, hold, max-cap and
  max-slew counter is zero at all three corners in each **[fact,
  `docs/22` sections 2.3, 9.3 and 9.5; `docs/23` section 3.1]**. Worst
  hold on the fast corner is **+0.1180 ns** at 4x2 and **+0.1089 ns** at
  6x2.
- **The sky130 column has moved too, and not in a way that helps.** A
  sky130 run on the current RTL was attempted at 4x2 and **does not
  route**, so the -2.9659 ns at `max_ss_100C_1v60` is still the last
  measured sky130 slack, still on `sky-04-tmr`, and it is neither
  confirmed nor superseded **[fact, `docs/22` section 5.2]**. At twelve
  tiles the corner is measurable again and the miss is **worse, not
  better**: **-5.4953 ns at 3x4** and **-7.3054 ns at 6x2**, 227
  violating paths in both **[fact, `docs/23` section 5]**. That is the
  same corner sky130 has always missed, now measured on a larger
  netlist — not a shape effect being discovered.
- **The instruction stands and its condition is still not met.** Do not
  subtract a current IHP slack from a `sky-04-tmr` slack: at 4x2 there
  is no routed sky130 netlist to subtract from, and at twelve tiles the
  two PDKs are no longer the same shape as the pair above. Read as
  frequency, the current IHP slow-corner path is **19.088 ns ->
  52.4 MHz** at 4x2 and **18.765 ns -> 53.3 MHz** at 6x2 **[estimate,
  arithmetic on a measured slack]** — replacing this section's
  53.1 MHz (`wave5-ihp`) and the 51.6 MHz below, and belonging in the
  IHP column only.
  *Corrected 2026-08-30: both are un-derated (`docs/28` §4.4b).
  Derated, 4x2 is **-0.0675 ns -> 49.8 MHz** and does **not** make the
  50 MHz target, and 6x2 is **+0.2913 ns -> 50.7 MHz** and does. The
  sky130 figures in this bullet move the same way and further: the
  twelve-tile misses become **-6.8359 ns at 3x4** and **-8.7163 ns at
  6x2**, and `sky-04-tmr`'s -2.9659 becomes **-4.1908**. The bullet's
  instruction — do not subtract a current IHP slack from a
  `sky-04-tmr` slack — is unchanged.*

**Read as frequency [estimate — a single-point extrapolation from one
run, and a weak one on the sky130 side: 3.3b shows the flow optimized
this design against a wire model it is not signed off against, so the
slow-corner figure below is what *this* run achieved, not what the design
is capable of on sky130]:**

| | sky130A (`sky-04-tmr`) | ihp-sg13g2 (`tmr-reharden`) |
|---|---|---|
| Typical-corner path | 20 - 8.7627 = 11.237 ns -> **89.0 MHz** | 20 - 11.4227 = 8.577 ns -> 116.6 MHz |
| **Slow-corner path** | 20 + 2.9659 = 22.966 ns -> **43.5 MHz** | 20 - 6.4359 = 13.564 ns -> 73.7 MHz |

Both columns are the same RTL revision, which is the only reason the
comparison means anything. So as hardened here the design is roughly
**41 % slower at the slow corner** on sky130 than on IHP, and 50 MHz —
the rate `tt/info.yaml` declares and docs/06 section B.2 budgets — **is
not met at `ss_100C_1v60`**. How much of that 41 % is the process and how
much is the PnR parasitic model of 3.3b is *not* separated by this run;
3.3b is why that distinction has to be made. Hold is clean everywhere,
with the thinnest margin +0.1089 ns at `min_ff`, which is
`PL_RESIZER_HOLD_SLACK_MARGIN: 0.1` working exactly as configured — the
same behaviour the IHP run shows at +0.119 ns.

On the current IHP RTL the IHP column would read
20 - 7.7094 = 12.291 ns -> **81.4 MHz** typical and
20 - 0.6315 = 19.369 ns -> **51.6 MHz** slow **[estimate, arithmetic on
the `ihp-mix` slacks; `ihp-memecc` gave 80.3 and 51.0 MHz]**. That is a
real and useful number for the IHP submission — it clears the 50 MHz
`tt/info.yaml` declares by about 3 % — but it must **not** be put in the
table above, because the sky130 column has no matching run and the
difference would then be reporting design growth as a PDK effect.

> **Corrected 2026-08-30: "it clears the 50 MHz `tt/info.yaml` declares
> by about 3 %" is false, and both runs named in this paragraph miss
> the target once the derate is honest.**
>
> `docs/28` section 4.4(b) establishes that this flow has never applied
> the 5 % on-chip-variation derate its configuration asks for.
> `TIME_DERATING_CONSTRAINT` is the integer `5` in **both** PDKs and
> LibreLane's `base.sdc` computes the factor as `expr 5 / 100`, Tcl
> integer division, which is `0`; the factors are 1.0 and 1.0 while the
> log reports "Setting timing derate to: 5%". Every slack in this
> document, on both PDKs, is an un-derated number.
>
> Re-derived on each run's own shipped netlist, parasitics, constraints
> and liberty — the method of `docs/28` section 11, which reproduces
> each run's own metric to 17 significant digits before the derate
> lines are added **[fact]**:
>
> | Run | Slow setup, as signed off | **Slow setup, derated** | Slow Fmax as signed off | **Slow Fmax derated** |
> |---|---|---|---|---|
> | `ihp-mix` | +0.6315 | **-0.3607** | 51.6 MHz | **49.1 MHz** |
> | `ihp-memecc` | +0.4035 | **-0.6000** | 51.0 MHz | **48.5 MHz** |
> | `tmr-reharden` (the table's IHP column) | +6.4359 | **+5.7331** | 73.7 MHz | **70.1 MHz** |
> | `sky-04-tmr` (the table's sky130 column, `max_ss`) | -2.9659 | **-4.1908** | 43.5 MHz | **41.3 MHz** |
>
> **[fact for the slacks, standalone OpenSTA on each run's
> `final/{nl,spef,sdc}`; estimate for the frequencies, on the linearity
> `docs/28` section 5.6 measures.]**
>
> **What moved.**
>
> - **Neither `ihp-mix` nor `ihp-memecc` clears 50 MHz derated.** Both
>   miss the slow corner outright, by 0.36 ns and 0.60 ns. "A real and
>   useful number for the IHP submission" is withdrawn: it was a number
>   that depended on a Tcl integer division. `docs/13` carried this
>   same `ihp-mix` sign-off into its funding application and has been
>   corrected accordingly.
> - **The paragraph's actual instruction is unaffected and is now
>   better founded.** Keeping this figure out of the cross-PDK table
>   was right for the reason given, and is right for a second reason:
>   the figure was not a target-clearing one.
> - **The table itself, and the 41 % conclusion, are unchanged.** Both
>   columns are un-derated and both move by a similar proportion, so
>   the sky130-versus-IHP ratio and the "not met at `ss_100C_1v60`"
>   verdict stand exactly as written. The sky130 miss is 1.22 ns larger
>   derated, which reinforces it.

The critical path is unchanged in kind: it still runs through the SECDED
XOR trees on the weight-load path, not the neuron scan.

Power at typical, 1.80 V, 50 MHz, **on the pre-fix `sky-02-signoff`
netlist and not re-measured on the corrected one**: **4.960 mW** (3.530
internal, 1.431 switching, 0.16 uW leakage), against 4.255 mW at 1.20 V
on IHP. Worst IR drop 0.070 mV on VPWR and 0.082 mV on VGND, 0
power-grid violations; on `sky-04-tmr` the equivalent drops are 0.094 mV
and 0.104 mV with the same 0 violations **[fact,
`runs/sky-04-tmr/final/metrics.json`]**. `VSRC_LOC_FILES` is unset, so
all of these are indicative rather than sign-off numbers.

#### 3.3a Why the flow reported `design__violations: 0` anyway [fact]

536 setup violations and 5,007 max-slew violations across the nine
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
three corners were clean anyway; on sky130 it hides a 2.97 ns setup miss
and 1,999 slew violations, and the flow exits 0. **A green LibreLane run
is not a statement that timing closed.** The fix did not change this: it
hid 3.85 ns and 1,526 violations on `sky-02-signoff` and hides 2.97 ns
and 1,999 on `sky-04-tmr`, with `design__violations: 0` both times.

For completeness, the max-slew violators at the typical corner are
marginal — on `sky-02-signoff`, 11 pins at 0.7897 ns against a 0.75 ns
`MAX_TRANSITION_CONSTRAINT`, i.e. 5 % over. The per-pin decomposition was
not repeated on `sky-04-tmr`; there the `tt` corners carry 251 of these
between them against 1,999 at `max_ss`. The constraint itself is the
sky130 PDK default, not a value this config set.

#### 3.3b Relaxing the clock does not fix it — measured [fact]

Both runs in this subsection are the **pre-fix** netlist, and that is
correct for what it measures: it is a controlled A/B in which the only
variable is `CLOCK_PERIOD`, so both arms must harden the same RTL. The
A/B result stands unchanged after the fix —
`docs/20-reharden-and-corners.md` section 6.3 re-states it explicitly and
supplies the reason for it. The *explanation* this subsection originally
gave, however, was wrong in three specific ways, and the corrected
account is below the table.

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

**The mechanism is not the one this section first proposed.** The
original account here was that the slow corner is invisible to
place-and-route until the final STA, and that putting it into
`PNR_CORNERS` would therefore close it. That has now been tested and it
is wrong on every limb. What follows is the corrected account, with the
evidence read out of this document's own runs where the run tree carries
it and cited to `docs/20-reharden-and-corners.md` where the experiment
that establishes it is recorded there.

- **The steps that repair timing are already multi-corner, and CTS is
  one of them.** `OpenROADStep.run` does take
  `corners = PNR_CORNERS or [DEFAULT_CORNER]`
  (`librelane/steps/openroad.py:351`), but `CTS` overrides it with
  `CTS_CORNERS or STA_CORNERS` (`openroad.py:2548`) and **every**
  `ResizerStep` overrides it with `RSZ_CORNERS or STA_CORNERS`
  (`openroad.py:2393`). Both resolve to all nine corners with
  `PNR_CORNERS` unset. In `sky-02-signoff` itself,
  `35-openroad-cts` and `37-openroad-resizertimingpostcts` each log
  `Reading timing models for corner` **nine times, once per corner,
  `ss` included** **[fact, grepped in both step logs]**. The single-corner
  set is floorplan, placement, routing, the mid-PnR STA reports and the
  antenna steps — and none of those acts on a slack number
  (`PL_TIMING_DRIVEN` is `False` and the logged `global_placement`
  command carries no `-timing_driven`;
  `docs/20-reharden-and-corners.md` section 5.3).
- **The single `or_metrics_out.json` key proves nothing about
  `PNR_CORNERS`.** The observation is real — `36-openroad-stamidpnr-1`,
  `38-openroad-stamidpnr-2` and `43-openroad-stamidpnr-3` each contain
  exactly one `timing__setup_vio__count__corner:*` key — but the
  inference drawn from it was invalid. `STAMidPNR` writes metrics for one
  corner **unconditionally**: its script iterates the corner dictionary
  and `break`s on the first entry
  (`librelane/scripts/openroad/sta/corner.tcl:51-55`). A single key is
  evidence about that `break`. `docs/20-reharden-and-corners.md` section
  5.3a demonstrates it directly, with a step that loads two corners and
  still emits one.
- **The post-CTS resizer did not run "too early to help" — it closed the
  slow corner outright.** The earlier claim that it "inserted only 22
  setup buffers" undercounted its work by an order of magnitude and got
  the conclusion backwards. In `sky-02-signoff`,
  `37-openroad-resizertimingpostcts` performed **250 gate upsizes, 21 pin
  swaps, 22 buffer insertions and 14 buffer removals**, and drove
  worst-corner WNS from **-9.612 ns to +0.052 ns** **[fact,
  `runs/sky-02-signoff/37-openroad-resizertimingpostcts/openroad-resizertimingpostcts.log`,
  `RSZ-0051`/`RSZ-0043`/`RSZ-0040`/`RSZ-0059` and the iteration table]**.
  It saw the `ss` corner, it worked on it, and on its own parasitic
  estimate it *passed*.
- **What it could not see is the wire model.** `LAYERS_RC` is **null**
  for sky130A **[fact, `runs/sky-04-tmr/resolved.json`]**, so `set_rc.tcl`
  takes its no-custom-RC branch, calls `set_wire_rc` with no `-corner`,
  and applies one averaged tech-LEF number to every corner. There is no
  `max`-interconnect model anywhere inside place-and-route; the only one
  is in OpenRCX, which runs after the last step that could act on it.
  `ihp-sg13g2` by contrast ships an explicit per-metal `LAYERS_RC` and
  only a `nom_*` extraction ruleset, so its two models are close to each
  other. `docs/20-reharden-and-corners.md` section 6.2.
- **The size of the gap, measured.** On `sky-06-postgrt` the chain reads
  +0.084 ns leaving the post-GRT resizer on the routing estimate against
  **-2.614 ns** at `nom_ss` on the OpenRCX extraction — same PVT, same
  nominal interconnect corner — and **-3.176 ns** at `max_ss`. So **~2.7
  ns of WNS is the model gap and only 0.56 ns is a genuine
  interconnect-corner effect** **[fact,
  `docs/20-reharden-and-corners.md` section 6.2]**. The same shape is
  visible in this document's own run: `sky-02-signoff` left the post-CTS
  resizer at +0.052 ns and signed off at -3.3056 ns on `nom_ss`, a gap of
  **3.36 ns** **[estimate, arithmetic on two measured slacks]**. The gap
  is a property of the flow and the PDK, not of a particular netlist,
  which is why it is the finding that survives the RTL churn described in
  the preamble.
- **There is no repair step after routing by default.** LibreLane skips
  both `Repair Design (Post-Global Routing)` and `Resizer Timing
  Optimizations (Post-Global Routing)`, in this run as in the IHP one
  (docs/12 section 4) **[fact, `Skipping step` lines in the flow log]**.
  That much of the original account was right — but turning them on has
  now been tried too, and it does not close the corner either.

**What was actually needed, and what testing it showed [fact — this was
run, in `docs/20-reharden-and-corners.md`]:** the fix proposed here was
`PNR_CORNERS` including the slow corner, or `DEFAULT_CORNER` moved to it,
plus the post-global-routing repair steps. `sky-05-pnrcorners` set
`PNR_CORNERS: ["nom_tt_025C_1v80", "max_ss_100C_1v60"]` against the
`sky-04-tmr` baseline and moved the slow corner from -2.9659 ns to
**-3.3475 ns — 0.382 ns worse**, at essentially zero area cost, and the
layouts are byte-identical through global routing, so it optimized
nothing; it perturbed the antenna-repair loop and the perturbation landed
the wrong way. `sky-06-postgrt` added both post-GRT repair steps and
reached **-3.176 ns**, better than the `PNR_CORNERS` run and still worse
than the plain baseline, though it removed **42 % of the total** negative
slack for 1.3 um2. On IHP `PNR_CORNERS` produces a **byte-identical**
layout and identical slack. `PNR_CORNERS` should be recorded as **tested
and inert**, not as untested. Sections 5, 6 and 7 of
`docs/20-reharden-and-corners.md` are the full investigation and are not
reproduced here.

**The remaining candidates [estimate — not run]**, from
`docs/20-reharden-and-corners.md` section 6.3, follow from the diagnosis
rather than from the corner list: populate `LAYERS_RC` for sky130A from
the OpenRCX `max` ruleset so the PnR estimate matches the corner the
design is signed off at — a config change, and `ihp-sg13g2` demonstrates
the shape of it — or use `SIGNAL_WIRE_RC_LAYERS` as a cruder lever on the
same averaged number. `CLOCK_PERIOD` remains the wrong knob and the A/B
above is still the evidence for that; what has changed is that the reason
is now known, and it is that the period does not change the model gap.
Estimating the achievable sky130 frequency from these runs is not sound,
because all of them were optimized against a wire model the sign-off does
not use.

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
gates anything. Max cap is 0 at all nine sky130 corners here, which is
what max-fanout is a proxy for.

Both counters move on the corrected netlist and the decomposition above
was not repeated on it: **98 on sky130** (`sky-04-tmr`,
`final/metrics.json`, again identical across all nine corners) and **77
on IHP** (`tmr-reharden`, `docs/20-reharden-and-corners.md` section 8.1)
**[fact]**. On the current IHP RTL the counter reads **82** (`ihp-mix`,
again identical across all three corners; `ihp-memecc` read 84), and
there the decomposition *was* repeated and confirms this section's
finding on a second PDK: **all 82 are CTS clock buffers**
(`clkbuf_leaf_*_clk/X`, the worst seven at 18 loads), every one held to
`sg13g2_stdcell_typ_1p20V_25C.lib`'s `default_max_fanout` of 8 rather
than to the design's `MAX_FANOUT_CONSTRAINT: 10` **[fact,
`hw/openlane/pilot_ihp/runs/ihp-mix/55-openroad-stapostpnr/nom_typ_1p20V_25C/checks.rpt`;
`docs/15` section 5.3]**. `ihp-memecc` had 83 clock buffers plus one
resizer-inserted `fanout924/X`; that cell is absent from the `ihp-mix`
list, which is the same story as its lower repair-buffer count. Not one
violator is an RTL net on either PDK.
There is no corresponding sky130 number for the current RTL. Max cap is no longer uniformly 0 either — `sky-04-tmr`
reports **one** max-cap violation, at `nom_ss` and `max_ss` and nowhere
else (section 3.3). One violating pin at the two slowest corners is the
same marginal signal the slew counts carry, not a new class of problem.

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
  `design__instance_unmapped__count: 0` on both PDKs. That was originally
  written as evidence for the docs/15 section 4.2 reasoning about *not*
  copying the sibling project's `SYNTH_HIERARCHY_MODE: deferred_flatten`
  workaround; **that reasoning has since been withdrawn on both PDKs**.
  The configuration-TMR repair builds each replica as a parameterised
  `keep_hierarchy` module, which makes yosys derive `$paramod` types that
  the checker counts as unmapped, so `deferred_flatten` is required — and
  `hw/openlane/pilot_sky130/config.json` now carries it (section 7). The
  count above is 0 *because* the setting is present, not because it is
  unnecessary. What genuinely ports is that the same one key fixes it on
  both technologies.
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
LVS and DRC are all clean while the slow corner misses setup by 3.85 ns
on this run, and by 2.97 ns on the corrected netlist. Section 6 is what
follows from that. The manufacturability result itself survives the fix:
`sky-04-tmr` reports route DRC, Magic DRC, KLayout DRC, XOR and Netgen
LVS all **0**, and 0 antenna-violating nets, exactly as here **[fact,
`runs/sky-04-tmr/final/metrics.json`;
`docs/20-reharden-and-corners.md` section 4]**.

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
  technology rather than only this one. **Read that as a whole-design
  average and nothing finer.** On IHP the same factor has since been
  measured at 1.2497, 1.2347 and 1.2262 on three consecutive re-hardens
  of the same design on the same floorplan **[fact, `docs/15` section
  4.1]**, so it does not transfer to an increment: a one-percent RTL
  change is not a one-percent placed change, and `docs/15` section 4 head
  records what happened when this programme assumed otherwise.

**Not proved, and the list is longer than the first one:**

- **Timing does not port, and this run is the counter-example.** Same
  RTL, same constraint, +6.44 ns of slow-corner slack on IHP and -2.97 ns
  on sky130 (`tmr-reharden` against `sky-04-tmr`). Any statement of the
  form "the design runs at 50 MHz" is a statement about a PDK, not about
  the design. `tt/info.yaml`'s `clock_hz: 50000000` is correct for the
  IHP submission it describes and would be wrong on a sky130 shuttle
  without a re-close. **On the current RTL the IHP side is down to
  +0.63 ns at the slow corner (`ihp-mix`, after `ihp-memecc`'s
  +0.40 ns), so `clock_hz: 50000000` is now correct by about 1.6 MHz
  rather than by 24; sky130 has not been re-hardened against that RTL and
  the gap between the two PDKs is therefore no longer measured.**
  *Corrected 2026-08-30: `clock_hz: 50000000` was **not** correct on
  either of those runs. Both slacks are un-derated (`docs/28` §4.4b);
  derated, `ihp-mix` is **-0.3607 ns** and `ihp-memecc` **-0.6000 ns**,
  so both miss 50 MHz — by 0.9 MHz and 1.5 MHz — rather than clearing it
  by 1.6 (section 3.3's correction note). The bullet's own thesis, that
  "the design runs at 50 MHz" is a statement about a PDK and a run
  rather than about the design, is unaffected and is illustrated better
  by the corrected numbers than by the original ones.*
- **The sky130 frequency is still not established, and the reason is now
  known.** The run this document originally said had to be made — the
  slow corner inside `PNR_CORNERS` — **has been made**, on both PDKs, and
  it changes nothing: `sky-05-pnrcorners` lands 0.382 ns *worse* than its
  baseline with a layout byte-identical through global routing, and on
  IHP the layout is byte-identical outright
  (`docs/20-reharden-and-corners.md` sections 5 and 7). Post-global-
  routing repair was tried as well and reaches -3.176 ns. So the
  number is unknown not because a corner was missing from a list, but
  because **the PnR wire-RC estimate and the OpenRCX extraction disagree
  by about 2.7 ns of WNS on this design** — the flow optimizes against a
  model it is not signed off against, and only 0.56 ns of the miss is a
  genuine interconnect-corner effect (section 3.3b,
  `docs/20-reharden-and-corners.md` section 6.2). Quoting 43.5 MHz as a
  sky130 capability would be wrong in the same way quoting 50 MHz would
  be. The number becomes knowable when `LAYERS_RC` is populated for
  sky130A and the design re-closed against a wire model that matches the
  sign-off; that has not been done **[planned — named as the first thing
  to try in `docs/20-reharden-and-corners.md` section 6.3, no date and no
  artifact yet]**.
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
  option is open at a known cost — a re-close against a corrected wire
  model, and a slower part — and that is the whole claim.

**The one-sentence version:** the design is manufacturably portable and
temporally not, which is exactly the distinction a gate that checks
Antenna, LVS and DRC cannot make for you.

> **Superseded 2026-08-30 in scope, and the conclusion survives with a
> qualifier the original did not have.** This section concludes that
> portability holds for structure and stops at timing. Two later rounds
> add a term between them: **it also stops at the tile, and the tile is
> a PDK-specific quantity.**
>
> - **At 4x2 on the current RTL, sky130 does not reach a routed netlist
>   at all** — `sky-08-ptrtmr` diverges in detailed routing at 82.96 %
>   placement utilization **[fact, `docs/22` section 5]**. For one round
>   this read as portability failing earlier than timing.
> - **At twelve tiles it routes, and the first bullet of "Proved" is
>   re-established on a larger netlist than it was first written for.**
>   sky130 6x2 and 3x4 both complete the whole sign-off, zero on every
>   deck including the Magic/KLayout XOR, which this document had never
>   run to a zero on a shape this size **[fact, `docs/23` section 5]**.
>   The 4x2 failure was a **tile-size** failure, not a technology one:
>   the sky130 4x2 core is 149,183 um2 against IHP's 259,837, so the
>   design outgrows the smaller tile first. This is the same asymmetry
>   section 3.2 already flagged as "the number to watch if the design
>   grows", and it is what happened.
> - **"Timing does not port" is confirmed and is worse.** On the
>   twelve-tile netlists sky130 misses `max_ss_100C_1v60` by **-5.4953 ns
>   at 3x4** and **-7.3054 ns at 6x2** with 227 violating paths, while
>   IHP closes all three of its corners at both shapes **[fact,
>   `docs/23` sections 3.1 and 5]**. The IHP half of the comparison is
>   now **+1.2347 ns** at 6x2 rather than the +0.63 ns quoted above, so
>   `clock_hz: 50000000` is correct by about 3.3 MHz rather than 1.6.
>   *Corrected 2026-08-30: both figures are un-derated (`docs/28`
>   §4.4b). Derated, the 6x2 run is **+0.2913 ns** and
>   `clock_hz: 50000000` is correct by about **0.7 MHz**, not 3.3; the
>   +0.63 ns run it is compared against was **-0.3607 ns** and did not
>   make the target at all. The declared clock is still met on the
>   submitted shape, with a quarter of the margin this sentence claims.
>   The sky130 half is unchanged in direction and larger in magnitude:
>   -7.3054 ns at 6x2 becomes **-8.7163 ns** derated, so "timing does
>   not port is confirmed and is worse" is confirmed again.*
>   Section 3.3b's parasitic-model diagnosis was **not** re-tested at
>   twelve tiles and remains the open item it was **[planned — no date
>   and no artifact, `docs/23` section 10 item 6]**.
>
> **The one-sentence version, restated:** the design is manufacturably
> portable at a tile count large enough to route it, temporally not, and
> the tile count that is large enough is not the same number on both
> PDKs.

---

## 7. Reproducing this

```
# nothing is installed; the PDK is already enabled at the LibreLane pin
export PDK_ROOT=$HOME/.ciel
ls -la $PDK_ROOT/sky130A     # -> ciel/sky130/versions/8afc8346.../sky130A

# the run recorded in sections 3.1, 3.2, 3.4, 4 and 5 -- but see 2.1:
# neither hw/rtl nor config.json is still what this run consumed
hw/openlane/pilot_sky130/run_sky130.sh --run-tag sky-02-signoff

# the relaxed-clock run of section 3.3b
hw/openlane/pilot_sky130/run_sky130.sh --run-tag sky-03-clk26 -c CLOCK_PERIOD=26

# the corrected-netlist re-harden that sections 3.2 and 3.3 now quote
hw/openlane/pilot_sky130/run_sky130.sh --run-tag sky-04-tmr

# NOT RUN: the sky130 counterpart of the two IHP re-hardens. Every sky130
# number in this file predates hw/rtl/lif_core.v's SECDED memory coding
# AND the MIX transform in hw/rtl/pilot_top.v. This is the command that
# would restore the like-for-like comparison of 3.2 and 3.3; nothing in
# this document is scaled to stand in for it. Pin it, the way the IHP
# side now does -- see the preamble for the blob list ihp-mix consumed:
#   python3 hw/openlane/pin_rtl.py <commit-ish> \
#       hw/openlane/pilot_sky130/config.json <dest>
#   CONFIG=<dest>/config.json hw/openlane/pilot_sky130/run_sky130.sh \
#       --run-tag sky-07-memecc --force-run-dir <dest>/run

# the gate of section 5, applied by hand
R=hw/openlane/pilot_sky130/runs/sky-02-signoff/76-misc-reportmanufacturability
grep -c 'Passed ✅' $R/manufacturability.rpt     # must be 3
```

If the PDK is not enabled, `run_sky130.sh` refuses to run and prints the
`ciel enable --pdk-family sky130 <hash>` line to fix it, or accepts
`ENABLE_PDK=1` to do it itself. `tt/tt/` must be present (2.4).

The corner experiments of section 3.3b are **not** reproduced from this
file: their configs are generated rather than hand-written and the
commands are in `docs/20-reharden-and-corners.md` section 10. `sky-04-tmr`
additionally requires `SYNTH_HIERARCHY_MODE: deferred_flatten`, which the
configuration-TMR fix forces and which
`hw/openlane/pilot_sky130/config.json` now carries.

Files this document owns: `hw/openlane/pilot_sky130/config.json`,
`hw/openlane/pilot_sky130/run_sky130.sh`, and itself.
