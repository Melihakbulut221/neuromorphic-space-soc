# 55 — Hardening the NPU connection, in the order the campaign ranked

`docs/52-npu-connection-fault-injection.md` measured the connection —
700 injections, seven strata, each run twice — and section 12 ranked
what to protect **by consequence rather than by size**. This document
builds that ranking, in that order, and re-runs the campaign against
what it built.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
an intention with nothing behind it yet.

**The pilot is untouched.** `docs/34` pins the TTIHP26b submission by
git blob hash and the shuttle closes 2026-09-21. Nothing in `hw/rtl/`,
`hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is modified; seven files in
`hw/rtl/` are **read and instantiated**, `hw/soc/flow/fi_npu.sh` still
refuses to elaborate if `git diff` over `hw/rtl/` is not empty, and
`sw/tests/test_soc_npu_guards.py` checks the blob hashes **[fact]**.
Section 12 lists every file touched.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| Did the hardening move the number it was built to move? | **Yes: 7 of 7 dead machines became 0, and 2 visible corrections became 75.** Every one of `docs/52`'s seven records was replayed verbatim — same site, same bit, same cycle — and each names the mechanism that saved it. Section 8.2 |
| And on a fresh campaign? | **0 dead machines in 700, with the watchdog held off for the whole run** **[fact]**. `docs/52`'s disarmed column carried seven. The backstop is no longer load-bearing for this block. Section 8.6 |
| Does the cause register still invent faults? | **No: 0 of 100, against `docs/52`'s 16.** The voter fired on all 100 draws into the bank, masked all 100, and reported 94 of them — the six it did not are the six drawn after the program's last read. Section 8.6 |
| What replaced them? | **A bus error the program can handle, and a named cause bit**, instead of a watchdog stage-2 system reset. Section 8.2 |
| Can the new bounds fire on a healthy part? | **The transport's cannot, and that is proved rather than measured**: `hw/soc/formal/soc_npu_ser_props.v` I10 states the guard as an exact function of the frame position and I11 concludes it stays below the bound, at both parameter points **[fact]**. The window's is measured instead, twice, and section 4.3 says why it can only be measured |
| Can an operator see the connection's protection now? | **Yes, and the campaign reads it with a load instruction.** On the same draws, the queues absorbed 80 upsets and the program saw **75 of them in `IRQ_CAUSE` and every one of them in `BUSSTAT`** — 74 corrections and 6 discards, the same numbers the bench counted. `docs/52`'s figure was 2. Section 8.2 |
| What did tripling the cause bank cost? | **+42 flip-flops and 4,708.8594 um2 against the right baseline** — the same design with `HARDEN = 0`, same file list, same recipe **[fact]**. Section 7 |
| Is the redundancy still there in the netlist? | **Three banks of 21 flip-flops, with every `keep` and `keep_hierarchy` deleted from the text of the sources** **[fact]**, and the mutation that would collapse it is measured collapsing it. Section 9.4 |
| *Re-measured 2026-09-07 by `docs/75` section 3.3* | The 21 was right, and so is the 25 the word became when `docs/56` widened it. Re-counted by the voter's fan-in cone, which depends on no name: **25 / 25 / 25 in the block synthesis and in every whole-SoC netlist in the tree that contains this block**, the three cones disjoint. A census by Q-net name would have said 25 / 12 / 13 — `dfflibmap` builds a reset-to-one flip-flop behind an inverter and the resulting cell carries no name — but no count this document published was taken that way |
| Is the whole-SoC invariant still 213,971 cycles? | **The RTL hardening costs zero cycles and reproduces it exactly** **[fact]** — both bounds, the orphan check, three fault lines and a tripled bank, measured against `07f0dd6`'s own program. The invariant becomes **215,428**, and all 1,457 of those cycles are software: 1,348 of them are section 3's read-back. Section 8.5 measures it three times so the two cannot be confused |
| Did it move the silent-corruption rate? | **No, and the campaign carries the control that says so.** 36 of 616 became 29, and the FROZEN die's own stratum — silicon that cannot have changed — moved by one with fifteen records changing verdict. The movement is workload drift. Section 8.3 |
| What was deliberately left alone? | **`evq_data`** — 41.2 % of the connection's flip-flops and 53.5 % of its area, and zero silent wrong inferences in 100 draws. Section 6 |
| Did anything get worse? | **Yes, and it is named rather than netted off**: 20 new unprotected flip-flops whose corruption *fails a healthy access* instead of hanging it. Section 6.2 |

---

## 2. What was built, and the order it was built in

`docs/52` section 15 ordered the work and the order is not the order of
increasing difficulty. It is followed here without re-deriving it, and
sections 4.3 and 8.3 record the two places the measurement during the
work disagreed with the expectation: `docs/52`'s "all one mechanism" was
three, and the silent-corruption rate — which this ranking never aimed
at — did not move beyond the noise.

| | What | The number it rests on |
|---|---|---|
| **1** | Read back every configuration register the bring-up wrote | 14 of 265 bring-up-phase draws corrupted the inference; the sequence's own read-backs caught 3 |
| **2** | Bound the transport's frame and the window's response | 7 of 7 dead machines. `docs/52` called them "all one mechanism"; section 4.3 found they are three, and the correction cost a rebuild |
| **3** | Give the queues' protection somewhere to report | 79 absorbed upsets, 0 visible |
| **4** | Triple the control and cause bank | a false fault report in 16 of 100 draws |
| **5** | **Nothing for `evq_data`** | 0 silent wrong inferences in 100 draws over 41.2 % of the block |

Items 3 and 4 were built together, as `docs/52` section 15 recommends,
because both are about the cause register and re-hardening one bank
twice would be wasteful.

---

## 3. Item 1: the configuration read-back, and which half it closes

`docs/51` section 18 wrote a condition under which the campaign could
invalidate a decision that document had just taken, and `docs/52`
section 11.4 met it: an upset in the transport's address field sends a
configuration write **to the wrong register**, and the one read-back the
bring-up did — `CFG_THRESH` — read the register that was *not*
corrupted and passed. The clearest record is `ser.tx` bit 32 at cycle
3,081, which is `ADDR[0]` of the 40-bit frame **[fact, `docs/52`]**.

Both bring-up sequences now read back **every** configuration register
they wrote. The list is generated once, by
`hw/soc/flow/gen_npu_vectors.py`, from the same source the writes come
from — a program that spelled the list out for itself would be a program
that stopped checking a register the day one was added.

**IT CLOSES HALF OF ONE CLASS AND THIS SECTION IS PRECISE ABOUT WHICH
HALF.** `docs/52` section 12 item 4 is the arithmetic: of the eleven
bring-up-phase records that corrupted the inference and passed every
check the sequence did,

- **six** are in the transport on one side of the pin boundary or the
  other — the class a read-back of the committed value does see;
- **five** are in the **event engine** — the show-ahead adapter and the
  AER strobe, which are not configuration at all and which no
  configuration read-back can ever see **[fact, `docs/52`]**.

**AND IT DOES NOT COVER THE WEIGHT ARRAY AT ALL.** `docs/10` section 10's
map has no weight read port. A weight word corrupted on the way in is
stored as a **valid SECDED codeword of the wrong value**: `CNT_SEC` and
`CNT_DED` stay at zero, the program's check of them passes, and the
inference comes out wrong with a clean bill of health. Closing that
needs a register the die does not have — a weight read port or a
checksum — and that is a full-scale-node requirement rather than a
change to this SoC. `docs/10` section 14 is where it belongs.

**What it costs, measured: 1,348 cycles once per bring-up** **[fact,
the difference of two whole-SoC runs]**. It is the only item in this
document that moves the whole-SoC cycle count at all — the RTL costs
zero — and section 8.5 measures the invariant three times so that the
two can never be confused with each other.

---

## 4. Item 2: bounding the frame and the response

### 4.1 The measurement, and the pattern that had not been applied

`docs/52` section 7.1 is the sharpest finding in that document:

> **THE ONLY WAY THIS BLOCK KILLS THE MACHINE IS BY LOSING THE FABRIC
> RESPONSE** … Four draws into `ser.tick` — the transport's half-period
> counter — one into `ser.state`, and two into `win_state`. Nothing else
> in 600 connection draws produced a dead machine.

The chain is one sentence: a corrupted phase leaves a frame that never
ends → `busy_o` never falls → `win_state` never leaves `W_WAIT` →
`rvalid` never returns → Ibex, a two-stage in-order machine that stalls
the pipeline on a load, waits for ever.

`soc_npu_ser.v`'s own header said, until this work, that the transport
*"has no timeout. A frame always completes in a fixed number of cycles
because nothing in the protocol can stall it"* — **true of the protocol
and false of the silicon**.

**The two precedents were found and followed rather than a third shape
invented.** `hw/rtl/pilot_top.v` section 8 bounds its dispatcher's
`D_FETCH` wait, because `docs/16` section 5.1 measured five HANGs there
and no fault indication at all; `soc_npu.v` bounds its own
injection-queue fetch for the same reason, and `docs/52` section 7.2
measured that bound converting a lost inference into a correct one on
one record in three. Both are: a counter, a comparator, a forced return
to idle, and a report. Both bounds below are the same four things.

### 4.2 The transport's frame bound

`soc_npu_ser.v` gains a counter that runs for as long as a frame is in
flight. At `GUARD_MAX` it forces `ST_IDLE`, releases the select, and
raises a new `timeout_o` beside `done_o`. The node window turns that
pair into a **bus error**, which is a load or store access fault the
program can handle, and latches `IRQ_CAUSE.SER_TO`.

**The bound is derived and not written down**:

```
HALVES_FRAME = 2 (setup, H2) + 2*NBITS (shift) + 3 (gap, H3) = 85
GUARD_MAX    = (HALVES_FRAME + HALVES_SLACK) * HALF          = 174
GUARD_W      = $clog2(GUARD_MAX + 1)                         = 8
```

at `HALF = 2` **[fact]**. Four things about it are decisions:

**The comparison is `>=` and not `==`.** An upset that pushes the
counter *above* the bound must expire now; with `==` it would count up,
wrap, and take another 2^8 cycles — which is the stall the mechanism
exists to stop, rebuilt inside its own guard.
`test_the_frame_bound_expires_on_greater_or_equal_and_not_on_equal`
checks both guards for it.

**It aborts a frame the die is still inside, deliberately.**
`pilot_top.v` P4 commits a write on the fortieth rising edge, so an
aborted *write* changes nothing on the die and an aborted *read* has
already had its side effect. The alternative — clocking out the
remaining edges of a frame whose phase state has just been shown to be
wrong — is driving a protocol from a register known to be corrupt.

**An aborted frame returns zero, and `timeout_o` says so.** A caller
that ignored the flag must not be able to read a partial frame as a
register value; formal property D1c is that statement and D1b is that
`timeout_o` never rises without `done_o`.

**The guard is itself unprotected state.** Section 6.2.

### 4.3 The window's bound, which was built wrong first

The transport's bound covers four of the seven dead machines. The other
three were drawn into `win_state` and `ser_state`, and **the first
version of the window's bound caught only one of them.** That is
section 8.2's measurement and it is the most useful thing this document
found, so it is stated here rather than tucked into the results.

The first version ran a counter while `win_state` was `W_ISSUE` or
`W_WAIT`, on the natural reasoning that those are the two states that
can wait for ever. Replayed against `docs/52`'s seven records, five
survived and **two were still dead with `win_to` reading zero — the
bound had not fired at all**. The failure was not the one the
state-armed version modelled:

| the record | what actually happens |
|---|---|
| `win_state` bit 1 at cycle 566 | `W_WAIT` (2) → `W_IDLE` (0). The window does not *wait* for ever, it **forgets** that it was waiting. A granted request is unanswered and nothing is counting |
| `win_state` bit 0 at cycle 5,658 | `W_IDLE` (0) → `W_ISSUE` (1). The window is **busy with nothing owed**: it issues a frame nobody asked for and raises `rvalid_o` with no grant behind it. `soc_bus.v` keeps one response-ownership queue per slave and rule 3 is exactly one `rvalid` per granted request, so a spurious one puts that queue out of step and every later response goes to the wrong master |

**Both are facts about the fabric handshake and not about this FSM's
encoding**, and both are answered from one bit that records the fact:
`win_out`, set by `gnt_o` and cleared by `rvalid_o`. Two mechanisms fall
out of it, and they are duals:

- **the bound** — a response is owed and has not come: fail the access,
  which is the same load access fault the transport's bound produces;
- **the orphan check** — the window is not idle and owes nothing: return
  to `W_IDLE` and **say nothing**. Returning a response here would
  manufacture the very thing that made that record fatal.

Both raise `IRQ_CAUSE.WIN_TO`. One cause bit for both, because what an
operator has to know is that the node register window had to repair
itself; a second bit would be three more flip-flops in the protected
word for a distinction no recovery policy acts on differently, and the
two are told apart at the bench instead.

**The orphan check is unreachable without a fault by construction, not
by argument.** `win_out` is set on the same edge as the only transition
out of `W_IDLE` — both arms of it, `W_ISSUE` for a good access and
`W_RESP` for a bad address — and cleared by the `rvalid_o` that `W_RESP`
raises as it returns to `W_IDLE`. The two move together in every cycle
of a healthy access.

> **THE STATE-ARMED VERSION WOULD HAVE SHIPPED IF THE CAMPAIGN HAD NOT
> BEEN RE-RUN AGAINST THE RECORDS IT WAS BUILT FROM.** It passed the
> whole regression, both cocotb bound tests, every formal task and every
> netlist census. What caught it was replaying seven specific
> injections and reading a column that said the mechanism never fired.

`WIN_MAX` is derived from the transport's bound and from the arbiter's
worst case, term by term:

```
an engine frame already in flight, at the transport's own bound   SER_GUARD_MAX + 2
the cycle W_ISSUE sees the transport idle, and the start pulse    2
the window's own frame, at the same bound                         SER_GUARD_MAX + 2
```

which is 354 at `SER_HALF = 2`, and the bound is 16 cycles above it at
**370** **[fact]**. The margin is small on purpose: every cycle of it is
a cycle a stalled CPU spends stalled, and the whole point is that it is
cheaper than the system reset the watchdog answered with.

**THE TWO BOUNDS HAVE DIFFERENT KINDS OF EVIDENCE AND THE DIFFERENCE IS
REAL.** A serial frame's length is an exact function of the state
encoding, so the transport's bound can be *proved* unreachable on a
healthy frame — and is, by I10 and I11. A window's wait depends on what
the event engine happens to be doing, so its worst case is an **argument
about the arbiter**, and an argument is not a measurement. It is
therefore measured twice:
`test_the_window_bound_never_fires_on_a_healthy_access` runs an
inference with the engine contending for the transport and reports the
largest `win_guard` it saw, and the campaign's clean run is a second,
longer one. **Section 4.3's defect is what that difference costs**: the
half of this block that could only be measured is the half that was
built wrong.

**Verilog-2005 gives an instantiating module no way to read a
submodule's localparam**, so `soc_npu.v` restates the transport's frame
arithmetic. `test_the_two_bounds_are_derived_from_one_frame` parses both
files and fails if they disagree — `docs/40` section 7.4 records what
one literal bit position written in two places cost `soc_wdog.v`, and a
frame length that grew in one file and not the other would give up on a
frame that was still legally in flight, intermittently, on a healthy
part.

---

## 5. Item 3: the queues' protection, given somewhere to report

`docs/52` section 10 counted every mechanism in the connection at the
bench:

> **SEVENTY-NINE UPSETS WERE ABSORBED BY MECHANISMS THAT WORKED, AND NO
> SOFTWARE AND NO PIN COULD SEE ANY OF THEM.** In silicon a corrected
> pointer upset is indistinguishable from no upset at all.

`soc_npu.v` brought `ptr_mismatch` and `par_err` out of both `aer_fifo`
instances and connected them to nothing; `rv_mismatch` was not brought
out at all, on a flag `aer_fifo.v`'s own header calls *"the design's
most dangerous small state"*.

**They now go to two places, and `docs/51` section 14 item 1's objection
is answered rather than overruled.** That objection was that a
fault-counter block invented inside `soc_npu.v` would put NPU-only
telemetry outside `BUSSTAT`, *"which `docs/41` owns"* — which is an
argument about **where the counters live**, and the counters live in
`BUSSTAT`.

- **A sticky bit each in this block's own cause register**, `Q_COR` and
  `Q_DET`, so an S2 supervisor reading `IRQ_CAUSE` sees them;
- **a saturating counter each in `BUSSTAT`**, at `0xFF915000 + 0x1C` and
  `+0x20`, in the slot the frozen map has reserved since `docs/39`.

**They are two and not one.** A pointer vote that *corrected* lost
nothing; a discarded entry or a held-low `rd_valid` **lost an event**. A
mission reading a rising `NPUDET` is reading dropped work and a mission
reading a rising `NPUCOR` is reading the environment. Folding them would
reproduce exactly what `pilot_top.v`'s header records costing it — *"a
host reading `CNT_SEC` cannot tell a synapse array correction from a
load-path one"* — and `docs/44` section 6.2 makes the same argument for
the four counters that were already there.

A third counter, `CNT_NPUTMR`, carries the cause bank's own voter, and
it is separate from `CNT_TMRERR` for the same reason: a watchdog vote
and an NPU vote are different parts with different remedies.

**THE MEASUREMENT SAYS THE TWO COUNTS ARE THE SAME NUMBER AND NOT AN
APPROXIMATION OF IT.** Over the 616 replayed injections, the bench
counted **74** pointer-vote corrections and **6** discards, and the
program read **74** out of `BUSSTAT.CNT_NPUCOR` and **6** out of
`CNT_NPUDET` with load instructions it executed **[fact]**. That
equality is the whole claim: `docs/44` section 8.2's distinction is that
a counter a testbench reads is not a counter an operator can see, and
the only way to show the second now exists is to put both in the same
table.

**What it costs to be told.** Every absorbed upset now sets a sticky
cause bit, so a run that would have been MASKED is DETECTED. In the
replay 70 records moved from CORRECTED to DETECTED **[fact]** — the
class boundary moving because the part learned to speak, not because
anything got worse. `docs/16` section 1.6's warning still applies in the
other direction: detected is recoverable, not harmless.

---

## 6. Item 4: the cause bank, and item 5: nothing for the queues

### 6.1 Tripling thirteen bits, which turned into twenty-one

`docs/52` section 11.2 measured the unprotected cause register producing
a **false fault report in 16 of 100 draws** — the highest per-bit
consequence anywhere in that campaign — and section 6.3 put the shape of
it plainly: it is **not a missed fault, it is a fabricated one**. A
fault-reporting channel that invents events is worse than one that is
merely lossy, because it will be believed, and every recovery policy
`docs/09`'s S2 supervisor might implement reads this register.

`docs/41` section 3.1's criterion — **persistence times silence** —
selects exactly these bits: software writes them once, the block never
rewrites them, and nothing votes, scrubs or reports them.

**The replication bound is real and the bundle is the answer.**
`hw/rtl/pilot_top.v` section 8.2 proves three replicas cannot be held
apart over one bit — there are exactly two storage functions, `x` and
`~x` — and `docs/30` section 3.3 generalises it: three bits is the first
width at which a third replica has a function left to take. **Nine of
the eleven fields here are one bit wide.** Naive replication would give
a netlist with one flip-flop and a voter voting it against itself, and
every test and every proof in this repository would still pass. So they
are concatenated into one word and the **word** is replicated, which is
`docs/41` section 4.2's move.

The word is **21 bits and not 13**, and the growth is the reports of
sections 4 and 5 arriving in the same register:

| Field | Bits |
|---|---:|
| `ctrl_in_en`, `ctrl_out_en` | 2 |
| sticky causes: `INJ_OVF`, `FETCH_ER`, `SER_TO`, `WIN_TO`, `Q_COR`, `Q_DET`, `CFG_TMR` | 7 |
| `irq_mask`, one bit per cause | 12 |
| **PROT_W** | **21** |

**Two things are inside the word on purpose and one is outside it.**

`sticky_cfg_tmr` — the voter's own report — is a **field of the bank**
and not a register beside it, so the write that repairs a replica and
the write that records the repair are the same write on the same edge.
`docs/16` section 5.8 measured the other arrangement costing this
repository its safety-net announcement: an upset could erase the record
of the very event it caused.

`flush_pulse` and `scrub_pulse` are **outside** it, and that is
`docs/41` section 3.1's rule applied rather than ignored: the block
rewrites both to zero on every clock edge, so they shed an upset within
one cycle and there is nothing for a vote to protect. Bundling them
would cost four more flip-flops for a hold time of one cycle.

**One deliberate divergence from `docs/41` section 5.3.** The watchdog's
`tmr_err` is not clearable, on the rule that a record software can erase
is a record an upset can erase. Here every sticky cause bit **is**
write-1-to-clear, including this one, because `IRQ_CAUSE` is an
*interrupt cause* register whose entire contract is acknowledgement: a
bit in it that could not be acknowledged would hold an enabled interrupt
line asserted for ever, which is `docs/40` section 7.2's brick in a new
place. The durable record lives in `BUSSTAT`'s saturating counter
instead, which is `docs/44` section 6.4's argument for the same choice.
**That decision has a measured cost of exactly one flip-flop** and
section 9.4 is where it turned up.

### 6.2 What was deliberately left alone, and what got worse

**`evq_data` is untouched, and the campaign of record confirms the
decision rather than merely leaving it standing.** It came back **100 of
100 MASKED** — not one record in the largest structure in the block
produced anything at all **[fact, section 8.6]**. It is 37.6 % of the
connection's flip-flops now that the block has grown, was 41.2 % when
`docs/52` measured it, and is 53.5 % of its area (`docs/51` section 11);
both campaigns measured it producing **zero silent wrong inferences in
100 draws**. The reason is not robustness, it is occupancy: the queues
hold a couple of live entries out of eight, so most of those 304 bits
are storage nothing will read. **A hardening wave that started with the
biggest structure would have spent its whole budget there.**
`test_the_queue_storage_is_left_alone_on_purpose` is a test for the
presence of that argument, because there is no way to test for the
absence of a future protection.

`evq_ptr` is likewise untouched: it already carries `aer_fifo`'s pointer
voting, and what it lacked was a report, which is section 5.

**And this work made something worse, which is stated rather than netted
off against the wins.** The two bounds are **twenty new unprotected
flip-flops** — eight of `u_ser.guard`, one of `u_ser.timeout_o`, nine of
`win_guard` and one of `win_out` — whose corruption **aborts a healthy
frame or fails a healthy access**, and in `win_out`'s case can also
*re-open* the hang the bound closes or manufacture one spurious
response. The trade is a bus error on a run that would have been
correct, against a system reset on a run that was dead. That is a trade
and not a free win; all twenty are in the campaign's site list, and
section 8.4 reports what the draws found in them rather than assuming.

---

## 7. Measured area

Same recipe as `docs/39` section 6, `docs/40` section 9, `docs/41`
section 6.5 and `docs/51` section 11: Yosys `stat -liberty` on
`ihp-sg13g2` typical, `abc` with the same driving cell, the same load
and the same 20 ns delay target. Gate equivalent = `sg13g2_nand2_1` =
7.2576 um2. The Ibex reference is **275,682.6198 um2**.

**EVERY BASELINE ROW WAS RE-MEASURED AT `07f0dd6` RATHER THAN QUOTED**,
because `hw/soc/flow/syn_soc.sh`'s own header records that a per-block
area reproduces against *the file list as it stood on the day* and this
work changes three files in that list.

| Block | Cells | Flops | Area, um2 | kGE |
|---|---:|---:|---:|---:|
| `soc_npu_ser`, baseline | 581 | 134 | **10,773.5670** | 1.484 |
| `soc_npu_ser`, with the frame bound | 717 | 143 | **11,931.1920** | 1.644 |
| `soc_busstat`, baseline | 442 | 72 | **7,060.5486** | 0.973 |
| `soc_busstat`, with three NPU counters | 713 | 126 | **11,856.6882** | 1.634 |
| `soc_npu`, connection only, baseline | 2,740 | 717 | **57,852.2196** | 7.971 |
| `soc_npu`, connection only, `HARDEN = 0` | 3,024 | 744 | **61,157.8296** | 8.427 |
| `soc_npu`, connection only, hardened | 3,303 | 786 | **65,866.6890** | 9.076 |
| `soc_npu`, whole subsystem, baseline | 12,421 | 2,008 | **209,739.0834** | 28.899 |
| `soc_npu`, whole subsystem, hardened | 13,066 | 2,077 | **218,407.9842** | 30.094 |

**[fact for every measured row; the kGE column is arithmetic on them]**

> **THE WHOLE WAVE COSTS +8,014.4694 um2 ON THE CONNECTION AND
> +4,796.1396 um2 IN BUSSTAT — 12,810.6090 um2, WHICH IS 4.65 % OF THE
> UNPROTECTED IBEX CORE** **[estimate, the sum of two differences of
> measured rows]**.

Four readings.

**The baseline for item 4 is `HARDEN = 0` and not the old design, and
`docs/41` section 6.5 is why.** That baseline carries the two bounds,
the three fault lines and the wider cause register, and differs from the
hardened build in exactly one thing: whether the protected word is one
bank or three. Measured that way, **tripling the bank costs +279 cells,
+42 flip-flops and 4,708.8594 um2** **[estimate, the difference of two
measured rows]**. Quoting it against the old design instead would put it
at 8,014.47 and credit the redundancy with the two bounds and the three
fault lines as well.

**The flip-flop arithmetic closes, and where it does not the difference
is attributed rather than absorbed.** The RTL census counts **+71
bits** — `u_ser.guard` 8, `u_ser.timeout_o` 1, `win_guard` 9, `win_out`
1, and the cause bank's 65 against 13 — and the mapped netlist counts
**+69**, 717 → 786. The two missing bits are in the **event engine**,
which this work did not touch: section 9.4 attributes every mapped
flip-flop by source line and finds `soc_npu_ser.v` holding its whole
stratum of 143, the three banks holding 21 each, and `win_out` present
as its own cell. The `HARDEN = 0` row splits the delta the same way:
+27 for everything but the redundancy, +42 for the redundancy, and 42 is
exactly 2 x PROT_W.

**The connection-only and whole-subsystem deltas disagree by 654.4314
um2 at the identical +69 flip-flops**, and that is mapping noise rather
than a finding: `syn_soc.sh`'s header records that Yosys is entitled to
map a design differently when the design it was given is different, and
here the difference is the whole of `pilot_top`. Both rows are given;
neither is corrected against the other.

**`soc_busstat` grows by 67.9 %, and it is three counters.** 54
flip-flops is exactly 3 × (16 counter bits + 1 sticky + 1 enable), and
`test_the_fault_counters_survive_synthesis` derives that from the
module's own `NSRC` and `CNT_W` rather than writing 126 down. It is the
largest proportional cost in this document and it buys the only thing
that distinguishes *"the protection has never fired"* from *"the
protection is broken"*.

**No frequency was measured for any of this.** None of it has been
through STA at any corner or through place-and-route. `docs/51` section
11's closing paragraph applies unchanged, and section 10 repeats it.

---

## 8. The campaign, re-run

### 8.1 Two runs, and why the delta needs the first one

`docs/52` drew every injection from a **measured** window, so a change
to the workload changes the cycles it draws. This work changes the
workload — section 3's read-back, and three `BUSSTAT` reads — so a fresh
campaign and `docs/52`'s campaign do not share their draws and a
difference between them would be a difference of two things.

So there are two runs:

| | build | what it answers |
|---|---|---|
| **the directed replay** | hardened RTL, `docs/52`'s workload (`FI_CFG_READBACK=0`) | **the delta on the same draws**: every injection `docs/52` recorded, replayed verbatim — same site, same bit, same cycle |
| **the campaign of record** | hardened RTL, the shipped workload | the rate of the design that ships, over its own populations |

**The replay is 616 of `docs/52`'s 700 records and the missing 84 are
named.** Five `cfgreg` paths — `ctrl_in_en`, `ctrl_out_en`, `irq_mask`
and the two old sticky bits — **do not exist any more**: they are fields
of a bank. `npu_campaign.py` fails hard on a path it cannot find rather
than skipping it, which is how that was discovered rather than
tolerated, and it is the honest form of the statement that this stratum
cannot be compared record by record.

**Three controls changed and one is new**, and they are listed because a
campaign that quietly re-tunes its own controls is a campaign that can
report anything:

- **control 1b** now also asserts that all three cause-bank targets end
  in `.bits` — replica storage and never the voted wire — and that there
  are exactly three of them.
- **control 4a had to be rebuilt.** It deposited into `ctrl_in_en`, and
  a single deposit into one replica of a tripled word is masked by the
  vote, so the old control would have failed **on the design it was
  meant to certify**. It now flips bit 15 of the event engine's
  `cnt_in`, which only ever increments and ends the clean run at 22, so
  the flip cannot be undone and MASKED is impossible if the deposit
  landed. Moving the old control's threshold until it passed was the
  other option and it is the one `docs/52` section 5.1 says makes
  `docs/41` section 6.6's list longer.
- **control 4d is new** and it is the only control in this campaign that
  exercises a mechanism this work built: one deposit into replica A must
  be masked, must leave the inference right **by the model**, must raise
  `IRQ_CAUSE.CFG_TMR`, and must show up in `BUSSTAT.CNT_NPUTMR`. It
  failed on its first run and the *control* was wrong — it asked whether
  the whole published result matched, and the cause register is supposed
  to move. `docs/52` section 9's second finding, turned into a gate.

### 8.2 The delta, on the same draws

**616 injections replayed verbatim, each run twice** **[fact,
`hw/soc/out/h55-replay/directed.csv`]**.

| | `docs/52` | now |
|---|---:|---:|
| **dead machines** (disarmed run never finished) | **7** | **0** |
| queue mechanism fired | 81 records | 80 records |
| — of those, **announced to software** | **2** | **75** |
| silent wrong inference (model wrong, no NPU channel, no watchdog) | 36 | 29 |

> **SEVEN OF SEVEN. Every record that left the SoC dead now finishes,
> and every one names the mechanism that saved it** **[fact]**:

| record | was | now | mechanism |
|---|---|---|---|
| `u_ser.tick` bit 3, cycle 1,286 | DEAD | WRONG | frame bound |
| `u_ser.tick` bit 10, cycle 1,613 | DEAD | WRONG | frame bound |
| `u_ser.tick` bit 11, cycle 6,084 | DEAD | WRONG | frame bound |
| `u_ser.tick` bit 10, cycle 10,663 | DEAD | WRONG | frame bound |
| `u_ser.state` bit 1, cycle 3,245 | DEAD | WRONG | **window** bound |
| `win_state` bit 1, cycle 566 | DEAD | WRONG | **window** bound |
| `win_state` bit 0, cycle 5,658 | DEAD | WRONG | **window orphan** |

Two readings of that table are worth more than the count.

**`u_ser.state` is caught by the WINDOW's bound and not the
transport's**, which is not what the design's own headings predict. A
flip of `state` into `ST_IDLE` drops `busy_o` without a `done_o`: the
transport believes it is idle, so its guard is cleared and its bound
never runs, and the only thing left waiting is the window. **The two
bounds are not redundant with each other and neither alone is
sufficient** — one of the seven needs each of them, and the seventh
needs the orphan check.

**"WRONG" here means the run finished, not that the inference was
wrong.** Six of the seven produce a wrong inference and one does not;
what changed for all seven is that a system reset became a completed
run with a bus error and a named cause bit.

**The 2 → 75 is item 3, measured.** `docs/52` section 10's finding was
not that the queues' protection failed — it worked 81 times — but that
an operator could see two of them, and both of those only *by their
consequence*. Now 75 of 80 are announced through `IRQ_CAUSE`, and the
counts agree exactly with the bench: **74 corrections and 6 discards at
the bench, 74 in `BUSSTAT.CNT_NPUCOR` and 6 in `CNT_NPUDET` read by a
load the core executed** **[fact]**. Not an approximation of the bench's
count — the same number.

### 8.3 The silent-corruption rate barely moved, and the campaign says why

36 → 29 of 616 looks like a 19 % improvement and **this document will
not claim it**, because the campaign carries the instrument that says
how much of it is real.

| stratum | n | silent wrong inference, `docs/52` | now | records whose model verdict changed |
|---|---:|---:|---:|---:|
| `ser` | 100 | 12 | **8** | 18 |
| `die_ser` — **frozen silicon** | 100 | 11 | **10** | **15** |
| `engine` — **untouched by this work** | 100 | 9 | **9** | 0 |
| `window` | 100 | 3 | 2 | 1 |
| `cfgreg` (16 comparable rows) | 16 | 1 | 0 | 1 |
| `evq_data`, `evq_ptr` | 200 | 0 | 0 | 1 |

**[fact]**

**`die_ser` IS THE CONTROL, AND IT IS A GOOD ONE.** It is
`hw/rtl/pilot_top.v`'s own half of the transport — silicon `docs/34`
froze, which this work cannot have changed by any mechanism. Its verdict
changed on **15 records in 100**, for a net movement of one. That is the
workload drift: the program is 154 cycles longer and its measured window
128 cycles wider, so a deposit at a given absolute cycle lands up to
about 146 cycles earlier in program-relative terms — under one serial
frame, and enough to move a record across a class boundary.

**So the per-record comparison is not stable under this drift and the
aggregate is.** `ser`'s 18 changed verdicts against `die_ser`'s 15 make
its net movement of four indistinguishable from noise at this sample
size.

**`engine` is the second control and it is the sharper one.** This work
did not touch the event engine, and **not one of its 100 records changed
verdict**: 9 silent wrong inferences before and 9 after, the same
records. A stratum that is genuinely untouched, drawn from the same
seed, comes back identical — which is what says the 15 in `die_ser` is
drift in the *cycle* draw and not noise in the harness.

> **THE HARDENING MOVED THE NUMBER IT WAS BUILT TO MOVE AND DID NOT MOVE
> THE ONE IT WAS NOT.** Seven dead machines to zero and two visible
> corrections to seventy-five are the numbers `docs/52` section 12 items
> 1, 2 and 3 named. The silent-corruption rate was **never what this
> wave was aimed at** — `docs/52` section 12 item 5 explicitly declined
> parity over the shift registers that carry most of it — and it did not
> move beyond the drift. Reporting the 36 → 29 as an achievement would
> be claiming credit for the difference between two workloads.

**This is the third negative result of its kind in this repository and
the first one that was expected.** `docs/43`'s windowed watchdog and
`docs/49`'s `SYNPRE` were mechanisms built, proved, measured, and found
to be worth nothing on the workload that recommended them. This is not
that: the mechanisms here moved the numbers they were built for, and
what did not move is a number nobody claimed they would. The value of
saying so is that the alternative — quoting 4.17 → 2.56 from section 8.6
— was available, defensible-sounding, and wrong.

### 8.4 The new state, and what the draws found in it

This work added 20 unprotected flip-flops — `u_ser.guard` 8,
`u_ser.timeout_o` 1, `win_guard` 9, `win_out` 1 — whose corruption
**fails a healthy access** rather than hanging one, plus 63 in the three
replicas. All of them are in the campaign's site list, because a
hardening measured without its own new state is a hardening measured for
its benefit and not its cost. Section 8.6 reports what the campaign of
record drew there.

**One of the twenty is worse than the other nineteen and it is named.**
`win_out` is a one-bit record of whether the fabric is owed a response,
and it has two failure directions rather than one: cleared while a
request is outstanding, it **re-opens the hang the bound closes**; set
while nothing is outstanding, it produces **one spurious `rvalid`** after
the bound expires — which is the mechanism that made `docs/52`'s seventh
dead machine fatal, reachable from a different flip-flop. It could be
protected; the honest reason it is not is that the campaign has not
measured it costing anything, and this project's rule is that hardening
follows a measurement.

### 8.5 The whole-SoC invariant, measured three times

The invariant every document since `docs/40` uses as evidence that
behaviour did not change. This work changes **both** the RTL and the
program, so one number could not have told the two apart and three were
measured **[fact, all three with 27 of 27 checks passing and a zero fail
mask]**:

| build | cycles |
|---|---:|
| hardened RTL, `test_ibex.c` exactly as `07f0dd6` has it | **213,971** |
| + the configuration writes as a loop over the generated table | 214,080 |
| + reading every configuration register back — **the design of record** | **215,428** |

> **THE RTL HARDENING COSTS ZERO CYCLES**, reproducing `docs/51`'s
> number to the cycle on the final design — both bounds, the orphan
> check, three fault lines and a tripled cause bank, and the program
> runs identically. **The 1,457 cycles are software**: 109 for the loop
> form of the writes and **1,348 for the read-back**, which is
> `docs/52` section 12 item 4's price paid.

`test_ibex.c` carries `NPU_CFG_READBACK` so that the first row is
reproducible rather than historical, and the middle row is what a reader
gets from `SW_DEFINES=-DNPU_CFG_READBACK=0` today.

**Every document after this one should quote 215,428.**

### 8.6 The campaign of record

700 injections, seven strata of 100, each run twice — 1,400 simulations
against the design that ships, drawn over **its own** populations, which
are not `docs/52`'s: the connection now offers **809 injectable bits**
against 738, and `cfgreg` alone went from 13 to 65 **[fact,
`hw/soc/out/h55-npu/`]**.

**With the watchdog armed — the SoC as this document ships it:**

| stratum | bits | n | MASKED | CORRECTED | SDC | DETECTED | HANG |
|---|---:|---:|---:|---:|---:|---:|---:|
| `ser` | 143 | 100 | 83 | 0 | 0 | 17 | **0** |
| `window` | 89 | 100 | 93 | 0 | 0 | 7 | **0** |
| `cfgreg` | 65 | 100 | 6 | 0 | 0 | 94 | **0** |
| `engine` | 140 | 100 | 74 | 0 | **1** | 25 | **0** |
| `evq_data` | 304 | 100 | 100 | 0 | 0 | 0 | **0** |
| `evq_ptr` | 68 | 100 | 10 | 6 | 0 | 84 | **0** |
| **CONNECTION** | **809** | **600** | **366** | **6** | **1** | **227** | **0** |
| `die_ser` — frozen | 87 | 100 | 91 | 0 | 0 | 9 | **0** |

**[fact]**

> **THE DISARMED COLUMN IS IDENTICAL, ROW FOR ROW, AND THAT IS THE
> RESULT.** `docs/52` ran the same counterfactual and its disarmed
> column carried **seven dead machines**; here it carries none, so the
> watchdog never escalates and the two columns cannot differ. **The
> backstop is no longer load-bearing for this block** — 0 of 700, with
> `wdog_dis_i` held high for the whole run.

Four readings, and one of them is a caution about the fifth number
anyone will look for.

**`cfgreg` is the item-4 result and it is complete.** Of 100 draws into
the tripled bank, the voter fired on **100**, the model says the
inference was wrong on **0**, and no other mechanism in the block moved
at all **[fact]**. `docs/52` measured this stratum producing a
**fabricated** fault in 16 of 100 and a wrong inference in 4 of 100;
both are now zero. The 94 DETECTED are not false alarms in the other
direction either — every one of them is `IRQ_CAUSE.CFG_TMR`, a report of
a real upset that was really corrected. The six MASKED are the six draws
whose cycle fell **after** the program's last read of the cause
register, not six that were missed.

**The queues' counters agree with the bench except where they cannot.**
A queue mechanism fired on 79 records and 73 announced; the bench
counted 74 corrections and 5 discards, `BUSSTAT` read **73 and 5**. The
two records that differ were injected at cycles **13,769 and 13,771**,
and the measured window closes at **13,772** — the upset happened after
the program's last load. That is the harness's own edge and not a
counting error, and it is worth stating precisely because "the counters
agree" is the whole of item 3's claim.

**The one SDC is the first in this repository's NPU campaigns, and it is
not a wrong answer.** `oh_valid` bit 0 at cycle 13,308, replayed:
`sig` is `8c215696` — **the golden inference, bit for bit** — `fi_mask`
is zero, and what differs is `STATUS` (`0x22` against `0x2a`) and
`IRQ_CAUSE` (`0x01` against `0x00`) **[fact]**. A stuck `oh_valid` makes
the block report **"an event is waiting"** when none is, in both
registers, with no fault channel raised. It classifies SDC rather than
DETECTED because `C_EVT` is deliberately excluded from the announcement
test — it is a *level* meaning the capture queue is not empty, not a
fault report — which is `docs/52`'s own rule, correctly applied. **A
driver that polled `EVQ_OUT` on that signal would poll for ever.**
Nothing in this document addresses it and section 14 does not rank it;
it is one record.

**AND THE NUMBER NOT TO QUOTE.** The connection-weighted silent wrong
inference is **2.56 % ± 1.25** here against `docs/52`'s **4.17 % ±
1.60** **[fact for both]**, and *that comparison is not valid*. The
denominators are different populations — 809 bits against 738 — and most
of the movement is arithmetic on the change: `cfgreg` grew from 1.8 % to
8.0 % of the block while its contribution went to zero, and `ser` grew
by nine bits of guard that carry almost no consequence. **The comparison
that is valid is section 8.3's, on the same draws, and it says the rate
did not move beyond the drift.** Two numbers computed over two different
populations are two numbers.

| mechanism | records it fired on, of 700 |
|---|---:|
| the cause bank's voter | **100** |
| the frame bound | 7 |
| the window's bound | 3 |
| the window's orphan check | 3 |
| the engine's fetch bound (inherited from `docs/51`) | 2 |

**[fact]**

---

## 9. Verification

Four kinds of evidence, and the division between them is `docs/41`
section 6's: **each one is blind to what the others see**, and this
section says which is blind to what rather than presenting four green
ticks as one.

### 9.1 The regression, the Python suite and the cocotb suites

`hw/soc/flow/sim_soc.sh` runs the whole SoC — Ibex, the fabric, the
memories, the watchdog, `BUSSTAT` and the connection with the frozen die
inside it — through 27 checks. **All 27 pass, in all three of section
8.5's configurations, with a zero fail mask** **[fact]**.

`hw/soc/tb/cocotb/test_soc_npu.py`'s existing **21 tests pass
unchanged** **[fact]**: the hardening changed no behaviour the suite
already checked, which is the first thing that had to be true and the
easiest to skip past.

**378 Python tests pass**: 341 outside the synthesis guards and 37 in
them **[fact]**. The synthesis guards are section 9.4 and they are the
only 37 that look at a netlist.

### 9.2 Six new cocotb tests, and they inject faults

Six tests were added, and every one of them writes a flip-flop
hierarchically — which nothing else in that suite does. It is
legitimate here for a reason that is worth stating: **these mechanisms
only ever fire under an upset, and there is no legal stimulus that
reaches them.** The campaign of section 8 exercises them too; what these
add is that a failure **names the mechanism** instead of moving a rate
by half a point.

| Test | What it establishes |
|---|---|
| `test_a_stuck_frame_becomes_a_bus_error_and_not_a_dead_machine` | `u_ser.tick` corrupted mid-frame: the access returns `err`, returns zero, the transport is idle again, `IRQ_CAUSE.SER_TO` is set, no queue fault line moved, and the **next** access completes normally |
| `test_the_frame_bound_never_fires_on_a_healthy_frame` | over real frames with the pilot in the loop, `timeout_o` never rises and the largest guard is **exactly** `GUARD_MAX − HALVES_SLACK*HALF − 1`, so the bound, the frame and the declared slack are three numbers that agree rather than three that are merely consistent |
| `test_the_window_bounds_a_response_that_never_comes` | `ser_owner_win` flipped: the window gives up inside its bound, fails the access, sets `WIN_TO` and **not** `SER_TO`, and recovers |
| `test_the_window_bound_never_fires_on_a_healthy_access` | the arbiter's worst case, measured with the engine contending for the transport, and the bound checked to be neither below it nor absurdly above it |
| `test_a_single_upset_in_the_cause_bank_is_voted_out_and_counted` | the vote masks it, the replica is **repaired on the next edge** — the fault line is high for exactly one cycle, which is what says the scrub happened rather than that the vote merely hid it — `CFG_TMR` is set, and it is acknowledgeable |
| `test_the_queues_protection_reaches_a_register_and_a_pin` | a corrected pointer raises `Q_COR` and **not** `Q_DET`; a failed entry parity raises `Q_DET` |

**27 of 27 pass** in `test_soc_npu.py` and **10 of 10** in
`test_soc_busstat.py` **[fact]**, the latter widened from four sources
to seven **with a different count on every source**, because equal
counts would pass on a block whose sources all drove one counter — which
is the exact defect the separation exists to prevent.

**One of the six failed on its first run and the test was wrong, not the
design.** `test_a_single_upset_in_the_cause_bank_is_voted_out_and_counted`
compared the repaired replica against its value **before** the deposit.
The word does not come back that way, and it must not: the write that
repairs the replica is the same write that **records** the repair,
because `sticky_cfg_tmr` is a field of the bank (section 6.1). Asking
the bank to come back unchanged is asking it to forget the event it just
survived, which is the arrangement `docs/16` section 5.8 measured being
a single point of failure. The check is now against the **vote** — all
three replicas agree with `prot_store`, the mismatch is gone, and the
voted word is the old one plus the report bit.

**What they do not cover.** All of them deposit into **RTL**, so every
one would pass on a netlist in which the three replicas had been merged
into one, or in which a guard's counter had been deleted. That is
section 9.4's question and nothing here can answer it.

### 9.3 Formal

`hw/soc/formal/soc_npu_ser.sby`, four tasks — `bmc`, `prove`, `cover`
and `prove_h3` — **all four PASS** **[fact]**, at both parameter points.
`cover` reaches all six of its statements, the new one at step 163 and
the frame's own completion at step 173. Two new strengthening invariants
carry the frame bound's claim:

- **I10** states the guard as an **exact function of the frame
  position** — `hcnt`, `bit_cnt` and `tick` under the state encoding —
  which is a real check of its own: a guard cleared or held anywhere
  inside a frame would satisfy I11 while doing nothing.
- **I11** concludes `guard < GUARD_MAX`, which is the property that says
  **the bound cannot fire on a healthy frame**.

I11 is also what keeps P2 provable without weakening it. P2 says a
select is not released before the fortieth clock edge, which an aborted
frame deliberately violates; with I11 in the inductive hypothesis the
abort is unreachable and P2 needs no exception clause. **The exception
is therefore not written, and that is a decision**: an assertion
weakened by `&& !timeout_o` would still pass on a design whose bound
fired every frame.

Two new interface properties, D1b and D1c, say that `timeout_o` never
rises without `done_o` and that an aborted frame returns zero — a caller
that ignored the flag must not be able to read a partial frame as a
register value.

A new cover, C6, reaches the last cycle of a healthy frame. Without it
I11 would be satisfied by a design whose guard never left zero and I10
by one that never left `ST_IDLE`.

**And there is no equivalent for the window**, which is the asymmetry
section 4.3 turned into a defect. `soc_npu.v` has no property set at
all; the window's bound and its orphan check are covered by cocotb and
by the campaign, and by nothing that reasons over all states. That is
the largest single gap in this section and section 14 does not propose
closing it, because the two mechanisms are now measured working on the
records that motivated them and a proof would be evidence of a kind
rather than evidence of more.

**What formal does not cover, and it is the important half.** There is
no fault model here, so **nothing in this file can prove the bound
works**. It proves the bound costs nothing when there is no fault.
Section 8 is where the other half is measured, and `docs/43` section 9.4
is the record of why the two cannot substitute: all twenty formal tasks
stayed green on a design whose three banks the synthesiser had collapsed
into one.

### 9.4 The netlist census — the only check that looks at what the foundry would get

`sw/tests/test_soc_synthesis_guards.py` gains a section for this bank.
It is not inherited from the watchdog's: this bank is a different width,
a different reset domain and a different instantiating module, and the
only thing the two share is `soc_tmr_bank.v` itself.

| Check | Result |
|---|---|
| three banks of `PROT_W` in the mapped netlist | **21, 21, 21** **[fact]** |
| the same with every `keep` and `keep_hierarchy` **deleted from the text** of the sources, and `flatten` forced before synthesis | **no flip-flop lost** **[fact]** |
| `.MIX(0)` on replica C — functionally identical RTL, invisible to every simulation and every proof | **11 flip-flops lost**, one for each even bit of the 21-bit word, where `POL_C` is zero and a polarity-only replica C stores what replica A stores **[fact]** |
| `HARDEN = 0` | **42 lost**, and the replicas are gone **[fact]** |
| the instantiation, textually: one voter, three banks, three distinct `(POL, MIX)` pairs | **[fact]** |
| `u_ser.guard` and `win_guard` are nets in the mapped netlist, at their derived widths | **8 and 9** **[fact]** |
| the mapped flip-flops whose `src` names `soc_npu_ser.v`, against the bits the campaign's site list declares for that stratum | **143 = 143** **[fact]** |

**The last row is a question nothing in this repository had asked**, and
it is not the same one as the others. Every other census counts
flip-flops; this one asks whether the flip-flops in the netlist are **the
ones the fault-injection campaign believes it is injecting into**. The
campaign deposits into RTL — `docs/52` section 13's last bullet says so
plainly, *"the campaign cannot fail because a flip-flop vanished in
synthesis"* — so a guard whose counter the mapper had deleted would be
reported as working by the campaign, by every cocotb test and by the
formal proof, and the part would ship without it. Both sides of the
comparison are derived: the left from `hw/soc/fi/npu_targets.py`, the
right from the `src` attributes the netlist still carries after the
flatten that erases instance paths.

**It was worth building, because the mapped total came out two
flip-flops below the prediction and the prediction was not obviously
wrong.** The RTL census elaborates 801 bits for the connection and the
netlist holds 786; the baseline's figures are 730 and 717, so the gap
widened from 13 to 15. Attributing the mapped flip-flops by source
line settles it: `soc_npu_ser.v` holds **143**, which is the transport's
whole stratum including both new registers; the three banks hold 21
each; `win_out` is its own cell; and every missing bit is in the event
engine, where `ev_we` folds to a constant and `ev_addr` and `ev_wdata`
lose the bits that only ever carry constants. **Nothing this work added
was optimised away, and that is measured rather than assumed.**

**The `HARDEN = 0` row is 42 and the number written here first was 43,
and the test is what found it.** `docs/41` section 6.3 measured the
watchdog's `HARDEN = 0` at 53 and not 58, because with the mismatch wire
a constant its report fields are dead and the optimiser deletes them.
The same reasoning predicts that this bank's `CFG_TMR` bit goes the same
way. **It does not.** The difference is the **clear path**, and it is a
consequence of a decision made in section 6.1 for an unrelated reason:
the watchdog's `tmr_err` is unclearable, so its next value is
`tmr_err | 0`, which is `d == q`, which `opt_dff` folds into the reset
value; this block's sticky bits are write-1-to-clear, so the next value
is `q & ~clr`, and proving *that* constant needs a fixpoint no optimiser
in this flow runs.

> **THE CLEARABILITY DECISION COSTS EXACTLY ONE FLIP-FLOP, IN A
> CONFIGURATION NOTHING SHIPS.** It is recorded because the wrong number
> was written first, and because it is the whole reason `docs/41`
> section 6.1 derives its counts instead of writing them down.

The census is joined by two textual guards, because a census **cannot
see a change of parameters at the instance**: three replicas given the
same `POL` and `MIX` would census as three banks under `keep_hierarchy`
and collapse without it. `docs/41` section 6.6 names that gap and pairs
the same two checks for the watchdog.

And a third textual guard,
`test_the_npu_queues_report_their_protection_somewhere`, exists because
**no other check in this repository can fail on the defect it names**.
Every cocotb test, every proof and the whole fault-injection campaign
would pass on a `soc_npu.v` that left the queues' fault reports
unconnected — that is precisely the state `docs/51` shipped and
`docs/52` measured. The failure has a name in this project:
`pilot_top.v` left four ECC status wires unconnected, and a campaign
then classified 84 corrections as MASKED with every gate green.

---

## 10. What this does NOT cover

Worst first, and at length, because `docs/41` section 6.6 now lists
twelve instances of a green check read wider than the thing it examined
and `docs/52` found the twelfth in its own oracle.

- **The transport's shift registers are still unprotected and still
  carry the largest share of the silent corruption.** `docs/52` section
  12 item 5 declined parity over `tx` and `rx` and this document does
  not revisit it: it would be a check over a register that changes every
  half period, and it would not cover the die-side half of the same
  failure, which cannot be fixed at all. **The frame bound stops the
  transport killing the machine; it does nothing about the transport
  corrupting a frame.**
- **The event engine's state is unprotected**, and `docs/52` attributed
  1.71 of its 4.17 points of silent corruption to it. Nothing here
  touches it. Section 14.
- **The two new guards are unprotected state that can fail a healthy
  access**, section 6.2. That is a new failure mode this work
  introduced.
- **The window's bound rests on an argument about the arbiter, not a
  proof, and that argument was wrong once already.** Section 4.3. If a
  future change let the event engine interpose after the window has
  entered `W_ISSUE` — today it cannot, because `E_SER_RQ` and `E_DRN_RQ`
  both stand off on `win_wants` — the worst case would move and nothing
  but the two measurements would notice. `soc_npu.v` has no formal
  property set at all.
- **THE SAME-DRAWS DELTA IS NOT AS SAME AS IT SOUNDS.** Section 8.3
  measures it: the workload is 154 cycles longer and its window 128
  cycles wider, so a deposit at a given absolute cycle lands up to about
  146 cycles earlier in the program. Fifteen of the frozen die's 100
  records changed verdict on silicon that cannot have changed. **The
  site, the bit and the cycle are identical; the instant in the program
  is not**, and any per-record conclusion in section 8 that is not one
  of the seven dead machines has to carry that.
- **The seven dead machines are seven records**, and the campaign of
  record found no new class of them rather than proving there is none.
  `docs/52` drew 600 connection injections to find those seven; a
  mechanism that killed the machine once in a thousand draws would not
  be in either document.
- **`BUSSTAT`'s record is software-clearable** and a wild store to `CLR`
  erases it. That is `docs/44` section 6.4's stated exposure, inherited
  unchanged, and it now covers three more counters.
- **`BUSSTAT`'s counters are themselves unprotected**, 126 flip-flops of
  them. The block that counts corrections has no correction of its own,
  and nothing in this repository has measured what an upset in it does.
- **One workload, one stimulus, one geometry, one seed** — `docs/52`
  section 13's caveat, inherited whole, and section 8 inherits its
  conditional-on-the-injection-window reading with it.
- **RTL, single-bit, flip-flop only.** No gate-level netlist, no
  back-annotated timing, no multi-bit strike, no single-event transient
  in combinational logic. The connection's netlist has still never been
  simulated.
- **No frequency, no STA, no place-and-route** for any of this. The
  connection grew by 8,014 um2 and `docs/51` section 11 already made the
  floorplan question a larger one; this makes it larger again and
  measures none of it.
- **The interrupt is still never armed by any workload here**, so the
  five new cause bits are measured as a **report** and not as a branch.
  A spurious interrupt on a system whose handler acts on it is outside
  everything in this document.
- **The netlist census counts flip-flops and asserts nothing about any
  other cell**, examines `soc_npu` with the die black-boxed rather than
  the whole SoC, and says nothing about placement or routing —
  `docs/41` section 6.6's list, unchanged and still true here.

---

## 11. Corrections to earlier documents

**`docs/51` section 14 item 1** recorded the queues' fault reports
connected to nothing and gave the reason. The reason was about where
counters live, the counters now live in `BUSSTAT`, and that item is
closed. **`docs/51` section 14's "No hardening of anything this file
adds"** is superseded by `soc_npu.v` header section 6.

**`hw/soc/rtl/soc_npu_ser.v`'s header said "It has no timeout. A frame
always completes in a fixed number of cycles because nothing in the
protocol can stall it."** That is true of the protocol and false of the
silicon, and `docs/52` measured five dead machines produced by exactly
that gap. The sentence is replaced, and the replaced text is quoted in
the file so the correction is legible rather than silent.

**`hw/soc/rtl/soc_top.v`'s header said "IS NOT hardened. No ECC, no
scrubbing, no TMR, no bus error latch … the BUSSTAT and SCRUB slots in
the map are reserved and empty."** Four documents had made most of that
false before this one — `docs/41`, `docs/43`, `docs/44` — and it is
replaced with an exact list of what is and is not protected today. This
is a correction to a stale claim rather than to a number.

**`docs/52` section 12 item 3** priced the cause bank's TMR at *"26
additional flip-flops"* on a 13-bit word, and noted that nothing had
been synthesised and no area was claimed. The word is **21 bits** in the
design that was built, because the reports of items 1 and 2 land in the
same register, so the replication is **+42 flip-flops** and
**4,708.8594 um2**. The estimate was low because the scope grew, not
because the arithmetic was wrong.

**`docs/52` section 13's list of what its campaign does not cover gains
one entry retrospectively.** Its own control 4a deposited into
`ctrl_in_en`, a register that is now a field of a triple-redundant word;
the control had to be rebuilt on state that is still single, and section
8.1 records that rather than editing it quietly.

**`docs/52` section 7.1 says the seven dead machines "are all one
mechanism", and that is the one substantive correction this document
makes to it.** The *chain* is one — a lost fabric response — but the
*failures that produce it are three*, and section 4.3 is the record of
finding that out by building a bound that only covered one of them. A
frame that never ends, a window that forgets it was waiting, and a
window that is busy with nothing owed need three different answers, and
a reader who took "all one mechanism" as a design statement would build
what was built first. The sentence is right about the consequence and
wrong about the cause, and only a re-run could tell the difference.

---

## 12. Files touched

### 12.1 RTL

```
hw/soc/rtl/soc_npu_ser.v    the frame bound, timeout_o
hw/soc/rtl/soc_npu.v        the window bound, the three fault lines,
                            five new cause bits, the tripled bank
hw/soc/rtl/soc_busstat.v    three counters, three stickies, three enables
hw/soc/rtl/soc_top.v        the three fault lines wired end to end
```

`hw/soc/rtl/soc_tmr_bank.v` and `hw/rtl/tmr_voter.v` are **instantiated
and not modified**. Nothing in `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or
`hw/openlane/` is touched.

### 12.2 Software, flows, harness and tests

```
hw/soc/tb/sw/soc_npucfg.h        five cause bits, and NPUCFG_C_FAULTS
hw/soc/tb/sw/soc_timers.h        three BUSSTAT registers and their bits
hw/soc/tb/sw/test_ibex.c         read back every configuration register
hw/soc/tb/sw/fi_npu.c            the same, plus the BUSSTAT counters
hw/soc/tb/tb_soc_npu_fi.v        five mechanisms and three counters
hw/soc/flow/gen_npu_vectors.py   the configuration table, generated once
hw/soc/flow/fi_npu.sh            three more symbols
hw/soc/flow/fi_npu_coverage.sh   soc_tmr_bank.v in the census
hw/soc/flow/syn_soc.sh           SOC_SYN_BLACKBOX and SOC_CHPARAM
hw/soc/fi/npu_targets.py         the new sites; NCAUSE parsed, not written
hw/soc/fi/npu_campaign.py        control 1b widened, control 4a rebuilt,
                                 control 4d added, directed replay
                                 parallelised
hw/soc/tb/cocotb/Makefile.soc_npu    soc_tmr_bank.v
hw/soc/tb/cocotb/test_soc_npu.py     six tests
hw/soc/tb/cocotb/test_soc_busstat.py seven sources
hw/soc/formal/soc_npu_ser_props.v    I5a, I10, I11, D1b, D1c, C6
sw/tests/test_soc_npu_guards.py      eight guards
sw/tests/test_soc_synthesis_guards.py  seven guards
docs/55-npu-connection-hardening.md  this document
docs/00-index.md                     one row
```

**Two additions to `hw/soc/flow/syn_soc.sh` are worth naming.**
`SOC_SYN_BLACKBOX` makes `docs/51` section 11's *"soc_npu, the
connection only (pilot black-boxed)"* row reproducible for the first
time — section 17 of that document had no command that produced it — and
`SOC_CHPARAM` is what lets a hardened block's own unhardened
configuration be measured with the identical recipe and the identical
file list, which is the baseline `docs/41` section 6.5 insists on.

**The black box is asserted and not assumed.** `blackbox` on a module
that has already been elaborated warns and exits zero, which is
`docs/49` section 8.1's shape; the script fails if the boxed module does
not survive as an instance in the netlist. It caught itself on the first
run: `read_verilog -defer` stores a module as `$abstract\name`, so a
bare `blackbox pilot_top` matched nothing, the warning scrolled past, and
the run reported the **whole subsystem's** 209,739 um2 under the name of
the connection alone.

---

## 13. Reproducing this

```
python regmap/generate.py                       # four outputs, one source
python regmap/generate_memmap.py
.venv/bin/python -m pytest sw/tests -q

hw/soc/flow/sim_soc.sh                          # 27 checks on the real SoC

cd hw/soc/tb/cocotb && make -f Makefile.soc_npu
cd hw/soc/tb/cocotb && make -f Makefile.soc_busstat
cd hw/soc/formal && make npuser                 # bmc, prove, cover, prove_h3

hw/soc/flow/syn_soc.sh soc_npu_ser
hw/soc/flow/syn_soc.sh soc_busstat
SOC_SYN_BLACKBOX=pilot_top hw/soc/flow/syn_soc.sh soc_npu
SOC_SYN_BLACKBOX=pilot_top SOC_CHPARAM="-set HARDEN 0" \
    hw/soc/flow/syn_soc.sh soc_npu
hw/soc/flow/syn_soc.sh soc_npu
```

The campaign of record, and the coverage census:

```
hw/soc/flow/fi_npu.sh          hw/soc/out/h55-npu
hw/soc/flow/fi_npu_coverage.sh hw/soc/out/h55-npu
hw/soc/fi/npu_campaign.py --build hw/soc/out/h55-npu --draws 100 --jobs 18
```

The same-draws delta of section 8.2 needs the build whose workload is
`docs/52`'s, so that every cycle in that document's `records.csv` refers
to the same instant in the same program:

```
SW_DEFINES="-DFI_CFG_READBACK=0" hw/soc/flow/fi_npu.sh hw/soc/out/h55-npu-nrb
hw/soc/fi/npu_campaign.py --build hw/soc/out/h55-npu-nrb \
    --directed <docs/52's records.csv, cfgreg rows removed> \
    --jobs 18 --out hw/soc/out/h55-replay
```

`docs/52`'s `cfgreg` rows have to be removed because their paths no
longer exist: `ctrl_in_en`, `ctrl_out_en`, `irq_mask` and the two old
sticky bits are fields of a bank now. `npu_campaign.py` fails hard on a
path it cannot find rather than skipping it, which is the behaviour that
made this visible.

**And the report is checked against itself rather than trusted**, which
is `docs/52` section 5.4 item 3's check after `--replay` was found not
reproducing the run it replays:

```
diff <(sed -n '/^1. CLASSIFICATION/,$p' hw/soc/out/h55-npu/campaign.log) \
     <(sed -n '/^1. CLASSIFICATION/,$p' <replay dir>/campaign.log)
```

**It reproduces line for line** **[fact]**. Seven integer columns were
added to the replay's coercion list with the seven new record fields —
`ser_to`, `win_to`, `win_orph`, `tmr_ev` and the three `bst_*` — because
a column left out of that list is a column `csv` hands back as a string,
and a non-empty string is truthy. That is exactly how the defect
`docs/52` section 5.4 item 3 records survived being looked at, and the
only thing that catches it is running the replay and diffing.

### 13a. What running it cost

**1,408 `vvp` invocations for the campaign of record — 1,400 injections
and 8 controls — in 37 minutes 10 seconds at 18 concurrent processes on
a 20-thread host** **[fact, 09:41:47 to the `records.csv` timestamp of
10:18:57]**, which is **37.9 simulations a minute**. The directed replay
is 1,232 plus its controls in about 32 minutes.

Both are slower per simulation than `docs/52`'s 44.6 a minute, and the
reason is measured rather than guessed: **the workload is longer**. The
clean run is 15,542 cycles against 14,057, which is the read-back of
section 3 and the three `BUSSTAT` loads, and the host was also running a
synthesis and a cocotb suite for part of the campaign. `docs/44` section
9.5's rule — quote the cost with the configuration it was measured in —
applies to both figures.

---

## 14. What the next block should be

**Not another hardening wave on this block.** `docs/52` ranked five
items and all five are now decided: four built, one deliberately not.
What is left unprotected in the connection is unprotected because that
document measured it, and the next thing to do is not to overturn a
measurement with an instinct.

**The order the measurements argue for**, and as in `docs/52` it is not
the order of increasing difficulty.

**1. The event engine, and only after a campaign that can see inside
it.** It is 19.0 % of the connection's flip-flops and `docs/52`
attributed **1.71 of its 4.17 points of silent corruption** to it —
second only to the transport, and unlike the transport it is a design
this project can change all of. `docs/52` section 12 says nothing about
it because its ranking was by *consequence class* and the engine's
consequence is the ordinary one: a wrong inference. **The reason to wait
is that the campaign cannot currently say which of the engine's
structures carries the rate** — `ev_state`, the AER pin drivers, the two
counters and the show-ahead adapter are one stratum of 140 bits, and
section 11.3 of `docs/52` already found that 14 of 24 of its wrong
answers were the counters alone. Splitting that stratum is a
half-day of work on `npu_targets.py` and it decides what to build.

**2. `BUSSTAT` is now 126 unprotected flip-flops whose whole job is to
be believed.** This document tripled the NPU's cause bank because a
fault channel that fabricates events is worse than one that is lossy —
and then routed three more fault lines into a block with 126 flip-flops
and no protection at all, which is the same argument one level up.
Nothing has measured it. `docs/41` section 3.1's criterion applies
without amendment: a saturating counter is **persistent** and its
corruption is **silent**, and `docs/44` did not protect it because
nothing had yet made it the place three blocks report to. The cheap
version is not TMR: it is bundling the four stickies and the enable
register into one protected word, which is 11 bits, and leaving the
counters alone.

**3. Place and route with the NPU in it.** `docs/51` section 11 made
this the open question at 76 % of Ibex by cell area; the connection has
since grown by 8,014 um2 and `BUSSTAT` by 4,796, and **no frequency has
been measured for any of it**. Two guards were added to the critical
block in the SoC's slowest path and neither has been through STA. That
is the largest unmeasured thing this document leaves.

**And one thing that should be said about what this work licenses.** It
licenses *"the connection's only lethal failure is bounded, the bound
cannot fire on a healthy frame, the queues' protection is now countable
by an operator, and the cause register survives a single upset in any
one replica."* It does **not** license "the NPU connection is
adequately protected": the transport still corrupts frames silently, the
event engine is untouched, and `docs/52`'s 4.17 points of silent
corruption were never what this wave was aimed at. Section 8 says what
that number became and section 8.6 says why the change is smaller than
the headline.

**The whole-SoC invariant is now 215,428 cycles** and every document
after this one should quote that number rather than `docs/51`'s 213,971.
Section 8.5 is why it moved and what it was with the RTL change alone.
