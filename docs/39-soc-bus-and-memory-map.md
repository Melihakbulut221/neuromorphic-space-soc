# 39 — The system bus and the memory map: freezing one, and deciding what the other actually is

`docs/38-ibex-bringup.md` ends with "**Nothing is integrated.** No bus, no
memory map, no NPU connection. That is the next step." This document is
that step. It freezes the memory map as a machine-readable source with a
generator, decides what the interconnect is, builds it, and runs the
bring-up program through it.

Two things constrain the answer before any design work starts.

The first is `docs/08-gr801-datasheet-notes.md` section 3.1, which
proposes a memory map in GRLIB/NOELVSYS style — AHB plus a single APB
bridge, plug-and-play tables at `0xFFFFF000` and bridge + `0xFF000`, RAM
at 0, ROM at `0xC0000000`. Section 4 item 1 says freezing it is the first
task. That skeleton was written from Gaisler conventions when the CPU was
still unchosen.

The second is that the CPU is now chosen and it is not NOEL-V. Ibex has
two independent simple request/grant/response ports, an instruction port
and a data port. It has no AHB, no AXI and no concept of a burst. So
somebody has to decide what the interconnect actually is, and
"`docs/08` says GRLIB" is not by itself a reason.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** = an
intention with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash and the shuttle closes 2026-09-21. Everything here is
under `hw/soc/`, plus one new generator in `regmap/`, one new test in
`sw/tests/`, one generated document, and three lines across `conftest.py`
and `pytest.ini`. Nothing in `hw/rtl/`, `hw/tb/`, `formal/`, `tt/` or
`hw/openlane/` was modified. Section 11 lists every file touched and why
none of them is in the frozen set.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| Is the memory map frozen? | **Yes.** `regmap/memmap.yaml` is the single source; six files are generated from it, and `sw/tests/test_memmap.py` fails if any is stale **[fact]** |
| Is the interconnect AMBA AHB? | **No, and it is not claimed to be.** Section 3 |
| Is it AMBA APB anywhere? | **Yes, at the peripheral boundary,** and that part is formally proved compliant. Section 4 |
| Did AHB lose on area? | **No.** The AHB path measures 17,154.32 um2 against 14,807.32 for what was built — a difference of **0.85 % of the CPU** **[fact]**. Area is not why. Section 6 |
| Then why? | Verification cost and claim honesty. AHB-Lite is also structurally wrong for two masters, which is a design fact and not a preference. Sections 3.3 and 4 |
| Does the bring-up program run on it? | **Yes.** All eleven original checks plus three new ones, out of the boot ROM, through the fabric, with the console decoded off a real serial line: 165,304 cycles, 403 characters, zero framing errors **[fact]**. Section 5.4 |
| Is the fabric verified? | cocotb: 13 tests on the fabric, 11 on the bridge, all passing, with mutation evidence **[fact]**. Formal: section 5.3 |
| Is any of it hardened? | **No.** No ECC, no scrubbing, no TMR, no bus error latch, no interrupt controller. Section 9 |

---

## 2. The memory map, frozen

### 2.1 It is a file, not a table in prose

`regmap/memmap.yaml` is the map. `regmap/generate_memmap.py` emits six
things from it **[fact]**:

| Output | Consumer |
|---|---|
| `docs/memmap-soc.md` | readers |
| `sw/golden/memmap_gen.py` | the Python test suite and the cocotb suites |
| `hw/soc/rtl/soc_memmap.vh` | the RTL's address decoder |
| `hw/soc/rtl/soc_pnp_rom.vh`, `hw/soc/rtl/soc_apb_pnp_rom.vh` | the device table contents |
| `hw/soc/tb/sw/soc_memmap.h` | the bare-metal program |
| `hw/soc/tb/sw/memmap.ld` | the linker's `MEMORY` block |

This is the pattern `regmap/regmap.yaml` already uses for the NPU
register block, and it is a **second** generator rather than an extension
of the first for a specific reason: `regmap/generate.py` writes
`hw/rtl/npu_regs.vh`, and `hw/rtl/` is pinned by git blob hash in
`docs/34` section 2.1 for the duration of the shuttle. Two generators
with disjoint output sets is the cheapest way to guarantee this work
cannot write into the frozen directory.

The linker script matters more than it looks. `docs/38` section 7.5
defect 4 was a link-time accident that moved `_start` off Ibex's fixed
reset vector; the symptom was garbled console output rather than a crash,
and it cost a debugging session. The `MEMORY` block is now generated, so
the reset vector reaches the linker from the same source that reaches the
RTL and the tests, and nobody writes it down twice.

### 2.2 The two Ibex constraints are checked, not commented

`docs/38` section 7.5 defects 3 and 4 are properties of the core that a
memory map can violate on paper:

- **Ibex resets to `{boot_addr_i[31:8], 8'h80}`.** The offset is not
  free and the low byte of `boot_addr_i` is discarded. The generator
  refuses a `reset_vector_offset` other than `0x80`, refuses a boot
  region whose base has a non-zero low byte, refuses one that does not
  contain the reset vector, refuses one that is not executable, and
  refuses one that is not implemented — because a core that resets into
  the error slave cannot start **[fact,
  `regmap/generate_memmap.py`, `validate()`]**.
- **Ibex's `mtvec` is 256-byte aligned and vectored-only.** A handler
  written to any other address is silently truncated to the enclosing
  256-byte boundary. Every region base is therefore required to be
  256-byte aligned, so the map is never itself the reason a trap vector
  lands somewhere else.

`sw/tests/test_memmap.py` re-checks both from the generated Python
constants, independently of the generator that produced them.

### 2.3 The map

Ten regions, four implemented. Sixteen peripheral slots, two implemented.
The full table with provenance per row is `docs/memmap-soc.md`; the shape
is:

| Range | Block | Status |
|---|---|---|
| `0x00000000` + 64 KiB | System SRAM | implemented |
| `0x10000000` + 256 MiB | NPU fabric window | reserved |
| `0xC0000000` + 8 KiB | Boot ROM, reset vector at `0xC0000080` | implemented |
| `0xD0000000`, `0xD8000000` | QSPI XIP windows | reserved |
| `0xE0000000` + 64 KiB | CLINT | reserved |
| `0xF8000000` + 4 MiB | PLIC | reserved |
| `0xFE000000` + 16 MiB | RISC-V debug module | reserved |
| `0xFF900000` + 1 MiB | Peripheral bus bridge, 4 KiB slots | implemented |
| `0xFFFFF000` + 4 KiB | Device table | implemented |

These are `docs/08` section 3.1's proposed addresses, unchanged, with the
NOELVSYS frame (`grip.pdf` table 2293) and GR740's APB slot numbering.
The proposal was good and freezing it required no argument; what required
argument is what "AHB PnP at `0xFFFFF000`" means when there is no AHB,
which is section 7.

### 2.4 A decode discipline, enforced by the generator

Every region is a **naturally aligned power of two** and no two overlap.
That is not cosmetic: it is what makes address decode a prefix compare
(`addr & MASK == BASE`) rather than a pair of magnitude comparisons in
the address path of every access. The generator exits non-zero rather
than emit a map that cannot be decoded cheaply, and
`sw/tests/test_memmap.py` re-derives the masks from the sizes and checks
that the first, middle and last word of every region decode to that
region and no other.

**What that discipline does not do.** It says nothing about whether a
region is the right size, and nothing about whether the RTL decodes what
the map says. A 4 GiB RAM would pass every check in that file. Section
5.3 says where the second question is answered, and section 10 says where
neither is.

---

## 3. The interconnect decision

### 3.1 The options, stated fairly

**(a) Real AHB-Lite plus APB, with Ibex bridged onto it.** Closest to
`docs/08`'s wording and to GR801. Costs two bridges, an interconnect and
— because Ibex has two masters — an arbiter.

**(b) Ibex's native protocol as the internal fabric, with an APB-like
peripheral bus, and no AHB claim.** Smaller and simpler.

**(c) Something else.**

The recommendation is a form of (c) that is closer to (b) than to (a),
and the difference from plain (b) is the part that matters:

> **The internal fabric speaks Ibex's own request/grant/response
> protocol. The peripheral bus is real AMBA 3 APB, not "APB-like". There
> is no AHB in the SoC and none is claimed. Everything that GR801
> software would actually see — the memory map, the 4 KiB peripheral slot
> geometry, the peripheral register maps, the device table record layout
> — is mirrored.**

### 3.2 The argument, in the order the evidence supports it

**First: `docs/08` defines GR801-proximity at the software-visible
layer, and the fabric protocol is not in it.** Section 3's own preamble
says proximity "operationally means close to the documented
GRLIB/NOELVSYS conventions of section 2, which is what GR801 software
(GRBOOT-style loaders, GRMON-style tools, driver stacks) is built
against". Software sees addresses, register maps, slot geometry, and
discovery tables. It does not see whether the wires between the core and
the RAM are called `HTRANS` or `req`. Rows 6, 8-12, 17 and 20 of that
checklist — the memory map, the peripheral register maps, the slot size,
the endianness, the debug convention — are mirrored here and are
unaffected by the fabric choice. Row 1 is the only row this decision
touches.

**Second: AHB buys this project no IP reuse, and that is measurable
from its own survey.** `docs/03-cpu-and-ip-survey.md` selected the
peripherals. Every one of them is native to a different bus **[fact,
`docs/03` section 2.2]**: the Mohor CAN core is Wishbone, the OpenCores
and alexforencich I2C cores are Wishbone, `simple_spi` is Wishbone,
OpenTitan's `spi_host` is TileLink, `spacewire_reloaded` carries
AXI4-Lite wrappers. **Not one is AHB-native.** So every peripheral needs
a wrapper whichever bus is chosen, and an APB wrapper is smaller than an
AHB one. The usual argument for adopting a standard bus — an ecosystem
of ready slaves — does not apply to the ecosystem this project actually
picked from.

**Third: `docs/08` row 1 is internally inconsistent, and the
inconsistency is load-bearing.** It says "Single AHB-lite layer (CPU +
NPU DMA + debug masters)". **AHB-Lite has exactly one master by
definition.** That is the whole difference between AHB-Lite and AHB: the
Lite subset drops `HBUSREQ`/`HGRANT`/`SPLIT`/`RETRY` because there is
nothing to arbitrate. Three masters on an AHB-Lite layer is not a
configuration, it is a category error. The honest version of option (a)
is therefore either full AHB with an arbiter and split/retry, or
AHB-Lite behind a multi-layer interconnect — both materially larger than
what row 1 describes. Ibex alone already supplies two masters.

**Fourth, and this is the finding that actually decides it: AHB-Lite
cannot back-pressure a master without also stalling its outstanding
response.** On an Ibex-native port "your request was accepted" (`gnt`)
and "your response is here" (`rvalid`) are two separate wires. AHB folds
both onto `HREADY`. An arbiter that drives `HREADY` low at a master to
stop it starting a new address phase is simultaneously telling that
master its outstanding data phase has not completed. There are exactly
two ways out, and both cost:

- hand the bus over only when the current owner has no data phase in
  flight — no storage, but a dead cycle on every ownership change, and
  with an instruction port and a data port both busy that is roughly
  every other transfer;
- let the data phase complete after ownership has moved and **park the
  response in a register** until its owner is granted again.

The cost probe implements the second. **67 of the arbiter's 71
flip-flops are parking registers** **[fact]** — two copies of 32-bit
`HRDATA` plus `HRESP` plus a valid bit. That is not an implementation
detail; it is the price of putting a single-master protocol underneath a
two-master core, and it is the largest single line item in the AHB path.

**Fifth: protocol compliance is a claim, and this repository has to be
able to back its claims.** `docs/05-market-positioning.md` section 4 rule
5 makes fact/estimate discipline binding on public text. "AMBA AHB
compatible" is exactly the shape of claim that has to be true, and
nothing in this project's pinned toolchain is an AHB protocol checker.
Building an AHB fabric and calling it AHB, with no compliance evidence,
would be the seventh instance of a defect this repository has already
been bitten by six times — `docs/28-timing-recovery.md` section 4.4a,
`docs/23-tile-shape-decision.md`, `docs/34` section 8.5,
`docs/36-checker-closure.md`, and `docs/38` sections 8.2 and 7.4 — a
green result read as wider than what it examined. APB, by contrast, has
a three-state state machine and about eight rules, and section 5.3
proves them.

**What the area evidence says, since it is the argument that would
otherwise be assumed.** It says area is *not* the reason. Section 6.

### 3.3 What was given up, stated plainly

- **An external AHB master or slave cannot be attached without a new
  bridge.** If a future block arrives as AHB IP, one has to be written.
  The cost probe is a sketch of what that would look like and section 6
  is what it would cost.
- **GRMON-class tooling will not attach.** Gaisler's debug tooling speaks
  AHB plug-and-play over a debug link. This SoC's device table has
  GRLIB's record layout but the bus underneath is not AHB, and
  `docs/08` row 17 already chose standard RISC-V debug over the SPARC DSU
  anyway.
- **The same-slave restriction** of section 5.1 is a restriction on
  masters that AHB would not have imposed in the same form. It costs a
  dead cycle when a master changes target region.

---

## 4. Why APB is real here and AHB is not

The distinction is not "standard buses are bad". It is that a claim of
compliance costs what it costs to verify, and the two protocols are not
in the same class:

| | AMBA 3 APB | AMBA AHB-Lite |
|---|---|---|
| States in the transfer | 3 | pipelined address/data with `HTRANS` encoding, `HSIZE`, `HBURST`, `HPROT`, two-cycle `ERROR` |
| Outstanding transactions | none | one address phase over one data phase |
| Bursts | none | four types, wrap and increment |
| Masters | one, by construction | one, by definition — see section 3.2 |
| Compliance evidence available here | **a full k-induction proof**, section 5.3 | none in the pinned toolchain |

So APB is implemented as APB, with `PSEL`/`PENABLE`/`PADDR`/`PWRITE`/
`PWDATA`/`PSTRB`/`PRDATA`/`PREADY`/`PSLVERR`, wait states, and a proof
that the sequencing and stability rules hold. That is what makes the
peripheral register maps of `docs/08` section 3 rows 8-12 portable, which
is the part of the GRLIB inheritance that has actual value.

One deliberate omission: **the bridge does not decode which peripheral is
selected.** It drives a single `psel_o` meaning "some peripheral", and
`soc_top.v` turns that into per-slot `PSEL` using the generated slot
constants. A bridge that decoded slots itself would be a second copy of
the memory map, and the second copy is where drift lives.

---

## 5. What was built, and what verifies it

### 5.1 The fabric

`hw/soc/rtl/soc_bus.v`. Two Ibex-native masters onto four slave ports
plus an internal error slave. The header states the protocol as a
specification — the four numbered rules quoted verbatim from
`ext/ibex/doc/03_reference/load_store_unit.rst` — then four numbered
slave obligations (S1-S4) and one master restriction, because those are
the contract the rest of the SoC's blocks are written against.

Three design points worth recording:

**Multiple outstanding requests are supported, and had to be.** Ibex's
prefetch buffer issues up to two (`NUM_REQS = 2` in
`ibex_prefetch_buffer.sv` **[fact]**) and the load/store unit issues a
second before the first response during a split misaligned access. A
fabric limited to one outstanding request per master would halve
instruction fetch bandwidth.

**All of a master's outstanding requests must go to one slave.** Ibex
protocol rule 4 requires in-order responses per master, and slaves have
different latencies: the RAM answers in one cycle, the peripheral bridge
in three or more. A master that issued to the bridge and then to the RAM
would get its answers out of order. The alternatives were a reorder
buffer, which has to store a whole response, or one outstanding request
per master, which costs the bandwidth above. This restriction costs
nothing in the case that dominates — linear fetch out of one memory — and
one dead cycle when a master changes region.

**Arbitration is round-robin, not fixed priority to the data port.**
Fixed priority is what most small systems do and the usual justification
is "the pipeline cannot issue loads without instructions". That is an
argument about the core, not about the fabric. Round-robin makes
no-starvation a property of this file, and section 5.3 states the bound
that is proved.

**An unmapped access is a bus error, not a read of zero.** The error
slave is inside the fabric, always ready, one-cycle latency, `err` high.
Ibex turns that into a load or store access fault. Six regions and
fourteen peripheral slots in the frozen map are reserved and reach it.

### 5.2 The rest

| File | What it is |
|---|---|
| `hw/soc/rtl/soc_apb_bridge.v` | System bus to AMBA 3 APB, one outstanding transfer |
| `hw/soc/rtl/soc_mem.v` | Behavioural memory model, `RO` makes it a ROM that faults writes. **Not a memory** — see section 9 |
| `hw/soc/rtl/soc_uart.v` | Console UART, GRLIB APBUART register map, transmit only, real serialiser |
| `hw/soc/rtl/soc_pnp.v`, `soc_apb_pnp.v` | The two device tables, contents generated from the map |
| `hw/soc/rtl/soc_top.v` | Ibex `small-pmp` plus all of the above, and the peripheral slot decode |
| `hw/soc/tb/tb_soc.v` | The system testbench, section 5.4 |

The UART is a subset and its header lists what is missing rather than
stubbing it: no receiver at all (`STATUS.DR` reads zero forever rather
than pretending), one holding register instead of a FIFO, no parity, no
FIFO-debug or capability registers. It is a real serialiser with GRLIB's
8x-oversampling scaler, not a simulation print hook, and that choice is
what puts the baud divider and the shift register inside what the run
proves.

### 5.3 Verification

**cocotb**, `hw/soc/tb/cocotb/` **[fact]**:

| Suite | Tests | Result |
|---|---:|---|
| `test_soc_bus` | 13 | 13 pass |
| `test_soc_apb_bridge` | 11 | 11 pass |

No address literal appears in any check. Every expected decode is derived
from `sw/golden/memmap_gen.py`, the generated map, so a check fails if
the map moves. Gap addresses for the error-slave tests are computed by
walking the sorted regions; reserved targets are selected by `port is
None`. The bus suite covered 40 decode probes over the four ported
regions, 88 accesses over 11 derived gap addresses and 48 over the six
portless regions; the starvation test measured a maximum gap of 2 cycles
between consecutive grants for each master over a 300-cycle window with
both hammering the same slave, against an asserted bound of 8 **[fact]**.

Non-vacuity was measured by mutation, against scratch copies (the
Makefiles expose `SOC_BUS_SRC` and `APB_BRIDGE_SRC` for this) **[fact]**:

| Mutation | Caught by |
|---|---|
| ROM decodes to the RAM port | `test_decode_every_mapped_region` and 4 others |
| unmapped addresses fall through to the device table | the two error-slave tests |
| same-slave outstanding restriction removed | `test_in_order_slow_then_fast` and 3 others |
| round-robin replaced by fixed data-port priority | `test_no_starvation`, and only that test |
| `PENABLE` asserted in SETUP as well | the protocol monitor, 9 failures |
| `PREADY` sampled in the SETUP state | the protocol monitor, 9 failures |
| `paddr_o` drops the low offset bits | `test_paddr_is_window_offset` and 4 others |
| `PRDATA` captured on ACCESS entry, not in the `PREADY` cycle | 9 failures |

**Formal**, `hw/soc/formal/` **[fact]**:

| Job | bmc, depth 24 | prove, k-induction | cover, depth 24 |
|---|---|---|---|
| `soc_apb_bridge` | PASS | **PASS** | PASS, 7 of 7 obligations reached |
| `soc_bus` | PASS | **PASS** | PASS, 11 of 11 obligations reached |

The bridge's property set (A1-A11) is the AMBA 3 APB sequencing and
stability rules plus the Ibex protocol's slave-side clauses, with ghost
registers capturing the request from the master port and the response
from the peripheral port independently of the bridge's own storage — so a
bridge that was merely self-consistent could not satisfy them. The
fabric's set (F1-F9) proves one-hot decode against the generated map
constants in both directions, that a grant requires the slave's grant,
that the payload broadcast matches the granted master and that the
instruction port can never cause a write, the outstanding limit and the
same-slave restriction, per-slave queue non-overflow with a ghost counter
wide enough to see an overflow, and a counting property that no response
is lost or duplicated.

**Both files state what they do not prove.** Neither proves liveness:
nothing says a transfer ever completes, and if a peripheral never asserts
`PREADY` every property still holds. Neither proves ordering directly —
F4 proves each master's outstanding requests are at one slave and F7
proves responses are not lost, and ordering then follows from the slave
contract S3, which is **assumed** of slaves rather than proved of them.
Neither can enumerate the map: if a region were added to
`regmap/memmap.yaml` with a fabric port and `soc_bus.v` were not
extended, every formal property would still pass and the new region would
quietly reach the error slave. That gap is closed from the other side, by
`sw/tests/test_memmap.py::test_fabric_decodes_every_ported_region_and_no_other`,
which is textual and cannot check that the constants are used correctly.
The two halves are complementary and neither is sufficient.

### 5.4 The bring-up program on the real bus

The brief for this work asked whether `hw/soc/tb/sw/test_ibex.c` could
run through the real bus and memory map rather than the minimal
testbench memory of `docs/38`. It can, and it is the same program file:

```
[TB] SoC: boot 0xc0000000, ROM image test_soc.hex, 8 clocks per UART bit
ibex bring-up self-test
  ok   test 0x00000001  ...  ok   test 0x0000000a
  ok   test 0x0000000c    ok   test 0x0000000d    ok   test 0x0000000e
  ok   test 0x0000000b
checks run: 0x0000000e  fail mask: 0x00000000
RESULT PASS
[TB] core asleep after 165304 cycles
[TB] exit code 0x00000000
[TB] console: 403 characters decoded, 0 framing errors
[TB] PASS
```

**[fact, `hw/soc/out/sim-soc/sim.log`]**

What is different from the `docs/38` run, and why each difference is
evidence rather than noise:

- **`.text` is in the boot ROM at `0xC0000080` and `.data` is in RAM at
  0.** `crt0.S` relocates `.data` from its load address in the ROM to
  its run address in RAM before `main`, so the very first thing the
  program does is read through one slave and write through another. A
  decode that sent either to the wrong place would corrupt every
  initialised variable before a single check ran.
- **Test 7 reads its own instruction stream**, which is now a data-port
  read of the ROM: a third decode case, unplanned, that falls out of
  keeping the program unchanged.
- **The console is a real UART on the peripheral bus, and the testbench
  decodes the serial line** rather than snooping the register write. The
  path proved is core, fabric, APB bridge, slot decode, UART register
  file, baud divider, shift register, pin. The stop bit is checked on
  every character; zero framing errors over 403 characters.
- **Three new checks exist only here.** Test 12 loads from
  `0xE0000000` — a region the map freezes and nothing decodes — and
  requires `mcause = 5`, load access fault. A fabric whose default was
  "return zero" would pass every other check in the program and fail
  that one. Test 13 reads the device table's identity and endianness
  words and compares them against constants generated from the same
  source as the table's contents. Test 14 stores into the boot ROM and
  requires `mcause = 7`.
- **Termination is `WFI`, not a magic store.** The frozen map has no
  address meaning "stop the simulator" and this work did not invent one;
  `crt0.S` leaves the exit code and a magic word in RAM and sleeps, and
  the testbench watches `core_sleep_o`.

**The pass criterion is deliberately wider than the exit code.** A run
passes only if the core woke and then slept, the magic word says the
exit code is meaningful, the exit code is zero, the string `RESULT PASS`
appeared on the decoded serial line, and no alert or double fault ever
fired. Criteria 3 and 4 reach the same conclusion by two independent
paths — one reads RAM through a hierarchical reference, the other reads a
pin.

**The `docs/38` flow is unchanged and still passes**: `small-pmp` on the
minimal system, 131,694 cycles, same as recorded there **[fact]**. The
program's two platforms are selected by `-DSOC_PLATFORM`, and the
non-SoC path is byte-identical in behaviour.

### 5.5 Induction needed strengthening, and the strengthening is itself a check

The fabric's first proof attempt failed under induction on the fairness
property, and would have failed on three more. That is not a design
defect: k-induction starts from an arbitrary state, and an arbitrary
state is one where the ghost bookkeeping and the design's own counters
disagree. Five invariants (I1-I5 in
`hw/soc/formal/soc_bus_props.v`) close the gap, and they are the only
properties in the file that name the design's own state:

- the ghost outstanding counts equal the design's counters;
- the ghost slave locks equal the design's, which is also the statement
  that the address broadcast to the slaves decodes to the same slave the
  granting master's own address decoded to;
- per-slave total occupancy is the sum of the two masters' shares;
- **the singleton property** — a master's outstanding requests are all at
  the one slave it is locked to and at no other. This is the same-slave
  restriction expressed as an invariant rather than as a check on a
  grant, and it is what makes the response-counting property true: two
  slaves cannot both hold a response for the same master, so two
  responses in one cycle cannot collide on one master's `rvalid`;
- the design's ownership queue holds exactly the entries the ghosts
  count, in the same positions.

Each is a real check as well as a proof aid: a fabric that miscounted, or
whose broadcast decode disagreed with the granting master's, would fail
one of them. With them the proof completes in one second **[fact]**; the
first attempt had been running for six minutes on the bounded check
alone.

---

## 6. Measured area, and why it does not decide anything

All numbers below are from **one recipe**: Yosys `stat -liberty` on
`ihp-sg13g2` at the typical corner, `abc` with the same driving cell,
the same load, and the same 20 ns delay target. `hw/soc/flow/syn_soc.sh`
and `hw/soc/flow/syn_probe.sh` are the same script pointed at two
directories, deliberately, because a comparison between two differently
measured things is not a comparison. Gate equivalent =
`sg13g2_nand2_1` = 7.2576 um2 **[fact, liberty]**.

The Ibex reference figure the percentages are taken against is
**275,682.6198 um2**, read out of `hw/soc/out/small-pmp/area.rpt`, whose
Yosys script carries `abc ... -D 20` **[fact]** — the same target, so the
three numbers are directly comparable. `docs/38` section 8.4 quotes
275,683 for the same configuration.

### 6.1 What was built

| Block | Cells | Flops | Area, um2 | kGE |
|---|---:|---:|---:|---:|
| `soc_bus` | 673 | 42 | **8,362.31** | 1.152 |
| `soc_apb_bridge` | 201 | 94 | **6,437.49** | 0.887 |
| `soc_uart` | 241 | 52 | 4,359.78 | 0.601 |
| `soc_pnp` | 150 | 28 | 2,610.51 | 0.360 |
| `soc_apb_pnp` | 102 | 0 | 930.67 | 0.128 |
| **`soc_bus` + `soc_apb_bridge`, integrated** | **891** | **136** | **14,807.32** | **2.040** |

**[fact]**

### 6.2 The AHB cost probe

`hw/soc/rtl/probe/` holds an honest AHB-Lite path: two Ibex-to-AHB-Lite
bridges, a two-master arbiter, a decoder/multiplexer with a compliant
two-cycle-error default slave, and an AHB-to-APB bridge, wired into a top
level whose every output reaches a port so the optimiser cannot delete
anything.

**It is a cost probe and it is not verified in any way.** Not one cycle
of its behaviour has been observed. Every file says so in its header. It
elaborates, it lints clean under Verilator, and it synthesises to a
specific number of gates; whether it moves the right bits at the right
time is unknown.

| Block | Cells | Flops | Area, um2 | kGE |
|---|---:|---:|---:|---:|
| `ibex2ahbl` | 89 | 34 | 2,507.50 | 0.346 |
| `ahbl_interconnect` | 169 | 8 | 1,948.02 | 0.268 |
| `ahbl_arbiter` | 320 | 71 | **7,667.62** | 1.057 |
| `ahbl2apb` | 133 | 42 | 3,233.26 | 0.446 |
| **`probe_ahbl_top`, integrated** | **901** | **189** | **17,154.32** | **2.364** |

**[fact]**

### 6.3 The comparison, and the honest reading

| | Built (native + APB) | Cost probe (AHB-Lite + APB) | Difference |
|---|---:|---:|---:|
| Area, um2 | 14,807.32 | 17,154.32 | **+2,347.00, +15.9 %** |
| Flip-flops | 136 | 189 | +53, +39 % |
| % of Ibex `small-pmp` (275,682.62 um2) | 5.37 % | 6.22 % | **+0.85 %** |

**[fact for the two measured columns; the percentages are arithmetic on
them]**

**Area does not decide this.** Nine tenths of one percent of the CPU is
not a reason to reject a bus, and this document would be dishonest if it
pretended otherwise. What the measurement is actually good for is
excluding the opposite mistake: it shows the decision was not made by
picking the smaller thing, and it puts a price on reversing it if an
external AHB interface is ever needed.

**Two things the numbers do not say.** First, `probe_ahbl_top` gives its
instruction-side bridge a full write path, because the five parts were
wired to stay additive rather than to be distorted by tie-off
propagation; the real Ibex instruction port is read-only, so an
integrated AHB build would be **somewhat smaller than 17,154 um2 and that
was not measured**. Second, the arbiter's 7,667.62 um2 is the option that
keeps both masters at full throughput; the alternative that costs a
bubble per ownership change would be far smaller. Both corrections point
the same way, and both make the area argument weaker, not stronger. That
is why the argument is section 3 and not this one.

### 6.4 Two synthesis findings

**A flip-flop that nothing can observe is removed, and that was correct
here.** The fabric's per-slave queue write index was first written as
three bits, because the queue holds up to four entries. Yosys reported
**42 flip-flops for both the three-bit and the two-bit version** and
8,814.015 um2 against 8,551.116 um2 **[fact, measured on a scratch
copy]**: the third bit influences nothing outside itself, so the flop was
deleted and 41 cells of its arithmetic survived. The index is only ever
*read* at values 0..3 — a push at fill 4 is impossible, because fill 4
means both masters hold their maximum at that slave and neither can issue
— so two bits is what the design means and two bits is what it now says.
The property that makes it safe is not visible in a modulo counter, so it
is proved separately with a ghost counter in the formal job rather than
left to a comment. `soc_bus` measures 8,362.31 um2 with that change and
the reset fix of section 8 together; ABC's mapping is not monotonic, so
the two deltas do not add and neither should be quoted alone.

**This is the mirror image of `docs/38` section 8.5**, which measured a
15,455 um2 gap where the synthesiser was removing redundancy that was
*wanted*. The rule that follows from both is the same: after synthesis,
count the flops against the registers that were written, and account for
every difference.

---

## 7. What may be claimed, and what may not

`docs/05-market-positioning.md` section 4 binds every public claim. Rule
5 — any figure published externally must be traceable to measurement or
clearly labelled as a design target — applies to protocol claims as
directly as it does to radiation numbers, because both are the kind of
statement a reader will rely on.

**May be claimed:**

- The peripheral bus is **AMBA 3 APB**, with the sequencing and stability
  rules proved by k-induction (section 5.3).
- The memory map, the 4 KiB peripheral slot geometry, the peripheral
  register maps and the device table record layout **follow GRLIB and
  NOELVSYS conventions**, with the source of each address recorded per
  row in `docs/memmap-soc.md`.
- The management core is **Ibex RV32IMC with PMP**, `small-pmp` as
  characterised in `docs/38`.

**May not be claimed:**

- **Anything about AHB.** There is no AHB in this SoC. Not "AHB
  compatible", not "AHB-Lite based", not "AMBA AHB system bus". The cost
  probe does not change this: it is unverified sketch RTL that nothing
  instantiates.
- **That the device table is an AMBA plug-and-play table.** It uses
  GRLIB's record *layout* — eight-word slave records, the identification
  word field split, the bank address register field split — because a
  documented layout is what makes a device table readable by something
  other than its author. It describes this project's own bus.
- **That the device IDs mean anything to Gaisler.** Vendor code `0x09` is
  GRLIB's "various contributions" bucket; the device IDs under it are
  assigned by this project and are **not** registered with Frontgrade
  Gaisler. A GRLIB-aware tool will show a known vendor and unrecognised
  devices, which is the truthful outcome. Using Gaisler's own `0x01`
  would not be, and `docs/08` section 3 row 4 already said so.
- **That the map is fully implemented.** Six of ten regions and fourteen
  of sixteen peripheral slots are reserved addresses with nothing behind
  them.

One consequence worth naming: GR740's `AHBSTAT` error-latch slot is
called **`BUSSTAT`** in this map. It latches errors on this project's own
system bus, and naming it after a bus that is not there would have been a
small lie in a place nobody would check.

**A field that cannot express this map, recorded rather than rounded
silently.** A GRLIB-style bank address register compares address bits
[31:20], so its granularity is 1 MiB, and three regions here are smaller
than that. Their `mask` field is rounded up and the **exact byte size is
carried in user-defined word 1**, which GRLIB leaves free.
`docs/memmap-soc.md` section 4 names the three. A reader that trusts only
the bank address register will over-state three sizes; a reader that uses
word 1 will not.

---

## 8. Defects found, all four in this project's code

Recorded because each is a trap the next block would otherwise walk into.

1. **An include guard on a body include silently blanks every module
   after the first.** `soc_memmap.vh` is a body of `localparam`
   declarations included inside a module, and more than one module needs
   it. With an `` `ifndef `` guard, the first module to include it got
   the constants and every later one got an empty file — because Verilog
   macro state is shared across a whole compilation unit. The symptom
   was an unbound-name error inside the address decoder with no hint of
   the cause. The generator now emits all three body includes unguarded
   and says why in the file.
2. **`core_sleep_o` is already high while the core is held in reset.** A
   core that is not fetching is not busy, and Ibex says so. The first
   version of the system testbench waited on `core_sleep_o` alone, so it
   returned instantly on the cycle reset was released and reported a
   timeout at whatever value the free-running cycle counter had reached
   by the time the report printed — a symptom that points nowhere. The
   testbench now requires the core to have been observed *awake* first.
3. **The first no-starvation property was false, and the bounded check
   found it at depth 3.** It required all slaves to be ready only in the
   second of the two cycles. The counterexample: cycle 0, the
   instruction port requests the device table and that slave withholds
   its grant; cycle 1, every slave is ready but the data port also
   requests, and with nothing yet accepted the round-robin flop still
   favoured the data port. Two cycles of requesting, no grant, and the
   fabric behaving correctly — a slave that refuses a grant is not
   starvation by the arbiter. Readiness had to be in the antecedent in
   both cycles.
4. **The fabric decoded and granted while reset was asserted.** Found by
   the cocotb suite driving requests during reset. The request and grant
   paths are combinational; the queues and counters are reset. A master
   asserting `req` during reset would therefore have a transaction
   accepted by a slave, whose response would arrive after reset release
   and pop a queue that never recorded it, underflowing the accounting.
   Ibex holds its request ports low in reset so this cannot happen in
   this SoC — but "cannot happen because of the master we happen to
   have" is not a property of the fabric. `can_issue_i` and
   `can_issue_d` are now gated by `rst_ni`.

Defect 4 is the one worth generalising: it was found by a test that
drove an input the specification says nothing about. Neither the Ibex
protocol nor the memory map mentions reset, so no property in either
formal file could have caught it.

---

## 9. What is not built

Listed so the gaps are visible rather than assumed closed.

1. **No memory.** `soc_mem.v` is a behavioural register array with no
   ECC, no scrubbing, no macro behind it and no wrapper for one.
   `soc_top.v` fixes `SecureIbex` to 0, which is the owner's decision
   (`docs/38` section 10 item 4, closed 2026-08-31 in favour of
   `small-pmp`) and is also the only thing this memory model can
   support: `ibex_top.sv` line 41 makes `MemECC` follow `SecureIbex`, so
   enabling it changes the memory interface contract to 39-bit ECC and
   raises `alert_major_bus_o` on the first fetch without stored check
   bits. `docs/38` section 7.4 is the bring-up record of that exact
   failure. **The management processor is now the least hardened block in
   the design**, and that consequence belongs with the hardening
   architecture rather than with this document.
2. **No interrupts.** No CLINT, no PLIC. Their addresses are frozen and
   nothing decodes them; every Ibex interrupt input is tied off, which is
   also why the UART's interrupt output goes to a port rather than
   anywhere. The interrupt source numbers are frozen in the map
   (`docs/08` section 4 item 7) so the device table, the future
   controller and the drivers cannot disagree later.
3. **No hardening at all.** No TMR, no SECDED on the bus, no `BUSSTAT`
   error latch, no scrubber. Those slots are reserved and empty. The
   fabric has no parity or protection on the address path, which for a
   part whose whole argument is fault tolerance is a gap and not an
   omission.
4. **No NPU connection.** The 256 MiB window is frozen and reaches the
   error slave.
5. **Fourteen of sixteen peripheral slots are empty**, including the
   watchdog that `docs/08` section 4 item 8 makes a project requirement
   ("armed at reset, staged through boot"). Nothing here implements it.
6. **No place-and-route and no timing.** Every number in section 6 is a
   synthesis cell area at a 20 ns delay target. No frequency was measured
   for any of this RTL, and the fabric has not been through STA at any
   corner. `docs/38` section 10 item 3's three place-and-route
   obligations are untouched and now have company.
7. **No gate-level simulation and no fault injection** on any of it.
8. **The device table is not validated against a GRLIB tool.** It is
   checked against the generator's own output, which proves internal
   consistency and not that anything else can read it.
9. **No boot flow.** `docs/08` section 4 item 6's ASW image header,
   checksum, boot report register, bootstrap pins and staged watchdog do
   not exist. The ROM holds a test program loaded by `$readmemh`.

---

## 10. What the checkers do not cover

Stated separately from section 9, because "not built" and "built but not
checked by the thing that looks like it checks it" are different failures
and this repository has been bitten by the second six times.

- **`sw/tests/test_memmap.py` simulates nothing.** It checks the map's
  internal consistency and the agreement of six generated artifacts. A
  self-consistent map with an interconnect that ignored it would pass
  every test in it.
- **The formal jobs cannot enumerate the map**, and the map test cannot
  read logic. Section 5.3 says how the two halves meet and that neither
  is sufficient.
- **The cocotb slave models never break their contract.** They never
  reorder, never double-respond and never respond in the grant cycle. So
  the suites say nothing about how the fabric behaves against a slave
  that violates S1-S4.
- **`tb_soc.v` exercises two-master contention only incidentally**, as a
  by-product of running a program. Nothing in it is designed to stress
  the arbiter.
- **Nothing checks the reserved addresses are the right ones.** Test 12
  proves *an* unmapped address faults; it does not prove that the address
  it used is where CLINT should be.
- **The AHB cost probe's area numbers are sound and its RTL is a
  sketch.** Section 6.2.
- **Neither formal job proves liveness.** Section 5.3.

---

## 11. Files touched outside `hw/soc/`, and why none is frozen

`docs/34` section 2 pins the pilot by git blob hash of the files in
`hw/rtl/` and section 5 lists the flow configs. None of the following is
in either set **[fact]**:

| File | Change |
|---|---|
| `regmap/memmap.yaml`, `regmap/generate_memmap.py` | new; disjoint output set from `regmap/generate.py`, which is what keeps this work out of `hw/rtl/` |
| `sw/golden/memmap_gen.py` | new, generated |
| `sw/tests/test_memmap.py` | new |
| `docs/memmap-soc.md`, `docs/39-soc-bus-and-memory-map.md` | new |
| `docs/00-index.md` | one row per new document, which `sw/tests/test_doc_links.py` requires |
| `conftest.py`, `pytest.ini` | `hw/soc/tb` added to the cocotb exclusion, same rule and same reason as `hw/tb` |
| `.gitignore` | four entries: the cocotb build directories and result XML, and the two SymbiYosys working directories. Same rule the file already applies to `hw/tb/` and `formal/`, and the same non-argument `docs/38` section 11 makes: `.gitignore` is in neither of `docs/34`'s pinned sets |

Everything else is under `hw/soc/`. `hw/soc/{ext,tools,gen,out}` remain
gitignored — fetched or generated, not vendored — by the rule `docs/38`
section 11 states.

---

## 12. Reproducing this

```
python regmap/generate_memmap.py            # the map and its six outputs
.venv/bin/python -m pytest sw/tests/test_memmap.py

make -f hw/soc/tools.soc.mk soc-toolcheck   # what will actually be used
hw/soc/flow/sim_soc.sh                      # the whole SoC in Icarus

cd hw/soc/tb/cocotb && make -f Makefile.soc_bus
cd hw/soc/tb/cocotb && make -f Makefile.soc_apb_bridge

cd hw/soc/formal && make                    # both sby jobs, all tasks

hw/soc/flow/syn_soc.sh   soc_fabric_meas    # what was built
hw/soc/flow/syn_probe.sh probe_ahbl_top     # what AHB would have cost
```

`hw/soc/flow/sim_ibex.sh small-pmp` still runs the `docs/38` bring-up on
the minimal system and still passes, unchanged.
