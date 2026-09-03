# 57 — Power, measured under a duty cycle: the part idles at 5.5 mW and the clock gate nobody knew about is why

`docs/53-workload-and-the-clock.md` section 15 item 1 ranked one
measurement above everything else in this repository:

> **`report_power` with the whole-SoC run's own switching activity**,
> against the `full3` netlist, so that section 7.1's estimate becomes a
> measurement and the duty-cycle question of section 7.3 can be asked
> with a number behind it. … **This is the smallest piece of work in the
> record that closes the largest requirement gap in it.**

**This is that measurement. It closes the gap by a factor of 6.3, and
it finds two things nobody was looking for.**

The first is that **this design has a clock gate.** One
`sg13g2_lgcp_1` — `u_ibex.core_clock_gate_i.u_icg` — sits in the signed
off netlist covering **2,464 of its 3,085 flip-flops**, and `u_ibex.clk`
toggles **1.9995 times per cycle when the core is running and 0.0004
when it is in WFI** **[fact]**. Six documents state that this design has
"one clock, one mode, no scan, no test, no power number", and the second
clause of that sentence has been wrong since `docs/38` put Ibex in the
design.

The second is that **the layout the power number comes from does not
contain the NPU.** `hw/soc/pnr/runs/full3` was hardened from a netlist
`hw/soc/flow/syn_soc_top.sh` produced before `docs/51` put `u_npu`
inside `soc_top.v`, and that script's source list still has no
`soc_npu.v` in it **[fact]**. `docs/51` section 11's last line says so —
*"docs/47's sign-off does not include this block"* — and `docs/53`
section 7.2 nonetheless derived **an energy per inference from a netlist
that cannot perform an inference.** Section 9 prices what is missing:
**+50.7 % of the cells and +69.8 % of the flip-flops** **[fact]**.

**The headline, at the typical corner and 20 ns:**

| | |
|---|---:|
| `docs/47`'s sign-off figure, no activity annotation | **34.835 mW** |
| **computing**, measured activity, core clock running | **33.890 mW** |
| **waiting**, measured activity, core clock gated in WFI | **5.539 mW** |
| the same program over its own 42/58 duty cycle | **17.876 mW** |
| the same program with the idle removed — one `wfi` | **33.724 mW** |

**[fact for every row]**

**So the no-VCD estimate was right to 2.8 % for the busy case and wrong
by 6.29x for the idle one**, and the reason is not switching activity:
section 6 measures that reducing every register's toggle rate to zero
while the clock keeps running leaves a floor of **30.5 mW at typ**, and
that over the whole range the two measured workloads actually occupy the
figure moves by **1.22 mW, 3.6 %**. **This design's power is
clock-driven, and the only thing that removes it is stopping the
clock.**

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[assumption]**
= chosen, with the effect of choosing differently stated where it is
chosen; **[planned]** = intended, with nothing behind it yet.

**The pilot is untouched and so is every frozen directory.**
`docs/34-pilot-freeze.md` pins the TTIHP26b submission by blob hash and
the shuttle closes 2026-09-21. **Nothing in `hw/rtl/`, `hw/tb/`, `tt/`,
`formal/` or `hw/openlane/` is modified**; `hw/rtl/` is read and
instantiated exactly as `hw/soc/flow/sim_soc.sh` reads it. Section 14
lists everything this document adds: **five new scripts under
`hw/soc/flow/`, this document, and one row in `docs/00-index.md`.**
**No existing file in the repository is modified except that index
row.**

**And the measurement is pinned to a commit rather than to a working
tree**, because the working tree was not clean while it ran: another
block was being written into `hw/soc/rtl/soc_clint.v`,
`hw/soc/rtl/soc_busstat.v` and `hw/soc/rtl/soc_top.v` at the time.
Every simulation below was elaborated from a **detached git worktree at
`7721719`**, the commit this work started from, and section 15 says how
to reproduce that. **`HEAD` has since moved past it**, so a reader
checking out `HEAD` and re-running will not get these cycle counts; the
commit is named rather than implied for that reason.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **What does it burn computing?** | **26.827 / 33.890 / 45.036 mW** at slow / typ / fast, on `docs/46`'s supervisor with the core awake, extracted parasitics, measured toggle rates **[fact]**. Section 5 |
| **What does it burn waiting?** | **4.528 / 5.539 / 7.093 mW** **[fact]**, on the same run's WFI intervals, which are **57.6 % of it**. Section 5 |
| **Is idle the same as busy, as `docs/53` section 7.3 says?** | **No. Idle is 16.3 % of busy** **[fact]**, and the mechanism is a clock gate that is already in the netlist and that no document in this repository has ever mentioned. Section 4 |
| **How far off was the static estimate?** | **+2.8 % on the busy case, +529 % on the idle case, +95 % on the duty-cycled run** **[estimate, arithmetic on measured figures]**. Section 5.3 |
| **Where does it go?** | At typ, busy: sequential **10.749 mW**, combinational **13.880**, clock tree **3.828**, the six macros **5.433**. Idle: **2.414 / 1.672 / 1.281 / 0.173** **[fact]**. Section 7 |
| **Which blocks?** | Busy, **`u_ibex` is 87.2 % of all register-bit transitions**. Idle, **`u_clint` 52.4 %, `u_timer0` 24.6 %, `u_uart0` 23.0 %, `u_ibex` 0.03 %** — three free-running counters in **231 of 2,905 flip-flops** **[fact]**. Section 7.3 |
| **The macros?** | Priced twice. `report_power` gives **5.433 mW busy and 0.173 mW idle**; the Liberty's own `when`-conditioned tables against the measured access counts give **2.608 and 0.155** **[fact both ways]**. Section 8 |
| **Anything actionable in the macros?** | **Yes, and it is one line.** `A_REN` is tied to `!do_write`, so every deselected macro is charged **0.5559 pJ per clock edge** against **0** for the same macro with `A_REN` low: **0.147 mW of the idle total, 20.7x the six macros' whole leakage** **[fact]**. Section 8.2 |
| **Energy per inference?** | **2.400 uJ** at typ for `docs/51`'s six-frame inference, measured through the whole SoC at **3,594 cycles** and **33.383 mW** **[fact for both terms, estimate for the product]**. `docs/53` section 7.2's **2.353 uJ** is **2.0 % away from it and both of its terms are wrong** — its cycle count is 6.4 % low and its energy per cycle 4.2 % high, and the errors cancelled. **And neither figure contains the accelerator.** Section 10 |
| **Is the mission's power requirement met?** | **Profile 1 is met and profile 4 is not, and both answers changed.** Orbit-average at profile 1's own 0.0044 % duty cycle is **5.540 mW** — *single-digit* milliwatts against a requirement stated in tens **[estimate]**. "Microwatts when idle" is still missed, but by **1.7 to 2.4 orders of magnitude and not four**. Section 11 |
| **What is missing from the number?** | **The NPU.** The layout has none. The same recipe on the same RTL with `u_npu` in it is **41,543 cells and 5,237 flip-flops against 27,565 and 3,085**, and its power ratio at the same activity is **1.465x busy and 5.588x idle** **[fact]** — the accelerator has no clock gate. Section 9 |
| **What should the next block be?** | **Harden the SoC that exists.** Every power, area and timing figure in `docs/47` through `docs/53` is for a design that is missing 50.7 % of its cells. Section 16 |
| **What may be published?** | **"Single-digit milliwatts idle, tens of milliwatts computing, pre-silicon flow estimate at measured RTL activity, on a layout that fails setup, max slew and max cap and has no DRC or LVS result and does not include the accelerator."** All of it or none of it. `docs/05` section 4 rule 5. Section 11.3 |
| **What does it correct?** | **Nine statements across `docs/45` to `docs/53`, and four in `docs/60`**, of which the sharpest is the datasheet's "the six SRAM macros … are the one term a duty cycle would not remove by clock gating alone": measured, **they are the term it removes most completely, by a factor of 31.4**. Section 12 |

---

## 2. Reproducing the instruments before moving them

`docs/44` section 5.2 set the rule and every document since has followed
it. **Five instruments are used here and all five were reproduced
first.**

| What | Published | Measured here |
|---|---|---|
| `docs/47` section 8.2, sign-off timing at typ | **+5.7231 setup, +0.0367 hold** | **+5.7231 / +0.0367**, from a standalone `sta` run that reads `full3/final/`'s netlist, SPEF and SDC rather than the LibreLane step **[fact]** |
| `docs/47` section 9 / `docs/53` section 7.1, power at three corners | **27.774 / 34.835 / 46.095 mW** | **27.7743 / 34.8347 / 46.0951 mW**, to every digit **[fact]** |
| `docs/47` section 6.1, the hardened netlist | **27,565 cells, 3,085 flip-flops, 396,177.6420 um2** | **the same three** **[fact, `hw/soc/out/s47-sram/area.rpt`]** |
| `docs/56` section 8.4, the whole-SoC invariant | **215,428 cycles** | **215,428**, from the pinned worktree **[fact]** |
| `docs/46` section 7.1, the supervisor's answer | **`sig = 216f8ce6`** | **`216f8ce6`**, both dispatch disciplines **[fact]** |

**And one instrument was reproduced in order to be labelled.**
`docs/53` section 7.1 item 3 says the sign-off figure "rests on OpenSTA's
default propagated activity". It does, and the default is now a number:

> **`set_power_activity -input -activity 0.1 -duty 0.5` reproduces
> `docs/47`'s 34.8347 mW to every digit** **[fact]**. So the sign-off
> power figure is the power of a design in which **every top-level input
> and every register output toggles 0.1 times per clock period and
> spends half its time at 1**, and nothing else about it was ever
> asserted. Section 6 is what happens when those two numbers are
> measured instead.

**Two of the five reproductions did not come for free**, and both are
recorded rather than smoothed over:

- **`docs/46`'s clean supervisor run is 69,106 cycles here against that
  document's 69,100**, and the measured injection window is 9,376..67,296
  against its 9,382..67,318 **[fact]**. The answer word `sig` is
  identical, so it is the same program on the same design; the six-cycle
  difference is the campaign build's `SUP_WDOG_RELOAD` and `WINS`
  settings, which this run does not set. **The number used below is this
  run's.**
- **`hw/soc/flow/fi_core.sh` does not elaborate at all**, and section 3
  is what that turned out to be.

---

## 3. Two defects found before any power was measured

Neither was looked for. Both are in the class `docs/41` section 6.6
keeps — a thing that looks done and is not — and both had to be worked
around before this document could take a measurement.

### 3.1 `fi_core.sh` has not elaborated since `docs/51`

```
FI_WORKLOAD=supervisor hw/soc/flow/fi_core.sh hw/soc/out/tmp
  hw/soc/rtl/soc_top.v:624: error: Unknown module type: soc_npu
  2 error(s) during elaboration.
```

**[fact]**

`docs/51` added `u_npu` to `soc_top.v`; `fi_core.sh`'s Verilog source
list was not updated and still has no `soc_npu.v`, no `soc_npu_ser.v`
and none of the five frozen `hw/rtl/` files `sim_soc.sh` reads. **The
core fault-injection campaigns of `docs/42`, `docs/43` and `docs/46`
cannot be rebuilt at HEAD**, in either workload. `hw/soc/flow/fi_npu.sh`
is unaffected — it has the NPU sources, because it was written for the
NPU — and `sim_soc.sh` is unaffected for the same reason.

**This document does not fix it**, because a repair to the
fault-injection flow is a change to the instrument three campaigns are
reported from and belongs in its own change with its own re-run. The
supervisor images below were built by a **scratch harness outside the
working tree** that is `fi_core.sh`'s recipe with the missing sources
added, and section 15 reproduces it.

### 3.2 The signed-off layout does not contain the accelerator

`hw/soc/flow/syn_soc_top.sh` — the script whose netlist
`hw/soc/flow/pnr_soc_top.sh` hands to LibreLane, by the mechanism
`docs/47` section 6.2 argues for at length — has the same gap:

```
SOC_MEM=sram SOC_KEEP_HIER=1 hw/soc/flow/syn_soc_top.sh 20 <out>
  ERROR: Module `\soc_npu' referenced in module `\soc_top'
         in cell `\u_npu' is not part of the design.
```

**[fact]**

`hw/soc/out/s47-sram/soc_top.netlist.v` is dated **2026-09-01**, and
`grep -i npu` over it and over
`hw/soc/pnr/runs/full3/final/nl/soc_top.nl.v` returns **only the word
`input`** **[fact]**. There is no `soc_npu`, no `soc_npu_ser`, no
`pilot_top`, no `lif_core` and no `aer_fifo` anywhere in the design that
was placed, routed, extracted and signed off.

> **THIS IS NOT AN ERROR IN `docs/47`.** That document was written
> before `docs/51` existed and its netlist is the netlist of the design
> at the time. `docs/51` section 11 states the consequence in its own
> last line — **"`docs/47`'s sign-off does not include this block"** —
> and it is correct.
>
> **IT IS AN ERROR IN `docs/53` SECTION 7.2**, which took that layout's
> power, multiplied it by a measured NPU inference's cycle count, and
> published **2.353 uJ per inference [estimate]** — an energy for a
> computation the silicon it is derived from cannot perform. Section 10
> is what that figure should have been and section 12 item 6 is the
> correction.

---

## 4. The finding that decides the rest: there is a clock gate

`docs/45` section 8, `docs/47` section 9, `docs/48` section 8,
`docs/49` section 12, `docs/50` section 10 and `docs/53` section 7.3 all
carry the same clause: **"one clock, one mode, no scan, no test, no
power number"**, and `docs/53` builds an argument on it —

> **This design idles at 27.8 to 46.1 mW.** It has **one clock and one
> mode** … no clock gating, no retention, no wake-on-event path that
> does not run the whole SoC.

### 4.1 What is in the netlist

```
grep -c sg13g2_lgcp_1 hw/soc/pnr/runs/full3/final/nl/soc_top.nl.v
  1
 sg13g2_lgcp_1 \u_ibex.core_clock_gate_i.u_icg  (.GATE(\u_ibex.clock_en ),
    .CLK(clknet_1_0__leaf_clk_i),
    .GCLK(\u_ibex.clk ));
```

**[fact]**

**It is the real PDK cell and it is there on purpose.**
`hw/soc/rtl/prim_clock_gating.v` exists precisely to bind it: its header
says Ibex "instantiates `prim_clock_gating` … and does NOT provide a
synthesis implementation", that the upstream substitute is "a modelling
stand-in, not a cell", and that this project binds `sg13g2_lgcp_1`
instead. **The file is 53 lines, 24 of them the argument for binding a real
clock gate rather than a behavioural stand-in, and it has been in the
source list of every synthesis and every layout since `docs/38`**
**[fact]**.

`docs/47` section 8.4 even quotes the tree it builds — *"clock-tree
synthesis reports an average sink wire length of 996.17 um on
`u_ibex.clk`, over **2,464 sinks**"* — without noticing that a design
with one ungated clock does not have a net called `u_ibex.clk` with a
sink count of its own.

**2,464 of 3,085 sequential cells is 79.9 % of the design's flip-flops
behind one enable** **[estimate, two measured counts]**.

### 4.2 What it does, measured

From the dump of `docs/46`'s time-triggered supervisor, at the design's
own `u_ibex.clk` and `u_ibex.clock_en`:

| window | cycles | `clock_en` duty | `u_ibex.clk` transitions per cycle |
|---|---:|---:|---:|
| the core awake (`core_sleep_o = 0`) | 29,302 | **1.0000** | **1.9995** |
| the core in WFI (`core_sleep_o = 1`) | 39,804 | **0.0000** | **0.0004** |
| the whole run | 69,106 | 0.4240 | 0.8480 |

**[fact, every cell]**

**2.0 transitions per cycle is a clock and 0.0004 is a stopped clock.**
The gate is not a formality that never closes: on this workload it is
open 42.4 % of the time and shut 57.6 % of it, and the thing that shuts
it is `wfi` in `hw/soc/tb/sw/fi_supervisor.c`.

> **SO THE CORRECT DESCRIPTION OF THIS DESIGN IS "ONE CLOCK DOMAIN WITH
> ONE INTEGRATED CLOCK GATE OVER 80 % OF ITS FLIP-FLOPS, DRIVEN BY THE
> CORE'S OWN WFI", and not "one clock, one mode".** Everything in
> section 5 follows from that, and so does the whole of the difference
> between this document's answer and `docs/53` section 7.3's.

---

## 5. The measurement

### 5.1 What was run, and why this workload

`docs/53` section 15's request names the `full3` netlist and "the
whole-SoC run's own switching activity". Three whole-SoC programs were
available and **the one that answers the question is not the obvious
one.**

| candidate | what it is | why it was or was not used |
|---|---|---|
| `docs/51`'s end-to-end inference, inside `sim_soc.sh`'s 215,428-cycle program | the whole SoC: core, fabric, bridge, both memories, the NPU and the frozen die | **Used, for the inference and for the whole-program figure.** It is the only program that exercises the accelerator. **It is useless for the idle question**: the core is awake for **215,329 of 215,449 cycles — 99.94 %** **[fact]**, and its only WFI is the 120-cycle tail after `crt0.S` posts the exit code. A power number from a workload that never idles cannot answer a question about idle. |
| **`docs/46`'s supervisor, time-triggered** | six frames of partitioned work on a fixed tick, **idling in WFI between them** | **Used, for busy and idle.** It is the only program in this repository with a duty cycle, and its shape — periodic work, long waits — is `docs/05` section 3.4 profile 1's shape. **57.6 % of it is idle** **[fact]**. |
| **the same supervisor, `-DSUP_FREERUN`** | the same partitions, the same schedule, the same kick placement, **one `wfi` removed** | **Used, as the control.** `docs/46` section 7.1: the two builds produce the same answer, `sig = 216f8ce6`. It is the same work with the idle taken out, which is what makes the duty cycle's saving a measurement rather than a model. |
| `docs/56`'s campaign clean run | `fi_npu.c` through the NPU connection | **Not used.** It runs on `tb_soc_npu_fi.v` for the FI campaign's purposes and its workload is 15,542 cycles of connection traffic; it adds no window the other two do not have and it would need its own build. |

**What a different choice would change.** Using only the `docs/51`
program would have produced **one** number — 33 to 34 mW — and would
have reproduced `docs/53`'s conclusion that the part burns tens of
milliwatts whatever it is doing, because on that program it does.
Using only the supervisor would have produced the duty cycle and no
inference. **The two together are the minimum, and even so the NPU is
in the simulation and not in the netlist (section 9).**

### 5.2 The numbers

`hw/soc/pnr/runs/full3/final/`'s netlist, extracted SPEF and SDC; three
corners; 20 ns; 5 % derate; measured activity in place of the default
0.1 / 0.5.

| workload | window | cycles | **slow** | **typ** | **fast** |
|---|---|---:|---:|---:|---:|
| — | `docs/47`'s figure, no annotation | — | 27.774 | **34.835** | 46.095 |
| supervisor, time-triggered | **computing** (`core_sleep_o = 0`) | 29,302 | **26.827** | **33.890** | **45.036** |
| supervisor, time-triggered | **waiting** (`core_sleep_o = 1`) | 39,804 | **4.528** | **5.539** | **7.093** |
| supervisor, time-triggered | **the whole run** | 69,106 | **14.292** | **17.876** | **23.311** |
| supervisor, free-running | the whole run, no idle in it | 29,197 | 26.687 | **33.724** | 44.806 |
| supervisor, free-running | its 216 idle cycles | 216 | 4.570 | 5.594 | 7.162 |
| `docs/51`'s program | **the whole self-test** | 215,449 | 26.442 | **33.407** | 44.344 |
| `docs/51`'s program | **the six-frame inference** | 3,594 | 26.444 | **33.383** | 44.322 |
| `docs/51`'s program | its post-WFI tail | 120 | 4.589 | **5.619** | 7.196 |

**[fact, all in mW]**

**Four checks on the internal consistency of that table, none of which
is the measurement.**

1. **The duty cycle composes.** 42.402 % x 33.890 + 57.598 % x 5.539 =
   **17.560 mW** against the **17.876 mW** measured over the whole run
   **[estimate against fact]** — **1.8 %**. The residue is the boundary
   cycles at each WFI entry and exit, which belong to neither window.
2. **The two dispatch disciplines agree on the work.** Free-running is
   **33.724 mW** over its whole run and time-triggered is **33.890 mW**
   over its busy window — **0.5 %** apart, on two builds that differ by
   one `wfi` **[fact]**. The same pair's idle windows agree to **1.0 %**
   at 216 and 39,804 cycles, which is the check that a 216-cycle window
   is not too short to measure.
3. **THE IDLE FIGURE IS CONFIRMED BY A DIFFERENT PROGRAM ON A DIFFERENT
   TESTBENCH.** `docs/51`'s 215,428-cycle self-test idles for exactly
   **120 cycles** — the tail after `crt0.S` posts the exit code and
   executes `wfi` — and that window measures **5.619 mW** at typ against
   the supervisor's **5.539 mW** over **39,804** cycles: **1.4 %
   apart** **[fact against fact]**. Two programs, two testbenches, two
   idle windows three hundred times apart in length, one answer.
4. **The register population is the netlist's.** On the supervisor the
   dump classifies **2,905 bits** as flip-flop outputs outside the NPU
   against the netlist's **3,085 sequential cells** — **6.0 %** — and
   **2,437 of them under `u_ibex`** against clock-tree synthesis's
   **2,464 sinks on `u_ibex.clk`** — **1.1 %** **[fact against fact]**.
   Two entirely different instruments counting the same flip-flops.

**And the two programs do not have the same population, which is a
property of the method and is stated rather than smoothed.** A bit
enters the population by moving at least once in the reference window,
so `docs/51`'s 215,449-cycle self-test finds **3,455** where the
supervisor's 69,106 finds 2,905 — it exercises more of the machine. The
annotation is therefore *"the mean toggle rate of the registers this
program uses"*, which is the right seed for that program and is not a
constant of the design. **The measured mean is 0.0749 for the
supervisor's busy window and 0.0594 for the whole self-test** **[fact]**,
and section 6 says what a difference of that size is worth: **0.2 mW**.

### 5.3 How far off the estimate was

| | measured | `docs/47`'s estimate | error |
|---|---:|---:|---:|
| computing | 33.890 | 34.835 | **+2.8 %** |
| waiting | 5.539 | 34.835 | **+529 %**, a factor of **6.29** |
| the duty-cycled run | 17.876 | 34.835 | **+95 %**, a factor of **1.95** |

**[estimate, arithmetic on measured figures]**

> **THE NO-VCD NUMBER IS A GOOD ESTIMATE OF A BUSY PART AND A BAD ONE OF
> A MISSION.** OpenSTA's default of 0.1 toggles per cycle is close to
> what this design's registers actually do when the core is running —
> **0.0749** on the supervisor and **0.0594** over the whole self-test
> **[fact]** — so the busy figure was nearly right by luck. **It is not close to what they do when the core is asleep, and
> it cannot be, because the default has no way to express a stopped
> clock.** Every mission profile in `docs/05` section 3.4 is about a
> part that is mostly asleep.

---

## 6. What the number is actually sensitive to

Before the breakdown, the instrument's own dynamic range, because a
figure that barely moves is a figure whose precision does not matter.
`report_power` at typ on the same netlist, sweeping the activity given
to every input port and register output at the measured duty of 0.27:

| activity, toggles per cycle | total, mW |
|---:|---:|
| 0.000001 | **30.492** |
| 0.0001 | 30.368 |
| 0.001 | 30.234 |
| **0.0033** (the measured idle value) | **30.290** |
| 0.01 | 30.463 |
| 0.0335 | 30.935 |
| **0.0749** (the measured busy value) | **31.510** |
| 0.1 (OpenSTA's default, at its default duty of 0.5: 34.835) | 31.748 |
| 0.2 | 32.669 |
| 0.5 | 35.806 |
| 1.0 | 40.725 |
| **2.0** (a clock) | **47.747** |

**[fact, `sta` on `full3/final/`, one invocation, 73 s; the duty is held
at the measured 0.27 throughout, which is why the 0.1 row is 31.748 and
not `docs/47`'s 34.835 — that figure is 0.1 at a duty of 0.5]**

> **WITH THE CLOCK RUNNING, THIS DESIGN'S FLOOR IS 30.5 mW AT TYP.**
> A **twenty-thousand-fold** reduction in data activity, from the
> measured busy value to one part in a million, buys **1.02 mW**; over
> the range the two measured workloads actually occupy — 0.0033 to
> 0.0749 — the figure moves by **1.22 mW, 3.6 %**. That is why
> section 5's idle number is 5.5 mW and not 30: **it is not below the
> floor because its registers are quiet, it is below the floor because
> 80 % of them have no clock.**
>
> **AND IT IS WHY THE RECOMMENDATION IN SECTION 16 IS ABOUT CLOCKS AND
> NOT ABOUT ACTIVITY.** Every technique that reduces toggling — operand
> isolation, bus encoding, a quieter fabric protocol — is bidding for a
> share of **1.2 mW**. The clock gate that is already in the netlist is
> worth **28.4**, and that is a factor of **23**.

**The curve is not monotone** — 0.001 is below 0.000001 — by 0.9 %,
which is OpenSTA's propagation model and not a measurement of anything.
It is reported because a sweep with a wrinkle in it is a sweep, and one
that has been smoothed is a claim.

---

## 7. Where the power goes

### 7.1 By group, which is clock tree against logic against macros

`report_power`'s own four groups, at typ, extracted parasitics:

| group | **computing** | **waiting** | ratio | what it is |
|---|---:|---:|---:|---|
| Sequential | **10.749** | **2.414** | 4.45x | the 3,085 flip-flops: mostly the energy of their own clock pins |
| Combinational | **13.880** | **1.672** | 8.30x | everything the flip-flops drive |
| **Clock** | **3.828** | **1.281** | **2.99x** | the tree itself, its 383 buffers and the one gate |
| **Macro** | **5.433** | **0.173** | **31.4x** | the six RM_IHPSG13 parts, 46.9 % of the die area |
| **total** | **33.890** | **5.539** | **6.12x** | |

**[fact, all in mW]**

Three readings.

**THE CLOCK TREE IS THE LEAST GATEABLE THING IN THE DESIGN AND IT IS THE
SMALLEST OF THE FOUR.** 3.828 mW busy against 1.281 mW idle — the gate
removes two thirds of the tree, which is `u_ibex.clk` and its 2,464
sinks, and the remaining **1.281 mW is the root network that still has
to reach the six macros, the fabric, the timers and the UART**. In the
idle total it is **23.1 %**, the largest single share.

**THE MACROS ARE THE MOST GATEABLE AND THEY ARE ALREADY GATED, BY THEIR
OWN ENABLE.** 31.4x between busy and idle, which is the `A_MEN` pin
doing exactly what it exists for. Section 8 prices them independently.

**SEQUENTIAL DOES NOT FALL BY 80 % AND THAT IS THE 621 UNGATED
FLIP-FLOPS.** 4.45x rather than 5.0x, on a design where 79.9 % of the
flops lose their clock, because the ones that keep it are the ones that
are still doing something. Section 7.3 says which.

### 7.2 By corner, and what the fast corner's macro figure means

| corner | Sequential | Combinational | Clock | Macro | total |
|---|---:|---:|---:|---:|---:|
| slow, computing | 8.601 | 10.711 | 2.957 | 4.558 | **26.827** |
| typ, computing | 10.749 | 13.880 | 3.828 | 5.433 | **33.890** |
| fast, computing | 13.183 | 17.841 | 5.041 | 8.972 | **45.036** |
| slow, waiting | 1.949 | 1.338 | 0.963 | 0.278 | **4.528** |
| typ, waiting | 2.414 | 1.672 | 1.281 | 0.173 | **5.539** |
| fast, waiting | 2.954 | 2.111 | 1.822 | 0.207 | **7.093** |

**[fact, all in mW]**

**The fast corner's macro column is characterised at −55 C where the
standard cells are at −40 C** — `docs/47` section 9's caveat, which
applies to power exactly as it applies to timing, and which is why the
fast row's Macro figure rises **65 %** from typ where the sequential
column rises **23 %**, the combinational **29 %** and the clock **32 %**
**[estimate, arithmetic on the table]**.

### 7.3 By block, which is where the recommendation comes from

`report_power` cannot attribute standard-cell power to a block on this
netlist and the reason is structural: `syn_soc_top.sh` runs
`synth -flatten` and `abc`, so **617 of 33,832 nets carry a name and not
one flip-flop instance does** **[fact]**. What can be attributed is the
**switching**, from the dump, at RTL, per top-level child of `soc_top`.

| block | flip-flop bits | **computing** | **waiting** |
|---|---:|---:|---:|
| `u_ibex` | 2,437 | **87.18 %** | **0.03 %** |
| `u_rom` | 33 | 4.17 % | 0.00 % |
| `u_bus` | 38 | 4.00 % | 0.00 % |
| `u_clint` | 102 | 2.36 % | **52.43 %** |
| `u_timer0` (with the watchdog) | 100 | 0.86 % | **24.59 %** |
| `u_uart0` | 29 | 0.82 % | **22.96 %** |
| `u_ram` | 33 | 0.44 % | 0.00 % |
| `u_pnp`, `u_apb`, `u_apbpnp`, top | 133 | 0.15 % | 0.00 % |
| **total transitions** | **2,905** | **6,374,723** | **303,515** |

**[fact: the bit counts, the transition counts and the shares]**

> **WHAT IT COSTS TO WAIT IS THREE FREE-RUNNING COUNTERS.** `u_clint`'s
> 64-bit `mtime`, `u_timer0`'s prescaler and counter, and `u_uart0`'s
> baud divider — **231 flip-flops, 8.0 % of the design — carry 99.98 %
> of the switching in the idle window**, and `u_ibex`'s 2,437 carry
> 0.03 % **[fact]**. That is not a defect: a timer that stops is not a
> timer, and `docs/40` is four documents' worth of argument for why
> `mtime` must free-run.
>
> **BUT IT IS THE ANSWER TO "WHAT WOULD THE NEXT GATE BE".** It is not
> the core — the core is already gated. It is the fabric and the
> peripherals that have no reason to be clocked between one timer tick
> and the next: of the **468 flip-flop bits outside `u_ibex`**, the
> three counters are **231** and the other **237 carry 0.02 % of the
> idle switching between them** **[fact]**. **Those 237 could lose their
> clock while the 231 kept theirs**, and the netlist's own arithmetic
> puts the same boundary at 621 ungated sequential cells against the
> gate's 2,464.

---

## 8. The six macros, priced twice

### 8.1 What `report_power` says, per instance

The six macros are the only cells in the hardened netlist that still
carry the name the RTL gave them, so this is the one block-level
attribution the layout supports without a second synthesis.

| instance | no annotation | **computing** | **waiting** |
|---|---:|---:|---:|
| `u_ram.g_ram_2048x64.u_b0` | 0.9573 | **1.3234** | 0.0334 |
| `u_ram.g_ram_2048x64.u_b1` | 0.9527 | 0.7637 | 0.0334 |
| `u_ram.g_ram_2048x64.u_b2` | 0.9464 | 0.7637 | 0.0334 |
| `u_ram.g_ram_2048x64.u_b3` | 0.9464 | 0.9485 | 0.0334 |
| `u_rom.g_rom_1024x32.u_b0` | 0.1508 | **1.5756** | 0.0196 |
| `u_rom.g_rom_1024x32.u_b1` | 0.1144 | 0.0580 | 0.0196 |
| **total** | **4.068** | **5.433** | **0.173** |

**[fact, all in mW at typ]**

**The unannotated column is flat and the measured one is not, and that
is the whole point of annotating.** With no VCD every macro of a given
size looks the same, because every macro's `A_MEN` is assumed to toggle
at 0.1 with a 0.5 duty. Measured, **`u_rom.u_b0` is 10.4x its
unannotated figure** — it is the half of the boot ROM this program
executes from, selected on **18,561 of 29,302 busy cycles, 63.3 %**
**[fact]** — while `u_rom.u_b1` is **0.51x** of it, because nothing in
this program lives in the upper 4 KB. **`u_ram.u_b1` and `u_b2` are
never accessed at all**: 0 reads and 0 writes in 69,106 cycles
**[fact]**, on a workload that fits in 32 KB of a 64 KB RAM.

### 8.2 What the Liberty says, which is not the same thing

`report_power` responds to the annotation but the weighting it applies
to a `when`-conditioned `internal_power` group appears in no report it
writes, and the arithmetic below does not reproduce it. So the macros
are priced a second time from the two things that are not in doubt: the
Liberty's own numbers and the number of clock edges the design spends in
each macro state. `soc_mem_sram.v` ties `A_REN` to `!do_write`, so
`A_WEN` and `A_REN` are complementary on every macro on every cycle and
only four of the eight `when` conditions can occur.

`RM_IHPSG13_1P_2048x64_c2_bm_bist`, typical corner, pJ per rising edge
of `A_CLK`:

| state | pJ | what it is |
|---|---:|---|
| `A_MEN & !A_WEN & A_REN` | **122.394** | a read |
| `A_MEN & A_WEN & !A_REN` | **155.368** | a write |
| **`!A_MEN & !A_WEN & A_REN`** | **0.5559** | **deselected, and the SoC is not writing** |
| `!A_MEN & A_WEN & !A_REN` | 0.6834 | deselected, and the SoC writes elsewhere |
| `A_MEN & !A_WEN & !A_REN` | **0** | selected with both strobes low |
| `!A_MEN & !A_WEN & !A_REN` | **0** | **deselected with both strobes low** |

**[fact, `RM_IHPSG13_1P_2048x64_c2_bm_bist_typ_1p20V_25C.lib`; the
1024x32 part's figures are 48.267 / 58.918 / 0.3622 / 0.5298 / 0 / 0]**

Against the measured access counts:

| window | reads | writes | dynamic | leakage | **total** | `report_power` |
|---|---:|---:|---:|---:|---:|---:|
| computing, 29,302 cycles | 19,691 | 2,649 | 2.601 | 0.007 | **2.608** | 5.433 |
| waiting, 39,804 cycles | **0** | **0** | **0.147** | 0.007 | **0.155** | 0.173 |
| the whole run | 19,691 | 2,649 | 1.188 | 0.007 | **1.195** | 2.355 |

**[fact for the counts and the arithmetic; mW at typ]**

**The two instruments agree to 12 % on the idle case and differ by 2.1x
on the busy one**, and this document does not claim to know which is
right. What it claims is that **both of them are far below the 4.068 mW
the unannotated flow reports for a workload in which the memories are
mostly idle**, and that the direction is the same.

### 8.3 And one line of RTL is worth 0.147 mW

> **EVERY DESELECTED MACRO IS CHARGED 0.5559 pJ ON EVERY CLOCK EDGE, AND
> IT DOES NOT HAVE TO BE.** `soc_mem_sram.v` drives
> `.A_REN(!do_write)`, which is **high on every macro on every cycle the
> SoC is not writing** — selected or not, idle or not. The Liberty's
> row for a deselected macro with `A_REN` **low** is **0**.
>
> Measured on the idle window: **117.3 nJ over 39,804 cycles across the
> six macros, 0.1474 mW — against 7.13 uW of leakage for the same six
> parts. The strobe that is doing nothing costs 20.7x what the silicon
> costs standing still** **[fact]**.
>
> **The change is `.A_REN(req_i && !do_write)`.** It adds one AND gate
> per macro, changes no timing arc the read path uses — `A_REN` is a
> setup-checked input on `A_CLK` exactly as `A_MEN` is, and `A_MEN`
> already carries `req_i` — and it is **2.7 % of the idle total** for
> six gates. **It is not the recommendation of section 11 and it should
> not be skipped either**: it is the cheapest measured saving in this
> document by two orders of magnitude in cost.

---

## 9. What the number is missing, and what it would be with it

Section 3.2 established that the layout has no NPU. This section prices
it, with the same recipe, the same Liberty, the same `abc` constraint
file and the same 20 ns target `docs/47`'s netlist was made with — so
the two are comparable, which is the whole of `syn_soc_top.sh`'s
argument.

| | `hw/soc/out/s47-sram`, the netlist `full3` hardened | **the same recipe on `7721719`'s `soc_top.v`, with `u_npu`** | ratio |
|---|---:|---:|---:|
| cells | **27,565** | **41,543** | **1.507x** |
| flip-flops | **3,085** | **5,237** | **1.698x** |
| standard-cell area, um2 | **396,177.642** | **619,892.406** | **1.565x** |

**[fact, `stat -liberty` on two syntheses]**

**The control is `docs/47`'s own netlist and the delta is therefore
everything `soc_top.v` gained between that run and `7721719`** — which
is `u_npu`, the sixth fabric port and the interrupt wiring, and nothing
else. **The flip-flop delta is +2,152 against `docs/51` section 11's
2,008 for `soc_npu` measured standalone** **[fact against fact]**: of
the 144 difference, **six are the sixth fabric port** that document
measures directly, and the rest is the parameter set `soc_top.v`
elaborates the block with against the standalone measurement's.

And the power, on both synthesis netlists, no parasitics, same corner,
same measured activity:

| | no NPU | with NPU | ratio |
|---|---:|---:|---:|
| computing | 33.678 | **49.348** | **1.465x** |
| waiting | 4.346 | **24.283** | **5.588x** |
| Sequential, computing | 26.488 | 45.329 | **1.712x** |
| Sequential, waiting | 3.268 | 23.325 | **7.137x** |

**[fact, mW at typ; switching power on an unrouted netlist is a
cell-pin-capacitance figure and is not usable, which is why the columns
above are dominated by internal power]**

> **THE SEQUENTIAL RATIO WHEN BUSY IS 1.712 AND THE FLIP-FLOP RATIO IS
> 1.698.** Those are two independent measurements of the same thing —
> sequential internal power is the energy of clock pins and there is one
> per flip-flop — and their agreement to **0.8 %** is the check that
> this comparison is measuring what it says.
>
> **AND THE IDLE RATIO IS 5.588, WHICH IS THE FINDING.** The clock gate
> of section 4 is **Ibex's**. `soc_npu` and the frozen die inside it
> have **2,152 flip-flops with no gate at all**, and they keep their
> clock through every WFI. In the design that exists in `hw/soc/rtl/`
> today, **the accelerator is the largest single consumer of idle
> power**, and the block whose entire architectural claim is
> "activity-proportional compute" is the one part of the SoC that is not
> activity-proportional.

**Scaling the layout's figures by those ratios [estimate, and the
weakest number in this document]:**

| | measured, no NPU | **projected, with NPU** |
|---|---:|---:|
| computing, typ | 33.890 | **~49.7** |
| waiting, typ | 5.539 | **~31.0** |

**Its weakness is named rather than hedged**: it applies a ratio taken
from an unrouted netlist — where switching power is cell-pin
capacitance only — to a total that is **36.1 % wire switching**
**[fact]**, on a floorplan sized for 27,565 cells that would have to
hold 41,543, and it assumes the NPU's registers toggle at the same rate
as the rest of the design's, which nothing here measures.
**The only way to know is to harden the SoC that exists**, which is
section 16.

---

## 10. Energy per inference

`docs/53` section 7.2 established that energy per inference is what a
mission budgets, that it is `cycles x energy per cycle`, and that it is
invariant under the clock to 0.045 %. **All three of those stand.** What
changes is both terms.

### 10.1 The window, measured on the whole SoC

`docs/51`'s six-frame inference, located in the 215,428-cycle program by
the design's own inbound and outbound event counters:

| | |
|---|---:|
| first increment of `u_npu.cnt_in` | cycle **191,692** |
| `u_npu.cnt_out` reaches 12, the last barrier | cycle **195,285** |
| **the whole inference** | **3,594 cycles** |

**[fact, timestamps of `cnt_in` and `cnt_out` transitions in the dump]**

**Against `docs/53` section 4.1's block-level W1 of 3,378 cycles that is
6.4 %** **[fact against fact]**, and the difference is the right sign
and the right size: that document timed `soc_npu` from the first
`EVQ_IN` write to the last barrier with a cocotb driver on the bus; this
one times the same six frames with Ibex fetching, decoding and polling
around them. **Two harnesses, one at block level and one through the
whole SoC, agree on what an inference costs to within the CPU's own
loop.**

### 10.2 The energy, both terms measured

| | energy per cycle, typ | x cycles | **energy per inference** |
|---|---:|---:|---:|
| **`docs/53` section 7.2** | 696.694 pJ, unannotated | 3,378, block level | **2.353 uJ** |
| **this document** | **667.650 pJ**, measured | **3,594**, whole SoC | **2.400 uJ** |

**[fact for the two power figures and the two cycle counts; estimate for
the products]**

At the three corners, and per event and per frame:

| | slow | **typ** | fast |
|---|---:|---:|---:|
| energy per cycle | 528.872 pJ | **667.650 pJ** | 886.440 pJ |
| **the six-frame inference, 3,594 cycles** | **1.901 uJ** | **2.400 uJ** | **3.186 uJ** |
| per event across the connection, 34 events | 55.9 nJ | **70.6 nJ** | 93.7 nJ |
| per inference frame | 316.8 nJ | **399.9 nJ** | 531.0 nJ |

**[estimate, section 5.2's measured power over section 10.1's measured
cycle count]**

> **THE TWO FIGURES AGREE TO 2.0 % AND BOTH OF `docs/53`'s TERMS ARE
> WRONG.** Its cycle count is **6.4 % low** because it is the block's
> and not the SoC's; its energy per cycle is **4.2 % high** because it
> is the unannotated figure. **The two errors are in opposite
> directions and they cancelled.** An agreement that survives because
> two mistakes were the same size is not a confirmation, and this
> section exists to say so rather than to let the second figure inherit
> the first's credibility.

**And `docs/53` section 7.2's most important claim is reproduced
exactly.** Scaling the dynamic term by 43.0981 / 50 and carrying leakage
unchanged:

| corner | energy per inference at 50 MHz | at 43.10 MHz | change |
|---|---:|---:|---:|
| slow | 1.9008 uJ | 1.9019 uJ | **+0.062 %** |
| typ | 2.3995 uJ | 2.4007 uJ | **+0.047 %** |
| fast | 3.1859 uJ | 3.1898 uJ | **+0.124 %** |

**[estimate]** — against that document's **+0.059 / +0.045 / +0.119 %**.
**Energy per inference is invariant under the clock to within 0.05 %,
and that survives having both of its terms re-measured.** The clock is
not a parameter of the figure a mission budgets, exactly as `docs/53`
section 7.2 said.

### 10.3 And the number it should be compared against does not exist

**The inference is performed by `soc_npu` and `pilot_top`, and neither
is in the netlist any of these figures come from.** So the honest
statement of this section is in two parts:

1. **What the measured SoC costs while the inference runs** — the CPU,
   the fabric, the bridge, both memories and the interrupt, which is
   everything except the block doing the work — is **2.400 uJ at typ**
   **[fact for the power and the cycles, estimate for the product]**.
2. **What the inference costs** is that plus `soc_npu`. Section 9's
   ratio says the second term is of the same order as the first: the
   accelerator is **69.8 % more flip-flops** than the design measured
   here has in total. **Nothing measures it and this document does not
   invent it.**

> **`docs/53` SECTION 7.2's 2.353 uJ PER INFERENCE MUST NOT BE QUOTED**,
> and the reason is not that it is 2 % out. **The two halves of its
> product come from different designs**: a cycle count for an
> accelerator's work, multiplied by an energy per cycle for a part with
> no accelerator in it. **The figure in section 10.2 has the same
> defect** and is labelled with it here rather than in a footnote.
> Section 12 item 6.

**One more thing the inference window says, which is not about energy.**
During those 3,594 cycles `u_rom.g_rom_1024x32.u_b1` is selected on
**74.9 %** of cycles and `u_ram` on **0.31 %** **[fact]** — the program
is executing out of the ROM's upper bank and touching data almost not at
all, because an inference in this SoC is a polling loop around a slave
that takes 176 cycles to answer. **That is why the inference window's
power, 33.383 mW, is 0.07 % BELOW the whole program's 33.407**: waiting
for the NPU is slightly cheaper than ordinary code, and the block it is
waiting for is not in the measurement.

---

## 11. Is the requirement met

### 11.1 Profile 1, the only quantified requirement in `docs/05`

> Always-on health monitoring of bus telemetry with wake-on-anomaly,
> **where orbit-average power must stay in the tens of milliwatts.**

`docs/53` section 6.2 sized that profile at **0.0044 % of the cycle
budget** — nine OPS-SAT-AD channels at 1 Hz. At that duty cycle:

| | |
|---|---:|
| 0.000044 x 33.890 mW (computing) | 0.0015 mW |
| 0.999956 x 5.539 mW (waiting) | 5.5388 mW |
| **orbit average** | **5.540 mW** |

**[estimate, a measured duty cycle against two measured powers]**

> **THE ORBIT AVERAGE IS THE IDLE POWER, TO FOUR DECIMAL PLACES**, and
> at this duty cycle it always will be. **The requirement is stated in
> tens of milliwatts and the measurement is single digits** — met, with
> between **1.8x and 18x** of margin depending on where "tens" starts
> **[estimate]**. With the NPU included at section 9's projected 31.0 mW
> it is **still met, and only just** **[estimate]**.

### 11.2 Profile 4, which is still not met

> Long-idle mission phases (transfer, storage orbits) where a
> frame-based accelerator would burn its budget doing nothing.

`docs/05` section 3.3's differentiation argument is "the chip must idle
at microwatts and wake on activity". **5.539 mW is not microwatts.**

But the gap is not what `docs/53` section 7.3 says it is:

| | `docs/53` | **measured here** |
|---|---:|---:|
| idle power | 27.8 – 46.1 mW | **4.5 – 7.1 mW** |
| gap to "tens of microwatts" | **~3.4 orders** | **~2.4 orders** |
| gap to "hundreds of microwatts" | ~2.4 orders | **~1.7 orders** |
| is there a mechanism? | *"nothing in the design is aimed at it"* | **there is one, it works, and it covers 80 % of the flip-flops** |

**[estimate for the orders of magnitude; fact for the measured column]**

### 11.3 What may and may not be said outside the repository

`docs/05` section 4 rule 5 binds this; `docs/13-nlnet-application.md` is
a live draft and `docs/60-soc-datasheet.md` is a datasheet whose
section 11.3 flags its own power figures as **[in flux]** and names this
measurement as the thing that supersedes them.

| | |
|---|---|
| **May not be published** | **"5.5 mW idle"** on its own, **"34.8 mW"** on its own, and **any per-inference energy at all.** The first is a number for a design missing its accelerator; the second is a design-average nobody's mission has; the third is section 10.3. |
| **May be published, with all of it or none of it** | "**Pre-silicon flow estimate at measured RTL switching activity: single-digit milliwatts idle and tens of milliwatts computing, at the typical corner, on a placed and routed layout that fails setup at the slow corner, fails max slew and max cap, has never been through DRC or LVS, and does not yet include the neuromorphic accelerator.**" |
| **Is the stronger claim anyway** | **That the part has a measured duty-cycle response.** "The same program, with and without its idle intervals, is 17.9 mW and 33.7 mW — the idle is measured, not modelled, and the mechanism is an integrated clock gate over 80 % of the flip-flops." That is a claim about a *measured ratio*, it does not depend on the absolute number being right, and it is what rule 5 exists to encourage. |
| **Never** | Any of it as **measured consumption**. It is a flow estimate from a Liberty model with no parasitic-accurate glitch modelling, no temperature feedback, no IR drop and no silicon. |

---

## 12. Corrections to earlier documents

1. **`docs/45` section 8, `docs/47` section 9, `docs/48` section 8,
   `docs/49` section 12, `docs/50` section 10 and `docs/53` section 7.3
   all say this design has "one clock, one mode".** It has one clock
   domain and **one integrated clock gate covering 2,464 of its 3,085
   flip-flops**, driven by Ibex's own `clock_en`, present in every
   netlist since `docs/38` and bound to `sg13g2_lgcp_1` by
   `hw/soc/rtl/prim_clock_gating.v`, 53 lines of which 24 are the
   argument for it. Section 4. **This is the same shape as `docs/53`
   section 11's own finding**: a fact in a
   file that six documents reported from and none of them opened.
2. **`docs/53` section 7.3's "This design idles at 27.8 to 46.1 mW" is
   wrong by a factor of 6.29.** It idles at **4.5 to 7.1 mW**. Section 5.
3. **`docs/53` section 7.3's "0.0044 % busy and 100 % powered" is
   wrong.** At 0.0044 % busy the part is **16.3 % powered**, and the
   orbit average is the idle figure. Section 11.1.
4. **`docs/53` section 9.3's "the requirement gap here is four orders of
   magnitude" is between 1.7 and 2.4 orders**, depending on where
   "microwatts" is read to start. Section 11.2. **The ranking that
   follows from it does not change and this document is the item that
   ranking put first; its size does.**
5. **`docs/47` section 8.4 quotes "2,464 sinks on `u_ibex.clk`" as
   evidence about placement** and it is also evidence that `u_ibex.clk`
   is a gated clock net. Not an error; an observation with a second
   reading nobody took.
6. **`docs/53` section 7.2's 2.353 uJ per inference must be
   withdrawn.** Section 10.3. Its cycle term is a block measurement and
   its energy term is a whole-SoC estimate from a netlist with no block
   in it.
7. **`docs/51` section 11's last line — "docs/47's sign-off does not
   include this block" — is correct and `docs/53` did not carry it.**
   That document's section 7.1 quotes the layout's power as this SoC's
   and its 27,565 cells as this SoC's, and section 7.2 multiplies the
   first by an NPU cycle count. **`docs/60`'s revision history does
   carry it** — *"Physical and timing data are from the `full3`
   place-and-route run of `docs/47`, which does not contain the NPU
   subsystem"* — and section 9 is the first measurement of what that
   costs. Section 3.2.
8. **`docs/53` section 7.1 item 2's group split is reproduced exactly
   and is the split of an assumption, not of a workload**: 46.0 %
   combinational, 31.4 % sequential, 11.7 % macro, 11.0 % clock is what
   0.1 toggles per cycle at a 0.5 duty produces. **Measured, computing,
   it is 41.0 / 31.7 / 16.0 / 11.3; measured, waiting, it is
   30.2 / 43.6 / 3.1 / 23.1** **[fact]** — the macro share rises by
   37 % when the memories are actually used and the clock share doubles
   when they are not. Section 7.1.
9. **`hw/soc/flow/fi_core.sh` has not elaborated since `docs/51`.**
   The reproduction sections of `docs/42`, `docs/43` and `docs/46` are
   stale. Section 3.1. Not fixed here.

**And four for `docs/60-soc-datasheet.md`, which is a datasheet and
therefore the document `docs/05` section 4 rule 5 binds most tightly.
Its section 11.3 already carries the flag — *"[in flux] … an
activity-annotated power measurement against this netlist is being
produced as this datasheet is written, and it will supersede the figures
below"*. This is that measurement.**

10. **`docs/60` section 1, "What is deliberately absent", and section
   4.3, "It has one clock and one mode", both say "no clock gating".**
   There is one integrated clock gate over 79.9 % of the flip-flops and
   it is the mechanism the whole of section 5 rests on. Section 4.
   Section 4.3's other clauses — no clock-domain crossing, no
   retention, no sleep state, CLKGATE reserved — are all correct.
11. **`docs/60` section 4.3's "this design is 0.0044 % busy and 100 %
    powered" and "this is the design's one measured requirement gap and
    it is four orders of magnitude wide" are both wrong**, and inherit
    from `docs/53` section 7.3. **16.3 % powered, and 1.7 to 2.4
    orders.** Sections 5 and 11.2.
12. **`docs/60` section 11.3 item 2's "the six SRAM macros are 4.068 mW
    of it, which is the one term a duty cycle would not remove by clock
    gating alone" is exactly backwards.** Measured, **the macros are
    the term a duty cycle removes most completely** — 5.433 mW to
    0.173 mW, a factor of **31.4**, the largest ratio of the four groups
    — because `A_MEN` is their own enable and it goes low when nothing
    is accessing them. **The term a duty cycle does not remove is the
    clock tree**, which falls by 2.99x and is 23.1 % of the idle total.
    Sections 7.1 and 8.
13. **`docs/60` section 11.3's power table and its "2.353 uJ" per
    inference are superseded** by sections 5.2 and 10.2, and its
    section 6.3 note that `core_sleep_o` "is not a power-management
    output" needs its reason changed rather than its conclusion:
    the pin does not *control* anything, but the state it reports is
    exactly the state that stops 2,464 flip-flops' clocks.

---

## 13. What this does NOT cover

Stated at length, because a power figure is exactly the kind of number
that is repeated into a grant application without its caveats.

- **THIS IS NOT A SILICON MEASUREMENT AND IT IS NOT A SIGN-OFF POWER
  ANALYSIS.** It is `report_power` on a Liberty model. There is **no
  glitch power** — the dump is a zero-delay RTL simulation, so a
  combinational node that would switch three times in silicon switches
  once here, and every combinational figure above is a lower bound.
  There is **no temperature feedback**, **no IR drop**, **no
  package**, and **no measurement of the leakage's dependence on
  anything but the corner's fixed temperature**.
- **THE LAYOUT IS NOT SIGNED OFF.** `docs/47` section 8.2: it misses
  setup by **3.2029 ns on 2,003 endpoints** at the slow corner, fails
  hold on 3 at fast, fails max cap at all three corners and max slew at
  two, and has **never been through Magic DRC, KLayout DRC or Netgen
  LVS**, because the one available SRAM macro fails all three inside the
  vendor views (`docs/12` sections 7.5 and 8, `docs/54`).
- **AND IT DOES NOT CONTAIN THE ACCELERATOR.** Section 3.2. Every
  figure from the `full3` netlist is the power of 27,565 of the design's
  41,543 cells. Section 9's projection is a ratio from an unrouted
  netlist and is the weakest number in this document.
- **NOT ONE INTERNAL PIN OF THE LOGIC IS ANNOTATED FROM THE DUMP.**
  Of 33,832 nets in the netlist, 617 carry a name and no flip-flop
  instance does, so `read_power_activities -vcd` would reach under 2 %
  of the design. What is annotated is **the three top-level ports, the
  clock gate's enable, the eighteen SRAM control pins and one
  population statistic** — the mean toggle rate and duty of the
  design's registers, in place of OpenSTA's 0.1 and 0.5. **Everything
  combinational is OpenSTA's propagation from a measured seed and not a
  measurement.**
- **"REGISTER" IS A CLASSIFICATION AND NOT A FACT ABOUT THE NETLIST.**
  A bit is counted as a flip-flop output if it is declared `reg` and
  every one of its transitions in the window lands on a rising clock
  edge. In a zero-delay simulation a combinational net settles in the
  same timestamp as the flop that drives it, so the second half of that
  test is necessary and not sufficient and the first half is a statement
  about a Verilog declaration. **The check that it is close is that it
  yields 2,905 bits against the netlist's 3,085 and 2,437 under
  `u_ibex` against clock-tree synthesis's 2,464 sinks** — 6.0 % and
  1.1 % **[fact]** — and the report prints the alternative population
  (12,382 moving bits, activity 0.111) so the reader can see what a
  different choice would have fed the tool.
- **TWO WORKLOADS, ONE GEOMETRY, ONE CONFIGURATION.** `docs/46`'s
  supervisor at its default watchdog settings and `docs/51`'s program.
  **No fault is injected anywhere in this document**, no upset, no
  scrub, no ECC event, no second NPU geometry, no second floorplan and
  no second clock period. The supervisor's duty cycle is **that
  program's**, not a mission's; `docs/05`'s profiles remain
  **[estimate]** in that document and sizing one does not validate it.
- **THE IDLE WINDOW IS A WFI WINDOW AND NOT A MISSION IDLE.** In it the
  timers run, the watchdog counts, the UART divider runs and the memory
  contents are held. A real long-idle phase would also want retention,
  a slower clock or none at all, and none of that is built or measured.
- **THE MACRO ARITHMETIC OF SECTION 8.2 AND `report_power` DIFFER BY
  2.1x ON THE BUSY CASE** and this document does not know which is
  right. Both are below the unannotated figure and that is all that is
  claimed.
- **`u_ram.g_ram_2048x64.u_b1` AND `u_b2` ARE NEVER ACCESSED AT ALL** in
  the supervisor workload — 0 reads, 0 writes in 69,106 cycles
  **[fact]**. Half the RAM's dynamic power in section 8.1 is a property
  of a program that fits in 32 KB.
- **NOTHING HERE IS AT GATE LEVEL.** The activity is RTL. The netlist
  has still never been simulated — `docs/49` section 12's "nothing has
  ever simulated `soc_top`'s netlist" is unchanged, and a gate-level
  dump is what would put glitch power into this measurement.
- **THE WORKING TREE WAS NOT CLEAN.** Another block was being written
  into `hw/soc/rtl/soc_clint.v`, `soc_busstat.v` and `soc_top.v` while
  this ran. Every simulation was elaborated from a detached worktree at
  **`7721719`**; the first supervisor pair was built before that was
  noticed, was contaminated, and was **discarded and re-run**. The
  synthesis of section 9 reads its RTL from the pinned worktree and its
  three `-I` include paths from the main tree, whose `.vh` files
  `git status` shows unmodified.

---

## 14. Files touched

| File | Change |
|---|---|
| `hw/soc/flow/power_soc_top.sh` | the flow: extract, annotate, report |
| `hw/soc/flow/vcd_activity.py` | VCD toggle-rate extraction, with gated and derived windows |
| `hw/soc/flow/power_activity.py` | toggle rates to `set_power_activity` |
| `hw/soc/flow/power_report.tcl` | the OpenSTA script, three corners |
| `hw/soc/flow/macro_energy.py` | SRAM energy from the Liberty tables |
| `docs/57-power-under-a-duty-cycle.md` | this document |
| `docs/00-index.md` | one row, which `sw/tests/test_doc_links.py` requires |

**No RTL, no testbench, no test and no existing flow script was
modified** **[fact, `git status`]**. In particular nothing under
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was written, and
`hw/soc/rtl/` was read only. The supervisor build harness and the two
synthesis scripts of section 9 live outside the working tree, for
`docs/53` section 13's reason and for one more: `fi_core.sh` and
`syn_soc_top.sh` are the instruments three and six documents report
from, and section 3 is why neither could be used as it stands.

---

## 15. Reproducing this

```
# 0. the instrument, before anything is claimed to move
V=$HOME/Documents/caravel-lif-crossbar/.venv-flow/bin/python
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/full3
cat hw/soc/pnr/runs/full3/19-openroad-stapostpnr/*/power.rpt   # 27.774 / 34.835 / 46.095

# 1. a worktree pinned to the commit, because the tree was not clean
git worktree add --detach /tmp/h57 7721719
for d in gen genp ext tools out; do ln -sfn $PWD/hw/soc/$d /tmp/h57/hw/soc/$d; done

# 2. the two supervisor builds. fi_core.sh cannot do this (section 3.1);
#    the scratch harness is its recipe plus soc_npu.v, soc_npu_ser.v and
#    hw/rtl/{pilot_top,lif_core,aer_fifo,scrub,tmr_voter}.v, with
#    -I hw/rtl for npu_regs.vh, and python3 hw/soc/fi/targets.py
#    writing fi_targets.vh into the output directory.
#      build_sup.sh   /tmp/h57/hw/soc/out/h57-sup
#      SW_DEFINES=-DSUP_FREERUN build_sup.sh /tmp/h57/hw/soc/out/h57-supfree
#    and the whole-SoC program, which sim_soc.sh builds unchanged:
(cd /tmp/h57 && hw/soc/flow/sim_soc.sh /tmp/h57/hw/soc/out/h57-base)

# 3. the dumps. tb_soc.v and tb_soc_fi.v both dump behind +vcd already.
vvp .../h57-sup/tb_soc_fi.vvp     +armed=0 +vcd    # 69,106 cycles,  177 MB
vvp .../h57-supfree/tb_soc_fi.vvp +armed=0 +vcd    # 29,197 cycles,  160 MB
vvp .../h57-base/tb_soc.vvp                +vcd    # 215,449 cycles, 1.1 GB

# 4. the activity, and then the power
hw/soc/flow/power_soc_top.sh extract tb_soc_fi.vcd tb_soc_fi out/sup
hw/soc/flow/power_soc_top.sh annotate out/sup busy tb_soc_fi
hw/soc/flow/power_soc_top.sh annotate out/sup idle tb_soc_fi
hw/soc/flow/power_soc_top.sh report   out/sup busy
hw/soc/flow/power_soc_top.sh report   out/sup idle
hw/soc/flow/power_soc_top.sh report   out/sup default     # reproduces docs/47

# 5. the macros, from the Liberty rather than from OpenSTA
python3 hw/soc/flow/macro_energy.py out/sup/activity.json --window idle

# 6. the inference window, located by the design's own counters
awk '/^#/{t=substr($0,2)+0;next} /^b/{if($2=="|O"||$2=="}O")print t,$2,$1}' tb_soc.vcd
#   |O is u_npu.cnt_in, }O is u_npu.cnt_out; first increment 1916925000 ps,
#   twelfth output 1952855000 ps -> cycles 191692..195285

# 7. the missing block. hw/soc/out/s47-sram/soc_top_syn.ys is the
#    generated script docs/47's netlist came from; the NPU-inclusive
#    synthesis is that file with one read_verilog line inserted before
#    soc_mem_sram.v, every source path pointed at the worktree, and the
#    output directory changed:
#      read_verilog -I<rtl> -I<hw/rtl> -defer soc_npu.v soc_npu_ser.v \
#          pilot_top.v lif_core.v aer_fifo.v scrub.v
yosys -q -l out/h57-npu/syn.log out/h57-npu/soc_top_syn.ys   # 4 min
#   41,543 cells, 5,237 flip-flops, 619,892.406 um2
```

**Cost, quoted with the configuration it was measured in**, on a shared
20-thread host that was also running another agent's synthesis and
cocotb suites for part of it:

| | |
|---|---:|
| the supervisor clean run, no dumping | **2 min 5 s** |
| the whole-SoC self-test, no dumping | **about 4 min** |
| the three dumps | **160 MB + 177 MB + 1.1 GB**, at roughly **1.1 kB per clock cycle** |
| activity extraction of the 160 MB dump, single-threaded Python | **3 min 44 s** |
| the resulting JSON | **17 MB** each, whatever the dump's size |
| one `report_power`, `full3` netlist with SPEF, cold | **40 s** alone, **80 to 90 s** at 7 concurrent |
| the whole matrix | **36 runs in three batches, 7 at a time** |
| the activity sweep of section 6, 12 points in one invocation | **1 min 13 s** |
| the two syntheses of section 9 | **29 s** and **3 min 56 s** |
| **total wall time, end to end** | **about 2 h**, of which about 25 min is OpenSTA and about 45 min is dumping and reading VCDs |

**[fact for every figure that carries a unit to the second; the wall
times are costs and not benchmarks, and the host was also running
another agent's synthesis and cocotb suites for part of the session]**

---

## 16. What the next block should be

**One thing, and it is not a power optimisation.**

> **HARDEN THE SoC THAT EXISTS.** `docs/47` through `docs/53` are six
> documents of area, timing and now power for a `soc_top` that is
> **missing 50.7 % of its cells and 69.8 % of its flip-flops**. The
> floorplan of `docs/48` was sized for 396,178 um2 of standard cells
> against 619,892; the 43.10 MHz of `docs/47` section 8.2 is the
> frequency of a design without a serial transport, an event engine, two
> protected queues and a frozen die in it; and the power of this
> document is the power of the part that is not the accelerator. **Every
> ranked item in `docs/49` section 14, `docs/50` section 12 and
> `docs/53` section 9.3 is ranked against numbers from that design.**
>
> It is one run of `hw/soc/flow/syn_soc_top.sh` with six paths added to
> its source list, and then `pnr_soc_top.sh` — the second of which is
> **83 minutes** by `docs/47` section 8.6's own accounting, plus a
> floorplan that has to be re-sized because section 9 says the cell area
> is 1.565x. **It is the cheapest thing in this record that makes six
> documents' numbers true again.**

**Second, and only then: the second clock gate.** Section 7.3 says
where it goes and section 6 says what it is worth. The core is gated;
**the fabric, the bridge, the memories' request paths and the NPU are
not**, and section 9 measures that the NPU alone multiplies idle power
by 5.588. `docs/08-gr801-datasheet-notes.md` reserved a `GRCLKGATE`-like
slot at **`0xFF918000`** in the frozen memory map and nothing has been
built behind it. What that block would cost:

| | |
|---|---|
| **area** | One `sg13g2_lgcp_1` is **27.216 um2** **[fact, the Liberty]** — 0.0069 % of the standard-cell area per domain. **The area is not the cost.** |
| **the real cost** | **Every gated domain is a new false path, a new hold risk at the enable, and a new way for a block to be asleep when the fabric addresses it.** `soc_bus.v`'s no-starvation property F9 and its response-ownership queues assume every slave answers; a slave whose clock is off does not. That is a formal re-proof, not a gate. |
| **what makes it cheap here** | **`core_sleep_o` already exists as a port and `prim_clock_gating.v` already binds the cell.** The enable for a peripheral domain is `core_sleep_o` and `!s_req` and the absence of a pending response — three signals the fabric already has. |
| **what it is worth** | Section 7.3: at idle, **237 of the 468 flip-flop bits outside the core carry 0.02 % of the switching between them**. Gating the fabric, the bridge and the memories' request paths while the three counters keep their clock is most of what is left of the **2.414 mW** sequential and **1.672 mW** combinational idle total. **With the NPU in the design it is worth 5.6x more than that** (section 9), because that is 2,152 more ungated flip-flops. |

**Third: `.A_REN(req_i && !do_write)`.** Six AND gates, 0.147 mW,
section 8.3. It is not a project and it should not wait for one.

**And what is NOT next.** Reducing switching activity: section 6 prices
the whole measured range of it at **1.2 mW** against the clock gate's
**28.4**. Retention:
nothing in `docs/05` needs the part to hold state through a power-down
and nothing in the flow supports one. A second floorplan for power:
`docs/48` already owns that question and the answer to it changes when
the design gains 50 % more cells.
