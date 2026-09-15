# 65 — The first spacecraft interface, and what the other four cost

`docs/60-soc-datasheet.md` section 4.1 states the position this document
starts from: "There is **no SpaceWire, no CAN, no SPI, no I2C, no QSPI
and no GPIO**, in the sense that matters: there is no RTL for any of
them." Eleven of sixteen peripheral slots were reserved addresses that
reached the error slave, and `soc_top`'s only functional output was the
UART's transmit line.

This document fills one of those slots, to this project's standard, and
prices the other four. The order is deliberate and section 2 argues it.
Two questions no earlier document had answered are answered here with
measurements: whether the sv2v path that carries Ibex also carries a
piece of third-party interface IP (`docs/38` section 10 item 7 said
this was untested), and what each of `docs/03`'s selected cores costs
once it is actually fetched, pinned and put through this flow.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
an intention with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash. Nothing in `hw/rtl/`, `hw/tb/`, `formal/`, `tt/` or
`hw/openlane/` was modified; `hw/tb/Makefile.fi` was not invoked.
Section 12 lists every file touched.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| What is built? | **GPIO**, GRGPIO-shaped, 16 pins, in slot `0x002` at `0xFF902000` on fast line 2 — the slot, device id, source number and line the map has carried since `docs/39` and `docs/40`. RTL, a 14-test cocotb suite written against `grip.pdf` chapter 62 with **14 of 14 mutations caught**, a **k-induction proof** at both widths with 13 of 13 covers reached, check 28 of the bring-up program driving pins and taking the interrupt on the real fabric, the map promoted, the device-table record live **[fact]**. Sections 3-6 |
| Is it through the pins? | **Yes.** `soc_top` gains 16 pins as three wires each, `tb_soc.v` models the pads and a board with a loopback, and every read-back in check 28 goes through a pad and a wire; `DATA` never reads the `OUTPUT` register. Section 5 |
| What does it cost? | **779 cells, 144 flip-flops, 13,162.87 um2, 1.814 kGE** alone; **+230 cells, +144 flip-flops, +14,649.73 um2, +2.35 %** on the whole SoC **[fact]**. Section 7 |
| Did the whole-SoC invariant move? | **215,428 exactly with the block present and the program unchanged. 217,634 with check 28 in the program**, +2,206 cycles, all of it the new check **[fact]**. Section 6 |
| Does sv2v carry OpenTitan's `spi_host`? | **Yes.** 52 modules, 8,064 lines of Verilog-2005 from 16 packages and the closure, **zero patches to OpenTitan, two lines rewritten in the generated file**, elaborates under Icarus `-g2005` and `-g2005-sv`, synthesises **[fact]**. The converter is not the obstacle. Section 8 |
| Then what is? | **The block is 65.05 kGE — 171 % of the Ibex core** — and about four fifths of its 5,404 flip-flops are FIFO storage whose depths are constants of a generated package **[fact for the area, estimate for the share]**. Section 8.4 |
| Is QSPI built? | **No. Assessed, with the fetch-pin-convert-elaborate-measure chain scripted and reproducible.** Section 8 says what a wrapper would have to do and section 13 says which of two routes to take |
| SpaceWire, CAN, I2C? | **Assessed, not built.** All three fetched, pinned and elaborated; SpaceWire and CAN synthesised for area. Section 9 |
| What is the sharpest finding? | **The source-list defect `docs/61` guarded against recurred in the guard itself**: `soc_gpio.v` was added to all four flows the guard checks and the whole-SoC elaboration test still failed, because that test carries a fifth list nothing checks. Section 10 |

---

## 2. Why GPIO first, and why the bridges are the work

`docs/03-cpu-and-ip-survey.md` section 2.2 selected the interface IP.
`docs/39` section 3.2 then used a fact about that selection as an
argument for the fabric: **not one selected core is native to the
peripheral bus this SoC speaks.** The Mohor CAN core and `simple_spi`
are Wishbone, OpenTitan's `spi_host` is TileLink-UL, `spacewire_reloaded`
is AXI4-Lite with AXI4-Stream data. Every one needs a bridge to AMBA 3
APB, and `docs/39` section 5.3 set the standard a bridge has to meet
here: compliance proved by k-induction, not asserted.

So the work is the bridges, and a bridge cannot be the first thing
verified on a path nothing has walked. Before this document, no
peripheral had ever gone from *reserved* to *implemented* in the map; the
three implemented APB blocks — UART0, TIMER0, BUSSTAT — were each built
in the same document that created or froze their slot. The sequence a
new block has to complete is:

1. a `status` promotion in `regmap/memmap.yaml`, and the six generated
   files with it;
2. a decode in `soc_top.v`, which `sw/tests/test_memmap.py` checks
   textually against the map;
3. a fast-line connection, checked the same way;
4. a source-list entry in every flow that builds `soc_top` — the four
   `docs/61` found had drifted;
5. a driver header, a vector-table entry and a check in the bring-up
   program;
6. a cocotb suite written against the block's specification, a formal
   job, and a measured area.

Walking that on a block that is this project's own RTL, with no
third-party dependency, means that when the second block fails a step,
the failure is in the block or its bridge and not in the path. GPIO is
that block: `docs/03` costed it at under 20 hours and said "no
third-party IP justified", and it is the interface bring-up needs first
— a pin the program can toggle is the cheapest observable a board has.

The order after it follows what each block proves and what the mission
needs. QSPI is the weight-load path `docs/51` section 14 item 4 left
unbuilt and the only interface the NPU itself needs, and it is where the
`docs/38` section 10 item 7 question — does sv2v carry a second piece
of lowRISC IP — gets answered. SpaceWire is the one interface `docs/05`
section 3.4's mission profiles imply and `docs/01` section 4 names
first. CAN and I2C are platform housekeeping.

---

## 3. What was built

| File | What it is |
|---|---|
| `hw/soc/rtl/soc_gpio.v` | The port. GRGPIO register map, `grip.pdf` table 923, 16 pins, two-flop input synchroniser, level and edge interrupt detection, one shared interrupt line, logical-OR/AND/XOR write aliases |
| `hw/soc/rtl/soc_top.v` | Three new pin vectors, a `GPIO_NBITS` parameter, the slot decode, the instance, fast line 2 |
| `hw/soc/tb/tb_soc.v` | A pad model and a board: pads 8-15 wired to pads 0-7 |
| `hw/soc/tb/tb_soc_fi.v`, `tb_soc_npu_fi.v` | The pins tied to a board with nothing on them |
| `hw/soc/tb/cocotb/test_soc_gpio.py`, `Makefile.soc_gpio` | 14 tests against the specification, section 4.1 |
| `hw/soc/formal/soc_gpio_props.v`, `soc_gpio.sby` | P1-P7, section 4.2 |
| `hw/soc/tb/sw/soc_gpio.h` | Offsets and fields for the program; the base comes from the generated map |
| `hw/soc/tb/sw/test_ibex.c`, `crt0.S` | Check 28 and vector 18 |
| `hw/soc/flow/sv2v_spi_host.sh` | The reproducible QSPI-candidate chain, section 8 |
| `hw/soc/tools.soc.mk` | Four new pinned checkouts, section 8.1 |

### 3.1 The register map, and what was declined

`grip.pdf` — the GRLIB IP Core User's Manual, version 2026.2, the same
document `docs/08` cites — chapter 62 is the specification. Its offsets
are implemented verbatim where they cost nothing, which `docs/08`
section 3 row 8 asks for, and the departures are in the file's header
rather than left for a driver to discover:

- **One shared interrupt line, `IRQGEN = 1` in `CAP`.** GRLIB can give
  every pin its own interrupt or a software-mapped one. The frozen map
  gives this slot exactly one source number, 4, and one fast line, 2;
  sixteen per-pin sources would consume numbers the map has not
  reserved. This is the same decision `soc_gptimer.v` took with
  `SI = 0` and for the same reason.
- **The interrupt flag register is implemented, `IFL = 1`.** Without
  it a shared line cannot say which pin raised it.
- **No bypass, no input-enable, no pulse register, no interrupt map
  registers.** `CAP` reports each absence, each reads zero, and a write
  to any is ignored — GRLIB's documented behaviour for a register a
  configuration leaves out.
- **The logical-OR/AND/XOR aliases (table 937) are implemented** for
  `OUTPUT`, `DIRECTION` and `IMASK`. They are cheap and they are what
  a driver needs to set one pin without a read-modify-write.
- **`IPOL` and `IEDGE` reset to zero** where GRLIB marks them "NR", no
  reset value. A register that powers up as whatever its flip-flops
  happened to hold is a register a fault-injection campaign cannot
  reason about. The cost is nothing: with `IMASK` reset to zero the two
  cannot be observed until software writes them, and software that
  writes `IMASK` before `IPOL` and `IEDGE` is relying on a value GRLIB
  does not define either.

### 3.2 `DATA` reads the pad and nothing else

`grip.pdf` 62.2: "The input from each buffer is synchronized by two
flip-flops in series ... The synchronized values can be read-out from
the I/O port data register." So `DATA` is `gpio_i` two clocks late, and
in particular a pin whose `DIRECTION` bit is set reads back through
`gpio_i`, not through the `OUTPUT` register.

This SoC has no pad ring. `gpio_o` and `gpio_oe_o` leave `soc_top` as
separate vectors and `gpio_i` enters as a third; the pad — where the
three meet — is outside the design. **A block that folded `OUTPUT` into
`DATA` would pass a write-then-read-back test with no pin present at
all**, and would hide exactly the board faults a read-back through the
pad exists to find. `test_data_is_the_pins_two_clocks_late_and_never_the_output_register`
drives every pin as an output with `OUTPUT` all ones and `gpio_i` at a
pattern, and requires the pattern. Mutation `m02` in section 4.3 is the
block that reads its own register; that one test catches it.

### 3.3 The interrupt is a level of the flag

A line detects, under its mask, when the synchronised value equals
`IPOL` (level mode) or becomes `IPOL` (edge mode). A detection sets
`IFLAG`; `IFLAG` is write-one-to-clear; a detection in the cycle of its
own clear wins — `soc_busstat.v`'s rule, for the same reason: the cycle
software acknowledges is not a rare cycle. `irq_o` is `|(IFLAG & IMASK)`,
a level driven from the flag rather than the detection, because a
one-cycle pulse on an Ibex fast line is a pulse the core can be inside a
trap for. `IMASK` gates both the setting of the flag (`grip.pdf` 62.2,
"To enable an interrupt, the corresponding bit in the interrupt mask
register must be set") and the line, so masking a flagged pin silences
it at once and unmasking a pin later delivers nothing from before.

---

## 4. Verification

### 4.1 cocotb, against the specification

`hw/soc/tb/cocotb/test_soc_gpio.py`: **14 tests, 14 pass** **[fact]**.
The expectations are `grip.pdf` tables 923-937 and the prose of 62.2,
the APB slave contract the sibling blocks obey, and the generated map
for the slot and the line; the RTL was read for port names and reset
polarity. No address literal for the block's base appears in it. The
width is read from the same `NBITS` the Makefile elaborates.

What the tests establish, in the order a doubt would arise: the reset
state is every pin an input and nothing enabled; `DATA` is the pins two
clocks late and never the output register; `OUTPUT` and `DIRECTION`
drive the pin wires independently; the nine logical aliases update the
right register with the right operation; a level interrupt follows
`IPOL` in both polarities and re-arms while the level persists; an edge
interrupt fires once on the selected edge and not on the other; the
mask gates the flag on the way in and the line on the way out; `IFLAG`
is write-one-to-clear per line and a write of zero does nothing; an edge
in the cycle of its own clear is not lost; `CAP` reports this
configuration and `IAVAIL` every line; unimplemented registers read
zero and writes to them disturb nothing; bits above the port width read
zero and are not stored; reads have no side effects; the slot and line
are the frozen map's.

`test_the_slot_and_the_line_are_the_frozen_maps` failed on the first
run, before `regmap/memmap.yaml` was promoted: the block existed and the
map still called it reserved. That is the test doing its job in the
direction it was written for.

### 4.2 Formal, by k-induction

`hw/soc/formal/soc_gpio.sby`, four tasks **[fact]**:

| Task | Mode | Result |
|---|---|---|
| `bmc` | bounded, depth 20, `NBITS = 4` | PASS |
| `prove` | k-induction, depth 8, `NBITS = 4` | **PASS** |
| `prove_w16` | k-induction, depth 8, `NBITS = 16` as instantiated | **PASS** |
| `cover` | depth 20, `NBITS = 4` | PASS, **13 of 13** cover statements reached |

The properties reconstruct the architectural state from the ports
alone — `soc_clint_props.v`'s method. Ghost registers read `PSEL`,
`PENABLE`, `PWRITE`, `PADDR`, `PWDATA` and `gpio_i`, apply table 937's
"new value = old value op write data" and 62.2's detection rule, and
the design's registers, pins and read data are asserted equal to them.
P4 states the synchroniser on the port history directly — `DATA` in
the access cycle equals `gpio_i` two cycles ago — so the ghost's own
delay chain is not what is being trusted. P5 says a flag is set only by
a detection under the mask and cleared only by its own write-one bit
with no detection in that cycle; P6 that the line is the OR of the
flags under the mask; P7 that reads, stray writes and writes to
read-only registers change nothing. Every ghost equality is also the
induction-strengthening invariant, the arrangement `docs/39` section
5.5 describes.

The narrow width is the reason every cover is reachable in a bounded
model; the wide task proves the shipped configuration without claiming
the covers at a width where they were not run — `soc_busstat.sby`'s
arrangement.

**What the proof does not say.** Nothing about a pad: `gpio_i` is free.
Nothing about metastability: two stages are present, whether two is
enough is not an RTL property. No liveness. No fault model.

### 4.3 Mutation evidence

Fourteen mutations against scratch copies of the RTL through
`Makefile.soc_gpio`'s `SOC_GPIO_SRC`, **all fourteen caught**
**[fact]**. The map test fails on every mutant for the reason section
4.1 gives — the mutants were run before the promotion — and is excluded
from the "caught by" column so that it does not count as a catch.

| Mutation | Caught by |
|---|---|
| one synchroniser stage instead of two | `test_data_is_the_pins_two_clocks_late...` and 1 other |
| `DATA` reads the `OUTPUT` register | `test_data_is_the_pins_two_clocks_late...` |
| the line is a pulse from the detection, not a level from the flag | `test_edge_interrupt_fires_once...` and 3 others |
| the line is not gated by `IMASK` on the way out | `test_the_mask_gates_the_flag...` |
| the mask is not applied on the way in | `test_reset_state...` and 6 others |
| an edge is treated as a level | `test_edge_interrupt_fires_once...` and 2 others |
| a clear wins over a simultaneous detection | `test_an_edge_in_the_cycle_of_its_own_clear_is_not_lost` |
| a write to `IFLAG` replaces it instead of clearing | `test_level_interrupt...` and 2 others |
| the AND alias performs OR | `test_logical_or_and_xor_aliases...` |
| `gpio_oe_o` follows `OUTPUT` instead of `DIRECTION` | `test_output_and_direction_drive_the_pin_wires` |
| `CAP.NLINES` reports the width, not width minus one | `test_cap_reports_this_configuration...` |
| polarity inverted | `test_level_interrupt...` and 4 others |
| `IPOL` not reset | `test_reset_state...` |
| the XOR alias is ignored | `test_logical_or_and_xor_aliases...` |

The suite's Makefile reports a `TESTS=` line on every mutant, so the
`docs/40` section 8.3 harness failure — a mutant that did not build
being read as caught by nothing — did not recur.

### 4.4 Everything else, re-run

`docs/50` found the fabric proof silently failing for two documents
after a change of this shape, so the whole of `hw/soc/formal` was
re-run rather than the new job alone: **10 jobs, 37 tasks, 37 PASS, no
unreached cover statement in any cover task** **[fact,
`cd hw/soc/formal && make`]**. The fabric's own two — `soc_bus` and
`soc_apb_bridge`, bmc, prove and cover — are unchanged by this work,
because the slot decode lives in `soc_top.v` and not in either of
them, and they pass. `soc_npu_ser`'s cover task is the long one at
about eight minutes; everything else completes in seconds.

`scripts/run_cocotb.sh`, the whole-repository runner: **19 suites, 294
tests passed, 0 failed, 0 suites not clean**, the three frozen-directory
suites skipped by its default **[fact]**. `sw/tests`: **402 passed**,
including the memory-map sync tests that now see GPIO implemented, the
textual checks that `soc_top.v` decodes exactly the implemented slots
and wires exactly the implemented interrupt-bearing ones, the flow
source-list guard, the whole-SoC elaboration guard of section 10 item
1, and the document link test **[fact]**.

---

## 5. The demonstration: pins and an interrupt on the real fabric

`tb_soc.v` now contains a pad model and a board. Each of the sixteen
pads shows the SoC's value when the SoC enables its driver and the
board's value otherwise; the board drives pads 0-7 low and **wires pads
8-15 to pads 0-7**. Contention — the SoC driving a looped-back pad
against the pin it is wired to — resolves to `X`, as it would on a
scope, and the program never does it.

Check 28, on the SoC platform only, after the NPU checks:

1. `CAP` reports `NLINES = 15`, `IFL = 1`, `IRQGEN = 1`, no input-enable
   and no pulse register — the configuration section 3.1 chose.
2. Out of reset `DIRECTION` is zero and `DATA` is zero: every pin an
   input, the board driving low.
3. `OUTPUT = 0x00A5`, `DIRECTION = 0x00FF`: `DATA` reads **`0xA5A5`** —
   the low byte back through the SoC's own pads, the high byte through
   the board wire.
4. `OUTPUT |= 0xFF00` through the OR alias: `DATA` still `0xA5A5`,
   because those pins are inputs and an `OUTPUT` bit does not reach the
   input side.
5. `OUTPUT ^= 0x0001` through the XOR alias: `DATA` reads `0xA4A4`; pad
   8 followed pad 0.
6. Pin 7 dropped through the AND alias, `IFLAG` cleared, pin 15 armed
   as a **rising edge** under the mask, `mie` and `mstatus.MIE` set; pin
   7 raised through the OR alias. The core takes **`mcause 0x80000012`
   at vector 18**, `mtvec + 0x48` — the marker written by the stub
   `crt0.S` now carries at that entry, compared against `mcause`, which
   is the only way a wrong vector is distinguishable from a right one
   (`docs/40` section 6.1). `IFLAG` reads bit 15; a write of 1 clears
   it and, because the mode is edge, it stays clear with the pin still
   high. `DATA` is `0xA4A4`.
7. The pins are returned to inputs and `DATA` reads zero.

```
  ok   test 0x0000001b    ok   test 0x0000001c    ok   test 0x0000000b
checks run: 0x0000001c  fail mask: 0x00000000
RESULT PASS
[TB] core asleep after 217634 cycles
[TB] console: 783 characters decoded, 0 framing errors
[TB] watchdog: stage1 1, stage2 0, stage3 0
[TB] gpio: pads 0x0000, driven 0x0000, irq 0
[TB] PASS
```

**[fact, `hw/soc/out/s65-sim-gpio/sim.log`]**

The first run of this check failed on step 6's last read: the program
expected `0xA5A5` after the pin had been flipped by the XOR in step 5
and never flipped back. The expectation was wrong and the pins were
right; the diagnostic line the check prints on failure said so
directly, and the comment now carries the arithmetic.

The escalation demonstration of `docs/40` section 6.2 was re-run with
the block present: three boots, three stages, **37,405 cycles**, the
number `docs/40` recorded **[fact, `hw/soc/out/s65-sim-wdog/sim.log`]**.

---

## 6. The invariant

`docs/56` section 8.4 asked that every document after it go on quoting
215,428, the whole-SoC cycle count with 27 checks. Two numbers, both
measured, and the difference between them is the point:

| Configuration | Checks | Cycles |
|---|---:|---:|
| HEAD, `docs/56` through `docs/64` | 27 | 215,428 |
| this RTL, `soc_gpio` in `soc_top`, program unchanged | 27 | **215,428** |
| this RTL, check 28 in the program | 28 | **217,634** |

**[fact, `hw/soc/out/s65-sim-gpio-noprog/sim.log` and `s65-sim-gpio/sim.log`]**

The first row is the statement that adding the block changes nothing
the existing program can see: `IMASK` resets to zero, so fast line 2 is
low throughout, and the slot decode adds no cycle to any access. The
second is +2,206 cycles, all of which are the new check. **Every
document after this one should quote 217,634.**

---

## 7. Measured area

Same recipe as `docs/39` section 6: Yosys `stat -liberty` on
`ihp-sg13g2` at the typical corner, the same driving cell, load and
20 ns target. Gate equivalent = `sg13g2_nand2_1` = 7.2576 um2. The Ibex
reference is 275,682.6198 um2 (`hw/soc/out/small-pmp/area.rpt`).

| Block | Cells | Flops | Area, um2 | kGE | % of Ibex |
|---|---:|---:|---:|---:|---:|
| `soc_gpio`, alone, `flow/syn_soc.sh` | 779 | 144 | **13,162.8672** | 1.814 | 4.77 % |

**[fact]**. The 144 flip-flops are 16 x 5 configuration registers, 16 x 3
synchroniser and history stages, and 16 flags, which is every bit the
file declares.

And the whole SoC, `flow/syn_soc_top.sh` at `SOC_MEM=sram`, 20 ns, the
configuration `docs/61` measured:

| Design | Cells | Flops | Area, um2 |
|---|---:|---:|---:|
| HEAD, from a clean worktree at `1d4a3e6` | 42,518 | 5,263 | 624,429.9180 |
| with `soc_gpio` | 42,748 | 5,407 | 639,079.6482 |
| **difference** | **+230** | **+144** | **+14,649.7302, +2.346 %** |

**[fact]**. The HEAD row reproduces `docs/61`'s cell count, flip-flop
count and area exactly, which is what licenses the difference. The
flip-flop delta is the block's exactly; the area delta is 1,486.86 um2
more than the block alone, which is `docs/45` section 4.3's effect —
the mapper places a block differently inside a different design — and
is reported rather than reconciled.

**What the numbers do not say.** No frequency was measured, nothing
here has been through STA at any corner or through place-and-route, and
the new pins have no pad and no I/O timing. `docs/38` section 10 item
3's obligations now have sixteen more pins of company.

---

## 8. The QSPI candidate: does sv2v carry OpenTitan's `spi_host`?

### 8.1 What was fetched, and how it is pinned

`hw/soc/tools.soc.mk` gains four checkouts under `hw/soc/ext/`, by the
Ibex rule — fetched by commit, gitignored, never vendored, never edited,
`soc-toolcheck` refusing a dirty tree **[fact]**:

| Checkout | Commit | Licence | How it was read |
|---|---|---|---|
| `lowRISC/opentitan` | `1e1dace7` | Apache-2.0 | sparse: `hw/ip/spi_host`, `prim`, `prim_generic`, `tlul`, `spi_device/rtl`, `top_earlgrey/rtl`, `dv/sv/dv_utils` |
| `lcapossio/spacewire_reloaded` | `450d2254` | LGPL-2.1-or-later, `LGPL-2.1.txt` and an SPDX tag per file | whole |
| `freecores/can` | `470f0e7a` | LGPL-2.1-or-later per file header, with the Bosch CAN protocol licence notice `docs/03` records | whole |
| `alexforencich/verilog-i2c` | `a65be404` | MIT, `COPYING` | whole |

None publishes releases, so there is no archive to sha256; the commit id
is the content hash of the tree, the same argument `tools.soc.mk` makes
for riscv-formal. OpenTitan is ~220 MB packed and is fetched with
`--filter=blob:none` and a sparse checkout of the closure, about
100 MB.

Against `docs/14`'s recommendation — CERN-OHL-W-2.0 for RTL — Apache-2.0
and MIT are inbound-compatible. The two LGPL cores are the case
`docs/14` section 5.2 argues is a bad fit for silicon and recommends
keeping out of the funded scope. **Fetching them for assessment does
not put them in the design**: nothing under `hw/soc/rtl/` instantiates
any of the four, and this document builds no wrapper for any of them.
Whether an LGPL core may enter the SoC is the owner's decision and
section 9 states what it would buy.

### 8.2 The chain, scripted

`hw/soc/flow/sv2v_spi_host.sh` does five things and stops **[fact]**:

1. Computes the module closure of `spi_host.sv` by reading
   instantiations out of the source: **52 modules** — 13 in `spi_host`,
   14 in `tlul`, 25 in `prim` and `prim_generic`. A module the closure
   reaches and the checkout lacks is an error there, not three tools
   later.
2. Runs the pinned sv2v v0.0.13 once over **16 packages and the whole
   closure**, with the defines and include paths `flow/sv2v_ibex.sh`
   uses. Ibex is converted a file at a time because upstream's script
   does; this closure is converted together because sv2v resolves
   package-scoped struct types across files and the TileLink ports are
   exactly that. Output: **52 modules, 8,064 lines**, in 0.34 s.
3. Applies **one mechanical rewrite to the generated file, two lines**:
   sv2v renders the unpacked-array parameter default `'{NumRegs{0}}` —
   the RACL policy vector in `spi_host.sv` and `spi_host_reg_top.sv` —
   as `{NumRegs {0}}`, a replication of an unsized literal that IEEE
   1364-2005 does not allow and Icarus refuses with "Concatenation
   operand `'sd0` has indefinite width". Yosys accepts it. The rewrite
   gives the literal a width. **Patches to OpenTitan: zero** — the rule
   `docs/63` applied to Ibex's RVFI declaration, for the same reason.
4. Elaborates `spi_host` at `NumCS = 2` under Icarus **`-g2005` and
   `-g2005-sv`**, so "Verilog-2005" is checked by the strict front end.
5. Synthesises it with `flow/syn_soc.sh`'s recipe.

### 8.3 The answer

**sv2v carries OpenTitan's `spi_host`.** The converter handled a 52-module
closure with packed structs, package-scoped parameters, `import`
statements, interface-free but heavily typed TileLink ports, and the
`prim_subreg` generate idiom of a register top, with one two-line
artefact in an unused parameter default. `docs/38` section 10 item 7
is closed, and `docs/03` section 2.4's coupled decision — "if the sv2v
path is rejected during CPU bring-up, both fall back together" — is
resolved in the direction of keeping both.

Three latch warnings are inferred by Yosys, all on `sv2v_autoblock_1.i`
inside `tlul_adapter_sram` — a `for` loop index that sv2v hoists into a
block-local variable and Yosys sees as a latch. It is a converter
idiom, not a design latch, and the same shape `spacewire_reloaded`'s
translation shows in section 9.1. A synthesis flow that refuses latches
would need it cleaned up.

### 8.4 What it costs, and where the cost is

| Block | Cells | Flops | Area, um2 | kGE | % of Ibex |
|---|---:|---:|---:|---:|---:|
| `spi_host`, `NumCS = 2`, as converted | 27,729 | 5,404 | **472,117.6152** | 65.051 | **171.3 %** |

**[fact, `hw/soc/gen_spi_host/area.rpt`]**. Yosys took 23.9 s and
951 MB.

That is 1.7 Ibex cores for a SPI host, and the reason is storage.
`spi_host_reg_pkg.sv` fixes `TxDepth = 72` and `RxDepth = 64` words of
32 bits — 4,352 bits of FIFO — as `parameter int` in a package
generated from the block's hjson, which after conversion is a
`localparam` folded into every module that reads it. Those 4,352 bits
are **about 80 % of the 5,404 flip-flops [estimate, arithmetic on the
package constants against the measured count]**, mapped to flip-flops
because this flow has no SRAM macro small enough to hold them and no
`prim_ram_1p` implementation bound. The remainder is the command queue,
the alert sender, the TileLink integrity encoders and decoders, the
RACL error arbiter and the core itself.

Two of those are worth naming because a wrapper would have to feed
them. `spi_host_reg_top` instantiates `tlul_cmd_intg_chk`: **every
TileLink command must carry a correct 57/64 SECDED integrity code over
its address, data and control fields, or the register top reports an
integrity error and errors the response.** An APB-to-TileLink bridge
therefore has to generate that code — `tlul_cmd_intg_gen.sv` is in the
checkout and could be converted alongside — and the `prim_alert_sender`
expects an alert receiver's handshake on `alert_rx_i` or it sits in its
initial state. Neither is hard; both are cost that a from-scratch block
does not carry, and both would be inside the bridge's proof.

### 8.5 What a wrapper would be, and why it is not here

An APB-to-TileLink-UL host adapter: one outstanding request, `a_valid`
held until `a_ready`, `d_ready` high, the response's `d_error` mapped
to `PSLVERR`, the integrity code generated on the way in and checked on
the way out. TL-UL has more rules than APB — a source id, a size, a mask
that must be consistent with the address, an opcode that must match the
response — and the proof would have to state them from the
specification, which is what `docs/39` section 5.3 did for APB. That is
a document of its own, and it is not started here for a reason section
13 argues: the block behind it is 65 kGE with its depths locked in a
generated package, and the choice between wrapping it and writing a
smaller controller is a decision with a number behind it now, which it
was not before.

---

## 9. SpaceWire, CAN and I2C: assessed, not built

All numbers are `flow/syn_soc.sh`'s recipe applied to the checkout as
fetched, with no wrapper and no change to any file **[fact]**.

### 9.1 `spacewire_reloaded`

The Verilog-2001 translation `docs/03` section 2.2 called "the first
credible Verilog-language SpaceWire codec found in the open". Fourteen
files, 3,574 lines, under `rtl/verilog/`; the VHDL original is beside it
and is not read.

- **Elaborates** in Icarus at `spw_axi_top` with default parameters,
  no warnings.
- **Licence**: LGPL-2.1-or-later, the whole tree, `LGPL-2.1.txt` and
  an SPDX tag in every source — the "intended-LGPL" of `docs/03` is now
  confirmed at the commit pinned. Section 8.1 says what that means
  against `docs/14`.
- **Bus**: an AXI4-Lite register block of ten registers in a 64-byte
  aperture — `CORE_ID`, `VERSION`, `CONTROL`, `STATUS`, `TXDIVCNT`,
  `TIMECODE_TX`, `TIMECODE_RX`, `ERROR`, `IRQ_ENABLE`, `IRQ_STATUS`,
  from the README — and an **AXI4-Stream** pair for the N-char data
  path. A wrapper is therefore two things: an APB-to-AXI4-Lite master,
  five channels, and an APB-visible FIFO front end for the two
  streams. The register block is small; the stream front end is where
  the design decisions are — depth, interrupt thresholds, and whether
  the frozen slot description's "one DMA channel" is honoured or
  declined the way `docs/51` section 12 declined descriptor rings.
- **Area**, two configurations:

| Configuration | Cells | Flops | Area, um2 | kGE |
|---|---:|---:|---:|---:|
| defaults, `RXFIFOSIZE_BITS = TXFIFOSIZE_BITS = 11` | 160,777 | 37,258 | 3,099,209.60 | 427.030 |
| 64-entry FIFOs, `RXFIFOSIZE_BITS = TXFIFOSIZE_BITS = 6` | 6,589 | 1,526 | **127,252.7550** | **17.534** |

The default is two 2,048-entry, 9-bit FIFOs in flip-flops — 36,864
bits, which is where 37,258 flip-flops come from; upstream's own Yosys
census in its README reports 36,957 flip-flops at the same defaults,
which agrees. At 64 entries the link core is **17.5 kGE, 6.3 % of
Ibex**, and that is the honest size of a SpaceWire codec on this flow
with its buffering left to the wrapper.

- **One latch** inferred at the small configuration, two at the
  default, both on a `for` loop index `i` in `spwrecv.v` — the same
  translation idiom as section 8.3's, and the same cleanup obligation.
- **The observability audit `docs/03` required is not done.** The
  Verilog was read for its module structure and its parameters, not
  audited state element by state element for `docs/03` rule 2.
  `spwlink.v` has 40 `reg` declarations and one combinational `always`
  block, which is the shape of hand-auditable code, and that is an
  observation, not the audit.

### 9.2 Mohor CAN

Thirteen Verilog files, 6,592 lines. LGPL-2.1-or-later, with the Bosch
protocol-licence notice in every header that `docs/03` section 2.1
recorded as a commercialisation cost. **Elaborates** at `can_top` with
`CAN_WISHBONE_IF` defined — but only with `bench/verilog/` on the
include path, because every RTL file includes a `timescale.v` that
lives in the bench directory rather than beside the RTL. A portability
wart, not a defect. **7,324 cells, 1,456 flip-flops, 131,430.34 um2,
18.109 kGE** — the Wishbone interface is a byte-wide register file, so
the APB wrapper would be an APB-to-Wishbone-classic bridge plus a
32-to-8-bit lane adapter, which is the smallest bridge in this set.

### 9.3 `alexforencich/verilog-i2c`

`i2c_master_wbs_8` with `i2c_master` and `axis_fifo`, 1,849 lines, MIT.
**Elaborates**, with ten Icarus width warnings from upstream's own
port connections (`s_axis_tkeep` and friends fed 32-bit zeros). **4,413
cells, 1,079 flip-flops, 90,471.69 um2, 12.466 kGE** with the three
32-deep FIFOs the parameters default to; the FIFOs are parameters here,
unlike `spi_host`'s, so a smaller instance is a Makefile line. The bus
is Wishbone with an 8-bit data path, the same bridge shape as CAN's;
an AXI4-Lite variant (`i2c_master_axil`) is in the same directory.

### 9.4 The bridge question, priced

| Core | Native bus | Bridge shape | Proof surface |
|---|---|---|---|
| `spi_host` | TileLink-UL, with command integrity | APB to TL-UL host, integrity generated and checked | source, size, mask, opcode consistency; integrity; one outstanding |
| `spacewire_reloaded` | AXI4-Lite registers, AXI4-Stream data | APB to AXI4-Lite master; a FIFO front end for two streams | five-channel handshake; stream back-pressure; FIFO accounting |
| Mohor CAN | Wishbone classic, 8-bit | APB to Wishbone, lane adapter | `stb`/`ack` sequencing, `cyc` framing |
| `verilog-i2c` | Wishbone classic, 8-bit | the same bridge | the same |

**One APB-to-Wishbone bridge serves two of the four cores**, and that
is the strongest structural argument in this table: it is the bridge
whose proof, once done, is reused.

### 9.5 The bridge, built (added 2026-09-15)

The bridge section 9.4 priced now exists and is proved on its own,
before either core is wrapped, for the reason section 2 gave: when the
first wrapper fails, the failure should be in the wrapper. Three files,
the same trio as `soc_apb_bridge`'s:

| File | What |
|---|---|
| `hw/soc/rtl/soc_apb_wb.v` | AMBA 3 APB completer to Wishbone B3 classic initiator, 8-bit data, with the 32-to-8 lane adapter |
| `hw/soc/formal/soc_apb_wb_props.v` | the properties, included into the module under `` `ifdef FORMAL `` |
| `hw/soc/formal/soc_apb_wb.sby` | `bmc`, `prove`, `cover`; `smtbmc yices`; the same depths as `soc_apb_bridge.sby` |

`.gitignore` gains the job's two working-directory lines by section
12's rule. `hw/soc/formal/Makefile` does not gain a target in this
section, and the formal-count line in `docs/00-index.md` is not brought
forward here; this job is one job of three tasks toward it.

**What the two cores actually present**, read from the pinned
checkouts, which is where "32-to-8 lane adapter" in sections 9.2 and
9.3 comes from **[fact]**:

| Core | Address | Data | Handshake | Not present |
|---|---|---|---|---|
| `can_top.v` with `CAN_WISHBONE_IF` | `wb_adr_i[7:0]` | `wb_dat_i[7:0]`, `wb_dat_o[7:0]` | `wb_cyc_i`, `wb_stb_i`, `wb_we_i`, `wb_ack_o` | SEL, ERR, RTY |
| `i2c_master_wbs_8.v` | `wbs_adr_i[2:0]` | `wbs_dat_i[7:0]`, `wbs_dat_o[7:0]` | `wbs_cyc_i`, `wbs_stb_i`, `wbs_we_i`, `wbs_ack_o` | SEL, ERR, RTY |

Both are byte-addressed byte-wide register files; both are classic,
not pipelined; neither has a select, error or retry pin. The bridge has
all three anyway, because they are the B3 initiator interface and a
bridge without them would be re-proved for the first core that has
them; at these two instantiations `err_i` and `rty_i` are tied low and
`sel_o` is left open. The CAN core resynchronises `cyc & stb` into its
own clock domain and pulses `ack` once; the I2C core toggles `ack`
every cycle it sees `stb`. Both therefore need what a classic
initiator promises and a pipelined one does not: the strobe held with
stable controls until the acknowledge, then dropped.

**The lane mapping, and why it is this one.** One APB transfer is one
Wishbone cycle. ~~`adr_o` carries the whole APB offset, and the byte
travels on the lane of `PWDATA` / `PRDATA` that `PADDR[1:0]` names:~~
*Corrected 2026-09-15: the byte travels on the lane `PSTRB` names and
`adr_o` carries the word offset with that lane in its low two bits.
The table below is the first draft's, left standing; the correction
after it says why it could not be driven and gives the table that
replaced it.*

| `PADDR[1:0]` | write: `dat_o` | read: `prdata_o` |
|---|---|---|
| `00` | `pwdata[7:0]` | `{24'h0, byte}` |
| `01` | `pwdata[15:8]` | `{16'h0, byte, 8'h0}` |
| `10` | `pwdata[23:16]` | `{8'h0, byte, 16'h0}` |
| `11` | `pwdata[31:24]` | `{byte, 24'h0}` |

That is the lane an Ibex byte access already uses — `lb`/`lbu` at
address A takes `rdata[8*A[1:0] +: 8]`, `sb` at A places the byte
there — so a driver reads and writes the cores' byte registers with
byte accesses at their natural byte offsets and shifts nothing. A word
access reaches lane 0 only. ~~`PSTRB` is not consulted, the position
`soc_top.v`'s note takes for every completer in this SoC.~~ *Corrected
2026-09-15: `PSTRB` is the only thing consulted; `PADDR[1:0]` is not,
and the Ibex byte access the previous sentence describes never puts
its offset there. See the correction.* Truncating
`adr_o` to the core's own width (8 bits, 3 bits) and inverting the
reset (both cores are active-high) belong to the instantiation.

**Correction, 2026-09-15: the lane is the strobe's, not the
address's.** The table above was written for a requester that puts the
byte offset in `PADDR[1:0]`, and the proof passed against that
requester. This fabric has no such requester, for three facts read
from the pinned sources **[fact]**:

- Ibex word-aligns every data address it issues.
`hw/soc/ext/ibex/rtl/ibex_load_store_unit.sv` at the pinned commit
`34b0705`, under the comment "output data address must be word
aligned" (lines 718-722): `data_addr_o = {data_addr[31:2], 2'b00}`.
The byte offset travels in `data_be_o`, whose generation (the BE
block from line 137) is a function of the access type and the offset
alone — a byte at offset 1 is `4'b0010`, at offset 3 `4'b1000`, for
loads exactly as for stores — and a load takes its byte back from the
lane the enable named (`rdata_b_ext`, selected by `rdata_offset_q`,
from line 324).
- `soc_bus.v` line 326 passes `md_be_i` through as `s_be_o`,
unchanged.
- `soc_apb_bridge.v` lines 106-109 capture `addr_i[19:0]` into
`paddr_o` and `be_i` into `pstrb_o` unconditionally, reads and writes
alike; `soc_apb_bridge_props.v` A11 proves both reach the completer.

So at every APB completer `PADDR[1:0]` is `2'b00` for every CPU access
and `PSTRB` alone carries the byte offset. The first draft therefore
reached only offsets `0, 4, 8, ...` of the CAN core's 256 registers and
only offsets `0` and `4` of the I2C core's eight, and a byte store to
any other register landed in the aligned one carrying `PWDATA[7:0]`.
Measured on the first-draft source — the `prove` job's `src/` copy,
saved before the re-run below replaced it — with a scratch Icarus
testbench that drives each request as Ibex issues it, through a
byte-wide classic target preloaded `mem[i] = 0x10 + i` **[fact]**:

| Request, as Ibex issues it | First draft, `PADDR[1:0]` lane | Corrected, `PSTRB` lane |
|---|---|---|
| `sb 0x5A` at byte offset 1: `PADDR 0x000`, `PSTRB 0010`, byte on `PWDATA[15:8]` | target saw `adr 0x000`, `dat 0x00`; `mem[0]` became `0x00`, `mem[1]` untouched | target saw `adr 0x001`, `dat 0x5A`; `mem[1]` became `0x5A` |
| `sb 0xA5` at byte offset 3: `PSTRB 1000`, byte on `PWDATA[31:24]` | `adr 0x000`, `dat 0x00` | `adr 0x003`, `dat 0xA5` |
| `lbu` at byte offset 1: `PSTRB 0010`; Ibex takes `PRDATA[15:8]` | `adr 0x000`, `PRDATA 0x00000000`; Ibex reads `0x00` | `adr 0x001`, `PRDATA 0x00005A00`; Ibex reads `0x5A` |
| `sh` at byte offset 2 of word 1: `PADDR 0x004`, `PSTRB 1100`, `PWDATA 0x77660000` | `adr 0x004`, `dat 0x00` | `adr 0x006`, `dat 0x66`, the lowest strobed byte |

The testbench and the first-draft source are not in the tree — the
draft was never committed, and the formal work directories now hold
the corrected source — so that table is a record of the run, and the
three citations above are what the tree can be checked against.

**The corrected contract.** `pstrb_i` is a port. The lane is the
lowest set bit of `PSTRB`, lane 0 when none is set, and `adr_o =
{paddr[11:2], lane}`, so the target is addressed with the byte offset
the software wrote:

| `PSTRB` | lane | write: `dat_o` | read: `prdata_o` |
|---|---|---|---|
| `???1` | 0 | `pwdata[7:0]` | `{24'h0, byte}` |
| `??10` | 1 | `pwdata[15:8]` | `{16'h0, byte, 8'h0}` |
| `?100` | 2 | `pwdata[23:16]` | `{8'h0, byte, 16'h0}` |
| `1000` | 3 | `pwdata[31:24]` | `{byte, 24'h0}` |
| `0000` | 0 | `pwdata[7:0]` | `{24'h0, byte}` |

A half-word or word access reaches its lowest strobed byte only:
`1100` is lane 2, `0110` is lane 1, `1111` is lane 0, and a read with
no strobe is lane 0. `PADDR[1:0]` is not consulted and carries the
`_unused_` tie with the reason, beside `penable_i`'s. What changed
with it: E4 holds `PSTRB` stable with the rest of the payload, which
`soc_apb_bridge_props.v` A3 proves of the fabric's requester; D1
states the address as the word offset with the strobe's lane and the
data as the byte from that lane; D2's lane is the strobe's; the lane
covers are stated as Ibex issues the request — `PADDR[1:0]` zero, a
one-hot `PSTRB` — so that the shape that was wrong is the shape that
is covered; and three more covers were added the same day as
witnesses for the two target misbehaviours the properties tolerate (a
termination in the SETUP cycle before the strobe is up, ACK and ERR
together) and for ACCESS without SETUP. The bridge is now the one
completer in the SoC that consults `PSTRB`. `soc_top.v`'s
`_unused_pstrb` note — "neither peripheral implements sub-word writes"
— stays true of the completers it was written for and is the
instantiation's to retire, with a dated correction there, when this
bridge is wired in.

**The design.** Three states. `PSEL` in idle launches the cycle — that
is SETUP for a requester that obeys APB, and APB guarantees the payload
from SETUP, so waiting for ACCESS would add a cycle for nothing; a
requester that presents ACCESS without a SETUP is served from ACCESS
instead, so nothing hangs on that mistake. The strobe cycle holds
`cyc`, `stb`, `sel`, `adr`, `we`, `dat` until `ack`, `err` or `rty`.
The response is registered: the data byte and the error flag are
captured at the terminating edge and `PREADY` rises the next cycle
from the copies, so there is no combinational path from any Wishbone
input to any output and a target whose `ack` is combinational from
`stb` cannot close a loop through the bridge. `RTY` is an error to
APB, which has no retry: a hardware retry loop would turn a target
that keeps saying "retry" into a bus that never answers, the hang
`docs/39` section 4 chose APB to exclude. Three cycles per access with
a zero-wait target, plus the target's wait states.

**The properties**, every one a clause of a specification that
predates the RTL, per `docs/39` section 5.3 and the rule
`soc_apb_bridge_props.v` states about restated implementations:

- **E1-E5, assumed**: the APB requester's clauses — PENABLE only with
  PSEL; SETUP one cycle then ACCESS; ACCESS held until PREADY; payload
  stable from SETUP to the end of ACCESS (`PSTRB` included, from the
  2026-09-15 correction); PENABLE low after PREADY.
  They are the clauses `soc_apb_bridge_props.v` A1-A5 *prove* of the
  fabric's requester, which is what makes the composition sound.
  Nothing is assumed about the target.
- **I1**: the ghost tracks the state machine; the one property that
  names the design's own state, for induction and nothing else.
- **W1-W8, Wishbone B3 initiator side** (sections 3.1.3, 3.1.4, 3.2.1,
  3.2.2, 3.5): STB only inside CYC; single cycles only, CYC never held
  across an idle strobe; no cycle without an APB transfer in ACCESS;
  strobe and controls held until termination; STB and CYC drop the
  cycle after termination; SEL equals STB; exactly one termination per
  APB transfer, no strobe after it; idle bus low.
- **P1-P3, APB completer side**: PREADY exactly one cycle after the
  termination of the cycle this bridge launched and never otherwise;
  PREADY only in ACCESS; PSLVERR only with PREADY.
- **D1-D2, the adapter**: while the strobe is up (and through the
  PREADY cycle, see below) the target sees ~~the whole offset~~ *the
  word offset with the strobe's lane in its low two bits (corrected
  2026-09-15)*, the
  direction and the byte from the named lane; in the PREADY cycle
  PSLVERR is the target's ERR or RTY and, on a read, the byte the
  target returned sits on the named lane with the other three zero.
  The lane is the one `PSTRB` names, per the correction above.
- ~~**Nine covers**~~ *Fifteen covers, from 2026-09-15*: read, write,
  ERR and RTY completions; zero and three
  wait states; a SETUP in the cycle after PREADY; ~~a byte on the top
  lane in and out~~ *the lanes as Ibex issues them — `lbu` on lane 3
  in, `sb` on lane 1 out, a half-word strobe on lane 2, a word strobe
  and a no-strobe read on lane 0 — and the three witnesses the
  correction names: a stray termination in SETUP, ACK with ERR, ACCESS
  without SETUP*.

**Results**, `sby` as `tools.mk` resolves it, from `hw/soc/formal/`
**[fact]**:

| Task | What | Result |
|---|---|---|
| `bmc` | bounded, depth 24 | PASS, 7 s |
| `prove` | k-induction, depth 12 | **PASS**, base case and induction, 2 s |
| `cover` | depth 24 | PASS, **9 of 9** reached: zero-wait termination and the write lane at step 3, the four completions and the read lane at step 4, back-to-back at step 5, three wait states at step 6; 2 s |

*The table above is the first draft's run of 01:44 on 2026-09-15 and
is superseded. Re-run 2026-09-15 07:02 on the corrected source with
the same pinned `sby`, from `hw/soc/formal/`; the `src/` copies in the
three work directories are now this source* **[fact]**:

| Task | What | Result |
|---|---|---|
| `bmc` | bounded, depth 24 | PASS, 3 s |
| `prove` | k-induction, depth 12 | **PASS**, base case and induction, 1 s |
| `cover` | depth 24 | PASS, **15 of 15** reached: zero-wait termination, the `sb` lane, the half-word and word lanes and the stray termination at step 3; the four completions, the `lbu` lane, the no-strobe read, ACK with ERR and ACCESS without SETUP at step 4; back-to-back at step 5; three wait states at step 6; 3 s |

**The proof found a defect in the RTL before a transaction was ever
driven.** The first `prove` run passed its base case and failed
induction at D2, from a state in which a separate two-bit register
holding the lane — a copy of `adr_o[1:0]`, captured in the same cycle
— disagreed with the address: unreachable, but not excluded, and the
byte came back on lane 0 for an offset ending in `11`. The copy is
gone; `prdata_o` decodes its lane from `adr_o` itself, and a register
that does not exist cannot disagree. D1 was then extended to hold
through the PREADY cycle as well as the strobe, which B3 does not ask
for and which is where D2's lane is anchored to the request; it is the
one property that changed, it became stronger, and the file says so.
*2026-09-15: the lane correction above then changed E4, D1, D2 and
the covers as well; the induction defect and its fix are as
described, and the proof that found it did not find the lane, because
a proof checks the contract it is given.*

**Lint and size.** `verilator --lint-only -Wall` and `iverilog -g2005
-Wall` are clean **[fact]**; Verilator's one finding, `penable_i`
unused, is a decision — the response lands in ACCESS by the
requester's own rules — and is recorded with the `_unused_` idiom
`soc_top.v` uses for `pstrb` (*2026-09-15: `paddr_i[1:0]` carries the
same tie since the correction, and both linters stay clean on the
corrected file*). With `flow/syn_soc.sh`'s recipe on the
block alone, 20 ns, typical liberty, in a scratch directory like
section 9's runs **[fact]**:

| Block | Cells | Flops | Area, um2 | kGE |
|---|---:|---:|---:|---:|
| `soc_apb_wb` | 121 | 33 | 2,964.73 | 0.408 |
| `soc_apb_bridge`, the requester half, same recipe | 201 | 94 | 6,437.49 | 0.887 |

All 33 flip-flops are `sg13g2_dfrbpq_1`; no latch. The whole bridge is
under half a kGE, which is the number section 9.2's "smallest bridge
in this set" was waiting for.

*Re-measured 2026-09-15 on the corrected RTL, same recipe, same
liberty at `c4b8b4e5`* **[fact]**. The two rows above were produced
with Yosys 0.67+94, the oss-cad-suite build, and not with the Yosys
0.33 that `tools.soc.mk` resolves and `syn_soc.sh` itself would run;
both are given so that the comparison with the row above is like for
like and the number the flow would print is on record too:

| Block | Cells | Flops | Area, um2 | kGE |
|---|---:|---:|---:|---:|
| `soc_apb_wb`, corrected, Yosys 0.67+94 as the rows above | 157 | 33 | 2,973.50 | 0.410 |
| `soc_apb_wb`, corrected, Yosys 0.33 as `syn_soc.sh` runs it | 164 | 32 | 2,953.81 | 0.407 |

The strobe decode costs 36 cells and 8.77 um2 like for like. All
flip-flops are `sg13g2_dfrbpq_1` in both, no latch in either, and the
bridge is still under half a kGE.

**Guard tests.** `.venv/bin/python -m pytest sw/tests -q -k "spdx or
lint or rtl or formal"`: 17 passed, 1 failed **[fact]**. The failure is
`test_the_newest_formal_count_in_the_documents_matches_the_tree`,
because the tree's task count has moved past `docs/00-index.md`'s
newest figure; this job's three tasks are part of that movement and
the figure is not corrected in this section.
*2026-09-15, after the correction: `1 failed, 17 passed, 508
deselected`, the same failure, now quoting "the tree has 81 across 20
jobs" (`assert 64 == 81`); three of the twenty are untracked jobs of
work in flight, this one among them* **[fact]**.

**What this section does not cover.** The bridge is not instantiated:
`soc_top.v` is unchanged, no slot is promoted, no core is wrapped, and
not one transaction has been driven through it in simulation — the
proof is standalone, which is what `docs/39` section 5.3 asks of a
bridge and all it asks. Liveness is not proved: a target that never
terminates holds PREADY low forever and every property still holds;
the covers show completion is reachable, which is weaker. The target is
not assumed to obey Wishbone at all. The CAN core's two-clock register
path is the wrapper's problem, not the bridge's.

---

## 10. Defects found

1. **The guard against source-list drift had a fifth list nothing
   guards.** `docs/61` added
   `test_every_flow_that_builds_soc_top_reads_every_module_it_instantiates`
   after `docs/51` updated one of four source lists. `soc_gpio.v` was
   added to all four flows that test names, and all six flows in
   `hw/soc/flow/` that read `soc_uart.v`, and `test_the_whole_soc_elaborates_as_one_design`
   still failed — with the error `docs/57` section 3.2 quotes, "Module
   `\soc_gpio` referenced in module `\soc_top` ... is not part of the
   design" — because that test elaborates from its own literal list.
   The list is extended and now says what it is. It is kept literal
   rather than derived from `soc_top.v`, because a guard that generated
   its list from the file it guards would pass on any list.
2. **Check 28's first expectation was wrong, and the diagnostic line
   said where.** Section 5.
3. **sv2v's unsized replication in a parameter default.** Section 8.2
   item 3. Not a defect in the design, and recorded as the one place
   the generated file is not what the converter emitted.

---

## 11. What the checks do not cover

Stated separately from "not built", because this repository has been
bitten by the difference.

- **No pad.** The proof and the suite drive `gpio_i` by hand; the
  whole-SoC run drives it through a model of a pad that is one line of
  Verilog. Nothing here says what a real pad does with `gpio_oe_o`, and
  the design has no pad ring, no pull-up, no drive control and no
  open-drain mode.
- **Two synchroniser stages are present; whether two is enough is not
  an RTL property.**
- **The whole-SoC run exercises one edge on one pin at one vector.**
  The level mode, the other fifteen pins' interrupts and the mask on
  the way out are the cocotb suite's, not the program's.
- **The GPIO block has no fault model.** An upset in `DIRECTION` turns
  an input into an output, which on a board is contention; nothing
  reports it and no campaign has been run on the block.
- **The four candidate cores were elaborated and synthesised, not
  simulated.** Not one transaction has been driven through any of
  them here. Their areas are areas of the checkouts as fetched, with
  no wrapper and no configuration beyond the parameters named.
- **`spacewire_reloaded`'s observability audit is not done.** Section
  9.1.
- **The whole-SoC area is synthesis at a 20 ns target with the SRAM
  boundary; no timing, no place-and-route, no power for anything
  here.**
- **No fault-injection campaign was re-run.** `flow/fi_core.sh` and
  `flow/fi_npu.sh` read `soc_gpio.v` now and their benches tie the pins
  to an empty board, but neither was executed; whether the campaigns of
  `docs/42` to `docs/58` reproduce on a design with 144 more flip-flops
  is a measurement with its own cost, the position `docs/61` took for
  the accelerator, and it is not taken here.
- **`test_the_slot_and_the_line_are_the_frozen_maps` reads the map, not
  the RTL.** That the RTL is at that slot is `test_memmap.py`'s textual
  check on `soc_top.v` plus check 28, which reaches it.

---

## 12. Files touched outside `hw/soc/`, and why none is frozen

`docs/34` section 2 pins `hw/rtl/` by blob and section 5 the flow
configurations. None of the following is in either set **[fact]**:

| File | Change |
|---|---|
| `regmap/memmap.yaml` | one field: GPIO `status` reserved to implemented. No address, slot, source number, line or device id moved |
| `docs/memmap-soc.md`, `sw/golden/memmap_gen.py`, `hw/soc/rtl/soc_memmap.vh`, `hw/soc/rtl/soc_pnp_rom.vh`, `hw/soc/rtl/soc_apb_pnp_rom.vh`, `hw/soc/tb/sw/soc_memmap.h`, `hw/soc/tb/sw/memmap.ld` | regenerated; the device-table record for slot 2 now carries status 1 |
| `sw/tests/test_soc_synthesis_guards.py` | `soc_gpio.v` in the whole-SoC elaboration list, section 10 item 1 |
| `docs/65-gpio-and-the-interface-ip-assessment.md` | this document |
| `docs/00-index.md` | one row, and one dated correction in section 2.2 |
| `docs/60-soc-datasheet.md`, `docs/38-ibex-bringup.md`, `README.md` | dated in-place corrections by `docs/64`'s rule: the "no GPIO" and "untested `spi_host`" statements were true when written and now name this document |
| `.gitignore` | the SymbiYosys working directories of the new job and `hw/soc/gen_spi_host/`, by the rule every prior document states for these two kinds of directory |

Everything else is under `hw/soc/`. `hw/soc/{ext,tools,gen,genp,gen_spi_host,out}`
remain gitignored.

---

## 13. What the next block should be

**QSPI**, and the question is not whether but how. Two routes, priced
by this document:

**Wrap `spi_host`.** A verified, silicon-proven core with quad mode,
`docs/03`'s first choice, now known to convert. Cost: an APB-to-TL-UL
bridge with integrity generation and a proof against the TL-UL rules
(section 8.5), an alert receiver stub, and **65 kGE of which four fifths
is FIFO storage at depths fixed in a generated package** — reducing
them means either editing the checkout, which the pinning rule forbids,
or regenerating `spi_host_reg_pkg.sv` from its hjson with OpenTitan's
own tooling, which is a second toolchain dependency.

**Write a QSPI flash reader on APB.** `docs/03` section 2.2 costed it at
60-100 hours **[estimate, docs/03]**: a command/address/dummy/data
sequencer, quad read, two chip selects, a small FIFO, and later the
execute-in-place windows the map has reserved at `QSPI3` and `QSPI4`,
which `spi_host` does not provide either — it is a register-driven host
and every word of a weight image would cross the CPU. No bridge, no
integrity, no third toolchain; the observability of `docs/03` rule 1 for
free; a proof the shape of `soc_uart`'s rather than TileLink's.

**The recommendation is the second**, for the reason section 8.4
measures: the block this project would inherit is bigger than its CPU,
and the part of it this SoC needs — a sequencer and a shift register —
is the part that is small. What the first route would have bought,
upstream verification, is worth less here than it looks: the wrapper
and the FIFO configuration are where the defects would be, and neither
is upstream's. The decision belongs to the owner; the numbers it rests
on are in section 8.4 and were not available before this document.

**Before SpaceWire, decide the licence.** Section 9.1 confirms LGPL at
the pinned commit and `docs/14` section 5.2 says what that means. The
17.5 kGE codec is buildable and the AXI bridge is a document's work; the
decision that gates it is not an engineering one.

**After that, one APB-to-Wishbone bridge, proved once, serves CAN and
I2C both.** Section 9.4.

*2026-09-15: the bridge is built and proved, section 9.5. What remains
after the licence decision is the two wrappers, and neither is started.
Later the same day its lane contract was corrected — the lane is the
strobe's, not the address's, section 9.5's dated correction — before
anything was wired to it.*

---

## 14. Reproducing this

```
python regmap/generate_memmap.py
.venv/bin/python -m pytest sw/tests                     # 402 passed
scripts/run_cocotb.sh                                   # 294 passed, 0 failed

cd hw/soc/tb/cocotb && make -f Makefile.soc_gpio        # 14 tests
cd hw/soc/formal && make gpio                           # 4 tasks
cd hw/soc/formal && make                                # every job, section 4.4

hw/soc/flow/sim_soc.sh hw/soc/out/s65-sim-gpio          # 28 checks, 217,634 cycles
SW_DEFINES=-DWDOG_RESET_DEMO hw/soc/flow/sim_soc.sh hw/soc/out/s65-sim-wdog

hw/soc/flow/syn_soc.sh soc_gpio                         # 13,162.8672 um2
SOC_MEM=sram hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s65-gpio

make -f hw/soc/tools.soc.mk fetch-opentitan fetch-spacewire_reloaded \
                            fetch-can fetch-verilog-i2c
hw/soc/flow/sv2v_spi_host.sh                            # section 8
```

The whole-SoC baseline in section 7 was produced from a clean
`git worktree` at `1d4a3e6` with `hw/soc/{gen,genp,tools,ext}`
symlinked in, and the SpaceWire, CAN and I2C syntheses of section 9
were run with `flow/syn_soc.sh`'s recipe against the checkouts under
`hw/soc/ext/` directly; the scripts for those three are not tracked,
because nothing decides on them yet, and the recipe is the one every
tracked synthesis script in `hw/soc/flow/` already spells out.
