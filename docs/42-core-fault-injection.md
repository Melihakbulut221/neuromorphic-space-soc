# 42 — The core's own upset campaign, and what the watchdog actually catches

`docs/38-ibex-bringup.md` section 10 item 4 records a decision and the
bill that comes with it. The owner chose Ibex `small-pmp` over
`small-pmp-sec` on 2026-08-31 — RV32IMC plus PMP, no lockstep, no shadow
register file — and the document states what that takes on:

> Declining `SecureIbex` leaves the core's own sequential logic
> protected by nothing. This project's TMR covers the NPU and the
> configuration state and does not reach inside the CPU. The management
> processor is therefore, as of this decision, the least hardened block
> in the design …
>
> - **The core needs its own fault-injection campaign** … An unmeasured
>   block, in a design whose entire claim is *measured* fault tolerance,
>   is the gap a reviewer finds before we do.
> - **A recovery policy is now required rather than optional.** … The
>   watchdog in the `docs/08` map is the only backstop currently
>   planned, and resetting a core is a coarse instrument. **Whether it
>   suffices is open.**
> - **The decision is cheap to reverse only before floorplanning.**

This document is that campaign, and it answers both questions. The
first — what is the core's silent-data-corruption rate — is the one the
decision obliges. The second — how much of it the watchdog catches —
has never been measured anywhere in this repository, because nothing
here had ever injected into one block and observed a different block's
response.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
intended, with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash and the shuttle closes 2026-09-21. Everything here
is new files under `hw/soc/`. Nothing in `hw/rtl/`, `hw/tb/`, `tt/`,
`formal/` or `hw/openlane/` was modified; `hw/rtl/tmr_voter.v` is read
by the elaboration, exactly as `docs/41` already reads it, and not
touched. Section 11 lists every file.

---

## 1. Verdict first

**The `small-pmp` decision stands on this evidence, the watchdog covers
most of what a watchdog can cover, and there is one named failure mode
it is structurally blind to that a single bit flip produced three
times.**

| Question | Answer |
|---|---|
| What is the core's silent-data-corruption rate under single-bit upsets? | **2.8 % ± 1.6** design-weighted, watchdog held off; **2.7 % ± 1.6** as the SoC is built **[fact]**. Per structure in section 6 |
| Is it the same everywhere? | **No, and not in the order the flip-flop count suggests.** `fetch_fifo` 9 %, `controller` 8 %, `id_ctrl` 8 %, `multdiv` 7 %, `regfile` 3 %, and seven strata at 0 of 100 **[fact]**. But the register file is 45 % of the core, so it contributes more to the design rate than everything else combined. Section 6.3 |
| How much does the watchdog catch? | **91.7 % [78.2 – 97.1] of the upsets that leave the core dead** — 33 of 36 — and 26 of those then completed correctly after the stage-2 reset **[fact]**. Section 7.2 |
| What does it cost? | **Nothing measurable.** Zero spurious escalations in the 1,106 injections the machine would have survived; zero outcomes made worse in 1,300; 27 failures turned into correct results **[fact]** |
| What does it not catch? | **A wrong answer from a core that keeps running.** 118 of 1,300 injections — 9.1 % — produced a wrong answer with no escalation. That is not a defect in the watchdog; it is what a watchdog is |
| Is there a failure it *should* catch and does not? | **Yes, one, and it is the important finding.** All three uncaught dead runs are the same register — `x23`, which holds the loop bound — and the corrupted machine **keeps kicking the watchdog on schedule while looping essentially for ever**. Section 8.1 |
| How was "the watchdog caught it" distinguished from "the simulation ended"? | A catch is a transition on `nmi_o`, `wdog_rst_o` or `wdog_no`, never a timeout; the budget gives every quiet run **eleven complete escalation ladders** in which to fire; and **every injection is run twice**, armed and with the block held off, so the disarmed run says whether the machine was in fact dead. Section 7.1 |
| Is the campaign complete over the core? | **Yes at RTL: 2,178 of 2,178 elaborated flip-flop bits are named by a site** **[fact]**, verified by an independent Yosys census and not by the campaign's own controls. Section 4.2 |
| Does the result argue for revisiting `SecureIbex`? | **No.** Lockstep would convert the 9 % silent set to announced, at +112 % core area, a 39-bit memory subsystem and a second SECDED codec, and would still deliver detection rather than correction. It argues instead for a **windowed watchdog** and for **parity over the register file**, both far cheaper. Section 10 |

**1,300 injections, 13 strata of 100, each run twice — 2,600
simulations, 53 minutes of wall time on 18 processes** **[fact]**.

---

## 2. What was built

Eight new files and one new directory, all under `hw/soc/`:

| File | What it is |
|---|---|
| `hw/soc/tb/sw/fi_workload.c` | The workload. A short, dense, self-checking program for the SoC of `docs/39` and `docs/40`, built against the same `crt0.S` and the same linker script as the bring-up program |
| `hw/soc/tb/tb_soc_fi.v` | The instrument. Runs the whole SoC, deposits one bit at one cycle, and prints a machine-readable record of what came out of the pins. It classifies nothing |
| `hw/soc/fi/targets.py` | The site list, written once, in one language. It generates the Verilog case statement the testbench includes **and** the dump the campaign checks that case statement against |
| `hw/soc/fi/campaign.py` | The campaign. Controls, draw, run, classify, report |
| `hw/soc/fi/coverage.py` | The other direction: given a Yosys census of every flip-flop that elaborates, which of them the site list does *not* name |
| `hw/soc/flow/fi_core.sh`, `build_sw_fi.sh`, `fi_coverage.sh` | Build, elaborate once, census |

The division between the testbench and the campaign is deliberate and it
is the one `docs/16` and `docs/41` already use: **the instrument
measures and the classifier judges, and they are different files.** A
testbench that classified would be a testbench that could be written
around a result.

---

## 3. What counts as a golden reference for a CPU

For the NPU this was not a question. `docs/16` section 1.6 compares
against `sw/golden/`, a bit-exact integer model that *is* the
specification (`docs/10`). A processor running a program has no such
thing sitting in this repository, and the honest options are different
from one another in what they license. All three were considered:

| Candidate | What it would license | Why not, or not alone |
|---|---|---|
| **An ISA simulator** (Spike, or Ibex's own co-simulation) | The strongest claim available: every architectural state change checked against the RISC-V specification, instruction by instruction, so an upset that corrupts a register the program never reads again is still caught | Spike is not in the pinned toolchain, Ibex's co-simulation harness is SystemVerilog and DPI-C for Verilator, and standing it up is a project rather than a step. It would also answer a question this campaign is not asking: whether the *core* is a correct RISC-V implementation is upstream's evidence, restated in `docs/38` section 7.3 |
| **The program's own self-checks** | That the program noticed. Nothing more | It is a property of the software, not of the machine. A self-check that passes has not declared the run correct; it has declared it unnoticed, and those are different claims. Used here, but as a *detection channel* and never as the oracle |
| **An undeposited run of the same program on the same design** | That this run and the reference run differ, in something observable, and the only difference between them is the deposit | Cannot see a defect present in both. Chosen |

**The choice is the undeposited run, and this is what it does and does
not let this document claim.**

*It licenses:* every number in section 6 and section 7. The reference
run and the injected run are the same RTL, the same program, the same
memory image, the same simulator and the same seed; `campaign.py`
control 3 shows the clean run reproduces itself exactly and is identical
with the watchdog held off. Any difference in the console stream, in the
program's published answer, in the trap count, on the alert pins or on
the watchdog's three pins is therefore attributable to the one bit that
was flipped, and to nothing else.

*It does not license:* any claim that the golden run is **correct**. If
`ibex_core` computes something the RISC-V specification does not, or if
sv2v mistranslated it — `docs/38` section 5 is explicit that no
equivalence was proven — the reference carries the same error and the
campaign scores the injected run as MASKED. This oracle measures
*deviation*, not *correctness*, and the two are different. The
correctness evidence for this core is upstream's, and this campaign does
not add to it.

*It also does not license a claim about latent corruption.* The
comparison is over what the run produced. An upset that leaves a
register wrong in a way this program never reads is MASKED here and
would be SDC under an architectural-state oracle. `docs/16` section 5.6
names exactly this class on the NPU side and section 9 below carries it
forward as the single biggest reason an ISA-simulator campaign would say
more than this one.

### 3.1 The second oracle, and why it carries no constants

`fi_workload.c`'s self-checks are all **dual computations**: a sum
forwards against the same sum backwards, a hardware multiply against a
shift-and-add loop, a hardware divide against its own reconstruction
`q*d + r`, a recursive Fibonacci against an iterative one, a memory
block checksummed while it is written and again while it is read back at
a different access width.

Not one of them compares against a written-down expected value, and that
is a direct application of `docs/38` section 7.5 defect 1: the bring-up
program carried four hand-computed RV32M constants, all four were wrong,
and all four were caught by the core being right. A campaign program
with a table of expected results would carry the same risk with nobody
to catch it. A dual computation cannot be wrong the way a transcribed
constant can be wrong; it can only fail to notice.

### 3.2 The workload is not the bring-up program, and that is a cost

`hw/soc/tb/sw/test_ibex.c` runs 185,443 cycles on this SoC **[fact,
`hw/soc/out/sim-soc/sim.log`]**, which is about 50 s of Icarus. A
campaign of 1,300 injections run twice would be a fortnight. It also
traps on purpose four times, which forecloses using "an unexpected trap"
as a detection channel, and spends most of its cycles in the UART wait
loop, where a uniformly drawn upset lands far more often than in
anything interesting.

`fi_workload.c` is 18,682 cycles with a 16,702-cycle measured window
**[fact]** — 89 % of the run is the kernel. The price is that the
campaign runs **one short program**, and section 9 says what that does
not cover.

---

## 4. Where to inject, and how much a sample of this size supports

### 4.1 The strata, and why an unstratified campaign would have been useless

`docs/16` section 6 ranks per structure, and the reason is arithmetic.
This core has **2,198 injectable RTL flip-flop bits** in the campaign's
site table **[fact, `python3 hw/soc/fi/targets.py`]**, and **992 of them
are the architectural register file**. A uniform random campaign would
put nearly one injection in two into `x1`..`x31` and would give the main
control FSM — fifteen bits — an expected **0.7 injections in a hundred**.
The controller is where a hang comes from; the register file is where
the bits are.

So the campaign is **stratified, with an equal sample from each
stratum**, and the strata are drawn over the *architecture* — the
structures the RISC-V privileged specification and the Ibex user manual
name — rather than over the RTL's naming conventions. A stratum is a
thing about which one could make a different decision.

| Stratum | Sites | Bits | What it is |
|---|---:|---:|---|
| `regfile` | 31 | 992 | The 31 architectural general-purpose registers `x1`..`x31` |
| `csr_trap` | 13 | 214 | The machine trap CSRs: `mstatus`, `mepc`, `mcause`, `mtvec`, `mtval`, `mie`, `mscratch`, the stack copies and the privilege level |
| `csr_pmp` | 9 | 155 | The PMP configuration and address registers — the mechanism `docs/09` part B track 3's option S2 rests on |
| `if_id` | 12 | 136 | The IF/ID pipeline register: the instruction presented to decode and its PC |
| `fetch_fifo` | 4 | 133 | The instruction queue between fetch and decode |
| `csr_cnt` | 3 | 131 | `mcycle`, `minstret` and `mcountinhibit` |
| `csr_debug` | 4 | 128 | The debug-mode CSRs, which nothing in this SoC can reach |
| `multdiv` | 6 | 75 | The RV32M multiplier and divider sequencer and its operand registers |
| `lsu` | 13 | 74 | The load/store unit's FSM and datapath registers |
| `id_ctrl` | 4 | 71 | The ID stage's sequencing and the multi-cycle intermediate value |
| `pc_fetch` | 6 | 70 | The fetch address and the prefetch buffer's outstanding-request state |
| `controller` | 10 | 15 | The main control FSM and its exception, NMI and debug state |
| `top_ctrl` | 1 | 4 | `ibex_top`'s own core-busy encoding, outside `ibex_core` |
| **Total** | **116** | **2,198** | |

**[fact]**

Within a stratum a bit is drawn **uniformly over the stratum's
flip-flops, not over its sites**: `x1` and `pmpcfg0` are one site each
but thirty-two bits and six, and weighting by site would over-sample the
narrow ones five to one. The cycle is drawn uniformly inside the
*measured* window of the clean run — `fi_workload.c` publishes a phase
word, the testbench records the cycle at which it changes, and
`campaign.py` draws inside what it recorded. That is `docs/41` section
8.1's last honesty clause applied here: a change to the workload moves
the draws with it instead of silently pushing half the campaign past the
end of the run.

The seed is derived **per (stratum, draw index)** rather than consumed
from one stream. Adding a stratum therefore does not re-roll every draw
after it, which is what makes the armed and the disarmed run of the same
injection the same draw — and that pairing is the whole of section 7.

### 4.2 Coverage: every flip-flop in the elaborated core, and how that was checked

A site list is a list a person wrote, and the campaign's own controls
cannot catch the failure of a person leaving something off it:
`campaign.py` control 1 verifies that every site it names elaborates,
which is the opposite question.

`hw/soc/flow/fi_coverage.sh` asks the right one. Yosys elaborates
`ibex_top` at `soc_top.v`'s exact parameters, flattens it, and dumps
every flip-flop that survives with the name of the signal it stores;
`hw/soc/fi/coverage.py` attributes each one to a site or reports it as
uncovered.

```
flip-flop signals elaborated : 113
  named by a campaign site   : 113
  not named                  : 0

flip-flop BITS elaborated    : 2178
  covered by the campaign    : 2178  (100.0 %)
  not covered                : 0
```

**[fact, `hw/soc/out/fi-core/fi_coverage.txt`]**

**The first run of that census was not 100 %.** It found four things,
and three of them changed the campaign:

1. **The debug CSRs — `dcsr`, `depc`, `dscratch0`, `dscratch1`, 128
   flip-flops.** This SoC ties `debug_req_i` low and `docs/39` section 8
   leaves the debug region reserved and faulting, so nothing can ever
   enter debug mode and nothing reads them. They are a twentieth of the
   core all the same. They are now the `csr_debug` stratum, and section
   6 reports what an upset in them does.
2. **Five bits of CHERIoT capability-load state in the load/store
   unit** — `cap_rx_fsm_q`, `cap_lsw_err_q`, `cheriot_err_q` — which
   survive elaboration at `BaseIsa = RV32I`. Dead logic in this
   configuration, and injected anyway: a flip-flop that is in the design
   is a flip-flop an upset can land in, whatever the architecture thinks
   of it.
3. **`mcountinhibit`**, three bits, simply missed.
4. A naming difference rather than a hole: Yosys puts an anonymous
   generate scope (`genblk3`) in the multiplier's path where Icarus does
   not. `coverage.py` normalises it, in the one place that has to
   reconcile two tools, so the site paths stay the strings a reader can
   search the RTL for.

The census also names three signals going the other way:

```
SITES THE CAMPAIGN INJECTS INTO THAT SYNTHESIS REMOVES:
  u_ibex_core.if_stage_i.instr_expanded_id_o
  u_ibex_core.if_stage_i.instr_gets_expanded_id_o
  u_ibex_core.if_stage_i.instr_new_id_q
```

**[fact]**. Nineteen bits that Icarus elaborates and this campaign
injects into, and that Yosys's `opt_clean` deletes because nothing in
this configuration reads them. That is a concrete, named instance of the
RTL-versus-netlist gap, and section 4.4 is where it matters.

Arithmetic that closes: 2,198 bits in the site table, minus the 19 bits
of those three signals, minus one bit of `mcountinhibit` that Yosys also
drops, is 2,178 — the census total **[fact]**.

**Against the netlist.** `docs/38` section 8.4 counts **2,106
flip-flops** in the mapped `small-pmp` netlist **[fact]**, against 2,178
in this RTL census. The two are not the same quantity and neither
supersedes the other: the census is of the elaborated RTL after
`opt_clean` and before technology mapping, and the netlist is after
`synth`, `dfflegalize` and `abc`, which merge and remove more. The
campaign's site list is complete against the first and is **not claimed
to be complete against the second**.

### 4.3 What is not in the campaign, and why each is a fact about the configuration

- **The writeback stage.** `WritebackStage = 0` selects `g_bypass_wb`,
  which has no flip-flops: writeback is combinational here. There is
  nothing to inject into, and the census confirms it.
- **The instruction cache, the scrambling keys, the dummy-instruction
  LFSR, the lockstep wrapper, the debug trigger registers and the
  CHERIoT datapath.** `ICache 0`, `ICacheScramble 0`, `SecureIbex 0`,
  `DbgTriggerEn 0`, `BaseIsa RV32I` — none is built. (Five bits of
  CHERIoT residue in the LSU *are* built, and are injected: section
  4.2.)
- **Everything outside `u_ibex`.** The fabric, the memories, the CLINT,
  the two timers, the UART and the watchdog's own state are not targets
  here. The watchdog's state is `docs/41` section 8; the memories are
  unhardened by construction and `soc_top.v`'s header says so.

### 4.4 RTL or gate level

**This campaign is RTL.** `docs/32` section 5.1 found **370 of 370
like-for-like injections classifying identically** between the RTL and
the gate-level campaigns, with equal histograms in every class, which is
the strongest evidence in this repository that RTL injection is
trustworthy — and it was established on the NPU, a design this project
wrote and whose netlist it controls, and not on a CPU it did not write.

Three things a gate-level campaign on this core would add that this one
cannot:

1. **The nineteen bits of section 4.2 would not be there.** Three
   registers this campaign injects into do not exist in the netlist. An
   upset into them is measured here and is not physical. That is a bias
   in a known direction: it can only *inflate* the masked fraction, and
   only by at most 19 of 2,178 bits.
2. **Flip-flops the netlist has and the RTL does not.** `synth`
   duplicates and re-encodes; `docs/32` section 1.3 spent a section on
   twenty-one added flip-flops on the pilot. Nothing equivalent has been
   looked at here.
3. **The single-event transient.** Neither campaign models one. Section
   9.

`docs/26` and `docs/32` are what closing this looked like for the pilot,
and doing the same for the core is real work: `hw/soc/` has no
gate-level simulation flow at all, `docs/38` synthesised `ibex_top`
standalone and never simulated the netlist, and the SoC has never been
synthesised as one design. It is named in section 10 as an open item and
not claimed. *Closed 2026-09-06 by `docs/74-core-gate-level-campaign.md`: the
whole SoC simulated at gate level on the sign-off layout's netlist,
the clean run identical to this document's in every published field,
and the 1,400 records of `docs/43`'s campaign of record replayed on
it flip-flop for flip-flop, on the instant each RTL deposit actually
landed. The three registers of section 4.2 are confirmed absent and
so is one bit of `mcountinhibit`; sixty bits of the IF/ID instruction
register are stored in one flip-flop for two RTL registers, and three
state machines are re-encoded, so neither has a like-for-like twin.*

### 4.5 What the sample size supports, stated before the numbers

**100 injections per stratum, 13 strata, 1,300 injections, each run
twice — 2,600 simulations** **[fact]**.

At n = 100, a 95 % Wilson interval is roughly:

| observed | 95 % interval |
|---:|---|
| 0 of 100 | 0.0 – 3.7 % |
| 5 of 100 | 2.2 – 11.2 % |
| 10 of 100 | 5.5 – 17.4 % |
| 20 of 100 | 13.3 – 28.9 % |
| 50 of 100 | 40.4 – 59.6 % |

**[estimate, arithmetic]**

So a per-stratum rate here is good to about **±5 points at the low end
and ±10 in the middle, and to no more than two significant figures.**
Every per-stratum figure in section 6 carries its interval, and none of
them is quoted to a decimal place it cannot carry. A stratum that
reports 0 of 100 is not a stratum with a rate of zero; it is a stratum
whose rate is below about 4 %.

**The core-level figure is not the average of the thirteen.** The
campaign draws equally from strata of very unequal size — 100 from a
15-bit controller and 100 from a 992-bit register file — so the estimate
for the whole core is the bit-weighted combination

    p   = Σ_h (bits_h / bits) · p_h
    var = Σ_h (bits_h / bits)² · p_h(1 − p_h) / n_h

and `campaign.py` reports both. The unweighted figure over all 1,300
injections is also printed, and it is **not** the design rate: it gives
the fifteen-bit controller the same weight as the 992-bit register file.
Against the design weights that **overstates the controller's
contribution by eleven times and understates the register file's by
six** **[estimate, arithmetic on the table above]**, so the two numbers
are labelled and neither is allowed to stand in for the other.

What none of this gives is a **rate per unit time**. Section 9.

---

## 5. The classification, stated over the ports and the specification

`docs/16` section 1.6's five classes, in its order, exactly one per
injection. What is new here is that the announcement channels are a
processor's, not an accelerator's, and every one of them is defined over
something the RISC-V specification or an Ibex pin already means —
**nothing in the classifier is read off this project's RTL.**

| Class | Condition |
|---|---|
| HANG | the run did not complete inside its budget **and** nothing announced anything |
| DETECTED | something announced: see the four channels below |
| SDC | the result differs from the reference run and nothing announced |
| CORRECTED | the result matches and a correction mechanism moved |
| MASKED | the result matches and nothing moved |

**The four announcement channels**, each a thing an operator could
actually see:

| Channel | What it is |
|---|---|
| The watchdog escalated | A transition on `nmi_o`, `wdog_rst_o` or `wdog_no` — `soc_wdog.v` W3's three stages, on pins |
| The program's self-checks | A nonzero `fail_mask`, or an exit code that is not the reference run's. `crt0.S`'s runaway-trap guard, which posts `0xdead0001` past 64 traps, lands here too |
| An unexpected trap | `trap_count` above the reference run's: an instruction faulted and the machine entered a handler. A RISC-V architectural event. The reference run takes none, which is why `fi_workload.c` has no deliberate trap in it |
| An Ibex alert pin | `alert_minor_o`, `alert_major_bus_o`, `double_fault_seen_o` |

**CORRECTED is structurally unreachable in this design, and that is the
finding rather than an omission.** `small-pmp` has no correction
mechanism inside the core at all — no lockstep, no register-file ECC, no
voter — so there is no counter that could move on an upset the machine
absorbed. The column is reported, at zero, rather than quietly dropped,
because a reader comparing this table with `docs/41` section 8.2's — 126
of 126 CORRECTED — should see the difference immediately.

**What is deliberately NOT in the comparison: the cycle count.** Unlike
`docs/41`, where the deadline *is* the function and a displaced event is
a wrong answer, a processor that produces the right value forty cycles
late has produced the right value. `cycles` is carried as a per-record
fact so a purely temporal perturbation is visible; it is not counted as
data corruption.

### 5.1 The controls, each of which is a way to report a confident number while measuring nothing

Five run before any data point, and `campaign.py` aborts on any of them
**[fact, all passing]**:

1. **The elaborated design is the one `targets.py` describes.** The
   testbench dumps every site's index, stratum, name, `$bits` width and
   full hierarchical path; the campaign compares all five against the
   table. A path that moved in the RTL, a width that changed and an
   index that slipped are all caught here.
2. **The clean run is clean in every channel.** It completes, the fail
   mask is zero, the exit magic is posted, no trap, no alert, no console
   framing error, and **no watchdog escalation** — the campaign cannot
   attribute an escalation to an injection if the workload produces one
   on its own.
3. **It reproduces, and it is identical with the watchdog held off.**
   The second condition is what makes the two columns of section 7
   comparable.
4. **A deposit lands, and a deposit can be absorbed.** Positive: bit 20
   of `x2`, the stack pointer, at mid-window. RAM is 64 KiB at zero, so
   setting bit 20 puts every subsequent stack access outside every
   mapped region; it must not classify MASKED. Negative: bit 40 of
   `mcycle`, which this program never reads; it must be possible for
   something to classify MASKED, or the oracle is too tight.
5. **Every deposit is verified after the fact.** The testbench reports
   the target's value before and after and its `$bits` width, and the
   campaign asserts that the value changed by exactly the requested bit
   and that the bit was inside the width. A deposit that missed is a
   hard failure, never a MASKED record.

*Note added 2026-09-06 by `docs/74-core-gate-level-campaign.md` section
5.2a: the deposit lands on the cycle a record names or on the one after
it. `tb_soc_fi.v` waits `while (cycles < arg_cycle) @(posedge clk)` and
`cycles` is incremented by another process on the same edge; the order
is the scheduler's, and measured over the 1,400 records of `docs/43`'s
campaign (which contain this one's 1,300) 686 landed one edge late and
714 on time, deterministically per record. No distribution here moves,
because a draw uniform over a window is uniform over the window shifted
by one; the `cycle` a record names is off by one on about half of them.*

**Control 4 earned its place immediately.** The first version of the
testbench parsed its plusargs in one `initial` block and tested
`arg_site` in another, at time zero, before the parse had run — so it
saw the declaration's `-1` and **every injection in the campaign was a
no-op**. The whole run came back MASKED, which is exactly what a healthy
core looks like. The stack pointer with bit 20 set cannot classify
MASKED, and that is what caught it. It is the same shape as the eight
instances `docs/41` section 6.6 lists, and this is the ninth.

---

## 6. The measured distribution, per structure

### 6.1 With the watchdog held off — the core with no backstop at all

This is the table `docs/38` section 10 item 4 asked for: what an upset in
the management core does when nothing catches it.

| stratum | bits | n | MASKED | CORRECTED | SDC | DETECTED | HANG |
|---|---:|---:|---:|---:|---:|---:|---:|
| `regfile` | 992 | 100 | 78 | 0 | 3 | 15 | 4 |
| `pc_fetch` | 70 | 100 | 67 | 0 | 0 | 33 | 0 |
| `fetch_fifo` | 133 | 100 | 43 | 0 | 9 | 47 | 1 |
| `if_id` | 136 | 100 | 75 | 0 | 5 | 20 | 0 |
| `controller` | 15 | 100 | 82 | 0 | 8 | 5 | 5 |
| `id_ctrl` | 71 | 100 | 84 | 0 | 8 | 8 | 0 |
| `lsu` | 74 | 100 | 95 | 0 | 0 | 2 | 3 |
| `multdiv` | 75 | 100 | 91 | 0 | 7 | 2 | 0 |
| `csr_trap` | 214 | 100 | 96 | 0 | 0 | 3 | 1 |
| `csr_pmp` | 155 | 100 | 97 | 0 | 0 | 3 | 0 |
| `csr_cnt` | 131 | 100 | 100 | 0 | 0 | 0 | 0 |
| `csr_debug` | 128 | 100 | 100 | 0 | 0 | 0 | 0 |
| `top_ctrl` | 4 | 100 | 85 | 0 | 0 | 12 | 3 |
| **all** | **2,198** | **1,300** | **1,093** | **0** | **40** | **150** | **17** |

**[fact, `hw/soc/out/fi-core/campaign.log`]**

**Of the 150 DETECTED, 137 also produced a wrong or missing answer.**
`docs/16` section 1.6's warning applies unchanged: detected is
recoverable, not harmless.

### 6.2 The silent-data-corruption rate

| stratum | n | SDC | rate | 95 % Wilson |
|---|---:|---:|---:|---|
| `fetch_fifo` | 100 | 9 | 9 % | 4.8 – 16.2 % |
| `controller` | 100 | 8 | 8 % | 4.1 – 15.0 % |
| `id_ctrl` | 100 | 8 | 8 % | 4.1 – 15.0 % |
| `multdiv` | 100 | 7 | 7 % | 3.4 – 13.7 % |
| `if_id` | 100 | 5 | 5 % | 2.2 – 11.2 % |
| `regfile` | 100 | 3 | 3 % | 1.0 – 8.5 % |
| `pc_fetch`, `lsu`, `csr_trap`, `csr_pmp`, `csr_cnt`, `csr_debug`, `top_ctrl` | 100 each | 0 | 0 % | 0.0 – 3.7 % |

**[fact]**

**Design-weighted, the whole core:**

| | rate | 95 % |
|---|---:|---|
| SDC, watchdog held off | **2.8 %** | ± 1.6 |
| SDC, watchdog armed | **2.7 %** | ± 1.6 |
| HANG, watchdog held off | **2.1 %** | ± 1.8 |
| HANG, watchdog armed | **1.4 %** | ± 1.5 |

**[fact, the stratified estimator of section 4.5, each stratum weighted
by its share of the 2,198 injectable RTL bits]**

The unweighted figure over all 1,300 injections is 3.1 % (2.3 – 4.2 %)
and it is **not** the design rate: section 4.5.

**Read the "0 %" rows correctly.** Seven strata produced no SDC in 100
draws. That is not a rate of zero, it is a rate below about 4 %, and
`csr_debug` in particular is 100 of 100 MASKED for a reason that has
nothing to do with robustness — nothing in this SoC can enter debug
mode, so nothing reads those registers. `csr_cnt` is the same shape:
this program never reads `mcycle` or `minstret`.

### 6.3 Ranked by consequence, which is not ranked by size

The table `docs/16` section 6 would build a hardening wave from. What it
shows is that **the flip-flop count and the risk are close to inversely
ordered**:

| stratum | bits | share of the core | SDC + HANG, disarmed | contribution to the design rate |
|---|---:|---:|---:|---:|
| `regfile` | 992 | 45.1 % | 7 % | **3.2 %** |
| `fetch_fifo` | 133 | 6.1 % | 10 % | 0.6 % |
| `if_id` | 136 | 6.2 % | 5 % | 0.3 % |
| `id_ctrl` | 71 | 3.2 % | 8 % | 0.3 % |
| `multdiv` | 75 | 3.4 % | 7 % | 0.2 % |
| `controller` | 15 | 0.7 % | 13 % | **0.1 %** |
| `lsu` | 74 | 3.4 % | 3 % | 0.1 % |
| everything else | 702 | 31.9 % | ≤ 1 % | ≤ 0.1 % |

**[fact for the measured columns, [estimate] for the products]**

The controller has the highest per-bit failure rate in the core — 13 of
100 draws into fifteen flip-flops ended wrong or dead — and it is 0.7 %
of the core, so it contributes almost nothing to the design-level rate.
The register file has a per-bit rate half that and contributes more than
everything else combined, because it is 45 % of the flip-flops.

**Both facts matter and they point at different remedies.** If the
question is "what raises the whole-core SDC rate", the answer is the
register file, and the remedy is parity or ECC over it. If the question
is "what turns a working core into a dead one", the answer is the
controller and the load/store FSM, and no amount of register-file ECC
touches that.

### 6.4 The worst individual sites

| stratum | site | n | SDC | HANG | wrong or dead |
|---|---|---:|---:|---:|---:|
| `controller` | `debug_mode_q` | 7 | 7 | 0 | **100 %** |
| `regfile` | `x23` | 4 | 1 | 3 | **100 %** |
| `regfile` | `x9` | 1 | 0 | 1 | 100 % |
| `if_id` | `instr_valid_id_q` | 1 | 1 | 0 | 100 % |
| `regfile` | `x10` | 3 | 2 | 0 | 67 % |
| `multdiv` | `mult_state_q` | 3 | 2 | 0 | 67 % |
| `lsu` | `ls_fsm_cs` | 7 | 0 | 3 | 43 % |
| `controller` | `ctrl_fsm_cs` | 28 | 1 | 5 | 21 % |
| `if_id` | `instr_rdata_alu_id_o` | 25 | 3 | 0 | 12 % |
| `fetch_fifo` | `rdata_q` | 72 | 8 | 0 | 11 % |
| `id_ctrl` | `imd_val_q` | 96 | 8 | 0 | 8 % |
| `top_ctrl` | `core_busy_q` | 100 | 0 | 3 | 3 % |

**[fact]**. The single-digit `n` rows are single-digit because a
stratified draw over bits does not visit every site equally; they are
reported because 4 of 4 and 7 of 7 are worth seeing even when the
interval on them is enormous. Two of them are section 8's findings.

---

## 7. The watchdog: what it catches, what it cannot, and how a catch is told from a timeout

### 7.1 The method, because this is the part nothing in this repository had done

`docs/41` injected into the watchdog and watched the watchdog. This
injects into the **core** and watches the **watchdog**, and that is a
different measurement with a different way of going wrong. Three
things had to be true before the number means anything.

**(a) A catch is a transition on a pin, never the simulation ending.**
`wdog_first` is the cycle at which `nmi_o`, `wdog_rst_o` or `wdog_no`
changed. A run that ends because the budget expired has no such
transition and cannot be counted as caught, by construction, in the
classifier. The two outcomes are not adjacent conditions on the same
variable; they are different variables.

**(b) The budget is long enough that "it did not fire" means "it had
chances and took none".** `campaign.py` computes the budget as
`2 × golden + 6 ladders`, checks it against
`win_close + 4 ladders + golden`, and prints the resulting margin:

```
budget 61940 cycles: the latest cycle an injection can be drawn at is
16910, a full escalation ladder is 4096 clocks, so every run that does
not escalate had at least 11.0 ladders in which to do so
```

**[fact]**. Eleven complete stage-1-then-stage-2 ladders after the
latest possible deposit. A quiet watchdog in this campaign is a
watchdog that did not fire, not one that had not got there yet.

**(c) The pair, which is the whole idea.** Every injection is run
**twice** — the same site, the same bit, the same cycle, the same seed —
once with `wdog_dis_i` low and once with it high. `soc_wdog.v` W1
samples that pin once as power-on reset releases and ignores it for ever
after, so it is a board strap and not a back door, and holding it high
gives **the same machine with the same upset and no backstop.**

That second run is what turns "the watchdog escalated" into a catch
rate. Without it there is no way to tell a backstop that saved a hung
core from one that reset a core which was about to finish correctly, and
those two lead to opposite decisions. `docs/41` section 8.3 makes the
identical argument with its unhardened counterfactual, and this is that
argument applied across a block boundary.

The disarmed run gives every injection a **ground truth**:

| Truth | Meaning |
|---|---|
| **OK** | it finished and the answer is golden. The upset did not break the machine, and any escalation the armed run produced is **spurious** |
| **WRONG** | it finished, with a wrong answer. The program kept kicking, on time, with a corrupted result. **A watchdog cannot catch this and is not supposed to** |
| **DEAD** | it never finished inside the budget. This is the set the backstop exists for |

Control 3 asserts that the clean run is **identical** armed and
disarmed, which is what makes the two columns comparable at all.

### 7.2 The result

**What the machine does with no backstop, and whether the watchdog
escalated on the same upset:**

| truth (disarmed run) | n | share | escalated | quiet | caught | 95 % |
|---|---:|---:|---:|---:|---:|---|
| **OK** — finished, golden answer | 1,106 | 85.1 % | 0 | 1,106 | **0.0 %** | 0.0 – 0.3 % |
| **WRONG** — finished, wrong answer | 158 | 12.2 % | 40 | 118 | 25.3 % | 19.2 – 32.6 % |
| **DEAD** — never finished | 36 | 2.8 % | 33 | 3 | **91.7 %** | 78.2 – 97.1 % |

**[fact, `hw/soc/out/fi-core/campaign.log`]**

**The three numbers, and what each one means.**

**(a) The watchdog catches 33 of 36 — 91.7 % [78.2 – 97.1] — of the
upsets that leave the core dead.** That is the set it exists for and it
is close to complete. **26 of the 33 then ended with the golden answer
anyway**: stage 2 reset the core, the program restarted, and it
produced the right result. The escalation reached stage 2 in 29 of the
33 and stopped at stage 1 in 4 **[fact]**.

Time to notice, measured from the deposit to the first transition on a
pin: **min 488, median 1,332, max 4,932 clocks**, against a programmed
timeout of 2,048 **[fact]**. A median under one timeout is what a
kick-per-round discipline buys — the corrupted core usually stops
kicking part-way through a period it had already partly consumed.

**(b) It catches nothing at all in the 1,106 injections the machine
would have survived. Zero spurious escalations.** That is the cost side
of a backstop and here it is empty. Over the whole campaign, **27
injections ended with the golden answer when armed and did not when
disarmed, and not one went the other way** **[fact]** — the watchdog
turned 27 failures into correct results and made nothing worse.

**(c) It catches a quarter of the wrong-answer set, and that is not the
watchdog seeing a wrong answer — it cannot.** A watchdog has no view of
a result. What those 40 records are is machines that produced a wrong
answer *and*, on the way there, stopped kicking for longer than a
timeout: a trap storm, a long stall, a detour through the handler. Of
the 40, only **one** ended with the golden answer when armed **[fact]**,
so this is not a recovery mechanism, it is an early warning that happens
to fire on a machine that was already lost. 24 of the 40 are
`fetch_fifo` **[fact]**.

**The number that decides the architecture is (c)'s complement: 118 of
1,300 injections — 9.1 % — produced a wrong answer and escalated
nothing.** That is the set no watchdog of any design reaches, and it is
what lockstep would have converted from silent to announced.

**Two partitions of the same 158 records, which happen to split
40 / 118 both ways, and must not be conflated.** By whether the *armed*
run escalated: 40 escalated, 118 did not. By what the *disarmed* run
announced through any channel: **40 announced nothing at all — those are
the SDC records of section 6 — and 118 were announced by the program's
own self-checks or by an unexpected trap** **[fact]**. The equality of
the two 40s is a coincidence of this campaign and not a relationship;
the records are largely different ones.

### 7.3 What announced it, with the watchdog armed

Of the 167 injections whose armed run did not produce the golden answer
**[fact]**:

| channel | n |
|---|---:|
| the program's own self-checks | 105 |
| an unexpected trap | 73 |
| the watchdog escalated | 46 |
| an Ibex alert pin | 26 |
| **nothing at all** | **42** |

The channels overlap; a run can trip several. All 26 alert-pin records
are `double_fault_seen_o` — a fault inside a fault handler — and none is
`alert_minor_o` or `alert_major_bus_o` **[fact, re-run and read off the
pins]**.

**The software noticed more than the hardware did.** The program's dual
computations flagged 105 of the 167; the watchdog flagged 46. That is
not a criticism of the watchdog, which is not a checker — but it is the
strongest single argument in this document that **the recovery policy
`docs/38` calls for is at least as much a software obligation as a
hardware one**, and section 10 says so.

---

## 8. Findings

### 8.1 The one thing the watchdog cannot see is a corrupted loop bound, and this campaign produced it three times

**All three uncaught DEAD records are the same register: `x23`, at bits
24, 15 and 29** **[fact]**.

`x23` is `s7`, and in this build of `fi_workload.c` `s7` holds the
**loop bound**: `main`'s disassembly has `li s7,4` at `c00003b2`, which
is `FI_ROUNDS` **[fact, `hw/soc/out/fi-core/fi_workload.dis`]**. Setting
a high bit of it makes the bound enormous. The program then does exactly
what it was written to do — run the kernel and **kick the watchdog every
round** — for a number of rounds that will not finish inside any budget
this campaign can afford. Re-run at ten times the budget, one of them
reaches round 143 with the watchdog still silent at 600,000 cycles
**[fact]**.

**This is the failure mode a watchdog is structurally blind to, produced
on demand, from a single bit flip, in a program written with no
intention of provoking it.** The core is executing its own instructions,
in order, at full speed, and petting the watchdog on schedule. Nothing
in `soc_wdog.v` — not W1's un-disableability, not W2's fixed time base,
not W3's escalation, not W5's key — has any purchase on it, because none
of them is about *whether the software should still be running*.

It generalises past this program. Any kick issued from inside the loop
whose control variable has been corrupted has the same property, and
"kick from the main loop" is the ordinary way to use a watchdog.

**What would catch it is a windowed watchdog** — one that also fires if
it is kicked *too early* or too often — or a heartbeat carrying a
sequence number the watchdog checks. Neither is built. Section 10 item 2.

### 8.2 An upset that produces the right answer and leaves the machine permanently wrong

**Seven of seven draws into `controller.debug_mode_q` classify SDC**
**[fact]** — the highest per-site failure rate in the campaign — and
every one of them produced **the golden signature, the golden fail mask,
the golden exit code and the golden 19-character console stream.**

What differs is one pin. Setting `debug_mode_q` puts Ibex in debug mode,
where the RISC-V debug specification makes `wfi` a no-op — Ibex
implements that, and `ibex_controller.sv` line 614's own comment says
"in debug mode or single step mode we leave immediately (wfi=nop)". So
`crt0.S`'s terminating `wfi; j` loop never sleeps, `core_sleep_o` never
settles high, and the machine spins for ever having already published a
correct result.

Nothing announces it. The watchdog does not fire — the program finished
and stopped kicking, but the run ends before a timeout elapses in the
normal budget. No trap, no alert, no failed self-check.

**It is in the table as SDC because `core_sleep_o` is part of the
compared result, and it is part of the compared result because of what
finding it cost** — section 8.5 item 1. Had the campaign compared only
the program's answer, these seven would have been MASKED and this
document would have reported a core that absorbs upsets to its debug
state, when what it actually does is enter a mode it can never leave.

### 8.3 The register file dominates the rate and the controller dominates the risk

Section 6.3. Restated because it is the finding a hardening decision
turns on: **45 % of this core's flip-flops are the architectural
registers, and they carry 3.2 of the 4.9 percentage points of
design-weighted wrong-or-dead outcome.** The fifteen-bit controller has
nearly twice the per-bit rate and contributes 0.1.

A register file is also the cheapest thing in a CPU to protect —
`docs/38` section 8.5 records that `SecureIbex`'s register-file ECC is
not separable from a whole shadow core, but **this project owns its own
SECDED codec with golden vectors and formal proofs** (`docs/29`,
`docs/35`), and 992 bits is 31 words of 32. That is a concrete, costed
alternative to lockstep and section 10 raises it.

### 8.4 The two campaigns in this repository now disagree about CORRECTED, and the disagreement is the point

`docs/41` section 8.2: **126 of 126** injections into the watchdog's
protected word came back CORRECTED.

Here: **0 of 1,300**. Not because the core is worse at correcting, but
because it has no correction mechanism at all. The column is in the
table at zero rather than dropped, so the two documents can be read side
by side and the difference is visible rather than inferred.

### 8.5 Four defects in this project's harness, none in Ibex

Recorded because each is a way a campaign can report a confident number
while measuring nothing, and because `docs/38` section 7.5 made the same
list for the same reason.

1. **A run that finished was recorded as a hang, and a permanently
   corrupted machine was recorded as healthy.** `finished` is a wire and
   the first version reported it live, long after the wait loop exited.
   The `debug_mode_q` runs of section 8.2 make `core_sleep_o` *pulse*,
   so the loop exited at the clean run's own cycle count and the report
   then read the wire again, found it low, and recorded seven injections
   as HANG at a budget they never reached. `done` is now latched at loop
   exit and `core_sleep_o` at the end is reported separately and
   compared. **Found by asking why a record said what it said** — the
   same move `docs/41` section 8.4 records — and the corrected numbers
   are the ones above: the whole campaign was re-run.
2. **Every injection was a no-op, and the result looked healthy.** The
   testbench parsed its plusargs in one `initial` block and tested
   `arg_site` in another at time zero, before the parse. It saw the
   declaration's `-1`, deposited nothing, and the campaign came back
   almost entirely MASKED — which is what a well-protected core looks
   like. Caught by the positive control of section 5.1. **The failure
   mode of a broken fault injector is a good result**, which is why that
   control is a gate and not a report.
3. **Twelve bit times of console drain was one frame short.** GRLIB's
   APBUART reports *transmit holding register empty*, so the program's
   last write returns while the previous character is still shifting and
   the last character can be two frames behind the store that queued it.
   The clean run recorded 18 console characters where the program emits
   19. Nothing would have failed; every injected run that happened to be
   a few cycles slower would simply have differed from the reference by
   one console character for a reason having nothing to do with the
   injection.
4. **Three site widths were wrong, and the site list was three
   structures short.** `instr_gets_expanded_id_o` is two bits and not
   one; `pmpaddr` is 32 and not 30; `mult_state_q` is at a different
   path and width under `RV32MFast`. All three were caught by control 1
   comparing `$bits` and the full path against `targets.py` before any
   data point — a campaign without that check would have injected into
   bit 30 of a 30-bit register and silently done nothing. The three
   missing structures (section 4.2) were caught by `fi_coverage.sh`,
   which exists because "every site I named elaborates" and "every
   flip-flop that elaborates is named" are different questions and only
   the second one is about coverage.

### 8.5 Four defects in this project's harness, none in Ibex

Recorded because each is a way a campaign can report a confident number
while measuring nothing, and because `docs/38` section 7.5 made the same
list for the same reason.

1. **Every injection was a no-op, and the result looked healthy.** The
   testbench parsed its plusargs in one `initial` block and tested
   `arg_site` in another at time zero, before the parse. It saw the
   declaration's `-1`, deposited nothing, and the campaign came back
   almost entirely MASKED — which is what a well-protected core looks
   like. Caught by the positive control of section 5.1, which asserts
   that flipping bit 20 of the stack pointer cannot classify MASKED.
   **The failure mode of a broken fault injector is a good result**, and
   that is why the control is a gate and not a report.
2. **Twelve bit times of console drain was one frame short.** GRLIB's
   APBUART reports *transmit holding register empty*, so the program's
   last write returns while the previous character is still shifting and
   the final character can be two frames behind the store that queued
   it. The clean run recorded 18 console characters where the program
   emits 19. Nothing would have failed; every injected run that happened
   to be a few cycles slower would simply have differed from the
   reference by one console character, for a reason having nothing to do
   with the injection. Now 24 bit times.
3. **Three site widths were wrong in the table, and the elaborated
   design said so.** `instr_gets_expanded_id_o` is two bits and not one;
   `pmpaddr` is 32 and not 30; the multiplier's `mult_state_q` is at a
   different path and a different width under `RV32MFast` than under
   the single-cycle variant. All three were caught by control 1
   comparing `$bits` and the full hierarchical path against
   `targets.py`, before any data point. A campaign without that
   comparison would have injected into bit 30 of a 30-bit register and
   silently done nothing.
4. **The site list was three structures short, and the campaign's own
   controls could not have found it.** Section 4.2. `fi_coverage.sh`
   exists because "every site I named elaborates" and "every flip-flop
   that elaborates is named" are different questions, and only the
   second one is about coverage.

---

## 9. What this campaign does NOT cover

Stated at length, because this repository has been bitten by a green
check read as wider than the thing it examined nine times — `docs/28`
4.4a, `docs/34` 8.5, `docs/36` 3.3, `docs/38` 7.3 and 8.2, `docs/39` 3,
twice in `docs/40`, and `docs/41` section 8.4 — and section 5.1 above is
the tenth.

**Even a clean SDC number here would not license the claim that the core
is adequately protected.** These are the reasons, worst first.

- **The oracle is the run's output, not the machine's architectural
  state.** An upset that leaves a register or a CSR wrong in a way *this
  program* never reads is MASKED here. Under an ISA-simulator oracle it
  would be SDC, or at least latent. `docs/16` section 5.6 records the
  same class on the NPU side and reports it separately; this campaign
  cannot, because it has no view of architectural state. **This is the
  single largest reason the measured SDC rate is a lower bound.**
- **One workload, one program, one seed, one parameter point.** A
  program that used the PMP, took interrupts, ran in U-mode, used the
  stack harder or held more live state in registers would exercise
  different structures for different fractions of its run. `docs/09`'s
  S2 supervisor does all of those and does not exist yet. Nothing here
  generalises to it.
- **RTL, single-bit, flip-flop only.** No gate-level netlist, no
  back-annotated timing, no multi-bit strike, no single-event transient
  in combinational logic — and a CPU is mostly combinational logic. No
  upset in a memory, in the fabric, or in any peripheral. `docs/16`
  section 7.4 makes the same disclaimer at length.
- **It says nothing about rates.** Every number is a conditional
  probability given that an upset landed in the injection window, on a
  uniform choice of flip-flop within a stratum and a uniform cycle. It
  is not a failures-in-time figure and cannot be turned into one without
  a cross-section this project has not measured and an orbit-flux model
  it does not have. `docs/16` section 7.5.
- **The injection window is the kernel.** An upset during the boot path,
  during `.data` relocation, during the console drain or during
  power-on reset is not covered — 11 % of the clean run.
- **The core is measured; the system is not.** An upset in `soc_mem`, in
  `soc_bus`, in the APB bridge or in the CLINT would be a different
  campaign. `soc_top.v`'s header already states that none of those is
  hardened.
- **The watchdog result is conditional on this workload's kick
  pattern.** `fi_workload.c` kicks several times per round, at intervals
  well under the timeout it arms. A program that kicked once per long
  computation would leave more slack for a corrupted core to be
  hammering the kick register by accident, and one that kicked from a
  timer interrupt handler would keep kicking while the main program was
  dead. The catch rate is a property of the *pair* — this watchdog and
  this software discipline — and section 10 says what that implies for
  the S2 supervisor.
- **Two upsets are not covered**, and nothing here claims otherwise.
- **The campaign cannot fail because a flip-flop vanished in
  synthesis.** Every site exists in the RTL whatever the netlist holds;
  section 4.2 names three that do not survive. `fi_coverage.sh` is the
  separate criterion and neither substitutes for the other.

---

## 10. Does the `small-pmp` decision stand?

**Plainly: yes, on this evidence, and the campaign was capable of saying
otherwise.** It is worth being explicit that a design-weighted SDC rate
of, say, 15 % would have argued the opposite, and that nothing in the
method was arranged to prevent that answer.

**The argument, in the order it should be checked.**

1. **The measured silent-corruption rate is 2.8 % ± 1.6 per upset in the
   injection window** **[fact]**. Nine upsets in ten either change
   nothing observable or announce themselves. That is not the profile of
   a block that needs a shadow core.
2. **The backstop covers what a backstop can cover.** 91.7 %
   [78.2 – 97.1] of the upsets that leave the core dead end in a
   watchdog escalation, on a pin, and 26 of those 33 then complete
   correctly after the reset. `docs/38` left "whether it suffices is
   open"; on this workload, for this failure class, **it largely does**.
3. **It costs nothing in false positives.** Zero spurious escalations in
   1,106 injections the machine would have survived, and zero outcomes
   made worse in 1,300 **[fact]**.
4. **`SecureIbex` would not have addressed the largest remaining
   category anyway.** The 118 wrong-answer-with-no-escalation records are
   what lockstep *would* catch — a shadow core comparing outputs sees a
   diverging result. But `docs/38` section 8.5 prices that at **+112 %
   core area, a 39-bit memory subsystem, a 22 % SRAM overhead on
   everything the CPU touches, and a second SECDED codec**, and it
   delivers **detection, not correction**: the recovery policy would
   still have to be written. Buying a 2.1x core to convert 9 % of upsets
   from silent to announced, when the announcement has nowhere to go, is
   not a good trade at this point in the design.

**What the decision now takes on that it did not before**, and these are
obligations rather than caveats:

- **The x23 finding is a real hole and it is cheap to close in
  software.** A watchdog that a corrupted loop bound can keep petting is
  not a backstop against that class at all (section 8.1). A **windowed**
  watchdog — one that also fires when kicked too early — costs a
  comparator and a second reload register, and would have caught all
  three. It is not built. This is the one concrete hardware change this
  campaign argues for, and it is two orders of magnitude cheaper than
  lockstep.
- **The register file is where the rate lives and it is the cheapest
  thing to protect** (section 8.3). Parity or SECDED over 31 words,
  using the codec this project already owns and has proved, is the
  measured-highest-value hardening available in this core. Nothing here
  costs it and nothing here says it is necessary; it says it is where to
  look first.
- **The recovery policy is more software than hardware.** The program's
  own dual-computation self-checks announced 105 of the 167 bad runs;
  the watchdog announced 46 (section 7.3). Whatever `docs/09`'s S2
  supervisor becomes, **its self-checking discipline is a
  fault-tolerance mechanism with measured effect**, and it should be
  designed as one rather than arrived at.
- **The reversal condition is unchanged and now has a number attached.**
  `docs/38` says the decision is cheap to reverse only before
  floorplanning. If a later campaign — with an architectural-state
  oracle, at gate level, or on the S2 supervisor rather than this
  kernel — puts the SDC rate materially above the 2.8 % ± 1.6 measured
  here, that is the trigger to re-open it. Section 9's first bullet says
  why that number is a **lower bound** and not a point estimate of the
  truth.

**And the honest limit on all of the above.** This is one short program,
one workload, one seed, RTL only, single-bit only, with an oracle that
sees the run's output and not the machine's architectural state. A clean
number here does not license "the management core is adequately
protected". It licenses "the decision not to buy a shadow core is not
contradicted by the first real measurement of what that decision costs",
which is a smaller claim and the one this document makes.

---

## 11. Files, and reproducing this

### 11.1 Files added

```
hw/soc/fi/targets.py            the site list, and the Verilog it generates
hw/soc/fi/campaign.py           controls, draw, run, classify, report
hw/soc/fi/coverage.py           flip-flop census attribution
hw/soc/tb/tb_soc_fi.v           the instrument
hw/soc/tb/sw/fi_workload.c      the workload
hw/soc/flow/fi_core.sh          build and elaborate once
hw/soc/flow/build_sw_fi.sh      the workload's build
hw/soc/flow/fi_coverage.sh      the Yosys flip-flop census
docs/42-core-fault-injection.md this document
```

Modified: `docs/00-index.md` (one row) and `.gitignore` (one comment
line, naming `hw/soc/fi/` among the tracked directories). No file that
`docs/34` section 2 or section 5 pins is added, removed or altered.

### 11.2 Reproducing

```
make -f hw/soc/tools.soc.mk fetch-ibex fetch-sv2v fetch-rvgcc
hw/soc/flow/sv2v_ibex.sh hw/soc/ext/ibex hw/soc/gen \
                         hw/soc/tools/sv2v-Linux/sv2v

hw/soc/flow/fi_core.sh     hw/soc/out/fi-core      # build, elaborate once
hw/soc/flow/fi_coverage.sh hw/soc/out/fi-core      # the coverage census
hw/soc/fi/campaign.py --build hw/soc/out/fi-core --draws 100 --jobs 18
```

`hw/soc/out/` is gitignored, by the rule `docs/38` section 11 already
applies: fetched or generated, not vendored. The campaign writes
`campaign.log` and `records.csv` there, one row per injection with both
runs' classes, the truth from the disarmed run, every announcement
channel and the escalation latency.

`--replay records.csv` re-prints the whole report from a saved run
without re-simulating anything, which is what every number in sections 6
and 7 was regenerated from.

**Cost, measured:** elaboration once, then 2,600 `vvp` invocations —
**53 minutes of wall time at 18 concurrent processes** on a 20-thread
host **[fact, the interval between `tb_soc_fi.vvp` and `records.csv` in
`hw/soc/out/fi-core/`]**. The clean run is 18,682 cycles and about six
seconds; a run that reaches the 61,940-cycle budget costs about twenty.
