# 50 — The register closes the macro path, and the part gets slower

`docs/49-synpre-and-the-binding-path.md` section 14 item 1 names this
block and section 11.1 is the arithmetic that motivates it:

> **AND THAT IS WHY ONE FLIP-FLOP, IN THE RIGHT PLACE, IS THE ONLY
> MECHANISM MEASURED ANYWHERE IN `docs/47`, `docs/48` OR THIS DOCUMENT
> THAT WOULD REACH 20 ns.** … **What it costs is not silicon, it is a
> cycle.**

**Both halves of that sentence are right, and this document is about the
second one.** The register was built, verified, hardened and signed off.
It does what `docs/49` predicted at the macro, completely: **of the 444
violating endpoints that `docs/47` launched from an SRAM macro's
`A_DOUT`, zero remain**, and the sign-off improves by **+0.7772 ns to
−2.4257 ns, 44.5917 MHz** — the first setup improvement in four documents
that is larger than this flow's measured noise.

**And the part gets slower.** The extra cycle costs **46,789 cycles on
the bring-up program, +25.23 %**, and **+25.72 %** on `docs/46`'s
supervisor. **The clock would have to reach 53.97 MHz for the part to do
the same work in the same time; it reaches 44.59.** At its own measured
clock the registered design takes **21.0 % longer in wall-clock time**,
and it would take **7.94 % longer even if it closed 20.000 ns exactly.**
**The recommendation is not to keep it**, with three stated reversal
conditions, and section 7.3 is the whole argument on one page.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
intended, with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by blob hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was modified;
`hw/openlane/checker_audit.py` and `hw/openlane/signoff_report.py` are
**read and run** and never written. Section 14 lists every file.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Does it close?** | **No. It closes at −2.4257 ns on 1,893 endpoints at `nom_slow_1p08V_125C`, 44.59 MHz**, against `docs/47`'s **−3.2029 on 2,003, 43.10 MHz**. The delta is **+0.7772 ns, which is OUTSIDE `docs/44`'s measured 0.4 ns of instrument noise and IS reported as an improvement** — the first setup improvement in `docs/47` to `docs/50` that is. **And not one violating endpoint is launched by a memory macro any more: 444 of them were, and now zero are.** Section 6 |
| **What does it cost in cycles?** | **185,443 → 232,232 on the bring-up program, +46,789, +25.23 %** **[fact]**, with all **22 checks passing, fail mask 0**, the watchdog escalation demo running its full ladder, and the console byte-identical for its first 587 characters. Sections 4 and 5 |
| **Where do the cycles go?** | **57.3 % to the data side and 43.0 % to instruction fetch**, measured by registering one memory at a time: RAM alone **+26,820**, ROM alone **+20,118**, both **+46,789** — the two are additive to **0.3 %**. Per access it is **0.9714 cycles per RAM response** and **0.1858 per ROM response**: a load stalls the pipeline outright, and Ibex's prefetch buffer hides **81 %** of the fetch latency **[estimate, measured deltas over measured response counts]**. Section 5.2 |
| **So is it worth it?** | **No, on every workload measured.** The part would have to close at **53.97 MHz** to run the bring-up program in the time `docs/47`'s 43.10 MHz design already runs it, and at **54.18 MHz** for `docs/46`'s supervisor. **Even a perfect 20.000 ns close — 50 MHz, the target — is 7.94 % SLOWER in wall-clock time than the design that misses it by 3.2 ns.** Section 7 |
| **What did the fabric need?** | **Nothing, and that is a measurement rather than a relief.** `soc_bus.v` is byte-identical to `docs/47`'s. Its protocol already allows a response "one or more cycles after the grant", its formal environment constrains slave response timing **not at all**, and its one accounting conservatism — refusing a grant in the cycle a response returns — **cannot ever fire in this SoC**, because Ibex's `NUM_REQS` is 2 and equals the fabric's `MAX_OUT`, so the core stops asking before the fabric stops granting. Measured at **zero cycles, in both configurations**, by a probe that is now part of the repository. Section 3 |
| **What was found that had nothing to do with this change?** | **`hw/soc/formal/soc_bus.sby` has been FAILING since `docs/47`, and no document noticed.** That document added `issue_en` to the fabric — a flop that keeps the request path closed for one cycle after reset release — and F9's two-cycle fairness bound has no room for it. The counterexample is at depth 3 and it is the sentence `soc_bus.v`'s own comment already wrote down. **F9 is extended, not relaxed**: the arbiter clause gains the precondition that the fabric is open, and a new clause bounds how long it may stay shut. Every other formal suite in `hw/soc/formal/` passes at HEAD, checked. Section 8.1 |
| Do the checkers still gate? | **17 of 19, the same as `docs/47`, `docs/48` and `docs/49`**, on the run that reports the improved setup AND the clean hold. `checker_audit.py` confirms `Checker.SetupViolations` and `Checker.HoldViolations` each examined **three corners** — the identical binding under which `full3` reported −3.2029 and −0.2015 and failed on both. Section 9 |
| What is new in verification? | **A cocotb suite for `soc_mem`, which had never had one** — 7 tests, run at **both** values of the parameter, with the latency **measured from the DUT** rather than trusted from the build; **7 of 7 at each**, and mutation-tested. **A two-cycle-memory test in the fabric suite**, 14 of 14. **Four new formal covers** that witness the two-cycle regime, 16 of 16 reached. **A guard file** with 6 tests. Sections 4 and 8 |
| What nearly went wrong | **The control was not byte-identical at first, and the cause was a term that folds to zero.** Section 2.2 |

---

## 2. Reproducing the instrument, and one new way it can lie

### 2.1 The published figures

| What | Published | Measured here |
|---|---|---|
| `SOC_MEM=sram` whole design | `docs/47` 6.3: **27,565 cells, 3,085 flip-flops, 396,177.6420 um2** | **27,565 / 3,085 / 396,177.6420** **[fact]** |
| the same netlist, byte for byte | `docs/49` 2 | **identical to `hw/soc/out/s47-sram/soc_top.netlist.v` up to three net names**, and identical after renaming them back — section 2.2 **[fact, `diff`]** |
| sign-off, slow corner | `docs/47` 8.2: **−3.2029 ns on 2,003 endpoints, 43.10 MHz** | **−3.2029 / 2,003**, `hw/openlane/signoff_report.py` on `full3` **[fact]** |
| post-CTS, before the timing resizer | `docs/47`/`docs/48`: **−10.7556** for `full2` | **−10.7556** **[fact]** |
| after global routing, post-GRT off | `docs/47`: **−6.8764** for `full2` | **−6.8764** **[fact]** |
| global-route wirelength | `docs/47`: **3,771,252 um** | **3,771,252** **[fact]** |
| `RepairDesignPostGPL`, `full2` | `docs/49` 5.1: **181 cap violations / 3,326 buffers in 2,396 nets** | **181 / 3,326 / 2,396**, and **70 slew violations**, which is new **[fact]** |
| the whole-SoC behavioural invariant | `docs/43` 9.1 and `docs/49` 9.2: 22 checks, fail mask 0, watchdog stage 1 at **174,128**, core asleep after **185,443**, **587** console characters, 0 framing errors | **every one** **[fact]** |
| **`docs/46`'s supervisor frame times** | `docs/46` 5: `kick_min = 2,118`, `kick_max = 4,456`; its section 1 ratio **2.104** | **2,120 / 4,458, ratio 2.1028** — two cycles out on each, 0.045 %, in the baseline and not in the change, and not chased. Section 7.1 **[fact]** |
| every formal suite under `hw/soc/formal/` except `soc_bus` | `docs/39` to `docs/44` | **apb, clint, busstat, wdog, wdogtmr, regfile: all tasks PASS at HEAD** **[fact]** |
| **`hw/soc/formal/soc_bus.sby`** | `docs/39`: bmc, prove, cover all PASS | **FAIL at HEAD**, section 8 **[fact]** |

### 2.2 The control cost three synthesis runs and the reason is worth the space

The rule since `docs/44` is that a knob at its default must reproduce the
netlist the previous document hardened. `MEM_RDREG` is a parameter of
`soc_top.v`, and at 0 the RTL is logically what it was — so the netlist
should have been byte-identical, and the first version was not: **27,837
cells and 397,241.7876 um2 against 27,565 and 396,177.6420, +272 cells
for a design that had not changed** **[fact]**.

The cause was localised by construction, one file at a time:

| build | cells | um2 |
|---|---:|---:|
| `docs/47`'s netlist | 27,565 | 396,177.6420 |
| HEAD, re-synthesised as a control | **27,565** | **396,177.6420** |
| the memory change alone, `RDREG = 0` | **27,565** | **396,177.6420** |
| **plus a fabric parameter written into the existing expression** | **27,837** | **397,241.7876** |
| the same expression restructured into two named generate arms | **28,656** | 396,196.7688 |
| the same, written as a separate disjunct | **28,512** | 395,317.6542 |
| **plus 52 lines of pure comment inserted into `soc_bus.v`** | **27,837** | **397,241.7876** |

**[fact, seven runs of `flow/syn_soc_top.sh`]**

Three things follow and all three are load-bearing.

1. **The restructuring of `soc_mem.v` and `soc_mem_sram.v` is a true
   no-op at `RDREG = 0`.** Both files were rewritten around a generate
   with two arms, three ports changed from `reg` to `wire`, and the
   netlist is `docs/47`'s **up to three net names** — `u_ram.rvalid_o`
   became `u_ram.rv0`, `u_rom.rvalid_o` became `u_rom.rv0`,
   `u_rom.err_o` became `u_rom.er0`. A `sed` renaming those three makes
   the two files identical **[fact]**. Same cells, same cell types, same
   area, 46 differing lines out of 71,000.
2. **The mapper is chaotic with respect to a term that is constant
   zero.** `((cnt < MAX_OUT) || (RESP_CREDIT && rvalid))` at
   `RESP_CREDIT = 1'b0` folds to `(cnt < MAX_OUT)`, and the design that
   comes out has **272 more cells**. Written three other ways it has
   1,091 more, 947 more, and the same again. The grant cone feeds the
   32-bit address and write-data broadcast multiplexers and every
   downstream counter, so a different factorisation there is a different
   mapping across the fabric.
3. **AND IT IS NOT SENSITIVITY TO THE FILE, WHICH IS THE CONTROL FOR
   ITEM 2.** Yosys embeds `file:line` in the names of the wires it
   generates, so the obvious explanation is that any edit perturbs the
   result. **It does not.** 52 lines of pure comment inserted after the
   `timescale` — every subsequent line number changed, every generated
   wire name changed — produce a **bit-identical area report** to the
   run without them **[fact]**. The sensitivity is to the **expression**.

> **THIS IS WHY `soc_bus.v` IS NOT MODIFIED BY THIS DOCUMENT, AND THE
> DECISION IS SECTION 3'S RATHER THAN THIS SECTION'S.** The netlist cost
> is what made the question worth asking carefully; the answer is that
> the fabric change buys **zero measured cycles** and is unreachable
> logic. But the finding stands on its own: **cell count is not a stable
> measure of a change in this flow, and a control that is not
> byte-identical may be saying nothing about the change under test.**
> `docs/48` compared two runs on a bit-identical placement for exactly
> this reason and said so; this is the same discipline arriving one level
> earlier, at synthesis.

---

## 3. The protocol, which is the part `docs/49` said would be the work

### 3.1 What actually changes on the wire

`soc_mem` is a fabric slave. `RDREG = 1` adds one pipeline stage to its
response, so a granted request is answered **two** cycles later instead
of one. Everything else is unchanged, and the list of what is unchanged
is the protocol argument:

| | `RDREG = 0` | `RDREG = 1` |
|---|---|---|
| `gnt_o` | `req_i`, combinational | **`req_i`, combinational** |
| requests accepted per cycle | 1 | **1** |
| responses per granted request | exactly 1 | **exactly 1** |
| response in the grant cycle | never | **never** |
| ordering | in order by construction | **in order by construction** |
| latency, read | 1 cycle | **2 cycles** |
| latency, write | 1 cycle | **2 cycles** |
| which slaves are affected | — | **RAM and boot ROM only** |

**[fact, `hw/soc/tb/cocotb/test_soc_mem.py`, 7 tests run at both values,
with the latency measured from the DUT]**

Two of those rows are decisions rather than consequences.

**THE WRITE RESPONSE IS DELAYED TOO.** Protocol rule 3 gives every
granted request exactly one `rvalid` and rule 4 requires them in order.
A memory that answered writes in one cycle and reads in two would
reorder its own responses the first time a store followed a load, and
`soc_bus.v`'s ownership queue would hand the load's data to whoever owned
the store. **Latency is a property of the SLAVE, not of the access**, and
`test_a_write_is_answered_like_a_read` states it as its own property so
the reason is recorded rather than inferred from a passing ordering test.

**THE PERIPHERALS DO NOT PAY.** `RDREG` is a parameter of `soc_mem` and
the extra stage is inside it. The APB bridge, the device tables and the
CLINT are not behind a macro, are not touched, and answer in the cycles
they always did — the CLINT in one, which matters because `mtime` is the
one register software polls in a loop and `docs/40` gave it its own
fabric port for that reason. **Putting the stage in the fabric's return
path instead would have been one register bank rather than two and would
have charged every slave for the macros' arc.** It was not done.

### 3.2 What the fabric needs, which is nothing, and why that is measured

`soc_bus.v` is **unchanged** — byte-identical to `docs/47`'s. Three
pieces of evidence, in increasing order of how much they are worth.

**First, the specification already says so.** The protocol block at the
top of that file, quoted verbatim from Ibex's own reference, says of
`rvalid`: *"It may be one or more cycles after the grant."* Slave
requirement S1 restates it from the slave side. A two-cycle memory is
inside the contract the fabric was written against, not an extension of
it.

**Second, and much stronger, the PROOF already quantified over it.**
`hw/soc/formal/soc_bus_props.v` constrains the four slave response inputs
with **exactly one assumption** — a slave does not answer a request it
was never given — and says **nothing whatever about when it answers**. So
the k-induction proof of F1 to F9 was already a proof for every slave
latency, and F4a (never more than `MAX_OUT` outstanding) and F6 (no queue
overflow) were already the statements that the accounting holds under one.
**No assertion in that file changed for this document.** What was missing
was not a property but a **witness**, and section 8.2 adds four covers
that name the two-cycle regime so it is a reachable state of the checked
model rather than a state adjacent to it.

**Third, the one thing that could have needed changing was designed,
built, and measured at zero.**

> **THE FABRIC ENFORCES ITS OUTSTANDING LIMIT WITH `cnt < MAX_OUT`, AND
> `cnt` IS A REGISTER.** A response arriving now is not subtracted until
> the next clock edge, so **in the cycle a response returns, a master at
> the limit is refused a grant it could have had**. At one cycle of slave
> latency this is invisible: the grant and the response coincide from the
> second cycle onwards, `cnt` is incremented and decremented in the same
> cycle, and the limit is never reached. **At two cycles the arithmetic
> says it should cost a third of the fetch bandwidth** — grants at cycles
> 0 and 1 take `cnt` to 2, at cycle 2 the response returns and the grant
> is refused because `cnt` still reads 2, and the pattern repeats at two
> grants every three cycles.
>
> **It costs nothing, and the reason is that Ibex's `NUM_REQS` is 2 and
> the fabric's `MAX_OUT` is 2.** The core reaches its own limit at the
> same occupancy the fabric would refuse at, and it stops asserting `req`
> — so **the fabric's conservatism is never the thing that refuses.**

This is measured, not argued, by `hw/soc/tb/soc_bus_probe.v`: a second
elaboration root that drives nothing and counts, among other things, the
cycles in which a master is **at** the limit, **locked to the slave it is
addressing**, and **still requesting** — which is exactly the population
any credit scheme would act on.

| whole-SoC run, per master | baseline | `MEM_RDREG = 1` |
|---|---:|---:|
| instruction port at occupancy 0 / 1 / 2 | 77,696 / 107,749 / **0** | 65,805 / 131,740 / **34,689** |
| data port at occupancy 0 / 1 / 2 | 141,155 / 44,290 / **0** | 162,676 / 69,558 / **0** |
| **at the limit and still asking**, instr / data | **0 / 0** | **0 / 0** |
| refused by the same-slave restriction, instr / data | **0 / 0** | **0 / 0** |
| grants, instr / data | 107,749 / 33,554 | 100,559 / 32,549 |
| responses ram / rom / apb / pnp / clint | 27,611 / 108,303 / 5,368 / 2 / 18 | 27,493 / 101,113 / 4,481 / 2 / 18 |

**[fact, `SOC_PROBE=1 hw/soc/flow/sim_soc.sh`]**

> **THE THIRD ROW IS THE RESULT.** The extra cycle DOES put the
> instruction port at the outstanding limit — **34,689 cycles of it,
> where the baseline never got there once** — and in **not one** of those
> cycles was the core still requesting. **A credit scheme has an empty
> population to act on.** It was implemented anyway, run end to end, and
> the whole-SoC cycle count with it is **232,232 — identical to the count
> without it, to the cycle** **[fact, two runs of `flow/sim_soc.sh`]**.
> It was then **removed**, because section 2.2 measures that carrying it
> at 0 costs 272 cells of a design that has not changed, and because a
> parameter with no reachable effect is a parameter someone eventually
> believes something about.
>
> **AND THE FOURTH ROW ANSWERS THE OTHER HALF OF THE QUESTION `docs/49`
> ASKED.** `docs/39`'s header prices the same-slave restriction at "one
> dead cycle when a master switches target", and the obvious worry is
> that the extra latency makes that dead cycle two. **It is never paid
> at all**, in either configuration: neither master is ever refused
> because its target changed while it had responses outstanding. The
> restriction costs what the header says it costs only when a switch
> happens while the previous burst is still in flight, and Ibex's two
> ports each address one region for long runs.

The credited-grant variant, for the record, since it is not in the tree:

```
-  wire can_issue_i = issue_en && mi_req_i &&
-                     ((cnt_i == 2'd0) ||
-                      ((lock_i == tgt_i) && (cnt_i < MAX_OUT[1:0])));
+  wire credit_i = RESP_CREDIT && mi_rvalid_w && issue_en && mi_req_i &&
+                  (cnt_i == MAX_OUT[1:0]) && (lock_i == tgt_i);
+  wire issue_i  = can_issue_i || credit_i;
```

with `mi_rvalid_w` forward-declared so `|resp_to_i` can be read before the
response-steering section, and `d_wins`/`i_wins` taking `issue_*`. It is
not a loop: every slave in this SoC registers `rvalid`, and rule 3
forbids a response in the grant cycle, so nothing a grant produces can
reach `rvalid` in the same cycle. **The reason it is not here is that it
does nothing, not that it is wrong.**

---

## 4. What was built

| File | Change |
|---|---|
| `hw/soc/rtl/soc_mem.v` | `RDREG`, two named generate arms `g_rd1` and `g_rd2`, three ports `reg` → `wire`. The behavioural model does not need the register; it has one because the two files must have the **same protocol timing** or every cycle count measured in simulation is a count for a different SoC |
| `hw/soc/rtl/soc_mem_sram.v` | the same parameter and the same two arm names, with the register **after** the bank and half multiplexers |
| `hw/soc/rtl/soc_top.v` | `MEM_RDREG`, defaulting to 0, passed to both memory instances |
| `hw/soc/flow/syn_soc_top.sh` | `SOC_MEM_RDREG` — one `chparam` on `soc_top`, emitting nothing at 0; and `RDREG` added to the two generated boundary models, with the stand-in **honouring** it so the stubbed timing model still starts a path one flip-flop later |
| `hw/soc/flow/sim_soc.sh` | `SOC_MEM_RDREG`, by generated `defparam` in a second root; `SOC_RAM_RDREG` / `SOC_ROM_RDREG` for the attribution of section 5.2; `SOC_PROBE`; and the compiled-object arm check generalised from `docs/49`'s single knob to a function |
| `hw/soc/flow/fi_core.sh` | `SOC_MEM_RDREG`, the same way and with the same arm check, so `docs/46`'s supervisor can be run at both latencies. Section 7 |
| `hw/soc/tb/soc_bus_probe.v` | **new.** Section 3.2 |
| `hw/soc/tb/cocotb/test_soc_mem.py`, `Makefile.soc_mem` | **new.** Section 8.3 |
| `hw/soc/tb/cocotb/test_soc_bus.py` | one test: the two-cycle memories at full rate |
| `hw/soc/formal/soc_bus_props.v` | **F9 repaired** and **F9b added** (section 8.1); a latency ghost and four covers (section 8.2) |
| `sw/tests/test_soc_memory_guards.py` | **new**, 6 tests |
| `sw/tests/test_soc_synthesis_guards.py` | its inline fifth `soc_mem` blackbox now **derives** the parameter list instead of restating it — see below |
| `sw/tests/test_soc_regfile_guards.py` | the SYNPRE override check follows the generalised mechanism |

**Where the register goes, and the alternative that was not built.**
`docs/49` section 11.1's arithmetic splits the path at the macro's
`A_DOUT`. That is not where the register is: it is **after** the 4-way
bank multiplexer and the half multiplexer, on the 32-bit `rdata_o`.
Registering at `A_DOUT` would be **4 × 64 = 256 flip-flops on the RAM and
2 × 32 = 64 on the ROM**; after the multiplexers it is **32 and 32**. The
first half of the path grows by two multiplexer stages and it has
**9.9231 ns** of margin on `docs/47`'s own decomposition to absorb them
**[estimate, `docs/49` 11.1's arithmetic]**; section 6 measures what
actually happened to it.

**A fifth copy of the parameter list was found by breaking it.**
`sw/tests/test_soc_synthesis_guards.py` writes its own `soc_mem`
blackbox, with the parameter list spelled out in four literal lines, to
elaborate the whole design as one. Adding `.RDREG(MEM_RDREG)` to
`soc_top.v` broke it — *"does not have a parameter named 'RDREG'"* — in
a test whose subject is precisely that the memory boundary models do not
go stale. It now derives the list from `soc_mem.v`. **That is four
declarations in the tree plus one in a test, all of which have to agree,
and until this document only the PORTS were compared.**
`sw/tests/test_soc_memory_guards.py` compares the parameters.

### 4.1 The area

| | cells | flip-flops | standard-cell area, um2 |
|---|---:|---:|---:|
| `soc_top`, `SOC_MEM=sram`, as `docs/47` hardened | 27,565 | 3,085 | 396,177.6420 |
| the same, `SOC_MEM_RDREG=1` | **28,544** | **3,152** | **399,299.8842** |
| difference | **+979** | **+67** | **+3,122.2422, +0.79 %** |

**[fact; the differences are arithmetic on them]**

**+67 flip-flops is exactly the register and nothing else**, and the
arithmetic is checkable: 32 for the RAM's `rd1`, 32 for the ROM's, one
`rv1` each, and one `er1` for the ROM. The RAM's `er1` is **absent**
because `RO = 0` makes its `err_o` a constant, so the synthesiser
removes both stages of it — 32 + 32 + 1 + 1 + 1 = 67 **[estimate,
arithmetic against a measured count]**. Against `docs/49`'s `SYNPRE` at
**+2,684 cells and +6.9 %**, this is **a quarter of the cell count and a
ninth of the area**.

---

## 5. The cycle count, which is the thing that had to be re-established

`docs/40` established the invariant and every hardening document since
has used "cycle-identical" as its evidence that behaviour did not change.
**This change makes the program slower by construction, so that evidence
is not available and a different one is owed.** What follows is the new
baseline, its breakdown, and the checks that the behaviour did not move
with the number.

### 5.1 The invariant at its new value

| `hw/soc/flow/sim_soc.sh`, whole SoC | baseline | **`SOC_MEM_RDREG=1`** |
|---|---:|---:|
| checks run | **0x16 (22)** | **0x16 (22)** |
| fail mask | **0** | **0** |
| watchdog stage 1 (NMI) at cycle | 174,128 | **220,848** |
| **core asleep after** | **185,443 cycles** | **232,232 cycles** |
| exit code | 0x0 | **0x0** |
| console characters decoded | 587 | **588** |
| framing errors | **0** | **0** |
| watchdog stage1 / stage2 / stage3 | 1 / 0 / 0 | **1 / 0 / 0** |

**[fact, two runs of `flow/sim_soc.sh`, whose compiled objects were
checked to contain `g_rd2` and `g_rd1` respectively]**

**THE 588TH CHARACTER IS THE TRAILING NEWLINE AND THE BASELINE IS THE ONE
THAT IS WRONG.** The console byte stream is identical for its first 587
characters and the registered run additionally **finishes** the final
newline of `RESULT PASS` before the testbench stops. The baseline
truncates it: the core reaches `wfi` while the last character is still on
the wire at 80 clocks per byte, and the testbench stops decoding.
**0 framing errors in both**, and the `sim.log` diff is that one blank
line, the two cycle numbers and the output path **[fact, `diff`]**.

**And the escalation demo still runs, which is the check that the
watchdog's own behaviour did not move:**

| `SW_DEFINES=-DWDOG_RESET_DEMO` | baseline | `SOC_MEM_RDREG=1` |
|---|---:|---:|
| stage 1 (NMI) at cycle | 10,928 | 11,024 |
| stage 2 (system reset) at cycle | 14,144 | 14,240 |
| stage 1 again | 25,104 | 25,264 |
| stage 2 again | 28,320 | 28,480 |
| **stage 3 (WDOGN pin)** at cycle | **28,320** | **28,480** |
| core asleep after | 37,405 | **37,653, +0.66 %** |
| **stage1 / stage2 / stage3 totals** | **2 / 2 / 1** | **2 / 2 / 1** |

**[fact]**. Three boots of the SoC in one simulation, the same ladder in
the same order, and **the stage timings move by 0.9 % where the bring-up
program's move by 26.8 %** — because the demo's timeouts are counted in
clock cycles from a fixed point and the bring-up program's stage 1 fires
when the program stops kicking, which is a function of how far it has
got. **That difference is itself the check that the +25.2 % is
work-proportional and not an artefact of a timer.**

### 5.2 Where the 46,789 cycles go

The two memories were registered one at a time, through the same flow,
with the per-instance knobs `flow/sim_soc.sh` gained for exactly this:

| configuration | cycles | delta | share of the total delta |
|---|---:|---:|---:|
| baseline | 185,443 | — | — |
| **RAM only** (`.data`, the stack, every load and store) | **212,263** | **+26,820** | **57.3 %** |
| **ROM only** (`.text`, `.rodata`, every instruction fetch) | **205,561** | **+20,118** | **43.0 %** |
| **both** | **232,232** | **+46,789** | 100 % |

**[fact for the cycle counts; the deltas and shares are arithmetic on
them]**. **The two are additive to 0.3 %** — 26,820 + 20,118 = 46,938
against 46,789 — so the instruction and data effects barely interact, and
each can be read on its own.

> **THE DATA SIDE COSTS MORE THAN THE INSTRUCTION SIDE ALTHOUGH THERE ARE
> FOUR TIMES AS MANY FETCHES, AND THAT IS THE ARCHITECTURE SHOWING
> THROUGH.** Per response, the RAM costs **0.9714 cycles** and the ROM
> **0.1858** **[estimate, measured deltas over the measured response
> counts of section 3.2]**. Ibex is a two-stage core with no cache: a
> load stalls the pipeline until its data returns, so **essentially every
> extra cycle of load latency is an extra cycle of execution** — 0.97 of
> one, measured. Instruction fetch is different because the prefetch
> buffer has two requests in flight, so **it hides 81 % of the extra
> fetch latency** and pays only on refills. That is also what the
> occupancy histogram in section 3.2 shows from the other side: the
> instruction port sits at occupancy 2 for **34,689** cycles and the data
> port **never** does.

---

## 6. The layout and the sign-off

`rdreg1` is `hw/soc/pnr/config.json` with **no overrides at all**, run
straight through from `docs/47`'s synthesised-netlist entry point.
Section 13 records that its `resolved.json` and `full3`'s are identical
key for key, so **the only difference between this run and `docs/47`'s
sign-off is which netlist went in.**

### 6.1 Stage by stage

Worst setup slack in ns at `nom_slow_1p08V_125C`, 20 ns period, 5 %
derate applied as a float.

| | `full2`/`full3`, `docs/47` | **`rdreg1`** |
|---|---:|---:|
| netlist standard-cell area, um2 | 396,177.6420 | **399,299.8842** |
| netlist cells / flip-flops | 27,565 / 3,085 | **28,544 / 3,152** |
| standard-cell utilization at global placement | 18.9429 % | **19.0925 %** |
| global-placement HPWL (OpenROAD's own units) | 1,116,085,161 | **1,133,705,029, +1.6 %** |
| **first STA after global placement** | **−75.1255** | **−77.7940** |
| `RepairDesignPostGPL`: slew / cap / buffers / nets | 70 / 181 / 3,326 / 2,396 | **65 / 174 / 3,261 / 2,419** |
| **post-CTS, before the timing resizer** | **−10.7556** | **−11.3488** |
| **post-CTS resizer, placement parasitics** | −0.1577 | **−1.0725** |
| global-route wirelength | 3,771,252 um | **3,821,673 um, +1.3 %** |
| `RepairDesignPostGRT`: slew / cap / buffers / nets | 26 / 101 / 110 / 127 | **43 / 92 / 101 / 135** |

**[fact for every row]**

**THE AREA AND WIRE COST IS AN ORDER OF MAGNITUDE SMALLER THAN
`SYNPRE`'S, WHICH IS THE FIRST THING TO READ OUT OF THAT TABLE.**
`docs/49` measured +6.9 % of standard-cell area, +23.2 % of
global-placement HPWL and +13.8 % of routed wirelength for 31 parity
trees fanned out of 32 registers' flip-flops. **This is +0.79 %, +1.6 %
and +1.3 %**: two 32-bit register banks placed next to the macros they
belong to. `RepairDesignPostGRT` finds **fewer** capacitance violations
than the baseline, not more.

**AND THE MID-FLOW SLACKS ARE WORSE ANYWAY, AT EVERY STAGE BEFORE THE
FINAL REPAIR.** −77.79 against −75.13 at global placement, −11.35 against
−10.76 post-CTS, −1.07 against −0.16 after the post-CTS resizer. **None
of those is the read path.** The global-placement figure is an
ASYNCHRONOUS RECOVERY check in both runs, which is `docs/45` section 7's
subject and not this one's; and at the start of the post-GRT setup
repair the worst SYNCHRONOUS path, **in both runs**, ends at
**`u_ram.g_ram_2048x64.u_b2/A_DIN[*]` — the macro's DATA INPUT**
(`A_DIN[21]` in `full3`, `A_DIN[14]` in `rdreg1`) **[fact, the two
`06-`/`36-openroad-resizertimingpostgrt` logs, iteration 0]**. **The
register is on the way OUT of the macro and does nothing for the way
in**, and 979 more cells make the design very slightly harder to place
around it.

### 6.2 The number

| `nom_slow_1p08V_125C`, 20 ns | `full3`, `docs/47` | **`rdreg1`** | delta |
|---|---:|---:|---:|
| **worst setup slack** | **−3.2029** | **−2.4257** | **+0.7772** |
| violating setup endpoints | 2,003 | **1,893** | −110 |
| setup TNS | −2,075.11 | **−2,630.63** | **−555.51, 26.8 % WORSE** |
| **derived Fmax** | **43.0981 MHz** | **44.5917 MHz** | **+1.4936 MHz** |

**[fact, `hw/openlane/signoff_report.py` on both run directories; the
Fmax figures are `docs/31` section 4.2's convention, `1 / (T − WNS)`, and
the deltas are differences of measurements]**

> **+0.7772 ns IS AN IMPROVEMENT AND THIS DOCUMENT REPORTS IT AS ONE.**
> `docs/44` section 5.2 measured this flow's resolution at about **0.4 ns**
> and `docs/49` used that figure to refuse to claim +0.1191 ns. **0.7772
> is 1.94 times that**, on a change whose mechanism is visible in the
> violator list rather than inferred from the number, and it is the first
> setup movement in `docs/47`, `docs/48`, `docs/49` or this document that
> survives the noise floor. **It still does not close 20 ns**, and it is
> **2.43 ns short of it.**
>
> **AND THE TNS GOES THE OTHER WAY, BY MORE.** `SYNPRE` improved the
> total and not the worst; this improves the worst and makes the total
> **26.8 % worse**. Section 6.3 is why, and it is not a paradox.

### 6.3 What happened to the binding path

**THE READ ARC IS GONE FROM THE CRITICAL PATH, WHICH IS THE ONE THING
THIS CHANGE WAS BUILT TO DO, AND IT IS VISIBLE BEFORE SIGN-OFF.** At
`OpenROAD.STAMidPNR-3` — after the post-GRT repair, on placement
parasitics, the last stage both runs share — the worst path is:

| | `full3` | **`rdreg1`** |
|---|---|---|
| worst slack at that stage | **−2.5778** | **−2.6949** |
| **startpoint** | `register_file_i.raddr_a_i[0]` | **`register_file_i.raddr_b_i[3]`** |
| **endpoint** | `u_clint.mtimecmp[52]` | **`u_clint.mtime[46]`** |

**[fact, the two `stamidpnr-3/max.rpt` and `ws.max.rpt`, with the two
anonymous flip-flop names resolved against each run's own netlist]**

**It is the same structure in both runs**, which is what makes the two
slacks comparable — and not one gate of it is inside a memory. **What
changed is that in `full3` this was the SECOND-worst structure and the
macro read path was ahead of it; here there is nothing ahead of it.**
`docs/49` section 14 item 2 predicted exactly that, and it also names the
endpoint: the CLINT's 64-bit counters, at the far end of a broadcast bus,
which `docs/41` section 7.4 ranked first and five documents since have
deferred.

**AT SIGN-OFF IT IS COMPLETE, AND THIS IS THE STRONGEST STATEMENT IN THE
DOCUMENT.** Every one of `rdreg1`'s 1,893 violating endpoints, resolved
against its own netlist:

| launch point | `full3` | **`rdreg1`** |
|---|---:|---:|
| **`u_ram.g_ram_2048x64.u_b0/A_DOUT[*]`** | **444**, worst **−3.2029** | **0** |
| `register_file_i.raddr_a_i[2]` | 868, worst −2.0227 | 0 |
| `register_file_i.raddr_a_i[0]` | 509, worst −1.7387 | 0 |
| **`register_file_i.raddr_b_i[1]`** | 181, worst −1.5937 | **1,889**, worst **−2.4257** |
| `register_file_i.raddr_b_i[0]` | 0 | 4, worst −1.9422 |
| `…g_scrub.ptr_q[3]` | 1 | 0 |
| **total** | **2,003** | **1,893** |

**[fact, resolving both `violator_list.rpt` files against their own
netlists with the same script, which reproduces `docs/49` section 3.1's
figures exactly on `full3`]**

> **1. THE MACRO GROUP IS NOT SMALLER. IT IS EMPTY.** `docs/49` measured
> 444 endpoints behind the RAM banks with a worst slack of −3.2029 and
> concluded that "the most a perfect, free `SYNPRE` could do to the worst
> slack is nothing", because that population was unreachable. **The
> register reaches it and removes it entirely.** No path from any SRAM
> macro's `A_DOUT` violates setup at any corner.
>
> **2. WHICH IS ALSO WHY THE TNS GOT WORSE, AND THE MECHANISM IS AN
> ARTEFACT OF HOW ENDPOINTS ARE COUNTED RATHER THAN A REGRESSION.** A
> violating endpoint is reported once, under its WORST launch. In `full3`
> the 444 register-file check bits and core flops behind the macros had
> their worst path through the macro; **the same flip-flops are still
> violating, and their worst path is now the read address**, so they move
> into the read-address group and drag its worst slack from −2.0227 to
> −2.4257 and its total from −1,464.55 to −2,630.63. **Total endpoints
> fall by 110 and the sum of a differently-partitioned population rises.**
> The honest summary is that **the read-address cone was always this bad
> and the macro was hiding 444 endpoints' worth of it.**
>
> **3. AND 1,889 OF THE 1,893 LAUNCH FROM ONE FLIP-FLOP.**
> `register_file_i.raddr_b_i[1]` — a single bit of a register-file read
> address, fanning out through the 32-way read multiplexer into the
> SECDED check bits (216 endpoints), `crash_dump_o` (158),
> `csr_pmp_addr_o` (128), `mtime` and `mtimecmp` (64 each), the
> performance counters (128) and the prefetch buffer (64) **[fact, the
> capture-side census]**. That is one launch point and one cone, and it
> is exactly the cone `docs/44` section 5.5's `SYNPRE` restructures.

### 6.4 The rest of the sign-off set

| | `full3` | **`rdreg1`** |
|---|---:|---:|
| **hold, `nom_fast_1p32V_m40C`** | **−0.2015 ns on 3 endpoints** | **+0.1029 ns on 0** |
| hold, slow / typ | +0.4082 / +0.0367, 0 violations | **+0.5960 / +0.2795, 0** |
| setup, fast / typ | 10.6634 / 5.7231 | 10.3811 / 5.7202 |
| **max slew, fast / slow / typ** | 1 / **14** / 0 | **3 / 70 / 4** |
| **max cap, fast / slow / typ** (both against the library's own 0.3 pF) | 12 / 10 / 10 | **35 / 34 / 34** |
| detailed-routing DRC | 0 | **0** |
| antenna violating nets / diodes | 1 / 514 | **1 / 594** |
| routed wirelength | 3,095,532 um | **3,154,101 um, +1.9 %** |
| standard cells excl. fill | 37,623 | **38,654** |
| standard-cell area, um2 | 531,371 | **532,176, +0.2 %** |
| timing-repair buffers | 7,910 | **7,820** |
| of which setup / hold buffers | 528 / 21 | **504 / 91** |
| max-fanout violations (judged by nothing) | 293 | 300 |
| disconnected pins / power-grid violations | 0 / 0 | **0 / 0** |
| `design__violations` on a run that fails setup | **0** | **0** |

**[fact, the two `final/metrics.json` and the two
`*-openroad-stapostpnr/checks.rpt`]**

> **THE HOLD ROW IS THE SAME TEMPTATION `docs/49` REFUSED AND IT IS
> REFUSED AGAIN.** `docs/47`'s hold failure is absent, at all three
> corners, through a checker section 9 confirms was bound to all three.
> But the movement is **0.3044 ns on a population of three endpoints**,
> which is **inside** the 0.4 ns that forbids claiming it, on a run where
> the netlist, the placement, the clock tree and the routing all changed.
> **This document reports that `rdreg1` has no hold violation and does
> not attribute it to the register.**
>
> **THE SLEW AND CAP ROWS ARE NOT INSIDE ANY NOISE AND THEY GO THE OTHER
> WAY.** Max slew at the slow corner **14 → 70** and max cap **10 → 34**,
> against the library's own `default_max_capacitance : 0.3` in both runs
> because neither sets `MAX_CAPACITANCE_CONSTRAINT` — **directly
> comparable, and `rdreg1` is electrically worse.** It is a smaller
> regression than `docs/49`'s (126 slew, 24 cap) for a smaller change,
> but it is in the same direction and it is a third criterion the flow
> exits non-zero on:
>
> ```
> One or more deferred errors were encountered:
> Setup violations found in the following corners:
> * nom_slow_1p08V_125C
> Max Slew violations found in the following corners:
> * nom_fast_1p32V_m40C
> * nom_slow_1p08V_125C
> * nom_typ_1p20V_25C
> Max Cap violations found in the following corners:
> * nom_fast_1p32V_m40C
> * nom_slow_1p08V_125C
> * nom_typ_1p20V_25C
> ```
>
> **[fact, `hw/soc/out/s50-pnr-rdreg1.log`]** — three criteria where
> `docs/47`'s named four; hold is absent because it passed.

---

## 7. The performance answer, which nobody had asked

`docs/48` section 7a and `docs/49` section 11.2 both ended by saying the
obligation was to **size the workload** before writing a frequency on a
datasheet, and both left it to another document. **This is the first
number in this repository that multiplies a cycle count by a period.**

The rule is one line: **a part is faster when `cycles x period` is
smaller**, and the period is `docs/31` section 4.2's convention,
`T - WNS`.

### 7.1 The break-even clock

`docs/47`'s design runs the bring-up program in
**185,443 x 23.2029 ns = 4.3028 ms** **[estimate, a measured cycle count
times a measured period]**. The registered design needs **232,232**
cycles, so to do the same work in the same time its period must be

**4.3028 ms / 232,232 = 18.5281 ns, which is 53.97 MHz.**

**[estimate, arithmetic on four measured quantities]**

| workload | baseline cycles | registered cycles | change | **break-even clock** |
|---|---:|---:|---:|---:|
| **bring-up program**, `hw/soc/tb/sw/test_ibex.c` | 185,443 | 232,232 | **+25.23 %** | **53.97 MHz** |
| **`docs/46`'s supervisor, work-triggered** | 29,176 | 36,680 | **+25.72 %** | **54.18 MHz** |
| `docs/46`'s supervisor, time-triggered at 8,912 | 69,085 | 73,283 | +6.08 % | 45.72 MHz |

**The registered design closes at 44.5917 MHz (section 6). It needs
53.97.**

**[fact for the six cycle counts; the changes and break-even clocks are
arithmetic on them and on `docs/47`'s 23.2029 ns period]**

**THE TWO WORKLOADS AGREE TO HALF A PERCENT AND THEY HAVE NOTHING IN
COMMON.** The bring-up program is a functional test with a UART console
and a watchdog escalation; `docs/46`'s supervisor is four U-mode
partitions behind PMP with a frame schedule and one kick per frame,
built from a different source file against a different startup file, run
on a different testbench. **+25.23 % and +25.72 %.** That is what a
change to memory latency looks like on a two-stage core with no cache:
it is a property of the machine, not of the program.

**The third row is real and it is not a counterexample.** The
time-triggered supervisor is slower by only 6.08 % because its frame
period is fixed in *time*: the extra work per frame is absorbed by the
slack in an 8,912-cycle frame, until it is not. **All six frames still
complete**, with the same `sig=216f8ce6`, the same `mask=0`, the same
`console_hash=37ded8d6`, no traps and no watchdog stage **[fact, the
`RECORD` lines of both runs]**. What moves is the margin: the
work-triggered worst-case frame grows from **4,458 to 5,510 cycles**, so
**`docs/46`'s `SUP_TICK_PERIOD = 8,912` falls from 2.00x that worst case
to 1.617x** **[estimate, measured frame times over a fixed period]**. **A
time-triggered schedule converts a throughput loss into a loss of
SCHEDULABILITY MARGIN, which is a worse currency to pay in**, because it
is spent silently until a frame overruns.

> **AND `docs/46`'s ACTUAL DECISION SURVIVES, WHICH IS WORTH ONE
> SENTENCE BECAUSE IT COULD EASILY NOT HAVE.** That document's
> load-bearing finding is that the work-triggered kick-interval ratio is
> **2.104** and that `WINS = 1` needs it below **2.0**, so no windowed
> timeout satisfies both bounds. At two cycles of memory latency the
> ratio is **5,510 / 2,646 = 2.0824** — smaller, still above 2.0, **so
> the answer does not change** **[estimate, on measured `kick_min` and
> `kick_max`]**.
>
> **The reproduction of `docs/46` is two cycles off and that is reported
> rather than rounded away.** That document measures `kick_min = 2,118`
> and `kick_max = 4,456` free-running; this environment measures **2,120
> and 4,458** on the unmodified design, a ratio of **2.1028** against its
> **2.104** **[fact]**. Two cycles in 4,456 is 0.045 %, it is in the
> baseline and not in the change, and it was not chased.

### 7.2 The answer

| workload | `docs/47`, 43.0981 MHz | **`rdreg1`, 44.5917 MHz** | |
|---|---:|---:|---:|
| **bring-up program** | **4.3028 ms** | **5.2080 ms** | **+21.04 % SLOWER** |
| **supervisor, work-triggered** | **0.6770 ms** | **0.8226 ms** | **+21.51 % SLOWER** |
| supervisor, time-triggered | 1.6030 ms | 1.6434 ms | +2.52 % slower |

**[estimate, measured cycle counts times measured periods]**

> **THE REGISTER BUYS 1.49 MHz AND COSTS 25 % OF THE CYCLES, SO THE PART
> DOES LESS WORK PER SECOND. THAT IS THE ANSWER AND IT IS NOT CLOSE.**
> The break-even clock is **53.97 MHz** and the layout reaches **44.59**.
> The gap is not a rounding error: the change would have to be worth
> **9.4 MHz more than it is**, and the entire measured effect of every
> mechanism tried in `docs/47` through `docs/50` — floorplan,
> capacitance, `SYNPRE`, and this — adds up to **1.49 MHz**.
>
> **AND THE TARGET DOES NOT RESCUE IT.** Suppose the design closed at
> exactly 20.000 ns, which is 50 MHz and is what four documents have been
> trying to reach. **232,232 x 20.000 ns = 4.6446 ms against 4.3028 ms:
> still 7.94 % slower than the 43.10 MHz design that misses the target by
> 3.2 ns** **[estimate]**. **A part that hits the clock target and does
> less work per second than one that misses it is a part whose clock
> target is measuring the wrong thing** — which is `docs/48` section 7a's
> and `docs/49` section 11.2's point, arriving with a price on it.

### 7.3 The recommendation

**DO NOT KEEP IT, AND THE PARAMETER STAYS AT 0.** Written out so that a
reader who disagrees can see exactly which measurement to attack:

| | |
|---|---|
| It does what it was built to do | **Yes.** Zero violating endpoints behind any SRAM macro, against 444. Section 6.3 |
| It improves the sign-off number | **Yes, by +0.7772 ns**, which is outside the noise floor and is the only setup improvement in four documents that is. Section 6.2 |
| It closes 20 ns | **No.** −2.4257 ns, 44.5917 MHz. Section 6.2 |
| It is cheap in area and in flow time | **Yes.** +0.79 % standard-cell area, +67 flip-flops, +1.9 % routed wire, and the timing repair runs 2.8 % longer rather than 16.9 times. Sections 4.1, 6.1 and 13 |
| It is electrically neutral | **No.** Max slew 14 → 70 and max cap 10 → 34 at the slow corner, against the library's own limit in both runs. Section 6.4 |
| It preserves the behaviour | **Yes.** 22 checks, fail mask 0, the escalation ladder, the supervisor's signature and console hash, all identical. Sections 5 and 7 |
| **It makes the part faster** | **NO. It makes it 21 % slower**, on both workloads, at its own measured clock — and 7.94 % slower even if it closed the target exactly. Section 7.2 |

**The last row is the one that decides it, and it is the only row that
had never been computed.** `docs/47` through `docs/49` optimised a
frequency; this is the first document to multiply that frequency by the
cycles the design needs, and the product moves the wrong way.

**The reversal condition, stated so this can be reopened rather than
re-litigated.** Keep the register if **any** of the following becomes
true, and none of them is true today:

1. **A workload is sized** (section 12 item 1) and its requirement is a
   deadline in *frequency* rather than in work per second — a part that
   must respond within N clocks rather than within N microseconds. The
   time-triggered supervisor row is the shape of that case: it pays
   2.5 % rather than 21 %, because its schedule is fixed in time.
2. **Something absorbs the load latency** — a cache, a wider fetch, a
   store buffer, a non-blocking load (section 12 item 4). The 21 % is
   0.9714 cycles per RAM access on a machine with nothing between the
   core and the memory; halve that and the arithmetic changes sign at
   about 48 MHz **[estimate]**.
3. **The clock target becomes a constraint rather than a habit** — an
   external interface, a PLL ratio, or a datasheet somebody has signed.

**What is worth keeping out of this block regardless of that decision**
is everything in section 8: the `soc_mem` suite, the fabric's two-cycle
test, the four covers, and above all the F9 repair, which is a real
defect in a proved block and has nothing to do with whether the register
ships.

### 7.4 Two things this does not settle

- **Neither workload is a mission profile.** `docs/05` section 3.4's
  four profiles are event-driven prose and none is specified in cycles;
  `docs/48`, `docs/49` and now this document have all said the same
  thing. What has changed is that **the sensitivity is now measured**:
  25 % of cycles per extra cycle of memory latency, on two independent
  programs. A future workload can be priced against that without
  re-running any of this.
- **The break-even clock is a ratio of two measured configurations and
  not a law.** It assumes the program is the same program, which it is
  — the ROM image hashes and the functional signatures are identical —
  and it assumes the period scales the whole design, which is what a
  single-clock part does.

---

## 8. Verification

### 8.1 `hw/soc/formal/soc_bus.sby` has been failing since `docs/47`

This has nothing to do with the memory and was found by re-running the
suite that the protocol change would have had to preserve.

```
SBY [soc_bus_bmc] engine_0: ##  BMC failed!
SBY [soc_bus_bmc] engine_0: ##  Assert failed in soc_bus:
                                soc_bus_props.v:417.9-417.45
SBY [soc_bus_bmc] summary: failed assertion
      soc_bus._witness_.check_assert_soc_bus_props_v_417_883
      at soc_bus_props.v:417.9-417.45 step 3
SBY [soc_bus_bmc] DONE (FAIL, rc=2)
```

**[fact, `make bus` at HEAD, `4dbabc3`, with `soc_bus_props.v` restored
from the index so the failure is HEAD's and not this document's]**

The counterexample, read out of `engine_0/trace.vcd`:

| cycle | `rst_ni` | `issue_en` | `mi_req_i` | `md_req_i` | `s_gnt_i` | `last_was_d` | `mi_gnt_o` |
|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 0 | 00000 | 0 | 0 |
| 1 | **1** | **0** | **1** | 0 | 11111 | 0 | **0** |
| 2 | 1 | 1 | **1** | **1** | 11111 | **0** | **0** |

**[fact]**

**F9 says a master that requests for two consecutive cycles, with nothing
outstanding and every slave ready, is granted in one of the two.** In
cycle 1 the instruction port is refused because `issue_en` is still 0. In
cycle 2 the fabric is open, but the data port also requests and
`last_was_d` is 0, so round-robin gives that cycle away. Two cycles of
requesting, no grant, and **the fabric is behaving exactly as designed**.

`issue_en` is `docs/47` section 5's change. That document replaced
`rst_ni && …` in the request gate with a local flop, because the old form
put the SoC's largest net into a combinational datapath, and it priced
the new one in `soc_bus.v`'s own comment:

> *"The cost is one flip-flop and one cycle of latency on the first
> transaction after a reset, once, at boot."*

**That cycle is inside F9's two-cycle bound. The comment was written and
the proof was not re-run.** `docs/48` and `docs/49` both modified no RTL
at all and had nothing to re-run; `docs/47` **changed the RTL of a
formally verified block** — its section 15 calls `soc_bus.v` "**the one
RTL change**" that document made — and its file table does not mention
`hw/soc/formal/` at all. **Every other formal suite in
`hw/soc/formal/` passes at HEAD** — apb, clint, busstat, wdog, wdogtmr
and regfile, all tasks — so this is one file and not a rotten directory
**[fact]**.

**THE REPAIR IS TO EXTEND, NOT TO RELAX**, and the difference is the
whole point:

- **F9a** — the arbiter clause gains `$past(issue_en)`. F9's own header
  says it is about the **arbiter**, so the arbiter's precondition, that
  the fabric is open, belongs in its antecedent.
- **F9b** — `assert (issue_en)` under `f_past_valid && $past(rst_ni) &&
  rst_ni`. **From the second cycle in which reset is high, the fabric is
  open, forever.** Without this, F9a's new antecedent would let the gate
  stay shut for an unbounded time and nothing would notice; with it, the
  pair is **strictly stronger** than the version that was failing, which
  said nothing at all about how long the gate may stay shut.

| task | engine | result |
|---|---|---|
| `bmc`, depth 24 | `smtbmc yices` | **PASS** |
| `prove`, k-induction, depth 12 | `smtbmc yices` | **PASS**, basecase and induction |
| `cover`, depth 24 | `smtbmc yices` | **PASS, 16 of 16 reached** (was 12 of 12) |

**[fact, `hw/soc/formal/soc_bus_*/PASS`]**

### 8.2 The two-cycle regime, as covers rather than as assertions

**No assertion in `soc_bus_props.v` changed for the memory**, for the
reason section 3.2 gives: the environment never constrained slave
response timing, so F1 to F9 were already proved for every latency. What
was added is a **witness**, because `docs/09` B.1's vacuity rule applies
to a new operating regime as much as to a new property — an assert set is
only as good as the reachable states it was checked on.

A ghost ages the oldest outstanding request at slave 0, the RAM, and four
covers name the regime:

- **L1** — slave 0 answers **exactly two cycles** after the grant.
- **L2** — and at **four or more**, so nothing has quietly fixed the
  latency at the one value the RTL happens to use.
- **L3** — **two requests in flight at a two-cycle slave** with the older
  one not yet returned, which the one-cycle memory never produced.
- **L4** — a grant to slave 0 in the same cycle as a response from it,
  with occupancy ≥ 2: the push-and-pop case of the ownership queue at a
  latency where it is **not the same request** being pushed and popped.

All four reachable; **16 of 16 covers reached** **[fact]**.

### 8.3 `soc_mem` gets a suite, at both latencies

Before this document `soc_mem` was one always block and the whole-SoC run
was proportionate verification of it. **A slave with two arms and a
parameter that selects between them is a protocol obligation**, and the
system-level run only exercises the memory through Ibex, so a defect the
core does not happen to provoke would not appear there.

`hw/soc/tb/cocotb/test_soc_mem.py`, **7 tests, run at both values of
`RDREG`, 7 of 7 each** **[fact]**:

| test | what it is for |
|---|---|
| `the_latency_is_the_one_that_was_built` | **the guard, and it runs first.** One request, count the cycles to its answer, compare with what the Makefile said it built. `docs/49` section 8.1's repair was to read the compiled object; here the suite can **measure the property the parameter controls**, which is stronger |
| `gnt_is_combinational_and_never_withheld` | `RDREG` changes latency, not throughput |
| `exactly_one_response_per_grant_back_to_back` | a request every cycle, 16 writes then 16 reads, tags checked in order; and `max_outstanding == LATENCY`, which is the assertion that the extra stage is a **pipeline and not a stall** |
| `every_response_is_exactly_latency_cycles_after_its_grant` | per response, not on average — a memory that dropped one and duplicated another would keep the totals |
| `a_write_is_answered_like_a_read` | section 3.1's decision, as its own property |
| `byte_enables` | `sb` and `sh` still land in the right bytes through the new stage |
| `read_only_answers_a_write_with_err` | `err` carried through the extra stage in the response cycle |

**The monitor's sampling phase is stated in the file** because it was got
wrong first: at the sample point, `rvalid_o` is the output of the edge
that has passed and `req_i`/`gnt_o` are the stimulus the **next** edge
will consume, so a response must be covered by grants counted **strictly
before** it. Getting that backwards makes "no response in the grant
cycle" fire on a correct design.

**Mutation-tested, and one mutation survives, which is reported rather
than hidden:**

| mutation | result |
|---|---|
| `assign rvalid_o = rv0` in the registered arm — forget to delay `rvalid` | **caught, 3 of 7 tests FAIL** |
| `rd1 <= rd0` unconditionally — drop the hold gate | **NOT caught, 7 of 7 pass** |

**[fact]**. The second is honest: **it is not observable through the
protocol.** `rdata` is meaningless outside an `rvalid` cycle, by rule 3,
and no master in this SoC reads it there. The gate exists so the two arms
of `soc_mem.v` and the two files behave identically between responses —
`soc_mem_sram.v`'s `A_DOUT` holds when `A_MEN` is low, and the
unregistered arm therefore holds too — which is a parity and power
argument, not a correctness one. A test that asserted it would be
asserting more than the protocol claims.

### 8.4 The fabric suite

`test_soc_bus.py` gains `test_two_cycle_memories_at_full_rate`: RAM and
ROM at two cycles and everything else at one, which is the part after
this document, driven at the rate the part runs it. **14 of 14 pass**
**[fact]**.

Its vacuity guard is the point of it. One master alone against a
two-cycle memory must reach `max_outstanding == 2`; **a fabric that
quietly serialised every access would pass every other assertion in that
file**, because serialising breaks no rule — it only destroys the
throughput this change depends on. The two-master phase does **not**
carry that assertion, and the reason is arbitration rather than latency:
with both masters asking, round-robin hands each of them every other
cycle, and every other cycle at two cycles of latency is an occupancy of
one. **That was found by asserting it and watching it fail**, which is
why it is written down.

### 8.5 Everything else, re-run

| | |
|---|---|
| `sw/tests/` whole suite | **342 passed** **[fact]** |
| `hw/soc/formal/` every job | apb, clint, busstat, wdog, wdogtmr, regfile: **all tasks PASS**; bus: **PASS after section 8.1** |
| `test_soc_bus.py` | **14 of 14** |
| `test_soc_mem.py` | **7 of 7 at `RDREG=0`, 7 of 7 at `RDREG=1`** |
| whole-SoC run | 22 checks, fail mask 0, in both configurations |
| watchdog escalation demo | full ladder, in both configurations |

---

## 9. The checkers, re-audited

`docs/41` section 6.6 counts the occasions on which a green result in
this repository was read as wider than the thing it examined, and
`docs/47` section 7 configured four of them out before its first run.
**Every one of those keys is carried into `rdreg1` unchanged**, and this
time that is not an argument from similar configurations: section 13
records that `full3`'s and `rdreg1`'s `resolved.json` files are
**identical, key for key**.

`hw/openlane/checker_audit.py`, which recomputes from the installed
LibreLane's own step classes whether each checker CAN fail, was run on
`full3` first as the reproduction and then on the run that produced this
document's sign-off number.

```
    registered Checker.* steps: 21
    of which the Classic flow runs: 19

GATES  Checker.SetupViolations   [corners] SETUP_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, violating nom_slow_1p08V_125C
GATES  Checker.HoldViolations    [corners] HOLD_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, all 0
GATES  Checker.MaxSlewViolations [corners] MAX_SLEW_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, violating all three
GATES  Checker.MaxCapViolations  [corners] MAX_CAP_VIOLATION_CORNERS = ["*"];
                                 corners measured 3, violating all three

    17 of 19 in-flow checkers gate fully.
    NOT gating in full: Checker.LintWarnings, Checker.WireLength
```

**[fact, `checker_audit.py hw/soc/pnr/runs/rdreg1`, ~~exit 0~~ exit 1]** *(~~exit 0~~ exit 1; corrected 2026-09-05 by `docs/71-layout-reproducibility.md` section 9)* — **17 of
19, the same as `docs/47`'s `full3`, `docs/48`'s `cap2` and `docs/49`'s
`syn2`**, and the same two exceptions: `Checker.WireLength` with no
threshold in either PDK and `Checker.LintWarnings` behind
`ERROR_ON_LINTER_WARNINGS`. The reproduction on `full3` prints the same
17 of 19 and names `nom_fast_1p32V_m40C` on hold, which is that run's
failure **[fact]**.

> **TWO ROWS HAVE TO BE READ TOGETHER HERE AND BOTH WERE CHECKED BEFORE
> ANYTHING WAS CLAIMED.**
>
> **`Checker.SetupViolations` examined three corners and names
> `nom_slow_1p08V_125C`.** This run FAILS setup, on a gate that was
> watching, and the +0.7772 ns of section 6.2 is an improvement in a
> number that is still red — not a run that closed because a checker
> stopped looking. `docs/41` section 6.6 lists eleven occasions on which
> this repository read a green result more widely than the thing it
> examined, and the defence against being the twelfth is that the audit
> is run on the run that produced the number.
>
> **`Checker.HoldViolations` reports `all 0`, at three corners, under the
> identical binding at which `full3` reported −0.2015 ns on 3 endpoints
> and failed.** The number moved; the gate did not. Section 6.4 still
> declines to attribute the movement, for a reason that is about the size
> of the movement and not about the gate.

The derate is audited where `docs/31` sections 3.2 and 10.3 say it can
be — not in `resolved.json`, which records the integer `5` either way —
and `rdreg1`'s flow-written SDC carries `set_timing_derate -early 0.9500`
and `-late 1.0500`, with **no `set_max_capacitance` and no
`set_max_transition`**, which is what makes section 6's max-cap and
max-slew comparisons comparisons against ONE limit, the library's own
**[fact]**.

---

## 10. What this does NOT cover

- **The register was measured at ONE point in the configuration space**,
  `docs/47`'s floorplan with `docs/47`'s keys, at one clock target. It
  was not combined with `SYNPRE`, with `docs/48`'s capacitance
  constraint, with a different density, or with a resynthesis at a
  different period. Section 12 is what a next document would do with
  that.
- **The cycle count is TWO programs and neither is a mission profile.**
  `hw/soc/tb/sw/test_ibex.c` is the bring-up program of `docs/38` section
  7 — a functional test with 22 checks, a watchdog escalation and a UART
  console — and `hw/soc/tb/sw/fi_supervisor.c` is `docs/46`'s partitioned
  supervisor. They agree to half a percent, which is evidence that the
  25 % is a property of the machine; it is **not** evidence that 25 % is
  what a mission payload would pay. **Nothing in this repository states
  what this part has to do per second**, and section 12 item 1 is the
  obligation that follows.
- **The 979 extra cells were not placed twice.** One netlist, one
  placement, one clock tree, one routing solution, against `docs/44`'s
  measured ~0.4 ns of flow noise which was measured on a 22,000-cell
  design and has not been re-measured at 28,000.
- **Nothing here is a gate-level simulation.** The behavioural evidence
  is RTL. `Yosys.EQY` is off, `soc_top`'s netlist has never been
  simulated, and the boot ROM still has no contents — so **the ROM whose
  read path this document registers cannot be read from in silicon
  yet**, which is `docs/47` section 4.4's open item and is untouched.
- **THIS IS STILL NOT A PHYSICAL SIGN-OFF.** `RUN_MAGIC_DRC`,
  `RUN_KLAYOUT_DRC`, `RUN_KLAYOUT_XOR` and `RUN_LVS` are 0, for the
  reason `docs/12` sections 7.5 and 8 measured. Nothing here is evidence
  that this layout is manufacturable.
- **The fast corner's macro Liberty is still characterised at −55 C
  against −40 C for the cells** (`docs/12` section 6.4a).
- **One clock, one mode, no scan, no test, ~~no power number~~.** *Corrected 2026-09-05: there was a power
  number, and it was in the `full3` run this document takes its timing
  baseline from.
  `OpenROAD.STAPostPNR` wrote a `power.rpt` per corner into
  `hw/soc/pnr/runs/full3/19-openroad-stapostpnr/` — 27.774 / 34.835 /
  46.095 mW at slow / typ / fast on a default activity assumption —
  found by `docs/53-workload-and-the-clock.md` section 7.1; measured at
  RTL activity by `docs/57-power-under-a-duty-cycle.md` section 5 it is
  **33.890 mW computing and 5.539 mW waiting at typ**, on a layout that
  does not contain the NPU. "One mode" is also wrong: `docs/57`
  section 4 finds a clock gate over 2,464 of the 3,085 flip-flops.*
- **`design__violations` still reads 0** on a run that fails setup;
  `docs/23` section 3.2's finding reproduced a fifth time.

---

## 11. Corrections to earlier documents

- **`docs/47` section 5 changed a formally verified block and did not
  re-run its proof, and `hw/soc/formal/soc_bus.sby` has been red since.**
  Section 8.1. The failing property is F9 and the counterexample is the
  sentence that document's own comment wrote down.
- **`docs/49` SECTION 11.1 SAYS THE REGISTER IS "THE ONLY MECHANISM …
  THAT WOULD REACH 20 ns". IT DOES NOT REACH 20 ns, AND THE PREDICTION
  WAS WRONG IN A SPECIFIC AND INSTRUCTIVE WAY.** Its arithmetic is
  correct as far as it goes: it splits the reported binding path in two
  and both halves have margin, and the run confirms the first half —
  **no path out of any macro violates at any corner.** What the
  arithmetic could not see is that the report it decomposed shows **one
  path**, and the design has **1,559 other violating endpoints behind a
  different launch point** that the macro path was ranking ahead of.
  Removing the worst path exposes the next one, at **−2.4257 ns**.
  **A decomposition of the critical path bounds what a change can buy
  ON THAT PATH; it says nothing about what the design does afterwards**,
  and this is the second time in three documents that a structural
  argument about one path has been overtaken by the population behind it
  — `docs/49` section 3.2 is the first, with the sign reversed. To
  `docs/49`'s credit its own section 14 item 2 predicts the outcome
  exactly; the two statements are in the same document and disagree.
- **`docs/49` section 11.1's split point is not where the register goes.**
  That document's arithmetic splits at the macro's `A_DOUT`; the register
  is after the bank and half multiplexers, which is 32 flip-flops per
  memory instead of 256 and 64. Section 4.
- **`docs/41` section 6.6's list gains a twelfth entry, and it is not a
  green result read too widely — it is a RED result nobody ran.** Every
  instance on that list so far is a check that passed while examining
  less than it appeared to. This one is a check that **failed for three
  documents and was never invoked**, which is the same defect with the
  sign reversed: the value of a gate is zero if nothing pulls it, whether
  it would have said yes or no.
- **A fifth `soc_mem` parameter list existed, in
  `sw/tests/test_soc_synthesis_guards.py`, and nothing compared it.**
  That file's own subject is the memory boundary going stale. Section 4.
- **`docs/23` section 3.2's `design__violations` finding** is reproduced
  a fifth time.

---

## 12. What the next block should be

1. **DECIDE THE TARGET BEFORE SPENDING ANOTHER CYCLE ON IT, and this
   document is the first one that can price the decision.** `docs/48`
   section 7a and `docs/49` section 11.2 both refused to revise 50 MHz
   because no document derived a throughput requirement from it. That is
   still true, and it is now expensive rather than merely untidy:
   **43.10 MHz with a one-cycle memory beats 50 MHz with a two-cycle one
   by 7.94 % on the bring-up program and by 8.4 % on `docs/46`'s
   supervisor** **[estimate, section 7]**, so the target and the design
   are not independent choices and the project has been treating them as
   if they were. **What is owed is one sentence in `docs/05` or `docs/09`
   saying what the part has to do per second.** Until it exists, "closes
   at 20 ns" is not a goal, it is a habit.
2. **`SYNPRE`, whose reversal condition `docs/49` wrote and this document
   has now met.** That document declined `SYNPRE` because the binding
   path was behind a macro it cannot reach, and said: *"if the memory
   read is registered and the binding path becomes the read-address
   group, `SYNPRE` acts directly on the new worst path and this
   measurement has to be redone."* Section 6 measures that the binding
   path IS now the read-address group. The two changes compose on paper
   and the cost is one more `syn1`/`syn2` pair — **but item 1 comes
   first, because `SYNPRE` costs +6.9 % of the standard-cell area to
   improve a frequency whose value in seconds nobody has stated.**
3. **`mtime`.** Ranked first by `docs/41` section 7.4 and `docs/44`
   section 11, second by `docs/43`, third by `docs/45`, fourth by
   `docs/47`, second by `docs/48`, third by `docs/49`, and it is on this
   document's binding path too. A 64-bit free-running counter at the far
   end of a broadcast bus remains the most-deferred item in this record.
4. **A cache, or a wider fetch, which is the change this document's
   measurement actually argues for.** The 25 % is not the memory's
   latency, it is the absence of anything between the core and the
   memory: 0.9714 cycles per RAM response, on a two-stage core with no
   cache. **Any structure that answers a fraction of accesses in one
   cycle converts most of that back**, and it would do so for the
   unregistered design as well. This is a bigger change than anything in
   `docs/47` to `docs/50` and it is out of scope for a timing-closure
   block, but it is what the numbers point at and no document has named
   it before.
5. **ECC on the memories** and **how the boot ROM gets its contents** —
   `docs/47` section 11 items 1 and 2, untouched here. The second still
   decides whether this part can boot, and this document has made it
   sharper by putting a register on a read path that has nothing to read.
6. **A gate-level simulation of `soc_top`**, still open, still blocked on
   item 5.

**And one thing that should be done regardless of any of the above:
re-run `hw/soc/formal/` in whatever runs the tests.** Section 8.1's
finding is not that F9 was wrong; it is that a proof stayed red across
three documents because nothing invoked it. `sw/tests/` runs on demand
and the formal jobs do not run at all unless somebody types `make`. That
is a gap in the process, not in the properties.

---

## 13. Cost

| | |
|---|---:|
| synthesis, `SOC_MEM_RDREG=1` | 38 s |
| **`rdreg1`, netlist to sign-off, one run** | **97.3 min** of summed step runtime over 60 steps |
| of which `OpenROAD.DetailedRouting` | **36 min 40 s**, against `full3`'s 22 min 52 s |
| of which `OpenROAD.ResizerTimingPostGRT` | **23 min 06 s**, against `full3`'s 22 min 28 s |
| of which `OpenROAD.ResizerTimingPostCTS` | 13 min 10 s |
| the six whole-SoC simulations of sections 3 and 5 | about 8 min in total |
| the four supervisor runs of section 7 | under 3 min in total |
| the formal suites, all seven jobs | under 2 min |
| the cocotb suites, `soc_bus` and `soc_mem` at two parameter values | under 1 min |
| `sw/tests/`, 342 tests | 3 min 25 s |
| the seven synthesis runs of section 2.2 | about 11 min |
| **total for this document** | **about 2.1 h**, of which the layout is 1 h 37 min wall |

**[fact, `runtime.txt` per step and wall times; the host is a shared
20-thread machine and the figures are quoted as costs and not as
precision]**

**THIS IS A QUARTER OF WHAT `docs/49` COST, AND THE REASON IS THE SAME
979 CELLS.** That document spent **9.0 h**, of which
`OpenROAD.ResizerTimingPostGRT` alone was **6 h 19 min against `full3`'s
22 min 28 s**, and attributed the 16.9x to a 6.9 % larger netlist making
the targeted timing repair harder. **`rdreg1`'s same step is 23 min 06 s
— 2.8 % longer than the baseline's, for a 3.6 % larger netlist.** The
step that did grow is detailed routing, 22 min 52 s to 36 min 40 s, on
1.9 % more wire. Whatever else this change costs, **it does not cost the
flow**.

**ONE RUN RATHER THAN `docs/47`'s AND `docs/49`'s TWO.** Those documents
ran a pair — post-GRT keys off, then a resume from post-CTS with them on
— because they were attributing the keys. There is nothing to attribute
here: the keys are `hw/soc/pnr/config.json`'s own values in both the
baseline and this run, and steps 1 to 30 do not read them, so a single
straight run is exactly `full2` followed by `full3` with no intermediate
artefact. **`resolved.json` for `full3` and `rdreg1` are
IDENTICAL — zero differing keys, `VERILOG_FILES` included** — because the
netlist reaches the flow through the initial state file and not through
the configuration **[fact, a key-by-key comparison]**. That is a stronger
control than `docs/47` or `docs/49` had: **the only difference between
this sign-off and `docs/47`'s is which netlist went in.**

---

## 14. Files touched

| File | Change |
|---|---|
| `hw/soc/rtl/soc_mem.v` | `RDREG` and the two response arms |
| `hw/soc/rtl/soc_mem_sram.v` | the same, with the register after the bank multiplexers |
| `hw/soc/rtl/soc_top.v` | `MEM_RDREG`, defaulting to 0 |
| `hw/soc/flow/syn_soc_top.sh` | `SOC_MEM_RDREG`; `RDREG` in both generated boundary models |
| `hw/soc/flow/sim_soc.sh` | `SOC_MEM_RDREG`, the per-memory attribution knobs, `SOC_PROBE`, and the generalised arm check |
| `hw/soc/flow/fi_core.sh` | `SOC_MEM_RDREG` and its arm check, so `docs/46`'s supervisor runs at both latencies |
| `hw/soc/tb/soc_bus_probe.v` | **new** |
| `hw/soc/tb/cocotb/test_soc_mem.py`, `Makefile.soc_mem` | **new** |
| `hw/soc/tb/cocotb/test_soc_bus.py` | one test |
| `hw/soc/formal/soc_bus_props.v` | F9a, F9b, the latency ghost, four covers |
| `sw/tests/test_soc_memory_guards.py` | **new** |
| `sw/tests/test_soc_synthesis_guards.py` | the blackbox parameter list is derived |
| `sw/tests/test_soc_regfile_guards.py` | the SYNPRE check follows the generalised mechanism |
| `docs/50-memory-read-register.md` | this document |
| `docs/00-index.md` | one row |

**`hw/soc/rtl/soc_bus.v` IS NOT IN THIS LIST AND THAT IS SECTION 3.2's
RESULT.** No file under `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or
`hw/openlane/` was modified **[fact, `git status`]**.

---

## 15. Reproducing this

```
V=$HOME/Documents/caravel-lif-crossbar/.venv-flow/bin/python
export PDK_ROOT=$HOME/.ciel

# ---- section 2: the instrument -------------------------------------
SOC_MEM=sram hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s50-repro-sram
sed -e 's/u_ram\.rv0/u_ram.rvalid_o/g; s/u_rom\.rv0/u_rom.rvalid_o/g' \
    -e 's/u_rom\.er0/u_rom.err_o/g' \
    hw/soc/out/s50-repro-sram/soc_top.netlist.v > /tmp/renamed.v
diff /tmp/renamed.v hw/soc/out/s47-sram/soc_top.netlist.v   # identical
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/full3      # -3.2029 / 2003

# ---- sections 3 and 5: the cycle count and the probe ----------------
SOC_PROBE=1                        hw/soc/flow/sim_soc.sh hw/soc/out/s50-p-base
SOC_PROBE=1 SOC_MEM_RDREG=1        hw/soc/flow/sim_soc.sh hw/soc/out/s50-p-rdreg
SOC_PROBE=1 SOC_MEM_RDREG=1 SOC_ROM_RDREG=0 \
                                   hw/soc/flow/sim_soc.sh hw/soc/out/s50-p-ram
SOC_PROBE=1 SOC_MEM_RDREG=1 SOC_RAM_RDREG=0 \
                                   hw/soc/flow/sim_soc.sh hw/soc/out/s50-p-rom
SW_DEFINES=-DWDOG_RESET_DEMO SOC_MEM_RDREG=1 \
                                   hw/soc/flow/sim_soc.sh hw/soc/out/s50-wdog-1

# ---- section 7: docs/46's supervisor, at both latencies -------------
# VVP is the oss-cad-suite one; `vvp` off PATH is a different runtime and
# refuses the object with "input file 14.0 can not be run with 12.0".
eval "$(make --no-print-directory -f hw/soc/tools.soc.mk printvars)"
for M in 0 1; do
  SOC_MEM_RDREG=$M FI_WORKLOAD=supervisor SW_DEFINES="-DSUP_FREERUN" \
    hw/soc/flow/fi_core.sh hw/soc/out/s50-sup-free-$M
  "$VVP" hw/soc/out/s50-sup-free-$M/tb_soc_fi.vvp +armed=1 +budget=400000
  SOC_MEM_RDREG=$M FI_WORKLOAD=supervisor SW_DEFINES="-DSUP_TICK_PERIOD=8912" \
    hw/soc/flow/fi_core.sh hw/soc/out/s50-sup-tt-$M
  "$VVP" hw/soc/out/s50-sup-tt-$M/tb_soc_fi.vvp +armed=1 +budget=600000
done

# ---- sections 4 and 6: the netlist and the layout -------------------
SOC_MEM=sram SOC_MEM_RDREG=1 hw/soc/flow/syn_soc_top.sh 20 hw/soc/out/s50-rdreg
grep -c g_rd2 hw/soc/out/s50-rdreg/soc_top.netlist.v   # nonzero
grep -c g_rd1 hw/soc/out/s50-rdreg/soc_top.netlist.v   # 0
SOC_MEM=sram hw/soc/flow/sta_soc_top.sh 20 hw/soc/out/s50-rdreg

SKIP="-S Yosys.Synthesis -S Checker.YosysUnmappedCells
      -S Checker.YosysSynthChecks -S Checker.NetlistAssignStatements"
SYN_NETLIST=$PWD/hw/soc/out/s50-rdreg/soc_top.netlist.v \
hw/soc/flow/pnr_soc_top.sh rdreg1 --overwrite -F Yosys.JsonHeader $SKIP \
    -i hw/soc/pnr/state/syn_soc_top.state.json

$V hw/openlane/signoff_report.py hw/soc/pnr/runs/rdreg1
$V hw/openlane/checker_audit.py  hw/soc/pnr/runs/rdreg1

# ---- section 8: verification ----------------------------------------
cd hw/soc/formal && make && cd ../../..
cd hw/soc/tb/cocotb && \
  make -f Makefile.soc_bus && \
  make -f Makefile.soc_mem && \
  make -f Makefile.soc_mem RDREG=1 SIM_BUILD=sim_build_soc_mem_rdreg \
       COCOTB_RESULTS_FILE=results_soc_mem_rdreg.xml && cd ../../../..
.venv/bin/python -m pytest sw/tests/
```

`hw/soc/out/`, `hw/soc/pnr/runs/`, `hw/soc/pnr/config.resolved.json` and
`hw/soc/tb/cocotb/sim_build*/` are gitignored.
