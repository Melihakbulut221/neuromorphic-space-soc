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
| Injections | 255 |
| Simulated time | 22.23 ms |
| Wall time | 79.5 s to 84.5 s on an otherwise idle machine; 103 s and 184 s on the same machine under concurrent load (Icarus 12, single-threaded) |

### Two runs, before and after one RTL fix

This document reports the campaign **twice**, and the two runs are kept
side by side rather than one overwriting the other.

- The **pre-fix** run is the measurement that found the deadlock of
  section 5.1. It is the evidence that motivated the change and it is
  reported here unaltered.
- The **post-fix** run is the same campaign — same seed, same target
  list, same workload, same 255 injections — against
  `hw/rtl/pilot_top.v` with the bounded `D_FETCH` wait of section 5.1
  in place. Every number in this document is labelled with which run it
  comes from. Where a section is not labelled the two runs agree.

`hw/tb/fi_campaign_results.json` holds the **post-fix** log, because
that is the design that exists. Exactly five of the 255 records differ
between the two runs and section 5.1 lists all five.

**Headline, pre-fix [fact].** 255 single-bit injections: **83 MASKED
(32.5%), 42 CORRECTED (16.5%), 34 DETECTED (13.3%), 91 SDC (35.7%),
5 HANG (2.0%)**.

**Headline, post-fix [fact].** The same 255 injections: **83 MASKED
(32.5%), 42 CORRECTED (16.5%), 39 DETECTED (15.3%), 91 SDC (35.7%),
0 HANG**. All five HANG outcomes became DETECTED and nothing else moved
— not one MASKED, CORRECTED or SDC record changed class, and the SDC
rate is unchanged at 35.7%. The fix removes the failure class it was
written for and buys nothing else, which is what it should do.

In both runs every hardened structure kept its promise with zero
counterexamples — the neuron-core FSM (12/12 detected), the
configuration TMR domain (15/15 corrected and counted), the SECDED
weight word (12/12 singles corrected, 4/4 doubles detected, E10
substitution exact on every event stream it produced). Every silent
corruption came from a structure the pilot never claimed to protect.
The ranking of those, and the previously unknown deadlock in the event
dispatcher, is the result that matters.

---

## 1. Method

### 1.1 What was adapted, and what was not

The method comes from the sibling programme's campaign
(`/home/hasanmelih/Documents/radhard-edge-ai`, its `docs/27`, its
`hw/tb/test_fi_campaign.py`, and the harness lessons in its `docs/25`
section 3). Four things were taken directly:

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

`test_04_summary` additionally fails if the campaign shrinks below 200
injections, if any FSM injection is not DETECTED, if any single TMR
replica upset is SDC, if any single-bit weight-word upset is not
CORRECTED, or if any double-bit weight-word upset is not DETECTED.

---

## 2. Coverage

Flip-flop counts below are **counted from the RTL declarations** at the
8 x 8 geometry, not from a synthesised netlist [fact for the counts,
estimate for their mapping to silicon area].

"Represented" means the campaign sampled that structure, not that it
injected into every bit of it — 255 injections cannot cover 996
flip-flops, and wide registers are sampled at low, middle and high bit
positions by design (section 1.1). The percentage below says how much of
the design the map speaks about, not how exhaustively.

| Structure | Group | FF | Injections |
|---|---|---:|---:|
| Synapse weight file, `lif_core.wmem` | `lif_wmem` (+ unread control) | 256 | 20 |
| Configuration TMR replicas, `cfg_a/b/c` | `cfg_tmr_a/b/c` | 165 | 15 |
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
| **Total represented** | | **996** | **255** |

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

---

## 3. Measured distribution

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

---

## 4. What held

Every mechanism the pilot claims was exercised and none produced a
counterexample. These are the campaign's positive results and they are
the reason the negative ones below are worth acting on rather than
worth panicking about.

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

Three of the five also produced the golden event stream and the golden
neuron state after recovering, so for those the fix converted a wedged
part into a correct answer plus a flag. The other two recovered and
still had a corrupted output — the upset had already damaged the run —
which is why they are DETECTED-with-wrong-output and not CORRECTED. A
bounded wait is a recovery, not a repair, and this document does not
claim otherwise.

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

### 5.2 AER queue pointers are the highest-rate silent corruptor — 22/24 SDC

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

### 5.3 The neuron state file is unprotected, and its corruption persists

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

### 5.7 The show-ahead adapter and the neuron scan

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

---

## 6. Ranking for the next hardening wave

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
   changes nothing else (section 5.1). Items 2 to 6 below are still
   open.
2. **TMR the four AER queue pointers.** 12 FF, top-three per-bit rate,
   `tmr_voter.v` already verified and proven, and the corruption it
   removes is the kind no consumer can detect (fabricated and duplicated
   spikes).
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
They cost 165 FF for the configuration TMR domain, 72 FF for the ECC
word plus the SECDED codec, and **one** extra state bit for the
neuron-core FSM encoding — `lif_core` has five states, which a plain
binary encoding would hold in 3 bits, and the Hamming-distance-2
even-parity encoding holds in 4 (an earlier revision of this section
said two). Across this campaign they were **50 for 50** — 12 FSM,
15 TMR replica, 12 ECC single, 4 ECC double, 7 scrub — with not one
silent corruption between them. They are the reason the design has a
story at all, and the list above is what it would take to make the rest
of the block deserve the same sentence.

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

### 7.2 One workload, and only a second geometry

The campaign of record is 8 x 8 neurons/axons, EVQ depth 4, one
eight-command stimulus, weight seed 10. **Rates are conditional on that
stimulus**, and that is the limitation that has not been lifted: the
same eight commands drive every run, so nothing here says whether the
ranking survives a different spike train. A second workload remains the
single cheapest way to test that, and it has not been done.

A second **geometry** has now been run [fact].
`make -f Makefile.fi N_NEURONS=4 N_AXONS=8` completes with all five
tests passing: 251 injections, **103 MASKED, 42 CORRECTED, 36 DETECTED,
70 SDC, 0 HANG** (27.9% SDC), log in
`hw/tb/fi_campaign_results_4x8.json`. It corroborates the section 6
ordering without reproducing the rates: `rmem` 100%, queue pointers
95.8%, `vmem` 62.5%, the EVQ_OUT adapter 50%, `wmem` 25%. Every
hardened structure held again — 12/12 FSM DETECTED, 15/15 TMR
CORRECTED, 12/12 ECC singles CORRECTED, 4/4 doubles DETECTED — and the
`lif_wmem_unread` control came back 4/4 MASKED. The top of the per-bit
table is therefore not an artefact of one elaboration; the exact
percentages are.

Two caveats on that second run. It uses a **different weight seed**
(4, not 10), because the five workload constraints of section 1.4 are a
property of the resulting spike train and the 8 x 8 seed does not
satisfy them at 4 x 8 — so it is a different workload as well as a
different geometry, and the comparison is of orderings rather than of
numbers. And the injection count differs (251 against 255) because the
target list is built from the geometry: a 4-neuron scan index is one
bit narrower.

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
make up the 164 flip-flops section 2 does not represent:

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

### 7.4 The fault model is single-bit, flip-flop only, at RTL

No multi-bit upsets, no single-event transients in combinational logic
(so the SECDED decoder, the TMR voter and the whole read multiplexer are
outside the model), no stuck-at faults, no latch-up. Injection is at RTL
with zero delay: there is no netlist campaign, no timing-aware
injection, and no cell-level sensitivity. The gate-level behaviour of a
deposit near a setup boundary is not represented at all.

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
comparing hosts; the 4 x 8 geometry is 15.47 ms and about 58 s.

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
  a finding. It now holds the post-fix run; the pre-fix numbers survive
  in this document, in the headline, in section 3 and in the section 5.1
  table of the five records that changed.

### Notes for the integrator

- `hw/tb/fi_campaign_results.json` is a generated artifact of the
  campaign. `.gitignore` (integrator-owned) currently covers
  `hw/tb/sim_build*/` and `hw/tb/results_*.xml` but not this file. It
  should either be committed as evidence — which is what the sibling
  programme does with its equivalent, and what section 8 above assumes
  when it calls the log an acceptance baseline — or added to
  `.gitignore`. Committing it is the recommendation.
  `hw/tb/fi_campaign_results_4x8.json`, the alternate-geometry log,
  falls under whichever decision is taken; it is evidence of the same
  kind but not the acceptance baseline.
- `hw/tb/results_fi_*.xml` and `hw/tb/sim_build_fi_*/` are already
  covered by the existing patterns; no change needed. The unsuffixed
  `results_fi.xml` and `sim_build_fi/` of the first revision are no
  longer produced and can be deleted from a working tree that has them.
- `hw/tb/Makefile` (the `TB=<block>` dispatcher, not owned by this
  track) lists `TB_FRAGMENTS := regbank lif secded tmr pilot`. Adding
  `fi` to that list would make `make TB=fi` work alongside the other
  suites and would be consistent with the docs/11 section 2 convention.
  It was deliberately **not** added here, because the campaign should
  stay off the default sweep: at 80 s it is six times the LIF sweep
  (14.2 s), which is the next slowest suite in the repository. If it is
  added, it should be as an explicit goal, never as part of a bare
  `make`.
- ROADMAP: this closes the fault-injection half of the wave-3 work item
  and is evidence for the G1 verification bar. No ROADMAP edit was made
  from this track.
