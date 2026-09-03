# 54 — The 2,316, examined: what the KLayout deck is objecting to inside RM_IHPSG13

Status: complete. `docs/12` section 8.2 named two exits from the
RM_IHPSG13 no-go — a Magic tech-file change, or moving sign-off to the
KLayout deck — and rejected the second in one clause: *"the KLayout deck
also returns 2,316 errors, so it is not a free exit either."* It never
examined those 2,316. This document examines them.

Convention: **[fact]** = measured in this environment or read out of the
installed PDK; **[estimate]** = derived or judged; **[assumption]** =
chosen. Every number below was measured for this document unless it is
attributed to another one.

**The short version.**

- **The 2,316 reproduces exactly, three ways.** From the retained
  `macro-03` report; from a fresh run of the same deck on the same GDS
  eight days later; and — this is new — from the same deck run on the
  **bare vendor macro GDS on its own**, with none of this project's flow
  anywhere near it. All three give 1,022 / 1,022 / 272. Section 2.
- **2,316 is not 2,316, and the caveat runs the opposite way from
  Magic's.** `Sdiod.d` and `Sdiod.e` flag the **identical 1,022
  polygons** — set intersection 1,022, symmetric difference 0 — so the
  headline double-counts. And the deep-mode number is a *hierarchically
  deduplicated marker count*: the same deck in flat mode on the same
  file returns **122,814**, a factor of **53.0**. Magic's raw count
  overstates by 3-4x; KLayout's understates by 53x. Section 3.
- **`docs/12`'s "nearly three orders of magnitude" disagreement between
  the two decks is mostly an artefact of that comparison.** Put on a
  comparable footing the gap is a factor of **4 to 9**, not 10^3, and
  the two decks **corroborate each other** on the contact-enclosure
  rule. Section 3.3.
- **`Sdiod.d`/`Sdiod.e` are an artefact, and the case does not depend on
  which deck is authoritative.** They check a Schottky diode. The macro
  contains no Schottky diode and **no drawn nBuLay at all** — the deck's
  own log line is `nbulay_drw has 0 polygons`. The layer the rule
  measures against is **synthesized from NWell** by the deck. Restrict
  the rule to the drawn layer and it returns **0**. Worse, the shapes it
  reports are **boolean-clip remnants**: no drawn contact in the file
  has any dimension below 0.16 um, and **2,303 of the 9,275 flagged
  shapes do**, down to 0.16 x 0.01 um. Section 4.
- **`Cnt.c.digibnd` is real geometry in a contested scope, and it is not
  waivable on this evidence.** 99.93 % of the errors sit at exactly
  **0.02 um** Activ enclosure against a 0.05 um requirement — systematic,
  not noise, and flat and deep agree, so it is not a hierarchy artefact.
  But all of it is inside a **vendor-drawn SRAM marker (layer 25/0,
  19,008 polygons, 66.9 % of the macro)** that this deck **reads and then
  never uses in any rule**. Section 5.
- **The prompt's hypothesis about `digibnd` is wrong in direction, and
  that is worth stating.** DigiBnd is a **relaxation**, 0.07 -> 0.05, not
  an extra constraint, and the macro **does** carry it. If it were absent
  these contacts would be checked at 0.07 and produce **104,285** errors
  instead of 104,264. The qualifier is helping by 21. Section 5.1.
- **Verdict: KLayout sign-off is NOT viable for these macros, and the
  deck swap is not the exit.** The deck the flow runs is the PDK's
  **main** set, which its own README calls *"thoroughly verified, tested
  ... intended for foundry precheck purposes"*. The deck that returns 0
  is the PDK's **extra/residual** set, which the same README calls
  *"not verified or tested"*. Swapping to it trades a verified deck for
  an unverified one. Section 7.
- **And DRC was never the binding constraint.** Netgen LVS returns 359
  errors whose hierarchy-name half is IHP-Open-PDK issue #239 and is not
  fixable here. A design that passes DRC and fails LVS is not signed off.
  Section 7.3.
- **`docs/12`'s NO-GO stands. Its reasoning changes.** The 2,316 is not
  "the second deck also finds the macro broken". It is two specific
  things, one of them a device-recognition misfire on a layer that does
  not exist. The macro's DRC status is *more* clearly a tooling question
  than `docs/12` concluded, and now has a mechanism attached to take
  upstream. Section 8.
- **Nothing here touches the pilot, and it structurally cannot.**
  `sg13g2_stdcell` has **zero non-square contacts and zero DigiBnd**
  **[fact, measured on the `aer_fifo` GDS]**, so both rules are inert on
  any standard-cell-only design. `docs/31`'s Magic 0 / KLayout 0 is
  unaffected. Section 9.

This document created **no run directories inside the repository** and
modified no file outside itself and its index row. All work was done in
a scratch directory against the retained `macro-03` tree and the
installed PDK, both read-only.

---

## 1. Scope, and what was read

The object under examination is one number: the `2316 KLayout DRC errors
found.` that `hw/openlane/sram_pilot/runs/macro-03` ended with, recorded
in `docs/12` sections 7.5, 7.7 and 8.1 and quoted forward into `docs/47`
section 9 as one of the three reasons the laid-out SoC has no DRC result.

Inputs, all read-only:

| Thing | Where |
|---|---|
| The retained report | `hw/openlane/sram_pilot/runs/macro-03/65-klayout-drc/reports/drc.klayout.lyrdb` |
| The design GDS it ran on | `.../macro-03/57-magic-streamout/sram_pilot.gds` |
| The vendor macro GDS | `~/.ciel/ihp-sg13g2/libs.ref/sg13g2_sram/gds/RM_IHPSG13_1P_512x32_c2_bm_bist.gds` |
| The deck the flow runs | `~/.ciel/ihp-sg13g2/libs.tech/klayout/tech/drc/ihp-sg13g2.drc` + `rule_decks/` |
| The other deck in the same commit | `.../rule_decks/sg13g2_maximal.drc` |
| The clean control | `hw/openlane/aer_fifo/runs/trial-03-signoff/57-magic-streamout/aer_fifo.gds` |

Tool and PDK are the pins of `docs/12` section 2.2: **KLayout 0.30.9**,
**IHP-Open-PDK `c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c`** **[fact]**.

Non-goals: this is not an attempt to make the macro pass, not a
re-hardening of `sram_pilot`, and not an LVS investigation. `docs/12`
section 10.2 item 5 (the KLayout LVS deck was never exercised) is still
open and this document does not close it.

---

## 2. Reproduction, before interpreting anything

### 2.1 The retained report

`drc.klayout.lyrdb` is 758,064 bytes of XML and survives in the
`macro-03` tree. Parsed directly **[fact]**:

| Quantity | Value |
|---|---|
| Rule categories declared by the deck | **173** |
| Categories with a nonzero count | **3** |
| Categories with zero | **170** |
| Total items | **2,316** |
| `Sdiod.d` | 1,022 |
| `Sdiod.e` | 1,022 |
| `Cnt.c.digibnd` | 272 |

`reports/drc.klayout.json` — the file the flow's metric is scraped from
— agrees, with `"total": 2316`. Distinct cells named by the items:
**121** counting orientation variants (`:r0`, `:m90`), **57** counting
base cell names. `docs/12` section 7.5's "57 distinct cells" is the
second of those and is correct **[fact]**.

### 2.2 Fresh re-run of the same deck

The `macro-03` step's `COMMANDS` file records exactly what LibreLane
invoked. Re-issued verbatim on 2026-09-03 against the same GDS:

```
klayout -b -zz -r <PDK>/libs.tech/klayout/tech/drc/ihp-sg13g2.drc \
  -rd input=<macro-03>/57-magic-streamout/sram_pilot.gds \
  -rd topcell=sram_pilot -rd report=repro_pilot.lyrdb \
  -rd no_recommended=True -rd run_mode=deep -rd thr=20
```

Result: **1,022 / 1,022 / 272, total 2,316** — identical, in 28.9 s of
deck time **[fact]**.

### 2.3 The vendor macro, checked entirely on its own

This is the run `docs/12` did not make, and it is the one that settles
where the errors come from. The same deck, same options, pointed at the
**unmodified vendor GDS as shipped in the PDK**, top cell
`RM_IHPSG13_1P_512x32_c2_bm_bist`, with no wrapper, no standard cells,
no PDN, no routing, no fill and no Magic streamout in the picture:

**1,022 / 1,022 / 272, total 2,316** **[fact]**.

Byte for byte the same result as the full design. So `docs/12`'s "100 %
of both inside the macro" can be sharpened: **100 % of the KLayout
errors are properties of the vendor cell as shipped, and this project's
flow contributes exactly zero of them.** In particular neither the
`MAGIC_MACRO_STD_CELL_SOURCE: PDK` workaround of `docs/12` section 7.4
nor the `PDN_CFG` Metal4 fix of 7.3 is implicated.

---

## 3. What 2,316 counts, and what it does not

`docs/12` section 7.5 corrected its own Magic headline because the raw
figure is error boxes rather than distinct violations, and the report
says so in a line beneath the total. The instruction for this document
was to check whether KLayout's count has an equivalent caveat before
treating 2,316 as 2,316. **It has two, and neither is printed anywhere
in the report.**

### 3.1 The headline double-counts by construction

`Sdiod.d` and `Sdiod.e` are evaluated over the same derived layer
(section 4.1). Comparing the two categories item by item, as
(cell, geometry) pairs **[fact]**:

| Quantity | Value |
|---|---|
| `Sdiod.d` items | 1,022 |
| `Sdiod.e` items | 1,022 |
| Distinct (cell, geometry) pairs shared by both | **1,022** |
| In `Sdiod.d` only | **0** |
| In `Sdiod.e` only | **0** |

Every single flagged shape is reported twice. `docs/12`'s suspicion that
"1,022 twice is unlikely to be a coincidence" is confirmed: it is one
population of 1,022 shapes, not two of 1,022. The Schottky contribution
to the headline is **1,022 shapes, not 2,044**.

### 3.2 The deep-mode number is a marker count, not a shape count

LibreLane runs this deck with `run_mode=deep` because the PDK's
`libs.tech/librelane/config.tcl` sets it. In deep mode KLayout reports
one marker per *cell definition and orientation variant*, not per
instance. The macro is 16 kbit of replicated array; the distinction is
not small.

Same deck, same file, same options, `run_mode=flat` **[fact]**:

| Rule | deep | flat | ratio |
|---|---|---|---|
| `Sdiod.d` | 1,022 | **9,275** | 9.1 |
| `Sdiod.e` | 1,022 | **9,275** | 9.1 |
| `Cnt.c.digibnd` | 272 | **104,264** | 383.3 |
| **Total** | **2,316** | **122,814** | **53.0** |

The flat figures were independently derived before this run, by
re-implementing the three rules' derivations from the deck source in a
standalone script, and they agree to the digit **[fact]**. The
hierarchical figure is also not stable under things that should not
matter: the same three rules re-implemented alone, with fewer input
layers and therefore a differently-built deep hierarchy, return
**897 / 897 / 130** instead of 1,022 / 1,022 / 272 while the flat counts
are unchanged **[fact]**. **The deep-mode count is a property of how the
deck was assembled, not of the layout.** Any number quoted from it has
to name the deck and the mode.

Reduced to distinct violating geometry **[fact]**:

| | Distinct shapes |
|---|---|
| ContBar shapes flagged by `Sdiod.d` **and** `Sdiod.e` | 9,275 |
| Contacts flagged by `Cnt.c.digibnd` (104,264 edge pairs, ~2 per contact) | 53,284 |
| **Total distinct shapes** | **62,559** |

### 3.3 What this does to `docs/12`'s headline comparison

`docs/12` section 7.5 concluded that "two signoff decks over the same
GDS disagree by nearly three orders of magnitude", and 7.7 repeated it
as "the two decks disagreeing by 2-3 orders of magnitude". That
comparison put Magic's **flat error-box count** next to KLayout's
**hierarchical marker count**. Normalised, the gap is much smaller
**[estimate — the two tools do not emit errors on the same convention,
so no single ratio is exact; the point is the order of magnitude]**:

| Comparison | Magic | KLayout | Ratio |
|---|---|---|---|
| Raw tool output as printed | 1,106,478 boxes | 2,316 markers | **478** |
| Both flat, as the tool emits them | 1,106,478 boxes | 122,814 items | **9.0** |
| Both reduced to distinct violations | ~277,000-369,000 (`docs/12` 7.5) | 62,559 | **4.4-5.9** |

A factor of **4 to 9**, not 10^3. And the agreement is qualitative as
well as numerical: `docs/12`'s Magic histogram lists **165,888 boxes for
`Cnt.c` — "P-diffusion overlap of P-diffusion contact"**, plus 4,806 for
the N-diffusion variant. That is **the same rule** as KLayout's
`Cnt.c.digibnd`, minimum Activ enclosure of Cont. **Two independently
implemented decks flag the same geometry class in the same macro at
comparable magnitude.** That corroboration is the single most important
thing this document found about `Cnt.c.digibnd`, and it is why section 5
does not call it an artefact.

The contrast is just as informative in the other direction: **Magic's
histogram contains no Schottky rule at all.** Section 4 is why.

---

## 4. `Sdiod.d` and `Sdiod.e`: a Schottky diode that is not there

### 4.1 The rule text

From `rule_decks/feol/6_7_schottkydiode.drc`, quoted in full because the
whole argument is in five lines **[fact]**:

```ruby
contbar_nbulay = contbar.and(nbuLay_gen_nbulay)

sdiod_d_l = contbar_nbulay.without_bbox_min(sdiod_d_value.um)   # 0.30
sdiod_d_l.output('Sdiod.d', "... Min. and max. ContBar width inside nBuLay is 0.3 um")

sdiod_e_l = contbar_nbulay.without_bbox_max(sdiod_e_value.um)   # 1.00
sdiod_e_l.output('Sdiod.e', "... Min. and max. ContBar length inside nBuLay is 1.0 um")
```

Note "**Min. and max.**". This is not a minimum-dimension rule. It is a
device-formation rule: a Schottky diode is *defined* by a bar contact of
exactly 0.30 x 1.00 um inside the buried n-layer, and any bar contact
inside nBuLay that is not exactly that is not a legal Schottky diode.
`without_bbox_min` and `without_bbox_max` select shapes whose bounding
box does **not** have that dimension. Both run on the same
`contbar_nbulay`, which is section 3.1's 1,022.

The two input layers are both **derived**, and both derivations are the
problem.

### 4.2 nBuLay is synthesized from NWell, and the macro has none

From `ihp-sg13g2.drc` **[fact]**:

```ruby
nbulay_gen_sized = nwell_drw.sized(-1.495.um).sized(0.495.um)
nbuLay_gen       = nbulay_gen_sized.not(nbulay_block.join(res_drw))
nbuLay_gen_nbulay = nbuLay_gen.join(nbulay_drw)
```

`nwell_drw.sized(-1.495).sized(0.495)` is a shrink-then-grow: any NWell
region wide enough to survive a 1.495 um erosion comes back, grown by
0.495. It models a real process feature — the buried layer forms under
sufficiently wide NWell — and as modelling it is defensible. What
matters here is what it means for this file.

Measured on the vendor macro GDS **[fact]**:

| Layer | Polygons |
|---|---|
| NWell, 31/0, drawn | 37,959 |
| **nBuLay, 32/0, drawn** | **0** |
| nBuLay:block, 32/21, drawn | 0 |
| **nBuLay, synthesized from NWell** | **49** (7,595.80 um2, 9.5 % of the macro) |

The deck says so itself, on every run, in its own log:
`nbulay_drw has 0 polygons` **[fact]**.

The consequence, measured by substituting one term **[fact]**:

| `Sdiod.d` evaluated against | Errors (flat) |
|---|---|
| drawn nBuLay only (`nbulay_drw`) | **0** |
| synthesized nBuLay (`nbuLay_gen_nbulay`, what the deck uses) | **9,275** |

**Every one of the Schottky errors is measured against a layer that does
not exist in the layout.**

### 4.3 ContBar is inferred from shape, with no device marker required

```ruby
cont_nseal = cont_drw.not(edgeseal_drw)
contbar    = cont_nseal.non_squares
cont_sq    = cont_nseal.not(contbar)
```

A "ContBar" is **any contact that is not square**. The macro has
**23,959** of them **[fact]**. Nothing in the derivation asks for a
Schottky marker, a PWell:block, an nSD:block or a SalBlock. So the rule
reduces to: *any non-square contact that happens to overlap a
wide-NWell region must be exactly 0.30 x 1.00 um*.

The same PDK commit contains a second deck,
`rule_decks/sg13g2_maximal.drc`, which recognises the device properly
**[fact]**:

```ruby
dschottky_1     = Activ_and_nSD_block.ext_and(nBuLay)
schottky_pwb    = schottky_nbl1.ext_and(PWell_block)
schottky_nSDBlock = schottky_nbl1.ext_and(nSD_block)
schottky_salblock = schottky_nbl1.ext_and(SalBlock)
schottky_contbar  = schottky_nbl1.ext_and(ContBar)
```

— it requires explicitly drawn nSD:block, PWell:block and SalBlock
markers before anything is treated as a Schottky diode. And it
**implements `Sdiod.a`, `Sdiod.b` and `Sdiod.c` only. `Sdiod.d` and
`Sdiod.e` do not exist in it** **[fact]**.

### 4.4 The reported shapes are boolean-clip remnants

`contbar.and(nbuLay_gen_nbulay)` is an intersection, so it **clips**, and
the bounding-box test then runs on the remnant rather than on the drawn
contact. Measured sizes of the 1,022 reported shapes **[fact]** — every
one is 0.16 um in one dimension, which is this PDK's minimum contact
width:

| Size (um) | Shapes |
|---|---|
| 0.16 x 0.34 | 616 |
| 0.16 x 0.075 | 141 |
| 0.16 x 0.245 | 63 |
| 0.16 x 0.13 | 60 |
| 0.16 x 0.865 | 23 |
| 18 further sizes, incl. **0.16 x 0.01** | 119 |

Those fractional heights are not contacts. Confirmed directly on the
macro **[fact]**:

| Quantity | Value |
|---|---|
| Drawn ContBar shapes with **any** bbox dimension below 0.16 um | **0** |
| Clipped shapes with a bbox dimension below 0.16 um | **2,303** |
| ContBar shapes fully inside the synthesized nBuLay | 6,139 |
| ContBar shapes only **partially** overlapping it, i.e. clipped | **3,136** |

No drawn contact in the file is smaller than 0.16 um on any side, and
2,303 of the flagged shapes are. **The rule is measuring geometry that
is not in the layout.** A correctly drawn 0.30 x 1.00 um Schottky
ContBar straddling the edge of a synthesized nBuLay region would be
flagged by this rule too.

### 4.5 Verdict on `Sdiod.d`/`Sdiod.e`

**Artefact.** Six independent reasons, and — this is the important part
— **the first, second and fourth are facts about the layout and the
arithmetic, so the verdict does not depend on which deck one considers
authoritative**:

1. The macro contains no drawn nBuLay (deck's own log: 0 polygons).
2. Restricting the rule to the drawn layer returns 0.
3. Device recognition is "any non-square contact", with no Schottky
   marker required.
4. 2,303 reported shapes are smaller than any drawn contact in the file;
   3,136 are known partial overlaps that the boolean clipped.
5. The PDK's other deck does not implement these two rules and derives
   the Schottky ContBar from three explicit markers.
6. Magic's independent deck reports no Schottky rule at all
   (`docs/12` 7.5 histogram).

The rule is well-formed for the device it was written for. It is being
applied to a memory macro that uses bar contacts over a large well for
ordinary reasons, and it misfires.

---

## 5. `Cnt.c.digibnd`: real geometry, contested scope

This one is not an artefact and this section does not claim it is.

### 5.1 The qualifier is a relaxation, not a constraint

From `rule_decks/feol/5_14_cont.drc` **[fact]** — two rules, one pair of
complementary scopes:

```ruby
cnt_c_l = cont_sq.not(digibnd_drw).enclosed(activ_drw, 0.07.um, euclidian)
cnt_c_l.output('Cnt.c', "5.14. Cnt.c Min. Activ enclosure of Cont is 0.07 um")

cnt_c_l = cont_sq.and(digibnd_drw).enclosed(activ_drw, 0.05.um, euclidian)
cnt_c_l.output('Cnt.c.digibnd', "8.1.2. ... (Inside DigiBnd) is 0.05 um")
```

Outside the digital boundary a contact needs 0.07 um of Activ around it;
inside, 0.05. **DigiBnd loosens the rule.**

The working hypothesis this document was given — that `digibnd` names a
marker a hard macro may legitimately not carry, so the rule is being
applied outside its context — **is wrong in direction, and measurably
so.** The macro **does** carry DigiBnd: **21,171 polygons on layer 16/0**
**[fact]**. And the counterfactual runs the other way **[fact]**:

| Scenario | Errors (flat) |
|---|---|
| As the deck runs it: contacts inside DigiBnd, at 0.05 | 104,264 |
| `Cnt.c`: contacts outside DigiBnd, at 0.07 | **0** |
| If DigiBnd did not exist: all contacts at 0.07 | **104,285** |

Removing the marker would make things *worse by 21*. The relaxation is
being granted and the geometry misses anyway.

### 5.2 The geometry, measured

Every reported error is an edge pair whose separation is the achieved
enclosure. Across all 104,264 **[fact]**:

| Achieved Activ enclosure of Cont | Errors |
|---|---|
| 0.01 um | 36 |
| **0.02 um** | **104,192 (99.93 %)** |
| 0.03 um | 36 |

Against a 0.05 um requirement. This is a **single systematic constant**,
not a distribution — one bitcell-level construct replicated across the
array, drawn at 0.02 um enclosure. 53,284 distinct contacts, roughly two
deficient sides each.

Flat and deep agree on the flat count, so this is **not** a hierarchy
artefact, and there is no boolean clipping in this rule's derivation, so
it is not a section 4.4 artefact either. **The enclosure really is
0.02 um.**

### 5.3 The macro carries an SRAM marker, and this deck discards it

`rule_decks/layers_def.drc` line 386 **[fact]**:

```ruby
sram_drw = get_polygons(25, 0)
count = sram_drw.count
logger.info("sram_drw has #{count} polygons")
```

Layer 25/0 is `SRAM.drawing` in the PDK's own `sg13g2.lyp`. Those three
lines are **the only references to it anywhere in `ihp-sg13g2.drc` or
its `rule_decks/`** — it is read, counted, logged, and **never used by a
single rule** **[fact, grepped over the whole deck]**.

The vendor drew it. Measured on the macro **[fact]**:

| Quantity | Value |
|---|---|
| SRAM marker polygons (25/0) | **19,008** |
| SRAM marker area | 53,416.91 um2 |
| Macro GDS extent | 79,813.64 um2 |
| **Fraction of the macro marked SRAM** | **66.9 %** |
| SRAM marker bounding box | (0, 45.44) - (416.64, 191.34) |

The other deck in the same PDK commit uses it. `sg13g2_maximal.drc`
**[fact]**:

```ruby
Act_Nsram = Activ.ext_not(SRAM)
Act_Nsram_or_Activ_mask = Act_Nsram.ext_or(Activ_mask)
...
Cont_SQ.ext_not(SVaricap_or_trans_bip)
       .ext_enclosed(Act_Nsram_or_Activ_mask.ext_and(DigiBnd), 0.05.um, ...)
   -> output("Cnt.c.Digi", "Min. Activ enclosure of Cont inside DigiBnd = 0.05")
```

The enclosing layer is Activ **minus SRAM**, which takes SRAM-marked
contacts out of the check. Substituting that one term into the main
deck's own expression, everything else identical **[fact]**:

| Enclosing layer | Errors (flat) |
|---|---|
| `activ` — what the main deck uses | **104,264** |
| `activ.not(sram)` — what the maximal deck uses | **0** |

All 104,264 are inside SRAM-marked geometry. Not most: all.

### 5.4 The rule variant is undocumented and its value is a fallback

Four independent signs that `Cnt.c.digibnd` is not a finished part of
the rule set **[fact]**:

1. It is **the only one of 374 rule-value keys** absent from the
   technology rule table
   `libs.tech/klayout/python/sg13g2_pycell_lib/sg13g2_tech_mod.json`.
   Set difference of the two JSONs is exactly `['Cnt_c_digibnd']`.
2. Its 0.05 therefore comes from the deck's own fallback,
   `rule_decks/sg13g2_tech_default.json`.
3. The deck **warns about it on every run**: `The following rules values
   were missing in tech json and default values were used: -
   Cnt_c_digibnd`. That line is in the `macro-03` log.
4. It appears in **neither** `docs/main_rules.md` **nor**
   `docs/extra_rules.md` — the PDK's own two rule tables. `Cnt.c` is
   documented at 0.07; there is no digibnd row. (`Sdiod.d` and `Sdiod.e`
   *are* documented, in `main_rules.md`.)

### 5.5 Verdict on `Cnt.c.digibnd`

**Real geometry; scope contested; not waivable on this evidence.**

What is established: the contacts are drawn at 0.02 um enclosure; the
geometry is entirely inside a marker the vendor drew to say "this is
SRAM"; the deck the flow runs ignores that marker; the other deck in the
same PDK honours it and returns 0; and Magic's independent deck flags
the same rule class on the same geometry.

What is **not** established, and this is the honest limit: **whether
0.02 um is a qualified SRAM design rule.** A vendor drawing a marker is
not the same as a foundry qualifying the geometry underneath it. Two
decks in one PDK commit disagree about scope and nothing in the
installed files says which one IHP treats as authoritative for sign-off.
A rule that 53,284 contacts miss by 60 % of its requirement is not
something this project can waive on the strength of a marker layer.

**This document does not recommend waiving `Cnt.c.digibnd`.** It
recommends asking upstream, and section 8.2 says exactly what to ask.

---

## 6. The other deck, run

Since section 5.3 turns on what `sg13g2_maximal.drc` does, it was run
rather than only read. Deep mode, same KLayout, same PDK **[fact]**:

| Input | Rules evaluated | Errors | Deck time |
|---|---|---|---|
| Vendor macro GDS, standalone | **371** | **0** | 92.5 s |
| `macro-03`'s full `sram_pilot.gds` | **371** | **0** | 847.6 s |

Zero in all 371, including every rule Magic complained about in
`docs/12` 7.5 — `NW.c`, `NW.c1`, `NW.d`, `NW.d1`, `Gat.c`, `M2.d`,
`LU.d`, `LU.d1` — and `Cnt.c.Digi`, all ten `CntB.*`, and
`Sdiod.a/b/c`.

**Positive control, because a deck that reports zero has to be shown
capable of reporting nonzero.** A four-shape GDS was built with two
deliberate violations: two Metal1 rectangles 0.01 um apart, and a
0.16 x 0.16 contact inside a 0.4 x 0.4 Activ with 0.02 um enclosure. The
maximal deck on that file reports **5 errors** — `M1.c` 1, `M1.c1` 1,
`Cnt.h` 1, `OffGrid.Metal1` 2 **[fact]**. The zeros above are real
results, not a silent no-op.

**And this is where the finding has to be stated against itself.** It is
tempting to read "the other deck returns 0" as "the macro is clean". The
PDK's own README does not support that reading **[fact, quoted]**:

- **Main rule set** — `ihp-sg13g2.drc`, the deck LibreLane runs, the one
  that returns 2,316: *"contains the essential DRC rules that are
  required for baseline verification. All rules in this category have
  been thoroughly verified, tested, and optimized for performance. This
  rule set is intended for foundry precheck purposes."*
- **Extra rule set** — `sg13g2_maximal.drc`, the deck that returns 0:
  *"additional residual rules that are not part of the main set ...
  Please note that these rules have not been verified or tested and may
  be slower."*

The maximal deck is not a superior deck. It is the **residual** set, and
the PDK's own `run_drc.py` runs **both** by default
(`run_check_by_flag(not args.disable_extra_rules, "sg13g2_maximal")`), so
a complete PDK DRC run is main + maximal = 2,316 + 0 = **2,316**.

What the maximal run establishes is therefore narrower than it first
looks, and is worth stating precisely: **the two decks shipped in one
PDK commit implement the same rule numbers with different scopes**, and
the difference is not stylistic — it is an SRAM exemption and a Schottky
device-recognition condition, both of which are exactly the two things
that produce the 2,316. That internal inconsistency is the finding.
Which deck is right is not decidable from here.

---

## 7. Verdict: is KLayout sign-off viable for these macros?

**No.** Three reasons, in order of how hard they are to argue with.

### 7.1 The exit `docs/12` named is technically available and is a downgrade

`KLAYOUT_DRC_RUNSET` is an ordinary LibreLane configuration variable —
the PDK sets it at `libs.tech/librelane/config.tcl` line 55, and
`librelane/steps/klayout.py` reads it with no PDK-specific special-casing
**[fact]**. Pointing the flow at a different deck is a one-line config
change and needs no fork.

But the deck that returns 0 is the unverified residual set (section 6).
Making it the sign-off deck would replace the PDK's verified,
precheck-intended rule set with one its own documentation says has not
been tested, and would stop running the 173 main rules entirely. That is
not a sign-off. It is a weaker check dressed as a stronger result, and
this repository's recurring defect — `docs/47` section 9 counts it
fourteen times — is exactly a green check read as wider than the thing
it examined.

### 7.2 Making the main deck return 0 needs two upstream changes

Neither is in this repository's gift, and neither should be forked
locally:

1. **Schottky device recognition** (section 4): require an explicit
   marker, or exclude synthesized nBuLay from `Sdiod.d`/`Sdiod.e`, or
   evaluate the bbox test on the unclipped ContBar. Any one of the three
   takes 1,022 of the 2,316 to zero.
2. **SRAM marker scoping** (section 5.3): honour layer 25/0, which the
   main deck already reads and discards. That takes the remaining 272 to
   zero — *if* IHP confirms the exemption is correct, which is the open
   question of 5.5.

### 7.3 DRC was never the binding constraint

This is the reason that survives regardless of how the other two land,
and it is the one `docs/12` already had right.

**Netgen LVS returns 359 errors** (`docs/12` 7.5): 181 net differences,
158 unmatched pins, 13 unmatched devices, 7 unmatched nets. The
bus-delimiter half — extracted `A_DIN[16]` against CDL `A_DIN<16>` — is
a local setup problem and `docs/12` section 10.2 item 9 estimates a few
hours for it. **The hierarchy-name half is IHP-Open-PDK issue #239**,
cited in `docs/04` section 1.2 as an open integration issue on the
foundry SRAM macros: the CDL carries a `512x32_c2` configuration infix
that the extracted layout does not, so Netgen flattens the entire macro
and nothing matches by name. That is not fixable from this repository,
and `docs/12` section 10.2 item 9 is explicit that fixing the delimiter
half alone would not make LVS pass.

**A design that passes DRC and fails LVS is not signed off.** Even in
the most favourable world — both deck defects fixed upstream tomorrow,
DRC 0 on the main deck — the macro still would not sign off, because
LVS would still return the #239 errors. The DRC result is one of two
gates and it is not the harder one.

### 7.4 So what would a deck swap actually buy?

Stated plainly, because the instruction was to say what the whole
picture would be and not only the part that was tested:

| | Today | If the main deck's two scoping defects were fixed upstream |
|---|---|---|
| Magic DRC | 1,106,478 boxes | unchanged — separate deck, separate defect (`docs/12` 8.2 exit 1) |
| KLayout DRC | 2,316 | **0** |
| Netgen LVS | 359 | **359** — unchanged, #239 is upstream and untouched |
| Signed off? | No | **No** |

The single largest manufacturability blocker does **not** move. It moves
from "two decks and LVS all fail" to "one deck passes, one deck fails,
LVS fails". That is a better-understood failure, not a passing one.

---

## 8. What changes, and what to take upstream

### 8.1 `docs/12`'s recommendation stands; two of its statements need amending

The NO-GO of `docs/12` section 8 is **unaffected**. Nothing here makes
the macro signable off, the schedule argument of 8.3 is untouched, and
the 2026-09-21 close is now eighteen days out.

Two statements in it should be read with this document alongside. Both
are recorded here rather than edited there, per that document's own
ownership rule (`docs/12` section 1):

1. **Section 7.5's "two signoff decks ... disagree by nearly three
   orders of magnitude", and 7.7's "2-3 orders of magnitude".** The
   comparison put a flat error-box count next to a hierarchical marker
   count. Normalised, the gap is a factor of 4 to 9 (section 3.3), and
   on the contact-enclosure rule the two decks **agree** rather than
   disagree. The conclusion those sentences support — that the macro's
   DRC status is a tooling question needing upstream resolution — is
   **strengthened**, not weakened; only the size of the discrepancy
   changes.
2. **Section 8.2's "the KLayout deck also returns 2,316 errors, so it is
   not a free exit either".** True, and the conclusion is right, but the
   clause implies a second independent confirmation that the macro
   geometry is bad. Sections 4 and 5 say what the 2,316 actually are:
   1,022 shapes from a Schottky rule evaluated against a layer the file
   does not contain, and 272 markers over geometry inside an SRAM marker
   the deck reads and discards. The right reason to reject the exit is
   section 7, not the number.

`docs/47` section 9 quotes the 2,316 as "KLayout deep-mode DRC 2,316 in
three rules, attributed to 57 cells all inside the macro hierarchy".
That is accurate as written and needs no change; a reader following it
here will now find what the three rules are.

### 8.2 The two things to take upstream

`docs/12` section 8.4 item 4 asked for the Magic-versus-KLayout
divergence to be tracked for TTIHP27a. It can now be filed as two
specific, reproducible reports rather than a divergence:

1. **`Sdiod.d`/`Sdiod.e` fire on designs containing no Schottky diode.**
   Reproducer: run `ihp-sg13g2.drc` on any PDK-shipped
   `RM_IHPSG13_*` GDS. Evidence: `nbulay_drw has 0 polygons` in the
   deck's own log while the rules report 9,275 shapes flat; 2,303 of the
   reported shapes are smaller than any drawn contact in the file;
   `sg13g2_maximal.drc` does not implement the pair and requires
   explicit markers.
2. **`ihp-sg13g2.drc` reads layer 25/0 (`SRAM.drawing`) and no rule uses
   it.** `sg13g2_maximal.drc` does use it, to exempt SRAM Activ from
   `Cnt.c.Digi`. On `RM_IHPSG13_1P_512x32_c2_bm_bist` the difference is
   104,264 errors against 0. Attached question, which is the one that
   actually matters: **is the 0.02 um Activ enclosure of Cont inside the
   SRAM marker a qualified rule?** Secondary: `Cnt_c_digibnd` is the only
   one of 374 rule-value keys missing from `sg13g2_tech_mod.json` and is
   documented in neither rule table.

Both are properties of the PDK, reproducible in 30 seconds from a
one-line command on a file IHP ships, and neither requires anything from
this repository.

---

## 9. What must not change: the pilot

`docs/34` pins the pilot by hash and the shuttle closes 2026-09-21.
`docs/31` records the frozen submission passing both decks — Magic DRC 0
and KLayout DRC 0, section 4.2 of that document. **Nothing in this
document implies any change to it**, and the reason is structural rather
than a judgement call.

Measured on `trial-03-signoff`'s `aer_fifo.gds`, a standard-cell-only
design that `docs/12` section 4.1 records as KLayout DRC 0 **[fact]**:

| Quantity | `aer_fifo` (standard cells only) | `RM_IHPSG13_1P_512x32` |
|---|---|---|
| NWell polygons | 18,166 | 37,959 |
| Synthesized nBuLay | **936 polygons, 57,027.02 um2** | 49 polygons, 7,595.80 um2 |
| **Non-square contacts (`contbar`)** | **0** | **23,959** |
| ContBar inside nBuLay — drives `Sdiod.d`/`Sdiod.e` | **0** | 9,275 |
| **DigiBnd polygons (16/0)** | **0** | 21,171 |
| `Cnt.c.digibnd` errors, flat | **0** | 104,264 |

Note the second row: `aer_fifo` has **7.5x more** synthesized nBuLay
area than the macro. The discriminator is not the well. It is that
**`sg13g2_stdcell` uses only square contacts**, so `contbar` is empty and
`Sdiod.d`/`Sdiod.e` are structurally incapable of firing on any
standard-cell-only design; and that the standard cells carry **no
DigiBnd at all**, so `Cnt.c.digibnd` is inert and every contact goes
through the `Cnt.c` path at 0.07, which passes.

The pilot contains no `RM_IHPSG13` macro. Both rules examined here are
inert on it. `docs/31`'s zeros stand exactly as recorded, and this
document asks for no re-run, no re-harden and no change to
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/`.

---

## 10. What this does NOT cover

Stated at length, in the discipline of `docs/47` section 9.

- **This is not a sign-off and does not make one available.** The
  conclusion of section 7 is that KLayout sign-off is **not** viable for
  these macros. Nothing here may be read as clearing `RM_IHPSG13`.
- **It does not establish that the macro layout is correct.** Section 5
  says explicitly that the 0.02 um contact enclosure is real geometry
  and that whether it is qualified is unknown from the installed files.
  "The other deck returns 0" is not "the layout is clean" — section 6
  argues against that reading at length.
- **It does not establish that the maximal deck is a valid sign-off
  deck.** The PDK's own README says its rules "have not been verified or
  tested". It was run here as an instrument for reading the main deck's
  scope, not as an alternative sign-off.
- **Only one macro was examined.** `RM_IHPSG13_1P_512x32_c2_bm_bist`,
  the part `docs/12` section 6.5 selects. The other 26 were not run. The
  mechanisms of sections 4 and 5 are generic to the family
  **[estimate]** but the counts are not transferable.
- **Magic's 1,106,478 was not re-examined.** `docs/12` section 7.5's
  inference that Magic is failing to merge geometry across subcell
  boundaries remains an `[estimate]` and this document neither confirms
  nor refutes it. The `docs/12` 8.2 exit 1 — a Magic tech-file change —
  is untouched.
- **No LVS work was done.** Section 7.3 quotes `docs/12`'s 359 and
  reasons about it; it re-measures nothing. `docs/12` section 10.2 item
  5 (the KLayout LVS deck has never been exercised) is still open, and
  given how far the two DRC decks diverged on scope, the LVS decks may
  diverge too.
- **No layout was modified, no design was re-hardened, and no run
  directory was created inside the repository.** Every measurement is
  read-only against the retained `macro-03` and `trial-03-signoff` trees
  and the installed PDK. Those trees are gitignored and may be deleted;
  section 11 is how to regenerate every number without them.
- **The deep-versus-flat ratio of 53.0 is a property of this macro**, not
  a general KLayout constant. It comes from a 16 kbit replicated array.
- **`docs/12` section 10.2 item 4 is not closed.** `sram_pilot` was
  floorplanned on the interpolated 4x2 block. Nothing here re-runs it,
  and section 2.3 removes the need to: the errors are in the vendor cell,
  so the die size cannot affect them.

---

## 11. Reproduction

Every number above regenerates from the installed PDK alone, except
those attributed to a run tree. No repository file is needed.

```
export PDK=$HOME/.ciel/ihp-sg13g2
MACRO=$PDK/libs.ref/sg13g2_sram/gds/RM_IHPSG13_1P_512x32_c2_bm_bist.gds

# section 2.3 — the 2,316, from the vendor macro alone (~30 s)
klayout -b -zz -r $PDK/libs.tech/klayout/tech/drc/ihp-sg13g2.drc \
  -rd input=$MACRO -rd topcell=RM_IHPSG13_1P_512x32_c2_bm_bist \
  -rd report=deep.lyrdb -rd no_recommended=True -rd run_mode=deep -rd thr=20

# section 3.2 — the same, flat: 122,814 (~34 s)
#   as above with -rd run_mode=flat -rd report=flat.lyrdb

# section 6 — the other deck in the same PDK: 0 in 371 rules (~93 s)
klayout -b -zz -r $PDK/libs.tech/klayout/tech/drc/rule_decks/sg13g2_maximal.drc \
  -rd input=$MACRO -rd topcell=RM_IHPSG13_1P_512x32_c2_bm_bist \
  -rd report=max.lyrdb -rd log=max.log -rd run_mode=deep -rd thr=20

# section 4.2 — the deck says it itself
grep "nbulay_drw has" max.log        # or the main deck's stdout
```

Counts by rule come out of the `.lyrdb` XML by tallying
`item/category`; the `Sdiod.d`-equals-`Sdiod.e` result of section 3.1 is
a set comparison of `(item/cell, item/values)` pairs between the two
categories. The substitution experiments of 4.2 and 5.3 are the deck's
own derivations with exactly one term changed —
`nbuLay_gen_nbulay` -> `nbulay_drw`, and `activ_drw` ->
`activ_drw.not(sram_drw)` — run as a standalone `.drc`.

The `macro-03` figures of section 2.1 come from
`hw/openlane/sram_pilot/runs/macro-03/65-klayout-drc/reports/`, which is
gitignored. If that tree is gone, section 2.3 regenerates the same 2,316
from the PDK, which is the point of having made that run.

---

## 12. Open items

1. **The upstream question of 5.5 is unanswered**: is a 0.02 um Activ
   enclosure of Cont inside the SRAM marker a qualified rule? Everything
   in section 5 hangs on it and nothing in the installed files decides
   it. This is the item to file.
2. **The two reports of 8.2 have not been filed.** They are written up
   here; nobody has sent them.
3. **The other 26 macros were not run.** One command each, ~30 s, and it
   would show whether the counts scale with array size as the mechanism
   predicts **[estimate]**.
4. **The KLayout LVS deck is still unexercised** — `docs/12` section
   10.2 item 5, restated here because sections 5 and 6 make it more
   interesting than it was: if the two DRC decks disagree about SRAM
   scope, the LVS decks may too, and the LVS failure is the one that
   actually blocks.
5. **Whether `sg13g2_maximal.drc` returning 0 means anything** depends on
   a judgement about that deck's status that this document declines to
   make and section 6 explains. If IHP confirms the residual set's SRAM
   scoping is the intended behaviour and the main set's omission is the
   bug, section 7.1's objection weakens considerably. That is a question
   for upstream, not a measurement.
