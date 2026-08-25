# 09 — Formal verification plan: a seL4-modeled assurance program

Research-phase report, document 09. Scope: (A) an accurate summary of the
seL4 verification program as the methodological reference, (B) an honest
translation of that methodology to this SoC in three tracks (RTL formal,
golden-model refinement, software), (C) a phased execution plan with CI
gates, a rootless tool checklist, and the first ten formal targets
(eleven rows: target #4 is split into #4a and #4b, because only the
voter half of it is provable against today's RTL).

Conventions, as in documents 01-06:

- **[fact]** — verifiable from the cited public source or from this
  project's own prior verified work.
- **[estimate]** — engineering judgment or derived arithmetic; the
  derivation or assumption is stated.

Why seL4 is the model: seL4 is the most complete assurance program ever
executed for a system artifact of roughly this project's complexity class
(a ~10 kSLOC kernel; this SoC is a ~10-100 kLOC-of-RTL system), and it is
the reference for exactly the discipline this project needs: a machine-read
specification written first, implementation proven against it, proofs
maintained together with the code forever after, and all assumptions stated
explicitly (https://sel4.systems/). The GR801 reference product this
project shadows is a space SoC; seL4 is simultaneously the obvious
candidate payload OS for the management CPU of such a product, which makes
the software question (Part B, track 3) concrete rather than academic.

---

## Part A — The seL4 reference program

Primary sources: the seL4 whitepaper, G. Heiser, revision 1.4.1 of
2026-07-17 (https://sel4.systems/About/seL4-whitepaper.pdf); the verified
configurations page
(https://docs.sel4.systems/projects/sel4/verified-configurations.html);
the FAQ (https://sel4.systems/About/FAQ.html); Klein et al., "seL4: Formal
Verification of an OS Kernel", SOSP 2009
(https://sel4.systems/Research/pdfs/sel4-formal-verification-os-kernel.pdf);
Klein et al., "Comprehensive Formal Verification of an OS Microkernel",
ACM TOCS 2014
(https://sel4.systems/Research/pdfs/comprehensive-formal-verification-os-microkernel.pdf).

### A.1 The proof stack [fact]

seL4's verification is a chain of machine-checked proofs in the
Isabelle/HOL theorem prover, structured as refinement between layers
(whitepaper ch. 3):

1. **Abstract specification** (Isabelle/HOL): a mathematical model of what
   the kernel does — the single source of truth for functional behavior.
2. **Executable design specification**: derived from a Haskell prototype
   of the kernel; an intermediate refinement layer between the abstract
   spec and C (SOSP 2009 paper; the whitepaper's "proof chain" collapses
   this into the abstract-model-to-C refinement).
3. **C implementation refinement proof**: the C code (a well-defined C
   subset, parsed into Isabelle/HOL with a formal C semantics) is proven
   to be a *refinement* of the abstract model — every behavior of the C
   code is allowed by the spec. This rules out entire defect classes:
   stack smashing, null-pointer dereference, code injection, control-flow
   hijacking (whitepaper 3.1).
4. **Binary verification (translation validation)**: the compiled binary
   is proven, by an automatic toolchain (formal ISA model, a provably
   correct disassembler into a graph language, rewrite rules, SMT solvers),
   to be a correct translation of the verified C — removing the compiler
   (GCC) from the trusted base (whitepaper 3.1, fig. 3.2).
5. **Security theorems above the spec**: confidentiality, integrity and
   availability are proven as properties of the abstract specification —
   i.e. the spec is proven to be *useful*, not just implemented correctly
   (whitepaper 3.1).
6. **System-level extensions**: verified capDL-based initialization (the
   booted system provably reaches the state described by the capability
   distribution spec) and the Microkit static-architecture layer, whose
   proofs were incomplete at whitepaper revision 1.4.1 (whitepaper 3.2).

Proof maintenance is part of the method, not an afterthought: "Commits to
the mainline kernel source are only allowed if they do not break proofs,
otherwise the proofs are updated as well"; the proof base exceeds one
million lines and is actively maintained (whitepaper ch. 3). The original
2009 proof was about 200,000 lines of proof script for a ~10 kSLOC kernel
(whitepaper ch. 3) — a roughly 20:1 proof-to-code ratio [estimate from the
two figures].

### A.2 Verified configurations as of 2026 [fact]

From https://docs.sel4.systems/projects/sel4/verified-configurations.html
(retrieved 2026-08) plus the FAQ:

| Architecture | Functional correctness | Binary verification | Integrity/availability | Confidentiality (infoflow) | Notes |
|---|---|---|---|---|---|
| Arm AArch32 | Yes, incl. fast path | Yes | Yes | Yes | Most complete; also verified capDL initializer; no FPU; MCS in progress |
| Arm AArch32 hyp | Yes (C level) | No | No | No | EL2 configuration |
| Arm AArch64 | Yes, incl. fast path | Not yet complete | Yes | Yes | Kernel at EL2 |
| **RISC-V 64 (RV64)** | Yes (C level, no fast path) | **Yes** | Yes | Yes | First 64-bit architecture with OS binary verification |
| x86-64 | Yes (C level, no fast path) | No | No | No | |

RISC-V specifics: binary verification for RV64 was completed in 2021
(https://microkerneldude.org/2021/05/05/sel4-on-risc-v-verified-to-binary-code/,
https://www.hensoldt.net/news/extended-trustworthiness-through-binary-verification-of-sel4r-microkernel-on-risc-vr-processor-architecture,
https://riscv.org/blog/sel4-is-verified-on-risc-v/), making seL4 on RV64
the most completely verified 64-bit configuration; the verified RV64 kernel
is about 10,000 SLOC and a 66 KiB image (FAQ, as of April 2025).
Functional correctness of the MCS (mixed-criticality scheduling) variant
was completed by Proofcraft targeting RISC-V first, with a port to AArch64
underway under DARPA's PROVERS program (https://sel4.systems/news/, as
reported 2026). Supported RV64 platforms explicitly include **Ariane
(CVA6)**, Rocket-chip variants, HiFive boards and Microchip PolarFire
(verified-configurations page) — relevant to track 3 below.

There is **no verified RV32 configuration** and none is announced
(verified-configurations page lists RISCV64 only) [fact]. seL4 requires
virtual-memory hardware; kernels for MMU-less microcontrollers are
explicitly out of seL4's design point (whitepaper ch. 1-2: address spaces
are hardware page-table backed).

### A.3 What is assumed and what is not covered [fact]

The proofs rest on three explicit assumptions (whitepaper 3.1, "Proof
assumptions"):

1. **Hardware behaves as expected** — "the kernel is at the mercy of the
   underlying hardware"; hardware verification is explicitly out of scope.
2. **The spec matches expectations** — mitigated, not eliminated, by the
   security proofs over the spec.
3. **The theorem prover is correct** — mitigated by Isabelle's small
   checking core.

Explicitly outside the verified perimeter (FAQ; verified-configurations
"universal caveats"): boot/startup code and the machine interface
(assumed), assembly stubs, TLB and cache management, device address
translation (SMMU/IOMMU), debug/profiling interfaces, DMA (proofs assume
DMA off), covert *timing* channels (storage channels are covered by the
confidentiality proof; timing channels are open research, whitepaper 3.1),
FPU on the verified configurations, and multicore (verified configurations
are unicore).

Two consequences matter for this project. First, the assumption stack of
the world's most-verified kernel *bottoms out exactly where an RTL project
begins*: seL4 consumes "correct hardware" as an axiom; a chip team is the
supplier of that axiom, and an RTL formal program is the closest available
analog of discharging it. Second, in a radiation environment the "hardware
behaves as expected" assumption is *known to be violated* (SEUs), so a
space SoC must add a layer seL4 does not model at all: proofs that the
hardware detects, masks, or recovers from state corruption. That is why
track 1 below treats TMR voters, ECC, and any-state FSM recovery as
first-class formal targets rather than nice-to-haves.

### A.4 Effort scale [fact unless noted]

- Designing and implementing the original kernel: about 2 person-years
  (py) (Klein et al., SOSP 2009).
- Original functional correctness proof (ARMv6/ARMv7, C level): about
  **20 py total**, of which about **11 py** was the seL4-specific proof and
  about **9 py** went into reusable frameworks, proof libraries, and tool
  development (Klein et al., 2009/2014).
- The complete proof stack (security theorems, binary verification, ports,
  maintenance since 2009) is "well over a million lines" of mostly
  hand-written proof (whitepaper ch. 3); the aggregate program across all
  architectures and years is plausibly 25-40 py [estimate — no single
  public total exists; derived from the per-proof publications].
- Klein et al. 2014 argue this cost is *competitive with or below*
  traditional highest-assurance certification (Common Criteria EAL7-class)
  per line of code — but only because the artifact is small.

The scale lesson for a solo developer is blunt: theorem-prover refinement
verification of even a 10 kSLOC artifact is a 10-20 py program executed by
a specialized team. Nothing in this project can or should imitate the
*mechanics* of seL4's proofs. What is imitable is the *shape* of the
program: small trusted base, spec first, proofs that live with the code,
assumptions in writing. That is what Part B transplants.

### A.5 Methodological lessons adopted [fact as to seL4; decision as to adoption]

1. **Spec before implementation, spec is an artifact.** seL4's abstract
   spec exists independently of the code and outlives it.
2. **Refinement, not testing, is the primary correctness argument** for
   the small critical core; testing remains for everything else.
3. **Proofs are maintained with the code** — a change that breaks a proof
   is not mergeable. The proof is CI, not a paper.
4. **Small trusted computing base**: verify a small thing completely
   rather than a big thing partially; put isolation boundaries around the
   unverified rest.
5. **Security properties are proven about the spec**, giving the spec
   independent meaning.
6. **Assumptions are enumerated, published, and versioned.** The honesty
   of the claim is part of the claim.
7. **Verify down the stack as far as tooling allows** (seL4: to binary;
   here: to the post-synthesis netlist).

---

## Part B — The methodology translated to this SoC

Correspondence map [decision]:

| seL4 artifact | This project's analog |
|---|---|
| Abstract spec (Isabelle/HOL) | Frozen bit-exact Python golden model (NPU, ECC, AER, quantization) + per-block formal property sets ("properties as spec") |
| Executable design spec (Haskell) | The Python golden model doubles as this layer (it is executable) |
| C refinement proof | Formal proofs per block (SymbiYosys) + lockstep cocotb equivalence RTL vs golden model + formal equivalence on datapath slices |
| Binary verification | Combinational/sequential equivalence RTL vs post-synthesis netlist and post-TMR-insertion netlist (Yosys eqy / equiv_*) |
| Integrity/confidentiality theorems | Chip-level fault-tolerance theorems: voter masking, ECC SECDED guarantees, any-state FSM recovery, bus isolation properties |
| Proof maintenance with commits | All sby/eqy/cocotb proofs in CI; a commit that breaks a proof does not merge |
| Stated proof assumptions | Assumption ledger, section C.4 |

### B.1 Track 1 — RTL formal: properties-as-spec per block

**Tools [fact].** The open formal stack is Yosys + SymbiYosys (sby), which
drives BMC, k-induction, cover, and liveness flows over SMT and
AIGER-based engines (https://symbiyosys.readthedocs.io/,
https://github.com/YosysHQ/sby). The oss-cad-suite distribution ships, in
one self-contained tarball: yosys, sby, eqy (equivalence checking), mcy
(mutation coverage), and the solver/engine set **Boolector, Bitwuzla,
Yices 2, Z3, ABC (including super_prove), aiger, avy (interpolating PDR),
Pono, and rIC3**, plus iverilog, verilator, GTKWave and Surfer
(https://github.com/YosysHQ/oss-cad-suite-build, README retrieved
2026-08). yosys-smtbmc is the underlying SMT flow used by sby's `smtbmc`
engine. This is the same tool family already used by the project's
synthesis flow, so no new vendor dependency enters the build.

**Property style [decision].** Properties are written in the Yosys-formal
subset (immediate `assert`/`assume`/`cover` plus `$past`, `$stable`,
`$rose`, `$anyseq`, `$anyconst`, `$initstate`) inside `ifdef FORMAL`
blocks or in separate `<block>_props.v` wrapper modules, so that the
Icarus/Verilator fault-injection flow (documents 02-03, rule: hand-auditable
Verilog) never sees them. One `formal/<block>/<block>.sby` file per target;
the sby file is part of the block's definition of done.

**riscv-formal and the Ibex core — status verified 2026-08 [fact].**

- riscv-formal (https://github.com/YosysHQ/riscv-formal) is a
  processor-independent formal RISC-V ISA description plus checks
  (instruction semantics validated against Spike, PC/register consistency,
  causality, memory/CSR checks) that bind to any core implementing the
  RVFI trace interface; in-tree core bindings include PicoRV32 and NERV,
  and the checks are bounded (BMC-style, depth-limited). RV32/RV64 base
  ISAs are covered; no floating point.
- Ibex's primary verification remains simulation-based: riscv-dv random
  instruction streams co-simulated against the Spike ISS, with the
  OpenTitan configuration at verification stage V2S (>90% coverage and
  pass rate) (https://ibex-core.readthedocs.io/en/latest/03_reference/verification.html).
  Ibex exposes RVFI trace ports, which is what its co-simulation checking
  is built on and what a riscv-formal binding would attach to
  (https://github.com/lowRISC/ibex).
- New since 2024/2025: Ibex carries an upstream formal flow in `dv/formal`
  that proves **trace equivalence between Ibex and the Sail RISC-V ISA
  specification** (lowRISC fork of sail-riscv), with top-level properties
  covering wrap-around liveness, loads, stores and no-memory instructions.
  The primary tool is Cadence Jasper (commercial), but the README
  documents an **open-source alternative using Yosys + rIC3** — and rIC3
  ships in oss-cad-suite. Verified configuration: 4 PMP regions, branch
  target ALU, RV32M fast multiplier, no bitmanip, flip-flop register file.
  Stated holes include: no proof of instruction-fetch correctness, some
  CSRs unchecked, bus errors assumed absent, debug-mode entry excluded,
  reset behavior unverified, memory response latency bounded at 10 cycles
  (https://github.com/lowRISC/ibex/tree/master/dv/formal). The related
  Oxford/Cambridge methodology was announced for CHERIoT-Ibex in February
  2025 (https://lowrisc.org/news/groundbreaking-formal-verification-further-enhances-the-quality-of-cheriot-ibex/).
- Consequence [decision]: for the management core this project does not
  write its own ISA-correctness program. It adopts upstream Ibex
  verification collateral (riscv-dv/Spike cosim; `dv/formal` via the
  Yosys+rIC3 path where licensing-free), and adds only *integration-level*
  formal properties (bus interface legality, interrupt/CSR protection,
  lockstep comparator behavior). If the fallback core (VexRiscv or
  PicoRV32, document 03) is chosen instead, riscv-formal binding via RVFI
  is the replacement plan — PicoRV32's binding is in-tree; SERV's upstream
  also reports riscv-formal use (https://github.com/olofk/serv).

**Why the small safety-critical blocks get full proofs [decision].**
FIFOs, ECC codecs, voters, arbiters and FSMs have state spaces where
unbounded proofs (k-induction or PDR) actually close — these are exactly
the blocks where formal is *cheaper* than simulation per bug found, and
they are the blocks whose failure is silent and mission-ending. This is
the small-TCB lesson applied to RTL: the fault-tolerance machinery is the
chip's trusted base, so it gets the strongest available evidence.

**Per-block formal targets.** Property classes: S = safety (nothing bad),
L = liveness/bounded response. Methods: BMC (bounded model check, depth
given), IND (k-induction, target k given; strengthen invariants until
inductive), PDR (IC3/property-directed reachability via abc/avy/rIC3),
EQ (equivalence, see track 2). Acceptance criteria are per-target and
binding; "full proof" means UNSAT induction/PDR, not a deep BMC.
Depths and hours are [estimate]; everything else is the plan of record.

The **Status** column is measured against the working tree of
2026-08-25 and is the only column that moves; it names the sby job that
carries the evidence, or the reason there is none. `docs/11` section 8
is the operating manual for re-running any of them. Statuses are one of
**closed** (the acceptance criterion is met and the job is in
`make -C formal everything`), **partial** (some clauses proven, the rest
named), **blocked** (the target cannot be attempted yet, with the
blocker stated) or **not started**.

| # | Block | Properties (class) | Method | Acceptance criterion | Status (2026-08-25) |
|---|---|---|---|---|---|
| 1 | Sync AER FIFO (event queues) | No overflow/underflow; count coherent with pointers; FIFO order preserved (two-symbol data-tracking abstraction); no data loss/duplication (S) | IND k<=4 after invariant strengthening; PDR fallback | Full proof of all safety props; covers: empty, full, wrap-around, simultaneous push+pop all reachable | **closed** — `formal/aer_fifo.sby` tasks `prove` (k-induction, depth 15), `prove_d4`, `bmc`, `cover`; 4 of 4 covers reached |
| 2 | SECDED ECC encoder/decoder, (72,64) Hsiao per docs/10 section 5 (64 data bits = 16 weights, 8 check bits) | decode(encode(x)) = x for all x; every 1-bit error corrected and flagged CE; every 2-bit error flagged UE, never silently miscorrected; syndrome=0 iff valid codeword (S) | BMC depth 1 over fully symbolic data + symbolic error mask constrained to weight 0/1/2 (`$anyconst`) — exhaustive for combinational logic | Full proof (UNSAT at depth 1 covers the whole input space); cross-checked against the Python golden ECC (track 2) | **closed, with the cross-check delivered by simulation rather than by eqy** — `formal/secded.sby` `bmc`, `bmc_abc`, `cover` give the full proof on two engine families. The track-2 cross-check against `sw/golden/secded.py` is layer 1 (lockstep simulation: `hw/tb/test_secded.py`, `sw/tests/test_secded.py`), not layer 2: **no eqy job exists in this repository**. See the note below the table |
| 3 | Async FIFO / CDC crossings (AER in/out, CPI capture) | Gray-code property: pointer changes one bit per clock (S); no overflow/underflow across domains (S); no data loss under symbolic clock ratios (S) | IND on gray-pointer invariants; sby multiclock BMC depth 32 for domain interaction | Full proof of pointer/flag safety; BMC clean at depth >= 2x deepest sync chain; structural CDC lint (no un-synchronized crossing) as a separate CI check | **blocked on RTL** — no asynchronous FIFO exists yet; `hw/rtl/aer_fifo.v` is synchronous and the pilot is single-clock |
| 4a | TMR voters | Output = majority(a,b,c) always (S); any single corrupted replica never changes output (S, symbolic fault via `$anyseq` on one replica) | BMC depth 1 for voter; IND with one-symbolic-fault assumption for masking | Full proofs; the masking theorem is the chip's "integrity" headline result and is reported per protected block | **closed** — `formal/tmr_voter.sby`, 8 tasks: exhaustive BMC at WIDTH 1, 8 and 32, the default width re-proven on a second engine family (`bmc_abc`), a `prove` cross-check, and a cover task at each of the three widths. S2 is stated per replica over *all* values of the third, so it covers faults of any weight, not only single-bit ones |
| 4b | TMR replica resynchronization path | After fault removal, replicas re-converge within N cycles (L as bounded safety) | Bounded-response counter for resync, under IND | Bounded-response proof with N documented per protected block | **blocked on RTL — nothing to prove** — `hw/rtl/tmr_voter.v` deliberately contains no resynchronization path (restoring a faulty replica belongs to the protected block) and `hw/rtl/pilot_top.v`, the voter's only current user, states that no replica resynchronization is implemented; there, a configuration rewrite restores all three replicas. Closing 4b needs a resync path in RTL first, then a new `formal/<block>.mk` and property file — not a task added to `formal/ecc.mk` |
| 5 | Control FSMs (scheduler, multi-pass sequencer, scrub controller, link controllers): deadlock freedom and any-state recovery | No unreachable lockup: from ANY state encoding (including illegal/SEU-corrupted), the FSM reaches a legal safe state within K cycles without asserting outputs that violate bus/interface safety (S+L); state register always in legal set once recovered (S) | IND/BMC with *unconstrained initial state* (reset assumption removed) — the standard any-state trick; bounded recovery via watchdog counter assertion | Full proof per FSM; K documented per FSM (target K <= 16); this result is the formal counterpart of the force/release fault-injection campaign and the two must agree | **partial, and the scrub controller named in this row is now discharged** — (a) `lif_core` control path, unchanged: `formal/lif_ctrl.sby` H8 proves the encoding is always one of five codewords and that an illegal encoding enters S_SAFE and latches `err_cfg`, with **K = 1**. The any-state trick is task `bmc_safe`, which starts the trace on an illegal encoding — necessary because k-induction assumes the legality invariant and makes the recovery antecedent unreachable in `prove` (see the H8 note in `formal/lif_ctrl_props.v`). (b) **scrub controller**, new: `hw/rtl/scrub.v` + `formal/scrub.sby`, 9 tasks — `prove` (k-induction depth 14 at AW 10 / CNT_W 16 / WD_W 4), `prove_small` (AW 2 / CNT_W 2 / WD_W 1), `prove_pdr` (same set on the AIGER/PDR engine family), `bmc` depth 40, `bmc_any`, `prove_any`, `bmc_live`, `cover` (14 of 14 reached), `cover_any` (2 of 2). Clause by clause: any-state recovery **K = 1** from each of the eleven illegal codewords, and S_SAFE terminal thereafter (SC13/SC14, in the two any-state tasks — `bmc_any` starts the trace on an illegal encoding, `prove_any` additionally switches off the legality invariant so k-induction closes the same result unbounded rather than to depth 10); legal-set invariant by induction (SC12); "without asserting outputs that violate bus/interface safety" — the parked controller drives no memory request, takes no ECC capture, records no fault event and freezes the walk (SC15), which is the clause that matters most here because this FSM is a *master* on the shared memory port; no unreachable lockup — every stall has a named external cause (SC16), the read-response wait is bounded at 2\*\*WD_W = **16** cycles by the watchdog with no environment assumption at all (SC17), and a whole word is bounded at 2*(G+1) + 2\*\*WD_W cycles under a stated arbiter-fairness bound G (SC18 — an assumption, C.4 ledger class, because target #7's arbiter does not exist). Also proven, beyond this row: window containment at the port (SC1/SC2) and writeback discipline (SC3–SC8: never on a double-bit detection, never on a clean word, never on a timed-out read, never at another address). Strength measured by mutation: 17 mutants, each reintroducing one of those defects, are all killed — and three of them (default arm resuming in S_IDLE, S_SAFE without `err_cfg`, S_SAFE still driving `mem_req`) pass `bmc` and `bmc_live` — the first two pass `prove` outright, the third only degrades it to UNKNOWN — and are killed **only** by the two any-state tasks. Golden-model agreement: `hw/tb/test_scrub.py` compares all 14 outputs against a cycle-accurate reference model every cycle, 13 tests at three elaborations, and kills the same 17 mutants. Still open on this row: the scheduler, multi-pass sequencer and link controllers have no RTL; `formal/scrub.mk` is not yet included from `formal/Makefile`, so its 9 tasks are not in `make -C formal everything` (a three-line change in a file this track does not own); and the fault-injection cross-check the criterion requires is not part of this evidence |
| 6 | Register file / CSR write-enable logic | Write-enable one-hot-or-zero (S); no write outside decoded address (S); lock/privilege bits actually gate writes (S); TMR'd CSRs vote correctly (reuse #4) | IND k<=2 | Full proof; every architecturally read-only bit proven unwritable | **closed for the register bank; the TMR'd-CSR clause reuses 4a and is exercised in RTL, not proven here** — `formal/npu_regbank.sby`, 5 tasks: `prove` at silicon parameters, `prove_cnt2`, `prove_n256`, `bmc`, `cover`. P4 is the read-only-immunity proof the acceptance criterion names. `hw/rtl/pilot_top.v` votes 55 configuration bits through the proven voter, but no property in this repository binds the register bank to the voter |
| 7 | Bus arbiter / interconnect (Wishbone/APB-class, document 03 IP set) | Grant mutual exclusion (S); no grant without request unless parked (S); bounded grant latency under fairness assumption (L); protocol legality: no response without request, single outstanding per master (S) | IND for mutex/legality; PDR for fairness with fairness assumptions; BMC depth 64 backstop | Full proof of mutex/legality; bounded-latency proof with stated fairness assumption in the assumption ledger | **blocked on RTL** — no arbiter or interconnect exists yet. The register bank's own single-master bus response channel is proven by P7 of target #6 |
| 8 | QSPI / multi-pass weight-streaming handshake | req/ack never lost or duplicated (S); no reload while fabric pass active unless paused (S); DMA pointer stays in configured window (S — the memory-isolation analog) | IND k<=4 | Full proof of handshake + window containment; the window property is the seL4 "integrity" analog for the NPU's memory traffic | **blocked on RTL** — no QSPI or streaming path exists; the pilot loads weights over the serial register port |
| 9 | SpaceWire codec link FSM (ECSS-E-ST-50-12C) | State order ErrorReset -> ErrorWait -> Ready -> Started -> Connecting -> Run with specified timeouts (S); credit counter bounds (never >56 outstanding N-chars) (S); disconnect/parity error always returns to ErrorReset (S) | IND for counters/order; BMC depth ~200 (timeout counters abstracted/reduced for induction) | Full proof of credit and reset properties; timeout values checked by scaled-counter abstraction with the scaling argument documented | **not started** — no codec RTL |
| 10 | Management core integration | Adopted upstream collateral (see above) + lockstep comparator: shadow-core mismatch always raises alarm within fixed delay (S) | Upstream flow + IND on comparator | Upstream suite green in project CI; comparator full proof | **not started** — no management core is integrated; the core decision itself is still open (B.1) |

Two notes on the acceptance criteria above, both of which exist because
a makefile fragment or a property file states a completion claim in one
line and the line has to be true:

- **Target #2 and `formal/ecc.mk`.** That fragment's header records
  "target #2, SECDED codec ... closed by `ecc_secded`". `ecc_secded`
  delivers the *proof* clause in full — depth-1 BMC over a symbolic
  data word and a symbolic 72-bit error vector is exhaustive for a
  combinational codec, on two engine families. It does not deliver the
  second clause as originally worded ("cross-checked by EQ ... (track
  2)"), because EQ in B.2 means Yosys `eqy`/`equiv_*` and there is no
  eqy job here **[fact — no `.eqy` file exists in the repository]**.
  The clause is met at track 2 layer 1 instead: `hw/tb/test_secded.py`
  runs the RTL against `sw/golden/secded.py` and `sw/tests/test_secded.py`
  holds the model to the code's algebraic properties. The wording of
  the criterion has been changed above from "by EQ" to "against the
  Python golden ECC" to match what is actually delivered; adding an eqy
  job would be a strengthening, not a repair, and is not scheduled.
- **Target #4 and the voter fragment.** #4 was one row and it is now
  two, because only 4a is provable today. `formal/ecc.mk` and
  `formal/tmr_voter_props.v` both already say so in prose; splitting the
  row means the plan of record says it too, and that "ecc PASSes" can no
  longer be read as "target #4 is complete". Nothing about 4a's evidence
  changes.

**Vacuity control [decision].** Every assert set ships with cover
obligations; a target with passing asserts but failing covers is *red*.
This is the formal equivalent of the "spec matches expectations" mitigation
in A.3: covers demonstrate the properties are exercised, not vacuous.

### B.2 Track 2 — golden-model refinement (spec-to-RTL)

The seL4 analog: abstract spec -> implementation refinement. Here the
abstract specification is the **bit-exact Python golden model** of the
NPU (LIF update arithmetic, threshold/reset semantics, weight addressing,
AER event ordering, quantization/packing, ECC, multi-pass schedule
semantics) plus the register-map spec. The RTL is the implementation. The
refinement evidence is layered [decision]:

1. **Lockstep simulation equivalence** (primary, whole-block): cocotb
   (https://www.cocotb.org/) drives identical stimulus into RTL and golden
   model; comparison is per-transaction (AER events out, membrane
   potentials at checkpoints) and per-cycle where the microarchitecture is
   architecturally visible. Stimulus: directed tests for every spec
   corner + constrained-random with functional coverage closure. Mutation
   coverage via mcy grades the testbench itself (mcy ships in
   oss-cad-suite) [fact as to tooling].
2. **Formal equivalence on datapath slices** (where tractable): Yosys
   `equiv_make`/`equiv_simple`/`equiv_induct` or eqy
   (https://github.com/YosysHQ/eqy) between RTL slices and reference
   implementations generated from the Python spec (spec emits a reference
   Verilog netlist for pure functions). Tractable slices [estimate]:
   LIF membrane update arithmetic, ECC encode/decode, weight
   unpack/quantize, priority/arbitration trees, address generators.
   **Not tractable** and not claimed: whole-core sequential equivalence
   across the time-multiplexed pipeline with SRAM (sequential depth ~
   number of neurons per pass makes miter induction hopeless). Said
   honestly, per A.5 lesson 6.
3. **Netlist equivalence — the binary-verification analog**: eqy proves
   RTL == post-synthesis netlist at each frozen milestone, and RTL+voters
   == post-TMR-insertion netlist under the zero-fault assumption. This
   removes Yosys-synthesis and TMR-insertion scripting from the trusted
   base, exactly as seL4's translation validation removes GCC. GL
   simulation of the smoke suite remains as a backstop (eqy partitioning
   limits are real on large SRAM-adjacent cones [estimate]).

**Discipline (the refinement rules)** [decision]:

- R1. The golden model is written and frozen (tagged `spec-vN`) before
  block RTL starts. The model itself is validated against the training
  toolchain (document 02 open question 3) and reference vectors before
  freezing — the spec must deserve its authority.
- R2. RTL merges only with green lockstep CI against the frozen spec tag.
- R3. Every RTL change re-runs the full equivalence suite for that block
  (cheap: minutes) and the formal property suite (B.1) — proofs travel
  with commits, the seL4 maintenance lesson verbatim.
- R4. A divergence is triaged in writing: spec bug (bump `spec-vN+1`,
  document the semantic change, re-run everything downstream) or RTL bug
  (fix, add the counterexample as a permanent directed test).
- R5. The spec version implemented by a given RTL commit is recorded in
  the commit and in a version register readable over the debug interface.
- R6. Interfaces frozen in document 02 (AER format, config map) are part
  of the spec: changing them is a spec bump, never a silent RTL edit.

### B.3 Track 3 — software: the seL4-on-chip question

**The hard constraint [fact].** Verified seL4 exists for RV64 with
virtual memory (SV39 page tables; the RISCV64 configuration). There is no
RV32 configuration, verified or otherwise supported, and seL4
architecturally requires an MMU. The recommended management core (Ibex
RV32IMC, document 03) has no MMU — PMP only. Therefore **seL4 cannot run
on the document-03 baseline, and no software effort changes that.** The
options:

**S1 — CVA6 (Ariane) RV64GC + seL4: the GR801-parity option.**

- Facts: GR801's NOEL-V is RV64GC (document 00), i.e. the reference
  product is seL4-capable hardware by ISA class. CVA6 is the open
  (Apache-2.0, SystemVerilog) application-class RV64GC core, 6-stage,
  single-issue, with SV39 MMU (https://github.com/openhwgroup/cva6), and
  Ariane/CVA6 is an explicitly listed supported seL4 RISCV64 platform
  (https://docs.sel4.systems/projects/sel4/verified-configurations.html).
  The silicon-measured reference (GF 22FDX tapeout) reports **210 kGE of
  core logic excluding cache SRAM**, with 16 KB I$ + 32 KB D$ and
  flip-flop TLBs, 902 MHz sign-off (Zaruba & Benini, "The Cost of
  Application-Class Processing", https://arxiv.org/abs/1904.05442).
- Area at 130 nm [estimate], computed on the primary PDK with the
  fallback kept for comparison. SG13G2 anchors: foundry SRAM macros in
  the open PDK at ~25-40 KiB/mm2, no commercial access needed (document
  04 section 3.1), and ~138 kGE/mm2 raw logic density (document 06 B.3).
  sky130 anchors: document 01's 150-190 kGE/mm2 placed and open-PDK SRAM
  at ~57 kbit/mm2.

  | Item | SG13G2 (primary) | sky130 (fallback) |
  |---|---|---|
  | 210 kGE core logic | ~2.2-2.5 mm2 placed (60-70% utilization of 138 kGE/mm2 raw) | 1.1-1.4 mm2 |
  | 48 KB caches + tags + TLB state (~430+ kbit) | ~1.3-2.1 mm2 (foundry macros) | 7-9 mm2 OpenRAM-class (1.5-2 mm2 only if commercial 130 nm SRAM compiler access materializes, document 04) |
  | CVA6 subsystem total | ~3.5-4.6 mm2 | ~8-10 mm2 |

  Versus 1.5-2.5 mm2 for the entire Ibex management subsystem (documents
  01/03). On the 25 mm2 die, the S1 caches are 9-19% of document 04's
  256-512 KiB SRAM budget — a real cost, but not "roughly half" of
  anything, and not what decides S1: on the primary PDK the area
  argument alone no longer carries the rejection.
- Memory reality [fact + estimate]: the verified seL4 RV64 image alone is
  66 KiB (FAQ); a useful seL4 system (kernel data, page tables, Microkit
  PDs, payload) needs multiple MB of RAM [estimate] — far beyond the
  hundreds-of-kB on-chip class (document 00), forcing an external
  RAM controller (HyperRAM/SDR SDRAM): new IP, new verification burden,
  new radiation-soft BOM component.
- Flow/verification fit: CVA6 is large PULP-style SystemVerilog; sv2v
  conversion at this scale, MMU/cache observability for the
  fault-injection flow, and TMR of an out-of-order-committing 6-stage
  pipeline are each project-scale risks under document 03's rules
  [estimate/judgment].
- Frequency at 130 nm: ~50-80 MHz [estimate from document 01's 4-6x
  gate-delay scaling of a 902 MHz 22FDX sign-off] — adequate, not the
  problem.
- **Verdict: rejected for v1 — on memory and verification scope, not on
  cache area.** The decisive, PDK-independent argument is the memory
  reality above: seL4's MB-class RAM requirement makes an external RAM
  controller mandatory, and no on-chip budget fixes that. The second is
  the flow/verification fit above, each item a project-scale risk on its
  own. S1 is not "add seL4", it is "build a different, GR801-sized
  chip". It also reverses the settled NOEL-V-to-RV32 shrink decision
  (document 01, section 5) that the whole area budget rests on.

**S2 — Ibex RV32 + seL4-inspired minimal verified runtime (no seL4).**

What a solo developer can honestly do, with effort in the documents-03
hour convention [estimate throughout]:

- Architecture (the transferable seL4 lessons, A.5): a **static
  partitioned bare-metal supervisor** in the style of the Microkit static
  architecture — fixed set of tasks ("protection domains"), fixed
  communication channels, no dynamic allocation after init, event-driven
  loop. M-mode supervisor ~1-2 kSLOC C; tasks in U-mode with **PMP
  regions as the isolation mechanism** (Ibex supports PMP; the upstream
  formally verified configuration runs 4 regions — B.1). Small TCB by
  construction: the NPU driver, comms stacks, and housekeeping live in
  unprivileged partitions.
- Verification that is actually reachable solo: MISRA-C:2012 subset
  compliance (cppcheck/misra + review); **Frama-C/WP or Eva for proof of
  absence of runtime errors** on the supervisor (https://frama-c.com/) —
  1-2 kSLOC is squarely inside published Frama-C case-study scale;
  **CBMC bounded proofs** (https://github.com/diffblue/cbmc) for key
  invariants: scheduler table bounds, queue index safety, ECC/CRC handler
  correctness against the same Python golden vectors as the RTL; static
  stack-depth analysis; interrupt-latency budget by construction
  (no nesting, bounded handlers). No Isabelle, no refinement proof, and
  the documentation says so plainly: this is "seL4-style architecture with
  machine-checked absence-of-runtime-error evidence", never "verified like
  seL4".
- Effort: supervisor 150-250 h; Frama-C/CBMC campaign 100-200 h;
  MISRA hygiene amortized. Fits the solo budget; produces real,
  citable assurance artifacts for the space positioning.

**S3 — Ibex now, seL4 compatibility as a later product tier.**

Keep S2 for this chip, and preserve a credible upgrade path: (a) document
the register map, interrupt semantics and AER/driver interface as a
versioned spec (R6 above) so the NPU fabric and peripheral set can be
re-hosted behind an RV64+MMU manager unchanged; (b) a future tier — larger
130 nm die with commercial SRAM access, or the same architecture on a
denser node — pairs the proven NPU/peripheral IP with CVA6 + seL4
(RISCV64 is the best-verified seL4 configuration including binary proofs,
A.2, and CVA6 is a supported platform — the pairing is technically clean).
Cost now: documentation discipline only. No RTL is written for S3 in this
phase.

**Recommendation [decision]: S2 now, S3 kept alive by interface
discipline; S1 rejected for v1.**

Justification: S1 fails the area/memory budget by roughly half a die and
contradicts document 01's architecture; S2 delivers the actual substance
of the seL4 lessons (small TCB, static architecture, machine-checked
evidence, explicit assumptions) at solo scale; S3 converts the GR801
parity question into a product-roadmap option instead of a v1 risk.

Fallback conditions (trigger -> action):

- T1. A funded mission requires a certified/verified separation kernel on
  this silicon -> that is an S1-class program: renegotiate die size,
  node, and budget explicitly; do not attempt to squeeze CVA6 into the
  25 mm2 envelope.
- T2. Frama-C/CBMC effort overruns (>2x estimate) -> descope to
  MISRA + CBMC on the two highest-value modules (scheduler, ECC/scrub
  handlers) and record the descope in the assumption ledger.
- T3. Ibex is displaced by VexRiscv/PicoRV32 (document 03 fallback) ->
  S2 carries over unchanged except PMP: if the fallback core lacks PMP,
  isolation degrades to supervisor-checked software partitioning and this
  is documented as a downgrade of the isolation claim.

---

## Part C — Phased plan

### C.1 Week 1: CI skeleton and rootless tool install

**Rootless install checklist [fact as to packaging].** oss-cad-suite is
distributed as self-contained nightly tarballs — no root, no system
packages, matching this project's rootless constraint:

1. Download the linux-x64 release tarball from
   https://github.com/YosysHQ/oss-cad-suite-build/releases (pin one dated
   release; record the date in the repo, e.g. `tools/VERSIONS`).
2. Extract to `$HOME/tools/oss-cad-suite`; activate via
   `source $HOME/tools/oss-cad-suite/environment` (or add `bin/` to PATH).
3. Smoke: `yosys -V`, `sby --help`, `eqy --help`, and one bundled sby demo
   (`mode bmc` and `mode prove`) to confirm the smtbmc engines find
   Boolector/Yices/Bitwuzla/Z3 and the aiger path finds
   abc/avy/rIC3.
4. sv2v (needed for Ibex, document 03): static binaries from
   https://github.com/zachjs/sv2v/releases — also rootless.
5. cocotb: `pip install --user cocotb` against the user Python
   (https://www.cocotb.org/).
6. Software track, later phase: Frama-C via opam in `$HOME` (rootless),
   CBMC static release binaries.
7. CI: same tarball cached on the runner; every log records the pinned
   suite date so proofs are reproducible against a fixed solver set.

**Week-1 deliverable [decision]:** `formal/fifo_sync/fifo_sync.sby`
running BMC depth 20 + `mode prove` + covers on the first AER FIFO, wired
into CI as a required check. This exists before the second RTL block
does — the program starts with the discipline, not after it.

### C.2 Gates per design phase [decision]

- **Gate F0 — block entry.** No block RTL merges without: property
  skeleton (asserts + covers) in `formal/<block>/`, golden-model stub or
  frozen spec section (R1), and the sby file in CI. Mirrors "spec first".
- **Gate F1 — block done.** The B.1 acceptance criterion for that block is
  met (full proof where specified, BMC depth met elsewhere, covers green),
  lockstep cocotb equivalence green against the frozen spec tag.
- **Gate F2 — integration.** Arbiter/interconnect proofs (#7), CDC checks
  (#3) across the assembled SoC, any-state recovery (#5) re-run on the
  integrated FSMs, management-core upstream suite green in project CI.
- **Gate F3 — tapeout freeze.** At the frozen commit: entire formal suite
  green; eqy RTL==netlist and RTL==post-TMR-netlist equivalence proofs
  green; fault-injection campaign results cross-checked against the
  #4a/#4b/#5 formal theorems (any disagreement is a blocker); assumption
  ledger (C.4) reviewed and published in the repo. If #4b is still
  blocked on RTL at that point, F3 records it as an open target rather
  than treating "ecc green" as its discharge.

Proof maintenance rule across all phases (the seL4 rule verbatim): a
commit that turns any formal target red is not mergeable; either the RTL
or the property/spec is fixed in the same change, with R4 triage recorded.

### C.3 First ten formal targets, priority order [estimate for hours]

Order maximizes early value: infrastructure-proving first, then the
fault-tolerance trusted base, then protocol machines, then the core.

| Priority | Target (B.1 ref) | Effort | Rationale for position |
|---|---|---|---|
| 1 | Sync AER FIFO full proof (#1) | 8-16 h | Proves the flow itself; week-1 CI smoke |
| 2 | SECDED encoder/decoder (#2) | 6-12 h | Exhaustive result on the hardening story's cornerstone; the spec-vs-RTL cross-check landed as lockstep simulation, not as an EQ slice (see the note under B.1) |
| 3 | TMR voter + masking theorem (#4a) | 8-16 h | The chip's integrity headline; tiny proof. #4b, the resync path, is not in this order at all: it is blocked on RTL that does not exist |
| 4 | Async FIFO / CDC (#3) | 12-24 h | Highest silent-failure risk class in the SoC |
| 5 | FSM any-state recovery template (#5), applied to scrub controller first | 16-32 h | Establishes the reusable SEU-recovery proof pattern all FSMs inherit. Executed out of order on `lif_core`'s control FSM instead, because that FSM exists and the scrub controller does not (`formal/lif_ctrl.sby`) |
| 6 | CSR/register write-enable protection (#6) | 8-16 h | Small, closes the register-file trusted base |
| 7 | Bus arbiter mutex + fairness (#7) | 16-32 h | Needed at Gate F2; fairness proof is the first liveness exercise |
| 8 | QSPI/multi-pass handshake + DMA window containment (#8) | 16-32 h | The NPU memory-isolation ("integrity") property |
| 9 | SpaceWire link FSM per ECSS (#9) | 24-48 h | Largest protocol FSM; benefits from patterns built in 5-8 |
| 10 | Management-core collateral: upstream Ibex suite in project CI, Yosys+rIC3 `dv/formal` path evaluated, comparator proof (#10) | 40-80 h | Largest item; deliberately last — it reuses upstream work rather than creating it, and depends on the final core decision |

Total: roughly 155-310 h [estimate], spread across the phases gated in
C.2 — roughly two to three of the largest single interface adaptations
(document 03's 80-115 h SpaceWire codec), i.e. about a third to
two-thirds of the corrected document 03 phase-1 interface base roll-up
(280-475 h, CPI excluded), and consistent with a solo schedule.

### C.4 Assumption ledger — what this program does not cover [decision]

Published and versioned in the repo, in imitation of A.3. Initial
contents:

1. SRAM macro internals are assumed to match their behavioral models;
   formal sees the behavioral model only. Mitigation: ECC+scrub proofs
   assume arbitrary single-bit array corruption, which subsumes most
   macro-internal upset modes; macro correctness itself rests on PDK
   characterization (document 04).
2. Timing is out of formal scope; STA (OpenSTA) is the separate authority.
   Formal results hold for any timing-clean implementation.
3. Analog/pad/PDK behavior, clock/reset generation asymmetries beyond the
   modeled CDC, and power events are out of scope.
4. Radiation *rates* are not a formal statement: formal proves masking and
   recovery mechanisms correct, fault injection measures architectural
   sensitivity, and only beam data (document 01 open question 10) speaks
   to cross-sections. The chain of claims is kept separated in all
   external material.
5. Software above the S2 supervisor (partition payloads) is tested, not
   proven; the supervisor's isolation claim is PMP-based and its
   configuration code is inside the Frama-C perimeter.
6. Bounded proofs (where full proofs were not achieved) are labeled with
   their bound in the results table; a bounded result is never reported
   as "proven".
7. Tool trust: Yosys/sby/solvers and the pinned oss-cad-suite release are
   trusted; solver diversity (two engines on key proofs) is used where
   cheap, mirroring seL4's small-checker-core argument at lower rigor.

---

## Summary of decisions

1. Adopt the seL4 program *shape* — spec-first, refinement evidence,
   proofs-with-commits, small trusted base, published assumptions — at RTL
   scale with open tools; explicitly do not imitate theorem-prover
   refinement (A.4 scale argument).
2. Track 1: ten named formal targets (eleven rows after the #4a/#4b
   split) with per-target acceptance criteria and a measured status;
   full proofs mandatory on the fault-tolerance trusted base.
3. Track 2: frozen Python golden model as the abstract spec; lockstep
   cocotb + datapath EQ slices + netlist equivalence as the refinement
   and binary-verification analogs; rules R1-R6.
4. Track 3: S2 (Ibex + seL4-inspired minimal verified runtime with
   Frama-C/CBMC evidence) now; S3 (seL4 on CVA6-class manager) preserved
   as a product tier through interface discipline; S1 rejected for v1 on
   memory (MB-class external RAM mandatory) and verification-scope
   grounds.
5. CI from week 1 (FIFO sby smoke), gates F0-F3, rootless oss-cad-suite
   toolchain, ~155-310 h initial formal budget.
