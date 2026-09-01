# 45 — The SoC synthesised as one design

`docs/41-watchdog-hardening.md` section 10 item 7 is one line long:

> **`soc_top.v` has never been synthesised as one design.**

`docs/43-core-hardening.md` section 11 left it standing among the items
that "stand unchanged", and `docs/44-margin-and-observability.md`
section 10 closes with the same sentence, word for word, as the last
thing it does not cover. Three documents flagged it; none did it. Every
area and timing number under `hw/soc/` before this one is **per block**:
`hw/soc/flow/syn_ibex.sh` measures `ibex_top` standalone and
`hw/soc/flow/syn_soc.sh` measures one peripheral at a time, with
`soc_top.v` excluded from its source list on purpose.

This document does it. **It synthesises, in 27 seconds and 250 MB, and
it elaborated as one design at the first attempt with no unresolved
reference, no width mismatch and no multiply-driven net.** The
interesting results are the four that follow from having the whole
design in one netlist:

1. **`docs/44` was right that the reported critical path was an
   artefact, and right about which artefact.** With
   `cheriot_enable_i` a constant inside the design rather than a free
   input, the path it started is gone. **The whole-design critical path
   starts at the register file's read-address register** — in two
   independently mapped netlists — which is the structure `docs/43`
   section 7.4 named and could not measure. The *sentence* survives; the
   numbers under it still do not.
2. **The whole-design critical path leaves the core, crosses the fabric
   and comes back.** 12.43 ns of it is inside `u_ibex` and 5.45 ns is
   not. **No per-block synthesis in this repository contains that path**,
   which is what "the per-block figures may not compose" looks like when
   it is measured rather than predicted.
3. **The reset tree is worse at the top, and it is worse structurally
   and not just by scale.** `rst_sys_n` reaches **2,766 flip-flop reset
   pins** — and, unlike `docs/44`'s `rst_ni`, it is driven not by an
   input port with a `set_driving_cell` but by `rst_sync[1]`, a
   `sg13g2_dfrbpq_1`, the weakest flip-flop in the library. OpenSTA
   charges it **58.9033 ns of clock-to-Q** at the slow corner. **The
   whole SoC as synthesised closes setup at 80.62 ns, 12.4 MHz.** With
   the reset trees treated as built it closes at **18.20 ns, 54.9 MHz**.
4. **The area composes to 1.1 %, and one class of per-block number
   does not reproduce against today's tree.** `soc_fabric_meas` — a
   wrapper containing two
   modules neither of which has changed — measures **16,379.99 um2**
   today against `docs/40`'s **16,229.24**, and reproduces that older
   number **exactly** once the *whole source list* is restored to
   `docs/40`'s. Editing `soc_wdog.v` moved the measured area of a block
   that does not contain it. Section 4.3.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
intended, with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was modified.
`hw/rtl/tmr_voter.v`, `secded_enc.v` and `secded_dec.v` are **read** and
instantiated in place, as they already were. Section 11 lists every
file.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| Does `soc_top` elaborate as one design? | **Yes, first attempt, no edit to any RTL file.** `hierarchy -check -top soc_top` over Ibex, the fabric, both memories and every peripheral resolves every reference in **88.96 s at 737.39 MB peak**, with 17 warnings of which every one is "Replacing memory … with list of registers" **[fact]**. Section 5 |
| Does it synthesise? | **Yes. 27,694 standard cells, 3,077 flip-flops, 392,932.8900 um2, 54.141 kGE**, at 20 ns on `ihp-sg13g2` typical, with the two memories blackboxed **[fact]**. It takes **27.33 s and 249.35 MB** — wall times here are on a shared 20-thread host and are quoted as costs, not as precision — and the reason this had never been done is therefore not that it is expensive. Section 6.1 |
| What about the memories? | **They cannot be synthesised and were never going to be.** `soc_mem.v` says of itself that it is "a BEHAVIOURAL MODEL of a memory, not a memory"; the two instances are 16,384 and 2,048 32-bit words, **589,824 registers** [estimate, arithmetic on a measured `$dff` count] against 2,328 in the whole of Ibex. `proc; opt_clean` on the RAM alone takes **1,693.86 s and 2.77 GB** and yields 376,841 cells **[fact]**. `flow/syn_soc.sh` already excluded `soc_mem.v` for this reason. Two boundary models are provided and both are stated at length. Section 3 |
| Do the per-block numbers compose? | **In area, to about 1.1 %.** Sum of the nine blocks as re-measured in this session: **397,329.2568 um2**; the whole design: **392,932.8900**. The whole is **4,396.3668 um2 smaller, −1.11 %**, and it additionally contains `soc_top`'s own glue, which the parts do not — counting that on the parts side makes it −5,812.6950, −1.46 % **[fact for both totals, estimate for the difference]**. Flip-flops: 3,085 against 3,077. Section 6.2 |
| Do they compose in timing? | **No, and the gap is well outside the noise.** `ibex_top` alone, as shipped, closes at 16.30 ns; the SoC closes at **18.20 ns**. **Integration costs 1.90 ns and 6.4 MHz**, and the unprotected pair moves the same way — 12.80 ns to 13.97 ns, 1.17 ns **[fact, four bisections]**. `docs/44` measured this instrument's noise at about 0.4 ns; both numbers are outside it. Section 7.6 |
| Where is the real critical path? | **It starts at the register file's read address and it is a cross-block path.** Flattened build: `u_ibex.…register_file_i.raddr_a_i[4]` → the fabric → `u_rom.gnt_o` → `u_pnp.gnt_o` → back into the core. Hierarchical build, a different netlist: `…register_file_i.raddr_b_i[1]` → `u_ibex` for **12.4256 ns** → `u_bus` for 3.05 ns → `u_clint` for 2.40 ns **[fact, two path reports]**. Section 7.4 |
| So was `docs/43` section 7.4 right after all? | **Its sentence, yes. Its numbers, still no.** "The decoder sits on the register read path and the register read path feeds the ALU" is what the whole-design critical path shows: two independently mapped netlists put the startpoint in the register file's read-address register. `docs/44` section 5.1's correction stands untouched — the *slack figures* under that sentence came from `cheriot_enable_i`, and this document is the first measurement in which they could not have. Section 7.4 |
| What does the reset tree become? | **2,766 pins on the system reset and 199 on the power-on reset, and the large one is driven by a minimum-drive flip-flop.** `rst_ni` in `docs/44` drove 2,328 pins **from an input port carrying `set_driving_cell sg13g2_buf_4`**, for 10.9223 ns. `rst_sys_n` here drives 2,766 from `sg13g2_dfrbpq_1`, for **58.9033 ns** **[fact]**. Section 7.2 |
| Synthesis problem or place-and-route problem? | **Place-and-route, and this document does not soften that.** Nothing under `hw/soc/` has been through place-and-route; a reset tree is what place-and-route builds. But it is no longer only an obligation: at the top level the unbuffered net poisons the **synchronous** group as well, because `soc_bus.v` gates its request path with `rst_ni` by a decision its own source argues for. Section 7.2 |
| Does the SoC meet its target? | **At 20 ns, with the reset trees treated as built: yes, by +1.8079 ns at the slow corner, setup met at all three corners.** As synthesised, with the reset trees not built: **no, by −60.6191 ns**, and it closes nowhere below 80.62 ns **[fact]**. Hold fails by −0.1091 ns at the fast corner, on the path `docs/38` section 8.3 already characterised — and the failing path is `soc_top`'s own two-stage reset synchroniser, the shortest path in the design. Sections 7.1, 7.3, 7.5 |
| What does the register-file protection cost at SoC scale? | **+44,639.4564 um2, +12.82 %, +273 flip-flops** against the same SoC with upstream's register file **[fact, two whole-design builds]**. `docs/44` measured +40,369.0392 and +222 at core scale. **The 51 flip-flops of difference are exactly `soc_busstat`'s three register-file counters and their stickies** — 3 × 16 + 3 — which exist only because there is something to count, and which no measurement of the core alone can see. Section 6.4 |
| And in frequency? | **4.23 ns and 16.6 MHz, 71.6 → 54.9 MHz** **[fact, two bisections]**. `docs/44` section 5.3 put it at "somewhere around 13 to 17 MHz" from the core alone and 16.8 MHz from its own tie-off table. **That one composes.** Section 7.6 |
| Did the instrument reproduce before it moved? | **Yes, ten times.** Two netlists byte-identical by md5 to `docs/44`'s, three `slack.rpt` files byte-identical across a refactor of the verdict rule, `docs/44`'s tie-off slack 2.9677 and its 16.30 ns bisection to the digit, the shipped core's area to four decimal places on a byte-identical netlist, and five block areas exactly. Section 4 |
| And the ones that did not? | **Two, and the cause is a finding rather than a defect.** `soc_clint` measures 16,712.8164 today against `docs/40`'s 16,683.48, and `soc_fabric_meas` 16,379.9874 against 16,229.24. Both reproduce **exactly** once the source list is restored to the one those documents used. **A block's measured area under `flow/syn_soc.sh` is a function of the whole file list, not of the block**: reading three files `soc_clint` does not instantiate moves it by 29.33 um2, and the two files `soc_fabric_meas` does not instantiate move it by 150.75 **[fact]**. Section 4.3 |
| What is the worst thing this document leaves? | **Everything here is pre-layout and the one number that decides the part is now a place-and-route number.** 54.9 MHz against a 50 MHz target is 9.8 % of headroom, measured on a netlist with no clock tree, no parasitics and no reset tree, by a flow this project has three times seen move numbers down at layout. Section 8 |

---

## 2. What was built

| File | What it is |
|---|---|
| `hw/soc/flow/syn_soc_top.sh` | **The missing flow.** `soc_top` synthesised whole, on the recipe `syn_ibex.sh` and `syn_soc.sh` already use, with the memory boundary named and three ways of cutting it |
| `hw/soc/flow/sta_soc_top.sh` | The same three-corner OpenSTA recipe, pointed at `soc_top` |
| `hw/soc/flow/sta_verdict.awk` | The verdict rule, moved out of `sta_ibex.sh` so that two designs are judged by one rule and not by two copies of one |
| `hw/soc/sta/soc_top_reset_cut.sdc` | The two reset nets false-pathed, so the rest of the design can be timed. Default off; both recipes reported |
| `hw/soc/sta/ibex_sta.tcl.in` | `@TOP@`, so one per-corner script serves both flows. `sta_ibex.sh` substitutes `ibex_top` and its output is byte-identical |
| `hw/soc/flow/sta_ibex.sh` | Calls the shared verdict rule; otherwise unchanged, and its `slack.rpt` is byte-identical before and after |
| `sw/tests/test_soc_synthesis_guards.py` | Section 5 of that file: the whole SoC still elaborates, the two memory boundary models still declare `soc_mem`'s ports, the three synthesis flows still write one abc constraint, and the verdict rule is still one file |

**No RTL file was modified.** Not one line of `hw/soc/rtl/` changed to
make this elaborate, which is worth saying because the honest
expectation was the opposite.

---

## 3. The memory boundary, which is the one thing that cannot be synthesised

### 3.1 What `soc_mem.v` is, in its own words

```
// SCOPE, stated first because it bounds every claim made with this file
// in the loop: this is a BEHAVIOURAL MODEL of a memory, not a memory.
// It infers a register array …
```

`soc_top.v` instantiates it twice, at sizes the generated map fixes:
`SOC_SIZE_RAM = 0x00010000` and `SOC_SIZE_ROM = 0x00002000`, so
`RAM_WORDS = 16,384` and `ROM_WORDS = 2,048` **[fact,
`hw/soc/rtl/soc_memmap.vh`]**. The model declares
`reg [31:0] mem [0:WORDS-1]`, and Yosys reports "Replacing memory `mem`
with list of registers" for both instances **[fact, the elaboration
log]** — the `initial` block and the asynchronous reset between them stop
it inferring a memory primitive.

> **That is 589,824 registers** — 16,384 × 32 plus 2,048 × 32 —
> **against 2,328 flip-flops in the whole of Ibex** **[estimate,
> arithmetic on the two measured parameters and the model's own
> declaration]**.

`hw/soc/flow/syn_soc.sh`'s header already excluded `soc_mem.v` from its
source list for exactly this reason, and said so:

> `soc_mem.v` … is a behavioural array standing in for an SRAM macro, so
> its area is a property of the model and not of the design

**And it is measured, not only derived.** `proc; opt_clean` on the RAM
instance alone — no technology mapping, no `abc`, no synthesis of any
kind — takes **1,693.86 s and 2,767.05 MB** and produces **376,841
cells**, of which **16,384 are 32-bit `$dff`** — one per word — beside
278,530 multiplexers and 81,915 comparators of address decode **[fact,
`yosys -p 'chparam -set WORDS 16384 …; proc; opt_clean; stat'`]**.

> **16,384 × 32 in the RAM and 2,048 × 32 in the ROM is 589,824
> flip-flops** **[estimate, arithmetic on the measured `$dff` count and
> the ROM's own `WORDS`]**, against **2,328 in the whole of Ibex**
> **[fact, `docs/44` section 7.1, reproduced in section 4.2]**.

Twenty-eight minutes and 2.8 GB is the cost of *elaborating* one of the
two, and the mapping that would follow is the expensive part. **This is
not a tool limitation to be worked around; it is the correct answer to
the wrong question.** `soc_mem.v` is a stand-in for an SRAM macro, and
the area of a register array is a property of the model.

### 3.2 Two boundary models, and what each does not reproduce

`SOC_MEM` selects, and both models are **generated into the output
directory** rather than tracked in `hw/soc/rtl/` — the pattern
`flow/syn_soc.sh` already uses for `soc_fabric_meas.v`, for the same
reason: nothing instantiates them and nothing simulates them.

**`SOC_MEM=blackbox`** — a port declaration read with
`read_verilog -lib`. The two instances survive as unresolved cells with
no area, everything driving them and everything driven by them is kept,
and `stat -liberty` therefore reports **the SoC's standard-cell logic
and nothing else**. This is the cleanest area number and it is the one
section 6.1 quotes. **It cannot be timed**: OpenSTA has no liberty for
the macro.

**`SOC_MEM=stub`** — an SRAM macro stand-in. It keeps `soc_mem`'s ports,
keeps `gnt_o = req_i` combinational (which `soc_bus.v` rule S1 depends
on and which is the one real combinational path through this boundary),
keeps `rvalid_o` and `err_o` registered, **captures every remaining
input in a flip-flop** and **drives `rdata_o` from one**. So a path from
the fabric into a memory ends at a setup check the way it would end at a
macro's address register, and a path out of one starts at a clock-to-Q
the way it would start at a macro's output. That is what makes the
netlist readable by the existing OpenSTA recipe with no macro liberty
written.

> **It is not functional and is not supposed to be.** `rdata_o` is not
> the memory's contents. This netlist is for area and timing; it must
> never be simulated, and no result in this document is a behavioural
> one.

**Four things it does not reproduce, and every number measured through
this boundary inherits all four:** the storage, the address decode, the
read multiplexer, and **a macro's clock-to-Q and setup, which are much
larger than a standard-cell flip-flop's**. The last is the one that
matters for section 7: a real SRAM would make the paths into and out of
the memories *worse* than they are measured here, not better.

**`SOC_MEM=array`** builds the real thing. It is provided so the
paragraph above is falsifiable rather than asserted, and it is not run
in any reported measurement.

**The guard.** `test_the_memory_boundary_models_declare_soc_mems_ports`
parses `soc_mem.v`'s port list and both models' out of the flow script
and asserts they are equal in name, width, direction **and order**. Two
failure modes exist here and only the first is loud: a port a model does
not declare stops elaboration, and **a port whose width a model gets
wrong does not**.

---

## 4. Reproducing the instrument before moving it

`docs/44` section 5.2 established the rule this section follows: before
a number is claimed to have moved, the thing that measures it has to be
shown not to have. That document reproduced `docs/43`'s netlists
byte-identically, and that is why its correction was credible.

### 4.1 The verdict rule moved to a file, and nothing changed

`flow/sta_ibex.sh`'s header states the rule at length — every check
reported is also judged, the verdict names its own scope, there is no
bare pass token — and this document needed the same rule for a second
design. Two copies of a rule that must agree and that nothing compares
is the defect `docs/44` section 5.4 refused for a parity matrix, one
level up. So the rule now lives in `hw/soc/flow/sta_verdict.awk` and both
flows call it, and `sta/ibex_sta.tcl.in` takes `@TOP@` instead of a
literal.

**`flow/sta_ibex.sh` re-run on all three of `docs/44`'s netlists
produces a `slack.rpt` that is byte-identical to the one on disk from
that document's session** **[fact, `diff` on three files]**. The
generated per-corner Tcl differs in its header comment and in nothing
else.

### 4.2 Ten prior numbers, reproduced

| What | Source | Reproduced here |
|---|---|---|
| `h44-base` netlist | `docs/44` 5.2, md5 `3efbe801…` | **identical** |
| `h44-doc43` netlist | `docs/44` 5.2, md5 `3f742dc3…` | **identical** |
| `h44-port` netlist, the shipped core | `docs/44` 5.2 | **identical**, md5 `fa3c11ae…`, re-synthesised in this session |
| shipped core area | `docs/44` 7.1: 22,338 / 2,328 / 316,051.6590 | **22,338 / 2,328 / 316,051.6590** |
| shipped core, tie-offs, worst `setup_sync` slow | `docs/44` 5.2: 3.5468 for `h44-doc43`, 2.9677 for `h44-port` | **2.9677** |
| shipped core closing period | `docs/44` 5.3: 16.30 ns, 61.3 MHz | **16.30 ns, 61.3 MHz** |
| `soc_bus` | `docs/40` 9: 808 / 48 / 9,688.29 | **9,688.2912** |
| `soc_apb_bridge` | `docs/39` 6.1: 201 / 94 / 6,437.49 | **6,437.4912** |
| `soc_uart` | `docs/39` 6.1: 241 / 52 / 4,359.78 | **4,359.7764** |
| `soc_wdog` with `tmr_ev_o` | `docs/44` 7.2: 1,035 / 131 / 15,579.7614 | **15,579.7614** |
| `soc_busstat` | `docs/44` 7.2: 442 / 72 / 7,060.5486 | **7,060.5486** |

**[fact for every row]**

### 4.3 And the two that did not, which is the more useful half

`soc_clint` and `soc_fabric_meas` do **not** reproduce:

| Block | Published | Measured today |
|---|---:|---:|
| `soc_clint` | `docs/40` 9: 1,038 / 163 / **16,683.48** | 1,043 / 163 / **16,712.8164** |
| `soc_fabric_meas`, five ports | `docs/40` 9: 1,006 / 142 / **16,229.24** | 1,027 / 142 / **16,379.9874** |

**[fact]**

Neither block's source has changed. `soc_clint.v` was last touched at
`dbbef96`, the commit that published the number **[fact, `git log`]**.
`soc_fabric_meas` is a generated wrapper containing exactly `soc_bus`
and `soc_apb_bridge`, and the wrapper text is **byte-identical** to the
one `dbbef96` generated, and both of its contents reproduce their own
published numbers exactly (section 4.2) **[fact]**.

**What changed is the source list.** `flow/syn_soc.sh` reads every SoC
block into the design and then selects a top; `docs/44` added
`soc_busstat.v`, `soc_tmr_bank.v` and `tmr_voter.v` to that list, and
`soc_wdog.v` and `soc_gptimer.v` have themselves been rewritten across
`docs/41`, `docs/43` and `docs/44`. Restoring the list:

| Configuration | `soc_clint` | `soc_fabric_meas` |
|---|---:|---:|
| today's list | 16,712.8164 | 16,379.9874 |
| minus `soc_busstat.v` | 16,701.8166 | 16,379.9874 |
| minus `soc_busstat.v`, `soc_tmr_bank.v`, `tmr_voter.v` | **16,683.4836** | 16,379.9874 |
| the whole of `docs/40`'s list, `soc_wdog.v` and `soc_gptimer.v` at `dbbef96` | — | **16,229.2410** |

**[fact, seven re-syntheses across the two blocks. `soc_bus` measures
9,688.2912 in all three configurations it was re-measured in, which is
the control: a block that reproduces does so in every one of them.]**

Both published numbers come back **exactly**, and the cause is now a
measurement rather than a hypothesis:

> **A block's measured area under `flow/syn_soc.sh` is a function of the
> whole source list and not only of the block.** Reading three files
> `soc_clint` does not instantiate makes it **29.3328 um2 and 5 cells**
> bigger. Editing two files `soc_fabric_meas` does not instantiate makes
> it **150.7464 um2 and 21 cells** bigger, 0.93 % **[estimate,
> differences of measurements]**.

This is `docs/44` section 5.2's mapper noise, at block scale, with an
unambiguous cause and a reproducible handle on it. It is not a defect in
`syn_soc.sh` — Yosys is entitled to map a design differently when the
design it was given is different — and it is **not a reason to distrust
the per-block numbers**, each of which was correct against the tree it
was measured on. It is a reason to stop treating them as properties of
the block.

**Two consequences, stated rather than left implied.**

- **Every per-block area in `docs/39`, `docs/40`, `docs/41`, `docs/43`
  and `docs/44` reproduces only against the file list as it stood on the
  day**, and the ones that reproduce today do so because they happen to
  be insensitive, not because they are guaranteed to be.
- **`soc_pnp` and `soc_apb_pnp` do not reproduce `docs/39` either**
  — 2,585.3310 against 2,610.51 and 905.2722 against 930.67 **[fact]** —
  and they have a second cause on top of this one: their contents are
  *generated*, and `regmap/memmap.yaml` moved BUSSTAT from `reserved` to
  `implemented` in `docs/44`, which changes one line of
  `hw/soc/rtl/soc_pnp_rom.vh` **[fact, `git diff cea5723`]**. That is a
  design change and not drift. The two causes are not separated here and
  no attempt is made to; section 8 carries it.

---

## 5. Does it elaborate?

**Yes, at the first attempt, with no edit to any RTL file.**

```
read_liberty -lib <sg13g2 typ>
read_verilog -defer hw/soc/rtl/prim_clock_gating.v
read_verilog -defer <36 Ibex sources, IBEX_REGFILE=secded IBEX_FAULT_PORT=1>
read_verilog -I hw/soc/rtl -defer <10 SoC blocks + hw/rtl/tmr_voter.v>
read_verilog -I hw/soc/rtl -defer hw/soc/rtl/soc_mem.v
read_verilog -I hw/soc/rtl -defer hw/soc/rtl/soc_top.v
hierarchy -check -top soc_top
```

**88.96 s, 737.39 MB peak, exit 0** **[fact,
`hw/soc/out/s45-elab/syn.log`, `SOC_ELAB_ONLY=1 SOC_MEM=array`]**. Eleven
submodules resolved, 4,118 cells at RTL level, and **17 warnings of which every one is "Replacing memory … with
list of registers"** **[fact]** — Ibex's own PMP and MHPM register
files, the GPTIMER's per-timer arrays, `soc_bus`'s response queues, and
the two memories of section 3.

**No unresolved reference. No width mismatch. No multiply-driven net.**
The honest expectation was the opposite — a top level that has never
been elaborated as one design routinely does not — and the reason it
holds here is worth naming rather than being modest about: every block
under `hw/soc/rtl/` has been elaborated by `flow/sim_soc.sh` for Icarus
and by the cocotb suites since `docs/39`, and the whole SoC is simulated
end to end on every one of `docs/40`, `docs/41`, `docs/43` and
`docs/44`'s 185,443-cycle runs. **What had never been done was
synthesis, not elaboration**, and this is the difference between the two
showing up as a non-event.

**The one coupling that does bite, and it bites correctly.** With
`IBEX_FAULT_PORT=0` the build stops at elaboration with

```
ERROR: Module `$paramod…\ibex_top' referenced in module `soc_top' in
cell `u_ibex' does not have a port named 'rf_ecc_err_o'.
```

**[fact]**, which is exactly what `docs/44` section 4.3 cost 4 said would
happen and is the first time it has been demonstrated at the top level.

---

## 6. Measured area

Same recipe as `docs/38` section 8.1, `docs/40` section 9, `docs/41`
section 6.5, `docs/43` section 7.1 and `docs/44` section 7: Yosys
`stat -liberty` on `ihp-sg13g2` typical, `abc` at a 20 ns delay target
with `sg13g2_buf_4` driving and 5 fF of load, deferred flatten. Gate
equivalent = `sg13g2_nand2_1` = 7.2576 um2. `sw/tests` asserts that the
three flows still write the same abc constraint, because a whole-design
number measured a different way could not be compared with the per-block
numbers it is supposed to compose from.

### 6.1 The whole design

| Configuration | Cells | Flops | Area, um2 | kGE |
|---|---:|---:|---:|---:|
| upstream register file, memories blackboxed | 24,177 | 2,804 | **348,293.4336** | 47.990 |
| **as shipped, memories blackboxed** | **27,696** | **3,077** | **392,932.8900** | **54.141** |
| upstream register file, macro stand-ins | 24,844 | 2,967 | 353,800.5534 | 48.749 |
| as shipped, macro stand-ins | 27,705 | 3,240 | 400,199.5242 | 55.142 |

**[fact]**. The blackboxed rows' cell counts include the two zero-area
`soc_mem` instances, so the shipped design is **27,694 standard cells**.

**The stand-ins cost 9,133.6896 um2** — 5,891.3568 for the RAM and
3,242.3328 for the ROM, read out of the hierarchical build's per-module
report **[fact]** — and **that number is not part of any design**. It is
quoted only so a reader can see what the difference between rows 2 and 4
is made of. The difference itself is 7,266.6342 and not 9,133.6896,
because the mapper does not produce the same netlist twice; section 4.3
is the same effect.

> **The shipped SoC is 392,932.8900 um2 of standard cells, 54.141 kGE,
> plus two SRAM macros this project does not have yet** **[fact]**.

### 6.2 Does it compose?

Every block re-measured in this session, on today's source list, so that
the sum and the whole come from one afternoon:

| Block | Cells | Flops | Area, um2 |
|---|---:|---:|---:|
| `ibex_top`, as shipped | 22,338 | 2,328 | 316,051.6590 |
| `soc_bus` | 808 | 48 | 9,688.2912 |
| `soc_apb_bridge` | 201 | 94 | 6,437.4912 |
| `soc_uart` | 241 | 52 | 4,359.7764 |
| `soc_pnp` | 152 | 28 | 2,585.3310 |
| `soc_apb_pnp` | 100 | 0 | 905.2722 |
| `soc_clint` | 1,043 | 163 | 16,712.8164 |
| `soc_gptimer`, watchdog included | 2,205 | 300 | 33,528.0708 |
| `soc_busstat` | 442 | 72 | 7,060.5486 |
| **sum of the parts** | **27,530** | **3,085** | **397,329.2568** |
| **the whole design** | 27,694 | 3,077 | **392,932.8900** |

**[fact for every measured row; the two totals are arithmetic on them]**

> **The whole is 4,396.3668 um2 smaller than the sum of its parts,
> −1.11 %** **[estimate, the difference of two measurements]**. It is
> also **8 flip-flops smaller**, and it additionally contains `soc_top`'s
> own logic — the reset synchroniser, the APB slot decode, the fast
> interrupt vector and the peripheral read multiplexer — which the parts
> do not. Counting that at the 1,416.3282 um2 section 6.3 measures makes
> the gap **−5,812.6950, −1.46 %**.

**Read that as a bound and not as a saving.** Flattening does give the
optimiser opportunities the hierarchical builds denied it — the constant
`cheriot_enable_i`, the unconnected `crash_dump_o` and shadow ports, the
tied-off scramble interface — and section 6.3 measures one of those
directly. But 1.1 % is the same order as the *noise* section 4.3 just
measured on a block nobody touched, so **the honest statement is that
the parts compose to within about one and a half per cent and that this
document cannot resolve which way the small residual goes.**

The flip-flop count is the sharper half, because flip-flops do not have
mapping noise: **3,085 against 3,077, a difference of 8, in a design of
three thousand** **[fact]**. `soc_top`'s own reset synchroniser adds two
of its own, so on a like-for-like basis the flattened design holds **ten
fewer flip-flops than its parts do**. **This document does not attribute
those ten.** What it can say is where they are not lost: the
hierarchical build of section 6.3 holds **every block at exactly its
standalone flip-flop count** — 2,328 in `ibex_top`, 300 across
`soc_gptimer` and its three TMR banks, 163, 94, 72, 52, 48 and 28 in the
rest **[fact, a census of the netlist by module]** — so the ten go to
optimisation across the block boundaries and to nothing else.

### 6.3 The blocks inside the integrated design

A second build holds `soc_top`'s direct children as hierarchy
boundaries — `flatten` skips a module carrying `keep_hierarchy`, so each
block is still flattened internally and only the top-level boundaries
survive. It is a **diagnostic and not the measurement**: a kept boundary
blocks constant propagation across it, so the netlist it produces is not
the netlist section 6.1 measures.

| Block, inside `soc_top` | Area, um2 | Standalone, same session | Difference |
|---|---:|---:|---:|
| `ibex_top` | **311,583.0564** | 316,051.6590 | **−4,468.6026, −1.41 %** |
| `soc_gptimer` + its three TMR banks | 33,317.9028 | 33,528.0708 | −210.1680 |
| `soc_clint` | 16,729.7130 | 16,712.8164 | +16.8966 |
| `soc_bus` | 9,826.2612 | 9,688.2912 | +137.9700 |
| `soc_busstat` | 6,800.7492 | 7,060.5486 | −259.7994 |
| `soc_apb_bridge` | 6,437.4912 | 6,437.4912 | **0.0000** |
| `soc_uart` | 4,397.8788 | 4,359.7764 | +38.1024 |
| `soc_pnp` | 2,585.3310 | 2,585.3310 | **0.0000** |
| `soc_apb_pnp` | 865.3932 | 905.2722 | −39.8790 |
| `soc_mem` stand-in, RAM | 5,891.3568 | — | — |
| `soc_mem` stand-in, ROM | 3,242.3328 | — | — |
| **`soc_top`'s own glue** | **1,416.3282** | — | — |
| whole design, this build, flattened | **402,788.9754** | — | — |

**[fact]**. The per-module areas sum to 403,093.7946 and the flattened
total is 402,788.9754; the 304.8192 um2 of difference is what the final
`opt_clean -purge` removes across the released boundaries **[fact]**.

**Two blocks come out exactly the same size inside the SoC as they do
alone, and seven do not**, by between 17 and 260 um2, in both
directions. That is the noise of section 4.3 again and none of it is a
cost or a saving of anything.

**The core is 1.41 % smaller inside the SoC**, and that one is larger
than the rest. With a kept boundary the constants `soc_top.v` drives —
`cheriot_enable_i`, `hart_id_i`, `boot_addr_i`, `test_en_i`, the
scramble ports — cannot propagate into it, so this is **not** a
measurement of what the tie-offs buy; the flattened build of section 6.1
is where they are cashed. It is one more instance of the same mapper
sensitivity, on the largest block, where 1.4 % is 4,468 um2.

**`soc_top`'s own glue is 1,416.3282 um2**, 0.35 % of the design: the
two-flop reset synchroniser, the four-way APB slot decode and its
default-error path, the fifteen-bit interrupt vector and the peripheral
read multiplexer. **Nothing in this repository had ever measured it**,
because it is the one piece of logic that exists only at the top.

### 6.4 What the protection costs, measured at SoC scale for the first time

Rows 1 and 2 of section 6.1 differ in one thing: `IBEX_REGFILE`.

> **The register-file protection costs +44,639.4564 um2 at SoC scale,
> +12.82 %, and +273 flip-flops** **[estimate, the difference of two
> measurements]**.
>
> `docs/44` section 7.1 measured **+40,369.0392 um2, +14.64 %, and +222
> flip-flops** at core scale.

The two are not in conflict and the difference is exactly accountable.
**+273 − 222 = 51 flip-flops, and 51 = 3 × 16 + 3**: `soc_busstat`'s
`CNT_RFSEC`, `CNT_RFRD` and `CNT_RFDED`, sixteen bits each, and their
three sticky bits. With upstream's register file the fault port is tied
to zero — `flow/ibex_fault_port.py` adds it and drives it with zero at
`IBEX_REGFILE=upstream`, deliberately, so the isolation builds keep
working — and three of `soc_busstat`'s four counters become constant and
are deleted **[fact, the two flip-flop counts]**.

> **A measurement of the core alone cannot see the telemetry that exists
> only because the core has something to report.** `docs/44` section 7.2
> measured `soc_busstat` at 7,060.5486 um2 as a block and called the
> whole telemetry 12,117.1302; **at SoC scale 4,270.4172 um2 of that
> block is attributable to the protection rather than to the block**
> **[estimate, 44,639.4564 − 40,369.0392]**, and the rest — `CNT_TMRERR`,
> the enables, the APB interface — is not.

The percentage moves the other way from the absolute, and that is
arithmetic and not a finding: +12.82 % of a 348,293 um2 SoC is a larger
number than +14.64 % of a 275,683 um2 core, because the denominator
grew.

---

## 7. Measured timing

`flow/sta_soc_top.sh`: OpenSTA 3.1.0, all three `sg13g2` corners, the 5 %
derate written as a float, `sta/ibex.sdc.in` **unedited** — a clock on
`clk_i`, 20 % IO delay on every other port, a `sg13g2_buf_4` driver, 6 fF
of load, 0.25 ns of uncertainty, 0.15 ns of transition, ideal clocks.
Nothing in that file names an Ibex port; it is LibreLane's `base.sdc`
with the PDK defaults substituted in, and using it unchanged is what
makes these numbers comparable with `docs/38`'s, `docs/43`'s and
`docs/44`'s.

**There is no tie-off file here, and that is the point of the exercise.**
`sta/ibex_tieoffs.sdc` exists because `flow/sta_ibex.sh` times `ibex_top`
standalone, where `cheriot_enable_i` is a free primary input that
`soc_top.v` in fact drives with a constant. At this level it is not a
port at all and the synthesiser has already propagated the constant.
There is nothing left to case-analyse — and that is measured rather than
assumed: **`ibex_top` synthesised standalone has 32 lines of netlist
naming `cheriot` or `trvk`, and the whole-design netlist has zero**
**[fact, `grep -ciE 'cheriot|trvk'` on the two `.sta.v` files]**. The
paths that
produced every worst-case slack in `docs/38`, `docs/43` and `docs/44`
are not in this design to be case-analysed away.

### 7.1 The whole design as synthesised does not close, and the reason is one flip-flop

```
  corner  setup      hold       | setup_sync setup_async
  typ    -33.7393   -0.0442    | -33.7393   -29.0393
  slow   -60.6191    0.0579    | -60.6191   -53.3681
  fast   -16.0666   -0.1091    | -16.0666   -12.9362
VERDICT soc_top period=20 ns NOT_MET: setup(-60.6191,slow) hold(-0.1091,fast)
```

**[fact, `hw/soc/out/s45-stub/slack.rpt`]**

The worst synchronous and the worst asynchronous path have the **same
startpoint**:

```
Startpoint: _51474_ (rising edge-triggered flip-flop clocked by clk_i)
   0.0000    0.0000 ^ _51474_/CLK (sg13g2_dfrbpq_1)
  58.9033   58.9033 ^ _51474_/Q (sg13g2_dfrbpq_1)
```

**[fact, `path_slow_setup_sync.rpt` and `path_slow_setup_async.rpt`]**

`_51474_` is

```
  sg13g2_dfrbpq_1 _51474_ (
    .CLK(clk_i), .D(\rst_sync[0] ), .Q(rst_sys_n), .RESET_B(rst_raw_n) );
```

**[fact, the netlist]** — the second stage of `soc_top.v`'s reset
synchroniser, and `rst_sys_n` is the system reset the whole SoC runs on.

### 7.2 The reset tree, and which stage's problem it is

| Net | Reset pins driven | Other pins | Driver | Delay, slow |
|---|---:|---:|---|---:|
| `rst_sys_n`, system | **2,766** | 2 | `sg13g2_dfrbpq_1`, `rst_sync[1]` | **58.9033 ns** |
| `rst_ni`, power-on | **199** | 1 | input port, `set_driving_cell sg13g2_buf_4` | not binding |
| `rst_ni` in `docs/44`'s `ibex_top` alone | 2,328 | — | input port, `set_driving_cell sg13g2_buf_4` | 10.9223 ns |
| `rst_ni` in `docs/38`'s `small-pmp-sec` | 1,447 | — | one `sg13g2_mux2_1` | 30.85 ns |

**[fact for the first two rows, counted in the netlist; rows 3 and 4 are
quoted from the documents named]**

**It is the same class of artefact `docs/38` section 8.6 and `docs/44`
section 5.3 both found — an unbuffered high-fanout net in a netlist that
has not been through a resizer — and it is worse here for a structural
reason and not only a scale one.** 2,766 pins is 1.19 times 2,328, and
58.9033 ns is 5.39 times 10.9223. The extra factor is the driver:
`docs/44`'s net was a **primary input**, which the SDC gives a
`sg13g2_buf_4`, and this one is the **Q of the weakest flip-flop in the
library**. The design has to synchronise its own reset deassertion —
`soc_top.v`'s reset section says why, and `soc_wdog.v` W4 is the
requirement behind it — so at the top level the largest net in the SoC is
driven by a cell nobody chose for its drive strength.

**Whose problem is it?** Place-and-route's, and this document does not
soften that: a reset tree is what place-and-route builds, nothing under
`hw/soc/` has been through it, and `docs/38` section 10 item 3 has
carried the obligation since the core was brought up. Two things are
nevertheless new.

**First, the number is now large enough that no plausible buffering
makes the check pass by itself.** Scaling `docs/44`'s measured 10.9223 ns
for a `sg13g2_buf_4` into 2,766 pins instead of 2,328 gives about
**13.0 ns** **[estimate, linear in fanout, which is the wrong model for
a tree and is quoted only as an order]** — still two thirds of a 20 ns
period on one net. **A tree, not a bigger driver, is the answer**, and
that is a floorplan input rather than an SDC one.

**Second, and this is the part `docs/44` could not have seen: at the top
level the unbuffered reset poisons the SYNCHRONOUS group too.** In
`ibex_top` alone the binding check was the asynchronous recovery check
and the datapath was clear of it. Here `setup_sync` is −60.6191 and
`setup_async` is −53.3681 — **the synchronous group is the worse of the
two** — because `rst_sys_n` has two data sinks as well as 2,766 reset
pins, and they are these:

```verilog
// soc_bus.v
wire can_issue_i = rst_ni && mi_req_i && …
wire can_issue_d = rst_ni && md_req_i && …
```

`soc_bus.v`'s own header argues for that gating at length, and the
argument is good: without it a master driving `req` during reset has a
transaction accepted by a slave while the response accounting is held at
zero, and the reply after reset release pops a queue that never recorded
the request. It was found by the cocotb suite driving requests during
reset, which is why that test exists.

> **A correctness gate in the fabric put the SoC's largest unbuffered net
> into the combinational request path.** Neither decision is wrong and
> the composition of the two is the finding: `soc_bus` alone could not
> have shown it, because alone its `rst_ni` is an input port and this SDC
> gives every input port a `sg13g2_buf_4` — and in any case **no SoC
> block has ever been through STA at all**, which `docs/40` section 9
> states of its own numbers in as many words,
> and `ibex_top` alone cannot see it because it has no fabric.

### 7.3 With the reset trees treated as built

`hw/soc/sta/soc_top_reset_cut.sdc` false-paths both reset nets.
`SOC_RESET_CUT=1` applies it and the default is off, so the unmodified
recipe is reported beside it — the same discipline `docs/44` section 5.1
uses for its tie-offs, and for the same reason: **neither recipe is the
truth and both are reported**.

```
  corner  setup      hold       | setup_sync setup_async
  typ     8.7347    -0.0442    | 8.7347     18.4590
  slow    1.8079     0.0579    | 1.8079     17.7198
  fast   12.6284    -0.1091    | 12.6284    18.8949
VERDICT soc_top period=20 ns NOT_MET: hold(-0.1091,fast)
```

**[fact, `hw/soc/out/s45-stub-rcut/slack.rpt`]**

> **Setup is met at all three corners with +1.8079 ns at the slow
> corner.** `docs/44` section 5.5 declined `SYNPRE` partly because the
> shipped core met 20 ns with +1.5514 ns; **the whole design meets it
> with +1.8079**, and that part of the argument survives integration.

**What the cut does and does not measure.** It measures the design
**supposing** the reset trees have been built. It is not a claim that
they have been, not a prediction of what they will cost, and it does not
close the check — a reset tree has its own recovery check and buffering
it changes the number rather than removing the obligation. Both nets are
cut and not only the large one, so that the file means one thing rather
than two; `rst_ni` was nowhere near binding and cutting it changes
nothing that was measured.

### 7.4 Where the real critical path is

**The flattened build**, with the named nets the netlist still carries as
waypoints:

| Arrival, ns | Waypoint |
|---:|---|
| 0.3941 | `u_ibex.gen_regfile_ff.register_file_i.raddr_a_i[4]` — **the startpoint** |
| 1.3042 | `…register_file_i.g_plain_rf.g_rf_flops[4].rf_reg_q[19]` |
| 11.8150 | `u_bus.lock_d[2]` — **it has left the core** |
| 12.4142 | the `soc_bus` gate whose other input is `rst_sys_n` |
| 14.7994 | `u_bus.last_was_d` |
| 15.8844 | `u_rom.gnt_o` — **through a memory's combinational grant** |
| 16.2646 | `u_pnp.gnt_o` |
| 17.7670 | `u_ibex.crash_dump_o[66]` — **the endpoint, back inside the core** |

**[fact, `hw/soc/out/s45-stub-rcut/path_slow_setup_sync.rpt` resolved
against the netlist]**. Between 1.3042 and 11.8150 the netlist carries no
public net at all — `abc`'s internal nodes are private — so that stretch
is bracketed rather than attributed.

**The hierarchical build**, which is a different netlist mapped
differently and whose instance names carry the block, attributes it
exactly:

| Arrival, ns | Block |
|---:|---|
| 0.0000 – 12.4256 | `u_ibex`, from `…register_file_i.raddr_b_i[1]` |
| 12.4256 – 15.4773 | `u_bus` |
| 15.4773 – 17.8793 | `u_clint`, ending at a CLINT flip-flop |

**[fact, `hw/soc/out/s45-hier/path_slow_setup_sync.rpt`]**, slack
+1.6957 against the flattened build's +1.8079 — 0.1122 ns apart, inside
`docs/44`'s measured noise.

Two things follow, and the first is the one this document exists for.

> **The whole-design critical path starts at the register file's
> read-address register, in two independently mapped netlists.** In the
> flattened build it is `raddr_a_i[4]`, in the hierarchical build
> `raddr_b_i[1]`; different bit, different port, same structure. That is
> the structure `docs/43` section 7.4 named:
>
> > The decoder sits on the register read path and the register read
> > path feeds the ALU, so this is the one place in the design where a
> > correction mechanism is **in series** with the thing it protects
>
> **`docs/44` section 5.1's correction is untouched and is not being
> walked back.** That sentence was attached to two slack figures which
> came from a path starting at `cheriot_enable_i[0]`, and it still is.
> What is new is that at the top level, where that input is a constant
> the synthesiser has folded, **the sentence is what the measurement
> shows.** `docs/43` was right about its design and wrong about its
> instrument, and it took two documents to establish both halves.

> **And the path is a cross-block path.** 12.43 ns of it is inside
> `u_ibex` and 5.45 ns is in the fabric and the CLINT **[fact]**. No
> per-block synthesis in this repository contains it: `flow/syn_ibex.sh`
> stops at the core's ports and `flow/syn_soc.sh` never sees the core.
> **This is what "the per-block figures may not compose" looks like when
> it is measured**, and it is the whole of the 1.90 ns of section 7.6.

### 7.5 The worst hold path is the reset synchroniser

```
Startpoint: _51473_   Endpoint: _51474_   Path Group: clk_i
            -0.1091   slack (VIOLATED)
```

`_51473_` drives `rst_sync[0]` and `_51474_` drives `rst_sys_n` **[fact,
the netlist]**: the two stages of `soc_top.v`'s reset synchroniser, back
to back with no logic between them, which is the shortest path the design
has.

This is `docs/38` section 8.3's finding and not a new one, and its four
tests still pass: there is no placement, no routing, no clock tree and no
hold-fixing buffer; the SDC charges **0.25 ns of clock uncertainty**
against the hold check as a stand-in for skew that has not been built,
and −0.1091 is 44 % of it; the violation is **identical at every period
probed** — −0.1091 at 20 ns, at 18.20, at 13.97 **[fact]** — which is a
fixed short path plus a fixed uncertainty and not a period-dependent
property; and the pilot closes hold in place-and-route with
`PL_RESIZER_HOLD_SLACK_MARGIN 0.1`.

**Worth one sentence anyway:** the hold triple −0.0442 / +0.0579 /
−0.1091 is identical to four decimal places at all three corners to
`docs/38` section 8.6's `small-pmp-sec` row **[fact, comparing two
tables]**. That is consistent with both designs' worst hold path being
the same structure — two reset flip-flops with nothing between them,
whose slack depends on the library and the uncertainty and on nothing
else — and it is **stated as an observation, not as a verified
identity**: `docs/38`'s netlist was not re-examined for this document.

### 7.6 Frequency

Bisection on the closing period. `docs/44` section 5.3a measured that
this flow's netlist does not depend on the period ABC is given — all
eight probes of its baseline sweep produced a byte-identical netlist —
so the bisection is a linear solve on a fixed netlist and needs no
re-synthesis. **That correction is used here rather than re-argued.**

| Configuration | Closes setup at | Frequency | What binds it |
|---|---:|---:|---|
| **`soc_top` as synthesised, as shipped** | **80.62 ns** | **12.4 MHz** | `rst_sys_n`, in the synchronous group |
| `soc_top`, reset trees cut, upstream register file | **13.97 ns** | **71.6 MHz** | logic |
| **`soc_top`, reset trees cut, as shipped** | **18.20 ns** | **54.9 MHz** | logic |
| `ibex_top` alone, tie-offs, upstream — `docs/44` 5.3 | 12.80 ns | 78.1 MHz | logic |
| `ibex_top` alone, tie-offs, as shipped — `docs/44` 5.3 | 16.30 ns | 61.3 MHz | logic |

**[fact for the first three, bisected here. The `as shipped` row of
`docs/44`'s pair was re-bisected in this session and reproduces 16.30 ns
and 61.3 MHz exactly; its `upstream` row is quoted from that document and
was not re-run, so the 12.80 ns is the one number in this table this
session did not measure.]**

Three readings, in order of how much the evidence supports them.

> **1. Integration costs 1.90 ns of period and 6.4 MHz on the shipped
> design, and 1.17 ns and 6.5 MHz on the unprotected one** **[estimate,
> differences of measurements; three of the four bisections are this
> session's and the fourth is `docs/44`'s]**. Both are well outside the
> ~0.4 ns of noise `docs/44` section 5.2 measured, and section 7.4 says
> where the time goes: out of the core, through `soc_bus`, into a slave
> and back.

> **2. The cost of the register-file protection composes almost
> exactly.** 16.8 MHz measured on the core alone (78.1 → 61.3), **16.6
> MHz measured on the whole SoC** (71.6 → 54.9) **[estimate,
> differences of measurements]**. `docs/44` section 5.3 put it at
> "somewhere around 13 to 17 MHz" and declined to be more precise than
> its instrument allowed. It was right, and this is the independent
> check.

> **3. The headroom over the target is much thinner than the per-block
> numbers suggested.** The SoC's SDC period is 20 ns and `docs/09`'s
> estimate for a 130 nm RV32 core was 50–80 MHz. The core alone said
> 61.3 MHz, 22.6 % above 50; **the whole design says 54.9 MHz, 9.8 %
> above it** **[estimate, arithmetic on two measurements]** — and that is
> pre-layout, with no clock tree, no parasitics and no reset tree, on a
> project whose history moves these numbers **down** at layout
> (`docs/28`).

**What this does not do is reopen `docs/44` section 5.5's decision.**
That section declined `SYNPRE` — 1.8677 ns of recovery for 11.6 % of the
core — on the grounds that the 20 ns target was met with margin to
spare, and at the whole-design level the 20 ns target **is** met, with
+1.8079 ns. The decision stands on its own terms. What has changed is the
**reversal condition** it wrote down: "if a clock target above about
60 MHz is ever adopted". The design as a whole closes at 54.9 MHz, which
is **below** that threshold, so the condition is no longer about a future
target — it is about whether 50 MHz survives place-and-route. Section 9
item 1 is that.

### 7.7 What this instrument can resolve

`docs/44` section 5.2 measured this flow's whole-design setup slack as
having about **0.4 ns** of resolution, from two controlled pairs in which
a change provably off the critical path moved the reported slack by
0.1585 and 0.3988 ns. **Nothing here contradicts that and one thing
supports it**: the flattened and hierarchical builds of the same RTL, at
the same period, report +1.8079 and +1.6957 — **0.1122 ns apart on
designs that differ only in where the optimiser was allowed to work**
**[fact]**.

> **No timing delta in this document smaller than about 0.4 ns is
> claimed.** The three that are claimed are 1.90 ns, 1.17 ns and
> 4.23 ns, and they are 3 to 10 times the resolution. **Frequencies are
> quoted to one decimal because that is what the bisection's 0.01 ns
> probe produces; they should be read as ±1 MHz at these periods**
> **[estimate, 0.4 ns at 18 ns is 1.2 MHz]**.

Section 4.3 adds a second kind of imprecision this repository had not
measured before, and it is not the same one: **area** under
`flow/syn_soc.sh` moves by up to 0.93 % when files the block does not
instantiate are edited. Both are the mapper; only the timing one had a
number before today.

---

## 8. What this does NOT cover

Stated at length, because this repository has been bitten by a green
check read as wider than the thing it examined fourteen times —
`docs/28` 4.4a, `docs/34` 8.5, `docs/36` 3.3, `docs/38` 7.3 and 8.2,
`docs/39` 3, twice in `docs/40`, `docs/41` 8.4, `docs/42` 5.1,
`docs/43` 9.5 and 9.6, and `docs/44` 5.2's new shape, a measured delta
attributed to the wrong cause.

- **The memories are not in this design.** Every number here is measured
  across a boundary model, and section 3.2 lists the four things neither
  model reproduces. The one that bites hardest is that **a real SRAM
  macro's setup and clock-to-Q are much larger than a standard-cell
  flip-flop's**, so the paths into and out of the memories are
  optimistic here by an amount this document cannot bound. `u_rom.gnt_o`
  is on the flattened build's critical path (section 7.4), so this is
  not hypothetical.
- **The stub netlist is not functional and was not simulated.** It
  computes the wrong thing at the memory boundary on purpose. No
  behavioural claim in this document rests on it, and none is made.
  **No gate-level simulation of `soc_top` exists**, and until one does,
  "it synthesises" means the tool produced a netlist and not that the
  netlist is the design.
- **No place-and-route, and section 7 depends on that more than any
  previous document's timing did.** The binding check of the design as
  synthesised is an unbuffered 2,766-fanout net; the worst hold path is
  a two-flop chain against a 0.25 ns uncertainty stand-in; and the
  frequency that decides the part is 9.8 % above target before a clock
  tree exists. **Two of those three are artefacts layout removes, and the
  third is the one layout is expected to make worse.**
- **The reset cut is an assumption and is labelled as one.** It reports
  the design supposing the reset trees are built. It says nothing about
  what building them costs, and a built reset tree has a recovery check
  of its own that this document does not evaluate.
- **The per-block source-list finding is characterised, not bounded.**
  Section 4.3 measures 29.33 um2 on `soc_clint` and 150.75 on
  `soc_fabric_meas`. It does not establish an upper bound over blocks, it
  does not separate the two causes acting on `soc_pnp` and
  `soc_apb_pnp`, and it says nothing about whether timing numbers move
  the same way.
- **The hierarchical build is a diagnostic and its slack is not a
  result.** A kept boundary blocks constant propagation, so it times a
  different netlist. It is used for path attribution and per-block area
  and for nothing else.
- **Nothing here is re-verified functionally.** No cocotb suite, no
  formal job, no fault-injection campaign and no whole-SoC simulation was
  re-run for this document, because nothing in `hw/soc/rtl/` was
  modified. `docs/44` section 8.1's 22 checks and 185,443 cycles are the
  last behavioural evidence and they stand; **this document adds none.**
- **One clock, one corner set, one period target.** No multi-mode
  analysis, no test mode, no scan, no power estimate, and no area for the
  two SRAM macros the design needs and does not have.
- **`soc_top` has still never been placed or routed**, which is the
  sentence this document replaces `docs/44` section 10's last line with.

---

## 9. What the next block should be

1. **Place and route `soc_top`, or one block of it, and re-read section
   7.** `docs/44` section 11 item 4 already ranked this and every result
   here raises it. The design's binding check is a reset net that
   place-and-route builds; its worst hold path is a two-flop chain a
   resizer fixes; and its closing frequency is 9.8 % above target on a
   netlist with no clock tree. **Until something is placed, the honest
   summary of this document is "it synthesises, and the number that
   decides the part is not a synthesis number".**

2. **The two SRAM macros.** Section 3 is the first time the memory
   boundary has had to be modelled rather than excluded, and it made
   plain that the SoC has 72 KiB of memory represented by nothing. A
   macro has area, a floorplan, a power grid, setup and clock-to-Q that
   are worse than the stand-in's, and — for a part that claims fault
   tolerance — **no ECC**, which `soc_mem.v` names in its own header and
   `docs/38` section 7 already carries. This is now on the critical path
   for anything past synthesis.

3. **`mtime`.** `docs/41` section 7.4 ranked it first, `docs/43` section
   12 second, `docs/44` section 11 first again. It is the oldest open
   item in the SoC and has now lost to a more interesting document four
   times running. Section 6.3 adds one small argument for it:
   `soc_clint` measures 16,729.71 um2 inside the SoC, about 4 % of it,
   and **163 of the design's 3,077 flip-flops sit in the one block whose
   largest object is an unprotected 64-bit counter**.

4. **Decide whether `flow/syn_soc.sh` should read only what the block
   needs.** Section 4.3 shows that it does not measure the block. The fix
   is small — derive the source list from the top rather than reading
   everything — and the cost of the fix is that **every per-block number
   in five documents would then be reproducible against a different
   recipe from the one that produced it.** That is a decision about
   comparability and not a tidy-up, which is why it is proposed rather
   than done here.

5. **A gate-level simulation of `soc_top`.** `docs/44` section 11 item 3
   asked for a gate-level *campaign* on the core; this makes the plainer
   version available and necessary. A netlist now exists; nothing has
   ever executed it. The memory boundary is the obstacle and it is the
   same obstacle as item 2.

6. **Give `campaign.py --directed` the `--jobs` it already accepts** —
   `docs/44` section 11 item 6, untouched here and still true.

---

## 10. Corrections to earlier documents

- **`docs/41` section 10 item 7**, **`docs/43` section 11**'s inheritance
  of it, and **`docs/44` section 10**'s last line — "`soc_top.v` has
  never been synthesised as one design" — are **closed**. The replacement
  obligation is that it has never been placed or routed, and it is
  section 8's last bullet and section 9 item 1.
- **`docs/40` section 9's `soc_clint` row** (1,038 cells, 16,683.48 um2)
  and **`soc_fabric_meas`, five ports** (1,006 cells, 16,229.24 um2) are
  **not reproducible against the current tree** and are **not wrong**.
  Section 4.3 reproduces both exactly against the source list those
  numbers were measured with, and identifies the cause: `flow/syn_soc.sh`
  reads every SoC block into the design, so a block's measured area moves
  when a file it does not instantiate is edited. The same applies to
  **`docs/39` section 6.1's `soc_pnp` and `soc_apb_pnp` rows**, which
  have a second cause as well — their contents are generated and
  `regmap/memmap.yaml` changed at `docs/44`.
- **`docs/40` section 9's `soc_gptimer` row** (1,500 cells, 23,733.94
  um2) was already superseded by `docs/41` section 6.5, and that
  supersession is itself two documents stale: the block measures 2,205
  cells and 33,528.0708 um2 today, because `docs/43` added W7 and W8 and
  `docs/44` added `tmr_ev_o`. Section 6.2 uses the current number.
- **`docs/43` section 7.4's sentence** — "the decoder sits on the
  register read path and the register read path feeds the ALU" — is
  **what the whole-design critical path shows**, in two independently
  mapped netlists. **`docs/44` section 5.1's correction of the numbers
  under that sentence stands unchanged**; this is a correction to the
  standing of the sentence and not to the correction.
- **`docs/44` section 5.3's "somewhere around 13 to 17 MHz" for the
  protection's logic-limited cost** is confirmed at the whole-design
  level: 16.6 MHz. The estimate was well calibrated and is now measured
  twice.
- **`docs/44` section 5.5's reversal condition** — "if a clock target
  above about 60 MHz is ever adopted" — should be read against 54.9 MHz
  and not 61.3. The **decision** to decline `SYNPRE` is unaffected: the
  20 ns target is met at the whole-design level with +1.8079 ns. The
  **condition** is now about whether 50 MHz survives place-and-route
  rather than about a future target.
- **`docs/44` section 7.2's "the whole telemetry costs 12,117.1302
  um2"** is correct as a sum of block measurements and understates what
  the *protection* costs at SoC scale by 4,270.4172 um2, because three of
  `soc_busstat`'s four counters exist only when the register file has
  something to report. Section 6.4.
- **`docs/44` section 4.3 cost 4** — "a flow that forgets
  `IBEX_FAULT_PORT=1` fails at elaboration with the port's name in the
  message" — is demonstrated at the top level for the first time, in
  section 5.
- **`docs/38` section 8.3's characterisation of the pre-layout hold
  violation** applies unchanged to `soc_top`, and section 7.5 re-runs all
  four of its tests on the new design rather than assuming them.

---

## 11. Files touched

`docs/34` section 2 pins the pilot by git blob hash of the files in
`hw/rtl/` and section 5 lists the flow configs. **Nothing in either set
is modified** **[fact]**.

| File | Change |
|---|---|
| `hw/soc/flow/syn_soc_top.sh` | new — `soc_top` synthesised whole |
| `hw/soc/flow/sta_soc_top.sh` | new — the same three-corner recipe at the top |
| `hw/soc/flow/sta_verdict.awk` | new — the verdict rule, moved out of `sta_ibex.sh` |
| `hw/soc/sta/soc_top_reset_cut.sdc` | new — the two reset nets false-pathed, default off |
| `hw/soc/sta/ibex_sta.tcl.in` | `@TOP@` instead of a literal `ibex_top` |
| `hw/soc/flow/sta_ibex.sh` | substitutes `@TOP@`; calls the shared verdict rule |
| `hw/soc/flow/syn_soc.sh` | a header note only: what section 4.3 measured about its own numbers, where a reader of that script will find it |
| `sw/tests/test_soc_synthesis_guards.py` | section 5 — four checks; and the header note about what it does not cover, corrected |
| `docs/45-soc-top-synthesis.md` | this document |
| `docs/00-index.md` | one row |

**No file under `hw/soc/rtl/` was modified**, and `hw/soc/ext`,
`hw/soc/gen`, `hw/soc/genp`, `hw/soc/tools` and `hw/soc/out` are
gitignored, by the rule `docs/38` section 11 already applies: fetched or
generated, never vendored.

---

## 12. Reproducing this

```
make -f hw/soc/tools.soc.mk fetch-ibex fetch-sv2v
hw/soc/flow/sv2v_ibex.sh hw/soc/ext/ibex hw/soc/gen \
                         hw/soc/tools/sv2v-Linux/sv2v

# ---- section 4: the instrument, before anything is claimed to move ----
for d in h44-base h44-doc43 h44-port; do
  hw/soc/flow/sta_ibex.sh small-pmp 20 hw/soc/out/$d      # byte-identical
done
IBEX_REGFILE=secded IBEX_FAULT_PORT=1 \
  hw/soc/flow/syn_ibex.sh small-pmp 20 hw/soc/out/s45-ibex-shipped
md5sum hw/soc/out/s45-ibex-shipped/small-pmp/ibex_top.netlist.v \
       hw/soc/out/h44-port/small-pmp/ibex_top.netlist.v   # fa3c11ae...
SOC_TIEOFFS=1 hw/soc/flow/sta_ibex.sh small-pmp 20 hw/soc/out/h44-port
                                                         # setup_sync 2.9677

for m in soc_bus soc_apb_bridge soc_uart soc_pnp soc_apb_pnp soc_clint \
         soc_gptimer soc_wdog soc_busstat soc_fabric_meas; do
  hw/soc/flow/syn_soc.sh $m
done
# Section 4.3: docs/40's two numbers come back only with docs/40's list.
# Edit hw/soc/out/soc-syn/<block>/soc_syn.ys, remove soc_busstat.v,
# soc_tmr_bank.v and tmr_voter.v from the read_verilog line and the
# `attrmap -modattr -remove keep_hierarchy` line, and for
# soc_fabric_meas also point soc_wdog.v and soc_gptimer.v at
# `git show dbbef96:hw/soc/rtl/<file>`. Then re-run yosys on it.

# ---- sections 5 and 6: elaboration and area -------------------------
# Section 5, with the REAL memories. SOC_ELAB_ONLY=1 cuts the script
# after `hierarchy -check`, because what follows would be a synthesis of
# 589,824 registers.
SOC_ELAB_ONLY=1 SOC_MEM=array \
  hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s45-elab   # 88.96 s, 737 MB

# Section 3.1's measurement of why SOC_MEM=array stops there:
yosys -p "read_verilog -I hw/soc/rtl hw/soc/rtl/soc_mem.v; \
          chparam -set WORDS 16384 -set RO 0 soc_mem; \
          hierarchy -check -top soc_mem; proc; opt_clean; stat"
#   1,693.86 s, 2,767.05 MB, 376,841 cells, 16,384 32-bit $dff

SOC_MEM=blackbox hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s45-bb
                                     # 27,696 cells, 3,077 ff, 392,932.8900
IBEX_REGFILE=upstream SOC_MEM=blackbox \
  hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s45-bb-up
                                     # 24,177 cells, 2,804 ff, 348,293.4336
SOC_MEM=stub hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s45-stub
IBEX_REGFILE=upstream SOC_MEM=stub \
  hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s45-stub-up
SOC_MEM=stub SOC_KEEP_HIER=1 \
  hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s45-hier    # per-block areas
grep "Chip area for module" hw/soc/out/s45-hier/area.rpt

# The coupling of section 5, seen rather than argued:
IBEX_FAULT_PORT=0 SOC_MEM=blackbox hw/soc/flow/syn_soc_top.sh 20 /tmp/nofp
#   ERROR: ... does not have a port named 'rf_ecc_err_o'.

# ---- section 7: timing ----------------------------------------------
hw/soc/flow/sta_soc_top.sh 20 hw/soc/out/s45-stub        # -60.6191 slow
SOC_RESET_CUT=1 hw/soc/flow/sta_soc_top.sh 20 hw/soc/out/s45-stub
                                                         # +1.8079 slow
SOC_RESET_CUT=1 hw/soc/flow/sta_soc_top.sh 20 hw/soc/out/s45-stub-up
                                                         # +6.0357 slow
SOC_RESET_CUT=1 hw/soc/flow/sta_soc_top.sh 20 hw/soc/out/s45-hier

# The reset tree, counted rather than described:
grep -c "\.RESET_B(rst_sys_n)" hw/soc/out/s45-stub/soc_top.sta.v   # 2766
grep -c "\.RESET_B(rst_ni)"    hw/soc/out/s45-stub/soc_top.sta.v   # 199

# The bisection. docs/44 section 5.3a measured that this flow's netlist
# does not depend on the period, so this is STA only.
for cut in 0 1; do
  lo=8; hi=120
  for i in $(seq 12); do
    p=$(python3 -c "print(f'{($lo+$hi)/2:.2f}')")
    s=$(SOC_RESET_CUT=$cut hw/soc/flow/sta_soc_top.sh $p hw/soc/out/s45-stub \
        | awk '$1=="GATE" && $2=="setup_all"{print $3}')
    if [ "$(python3 -c "print(1 if $s>=0 else 0)")" = 1 ]; then hi=$p; else lo=$p; fi
  done
  echo "cut=$cut closes at $hi ns"        # 80.62 and 18.20
done

# ---- the guards ------------------------------------------------------
.venv/bin/python -m pytest sw/tests/test_soc_synthesis_guards.py    # 18 pass
```

`hw/soc/out/` and `hw/soc/genp/` are gitignored.
