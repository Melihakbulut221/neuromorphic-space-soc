# 11 — Verification Harness

Date: 25 August 2026
Status: harness live across six RTL blocks and the pilot integration.
Every command in section 8 was executed against the working tree of this
date; the counts there are what those runs printed.

**Re-measured at HEAD on 2026-08-27: 45 SymbiYosys tasks across seven
formal jobs, 137 distinct cocotb tests across eight suites, and 191
Python tests from the repository root** [fact]. The per-section figures
throughout the rest of this document were measured before the scrub
controller, the memory hardening, the fault-injection campaign and the
ECC telemetry wiring were added. They are left in place as the record of
that state rather than patched line by line, because re-running the
command beside each one is the way to get a current number and patching
them by hand is how a document starts lying. The assert and cover
obligation totals have not been re-counted; treat them as a floor.

The original headline, superseded: **28 SymbiYosys tasks** across five
formal jobs, carrying **374 assert obligations** and **67 cover
obligations** counted once per property set at its default parameters;
**109 distinct cocotb tests** across six suites; and **145 Python
tests** from the repository root.
Scope: how to run and how to read every verification target in the
repository — the Python golden-model suite, the register-map sync check,
the cocotb/Icarus RTL suites, and the SymbiYosys formal jobs. The
normative content each target checks lives elsewhere:
`docs/09-formal-verification-plan.md` (the formal program, its
acceptance criteria and their measured status),
`docs/10-npu-mvp-spec.md` (the numbered equations and the register
list). This document is the operating manual. The physical flow —
synthesis, place and route, timing sign-off, the `hw/openlane/` tree and
the `tt/` submission — is not a verification target and is not covered
here; it has its own documents (`docs/12`, `docs/15`).

Tag convention, as in docs/09: **[fact]** is measured or read off a file
in this repository; **[decision]** is a choice made here and the reason
for it; **[estimate]** is a projection. Runtimes quoted below are
wall/CPU measurements from one machine and are **[estimate]** as
predictors for any other machine.

Everything runs rootless: no `sudo`, no system package installs, no
container. Tools come from a user-local prefix and from an unpacked
oss-cad-suite tree; Python dependencies come from two project-local
virtual environments.

**One caveat on reproducing section 8 exactly.** This repository was
being edited by several workstreams in parallel on the day these numbers
were taken, and three of them touched files the harness reads —
`hw/rtl/aer_fifo.v`, `hw/rtl/npu_regbank.v` and `hw/rtl/pilot_top.v`
were each rewritten while section 8 was being measured, and
`formal/aer_fifo_props.v` gained a cover statement mid-run **[fact —
observed by file mtime and by two `sby` processes running concurrently
against the same task directory]**. Section 8 states the time each
measurement was taken. A count that differs from section 8 is a change
to be explained, not noise — but check the source date before assuming
the harness moved.

---

## 1. What is verified today

| Block | RTL | Golden model | cocotb suite | Formal job |
|---|---|---|---|---|
| AER event FIFO | `hw/rtl/aer_fifo.v` | in-test scoreboard | `hw/tb/test_aer_fifo.py` | `formal/aer_fifo.sby` (4 tasks) |
| NPU register bank | `hw/rtl/npu_regbank.v` | `sw/golden/regmap_gen.py` (generated) | `hw/tb/test_npu_regbank.py` | `formal/npu_regbank.sby` (5 tasks) |
| LIF datapath | `hw/rtl/lif_core.v` | `sw/golden/lif_core.py` | `hw/tb/test_lif_core_rtl.py` | `formal/lif_ctrl.sby` (8 tasks) — the control path |
| SECDED (72, 64) codec | `hw/rtl/secded_enc.v`, `hw/rtl/secded_dec.v` | `sw/golden/secded.py` | `hw/tb/test_secded.py` | `formal/secded.sby` (3 tasks) |
| TMR voter | `hw/rtl/tmr_voter.v` | in-test majority model | `hw/tb/test_tmr_voter.py` | `formal/tmr_voter.sby` (8 tasks) |
| Pilot integration + TT wrapper | `hw/rtl/pilot_top.v` and its Tiny Tapeout wrapper | `lif_core.py` + `regmap_gen.py`, driven through the TT pins | `hw/tb/test_pilot_top.py` | none — an integration of blocks that are each proven above; see the note in section 6.2 |

Three independent kinds of evidence are kept for the fault-tolerance
primitives (SECDED, TMR) and for the register bank: a Python model that
is the executable form of the specification, a simulation suite that runs
the RTL against that model, and a formal job that proves the same
properties over the whole input space.

The reference sides are deliberately written in a different form from the
RTL, so that agreement is evidence rather than a restatement
**[decision]**. The voter is the clearest case: `hw/rtl/tmr_voter.v`
computes the majority as a sum of AND terms, while both
`hw/tb/test_tmr_voter.py` and the S1 property in
`formal/tmr_voter_props.v` state it as a per-bit population count. A
transcription error in the RTL therefore shows up as a disagreement; it
cannot be mirrored into the checker.

The same discipline runs through the other blocks: the register-bank
testbench walks the map out of the generated `sw/golden/regmap_gen.py`
rather than re-typing addresses, and the SECDED formal wrapper composes
the encoder with the decoder so that the two hand-written copies of the H
matrix are pinned to each other.

### 1.1 The LIF row is the one that changed, and why it matters

An earlier revision of this table recorded the LIF datapath's formal job
as "none; covered by golden-model lockstep, docs/09 track 2". That claim
has been disproved by measurement and the row now names
`formal/lif_ctrl.sby`.

The lockstep suite compares neuron state and the emitted spike stream
against `sw/golden/lif_core.py` after every command. The golden model
has no notion of `valid`/`ready`, of a command arbiter, or of a stall —
so a testbench built on it constrains the arithmetic completely and the
control interface not at all. **Five independent mutants of `ev_ready`,
`tick_ready`, the `state_clr` priority and the held-spike interaction
survived the entire lockstep suite** **[fact — recorded in the header of
`formal/lif_ctrl_props.v`; the mutation runs are
`hw/tb/results_mut_m1_*.xml` through `results_mut_m5_*.xml`]**. Two
further mutants of the SAFE state's default arm survive `lif_prove` and
`lif_bmc_live` and are caught only by `lif_bmc_safe`
(`results_mut_m6_*`, `results_mut_m7_*`).

The `results_mut_m*` numbering is repository-wide rather than
per-block: `m8` is the pilot mutant of section 6.2, and it is the one
mutant in the set whose repair was a **test** rather than a property.

Two things follow, and both are general:

1. **"Covered by lockstep against a golden model" is a claim about the
   model's interface, not about the RTL's.** Whatever the model does not
   represent is unconstrained, silently. Before writing that phrase into
   a coverage table, name what the model represents.
2. **The repair was both directed tests and a formal job.** The
   handshake tests added to `hw/tb/test_lif_core_rtl.py` kill the five
   mutants on one stimulus; `formal/lif_ctrl.sby` proves the same
   properties over the whole input space. The suite grew from 16 tests
   to **24** in the same change.

---

## 2. Layout

| Path | Role |
|---|---|
| `regmap/regmap.yaml` | register map single source (normative list: docs/10 section 10) |
| `regmap/generate.py` | emits `docs/regmap-npu.md`, `sw/golden/regmap_gen.py`, `hw/rtl/npu_regs.vh`; `--check` verifies sync |
| `sw/golden/` | bit-exact Python models: `lif_core.py`, `secded.py`, `network.py`, plus the generated `regmap_gen.py` |
| `sw/tests/` | pytest suite over the models, over spec/model/test traceability, and over the submission tree |
| `sw/requirements.txt` | dependency list for the golden-model environment |
| `conftest.py` (repository root) | the only pytest configuration: `collect_ignore` keeps a bare `pytest` out of `hw/tb/` and `tt/`. See section 4.1 |
| `hw/rtl/` | Verilog-2005 RTL for the blocks above |
| `hw/tb/Makefile` | integrator-owned cocotb driver; `TB=aer_fifo` is elaborated here, every other `TB=` forwards to the matching fragment |
| `hw/tb/Makefile.<block>` | one standalone cocotb driver per block: `.regbank`, `.lif`, `.secded`, `.tmr`, `.pilot` |
| `hw/tb/test_*.py` | cocotb test modules |
| `hw/tb/sim_build*/`, `hw/tb/results*.xml` | per-suite build directories and JUnit results (git-ignored) |
| `formal/Makefile` | integrator-owned formal driver; resolves `sby` and includes the fragments |
| `formal/npu_regbank.mk` | formal fragment for the register bank (`regbank_*` targets) |
| `formal/ecc.mk` | formal fragment for the fault-tolerance primitives, SECDED and TMR voter (`secded_*`, `tmr_*`, `ecc*` targets) |
| `formal/lif_ctrl.mk` | formal fragment for the LIF control path (`lif_*` targets) |
| `formal/<block>.sby` | SymbiYosys job files, one per block, several tasks each |
| `formal/<block>_props.v` | property sets (see section 7.2 for the two styles) |
| `formal/<task>/` | sby working directory per task: `status`, `PASS`, `logfile.txt`, `<task>.xml`, `model/`, `src/`, `engine_0/` (git-ignored) |
| `formal/<block>/` | one `status.sqlite` shared by that block's tasks (git-ignored) |

Two makefile conventions matter and are load-bearing **[decision]**:

- `hw/tb/Makefile` and `formal/Makefile` belong to the integrator. New
  blocks add a `hw/tb/Makefile.<block>` and a `formal/<block>.mk`
  instead of editing the shared files. Each fragment prefixes all its
  target names, so `include` from the shared makefile cannot collide.
  `formal/lif_ctrl.mk` is the most recent instance of the convention
  working: the fragment was written and exercised standalone
  (`make -C formal -f lif_ctrl.mk lif_all`) before the integrator added
  one `include` line, `lif_all` to `everything` and `lif_clean` to
  `clean-all`.
- Every cocotb fragment sets its own `SIM_BUILD` and
  `COCOTB_RESULTS_FILE`, so suites can run back to back (or in parallel)
  without overwriting each other's build directory or JUnit file. The
  formal side has no equivalent protection; see section 7.1.

`hw/tb/Makefile` rejects an unrecognised `TB=` at parse time rather than
starting a simulator with no sources — a failure mode that used to
delete `results.xml` first and then report an unrelated cocotb
traceback. The accepted set is `aer_fifo regbank lif secded tmr pilot`.

---

## 3. Rootless tool setup

### 3.1 Simulator and solvers

The only simulator the harness needs on `PATH` is Icarus Verilog, from a
user-local prefix. On the reference machine **[fact]**:

    $ command -v iverilog
    ~/.local/bin/iverilog
    $ iverilog -V | head -1
    Icarus Verilog version 12.0 (stable) ()
    $ command -v yosys
    ~/.local/bin/yosys

A `yosys` is present too, but the formal flow does not use it: sby
prepends its own `bin` to `PATH` and runs the `yosys` from its own
checkout.

SymbiYosys (`sby`) is not on `PATH` on this machine, and the makefiles do
not require it to be. `formal/Makefile` — and each `formal/<block>.mk`
when run standalone — prefers `sby` from `PATH` and otherwise takes the
first of three known oss-cad-suite checkouts:

    ~/oss-cad-suite/bin/sby
    ~/Documents/gt2n-soc/tools/oss-cad-suite/bin/sby
    ~/Downloads/oss-cad-suite-linux-x64-20260804/oss-cad-suite/bin/sby

If none exists the makefile stops with `sby not found: install
oss-cad-suite or put sby on PATH` rather than running a partial gate.
The checkout carries its own `yosys`, `yosys-smtbmc`, `yosys-abc` and the
solvers the jobs name — `yices`, `boolector`, `bitwuzla`, with `z3` and
`cvc5` also present **[fact]** — so the formal flow needs nothing
installed system-wide.

To see which `sby` a run will use without running it:

    make -C formal -n prove

On the reference machine this prints the second path above **[fact]**:
the first does not exist here, so the `wildcard` skips it.

The `formal/<block>.mk` fragments skip their own discovery when the
including makefile has already resolved `SBY`
(`ifeq ($(origin SBY),undefined)`), so the standalone and the included
forms cannot disagree about which binary runs.

### 3.2 The two Python environments

There are two project-local virtual environments, and the split is
deliberate **[decision]**.

| Environment | Contents (measured) | Used by |
|---|---|---|
| `.venv/` (repo root) | numpy 2.5.2, pytest 9.1.1, PyYAML 6.0.3, Python 3.12.3 | golden models, `sw/tests/`, `regmap/generate.py` |
| `hw/.venv/` | cocotb 2.0.1, find_libpython 0.5.1, pytest 9.1.1, PyYAML 6.0.3, Python 3.12.3 | every cocotb suite |

Creating them from scratch (both command lines executed and verified to
reproduce exactly the package sets above) **[fact]**:

    python3 -m venv .venv
    .venv/bin/pip install -r sw/requirements.txt

    python3 -m venv hw/.venv
    hw/.venv/bin/pip install cocotb pytest pyyaml

Why they are separate:

1. **cocotb is not an ordinary library.** It installs a native GPI/VPI
   layer alongside `find_libpython`; the simulator `dlopen`s that layer
   and then runs the testbench *inside* an embedded interpreter, which
   the install ties to one Python ABI. The environment is therefore part
   of the simulation toolchain, not part of the model's dependency set.
   Keeping it in `hw/.venv` means a cocotb or simulator upgrade cannot
   perturb the interpreter in which the normative golden model and its
   tests run, and a change on the model side cannot break elaboration.
2. **The split is structural, not a convention.** Every
   `hw/tb/Makefile*` computes `VENV_BIN` as `../.venv/bin` relative to
   `hw/tb`, i.e. `hw/.venv/bin`, and — if `cocotb-config` is not already
   on `PATH` — re-invokes itself with that directory prepended. The
   re-invocation exists because make older than 4.4 does not pass an
   exported `PATH` into `$(shell ...)`, which the cocotb makefiles rely
   on. So the cocotb suites find their own environment; you never
   activate anything.
3. **Neither environment contains the other's key package** — `hw/.venv`
   has no numpy, `.venv` has no cocotb **[fact — both re-checked, each
   raises `ModuleNotFoundError` for the other's package]**. The
   consequence that matters is directional: a cocotb suite launched
   against the root `.venv` dies at once with `ModuleNotFoundError: No
   module named 'cocotb'` rather than half-running, so a mistake in the
   environment is loud.

One honest qualification **[fact]**: as measured today `sw/tests/`
collects and runs to the *same* result under both interpreters, because
the golden models are plain-integer Python and do not import numpy at
run time — numpy is a declared dependency in `sw/requirements.txt`, not
a run-time one for the current suite. The separation is therefore a
containment decision taken before it becomes forced, not a repair for an
existing conflict. Use `.venv/` for the Python suite anyway: it is the
environment `sw/requirements.txt` describes, and the moment a model
starts using numpy the other interpreter stops working.

The cocotb testbenches import the golden models directly out of the
source tree (`sys.path` insertion of `sw/` or `sw/golden/` at the top of
`hw/tb/test_lif_core_rtl.py`, `hw/tb/test_secded.py`,
`hw/tb/test_npu_regbank.py`, `hw/tb/test_pilot_top.py`), so the models
are shared across the two environments as source, never as an installed
package. There is no third copy to drift.

---

## 4. Python golden-model suite

    .venv/bin/python -m pytest -q            # from the repository root
    .venv/bin/python -m pytest sw/tests/ -q  # the same set, named explicitly

Both forms collect the same tests, because `conftest.py` at the
repository root ignores everything else (section 4.1). The measured
count and result are in section 8.1; the per-file breakdown is measured
the same way, with

    .venv/bin/python -m pytest --collect-only -q | sed 's/::.*//' | sort | uniq -c

| File | What it holds |
|---|---|
| `sw/tests/test_lif_core.py` | the bit-exact LIF model against docs/10 equations E1..E8, E10 |
| `sw/tests/test_secded.py` | the (72, 64) Hsiao code: matrix shape, `decode(encode(x)) == x`, exhaustive single-bit correction, double-bit detection, and the algebraic properties the formal wrapper relies on |
| `sw/tests/test_multipass.py` | E9 tiling equivalence: tiled passes are bit-identical to one wide core |
| `sw/tests/test_events.py` | E8 event ordering and determinism |
| `sw/tests/test_regmap.py` | register-map sync (section 5) |
| `sw/tests/test_traceability.py` | every equation tag `En` in docs/10 has a `test_e<n>_*`, and no test cites an equation the spec does not define |
| `sw/tests/test_e2e.py` | a 3-layer toy SNN classifying two rate-coded patterns above chance |
| `sw/tests/test_tt_submission.py` | the `tt/` submission tree: `MANIFEST.sha256` against the files, `tt/src` against `hw/rtl`, and the whole tree against a fresh in-memory regeneration |
| `sw/tests/test_flow_evidence.py` | added by the physical-flow workstream; holds **`docs/12` section 4 only** — the sign-off and provenance claims — against the LibreLane run tree they were read from. It parses no other document, and `docs/12`'s descriptive tables (4.2, 4.3, 4.6) are out of its scope by its own statement. The `docs/15` figure that is machine-held is the 4x2 tile decision, and its guard is `test_tt_submission.py::test_tile_shape_is_the_documented_decision` |

`test_traceability.py` is the piece that keeps the model files honest: it
fails if the specification grows an equation nobody tested, or if a test
cites an equation that was removed. Run a single file the usual way, for
example `.venv/bin/python -m pytest sw/tests/test_secded.py -q`.

`test_tt_submission.py` is the piece that keeps the *submission* honest,
and it is the one most likely to be red in a working tree: it fails
whenever `hw/rtl` has been edited and `scripts/gen_tt_submission.py` has
not been re-run. That is a drift report about the submission, not a
defect in the harness, and the fix is to regenerate — never to edit
under `tt/`.

### 4.1 Why there is a root `conftest.py`

Three directories in this repository hold files named `test_*.py` and
only one of them is a pytest suite. Without `conftest.py`, a bare
`pytest` at the root walks into `hw/tb/` and aborts collection for the
whole repository — taking `sw/tests/` down with it — for two independent
reasons **[fact, both reproduced]**:

- `hw/tb/test_secded.py` and `sw/tests/test_secded.py` share a module
  basename, and pytest's rootdir import mode reports an "import file
  mismatch" for whichever it collects second;
- the root virtualenv deliberately has no cocotb (section 3.2), so every
  `hw/tb` module also fails to import there.

`collect_ignore = ["hw/tb", "tt"]` closes both, and `sw/tests/__init__.py`
closes the basename collision as well, so an explicit
`pytest hw/tb/... sw/tests/...` inside the cocotb virtualenv stays
collectable. A tree added later and not listed aborts collection loudly
rather than failing silently; that is the intended failure mode and the
fix is one line in `conftest.py`.

---

## 5. Register-map sync check

`regmap/regmap.yaml` is the single source. `regmap/generate.py` emits
three derived files — `docs/regmap-npu.md`, `sw/golden/regmap_gen.py`,
`hw/rtl/npu_regs.vh` — each carrying a `GENERATED FILE` header. Edit
only the YAML.

    .venv/bin/python regmap/generate.py            # regenerate
    .venv/bin/python regmap/generate.py --check    # verify sync

Measured behaviour **[fact]**:

- In sync: `--check` prints nothing and exits 0. Silence is the pass.
- Out of sync: it prints `stale generated files: <paths>` and exits 1.
  Verified by appending a line to a scratch copy of `hw/rtl/npu_regs.vh`,
  which produced exactly `stale generated files: hw/rtl/npu_regs.vh`
  with exit code 1; re-running the generator (`wrote docs/regmap-npu.md`,
  `wrote sw/golden/regmap_gen.py`, `wrote hw/rtl/npu_regs.vh`) restored
  exit 0.
- A plain regeneration always rewrites all three files and reports each.

`sw/tests/test_regmap.py` runs `--check` as a subprocess *and*
cross-checks the YAML against the normative register table in docs/10
section 10 — name, offset, access class, literal reset value — so the
specification and the map cannot drift apart silently. It also holds the
field-level bit assignments: `FAULT_CLR` at 0x88 declares five bits
(`b0 CNT_SEC`, `b1 CNT_DED`, `b2 CNT_EVQ_OVF`, `b3 CNT_AXON_OOR`,
`b4 FAULT_ADDR`, bits 31:5 ignored) and docs/10 section 10 now states
the same assignment rather than only "clear the fault counters". The
generator resolves its own repository root from `__file__`, so it can be
invoked from any working directory.

The RTL and the register-bank testbench both consume the generated
artifacts rather than re-typing addresses: `hw/rtl/npu_regbank.v`
includes `npu_regs.vh`, and `hw/tb/test_npu_regbank.py` walks the
register list programmatically out of `sw/golden/regmap_gen.py`. A
register renamed in the YAML therefore changes what the testbench checks
on the next run instead of quietly losing coverage.

---

## 6. cocotb suites (Icarus)

### 6.1 Shape

All six drivers share the rootless discovery described in section 3.2
and are run from `hw/tb`. `SIM ?= icarus` and `TOPLEVEL_LANG ?= verilog`
are overridable; `EXTRA_COMPILE_ARGS` is appended to `COMPILE_ARGS` in
every driver, for coverage or waveform builds. Results land in
`results*.xml` (JUnit) next to a per-suite `sim_build*/`.

Two drivers accept a source override so a mutation run can point the
same suite at a modified copy of the RTL without editing the tree:
`LIF_SRC` in `Makefile.lif` and `REGBANK_SRC` in `Makefile.regbank`
**[fact — grepped; no other driver has one]**. `LIF_SRC` is the
mechanism the five surviving LIF mutants of section 1.1 were found
with. Any block that acquires a mutation campaign should add the same
two-line pattern (a `<BLOCK>_SRC ?=` default plus its use in
`VERILOG_SOURCES`) rather than a shared one, so the override stays
inside the fragment that owns the block.

### 6.2 Per block

**AER event FIFO** — the integrator-owned driver, default `TB=aer_fifo`:

    cd hw/tb && make

11 tests. Reset state, fill/drain order, registered-output timing,
simultaneous read/write at constant occupancy, overflow-drop counting,
drop on coincident read+write at full, drop-counter clear including the
coincident-drop restart-at-1 convention, drop-counter saturation without
wrap, read-on-empty refusal, a randomized scoreboard against a Python
model of the whole contract, and reset mid-traffic with recovery. The
saturation test dominates the runtime, because it drives the 16-bit
sticky counter all the way to its rail: 1.90 s of the suite's 2.15 s on
the run behind section 8 **[fact]**.

**NPU register bank**:

    cd hw/tb && make -f Makefile.regbank         # 512x512 default
    cd hw/tb && make -f Makefile.regbank small   # 256x256
    cd hw/tb && make -f Makefile.regbank lint    # Verilator lint

**33 tests**, and the same 33 run at both geometries. Reset values,
identity and version constants, RW write/readback with field masking, RO
writes ignored, WO/W1C reading as zero, W1C set-by-hardware and
clear-by-write-one including the coincident race (hardware wins),
fault-counter increment and clear including the clear/event race,
`FAULT_ADDR` latching, the `FAULT_CLR` mask re-export, CTRL
self-clearing bits, the configuration lock while busy — including its
rising-edge hole and a sweep over every locked register — `cfg_valid`
start gating, `ERR_CFG` latching on a write that invalidates a running
configuration, the weight-load port and its back-to-back commits, the
`ECC_INJ` arm/consume path, the AER software ports, `EVQ_OUT`
back-to-back reads and its single wait state, APB bridge adaptation, the
neuron-state port, unmapped and misaligned access, one response beat per
transaction, reset mid-traffic, and a randomized scoreboard over the
whole map.

The `small` target is the case that catches a reset value taken from
the `regmap.yaml` 512 literal instead of from the `N_NEURONS` /
`N_AXONS` parameters (RTL header convention C8). It is a second
*geometry*, not a second test list.

Fault-counter *saturation* is deliberately not simulated: the counters
are 32 bits wide in silicon, so the rail is unreachable in a simulation
of any sane length. It is proven instead — for all widths — by P6 in
`formal/npu_regbank_props.v`, and shown reachable by the `CNT_W = 2`
cover task (section 7.2). This is the general pattern where the two
methods meet: what simulation cannot reach, the proof covers; what the
proof states abstractly, the cover task exhibits as a concrete trace.

**LIF datapath (lockstep against the golden model)**:

    cd hw/tb && make -f Makefile.lif                        # 32x32 default
    cd hw/tb && make -f Makefile.lif N_NEURONS=8  N_AXONS=4
    cd hw/tb && make -f Makefile.lif N_NEURONS=64 N_AXONS=16

**24 tests** at each geometry. The testbench reads `N_NEURONS` and
`N_AXONS` back from the DUT and builds `sw/golden/lif_core.py` to match,
then runs the two side by side: after every command the entire neuron
state file (V and R for all neurons, through the debug port) and the
emitted spike stream are compared, so a divergence fails on the step
that caused it and names the neuron.

The suite is now two halves, and the split is the point of section 1.1:

- **Arithmetic, against the golden model** — saturation at both 16-bit
  rails, leak toward zero including at full negative magnitude, leak
  during refractory, refractory gating and countdown, tile offset in
  emitted ids, ascending scan order, threshold check after update and on
  zero contribution, back-to-back events on one neuron, the E9 partial
  tile, 2000 randomized lockstep steps at a fixed seed, and a randomized
  configuration sweep.
- **Control, against nothing the golden model knows about** — command
  arbitration (a spike outranks a tick and loses neither; `state_clr`
  outranks both), no command granted while one is in flight, the output
  handshake never retracting or mutating, backpressure losing no spike,
  no deadlock with both channels held, a held spike not swallowing
  `state_clr`, a debug write outside IDLE being dropped rather than
  raced, ticks never emitting, `state_clr` zeroing the state file, and
  the SAFE state on a corrupted FSM encoding. These are the tests that
  kill the five mutants; `formal/lif_ctrl.sby` proves the same
  properties without stimulus.

The directed cases address specific neuron and axon indices, so the
suite needs `N_NEURONS >= 4` and `N_AXONS >= 4`. That is the only
restriction; the driver header records green runs at 4x4, 8x4, 32x32 and
64x16 for the whole suite and at 961x4, 1000x4 and 1024x4 for the
geometry-sensitive cases, which are run per test with `COCOTB_TESTCASE`
because the big geometries are slow.

**SECDED (72, 64) codec** — two combinational toplevels, and cocotb runs
one toplevel per simulation, so the driver invokes the simulator twice
with the same test module and skips the other DUT's tests each time:

    cd hw/tb && make -f Makefile.secded          # both elaborations
    cd hw/tb && make -f Makefile.secded enc      # encoder only
    cd hw/tb && make -f Makefile.secded dec      # decoder only

Read the result as **12 distinct tests — 3 encoder, 9 decoder** — each
executed exactly once across the two elaborations; the `SKIP` counts are
the other DUT's tests, not un-run coverage. The encoder and the
decoder's syndrome path are linear over GF(2), so agreeing with the
model on the 64 one-hot data words plus the zero word settles all 2^64
inputs: those sweeps are exhaustive, not sampled. The correction path is
nonlinear and is swept over all 72 single-bit error positions and over
the listed double-bit pairs.

**TMR voter** — parameterized, so the same tests run at three elaborated
widths:

    cd hw/tb && make -f Makefile.tmr             # widths 1, 8, 32
    cd hw/tb && make -f Makefile.tmr w8          # one width: w1 | w8 | w32

**7 distinct tests, of which 6 execute at any one width and 1 is skipped
as inapplicable** — so the run prints `TESTS=7 PASS=6 FAIL=0 SKIP=1` at
each width, and the suite is 18 executions, not 21 **[fact]**. The two
width-gated tests are complementary:
`test_exhaustive_at_width_one` runs only at WIDTH 1 (it sweeps all eight
input combinations) and `test_three_way_disagreement_is_flagged` only at
WIDTH >= 2 (three pairwise-distinct one-bit words do not exist). An
earlier revision of this document recorded `PASS=7 SKIP=0` and "21
executions"; that was wrong in a direction worth naming, because a
`SKIP` that is actually un-run coverage and a `SKIP` that is a width
guard look identical in the summary line. `TMR_WIDTH` is exported by the
driver precisely so the guard can be evaluated at import time, and the
testbench cross-checks it against the elaborated parameter on every
vector, so the two cannot drift apart unnoticed.

**Pilot integration**:

    cd hw/tb && make -f Makefile.pilot                       # 8x8, queues 4/4
    cd hw/tb && make -f Makefile.pilot N_NEURONS=4 N_AXONS=8
    cd hw/tb && make -f Makefile.pilot EVQ_IN_DEPTH=2 EVQ_OUT_DEPTH=2

**22 tests.** The device under test is the Tiny Tapeout wrapper, not
`pilot_top` directly: driving the TT port list is the only way to cover
the pin map and the reset synchronizer. Reset values against
`regmap_gen.py`, pin directions and quiescence, asynchronous reset
release, serial register access and chip-select setup, the
configuration lock, input-queue overflow, soft reset, state clear and
the state port, the SYNC barrier, out-of-range axon drops, the parallel
AER pins, inference against `sw/golden/lif_core.py` with and without
tile offset, SECDED single-bit correction, a syndrome walk, double-bit
detection with the E10 zero substitution, TMR masking of a corrupted
configuration replica, an upset in `lif_core`'s FSM state register seen
at `STATUS.ERR_CFG` and the ERR pin together with its `CTRL.SOFT_RST`
recovery, the same upset checked against the *live* half of that status
bit, and the `FAULT_CLR` bit assignment against `regmap.yaml`.

The wrapper has no parameters — a Tiny Tapeout top level cannot have any
— and Icarus applies `-P` only to a ROOT module, never to a nested
instance, so the geometry is selected by macros rather than by
`chparam`. The build directory and the results file both carry the
geometry, because Icarus bakes the defines into `sim.vvp` while the
cocotb makefile only rebuilds when a source is newer: without that, a
bare geometry change silently re-runs the previous elaboration.

One harness trap in that suite, found while adding the test below and
worth stating because nothing about it is obvious from a failure. The
serial helpers drive `SER_SCK` at exactly `clk/4` — host obligation H1
at its limit — by counting nanoseconds forward from wherever the test
happens to be. A test that samples a pin mid-cycle, `await
RisingEdge(clk)` followed by a short `Timer` to let combinational logic
settle, leaves the whole subsequent timeline offset by that `Timer`, and
every SPI edge of the next frame inherits it. **One leftover nanosecond
moves the MISO sampling point across a system-clock edge and the host
reads the entire 32-bit word shifted by one bit position** — `0xA5A51234`
came back as `0xD2D2891A` **[fact — measured with a throwaway
`SCRATCH` round trip, on the grid and one nanosecond off it]**. It
presents as a plausible-looking wrong register value several frames
later, not as a protocol error. `hw/tb/test_pilot_top.py` now has a
one-line `realign()` helper whose whole job is to await one more clock
edge, and whose docstring is the reason. This is a property of the
testbench, not of the design: a real host's `SER_SCK` has no phase
relationship to `clk`, which is what the two-flop synchronizer is for.

**There is no formal job for the pilot**, and that is a scope statement
rather than an omission: every block inside it is proven individually
above, and what the pilot adds is wiring.

An earlier revision of this section recorded a wiring gap here:
`lif_core.err_cfg` left unconnected, so an upset in the datapath's own
control FSM reached neither `STATUS.ERR_CFG` nor the ERR pin even though
`lif_ctrl.sby` H8 proves that `err_cfg` is latched correctly. **That gap
is closed.** `pilot_top.v` connects the port, ORs it into
`STATUS.ERR_CFG` live and latches it into the sticky bit as well
(`pilot_top.v` section 7), and Verilator no longer reports the
`PINMISSING` that named it — one warning, and only that one, is the
measured difference the connection makes (`docs/15` section 5.2).

Closing it also produced a lesson about mutation checking that is worth
carrying, because it is general. The two terms of `STATUS.ERR_CFG` are
not independently observable from the pins: while the core is parked,
the latch re-arms from `lif_err_cfg` on every clock edge, so the sticky
term alone answers every host-visible stimulus and reverting the live
`|| lif_err_cfg` term passed the whole pilot suite — **21 of 21 at the
time, measured** **[fact]**. A connection can be real, correct, and
still carry no test. The repair was a test that separates the terms two
ways at once: the cycle in which the ERR pin is already high and the
sticky flop is not yet set, and a clear that reaches the sticky flop
while the core is still parked. Each kills the mutant on its own
**[fact — both re-measured against the reverted term; the recorded run
is `hw/tb/results_mut_m8_errcfg_live_term_dropped.xml`, 22 tests,
21 pass, 1 fail]**.

`make -f Makefile.<block> clean` is cocotb's own clean and removes one
build directory at a time, so for the multi-elaboration drivers pass the
selector too: `make -f Makefile.secded clean SECDED_DUT=enc`,
`make -f Makefile.tmr clean TMR_WIDTH=8`.

---

## 7. Formal proofs (SymbiYosys)

### 7.1 Running

`formal/Makefile` resolves `sby` once and includes the three per-block
fragments, so from the repository root:

    make -C formal all           # aer_fifo:    prove prove_d4 bmc cover
    make -C formal regbank_all   # npu_regbank: prove prove_cnt2 prove_n256 bmc cover
    make -C formal ecc           # secded + tmr_voter, all eleven tasks
    make -C formal lif_all       # lif_ctrl, all eight tasks
    make -C formal lif_mem_all   # lif_core memory codes, all eight tasks
    make -C formal scrub_all     # scrub controller, all nine tasks
    make -C formal everything    # all six of the above
    make -C formal clean-all     # remove every sby working directory

Note the trap in the first line: `all` covers only `aer_fifo`. It was
kept that way deliberately so that invocations written when `aer_fifo`
was the only block keep their original meaning; `everything` is the whole
formal gate and is what section 9 uses **[decision]**. `make -C formal
clean` is likewise `aer_fifo`-only, against `clean-all`.

Individual tasks are ordinary targets: `make -C formal prove`,
`make -C formal regbank_bmc`, `make -C formal tmr_cover`,
`make -C formal lif_bmc_safe`, and so on. The fragments also run
standalone, which is how they are used before the integrator wires a new
block in:

    make -C formal -f npu_regbank.mk regbank_all
    make -C formal -f ecc.mk ecc
    make -C formal -f lif_ctrl.mk lif_all

Or invoke sby directly, which is what every target above reduces to:

    cd formal && <sby> -f tmr_voter.sby bmc_w32

**Forty-five tasks exist in total**: four for `aer_fifo`, five for
`npu_regbank`, three for `secded`, eight for `tmr_voter`, eight for
`lif_ctrl`, eight for `lif_mem`, nine for `scrub` **[fact — counted from
the seven `.sby` `[tasks]` sections and confirmed by
`make -C formal -n everything | grep -c "sby -f"`, which prints 45]**.
The count was 28 until the memory-hardening and scrub blocks were wired
in; `lif_mem` in particular sat on disk passing for a day before
`formal/lif_mem.mk` was included here, which is why the count is now
stated with a command that recomputes it rather than as a number to be
trusted. Each writes a working directory `formal/<task>/`; `-f`
forces a clean re-run, so a stale directory is never mistaken for a
result.

The count grew from seventeen in three places, and each is worth
knowing because each closes a specific hole:

| Job | Was | Now | What the new tasks buy |
|---|---|---|---|
| `npu_regbank` | 4 | 5 | `prove_n256` re-proves the whole set on a core smaller than the `regmap.yaml` default. That is where a `CFG_NEUR`/`CFG_AXON` reset value taken from the 512 literal instead of from the parameters (RTL header C8) shows up: at 256 the literal is out of range, so P1 and the `cfg_valid` part of P10 fail |
| `ecc` (`tmr_voter` half) | 9 | 11 | `cover_w1` and `cover_w32`. The cover set is width-conditional — the three-way-split cover is emitted only for WIDTH >= 2 — so covering at WIDTH 8 alone left the WIDTH 1 and WIDTH 32 property sets with no reachability check at all, and never exercised the generate arm the condition guards |
| `lif_ctrl` | 0 | 8 | the whole job, for the reason in section 1.1 |

**One task at a time per working directory.** That same `-f` deletes
`formal/<task>/` before it starts, so two concurrent runs of the *same*
task destroy each other: the second start removes the first one's
directory, and the first dies with

    status:  ERROR 16 <n>
    summary: engine_0 (smtbmc yices) did not return a status

Observed repeatedly on this tree while this document was being written,
and worth recording in detail because the symptom is not what the
documentation used to predict. A `make -C formal everything` completed
with exit code 0 and `aer_fifo_bmc` logged `DONE (PASS, rc=0)`; forty
seconds later the `formal/aer_fifo_bmc/` directory had been recreated
from scratch by another session's `sby -f aer_fifo.sby bmc` — with no
`status` and no `PASS` file in it, so the on-disk evidence for a task
that had passed was simply gone **[fact]**. Later, two
`make -C formal everything` invocations from different sessions were
live at once, and the `formal/*/status` set on disk was a mixture of the
two, with the four `aer_fifo` entries appearing, disappearing and
changing their CPU-time field over a ten-minute window **[fact]**.

It is a workspace collision, not a property failure, and it has two
practical consequences:

- **The durable record of a run is its stdout log, not the task
  directories.** `formal/<task>/status` describes whichever run touched
  that directory last, which under contention is not necessarily yours.
  Capture the output — `make -C formal everything 2>&1 | tee <log>` —
  and read `DONE (PASS, rc=0)` lines out of it if there is any chance
  another gate is in flight.
- **A missing verdict file is a collision symptom, not just `ERROR 16`.**
  The documented signature used to be an `ERROR 16` status line; a task
  directory that exists with no `status` and no `PASS` in it is the same
  event caught one step earlier.

Distinct tasks are much less exposed, since each owns its own directory,
but the tasks of one job still share a `formal/<block>/status.sqlite`,
so the safe rule is **one formal gate at a time, repository-wide** —
which in a repository worked by several parallel workstreams is a
coordination rule, not a shell habit. The cocotb suites and the Python
suite are unaffected and can run alongside anything, because every
cocotb fragment owns its `SIM_BUILD` and results file (section 2).

If you see `ERROR 16` with "did not return a status", or a task
directory with no verdict file in it, check for a second `sby` before
suspecting the design:

    pgrep -af 'sby -f'

### 7.2 What each job proves

Two property styles are in use, and the choice is per block **[decision]**:

- **`ifdef FORMAL` include** — `formal/aer_fifo_props.v`,
  `formal/npu_regbank_props.v` and `formal/lif_ctrl_props.v` are
  textually included at the end of the corresponding module body,
  guarded by `` `ifdef FORMAL ``. `read_verilog -formal` defines
  `FORMAL`, so the properties see module internals (pointers, write
  enables, register state, the FSM encoding) directly and are invisible
  to Icarus and to synthesis.
- **Wrapper module** — `formal/secded_props.v` and
  `formal/tmr_voter_props.v` are separate top modules that instantiate
  the RTL and drive it with `$anyconst` inputs. Used where the property
  set must see more than one instance: the SECDED wrapper composes the
  encoder with the decoder, which additionally pins the two copies of the
  H matrix to each other.

| Job | Task | Mode / depth | Parameters | Substance |
|---|---|---|---|---|
| `aer_fifo.sby` | `prove` | k-induction, depth 15 | WIDTH=16, DEPTH=64 | P1 level bookkeeping; P2 exact empty/full flags; P3 no overflow corruption; P4 drop-counter semantics with saturation; P5 FIFO order preservation by the two-token method; **P7 pointer TMR masking** — the three replicas of each pointer agree at all times and the voted pointer is bit-identical to a fault-free reference count whatever the faulty replica does, under a symbolic fault XORed into one replica per pointer with the single assumption of at most one faulty replica per pointer per cycle. P7 is what makes P1..P6 hold under a fault, and P1..P6 are what say the masking is complete; **P8 the correction is reported exactly** — `ptr_mismatch` is high if and only if a replica is faulty this cycle, so neither a missed correction nor a false alarm during clean traffic |
| | `prove_d4` | k-induction, depth 15 | DEPTH=4, WIDTH=8 via `chparam` | same properties, fast parameterization check |
| | `bmc` | bounded, depth 40 | defaults | bounded backstop |
| | `cover` | reachability, depth 150 | defaults | seven statements: empty, full, wrap-around and drop; **P6** a word queued while `rd_data` is not that word, which pins the read port as registered rather than show-ahead; and **P9** a corrected upset reachable while the queue is delivering an event. P9 is the vacuity alarm for the fault model — if an assumption were ever tightened until no fault is reachable, P7 and P8 would still pass and only this cover would fail (section 7.4) |
| `npu_regbank.sby` | `prove` | k-induction, depth 10 | CNT_W=32 (silicon) | P1 reset values; P2 decode integrity (write enables one-hot-or-zero, none outside a decoded address); P3 no phantom writes, and a decoded write lands; P4 read-only immunity; P5 W1C semantics; P6 counter semantics; P7 bus response; P8 configuration lock and start gating; **P9 EVQ_OUT read and pop are atomic** (docs/10 section 7.2, C9 — proven with a ghost bit tracking whether the presented head has already been handed out); **P10 the exported datapath ports** (P3..P8 assert on the internal `r_*` state; P10 carries the same claims out to the ports the rest of the chip sees) |
| | `prove_cnt2` | k-induction, depth 10 | CNT_W=2 via `chparam` | same properties at the width the cover task uses |
| | `prove_n256` | k-induction, depth 10 | N_NEURONS=256, N_AXONS=256 via `chparam` | same properties on a core smaller than the regmap default — the C8 parameter-versus-literal case |
| | `bmc` | bounded, depth 30 | CNT_W=32 | bounded backstop |
| | `cover` | reachability, depth 40 | CNT_W=2 | every proven behaviour shown reachable, counter saturation included — at 32 bits saturation is unreachable in a bounded trace, and an unreachable cover would be red under the docs/09 vacuity rule |
| `lif_ctrl.sby` | `prove` | k-induction, depth 12 | N_NEURONS=4, N_AXONS=4 | H1 grant discipline; H2 priority (`state_clr` > event > tick, at most one grant per cycle); H3 no lost command; H4 no phantom or duplicated command; H5 scan integrity (every accepted command visits every neuron exactly once, ascending, no skip under stall); H6 output handshake (never retracted without `out_ready`, held word stable, only S_EV emits, held spike never overwritten); H7 deadlock freedom in structural form; H8 SAFE state per docs/10 section 11.4; H9 debug-port interlock |
| | `prove_3x2` | k-induction, depth 12 | 3 x 2 via `chparam` | non-power-of-two neuron count, where `$clog2(3) = 2` leaves an unused index value and the wrap is done by `last_j` rather than by counter overflow |
| | `prove_8x2` | k-induction, depth 12 | 8 x 2 via `chparam` | second parameterization point |
| | `bmc` | bounded, depth 40 | 4 x 4 | bounded backstop |
| | `bmc_live` | bounded, depth 40, `-DLIF_LIVENESS` | 4 x 4 | bounded-liveness watchdog: under a sink-fairness assumption (`out_ready` not low on two consecutive cycles) a held `ev_valid` is granted within `2*N_NEURONS + 4` cycles, and likewise `tick_valid`. The obligation is re-armed while `state_clr` is requested or while parked in S_SAFE, neither being a state in which service is owed |
| | `bmc_safe` | bounded, depth 12, `-DLIF_SAFE_ENTRY` | 4 x 4 | the SAFE-state response, from a trace that **starts** on an illegal encoding. Load-bearing, not decoration: see the note below |
| | `cover` | reachability, depth 40 | 4 x 4 | every arbitration and handshake behaviour proven above shown reachable |
| | `cover_safe` | reachability, depth 8, `-DLIF_SAFE_ENTRY` | 4 x 4 | a concrete SAFE-state trace from an injected illegal encoding |
| `secded.sby` | `bmc` | bounded, depth 1, smtbmc boolector | — | S1 clean word / `decode(encode(x)) == x`; S2 syndrome zero only for codewords; S3 every one-bit error corrected; S4 every two-bit error detected and never miscorrected; S5 flag exclusivity; C1/C2 the encoder's `check_out` port agrees with `code_out` and with the decoder's independent copy of the H matrix |
| | `bmc_abc` | bounded, depth 1, abc bmc3 | — | the same property set on an independent engine family — minus C1/C2, which its pipeline discharges before the solver sees them (section 7.4) |
| | `cover` | reachability, depth 1 | — | every branch of the weight implications reachable |
| `tmr_voter.sby` | `bmc` | bounded, depth 1, smtbmc boolector | WIDTH=8 | S1 bitwise majority by population count; S2 the masking theorem, stated once per replica over **all** values of the third, so it covers a fault of any weight; S3 exact disagreement flag; S4 unanimity passes through |
| | `bmc_abc` | bounded, depth 1, abc bmc3 | WIDTH=8 | same set, independent engine family |
| | `bmc_w1` | bounded, depth 1 | WIDTH=1 via `chparam` | degenerate width |
| | `bmc_w32` | bounded, depth 1 | WIDTH=32 via `chparam` | register-file width |
| | `prove` | k-induction, depth 1 | WIDTH=8 | cross-check of the "no state to induct over" reasoning |
| | `cover` | reachability, depth 1 | WIDTH=8 | masking with a genuinely corrupted replica, unanimity, three-way split |
| | `cover_w1` | reachability, depth 1 | WIDTH=1 | the same cover set at the degenerate width, where the three-way-split cover is not generated |
| | `cover_w32` | reachability, depth 1 | WIDTH=32 | the same cover set at the register-file width |

Engines: `aer_fifo.sby`, `npu_regbank.sby` and `lif_ctrl.sby` each
declare one `[engines]` line, `smtbmc yices`, used by all of their
tasks; `secded.sby` and `tmr_voter.sby` assign an engine per task as
shown in the table.

Four points that are easy to misread:

- **Depth 1 BMC is a full proof here, not a bounded one.** The SECDED
  codec and the voter are purely combinational and their inputs are
  `$anyconst`, so a single time step ranges over the entire input space
  — 2^64 x 2^72 for the codec, 2^(3xWIDTH) for the voter at the
  elaborated width. This is the acceptance criterion of docs/09 targets
  #2 and #4a. On the three sequential blocks, by contrast, `bmc` is only
  a backstop; the proof is the `prove` task.
- **`lif_bmc_safe` is not redundant with `lif_prove`, and the reason
  generalizes.** The invariant "the state encoding is always one of the
  five legal codewords" is itself one of the H8 assertions, and
  k-induction assumes every assertion at steps 0..k-1 before checking
  step k. So in `prove` the encoding at step k-1 is *assumed* legal,
  which makes the antecedent of the recovery property — "if the previous
  encoding was illegal" — false at every checked step. `prove` therefore
  reports PASS for a default arm that silently resumes in IDLE and
  latches nothing, which is exactly the defect the property was written
  to catch. Measured: **two mutants of the default arm (recover to IDLE;
  enter SAFE without latching `ERR_CFG`) both survive `lif_prove` and
  `lif_bmc_live`, and both fail `lif_bmc_safe`** **[fact]**. The
  `LIF_SAFE_ENTRY` define starts the trace on an illegal encoding
  instead of from reset, which is the only way to reach the antecedent.
  Do not drop `bmc_safe` from the gate on the grounds that `prove`
  covers it.
- **Engine diversity is expressed as two tasks, not two engines in one
  task** **[decision]**. sby races the engines listed inside a task and
  reports the first to answer, so a second engine there would be a speed
  hedge. `bmc` and `bmc_abc` use different engine families — an SMT
  bit-blaster and the AIGER/SAT path — so a solver-specific defect would
  have to occur in both to go unnoticed. Section 7.4 records the one
  place where that diversity does not reach: two of the SECDED
  assertions never appear in the AIGER model at all.
- **Engine choice is measured, not inherited.** The `secded.sby` header
  records the bake-off that picked its engines: boolector closed that
  query in about 17 s and abc bmc3 in about 10 s, while yices — the
  engine `aer_fifo.sby` uses — had not returned after 3 minutes
  **[fact, from the job header]**. Re-measured on the runs behind this
  document, `secded bmc` reported 7 s and `secded bmc_abc` 2 s of CPU
  **[fact]**; the ordering holds, the absolute numbers move with load.
  Do not copy an engine choice from one block to another without
  re-timing it.

`aer_fifo`, `npu_regbank` and `lif_ctrl` all leave reset unconstrained
after the initial state, so their proofs include reset asserted in the
middle of traffic.

### 7.3 Reading a status file

Each task directory holds a one-line `formal/<task>/status`. sby writes
it at exit as

    <STATUS> <retcode> <total_time>

- **`<STATUS>`** — the task verdict, one of exactly six values:
  `PASS`, `FAIL`, `UNKNOWN`, `ERROR`, `TIMEOUT`, `CANCELLED`. Every
  target in this repository currently reads `PASS`. sby also drops a
  summary file *named after the verdict* in the same directory, so the
  presence of `formal/<task>/PASS` rather than `formal/<task>/FAIL` is
  itself the result, and section 7.4 check 2 reads its contents.
- **`<retcode>`** — sby's process exit code. It is `0` when the verdict
  matches what the job expected, and otherwise `2` for `FAIL`, `4` for
  `UNKNOWN`, `8` for `TIMEOUT`, `16` for `ERROR`, `32` for `CANCELLED`
  — and `1` for a `PASS` that was *not* expected, which is how a job
  declaring `expect fail` reports that a bug it was pinning has been
  fixed. This field is what a `make` target or a CI step keys on.
- **`<total_time>`** — **elapsed process (CPU) time for the task's child
  processes, in whole seconds.** It is `getrusage(RUSAGE_CHILDREN)`
  user+system time, computed in sby's `sby_core.py` and written by the
  `sby` launcher as `f"{task.status} {task.retcode} {task.total_time}"`
  **[fact, read from the installed sby source]**.

That third field is a **cost** number. It is not a proof depth, not a
number of solver steps, and not a number of properties. This matters
because all eight `tmr_voter` tasks report

    PASS 0 0

The trailing zero says the whole task — read_verilog, `prep`, SMT export
and solve — finished in under one second of CPU, which is unsurprising
for a combinational voter at widths 1, 8 and 32. It does not mean zero
steps ran and it does not mean zero properties were checked. The
corresponding log shows the work that was done:

    $ grep 'step 0\|Status:' formal/tmr_voter_bmc/logfile.txt
    ...  Checking assumptions in step 0..
    ...  Checking assertions in step 0..
    ...  Status: passed

A depth-1 BMC checks exactly one time step, step 0, which for this model
is the whole input space (section 7.2).

The comparison that settles it: in the same `make -C formal everything`
run, `formal/tmr_voter_bmc/status` read `PASS 0 0` while
`formal/aer_fifo_bmc` was the most expensive task in the gate at over
six minutes of solver time **[fact]**. The expensive one is the *weaker*
result — a bounded check to depth 40 on a sequential design — while the
cheap one is exhaustive over its entire input space. Cost tracks how
hard the model was to solve, not how much the result is worth. The
status line is the right thing to gate a build on and the wrong thing to
judge proof strength by; sections 7.2 and 7.4 are where strength is
decided.

`formal/<task>/status.path` is bookkeeping only: it points at the shared
`formal/<block>/status.sqlite` database that sby writes across the tasks
of one job.

### 7.4 Telling a real proof from a vacuous one

A `PASS` status is necessary and not sufficient. A property file that
never reached the model, a `prove` task whose induction step silently did
not run, or an assertion set that is unreachable in the first place would
all leave `PASS 0 <n>` behind. Four checks, in order of what they catch:

**1. Did the properties reach the model?** For every task driven by the
`smtbmc` engine, sby writes a JUnit file `formal/<task>/<task>.xml` with
one `<testcase>` per property, typed `ASSERT` or `COVER`:

    grep -c 'type="ASSERT"' formal/npu_regbank_prove/npu_regbank_prove.xml
    grep -c 'type="COVER"'  formal/npu_regbank_cover/npu_regbank_cover.xml

This is the check that catches the dangerous silent failure. The
`ifdef FORMAL` blocks lose their entire property set — with no error —
if the model is ever read without `read_verilog -formal`, and the task
then passes trivially. A collapsing assert count is the symptom. The
expected counts for this working tree are in section 8.3; treat a change
in them as a change to be explained, not noise.

The counts also confirm that a `chparam` override actually took effect,
which is the other thing that can quietly turn a parameterized proof into
a proof of something else. The voter's property file states one per-bit
majority assertion plus seven width-independent ones, so its assert count
should be `WIDTH + 7` — and the measured counts are **8, 15 and 39 at
WIDTH 1, 8 and 32** **[fact]**. Its cover count drops from 7 to 6 at
WIDTH 1, because the three-way-disagreement cover is generated only where
it is reachable — which is precisely why `cover_w1` and `cover_w32`
exist as their own tasks.

**The two `bmc_abc` tasks are the exception, and one of them is a
genuine gap.** The AIGER/SAT path returns a single aggregate verdict, so
their JUnit file holds one `<testcase>` and the grep above returns zero.
Use the engine's own structural line in the log instead — `PO` is the
number of assert outputs in the AIGER model:

    $ grep 'PI/PO/Reg' formal/tmr_voter_bmc_abc/logfile.txt
    ... Running "bmc3". PI/PO/Reg = 25/15/25. ...
    $ grep 'PI/PO/Reg' formal/secded_bmc_abc/logfile.txt
    ... Running "bmc3". PI/PO/Reg = 137/21/137. ...

The voter matches: **15 assert outputs against the 15 the `smtbmc` task
reports.** The codec does **not**: the AIGER model carries **21** while
the `smtbmc` task reports **23** **[fact]**. Earlier revisions of this
document quoted 21 for both engines and called them equal; that was
right when the SECDED property set had 21 assertions and stopped being
right when C1 and C2 were added.

The two missing ones are exactly C1 and C2, identified by name from
`formal/secded_bmc_abc/model/design_aiger.ywa`, whose `asserts` list
holds 21 entries covering `secded_props.v` lines 114-148 and neither of
lines 166-167 **[fact]**. The mechanism is in the two generated
scripts, which are not the same pipeline: `design_aiger.ys` runs
`opt -full` before `aigmap`, while `design_smt2.ys` runs no optimization
at all. C1 asserts `enc_check == code[71:64]` and `hw/rtl/secded_enc.v`
ends with `assign code_out = {check_out, data_in};`, so `opt -full`
discharges it structurally and `opt_clean` removes the now-constant
assert; C2 goes the same way once the two XOR cones are proven identical
**[fact for the counts, the names and the two scripts; the C2 half of
the mechanism is an [estimate] — the assertion's absence is measured,
the reason it folded is inferred]**.

What this costs, stated plainly: C1 and C2 **hold** — they are
discharged by the optimizer rather than by a solver, which is a stronger
outcome, not a weaker one — but the engine-diversity argument covers
**21 of the codec's 23 assertions, not all 23**. Two engine families
check S1..S5; only the SMT path ever sees the check-port pair. If that
matters for a given release, the fix is a third task with
`opt` suppressed, not a rewording here.

The general rule this refines: if the two engines disagree about how
many properties exist, one of them is not looking at the design you
think it is — *or* one of them optimized the difference away, and the
`.ywa` map is how you tell those two apart in about a minute.

**2. Was the mode actually a proof for this design?** Read
`formal/<task>/PASS`, which sby writes only on success:

    $ cat formal/npu_regbank_prove/PASS
    Elapsed clock time [H:MM:SS (secs)]: ...
    Elapsed process time [H:MM:SS (secs)]: ...
    engine_0 (smtbmc yices) returned pass for basecase
    engine_0 (smtbmc yices) returned pass for induction
    engine_0 did not produce any traces
    successful proof by k-induction.

For a `prove` task, both `basecase` and `induction` must return pass and
the last line must read `successful proof by k-induction.` A basecase-only
result is a bounded check wearing a proof's name. For a `bmc` task, the
depth in the `.sby` file decides what the result means: depth 1 over a
combinational `$anyconst` model is exhaustive; depth 12, 30 or 40 over a
sequential model is a backstop.

**3. Are the properties non-vacuous?** Every block ships cover
obligations, per the docs/09 rule that "a target with passing asserts but
failing covers is *red*". The cover task must pass *and* must report
reached statements:

    grep -c 'reached cover statement' formal/tmr_voter_cover/PASS

A cover that is never reached means the assertions guarding that branch
were never exercised, whatever the assert task said. Two blocks now
carry more than one cover task for exactly this reason: `tmr_voter`
because its cover set is width-conditional, and `lif_ctrl` because
S_SAFE is unreachable from reset by construction, so a reset-rooted
cover about it would be meaningless.

**4. Did anything get optimized away?**

    grep -i warning formal/aer_fifo_prove/logfile.txt

The expected output on this tree **[fact]**: the four `aer_fifo` tasks
each emit exactly one benign line,

    Warning: Replacing memory \mem with list of registers. See aer_fifo.v:86

which is Yosys reporting that the FIFO's small array was flattened into
flops for the solver; the `npu_regbank`, `lif_ctrl`, `secded` and
`tmr_voter` tasks emit none at all. Anything else — an unresolved
module, a `chparam` override that did not apply, a blackboxed instance —
deserves reading before the `PASS` is believed.

---

## 8. Every verification target

Every row below was produced by executing the command in that row on the
working tree of 25 August 2026, at the clock time each subsection names
**[fact]**. Property counts come from the per-task JUnit files as
described in section 7.4; the third field of a formal status line is CPU
time and is deliberately not tabulated, because it moves with machine
load. `sby` in the formal commands is whatever section 3.1 resolves; the
`make -C formal` forms resolve it for you.

Read the caveat at the top of this document before treating a difference
as a regression: `hw/rtl/aer_fifo.v`, `hw/rtl/npu_regbank.v`,
`hw/rtl/pilot_top.v` and `formal/aer_fifo_props.v` were all edited by
other workstreams during the window these measurements were taken.

### 8.1 Python and register map

| Target | Command | Status | Count |
|---|---|---|---|
| Register-map sync | `.venv/bin/python regmap/generate.py --check` | OK | exit 0, no output |
| Golden-model suite | `.venv/bin/python -m pytest -q` | PASS | **145 passed in 0.28 s**, measured 11:08 local |

The pytest suite is the one number in this document that a reader is
most likely to find different, because `sw/tests/test_tt_submission.py`
is a *drift guard over another workstream's output* rather than a test
of the harness. Its three checks — `MANIFEST.sha256` against the files,
`tt/src` against `hw/rtl`, and the tree against a fresh regeneration —
go red the moment `hw/rtl` is edited without re-running
`scripts/gen_tt_submission.py`, which is a state this repository passes
through routinely during a design wave. It was observed red for about
twenty minutes on the day of this measurement, between an edit to
`hw/rtl/pilot_top.v` and the regeneration that followed it **[fact —
two failures, `test_rtl_sources_are_byte_identical_to_hw_rtl` and
`test_tree_matches_the_generator`, both green again at 11:08]**. When it
is red, the message to read is "the submission tree is stale", and the
fix is `python3 scripts/gen_tt_submission.py`, never an edit under
`tt/`.

The measured composition, from `--collect-only`, is the durable part:

| File | Tests |
|---|---|
| `sw/tests/test_lif_core.py` | 41 |
| `sw/tests/test_secded.py` | 37 |
| `sw/tests/test_flow_evidence.py` | 16 |
| `sw/tests/test_tt_submission.py` | 16 |
| `sw/tests/test_regmap.py` | 12 |
| `sw/tests/test_multipass.py` | 9 |
| `sw/tests/test_events.py` | 7 |
| `sw/tests/test_traceability.py` | 4 |
| `sw/tests/test_e2e.py` | 3 |

An earlier revision of this document recorded 101 tests in seven files.
The suite has since gained `test_tt_submission.py` and
`test_flow_evidence.py` outright, and `test_secded.py` and
`test_regmap.py` have grown, so the earlier figure is not comparable to
the current one — it is a different suite, not the same suite with a
different count.

### 8.2 cocotb (run from `hw/tb`)

| Target | Command | Distinct tests | Executed per run |
|---|---|---|---|
| aer_fifo | `make` | 11 | 11 pass |
| npu_regbank, 512x512 | `make -f Makefile.regbank` | 33 | 33 pass |
| npu_regbank, 256x256 | `make -f Makefile.regbank small` | same 33 | 33 pass |
| lif_core, 32x32 | `make -f Makefile.lif` | 24 | 24 pass |
| lif_core, 8x4 | `make -f Makefile.lif N_NEURONS=8 N_AXONS=4` | same 24 | 24 pass |
| lif_core, 64x16 | `make -f Makefile.lif N_NEURONS=64 N_AXONS=16` | same 24 | 24 pass |
| secded, both elaborations | `make -f Makefile.secded` | 12 | 3 pass + 9 skip (encoder run), 9 pass + 3 skip (decoder run) |
| secded, encoder only | `make -f Makefile.secded enc` | — | 3 pass, 9 skip |
| secded, decoder only | `make -f Makefile.secded dec` | — | 9 pass, 3 skip |
| tmr_voter, three widths | `make -f Makefile.tmr` | 7 | **6 pass + 1 width-gated skip at each of WIDTH 1, 8 and 32** |
| tmr_voter, one width | `make -f Makefile.tmr w8` | — | 6 pass, 1 skip |
| pilot | `make -f Makefile.pilot` | 22 | 22 pass |
| pilot, other geometries | `make -f Makefile.pilot N_NEURONS=… N_AXONS=… EVQ_*_DEPTH=…` | same 22 | 22 pass at each |

**109 distinct cocotb tests** across the six suites (11 + 33 + 24 + 12 +
7 + 22). The five block suites were measured 11:08-11:10 local on
25 August 2026; the pilot row was 21 in that window and gained its
twenty-second test later the same day — the `STATUS.ERR_CFG` live-term
test of section 6.2 — and the whole pilot row was re-measured then, at
the default geometry and at 4x8, 8x16 and queue depths 2/2.

The `SKIP` counts in the secded and tmr rows are structural, not
coverage gaps: in secded they are the other elaboration's tests, and in
tmr they are the two width-gated tests described in section 6.2.

`make -f Makefile.secded clean SECDED_DUT=enc` and
`make -f Makefile.tmr clean TMR_WIDTH=8` were also exercised: each
returns 0 and removes exactly the one `sim_build_*` directory named by
its selector **[fact]**. A full pass leaves zero `<failure>` elements
across every `hw/tb/results*.xml`.

### 8.3 Formal (run from the repository root)

"Asserts" is the assert-property count the engine reported for that task
(section 7.4 check 1); "covers reached" is the count from
`formal/<task>/PASS`. A dash means the task does not evaluate that class:
`mode prove` and `mode bmc` skip the cover statements, `mode cover` skips
the assertions.

| Target | Command | Verdict | Asserts | Covers reached |
|---|---|---|---|---|
| `aer_fifo prove` | `make -C formal prove` | `PASS 0` | 21 | — |
| `aer_fifo prove_d4` | `make -C formal prove_d4` | `PASS 0` | 21 | — |
| `aer_fifo bmc` | `make -C formal bmc` | `PASS 0` | 21 | — |
| `aer_fifo cover` | `make -C formal cover` | `PASS 0` | — | **5 of 5** (see the note below) |
| `npu_regbank prove` | `make -C formal regbank_prove` | `PASS 0` | **251** | — |
| `npu_regbank prove_cnt2` | `make -C formal regbank_prove_cnt2` | `PASS 0` | 251 | — |
| `npu_regbank prove_n256` | `make -C formal regbank_prove_n256` | `PASS 0` | 251 | — |
| `npu_regbank bmc` | `make -C formal regbank_bmc` | `PASS 0` | 251 | — |
| `npu_regbank cover` | `make -C formal regbank_cover` | `PASS 0` | — | **31 of 31** |
| `lif_ctrl prove` | `make -C formal lif_prove` | `PASS 0` | **64** | — |
| `lif_ctrl prove_3x2` | `make -C formal lif_prove_3x2` | `PASS 0` | 64 | — |
| `lif_ctrl prove_8x2` | `make -C formal lif_prove_8x2` | `PASS 0` | 64 | — |
| `lif_ctrl bmc` | `make -C formal lif_bmc` | `PASS 0` | 64 | — |
| `lif_ctrl bmc_live` | `make -C formal lif_bmc_live` | `PASS 0` | **66** (64 + the two liveness watchdogs) | — |
| `lif_ctrl bmc_safe` | `make -C formal lif_bmc_safe` | `PASS 0` | 64 | — |
| `lif_ctrl cover` | `make -C formal lif_cover` | `PASS 0` | — | **15 of 15** |
| `lif_ctrl cover_safe` | `make -C formal lif_cover_safe` | `PASS 0` | — | **2 of 2** |
| `secded bmc` | `make -C formal secded_bmc` | `PASS 0` | **23** | — |
| `secded bmc_abc` | `make -C formal secded_bmc_abc` | `PASS 0` | **21** (as `PO`; C1/C2 folded, see 7.4) | — |
| `secded cover` | `make -C formal secded_cover` | `PASS 0` | — | **9 of 9** |
| `tmr_voter bmc` | `make -C formal tmr_bmc` | `PASS 0` | 15 | — |
| `tmr_voter bmc_abc` | `make -C formal tmr_bmc_abc` | `PASS 0` | 15 (as `PO`, see 7.4) | — |
| `tmr_voter bmc_w1` | `make -C formal tmr_bmc_w1` | `PASS 0` | 8 | — |
| `tmr_voter bmc_w32` | `make -C formal tmr_bmc_w32` | `PASS 0` | 39 | — |
| `tmr_voter prove` | `make -C formal tmr_prove` | `PASS 0` | 15 | — |
| `tmr_voter cover` | `make -C formal tmr_cover` | `PASS 0` | — | 7 of 7 |
| `tmr_voter cover_w1` | `make -C formal tmr_cover_w1` | `PASS 0` | — | **6 of 6** |
| `tmr_voter cover_w32` | `make -C formal tmr_cover_w32` | `PASS 0` | — | **7 of 7** |

**Twenty-eight tasks, twenty-eight `PASS`.** Two separate
`make -C formal everything` runs each emitted 28 `DONE (PASS, rc=0)`
lines, no `DONE` line of any other kind, and exit code 0 — the first in
**11 min 34 s** wall on an otherwise quiet machine, the second in
**13 min 60 s** with a second formal gate competing for CPU **[fact,
both read from the captured stdout of the run rather than from the task
directories, for the reason in section 7.1]**. The counts in the table
are from the second run.

**SUPERSEDED 2026-08-30, and the way it went stale is the point.** The
suite is now 45 tasks, and a full `make -C formal everything` emitted
**45 `DONE (PASS, rc=0)` lines, no `DONE` line of any other kind, and no
`make` error marker** **[fact]**. The table above is kept as the record
of the 28-task gate; it is not a current inventory.

That green run did **not** cover `aer_fifo`, and nothing in it said so.
`hw/rtl/aer_fifo.v` and `formal/aer_fifo.sby` were written at 19:31 and
`formal/aer_fifo_props.v` at 18:37, against a run whose `aer_fifo` tasks
executed at 16:21 — so the four tasks that reported `PASS` had seen
neither the pointer TMR nor the properties written for it, and the
sentence above claiming the table saw "the current `aer_fifo_props.v`"
was already false when it was written. A gate is only evidence about the
sources it read, and a per-task timestamp is the only thing that says
which sources those were. Re-running the block against the current tree
gives `prove`, `prove_d4`, `bmc` and `cover` all `PASS`, with all seven
cover statements reached — the last of them, `empty && f_seen_full`, at
step 130 of the 150 available **[fact]**.

One failure mode worth naming because it cost an hour here. The first
re-run ended `DONE (ERROR, rc=16)` on `cover` with
`FileNotFoundError: engine_0/trace5.vcd` from `yosys-smtbmc`, after
reaching six of the seven statements. That is the section 7.1 collision
in a form that section does not describe: it leaves a `status` file
saying `ERROR` rather than leaving none, so the "no status file" test
does not catch it. **The reliable signature is the elapsed-time pair in
the task summary** — that run reported 55 min 26 s of clock time against
**9 s** of process time, a ratio that means the solver was not computing
but waiting on a working directory being removed under it. The identical
task in isolation reported 20 min 41 s clock against 20 min 42 s
process, and passed. Compare the two numbers before reading any `ERROR`
as a property failure. All eight `tmr_voter` tasks write the full status
line `PASS 0 0`; section 7.3 explains why that trailing zero is a
runtime and not a proof depth.

Counting each property set once at its default parameters, the five
jobs carry **374 assert obligations** (21 + 251 + 64 + 23 + 15) and
**67 cover obligations** (5 + 31 + 15 + 9 + 7), and every cover is
reached. Two property sets sit outside that count because they are
different elaborations of the same file rather than additional sets:
`lif_ctrl`'s `LIF_LIVENESS` arm adds 2 asserts and its `LIF_SAFE_ENTRY`
arm replaces the 15 covers with 2.

*Note on the `aer_fifo cover` row.* This row moved during the
measurement window and the history is worth one paragraph, because it is
the only place in section 8 where two different numbers were both
correct. An earlier `make -C formal everything` ran against an
`aer_fifo_props.v` that declared **4** cover statements and reached 4 of
4. The FIFO workstream then added a fifth
(`formal/aer_fifo_props.v:167`, `!empty && rd_data != mem[rd_ptr]`),
and the re-run behind this table reports **5 of 5 reached**, at
`aer_fifo_props.v` lines 161, 162, 163, 164 and 167 **[fact, read from
`formal/aer_fifo_cover/PASS`]**. Five is the figure carried in the
totals above. The assert count of 21 is unchanged across both versions
of the file, which is the expected signature of a cover-only change and
is worth checking whenever one lands.

### 8.4 Property counts, and what they replaced

The formal counts moved substantially in this design wave. Recording
both figures makes the deltas auditable rather than mysterious:

| Job | Asserts, was | Asserts, now | Covers, was | Covers, now | Cause |
|---|---|---|---|---|---|
| `aer_fifo` | 21 | 21 | 4 | 5 | one cover added by the FIFO workstream |
| `npu_regbank` | 180 | **251** | 23 | **31** | P9 (EVQ_OUT atomicity) and P10 (exported ports) added to P1..P8 |
| `lif_ctrl` | — | **64** | — | **15** | new job, H1..H9 |
| `secded` | 21 | **23** | 7 | **9** | C1/C2 check-port assertions and their covers |
| `tmr_voter` | 15 | 15 | 7 | 7 | unchanged at WIDTH 8; the change was two new *tasks*, not new properties |
| **Total** | 237 | **374** | 41 | **67** | |

---

## 9. The full gate

Green means all four of these, in this order (the register map first, so
that a stale generated file fails before anything spends solver time on
it):

    .venv/bin/python regmap/generate.py --check
    .venv/bin/python -m pytest -q

    cd hw/tb
    make
    make -f Makefile.regbank
    make -f Makefile.lif
    make -f Makefile.secded
    make -f Makefile.tmr
    make -f Makefile.pilot
    cd -

    make -C formal everything

`everything` is the whole formal suite; `all` on its own would cover only
`aer_fifo` (section 7.1). Run the last step with no other formal gate in
flight anywhere on the machine, for the workspace reason in section 7.1
— that constraint is repository-wide, not per-shell.

Measured wall time for that sequence on the reference machine
**[fact]**, useful only as an order of magnitude elsewhere
**[estimate]**: the register-map check plus the whole Python suite is
under a second; the six cocotb suites together are on the order of a
minute, most of it elaboration and the LIF lockstep runs;
`make -C formal everything` was **11 min 34 s** end to end for the
28-task gate on a quiet machine and **14 min** with a second formal gate
competing. At 45 tasks it is longer and has not been timed end to end;
`aer_fifo cover` alone now takes **20 min 41 s** against the two and a
half minutes below, because the pointer-TMR cover statements reach much
deeper — one of them at step 130 **[fact]**. Treat the 11 min 34 s as
history, not as a target. The old formal number was dominated by two
`aer_fifo` tasks — `bmc` at over six minutes and `cover` at about two
and a half — with
`npu_regbank bmc` the next largest at about 80 s of CPU. Everything else
is small: `lif_ctrl`'s eight tasks close in about 30 s of CPU together,
and `secded` plus `tmr_voter` in about 10. Solver time moves with
whatever else is competing for CPU — the 21 % spread between those two
runs of the identical gate is the whole demonstration — so treat these
as a planning aid and not as a regression threshold.

After a run, a quick independent confirmation that nothing was skipped
by accident is

    grep -c '<failure' hw/tb/results_lif.xml hw/tb/results_lif_[0-9]*.xml \
        hw/tb/results.xml hw/tb/results_regbank*.xml \
        hw/tb/results_secded_*.xml hw/tb/results_tmr_*.xml \
        hw/tb/results_pilot_*.xml

which should print `0` for each file **[fact]**, and

    for d in formal/*/; do [ -f "$d/status" ] && echo "$(basename $d) $(cat $d/status)"; done

which should print 45 lines, every one beginning `PASS 0`. If a task
directory has no `status` file at all, that is the collision of section
7.1 and not a result — check `pgrep -af 'sby -f'` first. A `status` file
reading `ERROR` is not automatically a result either: compare the
task summary's clock time against its process time before believing it,
for the reason recorded in section 8.3.

**The file list in the first command is spelled out on purpose; do not
widen it to `hw/tb/results*.xml`.** An earlier revision of this section
did, and told the reader to expect `0` everywhere. On a machine where
the mutation runs have actually been done — the machine whose evidence
section 1.1 cites — the widened glob reports failures in **nine** files,
and every one of them is *supposed* to fail: `results_mut_m1_*.xml`
through `results_mut_m7_*.xml`, the seven `lif_ctrl` mutants;
`results_mut_m8_errcfg_live_term_dropped.xml`, the pilot mutant of
section 6.2; and `results_lif_dbg.xml`, a mutant that lets a mid-scan
debug write reach the neuron state file. A recorded dead mutant *is* a
`<failure>` element — that is the whole artifact — so a
red-means-broken check must not be pointed at one. All of these files
are gitignored (`hw/tb/results_*.xml`), so a fresh clone sees none of
them and the discrepancy reads as machine-to-machine noise rather than
as what it is **[fact — `grep -c '<failure' hw/tb/results*.xml` on this
tree]**.

Because that second check reads shared directories, capture the gate's
own output as well when anyone else might be running formal work:

    make -C formal everything 2>&1 | tee /tmp/formal-gate.log
    grep -c 'DONE (PASS' /tmp/formal-gate.log     # expect 28
    grep 'DONE (' /tmp/formal-gate.log | grep -v PASS   # expect nothing

The log belongs to your invocation and cannot be overwritten by
someone else's `sby -f`; the directories can. Where the two disagree,
the log is the evidence for what your run did (section 7.1).

A target that turns red is not a merge candidate: per docs/09, either the
RTL is fixed or the property is corrected with the reason recorded. The
formal fragments and the cocotb drivers are structured so a new block
adds files rather than editing shared ones, which is what keeps this gate
extendable without serializing on one makefile.
