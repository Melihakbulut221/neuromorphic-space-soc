# 79 — Where the replicas actually are, and whether the netlist computes what the RTL says

Two measurements that had never been made, both made because a hostile
reading of this corpus said they were the two that could sink it. One
came back badly. The other came back well and cost a false negative to
get there.

The subject of both is the claim this repository makes most often:
**the configuration state is protected by triple modular redundancy.**

---

## 0. Read this first

`docs/33` records the synthesiser merging three declared replicas into
one physical bank, and `sw/tests/test_synthesis_guards.py` is the
instrument built to catch it: count mapped flip-flops by instance path,
assert 55 under each of `u_cfg_a`, `u_cfg_b`, `u_cfg_c`. It passes. It
has been mutation-checked. It runs in two independent technology
mappers and with every attribute deleted from the source text.

**It is a statement about the netlist and it has been read as a
statement about the die.** Section 1 measures the die. The answer is
that the three banks are not separated: their cells touch.

**And a guard that counts flip-flops cannot check the voter**, which has
no flip-flops. A synthesis fault that preserved 3 x 55 registers and
miscomputed the majority function would pass every check in this
repository. Section 2 closes that, for three modules, with negative
controls.

Neither section says this design fails. Section 3 is emphatic about the
difference between what was measured and what a reader will want it to
mean.

---

## 1. The replicas are not placement-separated

### 1.1 The instrument

`hw/openlane/replica_placement.py`, new. It reads the run's own final
DEF and hierarchical netlist, attributes every `sg13g2_dfrbpq_1` to a
replica by instance path, attributes each to the storage bit it holds
where the `bits[]` net survives, and computes distances between cell
bounding boxes.

**Its first check is that it is counting the same flip-flops the
synthesis census counts.** If the DEF and the netlist have come apart,
nothing below means anything. It reads 55 / 55 / 55, which is
`test_synthesis_guards.py`'s own assertion on the same run.

Geometry, from the run's DEF and the PDK LEF: `UNITS DISTANCE MICRONS
1000`; die 1289.28 x 313.74 um; site 0.48 um; row 3.78 um;
`sg13g2_dfrbpq_1` is 12.96 x 3.78 um, which is 27 sites wide and exactly
one row high.

### 1.2 What it measures on the frozen sign-off layout

`hw/openlane/pilot_ihp/runs/signoff-6x2`, 33,564 components **[fact,
2026-09-09]**:

| | |
|---|---|
| Flip-flops per replica | 55 / 55 / 55 |
| Cross-replica pairs | 9,075 |
| Centre-to-centre, minimum | **3.78 um** — one row |
| Centre-to-centre, median | 113.47 um |
| **Edge-to-edge, minimum** | **0.00 um — the cells touch** |
| Pairs abutting | **49** |
| Pairs within one 0.48 um site | 51 |
| Corresponding-bit pairs, minimum | 3.78 um |
| Corresponding-bit pairs abutting | **18** (a lower bound, see 1.4) |
| Nearest fellow configuration flop is in **another** replica | **103 of 165** |

The closest pairs are the same bit of the same word.
`u_cfg_a[35]` and `u_cfg_b[35]` sit in adjacent rows at the identical x
span, sharing all 27 sites of width; `u_cfg_a[32]`/`u_cfg_b[32]` are the
same case. **Three replicas placed as three banks would put a flop's
nearest neighbour in its own bank. Here it is in another one, for 103
of the 165.**

### 1.3 The mechanism, which matters more than the numbers

**The placer is minimising wirelength to a shared voter, and that pulls
the three copies of each bit together.** It is not a bug and it is not
an unlucky seed: it is what the objective function asks for. Nothing in
this flow requested separation, and nothing in the flow supplies it by
default.

One consequence is worth stating because it was not designed:
**replica C is the best-separated bank**, and the reason is `MIX = 1`.
`docs/33` gave C a different storage transform for a purely logical
reason — to stop structural hashing merging it with A and B. A defence
chosen against the synthesiser bought physical margin by accident. It
bought it for one of the three pairings, and a vote needs only two
replicas corrupted.

### 1.4 What the tool undercounts, and says so

15 of replica C's flip-flops cannot be attributed to a bit index,
because C stores a transform of the value and its `bits[]` nets may be
optimised away. So the corresponding-bit figures — 120 pairs, 18
abutting — are a **lower bound**. Recovering the remaining 15 needs the
decode network walked, which the committed tool does not do; a deeper
one-off analysis that did resolve them by the `cfg_dec` gate signature
found 165 pairs and 28 abutting, and on 30 of the 55 value bits two of
the three voter inputs in contact. **The committed tool reports the
conservative number and prints the word UNDERCOUNT**, because a lower
bound quoted as a measurement is the failure this project keeps finding
in itself.

### 1.5 The guard, and why it pins rather than demands

`sw/tests/test_replica_placement.py` asserts the measured values. It
does not assert a minimum separation.

A test demanding separation would fail on a design that is frozen and
cannot change before the shuttle, and a test asserting nothing would
leave this measurement to be re-run by nobody. So it pins: **if a future
layout separates the banks, these tests fail and this document has to be
rewritten**, which is the correct outcome because the claim would have
changed.

It also asserts that the tool keeps declaring its own undercount.

### 1.6 It reproduces beyond the pilot

The same picture appears on `soc_top` across three independent TMR
structures — the watchdog's 29-bit bank, boot's 23, the NPU's 25 — on
two independent hardens, `s71boot` and `s75w9`, by a completely
different attribution method, because LibreLane destroys instance names
there and the cells have to be reached through fan-in cones. Per-bit
critical separations of 4.48 / 7.58 / 3.90 um minimum and 11.34 / 11.50
/ 9.22 um median, with different-replica cells holding the same output
bit abutting in the same row.

**Two designs, four layouts, three attribution methods, one answer.**

---

## 2. The netlist computes what the RTL says, for three modules

### 2.1 The link that was missing

The argument this repository had been making:

> the RTL is proved by SymbiYosys → the netlist is censused by
> `sw/tests` → therefore the netlist implements the proved RTL.

The middle step does not follow. A census counts cells and walks cones;
it never establishes that the netlist computes the RTL's **function**.
Until 2026-09-09 there were **zero** equivalence checks in this
repository, and `eqy` was in the pinned toolchain the whole time.

`formal/eqy/` is now the missing link. Three modules, chosen for a
reason rather than for convenience:

- **`tmr_voter`** — the one module a flip-flop census structurally
  cannot check, because it has no flip-flops. This is the module the
  hostile reading named.
- **`secded_enc`, `secded_dec`** — what every protected register in the
  design depends on being right.

**The gate side is extracted from the sign-off run**, not synthesised
fresh. A fresh synthesis would show the recipe is equivalence-preserving
today; extracting from the run shows it of the artefact `docs/34`
freezes.

### 2.2 Result

```
== eqy tmr_voter        2 partition(s) proved
== eqy secded_enc       1 partition(s) proved
== eqy secded_dec       1 partition(s) proved
== eqy voter_mutant       (negative control)  control fails as required
== eqy secded_dec_mutant  (negative control)  control fails as required
```

`tmr_voter` is checked at `WIDTH = 55`, all 55 outputs and `mismatch`.
The parameterised module is not in the netlist under its own name —
yosys writes it as `$paramod\tmr_voter\WIDTH=s32'...110111` — so the
Makefile derives the name from the netlist and renames it back rather
than hard-coding a string that the next width change would break.

**Both negative controls are part of the default target**, because a
checker that has never returned red is not a checker. `formal/eqy/mutate.py`
drops one term of the majority function, `(in_b & in_c)`, and flips one
bit of `H_ROW3`. Each mutation **asserts that it applied**: a mutation
that silently fails to match is a control reporting success while
testing nothing. The Makefile treats a control that PASSES as an error.

The voter mutation is invisible to every other instrument here — same
ports, same zero flip-flops, same mapped cell count. That is the point.

### 2.3 A finding about the checker, not the design

**`eqy` partitions at module outputs and feeds each partition's cut
points as independent free inputs.** For `secded_dec` that manufactures
an unreachable state — a syndrome no code word produces — and it
reported a counterexample **on a correct netlist**.

`bind *` binds the cut points to the gold design's own nets, which
removes the freedom without weakening the proof. It cost one false FAIL
to learn.

The general statement is worth carrying beyond this document:
**partitioned equivalence checking is sound for proofs and incomplete
for refutations.** A gate written as `eqy ... && echo ok` would have
reported FAIL on a correct netlist on the first day it ran. That is the
same shape as everything else in this corpus — a check that looks
conclusive and is not — arriving from the direction of the checker
rather than the design.

---

## 3. What this does NOT cover

- **A DISTANCE IS NOT A SAFETY ARGUMENT, IN EITHER DIRECTION.** No
  single-event or multiple-bit-upset cross-section, charge-collection
  radius or LET threshold for IHP SG13G2 was measured, and none is
  available here. Section 1 establishes that this layout **permits** a
  common-mode upset of two replicas over much of the protected word. It
  does **not** say one occurs at any fluence, and it does **not** say
  that some other separation would prevent one. The sentence *"because
  the replicas are a few micrometres apart, one ion track defeats the
  vote"* is **forbidden**: it silently supplies the conversion from
  micrometres to a coincidence probability, which this work does not
  have.
- **CELL BOUNDING BOXES, NOT SENSITIVE NODES.** The distances are
  between cell outlines. The storage node inside a `sg13g2_dfrbpq_1` is
  somewhere in a 12.96 x 3.78 um rectangle and this document does not
  say where.
- **EVERY UNQUALIFIED SENTENCE SAYING THE CONFIGURATION IS "PROTECTED BY
  TMR" IS NOW WRONG AS STATED** and must read "triplicated **in the
  netlist**". That is a correctness change to the corpus's own prose,
  not a style preference, and it applies to any paper drawn from it.
- **NO PLACEMENT CONSTRAINT WAS APPLIED.** Three mechanisms exist and
  two have been exercised here before: `MANUAL_GLOBAL_PLACEMENTS`, which
  the pilot flow already runs as step 33 and which no-ops when unset;
  `dbRegion` + `dbGroup`, which `hw/soc/pnr/clint_region.py` already
  implements; and `PL_SOFT_OBSTRUCTIONS`, which cannot fence a group and
  is useless alone. **The price is known from `docs/73`**, the one time
  placement was constrained here: the region form did not route, and the
  manual-placement form cost about 7 ns of WNS and moved the problem
  rather than solving it, because a constraint that captures one half of
  a co-placed cluster moves the crossing to the cut. For TMR that means
  each replica must move **with its own fan-in and fan-out cone**, not
  just its 55 flip-flops. Not attempted here.
- **THE EQUIVALENCE RESULT IS THREE MODULES, NOT THE DESIGN.** Whole-
  design equivalence against the post-P&R netlist was attempted
  separately and reached about half the partitions; nothing in
  `formal/eqy/` claims it, and this document does not print a figure for
  it. What is proved is what the Makefile's default target proves.
- **THE GATE SIDE IS NOT IN GIT.** `runs/` is gitignored build output.
  A reader who clones cannot obtain the DEF or the netlist, so section 1
  and section 2 both **skip** rather than fail without them —
  `test_replica_placement.py` says so in its skip reason. Publishing the
  digests would be the cheap fix and has not been done.
- **THE DEF IS ASSUMED TO BE THE PLACEMENT THAT REACHED GDS.** Both
  artefacts are written from the same final ODB, which is a construction
  argument rather than a check. Netgen LVS on this run reports *circuits
  match uniquely* with every counter zero, but **LVS certifies
  connectivity, not geometry**: it would not notice if a cell moved.
  Extracting cell origins from the GDS and diffing against the DEF would
  close it.
- **ONE LAYOUT PER DESIGN, ONE FLOW, ONE SEED.**

---

## 4. Reproducing this

```bash
python3 hw/openlane/replica_placement.py \
    hw/openlane/pilot_ihp/runs/signoff-6x2
.venv/bin/python -m pytest sw/tests/test_replica_placement.py -q
make -C formal/eqy
```

The last one runs the three checks and both negative controls, and fails
if a control passes.
