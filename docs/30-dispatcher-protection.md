# 30 — Wiring the queue discard to telemetry, and checking the dispatcher

Status: complete. Two independent changes to `hw/rtl/pilot_top.v`,
reported separately because they stand or fall on separate evidence:

1. **`par_err` reaches a register.** `hw/rtl/aer_fifo.v` has raised
   `par_err` on every entry-parity discard since `634ca3e` and
   `pilot_top` connected it to nothing. It now drives a pilot-only
   saturating counter, `CNT_EVQ_PAR` at `0x0B0`. `docs/29` section 9
   item 2 named this and explicitly did not own it.
2. **The event dispatcher gets a two-bit check field.** `dstate` and the
   twelve bits of `evw` the dispatcher acts on each carry a parity bit,
   held in one `pilot_chk_bank` instance. This closes the `dispatch`
   group, which led the residual at 5 silent corruptions of 18.

Pinned to `634ca3e` plus these changes. **No document other than this
one is edited**; section 8 lists what must change elsewhere.

Convention, inherited from `docs/18`, `docs/22`, `docs/27` and
`docs/29`: **[fact]** = measured in this environment or read out of an
installed file; **[estimate]** = derived or judged.

Run trees under `hw/openlane/*/runs/` and `tt/runs/` are gitignored and
`hw/openlane/` is outside this change's ownership, so the hardening
below was run **outside the repository** by the method `docs/29`
section 4.1 established. Every number is quoted with its run tag.

### Headline

- **Item 1 is one wire, one counter and one edge register, and its
  measured effect is a distinction rather than a class change.** All
  nine parity discards in the campaign already read `DETECTED`; what
  they could not say was *why*. Section 2, section 5.1.
- **One counter for both queue instances**, on the `CNT_TMR` precedent
  and against the `CNT_EVQ_OUT_OVF` one. The two differ in whether the
  signal *means* the same thing in both instances, and `par_err` does.
  Section 2.2.
- **Item 2's five records are data corruption, not deadlock**, so
  neither of the dispatcher's two previous rounds applies. Two are
  `dstate` flips that a 2-bit encoding cannot see at all — including
  `D_FETCH` → `D_ISSUE`, which is legal-word to legal-word — and three
  are `evw` field corruptions issued as real events. Section 3.1.
- **The one-bit pigeonhole binds at two bits as well, and that is a
  proof rather than a measurement.** A bijective replica's coordinate
  functions are balanced; there are exactly six balanced functions of
  two variables; A and B take four; the remaining two are complements of
  each other and determine nothing. `dstate` cannot be tripled either.
  Section 3.2.
- **The protection is +2 flip-flops for 5 records**, the best
  benefit-per-flip-flop of any wave in this project. Total cost of both
  items is **+11 flip-flops, 1,285 → 1,296 mapped** [fact]. Section 4.
- **Timing does not bind. Slow-corner setup went +0.4306 → +1.0423 ns**,
  zero violations at every corner with a real 5 % derate — but the
  worst path is inside `u_lif` in *both* runs and neither change touches
  it, so this is placement variation and not a speedup the change
  earned. Section 6 says so plainly and gives the number that is
  actually attributable.
- **Campaign: 11 silent corruptions → 6, across three structures
  instead of four.** `dispatch` joins `evq_mem` as closed. 374 → 378
  records, 364 of them field-for-field identical, and exactly 10 moved.
  Section 5.
- **The redundancy is counted in the shipped netlist and the guard is
  mutation-checked twice**, once with the storage removed and once with
  only the attributes removed. Section 7.
- **A cost is reported, not buried**: one campaign record that used to be
  harmless now loses an event, announced. Section 5.3.

---

## 1. Item 1: the discard that reached no register

### 1.1 What was wrong

`docs/29` gave every AER queue entry an even-parity bit and made a
failed check discard the entry: the read pointer advances, `rd_valid` is
held low, and `par_err` goes high for that cycle. `pilot_top`
instantiated the queue twice and connected `par_err` neither time.

So the only thing a host saw was the consumer's bounded wait expiring —
`fetch_expire` for EVQ_IN, `oh_expire` for EVQ_OUT — which latches
`STATUS.ERR_CFG`. That bit already means "a configuration fault happened
here". An operator reading it could not tell a configuration fault from
an event thrown away because its stored word no longer checked, and
those two call for different responses.

This is the defect `2d59ec2` fixed for the `lif_core` memory ECC, in the
same shape and with the same argument. That commit's own message states
it: *"an unreported correction is indistinguishable from no upset"*. The
codes were working and the evidence was going nowhere. Here the
mechanism is detection rather than correction, so the sentence becomes
*an unattributed loss is indistinguishable from a different loss*, but
the defect class is identical and the precedent is binding for a part
whose stated purpose is measuring the upset environment.

### 1.2 What was built

```
wire evq_par_err   = fi_par_err || fo_par_err;
wire evq_par_event = evq_par_err && !evq_par_q;     // rising edge
```

feeding `cnt_evqp`, a `CNT_W`-bit saturating counter read at `0x0B0` as
`CNT_EVQ_PAR` and cleared by `FAULT_CLR` bit 7. Both the counter and the
edge register live in the fault process on `rst_n`, not on `blk_rst_n`,
so `CTRL.SOFT_RST` — the recovery for exactly this class of fault —
cannot erase the record that it happened. That arrangement and its
reason are `CNT_TMR`'s and `CNT_EVQ_OUT_OVF`'s, unchanged.

**No new sticky, and that is deliberate.** Every discard already reaches
`STATUS.ERR_CFG` through the bounded wait — measured, `docs/29` section
5: all seven moved status `0x06` → `0x16` — so a second sticky would
report the same event twice, and there is no free `STATUS` bit to spend
on it. What was missing was never the alarm. It was the attribution.

**Pilot-only, not promoted into `regmap/regmap.yaml`**, on section 5.1's
three arguments carried over verbatim and on one that is specific to
this counter. The fault block of the architecture map is contiguous from
`0x70` to `0x88`, so a promoted counter lands at `0x8C`, and the
convention `sw/tests/test_regmap.py` checks — one clear bit per
fault-block register in offset order — would then hand it `FAULT_CLR`
bit 5. Bit 5 is the bit this pilot already spends on `CNT_TMR`.
Promoting the counter therefore renumbers `CNT_TMR` and
`CNT_EVQ_OUT_OVF` and breaks the portable clear-everything write that
`regmap.yaml`'s own `FAULT_CLR` description promises. `docs/15`'s D5 row
is the standing record for exactly this shape, and `pilot_top`'s header
section 5 is where the bit assignment lives. The portable
clear-everything write goes from `0x7F` to `0xFF`.

### 1.3 The decision this change had to make: one counter or two

Two queue instances raise `par_err`, and the file already contains both
precedents.

**Against splitting, and this is what was done.** `CNT_TMR` merges
`fi_ptr_mm` and `fo_ptr_mm` into a single episode count, because a
corrected pointer upset is the same event with the same consequence
whichever queue it happened in. A parity discard is that shape exactly:
one stored 16-bit event lost, announced through a bounded wait, in
instances of identical width and identical semantics. `par_err` is
`rd_ok && head_bad` in both, and in both it means one event that existed
and no longer does.

**For splitting.** `CNT_EVQ_OUT_OVF` exists precisely because
`aer_fifo`'s `wr_en && full` count *means different things* in the two
instances — refused software writes in EVQ_IN, ordinary lossless
backpressure cycles in EVQ_OUT — so one register could not have carried
both without publishing a number that is not an event-loss count
(`pilot_top` section 5.1, measured: `fo_drop` reaches 223 with nothing
lost). That asymmetry is real and it is why that split was right. It
does not exist for `par_err`.

**And the split is not free.** It costs a second `CNT_W` counter (+8
flip-flops), a second register offset, a second `FAULT_CLR` bit, and a
second row in every document and test that lists the map — to answer a
question no operator action depends on. The recovery is the same for
either queue, and a host that wants the instance can already read
`EVQ_STAT` and `STATUS`. Two counters would also break the symmetry with
`CNT_TMR`, which is the register a host reads next to this one.

**One counter, on the `CNT_TMR` precedent**, edge-detected on the OR so
that a persistent discard counts once and simultaneous discards in the
two queues count once — the same episode convention, stated in the same
words, because a host reading the two registers side by side must not
have to remember two conventions.

---

## 2. Item 1: measured

### 2.1 What the campaign group does

`hw/tb/test_fi_campaign.py` already carries an `evq_par` group
(`target_list` item 15): 8 deposits into
`{u_evq_in,u_evq_out}.u_par.bits`, the check field's own storage.
`docs/29` measured it at **6 MASKED / 2 DETECTED / 0 SDC**.

**After this change the group's classification is unchanged: still 6 / 0
/ 2 / 0 / 0** [fact]. So is `evq_mem`'s: still 25 / 0 / 7 / 0 / 0. That
is the honest headline for item 1, and it is worth stating plainly
rather than dressing up.

**The counter adds no DETECTED record, because there was none left to
add.** Every parity discard in this workload already latched
`STATUS.ERR_CFG` through a bounded wait, and `classify()` reads
`ERR_CFG` first. A counter cannot promote a record that is already in
the top class.

What changed is one field per record, and it is the field the
classification cannot carry:

| group | records | `cnt_evq_par` after the run |
|---|---:|---|
| `evq_mem` DETECTED | 7 | **1** each |
| `evq_par` DETECTED | 2 | **1** each |
| `evq_mem` MASKED | 25 | 0 |
| `evq_par` MASKED | 6 | 0 |
| every other group | 334 | **0** |

The 9 discards now show `telemetry_ok = False` — the counters moved
because of the injection, which the summary already labels as "the
design correctly counting the event it was given" — where before the
change they were indistinguishable from a configuration fault in every
recorded field.

### 2.2 Two criteria added, in both directions

`test_05_summary` gains a pair, on the two-part footing every hardening
in this campaign uses. The failure to catch is a cut wire, and a cut
wire looks like a quiet part:

- **every** `DETECTED` record in `evq_mem` or `evq_par` must have
  counted at least one discard; and
- **no** record in any other group may count one, because no other group
  corrupts a stored queue word or its check bit.

The second half is what stops the counter from being wired to something
that merely correlates with a discard. Both hold [fact].

`cnt_evq_par` also joins `COUNTERS`, so it is read back on every one of
the 378 injections and compared against the same bring-up undeposited,
and it joins the `detected` term of `classify()` — beside `cnt_ded`,
`cnt_ovf` and `cnt_oor`, the counters that mean "a fault happened and
the part noticed", rather than beside `cnt_sec` and `cnt_tmr`, which
mean "and the part repaired it". A discard repairs nothing.

`hw/tb/test_pilot_top.py` gains a directed test that corrupts one stored
check bit, lets the dispatcher fetch the entry, and asserts the counter
reads 1, `STATUS.ERR_CFG` is set, the `ERR` pin is high, `CNT_TMR` is
still zero, and that `FAULT_CLR` bits 2, 5 and 6 do not clear it while
bit 7 does.

---

## 3. Item 2: what the five records actually are

### 3.1 Read out of the log, not inferred

`hw/tb/fi_campaign_results.json` at `634ca3e`, `dispatch` group, the
five `SDC` records [fact]:

| target | bit | phase | what the run produced |
|---|---|---|---|
| `dstate` | 0 | b1 d7 | event 4 missing from `[1,2,5,6,4,2]` |
| `dstate` | 1 | b2 d0 | last event **7** where 2 was expected |
| `evw` | 0 | b1 d8 | `[1,2,5,6,7,2,3]` — wrong axon, wrong spikes |
| `evw` | 14 | b2 d7 | event 2 missing; TYPE reinterpreted |
| `evw` | 15 | b0 d14 | two events missing; TYPE reinterpreted |

Every one reads `STATUS 0x06` with all counters zero and the `ERR` pin
low. The run is wrong and the part says nothing.

Mechanically, and this is what decides the protection:

**`dstate` bit 1 is the dangerous one.** `D_FETCH` is `2'b01` and
`D_ISSUE` is `2'b11`. One flip turns a dispatcher that is *waiting for a
queue answer* into one that is *issuing an event*, and both words are
legal, so nothing anywhere in the design can tell them apart. The FSM
then issues whatever `evw` holds — a stale word from the previous event.
Measured: a spurious event 7 in place of the real event 2.

**`dstate` bit 0 from `D_ISSUE` reaches `2'b10`**, which is illegal and
which the `default` arm already recovers to `D_IDLE`. Nothing hangs. The
event being issued is dropped on the way out, with no counter, no sticky
and no pin.

**The three `evw` records are field corruption.** Bit 0 is the ID field:
the spike goes to the wrong axon and the run diverges from the golden
model in both the event stream and the retained neuron state. Bits 14
and 15 are the TYPE field: a SPIKE becomes a TICK or a reserved code and
is silently reinterpreted or silently dropped.

### 3.2 Why neither previous round applies

The dispatcher has been hardened twice. `docs/16` section 5.1 found a
deadlock in `D_FETCH` and bounded the wait. `pilot_top` section 8.1
found the bounded wait's own report pulse erasable in one direction and
fabricable in the other, and retired it in favour of a combinational
term, at minus two flip-flops.

Both of those are about an answer that **does not arrive**. A bounded
wait fires on absence. Here every answer arrives, on time, and is wrong,
so a wait has nothing to fire on — which is exactly why these five
records survived two rounds of hardening in this structure. The answer
had to be different in kind, and it is: a code over the state rather
than a timer on it.

### 3.3 The one-bit pigeonhole, checked at two bits

`pilot_top` section 8.2 proves that three replicas cannot be held apart
over one bit: there are exactly two storage functions, `x` and `~x`, and
whichever a third replica picks it is bit-for-bit identical to one of
the other two, so `opt_merge` hashes it away. That is why the valid
flags carry two rails and not three.

`dstate` is two bits. The bar does not carry over and had to be
re-derived. **It does not clear it**, and the derivation is short enough
to state in full.

A replica of a two-bit value is two flip-flops, each storing some
boolean function of the pair, and it is only a replica if the two
functions together determine the value — that is, if the map is a
bijection on the four states. Every coordinate function of a bijection
on two bits is **balanced** (two ones out of four), and there are
exactly six balanced functions of two variables:

```
d0,  ~d0,  d1,  ~d1,  d0^d1,  ~(d0^d1)
```

Replica A takes `d1` and `d0`. Replica B, on the POL transform of
`pilot_cfg_bank`, takes `~d1` and `~d0`. Four of the six are spent. The
two that remain are **complements of each other**, so a replica built
from both stores one bit of information twice and determines nothing.
There is no third replica.

The MIX layer that rescued the 55-bit configuration domain does not
help, and the same counting says why: over `W` bits the affine
transforms give `2 * (2^W - 1)` coordinate functions — **2** at `W = 1`,
**6** at `W = 2`, **14** at `W = 3`. Three replicas need six distinct
ones. **Three bits is the first width at which a third replica has
functions left to take**, which is the general statement section 8.2
should have made and which this document now carries.

So: correction is unavailable for `dstate` at any price this design
would pay. Detection is what is left.

---

## 4. Item 2: what was built, and what it costs

### 4.1 Two check bits

`u_disp_chk`, one `pilot_chk_bank` instance, two flip-flops:

**`dstate_par = ^dstate`.** Storing the parity of a 2-bit state beside
it makes `{dstate, dstate_par}` a three-bit code with three legal words
— `000` for `D_IDLE`, `011` for `D_FETCH`, `110` for `D_ISSUE` —
pairwise at Hamming distance 2. Every single-bit upset in the state or
in the check bit lands on one of the five illegal words and is detected,
**including the `D_FETCH` → `D_ISSUE` flip that the 2-bit encoding
cannot see at all**. This is the encoding `hw/rtl/lif_core.v` gives its
own FSM, which the campaign credits with 12 of 12 DETECTED, reached here
by adding a check bit rather than by re-encoding: the same +1 flip-flop,
and `dstate`'s three literals and every case arm stay as they were.

**`evw_par = ^{evw[15:14], evw[9:0]}`**, the parity of the twelve bits
the dispatcher acts on. `evw[13:10]` is deliberately outside the check:
nothing reads those bits — they sit in `pilot_top`'s `_unused` sink — an
upset in them is MASKED today, and covering them would convert a
harmless upset into a reported fault. A check field must not manufacture
alarms for state that does not matter. `test_pilot_top.py` holds that
line with a directed test, so widening the parity to all sixteen bits
fails rather than passes quietly.

The `evw` check is qualified with `dstate == D_ISSUE` for the same
reason: outside `D_ISSUE` the word is about to be overwritten by the
next capture, an upset in it costs nothing, and the campaign records
several such injections as MASKED.

### 4.2 Two traps, both walked into first and then measured

**The enable.** The first version of this change gave both check bits a
plain next value. That is correct for `dstate`, which is rewritten from
`dstate_n` on every edge, and **wrong for `evw`**, which holds its word
for the whole of `D_ISSUE`: a next-value check bit is recomputed from
the held word every edge, so an upset landing *in* the held word is
recomputed into the check bit one cycle later and the two agree on the
corrupted event from then on. The check would only ever have caught an
upset in the single cycle it arrived. `evw_par` therefore takes an
**enable**, written only when the word is. `lif_core`'s rail takes an
enable for a different reason (X-freedom); this is the second reason a
check bit ever needs one, and `test_pilot_top.py` holds it by waiting
six cycles between the deposit and the check.

**The recovery.** The first version *assigned* `D_IDLE` on a failed
check. Taking the **`D_IDLE` arm** instead — which captures a read
answer that arrived in the same cycle and re-arms the fetch — is worth
two campaign records, and it is the same distinction `docs/16` section
5.8 records for the bounded wait under the name `fire_spurious`, which
`test_04` already asserts: a spurious recovery must cost the report and
nothing else. Measured, the assigning version turned two upsets the
design used to absorb harmlessly into announced event losses; taking the
arm returns both to "announced, nothing lost", and turns one of the five
former SDC records into a run with **correct output**.

On a failed check the combinational issue is suppressed in the same
cycle — `lif_ev_valid`, `lif_tick_valid` and `ev_dropped_oor` all read
low — because `dstate` may read `D_ISSUE` while being untrustworthy and
the issue is combinational from it, so a next-cycle-only recovery would
deliver the bad event before recovering from it. `sticky_errcfg` latches
from the same wire on the same edge, which is section 8.1's rule applied
without amendment: there is no cycle in which the report exists as
separate state for a second upset to erase or fabricate.

### 4.3 The flip-flop budget

Mapped flip-flops, ASIC recipe, `hw/rtl` at `634ca3e` against `hw/rtl`
with both items [fact]:

| | yosys ASIC census | **shipped netlist** |
|---|---:|---:|
| `634ca3e` (`docs/29`'s figure, reproduced) | 1,285 | 1,285 |
| **both items** | **1,296** | **1,296** |
| move | **+11** | **+11** |

Two independent routes agreeing exactly: this file's model of LibreLane
synthesis, and the final netlist of the runs section 6 reports, counted
by cell type. `u_disp_chk` holds 2 flip-flops in both.

Attributed:

| structure | flip-flops | item |
|---|---:|---|
| `cnt_evqp`, the `CNT_EVQ_PAR` counter | 8 | 1 |
| `evq_par_q`, the discard edge register | 1 | 1 |
| `u_disp_chk.bits`, the dispatcher check field | **2** | 2 |

**Item 2 is +2 flip-flops for 5 silent-corruption records**, which is
2.5 records per flip-flop — the best ratio of any hardening wave in this
project. For comparison, `oh_valid`'s two rails were +1 for 2 records,
the queue entry parity +8 for 7, and the configuration TMR +110 for a
domain the campaign has never recorded an SDC in.

Item 1 is 9 flip-flops for no record at all, and that is the correct
reading of it: it buys a *distinction* in the telemetry, not a class
change, and the argument for spending 9 flip-flops on it is `2d59ec2`'s
rather than the campaign's.

---

## 5. The campaign

Seed `0x16F12026`, 8 x 8, `EVQ_*_DEPTH = 4`, 378 injections, 461 s wall
[fact]. Diffed record by record against the 374 of `634ca3e` by
`(group, target, bit, burst, delay)`.

### 5.1 The whole delta

**364 records are field-for-field identical. Exactly 10 moved, and every
one of them is in `dispatch`.** Nothing in `lif_*`, `cfg_tmr_*`,
`evq_ptr`, `evq_mem`, `evq_par`, `evq_hold`, `regbank_*`, `ecc_*` or
`wdog_*` changed class or output [fact]. Four records are new: the
`disp_chk` group.

| group | `634ca3e` | this change |
|---|---|---|
| `dispatch` | 9 / 0 / 4 / **5** / 0 | **4 / 0 / 14 / 0 / 0** |
| `disp_chk` (new) | — | **2 / 0 / 2 / 0 / 0** |
| `evq_mem` | 25 / 0 / 7 / 0 / 0 | 25 / 0 / 7 / 0 / 0 |
| `evq_par` | 6 / 0 / 2 / 0 / 0 | 6 / 0 / 2 / 0 / 0 |
| TOTAL | 100 / 193 / 70 / **11** / 0 | 97 / 193 / 82 / **6** / 0 |

**The residual is 6 across three structures** — `lif_scan` 3,
`evq_hold` 2, `regbank_cfg` 1 — from 11 across four. `dispatch` joins
`evq_mem` as closed, and the pilot's whole event path, from the queue
storage through the pointers, the valid flags, the show-ahead adapter
and now the dispatcher, has no unprotected register left in it.

### 5.2 The ten records that moved

| target | bit | phase | before | after |
|---|---|---|---|---|
| `dstate` | 0 | b1 d7 | SDC, wrong | **DETECTED**, wrong |
| `dstate` | 1 | b2 d0 | SDC, wrong | **DETECTED, output correct** |
| `evw` | 0 | b1 d8 | SDC, wrong | **DETECTED**, wrong |
| `evw` | 14 | b2 d7 | SDC, wrong | **DETECTED**, wrong |
| `evw` | 15 | b0 d14 | SDC, wrong | **DETECTED**, wrong |
| `dstate` | 0 | b0 d0 | MASKED, correct | DETECTED, **correct** |
| `dstate` | 1 | b0 d0 | MASKED, correct | DETECTED, **correct** |
| `dstate` | 1 | b1 d11 | MASKED, correct | DETECTED, **correct** |
| `dstate` | 1 | b1 d14 | MASKED, correct | DETECTED, **correct** |
| `evw` | 2 | b2 d17 | MASKED, correct | DETECTED, **wrong** |

All ten `dstate` injections are now DETECTED, which is the same 100 %
the HD-2 encoding buys `lif_core`'s FSM, reached by the same mechanism.

**The claim stays narrow, as `docs/29` insisted.** Four of the five
former SDC records are still **lost events**. The check detects and does
not correct — section 3.2 proves correction is not on offer — and what
changed is that the pilot announces the loss instead of handing a
consumer a spike that was never sent. One of the five is genuinely
recovered, and that is the `D_IDLE`-arm recovery of section 4.2, not the
check bit.

### 5.3 The cost, stated

Five records that used to be MASKED are now DETECTED. Four of them keep
a **correct output**: the upset is announced and nothing is lost, which
is a false alarm and no more. **One is a real cost**: `evw` bit 2 at
burst 2 delay 17 used to be absorbed and now loses an event, announced.
The corrupted ID reached `D_ISSUE`, the check caught it, and the event
was dropped rather than delivered to an axon the sender did not choose.
That is the trade this kind of protection makes and there is no version
of it that does not: a check field that drops on failure will sometimes
drop a word whose corruption would have been harmless.

**Net across the group: 5 silent wrong runs become 4 announced wrong
runs and 1 correct run; 1 correct run becomes an announced wrong run; 4
correct runs become announced correct runs.** The SDC class, which is
the one this project treats as the class that matters, goes to zero.

### 5.4 The new state was measured, not argued

The hardening adds two unprotected flip-flops, so `target_list` gains
item 16, `disp_chk`, four deposits into `u_disp_chk.bits` — the bank's
own storage, not the checked wire, which is the mis-targeting that cost
the pointer group a day of wrong numbers. **2 MASKED, 2 DETECTED, 0
SDC**, and both DETECTED records have **correct output** [fact]. Bit 0's
upsets are announced false recoveries that cost nothing, because a
next-value check bit is rewritten correct on the same edge that reports
it. Bit 1's are MASKED at these phases. Adding unprotected state here
imports no silent risk, which is the question item 16 exists to ask.

`test_05_summary` gains two criteria: `disp_chk` must show no SDC, and
`dispatch` must show no SDC. Both are written as "no SDC" rather than
"all DETECTED" for the reason the queue criteria are — an upset the
workload never reaches is legitimately MASKED.

### 5.5 The directed watchdog cases had to be rewritten, and that is a
result

`test_04` planted the `D_FETCH` deadlock with one deposit: `xor dstate
bit 0` from `D_IDLE`. **After this change that construction does not
produce a deadlock**, and the test found it before this document did —
every script logged `until fetch_expire == 1: MISSED`. A single flip of
`dstate` is now an illegal check word, `disp_chk_bad` fires
combinationally in that cycle, and the FSM is back in `D_IDLE` on the
next edge with `STATUS.ERR_CFG` latched. **The 63-cycle wait never
starts.**

That is worth saying carefully, because it is easy to over-claim. **The
bounded wait is not redundant.** It still covers the route the check
field cannot see: a read that was *legitimately requested* and never
answered, which is where an EVQ_IN pointer upset or a parity discard
leaves the FSM, with `dstate` and its check bit in perfect agreement.
What is gone is the single-bit route into a **silent 63-cycle hang**; it
is now a one-cycle recovery with a report.

The five `wdog_fetch_dir` cases now plant the state with two deposits in
the same cycle, `dstate` and its check bit together, keeping the pair
legal at `D_FETCH`. Two bits is not a single-event upset and the file
says so; these cases already use `force` on the wait counters, and their
question is whether the net still works when it matters, not how often
it matters. All five construct and pass, and `wdog_oh_dir` is untouched.

The same edit was needed in `test_pilot_top.py`'s
`test_dispatcher_stranded_in_fetch_recovers_and_is_flagged`, which
passed either way but would have stopped measuring the bounded wait. It
now asserts that the state it planted is a legal check word before it
starts, so a future edit cannot silently turn it back into a test of the
check field.

---

## 6. The timing budget

### 6.1 Method

`docs/29` section 4.1's method exactly: the config is read from
`hw/openlane/pilot_ihp/config.tr-best.json`, every `dir::` path expanded
to the absolute path it already resolved to, `TIME_DERATING_CONSTRAINT`
pinned to the float `5.0`, and the run placed outside the repository.
`SETUP_VIOLATION_CORNERS` is `["*"]`, so setup is gated on every corner
and not only on typical.

**The control is `docs/29`'s own `trbest_parity` run**, which is on disk
and which read `hw/rtl` directly at `634ca3e`. Its slow-corner setup
worst slack is `0.4305871336916171`, reproducing that document's
+0.4306 to sixteen digits [fact], so the control needed no re-run and
the only difference between the pair is the RTL.

Two variants were hardened, because the recovery changed between them
and the second is what ships:

| tag | RTL |
|---|---|
| `trbest_parity` | `634ca3e`, the control |
| `w8_v1_assign` | both items, recovery **assigns** `D_IDLE` |
| **`w8_disp_chk2`** | both items, recovery **takes the `D_IDLE` arm** |

One textual difference between `w8_disp_chk2`'s sources and the RTL as
committed: a redundant `begin`/`end` around the dispatcher's `case` was
removed and the body re-indented after the run. That is not asserted to
be harmless, it is **proved**: `yosys equiv_make / equiv_simple /
equiv_induct / equiv_status -assert` over the two `pilot_top`
elaborations returns clean [fact], so the netlist the numbers below come
from is the netlist this RTL produces.

### 6.2 The result

`OpenROAD.STAPostPNR`, post-PnR STA on extracted parasitics, 5 % OCV
derate, all figures in ns **[fact]**:

| Corner | Metric | control | `w8_v1_assign` | **`w8_disp_chk2`** |
|---|---|---:|---:|---:|
| `nom_slow_1p08V_125C` | **setup ws** | +0.4306 | +0.3096 | **+1.0423** |
| | hold ws | +0.5911 | +0.5944 | **+0.5946** |
| `nom_typ_1p20V_25C` | setup ws | +7.5844 | +7.4886 | **+7.9528** |
| | hold ws | +0.2783 | +0.2792 | **+0.2787** |
| `nom_fast_1p32V_m40C` | setup ws | +11.8164 | +11.7383 | **+11.9991** |
| | hold ws | +0.1029 | +0.1023 | **+0.0960** |
| all three | setup / hold violations | 0 / 0 | 0 / 0 | **0 / 0** |

Corroborated three ways for the shipping variant, not taken from the
worst-slack metric alone [fact]: `timing__setup__wns` and
`timing__setup__tns` are **0 at all three corners**, every corner's
`violator_list.rpt` is **empty**, and `Checker.SetupViolations` — which
`config.tr-best.json` points at `["*"]` rather than at typical — passed,
with `flow__errors__count = 0`, Magic DRC 0, KLayout DRC 0 and LVS 0.

**Timing does not bind.** The brief allowed for it doing so — the
dispatcher sits in `pilot_top`, not in the queues that had 9 to 12 ns to
spare — and the answer is measured rather than assumed.

### 6.3 What that +0.6117 ns is, and what it is not

The shipping variant reports **more** slow-corner margin than the
control. It would be dishonest to bank that as a speedup the change
earned, and the run says why:

**In both runs the design's worst path starts and ends inside
`u_pilot.u_lif`** — `_5618_` → `_5659_` in the control, `_5615_` →
`_5669_` in the variant [fact]. Neither item adds a single gate to
`lif_core`. `docs/29` measured the same structure in the opposite
direction: its 0.3686 ns loss also landed entirely on `lif_core`'s
critical path, to which *it* added no logic either, while both queues'
own paths got faster.

So the honest reading is: **the design's worst-corner slack is set by
`lif_core`'s critical path, and that path moves by several tenths of a
nanosecond under placement and routing changes that a hundred cells of
area elsewhere are enough to cause.** `w8_v1_assign` at +0.3096 and
`w8_disp_chk2` at +1.0423 differ by one multiplexer in the dispatcher
and 0.73 ns at the slow corner; no theory of logic depth explains that,
and placement does.

**What is attributable to this change** is the delay of what it added:
a 3-input XOR on the paths ending at `dstate` and at `lif_core`'s valid
inputs, and a 13-input XOR reduction, roughly four levels of XOR2, on
the `evw` check. Both terminate in `pilot_top` logic that is nowhere
near the critical path in either run, and neither appears in any
violator list at any corner [fact].

**The claim this section supports is therefore the narrow one: both
items close, with margin, at every corner, on a configuration that
applies a real derate and gates setup everywhere — and the design's
worst-corner Fmax is not decided by anything in this change.**
Slow-corner Fmax `1000 / (20 - ws)`: **51.10 → 52.72 MHz** against a
50 MHz target [estimate, arithmetic].

`docs/28`'s open item — which path lost the margin — remains open, and
this document narrows it in the same direction `docs/29` did: not this
one either. What both waves now show together is that the number is
`lif_core`'s to explain.

---

## 7. The netlist evidence, and the merge trap in its fourth form

### 7.1 Why this structure needs its own guard

The hazard is **not** `opt_merge`. That is the pointer replicas' and the
valid flags' problem, and it is why those modules carry a POL or MIX
storage transform and `pilot_chk_bank` does not — a check bit has no
twin to be hashed against.

The hazard is the one `lif_core`'s `wchk` and `smem` carry and
`aer_par_bank` carries after them: **a check bit is a pure function of
the register it covers in every reachable state**, so a tool able to
reason across sequential state could delete the storage, rebuild the bit
from the parity tree, and leave a checker that reports every state
legal. That is protection which passes every simulation in this
repository and detects nothing in silicon. Nothing in yosys does that
today; this guard is what says so tomorrow.

`u_disp_chk` is a module instance and not a `reg [1:0]` for the reason
`aer_par_bank` is: under `SYNTH_HIERARCHY_MODE = deferred_flatten`, abc
renumbers every cell to `_NNNN_` before the flatten, so an instance path
is the only naming that reaches the shipped netlist.

### 7.2 The guards

`sw/tests/test_synthesis_guards.py` gains four:

| test | flow | asks |
|---|---|---|
| `..._is_stored_in_the_asic_flow` | yosys/LibreLane-shaped | 2 flip-flops under `u_disp_chk.` |
| `..._is_stored_in_the_ecp5_flow` | `synth_ecp5` | the same |
| `..._survives_a_flow_that_ignores_keep_hierarchy` | `synth_ecp5`, attribute stripped | 1 each under `u_pilot.dstate_par` / `u_pilot.evw_par` |
| `..._survives_the_real_hardening_flow` | the shipped netlist | 2 flip-flops under `u_disp_chk.` |

The third is the only test in the file that has to ask by **net name**
rather than by instance, and the reason is measured: `pilot_chk_bank`'s
`q` is a plain alias of its storage, so once `keep_hierarchy` is gone
yosys resolves each flip-flop's Q to the parent's net and the instance
path stops existing — 0 under the instance, 1 each under the two names,
with the design's total flip-flop count unchanged at 1,296 [fact].
`aer_par_bank` keeps its path in the same run because its storage is
wider than any one output alias. That is a naming artifact and not a
missing register, and counting the instance there would fail on the
artifact — the mirror image of the trap
`test_lif_memory_survives_the_ecp5_flow` documents.

`HARDENED_REGISTERS` also gains `u_pilot.cnt_evqp` and, closing a gap
this change found on the way past, `u_pilot.cnt_evqo`, which has been in
the design since the wave before and was never listed.

### 7.3 The provenance rule, in its current form

The shipped-netlist guard uses `_witness_runs("pilot_chk_bank", RTL /
"pilot_top.v")` — the rule as rewritten in wave 7, which reads the run's
own **elaborated-module header** (`*-yosys-jsonheader/*.h.json`) rather
than the run's modification time. That rewrite happened because
`hw/openlane/pilot_ihp/runs/tr-control` postdates the edit that
introduced `aer_par_bank`, was hardened from a tree that did not contain
it, and was accepted as a witness — reporting a missing check field as a
collapse.

The guard **SKIPs** when no run on disk was built from RTL declaring
`pilot_chk_bank`, and the skip is on what the run was *built from*,
never on the absence of the storage, because a netlist-shaped skip
condition skips on precisely the symptom. Verified both ways [fact]:
with no witness on disk it skips with that message; with the
`w8_disp_chk2` run added through `NSSOC_RUN_TREES` all five
shipped-netlist guards run and pass — the configuration TMR, the
pointer banks, the entry parity, the eight valid-flag rails and the
dispatcher check field — against the netlist that would have been
fabricated.

### 7.4 Mutation-checked, twice

**Mutation A — the storage removed.** `u_disp_chk` deleted and the two
check bits recomputed combinationally from the registers they cover,
which is exactly what a sequential-equivalence optimisation would leave
behind. Result [fact]: **the three model guards fail and the other 30
tests in the file pass**, mapped flip-flops 1,296 → 1,294. Four tests in
`test_pilot_top.py` also fail, because in RTL this mutation destroys the
detector as well as the storage — so this mutation is caught in both
layers and is not a clean test of the netlist guard alone.

**Mutation B — the attributes removed, the RTL functionally
identical.** `(* keep_hierarchy *)` and `(* keep *)` stripped from
`pilot_chk_bank` and nothing else. Every simulation in the repository
still passes, mapped flip-flops are still 1,296 — the storage is
genuinely there — and **exactly the two instance-path guards fail**
[fact]. The net-name guard correctly passes, because it is asking
whether the storage exists and the answer is yes.

The pair is what makes the guard set meaningful: A says the tests notice
when the storage goes, B says they notice when the structure stops being
countable while the storage stays, and the two failures are disjoint in
the right way.

---

## 8. What must change in other documents and files

This change owns `hw/rtl/pilot_top.v`, `hw/tb/test_pilot_top.py`,
`hw/tb/test_fi_campaign.py`, `hw/tb/fi_campaign_results.json`,
`sw/tests/test_synthesis_guards.py` and this document. Everything below
is outside that set and is recorded rather than done, on the convention
`docs/27` and `docs/29` used.

**1. `docs/00-index.md` must gain a row for this document — and until it
does, `sw/tests/test_doc_links.py` FAILS.** That test discovers the
corpus rather than listing it, so a new document is in scope the moment
it exists. This is the same known one-line debt `docs/29` recorded, and
it is the only test in the repository this change leaves red. The row:

> `docs/30-dispatcher-protection.md` | The AER queue's parity discards
> reach `CNT_EVQ_PAR`, and the event dispatcher's state and event word
> get a two-bit check field. Closes the `dispatch` silent-corruption
> group at +2 flip-flops and leaves the residual at 6 records across
> three structures.

**2. `docs/29` section 8 item 5 and section 9 item 2 are now DONE and
should say so**, in the form sections 5.10 and 5.11 of `docs/16` use for
the items they closed: the counter is built, at `0x0B0` on `FAULT_CLR`
bit 7, one instance for both queues, and section 2.1 above records what
the `evq_par` group's classification does with it, which is nothing —
the value is the attribution.

**3. `docs/16` section 6.2's residual list and `docs/29` section 5's
"11 across four structures" both have a successor.** It is **6 across
three** — `lif_scan` 3, `evq_hold` 2, `regbank_cfg` 1 — and `dispatch`
is closed. `docs/16` section 5.1's account of the `D_FETCH` deadlock
also needs the qualification of section 5.5 above: the single-bit route
into that hang no longer exists, and the bounded wait now covers only
the requested-but-unanswered read.

**4. `docs/21-pilot-datasheet.md` must gain `CNT_EVQ_PAR` at `0x0B0`**
and update the portable `FAULT_CLR` clear-everything write from `0x7F`
to `0xFF`.

**5. `docs/29` section 9 item 7 — measure SECDED (22,16) on the queue —
is unaffected and still open.** Nothing here touches the queue's read
path or its margin.

**6. `hw/openlane/pilot_ihp/config.tr-best.json` does not carry
`TIME_DERATING_CONSTRAINT`**, so a run from it as committed is
un-derated while `config.json` beside it is not. `docs/29`'s `trbest_*`
pair and this document's runs both pin the float `5.0` in a copy. The
committed config should carry it, and `hw/openlane/` is outside this
change's ownership.

**7. `hw/tb/Makefile.gl` and `hw/tb/Makefile.glfi` still default to the
`shape-6x2` netlist**, which `docs/27` superseded and which `docs/29`
and now this change supersede again. `docs/29` section 9 item 6 already
records it; it is still true.

---

## 9. What is left, and whether it is worth doing

The residual is **6 records across three structures**, and every one of
them is in a file this change does not own:

| structure | records | where |
|---|---:|---|
| `lif_scan` | 3 of 24 | `u_lif.jj`, `u_lif.ev_axon_r` — `hw/rtl/lif_core.v` |
| `evq_hold` | 2 of 18 | `oh_data`, the show-ahead data register |
| `regbank_cfg` | 1 of 16 | `ctrl_en` |

**This is a flat tail and the next wave should be argued for, not
assumed.** `lif_scan`'s three are the neuron-scan loop counter and the
latched axon id, both one-cycle-live working registers inside the
datapath; protecting them means a code over a value that changes every
cycle, which is a different and more expensive construction than any
used so far. `evq_hold`'s two are `oh_data`, 16 bits of held event word
— the same shape as `evw`, so the same +1 check bit would close them, in
a structure this change does not own. `regbank_cfg`'s one is `ctrl_en`,
a single configuration bit that is already inside no code and would need
a rail pair.

The cheapest of the three by benefit-per-flip-flop is `oh_data`: +1
flip-flop for 2 records, on the construction this document has now built
and measured once. It is a one-line reuse of `pilot_chk_bank` and it is
the item this document would recommend next — with the caveat that
`oh_data` is *held* like `evw`, so it needs the enable of section 4.2
and not a next value.

`ctrl_en` and `lif_scan` are where the honest answer is probably "stop".
One record in 16 and three in 24 are rates a flight part reports rather
than removes, and the mechanisms that would remove them cost more per
record than anything this project has yet accepted.
