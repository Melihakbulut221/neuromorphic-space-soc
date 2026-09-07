# 47 — The SoC placed and routed

`docs/45-soc-top-synthesis.md` section 9 item 1 is the sentence this
document exists to delete:

> **Until something is placed, the honest summary of this document is
> "it synthesises, and the number that decides the part is not a
> synthesis number".**

Something is now placed. `soc_top` — Ibex, the fabric, the peripherals
and, for the first time, **72 KiB of memory that is memory** — has been
through LibreLane on `ihp-sg13g2`: floorplanned, power-gridded, placed,
clock-tree-synthesised, routed, extracted and timed at three corners on
extracted parasitics.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
intended, with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by blob hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was modified.
`hw/rtl/tmr_voter.v` is **read** and instantiated in place, as it already
was; `hw/openlane/sram_pilot/` and `hw/openlane/pilot_ihp/` are **read**
and their settings copied with their reasons restated, so that nothing
here depends on a frozen file staying where it is.
`hw/soc/flow/pnr_soc_top.sh` refuses to run if its configuration
directory is inside `hw/openlane/`. Section 13 lists every file.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Does it close at 50 MHz?** | **NO. It closes at 43.10 MHz**, and it is not a near miss: **−3.2029 ns of setup slack at `slow_1p08V_125C` on 2,003 endpoints**, on extracted parasitics, with the derate applied. It also fails **hold** at the fast corner (−0.2015 ns, 3 endpoints), **max cap** (10, 10 and 12 violations) and **max slew** (14 at slow). What it DOES do is route: **0 detailed-routing DRC errors, 0 disconnected pins, 0 power-grid violations, 1 antenna violating net.** Section 8.2 |
| So what did layout cost? | **7.07 ns and 18.9 MHz.** The same netlist bisects to **16.13 ns, 62.0 MHz** pre-layout and closes at **23.2029 ns, 43.10 MHz** placed and routed **[estimate, difference of two measurements]**. Sections 5.3 and 8.2 |
| What did the reset tree become? | **It stopped being a datapath, which is the half that was a design decision, and then place-and-route built the other half.** `docs/45` found `rst_sys_n` driving 2,766 flip-flop reset pins **and two data pins** — the two `can_issue` gates in `soc_bus.v` — which made the worst SYNCHRONOUS setup path (−60.6191 ns at the slow corner) worse than the worst asynchronous recovery path (−53.3681). Section 5 replaces that gate with a locally registered `issue_en`: **one flip-flop, one cycle of latency at boot, and strictly more conservative behaviour**. The synchronous group goes from **−60.6191 to +4.3006 on the identical memory model**, the reset net's data sinks go from two to **zero**, and the closing period goes from **18.20 ns to 15.71 ns, 54.9 → 63.7 MHz** **[fact, a controlled 2×2 matrix in section 5.3]**. Sections 5 and 8.3 |
| What are the memories? | **Six real RM_IHPSG13 SRAM macros: four `RM_IHPSG13_1P_2048x64_c2_bm_bist` for the 64 KiB RAM and two `RM_IHPSG13_1P_1024x32_c2_bm_bist` for the 8 KiB boot ROM**, in `hw/soc/rtl/soc_mem_sram.v`, a drop-in for `soc_mem.v` with the same module name and the same port list. **2,246,899.85 um2 of macro** **[fact, LEF `SIZE`]**, against 523,809.64 um2 of standard cells: **the memory is 4.29 times the logic**. Section 4 |
| Why those macros and not the dense one? | **Because `RM_IHPSG13_1P_8192x32_c4` has no write mask.** It is the densest 32-bit part in the library — 3,671.5 um2/kbit against the 2048x64's 3,840.9 — and it would have built 64 KiB in two instances instead of four. It is also the only 1P part in the family with **no `A_BM` port at all**, so it cannot serve `soc_mem`'s `be_i[3:0]` without a read-modify-write, which is a protocol change and not a wrapper. Ibex emits `sb` and `sh`. Section 4.2 |
| What does a real SRAM cost in timing? | **The read arc is the single largest delay in the design and it is a function of macro DEPTH.** `A_CLK → A_DOUT` at `slow_1p08V_125C` spans **5.2678 ns** (256 and 512 words) to **9.6611 ns** (8192 words) across the eighteen 1P parts, and density improves in the same direction, so **depth trades area against read delay and the trade is 4.4 ns wide** **[fact, eighteen Liberty files]**. The parts chosen here charge **9.2941 ns** and **7.5512 ns** — 46 % and 38 % of a 20 ns cycle spent inside the macro before the first gate of the read return path. Section 4.1 |
| Is that the thing `docs/45` said it could not bound? | **Yes, and it is now bounded.** `docs/45` section 8: "a real SRAM macro's setup and clock-to-Q are much larger than a standard-cell flip-flop's, so the paths into and out of the memories are optimistic here by an amount this document cannot bound." Measured: on the SAME netlist recipe, replacing the stand-in with real macros moves the closing period from **15.71 ns to 16.13 ns**, 0.42 ns **[fact, two bisections]** — which is **inside `docs/44`'s measured 0.4 ns of noise and is therefore not claimed as a cost**. The reason the 9.29 ns arc does not show up as 9.29 ns of damage is that it replaces a path that was already there, and section 8.4 says which. Sections 4.1 and 5.3 |
| And in the other direction? | **The macro INPUT side is faster than the stand-in, not slower.** `A_ADDR` `setup_rising` at the slow corner is **−0.1980 ns** — negative, so a path arriving at a macro address pin has more than a full cycle — where the stand-in ended at an ordinary flip-flop's positive setup. The macro's cost is entirely on the read side. Its `hold_rising` is **+1.3801 ns**, larger than any standard-cell flip-flop's in the library, and section 8.5 is what that does to hold. Section 4.1 |
| Did the instrument reproduce before it moved? | **Yes, five times, two of them byte-exact numbers from `docs/45`.** `SOC_MEM=blackbox` reproduces **27,696 cells / 3,077 flops / 392,932.8900 um2**; `SOC_MEM=stub` reproduces **27,705 / 3,240 / 400,199.5242**; the three-corner slack block of `docs/45` section 7.1 comes back **digit for digit** including `setup_sync −60.6191` and `setup_async −53.3681`; the bisection returns **18.20 ns and 54.9 MHz**; and the reset census returns **2,766 and 199**. Section 3 |
| Which checkers are bound to which corners? | **Section 7 is a table, and it is a table because the alternative is trusting a green result.** Four keys that this repository learned the hard way are set before the first run rather than audited after it: `TIME_DERATING_CONSTRAINT` as a **float**, and `SETUP_`, `HOLD_`, `MAX_CAP_` and `MAX_SLEW_VIOLATION_CORNERS` all `["*"]`. **Two things in this flow still gate nothing and are reported rather than fixed**: `Checker.WireLength` has no threshold in either PDK, and **there is no max-fanout checker step in the Classic flow at all**. Section 7 |
| What does this run NOT constitute? | **It is not a physical sign-off and it has no DRC, LVS or XOR result.** Those three decks are OFF, and not for time: `hw/openlane/sram_pilot` ran them over ONE RM_IHPSG13 macro and got **Magic DRC 1,106,478 errors — 1,106,478 inside the macro footprint and 0 outside — KLayout DRC 2,316, and Netgen LVS 359**, which `docs/12` sections 7.5 and 8 record as a **NO-GO on RM_IHPSG13 for this PDK version**. That is a property of the PDK and not of this design, and re-deriving six macros' worth of it would cost hours and tell a reader nothing. Section 9 says this in full and at length, because a run reported clean because a checker was pointed at nothing is the defect `docs/41` section 6.6 counts eight of. Section 9 |
| Does the layout change what the design IS? | **One RTL file, one gate, and it is priced.** `soc_bus.v`'s request gate. `soc_mem_sram.v` is new but replaces nothing — `soc_mem.v` is untouched and is still what every simulation, cocotb suite and formal job reads. **No behavioural evidence in this repository moved and none was re-run**, because the one change that could affect behaviour is strictly more conservative than what it replaces. Sections 5.2 and 9 |

---

## 2. What was built

| File | What it is |
|---|---|
| `hw/soc/rtl/soc_mem_sram.v` | **The memories.** A module called `soc_mem`, drop-in for `soc_mem.v`, on six RM_IHPSG13 macros. Read by the place-and-route flow and by `SOC_MEM=sram`; never by a simulation |
| `hw/soc/rtl/soc_bus.v` | **One gate.** The request path is gated by a locally registered `issue_en` instead of by `rst_ni` directly. Section 5 |
| `hw/soc/pnr/config.json` | The LibreLane configuration: floorplan, six macro placements, PDN hookup, and every checker bound to every corner with the reason for each key stated in the file |
| `hw/soc/pnr/pdn_macro.tcl` | The Metal4-to-TopMetal1 connect without which the six macros have no power and the flow does not notice for thirty-five steps |
| `hw/soc/pnr/RM_IHPSG13_1P_2048x64_c2_bm_bist_bb.v`, `..._1024x32_..._bb.v` | Macro blackbox declarations, transcribed from the PDK's own behavioural models by machine |
| `hw/soc/flow/pnr_soc_top.sh` | The runner: rootless toolchain assertions, the PDK pin read out of the installed wheel, and the source list merged into a resolved config under an assertion that it added nothing else |
| `hw/soc/flow/syn_soc_top.sh` | `SOC_MEM=sram`, a fourth memory boundary mode: the real macros, blackboxed for area and Liberty-backed for timing |
| `hw/soc/flow/sta_soc_top.sh`, `hw/soc/sta/ibex_sta.tcl.in` | `@MACROLIB@`: the macro Liberty, per corner, so the pre-layout STA can time the real memories |
| `hw/soc/tools.soc.mk` | `SRAM_TYP`, `SRAM_SLOW`, `SRAM_FAST` — and the corner-name mismatch stated where it is made |
| `sw/tests/test_soc_synthesis_guards.py` | Section 6 of that file: eight checks, every one of them mutation-tested. Section 10 |

---

## 3. Reproducing the instrument before moving it

`docs/44` section 5.2 set the rule and `docs/45` section 4 followed it:
before a number is claimed to have moved, the thing that measures it has
to be shown not to have.

| What | `docs/45` | Measured here |
|---|---|---|
| `SOC_MEM=blackbox` whole design | 6.1: 27,696 / 3,077 / **392,932.8900** | **27,696 / 3,077 / 392,932.8900** |
| `SOC_MEM=stub` whole design | 6.1: 27,705 / 3,240 / **400,199.5242** | **27,705 / 3,240 / 400,199.5242** |
| three-corner slack, as synthesised | 7.1: setup −33.7393 / −60.6191 / −16.0666, hold −0.0442 / 0.0579 / −0.1091, `setup_sync` **−60.6191**, `setup_async` **−53.3681** | **every figure, digit for digit** |
| closing period, reset cut | 7.6: **18.20 ns, 54.9 MHz** | **18.20 ns, 54.9 MHz** |
| reset census | 7.2: **2,766** and **199** pins | **2,766** and **199** |

**[fact for every row]**. The two syntheses take **28.54 s / 253.4 MB**
and **28.87 s / 237.8 MB** **[fact, `/usr/bin/time -v`]**, on a shared
20-thread host; wall times here are quoted as costs and not as precision.

Nothing in this document's own numbers rests on that reproduction being
approximate. The three-corner block and the bisection are the two things
section 5 claims to have moved, and both come back exactly.

**And the edit to the shared STA template was checked the same way, with
one thing worth recording.** `sta/ibex_sta.tcl.in` gained an
`@MACROLIB@` line so that one per-corner script serves a netlist with
macros and one without; `flow/sta_ibex.sh` substitutes a comment for it.
Re-run on `docs/44`'s three netlists, **two of the three `slack.rpt`
files come back byte-identical to the copies on disk** (`h44-base`,
`h44-doc43`) **[fact, `diff`]**. The third does not — and the disagreement
is with the FILE, not with the document. `hw/soc/out/h44-port`'s on-disk
`slack.rpt` reports −1.0533 at the slow corner, which is not a number
`docs/44` or `docs/45` publishes; the re-run reports **+1.5514**, which
is exactly `docs/44` section 5.5's figure for the shipped core, and
`SOC_TIEOFFS=1` on the same directory reports **2.9677**, which is
exactly `docs/45` section 4.2's. **Both published numbers reproduce; one
stale file in a gitignored output directory did not match either of
them**, and it has been overwritten by the re-run. `hw/soc/out/` is
build output and is not tracked.

---

## 4. The memories

`docs/45` section 9 item 2:

> **The two SRAM macros.** Section 3 is the first time the memory
> boundary has had to be modelled rather than excluded, and it made
> plain that the SoC has 72 KiB of memory represented by nothing.

There are in fact six, and the reason there are six rather than two is
the first finding of this section.

### 4.1 The library, measured

Eighteen single-port RM_IHPSG13 parts, each with a LEF, a GDS, a CDL, a
behavioural model and three Liberty corners. `W × H` is the LEF `SIZE`
statement; the read arc is the maximum `cell_rise` of the
`A_CLK → A_DOUT` table at `slow_1p08V_125C`; `BM` is whether the part
has the per-bit write mask `A_BM`.

| Macro | Words × bits | Area, um2 | um2/kbit | Read arc, slow | BM |
|---|---|---:|---:|---:|:--:|
| `RM_IHPSG13_1P_512x8_c3_bm_bist` | 512 × 8 | 26,138 | 6,534.5 | **5.2678** | y |
| `RM_IHPSG13_1P_256x8_c3_bm_bist` | 256 × 8 | 17,547 | 8,773.4 | 5.2709 | y |
| `RM_IHPSG13_1P_256x16_c2_bm_bist` | 256 × 16 | 28,127 | 7,031.8 | 5.3030 | y |
| `RM_IHPSG13_1P_256x32_c2_bm_bist` | 256 × 32 | 49,488 | 6,186.1 | 5.4353 | y |
| `RM_IHPSG13_1P_256x64_c2_bm_bist` | 256 × 64 | 93,181 | 5,823.8 | 5.4600 | y |
| `RM_IHPSG13_1P_64x64_c2_bm_bist` | 64 × 64 | 50,489 | 12,622.3 | 5.4644 | y |
| `RM_IHPSG13_1P_256x48_c2_bm_bist` | 256 × 48 | 70,850 | 5,904.2 | 5.5676 | y |
| `RM_IHPSG13_1P_512x16_c2_bm_bist` | 512 × 16 | 45,309 | 5,663.7 | 6.5555 | y |
| `RM_IHPSG13_1P_512x32_c2_bm_bist` | 512 × 32 | 79,720 | 4,982.5 | 6.6876 | y |
| `RM_IHPSG13_1P_512x64_c2_bm_bist` | 512 × 64 | 150,102 | 4,690.7 | 6.7252 | y |
| `RM_IHPSG13_1P_1024x8_c2_bm_bist` | 1024 × 8 | 49,419 | 6,177.4 | 7.3524 | y |
| `RM_IHPSG13_1P_1024x16_c2_bm_bist` | 1024 × 16 | 79,674 | 4,979.6 | 7.4186 | y |
| **`RM_IHPSG13_1P_1024x32_c2_bm_bist`** | **1024 × 32** | **140,183** | **4,380.7** | **7.5512** | **y** |
| `RM_IHPSG13_1P_1024x64_c2_bm_bist` | 1024 × 64 | 263,946 | 4,124.2 | 7.5803 | y |
| `RM_IHPSG13_1P_4096x8_c3_bm_bist` | 4096 × 8 | 146,413 | 4,575.4 | 9.1065 | y |
| `RM_IHPSG13_1P_4096x16_c3_bm_bist` | 4096 × 16 | 257,609 | 4,025.1 | 9.1931 | y |
| **`RM_IHPSG13_1P_2048x64_c2_bm_bist`** | **2048 × 64** | **491,634** | **3,840.9** | **9.2941** | **y** |
| `RM_IHPSG13_1P_8192x32_c4` | 8192 × 32 | 939,915 | **3,671.5** | 9.6611 | **NO** |

**[fact, eighteen LEF `SIZE` statements and eighteen Liberty files]**

> **The read arc is a function of DEPTH and of nothing else visible
> here.** Every 256- and 512-word part reads in 5.27 to 6.73 ns; every
> 1024-word part in 7.35 to 7.58; every part 2048 words or deeper in
> 9.11 to 9.66. Width moves it by tens of picoseconds within a depth and
> depth moves it by nanoseconds across them **[estimate, reading the
> table]**.
>
> **And density improves in the same direction**, monotonically from
> 6,534.5 um2/kbit at 512×8 to 3,671.5 at 8192×32. So **choosing a
> deeper macro buys area and spends cycle time**, and across this family
> the whole trade is **4.3933 ns and 2,862.6 um2/kbit** **[estimate,
> the two extremes of a measured table]**.

`docs/12` section 6.4g measured the 512×32's read arc at 6.688 ns and
called it "usable; the read is slow". This table is that observation
generalised over the family, and the generalisation is the useful part:
**there is no dense, shallow part.**

### 4.2 The decision, and the part that is excluded rather than chosen

**64 KiB of RAM is 16,384 words of 32 bits.** Every build the library
admits, with the constraint that a `soc_mem` slave must support byte
writes:

| Build | Instances | Total area, um2 | Read arc, slow |
|---|---:|---:|---:|
| `RM_IHPSG13_1P_2048x64_c2_bm_bist` | **4** | **1,966,534** | **9.2941** |
| `RM_IHPSG13_1P_1024x64_c2_bm_bist` | 8 | 2,111,569 | 7.5803 |
| `RM_IHPSG13_1P_1024x32_c2_bm_bist` | 16 | 2,242,923 | 7.5512 |
| `RM_IHPSG13_1P_4096x16_c3_bm_bist` | 8 | 2,060,868 | 9.1931 |
| `RM_IHPSG13_1P_512x64_c2_bm_bist` | 16 | 2,401,638 | 6.7252 |
| `RM_IHPSG13_1P_512x32_c2_bm_bist` | 32 | 2,551,037 | 6.6876 |
| `RM_IHPSG13_1P_1024x16_c2_bm_bist` | 32 | 2,549,559 | 7.4186 |
| `RM_IHPSG13_1P_256x64_c2_bm_bist` | 32 | 2,981,777 | 5.4600 |
| ~~`RM_IHPSG13_1P_8192x32_c4`~~ | ~~2~~ | ~~1,879,830~~ | ~~9.6611~~ |

**[fact for every area and arc; the instance counts are arithmetic]**

> **`RM_IHPSG13_1P_8192x32_c4` is struck out and it is the interesting
> row.** It is the densest part in the library, it is the only one that
> builds 64 KiB in **two** instances, and it would have saved 86,704 um2
> and two macro placements against the row above it. **It has no `A_BM`
> port.** Neither does `RM_IHPSG13_2P_64x32_c2`; those two are the only
> parts in all 27 without the bit mask, and the 8192×32 is the one
> anybody would reach for **[fact, its Liberty pin list and its
> behavioural model]**.
>
> `soc_mem`'s contract carries `be_i[3:0]`, Ibex emits `sb` and `sh`,
> and a memory that can only write 32 bits at a time serves them by
> read-modify-write — a second cycle, a hazard against the pipelined
> request the fabric permits, and a change to a protocol
> `hw/soc/tb/cocotb/test_soc_bus.py` proves rules about. **That is a
> design change and not a wrapper, and it is not made here.**

**The choice is 4 × `RM_IHPSG13_1P_2048x64_c2_bm_bist`.** It is the
smallest byte-writable 64 KiB build in the library and the one with the
fewest instances, which is most of the floorplan. It is also the slowest
of the practical ones, and the table above is printed so that the
alternative is visible rather than argued: **eight `1024x64` would buy
back 1.7138 ns of read arc for 145,035 um2 and four more macro
placements** **[estimate, differences of measurements]**. Section 8.4
says whether that 1.71 ns would have been worth anything, and the
answer is what decides whether this row should ever be revisited.

**The ROM is 2,048 words of 32 bits and there is no 2048×32 part**, so
it is **2 × `RM_IHPSG13_1P_1024x32_c2_bm_bist`**, 280,365 um2, an exact
fit with no wasted row.

**Total macro area: 2,246,899.85 um2** **[fact, LEF `SIZE`, arithmetic
over six instances]**, against **523,809.64 um2 of standard cells**
(section 6.2). **The memory is 4.29 times the logic** **[estimate]**.

### 4.3 The mapping

`hw/soc/rtl/soc_mem_sram.v`. A 64-bit macro holds two 32-bit words per
row, so the word index splits three ways:

```
  RAM, WORDS = 16384        ROM, WORDS = 2048
    widx[13:12]  bank         widx[10]   bank
    widx[11:1]   macro row    widx[9:0]  macro row
    widx[0]      half
```

The half selects both the write mask — `A_BM` is `{bm32, 32'h0}` or
`{32'h0, bm32}`, and `A_BM[i] = 1` writes bit `i`, which is the PDK
core model's own declaration — and the half of `A_DOUT` that is
returned. **Bank and half are REGISTERED**, captured on the request that
produced the data and held while `req_i` is low, so the read multiplexer
is driven from state rather than from this cycle's address and `rdata_o`
holds exactly as `soc_mem.v`'s does.

`rdata_o` is **combinational** from the macro output rather than
registered, and that is what keeps the protocol identical: the macro
registers `A_DOUT` internally, so the response still arrives exactly one
cycle after the request, as `soc_bus.v` rules S1–S4 require and as
`soc_mem.v` provides. **Nothing about the bus protocol changed and no
cocotb test would see a difference if this file could be simulated.**

`A_DLY` is tied high on all six. Sixteen of the 27 datasheets call that
mandatory and eleven call it recommended; the two parts used here are in
the second group and it is tied anyway, because the difference between
the two groups is not a difference anybody should have to remember
(`docs/12` section 6.4e). Every `A_BIST_*` port is parked with
`A_BIST_EN` low.

### 4.4 What the memories still do not have, which is more than they do

- **No ECC and no scrubbing.** `soc_mem.v`'s header says this of the
  behavioural model and making the storage real does not fix it. A macro
  word is 32 bits of data and nothing else. The consequence is already
  on the record in `soc_top.v`'s own header: **SecureIbex is fixed at 0
  because MemECC would require seven SECDED check bits per word that no
  memory in this design stores**, and `docs/38` section 7.4 is the
  bring-up record of what happens when it is not. Adding them means
  39-bit rows, which means a different macro geometry and a different
  area. For a part that claims fault tolerance this is the largest open
  item in the subsystem and it is now blocking a specific thing rather
  than a general one.
  *Corrected 2026-09-05:* built in `docs/67-memory-protection.md`,
  and not with 39-bit rows: the 64-bit row keeps its geometry and
  holds one word as four byte codewords, at the price of half the RAM.
- **The ROM has no contents, and that is an architecture question this
  layout has made unavoidable.** `INIT_FILE` and `INIT_WORD` are
  accepted so `soc_top.v`'s instantiation is unchanged, and they are
  **ignored**: an SRAM macro powers up undefined. A ROM built out of
  SRAM is not a ROM until something writes it, and **this design
  contains nothing that can**. It needs a mask ROM, a serial load path,
  or a boot from an external interface, and none of the three is a
  layout decision. Section 11 item 2.
- **No BIST.** The macros carry a full second port set for it and this
  design ties `A_BIST_EN` low.
- **Read-during-write differs from the behavioural model.** `soc_mem.v`
  returns the old word on a write cycle; here `A_REN` is low during a
  write and `A_DOUT` holds. No master in this SoC consumes `rdata` on a
  write response, so it is not observable through the protocol — but it
  is a difference, and it is why `soc_mem_sram.v` must never be
  substituted into a simulation.

---

## 5. The reset tree

`docs/45` section 7.2 stated the problem and named the half of it that
was not place-and-route's:

> **A correctness gate in the fabric put the SoC's largest unbuffered
> net into the combinational request path.** Neither decision is wrong
> and the composition of the two is the finding.

That is exactly right, and it is why this section changes RTL. There
were two problems on one net and only one of them is a flow problem.

### 5.1 What was measured, and which half is which

`rst_sys_n` in `docs/45`'s netlist reached **2,766 flip-flop reset pins
and two other pins** **[fact, reproduced in section 3]**. The two others
are these, in `soc_bus.v`:

```verilog
wire can_issue_i = rst_ni && mi_req_i && ...
wire can_issue_d = rst_ni && md_req_i && ...
```

- **The 2,766 reset pins are a fanout problem and place-and-route builds
  the tree.** `docs/38` section 10 item 3 has carried that obligation
  since the core was brought up.
- **The two data pins are a DESIGN problem and no amount of buffering
  makes them not a datapath.** A reset net that also carries data is on
  the critical path of every transaction the fabric issues, and it is on
  it in the SYNCHRONOUS group, where the recovery check does not
  protect it.

`docs/45` measured the consequence and it is unambiguous: at the slow
corner `setup_sync` was **−60.6191** and `setup_async` was **−53.3681**
— **the synchronous group was the worse of the two.**

### 5.2 The change, and what it costs

`soc_bus.v` now registers the release:

```verilog
reg issue_en;
always @(posedge clk_i or negedge rst_ni)
  if (!rst_ni) issue_en <= 1'b0;
  else         issue_en <= 1'b1;

wire can_issue_i = issue_en && mi_req_i && ...
wire can_issue_d = issue_en && md_req_i && ...
```

**One flip-flop, cleared asynchronously by `rst_ni` exactly as every
other register in the file is, with a fanout of two.**

The argument `soc_bus.v`'s header makes for the gate is untouched: a
master driving `req` during reset must not have a transaction accepted
while the response accounting is held at zero. `issue_en` enforces the
same thing.

> **The behaviour is STRICTLY MORE CONSERVATIVE than what it replaces.**
> `rst_ni` opens the fabric on the same edge that releases the counters
> and queues; `issue_en` opens it one cycle later, during which those
> counters and queues are already released. There is no window in which
> `issue_en` permits something `rst_ni` forbade.
>
> **The cost is one flip-flop and one cycle of latency on the first
> transaction after a reset — once, at boot** **[estimate, reading the
> change]**. It is not a per-transaction cost and it is not a
> throughput cost.

**This is why no behavioural evidence was re-run and none needed to
be.** Every cocotb test, every formal property in `hw/soc/formal/` and
every fault-injection campaign in `docs/42`, `docs/43` and `docs/46`
passes identically either way — which is also the reason
`sw/tests/test_soc_synthesis_guards.py` now carries a guard that fails
if the gate is reverted. Nothing else in this repository would notice.

### 5.3 The controlled matrix

Four whole-design builds, two variables, same session, same source list
otherwise. `BUS=old` is `git show HEAD:hw/soc/rtl/soc_bus.v` restored in
place; `mem` is `SOC_MEM`. Slack in ns at `slow_1p08V_125C`, 20 ns
period, no reset false-path applied to any row.

| Build | `setup_sync` | `setup_async` | worst setup | worst hold (fast) | closes at |
|---|---:|---:|---:|---:|---:|
| **old bus, stub memory** — `docs/45`'s design | **−60.6191** | −53.3681 | −60.6191 | −0.1091 | **18.20 ns, 54.9 MHz** |
| new bus, stub memory | **+4.3006** | −53.3625 | −53.3625 | −0.1091 | **15.71 ns, 63.7 MHz** |
| old bus, SRAM macros | −47.7408 | −49.2829 | −49.2829 | −0.2812 | 16.56 ns, 60.4 MHz |
| **new bus, SRAM macros** — what is laid out | **+3.8711** | −49.2780 | −49.2780 | −0.2475 | **16.13 ns, 62.0 MHz** |

**[fact, four syntheses, twelve corner runs and five twelve-step
bisections. Row 1 reproduces `docs/45` section 7.1 and 7.6 exactly;
section 3.]**

Four readings, in order of how much the evidence supports them.

> **1. The change does exactly one thing and does it completely.**
> `setup_sync` moves **−60.6191 → +4.3006** on the identical memory
> model, a swing of **64.9197 ns**, while `setup_async` moves
> **−53.3681 → −53.3625**, **0.0056 ns** — two orders of magnitude
> inside `docs/44`'s 0.4 ns of noise **[fact, differences of
> measurements]**. The reset is out of the synchronous group and
> nothing else moved.

> **2. The reset gate was on the critical path, not merely poisoning
> the group.** The closing period moves **18.20 → 15.71 ns** on the
> same memory model: **2.49 ns and 8.8 MHz** **[estimate, two
> bisections, 6× the noise]**. `docs/45` section 7.4's flattened
> critical path passed through "the `soc_bus` gate whose other input is
> `rst_sys_n`" at 12.41 ns of a 17.77 ns path; that gate is now driven
> by a local flip-flop.

> **3. The synchronous group MEETS 20 ns pre-layout with no false-path
> applied**, at +4.3006 and +3.8711 **[fact]**. `docs/45` needed
> `sta/soc_top_reset_cut.sdc` to report a synchronous number at all and
> was careful to label it an assumption. **That assumption is no longer
> load-bearing for the synchronous group**: bisecting `setup_sync` with
> the cut OFF and bisecting `setup_all` with the cut ON give the **same
> 16.13 ns** **[fact, two independent bisections]**. The cut still
> matters for the asynchronous group, which is section 8.3.

> **4. Real macros cost 0.42 ns of closing period against the stand-in
> and it is NOT CLAIMED.** 15.71 → 16.13 ns is inside `docs/44`'s
> measured 0.4 ns resolution and this document does not claim a delta
> it cannot resolve. What can be said is the negative, and it is the
> more surprising half: **a 9.2941 ns macro read arc did not cost
> 9.2941 ns**, and section 8.4 says why.

### 5.4 What the netlist looks like afterwards

```
grep -c "\.RESET_B(rst_sys_n)"  soc_top.sta.v     2611
grep -c "\.RESET_B(rst_ni)"     soc_top.sta.v      199
grep -o  "\.[A-Z_]*(rst_sys_n)" soc_top.sta.v | sort | uniq -c
     1 .Q(rst_sys_n)
  2611 .RESET_B(rst_sys_n)
```

**[fact, `hw/soc/out/s47-sram/soc_top.sta.v`]**

> **`rst_sys_n` has zero data sinks.** Every pin it reaches is a
> flip-flop reset pin or the Q that drives it. 2,766 fell to 2,611
> because the SRAM build has 155 fewer flip-flops at the memory boundary
> than the stand-in did — 3,240 against 3,085, exactly 155 **[fact, two
> area reports]** — and not because anything about the reset changed.

**Section 8.3 is what place-and-route then does with those 2,611
sinks**, which is the half of the problem this section deliberately did
not try to solve in RTL.

---

## 6. Area

### 6.1 The floorplan

| | |
|---|---:|
| Die | **2306.40 × 2075.22 um = 4,786,290 um2 = 4.7863 mm2** |
| Core | **4,338,910 um2** |
| Six SRAM macros | **2,246,899.85 um2, 46.9 % of the die** |
| Standard cells, as synthesised | **396,177.6420 um2**, 27,565 cells |
| Utilization, macros included | **62.03 %** |
| Utilization, standard cells alone | **21.24 %** |

**[fact, `OpenROAD.Floorplan` metrics and LEF `SIZE` arithmetic]**

**Two macro rows facing a central standard-cell channel**, and the
arrangement is forced by the macros' pin geometry rather than chosen for
elegance. Every RM_IHPSG13 part puts **all** of its signal pins on one
edge, at local `y = 0`, on Metal2 and Metal3 — **352 of them on the
2048×64 and 190 on the 1024×32** **[fact, LEF pin rectangles]**;
`docs/12` section 6.4c found 188 on the 512×32 the same way. A macro
whose pin edge faces another macro is a macro the router reaches the
long way round.

So the lower row is placed **FS**, which mirrors about X and puts its
pin edge at its **top**, and the upper row is placed **N**, which leaves
its pin edge at its **bottom**. Both rows' pins face the **700.08 um**
channel between them, and every standard cell in the design sits in that
channel or in the two pockets the shorter ROM macros leave above and
below it — **2,092,010 um2 of placeable area** for 396,178 um2 of cells,
**18.9 %** before repair and clock-tree buffers **[estimate, arithmetic
on the two measurements]**. **That is sparse, and section 8.4 is where
it is charged for.** The channel was sized against LibreLane's own
synthesis of the same RTL, which is 32 % larger (section 6.3); the
netlist actually hardened is the smaller one, so the die is bigger than
this design needs and **nothing has explored what a tighter one would
do**.

The core box is site-aligned by construction: **2186.40 um is exactly
4,555 sg13g2 sites of 0.48 um and 1984.50 um is exactly 525 rows of
3.78 um**, and every macro origin is an integer number of sites from the
core's left edge and an integer number of rows from its bottom.

### 6.2 The flow does not synthesise, and that is the second finding

**LibreLane hardens the netlist `hw/soc/flow/syn_soc_top.sh` produced.**
`flow/pnr_soc_top.sh` hands it in as an initial state and starts the
flow at `Yosys.JsonHeader` with `Yosys.Synthesis` skipped. That is not a
convenience; **both of LibreLane's own hierarchy modes are wrong for
this design, in opposite directions, and neither is fixable from a
configuration file.** The first attempt used `deferred_flatten` because
`hw/openlane/pilot_ihp` does, and it cost 13.8 ns before anything was
placed.

| | `deferred_flatten` | `flatten` | `syn_soc_top.sh` |
|---|---|---|---|
| what it does | synthesise hierarchically, then **re-synthesise the mapped netlist flat** | flatten **during** synthesis | flatten during synthesis; hold `keep_hierarchy` through `abc`; **release it before the final flatten** |
| `cheriot`/`trvk` lines in the netlist | **55** | **0** | **0** |
| `soc_tmr_bank` instances left unflattened | 0 | **3** | 0 |
| result | **runs, and is 13.84 ns slower** | **stops at `Checker.YosysUnmappedCells`** | **used** |

**[fact, `grep -ciE 'cheriot|trvk'` on three netlists and one Yosys
`stat`]**

**Why `deferred_flatten` is slow.** `soc_top.v` drives `ibex_top`'s
`cheriot_enable_i` with a **constant**, and `docs/44` section 5.1 is the
whole subject of what that constant does to a timing report when it is
not folded. `deferred_flatten` optimises with the module boundary
intact, so the constant stops there and **the CHERIoT logic survives**;
its second pass re-reads an already-mapped netlist, where nothing can
fold any more. `docs/45` section 7 measured that `ibex_top` synthesised
standalone carries 32 lines naming `cheriot` or `trvk` and the
whole-design netlist carries zero. **This flow reintroduced them.**

**Why `flatten` stops.** Yosys's `flatten` respects `keep_hierarchy`,
and `hw/soc/rtl/soc_tmr_bank.v` carries it as one of its two anti-merge
defences — `docs/41`'s finding that three identical flip-flop banks
written from the same expression are one bank after `opt_dff` and
`opt_merge`, and the voter above them then votes three copies of the
same corrupted value. **LibreLane has no way to RELEASE the attribute
after technology mapping**, so the three banks stand as submodules,
`Checker.YosysUnmappedCells` counts them, and the run stops. That
checker is right to stop it: OpenROAD needs a flat netlist of library
cells.

> **`syn_soc_top.sh` does both, and it does them because `docs/41`
> required one and `docs/44` diagnosed the other.** It holds
> `keep_hierarchy` through optimisation and `abc` and removes it before
> the final flatten. **Handing its netlist to LibreLane keeps the
> watchdog's protection, folds the constant, and makes every number in
> this document directly comparable with `docs/38` through `docs/45` —
> which no re-synthesis inside LibreLane could.**

### 6.3 What the difference is worth, measured by one tool

`OpenROAD.STAPrePNR`, same step, same `base.sdc`, same corner, same
three-corner set, on two netlists of the same RTL, **before any
placement exists**:

| Netlist | Cells | Area, um2 | worst `clk_i`-group path, slow |
|---|---:|---:|---:|
| LibreLane `deferred_flatten` | **37,895** | **523,809.6444** | **−9.9731** |
| `syn_soc_top.sh`, as hardened | **27,565** | **396,177.6420** | **+3.8711** |

**[fact]**

> **13.8442 ns and 127,632 um2, and not one picosecond of it is
> layout.** A configuration key copied from the pilot, where it is
> harmless because `pilot_top.v` has no tied-off configuration input of
> this kind, is load-bearing here. **This is `docs/44` section 5.1's
> finding recurring in a new flow**, and the only reason it was caught
> in an hour rather than in a document is that `docs/45` had already
> established what the whole-design netlist is supposed to look like —
> zero lines naming `cheriot`.

**And the cross-check is the best one in this document.** `+3.8711` is
what `hw/soc/flow/sta_soc_top.sh` reports for `setup_sync` at the slow
corner (section 5.3), and it is what OpenROAD reports here. **Two
independent tool invocations, two independent constraint files —
`hw/soc/sta/ibex.sdc.in` and LibreLane's `base.sdc` — agree to four
decimal places on all six of the three-corner setup and hold numbers**:
−26.3108 / −49.2780 / −11.1090 and −0.1875 / −0.1144 / −0.2475 **[fact,
`sta_soc_top.sh`'s `slack.rpt` against
`04-openroad-staprepnr/summary.rpt`]**. Nothing in this repository had
previously checked one STA recipe against another.

**A note on what `2,611` means in that table.** `OpenROAD.STAPrePNR`
reports **2,611 violating setup endpoints at every one of the three
corners** — exactly the number of flip-flop reset pins section 5.4
counts. The −49.2780 is the asynchronous recovery check on an unbuffered
reset net and nothing else, which is what section 8.3 hands to
place-and-route.

### 6.4 The generate restructuring changed names and nothing else

`soc_mem_sram.v`'s three branches are independent `if`s rather than an
`if`/`else if` chain, because an `else if` nests the second branch in an
anonymous generate block and Yosys names the ROM's macros
`u_rom.genblk1.g_rom_1024x32.u_b0` — a name whose middle component the
tool invents and `hw/soc/pnr/config.json` has to match exactly or the
run dies at `OpenROAD.CheckMacroInstances`. It did, once.

**Restructuring it moved no number.** Re-synthesised: **27,565 cells,
3,085 flip-flops, 396,177.6420 um2**, and the three-corner block
−26.3108 / −49.2780 / −11.1090 with `setup_sync` +3.8711 — **identical
before and after** **[fact, two syntheses and two STA runs]**.

---

## 7. The checkers, and which corners they are bound to

`docs/41` section 6.6 lists **eight** occasions on which a green result
in this repository was read as wider than the thing it examined.
**Four of the eight are defects in THIS flow — `docs/28` 4.4 and 4.4a,
`docs/34` 8.5 and `docs/36` — they were all found late and expensively
on the pilot, and none of them is visible in any report the flow
produces.**
They are configured out here before the first run rather than audited
after it.

### 7.1 The four, and the two mechanisms

| Key | Shipped behaviour | Set to | Mechanism |
|---|---|---|---|
| `TIME_DERATING_CONSTRAINT` | PDK ships the **integer 5**; `base.sdc` computes `expr 5 / 100` in Tcl = **0**, so **no derate is applied** while the log says `Setting timing derate to: 5%` and the written SDC has **no `set_timing_derate` line at all** | **`5.0`** | Tcl integer division. `docs/28` 4.4; cost measured on the pilot at **0.9910 ns** |
| `SETUP_VIOLATION_CORNERS` | **unset**, so it falls through to the PDK's `TIMING_VIOLATION_CORNERS` = `["*typ*"]` and the checker examines the typical corner and **nothing else** | **`["*"]`** | a PDK default reaching through an unset key. `docs/28` 4.4a; **four published "the corner closes" claims on the pilot came from runs in this state** |
| `MAX_CAP_VIOLATION_CORNERS` | step class declares `corner_override = [""]`, which becomes the Variable's **default**; `[""]` is truthy so `TIMING_VIOLATION_CORNERS` is **never consulted**, the list filters to **empty**, no corner matches, and the step **warns instead of failing** | **`["*"]`** | a step-class override, **not** the setup mechanism — raising `TIMING_VIOLATION_CORNERS` is inert. `docs/34` 8.5, closed by `docs/36` |
| `MAX_SLEW_VIOLATION_CORNERS` | as above | **`["*"]`** | as above |

`HOLD_VIOLATION_CORNERS` is already `["*"]` by LibreLane default and is
**set explicitly anyway**. A default is not a decision, and the whole
class of defect this table guards against is a default nobody wrote
down.

**The derate has an audit trap and it is worth one line.** `docs/31`
sections 3.2 and 10.3: **`resolved.json` records `5` in both the derated
and the underated case** — the float is flattened on serialization — so
it must never be used to audit this key. The three artifacts that decide
are the step `_env.tcl`, the flow log line, and the flow-written SDC.
This run's log line reads:

```
[INFO] Setting timing derate to: 5.0%
```

**[fact, `12-openroad-staprepnr/openroad-staprepnr.log`]** — `5.0%`, not
`5%`, which is the observable difference between a derate applied and a
derate logged.

### 7.2 And the two that still gate nothing

Reported rather than fixed, because inventing a threshold records the
tool rather than the design — the `docs/20` section 11 rule.

- **`Checker.WireLength`.** `WIRE_LENGTH_THRESHOLD` is optional and
  **neither PDK ships a value**, so `MetricChecker.run()` warns and
  skips. Present in 34 of the 34 runs in this repository that reach the
  step. No vendor limit exists for sg13g2.
- **Max fanout: there is no checker step in the Classic flow at all.**
  `design__max_fanout_violation__count` is computed at every STA and
  **judged by nothing**; the pilot carried 84 of them behind a green
  `design__violations`. It matters more here than it did there, because
  `MAX_FANOUT_CONSTRAINT` is the PDK's **10** while the sg13g2 library
  declares `default_max_fanout : 8`, and the net this run exists to
  build has 2,611 sinks. **The number is read out and reported in
  section 8.6 rather than left in a metrics file.**

A third, for completeness: **lint warnings do not gate**
(`ERROR_ON_LINTER_WARNINGS` defaults False), and Verilator produces
**468** of them on this source list **[fact, the `probe` run; the
reported run does not lint, because it does not synthesise]**. That is
`docs/36` section 3.3's disposition — policy, not oversight, because the
disabling key is named.

### 7.3 And the audit says the gates are live

`hw/openlane/checker_audit.py`, which recomputes from the installed
LibreLane's own step classes whether each checker CAN fail, run against
this run directory:

```
    registered Checker.* steps: 21
    of which the Classic flow runs: 19

GATES  Checker.SetupViolations   [corners] SETUP_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, violating nom_slow_1p08V_125C
GATES  Checker.HoldViolations    [corners] HOLD_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, violating nom_fast_1p32V_m40C
GATES  Checker.MaxSlewViolations [corners] MAX_SLEW_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, violating nom_fast_1p32V_m40C,
                                 nom_slow_1p08V_125C
GATES  Checker.MaxCapViolations  [corners] MAX_CAP_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, violating all three

    17 of 19 in-flow checkers gate fully.
    NOT gating in full: Checker.LintWarnings, Checker.WireLength
```

**[fact, `checker_audit.py hw/soc/pnr/runs/full3`]**

**Seventeen of nineteen**, against the fifteen `docs/36` section 4 found
on the pilot before it closed the last two. The two that do not are the
two section 7.2 names, and both are named rather than repaired.

**And the flow exits non-zero, naming every failing corner:**

```
One or more deferred errors were encountered:
Setup violations found in the following corners:
* nom_slow_1p08V_125C
Hold violations found in the following corners:
* nom_fast_1p32V_m40C
Max Slew violations found in the following corners:
* nom_fast_1p32V_m40C
* nom_slow_1p08V_125C
Max Cap violations found in the following corners:
* nom_fast_1p32V_m40C
* nom_slow_1p08V_125C
* nom_typ_1p20V_25C
```

**[fact, the flow log]**

> **In the shipped configuration, setup would have been examined at
> `nom_typ_1p20V_25C` and nowhere else — where this design passes with
> +5.7231 ns — and max cap and max slew would have warned and returned.
> This run would have failed on hold alone.** That is the difference
> between the table in section 7.1 and no table at all, on the first
> layout this project has ever produced.

---

## 8. The run

LibreLane v3.0.5, OpenROAD 26Q1-2938-g0e2d771c5e, `ihp-sg13g2` at
`c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c`, rootless, on a shared
20-thread host. The netlist is `hw/soc/flow/syn_soc_top.sh`'s, for the
reasons in section 6.2.

**It is two run directories and the reason is section 8.5.** `full2`
carries the flow from the netlist through floorplan, PDN, placement,
clock-tree synthesis and post-CTS timing repair. `full3` resumes from
`full2`'s post-CTS state with `RUN_POST_GRT_DESIGN_REPAIR` and
`RUN_POST_GRT_RESIZER_TIMING` turned on — **two stages that default to
`False` and whose absence nothing reports** — and carries it through
global routing, antenna repair, detailed routing, parasitic extraction
and sign-off STA. Everything before global routing is therefore one
placement and one clock tree, measured once.

### 8.1 What layout did, in one table

Worst slack in ns at `slow_1p08V_125C`, 20 ns period, 5 % derate applied
as a float, by path group, at each point the flow reports one. The
`asynchronous` group is the reset recovery and removal check; `clk_i` is
everything else.

| Stage | `clk_i` | `asynchronous` | hold |
|---|---:|---:|---:|
| pre-layout, `sta_soc_top.sh` (OpenSTA) | **+3.8711** | −49.2780 | −0.2475 (fast) |
| pre-layout, `OpenROAD.STAPrePNR` | **+3.8711** | **−49.2780** | −0.2475 (fast) |
| post-CTS, before the timing resizer | **−10.7556** | **+14.7319** | +0.0182 (slow) |
| post-route, extracted parasitics | **−3.2029** | **no violation at any corner** | **−0.2015** (fast) |

**[fact]**. The corner is named on each hold figure because **the two
mid-flow rows have only two corners to name**: `PNR_CORNERS` is
`["nom_typ_1p20V_25C", "nom_slow_1p08V_125C"]`, so the fast corner is
not analysed until sign-off. That narrows what is OPTIMISED and never
what is CHECKED — all four checkers of section 7 see all three — and it
is the same subset `hw/openlane/pilot_ihp` uses.

Two things happen at layout and they go in opposite directions.

> **1. PLACE-AND-ROUTE BUILT THE RESET TREE AND IT CLOSES WITH MARGIN.**
> The asynchronous group goes from **−49.2780 pre-layout to +14.7319
> post-clock-tree**, a swing of **64.0099 ns** **[fact]**. That is the
> answer to the question `docs/38` section 10 item 3 opened and
> `docs/44` and `docs/45` both deferred: **an unbuffered 2,611-fanout
> reset net is a synthesis artefact and the resizer removes it.**
> `docs/45` section 7.2's estimate — "scaling `docs/44`'s measured
> 10.9223 ns into 2,766 pins gives about 13.0 ns, still two thirds of a
> 20 ns period, a tree and not a bigger driver is the answer" — was
> right that a tree is the answer and **wrong about the order of the
> difficulty**: the tree is built by `repair_design` without being
> asked, and it leaves 14.73 ns of margin. **The number of violating
> setup endpoints pre-layout is 2,611 at every corner, exactly the reset
> fanout; post-CTS the asynchronous group has none.**
>
> **The half of the problem that needed an RTL change needed it, and the
> half that did not, did not.** Section 5 was necessary because a data
> path through a reset net is not something a resizer can fix; this is
> the evidence that the rest of it was correctly left to the flow.

> **2. AND IT COST THE SYNCHRONOUS GROUP 14.63 ns.** `clk_i` goes from
> **+3.8711 to −10.7556** across placement and clock-tree synthesis
> **[fact]**, with **2,506 violating endpoints** — which is not one path
> but a systemic one. Section 8.4 is what it is.

### 8.2 It does not close at 50 MHz. It closes at 43.10 MHz

`OpenROAD.STAPostPNR`, three corners, **extracted parasitics** from
`OpenROAD.RCX`, 5 % derate applied as a float, 0.25 ns of clock
uncertainty. Slack in ns.

| Corner | setup ws | setup vio | setup TNS | hold ws | hold vio | max cap | max slew |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`nom_slow_1p08V_125C`** | **−3.2029** | **2,003** | **−2,075.11** | +0.4082 | 0 | **10** | **14** |
| `nom_typ_1p20V_25C` | +5.7231 | 0 | 0.0000 | +0.0367 | 0 | **10** | 0 |
| `nom_fast_1p32V_m40C` | +10.6634 | 0 | 0.0000 | **−0.2015** | **3** | **12** | **1** |

**[fact, `hw/soc/pnr/runs/full3/19-openroad-stapostpnr/summary.rpt`]**

> **The design does not meet a 20 ns period at the slow corner. It
> misses by 3.2029 ns on 2,003 endpoints, and 1000/(20 + 3.2029) is
> **43.10 MHz** **[estimate, arithmetic on a measured slack; the
> derived-Fmax convention `docs/31` section 4.2 uses]**.
>
> **That is 13.8 % below the 50 MHz target.** Pre-layout the same
> netlist bisected to 16.13 ns and 62.0 MHz (section 5.3), so **layout
> costs 7.07 ns and 18.9 MHz** **[estimate, difference of two
> measurements]**.

**It also fails hold, max cap and max slew**, and none of those is
hidden behind a green summary:

- **Hold: −0.2015 ns at the fast corner, 3 endpoints.** This is a real
  post-layout number, not `docs/38` section 8.3's pre-layout artefact —
  the clock tree is built, hold buffers are inserted
  (`PL_RESIZER_HOLD_SLACK_MARGIN 0.1`, `GRT_… 0.05`), and it still
  fails on three paths. The macro-corner caveat of section 9 applies:
  the SRAM Liberty at that corner is characterised at −55 C and the
  cells at −40 C.
- **Max cap: 10, 10 and 12 violations, at all three corners.** **Gated,
  and failing, because section 7 bound `MAX_CAP_VIOLATION_CORNERS` to
  `["*"]`.** In the shipped configuration this step would have printed a
  warning and the flow would have exited 0.
- **Max slew: 14 at the slow corner, 1 at fast, 0 at typ.** The same.

> **This is what section 7 was for.** Three of the five failing criteria
> in this run — setup at the slow corner, max cap and max slew — are
> gated only because four keys were set before the run rather than
> audited after it. **In LibreLane's and this PDK's shipped
> configuration, `design__violations` for this layout would have read
> lower and three of them would have been warnings.**

**What DID close**, and it is not a short list:

| Check | Result |
|---|---|
| Detailed routing DRC | **0** after 5 iterations (35 → 0 → 93 → 0 → 0 → 0) |
| Disconnected pins | **0**, of which 0 critical |
| Power-grid violations | **0** on VPWR and VGND; `PSM-0040 All shapes … are connected` on both |
| Antenna, post-route | **1 violating net, 1 violating pin**, 514 diodes and 606 antenna cells inserted |
| Nets routed | 37,156 signal + 2 special, 286,273 vias, all single-cut |
| Routed wirelength | **3,095,532 um**; longest net **2,332.02 um** |
| Hold at slow and typ | **+0.4082** and **+0.0367**, 0 violations |

**[fact, `final/metrics.json`]**

### 8.3 The reset tree, which is the question `docs/45` handed over

| | slow corner |
|---|---:|
| `docs/45`, as synthesised, `rst_ni` gating | **−53.3681** (asynchronous), and `setup_sync` **−60.6191** was worse |
| this design, pre-layout | **−49.2780** (asynchronous), `clk_i` **+3.8711** |
| this design, post-clock-tree | **+14.7319** (asynchronous) |
| this design, post-route, extracted | **no asynchronous violation at any corner** |

**[fact]**

> **The reset tree is not a problem and it is not a problem in two
> different ways.**
>
> **The half that needed RTL got RTL.** Section 5's one flip-flop took
> `rst_sys_n` out of the combinational request path, which moved the
> synchronous group by 64.92 ns and the closing period by 2.49 ns. **No
> resizer could have done that**, because a reset net that carries data
> is a datapath and buffering a datapath does not remove it from the
> path.
>
> **The half that needed place-and-route got place-and-route, and it was
> not close.** 2,611 flip-flop reset pins on one net, charged 58.9033 ns
> of clock-to-Q in `docs/45`, become **+14.73 ns of recovery margin**
> once `repair_design` has built a tree — without being asked, without a
> configuration key, and in the same run that did everything else.
> `docs/45` section 7.2 estimated "about 13.0 ns, still two thirds of a
> 20 ns period" for a scaled single-buffer model and said "a tree, not a
> bigger driver, is the answer, and that is a floorplan input rather
> than an SDC one". **It was right about the tree and wrong about the
> difficulty: it is neither a floorplan input nor an SDC one, it is the
> default behaviour of a step that was always going to run.**
>
> The design's **2,611 violating setup endpoints at every corner
> pre-layout are exactly the reset fanout**, and post-layout the binding
> check is a datapath at 2,003 endpoints. **The obligation `docs/38`
> section 10 item 3 opened, `docs/44` section 5.3 measured and `docs/45`
> section 7.2 handed on is discharged.**

### 8.4 Where the time went, and why the floorplan is the suspect

**The critical path is the same structure it has been since `docs/43`,
now confirmed a third time and for the first time with wires on it.**
The worst `clk_i`-group path post-CTS starts at

```
u_ibex.gen_regfile_ff.register_file_i.raddr_b_i[1]
```

and passes through `s_addr[4]` — the fabric's broadcast address bus —
**[fact, resolving `28-openroad-stamidpnr-1/max.rpt` against the
netlist]**. `docs/45` section 7.4 found that startpoint in two
independently mapped pre-layout netlists, `raddr_a_i[4]` in one and
`raddr_b_i[1]` in the other, and named it as the structure `docs/43`
section 7.4 predicted and could not measure. **A placed and clocked
netlist finds the same register.**

**Three measurements say the floorplan is where the time went, and none
of them is conclusive on its own.**

- **The path is 101 nets long.** **[fact, counting `(net)` lines in the
  path report]** A path that deep is a path the resizer has already
  buffered heavily, and buffering long wires is what makes a path deep.
- **The standard cells occupy a strip 1,851.8 um wide and 790.0 um
  tall.** **[fact, the placement span of all 27,558 cells in
  `27-openroad-cts/soc_top.def`]** Maximum Manhattan separation inside
  the logic is therefore about **2,642 um**, on a design whose
  pre-layout critical path was 16.13 ns.
- **Clock-tree synthesis reports an average sink wire length of 996.17
  um on `u_ibex.clk`, over 2,464 sinks** **[fact,
  `27-openroad-cts` log, `CTS-0101`]**. Nearly a millimetre of wire per
  clock sink is a statement about how far apart the design was placed,
  not about the clock tree.

> **The standard cells occupy 396,178 um2 of a placeable area of
> 2,092,010 um2 — 18.9 %.** That is very sparse, and it is sparse
> because the die was sized against LibreLane's own synthesis of the
> same RTL, which is 32 % larger (section 6.3), and because **46.9 % of
> the die is SRAM macro whose position the pin geometry fixes**. A
> placer with four times the area it needs has no reason to keep
> anything close together, and `docs/12` section 7.6 recorded the same
> shape at the other extreme — `hw/openlane/sram_pilot`'s global
> placement DIVERGED at 5.3 % utilization around one fixed macro.

**This is a hypothesis with three pieces of evidence and no control, and
it is labelled as one.** Nothing here has run a second floorplan.
Section 11 item 3 is the experiment: the cheapest version is one run
with the channel sized to the netlist that is actually hardened rather
than to the one that is not, which would take the placeable area from
2.09 mm2 to about 0.9 mm2 and the die from 4.79 mm2 to roughly 3.6
**[estimate, arithmetic on a measured cell area at a 45 % target]**.
Until that run exists, **"the floorplan cost most of the 7.07 ns" is the
most likely explanation and not a measurement**, and the honest
statement of this document's headline number is that **43.10 MHz is the
frequency of this design IN THIS FLOORPLAN, not of this design.**

**One number in the sign-off report is the sharpest piece of evidence
for it and it arrives from the one checker that cannot fail.**
`route__wirelength__max` is **2,332.02 um** — a single net more than a
millimetre longer than the standard-cell strip is tall, in a design
whose entire pre-layout critical path was 16.13 ns. `Checker.WireLength`
read that number and **skipped**, because `WIRE_LENGTH_THRESHOLD` is
unset in both PDKs (section 7.2). Total routed wirelength is **3,095,532
um** over 37,156 nets **[fact]**.

### 8.5 Two of the flow's optimisation stages default to OFF

The first attempt at this run did not know that, and the difference is
4.30 ns.

| Stage | slow-corner setup ws |
|---|---:|
| `OpenROAD.STAMidPNR-2` — post-CTS resizing, placement-estimated parasitics | **−0.1577** (106 endpoints) |
| `OpenROAD.STAMidPNR-3` — after global routing, **without** post-GRT repair | **−6.8764** (2,426) |
| `OpenROAD.STAMidPNR-3` — after global routing, **with** it | **−2.5778** (1,976) |
| `OpenROAD.STAPostPNR` — detailed routing, extracted parasitics | **−3.2029** (2,003) |

**[fact, four `or_metrics_out.json` files across `full2` and `full3`]**

> **`RUN_POST_GRT_DESIGN_REPAIR` and `RUN_POST_GRT_RESIZER_TIMING`
> default to `False` in LibreLane 3.0.5**, and `hw/openlane/pilot_ihp`
> does not set them either **[fact, the Classic flow's own variable
> defaults and `runs/full2/resolved.json`]**. They are the two stages
> that optimise against GLOBAL-ROUTE parasitics rather than the
> placement estimate, and **on this design real wire capacitance costs
> 6.72 ns and by default nothing is asked to recover any of it.**
> Turning them on recovers **4.30 ns**.
>
> **Nothing in any report says they did not run.** The only evidence is
> one line of the flow log: `Gating variable for step
> 'OpenROAD.ResizerTimingPostGRT' set to 'False'`. **This is the same
> shape as the four checker defects of section 7, one layer down — a
> default that is not a decision — and it is a fifth instance for the
> list `docs/41` section 6.6 keeps.**
>
> They cost 8,910 s of the run and **7,910 timing-repair buffers**, and
> even so the resizer ends with `RSZ-0062 Unable to repair all setup`
> **[fact]**.

`RUN_HEURISTIC_DIODE_INSERTION` is also `False` by default and is
**left** there, which is a decision and a measured one: `docs/12`
section 4 measured it inserting 4,641 antenna cells for the same
zero-violation result three achieve.

### 8.6 Cost, and the numbers nothing judges

| | |
|---|---:|
| Summed step runtime, `full2` (netlist → post-CTS repair) | **22.2 min** over 35 steps |
| Summed step runtime, `full3` (global routing → sign-off) | **61.1 min** over 28 steps |
| of which detailed routing | **1,371.8 s** |
| of which the post-GRT timing resizer | **1,347.7 s** |
| of which `Magic.WriteLEF` | 463.6 s |
| Peak memory, detailed routing | **3,503 MB** |
| Disk | **1.1 GB** + **2.4 GB**, both gitignored |
| Standard cells, placed | **37,017**, of which **7,910** are timing-repair buffers and 383 clock buffers |
| Fill cells | **132,118** |
| Antenna cells | **606**, 3,298.58 um2 |
| Sequential cells | **3,085** — unchanged from synthesis |

**[fact; wall times on a shared 20-thread host, quoted as costs]**

**Two metrics this flow computes and judges with nothing**, reported
here because section 7.2 said they would be:

- **`design__max_fanout_violation__count` = 293.** There is no
  max-fanout checker step in the Classic flow at all.
  `MAX_FANOUT_CONSTRAINT` is the PDK's 10 against the library's declared
  `default_max_fanout : 8`.
- **`design__violations` = 0 and `flow__errors__count` = 0**, in the
  `final/metrics.json` of a run that fails setup, hold, max slew and max
  cap. **The aggregate metric does not aggregate**, which is `docs/23`
  section 3.2's finding exactly, and the only reason this run is not
  reported clean is that the four *checkers* were bound to `["*"]` and
  raised deferred errors of their own. **Reading `design__violations`
  would have said this layout is fine.**
- **`route__wirelength__max` = 2,332.02 um**, and `Checker.WireLength`
  skipped because `WIRE_LENGTH_THRESHOLD` is unset in both PDKs. **A
  2.3 mm net in a 2.3 mm die is section 8.4's evidence, arriving from
  the one checker that cannot fail.**

---

## 9. What this does NOT cover

Stated at length, because a green check read as wider than the thing it
examined is this repository's recurring defect. `docs/41` section 6.6
counts **eight** — `docs/28` 4.4a, `docs/34` 8.5, `docs/36` 3.3,
`docs/38` 7.3 and 8.2, `docs/39` 3, and twice in `docs/40` — and
`docs/45` section 8 counts **fourteen** under a wider reading that adds
`docs/41` 8.4, `docs/42` 5.1, `docs/43` 9.5 and 9.6 and `docs/44` 5.2.
**Four of the eight are defects in THIS flow** and section 7 configures
them out. This section is the other half of the same discipline: what
this run turns off, and what it therefore does not entitle anyone to
say.

- **THIS IS NOT A PHYSICAL SIGN-OFF. There is no DRC result, no LVS
  result and no XOR result, and nothing here may be read as though there
  were.** `RUN_MAGIC_DRC`, `RUN_KLAYOUT_DRC`, `RUN_KLAYOUT_XOR` and
  `RUN_LVS` are all 0 in `hw/soc/pnr/config.json`. **The reason is a
  prior measured result and not a schedule.** `hw/openlane/sram_pilot`
  ran all three decks over ONE `RM_IHPSG13_1P_512x32_c2_bm_bist` in a
  registered wrapper and they do not close: **Magic DRC 1,106,478
  errors, every one of which is inside the macro footprint and none
  outside; KLayout deep-mode DRC 2,316 in three rules, attributed to 57
  cells all inside the macro hierarchy; Netgen LVS 359**, because the
  GDS cell names carry no configuration infix and the CDL subcircuit
  names do, and because the extracted bus delimiters are `[15]` where
  the CDL's are `<15>`, so **none of the 188 bus pins match**.
  `docs/12` sections 7.5 and 8 record that as a **NO-GO on RM_IHPSG13
  for this PDK version**, tied to IHP-Open-PDK issue #239. It is a
  property of the PDK and not of this design, and running the decks
  here would re-derive six macros' worth of the same numbers at a cost
  of hours. **What that costs this document is real and is not being
  minimised**: a first layout that has not been DRC'd or LVS'd is not
  evidence that the layout is manufacturable or that it implements the
  netlist. It is evidence about **timing and area**, and that is all it
  is offered as.
- **`Yosys.EQY` is off.** Nothing here proves the placed netlist is
  equivalent to the RTL. `hw/soc/formal/` is where this project does
  equivalence work and it has not been pointed at `soc_top`.
- **No gate-level simulation of `soc_top` exists**, and this document
  does not create one. `docs/45` section 9 item 5 asked for it and the
  obstacle it named is unchanged in one respect and changed in another:
  the memory boundary is no longer a stand-in, but the macros are
  **blackboxes** in this netlist and the ROM **has no contents**, so a
  gate-level run would need the PDK's behavioural macro models and a way
  to load the ROM. Section 4.4. *Closed 2026-09-06 by `docs/74-core-gate-level-campaign.md`: the
  PDK's `FUNCTIONAL` macro models in the loop, the ROM loaded into its
  two macros by the bench at time zero, the clean run of `docs/42`'s
  workload identical to the RTL's in every published field.*
- **No behavioural evidence was re-run and none of it moved.** The one
  RTL change is `soc_bus.v`'s request gate, whose behaviour is strictly
  more conservative than what it replaced (section 5.2), and
  `soc_mem_sram.v` is never read by a simulation. `docs/44` section 8.1's
  22 checks and 185,443 cycles are still the last behavioural evidence
  and they still stand; **this document adds none**.
- **The fast corner's macro Liberty is characterised at −55 C while the
  standard cells around it are at −40 C.** The PDK ships
  `fast_1p32V_m55C` for the SRAM and `fast_1p32V_m40C` for the cells and
  there is no −40 C macro file, so the cross-corner map is forced.
  `docs/12` section 6.4a. **The hold result at that corner therefore
  carries a 15 C mismatch between the macros and everything around
  them**, and section 8.5 is where that matters.
- **IR drop is indicative only.** `VSRC_LOC_FILES` is unset, so
  `OpenROAD.IRDropReport`'s voltage numbers have no supply location
  behind them. Only its **connectivity** result is quoted, which is the
  thing it is used for here: it is the step that catches an unpowered
  macro.
- **One clock, one mode, no scan, no test, ~~no power number~~.** No
  multi-mode analysis, no DFT, no `mtime`-rate analysis, ~~and no dynamic
  or leakage power figure~~. *Corrected 2026-09-05: there was a power
  number, and it was in the `full3` run this document signs off.
  `OpenROAD.STAPostPNR` wrote a `power.rpt` per corner into
  `hw/soc/pnr/runs/full3/19-openroad-stapostpnr/` — 27.774 / 34.835 /
  46.095 mW at slow / typ / fast on a default activity assumption —
  found by `docs/53-workload-and-the-clock.md` section 7.1; measured at
  RTL activity by `docs/57-power-under-a-duty-cycle.md` section 5 it is
  **33.890 mW computing and 5.539 mW waiting at typ**, on a layout that
  does not contain the NPU. "One mode" is also wrong: `docs/57`
  section 4 finds a clock gate over 2,464 of the 3,085 flip-flops.*
- **The floorplan is a first floorplan and it was not swept.** Section
  6.1's arrangement is forced in its shape by the macros' single-edge
  pin geometry, but the die dimensions, the channel height, the macro
  ordering within a row and `PL_TARGET_DENSITY_PCT` are one point in a
  space nobody has explored. Section 8.4 is the evidence that the point
  matters.
- **`soc_top` has still never been through a signed-off flow, and it has
  still never been simulated as a netlist.** Those are the two sentences
  this document replaces `docs/45` section 8's last line with.

---

## 10. The guards

`sw/tests/test_soc_synthesis_guards.py` section 6, eight checks. Three
of them guard things that are silent in three different ways, and every
one of the eight was **mutation-tested** — the mutation applied, the
test observed to fail, the mutation reverted — because a guard that
cannot fail is the defect it is supposed to prevent.

| Check | The mutation it was shown to catch |
|---|---|
| `test_the_sram_memory_declares_soc_mems_ports` | `rdata_o` narrowed from `[31:0]` to `[30:0]` in `soc_mem_sram.v`. **A port whose width a drop-in gets wrong does not stop elaboration**; the same failure mode `docs/45` section 3.2 named for the generated boundary models |
| `test_the_fabric_does_not_gate_its_request_path_with_the_reset_net` | `issue_en` reverted to `rst_ni` in one of the two `can_issue` gates. **Nothing functional in this repository would catch this** — the behaviour is strictly more conservative either way — and it costs 2.49 ns and 8.8 MHz |
| `test_the_pnr_flow_writes_the_derate_as_a_float` | `5.0` written as `5`. The test is on the **type**, and additionally on the JSON **text**, because `5` and `5.0` are the same number in JSON's data model and not in this flow's |
| `test_the_pnr_flow_binds_every_timing_checker_to_every_corner` | `MAX_CAP_VIOLATION_CORNERS` narrowed to `["*typ*"]` |
| `test_every_macro_instance_the_pnr_config_places_exists_in_the_rtl` | a macro instance renamed to one that does not exist. It checks the `soc_top.v` instance, the generate-block label and the macro instance separately, so a **swapped** pair is caught and not only an absent one |
| `test_the_macro_blackboxes_declare_the_pdk_models_ports` | compares both `_bb.v` files against the PDK's own behavioural models, port for port. **Skips** without the PDK rather than passing, because a check that cannot see what it compares against is not a check |
| `test_the_pnr_flow_cannot_write_into_the_frozen_pilot` | the refusal removed from `pnr_soc_top.sh` |
| `test_the_pnr_flow_supplies_only_the_source_list` | the two assertions removed from the config generator |

**`.venv/bin/python -m pytest sw/tests/test_soc_synthesis_guards.py`:
26 passed** **[fact]**, against `docs/45`'s 18.

**What this section does NOT do**: it reads files. It does not place,
route or time anything, and it is **not a substitute for
`hw/openlane/checker_audit.py`**, which recomputes from the installed
LibreLane's own step classes whether a checker can in fact fail and
exits 1 if any is PARTIAL or NO-GATE. **These tests assert the
configuration is present; that script asserts it BINDS.** Section 7 is
the second of the two.

---

## 11. What the next block should be

1. **ECC on the memories, and it is now blocking something specific
   rather than being generally desirable.** `soc_top.v` fixes SecureIbex
   at 0 because MemECC requires seven SECDED check bits per word that no
   memory in this design stores, and section 4.4 is the first time that
   sentence has had a **geometry** attached to it: 39-bit rows out of a
   32-bit-wide macro family means either a second narrow macro per bank
   or a wider part with waste, and either way it is a different area and
   a different floorplan. For a part that claims fault tolerance, 72 KiB
   of unprotected storage that is now **4.29 times the logic by area**
   is the largest single-point failure in the subsystem. `docs/38`
   section 7 has carried this; it should stop being carried.

2. **How the boot ROM gets its contents.** Section 4.4: an SRAM macro
   powers up undefined, and this design contains nothing that can write
   the ROM. It needs a mask ROM, a serial load path, or a boot from an
   external interface. **It is an architecture decision, it is cheap to
   make and expensive to defer, and a layout has now made it
   unavoidable** — the current design would fetch undefined data from
   its reset vector.

3. **A second floorplan.** Section 8.4 measures what the first one
   costs. The die is 46.9 % macro and the logic sits in a channel whose
   shape the macros' single-edge pins force; nothing has explored
   whether a different macro arrangement, a different channel aspect or
   a different `PL_TARGET_DENSITY_PCT` moves the answer, and the cost of
   finding out is one run each.

4. **`mtime`.** `docs/41` section 7.4 ranked it first, `docs/43` section
   12 second, `docs/44` section 11 first, `docs/45` section 9 third. It
   is the oldest open item in the SoC and has now lost to a more
   interesting document five times running. This document adds one
   argument for it and one against: `u_clint` is on the post-layout
   critical path (section 8.4), which makes its internals a timing
   question and not only a robustness one — and equally, touching it now
   would change the block that the critical path runs through.

5. **A gate-level simulation of `soc_top`.** `docs/45` section 9 item 5,
   unchanged in rank and changed in obstacle: the memory boundary is now
   real, and what is missing is the PDK's behavioural macro models in
   the loop and item 2's answer. *Closed 2026-09-06 by `docs/74-core-gate-level-campaign.md`.*

6. **Give `campaign.py --directed` the `--jobs` it already accepts** —
   `docs/44` section 11 item 6 and `docs/45` section 9 item 6, untouched
   here and still true.

---

## 12. Corrections to earlier documents

- **`docs/45` section 8's last bullet and section 9 item 1** — "`soc_top`
  has still never been placed or routed" — are **closed**. The
  replacement obligations are section 9's: it has never been through a
  sign-off deck, and it has never been simulated as a netlist.
- **`docs/45` section 7.2's estimate of what the reset tree would cost**
  — "scaling `docs/44`'s measured 10.9223 ns into 2,766 pins gives about
  13.0 ns, still two thirds of a 20 ns period … a tree, not a bigger
  driver, is the answer, and that is a floorplan input rather than an
  SDC one" — was **right about the tree and wrong about the
  difficulty**. It is neither a floorplan input nor an SDC one:
  `repair_design` builds it unasked and leaves **+14.7319 ns** of
  recovery margin. Section 8.3.
- **`docs/45` section 7.2's diagnosis of the SYNCHRONOUS half stands and
  is acted on.** "A correctness gate in the fabric put the SoC's largest
  unbuffered net into the combinational request path" was exactly right,
  and section 5 is the change it implies. `docs/45` called the whole
  thing "place-and-route's problem"; **half of it was not**, and no
  amount of place-and-route would have fixed that half.
- **`docs/45` section 8's "the paths into and out of the memories are
  optimistic here by an amount this document cannot bound"** is now
  bounded: **0.42 ns of closing period**, which is inside `docs/44`'s
  measured 0.4 ns of noise and is therefore not claimed as a cost. The
  macro read arc is 9.2941 ns and the macro *input* setup is
  **negative**, so the stand-in was pessimistic on one side and
  optimistic on the other. Sections 4.1 and 5.3.
- **`docs/45` section 7.4's critical path** — starting at the register
  file's read-address register — is confirmed a **third** time, for the
  first time on a placed and clocked netlist:
  `u_ibex.gen_regfile_ff.register_file_i.raddr_b_i[1]`, through
  `s_addr[4]`. `docs/43` section 7.4's sentence and `docs/44` section
  5.1's correction of the numbers under it both stand. Section 8.4.
- **`docs/44` section 5.5's reversal condition**, which `docs/45`
  re-read as "whether 50 MHz survives place-and-route", now has its
  answer: **it does not, by 13.8 %**. That reopens `SYNPRE` as a
  question — it was declined at 1.8677 ns of recovery for 11.6 % of the
  core on the grounds that 20 ns was met with margin — but **it does not
  answer it**, because section 8.4's evidence is that most of the 7.07
  ns is floorplan and not logic. Recovering 1.87 ns of logic to close a
  3.20 ns gap caused by wires would be fitting a mechanism to the wrong
  cause. Section 11 item 3 comes first.
- **`hw/openlane/pilot_ihp/config.json`'s `SYNTH_HIERARCHY_MODE:
  deferred_flatten` is correct for the pilot and wrong for this
  design**, and this is a correction to the act of copying it rather
  than to that file. `pilot_top.v` has no tied-off configuration input
  of the kind `soc_top.v` drives into `ibex_top`, so the setting costs
  the pilot nothing and costs this design 13.84 ns. **The pilot is not
  changed.** Section 6.2.
- **`docs/41` section 6.6's list of eight** gains a ninth of the same
  shape, from a layer nobody had looked at: **`RUN_POST_GRT_DESIGN_REPAIR`
  and `RUN_POST_GRT_RESIZER_TIMING` default to `False`**, no report says
  they did not run, and on this design they are worth 4.30 ns. Section
  8.5.
- **`docs/23` section 3.2's finding that `design__violations` does not
  aggregate** is reproduced verbatim on a new design and a new PDK
  configuration: this run's `final/metrics.json` carries
  `design__violations: 0` and `flow__errors__count: 0` while failing
  setup, hold, max slew and max cap. Section 8.6.
- **`docs/12` section 7.3's PDN finding is reproduced at scale.** The
  Metal4-to-TopMetal1 connect is as load-bearing for six macros as for
  one: with it, `PSM-0040 All shapes … are connected` on both nets and
  zero power-grid violations, and the same **six** `PDN-0110 No via
  inserted between Metal4 and TopMetal1` warnings that document
  recorded. Section 6.1 and `hw/soc/pnr/pdn_macro.tcl`.
- **`docs/12` section 6.4g's "timing is usable; the read is slow"** is
  generalised from one part to the family in section 4.1, and the
  generalisation is the useful half: **the read arc is a function of
  depth, density improves with depth, and there is no dense shallow
  part.**

---

## 13. Files touched

`docs/34` section 2 pins the pilot by git blob hash of the files in
`hw/rtl/` and section 5 lists the flow configs. **Nothing in either set
is modified** **[fact]**.

| File | Change |
|---|---|
| `hw/soc/rtl/soc_mem_sram.v` | new — `soc_mem` on six RM_IHPSG13 macros |
| `hw/soc/rtl/soc_bus.v` | **the one RTL change**: the request path is gated by a locally registered `issue_en` instead of by `rst_ni`. Section 5 |
| `hw/soc/pnr/config.json` | new — the LibreLane configuration |
| `hw/soc/pnr/pdn_macro.tcl` | new — the Metal4-to-TopMetal1 macro grid connect |
| `hw/soc/pnr/RM_IHPSG13_1P_2048x64_c2_bm_bist_bb.v` | new — blackbox declaration, transcribed from the PDK model |
| `hw/soc/pnr/RM_IHPSG13_1P_1024x32_c2_bm_bist_bb.v` | new — the same |
| `hw/soc/flow/pnr_soc_top.sh` | new — the runner |
| `hw/soc/flow/syn_soc_top.sh` | `SOC_MEM=sram`, a fourth memory boundary mode; header |
| `hw/soc/flow/sta_soc_top.sh` | reads the macro Liberty per corner at `SOC_MEM=sram` |
| `hw/soc/sta/ibex_sta.tcl.in` | `@MACROLIB@` |
| `hw/soc/flow/sta_ibex.sh` | substitutes `@MACROLIB@` with a comment; **its `slack.rpt` is unchanged** |
| `hw/soc/tools.soc.mk` | `SRAM_TYP`, `SRAM_SLOW`, `SRAM_FAST`, and the corner-name mismatch stated |
| `sw/tests/test_soc_synthesis_guards.py` | section 6 — eight checks |
| `.gitignore` | `hw/soc/pnr/runs/`, `config.resolved.json`, `state/` |
| `docs/47-soc-place-and-route.md` | this document |
| `docs/00-index.md` | one row |

**No file under `hw/soc/rtl/` other than `soc_bus.v` was modified**, and
`hw/soc/ext`, `hw/soc/gen`, `hw/soc/genp`, `hw/soc/tools`, `hw/soc/out`,
`hw/soc/pnr/runs` and `hw/soc/pnr/state` are gitignored, by the rule `docs/38` section 11
already applies: fetched or generated, never vendored.

---

## 14. Reproducing this

```
make -f hw/soc/tools.soc.mk fetch-ibex fetch-sv2v
hw/soc/flow/sv2v_ibex.sh hw/soc/ext/ibex hw/soc/gen \
                         hw/soc/tools/sv2v-Linux/sv2v

# ---- section 3: the instrument, before anything is claimed to move ----
SOC_MEM=blackbox hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s47-repro-bb
#   27,696 cells, 3,077 flops, 392,932.8900 um2  -- docs/45 6.1
SOC_MEM=stub     hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s47-repro-stub
#   27,705 / 3,240 / 400,199.5242              -- docs/45 6.1

# ---- section 4.1: the macro library, measured rather than quoted ------
#   read arc = max cell_rise of the A_CLK -> A_DOUT table, slow corner
for m in $PDK_ROOT/ihp-sg13g2/libs.ref/sg13g2_sram/lef/RM_IHPSG13_1P_*.lef; do
  grep -m1 'SIZE' $m
done
#   and the matching *_slow_1p08V_125C.lib for each

# ---- section 5.3: the controlled 2x2 matrix --------------------------
#   BUS=old is `git show <before>:hw/soc/rtl/soc_bus.v` restored in place.
for mem in stub sram; do
  SOC_MEM=$mem hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/m-new-$mem
  SOC_MEM=$mem hw/soc/flow/sta_soc_top.sh 20 hw/soc/out/m-new-$mem
done
#   new bus, stub: setup_sync +4.3006 slow, setup_async -53.3625
#   new bus, sram: setup_sync +3.8711 slow, setup_async -49.2780
#   old bus, stub: setup_sync -60.6191 slow  <- docs/45 section 7.1

# The bisection. docs/44 section 5.3a measured that this flow's netlist
# does not depend on the period ABC is given, so this is STA only.
#   new bus + sram, reset cut:            16.13 ns, 62.0 MHz
#   new bus + sram, gate setup_sync only: 16.13 ns  (the cut is inert now)
#   new bus + stub, reset cut:            15.71 ns, 63.7 MHz
#   old bus + stub, reset cut:            18.20 ns, 54.9 MHz  <- docs/45

# The reset census, counted rather than described:
grep -c "\.RESET_B(rst_sys_n)" hw/soc/out/m-new-sram/soc_top.sta.v  # 2611
grep -o  "\.[A-Z_]*(rst_sys_n)" hw/soc/out/m-new-sram/soc_top.sta.v \
  | sort | uniq -c        # 1 .Q, 2611 .RESET_B, and no data sink

# ---- sections 6 to 8: the layout -------------------------------------
# The netlist LibreLane hardens is this one, for the reasons in 6.2.
SOC_MEM=sram hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s47-sram
#   27,565 cells, 3,085 flops, 396,177.6420 um2
python3 -c "import json,os; json.dump({'nl': os.path.abspath(
  'hw/soc/out/s47-sram/soc_top.netlist.v'), 'metrics': {}},
  open('hw/soc/pnr/state/syn_soc_top.state.json','w'), indent=1)"

hw/soc/flow/pnr_soc_top.sh full2 --overwrite \
    -F Yosys.JsonHeader -S Yosys.Synthesis \
    -S Checker.YosysUnmappedCells -S Checker.YosysSynthChecks \
    -S Checker.NetlistAssignStatements \
    -i hw/soc/pnr/state/syn_soc_top.state.json

# Section 6.2's rejected alternatives, both one key away:
#   "SYNTH_HIERARCHY_MODE": "deferred_flatten" and no -F/-S/-i
#     -> runs; 55 cheriot lines; STAPrePNR clk_i group -9.9731 at slow
#   "SYNTH_HIERARCHY_MODE": "flatten" and no -F/-S/-i
#     -> stops at Checker.YosysUnmappedCells, 3 soc_tmr_bank submodules
grep -ciE 'cheriot|trvk' hw/soc/pnr/runs/*/06-yosys-synthesis/soc_top.nl.v

# ---- the reports -----------------------------------------------------
V=$HOME/Documents/caravel-lif-crossbar/.venv-flow/bin/python
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/full2
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/full2

# The derate, audited where it can be audited. NOT in resolved.json,
# which records the integer 5 either way -- docs/31 sections 3.2, 10.3.
grep TIME_DERATING hw/soc/pnr/runs/full2/*/_env.tcl | head -1
grep "timing derate" hw/soc/out/s47-pnr-full2.log | head -1   # 5.0%
grep set_timing_derate hw/soc/pnr/runs/full2/final/sdc/*.sdc

# ---- the guards ------------------------------------------------------
.venv/bin/python -m pytest sw/tests/test_soc_synthesis_guards.py   # 26 pass
```

`hw/soc/out/`, `hw/soc/pnr/runs/` and `hw/soc/pnr/config.resolved.json`
are gitignored.
