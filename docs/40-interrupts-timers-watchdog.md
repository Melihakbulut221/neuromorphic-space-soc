# 40 — Interrupts, timers and the watchdog: three decisions, and the one that changed

`docs/39-soc-bus-and-memory-map.md` section 9 item 2 records the state
this document starts from: "**No interrupts.** No CLINT, no PLIC. Their
addresses are frozen and nothing decodes them; every Ibex interrupt input
is tied off." Item 5 adds the watchdog "that `docs/08` section 4 item 8
makes a project requirement — armed at reset, staged through boot.
Nothing here implements it."

This document is that work. It also has to answer three questions where
the obvious move is not obviously right, and the third of them is the
place where a hardware decision and a hardening consequence meet.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
an intention with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash and the shuttle closes 2026-09-21. Everything here is
under `hw/soc/`, plus `regmap/memmap.yaml` and its generator, one test
file in `sw/tests/`, and this document with its index row. Nothing in
`hw/rtl/`, `hw/tb/`, `formal/`, `tt/` or `hw/openlane/` was modified.
Section 11 lists every file touched.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| Does this SoC need a PLIC? | **No, not yet, and the region stays reserved for one.** Ibex's fifteen fast local interrupts cover the thirteen sources the frozen map defines, with **two spare** **[fact]**. Section 3 states the condition that reverses this |
| Are CLINT and GPTIMER duplication? | **No, and both are built.** CLINT owns monotonic *time*; GPTIMER owns reloadable *intervals* and the watchdog. Section 4 |
| What does the watchdog do when it fires? | **Three stages: NMI, then system reset, then an external pin** — and it cannot be disabled, slowed or acknowledged by software without a key, and its record survives the reset it causes. Section 5 |
| Is a timer interrupt actually taken on the real fabric? | **Yes.** Test 16 of the bring-up program, on the whole SoC: deadline programmed over the system bus, core vectored to `mtvec+0x1C`, handler ran, execution resumed. 22 checks, 185,443 cycles, 0 framing errors **[fact]**. Section 6 |
| Was the `mtvec` constraint exercised? | **Yes, and it bit.** Section 7.1 |
| Is it verified? | cocotb: **60 tests across five blocks**, with **19 mutations, all caught** **[fact]**. Formal: 4 jobs, 12 tasks, all PASS, 35 of 35 cover obligations reached **[fact]**. Section 8 |
| Is any of it hardened? | **No.** The watchdog itself has no parity, no redundancy and no TMR. Section 10 |

---

## 2. What was built

| File | What it is |
|---|---|
| `hw/soc/rtl/soc_clint.v` | RISC-V core-local interruptor: 64-bit `mtime`, `mtimecmp`, `msip`. A system-bus slave, fabric port 4 |
| `hw/soc/rtl/soc_gptimer.v` | GRLIB GPTIMER register map on APB: prescaler, two general timers, and the watchdog as the last timer |
| `hw/soc/rtl/soc_wdog.v` | The watchdog. Its own module, its own reset domain, its own proof |
| `hw/soc/rtl/soc_bus.v` | Extended from four slave ports to five |
| `hw/soc/rtl/soc_top.v` | Two reset domains, the interrupt vector, the two new blocks |
| `hw/soc/tb/sw/crt0.S` | A real 32-entry vector table and four interrupt handlers |
| `hw/soc/tb/sw/soc_timers.h` | Register offsets for the new blocks, shared by the assembler and the C |

---

## 3. Does this SoC need a PLIC?

### 3.1 The case for one, stated fairly

`docs/08-gr801-datasheet-notes.md` section 3 row 7 says "implement a
minimal PLIC (single hart, single context, fixed 32 sources)", and
section 4 item 7 requires the 32 source assignments to be frozen. The
NOELVSYS map puts a PLIC at `0xF8000000` and `regmap/memmap.yaml` froze
that address. Three real arguments follow:

1. **GR801 proximity at the software-visible layer**, which is
   `docs/08`'s own definition of the standing directive. A NOEL-V
   platform has a PLIC; a driver stack built against one expects it.
2. **Portability.** Every RV32 operating system with a board support
   package — RTEMS, Zephyr, Linux — has a PLIC driver. Ibex's fast local
   interrupts are a lowRISC extension; no third-party OS uses them
   without custom code.
3. **Growth.** `docs/08` item 7 lists NPU nodes among the sources, and
   the NPU is a many-node fabric.

### 3.2 The case against, which is the one the evidence supports

**Ibex already has fifteen dedicated, individually vectored, priority-
ordered interrupt inputs, and this SoC has thirteen sources.**
`irq_fast_i[14:0]` occupies interrupt IDs 16..30; each has its own entry
in the vector table at `mtvec + 4*id`, each has its own `mie` bit, and
between them the lowest ID wins **[fact,
`ext/ibex/doc/03_reference/exception_interrupts.rst`]**. That is a
priority-ordered, individually maskable, individually vectored interrupt
controller, in the core, at no cost. A PLIC would add:

- **Latency.** A PLIC handler must *claim* and then *complete*, which is
  two register accesses across the peripheral bus. `soc_apb_bridge.v`'s
  header states the cost of one: three cycles at the bridge, plus the
  fabric. A fast line costs nothing — the handler is entered directly at
  its own vector and the source is identified by the vector itself.
- **Area, and a register file to verify.** The whole of this document's
  new logic is measured in section 9; a 32-source single-context PLIC
  needs at minimum 32 priority registers, a pending and an enable word, a
  threshold, and a priority-selection tree with a claim/complete gateway
  per source. The gateway is the subtle part — claim must clear pending,
  complete must re-arm it, and a level source that is still asserted at
  complete must re-pend — and it is exactly the kind of state machine
  that would be the least-covered thing in this repository.
- **A namespace it does not resolve.** The map's `irq` field is a
  five-bit plug-and-play *source number*, running to 24. Ibex's fast
  lines are a fifteen-entry *wire index*. A PLIC does not remove the need
  to write both down; it only changes which one the hardware consumes.

### 3.3 The decision, and the condition that reverses it

> **No PLIC is built. `irq_external_i` is tied low, the `0xF8000000`
> region stays reserved and continues to fault, and the thirteen frozen
> source numbers each get an explicit fast-line assignment in
> `regmap/memmap.yaml`. Two lines, 13 and 14, are unassigned.**

The region is not a hole in the record. `regmap/memmap.yaml` says in
prose what it is reserved *for*, `irq_external_i` is left unconnected
rather than repurposed so that adding a controller later is a wiring
change and not a rework, and test 12 of the bring-up program loads from
`SOC_PLIC_BASE` and requires a load access fault — so "reserved" is a
tested property and not a comment **[fact, section 6]**.

**The condition is mechanical, not editorial.** The generator refuses a
`line` outside `0..14` and refuses two sources on one line
(`regmap/generate_memmap.py`, `validate()`), so a fourteenth
interrupt-bearing peripheral is a build failure with a message naming
this decision. `sw/tests/test_memmap.py::test_spare_lines_are_the_headroom_the_plic_decision_rests_on`
recomputes the spare count from the map rather than asserting it. When
the count reaches zero — or when a third-party BSP is adopted, which is
an editorial trigger and is recorded as one — the answer changes.

**What this gives up, stated plainly.** A driver written against a PLIC
will not work. The interrupt architecture is Ibex-specific at the
hardware level, and the `docs/09` part B track 3 supervisor will have to
be written against it. `docs/08` row 7's word "Simplify" covers this, but
row 7 also said "reuse of an existing Verilog CLINT/PLIC is likely" and
that half is now declined for the PLIC and taken for the CLINT.

### 3.4 The two namespaces, and why they are two fields

`regmap/memmap.yaml` now carries `irq` **and** `line` on every
interrupt-bearing slot, and the generator checks both:

| Source | IRQ | Line | `mcause` | Vector |
|---|---:|---:|---|---|
| UART0 | 2 | 0 | `0x80000010` | `mtvec+0x40` |
| UART1 | 3 | 1 | `0x80000011` | `mtvec+0x44` |
| GPIO | 4 | 2 | `0x80000012` | `mtvec+0x48` |
| TIMER0 | 8 | 3 | `0x80000013` | `mtvec+0x4C` |
| TIMER1 | 12 | 4 | `0x80000014` | `mtvec+0x50` |
| SPW | 16 | 5 | `0x80000015` | `mtvec+0x54` |
| CAN | 18 | 6 | `0x80000016` | `mtvec+0x58` |
| SPI | 19 | 7 | `0x80000017` | `mtvec+0x5C` |
| I2C | 20 | 8 | `0x80000018` | `mtvec+0x60` |
| QSPICTL | 21 | 9 | `0x80000019` | `mtvec+0x64` |
| BUSSTAT | 22 | 10 | `0x8000001A` | `mtvec+0x68` |
| SCRUB | 23 | 11 | `0x8000001B` | `mtvec+0x6C` |
| NPUCFG | 24 | 12 | `0x8000001C` | `mtvec+0x70` |

**[fact, `docs/memmap-soc.md` section 3a, generated]**

Plus four core inputs that are architectural rather than per-peripheral:
`MSOFT` at ID 3 from the CLINT's `msip`, `MTIMER` at ID 7 from the
CLINT's comparison, `MEXT` at ID 11 unconnected and reserved for a PLIC,
and `NMI` at ID 31 from the watchdog.

Both numbers reach the RTL, the assembler and the C from the same
generated source: `SOC_IRQLINE_*` and `SOC_IRQNUM_*` in
`hw/soc/rtl/soc_memmap.vh`, and `SOC_IRQLINE_*`, `SOC_IRQ_*` and
`SOC_VEC_*` in `hw/soc/tb/sw/soc_memmap.h`. `soc_top.v` builds
`irq_fast_i` out of the first, `crt0.S`'s vector table is checked against
the second by the C tests, and `soc_gptimer.v`'s configuration register
reports the plug-and-play number out of the third — so the number a
driver reads from the peripheral and the number in the device table are
the same number by construction, which
`test_configuration_register_reports_the_map` checks against the map
rather than against the RTL.

**No frozen value moved.** Every `base`, `size`, `slot`, `irq` and
`device_id` in `regmap/memmap.yaml` is unchanged **[fact, verified by
diffing those fields against the file at commit `cea5723`]**. What
changed is additive: a `line` field, a `core_irqs` section, `port: clint`
and two `status` fields promoted from `reserved` to `implemented`.

---

## 4. CLINT and GPTIMER are both timers. Is that duplication?

No, and the reason is not "the specifications both say to have one".

**CLINT owns time.** `mtime` is a free-running 64-bit up-counter that is
never reloaded and never restarted; `mtimecmp` is a deadline on it. It is
the only time base with an architectural meaning: the RISC-V privileged
specification names `mtime`, every RV32 clocksource reads it, and a core
without one has no portable notion of elapsed time. It drives
`irq_timer_i` and nothing else does.

**GPTIMER owns intervals.** Its timers count *down* from a reload value
and restart, which is what periodic work and timeouts want; they chain;
and its last timer is the watchdog. It is a peripheral, with GRLIB's
register map, so `docs/08` rows 8 and 3's "adopt the GRLIB register maps
verbatim" is honoured where it costs nothing.

Up-counting monotonic time and down-counting reloadable intervals are
different jobs with different register shapes, and neither is a
convenient way to do the other's. Building `mtime` out of a GPTIMER would
mean a counter that reloads, which is not a clock; building a periodic
tick out of `mtimecmp` alone means the handler must re-add the interval
every time, which is what an OS does *because it has no other timer*.

The division of labour is written in both files' headers so that a future
reader does not have to reconstruct it. One consequence is worth naming:
**the two have independent time bases and are not synchronised.** The
CLINT ticks at the system clock divided by `TICK_DIV` (1 in this SoC);
the GPTIMER ticks at its own software-programmable prescaler. A program
that timed a GPTIMER interval with `mtime` would measure a ratio, not an
error. Nothing enforces a relationship between them and none is claimed.

### 4.1 What each block is and is not

`soc_clint.v` implements the standard layout: `msip` at `0x0000`,
`mtimecmp` at `0x4000`, `mtime` at `0xBFF8`. It has **one hart** — every
other offset in the 64 KiB window is a bus error rather than a read of
zero, which is the same rule `soc_bus.v` applies to an unmapped address
and `soc_top.v` to an unoccupied peripheral slot, and it costs a
multi-hart-aware driver a fault when it probes hart 1. There is no hart 1.

Three things it deliberately does not do:

- **It does not paper over the 64-bit-register-on-a-32-bit-bus hazard.**
  Writing `mtimecmp` in two stores passes through an intermediate value
  that may already be met, and a spurious timer interrupt appears
  between them. A shadow register would hide it and would change the
  programming model every RISC-V timer driver already implements. The
  architectural three-store sequence is used by `test_ibex.c` and by the
  cocotb suite, and **the suite demonstrates that the hazard is real** —
  `test_naive_mtimecmp_write_glitches_and_the_safe_one_does_not` drives
  the naive sequence and *asserts that a spurious interrupt occurs*,
  because a test that only checked the safe path would be proving
  nothing about the hazard it describes.
- **`mtip` is high out of reset.** `mtimecmp` resets to zero, so
  `mtime >= mtimecmp` from cycle zero. That is standard — the RISC-V
  specification gives `mtimecmp` no reset value — and harmless because
  `mie.MTIE` resets clear, but a driver that enables MTIE before
  programming a deadline takes an immediate interrupt.
  `test_reset_state` asserts it so that anyone changing it has to read
  the reasoning first.
- **`mtime` has no independent time base.** It counts the system clock.
  A real part wants an always-on oscillator that survives the clock being
  gated; that is a clocking and power-intent question this SoC has not
  reached, and the consequence is that `mtime` cannot measure anything
  the clock itself is doing wrong.

`soc_gptimer.v` implements GRLIB's map with two documented simplifications
and one documented divergence. The simplifications: **one shared
interrupt** rather than one per timer, reported honestly as `SI = 0` in
the configuration register, because the frozen map gives this slot
exactly one source number and separate interrupts would consume 8, 9 and
10, which the map has not reserved; and the latch registers, `DH` and
`DF` are not implemented and read zero. The divergence is the watchdog,
which is section 5.

---

## 5. What should the watchdog do when it fires?

### 5.1 The weight it is carrying

`docs/38-ibex-bringup.md` section 10 item 4 chose `small-pmp`: no
lockstep, no shadow register file. Its own words for the consequence:

> Declining `SecureIbex` leaves the core's own sequential logic protected
> by nothing. This project's TMR covers the NPU and the configuration
> state and does not reach inside the CPU. The management processor is
> therefore, as of this decision, the least hardened block in the
> design … **The watchdog in the `docs/08` map is the only backstop
> currently planned, and resetting a core is a coarse instrument.
> Whether it suffices is open.**

So the question is not "what does a GPTIMER's last timer do". It is
"what does the only backstop a silently-corrupted processor has do". A
GRLIB GPTIMER watchdog built to template would have been the wrong
answer, and five specific things follow. They are stated as W1-W5 in the
header of `hw/soc/rtl/soc_wdog.v`, proved or measured against by
`hw/soc/formal/soc_wdog_props.v` and
`hw/soc/tb/cocotb/test_soc_wdog.py`, and argued here.

### 5.2 W1 — it must be independent of the software it watches

**A watchdog its own software can switch off is not a backstop against
software that has stopped behaving.** That is the entire failure mode: a
core whose program counter or whose control-register write has been
corrupted. GRLIB's GPTIMER watchdog is a timer with a writable `EN` bit.

So: `EN` reads 1 out of power-on reset and **a write of 0 to it is
accepted by the bus and ignored by the block**. The read-back reports 1,
so a driver that tried can discover that it failed rather than believing
it succeeded. `RS` and `IE` are the same: it always restarts and always
signals.

There is exactly one thing that can stop it and it is not software: the
`wdog_dis_i` bootstrap pin, sampled **once**, when power-on reset
releases, and ignored for ever after. A pin that could disable the
watchdog at any moment would be a hardware backdoor into the one block
whose job is to be unstoppable; sampling it once makes it a board
configuration. `WDOGSTAT.DISABLED` reports it and `EN` then reads 0, so a
part held off cannot claim to be protected. `soc_top.v` ties it low.

### 5.3 W2 — "cannot be disabled" is worthless if it can be slowed

This is the version of W1 that is easy to miss. **On a real GRLIB
GPTIMER the watchdog shares the block's prescaler, and that prescaler is
a writable register** — so software that cannot clear `EN` can still
multiply the timeout by up to 1024 with one store. That is the same
attack with extra steps.

Here the watchdog has **its own fixed divider that no register reaches**,
and its counter is `WIDTH` bits. The longest timeout the block can be
talked into is therefore a constant of the netlist:

    2^WIDTH * PRESCALE clocks  =  2^16 * 16  =  1,048,576 clocks
                               ≈  10.5 ms at 100 MHz  **[estimate,
                                  arithmetic on the instantiated
                                  parameters; no frequency is measured]**

There is deliberately **no clamp register and no maximum-reload
parameter**. A bound enforced by the width of a counter cannot be
misconfigured; one enforced by a comparator can. The first version of
this file had the comparator, and Verilator's `CMPCONST` warning pointed
out that at the default parameters the comparison was constant — the
clamp was dead logic pretending to be a defence. It was removed.

### 5.4 W3 — reset alone is too coarse, so it escalates

A watchdog that only resets gives the operator no diagnosis and gives
software no chance to recover. One that only interrupts is not a backstop
at all. Three stages:

**Stage 1, the counter reaches zero: raise `nmi_o` and reload.** Software
gets one full timeout to notice, record and recover.

The choice of `irq_nm_i` over a maskable line is the load-bearing part.
The state this fires in is very likely one where `mstatus.MIE` is already
zero — **the core clears it on entry to every trap handler**
(`ext/ibex/doc/03_reference/exception_interrupts.rst`), so a core stuck
inside a handler has interrupts globally disabled. A maskable warning
would simply never be taken in exactly the case it exists for. The NMI is
taken regardless of `mstatus.MIE` and `mie`, is not visible in `mip`, and
has its own vector at `mtvec + 0x7C`. Test 21 of the bring-up program
demonstrates this by never enabling interrupts at all and asserting that
`mstatus.MIE` is zero when the handler runs **[fact, section 6]**.

Two costs of the NMI are recorded rather than discovered later. Ibex
ignores the NMI while already in NMI mode and in debug mode, and nested
NMIs are unsupported — so a second stage-1 during the handler is lost,
which is precisely why stage 2 must not depend on the core taking
anything. And the handler must clear the source before `mret`, because
the line is level-sensitive; a handler that neither cleared nor masked
would re-enter for ever. `crt0.S`'s `vec_nmi` acknowledges and
deliberately does **not** kick: proving the software is alive and
noticing that the watchdog complained are different statements, and a
stage-1 handler that kicked would let a program that does nothing else
keep the watchdog satisfied from inside its own failure.

**Stage 2, the counter reaches zero again with stage 1 unacknowledged:
assert `rst_req_o`.** The core is not involved and cannot prevent it.
`soc_top.v` turns it into the system reset for every block except the
watchdog.

**Stage 3, after `ESCALATE` watchdog resets since power-on: assert
`wdog_no`, the external pin, latched until power-on reset.** Resetting
has demonstrably not worked and the decision belongs to whatever is
outside the chip — a platform supervisor that can power-cycle.

The count is **saturating and cleared only by power-on reset**. A
resettable counter is a counter the failing software can clear. The cost
is a deliberate conservatism: a healthy part that suffers two isolated
upsets days apart still asserts the pin, and the platform can choose to
ignore it. That is the right way round for a spacecraft.

### 5.5 W4 — the state must survive the reset it causes

**Everything in `soc_wdog.v` is in the power-on reset domain.**
`rst_req_o` drives the system reset; nothing in the watchdog is reset by
it. `soc_top.v` therefore has two reset domains and a synchroniser:
`rst_ni` is now the power-on reset and reaches only the watchdog, and
`rst_sys_n` — asynchronously asserted, synchronously deasserted through
two stages — reaches everything else. The synchroniser is not decoration:
`rst_req_o` is a registered signal in this clock domain, so without it
the system reset would deassert on a clock edge, which is a recovery-time
violation at every flop in the SoC.

The result is that after a watchdog reset the boot code reads `WDOGSTAT`
and finds `WDOGRST` set and `RSTCNT` non-zero, and a watchdog reset is
distinguishable from a power cycle. **A watchdog that erased its own
evidence would leave the operator with a machine that reboots for no
discoverable reason, which is the worst possible failure report from a
spacecraft.** Section 6.2 is the demonstration: three boots of the real
SoC in one simulation, carrying information between them through nothing
but that register.

### 5.6 W5 — the kick is keyed, and so is everything else

The failure this block guards is a processor executing something other
than its program, and such a processor stores wild values to wild
addresses. A single-bit "pet me" with no key is a watchdog a runaway can
pet by accident.

**No write to any watchdog register has any effect unless
`wdata[31:16] == KEY`.** The rule is all writes and not just the kick,
and the reason is the acknowledge: if the stage-1 acknowledge bit were
unkeyed, a core spraying stores at the status register would clear it
before every second expiry and hold the machine in stage 1 for ever — the
watchdog would warn and never act. That property is
`test_unkeyed_status_write_cannot_hold_off_stage_2`, and the mutation
that removes the key check fails it **[fact, section 8.3]**.

The consequence is that the value field of every register is the low half
word, which is why `WIDTH` may not exceed 16. GRLIB leaves the upper half
of these registers reserved, so this is a documented divergence and not
an incompatibility with a defined field.

### 5.7 "Armed at reset" is right, and it needed one more thing

The map says the watchdog is "armed at reset" and `docs/08` section 4
item 8 makes it a project requirement rather than an option. It is right,
and the reason it is safe is that **the reset default is the *longest*
timeout the block allows**. A short default risks a board whose boot is
slower than the watchdog resetting for ever with no way in, which is an
unrecoverable brick with no operator-visible cause.

That was not sufficient, and the insufficiency was found by running it.
Section 7.2.

---

## 6. The demonstration: interrupts on the real fabric

### 6.1 The bring-up program, extended

`hw/soc/tb/sw/test_ibex.c` is the same program `docs/38` and `docs/39`
run, with eight new checks that exist only on the SoC platform. All 22
pass:

```
ibex bring-up self-test
  ok   test 0x00000001  ...  ok   test 0x0000000a
  ok   test 0x0000000c    ok   test 0x0000000d    ok   test 0x0000000e
  ok   test 0x0000000f    ok   test 0x00000010    ok   test 0x00000011
  ok   test 0x00000012    ok   test 0x00000013    ok   test 0x00000014
[TB] watchdog stage 1 (NMI) at cycle 174128
  ok   test 0x00000015    ok   test 0x00000016    ok   test 0x0000000b
checks run: 0x00000016  fail mask: 0x00000000
RESULT PASS
[TB] core asleep after 185443 cycles
[TB] console: 587 characters decoded, 0 framing errors
[TB] watchdog: stage1 1, stage2 0, stage3 0
[TB] PASS
```

**[fact, `hw/soc/out/sim-soc/sim.log`]**

| Check | What it demonstrates |
|---|---|
| 15 | `mtime` advances and is coherently readable; an unimplemented CLINT offset is a load access fault |
| **16** | **A machine timer interrupt is taken and returned from.** Deadline programmed over the system bus, `mcause = 0x80000007`, entered at the MTIMER vector, control resumed, and the handler's mask took |
| 17 | `mtip` is a level: raising `mtimecmp` clears `mip.MTIP` |
| 18 | A machine software interrupt through `msip`, at a *different* vector |
| 19 | A GPTIMER interrupt on **fast local line 3**, at `mtvec + 4*(16+3)`, plus the configuration register reporting the map's source number |
| 20 | The watchdog cannot be disabled and cannot be written without the key |
| 21 | The watchdog's stage 1 arrives as an **NMI with `mstatus.MIE` never enabled** |
| 22 | The `mtvec` constraint itself — section 7.1 |
| 12 | Now loads from `SOC_PLIC_BASE`, so "the PLIC region is reserved" is tested |

**Test 16 is the one the whole block exists for**, and what makes it more
than "an interrupt happened" is that it checks **which vector the core
entered at**. Each used vector-table entry has its own stub that writes a
distinct marker before joining the common handler, so `irq_marker` says
which vector was entered and `mcause` says which interrupt the core
believes it took. Comparing the two is the only way a wrong vector is
distinguishable from a right one; reading `mcause` alone would prove
nothing about the vectoring. Tests 16, 18 and 19 report three different
markers at three different vectors.

### 6.2 The watchdog escalation ladder, end to end

Stage 1 is reachable from an ordinary program. Stages 2 and 3 are not:
they only happen when software has *seen* the warning and failed to act,
which a working program cannot produce. So there is one extra build,
identical to the normal one except that the NMI handler is told not to
acknowledge:

```
$ SW_DEFINES=-DWDOG_RESET_DEMO hw/soc/flow/sim_soc.sh hw/soc/out/sim-soc-wdog

wdog demo: boot with WDOGSTAT 0x00000000
wdog demo: arming and refusing to acknowledge
[TB] watchdog stage 1 (NMI) at cycle 10928
[TB] watchdog stage 2 (system reset) at cycle 14144
wdog demo: boot with WDOGSTAT 0x00000102
wdog demo: arming and refusing to acknowledge
[TB] watchdog stage 1 (NMI) at cycle 25104
[TB] watchdog stage 2 (system reset) at cycle 28320
[TB] watchdog stage 3 (WDOGN pin) at cycle 28320
wdog demo: boot with WDOGSTAT 0x00000206
wdog demo: three stages seen, rstcnt 0x00000002
RESULT PASS
[TB] core asleep after 37405 cycles
[TB] watchdog: stage1 2, stage2 2, stage3 1
[TB] PASS
```

**[fact, `hw/soc/out/sim-soc-wdog/sim.log`]**

Three boots of the same image in one simulation. **The only thing
carrying information between them is `WDOGSTAT`** — `crt0.S` zeroes
`.bss` on every boot, so every variable the program has is gone. The
status word goes `0x00000000` → `0x00000102` (WDOGRST set, RSTCNT 1) →
`0x00000206` (WDOGRST and ESCALATED set, RSTCNT 2). If that register were
reset by the reset it generates, this program could not tell a watchdog
reset from a power cycle and would loop for ever, which is exactly the
operator-facing failure W4 exists to prevent.

Each boot also verifies that the reload was restored to the maximum, that
the pending NMI did not survive the reset, and that the external pin
follows the count and nothing else.

### 6.3 The testbench had to change, and the change is a strengthening

`tb_soc.v`'s termination condition was "the core was awake and is now
asleep". The SoC can now reset its own core, and **Ibex reports
`core_sleep_o` high while it is held in reset** — the same behaviour that
`docs/39` section 8 defect 2 already recorded once. So the old condition
goes true in the middle of a watchdog reset, tens of thousands of cycles
before the program has finished, and the first watchdog run ended in a
timeout report at a cycle count that meant nothing.

The condition now also requires the exit magic to be in RAM. That makes
it "the program posted its result and then slept", which is what was
always meant, and it is strictly stronger than what `docs/39` ran.

---

## 7. Findings

### 7.1 The `mtvec` constraint has now been exercised, and it bit

`docs/38` section 7.5 defect 3 recorded that Ibex's `mtvec` is
vectored-only and 256-byte aligned, with `mtvec[7:2]` reading as zero
whatever is written. Until this document nothing in this SoC could raise
an interrupt, so **the core had only ever entered at BASE** and the
vectoring half of that constraint had never run.

Three things came out of exercising it:

1. **`crt0.S` needed a real 32-entry table**, 128 bytes, with
   `.option norvc` around the whole of it. A single entry assembled
   compressed would be two bytes and every later vector would be at the
   wrong offset — a failure that presents as the core vectoring at
   random. Both linker scripts now carry
   `ASSERT(trap_vectors_end - trap_vectors == 128)` so it is a link-time
   error.
2. **`mtvec` never reads back what is written.** Test 22 writes
   `trap_vectors + 4` — deliberately off the 256-byte grid, with MODE
   bits asking for direct mode — and requires the read-back to be the
   enclosing boundary with MODE still vectored. It reads `0xC0000E01`
   against a written `0xC0000E04` **[fact]**. The test's *own* first
   version then failed, because it compared the restored value against
   `good` rather than `good | 1`: `MODE` is hardwired to `2'b01` and
   reads back set. A CSR whose write and read differ is exactly the shape
   of thing a handler address gets silently wrong on.
3. **The generator now enforces that the table fits.** A 32-entry table
   is 128 bytes and every region base in the map is 256-byte aligned;
   `validate()` refuses a map where the first does not fit inside the
   second, and `test_memmap.py` re-checks it.

The `docs/38` minimal-system run still passes, at **131,718 cycles
against the 131,694 recorded there** **[fact]** — 24 cycles more, which
is the vector table's jump on each of the program's traps.

### 7.2 The reload survived the reset it caused, and bricked the SoC

Found by running it, not by reasoning about it. The reload register is in
the power-on domain by W4, so a short timeout that software installed
before it went wrong **survives the reset that going wrong caused**. The
first version kept it, and the whole SoC entered an unbreakable loop:
reset, 1,952 clocks of boot, reset again, for ever, with the console
never reaching its first character. The symptom was a testbench timeout
with a fetch address four instructions into `_start`.

The fix is that a stage-2 reset restores the reload to the maximum. Every
reset stage of GR716B's boot flow (`docs/08` section 2.4) starts from the
boot timeout for the same reason: **whatever the last software
configured, the next boot gets the whole budget.**

*Extended 2026-09-05 by `docs/68-boot-flow.md` section 6.3:* the boot
loader's give-up path deliberately shortens the reload and stops
kicking, so that the reset comes promptly rather than after a full
10.5 ms of doing nothing. **That is safe only because of the fix in this
section**, and `sw/tests/test_soc_boot_guards.py` checks both halves
together — the shortening in the loader and the restore in
`soc_wdog.v` — because the safety of the first is entirely a property of
the second.
`test_the_reload_is_restored_to_the_maximum_by_a_reset` is the check, and
the mutation that removes the restore fails it.

This is the sharpest single argument in this document for W4 being right
*and* for W4 not being sufficient on its own: putting state outside the
reset domain is what makes the record survive, and it is also what makes
a stale configuration survive. Both halves had to be designed.

### 7.3 A Verilog function in a continuous assignment lost its sensitivity

`soc_clint.v` merges byte lanes with a function. Written the short way —
the function reading `be_i` and `wdata_i` from module scope rather than
taking them as arguments — **writes to `mtime` silently did nothing**,
while writes to `mtimecmp` worked perfectly.

The difference is where each is assigned. `mtimecmp` is assigned inside a
clocked `always` block, which re-evaluates the function at every edge.
`mtime` is assigned from a *continuous* assignment, whose sensitivity is
inferred from the expression — and for a function call that is the
argument list, not whatever the body happens to reference. So the
continuous assignment never re-evaluated when `wdata_i` moved.

The symptom was a 64-bit comparison that looked off by one: the cocotb
suite reported `mtip` low where the ghost said it should be high, in
three tests, all of which read like a comparator bug. It was found by
adding a read-back assertion for the *other* half of `mtime` — an
observation, not an inference, which is the same lesson `docs/38` section
7.5 draws at length. Every input to that function is now an explicit
argument and the header says why.

### 7.4 The acknowledge bit was at the wrong position, and only stage 2 showed it

`WDOGSTAT`'s NMI flag is bit 0; the write-one-to-clear decode was written
against a literal `1`. The effect was a watchdog that accepted the
acknowledge and ignored it. **The symptom was not "the write failed"** —
it was a system reset 3,216 clocks later, with a correct-looking NMI
handler in between, and a console log that simply began again.

Two things came out of it. The bit positions are now named constants used
by both the decode and the read, so the layout a reader sees and the
layout the acknowledge decodes are one declaration. And `tb_soc.v` now
reports each escalation stage as it happens, because stage 2 in
particular restarts the program and without that line the symptom is a
log with no explanation.

### 7.5 Three testbench defects, recorded because they all read as design bugs

- **`Timer(T_CHECK)` after a transaction lands one cycle late.** The
  cocotb convention in this repository is that `T_DRIVE`, `T_SAMPLE` and
  `T_CHECK` are offsets *into* a cycle, applied after a `RisingEdge`. A
  transaction helper already returns at `T_SAMPLE`; waiting a further
  `T_CHECK` = 9 ns lands 7 ns into the *next* cycle. Three CLINT tests
  failed by exactly one `mtime` tick.
- **One `Clock` driver per call to `setup()`.** A watchdog test that
  re-applies power-on reset in a loop left one clock generator per
  iteration on `clk_i`, and the effective period shortened with each. It
  reported a stage-1 delay of 10 clocks where 32 was expected, which
  reads exactly like a prescaler bug. `setup()` and `por()` are now
  separate.
- **A ghost that counts a rising edge necessarily lags by one cycle.**
  `soc_wdog_props.v` counts stage-2 events from `rst_req_o`'s own rising
  edge, while the design's counter increments at the edge that produced
  it. The bounded check reported three failures at step 11 that were
  entirely an artefact of the ghost. The properties now use a
  combinational "including the pulse starting this cycle" form.

None of the three was a design defect and all three presented as one.

---

## 8. Verification

### 8.1 cocotb

| Suite | Tests | Result |
|---|---:|---|
| `test_soc_bus` | 13 | 13 pass |
| `test_soc_apb_bridge` | 11 | 11 pass |
| `test_soc_clint` | 12 | 12 pass |
| `test_soc_gptimer` | 10 | 10 pass |
| `test_soc_wdog` | 14 | 14 pass |

**[fact]**

The two pre-existing suites were re-run after the fabric grew a fifth
slave port; the fabric suite's slave index order, latency vectors and
`s_req_o` width all follow from `N_SLAVES`, and the CLINT's index is
cross-checked against the generated map's `PORTS` so that adding a port
in the YAML without extending the suite fails loudly.

No address literal appears in any of the new suites' region addressing:
the CLINT's base comes from `REGIONS`, the GPTIMER's source number from
`APB_SLOTS`, the NMI's interrupt id from `CORE_IRQS`. Register offsets
*within* a block are written in the suite, because they are that block's
own register map and the memory map has never described them — the same
split `test_ibex.c` already uses for the UART.

### 8.2 Formal

| Job | bmc | prove, k-induction | cover |
|---|---|---|---|
| `soc_bus` | PASS, depth 24 | **PASS** | PASS, 12 of 12 |
| `soc_apb_bridge` | PASS, depth 24 | **PASS** | PASS, 7 of 7 |
| `soc_clint` | PASS, depth 20 | **PASS** | PASS, 7 of 7 |
| `soc_wdog` | PASS, depth 40 | **PASS** | PASS, 9 of 9 |

**[fact]**

`soc_clint_props.v` reconstructs the architectural state — `mtime`,
`mtimecmp`, `msip` — from the *ports* alone, and asserts that
`irq_timer_o` is the 64-bit unsigned comparison of the two ghosts. So C1
is a statement about what software asked for, not about what the design
stored, and a block whose comparison was 32 bits wide, whose byte lanes
were wrong, or whose tick was doubled fails it. One strengthening
invariant ties the ghosts to the design's registers, which is what makes
induction start from a consistent state and is itself a real check.

`soc_wdog_props.v` is deliberately a set of **safety** properties rather
than a second implementation: it does not mirror the counter, the
prescaler or the reload. What it states is what must never happen — the
enable never reads clear on an armed part, an unkeyed write never changes
the timeout or clears a pending stage 1, stage 2 is never reached except
out of stage 1, stage 3 never before the `ESCALATE`-th stage 2, the
record is never lost or reduced. The one ghost that mirrors state is the
reset counter, and it counts `rst_req_o`'s own edges rather than reading
the register.

**Both files state what they do not prove.** Neither proves liveness:
nothing says the watchdog ever fires or a deadline is ever met. A block
whose counter never reached zero satisfies every property in
`soc_wdog_props.v`, which is why the cover task is not optional and why
the timeout *arithmetic* is a measurement in the cocotb suite and not a
proof. The watchdog proof also runs at **one parameter point** — `WIDTH`
8, `PRESCALE` 4, `RST_CYCLES` 4, `ESCALATE` 2 — chosen so the ladder fits
in a bounded check; `soc_top.v` instantiates `WIDTH` 16 and `PRESCALE`
16, and nothing proves the policy at every configuration.

### 8.3 Mutation evidence

Nineteen mutations against scratch copies of the RTL, all caught
**[fact]**.
The suites' Makefiles expose `SOC_CLINT_SRC`, `SOC_GPTIMER_SRC` and
`SOC_WDOG_SRC` for exactly this.

| Mutation | Caught by |
|---|---|
| `mtip` uses `>` instead of `>=` | `test_mtip_is_a_level_over_64_bits` and 2 others |
| `mtip` compares only the low 32 bits | `test_naive_mtimecmp_write_glitches_and_the_safe_one_does_not` |
| an unimplemented CLINT offset reads zero | `test_unimplemented_offsets_fault` |
| `msip` takes bit 1 of the write data | `test_msip_is_one_bit` |
| byte enables ignored on an `mtimecmp` write | `test_byte_lanes_are_honoured` |
| `mtime` ticks twice per clock | `test_mtime_advances_once_per_clock` and 1 other |
| **`EN` follows a keyed control write, as GRLIB's does** | `test_software_cannot_disarm_it` and 10 others |
| the key is not checked | `test_unkeyed_writes_do_nothing` and 1 other |
| stage 2 fires on the first expiry | `test_stage_1_then_stage_2_then_stage_3` and 9 others |
| the reload is not restored by a stage-2 reset | `test_the_reload_is_restored_to_the_maximum_by_a_reset` |
| the external pin asserts on the first reset | `test_the_external_pin_waits_for_the_escalate_count` |
| the pending NMI survives the reset it caused | `test_stage_1_then_stage_2_then_stage_3` and 1 other |
| the reset counter wraps instead of saturating | `test_the_reset_count_saturates` |
| the bootstrap pin is sampled every cycle | `test_the_pin_is_sampled_once_and_ignored_afterwards` |
| the watchdog is ORed into the shared maskable interrupt | `test_the_watchdog_is_not_on_the_shared_interrupt` |
| GPTIMER `IP` is not write-one-to-clear | `test_ip_is_write_one_to_clear_and_ie_gates_the_line` and 2 others |
| `RS` is ignored and every timer is periodic | `test_rs_decides_one_shot_or_periodic` |
| the configuration register hard-codes its interrupt number | `test_configuration_register_reports_the_map` |
| the watchdog offsets are routed to a general timer | `test_the_watchdog_offsets_reach_the_watchdog` |

A twentieth defect of the same shape -- a byte-merge function that never
re-evaluated -- did not need a mutation, because it was in the RTL as
delivered and the suite failed on it. Section 7.3.

One mutation in the first run appeared to be caught by nothing, and the
harness was wrong rather than the suite: the edit left the file
syntactically invalid, the simulation never built, and no `FAIL` lines
were produced to parse. The harness now treats a run with no `TESTS=`
line as a failure of the harness. That is the seventh instance in this
repository of a green result being read as wider than what it examined,
and it was caught by looking at *why* a mutation was uncaught rather than
recording that it was.

### 8.4 The map's own sync tests

`sw/tests/test_memmap.py` grew six tests and now passes 30 **[fact]**.
They check that the source numbers and the wire indices are separate,
unique and in range; that `mcause` and the vector offsets are Ibex's
arithmetic recomputed independently of the generator; that the 128-byte
table fits the 256-byte grid; that no core input collides with the fast
range; that the spare-line count is *derived*; that the C header, the
Verilog header and the Python map agree; and — textually, in the same
complementary pair `docs/39` section 5.3 describes — that `soc_top.v`
wires exactly the sources the map marks implemented onto fast lines.

---

## 9. Measured area

Same recipe as `docs/39` section 6, deliberately: Yosys `stat -liberty`
on `ihp-sg13g2` at the typical corner, `abc` with the same driving cell,
the same load, the same 20 ns delay target. Gate equivalent =
`sg13g2_nand2_1` = 7.2576 um2. The Ibex reference is **275,682.6198 um2**
(`hw/soc/out/small-pmp/area.rpt`).

| Block | Cells | Flops | Area, um2 | kGE | % of Ibex |
|---|---:|---:|---:|---:|---:|
| `soc_clint` | 1,038 | 163 | **16,683.48** | 2.299 | 6.05 % |
| `soc_gptimer` (incl. the watchdog) | 1,500 | 222 | **23,733.94** | 3.270 | 8.61 % |
| `soc_wdog` alone | 402 | 53 | 5,785.97 | 0.797 | 2.10 % |
| `soc_bus`, five ports | 808 | 48 | 9,688.29 | 1.335 | 3.51 % |
| `soc_bus`, four ports (`docs/39`) | 673 | 42 | 8,362.31 | 1.152 | 3.03 % |
| `soc_fabric_meas`, five ports | 1,006 | 142 | **16,229.24** | 2.236 | 5.89 % |
| `soc_fabric_meas`, four ports (`docs/39`) | 891 | 136 | 14,807.32 | 2.040 | 5.37 % |

**[fact for every measured row; the percentages are arithmetic on them]**

**Note added 2026-09-05.** The `soc_clint` row reproduces only against
the source list `flow/syn_soc.sh` read on the day. `docs/45-soc-top-synthesis.md`
section 6.2 measures the same, unchanged `soc_clint.v` at **1,043 cells
/ 16,712.8164 um2**, and section 4.3 of that document shows why: the
script reads every SoC block before selecting a top, and the three files
`docs/44` added to the list — `soc_busstat.v`, `soc_tmr_bank.v`,
`tmr_voter.v` — move the CLINT by 29.3328 um2 and 5 cells without
touching it; removing them brings back 16,683.4836 exactly **[fact,
`docs/45` section 4.3, seven re-syntheses]**. Neither number is wrong.
**1,038 / 16,683.48 is the figure for the list at `dbbef96`; the one to
quote for the SoC as it stands is `docs/45`'s.** The `soc_fabric_meas`
row moves the same way and for the same reason (1,027 / 16,379.9874
today), and `docs/51` section 11 reports the same pattern for `soc_bus`.

Three readings worth stating.

**The fifth fabric port costs 1,421.92 um2, or 0.52 % of the CPU**
**[estimate, the difference of two measurements]**. That is what putting
the CLINT on the system bus instead of behind the APB bridge costs, and
it buys a one-cycle `mtime` read instead of the bridge's three-cycle
minimum on the one register software polls in a loop.

**The CLINT is expensive for what it does.** 163 flip-flops is `mtime`
plus `mtimecmp` plus the response registers, and 6 % of the CPU for a
clock is a lot. Two thirds of it is the 64-bit width, which the RISC-V
specification fixes; narrowing `mtime` would be a divergence from the
architecture and is **not** proposed, but the number is recorded so that
if the SoC ever needs the area, the trade is visible.

**The whole of this document's new logic is about 15 % of the CPU**
**[estimate]**: 16,683 + 23,734 + 1,422 = 41,839 um2 against 275,683.
For comparison, `docs/38` section 8.5 measured `SecureIbex` at +112 % of
the same core. Interrupts, timers and a watchdog cost roughly an eighth
of what lockstep would have.

**What the numbers do not say.** No frequency was measured for any of
this RTL and none of it has been through STA at any corner or through
place-and-route. `docs/38` section 10 item 3's three obligations and
`docs/39` section 9 item 6 are untouched and now have more company.

---

## 10. What is not built, and what the checkers do not cover

Stated separately, because "not built" and "built but not checked by the
thing that looks like it checks it" are different failures.

### 10.1 Not built

1. **No PLIC**, by decision. Section 3. `irq_external_i` is tied low and
   the region faults.
2. **No hardening of any of this.** The watchdog has no parity, no
   redundancy and no TMR; nor does the CLINT's `mtime`, an upset in which
   is a silently wrong clock. **The block whose job is to catch upsets is
   itself unprotected**, and that is a gap and not an omission. It should
   be the first thing the hardening architecture reaches.
3. **No windowed watchdog mode.** A kick that arrives too *early* is
   accepted, so a runaway that keeps kicking is invisible to this block.
4. **No independent clock for either block.** If the system clock stops,
   the watchdog stops with it and nothing fires.
5. **No boot flow.** `docs/08` section 4 item 6's ASW image header,
   checksum, boot report register and bootstrap pins still do not exist.
   The watchdog's *staging* through boot is currently one stage: the
   reset default, restored by every watchdog reset.
6. **Eleven of sixteen peripheral slots are still empty**, including
   `BUSSTAT`, `SCRUB` and `BOOTREG`.
7. **No place-and-route, no timing, no gate-level simulation and no fault
   injection** on any of it.
8. **`wdog_dis_i`, `wdog_no`, `wdog_rst_o` and the interrupt observation
   outputs are ports of `soc_top.v` and not pins of anything.** There is
   no pad ring.

### 10.2 What the checkers do not cover

- **The watchdog proof is at one parameter point.** Section 8.2.
- **`soc_clint`'s formal job fixes `TICK_DIV` at 1.** A divided time base
  is a parameter no test and no proof reaches.
- **The 64-bit write hazard is demonstrated, not bounded.** The cocotb
  suite shows one naive sequence glitching and one safe sequence not
  glitching. It does not enumerate the sequences that are safe.
- **Nothing checks that the interrupt a peripheral raises is the one its
  driver expects.** `test_memmap.py` checks the map is self-consistent
  and that `soc_top.v` names the right constants; the whole-SoC run
  checks two of the thirteen sources. The other eleven have a line
  assigned and no hardware behind it.
- **The GPTIMER suite says nothing about the watchdog's policy**, only
  that the shell routes the right offsets to it. The policy is
  `test_soc_wdog.py` and the proof.
- **`tb_soc.v` still exercises two-master contention only incidentally.**
  Unchanged from `docs/39` section 10.
- **The escalation demonstration needs a deliberately broken handler.**
  Stages 2 and 3 are unreachable from a program that works, so the
  demonstration builds one that does not, and what it proves is that the
  hardware behaves as specified when software fails in that *particular*
  way.
- **Nothing has run at gate level or with back-annotated timing.** Every
  cycle count in this document is RTL simulation.

---

## 11. Files touched outside `hw/soc/`

`docs/34` section 2 pins the pilot by git blob hash of the files in
`hw/rtl/` and section 5 lists the flow configs. None of the following is
in either set **[fact]**:

| File | Change |
|---|---|
| `regmap/memmap.yaml` | additive: a `line` field per interrupt-bearing slot, a `core_irqs` section, `port: clint`, two `status` promotions. No frozen address, size, slot, source number or device id moved |
| `regmap/generate_memmap.py` | validation and emitters for the above |
| `sw/golden/memmap_gen.py`, `docs/memmap-soc.md`, `hw/soc/rtl/soc_memmap.vh`, `hw/soc/rtl/soc_pnp_rom.vh`, `hw/soc/tb/sw/soc_memmap.h` | regenerated |
| `sw/tests/test_memmap.py` | six new tests, section 8.4 |
| `docs/40-interrupts-timers-watchdog.md` | this document |
| `docs/00-index.md` | one row, which `sw/tests/test_doc_links.py` requires |
| `README.md` | the "next block" paragraph, which named this work |
| `.gitignore` | two entries: the SymbiYosys working directories of the two new formal jobs. Same rule the file already applies to `soc_bus` and `soc_apb_bridge`, and the same non-argument `docs/38` section 11 makes: `.gitignore` is in neither of `docs/34`'s pinned sets |

Everything else is under `hw/soc/`. `hw/soc/{ext,tools,gen,out}` remain
gitignored.

---

## 12. Reproducing this

```
python regmap/generate_memmap.py
.venv/bin/python -m pytest sw/tests/test_memmap.py

make -f hw/soc/tools.soc.mk soc-toolcheck

hw/soc/flow/sim_soc.sh                          # 22 checks on the real SoC
SW_DEFINES=-DWDOG_RESET_DEMO \
  hw/soc/flow/sim_soc.sh hw/soc/out/sim-soc-wdog   # the escalation ladder
hw/soc/flow/sim_ibex.sh small-pmp               # the docs/38 run, unchanged

cd hw/soc/tb/cocotb
make -f Makefile.soc_bus
make -f Makefile.soc_apb_bridge
make -f Makefile.soc_clint
make -f Makefile.soc_gptimer
make -f Makefile.soc_wdog

cd hw/soc/formal && make                        # four jobs, twelve tasks

hw/soc/flow/syn_soc.sh soc_clint
hw/soc/flow/syn_soc.sh soc_gptimer
hw/soc/flow/syn_soc.sh soc_wdog
hw/soc/flow/syn_soc.sh soc_fabric_meas
```

---

## 13. What the next block should be

Two candidates, and the argument is no longer close.

**`BUSSTAT`, the system-bus error latch** — `docs/08` section 3 row 18,
slot `0x015`, source number 22, fast line 10, all frozen and all empty.
The fabric already produces bus errors and the core already takes them as
access faults; nothing anywhere records the address, the master or the
type. This document has just added three more blocks that can produce
one. It is a small block, it is the first piece of the hardening
observability story in the family's own idiom, and it has a fast line
waiting for it.

**The core's fault-injection campaign** — `docs/38` section 10 item 4
made it a consequence of declining lockstep rather than deferred work:
"an unmeasured block, in a design whose entire claim is *measured* fault
tolerance, is the gap a reviewer finds before we do." That is still true,
and this document has changed the arithmetic for it: the watchdog now
exists, so the campaign can measure not only the core's SDC rate but
**how much of it the backstop actually catches** — which is the question
`docs/38` left open in the words "whether it suffices is open".

The recommendation is **the campaign**, and `BUSSTAT` immediately after
it. The campaign is the one that can invalidate an architectural decision
already taken; `BUSSTAT` cannot. And the campaign's answer determines
what `BUSSTAT` needs to latch.

One thing should be done before either, and it is small: **the watchdog
and the CLINT counter have no protection at all**. A watchdog that an
upset can silently disarm is worse than no watchdog, because the system
believes it has one. Whatever the campaign finds, the block whose job is
to catch upsets should not be the least protected thing in the design.
