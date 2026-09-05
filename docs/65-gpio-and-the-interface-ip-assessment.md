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
