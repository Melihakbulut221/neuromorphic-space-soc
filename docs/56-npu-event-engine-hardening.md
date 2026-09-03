# 56 — Splitting the event engine, and hardening the nine bits that carried it

`docs/55-npu-connection-hardening.md` section 14 named the event engine
as the next block and attached a condition that was not optional: **split
its 140-bit stratum first, so the campaign can say which structure inside
it carries the rate.** This document does that, reports what the split
showed — which is not what the ranking predicted — builds the two things
the measurement points at, and re-runs the campaign against them.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
an intention with nothing behind it yet.

**The pilot is untouched.** `docs/34` pins the TTIHP26b submission by git
blob hash and the shuttle closes 2026-09-21. Nothing in `hw/rtl/`,
`hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is modified; seven files in
`hw/rtl/` are **read and instantiated**, `hw/soc/flow/fi_npu.sh` still
refuses to elaborate if `git diff` over `hw/rtl/` is not empty, and
`sw/tests/test_soc_npu_guards.py` checks the blob hashes **[fact]**.
Section 13 lists every file touched.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| What did the split show? | **The engine's rate is in its STROBES and not in its data, and 96 % of it is in NINE of its 140 flip-flops** **[fact]**. `ev_data` — 64 bits, the largest sub-stratum by a factor of three — came back **0 of 100**, and `ev_cnt`'s 32 bits came back 0 of 100 as well. Section 3 |
| Which single bit was worst? | **`aer_in_stb`, at 18 silent wrong inferences in 18 draws** — the highest per-bit rate in any campaign this block has had, on **one flip-flop**, and the whole of its sub-stratum's contribution. Section 3.3 |
| Was the split honest? | **Yes, and the harness proves it rather than asserting it.** The six strata the split did not touch came back **identical, row for row and record for record**, to `docs/55`'s campaign of record. Section 3.1 |
| What was built? | **Two things, and between them they cost 15 flip-flops.** H4 bounds the show-ahead adapter's read of the capture queue; H5 gates the AER strobe with the FSM state that already implies it. Sections 5 and 6 |
| Did the campaign find something a campaign had not? | **Yes: a permanent stall no injection in `docs/52` or `docs/55` reached.** One discarded capture-queue entry — `aer_fifo`'s own documented behaviour, no upset required in the adapter — left `oh_req` set for ever, so the block never delivered another event while `IRQ_CAUSE.EVT` went on saying one was waiting. **Measured in simulation both ways in.** Section 5.1 |
| What did H5 cost? | **No flip-flop at all: +22 cells and 159.0246 um2, at an identical flip-flop count** **[fact]**, measured by removing the gate and re-synthesising. The redundancy it uses was already in the netlist and was not being read. Section 7 |
| And the whole wave? | **+15 flip-flops and 1,471.3650 um2 on the connection** against the same design at `4b77af1`, same file list, same recipe **[fact]**. 0.53 % of the unprotected Ibex core. Section 7 |
| Is the whole-SoC invariant still 215,428 cycles? | **Yes, exactly, and this wave is RTL-only so there is no second number** **[fact]**. `docs/55` had to measure three because it changed the program as well; this one changes no software, so the clean run, the measured injection window and the invariant are all unmoved. Section 8.4 |
| Did it move the number it was built to move? | **`ev_pin` is 18 silent wrong inferences in 100 to 0, and 17 of the 18 draws into `aer_in_stb` now return the golden inference with a named cause bit** **[fact]**. `oh_req` is 3 of 4 to 0 of 4. Sections 8.2 and 8.3 |
| Does the delta survive calibration? | **Yes, and for the first time in this block the calibration is exact rather than an argument.** On 1,000 verbatim replayed injections **exactly one record changed its verdict**, and it is in a stratum this work touched: the frozen die's 100 records, 400 more in untouched strata and 200 more inside the split stratum all come back **unchanged, record for record**. `docs/55` had to refuse a 19 % claim because its frozen die moved on 15 of 100; this one moves on none. Section 8.2 |
| What was left, and why | **`ev_state` (7 of 20), `cap_wr_en` (5 of 8) and `oh_valid` (2 of 4)** — 6 bits, ranked, priced and not built. Section 11 says what each would cost and why none of them is this wave. |
| Did anything get worse? | **Yes, in two named places.** H5 masks and does not correct, so an upset in `ev_state` inside a legal strobe now **loses a real event** where it used to pass one — one of the eighteen `aer_in_stb` draws is that case. And it adds three unprotected flip-flops, whose corruption is benign for a reason that is argued rather than measured. Sections 6.2, 6.4 and 8.3 |
| What did the split cost? | **A whole extra campaign**, and `docs/55`'s "half a day on `npu_targets.py`" was right about the edit and wrong about the work: a stratification that is not re-run is a re-labelling. Sections 8.5 and 12 |

---

## 2. The precondition, and why `docs/55` made it one

`docs/52` section 6.2 attributed **1.71 of the connection's 4.17 points**
of silent corruption to a stratum called `engine`: 140 flip-flops holding
the event FSM, the word in flight, the AER pin drivers, two counters and
the show-ahead adapter. That is enough to rank a block and not enough to
build in one, and `docs/55` section 14 item 1 said so:

> **The reason to wait is that the campaign cannot currently say which of
> the engine's structures carries the rate** — `ev_state`, the AER pin
> drivers, the two counters and the show-ahead adapter are one stratum of
> 140 bits … Splitting that stratum is a half-day of work on
> `npu_targets.py` and it decides what to build.

**The reason that is not a formality is measured twice already in this
repository.** `docs/52` section 6.3 found `evq_data` at **41.2 % of the
connection's flip-flops and zero of its rate**, and `docs/55` section 6.2
had to write a test whose only job is to keep that argument in the file,
because the instinct it contradicts is to protect the biggest thing.
A stratum is the unit at which that mistake is possible: **inside an
undifferentiated stratum, the biggest structure is invisible.**

Section 3 is what happened when this one was opened.

---

## 3. The stratification, and what it showed

### 3.1 The split, and the control it comes with

`hw/soc/fi/npu_targets.py` now draws the engine as **five strata**, at
the module's own boundaries. **No site moved, no width changed, and the
five sum to the same 140 bits** —
`test_the_engine_split_is_a_partition_of_the_stratum_it_replaced` asserts
that against a copy of `docs/52`'s own list rather than trusting it.

| stratum | bits | share of the engine | what it is |
|---|---:|---:|---|
| `ev_seq` | 19 | 13.6 % | the sequencer: `ev_state`, `ev_wait`, and the strobes and address it drives |
| `ev_data` | 64 | 45.7 % | the event word in flight: `ev_word`, `ev_wdata`, `cap_wr_data` |
| `ev_cnt` | 32 | 22.9 % | `cnt_in` and `cnt_out` |
| `ev_pin` | 6 | 4.3 % | `aer_in_stb`, `aer_in_tick`, `aer_in_addr` |
| `ev_oh` | 19 | 13.6 % | the show-ahead adapter: `oh_valid`, `oh_data`, `oh_req`, `cap_rd_en` |

**[fact, `python3 hw/soc/fi/npu_targets.py`]**

The campaign was then re-run at **`4b77af1`'s RTL, unchanged** — 1,100
injections, eleven strata of 100, each run twice **[fact,
`hw/soc/out/h56-split/`]**. That build is the split baseline and it is
also its own control, because `draws()` seeds per `(stratum, index)`
rather than from one stream:

> **THE SIX STRATA THE SPLIT DID NOT TOUCH CAME BACK IDENTICAL TO
> `docs/55`'s CAMPAIGN OF RECORD, ROW FOR ROW** **[fact]**: `ser`
> 83/0/0/17/0, `window` 93/0/0/7/0, `cfgreg` 6/0/0/94/0, `evq_data`
> 100/0/0/0/0, `evq_ptr` 10/6/0/84/0 and the frozen `die_ser` 91/0/0/9/0,
> in the five classes, with the same silent-wrong-inference counts —
> 6, 1, 0, 0, 0 and 6.

That is the strongest form of the check `docs/55` had to make with an
argument: **the split changed the label on 100 records and nothing else,
and the harness demonstrates it rather than promising it.**

### 3.2 The result, and it is not what the ranking predicted

Silent wrong inference — the golden **model** says the answer is wrong
and **no hardware channel** announced it, which is `docs/52` section
6.2's definition and is now printed by the campaign rather than computed
by hand:

| stratum | bits | n | silent | 95 % Wilson |
|---|---:|---:|---:|---|
| `ev_pin` | **6** | 100 | **18** | 11.7 – 26.7 % |
| `ev_seq` | 19 | 100 | **13** | 7.8 – 21.0 % |
| `ev_oh` | 19 | 100 | **6** | 2.8 – 12.5 % |
| `ev_data` | **64** | 100 | **0** | 0.0 – 3.7 % |
| `ev_cnt` | **32** | 100 | **0** | 0.0 – 3.7 % |

**[fact, `hw/soc/out/h56-split/campaign.log` section 3b]**

> **NINETY-SIX BITS OF THE ENGINE'S HUNDRED AND FORTY — 68.6 % OF IT —
> PRODUCED NOTHING IN TWO HUNDRED DRAWS.** `ev_data` is the largest
> sub-stratum by a factor of three and `ev_cnt` is the second largest,
> and between them they are the whole of what a wave that started with
> the biggest structure would have protected.

`ev_cnt`'s zero is a different zero from `ev_data`'s and the difference
matters. **Every one of its 100 draws classified DETECTED — 97 of 100,
with 3 MASKED** — because `fi_npu.c` cross-checks `NPUCFG.CNT` against
the stream it collected, which is `docs/52` section 11.3's finding
standing up under a hundred draws instead of fifteen: *"that detection is
entirely a property of the software."* **The counters are not safe. They
are watched, by a program, and by nothing in this design.** A driver that
read `CNT` to decide how many events to expect would be reading a
corrupted number with nothing to say so, and `docs/52` section 11.3 is
still the record of that.

### 3.3 Per site, which is where the answer actually is

The stratum table understates the finding, because `ev_pin` is six bits
of which five contribute nothing:

| site | bits | silent / draws | rate |
|---|---:|---:|---:|
| **`aer_in_stb`** | **1** | **18 / 18** | **100 %** |
| `oh_req` | 1 | 3 / 4 | 75 % |
| `cap_wr_en` | 1 | 5 / 8 | 62.5 % |
| `oh_valid` | 1 | 2 / 4 | 50 % |
| `ev_state` | 4 | 7 / 20 | 35 % |
| `inj_rd_en` | 1 | 1 / 4 | 25 % |
| `oh_data` | 16 | 1 / 85 | 1.2 % |
| `ev_wdata`, `aer_in_addr`, `ev_addr`, `cnt_in`, `cnt_out`, `cap_wr_data`, `ev_word`, `ev_wait`, `aer_in_tick`, `cap_rd_en`, `ev_we`, `ev_start` | 123 | **0 / 373** | **0 %** |

**[fact]**

Weighting each site's measured rate by its width gives the engine's own
figure — **4.713 bit-equivalents of 140, 3.37 % of the stratum, 0.58
points of the connection's 809 bits** **[estimate, arithmetic on measured
rows]** — and the six sites above `oh_data` are **4.525 of those 4.713,
which is 96.0 %, in nine flip-flops** **[estimate]**.

> **THE RATE IS IN THE STROBES AND NOT IN THE DATA.** Every site in the
> engine that carries anything is a one-bit control flag or the four-bit
> state that drives them. Every site that holds a *value* — the event
> word, the serial write data, the capture write data, the AER address,
> the register address, both counters — carries nothing measurable.

**`aer_in_stb` is 18 of 18 and the mechanism is one sentence.** The flag
drove the frozen die's `AER_IN_STB` pin on its own, so an upset that set
it while the engine was idle strobed a **phantom SPIKE or TICK** into the
die with whatever `aer_in_addr` and `aer_in_tick` happened to hold. The
die has no way to know it was not asked for: it accepts the event,
integrates it, and the inference comes out wrong. Nothing in the SoC
counted it — `cnt_in` does not move, because the SoC does not think it
sent anything — so the hardware's own cross-check cannot see it either.

**And it explains why the sub-stratum table hid it.** `ev_pin` is six
bits; `aer_in_addr` is four of them and `aer_in_tick` a fifth, and both
came back 0 of 82 draws between them, because a corrupted address on a
strobe that is not happening reaches nothing. The stratum's 18 % is one
bit at 100 % and five bits at zero.

### 3.4 Two things the split cost, stated

**The engine's contribution moved and the reason is the estimator, not
the design.** `docs/52` drew 100 injections proportionally over 140 bits
and got 9, which weights to 1.71 points; the split draws 100 into each of
five sub-strata and weights each by its own width, which gives **0.58
points** **[estimate]**. The design did not change between those two
numbers — `docs/55`'s campaign of record measured the same unsplit
stratum at 8 of 100 — and neither figure is wrong. **A stratified
estimator over five populations of very unequal size is a different
estimator**, and it is the better one here precisely because the rate is
concentrated in the small populations, which proportional sampling
under-visits. `docs/42` section 4.1 makes that argument for stratifying
at all and this is the same argument one level down.

**It cannot be compared record by record against `docs/52`.** The site
list is identical, so the *sites* are comparable; the draws are not,
because a stratum's seed string is its name. Section 8 is a replay
against the split baseline for exactly this reason.

---

## 4. What was built, and what was not

The measurement ranks six sites. Two were built.

| | site | measured | built | why |
|---|---|---|---|---|
| **1** | `aer_in_stb` | 18 / 18 | **H5**, section 6 | the worst site in the block and the answer costs no flip-flop |
| **2** | `oh_req` | 3 / 4 | **H4**, section 5 | and it closes a permanent stall no campaign had reached |
| **3** | `ev_state` | 7 / 20 | no | section 11 item 1 |
| **4** | `cap_wr_en` | 5 / 8 | no | section 11 item 2 |
| **5** | `oh_valid` | 2 / 4 | no | section 11 item 3 |
| **6** | `inj_rd_en` | 1 / 4 | no | section 11 item 4 |
| — | `ev_data`, `ev_cnt` | 0 / 200 | **nothing, deliberately** | section 3.2 |

**THE ORDER THEY WERE BUILT IN IS NOT THE ORDER THEY ARE RANKED IN, AND
THIS DOCUMENT SAYS SO RATHER THAN TIDYING IT.** H4 was built first,
before the split campaign finished, on the strength of `docs/55` section
8.6's surviving SDC and a reading of the RTL. That reading turned out to
be right about a defect the campaign had never reached (section 5.1) and
wrong about the ranking: `oh_req` is the *third* worst bit in the engine,
not the first. The measurement then named `aer_in_stb`, and H5 was built
after it. **The document that reported only the final order would be a
document whose method could not be checked**, which is `docs/55` section
4.3's rule applied to the sequence of work rather than to a bound.

---

## 5. H4: the show-ahead adapter's read is bounded

### 5.1 The defect, which is not only a radiation one

`soc_npu.v`'s show-ahead adapter is `pilot_top.v` section 8's convention
C9: `aer_fifo` presents its data one cycle after an accepted read, and
the register view of `EVQ_OUT` is a single-access pop, so a one-entry
holding register closes the gap. `oh_req` says a read is in flight. Until
this document the file said:

> *"A read whose entry fails its parity check returns no `rd_valid`;
> `oh_req` simply stays set until the next entry arrives, and the queue's
> own level tells software the difference."*

**That sentence is false, and it is false in the one direction that
matters.** `oh_req` is cleared by `cap_rd_valid` and by nothing else, and
the refill condition requires `!oh_req`. So a read that produces no
`rd_valid` leaves `oh_req` set **for ever**: no further `cap_rd_en` is
issued, every later event is stranded in the capture queue, and
`cause[C_EVT]` goes on reporting that an event is waiting because it
reads `!cap_empty`. **A driver polling `EVQ_OUT` polls for ever.**

**THE ANSWER WAS ALREADY WRITTEN DOWN IN THIS FILE'S OWN HEADER AND HAD
BEEN APPLIED TO THE OTHER QUEUE.** `soc_npu.v` section 4 says of the
injection queue:

> *"What it does need is a BOUNDED WAIT, because `aer_fifo` may
> legitimately answer a read with nothing — an entry whose stored parity
> fails is DISCARDED and `rd_valid` is held low. A fetch that never
> returns would hang the engine, so it expires, counts, and reports."*

The engine's `E_FETCH` does exactly that and has since `docs/51`. The
adapter reads the same queue type with the same contract and had no
bound at all.

**IT IS MEASURED, TWICE, AND ONE OF THE TWO NEEDS NO UPSET IN THE
ADAPTER.** Both are now regression tests in
`hw/soc/tb/cocotb/test_soc_npu.py` and both failed against the design
`docs/55` shipped **[fact]**:

| how it is reached | what was measured before H4 |
|---|---|
| one upset that **sets `oh_req`** while the adapter is idle | the next barrier never came back in 2,000 polls; `IRQ_CAUSE` = `0x01` (EVT), `cap_empty` = 0, `oh_req` = 1, `cap_rd_en` = 0 **[fact]** |
| one capture-queue entry whose **stored parity fails** — `aer_fifo`'s own documented discard, no upset in the adapter at all | three later barriers never came back; `IRQ_CAUSE` = `0x401` (EVT and Q_DET), `cap_level` = 2, `oh_req` = 1 **[fact]** |

> **THE SECOND ONE IS A DESIGN DEFECT AND NOT A RADIATION FINDING.** It
> is reachable from `evq_data` — the 304-bit stratum both `docs/52` and
> `docs/55` measured at zero and deliberately left alone.

**AND NO CAMPAIGN REACHED IT, WHICH IS WHY IT SURVIVED THREE OF THEM.**
Over `docs/52`'s 700 injections, `docs/55`'s 700 and this document's
split baseline's 1,100 — **2,500 in all** — the mechanisms that produce a
read with no `rd_valid` fired eight times **[fact, all three
`records.csv`]**:

- **two entry-parity discards, both in the INJECTION queue** (`inj_mem5`
  and `inj_mem3`, `docs/52`), where the engine's `E_FETCH` bound catches
  them and where they are not this failure at all;
- **five `rd_valid` rail disagreements**, of which three are in the
  capture queue (`cap_rdv_b`) — and all three in the direction that
  raises a rail **spuriously**, so `rd_valid = rdv_a && rdv_b` stays low
  and no read is lost. All three came back with `fi_mask` = `0x10`,
  telemetry only, and **the golden inference** **[fact]**.

**Zero of 2,500 landed on the direction that wedges.** `docs/52` section
13's caveat about one workload, one stimulus and one seed is not an
abstract one here: reading the RTL found this and 2,500 injections did
not.

### 5.2 The bound

`aer_fifo` registers `rd_valid` from `rd_en && !empty`, so a healthy read
raises `cap_rd_valid` exactly one cycle after `cap_rd_en` and `oh_req` is
set for exactly two cycles. The bound is derived from that and not
written down:

```
OH_WAIT    = 1 (the cap_rd_en cycle) + 1 (the rd_valid cycle) = 2
OH_MAX     = OH_WAIT + OH_SLACK                               = 4
OH_GUARD_W = width(OH_MAX)                                    = 3
```

**[fact]**. Four things about it are decisions.

**The comparison is `>=` and not `==`**, which is `docs/55` section 4.2's
rule and is checked for all three of this block's guards by
`test_the_frame_bound_expires_on_greater_or_equal_and_not_on_equal`.

**On expiry it clears `oh_req` and does nothing else.** No read is issued
and `oh_valid` is not touched. A version that issued the read itself
would pop a second entry while the first was in flight; a version that
also cleared `oh_valid` would drop the word the adapter is holding.

**The report is one sticky cause bit, `IRQ_CAUSE.OH_TO`, and there is no
`BUSSTAT` counter behind it.** That is a decision against the pattern
`docs/55` section 5 established, and the reason is that document's own
section 14 item 2: `BUSSTAT` is now **126 unprotected flip-flops whose
whole job is to be believed**, and a fourth NPU counter would be eighteen
more of them for an event no recovery policy yet acts on. Section 12
carries the exposure that leaves.

**The guard's own corruption is benign**, and unlike `docs/55`'s two
guards that is provable rather than measured. Section 6.4.

---

## 6. H5: the AER strobe, gated by the state that implies it

### 6.1 The redundancy was already in the netlist

`aer_in_stb` is set on the edge out of `E_PIN_A`, cleared on the edge out
of `E_PIN_S`, and the flush path clears it in the same statement that
returns `ev_state` to `E_IDLE`. So

```
aer_in_stb == (ev_state == E_PIN_S)
```

**is an invariant of this FSM**, and the flag is a **redundant encoding
of a state the module already holds**. It was not being used as one: the
flag drove the die's pin alone.

The pin is now `aer_in_stb && (ev_state == E_PIN_S)`, and a disagreement
raises `IRQ_CAUSE.AER_MM`. **A spurious strobe now needs two coincident
upsets — one in the flag and one in `ev_state`, in the same cycle,
landing on the right encoding — where it needed one.**

**IT COSTS NO FLIP-FLOP, AND THAT IS MEASURED RATHER THAN ASSERTED.**
Section 7: removing the gate and re-synthesising gives **the identical
flip-flop count and 22 fewer cells** **[fact]**.

**Three alternatives were considered and each is rejected for a stated
reason.**

**Driving the pin from `ev_state` alone** would also mask an upset in the
flag — by deleting the flag, which the optimiser would then do — and it
is *simpler*. It is rejected because it moves the whole exposure into
`ev_state`, which the split measured at **7 of 20**, and because it
reports nothing. This keeps both registers and requires both.

**Tripling the pin bundle** — `aer_in_stb`, `aer_in_tick`, `aer_in_addr`
concatenated into a 6-bit word under `soc_tmr_bank` — would *correct*
rather than mask, and would cover the address and type pins as well. It
costs **12 flip-flops and a restructure of the FSM's registered outputs
into a combinational next-value function**, which is exactly the refactor
`docs/41` section 6.5 records crediting to a hardening once. It is
rejected for this wave because the address and type pins measured **0 of
82** and because H5 gets the one bit that matters for nothing. Section 11
item 5 is what it would still buy.

**Tripling the flag alone is impossible.** `hw/rtl/pilot_top.v` section
8.2 proves three replicas cannot be held apart over one bit and `docs/30`
section 3.3 gives the general statement — three bits is the first width
at which a third replica has a function left to take. Naive replication
would give a netlist with one flip-flop and a voter voting it against
itself, and every test in this repository would still pass. That bound is
why the alternative above is a *bundle*.

### 6.2 It detects and does not correct, and the difference is named

On a disagreement the pin is held **quiet**. That is the right answer
when the **flag** was corrupted, which is 18 of 18 of the measured draws,
and it **loses an event** when `ev_state` was — and this module cannot
tell which. `IRQ_CAUSE.AER_MM` says the inbound event path took an upset
and does not claim to say more.

This is `hw/rtl/aer_fifo.v`'s dual-rail `rd_valid` pattern with the
second rail being state that exists for another reason. That file's own
header calls the rd_valid flag *"the design's most dangerous small
state"* and answers it with detection rather than correction, for the
same reason: **two rails cannot vote.**

### 6.3 What the two reports cost, and why they are two bits

`NCAUSE` goes 12 → 14 and `PROT_W` 21 → 25, which is **12 flip-flops** —
three replicas of a sticky bit and a mask bit each — and that is 80 % of
this wave's whole flip-flop cost. It is paid because a bound that fires
and tells nobody is `docs/16` section 5.1's original defect, and because
`docs/55` section 6.1's argument applies unchanged: the report belongs
**inside** the protected word, so the write that records the event and
the write that survives it are the same write.

**They are two bits and not one.** `OH_TO` says the SoC's **output** path
stalled and recovered; `AER_MM` says a **phantom input event** was
suppressed on its way into the die. Different parts, different
directions, and a mission reading one is not reading the other.
`pilot_top.v`'s own header records what folding two correction sources
cost it — *"a host reading `CNT_SEC` cannot tell a synapse array
correction from a load-path one"* — and `docs/44` section 6.2 and
`docs/55` section 5 both make the same argument.

### 6.4 The new state, and why its corruption is benign

H4 adds **three unprotected flip-flops**, `oh_guard`. `docs/55` section
8.4 added twenty whose corruption **fails a healthy access** and refused
to net that off against the wins. These three are different in kind, and
the difference is an argument about the refill condition rather than a
measurement:

- an upset that expires the guard early clears `oh_req` while a read may
  still be in flight. **It cannot pop a second entry**: the refill stands
  off on `!cap_rd_valid` and `!cap_rd_en`, so the earliest re-issue is
  two cycles later, by which time the in-flight read has either raised
  `cap_rd_valid` — which sets `oh_valid` and blocks the refill — or been
  discarded, which is the case the bound exists for;
- **and it cannot lose one**, because nothing in the expiry touches
  `oh_valid` or the queue's pointers.

**The whole cost of a spurious expiry is one needless `IRQ_CAUSE.OH_TO`.**
All three bits are in the campaign's site list anyway — `docs/55` section
8.4's rule, that a hardening measured without its own new state is a
hardening measured for its benefit and not its cost — and section 9.4
reports what the draws found there rather than assuming.

**H5 adds no state at all**, so there is nothing to report here for it.
What it adds instead is a way for `ev_state` to suppress a legitimate
strobe, which is the second half of section 6.2.

---

## 7. Measured area

Same recipe as `docs/39` section 6, `docs/40` section 9, `docs/41`
section 6.5, `docs/51` section 11 and `docs/55` section 7: Yosys
`stat -liberty` on `ihp-sg13g2` typical, `abc` with the same driving
cell, the same load and the same 20 ns delay target. Gate equivalent =
`sg13g2_nand2_1` = 7.2576 um2. The Ibex reference is **275,682.6198
um2**.

**EVERY BASELINE ROW WAS RE-MEASURED AT `4b77af1` RATHER THAN QUOTED**,
by checking that file out over the working copy and running the identical
command — `docs/41` section 6.5's rule, and `hw/soc/flow/syn_soc.sh`'s own
header's.

| Block | Cells | Flops | Area, um2 | kGE |
|---|---:|---:|---:|---:|
| `soc_npu`, connection only, baseline (`4b77af1`) | 3,303 | 786 | **65,866.6890** | 9.076 |
| `soc_npu`, connection only, `HARDEN = 0`, baseline | 3,024 | 744 | **61,157.8296** | 8.427 |
| `soc_npu`, connection only, **H4 + H5** | 3,416 | 801 | **67,338.0540** | 9.278 |
| `soc_npu`, connection only, `HARDEN = 0`, H4 + H5 | 3,067 | 751 | **61,845.2982** | 8.521 |
| `soc_npu`, connection only, H4 + H5, **the gate removed** | 3,394 | **801** | **67,179.0294** | 9.256 |
| `soc_npu`, whole subsystem, baseline (`4b77af1`) | 13,066 | 2,077 | **218,407.9842** | 30.094 |
| `soc_npu`, whole subsystem, H4 + H5 | 13,148 | 2,092 | **219,294.8478** | 30.216 |

**[fact for every measured row; the kGE column is arithmetic on them]**

> **THE WAVE COSTS +113 CELLS, +15 FLIP-FLOPS AND 1,471.3650 um2 ON THE
> CONNECTION, WHICH IS 0.53 % OF THE UNPROTECTED IBEX CORE** **[estimate,
> the difference of two measured rows]**.

Five readings.

**THE THREE BASELINE ROWS REPRODUCE `docs/55`'s TABLE TO THE FOURTH
DECIMAL** — 3,303 / 786 / 65,866.6890, 3,024 / 744 / 61,157.8296 and
13,066 / 2,077 / 218,407.9842, against that document's identical figures
**[fact]**. That was not the purpose of re-measuring them and it is worth
recording: an area figure in this repository is reproducible eight days
and one toolchain invocation later.

**H5's cost is isolated by a mutation and it is the row that matters
most.** The gate is combinational, so a flip-flop census is blind to it:
the design with the gate and the design without it hold **801 flip-flops
each**, and the difference is **22 cells and 159.0246 um2** **[fact]**.
That is the whole price of taking the worst bit in the block from 18 of
18 to what section 9 measures. `test_the_aer_strobe_gate_is_in_the_netlist_and_costs_no_flip_flop`
runs the same mutation as a regression, because **nothing else in this
repository could fail if the gate were optimised away** — the campaign
deposits into RTL, the cocotb suite drives RTL, and `soc_npu.v` has no
proof.

**The flip-flop arithmetic closes exactly, and it attributes.** +15 =
`oh_guard` 3, plus 3 replicas x 4 bits of protected word — a sticky bit
and a mask bit for each of the two new cause bits. Split by mechanism:

| | flip-flops | cells |
|---|---:|---:|
| H4's bound (`oh_guard`) | 3 | — |
| H4's report (`OH_TO` in the tripled bank) | 6 | — |
| **H5's gate** | **0** | **22** |
| H5's report (`AER_MM` in the tripled bank) | 6 | — |
| **total** | **15** | **113** |

**[estimate, arithmetic on the measured rows; the 22 is measured
directly]**. **The reports cost four times what the mechanisms do**, and
that is `docs/55` section 6.1's bundle being paid for twice more rather
than anything about these two mechanisms.

**The redundancy, priced against `HARDEN = 0` on the same design.**
801 − 751 = **50 = 2 x PROT_W** at PROT_W = 25 **[fact]**, and the area
is **5,492.7558 um2** **[estimate, the difference of two measured rows]**
against `docs/55`'s 4,708.8594 at 21 bits. `docs/41` section 6.5's rule —
compare against the same design's own unhardened configuration, never
against the older design — is what makes those two comparable at all.

**The connection-only and whole-subsystem deltas disagree by 584.5014
um2 at the identical +15 flip-flops**, and that is mapping noise rather
than a finding, exactly as `docs/55` section 7 recorded 654.4314 um2 of
it at +69. The whole-subsystem row even has **82 more cells for 133 fewer
in the connection-only comparison**; `syn_soc.sh`'s header records that
Yosys is entitled to map a different design differently, and here the
difference is the whole of `pilot_top`. Both rows are given; neither is
corrected against the other.

**No frequency was measured for any of this.** None of it has been
through STA at any corner or through place-and-route. `docs/55` section
14 item 3 made that the largest unmeasured thing that document left, and
this one adds a comparator in the AER pin path and does not measure it
either. Section 12.

---

## 8. The campaign, re-run

### 8.1 One build, and why this wave needs only one

`docs/55` needed two builds and said why: it changed the **workload** —
1,348 cycles of configuration read-back and three `BUSSTAT` loads — so a
fresh campaign and `docs/52`'s campaign did not share their draws, and
the difference between them would have been a difference of two things.
Section 8.3 of that document is the record of what that cost: fifteen of
the frozen die's hundred records changed verdict on silicon that cannot
have changed.

**This wave changes no software at all.** H4 and H5 are RTL, and the
measurement says so at three levels **[fact]**:

| | split baseline | H4 + H5 |
|---|---:|---:|
| whole-SoC invariant, 27 checks, fail mask 0 | 215,428 | **215,428** |
| the campaign's clean run | 15,542 cycles | **15,542** |
| the measured injection window | 292 .. 13,772 | **292 .. 13,772** |

> **THE DRIFT `docs/55` HAD TO CALIBRATE AGAINST IS EXACTLY ZERO HERE**,
> and section 8.2 does not have to argue it: the same cycle in the two
> builds is the same instant in the same program, and the calibration
> strata come back with **not one changed verdict** to prove it.

### 8.2 The delta, on the same draws, and its calibration

**1,000 of the split baseline's 1,100 injections replayed verbatim —
same site, same bit, same cycle, against the hardened build** **[fact,
`hw/soc/out/h56-replay/directed.csv`]**. The missing 100 are `cfgreg`:
the three replicas are 25 bits now and were 21 then, so bit *k* of the
word is a different field. The **paths still exist**, which is worse than
their not existing — `npu_campaign.py` would replay them happily — so
they are removed deliberately, and section 14 records that.

| stratum | n | silent, before | **after** | **records whose verdict changed** |
|---|---:|---:|---:|---:|
| **`ev_pin`** | 100 | **18** | **0** | 0 |
| **`ev_oh`** | 100 | 6 | **3** | **1** |
| `ev_seq` | 100 | 13 | 13 | **0** |
| `ev_data` | 100 | 0 | 0 | **0** |
| `ev_cnt` | 100 | 0 | 0 | **0** |
| `ser` — untouched | 100 | 6 | 6 | **0** |
| `window` — untouched | 100 | 2 | 2 | **0** |
| `evq_data` — untouched | 100 | 0 | 0 | **0** |
| `evq_ptr` — untouched | 100 | 0 | 0 | **0** |
| **`die_ser` — FROZEN SILICON** | 100 | 6 | 6 | **0** |
| **total** | **1000** | **51** | **30** | **1** |

**[fact]**. "Verdict changed" is the armed class or the truth column
differing on the same draw. The silent counts on both sides are computed
over the **same** announcement set — `ann_npu` and `ann_wdog`, the two
`directed.csv` carries — so the two columns are comparable to each other;
section 8.3's per-stratum figures use the full four-channel set and are
the ones to quote against another campaign.

> **THE CALIBRATION IS EXACT AND IT IS THE WHOLE REASON THIS DOCUMENT
> WILL QUOTE ITS DELTA WHERE `docs/55` REFUSED TO.** That document could
> not: its frozen die's own stratum — silicon `docs/34` committed, which
> cannot have changed — moved by one **with fifteen of a hundred records
> changing verdict**, because the workload was 154 cycles longer and the
> deposits landed at a different instant in the program. Here **`die_ser`
> comes back with 6 of 100 and NOT ONE CHANGED RECORD**, and so do
> `ser`, `window`, `evq_data` and `evq_ptr` — **500 calibration records,
> zero drift** — and so do `ev_data` and `ev_cnt`, 200 more inside the
> stratum that was split. **Exactly one record in a thousand moved, and
> it is in a stratum this work touched.**

**51 → 30, and every one of the 21 is in a stratum the work touched:
18 in `ev_pin` and 3 in `ev_oh`.** Nothing else moved at all.

**`ev_pin` is 18 → 0 and the class did NOT change on any of them**, which
is worth reading carefully. All 18 were DETECTED before and are DETECTED
now; what changed is **which channel detected them and whether the answer
was right**. Before, `fi_mask` was `0x8`, `0xa` or `0xc` — a wrong
neuron state file, a wrong stream length, a wrong stream — and the
program's own model check was the only thing that noticed. Now `fi_mask`
is `0x10` on seventeen of the eighteen: **telemetry only, the inference
bit-for-bit golden, and `IRQ_CAUSE.AER_MM` set** **[fact]**. The
eighteenth is section 8.3's.

**`ev_oh` is 6 → 3 and the three that moved are all `oh_req`** **[fact]**.
Their `fi_mask` was `0x6a` — wrong length, wrong state, the hardware's
counts disagreeing and **a barrier that never came back** — which is the
wedge of section 5.1, appearing in the campaign as four bits of one mask
and never as a class of its own. All three now return the golden
inference. **The three that did not move are `oh_valid` twice and
`oh_data` once**, and section 11 item 3 is why: H4 bounds a request that
never completes and says nothing about a holding register that lies.

**THE ONE CHANGED VERDICT IS AN IMPROVEMENT THAT READS LIKE A REGRESSION,
AND IT IS SPELLED OUT RATHER THAN LEFT IN THE TABLE.** `oh_req` bit 0 at
cycle 13,002 was **MASKED / OK** and is now **DETECTED / WRONG**. Its
deposit lands 770 cycles before the window closes and after the program's
last collection, so the wedge it caused did nothing and the run finished
with the golden answer and nothing set. Now the bound fires, `OH_TO` is
latched, and the record classifies DETECTED — **with `model_wrong` still
false**. The "WRONG" is `armed_out_ok` comparing the whole published
result, and the only thing in it that differs is the cause register,
**which is supposed to move**. That is `docs/55`'s control 4d exactly,
and `docs/55` section 5's *"what it costs to be told"*: a run that would
have been MASKED becomes DETECTED because the part learned to speak.

**And the mechanisms fired on the replay as they did on the campaign of
record**: the AER gate on **23** records, the show-ahead bound on **4**,
and the longest run of cycles the show-ahead's request stayed outstanding
over all 1,000 is **5** **[fact]** — against a healthy 2 and a bound of
4, with nothing anywhere near the thousands a wedge produces.

### 8.3 The campaign of record

1,100 injections, eleven strata of 100, each run twice — 2,200
simulations against the design that ships, drawn over **its own**
populations, which are not the split baseline's: the connection now
offers **824 injectable bits** against 809, `ev_oh` went from 19 to 22
and `cfgreg` from 65 to 77 **[fact, `hw/soc/out/h56-npu/`]**.

**With the watchdog armed — the SoC as this document ships it:**

| stratum | bits | n | MASKED | CORRECTED | SDC | DETECTED | HANG |
|---|---:|---:|---:|---:|---:|---:|---:|
| `ser` | 143 | 100 | 83 | 0 | 0 | 17 | **0** |
| `window` | 89 | 100 | 93 | 0 | 0 | 7 | **0** |
| `cfgreg` | 77 | 100 | 11 | 0 | 0 | 89 | **0** |
| `ev_seq` | 19 | 100 | 72 | 0 | 3 | 25 | **0** |
| `ev_data` | 64 | 100 | 100 | 0 | 0 | 0 | **0** |
| `ev_cnt` | 32 | 100 | 3 | 0 | 0 | 97 | **0** |
| `ev_pin` | 6 | 100 | 82 | 0 | 0 | 18 | **0** |
| `ev_oh` | 22 | 100 | 92 | 0 | 2 | 6 | **0** |
| `evq_data` | 304 | 100 | 100 | 0 | 0 | 0 | **0** |
| `evq_ptr` | 68 | 100 | 10 | 6 | 0 | 84 | **0** |
| **CONNECTION** | **824** | **1000** | **646** | **6** | **5** | **343** | **0** |
| `die_ser` — frozen | 87 | 100 | 91 | 0 | 0 | 9 | **0** |

**[fact]**, and **the disarmed column is identical, row for row**: no
record in 1,100 ends with a dead machine, so the watchdog never
escalates and the two columns cannot differ. `docs/55` section 8.6
established that for this block; this document inherits it and does not
break it.

The silent wrong inference, which is the figure the ranking is made of:

| stratum | bits | split baseline | **now** |
|---|---:|---:|---:|
| `ev_pin` | 6 | **18 / 100** | **0 / 100** |
| `ev_oh` | 19 → 22 | 6 / 100 | **3 / 100** |
| `ev_seq` | 19 | 13 / 100 | **13 / 100** |
| `ev_data` | 64 | 0 / 100 | 0 / 100 |
| `ev_cnt` | 32 | 0 / 100 | 0 / 100 |
| `ser` | 143 | 6 / 100 | 6 / 100 |
| `window` | 89 | 1 / 100 | 1 / 100 |
| `cfgreg` | 65 → 77 | 0 / 100 | 0 / 100 |
| `evq_data`, `evq_ptr` | 372 | 0 / 200 | 0 / 200 |
| `die_ser` — **frozen** | 87 | 6 / 100 | 6 / 100 |

**[fact]**

> **`ev_pin` IS 18 OF 100 TO 0 OF 100, AND THE EIGHTEEN DRAWS INTO
> `aer_in_stb` ARE THE WHOLE OF IT.** Seventeen of those eighteen now
> come back with **the golden inference and `IRQ_CAUSE.AER_MM` set** —
> `fi_mask` is `0x10`, telemetry only, where it was `0x8`, `0xa` or `0xc`
> **[fact]**. The eighteenth, at cycle 7,847, is still wrong, and it is
> the direction section 6.2 named: the flip cleared the flag inside a
> legal strobe, so H5 held the pin quiet and **a real event was lost**.
> One of eighteen, named rather than netted off.

**Four readings, and one of them is the number not to quote.**

**Every firing of every mechanism was announced** **[fact]**:

| mechanism | records it fired on, of 1,100 | announced |
|---|---:|---:|
| the AER strobe gate | **23** | **23 of 23** |
| the show-ahead bound | 3 | 3 of 3 |
| the engine's fetch bound (inherited from `docs/51`) | 3 | 3 of 3 |
| the queues' pointer vote | 74 | 68 of 74 |
| the queues' `rd_valid` rails | 5 | 5 of 5 |
| the queues' entry parity | 0 | — |

**The gate fires on `ev_state` as well as on the flag, and firing is not
helping.** Of its 23 firings, 18 are `aer_in_stb` and **5 are
`ev_state`** **[fact]** — and not one of `ev_state`'s seven silent
records changed. Section 11 item 1 is that measurement and it refutes a
prediction this document made before running it.

**THE STALL IS GONE AND THE CAMPAIGN MEASURES IT DIRECTLY RATHER THAN
INFERRING IT FROM A CLASS.** `docs/16`'s five classes have no name for
*"the block stopped delivering events and every register still looks
sane"*, so the bench now records **the longest run of cycles the
show-ahead's request stayed outstanding** on every record. Over 1,100:
**min 0, median 2, max 5, and zero records above 64** **[fact]**. Two is
the healthy figure and the bound is four; a wedged adapter would show
thousands. **That column exists because the classification could not
have caught this failure**, which is `docs/52` section 5.1's argument
about an oracle applied to a class boundary.

**AND THE NUMBER NOT TO QUOTE.** The connection-weighted silent wrong
inference is **1.53 %** here against the split baseline's **1.75 %**
**[fact for both]**, and *that comparison is not valid*: the denominators
are different populations — 824 bits against 809 — and `ev_oh` and
`cfgreg` grew while `ev_pin` went to zero, so part of the movement is
arithmetic on the change. **The comparison that is valid is section
8.2's, on the same draws.** `docs/55` section 8.6 refused the same
arithmetic for the same reason.

### 8.4 The whole-SoC invariant, measured once

`docs/55` had to measure it three times because it changed the RTL and
the program. **This wave changes only the RTL, so one measurement is the
whole of it** **[fact, 27 of 27 checks passing with a zero fail mask]**:

| build | cycles |
|---|---:|
| `docs/55`, the design of record | 215,428 |
| **H4 + H5** | **215,428** |

> **BOTH THE BOUND AND THE GATE COST ZERO CYCLES**, reproducing
> `docs/55`'s number to the cycle. H4's guard never expires on a healthy
> part — `oh_req` is outstanding for two cycles against a bound of four —
> and H5's gate is a conjunction that is true whenever the flag is.

**Every document after this one should go on quoting 215,428.**

### 8.5 What running it cost

**2,200 `vvp` invocations for the split baseline — 1,100 injections and
8 controls — in 60 minutes 3 seconds at 18 concurrent processes on a
20-thread host** **[fact, the elaborated image's timestamp of 20:32:17 to
the `records.csv` timestamp of 21:32:20]**, which is **36.6 simulations a
minute**. The campaign of record is 2,200 more in **59 minutes 13
seconds** **[fact, 21:41:17 to 22:40:30]**, 37.1 a minute.

Both are close to `docs/55`'s 37.9 and slower than `docs/52`'s 44.6, for
that document's reason: **the workload is longer**, 15,542 cycles against
14,057. The host was also running three syntheses and two cocotb suites
for part of the second campaign, and `docs/44` section 9.5's rule is to
quote the cost with the configuration it was measured in.

**THE SPLIT DOUBLED THE PRICE OF A HARDENING WAVE IN THIS BLOCK AND THAT
IS THE HONEST ACCOUNTING OF SECTION 12'S CORRECTION.** `docs/55` ran one
campaign of record and one replay; this one ran a campaign to *decide*
what to build before either, because a stratification that is not re-run
is a re-labelling.

---

## 9. Verification

Four kinds of evidence, and `docs/41` section 6's division between them:
**each one is blind to what the others see**, and this section says which
is blind to what rather than presenting four green ticks as one.

### 9.1 The regression and the existing suites

`hw/soc/flow/sim_soc.sh` runs the whole SoC — Ibex, the fabric, the
memories, the watchdog, `BUSSTAT` and the connection with the frozen die
inside it — through 27 checks. **All 27 pass with a zero fail mask, at
215,428 cycles** **[fact]**.

`hw/soc/tb/cocotb/test_soc_npu.py`'s existing **27 tests pass unchanged**
and `test_soc_busstat.py`'s **10 of 10** **[fact]**: this wave changed no
behaviour either suite already checked, which is the first thing that had
to be true and the easiest to skip past. `soc_busstat.v` is not edited at
all and its suite is run to say so.

### 9.2 Four new cocotb tests, and one of them injects nothing

| Test | What it establishes |
|---|---|
| `test_a_stuck_show_ahead_request_recovers_instead_of_wedging` | one upset in `oh_req` while the adapter is idle: the next barrier still arrives, `IRQ_CAUSE.OH_TO` is set and no other mechanism's bit is, the bit is acknowledgeable, and a **third** barrier goes through afterwards — the difference between a recovery and a one-shot escape |
| `test_a_discarded_capture_entry_does_not_stop_the_event_path` | **no upset in the adapter at all.** One capture-queue entry's stored parity is spoiled between the drain engine's write and the adapter's read; the entry is lost, `Q_DET` and `OH_TO` both rise, and **three later barriers still arrive** |
| `test_the_show_ahead_bound_never_fires_on_a_healthy_read` | over a whole inference, `oh_expire` never rises and the largest guard is **exactly `OH_WAIT`** — so the bound, the read's own latency and the declared slack are three numbers that agree rather than three that are merely consistent |
| `test_a_phantom_aer_strobe_never_reaches_the_die` | `aer_in_stb` set while the engine is idle: **no strobe reaches the die's pin**, `IRQ_CAUSE.AER_MM` is set, and the inference that follows is the golden one. It also asserts that every strobe the die did see was in `E_PIN_S` |

**31 of 31 pass in `test_soc_npu.py`** **[fact]**.

**Two of them are the defect, executable.** The first two were written as
probes against the design `docs/55` shipped and **both failed there**
(section 5.1); they pass now. That ordering is the point — a test written
after the fix is a test that has never been shown to be able to fail.

**The fourth checks the pin before it checks the register**, because a
version that reported `AER_MM` and still strobed the die would pass a
test that only read `IRQ_CAUSE`.

**What they do not cover.** All four deposit into **RTL**, so every one
would pass on a netlist in which the strobe gate had been optimised away
or the guard's counter deleted. That is section 9.4's question and
nothing here can answer it.

### 9.3 Formal

`hw/soc/formal/soc_npu_ser.sby`, four tasks — `bmc`, `prove`, `cover` and
`prove_h3` — **all four PASS** **[fact]**. `soc_npu_ser.v` is not
modified by this work and the property file is not edited; the tasks are
run because "the file I did not touch still proves" is a claim that costs
ten minutes to check and nothing to assume wrongly.

**AND THERE IS STILL NO PROPERTY SET FOR `soc_npu.v`.** `docs/55` section
9.3 named that as the largest single gap in its verification and declined
to close it; this document adds two more mechanisms to the module that
has none. H4's bound would be provable in the same shape the transport's
is — `oh_req` set implies `oh_guard` is an exact function of the cycles
since `cap_rd_en`, so `oh_guard < OH_MAX` on a healthy read is an
induction — and **H5's invariant is the simplest provable statement in
this block**: `aer_in_stb == (ev_state == E_PIN_S)` is one line, it is
the whole basis of the mechanism, and it is asserted here by a
simulation and a textual guard instead. Section 10 carries it.

### 9.4 The netlist census

`sw/tests/test_soc_synthesis_guards.py` gains two checks and one
capability.

| Check | Result |
|---|---|
| three banks of `PROT_W` in the mapped netlist, derived from `NCAUSE` and `C_INJ_OVF` in the RTL | **25, 25, 25** **[fact]** |
| the same with every `keep` and `keep_hierarchy` **deleted from the text** of the sources and `flatten` forced | **no flip-flop lost** **[fact]** |
| `.MIX(0)` on replica C | **13 flip-flops lost**, one for each odd bit of the 25-bit word **[fact]** |
| `HARDEN = 0` | **50 lost = 2 x PROT_W** **[fact]** |
| `u_ser.guard`, `win_guard` and **`oh_guard`** are nets in the mapped netlist at their derived widths | **8, 9 and 3** **[fact]** |
| the mapped flip-flops whose `src` names `soc_npu_ser.v`, against the campaign's site list | **143 = 143** **[fact]** |
| `aer_in_stb` is still a **net of its own** in the netlist, and so is the state comparison | **1 and 1** **[fact]** |
| **the AER strobe gate, by mutation**: the same design with `aer_in_stb_q = aer_in_stb` | **the identical flip-flop count and strictly fewer cells** **[fact]**; under `syn_soc.sh`'s recipe the difference is 22 cells (section 7) |

**The last row is the one this document needed and the file did not
have.** Every other census here counts flip-flops, and **H5 has none**:
its whole mechanism is a comparator and an AND. A mapper that folded the
gate away, or an edit that removed it, would leave the flip-flop count
untouched and **nothing else in this repository could fail** — the
campaign deposits into RTL, the cocotb suite drives RTL, and there is no
proof. So `Census` now counts every cell and the guard is a mutation:
build it without the gate and require the netlist to be strictly smaller
at the same flip-flop count. That says both things at once — the gate is
physically present, and it costs no state.

**`oh_guard`'s floor is derived from `OH_MAX` and not written down**, and
it is the guard in this block most likely to be folded: three bits
against the others' eight and nine, a next value that is a small function
of two flags, and on a healthy part it counts to two and clears — exactly
the shape an optimiser is entitled to try to fold.

**The textual guards, and why a census cannot replace them.** Five in
`test_soc_npu_guards.py`: that the engine's five sub-strata are a
**partition** of the 140 bits `docs/52` measured plus H4's guard and
nothing else; that H4's bound is derived from the read's own latency,
clears the request and reports; that the pop and the expiry are **two
separate `if`s** rather than a chain, which no simulation here can fail
on because `oh_valid && oh_req` is unreachable on a healthy part; that
H5's pin is the gated wire, that the flag is **still a register** — a
version driving the pin from `ev_state` alone would pass a behavioural
test and move the whole exposure into `ev_state` — and that a
disagreement is reported; and that every cause bit the RTL has is a fault
bit `soc_npucfg.h` knows about, because the campaign's announcement mask
is derived from `NCAUSE` and the **program's** is a written list.

---

## 10. What this does NOT cover

Worst first, and at length, because `docs/41` section 6.6 lists twelve
instances of a green check read wider than the thing it examined and
`docs/55` found the thirteenth in its own window bound.

- **H5 MASKS AND DOES NOT CORRECT, AND ONE OF ITS TWO DIRECTIONS LOSES AN
  EVENT.** Holding the pin quiet is right when the flag was corrupted and
  wrong when `ev_state` was, and this block cannot tell which. Section
  6.2. A campaign draw into `ev_state` that lands on `E_PIN_S` now
  produces a suppressed strobe and an `AER_MM` where it used to produce a
  phantom event; a draw that lands on it *out* of `E_PIN_S` now loses a
  real one. **The second is a failure mode this work introduced** and
  section 9's `ev_seq` row is where it would show.
- **`ev_state` IS UNPROTECTED AND IS NOW THE LARGEST SITE LEFT**, at 7 of
  20. Section 11 item 1. H5 depends on it: the gate makes the strobe a
  conjunction of the flag and the state, so the state is now load-bearing
  for a pin it was only implicitly related to before.
- **`soc_npu.v` STILL HAS NO FORMAL PROPERTY SET**, and this document
  added two mechanisms to it. H5's invariant —
  `aer_in_stb == (ev_state == E_PIN_S)` — is one line and is the entire
  basis of the mechanism, and it is checked here by **one cocotb test and
  one textual guard** rather than over all reachable states. `docs/55`
  section 9.3 named this gap and declined to close it; declining twice is
  a decision and section 9.3 says so.
- **THE THREE NEW GUARD FLIP-FLOPS ARE ARGUED BENIGN, NOT PROVED BENIGN.**
  Section 6.4's reasoning is about the refill condition's stand-offs and
  it is an argument about an FSM, which is the kind of argument
  `docs/55` section 4.3 got wrong once and had to rebuild. It is measured
  in section 9 by drawing into them; it is not proved.
- **NEITHER NEW REPORT HAS A DURABLE RECORD.** `OH_TO` and `AER_MM` are
  write-1-to-clear cause bits with **no `BUSSTAT` counter behind them**,
  by the decision in section 5.2 — so software that acknowledges one
  keeps no record of it anywhere, and `docs/44` section 6.4's argument
  for the counter applies to both and is not answered. `docs/55` section
  5's *"the bench count and the operator count are the same number"* is
  therefore **not available for either of this wave's mechanisms**: the
  campaign can show `IRQ_CAUSE` was read by a load, and cannot show a
  count.
- **THE SPLIT IS FIVE STRATA AND NOT NINETEEN.** Section 3.3's per-site
  table is drawn from a stratified campaign whose *strata* are the five,
  so `aer_in_stb`'s 18 of 18 rests on **18 draws** and `oh_req`'s 3 of 4
  on four. Those are the samples proportional-within-stratum sampling
  gave them, and the per-site column is the sharpest thing in this
  document and the thinnest. A campaign stratified per site would put
  100 draws on each and is a day of simulation, not an edit.
- **THE ENGINE'S CONTRIBUTION CHANGED WITH THE ESTIMATOR AND NOT WITH THE
  DESIGN**, from `docs/52`'s 1.71 points to 0.58. Section 3.4. Neither
  number is wrong and they must not be quoted as a before and after.
- **`ev_cnt`'s ZERO IS A PROPERTY OF THE PROGRAM.** 97 of its 100 records
  classify DETECTED because `fi_npu.c` cross-checks `NPUCFG.CNT` against
  the stream it collected. On a mission whose software does not, those 97
  are silent. Nothing in `soc_npu.v` compares those counters against
  anything and this document does not change that.
- **THE TWO ZERO ROWS ARE NOT RATES OF ZERO.** `ev_data` 0 of 100 and
  `ev_cnt` 0 of 100 silent are rates below about 3.7 %, and
  `aer_in_addr` and `aer_in_tick` at 0 of 82 below about 4.4 %.
  `docs/42` section 4.5's reading applies word for word. What makes them
  load-bearing anyway is their **share**: even at the top of their
  intervals they cannot be where this stratum's rate lives.
- **THE WEDGE WAS FOUND BY READING AND NOT BY MEASURING**, and the
  campaign that could not find it is the campaign that certifies the
  fix. 2,500 injections across three campaigns put zero draws on the
  path (section 5.1). Section 9's rate says nothing about how much of
  the improvement is the wedge, because the wedge is still not being
  drawn.
- **ONE WORKLOAD, ONE STIMULUS, ONE GEOMETRY, ONE SEED** — `docs/52`
  section 13's caveat, inherited whole, and section 9 inherits its
  conditional-on-the-injection-window reading with it.
- **RTL, SINGLE-BIT, FLIP-FLOP ONLY.** No gate-level netlist, no
  back-annotated timing, no multi-bit strike, no single-event transient
  in combinational logic — **and H5 is combinational logic**, so a
  transient on the gate is a failure mode this work introduced and no
  instrument in this repository can see. The connection's netlist has
  still never been simulated.
- **NO FREQUENCY, NO STA, NO PLACE-AND-ROUTE.** A four-bit state
  comparator is now in the path to the die's AER pins and nothing has
  timed it. Section 15 item 3.
- **THE INTERRUPT IS STILL NEVER ARMED BY ANY WORKLOAD HERE**, so the two
  new cause bits are measured as a **report** and not as a branch.
- **THE NETLIST CENSUS COUNTS CELLS AND FLIP-FLOPS AND ASSERTS NOTHING
  ABOUT ANY OTHER PROPERTY**, examines `soc_npu` with the die
  black-boxed rather than the whole SoC, and says nothing about placement
  or routing — `docs/41` section 6.6's list, unchanged and still true.
  The mutation guard for H5 says the gate is *present*; it says nothing
  about whether the cells it maps to are the ones a foundry would like.

---

## 11. What was left, ranked and priced

Four of the six sites the split ranked are not built, and none of them is
left because it is small. Each is priced against what the campaign
measured of it, in the order the measurement puts them.

**1. `ev_state`, 4 bits, 7 silent wrong inferences in 20 draws — now the
largest single site left in the connection.** It is the engine's whole
sequencer and there is no free redundancy for it: the answer is to bundle
it with `ev_wait` and the strobes into one protected word under
`soc_tmr_bank`, which is 19 bits of `ev_seq` at **38 more flip-flops**
**[estimate, 2 x the bundle]** — two and a half times this whole wave.
**And it needs the FSM's registered outputs rewritten as one
combinational next-value function**, because `soc_tmr_bank` has no write
enable. That is exactly the change `docs/41` section 6.5 records W6
making to `soc_wdog.v`, and it is exactly the change that document warns
must not be measured against the old design. It is the right next thing
in this block and it is not a half-day.

**H5 WAS EXPECTED TO TAKE A SHARE OF `ev_state` AND THE MEASUREMENT SAYS
IT TOOK NONE.** Six of the seven silent records are `ev_state` bit 1,
whose flip moves the FSM into or out of the pin sequence, and the
prediction was that a state landing on `E_PIN_S` without the flag would
no longer strobe the die. **The gate does fire on `ev_state` — 5 of its
23 firings are there** **[fact]** — and **not one of the seven silent
records changed**: same class, same `fi_mask`, `aer_mm` zero on every one
of them. The five it catches are records that were already masked or
already announced. The reason is that `ev_state` bit 1's flips mostly
carry the FSM *away* from the pin sequence, where the failure is a lost
or misrouted event rather than a phantom one, and H5 has nothing to say
about that. **`ev_state` is the same 7 of 20 it was.**

**2. `cap_wr_en`, 1 bit, 5 of 8 — and it has no state that implies it.**
A spurious pulse writes the stale `cap_wr_data` into the capture queue: a
**phantom output event**, which is H5's failure in the other direction.
It cannot take H5's answer, because `cap_wr_en` is a one-cycle pulse
issued on the way *out* of `E_DRN_W` — in the cycle it is high,
`ev_state` is already `E_IDLE` and implies nothing. Qualifying it needs a
**registered previous state**, four more flip-flops that are themselves
unprotected, or the `ev_seq` bundle of item 1, which subsumes it. **It is
deferred to item 1 rather than answered on its own**, and that is a
decision this document is making explicitly because the cheap-looking
alternative — a second copy of one bit — is the replication bound in a
costume.

**3. `oh_valid`, 1 bit, 2 of 4 — and `oh_data` behind it at 1 of 85.**
Set by an upset, the adapter hands software a **stale word** and reports
an event that is not there, which is `docs/55` section 8.6's surviving
SDC exactly. Cleared, it **loses** the word the adapter is holding. H4
does nothing for either: the bound is about a request that never
completes, not about a holding register that lies. The answer is the
adapter's own bundle — `{oh_valid, oh_req, cap_rd_en, oh_data}` is 19
bits under `soc_tmr_bank`, **38 more flip-flops** **[estimate]** — and it
is declined here on two grounds. The measured rate is 2 of 4 on one bit
against `ev_state`'s 7 of 20 on four, so item 1 outranks it; and **TMR
would not have found the wedge**, because a wedged `oh_req` is a value
all three replicas agree on. That is worth stating on its own: **the
mechanism this wave built is one redundancy cannot substitute for.**

**4. `inj_rd_en`, 1 bit, 1 of 4.** The lowest-ranked site the split found
that is not zero, and it is in the `ev_seq` bundle of item 1.

**5. The AER address and type pins.** `aer_in_addr` and `aer_in_tick`
measured **0 of 82 draws between them**, because a corrupted address on a
strobe that is not happening reaches nothing and there is one cycle per
event in which it would. H5 does nothing for them, and a 6-bit pin bundle
under `soc_tmr_bank` — 12 flip-flops — would. **It is declined on the
measurement and the interval is stated with it**: 0 of 82 is a rate below
about 4.4 %, not a rate of zero, and `docs/42` section 4.5's reading of a
zero row applies word for word.

**And two things that are left because the measurement says they carry
nothing**, which is the same decision `docs/55` took for `evq_data` and
for the same reason. `ev_data` is 64 bits — 45.7 % of the engine, the
largest sub-stratum by a factor of three — and came back 0 of 100.
`ev_cnt` is 32 bits and came back 0 of 100 silent, 97 of 100 DETECTED.
**`ev_cnt`'s zero is a property of the program and not of the design**
(section 3.2), and that is the one of the two that could change: a
mission whose software did not cross-check `NPUCFG.CNT` would move those
97 records from DETECTED to silent. `docs/52` section 11.3 said so and
this campaign is the confirmation at a hundred draws.

---

## 12. Corrections to earlier documents

**`hw/soc/rtl/soc_npu.v`'s show-ahead adapter said "`oh_req` simply stays
set until the next entry arrives, and the queue's own level tells
software the difference."** It does stay set; the next entry never
arrives *at the adapter*, because the refill it would arrive through
requires `!oh_req`. The sentence is replaced and the replaced text is
quoted in the file, so the correction is legible rather than silent —
which is the form `docs/55` section 11 used for the transport's "it has
no timeout".

**`docs/55` section 8.6 reported one SDC — `oh_valid` bit 0 at cycle
13,308 — and said "Nothing in this document addresses it and section 14
does not rank it; it is one record."** The split shows it is not one
record: `oh_valid` came back **2 of 4** and its neighbour `oh_req` **3 of
4** over the same sub-stratum at four times the draws. `docs/55` was
right that its own campaign could not rank it and right not to act on
one record; **what was missing was the resolution to see it, which is
this document's section 3.** Section 11 item 3 ranks it and still does
not build it.

**`docs/55` section 14 item 1 estimated the split at "a half-day of work
on `npu_targets.py`", and that estimate was right about the file and
wrong about the work.** The edit to `npu_targets.py` is 60 lines. What it
cost was **two full campaigns** — 1,100 injections to measure the split
and 1,100 more against what the split said to build — because a
stratification that is not re-run is a re-labelling.

**`docs/52` section 6.3's table gains a row it could not have had.** That
table ranks six strata by consequence and its sharpest reading is that
the largest structure in the block is the safest one. The engine was one
row in it; split, **the same relationship holds inside that row**, and
`docs/56` section 3.2 is the second instance. It was a finding in
`docs/52`; with a second independent instance one level down it is closer
to a property of this design, and section 15 says what to do with that.

**`README.md`'s NPU paragraph said "27 checks, fail mask 0, 213,971
cycles" and "Nothing in it is hardened beyond the two event queues."**
Both were made false by `docs/55` and neither was corrected there. The
invariant is **215,428** (`docs/55` section 8.5, reproduced here) and the
connection now carries five hardening items. The paragraph is replaced.
This is a correction to a stale claim rather than to a number, and it is
the same class `docs/55` section 11 found in `soc_top.v`'s header.

---

## 13. Files touched

### 13.1 RTL

```
hw/soc/rtl/soc_npu.v    H4's show-ahead bound, H5's strobe gate,
                        two new cause bits, header sections 8 and 9
```

**One file, and that is the whole of the RTL change.** `soc_npu_ser.v`,
`soc_busstat.v` and `soc_top.v` are untouched: this wave routes no new
fault line out of the block, which is section 5.2's decision about
`BUSSTAT` and section 12's exposure. `hw/soc/rtl/soc_tmr_bank.v` and
`hw/rtl/tmr_voter.v` are **instantiated and not modified**. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is touched, and
`hw/soc/formal/soc_npu_ser_props.v` is not edited because `soc_npu_ser.v`
is not.

### 13.2 Harness, tests and documents

```
hw/soc/fi/npu_targets.py        the engine split into five strata;
                                oh_guard added as a site
hw/soc/fi/npu_campaign.py       report section 3b, the unknown-stratum
                                guard, three new record columns
hw/soc/tb/tb_soc_npu_fi.v       oh_to, oh_req_max and aer_mm at the bench
hw/soc/tb/sw/soc_npucfg.h       two cause bits, and NPUCFG_C_FAULTS
hw/soc/tb/cocotb/test_soc_npu.py        four tests
sw/tests/test_soc_npu_guards.py         five guards
sw/tests/test_soc_synthesis_guards.py   two guards, and a cell count
README.md                       the NPU paragraph, section 12
docs/56-npu-event-engine-hardening.md   this document
docs/00-index.md                        one row
```

**No software changed**, which is section 8.1's whole argument: neither
`hw/soc/tb/sw/test_ibex.c` nor `hw/soc/tb/sw/fi_npu.c` is edited, so the
program that produced `docs/55`'s 215,428 cycles is the program that
produces this document's, instruction for instruction.

`hw/soc/tb/sw/soc_npucfg.h` gains two `#define`s and no code reads them
yet — the campaign's announcement mask is derived from `NCAUSE` in the
RTL, not from the header. `test_every_cause_bit_the_block_has_is_a_fault_bit_the_program_knows`
is what keeps the header from falling behind the RTL, because the derived
mask cannot protect the written one.

---

## 14. Reproducing this

```
python regmap/generate.py                       # four outputs, one source
python regmap/generate_memmap.py
.venv/bin/python -m pytest sw/tests -q

hw/soc/flow/sim_soc.sh                          # 27 checks on the real SoC

cd hw/soc/tb/cocotb && make -f Makefile.soc_npu
cd hw/soc/tb/cocotb && make -f Makefile.soc_busstat
cd hw/soc/formal && make npuser                 # bmc, prove, cover, prove_h3
```

The area table, with the baseline rows taken against `4b77af1`'s own
`soc_npu.v` and the same recipe:

```
SOC_SYN_BLACKBOX=pilot_top hw/soc/flow/syn_soc.sh soc_npu
SOC_SYN_BLACKBOX=pilot_top SOC_CHPARAM="-set HARDEN 0" \
    hw/soc/flow/syn_soc.sh soc_npu
hw/soc/flow/syn_soc.sh soc_npu
#   ... and the same three with `git checkout hw/soc/rtl/soc_npu.v`
#   for the baseline rows, restoring the working copy afterwards.
```

The row that isolates H5 is the same command on a copy of `soc_npu.v`
with the gate replaced by `assign aer_in_stb_q = aer_in_stb;` and
`assign aer_stb_mm = 1'b0;`. `test_the_aer_strobe_gate_is_in_the_netlist_and_costs_no_flip_flop`
runs exactly that mutation, so the number is reproducible from the test
suite and not only from a shell.

**THE TWO CAMPAIGNS, AND THE ORDER IS THE ARGUMENT.** The split baseline
is measured on `4b77af1`'s RTL — the design before this work — because a
split measured on the hardened design could not say what the split found:

```
git stash            # or measure at 4b77af1 in a worktree
hw/soc/flow/fi_npu.sh          hw/soc/out/h56-split
hw/soc/fi/npu_campaign.py --build hw/soc/out/h56-split --draws 100 --jobs 18
git stash pop
```

then the campaign of record and the verbatim replay against it, on the
hardened build:

```
hw/soc/flow/fi_npu.sh          hw/soc/out/h56-npu
hw/soc/flow/fi_npu_coverage.sh hw/soc/out/h56-npu
hw/soc/fi/npu_campaign.py --build hw/soc/out/h56-npu --draws 100 --jobs 18

hw/soc/fi/npu_campaign.py --build hw/soc/out/h56-npu \
    --directed <h56-split/records.csv, cfgreg rows removed> \
    --jobs 18 --out hw/soc/out/h56-replay
```

**THERE IS NO SECOND BUILD FOR THE REPLAY AND THAT IS THE POINT.**
`docs/55` needed one — its `FI_CFG_READBACK=0` variant — because it
changed the workload; this wave does not, so the campaign of record and
the replay run against the same image and the same measured window.
Section 8.1.

`h56-split`'s `cfgreg` rows are removed for `docs/55` section 13's
reason one width up: the three replicas are 25 bits now and were 21 then,
so bit *k* of the word is a different field. The paths still exist, which
is worse than their not existing — `npu_campaign.py` would replay them
happily — so they are removed deliberately and this sentence is the
record of it.

**And the report is checked against itself rather than trusted:**

```
diff <(sed -n '/^1. CLASSIFICATION/,$p' hw/soc/out/h56-npu/campaign.log) \
     <(sed -n '/^1. CLASSIFICATION/,$p' <replay dir>/campaign.log)
```

Three integer columns were added to the replay's coercion list with the
three new record fields — `oh_to`, `oh_req_max` and `aer_mm` — because a
column left out of that list is a column `csv` hands back as a string,
and a non-empty string is truthy. `docs/55` section 13 records that
defect surviving being looked at; the only thing that catches it is
running the replay and diffing.

---

## 15. What the next block should be

**1. `ev_seq` as one protected word, and it is the last hardening this
block has a measurement for.** Section 11 item 1: `ev_state` at 7 of 20
is the largest single site left in the connection, `cap_wr_en` at 5 of 8
and `inj_rd_en` at 1 of 4 are in the same 19-bit bundle, and the bundle
is the only answer for any of them because every one of them is a
one-bit flag. **38 flip-flops and an FSM rewritten as a combinational
next-value function** **[estimate]**, which is `docs/41` section 6.5's W6
in a second place — including its warning that the refactor must not be
measured against the old design. After it, everything left unprotected in
this block is unprotected because a campaign measured it at zero.

**2. `BUSSTAT`, which `docs/55` section 14 item 2 ranked and this
document has now made worse in the only way available to it.** That block
is 126 unprotected flip-flops whose whole job is to be believed; H4 and
H5 declined to add a fourth NPU counter to it precisely because of that
ranking, and the cost of declining is that both of this wave's reports
are **write-1-to-clear cause bits with no durable record anywhere**
(section 12). Nothing has measured `BUSSTAT`. `docs/41` section 3.1's
criterion applies without amendment and the cheap version is not TMR: it
is bundling the four stickies and the enable register into one protected
word, which is 11 bits.

**3. Place and route with the NPU in it, which has now been the largest
unmeasured thing for three documents.** `docs/51` section 11 made it the
open question at 76 % of Ibex by cell area; `docs/55` added 8,014 um2 to
the connection and 4,796 to `BUSSTAT` and measured no frequency; this
adds 1,471 more and **puts a four-bit state comparator in the path to the
die's AER pins** without an STA run at any corner. Every hardening wave
since `docs/51` has enlarged that question and none has touched it.

**AND ONE THING THAT IS NOW A METHOD RATHER THAN A FINDING.** `docs/52`
found the largest structure in the connection carrying none of its rate;
this document found the same thing one level down, on a different
structure, with a different mechanism behind it — and in both cases the
reason is **occupancy**, not robustness. A queue slot nothing reads and
an event word that is only live for a few cycles per event are the same
argument. **The corollary is the one worth carrying forward: in an
event-driven design the risk is in the control flags, and a flag is
exactly the thing the replication bound says cannot be tripled on its
own.** Every hardening this block has taken — `docs/55`'s bundle,
`docs/55`'s two bounds, H4's bound and H5's gate — is a way around that
bound, and section 11 item 1 is the last one it has left.

**The whole-SoC invariant is still 215,428 cycles** and every document
after this one should go on quoting it. Section 8.4 is why it did not
move.
