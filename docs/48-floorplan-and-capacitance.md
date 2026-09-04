# 48 — Three floorplans, and the constraint nobody set

`docs/47-soc-place-and-route.md` section 8.4 ends with a sentence this
document exists to test:

> **"43.10 MHz is the frequency of this design IN THIS FLOORPLAN, not of
> this design."**

It is a hypothesis with three pieces of evidence and no control, and
`docs/47` labels it as one. This document runs the control. **Two more
floorplans were built and measured against the first, and both are
worse** — and while measuring them a fourth thing turned up that nobody
had looked at, which is where the time actually is.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
intended, with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by blob hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was modified;
`hw/openlane/checker_audit.py` and `hw/openlane/signoff_report.py` are
**read and run** and never written. Section 12 lists every file.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Was the floorplan the problem?** | **No, and this is the clearest negative result in the SoC record.** Two more floorplans were built and hardened — one sized to the netlist actually hardened, as `docs/47` section 11 item 3 asked for; one with the die 19.8 % narrower and the ROMs moved out of the macro rows, against `docs/47`'s own complaint that "a strip is a bad shape for timing". **Both are worse.** At post-CTS: **−10.7556** for `docs/47`'s, **−11.5970** and **−12.4536** for the two new ones. After global routing the narrow one is **−16.9653 against −6.8764**, on **44.1 % more global-route wirelength**; **the tight one's global router did not terminate in 33 minutes against 8.033 seconds**, twice. Sections 4 and 5 |
| **So does it close?** | **No. Nothing in this document closes, and nothing in it beats 43.10 MHz.** The best sign-off number here is `docs/47`'s own. Sections 5, 7 and 7a |
| Two of the three leads this document was given were already spent | **`SYNTH_HIERARCHY_MODE: deferred_flatten` and both `RUN_POST_GRT_*` keys are already inside `docs/47`'s 43.10 MHz**, and the run directories say so without ambiguity: `full2` hardens `syn_soc_top.sh`'s netlist with `Yosys.Synthesis` skipped, and `full3` — the run that produced −3.2029 — has both post-GRT keys `True`. **Their remaining value is 0 ns each.** And the pilot's stated reason for `deferred_flatten` **does apply** to this design, which is why `docs/47` needed a third option rather than a switch. Section 3 |
| **A fourth lead, found while measuring the third** | **The library's `default_max_capacitance` is 0.3 pF, and at 0.3 pF a single `sg13g2_o21ai_1` costs 3.395 ns at the slow corner** — 17.0 % of a 20 ns period, on one gate **[fact, the vendor's own `cell_rise` table]**. `MAX_CAPACITANCE_CONSTRAINT` is `Optional` in LibreLane, **neither PDK ships a value**, and every signed-off SDC in this repository therefore contains **no `set_max_capacitance` at all**. The binding path carries **six stages of 62 to 202 fF on cells the library ships in exactly one drive strength**. Section 6 |
| And tightening it? | **Measured to sign-off, and it is worth −1.65 ns.** It is worth **+3.4722 ns** before the timing resizer runs and loses all of it back, because `repair_design` buffers **4,163 nets** rather than six and leaves `repair_timing` no room. **But it closes hold and it closes max slew** — `docs/47`'s −0.2015 ns on 3 fast-corner endpoints becomes **+0.0494 on 0**, and its max-slew violations — 14 at the slow corner, 1 at the fast — become **0 at all three** — through checkers still bound to all three corners. Sections 7 and 9 |
| Do the checkers still gate? | **17 of 19, the same as `docs/47`, on the run that reports the improved hold and slew.** `checker_audit.py` confirms `Checker.HoldViolations` and `Checker.MaxSlewViolations` each examined three corners before reporting `all 0`. Section 9 |
| What changed in the design? | **Nothing. No RTL file was modified.** Section 12 |

---

## 2. Reproducing the instrument, eight ways, before moving it

`docs/44` section 5.2 set the rule, `docs/45` section 4 and `docs/47`
section 3 followed it. Everything below is re-measured in this session
against `docs/47`'s published figures.

| What | `docs/47` | Measured here |
|---|---|---|
| `SOC_MEM=sram` whole design | 6.3: **27,565 cells, 3,085 flip-flops, 396,177.6420 um2** | **27,565 / 3,085 / 396,177.6420**, and `soc_top.netlist.v` is **byte-identical** to the netlist `full2` hardened **[fact, `diff`]** |
| pre-layout three-corner setup | 6.3: **−26.3108 / −49.2780 / −11.1090** | **every figure, digit for digit** |
| pre-layout three-corner hold | 5.3: **−0.1875 / −0.1144 / −0.2475** | **every figure** |
| pre-layout `setup_sync`, slow | 5.3: **+3.8711** | **+3.8711** |
| standard-cell placement span | 8.4: **1,851.8 × 790.0 um** over **27,558** cells | **1,851.8 × 790.0** over **27,558**, at origin (388.8, 582.1) |
| sign-off, slow corner | 8.2: **−3.2029 ns on 2,003 endpoints, 43.10 MHz** | **−3.2029 / 2,003**, `hw/openlane/signoff_report.py` |
| checker audit | 7.3: **17 of 19 in-flow checkers gate fully** | **17 of 19**, exit 0 |
| summed step runtime, `full2` | 8.6: **22.2 min** | **22.2 min** |

**[fact for every row]**

**One number in `docs/47` does not reproduce as a reader would compute
it, and it is worth a line because it is the document's own headline
caveat.** The 1,851.8 × 790.0 um strip is the span of the **27,558 cells
that exist in the synthesised netlist**. Counting every placed
standard cell — the repair buffers, the clock buffers, the tap and
endcap cells — the span at the same step is **2,184.5 × 1,345.7 um**
**[fact]**. Both numbers are true and `docs/47`'s is the one it says it
is measuring; this is recorded so that a reader who recomputes it and
gets a different answer knows why.

---

## 3. Two of the three leads were already spent

This document was asked to test three leads. **Two of them are already
inside `docs/47`'s 43.10 MHz**, and the run directories say so without
ambiguity. This section is short because the measurement is a file read,
and it is here because the alternative — measuring them again and
reporting a delta of zero — would have cost two runs and taught nobody
anything.

### 3.1 `SYNTH_HIERARCHY_MODE: deferred_flatten` was already removed

`hw/openlane/pilot_sky130/config.json` carries the reason the pilot
needs it, in the file:

> The three configuration TMR replicas are `keep_hierarchy` instances,
> so a plain flatten leaves `$paramod` module types that
> `Checker.YosysUnmappedCells` counts as unmapped instances and aborts
> on. `deferred_flatten` keeps the hierarchy through synthesis and
> flattens after mapping.

**That reason applies to this design too**, and `docs/47` section 6.2
says so in the same terms about a different module: `hw/soc/rtl/soc_tmr_bank.v`
carries `keep_hierarchy` as one of `docs/41`'s two anti-merge defences,
LibreLane cannot release the attribute after technology mapping, and
`flatten` therefore stops at `Checker.YosysUnmappedCells` with three
`soc_tmr_bank` submodules standing.

**So the 13.84 ns is not free, and `docs/47` did not take it with a
switch — it took it with the third option.** `hw/soc/flow/syn_soc_top.sh`
holds `keep_hierarchy` through optimisation and `abc` and releases it
before the final flatten, and `hw/soc/flow/pnr_soc_top.sh` hands
LibreLane that netlist as an initial state. The evidence, in the run
directory rather than in the document:

```
hw/soc/pnr/runs/full2/01-yosys-jsonheader/state_in.json
    "nl": ".../hw/soc/out/s47-sram/soc_top.netlist.v"
hw/soc/pnr/runs/full2/  -- first step is 01-yosys-jsonheader;
                           there is no Yosys.Synthesis step
```

**[fact]**. `SYNTH_HIERARCHY_MODE` in `resolved.json` reads `"flatten"`
and is **inert**, because the step it configures does not run.
`hw/soc/pnr/config.json`'s own `"//hierarchy"` note is 1,400 words
saying exactly this.

> **The lead is real, the 13.84 ns is real, and it was already spent
> before the number 43.10 MHz existed.** `+3.8711 ns` — the pre-layout
> synchronous slack of the netlist that was hardened — is the
> `syn_soc_top.sh` number, not the `deferred_flatten` one of −9.9731.

### 3.2 Both post-GRT stages were already on

| Run | `RUN_POST_GRT_DESIGN_REPAIR` | `RUN_POST_GRT_RESIZER_TIMING` | what it produced |
|---|---|---|---|
| `full2` | **False** | **False** | netlist → post-CTS repair → global routing → detailed routing |
| `full3` | **True** | **True** | resumed from `full2`'s post-CTS state; **produced −3.2029 ns and 43.10 MHz** |

**[fact, the two `resolved.json` files and `full3/01-openroad-globalrouting/state_in.json`,
which names `full2/29-openroad-resizertimingpostcts/`]**

`hw/soc/pnr/config.json` sets both to 1 and carries the measurement
behind it. **The 4.30 ns is inside 43.10 MHz already**; `docs/47`
section 8.5's table is the attribution and this document adds nothing to
it.

> **Both leads are correctly identified and both are already banked.
> The remaining value of leads 2 and 3, measured against `docs/47`'s
> headline number, is ZERO ns each** **[fact, from the configuration of
> the run that produced the number]**. What this document could still
> add is whether the 4.30 ns survives a different floorplan, and section
> 7 answers that for the configuration that reached sign-off.

---

## 4. The floorplan generator

Three floorplans are compared below, and the comparison is only worth
anything if they differ in the floorplan and in nothing else.
`hw/soc/pnr/floorplan.py` is what makes that true.

- **The macro dimensions are read, not typed.** `784.48 × 626.70` and
  `416.64 × 336.46` come from the installed PDK's LEF `SIZE` statements
  **[fact]**.
- **Site alignment is asserted, not arranged.** `docs/47` section 6.1
  established that the core box is an integer number of 0.48 um sites
  and 3.78 um rows and every macro origin likewise; the generator
  refuses to emit a floorplan that has lost it, and quantises the
  channel height to the admissible `0.78 + 3.78k`.
- **It changes four keys and asserts that it changed four keys** —
  `DIE_AREA`, `CORE_AREA`, the six macro *locations* inside `MACROS`,
  and `PL_TARGET_DENSITY_PCT` — the same shape of assertion
  `flow/pnr_soc_top.sh` already makes about `VERILOG_FILES`. Every
  checker binding of `config.json` section 7 is carried across
  unchanged.

> **And the self-check is the strongest one available: at
> `--channel 700.08 --density 40` the generator emits
> `hw/soc/pnr/config.json` BYTE FOR BYTE**, die, core box, six macro
> origins and two orientations, computed from the LEF without being told
> what they should come out as **[fact; `test_the_floorplan_generator_reproduces_the_hardened_floorplan`]**.

**Why a generator and not a second hand-edited config**, which is a
finding about the tool rather than a preference: LibreLane's
`-c KEY=VALUE` inserts the value as a **string** and re-parses it with
permissive typing, so `-c DIE_AREA=[0, 0, 2306.4, 1685.88]` is split on
its commas and the first element arrives as the Decimal `'[0'`; `MACROS`
is a dictionary of `Macro` objects and cannot be passed at all **[fact,
`librelane/config/config.py` and the error]**. A floorplan variant is
therefore a whole configuration file. `flow/pnr_soc_top.sh` gained one
environment variable, `PNR_CONFIG`, and a refusal: the variant must live
under `hw/soc/pnr/`, because the refusal that keeps this script out of
the frozen `hw/openlane/` is a check on the config directory and an
arbitrary path would walk around it.

### 4.1 The three floorplans

| | **FP-0**, `docs/47` | **FP-A**, tight channel | **FP-B**, islands |
|---|---|---|---|
| arrangement | two rows of **RAM, RAM, ROM**, pin edges facing a central channel | the same | **two RAM columns**; the two ROMs are **islands inside the channel** |
| channel height | **700.08 um** (185 rows) | **310.74 um** (82 rows) | **775.68 um** (205 rows) |
| die | **2306.40 × 2075.22** = **4.7863 mm2** | **2306.40 × 1685.88** = **3.8883 mm2** | **1850.40 × 2150.82** = **3.9799 mm2** |
| core | 2186.40 × 1984.50, 525 rows | 2186.40 × 1595.16, 422 rows | 1730.40 × 2060.10, 545 rows |
| placeable (core − macro) | **2,092,010.95 um2** | **1,240,757.97 um2** | **1,317,897.19 um2** |
| standard cells / placeable | **18.94 %** | **31.93 %** | **30.06 %** |
| `PL_TARGET_DENSITY_PCT` | 40 | 55 | 50 |

**[fact for every geometric figure; the two densities are arithmetic on
a measured cell area]**

**FP-A is the experiment `docs/47` section 11 item 3 asked for**, in its
own words: "the channel sized to the netlist that is actually hardened
rather than to the one that is not". `docs/47` section 6.1 sized the
channel against LibreLane's own synthesis of the same RTL, which is
32.3 % larger; FP-A sizes it against `syn_soc_top.sh`'s.

**FP-B is the answer to the other half of `docs/47`'s complaint**, that
"a strip is a bad shape for timing". The strip is 2,186.40 um wide
because three macros stand side by side, and the only way to narrow it
without rotating a hard macro — which this repository cannot check,
because `docs/12` section 7.5 records DRC on RM_IHPSG13 as a NO-GO — is
to take the ROMs out of the rows. FP-B puts them in the channel with
**220.02 um of clear standard-cell area below each and 219.20 um above**,
orientation `N` so their pin edge faces down into the channel exactly as
the upper RAM row's does. **The die is 19.8 % narrower and 16.8 %
smaller in area.**

Both floorplan variants **passed** floorplan initialisation, macro
placement, row cutting, tap and endcap insertion and PDN generation with
`Checker.PowerGridViolations` clear **[fact]**. Neither is an
ill-formed floorplan; they are well-formed floorplans that are worse.

---

## 5. Both new floorplans are worse, at every stage that was measured

Worst setup slack in ns at `nom_slow_1p08V_125C`, 20 ns period, 5 %
derate applied as a float, at the four points the flow reports one
before detailed routing. All three runs use the identical netlist, the
identical constraint file and the identical checker bindings; **the
post-GRT stages are OFF in all three**, so this table is a comparison of
floorplans and of nothing else.

| | **FP-0** | **FP-A** | **FP-B** |
|---|---:|---:|---:|
| global-placement HPWL, um | **2.100780e+06** | **2.342133e+06** | **2.441221e+06** |
| standard-cell span, global placement | **1849.3 × 792.2 um** | 2179.6 × 1261.6 | 1724.9 × 1928.4 |
| cells / their own bounding box | **27.0 %** | **14.4 %** | **11.9 %** |
| CTS average sink wire length, `u_ibex.clk` (2,323 sinks) | **996.17 um** | 1237.71 | 1089.75 |
| CTS average sink wire length, `clk_i_regs` (762 sinks) | **778.10 um** | 876.27 | **681.98** |
| CTS average sink wire length, macro `clk_i` (7 sinks) | 2643.87 um | 2329.76 | **2124.22** |
| **post-CTS, before the timing resizer** | **−10.7556** | **−11.5970** | **−12.4536** |
| **post-CTS resizer, placement parasitics** | **−0.1577** | −0.3737 | −0.0934 |
| global-routing runtime | **8.033 s** | **did not complete** | **4 min 47.661 s** |
| global-route wirelength | **3,771,252 um** | — | **5,433,782 um** |
| **after global routing, real parasitics, no post-GRT repair** | **−6.8764** | — | **−16.9653** |

**[fact]**

**Two cells in that table are not numbers and both are results.**

**FP-A's global routing did not complete.** `OpenROAD.GlobalRouting`
took **8.033 s** on FP-0 and **had not produced a single line of log
after 33 minutes** on FP-A, at 87 % of one core and 890 MB, on two
independent attempts — the original run and a resume from its own
post-CTS state **[fact, `runtime.txt` for FP-0 and `ps` and a
zero-length `openroad-globalrouting.log` for FP-A; both FP-A attempts
were terminated rather than failing on their own]**. A channel of 82
rows carrying 1,084 macro pins and 31,777 standard cells is not a
floorplan the global router can solve in the time the other two take,
and **that, rather than its post-CTS slack, is the finding about FP-A.**

**FP-B routed, and the reason it is 10.09 ns worse than FP-0 is in the
row above the slack.** Global routing takes **36 times longer** and
lays down **5,433,782 um of wire against 3,771,252 — 44.1 % more, on
36,423 nets against 36,494** **[fact, `GRT-0018` and `GRT-0014`]**.
Narrowing the die from 2,306.40 to 1,850.40 um did not shorten the
wires; it made the router go around things.

> **1. SHRINKING THE DIE DID NOT COMPACT THE LOGIC. IT SPREAD IT.**
> In FP-0 the 27,558 synthesised cells occupy **27.0 %** of their own
> bounding box; in FP-A **14.4 %** and in FP-B **11.9 %** **[estimate,
> arithmetic on measured spans]**. That is the opposite of the intended
> effect and the mechanism is visible in the placement: **in FP-A,
> 7,857 of the 27,558 cells are in the two ROM pockets at the far right
> of the die and 1,057 more are in the 60.48 um strip beside them,
> against 739 and 12 in FP-0** **[fact, counting placed instances by
> region in the two DEFs]**.
>
> The channel in FP-A holds 679,382 um2 and the design's cells,
> **after** `RepairDesignPostGPL` has inserted its buffers, are 531,371
> um2 in FP-0's netlist — 78 % of it. The placer cannot fit them, so it
> exiles a third of the design into the two pockets that the shorter
> ROM macros leave, which are **at the opposite end of a 2,186.40 um core from the
> RAM macros most of that logic talks to**. FP-0's 18.9 % is not slack the placer was
> wasting; it is the room the placer needs.

> **2. THE PLACER WAS NEVER DENSITY-CONSTRAINED IN FP-0, AND THAT IS
> WHY THE SIZING LEVER DOES NOT EXIST.** `PL_TARGET_DENSITY_PCT` was 40
> against a standard-cell utilization of 18.9 %, so the density penalty
> in global placement never bound and the placement FP-0 produced is
> the HPWL-optimal one for these macro pin positions. Making the box
> smaller cannot improve an unconstrained optimum; it can only remove
> feasible solutions, and the HPWL numbers say it removed good ones —
> **+11.5 % in FP-A and +16.2 % in FP-B** **[estimate, differences of
> measurements]**.

> **3. THE STRIP IS NOT WHAT COSTS THE TIME, AND FP-B IS THE CONTROL
> THAT SAYS SO.** FP-B narrows the standard-cell region from 2,186.40 to
> 1,730.40 um and improves two of the three clock nets' average sink
> wire length — `clk_i_regs` **778.10 → 681.98 um** and the macro clock
> **2643.87 → 2124.22** — and it is still **1.70 ns WORSE at post-CTS**
> **[fact]**. A narrower die is a better clock tree and a worse
> placement, and the placement is what the datapath rides on.

> **4. AND THE ONE PIECE OF EVIDENCE `docs/47` LEANED ON HARDEST POINTS
> THE WRONG WAY.** `docs/47` section 8.4 offers the 2,332.02 um longest
> net as "the sharpest piece of evidence" for the floorplan hypothesis.
> It is a **routed** length in a die whose diagonal is 3.1 mm, and the
> floorplan that shrinks that die by 16.8 % **increases total
> global-route wirelength by 44.1 %**. A long net in a big die is a
> description of the die, not a diagnosis.

### 5.1 The answer to `docs/47`'s closing sentence

> **"43.10 MHz is the frequency of this design IN THIS FLOORPLAN, not of
> this design"** is **not supported**. Two floorplans — one built to
> `docs/47`'s own specification for the experiment, one built against
> its own complaint about the strip — are worse by **0.84 ns** and
> **1.70 ns** at post-CTS, and the one of them that routes is worse by
> **10.09 ns** after global routing. **43.10 MHz is closer to being the
> frequency of this design than that sentence allows**, and the caveat
> should be narrowed rather than repeated. Section 10.

---

## 6. A limit the library sets and the flow never tightens

**Read this section as the hypothesis it was.** Section 5 rules the
floorplan out, so the next question is where the 7.07 ns is, and
resolving the critical path against the netlist and the Liberty
produces a candidate that is specific, measurable and — section 7 —
wrong. It is written out in full because the observation about the
library is true and useful whatever the fix turns out to be, and
because a lead that was pursued and failed is worth more on the record
than a lead that was not written down.

### 6.1 The path, resolved

`hw/soc/pnr/runs/full3/19-openroad-stapostpnr/nom_slow_1p08V_125C/violator_list.rpt`
carries all 2,003 violating endpoints and they have **four launch points
between them** **[fact]**:

| Launch flip-flop | Resolved against the netlist | Endpoints | Worst slack |
|---|---|---:|---:|
| `u_ram.g_ram_2048x64.u_b0` | the RAM macro's `A_DOUT` | **444** | **−3.2029** |
| `_49705_` | `u_ibex...register_file_i.raddr_a_i[2]` | 868 | −2.0227 |
| `_49703_` | `...raddr_a_i[0]` | 509 | −1.7387 |
| `_49709_` | `...raddr_b_i[1]` | 181 | −1.5937 |

**[fact, resolving the instance names against
`hw/soc/out/s47-sram/soc_top.netlist.v`]**

The endpoints resolve the same way: `_48886_`, the worst, is
`u_ibex.gen_regfile_ff.register_file_i.g_plain_rf.g_rf_flops[21].g_chk.rf_chk_q[1]`
— **a SECDED check-bit register of the protected register file**,
`docs/43`'s codec — and the other large group is `u_clint.mtime[*]`,
**the CLINT's 64-bit timer**.

> **This is a correction to `docs/47` and it matters, because `docs/47`
> reports the post-CTS path and presents it as the layout's answer.**
> Section 8.4 of that document names
> `u_ibex.gen_regfile_ff.register_file_i.raddr_b_i[1]` and says the
> critical path is "the same structure it has been since `docs/43`,
> confirmed a third time". **At post-CTS that is exactly right and it
> reproduces** — `full2/28-openroad-stamidpnr-1`'s worst violator is
> `_49709_/Q → _50288_/D`, which is `raddr_b_i[1] → u_clint.mtime[9]`
> **[fact]**. **At SIGN-OFF it is not the binding path.** After the
> post-GRT resizer has worked on it, the worst path in the run
> `docs/47` reports starts at **the SRAM macro's data output** and ends
> at a register-file check bit, and `docs/47` does not say so.

### 6.2 Where the 13.13 ns after the macro goes, and it is not wire RC

The worst path, decomposed from
`19-openroad-stapostpnr/nom_slow_1p08V_125C/max.rpt`:

| | ns |
|---|---:|
| clock to the macro's `A_CLK` | 1.8834 |
| **macro read arc `A_CLK → A_DOUT[15]`** | **9.5277** |
| 26 standard-cell stages to `_48886_/D` | **13.1261** |
| data arrival | **24.5371** |
| data required (20 ns + 1.7370 latency − 0.2500 uncertainty + 0.0690 CRPR − 0.2217 setup) | 21.3342 |
| **slack** | **−3.2029** |

**[fact]**

Of the 13.1261 ns in those 26 stages, **0.2481 ns is net delay and
12.8780 ns is cell delay** **[fact, summing the report's own two kinds of
row]**. **The wires are not slow. The wires are heavy**, and six stages
carry almost all of it:

| Stage | cell | load | input slew | delay |
|---|---|---:|---:|---:|
| `_34919_/Y` | `sg13g2_a22oi_1` | **202.3 fF** | 2.008 ns | **2.2383** |
| `_34912_/Y` | `sg13g2_a22oi_1` | 108.3 fF | 1.428 | 1.1511 |
| `_37779_/Y` | `sg13g2_nand3_1` | 81.5 fF | 1.117 | 1.0631 |
| `_34929_/Y` | `sg13g2_nand4_1` | 62.0 fF | 1.136 | 1.0542 |
| `_37783_/Y` | `sg13g2_o21ai_1` | 119.4 fF | 1.151 | 1.0009 |
| `_37879_/Y` | `sg13g2_xnor2_1` | 78.7 fF | 1.029 | 0.8509 |
| | | | **sum** | **7.3585** |

**[fact]**. The mean load over all 26 stages is **39.1 fF**.

### 6.3 Why the resizer did not fix it, in two measurements

**First: five of those six cells have no larger version in this
library.** The drive-strength ladder of `sg13g2_stdcell`, read out of
the LEF **[fact]**:

```
  buf   : 1 2 4 8 16      inv   : 1 2 4 8 16     ebufn/einvn : 2 4 8
  nand2 : 1 2             nor2  : 1 2            and2/or2    : 1 2
  a21oi : 1 2             a21o  : 1 2            mux2        : 1 2
  a22oi : 1               a221oi: 1              o21ai       : 1
  nand3 : 1               nand4 : 1              nor3/nor4   : 1 2
  xnor2 : 1               xor2  : 1              mux4        : 1
```

`sg13g2_a22oi`, `sg13g2_o21ai`, `sg13g2_xnor2`, `sg13g2_xor2`,
`sg13g2_nand3`, `sg13g2_nand4`, `sg13g2_a221oi` and `sg13g2_mux4` ship
in **exactly one drive strength**. `RSZ-0051` reports the post-GRT
resizer resized **1,620 instances, 1,620 up** **[fact]** — none of them
could be these.

**Second: those loads are LEGAL, so `repair_design` never looks at
them.** `sg13g2_stdcell_slow_1p08V_125C.lib` declares
`default_max_capacitance : 0.3` and `default_max_transition : 2.5074`
**[fact]**. The worst stage above sits at **0.2023 pF and 2.008 ns** —
inside both. The design has no other cap:
`MAX_CAPACITANCE_CONSTRAINT` and `MAX_TRANSITION_CONSTRAINT` are
`Optional` in LibreLane, **neither the sky130 nor the ihp-sg13g2 PDK
ships a value**, and `full3/final/sdc/*.sdc` contains
`set_max_fanout 10.0000`, the two `set_timing_derate` lines, and **no
`set_max_capacitance` and no `set_max_transition` at all** **[fact]**.

**What 0.3 pF buys, out of the library's own `cell_rise` table at the
slow corner with a 0.3294 ns input slew** — these are the seven loads
the vendor characterised at, and the numbers are the vendor's:

| load, pF | 0.0010 | 0.0234 | 0.0390 | **0.0648** | 0.1080 | 0.1800 | **0.3000** |
|---|---:|---:|---:|---:|---:|---:|---:|
| `sg13g2_a22oi_1` | 0.179 | 0.420 | 0.565 | **0.800** | 1.192 | 1.848 | **2.932** |
| `sg13g2_o21ai_1` | 0.197 | 0.468 | 0.635 | **0.908** | 1.365 | 2.127 | **3.395** |
| `sg13g2_xnor2_1` | 0.226 | 0.336 | 0.405 | **0.517** | 0.704 | 1.016 | **1.542** |

**[fact, `sg13g2_stdcell_slow_1p08V_125C.lib`]**

> **AT THE LIBRARY'S OWN `max_capacitance`, ONE `sg13g2_o21ai_1` COSTS
> 3.395 ns AT THE SLOW CORNER — 17.0 % OF A 20 ns PERIOD, ON ONE GATE**
> **[fact]**. `max_capacitance` in a standard-cell Liberty is a
> characterisation and reliability limit; it is not a timing budget, and
> a flow that enforces it and nothing tighter is enforcing nothing that
> a 50 MHz target cares about. **This is `docs/41` section 6.6's shape
> for a tenth time — a default that is not a decision — one layer below
> the two `RUN_POST_GRT_*` keys `docs/47` found there.**
>
> **What is NOT established by any of the above is that tightening it
> helps.** Everything in this section is a description of the flow's
> constraints and of one path; the inference that `repair_design` would
> convert it into slack is a prediction, and section 7 is the run that
> tests it.

### 6.4 The constraint, derived rather than invented

`docs/20` section 11's rule is that inventing a threshold records the
tool rather than the design. **0.0648 pF is not invented: it is the
fourth of the library's own seven characterisation loads, and the
largest of them at which every cell type on the measured critical path
stays under 1 ns at the slow corner** — `a22oi_1` 0.800, `o21ai_1`
0.908, `xnor2_1` 0.517 **[fact, the table above]**. At the next
characterised load up, 0.1080 pF, `o21ai_1` is 1.365 ns.

`MAX_CAPACITANCE_CONSTRAINT: 0.0648` puts
`set_max_capacitance 0.0648 [current_design]` into the flow-written
SDC beside the two derate lines **[fact,
`hw/soc/pnr/runs/cap1/05-openroad-floorplan/soc_top.sdc`]**.

---

## 7. What the constraint does, which is not what section 6 predicted

**The hypothesis section 6 builds is that a tighter capacitance limit
would let `repair_design` buffer the six heavy stages and recover
several nanoseconds. It was tested end to end, at extracted parasitics,
against `docs/47`'s own floorplan and its own configuration, and IT IS
WRONG.** This section is that measurement, and it is reported at the
same length it would have been reported at if it had worked.

Two runs, the same two-run structure `docs/47` used so that the stages
are comparable: `cap1` carries the flow from the netlist to global
routing with the post-GRT stages **off**, `cap2` resumes from `cap1`'s
post-CTS state with them **on** and goes to sign-off. **The only
difference from `full2`/`full3` is one key.**

### 7.1 The control is exact

| | `full2`/`full3` | `cap1`/`cap2` |
|---|---|---|
| global-placement HPWL | **2.100780e+06 um** | **2.100780e+06 um** |
| standard-cell span at global placement | 1849.3 × 792.2 um at (390.4, 587.1) | **the same, to 0.1 um** |
| CTS average sink wire length, `u_ibex.clk` | 996.17 um | 995.89 um |

**[fact]** — **the placement is the same placement.** Everything below
is the effect of one SDC line on the repair and resizing steps that
follow it, and of nothing else. This is the cleanest single-variable
comparison in this document and it is why the capacitance lead is worth
a section even though it fails.

### 7.2 What it did, stage by stage

Worst setup slack in ns at `nom_slow_1p08V_125C`.

| Stage | `full2`/`full3` | `cap1`/`cap2` | delta |
|---|---:|---:|---:|
| `RepairDesignPostGPL`: capacitance violations found | 181 | **1,021** | |
| `RepairDesignPostGPL`: buffers inserted | 3,326 in 2,396 nets | **6,128 in 2,919 nets** | |
| **post-CTS, before the timing resizer** | −10.7556 | **−7.2834** | **+3.4722** |
| post-CTS resizer, placement parasitics | −0.1577 | −0.9227 | −0.7650 |
| after global routing, no post-GRT repair | −6.8764 | −7.2927 | −0.4163 |
| `RepairDesignPostGRT`: capacitance violations found | 101 | **4,163** | |
| `RepairDesignPostGRT`: buffers inserted | 110 in 127 nets | **3,518 in 4,163 nets** | |
| post-GRT resizer: gates resized up / buffers inserted | 1,620 / 528 | **615 / 260** | |
| after global routing, **with** post-GRT repair | **−2.5778** | **−4.8771** | **−2.2993** |
| **sign-off, extracted parasitics** | **−3.2029** | **−4.8554** | **−1.6525** |
| **derived Fmax** | **43.10 MHz** | **40.23 MHz** | **−2.87 MHz** |

**[fact for every row; the deltas are differences of measurements and
the Fmax figures are `docs/31` section 4.2's convention]**

> **1. IT WORKS EXACTLY WHERE SECTION 6 SAID IT WOULD, AND THEN LOSES
> IT ALL BACK.** Before any timing resizer has run, the tightened
> constraint is worth **+3.4722 ns** — eight times `docs/44`'s measured
> noise, and the largest single-key improvement measured anywhere in
> this document. By sign-off it is **−1.6525 ns**, and the sign is the
> finding.
>
> **2. THE MECHANISM IS THAT `repair_design` IS A GLOBAL INSTRUMENT AND
> THE PROBLEM IS LOCAL.** `RepairDesignPostGRT` buffers **4,163 nets**
> against 127, because a 0.0648 pF limit is violated by thousands of
> ordinary nets and not only by the six on the critical path. The design
> ends with **13,745 timing-repair buffers against 7,910** and
> **42,979 standard cells against 37,623** — **+14.3 % cells and +73.1 %
> repair-buffer area** **[fact, the two `final/metrics.json`]**. Every
> one of those buffers is a stage of delay somewhere.
>
> **3. AND IT TAKES THE TARGETED INSTRUMENT'S ROOM AWAY.** OpenROAD's
> `repair_timing` is the step that works on the critical path
> specifically, and on the baseline it resized **1,620** gates up and
> inserted **528** buffers; with the constraint it managed **615** and
> **260** **[fact, `RSZ-0051` and `RSZ-0040`]**. It started from a worse
> post-route state (−8.188 against −6.530 on its own internal STA) and
> had less headroom to work in. **A global electrical constraint spent
> the budget that the targeted timing repair needed.**

### 7.3 But it fixes hold, and it fixes slew, and those are real

| Corner | `full3` hold ws | `cap2` hold ws | `full3` max slew | `cap2` max slew |
|---|---:|---:|---:|---:|
| `nom_fast_1p32V_m40C` | **−0.2015**, 3 violations | **+0.0494**, 0 | 1 | **0** |
| `nom_slow_1p08V_125C` | +0.4082, 0 | +0.4768, 0 | 14 | **0** |
| `nom_typ_1p20V_25C` | +0.0367, 0 | +0.2048, 0 | 0 | **0** |

**[fact, the two `19-openroad-stapostpnr/summary.rpt` files]**

> **`docs/47`'s hold failure and its slew failure are both closed by
> this one key, and the flow's own error list says so** — `cap2` exits
> non-zero naming **setup at the slow corner and max cap at all three,
> and nothing else**, where `full3` named four criteria **[fact, the
> two flow logs]**. `docs/47`'s max-slew violations -- 14 at the slow corner and 1 at the
> fast -- are gone,
> and the six heavy nets of section 6.2 are the same fact seen from the
> other side: a 2.008 ns transition on a 202.3 fF net is what a slew
> violation looks like when the limit is 2.5074 ns and nearly misses it.

**And the max-cap row must not be read as a regression, which is this
repository's own defect running backwards.** `cap2` reports 1,969 /
1,745 / 1,843 max-cap violations against `full3`'s 12 / 10 / 10, and
**the two numbers are counted against different limits** — 0.0648 pF
here, the library's 0.3 pF there. The gate is bound to all three
corners in both runs (section 9); what changed is the threshold behind
it. **`cap2` fails a criterion `cap2` invented for itself**, and this
document does not claim that its layout is electrically worse than
`full3`'s on the library's own terms, because it did not measure that.

### 7.4 What else the run says

| | `full3` | `cap2` |
|---|---:|---:|
| detailed-routing DRC | **0** after 5 iterations | **0** after 8 iterations (93 → 20 → 10 → 0 → 0 → 8 → 8 → 0) |
| disconnected pins | 0 | 0 |
| power-grid violations | 0 | 0 |
| antenna violating nets | 1 | 1 |
| antenna cells / diodes | 606 / 514 | **119 / 104** |
| routed wirelength | 3,095,532 um | 3,124,958 um |
| **longest net** | **2,332.02 um** | **2,137.16 um** |
| standard cells excl. fill | 37,623 | 42,979 |
| sequential cells | 3,085 | 3,085 — unchanged |
| max-fanout violations (judged by nothing) | 293 | 233 |
| `design__violations` in a run that fails setup | **0** | **0** |

**[fact]**

`design__violations` reads **0** again, on a run that fails setup at the
slow corner and exits non-zero — `docs/23` section 3.2's finding
reproduced for the third time and the second on this design.

### 7.5 Cost

| | |
|---|---:|
| `cap1`, netlist → global routing, post-GRT off | **29.8 min** over 35 steps |
| `cap2`, global routing → sign-off, post-GRT on | **92.3 min** over 32 steps |
| `fpA1`, netlist → post-CTS resizer (global routing did not complete) | **36.0 min** |
| `fpB1`, netlist → detailed routing | **57.8 min** |
| total for this document, excluding two terminated attempts | **about 3.6 h** of summed step runtime |

**[fact, `runtime.txt` per step; wall times on a shared 20-thread host
running up to three flows at once, quoted as costs and not as
precision]**. `cap2` is 51 % slower than `full3`'s 61.1 min for the same
steps, and the two causes are 5,356 more cells to route and two other
flows on the machine.

---

## 7a. So where is the 7.07 ns?

Four leads, all measured, none of them recovers it:

| Lead | Status | Worth |
|---|---|---:|
| `SYNTH_HIERARCHY_MODE: deferred_flatten` | **already removed** before `docs/47`'s number existed | **0 ns** remaining |
| `RUN_POST_GRT_*` | **already on** in the run that produced 43.10 MHz | **0 ns** remaining |
| The floorplan | two alternatives built and hardened; one does not route, one is 10.09 ns worse | **negative** |
| `MAX_CAPACITANCE_CONSTRAINT` | measured to sign-off | **−1.65 ns**, and hold and slew closed |

**[fact / estimate as marked above]**

**What is left is the design and the target, and the binding paths say
which parts of the design.** Section 6.1's four launch points and their
endpoints are two structures and both cross the SoC:

- **`register_file_i.raddr_a_i[0,2]` and `raddr_b_i[1,4]` → `u_clint.mtime[*]`.**
  A register-file read address, through the 32 × 39-bit read multiplexer,
  out through the fabric's broadcast address and write-data bus, into a
  **64-bit free-running counter**. `docs/47` section 11 item 4 noticed
  `u_clint` was on this path and ranked `mtime` fifth; it is the
  structure with the most endpoints behind it here.
- **`u_ram...u_b0/A_DOUT[15]` → `register_file_i...g_chk.rf_chk_q[1]`.**
  The SRAM read, through the load return path, into the **SECDED
  encoder of the protected register file** — `docs/43`'s codec, 22
  `sg13g2_xnor2_1` in the reported path. This is the binding one at
  −3.2029 and `docs/47` does not report it.

> **`docs/44` section 5.5's `SYNPRE` was declined for a reason that no
> longer holds.** It hoists the syndrome tree past the read multiplexer,
> **recovers 1.8677 ns measured on the register file alone for 11.6 %
> of the core**, and `docs/47` section 12 declined to reopen it because
> "most of the 7.07 ns is floorplan and not logic … recovering 1.87 ns
> of logic to close a 3.20 ns gap caused by wires would be fitting a
> mechanism to the wrong cause". **Sections 5 and 7 remove that
> premise.** The gap is not floorplan and it is not recoverable from the
> flow's constraints; 1.87 ns against 3.20 ns is the right order, and it
> acts on one of the two structures that are actually binding.

**And the target is a choice, so it is worth saying where it came
from.** `docs/02-npu-architecture.md`'s architecture table sets the
clock target as **"25–50 MHz, easily met"** — a range **[fact]**. 50 MHz
entered this project as the **Tiny Tapeout pilot's declared clock**:
`docs/06` calls it "the 50 MHz TT envelope" and a "~50 MHz practical
clock ceiling", and `docs/15` measured the pilot at 51.6 MHz against the
50 MHz `tt/info.yaml` declares. **`soc_top` is not a Tiny Tapeout tile,
has no `tt/info.yaml`, and is not bound by that envelope**, and
**43.10 MHz is inside the range `docs/02` states**.

> **This document does not revise the target, and says why rather than
> deferring silently.** A target is revised against a workload
> requirement, and **there is no document in this repository that
> derives a throughput requirement from the clock** — `docs/02` names
> telemetry anomaly detection and gives a range, `docs/10`'s only
> bandwidth anchor is a QSPI figure. **Revising 50 MHz to 43 MHz would
> therefore be revising it against nothing**, which is the same defect
> as meeting it against nothing. The consequence of not revising it is
> stated plainly instead: **the design misses its stated target by
> 13.8 %, the two cheapest remaining mechanisms are RTL, and if neither
> is taken then `docs/09` or `docs/15` has to say what 43.10 MHz costs
> the workload before anybody writes 43 MHz on a datasheet.**

---

## 8. What this does NOT cover

- **No new floorplan was taken to sign-off**, so FP-A and FP-B are
  compared with FP-0 at mid-flow stages and not at extracted
  parasitics. That is a real limit and it is one-directional: both are
  worse at every stage measured, by 0.84 and 1.70 ns at post-CTS
  against `docs/44`'s 0.4 ns of instrument noise and by 10.09 ns after
  global routing for the one that routes, and a stage-by-stage
  regression is not proof that the sign-off number would follow, only
  strong evidence for it. **FP-A was not carried past global routing
  because its global router did not terminate**, which is a result but
  is not the same result as a bad sign-off number.
- **FP-A's two global-routing attempts were TERMINATED, not observed to
  fail.** 33 minutes at 87 % of one core against 8.033 s is a
  congestion signal and is reported as one; **nobody knows what it
  would have done in four hours**, and no congestion report exists for
  it because the step never wrote one.
- **The capacitance sweep is one point.** `MAX_CAPACITANCE_CONSTRAINT`
  was measured at **0.0648 pF and nowhere else**. Section 11 item 3 is
  the search that was not run, and the −1.65 ns of section 7 is the
  cost of that one value and not of the idea.
- **`cap2`'s max-cap violation count is against its own tightened
  limit** and is not comparable with `full3`'s. **This document did not
  measure how many nets in `cap2`'s layout exceed the library's 0.3 pF**
  and does not claim that number is better or worse.
- **Two floorplans are not the floorplan space.** FP-A varies the
  channel height; FP-B varies the macro arrangement and the die aspect.
  Nothing here explored macro ORDERING within a row, a non-uniform
  channel, `PL_TARGET_DENSITY_PCT` as an independent variable, or any
  arrangement requiring a rotated macro. What is measured is that the
  two most obvious improvements are regressions and that the mechanism
  — the placer was never density-constrained — argues against the whole
  family.
- **THIS IS STILL NOT A PHYSICAL SIGN-OFF.** `RUN_MAGIC_DRC`,
  `RUN_KLAYOUT_DRC`, `RUN_KLAYOUT_XOR` and `RUN_LVS` are 0, for the
  reason `docs/12` sections 7.5 and 8 measured and `docs/47` section 9
  restates: Magic DRC 1,106,478, KLayout DRC 2,316 and Netgen LVS 359
  over ONE RM_IHPSG13 macro, every error inside the macro. Nothing here
  is evidence that any of these three layouts is manufacturable.
- **No behavioural evidence was re-run and none moved.** **This
  document changes no RTL at all** — section 12's file list has no file
  under `hw/soc/rtl/` in it. `docs/44` section 8.1's 22 checks and
  185,443 cycles remain the last behavioural evidence.
- **The fast corner's macro Liberty is still characterised at −55 C
  against −40 C for the cells** (`docs/12` section 6.4a), so every hold
  result here carries the same 15 C mismatch `docs/47` section 9 states.
- **`Yosys.EQY` is off, there is still no gate-level simulation of
  `soc_top`, and the boot ROM still has no contents.** `docs/47`
  sections 4.4 and 9; unchanged and not addressed.
- **One clock, one mode, no scan, no test, ~~no power number~~.** *Corrected 2026-09-05: there was a power
  number, and it was in the `full3` run this document takes its timing
  baseline from.
  `OpenROAD.STAPostPNR` wrote a `power.rpt` per corner into
  `hw/soc/pnr/runs/full3/19-openroad-stapostpnr/` — 27.774 / 34.835 /
  46.095 mW at slow / typ / fast on a default activity assumption —
  found by `docs/53-workload-and-the-clock.md` section 7.1; measured at
  RTL activity by `docs/57-power-under-a-duty-cycle.md` section 5 it is
  **33.890 mW computing and 5.539 mW waiting at typ**, on a layout that
  does not contain the NPU. "One mode" is also wrong: `docs/57`
  section 4 finds a clock gate over 2,464 of the 3,085 flip-flops.*
- **Nothing here closes, so no closing claim has to be qualified — but
  the qualification is written down anyway, because the next document
  will need it.** A first run that meets 20 ns at
  `nom_slow_1p08V_125C` would be: one netlist, one floorplan, one clock
  tree, one routing solution, timed at three corners, with no DRC, no
  LVS, no XOR, no equivalence check and no netlist simulation behind
  it. It would establish that a timing target is reachable and nothing
  else about whether the part works.
- **`design__violations` still reads 0 on every run in this document**,
  including the ones that fail. Nothing here fixed that and it is not
  fixable from a configuration file; `docs/23` section 3.2.

---

## 9. The checkers, re-audited

`docs/41` section 6.6 counts the occasions on which a green result in
this repository was read as wider than the thing it examined, and
`docs/47` section 7 configured four of them out before its first run.
**Every one of those keys is carried into every run in this document
unchanged**, because `hw/soc/pnr/floorplan.py` copies `config.json` and
asserts it touched four geometric keys and nothing else (section 4), and
because `cap1` and `cap2` are `config.json` itself with one command-line
override.

`hw/openlane/checker_audit.py`, which recomputes from the installed
LibreLane's own step classes whether each checker CAN fail, run against
the run that produced this document's sign-off number:

```
    registered Checker.* steps: 21
    of which the Classic flow runs: 19

GATES  Checker.SetupViolations   [corners] SETUP_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, violating nom_slow_1p08V_125C
GATES  Checker.HoldViolations    [corners] HOLD_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, all 0
GATES  Checker.MaxSlewViolations [corners] MAX_SLEW_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, all 0
GATES  Checker.MaxCapViolations  [corners] MAX_CAP_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, violating all three

    17 of 19 in-flow checkers gate fully.
    NOT gating in full: Checker.LintWarnings, Checker.WireLength
```

**[fact, `checker_audit.py hw/soc/pnr/runs/cap2`, exit 0]** — **17 of
19, the same as `docs/47`'s `full3`**, and the same two exceptions,
which are `Checker.WireLength` with no threshold in either PDK and
`Checker.LintWarnings` behind `ERROR_ON_LINTER_WARNINGS`.

> **THIS IS THE ROW THAT MATTERS AND IT IS WHY THE AUDIT WAS RE-RUN.**
> Section 7.3 claims that the capacitance constraint **closes hold and
> closes max slew**. Those two claims are `all 0` readings, and an
> `all 0` reading is worth exactly as much as the gate behind it.
> **`Checker.HoldViolations` and `Checker.MaxSlewViolations` are bound
> to `["*"]` in `cap2` and the audit confirms each examined three
> corners** — the identical binding under which `full3` reported
> **−0.2015 ns on 3 endpoints and 14 slew violations** and failed. The
> numbers improved; the gate did not move.

The derate is audited where `docs/31` sections 3.2 and 10.3 say it can
be — not in `resolved.json`, which records the integer `5` either way —
and `cap2`'s flow-written SDC carries `set_timing_derate -early 0.9500`
and `-late 1.0500` beside `set_max_capacitance 0.0648` **[fact]**.

**And the flow exits non-zero naming fewer criteria than `docs/47`'s
did**, which is the only honest form the improvement can take:

```
One or more deferred errors were encountered:
Setup violations found in the following corners:
* nom_slow_1p08V_125C
Max Cap violations found in the following corners:
* nom_fast_1p32V_m40C
* nom_slow_1p08V_125C
* nom_typ_1p20V_25C
```

**[fact, `hw/soc/out/s48-pnr-cap2.log`]** — against `docs/47` section
7.3's four blocks. Hold and max slew are absent because they passed,
through gates that were watching.

---

## 10. Corrections to earlier documents

- **`docs/47` section 8.4's closing sentence — "43.10 MHz is the
  frequency of this design IN THIS FLOORPLAN, not of this design" — is
  NOT SUPPORTED and should be narrowed.** It was labelled a hypothesis
  with three pieces of evidence and no control, which was the right
  label; the control now exists and both floorplans it admits are
  worse. The sentence that survives is: *43.10 MHz is the frequency of
  this design in the best of the three floorplans that have been tried,
  and the two most obvious improvements to it are regressions.*
  Sections 4 and 5.
- **`docs/47` section 8.4's critical path is the POST-CTS path, not the
  sign-off path, and the document does not distinguish them.** Its
  claim that the structure is "the same it has been since `docs/43`,
  confirmed a third time" reproduces exactly at `OpenROAD.STAMidPNR-1`
  (`raddr_b_i[1] → u_clint.mtime[9]`, −10.7556). **At sign-off the
  worst path starts at `u_ram.g_ram_2048x64.u_b0/A_DOUT[15]` and ends
  at a register-file SECDED check bit**, and 444 of the 2,003 violating
  endpoints are behind that macro. Section 6.1.
- **`docs/47` section 11 item 3, "a second floorplan … the cost of
  finding out is one run each", is DONE and the estimate of the cost
  was low.** FP-A cost two attempts and neither completed global
  routing; FP-B cost 57.8 min and routed. Section 5.
- **`docs/47` section 12's reason for leaving `SYNPRE` closed no longer
  holds.** It declined to reopen `docs/44` section 5.5 because "most of
  the 7.07 ns is floorplan and not logic". Sections 5 and 7 measure
  that it is neither floorplan nor a flow constraint. Section 7a.
- **`docs/47` section 8.4's 1,851.8 × 790.0 um strip reproduces
  exactly** and is the span of the 27,558 **synthesised** cells;
  counting every placed standard cell the same span is 2,184.5 ×
  1,345.7 um. Both are true; the document's own definition is the first
  and this is recorded so a reader who recomputes it is not misled.
  Section 2.
- **`docs/41` section 6.6's list gains a tenth entry of the same
  shape, and this one is in the PDK rather than in LibreLane.**
  `MAX_CAPACITANCE_CONSTRAINT` and `MAX_TRANSITION_CONSTRAINT` are
  `Optional`, **neither sky130 nor ihp-sg13g2 ships a value**, and the
  flow-written SDC of every run in this repository that reaches
  sign-off therefore contains no `set_max_capacitance` and no
  `set_max_transition` — so the only cap enforced is the library's
  `default_max_capacitance : 0.3`, at which **one `sg13g2_o21ai_1`
  costs 3.395 ns at the slow corner**. Unlike the other nine, **this one
  is reported and NOT taken**: section 7 measures that tightening it
  costs 1.65 ns of setup. It buys hold and slew closure, and section 11
  is where that trade goes.
- **`docs/23` section 3.2's finding that `design__violations` does not
  aggregate** is reproduced a third time: `cap2`'s `final/metrics.json`
  carries `design__violations: 0` and `flow__errors__count: 0` on a run
  that fails setup at the slow corner and exits non-zero.

---

## 11. What the next block should be

1. **`SYNPRE`, and it is now first rather than declined.**
   `docs/44` section 5.5 measured it at **1.8677 ns recovered on the
   register-file read path for 11.6 % of the core**, and proved the
   restructured decoder bit-for-bit identical to the frozen one over a
   free codeword. `docs/47` declined it on a premise sections 5 and 7
   have removed. It is the right size against a 3.2029 ns gap, and it
   acts on the SECDED encoder that terminates the binding path.
   **What has to be measured before it is taken**: `docs/44`'s 1.87 ns
   is a register-file-alone number pre-layout, and everything in
   `docs/47` and this document says a pre-layout number is not a
   post-layout number.
2. **`mtime`.** Ranked first by `docs/41` section 7.4 and `docs/44`
   section 11, second by `docs/43` section 12, third by `docs/45`,
   fourth by `docs/47`, and it has now been measured to be on **two** of
   the four binding launch structures rather than one. A 64-bit
   free-running counter at the far end of a broadcast bus is a timing
   problem as well as the robustness problem those documents describe.
3. **The capacitance constraint as a HOLD and SLEW fix rather than a
   setup fix.** Section 7.3: one key closes `docs/47`'s hold failure
   (−0.2015 ns on 3 endpoints at the fast corner) and its max-slew violations, 14 at the
   slow corner and 1 at the fast, for 1.65 ns of setup. **Neither this document nor
   `docs/47` has looked for a value that buys the first without paying
   the second** — 0.1080 pF and 0.1800 pF are the next two of the
   library's own characterisation loads and neither has been run. It is
   one run each and the search is one-dimensional.
4. **A hold-only alternative that is not a capacitance limit.**
   `PL_RESIZER_HOLD_SLACK_MARGIN` and `GRT_RESIZER_HOLD_SLACK_MARGIN`
   are the pilot's 0.1 and 0.05, quoted rather than tuned (`docs/47`
   section 7's note on `//holdmargin`). `docs/47` fails hold by 0.2015
   ns; the obvious experiment is a larger hold margin, and nobody has
   run it.
5. **ECC on the memories** and **how the boot ROM gets its contents** —
   `docs/47` section 11 items 1 and 2, untouched here and unchanged.
   The second is still the one that decides whether this part can boot.
6. **A gate-level simulation of `soc_top`**, `docs/45` section 9 item 5
   and `docs/47` section 11 item 5, still open and still blocked on item
   5's ROM answer.

**And one thing that should NOT be next.** A third floorplan. Section 5
measures that the placer was never density-constrained in `docs/47`'s
floorplan, which means the die size is not a lever on this design, and
the two arrangements that change the shape are worse for reasons — 44 %
more global-route wirelength, and a global router that does not
terminate — that a third variation would reproduce.

---

## 12. Files touched

| File | Change |
|---|---|
| `hw/soc/pnr/floorplan.py` | new — the floorplan generator. Reads the macro sizes from the PDK LEF, asserts site alignment and halo clearance, and reproduces `docs/47`'s floorplan exactly at `--channel 700.08 --density 40` |
| `hw/soc/flow/pnr_soc_top.sh` | `PNR_CONFIG` selects a floorplan variant, and the script refuses one outside `hw/soc/pnr/`. **The frozen-pilot refusal, the toolchain assertions and the `VERILOG_FILES` assertion are untouched** |
| `sw/tests/test_soc_synthesis_guards.py` | section 7 — three checks, each mutation-tested |
| `.gitignore` | `hw/soc/pnr/config-fp*.json` |
| `docs/48-floorplan-and-capacitance.md` | this document |
| `docs/00-index.md` | one row |

**No file under `hw/rtl/`, `hw/tb/`, `tt/`, `formal/`, `hw/openlane/` or
`hw/soc/rtl/` was modified** **[fact, `git status`]**.

---

## 13. Reproducing this

```
# ---- section 2: the instrument, before anything is claimed to move ----
SOC_MEM=sram hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s48-repro-sram
#   27,565 cells, 3,085 flops, 396,177.6420 um2
diff hw/soc/out/s48-repro-sram/soc_top.netlist.v \
     hw/soc/out/s47-sram/soc_top.netlist.v          # identical
SOC_MEM=sram hw/soc/flow/sta_soc_top.sh 20 hw/soc/out/s48-repro-sram
#   -26.3108 / -49.2780 / -11.1090, setup_sync +3.8711 slow

V=$HOME/Documents/caravel-lif-crossbar/.venv-flow/bin/python
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/full3   # -3.2029 / 2003
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/full3   # 17 of 19

# ---- section 3: the two leads that were already spent -----------------
python3 -c "import json;d=json.load(open('hw/soc/pnr/runs/full2/resolved.json'));\
print(d['SYNTH_HIERARCHY_MODE'], d['RUN_POST_GRT_DESIGN_REPAIR'])"   # flatten False
python3 -c "import json;d=json.load(open('hw/soc/pnr/runs/full3/resolved.json'));\
print(d['RUN_POST_GRT_DESIGN_REPAIR'], d['RUN_POST_GRT_RESIZER_TIMING'])"  # True True
cat hw/soc/pnr/runs/full2/01-yosys-jsonheader/state_in.json  # names s47-sram

# ---- section 4: the floorplans ---------------------------------------
export PDK_ROOT=$HOME/.ciel
python3 hw/soc/pnr/floorplan.py --channel 700.08 --density 40    # docs/47's
python3 hw/soc/pnr/floorplan.py --channel 310.74 --density 55 \
        --write hw/soc/pnr/config-fpA.json
python3 hw/soc/pnr/floorplan.py --arrangement islands \
        --channel 775.68 --density 50 --write hw/soc/pnr/config-fpB.json

SKIP="-S Yosys.Synthesis -S Checker.YosysUnmappedCells
      -S Checker.YosysSynthChecks -S Checker.NetlistAssignStatements"
for tag in fpA fpB; do
  PNR_CONFIG=hw/soc/pnr/config-$tag.json \
  hw/soc/flow/pnr_soc_top.sh ${tag}1 --overwrite -F Yosys.JsonHeader $SKIP \
      -i hw/soc/pnr/state/syn_soc_top.state.json \
      -c RUN_POST_GRT_DESIGN_REPAIR=false -c RUN_POST_GRT_RESIZER_TIMING=false
done

# ---- section 6: the library, measured rather than quoted -------------
grep -E "default_max_(capacitance|transition|fanout)" \
  $PDK_ROOT/ihp-sg13g2/libs.ref/sg13g2_stdcell/lib/sg13g2_stdcell_slow_1p08V_125C.lib
grep -o "^MACRO sg13g2_[a-z0-9_]*" \
  $PDK_ROOT/ihp-sg13g2/libs.ref/sg13g2_stdcell/lef/sg13g2_stdcell.lef | sort -u
grep set_max_capacitance hw/soc/pnr/runs/full3/final/sdc/*.sdc   # nothing

# ---- section 7: the constraint ---------------------------------------
hw/soc/flow/pnr_soc_top.sh cap1 --overwrite -F Yosys.JsonHeader $SKIP \
    -i hw/soc/pnr/state/syn_soc_top.state.json \
    -c RUN_POST_GRT_DESIGN_REPAIR=false -c RUN_POST_GRT_RESIZER_TIMING=false \
    -c MAX_CAPACITANCE_CONSTRAINT=0.0648
hw/soc/flow/pnr_soc_top.sh cap2 --overwrite -F OpenROAD.GlobalRouting \
    -i hw/soc/pnr/runs/cap1/30-openroad-stamidpnr-2/state_out.json \
    -c MAX_CAPACITANCE_CONSTRAINT=0.0648

# ---- the guards ------------------------------------------------------
.venv/bin/python -m pytest sw/tests/test_soc_synthesis_guards.py
```

`hw/soc/out/`, `hw/soc/pnr/runs/`, `hw/soc/pnr/config.resolved.json` and
`hw/soc/pnr/config-fp*.json` are gitignored.
