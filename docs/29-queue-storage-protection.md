# 29 — Protecting the AER queue storage, and what it cost in nanoseconds

Status: complete. One even-parity bit per queue entry in
`hw/rtl/aer_fifo.v`, checked on every accepted read, with the failed
entry discarded rather than delivered. Pinned to `c52518e` plus this
change. **No document other than this one is edited**; section 9 lists,
location by location, what must change in the others.

Convention, inherited from `docs/18`, `docs/22` and `docs/27`:
**[fact]** = measured in this environment or read out of an installed
file; **[estimate]** = derived or judged.

Run trees under `hw/openlane/*/runs/` and `tt/runs/` are gitignored, and
the run this document reports was deliberately placed **outside the
repository** (section 4.1), so every number below is quoted with the run
tag and the step directory it came from.

### Headline

- **Parity, and SECDED deferred rather than rejected.** The queue's own
  read path has about 11.6 ns of headroom, so a decoder would fit; what
  decides it is that SECDED's codec measures **117 cells and
  1,554.94 um2 per queue instance against parity's 31 and 449.97**, plus
  40 more flip-flops, in a design whose worst-corner slack has twice
  been measured to move non-proportionally with area. Section 1.
- **The flip-flop cost is exactly the estimate: +8.** 1,277 → **1,285**
  mapped, in the ASIC census, in the ECP5 census and in the hardening
  flow's own synthesis, three routes agreeing **[fact]**. Section 3.
- **The timing cost is 0.3686 ns of the design's worst-corner setup
  margin, and the design closes with room: +0.7992 -> +0.4306 ns
  derated, zero violations at every corner.** It is not spent in the
  queue — both queues' own worst paths got *faster*, and the loss lands
  on `lif_core`'s critical path, which this change adds no logic to.
  Section 4, measured against a control that reproduces `docs/27` to
  seventeen digits.
- **`evq_mem` goes from 7 silent corruptions to 0.** 374 injections,
  366 common records diffed by key, exactly 7 changed and every one of
  them SDC → DETECTED. Section 5.
- **The check field is counted in the shipped netlist, not in the RTL,
  and the count is mutation-checked.** Section 6.
- **What is left unprotected is stated rather than implied**: even-weight
  corruption of an entry, and `rd_data` itself. Section 8.

---

## 1. The choice

### 1.1 What the campaign says has to be fixed

`docs/16` section 5.11 leaves the residual at **18 silent-corruption
records across five structures** — `evq_mem` 7, `dispatch` 5,
`lif_scan` 3, `evq_hold` 2, `regbank_cfg` 1. The queue storage leads it
outright, and it is the only member with no protection of any kind: the
pointers are triple-redundant and voted (section 5.2), the valid-flag
class is closed by the dual-rail construction (sections 5.10 and 5.11),
and what is left in the AER path is the 128 flip-flops the events
themselves sit in.

The measurement is 32 single-bit deposits into
`{u_evq_in,u_evq_out}.mem[]`, 7 ending in silent data corruption,
**spread over four of the eight pilot slots at bit 0 and bit 14 alike
with no concentration to exploit** (`docs/16` section 6.2). There is no
cheap partial answer here of the kind the valid flags had — no two
flip-flops carrying two thirds of the group — so the fix has to cover
the whole array or none of it.

Why it matters more than the count suggests: `docs/10` section 7.1
freezes the AER word at TYPE plus a 10-bit ID, with no sequence number
and no length. A corrupted event word is a spike that a consumer has no
way to distinguish from a real one.

### 1.2 The two candidates, costed against both budgets

| | one parity bit per entry | SECDED (22,16) per entry |
|---|---|---|
| check bits per 16-bit entry | 1 | 6 |
| flip-flops at the pilot geometry (8 entries) | **+8** | +48 |
| records removed from the residual | 7 | 7 |
| records per flip-flop | **0.88** | 0.15 |
| single-bit entry upset | detected, entry discarded | **corrected**, event delivered |
| double-bit entry upset | undetected, delivered | **detected**, discarded |
| upset in the check field itself | detected as a false discard | corrected |
| codec cells per queue instance, sg13g2 | **31** | 117 |
| codec area per queue instance (um2) | **449.97** | 1,554.94 |

[fact for the flip-flop counts and the record count; the per-flip-flop
ratios are `docs/16` section 6.2 item 4's arithmetic; the codec rows are
measured — section 1.4.]

### 1.3 The timing argument, corrected

The first draft of this section rejected SECDED because its correction
path — a syndrome decoder and a bit-flip multiplexer between the storage
and `rd_data` — would sit in the queue's read path on a design closing
at 1.61 % of its cycle. **That argument was wrong and is withdrawn.**
`docs/27`'s +0.3229 ns is the design's worst path and it is
`lif_core`'s. The AER queues' own paths carry an order of magnitude
more: measured here on the recovered configuration at the derated slow
corner, **+9.2279 ns into EVQ_IN and +11.1861 ns into EVQ_OUT**
(section 4.3), against roughly 4.85 ns for a SECDED decode. **A decoder
in the queue read path is affordable, and timing at the queue does not
decide this.**

Two corrections to how any slack number here should be read, both from
the same investigation and both applied to section 4:

- **The flow has been applying no OCV derate.** `TIME_DERATING_CONSTRAINT`
  was an integer and Tcl integer division silently turned the 5 % into
  zero while the log still said "5 %". Every timing figure previously
  published in this repository, on both PDKs, is optimistic by that
  amount. The `trbest_*` runs of sections 4.2 and 4.3 pin it to `5.0`
  and are **derated**; the three runs of sections 4.4 and 4.5 predate
  the fix and are **underated**, and are labelled as such.
- **`Checker.SetupViolations` only ever examined the typical corner.**
  The slow corner was gated by no checker at all. This document's own
  first harden is a demonstration: it finished with `flow__errors__count`
  clean while carrying **14 slow-corner setup violations**, which were
  found by reading the corner's own report rather than by any gate.
  Every slack quoted below names its corner.

### 1.4 So why parity, on the merits

Correcting beats detecting for an event stream, and the queue can afford
the decoder. The decision is still parity, and the reason is neither of
the two the first draft gave. It is this, measured:

**The design's worst path is not in the queue, and it responds to added
AREA on a path the change does not touch.** Section 4 measures this
change's +27 cells and +2,053 um2 costing **0.3686 ns** of derated
slow-corner margin — spent entirely inside `lif_core`, while both
queues' own worst paths *improved*. Section 4.5 measures the other end
of the same effect: halving the addition gives back only 12 % of the
loss. So the price of protecting the queue is set by how much AREA the
protection adds, not by how much delay it adds to the queue.

That makes the codec measurement the deciding number **[fact, standalone
synthesis to sg13g2 with the pinned yosys, section 1.2 table]**:
SECDED's encoder and decoder are **117 cells and 1,554.94 um2 per queue
instance against parity's 31 and 449.97** — 3.5x the codec area — and it
carries **40 more flip-flops**, roughly another 1,960 um2 at this
library's 48.99 um2 per `sg13g2_dfrbpq_1`. Choosing SECDED would put
about **+4,170 um2 more** into the design than this change does, against
a measured +0.4306 ns of remaining derated margin.

**So the merits split cleanly, and this is the trade being made:** the
protection this change ships costs the least area of any code that
detects anything, closes the whole `evq_mem` group, leaves the
even-weight case open, and closes timing with 1.10 MHz of Fmax to spare.
SECDED closes the even-weight case too and delivers the event instead of
dropping it, at roughly three times the area of a change that has just
been measured to consume 46 % of the available margin.

**The honest form of that last sentence is that it is unmeasured.** The
+4,170 um2 is a codec measurement scaled by arithmetic, not a hardened
result, and section 4 is a warning against predicting this design's
slack from an area delta. What would settle it is one more pair of runs,
which is section 9 item 7.

**This is a deferral, not a rejection.** The recommendation, recorded in
section 9 item 7: **measure SECDED (22,16) on the queue and take it if
it closes** — the queue-path slack in section 4.3 says it fits, and the reason to
prefer correction to a counted drop in a spike train is not in dispute.
`docs/16` section 6.2 item 4's judgement that the full code belongs with
the SRAM macro remains right for the NPU-scale 64-entry queue; it is not
an argument against the code at the pilot's 4-entry geometry.

### 1.5 Detect, do not correct — and why that is enough here

Two rails on `rd_valid` detect and do not correct, on the argument in
`hw/rtl/pilot_top.v` header section 8.2; this is the same decision on
the same grounds. A dropped event is a bounded, reported wait in both
consumers. A wrong event is a spike out of nothing.

The asymmetry is the whole reason the cheap code is acceptable: what the
protection has to remove is *silence*, not loss. `docs/16` section 5.11
measured the same move on the valid flags and stated the honest form of
it — 5 SDC records became 10 announced ones, and the run may still be
wrong; what it may never be is wrong silently.

---

## 2. What was built

### 2.1 The mechanism

`hw/rtl/aer_fifo.v`, section "entry parity":

```
wr_par    = ^wr_data                     even parity, computed on write
u_par     aer_par_bank, DEPTH flip-flops, one per slot, written with
          the entry from the same wr_data on the same edge
head_raw  = {head_par, mem[rd_idx]}      the fetched codeword
head_bad  = ^head_raw                    zero exactly when consistent
rd_pass   = rd_ok && !head_bad           an accepted read that checked
par_err   = rd_ok && head_bad            the discard, reported
```

`rd_pass` and not `rd_ok` drives the two read-valid rails. The read
pointer still advances on `rd_ok`, so a failed entry is **consumed and
thrown away** rather than presented again forever — the difference
between a counted drop and a queue that has stopped. `rd_data` still
captures on `rd_ok`, unchanged, so nothing at all is added to its own
timing path; the discarded word lands there and is unreachable, because
both consumers read `rd_data` only under `rd_valid`.

### 2.2 How a discard is reported, and why not through `drop_cnt`

The obvious reuse is the queue's own sticky drop counter, which the
pilot exposes as `CNT_EVQ_OVF`, and `docs/16` section 6.2 item 4
described the interim as converting corruption "into a counted drop" on
that basis. It was costed and rejected on two facts, both readable in
`hw/rtl/pilot_top.v` **[fact]**:

- **It would report nothing for six of the seven records.** `pilot_top`
  **sinks** `u_evq_out`'s `drop_cnt` — `fo_drop` is declared, connected
  and read by nothing — on the measured grounds in its header section
  5.1: for that instance the count is backpressure cycles, not lost
  events. `docs/16` section 6.2 puts six of the seven `evq_mem` SDC
  records in `u_evq_out.mem[1..3]`. A discard counted there would be
  counted into a wire that goes nowhere.
- **It would redefine a documented register.** `regmap/regmap.yaml`
  defines `STATUS.OVF_SEEN` as "at least one software-port event dropped
  at a full input queue", and formal property P4 proves `drop_cnt`
  increments exactly on a refused write. Folding a read-side integrity
  discard into it makes the overflow measurement unreadable in both
  directions.

So the discard is reported the way the rails' detection already is:
**through the read answer that does not arrive**. Both consumers issue a
single-cycle `rd_en` and then wait for `rd_valid` under a bounded
counter — the dispatcher's `fetch_expire` for EVQ_IN and the show-ahead
adapter's `oh_expire` for EVQ_OUT — and both latch `STATUS.ERR_CFG` when
the wait expires. Those two structures exist, are measured
(`docs/16` sections 5.1 and 5.7) and are already what turns a suppressed
`rd_valid` into a DETECTED outcome rather than a hang. **A parity
discard is the same event and takes the same path, with no edit outside
`aer_fifo.v`.** Section 5 measures that this is what happens.

A new `par_err` output carries the discard as a level, following the
`ptr_mismatch` / `rv_mismatch` convention. Nothing connects it today;
giving it its own fault counter is one line in `hw/rtl/pilot_top.v`,
which this change does not own (section 9).

### 2.3 A fourth module in one file, for the same reason as the other three

`aer_par_bank` joins `aer_ptr_bank` and `aer_flag_rail` at the bottom of
`aer_fifo.v` rather than becoming `hw/rtl/aer_par_bank.v`. The
constraint is unchanged and is stated in all three existing headers:
`formal/aer_fifo.sby` lists exactly `aer_fifo.v` and its property file,
and `hw/tb/Makefile` builds the queue standalone from the same one file.
A shared fifth RTL file would break both and every flow's file list with
them.

Why it is a module at all rather than a `reg [DEPTH-1:0]` in `aer_fifo`
is a different question with a different answer, and it is section 6.

### 2.4 The simulation half

`hw/tb/test_aer_fifo.py` goes from 15 tests to **20**, and all 20 pass
at `DEPTH` 2, 4, 8 and the default 64 — `WIDTH+1` of 3, 4, 5 and 8 — so
the check is exercised at every geometry the suite is run at [fact]. The
five new tests deposit into the storage directly, for the same reason
the pointer group does: an upset lands on a physical cell and no port
produces one. They walk all four cases the header claims rather than
only the covered ones:

| test | claim |
|---|---|
| `..._is_quiet_and_stored_beside_the_word` | no traffic pattern raises `par_err`, and the bank really holds the word's parity |
| `..._single_bit_upset_in_a_stored_word_is_discarded` | every sampled slot and bit: exactly one discard, the other events golden and in order, the queue still empties |
| `..._upset_in_the_check_bit_is_a_reported_false_discard` | an upset in the new state loses an event and announces it, rather than corrupting one |
| `..._double_bit_upset_is_not_detected` | the honest limit: even weight passes the check and is delivered |
| `..._a_rewritten_slot_is_repaired` | a corrupted slot written again carries no error, so one upset is not a permanent one-in-DEPTH loss |

One of them found a defect in itself before it found anything about the
design: a two-bit deposit written as two successive read-modify-writes
to the same cocotb handle is a **one-bit** deposit, because both reads
see the pre-write value and the second write wins. Written that way the
double-bit test passed while measuring the single-bit case. The helper
now flips all the bits in one write and says why.

---

## 3. The flip-flop budget

All rows **[fact]**, produced by `sw/tests/test_synthesis_guards.py`'s
own census functions on the pinned toolchain (`make -f tools.mk
toolcheck`: yosys 0.67+146, no mismatch warning), and independently by
the hardening flow's own yosys.

| | before | after | move |
|---|---:|---:|---:|
| declared (after `proc`, before optimisation) | 1,283 | **1,291** | +8 |
| mapped, ASIC recipe (sg13g2) | 1,277 | **1,285** | **+8** |
| mapped, `synth_ecp5` | 1,277 | **1,285** | +8 |
| mapped, ASIC, `keep_hierarchy` stripped first | 1,277 | **1,285** | +8 |
| mapped, ECP5, `keep_hierarchy` stripped first | 1,277 | **1,285** | +8 |
| lost to optimisation | 6 | **6** | — |
| lost when `keep_hierarchy` is ignored | 0 | **0** | — |
| `sg13g2_dfrbpq_1` in the hardening flow's synthesis | 1,277 | **1,285** | +8 |

**+8 is one bit per entry of each 4-deep queue, both instances, and it
is what `docs/16` section 6.2 item 4 estimated.** The estimate and the
measurement agree exactly. `u_evq_in.u_par` and `u_evq_out.u_par` hold
4 flip-flops each in both flows and in both attribute-free flows.

For scale: the two queues' `mem[]` arrays are 64 flip-flops each — the
128 the campaign table names — so the check field is **6.25 % overhead
on the storage it protects** and **0.63 % of the design's register
count**.

Combinational cost, from the hardening flow's own `stat.json`, on both
recipes **[fact]**:

| | `base-6x2` | `parity-6x2` | move | `trbest_base` | `trbest_parity` | move |
|---|---:|---:|---:|---:|---:|---:|
| synthesis cells | 9,686 | 9,713 | +27 | 12,882 | **13,121** | **+239** |
| synthesis cell area (um2) | 152,099.79 | 154,152.86 | +2,053.07 | 185,393.35 | **188,176.79** | **+2,783.44 (+1.50 %)** |
| `sg13g2_xnor2_1` | 1,038 | 1,068 | +30 | 531 | 561 | +30 |
| `sg13g2_xor2_1` | 393 | 423 | +30 | 312 | 325 | +13 |

The two recipes are not comparable to each other — `config.tr-best.json`
runs `SYNTH_STRATEGY: DELAY 0`, which trades cells for depth across the
whole design — but each column pair is a controlled comparison. On both,
the XOR delta is the same order and the same shape: the four reduction
trees this change adds, a 16-input encoder on each queue's write path
and a 17-input checker on each queue's read path **[inference; the cell
counts are measured, the attribution is arithmetic on the tree
widths]**.

---

## 4. The timing budget

**The change closes, with margin, on the recovered configuration**:
derated slow-corner setup slack **+0.7992 ns -> +0.4306 ns**, zero
violations at every corner. It does **not** close on the configuration
that existed when this work started, and the two facts together are the
useful part of this section, because they say where the cost is paid and
where it is not.

### 4.1 Method, and the control that makes the numbers mean something

The concurrent timing-recovery work owns `hw/openlane/`, so every
hardening here was run **outside the repository**: the config is read
from `hw/openlane/pilot_ihp/`, every `dir::` path expanded to the
absolute path it already resolved to, copied to a scratch directory, and
run with `librelane --design-dir <scratch>` so the run tree lands there.
Nothing under `hw/openlane/` or `tt/` was written.

Because the run location, the job count and the copy could all be
confounds, **a matched control was hardened from the same scratch
directory with the same flags and the pinned `c52518e` copy of
`hw/rtl`** — the only difference between a pair of runs is the RTL. On
the pre-recovery configuration it reproduces the `docs/27` run
**exactly** [fact]:

| | `tt/runs/wave6-6x2` (docs/27) | `base-6x2` control |
|---|---:|---:|
| slow-corner setup ws | 0.32288661547280123 | **0.32288661547280123** |
| synthesis cells | 9,686 | **9,686** |
| synthesis area (um2) | 152,099.79 | **152,099.79** |

Bit-identical to seventeen digits and cell for cell, so the flow is
deterministic under this environment and every difference below is
attributable to the RTL.

Five runs are reported, all at the 6x2 submission shape, 20 ns clock:

| tag | configuration | RTL | derate |
|---|---|---|---|
| `base-6x2` | `config.6x2.json`, pre-recovery | `c52518e` | none (see below) |
| `parity-6x2` | `config.6x2.json`, pre-recovery | this change | none |
| `evqout-6x2` | `config.6x2.json`, pre-recovery | EVQ_OUT-only variant | none |
| `trbest_base` | `config.tr-best.json` | `c52518e` | **5.0 %** |
| `trbest_parity` | `config.tr-best.json` | this change | **5.0 %** |

**The first three are underated and are labelled as such throughout.**
`TIME_DERATING_CONSTRAINT` shipped as an integer and Tcl integer
division in `base.sdc` turned the 5 % into zero while the log still
said "5 %", so every timing figure previously published in this
repository is optimistic by that amount. The last two pin it to the
float `5.0` and are honest.

**And a setup violation was not, until now, a gate.**
`Checker.SetupViolations` only ever examined the typical corner.
`parity-6x2` is a demonstration: it ran to `Magic.DRC` with
`flow__errors__count` clean while carrying **14 slow-corner setup
violations**, which this document found by reading the corner's own
report. `config.tr-best.json` sets `SETUP_VIOLATION_CORNERS` to `["*"]`,
so the two `trbest_*` runs are gated on every corner as well as measured
on them.

### 4.2 The result that matters: the recovered configuration, derated

`OpenROAD.STAPostPNR`, post-PnR STA on extracted parasitics, 5 % OCV
derate, all figures in ns **[fact]**:

| Corner | Metric | `trbest_base` | **`trbest_parity`** | Move |
|---|---|---:|---:|---:|
| `nom_slow_1p08V_125C` | **setup ws** | **+0.7992** | **+0.4306** | **-0.3686** |
| | setup violations | 0 | **0** | — |
| | setup TNS | 0.0000 | **0.0000** | — |
| | hold ws | +0.5947 | +0.5911 | -0.0036 |
| | hold violations | 0 | **0** | — |
| `nom_typ_1p20V_25C` | setup ws | +7.8567 | +7.5844 | -0.2723 |
| `nom_fast_1p32V_m40C` | setup ws | +11.9543 | +11.8164 | -0.1379 |
| all three | setup / hold violations | 0 / 0 | **0 / 0** | — |

**Slow-corner Fmax: 52.08 MHz -> 51.10 MHz**, against a 50 MHz target
**[estimate, arithmetic `1000 / (20 - ws)`]**. The change costs
**0.98 MHz** and leaves **1.10 MHz** of headroom.

Worth stating plainly, because it inverts the brief this work started
from: **the design carries more margin with the parity in it and the
recovery applied (+0.4306 ns, derated) than it carried without the
parity before the recovery (+0.3229 ns, underated)**, and the second
number was the optimistic one.

### 4.3 The queue's own margin, before and after

The design's worst path and a block's worst path are different numbers,
and this document was briefed on the first as though it were the second.
Measured directly with OpenSTA on each run's post-PnR netlist and
`nom` SPEF at the slow corner, 5 % derate — the same setup, since it
reproduces each flow's own worst-slack figure to sixteen digits [fact]:

| worst setup slack of paths ending in | `trbest_base` | **`trbest_parity`** | Move |
|---|---:|---:|---:|
| `u_pilot.u_evq_in` | +9.2279 | **+9.6213** | **+0.3934** |
| `u_pilot.u_evq_out` | +11.1861 | **+12.3513** | **+1.1652** |
| `u_pilot.u_lif` | +0.7992 | **+0.4306** | -0.3686 |
| the design | +0.7992 | +0.4306 | -0.3686 |

**Both queues got faster, not slower.** The check adds a WIDTH+1 input
XOR reduction and one AND gate to a read path with more than nine
nanoseconds of slack, and after placement the queues' worst paths
improved. In `trbest_parity` the output queue's worst path does not
touch the parity logic at all — it starts at `u_rptr_c`, a pointer
replica bank. The 0.3686 ns the change costs is spent entirely on
`lif_core`'s critical path, which this change adds no logic to.

### 4.4 The pre-recovery measurement, and why it is kept

On the configuration that existed when this work started — no derate, no
slow corner in `PNR_CORNERS`, no slow-corner setup checker — the same
RTL change does **not** close [fact, underated]:

| Corner | Metric | `base-6x2` | **`parity-6x2`** | Move |
|---|---|---:|---:|---:|
| `nom_slow_1p08V_125C` | setup ws | +0.3229 | **-0.4788** | **-0.8017** |
| | setup violations | 0 | **14** | +14 |
| | setup TNS | 0.0000 | **-4.2538** | -4.2538 |
| `nom_typ_1p20V_25C` | setup ws | +7.5628 | +7.0550 | -0.5078 |
| `nom_fast_1p32V_m40C` | setup ws | +11.8588 | +11.5369 | -0.3219 |

Every one of the 14 violating endpoints is inside `u_pilot.u_lif` and
all of them share one startpoint, `u_pilot.u_lif._5478_` **[fact,
`55-openroad-stapostpnr/nom_slow_1p08V_125C/max.rpt`]** — the same
conclusion section 4.3 reaches from the other direction. It is kept
because it is the measurement that shows what the recovery bought:
**the identical RTL delta costs 0.8017 ns on the old recipe and
0.3686 ns on the recovered one**, and closes only on the second.

### 4.5 The cheaper variant, measured — and why it was not needed

Before the recovery landed, the obvious fallback was to protect
**EVQ_OUT only**: `docs/16` section 6.2 puts **six of the seven**
`evq_mem` SDC records in `u_evq_out.mem[1..3]` and one in
`u_evq_in.mem[0]`, so half the logic buys 86 % of the benefit. It was
built as a parameterised variant and hardened through the identical
pre-recovery flow **[fact, underated]**:

| Run | new FF | synthesis cells | synthesis area (um2) | placed util | slow-corner setup ws | setup vio |
|---|---:|---:|---:|---:|---:|---:|
| `base-6x2` | — | 9,686 | 152,099.79 | 0.472225 | **+0.3229** | 0 |
| `evqout-6x2` (EVQ_OUT only) | +4 | 9,725 | 153,106.29 | 0.474464 | **-0.3831** | 14 |
| `parity-6x2` (both queues) | +8 | 9,713 | 154,152.86 | 0.476878 | **-0.4788** | 14 |

**Halving the protection recovers 0.0957 ns of the 0.8017 ns lost —
12 %**, and the same 14 endpoints still violate. So the cheaper variant
was never the answer: the loss was not proportional to what was added,
because what was added is not on the path that fails. The variant is
recorded rather than shipped, and `aer_fifo` carries no `PARITY`
parameter in the tree — a parameter with one legal value is dead weight,
and turning it off would need an edit to `hw/rtl/pilot_top.v` anyway.

Two further observations from that table, both worth carrying:

- **Cell count is not monotonic in the change.** The half-size variant
  synthesises to *more* cells than the full one (9,725 against 9,713)
  while occupying less area — the same lesson `docs/27` section 2.2
  recorded when the cell count fell by 135 while the area rose.
- **`docs/27`'s own datapoint says the same thing.** Wave 6 spent
  0.9118 ns of slow-corner margin for **+2 flip-flops**. This change
  spent 0.8017 ns for +8 on that recipe. Neither is proportional to what
  was added, and section 4.3 says why: the sensitive path is not the one
  being changed.

### 4.6 What this means for shipping

**Ship it, on the recovered configuration, and re-harden before
submission.** The three statements that follow from the measurements
above:

1. **The queue is not where the timing is spent, so do not design the
   protection around the queue's read path.** It has 9 to 12 ns of
   slack, and the check made it faster, not slower. Section 1.4 uses
   that to say a SECDED decoder would also fit, and section 9 item 7
   recommends taking it.
2. **What the design is sensitive to is added AREA, on a path elsewhere.**
   That is a property of the placement at this utilization, it is now
   measured three times, and it applies to every future RTL wave — the
   `dispatch` and `lif_scan` items still open in the residual as much as
   this one.
3. **Numbers from before 2026-08-30 are underated and are not
   comparable.** `docs/27`'s +0.3229 ns and everything derived from it,
   including this document's own sections 4.4 and 4.5, are optimistic by
   the missing 5 %. The only numbers to plan with are section 4.2's.

---

## 5. The campaign

`hw/tb/test_fi_campaign.py`, 8 x 8 geometry, same seed, same workload,
same bursts. **374 injections, 1,755 s wall** against the 366 of
`docs/16` section 5.11 [fact]. The log is
`hw/tb/fi_campaign_results.json` and it is diffed **by key** — the
group, the target path, the deposited bit and the drawn (burst, delay)
phase — because the record order follows the target list and inserting a
group shifts every later line.

| | MASKED | CORRECTED | DETECTED | SDC | HANG | n |
|---|---:|---:|---:|---:|---:|---:|
| after `docs/16` section 5.11 | 94 | 193 | 61 | **18** | 0 | 366 |
| after this change | 100 | 193 | **70** | **11** | 0 | **374** |

**366 common records, and exactly 7 of them changed anything at all
[fact].** Every one is `evq_mem`, and every one is the same move:

| target | before | after |
|---|---|---|
| `u_evq_in.mem[0]` bit 0, bit 14 | **2 SDC**, status `0x06` | **2 DETECTED**, status `0x16` |
| `u_evq_out.mem[1]` bit 0, bit 14 | **2 SDC**, status `0x06` | **2 DETECTED**, status `0x16` |
| `u_evq_out.mem[2]` bit 0, bit 14 | **2 SDC**, status `0x06` | **2 DETECTED**, status `0x16` |
| `u_evq_out.mem[3]` bit 0 | **1 SDC**, status `0x06` | **1 DETECTED**, status `0x16` |

`0x06 -> 0x16` is `STATUS.ERR_CFG` latching — the consumer's bounded
wait expiring on a read answer that never came, which is the reporting
path section 2.2 chose and did not have to build. **No other record in
the campaign moved in any field**: not its class, not its status, not
its counters, not its event stream, not its neuron state.

| group | before | after |
|---|---|---|
| `evq_mem` | 25 / 0 / 0 / **7** / 0 | 25 / 0 / **7** / **0** / 0 |
| `evq_par` (new) | — | **6 / 0 / 2 / 0 / 0** |

**The residual is 11 across four structures** — `dispatch` 5,
`lif_scan` 3, `evq_hold` 2, `regbank_cfg` 1 — from 18. **`evq_mem` is
closed**, and the AER event path now has no unprotected structure left
in it.

**The claim is narrower than "7 corruptions removed", and it should
stay narrow.** Two rails made 5 silent records into 10 announced ones
and `docs/16` section 5.11 insisted on saying so; the same discipline
here. The 7 events are still **lost** — parity detects and does not
correct — and what changed is that the pilot now says so instead of
handing the consumer a spike that was never sent. Section 1.4 records
that correcting them instead is affordable and is the recommended next
step.

**The new state was measured, not argued [fact].** The check field is 8
flip-flops this hardening adds, and an upset in one of them makes a good
event fail its check. `target_list` item 15 injects into
`{u_evq_in,u_evq_out}.u_par.bits` at the storage register, on the same
footing items 9 and 11 were rewritten to: 8 injections, **6 MASKED, 2
DETECTED, 0 SDC**. The false discard is announced exactly like the real
one, which is why adding unprotected state here is acceptable.

**Two pass criteria were added to `test_05_summary`**, on the two-part
footing the pointer and rail groups use — the failure to catch is a
mis-targeted injector, not a broken checker:

- every `evq_mem` target is a stored queue word and every `evq_par`
  target is the check field's own storage register, so a future edit
  that re-points either at a downstream wire fails here; and
- `evq_mem` and `evq_par` together must show **no SDC**. It is written
  as "no SDC" rather than "all DETECTED" because a slot the workload
  never reads is legitimately MASKED — 25 of the 32 `evq_mem`
  injections are exactly that.

---

## 6. The netlist evidence, and the merge trap in its third form

### 6.1 Why this structure needs its own guard

Three structures in this design have been silently merged away by
synthesis — the configuration TMR (`docs/20` section 11), and the two
the pointer and rail guards were written for — and **every one was
caught by counting flip-flop cells, not by simulation**. The hazard here
is not the one those guards are shaped against. A check field has no
twin, so `opt_merge` has nothing to hash it into.

The hazard is the one `hw/rtl/lif_core.v`'s `wchk` and `smem` carry, and
it is sharper here because the field is one bit wide:
`par_shadow[i]` is a pure **function** of `mem[i]` in every reachable
state, so a tool able to reason across sequential state could delete the
storage, rebuild the bit from the write-side encoder, and leave a
checker that reports every stored word clean. That is protection which
passes every simulation in this repository and detects nothing in
silicon. Nothing in yosys does that today; this test is what says so
tomorrow.

### 6.2 Why the storage is a `keep_hierarchy` module

Countability, first, and the fold second.

Under LibreLane's `deferred_flatten`, abc renumbers every cell to
`_NNNN_` before the flatten, so **an instance path is the only naming
that reaches the shipped netlist**. A plain `reg [DEPTH-1:0]` in
`aer_fifo` would be a structure checkable in this repository's yosys
*model* of synthesis and not in the artifact that becomes silicon —
which is precisely the distinction section 4 of
`sw/tests/test_synthesis_guards.py` exists to make. As an
`aer_par_bank` instance the field is counted at `u_evq_in.u_par.` and
`u_evq_out.u_par.` in the netlist LibreLane actually produced.

Second, `flatten` skips a module carrying the attribute and no
optimisation pass runs after the deferred flatten, so the fold has a
structural barrier in front of it as well as a test behind it. Neither
is trusted alone, which is this repository's rule for all three
redundant structures.

### 6.3 What was added, and what it measured

Four tests, and the file goes from **25 passed / 2 skipped** to
**30 passed / 1 skipped** on the repository's own run trees, and to
**31 passed / 0 skipped** with the `trbest_parity` run tree added
through `NSSOC_RUN_TREES` [fact]. The single skip without it is the
shipped-netlist guard, correctly reporting that no run in the repository
was built from RTL declaring `aer_par_bank`:

| test | flow | reads |
|---|---|---|
| `test_entry_parity_is_stored_in_the_asic_flow` | yosys, LibreLane-shaped, sg13g2 | 4 per queue |
| `test_entry_parity_is_stored_in_the_ecp5_flow` | `synth_ecp5` | 4 per queue |
| `test_entry_parity_survives_a_flow_that_ignores_keep_hierarchy` | `synth_ecp5`, attribute stripped before synthesis | 4 per queue |
| `test_entry_parity_survives_the_real_hardening_flow` | the netlist LibreLane produced | 4 per queue |

The existing catch-all covers it too and is the stronger of the pair in
the attribute-free case: `test_config_tmr_survives_a_flow_that_ignores_
keep_hierarchy` allows **zero** lost flip-flops across the whole design,
and a folded check field is eight lost flip-flops there. Measured, with
`keep_hierarchy` stripped before synthesis the design still maps to
1,285 in both flows — nothing is lost.

**The shipped netlist, which is the one that matters [fact].** The
`trbest_parity` run's `final/nl/tt_um_melihakbulut_nssoc.nl.v` —
`SYNTH_HIERARCHY_MODE: deferred_flatten`, 1,285 flip-flops, the netlist
that would have been fabricated — carries **4 flip-flops under
`u_evq_in.u_par.` and 4 under `u_evq_out.u_par.`**, alongside 55 under
`u_cfg_a.`, 3 under each pointer bank and 1 under each valid-flag rail.
All four shipped-netlist guards assert rather than skip against it, and
the whole file is **31 passed, 0 skipped**.

The run tree lives outside the repository (section 4.1), so this file
gained an `NSSOC_RUN_TREES` environment variable that ADDS trees to the
three it already searches. It cannot subtract: the in-repository trees
are still searched, still the default, and the `deferred_flatten`
discriminator is unchanged, so it cannot be used to point the guards at
a friendlier netlist while the real one goes unchecked.

Unlike the pointer banks and the rails there is **no storage transform**
behind the attribute here, and there is nothing for one to do: a check
field has no twin to be held apart from. What holds the storage in place
without the attribute is that no pass in this yosys does the sequential
equivalence the fold would need. That is stated in the test rather than
assumed.

### 6.4 Mutation check

**The mutation is the fold itself, written as RTL so it can be run**: a
scratch copy of `hw/rtl` in which the check reads
`^mem[rd_idx]` — the parity recomputed from the data — instead of the
stored bit. The bank is left instantiated and left written; only the
CHECK changes. That is exactly the netlist a sequential-equivalence
optimisation would produce: the storage dead, the bit rebuilt from its
encoder, and a checker that reports every stored word clean. Run with
`NSSOC_RTL_DIR` pointed at the scratch tree **[fact]**:

- the ASIC total goes **1,285 -> 1,277**, the eight check flip-flops
  gone;
- **exactly three tests fail** — `3 failed, 27 passed, 1 skipped` —
  and they are the three added in section 6.3 that count the bank; and
- **nothing else in the file notices**, and nothing in the cocotb
  campaign could, because the RTL still contains the storage and RTL
  simulation cannot see a register that synthesis deletes.

**A first mutation attempt did not fail, and that is worth recording.**
The same fold written with the bank's output merely left unread passed
all 28 tests: `(* keep *)` on `bits` holds the flip-flops against
`opt_clean` even when nothing reads them, so the census still counted
four per queue. `keep` preserves storage that is dead; it does not
preserve storage that is *absent*. The mutation had to remove the read
of the stored bit, not just its consumer, before it modelled the defect
— and a mutation that passes is a mutation that was testing the wrong
thing.

### 6.5 The provenance rule was wrong, and this test found it

The shipped-netlist guards skip when no run on disk could contain the
structure and fail when a run contains it and the structure is missing.
Until this change the discriminator was the run's **modification time**
against the RTL file's. That is not sound when two changes are in
flight: measured 2026-08-30, `hw/openlane/pilot_ihp/runs/tr-control`
postdates the edit that introduced `aer_par_bank`, was hardened by the
concurrent timing work from a tree that did not contain it, and was
therefore accepted as a witness — so the guard **failed**, reporting a
collapse, where it should have skipped **[fact]**.

The replacement is the run's own yosys JSON header, which lists the
module names of the **elaborated** design. It is written before any
optimisation pass runs, so it records what synthesis was handed and not
what it did — which is the property a provenance discriminator needs,
and the reason it cannot skip on the symptom. `_witness_runs` applies it
to all three guards, not only the new one: the pointer guard now
requires `aer_ptr_bank` in the header and the rail guard requires all
three of `pilot_flag_rail`, `aer_flag_rail` and `lif_flag_rail`. Runs
with no header on disk fall back to the old mtime rule, so older run
trees behave as they did.

---

## 7. Formal

`aer_fifo` is a formally proven leaf with four SymbiYosys tasks and they
are part of this change, not a check run after it.

### 7.1 The fault model

`hw/rtl/aer_fifo.v` declares a seventh free vector under `ifdef FORMAL`,
over the **fetched codeword** `{check bit, data word}`, free every
cycle, and `formal/aer_fifo_props.v` constrains it to the weight one
check bit can claim: `(x & (x - 1)) == 0`, which is zero exactly for a
vector of weight 0 or 1, in plain Verilog-2005 and without
`$countones`. It is on in **all four tasks**, on the same reasoning the
existing pointer injection is: the fault-free design is the case where
the solver picks zero, so P1..P6 are proven in the presence of a queue
entry upset rather than beside one.

Injecting at the read port rather than into `mem[]` is a **superset** of
injecting into the storage, not a weakening of it. The delivered word
and the checked word are the same expression in the same cycle, so for
the read that matters the two are identical; a vector free every cycle
also covers a stored bit that stays wrong across many reads; and it
additionally covers a slot that is rewritten and still reads wrong,
which storage injection cannot reach.

The even-weight case is **excluded by an assumption rather than hidden
by one**. That is the limit of one check bit, it is stated in the RTL
header and in section 8, and `hw/tb/test_aer_fifo.py` measures it.

### 7.2 What was added

- **P10**, the stored-parity invariant: an in-flight slot's check bit is
  the even parity of its word. It reuses P5's two anyconst slots.
- **P11**, exact reporting in both directions, on P8's footing:
  `par_err` is high if and only if a read was accepted while the fetched
  codeword carried an upset. The reverse half matters as much as the
  forward one — a checker that fired on clean traffic would destroy
  events at the rate the queue runs at.
- **P12**, the safety theorem: whenever `rd_valid` is high the fetched
  codeword was intact, so no consumer is ever handed a word that is not
  the word that was written.
- **P13**, two reachability covers: an entry upset is detected during
  traffic, and the queue then delivers a good event — which is what says
  the discard consumed the entry rather than parking the read pointer on
  it. Without them P11 and P12 could pass over an empty set of faults.
- **P5 was rewritten, not left alone.** Its readout assertions and the
  exactness of `rd_valid` are now qualified by `rd_pass` (accepted AND
  checked) rather than `rd_ok`. Asserting the old form would be
  asserting that a corrupted entry is still delivered correctly, which
  is the claim the check exists to refuse.

### 7.3 One measurement that changed the shape of the proof

The first draft stated P10 over **all** `DEPTH` slots with a generate
loop, on the reasoning that P11 needs the invariant at `rd_ptr` and an
anyconst address is one fixed address inside a trace. That reasoning is
wrong — universal quantification over the anyconst delivers the
invariant at every reachable head address if the property that needs it
is **conditioned** on the anyconst being the head — and it is expensive:
sixty-four sixteen-input XOR reductions inside the inductive invariant
took the `prove` job past ten minutes without converging **[fact]**. The
form that shipped states the invariant twice, once per token.

The intermediate version, with the invariant on one token only, **failed
induction** on the *other* token's readout (`aer_fifo_props.v:205): the
solver started in a state where slot `f_addr2` held a check bit that was
not its word's parity, passed the check with a compensating injection,
and delivered a word that was not `f_data2` **[fact, counterexample
trace]**. Both facts are recorded in the property file next to the code
they explain.

### 7.4 A cover statement that could not be reached, and why that is the job working

`cover ($past(par_err) && rd_valid)` was the first form of P13's second
half, and the cover job reported it **unreached at depth 150** [fact].
It is not a design defect and no amount of depth would have helped: it
is unsatisfiable by construction. `par_err` high at cycle t means
`rd_pass` was LOW at t, and `rd_valid` at t+1 is exactly
`$past(rd_pass)`, so the two can never coincide. The property file was
wrong about its own design. It now uses a sticky `f_seen_par` and covers
`rd_valid && f_seen_par` — the queue delivering a good event after
having discarded a corrupted one, which is the statement that was
wanted.

Recorded rather than quietly fixed because it is the second time in this
change that a check found a mistake in the checking rather than in the
design: section 7.3's induction failure was the first, and section 6.4's
mutation-that-passed was the third.

### 7.5 Results and runtimes

All four tasks **PASS** [fact]. Runtimes on the pinned toolchain
(`make -f tools.mk toolcheck`: yosys 0.67+146, yices), measured on an
otherwise idle machine so they are comparable with the numbers
`formal/aer_fifo.sby` already records:

| task | before | after | move |
|---|---:|---:|---|
| `prove_d4` | 1 s | **3.58 s** | +2.6 s |
| `prove` | 41 s | **80.19 s** | 2.0x |
| `bmc` | 5 min 48 s | **12 min 11 s** | 2.1x |
| `cover` | 29 min 19 s | **41 min 55 s** | 1.4x |

All eight cover statements are reached, P13's two among them:
`cover (par_err)` at step 3 and `cover (rd_valid && f_seen_par)` at step
5, so the entry fault model is not vacuous and the discard demonstrably
consumes the entry rather than parking the read pointer on it.

**The cost is the fault model, not the properties**, the same conclusion
`aer_fifo.sby`'s header already reached about the pointer injection:
seventeen more free bits per cycle over `{check bit, data word}` roughly
doubles the three assertion-carrying jobs. It was measured, not assumed
— an earlier draft of P10 that stated the invariant over all `DEPTH`
slots took `prove` past ten minutes without converging (section 7.3),
and the form that shipped is 80 s.

---

## 8. What remains unprotected

Stated as bounds rather than as reassurance, in the order a reviewer
should care about them.

**1. Even-weight corruption of a stored entry.** One check bit detects
every odd-weight error and no even-weight one, so two upsets in the same
16-bit entry between its write and its read pass the check and the
corrupted word is delivered as a valid event. This is the residual after
this change and it is what SECDED (22,16) would have bought for six
check bits per entry instead of one (section 1.2).
`hw/tb/test_aer_fifo.py::test_double_bit_upset_is_not_detected` measures
it rather than leaving it to be discovered, and the formal fault model
excludes it by an explicit assumption rather than by silence. The
exposure window is short — an entry lives in the queue for as long as it
takes the consumer to drain it, tens of cycles at the pilot's rates —
which is why one bit is a reasonable trade and not a shortcut
**[estimate on the window; the detection bound is arithmetic]**.

**1b. The design's remaining margin, and what any further wave costs.**
Section 4 leaves **+0.4306 ns derated at the slow corner** — 2.15 % of
the cycle, 51.10 MHz against a 50 MHz target — and measures that this
design's slack responds to how much AREA a change adds rather than to
where it adds it. The two items still open in the residual, `dispatch`
at 5 records and `lif_scan` at 3, will each cost some of that. This
document does not leave a timing problem behind, but it does leave a
timing budget that the next wave has to be measured against rather than
assumed into.

**2. `rd_data` itself, and everything downstream of the check.** The
check is on the storage, so the registered output word is downstream of
it and is not covered. `docs/16` puts `u_evq_out.rd_data` in the
`evq_hold` group, where it is 0 of 2 SDC in the current campaign, and
that flip-flop remains what it was. The show-ahead adapter's `oh_data`
(2 of 6 SDC in `docs/16` section 6.2) is downstream again and is
likewise untouched by this change — it lives in `hw/rtl/pilot_top.v`.

**3. The check field is not itself redundant.** An upset in one of the 8
new flip-flops makes a good event fail its check and be dropped:
announced, and the same cost as the case the field exists to catch, but
a real event lost that would not have been lost without the hardening.
Section 5 measures the rate. Protecting the check field would need a
code over the check field, which is what a real SECDED word does by
including its own check bits in the codeword — one more reason the full
answer belongs with the macro.

**4. The queue is still not a coded memory.** The right answer for a
large regular array arrives with the SRAM macro, where the ECC comes
with the compiler rather than out of the flip-flop budget and the
decoder is inside the macro's own timing model. `docs/16` section 6.1
item 4 makes the same judgement about `wmem` for the same reason. At
the NPU scale of `docs/10` section 7.2 — 64 entries per node, one queue
per node — the flip-flop cost of a per-entry SECDED field is not a
budget item this pilot can carry.

**5. `par_err` is not counted.** The discard is reported through the
consumers' bounded waits, which latch `STATUS.ERR_CFG` — an operator
learns that the queue lost an event, not that it lost it to a failed
integrity check rather than to a configuration fault. The distinction
costs one counter and is section 9 item 2.

---

## 9. What must change in other documents and files

This change owns `hw/rtl/aer_fifo.v`, `hw/tb/test_aer_fifo.py`,
`formal/aer_fifo.sby`, `formal/aer_fifo_props.v`,
`hw/tb/test_fi_campaign.py`, `hw/tb/fi_campaign_results.json`,
`sw/tests/test_synthesis_guards.py` and this document. Everything below
is outside that set and is recorded rather than done, on the convention
`docs/27` used.

**0. Three tests are knowingly red, all mechanical, none a defect.**
`sw/tests/` is **183 passed, 3 failed** and the three are item 1 below
and two in `sw/tests/test_tt_submission.py`. The latter two are
`tt/src/aer_fifo.v` having drifted from `hw/rtl/aer_fifo.v`: the
submission tree is generated, `tt/` is outside this change's ownership,
and the copy on disk was regenerated at 18:55 while this file was still
being edited, so it is a stale snapshot rather than a divergence of
intent. The remedy is the one the test prints, `python3
scripts/gen_tt_submission.py`, and it must be run before submission.

**1. `docs/00-index.md` must gain a row for this document — and until it
does, `sw/tests/test_doc_links.py` FAILS.** That test enforces "every
document is reachable from the index", by discovering the corpus rather
than listing it, so a new document is in scope the moment it exists.
This is a known, deliberate, one-line debt and it is the only test in
the repository this change leaves red. The row:

> `docs/29-queue-storage-protection.md` | One even-parity bit per AER
> queue entry, checked on the read and discarded on failure. Closes the
> `evq_mem` silent-corruption group at +8 flip-flops, and costs the
> slow-corner margin the amount section 4 measures.

**2. `hw/rtl/pilot_top.v` should count `par_err`.** The port exists and
is unconnected. One edge-detected counter on the `CNT_TMR` pattern —
`wire evq_par_event = fi_par_err || fo_par_err`, edge-detected in the
fault-counter block on `rst_n` so `CTRL.SOFT_RST` cannot erase it —
turns "the queue lost an event" into "the queue discarded a corrupted
entry". Section 8 item 5.

**3. `docs/16` section 6.2 item 4 is now DONE and should say so**, in
the form sections 5.10 and 5.11 use for the items they closed: the
interim it proposed is built, at the flip-flop cost it estimated, and
the residual it reports moves from 18 records to the number section 5
measures. Its `evq_mem` row and its section 5.2 residual list are the
two places that carry the old number.

**4. `docs/27` section 3's timing table has a successor.** Section 4
below is the next measurement of the same corner on the same shape, and
`docs/27`'s open item 2 — "which path lost the margin" — is still open;
this document narrows it only in the sense that it says which paths did
*not* cause the next move.

**5. `hw/openlane/aer_fifo/config.json` still hardens this module
standalone under LibreLane's default `flatten`**, so the derived
`$paramod` types of `aer_ptr_bank` reach the mapped netlist and
`Checker.YosysUnmappedCells` aborts. `aer_par_bank` is a fourth
`keep_hierarchy` module in the same file and makes that pre-existing
defect no better and no worse. The fix is the `deferred_flatten` key the
other three configs already carry; it is recorded in `hw/rtl/aer_fifo.v`
and is not this change's to make.

**6. `hw/tb/Makefile.gl` and `hw/tb/Makefile.glfi` still default to the
`shape-6x2` netlist**, which `docs/27` already superseded and which this
change supersedes again. The gate-level suites are measuring an RTL two
waves old.

**7. Measure SECDED (22,16) on the queue, and take it if it closes.**
This is the recommendation section 1.4 defers to. The queue's read path
has 9 to 12 ns of slack (section 4.3), so the decoder fits; what is
unmeasured is whether the extra area costs more of `lif_core`'s margin
than the +0.4306 ns that is left. The experiment is exactly the pair of
runs section 4 already ran — `config.tr-best.json`, one control, one
with the code — and it is cheap. If it closes, correction beats a
counted drop in a spike train and the even-weight residual of section 8
item 1 closes with it. The codec measured here is 33 cells for the
encoder and 84 for the decoder per queue instance, plus 6 check bits per
entry.
