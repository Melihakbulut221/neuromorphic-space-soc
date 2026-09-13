# 68 — The boot flow: what the ROM is, who writes the RAM's check bits, and what happens when neither works

`docs/67-memory-protection.md` section 15 item 1 named this block and
stated why it is not a feature but a consequence: *"The boot flow, which
is now the ROM's protection. The ROM's code and check bits are loaded
together or the first fetch traps."* `docs/66-qspi-flash-controller.md`
section 15 named the same block from the other side — *"This block reads
a flash; a flight part boots from one"* — and added the finding that
sharpens it: **the bring-up program had outgrown the boot ROM.** That
document measured 7,794 of the 8,064 bytes above the reset vector; at
`ed51de0`, after `docs/67`, the same build reports **7,826**, and with
this document's changes to the program it is **7,814** **[fact, the
`== sw:` line of three builds]**. Either way the two flash checks needed
1,800 more bytes and had to be a second image.

Four questions were open, in four documents, and they are one design:

1. **How the ROM gets contents.** `docs/47` section 4.4 and `docs/58`
   left it open; `docs/67` section 8 sharpened it to *"check bits on a
   ROM nobody can write are check bits nobody can initialise"*.
2. **The loader.** `docs/66` proved the reads; nothing wrote the loader.
3. **The bootstrap pin and the boot report.** `docs/40` W1 established a
   pin sampled once; the map has reserved `0xFF917000` for a
   GRGPREG-shaped boot report since `docs/39`.
4. **What happens when boot fails.** The watchdog is armed at reset and
   cannot be disabled (`docs/40` W1, W2), so a loader that retries for
   ever gets reset — and `docs/40` section 7.2's brick loop is the
   precedent for what a boot flow must not do.

They are one design because **each one's answer is the next one's
mechanism**: the ROM holds a loader because the ROM cannot be patched;
the loader must write whole codewords because the RAM's check bits do
not exist until it does; the boot report exists because the escalation
happens across resets; and the escalation is the watchdog's, not a new
one, because a second ladder would be a second thing that can brick the
part.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged, with the
derivation stated; **[planned]** = an intention with nothing behind it
yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash. Nothing in `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or
`hw/openlane/` was modified and `hw/tb/Makefile.fi` was not invoked;
section 14 lists every file.

**A NOTE ON WHICH BASELINE, BECAUSE HEAD MOVED UNDER THIS WORK.** Every
baseline in sections 8 and 9 is `ed51de0`, the commit this work started
from. While it was running, the repository advanced to `369c18c` —
`ROADMAP.md`, `docs/13`, `docs/14` and two files under
`hw/soc/rvformal/insns/` — and **none of those is read by any flow, any
testbench or any program measured here**: `git diff ed51de0..369c18c`
restricted to `hw/soc/{rtl,flow,tb,formal}`, `regmap/`, `sw/` and the
five frozen directories is empty **[fact]**. The baselines therefore
stand against the current HEAD as well, and this paragraph exists so
that a reader who checks the hashes is not left wondering.

**A NOTE ON WALL-CLOCK TIME, FIRST RATHER THAN LAST.** This session ran
against a contended machine: another application held about one core for
part of it and a process from an unrelated project held one core
throughout. **No wall-clock figure appears in this document.** Every
runtime quoted is either a **cycle count from the simulation**, which is
a property of the design and not of the machine, or a **flow's own
per-step `runtime.txt`**, which is written by the step. `docs/67` section
14 set that rule for a different reason and it is the right instrument
here too.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **What is the boot ROM in a flight part?** | **A mask-programmed array holding a loader and nothing else**, and the 8 KiB SRAM macro pair this PDK forces is a **stand-in** for it. Section 3 argues it against the other three candidates and states what it makes of `docs/67`'s ROM check macros: a mask ROM's bit is a via, it has no stored-upset mechanism, and **it needs no check field at all** — so `docs/67` section 15 item 2, "place the ROM's check macros", becomes conditional on the stand-in rather than owed by the design. `ROM_HARDEN` stays, and what it protects is now named |
| **What does the loader do about uninitialised ECC?** | **It writes every word of the RAM before it reads any of it, and it writes WHOLE WORDS.** `boot_crt0.S` sweeps `[RAM_BASE, RAM_TOP)` with 8,192 word stores before the stack pointer is set — the only order that works, because the loader's stack, `.data` and `.bss` are all inside what it is initialising. A byte store makes one of a row's four (16,8) codewords valid and leaves three as the SRAM powered up, so **"initialise the RAM" is not the requirement; "write whole codewords" is** — and `-DBOOT_SWEEP_BYTE` is the build that shows the difference. The sweep costs **49,178 cycles, 6.003 per word** **[fact]**. Section 4 |
| **And the checksum?** | **Computed from the RAM, not from the flash.** The copy loop writes what the controller delivered; a second pass reads those words **back out of the RAM** and sums them, so a word that arrived intact and landed on a row whose codeword did not take is caught. It costs **17.01 cycles per word** **[fact]** and it is what turns an uncorrectable in a loaded image into a reported boot failure instead of the application's first mysterious fault. Section 5 |
| **What is the escalation?** | **Two images per boot, three boots, and then the watchdog's own ladder — there is no second one.** Within a boot the primary image's magic, header checksum, geometry, body checksum and ECC are each a reason to try the secondary. Both failing means the loader **shortens the watchdog to its minimum and stops kicking**; the next boot reads `BOOTREG.BSTAT.CNT` one higher, and no software can write that counter. The limit is **three**, chosen so the last boot the loader attempts is one during which `WDOGN` is **already** asserted: software gives up after the hardware has told the platform, never before. Section 6 |
| **Why not wait for an upload?** | **Because this part has no ingress channel.** GR716B's boot flow has a standby mode waiting for a remote boot; the console UART here is transmit-only and nothing else is built, so a loader that waited would be a hang with a good name. Handing the decision outside is the only terminal state this part can offer, and section 6 says what changes the day an ingress channel exists |
| **What was built?** | `hw/soc/rtl/soc_boot.v` in the BOOTREG slot — the straps as they were sampled, a **boot counter no software can write**, and a boot report and an epoch word that survive the reset they describe — plus a loader (`boot.c`, `boot_crt0.S`, `link_boot.ld`), the application relinked to run from RAM (`link_app.ld`), and the image in the flash (`gen_boot_image.py`). Section 2 |
| **Did it boot?** | **Yes, end to end, through the real fabric, from the modelled flash, with the RAM powered up undefined.** 28 of 28 checks, fail mask 0, `RESULT PASS`: **415,324 cycles, of which 195,068 are the boot and 220,256 are the program** **[fact, `hw/soc/out/s68-ship/sim.log`]** |
| **What does the invariant become?** | **220,256 for the program, against 217,630 for the same program fetched from the boot ROM: +2,626 cycles, +1.207 %** **[fact, measured against a `git worktree` at `ed51de0` carrying the identical `test_ibex.c`]**. The whole difference is that instruction fetch and data access now share **one** slave port instead of two. It is not a regression and it is not free; section 8 |
| **What did it cost in area?** | **The block alone: 303 cells, 92 flip-flops, 7,229.0610 um2, 0.996 kGE** **[fact]**. On the whole SoC the honest answer is that **the measurement is noisier than the block**: +971.5356 um2 (+0.140 %) at the shipped `ROM_HARDEN`, +10,437.2604 um2 (+1.549 %) on the netlist the layout uses, against baselines re-measured in this session. Section 9 says why both are reported |
| **The layout?** | **Placed and routed on `docs/67`'s die against a baseline placed in the same session on the same config — 0 DRC in both, the die not one database unit larger, hold closed at all three corners, +1.986 % of placed standard-cell area.** The baseline reproduces `docs/67` section 5.3 to the last digit, which is what makes the difference attributable. Hold at the fast corner falls from **+0.1012 ns to +0.0715 ns**, the smallest margin in the design and the number the next block should look at; setup improves by 0.1114 ns and **that is placement noise on a design that does not close, reported and not attributed**. Section 9.3 |
| **Sharpest findings?** | Four, all found by running it. **A sentinel inside its own range**: `try_image` returned "the entry point, or 0 for failure", and the application's entry point is 0 — every successful boot was reported as a failure with `cause 0x00000000`. **A scrubber counting a boot as radiation**: the RAM scrubber ships enabled and starts walking a memory the sweep has not reached, so `SCRUB.CNT_RAMDED` reads non-zero on every power-on before any upset has happened. **Undefined behaviour that had been harmless for thirty documents**: test 10 dereferenced a `char[]` symbol as a `uint32_t`, and when the program moved from ROM to RAM the compiler's byte-wise expansion of it went through a base register the surrounding code had since reloaded — three of four bytes went to an unmapped address and took bus errors, presenting as `mcause 5` inside a PMP test. **And a check that had become a check that the loader did not run**: `docs/66`'s test 29 asserted the flash's QE bit reads zero, which is only true of a part nothing has touched. Section 10 |

---

## 2. What was built

| File | What it is |
|---|---|
| `hw/soc/rtl/soc_boot.v` | **New.** The BOOTREG slot: the straps sampled once through two synchronisers, a boot counter maintained by hardware and writable by nothing, and a 32-bit report and a 32-bit epoch word in the power-on domain. Everything in it is power-on-reset only, and it has **no output but the APB read path** — section 7 says why that is the structural form of `docs/40` section 7.2's fix |
| `hw/soc/rtl/soc_top.v` | `BOOT_NSTRAP`, `BOOT_LIMIT`, a four-pin `strap_i` port, the slot decode and `u_boot` |
| `hw/soc/tb/sw/boot.c` | **New.** The loader: the console, the report from the last boot, the straps, the limit, the flash, two image slots, the copy, the read-back verify, the hand-over and the escalation |
| `hw/soc/tb/sw/boot_crt0.S` | **New.** `mtvec`, then **the RAM sweep**, then the stack, then `.data`. A 32-entry trap table whose synchronous entry records a fault and returns, so that an uncorrectable in the loaded image is a reported boot failure and not a machine that stops |
| `hw/soc/tb/sw/link_boot.ld`, `link_app.ld` | **New.** The loader into the ROM with its private RAM at the top; the application into RAM at the bottom, `_start` at the region base |
| `hw/soc/tb/sw/soc_boot.h` | **New.** The register map, the report layout, the cause codes and the image header format — the one declaration `gen_boot_image.py` and `boot.c` share |
| `hw/soc/flow/gen_boot_image.py` | **New.** Puts the linked application into two slots of the flash with an eight-word header that sums to zero, taking the load address and entry point **out of the ELF**; `--corrupt` breaks exactly one thing for each counterfactual |
| `hw/soc/flow/build_sw_soc.sh` | Two programs instead of one, and the image between them |
| `hw/soc/flow/sim_soc.sh` | `SOC_RAM_RANDOM` (**on by default**), `SOC_STRAP`, `SOC_DED_WORD`, `SOC_TIMEOUT_CYCLES`, `SOC_VVP_ARGS`, `BOOT_CORRUPT`; symbols taken from the application's ELF |
| `hw/soc/flow/pnr_soc_top.sh` | `PNR_STATE`, so a change and its baseline can be placed at the same time without racing on one file |
| `hw/soc/tb/tb_soc.v` | **A power-up model**: `+ram_random` fills the RAM's data *and its check field* with pseudo-random bits before reset releases. `+ded_word`/`+ded_skip` plant an uncorrectable in a word the loader has just written. `+strap`. The hand-over cycle. `+errtrace` and `+ftrace_from/to`, the two observations section 10 needed and did not have |
| `hw/soc/formal/soc_boot.sby`, `soc_boot_props.v` | **New.** D1-D8, four tasks. Section 11.2 |
| `hw/soc/tb/cocotb/test_soc_boot.py`, `Makefile.soc_boot`, `mutate_soc_boot.py` | **New.** Fourteen tests, eight mutations. Sections 11.1 and 11.3 |
| `sw/tests/test_soc_boot_guards.py` | **New.** Eighteen guards on the wiring and the order, which is what neither the proof nor the suite can see |
| `regmap/memmap.yaml` and its generated files | BOOTREG **reserved → implemented** |

---

## 3. What the boot ROM is

### 3.1 The four candidates, and the one that answers the question rather than moving it

`docs/67` section 8 named three; `docs/66` section 2.1 implies a fourth.
Each is costed against one criterion: **does it give the ROM contents
that exist before the core leaves reset, without needing something else
that has the same problem?**

| | what it is | contents exist at reset? | check bits needed? | why not |
|---|---|---|---|---|
| **A, chosen** | a **mask-programmed array** holding a loader | **yes**, they are geometry | **no**: a bit is a via, it has no stored-upset mechanism | it can never be patched — which is why the *application* must not live in it |
| B | an SRAM **loaded through the `A_BIST_*` port** before reset releases | only if something else loads it | yes, and they must be written with the data | **the loader has a loader**: whatever drives the BIST port is itself a boot mechanism with the same question, one level out and outside this die |
| C | **the flash itself**, executed in place | yes | not this design's problem | `docs/66` section 2.1: a seventh fabric port, a re-proof of `soc_bus.v`, and about 56 system clocks per fetched word on a core with no cache |
| D | an SRAM loaded **by the application** | no | — | circular: the thing that would load it is the thing that has to be loaded |

**B is the interesting rejection**, because `docs/67` section 8 listed it
without ranking it. It is not wrong — a real part may well have a test
port that a board loads — but it does not answer the question asked. It
relocates it: the ROM's contents then exist because something outside
the die put them there, and *that* thing's contents, integrity and
failure behaviour are unspecified. A mask ROM's contents exist because
the mask exists. That is the only one of the four whose answer is
terminal.

**C is not rejected for ever, and section 16 says what would reopen it.**
`docs/66` left the two XIP windows reserved with the reason written into
the map, and one of the three things it named as needed in front of the
flash was *"a copy-to-RAM boot loader"*. That now exists, which does not
make XIP cheaper — it makes it unnecessary for booting, which was the
only use it had.

### 3.2 So what is the 8 KiB macro pair?

**A stand-in, and this document is the first to say so in those words.**
`libs.ref` of `ihp-sg13g2` at the pinned version has `sg13g2_io`,
`sg13g2_pr`, `sg13g2_sram` and `sg13g2_stdcell` and **no ROM generator**
**[fact, `docs/67` section 8's directory listing, unchanged]**. So the
design instantiates two `RM_IHPSG13_1P_1024x32` and calls the result a
ROM, and three things follow that are now decided rather than open:

1. **In simulation the stand-in is exact.** `$readmemh` loads the two
   macros' behavioural model from the linked image and `soc_mem.v`
   derives the check field word by word through the frozen encoder. That
   models a mask ROM precisely: contents that are there before the first
   fetch, and no mechanism that could make them not be.
2. **In silicon on this PDK the stand-in is not a ROM**, and the
   honest statement is `docs/67` section 9's: **the ROM's contents are
   unprotected and undefined**. A part built from these macros needs
   candidate B to load them, and the part of B this die can offer —
   the `A_BIST_*` port — is parked. Nothing here changes that.
3. **`ROM_HARDEN`'s meaning is now named.** `docs/67` added a (39,32)
   word code and two `RM_IHPSG13_1P_512x16` check macros to the ROM at
   **+90,618.62 um2** and did not place them, and its section 15 item 2
   made placing them the second-highest next task. **On decision A those
   macros are not needed**: a mask ROM has no stored-upset mechanism for
   a code to catch, and only its read path is exposed, which is a
   transient and not a stored fault. ~~They remain in the RTL and remain
   unplaced~~ -- **placed and routed 2026-09-13, run `s83romecc5`**,
   which does not disturb this section's argument: what they protect is
   still stated exactly as **the stand-in**, and any flight part that
   takes candidate B instead. Decision A is unchanged by the geometry
   turning out to be free. That
   is a reprioritisation of another document's recommendation and
   section 13 records it as one.

### 3.3 What the loader being unpatchable buys, and what it costs

A mask ROM is fixed at tape-out. That is the cost, and it is the reason
for every other decision in this document:

- **The loader must be small.** It is **3,104 bytes of the 8,064 the map
  leaves above the reset vector** **[fact, `== sw:` line of the build]**,
  against 7,814 for the program it replaced. There is room for the
  loader to grow by a factor of two and a half.
- **The loader must be simple enough to be right the first time.** It
  has one loop that can spin (`qspi_wait`, bounded at 20,000 iterations),
  no dynamic allocation, no interrupt, and a trap handler that records
  and returns.
- **The application must live somewhere that can be patched**, which is
  the flash, which is what `docs/66` built.
- **And the loader's own failure must not be silent**, because nobody
  can fix it in the field. That is section 6.

---

## 4. The RAM has no check bits until something writes them

### 4.1 An uninitialised protected word is an uncorrectable, not a zero

`docs/67` put four (16,8) byte codewords in every RAM row. On this PDK
the RAM is an SRAM and **an SRAM powers up undefined — and so does its
check field.** A word nothing has written is therefore 32 random data
bits beside 32 random check bits, and the codec's answer to a read of it
is not a random value: it is an **uncorrectable**, which `soc_mem_ecc.v`
answers with a bus error and the core takes as a load access fault.

This is the same shape as the ROM's problem one memory across, and it has
the same statement — check bits nobody has initialised are check bits
nobody can read — with one difference that decides everything: **the RAM
has something that can write it.**

### 4.2 The sweep, and why it writes whole words

`boot_crt0.S`:

```
  la    t0, boot_trap_vectors
  csrw  mtvec, t0
  li    t0, SOC_RAM_BASE
  li    t1, SOC_RAM_BASE + SOC_RAM_SIZE
1:
  sw    zero, 0(t0)
  addi  t0, t0, 4
  bltu  t0, t1, 1b
```

Three properties, each of which is a decision:

**It is first.** Not "early" — first, before the stack pointer is set.
The loader's stack, its `.data` and its `.bss` are all inside the region
it is initialising, so nothing that touches memory may run before it.
The loop uses three registers and performs no load at all.

**It writes WORDS.** A RAM row holds four independent byte codewords and
a byte write updates one lane's data and its eight check bits together
through the macro's own `A_BM` (`docs/67` section 3.3). So a word store
makes all four lanes of that word valid at once, and a **byte** store
makes one lane valid and leaves three as they powered up — and a later
32-bit load of that word reads all four lanes and gets an uncorrectable
from the three nobody wrote. **A loader that initialised the RAM a byte
at a time would leave it in exactly the state it was trying to leave
behind.**

**There is no `.bss` loop after it.** The sweep is strictly stronger
than zeroing `.bss`, and `link_boot.ld`'s `__bss_start`/`__bss_end`
survive only so that `boot.c` can check the sweep's bounds covered them.

**It costs 49,178 cycles for 8,192 words — 6.003 cycles per word**
**[fact, `boot: cycles sweep=0x0000c01a`, and the same figure in every
run in this document]**. That is 26.5 % of the boot and 11.8 % of the
whole run, and section 8 puts it against the watchdog's budget.

### 4.3 The counterfactuals, and what each one measures

The sweep is invisible in a passing simulation unless the RAM is modelled
as powering up undefined, so `tb_soc.v` now does that: `+ram_random=<seed>`
fills the data array **and the check array** with pseudo-random bits at
1 ns, after `soc_mem.v`'s own initial blocks have left every row a valid
all-zero codeword and long before reset releases 20 clocks later.
`flow/sim_soc.sh` passes it **by default**; `SOC_RAM_RANDOM=0` reproduces
the pre-`docs/68` model, in which the memory is already initialised and
the sweep proves nothing.

| build | RAM at power-up | result |
|---|---|---|
| shipped | random | **PASS**, 28 of 28, 415,324 cycles **[fact]** |
| `-DBOOT_NO_SWEEP` | **zeroed** (`SOC_RAM_RANDOM=0`) | **PASS**, 357,856 cycles — and this row is the trap: with the memory already initialised, a loader with no sweep at all works perfectly **[fact, `s68-nosweep0/sim.log`]** |
| `-DBOOT_NO_SWEEP` | random | section 4.4 |
| `-DBOOT_SWEEP_BYTE` | random | section 4.4 |

The second row is why `SOC_RAM_RANDOM` defaults to 1 and why
`sw/tests/test_soc_boot_guards.py` checks that it does. A default of 0
would make every run in this document vacuous in exactly the way
`docs/41` section 6.6 counts.

It also isolates the sweep's cost cleanly: **28 cycles** for the `.data`
relocation alone against **49,178** with the sweep in front of it
**[fact, both from `boot: cycles sweep=`]**.

### 4.4 The two failures, measured

With the RAM powered up undefined, both counterfactuals fail, and they
fail in the same place for the same reason:

| build | what it does | outcome |
|---|---|---|
| `-DBOOT_NO_SWEEP` | nothing writes the RAM before it is read | **timeout at 900,095 cycles, no hand-over, `double_fault_seen_o` asserted**, last fetch `0xC0000980` **[fact, `s68-nosweep/sim.log`]** |
| `-DBOOT_SWEEP_BYTE` | one byte per word is written; three lanes of every row are left as they powered up | **the same**, last fetch `0xC0000980` **[fact, `s68-bytesweep/sim.log`]** |

`0xC0000980` is inside `boot_trap_entry`, and `0x00007C08` — the last
data address in both — is inside the loader's own stack. The failure is
therefore exact and it is the predicted one: the loader takes a load
access fault on the first RAM word nobody wrote, enters its trap
handler, and **the handler reads a word nobody wrote too**, faults
again, and the core reports a double fault. The two builds reach it
through different first words and end in the same state.

**The byte sweep is the one worth having.** A loader written by somebody
who had read `docs/67` and concluded "initialise the RAM" would pass
every review and would produce this: a memory in which **every** word
has exactly one valid lane, which is worse than an untouched memory
because it looks initialised. The scrubbers' own counters say how much
worse — they walk the memory throughout and report what they found:

| build | `CNT_RAMSEC` | `CNT_RAMDED` |
|---|---:|---:|
| `-DBOOT_NO_SWEEP` | 346 | **1,706** |
| `-DBOOT_SWEEP_BYTE` | 277 | **1,648** |
| shipped | 0 | 0 |

**[fact, the `[TB] scrub:` line of each run]**

The byte sweep repairs fewer rows and leaves nearly as many
uncorrectable, which is the number that says a lane of valid data does
not help a word whose other three lanes are noise.

### 4.5 The scrubber counts a boot as if it were radiation

Found by running it, and it is a finding about `docs/67`'s block rather
than about this one.

`docs/44` section 11's rule is that a mechanism which ships disabled and
has never caught anything is a liability, so `soc_scrub.v` brings both
scrubbers up **enabled** and `soc_scrub_props.v` C6 proves it. The RAM
scrubber therefore starts walking on the first idle cycle after reset —
**across a memory the sweep has not reached yet.** Every row it gets to
first reads as an uncorrectable, because that is what an uninitialised
protected word is, and `SCRUB.CNT_RAMDED` counts it:

```
boot: scrub saw the uninitialised RAM: sec 0x00000000 rd 0x00000000 ded 0x00000001 -- clearing
```

**[fact, every power-on boot in this document, `ded` = 1]**

One, and not more, because the bus is busy almost every cycle during the
sweep and the scrubber only takes idle ones. But one is enough to matter:
`CNT_RAMDED` is a telemetry counter, an operator reads it as an upset
rate, and **a part that reported one uncorrectable per power cycle would
be reporting its own boot as a radiation event.**

The loader clears the three RAM sources, and the discipline is exact:

- **Only on the power-on boot** (`BSTAT.CNT == 0`). On any later boot the
  RAM was initialised by the previous one, the scrubber cannot
  manufacture a count, and the record is a record — clearing it there
  would destroy precisely the evidence `docs/44` built the counters for,
  and would do it at the moment an operator most needs it.
- **Only the RAM's three.** The ROM's are never touched; nothing in this
  flow writes the ROM.
- **The window is stated rather than closed.** An upset in the ~49,000
  cycles between power-on and the clear is lost. Nothing is running in
  that window.

---

## 5. The loader

### 5.1 The image, and where its geometry comes from

Two slots in the modelled device, `0x018000` and `0x01C000`, 16 KiB
apart so that no 4 KiB sector and no 64 KiB block of the W25Q128JV holds
both. Each is an eight-word header followed by the body:

| word | field | checked how |
|---:|---|---|
| 0 | `MAGIC` = `NSB1` | compared first, and separately, so an erased region fails here |
| 1 | `LOAD` | section 5.3 |
| 2 | `BYTES` | section 5.3 |
| 3 | `ENTRY` | section 5.3 |
| 4 | `CSUM` | section 5.2 |
| 5 | `VERSION` | not checked; carried for the log |
| 6 | reserved | — |
| 7 | `HCSUM` | **the eight words sum to zero**, which is one comparison and needs no constant in the loader |

GR716B validates an application image with *"header, code, data checksum,
and header checksum"* (`docs/08` section 2.4) and this is that at this
part's scale. **`gen_boot_image.py` takes `LOAD` and `ENTRY` out of the
linked ELF** rather than being told them, so a program that moved cannot
be loaded to where it used to be, and `link_app.ld` asserts that `_start`
is at the base of the RAM region.

**Two copies in one device is the weakest form of redundancy** and the
document says so: it survives a corrupted sector and not a dead part. It
is what a board with one flash and two chip selects can offer without a
second device; `BSTRAP.SRC` already selects the chip select, so a board
with two devices needs no change to this loader.

### 5.2 The checksum is computed from the RAM

The copy loop writes what the controller delivered. A **second pass reads
those words back out of the RAM** and sums them, and that sum is what is
compared with the header's.

That is the difference between checking the flash read and checking the
image. A word that arrived intact and landed on a row whose codeword did
not take is caught by the second and invisible to the first — and on a
memory where every row is a codeword and a bad one answers with a bus
error, the read-back is also **where an uncorrectable in the loaded image
is detected**. `boot_crt0.S`'s synchronous handler records the fault and
returns; `boot.c` compares the fault count across the pass and turns a
difference into `BOOT_CAUSE_ECC`, which is a reason to try the other
image rather than a machine that stops.

It costs one extra pass over the image: **17.01 cycles per word**,
31,792 cycles for the 1,869-word image **[fact]**, against 44.06 cycles
per word for the copy itself. **The verify is 39 % of the copy's cost**,
which is the price of the distinction and is stated so that a mission
with a much larger image can decide it again.

### 5.3 The geometry check, and what it is protecting

`LOAD`, `BYTES` and `ENTRY` come out of a flash the loader has not yet
decided it can trust, and they are about to be used as a destination.
Four things must hold and each one is a way to destroy the machine that
is checking:

- `LOAD` and `BYTES` are **word-aligned and a whole number of words**, or
  the copy writes partial words and leaves check bits uninitialised in
  the middle of the image — section 4's hazard, reintroduced by the fix
  for it;
- `BYTES` is not zero;
- the image lies inside the RAM **and below `__boot_private`**, so the
  copy cannot overwrite the stack of the loader that is running it;
- `ENTRY` is inside the image.

`link_boot.ld` puts the loader's `.data`, `.bss` and stack in the **top
1 KiB** of the RAM and the image at the bottom precisely so that this
check has something to compare against. The `geom0` counterfactual is an
image whose header is otherwise perfect and whose `LOAD` is `0x7F00`:

```
boot: geometry load=0x00007f00 bytes=0x00001d34 entry=0x00007f00
boot: image 0x00000000 rejected, cause 0x00000004
boot: image 0x00000001 at 0x0001c000
```

and the run goes on to pass 28 of 28 from the secondary image **[fact,
`s68-geom0/sim.log`]**.

### 5.4 The watchdog is kicked on progress, not on a schedule

`docs/40` section 5.4 refuses a stage-1 handler that kicks, because it
*"would let a program that does nothing else keep the watchdog satisfied
from inside its own failure"*. The same rule applies to a copy loop, and
it is applied the same way: `wdog_kick()` is called from **inside** the
loop that moves words, gated on the word index (`w & 255 == 255`), so a
loop that is moving words keeps the watchdog satisfied and a loop that is
stuck does not.

**Was it needed?** Measured rather than assumed, and the honest answer
is **no, not in any configuration this part can currently be built in** —
which is worth writing down properly rather than leaving as a comfortable
silence.

The watchdog's longest timeout is a constant of the netlist:
`2^16 × 16 = 1,048,576` clocks (`soc_wdog.v` W2). The boot measured here
is **195,068 cycles**, 18.6 % of it. Extrapolating the two per-word
figures to the **largest image this RAM can hold** — 7,936 words, the
32 KiB less the loader's private KiB — gives **554,971 cycles, 52.9 % of
the budget** **[estimate, arithmetic on section 8.2's measured 6.003,
44.06 and 17.01 cycles per word]**. So at the divider this design uses,
a loader with no kick at all would still finish.

**Three things move it over, and each is a change somebody may make.**
`DIV` is a software-writable field of the QSPI controller
(`soc_qspi.v`'s `CONF`), and a word on the wire costs `16(DIV+1)` clocks:

| `DIV` | copy, cycles/word | boot with the largest image |
|---:|---:|---:|
| 0, this design | 44 | 554,495, **53 %** of the budget |
| 3 | 92 | 935,423, **89 %** |
| 7 | 156 | **1,443,327 — over** |
| 15, the slowest | 284 | 2,459,135, over by 2.3x |

and the RAM is the second: `docs/67` section 3.4 keeps the two-words-per-
row arm for the day a sized workload wants 64 KiB back, and that is a
98,353-cycle sweep and a 16,128-word ceiling — **1,104,432 cycles,
over the budget on its own** **[estimate, the same arithmetic]**. The
third is a board that needs a slower SCK for signal integrity, which is
`DIV` again for a reason that is not a choice.

**So the kick is what makes the loader's correctness independent of the
divider, the image and the size of the RAM**, none of which it can see,
and it costs one keyed store per 256 words. That is the argument for
building a mechanism this configuration does not need, and it is exactly
the argument `docs/44` section 11 refuses in the other direction — a
mechanism that ships disabled and catches nothing — with the difference
that this one is enabled, is exercised on every boot, and is one store.

---

## 6. What happens when boot fails

### 6.1 The ladder, and why it is the watchdog's

`docs/40` W1 and W2: the watchdog is armed at reset, a write of 0 to its
enable is accepted and ignored, and its longest timeout is a constant of
the netlist. So **a loader that retried for ever would be reset by it.**

That is not a constraint to work around. It is the escalation, and this
loader uses it rather than building a second one — because a second
ladder would be a second thing that can be misconfigured, a second thing
whose state must survive a reset, and a second candidate for `docs/40`
section 7.2's brick.

| level | what fails | what happens |
|---|---|---|
| **within a boot** | the primary image's magic, header checksum, geometry, body checksum or ECC | the **secondary image** is tried, from a different 16 KiB region of the device |
| | the flash does not identify at all | no image is tried; the report says `NOFLASH` |
| **across boots** | both images fail | the loader **shortens the watchdog to its minimum, loads it, and stops kicking**. Stage 1 raises the NMI into a handler that deliberately does not acknowledge; stage 2 resets the part. `BOOTREG.BSTAT.CNT` reads one higher on the next boot and **no software can write it** |
| **the end** | `BSTAT.CNT` reaches `BSTAT.LIMIT` | the loader **does not touch the flash at all**. It reports `GIVEUP` and takes the same exit, and the part resets with `WDOGN` asserted and BOOTREG carrying why |

### 6.2 Three, and the reason it is three

`BOOT_LIMIT = 3` is a parameter of `soc_boot.v` reported through
`BSTAT.LIMIT`, and it is tied to `soc_top.v`'s `WDOG_ESCALATE = 2` by an
argument rather than by taste:

- the watchdog asserts its external pin on its **second** stage-2 reset
  (`docs/40` section 5.4, stage 3), which is the reset that begins boot
  number 2;
- the loader's last attempt is boot number `LIMIT - 1` = 2;
- so **the last boot the loader attempts is one during which the platform
  supervisor has already been told.** Software gives up after the
  hardware has escalated, never before.

`sw/tests/test_soc_boot_guards.py::test_the_attempt_limit_and_the_watchdogs_escalation_agree`
reads both parameters out of `soc_top.v` and fails if that inequality
stops holding, which is the only way the relationship survives somebody
changing one of them.

### 6.3 Shortening the watchdog on the way out, and why that is safe

The give-up path writes a **short** reload and loads it. That is the
register `docs/40` section 7.2 is a document about — a short timeout that
software installed before it went wrong, surviving the reset that going
wrong caused, and bricking the SoC in a loop that never reached the
console.

It is safe here for the reason that document's fix supplies: **a stage-2
reset restores the reload to the maximum.** So a short reload lasts
exactly until the reset it exists to hasten, and the next boot gets the
whole budget. The loader shortens it only on a path whose only exit is
that reset, and `test_the_give_up_path_shortens_the_watchdog_and_stops_kicking`
checks both halves — the shortening here and the restore in
`soc_wdog.v` — because the safety of the first is entirely a property of
the second.

The alternative was to leave the maximum timeout and spin, which costs
about 2.1 million clocks per failed boot doing nothing. Hastening the
reset is a decision about how quickly the platform is told, and it is
made in the direction of telling it sooner.

### 6.4 The ladder, run

Stages 2 and 3 are not reachable from a loader that works, for exactly
`docs/40` section 6.2's reason one level up: they only happen when
software has given up, which a working loader does not do. So there is
one extra build, `-DBOOT_GIVEUP_DEMO`, identical to the normal one
except that **it refuses every image until the watchdog has asserted its
external pin** — which is the platform having been told — and then boots
normally, so that the whole ladder is in one terminating log:

```
boot: strap 0x84000000 cnt 0x00000000 of 0x00000003 stat 0x00030000 wdog 0x00000000 rpt 0x00000000
boot: scrub saw the uninitialised RAM: sec 0x00000000 rd 0x00000000 ded 0x00000001 -- clearing
boot: giveup demo, refusing the flash
boot: giving up; the watchdog will reset this part
boot: strap 0x84000000 cnt 0x00000001 of 0x00000003 stat 0x00030001 wdog 0x00000102 rpt 0xb00000f1
boot: giveup demo, refusing the flash
boot: giving up; the watchdog will reset this part
boot: strap 0x84000000 cnt 0x00000002 of 0x00000003 stat 0x00030102 wdog 0x00000206 rpt 0xb00101f1
boot: giveup demo, the pin is asserted; booting
boot: image 0x00000000 at 0x00018000
boot: entering 0x00000000
...
RESULT PASS
[TB] boot: 1 hand-over, the last at cycle 417118
[TB] bootreg: bstrap 0x84000000 bstat 0x00030102 brpt 0xb0020200 epoch 0x00000003
[TB] watchdog: stage1 2, stage2 2, stage3 1
```

**[fact, `hw/soc/out/s68-giveup2/sim.log`]**

Three boots of the same part in one simulation, and every field of the
argument is in the trace:

- **`BSTAT.CNT` reads 0, 1, 2** — the counter no software can write,
  advancing once per boot;
- **`WDOGSTAT` reads `0x000`, `0x102`, `0x206`** — `WDOGRST` then
  `WDOGRST | ESCALATED`, with `RSTCNT` 0, 1, 2 — so **the two counters
  agree at every step**, which is what section 7.2 said must be visible;
- **`BSTAT` bit 8 (`LAST`) is set on the third boot** and not before, so
  the loader knows it is on its last attempt without carrying a copy of
  the limit;
- **`BRPT` carries the previous boot's cause across each reset**:
  `0xb00000f1` is magic `B0`, boot count 0, watchdog reset count 0,
  image `F` (none), cause 1 (`NOFLASH`); `0xb00101f1` is the same one
  boot later;
- **`EPOCH` reads 3** at the end: three boots, three epochs, and section
  7.4's reason for the register;
- and the watchdog's own summary — **stage 1 twice, stage 2 twice, stage
  3 once** — is `docs/40` section 6.2's ladder, now driven by a loader
  declining to kick rather than by a handler declining to acknowledge.

**The third boot is the one the design is about.** The loader reaches it
with the external pin already asserted, which is what
`BOOT_LIMIT - 1 >= WDOG_ESCALATE` buys: had the limit been two, software
would have stopped trying on the boot *before* the platform was told.

### 6.5 The NOBOOT strap, and the bound on it

`BSTRAP` bit 2 is GR716B's "direct boot" bootstrap in the only form this
part can offer it: **do not load an image.** The loader reports it, keeps
the part alive for a bounded number of heartbeats, and then takes the
same exit every failure takes.

**The bound is a decision and not an omission.** A strap that parked the
part in a kick loop for ever would be software holding a spacecraft in a
state no operator can leave; the pin says "do not boot", not "never
escalate". And there is nothing to wait for: **this part has no ingress
channel** — the console UART is transmit-only (`docs/39`), SpaceWire, CAN
and I2C are assessed and unbuilt (`docs/65` section 9), and the QSPI
controller talks to a flash and not to a ground station. GR716B's standby
mode waits for a remote boot over one of five interfaces; a loader here
that waited would be a hang with a good name.

**The day an ingress channel exists, this is where standby goes and the
bound goes away.** That is section 16 item 3.

```
boot: strap 0x84000004 cnt 0x00000000 of 0x00000003 stat 0x00030000 wdog 0x00000000 rpt 0x00000000
boot: NOBOOT strap; staying in the ROM
boot: idle
boot: idle
boot: idle
boot: idle
boot: giving up; the watchdog will reset this part
boot: strap 0x84000004 cnt 0x00000001 of 0x00000003 stat 0x00030001 wdog 0x00000102 rpt 0xb00000f8
boot: NOBOOT strap; staying in the ROM
...
```

**[fact, `hw/soc/out/s68-noboot/sim.log`, `SOC_STRAP=4`]**

`BSTRAP` reads `0x84000004`: `VALID`, four straps, and bit 2 set. The
report carries cause 8, `NOBOOT`. **This run does not terminate and is
not expected to** — it is a part being reset for ever with a reason on
the console and in a register, which is the correct behaviour and the
thing `docs/40` section 7.2's brick was not: that one reset for ever
*with the console never reaching its first character*. It is run with
`SOC_TIMEOUT_CYCLES=700000` so that observing it costs seven hundred
thousand cycles rather than five million, and `flow/sim_soc.sh` reports
it as a failure, correctly, because nothing reached `WFI`.

---

## 7. The bootstrap pins and the boot report

### 7.1 The one field with authority is the one software cannot write

That sentence is the whole design rule of `soc_boot.v`, and it is what
keeps a register block that survives resets out of `docs/40` section
7.2's brick loop.

| field | domain | who writes it | authority |
|---|---|---|---|
| `BSTRAP` | power-on | **the pins**, once, three clocks after power-on reset releases | reported; the loader acts on `NOBOOT` and `SRC` |
| `BSTAT.CNT` | power-on | **hardware**, on each release of the system reset, saturating | **this is the escalation**, and no APB write of any value to any offset moves it |
| `BSTAT.LIMIT` | — | nothing; it is a parameter | the bound, and no register reaches it |
| `BRPT` | power-on | software | **none**. Evidence |
| `EPOCH` | power-on | software | **none**. Evidence |

`docs/40` W5 keyed *every* write to the watchdog because its acknowledge
had authority — an unkeyed acknowledge would let a core spraying stores
hold the machine in stage 1 for ever. **This block needs no key, and the
reason is the table**: nothing writable here has any authority at all.
That is a stronger statement than a key, because a key protects a field
that could still be forged by code that knows the key, and a field
hardware maintains cannot be forged at all.

**And nothing in this block reaches anything.** Its only outputs are
`prdata_o`, `pready_o` and `pslverr_o`.
`test_the_boot_block_drives_nothing_but_its_own_read_data` asserts
exactly that port list, because the failure `docs/40` found was a
persistent register that could shorten the next boot's budget, and a
persistent register that cannot reach the budget at all is the structural
version of the same fix.

### 7.2 Why there are two counters

`soc_wdog.v` already carries `RSTCNT`, saturating and power-on-only. On
this SoC every non-power-on reset is a watchdog stage-2 reset, so **today
the two counters are the same number** — and the loader prints both, so
that the day they differ it is visible rather than invisible.

They are two counters because they count different things:

- `RSTCNT` counts **stage-2 assertions by the watchdog**. It is the
  watchdog's own escalation input, inside its key-protected,
  triple-redundant bank.
- `BSTAT.CNT` counts **releases of the system reset**, whatever asserted
  it, with the power-on boot counting zero.

A boot loop driven by something the watchdog did not cause — an external
reset pin, a brownout, a debug reset, none of which this SoC has yet —
must still terminate. Counting the boot is the general statement and
counting the watchdog is the special case.

**The power-on boot counts zero**, and that is a decision with a name in
the RTL: `armed_q`. The power-on release is a release like any other and
would otherwise be counted; instead it arms the counter. `BSTAT.CNT`
therefore reads *"boots before this one"*, which is the number a loader
deciding whether to attempt **this** boot needs, and
`test_the_power_on_boot_is_boot_zero` and formal D3 both say so.

### 7.3 The straps are sampled once

Two synchroniser flops per pin, then a hold at the third clock, then
never again. `soc_wdog.v` W1's argument, one block across: *a pin that
could disable the watchdog at any moment would be a hardware backdoor
into the one block whose job is to be unstoppable* — and a pin that could
change the boot source after the boot began is the same backdoor into the
boot decision. `BSTRAP.VALID` says the sample has been taken, so a read
in the first three clocks — which no software can take, because the core
is fetching its first instruction — is distinguishable from a strap field
of zero.

A **system** reset does not re-sample: the sample belongs to the power
cycle, not to the boot. A **power cycle** does, because a board that is
rewired and power-cycled must read the new wiring. Both halves are tests
(`test_the_sample_is_taken_once_and_the_pins_are_then_ignored`,
`test_a_power_cycle_re_samples`) and formal D4, and the mutation
`strap_sysrst` — resample on a system reset — is caught by three of the
fourteen tests.

`BSTRAP` also carries **`WDOGDIS`, the watchdog's own bootstrap pin,
sampled here a second time**. It is reported and not consumed:
`soc_wdog.v` samples the same wire for itself and `WDOGSTAT.DISABLED` is
authoritative. Two samples of one static pin that must agree is a cheap
cross-check, and it is what makes the map's promise of "bootstrap pin
readback" true for the one bootstrap pin this SoC had before this
document.

### 7.4 The epoch

`docs/58` section 5.2 planned the recovery from an uncorrectable in
`mtime` — *"it re-epochs"* — and observed that the correlation with
absolute time has to come from outside. `mtime` is in the system reset
domain and a stage-2 reset zeroes it, so **every boot starts a new epoch
whether anything asked for one or not.** `EPOCH` is where the epoch's
identity lives: a word in the power-on domain that the loader increments
once per boot, so that two readings of `mtime` taken in different epochs
are distinguishable as such.

It is deliberately **not** a copy of `mtime` and not a second time base.
Nothing here counts. Reconstructing elapsed time across a reset needs a
counter in the power-on domain that this part does not have, and
`docs/58`'s `mcycle` reconstruction is still **[planned]**. What this
register removes is the weaker failure of not being able to tell that a
re-epoch happened at all — and the escalation run of section 6.4 shows it
reading 3 after three boots.

---

## 8. The invariant, and what it becomes

`docs/66` section 8 asked that every document after it quote **217,682**.
A boot flow changes what the program is and where it runs, so the number
moves; what follows is every step of the move, each measured in this
session, so that none of it is attributed to the wrong thing.

| # | configuration | cycles | what changed from the row above |
|---|---|---:|---|
| 1 | HEAD (`ed51de0`), program as committed, fetched from the boot ROM | **217,682** | — (reproduces `docs/66` exactly) **[fact, `s68-base/sim.log`]** |
| 2 | HEAD, **the same program with section 10.3's alignment fix**, from the ROM | **217,630** | one attribute on one declaration: four byte accesses become one word access, twice **[fact, `s68-base-same/sim.log`]** |
| 3 | this work: the identical program, **loaded from flash into RAM and run there** | **220,256** in the image | **+2,626, +1.207 %.** Section 8.1 **[fact, `s68-ship/sim.log`]** |
| 4 | the same run, whole | **415,324** | + 195,068 cycles of boot. Section 8.2 |

And the two demonstration images, for completeness, both of which now
boot through the loader rather than being fetched from the ROM:

| image | checks | boot | in the image | whole |
|---|---:|---:|---:|---:|
| `-DQSPI_DEMO`, `docs/66`'s flash demonstration | 5 | 153,326 | **60,673** | 223,652 |
| `-DWDOG_RESET_DEMO`, `docs/40`'s escalation | 5 | three boots | 9,067 (the third) | 318,131 |

**[fact, `s68-qspi2/sim.log`, `s68-wdog/sim.log`]**. `docs/66` measured
its demonstration image at 60,706 cycles from the ROM against 60,673
here, and **the 33-cycle difference is not attributed**: both the image
and where it runs from changed, and unlike row 3 there is no controlled
pair for it. It is quoted so that the two are not confused, not as a
measurement of anything.

**Rows 1 and 2 are the same design and rows 2 and 3 are the same
program**, which is what makes row 3's difference attributable. Row 2 was
produced from a `git worktree` at `ed51de0` carrying a byte-identical
`hw/soc/tb/sw/test_ibex.c`, `docs/66` section 14's method.

**Every document after this one should quote 220,256 for the program and
415,324 for the run**, and should say which it means.

### 8.1 Why the program is 1.207 % slower from RAM

Not because RAM is slower than ROM: they are the same module with the
same one-cycle response (`soc_mem.v`, `soc_mem_sram.v`, the `g_rd1` arm
in both). The difference is the **fabric**.

With the program in the ROM, instruction fetch goes to slave 1 and every
load and store goes to slave 0, and the two masters never contend for a
slave port. With the program in RAM **both go to slave 0**, and
`soc_bus.v` arbitrates: one of them waits. +2,626 cycles over a
217,630-cycle program is one stall per 83 cycles **[estimate, arithmetic
on the two measurements]** — small because this program is dominated by
UART polling and by the NPU's serial transport, both of which are
peripheral traffic, and because the core is a two-stage machine that
issues at most one data access per instruction.

**This is a measurement of one program and it does not generalise.** A
loop that is dense in loads and stores would pay more. What it does
establish is the shape of the trade the boot flow makes: an image in RAM
costs contention on one port and buys a program that is not bounded by
8 KiB of ROM.

### 8.2 Where the 195,068 cycles of boot go

The loader reads `mtime` at five points and prints the four differences
once, at the end. `soc_top.v` instantiates the CLINT at `TICK_DIV = 1`,
so one tick is one system clock and the low half of `mtime` is a cycle
counter that starts at zero on every system reset.

| phase | cycles | per unit | what it scales with |
|---|---:|---|---|
| **sweep** — `boot_crt0.S`'s RAM initialisation and `.data` relocation, from reset | **49,178** | **6.003 / word** over 8,192 words | the size of the RAM |
| **open** — the console, the report, the straps, the JEDEC identification and the QE bit | **17,506** | — | fixed, plus the console |
| **hdr** — one quad I/O frame for the primary header | **3,636** | — | fixed |
| **copy** — one quad I/O frame for the body, pulled through the controller's one-word pause | **82,344** | **44.06 / word** over 1,869 words | the size of the image |
| **verify** — reading the image back out of the RAM and summing it | **31,792** | **17.01 / word** | the size of the image |
| the console between them | 10,612 | — | how much the loader says |
| **total to hand-over** | **195,068** | | |

**[fact, `boot: cycles sweep=0x0000c01a open=0x00004462 hdr=0x00000e34
copy=0x000141a8 verify=0x00007c30` and the hand-over cycle
`tb_soc.v` reports]**

Two of these are worth reading carefully.

**The copy is 44 cycles per word and the flash is not the reason.** A
quad I/O word is 8 SCK periods and SCK is `clk/2` at `DIV = 0`, so the
device delivers a word every 16 clocks. The other 28 are **software
polling `QSPI_STAT` over the APB bridge**, which is what `docs/66`
section 3.1's "the storage is where software is, not where the block is"
costs when the software is a loader rather than a test. A FIFO, or the
interrupt the controller already has, would take most of it back; neither
is built and section 12 says so.

**The per-word figures are stable across every image size in this
document.** The watchdog escalation demonstration loads a 1,188-byte
image and measures 13,164 cycles of copy over 297 words — **44.32 per
word** — and 5,062 of verify — **17.04 per word** **[fact,
`s68-wdog/sim.log`]**. Two images differing by a factor of 6.3 give
per-word costs differing by 0.6 %, which is what makes the extrapolation
in section 5.4 worth making at all.

---

## 9. Measured area, and the layout

### 9.1 The block alone

Same recipe as `docs/39` section 6, `docs/65` section 7 and `docs/66`
section 9: Yosys `stat -liberty` on `ihp-sg13g2` at the typical corner,
the same driving cell and load, a 20 ns target. Gate equivalent =
`sg13g2_nand2_1` = 7.2576 um2.

| Block | Cells | Flops | Area, um2 | kGE |
|---|---:|---:|---:|---:|
| `soc_boot` | **303** | **92** | **7,229.0610** | **0.996** |

**[fact, `hw/soc/flow/syn_soc.sh soc_boot`]**

The 92 flip-flops are the whole of the block and every one of them is
named: 8 strap synchronisers and 2 for the watchdog pin, 2 for the
sampling delay, 1 `VALID`, 4 held straps, 1 held watchdog pin, 1 system
reset sample, 1 `armed`, 8 of boot counter, and **64 of report and
epoch**. Two thirds of the block is the two words that survive a reset,
which is `docs/56`'s accounting — *"twelve are the two reports and not
the two mechanisms"* — in its starkest form yet, and section 7.4 is why
they are worth it.

### 9.2 The whole SoC, and why two numbers are reported

Both against baselines re-measured **in this session** from a `git
worktree` at `ed51de0` with `hw/soc/{gen,genp,tools,ext}` symlinked in.

| configuration | cells | flops | area, um2 |
|---|---:|---:|---:|
| baseline, `ROM_HARDEN` = 1 | 46,350 | 5,833 | 692,735.0850 |
| **this work**, `ROM_HARDEN` = 1 | 46,064 | 5,925 | **693,706.6206** |
| difference | **−286** | **+92** | **+971.5356, +0.140 %** |
| baseline, `ROM_HARDEN` = 0 (the netlist the layout uses) | 44,917 | 5,730 | 673,967.2338 |
| **this work**, `ROM_HARDEN` = 0 | 45,609 | 5,822 | **684,404.4942** |
| difference | **+692** | **+92** | **+10,437.2604, +1.549 %** |

**[fact, `SOC_MEM=sram hw/soc/flow/syn_soc_top.sh 20`, four runs]**

**The baseline's 673,967.2338 um2 is exactly the `--cell-area` `docs/67`
section 14 gave its floorplan generator** **[fact]**, which is the
strongest available evidence that the baseline reproduces that document's
netlist rather than approximating it.

**And the two differences do not agree, which is the finding.** The
flip-flop delta is +92 in both — the block's own count, exactly, in both
configurations. The area delta is +971 um2 in one and +10,437 in the
other, a spread of 9,466 um2 for a block whose standalone area is 7,229.
`soc_top` is flattened before technology mapping (`docs/47` section 6.2),
so a change of this size perturbs the mapping of things it does not
touch, and one configuration's mapping happened to recover 286 cells
elsewhere. **The honest reading is that this flow's whole-design area
measurement has a noise floor larger than a 1 kGE block**, so the block's
own 7,229.0610 um2 is the number to use and the whole-SoC deltas are
reported as a range with their configurations attached — `docs/44`
section 9.5's rule. `docs/67`'s +31,391 um2 for a much larger change is
comfortably outside that floor and is not called into question by this.

### 9.3 The layout

Placed and routed on `docs/67`'s die with `docs/67`'s floorplan
(`config-ecc.json`, unchanged and not regenerated), against a baseline
placed and routed **in the same session, side by side, on the same
config** — which is what `PNR_STATE` was added for. Both are the
`ROM_HARDEN = 0` netlist, `docs/67` section 8's measurement knob, so
that this comparison is against that document's layout and not against a
different one.

**The baseline reproduces `docs/67` section 5.3 exactly.** Every metric
below matches `hw/soc/pnr/runs/s67ecc/final/metrics.json` to the last
digit — `-4.415898882660414` of setup slack, `0.10122436508841427` of
hold, 880,499 um2 of placed standard cells, 0 DRC, 4 antenna-violating
nets **[fact]** — which is the strongest available evidence that what
follows is a difference of netlist and of nothing else.

| | baseline (`ed51de0`) | this work | difference |
|---|---:|---:|---:|
| die area, um2 | 4,786,290 | 4,786,290 | **0** |
| die bounding box, um | 2306.4 x 2075.22 | 2306.4 x 2075.22 | **identical** |
| macro area, um2 | 2,246,900 | 2,246,900 | 0 |
| **placed standard-cell area, um2** | 880,499 | **897,986** | **+17,487, +1.986 %** |
| fill cells, um2 | 1,051,290 | 1,033,800 | −17,490 |
| sequential cells | 5,730 | **5,822** | **+92** |
| sequential-cell area, um2 | 280,724 | 285,229 | +4,505 |
| timing-repair buffers, um2 | 162,763 | 165,954 | +3,191 |
| utilisation | 72.078 % | 72.481 % | +0.403 pp |
| **detailed-routing DRC errors** | **0** | **0** | — |
| routed vias | 443,544 | 460,711 | +17,167 |
| antenna-violating nets / pins | 4 / 6 | **0 / 0** | −4 / −6 |
| antenna diodes | 405 | 692 | +287 |
| setup slack, slow corner, ns | −4.4159 | **−4.3045** | **+0.1114** |
| setup TNS, slow corner, ns | −5,742.57 | −5,275.81 | +466.76 |
| hold slack, fast corner, ns | +0.1012 | **+0.0715** | −0.0297 |
| hold slack, slow / typ, ns | +0.5927 / +0.2858 | +0.5847 / +0.2618 | −0.0080 / −0.0239 |
| clock skew, worst setup, ns | 1.0457 | 1.0681 | +0.0224 |

**[fact, `hw/soc/pnr/runs/{s68base,s68boot}/final/metrics.json`]**

Five things are worth reading off it.

**The die does not grow, and the fill absorbs the block.** +17,487 um2
of standard cells against −17,490 um2 of fill: the boot block and the
repair it pulled in went into space that was already there, and the
utilisation moved four tenths of a point. `docs/67` said the same of a
change seven times larger.

**The 92 sequential cells are the block's 92 flip-flops, exactly.** The
other 12,982 um2 of the difference is combinational logic and repair
buffers — 3,191 um2 of the latter — which is what a new APB slave costs
in a design whose peripheral read mux it widens.

**Hold is still closed at all three corners**, and it is the number that
moved worst: +0.1012 ns to +0.0715 ns at the fast corner, a 29 % cut in
a margin that was already the smallest in the design. It closes, and
`docs/47` section 7.1's checker is bound to all three corners, so this
is a checked result and not an unchecked one — but **0.07 ns is 3.5 % of
a 2 ns library setup and the next block that lands near the clock tree
should look at it before assuming there is room.**

*Corrected 2026-09-05 by `docs/70-boot-hardening-placed.md` section
5.3: the 29 % is not a measurement. That document placed a control
pair — the same design on the same die and the same configuration,
two netlists at an identical 5,822 flip-flops differing only by
`docs/69` section 7.1's one-cell refactor of this block — and
fast-corner hold moves by **0.0198 ns** between them, which is 67 % of
the −0.0297 ns above. The direction may be right; the magnitude is
inside the instrument. **The advice in the sentence stands and is what
`docs/70` acted on**, and its answer, with `docs/69`'s 51 further
flip-flops in this block, is that hold closes at all three corners and
is 0.0104 ns better rather than worse.*

**Setup got 0.11 ns better and that is not an improvement this work
made.** The design does not close at 20 ns — `docs/47` section 8.2's
43.10 MHz — and its binding path is the register file's read address,
which this document does not touch. A netlist 1.99 % larger placed on
the same die perturbs placement everywhere; +0.1114 ns of worst slack
and +466.76 ns of TNS are that perturbation. **Reported, not
attributed**, which is `docs/67` section 5.3's discipline for the same
situation with the sign the other way.

**The antenna violations went to zero and that is the same kind of
noise.** Four violating nets became none while the diode count rose by
287; the flow inserted more diodes because placement moved, not because
the boot block fixed anything.

**And the router check that did not run, re-checked rather than
inherited.** `docs/67` section 11 found that the detailed router emits
`[WARNING DRT-0349] LEF58_ENCLOSURE with no CUTCLASS is not supported.
Skipping for layer <L>` and that the lines are a property of the
`ihp-sg13g2` technology LEF. **Both runs here emit ten such lines, layer
for layer and count for count** — `Cont`, `Via1` (twice), `Via2`,
`Via3`, `Via4`, `TopVia1` (twice) and `TopVia2` (twice) **[fact,
`grep DRT-0349` over both logs]**. So `0 detailed-routing DRC errors`
means zero errors among the rules the router did check, and via
enclosure on those layers was not among them, in both columns of the
table above.

**Runtimes are the flow's own per-step timers and nothing else.** The
two runs were placed and routed **concurrently**, on a machine that also
carried a process from an unrelated project throughout, so their
elapsed times are contended with each other and with that — which is
exactly why they are not quoted. What is quoted is what each step's
`runtime.txt` says it took: detailed routing at **1 h 08 m 42 s** for
the baseline and **1 h 02 m 53 s** for this work, and 59 timed steps
summing to **3 h 01 m 37 s** and **2 h 56 m 23 s** **[fact]**. Those two
are comparable with each other, because they are the same 59 steps on
the same flow; they are **not** a measure of what either run would cost
alone.

---

## 10. Defects found, all of them by running it

### 10.1 A sentinel inside the range of the thing it was a sentinel for

`try_image` returned *"the entry point, or 0 if the image cannot be
used"*. `link_app.ld` puts `_start` at the base of the RAM region, which
is **`0x00000000`**. So every successful load of a correct image was
reported as a failure, and the console said:

```
boot: image 0x00000000 rejected, cause 0x00000000
```

— rejected, with cause `BOOT_CAUSE_OK`. **The contradiction inside that
one line is what located it**, and it is worth recording because the
whole design is careful about this in hardware and was not in software:
`soc_scrub.v` latches an uncorrectable address and never clears it
because *"a zero would look like a valid address"*, and this is the same
mistake one abstraction up. Success is now its own return value and the
entry point is written through a pointer. `boot_crt0.S`'s guard changed
with it, from `beqz a0` — which rejected every good boot — to a range
check against the RAM region, which is what is actually impossible.

### 10.2 A scrubber counting a boot as radiation

Section 4.5.

### 10.3 Undefined behaviour that had been harmless since `docs/38`

Test 10 checks the PMP. It takes `__pmp_buf`, declared `extern char
__pmp_buf[]`, and dereferences it as a `volatile uint32_t *`. The linker
script places it on a 64-byte boundary and **asserts** it, and the
program checks the alignment again at run time before programming the
NAPOT encoding — but a bare `extern char[]` tells the compiler the
alignment is **one**, and dereferencing it as a 32-bit object on a target
that does not permit unaligned access is undefined behaviour. The
compiler expanded it into four byte accesses.

That had been true and harmless since `docs/38`. When the program moved
out of the boot ROM and into RAM the register allocation around test 10
changed, and the byte accesses were emitted through a base register that
the surrounding code had since reloaded with the value of a different
variable. Three of the four bytes went to `0x01234468` — an address in no
region — and took bus errors.

**The symptom was `mcause 5` inside a PMP test**, which reads exactly
like a PMP failure and is not one, and it cost the two observations that
`tb_soc.v` now has permanently:

- **`+errtrace`** prints every bus error with its address. A PMP
  violation never reaches the fabric, so **an `mcause 5` with no line
  here is the core's own permission check and one with a line here is the
  memory or the decode.** That distinction is not available from inside
  the program and it is what separated the two hypotheses.
- **`+ftrace_from`/`+ftrace_to`** print every granted fetch and data
  access in a cycle window. It showed the byte load, its address and the
  instruction it came from, and ended the question.

The fix is to declare the alignment the linker script already guarantees:
`extern char __pmp_buf[] __attribute__((aligned(64)))`. The access
becomes one aligned word, the undefined behaviour is gone, and the
application image shrinks by 268 bytes. **It is a fix to a latent defect
and not a workaround**, and row 2 of section 8's table is what it costs:
−52 cycles.

### 10.4 A check that had become a check that the loader did not run

`docs/66`'s test 29 asserts that the flash's Status Register-2 reads
**zero** before the program sets the quad-enable bit — *"SR2 reads 0 out
of the box"*, which was true of a part nothing had touched.

Since this document the loader touches it: it reads the image on four
lanes, so it sets QE, with the volatile write (50h then 31h) that is not
undone by anything short of a power cycle. **The test therefore became a
test that the loader had not run, and it failed for exactly that reason
the first time the program was loaded rather than fetched.** What is
checked instead is the property that still holds and that the application
actually depends on: QE is **already set** on entry, and setting it again
is idempotent.

This is the second time in this document that a check written against a
part in its power-on state stopped being true because something now runs
before the program. The first was section 4.5's scrub counters. **Both
are the same lesson: a boot flow moves the boundary of "what has already
happened when the program starts", and every check that assumed nothing
had is now wrong.** Section 12 lists what has not been re-examined
against that.

### 10.5 A fault injector that fired before the fault could exist

`+ded_word` corrupts a RAM word's check field on the edge after the
loader writes it. The first version fired on the **first** write — which
is the **sweep's**, not the copy's — so the corrupted word was
overwritten by the copy a moment later and the run passed while appearing
to have injected a fault. `+ded_skip` defaults to 1 for that reason. It
is `docs/41` section 6.6's shape in a testbench: a mechanism that looks
applied and is not.

---

## 11. Verification

Four kinds of evidence, `docs/41` section 6's division, each blind to
what the others see.

### 11.1 cocotb

`hw/soc/tb/cocotb/test_soc_boot.py`, **14 tests, 14 passed** **[fact]**,
at `CNT_W = 4` so that saturation is reachable in a suite that drives one
reset release per iteration. Expectations come from `docs/08` section
2.4, `docs/40` W1 and W4, `docs/41` section 3.1 and the generated map —
never from the RTL. Highlights:

- **`test_no_write_can_move_the_boot_counter`** — every offset in the
  slot's first sixteen words, four values each, including two a runaway
  core would plausibly produce. This is the block's reason for existing.
- **`test_every_system_reset_release_counts_one_boot`** — and a reset
  held for a varying number of cycles is still one boot, so the length of
  the assertion cannot inflate the count.
- **`test_the_report_and_the_epoch_survive_the_reset_they_describe`** and
  **`test_a_power_cycle_clears_the_record`** — the two halves that must
  both hold.
- **`test_the_straps_are_reported_as_they_were_wired`** — all sixteen
  values of the four-pin field, because a strap field that reported the
  right number of bits and the wrong ones would look exactly like this
  test passing on one value.

### 11.2 Formal

`hw/soc/formal/soc_boot.sby`: **bmc (depth 20), prove (k-induction, depth
10), prove_full at the shipped `CNT_W = 8`, and cover — four tasks, all
PASS, 6 of 6 cover statements reached** **[fact]**.

D1 is the one that matters and it is written over `wr` rather than over
any particular offset, so it holds for every offset the decode has **and
every offset it does not**: no APB write changes the boot counter, in any
reachable state. D2 adds that the counter moves only on a release and
saturates; D3 that the power-on boot is boot zero; D4 that the straps are
sampled once; D5 that the report and the epoch change only on a write to
their own offset and that a system reset does not touch them; D7 the APB
contract; D8 that `BSTAT`'s two derived flags are the comparisons they
claim to be.

**Two properties were wrong before the design was**, and both were found
by the bounded check rather than by reasoning:

- **the release, written as an edge.** The block samples `rst_ni` into
  `sys_q` and counts where `rst_ni` is high and the sample is not, which
  is evaluated with the values the flip-flops had going *into* the edge.
  Writing the property as an edge between `$past(rst_ni)` and `rst_ni` is
  the obvious thing and is a different event by one cycle; BMC found it
  at step 5.
- **`LAST`, written in the counter's own width.** At `CNT_W = 4` the
  counter saturates at 15 and `cnt + 1` in four bits is 0, so the
  natural-looking form of D8 is false at the top of the range while the
  design is right. BMC found it at step 16. The property is now stated
  one bit wider; the design's own form, `cnt >= LIMIT - 1`, cannot wrap,
  **which is why it is written that way** and why restating it in the
  plus-one form is worth doing at all.

### 11.3 Mutation evidence

`python3 hw/soc/tb/cocotb/mutate_soc_boot.py`: **8 of 8 caught** **[fact]**.

Each mutation is a boot flow that **works on a healthy part** and fails
only in the case the block exists for:

| mutation | what it is | caught by |
|---|---|---|
| `cnt_writable` | an APB write to `BSTAT` loads the counter — a counter the failing software can clear, `soc_wdog.v` W1's rejected design one level up | `test_no_write_can_move_the_boot_counter` |
| `cnt_wraps` | saturation removed: a part that has rebooted 2^CNT_W times drops back below the limit and starts the ladder again | `test_the_counter_saturates_and_never_wraps` |
| `cnt_por_zero` | the power-on boot is counted, so every limit is off by one and the last attempt is not the boot the watchdog escalated on | five tests |
| `cnt_on_level` | counts the level of the system reset rather than its release | three tests |
| `strap_live` | the straps are resampled every cycle | `..._sampled_once...` |
| `strap_sysrst` | resampled on a system reset: the sample belongs to the boot instead of the power cycle | three tests |
| `rpt_sysrst` | the report and the epoch in the system reset domain — erased by the reset they exist to describe, `docs/40` section 7.2's operator-facing failure | `..._survive_the_reset_they_describe` |
| `last_off_by_one` | `LAST` against `LIMIT` instead of `LIMIT - 1` | `..._the_comparisons_a_loader_would_write` |

### 11.4 The guards, and where they sit

`sw/tests/test_soc_boot_guards.py`, **18 tests** **[fact]**. They exist
because the properties that hold this design together are properties of
the **wiring** and of the **order**, which neither a block-level suite
nor a proof can see, and they are placed at the stage that can satisfy
each one:

- the counter's authority is a property of the RTL, so it is checked
  there (`..._entirely_in_the_power_on_domain`,
  `..._drives_nothing_but_its_own_read_path`);
- that the counter counts **boots** is a property of `soc_top.v`'s
  wiring, so it is checked there
  (`..._gives_the_boot_block_both_resets_the_right_way_round`);
- the limit's relation to the watchdog's escalation is a property of two
  parameters in one file, so it is checked between them;
- **the sweep's correctness is a property of the ORDER of instructions**,
  so it is checked in `boot_crt0.S`
  (`..._is_the_first_thing_that_touches_the_ram`,
  `..._writes_whole_words_in_the_shipped_build`);
- and that the simulation can see any of it is a property of the flow, so
  `..._power_up_model_is_on_by_default` and
  `..._reaches_the_check_field` are checked in `sim_soc.sh` and
  `tb_soc.v`.

### 11.5 The counterfactual matrix

Every branch of section 6's escalation, each reached by breaking exactly
one thing, and each checked against the cause code the loader reported:

| run | what is broken | expected cause | result |
|---|---|---|---|
| `s68-ship` | nothing | — | **PASS**, 28 of 28, 415,324 cycles |
| `s68-magic0` | the primary image's magic word | 2, `MAGIC` | rejected with **cause 2**, secondary boots, **PASS** |
| `s68-csum1` | one bit of one body word, after the checksum was taken | 5, `CSUM` | `boot: csum 0xb7be9150 want 0xb7be9151`, **cause 5**, secondary boots, **PASS** |
| `s68-geom0` | the primary's load address, into the loader's private RAM | 4, `GEOM` | `load=0x00007f00`, **cause 4**, secondary boots, **PASS** |
| `s68-ded3` | two check bits of one RAM word, on the edge after the loader writes it | 6, `ECC` | `boot: fault cause=0x00000005 pc=0xc000066c`, **cause 6**, secondary boots, **PASS**, `CNT_RAMDED` = 2 |
| `s68-giveup2` | every image, until the pin is asserted | 1, `NOFLASH` | the ladder of section 6.4, **PASS** |
| `s68-noboot` | nothing; the strap says do not boot | 8, `NOBOOT` | section 6.5, does not terminate |
| `s68-nosweep`, `s68-bytesweep` | the sweep | — | section 4.4, both fail |

**[fact, the eight logs named]**

The `ECC` row is the one that needed the most machinery to reach and it
is the one that matters most: an uncorrectable inside an image the
loader has just written, found by the read-back pass, reported with the
faulting PC inside the loader, and answered by loading the other copy.

### 11.6 Everything else, re-run

| suite | result |
|---|---|
| `.venv/bin/python -m pytest sw/tests` | **437 passed** **[fact]** |
| `scripts/run_cocotb.sh` | **387 passed, 0 failed, 0 suites not clean**, over 16 suites in `hw/soc/tb/cocotb` and 6 in `hw/tb` **[fact]** |
| `cd hw/soc/formal && make` | **56 SymbiYosys tasks over 14 jobs, 56 PASS, 0 FAIL**, plus the `soc_wdog_tmr` parameter guard **[fact]** |
| `verilator --lint-only` on `soc_boot.v` | clean **[fact]** |

**Three guards fired before the flows were updated, and passed after**,
which is what they are for:
`test_every_flow_that_builds_soc_top_reads_every_module_it_instantiates`
and `test_the_whole_soc_elaborates_as_one_design` both failed on a
`soc_top.v` that instantiated `soc_boot` before four source lists knew
about it — `docs/57` and `docs/59`'s defect, caught this time by the
check that exists because of it — and `test_doc_links` failed until this
document had a row in the index.

**And one lint finding is worth recording**: Verilator's `WIDTHTRUNC` is
an error in this repository's lint, and the first version of
`soc_boot.v` narrowed its `LIMIT` parameter to the counter's width by
implicit assignment. The part-selects are now explicit, the synthesised
result is byte-identical (`soc_top.netlist.v` compares equal before and
after **[fact]**), and what the diagnostic was protecting is real: a
`LIMIT` that did not fit in `CNT_W` bits would silently have become a
different limit.

---

## 12. What the checks do NOT cover

Stated at length, in the discipline `docs/47` section 9, `docs/58`
section 11 and `docs/67` section 11 set.

- **The macros cannot be signed off, and therefore neither can the die.**
  `docs/12` section 8's NO-GO stands and `docs/54` section 7 closed the
  KLayout exit. Nothing here changes any of those numbers, and section
  3.2's decision that the flight ROM is a mask ROM is a decision about a
  part **no open deck in this environment can check**.
- **THE MASK ROM IS A DECISION AND NOT A DESIGN.** There is no ROM
  generator on this PDK, so nothing in this repository has ever
  elaborated, synthesised, placed or simulated one. Section 3's argument
  is an argument; what exists is two SRAM macros and a `$readmemh`.
- **The RAM sweep is checked against a MODEL of an SRAM.** `soc_mem.v`'s
  power-up is `tb_soc.v` writing pseudo-random bits into two arrays. A
  real SRAM's power-up state is not uniform random, is correlated between
  neighbouring cells, and can be repeatable per die. What is established
  is that a loader which writes every word makes every word readable;
  what is not is anything about the distribution it is writing over.
- **One seed.** `+ram_random=1` in every run in this document. Nothing
  swept the seed.
- **The flash is a behavioural model.** `docs/66` section 12's first
  bullet, unchanged and now load-bearing for boot rather than for a
  demonstration: that the loader obeys the datasheet as the model states
  it is established; that it works with a device is not.
- **The image is 1,869 words and the RAM is 8,192.** No image near the
  RAM's capacity has been loaded, and every figure in section 5.4's
  table is arithmetic on two measured per-word costs, not a run. **No
  divider other than 0 was run at all**, so the three rows that put the
  boot over the watchdog's budget are extrapolations of a rate measured
  at one point.
- **`BOOT_LIMIT` is 3 and only that value was run.** The relationship to
  `WDOG_ESCALATE` is proved as an inequality by a guard and demonstrated
  at one pair of values.
- **Section 6.2's alignment assumes the watchdog's ladder is the only
  thing that resets the part.** It is, on this SoC; the guard checks the
  inequality and not the assumption.
- **The two image slots are in ONE modelled device.** A boot from chip
  select 1 is selected by a strap the testbench can set and was **not
  run**; `docs/66` established that a frame to that chip select reads the
  pull-ups on this board, so a run would fail at the JEDEC check, which
  is the right answer for a board with nothing there and not a test of
  redundancy across devices.
- **No fault-injection campaign was re-run.** `flow/fi_core.sh` and
  `flow/fi_npu.sh` read `soc_boot.v` now and their benches tie `strap_i`
  to the board, but neither was executed — the position `docs/61`,
  `docs/65` and `docs/66` took, for the same reason. **`soc_boot.v` is
  unprotected**: an upset in the boot counter changes a boot decision,
  an upset in the report corrupts a diagnosis, and neither is voted,
  coded or scrubbed. Section 16 item 5.
- **The uncorrectable path is reached by ONE directed injection**, at one
  word, on one boot. There is no rate and no fault model behind it.
- **Nothing checks that the loader's console output is what an operator
  would want.** The lines are diagnostics chosen while debugging.
- ~~**Section 10.4's lesson has not been applied exhaustively.** Two
  checks were found that assumed nothing had run before the program; the
  other twenty-six were not re-examined against that assumption, and a
  third one may exist.~~ **Superseded 2026-09-12 by section 16 item 5**,
  which re-examines all thirty `check(n, ok)` call sites in
  `test_ibex.c`, corrects the counting in the struck sentence, and finds
  **two more** — checks 20 and 21, both on `WDOGSTAT`. The bullet stands
  because it is what this document knew on the day. What replaces it is
  narrower and is in that item: the re-examination was run in one
  configuration, and a boot from the secondary device, a slower `SCK` or
  a second RAM seed was not put under it.
- **The whole-SoC area is synthesis at a 20 ns target with the SRAM
  boundary**, and section 9.2 measures its own noise floor rather than
  assuming there is none.
- **No frequency.** `docs/53` section 9.2's three grounds and `docs/05`
  section 4 rule 5, unchanged.
- **A ROUTER CHECK DID NOT RUN, AND IT IS THE PDK'S.** `docs/67` section
  11's `LEF58_ENCLOSURE` finding is inherited by both layouts here and is
  re-checked in section 9.3 rather than assumed.

---

## 13. Corrections to earlier documents

Every one is a dated in-place note by `docs/64`'s rule; the original
sentences stand.

- **`docs/66` section 8**: "Every document after this one should quote
  217,682 for the 28-check image" — section 8 of this document is what it
  becomes and why.
- **`docs/66` section 7.1**: "the bring-up program has outgrown the boot
  ROM" — it has, and it no longer needs to fit: the ROM holds a 3,104-byte
  loader and the program is bounded by the RAM.
- **`docs/66` section 7.2 item 3**: test 29's "SR2 reads 0" is now a
  check that the loader did not run. Section 10.4.
- **`docs/67` section 15 item 2**: "Place the ROM's check macros" was
  ranked second. On section 3's decision the flight ROM needs no check
  macros at all, and what they protect is the stand-in. The item is not
  wrong; its priority is now conditional on which candidate a part takes.
- **`docs/67` section 9**: the ROM's contents are still listed as
  unprotected in the flight part, and section 3.2 keeps that true while
  naming what would change it.
- **`docs/58` section 5.2**: the re-epoch was **[planned]**; the epoch's
  identity now exists in hardware and the loader maintains it. The
  reconstruction of elapsed time is still [planned].
- **`docs/44` section 11**: "a mechanism that ships disabled and has
  never caught anything is a liability" — the rule stands, and section
  4.5 records the cost it has on a memory nothing has initialised yet.
- **`docs/60`**: a v0.2 of the datasheet is now owed by three documents.
- **`README.md`** and **`docs/00-index.md`**: the boot flow.

---

## 14. Files touched

### 14.1 RTL, under `hw/soc/rtl/`

| file | change |
|---|---|
| `soc_boot.v` | **new** |
| `soc_top.v` | `BOOT_NSTRAP`, `BOOT_LIMIT`, `strap_i`, the slot decode, `u_boot`, the three muxes, the header |

**Nothing in `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is
modified. `docs/34`'s freeze is untouched.**

### 14.2 Software, under `hw/soc/tb/sw/`

| file | change |
|---|---|
| `boot.c`, `boot_crt0.S`, `link_boot.ld`, `link_app.ld`, `soc_boot.h` | **new** |
| `test_ibex.c` | the alignment attribute on `__pmp_buf` (section 10.3), test 29's QE precondition (section 10.4), and `mepc` in test 10's diagnostic |

`crt0.S` is **unchanged**, and that is deliberate: its `.data`
relocation loop still runs and now copies onto itself, so the program
whose cycle count section 8 compares is the same program.

### 14.3 Flows and testbench

| file | change |
|---|---|
| `hw/soc/flow/gen_boot_image.py` | **new** |
| `hw/soc/flow/build_sw_soc.sh` | two programs and the image between them |
| `hw/soc/flow/sim_soc.sh` | the power-up model, the straps, the injector, the timeout, the pass-through, `BOOT_CORRUPT`, symbols from the application ELF, `soc_boot.v` in the source list |
| `hw/soc/flow/pnr_soc_top.sh` | `PNR_STATE` |
| `hw/soc/flow/syn_soc.sh`, `syn_soc_top.sh`, `fi_core.sh`, `fi_npu.sh` | `soc_boot.v` in every source list the guard checks |
| `hw/soc/tb/tb_soc.v` | the power-up model, the DED injector, the straps, the hand-over, `+errtrace`, `+ftrace_*`, the BOOTREG report |
| `hw/soc/tb/tb_soc_fi.v`, `tb_soc_npu_fi.v` | `strap_i` tied to the board |

### 14.4 Map and verification

| file | change |
|---|---|
| `regmap/memmap.yaml` | one field: BOOTREG reserved → implemented, and its description |
| `docs/memmap-soc.md`, `sw/golden/memmap_gen.py` | regenerated |
| `hw/soc/formal/soc_boot.sby`, `soc_boot_props.v`, `Makefile` | **new**, and one target |
| `hw/soc/tb/cocotb/test_soc_boot.py`, `Makefile.soc_boot`, `mutate_soc_boot.py` | **new** |
| `sw/tests/test_soc_boot_guards.py` | **new** |
| `.gitignore` | the new job's working directories and the mutation scratch |
| `docs/68-boot-flow.md`, `docs/00-index.md`, and the dated notes of section 13 | this document |

---

## 15. Reproducing this

```
python regmap/generate_memmap.py
.venv/bin/python -m pytest sw/tests -q
scripts/run_cocotb.sh

cd hw/soc/tb/cocotb && make -f Makefile.soc_boot        # 14 tests
python3 hw/soc/tb/cocotb/mutate_soc_boot.py             # 8 of 8
cd hw/soc/formal && make boot                           # 4 tasks
cd hw/soc/formal && make                                # every job

# the design, with the RAM powered up undefined
hw/soc/flow/sim_soc.sh hw/soc/out/s68-ship

# the sweep, both ways it can be got wrong
SOC_RAM_RANDOM=1 SW_DEFINES=-DBOOT_NO_SWEEP   SOC_TIMEOUT_CYCLES=900000 \
    hw/soc/flow/sim_soc.sh hw/soc/out/s68-nosweep
SOC_RAM_RANDOM=1 SW_DEFINES=-DBOOT_SWEEP_BYTE SOC_TIMEOUT_CYCLES=900000 \
    hw/soc/flow/sim_soc.sh hw/soc/out/s68-bytesweep
SOC_RAM_RANDOM=0 SW_DEFINES=-DBOOT_NO_SWEEP \
    hw/soc/flow/sim_soc.sh hw/soc/out/s68-nosweep0

# one broken image at a time, and the fall-back to the other
BOOT_CORRUPT=magic0 hw/soc/flow/sim_soc.sh hw/soc/out/s68-magic0
BOOT_CORRUPT=csum0  hw/soc/flow/sim_soc.sh hw/soc/out/s68-csum0
BOOT_CORRUPT=geom0  hw/soc/flow/sim_soc.sh hw/soc/out/s68-geom0
SOC_DED_WORD=300    hw/soc/flow/sim_soc.sh hw/soc/out/s68-ded2

# the ladder, and the strap
SW_DEFINES="-DBOOT_GIVEUP_DEMO -DQSPI_DEMO" SOC_TIMEOUT_CYCLES=2000000 \
    hw/soc/flow/sim_soc.sh hw/soc/out/s68-giveup2
SOC_STRAP=4 SOC_TIMEOUT_CYCLES=700000 hw/soc/flow/sim_soc.sh hw/soc/out/s68-noboot

# the two demonstrations that were already there
SW_DEFINES=-DWDOG_RESET_DEMO hw/soc/flow/sim_soc.sh hw/soc/out/s68-wdog
SW_DEFINES=-DQSPI_DEMO       hw/soc/flow/sim_soc.sh hw/soc/out/s68-qspi2

# area, this work and the baseline, four runs
SOC_MEM=sram hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s68-syn
SOC_MEM=sram SOC_ROM_HARDEN=0 hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s68-rom0-syn
hw/soc/flow/syn_soc.sh soc_boot
```

The baseline rows of sections 8 and 9 were produced from a clean
`git worktree` at `ed51de0` with `hw/soc/{gen,genp,tools,ext}` symlinked
in — `docs/65` section 14's method — running the same four commands, and
for section 8 row 2 with `hw/soc/tb/sw/test_ibex.c` copied across so the
two runs are the same program.

The two layouts of section 9.3 are `docs/67` section 14's recipe on
`docs/67`'s floorplan, run **side by side** rather than one after the
other, which is what `PNR_STATE` exists for:

```
SOC_MEM=sram SOC_ROM_HARDEN=0 hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s68-rom0-syn

SYN_NETLIST=$PWD/hw/soc/out/s68-rom0-syn/soc_top.netlist.v \
PNR_CONFIG=$PWD/hw/soc/pnr/config-ecc.json \
PNR_STATE=$PWD/hw/soc/pnr/state/s68boot.state.json \
hw/soc/flow/pnr_soc_top.sh s68boot --overwrite -F Yosys.JsonHeader \
    -S Yosys.Synthesis -S Checker.YosysUnmappedCells \
    -S Checker.YosysSynthChecks -S Checker.NetlistAssignStatements \
    -i $PWD/hw/soc/pnr/state/s68boot.state.json
```

and the same three lines with `s68base`, the baseline worktree's
netlist and `state/s68base.state.json`. **`config-ecc.json` is
`docs/67`'s, unchanged and not regenerated**: the die, the six macro
placements and the density target are that document's, so a difference
between these two runs is a difference of netlist and of nothing else —
and a difference between either of them and `docs/67` section 5.3's is a
difference of netlist too.

---

## 16. What the next block should be

1. **Harden `soc_boot.v`, or decide not to.** It is 92 unprotected
   flip-flops, and eight of them decide whether the part tries to boot
   again. An upset in the boot counter is not a wrong number in
   telemetry: it is a part that gives up early or never gives up.
   `docs/41`'s triple-redundant word costs about three times the state
   plus a voter and the frozen `tmr_voter.v` is already in the design;
   `docs/58` section 4.4's argument against TMR for a counter applies to
   `mtime` and not obviously to this one, because this counter is not
   monotone in a way a residue can check across a reset. It is a decision
   with a measured price and it is the highest-consequence thing this
   document leaves open.
2. **Place the ROM's check macros, or record that the mask ROM decision
   retires them.** `docs/67` section 15 item 2, now conditional on
   section 3.
3. **An ingress channel, and then standby.** Section 6.5: the loader's
   terminal state is "hand the decision to the platform" because there is
   nothing to wait for. A UART receiver is the cheapest ingress this SoC
   could have — the block is already there and half of it is built — and
   it would turn `NOBOOT` from a bounded monitor into GR716B's standby
   mode.
4. **Reduce the copy's 44 cycles per word.** Section 8.2: 28 of the 44
   are software polling a status register. The controller already has an
   interrupt line and the map already gives it a vector; a loader that
   used it, or a FIFO in the controller, would take most of it back, and
   the measurement to compare against is in this document.
5. ~~**Re-examine the remaining twenty-six checks against section 10.4's
   lesson.** Two of the twenty-eight assumed that nothing had run before
   the program. Nothing has looked at the others.~~ **Closed 2026-09-12,
   and it is not a formality: two of the twenty-eight ARE affected, they
   are checks 20 and 21, and the run that shows it was already on this
   disk when the sentence above was written.** The struck sentence stands
   by `docs/64`'s rule; everything below corrects it.

   **WHERE THE LIST IS, AND WHY THE ARITHMETIC ABOVE IS WRONG TWICE.**
   `docs/66` does not enumerate the checks, it counts them. The list is
   the `check(n, ok)` call sites in `hw/soc/tb/sw/test_ibex.c`, and there
   are **thirty distinct numbers, 1 to 30, with no gaps** **[fact,
   `grep -o 'check([0-9]*,' | sort -nu`; check 10 appears at two call
   sites, on mutually exclusive arms of its alignment guard]**.
   Twenty-eight of them compile into the default image — every run in
   this document ends `checks run: 0x0000001c` — and checks 29 and 30
   exist only under `-DQSPI_DEMO`, which is `docs/66` section 7.1's
   second image. So **neither of the two already found was one of the
   twenty-eight.** Section 4.5's is the `SCRUB` telemetry counters, and
   **no check in this program reads them at all**: `SCR_` does not appear
   in `test_ibex.c`, which is why that one was found by reading a console
   line rather than by a failing check. `docs/66`'s test 29 is in the
   demonstration image. The set that had not been looked at was therefore
   **twenty-nine — the twenty-eight, plus check 30** — and not
   twenty-six.

   **WHAT THE BOOT FLOW LEAVES BEHIND**, which is what the re-examination
   is against. `boot.c` has twenty-six store sites and every store in
   `boot_crt0.S` is to the RAM **[fact, grep]**:

   | state | what the loader does to it | undone by |
   |---|---|---|
   | the RAM, all 8,192 words | `sw zero` over `[RAM_BASE, RAM_TOP)` in `boot_crt0.S`, then the 1,869-word image copied over the bottom of it | rewritten on every boot |
   | `mtvec`, `sp`, `gp` | set to the loader's own | the application's `crt0.S`, before `main` |
   | UART0 `SCALER` and `CTRL` | `UART_SCALER_VAL` and `TE` — the same two constants `uart_init()` writes, from the same `-D` on the same command line | system reset; and the application writes them again anyway |
   | WDOG `CTRL` | a keyed `GPT_LD` about ten times per boot. `RLD` is written only on the give-up path, which by construction never reaches an application | system reset, which also restores `RLD` to the maximum (`docs/40`) |
   | QSPICTL `CONF`, `CTRL`, `STAT`, `ADDR`, `CMD`, `TX` | the whole register-mode driver; left idle with `STAT` clear, `IEN` off and `CS` on the strap's device | system reset |
   | the W25Q128JV's `SR2.QE` | set, with the volatile 50h/31h pair | **a power cycle and nothing else.** `hw/soc/tb/flash_w25q128jv.v` has three ports — `cs_n`, `sck`, `io` — and no reset input, so QE survives every reset this SoC can generate. Section 10.4 |
   | `SCRUB` `CNT_RAMSEC`, `CNT_RAMRD`, `CNT_RAMDED` | cleared once, and only on the power-on boot (`BSTAT.CNT == 0`). Section 4.5 | — |
   | BOOTREG `BRPT` and `EPOCH` | written on every boot | power-on reset |
   | `WDOGSTAT` | **not written — no software can write it.** The give-up path makes the *hardware* write it, by declining to kick | power-on reset |

   `pmpcfg`, `pmpaddr`, `mie`, `mstatus`, `mscratch`, `mtimecmp`, `msip`
   and every address in the GPIO slot (`0xFF902000`) and the NPU slot
   (`0x10000000`) appear in neither file **[fact, grep]**. That negative
   half is why most of the verdict table is short.

   **THE VERDICTS**, one row per check. "Power-on state" means state the
   check did not set itself:

   | check | what it assumes about state it did not set | verdict |
   |---:|---|---|
   | 1 | nothing; `alive` is a local `volatile` | UNAFFECTED — no memory-mapped state at all, and the RAM it uses was written by the sweep |
   | 2 | nothing | UNAFFECTED — core registers only |
   | 3 | nothing | UNAFFECTED — its operands are `static volatile` in `.data`, carried by the image itself |
   | 4 | nothing | UNAFFECTED — it writes all eight bytes of `buf` before it reads any |
   | 5 | nothing | UNAFFECTED — core only |
   | 6 | nothing | UNAFFECTED — the stack, which `link_app.ld` puts in RAM the sweep wrote |
   | 7 | its own instruction stream | UNAFFECTED — it asserts a property of the image's own bytes; the loader is what put those bytes in RAM and cannot alter them |
   | 8 | `mscratch`, and that `mcycle` advances | UNAFFECTED — the loader writes no CSR but `mtvec`, `sp` and `gp`, and `mcycle` is compared as a difference, so the boot's 195,068 cycles are invisible |
   | 9 | nothing | UNAFFECTED — `trap_count` is read as a baseline first, and `crt0.S` zeroes `.bss` |
   | 10 | that no PMP region is locked | UNAFFECTED — `pmpcfg` and `pmpaddr` appear nowhere in `boot.c` or `boot_crt0.S`, so nothing is locked at hand-over; `__pmp_buf` is seeded by the check itself |
   | 11 | `trap_saw_rvc == 0` | UNAFFECTED — `.bss`, zeroed by the application's own `crt0.S` after the loader's sweep |
   | 12 | that the PLIC region is undecoded | UNAFFECTED — a property of the fabric's decode, which no software writes |
   | 13 | the PnP table's IDENT and ENDIAN words | UNAFFECTED — `0x4E530001` and `0x00000001` are generated into both `soc_pnp.v`'s ROM and `soc_memmap.h`, and neither word encodes per-slot state, so BOOTREG going reserved → implemented cannot move them |
   | 14 | that the boot ROM refuses a store | UNAFFECTED — the ROM is read-only to the fabric whoever is running. **Its stated reason is now stale**: the program no longer executes out of that region, so what a wild store would destroy is the loader for the next boot rather than the running code. Prose, not a defect |
   | 15 | that `mtime` advances, and that an unimplemented CLINT offset faults | UNAFFECTED — the loader reads `CLINT_MTIMEL` five times and writes no CLINT register; `mtime` is compared as a difference, so starting near 195,068 rather than near zero is invisible |
   | 16 | that `mie` and `mstatus.MIE` are clear on entry | UNAFFECTED — and this is the one worth stating out loud. `boot_crt0.S`'s table is thirty-one spins and one recorder, the loader enables nothing maskable, and it drives its one assigned line — the QSPI controller's — by polling. Both CSRs are still at their reset values when the application starts |
   | 17 | that `mtimecmp` is the check's own | UNAFFECTED — the check sets it, and `MTIMECMP` appears nowhere in the loader |
   | 18 | that `msip` is clear | UNAFFECTED — `CLINT_MSIP` appears nowhere in the loader |
   | 19 | `GPT_CONFIG`, and the general timers' prescaler | UNAFFECTED — the loader's only write into the timer slot is the watchdog's keyed `CTRL`, and the watchdog has its own fixed `PRESCALE` that no register reaches (`soc_wdog.v`); `GPT_SCRELOAD`, which the check writes itself, is untouched |
   | **20** | **`WDOGSTAT.WDOGRST` clear and `WDOGSTAT.RSTCNT` zero — "this run was not started by the watchdog"** | **AFFECTED** |
   | **21** | **`WDOGSTAT.WDOGRST` clear after the NMI — "stage 2 has not fired"** | **AFFECTED** |
   | 22 | nothing about `mtvec`'s prior value | UNAFFECTED — it compares against `trap_vectors`, a symbol of the *running image*, and restores that; the loader's `mtvec` is a ROM address the application's `crt0.S` overwrote before `main` |
   | 23 | NPUCFG's identity, version and geometry at reset | UNAFFECTED — the NPU slot is not in the loader's store set |
   | 24 | the node window's `NPU_RST_*` values | UNAFFECTED — same; nothing has reached the die, so its reset values are still its reset values |
   | 25 | that the reserved parts of the window fault | UNAFFECTED — same |
   | 26 | a node in its reset state, and no prior ECC event | UNAFFECTED — same, and `docs/66` already made `NPUCFG_CNT` a delta rather than an absolute |
   | 27 | that `IRQCAUSE.EVT` is clear on entry | UNAFFECTED — that precondition is check 26 having drained the capture queue, not a power-on value, and the loader never reaches the NPU |
   | 28 | `GPIO.DIR` and `GPIO.DATA` read zero "out of reset" | UNAFFECTED — **and this is the closest thing in the twenty-eight to test 29's shape.** It survives for a specific reason and not a general one: the GPIO slot is in neither the loader's store set nor anything else's, and nothing in the SoC drives those pads before the check does |
   | 29 | `SR2` reads zero | AFFECTED — section 10.4, found and closed before this item |
   | 30 | that quad I/O is available | UNAFFECTED, and now over-determined: its EBh frames need QE set, which check 29 used to provide and which the loader now provides first |

   **TWO ARE AFFECTED, AND THE MEASUREMENT WAS ALREADY ON DISK.**
   `hw/soc/out/s68-giveup/sim.log` is section 6.4's ladder demonstration
   carrying **the twenty-eight-check image** instead of the demonstration
   image. It reaches the application on the third boot, after two
   watchdog resets:

   ```
     wdog ctrl=0x0000000b stat=0x00000206 rld=0x0000ffff
     FAIL test 0x00000014
     nmi cause=0x8000001f vec=0x0000001f stat=0x00000206 spun=0x00000164
     FAIL test 0x00000015
   checks run: 0x0000001c  fail mask: 0x00300000
   RESULT FAIL
   ```

   **[fact]**. `0x00300000` is bits 20 and 21. `WDOGSTAT` reads `0x206` —
   `WDOGRST` set, `ESCALATED` set, `RSTCNT` = 2 — and **every other term
   of both checks passed**: the unkeyed write was ignored, the keyed
   disable was ignored, `DISABLED` was clear, the NMI arrived at vector
   `0x1F` with cause `0x8000001F` in 356 spins and was acknowledged, and
   `RLD` read `0xFFFF`, which incidentally measures `docs/40`'s rule that
   a stage-2 reset restores the reload after the loader shortened it to
   2,000 on the two boots before. **Both checks failed on the single
   proposition that no watchdog reset had happened in this power cycle.**

   So this item is not an argument with a run behind it; it is a run.
   **The twenty-eight-check program has been entered after the loader ran
   three times and the watchdog reset the part twice, and exactly two of
   the twenty-eight failed.**

   **THE MECHANISM IS NOT TEST 29's, AND THAT IS WHY IT WAS MISSED.**
   Test 29 asserted the power-on value of a register **the loader
   writes**. Checks 20 and 21 assert the power-on value of a register
   **no software can write at all** — and they are affected anyway,
   because the loader's escalation makes the *hardware* write it before
   the program starts. Before this document, `RSTCNT != 0` at the
   application's first instruction meant exactly one thing: the
   application had hung and stage 2 had reset it, which is a defect and
   which these two checks are right to report. Since this document it can
   also mean the loader gave up on an earlier boot and a later attempt
   succeeded — **the recovery working, reported as a watchdog defect.**
   That is section 10.4's lesson in its general form: the test is not
   "what does the loader write", it is "what has already happened".

   And the run was not lost, only unaccounted for. `s68-giveup` is
   `s68-giveup2` without `-DQSPI_DEMO`; section 15's recipe for the
   demonstration carries the define and section 6.4 quotes only the run
   that has it, while `hw/soc/out/s68-matrix.txt` records
   `s68-giveup done rc=1`. **Why the define was added is nowhere in this
   document; what it steps around is on disk**, and this item is where
   that is accounted for.

   **WHAT NEEDS DOING.** It is the same shape of fix as section 10.4's
   and as `docs/66`'s event-counter refactor — compare against what was
   true on entry, not against the power-on value — and neither part of it
   is a hardware change or touches `soc_wdog.v`:

   - **Check 20** must stop requiring `RSTCNT == 0`. BOOTREG is
     implemented now and `boot.c` already compares
     `WDOG_ST_RSTCNT(wstat)` with `BSTAT.CNT`; the application can make
     the same comparison and require the two to **agree**, whatever they
     are, which is the property section 7.2 says must be visible. What
     must be zero is any *increment* across the program's own run.
   - **Check 21** must read `WDOGSTAT` before it shortens the timeout and
     require `RSTCNT` unchanged afterwards, instead of requiring
     `WDOGRST` clear. "Stage 2 has not fired" is a statement about this
     test, and it should be written as one.
   - Until one of those is made, **the ladder demonstration must keep
     `-DQSPI_DEMO`**, and section 6.4 should say so rather than leaving
     the define unexplained.

   **WHAT THIS DOES NOT SETTLE.** Twenty-six of the twenty-eight are now
   confirmed twice — by the table above and by a run that put them on the
   third boot — but that run is one configuration: strap 0, chip select
   0, `DIV` 0, one RAM power-up seed, the primary image. Every other run
   in this document enters the application on the power-on boot
   (`cnt 0x00000000` in `s68-ship`, `s68-boot2`, `s68-magic0`,
   `s68-geom0`, `s68-csum1`, `s68-ded2` and `s68-ded3`) **[fact]**, so
   nothing here re-examines the checks against a boot from the secondary
   device, a slower `SCK`, or a second seed. Section 12's bullets on
   those three stand unchanged.
6. **A v0.2 of `docs/60`**, now owed by `docs/58`, `docs/67` and this.
