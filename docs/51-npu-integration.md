# 51 — Connecting the NPU: the die has a serial port, so the SoC drives one

`docs/39-soc-bus-and-memory-map.md` section 9 item 4 is one line long:

> **No NPU connection.** The 256 MiB window is frozen and reaches the
> error slave.

Every document since has repeated it. Until this one the repository held
a RISC-V SoC and a separate neuromorphic accelerator that had never been
in the same simulation, and the word "neuromorphic" in its name was a
statement about two directories rather than about a part.

**This document is that connection, and it is built the hard way.**
`hw/rtl/pilot_top.v` — the TTIHP26b submission, frozen by blob hash in
`docs/34-pilot-freeze.md`, unmodified — is INSTANTIATED in `soc_top.v`
and reached over the same four serial pins the die will have. A program
on Ibex, out of the boot ROM, over the real fabric, configures it, loads
its weights, feeds it an event stream and reads the spikes back, and the
result is checked against `sw/golden/lif_core.py` rather than against
what the hardware produced. **27 checks, fail mask 0, 213,971 cycles.**

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
an intention with nothing behind it yet.

**The pilot is untouched.** `docs/34` pins the submission by blob hash
and the shuttle closes 2026-09-21. Nothing in `hw/rtl/`, `hw/tb/`,
`tt/`, `formal/` or `hw/openlane/` was modified; seven files in
`hw/rtl/` are **read and instantiated** and
`sw/tests/test_soc_npu_guards.py` fails if any of them has been touched.
Section 16 lists every file.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| Is the 256 MiB window reached? | **Yes.** Fabric port 5, sixteen 4 KiB per-node register windows in its low 64 KiB, and everything else in it is a bus error that the program tests **[fact]**. Section 6 |
| Serial master, or a parallel port on a copy of the pilot? | **The serial master, and the argument is not "purity".** Section 3 |
| Is the frozen pilot instantiated or copied? | **Instantiated**, out of `hw/rtl/`. There is no copy anywhere under `hw/soc/` and a test says so **[fact]** |
| Does an inference run end to end? | **Yes, and it matches the golden model event for event and neuron for neuron.** 22 events in, 12 out, six spikes and six barrier echoes, all in stream order, plus the whole neuron state file **[fact]**. Section 7 |
| Where does the answer come from? | `sw/golden/lif_core.py`, at BUILD time, into a header the ROM image carries. The program never asks the hardware what the answer is. Section 7.1 |
| What does a register access cost? | **176 clock cycles**, measured, of which 171 is the serial frame **[fact]**. Section 8 |
| What does the whole program cost? | **185,443 → 213,971 cycles, +28,528, +15.4 %** — of which about **13,840 is console output** and the rest is the work **[fact for the counts, estimate for the split]**. Section 8.3 |
| What does the interrupt cost? | **Nothing that was spare.** `docs/40` assigned NPUCFG source 24 on fast line 12 before this block existed; lines 13 and 14 are still unassigned and a test derives that **[fact]**. Section 9 |
| Is it verified? | cocotb: **21 tests on `soc_npu` with the frozen pilot inside it, 21 pass**, with **14 mutations, of which four survived and one of those was a real gap** **[fact]**. Formal: **4 tasks on the transport, all PASS, 5 of 5 covers reached**, and **the fabric's own proof extended to six ports, 17 of 17 covers** **[fact]**. Section 10 |
| Is any of it hardened? | **The queues are, because they are `aer_fifo`. Nothing else is.** Section 14 |
| Is a descriptor ring built? | **No, and section 12 prices it rather than deferring it.** |

---

## 2. What was built

| File | What it is |
|---|---|
| `hw/soc/rtl/soc_npu_ser.v` | The serial host master. A transport and nothing else: one 40-bit mode-0 frame per register transaction, honouring the die's three host obligations by construction |
| `hw/soc/rtl/soc_npu.v` | The NPU subsystem. Two bus faces — the node register window on the system bus, the event port on the peripheral bus — an AER event engine between them, and the frozen `pilot_top` instantiated inside |
| `hw/soc/rtl/soc_npu_regs.vh` | Generated. The node register map for the SoC, from the same `regmap/regmap.yaml` that produces the die's own header |
| `hw/soc/rtl/soc_bus.v` | Extended from five slave ports to six |
| `hw/soc/formal/soc_bus_props.v` | The same extension, in the proof. Section 10.2 |
| `hw/soc/rtl/soc_top.v` | The subsystem, the sixth port, the NPUCFG slot decode, the interrupt line, and the die's pins brought out for observation |
| `hw/soc/flow/gen_npu_vectors.py` | The golden model's answer, computed at build time into two headers the program compiles against |
| `hw/soc/tb/sw/soc_npucfg.h` | The NPUCFG block's own register map, hand-written, as `soc_timers.h` is for the GPTIMER |
| `hw/soc/tb/sw/test_ibex.c` | Five new checks, 23 to 27 |
| `hw/soc/tb/sw/crt0.S` | A vector stub for interrupt id 28, fast line 12 |
| `hw/soc/tb/cocotb/test_soc_npu.py` | 21 tests, with the frozen pilot in the design under test |
| `hw/soc/formal/soc_npu_ser_props.v`, `.sby` | The serial protocol and its three host obligations, proved |
| `sw/tests/test_soc_npu_guards.py` | 15 textual guards, including that `hw/rtl/` is unmodified |

---

## 3. The connection decision, which is what this document is really about

### 3.1 The options, stated fairly

The pilot exposes exactly two interfaces. A **serial host port** —
`ser_sck`, `ser_cs_n`, `ser_mosi`, `ser_miso` — through which its whole
register bank is reached, and a **parallel 4-bit AER port** for events.
The host port is serial because it was designed against a Tiny Tapeout
pin budget. Inside an SoC there is no pin budget.

**(a) Drive the serial port from hardware.** A memory-mapped serial
master shifting frames into the frozen pilot exactly as external silicon
would. Preserves `pilot_top` bit-exactly. Costs latency and a shift
engine.

**(b) Add a parallel register port to a copy of the pilot under
`hw/soc/`.** Faster and cleaner, and the copy diverges from the design
being fabricated.

**(c) Something else.**

### 3.2 The usual argument for (a), and why it is not enough alone

The obvious case is: **the shuttle silicon will have the serial port and
nothing else.** If a TTIHP26b die arrives in 2027 and the SoC was built
against a parallel port that does not exist in it, the SoC cannot be
validated against the only real hardware this project will ever have.

**That argument is weaker than it first looks and it should be attacked
before it is used.** The SoC is not on the same die as the pilot and
never will be — the pilot is twelve Tiny Tapeout tiles, the SoC is a
different part on a different schedule. So "validate the SoC against the
die" cannot mean putting the die inside the SoC. It means running the
SoC's *driver* against the die over a bench harness, and a bench harness
needs a serial host of its own whether or not the SoC contains one. On
that reading, option (b) costs nothing: build the SoC against a parallel
port, and write a separate serial host for the bench.

**Three things defeat that reading, and only the third is decisive.**

**First, (b) needs a second copy of a frozen file, and this repository
has been bitten by second copies six times.** `docs/28` section 4.4a,
`docs/23`, `docs/34` section 8.5, `docs/36`, and `docs/38` sections 8.2
and 7.4 are all the same defect in different clothes: something was
checked, and the thing checked was not the thing that shipped. A copy of
`pilot_top.v` with a parallel port added would be verified, hardened and
measured, and every one of those results would be about a module that is
not the submission. The freeze exists precisely to make that impossible,
and `docs/34` section 9's rule is that changing a pinned file costs a
re-harden.

**Second, the parallel port is not a small change to that copy.** The
die's read side effects are timed to the serial frame: `pilot_top.v`
section 2 states that a read captures the addressed register when the
COMMAND BYTE completes, so `EVQ_OUT`'s pop happens once, early, at that
capture. A parallel port has no command byte and no frame, so the pop
would have to be re-timed — and `EVQ_OUT` is the register whose pop
semantics `docs/50` section 5.1 spends four pages on. Adding a parallel
port means re-deciding, and re-verifying, the part of the register bank
that is hardest to get right.

**Third, and this is the one that decides it: with (a) there is only
one host implementation, and it is the SoC's.** The bench harness for
the die is not a second thing to write — it is `soc_npu_ser.v` and the
driver above it, pointed at a socket instead of at an instance. The
three host obligations `pilot_top.v` numbers H1, H2 and H3 are
implemented once and proved once (section 10.2). With (b) they would be
implemented twice, and the copy that is *not* in the SoC is the copy
nobody runs a regression against — so it is the copy that would still
have the half-period-gap defect the pilot's own bring-up found.

> **THE DECIDING QUESTION IS NOT "CAN THE SoC TALK TO THE DIE". IT IS
> "HOW MANY IMPLEMENTATIONS OF THE DIE'S HOST PROTOCOL EXIST, AND WHICH
> OF THEM IS REGRESSED".** Option (a) answers one, and it is the one in
> the SoC's own test suite. That is a stronger reason than the shuttle
> argument, and it survives the attack the shuttle argument does not.

### 3.3 What was actually built is (c), and the difference matters

Option (a) as stated would be "a serial master, memory-mapped". What is
built is one level up from that:

> **THE SoC-SIDE INTERFACE IS THE MEMORY MAP, AND THE TRANSPORT IS
> UNDERNEATH IT.** `SOC_NPU_BASE + node*0x1000 + offset` behaves exactly
> like the `docs/10` section 10 register block, reached with ordinary
> loads and stores. Software does not know a serial port exists. A
> future node with a native 32-bit configuration bus — which is what
> `docs/10` section 1 specifies and what a full-scale node will have —
> is a change of transport under an unchanged address, an unchanged
> driver and an unchanged test suite.

The difference between (a) and (c) is one sentence in the RTL and the
whole of the software interface. It is the answer to the second question
this work had to decide, which is section 5.

### 3.4 What (a) costs, stated rather than waved at

**176 clock cycles per register access** **[fact, section 8]**. At the
pilot's scale that is a few dozen accesses per pass and it does not
matter. At full scale — 16,384 weight words, `docs/10` section 5 — it
would be 32,768 register writes and 5.8 million cycles, which is
absurd. **That is not an argument against the serial transport; it is an
argument the specification already makes.** `docs/10` section 9 puts
weight loading on a QSPI DMA path for exactly this reason, and section
14 item 4 lists it as the v0.2 work. The serial transport is the right
transport for configuration and the wrong one for bulk, and configuration
is what it carries.

---

## 4. The die's two ports are not symmetric, and the pin contract says so

The second question the brief posed is whether register access and event
flow are the same problem. They are not, and **the pilot's own pinout
already separates them** — `pilot_top.v` section 1 gives the event path
its own pins. So the SoC uses both, at the rate each was designed for.

What is worth recording is that the parallel port is **lossy in one
direction and impossible in the other**, and both facts come from the pin
contract rather than from anything in this work:

**Inbound, SYNC has no pin.** The event word the die builds from its
input pins is `{AER_IN_TICK ? 2'b01 : 2'b00, ...}`. Its TYPE field is 00
or 01 and never 10. **SYNC — the frame barrier that `docs/10` section
7.1 makes the determinism and multi-pass handshake primitive — cannot be
injected over the pins at all.** It goes over the serial `EVQ_IN`
register instead, at 176 cycles once per frame rather than per event.

**Outbound, there is no TYPE.** `AER_OUT_ID` is four bits and
`pilot_top.v` section 1 says what they are: "the low four bits of its ID
field". **A SYNC echo and a spike from neuron 0 are the same four bits.**
Reading the output pins would silently conflate the barrier with a
spike, which is the one event in the stream whose identity the sequencer
depends on. So `AER_OUT_VLD` is used as a NOTIFICATION and the word is
read from the die's `EVQ_OUT` register, which the same section says "is
always available over the serial EVQ_OUT register".

`aer_out_ack` is therefore **tied low and never used**: the serial read
is itself the pop, and two pop paths into the die's one-entry show-ahead
register would be two ways to lose the same event.

> **THE CONSEQUENCE IS AN ASYMMETRY OF ABOUT 44x AND IT IS THE TILE'S
> PIN BUDGET SHOWING THROUGH, NOT A DESIGN CHOICE.** An inbound SPIKE or
> TICK costs **4 clock cycles** on the pins; an outbound event costs a
> **176-cycle** frame **[fact]**. A full-scale node's mesh link
> (`docs/10` section 8 item 2, a 24-bit word with valid/ready) is
> symmetric and has neither problem, which is why the SoC-side event
> interface below is shaped like the mesh link and not like these pins.

---

## 5. Is this connecting to the pilot, or designing for a full-scale NPU?

**The second, and the frozen map's own author is the evidence.**
`regmap/memmap.yaml` reserves **256 MiB** at `0x10000000` and describes
it as "per-node register windows and descriptor rings", and separately
reserves a 4 KiB peripheral slot called NPUCFG for "NPU fabric-level
global configuration and status". A single pilot needs neither: one
4 KiB page would hold its whole register bank. Somebody who intended a
mesh wrote that map, and `docs/08` section 3.1 is where they wrote it.

So the CPU-side interface is designed for the mesh and the pilot is its
first and smallest instance:

| What the SoC presents | Why it is that shape | The pilot's part in it |
|---|---|---|
| One 4 KiB register window per node at `NODE_ID * 0x1000`, sixteen of them | `docs/10` section 8 item 5 freezes "one identical regmap instance per node at a per-node base address"; item 2 makes NODE_ID four bits | One node at index 0; the other fifteen are decoded and fault |
| A 16-bit event stream in each direction, valid/ready, `docs/10` section 7.1 words | Item 1 freezes the event word and item 3 freezes the handshake. This is the mesh link minus its 8-bit routing prefix, which item 2 says is tied off in single-node builds | Carried by a hybrid of the die's pins and its serial port, section 4 |
| One interrupt with a cause register | A cause register scales to sixteen nodes on one wire; a wire per node does not | Five of the seven cause bits come off the die's fault pins |
| The rest of the 256 MiB reserved and faulting | Descriptor rings live there and are not built, section 12 | — |

**What this costs.** The window decodes sixteen node slots when one
exists, which is four comparator bits that do nothing today, and the
event port carries a 16-bit word where four would do. Both are
unmeasurable next to the queues (section 11). **What it buys** is that
the second node is a parameter and a wiring change rather than a
redesign of the software interface — which is the whole content of
`docs/02` section 4 point 2's "one node of a mesh from day one".

---

## 6. The memory map, and what "reserved" now means inside it

Nothing in `regmap/memmap.yaml` moved. Two fields changed: the NPU
region gained `port: npu` and both it and the NPUCFG slot were promoted
from `reserved` to `implemented` **[fact, the diff]**.

```
0x10000000 + node*0x1000 + offset    node `node`'s docs/10 section 10
                                     register block, offsets 0x000..0x1FC
0x10000000 .. 0x1000FFFF             sixteen such windows; nodes at or
                                     above N_NODES are a bus error
0x10010000 .. 0x1FFFFFFF             reserved. Descriptor rings would
                                     live here. Bus error.
0xFF919000                           NPUCFG, the fabric controller and
                                     the event port
```

Three decode rules, and each of them faults rather than aliasing:

- `addr[27:16] != 0` — above the node windows, including the whole
  descriptor-ring area;
- `node >= N_NODES` — a node that is not instantiated;
- `addr[11:9] != 0` — above `0x1FC`, which is where the die's own
  seven-bit register address runs out;
- **a sub-word write.** The serial frame is 32 bits and carries no byte
  enable. A slave that accepted a byte store would have to widen it,
  writing three bytes of a register the master never named. It faults,
  and check 25 of the bring-up program requires `mcause = 7` for it.

**Check 25 tests all five**, and the cocotb suite tests seven addresses
plus four byte-enable patterns plus three misalignments **[fact]**. A
window that decoded everything to node 0 would pass every other NPU
check in this repository and fail that one.

---

## 7. The demonstration

### 7.1 The answer is computed before the hardware is asked

`hw/soc/flow/gen_npu_vectors.py` runs on **every** build of the ROM
image, before the compiler. It builds the weight matrix, runs
`sw/golden/lif_core.py` — which `docs/10` section 13 makes the normative
executable form of the section 4 equations — over the stimulus, and
emits two headers:

- `npu_regs.h`, the node register map in C, from `regmap/regmap.yaml`,
  so no offset of that map is written by hand anywhere in the program;
- `npu_vectors.h`, the stimulus and **the expected output stream**.

The program compares against those constants. **It never asks the
hardware what the answer is**, which is the difference between a check
and a tautology.

The configuration and the stimulus are `hw/tb/test_pilot_top.py`'s,
deliberately unchanged — same `LIFConfig`, same frames, same weight seed
— so the SoC's run and the pilot's own run are the same inference on the
same numbers, and a disagreement between them is attributable.

### 7.2 What the program does

```
  ok   test 0x00000017      NPUCFG answers; its reserved offsets fault
  ok   test 0x00000018      the node window IS docs/10 section 10
  ok   test 0x00000019      reserved addresses in the window are faults
npu: 0x0000000c events, cnt=0x000c0016 status=0x0000002a
  ok   test 0x0000001a      the inference, against sw/golden
  ok   test 0x0000001b      the interrupt, on the map's own fast line
checks run: 0x0000001b  fail mask: 0x00000000
RESULT PASS
[TB] core asleep after 213971 cycles
[TB] console: 760 characters decoded, 0 framing errors
```

**[fact, `hw/soc/out/sim-soc/sim.log`]**

Check 26 is the one the block exists for. In order: state clear and wait
for BUSY to drop; write eight configuration registers and **read one
back**, because a configuration write that was refused is otherwise
invisible until the arithmetic comes out wrong and then it looks like an
arithmetic defect; load four ECC-checked weight words through
`W_DATA_LO`/`W_DATA_HI`; check `CNT_SEC` and `CNT_DED` are zero, because
a clean image must not produce an ECC event; enable. Then six frames,
each injected as its spikes, a TICK and a SYNC, and read back until that
frame's barrier returns.

**What is in the loop:** Ibex, the boot ROM, the system fabric, the APB
bridge, the peripheral slot decode, the serial transport, the frozen
die's register bank, its ECC-checked weight loader, its LIF datapath,
its event queues, the parallel AER pins inbound and the serial `EVQ_OUT`
register outbound, and the SoC's own two queues.

**What is checked:** the output stream, event for event and in stream
order — six spikes and six barrier echoes, twelve words; then **the
whole neuron state file**, `V` and `R` for all eight neurons, which is
strictly stronger than the spike stream because it catches an error that
happened to cancel; then that nothing was lost — the die's
`CNT_EVQ_OVF` and `CNT_AXON_OOR`, the SoC's injection-drop counter, and
the interrupt cause's fault bits, all zero; and finally that the
hardware's OWN count of events delivered and drained (22 and 12) agrees
with the stream the program collected, which is a second path to the
same conclusion.

### 7.3 The barrier is what makes the stream self-delimiting

The read loop has **no timing knowledge at all**. It reads until the
SYNC it injected comes back, and `docs/10` section 7.1 is why that is
legitimate: a consumed SYNC means every prior event is fully processed
and the barrier is echoed downstream. The die echoes the consumed word,
so the barrier carries its own frame number and the program can label
frames without counting spikes.

> **THIS IS THE RETURN ON PAYING 176 CYCLES TO INJECT A SYNC OVER THE
> SERIAL PORT.** The pins cannot carry the barrier in either direction
> (section 4). Without it the program would have to know how many spikes
> each frame produces — which is the answer it is trying to check — or
> wait a fixed time, which is a test that passes for the wrong reason on
> a slow day.

---

## 8. What it costs, measured

### 8.1 One register access

**176 clock cycles**, from the cycle `req` is asserted to the cycle
`rvalid` returns **[fact, `hw/soc/tb/cocotb/test_soc_npu.py::test_the_frame_costs_what_the_protocol_says_it_costs`,
and independently in a standalone Icarus run]**. Of that, **171** is the
serial frame itself and the rest is the slave's own sequencing.

The protocol's floor is arithmetic on `pilot_top.v` section 2: 40 SCK
cycles plus one period of select setup (H2) plus one of inter-frame gap
(H3), at `SER_HALF` clock cycles per half period, is
`(40 + 1 + 1) * 2 * 2 = 168` cycles. The test asserts the measurement
lies between that floor and the floor plus 24, so the number in this
document is an observation and not a design intent.

### 8.2 The grant discipline, and the fabric consequence nobody had met

The node window **accepts one request at a time and withholds `gnt`
otherwise**, which is `soc_bus.v` rule S4 and is exactly what
`soc_apb_bridge.v` already does. The difference is the duration: three
cycles there, 176 here.

> **AND THAT MAKES A PROPERTY OF THE FABRIC VISIBLE FOR THE FIRST TIME.**
> `soc_bus.v`'s round-robin arbiter picks a winner BEFORE it looks at the
> target's grant. Its no-starvation property F9 has "every slave ready"
> in its antecedent for exactly this reason — `docs/39` section 8 defect
> 3 records the counterexample that put it there. So while one master is
> being refused by a slow slave, **the other master is not granted
> either.**

In this SoC that costs nothing measurable, and the reason is a property
of the CORE rather than of this block: Ibex is a two-stage machine with
no cache, so **a load stalls the pipeline until its data returns**
(`docs/50` section 5.2 measures 0.9714 cycles of execution per cycle of
RAM latency), and no second request to this window is ever issued while
the first is in flight. `md_req_i` is low for the whole frame and the
instruction port fetches normally.

**"Cannot happen because of the master we happen to have" is not a
property of a slave** — that is `docs/39` section 8 defect 4 in one line
— so it is reported here as a measurement of this SoC and not as a
property of the fabric. A future master that pipelines accesses into
this window would pay it, and the fix would be to buffer up to
`2*MAX_OUT` requests in the slave rather than to change the arbiter.

### 8.3 The whole program

| `hw/soc/flow/sim_soc.sh`, whole SoC | `docs/50` baseline | with the NPU |
|---|---:|---:|
| checks run | 0x16 (22) | **0x1B (27)** |
| fail mask | 0 | **0** |
| watchdog stage 1 (NMI) at cycle | 174,128 | **174,208** |
| **core asleep after** | **185,443** | **213,971** |
| console characters decoded | 587 | **760** |
| framing errors | 0 | **0** |
| watchdog stage1 / stage2 / stage3 | 1 / 0 / 0 | **1 / 0 / 0** |

**[fact, `hw/soc/out/sim-soc/sim.log`]**

**+28,528 cycles, +15.38 %.** Two things are worth separating out of
that number.

**THE BLOCK IS FREE UNTIL SOFTWARE TOUCHES IT, AND THAT WAS MEASURED
BEFORE THE CHECKS WERE WRITTEN.** With `soc_npu` instantiated, the sixth
fabric port decoded and the interrupt wired, and with the program
unchanged, the run was **185,443 cycles — identical to `docs/50`'s, to
the cycle** **[fact]**. The interrupt mask resets to zero and both event
engines reset disabled, so nothing the block does is visible until a
register is written. That is the same discipline `docs/41` records for
BUSSTAT and the reason `soc_top.v` could grow a block without moving the
invariant.

**ABOUT HALF THE DELTA IS THE CONSOLE.** The program prints 173 more
characters and `soc_uart.v` has one holding register, so at 80 clocks
per character that is **13,840 cycles [estimate, a measured character
count times a measured bit period]**, leaving about **14,700** for the
work: roughly 50 node-window accesses at 176, 18 engine frames at 172,
16 pin events at 4, and the CPU's polling in between.

**The new invariant is 213,971** and every hardening document after this
one should use it. The `docs/38` minimal-system run is unchanged at
131,718 cycles **[fact]**, because nothing in this work is on that
platform.

---

## 9. The interrupt, and what one fast line actually cost

`docs/40` section 3.3 decided against a PLIC on the strength of headroom:
Ibex's fifteen fast local interrupts cover thirteen sources with two
spare. Spending one here would be a real decision against that budget.

**It does not spend one.** NPUCFG was one of the thirteen sources that
document assigned — source number 24, fast line 12, `mcause 0x8000001C`,
vector `mtvec+0x70` — before this block existed. This work moves that
slot from `reserved` to `implemented`. **Lines 13 and 14 are still
unassigned**, and `test_soc_npu_guards.py` derives the spare set from the
generated map rather than asserting it **[fact]**.

**One line is enough for any number of nodes**, because the cause
register and not the wire says what happened:

| Bit | Meaning | Kind |
|---|---|---|
| 0 EVT | the capture queue is not empty | **level** |
| 1 ERR | the die's ERR pin | **level** |
| 2 SEC | the die's SEC pin, sticky at the die | **level** |
| 3 DED | the die's DED pin, sticky at the die | **level** |
| 4 TMR | the die's TMR pin, sticky at the die | **level** |
| 5 INJ_OVF | an `EVQ_IN` write was refused by a full queue | **sticky, W1C** |
| 6 FETCH_ER | an injection-queue fetch expired | **sticky, W1C** |

**The mix of levels and stickies is a decision and not untidiness, and
`docs/50` section 5.1 is the precedent.** A level has state behind it,
so the way to clear it is to fix the state — drain the queue, write the
die's `FAULT_CLR`. A refused write has no state behind it: it is an
event, and an event that is not latched is an event nobody can observe.
Writing 1 to a level bit is accepted and does nothing, and
`test_evt_is_a_level_and_says_so` asserts exactly that, because the
opposite convention is the easy mistake and it produces a driver that
loses events.

**Five of the seven bits come off the die's pins**, not off a polled
register. `pilot_top.v` section 1's four fault pins exist so "every
hardening event is visible on a scope with no host software"; inside an
SoC they are visible with no 176-cycle frame either. That is the
`docs/08` section 2.3 fault-visibility convention paying for itself in a
place it was not designed for.

**Check 27 takes the interrupt**, on line 12, at its own vector, and
checks the marker and `mcause` separately — `docs/40` section 6.1's rule
that reading `mcause` alone proves nothing about vectoring. It then
checks that the event is still in the queue, because the handler masked
the line rather than consuming anything, and that draining the queue
clears the level. That last assertion is the whole claim about what kind
of bit EVT is.

---

## 10. Verification

### 10.1 cocotb

| Suite | Tests | Result |
|---|---:|---|
| `test_soc_npu` | **21** | **21 pass** **[fact]** |

**The device under test contains the frozen pilot.** Every register value
in that suite travels a real 40-bit serial frame into `hw/rtl/pilot_top.v`
and back, and every event travels either the parallel AER pins or that
same frame. It is not a model of the die.

No expectation is read out of `soc_npu.v` except the port names. Node
register offsets, reset values and field positions come from
`sw/golden/regmap_gen.py`; the region base comes from
`sw/golden/memmap_gen.py`; the slave contract is `soc_bus.v`'s S1-S4,
quoted in the docstrings that test it; the frame format and the host
obligations are `pilot_top.v` section 2; and the inference answer is
`sw/golden/lif_core.py`.

`test_every_reset_value_survives_the_transport` walks the whole map — 26
registers — because a frame that was one bit short, one bit long, sampled
on the wrong edge, or misaligned by a deselect the die never saw would
corrupt SOME of them and not others. Two registers are excluded and the
reasons are normative rather than convenient: `CFG_NEUR` and `CFG_AXON`
report the elaborated geometry under `pilot_top.v` deviation D2, and
`N_DATA` has no reset value at all because `docs/10` section 3 says the
neuron state memory is UNDEFINED after reset.

**Mutation evidence, and four of the fourteen were not caught.**
Fourteen mutations against scratch copies; the Makefile exposes
`SOC_NPU_SRC` and `SOC_NPU_SER_SRC` for exactly this.

| Mutation | Result |
|---|---|
| `SER_MISO` sampled at the first cycle of the high half | caught, 8 tests |
| the frame is 39 bits | caught, 10 tests |
| a sub-word write is widened instead of refused | caught, `test_a_partial_write_is_refused` |
| every node index decodes to node 0 | caught, `test_reserved_addresses_in_the_window_are_bus_errors` |
| offsets above the die's 7-bit map are accepted | caught, the same test |
| a SYNC is strobed onto the AER pins | caught, 6 tests |
| a refused `EVQ_IN` write is not recorded | caught, 2 tests |
| the interrupt ignores the mask | caught, `test_the_line_is_the_cause_and_the_mask` |
| EVT is a sticky rather than a level | caught, 2 tests |
| `CTRL.FLUSH` also clears the sticky record | caught, `test_flush_empties_the_queues_and_keeps_the_record` |
| **the window grants while a frame is in flight** | **NOT caught — a real gap, now closed. Section 10.1a** |
| **the inter-frame gap H3 is dropped** | **not caught by the suite; caught by the induction proof** |
| **the select setup H2 is shortened** | **not caught by anything, and it is not a violation** |
| **a drained word is captured without checking VALID** | **not caught; the condition is unreachable in this SoC** |

**[fact, section 17 reproduces it]**

#### 10.1a The gap, which is the most useful result in this section

`gnt_o = req_i` — a window that grants a second request while the first
is unanswered — **passed all 21 tests.** A grant the fabric records owes
an `rvalid` the slave never sends, which underflows `soc_bus.v`'s
per-slave ownership queue; it is one of the worse things a slave can do.

The reason it survived is a defect in the test, not in the suite's
coverage: `test_gnt_is_withheld_while_a_frame_is_in_flight` **dropped
the request as soon as it saw the grant**, so it never presented the
slave with the opportunity to misbehave.

Rewriting it took two attempts, and the second one is the interesting
part. Holding the request high and requiring **one grant** fails on the
CORRECT design, because a grant and an `rvalid` may legitimately
coincide — they belong to different transactions, and
`soc_apb_bridge.v`'s header already says so of itself. **The property is
an OUTSTANDING COUNT and not a grant count**: grants minus responses
must never exceed one. Stated that way it passes on the design and
reports **523 outstanding** on the mutation.

> **A TEST THAT NAMES THE PROPERTY IT CHECKS AND DOES NOT SET IT UP IS
> WORSE THAN NO TEST**, because the name is read as coverage. This is the
> twelfth entry for `docs/41` section 6.6's list and the first in this
> work.

#### 10.1b The three that were not gaps

**H3 is caught by the proof and not by the simulation, and the depths
say why.** The bounded check runs to depth 30 and one frame is 171
cycles, so **no bounded check that finishes in reasonable time reaches a
second frame** — and H3 is entirely about the gap between two. The
k-induction proof has no such limit and fails on the mutation at the
`g_h3` clause. That is the division of labour the two tools are for, and
it is worth recording that the simulation could not have found it: with
`SER_HALF = 2` the shortened gap still leaves three cycles of deselect,
and the die needs one.

**The H2 mutation is not a violation.** Shortening the SETUP state from
two half periods to one still leaves five cycles between the select
falling and the first sampled clock edge, because **the first bit's own
low half supplies the rest of the setup**. The obligation `pilot_top.v`
section 2 states is about the interval, not about a state, and the
property is written over the interval — so both designs meet it and
neither tool should flag it. A mutation that changes no observable
behaviour is a statement about the design, and it is recorded rather
than quietly dropped.

**The VALID check on a drained word guards a condition this SoC cannot
produce.** The drain engine only starts when `AER_OUT_VLD` is high, and
nothing in this SoC pops the die's holding register behind its back —
`aer_out_ack` is tied low. The check is there because
`regmap/regmap.yaml`'s `EVQ_OUT` contract permits a read with VALID
clear, and the module's comment says so. **It is unreachable, so it is
uncovered, and calling that a coverage hole would be wrong** — it would
be a hole if `aer_out_ack` were ever connected.

### 10.2 Formal

| Job | bmc | prove, k-induction | cover | prove at `HALF = 3` |
|---|---|---|---|---|
| `soc_npu_ser` | **PASS**, depth 30 | **PASS**, depth 16 | **PASS, 5 of 5 reached**, depth 220 | **PASS** |

**[fact, `hw/soc/formal/soc_npu_ser_*/PASS`]**

**AND `soc_bus`'s PROOF WAS EXTENDED, BECAUSE THIS WORK CHANGED A PROVED
BLOCK.** `docs/50` section 8.1 found `hw/soc/formal/soc_bus.sby` failing
since `docs/47` — that document changed `soc_bus.v` and did not re-run
the proof — and the lesson is one document old. Adding a sixth slave
port breaks the property set immediately and loudly: the ghost
occupancy arrays, the one-hot decode, the response-balance count and the
error-slave index are all written per port, and `bmc` fails at step 2 on
"no response to a master that has nothing outstanding". Every one of
them is extended, F2a and F2b gain the NPU region's decode in both
directions against the generated map constants, and **the cover set
gains a witness for the new port** — without it the sixth slave would be
covered by every assertion and witnessed by none, which is the vacuity
`docs/09` section B.1 makes a red result.

| `soc_bus` | bmc, depth 24 | prove, k-induction | cover, depth 24 |
|---|---|---|---|
| before | PASS | PASS | PASS, 16 of 16 |
| **six ports** | **PASS** | **PASS** | **PASS, 17 of 17** |

**[fact]**

The property set is `pilot_top.v` section 2 expressed over this module's
PORTS: the frame format (P1, P2, P3), the three host obligations (H1,
H2, H3) and one the pilot does not number (H4). Nothing in it restates
the state encoding of the module it checks, except the strengthening
invariants I1-I9, and each of those is a real check as well as a proof
aid — the discipline `docs/39` section 5.5 records for the fabric.

**H4 is the property that is not in `pilot_top.v`'s list, and that is why
it is worth having.** H1 is about the clock RATE; H4 says `SER_MOSI` is
stable for at least `HALF` cycles before every rising edge, which is the
setup requirement the die's two-flop MOSI synchronizer imposes on the
DATA. Section 2 of that file states H1, H2 and H3 and not this, and an
obligation nobody wrote down is an obligation nobody checks.

**Two parameter points, because H1's whole content is a rate.** `HALF`
2 is the default and is the documented limit; `HALF` 3 is what a bench
driving real silicon over an independent clock would need, and a proof
at one rate says nothing about another.

### 10.3 The Python guards

`sw/tests/test_soc_npu_guards.py`, 15 tests **[fact]**. The half a
simulation cannot do: that `hw/rtl/` is unmodified against the index and
every pinned file is present; that no copy of `pilot_top` exists under
`hw/soc/`; that every flow reads the pilot from the frozen directory by
path; that every die-side offset in `soc_npu.v` is a generated NAME and
not a number; that `hw/soc/rtl/soc_npu_regs.vh` has **no include guard**
and `hw/rtl/npu_regs.vh` still has one; that the region has a fabric port
and the fabric decodes it; that the interrupt reaches the generated line
constant; that the vector table has a real stub for id 28; and that the
spare-line count is still two.

---

## 11. Measured area

Same recipe as `docs/39` section 6 and `docs/40` section 9, deliberately:
Yosys `stat -liberty` on `ihp-sg13g2` at the typical corner, `abc` with
the same driving cell, the same load and the same 20 ns delay target.
Gate equivalent = `sg13g2_nand2_1` = 7.2576 um2. The Ibex reference is
**275,682.6198 um2**.

| Block | Cells | Flops | Area, um2 | kGE | % of Ibex |
|---|---:|---:|---:|---:|---:|
| `soc_npu_ser`, the transport | 581 | 134 | **10,773.5670** | 1.484 | 3.91 % |
| `aer_fifo` 16 x 8, one of the two queues | 671 | 186 | **15,465.3408** | 2.131 | 5.61 % |
| **`soc_npu`, the connection only** (pilot black-boxed) | **2,723** | **717** | **57,805.4988** | **7.965** | **20.97 %** |
| `pilot_top` at 8 x 8, this recipe | 9,560 | 1,294 | **152,717.1786** | 21.042 | 55.40 % |
| **`soc_npu`, the whole subsystem** | **12,421** | **2,008** | **209,739.0834** | **28.899** | **76.08 %** |
| `soc_bus`, six ports | 868 | 55 | **10,928.8872** | 1.506 | 3.96 % |
| `soc_bus`, five ports, re-measured as a control | 812 | 49 | **9,917.3592** | 1.366 | 3.60 % |
| `soc_fabric_meas`, six ports | 1,074 | 149 | **17,355.4920** | 2.391 | 6.30 % |

**[fact for every measured row; the percentages are arithmetic on them]**

Four readings.

**THE SIXTH FABRIC PORT COSTS +56 CELLS, +6 FLIP-FLOPS AND 1,011.53 um2
— 0.37 % OF THE CPU** **[estimate, the difference of two measurements]**.
The six flops are checkable arithmetic rather than a number to be
believed: `soc_bus.v` keeps one response-ownership queue per slave, four
entries of one bit plus a two-bit write index, so a port is exactly six.

**THE CONTROL IS NOT `docs/40`'s PUBLISHED FIGURE AND THE DIFFERENCE IS
REPORTED.** That document measured the five-port fabric at 808 cells and
9,688.29 um2; re-measuring the same configuration at HEAD gives **812 and
9,917.36**. `soc_bus.v` has changed since — `docs/47` section 5 added
`issue_en` — so the two are not the same file, and `docs/50` section 2.2
is the reason a control that is not byte-identical is measured rather
than assumed.

**THE CONNECTION IS MEASURED DIRECTLY AND THE SUBTRACTION AGREES WITH IT
TO 1.4 %.** Black-boxing `pilot_top` gives 57,805.50 um2; subtracting the
pilot from the whole subsystem gives 57,021.90. The two are independent
and their agreement is what licenses quoting either.

**MORE THAN HALF THE CONNECTION IS THE TWO QUEUES.** 2 x 15,465.34 =
30,930.68 um2, **53.5 %** of it; the transport is 10,773.57, **18.6 %**;
the two bus faces, the event engine and the registers are the remaining
**27.9 %** **[estimate, arithmetic on measured rows]**. The queues are
`hw/rtl/aer_fifo.v` — the proved queue the die itself uses, with its
entry parity, its pointer voting and its drop counter — and they are
expensive because they carry that protection at eight entries of
seventeen stored bits each. **A cheaper queue was available and was not
taken**: the alternative is a second set of pointer, parity and drop
semantics in this repository, and `docs/50` section 5.1 is four pages on
how hard those are to get right once.

**What the numbers do not say.** No frequency was measured for any of
this RTL. None of it has been through STA at any corner or through
place-and-route, and `soc_npu` is 76 % of Ibex by cell area, so the
floorplan question `docs/48` opened is now a larger one. `docs/47`'s
sign-off does not include this block.

---

## 12. Descriptor rings: not built, and priced

`docs/08` section 3.1 sketches "per-node SRAM apertures + descriptor
rings" for this window. The apertures are built. The rings are not, and
the reason is not that they are hard:

> **A DESCRIPTOR RING IS A BUS MASTER.** `soc_bus.v` has two master
> ports, hardcoded, with a two-master round-robin arbiter whose fairness
> property F9 is written for two and whose response-ownership queues are
> sized `2 * MAX_OUT` for two. A third master is a fabric change, a
> re-proof, and a re-measurement of a block that four documents have
> hardened. That is a document of its own.

**And at this scale it would save nothing.** A ring replaces "one
register access per event" with "one memory write per event, plus a
doorbell, plus a DMA engine". The measured per-event CPU cost today is
one APB write in and one APB read out — about 8 cycles each **[estimate,
the bridge's three-cycle minimum plus the fabric]** — against the
**176-cycle serial frame** the drain engine already performs in the
background. **The CPU is not the bottleneck; the transport is**, and a
ring does not touch the transport.

**The reversal condition, stated so this can be reopened rather than
re-litigated.** Build the ring when **either** becomes true: the event
rate is high enough that the CPU's per-event bus cost is a measurable
fraction of a frame time — which needs the workload `docs/50` section
7.4 says is still unsized — **or** the SoC gains a bus master for some
other reason, at which point the fabric cost is already paid.

---

## 13. Defects found, all four in this work

Recorded because each is a trap the next block would otherwise walk into,
and because three of the four are the same mistake in three places.

**1. A state that both starts a transaction and waits for it starts a
second one on the way out.** `soc_npu_ser.v` drops `busy_o` and raises
`done_o` at the SAME edge, which is correct and is what a caller wants.
Both FSMs above it were written with one state that issued the start and
watched for the completion, so in the completion cycle the start
condition — "not busy, transport free" — is true again and fires.

The two symptoms looked nothing alike. On the **event engine** the
spurious frame is a read of `EVQ_OUT`, which POPS, and its result reaches
an engine that has moved on: **one barrier echo was duplicated in a
twelve-event stream** and a stray pop was left in flight behind it. On
the **node window** the spurious frame is a repeat of the same access
with the same captured payload — harmless in itself — but it is still
owned by the window, so its completion is mistaken for the response to
the NEXT access: **a read immediately after a write to the same register
returned zero**, which is what a write frame's MISO carries. And it only
appeared when the two accesses were close together, because anything
slow in between let the spurious frame drain first. The debug print that
was supposed to diagnose it did four UART writes and therefore could not
reproduce it.

Both are fixed by splitting issue and wait into separate states, and both
files say so where the states are declared.

**2. A test that names the property it checks and does not set it up.**
Section 10.1a. `gnt_o = req_i` survived all 21 tests because
`test_gnt_is_withheld_while_a_frame_is_in_flight` dropped the request on
the first grant.

**3. A cocotb driver that starts looking for the grant on the NEXT
cycle.** `gnt_o` is combinational on `req_i`, so this slave grants in the
same cycle when it is idle — rule 1's "the same cycle or any number of
cycles later". A driver that samples from the following cycle misses it,
holds `req` high through the whole frame, and is then granted a SECOND
transaction the moment the first response returns. **Measured: one read
became two frames and 350 cycles where the design does one and 176.**
Every symptom of it read as a design defect — a doubled grant count, a
frame twice as long as the protocol allows, and an inference that came
out wrong — and all three were one line in the testbench. This is the
same class as `docs/40` section 7.5's three testbench findings.

**4. A ghost counter that observes a pin through its own registered
copy sees the change one cycle late.** The first version of
`soc_npu_ser_props.v` measured "cycles since `SER_SCK` last changed" in a
register and compared it against `HALF`. At the very cycle a dwell
property wants the OLD level's dwell it is already reporting the new
one's, so the bound reads 1 where the design held the level for `HALF`.
Two further variants of the same mistake followed — a counter parked at
`0xFFFF` to mean "unbounded" that a property then added one to, wrapping
to zero and reading as "the pin just changed". **Every dwell property is
now written over `$past` of the pin at fixed offsets**, which has no lag
and needs no invariant to tie it to anything, and the single registered
copy that survives is used only to NAME an edge.

Defects 3 and 4 are worth generalising together: **both were an
observer, not a design, and both presented as a design defect with a
plausible mechanism.** The habit that resolved them was the same one
`docs/38` section 7.5 draws at length — measure the thing directly, in a
second harness, before believing the first.

---

## 14. What is not built

1. **No hardening of anything this work adds, except what it inherited.**
   The two queues are `aer_fifo` and carry its entry parity, pointer
   voting and drop counting. The event engine's state, the transport's
   shift register, the window's captured request and every register in
   the NPUCFG block have **no protection at all**. `aer_fifo`'s
   `ptr_mismatch` and `par_err` outputs are brought out of both
   instances and connected to nothing, because this SoC has no
   fault-counter block of its own and inventing one here would put
   NPU-only telemetry outside BUSSTAT, which `docs/41` owns.
2. **No second node.** `N_NODES` is a parameter, the window decodes all
   sixteen NODE_ID values, and fifteen of them fault.
3. **No descriptor rings.** Section 12.
4. **No QSPI weight path.** `docs/10` section 9's `W_BASE` is not
   implemented in the pilot at all and there is no QSPI controller;
   weights are loaded a register at a time.
   *Corrected 2026-09-05:* there is a QSPI controller, and the
   bring-up program's check 30 loads the same weight words from a
   modelled flash through it and runs this inference with them
   (`docs/66-qspi-flash-controller.md`). The words still enter the
   node a register at a time, because that is the die's only weight
   port; what changed is where they come from.
5. **No multi-pass sequencing.** `PASS_TILE_OFF` is written once, to
   zero. `docs/10` section 9's E9 tiling is exercised by the pilot's own
   suite and by nothing here.
6. **No place-and-route, no timing, no gate-level simulation and no
   fault injection** on any of this. Section 11's last paragraph.
7. **No fault-injection campaign through the connection.** `docs/16`
   measures upsets in the die through its own pins; nothing measures
   what an upset in the transport or the event engine does to an
   inference.
8. **The `SCRUB_STB` pin is driven and never used.** `CTRL.SCRUB` pulses
   it, and no test in this repository uses that path from the SoC side.

---

## 15. What the checkers do not cover

Stated separately from section 14, because "not built" and "built but not
checked by the thing that looks like it checks it" are different failures
and `docs/41` section 6.6 now lists eleven instances of the second.

- **The cocotb suite never drives two masters**, because `soc_npu` has
  one slave port. Section 8.2's arbitration consequence is a whole-SoC
  property, measured there by a cycle count, and no property anywhere
  states it.
- **Nothing injects an upset into this work.** The queues carry
  `aer_fifo`'s protection and no test provokes it; the bounded wait on
  an injection fetch exists, is reachable in principle, and is exercised
  by nothing.
- **The formal job proves no liveness.** A transport whose tick counter
  never reached its limit satisfies every assertion in the file, which is
  why the cover task is not optional and why the frame LENGTH is a
  measurement in the cocotb suite rather than a proof.
- **The formal job cannot see the die.** It says what this module puts
  on the wire. Whether the die interprets it as intended is the cocotb
  suite's subject, and the MISO sampling point — the load-bearing timing
  argument in `soc_npu_ser.v`'s header — is checked only by reading every
  register's reset value back through the transport.
- **The formal job runs at two parameter points**, `HALF` 2 and 3.
  Nothing sweeps `N_NODES`, the queue depths, or the geometry.
- **The end-to-end demonstration is one inference at one geometry.**
  8 x 8, one node, no tiling, no ECC injection, no upset. The pilot's own
  suite covers the die's behaviour under all of those; this one covers
  the connection under none of them.
- **`test_soc_npu_guards.py` simulates nothing.** It checks that
  constants are generated and that the frozen directory is clean. A
  correctly generated map wired to the wrong port would pass every test
  in it.
- **The whole-SoC run exercises the arbiter only incidentally**, which is
  unchanged from `docs/39` section 10 and is now less true than it was:
  the NPU is the first slave slow enough to matter and nothing stresses
  it deliberately.
- **Nothing has run at gate level or with back-annotated timing.** Every
  cycle count here is RTL simulation.

---

## 16. Files touched outside `hw/soc/`

`docs/34` section 2 pins the pilot by git blob hash of the files in
`hw/rtl/` and section 5 lists the flow configs. **None of the following
is in either set, and `hw/rtl/` itself is unmodified** **[fact,
`test_soc_npu_guards.py::test_the_pilot_directory_is_unmodified_against_the_index`]**.

| File | Change |
|---|---|
| `regmap/memmap.yaml` | additive: `port: npu` on the NPU region, two `status` promotions. No frozen base, size, slot, source number, line or device id moved |
| `regmap/generate.py` | a fourth output, `hw/soc/rtl/soc_npu_regs.vh`, and a `guard` argument to the Verilog emitter. **Its `hw/rtl/npu_regs.vh` output is byte-identical** |
| `sw/golden/memmap_gen.py`, `docs/memmap-soc.md`, `docs/regmap-npu.md`, `hw/soc/rtl/soc_pnp_rom.vh` | regenerated |
| `sw/tests/test_soc_npu_guards.py` | new, 15 tests |
| `sw/tests/test_soc_synthesis_guards.py` | the whole-SoC elaboration guard reads the NPU subsystem and the frozen pilot |
| `docs/51-npu-integration.md` | this document |
| `docs/00-index.md` | one row, which `sw/tests/test_doc_links.py` requires |
| `.gitignore` | one entry: the SymbiYosys working directories of the new formal job. Same rule the file already applies to `soc_bus` and the same non-argument `docs/38` section 11 makes |

Everything else is under `hw/soc/`. `hw/soc/{ext,tools,gen,genp,out,pnr/runs}`
remain gitignored.

**Seven files in `hw/rtl/` are read and instantiated** — `pilot_top.v`,
`lif_core.v`, `aer_fifo.v`, `scrub.v`, `secded_enc.v`, `secded_dec.v`,
`tmr_voter.v` — plus `npu_regs.vh` through an include path. That is the
rule `hw/soc/flow/sim_soc.sh` already followed for `tmr_voter.v` and
`ibex_sources.sh` for the two SECDED files, applied to the whole
submission.

---

## 17. Reproducing this

```
python regmap/generate.py                       # four outputs, one source
python regmap/generate_memmap.py
.venv/bin/python -m pytest sw/tests -q

hw/soc/flow/sim_soc.sh                          # 27 checks on the real SoC

cd hw/soc/tb/cocotb && make -f Makefile.soc_npu
cd hw/soc/tb/cocotb && make -f Makefile.soc_npu SER_HALF=3 \
    SIM_BUILD=sim_build_soc_npu_h3 COCOTB_RESULTS_FILE=results_soc_npu_h3.xml

cd hw/soc/formal && make npuser                 # bmc, prove, cover, prove_h3

hw/soc/flow/syn_soc.sh soc_npu_ser
hw/soc/flow/syn_soc.sh soc_npu
hw/soc/flow/syn_soc.sh soc_bus
hw/soc/flow/syn_soc.sh soc_fabric_meas
```

A mutation is a scratch copy and one variable:

```
cd hw/soc/tb/cocotb
SOC_NPU_SRC=/tmp/mutated_soc_npu.v make -f Makefile.soc_npu
SOC_NPU_SER_SRC=/tmp/mutated_soc_npu_ser.v make -f Makefile.soc_npu
```

---

## 18. What the next block should be

Three candidates, and the argument is not close.

**Fault injection through the connection.** `docs/16` measured the die's
upset response through its own pins and `docs/42` measured the core's.
Between them sits a transport with an unprotected 40-bit shift register,
an event engine with an unprotected state, and two bus faces — and an
upset in any of them corrupts an inference in a way that looks like an
arithmetic defect. **This is the first block in the SoC that sits
between two measured things and is itself unmeasured**, and the campaign
already exists: `hw/soc/flow/fi_core.sh` and the `docs/16` method need a
new fault port and a new workload, not a new method.

**Hardening the connection.** Section 14 item 1 is a list of unprotected
state in a part whose whole claim is measured fault tolerance. But
**hardening before measuring is the mistake `docs/38` section 10 item 4
names**: the campaign's answer determines what needs protecting, and
protecting the wrong thing costs area and buys nothing.

**Place and route with the NPU in it.** Section 11 measures `soc_npu` at
76 % of Ibex by cell area, which changes the floorplan question `docs/47`
and `docs/48` left open into a different question. It is real work and it
is not urgent: `docs/50` section 7.3 has just recommended against the one
mechanism that moved the sign-off number, so there is nothing waiting on
a new layout.

**The recommendation is the campaign**, and hardening immediately after
it. The campaign can invalidate a decision this document has just taken —
if an upset in the transport can corrupt a weight word silently, then
`W_DATA_HI`'s commit needs a read-back that the bring-up sequence does
not currently do — and neither of the other two can.

One thing should be done before any of them, and it is small: **the
whole-SoC invariant is now 213,971 cycles**, and every document after
this one should quote that number rather than `docs/50`'s.
