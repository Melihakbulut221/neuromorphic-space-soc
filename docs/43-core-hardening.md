# 43 — Hardening the core, and measuring whether it delivered

`docs/42-core-fault-injection.md` section 10 ends with two concrete
hardware recommendations, both of them argued from a number rather than
from a preference:

> - **The x23 finding is a real hole and it is cheap to close** … A
>   **windowed** watchdog — one that also fires when kicked too early —
>   costs a comparator and a second reload register, and would have
>   caught all three.
> - **The register file is where the rate lives and it is the cheapest
>   thing to protect** … Parity or SECDED over 31 words, using the codec
>   this project already owns and has proved, is the
>   measured-highest-value hardening available in this core.

This document builds both and then measures whether they did what they
were built to do. One of them did. **The other did not, and the reason
is that `docs/42`'s own inference about it was wrong** — a windowed
watchdog fires on a kick that arrives too *early*, and the machine
`docs/42` section 8.1 found kicks exactly on time. Section 5 is that
correction, made against a measurement rather than by re-reading the
argument.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
intended, with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was modified.
Three files in `hw/rtl/` are **read**: `tmr_voter.v`, which `docs/41`
already reads, and `secded_enc.v` and `secded_dec.v`, instantiated in
place and not copied. Section 13 lists every file.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| What was built? | **Three things.** A SECDED-protected architectural register file substituted into Ibex; **W7**, a windowed watchdog; and **W8**, a per-phase kick budget, which W7 turned out to need. Section 2 |
| Did the register file move the number it was built to move? | **Yes, decisively.** Re-running `docs/42`'s campaign with **identical draws** — same site, same bit, same cycle, a byte-identical workload image — the register-file strata go from 3 SDC and 4 HANG in 100 to **0 and 0 in 200**, with 190 CORRECTED that all ended with the golden answer and **zero uncorrectable syndromes in 1,400 injections**. Design-weighted SDC **2.8 % ± 1.6 → 1.3 % ± 0.4**, HANG **2.1 % → 0.3 %** **[fact]**. Section 8.2 |
| Did the windowed watchdog? | **No — not on the class `docs/42` recommended it for, and this is the most important negative result in the document.** Replayed verbatim against a build with the window armed and nothing else, all four of `docs/42`'s `x23` records come back exactly as they did: **three HANG, one SDC, nothing escalated** **[fact]**. A window fires on a kick that is too early and that machine kicks on time. Section 5.4 |
| Is the `x23` class of `docs/42` section 8.1 now caught? | **Yes, twice over, and neither time by the window.** W8's kick budget catches **4 of 4** of those same records, turning three HANGs and one SDC into announced escalations **[fact]**. And the register-file protection removes the class at source — an `x23` upset is a single-bit upset in a protected register — so in the design as it would ship the watchdog never sees it. Sections 5.4 and 8 |
| What does the substitution cost the "zero patches to Ibex" claim? | **The claim survives and a weaker one does not.** `hw/soc/ext/ibex` is still a pristine checkout and `hw/soc/gen` is still its unedited sv2v output; what changes is one entry in a *file list*. But the build's Ibex is no longer bit-for-bit the one the pinned commit describes, the substituted file is outside the pinned set, and an upstream interface change is now this project's problem. Section 3 states all four costs |
| Isn't this the duplication `docs/38` declined `SecureIbex` over? | **No, and the document says so rather than leaving it to be noticed.** `docs/38` section 8.5 objected to *two SECDED codecs on one die*. There is still one: `hw/rtl/secded_{enc,dec}.v`, read in place. What has changed is that lockstep *detects* and this *corrects*, over the 45 % of the core's flip-flops that carry most of its measured failure rate. Section 6.1 |
| What does the window cost in false positives? | **A bound on the jitter of the software's kick cadence, and — measured — seven spurious escalations in 1,232 survivable upsets.** `WINS = s` requires `i_max / i_min < 1/(1 − 2^-s)`. The `docs/42` workload, written the ordinary way, measures **25 kicks at intervals of 30 to 1,716 clocks, a ratio of 57.2** **[fact]**, and can use no window at all; rewritten to kick once per round it measures **1.018**, and one notch tighter than the shipped setting turns **every one of a healthy program's kicks** into a violation **[fact]**. `docs/41`'s zero-spurious-escalation headline does not survive this feature. Sections 4 and 8.4 |
| What stops software or an upset from widening the window? | Three things, and the third is the load-bearing one: W5's key, the fact that neither field can *disarm* the block, and that both live inside W6's protected word. Section 4.5 |
| Measured area | **The core: +38,050.5762 um2, +13.80 %, +222 flip-flops** **[fact]**, against a baseline re-measured in the same session that reproduces `docs/38`'s 275,682.6198 um2 exactly. **The watchdog: +4,904.0964 um2 for W7 and W8**, against a `WINDOW = 0` build of the same file. Section 7 |
| Measured timing | **62.6 MHz becomes 56.8 MHz, −9.3 %**, bisected on both configurations with `docs/38` section 8.6's method **[fact]**. The decoder is on the register read path and the register read path feeds the ALU, so unlike lockstep — which `docs/38` measured at 0.27 ns because a shadow core runs in parallel — this correction is *in series* with the thing it protects. Section 7.4 |
| Did the hardening change any behaviour? | **No, and it is measured rather than argued.** The whole-SoC run is cycle-identical to `docs/40` and `docs/41`: 22 checks, stage 1 at cycle 174,128, core asleep after 185,443 cycles, 587 console characters, 0 framing errors. The escalation demo is identical too **[fact]**. Section 9.1 |
| Does the redundancy survive synthesis? | **Counted, not assumed.** 992 data + 217 check + 5 scrub-pointer flip-flops in the mapped netlist, on two technology mappers, dropping to 992 at `HARDEN = 0` **[fact]**. And the check field is **seven** bits per register and not eight, for a reason that is proved rather than observed. Sections 6.3 and 9.4 |
| Is it proved? | 6 formal jobs, 25 tasks, all PASS; 54 of 54 cover obligations reached **[fact]**. Section 9.3 |

---

## 2. What was built

| File | What it is |
|---|---|
| `hw/soc/rtl/ibex_regfile_secded.v` | The substituted register file. `ibex_register_file_ff`'s module name and port list, this project's SECDED codec inside |
| `hw/soc/flow/ibex_sources.sh` | The substitution itself: an Ibex source list with the register file selected by `IBEX_REGFILE`. This is the only place the swap happens |
| `hw/soc/rtl/soc_wdog.v` | **W7** and **W8** join W1–W6 in the header, with a `WINDOW` parameter so their cost is measurable against the same file |
| `hw/soc/rtl/soc_gptimer.v` | Decodes a fifth watchdog register at the watchdog's own `+0xC` |
| `hw/soc/formal/regfile_secded_props.v`, `.sby` | The shortened code, proved: one error corrected, two detected, and the eighth check bit shown not to exist |
| `hw/soc/formal/soc_wdog_props.v` | W7 and W8 stated as properties, plus a `prove_w0` task at `WINDOW = 0` |
| `hw/soc/tb/cocotb/test_ibex_regfile_secded.py` | The register file's own campaign, with a `SCRUB = 0` counterfactual |
| `hw/soc/tb/cocotb/test_soc_wdog_win.py` | W7 and W8 against their requirements, and the measured price of leaving the kick budget unprotected |
| `sw/tests/test_soc_regfile_guards.py` | The netlist census, the guard on upstream's interface, and the check that the codec is still the blob `docs/34` pins |
| `hw/soc/flow/syn_regfile.sh` | The register file measured four ways, like for like |
| `hw/rtl/secded_enc.v`, `secded_dec.v`, `tmr_voter.v` | **Read, not modified.** Instantiated in place |

The division `docs/16`, `docs/41` and `docs/42` already use is kept
unchanged: **the instrument measures and the classifier judges, and they
are different files.**

---

## 3. The substitution, and what "zero patches" actually costs

`docs/38` section 4.2 makes **"patches required to Ibex for the sv2v
path: zero"** a headline, and calls it "the most important line in this
document, because a fork that has to be maintained is a different
proposition from a dependency that is read". That is right, it is
load-bearing, and this work has to be honest about what it does to it.

### 3.1 What was done, and why it is the least invasive thing available

`ibex_top` selects among `ibex_register_file_ff`, `_fpga` and `_latch`
by the `RegFile` parameter, in a `generate if` chain **with no default
branch** — so a fourth value selects nothing and leaves the read ports
undriven. The interface is therefore the only seam there is, and the
substitution is made at it:

```
hw/soc/ext/ibex     pristine checkout at the pinned commit — UNTOUCHED
hw/soc/gen          sv2v output, generated from it — UNTOUCHED
hw/soc/rtl/soc_top.v  instantiates ibex_top — UNTOUCHED
hw/soc/flow/ibex_sources.sh
    IBEX_REGFILE=secded   gen/*.v minus ibex_register_file_ff.v,
                          plus hw/soc/rtl/ibex_regfile_secded.v
    IBEX_REGFILE=upstream gen/*.v
```

**No file is edited to do this.** `git -C hw/soc/ext/ibex status` is
still clean, `hw/soc/gen` is still exactly what `sv2v_ibex.sh` writes,
and the `upstream` mode reproduces the design `docs/38` to `docs/42`
measured — which is not a courtesy, it is what makes the campaign delta
in section 8 a comparison rather than two unrelated numbers.

**The two families of flow default differently, on purpose.** The SoC
flows — `sim_soc.sh`, `fi_core.sh`, `fi_coverage.sh` — default to
`secded`, because the SoC as built is the hardened design.
`syn_ibex.sh` defaults to **`upstream`**, because its configuration
names are `docs/38`'s and a tool that silently measured a substituted
register file under the name `small-pmp` would stop `docs/38` section
8.4's 275,682.6198 um2 reproducing without anything saying so. The
hardened core is measured by asking for it, and section 7.1 asks for
both in the same session.

`hw/soc/flow/sim_ibex.sh` is not touched at all: `docs/38`'s bring-up is
about Ibex and not about this project's register file.

### 3.2 Four costs, stated plainly

**1. The build's Ibex is no longer the Ibex the commit names.** The
zero-patch claim is about the checkout and it survives intact. The
sentence a reader might infer from it — "what we build is upstream's
RTL" — does not, and it did not before either (`docs/38` section 5:
"no equivalence between the SystemVerilog and the sv2v output was
proven"). What is new is a module of this project's own inside
upstream's hierarchy. The strongest evidence that this is behaviourally
transparent is section 9.1: the whole SoC runs cycle for cycle as it did
in `docs/40` and `docs/41`, and the fault-injection workload's ROM image
is **byte-identical** to `docs/42`'s **[fact, `md5sum`]**.

**2. An upstream interface change breaks this, and only some shapes of
it break loudly.** Every connection in `ibex_top.v` is by name, so a
port added or removed fails at elaboration. A port whose *meaning*
changes without its name changing does not, and nothing here catches
that. `sw/tests/test_soc_regfile_guards.py` reads the port list and the
parameter list out of the pristine sv2v output and fails if either has
moved, so the first shape is caught at test time as well as at build
time; **the second is an accepted risk and this is where it is
recorded.**

**3. The substituted file is outside the pinned set.** `hw/soc/ext/ibex`
is pinned by commit in `hw/soc/tools.soc.mk` and `hw/soc/gen` is
generated from it. `hw/soc/rtl/ibex_regfile_secded.v` is neither: it is
ordinary tracked RTL of this project, reviewed and tested as such, and
it carries an obligation that did not exist before — **it must be re-read
against upstream whenever the pin moves.**

**4. The sv2v story is unchanged in kind and smaller in scope.** sv2v
still converts 30 of 30 Ibex modules with zero errors and zero patches;
one of its 34 output files is now excluded from the build rather than
altered. Nothing about the conversion is different.

### 3.3 Three alternatives that were considered and rejected

| Alternative | Why not |
|---|---|
| **A wrapper around `ibex_top`** | The register file is inside `ibex_core`, which is inside `ibex_top`. There is no port at which its contents are visible. This is not a preference; it is arithmetic about the hierarchy |
| **Protection outside the core entirely** — a software checkpoint, a periodic self-check of live registers | It cannot *correct*, it costs instructions in the hot path, and it protects only what the checking code knows to look at. `docs/42` section 7.3 already measured that this project's software self-checks announce more than its hardware does, and section 12 keeps that as a recommendation — but a supervisor cannot repair a register it is holding a value in |
| **Bringing an error port out of `ibex_register_file_ff`** | It is one line, and it is a patch to `ibex_top.sv`, which is the thing the whole arrangement exists to avoid. Section 6.5 is the price of not doing it, and section 12 ranks doing it |

---

## 4. W7, the window: how the bound is chosen and what it costs

### 4.1 The mechanism, in one line of arithmetic

After a reload the counter runs from `reload` down to zero. The window
is **closed** while

    counter > (reload >> WINS)

and a kick that arrives while it is closed is a violation, not a kick.
`WINS` is a four-bit field of the new `WDOGWIN` register.

`WINS = 0` makes the right-hand side `counter <= reload`, which is true
for every reachable counter value — so **the zero case is not a special
case, it is the whole period**, and it is both the reset default and the
value a stage-2 reset restores.

**The window is a FRACTION of the period and not a second absolute
number**, and that is a decision. A separate open-point register could
be set above the reload, which would close the window for ever and stop
every kick — a way to brick the part with one store, which is exactly
what W1 exists to prevent. A fraction cannot be made inconsistent with
the period it is a fraction of.

### 4.2 What the bound *is*, expressed as the rule a program must obey

Write `T` for the timeout `(reload + 1) × PRESCALE` and `i_min`, `i_max`
for the shortest and longest interval between consecutive kicks the
software can produce. Then

    T > i_max                      or a legitimate round expires
    T · (1 − 2^-WINS) < i_min      or a legitimate kick is early

and eliminating `T`:

    i_max / i_min  <  1 / (1 − 2^-WINS)

**So `WINS` is exactly a bound on the jitter ratio of the program's kick
cadence** — 2:1 at `WINS = 1`, 4:3 at 2, 8:7 at 3 **[estimate,
arithmetic]**. That is the entire cost of the window, and it is paid by
the software and not by the hardware.

### 4.3 What that meant for a program written the ordinary way

`hw/soc/tb/sw/fi_workload.c` as `docs/42` wrote it kicks from six places
inside a round, wherever the code happens to pass. Measured on the clean
run:

| workload | kicks in the window | shortest interval | longest | jitter ratio |
|---|---:|---:|---:|---:|
| `docs/42`'s, unchanged | 25 | 30 clocks | 1,716 clocks | **57.2** |
| one kick per round | 5 | 4,090 clocks | 4,164 clocks | **1.018** |

**[fact, the `kick_min` and `kick_max` fields of the clean run's record;
`hw/soc/tb/tb_soc_fi.v` counts every kick request the block sees]**

**A jitter ratio of 57 fits inside no window at all.** `WINS = 1`, the
weakest setting that does anything, permits 2. So the honest answer to
"what makes a legitimate program trip it" is: **the ordinary way of
using a watchdog does.** Kicking from wherever the code passes is how
`fi_workload.c` was written, how `test_ibex.c` is written, and how most
embedded software is written, and every one of those programs would be
reset by a windowed watchdog on its first round.

The windowed build therefore kicks **once per round and nowhere else**,
which is what a program written to live inside a window has to look
like. `FI_WINDOWED` is a separate build rather than a runtime option
precisely because it changes the program, and section 8 keeps the two
campaigns apart for that reason.

### 4.4 The margin, measured rather than asserted

At `FI_WDOG_RELOAD = 383` the timeout is 6,144 clocks. The measured
`i_max` is 4,164, so the deadline has **47.6 % of headroom**; at
`WINS = 1` the window opens at `T·(1 − 2^-1) = 3,072` and the measured
`i_min` is 4,090, so the earliest legitimate kick has **33.1 % of
headroom** the other way **[estimate, arithmetic on the measured
cadence]**. Sweeping `WINS` on the clean run, with everything else held
fixed:

| `WINS` | `T_min` (clocks) | early kicks in the clean run | answer |
|---:|---:|---:|---|
| 0 | 0 | 0 | golden |
| 1 | 3,072 | **0** | golden |
| 2 | 4,608 | **4** | golden |
| 3 | 5,376 | 4 | golden |
| 4 | 5,760 | 4 | golden |
| 5 | 5,952 | 4 | golden |
| 6 | 6,048 | 4 | golden |

**[fact, seven builds of the clean run]**

The transition is exactly where the arithmetic says it is: `i_min` is
4,090 and `T_min` at `WINS = 2` is 4,608, so **every one of the four
in-loop kicks becomes early**, four times per run, on a machine with
nothing wrong with it. That is what a window set one notch too tight
costs, and it is 100 % of the kicks and not a marginal effect.

Two further readings, both of which matter more than the table.

**The run still produced the golden answer at every setting.** Four
spurious stage-1 NMIs did not stop the program: `crt0.S`'s `vec_nmi`
acknowledges and returns, and stage 2 needs a *second* violation with
stage 1 still unacknowledged. So a too-tight window on this software is
loud and survivable rather than fatal — which is the right way round,
and is a property of the *pair* (this escalation ladder, this handler)
and not of the watchdog alone.

**And `docs/41`'s headline is at risk in a way it was not before.**
`docs/41` section 8.2 counted **zero spurious escalations** as a result.
W7 can produce them, on a healthy part, if the window is set wrong —
and "set wrong" is a property of software that the hardware cannot
check. That is why `WINS = 0` is the reset default, why a stage-2 reset
restores it, and why section 8 reports the spurious-escalation count of
the windowed campaign as a first-class number rather than a footnote.

### 4.5 What stops it being widened

The question `docs/40`'s W1 and W5 force, asked of a field that software
writes. Three answers, in increasing strength:

1. **The write is keyed (W5).** `WDOGWIN` is no more reachable by a
   runaway storing wild values than `reload` already is — and `reload`
   decides the timeout itself, which is at least as safety-critical.
   This is not a new class of exposure; it is the class `docs/40`
   already accepted.
2. **Neither field can disarm the block.** `WINS = 0` and a disarmed
   budget restore the conventional watchdog of `docs/40`, which still
   expires, still escalates and still resets. A corrupted write is
   either a loss of the *new* check or a spurious ladder, which is
   loud. Compare `dis_q`, which stops the block entirely — that is the
   bit `docs/41` protects first and the reason W1 admits exactly one
   escape hatch and it is a pin.
3. **An upset cannot widen them either.** `WINS`, the budget's armed
   flag and both violation records are **fields of W6's protected
   word**, by W6's own criterion: software writes them once per phase,
   nothing else rewrites them, and their corruption toward zero is
   silent. The protected word goes from 22 bits to 29 and the flip-flop
   count from 102 to 131, and section 7.3 prices that.

### 4.6 One obligation on software that had to be found by running it

**The contract must be armed immediately after a kick, and not before
one.** Out of power-on reset the counter is running down from its
maximum against a reload software has just shortened, so it is far above
the open point; a window declared at that moment makes the very next
kick early. The first version of
`hw/soc/tb/cocotb/test_soc_wdog_win.py` armed first and kicked second,
and the arming kick tripped its own contract: stage 1 immediately, stage
2 on the next kick, and every test in the file failed for one reason
that had nothing to do with what any of them was checking.

It is now `test_arming_the_contract_before_a_kick_trips_it_immediately`,
stated as a test so that a later reordering is a red result and not a
silent one, and `fi_workload.c` does it in that order for the same
reason.

---

## 5. W8, the kick budget — and a correction to `docs/42`

### 5.1 The correction

`docs/42` section 8.1 found the failure and described it exactly:

> The core is executing its own instructions, in order, at full speed,
> and **petting the watchdog on schedule**.

and then section 10 drew a conclusion that does not follow from it:

> A **windowed** watchdog — one that also fires when kicked too early —
> … **would have caught all three.**

**It would not, and the reason is in `docs/42`'s own sentence.** A
window fires on a kick that arrives too *early*. The `x23` machine is
running the unmodified loop body an unbounded number of times, so its
kicks arrive at exactly the cadence the program was written to produce.
They are not early. Nothing about the timing of a kick distinguishes
"the right loop" from "the right loop, too many times".

This is worth being precise about because the two failure shapes are
easy to conflate and a window does catch one of them. A window catches a
**fast** runaway: a corrupted branch or a corrupted PC that sweeps
through a kick site far more often than the program would. It does not
catch a **long** one.

### 5.2 What does catch it

Only a bound on the amount of work, and the software is the only thing
that knows what that bound is. So a keyed `WDOGWIN` write with `BUDEN`
loads `KICKS` into an eight-bit down-counter and arms it; every accepted
kick spends one; a kick that arrives when it is already zero is a
violation in exactly the sense W7's early kick is.

The contract is a statement about **progress** rather than liveness:
*this phase will kick at most N times, and if it kicks more it is not my
program any more*. `fi_workload.c` declares `FI_ROUNDS + 2` — one kick
per round with two spare, so the contract is about the loop bound and
not a hair-trigger on the exact count.

It is disarmed at power-on reset and by every stage-2 reset, so it is
opt-in per phase, and **a program that never writes `WDOGWIN` gets the
block `docs/42` measured, bit for bit** — which is not left to the reset
value but proved: `soc_wdog_props.v` W7b says that at `WINS = 0` with the
budget disarmed neither mechanism can fire, and the `prove_w0` task
proves every property of W1–W5 again at `WINDOW = 0`.

### 5.3 The failure `docs/40` section 7.2 found, reproduced by this feature

A window or a budget installed before software went wrong would survive
the reset that going wrong caused — everything in this block is in the
power-on domain by W4 — so the fresh boot would trip the same contract
on its first kick and reset again, for ever, with the console never
reaching its first character. **That is precisely the brick `docs/40`
section 7.2 spent a section on**, and the fix is the same line: a
stage-2 reset restores `WINS` to 0 and disarms the budget, beside
restoring the reload to the maximum.

`test_a_stage_2_reset_restores_the_whole_period_and_no_budget` is the
check, and it also asserts the other half: the *records* of what
happened — `EARLY`, `BUDGET`, `WDOGRST` — are not restored with it. A
record software can erase is a record an upset can erase.

### 5.4 The experiment that settles it

Section 5.1 is an argument. This is the measurement, and it was designed
so that only one thing varies.

`docs/42`'s three uncaught DEAD records are `x23` at bits 24, 15 and 29,
and its records also hold a fourth `x23` draw at bit 3 that came back
SDC. All four are **replayed verbatim** — same site, same bit, same
cycle — against three builds that differ only in which mechanism is
armed, with `IBEX_REGFILE=upstream` in every one so that the register
file cannot rescue them and the watchdog has to do it alone:

| build | `WINS` | kick budget | what is being asked |
|---|---|---|---|
| `fi-w7` | 1 | 255, which this run cannot reach | can the WINDOW alone catch it? |
| `fi-w8` | 0 | `FI_ROUNDS + 2` | can the BUDGET alone catch it? |
| `fi-w` | 1 | `FI_ROUNDS + 2` | both, which is what the watchdog would ship as |

The budget of 255 in the first build is how the window is isolated
without changing the file: at one kick per round of about 4,100 clocks,
255 kicks is more than a million clocks and the simulation budget is
110,774, so W8 cannot fire inside the run. That is a weaker isolation
than a parameter would give and it is the honest one available, because
a `WINDOW`-style parameter that removed only W8 would be a fourth
configuration of the RTL invented for one experiment.

**The window alone catches none of them:**

| site | bit | cycle | `docs/42` | `fi-w7` armed | truth | escalated |
|---|---:|---:|---|---|---|---|
| `x23` | 24 | 14,073 | HANG / DEAD | **HANG** | DEAD | **nothing** |
| `x23` | 15 | 9,940 | HANG / DEAD | **HANG** | DEAD | **nothing** |
| `x23` | 29 | 9,670 | HANG / DEAD | **HANG** | DEAD | **nothing** |
| `x23` | 3 | 5,720 | SDC / WRONG | SDC | WRONG | nothing |

**[fact, `hw/soc/out/iso-w7/directed.csv`]**

**The budget alone catches every one of them:**

| site | bit | cycle | `docs/42` | `fi-w8` armed | truth | escalated |
|---|---:|---:|---|---|---|---|
| `x23` | 24 | 14,073 | HANG / DEAD | **DETECTED** | DEAD | **W8 budget** |
| `x23` | 15 | 9,940 | HANG / DEAD | **DETECTED** | DEAD | **W8 budget** |
| `x23` | 29 | 9,670 | HANG / DEAD | **DETECTED** | DEAD | **W8 budget** |
| `x23` | 3 | 5,720 | SDC / WRONG | **DETECTED** | WRONG | **W8 budget** |

**[fact, `hw/soc/out/iso-w8/directed.csv`]**

Four of four, including the fourth record, which is not a hang at all:
bit 3 turns the bound from 4 into 12, so the program finishes — with a
wrong answer, silently, in `docs/42`'s design — and the budget announces
it because twelve rounds is more kicks than the phase declared. **W8
converts one SDC into a DETECTED as well as three HANGs**, which is more
than it was built to do.

**And with both armed the combined build catches them too**, with both
counters nonzero over runs that reset themselves and re-arm:

| site | bit | cycle | `fi-w` armed | truth | escalated |
|---|---:|---:|---|---|---|
| `x23` | 24 | 14,073 | DETECTED | DEAD | W7 early, W8 budget |
| `x23` | 15 | 9,940 | DETECTED | DEAD | W7 early, W8 budget |
| `x23` | 29 | 9,670 | DETECTED | DEAD | W7 early, W8 budget |
| `x23` | 3 | 5,720 | DETECTED | WRONG | W7 early, W8 budget |

**[fact, `hw/soc/out/iso-w/directed.csv`]**

**Which is exactly why the isolation builds exist.** In the combined
build both mechanisms have fired by the end of a run that has reset
itself and restarted, and a report that read those two counters would
credit the window with a catch it did not make. `fi-w7` and `fi-w8`
answer the question the combined build cannot: **the window catches
none of the four and the budget catches four of four.**

**Three caveats, because this is a replay across a changed program.**
The `fi-w7`, `fi-w8` and `fi-w` builds all run the *windowed* workload —
one kick per round, `FI_WDOG_RELOAD = 383` — so the injected cycle lands
in a different place in a different program than it did in `docs/42`.
What survives that is exactly the thing under test: `x23` still holds
`FI_ROUNDS` in the windowed build (`li s7,4` at `c000038e` **[fact,
`hw/soc/out/fi-w/fi_workload.dis`]**), the corrupted bound still makes
the loop unbounded, and the machine is still DEAD with the backstop held
off. The `was(truth)` column is `docs/42`'s and the `truth` column is
this build's, and the two agree on all four records — which is the check
that the class was reproduced and not merely replayed.

Second, this is four injections and not a rate. It answers "is *this*
failure caught", which is the question `docs/42` section 8.1 posed, and
not "how often is this class produced".

Third, the register-file protection removes the class *before* the
watchdog ever sees it, which section 8 measures. These three builds hold
it off deliberately so that the watchdog's own contribution is
separable — a design where two mechanisms cover one failure is a design
whose measurement has to say which one did.

### 5.5 What W8 is not

It is not a general answer to "has this program made progress". It is a
counter of kicks against a number the software declared, and it is only
as good as that number. A phase whose kick count is data-dependent
cannot use it; a supervisor that runs for ever and kicks for ever cannot
use it at all without dividing itself into phases first. That is a real
limitation and it is the same shape as W7's: **both of these mechanisms
move work from the hardware to the software's own discipline**, and
`docs/42` section 10's third bullet — "the recovery policy is more
software than hardware" — is more true after this document than before
it.

---

## 6. The register file

### 6.1 This is not the duplication `docs/38` declined

A reader who has read `docs/38` section 10 item 4 will remember that one
of its stated reasons for declining `SecureIbex` was the register file:

> the one genuine overlap — ECC over the register file — duplicates a
> SECDED codec this project already owns and has golden-vector tested.

Building register-file protection here is not a reversal of that, and
the distinction is the one `docs/38` section 8.5 drew for itself:

- **The objection was to two codecs, and there is still one.**
  `hw/rtl/secded_enc.v` and `hw/rtl/secded_dec.v` are read in place —
  the same (72,64) Hsiao code `sw/golden/secded.py` models,
  `hw/tb/test_secded.py` cross-checks and `formal/secded.sby` proves.
  `sw/tests/test_soc_regfile_guards.py::test_the_codec_is_read_from_hw_rtl_and_not_copied`
  fails if a copy ever appears under `hw/soc/`.
- **Lockstep detects; this corrects.** A shadow core comparing outputs
  announces a divergence and leaves a recovery policy to be written.
  This repairs the value on the way out and scrubs it out of the
  storage, and the program never sees it.
- **And the price is now known on both sides.** `SecureIbex` is
  +309,550 um2 and +112 % for detection over the whole core; this is
  +37,983 um2 and +13.8 % for correction over 45 % of its flip-flops
  **[fact, section 7]**. That is **12.3 % of the cost** **[estimate,
  arithmetic on two measurements]**.

### 6.2 Why (72,64) and not a (39,32) of its own

The registers are 32 bits and the codec is fixed at 64 data bits; both
are given. Two ways to reconcile them:

| | check flip-flops | why not, or why |
|---|---:|---|
| **Pair two registers into one 64-bit codeword** | about 128 | The write path would need a decode as well as an encode, because writing one register of a pair means re-encoding over the other. Worse: two architectural registers would share a codeword, so an upset in `x8` and an upset in `x9` would be a **double** error — detected and not corrected — where here they are two independent single errors. It buys about 89 flip-flops **[estimate, arithmetic]** by making two registers share a fate |
| **One codeword per register, upper 32 data bits tied to zero** | 217 | Chosen |

**The tie-off is a constant the synthesiser folds, so what is built is
the (40,32) shortening of the same code.** The shortening is safe for
the reason the code is safe — all 72 columns of H are distinct, nonzero
and of odd weight, so any 40 of them are too — and a single error among
the 40 stored bits produces the syndrome of its own column and nothing
else. **No parameter of the codec is overridden**; both modules carry an
elaboration guard refusing any width but 72/64, and this file passes 64
and 8.

That argument is made in a comment, and a comment is not a check, so it
is also **proved**: `hw/soc/formal/regfile_secded.sby` states it over a
free data word and a free 40-bit error vector — one bit corrected, two
detected and never miscorrected — and the four tasks pass with 5 of 5
covers reached **[fact]**. Section 9.3.

### 6.3 The seven-bit surprise, which is arithmetic and not luck

**The shortened code costs seven check flip-flops per register, not
eight**, and the reason is that `H_ROW7` is `64'hF8FFFFF800000000`,
whose low 32 bits are zero. Over a 32-bit data field that check bit is
identically zero; the optimiser finds the constant and deletes one
flip-flop per register, 31 in all.

What is left is 39 columns in a 7-bit syndrome space, all distinct,
nonzero and odd-weight — which is **(39,32), the minimal SECDED width
for 32 data bits.** The (72,64) codec, shortened, lands exactly on the
code a purpose-built one would have been.

This is stated as a measurement in three places rather than as a happy
accident: `regfile_secded.sby` property **C4** proves
`check_out[7] == 0`;
`test_the_eighth_check_bit_does_not_exist_over_32_data_bits` re-derives
which rows of H are empty over the low 32 columns from
`hw/rtl/secded_enc.v` itself; and the netlist census in section 9.4
counts 217 and would fail at 248.

### 6.4 Correct on read, and scrub, and why both

Correction on read alone repairs the value the program sees and leaves
the corruption in the flip-flop. `docs/41` section 5.1 made the same
argument for the watchdog's protected word and it is stronger here: a
register written once and read for the rest of the run — a loop bound, a
base pointer, a callee-saved register held across a long call — keeps an
upset for as long as it holds its value, and **the second upset in that
word is uncorrectable.**

So a pointer walks `x1`..`x31`; on every cycle in which the core is not
writing the file, the register it points at is decoded, re-encoded from
the corrected value and written back, and the pointer advances. On
cycles when the core writes, the scrub stalls and the pointer **holds**
— it does not skip — and the register the core wrote was re-encoded by
that write in any case.

The scrub and the core share one encoder and one write port, which is
why it stalls rather than proceeding in parallel: a second write port
would need a 40-bit two-input multiplexer in front of all 31 registers
and would cost more than the protection.

**Its period is data-dependent and that is not proved to be bounded.**
It is 31 cycles when the core is idle and unbounded in the limit of a
program that writes the register file on every cycle for ever. No real
program does — Ibex cannot retire a writing instruction every cycle
indefinitely — but nothing in this repository proves that, and section
10 lists it.

**What the scrub buys, measured against the design without it** —
section 9.2 — is the difference between 0 and 6 injections left sitting
in the storage unseen, and between a second upset 36 cycles later being
corrected and being an uncorrectable double error.

### 6.5 The report has nowhere to go, and that is the price of section 3

The module counts what the codec did. **Nothing reads those counters.**
`ibex_register_file_ff` carries upstream's port list, upstream's port
list has no error output, and adding one is a patch to `ibex_top.sv` —
which is the thing the whole arrangement exists to avoid.

So **the correction is silent**: in silicon, a corrected upset is
indistinguishable from no upset at all. Two consequences, both stated
here rather than discovered later:

- `opt_clean` deletes the counters, because they drive nothing. **The
  report costs zero area**, and
  `test_the_report_costs_nothing_because_nothing_can_read_it` asserts
  that it does — a test whose *failure* would be the good news, because
  it would mean something now reads it.
- In simulation they are readable hierarchically, and
  `hw/soc/tb/tb_soc_fi.v` reads them the way it already reads words out
  of RAM. **That is a bench observation and not an operator channel**,
  and section 8 says so where it reports the CORRECTED column — a column
  that is populated by an instrument the silicon does not have.

Closing this is a port on `ibex_top` and therefore a patch to Ibex, or a
fault line reaching the SoC by some other route. Neither is built.
Section 12 ranks it.

### 6.6 What it does not protect

- **x0.** It has no flip-flops in this configuration and never did.
- **The addresses.** `raddr_a_i`, `raddr_b_i` and `waddr_a_i` come from
  the decoder and are unprotected there. A corrupted address reads or
  writes the wrong register with a perfectly valid codeword, and no code
  over the data can see it. `docs/42`'s `if_id` and `id_ctrl` strata are
  where those bits live and they are still measured at their
  unprotected rate.
- **Everything else in the core.** This is 45 % of its flip-flops and no
  more. The controller, the fetch FIFO and the load/store FSM are
  untouched, and `docs/42` section 6.3 shows they carry the highest
  per-bit rates in the design.
- **Two upsets in one register between two scrubs.** Detected rather
  than miscorrected — that is what the odd column weight buys — but
  reporting is all it can do, and there is nowhere for the report to go.

---

## 7. Measured area, and measured timing

### 7.1 The core, which is the number that matters

Same recipe as `docs/38` section 8.1 and `docs/41` section 6.5: Yosys on
`ihp-sg13g2` typical, `abc` at a 20 ns delay target with the same
driving cell and load, `stat -liberty`. Gate equivalent =
`sg13g2_nand2_1` = 7.2576 um2.

| Configuration | Cells | Flops | Area, um2 | kGE |
|---|---:|---:|---:|---:|
| `small-pmp`, upstream register file | 18,921 | 2,106 | **275,682.6198** | 37.985 |
| `small-pmp`, SECDED register file | 22,796 | 2,328 | **313,733.1960** | 43.228 |

**[fact, both measured in the same session with the same script]**

**Note added 2026-09-05.** 313,733.1960 um2 is the core with the SECDED
register file **as this document built it**. It is not the area of the
shipped core. `docs/44-margin-and-observability.md` section 7.1
re-measures this document's file byte-identically and then measures the
core as shipped — `FASTCORR = 1` with the fault-report port live — at
**22,338 cells, 2,328 flip-flops, 316,051.6590 um2**, +14.64 % over the
baseline **[fact, `docs/44` section 7.1]**; `docs/45` section 6.2 and
`docs/60` section 5 carry that figure. The 2,318.4630 um2 between the
two is content — the fast-correction read path and the report cone — and
not method **[estimate, the difference of two measurements]**, and
`docs/44` section 7.1 says which of its rows may be subtracted from
which. Quote 316,051.6590 for the core in the SoC; quote this table for
what the register-file protection alone cost.

> **The register-file protection costs +38,050.5762 um2 on the core,
> +13.80 %, and +222 flip-flops** **[estimate, the difference of two
> measurements]**.

**The baseline row reproduces `docs/38` section 8.4 exactly** — 18,921
cells, 2,106 flip-flops, 275,682.6198 um2, to four decimal places —
which is worth one sentence because it is the check that the flow has
not drifted underneath the comparison.

**Against the alternative that was declined.** `docs/38` section 8.5
measured `SecureIbex` at +309,550 um2 over `small-pmp`, +112 %, for
detection. This is **12.3 % of that** **[estimate, arithmetic on two
measurements]** and it corrects.

### 7.2 The register file on its own, four ways, and the baseline trap

`docs/41` section 6.5 records a measurement defect worth not repeating:
a hardening was nearly priced against the number a previous document had
measured, which would have credited it with a saving a refactor made in
the same commit. **The baseline has to be the same source, measured now,
with only the thing being priced turned off.** For a substituted file
there are two candidate baselines and they are not the same number.

`hw/soc/flow/syn_regfile.sh`, same recipe, all four in one run:

| Configuration | Cells | Flops | Area, um2 |
|---|---:|---:|---:|
| upstream's `ibex_register_file_ff` | 4,804 | 992 | 94,153.1094 |
| this file, `HARDEN = 0` | 5,797 | 992 | **93,469.9878** |
| this file, `HARDEN = 1, SCRUB = 0` | 7,113 | 1,209 | 115,216.0254 |
| this file, `HARDEN = 1` | 8,129 | 1,214 | **125,179.5384** |

**[fact]**

Four readings.

**The cost of the protection is +31,709.5506 um2**, `HARDEN = 1` against
`HARDEN = 0` — the same file, the same generate structure, the
protection switched off.

**Quoting it against upstream's file would say +31,026.4290 and would be
wrong by 683.1216 um2**, because this project's rewrite of a file it did
not write is **683.12 um2 cheaper** than upstream's at the same
behaviour. That difference is a rewrite, not a hardening, and crediting
the hardening with it would understate the hardening's cost. Same shape
as `docs/41` section 6.5, and again in the understating direction.

**The scrub is +9,963.5130 um2 of the +31,710**, 31 % of the
protection, for five flip-flops and a third decoder. That is the price
of section 6.4, separable because `SCRUB` is a parameter.

**And the module measured alone understates what it costs in place.**
The standalone delta is +31,709.55; the whole-core delta in section 7.1
is +38,050.58, **20 % larger** **[estimate, arithmetic]**. The
difference is `abc` re-optimising across a boundary that does not exist
in the flattened core, and buffering for a read path that is now
longer — section 7.4. **The core number is the design's cost; the module
number is what the module contains.** Neither supersedes the other and
this document quotes the first.

### 7.3 The watchdog: what W7 and W8 cost

`hw/soc/flow/syn_soc.sh soc_wdog`, the recipe `docs/40` and `docs/41`
measured with:

| Configuration | Cells | Flops | Area, um2 | % of Ibex |
|---|---:|---:|---:|---:|
| `HARDEN = 0, WINDOW = 0` | 398 | 53 | 5,760.4176 | 2.089 % |
| `HARDEN = 0, WINDOW = 1` | 633 | 68 | 9,201.6540 | 3.338 % |
| `HARDEN = 1, WINDOW = 0` | 710 | 102 | **10,791.6354** | 3.914 % |
| `HARDEN = 1, WINDOW = 1` — as built | 1,042 | 131 | **15,695.7318** | 5.693 % |
| `docs/41`'s shipped W6 build, at `acec4d8` | 715 | 102 | 10,818.8514 | 3.924 % |

**[fact for every measured row; the percentages are arithmetic on the
275,682.6198 um2 of section 7.1]**

> **W7 and W8 cost +4,904.0964 um2 on the watchdog, +45.4 %, and +1.78 %
> of the Ibex core** **[estimate, the difference of two measurements]**.

**The comparison is against the `WINDOW = 0` row of the same file and
not against `docs/41`'s 10,818.8514**, and the difference is small and
is the kind of thing this repository writes down: adding W7 and W8 made
the `WINDOW = 0` configuration **27.216 um2 and 5 cells cheaper** than
the version `docs/41` measured. Quoting the delta against the older
number would put the cost at 4,876.88 um2 — **understating it by 27.2**.
The direction is the small one again; the habit is not.

**Where the flip-flops go.** 102 → 131 is 21 more in the three replicas
(the protected word goes from 22 bits to 29) and 8 for `kick_left`,
which is deliberately outside the protected word. Section 4.5 item 3 is
what the 21 buy and section 9.2 is what leaving the 8 out costs,
measured.

### 7.4 Timing, which is the largest non-area cost in this document

The decoder sits on the register read path and the register read path
feeds the ALU, so this is the one place in the design where a correction
mechanism is **in series** with the thing it protects. Both the slack at
a fixed period and the maximum frequency are measured, on both
configurations, in the same session.

OpenSTA, all three sg13g2 corners, the pilot's 5 % derate, at the same
20 ns period **[fact]**:

| Configuration | worst setup | corner | worst hold | corner |
|---|---:|---|---:|---|
| `small-pmp`, upstream register file | **+2.4337 ns** | slow | −0.0766 ns | fast |
| `small-pmp`, SECDED register file | **+1.7411 ns** | slow | −0.0710 ns | fast |

> **The protection costs 0.6926 ns of setup slack at 20 ns** **[estimate,
> the difference of two measurements]** — 3.5 % of the period.

**Hold is unchanged in kind and slightly better in degree.** Both
configurations fail hold at the fast corner pre-layout, by 0.0766 ns and
0.0710 ns; `docs/38` section 10 item 3 already carries closing that as
an obligation on place-and-route, and `hw/soc/flow/sweep_ibex.sh`'s
header explains at length why hold is not in the frequency gate on a
synthesis netlist. **The hardened design is not being credited with
improving hold**: a 5.6 ps movement on a pre-layout number with no clock
tree is noise, and section 10 says so.

**And the frequency, bisected.** `docs/38` section 8.6's method —
bisection on the clock period, re-synthesising at every probe, so that
the number `abc` optimises for and the number STA checks are the same
number — run on both configurations here:

| Configuration | Closes setup at | Frequency | Binding corner |
|---|---:|---:|---|
| `small-pmp`, upstream register file | **15.98 ns** | **62.6 MHz** | slow (1.08 V, 125 C) |
| `small-pmp`, SECDED register file | **17.62 ns** | **56.8 MHz** | slow |

**[fact]**

> **The protection costs 1.64 ns of period and 5.8 MHz, −9.3 %**
> **[estimate, the difference of two measurements]**.

The baseline row reproduces `docs/38` section 8.6's 16.02 ns / 62.4 MHz
to within the bisection grid, which is the check that the method has not
drifted. And the shape of the cost is the opposite of lockstep's:
`docs/38` measured `SecureIbex` at **0.27 ns** against `small-pmp`,
because a shadow core runs in *parallel* with what it checks. This
decoder runs in *series* with it, and pays six times as much period for
a mechanism that costs an eighth of the area.

**As always, `docs/09` estimated 50–80 MHz for a 130 nm RV32 core and
56.8 MHz is still inside it**, and as always these are pre-layout
numbers with no parasitics and no clock tree, and on this project's
history they move down.

---

## 8. The campaign, re-run

### 8.1 Two campaigns, and why they are two

A delta is only a delta if the two runs were asked the same question, so
the hardening is measured in **two campaigns and not one**:

| | register file | watchdog contract | workload | what it isolates |
|---|---|---|---|---|
| **A** | SECDED | `WINS = 0`, budget disarmed — inert | **`docs/42`'s, byte for byte** | the register file, with the software held fixed |
| **AW** | SECDED | `WINS = 1`, budget `FI_ROUNDS + 2` | one kick per round | the contract, on top of A |

**Campaign A is a paired comparison and campaign AW is not**, and the
difference matters enough to be the first thing said about them.

`fi_workload.c` with `FI_WINDOWED` off compiles to a **byte-identical
ROM image** to `docs/42`'s **[fact, `md5sum` = `c48d8d73…`]**, its clean
run is the same 18,682 cycles with the same signature and the same
208..16,910 window **[fact]**, and the draw is seeded per (stratum,
index) — so campaign A's 1,300 shared-stratum injections are
**identical, draw for draw, to `docs/42`'s 1,300**: same site, same bit,
same cycle. That is checked and not assumed; section 14 gives the
twenty-line check and it prints `True` **[fact]**. Campaign A is
therefore the *same experiment on a changed design*, which is the only
arrangement in which "the number moved" means the design moved it.

Campaign AW runs a different program, by necessity — section 4.3 — so
its numbers are a measurement of the hardened SoC and **not** a
controlled comparison against `docs/42`. Both are reported; neither is
allowed to stand in for the other.

**1,400 injections per campaign, 14 strata of 100, each run twice —
2,800 simulations each, 5,600 in all, the two campaigns run concurrently
at eight processes each in 1 h 17 m of wall time on a 20-thread host**
**[fact, the interval between `tb_soc_fi.vvp` and `records.csv` in the
two build directories]**. The fourteenth
stratum is new: `regfile_ecc`, the 248 check bits and the five-bit scrub
pointer the protection adds, because 253 flip-flops an upset can land in
that a campaign does not visit are 253 flip-flops the campaign has not
finished looking at.

Every one of `docs/42` section 5.1's five controls passes on both
builds, and one of them changed meaning in a way worth recording:
**control 4a, the positive control, now classifies CORRECTED instead of
DETECTED.** Bit 20 of the stack pointer still cannot come back MASKED —
which is what the control asserts and why it is a gate — but the reason
it is not MASKED is now that the codec repaired it rather than that the
machine fell over. The control still does its job; what it demonstrates
has changed.

### 8.2 Campaign A: the register file

**With the watchdog held off — the core with no backstop at all**, the
two register-file strata against `docs/42`'s:

| stratum | n | MASKED | CORRECTED | SDC | DETECTED | HANG |
|---|---:|---:|---:|---:|---:|---:|
| `regfile`, `docs/42` | 100 | 78 | 0 | **3** | 15 | **4** |
| `regfile`, now | 100 | 6 | **94** | **0** | **0** | **0** |
| `regfile_ecc`, now | 100 | 4 | **96** | **0** | **0** | **0** |

**[fact, `hw/soc/out/fi-h1/campaign.log` against
`hw/soc/out/fi-core/campaign.log`]**

**Every injection into the architectural registers that produced a wrong
answer or a dead machine in `docs/42` now produces neither.** 190 of the
200 draws across the two strata are CORRECTED and **all 190 ended with
the golden answer**; the other 10 are MASKED, and MASKED here means what
section 9.2 measured on the module: the program overwrote the register
before anything read it. **Zero uncorrectable syndromes in 1,400
injections** **[fact]**.

**And the class `docs/42` section 8.1 named is gone at source.** All
four of its `x23` draws — bits 24, 15, 29 and 3, at their own cycles —
come back **CORRECTED with the golden answer, the codec having repaired
one bit** **[fact, `hw/soc/out/fi-h1/records.csv`]**. Three of them were
the three uncaught HANGs the whole of `docs/42` section 8.1 is about.
The watchdog is not involved: there is nothing left for it to catch.

**The design-weighted rates, which is what a hardening is bought
against:**

| | `docs/42` | campaign A |
|---|---|---|
| SDC, watchdog held off | 2.8 % ± 1.6 | **1.3 % ± 0.4** |
| HANG, watchdog held off | 2.1 % ± 1.8 | **0.3 % ± 0.2** |
| SDC, watchdog armed | 2.7 % ± 1.6 | **1.2 % ± 0.4** |
| HANG, watchdog armed | 1.4 % ± 1.5 | **0.0 % ± 0.0** |

**[fact, the stratified estimator of `docs/42` section 4.5]**

**The design-weighted silent-corruption rate is more than halved and the
hang rate falls by a factor of seven.** Two cautions on reading that
table, both of which cut against the number.

**The weights changed.** `docs/42` weighted 13 strata by their share of
2,198 injectable bits; this weights 14 by their share of 2,451, because
the design has 253 more flip-flops. The register file's share falls from
45.1 % to 40.5 % and the new stratum takes 10.3 % at a measured rate of
zero, so **part of the improvement in the weighted figure is the
denominator and not the numerator**. The per-stratum rows above are the
unweighted evidence and they are unambiguous; the weighted row is the
design-level figure and it is doing two things at once.

**And the intervals are not comparable to the old ones in the way they
look.** ±1.6 became ±0.4 because the variance of a stratified estimator
collapses when the largest stratum's rate goes to zero. That is a real
narrowing, but 0 of 100 is a rate below about 3.7 % and not a rate of
zero — `docs/42` section 4.5's reading of a zero row applies here
unchanged and applies to the most important row in the table.

**What did not move, and it is most of the core.** `fetch_fifo` 9 %,
`controller` 8 %, `id_ctrl` 8 %, `multdiv` 7 %, `if_id` 5 % — every SDC
rate outside the register file is within one draw of `docs/42`'s, which
is what should happen when nothing in those structures changed and is a
check that the campaign is measuring the design and not the weather.
`docs/42` section 6.3's other half stands untouched: **the controller
still has the highest per-bit rate in the core and nothing here goes
near it.**

### 8.3 Campaign A: the watchdog, on a core that hangs less

| | `docs/42` | campaign A |
|---|---|---|
| upsets that leave the core DEAD | 36 of 1,300 | **28 of 1,400** |
| of those, the watchdog escalated | 33 — **91.7 %** [78.2 – 97.1] | **28 — 100.0 %** [87.9 – 100] |
| of those, ended golden after the reset | 26 | **24** |
| spurious escalations, over survivable upsets | 0 of 1,106 | **0 of 1,228** |
| wrong answer with nothing announced | 118 of 1,300 | **110 of 1,400** |

**[fact]**

**The three uncaught dead runs are gone and the catch rate is 28 of
28**, which is the headline `docs/42` section 7.2 would have wanted —
and it is worth being exact about why, because it is not because the
watchdog got better. **The watchdog is unchanged in this campaign**:
`WINS = 0` and the budget disarmed make it the block `docs/42` measured,
and `soc_wdog_props.v` W7b proves that. The three records it could not
catch were removed from the population by the register file. **The
denominator changed, not the mechanism.**

The one number that did not improve is the one no watchdog reaches:
**110 injections still produce a wrong answer and announce nothing**,
against `docs/42`'s 118. Those are the fetch path, the decoder, the
control FSM and the multiplier, and the register-file protection was
never going to touch them.

### 8.4 Campaign AW: what the cadence contract cost and what it caught

This is the negative result, and it is the one worth reading twice.

| | value |
|---|---|
| injections on which **W7** rejected a kick as too early | **11 of 1,400** |
| of those, on machines that were **DEAD** without a backstop | **0** |
| of those, on machines that were **OK** without a backstop | **7** |
| **spurious escalations** — a healthy outcome escalated anyway | **7 of 1,232** |
| highest stage any of the 11 reached | **stage 1**, all eleven |
| injections on which **W8** ran a phase out of kicks | **0** |
| upsets that leave the core DEAD, and the catch rate | 30 of 30, 100 % |

**[fact, `hw/soc/out/fi-h2/campaign.log` and `records.csv`]**

**W7 caught nothing that the block would not have caught anyway, and it
produced seven escalations on machines that were fine.** Every one of
the 30 dead machines was caught by an ordinary expiry; not one was
caught by the window. That is the same answer section 5.4 got by
replaying `docs/42`'s own records, arrived at independently over 1,400
draws.

**`docs/41`'s zero-spurious headline is therefore gone, and this is
where it went.** Seven of 1,232 survivable upsets escalated —
0.6 % [0.3 – 1.2] — and all seven are corruptions of the *core*, five of
them in `ctrl_fsm_cs`, that perturbed the program's timing enough to
push a kick over the line and then let it finish correctly anyway.

Two things soften that and neither removes it. **All seven stopped at
stage 1**: an NMI the handler acknowledged, not a reset, so the
measured cost is a spurious interrupt and not a spurious reboot — and
all seven still produced the golden answer. And a stage-1 NMI on a
machine that had in fact been hit is arguably the window doing something
useful: it is the only mechanism in this design that *announced* a
survivable upset, which section 10 says nothing else can do. But a
watchdog is not telemetry, an escalation ladder ends in a reset, and
counting this as a benefit would be reading the result backwards.

**W8 fired zero times, and that is the register file's doing.** The only
failure class in this campaign that would exhaust a kick budget is the
corrupted loop bound, and the register file corrects it before the loop
is ever wrong. Section 5.4's isolation builds are what say W8 works,
because they are the only place in this document where it has anything
to do.

### 8.5 What the two campaigns say together

**The register file delivered and the window did not**, on this
workload, against these numbers:

| mechanism | what it was built to move | did it |
|---|---|---|
| SECDED register file | the 3.2 of 4.9 design-weighted points `docs/42` section 6.3 attributes to the register file | **Yes.** 0 SDC and 0 HANG in 200 draws where `docs/42` had 3 and 4; design-weighted SDC 2.8 % → 1.3 % |
| W7, the window | the `x23` class of `docs/42` section 8.1 | **No.** 0 of 30 dead machines caught, 7 spurious escalations, and 0 of 4 on the `x23` records replayed verbatim |
| W8, the kick budget | the same class, after W7 was found not to reach it | **Yes, where it can be seen.** 4 of 4 on the replayed records; 0 of 1,400 in campaign AW, because the register file gets there first |

**W7 is built, proved, measured, and its measured value on this workload
is zero.** It ships at `WINS = 0` — off — and a stage-2 reset restores
it there. The document is not going to argue it into being worth 4,904
um2: it is worth that if a future workload produces the failure it
catches, which is a **fast** runaway rather than a long one, and this
one does not. The honest summary is that **`docs/42` recommended it,
this document built it, and the measurement says the recommendation was
aimed at the wrong failure** — and the useful part of building it was
finding that out and finding W8.

---

## 9. Verification

### 9.1 The regression: the hardening changed nothing it should not have

The strongest evidence that both changes are transparent to the design's
behaviour is that every measurement `docs/40` and `docs/41` recorded
reproduces **exactly**:

| | `docs/40` and `docs/41` | now |
|---|---|---|
| whole-SoC run, checks | 22, fail mask 0 | 22, fail mask 0 |
| watchdog stage 1 | cycle 174,128 | cycle 174,128 |
| core asleep after | 185,443 cycles | 185,443 cycles |
| console | 587 characters, 0 framing errors | 587 characters, 0 framing errors |
| escalation demo | stage1 2, stage2 2, stage3 1, 37,405 cycles | stage1 2, stage2 2, stage3 1, 37,405 cycles |
| `WDOGSTAT` after the demo | `0x…206`, rstcnt 2 | `0x…206`, rstcnt 2 |
| `docs/42`'s workload, ROM image | `c48d8d732610b323a7243a88408df00a` | identical |
| `docs/42`'s clean fault-injection run | 18,682 cycles, sig `9c07ef12`, window 208..16910 | identical |

**[fact]**. Not one cycle moved, and the campaign's stimulus is the same
bytes. That is what makes section 8's comparison a controlled one rather
than two campaigns that happen to be about the same design.

### 9.2 cocotb

| Suite | Tests | Result |
|---|---:|---|
| `test_soc_bus` | 13 | 13 pass |
| `test_soc_apb_bridge` | 11 | 11 pass |
| `test_soc_clint` | 12 | 12 pass |
| `test_soc_gptimer` | 10 | 10 pass |
| `test_soc_wdog` | 14 | 14 pass |
| `test_soc_wdog_fi` | 3 | 3 pass, **220** injections inside |
| **`test_soc_wdog_win`** | **13** | **13 pass** |
| **`test_ibex_regfile_secded`** | **6** | **6 pass**, 124 injections inside |

**[fact]**. The 60 tests of `docs/40` and `docs/41` are unchanged and
were re-run; they are written over W1–W6 as a specification, so they are
a genuine regression on the policy and not a description of the new
implementation.

`sw/tests`, the whole tree: **295 collected, 295 passed** **[fact]**,
including the 13 new register-file guards. `docs/41` closed at 279.

**The watchdog's own campaign scaled with the protected word.** W6's
word went from 22 bits to 29, so `test_soc_wdog_fi` now draws 220
injections instead of 162, and **168 of 168 into the protected word came
back CORRECTED** — 0 SDC, 0 HANG, 0 disarmed **[fact]**. The seven new
W7/W8 bits are masked exactly as the other 22 are.

**And the price of leaving `kick_left` unprotected is measured rather
than argued**, as `docs/41` section 7 measures `counter`, `reload` and
`pre`. Eight single-bit upsets into the armed budget counter: seven
raised it and one lowered it; **every one still escalated, at exactly
the value the corrupted counter held**, and the worst upward excursion
bought 247 further kicks before the budget bit anyway **[fact]**. That
is the bound the decision rests on, and it is now a number.

**The register file's own campaign, and its counterfactual.** 124
injections drawn uniformly over the 40 stored bits of each of the 31
registers, against a golden model that is a Python dictionary and not
the design:

| build | CORRECTED | MASKED | of which unexplained | SDC | DETECTED |
|---|---:|---:|---:|---:|---:|
| `SCRUB = 1` — as built | **107** | 17 | **0** | **0** | **0** |
| `SCRUB = 0` — the counterfactual | 99 | 25 | **6** | 0 | 0 |

**[fact]**

**MASKED here is a real class and getting the criterion right took two
goes.** The first version demanded CORRECTED of every injection, on the
model of `docs/41` section 8.2's 126 of 126. It failed at 104 of 124,
and **the design was right and the criterion was wrong**: the watchdog's
protected word is rewritten from the voted value on *every clock*, so an
upset in it is seen within one cycle; a register file is not like that,
and a register the program overwrites before the scrub reaches it has
shed the upset without the codec ever seeing it. The criterion is now
that nothing is SDC or DETECTED **and every MASKED record is explained**
— the workload wrote that register after the injection — because an
unexplained MASKED record is the signature of a deposit that did not
land, which is the failure mode the controls exist to catch.

**The counterfactual is the measurement.** Without the scrub, six
injections end the run as upsets still sitting in the storage that
nothing has seen; with it, none do. And two upsets in one register 36
cycles apart are **corrected with the scrub and an uncorrectable double
error without it** **[fact]** — which is the whole argument of section
6.4, produced on demand.

**One honesty note about where these expectations come from.** `docs/40`
could say that W1-W5 were written down before the RTL that implements
them. **W7 and W8 were not**: the requirement and the implementation
were written in the same change, and claiming otherwise would be a
pretence. What is done instead is to keep the expectations at one remove
from the design wherever that is possible — every number in
`test_soc_wdog_win.py` is computed from the requirement's arithmetic and
not copied from an expression, and
`test_the_window_boundary_is_where_the_requirement_says` asserts no
formula at all: it sweeps the tick at which the kick lands, finds the
first one the block accepts, and compares that with the arithmetic. A
shift the wrong way round, off by one, or taken against the counter
instead of the reload would all still be a watchdog, and all three would
fail there. The register file is in a stronger position: what it has to
do is the RISC-V architecture, and its golden model is a Python
dictionary.

### 9.3 Formal

| Job | Tasks | Result |
|---|---|---|
| `soc_bus` | bmc, prove, cover | all PASS |
| `soc_apb_bridge` | bmc, prove, cover | all PASS |
| `soc_clint` | bmc, prove, cover | all PASS |
| `soc_wdog` | bmc, prove, **prove_w0**, cover | all PASS |
| `soc_wdog_tmr` | 8 tasks | all PASS |
| **`regfile_secded`** | bmc, prove, prove_abc, cover | **all PASS** |

**6 jobs, 25 tasks, 54 of 54 cover obligations reached, 0 unreached**
**[fact]**. `docs/41` closed at 5 jobs, 20 tasks and 41 covers.

**`regfile_secded.sby` is the new one and it proves the shortening.**
`formal/secded.sby` proves the codec at its own width and is untouched
by this work; what was not proved anywhere is that tying the upper 32
data bits to zero leaves a code that still corrects one error and
detects two over the 40 bits that remain. Over a free data word and a
free 40-bit error vector: **C1** no error, no flag, data unchanged;
**C2** one bit corrected and flagged; **C3** two bits reported
uncorrectable and **never** miscorrected; **C4** the eighth check bit is
identically zero — the fact section 6.3 and the netlist census depend
on. Two engine families, `smtbmc yices` and `abc pdr`, which is
`docs/09` C.4 item 7's engine diversity expressed as a task.

**`soc_wdog.sby` gains W7, W8 and a `prove_w0` task.** The load-bearing
property is **W7b**: at `WINS = 0` with the budget disarmed neither
mechanism can fire, so a program that never writes `WDOGWIN` gets the
block `docs/42` measured. `prove_w0` proves every property again at
`WINDOW = 0` — the configuration in which W7 and W8 do not exist — and
there is deliberately no cover task there, because the new covers are
unreachable by construction in it. Cover obligations went from 9 to 17
and all 17 are reached.

### 9.4 The netlist census

`sw/tests/test_soc_regfile_guards.py`. Every functional test above would
pass on a netlist with the check flip-flops optimised away, and the risk
is not theoretical: `chk_q` is, in a fault-free design, a pure function
of `data_q`, and the scrub's write-back is `encode(decode(stored))`,
which **is** the identity on a clean codeword.

| Configuration | flip-flops in the mapped netlist |
|---|---:|
| `HARDEN = 1`, ASIC recipe | **1,214** = 992 data + 217 check + 5 scrub pointer |
| `HARDEN = 1`, `synth_ecp5` | **1,214** |
| `SCRUB = 0` | 1,209 |
| `HARDEN = 0` | **992** |
| upstream's own file | **992** |

**[fact]**

The `HARDEN = 0` and upstream rows are the mutations: a count that were
being met by something other than the protection would not move when the
protection is removed. Two technology mappers, because one mapper's
behaviour is the tool and not the design — the move
`sw/tests/test_soc_synthesis_guards.py` already makes for the watchdog's
replicas.

**And the RTL census still covers the whole core.**
`hw/soc/flow/fi_coverage.sh`, re-run against the hardened elaboration:

```
flip-flop signals elaborated : 145
  named by a campaign site   : 145
  not named                  : 0

flip-flop BITS elaborated    : 2431
  covered by the campaign    : 2431  (100.0 %)
  not covered                : 0
```

**[fact, `hw/soc/out/fi-h1/fi_coverage.txt`]**. The site table lists
2,451 bits; 2,451 minus the 19 bits of the three IF-stage signals
`opt_clean` deletes and one bit of `mcountinhibit` is 2,431, which
closes the same arithmetic `docs/42` section 4.2 closes at 2,178.

**Note the two different check-bit counts and do not reconcile them.**
The RTL census sees 248 check flip-flops because the eighth bit's
flip-flop exists in the elaborated RTL; the mapped netlist has 217
because its D input is a constant. Both are true at their own stage, the
campaign injects into all 248, and 31 of those injections are into
storage the netlist does not contain — the same class of bias
`docs/42` section 4.4 item 1 records for the three IF-stage signals, in
the same direction, and it can only inflate the masked fraction. *Measured 2026-09-06 by `docs/74-core-gate-level-campaign.md`: the
31 eighth-bit check flip-flops are absent from the sign-off netlist by
name, by alias and by trace, the other 217 are present under their own
names, and every `regfile_ecc` record of section 8 whose bit exists in
silicon was replayed there. The cycle each record names is the edge or
the one after it, `docs/74` section 5.2a.*

### 9.5 A latent defect in an existing guard, found by the width changing

`test_removing_the_mix_transform_from_one_replica_collapses_half_of_it`
asserted that turning MIX off on both mixed replicas loses `2 × collided`
flip-flops, where `collided` is the number of bits on which `POL_C` is
zero. At `PROT_W = 22` that is 2 × 11 = 22 and it was right. At
`PROT_W = 29` it is 2 × 15 = 30, and the answer is 29.

**The design was right and the arithmetic was wrong, and the comment
above it had said the right thing all along**: on *every* bit one of the
three replicas has to collide, because polarity offers exactly two
storage functions per bit and there are three replicas. The expression
is now `intact − PROT_W`, which is what the comment says. It could only
ever have been caught by the width changing, and it is recorded here
because `docs/41` section 6.6's list is about checks that are narrower
than they read.

### 9.6 Three defects in this project's harness, none in Ibex

Recorded because each is a way a campaign can report a confident number
while measuring nothing, and because `docs/42` section 8.5 and `docs/38`
section 7.5 made the same list for the same reason.

1. **The directed replay keyed on the site NAME, and site names are not
   unique.** `rdata_q` is the fetch FIFO's 96-bit instruction queue in
   one stratum and the load/store unit's 24-bit data register in
   another. A name lookup silently replayed one into the other, and bit
   87 of a 24-bit register XORs a mask entirely outside it: the
   testbench reports `hit = 1`, the value does not change, and the run
   comes back MASKED. **Two of `docs/42`'s DEAD records were replayed
   that way and looked exactly like a hardening that had fixed them.**
   Caught by reading a record that said the deposit changed nothing and
   asking why — the move `docs/41` section 8.4 records — and the mode
   now keys on the path, which is unique, and verifies the deposit
   exactly as the campaign does.
2. **A cocotb file relied on a clock an earlier test had started.**
   `start_soon` coroutines are killed when a test ends, so
   `test_the_window_boundary_is_where_the_requirement_says`, which does
   not call `setup()`, ran with no clock at all — a hang rather than a
   failure, which took the seven tests after it down with it and
   reported them as failures with 0 ns of simulation time. Every test in
   the file now starts its own clock and loops inside a test use `por()`.
   `test_soc_wdog.py`'s `por()` docstring records the other half of the
   same hazard, from `docs/40`.
3. **An acceptance criterion that could only be met by a slower
   workload.** Section 9.2. The register file's campaign demanded
   CORRECTED of every injection, on the model of `docs/41` section
   8.2's 126 of 126, and failed at 104 of 124 on a design that was
   right.

And one **latent** defect in an existing guard, section 9.5, which no
change to this repository except a width change could have exposed.

---

## 10. What this does NOT cover

Stated at length, because this repository has been bitten by a green
check read as wider than the thing it examined ten times — `docs/28`
4.4a, `docs/34` 8.5, `docs/36` 3.3, `docs/38` 7.3 and 8.2, `docs/39` 3,
twice in `docs/40`, `docs/41` 8.4 and `docs/42` 5.1 — and sections 9.5
and 9.6 above add three more.

**Even every green check in section 9 would not license "the core is
adequately protected."** The reasons, worst first.

- **The correction is invisible outside a simulator.** Section 6.5. The
  CORRECTED column of section 8 is populated by a hierarchical read of a
  counter that `opt_clean` deletes. In silicon a corrected upset and no
  upset are the same event, so **this design cannot tell an operator
  that it is being hit**, and a mission that wanted to know its upset
  rate could not learn it from this part. That is the single largest
  gap this document opens.
- **The oracle is still the run's output, not the machine's
  architectural state.** `docs/42` section 9's first bullet is unchanged
  and is still the largest reason the SDC rate is a lower bound.
- **One workload, one seed, one parameter point** — and now two
  workloads, which is worse in one specific way: the windowed campaign
  runs a *different program*, so its numbers are not a controlled
  comparison against `docs/42`'s in the way the unwindowed campaign's
  are. Section 8 keeps them apart and labels which is which.
- **RTL, single-bit, flip-flop only.** No gate-level netlist, no
  back-annotated timing, no multi-bit strike, no single-event transient
  in combinational logic — and the SECDED decoder is a large piece of
  new combinational logic on a critical path, so this design has more
  exposure to a transient than the one it replaces, and nothing here
  measures it.
- **The scrub's period is not bounded by anything but a workload
  measurement.** Section 6.4.
- **The register file's addresses are unprotected**, so a corrupted
  `waddr` writes a valid codeword into the wrong register and this
  design cannot see it.
- **W7 and W8 move work to software and the software has no test here.**
  The windowed workload is one program with one kick discipline. Whether
  `docs/09`'s S2 supervisor can be written to a jitter ratio below 2 is
  unknown and is a design constraint on it that did not exist before.
- **The window's false-positive rate is measured on one program at one
  margin.** Section 4.4 measures where the *clean* program starts
  tripping and section 8.4 measures seven spurious escalations under
  injection. Neither is a rate for a different program, and a program
  with a wider kick jitter would produce more of both. **This is the
  first mechanism in the SoC whose measured cost includes escalations on
  a healthy part**, and `docs/41` section 8.2's zero is the number it
  spends.
- **`soc_top.v` has still never been synthesised as one design**, and no
  SoC block has been through place and route, timing closure or
  gate-level simulation.
- **Two upsets are not covered** in the register file except that they
  are detected, and there is nowhere for the detection to go.

---

## 11. Corrections to earlier documents

- **`docs/42` section 10, first bullet, and section 8.1's last
  paragraph.** "A windowed watchdog … would have caught all three" is
  **wrong**, and section 5.1 above says why: a window fires on a kick
  that is too early, and the `x23` machine kicks on time. The mechanism
  that addresses that class is W8's kick budget, and the mechanism that
  removes it at source is the register-file protection. `docs/42`'s
  *measurement* is untouched; its inference from it is corrected here.
- **`docs/42` section 5**, "CORRECTED is structurally unreachable in
  this design", is true of `small-pmp` with upstream's register file and
  is no longer true of the design this document builds. The column is
  now populated, by an instrument that is a simulation and not a pin.
- **`docs/41` section 6.5's area table** row for `soc_wdog` at
  `HARDEN = 1` (715 cells, 10,818.8514 um2) is **no longer
  reproducible**, and that is not a correction of it: it was right for
  the file as it stood at `acec4d8`, and the file has changed. The same
  configuration of the file as it stands now measures 710 cells and
  10,791.6354 um2, and section 7.3 uses that number and not the older
  one as the baseline for W7 and W8.
- **`docs/41` section 10 item 4**, "no windowed watchdog mode, no
  independent clock, no boot flow, no pad ring", is now true of three of
  its four. Items 1, 2, 3, 5 and 7 stand unchanged; item 6, the core's
  own campaign, was closed by `docs/42`.
- **`docs/38` section 4.2's zero-patch claim** stands as written and
  section 3 above states what it does and does not cover now.

---

## 12. What the next block should be

1. **A fault line for the register file's correction counter**, and for
   `TMRERR`, which `docs/41` section 10 item 3 already left open. This
   is now the top of the list rather than the third item on it: this
   document has put a correction mechanism into the core that no
   operator can observe, and an unobservable correction is
   indistinguishable from an absent one at any distance greater than a
   simulator. It costs a port on `ibex_top` — a patch to Ibex, which
   section 3 explains the price of — or a route out of the core that
   does not exist yet.
2. **`mtime`**, which `docs/41` section 7.4 ranked above everything it
   left unprotected and which is still unprotected.
3. **A gate-level campaign on the core.** `docs/42` section 4.4 names it
   and this document makes it more valuable, not less: the SECDED
   decoder is a large combinational cone on the read path, the netlist
   has 31 fewer check flip-flops than the RTL, and neither difference is
   visible to an RTL campaign.
4. **The S2 supervisor's kick discipline as a design input.** Section 4
   makes the jitter ratio of the software's kick cadence a hardware
   constraint. `docs/09`'s S2 supervisor does not exist yet and it now
   has one more requirement to be designed against rather than
   discovered by.
5. **A decision about W7, made from a second workload rather than from
   this one.** Section 8.4 measured its value on this program at zero
   and its cost at seven spurious escalations and 4,904 um2. That is one
   program. Before floorplanning, either a workload that produces a fast
   runaway justifies keeping it, or it should be removed — and removing
   it is a `WINDOW = 0` instantiation and a deletion, both of which this
   file already supports and both of which are proved (`prove_w0`). **A
   mechanism that ships disabled and has never caught anything is a
   liability in an area budget**, and this document is not going to
   pretend otherwise by leaving the question open indefinitely.

---

## 13. Files touched

`docs/34` section 2 pins the pilot by git blob hash of the files in
`hw/rtl/` and section 5 lists the flow configs. **Nothing in either set
is modified** **[fact]**.

| File | Change |
|---|---|
| `hw/soc/rtl/ibex_regfile_secded.v` | new |
| `hw/soc/rtl/soc_wdog.v` | W7, W8, the `WINDOW` and `KICK_W` parameters, the protected word from 22 bits to 29 |
| `hw/soc/rtl/soc_gptimer.v` | a fifth watchdog register select |
| `hw/soc/flow/ibex_sources.sh` | new — the substitution |
| `hw/soc/flow/syn_regfile.sh` | new — the four-way area measurement |
| `hw/soc/flow/sim_soc.sh`, `fi_core.sh`, `fi_coverage.sh`, `syn_ibex.sh` | read the source list from `ibex_sources.sh` |
| `hw/soc/syn/ibex_syn.ys.in` | `@GEN@/*.v` becomes `@IBEX_SRCS@` |
| `hw/soc/formal/regfile_secded_props.v`, `regfile_secded.sby` | new |
| `hw/soc/formal/soc_wdog_props.v`, `soc_wdog.sby` | W7, W8, `prove_w0` |
| `hw/soc/formal/Makefile` | the `regfile` target, `prove_w0` in `wdog` |
| `hw/soc/tb/tb_soc_fi.v` | the kick cadence, the watchdog's programmed timeout, the register file's counters |
| `hw/soc/tb/sw/fi_workload.c` | the `FI_WINDOWED` build; **byte-identical output with it off** |
| `hw/soc/tb/sw/soc_timers.h` | `WDOGWIN` and its fields |
| `hw/soc/fi/targets.py` | the `regfile_ecc` stratum |
| `hw/soc/fi/campaign.py` | CORRECTED reachable, the escalation ladder measured off the golden run rather than written down, `--directed` |
| `hw/soc/tb/cocotb/test_ibex_regfile_secded.py`, `Makefile.ibex_regfile_secded` | new |
| `hw/soc/tb/cocotb/test_soc_wdog_win.py`, `Makefile.soc_wdog_win` | new |
| `hw/soc/tb/cocotb/test_soc_wdog_fi.py` | the wider protected word, and `kick_left` as a target |
| `sw/tests/test_soc_regfile_guards.py` | new, 13 tests |
| `sw/tests/test_soc_synthesis_guards.py` | the geometry, and section 9.5's fix |
| `.gitignore` | two lines, the new sby working directories |
| `docs/43-core-hardening.md` | this document |
| `docs/00-index.md` | one row, which `sw/tests/test_doc_links.py` requires |

**`hw/rtl/secded_enc.v`, `hw/rtl/secded_dec.v` and `hw/rtl/tmr_voter.v`
are read and not modified.** The register file instantiates the first
two in place, so the SoC's codec is the one `formal/secded.sby` proves
and `hw/tb/test_secded.py` checks against `sw/golden/secded.py`, rather
than a copy that can drift —
`test_the_codec_is_read_from_hw_rtl_and_not_copied` asserts that no copy
has appeared.

---

## 14. Reproducing this

```
make -f hw/soc/tools.soc.mk fetch-ibex fetch-sv2v fetch-rvgcc
hw/soc/flow/sv2v_ibex.sh hw/soc/ext/ibex hw/soc/gen \
                         hw/soc/tools/sv2v-Linux/sv2v

# behaviour is unchanged
hw/soc/flow/sim_soc.sh                       # 22 checks, 185,443 cycles
SW_DEFINES=-DWDOG_RESET_DEMO \
  hw/soc/flow/sim_soc.sh hw/soc/out/sim-soc-wdog

cd hw/soc/tb/cocotb
make -f Makefile.soc_bus
make -f Makefile.soc_apb_bridge
make -f Makefile.soc_clint
make -f Makefile.soc_gptimer
make -f Makefile.soc_wdog
make -f Makefile.soc_wdog_win                # W7 and W8
make -f Makefile.soc_wdog_fi                 # 220 injections
make -f Makefile.ibex_regfile_secded         # 124 injections
REGFILE_SCRUB=0 make -f Makefile.ibex_regfile_secded \
  EXTRA_COMPILE_ARGS=-Pibex_register_file_ff.SCRUB=0 \
  SIM_BUILD=sim_build_regfile_s0 \
  COCOTB_RESULTS_FILE=results_regfile_s0.xml # the scrub counterfactual

cd hw/soc/formal && make                     # six jobs, twenty-five tasks

.venv/bin/python -m pytest sw/tests          # 295

# area and timing
IBEX_REGFILE=upstream hw/soc/flow/syn_ibex.sh small-pmp 20 hw/soc/out/h43-base
IBEX_REGFILE=secded   hw/soc/flow/syn_ibex.sh small-pmp 20 hw/soc/out/h43-secded
IBEX_REGFILE=upstream hw/soc/flow/sta_ibex.sh small-pmp 20 hw/soc/out/h43-base
IBEX_REGFILE=secded   hw/soc/flow/sta_ibex.sh small-pmp 20 hw/soc/out/h43-secded
IBEX_REGFILE=upstream hw/soc/flow/sweep_ibex.sh small-pmp 14 20 7   # 62.6 MHz
IBEX_REGFILE=secded   hw/soc/flow/sweep_ibex.sh small-pmp 15 22 7   # 56.8 MHz
hw/soc/flow/syn_regfile.sh                   # the four-way comparison
hw/soc/flow/syn_soc.sh soc_wdog              # 1,042 cells, 131 flops

# the campaigns
hw/soc/flow/fi_core.sh     hw/soc/out/fi-h1  # hardened, docs/42's workload
hw/soc/flow/fi_coverage.sh hw/soc/out/fi-h1
FI_REGFILE=secded hw/soc/fi/campaign.py --build hw/soc/out/fi-h1 \
                  --draws 100 --jobs 9

SW_DEFINES="-DFI_WINDOWED -DFI_WDOG_RELOAD=383u -DFI_WIN_S=1u" \
  hw/soc/flow/fi_core.sh hw/soc/out/fi-h2    # hardened + the contract
FI_REGFILE=secded hw/soc/fi/campaign.py --build hw/soc/out/fi-h2 \
                  --draws 100 --jobs 9

# The three isolation builds of section 5.4. All three hold the
# register-file protection OFF, so the watchdog has to catch the x23
# class on its own and the two mechanisms are separable.
W="-DFI_WINDOWED -DFI_WDOG_RELOAD=383u"
IBEX_REGFILE=upstream SW_DEFINES="$W -DFI_WIN_S=1u -DFI_KICK_BUDGET=255u" \
  hw/soc/flow/fi_core.sh hw/soc/out/fi-w7      # the window alone
IBEX_REGFILE=upstream SW_DEFINES="$W -DFI_WIN_S=0u" \
  hw/soc/flow/fi_core.sh hw/soc/out/fi-w8      # the budget alone
IBEX_REGFILE=upstream SW_DEFINES="$W -DFI_WIN_S=1u" \
  hw/soc/flow/fi_core.sh hw/soc/out/fi-w       # both

# docs/42's four x23 records, replayed VERBATIM against each of them
grep -E '^stratum|^regfile,x23,' hw/soc/out/fi-core/records.csv > x23.csv
for b in w7 w8 w; do
  FI_REGFILE=upstream hw/soc/fi/campaign.py --build hw/soc/out/fi-$b \
    --directed x23.csv --out hw/soc/out/iso-$b
done
```

**And the control that makes section 8 a paired comparison**, which is
that campaign A draws the same 1,300 injections `docs/42` drew. The
draw is seeded per (stratum, index) so the site and the bit are stable
by construction; the cycle is drawn inside the *measured* window, so it
is stable only because the window did not move. Both are checked rather
than assumed:

```
FI_REGFILE=secded python3 - <<'EOF'
import csv, sys
sys.path.insert(0, "hw/soc/fi")
import campaign, targets
win = (208, 16910)                     # the measured window of both runs
plan = [(st, s.path, b, c)
        for st in targets.STRATA
        for _, s, b, c in campaign.draws(st, 100, win)
        if st != "regfile_ecc"]
old = [(r["stratum"], r["path"], int(r["bit"]), int(r["cycle"]))
       for r in csv.DictReader(open("hw/soc/out/fi-core/records.csv"))]
print("identical draw for draw:", plan == old)
EOF
```

prints `True` **[fact]**.

`hw/soc/out/` is gitignored, by the rule `docs/38` section 11 already
applies: fetched or generated, never vendored. `--replay records.csv`
re-prints a whole report without re-simulating anything.
