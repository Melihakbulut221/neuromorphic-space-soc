# 69 — Hardening the boot block: which eighteen of ninety-two bits decide whether the part boots again

`docs/68-boot-flow.md` section 16 opens its list of what to do next with
the sentence this document is the answer to:

> **Harden `soc_boot.v`, or decide not to.** It is 92 unprotected
> flip-flops, and eight of them decide whether the part tries to boot
> again. An upset in the boot counter is not a wrong number in
> telemetry: it is a part that gives up early or never gives up.

Both halves of that are now measured rather than argued, and the count
in it turned out to be wrong in both directions: **it is eighteen bits
and not eight, and it is eighteen and not ninety-two.**

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged, with the
derivation stated; **[planned]** = an intention with nothing behind it
yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash. Nothing in `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or
`hw/openlane/` was modified and `hw/tb/Makefile.fi` was not invoked.
One file in `hw/rtl/` is **read**: `tmr_voter.v`, instantiated in place
rather than copied, exactly as `docs/41` does for the watchdog and
`docs/55` for the NPU;
`sw/tests/test_soc_synthesis_guards.py::test_the_voter_is_the_blob_the_pilot_freeze_pins`
still asserts it is the blob `docs/34` section 2 names. Section 13 lists
every file touched.

**BASELINE OR DELTA — WHICH NUMBER IS WHICH.** `docs/68` ran **no
fault-injection campaign on this block at all**, so this document
establishes the baseline as well as the delta and they are kept apart
everywhere. Every number attributed to the *unprotected* block is a
measurement made **in this session**, of the block as `fe2c008` shipped
it, by `SOC_BOOT_FI_UNHARDENED=1`; nothing is compared against a number
`docs/68` reported, because `docs/68` reported none. The one figure
inherited from that document is its **area**, 7,229.0610 um2, and
section 7 re-measures it rather than quoting it — and finds it is not
the right baseline, by 10.9242 um2.

**A NOTE ON WALL-CLOCK TIME.** `docs/67` section 14 and `docs/68`'s
opening note set the rule and it holds here: a process from an unrelated
project held one core for the whole session, so **no wall-clock figure
appears in this document**. Every runtime quoted is a cycle count from a
simulation, which is a property of the design and not of the machine.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **What is protected?** | **Eighteen bits: the whole of what decides a boot.** The boot counter (8), the sampled straps (4), the watchdog-pin readback (1), `armed_q` (1), `valid_q` (1), the sampling delay (2) and — the one the campaign added — the system-reset sample (1). Bundled into one word with a five-bit mismatch report and tripled under the frozen voter. Section 3 |
| **What is deliberately NOT protected?** | **Seventy-four flip-flops, which is FOUR FIFTHS of the block.** `BRPT` and `EPOCH` are 64 of them — 69.6 % of everything `docs/68` built — and they get nothing, because nothing in the design branches on them: they are evidence, and the block's own header says so. The two strap synchroniser stages are eight of the other ten and the watchdog pin's two are the rest. Section 4, and it is the more interesting half |
| **So do the eight decision bits and the other 84 deserve the same treatment?** | **No, and the split is not 8/84 either.** It is **18/74**, and the ranking is not the flip-flop count in any order: the largest single stratum in the block, at 69.6 % of its state, has **zero** boot consequence, and a one-bit register that is rewritten every clock has a permanent one. That is `docs/52`'s `evq_data` finding (41.2 % of the flops, 0 % of the rate) and `docs/56`'s (96 % of a rate in 9 of 140 bits), a third time. Section 3.4 |
| **What did the campaign change about the ranking?** | **One bit, and it is the finding of this document.** `sys_q` was ranked *unprotected* on `docs/41` section 3.1's first question — a register the block rewrites every clock sheds an upset on its own — and that is true of the register and false of the consequence: an upset there manufactures a release edge, the boot counter increments, and **the counter is saturating and power-on-only, so nothing ever takes it back.** 3 of 4 draws came back SDC and one put the part past its attempt limit for the rest of the power cycle. It moved into the word at a cost of two flip-flops. Section 8.4 |
| **How is a 1-bit flag tripled, given the replication bound?** | It is not. Five of the seven fields are one or two bits and none can be tripled alone; they are **bundled** into one 23-bit word and the word is replicated, which is `docs/41` section 4.2's answer and `soc_tmr_bank.v`'s compile-time guard on `W >= 4`. The masking theorem is not re-proved — it is `docs/41`'s `soc_wdog_tmr.sby`, which now runs a **`prove_w23`** task because 23 is this block's width and that job's four widths did not include it. Section 3.5 |
| **Does the redundancy survive synthesis?** | **Yes, and it is counted, not assumed. 143 flip-flops mapped, 23 per replica, with every protective attribute deleted from the text of the source.** Turning the MIX transform off on one replica costs **12** of them, and that mutation is invisible to every simulation, to all five formal tasks and to all 572 injections. Section 6 |
| *Re-measured 2026-09-07 by `docs/75` section 3.3* | The 23 per replica is right by a second instrument as well: the voter's fan-in cone gives **23 / 23 / 23, disjoint**, in the block synthesis and in every whole-SoC netlist in the tree that contains this block. `docs/74` section 6.6's 23 / 11 / 12 is a census by Q-net name, which this document did not use. And `docs/75` section 6 measured something this block gets right for free: **`soc_boot` has no reset output at all**, so the decode of its voted word reaches register reads and nothing else, and the hazard `docs/74` found on the watchdog's identical structure does not exist here |
| **What does it cost?** | **+5,255.9010 um2, +72.60 % of the block, +51 flip-flops, +1.9065 % of the Ibex core** **[fact, the difference of two measurements on an identical source list]**. On the whole SoC, **+6,215.8320 um2 (+0.894 %)** and **+4,546.4706 um2 (+0.668 %)** in two configurations, both against baselines measured in this session that differ from this work **by one parameter and nothing else**. Section 7 |
| **And is the baseline the right one?** | **No, and that is the third time this repository has caught it.** Quoting the delta against `docs/68`'s committed 7,229.0610 gives 5,266.8252 — **overstating B1 by 10.9242 um2**, because the refactor that lets both configurations run identical policy is one cell more expensive at `HARDEN = 0`. `docs/41` section 6.5 found it at 58.17 um2 and `docs/58` section 7 at 25.4394 um2, **both in the direction that would have flattered the hardening; this one runs the other way**. Section 7.1 |
| **Is it proved?** | **Five tasks on this block, all PASS, 6 of 6 cover statements reached**, and two properties are new: D9 says the report is a record and not a register, D10 says the three replicas round-trip. D1-D8 now hold over the *voted* state. **`prove_h0` proves the same policy at `HARDEN = 0`**, which is what makes the area baseline like-for-like an established fact rather than an intention. Across the tree: **58 tasks over 14 jobs, 58 PASS, 0 FAIL** **[fact]**, where `docs/68` ran 56. Section 9.2 |
| **Is it *measured*?** | **572 injections into the block's own flip-flops. 276 of 276 into the protected word came back CORRECTED — every register read unchanged, every one announced. 0 SDC, 0 spurious give-up, 0 misreported strap.** Section 8 |
| **Does the same experiment on the unprotected block look different?** | **Yes, and it is the baseline nobody had.** 368 injections with `HARDEN = 0`: **261 SDC**, and inside the decision word **38 of 72 corrupted the boot counter — the worst by 128 boots — 11 put the part past its attempt limit and 8 stopped it ever reaching one.** Four flips of the strap field set NOBOOT, which is a part that refuses to load an image for the rest of the power cycle. Section 8.3 |
| **Is the delta trustworthy?** | **The calibration is exactly zero. Not one of the 296 records in the strata B1 does not touch changed anything** — not its class, not any of its eight fact columns, not its drawn cycle. `docs/55` section 8.3 had to refuse a 19 % improvement because its control moved; this one did not. Section 8.7 |
| **Did the hardening change any behaviour?** | **No, and it is measured rather than argued.** The whole-SoC run is cycle-identical: **220,256 cycles in the image and 415,324 for the run, 28 of 28 checks, fail mask 0**, with `BSTAT` reading `0x00030000` — the mismatch report zero on a clean part. Section 10 |
| **What is still not covered?** | Two residuals B1 does **not** close, both demonstrated by directed injection rather than left to be inferred: the **two-clock strap sampling window**, where a synchroniser upset is latched for the power cycle and nothing reports it, and **two upsets in two replicas on one bit**, which no reset in this block ever repairs. Section 11 |

---

## 2. What was built

| File | What it is |
|---|---|
| `hw/soc/rtl/soc_boot.v` | **B1**, the first numbered requirement this file has: the decision word, three `soc_tmr_bank` replicas, the frozen voter, the mismatch report in `BSTAT`, and a `HARDEN` parameter that exists to be measured against |
| `hw/soc/formal/soc_boot_props.v`, `soc_boot.sby` | D9 and D10, and a `prove_h0` task |
| `hw/soc/formal/soc_wdog_tmr.sby` | `prove_w23`, this block's word width, so the masking theorem it relies on is proved at it |
| `hw/soc/formal/Makefile` | `boot_tmr_params`, the drift guard, which runs first in the `boot` target, and `prove_w23` in the `wdogtmr` set |
| `hw/soc/tb/cocotb/test_soc_boot_fi.py`, `Makefile.soc_boot_fi` | **New.** The campaign, its counterfactual, and two directed injections |
| `hw/soc/tb/cocotb/test_soc_boot.py` | Four directed tests of the mechanism, in the functional suite |
| `hw/soc/tb/cocotb/mutate_soc_boot.py` | Five more mutations, and an `EXPECTED_UNCAUGHT` set |
| `sw/tests/test_soc_synthesis_guards.py` | Seven netlist-census tests: the only check that looks at what the foundry would receive |
| `sw/tests/test_soc_boot_guards.py` | Six guards, one of which exists because nothing else in the repository could catch a field leaving the word |
| `hw/soc/flow/syn_soc_top.sh` | `SOC_BOOT_HARDEN`, so the whole-SoC baseline differs from this work by one parameter |
| `hw/rtl/tmr_voter.v` | **Read, not modified.** Instantiated in place |

---

## 3. What actually needs protecting, ranked by consequence

### 3.1 The criterion, and the question it is not

`docs/41` section 3.1's rule is **persistence times silence**, decided by
two questions: what rewrites this register, and does its corruption
announce itself. It is the right rule and this block is where it needs a
third question, because two of its fields answer the first one
misleadingly.

The third question is: **what does the corruption REACH?** A register
the block rewrites every clock sheds an upset on its own — and if, in
the cycle before it sheds it, it has already moved something that never
comes back, the register is self-correcting and the failure is not.
`sys_q` is exactly that and section 8.4 is the measurement that found
it.

### 3.2 The protected list, worst first

| Field | Bits | What one upset does | Measured, unprotected (section 8.3) |
|---|---:|---|---|
| `cnt_q` | 8 | **The sharpest state in the block.** Up: the loader reads `BSTAT.OVER`, does not touch the flash, reports `GIVEUP` and takes the give-up exit — and because the counter is saturating and power-on-only, **it stays there for the rest of the power cycle**. Down: the ladder never terminates, and the watchdog cannot break the loop because `docs/68` section 5.4's loader kicks it | **32 of 32 SDC**, 0 of 32 with the right count, worst displacement **128 boots**, **10 gave up early**, **5 never gave up** |
| `strap_q` | 4 | Bit 2 is `NOBOOT`: an upset that sets it is a part that refuses to load an image, for ever, on a board that wired the opposite. Bits 1:0 are `SRC`: the boot moves to a chip select with nothing on it, which is `NOFLASH` on every attempt | **16 of 16 SDC**, 0 of 16 with the right straps, **4 set NOBOOT** |
| `sys_q` | 1 | Manufactures a release edge (one spurious boot counted) or swallows a real one. The register recovers on the next clock; the counter it moved does not | **3 of 4 SDC**, **1 gave up early** |
| `armed_q` | 1 | To 0 the next release re-arms instead of counting, so the counter never advances and the ladder never ends; to 1 before the power-on release every limit is off by one | **3 of 4 SDC**, **3 never gave up** |
| `wdis_q` | 1 | The cross-check against `WDOGSTAT.DISABLED` disagrees for its own reason, which is worse than no cross-check | **4 of 4 SDC**, and no boot consequence |
| `valid_q`, `dly` | 3 | Reopens the sampling window. **Worth less than the argument claimed** — section 4.2 | **12 of 12 MASKED** |

Eighteen bits, plus the five-bit report B1 adds, is a **23-bit** word at
`NSTRAP = 4` and `CNT_W = 8`. The field offsets are named constants used
by the packing, the unpacking and the register reads alike, because
`docs/40` section 7.4 records what one literal bit position cost
`soc_wdog.v`.

### 3.3 The report is inside the word, not beside it

`docs/16` section 5.8 measured this repository's own safety-net report
and found it was the single point of failure: an upset could erase the
announcement of the event it caused. So `TMRERR` and `TMRCNT` are
**fields of the voted word**, and the write that repairs a replica and
the write that records the repair are the same write on the same edge.
An upset in the report is itself corrected and counted; the campaign
draws into all five of those bits and gets 20 of 20 CORRECTED
**[fact]**.

Neither is clearable. `docs/41` section 5.3's reason, unchanged: a
record software can erase is a record an upset can erase. Formal D9
proves it over every write to every offset and the `report_clearable`
mutation is what checks the test can fail.

**They are counted as a stratum of their own** and not folded into
`cnt`, which is `docs/43`'s `regfile_ecc` argument and `docs/58`'s
`mtime_chk`: they are five flip-flops the design did not have, an upset
can land in them exactly as it can land in a decision bit, and folding
them in would move that stratum's measured rate for two unrelated
reasons at once.

### 3.4 The answer to "do the eight and the other 84 deserve the same"

**No, and the number in the question is wrong twice.** Ranked by what
their corruption reaches, the block's 92 flip-flops fall into three
groups that have nothing to do with their sizes:

| group | flip-flops | % of the block | boot consequence, measured |
|---|---:|---:|---|
| the decision word | 18 | 19.6 % | **58 of 72 injections SDC; 11 gave up early, 8 never gave up, 4 refused to boot** |
| the synchronisers | 10 | 10.9 % | 40 of 40 MASKED under a uniform draw; **1 cycle in 101 latches NOBOOT for the power cycle** (section 4.3) |
| `BRPT` and `EPOCH` | 64 | **69.6 %** | **203 of 256 SDC and not one of them touched a boot decision, a strap or the counter** |

**[fact, sections 8.3 and 8.5]**

Two thirds of the block is the two words that survive a reset —
`docs/68` section 9.1 said so and called it "`docs/56`'s accounting in
its starkest form yet" — and they are two thirds of the block with none
of the consequence. Tripling them would have cost roughly
**+13,000 um2** **[estimate, scaling this document's own measured 5,256
um2 for 51 flip-flops to the 128 more that 64 tripled bits would add]**,
two and a half times what B1 cost, to protect the one thing in this
block that cannot cause a failure. That is the instinct `docs/52`
caught out when `evq_data` turned out to be 41.2 % of the flops and zero
of the rate, and `docs/56` caught again when 96 % of a stratum's rate
sat in nine of 140 bits.

### 3.5 The replication bound, and the bundle

Five of the seven protected fields are one or two bits wide.
`hw/rtl/pilot_top.v` section 8.2 proves that three replicas cannot be
held apart over one bit — there are exactly two storage functions, `x`
and `~x` — and `docs/30` section 3.3 generalises it: over `W` bits the
affine transforms give `2 * (2^W - 1)` coordinate functions and three
replicas need six, so **three bits is the first width at which a third
replica has functions left to take**.

A naive replication of `valid_q` would produce **one flip-flop and a
voter voting it against itself**, and every test and every proof in this
repository would still pass. So the bits are concatenated into one word
and the **word** is replicated. `soc_tmr_bank.v` carries the elaboration
guard on `W >= 4`; at `W = 23` the transforms offer `2 * (2^23 - 1)`
coordinate functions and three replicas need 66.

**The composition is not re-proved, and it is proved at this block's
width rather than near it.** `hw/soc/formal/soc_wdog_tmr.sby` already
proves T1-T6 — the round trip, the agreement, the masking theorem under
a free fault vector free every cycle over every bit of any one replica,
the mismatch flag in both directions, and the one-cycle scrub — over
`soc_tmr_bank` under `tmr_voter`, and `soc_boot.v` composes the same
three replicas with the same three POL masks and the same MIX
assignments. That job ran at 22, 21, 5 and 4 bits; **this block's word
is 23, and a width a proof is not run at is a width it does not cover**,
so a `prove_w23` task was added rather than the difference being waved
at. It passes by k-induction **[fact]**.

Rebuilding the composition a second time inside `soc_boot.sby` would be
copying the thing most likely to drift, so instead
`make -C hw/soc/formal boot_tmr_params` reads the three POL masks and
the three MIX assignments back out of `soc_boot.v` and fails if any has
moved — the same guard `wdog_tmr_params` applies one file across. It
runs first in the `boot` target.

---

## 4. What was deliberately left unprotected

This list matters as much as the protected one, and it is four times
longer in flip-flops.

### 4.1 `BRPT` and `EPOCH` — 64 flip-flops, and they get nothing

`soc_boot.v`'s own header, before any of this work, states the reason in
a sentence: *"BRPT and EPOCH are EVIDENCE, not authority. Software
writes them, they survive a stage-2 reset, and nothing in this block or
in the boot flow branches on their contents."* An upset is a wrong
diagnosis in **one** boot's telemetry, and the next boot overwrites it.

Measured: **203 of 256 injections were SDC** — the design's read-back
differs from golden, which is the honest classification, because the
value did change — and **not one of them moved the boot counter, a
strap, `VALID`, or either derived flag** **[fact]**. The 53 that came
back MASKED are the draws that landed after the last write to the
register in question.

That is the whole argument, and it is the same shape as `docs/41`
section 7's for `counter`, `reload` and `pre`: not that the upset is
invisible, but that it is **bounded**, and here the bound is one boot's
worth of telemetry rather than one escalation ladder.

### 4.2 `valid_q` and `dly` are protected, and the campaign says they are worth less than the argument claimed

They are in the word, and this is the honest note about what that buys.

The argument in `soc_boot.v`'s B1 section is that clearing `valid_q`
**reopens the sampling window**, which is `soc_wdog.v` W1's hardware
back door into the boot decision. The mechanism is real. Its value on
this board is not, and the campaign is what said so: **12 of 12
injections into `valid` and `dly` in the unprotected build came back
MASKED** **[fact]**.

`test_02_directed` is why. **`dly` saturates at 2** — it stops
incrementing on the clock the sample is taken — so clearing `valid_q`
does not restart a three-clock delay; it re-latches `sync1` on the very
next clock. And `sync1` is two flops behind pins a board holds static,
so **what a reopened window latches is the value that was already
there**. With the pins deliberately moved first, the re-latch takes the
new value (`0x0006` instead of `0x0009`); with them static it does not
**[fact, both rows of the directed test]**.

So the back door exists and, on a board with static straps, it opens
onto the same room. These three bits are protected anyway, because they
are inside a word that was going to be tripled for `cnt_q` and `strap_q`
and they cost nothing extra — but **they are not part of the case for
B1**, and a document that claimed them as such would be claiming a
measurement it does not have.

### 4.3 The synchronisers — 10 flip-flops, and the residual is real

`sync0`, `sync1`, `wsync0` and `wsync1` are rewritten from the pins
every clock, so an upset is gone in one or two clocks. The exception is
**the clock on which the sample is taken**, where an upset in `sync1` is
latched into `strap_q` for the whole power cycle; `sync0` has the
corresponding clock one earlier.

That residual is real and B1 does **not** close it. Section 8.6
demonstrates it directly and states its exposure: **exactly one of the
101 cycles in the campaign's window** does it, which is why 40 uniform
draws found none of them, and why a directed injection rather than a
bigger campaign is the right instrument — `docs/58` section 8.3's
discipline for a class a uniform draw cannot reach.

Protecting them was considered and rejected: they are a copy of a pin
for two clocks out of a mission, they cannot be bundled without being
written from `strap_i` every clock through the voter, and the residual
they would close is two clocks wide where `sys_q`'s was the whole
mission. **That is the difference between the two, and it is why one of
them moved into the word and the other did not.**

---

## 5. The power-on domain, which cuts both ways here harder than anywhere

`docs/40` section 7.2 is the sharpest finding in that document: state
outside the reset domain is what makes a record survive, and it is also
what makes a stale configuration survive. **The same double edge applies
to the protection**, because the replicas are not reset either — and
this block is the worst case for it in the design.

### 5.1 A held bank would accumulate corruption, and here "held" means for ever

`strap_q` is written **once in a power cycle**. `cnt_q` moves perhaps
three times in a mission. A bank with a write enable would repair a
corrupted replica only at the next write, so the first upset would be
masked and then **wait** — and the second, in a different replica on the
same bit, would not be corrected.

`soc_tmr_bank` has **no write enable**: the whole word is written from
the voted value on every clock edge, which makes the voter a continuous
scrubber and bounds the exposure to a coincident second upset at **one
clock cycle** rather than at the rest of the mission.
`test_an_upset_in_one_replica_is_masked_and_counted` checks the scrub
directly — `TMRCNT` reads 1 and stays at 1 after the fault is gone,
which it could only do if the corrected word went back into the replica
— and
`test_the_decision_word_holds_everything_the_ranking_ranked` asserts
textually that all three replicas are written from `prot_n` every clock.

### 5.2 And the other edge, which is this block's own

The boot counter **must survive a reset in order to count it**, and it
must not survive in a way that strands the part. Three things keep it
out of `docs/40` section 7.2's brick loop and **none of them is the
protection**:

- **the bound is a parameter of the netlist, not a register.** No write
  reaches `LIMIT`, so a corrupted counter can reach the end of the
  ladder early but cannot move the end of the ladder;
- **the terminal state is not silence.** At `BSTAT.OVER` the loader
  still runs, still opens the console, still writes the report, and
  still hands the decision to the platform with `WDOGN` asserted.
  `docs/40` section 7.2's brick was a part that reset for ever *with the
  console never reaching its first character*; this one talks;
- **nothing in this block reaches a budget.** Its only outputs are the
  APB read path, which is the structural version of that document's fix,
  and `test_the_boot_block_drives_nothing_but_its_own_read_data` asserts
  the port list.

**What B1 changes is only how likely a single upset is to put the
counter somewhere it was not.** What it does not change is that **two
upsets in two replicas on one bit inside one clock are uncorrected,
permanently**, because no reset in this block ever repairs the word. On
a part with a system reset that reached the word, a stale value would
last until the next reset; here it lasts until the next power cycle,
which for a spacecraft is the end of the mission's uptime. That is
stated here, in `soc_boot.v`'s header, and again in section 11.

---

## 6. Does the redundancy survive synthesis?

A synthesiser is built to delete deliberately redundant logic, and this
repository has been burned by exactly that: `hw/rtl/pilot_top.v` section
9 records the pilot's configuration TMR merging away entirely, `docs/38`
section 8.5 measured 15,455 um2 of an unguarded lockstep the mapper was
removing, and `docs/43` section 9.4 found **all twenty formal tasks
staying green on a design where the synthesiser had collapsed three
banks into one.**

Every functional test in this repository would pass on a netlist with
one replica instead of three. So would all five formal tasks. So would
**all 572 injections** of section 8, which deposit into RTL registers
that exist in the RTL whatever the netlist holds.
`sw/tests/test_soc_synthesis_guards.py` section 9 is the only check that
looks at what the foundry would receive.

### 6.1 The flip-flop budget, counted

The recipe `hw/soc/flow/syn_soc.sh` runs, on `ihp-sg13g2` at the typical
corner, censused by instance path through the post-mapping flatten:

| | flip-flops |
|---|---:|
| `sync0`, `sync1`, `wsync0`, `wsync1` — unprotected by decision | 10 |
| `brpt_q`, `epoch_q` — unprotected by decision | 64 |
| `u_prot_a` | 23 |
| `u_prot_b` | 23 |
| `u_prot_c` | 23 |
| **total** | **143** |

**[fact]**, and the test derives the 74 and the 23 from `soc_boot.v`'s
own parameter declarations and its field list rather than writing them
down, so a width change moves the expectation with it.

### 6.2 With every protective attribute deleted from the text

`(* keep_hierarchy *)` is the weaker of the two defences and is not
portable to a front end that does not read yosys attributes. So the
guard deletes both attributes from the **text** of a scratch copy —
which no pass can honour and none can re-derive — and forces the flatten
before synthesis:

| sources | mapped flip-flops |
|---|---:|
| as committed | **143** |
| every `keep` and `keep_hierarchy` deleted from the text | **143** |

**[fact]**. Nothing is lost. The POL/MIX storage transform carries the
whole structure on its own.

### 6.3 The mutation, because a guard that cannot fail is not a guard

| mutation | mapped flip-flops |
|---|---:|
| none | 143 |
| `.MIX(0)` on replica C | **131** |
| `HARDEN = 0` | **92** |

**[fact]**, the first two with the attributes deleted.

The middle row is the pigeonhole measured rather than argued: with `MIX`
off, a replica stores `v[i] ^ POL[i]`, one of the only two storage
functions a single bit has, and `POL_C = 0xAAAA…` is zero on the twelve
even bits of 23 — so on exactly those bits replica C stores what replica
A stores and structural hashing merges the pair. **That mutation is
functionally identical RTL, bit for bit at every port**, and section 9.4
records that the formal job passes on it too.

### 6.4 `HARDEN = 0` is 92, and 92 is `docs/68`'s number

The last row is the check that the area baseline in section 7 **is** the
block `docs/68` shipped, and it is stronger than the watchdog's version
of the same check. `soc_wdog.v` leaves its report fields in the bank at
`HARDEN = 0` and **relies on the optimiser noticing they are constant** —
`docs/41` section 6.3's 53 flip-flops rather than 58. `soc_boot.v`
narrows the banked width instead, so the five report bits are never
instantiated:

```
localparam integer PBANK_W = (HARDEN != 0) ? PFULL_W : PDEC_W;
```

which comes to 74 + 18 = **92**, the number `docs/68` section 9.1
measured before any of this existed.
`test_boot_harden_zero_is_exactly_the_block_docs_68_shipped` asserts
both the arithmetic and the literal 92, so that a field list edit which
quietly moved the baseline fails there rather than silently changing
what section 7's delta is a delta against.

### 6.5 What the census cannot see

- **It counts flip-flops and asserts nothing about any other cell.**
- **It examines `soc_boot` alone**, with the three sources the block
  elaborates from.
- **It says nothing about placement or routing.** No layout was run for
  this document; section 11 says what that leaves open.
- **It says nothing about whether the replicas are correct.** Three
  banks that all store the wrong function are three banks. D10 is where
  the round trip is proved.
- **It cannot see a change of parameters at the instance.** Three
  replicas given the same POL and MIX would census as three banks under
  `keep_hierarchy` and collapse without it;
  `test_the_boot_block_instantiates_the_frozen_voter_and_three_banks` is
  the second, textual check on the same thing and neither alone is
  enough.
- **AND IT CANNOT SEE A FIELD LEAVING THE WORD**, which is section 9.5.

---

## 7. Measured area

Same recipe as `docs/39` section 6, `docs/41` section 6.5, `docs/58`
section 7 and `docs/68` section 9.1: `hw/soc/flow/syn_soc.sh`, Yosys
`stat -liberty` on `ihp-sg13g2` typical, `abc` with the same driving
cell, the same load and the same 20 ns delay target. Gate equivalent =
`sg13g2_nand2_1` = 7.2576 um2. The Ibex reference is **275,682.6198
um2** (`hw/soc/out/small-pmp/area.rpt`) **[fact]**.

| Block | Cells | Flops | Area, um2 | kGE | % of Ibex |
|---|---:|---:|---:|---:|---:|
| `soc_boot`, `HARDEN = 0` | 304 | 92 | **7,239.9852** | 0.998 | 2.626 % |
| `soc_boot`, `HARDEN = 1` | 634 | 143 | **12,495.8862** | 1.722 | 4.533 % |
| `soc_boot` as `docs/68` shipped, at `fe2c008` | 303 | 92 | 7,229.0610 | 0.996 | 2.622 % |

**[fact for every measured row; the percentages are arithmetic on them]**

> **The cost of B1 is +5,255.9010 um2 on the block, +72.60 % of it, +51
> flip-flops, and +1.9065 % of the Ibex core** **[estimate, the
> difference of two measurements]**.

Four readings.

### 7.1 The baseline must be `HARDEN = 0`, and this is the third time

**Quoting the delta against `docs/68`'s committed 7,229.0610 gives
5,266.8252 — overstating B1 by 10.9242 um2.** B1 rewrote this block's
next state as one combinational function shared by both configurations,
and at `HARDEN = 0` that shape is **one cell and 10.9242 um2 more
expensive** than the three sequential always-blocks `docs/68` measured,
at the identical 92 flip-flops and the **identical** sequential area of
4,506.9696 um2 **[fact, the two `stat -liberty` reports]**.

`docs/41` section 6.5 found the same thing at 58.17 um2 and `docs/58`
section 7 at 25.4394 um2, both in the direction that would have
flattered the hardening. **This one runs the other way** — the wrong
baseline would have made B1 look *more* expensive, not less — and it is
reported for exactly the reason those two were: the direction is the
small thing and the habit is not.

### 7.2 The source list did not move, and that is checked rather than lucky

`hw/soc/flow/syn_soc.sh` already read `soc_tmr_bank.v` and
`hw/rtl/tmr_voter.v` before this work, because `soc_wdog` needs them, so
`HARDEN = 0` and `HARDEN = 1` are measured from **the same files** and
differ only by whether three instances exist. That matters because the
script's own header records that reading three extra files makes
`soc_clint` 29.3328 um2 *bigger*, and `docs/45` section 4.3 measured it:
a per-block area from this script reproduces against the file list as it
stood on the day. Here the list is identical across every row.

### 7.3 Where the area goes

330 cells and 51 flip-flops. The 51 are two extra replicas of 23 bits
plus the five-bit report; the 330 cells are the two mixed replicas' XOR
encode and decode cones and the 23-bit majority gate. **No attempt was
made to reduce it.**

The cross-check worth naming: `docs/41` section 6.5 measured W6 at
**+5,091.0552 um2 for +49 flip-flops** on a 22-bit word, and this is
**+5,255.9010 for +51** on a 23-bit one. Two independent instantiations
of the same construction, in the same flow, two documents apart, at
103.9 and 103.1 um2 per added flip-flop **[estimate, arithmetic on four
measurements]**. That is not a proof of anything; it is the observation
that a tripled bundle in this design costs about 5.2 kum2 and that a
third one would too.

### 7.4 The whole SoC, and it is quieter than `docs/68`'s

Both differences are against baselines synthesised **in this session,
from the same tree, differing by one parameter and nothing else** —
which is what `SOC_BOOT_HARDEN` was added to `syn_soc_top.sh` for, and
is a tighter control than `docs/68` had available for its own numbers.

| configuration | cells | flops | area, um2 |
|---|---:|---:|---:|
| `ROM_HARDEN = 1`, `SOC_BOOT_HARDEN = 0` | 45,953 | 5,925 | 695,112.9318 |
| **this work**, `ROM_HARDEN = 1` | 46,711 | 5,976 | **701,328.7638** |
| difference | **+758** | **+51** | **+6,215.8320, +0.894 %** |
| `ROM_HARDEN = 0`, `SOC_BOOT_HARDEN = 0` (the netlist the layout uses) | 45,132 | 5,822 | 680,606.8038 |
| **this work**, `ROM_HARDEN = 0` | 45,546 | 5,873 | **685,153.2744** |
| difference | **+414** | **+51** | **+4,546.4706, +0.668 %** |

**[fact, `SOC_MEM=sram hw/soc/flow/syn_soc_top.sh 20`, four runs]**

**The flip-flop delta is +51 in both — the block's own count, exactly.**
And in both `SOC_BOOT_HARDEN = 0` configurations the whole-SoC flip-flop
count reproduces `docs/68` section 9.2's **to the flip-flop**: 5,925 and
5,822 **[fact]**. That is the strongest available evidence that the
baseline is that document's netlist and not an approximation of it.

**The two area differences bracket the block's own 5,256 um2 rather than
agreeing with it**, and that is the noise floor `docs/68` section 9.2
measured and named: `soc_top` is flattened before technology mapping, so
a change of this size perturbs the mapping of things it does not touch.
The spread here is **1,669 um2** against that document's 9,466, which is
a smaller floor for a smaller change and **not a claim that the floor
has moved**. The block's own 5,255.9010 um2 is the number to use;
`docs/44` section 9.5's rule.

The whole-SoC *areas* do not reproduce `docs/68`'s to the same precision
— 695,112.9318 against 693,706.6206, and 680,606.8038 against
684,404.4942, differences of +1,406 and −3,798 um2 **[fact]** — and
those two numbers are the floor stated a third way, since the designs
differ only by the one-cell refactor of section 7.1.

---

## 8. The campaign

`hw/soc/tb/cocotb/test_soc_boot_fi.py`, a new suite on the model of
`test_soc_wdog_fi.py` and `test_soc_clint_fi.py`: the DUT is `soc_boot`
itself, only the stimulus reaches into the hierarchy, and every
observation is one a bench with a bus master and a reset pin could
make — what a read of `BSTRAP`, `BSTAT`, `BRPT` and `EPOCH` returns, at
a stamped cycle.

### 8.1 The window opens at reset release, which the other two campaigns do not do

`test_soc_wdog_fi.py` and `test_soc_clint_fi.py` both put their bring-up
**outside** the injection window, because in those blocks the bring-up
is a program writing configuration and an upset drawn there measures the
bring-up rather than the mission.

**In this block the bring-up IS the mission.** The straps are sampled
three clocks after power-on reset releases and never again; `armed_q` is
set on that same release; the whole of what this block decides is
decided in the first four clocks of a power cycle and then held for the
rest of it. A campaign that opened its window after the sample could
never draw the upset that lands *in* the sample, which is the one
residual the synchronisers have. So the window opens on the cycle after
the release, and control 8 asserts that at least one drawn cycle lands
inside the sampling window.

The clean run is **113 cycles with a 101-cycle injection window**
**[fact]**, identical in both builds. It walks the whole ladder: the
power-on boot, three system resets, `BSTAT.CNT` reading 0, 1, 2, 3 with
`LAST` at 2 and `OVER` at 3, the record written and read back across
each reset, and eight wild stores to the counter's own offset. **A
campaign whose golden run never passed the attempt limit could not tell
a part that gave up early from one that gave up on time**, and control 3
asserts that it does.

### 8.2 The strap pattern is `0b1001`, and NOBOOT is clear

`docs/58` section 8.1's lesson, one block across: a campaign drawn over
a field of zeros measures only the 0 → 1 direction and would report that
clearing a strap is impossible because there was nothing set to clear.
`0b1001` sets bits 0 and 3 and clears bits 1 and 2, so a drawn flip is
as likely to clear a one as to set a zero — and, deliberately, **NOBOOT
(bit 2) is clear on the board**, so an upset that sets it is a part that
refuses to load an image. Control 4 asserts both.

### 8.3 The two campaigns

572 injections hardened and 368 unhardened — every bit of every target,
four times, at seeded-random cycles inside the measured window. The seed
is derived **per target bit and path** rather than consumed from one
stream, so the cycle drawn for `cnt` bit 3 is the same number in both
builds whatever else is in the target list. That is what makes section
8.7's calibration possible.

**Hardened — the design that ships:**

| stratum | bits | n | CORRECTED | MASKED | SDC | counter wrong | strap wrong | announced |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `cnt` | 8 | 32 | **32** | 0 | 0 | **0** | 0 | 32 |
| `armed` | 1 | 4 | **4** | 0 | 0 | 0 | 0 | 4 |
| `valid` | 1 | 4 | **4** | 0 | 0 | 0 | 0 | 4 |
| `strap` | 4 | 16 | **16** | 0 | 0 | 0 | **0** | 16 |
| `wdis` | 1 | 4 | **4** | 0 | 0 | 0 | 0 | 4 |
| `dly` | 2 | 8 | **8** | 0 | 0 | 0 | 0 | 8 |
| `sysq` | 1 | 4 | **4** | 0 | 0 | **0** | 0 | 4 |
| `report` | 5 | 20 | **20** | 0 | 0 | 0 | 0 | 20 |
| `prot_b` | 23 | 92 | **92** | 0 | 0 | 0 | 0 | 92 |
| `prot_c` | 23 | 92 | **92** | 0 | 0 | 0 | 0 | 92 |
| `strap_sync` | 8 | 32 | 0 | 32 | 0 | 0 | 0 | 0 |
| `wdog_sync` | 2 | 8 | 0 | 8 | 0 | 0 | 0 | 0 |
| `brpt` | 32 | 128 | 0 | 19 | 109 | 0 | 0 | 0 |
| `epoch` | 32 | 128 | 0 | 34 | 94 | 0 | 0 | 0 |
| **total** | | **572** | **276** | **93** | **203** | **0** | **0** | **276** |

**[fact, `hw/soc/tb/cocotb/records_soc_boot_fi.csv`]**

**Unhardened — the block `docs/68` shipped, same draws:**

| stratum | bits | n | MASKED | SDC | counter wrong | worst | gave up early | never gave up | strap wrong | NOBOOT set |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `cnt` | 8 | 32 | 0 | **32** | **32** | **128 boots** | **10** | **5** | 0 | 0 |
| `armed` | 1 | 4 | 1 | 3 | 3 | 1 | 0 | **3** | 0 | 0 |
| `valid` | 1 | 4 | **4** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `strap` | 4 | 16 | 0 | **16** | 0 | 0 | 0 | 0 | **16** | **4** |
| `wdis` | 1 | 4 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| `dly` | 2 | 8 | **8** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `sysq` | 1 | 4 | 1 | 3 | 3 | 1 | **1** | 0 | 0 | 0 |
| `strap_sync` | 8 | 32 | 32 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `wdog_sync` | 2 | 8 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `brpt` | 32 | 128 | 19 | 109 | 0 | 0 | 0 | 0 | 0 | 0 |
| `epoch` | 32 | 128 | 34 | 94 | 0 | 0 | 0 | 0 | 0 | 0 |
| **total** | | **368** | **107** | **261** | **38** | **128** | **11** | **8** | **16** | **4** |

**[fact, `records_soc_boot_fi_h0.csv`]**

**Five readings.**

**The mechanism does what it claims, on every bit of every replica.**
276 of 276 draws into the protected word come back CORRECTED, with every
register read identical to golden and the mismatch announced in
`BSTAT`. Not a sample of the bits: all 23, in all three replicas, four
times each, plus the five report bits.

**128 boots is the number the ranking was about.** In the unprotected
block the worst single injection displaced `BSTAT.CNT` by 128 — a flip
of the counter's top bit — and **nothing on the part said so**. A loader
reading that value takes the give-up exit on a part that has booted
once.

**Eleven and eight, and they are not the same failure.** Eleven
injections put the part past its attempt limit while golden was still
trying: `docs/68` section 6.1's terminal state, reached early, and
permanently, because the counter saturates and lives in the power-on
domain. Eight left it short of the limit at the end of the run: the
ladder that never terminates, which the watchdog cannot break because
`docs/68` section 5.4's loader kicks it. The campaign keeps them in
separate columns because a single "the counter was wrong" figure would
average two failures with different costs.

**Four flips of one four-bit field are a part that refuses to boot.**
`strap` is 16 draws and every one of them misreported the straps; four
of them set `NOBOOT` on a board that wired it clear. That is not a
counter being wrong — it is the loader correctly obeying a strap that
was never wired.

**`wdis` is 4 of 4 SDC and has no boot consequence at all**, which is
the honest reading of a bit that is reported and not consumed. It is in
the word because it is one bit of a bundle that was already paid for,
not because the campaign found a cost for it.

### 8.4 The one the campaign moved: `sys_q`

**This is the finding of the document.**

The first version of B1 left `sys_q` unprotected, and the argument was
`docs/41` section 3.1's first question answered honestly: it is
rewritten from `rst_ni` on every clock, so an upset is shed on the next
edge and nothing accumulates. That is true of the register.

The first campaign run — at two draws per bit, with `sys_q` as its own
stratum of one plain flip-flop — returned **2 of 2 SDC, both with
`gave_up_early` set** **[fact, the run that caused the design change]**.
An upset in `sys_q` while the system reset is released **manufactures a
release edge**: the block sees `rst_ni && !sys_q`, the counter
increments, and the counter is saturating and power-on-only, so
**nothing ever takes it back**. The register recovers on the next clock;
the boot decision does not.

So the criterion needed a third question — *what does the corruption
reach?* — and `sys_q` moved into the word at a cost of **two flip-flops
and one bit of the bundle**. It is the cheapest bit in the block by
consequence per flip-flop. `soc_boot.v`'s `P_SYS` localparam carries the
record, and `mutate_soc_boot.py`'s `sys_unprotected` mutation is the
rejected design kept executable.

At four draws per bit the unprotected rate is 3 of 4 SDC with 1
`gave_up_early` **[fact]**, which is the same conclusion with a wider
error bar; the two-draw result is quoted above only because it is what
prompted the change.

### 8.5 `BRPT` and `EPOCH`: 203 SDC and zero consequence

The 64 flip-flops that are 69.6 % of the block produced **203 of the
campaign's 261 unhardened SDC records — 77.8 % of them — and not one
touched a boot decision, a strap, `VALID` or the counter** **[fact]**.

That is what a stratum with a high *rate* and no *consequence* looks
like, and it is why a campaign that reported only classes would rank
this block exactly backwards. The eight fact columns are what separate
them, and `docs/41` section 8.2's sentence is the general form: what the
ranking claims about the unprotected state is not that the upset is
invisible but that it is bounded.

### 8.6 The residual B1 does not close, driven directly

`test_02_directed`, and `docs/58` section 8.3's discipline for a class
that a uniform draw cannot reach.

An upset in `sync1` bit 2 on the clock the strap latch closes puts
`NOBOOT` into `strap_q` **for the rest of the power cycle**, in **both
builds** — the hardened one included, because `sync1` is not in the
protected word. The directed test finds the clock rather than writing it
down — it scans the first seven cycles, which is every cycle at which a
`sync1` upset could still reach the latch — and reports the exposure:
**exactly one of the 101 cycles in the campaign's window does it, 1.0 %**
**[fact]**, which is why 40 uniform draws into the synchronisers found
none of them and why the class reads 40 of 40 MASKED above. `sync0`'s
equivalent cycle is one earlier and was not scanned, so the exposure
across all ten flip-flops is **at least** one cycle in 101 and this
document does not claim it is exactly that.

It is also **silent**: `t.report == 0` is asserted. This is not a TMR
mismatch and nothing in this block can see it.

The second directed injection is section 4.2's, and it is the reason
`valid_q`'s protection is claimed for less than the argument for it
would suggest.

### 8.7 The calibration, and the drift is exactly zero

`docs/55` section 8.3 had to refuse a 19 % improvement because its
frozen-die stratum moved on 15 of 100 records; `docs/56` and `docs/58`
reported their deltas because the same control came back at zero. This
wave changes **no software at all** — B1 is RTL — so the two builds run
the same workload over the same draws, and the strata B1 does not touch
have to come back identical or the delta is a difference of two things.

| | hardened | unhardened |
|---|---:|---:|
| clean run | 113 cycles | **113** |
| measured injection window | 101 cycles | **101** |
| records in untouched strata | 296 | 296 |
| **records that changed verdict** | — | **0 of 296** |
| drawn cycles identical | — | **296 of 296** |

**[fact, a field-by-field diff of the two `records_*.csv` files over
`strap_sync`, `wdog_sync`, `brpt` and `epoch`, keyed on stratum, path,
bit and draw index]**

> **NOT ONE OF THE 296 RECORDS IN THE STRATA B1 DOES NOT TOUCH CHANGED
> ANYTHING — not its class, not any of its eight fact columns, not its
> drawn cycle.** So the 276-of-276 above is a property of the mechanism
> and not of two campaigns that happened to be run.

### 8.8 What the campaign does not cover

- **RTL, single-bit, flip-flop only.** No gate-level netlist, no
  back-annotated timing, no multi-bit strike, and no single-event
  transient in combinational logic — which for this block includes the
  voter, which has no state to inject into, and the whole of the
  next-state function.
- **Two upsets are not covered** and nothing about three replicas claims
  they are. Section 5.1 bounds the uncorrectable window to one clock
  cycle; it does not eliminate it.
- **It says nothing about rates.** Every number is conditional on an
  upset having landed in the window, on a uniform choice of target and
  bit.
- **DETECTED depends on someone looking.** `BSTAT.TMRERR` and `TMRCNT`
  are register fields; this block has no interrupt line and the map
  gives it none, so the only reader is the next boot's loader.
- **One workload, one seed, the block alone.** Nothing here runs
  `soc_boot` inside the SoC with a core and a loader in front of it, so
  "gave up early" and "never gave up" are consequences the **loader**
  would draw from what it read, argued from `hw/soc/tb/sw/boot.c` and
  not run.
- **It cannot fail because a replica vanished in synthesis**, and
  section 6 is the separate criterion.
- **AND IT CANNOT FAIL BECAUSE A FIELD LEFT THE WORD.** Section 9.5.

---

## 9. Verification

Four kinds of evidence, `docs/41` section 6's division, each blind to
what the others see.

### 9.1 cocotb

`test_soc_boot.py`: **18 tests, 18 passed** **[fact]**. The 14 of
`docs/68` are unchanged and were re-run against the hardened block; they
are written over `docs/08` section 2.4, `docs/40` W1 and W4 and the
generated map as a specification, so they are a genuine regression on
the policy and not a description of the new implementation.

Four are new, and they are the only tests in that suite that reach into
the hierarchy — allowed for `docs/16` section 1.2's reason, that the
block has no port through which a fault can be injected, with the
observation still made entirely through the bus:

- **`test_an_upset_in_one_replica_is_masked_and_counted`** — a flip of
  the boot counter's top bit in replica A, and every register read
  unchanged, `TMRERR` set and `TMRCNT` reading 1. **And the scrub**:
  `TMRCNT` still reads 1 on the next read, which it could only do if the
  corrected word went back into the replica.
- **`test_the_mismatch_report_cannot_be_cleared_by_software`** — every
  offset, three values each.
- **`test_the_mismatch_counter_saturates`** and
  **`test_the_mismatch_report_reads_zero_on_a_healthy_part`**.

### 9.2 Formal

`hw/soc/formal/soc_boot.sby`: **bmc (depth 20), prove (k-induction,
depth 10), prove_full at the shipped `CNT_W = 8`, prove_h0 at
`HARDEN = 0`, and cover — five tasks, all PASS, 6 of 6 cover statements
reached** **[fact]**, plus the `boot_tmr_params` drift guard which runs
first. `docs/68` ran four tasks; the fifth is `prove_h0`.

D1-D8 are `docs/68`'s and now hold over the **voted** state, which is a
regression statement and not a redundancy statement: `soc_boot` has no
port through which a fault can be injected, so in this job the replicas
are always in agreement and the voter is proved to be a wire.

**D9** says the report is a record and not a register: no write of any
value to any offset changes `TMRERR` or `TMRCNT`, `TMRERR` never falls,
`TMRCNT` never decreases and saturates.

**D10** says the three replicas agree and the voted word is what every
read is written against. It catches the failure `docs/41` section 9.3
describes as silent in the one direction that matters: a transform that
did not round-trip would make one replica permanently present a
different value, the voter would mask it, **every other property here
would still pass**, and the triple redundancy would have quietly become
a duplex with a wrong third rail.

**`prove_h0` is not a duplicate task.** B1 rewrote the next state as one
combinational function shared by both configurations, and the whole
argument that section 7's `HARDEN = 0` row is a like-for-like baseline
is that the two run identical policy. Proving the policy in both is what
makes that an established fact.

### 9.3 Mutation evidence for the proof

Two mutations against scratch copies of the three sources **[fact]**:

| mutation | bmc | prove |
|---|---|---|
| `mix_dec`'s rotation off by one, `c[i % LO]` | **FAIL** | **FAIL** |
| **`MIX` off on replica C** | **PASS** | **PASS** |

The first is D10 biting: the decode is no longer the encode's inverse,
replicas B and C present a value A does not, and the bounded check finds
it. **The second is the honest negative and it is the most important
line in this section**, and it reproduces `docs/41` section 9.4's
exactly: turning off the anti-merge transform keeps every property in
the job true, because a design in which yosys hashed the three banks
into one still satisfies all of them — there is simply one bank
answering three times. **The formal job cannot see it. The census can,
and measures it at 131 flip-flops instead of 143** (section 6.3).
Neither is a substitute for the other.

### 9.4 Mutation evidence for the suite

`python3 hw/soc/tb/cocotb/mutate_soc_boot.py`: **12 of 13 caught, and
the thirteenth is expected to survive and is listed as such** **[fact]**.

`docs/68`'s eight mutations are re-expressed against the new
combinational next state and all eight are still caught. Five are new
and every one is a protection that **looks** present — three banks, a
voter, a report — and is not:

| mutation | what it is | caught by |
|---|---|---|
| `vote_two` | the voter is fed replica A twice, so it is a duplex with a spare: an upset in A now **wins** the vote and one in C is invisible. The flip-flop count does not change, so this is a suite mutation and not a census one | two tests |
| `report_silent` | the mismatch is corrected and never announced — `docs/43` section 6.5's complaint, built | three tests |
| `report_clearable` | a write to `BSTAT` clears the report | `..._cannot_be_cleared_by_software` |
| `report_wraps` | `TMRCNT`'s saturation removed | `..._counter_saturates` |
| `sys_unprotected` | `sys_q` back outside the word: **the design section 8.4 rejected** | **nothing in the campaign or the suite — section 9.5** |

### 9.5 The gap that three kinds of evidence could not see

`sys_unprotected` is not caught by the functional suite, which was
expected: the difference is what happens under an upset and there are no
upsets in a functional run.

**It is not caught by the netlist census either**, which was also
expected: 74 + 3 × 22 + 1 is the same 143 flip-flops, and the census's
expectation is derived from the same field list the mutation edits, so
the expectation moves with the design.

**And it is not caught by the campaign, which was a surprise.** Running
`test_soc_boot_fi.py` against the mutant passes **4 of 4** **[fact]**:
the campaign derives its target list from the same field layout, so a
field that leaves the word leaves the target list too, the injection
lands on a bit nothing reads, the voter reports a mismatch and the
record classifies CORRECTED. Three independent kinds of evidence,
blind to the same thing for three different reasons.

What catches it is a **textual guard on the RTL's own declarations**:
`test_every_flip_flop_outside_the_protected_word_is_one_that_was_decided`
collects every signal `soc_boot.v` assigns with `<=` and asserts the set
is exactly the four synchroniser stages, the two evidence words and the
`HARDEN = 0` bank. A flip-flop outside the bank that is not on that list
is state that has acquired no ranking — **which is precisely how `sys_q`
was left out of the first version of B1**, and it cost a campaign run to
find.

That is `docs/41` section 6.6's list of eight green checks read wider
than what they examined, and `docs/43` section 9.4's twenty green formal
tasks, one more time — and this time the check that closes it is the
cheapest of the four.

### 9.6 The guards

`sw/tests/test_soc_boot_guards.py`, **24 tests** (18 of `docs/68`, 6
new) **[fact]**, each placed at the stage that can satisfy it:

- what is stored outside the word is a property of the RTL's
  declarations, so it is checked there (9.5);
- that every ranked field is **read from the voted word** is a property
  of the same file, so `..._holds_everything_the_ranking_ranked` checks
  each of the nine field offsets against its named view — the shape
  `docs/58` section 9.4 guards for the CLINT, where the raw register is
  readable beside the corrected one;
- that the bank is written every clock is the scrub, and it is checked
  by counting the three `.d_i(prot_n[PBANK_W-1:0])` connections;
- that `HARDEN` is nowhere set in the design is a property of `soc_top.v`
  and the flows, so it is checked between them;
- that every flow which builds `soc_boot` also reads `soc_tmr_bank.v`
  and `tmr_voter.v` is `docs/57` and `docs/59`'s defect, checked over
  six flow scripts and two Makefiles;
- and that the campaign names every field the layout has is checked
  between the two files, which is what stops a field being added without
  a stratum.

### 9.7 Everything else, re-run

| suite | result |
|---|---|
| `.venv/bin/python -m pytest sw/tests` | **451 passed** **[fact]** (437 at `fe2c008`, plus 7 census tests, 6 guards, and one more `test_doc_links` case for this document) |
| `scripts/run_cocotb.sh` | **395 passed, 0 failed, 0 suites not clean**, over 17 suites in `hw/soc/tb/cocotb` and 6 in `hw/tb` **[fact]** (387 at `fe2c008`, plus 4 functional and 4 campaign) |
| `cd hw/soc/formal && make` | **58 SymbiYosys tasks over 14 jobs, 58 PASS, 0 FAIL**, plus **two** parameter guards **[fact]** (56 tasks and one guard at `fe2c008`: `soc_boot`'s `prove_h0` and `soc_wdog_tmr`'s `prove_w23` are the two new tasks, and `boot_tmr_params` the second guard) |
| `verilator --lint-only` on the three sources | clean **[fact]** |
| `python3 hw/soc/tb/cocotb/mutate_soc_boot.py` | 12 of 13, 1 expected **[fact]** |

---

## 10. The invariant

`docs/68` section 8 asked that every document after it quote **220,256
for the program and 415,324 for the run**, and say which it means.

| build | in the image | whole run |
|---|---:|---:|
| `docs/68`, the design of record | 220,256 | 415,324 |
| **B1** | **220,256** | **415,324** |

**[fact, `hw/soc/flow/sim_soc.sh hw/soc/out/s69-ship`: 28 of 28 checks,
fail mask `0x00000000`, `RESULT PASS`, 1,135 console characters decoded
with 0 framing errors, boot hand-over at cycle 195,068]**

> **THE PROTECTION COSTS ZERO CYCLES**, reproducing both numbers exactly.
> It must: in a fault-free machine the voter is a wire, which is D10
> proved by induction and not assumed.

And the register the whole SoC reports at the end reads
`bstat 0x00030000` **[fact]** — the limit in bits 23:16, the counter
zero, and **the top five bits zero**, which is the mismatch report on a
part nothing has upset. `docs/44` section 11's rule, satisfied by a
counter that is exercised on every run of the campaign rather than by
one that ships enabled and has never caught anything.

**Every document after this one should go on quoting 220,256 and
415,324.**

---

## 11. What this does NOT cover

Stated at length, in the discipline `docs/47` section 9, `docs/58`
section 11 and `docs/68` section 12 set. `docs/68`'s own list stands
unchanged except where this document names an item; what follows is
this document's additions.

- **TWO UPSETS IN TWO REPLICAS ON ONE BIT ARE NOT CORRECTED, AND IN
  THIS BLOCK NOTHING EVER REPAIRS THEM.** The unconditional write makes
  the voter a continuous scrubber and bounds the window to one clock
  cycle; it does not eliminate it. Everything here is in the power-on
  domain, so no reset repairs the word: a double fault lasts until the
  next power cycle, which for a spacecraft is the end of the mission's
  uptime. Nothing in this document measures a double fault and the
  campaign is single-bit by construction.
- **THE STRAP SAMPLING WINDOW IS OPEN AND B1 DOES NOT CLOSE IT.**
  Section 8.6: an upset in `sync1` on the clock the latch closes puts a
  wrong strap — `NOBOOT` included — into the protected word for the
  power cycle, and it is neither corrected nor reported. The exposure
  is two clocks of a power cycle; the effect is permanent. This is the
  sharpest thing this document leaves open inside its own block.
- **NO LAYOUT.** `docs/68` section 9.3 placed and routed its block
  against a baseline in the same session and found hold at the fast
  corner falling from +0.1012 ns to +0.0715 ns, the smallest margin in
  the design, with the warning that *"the next block that lands near the
  clock tree should look at it before assuming there is room"*. **This
  work adds 51 flip-flops and 330 cells to that block and has not been
  placed.** Section 15 item 1.
- **THE CONSEQUENCE COLUMNS ARE ARGUED FROM THE LOADER, NOT RUN
  THROUGH IT.** `gave_up_early` and `never_gives_up` are properties of
  what a bus master read; that a loader reading those values takes the
  give-up exit is `hw/soc/tb/sw/boot.c` and `docs/68` section 6, and no
  whole-SoC run in this document injects a fault.
- **NO WHOLE-SOC FAULT INJECTION.** `flow/fi_core.sh` and
  `flow/fi_npu.sh` read `soc_boot.v` and neither was executed, which is
  the position `docs/61`, `docs/65`, `docs/66` and `docs/68` took.
- **ONE SEED, ONE WORKLOAD, ONE PARAMETER POINT** for the campaign, and
  one strap pattern.
- **THE `wdis` STRATUM HAS NO MEASURED CONSEQUENCE.** It is protected
  because it is one bit of a bundle already paid for. A document that
  claimed the campaign justified it would be claiming a measurement it
  does not have; section 8.3 is what it actually found.
- **`valid_q` AND `dly` ARE PROTECTED AND THE CAMPAIGN FOUND NO COST
  FOR THEM EITHER**, on a board with static straps. Section 4.2.
- **THE CENSUS RUNS ONE LIBERTY AT ONE CORNER** and no timing was
  measured for any of this.
- **NOTHING RAISES AN ALARM ON THE MISMATCH.** It is counted and sticky
  in `BSTAT` and that is all. `soc_busstat.v`'s sticky field has one bit
  left and `docs/58` section 9.2 already spent the argument for a ninth
  source; this block has no interrupt line and the map gives it none, so
  the only reader is the next boot's loader. `docs/16` section 7.6.
- **THE MASK ROM IS STILL A DECISION AND NOT A DESIGN**, `docs/68`
  section 12, unchanged. Nothing here touches it.

---

## 12. Corrections to earlier documents

Every one is a dated in-place note by `docs/64`'s rule; the original
sentences stand.

- **`docs/68` section 12**: *"`soc_boot.v` is unprotected: an upset in
  the boot counter changes a boot decision, an upset in the report
  corrupts a diagnosis, and neither is voted, coded or scrubbed."* The
  first clause is now false of eighteen bits and **still true of the
  report**, which is section 4.1's decision rather than an omission.
- **`docs/68` section 16 item 1**: *"eight of them decide whether the
  part tries to boot again."* Eighteen do, and section 8.4 is how the
  eighteenth was found. The item is closed.
- **`docs/68` section 9.1**: the block's 303 cells / 92 flip-flops /
  7,229.0610 um2 is superseded by section 7 here, and section 7.1
  records that it is **not** the right baseline for the delta.
- **`docs/68` section 9.2**: the whole-SoC rows are superseded by
  section 7.4, which measures its own baseline in-session rather than
  differencing against a worktree.
- **`docs/41` section 7.4**'s ordering argument — protect the backstop
  before the thing it backs up — is unaffected; this block is neither.
- **`docs/44` section 11**: *"a mechanism that ships disabled and has
  never caught anything is a liability."* `TMRERR` and `TMRCNT` ship
  enabled and are exercised 276 times per campaign run; section 10
  records that they read zero on a clean whole-SoC run.
- **`docs/00-index.md`**: one row, which `sw/tests/test_doc_links.py`
  requires.

---

## 13. Files touched

### 13.1 RTL, under `hw/soc/rtl/`

| file | change |
|---|---|
| `soc_boot.v` | B1: the field layout, the three replicas, the voter, the report in `BSTAT`, the next state as one combinational function, `HARDEN` |

**Nothing in `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is
modified. `docs/34`'s freeze is untouched.** `hw/rtl/tmr_voter.v` is
read in place.

### 13.2 Verification

| file | change |
|---|---|
| `hw/soc/formal/soc_boot_props.v` | D9, D10, and the names updated to the voted views |
| `hw/soc/formal/soc_boot.sby` | the two new sources, the four chparam lines, `prove_h0` |
| `hw/soc/formal/soc_wdog_tmr.sby` | `prove_w23` |
| `hw/soc/formal/Makefile` | `boot_tmr_params`, `boot` depends on it, and `prove_w23` in `WDOG_TMR_TASKS` |
| `hw/soc/tb/cocotb/test_soc_boot_fi.py`, `Makefile.soc_boot_fi` | **new**, 4 tests, 572 injections |
| `hw/soc/tb/cocotb/test_soc_boot.py` | four directed tests of the mechanism |
| `hw/soc/tb/cocotb/Makefile.soc_boot` | the two new sources, `BOOT_HARDEN` |
| `hw/soc/tb/cocotb/mutate_soc_boot.py` | eight mutations re-expressed, five added, `EXPECTED_UNCAUGHT` |
| `sw/tests/test_soc_synthesis_guards.py` | section 9, seven tests |
| `sw/tests/test_soc_boot_guards.py` | section 6, six tests |
| `hw/soc/flow/syn_soc_top.sh` | `SOC_BOOT_HARDEN` |
| `docs/69-boot-hardening.md`, `docs/00-index.md` | this document |

`hw/soc/tb/cocotb/records_soc_boot_fi.csv` and
`records_soc_boot_fi_h0.csv` are the two per-record files section 8.7's
calibration diffs.

---

## 14. Reproducing this

```
python regmap/generate_memmap.py
.venv/bin/python -m pytest sw/tests -q                  # 451
scripts/run_cocotb.sh                                   # 395

cd hw/soc/tb/cocotb && make -f Makefile.soc_boot        # 18 tests
cd hw/soc/tb/cocotb && make -f Makefile.soc_boot_fi     # 572 injections
python3 hw/soc/tb/cocotb/mutate_soc_boot.py             # 12 of 13
cd hw/soc/formal && make boot                           # 5 tasks + the guard
cd hw/soc/formal && make wdogtmr                        # 9 tasks, incl. prove_w23
cd hw/soc/formal && make                                # every job

# the counterfactual, which is also the baseline
cd hw/soc/tb/cocotb && SOC_BOOT_FI_UNHARDENED=1 \
    make -f Makefile.soc_boot_fi \
        EXTRA_COMPILE_ARGS=-Psoc_boot.HARDEN=0 \
        SIM_BUILD=sim_build_soc_boot_fi_h0 \
        COCOTB_RESULTS_FILE=results_soc_boot_fi_h0.xml

# the invariant
hw/soc/flow/sim_soc.sh hw/soc/out/s69-ship

# area: the block, both configurations, from the same file list
hw/soc/flow/syn_soc.sh soc_boot
SOC_CHPARAM="-set HARDEN 0" hw/soc/flow/syn_soc.sh soc_boot

# area: the whole SoC, four runs, each pair differing by one parameter
SOC_MEM=sram                     hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s69-syn
SOC_MEM=sram SOC_BOOT_HARDEN=0   hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s69-syn-h0
SOC_MEM=sram SOC_ROM_HARDEN=0                   hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s69-rom0-syn
SOC_MEM=sram SOC_ROM_HARDEN=0 SOC_BOOT_HARDEN=0 hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s69-rom0-syn-h0
```

The calibration in section 8.7 is a field-by-field diff of the two
`records_soc_boot_fi*.csv` files over the four strata B1 does not touch,
keyed on `(stratum, path, bit, draw)`.

Section 9.3's two proof mutations are made against scratch copies of
`soc_boot.v`, `soc_tmr_bank.v` and `tmr_voter.v` in a temporary
directory with a `soc_boot.sby` whose `[files]` section points at them,
so no mutation is ever made in the tree.

---

## 15. What the next block should be

1. **Place and route it.** `docs/68` section 9.3 measured hold at the
   fast corner falling to **+0.0715 ns** — the smallest margin in the
   design — and warned the next block near the clock tree to look at it.
   This work adds 51 flip-flops and 330 cells to exactly that block and
   **has not been placed**. The recipe, the floorplan and the
   side-by-side baseline method are all in that document's section 14;
   this is the cheapest remaining thing and it is the only one that
   could invalidate a shipped number.
2. **Close the strap sampling window, or record that it stays open.**
   Section 8.6 is a permanent, silent, unreported corruption of the boot
   decision from a two-clock exposure. The obvious answer — sample the
   pins into the protected word directly, so the latch closes on a voted
   value — is one bit of the bundle and a rewrite of the sample logic,
   and it would need its own campaign because it moves state across the
   boundary this document just drew. It is smaller than this work was.
3. **The report has no reader.** `BSTAT.TMRCNT` is counted, sticky and
   saturating, and nothing raises a pin or an interrupt on it; the only
   reader is the next boot's loader, which does not read it. Two lines
   in `boot.c` would put it on the console beside the boot count and the
   watchdog's reset count, which is where an operator already looks.
   That is smaller than item 2 and closes `docs/41` section 10 item 3's
   shape for this block.
4. **The remaining items of `docs/68` section 16 are unchanged**: place
   the ROM's check macros or retire them (item 2), an ingress channel
   and then standby (item 3), the copy's 44 cycles per word (item 4),
   the twenty-six unre-examined checks (item 5), and a v0.2 of
   `docs/60` (item 6), now owed by four documents.
