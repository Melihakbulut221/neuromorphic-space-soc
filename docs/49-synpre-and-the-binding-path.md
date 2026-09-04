# 49 — The lever is real, and it is not on the path that binds

`docs/48-floorplan-and-capacitance.md` section 11 item 1 promoted
`SYNPRE` from declined to first, and ended with a sentence this document
exists to test:

> **`docs/44` section 5.5's `SYNPRE` was declined for a reason that no
> longer holds.** … It is the right size against a 3.2029 ns gap, **and
> it acts on the SECDED encoder that terminates the binding path.**

**The first half is right and the second half is wrong**, and the
difference between them is what this document measures. `SYNPRE` was
built into the whole SoC, hardened on `docs/47`'s floorplan and carried
to sign-off at extracted parasitics. It is worth exactly what `docs/44`
priced it at on the register file, it is worth **more than that** in
layout at the stage where the read path binds — and at sign-off it moves
the number by **less than the instrument's own noise**, because the
binding path contains no syndrome tree for it to hoist.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
intended, with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by blob hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was modified;
`hw/openlane/checker_audit.py` and `hw/openlane/signoff_report.py` are
**read and run** and never written. Section 15 lists every file.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Does it close?** | **No. It closes at −3.0838 ns on 1,783 endpoints at `nom_slow_1p08V_125C`, 43.32 MHz**, against `docs/47`'s **−3.2029 on 2,003, 43.10 MHz**. The delta is **+0.1191 ns**, which is **inside `docs/44`'s measured 0.4 ns of instrument noise** and is **not reported as an improvement**. Sections 6.1 and 12 |
| **What did `SYNPRE` alone buy at sign-off?** | **Nothing on the number that decides the corner, and 30.3 % of the total negative slack.** Setup TNS **−2,075.11 → −1,446.11**, violating endpoints **2,003 → 1,783** — for **+2,684 cells and +27,237.7728 um2 as synthesised, +6.9 %** **[fact]**. Sections 4.1 and 6.2 |
| **Why not the worst path?** | **Because `docs/48` mis-named the cone, and this is the whole result.** That document says `SYNPRE` "acts on the SECDED **encoder** that terminates the binding path". `SYNPRE` restructures the SECDED **decoder** on the **read** port. The binding path is `SRAM macro → load return → the WRITE encoder → a check-bit flip-flop`, one `secded_enc` instance already in front of the storage with nothing to hoist it past. **The two cones are disjoint**, and the 444 endpoints behind the macros have a worst slack of −3.2029 while the 1,559 `SYNPRE` can reach have −2.0227 — **so the most a perfect, free `SYNPRE` could do to the worst slack is nothing.** Sections 3.2 and 13 |
| Is the lever real at all? | **Yes, and at post-CTS it is the largest single-change improvement measured on this design: −10.7556 → −7.2915, +3.4641 ns**, on the same read-address-to-`mtime` structure in both netlists, with the data arrival falling **31.8640 → 28.4130 ns** and **five `xnor2` cells on the path becoming two** **[fact]**. **It is then given back entirely by routing**: after global routing `syn1` is **−7.6924 against `full2`'s −6.8764**. Section 5 |
| What does the area do to the placement? | **Nothing to the density regime and a lot to the wire.** `docs/48` measured that the placer was never density-constrained at 18.9 % utilization; **+27,238 um2 takes it to 20.2 % against a target of 40 % and it still does not bind** — but the cells **spread** rather than compact, **27.0 % of their own bounding box becomes 22.1 %**, global-placement HPWL rises **23.2 %** and routed wirelength **13.8 %**. Sections 5.1 and 5.2 |
| Does anything compose? | **The composition premise was measured false and the run was not made.** `SYNPRE` frees no setup margin on the binding path, its `RepairDesignPostGRT` behaves like the baseline's (**94 / 109 / 128 nets against 101 / 110 / 127**) so it makes no room in the step `docs/48` measured as starved, and it moves max-cap and max-slew counts **up** against the library's own limit. Section 7 |
| Do the checkers still gate? | **17 of 19, the same as `docs/47` and `docs/48`, on the run that reports the improved hold.** `checker_audit.py` confirms `Checker.HoldViolations` examined three corners before reporting `all 0` — the identical binding under which `full3` reported −0.2015 ns on 3 endpoints and failed. Section 10 |
| Is the hold closure `SYNPRE`'s? | **Not claimed.** `syn2` has **0 hold violations at all three corners** against `docs/47`'s 3 at the fast corner, through a live gate — but the movement is **0.2498 ns on three endpoints**, inside the same noise that forbids claiming the setup delta, on a run where the netlist, placement, clock tree and routing all changed. Section 6.3 |
| What got worse? | **Max slew at the slow corner, 14 → 126, and max cap, 10 → 24 — both against the library's own 0.3 pF and 2.5074 ns, in both runs, so directly comparable.** Section 6.3 |
| Does the behavioural evidence still hold? | **Yes, and the change needed a new proof that `docs/44`'s C5 does not give.** `SYNPRE` substitutes an **encoder's** output for the **decoder's** syndrome, and the two modules carry **separate copies of H** that nothing in this repository had ever compared. **C6 and C7 were added and proved** on `bmc`, `prove`, `prove_abc` and `cover`, **9 of 9 covers reached**, and C6 mutation-tested to FAIL. The 124-injection campaign is identical field for field and the whole-SoC run is **cycle-identical: 22 checks, 174,128, 185,443, 587, 0**. Section 9 |
| What nearly went wrong | **`iverilog -P` on a hierarchical path elaborates, exits 0 and changes nothing.** The first whole-SoC "cycle-identical" result was a run of the design **without** the change. It is caught, repaired with a `defparam` in a second root, checked against the compiled object, and guarded. Section 8 |
| What changed in the design? | **Nothing. No RTL file was modified**, `hw/soc/rtl/ibex_regfile_secded.v` included. Section 15 |

---

## 2. Reproducing the instrument, eleven ways, before moving it

`docs/44` section 5.2 set the rule and `docs/45`, `docs/47` and
`docs/48` all followed it. Everything below is re-measured in this
session against the published figures, and it covers **both**
instruments this document uses — the whole-SoC flow and `docs/44`'s
register-file-alone one, because the number under test was produced by
the second and is being spent on the first.

| What | Published | Measured here |
|---|---|---|
| `SOC_MEM=sram` whole design | `docs/47` 6.3: **27,565 cells, 3,085 flip-flops, 396,177.6420 um2** | **27,565 / 3,085 / 396,177.6420**, and `soc_top.netlist.v` is **byte-identical** to `hw/soc/out/s47-sram/`'s **[fact, `diff`]** |
| pre-layout three-corner setup | `docs/47` 6.3: **−26.3108 / −49.2780 / −11.1090** | **every figure** |
| pre-layout `setup_sync`, slow | `docs/47` 6.3: **+3.8711** | **+3.8711** |
| sign-off, slow corner | `docs/47` 8.2: **−3.2029 ns on 2,003 endpoints, 43.10 MHz** | **−3.2029 / 2,003**, `hw/openlane/signoff_report.py` on `full3` |
| post-CTS, before the timing resizer | `docs/48` 5: **−10.7556** | **−10.7556** |
| standard-cell placement span | `docs/48` 2: **1,849.3 × 792.2 um** over **27,558** synthesised cells at (390.4, 587.1) | **1,849.3 × 792.2** over **27,558** at **(390.4, 587.1)** |
| the four launch points of the 2,003 violators | `docs/48` 6.1: **444 / 868 / 509 / 181**, worst **−3.2029 / −2.0227 / −1.7387 / −1.5937** | **every count and every slack**, resolved against the netlist independently |
| checker audit | `docs/47` 7.3 and `docs/48` 9: **17 of 19 in-flow checkers gate fully** | **17 of 19**, exit 0 |
| **`docs/44` section 5.4's register file, all six rows** | 94,153.1094 / 93,469.9878 / 113,987.9412 / 126,842.2470 / 128,043.7956 / **159,272.9082** um2 | **all six, to four decimal places** |
| **`docs/44` section 5.4's read-path arrivals** | 5.5014 / 5.5282 / 7.8891 / 8.3210 / 8.0617 / **6.4533** ns at the slow corner | **all six** |
| the whole-SoC behavioural invariant | `docs/43` 9.1 and `docs/44` 8.1: 22 checks, fail mask 0, watchdog stage 1 at cycle **174,128**, core asleep after **185,443** cycles, **587** console characters, 0 framing errors | **every one** |

**[fact for every row]**

**The two derived quantities `docs/44` section 5.5 rests on reproduce as
differences of those measurements**: the codec costs
**8.3210 − 5.5282 = 2.7928 ns** on the read path, `FASTCORR` recovers
**8.3210 − 8.0617 = 0.2593 ns**, and `SYNPRE` recovers
**8.3210 − 6.4533 = 1.8677 ns**, for
**159,272.9082 − 128,043.7956 = +31,229.1126 um2** on the module
**[estimate, arithmetic on measured rows; every input is in the table
above]**.

> **One number that `docs/44` does not state and this document needs.**
> Its 1.8677 ns is measured against `FASTCORR = 0`, which is
> `docs/43`'s read path and **not the one that ships**. Against the
> shipped `FASTCORR = 1` row, `SYNPRE` is worth
> **8.0617 − 6.4533 = 1.6084 ns** **[estimate, the difference of two
> rows of the same table]**. That is the marginal figure for this
> decision, because `FASTCORR`'s 0.2593 ns is already banked, and it is
> the smaller of the two.

---

## 3. What `SYNPRE` acts on, and what binds — which are not the same cone

This section is the one that decides the document, and it is a structural
statement with two measurements under it.

### 3.1 The population of the 2,003 violating endpoints

Every violator in
`hw/soc/pnr/runs/full3/19-openroad-stapostpnr/nom_slow_1p08V_125C/violator_list.rpt`
resolved against `hw/soc/out/s47-sram/soc_top.netlist.v`, launch and
capture both:

| Launch | Capture | Endpoints | Worst | Group TNS |
|---|---|---:|---:|---:|
| **SRAM macro `u_ram.g_ram_2048x64.u_b0/A_DOUT`** | register-file **SECDED check bits** | **217** | **−3.2029** | |
| the same | register-file **data bits** | 219 | −0.9306 | |
| the same | core, other | 8 | −2.3058 | |
| | **the macro's total** | **444** | **−3.2029** | **−610.5630** |
| `register_file_i.raddr_a_i[2]` | mixed | 868 | −2.0227 | |
| `register_file_i.raddr_a_i[0]` | mixed | 509 | −1.7387 | |
| `register_file_i.raddr_b_i[1]` | mixed | 181 | −1.5937 | |
| `…g_scrub.ptr_q[3]` | `u_busstat` | 1 | −0.0098 | |
| | **the read-address total** | **1,559** | **−2.0227** | **−1,464.5506** |

**[fact; the four launch points and their counts are `docs/48` section
6.1's, reproduced, and the capture-side split and the two group TNS
figures are new]**

### 3.2 `SYNPRE` is on the read side. The binding path is on the write side.

`hw/soc/rtl/ibex_regfile_secded.v` has **two** places where the codec
touches a flip-flop, and they are disjoint:

- **The read ports.** `raw_a = rf_data[raddr_a_i]`, `chk_a =
  rf_chk[raddr_a_i]`, then a `secded_dec` whose **syndrome** builds the
  correction mask, then `rdata_a_o`. **This is what `SYNPRE` changes**:
  `g_synpre` puts one `secded_enc` beside every register and takes
  `enc(rf_data[j]) ^ rf_chk[j]`, so the XOR tree runs **in parallel with
  the 32-way read multiplexer** instead of behind it.
- **The write port.** `wr_data = we_a_i ? wdata_a_i : scrub_data`, one
  `secded_enc u_enc_wr`, and its `check_out` is the D input of every
  `rf_chk_q`. **`SYNPRE` does not touch this and cannot**: there is one
  encoder, it is already in front of the storage, and there is nothing
  to hoist it past.

**The binding path is the second one.** The sign-off `max.rpt`
decomposes as: the macro's `A_CLK → A_DOUT[15]` read arc, the load
return path through the fabric into Ibex's write-back, and then **eleven
`sg13g2_xnor2_1` in series — the write encoder's parity chain — into
`_48886_/D`, which resolves to
`…g_rf_flops[21].g_chk.rf_chk_q[1]`** **[fact,
`full3/19-openroad-stapostpnr/nom_slow_1p08V_125C/max.rpt`]**. Not one
gate of that path is inside the cone `SYNPRE` restructures.

> **SO THE CORRECTION TO `docs/48` IS ONE WORD LONG AND IT IS THE WHOLE
> RESULT.** That document says `SYNPRE` "acts on the SECDED **encoder**
> that terminates the binding path". `SYNPRE` acts on the SECDED
> **decoder** on the read path. The encoder that terminates the binding
> path is `u_enc_wr`, a single instance on the write port, and what
> `SYNPRE` adds is **thirty-one more encoders somewhere else**.
>
> **The most `SYNPRE` could do to the sign-off worst slack, if it were
> perfect and free, is nothing**, because the 1,559 endpoints it can
> reach have a worst slack of **−2.0227** and the 444 it cannot have
> **−3.2029** **[fact, section 3.1]**. What it can move is **70.6 % of
> the TNS** and **77.8 % of the endpoint count** — and the worst-slack
> number that decides `Checker.SetupViolations` and the derived Fmax is
> not in that population.

**This is not a reason to skip the experiment and it was not treated as
one.** A pre-layout structural argument is exactly the kind of thing
`docs/47` and `docs/48` were written to distrust: `repair_timing` works
on whichever path is worst at the time it runs, the two populations
compete for the same resizer budget, and 2,684 more cells change the
placement. The rest of this document is what happened when it was run.

---

## 4. What was built

`SYNPRE` is a parameter of `hw/soc/rtl/ibex_regfile_secded.v` that has
existed and been priced since `docs/44` and that **nothing sets**. Two
flows gained a way to reach it, both defaulting to 0, and
`sw/tests/test_soc_regfile_guards.py` was extended rather than relaxed
so that the default stays where it is (section 15).

| | |
|---|---|
| `hw/soc/flow/syn_soc_top.sh` | `IBEX_RF_SYNPRE=1` emits one `chparam` before `hierarchy -check`. **At 0 nothing is emitted at all**, and the control is that the netlist is then **byte-identical** to the one `docs/47` hardened — measured, section 2 |
| `hw/soc/flow/sim_soc.sh` | `SOC_RF_SYNPRE=1` builds the whole-SoC simulation with the hoisted read path, by a generated `defparam` in a second elaboration root. Section 8 is why it is not `-P`, and why the script checks the compiled object afterwards |
| `hw/soc/flow/pnr_soc_top.sh` | **unchanged**. It already takes `SYN_NETLIST` |

### 4.1 The area, at the two scales it can be read at

| | cells | flip-flops | standard-cell area, um2 |
|---|---:|---:|---:|
| **the register file alone**, `HARDEN = 1, FASTCORR = 1` | 8,432 | 1,214 | **128,043.7956** |
| the same, `SYNPRE = 1` | 10,539 | 1,214 | **159,272.9082** |
| difference | **+2,107** | **0** | **+31,229.1126** |
| **`soc_top` whole**, `SOC_MEM=sram`, as `docs/47` hardened | 27,565 | 3,085 | **396,177.6420** |
| the same, `IBEX_RF_SYNPRE=1` | 30,249 | 3,085 | **423,415.4148** |
| difference | **+2,684** | **0** | **+27,237.7728** |

**[fact for every row; the differences are arithmetic on them]**

Three things to read out of that table.

1. **The flip-flop count does not move, at either scale.** `SYNPRE` is
   pure combinational restructuring: 31 parity trees, no state. That is
   the check that the parameter does what its comment says it does.
2. **`docs/44`'s "+31,229.1126 um2, 11.6 % of the unprotected core" is
   the module figure and it reproduces exactly.** In the whole SoC the
   same change costs **+27,237.7728 um2, +6.9 %** of the design's
   standard-cell area **[estimate]** — smaller, because the whole-design
   mapper folds some of it and because the denominator is the whole SoC
   rather than the core. Both are true and this document quotes the
   second, because the second is what gets placed.
3. **The SoC gains 577 more cells than the module does** (+2,684 against
   +2,107) for the same change, which is `docs/45` section 4.3's finding
   again: a block's measured size is a function of the whole source
   list, not only of the block.

---

## 5. The layout, stage by stage

Worst setup slack in ns at `nom_slow_1p08V_125C`, 20 ns period, 5 %
derate applied as a float. `syn1` is `hw/soc/pnr/config.json` with the
two post-GRT keys **off**, from the `SYNPRE` netlist; `syn2` resumes
from `syn1`'s post-CTS state with them **on**. **That is `docs/47`'s
`full2`/`full3` structure and `docs/48`'s `cap1`/`cap2` structure, and
the only difference from `full2`/`full3` is which netlist went in** —
`resolved.json` for `full2` and `syn1` agree on every key this document
quotes, including all four `*_VIOLATION_CORNERS`, the derate, both
`RUN_POST_GRT_*`, `DIE_AREA`, `PL_TARGET_DENSITY_PCT` and
`MAX_CAPACITANCE_CONSTRAINT: null` **[fact]**.

### 5.1 The table

| | **`full2`/`full3`**, `docs/47` | **`cap1`/`cap2`**, `docs/48` | **`syn1`/`syn2`**, here |
|---|---:|---:|---:|
| netlist standard-cell area, um2 | 396,177.6420 | the same netlist | **423,415.4148** |
| global-placement HPWL, um | **2.100780e+06** | 2.100780e+06 | **2.588377e+06** |
| standard-cell span, global placement | 1,849.3 × 792.2 um | the same | **1,902.0 × 1,006.7** |
| cells / their own bounding box | **27.0 %** | 27.0 % | **22.1 %** |
| cells / placeable core area | 18.9 % | 18.9 % | **20.2 %** |
| `RepairDesignPostGPL`: cap violations / buffers | 181 / 3,326 in 2,396 nets | 1,021 / 6,128 in 2,919 | **202 / 3,271 in 2,366** |
| **post-CTS, before the timing resizer** | **−10.7556** | −7.2834 | **−7.2915** |
| post-CTS resizer: resized / buffers | 1,038 / 392 | 385 / 217 | **358 / 228** |
| **post-CTS resizer, placement parasitics** | −0.1577 | −0.9227 | **+0.0173**, TNS 0 |
| global-routing runtime | 8.033 s | — | **10.547 s** |
| global-route wirelength / nets | 3,771,252 um / 36,494 | — | **4,223,628 um / 38,864** |
| **after global routing, no post-GRT repair** | **−6.8764** | −7.2927 | **−7.6924** |
| `RepairDesignPostGRT`: cap violations / buffers | 101 / 110 in 127 nets | 4,163 / 3,518 in 4,163 | **94 / 109 in 128** |

**[fact for every row]**

### 5.2 What `SYNPRE` did, where it did it, and where it stopped

> **1. AT POST-CTS IT IS THE LARGEST SINGLE-CHANGE IMPROVEMENT MEASURED
> ANYWHERE ON THIS DESIGN, AND IT IS ON EXACTLY THE PATH IT WAS BUILT
> FOR.** −10.7556 → **−7.2915**, **+3.4641 ns**, eight times `docs/44`'s
> measured 0.4 ns of noise. The worst post-CTS path is a register-file
> read address into `u_clint.mtime` in **both** netlists —
> `raddr_b_i[1] → mtime[9]` in `full2`, `raddr_a_i[3] → mtime[24]` in
> `syn1` — so this is the same structure measured twice, and the data
> arrival on it falls from **31.8640 ns to 28.4130 ns** with **five
> `xnor2` cells on the path becoming two** **[fact, the two
> `28-openroad-stamidpnr-1/max.rpt`]**. That is the syndrome tree coming
> off the read path, visible as cells.
>
> **2. AND IT IS ALMOST EXACTLY WHAT THE CAPACITANCE CONSTRAINT WAS
> WORTH AT THE SAME STAGE, BY A COMPLETELY DIFFERENT MECHANISM.**
> `docs/48`'s +3.4722 ns came from `repair_design` buffering 2,919 nets;
> this +3.4641 ns comes from deleting three levels of logic and
> buffering **fewer** nets than the baseline did. **The two numbers
> agreeing to 0.008 ns is a coincidence and is reported as one.** What
> is worth noticing is weaker and is labelled as such: **two changes
> with nothing in common both stop at about −7.3 ns at this stage**,
> which is what a third structure that neither of them touches would
> look like **[estimate, from two measurements and no third experiment]**.
>
> **3. THE PLACER IS STILL NOT DENSITY-CONSTRAINED, WHICH IS THE ANSWER
> TO THE OTHER HALF OF THE AREA QUESTION.** `docs/48` section 5's
> mechanism was that `PL_TARGET_DENSITY_PCT: 40` never bound at 18.9 %
> utilization. **+27,238 um2 takes that to 20.2 % and it still does not
> bind** **[estimate, arithmetic on measured areas]**. The extra area
> costs nothing in the density regime; **what it costs is wire.** The
> cells spread rather than compact — **27.0 % of their own bounding box
> becomes 22.1 %** — global-placement HPWL rises **23.2 %** and
> global-route wirelength **12.0 % on 6.5 % more nets** **[estimate,
> differences of measurements]**. 31 parity trees fanning out of all 32
> registers' flip-flops is a lot of new connectivity in a design whose
> logic already sits in a strip 1,849 um long.
>
> **4. AND THAT IS WHERE IT GIVES THE 3.46 ns BACK.** After global
> routing with the post-GRT stages off, `syn1` is **−7.6924 against
> `full2`'s −6.8764 — 0.8160 ns WORSE** **[fact]**, and the worst path
> is no longer a register-file read at all: it ends **at the RAM macro's
> own input**, `u_ram.g_ram_2048x64.u_b0`. The read path was shortened,
> every other path got longer wires, and by the time real routing
> parasitics exist the second effect has eaten the first.

**One difference from `docs/47`'s pair, stated so the tables are read
correctly.** `full2` was stopped at detailed routing; `syn1` was allowed
to run its full 60 steps and therefore has a sign-off of its own —
**−7.3439 ns on 2,998 endpoints, hold clean at all three corners, 208
max-slew violations at the slow corner** **[fact,
`signoff_report.py hw/soc/pnr/runs/syn1`]**. **It has no matched
baseline**, because no run in `docs/47` or `docs/48` took the post-GRT
stages off all the way to extracted parasitics, so it is recorded and
not compared. `syn2` is the run that answers the question.

---

## 6. Sign-off

`syn2` resumed from `syn1`'s post-CTS state with `RUN_POST_GRT_DESIGN_REPAIR`
and `RUN_POST_GRT_RESIZER_TIMING` on, exactly as `full3` resumed from
`full2`'s, and ran to extracted parasitics and three-corner sign-off STA.

### 6.1 The number

| `nom_slow_1p08V_125C`, 20 ns | `full3`, `docs/47` | **`syn2`** | delta |
|---|---:|---:|---:|
| **worst setup slack** | **−3.2029** | **−3.0838** | **+0.1191** |
| violating setup endpoints | 2,003 | **1,783** | −220 |
| setup TNS | −2,075.11 | **−1,446.11** | +629.00 |
| **derived Fmax** | **43.10 MHz** | **43.32 MHz** | **+0.22 MHz** |

**[fact, `hw/openlane/signoff_report.py` on both run directories; the
Fmax figures are `docs/31` section 4.2's convention and the deltas are
differences of measurements]**

> **+0.1191 ns IS NOT AN IMPROVEMENT AND THIS DOCUMENT DOES NOT REPORT
> IT AS ONE.** `docs/44` section 5.2 measured this flow's resolution at
> about **0.4 ns**, from two controlled pairs that added no gate level
> to the path under test and moved the reported slack by 0.1585 and
> 0.3988 ns anyway. **0.1191 ns is inside that**, on a change that
> re-mapped, re-placed, re-clocked and re-routed a 30,000-cell design.
> The honest statement is that **`SYNPRE` did not move the sign-off
> worst slack**, and 43.32 against 43.10 MHz is the same number twice.

### 6.2 What it DID move, which is everything except the number

| | `full3` | `syn2` |
|---|---:|---:|
| **endpoints launched by the SRAM macros** | **444**, worst −3.2029, TNS −610.56 | **257**, worst **−3.0838**, TNS −431.65 |
| **endpoints launched inside the register file** | **1,559**, worst −2.0227, TNS −1,464.55 | **1,526**, worst **−2.1220**, TNS **−1,014.46** |
| total setup TNS | −2,075.11 | **−1,446.11**, **−30.3 %** |

**[fact, resolving both `violator_list.rpt` files against their own
netlists]**

> **1. THE BINDING PATH IS THE SAME PATH, AND IT IS THE ONE `SYNPRE`
> CANNOT REACH.** `syn2`'s worst is
> **`u_ram.g_ram_2048x64.u_b2/A_DOUT → a register-file SECDED check
> bit`**, and **217 endpoints sit behind the two RAM banks on exactly
> that structure** — 155 behind `u_b2` and 62 behind `u_b0` — against
> `full3`'s 217 behind `u_b0` **[fact]**. **The same 217-endpoint
> write-encoder population binds both runs.** Section 3.2 predicted
> this from the RTL before the run; the run agrees.
>
> **2. THE READ PATH'S LAUNCH POINT MOVED, WHICH IS `SYNPRE`'S
> SIGNATURE IN THE VIOLATOR LIST.** In `full3` the 1,559 register-file
> endpoints launch from the **address** registers, `raddr_a_i[2]`,
> `raddr_a_i[0]` and `raddr_b_i[1]`. In `syn2` **1,242 of them launch
> from `g_rf_flops[*].rf_reg_q`, the stored data itself** **[fact]**.
> That is precisely what hoisting the tree does: the syndrome no longer
> waits for the address to select a word, so the long path now starts at
> the word.
>
> **3. AND ON THAT POPULATION THE WORST SLACK DID NOT IMPROVE EITHER:
> −2.0227 became −2.1220** **[fact]**. What improved is the **bulk**.
> **TNS on the register-file group falls 30.7 %**, from −1,464.55 to
> −1,014.46, on 1,526 endpoints against 1,559 — so **almost every path
> in that population got shorter and the longest one did not.** Across
> the whole design 220 endpoints stop violating, and **187 of the 220
> are in the macro group** (444 → 257) rather than in the one `SYNPRE`
> acts on **[fact]**. **`SYNPRE` bought depth on 1,526 paths and gave it
> back on the longest of them to the 13.8 % more wire it costs.**

### 6.3 The rest of the sign-off set

| | `full3` | `syn2` |
|---|---:|---:|
| **hold, `nom_fast_1p32V_m40C`** | **−0.2015 ns on 3 endpoints** | **+0.0483 ns on 0** |
| hold, slow / typ | +0.4082 / +0.0367, 0 violations | +0.4877 / +0.2102, 0 |
| **max slew, fast / slow / typ** | 1 / **14** / 0 | 1 / **126** / 3 |
| **max cap, fast / slow / typ** (both against the library's 0.3 pF) | 12 / 10 / 10 | **24 / 24 / 24** |
| detailed-routing DRC | 0 after 6 iterations | **0 after 5** |
| **antenna violating nets** | 1 | **0** |
| antenna diodes | 514 | 439 |
| routed wirelength | 3,095,532 um | **3,523,011 um, +13.8 %** |
| longest net | 2,332.02 um | 2,206.19 um |
| standard cells excl. fill | 37,623 | **40,119** |
| standard-cell area, um2 | 531,371 | **551,672, +3.8 %** — smaller than the netlist's +6.9 %, because `syn2` ends with **fewer** timing-repair buffers |
| timing-repair buffers | 7,910 | **7,824** |
| of which setup buffers | 528 | **701** |
| post-GRT resizer: resized / buffers | 1,620 / 528 | **1,653 / 701** |
| max-fanout violations (judged by nothing) | 293 | 267 |
| disconnected pins / power-grid violations | 0 / 0 | 0 / 0 |
| `design__violations` on a run that fails setup | **0** | **0** |

**[fact, the two `final/metrics.json` and the two
`19-openroad-stapostpnr/summary.rpt`]**

> **THE HOLD ROW IS TEMPTING AND IT MUST NOT BE CLAIMED.** `docs/47`'s
> hold failure — the one that made `full3` exit non-zero on a second
> criterion — is **absent in `syn2`, at all three corners, through a
> checker the audit confirms was bound to all three** (section 10). But
> the movement is **0.2498 ns on a population of three endpoints**, and
> 0.2498 ns is **inside the same 0.4 ns** that forbids claiming the
> setup delta. **This document reports that `syn2` has no hold violation
> and does not attribute it to `SYNPRE`.** `docs/48` bought the same
> closure from a different key and could attribute it, because there the
> placement was bit-identical and one SDC line was the only difference;
> here the netlist, the placement, the clock tree and the routing all
> changed.
>
> **THE SLEW AND CAP ROWS ARE NOT INSIDE ANY NOISE AND THEY GO THE OTHER
> WAY.** Max-slew violations at the slow corner go **14 → 126** and
> max-cap violations **10 → 24** at the slow corner and **12 → 24** at
> the fast — **and unlike `docs/48` section 7.3's, these two counts are
> against the SAME limit in both runs**, the library's
> `default_max_capacitance : 0.3`, because neither run sets
> `MAX_CAPACITANCE_CONSTRAINT`. **They are directly comparable and
> `syn2` is electrically worse.** The mechanism is the row above them:
> **+13.8 % routed wirelength** on 31 parity trees fanned out of 32
> registers' flip-flops. `docs/48` section 6 measured that heavy nets on
> single-drive-strength cells are what this design's delay is made of;
> `SYNPRE` makes more of them.
>
> **The flow exits non-zero on three criteria where `docs/47`'s exited
> on four**, and the one that dropped off is hold **[fact, the two flow
> logs]**.

---

## 7. Composition, and why it was not run

`docs/48` section 11 item 3 leaves `MAX_CAPACITANCE_CONSTRAINT` as a
half-good lead: at 0.0648 pF it closes hold and every max-slew violation
and costs **1.6525 ns of setup**, because `RepairDesignPostGRT` buffers
**4,163 nets** and leaves `repair_timing` no room. The composition
hypothesis is that if `SYNPRE` frees setup margin, a capacitance value
that was unaffordable becomes affordable — that the two leads compose
where neither alone is enough.

**The premise is measured false, in three places, and this document
declines the run rather than spending nine hours confirming a
prediction it can already state.**

1. **`SYNPRE` frees no setup margin on the binding path.** Section 6.1:
   +0.1191 ns, inside the noise, and section 6.2: the same 217-endpoint
   write-encoder population binds both runs. There is nothing for
   0.0648 pF to be spent out of.
2. **`SYNPRE` does not fix `docs/48`'s mechanism.** That document's
   diagnosis is that `repair_design` is a global instrument starving a
   local one. **`syn2`'s `RepairDesignPostGRT` found 94 capacitance
   violations and inserted 109 buffers in 128 nets, against `full3`'s
   101 / 110 / 127** **[fact]** — `SYNPRE` behaves like the baseline
   here, not like `cap1`, so it makes no room in the step that was
   short of it. Adding 0.0648 pF would produce `cap2`'s 4,163 nets on
   top of `syn2`'s 2,496 extra cells.
3. **And `SYNPRE` moves the electrical figures in the direction that
   makes a tighter cap MORE expensive, not less.** Section 6.3:
   +13.8 % routed wirelength, **24 max-cap violations at every corner
   against 10 to 12**, and **126 max-slew violations at the slow corner
   against 14** — against the library's own limit in both cases. A
   design with more heavy nets is a design `repair_design` buffers more
   of.

> **The predicted composed result is `cap2`'s sign-off, not better than
> it** **[estimate, from items 1 to 3]**, and the cost of measuring it
> is a second `syn1`/`syn2` pair. **`docs/48`'s most valuable finding was
> that leads get stacked and never attributed; the discipline that
> follows from it is not to run a combination whose premise has just
> been measured false.** The lead itself is not dead — 0.1080 pF and
> 0.1800 pF are still unrun and still one-dimensional — but it is
> `docs/48`'s lead about hold and slew, on the baseline netlist, and
> section 14 item 4 leaves it there.

### 7.1 Cost

| | |
|---|---:|
| `syn1`, netlist → sign-off, post-GRT off | **109.9 min** over 60 steps |
| `syn2`, global routing → sign-off, post-GRT on | **427.6 min** over 32 steps |
| of which `OpenROAD.ResizerTimingPostGRT` alone | **6 h 19 min 16 s**, against `full3`'s **22 min 28 s** |
| synthesis, `IBEX_RF_SYNPRE=1` | 37.3 s |
| the register-file suite, formal and cocotb and two SoC simulations | under 2 min in total |
| **total for this document** | **about 9.0 h** of summed step runtime |

**[fact, `runtime.txt` per step; wall times on a shared 20-thread host
that was also running another project's flow throughout, quoted as costs
and not as precision]**. **`syn2` was started from `syn1`'s post-CTS
state before `syn1` had finished, so the two overlapped for about an
hour**; that inflates `syn2`'s early steps and is why the 16.9x below is
labelled an estimate rather than a measurement of the tool.

> **THE 16.9x ON ONE STEP IS ITSELF A RESULT AND IT IS REPORTED BECAUSE
> IT IS PART OF THE PRICE.** `repair_timing` ran **3,140 setup
> iterations against `full3`'s 2,500**, on **2,964 violating endpoints
> against 2,445**, and spent most of them oscillating between −1.02 and
> −1.09 ns on its own internal STA **[fact, the two step logs]**.
> Whatever `SYNPRE` costs in area, it costs more in the flow: **a 6.9 %
> larger netlist made the targeted timing repair 16.9 times slower**
> **[estimate, the ratio of two measured runtimes on a shared host]**.

---

## 8. Two ways this document nearly reported a number it had not measured

Both were caught, both are recorded, and the second is now a guard.

### 8.1 `iverilog -P` on a hierarchical path is discarded in silence

The whole-SoC behavioural check needs the register file built with
`SYNPRE = 1` four levels down inside `ibex_top`, without editing
anything under `hw/soc/ext` or `hw/soc/gen`. The obvious way is
Icarus's `-P`:

```
iverilog -s tb_soc -Ptb_soc.dut.u_ibex.gen_regfile_ff.register_file_i.SYNPRE=1 ...
```

**It elaborates, exits 0, prints nothing to the log, and changes
nothing.** The first run of this check reported the invariant — 22
checks, 174,128, 185,443, 587, 0 — from a design that did not have the
change in it. What gave it away was that the compiled object still
carried the `g_synpost` scope and not `g_synpre`.

Measured on a four-module toy so that the finding is about the tool and
not about this design **[fact]**:

| mechanism | parameter seen by the design |
|---|---|
| nothing | 0 |
| `-Ptop.u_mid.u_leaf.P=7` | **0** |
| `defparam top.u_mid.u_leaf.P = 7;` in a second root module | **7** |

Icarus's `-P` reaches **root** modules only, and a hierarchical path
that names no root is dropped without a diagnostic. `defparam` from a
second elaboration root works, and works through a `generate if` as
well, which was checked separately because that is what `SYNPRE`
controls **[fact]**.

> **This is `docs/41` section 6.6's shape in a simulator, and it is the
> eleventh instance: an override that looks applied and is not.** The
> repair is not to remember it. `flow/sim_soc.sh` now reads the two arms
> of the `SYNPRE` generate — `g_synpre` and `g_synpost` — **out of the
> compiled object** and refuses to run if the wrong one is there, and
> `sw/tests` fails if that check is removed. The run's own output names
> which arm it built.

### 8.2 `set -o pipefail` turns `grep -q` into a failure

The first version of that check was `strings file | grep -q "$want"`.
`grep -q` exits on its first match, `strings` dies of SIGPIPE, and
`pipefail` reports the pipeline as failed — **so the check failed
exactly when it should have passed**, and the run aborted on a correct
build. It is `grep -qa` on the file now, with the reason in the script.
Recorded because it is a check that *appeared* to work: it had already
correctly rejected one bad build before it wrongly rejected a good one.

---

## 9. The evidence for the change itself

**`SYNPRE` replaces a function of the decoder's syndrome with a function
of an encoder's output, so the logical obligation is new and `docs/44`'s
C5 does not discharge it.** C5 states that the fast correction equals
the decoder's correction, **for the decoder's own syndrome**. `SYNPRE`
does not change what is done with the syndrome; it changes where the
syndrome comes from. And that substitution is only sound if
`hw/rtl/secded_enc.v`'s H and `hw/rtl/secded_dec.v`'s H are the same
matrix — which they are **two separate copies of**, by
`secded_dec.v`'s own header: *"the H matrix constants are identical to
secded_enc.v (each module stays self-contained)"*. **Nothing in this
repository had compared them.** `formal/secded.sby` proves the codec end
to end, which any self-consistent pair of matrices satisfies.

### 9.1 Two new properties, proved

`hw/soc/formal/regfile_secded_props.v` gains:

- **C6 — `enc(stored_data).check_out ^ stored_chk == dec.syndrome`**,
  over a free 32-bit word and a free 40-bit error vector, with no guard
  on the error weight.
- **C7 — the hoisted read path returns the same word**:
  `stored_data ^ pre_mask == dec.data_out[31:0]`. It follows from C5 and
  C6 and is stated anyway, because it is the sentence this document
  relies on.

| task | engine | result |
|---|---|---|
| `bmc`, depth 4 | `smtbmc yices` | **PASS** |
| `prove`, k-induction | `smtbmc yices` | **PASS**, basecase and induction |
| `prove_abc` | `abc pdr` | **PASS** |
| `cover` | `smtbmc yices` | **PASS, 9 of 9 reached** (was 7 of 7) |

**[fact, `hw/soc/formal/*/PASS`]**. The two new covers are
`pre_syn != 0` and `pre_mask != 0`, so C6 and C7 are not holding
vacuously on a harness where the hoisted syndrome is always zero.

**And C6 is falsifiable, which was checked rather than assumed.** With
one constant XORed into `pre_syn`, `prove` returns **FAIL for basecase**
naming `assert (pre_syn == syn)` by line **[fact]**. The mutation was
reverted and the four tasks re-run.

### 9.2 The behavioural evidence, re-run

| | shipped read path | `SYNPRE = 1` |
|---|---|---|
| register-file cocotb suite | 6 of 6 pass | **6 of 6 pass** |
| its 124-injection campaign | 107 CORRECTED, 17 MASKED, 0 SDC, 0 DETECTED, 25 draws into the check field | **identical, every field** |
| whole-SoC run: checks / fail mask | 0x16 / 0 | **0x16 / 0** |
| watchdog stage 1 at cycle | 174,128 | **174,128** |
| core asleep after | 185,443 cycles | **185,443 cycles** |
| console | 587 characters, 0 framing errors | **587, 0** |
| ROM image | `md5 86ee78b9…` | **the same image** |
| the two `sim.log` files | | **differ in one line, which is the output path** |

**[fact]**. The whole-SoC rows are from a run whose compiled object was
checked to contain `g_synpre` and not `g_synpost` — section 8.1 is why
that sentence is in this table.

---

## 10. The checkers, re-audited

`docs/41` section 6.6 counts the occasions on which a green result in
this repository was read as wider than the thing it examined, and
`docs/47` section 7 configured four of them out before its first run.
**Every one of those keys is carried into `syn1` and `syn2` unchanged**,
because both runs are `hw/soc/pnr/config.json` itself with two
command-line overrides in `syn1` and none in `syn2` — `resolved.json` for
`full2` and `syn1` agree on all four `*_VIOLATION_CORNERS`, on
`TIME_DERATING_CONSTRAINT`, on `MAX_CAPACITANCE_CONSTRAINT: null`, on
`DIE_AREA`, on `PL_TARGET_DENSITY_PCT` and on `MAX_FANOUT_CONSTRAINT`
**[fact]**.

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
                                 corners measured 3, violating all three
GATES  Checker.MaxCapViolations  [corners] MAX_CAP_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, violating all three

    17 of 19 in-flow checkers gate fully.
    NOT gating in full: Checker.LintWarnings, Checker.WireLength
```

**[fact, `checker_audit.py hw/soc/pnr/runs/syn2`, exit 0]** — **17 of
19, the same as `docs/47`'s `full3` and `docs/48`'s `cap2`**, and the
same two exceptions: `Checker.WireLength` with no threshold in either
PDK and `Checker.LintWarnings` behind `ERROR_ON_LINTER_WARNINGS`.

> **THE ROW THAT MATTERS IS `Checker.HoldViolations`, AND IT IS WHY THE
> AUDIT WAS RE-RUN.** Section 6.3 reports **`all 0` on hold, at three
> corners, on a run where `docs/47`'s configuration reported −0.2015 ns
> on 3 endpoints and failed.** An `all 0` reading is worth exactly as
> much as the gate behind it, and this repository has published four
> claims that a corner closes from runs where nothing was checking.
> **The audit confirms `HOLD_VIOLATION_CORNERS = ["*"]` and three
> corners measured — the identical binding under which `full3` failed.**
> The number moved; the gate did not.
>
> **And the same audit is what stops the setup result from being read
> as better than it is.** `Checker.SetupViolations` examined three
> corners and names `nom_slow_1p08V_125C`. **This run fails setup, on a
> gate that was watching, at a number that is `docs/47`'s number.**

The derate is audited where `docs/31` sections 3.2 and 10.3 say it can
be — not in `resolved.json`, which records the integer `5` either way —
and `syn2`'s flow-written SDC carries `set_timing_derate -early 0.9500`
and `-late 1.0500`, with **no `set_max_capacitance` and no
`set_max_transition`**, which is what makes section 6.3's max-cap
comparison a comparison against one limit **[fact]**.

**The flow exits non-zero naming three criteria where `docs/47`'s named
four:**

```
One or more deferred errors were encountered:
Setup violations found in the following corners:
* nom_slow_1p08V_125C
Max Slew violations found in the following corners:
* nom_fast_1p32V_m40C
* nom_slow_1p08V_125C
* nom_typ_1p20V_25C
Max Cap violations found in the following corners:
* nom_fast_1p32V_m40C
* nom_slow_1p08V_125C
* nom_typ_1p20V_25C
```

**[fact, `hw/soc/out/s49-pnr-syn2.log`]** — hold is absent because it
passed; max slew has gained a corner because it got worse.

---

## 11. The target, and the one thing that would reach it

### 11.1 What the binding path is made of, and what a register would do to it

`docs/48` section 6.2 decomposed the binding path and this document
re-reads the same three numbers, because they are what decides whether
anything short of an RTL change to the memory interface can reach 20 ns:

| | ns |
|---|---:|
| clock to the macro's `A_CLK` | 1.8834 |
| **macro read arc `A_CLK → A_DOUT[15]`, the vendor's Liberty** | **9.5277** |
| 26 standard-cell stages to the register-file check bit | 13.1261 |
| arrival | **24.5371** |
| required | 21.3342 |
| **slack** | **−3.2029** |

**[fact, `full3/19-openroad-stapostpnr/nom_slow_1p08V_125C/max.rpt`]**

**The macro arc alone is 47.6 % of the 20 ns period and no design
change touches it.** It is a hard-macro Liberty number; there is no
faster version of that macro in this PDK and `docs/12` section 7.5
already records that rotating or re-characterising it is out of reach
here.

> **AND THAT IS WHY ONE FLIP-FLOP, IN THE RIGHT PLACE, IS THE ONLY
> MECHANISM MEASURED ANYWHERE IN `docs/47`, `docs/48` OR THIS DOCUMENT
> THAT WOULD REACH 20 ns.** Registering the RAM's read data at the
> macro's output splits that arrival in two, and on the report's own
> decomposition **both halves close with margin**:
> **`clk → A_CLK → A_DOUT` arrives at 11.4111 against 21.3342 required
> — +9.9231 ns** — and **a new launch flop through the same 26 stages
> arrives at 15.0095 — +6.3247 ns** **[estimate, arithmetic on the four
> measured rows above; it assumes the new flop's own clock latency and
> setup are the ones already in this report, and it does not model the
> placement of a register that does not exist]**.
>
> **What it costs is not silicon, it is a cycle**, and the cycle is what
> makes it an RTL change rather than a floorplan one:
> `hw/soc/rtl/soc_mem_sram.v` returns `rvalid_o` one cycle after `req_i`
> and `hw/soc/rtl/soc_bus.v`'s rule S1 and the whole fabric protocol are
> written against that. **This document did not build it and does not
> claim it works**; it claims the arithmetic on the binding path says
> where the 3.2029 ns is and that no other measured lever is in that
> place.

### 11.2 So is 50 MHz still the right target?

`docs/48` section 7a already refused to revise it and gave the reason:
`docs/02`'s architecture table states the clock target as a **range,
"25–50 MHz, easily met"**, 50 MHz entered the project as the **Tiny
Tapeout pilot's declared clock** (`docs/06`, and `docs/15` measured the
pilot at 51.6 MHz against the 50 MHz `tt/info.yaml` declares), **and no
document in this repository derives a throughput requirement from the
clock** — so revising 50 to 43 would be revising it against nothing.
**None of that has changed and this document does not revise it
either.** What this document adds is the two things that make the
question sharper than it was.

**First, the target's provenance is now measurably inapplicable.**
`docs/15`'s 50 MHz is the closing frequency of a Tiny Tapeout tile with
**no SRAM macro in it at all**; `soc_top` has **six**, and section 11.1
measures that one of them contributes **9.5277 ns — 47.6 % of the
period — on a single arc that no design change can shorten**. A clock
target inherited from a design whose critical path had no macro in it is
not evidence about a design whose critical path is half macro. **That is
an argument for deriving the target rather than for lowering it**, and
this document is careful about the difference: 43.10 MHz is inside
`docs/02`'s stated range either way, so nothing is currently violated
except a number nobody derived.

**Second, the consequence for `docs/05` is stateable and it is small.**
`docs/05` section 3.4's four mission profiles — always-on bus-telemetry
health monitoring with wake-on-anomaly, event-camera payloads,
attitude-relevant event detection faster than a ground loop, and
long-idle transfer phases — are **all event-driven and none of them is
specified in cycles** **[fact, they are prose in that document]**. Three
of the four are explicitly *sparse* or *idle-dominated*, which is the
whole architectural argument for this part; the one with a latency
requirement states it as "faster than a ground loop", which is seconds
to minutes and not nanoseconds.

> **A 13.8 % clock shortfall is a 13.8 % throughput shortfall on a
> workload nobody has sized, against mission profiles whose stated
> requirement is that the part be idle most of the time** **[estimate,
> from `docs/05` section 3.4's text]**. **That is not a reason to write
> 43 MHz on a datasheet and it is not a reason to spend a pipeline stage
> either — it is a reason to size the workload**, and the obligation
> belongs where `docs/48` put it: `docs/09` or `docs/15` has to say what
> 43.10 MHz costs the workload before either number is published.
> Section 14 item 1 carries it.

---

## 12. What this does NOT cover

- **`SYNPRE` was measured at ONE point in the flow's configuration
  space**, `docs/47`'s floorplan with `docs/47`'s keys. It was not
  combined with a different `PL_TARGET_DENSITY_PCT`, a different
  channel, a different `abc -D`, or a resynthesis at a different clock
  target. Section 7 gives the reason for the one combination that was
  considered and declined; the rest were not considered.
- **The 2,684 extra cells were not placed twice.** One netlist, one
  placement, one clock tree, one routing solution. `docs/44` section 5.2
  measured this flow's mapper noise at about 0.4 ns on a 22,000-cell
  design and nothing here re-measured it at 30,000; the sign-off delta
  in section 6 is reported against that figure and not against a
  repeated run of the same configuration, which does not exist.
- **`SYNPRE` protects nothing new and detects nothing new.** It is a
  timing restructuring of a correction path, proved equal (section 9),
  and it changes no fault-injection outcome — which is why the campaign
  in section 9.2 is a check that nothing moved and not evidence of
  anything gained.
- **THIS IS STILL NOT A PHYSICAL SIGN-OFF.** `RUN_MAGIC_DRC`,
  `RUN_KLAYOUT_DRC`, `RUN_KLAYOUT_XOR` and `RUN_LVS` are 0, for the
  reason `docs/12` sections 7.5 and 8 measured and `docs/47` section 9
  and `docs/48` section 8 restate: Magic DRC 1,106,478, KLayout DRC
  2,316 and Netgen LVS 359 over ONE RM_IHPSG13 macro, every error inside
  the macro. Nothing here is evidence that this layout is
  manufacturable.
- **The fast corner's macro Liberty is still characterised at −55 C
  against −40 C for the cells** (`docs/12` section 6.4a), so every hold
  result here carries the same 15 C mismatch `docs/47` section 9 states.
- **`Yosys.EQY` is off, there is still no gate-level simulation of
  `soc_top`, and the boot ROM still has no contents.** `docs/47`
  sections 4.4 and 9; unchanged and not addressed. The formal properties
  of section 9.1 are about the CODE and the two matrices, not about the
  netlist that was placed.
- **The behavioural evidence is RTL simulation.** The whole-SoC run and
  the register-file campaign of section 9.2 run on
  `hw/soc/rtl/ibex_regfile_secded.v` and `hw/soc/gen/`, not on the
  hardened netlist. Nothing has ever simulated `soc_top`'s netlist.
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
- **`design__violations` still reads 0** on every run in this document,
  including the ones that fail setup; `docs/23` section 3.2's finding
  reproduced a fourth time.

---

## 13. Corrections to earlier documents

- **`docs/48` section 7a and section 11 item 1 say `SYNPRE` "acts on the
  SECDED ENCODER that terminates the binding path". IT DOES NOT.**
  `SYNPRE` restructures the read-side syndrome, in front of the read
  multiplexer. The encoder that terminates the binding path is
  `u_enc_wr` on the **write** port, one instance, already in front of
  the storage and with nothing to hoist it past. The two cones are
  disjoint and this document's whole result follows from that. Section
  3.2.
- **`docs/48` section 11 item 1's ranking is therefore wrong for the
  reason it gives, and right for a different one.** `SYNPRE` is worth
  measuring — it is the largest single-change improvement measured at
  any mid-flow stage on this design (section 5) — but not because it is
  "the right size against a 3.2029 ns gap". It is on the wrong 1,559
  endpoints for that gap. Section 3.1.
- **`docs/44` section 5.5's 1.8677 ns is measured against `FASTCORR = 0`
  and not against the shipped read path.** Against `FASTCORR = 1`, which
  is what ships, `SYNPRE` is worth **1.6084 ns** on the same table.
  `docs/44` states both rows and does not take the second difference;
  this is not an error in that document, but a reader who reaches for
  "1.87 ns" as the value of adopting `SYNPRE` today is reaching for the
  wrong 0.26 ns. Section 2.
- **`docs/48` section 6.2's "22 `sg13g2_xnor2_1` in the reported path"
  counts REPORT LINES, not cells.** The path carries **11** `xnor2`
  cells; each appears twice in `report_checks` output, once at its input
  pin and once at its output **[fact, both counts made]**. Recorded
  because 22 XOR levels and 11 XOR levels are different diagnoses of the
  same encoder.
- **`docs/41` section 6.6's list gains an ELEVENTH entry, and this one
  is in the simulator.** `iverilog -P` on a hierarchical path that names
  no root module elaborates, exits 0, warns about nothing and changes
  nothing. Unlike the tenth, this one **is** repaired rather than only
  reported: `flow/sim_soc.sh` checks the compiled object and `sw/tests`
  checks that it checks. Section 8.1.
- **`docs/23` section 3.2's finding that `design__violations` does not
  aggregate** is reproduced a fourth time.

---

## 14. What the next block should be

1. **The memory read register, and it is now first.** Section 11.1's
   arithmetic is the only mechanism measured in `docs/47`, `docs/48` or
   this document that puts both halves of the binding path inside 20 ns,
   and it is the "RTL change to the memory interface" those documents
   kept naming without pricing. **What has to be established before it
   is built**: what an extra cycle of read latency does to
   `hw/soc/rtl/soc_bus.v`'s rule S1 and to Ibex's load/store unit, which
   is a protocol question and not a timing one, and whether
   `hw/soc/formal/soc_bus.sby` still passes with the latency changed.
   The timing case is arithmetic on a measured report; the protocol case
   is the work.
2. **What 43.10 MHz costs the workload.** `docs/48` section 7a raised
   it, this document's section 11.2 sharpens it — the target's
   provenance is a tile with no SRAM in it, and this design's critical
   path is **47.6 % macro arc** — and neither document can answer it,
   because answering it is `docs/09`'s or `docs/15`'s to do. **Until it
   is answered, no frequency should be written on a datasheet, 43 or
   50.**
3. **`mtime`.** Ranked first by `docs/41` section 7.4 and `docs/44`
   section 11, second by `docs/43`, third by `docs/45`, fourth by
   `docs/47`, second by `docs/48` — and this document measures that
   **128 of the 1,559 read-address endpoints land on it** and that it is
   still on the post-CTS binding path in **both** netlists (section 5).
   A 64-bit free-running counter at the far end of a broadcast bus is
   the most-deferred item in this record.
4. **The capacitance constraint as a hold-and-slew fix.** `docs/48`
   section 11 item 3, untouched here: 0.1080 pF and 0.1800 pF are the
   next two of the library's own characterisation loads and neither has
   been run. This document declined to compose with 0.0648 pF for the
   reason in section 7, which is a statement about 0.0648 pF and not
   about the search.
5. **ECC on the memories** and **how the boot ROM gets its contents** —
   `docs/47` section 11 items 1 and 2, `docs/48` section 11 item 5,
   untouched here. The second still decides whether this part can boot.
6. **A gate-level simulation of `soc_top`**, still open, still blocked
   on item 5.

**And one thing that should NOT be next: `SYNPRE` again, in this
configuration.** Section 6 measures what it is worth at sign-off on this
floorplan and the answer is inside the noise, for +6.9 % of the
standard-cell area. **The reversal condition is specific and it is item
1**: if the memory read is registered and the binding path becomes the
read-address group, `SYNPRE` acts directly on the new worst path and
this measurement has to be redone — the number in section 5 says it
would be worth having then. `docs/44` section 5.5 wrote a reversal
condition when it declined this; so does this document.

---

## 15. Files touched

| File | Change |
|---|---|
| `hw/soc/flow/syn_soc_top.sh` | `IBEX_RF_SYNPRE` — one `chparam`, defaulting to 0 and emitting nothing at 0. The netlist at 0 is byte-identical to `docs/47`'s |
| `hw/soc/flow/sim_soc.sh` | `SOC_RF_SYNPRE` — a generated `defparam` in a second elaboration root, **and the check that it took effect**, which is section 8.1's finding turned into a refusal |
| `hw/soc/formal/regfile_secded_props.v` | properties **C6** and **C7**, two covers, and the header paragraph saying why C5 does not imply them |
| `sw/tests/test_soc_regfile_guards.py` | the `SYNPRE` guard extended to four flows and three defaults; one new test with three mutation-tested assertions |
| `docs/49-synpre-and-the-binding-path.md` | this document |
| `docs/00-index.md` | one row |

**No file under `hw/rtl/`, `hw/tb/`, `tt/`, `formal/`, `hw/openlane/` or
`hw/soc/rtl/` was modified** **[fact, `git status`]**. In particular
**`hw/soc/rtl/ibex_regfile_secded.v` is untouched**: `SYNPRE` and its
`g_synpre` block have been in that file since `docs/44` and this
document only reached them.

---

## 16. Reproducing this

```
V=$HOME/Documents/caravel-lif-crossbar/.venv-flow/bin/python
export PDK_ROOT=$HOME/.ciel

# ---- section 2: the instrument, before anything is claimed to move ----
SOC_MEM=sram hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s49-repro-sram
diff hw/soc/out/s49-repro-sram/soc_top.netlist.v \
     hw/soc/out/s47-sram/soc_top.netlist.v          # identical
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/full3   # -3.2029 / 2003
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/full3   # 17 of 19

hw/soc/flow/syn_regfile.sh hw/soc/out/s49-regfile        # docs/44 5.4's areas
hw/soc/flow/sta_regfile.sh hw/soc/out/s49-regfile        # ... and arrivals
TAGS="harden1 synpre" hw/soc/flow/sta_regfile.sh hw/soc/out/s49-regfile
#   harden1 slow 8.0617, synpre slow 6.4533

# ---- section 4: the netlist ------------------------------------------
SOC_MEM=sram IBEX_RF_SYNPRE=1 hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s49-synpre
#   30,249 cells, 3,085 flops, 423,415.4148 um2
SOC_MEM=sram hw/soc/flow/sta_soc_top.sh 20 hw/soc/out/s49-synpre

# ---- sections 5 and 6: the layout ------------------------------------
SKIP="-S Yosys.Synthesis -S Checker.YosysUnmappedCells
      -S Checker.YosysSynthChecks -S Checker.NetlistAssignStatements"
SYN_NETLIST=$PWD/hw/soc/out/s49-synpre/soc_top.netlist.v \
hw/soc/flow/pnr_soc_top.sh syn1 --overwrite -F Yosys.JsonHeader $SKIP \
    -i hw/soc/pnr/state/syn_soc_top.state.json \
    -c RUN_POST_GRT_DESIGN_REPAIR=false -c RUN_POST_GRT_RESIZER_TIMING=false
SYN_NETLIST=$PWD/hw/soc/out/s49-synpre/soc_top.netlist.v \
hw/soc/flow/pnr_soc_top.sh syn2 --overwrite -F OpenROAD.GlobalRouting \
    -i hw/soc/pnr/runs/syn1/30-openroad-stamidpnr-2/state_out.json

$V hw/openlane/signoff_report.py hw/soc/pnr/runs/syn2
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/syn2

# ---- section 9: the evidence -----------------------------------------
cd hw/soc/formal && make regfile && cd ../../..    # bmc, prove, prove_abc, cover
cd hw/soc/tb/cocotb && \
  make -f Makefile.ibex_regfile_secded \
       EXTRA_COMPILE_ARGS=-Pibex_register_file_ff.SYNPRE=1 \
       SIM_BUILD=sim_build_regfile_synpre \
       COCOTB_RESULTS_FILE=results_regfile_synpre.xml && cd ../../../..
hw/soc/flow/sim_soc.sh              hw/soc/out/s49-sim-base
SOC_RF_SYNPRE=1 hw/soc/flow/sim_soc.sh hw/soc/out/s49-sim-synpre
diff hw/soc/out/s49-sim-{base,synpre}/sim.log   # one line, the path

# ---- the guards ------------------------------------------------------
.venv/bin/python -m pytest sw/tests/test_soc_regfile_guards.py
```

`hw/soc/out/`, `hw/soc/pnr/runs/`, `hw/soc/pnr/config.resolved.json` and
`hw/soc/tb/cocotb/sim_build*/` are gitignored.
