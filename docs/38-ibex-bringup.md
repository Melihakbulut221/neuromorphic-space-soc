# 38 — Ibex bring-up: does the sv2v path survive contact with this flow?

`ROADMAP.md` P3 item 2 is the management subsystem, and
`docs/03-cpu-and-ip-survey.md` section 1.4 recommends Ibex for it. That
recommendation rests on a dependency the document itself flags as
single-point and untested:

> **Fallback: VexRiscv.** If the sv2v path proves brittle in practice
> (conversion regressions, unnameable nets in fault scripts) …
> (`docs/03` section 1.4)

and section 4 makes the exposure explicit: the CPU recommendation and
the QSPI candidate "share one toolchain dependency; if the sv2v path is
rejected during CPU bring-up, both fall back together."

This document is that check, run before anything is built on top of it.
It fetches Ibex at a pinned commit, chooses a configuration
deliberately, puts it through sv2v into Yosys and OpenSTA on
`ihp-sg13g2`, simulates it in Icarus, and reports what it costs.

**Nothing is integrated.** No bus, no memory map, no NPU connection.
That is the next step and it depended on this one's answer.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash and the shuttle closes 2026-09-21. All work here is
under `hw/soc/`, a new directory. Nothing in `hw/rtl/`, `hw/tb/`,
`formal/`, `tt/` or `hw/openlane/` was read for anything but reference
and none of it was modified. Section 9 records the one place where this
work touches a shared file and why that is not a pilot change.

---

## 1. Verdict first

**`docs/03`'s recommendation survives, with two corrections to the
reasoning behind it and one new fact that weakens the "single point of
dependency" framing considerably.**

| Question | Answer |
|---|---|
| Does sv2v convert Ibex? | Yes. 38 of 38 source files, zero errors, **zero patches to Ibex** [fact] |
| Does the output synthesise on sg13g2? | Yes. Yosys 0.67+146. Every warning is counted and explained in section 4.3; none is a translation problem [fact] |
| Does the output simulate in Icarus? | Yes. Elaborates and executes a compiled RISC-V program; see section 7 [fact] |
| Is the translation *verified* equivalent? | **No.** Nothing here proves equivalence. Section 5 says exactly what was done instead and what it does and does not license |
| Is sv2v actually a single point of failure? | **Weaker than `docs/03` states.** The pinned oss-cad-suite already ships `slang.so`, and Yosys reads Ibex SystemVerilog directly through it, blocked by exactly one construct in one file. Section 6 |
| Does it fit? | On the 25 mm2 SoC envelope, comfortably: 1.6–1.9 % [fact/estimate]. On a Tiny Tapeout tile block alongside the pilot, **no** — section 8 |

The two corrections to `docs/03`:

1. **The gate-count estimate was right; the framing of the security
   configuration was not.** `docs/03` describes "lockstep (shadow core
   plus comparators)" and "register file ECC" as though they were
   separable options. In this Ibex they are one switch. `ibex_top.sv`
   lines 212–216 make `Lockstep`, `ResetAll`, `DummyInstructions` and
   `RegFileLockstepECC` all localparams of `SecureIbex`, and `MemECC`
   defaults to it (line 41) **[fact]**. There is no configuration that
   buys register-file ECC without also buying a second copy of the core.
   Section 3.3.
2. **"Its maintained sv2v+Yosys flow is exactly the open toolchain this
   project runs" overstates it.** The in-repo flow's own README opens
   with "This synthesis flow is experimental and under development, it
   does not produce tape-out quality netlists and area/timing numbers it
   generates are not representative" **[fact,
   `hw/soc/ext/ibex/syn/README.md`]**. It targets Nangate45, it is
   configured through a Nix devShell this project does not use, and it
   forces the latch-based register file. Its **sv2v invocation** is
   reusable and was reused verbatim; the flow around it was not, and
   section 4.1 lists the three reasons.

---

## 2. What was pinned

| Item | Value |
|---|---|
| Ibex upstream | https://github.com/lowRISC/ibex |
| Commit | `34b0705760ef3dfa00e99637432473d2be8f22f3` **[fact]** |
| Commit date | 2026-08-31T07:52:49+00:00, "[rtl] Add missing countermeasure tags" **[fact]** |
| Licence | **Apache-2.0**, `LICENSE` at the repository root, `SPDX-License-Identifier: Apache-2.0` in every RTL file **[fact]** |
| sv2v | v0.0.13, https://github.com/zachjs/sv2v/releases/tag/v0.0.13 |
| sv2v archive sha256 | `552799a1d76cd177b9b4cc63a3e77823a3d2a6eb4ec006569288abeff28e1ff8` **[fact]** |
| Yosys | 0.67+146, from the checkout `tools.mk` pins **[fact]** |
| Icarus / vvp | from the same checkout **[fact]** |
| OpenSTA | 3.1.0, the LibreLane tool tree the pilot's sign-off used **[fact]** |
| PDK | `ihp-sg13g2` at `c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c`, the commit `docs/12-sg13g2-flow-bringup.md` records **[fact]** |
| riscv-none-elf-gcc | xPack v15.2.0-1, sha256 `aaaa8060c914851a3e5ee1ba82cc3d6f80972f90638a05c6e823a37557a33758` **[fact]** |

### 2.1 Two tools were not in the pinned suite, and are now pinned the same way

`tools.mk` exists because a formal gate once resolved `sby` through a
glob and silently ran a sibling project's toolchain. Its rule is: one
checkout, named explicitly, overridable, verified.

`ls $OSS_CAD_SUITE/bin` on 2026-08-31 contains **no sv2v** and no
RISC-V compiler **[fact]**. Rather than resolve either off `PATH`,
`hw/soc/tools.soc.mk` includes `tools.mk` and extends it: both are
pinned by upstream release tag **and** by sha256 of the release archive,
both are fetched by an explicit `make` target that verifies the hash
before unpacking, and `make -f hw/soc/tools.soc.mk soc-toolcheck` prints
what would actually be used, with versions, and fails if anything is
missing. The GCC sha256 was checked against the `.sha` file the release
publishes rather than merely transcribed **[fact]**.

OpenSTA is taken from the LibreLane tree the pilot's sign-off runs used,
deliberately: the CPU timing numbers and the pilot timing numbers then
come from one STA build.

---

## 3. The configuration, and why

### 3.1 What was chosen

Upstream ships named configurations in `ibex_configs.yaml`. None of them
is the right one, for a reason that is a decision rather than an
oversight: upstream's `small` has `PMPEnable: 0`, and
`docs/09-formal-verification-plan.md` part B track 3 chose **option S2**,
whose isolation mechanism is PMP —

> tasks in U-mode with **PMP regions as the isolation mechanism** (Ibex
> supports PMP; the upstream formally verified configuration runs 4
> regions)

A core without PMP does not implement the software architecture this
project has already decided on. So the measured candidate is upstream's
`small` **plus PMP at 4 regions**, the number `docs/09` itself names.

`hw/soc/flow/syn_ibex.sh` defines three configurations. All three set
`BaseIsa = BaseIsaRV32I` — this Ibex is a dual-ISA core that can also be
built as CHERIoT, and the CHERIoT half is not wanted.

| Parameter | `small` | **`small-pmp`** | `small-pmp-sec` |
|---|---|---|---|
| `BaseIsa` | RV32I | **RV32I** | RV32I |
| `RV32M` | RV32MFast | **RV32MFast** | RV32MFast |
| `RV32B` | None | **None** | None |
| `RV32ZC` | Zca | **Zca** | Zca |
| `RegFile` | FF | **FF** | FF |
| `BranchTargetALU` / `WritebackStage` | 0 / 0 | **0 / 0** | 0 / 0 |
| `ICache` | 0 | **0** | 0 |
| `PMPEnable` / `PMPNumRegions` | 0 / — | **1 / 4** | 1 / 4 |
| `SecureIbex` | 0 | **0** | **1** |

`small-pmp` is the candidate. `small` is measured only so that the
number `docs/03` estimated has a like-for-like comparison.
`small-pmp-sec` is measured to answer the fault-tolerance question in
section 3.3.

### 3.2 Three deliberate departures from what upstream's own flow does

- **`RV32ZC = RV32Zca`, not `RV32ZcaZcbZcmp`.** `docs/03` specifies
  RV32IMC. Zcb and Zcmp are later compressed extensions; taking them
  would make the core wider than the survey costed.
- **`RegFile = RegFileFF`, not the latch register file.** Upstream's
  synthesis script deletes `ibex_register_file_ff.v` and keeps the
  latch-based one. This project keeps the flip-flop file and deletes the
  other two, because `docs/03` rule 1 makes verification observability
  the deciding filter: every architectural state element has to be a
  nameable flop that the fault-injection flow can find and flip. A latch
  array is cheaper and is not that.
- **A real clock gate.** `ibex_top` instantiates `prim_clock_gating` and
  leaves it to the integrator; upstream's synthesis flow substitutes a
  behavioural `always @*` latch plus an AND. `hw/soc/rtl/prim_clock_gating.v`
  binds `sg13g2_lgcp_1` instead, the PDK's integrated clock gate
  (`clock_gating_integrated_cell : "latch_posedge"`, area 27.216 um2)
  **[fact, read out of `sg13g2_stdcell_typ_1p20V_25C.lib`]**. Exactly one
  instance appears in every synthesised netlist **[fact]**. The
  behavioural model is kept behind `SG13G2_ICG_BEHAVIOURAL` for the
  Icarus run, which has no PDK cells.

### 3.3 The fault-tolerance options are NOT in the chosen configuration, and they are not separable

This matters because `docs/03`'s recommendation rests on them:

> It is the only candidate where the fault-tolerance requirement is met
> by documented, silicon-proven upstream features (delayed-shadow
> lockstep, register file ECC, bus integrity) rather than by this
> project alone

The features exist **[fact]** — `rtl/ibex_lockstep.sv` is in the tree,
sv2v converts it, and section 8 measures it. But in this Ibex there is
one switch, not three. `rtl/ibex_top.sv`:

```
212:    localparam bit          Lockstep              = SecureIbex;
213:    localparam bit          ResetAll              = Lockstep;
214:    localparam bit          DummyInstructions     = SecureIbex;
216:    localparam bit          RegFileLockstepECC    = Lockstep;
 41:  parameter bit             MemECC                = SecureIbex,
```

**[fact]**. `Lockstep`, `ResetAll`, `DummyInstructions` and
`RegFileLockstepECC` are localparams — not parameters — so they cannot
be overridden from outside. Setting `SecureIbex = 1` buys the shadow
core, the register-file ECC, reset-all flops, dummy-instruction
insertion and 39-bit memory buses together. Setting it to 0 buys none of
them.

Consequence for the architecture: **`docs/03`'s "plain Ibex + project
TMR (cheaper) versus SecureIbex-style lockstep (upstream-supported)" is
the whole decision space, and it is binary.** There is no middle option
where this project takes upstream's register-file ECC and supplies its
own coarser redundancy elsewhere. Section 8.4 costs the choice.

---

## 4. sv2v: what it did and did not handle

### 4.1 What was run

`hw/soc/flow/sv2v_ibex.sh`. The sv2v invocation — the defines
(`SYNTHESIS`, `YOSYS`), the package list, the include paths, and the
`prim_* -> prim_generic_*` renaming — is upstream's
`syn/syn_yosys.sh` **verbatim**, because that is the part under
evaluation. The flow around it is not upstream's, for three reasons:

1. Upstream's script sources `syn_setup.sh`, which ships with the cell
   library variables commented out; they are exported by a Nix devShell
   this project does not use, and the flow hardwires Nangate45.
2. Upstream deletes the flip-flop register file (section 3.2).
3. Upstream's output directory is timestamped; this needs a fixed path a
   Makefile and a `git status` can both reason about.

### 4.2 Result: clean, and no patches

| | Count |
|---|---:|
| Ibex RTL modules converted (`rtl/*.sv`, packages excluded) | **30 of 30** |
| Vendored lowRISC primitives converted | **8 of 8** |
| sv2v errors | **0** |
| sv2v warnings | **0** |
| Files removed after conversion (tracer, unused register files) | 4 |
| Output | 34 files, 15,873 lines of Verilog-2005 |

**[fact]**.

**Patches required to Ibex for the sv2v path: zero.** This is the
question `docs/03` could not answer and it is the most important line in
this document, because "a fork that has to be maintained is a different
proposition from a dependency that is read". `hw/soc/ext/ibex` is a
pristine checkout at the pinned commit; `git -C hw/soc/ext/ibex status`
is clean **[fact]**. Everything this project adds lives outside it.

Notably, sv2v converted `ibex_lockstep.sv` and the SECDED
encoder/decoder (`prim_secded_inv_39_32_{enc,dec}.sv`) — the
fault-tolerance RTL — without special handling.

### 4.3 What Yosys said about the output

Every warning, counted, with what each one is **[fact, the `syn.log`
files under `hw/soc/out/`]**:

| Warning | `small` | `small-pmp` | `small-pmp-sec` |
|---|:-:|:-:|:-:|
| `Replacing memory … with list of registers` (`mhpmevent`, `pmp_addr_rdata`, `g_pmp_registers.pmp_cfg_wdata`) | 2 | 3 | 3 |
| `Selection "*prim_generic_*" did not match any module` | 3 | 3 | 1 |
| `Resizing cell port … entropy_i from 1 bits to 8 bits` | — | — | 1 |
| **Unique messages** | **5** | **6** | **5** |

None is a translation problem, and each is worth one line:

- **`Replacing memory`** — small CSR arrays that Yosys declines to infer
  as memories and turns into flops instead. That is the wanted outcome
  on a design with no RAM macro; the extra one in the PMP builds is the
  PMP config array.
- **`Selection … did not match`** — the redundancy anchors of section
  8.5 are applied unconditionally, so in configurations where the
  `prim_generic_*` wrappers do not exist the `setattr` matches nothing
  and Yosys says so. This is a deliberate trade: a warning in two
  configurations, in exchange for the synthesis script having no
  configuration-dependent branch that could be right for one build and
  wrong for another.
- **`Resizing cell port … entropy_i`** — `ibex_dummy_instr.sv` line 88
  ties `.entropy_i('0)`. sv2v lowers the unsized SystemVerilog `'0` to
  `1'sb0`, a **signed** 1-bit zero, which the consumer must extend to
  the port's 8 bits. Sign-extending zero gives zero, so the result is
  correct. Notably **Icarus independently reports and resolves the same
  thing the same way** — "Port 6 (entropy_i) of module prim_lfsr expects
  8 bit(s), given 1 … Padding (signed) 7 high bits of the port"
  **[fact, `hw/soc/out/sim-small-pmp-sec/iverilog.log`]** — so two
  unrelated tools agree on the interpretation. The idiom is still worth
  knowing: sv2v's lowering of `'0`/`'1` relies on signedness surviving
  into the consumer, and a consumer that zero-extended instead would be
  correct for `'0` and wrong for `'1`.

### 4.4 What sv2v did NOT do

- It did not fail on anything.
- It did **not** produce unnameable nets. Module and signal names
  survive: `gen_lockstep.u_ibex_lockstep.gen_shadow_regfile_ff.register_file_shadow_i.rst_ni`
  appears verbatim in the synthesised netlist **[fact]**, which is what
  `docs/03`'s second fallback trigger ("unnameable nets in fault
  scripts") was worried about. Fault-injection scripts can target this.
- It did **not** eliminate the need for care with parameters. sv2v
  preserves `ibex_top`'s parameters as Verilog-2005 parameters, so the
  configuration is applied with Yosys `chparam` using the integer
  encodings from `ibex_pkg.sv` — enum *names* do not survive, and a
  wrong integer is a silently different core. `hw/soc/flow/syn_ibex.sh`
  writes the encoding next to every value, and
  `hw/soc/tb/ibex_min_system.v` uses the same integers so the simulated
  and synthesised configurations cannot drift apart.

---

## 5. Equivalence: what was NOT checked, stated plainly

**No equivalence between the SystemVerilog and the sv2v output was
proven, in any form.** This document does not claim the translation is
verified, and nothing below should be read as claiming it.

That is not laziness about an available check. Upstream ships one —
`syn/lec_sv2v.sh` and `syn/lec_sv2v.do` — and it drives **Cadence
Conformal**, a proprietary logic-equivalence tool this project does not
have and whose licence terms are incompatible with an open flow
**[fact]**. Upstream itself offers no open equivalence check for this
step.

Two independent corroborations were run instead. Neither is a proof;
both would have caught a gross mistranslation.

**(a) Two SystemVerilog front-ends, one design.** Section 6 explains how
Yosys was made to read the original SystemVerilog directly. Synthesising
both to `ihp-sg13g2` at `ibex_top`'s default parameters — same Yosys,
same script, same liberty, the only difference being how the SV entered
the tool:

| Front-end | Cell area, um2 | Flip-flops |
|---|---:|---:|
| sv2v v0.0.13 -> Yosys Verilog frontend | 229,120.13 | 1,972 |
| `slang.so` -> Yosys, SV read directly | 231,167.49 | 1,970 |
| **Difference** | **+2,047, +0.89 %** | **2, +0.10 %** |

**[fact]**. Two independently written SystemVerilog elaborators, taking
the same source to the same technology, land within 1 % of area and two
flip-flops of each other. A translation that had dropped or duplicated
logic would not do that.

**(b) It executes a real program.** Section 7. A mistranslation of the
decoder, the ALU, the multiplier, the load/store unit, the compressed
decoder, the CSR file or the PMP would show up as a wrong answer in a
self-checking program, and the program checks its own arithmetic against
values derived outside it.

**What this licenses and what it does not.** It licenses proceeding to
integration on the sv2v output. It does not license a claim that the
netlist is equivalent to the SystemVerilog, and any future assurance
argument that needs that claim needs an actual equivalence run — which,
today, means either a commercial LEC or bringing `eqy` to bear on a
name-matching problem that has not been attempted here.

---

## 6. The dependency is not as single-point as `docs/03` says

`docs/03` section 4 treats sv2v as one dependency shared by the CPU and
the OpenTitan SPI host, such that "if the sv2v path is rejected during
CPU bring-up, both fall back together". That is true for **Icarus**,
which is a Verilog-2005 simulator with no SystemVerilog path. It is not
true for **Yosys**.

The pinned oss-cad-suite already ships a SystemVerilog frontend:
`share/yosys/plugins/slang.so` **[fact]**. With
`plugin -i slang; read_slang --top ibex_top …`, Yosys reads Ibex's
SystemVerilog directly and fails on **exactly one construct**, producing
three errors that are three sub-expressions of one statement **[fact]**:

```
ext/ibex/rtl/ibex_top.sv:659: error: reading net state during design
                              initialization unsupported
    logic unused_scramble_inputs = scramble_key_valid_i & …
```

Rewriting that one declaration-with-initializer as a declaration plus a
continuous assign — semantically identical, five lines, in one file —
lets `read_slang` elaborate the entire Ibex hierarchy into RTLIL, and
the result synthesises to within 0.89 % of the sv2v path (section 5)
**[fact]**.

**What this changes.** The risk `docs/03` prices is "sv2v regresses or
is abandoned, and Ibex plus the OpenTitan SPI host both become
unreachable". The measured position is milder:

- **Synthesis** has two independent paths today, and the second needs a
  five-line upstream change (or a local pre-processing step) rather than
  a new tool.
- **Simulation** in Icarus has one path, sv2v, with no alternative in
  the pinned suite. Verilator, which is in the suite, consumes the
  SystemVerilog directly — so the *fallback* for simulation is a
  different simulator, not a different core.

**This does not change the recommendation**, because sv2v worked
perfectly. It changes what happens if it stops working: the answer is no
longer "fall back to VexRiscv", it is "read the SystemVerilog with
`slang` and simulate with Verilator". That is a materially smaller
contingency than `docs/03` budgets for, and it should be recorded before
anyone spends the VexRiscv adoption effort the survey holds in reserve.

---

## 7. Simulation: what was run and what it proves

### 7.1 What was built, and why not `ibex_simple_system`

Upstream ships `examples/simple_system`, which is the obvious thing to
reach for and the wrong one here. It is SystemVerilog that pulls in the
OpenTitan bus fabric, a `simulator_ctrl` block, a `prim_ram_2p` and a
DPI-C `simutil_memload`, and it is written for Verilator. Putting all of
that through sv2v would put a bus, a memory model and a DPI shim inside
the gate for the CPU; if any of them failed to convert, the result would
say nothing about whether the core converted.

`hw/soc/tb/ibex_min_system.v` is a minimal system in Verilog-2005: one
word-addressed 16 KiB array serving both the instruction and data ports
with a one-cycle data phase, plus two decoded addresses — a character
output and a halt-with-exit-code. Nothing else. **The RTL read by
Icarus is `hw/soc/gen/*.v`, the sv2v output** — not the SystemVerilog.
That is the whole point: Icarus is this project's simulator, so if the
sv2v output does not run here, `docs/03`'s recommendation does not reach
this project's flow.

### 7.2 The program

`hw/soc/tb/sw/test_ibex.c`, compiled `-march=rv32imc_zicsr_zifencei
-mabi=ilp32 -Os` with the pinned GCC, linked bare-metal against
`hw/soc/tb/sw/link.ld` and `crt0.S`, loaded as a `$readmemh` image. It
is self-checking: each test reports, the exit code is a bitmask of
failures, and the testbench fails the run unless the program reached the
halt write **and** wrote zero **and** no alert asserted **and**
`double_fault_seen_o` never asserted.

| # | Proves |
|---|---|
| 1 | Fetch and straight-line execution |
| 2 | RV32I ALU: arithmetic/logical shifts, signed and unsigned compare, xor |
| 3 | RV32M: `mul`, `mulh`, `div`, `divu`, `rem`, `remu`, and the divide-by-zero results the ISA defines |
| 4 | Loads and stores at byte, half and word width, sign extension, byte lanes against the testbench's byte-enable decode |
| 5 | Taken and not-taken branches, data-dependent loop |
| 6 | Calls, returns, stack: `fib(17)` by recursion |
| 7 | RV32C: a value computed in compressed code, plus the function inspecting its own instruction stream to assert the code really is 16-bit |
| 8 | CSR read/write (`mscratch`), `mcycle` advancing |
| 9 | Traps: a deliberate illegal instruction reaching the handler with `mcause = 2` |
| 10 | **PMP enforcement** — a locked read-only NAPOT region permits a load and faults a store with `mcause = 7`. This is the mechanism `docs/09` option S2 rests on |
| 11 | The handler never had to guess an instruction width |

### 7.3 Result

```
[TB] config: PMPEnable=1 SecureIbex=0
ibex bring-up self-test
  ok   test 0x00000001    ...    ok   test 0x00000009
  ok   test 0x0000000a    ok   test 0x0000000b
checks run: 0x0000000b  fail mask: 0x00000000
RESULT PASS
[TB] halted after 131694 cycles, exit code 0x00000000
[TB] PASS
```

**[fact, `hw/soc/out/sim-small-pmp/sim.log`]**

| Configuration | Icarus elaborates | Program result | Cycles |
|---|---|---|---:|
| `small` | yes | **PASS**, 10 checks (test 10 skipped: no PMP) | 131,706 |
| **`small-pmp`** | yes | **PASS**, 11 of 11 checks | 131,694 |
| `small-pmp-sec` | see section 7.5 | | |

**What this proves.** The sv2v output of Ibex, read by Icarus with no
SystemVerilog anywhere in the flow, fetches and executes a 1,884-byte
program compiled by an upstream RISC-V GCC, and that program's own
checks — arithmetic verified against values derived outside it,
including every RV32M operation and the ISA's divide-by-zero results —
all pass. It takes an illegal-instruction trap and returns from it. And
with PMP enabled it **enforces a locked read-only region**: the load is
permitted, the store faults with `mcause = 7`, and the stored value does
not land. That last one is the mechanism `docs/09`'s chosen software
architecture rests on, and it is now observed working rather than
assumed from the parameter name.

**What it does not prove.** It is one program, not a compliance suite.
`riscv-tests` and `riscv-dv` were not run; Ibex's own upstream
verification (Spike co-simulation, random instruction streams) is the
evidence for the core being a correct RISC-V implementation, and this
document does not restate it. What this run adds is that *the sv2v
output of it, in this project's simulator, does the same thing*.

### 7.4 Four defects were found, and all four were in this project's code, not in Ibex

Recorded because each is a trap the integration step would otherwise
walk into, and two of them are Ibex behaviours that differ from the
generic RISC-V assumption.

1. **Four wrong expected constants in the RV32M test.** Hand-computed
   `mul`, `mulh`, `divu` and `remu` results, all four wrong. The
   self-check caught them and the core was right. Every expected value
   in that test is now derived in exact integer arithmetic outside the
   program, and the derivation is written next to it.
2. **`0x00000000` is not a 32-bit illegal instruction.** Its low two bits
   are `2'b00`, which is a *compressed* encoding — it is `c.unimp`. The
   trap handler advanced `mepc` by 2, landed inside the same zero word,
   faulted again, and the run became an unbounded trap loop visible only
   as a timeout. The test now uses `0xFFFFFFFF`, whose low bits are
   `2'b11`. The handler also gained a runaway guard that halts the run
   after 64 traps, so this failure mode is now loud.
3. **Ibex's `mtvec` is 256-byte aligned and vectored-only** — stricter
   than the RISC-V privileged spec, which permits 4-byte alignment and a
   direct mode. `mtvec[7:2]` reads as zero regardless of what is
   written, `ibex_if_stage.sv` line 231 forms the exception PC as
   `{csr_mtvec_i[31:8], 8'h00}`, and MODE is hardwired to `2'b01`
   **[fact, `doc/03_reference/cs_registers.rst` and the RTL]**. A
   4-byte-aligned handler is silently truncated to the enclosing 256-byte
   boundary and the core vectors into whatever lives there. **This is a
   requirement on the S2 supervisor** (`docs/09` part B track 3) and is
   recorded here so the supervisor's vector table is designed for it
   rather than debugged into it.
4. **The reset vector is fixed and the image origin is not free.** Ibex
   resets to `{boot_addr_i[31:8], 8'h80}`. Aligning the trap vector by
   putting `.balign 256` into a `.text.*` input section raised the whole
   `.text` output section's alignment to 256, which moved `_start` from
   0x80 to 0x100 — and the linker's `*(.text .text.*)` wildcard silently
   matched the `.text.trapvec` section that caused it. The core went on
   fetching at 0x80, found padding, and executed the program from
   arbitrary offsets; the symptom was garbled character output, not a
   crash. The trap vector now has its own output section and the linker
   script carries two `ASSERT`s — `_start == 0x80` and
   `trap_entry & 0xff == 0` — so both are link-time errors rather than
   waveform archaeology.

Defects 3 and 4 are the kind that make a "the core does not work"
report. The core worked; the software around it did not. That
distinction is the reason this section exists.

---

## 8. Measured area and timing

### 8.1 Method

Yosys `stat -liberty` on the mapped netlist, and OpenSTA 3.1.0 at
**all three** `sg13g2` corners with the **5 % derate written as a
float**. Both of those are `docs/28-timing-recovery.md` section 4.4
lessons applied rather than re-learned: the PDK ships
`TIME_DERATING_CONSTRAINT` as the integer `5` and the stock SDC computes
`[expr 5 / 100]`, which is 0 in Tcl, so the flow applies no derate while
logging "5%"; and LibreLane's setup checker defaults to `["*typ*"]`, so
the corner that decides whether the part works was gated by nothing.
`hw/soc/sta/ibex.sdc.in` and `hw/soc/sta/ibex_sta.tcl.in` write both out
explicitly. The rest of the constraint set is LibreLane's `base.sdc`
specialised with the `ihp-sg13g2` defaults (0.25 ns uncertainty, 0.15 ns
clock transition, 20 % IO delay, `sg13g2_buf_4` driving cell, 6 fF load).

The frequency is found by bisection in which **every probe
re-synthesises at that period**, so ABC optimises for the number the SDC
then checks. "A netlist optimised for 20 ns that happens to have
positive slack at 16 ns" is a different claim from "the design closes at
16 ns", and only the second is a frequency.

Gate equivalents use `sg13g2_nand2_1` = 7.2576 um2 **[fact, liberty]**.

### 8.2 The verdict string had the repository's recurring defect, and it is fixed

The first version of `hw/soc/flow/sta_ibex.sh` printed:

```
RESULT small-pmp period=20 ns worst_setup=2.4337 (slow)
       worst_hold=-0.0766 (fast) SETUP_MET_ALL_CORNERS
```

A token that reads as a pass, on the same line as a negative number,
because the token was computed from the setup numbers only. **This is
the fifth instance of one shape in this repository** — `docs/28` section
4.4a (setup checker resolved to `["*typ*"]`),
`docs/23-tile-shape-decision.md` (`design__violations` not aggregating
hold), `docs/34` section 8.5 and `docs/36-checker-closure.md` (max-cap
and max-slew checkers bound to a match-nothing corner list) — a green
result only as wide as the thing it examined.

The fix is the one that has worked the other four times: **widen the
verdict, never narrow the evidence.** Every check reported is now also
judged, there is no bare pass token, and the last line is either
`ALL_CHECKS_MET (setup+hold, 3 corners)` or `NOT_MET:` followed by the
checks that failed and the corners they failed at. A caller that wants
to gate on a subset — the frequency sweep does — must name the subset in
the gate, and the sweep prints that name and the excluded hold number on
every line it emits.

### 8.3 Is the pre-place-and-route hold violation real, or an artifact?

**It is an artifact of the stage, and it is a real obligation on the
next stage. It is not evidence that the design cannot close hold, and it
is not something to drop.**

The reasoning, in the order it should be checked:

- The netlist has **no placement, no routing, no clock tree and no
  hold-fixing buffers**. Hold margin is created at place-and-route, by
  the resizer, out of exactly those things.
- The SDC charges **0.25 ns of clock uncertainty against the hold
  check** — the PDK's `CLOCK_UNCERTAINTY_CONSTRAINT`, standing in for
  skew that has not been built yet. The violation is **-0.0766 ns**, or
  31 % of that uncertainty **[fact]**. Remove the stand-in and the path
  passes by about 0.17 ns.
- The violated amount is **identical at every clock period probed** —
  -0.0766 ns at 20 ns, at 17.88, at 16.02, at 15.75 **[fact]**. A hold
  violation that does not move when the period moves is not a
  period-dependent property; it is a fixed short path plus a fixed
  uncertainty.
- The pilot closes hold in place-and-route, with
  `PL_RESIZER_HOLD_SLACK_MARGIN 0.1` and
  `GRT_RESIZER_HOLD_SLACK_MARGIN 0.05`
  (`hw/openlane/pilot_ihp/config.signoff-6x2.json`) **[fact]**, on a
  design whose synthesis netlist would have looked the same way.

So: gating the frequency sweep on hold would return "closes nowhere" for
every configuration, which is a statement about the stage and not about
the design. Hold is therefore **excluded from the sweep gate and printed
on every line of it**, and the sweep's summary says "closes SETUP",
never "closes". The obligation it hands forward is in section 10.

### 8.4 Area

Yosys `stat -liberty`, at each configuration's own closing period
**[fact]**:

| Configuration | Cells | Flip-flops | Cell area, um2 | mm2 | kGE |
|---|---:|---:|---:|---:|---:|
| `small` (no PMP) | 15,736 | 1,950 | **232,049** | 0.232 | **31.97** |
| **`small-pmp`** (the candidate) | 18,921 | 2,106 | **275,683** | 0.276 | **37.99** |
| `small-pmp-sec` (SecureIbex) | 40,236 | 4,975 | **585,233** | 0.585 | **80.64** |

**`docs/03`'s estimate was good.** It put a small RV32IMC Ibex at
25–45 kGE at 130 nm; the measurement is 31.97 kGE without PMP and 37.99
with. It put a SecureIbex-style instance at 60–100 kGE; the measurement
is 80.64 kGE. Both measured values fall inside both estimated ranges
**[fact]**.

PMP at 4 regions costs **43,634 um2, +18.8 %** over `small` **[fact]** —
more than "a few CSRs", because the address-match logic is replicated
per region and sits in the load/store path.

### 8.5 What the security configuration buys, and what it costs

SecureIbex is **+353,184 um2 over `small`, +152 %** — the area triples —
and **+112 % over `small-pmp`** **[fact]**. Flip-flops go from 2,106 to
4,975, **2.36x** **[fact]**, which is the shadow core plus the ECC bits
on the shadow register file.

An aside on measuring it at all: **a synthesiser is built to delete
deliberately redundant logic**, so the shadow core has to be protected
across `synth` and `abc`. `hw/soc/syn/ibex_syn.ys.in` holds the
`prim_generic_*` wrappers as hierarchy boundaries and releases them
afterwards — upstream's own guard, reused. Without it the same
configuration measures **569,778 um2**; with it, 585,233. **The
difference, 15,455 um2, is redundancy the mapper was removing**
**[fact]**, and a report produced without the guard would have
understated the cost of lockstep by 2.6 % while silently shipping a
netlist whose redundancy had been partly optimised away. That is worth
knowing before any TMR of this project's own is measured the same way.

**The architectural question this raises, which is not a footnote.**
This project already has its own fault-tolerance layer: TMR voters with
a proved masking theorem, SECDED, parity, scrubbing, and a
fault-injection campaign that measures them (`docs/16`, `docs/26`,
`docs/29`, `docs/30`, `docs/32`, and the closed voter rows in
`docs/35-formal-progress.md`). Ibex's lockstep is a *different* kind of
mechanism, and the two do not compose the way a reader might assume:

- **Lockstep detects; TMR masks.** A shadow core with output comparison
  raises `alert_major_internal_o` and stops trusting the core. It does
  not produce a correct answer. This project's voters do. For a
  spacecraft manager whose job is to survive an upset and keep running,
  detection alone requires a recovery policy — reset and re-init, or a
  checkpoint — that does not exist yet and is not free.
- **They protect different things.** Lockstep covers the core's own
  logic, which this project's TMR does not touch at all. TMR covers the
  NPU and the configuration state, which lockstep does not touch. They
  are complements, not alternatives — but that means the cost is
  additive, not shared.
- **The overlap that does exist is the register file.**
  `RegFileLockstepECC` is ECC over the shadow register file, and this
  project already owns a SECDED encoder/decoder with golden-vector
  tests. Two independent implementations of the same idea in one die is
  a maintenance and verification cost, not a redundancy benefit.
- **`ResetAll` is not free and shows up in section 8.6.** Turning
  `SecureIbex` on also turns every flop into a reset flop, which is what
  produced the asynchronous-path finding below.

**Nothing here decides that question**, and this document deliberately
does not. What it supplies is the price: lockstep costs 309,550 um2 over
the PMP candidate, roughly **two pilots' worth of standard cells**, and
delivers detection rather than correction. `docs/09`'s S2 architecture
does not require it. The decision belongs with the hardening
architecture, with this number in hand.

### 8.6 Timing

Bisection on the clock period, re-synthesising at each probe, setup at
all three corners with the 5 % derate **[fact]**:

| Configuration | Closes setup at | Frequency | Binding corner | Gate |
|---|---:|---:|---|---|
| `small` | **14.81 ns** | **67.5 MHz** | slow (1.08 V, 125 C) | all path groups |
| **`small-pmp`** | **16.02 ns** | **62.4 MHz** | slow | all path groups |
| `small-pmp-sec` | **16.29 ns** | **61.4 MHz** | slow | synchronous only, see below |

PMP costs 1.21 ns of period, 5.1 MHz. **Lockstep costs almost nothing in
frequency** — 0.27 ns against `small-pmp` — which is the expected shape:
the shadow core runs in parallel, not in series, so it buys its area
without lengthening the critical path.

These are **pre-layout** numbers: no parasitics, no clock tree, ideal
clocks plus the 0.25 ns uncertainty. They will move at place-and-route,
and on this project's history they move down.

For context rather than comparison, `docs/09` estimated ~50–80 MHz for a
130 nm RV32 core; 62.4 MHz is inside that.

**The asynchronous path group, and why `small-pmp-sec` is gated
differently.** Under `SecureIbex`, `ResetAll` makes every flop a reset
flop, and the shadow register file's reset arrives through a single
`sg13g2_mux2_1` (the `prim_clock_mux2` selecting `rst_ni` against
`scan_rst_ni` under `test_en_i`) that drives **1,447 `RESET_B` pins**
**[fact, counted in the netlist]**. OpenSTA reports that one cell with a
**30.85 ns delay** at the slow corner, and the reset-recovery check
therefore fails at every period tried up to 30 ns.

This is the same class of artifact as the hold violation: an unbuffered
high-fanout net in a netlist that has not been through a resizer. It is
recorded, not hidden — the sweep for that configuration is explicitly
gated on the synchronous path group, the gate name is printed on every
line it emits, and the un-gated result (`setup_all` fails at any period)
is in `hw/soc/out/sweep-small-pmp-sec-setup_sync/`. The same net exists
in the non-secure configurations — `rst_ni` drives 1,833 `RESET_B` pins
in `small-pmp` **[fact]** — where it is driven by an input port with a
`set_driving_cell` and reaches +0.18 ns of recovery slack at 16.02 ns,
so it does not bind. **For `small` and `small-pmp` the reported
frequency is a logic path; the two gates agree exactly** (`small-pmp`
closes at 16.02 ns under both `setup_all` and `setup_sync`) **[fact]**.

Reset-tree buffering is a place-and-route obligation, and section 10
carries it forward.

---

## 9. Does it fit?

Two different questions with two different answers.

### 9.1 Against the SoC envelope: comfortably

`docs/01-reference-decomposition.md` sizes the whole SoC at 25 mm2.
Taking the pilot's own measured ratio of placed cell area to synthesis
cell area, 191,588 / 155,462.93 = **1.2324** **[fact,
`docs/31-signoff-6x2.md` section 6]**, and the 70 % utilisation criterion
`docs/15`, `docs/22` and `docs/23` use:

| Configuration | Synthesis area | Placed (est.) | Core at 70 % (est.) | % of 25 mm2 |
|---|---:|---:|---:|---:|
| `small` | 232,049 | 285,970 | 408,528 | **1.63 %** |
| **`small-pmp`** | 275,683 | 339,743 | 485,348 | **1.94 %** |
| `small-pmp-sec` | 585,233 | 721,224 | 1,030,320 | **4.12 %** |

**[fact for the synthesis column, [estimate] for the rest — the ratio is
carried from one design to another and the target design's routing is
not the pilot's.]**

Under 2 % of the die for the management core is not a budget problem.
`docs/09` rejected CVA6 on area; Ibex is not in that category.

### 9.2 Against a Tiny Tapeout tile block, alongside the pilot: no

The pilot is 6x2 = 12 tiles, `DIE_AREA 0 0 1289.28 313.74`, core
392,988 um2, placed cell area 191,588 um2, 48.75 % utilisation **[fact,
`docs/31` section 6]**. That gives **32,749 um2 of core per tile**
**[fact, derived from the pilot's own 6x2 run]**.

| | Core at 70 % (est.) | Tiles needed |
|---|---:|---:|
| `small` alone | 408,528 | **13** |
| `small-pmp` alone | 485,348 | **15** |
| `small-pmp-sec` alone | 1,030,320 | **32** |
| pilot + `small` | 682,226 | **21** |
| pilot + `small-pmp` | 759,045 | **24** |
| pilot + `small-pmp-sec` | 1,304,017 | **40** |

**[estimate]**. The largest tile block the project's own tech directory
carries a pin frame for is `tt_block_8x4_pgvdd.def` = **32 tiles**
**[fact, `tt/tt/tech/ihp-sg13g2/def/`]**.

The precise statement, which is slightly different from "it does not
fit":

- **Neither configuration fits inside the pilot's frozen 12 tiles.** The
  smallest needs 13 on its own, before the pilot is placed at all.
- **Each fits alone** in a 16-tile block (`4x4` or `8x2`).
- **Together with the pilot**, `small` needs 21 tiles and `small-pmp`
  needs 24, i.e. at least `6x4` — **twice the pilot's allocation**, with
  `small-pmp` leaving no margin at all in a 24-tile block.
- **`small-pmp-sec` with the pilot needs about 40 tiles and does not fit
  in any block this project has a pin frame for.**

So Tiny Tapeout is not the vehicle for the management subsystem, and the
pilot's 12-tile allocation was never going to absorb a CPU. That is not
a surprise — the pilot is a shuttle-scale proof of the NPU tile, and the
SoC is the 25 mm2 part of section 9.1 — but it is worth stating in
numbers so nobody plans a combined shuttle submission.

---

## 10. What this does not answer

Deliberately out of scope, per the bring-up brief, and listed so the
gaps are visible rather than assumed closed:

1. **No integration.** No bus, no memory map, no interrupt wiring, no
   NPU connection, no register-map exposure. That is the next step and
   it now has an answer to build on.
2. **No equivalence proof** between the SystemVerilog and the sv2v
   output. Section 5 says what was done instead and what it licenses.
3. **No place-and-route.** Every area and timing number here is
   pre-layout. Three obligations are handed forward:
   - hold, currently -0.0766 ns (non-secure) and -0.1091 ns (secure) at
     the fast corner, to be closed by the resizer as the pilot closes it;
   - reset-tree buffering, without which the asynchronous recovery check
     fails on any `ResetAll` configuration (section 8.6);
   - the 1,447-pin and 1,833-pin reset nets are also a max-fanout
     question, which `docs/34` section 8 shows this flow reports
     unevenly.
4. **No decision between plain-Ibex-plus-project-TMR and SecureIbex.**
   Section 8.5 supplies the price and the architectural argument; the
   choice belongs with the hardening architecture.
5. **No fault injection on the core.** Section 4.4 establishes that the
   nets are nameable, which is the precondition. The campaign itself is
   not run.
6. **No software beyond a self-test.** The S2 supervisor of `docs/09`
   part B track 3 is not started. Two of its requirements are now
   known — the 256-byte `mtvec` alignment and the vectored-only mode of
   section 7.4 — and should be inputs to its design.
7. **The `docs/03` OpenTitan `spi_host` claim is untested.** This
   document only establishes that sv2v carries *Ibex*. The SPI host
   shares the dependency and has not been through it.

---

## 11. Reproducing this

```
make -f hw/soc/tools.soc.mk fetch-ibex fetch-sv2v fetch-rvgcc
make -f hw/soc/tools.soc.mk soc-toolcheck

hw/soc/flow/sv2v_ibex.sh hw/soc/ext/ibex hw/soc/gen \
                         hw/soc/tools/sv2v-Linux/sv2v

hw/soc/flow/syn_ibex.sh   small-pmp 16.02      # synthesis + area
hw/soc/flow/sta_ibex.sh   small-pmp 16.02      # all corners, 5 % derate
hw/soc/flow/sweep_ibex.sh small-pmp 3 20 7     # closing frequency
hw/soc/flow/sim_ibex.sh   small-pmp            # Icarus
```

Tracked sources are `hw/soc/{flow,rtl,tb,syn,sta}/` and
`hw/soc/tools.soc.mk` — sixteen files. `hw/soc/ext/` (the 94 MB upstream
checkout), `hw/soc/tools/` (1.6 GB of fetched toolchains), `hw/soc/gen/`
(sv2v output) and `hw/soc/out/` (every run) are gitignored, by the same
rule the repository already applies to `tt/tt/` and the SymbiYosys
working directories: fetched or generated, not vendored. Everything
ignored is pinned by commit or sha256 in `tools.soc.mk`, so what is not
tracked is still reproducible.

**The one shared file this work touches** is the repository `.gitignore`,
which gains four entries. It is not a pilot artifact:
`docs/34` section 2 pins the pilot by git blob hash of the files in
`hw/rtl/`, and section 5 lists the flow configs; `.gitignore` is in
neither set, and no file the freeze names is added, removed or altered
by this change.
