# 67 — The 72 KiB nothing checked, and why the check bits fit only by halving the RAM

`docs/58-clint-time-base-hardening.md` section 15 item 3 named this
block and stated the enabling fact as it saw it: *"The codec this
document instantiates is (72,64) and the RAM macro is 64 bits wide."*
That coincidence is not the answer, and the reason it is not is the
whole of section 3: a (72,64) codeword is eight bits **wider** than the
row, and a macro row that is exactly the codec's data width has no bit
left for the codec's check field. Every way out costs something, and
this document costs each of them from the LEF before choosing.

`docs/47-soc-place-and-route.md` section 4.4 called the memories "the
largest open item in the subsystem"; `docs/58` section 15 called them
"the largest unprotected thing left, by two orders of magnitude over
anything in section 9.1". Three documents ranked memory protection and
deferred it, and each time the thing built instead was worth more than
the hardening would have been. This one builds it, and the argument
for building it now is the same criterion `docs/41` section 3.1 applied
to the watchdog: an upset in a word of the boot ROM is **persistent** —
nothing in this design ever rewrites the ROM — and **silent** until the
word is fetched, when it is a wrong instruction.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged, with the
derivation stated; **[planned]** = an intention with nothing behind it
yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the
TTIHP26b submission by hash. Nothing in `hw/rtl/`, `hw/tb/`, `tt/`,
`formal/` or `hw/openlane/` was modified; `hw/rtl/secded_enc.v` and
`secded_dec.v` are read in place by three new consumers and copied by
none; `hw/tb/Makefile.fi` was not invoked. Section 13 lists every file.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Where do the check bits live?** | **In the row, and the row holds one word instead of two.** A `RM_IHPSG13_1P_2048x64` row is 64 bits; a 32-bit word as **four (16,8) byte codewords** — each the shortening of the repository's one SECDED code with 56 data bits tied to zero — is exactly 64. No seventh macro, no die growth, no read-modify-write: a byte write lands through the macro's own `A_BM` with its check bits beside it. **The RAM is 32 KiB, not 64.** Section 3 costs the alternatives from the LEF: a seventh `2048x64` for (39,32) check bits is **+491,633.62 um2, +21.88 % of the six-macro area**, with a read-modify-write on every `sb` and `sh`; a `4096x16` for a (72,64) row code is **+257,608.51 um2, +11.46 %**, with one on every store. Section 3.4 measures what the 32 KiB that went were holding: **192 bytes of static data and a stack** |
| **And the boot ROM?** | A **(39,32) word code** — `docs/43`'s shortening, already proved — in a `RM_IHPSG13_1P_512x16` check macro per bank, **+90,618.62 um2, +4.03 %** from the LEF, ~~**and not placed**: `docs/61`'s floorplan has 60.48 um beside each ROM macro and the part is 236.80 wide.~~ **PLACED 2026-09-12** — and the sentence struck here is a measurement of the wrong axis. There is 60.48 um *beside* the ROM and 290.24 um *above* it, because a macro row is as tall as the RAM and the ROM is not; the part is 191.34 tall. Section 11's list carries the placement and why the pin edges made it slightly more than a coordinate change. Section 8 is the ROM's whole story, including that on this PDK nothing in the design can write its contents, and its check bits are in exactly the same position |
| **Does the decoder fit on the read path?** | **Pre-layout yes, with 2.04 ns of margin; post-layout no, and the margin is what layout spent.** Pre-layout at the slow corner with the reset net cut, the `A_DOUT`-launched path keeps **+2.0352 ns** against **+4.0728** on HEAD **[fact]**; routed, the same group's worst goes from **−2.7112 to −4.0021** and its population from **68 endpoints to 1,080**, because the read return grows from **12.7286 ns to 14.0728 ns** after `A_DOUT` **[fact]**. It is shallow as codecs go — eight column matches, not sixty-four, section 4.2 — and it is still not the binding path. Sections 5.2 and 5.3 |
| **What does it cost?** | **+2,068 cells, +234 flip-flops, +31,391.3124 um2, +4.783 %** on the whole SoC at the SRAM boundary, against a baseline that reproduces `docs/66`'s exactly **[fact]**; **+3.01 % of placed standard-cell area** after layout, on a die that does not grow. Of the flip-flops, **150 are the SCRUB block's counters, stickies and addresses** and 84 are the two codec wrappers' scrubber pointers, intervals and response registers. Section 5.1 |
| **Is there a scrubber?** | **Yes, and it is a back-door on the row port, not a fabric master.** `docs/51` section 12 priced a third master as a re-proof of the fabric; this one reads a row in an idle cycle, examines it in the next, writes back only the byte lanes the decoder corrected — never an uncorrectable one — and drops the result if the bus takes the port in between. The bus always wins. It repaired **36 of 360** upsets at the shipped interval and **135 of 360** at interval 0, and the campaign found the second setting missing what the first caught: **a scrubber's coverage of a row is the interval between two visits to it**, which is section 6.2's bound and section 7.3's measurement |
| **What is protected and what is not?** | Every stored bit of both memories, data and check. **Not**: the row address, the bank select, the scrubber's own pointer, the response registers, the codec's gates, and the ROM's contents in a part where nothing loads them. Section 9 |
| **Did the invariant move?** | **No. 217,682 cycles, 28 checks, fail mask 0, 783 console characters, identical to HEAD to the cycle** **[fact]**, with the RAM halved and the codec on every read. Section 7.4 |
| **The campaign?** | **1,000 injections into the two memories, by region of the link map, on three builds of one program.** On the design: **0 wrong answers, 0 traps, 0 hangs in 720** — 104 corrected at the shipped scrub interval (68 on a read, 36 by the scrubber), 168 with the scrubber walking every second idle cycle. The same 280 draws on the unprotected memory: **17 silent wrong answers, 17 announced failures and a hang**, fifteen of the seventeen from a constant the program reads on every round. Section 7 |
| **The layout?** | **Placed and routed on `docs/61`'s die against HEAD on the same die: 0 DRC, hold closed at three corners, the die not one database unit larger, +3.01 % of placed standard-cell area — and the read path costs 1.29 ns it did not cost pre-layout.** The `A_DOUT`-launched violating population goes from 68 endpoints at −2.7112 to **1,080 at −4.0021**, and its worst path spends **14.0728 ns from `A_DOUT` to a flip-flop against 12.7286** on HEAD. The binding path is still the register file's read address, at −4.4159 against −3.7806, which the codec does not touch and which this document reports without attributing. Section 5.3 |
| **What can still not be signed off?** | **The macros**, and therefore the die. `docs/12` section 8 and `docs/54` section 7 stand: no DRC, no LVS, no XOR result exists for any RM_IHPSG13 part on this PDK, and nothing here changes that. It is stated here and in section 11, not in a footnote |

---

## 2. What was built

| File | What it is |
|---|---|
| `hw/soc/rtl/soc_mem_ecc.v` | **New.** The codec, the write masks, the read-path correction, the error response and the scrubber, in one module both memory implementations instantiate at `HARDEN = 1`. Section 4 |
| `hw/soc/rtl/soc_mem.v` | The behavioural model, with a `g_plain` arm that is the file every document since `docs/39` ran, byte for byte, and a `g_ecc` arm that puts `soc_mem_ecc` over the same `mem` array and a `chk` array beside it. The ROM's check bits are derived at load from the frozen encoder |
| `hw/soc/rtl/soc_mem_sram.v` | The macro wrapper, with `docs/47`'s two arms kept under their labels and two codec arms added: the same four `2048x64` under `soc_mem_ecc` for the RAM, and the two `1024x32` plus two `512x16` for the ROM |
| `hw/soc/rtl/soc_scrub.v` | **New.** The SCRUB slot the map reserved since `docs/39`: six counters, six stickies, the two uncorrectable addresses, the scrubbers' enables and interval, fast line 11. Section 4.4 |
| `hw/soc/rtl/soc_top.v` | `MEM_HARDEN`, `ROM_HARDEN` and `SCRUB_IVL_RST`; the memories' new ports; `u_scrub` in its slot on its line |
| `regmap/memmap.yaml` and its seven generated files | RAM **64 KiB → 32 KiB**; SCRUB **reserved → implemented** |
| `hw/soc/pnr/config-ecc.json`, `floorplan.py --memory ecc`, `RM_IHPSG13_1P_512x16_c2_bm_bist_bb.v` | The floorplan for the codec arm's instance paths — the same six macros in the same places — with the ROM's check macro known and unplaced |
| `hw/soc/pnr/config-ecc-rom.json`, `floorplan.py --memory ecc-rom` | The same die and the same four RAM origins, with the ROM's two check macros PLACED — eight macros, added 2026-09-13. Section 11 carries the run |
| `hw/soc/pnr/config-lvs-ecc-rom.json`, `floorplan.py --memory ecc-rom --lvs-blackbox` | The same floorplan with `RUN_LVS = 1` and no `EXTRA_SPICE_MODELS`, which is the only recipe that matches: the vendor macro is a black box on both sides. Section 11 says what that does and does not prove |
| `hw/soc/flow/sta_mem_paths.sh` | **New.** The three memory path groups, by name, on a timed netlist. Section 5.2 |
| `hw/soc/fi/mem_campaign.py`, `hw/soc/tb/tb_soc_fi.v` | **New** and extended: a memory deposit by region of the link map. Section 7 |
| `hw/soc/formal/{byte_secded,soc_mem_ecc,soc_scrub}.sby` and their properties | Three proofs. Section 10.3 |
| `hw/soc/tb/cocotb/test_soc_mem.py`, `test_soc_scrub.py`, `mutate_soc_mem.py` | Sixteen tests in four configurations, twelve for the block, eight mutations. Sections 10.1 and 10.2 |

---

## 3. The trade, costed

### 3.1 The row has no spare bit, and that is the whole problem

`docs/47` section 4.2 chose the RAM's macro for two properties it
measured across the library: `RM_IHPSG13_1P_2048x64_c2_bm_bist` is the
smallest byte-writable 64 KiB build the PDK admits, and the one with the
fewest instances. Its row is 64 bits and holds two 32-bit words. A
(72,64) codeword — the codec's own width, `docs/58`'s coincidence —
needs eight bits the row does not have. A (39,32) codeword per word
needs fourteen. **There is no bit-widening in a hard macro**, so the
check field is either in another macro or in the space a narrower word
leaves.

The options, with every area read from the LEF `SIZE` statement and
none from a formula **[fact for the areas; the percentages are
arithmetic on them and on `docs/47` section 4.2's 2,246,899.85 um2 for
the six macros and `docs/61` section 8.3's 4,786,287.41 um2 die]**:

| | code | check bits per 64-bit row | where they go | macro area | of the six | of the die | writes | RAM |
|---|---|---:|---|---:|---:|---:|---|---:|
| **A, built** | four (16,8), one per byte | 32, in the row | the row's upper half | **+0** | 0 % | 0 % | byte by byte through `A_BM`, no read-modify-write | **32 KiB** |
| B | (39,32) per word, two words per row | 14 | a seventh `2048x64`, 56 of its 64 bits used | +491,633.62 | +21.88 % | +10.27 % | read-modify-write on every `sb` and `sh` | 64 KiB |
| C | (72,64) over the row | 8 | one `4096x16`, addressed by `{bank[0], row}` with `bank[1]` selecting the field | +257,608.51 | +11.46 % | +5.38 % | read-modify-write on **every** store | 64 KiB |
| D | four (16,8) per word, two words per row | 64 | four more `2048x64` | +1,966,534.46 | +87.52 % | +41.09 % | none | 64 KiB |
| E | byte parity, detection only | 8 | the same `4096x16` as C | +257,608.51 | +11.46 % | +5.38 % | none | 64 KiB |
| F | (39,32), one word per row | 7, in the row | 25 bits of the row wasted | +0 | 0 % | 0 % | read-modify-write on `sb` and `sh` | 32 KiB |

Two of the six are struck out by their own row before any timing is
measured.

**E is `docs/58` section 4.3's lesson in a different currency.** It
costs the same macro as C and corrects nothing — a parity bit tells the
program a word is wrong and leaves it wrong. `docs/58` found the
detector at 98.7 % of the corrector's area and concluded the detector
was not on the table; here the detector is at 100 % of one corrector's
macro area and 0 % of another's.

**F is dominated by A.** Both halve the RAM; F keeps a word code and
therefore needs a read-modify-write on every sub-word store, which A
does not, and F wastes 25 bits a row where A uses all 64.

### 3.2 Why a read-modify-write is a design change and not a wrapper

B and C keep the RAM at 64 KiB and pay for it in the protocol. Ibex
emits `sb` and `sh`; `soc_bus.v`'s contract carries `be_i[3:0]`. A code
over a field wider than the write granularity cannot update a byte
without reading the field, re-encoding and writing it back, which is a
second port cycle per store, a hazard against the pipelined request the
fabric permits, and a grant the memory would have to withhold.
`docs/47` section 4.2 refused exactly that when it struck the densest
part in the library out for having no bit mask:

> **That is a design change and not a wrapper, and it is not made here.**

`docs/50` section 5.2 then measured what one extra cycle of memory
latency costs this core on this program — **0.9714 cycles per RAM
response, 25.23 % of the run** — and the reason was that a two-stage
core with nothing between it and its memory stalls outright on a load.
A read-modify-write on stores is that cost on the store side of the same
machine, with no cache and no store buffer to hide it, and it is why B
and C are not priced in cycles here: their price in cycles would have
to be measured on a fabric that does not yet permit them.

**A code per byte pays none of it.** The macro's `A_BM` is a per-bit
write mask — `docs/47` section 4.3 records the PDK's own declaration
that `A_BM[i] = 1` writes bit `i` — so a byte and its eight check bits
are written together and nothing else in the row is touched. `gnt_o`
stays `req_i`, the response stays one cycle, `soc_bus.v` is byte for
byte the file `docs/50` section 8.1 repaired, and its formal suite
passes at HEAD (section 10.3).

### 3.3 The code that fits

Each byte codeword is the (72,64) Hsiao code of `hw/rtl/secded_enc.v`
with data bits 8..63 tied to zero — the construction
`ibex_regfile_secded.v` uses to make its (40,32). Over eight data bits,
three of the eight check rows are identically zero — `H_ROW5`, `H_ROW6`
and `H_ROW7` have no bit set below bit 8 **[fact,
`hw/soc/formal/byte_secded.sby` B4]** — so what is stored is a (13,8)
code plus three constant-zero bits, and (13,8) is the minimal SECDED
width for a byte. The three spare bits cost nothing, because the row
has them anyway, and a flip in one of them is a check-bit error with an
unambiguous syndrome (B2 covers it explicitly).

Four codewords per row are **four independent codewords**, and section
10.1's double-upset test measures what that buys: two upsets in two
lanes of one row are two single errors, each corrected, where a word
code would have reported one uncorrectable. `byte_secded.sby` B5 states
the independence over a free second lane.

The ROM is a **word code** — RO memories are never written by the bus,
so the read-modify-write argument does not apply, and the ROM's macros
are 32 bits wide with no spare bit at all. Its seven check bits are the
(40,32) shortening `docs/43` section 6.2 argued and
`regfile_secded.sby` proves, in a macro of their own (section 8).

### 3.4 What the 32 KiB that went were holding

The map's RAM was 64 KiB because `docs/08` section 3.1 modelled the map
on NOELVSYS and GR740 and `docs/39` froze it. Nothing sized it against a
program. Measured against the programs this repository has **[fact,
`riscv-none-elf-size` and `nm` on the ELFs the flows build]**:

| program | `.data` + `.bss` + PMP buffer | stack | RAM used |
|---|---:|---|---|
| `test_ibex.c`, the 28-check bring-up program | **192 bytes** (`__stack_bottom` = 0xC0) | from the top of RAM down | under 1 KiB **[estimate, no stack-depth measurement exists]** |
| `fi_workload.c`, `docs/42`'s kernel | 148 bytes (`.bss` 0x54 + `.pmpbuf` 0x40) | the same | the same |

The bring-up program links, runs and passes all 28 checks in 32 KiB
with the identical cycle count (section 7.4), and `link_soc.ld`'s own
`ASSERT` — *"RAM is full: .data, .bss and the PMP buffer leave no room
for a stack"* — is the check that would have fired.

**What would want the 64 KiB back, stated so the decision can be
reopened rather than re-litigated.** `docs/10` section 5's full-scale
weight image is 16,384 words, 64 KiB; `docs/66` section 7 loads the
pilot's image from flash **a register at a time, into the node, through
no RAM buffer**, and a full-scale loader that staged the image in RAM
would not fit it in 32 KiB. That is a sized requirement that does not
exist yet — `docs/50` section 7.4 and `docs/61` section 18 both record
that no workload has been — and if it arrives, option B is the design
that meets it, at the macro area and the protocol cost stated above.
The RTL keeps `docs/47`'s two-words-per-row arm under its own label for
that day, and section 10.4's census asserts it still elaborates.

---

## 4. The mechanism

### 4.1 One module under both memories

`hw/soc/rtl/soc_mem_ecc.v` stands between the fabric's slave port and a
**row port** in the shape of one RM_IHPSG13 macro: an enable, a write
strobe, a row address, a data-in, a per-bit write mask and a data-out
that lands the cycle after a read and holds across a write. The
behavioural model puts a register array under that port and the macro
wrapper puts six macros and a bank multiplexer; the codec, the write
masks, the correction, the error response and the scrubber are written
once and verified once. `docs/50` section 4 found a fifth copy of the
memory's parameter list by breaking it; this is the arrangement in
which the codec cannot have a second copy.

### 4.2 Correct on read, trap on uncorrectable

Every read decodes the row on the way out. A single-bit error in any
byte codeword is corrected before `rdata_o` and reported on `rd_o`. An
uncorrectable syndrome answers the read with **`err_o`**, which the
fabric carries in the response cycle — `soc_bus.v` rule 3 already does
— and Ibex takes as a load, store or instruction access fault. The
recovery is a trap, not a wrong word. `docs/58` section 5 argued that a
detector with no recovery is a fault channel; here the recovery is the
architectural one, the program's own trap handler, and section 7
measures it firing.

**The decoder is used for its syndrome and not for its outputs**, and
that is a timing decision with a proof behind it. `secded_dec.v`
corrects by matching the syndrome against all 64 data columns and
OR-ing the matches; over a byte, 56 of those columns belong to bits
that are tied to zero, and a synthesiser cannot delete a comparison
whose result feeds `data_hit`. The first build of this design used the
decoder's outputs as they are, and section 5.2's table carries what it
measured: the 64-wide match sat on a path ending at a macro's `A_BM`
pin. So the codec does what `ibex_regfile_secded.v`'s `FASTCORR` did
and one step more — the mask is the syndrome matched against the H
columns of the **eight live bits**, derived from the frozen encoder on
unit vectors exactly as the register file derives them, and `sec` and
`ded` follow from the mask and a one-hot test. `byte_secded.sby` B6 and
`regfile_secded.sby` C8 state that the byte, `sec` and `ded` so derived
equal the frozen decoder's **for every error of weight two or less**,
over a free codeword and a free error vector. Where they differ is
weight three and above, and the difference is in this file's favour: a
triple error whose syndrome equals a tied-off column makes the frozen
decoder report `sec` and "correct" a bit that is not stored, delivering
a wrong word as corrected; the fast decode reports it uncorrectable,
which is what the (13,8) code's own decoder would say. **A cover in
`byte_secded.sby` reaches that case**, so the divergence is a witnessed
fact and not a claim.

### 4.3 The scrubber is a back-door, and the bus always wins

`mtime` scrubs itself because it is rewritten every tick (`docs/58`
section 3.2). A memory word is rewritten when the program rewrites it,
and a constant, an instruction, or a word the program never touches is
rewritten never. Without a scrubber an upset in such a word sits until
a second one lands in the same 16-bit codeword, and the second is
uncorrectable.

`docs/51` section 12 priced the obvious scrubber — a bus master that
reads and rewrites every word — as a third master on a fabric whose
arbiter, fairness property and ownership queues are written for two,
"a document of its own". This one is not on the fabric at all. It lives
behind the row port:

1. In a cycle where the bus is not asking and the interval counter has
   expired, it reads one row.
2. In the next cycle, if the bus is **still** not asking, the decoders
   have that row, and it writes back every byte lane the decoder
   corrected — re-encoded from the corrected word, masked to those
   lanes — and advances. That is one `sec_o` per row repaired.
3. If the bus asks in that second cycle, the bus has the port: the
   address, the data and the mask on the row port are the bus's, the
   scrub result is dropped, the pointer stays, and the row is read
   again two cycles later.

So nothing is ever withheld from the bus — `gnt_o` is still `req_i`,
proved as M3 — and a bus write that lands between a scrub read and its
write-back cannot be overwritten, because the write-back does not
happen. `test_the_bus_always_wins_the_port` drives both cases and one
more: a bus *read* of another row in the examine cycle, on which a
scrubber that ignored the bus would put its write-back onto the port
under the bus's address and mask and corrupt the row being read.
Mutation `scrub_takes` (section 10.2) is that scrubber, and the test
catches it.

**A lane the decoder reports uncorrectable is never written back.**
Re-encoding a wrong byte would turn a detected double error into a
valid codeword over a wrong value — `soc_clint.v` H6's "standard way to
build an ECC counter that silently does nothing", in a memory. The lane
is left as it is, counted on `ded_o` with its row's offset, and the next
read of it traps. Mutation `wb_on_ded` is the launderer and the suite
catches it too.

The interval is `SCRUB.CTRL[31:16]` idle cycles between scrub reads,
with a floor of two because the row read in one cycle is examined in
the next; the design ships at **255**, which walks the 8,192-row RAM in
about 2.1 million idle cycles and costs one macro read in 256 idle
cycles **[estimate, arithmetic on the RTL's counters]**. A campaign sets
0. `docs/57` measured what a macro access costs in energy, and section
11 says the scrubber's share of it has not been.

### 4.4 The SCRUB block, and why the counters are not in BUSSTAT

`docs/58` section 9.2 took the last sticky bit below BUSSTAT's interrupt
bit and priced a ninth source at either moving that bit out of a frozen
header or splitting the sticky field around it. The memories have
**six** sources. They go where the map reserved a slot for them since
`docs/39` — `0xFF916000`, `SCRUB`, IRQ 23, fast line 11, "Memory
scrubber control, MEMSCRUB-like" — and nothing about the address, the
slot, the source number or the line is new.

Per memory, three quantities that `soc_busstat.v`'s header already
argued must not be folded into one:

| | what it counts | what it is |
|---|---|---|
| `CNT_RAMSEC`, `CNT_ROMSEC` | rows the scrubber **repaired** | the upset-rate counter, one per upset that nothing overwrote first, however many reads returned it corrected before the scrubber arrived — `CNT_RFSEC`'s meaning |
| `CNT_RAMRD`, `CNT_ROMRD` | reads that returned a **corrected** word | not upsets: one corrupt word read in a loop raises it every iteration until the scrubber reaches it. `RD >> SEC` is the observable signature of the interval being too long for the rate, which is what `CTRL.IVL` exists to change — `CNT_RFRD`'s meaning |
| `CNT_RAMDED`, `CNT_ROMDED` | uncorrectable syndromes, on a read or on a scrub | with `RAMADDR` / `ROMADDR` holding the byte offset of the last one, which is the thing a handler needs and a counter cannot carry |

The record is in the power-on domain and the interrupt enable in the
system domain, for exactly `soc_busstat.v`'s two reasons. `CTRL` — the
two enables and the interval — is in the **system** domain, and that is
a third decision: a watchdog stage-2 reset puts both scrubbers back to
enabled at the reset interval, which is the safe direction. The block
ships with both scrubbers **walking**, by `docs/44` section 11's rule
that a mechanism which ships disabled and has never caught anything is
a liability; `soc_scrub.sby` C6 states it as an invariant.

---

## 5. Measured area and measured timing

### 5.1 Area

`hw/soc/flow/syn_soc_top.sh` at `SOC_MEM=sram`, 20 ns, the recipe of
`docs/45`, `docs/61` and `docs/66`; `stat -liberty` on `ihp-sg13g2`
typical, the standard cells only, the macro area added from the LEF in
public (section 3). Every row is one synthesis of the same source list;
the configurations are `soc_top.v`'s own parameters through the flow's
knobs **[fact]**:

| configuration | `MEM_HARDEN` | `ROM_HARDEN` | cells | flops | area, um2 | Δ vs HEAD |
|---|:-:|:-:|---:|---:|---:|---:|
| **HEAD**, `778cdd5`, 64 KiB, two words per row | — | — | 43,884 | 5,599 | **656,385.0552** | — |
| the control: 32 KiB, one word per row, no codec, no scrubber, SCRUB present | 0 | 0 | 44,607 | 5,622 | 660,843.3762 | +4,458.3210 |
| the RAM protected, the ROM as `docs/47` built it | 1 | 0 | 44,917 | 5,730 | 673,967.2338 | +17,582.1786 |
| **the design: both protected** | 1 | 1 | **45,952** | **5,833** | **687,776.3676** | **+31,391.3124, +4.783 %** |
| the design with the frozen decoder's outputs used as they are (section 4.2) | 1 | 1 | 46,566 | 5,833 | 691,109.9496 | +34,724.8944 |

The HEAD row reproduces `docs/66` section 9's cell count, flip-flop
count and area exactly, which is what licenses the differences.

**Three readings.**

**The codec is +26,932.9914 um2 and +211 flip-flops against the
control**, the same map and the same four macros with the code off —
`docs/41` section 6.5's rule for what a hardening may be credited with.
The +4,458.3210 um2 and +23 flip-flops between HEAD and the control are
the SCRUB block's control, enable and interrupt-enable registers and
its read multiplexer — its counters have constant-zero events in that
configuration and the optimiser removes them — and the
one-word-per-row wrapper, whose `row_q` register feeds the event
address even with nothing to report.

**Where the flip-flops go.** +234 over HEAD, and the arithmetic closes
**[estimate, on the per-block counts below and the census of section
10.4]**: the two codec wrappers hold **47 and 44** against HEAD's 4 and
3, which is +84; `soc_scrub` holds **190** alone but **150** inside the
SoC, because the upper 19 and 21 bits of its two address latches are
constant at these region sizes and are removed; 84 + 150 = 234. The
190 are six 16-bit saturating counters, six stickies, six interrupt
enables, two scrubber enables, a 16-bit interval and two 32-bit
addresses; the 47 are 13 + 16 + 1 of pointer, interval and examine
strobe, the `rv0`, `rd0` and 13-bit `row_q` response registers, and
the 2-bit bank select. Per block, `hw/soc/flow/syn_soc.sh` **[fact]**:

| block | cells | flops | area, um2 | % of Ibex |
|---|---:|---:|---:|---:|
| `soc_scrub` | 903 | 190 | **16,710.9642** | 6.062 % |
| `soc_mem_ecc`, the RAM's byte code, `WORDS = 8192` | 557 | 45 | **8,616.5478** | 3.126 % |
| `soc_mem_ecc`, the ROM's word code, `WORDS = 2048`, `RO = 1` | 492 | 42 | 7,694.7948 | 2.791 % |
| `soc_mem_ecc`, `HARDEN = 0` | 84 | 14 | 1,946.8512 | 0.706 % |

against the 275,682.6198 um2 of `hw/soc/out/small-pmp/area.rpt`.

**The fast decode is worth −3,333.5820 um2 and −614 cells**, the
difference between the last two rows of the first table, and section
5.2 says what it was worth in time. It is measured because the first
build used the frozen decoder's outputs, and the numbers are kept
because a reader deciding whether to do the same for the next codec
should have them.

### 5.2 Timing, pre-layout

`hw/soc/flow/sta_soc_top.sh` at `SOC_MEM=sram`, `SOC_RESET_CUT=1`, the
macro Liberty at all three corners and the pilot's 5 % derate, 20 ns.
The reset cut is not optional on a pre-layout netlist: without it the
worst path is the unbuffered reset net at **−84.0327 ns** on HEAD
**[fact]**, `docs/45` section 6's finding, and it hides everything
else. What is reported is the slow corner, `nom_slow_1p08V_125C`,
because that is the corner every layout in this repository has failed
at.

`hw/soc/flow/sta_mem_paths.sh` is new: it reports, on the same
generated Tcl with the same constraints, the worst path **launched by a
macro's `A_DOUT`** (the read return: macro arc, bank multiplexer, codec,
fabric response multiplexer, the register that captures it), the worst
path **captured at a macro's input** (address, data and mask into a
macro), and the worst path **from a macro's output to a macro's input**
(the scrubber's write-back, which did not exist before this document).

| configuration | worst sync setup | FROM_DOUT | TO_MACRO | DOUT_TO_MACRO |
|---|---:|---:|---:|---:|
| HEAD | **+3.0029** | +4.0728 (`u_b1/A_DOUT[33]`) | +4.6568 (`A_BM[16]`) | no such path |
| the control | +3.2722 | +4.2891 | +3.9074 | +10.5810 (`A_DIN`) |
| RAM protected, ROM plain | +1.0224 | +2.1969 | +1.0224 (`A_BM[16]`) | +4.9867 |
| **the design** | **+0.5554** | **+2.0352** | **+0.5554 (`A_BM[0]`)** | +4.2063 |
| the design, frozen decoder's outputs | +1.3933 | +1.6333 | +1.3933 | +3.9622 |

**[fact, slack in ns at 20 ns; the endpoint in brackets is the path
report's]**

**Four readings.**

**The read return keeps 2.04 ns of slack.** The decoder and the
one-word multiplexer cost the `A_DOUT` path **2.0376 ns** against HEAD
and 2.2539 against the control, and it is not the worst path in the
netlist. `docs/43` section 7.4 measured the register file's decoder at
0.6926 ns and 3.5 % of the period, in series with an ALU; this decoder
is in series with a 9.2941 ns macro arc **[fact, `docs/47` section 4.1]**
and costs three times as much, on a path that had 4.07 ns to give.
`docs/50`'s register would have bought the whole 9.29 ns back for 25 %
of the cycles; nothing here reopens that arithmetic.

**The worst path is now INTO a macro, and it is the write mask.** The
`A_BM` pin's library setup at the slow corner is **2.2185 ns** **[fact,
the path report]**; the path into it starts at a fabric register,
crosses the request decode and the byte-enable expansion, and ends in
the `req_i ? bm_bus : bm_wb` multiplexer this codec adds. `docs/61`
section 9.4 found 303 violating endpoints captured at macro input pins
at −2.9768 ns post-layout in a design with no codec; this is that
population, one multiplexer longer, and section 5.3 is where it lands
after routing.

**The scrubber's write-back is a macro-to-macro combinational path,
and it has 4.2 ns to spare.** `A_DOUT` through the decoder, the encoder
and the mask multiplexer to `A_BM` of another bank: 9.29 ns of macro arc
plus the whole codec, inside 20 ns, with margin. It is reported because
it is the one path this design created that no earlier netlist had.

**Hold is worse pre-layout and closes after layout, in both
configurations.** The four rows fail hold at −0.2776, −0.3061, −0.4452
and −0.5671 ns on a netlist with no clock tree **[fact,
`slack.rpt`]** — the obligation `docs/38` section 10 item 3 places on
place-and-route and `docs/43` section 7.4 declines to be credited for
— and section 5.3's two layouts close hold at **all three corners**,
+0.5927 and +0.6033 at the slow one. The pre-layout hold column is
recorded and is not a result.

**The fast decode bought 0.40 ns on the read return and lost 0.84 on
the write mask, and the second number is noise.** The two "design" rows
differ only in the decoder's structure; the RAM-protected row with the
plain ROM differs from the design row in nothing on the RAM's write
path, and the two are 0.47 ns apart on it. `docs/44` section 5.2
measured this flow's resolution at about 0.4 ns **after** layout; two
mappings of the same cone before layout are at least that far apart,
and the honest reading of the TO_MACRO column is **between +0.5 and
+1.4 ns pre-layout, and the layout decides**.

### 5.3 Timing, post-layout

`docs/61`'s recipe, twice, on `docs/61`'s floorplan: `flow/syn_soc_top.sh`
at `SOC_MEM=sram`, then `flow/pnr_soc_top.sh` from `Yosys.JsonHeader`
with that netlist, `config-npu.json`'s die, core, macro origins,
orientations, density and checker bindings, three corners, extracted
parasitics, 5 % derate, 20 ns. The baseline is **HEAD's netlist**, not
`docs/61`'s: `docs/65` and `docs/66` added the GPIO port and the QSPI
controller after that layout, so the design `docs/61` placed no longer
exists and a comparison against its numbers would be a comparison of
three changes. The protected run is the **RAM protected and the ROM as
`docs/47` built it** (`ROM_HARDEN = 0`, section 8), on `config-ecc.json`,
which differs from `config-npu.json` in the RAM instances' generate
label, the PDN hookup's spelling of it, the unplaced check macro and
the one `chparam` — and in nothing geometric, which the generator
asserts.

**The baseline, HEAD at `778cdd5`** **[fact,
`hw/soc/pnr/runs/s67base2/…/summary.rpt`, `signoff_report.py`,
`checker_audit.py`; the run was interrupted after
`OpenROAD.RepairAntennas` and resumed from that step's state, section
14]**:

| corner | setup ws | setup vio | setup TNS | hold ws | hold vio | max cap | max slew |
|---|---:|---:|---:|---:|---:|---:|---:|
| `nom_slow_1p08V_125C` | **−3.7806** | **2,003** | **−2,401.00** | +0.6033 | 0 | 33 | 81 |
| `nom_typ_1p20V_25C` | +4.9092 | 0 | 0 | +0.2857 | 0 | 33 | 16 |
| `nom_fast_1p32V_m40C` | +9.9037 | 0 | 0 | +0.0630 | 0 | 33 | 12 |

Routed with **0 detailed-routing DRC errors, 0 disconnected pins, 0
power-grid violations and 0 antenna-violating nets** over 4,131,551 um
of wire, 58,955 standard cells placed; **17 of 19 in-flow checkers
gate fully**, the same two not gating as in every run since `docs/47`.
Against `docs/61`'s `npu2` — a different netlist, so a context and not
a delta — the worst setup is 0.2017 ns worse and inside `docs/44`
section 5.2's 0.4 ns floor, the TNS is 580 ns better on 172 fewer
endpoints, hold still closes at every corner, and max slew and max cap
are worse, 81 / 16 / 12 against 29 / 8 / 6 and 33 against 15.

`hw/soc/pnr/violator_census.py`, on the same run: **1,496 of the 2,003
violating endpoints launch from `raddr_b_i[3]`** and 402 from
`raddr_a_i[0]` — the register file's read address, the structure
`docs/43` section 7.4 predicted, `docs/45` measured twice and `docs/61`
measured a third time — and **68 launch from a macro's `A_DOUT`**, worst
−2.7112, which is the read-return population `docs/50` emptied with a
register and this document puts a decoder into. **461 are captured at
an SRAM macro's input pins**, worst −2.4281, the population `docs/61`
section 9.4 found had moved from the launch side to the capture side.
Those two groups are the ones section 5.2 measured pre-layout and the
ones the codec touches.

**The RAM protected, on the same die** **[fact,
`hw/soc/pnr/runs/s67ecc/…/summary.rpt` and `final/metrics.json`]**:

| corner | setup ws | setup vio | setup TNS | hold ws | hold vio | max cap | max slew |
|---|---:|---:|---:|---:|---:|---:|---:|
| `nom_slow_1p08V_125C` | **−4.4159** | **3,022** | **−5,742.57** | +0.5927 | 0 | 16 | 65 |
| `nom_typ_1p20V_25C` | +4.5238 | 0 | 0 | +0.2858 | 0 | 17 | 20 |
| `nom_fast_1p32V_m40C` | +9.8017 | 0 | 0 | +0.1012 | 0 | 18 | 11 |

| | HEAD | RAM protected | delta |
|---|---:|---:|---:|
| standard cells placed | 58,955 | **60,617** | +1,662 |
| standard-cell area placed, um2 | 854,729 | **880,499** | +25,770, +3.01 % |
| die area, um2 | 4,786,290 | **4,786,290** | **0** |
| macros | 6 | 6 | 0 |
| routed wirelength, um | 4,131,551 | 4,144,062 | +0.30 % |
| longest net, um | 2,219.70 | 2,554.76 | +15.1 % |
| detailed-routing DRC | **0** | **0** | — |
| disconnected pins, power-grid violations | 0, 0 | **0, 0** | — |
| antenna-violating nets | 0 | **4** | +4 |
| hold, all three corners | closes | **closes** | — |
| in-flow checkers gating fully | 17 of 19 | **17 of 19** | — |
| detailed routing, the flow's own runtime | 39 min 27.280 s | **39 min 28.545 s** | +1.3 s |

**The read return is where the codec lands, and post-layout it costs
1.29 ns and 1,012 endpoints.** The violating population, split by the
group section 5.2 measured **[fact,
`nom_slow_1p08V_125C/violator_list.rpt` of each run]**:

| population | HEAD count | worst | TNS | protected count | worst | TNS |
|---|---:|---:|---:|---:|---:|---:|
| launched by a macro's `A_DOUT` | 68 | −2.7112 | −140.45 | **1,080** | **−4.0021** | **−2,400.07** |
| captured at a macro's input | 461 | −2.4281 | −512.20 | 522 | −2.9257 | −1,166.12 |
| everything else | 1,474 | −3.7806 | −1,748.34 | 1,420 | −4.4159 | −2,176.38 |
| **total** | **2,003** | **−3.7806** | **−2,401.00** | **3,022** | **−4.4159** | **−5,742.57** |

and the worst path of that group, decomposed as `docs/47` section 8.4
decomposed its own **[fact, `max.rpt` of each run]**:

| | HEAD | RAM protected |
|---|---:|---:|
| clock to `A_CLK` | 1.9061 | 1.8679 |
| **inside the macro, `A_CLK` → `A_DOUT`** | **9.4799** | **9.4597** |
| **`A_DOUT` to the capturing flip-flop** | **12.7286** | **14.0728** |
| standard cells on that second half | 68 | 72 |
| arrival | 24.1146 | 25.4004 |
| required | 21.4034 | 21.3983 |
| **slack** | **−2.7112** | **−4.0021** |

**Five readings, and the first is the one this document exists to
report honestly.**

**Pre-layout the decoder fit with 2.04 ns to spare; post-layout it does
not, and section 5.2's margin was the estimate that layout spent.** The
routed read return grows by **1.3442 ns** — the codec, on the only path
that changed — and the population violating on it grows from 68
endpoints to **1,080**, because at 12.73 ns only a few bits of a few
banks missed and at 14.07 ns nearly every read-return bit does. That is
the same shape `docs/47` section 8.4 measured for the whole design and
`docs/49` and `docs/50` then spent three documents on: **a pre-layout
number on this floorplan is an estimate, and the estimate was 1.3 ns
optimistic here.**

**And the path it lands on has two codecs in series, which nothing had
before.** Its endpoint is inside the register file: a load's data goes
macro arc → memory decoder → fabric response multiplexer → core
writeback → **the register file's own SECDED encoder** (`docs/43`) →
its flip-flops. 1,008 of the 1,080 capture at the register file's data
bits and 217 at its check bits **[fact, `violator_census.py`]**. Two
independent codes over one word in one cycle is a structure this
project had not built before and would not have chosen deliberately;
`docs/50`'s response register is the mechanism that splits it, and
section 15 item 3 is where that now sits.

**It is still not the binding path.** The worst endpoint in the design
is `raddr_b_i[4]` at −4.4159, the register file's read address —
`docs/43` section 7.4's prediction, measured for the fourth time
(`docs/45` twice, `docs/61`, here). It moved **0.6353 ns** between the
two runs and the codec does not touch it: the netlist, the placement,
the clock tree and the routing all changed at once, so the movement is
**reported and not attributed**, which is `docs/61` section 8.1's rule
and `docs/49` section 6.3's before it. It is outside `docs/44` section
5.2's 0.4 ns floor, so it is not called noise either.

**The die did not grow and the router did not notice.** Same die to the
database unit, same six macros in the same places, **0 detailed-routing
DRC errors** after 21 iterations against 16, and detailed routing took
**39 min 28.545 s against 39 min 27.280 s** — 1.3 seconds apart on the
flow's own clock. What did move: four antenna-violating nets where HEAD
had none, and the longest net 15 % longer. Max slew is **better** (65 /
20 / 11 against 81 / 16 / 12) and max cap is **better** (16 / 17 / 18
against 33 / 33 / 33), which is not a claim about the codec — both are
properties of a placement that changed for every reason at once.

**Both runs exit non-zero and that is the flow working.** `docs/47`
section 7 bound every timing checker to every corner; both runs end
with `Checker.SetupViolations`, `MaxSlewViolations` and
`MaxCapViolations` naming their corners and LibreLane quitting, and
both reached `final/` with a GDS. `design__violations` reads **0**
anyway in both, which is `docs/23` section 3.2 recurring for the fourth
document.

---

## 6. Detection, correction and what accumulates

### 6.1 Three fault classes, and where each one goes

| upset | on read | on scrub | reported as | recovery |
|---|---|---|---|---|
| one bit in a 16-bit byte codeword, or in the ROM's 39-bit word | corrected before `rdata_o` | repaired in place, once | `CNT_*RD` per read, `CNT_*SEC` once | none needed |
| two bits in one codeword | `err_o`; the core traps | left as it is; counted, addressed | `CNT_*DED`, `*ADDR`, sticky, IRQ 23 if enabled | the trap handler; for the ROM, a reboot **[planned]** |
| two bits in two codewords of one row | both corrected | both repaired | two events | none needed |
| three or more in one codeword | outside the guarantee: detected or miscorrected as the code allows; section 4.2's fast decode never reports a phantom correction | the same | — | — |

### 6.2 The accumulation bound without the scrubber

With the scrubber off, an upset in a word nothing rewrites stays until
a second lands in the **same 16-bit codeword**. Under a uniform
per-bit rate λ per second, the expected number of upsets in one
codeword over time t is 16 λ t, and the probability that a given
codeword has taken two or more is about (16 λ t)² / 2 for small
arguments; over the 32,768 codewords of the RAM and the 2,048 of the
ROM the expected number of uncorrectable codewords by time t is
therefore about **34,816 × (16 λ t)² / 2 = 4.46 × 10⁶ λ² t²**
**[estimate, arithmetic; λ is not a number this repository has, and
`docs/16` section 7 says why]**. With the scrubber walking at the
shipped interval, t in that expression is bounded by one walk of the
RAM — about 2.1 million idle cycles, 42 ms at a 20 ns period
**[estimate]** — instead of the mission, and the exposure of any one
codeword is the interval between two visits to its row rather than the
time since it was written.

The number this document does not have is λ. What it has is the
comparison: the CLINT's exposure window is one cycle (`docs/58` section
3.2), the register file's is 31 cycles when the core is idle (`docs/43`
section 6.4), and the memory's is one walk. That is the ranking of the
three scrubbers, and it is the reason the memory's interval is a
register and the other two are not.

### 6.3 The ROM's uncorrectable is different

A double error in a ROM word the program executes is an instruction
access fault on every fetch of it, for ever, because nothing rewrites
the ROM. The recovery is not a handler — the handler cannot make the
word right — but a reboot into a part whose boot image comes from
somewhere that can be reloaded, which is section 8's question and
`docs/66` section 15's boot flow. **[planned]**

---

## 7. The campaign

### 7.1 Strata by consequence

`docs/41` section 3.1's criterion gives four different answers for four
kinds of word in the same 72 KiB, and a uniform rate over the whole
would describe none of them. `hw/soc/fi/mem_campaign.py` draws by
**region of the program's own link map**, read from the ELF the build
linked so that a change to the workload moves the strata with it:

| stratum | words | what an upset there is |
|---|---:|---|
| `ROM.text` | 404 | an instruction: never rewritten, executed repeatedly |
| `ROM.rodata` | 8 | a constant the program reads |
| `ROM.unused` | 1,604 | a row above the image, fetched by nothing |
| `RAM.data` | 21 | `.data` and `.bss`, including the four words the program publishes its answer in |
| `RAM.pmpbuf` | 16 | the PMP test buffer, written once and read to check |
| `RAM.stack` | 256 | the top 1 KiB of RAM |
| `RAM.unused` | 7,888 | a word the program never touches |
| `RAM.chk` | 21 rows | a **check** bit of a used RAM row — state the codec added |
| `ROM.chk` | 404 rows | a check bit of a code row |

**[fact, the strata `mem_campaign.py` printed from
`hw/soc/out/s67-fi-h1/fi_workload.elf`]**

The workload is `docs/42`'s dense kernel, 18,682 cycles, injection
window 208..16,910, the same instrument as every core campaign since
`docs/42`; the deposit is one bit XORed into `mem[]` or `chk[]` of one
memory at a seeded cycle, through `tb_soc_fi.v`'s new `+mem`, `+midx`
and `+mbit`. Forty draws per stratum, 360 per build. Three builds of
the same program: **the design** (`SOC_SCRUB_IVL` at its reset default
of 255, under which the scrubber reads at most 73 rows in an 18,682-cycle
run **[estimate, 18,682 / 256]** and correct-on-read is what is
measured), **the design with the scrubber walking every second idle
cycle** (`SOC_SCRUB_IVL=0`, at most 9,341 scrub reads in the run, one
full walk of the 8,192-row RAM and a seventh **[estimate]**), and **the
counterfactual** (`SOC_MEM_HARDEN=0`, the same map, no check bits, no
scrubber, the check-bit strata absent).

The bench reads the words the program publishes — the signature, the
mask, the trap count, the exit code — **through the codec**, by a
simulation-only `observe` task on the behavioural model that decodes a
row lane by lane as a bus read would. The first run of this campaign
read the raw array, and six corrected upsets in the trap counter's own
word came back as six phantom traps: a bench that reads storage the
codec has not decoded is not an operator, and `docs/44` section 8.2's
distinction between a bench observation and a software-visible count
is the one this instrument now respects. The termination condition
still reads the raw exit magic, because the program's last act is to
store it and no deposit drawn inside the window can survive into it;
reading it through the decoder moved `docs/42`'s 18,682-cycle clean
run by one cycle, and the clean run is a published number.

Four controls before any data point: the clean run reproduces and
reports no memory event on either line; a flip of bit 31 of `fi_sig` —
the word the program folds every intermediate result into — classifies
CORRECTED on the hardened build and cannot classify MASKED on the
unhardened one; a flip in an unused RAM word classifies MASKED.

### 7.2 The design

360 injections, the scrubbers at their shipped interval, the watchdog
armed as the SoC is built **[fact, `hw/soc/out/s67-memfi/mem_records_h1.csv`]**:

| stratum | n | HANG | DETECTED | SDC | CORRECTED | MASKED |
|---|---:|---:|---:|---:|---:|---:|
| `ROM.text` | 40 | 0 | 0 | 0 | **15** | 25 |
| `ROM.rodata` | 40 | 0 | 0 | 0 | **34** | 6 |
| `ROM.unused` | 40 | 0 | 0 | 0 | 0 | 40 |
| `RAM.data` | 40 | 0 | 0 | 0 | **5** | 35 |
| `RAM.pmpbuf` | 40 | 0 | 0 | 0 | **26** | 14 |
| `RAM.stack` | 40 | 0 | 0 | 0 | **4** | 36 |
| `RAM.unused` | 40 | 0 | 0 | 0 | 0 | 40 |
| `RAM.chk` | 40 | 0 | 0 | 0 | **4** | 36 |
| `ROM.chk` | 40 | 0 | 0 | 0 | **16** | 24 |
| **all** | **360** | **0** | **0** | **0** | **104** | **256** |

The CORRECTED column is two mechanisms, and the records say which
**[fact, the `ramrd`/`romrd` and `ramsec`/`romsec` columns of the same
file]**:

| stratum | corrected on a **read** | repaired by the **scrubber** | either |
|---|---:|---:|---:|
| `ROM.text` | 14 | 1 | 15 |
| `ROM.rodata` | 34 | 0 | 34 |
| `RAM.data` | 1 | 4 | 5 |
| `RAM.pmpbuf` | 0 | 26 | 26 |
| `RAM.stack` | 4 | 0 | 4 |
| `RAM.chk` | 0 | 4 | 4 |
| `ROM.chk` | 15 | 1 | 16 |
| **all** | **68** | **36** | **104** |

**Five readings.**

**Not one wrong answer, not one trap, not one hang, in 360.** Every
injection that reached anything the program did was corrected on the
read that reached it, or repaired before anything did, and the
program's answer, its console and its exit were golden in all 360. The
class `docs/42` reported as structurally unreachable for the core —
CORRECTED — is where 104 of these went.

**The consequence ranking is in the read column, and it is the ranking
section 7.1 predicted.** A constant the program reads on every round
(`ROM.rodata`, 34 of 40) is reached almost every time; an instruction
(`ROM.text`, 14 of 40) is reached when the drawn word is in code that
runs after the drawn cycle, and a third of the image is; a stack word
(4 of 40) or a data word (1 of 40) is reached only when the program
reads it before it rewrites it; an unused word is reached never, in 80
of 80. **A uniform rate over the 72 KiB would have put one number on all
of that, and the number would have been 19 %.** The largest single
count in any record is **139 corrected reads of one word** — a
constant in a loop, corrected on every iteration until the run ended —
which is exactly the `RD >> SEC` signature `soc_scrub.v`'s header says
the interval register exists to shorten.

**At the shipped interval the scrubber repaired 36, and 26 of them are
the PMP buffer.** In an 18,682-cycle run at interval 255 the walk
covers rows 0 to about 73 **[estimate]**, and rows 0 to 47 are the
program's `.bss` and its PMP buffer: the scrubber reached the buffer's
rows once, after the injection, and repaired what it found. That is
the mechanism working and it is also a property of a short run on a
small program, and section 7.3 measures what a full walk does.

**The check bits are hit exactly as the data is.** 20 of 80 draws into
the check field came back CORRECTED — the state the codec added is
state an upset can land in, `docs/58`'s `mtime_chk` argument, and the
codec repairs its own field as it repairs the data. Nothing outside the
two memories was announced: `DETECTED` is zero, so no phantom trap, no
software flag and no watchdog stage came from an upset the codec
corrected.

**MASKED is not "the codec did nothing"; it is "nothing looked".** 256
draws landed in words that were never read after the drawn cycle and
never visited by the scrubber before the run ended, or were rewritten
before either.

### 7.3 The scrubber walking, and the counterfactual

**The same 360 draws with the scrubber at interval 0** — a read every
second idle cycle, one walk of the RAM and a seventh in the run
**[estimate]** — **[fact, `mem_records_h1s.csv`]**:

| stratum | n | HANG | DETECTED | SDC | CORRECTED | MASKED | of which read | scrub | both |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `ROM.text` | 40 | 0 | 0 | 0 | **31** | 9 | 2 | 24 | 5 |
| `ROM.rodata` | 40 | 0 | 0 | 0 | **38** | 2 | 12 | 26 | 0 |
| `ROM.unused` | 40 | 0 | 0 | 0 | **32** | 8 | 0 | 32 | 0 |
| `RAM.data` | 40 | 0 | 0 | 0 | 1 | 39 | 1 | 0 | 0 |
| `RAM.pmpbuf` | 40 | 0 | 0 | 0 | **0** | 40 | 0 | 0 | 0 |
| `RAM.stack` | 40 | 0 | 0 | 0 | **10** | 30 | 4 | 6 | 0 |
| `RAM.unused` | 40 | 0 | 0 | 0 | **22** | 18 | 0 | 22 | 0 |
| `RAM.chk` | 40 | 0 | 0 | 0 | 1 | 39 | 1 | 0 | 0 |
| `ROM.chk` | 40 | 0 | 0 | 0 | **33** | 7 | 5 | 25 | 3 |
| **all** | **360** | **0** | **0** | **0** | **168** | **192** | **25** | **135** | **8** |

**Three readings, and the second is the one to keep.**

**The walk finds what nothing reads.** 135 rows repaired that no read
had reached, against 36 at the shipped interval: 32 of 40 in the unused
ROM, 22 of 40 in the unused RAM, 24 of 40 instructions the program had
not yet fetched. Eight records were corrected on a read AND then
repaired in place, which is the two mechanisms in their intended
order. The ROM's constants, read every round, still show 12 corrected
reads: the walk got to 26 of them first.

**And the walk misses what it has already passed.** `RAM.pmpbuf` went
from 26 repaired to **0**, and `RAM.data` from 4 to 0: at interval 0
the pointer had left rows 0 to 47 within the first hundred cycles and
did not return inside the run, so a flip drawn there afterwards was
neither read nor revisited. At interval 255 the pointer was still
among those rows when the flips landed. **A scrubber's coverage of a
row is the interval between two visits to it, and a walk that is too
fast for a short run is no better for the low rows than one that is
too slow for the high ones** — which is section 6.2's bound in the
data, and the reason the interval is a register and not a constant.

**Nothing was announced, nothing was wrong, in 720 injections across
the two hardened builds.** The bus won the port on every one of the
9,000-odd scrub reads of this build **[estimate, 18,682 / 2]** and the
program's cycle count was 18,682 in every record of both.

**The counterfactual: the same draws, no check bits, no scrubber.**
`SOC_MEM_HARDEN=0`, the same map, the same program, the same 280 draws
of the seven strata that exist without a check field — every one with
the identical word, bit and cycle, checked record for record **[fact,
`mem_records_h0.csv` against `mem_records_h1.csv`]**:

| stratum | n | HANG | DETECTED | SDC | CORRECTED | MASKED | announced by |
|---|---:|---:|---:|---:|---:|---:|---|
| `ROM.text` | 40 | **1** | 9 | **2** | — | 28 | 7 traps, 6 watchdog stages, 7 self-check flags |
| `ROM.rodata` | 40 | 0 | 0 | **15** | — | 25 | nothing |
| `ROM.unused` | 40 | 0 | 0 | 0 | — | 40 | |
| `RAM.data` | 40 | 0 | 7 | 0 | — | 33 | 6 in the trap counter's own word, 1 self-check flag |
| `RAM.pmpbuf` | 40 | 0 | 0 | 0 | — | 40 | |
| `RAM.stack` | 40 | 0 | 1 | 0 | — | 39 | 1 self-check flag |
| `RAM.unused` | 40 | 0 | 0 | 0 | — | 40 | |
| **all** | **280** | **1** | **17** | **17** | **0** | **245** | |

And draw for draw, what the hardened build's verdicts became without
the codec **[fact, the two files joined on stratum and index]**:

| the hardened build said | n | unhardened: MASKED | DETECTED | SDC | HANG |
|---|---:|---:|---:|---:|---:|
| CORRECTED | 84 | 55 | 11 | **17** | 1 |
| MASKED | 196 | 190 | 6 | 0 | 0 |

**Four readings.**

**Seventeen silent wrong answers, fifteen of them from a constant.**
The `ROM.rodata` stratum is eight words the program reads on every
round, and in the unhardened build a flip in one of them changes the
answer on every round from then on and announces nothing: 15 of 40
draws, the highest silent-corruption rate any stratum in any campaign
in this repository has shown, and **zero of 40 with the code**. That
is `docs/41` section 3.1's "persistent and silent" measured on the
structure it was written about — a word nothing rewrites, in a memory
nothing writes, read by everything.

**Two more from instructions, and the rest of the instruction upsets
were loud.** 12 of 40 flipped instructions the program fetched were
caught by something — a trap, the watchdog, a self-check — and 2 were
not: a wrong instruction that computes a plausible wrong answer. With
the code, all 15 that were fetched were corrected on the fetch.

**The RAM's own words were the least of it, and the six "traps" in
`RAM.data` are the trap counter.** The bench reads the program's
published words out of the RAM, and in the unhardened build it reads
the raw array: six draws landed in the trap counter's own word, and
what the bench saw was a corrupted count — which is what software would
have seen too, and is a wrong published record. The hardened build
corrected the same six reads (section 7.1's `observe`) and reported
nothing, because there was nothing wrong to report.

**The calibration is exact on the strata the codec does not change
the fate of.** 190 of the 196 draws the hardened build MASKED are
MASKED without the codec too; the six that are not are the trap
counter's word above. The 84 draws the codec CORRECTED are 29 that the
unprotected memory turned into a wrong answer, a hang or an
announcement, and 55 that happened not to matter on this program on
this run — which is `docs/16` section 7.5's disclaimer measured: a
MASKED draw is a draw the program did not look at, not a draw the
memory absorbed.

### 7.4 The whole-SoC invariant

| build | cycles | checks | SCRUB counters at the end |
|---|---:|---:|---|
| HEAD, `778cdd5`, 64 KiB | 217,682 | 28, fail mask 0, 783 characters | — |
| **this RTL, 32 KiB, both memories protected, scrubbers at 255** | **217,682** | **28, fail mask 0, 783** | all six zero |
| this RTL, the scrubbers at interval 0 | **217,682** | 28, fail mask 0 | all six zero |
| this RTL, `MEM_HARDEN = 0` | **217,682** | 28, fail mask 0 | all six zero |
| the `QSPI_DEMO` image, `docs/66` section 8 | **60,706** | 5, fail mask 0 | all six zero |
| the `WDOG_RESET_DEMO` image, three boots | 37,405 | fail mask 0 | all six zero |

**[fact, `hw/soc/flow/sim_soc.sh`, `hw/soc/out/s67-*sim*/sim.log`; the
QSPI image reproduces `docs/66` section 8's 60,706 exactly]**

> **THE CORRECTION COSTS ZERO CYCLES AND THE HALVING COSTS ZERO
> CYCLES**, reproducing the invariant to the cycle. The first must: in a
> fault-free machine the decoder is the identity, which `soc_mem_ecc.sby`
> M2 proves by induction. The second is the finding of section 3.4 in a
> different form: the stack moved from the top of 64 KiB to the top of
> 32 and nothing the program does depends on where it is.
>
> `docs/66` section 8 asked that every document after it quote
> **217,682** for the 28-check image; this one does, and the number
> given in the brief for this work, 217,634, is `docs/65`'s figure for
> the program before `docs/66`'s refactor.

`tb_soc.v` now reads the six SCRUB counters at the end of every run and
fails the run if any is nonzero: a scrubber that walked both memories
for 217,682 cycles and repaired nothing, and a read path that corrected
nothing, is what a clean run has to report, and the last column above
is what every image reported. At interval 0 the scrubber read the RAM
port on every second idle cycle of a 217,682-cycle run and found nothing
to repair — which is the statement that the ROM's load-time check field
and every row the program wrote were codewords, made by an instrument
that would have said otherwise.

---

## 8. The ROM

`docs/47` section 4.4 and `docs/58` both left "how the ROM gets
contents" open. The honest statement, in three parts.

**On this PDK the boot ROM is an SRAM, it powers up undefined, and
nothing in this design can write it.** `docs/47` section 4.4 said so;
`soc_mem_sram.v`'s header says so; nothing here changes it. The check
bits this document adds to the ROM are in exactly the same position:
whatever loads the two data macros must load the two check macros,
through the same row port and the same encoder, or the first fetch
traps. **Check bits on a ROM nobody can write are check bits nobody can
initialise, and that is the correct reading** — they are not a
protection of the ROM as this design exists, they are the protection
the ROM will have once it has contents, and the simulation model
demonstrates that story end to end by deriving its check field from
the frozen encoder at load.

**In the flight part the ROM is one of three things, and none of them
is in this PDK.** `docs/47` section 11 item 2 named them:

1. **A mask ROM.** `libs.ref` of `ihp-sg13g2` at the pinned version has
   `sg13g2_io`, `sg13g2_pr`, `sg13g2_sram` and `sg13g2_stdcell` and no
   ROM generator **[fact, the directory listing]**. A mask ROM's bit is
   a via and not a bit cell: it has no upset mechanism for the code to
   catch, and would need no check bits at all — only its read path
   would be exposed, which is a transient and not a stored fault.
2. **An SRAM loaded before the core leaves reset.** Every RM_IHPSG13
   part carries a second, `A_BIST_*` port set that this design parks;
   a loader on it — from the QSPI flash `docs/66` built, or a serial
   test port — would write data and check bits together. That is a
   boot controller and a document of its own **[planned]**.
3. **A ROM that holds a loader and nothing else**, `docs/66` section
   15's recommendation, with the program in flash and copied to the
   protected RAM at boot. The ROM shrinks to what a loader needs, and
   the question of *its* contents is still 1 or 2.

**So the ROM's protection story is the boot flow's story**, and this
document does the part of it that is a memory problem — the code, the
macro, the wrapper, the model — and leaves the part that is a system
problem to the block `docs/66` already named next.
*Answered 2026-09-05 by `docs/68-boot-flow.md` section 3:* the flight
part's ROM is candidate 1, a mask ROM holding a loader, and its
protection story is that a via cannot be upset. The 8 KiB macro pair is
a stand-in, and what this section says about it is unchanged. What it does not do
is pretend: section 9's table lists the ROM's contents as unprotected
in the flight part until one of the three exists.

**The check macro, and where it would go.** Seven bits per word, 2,048
words, is 14,336 bits. One `RM_IHPSG13_1P_1024x16` holds both banks'
fields in one 16-bit row and costs **79,673.73 um2** **[fact, LEF]**,
but it is 236.80 um wide and `docs/61`'s floorplan leaves 60.48 um
beside each ROM macro **[fact, `config-npu.json`'s `CORE_AREA` and the
ROM's origin]** — placing it means growing the die by about 200 um in x,
roughly ~~**+0.4 mm2, +8.7 %**~~ **[estimate, arithmetic on the die's
2,075.22 um height -- SUPERSEDED 2026-09-13: this measured the wrong
axis. The space beside the ROM is not where the macros go; the space is
VERTICAL, in the pocket the shorter ROM macro leaves in its own row, and
the die did not grow at all. Section 11 carries the replacement and the
run. The number is left standing because it is what this document
believed when it planned the work]**, for a 0.08 mm2 macro. Two
`RM_IHPSG13_1P_512x16`, one per bank, cost **90,618.62 um2** together
and each is 236.80 x 191.34, which fits the 416.64 x 290.24 um pocket
the shorter ROM macro leaves above or below it in its row **[fact,
LEF; estimate that it routes]** — with its pin edge facing the channel
in one orientation and the ROM's own pin edge facing it in the other,
so the pocket placement is a routing question this document did not
run. ~~**The RTL instantiates the two `512x16`; the floorplan knows them
and places neither**~~ **[PLACED AND ROUTED 2026-09-13.** The pocket
estimate held. `floorplan.py --memory ecc-rom` places the pair at
x = 1,769.28, `u_c0` at y = 60.48 FS and `u_c1` at y = 1,821.96 N, with
95.94 um of clearance below and 98.24 um above and a 10 um halo, and the
die does not grow. Run `s83romecc5` routed it: a 113 MB GDS carrying
eight macros with `route__drc_errors = 0`. It took five attempts and the
two failures worth naming are `s83romecc4`, where placing the macros
against the ROM fixed the power grid and choked the router with
`GRT-0116` congestion, and `s83romecc3`, where bonding them onto the
global macro grid raised `PDN-0179` and silently covered the four
784.48 um RAMs as well. What routes is band-edge placement with a
**scoped** `rom_chk` PDN grid. Section 11 carries the numbers.**]** Note
what this does and does not move: section 5.3's layout is still taken
with the ROM as `docs/47` built it, through `ROM_HARDEN = 0`, a
measurement knob the guards forbid the design to set, and so is every
gate-level campaign, STA and power number in this corpus. One layout has
been built and routed with the ROM hardened. Nothing has been
re-measured on it.

---

## 9. What is protected, what is deliberately not, and what is not yet

| structure | bits | protection | reported through |
|---|---:|---|---|
| every stored bit of the RAM, data and check | 8,192 x 64 | (16,8) x 4 per row, corrected on read, scrubbed | `SCRUB.CNT_RAM*`, `RAMADDR` |
| every stored bit of the ROM, data and check | 2,048 x 39 | (39,32) per word, corrected on read, scrubbed | `SCRUB.CNT_ROM*`, `ROMADDR` |
| **the row address** into either memory | — | **none**: a corrupted index reads or writes the wrong row, which is a valid codeword. `ibex_regfile_secded.v` states the same limit for its read addresses and `docs/42`'s core strata carry the flip-flops it comes from | — |
| the bank and lane selects in the macro wrapper, `bank_q`, `half_q` | 3 | none: an upset returns another bank's row, decoded as a valid codeword | — |
| the response registers `rv0`, `rd0`, `er0`, `row_q` | 3 + 13 | none, `docs/41` section 3.1's "rewritten every tick" | — |
| the scrubber's pointer, interval and strobe | 30 + 28 | none: an upset moves where the next scrub read lands, or how soon | — |
| the SCRUB block's own state | 190 | none: an upset corrupts a number, `docs/44` section 9's position on BUSSTAT | — |
| the codec's combinational logic | — | none: a transient in an encoder or a decoder is a fault model no campaign here can express, `docs/58` section 11 | — |
| **the ROM's contents in the flight part** | 8 KiB | **not yet**: section 8 | — |

The first two rows are the whole of the 72 KiB, less the 32 KiB the
map no longer has.

---

## 10. Verification

Four kinds of evidence, `docs/41` section 6's division, and each is
blind to what the others see.

### 10.1 cocotb

`hw/soc/tb/cocotb/test_soc_mem.py`, the suite `docs/50` wrote for the
memory as a fabric slave, run in **four configurations** by the same
Makefile: the RAM's byte code, the same with `RDREG = 1`, the ROM's word
code (`RO = 1`, `ECC_BYTE = 0`), and `HARDEN = 0` **[fact]**:

| configuration | tests | passed | skipped |
|---|---:|---:|---:|
| RAM, `HARDEN = 1` | 16 | **16** | 0 |
| RAM, `RDREG = 1` | 16 | **16** | 0 |
| ROM, `RO = 1`, `ECC_BYTE = 0` | 16 | **14** | 2, the two that write |
| `HARDEN = 0`, `docs/47`'s model | 16 | **7** | 9, the codec's |

The seven protocol tests of `docs/50` run unchanged in every
configuration, because the codec must not change the slave's behaviour
on the bus. The nine new tests, all against `sw/golden/secded.py` and
never against the DUT's own encoder:

- the stored rows are codewords of the golden model, after whole-word
  and every byte-lane write;
- **a single upset in ANY stored bit** — all 32 data and all 32 (or 7)
  check bits, on four rows — is corrected on read, reported exactly
  once, and left in the storage;
- a double upset in one codeword answers with a bus error and its
  offset and is never written back; on the byte code, two upsets in two
  lanes of one row are both corrected;
- the scrubber repairs a word nobody reads, counts it exactly once, and
  a later read of it is clean; at two intervals;
- the scrubber never writes back an uncorrectable row;
- the bus always wins the port, in three shapes (section 4.3);
- the interval paces the scrubber at 1/max(2, N+1);
- nothing is reported when nothing is wrong, over 300 random accesses
  with the scrubber walking underneath;
- a read-only memory refuses the bus and keeps its codeword.

The ROM build has no bus writes, so the suite loads it the way the
flight part's loader would — word and check field deposited together —
and everything else is the same.

`test_soc_scrub.py`: **12 of 12** **[fact]** — the counters, the
stickies, the two reset domains, the saturation, the interrupt, the
addresses, the control register, and the scrubbers enabled out of
reset.

**Two harness defects, recorded because they produced confident wrong
numbers first.** A cocotb deposit is applied at the next scheduling
point and not when the assignment runs, so two deposits into one row at
the same simulation time read the same stale value and compose into a
double flip; the first version of the single-upset test reported a bus
error on a single upset for exactly that reason. And `sec_o` is sampled
in the write-back cycle while the row changes at the edge that ends
it, so a check of the storage in the cycle of the pulse reads the row
before the repair; the first version of the scrubber test reported a
row "not restored" that was restored one edge later.

### 10.2 Mutation evidence

`hw/soc/tb/cocotb/mutate_soc_mem.py`: eight edits to a copy of
`soc_mem_ecc.v`, each functionally invisible in a fault-free machine,
each asserted to have applied, and the claim that the suite fails on
every one. **8 of 8 caught** **[fact]**:

| mutation | what it is | caught by |
|---|---|---|
| `wb_raw` | the scrubber writes back the raw row: the launderer | the scrubber test, the port test |
| `wb_on_ded` | an uncorrectable lane is written back too | the never-writes-back test |
| `no_err` | an uncorrectable read is answered without `err` | the double-upset test, the never-writes-back test |
| `rd_raw` | the read path returns the raw word | four tests |
| `sec_never` | `sec_o` tied low | two tests |
| `scrub_takes` | the scrubber ignores the bus | the port test's third claim, **and only after it was added**: the first version of the suite passed on this mutant, because a write-back under the bus's own address and mask is invisible unless the bus is reading a *different* row in that cycle |
| `ptr_stuck` | the pointer never advances | three tests |
| `lane_swap` | lane 1's check bits from lane 0's data | ten tests |

### 10.3 Formal

| job | tasks | result | cost |
|---|---|---|---|
| `byte_secded.sby`: the (16,8) shortening — B1 to B6 and the weight-3 divergence cover | bmc, prove, prove_abc, cover | **4 of 4 pass** | seconds |
| `regfile_secded.sby`: C8 added, the word code's fast flags | bmc, prove, prove_abc, cover | **4 of 4 pass** | seconds |
| `soc_scrub.sby`: C1 to C7 at `CNT_W` 4 and 16 | bmc, prove, prove_w16, cover | **4 of 4 pass** | seconds |
| `soc_mem_ecc.sby`: the codec and scrubber over a four-row array, M1 to M8 | bmc depth 10, prove depth 4, cover | **3 of 3 pass** | **bmc 2 min 5 s, prove 13 s, cover 3 s** |
| `soc_bus.sby`, unchanged, at HEAD | bmc, prove, cover | **3 of 3 pass** | prove 20 s |

**[fact, SymbiYosys `Elapsed clock time`]**

`soc_mem_ecc.sby`'s harness owns a four-row array in `soc_mem.v`'s
shape and a ghost word per row, and proves by induction that **every
row is a codeword in every reachable state** (M1, the invariant that
makes the induction close, `soc_clint.v` H6's E1 for a memory), that
**the codec is invisible** — a read returns what the last write left,
lane by lane, and no report line ever rises (M2) — the protocol (M3),
that the bus owns the row port in its cycle (M4), that the scrubber
writes back nothing in a fault-free machine (M5), and, inside the
module, that the pointer moves only on an examined row and a
write-back happens only in an examine cycle with a corrected lane (M6
to M8). A bounded check at depth 24 was started and stopped at step 15
after nine minutes; the depths quoted are what the solver finishes,
and `docs/58` section 9.3 already recorded that an XOR-tree invariant
over storage is where SMT spends its time.

**What is NOT proved, and it is the important half.** Nothing in any
of these harnesses injects a fault into the storage — a formal harness
that deposits into a row is proving a property of the harness, `docs/58`
section 10.3's position. M1 and M2 are statements about the fault-free
machine; the correction is **measured**, in section 10.1 and section 7,
and the code itself is proved once for every consumer in
`formal/secded.sby`. `soc_bus.sby` passing at HEAD closes `docs/61`
section 18 item 5, which that document did not check.

### 10.4 The netlist census and the textual guards

`sw/tests/test_soc_synthesis_guards.py` section 9 synthesises the
macro wrapper with the three macros as blackboxes, on `syn_soc.sh`'s
recipe, and counts **[fact]**:

| configuration | flip-flops | and |
|---|---:|---|
| the RAM wrapper, `WORDS = 8192`, `HARDEN = 1` | **47** = 45 codec + 2 bank select | four encoders and four decoders by instance path, the scrubber's cells |
| the ROM wrapper, `WORDS = 2048`, `HARDEN = 1`, `RO = 1` | **44** = 42 codec + 2 | one encoder, one decoder, four macros by leaf name |
| `HARDEN = 0` | **16** = `rv0` + 13 of `row_q` + 2 | no `u_enc`, no `u_dec`, no `g_scrub` |
| `docs/47`'s arm, `WORDS = 16384` | **4** | its four macros under its label |
| the launderer mutation, `wb_raw` | **47** | the same as the design |

The last row is `docs/58` section 9.4's sentence for a memory: **the
census cannot tell a corrector from a launderer**, because re-encoding
the raw row costs the same flip-flops and the same cones as re-encoding
the corrected one. What tells them apart is the suite (mutation
`wb_raw`) and the text, and `sw/tests/test_soc_memory_guards.py` is the
text: the encoders cover `enc_in`, which is the bus word or the
**corrected** word and never the raw row; the read path returns the
corrected word; the write-back mask is `sec` and never `ded`; an
uncorrectable read answers with `err`; no report line is tied off; the
raw row reaches nothing but the decoders and the correction XOR;
`MEM_HARDEN` defaults to 1 and nothing outside three named flows sets
it; every event and control wire is connected between the memories,
`soc_top.v` and `u_scrub`; the scrubbers ship enabled; the software
header matches the block; and every instance path any of the three
floorplans places is an arm `soc_mem_sram.v` still has.

`test_the_four_soc_mem_declarations_agree_on_the_parameter_list`, from
`docs/50`, fired on the first build — the two stand-ins in
`syn_soc_top.sh` had not gained the new parameters and ports — and
passed after. That is the guard doing what `docs/50` section 4 built it
to do.

### 10.5 Everything else, re-run

| suite | before | after |
|---|---:|---:|
| `.venv/bin/python -m pytest sw/tests -q` | 412 **[estimate, 418 less this wave's six, four of which are in `test_soc_synthesis_guards.py` and require yosys]** | **418 passed, 0 failed** **[fact]**, re-run against the final tree in 4 min 32 s |
| `scripts/run_cocotb.sh`, every suite | 340 **[estimate, 373 less this wave's]** | **373 passed, 0 failed, 0 suites not clean** **[fact]**, re-run against the final tree |
| `hw/soc/formal`, `make bus` | 3 | **3 of 3** |
| `hw/soc/formal`, `make regfile` (C8 added) | 4 | **4 of 4** |
| `hw/soc/formal`, `make scrub`, `bytesecded`, `memecc` | — | **11 of 11** (new) |
| `hw/soc/formal`, `make` — every job, `soc_clint`'s 24 minutes included | 41 | **52 of 52 pass** **[fact]** |
| `hw/soc/flow/sim_soc.sh`, five images | 28 checks | **28 checks, fail mask 0**, section 7.4 |
| `hw/soc/flow/fi_npu.sh` | builds | **builds** — the NPU campaign's instrument reads the two new files and elaborates; its campaign was not re-run, the position `docs/61` section 12 and `docs/66` section 12 took |

Five guards fired during this work and every one was doing its job:
`docs/50`'s four-declarations check on the memory's parameter list;
`test_the_whole_soc_elaborates_as_one_design` on a source list that
did not yet name `soc_scrub.v`; `test_doc_links` on a document that did
not yet exist; and the two `.HARDEN` guards of the NPU and the watchdog,
which read the whole of `soc_top.v` and now read the instantiation they
are about, because the memories' `.HARDEN(MEM_HARDEN)` is a defaulted
parameter of `soc_top`'s own and has a guard of its own.

---

## 11. What the checks do NOT cover

Stated at length, in the discipline `docs/47` section 9 and `docs/58`
section 11 set, because this repository has been bitten by a green
check read as wider than its scope more times than either document
counted.

- **The macros cannot be signed off, and therefore neither can the die.
  This is not a footnote.** `docs/12` section 8's NO-GO stands and
  `docs/54` section 7 closed the KLayout exit: 1,106,478 Magic error
  boxes, 2,316 KLayout errors and 359 LVS errors over one RM_IHPSG13
  macro, every one inside vendor geometry this repository cannot edit,
  and the LVS half is IHP-Open-PDK issue #239. Nothing here changes any
  of those numbers. Every area in section 5 is a LEF `SIZE` and every
  timing number is a Liberty arc, and both describe a part that no open
  deck can check.
- **The ROM has no contents in the macro build**, and its check bits
  have none either. Section 8.
- ~~**The ROM's check macros are not placed.** Section 5.3's layout is
  the RAM protected and the ROM as `docs/47` built it; the design that
  ships has never been placed.~~
  **FLOORPLANNED 2026-09-12**, `floorplan.py --memory ecc-rom` and
  `hw/soc/pnr/config-ecc-rom.json`; **BUILT AND ROUTED 2026-09-13**, run
  `s83romecc5`. The distinction is the point and it was not made when
  this marker was first written: on 2026-09-12 a generator emitted
  coordinates and no eight-macro layout existed anywhere in the tree.
  The layout finished at 08:18 the next morning. A placement that has
  not been routed is a proposal:

  ```
  u_rom.g_rom_1024x32_ecc.u_b0   1769.28    347.76  FS
  u_rom.g_rom_1024x32_ecc.u_b1   1769.28   1387.26  N
  u_rom.g_rom_1024x32_ecc.u_c0   1769.28     60.48  FS
  u_rom.g_rom_1024x32_ecc.u_c1   1769.28   1821.96  N
  clearance: bottom 95.94 um, top 98.24 um, halo 10 um
  ```

  **The die, the core and the four RAM macros do not move**, which is
  what keeps every measurement taken on `docs/61`'s floorplan
  comparable with one taken on this one. The mode does not pass
  `ROM_HARDEN=0`, so the instances it names are the ones the RTL builds
  at its own default.

  **Why it sat open is worth more than the fix.** The row above and
  section 0's table say *"`docs/61`'s floorplan has 60.48 um beside each
  ROM macro and the part is 236.80 wide"* — which is true, and is a
  measurement of the wrong direction. **The space is vertical.** A macro
  row is as tall as the RAM, 626.70 um; the ROM is 336.46; so column 2
  carries **290.24 um of unused height in each row**, and the check
  macro is 191.34 tall. It fits with 98 um to spare and always did. The
  search stopped at the first axis it tried.

  The one real obstacle was pins, not area. Both rows put their pin edge
  against the channel -- the bottom row is `FS`, which mirrors the macro
  and lifts its pins to its top -- so the bottom row's pocket lies
  directly over the ROM's pins and a macro parked there would sit across
  every wire leaving them. The bottom ROM is therefore raised to the top
  of its own band, which puts its pins at the channel instead of 290 um
  below it, and the check macro takes the blind space underneath. The
  top row needs none of this: its pins are already at the channel and
  the pocket is above, on the blind edge.

  Nothing is written down as a coordinate. The placement is computed
  from the ROM's LEF size, the row pitch and the insets, and
  `place_rom_check()` asserts site and row alignment, the halo on the
  side each macro was put, and that neither leaves its macro row.

  **What the run then measured, 2026-09-13.** `s83romecc5` completed
  every step its configuration enables and wrote a 113 MB GDS carrying
  eight macros, `route__drc_errors = 0`, `design__disconnected_pin__count
  = 0`. Two decks were run on it separately, because that configuration
  gates all four off:

  * **Netgen LVS** matches. `Circuits match uniquely`, 263 symmetries,
    all seven `design__lvs_*` counters zero (`s83lvsbb2`). Read it for
    exactly what it is: the vendor macro is a **black box** on both
    sides, so this signs off the connectivity INTO all eight macros'
    pins and says nothing about the macro internals. Supplying the
    vendor CDL instead makes the run fail -- 64,901 netlist nets against
    63,155 layout nets, `Top level cell failed pin matching`
    (`s83lvs`) -- and the cause is the bus delimiters and the `!` on the
    CDL's globals, the same disagreement `docs/12` section 7.5 already
    measured as 359 LVS errors on one macro. Dropping the CDL does not
    repair that comparison; it removes it.
  * **KLayout DRC** reports **11,048** markers -- **6,584 distinct
    shapes**, because `Sdiod.d` and `Sdiod.e` are evaluated over the
    same derived layer and report an identical (cell, geometry) set,
    which `docs/54` section 3.1 measured on a different layout and this
    run reproduces exactly -- and every one of them is
    inside the vendor macro: `Sdiod.e` 4,464, `Sdiod.d` 4,464,
    `Cnt.c.digibnd` 2,120, attributed to 204 distinct cells of which 204
    are `RM_IHPSG13_1P_ROWDEC*`, `COLDEC*` or `RSC_IHPSG13_*`. Outside
    the macro hierarchy: **0**. The scope is what makes that worth
    stating -- the deck declared **173 rule categories in 47 groups**,
    M1 through M5, V1 through V4, TM1, TM2, MIM, NW, Act, Gat, Seal and
    the Fil family, and three fired. This is the first deck result in
    this repository that does **not** exclude the check macros.
    `docs/12` section 8's prediction held: 2,316 markers over 57 cells
    for one macro, 9,668 for six, 11,048 for eight.

  * **Magic DRC**, abstracted (`MAGIC_DRC_USE_GDS = 0`, so the vendor
    macros enter as their LEF abstracts), reports **170** error boxes
    against **123** for the six-macro layout `s77gate-drc-abstract`.
    `scripts/classify_magic_drc.py` attributes them --- and that script
    is new, because the classifications this repository already cites
    were produced by one that was never committed and could not be
    re-derived from a checkout. It reproduces `s77gate`'s recorded
    LEF-footprint split exactly, 16 inside and 107 outside of 123.

    On the eight-macro layout: **20 inside a macro footprint, 150
    outside**. The 150 is the abstraction, not the design. `M3.f` alone
    is 102 of it, and `M3.f`, `M2.f` and `M4.f` are all *wide-metal*
    spacing rules --- a LEF `OBS` blanket is one shape more than 10 um
    wide, so ordinary routing beside it violates a rule it would not
    violate against the macro's real geometry. This is the mechanism
    `docs/54` section 4 characterises for the KLayout deck, in Magic's
    vocabulary.

    **Four of the twenty are new, and they are worth naming.** `M2.d`,
    minimum area, fires four times: twice in `u_c0` and twice in `u_c1`,
    at 0.26 x 0.26 um. They are the check macro's own pin rectangles
    for **`A_DOUT[14]` and `A_DOUT[15]`** --- 108 of the macro's 111
    pins are exactly that size, and those two are the ones with nothing
    routed to them, so no attached wire grows the shape past the
    minimum. That is not a defect but a design fact made visible: a
    `512x16` row carries **two words' check bits, 7 + 7 = 14 of its 16**,
    and the top two outputs are unused. `cout0[14]` and `cout0[15]`
    appear exactly once each in the routed netlist, at the macro port
    and nowhere else, where every used bit appears twice. In the
    macro's real GDS that pin attaches to internal metal and has ample
    area; it is isolated only because this run reads the abstract.

    One caution about the other split this script prints. Against the
    *drawn* extent --- the LEF box plus a 0.225 um NWell overhang --- 33
    boxes straddle an edge, and **31 of them overlap by exactly
    0.0050 um**, at three different macro edges. The markers sit 0.220
    um from the LEF edge; the 0.225 model overshoots by five
    nanometres. Set the constant to 0.220 and all 31 move to *outside*.
    The drawn-extent number is decided by a 5 nm modelling choice and
    the LEF-footprint number is the one to quote.

  **And what it did not measure.** Magic DRC ran abstracted, not over
  the vendor GDS; `docs/12` section 7.5 measured that mode at 1,106,478
  errors inside a single macro and called it a no-go, and nothing here
  changes that. No XOR.
  Antenna repair took 538 net and 729 pin violations to 2 and 2, and the
  two left are real -- `net166` into
  `u_ram.g_ram_2048x64_ecc.u_b0/A_ADDR[4]` on Metal3 at 2.26x and an
  Ibex regfile net into `hold13394/A` on Metal2 at 1.22x -- neither in
  the check macros, and both `s81timing` and `s81drv` reached 0/0, so
  the tighter floorplan is what left them. Setup is broken at the slow
  corner, 3,529 violations and a WNS of -7.576 ns against a 20 ns
  period. **No campaign, STA or power number in this corpus has been
  re-measured on this layout.** Every one of them still runs on a
  `rom0` build.
- **The campaign is RTL, single-bit, storage only.** No transient in the
  codec's gates, no multi-bit strike, no gate-level netlist. The
  uncorrectable class is reached only by directed tests; a rate for it
  needs a fault model this repository does not have.
- **One workload, one seed, two scrub settings.** `docs/42`'s kernel,
  forty draws per stratum, the shipped interval and zero; nothing in
  between, and nothing on the bring-up program, whose ROM is nearly full
  and whose RAM use is section 3.4's 192 bytes.
- **The scrubber's energy is not measured.** One macro read per 256 idle
  cycles is arithmetic on the RTL; `docs/57`'s pipeline could put a
  number on it and this document did not run it.
- **The strata are the link map's, not the program's liveness.**
  `RAM.stack` is the top 1 KiB of RAM by declaration, not the frames
  the program actually had live at the drawn cycle; `ROM.text` includes
  code that ran before the window opened. A word drawn in either can be
  dead at its cycle, and the MASKED column carries that.
- **The counters are read hierarchically in every campaign.** In
  silicon they are read over the peripheral bus, and the program in the
  campaign does not; `docs/44` section 8.2's bench-versus-software
  comparison was not repeated here.
- **A ROUTER CHECK DID NOT RUN, IN BOTH LAYOUTS, AND IT IS THE PDK'S.**
  The detailed router emits, ~~seven~~ **ten** times per run,
  `[WARNING DRT-0349]
  LEF58_ENCLOSURE with no CUTCLASS is not supported. Skipping for layer
  <L>` — for `Cont`, `Via1` (twice), `Via2`, `Via3`, `Via4`, `TopVia1`
  (twice) and `TopVia2` (twice). **The seven lines are identical, layer
  for layer and count for count, in HEAD's run and in the protected
  one** **[fact, `grep DRT-0349` over both
  `openroad-detailedrouting.log` files]**, so it is a property of the
  `ihp-sg13g2` technology LEF and not of anything this document
  changed: the PDK states a cut-enclosure rule in a form
  (`LEF58_ENCLOSURE` without `CUTCLASS`) that this OpenROAD build does
  not implement, and the router skips it. **`0 detailed-routing DRC
  errors` therefore means zero errors among the rules the router did
  check**, and via enclosure on ~~nine layers~~ **seven layer names**
  was not among them. *Corrected 2026-09-05 by
  `docs/70-boot-hardening-placed.md` section 7: the enumeration in this
  bullet sums to ten lines over seven layer names, `docs/68` section
  9.3 stated it correctly, and four run directories —* `s67ecc`,
  `s68base`, `s68boot` *and both of* `docs/70`*'s — give ten and
  seven.* It
  belongs beside `docs/54`'s finding that this PDK's two DRC decks
  disagree about their own scope, and beside `docs/47` section 7.2's
  two checkers that gate nothing: this repository counts a check that
  did not run, and this is one. It was not noticed before this document
  because no earlier run's log was read for it; `docs/47`, `docs/48`,
  `docs/49`, `docs/50` and `docs/61` all inherit it.
- **Pre-layout STA is one mapping.** Section 5.2's last reading.
- **No frequency.** `docs/53` section 9.2's three grounds and `docs/05`
  section 4 rule 5, unchanged, and section 11's first bullet is a
  fourth.
- **The accumulation bound is a formula with no rate in it.** Section
  6.2.
- **`soc_mem_ecc.sby` proves a four-row array at depth 10.** Nothing in
  the properties names the size, and nothing here proves that the
  8,192-row instance inherits them.

---

## 12. Corrections to earlier documents

Every one is a dated in-place note by `docs/64`'s rule; the original
sentences stand.

- **`docs/58` section 15 item 3**: "the codec this document instantiates
  is (72,64) and the RAM macro is 64 bits wide" — the width coincidence
  was not the answer, and the note says what was.
- **`docs/47` section 4.4**: "adding them means 39-bit rows, which means
  a different macro geometry" — the geometry did not change; the word
  count did.
- **`docs/60` sections 5.3, 9.8 and 11.1**: the RAM is 32 KiB; the
  memory contents are protected; the ROM's check macros exist and are
  unplaced. A v0.2 of the datasheet is now owed by two documents.
- **`README.md`**: "no ECC on the 72 KiB of memory ... and nothing on
  the CLINT's `mtime`" — both done, `docs/58` and this.
- **`docs/00-index.md` section 2.2**: "no SRAM macro in any hardened
  design" has been false since `docs/47`; noted. Its section 6's
  verification totals are re-measured there.
- **Nothing in `docs/61` moves**, and its numbers are not compared with
  section 5.3's: `docs/65` and `docs/66` changed the netlist after that
  layout, so HEAD was placed and routed here rather than `docs/61`'s
  figures being differenced.

---

## 13. Files touched

### 13.1 RTL, under `hw/soc/rtl/`

| file | change |
|---|---|
| `soc_mem_ecc.v` | **new** |
| `soc_scrub.v` | **new** |
| `soc_mem.v` | `HARDEN`, `ECC_BYTE`; the `g_plain` and `g_ecc` arms; the load-time check field |
| `soc_mem_sram.v` | `HARDEN`, `ECC_BYTE`; `g_rsp`; the two codec arms; `rd_raw` and the write decode at module scope |
| `soc_top.v` | `MEM_HARDEN`, `ROM_HARDEN`, `SCRUB_IVL_RST`; the memories' ports; `u_scrub`; the slot decode and the line; the header |

**Nothing in `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/`
is modified. `docs/34`'s freeze is untouched.**

### 13.2 Map, flows, layout

| file | change |
|---|---|
| `regmap/memmap.yaml` | RAM 32 KiB; SCRUB implemented |
| `docs/memmap-soc.md`, `sw/golden/memmap_gen.py`, `hw/soc/rtl/soc_memmap.vh`, `soc_pnp_rom.vh`, `soc_apb_pnp_rom.vh`, `hw/soc/tb/sw/soc_memmap.h`, `memmap.ld` | regenerated |
| `hw/soc/flow/sim_soc.sh`, `fi_core.sh` | the two files; `SOC_MEM_HARDEN` and `SOC_SCRUB_IVL` by generated defparam, with the arm check |
| `hw/soc/flow/fi_npu.sh`, `pnr_soc_top.sh`, `syn_soc.sh` | the two files |
| `hw/soc/flow/syn_soc_top.sh` | the two files, the third blackbox, the stand-ins' parameters and ports, `SOC_MEM_HARDEN` and `SOC_ROM_HARDEN` |
| `hw/soc/flow/sta_mem_paths.sh` | **new** |
| `hw/soc/pnr/RM_IHPSG13_1P_512x16_c2_bm_bist_bb.v` | **new**, transcribed from the PDK model by machine |
| `hw/soc/pnr/floorplan.py`, `config-ecc.json` | `--memory ecc`; the generated floorplan |
| `hw/soc/tb/sw/soc_scrub.h` | **new** |
| `hw/soc/fi/campaign.py` | one comment |

### 13.3 Verification

| file | change |
|---|---|
| `hw/soc/tb/cocotb/test_soc_mem.py`, `Makefile.soc_mem` | nine tests, four configurations |
| `hw/soc/tb/cocotb/test_soc_scrub.py`, `Makefile.soc_scrub`, `mutate_soc_mem.py` | **new** |
| `hw/soc/tb/tb_soc.v` | the SCRUB counters checked at the end of a run |
| `hw/soc/tb/tb_soc_fi.v` | the memory deposit and its record |
| `hw/soc/fi/mem_campaign.py` | **new** |
| `hw/soc/formal/byte_secded.sby`, `byte_secded_props.v`, `soc_scrub.sby`, `soc_scrub_props.v`, `soc_mem_ecc.sby`, `soc_mem_ecc_props.v`, `soc_mem_ecc_int_props.v` | **new**; `Makefile` gains three targets |
| `hw/soc/formal/regfile_secded_props.v` | C8 |
| `sw/tests/test_soc_memory_guards.py`, `test_soc_synthesis_guards.py` | eight and six guards |
| `.gitignore` | the three jobs' working directories |
| `docs/67-memory-protection.md`, `docs/00-index.md`, `docs/47`, `docs/58`, `docs/60`, `README.md` | this document, its row, and dated notes |

---

## 14. Reproducing this

```
python regmap/generate_memmap.py
.venv/bin/python -m pytest sw/tests -q
scripts/run_cocotb.sh

# the memory and the block, in every configuration
cd hw/soc/tb/cocotb
make -f Makefile.soc_mem
make -f Makefile.soc_mem RDREG=1 SIM_BUILD=sim_build_soc_mem_rdreg \
     COCOTB_RESULTS_FILE=results_soc_mem_rdreg.xml
make -f Makefile.soc_mem RO=1 ECC_BYTE=0 SIM_BUILD=sim_build_soc_mem_rom \
     COCOTB_RESULTS_FILE=results_soc_mem_rom.xml
make -f Makefile.soc_mem HARDEN=0 SIM_BUILD=sim_build_soc_mem_h0 \
     COCOTB_RESULTS_FILE=results_soc_mem_h0.xml
make -f Makefile.soc_scrub
python3 mutate_soc_mem.py                                  # 8 of 8

cd hw/soc/formal && make bytesecded regfile scrub memecc bus

# the whole SoC, four images and two knobs
hw/soc/flow/sim_soc.sh hw/soc/out/s67-ecc-sim              # 217,682
SOC_SCRUB_IVL=0  hw/soc/flow/sim_soc.sh hw/soc/out/s67-sim-ivl0
SOC_MEM_HARDEN=0 hw/soc/flow/sim_soc.sh hw/soc/out/s67-sim-h0
SW_DEFINES=-DQSPI_DEMO       hw/soc/flow/sim_soc.sh hw/soc/out/s67-sim-qspi
SW_DEFINES=-DWDOG_RESET_DEMO hw/soc/flow/sim_soc.sh hw/soc/out/s67-sim-wdog

# area and pre-layout timing, five configurations, one recipe
SOC_MEM=sram hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s67-ecc-syn
SOC_MEM=sram SOC_MEM_HARDEN=0 hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s67-ctl-syn
SOC_MEM=sram SOC_ROM_HARDEN=0 hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s67-rom0-syn
SOC_MEM=sram SOC_RESET_CUT=1 hw/soc/flow/sta_soc_top.sh 20 hw/soc/out/s67-ecc-syn
hw/soc/flow/sta_mem_paths.sh hw/soc/out/s67-ecc-syn
hw/soc/flow/syn_soc.sh soc_scrub; hw/soc/flow/syn_soc.sh soc_mem_ecc
SOC_CHPARAM="-set ECC_BYTE 0 -set RO 1 -set WORDS 2048 -set RW 39" \
    hw/soc/flow/syn_soc.sh soc_mem_ecc

# the campaign, three builds of one program
hw/soc/flow/fi_core.sh hw/soc/out/s67-fi-h1
SOC_SCRUB_IVL=0  hw/soc/flow/fi_core.sh hw/soc/out/s67-fi-h1s
SOC_MEM_HARDEN=0 hw/soc/flow/fi_core.sh hw/soc/out/s67-fi-h0
python3 hw/soc/fi/mem_campaign.py --build hw/soc/out/s67-fi-h1  --tag h1
python3 hw/soc/fi/mem_campaign.py --build hw/soc/out/s67-fi-h1s --tag h1s
python3 hw/soc/fi/mem_campaign.py --build hw/soc/out/s67-fi-h0  --tag h0 --unhardened

# the layout, docs/61's recipe on docs/61's floorplan
PDK_ROOT=$HOME/.ciel python3 hw/soc/pnr/floorplan.py --channel 700.08 \
    --density 48 --cell-area 673967.2338 --memory ecc \
    --write hw/soc/pnr/config-ecc.json
SYN_NETLIST=$PWD/hw/soc/out/s67-rom0-syn/soc_top.netlist.v \
PNR_CONFIG=$PWD/hw/soc/pnr/config-ecc.json \
hw/soc/flow/pnr_soc_top.sh s67ecc --overwrite -F Yosys.JsonHeader \
    -S Yosys.Synthesis -S Checker.YosysUnmappedCells \
    -S Checker.YosysSynthChecks -S Checker.NetlistAssignStatements \
    -i hw/soc/pnr/state/syn_soc_top.state.json
```

The HEAD baseline layout is the same command on `config-npu.json` with
`hw/soc/out/s67-base-syn/soc_top.netlist.v`; this session's run of it
was interrupted after `OpenROAD.RepairAntennas` and resumed as
`s67base2` from that step's `state_out.json`, `docs/61` section 17's
own resume form, so its numbers are one run in two directories and
`s67base2/` holds only the tail of the flow.

**NO WALL-CLOCK FIGURE IN THIS DOCUMENT IS A WALL-CLOCK FIGURE, and
the reason is not modesty.** This session was interrupted for an
interval that is not in any log, in the middle of the two layouts and
after the campaigns, so elapsed time measured across it would be a
measurement of the interruption. Every runtime quoted here is the
**flow's own per-step `runtime.txt`**, which is written by the step and
does not span the gap: detailed routing at **39 min 28.545 s** against
**39 min 27.280 s** is two step timers, and the summed step time of the
protected run's 59 timed steps is **3 h 01 m** against **2 h 18 m** over
the baseline resume's 24 — which are not comparable to each other,
because one is a whole flow and the other is a tail, and are quoted
only so that neither is mistaken for the other. `docs/44` section 9.5's
rule is to quote a cost with the configuration it was measured in;
`docs/58` section 8.6 quoted a campaign runtime as a range for a
weaker reason than this one. The verification runtimes in section 10.3
and 10.5 — the SymbiYosys `Elapsed clock time` values and pytest's own
9 min 3 s — are each a single tool's own measurement of a single
uninterrupted invocation, and are quoted as such.

---

## 15. What the next block should be

1. **The boot flow, which is now the ROM's protection.** Section 8. The
   ROM's code and check bits are loaded together or the first fetch
   traps; `docs/66` section 15 named the loader and this document says
   what it must also write. Until it exists the highest-consequence
   words in the design are protected in simulation and undefined in
   silicon.
2. **Place the ROM's check macros**, in the pockets or on a grown die,
   and route them. Section 8's last paragraph is the geometry; the
   answer is one run.
   *Reprioritised 2026-09-05 by `docs/68-boot-flow.md` section 3:* that
   document decides the flight part's boot ROM is a mask-programmed
   array, whose bit is a via and which therefore has no stored-upset
   mechanism for a code to catch. **On that decision the check macros
   protect the SRAM STAND-IN and not the design**, and this item becomes
   conditional on which candidate a part takes rather than owed. ~~The
   macros stay in the RTL and stay unplaced.~~
   **Done 2026-09-13**, run `s83romecc5`, and the estimate above was
   right about the cost and wrong about the axis: it took one run in the
   sense that one run routes, and five in the sense that four had to
   fail first. Sections 8 and 11 carry the placement, the two failures
   worth naming and the deck results. The conditional stands -- on
   `docs/68`'s mask-ROM decision these macros still protect the SRAM
   stand-in rather than the flight part -- so what closed is the
   geometry question, not the question of whether the design wants
   them.
3. **`docs/50`'s response register, re-asked on this design.** Section
   5.3 measured the read return at **14.0728 ns from `A_DOUT` to a
   flip-flop**, with a macro arc, a memory decoder, the fabric and the
   register file's encoder on one path, and 1,080 endpoints violating
   on it. `docs/50` built the flip-flop that splits exactly that path,
   measured it emptying the group, and declined it because it cost
   25.23 % of the cycles on a program with nothing to hide the
   latency. **Three things have changed since**: the group is fifteen
   times larger, `docs/61` section 9.4 found the program now spends
   3,594 cycles per inference waiting for the NPU, and the path now
   carries two codecs. Its reversal condition is `docs/50` section
   7.3's item 2, and this is the first design in which the second half
   of it is arguable. One `SOC_MEM_RDREG=1` synthesis, one layout and
   one `sim_soc.sh` would settle it.
4. **Size a workload against 32 KiB.** Section 3.4's reversal
   condition. The two-words-per-row arm is kept for the day a sized
   requirement wants the 64 KiB back, and option B's cost is on the
   record.
5. **Read the SCRUB counters over the bus in a campaign**, `docs/44`
   section 8.2's comparison, so the operator's count and the bench's
   are shown to be the same number for the memories as they were for
   the register file.
6. **The scrubber's energy**, with `docs/57`'s pipeline, at the shipped
   interval and at zero; and then the interval a mission would choose,
   which is a rate this repository does not have (section 6.2).
7. **A v0.2 of `docs/60`**, now owed by `docs/58` and this document.
