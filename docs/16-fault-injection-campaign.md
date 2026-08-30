# Fault-injection campaign: the pilot's measured upset response

The pilot exists to demonstrate that single-event upsets in a
neuromorphic node are caught. Until now that was a set of directed
demonstrators — one FSM upset, one TMR replica, one corrected weight
word — each of which shows that a mechanism *works*, and none of which
says how much of the design those mechanisms actually cover. This
document is the measurement. It reports what happens to
`hw/rtl/pilot_top.v` when one bit of one architectural flip-flop is
flipped, per structure, against the golden model as the only judge of
right and wrong.

Convention, as everywhere in this repository: **[fact]** = measured in
this environment or read out of an installed file; **[estimate]** =
derived or judged. Sections 2 to 6 are measured unless a sentence is
marked otherwise. Section 7 is where this campaign is weak, stated
plainly, and it should be read before section 6 is quoted anywhere.

| | |
|---|---|
| Campaign source | `hw/tb/test_fi_campaign.py` |
| Harness | `hw/tb/Makefile.fi` (`cd hw/tb && make -f Makefile.fi`) |
| Per-injection log | `hw/tb/fi_campaign_results.json` |
| Device under test | `hw/rtl/pilot_top.v`, 8 x 8 neurons/axons, EVQ depth 4 |
| Oracle | `sw/golden/lif_core.py` (`LIFCore`, `LIFConfig`) |
| Seed | `0x16F12026` |
| Injections | 255 to 2026-08-26; 287 from 2026-08-27; 335 from 2026-08-29; 365 from 2026-08-30 (section 2) |
| Simulated time | 22.23 ms at 255 injections; 28.77 ms at 335; 31.31 ms at 365 |
| Wall time | 79.5 s to 84.5 s idle before the memory hardening; 674 s for the same 255 injections after it; 892 s for 335 injections on a loaded machine; 567 s for 365 on a quiet one — and 1769 s for an identical 365-injection run alongside three other simulator jobs (Icarus, single-threaded; section 8) |

### Five runs, kept side by side

This document reports the campaign **five times**, and the runs are
kept side by side rather than one overwriting the other. That is the
whole value of the document: it shows what each change to the design did
to the measured upset response, which a single current number cannot.

- The **pre-fix** run is the measurement that found the deadlock of
  section 5.1. It is the evidence that motivated the change and it is
  reported here unaltered.
- The **post-fix** run is the same campaign — same seed, same target
  list, same workload, same 255 injections — against
  `hw/rtl/pilot_top.v` with the bounded `D_FETCH` wait of section 5.1
  in place.
- The **post-hardening** run of 2026-08-27 is the same campaign again,
  against `hw/rtl/lif_core.v` with the SECDED codes on `wmem`, `vmem`
  and `rmem` that the section 6 ranking asked for. It was run twice:
  once with the target list untouched, so the comparison with the 255
  above is exact; and once extended by 32 injections into the 80 check
  flip-flops the hardening itself added, because a protection whose own
  storage is unmeasured is a claim (section 3.2).
- The **post-wave-5** run of 2026-08-29. Three things changed under it:
  `hw/rtl/aer_fifo.v` triplicated the four AER queue pointers; the
  injector was **retargeted** onto the pointer replicas' storage,
  because the old targets had become voted wires and the group was
  reporting a number about a node nothing protects (section 3.3); and
  `hw/rtl/pilot_top.v` gained the bounded `oh_req` wait of section 5.7,
  for a deadlock this run found. It is 335 injections: the 24 pointer
  records are replaced by 72, and the other 263 are unchanged targets.
- The **safety-net** run of 2026-08-30 is the current one, and it is
  the only one of the five in which **no RTL changed at all**. What
  changed is the instrument: the two bounded-wait counters that convert
  a silent hang into a host-visible fault — added after this campaign
  found the two deadlocks, and never injected into — are in the target
  list, with 18 random-phase injections and 12 directed ones (section
  5.8). It is 365 injections and all 335 of the previous run are
  unchanged, record for record.

Every number in this document is labelled with which run it comes from.
Where a section is not labelled the runs agree.

`hw/tb/fi_campaign_results.json` holds the **365-injection safety-net**
log, because that is the design that exists. Exactly five of the 255
records differ between the pre-fix and post-fix runs and section 5.1
lists all five; exactly 43 differ between the post-fix and
post-hardening runs and section 3.2 accounts for every one; between the
post-hardening run and the wave-5 one **exactly one common record
changed class** — `evq_hold` / `oh_req`, HANG to DETECTED — with the 24
pointer records retired and 72 new ones taking their place (section
3.4); and between the wave-5 run and this one **not one of the 335
common records changed anything at all**, because the RTL did not move
and the 30 new records draw from the second seeded stream (section
3.5).

**Headline, pre-fix [fact].** 255 single-bit injections: **83 MASKED
(32.5%), 42 CORRECTED (16.5%), 34 DETECTED (13.3%), 91 SDC (35.7%),
5 HANG (2.0%)**.

**Headline, post-fix [fact].** The same 255 injections: **83 MASKED
(32.5%), 42 CORRECTED (16.5%), 39 DETECTED (15.3%), 91 SDC (35.7%),
0 HANG**. All five HANG outcomes became DETECTED and nothing else moved
— not one MASKED, CORRECTED or SDC record changed class, and the SDC
rate is unchanged at 35.7%. The fix removes the failure class it was
written for and buys nothing else, which is what it should do.

**Headline, post-hardening [fact].** The same 255 injections again:
**126 MASKED (49.4%), 42 CORRECTED (16.5%), 39 DETECTED (15.3%),
48 SDC (18.8%), 0 HANG**. Silent corruption falls from 91 to 48, and
**every one of the 43 records that moved went from SDC to MASKED, in the
three structures that were hardened and in no others** — `lif_wmem` 9,
`lif_vmem` 22, `lif_rmem` 12. Not one record moved in the other
direction, and no record outside those three groups changed at all.

**Headline, post-wave-5 [fact].** 335 injections, 2026-08-29: **79
MASKED (23.6%), 193 CORRECTED (57.6%), 37 DETECTED (11.0%), 26 SDC
(7.8%), 0 HANG**. The AER pointer group goes from 22 SDC and 1 HANG of
24 to **0 SDC of 72**, every one of the 72 corrected and counted; the
show-ahead adapter's one HANG becomes DETECTED under the bounded wait of
section 5.7. Of the 263 targets this run shares with the previous one,
**exactly one record changed class** and it is that HANG.

**Headline, safety-net [fact].** 365 injections, 2026-08-30, against
byte-identical RTL: **91 MASKED (24.9%), 193 CORRECTED (52.9%), 53
DETECTED (14.5%), 28 SDC (7.7%), 0 HANG**. The 7.8% → 7.7% is
arithmetic on a larger denominator and says nothing. What this run says
is in section 5.8, and it is the first headline in this document that
is not an improvement:

> **The two bounded-wait counters are partially robust. The wait itself
> cannot be broken by an upset — 12 of 12 counter injections MASKED,
> and the reason is structural rather than statistical. The one-cycle
> pulse each of them reports through can be. An upset that sets it
> fabricates a fault the host cannot distinguish from a real one (6 of
> 6). An upset that clears it in the single cycle it is high erases the
> report entirely: the design deadlocks, recovers, returns a wrong
> answer, and reads `STATUS` = `0x06` with every counter at zero and
> every fault pin low. Two SDC records, each with a paired control that
> classifies DETECTED — same fault, same cycle, byte-identical wrong
> output, one deposit apart.** The structure that closes the
> silent-hang failure class is itself a silent-failure path, and the
> fix costs −2 flip-flops.

**Read the four headline denominators before comparing any two of
them**, because they are not the same experiment: 255, 287, 335 and 365
injections. The 32 added on 2026-08-27 are the memory hardening's own
check-field flip-flops, which did not exist before it; the 48 net added
on 2026-08-29 are the pointer TMR's replicas, likewise; and the 30
added on 2026-08-30 are two structures that existed all along and had
never been injected into. **The only defensible before/after figure for
the memory hardening is 35.7% → 18.8% SDC on the identical 255
injections** (section 3.2). Pairing 35.7% with 16.7% — or now with 7.7%
— divides by a denominator the earlier run did not have, and sections
3.4 and 3.5 give the like-for-like arithmetic for the pointer TMR and
for this run the same way. The 2026-08-30 run has the cleanest such
statement of the four, because **no RTL changed under it at all**: all
335 previous records are identical and the 30 new ones are the whole
difference.

In all five runs every hardened structure kept its promise with zero
counterexamples — the neuron-core FSM (12/12 detected), the
configuration TMR domain (15/15 corrected and counted, but read the
correction of 2026-08-26 in section 4 before quoting that number: the
replicas it votes on did not exist as three registers in the netlist
until that date), the SECDED weight word (12/12 singles corrected, 4/4
doubles detected, E10 substitution exact on every event stream it
produced), and now the AER pointer TMR (72/72 corrected and counted —
and read section 3.3 before quoting *that* number, because the day
before, the same group reported 23 SDC against the same working
hardware). Every silent corruption still comes from a structure the
pilot does not claim to protect. What changed is which structures those
are: before the memory hardening the residual was dominated by the
neuron core's memories; after it the AER event path dominated; and after
the pointer TMR the residual is 26 records of which **19 are in the AER
event path that is still unprotected** — queue storage 7, the
show-ahead adapter 6, the dispatcher 6 — with the neuron scan at 6 and
the register bank at 1. The pointers have left that list entirely.
**Two more records joined it on 2026-08-30 and they are of a different
kind**: they are not in a structure the pilot never claimed to protect,
they are in a structure it added *in order to* protect itself, and they
are there because the report is one flip-flop wide (section 5.8). That
is why the residual is now 28 and why the wave-6 ranking in section 6.2
puts a −2 flip-flop item above all five of the structures it ranks.

**The result that is not a number.** The corrections *were* invisible.
Until 2026-08-27 the memory hardening's four telemetry outputs were left
unconnected in `hw/rtl/pilot_top.v`, so a corrected upset moved no
counter and lit no pin, and this campaign — which is only allowed to
observe what a bench observes — had to classify it MASKED rather than
CORRECTED. That is why the MASKED column absorbed all 43 records instead
of the CORRECTED column taking them. The wiring was then done and the
same injections classify CORRECTED; the pointer TMR was wired to
`CNT_TMR` from the start, which is why its 72 corrections are visible.
Section 4.1 carries both numbers and what the gap cost.

---

## 1. Method

### 1.1 What was adapted, and what was not

The method comes from the sibling programme's campaign
(`/home/hasanmelih/Documents/radhard-edge-ai`, its
`radhard-edge-ai/docs/27`, its `hw/tb/test_fi_campaign.py`, and the
harness lessons in its `radhard-edge-ai/docs/25` section 3). The
repository prefix is not decoration. This corpus now has a `docs/25` of
its own, and `scripts/build_docs.py` turns a bare `docs/NN` into a local
hyperlink, so an unqualified sibling citation would quietly send a
reader to the wrong document — which is exactly what happened to the
`docs/25` reference on this line. Four things were taken directly:

1. **The SEU model**: XOR one bit into a named architectural flip-flop,
   with the deposit landing 3 ns after a clock edge. An on-edge deposit
   is overwritten by that same edge's non-blocking update before
   anything samples it, so it silently does nothing. That lesson cost
   the sibling project a debugging session and is reproduced here rather
   than rediscovered.
2. **Sampling `busy` one nanosecond past the edge**, not at the
   `RisingEdge` callback, where it still reads its pre-update value and
   shifts the whole injection window one cycle late.
3. **A curated target list, not a hierarchy scrape.** Every entry is a
   named register, so the resulting map reads directly as a hardening
   priority list and the injection count is a constant rather than a
   function of how the elaborator names things.
4. **Sentinel scrubbing**, so a corrupted read cannot alias a correct
   value. Section 1.5.

Its **conclusions** were not taken. That design is a requantising INT8
MAC row behind an AXI port; its headline finding is that wide
accumulation registers dominate fault magnitude, with small routing
state carrying the highest per-bit rate. This design has no accumulator
and no requantiser. Whether the "small routing state dominates" half
carries over was treated as a question to answer, not a result to
reuse — and section 6 shows it carries over in a different place than
the analogy would have predicted.

### 1.2 Device, harness and observation rule

The DUT is `pilot_top` itself, not the Tiny Tapeout wrapper that
`Makefile.pilot` drives. The wrapper adds a pin map and a reset
synchronizer and nothing a fault can hide in, and driving `pilot_top`
directly makes every hierarchical target path the path the RTL itself
uses, so the target list is checkable by eye against the source.
`Makefile.fi` gives the campaign its own `sim_build_fi_<geometry>/` and
`results_fi_<geometry>.xml` so it never shares a build with the
functional suites, nor one geometry's build with another's (section 8).

**Only the stimulus reaches into the hierarchy.** Every observation is
one a bench with an SPI master and a logic analyser could make: the
serial register port and the five status pins. That is the same rule
`test_pilot_top.py`'s FSM-upset test already states — there is no pin
that injects an upset, and a demonstrator that cannot be provoked in
simulation is a claim rather than a result.

Two deliberate consequences:

- Output events are drained through the serial `EVQ_OUT` register, which
  returns the full 16-bit event word plus VALID, rather than through the
  four-bit `AER_OUT_ID` nibble on the pins. A corrupted TYPE field
  therefore cannot hide.
- Input events are pushed through the parallel AER pins, not the serial
  port. A serial frame is 170 clock cycles long and would smear a
  one-cycle injection across the whole run; a pin strobe places the
  event a known six cycles from a known edge.

### 1.3 Per-injection procedure

1. **Hardware reset.** Costs no serial frames and clears everything on
   the reset net: every configuration register, every counter, every
   sticky bit, the three TMR replicas, both queue pointer pairs and
   `lif_core`'s control state.
2. **Sentinel fill** of both `aer_fifo` storage arrays (section 1.5).
   These are the only arrays no reset and no bring-up writes.
3. **Bring-up over the serial port**: `STATE_CLR`, the seven
   configuration registers, the four ECC-checked weight words, `CTRL.EN`.
   This rewrites `lif_core`'s `vmem`, `rmem` and `wmem`, which docs/10
   section 3 deliberately keeps off the reset net. Every injection
   therefore starts from an identical, fully defined machine.
4. **The stimulus**, eight AER commands in three bursts (section 1.4).
5. **The deposit**: one bit of one flip-flop, XORed at a seeded-random
   cycle inside a measured busy window.
6. **Drain and read back**: STATUS, the five counters, the four fault
   pins, then the whole neuron state file through `N_ADDR` / `N_DATA`.
   If the run did not complete, `CTRL.SOFT_RST` is issued first — it is
   the documented recovery, it un-parks a core holding BUSY high so that
   the configuration-locked `N_ADDR` becomes writable again, and it
   preserves both the counters (hardware reset net) and the neuron state
   file (not on the block reset net either).

Every loop in the harness is bounded. A hang costs a timeout, never the
suite: `wait_idle` polls the BUSY pin for at most 2000 cycles, `drain`
issues at most 24 reads per burst, and each cocotb test additionally
carries a wall-clock `timeout_time`.

### 1.4 Workload

Chosen against the golden model under five constraints, every one of
them asserted in `test_00_control` rather than assumed:

- the run must emit spikes in **all three bursts**, so a fault has
  something to corrupt before, during and after the injection window;
- no burst may emit more than the five-entry output path holds, so the
  clean run never backpressures and BUSY means "working", not "stalled";
- the golden final V must be **distinct and nonzero for every neuron**
  (section 1.5);
- at least one neuron must end refractory, or `rmem` is untested;
- several distinct neurons must spike, or the event stream is a weak
  oracle.

The result [fact]:

```
weights   seeded random, 8 x 8, seed 10
config    THETA 16, V_RESET -4, S_LEAK 3, S_SYN 2, T_REFR 2, leak on
bursts    [SPIKE 0, SPIKE 1, TICK] [SPIKE 2, SPIKE 3] [TICK, SPIKE 1, TICK]
golden    events [1, 2, 5, 6, 4, 2]
          final state [(-32,0) (-27,0) (-3,1) (-10,0) (-2,0) (-5,0) (9,0) (-13,0)]
busy      28 / 19 / 28 clock cycles per burst (measured, asserted)
```

### 1.5 Sentinels

Two things could otherwise make a corrupted read look correct, and both
are closed:

- **Queue storage.** Both `aer_fifo` `mem` arrays are pre-filled with
  `0xF0F0`, an event word whose TYPE field is the reserved encoding
  `2'b11` that the dispatcher drops. A pointer upset that fetches an
  unwritten slot therefore yields something visibly non-golden. Without
  it the slot holds whatever it last held, which in a four-entry queue
  cycling through a repeating event pattern is frequently the *correct*
  word for that position — a pointer fault that re-reads a stale slot
  would then produce a golden-looking stream and be recorded as masked.
  The sentinel earned its place: one `u_evq_out.wr_ptr` injection put
  `0xF0F0` straight into the drained event stream, which is the queue
  presenting an unwritten slot as an event.
- **Neuron state.** The golden final V is distinct and nonzero for all
  eight neurons, so a fault that writes the right value to the wrong
  neuron, or that zeroes one, cannot pass the state comparison.

### 1.6 Classification

Exactly one class per injection, decided in this order:

| Class | Condition |
|---|---|
| HANG | the run did not complete inside its cycle budget **and** nothing was flagged |
| DETECTED | `STATUS.ERR_CFG`, `STATUS.DED_SEEN`, `STATUS.OVF_SEEN`, or a nonzero `CNT_DED` / `CNT_EVQ_OVF` / `CNT_AXON_OOR` |
| SDC | the output differs from the golden model and nothing was flagged |
| CORRECTED | the output matches the golden model **and** `CNT_SEC` or `CNT_TMR` moved |
| MASKED | the output matches the golden model and nothing moved |

**The golden model decides right from wrong, always.** The design's own
flags only decide whether a wrong answer was *announced*; they are never
allowed to declare an answer correct. That distinction is why every
record also carries `out_ok`, and why section 3 can report that 21 of
the 34 DETECTED outcomes also had a corrupted output — detected is
recoverable, not harmless.

The compared output is the whole observable result of the run: the
ordered event stream *and* the final neuron state file. State is in the
comparison because this design is stateful. An upset that leaves V wrong
but produces no wrong spike inside an eight-command run has not been
masked; it has been deferred. `spikes_ok` and `state_ok` are recorded
separately so the two can be told apart, and section 3 keeps them apart.

Three further per-record facts, because five classes cannot carry them:

- `telemetry_ok` — the counters read exactly what the *same bring-up*
  reads with no deposit. Outside the two telemetry groups a difference
  means the design correctly counted the event it was given; inside
  them it means the record itself was corrupted.
- `latent` — an architectural register still holds a corrupted value
  after a run the design otherwise handled cleanly.
- `e10_events_ok` — for double-bit weight-word injections, whether the
  degraded output is exactly the fail-operational zero substitution of
  docs/10 section 11.2 rather than garbage.

### 1.7 Reproducibility

One seed (`0x16F12026`) drives every randomised injection cycle;
targets, bits and phase counts are constants. **Verified [fact]:** four
pre-fix runs, two of them after unrelated edits to the harness, produced
identical logs — same total, same histogram, same per-group counts, and
the same 255 individual records including every drawn burst index, every
drawn delay and every read-back neuron state. Only `wall_seconds`
differed (84.5, 103.1, 183.9 and 83.5 s, tracking host load).

The post-fix run reproduces the same way [fact]: three 8 x 8 runs — one
before the harness changes of this revision, one after the weight seed
and the burst windows moved into the per-geometry `WORKLOAD` table, one
after the strengthened sentinel check of section 1.8 — produced
byte-identical logs apart from `wall_seconds` (79.5, 81.1 and 80.5 s).
That comparison is also what shows those harness changes did not
perturb the campaign of record: the table pins 8 x 8 to the same seed 10
and the same (28, 19, 28) windows, so the random draw consumes the same
numbers.

### 1.8 Harness honesty checks

`test_00_control` runs before any data point and fails the suite if any
of these is false [fact, all passing]:

- the workload satisfies all five constraints of section 1.4;
- an uninjected run reproduces the golden event stream and the golden
  neuron state file exactly, with no flag, no counter and no fault pin,
  and classifies MASKED;
- the sentinel carries the reserved TYPE encoding, does not alias a
  golden event word, and is actually *there*: every slot of both
  `aer_fifo` storage arrays is read back after a bring-up and must hold
  it, so the aliasing argument of section 1.5 is a checked property
  rather than an assumption about the fill;
- the ERR pin agrees with the STATUS bits it is derived from, so the
  campaign's zero-frame pin reads cross-check the register reads it
  classifies on;
- the busy windows the random draw is scaled to are no longer than the
  measured ones, so a drawn delay always lands on a working design;
- **the injection mechanism demonstrably reaches a target**: a deposit
  into `lif_core.state` must come back DETECTED. The FSM encoding is the
  one prediction the design states outright, so if this probe came back
  MASKED the deposit would not be landing and the whole campaign would
  be measuring nothing. The probe result is then discarded — it is a
  self-test, not a data point.

`test_05_summary` additionally fails if the campaign shrinks below 200
injections, if any FSM injection is not DETECTED, if any single
configuration-TMR replica upset is SDC, if any single-bit weight-word
upset is not CORRECTED, if any double-bit weight-word upset is not
DETECTED, or if any single-bit upset in a coded memory file is SDC.

**Added 2026-08-30, with the safety-net groups.** Two more criteria,
and the shape of them is the point. The first is a *presence* check:
all four `wdog_*` groups must be in the log, because the way these
structures came to be unmeasured was not a decision but an omission,
and an omission that fails a test cannot repeat. The second is the one
behavioural promise a bounded wait makes — **no `wdog_*` injection may
classify HANG** — which holds even in the two cases where the report is
erased, because the recovery survives the upset and only the
announcement does not. There is deliberately no criterion asserting
that a timeout is reported: the measurement found a case where it is
not (section 5.8), and a criterion written around a known weakness is a
criterion written to pass. It tightens when the fix lands.

**Added 2026-08-29, and it is a criterion about the harness as much as
about the design.** Two more clauses cover the AER pointer TMR:

- every `evq_ptr` target must be a replica's storage register
  (`...u_{w,r}ptr_{a,b,c}.bits`), not the voted `wr_ptr` / `rd_ptr`
  wire; and
- every one of those injections must be CORRECTED — masked at the
  outputs *and* counted in `CNT_TMR`.

The first exists because this campaign has now twice deposited into a
continuously driven voter output and reported the result as if it said
something about the replicas (the configuration domain on 2026-08-26,
the pointers on 2026-08-29; section 3.3). The second is deliberately
stronger than "never SDC": an injection that never reached a flip-flop
comes back MASKED, and MASKED is exactly the quiet nothing a
mis-targeted injector produces. Both clauses would have failed the
campaign at HEAD on 2026-08-29 instead of letting it report 23 SDC and
zero corrections against a working TMR.

Every one of those criteria is an RTL criterion and none of them can
fail because a structure vanished in synthesis; `test_05_summary` would
have passed unchanged on a netlist with one configuration bank instead
of three. `sw/tests/test_synthesis_guards.py` is the separate,
netlist-level criterion that covers that class, and it is not a
substitute for this one or vice versa.

---

## 2. Coverage

Flip-flop counts below are **counted from the RTL declarations** at the
8 x 8 geometry, not from a synthesised netlist [fact for the counts,
estimate for their mapping to silicon area].

That distinction cost this project a real defect and is worth stating
rather than assuming. Counting from the RTL is the right basis for
*coverage* — the campaign injects into RTL signals, so RTL is the
population it samples — but it is not evidence that any of those
flip-flops reach silicon. The 165 flip-flops of the `cfg_a/b/c` row
below were 55 in the netlist until 2026-08-26; see the correction in
section 4 and the discussion in section 7.4.

"Represented" means the campaign sampled that structure, not that it
injected into every bit of it — 255 injections cannot cover 996
flip-flops, and wide registers are sampled at low, middle and high bit
positions by design (section 1.1). The percentage below says how much of
the design the map speaks about, not how exhaustively.

| Structure | Group | FF | Injections |
|---|---|---:|---:|
| Synapse weight file, `lif_core.wmem` | `lif_wmem` (+ unread control) | 256 | 20 |
| Configuration TMR replicas, `cfg_a/b/c` [†] | `cfg_tmr_a/b/c` | 165 | 15 |
| Membrane potentials, `lif_core.vmem` | `lif_vmem` | 128 | 24 |
| AER queue storage, both `mem[]` | `evq_mem` | 128 | 32 |
| Register-bank configuration | `regbank_cfg` | 75 | 16 |
| ECC-protected weight word (`ecc_data`/`ecc_check`) | `ecc_ff`, `ecc_port_*` | 72 | 23 |
| Fault counters and stickies | `regbank_cnt`, `telemetry_primed` | 48 | 24 |
| Refractory counters, `lif_core.rmem` | `lif_rmem` | 32 | 12 |
| EVQ_OUT show-ahead adapter + queue read port | `evq_hold` | 35 | 14 |
| Neuron scan and emission state | `lif_scan` | 23 | 21 |
| Event dispatcher (`dstate`, `evw`) | `dispatch` | 18 | 18 |
| AER queue pointers (4 x 3 b) | `evq_ptr` | 12 | 24 |
| Neuron-core FSM state | `lif_fsm` | 4 | 12 |
| **Total represented, to 2026-08-26** | | **996** | **255** |
| Neuron-state ECC check field, `lif_core.smem` [‡] | `lif_smem` | 48 | 18 |
| Synapse ECC check field, `lif_core.wchk` [‡] | `lif_wchk` (+ unread control) | 32 | 14 |
| **Total represented, from 2026-08-27** | | **1076** | **287** |
| AER pointer TMR replicas, `aer_ptr_bank.bits` [§] | `evq_ptr` | +24 | +48 |
| **Total represented, from 2026-08-29** | | **1100** | **335** |
| Dispatcher bounded wait, `fetch_wait`/`fetch_timeout` [¶] | `wdog_fetch`, `wdog_fetch_dir` | 7 | 15 |
| Show-ahead bounded wait, `oh_wait`/`oh_timeout` [¶] | `wdog_oh`, `wdog_oh_dir` | 7 | 15 |
| **Total represented, from 2026-08-30** | | **1114** | **365** |

[†] 165 in the RTL, and 55 in the netlist until 2026-08-26 — the three
replicas were merged into one register bank by synthesis. Corrected in
`hw/rtl/pilot_top.v` on that date; see section 4 and section 7.4.

[§] The `evq_ptr` row above counts 12 flip-flops and 24 injections
because that is what the pointers were: four 3-bit registers. Since the
pointer TMR of 2026-08-29 they are twelve `aer_ptr_bank` instances, 36
flip-flops, and the campaign injects into all of them — one replica at
a time, three replicas per drawn phase, so 72 injections against the
same 24 phases (section 3.3). The `+24 / +48` row is the delta, so the
`evq_ptr` row and this one together read 36 FF and 72 injections.

[¶] Added to the target list on 2026-08-30, closing the gap section 7.3
named as the next campaign's first item. These 14 flip-flops are the two
safety nets themselves — the structures added after this campaign found
the `D_FETCH` deadlock of section 5.1 and the `oh_req` deadlock of
section 5.7, whose entire job is to convert a silent hang into a
host-visible fault. They draw from the same second seeded stream as the
check fields and are appended after them, so no phase drawn by any
earlier group moved: measured, the first 335 records of the 365-injection
run are field-for-field identical to the 335-injection run [fact]. Each
row is 9 random-phase injections plus 6 directed ones (section 5.8);
`fetch_wait` and `oh_wait` are sampled low / mid / high and the two
one-bit timeout pulses take three phases each.

[‡] Added to the target list on 2026-08-27, with the memory hardening
that created them. They are the 80 flip-flops the protection itself
costs, and section 3.2 explains why leaving them unrepresented would
have been the configuration-TMR mistake in a different form. They draw
their injection phases from a second seeded stream (`EXT_RNG` in
`hw/tb/test_fi_campaign.py`) so that adding them moved no phase of the
255 injections above; the first 255 records of the 287-injection run are
field-for-field identical to the 255-injection run [fact].


The design held **1160 flip-flops** at this geometry by the same count
when the campaign was written, so the campaign represents **86%** of
them. The remaining 164, named rather than left implicit: the serial
shift engine (`bit_cnt`, `rx_sh`, `tx_sh`, `cmd_addr`, `cmd_wr`, the two
strobes — 80 FF), the input synchronizers (26 FF), the SYNC echo path
(`sync_push`, `sync_word` — 17 FF), the EVQ_IN read register
(`rd_data`, `rd_valid` — 17 FF), the ECC weight loader state (`ld_*`,
`ecc_commit`, `w_addr_cmt` — 12 FF), the EVQ_OUT drop counter (8 FF,
which cannot increment by design), and four single flops (`err_cfg_r`,
`mismatch_q`, `fi_rd_en`, `fo_rd_en`). Section 7.3 explains why, and
what it would take to close.

The section 5.1 fix adds 7 flip-flops that the target list does not
inject into (`fetch_wait[5:0]` and `fetch_timeout`), so the post-fix
design holds **1167** and the represented share is **85%** with the
unrepresented count at 171 [fact]. The `dispatch` group's 18 FF above
is `dstate` and `evw` only, unchanged.

The section 5.7 fix of 2026-08-29 does the same thing to the other end
of the pipe: `oh_wait[5:0]` and `oh_timeout` are 7 more flip-flops, and
the `evq_hold` group's 35 FF above is unchanged.

**Corrected 2026-08-30.** Until that date this paragraph read "the target
list does not inject into" those two structures, and added that "the
structures that convert a hang into a report are themselves unmeasured
by this campaign, and an upset in one of them is an unmeasured way to
get the hang back." That was true and it is no longer. Both bounded
waits are in the target list now, with 30 injections between them, and
the sentence they earned is section 5.8: an upset in one of them is a
*measured* way to get the hang back, and the measurement found it. The
`dispatch` and `evq_hold` group flip-flop counts above still exclude
them — the two `wdog_*` rows carry them — so no structure is counted
twice.

**A note on the several flip-flop totals in this document, because they
look like a contradiction and are not.** Each is a measurement of the
design as it stood when that section was written, and the design grew
five times during the work this document reports:

| total | the design it describes |
|---|---|
| 1,161 | before the dispatcher-deadlock fix (quoted in the section 7.4 correction) |
| 1,167 | after that fix adds `fetch_wait` and `fetch_timeout` |
| 1,247 | after the memory hardening of section 2.1 |
| 1,274 | after the AER pointer TMR of 2026-08-29 adds 24 replica flip-flops |
| 1,281 | after the show-ahead bounded wait of section 5.7 adds `oh_wait` and `oh_timeout` |

The last two are measured with the same census, on 2026-08-29:
**1,281 declared, 1,275 mapped, 6 lost to optimisation** at HEAD, and
1,274 declared with only the `oh_req` fix reverted [fact]. The 6 lost is
the same constant recorded before and after the configuration-TMR fix
and before and after the pointer TMR, so nothing new is disappearing.

Against that census the represented share was **1,100 of 1,281, or 86%**,
with 181 flip-flops unrepresented, and is **1,114 of 1,281, or 87%**,
with 167 unrepresented, since the two bounded waits joined the target
list on 2026-08-30 — and the two numbers come from
different counting methods, which is the caveat this paragraph exists
for. 1,100 is hand-counted from the RTL declarations in the coverage
table above; 1,281 is the yosys census. They disagree by a handful of
flops for the reasons in the paragraph below, so read 86% as accurate to
about half a percentage point, and read the *named* unrepresented
structures in section 7.3 rather than the residual as the statement of
what is not covered.

Re-measured at HEAD on 2026-08-27 with `sw/tests/test_synthesis_guards.py`'s
own census: **1,241 declared, 1,235 mapped, 6 lost to optimisation**
[fact]. The 6 lost is the same constant recorded before and after the
TMR fix, so nothing new is disappearing. The 1,247 above does not
reproduce at HEAD and the 6-flop gap is not explained by the
optimisation step — counting without `opt_clean` gives 1,922, not 1,247
— so it is most likely a measurement of an intermediate state during
the hardening rather than of the committed design. The shares computed
against it in section 2.1 are therefore accurate to roughly 0.3
percentage points; the census should be re-derived when the next
campaign runs rather than patched here, because the numerator would
have to be re-measured too and this document does not guess at numbers.

**After the memory hardening of 2026-08-26 [fact].** `hw/rtl/lif_core.v`
adds 80 flip-flops and no others: `wchk`, 8 SECDED check bits per 16
weights, 32 bits at 8 x 8; and `smem`, 6 check bits per neuron state
word, 48 bits at 8 x 8. The design therefore declares **1247**
flip-flops, the campaign represents **1076** of them (86%), and the
unrepresented count is unchanged at 171 — the extension covers exactly
what the hardening added and nothing else.

The +80 is cross-checked mechanically rather than counted by hand:
a yosys census of the two trees (`proc; flatten; opt_expr; opt_clean;
simplemap`, the same recipe `sw/tests/test_synthesis_guards.py` uses for
its declared-flip-flop fixture, pinned yosys 0.67+146) reports **1159**
flip-flops before the hardening and **1239** after, a delta of exactly
+80 [fact]. The census sits 8 below the hand count in both trees,
consistently, because `opt_clean` removes the EVQ_OUT drop counter — the
8 constant bits this section already names as unrepresentable.

### 2.1 How much of the design is protected

The question this document could not answer before the hardening, on the
same RTL-declaration basis [fact for the counts, and see section 7.4 for
what an RTL count does and does not license]:

| Mechanism | Structures | FF | Corrects? |
|---|---|---:|---|
| SECDED (26,20) on the neuron state word | `vmem` 128 + `rmem` 32 + `smem` 48 | 208 | yes |
| SECDED (72,64) on the synapse file | `wmem` 256 + `wchk` 32 | 288 | yes |
| Configuration TMR | `cfg_a/b/c` | 165 | yes |
| SECDED (72,64) on the weight staging word | `ecc_data` 64 + `ecc_check` 8 | 72 | yes |
| **Correcting total** | | **733** | |
| HD-2 encoding + `default` park | `lif_core.state` | 4 | detects only |
| **Any protection at all** | | **737** | |

**733 of 1247 flip-flops — 58.8% of the design — carry single-error
correction, and 737 (59.1%) carry some protection.** Before the
hardening the correcting total was 237 of 1167 (20.3%) and the
any-protection total 241 (20.7%). The hardening moved 416 flip-flops
from unprotected to correcting for 80 added ones, so the protected share
went up by 38 percentage points at a 6.9% increase in register count.

**After the pointer TMR of 2026-08-29 [fact].** The four AER queue
pointers join the correcting column: 36 flip-flops where there were 12,
voted bitwise and reported on `CNT_TMR`. On the re-measured declared
census of 1281 (section 2) that is **769 of 1281 correcting (60.0%)**
and 773 (60.3%) with any protection, for 24 added flip-flops — the
cheapest protected-share increase in the programme so far, and the one
with the largest measured effect per bit (section 5.2).

Two things this table is not. It is not a statement about area — the
correction is cheap in flip-flops and expensive in combinational logic,
and `hw/rtl/lif_core.v`'s header section 6 carries the measured cell
areas. And it is not a statement about the *rest* of the design: the 508
unprotected flip-flops are still 40% of the register count, they are
where every residual silent corruption in section 3.4 comes from, and
section 6 ranks them.

---

## 3. Measured distribution

### 3.1 Pre-hardening

255 injections, seed `0x16F12026`, **pre-fix** [fact]. `stream` and
`state` split the SDC column: `stream` = the drained event stream was
wrong; `state` = the event stream was right for this run but the
retained neuron state was not.

| Group | MASKED | CORRECTED | DETECTED | SDC | HANG | n | SDC rate | stream | state |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `lif_rmem` | 0 | 0 | 0 | 12 | 0 | 12 | 100.0% | 3 | 9 |
| `lif_vmem` | 2 | 0 | 0 | 22 | 0 | 24 | 91.7% | 7 | 15 |
| `evq_ptr` | 0 | 0 | 1 | 22 | 1 | 24 | 91.7% | 21 | 1 |
| `lif_wmem` | 7 | 0 | 0 | 9 | 0 | 16 | 56.2% | 5 | 4 |
| `evq_hold` | 7 | 0 | 1 | 6 | 0 | 14 | 42.9% | 6 | 0 |
| `dispatch` | 8 | 0 | 0 | 6 | 4 | 18 | 33.3% | 6 | 0 |
| `lif_scan` | 15 | 0 | 0 | 6 | 0 | 21 | 28.6% | 3 | 3 |
| `evq_mem` | 25 | 0 | 0 | 7 | 0 | 32 | 21.9% | 7 | 0 |
| `regbank_cfg` | 9 | 1 | 5 | 1 | 0 | 16 | 6.2% | 1 | 0 |
| `lif_wmem_unread` (control) | 4 | 0 | 0 | 0 | 0 | 4 | 0.0% | 0 | 0 |
| `lif_fsm` | 0 | 0 | 12 | 0 | 0 | 12 | 0.0% | 0 | 0 |
| `cfg_tmr_a` | 0 | 5 | 0 | 0 | 0 | 5 | 0.0% | 0 | 0 |
| `cfg_tmr_b` | 0 | 5 | 0 | 0 | 0 | 5 | 0.0% | 0 | 0 |
| `cfg_tmr_c` | 0 | 5 | 0 | 0 | 0 | 5 | 0.0% | 0 | 0 |
| `ecc_port_single` | 0 | 12 | 0 | 0 | 0 | 12 | 0.0% | 0 | 0 |
| `ecc_port_double` | 0 | 0 | 4 | 0 | 0 | 4 | 0.0% | 0 | 0 |
| `ecc_ff` | 0 | 7 | 0 | 0 | 0 | 7 | 0.0% | 0 | 0 |
| `regbank_cnt` | 5 | 4 | 9 | 0 | 0 | 18 | 0.0% | 0 | 0 |
| `telemetry_primed` | 1 | 3 | 2 | 0 | 0 | 6 | 0.0% | 0 | 0 |
| **TOTAL** | **83** | **42** | **34** | **91** | **5** | **255** | **35.7%** | **59** | **32** |

**Post-fix, the same 255 injections [fact].** Only two rows move, and
only by the five records section 5.1 lists; every other row is
identical, so the table above stands for the post-fix run with these
two substitutions:

| Group | MASKED | CORRECTED | DETECTED | SDC | HANG | n | SDC rate | stream | state |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `evq_ptr` | 0 | 0 | 2 | 22 | 0 | 24 | 91.7% | 21 | 1 |
| `dispatch` | 8 | 0 | 4 | 6 | 0 | 18 | 33.3% | 6 | 0 |
| **TOTAL** | **83** | **42** | **39** | **91** | **0** | **255** | **35.7%** | **59** | **32** |

Three cross-cutting numbers, pre-fix [fact]:

- **21 of the 34 DETECTED outcomes also had a corrupted output.** A
  detection is a recoverable failure, not a harmless one. The other 13
  are false alarms: the design flagged something while producing the
  right answer (section 5.5). Post-fix the ratio is **23 of 39**: three
  of the five recovered dispatchers went on to produce the correct
  output and the other two did not.
- **32 of the 91 SDC outcomes corrupted only the retained neuron
  state**, not the event stream of this run: 15 `lif_vmem`, 9
  `lif_rmem`, 4 `lif_wmem`, 3 `lif_scan` and 1 `evq_ptr`. They are
  deferred divergence, not masking (section 5.3).
- **15 injections left an architectural register wrong after a run the
  design otherwise handled** — `W_ADDR`, `SCRATCH`, `NODE_ID`,
  `ECC_INJ_POS`, `TMR_INJ`, `CTRL.SCRUB_EN`, `CFG_AXON`, `CTRL.EN`
  (section 5.6).

The last two carry over to the post-fix run unchanged: 32 state-only
SDC and 15 latent registers in both, as does the telemetry-mismatch
count of 34 [fact].

### 3.2 Post-hardening

Same seed, same geometry, same workload, same target list, 2026-08-27,
against `hw/rtl/lif_core.v` with the SECDED codes on `wmem` and on the
`{R, V}` neuron state word [fact]. **Exactly three rows move**, so the
section 3.1 table stands for this run with these three substitutions and
the new total:

| Group | MASKED | CORRECTED | DETECTED | SDC | HANG | n | SDC rate | stream | state |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `lif_wmem` | 16 | 0 | 0 | 0 | 0 | 16 | 0.0% | 0 | 0 |
| `lif_vmem` | 24 | 0 | 0 | 0 | 0 | 24 | 0.0% | 0 | 0 |
| `lif_rmem` | 12 | 0 | 0 | 0 | 0 | 12 | 0.0% | 0 | 0 |
| **TOTAL** | **126** | **42** | **39** | **48** | **0** | **255** | **18.8%** | **44** | **4** |

**Where the SDC went, per structure [fact].** The comparison is
record-by-record, not histogram-to-histogram: the two logs carry the
same 255 injections in the same order, same group, same bit, same drawn
burst and same drawn delay, so "moved" means one named injection changed
class.

| Group | SDC before | SDC after | Records that moved | To |
|---|---:|---:|---:|---|
| `lif_wmem` (live weights) | 9 / 16 | 0 / 16 | 9 | MASKED |
| `lif_vmem` | 22 / 24 | 0 / 24 | 22 | MASKED |
| `lif_rmem` | 12 / 12 | 0 / 12 | 12 | MASKED |
| `lif_wmem_unread` (control) | 0 / 4 | 0 / 4 | 0 | — |
| every other group, all 16 of them | 48 | 48 | **0** | — |

Three things in that table are worth saying out loud.

**Nothing moved the wrong way.** Not one record went from MASKED,
CORRECTED or DETECTED into SDC, and no record outside the three hardened
groups changed class at all — including `completed`, `out_ok`, the
status word and the counters, which are compared field by field. A
hardening that fixes one structure and perturbs another would show up
here and does not.

**The unread-weight control still reads MASKED**, which means it is
still doing its job: it was MASKED before the hardening because the
workload never reads that row, and it is MASKED now for the same reason,
not because the code corrected it. It bounds the `lif_wmem` result the
same way it did before and no better.

**All 43 landed in MASKED, and none in CORRECTED.** That is not the code
failing to report — it is `hw/rtl/pilot_top.v` not listening. Section
4.1.

The cross-cutting numbers, post-hardening [fact]:

- **23 of the 39 DETECTED outcomes also had a corrupted output**,
  unchanged from post-fix. The hardening touches no detection path.
- **4 of the 48 SDC outcomes corrupted only the retained neuron state**,
  down from 32: 3 `lif_scan` and 1 `evq_ptr`. Every one of the 28
  state-only corruptions that disappeared was in `vmem`, `rmem` or
  `wmem`. The three that remain are the mis-steered scan index of
  section 5.7, which writes a *correct* update to the *wrong* neuron —
  a code over the state word cannot see that, because the word it
  protects is written consistently, just to the wrong address.
- **15 latent registers** and **34 telemetry mismatches**, both
  unchanged. Neither is in the hardened path. The telemetry-mismatch
  count is the one number in this list that has since moved a long way,
  and not because anything got worse: wiring the `lif_core` ECC outputs
  took it to 113 on the same 287 injections and the pointer TMR took it
  to 185 on 335, because `telemetry_ok` is false whenever a counter
  moved that a clean bring-up does not move — which, outside the two
  telemetry groups, is the design correctly reporting the upset it was
  given. Section 3.4.

### 3.3 What the injector deposits into, and why that is the right experiment

This question is asked before the numbers are believed, because getting
it wrong has already cost this campaign a result once. When the
configuration TMR replicas became real bank instances, the `cfg_tmr_*`
targets were still depositing on `cfg_a` — by then a continuously driven
net, not a register — and had to be moved to the banks' storage
(`u_cfg_a.bits`; section 4 and `hw/tb/test_fi_campaign.py` target 6).
The memory hardening has exactly the same shape: there is now a
corrected read path sitting next to the raw storage, and a deposit into
one is not the same experiment as a deposit into the other.

**Checked against `hw/rtl/lif_core.v` [fact]:**

- `wmem`, `vmem` and `rmem` are still `reg` arrays and still the
  storage. The hardening deliberately did not rename or reshape them,
  and says so at the declaration in those terms — *"they are the arrays
  `hw/tb/test_fi_campaign.py` deposits upsets into, and a fault map is
  worth nothing if the target names move under it"*. The campaign's
  targets `u_lif.wmem[i]`, `u_lif.vmem[j]` and `u_lif.rmem[j]` are
  unchanged and are flip-flop deposits.
- The values the datapath consumes are `w_code`, `v_cur` and `r_cur`,
  which are **wires** driven by `secded_dec` and `lif_state_dec`. The
  campaign does not touch them, and must not.

**So the experiment being run is: the flip-flop holds the wrong bit, and
the read path has to cope.** That is the one that models an upset.
Depositing on the corrected output would model a fault the code cannot
see by construction — a combinational transient at the decoder output,
which section 7.4 places outside this fault model — and would measure
nothing except the datapath downstream of the decoder. **No retargeting
was needed** for the memories.

#### The pointers needed one, and it was missed for a day

**The same trap, the second time [fact].** The pointer TMR of
`hw/rtl/aer_fifo.v` landed on 2026-08-29 and turned `wr_ptr` and
`rd_ptr` from registers into voted wires driven by six `aer_ptr_bank`
instances per queue. The `evq_ptr` targets still named
`u_evq_in.wr_ptr` and its three siblings. Those names still resolved,
the campaign still ran, and it reported **23 SDC and 1 HANG out of 24,
with zero CORRECTED** — its pre-TMR result to within one outcome,
against three replicas and a proven majority vote.

Two things were wrong with that deposit, not one:

- `wr_ptr` is not a flip-flop, so no physical upset corresponds to it.
  A deposit there models a fault arriving at the voter *output*, a node
  nothing in this design claims to protect.
- Icarus holds a deposit on a driven net until the driver
  **re-evaluates**, and the voter's inputs stop changing as soon as the
  pointer stops moving. So the deposit did not decay after a cycle: it
  persisted for the rest of the run. What was measured was a permanent
  stuck-at on the voted node, which is a harsher fault than the one the
  fault model claims and a fault no single upset can cause.

That is why the number looked like the pre-TMR number. It was not a
statement about the replicas at all.

**Retargeted 2026-08-29 [fact].** The group now deposits into
`{u_evq_in,u_evq_out}.u_{w,r}ptr_{a,b,c}.bits`, the banks' storage
registers, and each injection lands in exactly one replica — which is
what a single-event upset in a triplicated pointer is. The three
replicas are injected at the **same drawn phases** rather than drawing
their own, so `phases()` consumes exactly the numbers it consumed
before and the groups drawn after this one (`evq_mem`, `evq_hold`,
`dispatch`) keep the phases this document already reports. Only the
pointer group's own records moved.

Bit positions are per replica. Banks A and B store the pointer and its
exact complement, so bit *i* of `bits` is bit *i* of the pointer; bank C
stores an XOR mixing, so bit *i* of `bits` decodes to two or three wrong
pointer bits (`aer_fifo.v`, `aer_ptr_bank` header). Both are
single-replica faults and a bitwise majority masks each of them, which
is the point of the mixing rather than a weakness of it — and the
measurement below is what turns that from an argument into a result.

The pass criteria of section 1.8 now enforce both halves, so the next
edit that re-points this group at a driven net fails the suite instead
of reporting zeros.

The evidence that the deposits still land is in the diff rather than in
the argument. 43 records changed class and all 43 are these three
targets: the same bit, in the same array, at the same drawn cycle,
produced a silent corruption before the hardening and does not after. A
deposit that had stopped landing would have moved nothing, and one that
had never landed would have been MASKED in both runs. `test_00_control`
independently refuses to run the campaign at all unless a deposit into
`u_lif.state` comes back DETECTED (section 1.8).

What the raw-storage choice does **not** settle is the check fields.
`wchk` and `smem` are 80 flip-flops of storage that did not exist before
the hardening, they are part of every codeword the decoders read, and
until 2026-08-27 no injection reached them. That is the same shape of
gap as the one section 7.4 describes for the TMR replicas — a protection
believed rather than measured — so the target list was extended.

**Check fields, extension of 2026-08-27 [fact].** 32 injections, drawn
from a second seeded stream so the 255 above are untouched (section 2):

| Group | Target | Bits | MASKED | CORRECTED | DETECTED | SDC | HANG | n | SDC rate |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `lif_wchk` | `u_lif.wchk` | 0, 3, 7 (codeword 0); 8, 11, 15 (codeword 1) | 12 | 0 | 0 | 0 | 0 | 12 | 0.0% |
| `lif_wchk_unread` | `u_lif.wchk` | 24 (codeword 3, control) | 2 | 0 | 0 | 0 | 0 | 2 | 0.0% |
| `lif_smem` | `u_lif.smem` | 0, 2, 5 / 18, 20, 23 / 42, 44, 47 (neurons 0, 3, 7) | 18 | 0 | 0 | 0 | 0 | 18 | 0.0% |
| **TOTAL** | | | **32** | 0 | 0 | **0** | 0 | **32** | **0.0%** |

Both codewords the `lif_wchk` group hits are ones the workload reads:
codeword 0 covers axons 0 and 1, codeword 1 covers axons 2 and 3, and
the stimulus spikes all four. Codeword 3 is the control and is never
read, exactly like the `lif_wmem_unread` target.

**What that does and does not show.** It shows the protection does not
import the risk it removes: 32 for 32, no silent corruption, no wrong
spike, no wrong retained state, no flag. The mechanism is worth naming
so the zero is not over-read — a single-bit error in a systematic code's
check field leaves the *data* field untouched, so the only way it could
corrupt an inference is if the decoder mis-corrected, flipping a data
bit in response to a syndrome that points at a check bit. **That is the
failure this group tests for, and it did not occur.** It is a
smaller claim than "the check bits are safe", and it is the claim the
experiment supports.

**One consequence that follows from the mechanism rather than from the
measurement, stated because it belongs in a hardening plan
[estimate].** The two check fields are not repaired alike. `smem` is
re-encoded by the scan's write-back on the next event or tick that
visits that neuron, so an upset in it is gone within a few cycles.
`wchk` has no such path — the scan never writes `wmem` — so an upset in
a weight check field persists until the host rewrites that word, and it
is not announced, because the correction reaches no counter and no pin
(section 4.1). For the rest of that interval the codeword has spent its
one-error budget, and a second upset anywhere in the same 72 bits is a
DED rather than a correction. This campaign is single-bit by
construction (section 7.4), so it measures none of that; it is an
argument for wiring the telemetry and for the periodic weight reload of
section 5.4, not a measured rate.

**Two of the 32 drew a phase identical to the pinned one**, so the
extension is 30 distinct (target, bit, phase) points and not 32
[fact]. Section 7.1 applies unchanged.

**The campaign of record as it stood on 2026-08-27 was 287 injections
[fact]: 158 MASKED (55.1%), 42 CORRECTED (14.6%), 39 DETECTED (13.6%),
48 SDC (16.7%), 0 HANG.** Then the ECC telemetry was wired (section
4.1), which moved 79 records from MASKED to CORRECTED and nothing else,
taking the same 287 to 79 / 121 / 39 / 48 / 0. Section 3.4 carries the
current run.

**On quoting any of these against any other.** The 16.7% above is a
correct number and it is **not** the number to place next to the
pre-hardening 35.7%. They have different denominators — 287 against 255
— and the 32 extra injections are all in the newly created check fields,
all MASKED, so the difference between 16.7% and 18.8% is entirely the
arithmetic of adding 32 non-SDC records to the bottom of a fraction and
says nothing about the design. **The like-for-like figure for the memory
hardening is 91/255 = 35.7% to 48/255 = 18.8%**, the same 255
experiments before and after, which is section 3.2.

### 3.4 Post-wave-5 — superseded as the campaign of record by 3.5, and unchanged by it

Same seed, same geometry, same workload, 2026-08-29, against
`hw/rtl/aer_fifo.v` with the pointer TMR, `hw/rtl/pilot_top.v` with the
bounded `oh_req` wait of section 5.7, and the `evq_ptr` targets moved
onto the replica storage (section 3.3). **335 injections, 892 s wall,
28.77 ms simulated [fact]:**

| Group | MASKED | CORRECTED | DETECTED | SDC | HANG | n | SDC rate | stream | state |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `evq_hold` | 7 | 0 | 1 | 6 | 0 | 14 | 42.9% | 6 | 0 |
| `dispatch` | 8 | 0 | 4 | 6 | 0 | 18 | 33.3% | 6 | 0 |
| `lif_scan` | 15 | 0 | 0 | 6 | 0 | 21 | 28.6% | 3 | 3 |
| `evq_mem` | 25 | 0 | 0 | 7 | 0 | 32 | 21.9% | 7 | 0 |
| `regbank_cfg` | 9 | 1 | 5 | 1 | 0 | 16 | 6.2% | 1 | 0 |
| `lif_wmem` | 3 | 13 | 0 | 0 | 0 | 16 | 0.0% | 0 | 0 |
| `lif_wmem_unread` (control) | 4 | 0 | 0 | 0 | 0 | 4 | 0.0% | 0 | 0 |
| `lif_vmem` | 0 | 24 | 0 | 0 | 0 | 24 | 0.0% | 0 | 0 |
| `lif_rmem` | 0 | 12 | 0 | 0 | 0 | 12 | 0.0% | 0 | 0 |
| `lif_wchk` | 0 | 12 | 0 | 0 | 0 | 12 | 0.0% | 0 | 0 |
| `lif_wchk_unread` (control) | 2 | 0 | 0 | 0 | 0 | 2 | 0.0% | 0 | 0 |
| `lif_smem` | 0 | 18 | 0 | 0 | 0 | 18 | 0.0% | 0 | 0 |
| `lif_fsm` | 0 | 0 | 12 | 0 | 0 | 12 | 0.0% | 0 | 0 |
| `evq_ptr` | 0 | **72** | 0 | **0** | 0 | 72 | 0.0% | 0 | 0 |
| `cfg_tmr_a` | 0 | 5 | 0 | 0 | 0 | 5 | 0.0% | 0 | 0 |
| `cfg_tmr_b` | 0 | 5 | 0 | 0 | 0 | 5 | 0.0% | 0 | 0 |
| `cfg_tmr_c` | 0 | 5 | 0 | 0 | 0 | 5 | 0.0% | 0 | 0 |
| `ecc_port_single` | 0 | 12 | 0 | 0 | 0 | 12 | 0.0% | 0 | 0 |
| `ecc_port_double` | 0 | 0 | 4 | 0 | 0 | 4 | 0.0% | 0 | 0 |
| `ecc_ff` | 0 | 7 | 0 | 0 | 0 | 7 | 0.0% | 0 | 0 |
| `regbank_cnt` | 5 | 4 | 9 | 0 | 0 | 18 | 0.0% | 0 | 0 |
| `telemetry_primed` | 1 | 3 | 2 | 0 | 0 | 6 | 0.0% | 0 | 0 |
| **TOTAL** | **79** | **193** | **37** | **26** | **0** | **335** | **7.8%** | **23** | **3** |

**What moved, record by record [fact].** The two logs share 263 targets
— everything except the 24 retired pointer targets — and the comparison
is field-by-field, not histogram-to-histogram:

| | count | |
|---|---:|---|
| common records | 263 | of which **1** changed class |
| the one that changed | 1 | `evq_hold` / `oh_req` / bit 0 / burst 0 / delay 0: **HANG → DETECTED** |
| retired targets (voted pointer wires) | 24 | were 23 SDC + 1 HANG; not a physical fault (section 3.3) |
| new targets (pointer replica storage) | 72 | **72 CORRECTED, 0 SDC, 0 HANG** |

Nothing else moved: not a class, not `completed`, not `out_ok`, not a
status word, not a counter. That is the point of drawing the three
replicas at the same phases — `evq_mem`, `evq_hold` and `dispatch` are
drawn *after* `evq_ptr` from the same stream, and a change in how many
numbers the pointer group consumed would have re-rolled all three.

The cross-cutting numbers, post-wave-5 [fact]:

- **20 of the 37 DETECTED outcomes also had a corrupted output**, and
  the ratio changed only by the one HANG that became a detection.
- **3 of the 26 SDC outcomes corrupted only the retained neuron state**,
  down from 4: the one `evq_ptr` state-only corruption is gone with the
  target that produced it. The remaining three are all the mis-steered
  scan index of section 5.7.
- **15 latent registers**, unchanged.
- **185 telemetry mismatches**, up from 113. `telemetry_ok` compares
  against the same bring-up with no deposit, so outside the two
  telemetry groups a mismatch means the design **correctly counted the
  event it was given** — and 72 of the 72 new pointer injections
  incremented `CNT_TMR`, which is exactly the 72-record rise. This
  number goes up when the chip reports more, which is the direction it
  should move.

**The like-for-like figure for the pointer TMR.** The wave-5 change
cannot be quoted as 16.7% → 7.8%: those are 287 and 335 injections and
the added 48 are all corrections in hardware that did not exist before.
The defensible comparison is per-structure and is the one section 5.2
gives — the pointers went from **22 SDC of 24** to **0 SDC of 72** — and
on the 263 targets the two runs share, SDC went from **26 of 263 to 26
of 263**, unchanged, which is what a change confined to the pointers
should do. Wave 5 removed a structure from the SDC list; it did not
improve any other structure and does not claim to.

### 3.5 Post-wave-5 plus the safety nets — the campaign of record

Same seed, same geometry, same workload, same RTL — **`hw/rtl` is
byte-identical to the run above** — 2026-08-30. The only change is to
the campaign: the two bounded-wait counters of sections 5.1 and 5.7 are
in the target list at last, with 18 random-phase injections between them
and 12 directed ones. **365 injections, 567 s wall, 31.31 ms
simulated [fact]:**

| Group | MASKED | CORRECTED | DETECTED | SDC | HANG | n | SDC rate | stream | state |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `evq_hold` | 7 | 0 | 1 | 6 | 0 | 14 | 42.9% | 6 | 0 |
| `dispatch` | 8 | 0 | 4 | 6 | 0 | 18 | 33.3% | 6 | 0 |
| `lif_scan` | 15 | 0 | 0 | 6 | 0 | 21 | 28.6% | 3 | 3 |
| `evq_mem` | 25 | 0 | 0 | 7 | 0 | 32 | 21.9% | 7 | 0 |
| `wdog_fetch_dir` (directed) | 0 | 0 | 5 | 1 | 0 | 6 | 16.7% | 1 | 0 |
| `wdog_oh_dir` (directed) | 0 | 0 | 5 | 1 | 0 | 6 | 16.7% | 1 | 0 |
| `regbank_cfg` | 9 | 1 | 5 | 1 | 0 | 16 | 6.2% | 1 | 0 |
| `wdog_fetch` | 6 | 0 | 3 | 0 | 0 | 9 | 0.0% | 0 | 0 |
| `wdog_oh` | 6 | 0 | 3 | 0 | 0 | 9 | 0.0% | 0 | 0 |
| every other group | 15 | 192 | 27 | **0** | 0 | 234 | 0.0% | 0 | 0 |
| **TOTAL** | **91** | **193** | **53** | **28** | **0** | **365** | **7.7%** | **25** | **3** |

The seventeen groups folded into "every other group" are unchanged from
the section 3.4 table, row for row, and are not repeated here.

**What moved, record by record [fact].** The two logs share all 335
targets of the previous run, and **not one of them changed class** —
not `completed`, not `out_ok`, not a status word, not a counter. That
is the phase discipline working as designed: the new groups draw from
`EXT_RNG` and are appended after every existing group, so the
comparison with the 335 is exact and the 30 new records are the whole
difference.

| | count | |
|---|---:|---|
| common records | 335 | of which **0** differ in any field |
| new random-phase records | 18 | 12 MASKED, 6 DETECTED, 0 SDC, 0 HANG |
| new directed records | 12 | 10 DETECTED, 2 SDC, 0 HANG |

**Diff the log by key, not by line.** The two new random-phase groups
are appended to `target_list`, so the 18 records they add sit at the
*end of the structural block* and push the ECC and telemetry records
18 positions down the file. A naive positional or line-by-line
comparison therefore shows hundreds of differences and none of them are
real. Matched on `(group, target, bit, burst, delay)`, **every one of
the 335 old records is present and identical field for field, and there
are exactly 30 new ones** [fact, verified against the previous file in
git].

The cross-cutting numbers, and only one of them moved for a reason that
is not simply "there are 30 more records" [fact]:

- **23 of the 53 DETECTED outcomes also had a corrupted output**, up
  from 20 of 37, and all three additions are directed cases. Two are
  the `report_kept` controls — a real deadlock, caught, reported, and
  the run still wrong, which is what section 5.1 already said a bounded
  wait is: a recovery and not a repair. The third is `wdog_fetch_dir` /
  `fire_spurious`, where the dispatcher's own bound, fired early by an
  upset in its counter, destroys the event it was fetching. Section
  5.8.
- **3 of the 28 SDC outcomes corrupted only the retained neuron
  state**, unchanged — so **both new SDC records corrupted the drained
  event stream**. They are the two `report_erased` cases and they are
  the finding of section 5.8.
- **15 latent registers**, unchanged. **185 telemetry mismatches**,
  unchanged: nothing in the two new groups moves a counter, because
  a bounded-wait timeout latches `STATUS.ERR_CFG` and no counter
  counts it (section 5.8 says why that matters).

**The like-for-like figure.** 7.8% → 7.7% SDC is arithmetic on a larger
denominator and means nothing; the two runs measure the same design.
The defensible statement is per-structure: **the residual SDC list of
section 3.4 is unchanged, record for record, at 26 across the same five
structures, and two new records join it from a sixth that had never
been injected into — the safety nets themselves.**


## 4. What held

Every mechanism the pilot claims was exercised and none produced a
counterexample. These are the campaign's positive results and they are
the reason the negative ones below are worth acting on rather than
worth panicking about.

**One thing is deliberately not in this list, as of 2026-08-30.** The
two bounded-wait counters are protective structures and they were
measured for the first time in the 365-injection run, and they do not
appear here because **they produced a counterexample.** Half of each of
them held for a structural reason worth having; the one-cycle pulse
each reports through did not. Section 5.8, and it is in section 5
rather than in section 4 for exactly that reason.

**Neuron-core FSM: 12/12 DETECTED [fact].** All four bits of
`lif_core.state`, three injection phases each. The five legal encodings
are the even-parity words of a 4-bit vector, so every single-bit upset
lands on a word no legal transition can produce; the core parks in
S_SAFE, freezes the neuron state file, latches `err_cfg`, and the flag
reaches `STATUS.ERR_CFG` and the ERR pin. All twelve also stopped the
run (`completed` false in every record), which is correct behaviour and
is why they show as DETECTED with a corrupted output rather than as
false alarms. The recovery is exercised on all twelve as a side effect
of the readback: `N_ADDR` is configuration-locked while BUSY, so the
neuron state file could not have been read at all if `CTRL.SOFT_RST`
had failed to un-park the core. This confirms docs/10 section 11.4 as a
measurement rather than as a design intent.

What the twelve readbacks show, precisely [fact]: **four** of them read
back the all-zero post-`STATE_CLR` state, and they are exactly the four
injections pinned to the first busy cycle of the first burst — the core
parked before any event had updated the file, so the frozen state *is*
the post-`STATE_CLR` state. The other eight parked part-way through the
run and read back a partial state: not the post-`STATE_CLR` value and
not the clean golden final value either (no `lif_fsm` record has
`state_ok`). That is what a freeze at the moment of parking looks like
mid-run, and it is the reason all twelve classify with a corrupted
output. An earlier revision of this section claimed all twelve read
back the post-`STATE_CLR` state; that was true of four.

> **Correction, 2026-08-26 — the 15/15 result below is an RTL-level
> measurement that did not hold in the netlist until the synthesis fix
> of that date.** The original measurement stands exactly as recorded
> and is not withdrawn: at RTL, `cfg_a`, `cfg_b` and `cfg_c` are three
> distinct signals, the campaign deposited into one of them at a time,
> and the voter masked every one. What the campaign could not see is
> that the three replicas did not exist as three registers in silicon.
> They were written from the same expression on the same cycle, so
> yosys `opt_dff` normalised them into identical enable flip-flops and
> `opt_merge` hashed those into a single bank. Netlist evidence, read
> off the artifact that fed the 4x2 harden,
> `tt/runs/tt-harden/06-yosys-synthesis/tt_um_melihakbulut_nssoc.nl.v`:
> **362 references to `cfg_a[`, zero to `cfg_b[`, zero to `cfg_c[`**
> [fact]. It was not one PDK's behaviour: the sky130 run
> `hw/openlane/pilot_sky130/runs/sky-03-clk26/` carries 1045
> `sky130_fd_sc_hd__df*` flip-flops with the same zero references to
> `cfg_b[` and `cfg_c[`, and the ECP5 fit measured 1045 TRELLIS_FF —
> against 1161 flip-flops declared by the RTL [fact]. In that netlist
> the voter read one physical bank three times:
> a real upset would have corrupted all three of its inputs together
> and the majority vote would have returned the corrupted value —
> masking nothing, counting nothing, lighting no pin.
>
> `hw/rtl/pilot_top.v` header section 9 fixes this by building each
> replica as its own `pilot_cfg_bank` instance and giving each instance
> a different storage polarity. After the fix, both flows carry
> **1155 flip-flops, 55 under each of `u_cfg_a`, `u_cfg_b` and
> `u_cfg_c`** [fact], which is the +110 the three banks cost.
>
> So this paragraph now reports two different things and both are true:
> **the voting logic is correct and was measured correct at RTL
> (15/15)**, and **the redundancy it votes on only existed in silicon
> from 2026-08-26**. Any use of the 15/15 number against a netlist
> older than that date is a claim about a design that had no
> configuration TMR. See section 7.4 for why no amount of RTL injection
> could have caught this, and `sw/tests/test_synthesis_guards.py` for
> the check that now closes the gap.
>
> **What the campaign deposits into, after the same fix.** With the
> replicas built as instances, `cfg_a` / `cfg_b` / `cfg_c` are no longer
> registers — they are wires driven by the banks' `q` outputs — so the
> `cfg_tmr_*` targets moved to `u_cfg_a.bits` / `u_cfg_b.bits` /
> `u_cfg_c.bits`, the storage registers inside the banks. This changes
> what the injection *means*, not what it measured: a deposit on the
> output models an upset at the voter input rather than in the
> flip-flop, and it only survives at all because Icarus lets a deposit
> on a continuously driven net stand until that net's driver next
> re-evaluates, which here is the next clocked configuration write.
> Both spellings were run at 8 x 8 and the 255-injection log is
> byte-identical apart from `wall_seconds` and the three target strings
> [fact], so every number in this document is unaffected. The sampled
> bit positions carry over unchanged as well: a bank stores
> `value ^ POL` and presents `bits ^ POL`, and XOR against a constant is
> bit-wise, so bit *i* of `bits` is still bit *i* of the voted field and
> a single-bit deposit is still a single-bit error at the voter.

**Configuration TMR: 15/15 CORRECTED [fact].** Five voted-field bits
(THETA low, THETA high, V_RESET, S_LEAK, CFG_FLAGS) across all three
replicas. Zero SDC, zero detected failures. Every one was masked at the
voter, produced a bit-exact inference, incremented `CNT_TMR` and lit the
TMR pin — which is the docs/08 section 2.3 fault-visibility convention
holding under measurement, not just under one directed test. Note that
this campaign deposits into the replica **flip-flops**, not into the
`TMR_INJ` read-path emulation, so it also measures the consequence
`tmr_voter.v`'s header states: nothing resynchronises the faulty
replica, the disagreement persists for the rest of the run, and it
counts once (one event per rising edge of mismatch). A configuration
rewrite repairs all three replicas, which is what the bring-up of the
next injection does.

**AER pointer TMR: 72/72 CORRECTED [fact, 2026-08-29].** All three bits
of all four pointers across all three replicas, two phases each, one
replica per injection. Zero SDC, zero detected failures, zero hangs:
every one was masked by the bitwise majority, produced a bit-exact
event stream and neuron state, and incremented `CNT_TMR` through
`aer_fifo`'s `ptr_mismatch`. It is the same result as the configuration
domain with one structural difference that runs the other way: here all
three replicas are reloaded from the **voted** next-state every cycle,
so the corrupted replica is repaired on the next clock edge instead of
persisting for the run — which is why these injections count once and
then leave no residue, and why `evq_ptr` shows no latent corruption.

**Read this number together with section 3.3.** On 2026-08-28 the same
hardware, measured by the same campaign, reported 23 SDC and zero
corrections in this group. The hardware did not change; the injector was
pointed at a driven wire instead of at a flip-flop. The 72/72 is the
measurement; the day in between is the reason section 1.8 now has a pass
criterion that fails the suite when the pointer targets are not storage
registers.

**SECDED weight word, single-bit: 12/12 CORRECTED [fact].** Twelve
codeword positions walked across both fields (data bits 0, 7, 19, 31,
33, 47, 58, 63; check bits 64, 67, 70, 71), rotating over all four
weight words, injected through the design's own `ECC_INJ` port so the
corruption is present at the instant the loader reads the word. Every
one: inference bit-exact against the clean golden, `CNT_SEC` = 1, SEC
pin lit, `CNT_DED` = 0.

**SECDED weight word, double-bit: 4/4 DETECTED, E10-exact on the event
stream 4/4 and on the retained state 3/4 [fact].** `CNT_DED` = 1, DED
pin, `STATUS.DED_SEEN`, `CNT_SEC` = 0 — never miscorrected. In all four
the drained event stream matched a golden model built with exactly that
weight word poisoned, so the degradation is the zero substitution of
docs/10 section 11.2 and not garbage.

Two of the four landed in words holding weights for axons this workload
never stimulates, so their result was also identical to the clean
golden. The third differed from the clean golden by exactly the E10
amount. The fourth is worth stating rather than rounding away: zeroing
word 0, which holds the weights for axons 0 and 1, pushed enough neurons
over threshold that the run emitted more spikes than the five-entry
output path could hold, backpressured past its cycle budget and also
raised `STATUS.OVF_SEEN`. Its event stream was still E10-exact as far as
it got; its final state was read from an interrupted run and therefore
does not match. E10 keeps the *values* right; it does not keep the
*rate* right, and a fail-operational substitution that changes the spike
rate can still saturate the path downstream of it. That is a real
property of zero substitution in a spiking datapath and it is not
recorded anywhere else in this repository.

**Scrubber loop: 7/7 CORRECTED with the stored word repaired [fact].**
Deposits into the stored 72-bit codeword flip-flops (`ecc_data` bits 0,
17, 40, 63; `ecc_check` bits 0, 3, 7) followed by a `SCRUB_STB` pulse
with `CTRL.SCRUB_EN` set. In all seven the error was counted in
`CNT_SEC` and `W_DATA_LO`/`W_DATA_HI` read back byte-identical to the
loaded word. The scrub loop of docs/10 section 11.2 closes.

**Unread-weight control: 4/4 MASKED [fact].** A deliberate control
target in a crossbar row the workload never reads. It came back MASKED
in all four, which is what makes the `lif_wmem` rate in section 3 a
statement about weights the datapath actually uses rather than a
statement about the stimulus.

### 4.1 The memory codes hold — and nothing on the chip says so

**The codes: 84 for 84 [fact].** Post-hardening, at the same seed and
the same 8 x 8 geometry: `lif_wmem` 16/16, `lif_vmem` 24/24,
`lif_rmem` 12/12, `lif_wchk` 12/12, `lif_wchk_unread` 2/2 and
`lif_smem` 18/18 — every single-bit deposit into a coded memory file or
its check field left the drained event stream and the retained neuron
state bit-exact against `sw/golden`, with no silent corruption. The
campaign now enforces that as a pass criterion (`test_05_summary`: *a
single-bit upset in a coded memory file must never be SDC*), so a future
edit that bypasses a decoder or widens a word past the code fails the
suite rather than quietly reducing the number.

**CLOSED 2026-08-27 — the wiring was done and this campaign re-run.**
`hw/rtl/pilot_top.v` now connects all four outputs and counts them on
`CNT_SEC`/`CNT_DED` with their sticky bits. At the same seed and
geometry the 287-injection distribution moves from 158 MASKED / 42
CORRECTED / 39 DETECTED / 48 SDC / 0 HANG to **79 MASKED / 121 CORRECTED
/ 39 DETECTED / 48 SDC / 0 HANG** [fact] — 79 injections cross from
MASKED to CORRECTED. The silent-corruption count is unchanged at 48,
which is the expected result and worth saying plainly: wiring telemetry
changes what the chip can *report*, never what it computes.

(That 287-injection figure is the last one before wave 5. The
335-injection run is section 3.4 and the current 365-injection run is
section 3.5; the 84 coded-memory injections are unchanged in both —
still 0 SDC — and 79 of them still classify CORRECTED for the reason
recorded here.)

Two notes from doing it. The counters are shared with the weight-load
and scrub codec rather than split per domain, because `CNT_SEC` is
defined generically in `regmap.yaml`; the cost is that a host cannot
tell a synapse-array correction from a load-path one, and per-domain
attribution is a named follow-up rather than something to bolt on.
`FAULT_ADDR` is deliberately not written from the core's path, since it
holds a loader-address-space index — so a `DED_SEEN` with an unchanged
`FAULT_ADDR` means the uncorrectable word was inside the core, which is
the one bit of attribution the aggregate does preserve. And both domains
can raise an event in the same cycle: two branches of one always block
writing the same counter would keep only the last, dropping an event on
exactly the busy cycles a radiation counter exists to record, so the
increment is computed once, adds the number of events, and saturates.

The finding as originally written, retained because it is the reasoning
that produced the fix:

**And every one of the 84 classified MASKED. Not one CORRECTED.**

That is not the classifier being conservative; it is the measurement of
a real gap. `hw/rtl/lif_core.v` raises four level outputs when it
corrects or fails to correct — `wmem_sec`, `wmem_ded`, `state_sec`,
`state_ded` — and `hw/rtl/pilot_top.v` leaves **all four unconnected**
at the `u_lif` instantiation [fact, read off the port map]. `lif_core`'s
own header records the decision and calls the wiring "the integration
step that makes these corrections visible in telemetry"; the integration
step has not been taken. So:

- no counter moves, no sticky latches, no fault pin lights, and
  `STATUS` reads exactly as it does on a clean run;
- this campaign, which is allowed to observe only what a bench with an
  SPI master and a logic analyser observes (section 1.2), has no
  evidence a correction happened and must call the run MASKED;
- a host has none either.

**Why that matters more here than it would elsewhere.** This part's
stated purpose is to *measure* the upset environment. Section 5.5 already
makes the point that for such a part the counters are the product. The
hardening has just moved the majority of the design's flip-flops under a
code that corrects — 416 of them, section 2.1 — and the number of those
corrections the mission can report is zero. Before the hardening a
`vmem` upset produced a wrong answer that nobody was told about; after
it, it produces a right answer that nobody is told about. The second is
much better and it is still not what a radiation-measurement payload is
for.

**The uncorrectable case is the sharper end of the same gap
[estimate, from the mechanism; this campaign is single-bit and does not
inject doubles into these arrays].** A double-bit error in a neuron
state word passes the data field through uncorrected with `state_ded`
raised, and a double-bit error in a weight word triggers the E10 zero
substitution with `wmem_ded` raised. Both are exactly the fail-operational
behaviour `lif_core`'s header specifies, and with the outputs
unconnected both are **silent**: the part degrades as designed and
announces nothing. The design knows; the chip does not say.

**Cost of closing it [estimate].** `pilot_top` already carries
`CNT_SEC`, `CNT_DED`, the SEC and DED pins and their stickies, built for
the weight staging word's SECDED. Wiring the four `lif_core` outputs in
is an OR into the existing count-enable and sticky-set terms plus edge
detection on the level outputs, which is the same shape as the
`tmr_voter` mismatch path already in the block. No new counter, no new
pin, no new register-map address. The one design question it forces is
whether a `lif_core` correction should share `CNT_SEC` with the staging
word or get its own counter — sharing loses the ability to tell an array
upset from a staging upset, and the register map has spare addresses.
This is item 1 of section 6.2.

---

## 5. What did not hold

### 5.1 The event dispatcher could deadlock — 5 HANG (2.0%) pre-fix, 0 post-fix

**This is the campaign's one genuinely new mechanism — every other
finding below quantifies a structure the design already knew it had left
unprotected — and it is the one that was acted on [fact].**

All five pre-fix HANG outcomes have the same root cause, confirmed by
instrumented replay of two of them: `dstate` sits in `D_FETCH`
(`2'b01`) with `fi_rd_en` low, `fi_rd_valid` low, and no queue read
outstanding. `D_FETCH` had exactly one exit — `if (fi_rd_valid)` — and
`fi_rd_en` is only ever asserted from the `D_IDLE` arm, so a dispatcher
that arrives in `D_FETCH` without having requested a read waits there
forever. `disp_busy` is high for as long as it does, so `STATUS.BUSY`
is stuck high and the pilot accepts no further event. Recovery is
`CTRL.SOFT_RST`, verified working in both replays.

#### What the operator could and could not see, pre-fix

An earlier revision of this section said that during the deadlock "no
flag is raised anywhere". That is too strong, and a reviewer was right
to dispute it. The pre-fix RTL was reconstructed and the deadlock driven
directly, reading only the serial port and the pins. Measured [fact]:

| Observation | During the pre-fix deadlock |
|---|---|
| `STATUS.BUSY`, and the BUSY pin | **high for the whole observation** — 2600 clock cycles plus every serial frame in between, released only by `CTRL.SOFT_RST` |
| `STATUS.EVQ_IN_EMPTY` | reads 0 from the first queued event onward and never returns to 1 |
| `AER_IN_RDY` pin | drops to 0 once the four-entry input queue fills, on the fourth queued event |
| `STATUS.ERR_CFG`, `STATUS.DED_SEEN` | **never set by the deadlock** |
| `CNT_SEC`, `CNT_DED`, `CNT_AXON_OOR`, `CNT_TMR`, `FAULT_ADDR` | **never move** |
| ERR, SEC, DED, TMR pins | **all stay low**, as long as the host stops offering events |
| `STATUS.OVF_SEEN`, `CNT_EVQ_OVF`, ERR pin | set **only if the host keeps pushing**: the fifth event past an empty four-entry queue overflows it, and from that write on `CNT_EVQ_OVF` counts, `OVF_SEEN` latches and ERR lights |

So the precise statement is: **the pilot has no fault indication for
this failure at all — no flag, no counter and no fault pin names it —
and the only direct symptom is a BUSY that never falls.** A host that
polls `STATUS` sees a part that has been busy for an implausible length
of time, which is a symptom and not a report: nothing distinguishes it
from a long legitimate burst except duration, and the pilot has no
watchdog to make that judgement for the host (section 7.6).

The overflow in the last row is a real, host-visible consequence, and it
deserves to be named rather than rounded away — but it is not a report
of the deadlock. It requires the host to keep pushing into a part that
has stopped acknowledging; it names the wrong fault (an input-queue
overflow, which is a host flow-control error); and it arrives an
arbitrary number of events late. One further measured detail [fact]:
`CTRL.SOFT_RST` clears `CNT_EVQ_OVF` back to 0 while `STATUS.OVF_SEEN`
stays set, because the drop counter lives inside `aer_fifo` and is on
the block reset net while the sticky is not. The recovery therefore
leaves the telemetry self-inconsistent in exactly the way section 5.5
describes for upsets.

Two independent single-bit upsets reach that state:

1. **`dstate` directly — 4 of 10 injections.** `D_IDLE` is `2'b00` and
   `D_ISSUE` is `2'b11`, so both have a one-bit neighbour that is
   `D_FETCH`. The remaining encoding `2'b10` is undefined and the
   `default` arm correctly returns it to `D_IDLE`. The dispatcher FSM
   has recovery for its unreachable encoding and no recovery for its
   reachable one.
2. **`u_evq_in.wr_ptr` — 1 of 6 injections.** `aer_fifo` refuses a read
   while empty by contract (proven in `formal/aer_fifo.sby`: `rd_ok =
   rd_en && !empty`). An upset that makes the queue read empty in the
   cycle a requested read would be granted therefore produces no
   `rd_valid`, and the dispatcher is stranded in `D_FETCH` with the
   queue subsequently refilling behind it. The replay caught it with
   `level = 1` and `dstate = 01` for the entire 2000-cycle budget.

This is not an `aer_fifo` bug — the queue behaves exactly as proven —
and it was not visible to any existing test, because no existing test
put the dispatcher in `D_FETCH` without a read in flight. It was a
missing guard in the pilot's own glue, and it was the one class of
outcome the pilot had no fault indication for.

**Implication.** `lif_core` was given a Hamming-distance-2 encoding and
a `default` recovery precisely so an upset in its state register cannot
resume silently. The dispatcher, which sits in front of it and gates
every event, was not. Three fixes were available, cheapest first
[estimate]:

- a bounded `D_FETCH` timeout that returns to `D_IDLE` and raises
  `STATUS.ERR_CFG` — turns all five HANGs into DETECTED for a counter
  and a comparator;
- an HD-2 encoding for `dstate` with a `default` arm, matching
  `lif_core` (`dstate` is 2 bits today and would become 4);
- a watchdog on `STATUS.BUSY`, which the pilot does not have.

#### The fix, and what the campaign measured after it

The first of the three was implemented in `hw/rtl/pilot_top.v`
section 8: a 6-bit `fetch_wait` counter bounds the `D_FETCH` wait at
`FETCH_WAIT_MAX` = 63 cycles. On expiry the dispatcher returns to
`D_IDLE` and pulses `fetch_timeout`, which latches `sticky_errcfg`, so
`STATUS.ERR_CFG` and the ERR pin report it. Cost: 7 flip-flops and a
comparator [fact, counted from the RTL declarations].

**Post-fix campaign [fact].** Same seed, same target list, same 255
injections. **Exactly five records changed class and every one of them
is a HANG that became DETECTED.** No other record moved — not its
class, not `completed`, not `out_ok`, not its status word:

| Group | Target | bit | burst / delay | Pre-fix | Post-fix | Output after the fix |
|---|---|---:|---|---|---|---|
| `evq_ptr` | `u_evq_in.wr_ptr` | 0 | 0 / 3 | HANG | DETECTED | still corrupted |
| `dispatch` | `dstate` | 0 | 2 / 24 | HANG | DETECTED | golden |
| `dispatch` | `dstate` | 0 | 1 / 13 | HANG | DETECTED | golden |
| `dispatch` | `dstate` | 0 | 1 / 15 | HANG | DETECTED | golden |
| `dispatch` | `dstate` | 1 | 0 / 10 | HANG | DETECTED | still corrupted |

All five now complete the run inside the cycle budget without
`CTRL.SOFT_RST`, all five read `STATUS` = `0x16` (`EVQ_IN_EMPTY` |
`EVQ_OUT_EMPTY` | `ERR_CFG`) and all five light the ERR pin. **Both
routes into `D_FETCH` are covered**, including the `u_evq_in.wr_ptr`
one, which matters because that route does not involve `dstate` at all
and a fix that only hardened the state encoding would have missed it.

**One footnote on that second route, added 2026-08-29.** The
`u_evq_in.wr_ptr` target no longer exists: the pointer is a voted wire
now and the campaign injects into the replica storage instead (section
3.3), so this route is exercised in the current target list only
through `dstate`. That is not a loss of coverage for the *fix* — the
bound is on `D_FETCH` and does not care how the FSM got there — but it
does mean the current campaign no longer demonstrates a pointer-driven
entry into `D_FETCH`, and it cannot, because the vote now masks the
pointer upset before the dispatcher sees it.

Three of the five also produced the golden event stream and the golden
neuron state after recovering, so for those the fix converted a wedged
part into a correct answer plus a flag. The other two recovered and
still had a corrupted output — the upset had already damaged the run —
which is why they are DETECTED-with-wrong-output and not CORRECTED. A
bounded wait is a recovery, not a repair, and this document does not
claim otherwise.

**And a bounded wait is itself state, which this section did not ask
about and section 5.8 does [fact, 2026-08-30].** The 7 flip-flops
above went into the target list a day later than they should have. The
counter survives an upset for a structural reason; the one-cycle
`fetch_timeout` pulse that reports the recovery does not, and an upset
that clears it in that cycle puts this section's failure back exactly
as it was — recovered, wrong, and unannounced.

**Zero HANG does not mean zero hang.** The campaign's 255 injections
reach 86% of the design's flip-flops (section 2) and its HANG class is
"did not complete inside the budget and nothing was flagged". A hang
originating in one of the 164 unrepresented flip-flops — the serial
shift engine and the ECC loader in particular (section 7.3) — is
outside what this run can see, and `STATUS.BUSY` still has no watchdog
behind it (section 7.6). What is measured is that the two known routes
into the `D_FETCH` deadlock now report, and that no new hang appeared
anywhere else in the target list.

**Regression test.** `hw/tb/test_pilot_top.py`,
`test_dispatcher_stranded_in_fetch_recovers_and_is_flagged`. It
deposits `D_FETCH` into `dstate` with the input queue empty — the same
deposit and the same 3 ns offset as the campaign — and then observes
only host-visible results: BUSY clears on its own inside a bounded
number of cycles (measured: 64), `STATUS.ERR_CFG` is set, the ERR pin
is high, `STATUS_CLR` clears the record because the core was never
parked, and a following inference matches `sw/golden` spike for spike
and neuron for neuron. **Mutation-checked [fact]:** with the `D_FETCH`
arm reverted to its single-exit form the test fails at the BUSY poll
with "the dispatcher never left D_FETCH: BUSY still high 512 cycles
after an upset put the FSM there with no read outstanding".

### 5.2 AER queue pointers were the highest-rate silent corruptor — 22/24 SDC, now 0/72

> **Superseded by the pointer TMR of 2026-08-29, and kept in full.** The
> measurement below is what motivated the change and it is not
> withdrawn: at the time it was taken, the four queue pointers were four
> plain registers with no protection of any kind, and they carried the
> highest per-bit silent-corruption rate measured anywhere in the pilot.
> `hw/rtl/aer_fifo.v` now holds each pointer in three `aer_ptr_bank`
> replicas behind a bitwise majority vote, and reports a corrected
> disagreement on `ptr_mismatch`, which `pilot_top.v` counts on
> `CNT_TMR` and latches in `STATUS.TMR_SEEN`. Read this section as the
> diagnosis. The post-TMR measurement is at the end of it, and the
> retargeting the measurement needed first — which took a day and one
> false result to get right — is section 3.3.

Twelve flip-flops — `wr_ptr` and `rd_ptr` of both queues, three bits
each including the wrap bit — and **21 of 24 injections corrupted the
drained event stream with nothing flagged** [fact]. One more corrupted
only the retained state, one deadlocked (section 5.1, and post-fix that
one is flagged as well, taking the flagged count to two of
twenty-four), and pre-fix exactly one of the twenty-four was flagged at
all — and that one is worth reading
closely: it raised `STATUS.OVF_SEEN` with `CNT_EVQ_OVF` still reading
zero, because the overflow was on the **output** queue and
`pilot_top.v` exposes only the input queue's drop counter (`fo_drop` is
deliberately sunk as unused). The operator is told an overflow happened
and is given no count for it. That is defensible as designed — EVQ_OUT
can never drop under normal operation, since `out_ready = !full` — but
an upset breaks that invariant, and the telemetry has no room for the
result.

Every pointer except `u_evq_in.wr_ptr` was 6/6 SDC. The observed
corruption modes, read from the log:

| Mode | Example (golden is `[1, 2, 5, 6, 4, 2]`) |
|---|---|
| whole burst re-emitted | `[1, 2, 5, 6, 1, 2, 5, 6, 4, 2]` |
| events duplicated | `[1, 1, 2, 5, 6, 4, 2]` |
| events lost | `[1, 6, 4, 2]` |
| extra events fabricated | `[1, 2, 5, 6, 4, 2, 4, 6, 2]` |
| unwritten slot presented as an event | `[61680, 1, 2, 5, 6, 4, 2]` (`0xF0F0`, the sentinel) |

Nothing downstream can tell any of these from a legitimate spike train.
An event-driven interface has no sequence numbers and no length field —
docs/10 section 7.1 freezes the event word at TYPE plus a 10-bit ID —
so a duplicated or fabricated spike is indistinguishable from a real
one at the consumer.

**Implication.** This is the best protection-per-flip-flop in the
design: 12 flip-flops, 1% of the register count, carrying the highest
per-bit silent-corruption rate measured anywhere in the pilot. TMR on
the four pointers costs 24 extra flip-flops and four voters
[estimate], and `hw/rtl/tmr_voter.v` is already verified and proven. An
even cheaper partial measure is a redundancy check on `level` (the
pointer difference) that raises `ERR_CFG` when the two queues disagree
with their own occupancy history — but that detects rather than
corrects.

#### After the TMR: 72 for 72 corrected

**The estimate was right about the cost and the campaign now measures
the benefit [fact].** The pointers are twelve `aer_ptr_bank` instances,
36 flip-flops, 24 more than before — the estimate said 24 and it was
exact. On 2026-08-29, with the injector aimed at the replica storage
(section 3.3), **all 72 single-replica upsets across the twelve banks
came back CORRECTED**: the drained event stream and the retained neuron
state were bit-exact against `sw/golden` in every one, and every one
moved `CNT_TMR`, so the correction is reported rather than silent.
`evq_ptr` goes from 22 SDC of 24 to **0 SDC of 72**, and from one
flagged outcome of 24 to 72 of 72.

Three things that result does *not* say, because a zero is easy to
over-read:

- It is a **single-replica** result. `formal/aer_fifo_props.v` assumes
  at most one faulty replica per pointer, the campaign injects one at a
  time, and neither says anything about two upsets landing on the same
  bit of two replicas before the voted feedback repairs them. The
  repair happens on the next clock edge, so that window is one cycle
  wide; this campaign does not measure it (section 7.4).
- It covers **replica C's mixing** as well as A and B. A single upset
  in bank C decodes to two or three wrong pointer bits at the voter
  input, which is the price of the storage transform that keeps
  synthesis from hashing the three banks together. All 24 of C's
  injections are in the 72, and the vote masked every one — the widened
  error is still one replica, and a bitwise majority does not care how
  many bits of one replica are wrong.
- It says nothing about the queue **storage**, which is unprotected and
  is now the AER path's SDC contributor (`evq_mem`, section 6).

**The one HANG this group produced on 2026-08-29 was an artefact, and
here is the evidence [fact].** Before the retarget the campaign
returned a HANG at `u_evq_in.wr_ptr`, bit 1, burst 0, delay 14.
Replayed with a cycle-by-cycle trace: the deposit left the *voted*
write pointer stuck at `001` — a driven net Icarus never re-evaluated,
because the pointer stopped moving (section 3.3) — the read pointer
swept the whole 3-bit space re-reading stale slots, the same burst was
emitted twice, EVQ_OUT filled, `lif_core` held its next spike against
the full queue and `STATUS.BUSY` stayed high. That is **not a
deadlock**: draining EVQ_OUT once frees the queue and the design goes
idle, which was measured directly — after one drain the design reported
idle and the queue was empty. It reads as HANG only because the harness
waits for idle *before* draining, and the fault it models is a
permanent stuck-at on a voter output, which no single upset can cause.
The corresponding real experiment, a deposit in one replica, is
CORRECTED. Contrast section 5.7's `oh_req` HANG, which was replayed the
same way and *was* a genuine deadlock: no host action clears it.

### 5.3 The neuron state file is unprotected, and its corruption persists

> **Superseded by the hardening of 2026-08-26, and kept in full.** The
> measurement below is what motivated the change and it is not
> withdrawn: at the time it was taken, `vmem` and `rmem` had no
> protection of any kind. `hw/rtl/lif_core.v` now codes `{R, V}` as one
> SECDED (26,20) word per neuron, and the re-run of 2026-08-27 puts the
> same 24 `vmem` and the same 12 `rmem` injections — same bits, same
> phases, same seed — at **0/24 and 0/12 SDC** (section 3.2). Read this
> section as the diagnosis, not as the current behaviour. The
> *persistence* argument it makes is the part that survives and is worth
> keeping: it is why the fix had to correct rather than detect, and
> `lif_core.v`'s header records that reasoning.

`vmem` 22/24 SDC, `rmem` 12/12 SDC [fact]. Together 160 flip-flops with
no protection of any kind — no parity, no ECC, no TMR, and deliberately
not even on the reset net (docs/10 section 3).

The important qualifier, and it cuts both ways: **24 of those 34 SDC
outcomes corrupted only the retained state**, not the event stream of
this eight-command run. A campaign that compared only the spike train
would have called them masked. They are not masked. V and R are the
neuron's memory; a wrong V biases every subsequent event until the
neuron next spikes (which overwrites it with V_RESET) or until the host
issues `STATE_CLR`. Only 2 of 24 `vmem` injections were actually masked,
and both are the same mechanism: a bit-0 flip on `vmem[0]` and on
`vmem[3]`, absorbed by the shift-based leak. E6 decays by
`max(|V| >> S_LEAK, 1)`, which quantises neighbouring potentials into the
same result — at S_LEAK = 3, `leak(-32)` and `leak(-31)` are both -28 —
so a one-LSB error can be erased outright by a tick. **Confirmed
independently [fact]**: perturbing the same bit in the golden model
before the run reproduces both maskings exactly (events and state both
golden), while the same bit on `vmem[7]`, whose trajectory does not land
in a shared bucket, is not absorbed. Shift quantisation is the only
masking mechanism a LIF membrane offers for a small error, and it does
not reach past the low bits: every bit-4, bit-11 and bit-15 injection
diverged.

`rmem` at 12/12 is the more surprising half. R is four bits and reads
zero most of the time, so a single-bit upset almost always *sets* a
spurious refractory count — which then gates E1..E5 for that neuron on
every following event (docs/10 E7), suppressing updates that should have
happened. Three of the twelve propagated into a wrong spike stream
inside the run; the other nine left the neuron in a state the host would
read back wrong.

**Implication [estimate].** There is no cheap in-place fix for 160 bits
of live state. For the pilot this is arguably correct as designed: a
demonstrator whose purpose is to make upsets visible benefits from an
unprotected, host-readable state file — the `N_ADDR`/`N_DATA` port turns
every one of these into a measurement. For a product the options are
parity on V with substitution on error, or bounding the persistence by
issuing `STATE_CLR` at frame boundaries, which is a host policy
available today at zero silicon cost.

### 5.4 Weight storage is protected on the way in and unprotected once there

> **Superseded by the hardening of 2026-08-26, and kept in full.** The
> gap this section names — protected staging word, unprotected array —
> is closed: `lif_core.wmem` now sits under one SECDED (72,64) codeword
> per 16 weights, and the same 16 live-weight injections that were 9/16
> SDC here are **0/16** in the re-run of 2026-08-27 (section 3.2). The
> zero-silicon host mitigation below is still worth having, for the
> reason `lif_core.v`'s header gives: the load port's read-modify-write
> re-encodes a whole word, so a full image reload leaves every codeword
> exactly clean, which bounds the accumulation of a second error in a
> word the code can only correct one error in.

The ECC path is clean (section 4): 12/12 singles corrected, 4/4 doubles
detected, 7/7 scrub repairs. But that protects the 72-bit
staging word. Once the loader has copied the nibbles into `lif_core`'s
256-flip-flop `wmem`, nothing checks them again: **9 of 16 injections
into weights the workload reads were SDC** (56.2%), five of them
corrupting the event stream [fact]. The control target in an unread row
was 4/4 MASKED, so this rate is about live weights, not about the
stimulus.

`wmem` is the **largest structure in the design** at 256 of the 1167
flip-flops. Multiplying its measured per-bit rate by its size makes it
the largest expected source of silent corruption in the pilot
[estimate: 256 x 0.56 ~ 144 "SDC-weighted bits", against 117 for `vmem`
and 11 for the queue pointers].

**Implication.** The mitigation already exists and costs no silicon: the
host can periodically reload the whole weight image through the existing
ECC-checked loader, which repairs `wmem` from a protected source. That
turns a permanent corruption into one bounded by the reload interval.
It should be written into the driver contract. A silicon fix — parity
per weight word inside `lif_core`, or the SRAM-macro build where the
array carries its own ECC (the `lif_core.v` header already notes E10
"returns with the SRAM-macro build") — belongs to the next architecture
step, not to this pilot.

### 5.5 Telemetry is unprotected and can both invent and erase records

This matters more here than it would in most designs, because for a chip
whose stated purpose is to *measure* upset rates, the counters are the
product.

**Inventing records [fact].** 13 of 18 `regbank_cnt` injections produced
a flag or a counter movement while the output was perfectly correct:
nine DETECTED (an upset in `CNT_DED`, `CNT_AXON_OOR`, the EVQ_IN drop
counter, or the `DED`/`ERR_CFG`/`OVF` stickies) and four CORRECTED (an
upset in `CNT_SEC` or `CNT_TMR`). Because the counters saturate at 8
bits rather than counting to 32 (deviation D1), a single upset in the
top bit is not a small error: **one flip of `CNT_SEC` bit 7 turned a
count of 0 into 128**, and the same for `CNT_TMR`.

**Erasing records [fact].** The `telemetry_primed` group starts each run
with one *real* corrected single-bit weight error, so `CNT_SEC` reads 1
and the SEC pin is lit before the deposit. Then:

- an upset in `CNT_SEC` bit 0 took the count back to 0. The SEC sticky
  pin stayed high, so the telemetry became self-inconsistent — and the
  classifier, which reads only what the chip reports, called the run
  **MASKED**. A real corrected upset happened and the record of it was
  gone.
- an upset in `sticky_sec` cleared the pin while `CNT_SEC` still read 1:
  the same inconsistency in the other direction.
- an upset in `CNT_SEC` bit 1 turned the count of 1 into 3, inflating a
  real measurement rather than erasing it.

**Implication.** Both directions are visible as a *disagreement between
a counter and its sticky bit*, and that is exploitable for free. Two
fixes [estimate]:

- **Host-side, available today:** treat "counter nonzero" and "sticky
  set" disagreeing as a detected fault. This needs no RTL change and
  should go into the driver contract and the bench script.
- **Silicon:** parity or duplication over the four counters and six
  stickies, about 48 flip-flops, or a comparator that raises `ERR_CFG`
  on counter/sticky disagreement — far cheaper than protecting them
  outright, and it converts an erased record into a detected one.

### 5.6 Latent register corruption

Fifteen injections left an architectural register wrong after a run the
design otherwise handled cleanly [fact]: `W_ADDR` (2), `SCRATCH` (2),
`NODE_ID`, `ECC_INJ_POS`, `TMR_INJ` (2), `CTRL.SCRUB_EN`, plus
`CFG_AXON` (4) and `CTRL.EN` (2) which were also flagged or corrupted in
their own right. Eight of the fifteen were MASKED for this run and would
be inherited whole by the next host command sequence — a weight load
that starts from a corrupted `W_ADDR` writes the whole image to the
wrong offset.

This reproduces the sibling programme's finding on its own register bank
and carries the same remedy: **the driver must rewrite `W_ADDR` and
`CTRL` before every use rather than trusting a previously-set value.**
The bring-up in this very campaign already does, which is why the
campaign itself is not contaminated by it.

### 5.7 The show-ahead adapter and the neuron scan — including a second deadlock

`evq_hold` 6/14 SDC (42.9%) with `oh_valid` and `u_evq_out.rd_valid`
both 2/2 [fact]: a one-bit valid flag on a one-deep adapter either
fabricates an event out of stale `oh_data` or drops the one it was
holding. `oh_data` itself was 2/6 — the data is less dangerous than the
flag that says the data is there.

`lif_scan` 6/21 (28.6%) [fact], concentrated in `out_pend` (3/3, the
same valid-flag pattern) and `jj` (2/6, the scan index, which re-steers
which neuron an update lands on). `out_event` was 0/6 — the emitted word
is written one cycle before it is consumed, so its live window is
narrow.

#### `oh_req` could deadlock the output path — found 2026-08-29, fixed

**The second silent hang in the pilot, and the same shape as the
first [fact].** The 2026-08-29 campaign returned a HANG in this group:
`evq_hold`, target `oh_req`, bit 0, burst 0, delay 0. Reproduced by
instrumented replay and the mechanism read directly off the trace.

`oh_req` is the adapter's "a queue read is outstanding" flag. It is set
only together with `fo_rd_en`, cleared only by `fo_rd_valid`, and the
arming condition is gated on `!oh_req`. An upset that sets it with no
read outstanding therefore waits for a grant that will never be
requested: the adapter never issues another read, EVQ_OUT never
advances, and the queue fills. In the replay, sixteen cycles after the
deposit the design sat with `oh_req` = 1, `oh_valid` = 0, `fo_rd_en` =
0, `fo_rd_valid` = 0 and EVQ_OUT full at 4 of 4, and stayed there for
the rest of the run. `lif_core` then held its next spike against the
full queue, `STATUS.BUSY` went high and stayed high, and no flag, no
counter and no fault pin moved.

**Why it is a deadlock and not the backpressure it looks like.** With
`oh_valid` low, neither observer can free the entry: a serial EVQ_OUT
read returns VALID = 0 and an `AER_OUT_ACK` edge pops nothing. The host
sees `EVQ_STAT.OUT_FILL` reporting events it cannot get out. Only
`CTRL.SOFT_RST` or a reset recovers it. That distinguishes it sharply
from the pointer HANG discussed in section 5.2, which is ordinary
backpressure a single host read clears.

**The fix, same as section 5.1's [fact].** `hw/rtl/pilot_top.v` header
section 8: a 6-bit `oh_wait` counter bounds the `oh_req` wait at
`OH_WAIT_MAX` = 63 cycles. On expiry the adapter clears `oh_req`,
re-arms on the next cycle and pulses `oh_timeout`, which latches
`sticky_errcfg`, so `STATUS.ERR_CFG` and the ERR pin report it. Cost: 7
flip-flops and a comparator [fact, counted from the RTL declarations;
declared census 1274 before, 1281 after]. Nothing is lost by the
recovery: an `oh_req` with no read behind it is by construction a state
in which the queue dequeued nothing, so the re-armed read fetches the
word that was next all along — measured, the replay recovers with the
correct next event and the run then matches `sw/golden`.

**Regression test.** `hw/tb/test_pilot_top.py`,
`test_show_ahead_stranded_request_recovers_and_is_flagged`. It deposits
`oh_req` = 1 with one word presented and one still queued, pops the
presented word on the `AER_OUT_ACK` pin, and then observes only
host-visible results: `AER_OUT_VLD` rises again on its own inside a
bounded number of cycles (measured: 60) carrying the correct next
event, `STATUS.ERR_CFG` is set, the ERR pin is high, `STATUS_CLR`
clears it, and the remaining events drain in golden order.
**Mutation-checked [fact]:** with the bounded wait removed the test
fails at the `AER_OUT_VLD` poll with "the adapter never issued another
read", and the other 26 tests of that suite still pass — so the mutant
is killed by this test and by nothing else.

**What that test does not cover [fact, 2026-08-30].** It removes the
bounded wait and checks that the test notices. It says nothing about
what happens when the bounded wait is *present and upset*, which is the
question section 5.8 answers for both nets: the `oh_wait` counter holds,
and the `oh_timeout` pulse it reports through is one flip-flop wide.

#### The general finding

This is where the sibling programme's "small routing state carries the
highest per-bit rate" observation does carry over, and it is worth
naming precisely: **in this design the dangerous small state is the
valid flags, not the indices.** `oh_valid`, `u_evq_out.rd_valid` and
`out_pend` are three flip-flops and were 7/7 SDC between them, every one
of them corrupting the event stream. The indices (`jj`, `ev_axon_r`)
were 3/12, and all three of those corrupted only the retained neuron
state — a mis-steered scan writes the right update to the wrong neuron
without changing what was emitted. That is the opposite emphasis from
the sibling's `yw_ptr` result and is the clearest single example of why
its conclusions were not imported.

### 5.8 The safety nets are partially robust — the counter holds, the report is a single point of failure

This section answers the question section 7.3 left open on 2026-08-29:
what happens when the watchdog itself is upset. The two bounded waits
of sections 5.1 and 5.7 are the only structures in the pilot whose
entire job is to convert a silent hang into a host-visible fault. They
were added because this campaign found the two deadlocks, and they were
then left out of the target list — so the structures that catch the
failure class this chip exists to rule out were themselves unverified
against that same failure class. They are in it now, and the answer is
**partially robust**: the wait counter is sound and cannot be made to
lose a timeout, and the one-cycle report it fires through is a single
point of failure that a single upset turns back into a silent hang.

#### The counter holds, and it holds for a structural reason

**Random phases [fact].** 12 injections into `fetch_wait[5:0]` and
`oh_wait[5:0]`, six per counter, at low / mid / high bit positions:
**12 MASKED, 0 SDC, 0 HANG.** Two things make that not luck:

- **A single-bit upset cannot fire either timeout early.** Both
  counters increment by one and exit on an equality test against
  `{6{1'b1}}` = 63. From the zero the counter holds outside a wait, one
  flipped bit can only produce 1, 2, 4, 8, 16 or 32, and none of them is
  63. Reaching the bound from that zero takes all six bits at once, and
  from a counter part way through a wait it takes however many bits the
  two values differ in; the directed `fire_*` cases below had to move
  six and four respectively, and the log records the popcount of every
  constructed deposit for exactly this reason.
- **A single-bit upset cannot stop either timeout firing.** Monotone
  increment with an equality test at the maximum reaches that maximum
  from every value below it, and fires immediately from the maximum
  itself. There is no counter value from which the wait does not end.
  Nor does a corrupted value persist: `fetch_wait` is zeroed on every
  successful fetch and `oh_wait` on every `fo_rd_valid` and every
  re-arm, so its lifetime is one event and not a mission.

**Directed, `clear_midwait` [fact].** The counter zeroed 20 cycles into
a real bounded wait, on both nets. Both still time out, both still
latch `STATUS.ERR_CFG` (`STATUS` = `0x16`), both recover, and both
produce the golden event stream and the golden neuron state. The wait
is longer — one upset buys one more full 63-cycle count, bounded, not a
restart loop — and nothing else changes. **The answer to "does it
restart forever" is no, and it is no by construction.**

#### Firing early costs one event on one net and nothing on the other

**Directed, `fire_early` [fact].** The counter driven to its bound 10
cycles into a real wait, on both nets: DETECTED, `ERR_CFG` set, golden
output on both. Firing early during a genuine fault is a faster
recovery and costs nothing.

**Directed, `fire_spurious` [fact].** The same deposit with no fault
present, placed on a *legitimate* one-cycle wait, and here the two nets
diverge:

| | dispatcher (`fetch_wait` → 63 in a legitimate `D_FETCH`) | adapter (`oh_wait` → 63 in a legitimate `oh_req`) |
|---|---|---|
| class | DETECTED | DETECTED |
| `STATUS` | `0x16`, ERR pin high | `0x16`, ERR pin high |
| output | **corrupted** — got `[2, 3, 4, 6, 2]` against golden `[1, 2, 5, 6, 4, 2]` | golden, spike for spike and neuron for neuron |

**The dispatcher's own bound destroys the event it was fetching and the
adapter's does not, and the difference is one guard.** The read had
already been granted: `aer_fifo` advanced its pointer and delivers
`fi_rd_valid` the cycle after the spurious timeout took `dstate` back
to `D_IDLE`, and the `D_IDLE` arm has no branch that accepts a late
grant, so the popped word is gone. The adapter captures under
`if (fo_rd_valid)`, which is not gated on `oh_req`, so the same late
grant still lands in `oh_data` and the run is untouched. The same
circuit twice, opposite outcomes.

Two caveats, both load-bearing. The construction takes six bit flips,
so it is **outside the single-bit fault model** of section 7.4 — a
statement about what the structure does when driven to that state, not
a rate. And the loss is *announced*: `ERR_CFG` is set and the ERR pin
is high, so this is a detected event loss and not a silent one. It is
reported here because the fix costs zero flip-flops.

#### The report is where the net breaks

`fetch_timeout` and `oh_timeout` are one-bit pulse registers, high for
exactly one cycle, cleared unconditionally at the top of their own
`always` block, and `sticky_errcfg` samples them at the following clock
edge. That single cycle is the whole of the protection, in both
directions.

**Set spuriously — 6 of 6 [fact].** Every one of the six random-phase
injections into the two pulse flops came back DETECTED with a golden
output: a report of a fault that did not happen, at a 100% rate for
that bit. The host cannot tell it from a real one. `STATUS.ERR_CFG` is
shared with the parked-core term and the invalid-configuration term, no
counter counts a timeout and no status bit names one — so a fabricated
timeout is indistinguishable from a genuine `D_FETCH` deadlock, and on
a part flown to *measure* upset rates that is a corrupted measurement
as surely as an erased one (section 5.5 makes the same point about the
counters).

**Cleared in that one cycle — and this is the finding [fact].** The
`report_erased` cases plant the real fault, let the net catch it, and
flip the pulse in the one cycle it is high. The `report_kept` controls
run byte-for-byte the same script with the final deposit removed —
including the 64-cycle poll that waits for the pulse, so the two
records differ in exactly one deposit and in nothing else. **One
deposit apart:**

| Case | class | `STATUS` | ERR pin | drained event stream (golden: `[1, 2, 5, 6, 4, 2]`) |
|---|---|---|---|---|
| `wdog_fetch_dir` / `report_kept` | DETECTED | `0x16` | high | `[0, 1, 2, 3, 4, 2]` |
| `wdog_fetch_dir` / `report_erased` | **SDC** | `0x06` | **low** | `[0, 1, 2, 3, 4, 2]` |
| `wdog_oh_dir` / `report_kept` | DETECTED | `0x16` | high | `[0, 1, 2, 3, 4, 2]` |
| `wdog_oh_dir` / `report_erased` | **SDC** | `0x06` | **low** | `[0, 1, 2, 3, 4, 2]` |

Read the table row by row. **All four runs deadlocked, all four
recovered, and all four returned the same wrong answer, word for word.
The class changes anyway, because the only thing that changed is
whether the chip said so.** The event streams are byte-identical across
the pair — which is what makes this a controlled experiment rather than
an anecdote, and which also confirms directly what the RTL says: the
timeout pulse feeds `sticky_errcfg` and nothing in the datapath, so
erasing it removes the report and only the report.

**Why the control had to include the poll, recorded because the first
version of it did not [fact].** Written without the 64-cycle wait, the
control returned a *golden* output while the case it controls returned
a corrupted one — which would have supported a much stronger and false
claim, that erasing the report also corrupts the run. It does not.
`sticky_errcfg` drives `status_word` and the `err` pin and nothing else
in `hw/rtl/pilot_top.v`; there is no datapath consumer for it. The
difference was the harness: the erasure script holds `run_stimulus` up
for 64 more cycles before the serial drain begins, and that moves the
drain relative to the recovery. Making the control wait the same 64
cycles removed the difference and the two streams became identical.
**A control that differs from its case in two things measures
neither**, and this one now differs in one deposit.

The recovery still happens in all four — `completed` is true everywhere
and the campaign's bounded-wait criterion holds, which is why
`test_04_watchdog_directed`'s one hard assertion passes. What does not
happen is the report. The design deadlocks, unwedges itself, returns a
wrong answer, and says nothing: **`STATUS` reads `0x06`
(`EVQ_IN_EMPTY | EVQ_OUT_EMPTY`), every counter reads zero and every
fault pin is low.** That is the exact operator-visible picture section
5.1 documented for the *pre-fix* design, restored by one bit.

**So, plainly: the bounded waits are partially robust, and the claim
this campaign supports is narrower than "the safety nets hold".** The
counter half is robust and provably so. The reporting half is a single
unreplicated flip-flop with a one-cycle live window, and it is a
silent-failure path: one upset in it converts a caught fault back into
an uncaught one. The bounded *wait* is not a single point of failure —
the count cannot be broken — but the *announcement* of it is, and it
needs the same treatment the pointers got.

**What the rate does and does not say.** The random draw found the
fabricated direction six times out of six and the erased direction not
once, and it never will: the erasure window is one cycle of a 31 ms run
and it exists only while a timeout is already firing, so the joint
probability is negligible and the expected number of such events in a
mission is far below one [estimate]. That is an argument about how
*often*, and it is not the argument that matters here. The pilot exists
to make upsets visible, and the one case where the report is lost is by
construction the case where something happened. This is why the cases
were constructed rather than drawn, and it is the one place in this
document where section 7.1's "treat the ordering as the result" advice
cuts the wrong way: an outcome a rate cannot reach is not an outcome
that does not exist.

#### The fix, and its cost

**Not implemented in this pass.** `hw/rtl/pilot_top.v` is shared and was
being worked in concurrently; all three items below need the section
5.1 and 5.7 regression tests re-run and a fresh flip-flop census, which
is a wave and not an edit. Ordered by benefit per flip-flop:

1. **Retire the pulse flops and latch the stickies from the timeout
   condition.** `sticky_errcfg` is set today from the registered pulse.
   Setting it instead from the combinational expiry term — `dstate ==
   D_FETCH && !fi_rd_valid && fetch_wait == FETCH_WAIT_MAX`, and its
   `oh_req && !fo_rd_valid && oh_wait == OH_WAIT_MAX` twin — makes the
   report and the recovery the same clock edge. **The design cannot then
   recover without reporting, and there is no one-cycle flop left to
   upset.** Cost: **−2 flip-flops** [fact, counted from the RTL
   declarations], plus a three-term AND and a 6-bit equality carried
   into the fault-counter process. It closes the erased direction
   outright and the fabricated direction with it, because the term is
   derived rather than stored. [estimate] the combinational path is
   short and neither flow is near its timing bound, but it is a path
   into a block on a different reset net, which is why item 2 exists.
2. **If that path is unacceptable, duplicate and OR.**
   `fetch_timeout_b` and `oh_timeout_b` written from the same
   expressions, with `sticky_errcfg` set from the OR of each pair. An
   upset that clears one copy is masked. Cost: **+2 flip-flops.**
   Strictly weaker — it closes the erased direction and leaves the
   fabricated one exactly as it is — and worth taking only as a
   fallback.
3. **Give `D_IDLE` the arm the adapter already has**, so a grant that
   arrives after a timeout is consumed rather than dropped: `if
   (fi_rd_valid) begin evw <= fi_rd_data; dstate <= D_ISSUE; end`. This
   removes the `fire_spurious` event loss above and makes the
   dispatcher's recovery match the adapter's, which is worth having on
   its own. Cost: **0 flip-flops**, one mux on `evw` and one on
   `dstate`.

**Not proposed: TMR on the wait counters.** Twenty-four flip-flops for
the half of the structure the measurement says is already sound. The
counter is not where the weakness is, and spending there would repeat
the mistake of ranking by fault magnitude instead of by measured
behaviour.

**And one line for the telemetry wave (section 6.1 item 3, still
open).** Neither
timeout has a counter. `CNT_SEC`, `CNT_DED`, `CNT_EVQ_OVF`,
`CNT_AXON_OOR` and `CNT_TMR` each name their event; a bounded-wait
expiry lands in `STATUS.ERR_CFG` alongside two unrelated causes and is
counted nowhere, so the host cannot tell one timeout from ten, or a
timeout from a parked core. A `CNT_TIMEOUT` on the existing counter
convention is 8 flip-flops and would make the two deadlock classes
measurable rather than merely visible.

---

## 6. Ranking for the next hardening wave

### 6.1 The ranking that drove wave 4 (pre-hardening)

Kept because it is the reasoning the change was made on, and because a
ranking is only checkable against what happened next. Everything in this
subsection is the pre-hardening measurement.

Two rankings, because they answer different questions and the wrong one
leads to the wrong wave.

**By per-bit SDC rate** — "how dangerous is a single upset here":

| Rank | Structure | SDC rate | n |
|---|---|---:|---:|
| 1 | `rmem` refractory counters | 100.0% | 12 |
| 2 | `vmem` membrane potentials | 91.7% | 24 |
| 2 | AER queue pointers | 91.7% | 24 |
| 4 | `wmem` live synapse weights | 56.2% | 16 |
| 5 | EVQ_OUT adapter / valid flags | 42.9% | 14 |
| 6 | Event dispatcher | 33.3% (+22.2% HANG) | 18 |
| 7 | Neuron scan state | 28.6% | 21 |
| 8 | AER queue storage | 21.9% | 32 |
| 9 | Register-bank configuration | 6.2% | 16 |

**By expected SDC contribution** — rate x flip-flop count, "where the
silent corruptions will actually come from" [estimate; the rates are
measured, the weighting is arithmetic on the section 2 FF counts]:

| Rank | Structure | FF | rate | weighted |
|---|---|---:|---:|---:|
| 1 | `wmem` synapse weights | 256 | 0.56 | 144 |
| 2 | `vmem` membrane potentials | 128 | 0.92 | 117 |
| 3 | `rmem` refractory counters | 32 | 1.00 | 32 |
| 4 | AER queue storage | 128 | 0.22 | 28 |
| 5 | EVQ_OUT adapter | 35 | 0.43 | 15 |
| 6 | AER queue pointers | 12 | 0.92 | 11 |
| 7 | Neuron scan state | 23 | 0.29 | 7 |
| 8 | Event dispatcher | 18 | 0.33 | 6 |
| 9 | Register-bank configuration | 75 | 0.06 | 5 |

**The recommended wave, ordered by benefit per flip-flop spent:**

1. **Guard the dispatcher. — DONE, and re-measured [fact].** 18 FF,
   removes the only class of outcome the pilot had no fault indication
   for, and the cheapest form (a bounded `D_FETCH` timeout raising
   `ERR_CFG`) is a counter and a comparator. It does not appear high in
   either table above precisely because a HANG is not an SDC — which is
   the point: it is the failure the tables cannot rank, and it is the
   one a spacecraft operator would notice first. Implemented in
   `pilot_top.v` section 8 at a cost of 7 flip-flops and one
   comparator; the post-fix campaign turns all 5 HANGs into DETECTED and
   changes nothing else (section 5.1). The **same treatment was applied
   to the show-ahead adapter on 2026-08-29**, for a second silent
   deadlock this campaign found in `oh_req` — same shape, same cost, and
   section 5.7 has the mechanism, the fix and the mutation check.
2. **TMR the four AER queue pointers. — DONE, and re-measured [fact].**
   12 FF, top-three per-bit rate, `tmr_voter.v` already verified and
   proven, and the corruption it removes is the kind no consumer can
   detect (fabricated and duplicated spikes). Implemented in
   `hw/rtl/aer_fifo.v` on 2026-08-29 as twelve `aer_ptr_bank` instances
   behind a bitwise majority, at the estimated cost of exactly 24 extra
   flip-flops, and reported to the host on `CNT_TMR` through
   `ptr_mismatch`. The re-run puts the group at 72/72 CORRECTED, 0 SDC
   (sections 3.4 and 5.2). It also cost a day of measuring the wrong
   node, which section 3.3 records rather than quietly fixes.
3. **Make the telemetry self-checking.** A counter/sticky disagreement
   comparator raising `ERR_CFG`, plus the host-side cross-check, at
   roughly 48 FF of coverage. This protects the measurement the whole
   product is for. The host half costs nothing and should land first.
4. **Write the `wmem` reload policy into the driver contract.** The
   largest expected SDC contributor has a zero-silicon mitigation today
   — periodic reload through the ECC-checked loader — and no in-place
   fix worth the area at this scale. The silicon answer arrives with the
   SRAM-macro build.
5. **Leave `vmem`/`rmem` unprotected for the pilot, and say so.** 160 FF
   of live state with no cheap fix; for a demonstrator whose job is to
   make upsets visible, a host-readable unprotected state file is an
   instrument, not a defect. Bound the persistence with `STATE_CLR` at
   frame boundaries.
6. **Leave the register-bank configuration unprotected** (6.2%), and
   state the latent-register rule in the driver contract: rewrite
   `W_ADDR` and `CTRL` before every use.

Nothing in this list argues for touching the three hardened structures.
One correction to the cost line below, dated 2026-08-26: the 165 FF of
the configuration TMR domain were an RTL cost that the design was not
actually paying — synthesis had merged the three replicas into one bank
of 55, so the block was carrying the voter, the counter and the pin
while banking the area saving of having no redundancy (section 4
correction). The fix restores the full 165, measured as +110 flip-flops
in both the sg13g2 and the ECP5 flow. The "50 for 50" record below is
an RTL record throughout and section 7.4 says what that does and does
not license.
They cost 165 FF for the configuration TMR domain, 72 FF for the ECC
word plus the SECDED codec, and **one** extra state bit for the
neuron-core FSM encoding — `lif_core` has five states, which a plain
binary encoding would hold in 3 bits, and the Hamming-distance-2
even-parity encoding holds in 4 (an earlier revision of this section
said two). Across this campaign they were **50 for 50** — 12 FSM,
15 TMR replica, 12 ECC single, 4 ECC double, 7 scrub — with not one
silent corruption between them, and with the pointer TMR of 2026-08-29
the same sentence covers **122 for 122** at a further cost of 24 FF. They are the reason the design has a
story at all, and the list above is what it would take to make the rest
of the block deserve the same sentence.

### 6.2 The ranking for wave 6 — and why the argument matters more than the number now

**The residual is flat.** After the memory hardening and the pointer
TMR the silent-corruption tail is 26 records across five structures —
four of them carrying six or seven records each and the fifth carrying
one — and no structure dominates it the way `wmem` and the pointers
dominated the wave-4 table. The two `wdog_*` records of section 5.8 are
excluded from this ranking on purpose: they are a defect with a named
fix that costs negative flip-flops, not a structure to be weighed
against the others.

| Structure | Group | SDC | n | rate | FF | weighted |
|---|---|---:|---:|---:|---:|---:|
| AER queue storage | `evq_mem` | 7 | 32 | 21.9% | 128 | **28.0** |
| EVQ_OUT show-ahead adapter | `evq_hold` | 6 | 14 | 42.9% | 35 | **15.0** |
| Neuron scan and emission state | `lif_scan` | 6 | 21 | 28.6% | 23 | **6.6** |
| Event dispatcher | `dispatch` | 6 | 18 | 33.3% | 18 | **6.0** |
| Register-bank configuration | `regbank_cfg` | 1 | 16 | 6.2% | 75 | **4.7** |

[fact for the rates and the counts; the weighting is arithmetic on the
section 2 flip-flop counts, and it is the same weighting section 6.1
used so the two tables can be read against each other.] The wave-4
table had a leader at 144 and a second at 117; this one has a leader at
28 and a second at 15 out of a total of 60. **The ordering is no longer
the answer, so the argument has to be.**

**The per-target split is what the group rates hide [fact].** Read out
of `hw/tb/fi_campaign_results.json` rather than off the table above:

| Structure | where its SDC actually is |
|---|---|
| `evq_hold` | `oh_valid` 2/2, `u_evq_out.rd_valid` 2/2, `oh_data` 2/6 — **4 of 6 in two single-bit valid flags** |
| `lif_scan` | `out_pend` 3/3, `jj` 2/6, `ev_axon_r` 1/6 — **3 of 6 in one valid flag**, and the other 3 corrupt only retained state |
| `dispatch` | `dstate` 3/10, `evw` 3/8 — evenly split between the state register and the event word |
| `evq_mem` | spread over 4 of the 8 queue slots (`u_evq_in.mem[0]`, `u_evq_out.mem[1..3]`), at bit 0 and bit 14 alike — no concentration to exploit |
| `regbank_cfg` | `ctrl_en` 1/16 — one record, and it is a latent-register case section 5.6 already covers by driver contract |

**Wave 6 should take `evq_hold`.** Not because it leads the weighted
table — it does not, `evq_mem` does — but because the recommendation
column in section 6.1 has always been ordered by benefit per flip-flop
spent, and on that basis it is not close:

1. **Two flip-flops carry two thirds of the group's silent
   corruption.** `oh_valid` and `u_evq_out.rd_valid` are 4 of the 6
   records and 4 of 4 in their own right. Triplicating two one-bit
   flags on the `aer_ptr_bank` pattern already in the tree costs
   **+4 flip-flops** and removes 4 of the 26 residual records: **1.0
   SDC records per flip-flop spent**, against 0.15 for SECDED on
   `evq_mem`. [estimate for the cost; the rates are measured.]
2. **It is the highest per-bit rate left in the design** at 42.9%, and
   section 5.7's general finding says why: in this design the dangerous
   small state is the valid flags, not the indices. A valid flag
   fabricates an event out of stale `oh_data` or drops the one it was
   holding, and no consumer downstream can tell either from a real
   spike. `evq_mem` corruption is a wrong event *word*, which is at
   least bounded by the ID range and, with item 4 below, becomes
   detectable for a fraction of the cost.
3. **The same mechanism extends across the structure boundary for two
   more flip-flops.** `lif_core`'s `out_pend` is the third valid flag
   and it is 3/3 SDC. Triplicating all three — `oh_valid`,
   `u_evq_out.rd_valid`, `out_pend` — is **+6 flip-flops for 7 of the
   26 residual records**, 27% of the whole tail at 1.17 records per
   flip-flop. That is the best measured benefit per flip-flop anywhere
   left in the pilot, and it is invisible in the structure table above
   because it is not a structure: it is a class.
4. **`evq_mem` leads the weighted table and should still not lead the
   wave.** 128 flip-flops of transient event storage, and SECDED (22,16)
   at 6 check bits per 16-bit entry is +48 flip-flops for 7 records —
   0.15 per flip-flop, the worst ratio in the table. This is the same
   judgement section 6.1 item 4 made about `wmem`, for the same reason:
   the right answer for a large regular array arrives with the SRAM
   macro, where the ECC comes with the compiler rather than out of the
   flip-flop budget. The cheap interim is worth costing separately —
   **one parity bit per queue entry, +8 flip-flops**, which does not
   correct but converts all 7 SDC records into a counted drop, at 0.88
   records per flip-flop [estimate]. That is competitive, it covers 128
   flip-flops rather than 3, and it belongs in the same wave as the
   second item rather than the first.
5. **`dispatch` and `regbank_cfg` stay where they are.** The
   dispatcher's 6 records split evenly between `dstate` and `evw`, so
   there is no cheap concentrated fix: an HD-2 encoding for `dstate`
   (+2 FF) converts 3 SDC into DETECTED and does nothing for `evw`,
   which would need its own parity. It is a reasonable third item and
   not a first. `regbank_cfg` at one record in sixteen is below the
   noise of this sample size (section 7.1) and section 5.6's driver
   contract already covers the mechanism.

**And the item this campaign added [fact, section 5.8].** The
bounded-wait *reports* are now a measured silent-failure path and the
primary fix costs **−2 flip-flops**. Nothing else in this document
proposes a hardening that reduces the register count, and it should
land before any of the five above.

---

## 7. Where this evidence is thin

Read this before quoting section 6 anywhere. Every limitation below is a
real bound on what the numbers mean.

### 7.1 Sample sizes are small

One to five injections per bit position, 4 to 32 per group. A group
reported at 100% is "no counterexample in n shots", not a proof: at
n = 12 the rule of three puts the one-sided 95% bound on the missed rate
at about 25%. The same applies in the other direction — `lif_fsm` at
12/12 DETECTED is strong evidence and not a proof, though it is backed
independently by the encoding argument and by `formal/lif_ctrl_props.v`.
Treat the *ordering* in section 6 as the result and the individual
percentages as indicative.

`evq_ptr` at 72/72 CORRECTED is the largest single-group sample in the
campaign and the rule of three still puts the one-sided 95% bound on the
missed rate at about 4%. It is also the group with the most independent
support: the vote is `tmr_voter.v`'s expressions verbatim, proven
exhaustively in `formal/tmr_voter.sby`, and `formal/aer_fifo_props.v`
re-proves the queue's four properties *under* a single-replica pointer
fault rather than beside it. The campaign result is the measurement that
the RTL the proofs describe is the RTL the design instantiates.

### 7.2 One workload, and only a second geometry

The campaign of record is 8 x 8 neurons/axons, EVQ depth 4, one
eight-command stimulus, weight seed 10. **Rates are conditional on that
stimulus**, and that is the limitation that has not been lifted: the
same eight commands drive every run, so nothing here says whether the
ranking survives a different spike train. A second workload remains the
single cheapest way to test that, and it has not been done.

A second **geometry** has now been run [fact].
`make -f Makefile.fi N_NEURONS=4 N_AXONS=8` completes with all five
tests passing. Pre-hardening it was 251 injections, **103 MASKED, 42
CORRECTED, 36 DETECTED, 70 SDC, 0 HANG** (27.9% SDC), and it
corroborated the section 6 ordering without reproducing the rates:
`rmem` 100%, queue pointers 95.8%, `vmem` 62.5%, the EVQ_OUT adapter
50%, `wmem` 25%. The top of the per-bit table was therefore not an
artefact of one elaboration; the exact percentages were.

**Re-run at wave 5 on 2026-08-29 [fact]:** 325 injections, **88 MASKED,
185 CORRECTED, 38 DETECTED, 14 SDC, 0 HANG** (4.3% SDC), 707 s wall, log
in `hw/tb/fi_campaign_results_4x8.json`. Every hardened structure held
again — 12/12 FSM DETECTED, 15/15 configuration TMR CORRECTED, **72/72
pointer TMR CORRECTED**, 12/12 ECC singles CORRECTED, 4/4 doubles
DETECTED, 0 SDC across every coded memory file — and both unread
controls came back MASKED. The residual is the same three structures as
at 8 x 8 and in the same order: the show-ahead adapter 5/14 (35.7%), the
dispatcher 4/18 (22.2%), the neuron scan 4/19 (21.1%), with queue
storage at 1/32. Two elaborations, two workloads, the same surviving
list.

Two caveats on that second geometry. It uses a **different weight seed**
(4, not 10), because the five workload constraints of section 1.4 are a
property of the resulting spike train and the 8 x 8 seed does not
satisfy them at 4 x 8 — so it is a different workload as well as a
different geometry, and the comparison is of orderings rather than of
numbers. And the injection count differs (325 against 335) because the
target list is built from the geometry: a 4-neuron scan index is one
bit narrower and there are fewer weight codewords to reach.

The geometry is followed automatically — the campaign reads
`CFG_NEUR`/`CFG_AXON` back and builds its target list and its golden
model from them — but the **workload is not**. The weight seed and the
per-burst busy windows are a table (`WORKLOAD` in
`hw/tb/test_fi_campaign.py`) with an entry for each geometry that has
been run; a geometry with no entry fails immediately with a message
saying so, rather than reporting numbers drawn against the wrong
windows. Adding one is a short offline search against the golden model
plus one measurement run, and the procedure is written down beside the
table.

The `lif_wmem_unread` control exists because the workload limitation
bites hardest there: the stimulus drives four of eight axons, so half
the crossbar is never read, and an evenly-sampled `wmem` rate would
have been a statement about the workload. It is fenced off, not solved.

### 7.3 The injection window does not cover the whole design

Deposits land inside the AER stimulus windows only. Four structures are
therefore untouched (152 FF); together with the EVQ_OUT drop counter,
which cannot increment by design, and four isolated control flops, they
made up the 164 flip-flops section 2 did not represent when this
section was written. A fifth entry was added on 2026-08-29 for a
different reason — the two bounded-wait counters were inside the window
and simply had no target — and **was closed on 2026-08-30**, which is
what section 5.8 reports. The list is back to the original four
structures, 152 FF, plus the isolated flops:

- **the serial shift engine** (80 FF) — live only during a serial frame.
  Reaching it needs the injection scheduled against the frame rather
  than against the event burst, which is a second injection procedure
  and was not built. An upset here corrupts one register access; the
  40-bit frame commits only on the last edge, so an aborted frame
  changes nothing, but a corrupted `cmd_addr` writes the right data to
  the wrong register. **Unmeasured.**
- **the input synchronizers** (26 FF) — an upset presents as a spurious
  or missing strobe edge, i.e. a fabricated or lost input event.
  **Unmeasured**, and structurally similar to the queue-pointer result.
- **the ECC weight loader** (`ld_*`, `ecc_commit`, `w_addr_cmt`, 12 FF)
  — live only during bring-up, before the injection window opens. An
  upset in `ld_k` or `ld_word_idx` writes a weight to the wrong synapse.
  **Unmeasured**, and it is the one gap with a clear path to closing:
  the injection would have to be scheduled during the weight load rather
  than during the stimulus.
- **the SYNC echo path and the EVQ_IN read register** (34 FF) — the
  workload contains no SYNC barrier, so half of this is untested by
  construction.
- ~~**the two bounded-wait counters**~~ (`fetch_wait` + `fetch_timeout`,
  `oh_wait` + `oh_timeout`, 14 FF, added 2026-08-29 to this list,
  **closed 2026-08-30**) — the structures that convert a silent hang
  into a reported one. This entry is kept struck through rather than
  deleted, because the prediction it made is worth comparing against
  what was measured. It said: an upset in `fetch_wait` or `oh_wait`
  "shortens or lengthens a wait that is otherwise never near its bound,
  which is harmless; an upset in either `*_timeout` flop fabricates an
  `ERR_CFG` the host cannot distinguish from a real one." Both halves
  held [fact] — 12 of 12 counter injections MASKED, 6 of 6 pulse
  injections a fabricated `ERR_CFG` with a golden output. **What the
  prediction missed is the other direction of the same flop:** an upset
  that *clears* the pulse in the one cycle it is high erases the report
  entirely, and the design then recovers from a real deadlock with a
  wrong answer and nothing flagged — SDC, not a false alarm. A random
  draw cannot find that cycle, which is why the closure needed
  constructed cases and not only 18 more phases. Section 5.8 has the
  measurement, the paired controls and the fix.

### 7.4 The fault model is single-bit, flip-flop only, at RTL

No multi-bit upsets, no single-event transients in combinational logic
(so the SECDED decoder, the TMR voter and the whole read multiplexer are
outside the model), no stuck-at faults, no latch-up. Injection is at RTL
with zero delay: there is no netlist campaign, no timing-aware
injection, and no cell-level sensitivity. The gate-level behaviour of a
deposit near a setup boundary is not represented at all.

**RTL-level fault injection cannot see synthesis-level structure loss,
and this is not a weakness of the harness — it is a property of where
the harness stands.** The campaign deposits into RTL signals. A
redundant structure that synthesis proves equivalent and deletes is
still three separate signals in the RTL simulation, so the campaign
measures the redundancy the designer wrote, not the redundancy the
netlist contains. Every "hardened structure held" result in section 4
therefore carries an implicit precondition: *provided the structure
exists in the netlist*. This is not hypothetical. The configuration TMR
domain was measured 15/15 CORRECTED here while the netlist that fed the
4x2 harden contained one physical bank instead of three (section 4,
correction dated 2026-08-26), and nothing in this campaign could have
revealed that — not a longer run, not more injections, not a better
oracle.

Two things close the gap, and only the second is mechanical:

- a **gate-level campaign**, which would see the loss but only if
  someone thought to attack that structure there. Not run; it is on the
  section 6 list.
- **`sw/tests/test_synthesis_guards.py`**, which runs both synthesis
  flows on every `pytest` invocation, counts the flip-flops in the
  mapped netlist per replica bank, and fails if any of them collapses.
  It also compares the whole design's declared flip-flop population
  against the mapped one, so a future redundant structure is covered
  the day it is added rather than the day someone remembers to check
  it. That test, not this campaign and not any synthesis attribute, is
  what keeps the section 4 preconditions true. It asserts on flip-flop
  *cells*: a `(* keep *)` attribute was measured to preserve the signal
  *name* in the netlist while the storage still merged, so any guard
  that greps for a signal name is satisfied by a design that has
  already lost the redundancy.

**There is a second implicit precondition, and it failed twice
[fact].** Every result in section 4 also assumes *the injector is aimed
at storage*. Twice now a hardening turned a register into a
continuously driven wire — the configuration replicas on 2026-08-26,
the queue pointers on 2026-08-29 — and twice the target list kept
naming the old signal, which still resolved and still produced numbers.
The configuration case was caught before it reported anything wrong; the
pointer case reported 23 SDC and zero corrections against a working TMR
for a day (section 3.3). Neither a longer run nor a better oracle would
have found either. What finds them is a criterion that names the target
*shape* rather than the outcome, which is why section 1.8's new clause
asserts that every pointer target path ends in a bank's storage register
and that every such injection is CORRECTED rather than merely not-SDC.
The general rule this campaign now works to: **when a hardening replaces
a register with a voted or decoded wire, the target list is part of the
change.**

### 7.5 This says nothing about rates

The campaign reports **conditional** probabilities — given that an upset
lands in structure X, what happens. It says nothing about how often an
upset lands in structure X, which needs a cross-section per bit and an
environment model. The 22.23 ms of simulated time is not an exposure
figure and must never be quoted as one. No upset-rate, cross-section or
total-dose claim can be derived from this document; those require beam
data this project does not have, and the positioning rules of docs/05
apply unchanged.

### 7.6 DETECTED depends on someone looking

Every DETECTED outcome assumes the host polls `STATUS` or watches the
fault pins. The pilot has no watchdog and no interrupt. A host that
never polls sees a HANG and a DETECTED identically: nothing. The four
dedicated fault pins (ERR, SEC, DED, TMR) are the mitigation and they
are why they exist, but they still need an observer.

This applies to the section 5.1 fix as much as to anything else. The
bounded `D_FETCH` wait converts a stuck part into a running part with
`ERR_CFG` latched and the ERR pin high — which is a large improvement
for a host that watches the pin and no improvement at all for a host
that does not. It also does not add the `STATUS.BUSY` watchdog that the
third option in section 5.1 would have; a hang from a structure this
campaign does not represent (section 7.3) would still present as a BUSY
that never falls, and nothing in the pilot would name it.

### 7.7 State-in-the-comparison is a choice

Counting a corrupted retained neuron state as SDC is a decision, and it
is what drives `vmem` and `rmem` to the top of the rate table. A
campaign that compared only the spike stream would report `lif_vmem` at
7/24 (29%) and `lif_rmem` at 3/12 (25%) instead of 92% and 100%. Both
numbers are in section 3 (the `stream` and `state` columns) so a reader
can take either view. The reason this document takes the stricter one:
the state is architecturally visible through `N_ADDR`/`N_DATA`, it is
the neuron's memory, and calling a corruption "masked" because the run
ended before it mattered is exactly the kind of claim this project's
review record punishes.

---

## 8. Running it, and where it sits

```
cd hw/tb && make -f Makefile.fi                  # 8 x 8, the campaign of record
cd hw/tb && make -f Makefile.fi N_NEURONS=4 N_AXONS=8
```

Both are verified working [fact]. Each geometry gets its own build
directory (`sim_build_fi_<n>x<a>_q<d>x<d>/`) and its own JUnit file
(`results_fi_<n>x<a>_q<d>x<d>.xml`), for the reason `Makefile.pilot`
already states: Icarus bakes the geometry defines into `sim.vvp` but
the cocotb rule only rebuilds when a source file is newer, so a shared
build directory makes a geometry change silently re-run the previous
elaboration. That was not hypothetical — before the build directory
carried the geometry, `make -f Makefile.fi N_NEURONS=4 N_AXONS=8`
immediately after an 8 x 8 run reproduced the 8 x 8 histogram, the
8 x 8 simulated time and the 8 x 8 log, and passed. The per-injection
log is likewise split: the 8 x 8 campaign of record keeps the
documented `hw/tb/fi_campaign_results.json`, and any other geometry
writes `hw/tb/fi_campaign_results_<n>x<a>.json` beside it rather than
over it.

The campaign is a **separate simulator target** and is not part of the
default cocotb sweep. Two reasons: it is the slowest suite in the
repository, and it deposits into internal state, so it must not share a
build directory or a results file with the functional suites. At 80 s
on an idle machine it is comfortably CI-affordable as its own job
[fact]. It is single-threaded and its wall time tracks host contention
directly — runs on the same machine took 79.5, 80.5, 81.1, 83.5, 84.5,
103 and 184 s as the load average went from near zero to 14 of 20 cores —
so a CI job should budget three minutes rather than ninety seconds. The
22.23 ms of simulated time is the machine-independent figure for
comparing hosts; the 4 x 8 geometry was 15.47 ms and about 58 s.

**Both of those cost figures are superseded and the direction is up
[fact].** The memory hardening put two SECDED decoders and an encoder in
the neuron core's per-cycle read path, and the wave-5 run adds 48
injections on top: the 335-injection campaign of section 3.4 took
**892 s of wall time for 28.77 ms of simulated time**, and the 325
injections at 4 x 8 took **707 s for 20.03 ms**, both on a machine
carrying a load average of about 12 of 20 cores throughout. A CI job
should budget twenty minutes, and the argument for keeping this suite
off the default sweep is correspondingly stronger.

The 365-injection run of section 3.5 took **567 s for 31.31 ms** [fact]
on a quiet machine. An identical run — same seed, same target list,
same 365 records — took **1769 s** earlier the same day with three
other simulator jobs on the host [fact]. Same measurement, same log,
3.1x the wall time. **Quote the 31.31 ms when comparing hosts and the
wall time never**; the 892 s and 674 s figures above carry the same
warning and are the reason the CI budget in this section is three
times the observed best case rather than equal to it. The directed
cases of section 5.8 are cheap either way —
`test_04_watchdog_directed` is 18 s of the 567, twelve injections that
each stall the design for 60 to 90 cycles — so closing the section 7.3
gap cost about 3% of the run.

One operational note learned on 2026-08-30 and worth writing down.
`hw/tb/sim_build_fi_8x8_q4x4/` and `hw/tb/fi_campaign_results.json` are
**shared, unlocked artifacts**: two concurrent invocations of this
target on the same machine will recompile `sim.vvp` under each other
(and if their `iverilog` versions differ, the second one's `vvp`
refuses to run the first one's output) and will overwrite each other's
log. There is no locking and there should not be one; the fix when it
matters is to pass a private build directory, which the cocotb
makefiles already support:

```
make -f Makefile.fi SIM_BUILD=$PWD/sim_build_fi_mine \
                    COCOTB_RESULTS_FILE=$PWD/results_fi_mine.xml
```

The JSON path is still shared, so check the record count and the seed
in the file before quoting it as the run you just started.

Relationship to the rest of the verification programme:

- `hw/tb/test_pilot_top.py` keeps the directed demonstrators. They are
  not redundant with this campaign: they check the *mechanisms* end to
  end through the Tiny Tapeout wrapper, including the recovery sequence
  and the register-map contract. This campaign checks *coverage*.
- `formal/` proves the properties that hold for all inputs. Section 5.1
  is a good illustration of the division of labour: `aer_fifo`'s
  refusal to read while empty is proven and correct, and the deadlock
  was in the consumer that assumed a read it requested would always be
  granted. The bounded wait that closes it is a liveness bound and no
  formal property asserts it; `test_pilot_top.py`'s regression test is
  the only thing that does, and it has been shown to fail without it.
- The per-injection log `hw/tb/fi_campaign_results.json` is the
  acceptance baseline for any later campaign — an FPGA saboteur run or a
  beam campaign inherits this target list, these classes and this seed,
  and any structure whose measured behaviour disagrees with this file is
  a finding. It now holds the 365-injection safety-net run; the earlier
  numbers survive in this document, in the headline, in sections 3.1 to
  3.5, in the section 5.1 table of the five records that changed, in
  the section 3.4 table of the one that changed at wave 5, and in
  section 3.5's statement that none of the 335 changed at all this
  time.
- `hw/tb/test_fi_campaign.py`'s `test_04_watchdog_directed` is the one
  test in this file that does not draw its phases. It constructs a
  fault and an upset in the structure meant to catch it, placed against
  each other cycle by cycle, because the case that matters is one cycle
  wide and a rate cannot reach it (section 5.8). Its multi-step deposits
  are logged with the popcount of every write, so a reader can see at a
  glance which of them are single-event upsets and which are
  constructions outside the section 7.4 fault model.

### Notes for the integrator

- **Resolved 2026-08-26.** `hw/tb/fi_campaign_results.json` was
  committed as evidence, which was this section's recommendation, and
  `hw/tb/fi_campaign_results_4x8.json` with it. Both are tracked and
  neither is in `.gitignore`. The consequence, stated so it is not
  discovered later: the log is a versioned artifact now, so a campaign
  re-run shows up as a diff, and *that diff is the measurement*. The
  memory hardening of 2026-08-26 is legible in git history as 43 records
  changing class in that file and nothing else moving.
- `hw/tb/results_fi_*.xml` and `hw/tb/sim_build_fi_*/` are already
  covered by the existing patterns; no change needed. The unsuffixed
  `results_fi.xml` and `sim_build_fi/` of the first revision are no
  longer produced and can be deleted from a working tree that has them.
- **Resolved 2026-08-26, the other way.** `hw/tb/Makefile` now reads
  `TB_FRAGMENTS := regbank lif secded tmr pilot scrub fi`, so `make
  TB=fi` works. This section had argued against adding it; the argument
  was about the *default sweep*, and the dispatcher is not the default
  sweep — `make TB=fi` is an explicit goal, which is exactly the
  condition the argument allowed. The thing to keep true is that a bare
  `make` in `hw/tb` must not pull the campaign in. It does not.
  The cost figure that argument used has moved, and by a lot. The
  campaign was 80 s when this was written; after the memory hardening
  put two SECDED decoders and an encoder in the neuron core's per-cycle
  read path, the same 255 injections take **674 s** on this machine
  (section 8). That makes the case for keeping it off the default sweep
  stronger than it was, not weaker.
- ROADMAP: this closes the fault-injection half of the wave-3 work item
  and is evidence for the G1 verification bar. No ROADMAP edit was made
  from this track.
