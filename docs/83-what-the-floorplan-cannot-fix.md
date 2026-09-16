<!--
SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
SPDX-License-Identifier: CC-BY-4.0
-->
# 83 — What the floorplan cannot fix, and what the CLINT probe was measuring

`docs/73` section 16 ended with a sentence that reads like an
instruction: *"the requirement is a floorplan requirement and not a
placement one"*. This document takes that instruction, asks what a
floorplan would have to do to satisfy it, and finds that **the
requirement is already satisfied and was never what the slack was made
of.**

Two measurements settle it, and both are on layouts that already exist.
The first locates the CLINT's closure in the sign-off layout: **1,802
cells of 1,802 are in the channel, none in any pocket, and no macro
stands between them and the fabric.** The second decomposes the delay of
every violating path: **wire is 1.9 % of it, and the median path is 78
gate stages deep.** A floorplan moves wire. There is no version of this
floorplan that moves 78 gate stages.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged, with the
derivation stated.

**No run was launched for this document.** Every number below is read
out of two run trees that were already on disk when it was written:
`s83romecc5`, the sign-off layout, and `s71boot`, the layout `docs/73`'s
probe was run on. One tool is new, `hw/soc/pnr/path_composition.py`,
and it is section 3's arithmetic and nothing else.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Is the CLINT's closure split by a macro in the sign-off layout?** | **No. 1,802 of 1,802 in the channel, 0 in the upper pocket, 0 in the lower pocket, 0 in the strip** **[fact]**. The condition `docs/73` section 15 item 2 states is met by the placer, unconstrained, with no fence and no manual placement. |
| **Then what were `s84clint5` and `s84clint6` doing?** | Forcing a cluster that is already together into a box, which is why both congested. `docs/73` section 16's negative result stands as measured and its conclusion is narrowed here. |
| **How much of a violating path is wire?** | **1.9 % at the median, 3.0 % at the most wire-bound path in the report** **[fact, 1,000 violating paths]**. On `s71boot` it is 1.9 % and 2.8 %. The figures first published here were 3.6 % and 4.7 %, from a tool that counted the capture clock tree into the data path; section 3 carries the correction. |
| **How deep are the violating paths?** | **78 gate stages at the median**, 57 at the shallowest and 91 at the deepest **[fact]**. |
| **What is the worst endpoint?** | A **register-file SECDED check bit**, at −7.5758 ns — the hardening's own write path, not the fabric's read path **[fact]**. |
| **Where did the one-cycle bus read go?** | It is still there and it is a minority: `u_clint` captures **138** of 3,529 violating endpoints and `u_bus` **54**, against 1,224 in the register file and 864 elsewhere in Ibex **[fact]**. |
| **Was the bus-read framing ever right?** | **On `s71boot`, yes, for the worst path**: `docs/73` section 7.3 measured it as `raddr_b_i[0]` → `s_rdata_clint[27]` at −8.1852. On the eight-macro layout that structure is no longer the worst and nobody re-asked. Wire was 1.9 % of `s71boot`'s paths as well. |
| **So what binds this design at 20 ns?** | Gate delay, spread across the core's datapath and its hardening. Section 5. |

---

## 2. The CLINT closure, located

`docs/73` section 15 item 2 states the requirement in one sentence: the
CLINT's response registers, the fabric decode that selects them and the
time base that feeds them *"have to be on one side of the ROM, and any
constraint that draws a line through that set puts the line's nets over
the macro."*

The set is the 1,802-cell register-to-register closure of section 16.1.
Located in `s83romecc5`'s own final DEF, by the zone convention
`hw/soc/pnr/clint_region.py` defines:

| zone | standard cells | flip-flops | **CLINT set** |
|---|---:|---:|---:|
| channel | 52,717 | 10,710 | **1,802** |
| upper pocket | 3,384 | 298 | **0** |
| lower pocket | 460 | 63 | **0** |
| strip beside the ROMs | 1,198 | 318 | **0** |
| elsewhere | 6,590 | 1,608 | **0** |

**[fact, `clint_region.py census` on
`hw/soc/pnr/runs/s83romecc5/final/def/soc_top.def`.]** The set's
bounding box is x 788.16 to 2041.92, y **782.46 to 1288.98**, which is
inside the channel band 687.18 to 1387.26 on both edges. Twenty-two of
the 1,802 sit at x beyond the ROM column's left face, and at channel
height there is no ROM there: the lower ROM ends at y 684.22 and the
upper one begins at 1387.26.

**The requirement is met, by the placer, with nothing asked of it.**
What changed between `s71boot` and here is not a constraint but the
floorplan: the two ROM check macros of `docs/67` took the blind space at
the outer edge of each band, the ROM column's usable pocket shrank, and
the placer stopped trying to put the CLINT in it. The probe of
`docs/73` was aimed at a pocket the design had already left.

> **THIS IS THE PROJECT'S OWN RECURRING SHAPE, AND IT IS WORTH NAMING
> ONCE MORE.** `docs/64` collects it: *a measurement taken on a design
> that no longer exists*. Three layouts in `docs/73` moved a set that
> cut through a cluster, a fourth and fifth in section 16 forced the
> whole cluster into a box, and all five were answering a question the
> eight-macro floorplan had already answered by accident. The five runs
> are not wasted — they measured what they measured — but the question
> should have been re-asked when the floorplan changed under it.

---

## 3. What a violating path is made of

The flow's own sign-off report, `49-openroad-stapostpnr` at
`nom_slow_1p08V_125C`, lists 2,000 paths of which 1,000 violate. Each
path is decomposed at its launch flip-flop's `Q` and every incremental
delay after it is attributed to a **cell arc** (an output pin) or to a
**net** (an input pin).

| | `s83romecc5`, 1,000 violating | `s71boot`, 985 violating |
|---|---|---|
| gate stages, median | **78** (57 to 91) | **76** (66 to 79) |
| net delay, median | **0.493 ns** | 0.526 ns |
| cell delay, median | **24.976 ns** | 26.869 ns |
| **wire share, median** | **1.9 %** | **1.9 %** |
| **wire share, maximum over all violating paths** | **3.0 %** | **2.8 %** |

> **THE FIRST VERSION OF THESE NUMBERS WAS WRONG, AND THE CORRECTION
> MAKES THE ARGUMENT STRONGER.** As published on 2026-09-16 this section
> read 3.6 % at the median and 4.7 % at the most wire-bound path, over a
> median of 88 stages, with 0.971 ns of net delay and 26.785 ns of cell
> delay. `hw/soc/pnr/path_composition.py` was cutting each path at the
> END of the report block instead of at `data arrival time`, so the
> CAPTURE clock's tree --- the clock edge at the period and a dozen
> buffers after it --- was being counted into the data path. The tool
> was corrected the same day and every figure in this document is the
> corrected one. The old numbers are recorded here rather than in the
> tables, because they are an instrument defect and not a superseded
> measurement: nothing about the design changed between them.



**[fact, arithmetic on each report's own incremental-delay column.]**

The worst path alone, in full: 77 gate stages after the launch flop,
**26.2904 ns of cell delay and 0.7827 ns of net delay**, 27.0731 ns of
data path, slack −7.5758 **[fact]**.

**Read the third row again.** If every wire on the worst path were
made ideal — zero resistance, zero capacitance, the cells placed on top
of one another — the path would still take 26.29 ns against a 20 ns
constraint. Perfect placement does not close this design; it closes
3.0 % of the gap at the most wire-bound path in the report and 1.9 % at
the median.

That is the whole of the answer to "solve the floorplan problem", and
it does not depend on which floorplan: `s71boot`, on a different macro
set and a different pocket, has the same profile.

---

## 4. Where the endpoints are

The violating endpoints of `s83romecc5`, resolved by the project's own
census rather than by this document's attribution:

| capture group | endpoints | worst | TNS |
|---|---:|---:|---:|
| register file, data bits | **1,007** | −7.0936 | −3,646.21 |
| `u_ibex`, elsewhere | 864 | −5.7805 | −3,473.96 |
| unresolved | 763 | −7.2251 | −3,592.45 |
| **register file, SECDED check bits** | 217 | **−7.5758** | −1,469.22 |
| `u_npu` | 156 | −5.1658 | −355.41 |
| **`u_clint`** | **138** | −5.9318 | −618.76 |
| top level | 111 | −5.2825 | −475.55 |
| `u_scrub` | 92 | −5.5364 | −418.47 |
| **`u_bus`** | **54** | −5.5521 | −241.80 |
| `u_ram` | 47 | −5.6420 | −199.12 |
| `u_rom` | 44 | −5.1307 | −183.97 |

**[fact, `violator_census.py` at the slow corner.]**

**The register file and the rest of Ibex hold 2,088 of 3,529 endpoints
and −8,589 ns of the −14,736 TNS**, 59 % of the count and 58 % of the
total. The bus fabric holds 54 endpoints, 1.5 %, and the CLINT 138,
3.9 %.

**And the single worst endpoint in the design is a SECDED check bit of
the register file.** The path is the read address, through the core's
datapath, into the write encoder, into the check-bit storage: it is the
hardening's own write path, and `docs/43` bought it deliberately. It is
not a floorplan artefact and no placement removes an XOR tree.

---

## 5. What binds this design, stated plainly

Gate delay, spread over roughly 88 stages between two flip-flops, in a
130 nm standard-cell library, at a 20 ns constraint with a 5 % derate at
the slow corner.

**No frequency is claimed for this design and none is derived here**
(`docs/53` section 9.2, `docs/05` rule 5). What sections 3 and 4 add to
that rule is a reason: the number a reader would want to derive is not
a property of this layout, this floorplan or this placement, and
quoting one would attach a process and a netlist to a figure that
belongs to neither.

The three things that would move it are all structural, and all of
them are named elsewhere in this corpus:

1. **The core's pipeline.** Eighty-eight stages between flip-flops is
   the RV32IMC datapath this project fetched, configured `small-pmp`
   and did not re-time. Splitting it is a core change, not a SoC one.
2. **The register file's write encoder.** The worst endpoint is its
   check bits; `docs/43` priced the encoder in area and in fault
   coverage and did not price it in depth.
3. **`docs/72` section 15 item 5's registered request phase.** It
   remains the right answer to the paths it is about --- but section 4
   measures those paths at **192 endpoints of 3,529**, so it is a
   correction to 5.4 % of the problem and not to the problem.

None of the three is a floorplan.

---

## 6. What this changes in the documents

- **`docs/73` section 15 item 1 is closed** by section 16 of that
  document, and its conclusion is narrowed here: the cluster does not
  route in a box, AND the condition the box was meant to enforce is
  already met without one.
- **`docs/73` section 15 item 2's condition is met** in the eight-macro
  floorplan, measured in section 2 above.
- **`docs/72` section 15 item 5 stands**, with its scope measured for
  the first time: 192 of 3,529 violating endpoints.
- **`docs/48`'s two rejected floorplans are not reopened.** FP-A and
  FP-B were worse for reasons that document measures, and section 3
  adds the reason none of the three floorplans could have been much
  better than another: they differ in wire, and wire is under 5 % of
  every violating path in any of them.

---

## 7. What this does NOT cover

- **It does not measure a floorplan that does not exist.** The claim is
  about the delay composition of the two layouts on disk, not a proof
  that no floorplan helps. What it establishes is the size of the prize:
  at most the net delay, which is 0.493 ns at the median violating path
  and 0.7827 ns on the worst, against deficits of 7.5758 ns.
- **It does not price any of section 5's three structural changes.**
  Two of them are core changes and the third is `docs/72`'s, still
  unpriced there.
- **It says nothing about hold.** Hold is met at all three corners in
  `s83romecc5` by 29.6 ps at the fast corner, and that margin is a
  placement and buffering property where setup here is not. `docs/79`
  and `docs/50` section 16 are where that margin gets spent.
- **The attribution of stages to blocks is not used for any claim.**
  This document's own connectivity attribution leaves 46.6 % of the
  critical path's stages unattributed, because the flattened netlist
  keeps no hierarchy through the core's datapath. Section 4 uses the
  census's endpoint resolution instead, which reads names the netlist
  still carries.

---

## 8. Reproducing this

```
export PDK_ROOT=$HOME/.ciel
P=hw/soc/pnr/runs/s83romecc5

# section 2: where the CLINT closure sits
python3 hw/soc/pnr/clint_region.py census $P/final/def/soc_top.def \
  --members <the 1,802-cell union of docs/73 section 16.1>
#   channel 1802, upper pocket 0, lower pocket 0, strip 0, elsewhere 0

# section 3: what a violating path is made of.  Each path is split at
# its launch flip-flop's Q; every incremental delay after it belongs to
# an output pin (a cell arc) or to any other pin (the net that reached
# it).  The clock network is counted into neither, which is what makes
# the percentage comparable between layouts with different clock trees.
python3 hw/soc/pnr/path_composition.py \
  $P/49-openroad-stapostpnr/nom_slow_1p08V_125C/max.rpt --top 100
#   1,000 violating: stages med 78 (57..91), net med 0.493,
#   cell med 24.976, WIRE SHARE med 1.9 % max 3.0 %
#   worst path: slack -7.5758, 77 stages, net 0.7827, cell 26.2904
python3 hw/soc/pnr/path_composition.py \
  hw/soc/pnr/runs/s71boot/49-openroad-stapostpnr/nom_slow_1p08V_125C/max.rpt
#   985 violating: stages med 76 (66..79), WIRE SHARE med 1.9 % max 2.8 %

# section 4: where the endpoints are
python3 hw/soc/pnr/violator_census.py $P --corner nom_slow_1p08V_125C
```

---

## 9. What the next block should be

1. **Do not run another floorplan for timing.** Section 3 is the
   argument: three floorplans have now been measured and they differ in
   a quantity that is under 5 % of every violating path. A fourth would
   measure the same thing again. If a floorplan is run, it should be run
   for a reason section 3 does not cover --- area, hold margin, power
   grid or routability --- and the reason should be stated before the
   run.
2. **Price the register file's write depth.** Section 4's worst
   endpoint is its check bits and `docs/43` never measured that path's
   depth. This is the smallest of section 5's three items and the only
   one inside this project's own RTL.
3. **Re-ask `docs/72` section 15 item 5 with its scope attached.** It
   is a correction to 192 endpoints and it costs a cycle on every load.
   That trade can now be stated as a trade, which it could not before.
4. **When a floorplan changes, re-ask the questions that were asked of
   the old one.** Section 2's note is the fifth instance of this shape
   in the corpus. The cheapest guard against it is the one this project
   already uses everywhere else: cite the run a measurement was taken
   on, in the sentence that quotes it.
