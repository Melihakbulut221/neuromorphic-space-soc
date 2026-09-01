# 46 — A second workload, and the decision about W7

`docs/43-core-hardening.md` section 12 item 5 sets this task, and sets
the terms it has to be answered on:

> **A decision about W7, made from a second workload rather than from
> this one.** Section 8.4 measured its value on this program at zero and
> its cost at seven spurious escalations and 4,904 um2. That is one
> program. Before floorplanning, either a workload that produces a fast
> runaway justifies keeping it, or it should be removed … **A mechanism
> that ships disabled and has never caught anything is a liability in an
> area budget**, and this document is not going to pretend otherwise by
> leaving the question open indefinitely.

So this document writes the second workload — a static partitioned
supervisor of the shape `docs/09` part B track 3 chose — measures its
kick cadence, measures what window that admits, runs the campaign, and
recommends.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[decision]** =
a choice, with its reasoning.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was modified, and
no RTL of any kind was written for this document: `hw/soc/rtl/soc_wdog.v`
already contains W7 and W8 and is read, not changed. Section 12 lists
every file.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| What was measured? | A **second workload**: `hw/soc/tb/sw/fi_supervisor.c`, a static partitioned supervisor with four U-mode partitions isolated by PMP, a periodic frame tick, a run-to-completion schedule and one kick per frame. It is run by the **same instrument** — `tb_soc_fi.v`, `targets.py` and `campaign.py` are byte-for-byte the ones `docs/42` and `docs/43` used, and not one line of them was changed to accept it. Section 3 |
| Was the kick placement decided before the cadence was measured? | **Yes, and it is auditable.** The argument is the "WHERE THE KICK GOES" section of the source file, written before the program was first built, rejecting three placements and taking the fourth on a ground that has nothing to do with a window. Section 4 quotes it in full |
| What is the measured kick-interval ratio? | **1.412** — 7 kicks at intervals of 7,836 to 11,064 clocks **[fact]**. Against `docs/42`'s workload at 57.2 and its rewrite at 1.018, this is the first number in the project measured from software written to be what the software will be. Section 5 |
| What window does that admit? | **`WINS = 1`, and nothing tighter.** Swept on the clean run at every setting from 0 to 6: 0 early kicks at `WINS` 0 and 1, **2** at `WINS = 2`, and **6 — every kick in the contract — at 3 and above** **[fact]**. Section 6 |
| And what does `WINS = 1` cost before any upset? | **It puts the timeout in a box.** W7 at `WINS = 1` requires `i_max < T < 2·i_min`, which here is `11,042 < T < 15,672` — a band 42 % wide. A designer without a window would have taken a longer timeout and been less trigger-happy; with one, the timeout is chosen from a range the software's own jitter closes in on. Section 6.2 |
| Does the answer survive a different dispatch discipline? | **No, and this is the load-bearing finding.** The same supervisor, same partitions, same schedule, same kick placement, run **work-triggered** instead of time-triggered — one `wfi` — measures **2.104**, and `WINS = 1` needs 2.0. There is then **no timeout at all** that satisfies both bounds: it would have to be above 4,456 and below 4,236. Measured rather than argued: at the tightest timeout the ordinary watchdog tolerates, the window rejects **4 of 6** kicks of a healthy program and raises 5 stage-1 NMIs. Section 7 |
| What did the campaign say? | **812 stratified injections, 58 per stratum, each run twice, on the shipping configuration.** The watchdog catches **32 of 32** dead machines, all by ordinary expiry. **W7 rejected a kick as too early on 9 of them**, and a verbatim replay against a `WINS = 0` build attributes the outcomes: **it converted 2 silent data corruptions into announced failures** — the first catches the window has ever made in this repository — and **it caused 2 of the 4 spurious escalations**; the other 2 escalate without it, because the tight timeout W7 obliges is itself more trigger-happy. W8 fired 0 times. Section 8 |
| Recommendation | **W7 is conditional, and the condition should not be taken: remove it before floorplanning.** Not because it is worthless — it is not — but because its benefit (0.25 % [0.07 – 0.89]) and its cost (0.27 % [0.08 – 1.00]) are the same size from one site each, and because its feasibility depends on a dispatch discipline `docs/09` has not chosen. Five requirements that would have to be adopted to keep it, and three triggers that would reverse the decision, are in section 9 |
| Is the isolation real, or would the program run the same with PMP switched off? | **Measured, because a clean run could not tell.** A build in which one partition reads a word outside its region faults **6 times, `mcause = 0x5`, load access fault**, the supervisor terminates that partition and all six frames still complete **[fact]**. Section 3.4 |

---

## 2. What this document does not repeat

`docs/43` section 4 derives the window's arithmetic and this document
uses it without re-deriving it. In one line: with `T` the timeout and
`i_min`, `i_max` the shortest and longest interval between kicks a
program can produce,

    T > i_max                      or a legitimate frame expires
    T · (1 − 2^-WINS) < i_min      or a legitimate kick is early

and therefore `i_max / i_min < 1 / (1 − 2^-WINS)` — **2:1 at
`WINS = 1`, 4:3 at 2, 8:7 at 3.** `WINS` is a bound on the jitter ratio
of the software's kick cadence, and it is paid by the software.

`docs/43` section 5.1 is also taken as read: a window catches a **fast**
runaway and not a **long** one, and `docs/42`'s inference that it would
have caught the corrupted-loop-bound class was wrong.

---

## 3. The workload

### 3.1 What it is

`hw/soc/tb/sw/fi_supervisor.c` and `hw/soc/tb/sw/sup_crt0.S`, 2,172
bytes of ROM image **[fact]**, built by `hw/soc/flow/build_sw_sup.sh`
against the same toolchain, the same flags and **the same linker
script** as `docs/42`'s workload.

`docs/09` part B track 3's S2, in its own words, is

> a **static partitioned bare-metal supervisor** in the style of the
> Microkit static architecture — fixed set of tasks ("protection
> domains"), fixed communication channels, no dynamic allocation after
> init, event-driven loop. M-mode supervisor ~1-2 kSLOC C; tasks in
> U-mode with **PMP regions as the isolation mechanism**.

and this program is a small instance of exactly that:

| | |
|---|---|
| **Four partitions**, a static schedule, no allocation after init | `SUP_NTASK = 4`, chosen because Ibex is built here with `PMPNumRegions = 4` |
| **U-mode**, entered by `mret` with `mstatus.MPP = U` | `sup_dispatch` in `sup_crt0.S` |
| **PMP isolation**, three regions: the boot ROM R+X, the partition's own 1 KiB of RAM R+W, the frame's input message R | `pmp_init`; the partition's region is **rewritten on every dispatch**, which is the actual per-switch cost of choosing PMP |
| **A periodic frame tick** from CLINT `mtimecmp`, advanced absolutely with a catch-up loop | `sup_tick`; `soc_clint.v` is instantiated at `TICK_DIV = 1`, so one mtime tick is one CPU clock |
| **Run to completion**, returning by `ecall`; a partition that faults is **terminated** and the supervisor carries on | `sup_exception` |
| **Partitions of unequal length**, doing **data-dependent** work on a message of one to sixteen words | `task0`..`task3`, `fill_msg` |
| **One kick per frame**, in the supervisor, which is the only code that can reach the watchdog at all | Section 4 |

### 3.2 What it is not

It is not the S2 supervisor. It has no channels between partitions, no
driver model, no error-recovery policy, no MISRA or Frama-C evidence,
and it is about 400 lines against `docs/09`'s 1-2 kSLOC. It is the
smallest program with the **structure** S2 will have — privilege
switches, PMP reprogramming, a frame tick, unequal data-dependent
partitions — on the argument that it is that structure, and not the
arithmetic inside a partition, that determines a kick cadence.

It is also not a replacement for `docs/42`'s workload and does not
supersede any number measured on it. The two are different programs and
this document keeps them apart everywhere.

### 3.3 The constraints it had to satisfy, and what enforces them

`docs/38` section 7.5 defect 3 — **Ibex's `mtvec` is 256-byte aligned
and vectored-only**, stricter than the privileged specification, so a
4-byte-aligned handler is silently truncated to the enclosing 256-byte
boundary — and defect 4 — **the reset vector is fixed** at
`{boot_addr_i[31:8], 8'h80}` and the image origin is not free — each
cost that document a debugging session.

**Neither is re-implemented here and neither could be got wrong
silently**, because both are asserted by `hw/soc/tb/sw/link_soc.ld`,
which is shared and is not copied: `_start == __soc_reset_vector`,
`(trap_vectors & 0xff) == 0`, and `trap_vectors_end - trap_vectors ==
128`. The vector table in `sup_crt0.S` is 32 entries of four bytes
inside a `.option norvc` region, and
`sw/tests/test_soc_supervisor_guards.py` asserts the shape the linker
cannot see.

**A second startup file is a real cost and it is recorded rather than
discovered.** `crt0.S` was kept single precisely so that the reset
sequence and the trap handler could not drift. `sup_crt0.S` duplicates
it because a supervisor whose partitions run in U-mode and return by
`ecall` needs a synchronous-exception handler that switches privilege
and stack, which is not a variation on `crt0.S`'s handler but a
different one — and because the alternative, a hook in `crt0.S`, would
change the instruction stream of the bring-up program and of
`fi_workload.c`, and `docs/43` section 9.1 rests on both being
cycle-identical to `docs/40` and `docs/41`.

### 3.4 A control on the isolation, because a clean run could not provide one

Every partition in the ordinary build touches only its own memory. **A
run in which PMP enforced nothing at all would therefore look
identical**, which is the same shape of defect as `docs/42` section
5.1's control 4: the first version of that testbench made every
injection a no-op and the whole campaign came back MASKED, which is what
a healthy core looks like.

So `-DSUP_PROVE_ISOLATION` builds a partition that reads word 0 of RAM,
below every region granted to U-mode. Measured:

```
RECORD done=1 cycles=68707
RECORD sig=62847c4e mask=00001300 rounds=6
RECORD traps=6 mcause=00000005 nmis=0
RECORD wdog1=0 wdog2=0 wdog3=0
```

**[fact, `hw/soc/out/sup-iso`]** — six faults, `mcause = 0x5`, a load
access fault, one per frame; the supervisor terminated that partition
each time; **all six frames still completed and the watchdog never
escalated.** That is the enforcement and the containment in one run, and
`F_FAULT`, `F_ECALL` and `F_TRAP` in the mask are the supervisor
reporting all three of the things that happened.

---

## 4. Where the kick goes — the decision, made before the measurement

This is the whole difficulty of the task, so the decision is stated
before any number and its reasoning is in the source file rather than
here, where it could be adjusted to suit a result. What follows is that
section of `hw/soc/tb/sw/fi_supervisor.c`, verbatim.

> The kick is issued ONCE PER FRAME, IN THE SUPERVISOR, IMMEDIATELY
> AFTER THE LAST PARTITION IN THE STATIC SCHEDULE HAS RETURNED.
>
> Four placements are available to a supervisor of this shape, and the
> argument for the one chosen is an argument about what a kick asserts.
>
> **(a) IN THE TICK HANDLER, once per tick.** Rejected. It decouples the
> kick from the work: a system in which every partition has deadlocked
> still takes its timer interrupt, so the watchdog goes on being petted
> by a machine that has stopped doing anything. This is the classic
> watchdog anti-pattern and it is rejected on that ground alone, not on
> any ground to do with a window.
>
> **(b) IN THE IDLE PATH**, whenever the supervisor has nothing to do.
> Rejected. It asserts that the supervisor reached its idle loop, which
> is a statement about the supervisor and not about the system; and a
> system that is never idle never kicks, so the watchdog fires hardest
> exactly when the machine is busiest.
>
> **(c) ONCE PER PARTITION**, at each partition's return. Rejected, for
> two reasons. It asserts less — "some partition ran" rather than "the
> schedule completed" — and it multiplies the number of places in the
> program that touch the watchdog by the number of partitions, which is
> the wrong direction for a block whose whole argument (`soc_wdog.v` W5,
> `docs/40` section 5.6) is that a runaway must not be able to pet it by
> accident.
>
> **(d) ONCE PER FRAME, AFTER EVERY PARTITION HAS RUN AND RETURNED.**
> CHOSEN. It is the strongest statement the supervisor can make from
> evidence it actually holds: every partition in the static schedule was
> dispatched, ran, and returned through the one exit the architecture
> gives it.

and the part of it the requirement does not determine, which the same
section records:

> "Once per frame after every partition has returned" still admits two
> instants: at the moment the last partition returns, or at the top of
> the next frame gated on the previous frame having completed. Both are
> progress attestations. This file takes the FIRST, on the ground that a
> kick should be as close in time as possible to the evidence it
> attests: a kick issued at the top of the next frame attests work that
> finished up to a whole frame period ago, and if the machine dies in
> the idle gap the watchdog has already been petted for a frame that did
> complete. …
>
> It is worth being explicit that this choice does not flatter a window.
> The kick instant is tied to the WORK, so all of the frame's execution
> -time variation lands in the kick interval. The alternative instant is
> tied to the CLOCK and would produce a tighter cadence.

**Two honesty notes about this.**

**It is a claim about process and nothing in a simulator can attest to
it.** The section was written before the program was first built and
before any cadence was measured, and has not been edited since. The
reader has the source file, the order in which its sections read, and
the fact that the placement chosen is the one that measures worse — and
nothing stronger than that.

**And the chosen instant is the one that produces MORE jitter, not
less.** A kick tied to the frame clock rather than to the end of the
work would have had a cadence close to the tick's own, which is very
nearly constant. That option was available, it was rejected for a reason
stated above, and section 9 treats the fact that it was available as
part of the answer rather than as a footnote.

**And one thing that is settled by construction rather than by
argument.** The watchdog is unreachable from a partition: `pmp_init`
grants U-mode the boot ROM, the partition's own kilobyte and the shared
message, and nothing else — not the peripheral bus, which is where the
watchdog is. So there is exactly one place in the whole program that
kicks, and that is what makes a one-kick-per-frame cadence a meaningful
quantity at all. Section 3.4 shows PMP refusing a U-mode access to an
address outside the granted set; it does not separately exercise the
peripheral bus, and the argument that the same rule denies that too is
the region list and not a measurement.
`sw/tests/test_soc_supervisor_guards.py` counts the call sites and fails
at three.

---

## 5. The measured cadence

### 5.1 The frame's execution time, and the frame period derived from it

The frame period is a **schedulability decision** and the rule was
stated in `hw/soc/tb/sw/sup_config.h` before it was applied: the period
is **twice the measured worst-case frame execution time**, a 50 % CPU
margin, which is the conventional early-development budget for a
spacecraft management processor **[decision]**.

The worst case is measured and not estimated, using the work-triggered
build, in which the interval between two kicks *is* one frame's
execution time:

| | clocks |
|---|---:|
| shortest frame | **2,118** |
| longest frame | **4,456** |

**[fact, `hw/soc/out/sup-free`, the `kick_min` and `kick_max` fields of
the clean run's record; `tb_soc_fi.v` counts every kick request the
block sees]**

So `SUP_TICK_PERIOD = 2 × 4,456 = 8,912` clocks **[estimate,
arithmetic]**, and the worst-case frame occupies exactly 50.0 % of it
while the mean frame occupies about 31 % **[estimate]**.

### 5.2 The kick cadence of the time-triggered supervisor

| | clocks |
|---|---:|
| kicks in the run | 7 |
| shortest interval `i_min` | **7,836** |
| longest interval `i_max` | **11,042** |
| **jitter ratio** | **1.409** |

**[fact, `hw/soc/out/sup-tt`, the clean run with no contract declared]**

With the contract declared the same measurement is 7,836 to **11,064**,
ratio **1.412** — the four extra clocks are the store that declares it
**[fact, `hw/soc/out/sup-w`, `campaign.py` control 2]**. The campaign's
numbers are the second set and this document quotes it where it quotes
the campaign.

**Where the jitter comes from, because it is not noise.** The frame
opens on the tick, so the interval between two kicks is one period plus
the difference of two frames' execution times: `P + W_f − W_{f−1}`. The
spread is therefore the spread of the frame's own work, which is the
spread of the message length, which is one to sixteen words. Nothing in
this number is simulator jitter, cache behaviour or interrupt latency,
and section 10 says what that means for reading it.

### 5.3 The three cadences this project has now measured

| program | how it kicks | kicks | `i_min` | `i_max` | ratio |
|---|---|---:|---:|---:|---:|
| `fi_workload.c`, as `docs/42` wrote it | six times per round, wherever the code passes | 25 | 30 | 1,716 | **57.2** |
| `fi_workload.c`, rewritten for a window | once per round | 5 | 4,090 | 4,164 | **1.018** |
| `fi_supervisor.c`, time-triggered | once per frame, after the schedule completes | 7 | 7,836 | 11,064 | **1.412** |
| `fi_supervisor.c`, work-triggered | the same | 7 | 2,118 | 4,456 | **2.104** |

**[the first two are `docs/43` section 4.3; the last two are measured
here]**

The two middle rows are the same program written two ways and neither is
a fact about realistic software. **The bottom two are the same realistic
program run under the two dispatch disciplines `docs/09` has not chosen
between**, and they fall on opposite sides of the only window setting
this design can use.

---

## 6. What `WINS` that admits

### 6.1 The sweep, which is the measurement that decides it

The arithmetic of section 2 says `WINS = 1` (bound 2.0) is admissible at
a ratio of 1.412 and `WINS = 2` (bound 1.333) is not. That is an
argument. This is the measurement: seven builds of the clean run, the
contract declared at each `WINS`, everything else held fixed, at
`T = 13,360`.

| `WINS` | window opens at | early kicks in the clean run | stage-1 NMIs | answer |
|---:|---:|---:|---:|---|
| 0 | 0 | **0** | 0 | golden |
| **1** | **6,680** | **0** | **0** | **golden** |
| 2 | 10,020 | **2** | 3 | golden |
| 3 | 11,690 | **6** | 10 | golden |
| 4 | 12,525 | 6 | 10 | golden |
| 5 | 12,942 | 6 | 10 | golden |
| 6 | 13,151 | 6 | 10 | golden |

**[fact, seven builds, `hw/soc/out/sup-s0` .. `sup-s6`]**

**`WINS = 1` is the setting, and one notch tighter costs 2 of the 6
kicks of a healthy program.** At `WINS = 3` and above it costs all six —
100 % of the kicks the contract covers, on a machine with nothing wrong
with it.

Two readings, both of which `docs/43` section 4.4 also had.

**The run produced the golden answer at every setting**, including the
one where every kick is a violation: `sup_crt0.S`'s NMI handler
acknowledges and returns, and stage 2 needs a second violation with
stage 1 still unacknowledged. A too-tight window on this software is
loud and survivable rather than fatal, and that is a property of the
pair (this escalation ladder, this handler), not of the watchdog.

**And the violation count is not the count of short intervals.** At
`WINS = 2` the window opens at 10,020 and the shortest interval is
7,836, so more than one kick arrives before it — and only **two** are
recorded as violations, because **a rejected kick is not a reload**:
after the first violation the counter goes on running down from the last
*accepted* kick, so the next kick arrives further into the period and is
admitted. "How many intervals are short" and "how many violations there
are" are therefore not the same number, which is why the sweep is the
instrument and the arithmetic is only the bound.

### 6.2 The timeout, and the box `WINS = 1` puts it in

`WINS = 1` requires both bounds at once:

    T > i_max = 11,042        and        T < 2 · i_min = 15,672

so **the timeout is confined to a 42 %-wide band** and
`SUP_WDOG_RELOAD = 834` puts it at `T = 13,360` clocks, 21.0 % above the
floor and 17.3 % below the ceiling **[estimate, arithmetic on the
measured cadence]**.

**This is a cost of W7 that is paid before any upset happens, and it is
not in `docs/43`'s accounting.** Without a window the only bound is
`T > i_max`, and a designer would take a comfortable multiple —
`docs/43`'s own windowed build sits at 1.48 × `i_max` **[estimate,
6,144 / 4,164 from its section 4.4]**, which here would be 16,300, and
2× would be 22,100. With `WINS = 1` armed, 15,672 is a *ceiling*. **A
window therefore forces a shorter timeout than the same designer would
otherwise choose, and a shorter timeout is a more trigger-happy one.**
Section 8 reports how many of the campaign's spurious escalations are
ordinary expiries at this timeout rather than window violations, because
that is the number this paragraph predicts.

### 6.3 What the supervisor had to do to be able to declare a contract at all

Two obligations, both of which shaped the program and neither of which
is a free feature.

**The timeout is shortened at the start of the operational phase, not at
reset.** The watchdog's reset default is the maximum, 1,048,576 clocks
(`soc_wdog.v` W1 and `docs/40` section 5.7: a short default risks a
board whose boot is slower than its watchdog), and that is what protects
initialisation. The supervisor shortens it, kicks, and declares the
contract at the one point where the cadence it is declaring actually
begins. **A contract is a statement about a phase and the phase has to
be entered first.**

**And it is declared after a kick and not before one.** `docs/43`
section 4.6 found by running it that a window armed before a kick makes
the very next kick early, because out of reset the counter is far above
the open point. This program does it in that order for that reason, and
`sw/tests/test_soc_supervisor_guards.py` counts the kick sites so that a
later edit that removes the arming kick is a red test.

### 6.4 Both bounds are build-time errors, and the guard has no default

A build that gets either bound wrong does not fail; it escalates in a
loop. So a build that declares a contract must state its own **measured**
`i_min` and `i_max` on the command line, and `fi_supervisor.c` refuses to
compile if `T <= i_max` or if `T · (1 − 2^-WINS) >= i_min`.

**There is deliberately no default for either.** A default would be a
number for one dispatch discipline at one frame period, silently wrong
for the other — and a guard that is inert unless somebody remembers to
arm it is a guard that reads wider than it is, which is the class of
defect `docs/41` section 6.6 lists nine instances of. The first version
of this file had exactly that: `SUP_KICK_MAX` defaulted to zero and the
check was skipped in every build that did not pass it.

All three failure modes were provoked and all three are build errors
**[fact]**: a windowed build with no stated cadence, one at
`SUP_WDOG_RELOAD = 600` (`T = 9,616 < i_max`), and one at `WINS = 2` on
the measured cadence — which is the arithmetic bound of section 2
agreeing with the sweep of section 6.1 by a completely different route.
And the fixed file produces a **byte-identical** ROM image to the one
the campaign ran (`md5sum fd78a069…`) **[fact]**, because the guard is
preprocessor arithmetic and emits no code.

---

## 7. The other dispatch discipline, and why it decides the answer

### 7.1 One `wfi`

`-DSUP_FREERUN` builds the same partitions, the same schedule, the same
kick placement and the same code work-triggered: the next frame starts
the instant the previous one finished. That is the other plausible
reading of `docs/09`'s "event-driven loop", and **`docs/09` has not
chosen between them**: track 3 names a scheduler and an event-driven
loop and says nothing at all about a period, a frame or a tick **[fact,
`docs/09` part B track 3 contains none of those three words]**.

The two builds produce the **same answer**, `sig = 216f8ce6`, which is
the check that they are the same program **[fact]**.

### 7.2 No window is feasible in it, and that is arithmetic before it is a measurement

`i_min = 2,118` and `i_max = 4,456`, ratio **2.104** **[fact,
`hw/soc/out/sup-free`, the program with no contract declared]**, and
`WINS = 1` permits 2.0. Written as the two bounds:

    T > 4,456        and        T < 2 · 2,118 = 4,236

**and there is no such `T`.** The window is not "tight" in the
work-triggered discipline; it is empty. In the build that declares the
contract the same measurement is 2,148 to 4,480, ratio **2.086**
**[fact]** — the store that declares it lands inside the first
interval — and the interval is empty there too, by 244 clocks.

### 7.3 Measured, at two timeouts, because an empty interval is easy to state and worth showing

| timeout `T` | `WINS` | early kicks | stage-1 NMIs | reading |
|---:|---:|---:|---:|---|
| 4,464 | 0 | 0 | **1** | 8 clocks above the 4,456 measured with no contract, and *below* the 4,518 this build measures — so the ordinary watchdog already expires once |
| 4,464 | 1 | **3** | 5 | and the window rejects three kicks on top of that |
| **6,320** | **0** | **0** | **0** | at 1.41 × `i_max` the ordinary watchdog is **silent and clean** |
| **6,320** | **1** | **4** | 5 | the same timeout with `WINS = 1` rejects **four of the six** kicks of a healthy program |

**[fact, the four work-triggered builds of section 13]**

The last two rows are the point. **At a timeout the ordinary watchdog is
perfectly happy with — zero escalations, zero violations — arming
`WINS = 1` and changing nothing else makes it reject four of six kicks
and raise five NMIs on a machine with nothing wrong with it.** And there
is no other setting of `T` that fixes it, because section 7.2's interval
is empty. The first two rows are the other end of the same box: pushing
`T` down towards the floor to make the window open earlier breaks the
upper bound instead.

### 7.4 So the answer to "can realistic software live inside a window" is: it depends on a choice nobody has made

The same supervisor, the same partitions, the same kick placement, the
same argument for that placement — and one architectural decision that
`docs/09` track 3 leaves open — is the difference between `WINS = 1`
being usable and no window being usable at all. **That is the finding of
this document and section 9 is what follows from it.**

---

## 8. The campaign

### 8.1 What was run, and what it is a measurement of

**812 single-bit upsets, 14 strata of 58, each run twice — once with the
watchdog armed and once with `wdog_dis_i` held high — 1,624
simulations.** `hw/soc/fi/campaign.py` and `hw/soc/fi/targets.py` are
`docs/42`'s, unmodified; the strata, the stratified draw, the five
controls and the five classes are all `docs/42` section 4 and 5's.

The configuration is **the design as it would ship with W7 kept**: the
SECDED register file of `docs/43`, `WINS = 1`, the kick budget armed at
`SUP_FRAMES + 2 = 8`, `T = 13,360`, the time-triggered supervisor. That
choice matters for how the result reads and is stated here rather than
left to be inferred: **the register file removes the corrupted-loop-bound
class at source** (`docs/43` section 8.2), so — exactly as in `docs/43`'s
campaign AW — W8 has almost nothing to do in this campaign and the
question being asked of W7 is *what it adds to a design that already has
the register file and the ordinary escalation ladder.* That is the
question a keep-or-delete decision has to answer.

All five controls pass **[fact]**. Control 4a, the positive control,
classifies **CORRECTED** — the register file repaired bit 20 of the stack
pointer — which is `docs/43` section 8.1's observation reproduced on a
different program. The clean run is 69,100 cycles with a measured
injection window of 9,382..67,318, **84 % of the run**, and the budget
is 298,520 cycles, which leaves **8.7 complete escalation ladders** after
the latest cycle any injection can be drawn at **[fact]**.

**The sample is 58 draws per stratum and not 100, and how that came
about is worth one sentence.** The campaign was run in resumable chunks,
in **round-major order** — the first *m* draws of every stratum, which
because `campaign.py` seeds each draw per (stratum, index) *is* a
complete stratified campaign at *m* per stratum. It was stopped at 58
complete rounds for wall-clock reasons and not for any reason to do with
the numbers. Every record is produced by `campaign.py`'s own `Runner`,
`draws` and `classify`; the report in `hw/soc/out/sup-wc/campaign.log` is
`campaign.py --replay` on the resulting `records.csv`, so nothing in it
was computed by anything else. **This is a smaller campaign than
`docs/43`'s 1,400 and section 8.4 says where that bites.**

**One thing about this workload that changes how the draws land.** The
supervisor idles in `wfi` for about 69 % of the injection window, which
is what a 50 % worst-case CPU margin looks like at an average frame. An
upset deposited while the core is clock-gated is **not** wasted: nothing
overwrites it, so it sits in the flip-flop until the core wakes. If
anything it dwells longer than one deposited into a busy machine.

### 8.2 The distribution

Per stratum **with the watchdog held off** — the core with no backstop —
and both totals:

| stratum | n | MASKED | CORRECTED | SDC | DETECTED | HANG |
|---|---:|---:|---:|---:|---:|---:|
| `regfile` | 58 | 2 | **56** | 0 | 0 | 0 |
| `regfile_ecc` | 58 | 0 | **58** | 0 | 0 | 0 |
| `controller` | 58 | 42 | 0 | 0 | 7 | **9** |
| `csr_pmp` | 58 | 34 | 0 | 0 | **24** | 0 |
| `csr_trap` | 58 | 49 | 0 | 0 | 7 | 2 |
| `fetch_fifo` | 58 | 45 | 0 | 3 | 9 | 1 |
| `multdiv` | 58 | 55 | 0 | **3** | 0 | 0 |
| `if_id` | 58 | 52 | 0 | 1 | 5 | 0 |
| `id_ctrl` | 58 | 55 | 0 | 2 | 1 | 0 |
| `pc_fetch` | 58 | 54 | 0 | 0 | 3 | 1 |
| `lsu` / `top_ctrl` | 58 each | 55 | 0 | 0 | 3 | 0 |
| `csr_cnt` / `csr_debug` | 58 each | 58 | 0 | 0 | 0 | 0 |
| **ALL, watchdog held off** | **812** | **614** | **114** | **9** | **62** | **13** |
| **ALL, watchdog armed** | **812** | **610** | **114** | **7** | **81** | **0** |

**[fact, `hw/soc/out/sup-wc/campaign.log`]**

The design-weighted rates, on the estimator of `docs/42` section 4.5:
**SDC 0.6 % ± 0.4 with the watchdog held off and 0.5 % ± 0.4 armed;
HANG 0.5 % ± 0.5 held off and 0.0 % armed** **[fact]**. They are not
directly comparable with `docs/43`'s — a different program produces a
different rate, which is the whole reason this document exists — and no
comparison is drawn from them here.

**The register file did on this program what it did on the other one.**
114 of 812 injections were corrected, **all 114 ended with the golden
answer**, and there were **zero uncorrectable syndromes** **[fact]**.

### 8.3 What the backstop did

| | value |
|---|---|
| upsets that leave the core DEAD with no backstop | **32 of 812** |
| of those, the watchdog escalated | **32 — 100.0 %** [89.3 – 100] |
| of those, ended with the golden answer after the reset | **29** |
| highest stage reached | stage 1: 3, stage 2: 29 |
| deposit to first escalation | min 3,203, median 9,191, max 16,600 clocks (one timeout is 13,360) |
| **spurious escalations**, over survivable upsets | **4 of 728** — 0.5 % [0.2 – 1.4] |
| wrong answer with nothing announced | 49 of 52 WRONG |

**[fact]**

**The DEAD fraction is nearly twice `docs/43`'s** — 3.9 % against 2.1 %
— and the reason is structural rather than statistical: this supervisor
makes progress only when its timer interrupt arrives, so every upset
that stops the tick leaves it asleep for ever. `controller` contributes
14 of the 32 and `csr_trap` 8. **A program that waits has more ways to
die than a program that spins**, and that is a property of the
architecture `docs/09` chose, not of this workload's arithmetic.

### 8.4 What W7 did, and the replay that attributes it

**W7 rejected a kick as too early on 9 of 812 injections. W8 ran a phase
out of kicks on none** **[fact]**. Those nine, with what else announced
them:

| stratum | site | bit | truth | early kicks | stage | self-checks | trap | alert |
|---|---|---:|---|---:|---:|---|---|---|
| `controller` | `ctrl_fsm_cs` | 1 | OK | 3 | 1 | no | no | no |
| `controller` | `ctrl_fsm_cs` | 1 | OK | 1 | 1 | no | no | no |
| `controller` | `ctrl_fsm_cs` | 1 | OK | 1 | 1 | no | no | no |
| `controller` | `ctrl_fsm_cs` | 2 | OK | 3 | 1 | no | no | no |
| `csr_pmp` | `pmpaddr2` | 9 | WRONG | 2 | 1 | yes | yes | no |
| **`multdiv`** | **`mult_state_q`** | **1** | **WRONG** | **1** | **1** | **no** | **no** | **no** |
| **`multdiv`** | **`mult_state_q`** | **0** | **WRONG** | **2** | **1** | **no** | **no** | **no** |
| `fetch_fifo` | `instr_addr_q` | 28 | DEAD | 1 | 2 | no | no | yes |
| `fetch_fifo` | `instr_addr_q` | 22 | DEAD | 1 | 2 | no | no | yes |

**[fact, `hw/soc/out/sup-wc/records.csv`]**

Three readings, and the second is the one this document was written to
find.

**The two DEAD records were caught anyway.** All 32 DEAD injections
escalated, W7 was involved in two of them, and both reached **stage 2**
— an ordinary expiry the window did not need to produce. W7 adds nothing
on the set a watchdog exists for, which is `docs/43` section 8.4's
result reproduced on a second program.

**The two `mult_state_q` records are a genuine catch, and it is
verified by replay rather than inferred.** Both are wrong answers that
**nothing else in the design announced** — not the self-checks, not a
trap, not an alert pin. All seven non-DEAD records were replayed
**verbatim** — same site, same bit, same cycle — against a build
identical except that `WINS = 0` and the budget is unreachable:

| site | bit | cycle | with `WINS = 1` | with `WINS = 0` | truth |
|---|---:|---:|---|---|---|
| `pmpaddr2` | 9 | 30,455 | DETECTED | DETECTED | WRONG |
| **`mult_state_q`** | **1** | **24,388** | **DETECTED** | **SDC** | **WRONG** |
| **`mult_state_q`** | **0** | **34,145** | **DETECTED** | **SDC** | **WRONG** |
| `ctrl_fsm_cs` | 1 | 52,528 | DETECTED | DETECTED, by expiry | OK |
| `ctrl_fsm_cs` | 1 | 22,681 | DETECTED | **MASKED** | OK |
| `ctrl_fsm_cs` | 1 | 9,828 | DETECTED | **MASKED** | OK |
| `ctrl_fsm_cs` | 2 | 53,996 | DETECTED | DETECTED, by expiry | OK |

**[fact, `hw/soc/out/iso-w7only/directed.csv`]**

So, attributed rather than assumed:

- **W7 converted two silent data corruptions into announced failures.**
  Both were SDC without it. That is the first time in this repository
  that the window has caught anything, and the class is the one section
  5.1 of `docs/43` said it was for — a machine sweeping through its kick
  site too often, here because a corrupted multiplier FSM shortens the
  frame.
- **Two of the four spurious escalations are W7's and two are not.** The
  `ctrl_fsm_cs` records at 52,528 and 53,996 escalate at `WINS = 0` too,
  by ordinary expiry — which is section 6.2's prediction arriving: the
  window forced the timeout down into a band, and a shorter timeout is
  more easily tripped by an upset that merely slows the machine. **The
  window's true false-positive cost on this workload is 2 of 728**, and
  the other two are the price of the *timeout* the window obliged.
- **All seven stayed at stage 1**, an NMI the handler acknowledged, and
  the four OK records all still produced the golden answer.

**And the honest arithmetic on those two numbers.** W7's measured
benefit is **2 of 812** — 0.25 % [0.07 – 0.89] — and its measured cost
is **2 of 728** — 0.27 % [0.08 – 1.00] **[fact, Wilson]**. **The
intervals overlap almost completely: at this sample size the benefit and
the cost are the same size and cannot be told apart.** Worse for the
reading, both numbers are two draws at **one site each** — `mult_state_q`
and `ctrl_fsm_cs` — so they are two site behaviours and not four
independent events. **A campaign four times this size might separate
them. This one does not, and no sentence in section 9 is allowed to
pretend otherwise.**

**One caveat on the replay, the same one `docs/43` section 5.4
records.** The `WINS = 0` build is a different ROM image — one store's
operand differs — so the injected cycle lands in a marginally different
program. What says the class was reproduced and not merely replayed is
the `truth` column: it agrees on all seven records, so the machine with
no backstop did the same thing in both builds.

### 8.5 W8 fired zero times, for the reason `docs/43` gives

The only failure class that exhausts a kick budget is a phase that kicks
more often than it declared, and the register file corrects the
corrupted loop bound that produces it before the loop is ever wrong
(`docs/43` section 8.4). **W8 has nothing to do in a campaign on the
hardened design**, and `docs/43` section 5.4's isolation builds remain
the only place in this project where it has been shown to work. Nothing
here weakens that and nothing here strengthens it.

### 8.6 A finding that is not about the watchdog: the isolation mechanism is a new fault surface

`csr_pmp` — `pmpaddr0..3`, `pmpcfg0`, `mseccfg` — is **the worst stratum
in this campaign by wrong answers**: 23 of 58 injections produce a WRONG
result and 24 of 58 classify DETECTED, against zero WRONG in `regfile`
and three in `multdiv` **[fact]**.

This is new, and it is new because of the *software*. `docs/42`'s and
`docs/43`'s workload never wrote a PMP register, so the stratum was
nearly inert in both. This one reprograms `pmpaddr1` on **every one of its
24 partition dispatches**, and the PMP registers are now live
architectural state that the isolation depends on. An upset in them does
not break the arithmetic; it makes a partition fault, which the
supervisor contains — every one of those 23 was announced, 43 of the 52
WRONG runs by the program's own self-checks and 41 by an unexpected trap.

**So the S2 architecture buys containment and pays for it with a new
soft target, and neither `docs/09` nor `docs/43` had priced that.** It
is not a watchdog question and this document does not pursue it; section
9.4 records it as work.

---

## 9. Recommendation

### 9.1 The recommendation

> **W7 is CONDITIONAL, and on the evidence here the condition should not
> be taken. Remove it before floorplanning — and record, in `docs/09`
> part B track 3, the five requirements that would have to be adopted if
> anybody ever wants it back.**

This is the third of the three answers this work could have produced,
and it is not a way of avoiding the other two. The two that were
available and are not being given:

- **"W7 earns its place"** is not available, because feasibility is not
  a property of the hardware. Section 7: the same supervisor, the same
  partitions, the same kick placement, run work-triggered instead of
  time-triggered, admits **no window at any timeout** — and `docs/09`
  has not chosen between those two dispatch disciplines. A mechanism
  that a still-open software decision can render unusable has not earned
  a place in a netlist.
- **"W7 is worthless, delete it"** is not available either, and this is
  the finding that stops it. Section 8.4: **W7 converted two silent data
  corruptions into announced failures, verified by verbatim replay
  against a `WINS = 0` build.** `docs/43` measured its value at exactly
  zero; on a second, more realistic workload it is not zero. The
  document that reported the negative result was right about that
  workload and would have been wrong to generalise it, and this document
  is not going to make the mirror-image mistake.

**What tips it is that the benefit and the cost are the same size and
this campaign cannot separate them.** 2 catches in 812 injections
against 2 window-attributable spurious escalations in 728 survivable
ones — 0.25 % [0.07 – 0.89] against 0.27 % [0.08 – 1.00] — from two
sites, one each. On that evidence W7 is not a mechanism that works; it
is a mechanism whose sign is unmeasured. **A design decision taken
before floorplanning has to be taken on the evidence that exists, and
the evidence that exists does not support spending area and five
software requirements on a mechanism whose net effect cannot be shown
to be positive.**

**The strongest argument against this recommendation is in section 9.3
and it is not being hidden.** The oracle scores a machine that runs its
schedule *fast* as OK, so W7's measured benefit is a lower bound and its
measured cost an upper bound; a fairer instrument could move both
numbers in W7's favour. That is why the answer is "remove it and write
down what would bring it back" rather than "delete it". **What the bias
does not touch is section 7**, which is an argument about feasibility
rather than about value: no bias in the oracle makes a window exist for
the work-triggered discipline, because the interval `i_max < T < 2·i_min`
is empty there whatever the campaign says. **The feasibility argument
alone carries the recommendation, and the value argument is what makes
it reversible rather than final.**

**And the decision is reversible in the direction that matters.**
Removing W7 is a `WINDOW = 0` instantiation and a deletion, both of
which `hw/soc/rtl/soc_wdog.v` already supports and both of which are
proved (`prove_w0`, `docs/43` section 9.3). The RTL, the properties and
this measurement stay in history. What is *not* reversible is
floorplanning a block whose software preconditions nobody has agreed to.

### 9.2 What keeping W7 would cost the software, written as the requirement it would be

`docs/09` part B track 3 would have to carry all five of these, because
each of them is load-bearing for something measured above:

| | requirement | what it comes from |
|---|---|---|
| **R1** | The supervisor is **time-triggered**: every frame opens on a periodic tick and the supervisor idles between the end of one frame's work and the start of the next. | Section 7. Work-triggered dispatch admits no window at any timeout |
| **R2** | **Exactly one kick per frame**, in the supervisor, after every partition has run and returned. No other code kicks, and the isolation mechanism must deny U-mode the peripheral bus so that no other code *can*. | Sections 4 and 5.3. `docs/42`'s ordinary six-kicks-per-round style measures 57.2 |
| **R3** | The **frame period** is at least the worst-case frame execution time, and the CPU margin is a stated number. | Section 5.1; section 10's third bullet is the sensitivity |
| **R4** | The operational phase's `i_min` and `i_max` are **measured on the shipping software** and the timeout is chosen inside `i_max < T < 2·i_min`. The build refuses otherwise. | Sections 6.2 and 6.4 |
| **R5** | The contract is armed **after a kick**, at the start of the phase whose cadence it describes, and a stage-2 reset restores `WINS = 0`. | Section 6.3 and `docs/43` sections 4.6 and 5.3 |

**R1 is the expensive one and it is not a free choice.** It forecloses
the work-triggered dispatch discipline for the life of the part, and
that discipline is the one that finishes the schedule soonest and is the
natural shape of `docs/09`'s "event-driven loop". Committing to R1 to
keep a hardware feature is the tail wagging the dog unless the feature
earns it.

**And R4 is a recurring obligation, not a one-off.** The cadence is a
property of the software, so every change to the schedule — a partition
added, a frame's work lengthened, a new peripheral whose handler runs
inside a frame — re-opens it. Section 10's second bullet is why that is
not a small thing: every one of those changes pushes the jitter ratio up
and none pushes it down.

### 9.3 What deleting it costs, and what it does not

**The area recovered is less than 4,904 um2 and this document cannot say
how much less.** `docs/43` section 7.3 measures W7 and W8 **together**
at +4,904.0964 um2 on the watchdog, and there is no parameter that
builds one without the other, so the split is **not measured**. By
flip-flop count alone the two are close: of the 29 flip-flops the pair
adds, **15 are W7's** — `WINS`'s four bits and the `EARLY` record,
tripled by W6's replication — and **14 are W8's** — `BUDARM` and
`BUDGET` tripled, plus `kick_left`'s eight **[estimate, arithmetic on
`docs/43` section 7.3's own breakdown]**. The combinational split is not
even estimable from here: W7 needs a variable shift of the reload by
`WINS` and a comparator against the counter, W8 an eight-bit down-counter
and a zero test. **Measuring it is a one-parameter change to
`soc_wdog.v`, and this document wrote no RTL.**

**W8 stays, and W8 is the one that works.** `docs/43` section 5.4
replayed `docs/42`'s four `x23` records verbatim: the budget caught four
of four, including one that was a silent wrong answer rather than a
hang. Nothing here disturbs that.

**The larger saving is R1 to R5.** Deleting W7 returns a free
architectural choice to `docs/09` track 3 and removes a standing
obligation to re-measure a cadence after every schedule change.

**What is genuinely lost, and it is not nothing.** W7 is the only
mechanism in this design that can see a machine running **too fast**, and
section 8.4 measured it doing exactly that: two upsets in the
multiplier's state machine shortened the frame, the kicks arrived early,
and two wrong answers that **nothing else in the design announced** were
announced. Deleting W7 gives those two back to the silent-corruption
column.

**And the loss is larger than the campaign can show**, because the
oracle cannot score the class W7 is best at. Section 10's fourth bullet:
a supervisor that lost its frame synchronisation and ran its schedule
back to back produces the **right** answer early, and `campaign.py`
scores that OK — so a W7 escalation on it is counted here as a spurious
escalation when in a real-time system it would be a detection. **W7's
measured benefit in section 8.4 is therefore a lower bound and its
measured cost an upper bound**, and section 9.4's third trigger is the
instrument that would separate them. That, and not the area, is the
reason to keep the RTL and this measurement in history rather than to
keep the block in the netlist.

### 9.4 The three conditions that would reverse this

Stated as triggers, in `docs/09` part C's style, so that "revisit it"
is a test and not a sentiment.

| | trigger | action |
|---|---|---|
| **T1** | `docs/09` track 3 **commits** to a time-triggered frame schedule and adopts R1–R5 as requirements *for reasons of its own* | W7 becomes free of its precondition. Re-run section 6.1's sweep on the shipping supervisor and keep W7 if it passes |
| **T2** | A campaign **four times this size** — or one on a workload with more than one multiplier-shaped failure — separates 0.25 % from 0.27 % | Whichever way it separates, that is the answer. This campaign's own numbers say what size would do it |
| **T3** | The project acquires an oracle that can score a **timing** failure — an architectural-state comparison, or a deadline the classifier checks | W7's two catches were both machines running *fast*, and `campaign.py` cannot see that class as a failure at all. Its measured benefit here is a **lower bound** for that reason |

And one item that this document turned up and is not qualified to
pursue: **section 8.6's `csr_pmp` result.** The isolation mechanism
`docs/09` chose is now the worst stratum in the campaign by wrong
answers, and no document has priced it. It belongs on the same list as
`docs/43` section 12's `mtime`.

---

## 10. What this does NOT cover

Stated at length, because this repository has been bitten by a green
check read as wider than the thing it examined a dozen times —
`docs/28` 4.4a, `docs/34` 8.5, `docs/36` 3.3, `docs/38` 7.3 and 8.2,
`docs/39` 3, twice in `docs/40`, `docs/41` 8.4, `docs/42` 5.1 and
`docs/43` 9.5 and 9.6.

- **Two workloads is still two.** `docs/43` section 10 already records
  that one workload is one workload; this document does not repair that,
  it adds a second data point of a different kind. The kick cadence of
  the S2 supervisor that actually ships will be neither of the numbers
  in section 5.3, because that supervisor does not exist.
- **A jitter ratio measured on this simulator is not a flight
  measurement.** There is no cache, no branch predictor, one memory
  latency, no bus contention from any master but the core, and the only
  interrupt in the run is a timer this program programmed itself. **A
  real part has a mission data bus, a SpaceWire or CAN controller, an
  NPU raising completions, and DMA** — every one of which lengthens some
  frames and not others, and all of which push the jitter ratio up and
  never down. **The measured 1.412 is therefore a lower bound on the
  ratio the real supervisor will have**, and `WINS = 1`'s bound of 2.0
  is 42 % above it. Whether that margin survives a real peripheral set
  is unknown and is not knowable from here.
- **The frame period is a convention, not a requirement**, and the
  jitter ratio depends on it. The 50 % CPU margin of section 5.1 is
  standard practice and nobody on this project has written it down as a
  requirement. The period is the constant term in `P + W_f − W_{f−1}`,
  so a tighter margin raises the ratio: the measured extremes are
  `P − 1,076` and `P + 2,152` **[fact]**, which at `P = 8,912` is 1.412
  and at a 20 % margin (`P = 5,347`) would be **1.750** **[estimate,
  arithmetic]**. The bound is reached only at `P = 4,304`, which is
  *below* the worst-case frame itself, so — for this program, and only
  for this program — **`WINS = 1` stays admissible at every schedulable
  frame period, with the margin to the bound shrinking from 42 % to
  about 2 %.** That is a robustness result and it is a narrow one: it
  says nothing about a supervisor with different frames.
- **The oracle is the run's output, not the machine's timing.** This is
  the sharpest limitation in this document and it cuts against W7's
  case, not for it. A supervisor that lost its frame synchronisation and
  ran its schedule back to back would produce **the right answer, early**
  — and `campaign.py` scores that OK, so a W7 escalation on it counts in
  section 8 as a **spurious** escalation. In a real-time system it is a
  failure. All four of section 8.4's OK-truth escalations are of that
  shape, and two of them are W7's; whether they are false positives or
  the only detections of a lost schedule is a question this oracle
  cannot answer. Section 9.3 says which way that biases the two numbers
  the recommendation turns on.
- **The campaign is 812 injections and `docs/43`'s was 1,400.** It was
  stopped at 58 complete rounds for wall-clock reasons. That matters in
  exactly one place and section 8.4 says so there: the two numbers the
  recommendation turns on are 2 of 812 and 2 of 728, whose 95 %
  intervals overlap almost entirely, and a larger campaign is the first
  of section 9.4's three triggers.
- **RTL, single-bit, flip-flop only.** No gate-level netlist, no
  back-annotated timing, no multi-bit strike, no transient in
  combinational logic. `docs/42` section 4.4 and `docs/43` section 10
  say the rest.
- **The supervisor is not verified.** No MISRA subset, no Frama-C, no
  CBMC — `docs/09` part B track 3 lists all three as the evidence S2 is
  supposed to carry and none of them is here. This is a workload, not a
  supervisor.
- **The isolation control is one control.** Section 3.4 shows that a
  read outside the region faults. It does not show that every region is
  the region intended, that the reprogramming on dispatch is correct for
  every partition, or that a partition cannot reach another's memory —
  only that PMP is enforcing something.
- **Nothing here was proved.** `hw/soc/formal/soc_wdog.sby` proves W7 and
  W8 and is untouched; no property was added, because this document
  measures software against hardware that is already proved and adds no
  hardware.
- **`soc_top.v` has still never been synthesised as one design**, and no
  SoC block has been through place and route, timing closure or
  gate-level simulation.

---

## 11. Relations to earlier documents

**No earlier measurement is corrected.** Every number in `docs/42` and
`docs/43` stands as written; this document adds a second program and
does not re-run the first.

- **`docs/43` section 12 item 5** is the open point this document
  closes. `docs/43` allowed two answers — keep it or remove it — and
  section 9 gives a third: remove it, and write down the conditions
  under which it would be worth having back.
- **`docs/43` section 10**, "Whether `docs/09`'s S2 supervisor can be
  written to a jitter ratio below 2 is unknown and is a design
  constraint on it that did not exist before", is now **partly**
  answered: it can, if it is time-triggered, and it cannot if it is
  work-triggered. The constraint is real and section 9 says where it
  belongs.
- **`docs/43` section 4.3**'s two cadences, 57.2 and 1.018, are the
  first two rows of section 5.3 and are unchanged. What this document
  adds is that neither of them was a fact about realistic software, and
  that the realistic number is between them and depends on an
  architectural choice.
- **`docs/09` part B track 3** acquires a requirement if and only if W7
  is kept: section 9 states it in the form it would have to take.
- **`docs/38` section 7.5 defects 3 and 4** are exercised again by a
  second startup file and were not re-encountered, because
  `link_soc.ld` asserts both and is shared. Section 3.3.
- **`docs/41` section 8.2**'s zero spurious escalations remains the
  number W7 spends, and section 8 reports what it spent on this
  workload.

---

## 12. Files touched

`docs/34` section 2 pins the pilot by git blob hash of the files in
`hw/rtl/` and section 5 lists the flow configs. **Nothing in either set
is modified** **[fact]**, and **no RTL of any kind was written or
changed for this document.**

| File | Change |
|---|---|
| `hw/soc/tb/sw/fi_supervisor.c` | new — the supervisor, its four partitions, and the kick-placement argument |
| `hw/soc/tb/sw/sup_crt0.S` | new — its startup, vector table, frame tick and privilege switch |
| `hw/soc/tb/sw/sup_config.h` | new — the numbers the C and the assembly share |
| `hw/soc/flow/build_sw_sup.sh` | new — the build, against the shared linker script |
| `hw/soc/flow/fi_core.sh` | `FI_WORKLOAD` selects which program is built; the image name becomes a variable |
| `sw/tests/test_soc_supervisor_guards.py` | new, 13 tests |
| `docs/46-watchdog-window-decision.md` | this document |
| `docs/00-index.md` | one row, which `sw/tests/test_doc_links.py` requires |

**No tooling was added to the repository.** The campaign was driven in
chunks by a scratch script that imports `hw/soc/fi/campaign.py` and calls
its own functions; section 13 says what it does and why it exists, and it
is deliberately not a file of this project, because the instrument is
`campaign.py` and a second scheduler in the tree would be a second thing
to keep true.

**Verification.** `sw/tests/test_soc_supervisor_guards.py`: **13 tests,
13 pass** **[fact]**. The whole `sw/tests` tree passes — **315 collected,
315 passed** **[fact]**; `docs/43` closed at 295 and the difference is
this document's 13 and work in flight beside it. Nothing in
`hw/soc/formal/` was added or re-run: this document measures software
against hardware that is already proved.

**Read and not modified**: `hw/soc/rtl/soc_wdog.v` (W7 and W8 are
already in it), `hw/soc/tb/tb_soc_fi.v`, `hw/soc/fi/campaign.py`,
`hw/soc/fi/targets.py`, `hw/soc/tb/sw/link_soc.ld`,
`hw/soc/tb/sw/crt0.S`, `hw/soc/tb/sw/fi_workload.c`.

**That the instrument was not touched is the load-bearing part.** A
second workload measured by a modified testbench or a modified
classifier would not be comparable with `docs/42`'s or `docs/43`'s, and
the comparison is most of what this document is for. The testbench runs
this program because the program publishes the same four words
`fi_workload.c` publishes, and for no other reason.

---

## 13. Reproducing this

```
make -f hw/soc/tools.soc.mk fetch-ibex fetch-sv2v fetch-rvgcc
hw/soc/flow/sv2v_ibex.sh hw/soc/ext/ibex hw/soc/gen \
                         hw/soc/tools/sv2v-Linux/sv2v

# The worst-case frame execution time, from which the frame period is
# derived: work-triggered, so a kick interval IS one frame.
FI_WORKLOAD=supervisor SW_DEFINES="-DSUP_FREERUN" \
  hw/soc/flow/fi_core.sh hw/soc/out/sup-free
vvp hw/soc/out/sup-free/tb_soc_fi.vvp +armed=1 +budget=400000

# The time-triggered cadence, at a period of twice that worst case.
FI_WORKLOAD=supervisor SW_DEFINES="-DSUP_TICK_PERIOD=8912" \
  hw/soc/flow/fi_core.sh hw/soc/out/sup-tt
vvp hw/soc/out/sup-tt/tb_soc_fi.vvp +armed=1 +budget=600000

# The sweep of section 6.1: seven builds of the clean run.
for s in 0 1 2 3 4 5 6; do
  FI_WORKLOAD=supervisor SW_DEFINES="-DSUP_TICK_PERIOD=8912 \
      -DSUP_WDOG_RELOAD=834u -DSUP_WINDOWED -DSUP_WIN_S=${s}u \
      -DSUP_SWEEP" \
    hw/soc/flow/fi_core.sh hw/soc/out/sup-s$s
  vvp hw/soc/out/sup-s$s/tb_soc_fi.vvp +armed=1 +budget=600000 \
    | grep -E 'wdog1=|wdog_early='
done

# Section 7.3: the work-triggered discipline at two timeouts.
for r in 278 394; do for s in 0 1; do
  FI_WORKLOAD=supervisor SW_DEFINES="-DSUP_FREERUN -DSUP_WDOG_RELOAD=${r}u \
      -DSUP_WINDOWED -DSUP_WIN_S=${s}u -DSUP_SWEEP" \
    hw/soc/flow/fi_core.sh hw/soc/out/sup-free-r$r-s$s
  vvp hw/soc/out/sup-free-r$r-s$s/tb_soc_fi.vvp +armed=1 +budget=600000
done; done

# Section 3.4: the control on the isolation.
FI_WORKLOAD=supervisor SW_DEFINES="-DSUP_TICK_PERIOD=8912 \
    -DSUP_WDOG_RELOAD=834u -DSUP_PROVE_ISOLATION" \
  hw/soc/flow/fi_core.sh hw/soc/out/sup-iso
vvp hw/soc/out/sup-iso/tb_soc_fi.vvp +armed=1 +budget=600000

# The campaign of section 8, and the WINS = 0 build the escalations are
# replayed against.
C="-DSUP_KICK_MIN=7836u -DSUP_KICK_MAX=11064u"   # the MEASURED cadence
FI_WORKLOAD=supervisor SW_DEFINES="-DSUP_TICK_PERIOD=8912 \
    -DSUP_WDOG_RELOAD=834u -DSUP_WINDOWED -DSUP_WIN_S=1u $C" \
  hw/soc/flow/fi_core.sh hw/soc/out/sup-w
FI_WORKLOAD=supervisor SW_DEFINES="-DSUP_TICK_PERIOD=8912 \
    -DSUP_WDOG_RELOAD=834u -DSUP_WINDOWED -DSUP_WIN_S=0u \
    -DSUP_KICK_BUDGET=255u $C" \
  hw/soc/flow/fi_core.sh hw/soc/out/sup-w0
hw/soc/fi/campaign.py --build hw/soc/out/sup-w --draws 58 --jobs 16 \
                      --out hw/soc/out/sup-wc

# and the seven non-DEAD records on which W7 fired, replayed VERBATIM
# against the WINS = 0 build -- which is what attributes section 8.4's
# two catches and two false positives.
python3 - <<'EOF'
import csv
rows = list(csv.DictReader(open("hw/soc/out/sup-wc/records.csv")))
keep = [r for r in rows if int(r["wdog_early"]) > 0 and r["truth"] != "DEAD"]
w = csv.DictWriter(open("w7only.csv", "w", newline=""),
                   fieldnames=rows[0].keys())
w.writeheader(); w.writerows(keep)
EOF
hw/soc/fi/campaign.py --build hw/soc/out/sup-w0 --directed w7only.csv \
                      --out hw/soc/out/iso-w7only

.venv/bin/python -m pytest sw/tests/test_soc_supervisor_guards.py   # 13
.venv/bin/python -m pytest sw/tests                                 # 314
```

**How the campaign was actually run, because it was not one invocation.**
`campaign.py` writes `records.csv` only when it finishes, and this
environment would not keep a two-hour process alive. So the 1,624
simulations were driven in resumable chunks by a scratch script that
imports `campaign.py` and uses its own `Runner`, `draws` and `classify`
— **nothing about the draw, the deposit verification or the
classification is reimplemented** — appending one record per injection to
a journal, and ordering the plan **round-major**: the first *m* draws of
every stratum, which because the draw is seeded per (stratum, index) is
a complete stratified campaign at *m* per stratum. Stopping early
therefore yields a smaller campaign rather than a truncated one, and it
was stopped at **58 complete rounds**. The `records.csv` that results is
`campaign.py`'s own format and every number in section 8 comes from
`campaign.py --replay` on it. The single invocation above reproduces the
same 812 draws in one go on a machine that will let it finish.

**Which design this was measured on.** Everything above was run against
the RTL at commit `3e28344` — the design `docs/43` measured — in a
separate checkout, because work on `hw/soc/rtl/soc_top.v` and the
register file's fault reporting was in flight in the working tree at the
same time. **That is a statement about hygiene and not a claim of
independence**: this document's numbers are comparable with `docs/43`'s
because they are the same design, and they are not a measurement of
whatever `soc_top.v` becomes next.

`hw/soc/out/` is gitignored, by the rule `docs/38` section 11 already
applies: fetched or generated, never vendored. `campaign.py --replay
records.csv` re-prints the whole report without re-simulating anything.
