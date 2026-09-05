# 66 — The QSPI flash controller, and the NPU fed from where a flight part would feed it

`docs/65-gpio-and-the-interface-ip-assessment.md` section 13 named
QSPI the next block and put a number under each of the two ways to get
one: wrap OpenTitan's `spi_host`, which converts cleanly and measures
65 kGE with four fifths of it FIFO storage at depths fixed in a
generated package, or write a flash reader on APB from scratch. It
recommended the second. This document takes it, and it takes it for the
reason `docs/51-npu-integration.md` section 14 item 4 states: weights
are loaded "a register at a time" from arrays the boot ROM image
carries, which is a bring-up convenience, and a flight part holds its
weight image in external flash. QSPI is the one interface the NPU itself
needs.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
an intention with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash. Nothing in `hw/rtl/`, `hw/tb/`, `formal/`, `tt/` or
`hw/openlane/` was modified; `hw/tb/Makefile.fi` was not invoked.
Section 13 lists every file touched.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| What is built? | **A register-mode QSPI flash controller with two chip selects**, `hw/soc/rtl/soc_qspi.v`, in slot `0x014` at `0xFF914000` on fast line 9 — the slot, device id, source number and line the map has carried since `docs/39` and `docs/40`. Software describes one flash transaction in a command register and pulls the data through a one-word receive register; the block drives opcode, 24-bit address, dummy clocks and a data phase of any length on one or four lanes. Sections 3 and 4 |
| Execute-in-place? | **No, deliberately, and the map says so.** The two XIP windows at `0xD0000000` and `0xD8000000` stay reserved, with the reason written into `regmap/memmap.yaml` beside them. Section 2 is the argument: XIP is a seventh fabric port and a re-proof of `soc_bus.v`, and a quad read is about forty system clocks per word on a core with no cache |
| What flash? | **The Winbond W25Q128JV**, modelled from its datasheet (Revision M, 2024-12-24) in `hw/soc/tb/flash_w25q128jv.v`, which applies the AC table's timing at its own terminals and counts every departure from the part's rules. The cocotb suite and the whole-SoC run both end by asserting that count is zero **[fact]**. Section 5 |
| Verified how? | **16 cocotb tests through two modelled devices on a pulled-up wire, 16 of 16 mutations caught; a k-induction proof at the narrowed and the shipped widths, bounded check to depth 40, 12 of 12 covers reached at depth 110** **[fact]**. Section 6 |
| Was the NPU fed from flash? | **Yes.** Check 30 of the bring-up program reads a 16-byte header and the `docs/51` weight words out of the modelled flash on four lanes through the real fabric, checks the header and the checksum, and runs the same inference check 26 runs from the ROM's arrays — against the golden model's answer, computed at build time. **`npu from flash: 0x0000000c events`, fail mask 0** **[fact]**. Section 7 |
| Why a second image? | **The boot ROM.** The 28-check program is 7,794 of the 8,064 bytes the map's 8 KiB ROM leaves above the reset vector, and checks 29 and 30 need 1,800 more **[fact]**. So `-DQSPI_DEMO` builds a second image from the same file, the arrangement `docs/40` established for the watchdog demonstration. Section 7.1 |
| Did the invariant move? | **217,634 with the block present and the program unchanged** — to the cycle **[fact]**. 217,682 with the one refactor the demonstration needs in the shipped program. Section 8 |
| What does it cost? | **1,231 cells, 192 flip-flops, 19,690.62 um2, 2.713 kGE** alone; the second chip select is **23 cells, one flip-flop, 292.95 um2** of that; **+1,136 cells, +192 flip-flops, +17,305.41 um2, +2.708 %** on the whole SoC against a baseline that reproduces `docs/65`'s exactly **[fact]**. Section 9 |
| Sharpest findings? | Two RTL defects found by the proof and not by the suite (a TX word landing on the clock a pause began was stranded; an abort could cut an SCK level short), one found by the model and not by any test (a quad address sent with QE clear drives the part's /HOLD pin), and the source-list guards firing exactly as `docs/61` and `docs/65` built them to. Section 10 |

---

## 2. The scope, decided before the RTL

### 2.1 Register mode, not execute-in-place

GR716B's SPIMCTRL, which `docs/08` section 3.1 modelled the map on, has
both: a user mode in which software drives a command and reads bytes
through registers, and a memory-mapped mode in which the flash appears
in the address space and the CPU fetches from it. This block has the
first only, and the decision rests on three things, all of which were
known before a line of RTL was written.

**XIP makes the block a fabric slave as well as an APB one.**
`soc_bus.v` has six slave ports, hardcoded, with a one-hot decode
proved by `hw/soc/formal/soc_bus.sby` for exactly the regions the map
gives a port. A seventh port is a change to the fabric, a re-proof of
F1 through F9, and a re-measurement of a block four documents have
hardened — `docs/51` section 12 declined a third *master* on the same
grounds. That is a document of its own.

**A quad read without a cache is a fetch-latency contract this core
cannot afford.** A quad I/O read of one 32-bit word is 8 opcode clocks,
6 address clocks, 6 mode and dummy clocks and 8 data clocks — 28 SCK
periods, which at the fastest divider is 56 system clocks plus the
chip-select setup and hold **[fact, the frame the block drives]**.
`docs/50` section 5.2 measured what one extra cycle of memory latency
costs a two-stage core with no cache: 0.97 cycles per RAM response,
about 25 % of run time. An instruction fetch that costs 56 cycles
instead of one is not a slower memory; it is a different execution
model, and it needs the prefetcher, a cache or a copy-to-RAM boot loader
in front of it before it is worth measuring. The honest way to offer
XIP is with that in front of it, and that is not this document.

**The weight loader does not need it.** `docs/51`'s bring-up sequence
writes weight words into the node's `W_DATA_LO`/`W_DATA_HI` registers
one at a time, because that is the die's only weight port. A register
that delivers the next word from flash to software, which then writes
it to the node, is the whole of what the loader needs. Section 7 shows
it doing exactly that.

**What the XIP windows become.** They stay `reserved` in
`regmap/memmap.yaml`, decoding to the error slave as every reserved
region does, and the comment above them now says why and what would
change it: a fabric port, a re-proof, and something in front of the
flash that absorbs the latency. The addresses are frozen so that building
it later renumbers nothing. Nothing about them is silent.

### 2.2 Quad I/O, and the part that defines it

`docs/65` section 13: "quad I/O read is the whole reason for the Q; a
1-bit SPI controller is a different, smaller block." The block has four
data lanes and drives the two quad read commands the part defines —
Fast Read Quad Output (6Bh, 1-1-4) and Fast Read Quad I/O (EBh, 1-4-4,
with the mode byte and four dummy clocks) — as well as the single-lane
reads, the status and identification reads, the write-enable and
status-write commands that set the quad-enable bit, and page program.
Section 4 lists them with the datasheet section that defines each.

The part is the **Winbond W25Q128JV**: 16 MiB, 3-byte addresses, the
QE bit in Status Register-2 gating quad operation, /WP and /HOLD on IO2
and IO3 until it is set. It was chosen because it is the ordinary part
in this class — the one a board designer reaches for — and because its
datasheet was obtainable and readable in this environment (Revision M,
publication release date 2024-12-24, 81 pages). Section 5 is what the
model takes from it.

The block itself knows nothing of the part. Every field in its command
register is generic — an opcode, whether there is an address, whether
the address and the data go on four lanes, how many dummy clocks — and
the part's command set lives in the driver header and the testbench. A
different flash is a different header.

### 2.3 Two chip selects

GR801 has two (`docs/03` section 2.2). So does this block: `NCS` is a
parameter, `soc_top.v` instantiates two, and the bring-up program reads
the pull-ups back through the second one, which on the modelled board
goes to nothing. The cost of the second is measured in section 9:
**23 cells, one flip-flop, 292.95 um2** **[fact]**.

---

## 3. What was built

| File | What it is |
|---|---|
| `hw/soc/rtl/soc_qspi.v` | The block. SPIMCTRL-shaped register file, a sequencer that drives opcode, address, dummy and data phases on one or four lanes, a one-word receive and transmit register with a pause at every word, two chip selects, a deselect gap |
| `hw/soc/rtl/soc_top.v` | Five pins plus four three-wire lanes, a `QSPI_NCS` parameter, the slot decode, the instance, fast line 9 |
| `hw/soc/tb/flash_w25q128jv.v` | The specification on the wire: a behavioural W25Q128JV, section 5 |
| `hw/soc/tb/tb_soc_qspi.v` | The controller on a board with two modelled devices, for cocotb |
| `hw/soc/tb/tb_soc.v` | A modelled device on chip select 0, loaded from the image the build writes; a pass criterion on its violation count |
| `hw/soc/tb/tb_soc_fi.v`, `tb_soc_npu_fi.v` | The pins tied to a board with pull-ups and no flash |
| `hw/soc/tb/cocotb/test_soc_qspi.py`, `Makefile.soc_qspi` | 16 tests against the specification, section 6.1 |
| `hw/soc/tb/cocotb/mutate_soc_qspi.py` | The sixteen mutations, section 6.3, tracked this time |
| `hw/soc/formal/soc_qspi_props.v`, `soc_qspi.sby` | Q1-Q8, section 6.2 |
| `hw/soc/flow/gen_flash_image.py` | The flash images and the header the program checks them against |
| `hw/soc/tb/sw/soc_qspi.h` | Offsets, fields and the part's command set for the program |
| `hw/soc/tb/sw/test_ibex.c`, `crt0.S` | Checks 29 and 30, the `npu_inference` refactor, vector 25, the `QSPI_DEMO` image |
| `hw/soc/flow/sim_soc.sh`, `build_sw_soc.sh` | The model in the source list, the image on the command line |
| `hw/soc/flow/syn_soc.sh`, `syn_soc_top.sh`, `pnr_soc_top.sh`, `fi_core.sh`, `fi_npu.sh` | `soc_qspi.v` in every source list the guard checks |

### 3.1 The register map, and where its shape comes from

The first five offsets follow the shape of GRLIB's SPIMCTRL —
configuration, control, status, receive, transmit — because `docs/08`
section 3 row 15 asks for it and because a driver written for that
family should find the familiar things where it expects them. It has to
be said plainly that `grip.pdf` was not readable in the environment
this block was written in: the offsets and bit names are SPIMCTRL's as
`docs/08` section 2.5 records them and as recalled, and they are **not
claimed as a verbatim mirror** **[estimate]**. Everything from `0x14`
upward is this project's, and the reason is structural: SPIMCTRL's user
mode moves one byte at a time on one lane, and a quad data phase needs
a transaction description.

| Offset | Register | What it holds |
|---|---|---|
| `0x00` | `CONF` | `DIV` (SCK = clk / 2(DIV+1)), `CS` (which chip select) |
| `0x04` | `CTRL` | `RST` abort, `IEN` |
| `0x08` | `STAT` | `BUSY`, `DR` data ready, `DONE` (w1c), `LOST` (w1c), `TXE` |
| `0x0C` | `RX` | the received word; reading it clears `DR` and resumes |
| `0x10` | `TX` | the word to transmit; writing it clears `TXE` |
| `0x14` | `CMD` | `OP`, `DUMMY`, `ADDR`, `AQUAD`, `DQUAD`, `WRITE`, `LEN`; a write starts the frame |
| `0x18` | `ADDR` | 24 bits, sent A23 first |

Three decisions in it are worth recording.

**The data phase pauses at every word.** Four bytes in and the block
holds SCK low with the chip select still asserted, sets `DR` and waits
for software to read `RX`; four bytes out and it waits for `TX`. A data
phase of any length therefore needs one word of storage and no FIFO,
and the flash — which is static and has no minimum clock frequency (the
part's table 9.6 says "D.C.") — simply waits. This is the whole of the
difference between this block and the one `docs/65` section 8.4
measured: the storage is where software is, not where the block is.

**Byte lanes are little-endian.** The first byte off the wire is
`RX[7:0]`, so a 32-bit word stored little-endian in the flash image
reads back as itself on this little-endian core, and the weight image
in section 7 needs no byte swapping.

**`DONE` means "a `CMD` write will be accepted."** It is set when the
deselect gap ends, not when the chip select rises, so a driver that
polls `DONE` and then writes `CMD` cannot lose the write. A `CMD`,
`CONF` or `ADDR` write that arrives while `BUSY` is refused and flagged
`LOST`, rather than taken into a frame that has already captured its
values.

### 3.2 The frame on the pins

SPI mode 0. The chip select falls with SCK low, one half period before
the first rising edge; outputs change on the falling edge and both
sides sample on the rising edge; the chip select rises one half period
after the last falling edge, and every chip select then stays high for
four SCK periods — 8(DIV+1) clocks — before another frame may start.
At DIV = 0 and 100 MHz that gap is 80 ns against the part's 50 ns
deselect time after a write **[fact, table 9.6 tSHSL2]**, and it
lengthens with any slower clock.

The lane discipline is the part's. In every single-lane phase IO0 is
driven, IO1 (the part's DO) is released, and **IO2 and IO3 are driven
high**, because until the QE bit is set they are /WP and /HOLD
(datasheet 4.3, 4.4, 7.1.4) and a released /HOLD that a board pulled
low would pause the flash mid-frame. In a quad address phase all four
lanes are driven; the two mode clocks after it carry FFh on all four
(8.2.11 note 11: "should be set to Fxh", and Fxh keeps the part out of
continuous read mode); and from the first real dummy clock of a quad
read nothing is driven, because 8.2.9 asks for the lanes to be
"high-impedance prior to the falling edge of the first data out clock."
The lanes keep their pattern until the chip select rises, so /HOLD is
never released while the part is selected — a rule the first version of
the block broke and the suite caught (section 10).

### 3.3 The clock, and the constraint on it

Inputs are sampled at the rising edge the block itself generates. The
part drives its output up to tCLQV = 6 ns after the falling edge, so
the half period must exceed 6 ns plus the input path: SCK is bounded
at about 80 MHz **[estimate, 1/(2 x 6 ns)]**, below the part's
133 MHz. At the 20 ns period every synthesis in this repository targets,
DIV = 0 gives 25 MHz SCK; in simulation at 100 MHz it gives 50 MHz, and
the model checks it against the part's 133 MHz for every command and
50 MHz for Read Data (03h). A sampling-delay adjustment for a faster SCK
is not here and section 12 says so.

---

## 4. The commands the driver uses

`hw/soc/tb/sw/soc_qspi.h`, each with the datasheet section that defines
it:

| Opcode | Command | Section | Lanes | Dummy | Needs |
|---|---|---|---|---|---|
| 9Fh | Read JEDEC ID | 8.2.27 | 1-1-1 | 0 | — |
| 05h / 35h | Read Status Register-1 / -2 | 8.2.4 | 1-1-1 | 0 | — |
| 50h | Volatile SR Write Enable | 8.2.2 | 1-0-0 | 0 | — |
| 06h | Write Enable | 8.2.1 | 1-0-0 | 0 | — |
| 31h | Write Status Register-2 | 8.2.5 | 1-0-1 | 0 | 06h or 50h first |
| 03h | Read Data | 8.2.6 | 1-1-1 | 0 | SCK <= 50 MHz |
| 0Bh | Fast Read | 8.2.7 | 1-1-1 | 8 | — |
| 6Bh | Fast Read Quad Output | 8.2.9 | 1-1-4 | 8 | QE |
| EBh | Fast Read Quad I/O | 8.2.11 | 1-4-4 | 2 mode + 4 | QE |
| 02h | Page Program | 8.2.13 | 1-1-1 | 0 | 06h first |
| 66h, 99h | Enable Reset, Reset Device | 8.2.43 | 1-0-0 | 0 | consecutive |

The block sends any of them as a `CMD` word; the header's `FLASH_CMD_*`
constants are those words with `LEN` left for the caller.

---

## 5. The specification on the wire: a modelled W25Q128JV

`hw/soc/tb/flash_w25q128jv.v` was written from the datasheet and not
from the RTL — the vacuity rule of `docs/09` B.1, which this repository
has broken before and which would have made every test below a test
that the controller agrees with itself. What it takes from the
datasheet, by section and table **[fact, the file cites each]**:

- **Table 9.6, the AC characteristics**, applied against `$realtime`
  in nanoseconds: tSLCH 3 ns, tCHSL 3 ns, tCHSH 3 ns, tSHCH 3 ns,
  tSHSL1 10 ns after a read, tSHSL2 50 ns after a write, tDVCH 1 ns
  input setup, tCHDX 2 ns input hold, FR 133 MHz for every instruction
  but Read Data and fR 50 MHz for it, tCLH and tCLL at 45 % of the
  133 MHz period (note 1). On the output side tCLQX 1.5 ns and tCLQV
  6 ns: the model holds the old value for 1.5 ns after the falling
  edge, drives **X** until 6 ns, then the new value — the worst case of
  the table, so a controller that samples too early reads X and fails.
  tSHQZ 7 ns: the outputs stay driven that long after the chip select
  rises.
- **Table 8.1.1**: the JEDEC identification EFh, 40h, 18h.
- **Section 6.1**: mode 0, so a chip select that falls or rises with
  CLK high is a violation.
- **Sections 8.2.9 and 8.2.11**: 6Bh and EBh are refused with QE = 0 —
  the device drives nothing and the lanes read as the pull-ups.
- **Section 4.4**: /HOLD low at a rising edge with QE = 0 is counted,
  because on the part it would pause the device.
- **Section 8.2.5**: 31h without 06h or 50h before it is ignored; the
  non-volatile write (06h) shows BUSY for tW and clears WEL afterwards;
  the volatile write (50h) takes effect at once and WEL stays clear.
  While BUSY, only Read Status is accepted.
- **Section 8.2.11**: M5-4 = 1,0 enters continuous read mode, which
  this controller never leaves, so it is counted.
- **Section 8.2.43**: 66h then 99h resets the volatile state and
  restores the non-volatile QE.
- **Section 8.2.13**: page program ANDs the data into the page, wraps
  within 256 bytes, needs WEL, and a frame that ends mid-byte is
  counted.
- **Table 9.6 note 6**, "4-bytes address alignment for Quad Read", is
  carried as an advisory counter rather than a violation, because the
  note's force is not clear from the table it annotates; the program
  and the suite use aligned quad addresses and assert the counter is
  zero.

Every violation increments `violations`, prints what it was and when,
and every test in the suite and the whole-SoC run end by asserting the
count is zero. The busy times tW, tPP, tSE and tRST default to the
table's maxima (15 ms, 3 ms, 400 ms, 30 us) and **both testbenches scale
them to 2 us** and say so; a 15 ms wait is 1.5 million cycles and
proves nothing a 2 us wait does not. The storage behind the array is
128 KiB, not 16 MiB, and addresses above it read as erased and are
counted.

**What the model does not model.** Dual-lane instructions, QPI mode,
4-byte addressing, wrap reads, the security registers, block and chip
erase, suspend and resume, power-down, the /RESET pin, the write-protect
bits as protection, the unique ID, SFDP, Status Register-3, and any
electrical property. And it must be said once more, because it is the
sentence this document most needs: **a behavioural model is not a
flash.** It has no process, no temperature and no voltage; it does not
age; its timing is a set of inequalities checked in simulation time.
What passing against it establishes is that the controller obeys the
datasheet's published contract as this file states it — not that the
controller works with a device.

---

## 6. Verification

### 6.1 cocotb, through two modelled devices

`hw/soc/tb/cocotb/test_soc_qspi.py`, top level `tb_soc_qspi.v`: the
controller on a board with two W25Q128JV models, the four lanes meeting
on a `tri1` net with a pull-up — what a board carries on /WP and /HOLD
— and each device loaded from an image `hw/soc/flow/gen_flash_image.py`
writes into the build directory on every run. **16 tests, 16 pass**
**[fact]**. The expectations are the datasheet through the model's
counters, the block's register map as its header states it, the APB
slave contract, and the generated map for the slot and the line; the
image's pattern is imported and recomputed for the expectation, never
read back from the simulation.

What the tests establish, in the order a doubt would arise: the reset
state and every register's read-back; the JEDEC identification through
each chip select, with the other device seeing no frame; Read Data
returning the image in little-endian lanes with the pause at every word
observed on the pins (SCK low, chip select held) and a short last word
zero-padded; Fast Read with its eight dummy clocks on the second device,
whose image carries a different seed so a read that reached the wrong
device is wrong in every byte; the quad reads refused until QE is set,
the volatile write setting it, 6Bh and EBh then delivering, and a
software reset dropping it again; the non-volatile write showing BUSY
for tW and surviving the reset; page program driving a three-word TX
phase through two `TXE` pauses and reading back, and refused without
write-enable; the divider, the chip-select setup and hold and the
deselect gap measured on the wire at two dividers, with a `CMD` written
during the gap refused and flagged; writes while busy refused and the
frame running on with what it captured; the interrupt as a level of
`DONE` or `DR` under `IEN`; the abort, paused and with SCK running at
DIV = 3, every SCK level still whole; the lane discipline in a
single-lane frame and clock by clock through a quad I/O frame — 8
single, 6 quad, 2 mode at FFh, 4 released, 8 data released; the opcode
and address on the wire being the registers, checked through the
model's own decode; unimplemented offsets; reads without side effects
except `RX`; and the slot and line being the frozen map's.

`test_the_slot_and_the_line_are_the_frozen_maps` failed on the first
run, before `regmap/memmap.yaml` was promoted, exactly as `docs/65`
section 4.1 records for GPIO.

### 6.2 Formal, by k-induction

`hw/soc/formal/soc_qspi.sby`, four tasks **[fact]**:

| Task | Mode | Widths | Result |
|---|---|---|---|
| `bmc` | bounded, depth 40 | `LEN_W = 3`, `DIV_W = 2` | PASS |
| `prove` | k-induction, depth 12 | `LEN_W = 3`, `DIV_W = 2` | **PASS** |
| `prove_full` | k-induction, depth 12 | `LEN_W = 16`, `DIV_W = 4`, `NCS = 2` as instantiated | **PASS** |
| `cover` | depth 110 | `LEN_W = 3`, `DIV_W = 2` | PASS, **12 of 12** cover statements reached, the quad I/O read at step 84 |

The widths are narrowed in the default tasks for `soc_busstat.sby`'s
reason: at `LEN_W = 3` a whole data phase, a pause and a resume fit in a
bounded model, so the covers are reachable; `prove_full` runs the same
property set at the shipped widths so nothing is claimed at a width
where the covers were not run.

`soc_qspi_props.v` reconstructs the register file from the APB port in
ghosts and the frame from the pins — a rising-edge counter, and "age"
counters since the last SCK change, since the chip select fell, since
the last falling edge and since the chip select rose — and asserts:

- **Q1, Q2** the APB contract and the registers: every register is what
  the header says after any sequence of writes, `CONF`, `CMD` and `ADDR`
  refused while busy with `LOST` set, reads change nothing but `DR` on
  `RX`, reserved bits read zero;
- **Q3** at most one chip select low, none low unless busy, the low one
  the one `CONF.CS` names, all high through the gap;
- **Q4** SCK low when nothing is selected, changing only on the block's
  own tick and never twice within DIV + 1 clocks, the first rising edge
  at least a half period after the chip select falls, the chip select
  rising with SCK low at least a half period after the last falling
  edge, and no chip select falling for 8(DIV + 1) clocks after one
  rose;
- **Q5** the lanes never changing on a rising edge, IO2 and IO3 high
  whenever IO0 is driven alone, IO1 driven only in a four-lane phase,
  nothing driven while nothing is selected;
- **Q6** the opcode on IO0 MSB first at the first eight rising edges,
  then the address MSB first on one lane or four;
- **Q7** every unaborted frame having exactly `8 + address + dummy +
  LEN x (2 or 8)` rising edges, counted from the pins, and never more;
- **Q8** `DR`, `DONE`, `LOST`, `BUSY` and `irq_o` rising and falling
  only for the reasons the header gives.

The ghost equalities and a set of structural invariants — the
sequencer's position in the frame, computed from its own counters,
equal to the pin ghost's count at every clock; the shifter and the
lanes holding the register's bit for the current unit; the ages against
the divider — are what make the set inductive at depth 12. Section 10
records that two of the counterexamples on the way were the RTL's and
not the properties'.

**What the proof does not say.** Nothing about the data path's
*value* — that `RX` holds the sampled bytes in the right lane order —
which is the suite's against a model whose contents are known, because
a ghost that assembled the word would be the design's shift register
written a second time. Nothing about a device: `io_i` is free. No
liveness, because a frame paused at `DR` waits for software for ever
by design. No fault model.

### 6.3 Mutation evidence

`hw/soc/tb/cocotb/mutate_soc_qspi.py` — tracked, unlike `docs/65`'s
scratch mutations, so the table below is reproducible — writes each
defect into a scratch copy of the RTL and runs the suite through
`SOC_QSPI_SRC`. **Sixteen mutations, all sixteen caught** **[fact]**.
The map test is excluded from the "caught by" column; it reads the map,
not the RTL.

| Mutation | Caught by |
|---|---|
| RX packs the first byte into the top lane (big-endian) | `test_jedec_id_on_each_chip_select` and 9 others |
| the opcode goes out LSB first | `test_reset_state_and_registers_read_back` and 11 others |
| the input is sampled from IO0 instead of IO1 in single mode | `test_jedec_id_on_each_chip_select` and 7 others |
| IO3 (/HOLD) released instead of driven high in single mode | `test_lane_discipline_in_single_and_quad_phases` |
| one dummy clock too few | `test_fast_read_0bh_with_eight_dummy_clocks` and 3 others |
| the lanes are not released for a quad data phase | `test_quad_reads_need_qe_and_then_deliver` and 2 others |
| no pause at a word boundary: DR set but the frame runs on | `test_read_data_03h_returns_the_image_little_endian` and 2 others |
| the deselect gap is one SCK period instead of four | `test_sck_divider_cs_setup_and_the_deselect_gap` and 3 others |
| a CMD write while BUSY is accepted | `test_sck_divider_cs_setup_and_the_deselect_gap` and 2 others |
| the interrupt ignores DR | `test_interrupt_is_a_level_of_done_or_dr_under_ien` |
| the address goes out low byte first | `test_read_data_03h_returns_the_image_little_endian` and 5 others |
| the second chip select is never asserted | `test_jedec_id_on_each_chip_select` and 2 others |
| the mode byte after a quad address is 00h, entering continuous read mode | `test_lane_discipline_in_single_and_quad_phases` |
| the SCK divider runs at DIV instead of DIV + 1 clocks per half period | `test_sck_divider_cs_setup_and_the_deselect_gap` and 1 other |
| a read of RX does not clear DR | `test_read_data_03h_returns_the_image_little_endian` and 8 others |
| the TX word's first byte out is its top lane | `test_page_program_drives_a_multi_word_tx_phase` and 1 other |

Two of the sixteen are caught by exactly one test each — the /HOLD
lane and the mode byte — and both by the test that watches the lanes
clock by clock. That is the test to keep.

### 6.4 Everything else, re-run

`cd hw/soc/formal && make`: **11 jobs, 41 tasks, 41 PASS, no unreached cover statement in any cover task** **[fact]**. The
fabric's own two jobs, `soc_bus` and `soc_apb_bridge`, are unchanged by
this work — no fabric port was added and the slot decode lives in
`soc_top.v` — and they pass.

`scripts/run_cocotb.sh`: **20 suites, 352 tests passed, 0 failed, 0 suites
not clean**, the three frozen-directory suites skipped by its default
**[fact]** — after the runner was repaired. Its first run of this work
reported 573, then 548, with the 16-test QSPI suite shown as 47, and
section 10 item 7 is the reason: the runner took its "written during
this run" timestamp before its one-second pause, at one-second
granularity, so almost every suite was credited with its predecessor's
results as well. **`docs/65` section 4.4's 294 was produced by that
runner and is not comparable**; the same nineteen suites count 336
today **[fact, 352 less the 16 new ones]**.

`sw/tests`: **403 passed** **[fact]**, including the memory-map
sync tests that now see QSPICTL implemented, the textual checks that
`soc_top.v` decodes exactly the implemented slots and wires exactly the
implemented interrupt-bearing ones, both source-list guards (section
10), and the document link test.

---

## 7. The demonstration: the NPU fed from flash

### 7.1 Why it is a second image

`hw/soc/tb/sw/test_ibex.c` is linked into the boot ROM at the reset
vector, which leaves 8,064 bytes of the map's 8 KiB. At HEAD the
28-check program is **7,794 bytes** **[fact, `== sw:` line of the
build]**. With checks 29 and 30 and their helpers it is **9,594
bytes** **[fact, linked against a scratch 32 KiB ROM to measure it]**
— 1,530 over — and none of the code-size flags the toolchain offers
helps: `-msave-restore` makes it larger **[fact]**.

So the demonstration is a second image, built from the same file with
`-DQSPI_DEMO`, exactly as `-DWDOG_RESET_DEMO` builds the watchdog
escalation demonstration of `docs/40`. It keeps check 1 (the core is
alive), check 26 (the inference from the ROM's weight arrays), checks
29 and 30, and check 11; the rest are compiled out. It is **4,566
bytes** **[fact]**. The 28-check image is unchanged in what it does,
and section 8 measures what the one refactor it carries costs.

The alternative — a bigger ROM — is a map change and a floorplan change
(`docs/47` sizes the ROM as two 1024x32 macros) and was not made for a
demonstration program. The finding stands on its own: **the bring-up
program has outgrown the boot ROM**, and any further check will either
displace one or be a second image.

*Corrected 2026-09-05 by `docs/68-boot-flow.md`:* it no longer has to
fit. The boot ROM holds a 3,104-byte loader and the program is bounded
by the 32 KiB of RAM it is loaded into, so a further check displaces
nothing. The demonstration images remain, because they demonstrate
different things and not because of a size limit.

### 7.2 Check 29: the flash through the real fabric

Every word here travels core, fabric, APB bridge, slot decode, the
block's sequencer, the four lanes, the model's timing checks and back.
The expected words come from `qspi_image.h`, written by
`gen_flash_image.py` at build time from the pattern the image was
written from, and never from anything the simulation produced.

1. 9Fh reads **EF 40 18**, the part's identification.
2. 03h reads seven sample words, including one at an unaligned byte
   address, and every one matches the header.
3. SR2 reads 0; 50h then 31h sets QE; SR2 reads 2.
   *Corrected 2026-09-05 by `docs/68-boot-flow.md` section 10.4:* since
   the boot flow exists, the LOADER sets QE before this program runs, so
   "SR2 reads 0" had become a check that the loader did not run and it
   failed for exactly that reason. The check is now that QE is already
   set on entry and that setting it again is idempotent.
4. EBh and 6Bh read the aligned samples on four lanes; every one
   matches.
5. 0Bh reads two consecutive words in one frame through the `DR` pause.
6. Chip select 1, which goes to nothing on this board, reads the
   pull-ups: `0x00FFFFFF` for a three-byte read.
7. A `CMD` written while a frame is paused at `DR` is refused and
   flagged `LOST`; the frame runs on and delivers the right words.
8. The interrupt: `IEN` set, a read started, the core takes **`mcause
   0x80000019` at vector 25**, `mtvec + 0x64`, the marker `crt0.S`'s
   new stub carries compared against `mcause`; the word is still in
   `RX` afterwards because the handler masks the line and touches no
   register.

### 7.3 Check 30: the weight image

`gen_flash_image.py` places at `0x010000` in the image on chip select 0
a 16-byte header — magic `NSW1`, the word count, the geometry, a
checksum — followed by the `docs/51` weight words, packed by the same
`pack_words` from the same `make_weights` and the same seed that fill
the ROM's `npuv_wlo`/`npuv_whi` arrays. The program reads the header
with one EBh frame, checks all four words, then reads the body with one
EBh frame of `8 x N_WWORDS` bytes, pulling each word through `DR` into
RAM, and checks the checksum. As a diagnostic it also compares the
words with the ROM's copy; the pass criterion is not that.

The pass criterion is the golden model. `npu_bring_up` now takes the
weight arrays as a parameter, and the body of check 26 is a function,
`npu_inference`, that check 26 calls with the ROM's arrays and check 30
calls with the flash's. Everything `docs/51` section 7 puts in the loop
is in the loop again — the serial transport, the die's frozen register
bank, its ECC-checked weight loader, the event queues, the LIF
datapath, the AER pins — and the answer is `sw/golden/lif_core.py`'s,
computed at build time.

```
npu: 0x0000000c events, cnt=0x000c0016 status=0x0000002a
  ok   test 0x0000001a
  ok   test 0x0000001d
npu from flash: 0x0000000c events, cnt=0x0018002c status=0x0000002c
  ok   test 0x0000001e
  ok   test 0x0000000b
checks run: 0x00000005  fail mask: 0x00000000
RESULT PASS
[TB] core asleep after 60,706 cycles
[TB] qspi: 29 frames on CS0, 0 datasheet violations, irq 0
[TB] PASS
```

**[fact, `hw/soc/out/s66-sim-qspi/sim.log`]**. The event counters are
not cleared between inferences, so `npu_inference` checks what one
inference adds to them; the second `cnt` is the first plus a run of
`docs/51`'s 22 events in and 12 out, plus check 27's barrier, which
the demonstration image does not run and which is why its counts are
what they are. **This is the first time the NPU has been fed from
where a flight part would feed it** — the words still enter the node
one register at a time, because that is the die's only weight port;
what changed is where they come from.

The 28-check image was re-run with the final RTL, 217,682
cycles and 28 of 28; and the escalation demonstration of `docs/40`
section 6.2 with the block present: three boots, three stages,
37,405 cycles **[fact, `hw/soc/out/s66-sim/sim.log`,
`s66-sim-wdog/sim.log`]**.

---

## 8. The invariant

`docs/65` section 6 asked that every document after it quote 217,634.
Three numbers, all measured, and the difference between the first two
is the point:

| Configuration | Checks | Cycles |
|---|---:|---:|
| HEAD, `docs/65` | 28 | 217,634 |
| this RTL, `soc_qspi` in `soc_top`, program unchanged | 28 | **217,634** |
| this RTL, the `npu_inference` refactor in the program | 28 | **217,682** |
| this RTL, the `QSPI_DEMO` image | 5 | **60,706** |

**[fact, `hw/soc/out/s66-sim-noprog/sim.log`, `s66-sim/sim.log`,
`s66-sim-qspi/sim.log`]**

The second row is the statement that adding the block changes nothing
the existing program can see: `CTRL.IEN` resets to zero so fast line 9
is low throughout, the slot decode adds no cycle to any access, and the
model on the pins saw **0 frames** **[fact]**. The third row is the
cost of turning check 26's body into a function that takes its weight
arrays as a parameter and checks the event counters as deltas rather
than absolutes: +48 cycles, none of it in the
block. **Every document after this one should quote 217,682
for the 28-check image**, and the demonstration image carries its own
number.

*Corrected 2026-09-05 by `docs/68-boot-flow.md` section 8:* the program
is no longer fetched from the boot ROM. The ROM holds a loader, the
program is copied into RAM from a flash image, and the number becomes
**220,256 for the program and 415,324 for the run**, against **217,630**
for the identical program from the ROM — the difference being that
instruction fetch and data access now share one slave port. That
document's section 8 carries every step of the move, each measured.

---

## 9. Measured area

Same recipe as `docs/39` section 6 and `docs/65` section 7: Yosys
`stat -liberty` on `ihp-sg13g2` at the typical corner, the same driving
cell, load and 20 ns target. Gate equivalent = `sg13g2_nand2_1` =
7.2576 um2. The Ibex reference is 275,682.6198 um2.

| Block | Cells | Flops | Area, um2 | kGE | % of Ibex |
|---|---:|---:|---:|---:|---:|
| `soc_qspi`, `NCS = 2`, `flow/syn_soc.sh` | 1,231 | 192 | **19,690.6248** | 2.713 | 7.14 % |
| `soc_qspi`, `NCS = 1`, `SOC_CHPARAM="-set NCS 1"` | 1,208 | 191 | 19,397.6748 | 2.673 | 7.04 % |
| **the second chip select** | **+23** | **+1** | **+292.9500** | +0.040 | |

**[fact]**. The 192 flip-flops are the registers the header declares —
`CONF` 5, `CTRL` 1, `CMD` 30, `ADDR` 24, `TX` 32, `RX` 32, five flags —
and the sequencer's state, shifter, counters and lane registers. Against
`docs/65` section 8.4's `spi_host` at 65.051 kGE, this is **4.2 % of
the size** for the part of it this SoC needs **[fact, the two
measurements]**.

And the whole SoC, `flow/syn_soc_top.sh` at `SOC_MEM=sram`, 20 ns:

| Design | Cells | Flops | Area, um2 |
|---|---:|---:|---:|
| HEAD, from a clean worktree at `9e28a62` | 42,748 | 5,407 | 639,079.6482 |
| with `soc_qspi` | 43,884 | 5,599 | 656,385.0552 |
| **difference** | **+1,136** | **+192** | **+17,305.4070, +2.708 %** |

**[fact]**. The HEAD row reproduces `docs/65` section 7's cell count,
flip-flop count and area exactly, which is what licenses the
difference. The flip-flop delta is the block's exactly; the area delta
is 2,385.22 um2 less than the block alone, `docs/45` section 4.3's
effect in the other direction from `docs/65`'s, reported rather than
reconciled.

**What the numbers do not say.** No frequency was measured, nothing
here has been through STA at any corner or through place-and-route,
and the new pins have no pad and no I/O timing.

---

## 10. Defects found, all in this work

1. **A TX word landing on the clock a pause began was stranded.** The
   sequencer reached a word boundary in a write phase, saw `tx_full`
   clear, and entered the `TXE` pause in the same clock that software's
   `TX` write set it; the pause then waited for a second write that
   would never come. **Found by the bounded model check at step 18 and
   by no cocotb test**, because the suite writes `TX` only after seeing
   `TXE`. The pause now resumes on either the write or the register
   being full, and a property says a word in `TX` never waits in the
   pause for more than one clock.
2. **An abort could cut an SCK level short.** `CTRL.RST` dropped SCK at
   once, so an abort landing one clock into a high half period produced
   a pulse shorter than the divider promises. **Found by the proof of
   Q4** — the counterexample was a legal abort. An abort with SCK high
   now waits for the falling edge the divider is already counting
   toward; one with SCK low acts at once; one in the hold or the gap is
   ignored, which the proof also required, because restarting the gap
   from the gap put a chip select low with nothing selected. The suite
   gained a test that watches every SCK level through an abort at
   DIV = 3.
3. **A quad address sent with QE clear drives /HOLD.** The first
   version of the register read-back test used a quad-address frame
   before QE was set, and the model counted six /HOLD violations: with
   QE = 0 the part's IO3 is /HOLD, and address nibbles put zeros on it.
   The test was wrong and the model was right; the controller cannot
   know QE, so the rule belongs to the driver and is in the header.
4. **The lanes were released before the chip select rose.** The first
   RTL released all four lanes at the end of the data phase, one half
   period before CS rose, so /HOLD floated on a pull-up while the part
   was still selected. Caught by the lane-discipline test; the lanes
   now keep their pattern until CS rises.
5. **Both source-list guards fired.** With `u_qspi` in `soc_top.v` and
   no flow updated, `test_every_flow_that_builds_soc_top_reads_every_module_it_instantiates`
   failed on the four flows and
   `test_the_whole_soc_elaborates_as_one_design` failed with "Module
   `\soc_qspi` referenced in module `\soc_top` ... is not part of the
   design" — the fifth list `docs/65` section 10 added it for **[fact]**.
   Both pass with the six flows and the list updated. The cocotb slave
   index guard in `test_soc_bus.py` is untouched by this work because
   no fabric port was added; section 12 says what that guard would have
   caught.
6. **The bring-up program has outgrown the boot ROM.** Section 7.1.
7. **`scripts/run_cocotb.sh` double-counted.** It captured `date +%s`
   before its one-second pause and collected every results XML newer
   than that second; a suite whose predecessor finished in the same
   second inherited the predecessor's XML. The QSPI suite, three
   seconds of simulation after the NPU suite's thirty-one tests,
   reported 47 **[fact]** — and so, on inspection, did most suites:
   `pilot` 63 for 31, `regbank` 64 for 33, `scrub` 75 for 42. A marker
   file touched after the pause replaces the timestamp. Every "n
   passed" this runner has printed before today is inflated by the
   same mechanism; the "0 failed" beside each was never affected,
   because a duplicated XML has the same failures as the original.

---

## 11. What is not built

- **Execute-in-place.** Section 2.1. The windows are reserved with
  the reason beside them.
- **4-byte addressing, dual lanes, QPI mode, continuous read mode, a
  DMA, a FIFO.** The block is a sequencer and one word of storage.
- **A sampling-delay adjustment.** Section 3.3 bounds SCK at about
  80 MHz for that reason.
- **Erase.** The model implements sector erase; the program never
  erases anything, and the flash image is written by the build.
- **Hardening.** An upset in the sequencer's state is a frame that ends
  early or never; `CTRL.RST` is the recovery, the watchdog is the
  backstop, and nothing reports the upset.
- **A boot flow.** `docs/08` section 3 row 16's bootstrap-selected boot
  from QSPI needs a ROM loader that copies an image to RAM through this
  block and checks it; the block can do the reads and nothing in this
  document writes the loader.

---

## 12. What the checks do not cover

Stated separately from "not built", because this repository has been
bitten by the difference.

- **A behavioural flash model is not a flash.** Section 5's last
  paragraph. The timing is the datasheet's table applied as
  inequalities in simulation time at the model's terminals; no pad, no
  trace, no capacitance, no temperature, no voltage and no wear is in
  it. That the controller obeys the datasheet as the model states it is
  what is established; that it works with a device is not.
- **The datasheet was read once, by one reader.** Every number in the
  model cites its section; a misreading would be a wrong specification
  faithfully enforced.
- **The proof says nothing about the data path's value.** Section 6.2.
  The suite does, against known contents.
- **The whole-SoC run exercises one device, one divider, aligned quad
  addresses, and a 32-byte weight image.** A full-scale image
  (`docs/10` section 5: 16,384 words) crosses the same path 512 times
  over and was not run.
- **The cocotb slave index guard was not exercised**, because nothing
  changed the fabric. It would fire if a region gained a `port` in the
  map that `soc_bus.v` does not decode, or the reverse — which is
  exactly what XIP would do.
- **No fault-injection campaign was re-run.** `flow/fi_core.sh` and
  `flow/fi_npu.sh` read `soc_qspi.v` now and their benches tie the pins
  to an empty board, but neither was executed — the position `docs/61`
  and `docs/65` took, for the same reason.
- **The whole-SoC area is synthesis at a 20 ns target with the SRAM
  boundary; no timing, no place-and-route, no power.**
- **`prove_full` proves the shipped widths; the covers were run only
  at the narrow ones.** A behaviour reachable only above `LEN = 7` is a
  behaviour the cover job did not witness.

---

## 13. Files touched outside `hw/soc/`, and why none is frozen

`docs/34` section 2 pins `hw/rtl/` by blob and section 5 the flow
configurations. None of the following is in either set **[fact]**:

| File | Change |
|---|---|
| `regmap/memmap.yaml` | one field: QSPICTL `status` reserved to implemented, and its description; a comment above the two XIP windows saying why they stay reserved. No address, slot, source number, line or device id moved |
| `docs/memmap-soc.md`, `sw/golden/memmap_gen.py` | regenerated and changed: the slot's status and description. The other five generated files are byte-identical, because no constant moved and the two-word peripheral device-table record carries no status field **[fact, `git status`]** |
| `sw/tests/test_soc_synthesis_guards.py` | `soc_qspi.v` in the whole-SoC elaboration list |
| `docs/66-qspi-flash-controller.md` | this document |
| `docs/00-index.md` | one row, and one dated correction in section 2.2 |
| `docs/60-soc-datasheet.md`, `docs/51-npu-integration.md`, `README.md` | dated in-place corrections by `docs/64`'s rule: the "no QSPI" statements were true when written and now name this document |
| `scripts/run_cocotb.sh` | the same-second race of section 10 item 7 |
| `.gitignore` | the SymbiYosys working directories of the new job and the mutation scratch directory |

Everything else is under `hw/soc/`. `hw/soc/{ext,tools,gen,genp,out}`
and `hw/soc/pnr/runs` remain gitignored.

---

## 14. Reproducing this

```
python regmap/generate_memmap.py
.venv/bin/python -m pytest sw/tests
scripts/run_cocotb.sh

cd hw/soc/tb/cocotb && make -f Makefile.soc_qspi         # 16 tests
python3 hw/soc/tb/cocotb/mutate_soc_qspi.py              # 16 of 16
cd hw/soc/formal && make qspi                            # 4 tasks
cd hw/soc/formal && make                                 # every job

hw/soc/flow/sim_soc.sh hw/soc/out/s66-sim                # 28 checks
SW_DEFINES=-DQSPI_DEMO hw/soc/flow/sim_soc.sh hw/soc/out/s66-sim-qspi
SW_DEFINES=-DWDOG_RESET_DEMO hw/soc/flow/sim_soc.sh hw/soc/out/s66-sim-wdog

hw/soc/flow/syn_soc.sh soc_qspi                          # 19,690.6248 um2
SOC_CHPARAM="-set NCS 1" hw/soc/flow/syn_soc.sh soc_qspi
SOC_MEM=sram hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s66-soc
```

The whole-SoC baseline in section 9 was produced from a clean
`git worktree` at `9e28a62` with `hw/soc/{gen,genp,tools,ext}` symlinked
in, `docs/65` section 14's method. The program-unchanged row of section
8 was produced by stashing the three program files (`crt0.S`,
`test_ibex.c`, `soc_qspi.h`) and running `flow/sim_soc.sh` against the
new RTL.

---

## 15. What the next block should be

**The boot flow, not another interface.** This block reads a flash; a
flight part boots from one. `docs/08` section 3 row 16 — a bootstrap
pin, a checksummed image header, a copy to RAM, a boot report register,
the staged watchdog through it — is now buildable on the reads this
document verifies, and it is what turns the QSPI3 window's absence from
a gap into a decision: an image copied to RAM at boot does not need to
be fetched from flash, and the XIP question can be answered with a
measurement of the copy instead of an argument about the latency.
Section 7.1's finding sharpens it: **the bring-up program has outgrown
the boot ROM**, and a ROM that holds a loader rather than a test
program is the arrangement every reference part uses.

**Before SpaceWire, decide the licence** — `docs/65` section 13,
unchanged. **After that, one APB-to-Wishbone bridge for CAN and I2C** —
`docs/65` section 9.4, unchanged.
