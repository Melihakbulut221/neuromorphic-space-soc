# 63 — riscv-formal on the management core: an ISA proof, and a defect in the specification

`docs/09-formal-verification-plan.md` part B track 1 named riscv-formal
in August 2026 and nothing was ever run with it. This document is that
bring-up. It fetches riscv-formal at a pinned commit, binds it to the
`small-pmp` Ibex this SoC is built from, and runs it.

**This document is both phases.** Sections 1-13 are phase 1, the STOCK
core with upstream's register file, and their numbers are unchanged
since that work was committed. Part 2, sections 14-19, is phase 2: the
SECDED register file of `docs/43-core-hardening.md` section 6
substituted, at the same settings, and the delta between the two runs.
Phase 1 first is not caution for its own sake:
a phase-2 failure with no phase-1 baseline cannot distinguish "our
harness is wrong" from "our substitution broke the core", and this
document contains four separate demonstrations that a harness for this
is easy to get wrong -- and a fifth finding, in riscv-formal's own model
of the ISA, which is the one that argues hardest for having run it.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
intended and not done.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was modified,
`hw/tb/Makefile.fi` was not invoked, and section 12 lists every file
this work touches.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| Does riscv-formal bind to this Ibex? | **Yes, and not the way `docs/09` assumed.** `docs/09` wrote that Ibex "exposes RVFI trace ports, which is what a riscv-formal binding would attach to". It does — in SystemVerilog. `hw/soc/gen/`, the RTL this SoC is actually built from, contains **zero** occurrences of the string `rvfi` [fact]. Section 3 |
| Does the sv2v path carry the RVFI trace? | **Only halfway.** sv2v converts it with zero errors, but Ibex's RVFI block reads sixteen signals out of submodules by **hierarchical reference** and Yosys's Verilog-2005 front end cannot resolve one of them. A second front end was required. Section 3.2 |
| What is proved? | **70 of 79 bounded checks PASS and 79 of 79 cover obligations PASS** [fact]. That is 62 of the 70 RV32IMC instruction models and 8 of the 9 consistency checks, at the depths in section 8.1. **The eight M-extension instructions — `mul`, `mulh`, `mulhsu`, `mulhu`, `div`, `divu`, `rem`, `remu` — have no formal result at all**, six stopped on solver cost and two against a defective model; sections 8.4 and 8.5 |
| What failed? | **Three checks failed and six were stopped without a verdict, and not one of the nine is a defect in the core.** `insn_div` and `insn_rem` fail because riscv-formal's own models compute an UNSIGNED result — Ibex is right (section 7.5). `liveness` fails at check cycle 50 on a trace whose next instruction is a 37-cycle divide, which is a statement about the bound (section 8.3). The four multiply checks, `divu` and `remu` were stopped after 35-40 minutes each because a bit-blasting solver does not close multiplier equivalence (section 8.4) |
| Did the run find defects? | **Five. Three in this project's harness, one in Ibex's RVFI trace, and one in riscv-formal's own model of `div` and `rem`, which compute an UNSIGNED result. Not one of them is in Ibex's execution of an instruction.** Section 7 |
| Is it a proof of ISA correctness? | **No, and the gap is not small.** Every result here is a BOUNDED check at a stated depth, under the nine assumptions ledgered in section 4.1, over a core whose CSR file, memory system, netlist and timing are all outside it. Sections 2 and 6 |
| Is phase 2 ready? | It was, and it has been run. Section 10 states the plan; Part 2 is the result |
| **Phase 2: does the SECDED register file change the core's ISA behaviour?** | **No check that passed on the stock core fails on the substituted one.** 68 of the 79 bmc checks have an identical verdict, all 79 cover jobs pass in both, and the three failures are the same three for the same reasons — two of them riscv-formal's own defective model, reproduced on fresh operands. Sections 16 and 17 |
| **What phase 2 does NOT cover** | The **eight M-extension instructions have no verdict in either run**, so the delta over them is undefined rather than clean; and everything section 6 excludes is excluded in both. Section 16.3 |
| **Is the substituted core harder to prove?** | **Yes, by about half again.** CPU x1.55 over the run, x1.21 median over the 62 checks comparable per-check, **x1.92 over the whole cover set**. Section 18 |

**What is now proved about this core that was not proved before.** For
**62 of the 70 instructions of RV32IMC** — every one except the eight of
the M extension, which sections 8.4 and 8.5 account for — on every
execution the core can reach from reset within that check's depth, under
the nine assumptions of section 4.1, the
instruction's effect on the architectural state (destination register
and value, source register numbers, next PC, memory address, byte masks,
store data, and whether it traps) agrees with riscv-formal's formal
model of the RISC-V ISA. Add to that eight consistency properties over
the retirement stream, and a bounded proof that the core never has more
than two bus requests in flight.

Before this document the evidence for any of that was
`docs/38-ibex-bringup.md` section 7: **one** self-checking C program,
eleven checks, 131,694 cycles, one path through the machine. This is a
different kind of claim, and section 6 is at length about how much
smaller it is than the phrase "formally verified" would suggest.

---

## 2. What riscv-formal is, and what it is not

**What it is [fact].** riscv-formal
(https://github.com/YosysHQ/riscv-formal) is a formal description of the
RISC-V instruction set written as synthesisable Verilog — one module per
instruction, computing the architectural next state from the
architectural current state — plus a set of consistency checkers, plus a
generator that turns a configuration file into one SymbiYosys job per
check. It binds to any core that exposes an **RVFI** retirement trace: a
bundle of signals reporting, for each retired instruction, what it was
and what it did.

The instruction models are generated from
`riscv-formal/insns/generate.py`, which upstream validates against the
Spike reference simulator. This project does not re-derive them and does
not audit them; they are trusted in the sense of `docs/09` C.4 item 7,
alongside Yosys, sby and the solvers.

**What it is not, said before the results rather than after.** It is not
seL4. `docs/09` part A is the reference and part A.4 is the arithmetic:
seL4's functional-correctness proof alone was about 20 person-years for
a 10 kSLOC artifact, it is a *refinement* between a machine-checked
abstract specification and an implementation, and its proofs are
unbounded and machine-checked in Isabelle/HOL. Nothing here is any of
those things:

- **These are bounded model checks.** Each one asks whether a property
  holds on every execution of at most N cycles from reset. A check that
  passed at depth 20 says nothing whatever about cycle 21. `docs/09`
  C.4 item 6 forbids reporting a bounded result as "proven" and this
  document obeys it: the depth is in every table.
- **There is no refinement relation.** riscv-formal compares one
  retirement against one instruction model. It says nothing about the
  core's internal state, and there is no abstraction function relating
  the two.
- **The specification is Verilog, not a theorem prover's logic.** Its
  correctness rests on upstream's Spike cross-check, not on a proof.
- **The proof obligations are discharged by SMT solvers**, which are
  larger and less scrutinised trusted components than Isabelle's kernel.

What it *is* is still the largest single verification result available
to this project, and it is a different KIND of result from the ones the
repository already carries. Those are **87 sby tasks across 16 property
sets** -- eight under `formal/` for the pilot and eight under
`hw/soc/formal/` for the SoC fabric, counted from the `[tasks]` section
of every `.sby` file in the tree [fact] -- and every one of them is a
property set over an individual block: a named list of things that must
never happen, written by the same person who wrote the block.
This checks the core's instruction-by-instruction behaviour against a
model of the ISA it claims to implement — a specification written by
someone else, before this core was chosen.

---

## 3. Getting the trace out of the core, which is where the work was

### 3.1 The RVFI ports are not in the RTL this SoC is built from

`docs/09` B.1 records that "Ibex exposes RVFI trace ports, which is what
its co-simulation checking is built on and what a riscv-formal binding
would attach to". True of the SystemVerilog. Not true of what this
project builds:

```
grep -c rvfi hw/soc/gen/ibex_top.v      ->  0
```

**[fact]**. The ports are inside `` `ifdef RVFI `` (`ibex_top.sv` lines
138-183 and 474-519) and `hw/soc/flow/sv2v_ibex.sh` passes
`--define=SYNTHESIS --define=YOSYS` and nothing else, because that is
upstream's own synthesis invocation and `docs/38` section 4.1 reused it
verbatim.

So a second conversion is needed, and it is a **second tree and not a
replacement**: `hw/soc/gen/` is what every area, timing, fault-injection
and cocotb number from `docs/38` to `docs/62` was measured from, and it
must go on reproducing byte-identically. `sv2v_ibex.sh` gained an
optional trailing argument for extra defines; with none passed it
converts exactly what it converted before, and that was checked rather
than assumed — a fresh three-argument run into a scratch directory
`diff`s empty against `hw/soc/gen/` [fact].

| | `hw/soc/gen` | `hw/soc/genrvfi` |
|---|---:|---:|
| sv2v defines | `SYNTHESIS`, `YOSYS` | `SYNTHESIS`, `YOSYS`, **`RVFI`** |
| Files | 34 | 34 |
| Lines of Verilog-2005 | 15,873 | **16,770** |
| sv2v errors / warnings | 0 / 0 | **0 / 0** |
| `rvfi` occurrences in `ibex_top.v` | 0 | **132** |

**[fact]**. `docs/38`'s headline — sv2v converts Ibex with zero errors
and zero patches — survives the RVFI define intact.

### 3.2 Ibex's RVFI reads submodules by hierarchical reference, and Yosys cannot

This is the finding that decided the shape of the harness.

`ibex_core.sv`'s RVFI block does not receive everything it reports
through ports. It reaches into the instantiated submodules:

```
assign rvfi_trap_id = (id_stage_i.controller_i.exc_req_d |
                       id_stage_i.controller_i.exc_req_lsu) &
                      ~(id_stage_i.ebrk_insn &
                        id_stage_i.controller_i.ebreak_into_debug);
```

There are **sixteen distinct such references**, up to three levels deep,
across four submodules [fact, counted in `hw/soc/genrvfi/ibex_core.v`]:

| Submodule | References |
|---|---|
| `id_stage_i.controller_i` | `exc_req_d`, `exc_req_lsu`, `exc_req_wb`, `id_exception_o`, `wb_exception_o`, `rvfi_flush_next`, `ebreak_into_debug`, `irq_nm_int` |
| `id_stage_i` | `ebrk_insn` |
| `if_stage_i` | `instr_valid_id_d`, `instr_new_id_d` |
| `cs_registers_i` | `mip`, `mhpmcounter`, `cpuctrlsts_ic_scr_key_valid_q`, `mcycle_counter_i.counter_val_o` |
| `load_store_unit_i` | `resp_is_cap_q` |

sv2v carries them through verbatim — it is a translator, not an
elaborator, and cross-module references are legal SystemVerilog and
legal-ish Verilog. Yosys's Verilog-2005 front end then treats every
dotted name as an implicitly declared net and stops:

```
hw/soc/genrvfi/ibex_core.v:1580: ERROR: Don't know how to detect sign
                                 and width for AST_AUTOWIRE node!
```

**[fact]**. This is not a warning and there is no flag for it.

**The route out was already in the repository.** `docs/38` section 6
established that the pinned oss-cad-suite ships `slang.so`, a
SystemVerilog front end that reads this design, and that it was blocked
by exactly one construct. Reading the **sv2v output** with it resolves
all sixteen references. So the harness reads the core with
`read_slang` and everything else with Yosys's own front end;
riscv-formal's `[script-sources]` configuration section, which is
emitted between its `read -sv` line and its `prep`, is the hook.

**What that costs and it is not nothing.** The front end that elaborates
the core in this document is **not** the front end that elaborates it in
`hw/soc/syn/ibex_syn.ys.in`, which is what builds the SoC. Section 6
carries this as an assumption. `docs/38` section 5 measured the two
front ends against each other on the same source and got 229,120.13 um2
and 1,972 flip-flops against 231,167.49 um2 and 1,970 — 0.89 % and two
flip-flops apart — which is a corroboration and not an equivalence
proof, and it was measured on the SystemVerilog rather than on this
tree.

### 3.3 The one construct slang refuses, and where the rewrite goes

`read_slang` fails on `ibex_top.v:678`, which is `ibex_top.sv:659`
carried through sv2v unchanged — the same line `docs/38` section 6
found:

```
reg unused_scramble_inputs = <expression over seven nets>;
error: reading net state during design initialization unsupported
```

**[fact]**, seven errors, one per net in the initialiser. `docs/38`
proposed rewriting it as a declaration plus a continuous assign —
"semantically identical, five lines, in one file" — and proposed doing
it to Ibex.

**Doing it to Ibex is what would end "patches required to Ibex: zero",
so it is done to the generated file instead.**
`hw/soc/flow/rvfi_slangfix.py` rewrites that one declaration and writes
the result into the run's work tree. It is the same rule
`hw/soc/flow/ibex_fault_port.py` already follows and `.gitignore`
already states: derived from a pinned input by a tracked script, never
vendored, never edited by hand. It refuses to run unless it finds the
construct **exactly once**, so an upstream commit that adds another is
an error and not a quietly different core. `hw/soc/ext/ibex` and
`hw/soc/ext/riscv-formal` both stay `git status`-clean, and
`make -f hw/soc/tools.soc.mk soc-toolcheck` now fails if the
riscv-formal checkout is dirty [fact].

---

## 4. The harness

`hw/soc/rvformal/wrapper.sv` instantiates `ibex_top` at
`hw/soc/rtl/soc_top.v`'s nineteen parameters, drives its two memory
ports and five interrupt lines from free solver-chosen inputs, and
exports the RVFI trace. `hw/soc/flow/rvformal.sh` builds the work tree
riscv-formal's generator requires, out of symlinks to the pristine
checkout plus the tracked files, and runs the jobs.

**The parameters are not in the wrapper, and that is forced.**
`read_slang` elaborates `ibex_top` completely, so the module it leaves
in RTLIL is not parametric and an override at the instantiation is a
hard error rather than an override. They go on the `read_slang` command
line as `-G` in `hw/soc/rvformal/checks.cfg.in`, and
`hw/soc/rvformal/params.sh` reads all nineteen back out of that file and
out of `soc_top.v` and fails if any has moved. It runs FIRST, before
anything is generated, so a moved parameter is an error at setup and not
79 green checks about a different core. It is the same guard
`hw/soc/formal/Makefile`'s `wdog_tmr_params` target applies to the
watchdog's copied TMR masks. Mutation-tested: changing `PMPNumRegions`
from 4 to 8 and deleting the `SecureIbex` line are both caught, with the
parameter named [fact].

### 4.1 The assumption ledger

Every one of these narrows the set of traces the solver considers, and
the proofs are only as strong as this list is short and true. The
`[defines]` block of `checks.cfg.in` puts the switchable ones into every
generated `.sby` file in plain text, so `grep IBEX_ASSUME` over the work
tree lists what was assumed, per check, without reading any Verilog.

| # | Assumption | Where | Why, and what it costs |
|---|---|---|---|
| A1 | A bus grant only in a cycle the core is requesting | wrapper §3, always on | Interface contract. Without it the first counterexample is a bus that grants requests nobody made |
| A2 | A bus response only against a grant given in an **earlier** cycle | wrapper §3, always on | Ibex's own documentation: "This may happen one or more cycles after the grant has been received" (`doc/03_reference/load_store_unit.rst`) [fact]. Section 7 defect 2 is what happens without the word "earlier" |
| A3 | Bus errors do not occur (`instr_err_i`, `data_err_i` tied low) | wrapper §4, always on | Ibex reports a bus error as `rvfi_trap` on the retiring instruction; riscv-formal can express that only through `rvfi_mem_fault*`, which Ibex has no port for. Upstream's own `dv/formal` states the same exclusion. **Cost: nothing here says anything about the core's behaviour on a bus error, and `hw/soc/rtl/soc_bus.v` raises one on every unmapped address** |
| A4 | The retired instruction stream stays in M-mode | `IBEX_ASSUME_MMODE` | With every `pmpcfg` at its reset value, U-mode denies every access (no matching entry outside M-mode fails), so without this the shortest counterexample to every load and store check is "enter U-mode, then execute it" |
| A5 | No retired instruction writes `mstatus`, `mseccfg`, `mseccfgh`, `pmpcfg*` or `pmpaddr*` | `IBEX_ASSUME_NO_PROT_CSR_WRITE` | These are the registers that make the PMP deny in M-mode. Section 7.1 is the version of this assumption that named only the last two of them. **Cost: the PMP is elaborated and in the load/store path of everything below, and none of this proves PMP enforcement** |
| A6 | Memory grants within 2 cycles and responds within 4 | `IBEX_FAIRNESS`, `liveness` and `hang` only | Only the two checks that ask whether the core makes progress need it; a safety check that does not need an assumption should not carry one. Ibex's own `dv/formal` bounds the same thing at ten cycles — this is **tighter**, i.e. stronger, and the last two paragraphs of section 7.2 are why |
| A7 | The core's clock gate passes the clock through | `hw/soc/rvformal/prim_clock_gating_formal.v` | A gated clock makes the design multi-clock and sby's single-clock model cannot represent it. Upstream assumes the same thing in one line: "We assume `ResetAll` and no clock gating" (`dv/formal/README.md`) [fact]. **Cost: the core keeps clocking through the sleep state a `wfi` enters** |
| A8 | Debug mode is never entered (`debug_req_i` tied low) | wrapper §2, always on | Debug entry diverts the PC to an address no ISA model describes. Upstream excludes it too |
| A9 | `rvfi_intr` is treated as set on the instruction after a trap or an `mret` | wrapper §5a | An **adapter**, not an assumption about the core, and section 7.4 is the finding behind it. It relaxes riscv-formal's PC checks across a handler entry or return. **Cost: the PC checks are blind to the handler entry address — which riscv-formal could not check anyway, having no `mtvec` or `mepc` model to compare against** |

Interrupts are **not** assumed away: `irq_software_i`, `irq_timer_i`,
`irq_external_i`, `irq_fast_i` and `irq_nm_i` are free every cycle. What
that buys is narrow and section 6 says so.

**An incomplete assumption set here is loud, not silent, and that is
what makes this shape of harness safe to iterate on.** Too weak, and a
check fails with a counterexample naming the register or the bus cycle
that did it — which is how A2 and A5 reached their present form. Too
strong, and the check becomes vacuous — and the cover run of section 5
fails, because the instruction can no longer retire at the check cycle.
Both directions have an alarm.

---

## 5. Vacuity control: the second run that exists because the first one cannot see itself

`docs/09` B.1 makes this a decision of record: "Every assert set ships
with cover obligations; a target with passing asserts but failing covers
is *red*."

It matters more here than usual. Every instruction check begins
`assume(spec_valid)` at its check cycle — it constrains the trace to one
in which *this* instruction retires exactly then. If the depth is too
small for the core to get there, the assumption is unsatisfiable, there
is no trace at all, and **the bounded model check passes having examined
nothing**. That is a green result exactly as wide as the thing it
examined, which `docs/41-watchdog-hardening.md` section 6.6 catalogues
by name -- eight instances as of its writing, in `docs/28`, `docs/34`,
`docs/36`, `docs/38` twice, `docs/39` and `docs/40` twice.

The failure mode is not hypothetical for this core. Ibex's RV32MFast
divider is sequential and takes about 37 cycles on its own, so
`insn_div` at the instruction default depth of 20 would be a vacuous
pass.

So `hw/soc/rvformal/checks.cfg.in` is expanded **twice**, into
`checks.cfg` (`mode bmc`) and `cover.cfg` (`mode cover`), and both are
generated and both are run. The same check files carry four `cover`
statements each — `spec_valid`, `spec_valid && !trap`,
`check && spec_valid`, `check && spec_valid && !trap` — that sby ignores
in `bmc` mode and checks in `cover` mode. A cover run that fails is an
instruction that **cannot retire at its check cycle**, which is exactly
the vacuity alarm.

**And there is a first line of defence that was found by reading the
tool rather than by assuming it.** `yosys-smtbmc` checks the
satisfiability of the assumptions at the check step BEFORE it checks any
assertion, and if they are unsatisfiable it reports the status
`PREUNSAT` — which `sby_engine_smtbmc.py` maps to **ERROR**, not to
PASS [fact, read out of `yosys-smtbmc` line 2035 and
`share/yosys/python3/sby_engine_smtbmc.py` line 237 of the pinned
oss-cad-suite]. So the crudest form of vacuity — "there is no trace at
all" — cannot be reported as a green result by this flow, on any of the
79 checks.

**The cover run is still not redundant, and the difference is exactly
one word.** `PREUNSAT` would fire only if NO trace satisfies the
assumptions. The cover obligation is stronger: `cover(check &&
spec_valid && !trap)` requires the instruction to retire at the check
cycle **and not trap while doing it**. A depth at which the only
reachable instance of an instruction is a trapping one satisfies the
assumptions, passes the BMC, is not PREUNSAT, and has checked almost
nothing — and that is not a hypothetical shape, because section 7.1 is
a configuration in which every instruction retired with `rvfi_trap` set.

**What the cover run does NOT reach.** Of riscv-formal's checkers, only
`rvfi_insn_check.sv` (four covers) and `rvfi_ill_check.sv` (one) carry
cover statements; `reg`, `pc_fwd`, `pc_bwd`, `causal`, `unique`,
`liveness` and `hang` carry none [fact, counted]. Their cover-mode jobs
therefore have nothing to check, and for those seven the anti-vacuity
argument is `PREUNSAT` alone plus the `cover` check's own obligation
that two instructions retire at all. That is weaker, it is stated here
rather than left to be inferred from a table of passes, and closing it
would mean writing cover statements into riscv-formal's checkers — which
is a change to the fetched checkout and therefore not something this
flow does.

**The result: 79 of 79 cover jobs PASS** [fact]. Every instruction in
the set can retire at its own check cycle without trapping, the all-zero
word can retire and trap, and two instructions can retire at all. No
depth in section 8.1 is vacuous, including the four at cycle 55 that
were chosen for the divider — and including the six whose BMC side was
stopped without a verdict, so the reason those six have no result is
solver cost and not an unreachable depth.

The cover set cost **1,122 job-seconds** against the BMC set's 7,790
[fact]: finding one witness is cheap and proving no counterexample
exists is not, which is the whole shape of this exercise in one ratio.

---

## 6. What this does NOT cover

At length, because the phrase "formally verified against the RISC-V ISA"
will otherwise be read as much wider than it is.

**Bounded, not proven.** Every result is a bounded model check to a
stated depth. There is no k-induction and no PDR anywhere in this
document, and no unbounded result. `mode prove` is available in
riscv-formal's configuration and was not attempted: the instruction
checks would need an inductive invariant over Ibex's whole
microarchitecture, which is a research project and not a bring-up.
`docs/09` C.4 item 6 governs how these are reported and every table
here carries its depth.

**The CSR file is not checked at all.** riscv-formal's `csrw`, `csrc_*`
and `csr_ill` checks bind to `rvfi_csr_<name>_{rmask,wmask,rdata,wdata}`
ports. Ibex has none — it carries `rvfi_ext_*` signals for its own Spike
co-simulation instead. Not configuring any `[csrs]` is what leaves those
checks ungenerated, and the consequence is that **nothing here says
anything about `mstatus`, `mtvec`, `mepc`, `mcause`, `mie`, `mip`,
`mcycle`, `minstret` or the PMP registers**. For a core whose software
architecture (`docs/09` part B track 3, option S2) rests on PMP and on a
trap vector, that is the largest single gap in this document.

**PMP enforcement is not proved.** A4 and A5 exist precisely to keep the
PMP transparent so the instruction models, which are privilege-blind,
can be compared at all. The hardware is present, elaborated, and in the
load/store path of everything below. The evidence that it *enforces*
anything remains `docs/38` section 7.2 test 10: one simulated locked
read-only region, one permitted load, one faulting store.

**Trap and interrupt behaviour is checked only in one direction.** An
instruction check asserts `spec_trap == rvfi_trap` — so an instruction
that should trap and does not, or does not and does, is caught. Where
the core goes afterwards is not: the handler address, `mepc`, `mcause`,
`mtval` and the return are all unchecked, and A9's adapter makes the PC
checks look away across exactly that transition. Interrupt inputs are
free, so the core must remain ISA-correct in their presence, but nothing
checks that an interrupt was taken correctly, at the right priority, or
at all.

**The memory system is not in scope, in either direction.** The two bus
ports are driven by free inputs under A1, A2 and A6. Nothing here
concerns `hw/soc/rtl/soc_bus.v`, `soc_mem.v`, the APB bridge, the
peripherals or the SRAM macros; and nothing here checks that the core's
bus behaviour is legal beyond the two outstanding-count assertions P1
and P2 of section 7.3.

**Nothing below the RTL.** No netlist, no synthesis, no place and route,
no timing, no power. `docs/09` C.4 item 2 is the standing statement:
formal results hold for any timing-clean implementation, and OpenSTA is
the separate authority. The equivalence between this RTL and the mapped
netlist is `docs/09` B.2 layer 3, and **no `eqy` job exists in this
repository** — the same sentence `docs/09` already has to write about
target #2.

**Not the RTL the SoC is built from, in two respects.** The core here is
`hw/soc/genrvfi/`, elaborated by yosys-slang; the SoC is built from
`hw/soc/gen/`, elaborated by Yosys's Verilog front end, with the RVFI
block absent and `hw/soc/rtl/ibex_regfile_secded.v` substituted for the
register file. Phase 2 removes the second difference. The first one
stays, and A7's clock-gate substitution is a third.

**Nothing about radiation.** `docs/09` C.4 item 4 governs: formal proves
mechanisms correct, fault injection measures architectural sensitivity,
and only beam data speaks to cross-sections. This document proves
neither a mechanism nor a rate. It says the core executes the ISA
correctly in the absence of faults, which is the *precondition* for
`docs/42-core-fault-injection.md`'s numbers meaning what they say, and
had never been checked before.

**The instruction models are trusted, and section 7.5 is what that
costs.** riscv-formal's per-instruction Verilog is upstream's, validated
upstream against Spike. This project neither re-derives nor audits it.
`docs/09` C.4 item 7 already places Yosys, sby and the solvers in the
trusted set; this adds one more, and it is a *specification* rather than
a tool, which makes it the more important of the two to say out loud —
because a wrong specification does not merely fail to catch a bug, it
manufactures one. Two of the 70 models turned out to compute the wrong
function, and the only reason that is visible at all is that Ibex
disagreed with them and the disagreement had to be adjudicated by hand.
**A model that is wrong in the same direction as the core would be
invisible to this entire document.** That is the shape of the residual
risk here and there is nothing in this flow that reduces it.

---

## 7. The five defects the run found, and where they were

Not one of them is in Ibex's execution of an instruction, which is the
expected outcome for a core with upstream's verification history. Three
are in this project's harness; one is a genuine deviation between Ibex's
RVFI and riscv-formal's definition of it; and one is in riscv-formal's
own model of the ISA. Every one was found by a check failing, which is
the argument for running the tool rather than reasoning about it.

### 7.1 Defect 1 — an assumption that named two registers and needed five

The first check ever run, `insn_add_ch0`, **failed** at depth 20. The
counterexample's only interesting feature was
`csr_pmp_mseccfg = 3'b001` — `mseccfg.MML` set. With Machine Mode
Lockdown on, a PMP region that matches nothing **denies** in M-mode
rather than permitting, so with the reset configuration every
instruction fetch faulted and every retired instruction reported
`rvfi_trap` [fact].

`mseccfg` is CSR `0x747`. The assumption as first written guarded
`0x3A0-0x3EF`, the pmpcfg and pmpaddr range, and nothing else. It now
guards `mstatus` (whose `MPRV` bit redirects load/store privilege to
`MPP`, reaching U-mode without leaving M-mode), `mseccfg`, `mseccfgh`
and the PMP range, and it distinguishes a CSR *write* from a CSR read —
`csrrs`/`csrrc` with a zero source operand do not write, and forbidding
those too would have been a strictly larger assumption for no reason.

### 7.2 Defect 2 — a bus response in the same cycle as the grant, and a real deadlock behind it

`hang` **failed** at depth 25. The trace: a store is requested, granted
and answered **in one cycle**. The LSU completes it immediately; the ID
stage has already moved to its multi-cycle state expecting a response in
a later cycle; the core stalls for ever [fact].

The deadlock is real and reachable — and only on a bus Ibex is not
specified to work with. `doc/03_reference/load_store_unit.rst` step 3 at
the pinned commit: "The memory answers with a `data_rvalid_i` set high
for exactly one cycle ... This may happen **one or more cycles after**
the grant has been received" [fact]. The harness's A2 read
`instr_out_next != 0`, which permits the same cycle. It now reads
`instr_out != 0`.

This is recorded rather than fixed silently because it is a fact about
the core that anyone integrating it needs: **a zero-latency memory
hangs this core.** `hw/soc/rtl/soc_mem.v` does not have zero latency, so
the SoC is not exposed; a future peripheral that answers combinationally
would be.

**And then `hang` failed a second time, at the same depth, for a reason
that was neither the core nor the harness but the arithmetic between
them.** With A2 corrected, the counterexample became a MISALIGNED store
-- two bus requests, therefore two bus responses -- under a fairness
bound that allowed the memory eight cycles per response. Two responses
at up to eight cycles each, behind a fetch that had already spent its
own budget, does not fit in a 25-cycle window, so the check was failing
on a trace in which nothing at all was wrong.

Two ways out, and the choice is a trade rather than a fix. Raising the
depth costs solver time on every run of the two checks that need it;
tightening the environment costs an assumption. A6 is the second: the
bound is now **two cycles to grant and four to respond**, and `hang`'s
check cycle moved from 25 to 30 and `liveness`'s from 30 to 50. The
memory this SoC has meets that bound with margin — `hw/soc/rtl/soc_mem.v`
grants in the request cycle (`gnt_o = req_i`) and answers one cycle
later, two with `RDREG` [fact] — but the bound is an assumption about
memory in general and the checks below hold only for memories that keep
it. Both numbers are in section 8's
table and neither is derived from anything but this: **they are the
smallest values at which the checks stopped failing for arithmetic**,
which is an honest thing to say about a bound and a dishonest thing to
leave unsaid.

### 7.3 Defect 3 — the data port takes two outstanding requests, not one

`unique_ch0` **failed** in three minutes, on an assertion in the
harness rather than in riscv-formal: `assert(data_out_next <= 1)`. The
counterexample is a **misaligned** word access, which the LSU splits
into two bus requests — `data_be` `4'hE` at `0x104` then `4'h1` at
`0x108` — and for which it takes the second grant before the first
response arrives [fact].

The bound was written from the one-request-at-a-time reading of the LSU
and it is wrong; the bound is 2. This is the one place where the harness
**asserts** rather than assumes the core's half of the bus contract, and
it is worth the two lines: an assumption there would have hidden the
fact instead of reporting it. Both P1 (instruction port) and P2 (data
port) now assert a bound of 2, and **no check in the run of section 8
failed at either of them** -- `grep 'failed assertion'` over every
logfile in the work tree returns only riscv-formal's own assertions
and none of the wrapper's [fact]. The bound is therefore a bounded
*proof* about Ibex's bus behaviour and not merely a passing
observation: within every depth in section 8's table, the core never
has more than two requests in flight on either port.

### 7.4 Defect 4 — `rvfi_intr` and `rvfi_pc_wdata` do not follow riscv-formal's definitions

This one is not in the harness. It is a genuine mismatch between what
Ibex's RVFI means and what riscv-formal's RVFI means, and it has two
halves.

**`rvfi_intr` is narrower than the RVFI definition.** RVFI defines it as
marking the first instruction of a trap handler. `ibex_core.sv` sets it
only for `EXC_PC_IRQ`:

```
if (pc_set && pc_mux_id == PC_EXC && (exc_pc_mux_id == EXC_PC_IRQ))
  rvfi_set_trap_pc_d = 1'b1;
```

**[fact]**. `EXC_PC_IRQ` and not `EXC_PC_EXC`, so after an illegal
instruction, an `ecall`, an `ebreak` or an access fault, the handler's
first instruction reports `rvfi_intr` **low**. `pc_fwd_ch0` failed at
depth 30 on exactly that: a `c.lwsp` with `rd = x0`, which is reserved,
retiring with `rvfi_trap` set, and the next instruction starting at the
`mtvec` Ibex derives from `boot_addr` with no relaxation flag [fact].

**`rvfi_pc_wdata` is not the next PC for a redirect that is not a branch
or a jump.** `ibex_core.sv` builds it as

```
rvfi_stage_pc_wdata[i] <= pc_set ? branch_target_ex : pc_if;
```

**[fact]**, and `branch_target_ex` is the ALU's target — the right
answer for `PC_JUMP` and `PC_BP`, and not the right answer for
`PC_ERET`, whose target is `csr_mepc`. `pc_fwd_ch0` failed again, with
the trap adapter already in place, on an `mret` at PC `0x0` reporting
`rvfi_pc_wdata = 0x4` while the next instruction started at `0x80`,
which is where `mepc` pointed [fact].

**Neither is an execution bug and neither is harmless.** Ibex's RVFI is
built for its Spike co-simulation, which compares architectural effects
rather than reconstructing PC continuity, so the deviation has no
consequence upstream. It has a consequence for anything that consumes
the trace under the published RVFI definition. It is reported here, and
worked around by A9, which relaxes the PC checks across a handler entry
or a return — concealing the entry address, which riscv-formal has no
model to check anyway, and concealing nothing else. `spec_trap ==
rvfi_trap` still runs, unrelaxed, on the instruction that caused the
trap.

### 7.5 Defect 5 — riscv-formal's `div` and `rem` models compute an UNSIGNED result

This is the one that argues for having run the tool. It is in the
**specification**, the core is right, and it is exactly reproducible by
hand.

`insn_div_ch0` failed at check cycle 55 on the assertion
`spec_rd_wdata == rd_wdata`, with

| | |
|---|---|
| Instruction | `0x03934FB3` = `div x31, x6, x25` |
| `rvfi_rs1_rdata` | `0xFFFFFEA5` = **-347** |
| `rvfi_rs2_rdata` | `0x40100401` = **+1,075,056,129** |
| Ibex's `rvfi_rd_wdata` | **`0x00000000`** |
| The model's `spec_rd_wdata` | **`0x00000003`** |

**[fact].** Signed division truncating toward zero gives -347 /
1075056129 = 0. **Ibex is correct.** Three is what you get from
4,294,966,949 / 1,075,056,129 — the same bit pattern read as
**unsigned**.

`insn_rem_ch0` failed the same way, independently, and its arithmetic
closes the argument:

| | |
|---|---|
| Instruction | `0x0392E133` = `rem x2, x5, x25` |
| `rvfi_rs1_rdata` | `0xFFFFB3AB` = **-19,541** |
| `rvfi_rs2_rdata` | `0x50A00000` = **+1,352,663,040** |
| Ibex's `rvfi_rd_wdata` | **`0xFFFFB3AB`** = -19,541, correct |
| The model's `spec_rd_wdata` | **`0x0E1FB3AB`** = 236,958,635 |

and 4,294,947,755 mod 1,352,663,040 = 236,958,635 **[fact, arithmetic]**.

**The cause is Verilog signedness propagation, and it is in three lines
of upstream's `insns/insn_div.v`:**

```
wire [XLEN-1:0] result = rs2 == 0 ? {XLEN{1'b1}} :
                         rs1 == MIN && rs2 == -1 ? MIN :
                         $signed(rs1) / $signed(rs2);
```

IEEE 1364-2005 section 5.5.1: the second and third operands of the
conditional operator are **context-determined**, and the expression type
is unsigned if either of them is unsigned. `{XLEN{1'b1}}` is an unsigned
concatenation. It therefore demotes the third branch, the `$signed`
casts have no effect, and the division is evaluated unsigned.

**This was checked in a second tool rather than argued from the LRM.**
Icarus Verilog, which shares no code with Yosys, evaluates upstream's
expression on the `div` counterexample's operands to **3** and the same
division written on its own self-determined wire to **0** **[fact]**.
Two independent front ends agree, which makes this the language's
semantics and not a tool defect.

**Which models are affected, and which are not.** Exactly two:

| Model | Shape | Affected |
|---|---|---|
| `div`, `rem` | conditional whose other branches are unsigned, around `$signed(a) op $signed(b)` | **Yes** |
| `divu`, `remu` | same conditional shape, but the operation is unsigned by intent | No |
| `mul` | `a * b`, low XLEN bits — correct for either signedness | No |
| `mulh`, `mulhsu`, `mulhu` | operands sign- or zero-extended to 2\*XLEN by hand, then multiplied | No |

**The controls all pass**: `slt`, whose `$signed(a) < $signed(b)` is a
relational operator whose operand signedness is determined by the
operands and not by the result context, and `sra` and `srai`, whose
`$signed(a) >>> n` sits at the top of a continuous assignment — where
the same section of the LRM says the left-hand side determines width and
**not** type.

**How a defect like this survives in a widely used tool.** riscv-formal's
own in-tree core configurations reach for `RISCV_FORMAL_ALTOPS`, which
replaces multiply and divide with cheap stand-ins on both sides so the
solver never has to reason about them — PicoRV32's `checks.cfg` sets it
[fact]. With ALTOPS on, the defective expression is not compiled at all.
This harness does not set it, because Ibex has no ALTOPS mode and the
point was to check the real arithmetic.

**What was done about it.** `hw/soc/rvformal/insns/insn_div.v` and
`insn_rem.v` are corrected copies — byte-identical to upstream apart
from the three lines between two marked comments, which move the signed
operation onto its own self-determined wire.
`RVF_INSN_FIX=1` substitutes them, by the same file-list rule
`hw/soc/flow/ibex_sources.sh` uses for the register file, so the fetched
checkout stays pristine. **The default is 0** — a reader reproducing
this against riscv-formal as published should get what riscv-formal as
published gives, and section 8's table is that run. Section 8.5 is the
run with the substitution.

**It has not been reported upstream from inside this repository**, and
doing so is the first item in section 11.

---

## 8. The result

All numbers below are from one run of

```
hw/soc/flow/rvformal.sh setup      # RVF_INSN_FIX=0, RVF_LIVENESS_DEPTH=50
hw/soc/flow/rvformal.sh run -j8
```

on a 20-core machine with 31 GiB of RAM, eight sby jobs concurrent,
which was not otherwise idle. The toolchain is the pinned one:
`oss-cad-suite-linux-x64-20260804`, yosys 0.67+146, and **boolector** on
every check — `[options] solver boolector` in `checks.cfg.in`, and no
second engine family was tried, which `docs/09` C.4 item 7's
solver-diversity note would prefer and this run does not have.

### 8.1 What ran

**79 bounded model checks and 79 cover jobs**, generated by
riscv-formal's `checks/genchecks.py` from `hw/soc/rvformal/checks.cfg.in`
[fact]:

| Family | Jobs | Check cycle | What one instance asserts |
|---|---:|---:|---|
| `insn_<name>_ch0` | 66 | **20** | The retired instruction's effect on the architectural state equals riscv-formal's model of that instruction: `spec_rd_addr == rd_addr`, `spec_rd_wdata == rd_wdata`, `spec_pc_wdata == pc_wdata`, the memory address, the byte masks, the store data, the source register numbers, and `spec_trap == trap` |
| `insn_{div,divu,rem,remu}_ch0` | 4 | **55** | The same, at a depth that fits Ibex's sequential divider |
| `reg_ch0` | 1 | 25 | A register written by one instruction reads back the same value at a later one — the register file does not lose or invent state |
| `pc_fwd_ch0` | 1 | 30 | Instruction N+1 starts where instruction N said the PC would go |
| `pc_bwd_ch0` | 1 | 30 | The same relation read backwards |
| `causal_ch0` | 1 | 30 | An instruction's register inputs are not read by an instruction that retired before its producer — no value arrives from the future |
| `unique_ch0` | 1 | 30 | `rvfi_order` is unique: no instruction is reported twice |
| `liveness_ch0` | 1 | 50 (trigger 12) | After an instruction retires, the next one retires |
| `hang` | 1 | 30 | Some instruction retires at all |
| `ill_ch0` | 1 | 20 | The all-zero instruction word traps, writes no register and writes no memory |
| `cover` | 1 | 20 | **Cover**: two instructions can retire. The floor of every claim above |

The 70 instruction names are riscv-formal's `insns/isa_rv32imc.txt`,
which is the configuration `soc_top.v` elaborates. Depths are check
cycles; sby's own `depth` is one more, and a check that passed at cycle
20 says nothing about cycle 21.

### 8.2 The headline

| Set | Jobs | PASS | FAIL | Stopped without a verdict | Job-seconds (wall) |
|---|---:|---:|---:|---:|---:|
| **bmc** | 79 | **70** | 3 | 6 | 7,790 |
| **cover** | 79 | **79** | 0 | 0 | 1,122 |

**[fact, `hw/soc/flow/rvformal.sh report`.]** Broken down:

| | PASS | FAIL | Stopped |
|---|---:|---:|---:|
| Instruction checks (70) | **62** | 2 (`div`, `rem`) | 6 (`mul`, `mulh`, `mulhsu`, `mulhu`, `divu`, `remu`) |
| Consistency checks (9) | **8** | 1 (`liveness`) | 0 |

Every consistency check except `liveness` passed: `reg_ch0` (400 s),
`pc_fwd_ch0` (230 s), `causal_ch0` (159 s), `hang` (132 s),
`unique_ch0` (106 s), `pc_bwd_ch0` (91 s), `ill_ch0` (41 s) and `cover`
(12 s) **[fact]**. The 62 passing instruction checks took **54 to 133
seconds** each, median 63 **[fact]**.

### 8.3 The two checks that fail, and what each failure is

**`insn_div_ch0` and `insn_rem_ch0` fail because the SPECIFICATION is
wrong.** Section 7.5 is the finding, with both counterexamples, the
arithmetic, the LRM citation and an independent tool's confirmation.
Ibex's answers are correct in both; riscv-formal's models compute an
unsigned division and an unsigned remainder. These are the only two
checks in this document where the core and the model disagree, and in
both the core is right.

**`liveness_ch0` fails at check cycle 50, and it is a bound.** The
counterexample's trigger instruction retires at cycle 12 and the next
instruction in the stream is `rem x0, x7, x25` — a divide, which
`ibex_multdiv_fast` takes about 37 cycles to complete **[fact, the
trace: `id_fsm_q` in its multi-cycle state, no bus activity, no
retirement]**. 12 + fetch + 37 does not fit in 50. The depth that would
close it is around 65 **[estimate, arithmetic on those three numbers]**
and it was not run, because a depth-50 BMC of this check already cost
616 seconds and is the third most expensive job in the set.
`RVF_LIVENESS_DEPTH` exists so that raising it is a decision someone
makes rather than a constant someone edits, and it is the only check
depth in the configuration that is overridable.

**What `liveness` failing does and does not leave open.** It does not
leave "the core can deadlock" open: `hang` PASSES at cycle 30, so within
that depth the core always retires something, and section 7.2's genuine
deadlock is excluded by an environment assumption that Ibex's own
documentation states. What is open is the stronger statement `liveness`
makes — that the instruction after *any* given retirement also
retires — and it is open at any depth, because no depth was found at
which it holds.

### 8.4 The six checks that were stopped, and what that costs

The four multiply checks and `divu`/`remu` were **stopped without a
verdict** after running, each on its own core, for

| Check | Depth | Stopped after |
|---|---:|---:|
| `insn_divu_ch0` | 55 | **2,419 s** (40 min) |
| `insn_mul_ch0` | 20 | **2,265 s** (38 min) |
| `insn_mulh_ch0` | 20 | **2,260 s** (38 min) |
| `insn_mulhsu_ch0` | 20 | **2,251 s** (38 min) |
| `insn_mulhu_ch0` | 20 | **2,241 s** (37 min) |
| `insn_remu_ch0` | 55 | **2,117 s** (35 min) |

**[fact, `ps` elapsed time at the moment each was killed].** They were
stopped because they were occupying six of the eight job slots and
nothing else in the run could start behind them.

**This is not a pass and it is not a failure.** It is the absence of a
result, and the reason is the one every formal flow meets at the
multiplier: proving that a sequential 32x32 multiplier equals `a * b`
is the classic hard case for a bit-blasting SMT solver, and `boolector`
is bit-blasting. The evidence that the problem is the solver and not the
model or the depth is that **every one of the six passes its COVER job**
in 9 to 73 seconds [fact] — the witness is easy, the proof is not.

Section 11 item 3 lists the three routes out and none of them is free.
Until one is taken, **`mul`, `mulh`, `mulhsu`, `mulhu`, `divu` and
`remu` have no formal result in this project**, and `docs/38` section
7.2 test 3 — one simulated case per operation, including the ISA's
divide-by-zero results — remains the only evidence for them.

### 8.5 The same two checks with the specification corrected

The diagnosis in section 7.5 does not depend on this run: it rests on
two counterexamples whose arithmetic is checkable by hand and on an
independent simulator agreeing with Yosys about the same expression.
This is the end-to-end confirmation, and it was run in its own work tree
so that section 8.2's numbers stay the numbers upstream's specification
gives.

```
RVF_INSN_FIX=1 RVF_OUT=hw/soc/out/rvformal-insnfix \
  hw/soc/flow/rvformal.sh setup
RVF_INSN_FIX=1 RVF_OUT=hw/soc/out/rvformal-insnfix \
  hw/soc/flow/rvformal.sh run -j2 insn_div_ch0 insn_rem_ch0
```

**Neither check closed, and that is the honest result.** Both were
started at 14:35:32 and both were stopped without a verdict:
`insn_div_ch0` after **40 min 43 s** and `insn_rem_ch0` after
**48 min 52 s** **[fact, the sby logfiles' start and `terminating
process` timestamps]**. The solver was still working on the assertions
at step 55 in both.

**This does not weaken section 7.5 and it does sharpen section 8.4.**
The diagnosis rests on evidence that does not need this run: two
counterexamples whose arithmetic anyone can check with a calculator,
IEEE 1364-2005 section 5.5.1, and Icarus Verilog independently
evaluating upstream's expression to 3 where the same division on its own
gives 0. What the non-termination adds is a measurement of *direction*:
against the defective model the checks **failed in 852 s and 731 s**,
because finding one counterexample is a satisfiability question;
against the corrected model they had not **proved** anything after 41
and 49 minutes, because proving equivalence with a signed divider is the
same hard case as the multiply checks of section 8.4. **Correcting a
specification made the proof harder, not easier**, and that is a useful
thing to know before item 1 of section 11 is attempted.

So `div` and `rem` join `mul`, `mulh`, `mulhsu`, `mulhu`, `divu` and
`remu`. **All eight instructions of the M extension have no formal
result in this project**, and in every case the reason is the solver and
not the core — six were stopped, and the two that produced a verdict
produced it against a model that was wrong. The evidence for the M
extension remains `docs/38` section 7.2 test 3.

**A defect in this project's own driver, found by running exactly this.**
The first attempt failed in under a second with `ERROR: Bad command` and
nothing else. `RVF_OUT` had been given as a RELATIVE path; sby runs
yosys from inside each check's `src/` directory, and the generated
`read_slang` line named the rewritten `ibex_top.v` by that relative
path, which resolved against the wrong directory. `rvformal.sh` now
makes `RVF_OUT` absolute before anything is generated. It is a small
thing and it is recorded because the error message named nothing — the
same complaint `docs/38` section 7.5 makes about its own five.

### 8.6 What is proved, in one paragraph, with the qualifiers attached

For each of the RV32IMC instructions whose check passed, on **every**
execution this core can reach from reset within that check's depth,
under the nine assumptions of section 4.1 and with the memory and
interrupt inputs otherwise free, the instruction's effect on the
architectural state agrees with riscv-formal's model of the RISC-V ISA.
The core's register file does not lose or invent state (`reg_ch0`), its
PC is continuous in both directions across every retirement that is not
a trap entry or an `mret` (`pc_fwd_ch0`, `pc_bwd_ch0`), no register
value arrives from an instruction that has not retired (`causal_ch0`),
no instruction is reported twice (`unique_ch0`), the all-zero word traps
(`ill_ch0`), it makes progress at all (`hang`), and it never has more
than two bus requests in flight on either port (P1 and P2 of section
7.3). Every one of those is bounded at the depth in the table and none
of them is a proof about cycle depth+1.

---

## 9. The cost

### 9.1 The model

The thing the solver is given, per check, measured out of the SMT2 the
flow writes for `insn_add_ch0` [fact,
`checks/insn_add_ch0/model/design_smt2.smt2`]:

| | |
|---|---:|
| State registers in the flattened model | 149 |
| **State bits** | **2,781** |
| Free (`anyseq`) inputs | 76, **930 bits** |
| Free constants (`anyconst`) | 1 (`boot_addr`) |
| Assertions | 35 |
| Assumptions | 9 |

For scale: `docs/38` section 8.4 measured 2,106 flip-flops in the
synthesised `small-pmp` netlist. The extra ~675 bits here are the RVFI
trace pipeline, which the synthesised design does not contain, plus the
harness's own counters and the checker's shadow state.

### 9.2 The run

| | |
|---|---:|
| Wall clock, 158 jobs at `-j8` | **50 min 52 s** |
| CPU, user + system, as `/usr/bin/time -v` attributed it | **9,076 s** (2 h 31 min) |
| Peak resident set of the largest single job | **2.82 GiB** |
| Job-seconds (wall) summed over the 73 bmc jobs that finished | 7,790 |
| Job-seconds (wall) summed over the 79 cover jobs | 1,122 |

**[fact, `/usr/bin/time -v` and the per-check `status` files.]**

**The CPU figure is an undercount and here is by how much.** It excludes
the six stopped checks entirely: killing a job orphans its solver
process, and an orphaned process's usage is never attributed to the tree
that started it. Those six ran 2,117 to 2,419 seconds each on a core of
their own, so the true cost of this run is about **22,600 s of CPU, or
6.3 core-hours** **[estimate, the measured 9,076 s plus the six
stopped jobs' wall times]**.

**Where it went.** Nine jobs account for 4,000 of the 7,790 finished
bmc job-seconds; the other 64 average 59 seconds each **[fact,
arithmetic]**. The expensive ones are, in order: `insn_div` 852 s,
`insn_rem` 731 s, `liveness` 616 s, `reg` 400 s, `pc_fwd` 230 s,
`causal` 159 s, `insn_sh` and `insn_sw` 133 s each, `hang` 132 s. Two of
those nine are the checks that failed on a defective model and one is
the check that failed on its bound, so **more than a quarter of the
finished solver time went into the three results this document cannot
claim** — before counting the six that were stopped, which cost more
than all 73 finished jobs put together.

**A note on the units.** sby's `status` file records ELAPSED CLOCK time
per job, not CPU time, so summing it gives job-seconds under whatever
`-j` the run used and not core-hours. `hw/soc/flow/rvformal.sh report`
labels it `job-seconds(wall)` for that reason; an earlier version of
that script read the wrong field of the status file entirely and
reported every check's runtime as its verdict, which is a report that
cannot say FAIL. It was caught by running it.

---

## 10. Is phase 2 ready?

**Yes, and it is one environment variable.** *(Written before phase 2
was run. It was, at these settings; Part 2 is the result and section 16
is the delta this section predicts.)*

```
IBEX_REGFILE=secded hw/soc/flow/rvformal.sh setup
IBEX_REGFILE=secded hw/soc/flow/rvformal.sh run -j8
```

`hw/soc/flow/ibex_sources.sh` is the same function every other SoC flow
uses to choose between upstream's `ibex_register_file_ff` and
`hw/soc/rtl/ibex_regfile_secded.v`, so phase 2 is the same harness, the
same assumptions, the same depths and the same solver against a
different register file. The work trees are separate
(`hw/soc/out/rvformal-upstream` and `hw/soc/out/rvformal-secded`), so
phase 2 cannot overwrite phase 1's evidence, and the comparison is
`rvformal.sh report` run against each.

**What the delta will and will not mean.** The SECDED register file of
`docs/43` section 6 changes the register file's read path: a value is
decoded and corrected on the way out. If it is transparent — and
`docs/43` section 9.1's cycle-identical whole-SoC run is the evidence
that it is — every check that passes in phase 1 passes in phase 2 and
the delta is empty. A check that passes in phase 1 and fails in phase 2
is the substitution, and the one that would find it is `reg_ch0`, whose
whole content is that a register written by one instruction reads back
the same value at the next. **That is the check phase 2 exists for**, and
it is the reason a phase-1 baseline had to be established first: without
one, a `reg_ch0` failure could equally be A5, or the front end, or the
`prim_clock_gating` substitution, or any of the three harness defects
section 7 records.

**Two things phase 2 will still not see**, and they are the same two
`docs/43` section 6.5 and 6.6 already state. The error counters are
deleted by `opt_clean` because nothing reads them, so a corrected upset
is invisible to any port riscv-formal can bind to; and the register file
protects the data and not the addresses, which come from the decoder.
riscv-formal checks the *fault-free* behaviour of the substituted file.
It is not a fault-injection campaign and does not replace `docs/44`
section 9.

**One thing phase 2 must carry forward unchanged**, and it is the
reason the settings are printed at setup: phase 1 ran with
`RVF_INSN_FIX=0` and `RVF_LIVENESS_DEPTH=50`. A phase 2 run at different
settings is not a delta against this one, and
`hw/soc/flow/rvformal.sh setup` prints all three selectors on its first
line so a log says which run it is.

---

## 11. What should be done next, ranked

1. **Report the `div`/`rem` signedness defect to riscv-formal.** It is
   in a specification other people are checking their cores against, the
   fix is three lines, and section 7.5 has the counterexample, the
   arithmetic, the LRM citation and a second tool's confirmation. This
   repository has not done it.
2. **Run phase 2.** It is one environment variable and the delta is the
   point of phase 1 existing.
3. **Decide what to do about the M-extension checks.** Sections 8.4 and
   9.2 measure where the solver time went and it is not evenly spread.
   Three routes exist and none is free: a different engine (`abc pdr`,
   `bitwuzla`, `rIC3` — all in the pinned suite, none tried here), a
   deeper look at whether the multiplier equivalence is tractable at
   all with a bit-blasting solver, or `RISCV_FORMAL_ALTOPS`, which
   would need Ibex to implement it and Ibex does not.
4. **The CSR checks, which need a patch to Ibex.** Section 6's largest
   gap closes only by adding `rvfi_csr_*` ports to `ibex_core.sv` and
   `ibex_top.sv`. That is a patch, it is the thing `docs/38` section 4.2
   and `docs/43` section 3 are careful about, and `docs/44` section 4
   already took one on for the register file's fault port. The trade is
   the same shape and the prize is larger: `mstatus`, `mtvec`, `mepc`,
   `mcause` and the PMP registers are what `docs/09`'s S2 software
   architecture rests on and none of them is checked by anything today.
5. **`mode prove` on the consistency checks only.** The instruction
   checks need an inductive invariant over the microarchitecture and are
   out of reach; `reg`, `causal` and `unique` are smaller and an
   unbounded result on any of them would be the first in this document.
6. **An `eqy` job.** `docs/09` B.2 layer 3 and target #2's note both say
   the same thing: there is no equivalence job in this repository, and
   the front-end split of section 3.2 has now added a second place where
   one would be worth having.

---

## 12. Files touched

| File | What |
|---|---|
| `hw/soc/tools.soc.mk` | riscv-formal pinned by commit, `fetch-riscv-formal`, and a `soc-toolcheck` line that FAILS if the checkout is dirty |
| `hw/soc/flow/sv2v_ibex.sh` | optional trailing `--define` arguments; the three-argument invocation is byte-identical to before [fact] |
| `hw/soc/flow/ibex_sources.sh` | `IBEX_GEN` selects `gen` or `genrvfi`; `IBEX_FAULT_PORT=1` is refused with anything but `gen` |
| `hw/soc/flow/rvfi_slangfix.py` | new — the one declaration rewrite of section 3.3 |
| `hw/soc/flow/rvformal.sh` | new — the driver: work tree, generation, run, report |
| `hw/soc/rvformal/wrapper.sv` | new — the binding and every assumption in section 4.1 |
| `hw/soc/rvformal/checks.cfg.in` | new — depths, the `read_slang` line with the nineteen parameters, and what is deliberately not generated |
| `hw/soc/rvformal/prim_clock_gating_formal.v` | new — A7 |
| `hw/soc/rvformal/params.sh` | new — the parameter guard |
| `hw/soc/rvformal/insns/insn_div.v`, `insn_rem.v` | new — the corrected models of section 7.5, off by default |
| `.gitignore` | `hw/soc/genrvfi/`, and the tracked-source list gains `rvformal` |
| `docs/00-index.md` | this document's row |

**Phase 2 added no tracked file.** It is `IBEX_REGFILE=secded` through
`hw/soc/flow/ibex_sources.sh`, which every other SoC flow already uses,
and the only source change in Part 2's work was one robustness fix in
`hw/soc/flow/rvformal.sh` (`RVF_OUT` is made absolute; a relative path
produced `ERROR: Bad command` from a `read_slang` line resolved against
the wrong directory) and one label change in its `report` subcommand
(`NOT RUN` became `NO STATUS`, because a job stopped after forty minutes
of solver time reported as "not run" is a label narrower than the thing
it describes).

Nothing under `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is
touched, and `hw/tb/Makefile.fi` — which writes a file `docs/34` pins —
was not invoked.

---

## 13. Reproducing this

```
make -f hw/soc/tools.soc.mk fetch-riscv-formal
make -f hw/soc/tools.soc.mk soc-toolcheck

# the second sv2v tree, with the RVFI ports
hw/soc/flow/sv2v_ibex.sh hw/soc/ext/ibex hw/soc/genrvfi \
                         hw/soc/tools/sv2v-Linux/sv2v RVFI

# phase 1 -- the stock core, upstream's register file, and
# riscv-formal's instruction models exactly as fetched
hw/soc/flow/rvformal.sh setup
hw/soc/flow/rvformal.sh run -j8
hw/soc/flow/rvformal.sh report

# section 8.2's second run: the same, with the two corrected models of
# section 7.5 substituted for upstream's div and rem
RVF_INSN_FIX=1 RVF_OUT=hw/soc/out/rvformal-insnfix \
  hw/soc/flow/rvformal.sh setup
RVF_INSN_FIX=1 RVF_OUT=hw/soc/out/rvformal-insnfix \
  hw/soc/flow/rvformal.sh run -j2 insn_div_ch0 insn_rem_ch0

# phase 2 -- the same proofs against docs/43's SECDED register file
IBEX_REGFILE=secded hw/soc/flow/rvformal.sh setup
IBEX_REGFILE=secded hw/soc/flow/rvformal.sh run -j8
```

The three settings that change what is run are `IBEX_REGFILE`
(phase 1 or 2), `RVF_INSN_FIX` (section 7.5) and `RVF_LIVENESS_DEPTH`
(section 7.2); `hw/soc/flow/rvformal.sh setup` prints all three before
it generates anything, and every generated `.sby` carries the
`IBEX_ASSUME_*` defines in plain text. The phases write to different
work trees (`hw/soc/out/rvformal-upstream` and `-secded`) so neither can
overwrite the other's evidence. Everything under `hw/soc/out/`, `hw/soc/ext/` and
`hw/soc/genrvfi/` is generated or fetched and gitignored; the tracked
sources are the eleven files of section 12.


---

# Part 2 — Phase 2: the SECDED register file substituted

Everything above is phase 1 and its numbers are unchanged. This part is
the second half of the same experiment, run after phase 1 was reviewed
and committed as `a5699b4`.

## 14. Why this is here and not in a document of its own

**Because a phase-2 result read without phase 1's ledger is a result
that outruns its evidence, and separating them would either duplicate
the ledger or produce a document that cannot be read alone.** Phase 2
inherits, unchanged and by construction, every one of the nine
assumptions of section 4.1, the eleven check depths of section 8.1, the
two front ends of section 3, the `rvfi_intr` adapter of section 7.4 and
the eight-instruction M-extension gap of sections 8.4 and 8.5. A reader
who is handed "the substitution is transparent" without those is being
handed a claim about a core with no CSR checks, no PMP enforcement
proof, no netlist and no result at all for `mul`, `div` or their
siblings.

The second reason is smaller and also real: section 10 asks "Is phase 2
ready?" and answers yes. Answering it somewhere else leaves a question
open in a committed document.

## 15. What changed, and what did not

**One thing changed: which file supplies `ibex_register_file_ff`.**
`hw/soc/flow/ibex_sources.sh` at `IBEX_REGFILE=secded` drops
`hw/soc/genrvfi/ibex_register_file_ff.v` and adds
`hw/soc/rtl/ibex_regfile_secded.v` plus `hw/rtl/secded_enc.v` and
`hw/rtl/secded_dec.v` — the pilot's own codec, read in place from the
frozen directory and not copied, which is the arrangement `docs/43`
section 6.1 exists to preserve. `diff` of the two generated `.sby`
files confirms that is the ONLY difference: same nineteen `-G`
parameters, same defines, same depths, same engine, same wrapper, same
32 other core files **[fact]**.

| | Phase 1 | Phase 2 |
|---|---|---|
| `IBEX_REGFILE` | `upstream` | **`secded`** |
| `RVF_INSN_FIX` | 0 | 0 |
| `RVF_LIVENESS_DEPTH` | 50 | 50 |
| Register file | `genrvfi/ibex_register_file_ff.v` | `hw/soc/rtl/ibex_regfile_secded.v` + `hw/rtl/secded_{enc,dec}.v` |
| Work tree | `hw/soc/out/rvformal-upstream` | `hw/soc/out/rvformal-secded` |

**The substituted file elaborates at its own defaults, and they are the
ones the SoC ships.** `read_slang -G` sets `ibex_top`'s parameters and
nothing sets the register file's, so `SCRUB = 1`, `FASTCORR = 1` and
`SYNPRE = 0` apply — which is `docs/44`'s build and not `docs/49`'s
declined `SYNPRE` variant **[fact, the parameter declarations in
`ibex_regfile_secded.v`]**. What is proved below is the register file as
built, correct-on-read and scrubbing, and it is not a statement about
`SYNPRE = 1`.

**What the substitution does to the formal model** [fact, counted out of
the SMT2 written for `insn_add_ch0` in each tree]:

| | Phase 1 | Phase 2 | Delta |
|---|---:|---:|---:|
| State registers | 149 | 181 | +32 |
| **State bits** | 2,781 | **3,034** | **+253, +9.1 %** |
| Free (`anyseq`) signals | 76 | 84 | +8 |
| Free bits | 930 | **1,042** | **+112** |
| SMT2 file | 1,521,200 B | 1,832,016 B | +20.4 % |

The +253 state bits are the stored check bits: `docs/43` section 6.3
measures 217 check flip-flops for 31 registers, and the remainder is the
scrub pointer and the counters.

**The +112 free bits deserve a sentence, because a free input is solver
freedom.** They are eight signals — two of 32 bits and six of 8 —
that `setundef -undriven -anyseq` turned into unconstrained inputs
because nothing in the elaborated design drives them. They could not be
attributed to named signals from the model, because sby's
`rename -witness` anonymises them before the SMT2 is written, and no
attempt was made to defeat that. **The direction of the effect is
nevertheless certain: a free input can only ADD traces**, so every check
that passes below passes with those 112 bits under the solver's control,
and `opt_clean` did not remove them, so they reach something. This makes
the phase-2 result marginally stronger than the phase-1 one over the
same properties rather than weaker, and it is stated here because "the
model grew" would otherwise read as a caveat when it is not one.

## 16. The delta, check by check

`hw/soc/flow/rvformal.sh report` on each tree, compared entry by entry
rather than in totals.

| | Phase 1 | Phase 2 |
|---|---|---|
| **bmc** | 70 PASS, 3 FAIL, 6 stopped | REG_BMC |
| **cover** | 79 PASS | **79 PASS** |

### 16.1 Sixty-nine checks pass in both, and the list is identical

Of the 79 bmc checks, **68 have the same status in both runs and one
changed**, and the one that changed is `reg_ch0`, which section 17 is
about. Every other check — 62 instruction checks, the seven consistency
checks other than `reg` and `liveness`, and `cover` — has the same
verdict in both runs, and no check that passed in phase 1 fails in
phase 2 **[fact]**.

**All 79 cover jobs pass in both runs.** Nothing became unreachable, no
depth became vacuous, and the substituted register file does not stop
any instruction retiring at its check cycle.

### 16.2 The three failures are the same three, for the same reasons

| Check | Phase 1 | Phase 2 | Same cause? |
|---|---|---|---|
| `insn_div_ch0` | FAIL, 852 s | FAIL, 1,135 s | **Yes** |
| `insn_rem_ch0` | FAIL, 731 s | FAIL, 1,124 s | **Yes** |
| `liveness_ch0` | FAIL, 616 s | FAIL, 720 s | **Yes** |

`insn_div` and `insn_rem` fail on the same assertion at the same step
(`rvfi_insn_check.sv:177`, `spec_rd_wdata == rd_wdata`, step 55) and on
the specification defect of section 7.5. **Phase 2 reproduced that
defect independently, on different operands, and this time with negative
DIVISORS where phase 1 had a negative dividend** — which is worth having
because it exercises the other half of the sign confusion:

| | Phase 2 `insn_div_ch0` | Phase 2 `insn_rem_ch0` |
|---|---|---|
| `rvfi_rs1_rdata` | `0x00724800` = +7,489,536 | `0xC957F6C6` = -900,433,722 |
| `rvfi_rs2_rdata` | `0xFFFFFFE8` = **-24** | `0xC957F622` = **-900,433,886** |
| Ibex's `rvfi_rd_wdata` | `0xFFFB3D00` = **-312,064** | `0xC957F6C6` = **-900,433,722** |
| The model's `spec_rd_wdata` | `0x00000000` | `0x000000A4` = 164 |

**[fact].** 7,489,536 / -24 = -312,064 signed, and 7,489,536 /
4,294,967,272 = 0 unsigned. -900,433,722 mod -900,433,886 is
-900,433,722 signed, and 3,394,533,574 mod 3,394,533,410 = 164 unsigned.
**Ibex is right in both, on the substituted register file as it was on
the stock one**, and the model is wrong in both. Section 7.5 now rests
on four counterexamples from two independent runs rather than two.

`liveness_ch0` fails at check cycle 50 in both, and section 8.3's
account is unchanged: the bound does not fit a 37-cycle divide.

### 16.3 The M-extension gap carries forward, and the delta over it is UNDEFINED

The four multiply checks, `divu` and `remu` had no result in phase 1 and
they have none in phase 2. They were stopped at a deliberately
comparable budget — phase 1's longest ran 2,419 s before being stopped,
phase 2's 2,434 s [fact] — and neither run produced a verdict for any of
them.

| Check | Phase 1, stopped after | Phase 2, stopped after |
|---|---:|---:|
| `insn_divu_ch0` | 2,419 s | 2,434 s |
| `insn_mul_ch0` | 2,265 s | 2,227 s |
| `insn_mulh_ch0` | 2,260 s | 2,210 s |
| `insn_mulhsu_ch0` | 2,251 s | 2,160 s |
| `insn_mulhu_ch0` | 2,241 s | 2,159 s |
| `insn_remu_ch0` | 2,117 s | 1,332 s |

**This is stated at length because of how it could be misread.** "62 of
70 instruction checks pass in both runs" is true, and it is NOT the same
sentence as "the substitution is transparent to the ISA". Over the eight
M-extension instructions the two runs agree on nothing, because neither
of them says anything: six have no verdict in either run and two have
the same wrong verdict from the same wrong model. **The delta over the M
extension is undefined, not clean.** If the SECDED register file changed
`mulh`'s result, this experiment would not know.

Together with the standing exclusions of section 6 — no CSR is checked,
PMP enforcement is not proved, bus errors and debug are assumed away —
the honest statement of scope for phase 2 is: *the substitution does not
change the architectural behaviour of the 62 RV32I and RV32C
instructions that were checked, at the depths that were checked, under
the assumptions that were ledgered.*

## 17. `reg_ch0`: what it proves, and what it cannot

This is the check phase 2 exists for, and it is the one check whose
status differs between the two runs.

### 17.1 What it asserts

`riscv-formal/checks/rvfi_reg_check.sv`, read rather than paraphrased.
It carries two free CONSTANTS — `register_index`, five bits, and
`insn_order`, sixty-four — so the solver picks which architectural
register and which instruction in the retirement stream to interrogate,
and the proof therefore covers **every** register and **every** position
in the stream within the depth. It maintains a shadow of that register,
updated from `rvfi_rd_wdata` on every retired, non-trapping instruction
whose `rvfi_rd_addr` is `register_index` and whose order is earlier than
`insn_order`. At the check cycle it assumes the retiring instruction is
the one at `insn_order`, and asserts:

```
if (register_written && register_index == rvfi_rs1_addr)
    assert(register_shadow == rvfi_rs1_rdata);
if (register_written && register_index == rvfi_rs2_addr)
    assert(register_shadow == rvfi_rs2_rdata);
```

In words: **the value the core reads out of a register is the value the
last instruction to write that register wrote.** Between the write and
the read the substituted file encodes the word to a 40-bit codeword,
holds it in flip-flops, may scrub it, and decodes and corrects it on the
way out. `reg_ch0` is the property that the whole of that is the
identity function on architectural state.

That is the property `docs/43` asserts and had not proved. Its evidence
was a cycle-identical simulation on one workload; this quantifies over
all registers, all stream positions and all values, to a depth.

### 17.2 The result

**Unresolved, and that is the honest word for it.** `reg_ch0` did not
finish on the SECDED build: it waited **1 h 41 min** for the solver and
then took `SIGTERM` when the run was stopped from outside, so `sby`
recorded `DONE (ERROR, rc=16)` with "engine terminated without status"
and no trace **[fact,
`hw/soc/out/rvformal-secded/cores/ibex/checks/reg_ch0/logfile.txt`]**.

`ERROR` is not `FAIL`. No counterexample was found and none was ruled
out. **The check phase 2 exists for has no verdict**, and nothing in
this part may be read as evidence that the substitution preserves or
breaks the register-file consistency property.

What the non-result does establish is a lower bound on section 18's
finding: the same check on the same harness at the same depth took
**6 min 39 s** in phase 1 **[fact, the phase-1 logfile]**. So the
substituted core is at least **15.3x** harder here, and that ratio is a
measurement even though the verdict is not.

To close it, `reg_ch0` must be re-run alone on the secded tree carrying
`IBEX_REGFILE=secded`, `RVF_INSN_FIX=0` and `RVF_LIVENESS_DEPTH=50`
forward unchanged, with either no wall-clock limit or a stated one whose
expiry is reported as a timeout rather than as a verdict.

### 17.3 What it cannot prove, and one limit is sharper than it looks

- **It is bounded at check cycle 25.** The write and the read both
  happen within 25 cycles of reset.
- **AND THE SCRUB DOES NOT COMPLETE A PASS IN 25 CYCLES.** `docs/43`
  section 6.4: the scrub pointer walks `x1`..`x31` one register per
  idle cycle, so a full pass is **31 cycles when the core is idle and
  longer when it is not** [fact, `docs/43`]. At depth 25 the pointer
  cannot have visited every register even once. So `reg_ch0` covers the
  encode, the storage, the decode and *some* scrub writebacks — it does
  not cover a completed scrub cycle, and it certainly does not cover the
  case `docs/43` section 6.4 is really about, which is a register held
  across many scrub passes. Closing that means a deeper check, and
  section 18 measures what depth costs here.
- **It says nothing about an unwritten register.** `register_written`
  gates both assertions, so the arbitrary reset-state contents of a
  register that no instruction has written are never compared.
- **It says nothing under faults.** No injection, and the error counters
  are deleted by `opt_clean` because nothing reads them (`docs/43`
  section 6.5). A register file that silently corrected nothing would
  pass this.
- **It does not check `x0`**, which has no flip-flops in this
  configuration (`docs/43` section 6.6), and it does not check the
  register ADDRESSES, which come from the decoder and which `docs/43`
  section 6.6 already excludes from the protection.

## 18. Cost: the substituted core IS harder to prove

Both runs used the same machine, the same `-j8`, and the same competing
workload — a 9.5 GiB, ~96 % CPU process belonging to another project was
resident throughout both, and the machine's load average outside the
formal jobs was ~1 in both cases [fact]. That does not make the
comparison perfect and it does make it fair.

### 18.1 The whole run

| | Phase 1 | Phase 2 | Ratio |
|---|---:|---:|---:|
| Wall clock, `-j8` | 50 min 52 s | **54 min 45 s** | 1.08 |
| CPU (user + system) as attributed | 9,076 s | **14,027 s** | **1.55** |
| Peak RSS of the largest single job | 2.82 GiB | **3.10 GiB** | 1.10 |
| Cover set, job-seconds | 1,122 | **2,154** | **1.92** |

**[fact, `/usr/bin/time -v` and the `status` files.]** The wall-clock
ratio is the least informative of these, because both runs spent most of
their tail blocked behind six M-extension checks that were stopped on a
clock rather than finishing. The CPU and cover figures are the honest
ones, and they agree: **the substituted core costs the solver about half
again as much**.

### 18.2 Per check, which is where it is visible

Over the **62 checks that PASS in both runs and that ran inside their
own `-j8` run** — this excludes eight phase-2 checks that had to be
re-run on a nearly idle machine, section 18.3 — the phase-2 times are:

| | |
|---|---:|
| Total | 4,640 s -> **5,629 s**, x1.213 |
| Median per-check ratio | **x1.20** |
| 10th / 90th percentile ratio | x0.88 / x1.56 |
| Slower / faster | **50 of 62 slower**, 12 faster |
| Largest increases | `insn_c_sw` 89 -> 221 s (x2.48), `insn_c_lw` 89 -> 154 s, `pc_bwd` 91 -> 149 s, `insn_c_j` 54 -> 109 s |

**[fact].** The twelve that got faster and the x0.88 tenth percentile
are contention noise: eight jobs sharing a machine do not divide it
evenly, and no attempt was made to control for that. The signal is the
median and the count — a 20 % median increase with fifty of sixty-two
checks slower is not noise.

**The cover set is the cleaner measurement and it is larger.** Cover
jobs are short, uniform, and solve a satisfiability question rather than
a proof, so they are less exposed to scheduling: **x1.92 over 79 of 79,
median per-check x2.20** [fact]. Finding a witness in the substituted
core costs about twice what it costs in the stock one.

### 18.3 One place the measurement had to be repaired

Eight phase-2 bmc jobs were killed by a mistake of mine: the watcher
that stopped the six M-extension checks at their budget ended with a
blanket `pkill boolector`, which took out every solver then running,
not only the six. The eight were re-run afterwards, on a machine that
was by then nearly idle, so **their phase-2 times are not comparable
with phase-1 numbers measured under `-j8`** and they are excluded from
section 18.2 rather than quietly averaged in. Seven of them are
instruction checks that re-ran in 42-88 s and passed. The eighth is
`reg_ch0` and it is section 17.

The same mistake cost phase 1 eight cover jobs and was repaired the same
way; it is recorded twice because the second time was avoidable and the
watcher still has the defect.

### 18.4 What this predicts for a phase 3

`docs/49` measured the analogous thing at layout and found the post-CTS
resizer 5.6 times slower on a `SYNPRE` netlist. This is a milder effect
of the same kind — protection logic in the read path costs downstream
tools time — and the number to carry forward is **1.5 to 2 times, not
5 times**, for solver work on this register file at these depths.

What it does NOT predict is the cost of the things phase 2 did not
reach. The eight M-extension checks were already beyond the budget in
phase 1; a 1.5x factor on a job that did not terminate in 40 minutes is
not a number, it is a reason to change engine before trying again
(section 11 item 3).

## 19. What phase 2 settles for `docs/43`, and what it does not

`docs/43` substituted a SECDED-protected register file into Ibex by a
file list and asserted, in section 3.2 cost 1, that the substitution is
behaviourally transparent. The evidence it offered was simulation:
`docs/43` section 9.1's cycle-identical whole-SoC run and a
byte-identical ROM image, on one workload. `docs/44` added a
124-injection campaign, `docs/49` sections 9.1 added properties C6 and
C7 proving the encoder and the decoder agree on the same H matrix, and
`hw/soc/formal/regfile_secded.sby` proves the shortened code corrects
one error and detects two. **None of those is a statement about the core
still implementing RV32IMC**, and that is the gap phase 2 closes part of.

**Settled.** For the 62 RV32I and RV32C instructions whose checks pass,
at their depths and under the nine assumptions of section 4.1, the
substituted register file does not change what the instruction does to
the architectural state — not the destination register or its value, not
the source register numbers, not the next PC, not the memory address,
masks or store data, and not whether it traps. The retirement stream is
still causal, unique, PC-continuous in both directions, and it still
makes progress. Every cover obligation is still reachable. **No check
that passed on the stock core fails on the substituted one.**

**Not settled, and the list is longer than the settled one.**

- **The eight M-extension instructions.** Section 16.3. Neither run has
  a verdict for six of them, and the two that have one have it against
  a defective model. If the substitution changed `mulh`, this
  experiment could not see it.
- **REG_NOT_SETTLED**
- **Everything section 6 excludes**, unchanged: no CSR is checked, PMP
  enforcement is not proved, bus errors and debug are assumed absent,
  the clock gate is a substitute, and nothing below the RTL is touched.
  Phase 2 inherits all of it.
- **`SYNPRE = 1`.** The file elaborates at its own defaults, which are
  `docs/44`'s build. `docs/49` and `docs/62` declined `SYNPRE` three
  times; nothing here says anything about it.
- **Anything about faults.** riscv-formal checks the FAULT-FREE
  behaviour of the substituted file. It does not inject, it does not
  read the error counters — which `opt_clean` deletes because nothing
  reads them, `docs/43` section 6.5 — and it is not a substitute for
  `docs/44` section 9's campaign. A register file that corrected
  nothing but was otherwise transparent would pass every check here.
- **The addresses.** `docs/43` section 6.6 already says the file
  protects the data and not `raddr_a_i`, `raddr_b_i` or `waddr_a_i`.
  Phase 2 does not change that and does not test it.

**One correction of emphasis for `docs/43`.** Section 3.2 cost 2 warns
that "an upstream interface change breaks this, and only some shapes of
it break loudly" — a port added or removed fails at elaboration, a port
whose *meaning* changes does not. Phase 2 is a second net under the
second shape, for the instructions it covers: a register file that
returned the right value at the wrong time, or the wrong register, would
fail `reg_ch0` or one of the 62 instruction checks rather than passing
elaboration silently. It is a net with eight instruction-sized holes in
it and it is more than `docs/43` had.

