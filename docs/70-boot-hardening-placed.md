# 70 — The hardened boot block, placed: hold closes, setup does not, and the instrument's own resolution is the finding

`docs/69-boot-hardening.md` section 15 opens its list of what to do next
with the item this document is the answer to:

> **Place and route it.** `docs/68` section 9.3 measured hold at the
> fast corner falling to **+0.0715 ns** — the smallest margin in the
> design — and warned the next block near the clock tree to look at it.
> This work adds 51 flip-flops and 330 cells to exactly that block and
> **has not been placed**. […] this is the cheapest remaining thing and
> it is the only one that could invalidate a shipped number.

**It did invalidate a shipped number, and not the one it was looking
for.** Hold at the fast corner does not fall: it closes at all three
corners in both runs and it is **better** with the protected block in
the design, by +0.0104 ns. What this document found instead is that
**+0.0104 ns and `docs/68`'s −0.0297 ns are both below this flow's
own resolution**, because a control pair that changes nothing a
designer would call a change moves the same number by **0.0198 ns** —
and moves setup by **0.5031 ns**, which is larger than the floor
`docs/44` section 5.2 measured for synthesis and which nobody had ever
measured after layout.

And the setup number did move, far outside that: **−4.3009 ns at
`nom_slow_1p08V_125C` against the baseline placed beside it**, on a
design that already does not close, with the protected block on
**neither** the setup nor the hold critical path. `docs/62` is the
model for what follows: it is stated, it is not softened, and section 6
says what would fix it.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged, with the
derivation stated; **[assumption]** = chosen, and named so it can be
argued with; **[planned]** = an intention with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by blob hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was modified,
and `hw/tb/Makefile.fi` was not invoked.
`hw/openlane/checker_audit.py` and `hw/openlane/signoff_report.py` are
**read and run** and never written; `hw/rtl/tmr_voter.v`,
`pilot_top.v`, `lif_core.v`, `aer_fifo.v`, `scrub.v`, `secded_enc.v`
and `secded_dec.v` are **read in place** by the flow, exactly as
`docs/61` section 16 and `docs/69` section 13 record.

**And no RTL, flow script, test or configuration file was modified
either.** This document sets no parameter that did not already exist,
writes no RTL and adds no test. `SOC_BOOT_HARDEN` is `docs/69`'s knob on
`hw/soc/flow/syn_soc_top.sh`; `PNR_STATE` is `docs/68`'s knob on
`hw/soc/flow/pnr_soc_top.sh`; `config-ecc.json` is `docs/67`'s
floorplan, unchanged and not regenerated. What changed on disk is this
document, one index row, and the three dated in-place notes section 12
names; everything else this session produced is a gitignored run
directory. Section 13.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Does hold still close?** | **Yes, at all three corners, in both runs, with `Checker.HoldViolations` bound to all three and reporting `all 0`.** Fast corner **+0.0621 ns** with the protected block against **+0.0517 ns** without it — the protected design is the **better** of the two **[fact]**. `docs/68`'s worry was well placed and the answer to it is no. Section 5 |
| **Is that +0.0104 ns real?** | **No, and neither is `docs/68`'s −0.0297 ns.** A control pair — the same design, the same die, the same configuration, two netlists differing by one combinational refactor inside one 1 kGE block at an identical 5,822 flip-flops — moves fast-corner hold by **0.0198 ns** and slow-corner hold by **0.0707 ns [fact]**. **Both documents' hold deltas are inside that.** Section 5.3 |
| **What does it cost on the die?** | **Nothing measurable, and the die does not grow by one database unit.** Placed standard-cell area goes **down** 8,703 um2 (−0.98 %) with 51 more flip-flops in it, because the flow spent **10,964 um2 fewer timing-repair buffers [fact]**. The control pair moves the same quantity by 12,962 um2, so the sign is not interpretable. **The number to quote is still `docs/69`'s block-level +5,255.9010 um2**, reproduced here. Sections 4 and 5.3 |
| **Then what did move?** | **Setup, by −4.3009 ns and −11,041 ns of TNS**, on 253 more violating endpoints **[fact]**. That is **8.6 times** the control pair's 0.5031 ns, so unlike everything else in this document it is outside the instrument. **It is a regression and it is reported as one.** Section 6 |
| **Is the boot block on the path?** | **No, and not on any violating path at all.** `violator_census.py` resolves every violating endpoint in both runs and **`u_boot` appears zero times in either** **[fact]**. The binding path is `raddr_b_i` — the register file's read address, `docs/43` section 7.4's prediction, measured for the sixth time. The worst hold path in both runs ends at a boot **ROM macro** pin and starts nowhere near the block. Sections 5.2 and 6.1 |
| **So what is the mechanism?** | **The timing resizer did a fifth of the setup repair.** 519 setup repair buffers in the baseline against **102** in the protected run **[fact]**, and the divergence is localised: post-CTS the two runs are **0.0922 ns** apart, after global routing and post-GRT repair they are **4.0739 ns** apart. Section 6.2 |
| **Is DRT-0349 unchanged?** | **Yes, exactly.** Ten `[WARNING DRT-0349]` lines over seven layer names — `Cont`, `Via1`×2, `Via2`, `Via3`, `Via4`, `TopVia1`×2, `TopVia2`×2 — **layer for layer and count for count in both runs**, and the same ten as `s67ecc`, `s68base` and `s68boot` **[fact]**. It is the PDK's. Section 7 |
| **Did the checkers keep watching?** | **17 of 19, the same seventeen and the same two, in both runs**, recomputed from the installed LibreLane's own step classes against each run's own `resolved.json`; `checker_audit.py` ~~exits 0~~ exits 1 on both (corrected 2026-09-05 by `docs/71-layout-reproducibility.md` section 9). The four corner checkers each examined **three corners**. Section 8 |
| **Did both source-list guards fire and pass?** | **Both pass, and both were shown to be live rather than assumed to be.** `soc_boot` is one of the **13** modules the flow-list guard checks, and the check is live on all four flows; the fifth-list elaboration fails with `Module \soc_boot referenced in module \soc_top in cell \u_boot is not part of the design` when `soc_boot.v` is withheld. Section 9 |
| **Did the instrument reproduce before it moved?** | **Yes, seven ways, and two of them are byte-identical netlists.** Section 2 |
| **May a frequency be published?** | **No.** `docs/53` section 9.2's three grounds and `docs/05` section 4 rule 5 bind, none of the three has moved, and this run is **further** from the constraint than any before it. Slack against **20 ns** is what this document reports. Section 6.4 |

> **THE ONE-SENTENCE RESULT.** The 51 flip-flops `docs/69` added to the
> boot block cost **no die area, no hold margin and no routing
> quality** — and the layout they landed in reports **4.30 ns less
> setup slack** than the layout beside it, for reasons that are the
> flow's timing repair and not the block, on a design that did not
> close either way.

---

## 2. Reproducing every instrument before moving it

`docs/44` section 5.2 set the rule and `docs/45` section 4, `docs/47`
section 3, `docs/48` section 2, `docs/61` section 2, `docs/62` section
2 and `docs/69` section 2 all follow it. Everything below was measured
in this session.

| What | Published | Measured here |
|---|---|---|
| `soc_boot`, `HARDEN = 1` | `docs/69` 7: **634 cells, 143 flops, 12,495.8862 um2** | **634 / 143 / 12,495.8862** **[fact]** |
| `soc_boot`, `HARDEN = 0` | `docs/69` 7: **304 / 92 / 7,239.9852** | **304 / 92 / 7,239.9852** **[fact]** |
| whole SoC, `ROM_HARDEN = 0`, `SOC_BOOT_HARDEN = 0` | `docs/69` 7.4: **45,132 / 5,822 / 680,606.8038** | **45,132 / 5,822 / 680,606.8038**, and the netlist is **byte-identical** to `docs/69`'s, `md5 aaf14e6d…` **[fact]** |
| whole SoC, `ROM_HARDEN = 0`, protected | `docs/69` 7.4: **45,546 / 5,873 / 685,153.2744** | **45,546 / 5,873 / 685,153.2744**, netlist **byte-identical**, `md5 a8d5ef81…` **[fact]** |
| `docs/68`'s two layouts, on disk | 9.3: **880,499 / 897,986 um2 placed, −4.4159 / −4.3045 setup, +0.1012 / +0.0715 hold, 0 / 0 DRC** | every figure, to the last digit, out of `runs/{s68base,s68boot}/final/metrics.json` **[fact]** |
| `docs/68`'s step timers | 9.3: **3 h 01 m 37 s / 2 h 56 m 23 s**, detailed routing **1 h 08 m 42 s / 1 h 02 m 53 s** | **3 h 01 m 37 s / 2 h 56 m 23 s**, **1 h 08 m 42.06 s / 1 h 02 m 52.90 s** **[fact]** |
| the Python suite | `docs/69` 14: **451** | **451 passed** with this document absent; **452 passed** with it present **[fact]** |

**[fact for every row]**

**The suite gains one test and the reason is worth one line.**
`sw/tests/test_doc_links.py` **discovers** the corpus rather than
listing it — `docs/00-index.md` section 5's own note says a document
added tomorrow is in scope tomorrow with no edit to that file — so it
parameterises one check per source document and **adding this document
adds one test**. 451 is the count `docs/69` reports and the count
measured here before this file existed; 452 is the count afterwards,
and the difference is this file being checked rather than a check being
added. Both were run to completion with 0 failures.

**The two netlists being byte-identical to `docs/69`'s is the strongest
control available here**, and it is stronger than `docs/68` had: it
means the netlist this document places is not *a* netlist of that
design, it is *the* netlist that document measured, and every area
number in `docs/69` section 7.4 is therefore a number about this
layout's input.

**It also proves the two syntheses did not race.** They were run
concurrently and `hw/soc/flow/ibex_sources.sh` regenerates one shared
file, `hw/soc/genp/ibex_top.v`, in both. Two byte-identical netlists
against a third party's published hashes is the evidence that the
shared write was harmless; it was not assumed.

---

## 3. What was run, and the control

### 3.1 Two layouts, one configuration, one difference

`docs/68` section 15's recipe, on `docs/67`'s floorplan, with
`docs/68`'s `PNR_STATE` so that two concurrent runs cannot race on one
state file:

```
SOC_MEM=sram SOC_ROM_HARDEN=0 SOC_BOOT_HARDEN=0 \
    hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s70-rom0-syn-h0
SOC_MEM=sram SOC_ROM_HARDEN=0 \
    hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s70-rom0-syn

SYN_NETLIST=$PWD/hw/soc/out/s70-rom0-syn-h0/soc_top.netlist.v \
PNR_CONFIG=$PWD/hw/soc/pnr/config-ecc.json \
PNR_STATE=$PWD/hw/soc/pnr/state/s70base.state.json \
hw/soc/flow/pnr_soc_top.sh s70base --overwrite -F Yosys.JsonHeader \
    -S Yosys.Synthesis -S Checker.YosysUnmappedCells \
    -S Checker.YosysSynthChecks -S Checker.NetlistAssignStatements \
    -i $PWD/hw/soc/pnr/state/s70base.state.json
```

and the same three lines with `s70boot` and the protected netlist.
LibreLane v3.0.5, OpenROAD `26Q1-2938-g0e2d771c5e`, `ihp-sg13g2` at
`c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c`, rootless, 61 Verilog files,
three corners, extracted parasitics, 5 % derate, 20 ns **[fact]**.

**`config-ecc.json` is `docs/67`'s, unchanged and not regenerated.**
The die, the core box, the six macro placements, the density target and
the four checker bindings are that document's, and the assertion is not
prose:

```
keys differing between the two runs' resolved.json: []
```

**[fact, a `json` diff of `runs/s70base/resolved.json` against
`runs/s70boot/resolved.json`]** — **not one key differs, `VERILOG_FILES`
included**, because both runs are handed a netlist and LibreLane's own
synthesis is skipped. **A difference between these two runs is a
difference of netlist and of nothing else.**

### 3.2 The baseline is `SOC_BOOT_HARDEN = 0` at HEAD, and that matters

`docs/68`'s baseline was a `git worktree` at `ed51de0`, a design with
**no boot block at all**. This document's baseline is the same tree,
the same commit and the same command with one parameter flipped, which
is a tighter control and is what `docs/69` section 7.4 added
`SOC_BOOT_HARDEN` for. `sw/tests/test_soc_synthesis_guards.py::
test_boot_harden_zero_is_exactly_the_block_docs_68_shipped` is the
check that `HARDEN = 0` is the block `docs/68` shipped — the same 92
flip-flops, the report unbanked, no replica — and it passes.

**It is not, however, the same netlist `docs/68` placed**, and section
5.3 is what that turned out to be worth.

### 3.3 The interruption, and the resume

Both runs were interrupted by this session's own process management
partway through `OpenROAD.DetailedRouting` and were **resumed from
`37-openroad-stamidpnr-3/state_out.json`** as `s70base2` and
`s70boot2` — `docs/61` section 17's resume form, which `docs/67`
section 14 used for the same reason. **Both were resumed identically,
from the same step, at the same time, into concurrent runs**, so the
comparison this document is about is unaffected: the interruption is
symmetric.

Three consequences, stated rather than buried:

- **Each configuration is one flow in two directories.** `s70base`
  holds steps 1–37 and `s70base2` steps 38–62 renumbered from 01;
  `final/metrics.json` in the second is the whole flow's, because the
  state carries forward.
- **NO WALL-CLOCK FIGURE HERE IS A WALL-CLOCK FIGURE**, `docs/67`
  section 14's rule, and for a second reason on top of its own: this
  machine carried a process from an unrelated project throughout, the
  two layouts ran concurrently with each other, and the Python suite
  ran across part of them. What is quoted is the flow's own per-step
  `runtime.txt`. Section 12.
- **Whether this flow is bit-reproducible run-to-run has not been
  tested**, here or anywhere in this repository. Section 11.

---

## 4. Measured area

### 4.1 Pre-layout, reproduced rather than quoted

| configuration | cells | flops | area, um2 |
|---|---:|---:|---:|
| `ROM_HARDEN = 0`, `SOC_BOOT_HARDEN = 0` | 45,132 | 5,822 | 680,606.8038 |
| **protected**, `ROM_HARDEN = 0` | 45,546 | 5,873 | **685,153.2744** |
| difference | **+414** | **+51** | **+4,546.4706, +0.668 %** |

**[fact, `SOC_MEM=sram hw/soc/flow/syn_soc_top.sh 20`, two runs; both
netlists byte-identical to `docs/69`'s]**

`docs/69` section 7.4's reading stands unchanged: the flip-flop delta is
**+51, the block's own count exactly**, the two whole-SoC area deltas
bracket the block's own 5,255.9010 um2 rather than agreeing with it,
and the block's own number is the one to use.

### 4.2 On the die, where it goes the other way

| | baseline (`HARDEN = 0`) | protected | difference |
|---|---:|---:|---:|
| die area, um2 | 4,786,290 | 4,786,290 | **0** |
| die bounding box, um | 2306.4 x 2075.22 | 2306.4 x 2075.22 | **identical** |
| core area, um2 | 4,338,910 | 4,338,910 | 0 |
| macros / macro area, um2 | 6 / 2,246,900 | 6 / 2,246,900 | 0 / 0 |
| **placed standard-cell area, um2** | 885,024 | **876,321** | **−8,703, −0.983 %** |
| cells, excluding fill | 60,747 | 60,868 | +121 |
| fill cells, um2 | 1,046,770 | 1,055,470 | +8,700 |
| **sequential cells** | 5,822 | **5,873** | **+51** |
| sequential-cell area, um2 | 285,231 | 287,715 | +2,484 |
| **timing-repair buffers** | 12,030 / 159,656 um2 | **11,530 / 148,692 um2** | **−500 / −10,964** |
| of which setup buffers | **519** | **102** | **−417** |
| of which hold buffers | 4 | 4 | 0 |
| clock buffers / inverters | 733 / 257 | 745 / 280 | +12 / +23 |
| clock-buffer area, um2 | 19,989.2 | 20,294.1 | +304.9 |
| utilisation | 72.182 % | 71.982 % | −0.200 pp |
| routed wirelength, um | 4,286,499 | 4,248,250 | −38,249 |
| longest net, um | 2,472.92 | 2,379.42 | −93.50 |
| routed vias | 449,743 | 451,091 | +1,348 |
| **detailed-routing DRC errors** | **0** | **0** | — |
| disconnected pins / PDN violations | 0 / 0 | 0 / 0 | — |
| antenna-violating nets / pins | 0 / 0 | 1 / 1 | +1 / +1 |
| antenna diodes | 515 | 674 | +159 |
| Magic illegal overlaps | 0 | 0 | — |

**[fact, `runs/{s70base2,s70boot2}/final/metrics.json` via
`hw/openlane/signoff_report.py`]**

**The 51 sequential cells are the block's 51 flip-flops, exactly**, and
the census resolves them by name rather than by subtraction:

| | baseline | protected |
|---|---|---|
| flip-flops whose `Q` net is a `\u_boot.*` name | **92** | **120** |
| `u_boot.g_prot_tmr.u_prot_{a,b,c}.bits` | — | 23 / 11 / 12 |
| `u_boot.g_prot_plain.plain` | 4 | — |
| `brpt_q` / `epoch_q` | 32 / 32 | 32 / 32 |
| placement bounding box, um | 1824.5–2233.4 x 563.2–914.8 | 1896.0–2233.4 x 415.8–812.7 |

**[fact, the two runs' own `final/nl/soc_top.nl.v` and
`final/def/soc_top.def`]**

The baseline's **92 is the whole block, every field named**, which is
`docs/68` section 9.1's census surviving into a flattened, placed
netlist. The protected run's **120 is a lower bound and not a
disagreement**: the block is 143 flip-flops, and 23 of them — one
replica's width — drive a net that did not keep a `u_boot.` public name
through `flatten` + `opt_clean`. **The checkable statement is the
whole-design one, and it is exact: +51.**

**And the die cost is negative, which is not a saving.** The block adds
2,484 um2 of sequential cells and the flow removes 10,964 um2 of
timing-repair buffers, so placed standard-cell area falls by 8,703. A
reader who quoted that as "the hardening pays for itself" would be
quoting the resizer's budget, not the block — section 6.2 is what that
budget did — and section 5.3 is the measurement that says a movement of
this size in this quantity is not resolvable by this flow at all.

---

## 5. Hold, which is the number this document was sent to look at

### 5.1 It closes, at three corners, in both runs

| corner | baseline | protected | difference |
|---|---:|---:|---:|
| `nom_fast_1p32V_m40C` | **+0.0517** | **+0.0621** | **+0.0104** |
| `nom_typ_1p20V_25C` | +0.2591 | +0.2735 | +0.0145 |
| `nom_slow_1p08V_125C` | +0.5140 | +0.5897 | +0.0757 |
| violating endpoints, all three | 0 | 0 | — |
| hold TNS, all three | 0 | 0 | — |

**[fact, `final/metrics.json` and
`12-openroad-stapostpnr/summary.rpt` of each run]**

**Hold does not appear in either run's deferred-error list.** Both runs
exit non-zero naming setup, max slew and max cap at their corners, and
`Checker.HoldViolations` — bound to `["*"]` since `docs/47` section 7.1
— reports `corners measured 3, all 0` in both **[fact,
`checker_audit.py`]**. That is the shape `docs/61` section 10 insisted
on: a criterion that passes is exactly where a checker that stopped
looking would hide, and this one was asked whether it could still fail
before it was believed.

### 5.2 The worst hold path is not in this block

| | baseline | protected |
|---|---|---|
| endpoint | `u_rom.g_rom_1024x32.u_b1` | `u_rom.g_rom_1024x32.u_b1` |
| launch flop resolves to | `u_ibex.…prefetch_buffer_i.stored_addr_q[8]` | `u_bus.cnt_i[0]` |

**[fact, `nom_fast_1p32V_m40C/min.rpt` of each run, with the launch
cell resolved against that run's own netlist]**

Both worst hold paths **capture at a boot ROM macro's input pin** and
neither launches inside `soc_boot`. The block that `docs/68` warned
would land near the clock tree did land near it — its 120 resolvable
flip-flops sit in a 337 x 397 um box in the same corner of the die as
before — and it is on neither end of the tightest hold check.

### 5.3 And the movement is not resolvable, which is this document's finding

**The control pair.** `s70base2` and `docs/68`'s `s68boot` are two
layouts of **the same design**: same die, same `config-ecc.json`, same
flow, same tool versions, and two netlists at an identical **5,822
flip-flops** whose only difference is `docs/69` section 7.1's
refactor — the boot block's next state written as one combinational
function instead of three sequential always-blocks, worth **one cell
and 10.9242 um2** at the block level. Nothing a designer would call a
change.

| | `s68boot` | `s70base2` | difference |
|---|---:|---:|---:|
| sequential cells | 5,822 | 5,822 | **0** |
| **hold ws, fast, ns** | +0.0715 | +0.0517 | **−0.0198** |
| hold ws, typ, ns | +0.2618 | +0.2591 | −0.0028 |
| hold ws, slow, ns | +0.5847 | +0.5140 | −0.0707 |
| **setup ws, slow, ns** | −4.3045 | −4.8076 | **−0.5031** |
| setup TNS, slow, ns | −5,275.81 | −8,948.31 | −3,672.50 |
| setup violating endpoints | 3,003 | 3,108 | +105 |
| placed standard-cell area, um2 | 897,986 | 885,024 | **−12,962** |
| timing-repair buffers, um2 | 165,954 | 159,656 | −6,298 |
| routed wirelength, um | 4,505,318 | 4,286,499 | −218,819 |
| max slew violations, s/t/f | 28 / 10 / 8 | 60 / 30 / 22 | +32 / +20 / +14 |
| detailed-routing DRC | 0 | 0 | — |

**[fact for every row, the two runs' `final/metrics.json`]**

Three readings, and the first supersedes a shipped conclusion.

> **`docs/68` section 9.3's hold delta is inside the instrument.** That
> document measured fast-corner hold falling from +0.1012 to +0.0715 ns
> — **−0.0297** — and read it as *"a 29 % cut in a margin that was
> already the smallest in the design"*. **A pair that changes nothing
> moves the same number by 0.0198 ns, which is 67 % of it**, and this
> document's own +0.0104 ns is half of that again. The direction
> `docs/68` reported may well be right; **the magnitude is not a
> measurement**, and the sentence that followed it — *"the next block
> that lands near the clock tree should look at it before assuming
> there is room"* — is good advice that its own number did not support.

**Second: nobody had measured a post-layout floor before.** `docs/44`
section 5.2's **0.4 ns** is a *synthesis* floor for *whole-core setup*,
established from two controlled pairs on the Ibex core; it has been
quoted after layout by `docs/61`, `docs/62` and `docs/67` because it
was the only floor on the shelf. **After layout, on this design, the
same kind of control gives 0.5031 ns for setup** — larger, and in the
same neighbourhood — **and 0.0198 ns for fast-corner hold**, which is a
number this repository did not have. Both are **[estimate]**s from a
single pair, exactly as `docs/44`'s was, and neither is a distribution.

**Third: the area floor is 12,962 um2**, which is 2.5 times the
5,255.9010 um2 the protected block costs standalone. That is
`docs/68` section 9.2's noise-floor finding — *"this flow's
whole-design area measurement has a noise floor larger than a 1 kGE
block"* — reproduced **after layout** rather than before it, and it is
why section 4.2's −8,703 um2 is reported and not interpreted.

**What the control does not establish.** It is one pair. It cannot
separate "the mapper chose differently" from "the placer chose
differently", because the netlist changed and everything downstream of
it changed at once — the same limitation `docs/44` section 5.2 states
for its own two pairs. And `s70base2` is a resumed run where `s68boot`
was not; the resume restores the step's own `state_out.json`, so the
comparison should be of netlists, but **that is an argument and not a
measurement**.

*Measured 2026-09-05 by `docs/71-layout-reproducibility.md` sections 5 to 7.
`s70boot2`'s netlist laid out again, uninterrupted, is byte-identical to
`s70boot2` in `final/metrics.json` and in every design view, so this
control pair measured **netlist sensitivity** and not tool noise; its
0.5031 ns, 0.0198 ns and 12,962 um2 stand under that name. And the
resume form loses nothing: the uninterrupted run and this resumed one
agree at every step from 38 on, so the sentence above is a measurement
now.*

---

## 6. Setup, which is the regression

### 6.1 The numbers, and they are not close

| corner | baseline | protected | difference |
|---|---:|---:|---:|
| `nom_slow_1p08V_125C`, ws | **−4.8076** | **−9.1085** | **−4.3009** |
| `nom_slow_1p08V_125C`, TNS | −8,948.31 | **−19,989.82** | −11,041.51 |
| `nom_slow_1p08V_125C`, violating endpoints | 3,108 | **3,361** | +253 |
| `nom_typ_1p20V_25C`, ws | +4.1645 | +1.7820 | −2.3825 |
| `nom_fast_1p32V_m40C`, ws | +9.4537 | +8.0527 | −1.4011 |
| max slew violations, s/t/f | 60 / 30 / 22 | 47 / 2 / 1 | −13 / −28 / −21 |
| max cap violations, s/t/f | 24 / 24 / 25 | 16 / 16 / 16 | −8 / −8 / −9 |
| clock skew, worst setup, ns | 0.9506 | 0.9782 | +0.0276 |

**[fact, both runs' `final/metrics.json` and
`12-openroad-stapostpnr/summary.rpt`]**

**−4.3009 ns is 8.6 times section 5.3's 0.5031 ns and 10.8 times
`docs/44`'s 0.4 ns.** `docs/62` called −1.0109 ns a regression at 2.5
times that floor and said so in its title; this is four times larger
than that one. **It is a regression.** It is not softened, and it is
not reported as placement noise, because the control that would let it
be reported as noise was run and says it is not.

**And the design does not close either way.** `docs/47` section 8.2's
result stands: this design has never met 20 ns, its binding path has
been the register file's read address since `docs/45`, and both columns
above are numbers about how far short it falls. **No frequency is
derived from either**, section 6.4.

### 6.2 Where it happens, and what did it

The stage table, both runs, worst setup at `nom_slow_1p08V_125C`:

| stage | baseline | protected | difference |
|---|---:|---:|---:|
| `23-openroad-stamidpnr`, post-global-placement | −151.3650 | −157.3530 | −5.9880 |
| `28-openroad-stamidpnr-1`, post-CTS | **−12.4812** | **−12.5734** | **−0.0922** |
| `30-openroad-stamidpnr-2`, post-CTS repair | −2.2548 | −2.5962 | −0.3414 |
| `37-openroad-stamidpnr-3`, post-GRT repair | **−4.1113** | **−8.1852** | **−4.0739** |
| sign-off, routed and extracted | −4.8076 | −9.1085 | −4.3009 |

**[fact, each step's own `or_metrics_out.json`]**

**Post-CTS the two designs are 0.0922 ns apart — inside every floor
this repository has** — and after global routing and the post-GRT
repair they are 4.0739 ns apart. **The whole of the regression appears
between step 30 and step 37**, and detailed routing then adds 0.23 ns
to it.

**The mechanism is in the buffer census.** The post-GRT resizer
inserted **519 setup repair buffers in the baseline and 102 in the
protected run** — a fifth — and 500 fewer timing-repair buffers
overall, 10,964 um2 of them **[fact]**. It is the same shape `docs/48`
section 7 measured for `MAX_CAPACITANCE_CONSTRAINT` and `docs/62`
section 7.1 for `SYNPRE`, in the opposite direction: there the resizer
did **too much** work on the wrong nets and left `repair_timing` no
room; here it did far less of it and the paths it did not repair are
the ones that report.

**Why it did less is not established by this document.** The two
plausible readings — that the design 0.67 % larger left the resizer a
different set of legal placements, or that `repair_design`'s and
`repair_timing`'s own iteration budget terminated differently — are
distinguishable by instrumenting the step and were not. Section 15 item
1.

*Established 2026-09-06 by `docs/72-post-grt-resizer.md`: it is the
first reading, sharpened, and not the second. No repair budget bound;
both loops ended on OpenROAD's own no-progress rule, the hardened one
after 20 of 3,365 endpoints — the CLINT's read-data and time-base
registers — each tried for 51 passes and restored. It started 2.477 ns
worse on global-route parasitics because a single-drive `nor4_1` was
left driving a 180 fF net across the upper ROM macro on the binding
path, and it recovered 2.092 ns less. `docs/72` sections 6 to 8.*

### 6.3 The block is on none of it

`hw/soc/pnr/violator_census.py`, on each run's own netlist:

**Baseline, 3,108 violating endpoints, worst −4.8076, sum −8,948.31:**

| launch point | count | worst | TNS |
|---|---:|---:|---:|
| `…register_file_i.raddr_b_i[3]` | 1,807 | −4.8076 | −5,513.32 |
| `u_ram.g_ram_2048x64_ecc.u_b0/A_DOUT[24]` | 849 | −3.3169 | −2,158.54 |
| `u_ram.g_ram_2048x64_ecc.u_b0/A_DOUT[18]` | 290 | −4.5328 | −986.46 |
| `…raddr_a_i[0]` | 111 | −2.8177 | −252.92 |
| `u_npu.u_node0.u_lif.ev_axon_r[1]` | 45 | −1.6096 | −33.05 |
| `u_clint.g_mtime_secded.u_mtime_dec.code_in[60]` | 6 | −1.2837 | −4.02 |

**Protected, 3,361 endpoints, worst −9.1085, sum −19,989.82:**

| launch point | count | worst | TNS |
|---|---:|---:|---:|
| `…raddr_b_i[0]` | 1,725 | −9.0480 | −11,650.25 |
| `u_ram.g_ram_2048x64_ecc.u_b0/A_DOUT[3]` | 1,018 | −6.8564 | −5,784.61 |
| `…raddr_b_i[1]` | 392 | −9.1085 | −2,270.06 |
| `u_npu.u_node0.u_lif.ev_axon_r[1]` | 218 | −4.4431 | −280.95 |
| `u_clint.g_mtime_secded.u_mtime_dec.code_in[47]` | 7 | −0.9355 | −3.56 |

**[fact, `violator_census.py --top 6` on each run]**

> **`u_boot` appears zero times in either census, and zero times in
> either corner's `violator_list.rpt`** **[fact, `grep`]**. Not as a
> launch point, not as a capture, not once in 6,469 violating endpoints
> across the two runs.

**The binding path is `raddr_b_i`, for the sixth time.** `docs/43`
section 7.4 predicted it, `docs/45` measured it twice, `docs/61`,
`docs/67` and `docs/62` each measured it again, and it is here in both
columns. The two populations `docs/67` section 5.3 identified — the
macro read return and the register file's two codecs in series — are
both here too, and the protected run's macro-launch group is
**1,018 endpoints at −6.8564** against the baseline's 1,139 across two
bits, worst −4.5328.
That is `docs/67`'s finding getting worse, on a change that does not
touch the memory.

### 6.4 No frequency

`docs/53` section 9.2 refused a frequency on three grounds — that it is
the number a layout reached and not a requirement; that the derived
requirement in that document's section 6 is not a frequency at all; and
that `docs/05` section 4 rule 5 binds any externally published figure
to a measurement or an explicit target. **None of the three has
moved**, and this document is the furthest from the constraint any run
in this repository has been: **−9.1085 ns of slack against 20 ns**.
Slack against 20 ns is what is reported here, in section 6.1, and
nothing in this document may be converted into a clock rate.

---

## 7. The router check that did not run, re-checked rather than inherited

`docs/67` section 11 found that the detailed router emits

```
[WARNING DRT-0349] LEF58_ENCLOSURE with no CUTCLASS is not supported.
Skipping for layer <L>
```

and that the lines are a property of the `ihp-sg13g2` technology LEF
rather than of any design. `docs/68` section 9.3 re-checked it on its
own pair. Re-checked again here, on both runs:

| | baseline | protected |
|---|---:|---:|
| total `DRT-0349` lines | **10** | **10** |
| distinct layers | 7 | 7 |
| `Cont` / `Via1` / `Via2` / `Via3` / `Via4` | 1 / 2 / 1 / 1 / 1 | 1 / 2 / 1 / 1 / 1 |
| `TopVia1` / `TopVia2` | 2 / 2 | 2 / 2 |

**[fact, `grep DRT-0349` over
`01-openroad-detailedrouting/openroad-detailedrouting.log` in both]**

**Identical, layer for layer and count for count** — and identical to
`s67ecc`, `s68base` and `s68boot`, which were re-read for this
document and give the same ten **[fact]**. So it is the PDK's, it is
not this change's, and **`0 detailed-routing DRC errors` in section 4.2
means zero errors among the rules the router did check**, with cut
enclosure on those seven layers not among them, in both columns.

**One correction falls out of counting it.** `docs/67` section 11 says
the warning is emitted *"seven times per run"* and that via enclosure
*"on nine layers"* was not checked. **Neither is right: it is ten lines
over seven layer names**, which is what that section's own enumeration
adds up to and what `docs/68` section 9.3 already stated correctly.
Section 12.

---

## 8. The checkers, re-audited

`hw/openlane/checker_audit.py`, which recomputes from the installed
LibreLane's own step classes and each run's own `resolved.json` whether
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

**[fact, identical output for `runs/s70base2` and `runs/s70boot2`;
both ~~exit 0~~ exit 1]**

*Corrected 2026-09-05 by `docs/71-layout-reproducibility.md` section 9:
`checker_audit.py` exits **1** on both runs, as its own docstring says it
must whenever any in-flow checker is NO-GATE; with `LintWarnings` and
`WireLength` abstaining by policy it has exited 1 on every run since
`docs/47`. The 17-of-19 count stands.*

**Seventeen of nineteen, the same seventeen and the same two**, as
`docs/47` 7.3, `docs/48` 9, `docs/49` 10, `docs/50` 9, `docs/61` 10,
`docs/62` 10, `docs/67` 5.3 and `docs/68` 9.3. The two that do not gate
are `Checker.WireLength` — `WIRE_LENGTH_THRESHOLD` unset in both PDKs —
and `Checker.LintWarnings`, off by an explicitly named boolean, which
is a policy and not an oversight. Neither is repaired here.

**The derate is audited where it can be audited.** `docs/31` sections
3.2 and 10.3: `resolved.json` records the integer `5` whether or not
the derate applied, so the observable is the flow's own log line, and
both runs print

```
[INFO] Setting timing derate to: 5.0%
```

**[fact]** — `5.0%` and not `5%`, which is `docs/28` section 4.4's
distinction between a derate applied and a derate logged.

**And the flow exits non-zero in both, naming every failing criterion:**
setup at `nom_slow_1p08V_125C`, max slew at all three, max cap at all
three — **and hold in neither list** **[fact, both flow logs]**.
`design__violations` reads **0** in both `final/metrics.json` anyway,
which is `docs/23` section 3.2's non-aggregating aggregate recurring
yet again, and the only reason these runs are not
reported clean is that four checkers were bound to `["*"]` before they
started.

**The two metrics nothing judges**, read out here rather than left in a
file, `docs/47` section 8.6's rule: `design__max_fanout_violation__count`
is **530** in the baseline and **565** in the protected run, against no
checker step at all in the Classic flow; `timing__unannotated_net__count`
is **441** and **479** **[fact]**.

---

## 9. The two source-list guards, fired and passed

`docs/61` section 3.3 added the first because `docs/51` put `u_npu`
into `soc_top.v` and updated one of four source lists, and six
documents' area, timing and power numbers were signed off from a
netlist missing half the design. `docs/65` section 10 added the second
after finding a fifth list. `docs/66` section 10 item 5 recorded both
firing on the QSPI controller. Both are re-run here with the protected
block in the build:

```
sw/tests/test_soc_synthesis_guards.py::
    test_every_flow_that_builds_soc_top_reads_every_module_it_instantiates  PASSED
sw/tests/test_soc_synthesis_guards.py::
    test_the_whole_soc_elaborates_as_one_design                             PASSED
```

**[fact; and 452 of 452 in the whole suite, section 2]**

**Passing is not the evidence; being live is.** Both were shown to fire
on this block specifically, in a scratch directory, without touching
the tree:

- The flow-list guard's own logic, replicated against the same four
  scripts, checks **13** of `soc_top.v`'s children —
  `soc_apb_bridge`, `soc_apb_pnp`, **`soc_boot`**, `soc_bus`,
  `soc_busstat`, `soc_clint`, `soc_gpio`, `soc_gptimer`, `soc_npu`,
  `soc_pnp`, `soc_qspi`, `soc_scrub`, `soc_uart` — plus the four
  transitive ones through `soc_npu.v`. With `soc_boot` removed from a
  flow's text the assertion fires, and it fires on **all four**
  flows **[fact]**.
- The fifth-list elaboration, run with `soc_boot.v` withheld from the
  list and everything else identical, fails with

  ```
  ERROR: Module `\soc_boot' referenced in module `\soc_top' in cell
  `\u_boot' is not part of the design.
  ```

  **[fact]** — the exact message `docs/66` section 10 item 5 records
  for `soc_qspi`.

**And the protected variant is what the layout contains, checked in the
placed netlist rather than in the RTL.** The baseline's netlist carries
`u_boot.g_prot_plain.plain`; the protected one carries
`u_boot.g_prot_tmr.u_prot_a`, `u_prot_b` and `u_prot_c` — **three
distinct replica banks** — and no `g_prot_plain` **[fact, `grep` over
both `soc_top.netlist.v`]**. That is
`test_the_boot_decision_word_is_three_banks_in_the_netlist`'s property,
verified on the netlist that was actually placed.

---

## 10. Which prior conclusions survive

| Conclusion | Where | Status after this document |
|---|---|---|
| The die does not grow; fill absorbs the block | `docs/67` 5.3, `docs/68` 9.3 | **Survives**, a third time: 0 um2, identical bounding box, fill ±8,700 um2 |
| 0 detailed-routing DRC on this floorplan | `docs/47` 8, `docs/61`, `docs/67`, `docs/68` | **Survives**, both runs |
| Hold closes at all three corners | `docs/67` 5.3, `docs/68` 9.3 | **Survives**, both runs, with the checker bound to three corners |
| 17 of 19 in-flow checkers gate | every physical document since `docs/47` | **Survives**, both runs, `checker_audit.py` ~~exit 0~~ exit 1 (corrected 2026-09-05 by `docs/71-layout-reproducibility.md` section 9) |
| The binding path is the register file's read address | `docs/43` 7.4, `docs/45`, `docs/61`, `docs/62`, `docs/67` | **Survives**, both runs, sixth measurement |
| DRT-0349 is the PDK's and identical across runs | `docs/67` 11, `docs/68` 9.3 | **Survives**, and the count is corrected to ten lines over seven layers |
| The block's cost is +5,255.9010 um2, +51 flops | `docs/69` 7 | **Survives**, reproduced exactly, and it remains the number to quote |
| Whole-design area from this flow has a noise floor larger than a 1 kGE block | `docs/68` 9.2 | **Survives and is extended**: 12,962 um2 *after layout*, section 5.3 |
| **Fast-corner hold fell 29 % when the boot block landed** | `docs/68` 9.3 | **Does NOT survive as a measurement.** The −0.0297 ns is inside a 0.0198 ns control. The warning it motivated is still worth heeding; the number is not evidence. Section 5.3 |
| `docs/69`'s **NO LAYOUT** limitation | `docs/69` 11 | **Closed by this document.** |
| `docs/69` 15 item 1, place and route it | `docs/69` 15 | **Closed.** |
| The 0.4 ns floor is the resolution to use after layout | quoted by `docs/61`, `docs/62`, `docs/67` | **Amended.** It is a *synthesis* floor for whole-core *setup*. After layout the control gives **0.5031 ns setup** and **0.0198 ns fast-corner hold** **[estimate]**. `docs/62`'s −1.0109 ns is 2.0x the post-layout figure rather than 2.5x the synthesis one and its verdict is unchanged; `docs/67`'s −0.6353 ns is 1.26x it, which is outside but thin. |
| `docs/67` section 11's "seven times per run" and "nine layers" | `docs/67` 11 | **Corrected**: ten lines, seven layer names. Section 12. |

---

## 11. What this does NOT cover

Stated at length, in the discipline `docs/47` section 9, `docs/62`
section 13, `docs/67` section 11, `docs/68` section 12 and `docs/69`
section 11 set. Those lists stand unchanged except where this document
names an item; what follows is this document's additions and the two
items it must repeat because they are the largest.

- **THIS IS NOT A PHYSICAL SIGN-OFF. THERE IS NO DRC RESULT, NO LVS
  RESULT AND NO XOR RESULT, AND NOTHING HERE MAY BE READ AS THOUGH
  THERE WERE.** `RUN_MAGIC_DRC`, `RUN_KLAYOUT_DRC`, `RUN_KLAYOUT_XOR`
  and `RUN_LVS` are all **0** in `config-ecc.json` **[fact]**, and the
  reason is a prior measured result and not a schedule: `docs/12`
  sections 7.5 and 8 record a **NO-GO on RM_IHPSG13 for this PDK
  version**, tied to IHP-Open-PDK issue #239, from a run of all three
  decks over one macro in a registered wrapper — **Magic DRC 1,106,478
  errors, KLayout deep-mode DRC 2,316, Netgen LVS 359 with none of 188
  bus pins matching**. `docs/54` then examined those 2,316 in full and
  found the two rules that produce 1,022 of them are an artefact of a
  synthesized layer, that the deep-mode count understates by a factor
  of 53, and that **neither exit from the no-go is free**. Six macros
  sit on this die. **A layout that has not been DRC'd or LVS'd is not
  evidence that it is manufacturable or that it implements the
  netlist.** Everything in this document is about **area and timing**,
  and that is all it is offered as.
- **`Yosys.EQY` is off**, so nothing here proves the placed netlist is
  equivalent to the RTL, and **no gate-level simulation of `soc_top`
  exists**. `docs/47` section 9's two obligations are unchanged. *The second is closed 2026-09-06 by
  `docs/74-core-gate-level-campaign.md`, on this very layout's netlist;
  the first, equivalence, is not.*
- **NO BEHAVIOURAL EVIDENCE WAS ADDED AND NONE WAS NEEDED.** No RTL
  file was modified, so `docs/69`'s campaign, its 572 injections, its
  formal jobs, its cocotb suites and its whole-SoC invariant of
  **220,256 / 415,324 cycles** are the evidence for this design and
  they are not re-derived here. The suite was re-run (452 of 452, section 2)
  as a check that the **tree** did not move, not as a check that the
  design did.
- **THE SETUP REGRESSION'S MECHANISM IS LOCALISED, NOT EXPLAINED.**
  Section 6.2 shows it appears between post-CTS repair and post-GRT
  repair and that the resizer inserted a fifth of the setup buffers.
  **Why** it did is not established, and separating "a larger netlist
  left a different set of legal placements" from "the repair loop
  terminated differently" needs the step instrumented, which was not
  done. *Closed 2026-09-06 by `docs/72-post-grt-resizer.md`: the step was
  instrumented on its own saved state, reproduces to the byte, and the
  mechanism is a different placement of the CLINT read path across the
  ROM macro plus a loop that gives up when the worst endpoints cannot
  be moved — not a budget.*
- **THE CONTROL PAIR IS ONE PAIR.** Section 5.3's 0.5031 ns and
  0.0198 ns are single differences, exactly as `docs/44` section 5.2's
  0.4 ns is, and neither is a distribution. A floor derived from one
  pair can be too small as easily as too large.
- **WHETHER THIS FLOW IS BIT-REPRODUCIBLE RUN TO RUN HAS NEVER BEEN
  TESTED**, here or in any earlier document. Every "noise floor" in
  this repository is a floor over *netlists*, and it silently assumes
  that the same netlist twice gives the same layout. That assumption
  has not been checked, it is cheap to check, and until it is, section
  5.3's numbers are an upper bound on netlist sensitivity and a lower
  bound on nothing. *Closed 2026-09-05 by
  `docs/71-layout-reproducibility.md`: tested, and the same netlist gives a
  byte-identical layout.*
- **ONE FLOORPLAN, ONE DENSITY, ONE CLOCK, ONE MODE.** `config-ecc.json`
  is `docs/67`'s single point; `docs/48` measured two alternatives and
  both were worse, but neither was sized for the design that now
  exists. No DFT, no scan, no multi-mode analysis, and no power number
  is taken from these runs.
- **THE FAST CORNER'S MACRO LIBERTY IS CHARACTERISED AT −55 C** while
  the standard cells around it are at −40 C, `docs/12` section 6.4a,
  because the PDK ships no −40 C macro file. **Every hold result in
  section 5 carries that 15 C mismatch**, and section 5 is the section
  of this document where it matters most.
- **IR DROP IS INDICATIVE ONLY.** `VSRC_LOC_FILES` is unset; only the
  connectivity result is used.
- **THE ANTENNA MOVEMENT IS NOT INTERPRETED.** 0 violating nets became
  1 while the diode count rose by 159. `docs/68` section 9.3 reported
  the same quantity moving the other way for the same reason:
  placement changed for every reason at once.
- **NO WALL-CLOCK FIGURE IS A WALL-CLOCK FIGURE**, section 3.3 and
  section 12.

---

## 12. Corrections to earlier documents

Every one is a dated in-place note in the corrected file, by `docs/64`
section 2's rule; every original sentence stands, struck through only
where a short phrase is wrong. Section 13 names the three files.

- **`docs/68` section 9.3**: *"Hold is still closed at all three
  corners, and it is the number that moved worst: +0.1012 ns to
  +0.0715 ns at the fast corner, a 29 % cut…"* The first clause is
  confirmed and the second is **withdrawn as a measurement**: section
  5.3's control moves the same number by 0.0198 ns with no design
  change at all. The advice that followed it — look before assuming
  there is room — is what this document acted on and is why the control
  exists.
- **`docs/68` section 16 item 1** and **`docs/69` section 15 item 1**,
  *"place and route it"*: **closed**.
- **`docs/69` section 11**, the **NO LAYOUT** bullet: **closed**, and
  replaced by this document's section 11.
- **`docs/67` section 11**: *"The detailed router emits, seven times
  per run…"* and *"via enclosure on nine layers was not among them"*.
  It is **ten lines over seven layer names**, which is what that
  section's own enumeration sums to; `docs/68` section 9.3 stated it
  correctly and four run directories agree. Section 7.
- **`docs/44` section 5.2's 0.4 ns**, as quoted after layout by
  `docs/61` section 9.1, `docs/62` section 1 and `docs/67` section 5.3:
  it is a **synthesis** floor for **whole-core setup** and was never
  measured after layout. Section 5.3 measures the post-layout
  equivalents. **No verdict in those three documents changes**, but the
  margins narrow: `docs/62`'s −1.0109 ns is **2.0x** the post-layout
  setup figure rather than 2.5x the synthesis one, and `docs/67`'s
  −0.6353 ns is **1.26x** it, which is thin enough that it should be
  read as "outside, barely" rather than as comfortably outside.
- **`docs/00-index.md`**: one row, which `sw/tests/test_doc_links.py`
  requires.

---

## 13. Files touched

| file | change |
|---|---|
| `docs/70-boot-hardening-placed.md` | this document |
| `docs/00-index.md` | one row |
| `docs/68-boot-flow.md` | section 9.3, a dated note: the 29 % hold cut is withdrawn as a measurement, the advice that followed it stands |
| `docs/67-memory-protection.md` | section 11, a dated note: seven becomes ten, nine layers becomes seven layer names |
| `docs/44-margin-and-observability.md` | section 5.2, a dated note: the 0.4 ns is a synthesis floor for setup, and the post-layout figures are named |

**Nothing else in the repository is modified.** No RTL, no flow script,
no test, no configuration. `hw/soc/out/s70-*`,
`hw/soc/pnr/runs/s70{base,boot,base2,boot2}/`,
`hw/soc/pnr/state/s70*.state.json` and
`hw/soc/pnr/config.resolved.json` are gitignored build products and are
not checked in, `docs/38` section 11's rule; the durable record of the
two layouts is this document.

**Nothing in `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is
modified and `hw/tb/Makefile.fi` was not invoked. `docs/34`'s freeze is
untouched.**

---

## 14. Reproducing this

```
# 0. the instruments, before anything is claimed to move
V=$HOME/Documents/caravel-lif-crossbar/.venv-flow/bin/python
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/s68base hw/soc/pnr/runs/s68boot
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/s68boot   # 17 of 19
hw/soc/flow/syn_soc.sh soc_boot                            # 634 / 143 / 12495.8862
SOC_CHPARAM="-set HARDEN 0" hw/soc/flow/syn_soc.sh soc_boot  # 304 / 92 / 7239.9852
.venv/bin/python -m pytest sw/tests -q                     # 452 with docs/70

# 1. the two netlists, one parameter apart
SOC_MEM=sram SOC_ROM_HARDEN=0 SOC_BOOT_HARDEN=0 \
    hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s70-rom0-syn-h0
SOC_MEM=sram SOC_ROM_HARDEN=0 \
    hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s70-rom0-syn
md5sum hw/soc/out/s70-rom0-syn{,-h0}/soc_top.netlist.v \
       hw/soc/out/s69-rom0-syn{,-h0}/soc_top.netlist.v    # two pairs, equal

# 2. the two layouts, side by side, each with its own state file
SYN_NETLIST=$PWD/hw/soc/out/s70-rom0-syn-h0/soc_top.netlist.v \
PNR_CONFIG=$PWD/hw/soc/pnr/config-ecc.json \
PNR_STATE=$PWD/hw/soc/pnr/state/s70base.state.json \
hw/soc/flow/pnr_soc_top.sh s70base --overwrite -F Yosys.JsonHeader \
    -S Yosys.Synthesis -S Checker.YosysUnmappedCells \
    -S Checker.YosysSynthChecks -S Checker.NetlistAssignStatements \
    -i $PWD/hw/soc/pnr/state/s70base.state.json
#   ... and the same with s70boot and hw/soc/out/s70-rom0-syn/

# resuming, if interrupted (this session's s70base2 / s70boot2):
SYN_NETLIST=... PNR_CONFIG=... PNR_STATE=... \
hw/soc/flow/pnr_soc_top.sh s70base2 --overwrite \
    -F OpenROAD.DetailedRouting \
    -i $PWD/hw/soc/pnr/runs/s70base/37-openroad-stamidpnr-3/state_out.json

# 3. the configuration difference, asserted rather than described
python3 -c "
import json
a=json.load(open('hw/soc/pnr/runs/s70base/resolved.json'))
b=json.load(open('hw/soc/pnr/runs/s70boot/resolved.json'))
print(sorted(k for k in set(a)|set(b) if a.get(k)!=b.get(k)))"   # []

# 4. the reports
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/s70base2 hw/soc/pnr/runs/s70boot2
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/s70base2   # 17 of 19, exit 1 (docs/71)
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/s70boot2   # 17 of 19, exit 1 (docs/71)
python3 hw/soc/pnr/violator_census.py hw/soc/pnr/runs/s70boot2 --top 6
grep -c u_boot hw/soc/pnr/runs/s70boot2/12-openroad-stapostpnr/*/violator_list.rpt

# 5. the router check that did not run
for t in s67ecc s68base s68boot s70base2 s70boot2; do
  grep -h DRT-0349 hw/soc/pnr/runs/$t/*openroad-detailedrouting/*.log \
    | sed 's/.*layer //' | sort | uniq -c
done                                                   # ten lines, seven layers

# 6. the derate, where it can be audited and NOT in resolved.json
grep -m1 "timing derate" hw/soc/out/s70-pnr-base2.log  # 5.0%

# 7. the guards
.venv/bin/python -m pytest \
  "sw/tests/test_soc_synthesis_guards.py::test_every_flow_that_builds_soc_top_reads_every_module_it_instantiates" \
  "sw/tests/test_soc_synthesis_guards.py::test_the_whole_soc_elaborates_as_one_design" -q
.venv/bin/python -m pytest sw/tests/test_doc_links.py -q
```

Section 9's two firing demonstrations are made in a temporary
directory against copies of the flow texts and the source list, so no
mutation is ever made in the tree — `docs/69` section 14's rule for the
same kind of demonstration.

**The step timers**, which are the only runtimes quoted and which are
not wall-clock:

| | steps 1–37 | the resumed tail | total, 59 timed steps | detailed routing |
|---|---:|---:|---:|---:|
| baseline | 50 m 33.86 s | 1 h 32 m 09.55 s | **2 h 22 m 43.41 s** | **1 h 16 m 06.98 s** |
| protected | 33 m 53.01 s | 1 h 32 m 26.97 s | **2 h 06 m 19.98 s** | **1 h 20 m 23.49 s** |

**[fact, each step's own `runtime.txt`]**

The two **detailed routing** figures are comparable with each other —
the two runs were in that step concurrently — and the two **steps 1–37**
figures are not, because the runs were started 90 seconds apart into
different loads. Neither total is a measure of what either run would
cost alone: a process from an unrelated project occupied about one core
throughout, and the Python suite of section 2 ran across part of both.
Against `docs/68`'s 3 h 01 m 37 s and 2 h 56 m 23 s on the same flow,
these are 21 % and 28 % shorter, and that comparison is worth nothing
for the same reason.

---

## 15. What the next block should be

1. **Test whether this flow is reproducible run to run.** Section 11
   names it: every noise floor in this repository — `docs/44`'s 0.4 ns,
   `docs/68`'s area floor, this document's section 5.3 — is a floor
   over netlists that silently assumes the same netlist twice gives the
   same layout. **One re-run of `s70boot`'s netlist under a second tag
   settles it**, it costs one layout, and it decides whether section
   6.1's −4.3009 ns is a property of a netlist or a draw. Nothing else
   in this list is worth as much per hour. *Closed 2026-09-05 by
   `docs/71-layout-reproducibility.md`: it is a property of the netlist.*
2. **Find out what the post-GRT resizer did.** Section 6.2 localises
   the regression to one stage and one observable — 102 setup repair
   buffers against 519 — and stops there. `repair_timing`'s own report
   and its iteration budget are in the step's log and were not read.
   This is the difference between "reported" and "explained". *Closed 2026-09-06 by
   `docs/72-post-grt-resizer.md`: read, instrumented and explained —
   no cap bound; 20 of 3,365 endpoints visited before OpenROAD's
   no-progress rule fired; 2.477 ns of the 4.0739 handed to the resizer
   by one macro-crossing net, 2.092 ns not recovered.*
3. **`docs/50`'s read register, which is owed a re-measurement.**
   `docs/67` section 5.3 found the load return carrying the memory's
   decoder and the register file's encoder in series, and section 6.3
   shows that population is now **1,018 endpoints at −6.8564**. The
   mechanism that splits it has been priced twice on designs that no
   longer exist.
   *Measured 2026-09-15 on the eight-macro design: `docs/50` section 16. The macro read return stops being a violating launch group (360 endpoints to 17, their TNS -864.88 to -28.87) and the design's setup TNS improves 21.9 %, at the cost of 325.7 ps of the sign-off layout's 29.6 ps hold margin at the fast corner, which takes hold negative. It stays at its default of 0.*

4. **Close the strap sampling window, or record that it stays open.**
   `docs/69` section 15 item 2, unchanged and untouched by this
   document: a two-clock exposure with a permanent, silent, unreported
   effect on the boot decision. It is smaller than `docs/69` was and it
   is the sharpest thing still open **inside** the block this document
   just placed.
5. **The report has no reader.** `docs/69` section 15 item 3: two lines
   in `boot.c` put `BSTAT.TMRCNT` on the console beside the boot count
   and the watchdog's reset count.
6. **The remaining items of `docs/68` section 16 are unchanged**: place
   the ROM's check macros or retire them, an ingress channel and then
   standby, the copy's 44 cycles per word, the twenty-six unre-examined
   checks, and a **v0.2 of `docs/60`**, now owed by five documents.
