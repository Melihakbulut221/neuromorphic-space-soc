# 73 — The CLINT placed on one side of the ROM: the crossing moves to the cut, the binding path moves into the time base, and a fence in this channel does not route

`docs/72-post-grt-resizer.md` section 15 opens with the item this
document is the answer to:

> **Put the CLINT's read mux and its response register on one side of
> the ROM.** Section 6.4: both runs split `s_rdata_clint` across the
> upper macro, and the binding stage in the hardened run is a one-drive
> gate driving a macro-crossing net. This is a placement question
> before it is a timing one, and it has a cheap first probe that is not
> a new floorplan: the flow's own `PL_SOFT_OBSTRUCTIONS` or a region
> constraint on `u_clint`'s cells, measured to step 37 on the hardened
> netlist with everything else held. `docs/48`'s lesson applies — one
> probe, not four — and the metric is section 6.4's crossing count on
> the worst path, not the WNS alone.

**It was done, in two forms, and neither took the crossing to zero.**
A placement region — OpenROAD's `dbRegion` and `dbGroup`, which no
LibreLane key reaches, written into the flow's own saved database
between two steps — fences the CLINT's cells into a box in the channel
under the ROM, and **does not route**: the channel has no 38,000 um2
to give, 3,076 cells spread into the macro gaps, and the global router
ends with 420 units of overflow. The flow's own
`MANUAL_GLOBAL_PLACEMENTS`, which moves the same cells to the same
coordinates and holds every other cell at `s71boot`'s placement,
routes and reaches sign-off, and **the crossing count on the
register-file read went from 2 to 4, not to 0**: the response
registers and the exclusive part of their mux moved, the decode that
selects them and the mtime SECDED decoder did not, and every net
between the two halves now crosses the macro. The worst path moved
from the register-file read into the CLINT's time base — `code_in` →
`check_raw`, four crossings, three stages over 300 fF — at
**−15.1863 ns at step 37 against −8.1852**, and **−13.9924 at sign-off
against −9.1085**, with the typical corner failing for the first time.

**The resizer's trace says it was handed a different problem, not that
it behaved differently.** Re-executed on the new run's saved state with
`docs/72`'s instrumentation, it reproduces the flow's step to the byte
and shows the same loop at a third height: a 281-iteration chase from
−24.773 to −10.675 (`docs/72`: 257, −12.260 → −7.990), then nineteen
CLINT registers tried 51 times each and restored, OpenROAD's
no-progress rule at 1,200 and 1,300, **21 of 3,434 endpoints visited**
against 20 of 3,365 — and the registers at the head of the list are
the time base's check bits instead of the response register.

**The finding is a condition, not a placement.** The CLINT's response
registers, the fabric decode that selects them and the time base that
feeds them have to be on one side of the macro together; a constraint
that captures one without the other moves the crossing to the cut.
The set the two layouts moved was itself smaller than intended — the
tool that derived it dropped five cell masters through an unanchored
regular expression, section 3.4, found after both layouts had used it
and fixed — and the set that captures the whole co-placed cluster
(1,830 cells, four fifths of which the placer had already put in the
pocket as one unit) was taken as far as a placement and no further,
under the bound of 2026-09-06 and `docs/48`'s one-probe rule: section
15 item 1 says exactly what one more layout would answer and does not
run it.

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

**No RTL was modified, and `config-ecc.json` was not modified.** The
constraint lives in a generated copy, `hw/soc/pnr/config-ecc-clint.json`,
that a script derives from `config-ecc.json` and asserts differs from it
in the constraint key and a comment and in nothing else, section 4.3.
Section 13 lists every file.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Does the worst path still cross the ROM?** | **Yes — differently.** The register-file read that was the worst path crosses it **four** times instead of two (section 7.3, queried by name: −12.2500 against −8.1852), and the new worst path, inside the CLINT's time base, crosses it four times at step 37 and twice plus once on its launch clock at sign-off. No path measured here went to zero crossings. Sections 7 and 9 |
| **What is the worst path now?** | `u_mtime_dec.code_in[42]` → `check_raw[1]` at step 37, `code_in[46]` → `check_raw[4]` at sign-off: the mtime codeword register, in the channel, through its SECDED decoder, in the pocket, through the increment, back through the encoder — 1,147 endpoints launch from that register at sign-off where `s71boot` had 7. **A different structure**, `docs/49`'s relocation: the constraint was moved to the boundary of the moved set. Sections 7.2 and 9.2 |
| **What did the resizer do?** | **The same thing, from further away.** Iteration 0 −24.773 against −12.260; a 281-iteration chase to −10.675; 19 stuck endpoints; the rule at 1,200 and 1,300; 21 of 3,434 visited; 147 buffers; −10.659 final. Byte-identical reproduction by the instrumented re-run. Section 8 |
| **Sign-off** | slow **−13.9924 / 3,430** against −9.1085 / 3,361; typ **−2.1708 / 98** against +1.7820 / 0; fast +4.3136; hold +0.0775 / +0.2820 / +0.5878, 0 violations; DRC 0; 885,409 um2 against 876,321; 5,137,507 um of wire against 4,248,250; 17 of 19 checkers, exit 1. Section 9 |
| **Did the fence work?** | **No, and the reason is measured**: a hole in a channel running at 0.30–0.46 in every 200 um column spreads 3,076 cells into the macro gaps, +32.5 % global-route wire, 420 overflow, `GRT-0116`. `docs/48` section 5's mechanism, reproduced by a hole instead of a smaller die. Section 5 |
| **Which mechanism, and why?** | Both. The region, because it is what `docs/72` asked for and the only form that constrains cells by name; `MANUAL_GLOBAL_PLACEMENTS`, because it is the flow's own key, moves the set and nothing else, and routes. `PL_SOFT_OBSTRUCTIONS` not run: the fence already measured that the channel cannot absorb the pocket. Section 4 |
| **Was the baseline re-run?** | **No.** `s71boot` is deterministic (`docs/71`); the fence changes no key; the manual form changes the constraint key and, for the resumed tail, `GRT_ALLOW_CONGESTION`, which the source shows gates only a message and which `s71boot`'s zero-overflow router never consulted. Section 4.4 |
| **What was the set?** | Derived, not read: 743 cells by an exclusive-fan-in rule over the surviving net names — and derived with a defect that dropped five masters, so the rule's own answer is 999 and the block's register-to-register closure is 1,830. Sections 3.2 and 3.4 |
| **Did the checkers keep watching?** | **17 of 19, exit 1**, on `s73clintmgp3` and re-run on `s71boot`. The fence run and the union fence have no checker stage and no sign-off figure. Section 9 |
| **May a frequency be published?** | **No.** `docs/53` section 9.2's three grounds bind. Slack against **20 ns** is what is reported. |

> **THE ONE-SENTENCE RESULT.** Putting the CLINT's response registers
> on the channel side of the ROM without the decode and the time base
> that feed them doubled the crossings on the read path, moved the
> worst path into the time base at −13.99 ns, and handed the resizer
> the same unrepairable stage 12.5 ns further down; the crossing is a
> property of where the cut falls, not of which cells are moved.

---

## 2. Reproducing every instrument before moving it

`docs/44` section 5.2's rule. Everything below was read out of `s71boot`
— the run `docs/72` analysed and `docs/71` measured reproducible — in
this session, before anything was executed, and `s71boot` is this
document's baseline throughout (section 4.4 says why it does not need
re-running).

| What | Published | Measured here |
|---|---|---|
| the resizer's own starting point | `docs/72` 6.2: **−12.260** at iteration 0, TNS −12,810.3, 3,365 endpoints, first endpoint `_80296_/D` | row `0*` of `36-openroad-resizertimingpostgrt/…log`: **−12.260 / −12,810.3 / −20,775.3 / 3365 / `_80296_/D`** **[fact]** |
| its trajectory | `docs/72` 4.1: −7.987 from iteration 300, fix-rate exits at 1,100 and 1,200, −7.841 final, 102 buffers | rows `300*` −7.987 / −7,308.7; `1100*` and `1200*` −7.987 / −7,308.7 / 102 buffers; `final` −7.841 / −7,261.3 / 3,347 endpoints **[fact]** |
| its summary | `docs/72` 4.2: 3,365 / 3 / **102** / 168 / 52 / `RSZ-0062` | `RSZ-0094` 3365, `RSZ-0059` 3, `RSZ-0040` **102**, `RSZ-0051` 168 up, `RSZ-0043` 52, `RSZ-0062` present; step time **9 m 52.82 s** **[fact]** |
| the router before it | `docs/72` 6.1: 5,310,590 um, 59,758 nets, zero overflow | `GRT-0018` 5,310,590 um, `GRT-0014` 59,758; every layer 0 / 0 / 0 overflow; total usage 22.61 %; step time 16.06 s **[fact]** |
| step 37 | `docs/70` 6.2, `docs/72` 8.1: **−8.1852**, TNS −17,872.4 | `timing__setup__ws` **−8.18517**, `timing__setup__tns` −17,872.4 at `nom_slow_1p08V_125C` **[fact]** |
| sign-off | `docs/70` 6.1, `docs/71` 5: **−9.1085 / 3,361**; hold +0.0621 / +0.2735 / +0.5897; 876,321 um2; 4,248,250 um | `signoff_report.py hw/soc/pnr/runs/s71boot`: **−9.1085 / 3361**; +1.7820 typ, +8.0527 fast; hold **+0.0621 / +0.2735 / +0.5897**, 0 violations; cells excl. fill **876,321** um2; routed **4,248,250** um; max slew 1 / 47 / 2; max cap 16 / 16 / 16; 565 max-fanout; 674 antenna diodes; DRC 0 **[fact]** |
| the checkers | `docs/71` 9, `docs/72` 9: **17 of 19, exit 1** | 17 of 19, `LintWarnings` and `WireLength` abstaining, `$?` = **1** **[fact]** |
| the netlist | `docs/70` 2, `docs/72` 2: `a8d5ef81…` | `md5sum hw/soc/out/s70-rom0-syn/soc_top.netlist.v` → `a8d5ef81446ce6d2aa2eb4c1e0fdff79` **[fact]** |
| the pocket census | `docs/72` 6.4: channel **45,619**, upper pocket **2,222**, lower pocket 3,568, strip 441, elsewhere 436; 308 flip-flops in the upper pocket; baseline 45,966 / 2,208 / 3,049 / 424 / 173 | `clint_region.py census` on `26-openroad-detailedplacement/soc_top.def`: **45,619 / 2,222 / 3,568 / 441 / 436**, total 52,286, **308** flip-flops in the upper pocket **[fact]**. Baseline `s70base`: 45,966 / **2,209** / 3,049 / 424 / **172** — one cell on the boundary between the upper pocket and "elsewhere" is classified the other way; total 51,820 agrees **[fact]** |
| the crossings | `docs/72` 6.4: **2** on the step-37 worst path in the hardened run, **0** in the baseline; 0 at the hardened sign-off | `clint_region.py path` on `37-openroad-stamidpnr-3/max.rpt` with the step-36 DEF: `raddr_b_i[0]` → `s_rdata_clint[27]`, 90 driver stages, **2 crossings** — `rebuffer14023` in the channel at (1890.24, 1228.50) driving `rebuffer14022` in the pocket at (1890.24, 1735.02), and `_68128_` `nand3_1` in the pocket at (1939.68, 1772.82), 184 fF, **1.978 ns**, driving `_68129_` in the channel at (1935.36, 1360.80) **[fact]**; baseline step 37: 92 stages, **0** crossings; hardened sign-off `49-openroad-stapostpnr`: 75 stages, **0** crossings, heaviest `_73919_` `nor4_1` 128 fF 2.681 ns **[fact]** |

**[fact for every row]**

The last two rows are the instrument this document's judgement rests
on, so they were built first and checked against `docs/72` before the
constraint existed: the zone convention that reproduces the five census
numbers exactly, and the crossing rule that reproduces the 2 and the 0.

---

## 3. What "the CLINT" is, in a netlist that has forgotten

### 3.1 The problem

`docs/59` section 6 established that the physical database carries no
hierarchy: `flow/syn_soc_top.sh` runs `synth -flatten` **before** `abc`,
so the technology mapper saw one combinational cloud from the register
file's read address to the CLINT's response register, and the cells it
emitted are `_NNNNN_` with no memory of which module they came from
**[fact, `syn_soc_top.sh` lines 542 and 549]**. What survives is net
names: `u_clint.mtimecmp[*]`, `u_clint.g_mtime_secded.u_mtime_dec.code_in[*]`
and `check_raw[*]`, `u_clint.rvalid_o`, `u_clint.err_o`, `u_clint.gnt_o`,
the encoder's `code_unused[*]`, and the fabric's `s_rdata_clint[*]` —
832 occurrences of `u_clint.` in the netlist, on seven names **[fact]**.
Nothing named `u_clint.msip`, nothing for the address decode, nothing
for the read mux.

A region constraint needs a list of instances, so the list had to be
derived, and the first derivation was wrong in an instructive way. A
plain backward cone from the 32 `s_rdata_clint` flip-flops' `D` pins,
stopping only at named nets and at flip-flops, returns **4,036 cells**,
1,069 of them `a22oi_1` — it is the register file's 32 × 39-bit read
multiplexer, the Ibex ALU and the fabric's address mux, and its
boundary is `rf_reg_q` and `csr_pmp_addr_o` **[fact]**. That is the
worst path, not the CLINT. There is no net between the ALU and the
CLINT's decode that Yosys kept a name on.

### 3.2 The rule

`hw/soc/pnr/clint_region.py members` **[fact, the script, run on
`a8d5ef81…`]**:

- **seeds**: every cell whose output drives a `u_clint.*` or
  `s_rdata_clint[*]` net — **243** cells: 170 flip-flops (64 `mtimecmp`,
  64 `code_in`, 8 `check_raw`, 32 `s_rdata_clint`, `rvalid_o`, `err_o`)
  and 73 combinational drivers of named CLINT nets;
- **the cone**: a fixpoint that adds a cell when **every load of every
  one of its outputs is already a member** and no output touches a port
  or a macro pin — the logic that feeds nothing but the CLINT.

The result is **743 cells: 170 sequential and 573 combinational,
15,231.8880 um2** of LEF area — 166 `xnor2_1` and 37 `xor2_1` (the
mtime SECDED decode and encode), 92 `mux2_1` and 61 `a22oi_1` (the read
and write muxes), 77 inverters, and a tail of small gates **[fact]**.
Its inputs from outside are `clk_i` and `rst_sys_n` on 170 flip-flops
each, `s_wdata` on 31 pins, `s_be` and `s_addr` on two each, and **440
pins on anonymous nets** — the decoded address and the fabric's select,
arriving from cells the exclusive rule correctly leaves outside because
a second block also reads them **[fact]**.

**What the rule leaves out is stated rather than hidden.** The
address decode that only the CLINT uses but that `abc` merged with the
decode of the other slaves is outside the set; so is `msip`, one
flip-flop whose `Q` net lost its name; so is the comparator that drives
`irq_timer_o`, because its output leaves the set. On the step-37 worst
path of `s71boot` the set covers exactly the three stages `docs/72`
section 6.4 named as the binding structure — `_68126_` `a22oi_1`,
`_68128_` `nand3_1` and `_68129_` `nor2b_1` — and not `_52172_`, the
`nor4_1` of section 6.3, which drives eight loads and is fabric decode
**[fact]**. "The CLINT's read mux and its response register" is
therefore what the set contains; "`u_clint`" in the RTL sense is what
it approximates.

### 3.4 A defect in the derivation, found after two layouts had used it

**The 743-cell set of section 3.2 is smaller than the rule says it
is, and the reason is a regular expression.** `clint_region.py` reads
each cell's output pins out of the PDK LEF, and its first version
matched `MACRO <name> … END <name>` without anchoring the keyword to a
line. The LEF's `PROPERTYDEFINITIONS` block also contains the word
`MACRO`, the match that started there ran to the first `END` it could
pair, and **the first five macros of the file — `sg13g2_a21o_1`,
`a21o_2`, `a21oi_1`, `a21oi_2`, `a221oi_1` — were swallowed: 80 of 84
masters parsed** **[fact]**. A cell of an unknown master can never
join the exclusive set (the rule skips it), and neither can anything
upstream of it. The design has **4,832** cells of those five types,
10.6 % of it; 5,195 nets had loads and no driver in the parsed
netlist, 363 after the fix (the remaining ones are ports, constants
and the seven `assign` statements).

Fixed — the match is now anchored — the same rule on the same netlist
gives **999 cells, 17,552.5056 um2**: the 743 plus 256, of which 213
were in the pocket in `s71boot` **[fact]**. The 256 include the
cells `docs/72` named on the crossing: `_52172_`, the `nor4_1` of its
section 6.3, `_68120_`, `_67981_`, `_68005_`, and `_68094_` — every one
of them `a21oi`-adjacent decode that the defective parse had cut off.
**All 32 response registers' `D`-pin drivers are in the corrected set;
25 were in the defective one.**

What the corrected exclusive set still leaves out is the mtime SECDED
decoder — `_44320_` to `_44785_` in section 7.2 — for the reason
section 3.2 gives: its corrected value also feeds the `mtip`
comparator, whose output leaves the block. So a third derivation was
added for the third layout: the register-to-register **closure** of
the CLINT — the cells that are both in the backward cone of a CLINT
flip-flop's `D` and in the forward cone of a CLINT flip-flop's `Q`,
through combinational cells of any type, stopping at any flip-flop or
macro — which is the decoder, the increment, the encoder, the read and
write muxes and the fabric handshake around `gnt_o` and `rvalid_o`:
**1,659 cells**. Its union with the corrected exclusive set is
**1,830 cells, 26,267.0688 um2**, of which **1,461 sat in the upper
pocket in `s71boot`, 356 in the channel and 13 elsewhere** **[fact]**.
That last row is the one that matters: the placer had put four fifths
of this set in the pocket as one cluster, and sections 6 and 7 are
what happened when two fifths of it was moved out.

Sections 5 to 9 report the layouts that used the defective 743-cell
set, as measured, because they are real layouts of a real constraint
and because what they measured — the crossing relocating to the cut —
is the mechanism. The 1,830-cell union was taken only as far as the
fence form's detailed placement, section 5.4, to obtain the placer's
own coordinates for it; **the layout that would move it was not run**,
section 15 item 1 says exactly what it would answer, and
`hw/soc/pnr/config-ecc-clint2.json` is generated and ready for it. The
tool in the tree is the fixed one; `clint_members.json` in
`runs/s73clint-pre/` is the defective list the first layouts consumed,
kept so that they can be reproduced.

### 3.3 Where the set was

| run | cells of the set in the channel | in the upper pocket | elsewhere | `s_rdata_clint` flops, pocket / channel / other |
|---|---:|---:|---:|---|
| `s71boot`, step 26 | 43 | **694** | 6 | 16 / 14 / 2 |
| `s70base`, step 26, the set rederived from its own netlist (886 cells, 15,756.2496 um2) | 52 | **803** | 31 | 20 / 12 / 0 |

**[fact, `clint_region.py census`; the baseline's set is derived from
`hw/soc/out/s70-rom0-syn-h0/soc_top.netlist.v`, because instance names
are not shared between netlists]**

So `docs/72` section 6.4's "both runs split the CLINT's 32-bit read-data
register across the macro" is a corner of a larger fact: **the placer
put essentially the whole CLINT in the pocket above the upper ROM in
both runs**, and the response register is the part of it that happens
to have a name. The set's channel-side partners — the 488 cells outside
it that drive or load its nets, weighted by pin — sit at a centroid of
**(1888.1, 1292.9) um**, and the 96 loads of `s_rdata_clint` (the
fabric's read mux) at a median **(1893, 1334)**: the top-right corner
of the channel, directly under the ROM **[fact, `s71boot` step 26]**.
The macro sits between the CLINT and everything it talks to.

---

## 4. How the constraint was applied, and the two forms it took

### 4.1 The options, read before choosing

| Mechanism | Where | What it does | Why not, or why |
|---|---|---|---|
| `FP_OBSTRUCTIONS` | LibreLane, floorplan step | removes placement sites for the whole flow | a hole, not a constraint on cells |
| `PL_SOFT_OBSTRUCTIONS` | LibreLane, floorplan step | a soft blockage the initial placer avoids and later steps may use | keeps *all* 2,222 pocket cells out of the pocket, not the CLINT; the coarser probe of `docs/72` 15.1, not run |
| `MANUAL_GLOBAL_PLACEMENTS` | LibreLane, `Odb.ManualGlobalPlacement`, step 25 | sets named instances to given coordinates, `PLACED` and unfixed, after global placement and before legalisation | **used, second form**: moves the set and nothing else |
| a placement region: `dbRegion` + `dbGroup` | OpenROAD; no LibreLane key or hook reaches it | `gpl` builds a separate placement problem per group inside the region's box and **blocks the region's sites for every other cell**; `dpl` legalises group cells inside and keeps the rest out (`placerBase.cpp`, `Opendp.cpp` at `0e2d771c5e`) | **used, first form**: the fence `docs/72` 15.1 called "a region constraint on `u_clint`'s cells" |

**[fact: `librelane/steps/openroad.py` and `odb.py` at v3.0.5 — the only
Tcl file a design can inject is `STA_EXTRA_CORNER_TCL_FILE`; the
OpenROAD sources at the installed commit]**

`PL_SOFT_OBSTRUCTIONS` was not run because it answers a different
question — what the pocket costs — and because the fence's result,
section 5, is that this channel has no room for what a soft blockage
would push into it. The macros were not moved: `docs/48` measured the
macro placement HPWL-optimal for these pins and two alternatives
worse, and nothing here re-opens that.

### 4.2 The first form: a fence, applied between two steps

No configuration key creates a region, so it was written into the
flow's own saved database: `hw/soc/pnr/clint_region.py apply` reads
`s71boot`'s `13-openroad-generatepdn/soc_top.odb` (the last database
before global placement — steps 14 and 15 change no view), creates one
`dbRegion` named `clint` with one boundary box, one `dbGroup` in it,
adds the 743 instances, and writes an ODB, a DEF and a copy of step
15's `state_out.json` with only its `odb` and `def` entries re-pointed.
The flow then resumed from `OpenROAD.GlobalPlacementSkipIO` on that
state with `config-ecc.json` unchanged — `docs/71` section 6.3's resume
form, whose loss was measured to be nothing, used here as the hook the
tool does not have.

The edit was checked before it was used: the written DEF differs from
step 13's in **191 lines, all of them the three-line `REGIONS` section
and the 188-line `GROUPS` section**; the state file differs in `def` and
`odb` **[fact, `diff`]**.

**The box**, `(1780.32, 1217.16)–(2020.32, 1375.92)` um: 500 sites by
42 rows, **240.00 × 158.76 = 38,102.40 um2**, on the site grid so that
`dpl` invalidates no half-covered pixel, its top on the channel's last
full-width row (y = 1372.14, the halo edge is 1377.26) and its centre
at x = 1900 — the column where the set's channel members and its
partners already were. The set fills it to **0.3998**, under the 48 %
density target the run places at. In `s71boot`'s step-26 placement the
same box held 1,259 cells and 15,437 um2, 0.40 utilisation **[fact]**.
One box, sized to the set at the flow's own density and put where the
set's connections are: `docs/48`'s one probe.

### 4.3 The second form: the flow's own key, on the flow's own placement

`hw/soc/pnr/clint_region.py placement` reads the 743 members'
coordinates and orientations out of a placed DEF into the shape
`MANUAL_GLOBAL_PLACEMENTS` takes, and `clint_region.py config` writes
`config-ecc-clint.json` as `config-ecc.json` plus that key and one
comment, asserting that nothing else was added or changed —
`pnr_soc_top.sh`'s own guard, at one more layer. The coordinates are
the ones in `hw/soc/pnr/clint_placement.json`, which is tracked; the
configuration file is regenerated from it and gitignored, like `docs/48`'s
floorplan variants.

The flow resumed from **`s71boot`'s own step 24**
(`24-openroad-repairdesignpostgpl/state_out.json`) at
`Odb.ManualGlobalPlacement`, the step that in every earlier run printed
`'MANUAL_GLOBAL_PLACEMENTS' not set. Skipping`. Everything upstream of
that point is `s71boot`'s, to the byte, by `docs/71`; everything
downstream is `s71boot`'s flow with 743 cells moved before legalisation.

### 4.4 Why the baseline is `s71boot` and was not re-run

`docs/71` measured the flow bit-reproducible, so `s71boot` *is* the
measurement of `config-ecc.json` on this netlist. The first form
changes no configuration key at all — `resolved.json` of the fence run
differs from `s71boot`'s in **no key** **[fact]**. The second form
changes exactly the constraint key and a comment — `resolved.json`
differs in **`MANUAL_GLOBAL_PLACEMENTS`** and nothing else, the `//clint`
comment not being carried into it **[fact]** — plus, for the tail
resumed after the router, `GRT_ALLOW_CONGESTION`, section 6.3 — and starts from `s71boot`'s own saved state, so no
upstream step could have moved. `docs/45`'s and `docs/48`'s conditions
for re-running a baseline (a changed file list, a density target that
binds differently) are not met by either.

---

## 5. The fence does not route, and the reason is `docs/48`'s

The fence run, `hw/soc/pnr/runs/s73clint`, resumed from
`OpenROAD.GlobalPlacementSkipIO` on the edited state, is the run
`docs/72` section 15 item 1 literally asked for, and **it did not reach
the resizer**: `OpenROAD.GlobalRouting` ended with `GRT-0116`, "Global
routing finished with congestion", after all 50 extra iterations, and
LibreLane stopped **[fact, `hw/soc/out/s73-pnr-clint.log`]**. What it
measured on the way is the mechanism, and it is `docs/48` section 5's.

### 5.1 The placer honoured the region and paid for it everywhere else

`gpl` printed `---- Initialize Region: clint`, a region area of
38,102.400 um2 on 256 bins beside the top level's 4,338,910.800 on
65,536, and `Region 'clint' placement finished at iteration 240` in the
skip-IO pass and 335 in the full one **[fact, the two step logs]**. The
743 cells went where they were told: at detailed placement every one of
them is inside the box, bounding box (1786.56, 1217.16)–(2015.52,
1368.36) **[fact, `clint_region.py census`]**. Then:

| | `s71boot` | fence run | Δ |
|---|---:|---:|---:|
| global placement, final HPWL at overflow ≈ 0.099 | 2.907875e+06 um, 1,608 iterations | **3.486970e+06 um**, 1,009 iterations | **+19.9 %** |
| post-global-placement setup ws (step 23 / 08) | −157.353 | −166.572 | −9.2 |
| detailed placement, HPWL after | 3,545,538 um | **4,233,860 um** | +19.4 % |
| standard cells in the channel (step 26 / 11) | **45,619** | **42,543** | **−3,076** |
| in the upper pocket | 2,222 | 3,312 | +1,090 |
| in the lower pocket | 3,568 | 3,942 | +374 |
| in the strip beside the ROMs | 441 | 732 | +291 |
| elsewhere | 436 | **1,720** | **+1,284** |
| of "elsewhere": the 40 um gap between the RAM column and the ROMs | 340 | **837** | |
| the 60 um column left of the RAMs | 3 | **630** | |
| the 40 um gaps between the two RAMs of each row | 90 | 228 | |
| above the upper macro row | 0 | 24 | |
| flip-flops in the upper pocket | 308 | 129 | |
| CTS, `u_ibex.clk`: sinks / average sink wire | 2,464 / **780.40 um** | 2,472 / **1,181.59 um** | +51 % |
| CTS, `clk_i_regs`: sinks / average sink wire | 3,785 / 1,583.73 um | 3,759 / 1,625.68 um | +2.6 % |
| CTS, macro `clk_i` | 7 / 2,674.24 | 7 / 2,698.09 | |
| post-CTS setup ws (step 28 / 13) | −12.5734, TNS −20,553.2, 3,163 endpoints | **−18.0426**, −31,808.2, 3,230 | −5.47 |
| post-CTS resizer: buffers / resized / pin swaps | 203 / 492 / 132 | 443 / 884 / 198 | |
| post-CTS repair, placement parasitics (step 30 / 15) | −2.5962, −3,801.1, 2,897 | **−3.8923**, −7,168.41, 3,076 | −1.30 |
| global routing: wirelength | 5,310,590 um | **7,035,796 um** | **+32.5 %** |
| global routing: overflow, max H / max V / total | 0 / 0 / 0 | **5 / 4 / 420** (Metal5 262, Metal4 82, TopMetal1 55, Metal2 17, TopMetal2 3, Metal3 1) | |
| global routing: total usage | 22.61 % | 31.15 % | |
| global routing: extra iterations / step time | 3 / 16.06 s | **50 / about 33 min** (the flow log's progress clock; the step wrote no `runtime.txt`) | |

**[fact for every row; the step logs, `or_metrics_out.json`, the DEFs
through `clint_region.py census`, and a classification of the
"elsewhere" cells by the macro gaps of `docs/59` section 4.2]**

### 5.2 Why: the channel had no 38,000 um2 to give

The fence removes its sites from the top-level placer. **The channel
lost 38,102 um2 of placeable area and gained back 15,232 um2 of cells
it no longer had to hold**, a net 22,870 um2 of demand at a 48 %
density target that the channel was already meeting: in `s71boot`'s
step-26 placement the channel's own utilisation, in 200 um columns
from its left edge, reads 0.30, 0.44, 0.45, 0.37, 0.37, 0.42, 0.38,
0.38, 0.39, 0.43 and 0.46 at the ROM end **[fact, `s71boot` step-26
DEF, cell area over the 179 full-width channel rows]**. That is
`docs/59` section 5.2's 34.84 % grown into a design 1.9 times larger,
and there is no column with room for a hole. The placer did what
`docs/48` section 5 watched it do when FP-A shrank the channel: it
spread. 3,076 cells left the channel and 1,284 of them landed in the
worst places on the die — 630 in the 60 um column left of the RAM
macros, 837 in the 40 um gap between the RAM column and the ROMs —
and `u_ibex.clk`'s average sink wire went up by half. The global
router then laid down 32.5 % more wire and could not clear 420 units
of overflow on the layers that cross macros, exactly the pair of
symptoms `docs/48` section 5 recorded for FP-B (+44.1 % wire) and
FP-A (a router that did not finish).

The fence is therefore not a measurement of the CLINT; it is a second
measurement of the channel's density regime, and it agrees with the
first. **A region constraint that excludes other cells is not
available on this floorplan at this cell count**, and `PL_SOFT_OBSTRUCTIONS`
over the pocket — 2,222 cells pushed into the same channel with
nowhere to go — is the same experiment with a larger number, which is
why it was not run.

### 5.3 What it did say about the CLINT, before it stopped

Two things survive from the fence run because they are placement
facts and not routing ones. First, with the whole set in the channel
the post-CTS-repair worst path (step 15, placement parasitics) is no
longer the register-file-to-`s_rdata_clint` read: it is
`raddr_a_i[0]` → `u_mtime_dec.check_raw[7]`, into the CLINT's time
base, 96 stages of which 10 are members and all 10 in the channel, and
it crosses the macro **4** times through cells that are *not* members
and were exiled to the pocket and to the RAM/ROM gap — `_43413_`
`xnor2_1` at (1944.48, 1935.36), `_43588_` `nand4_1` at (1900.32,
1939.14), `_43587_` `nor4_2` at (1743.36, 1409.94) **[fact,
`clint_region.py path` on step 15]**. That is the shape section 7
finds again in the run that routed. Second, the box itself was not the
problem: its 743 cells at 0.40 utilisation legalised in 2.5 s with zero
displacement **[fact, step 11's `DPL` lines]**.


### 5.4 The union set, fenced, to detailed placement only

The 1,830-cell union of section 3.4 was given the same treatment as
far as detailed placement and no further — `-T OpenROAD.DetailedPlacement`
— to obtain the placer's own coordinates for it and to see whether a
larger fence behaves differently. It does not. Box
`(1740.00, 1168.02)–(2060.16, 1375.92)`, 667 sites by 55 rows,
**320.16 × 207.90 = 66,561.26 um2**, utilisation 0.3946 **[fact]**:

| | `s71boot` | union fence, `s73v2fence` |
|---|---:|---:|
| global placement, final HPWL | 2.907875e+06 um | **3.192011e+06 um**, +9.8 % |
| region placement finished at iteration | — | 1,116 |
| post-global-placement setup ws | −157.353 | −165.455 |
| standard cells in the channel | 45,619 | **42,960** |
| upper pocket / lower pocket / strip / elsewhere | 2,222 / 3,568 / 441 / 436 | 3,719 / 4,122 / 455 / **981** |
| of "elsewhere": the RAM/ROM gap | 340 | **824** |
| flip-flops in the upper pocket | 308 | **23** |
| the set in the channel | 356 of 1,830 | **1,830 of 1,830** |
| detailed placement, HPWL after; displacement | 3,545,538 um; 0 | 3,889,286 um; 0 |
| step times, global placement skip-IO / full | 11.7 s / 37.0 s | 75.2 s / 80.1 s |

**[fact]**

A hole 1.75 times larger displaces 2,659 cells from the channel, 824
of them into the 40 um gap between the RAM column and the ROMs, and
the pocket fills with cells that are not the CLINT: 3,719 of them and
23 flip-flops. The placer had put the CLINT cluster in the pocket
because the channel was full; fencing the cluster into the channel
sends the next cluster to the pocket instead. This run was stopped
where it was meant to stop; its coordinates are
`hw/soc/pnr/clint_placement_v2.json` and section 15 item 1 is what
they are for.

---

## 6. The second form: what the layout did

`hw/soc/pnr/runs/s73clintmgp` resumed from `s71boot`'s step 24 with
`config-ecc-clint.json`; `hw/soc/pnr/runs/s73clintmgp2` is the same
flow resumed from that run's own step 06 (post-CTS repair) with
`GRT_ALLOW_CONGESTION=1`, section 6.3. Together they are one layout in
two directories, `docs/70` section 3.3's form.

### 6.1 A controlled move

`Odb.ManualGlobalPlacement` set the 743 cells to the coordinates the
fence run's placer had chosen for them inside the box, and
`OpenROAD.DetailedPlacement` legalised: total displacement 7,033.6 um
over the whole design, average 0.1 um, **maximum 38.9 um** **[fact,
`DPL` lines of step 02]**. Against `s71boot`'s step-26 DEF, **1,475
of 52,286 standard cells sit at a different position: the 743 members
by construction, and 732 neighbours the legaliser nudged by at most
38.88 um, 6.79 on average** **[fact, the two DEFs compared cell by
cell]**. Nothing else moved. This is the experiment the fence could not
be: `s71boot`'s placement with one block relocated.

| | `s71boot` | manual placement | Δ |
|---|---:|---:|---:|
| detailed placement, HPWL after | 3,545,538 um | 3,757,020 um | **+6.0 %** |
| standard cells in the channel (step 26 / 02) | 45,619 | 46,319 | +700 |
| in the upper pocket | 2,222 | **1,528** | −694 |
| lower pocket / strip / elsewhere | 3,568 / 441 / 436 | 3,568 / 441 / 430 | 0 / 0 / −6 |
| flip-flops in the upper pocket | 308 | 157 | −151 |
| the set: channel / pocket | 43 / 694 | **743 / 0** | |
| CTS `u_ibex.clk`: sinks / average sink wire | 2,464 / 780.40 um | 2,464 / **780.40 um** | 0 |
| CTS `clk_i_regs` | 3,785 / 1,583.73 um | 3,771 / 1,542.81 um | −2.6 % |
| CTS macro `clk_i` | 7 / 2,674.24 um | 7 / 2,674.24 um | 0 |
| post-CTS setup ws (step 28 / 04) | −12.5734, TNS −20,553.2, 3,163 | −13.2471, −20,964.4, 3,164 | −0.67 |
| post-CTS resizer: buffers / resized / pin swaps | 203 / 492 / 132 | 225 / 585 / 157 | |
| post-CTS repair, placement parasitics (step 30 / 06) | **−2.5962**, −3,801.1, 2,897 | **−3.5382**, −4,461.96, 2,994 | **−0.94** |
| global routing: wirelength | 5,310,590 um | **6,251,047 um** | **+17.7 %** |
| global routing: usage; Metal5 usage | 22.61 %; 8.64 % | 27.21 %; 13.76 % | |
| global routing: overflow, max H / max V / total | 0 / 0 / 0 | **1 / 0 / 1**, on Metal5 | |
| global routing: extra iterations / step time | 3 / 16.06 s | 50 / 4 m 37.79 s, then 5 m 09.51 s in the resumed run | |

**[fact for every row]**

### 6.2 The wire went up by a sixth, and the place it went is the answer

The set's 815 external input pins are driven from 488 cells, and in
`s71boot` **661 of the 816 pin connections were to cells in the pocket
beside it** and 136 to the channel (section 3.3). Moving the set moved
none of those 488 cells. The exclusive rule of section 3.2 — and, section 3.4, the
defect in its first implementation — had drawn the boundary through
the CLINT: the mtime SECDED *decoder* — the `xnor2`
syndrome tree whose corrected value feeds the tick, the read mux and
the `mtip` comparator — stayed outside the set because the comparator's
output leaves for `irq_timer_o`, and the decoder stayed in the pocket
with the rest of the co-exiled decode. So every net between the
codeword registers, now in the channel, and their decoder, still in
the pocket, crosses the ROM: 940,457 um of global-route wire, Metal5
usage up from 8.64 % to 13.76 %, and one g-cell over the upper-left
RAM macro at x = 835 um where two nets needed a Metal5 track with
capacity for one **[fact; the location from a scratch `global_route
-congestion_report_file` on the same step-06 database outside the
flow, which routed 6,245,920 um with 2 overflow against the flow's
6,251,047 and 1, and is quoted for the location only]**. One of the two
nets in that g-cell is `_11889_`, from `_45614_` in the pocket at
(1829.76, 1818.18) to a member at (1904.64, 1307.88) — a CLINT input,
detoured across the die.

### 6.3 One overflow unit, and the flag that let the flow continue

`GRT_ALLOW_CONGESTION` is `False` in `config-ecc.json`, so the flow
stopped at the router with **one** unit of overflow. In OpenROAD at
the installed commit the flag decides only which message is printed
after the routing is complete and its guides saved: `is_congested_`
then `allow_congestion_ ? warn GRT-0115 : error GRT-0116`
(`src/grt/src/GlobalRouter.cpp` lines 427–440) **[fact]**. The
routing is the same routing. The layout was therefore resumed from its
own step 06 with `-c GRT_ALLOW_CONGESTION=1`, as `s73clintmgp2`, and
carried to sign-off. `s71boot`'s router had zero overflow on every
layer, so the flag would never have been consulted there: `s71boot`
remains the baseline, and the flag is recorded as a second key that
differs, section 4.4, whose effect on the baseline is provably none.
Whether one unit of global-route overflow costs anything is a question
for the detailed router, and section 9 reports its answer.

---

## 7. The worst path, stage by stage

Both reports are `OpenROAD.STAMidPNR-3`, the flow's STA after the
post-GRT resizer on global-route parasitics — step 37 of `s71boot`,
step 07 of `s73clintmgp2` — at `nom_slow_1p08V_125C`, positions from
each run's post-resizer DEF, through `clint_region.py path`.

### 7.1 The path the probe was aimed at, and where it went

| | `s71boot`, step 37 | `s73clintmgp2`, step 07 |
|---|---|---|
| worst path | `raddr_b_i[0]` → **`s_rdata_clint[27]`** | `u_mtime_dec.code_in[42]` → **`u_mtime_dec.check_raw[1]`** |
| slack | **−8.1852** | **−15.1863** |
| arrival / required | 32.17 / 23.98 | 37.168 / 21.982 |
| driver stages (data path, after the launch clock) | 90 | 72 |
| macro crossings on the data path | **2** | **4** (5 counting one launch-clock buffer in the lower pocket) |
| stages that are members of the set | 3, all in the pocket | 7, all in the channel |
| stages ≥ 100 fF, their delay | 12, 5.490 ns | **15, 11.873 ns** |
| heaviest stage | `_68128_` `nand3_1`, 184 fF, **1.978 ns**, pocket → channel | `_44717_` `xnor2_1`, **326 fF, 3.016 ns**, in the pocket |
| next | `_39972_` `nand4_1` 76 fF 1.187; `_42428_` `nor2_1` 85 fF 0.917 | `_45704_` `a21oi_2` **392 fF 2.802**, pocket → channel; `_44785_` `a221oi_1` 109 fF 1.742 |
| violating endpoints / TNS | 3,356 / −17,872.4 | 3,434 / −24,182.4 |

**[fact]**

**The path the probe was aimed at is gone from the report.** In
`s71boot`'s 2,000-path report 31 paths run from the register file's
read address to an `s_rdata_clint` register, the worst of them the
worst path in the design, and every one of the 32 response registers
has that launch as its worst. In the new run **none of the 2,000
paths** has that shape; all 32 response registers now have
`u_mtime_dec.code_in[*]` as their worst launch, at −14.8954 for
`s_rdata_clint[20]` **[fact, both `max.rpt`]**. Section 7.3 has the
direct query for what the old path now reads.

### 7.2 The new worst path, stage by stage

`code_in[42]` → `check_raw[1]` is the CLINT's own time base: the mtime
codeword register, through the SECDED decoder, the increment, the
re-encoder, back into a check bit — `soc_clint.v`'s H6 loop, which
`docs/58` hardened and which `docs/72` section 7.3 saw only as the
seventeenth-to-twentieth endpoint the resizer gave up on. Stage by
stage **[fact]**:

| # | driver | cell | load fF | delay ns | (x, y) um | zone | note |
|---:|---|---|---:|---:|---|---|---|
| 10 | `_77675_` | `dfrbpq_1` | 79.6 | 0.638 | (1786.56, 1326.78) | channel | the codeword register, **member** |
| 11 | `wire14036` | `buf_8` | **863.6** | 0.380 | (1026.24, 1357.02) | channel | a long-wire buffer the resizer put 760 um to the left |
| 12 | `_44320_` | `xnor2_1` | 7.2 | 0.921 | (1893.12, 1890.00) | **upper pocket** | **crosses**: the decoder's first stage, not a member |
| 13–19 | `_44321_` … `_44716_` | `xnor2_1` ×4, `nor2_1`, `nand2_1`, `nor2b_1` | 8–56 | 0.24–0.55 | (1879–1901, 1871–1920) | upper pocket | the syndrome tree |
| 20 | `_44717_` | `xnor2_1` | **326.3** | **3.016** | (1890.72, 1871.10) | upper pocket | the heaviest stage in the design |
| 21–30 | `_44720_` … `_44785_` | `a22oi_1`, `nand3_1`, `nor2b_1`, `o21ai_1` … `a221oi_1` | 4–109 | 0.09–1.74 | (1868–1910, 1788–1807) | upper pocket | the corrected value, the increment |
| 31 | `wire13860` | `buf_8` | 347.7 | 0.637 | (1224.96, **2026.08**) | elsewhere | **crosses**: a long-wire buffer on the one row above the upper macros |
| 32 | `wire1326` | `buf_8` | 144.6 | 0.339 | (1739.52, 1455.30) | elsewhere | the RAM/ROM gap |
| 33–63 | `_44786_` … `_45701_` | 31 stages: `inv`, `nand`, `and4`, buffers, `fanout*`, `a21oi`, `nor4` … | 3–127 | 0.12–0.58 | x 1225–1885, y 843–1157 | channel | the tick and the write path, in the channel |
| 64 | `wire596` | `buf_8` | 264.6 | 0.322 | (1621.44, 1296.54) | channel | |
| 65 | `_45703_` | `and2_2` | **526.6** | 0.709 | (1872.48, 1372.14) | channel | the channel's top row |
| 66 | `_45704_` | `a21oi_2` | **391.9** | **2.802** | (1872.00, 1829.52) | **upper pocket** | **crosses** up and drives 392 fF |
| 67 | `_45706_` | `mux2_1` | 23.4 | 0.758 | (1891.20, 1296.54) | channel | **crosses** back; the write mux, **member** |
| 68–72 | `_51694_` … `_51723_` | `xnor2_1` ×5 | 6–16 | 0.23–0.30 | (1835–1884, 1323–1338) | channel | the re-encoder, **members** |

Read down the zone column and the mechanism is on the page. The
register left the pocket; **its decoder did not**, because section
3.2's exclusive rule kept the decoder outside the set (its corrected
value also feeds the `mtip` comparator, whose output leaves the CLINT
for `irq_timer_o`). So the codeword now goes up over the ROM to be
decoded, comes back down to be incremented and written, goes up again
through `_45704_` and comes back to the encoder. Four crossings where
`docs/72`'s path had two, three stages over 300 fF where it had none,
and the register-file read that was binding is not in the first two
thousand paths.

This is `docs/49`'s lesson at the cell: the constraint was not
removed, it was relocated to the boundary of the set that was
constrained, and the boundary was drawn by a rule about net
exclusivity rather than by the block's own structure. The path that
crosses is the one that connects the moved half of the CLINT to the
unmoved half.

### 7.3 The path the probe was aimed at, queried directly

Because the register-file read no longer appears in the 2,000-path
report, it was asked for by name: the flow's own `OpenROAD.STAMidPNR`
step, re-executed on each run's saved step-37 state through
`librelane.steps run` with its `corner.tcl` copied and one
`report_checks -from {the ten raddr flip-flops} -to {the 32
s_rdata_clint D pins}` appended, and the step's `config.json` corrected
for `docs/72` section 7.1's lossy derate. Both re-runs reproduce the
flow's step — `or_metrics_out.json` **0 keys differ** in either, the
derate logs `5.0%`, the worst slack reads −8.18517 and −15.18630 — so
the query is on the flow's own analysis **[fact]**.

| | `s71boot` | `s73clintmgp2` |
|---|---|---|
| worst register-file → `s_rdata_clint` path | `raddr_b_i[0]` → `s_rdata_clint[27]`, **−8.1852** — the design's worst path | `raddr_a_i[2]` → `s_rdata_clint[20]`, **−12.2500** |
| arrival / required | 30.0376 / 21.8525 | 33.7652 / 21.5153 |
| driver stages | 83 | 81 |
| **macro crossings** | **2** | **4** |
| stages that are members | 3 | **0** |
| stages ≥ 100 fF | 8, 4.429 ns | 12, 7.451 ns |
| heaviest | `_68128_` `nand3_1` 184 fF 1.979 ns | `_68094_` `a21oi_2` 97 fF **3.185 ns**; `fanout2671` `buf_1` 270 fF 1.459; `fanout479` `buf_2` 528 fF 0.901 |
| where it crosses | channel → pocket at `rebuffer14022`; pocket → channel at `_68128_` → `_68129_` | `_45547_` `inv_2` into the pocket at (1969.92, 1735.02); `_45647_` `nand4_1` back to the channel's bottom row of the box at (1924.80, 1217.16); `_67974_` `buf_2` into the pocket again at (1910.88, 1806.84); `wire13808` `buf_8`, 660 fF, on the row above the upper macros at (1167.36, 2026.08), then down to the register |

**[fact]**

**The crossing did not go away on the path it was aimed at either; it
doubled.** The decode that feeds the response register was not in the
set, so it stayed in the pocket, and the response register's own
`D`-pin driver is a member for 25 of the 32 bits in the set the layout
used — bit 20's `_68094_` is one of the seven it missed, through the
defect of section 3.4; all 32 are in the corrected set **[fact, the
netlist]**. The read now leaves the channel to be decoded, comes back to
the box's edge, goes up again for the mux and returns through a
resizer buffer parked on the one row above the macros. Four ROM
crossings, 4.06 ns worse on the same launch-to-capture pair of
structures, and the slowest stage on it is 3.185 ns on a two-drive
`a21oi_2` — the size-up already taken.

---

## 8. The resizer's trace on the new run

`docs/72` section 7's instrumentation, repeated on the new run: the
flow's `OpenROAD.ResizerTimingPostGRT` re-executed on `s73clintmgp2`'s
own step-06 `state_in.json` through `librelane.steps run`, with the
step script copied and three reports and `set_debug_level RSZ
repair_setup 2` added around the setup `repair_timing`, no argument
changed, and the step's `config.json` corrected `5 → 5.0`. It
reproduces the flow's step **to the byte**: `soc_top.odb`, `.nl.v`,
`.def` and `.sdc` identical, **53 metrics, 0 differ**, 147 setup
buffers; 49 m 03 s of wall time on a machine also running a detailed
router, against the flow's 18 m 50.83 s step time **[fact]**. The trace
therefore describes the flow's own run.

### 8.1 The hand it was dealt

| | `s71boot` (`docs/72`) | `s73clintmgp2` | difference |
|---|---:|---:|---:|
| step 30 / 06, post-CTS repair, placement parasitics | −2.5962 | −3.5382 | −0.942 |
| **iteration 0, GRT parasitics, the resizer's own STA** | **−12.260** | **−24.773** | **−12.513** |
| iteration-0 TNS, startpoint-summed / endpoint-summed | −12,810.3 / −20,775.3 | −26,081.0 / −30,441.7 | |
| iteration-0 endpoints | 3,365 | 3,434 | +69 |
| pre-repair `report_wns` / `report_tns` | −12.26 / −20,775.27 | **−24.77 / −30,441.75** | |
| pre-repair worst path | `raddr_a_i[1]` → `s_rdata_clint[2]` | `u_mtime_dec.code_in[58]` → **`check_raw[0]`** | |
| its arrival / required | 34.07 / 21.81 | **46.74** / 21.97 | |
| driver stages; stages ≥ 100 fF, their delay | 75; 14, 11.77 ns | 63; **12, 23.13 ns** | |
| macro crossings on it | 2 | **4** | |
| its heaviest stages | `nor4_1` 180 fF 3.73 ns | `_44431_` `xnor2_1` **470 fF 4.12 ns**; `_45644_` `a21oi_1` 460 fF 4.07; `wire13847` `buf_8` 320 fF 3.08; `_45588_` `nor2_2` **740 fF** 2.70; `_77691_`'s own `Q`, 620 fF, 2.17 | |

**[fact; the pre-repair report prints two decimals]**

Global-route parasitics cost the new layout's worst path **21.2 ns**
relative to the placement estimate, where `docs/72` measured 9.66 for
`s71boot` and 7.53 for the baseline. The path is the time base
(section 7.2's structure before the resizer touched it), and the
stages that carry it are the crossings: the codeword register's own
output at 620 fF, `_44318_` the decoder's first `xnor2` reached across
the macro, and three `wire*` buffers `RepairDesignPostGRT` had already
parked at (1224.96, 2026.08) on the row above the upper macros, at
(914.88, 1602.72) in the gap between the upper RAMs, and at (680.64,
1372.14) — a net from the pocket to the box detoured 1.2 mm to the
left across the die. **The resizer was handed a problem twice as far
from closing as `docs/72`'s**, and every heavy stage on it is a wire
that crosses a macro.

### 8.2 What it did with it

The verbose table, every hundredth iteration and the forced rows at
the phase exits **[fact, the flow's step log]**:

| iteration | WNS | TNS (startpoint) | buffers | |
|---:|---:|---:|---:|---|
| 0 | −24.773 | −26,081.0 | 0 | endpoint `_77625_/D`, `check_raw[0]` |
| 100 | −12.131 | −13,280.5 | 62 | |
| 200 | −10.805 | −11,318.3 | 121 | |
| 281 | −10.675 | −11,259.5 | 135 | **endpoint 1 stuck** on `check_raw[4]` after 51 non-improving passes; 183 → 135 buffers restored from the journal |
| 300 | −10.672 | −11,258.8 | 152 | |
| 500 … 1,000 | −10.672 … −10.671 | −11,289.7 … −11,288.5 | 183 → 166 | flat |
| 1,200 | −10.671 | −11,288.5 | 147 | **fix rate 0.00 % < 0.02 %** |
| 1,300 | −10.671 | −11,288.5 | 147 | **−0.00 %: `LEGACY` aborts** |
| 1,500, final | **−10.659** | −11,281.9 | **147** | `LAST_GASP` |

The trace, `LEGACY*` phase, every endpoint it visited **[fact]**:

| # | endpoint | register | WNS at entry | endpoint slack | exit |
|---:|---|---|---:|---:|---|
| 1 | `_77625_/D` | `check_raw[0]` | −24.773 | −24.773 | chased the worst endpoint to −10.675 over **281** iterations, then stuck on `check_raw[4]` |
| 2 | `_77626_/D` | `check_raw[1]` | −10.675 | −10.567 | stuck after 51 |
| 3 | `_77632_/D` | `check_raw[7]` | −10.672 | −10.414 | stuck after 51 |
| 4 | `_77628_/D` | `check_raw[3]` | −10.672 | −10.515 | stuck after 51 |
| 5 | `_77630_/D` | `check_raw[5]` | −10.672 | −10.502 | stuck after 51 |
| 6 | `_77668_/D` | `code_in[35]` | −10.672 | −8.013 | stuck after 51 |
| 7 | `_77627_/D` | `check_raw[2]` | −10.672 | −10.356 | stuck after 51 |
| 8 | `_77629_/D` | `check_raw[4]` | −10.672 | −10.672 | stuck after 51 |
| 9 | `_77631_/D` | `check_raw[6]` | −10.672 | −10.485 | stuck after 51 |
| 10 | `_77648_/D` | `code_in[15]` | −10.672 | −9.390 | stuck after 51 |
| 11 | `_77667_/D` | `code_in[34]` | −10.672 | −9.583 | stuck after 51 |
| 12 | `_77672_/D` | `code_in[39]` | −10.672 | −8.401 | stuck after 51 |
| 13 | `_77637_/D` | `code_in[4]` | −10.672 | −9.150 | stuck after 51 |
| 14 | `_77671_/D` | `code_in[38]` | −10.671 | −7.624 | stuck after 51 |
| 15 | `_80101_/D` | `mtimecmp[8]` | −10.671 | −9.063 | stuck after 51 |
| 16 | `_77696_/D` | `code_in[63]` | −10.671 | −8.251 | stuck after 51 |
| 17 | `_80309_/D` | `s_rdata_clint[15]` | −10.671 | −9.191 | stuck after 51 |
| 18 | `_80106_/D` | `mtimecmp[13]` | −10.671 | −8.234 | stuck after 51 |
| 19 | `_80103_/D` | `mtimecmp[10]` | −10.671 | −7.993 | **`Exiting at iteration 1200 because incr fix rate 0.00% is < 0.02%`** |
| 20 | `_80107_/D` | `mtimecmp[14]` | −10.671 | −8.048 | stuck after 51 |
| 21 | `_80102_/D` | `mtimecmp[9]` | −10.671 | −8.713 | **`Exiting at iteration 1300 because incr fix rate -0.00% is < 0.02%`**, then `Exiting due to no TNS progress for two opto cycles` |

`LAST_GASP+`: 3,377 violating endpoints remain; **16 visited, 44 moves
accepted, 154 rejected**; WNS −10.671 → −10.659; the endpoints are the
eight check bits, `s_rdata_clint[20]`, `[1]`, `[4]`, `[14]`, three
codeword bits and `mtimecmp[59]` **[fact]**. Summary: `RSZ-0094`
3,434 endpoints, `RSZ-0059` 1 removed, `RSZ-0040` **147** inserted,
`RSZ-0051` 183 up, `RSZ-0043` 61 swapped, `RSZ-0062`; hold 4 endpoints
/ 4 buffers as before **[fact]**.

### 8.3 Against `docs/72`'s 20-of-3,365 and 257-then-flat

| | `s70base` (`docs/72`) | `s71boot` (`docs/72`) | `s73clintmgp2` |
|---|---:|---:|---:|
| iteration 0 | −9.783 | −12.260 | **−24.773** |
| the chase: iterations, from → to | 2,005, −9.783 → −3.272 | 257, −12.260 → −7.990 | **281, −24.773 → −10.675** |
| recovered by the chase | 6.511 | 4.270 | **14.098** |
| `LEGACY` endpoints visited, of | 7 of 3,367 | 20 of 3,365 | **21 of 3,434** |
| of them "stuck after 51" | 1 | 18 | **19** |
| iterations at which the rule fired | 2,200, 2,300 | 1,100, 1,200 | 1,200, 1,300 |
| `LAST_GASP`: visited / accepted / rejected | 70 / 133 / 63 | 156 / 48 / 150 | 16 / 44 / 154 |
| final, resizer's STA | −3.272 | −7.841 | **−10.659** |
| buffers inserted / resized up / pins swapped | 519 / 1,536 / 316 | 102 / 168 / 52 | 147 / 183 / 61 |
| step 37 | −4.1113 | −8.1852 | **−15.1863** |
| step time | 21 m 38.29 s | 9 m 52.82 s | 18 m 50.83 s |

**[fact]**

**It is the same loop, at a third height.** One chase of the worst
endpoint that ends when the path has no improving move — 281
iterations here against 257, and it recovered 14.1 ns from a start
12.5 ns further down — then a run of CLINT registers that cannot be
moved, each tried 51 times and restored, then OpenROAD's no-progress
rule at its first two opportunities. The loop visited 21 endpoints
where `docs/72`'s visited 20, and every one of them is a register of
`u_clint` or the fabric's response from it, as before; the only
difference in the list is which CLINT registers lead it: the eight
`check_raw` bits and the codeword, the time base, where `s71boot`'s
were the response register. **The resizer was handed a different
problem, not a different resizer**: the same rule, the same
give-up, at −10.67 instead of −7.99, because the crossing it could
not repair was moved to a path with four of them and three 300–740 fF
stages on it. On the resizer's own STA the two runs end 2.818 ns apart
(−10.659 against −7.841): **12.513 ns handed, of which 9.695 was
recovered** — the new loop took back 14.114 ns against 4.419, because
it had more to take. Step 37 then reads −15.1863 against −8.1852,
7.001 ns apart: the flow's STA on the re-routed design lands 4.527 ns
below the resizer's final here and 0.344 ns below it in `s71boot`,
which is `docs/72` section 11's caveat about the two analyses, at a
size this document has not decomposed.

---

## 9. Sign-off

`s73clintmgp3`, resumed from `s73clintmgp2`'s own step 07 after the
session's process management killed that flow in its detailed router
(`docs/71`: a resume loses nothing), so one layout in three
directories; `resolved.json` differs from `s71boot`'s in
**`MANUAL_GLOBAL_PLACEMENTS` and `GRT_ALLOW_CONGESTION`** and in no
other key; the fence run's and the union fence's differ in **none**
**[fact]**.

### 9.1 The numbers

| | `s71boot` | `s73clintmgp3` | Δ |
|---|---:|---:|---:|
| `nom_slow_1p08V_125C` setup ws / TNS / endpoints | **−9.1085** / −19,989.82 / 3,361 | **−13.9924** / −24,411.16 / 3,430 | **−4.884** |
| `nom_typ_1p20V_25C` setup ws / endpoints | +1.7820 / 0 | **−2.1708 / 98** | −3.953 |
| `nom_fast_1p32V_m40C` setup ws | +8.0527 | +4.3136 | −3.739 |
| hold ws fast / typ / slow, violations | +0.0621 / +0.2735 / +0.5897, 0 | +0.0775 / +0.2820 / +0.5878, 0 | |
| clock skew, worst setup, slow | 1.796 | 1.6005 | |
| cells excl. fill, um2 | 876,321 | 885,409 | +9,088 |
| timing-repair buffers, um2 | 148,692 | 154,112 | +5,420 |
| standard cells / sequential | 60,868 / 5,873 | 61,778 / 5,873 | +910 / 0 |
| setup buffers, post-GRT resizer | 102 | 147 | |
| routed wirelength, um | 4,248,250 | **5,137,507** | **+20.9 %** |
| longest routed net, um | 2,379.42 | **6,013.30** | |
| detailed-routing DRC | 0 | **0** | |
| `DRT-0349` | ten lines over seven layers (`docs/70` 7) | ten lines over the same seven layers, count for count | 0 |
| max slew violations fast / typ / slow | 1 / 2 / 47 | 9 / 32 / 279 | |
| max cap violations, each corner | 16 | 63 | |
| max-fanout violations (judged by nothing) | 565 | 603 | |
| antenna nets / diodes | 1 / 674 | 4 / 1,093 | |
| disconnected pins / power-grid violations | 0 / 0 | 0 / 0 | |
| `design__violations` on a run that fails setup | 0 | 0 | `docs/23` 3.2, again |
| the flow's deferred-error list | setup at slow; max slew at three corners; max cap | setup at **slow and typ**; max slew at three; max cap | |
| checkers | 17 of 19, exit 1 | **17 of 19, exit 1** | |

**[fact, `signoff_report.py`, `final/metrics.json`, `checker_audit.py`,
the two flow logs]**

The one unit of global-route overflow cost nothing the detailed router
reports: DRC 0, `DRT-0349` unchanged. What the move cost is 4.884 ns
at the slow corner, a typical corner that fails for the first time in
this design's record (98 endpoints at −2.1708 where `s71boot` had
+1.7820), 889,257 um of wire, and a longest net 2.5 times the die's
width.

### 9.2 Where the binding path is now

`violator_census.py`, slow corner, by launch point **[fact]**:

| launch point | `s71boot` (`docs/70` 6.3) | `s73clintmgp3` |
|---|---|---|
| `u_clint.g_mtime_secded.u_mtime_dec.code_in[46]` | — (7 endpoints from `code_in[47]`, worst −0.9355) | **1,147 endpoints, worst −13.9924, TNS −10,085.85** |
| `u_ram…u_b0/A_DOUT[*]` | 1,018 at −6.8564 | 1,137 at −9.7218 |
| `register_file_i.raddr_b_i[0]` / `raddr_a_i[1]` | **1,725 at −9.0480; 392 at −9.1085** (the worst) | 793 at −9.5865 |
| `u_npu.u_node0.u_lif.ev_axon_r[1]` | 218 at −4.4431 | 218 at −4.6010 |

The binding path did not move back to the register file's read
address. It moved into the CLINT's time base — `code_in[46]` →
`check_raw[4]`, the same loop section 7.2 tabulated at step 37, now
1,147 endpoints wide because the corrected `mtime` fans out through
`mtip` and the response register into the core — and the register
file's read, at −9.5865, is 0.48 ns *worse* than `s71boot`'s worst
path while no longer being the worst. Sign-off path, positions from
the final DEF **[fact]**: 78 driver stages, **3 crossings** (one on
the launch clock through the lower pocket, two on the data: `_44266_`
`xnor2_1` in the pocket at (1894.56, 1886.22), and `_45634_` `and2_1`
back into the box), 40 member stages, heaviest `_45633_` `nor2b_2` 247
fF 1.265 ns — the resizer's second global route and the detailed
router shortened section 7.2's 326 fF and 392 fF stages, and the
crossing structure is what it was. `s71boot`'s sign-off path,
`docs/72` 6.4 and section 2: 75 stages, **0** crossings.

### 9.3 Each run, on one line each

| run | what it constrained | worst path | crossings on it | crossings on the register-file read | sign-off, slow |
|---|---|---|---:|---:|---|
| `s71boot`, the baseline | nothing | `raddr_b_i[0]` → `s_rdata_clint[27]`, −8.1852 at step 37 | 2 | 2 | **−9.1085**, 0 at sign-off |
| `s73clint`, fence | 743 cells into a 38,102 um2 box; everything else free | at step 15: `raddr_a_i[0]` → `check_raw[7]`, −3.8923 on placement parasitics | 4 | not measured | **none: did not route**, 420 overflow |
| `s73clintmgp` / `2` / `3`, manual placement | the same 743 cells to the same coordinates; everything else at `s71boot`'s placement | `code_in[42]` → `check_raw[1]`, −15.1863 at step 37; `code_in[46]` → `check_raw[4]` at sign-off | 4 at step 37, 2 + launch clock at sign-off | **4**, at −12.2500 | **−13.9924**, 3,430 endpoints |
| `s73v2fence`, the union fenced, to placement only | 1,830 cells into a 66,561 um2 box | not measured past placement | — | — | none by design |

**[fact]**. Not the best of three: every one of them, and none of them
took the crossing count to zero.

---

## 10. Which prior conclusions survive

| Conclusion | Where | Status after this document |
|---|---|---|
| `docs/48` 5: the placer is not density-constrained on this floorplan, and shrinking the room spreads the logic | `docs/48` 5, `docs/59` 5.2 | **Sharpened**: at 52,286 cells the channel runs at 0.30–0.46 in every 200 um column, and removing 38,102 um2 of it for a fence spread 3,076 cells into the macro gaps and broke global routing, section 5. The floorplan is not a lever and neither is a hole in it |
| `docs/48` 5: the macro placement is HPWL-optimal for these pins | `docs/48` 5 | **Untouched**: no macro moved |
| `docs/72` 6.4: both runs split the CLINT's response register across the upper ROM | `docs/72` 6.4 | **Survives, and is enlarged**: the placer put essentially the whole CLINT — 694 of the 743-cell set, 1,461 of the 1,830-cell union — in the pocket in `s71boot`, and 803 of 886 in the baseline; the register was the part with a name, section 3.3 |
| `docs/72` 8.2: what would fix the binding stage is a placement with the read mux and the response register on the same side of the macro | `docs/72` 8.2 | **Necessary and not sufficient, as measured**: the response register and its mux on one side, with the decode and the mtime decoder on the other, doubles the crossings on the read path and puts a 4-crossing path inside the time base on top, sections 7 and 9. The condition is on the set, not on the register |
| `docs/72` 7.3: the resizer's `LEGACY` phase reaches twenty CLINT endpoints and stops on the no-progress rule | `docs/72` 7.3 | **Reproduced at a third height**: 21 of 3,434 visited, a 281-iteration chase from −24.773 to −10.675, 19 stuck, the rule at 1,200 and 1,300, section 8. The loop is the same; what it is handed is not |
| `docs/71` 6: the flow is deterministic and the resume form loses nothing | `docs/71` 6.1, 6.3 | **Used four times, not re-measured**: every run here is a resume of `s71boot`'s own state, and the two instrumented step re-runs reproduce their steps' metrics in 0 keys |
| `docs/72` 7.1, `docs/31` 3.2: a step's own `config.json` is lossy for the derate | `docs/72` 7.1 | **Reproduced**: both re-runs here needed the same `5 → 5.0` correction before the derate logged `5.0%` |
| `docs/49`: a remedy that relocates the constraint is a different result from one that removes it | `docs/49` | **This document's whole finding**, section 7 |
| `docs/70` 6.3, `docs/72` 7.3: `u_boot` is on none of the violating paths | | **Survives**: `u_boot` is on none of the paths tabulated here |
| `docs/59` 6: the physical database has no hierarchy | `docs/59` 6 | **Survives, with a cost measured**: "the CLINT" had to be derived, the derivation had a defect, and the defect shaped two layouts, section 3.4 |

---

## 11. What this does NOT cover

Stated at length, in the discipline `docs/47` section 9 through `docs/72`
section 11 set. Those lists stand unchanged except where this document
names an item.

- **THIS IS NOT A PHYSICAL SIGN-OFF. THERE IS NO DRC RESULT, NO LVS
  RESULT AND NO XOR RESULT, AND NOTHING HERE MAY BE READ AS THOUGH
  THERE WERE.** `RUN_MAGIC_DRC`, `RUN_KLAYOUT_DRC`, `RUN_KLAYOUT_XOR`
  and `RUN_LVS` are all **0** in `config-ecc.json` and in every copy of
  it here **[fact]**, for the reason `docs/12` sections 7.5 and 8
  measured — a **NO-GO on RM_IHPSG13 for this PDK version** — and
  `docs/54` examined in full. **`Yosys.EQY` is off** and no gate-level
  simulation of `soc_top` exists.
- **THE CONSTRAINED SET IS NOT `u_clint`.** Section 3: it is a set
  derived from net names by a rule, the rule's first implementation
  had a defect, and the two layouts that reached the router moved 743
  cells that are a proper subset of what the rule gives (999) and of
  what the block's register-to-register closure gives (1,830). Nothing
  here measures what moving the whole block does; section 15 item 1
  is that run, not run.
- **ONE BOX, ONE POSITION.** The region was drawn once, where the
  set's channel-side partners were. A box lower in the channel, a
  wider one, or one that also holds the decode was not tried; `docs/48`'s
  one-probe rule and the coordinator's bound of 2026-09-06 both
  applied, and the runs that were made answered the question they were
  asked.
- **THE FENCE RUN HAS NO TIMING PAST STEP 15.** Its post-CTS-repair
  figures are on placement parasitics; its global route did not
  finish; no resizer or sign-off figure exists for it and none is
  implied.
- **ONE UNIT OF GLOBAL-ROUTE OVERFLOW WAS CARRIED THROUGH**, section
  6.3, under a flag that the source shows gates only the message. What
  the detailed router made of it is in section 9's DRC count and
  nowhere else.
- **THE CONGESTION LOCATION IS FROM A SCRATCH ROUTE**, section 6.2,
  that reproduces the flow's route to 0.08 % in wirelength and 2
  against 1 in overflow; it is quoted for where, not for how much.
- **NO FREQUENCY.** `docs/53` section 9.2's three grounds bind and
  nothing here moves them; slack against **20 ns** is what is reported.
- **THE RESIZER'S OWN STA IS NOT THE FLOW'S STA**, `docs/72` section
  11's caveat: iteration-0 and final figures in section 8 are over
  `PNR_CORNERS` on the resizer's incremental parasitics, step 37 and
  sign-off are LibreLane's reports, and none are mixed in one
  subtraction.
- **THE FROM/TO QUERY OF SECTION 7.3 IS ON GLOBAL-ROUTE PARASITICS**,
  the step-37 view; it was not repeated at sign-off.
- **NO WALL-CLOCK FIGURE IS A WALL-CLOCK FIGURE.** Step timers are the
  flow's own `runtime.txt`; the machine carried one unrelated process
  throughout, and for part of the night three layouts, two
  instrumented steps and a scratch route at once. One flow was killed
  mid-router by the session's own process management and resumed from
  its own step 07, section 9, which by `docs/71` costs nothing but is
  named.
- **ONE NETLIST, ONE FLOORPLAN, ONE MACHINE, ONE BINARY**, and the
  fast corner's macro Liberty is still at −55 C, `docs/12` 6.4a.
- **NO BEHAVIOURAL EVIDENCE WAS ADDED AND NONE WAS NEEDED.** No RTL was
  modified.

---

## 12. Corrections to earlier documents

Every one is a dated in-place note in the corrected file, by `docs/64`
section 2's rule; every original sentence stands.

- **`docs/72` section 15 item 1**: closed, with the result in one
  sentence — the crossing relocates to the boundary of whatever set is
  constrained; a fence in this channel does not route; the flow's own
  `MANUAL_GLOBAL_PLACEMENTS` is the form that does.
- **`docs/72` section 8.2**'s *"what would fix it is a placement in
  which the CLINT's read mux and its response register are on the same
  side of the ROM macro"*: a note that this was tried, that the
  condition is necessary and not sufficient, and where the crossing
  went.
- **`docs/00-index.md`**: one row, which `sw/tests/test_doc_links.py`
  requires.

---

## 13. Files touched

| file | change |
|---|---|
| `docs/73-clint-placement-probe.md` | this document |
| `docs/00-index.md` | one row |
| `docs/72-post-grt-resizer.md` | dated notes: section 8.2, section 15 item 1 |
| `hw/soc/pnr/clint_region.py` | **new**: `members`, `apply`, `placement`, `config`, `census`, `path` — section 3, 4 and 7's instrument; the LEF parse anchored after section 3.4's defect |
| `hw/soc/pnr/clint_placement.json` | **new, tracked**: the 743 coordinates the two routed layouts used (the defective set, at the fence run's step-11 positions) |
| `hw/soc/pnr/clint_placement_v2.json` | **new, tracked**: the 1,830 coordinates of the union set at the union fence's step-11 positions, for the layout section 15 item 1 names and this document did not run |
| `.gitignore` | `hw/soc/pnr/config-ecc-clint*.json`, the generated configuration variants, regenerable from the two files above |

**`config-ecc.json` is not modified. No RTL, no flow script, no test.**
`hw/soc/pnr/runs/s73clint-pre/` (the edited databases, states and the
three member lists), `runs/s73clint`, `runs/s73clintmgp`,
`runs/s73clintmgp2`, `runs/s73clintmgp3` and `runs/s73v2fence` are run
directories and gitignored; the instrumented step re-runs, the scratch
route and the STA queries live in this session's scratch directory and
are not part of the repository. `runs/s71boot`, `runs/s70base` and
their states were read and not written.

**Nothing in `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is
modified and `hw/tb/Makefile.fi` was not invoked. `docs/34`'s freeze is
untouched.**

The Python suite: **455 passed, 0 failed** **[fact, `.venv/bin/python -m pytest sw/tests -q`, 4 m 23 s]** — `docs/72` section 13 reports 454 with that document present, and `sw/tests/test_doc_links.py` discovers the corpus, so this document adds exactly one test; `test_doc_links.py` alone: 86 passed.

---

## 14. Reproducing this

```
# 0. the instruments, before anything is claimed to move (section 2)
V=$HOME/Documents/caravel-lif-crossbar/.venv-flow/bin/python
export PATH=$HOME/.local/opt/llbin:$PATH PDK_ROOT=$HOME/.ciel
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/s71boot            # -9.1085 / 3361
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/s71boot; echo $?   # 17 of 19, 1
md5sum hw/soc/out/s70-rom0-syn/soc_top.netlist.v                     # a8d5ef81...
python3 hw/soc/pnr/clint_region.py census \
  hw/soc/pnr/runs/s71boot/26-openroad-detailedplacement/soc_top.def  # 45,619 / 2,222 / 3,568 / 441 / 436
python3 hw/soc/pnr/clint_region.py path \
  hw/soc/pnr/runs/s71boot/37-openroad-stamidpnr-3/max.rpt \
  hw/soc/pnr/runs/s71boot/36-openroad-resizertimingpostgrt/soc_top.def  # 90 stages, 2 crossings

# 1. the set (section 3): the fixed tool gives 999; the runs used 743
python3 hw/soc/pnr/clint_region.py members hw/soc/out/s70-rom0-syn/soc_top.netlist.v \
  --write /some/scratch/members.json                                  # 999 cells, 17552.5056 um2
#    the defective 743-cell list is hw/soc/pnr/runs/s73clint-pre/clint_members.json;
#    to regenerate it, replace the anchored LEF regex with the unanchored one
#    section 3.4 names -- or take the 743 instance names from clint_placement.json

# 2. the fence form (sections 4.2 and 5)
P=hw/soc/pnr/runs/s73clint-pre
openroad -exit -no_splash -python hw/soc/pnr/clint_region.py apply \
  --odb-in hw/soc/pnr/runs/s71boot/13-openroad-generatepdn/soc_top.odb \
  --members $P/clint_members.json --box 1780.32 1217.16 2020.32 1375.92 \
  --odb-out $P/soc_top.odb --def-out $P/soc_top.def \
  --state-in hw/soc/pnr/runs/s71boot/15-odb-addroutingobstructions/state_out.json \
  --state-out $P/state_in.json                                        # 743 instances, util 0.3998
diff hw/soc/pnr/runs/s71boot/13-openroad-generatepdn/soc_top.def $P/soc_top.def | grep -c '^[<>]'   # 191
SYN_NETLIST=$PWD/hw/soc/out/s70-rom0-syn/soc_top.netlist.v \
PNR_CONFIG=$PWD/hw/soc/pnr/config-ecc.json PNR_STATE=$PWD/hw/soc/pnr/state/s73clint.state.json \
hw/soc/flow/pnr_soc_top.sh s73clint --overwrite -F OpenROAD.GlobalPlacementSkipIO \
  -i $PWD/$P/state_in.json                                            # stops at GRT-0116, overflow 420

# 3. the manual-placement form (sections 4.3, 6 to 9)
python3 hw/soc/pnr/clint_region.py placement \
  hw/soc/pnr/runs/s73clint/11-openroad-detailedplacement/soc_top.def \
  --members $P/clint_members.json --write hw/soc/pnr/clint_placement.json
python3 hw/soc/pnr/clint_region.py config --base hw/soc/pnr/config-ecc.json \
  --placements hw/soc/pnr/clint_placement.json --write hw/soc/pnr/config-ecc-clint.json
SYN_NETLIST=... PNR_CONFIG=$PWD/hw/soc/pnr/config-ecc-clint.json PNR_STATE=.../s73clintmgp.state.json \
hw/soc/flow/pnr_soc_top.sh s73clintmgp --overwrite -F Odb.ManualGlobalPlacement \
  -i $PWD/hw/soc/pnr/runs/s71boot/24-openroad-repairdesignpostgpl/state_out.json   # stops at GRT-0116, overflow 1
SYN_NETLIST=... PNR_CONFIG=$PWD/hw/soc/pnr/config-ecc-clint.json PNR_STATE=.../s73clintmgp2.state.json \
hw/soc/flow/pnr_soc_top.sh s73clintmgp2 --overwrite -F OpenROAD.GlobalRouting \
  -i $PWD/hw/soc/pnr/runs/s73clintmgp/06-openroad-stamidpnr-2/state_out.json -c GRT_ALLOW_CONGESTION=1
#    (this session's s73clintmgp2 was killed in its detailed router by the session's
#     own process management and resumed as s73clintmgp3 from its own step 07:)
SYN_NETLIST=... PNR_CONFIG=$PWD/hw/soc/pnr/config-ecc-clint.json PNR_STATE=.../s73clintmgp3.state.json \
hw/soc/flow/pnr_soc_top.sh s73clintmgp3 --overwrite -F OpenROAD.DetailedRouting \
  -i $PWD/hw/soc/pnr/runs/s73clintmgp2/07-openroad-stamidpnr-3/state_out.json -c GRT_ALLOW_CONGESTION=1

# 4. the reports
python3 hw/soc/pnr/clint_region.py census hw/soc/pnr/runs/s73clintmgp/02-openroad-detailedplacement/soc_top.def --members $P/clint_members.json
python3 hw/soc/pnr/clint_region.py path hw/soc/pnr/runs/s73clintmgp2/07-openroad-stamidpnr-3/max.rpt \
  hw/soc/pnr/runs/s73clintmgp2/06-openroad-resizertimingpostgrt/soc_top.def --members $P/clint_members.json
grep -E '^ +[0-9]+[*+] \||^ *final' hw/soc/pnr/runs/s73clintmgp2/06-*/openroad-resizertimingpostgrt.log | awk -F'|' 'NF>=12'
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/s73clintmgp3
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/s73clintmgp3; echo $?
python3 -c "
import json
a=json.load(open('hw/soc/pnr/runs/s71boot/resolved.json'))
for r in ['s73clint','s73clintmgp','s73clintmgp3']:
  b=json.load(open(f'hw/soc/pnr/runs/{r}/resolved.json'))
  print(r, sorted(k for k in set(a)|set(b) if a.get(k)!=b.get(k)))"

# 5. the instrumented resizer step and the from/to query: docs/72 section 14 step 3's
#    form -- a copy of rsz_timing_postgrt.tcl with report_wns/report_tns/report_checks
#    before and after the setup repair_timing and `set_debug_level RSZ repair_setup 2`,
#    a copy of the step's config.json with TIME_DERATING_CONSTRAINT 5 -> 5.0 and
#    OUTPUT_CAP_LOAD 6 -> 6.0, and librelane.steps run with the step class's
#    get_script_path redirected; for the query, sta/corner.tcl with a
#    `report_checks -from {raddr flops} -to {s_rdata_clint D pins}` appended and
#    OpenROAD.STAMidPNR redirected the same way, on 37-.../state_in.json of each run.

# 6. the union set, to detailed placement only (sections 3.4 and 5.4)
python3 hw/soc/pnr/clint_region.py members hw/soc/out/s70-rom0-syn/soc_top.netlist.v --write $P/clint_members_corrected.json
#    the closure union of section 3.4 is the members list in $P/clint_members_v2.json,
#    whose 1,830 names are also the keys of hw/soc/pnr/clint_placement_v2.json
openroad -exit -no_splash -python hw/soc/pnr/clint_region.py apply --odb-in ... \
  --members $P/clint_members_v2.json --box 1740.00 1168.02 2060.16 1375.92 ...        # util 0.3946
hw/soc/flow/pnr_soc_top.sh s73v2fence --overwrite -F OpenROAD.GlobalPlacementSkipIO \
  -T OpenROAD.DetailedPlacement -i $PWD/$P/v2/state_in.json
python3 hw/soc/pnr/clint_region.py placement hw/soc/pnr/runs/s73v2fence/11-*/soc_top.def \
  --members $P/clint_members_v2.json --write hw/soc/pnr/clint_placement_v2.json
python3 hw/soc/pnr/clint_region.py config --base hw/soc/pnr/config-ecc.json \
  --placements hw/soc/pnr/clint_placement_v2.json --write hw/soc/pnr/config-ecc-clint2.json   # ready, not run

# 7. the guards
.venv/bin/python -m pytest sw/tests/test_doc_links.py -q
.venv/bin/python -m pytest sw/tests -q
```

**The step timers**, the flow's own `runtime.txt` and not wall-clock:

| | fence `s73clint` | `s73clintmgp` (01–06) | `s73clintmgp2` (01–07) | `s73clintmgp3` (01–25) | `s71boot`, the same steps |
|---|---:|---:|---:|---:|---:|
| global placement, skip-IO / full | 11.26 s / 25.39 s | — | — | — | 11.75 s / 37.04 s |
| detailed placement | 2.51 s | 2.41 s | — | — | (0 displacement) |
| CTS / post-CTS resizer | | 29.02 s / 9 m 23.25 s | — | — | |
| global routing | no `runtime.txt`; about 33 min by the flow log | — (4 m 37.79 s by process stats) | 5 m 09.51 s | — | 16.06 s |
| `RepairDesignPostGRT` | — | — | 13 m 11.52 s | — | |
| post-GRT resizer | — | — | **18 m 50.83 s** | — | 9 m 52.82 s |
| detailed routing | — | — | killed | **3 h 19 m 13.46 s**, beside two instrumented steps, a scratch route and the union fence | 36 m 19.54 s alone |
| `STAPostPNR` | — | — | — | 1 m 09.43 s | |

**[fact]**. The detailed-routing figure is the loudest illustration
yet of `docs/71` section 14's point: the same router, the same
threads, a layout 21 % longer in wire, and 5.5 times the step time
because the machine was carrying four other jobs. No figure in this
table is a measurement of the flow.

---

## 15. What the next block should be

1. **Move the whole cluster, once, and only if this sentence is
   accepted as the question.** Every layout here moved a set that
   cut through the cluster the placer had co-placed in the pocket, and
   every one relocated the crossing to the cut. The one thing they
   leave unanswered, and the only thing a further layout would answer,
   is whether a set that captures the response registers **together
   with** their decode and the mtime decoder — the 1,830-cell union of
   section 3.4, four fifths of which the placer had already put in the
   pocket as one cluster — removes the crossing rather than moving it.
   The set is derived, its placer-chosen coordinates are in
   `hw/soc/pnr/clint_placement_v2.json`, its configuration is
   `config-ecc-clint2.json`, and the command is section 14 step 3 with
   that file. It is one run of the form that routes, from `s71boot`'s
   own step 24. **[planned]** It was not run here under the bound of
   2026-09-06, and it should not be run as "the next variant" — only
   as the answer to that sentence, with the crossing count on the
   register-file read *and* on the mtime loop as its two metrics.
2. **The condition, stated as a condition.** What the three layouts
   establish is not a placement recipe but a requirement: the CLINT's
   response registers, the fabric decode that selects them, and the
   time base that feeds them have to be on one side of the ROM, and
   any constraint that draws a line through that set puts the line's
   nets over the macro. A floorplan in which the pocket does not exist
   — `docs/48`'s FP-B put the ROMs in the channel and was worse for
   other reasons — or a channel with room for the cluster is what
   satisfies it; a fence does not, section 5.
3. **`docs/72` section 15 item 5 is the structural answer and it is
   unchanged**: the one-cycle bus read puts the register file's read
   address, the ALU, the fabric mux, the CLINT decode and the response
   register in one period. A registered request phase would take the
   decode off the read path and make the pocket a latency question
   instead of a slack one. Not priced here.
4. **`docs/50`'s read register and `docs/69`'s strap window**,
   `docs/72` section 15 items 2 and 3, unchanged and still unblocked.
5. **Guard the step-rerun form**, `docs/72` section 15 item 4: two more
   re-runs here needed the same by-hand `5 → 5.0` correction. ~~The
   guard is still owed.~~ **DONE 2026-09-12**,
   `sw/tests/test_derate_is_a_float.py`. This document's two re-runs are
   the second and third evidence for it; `docs/72` section 15 item 4
   carries what the guard does and what it deliberately does not.
6. **The remaining items of `docs/68` section 16 and `docs/71` section
   15 are unchanged.**
