# 24 — Gate-level simulation of the 6x2 submission netlist

Status: complete. The pilot bring-up suite has been run against the
placed-and-routed netlist of the submission harden. **20 of the 27 tests
run at gate level; all 20 match the RTL run to the nanosecond.** The
other 7 cannot run and section 4 says exactly why, one reference at a
time. One test diverged on the first attempt and the divergence is fully
explained in section 6: it is X-pessimism over an unreset memory the
test never writes, not a netlist defect, and it is reproducible in both
directions on demand.

This closes `docs/20` section 9 item 3 and `docs/23` section 10 item 3,
and it is the first evidence in this repository that the thing being
manufactured behaves like the thing that was verified. It does **not**
fully meet the ROADMAP P1 bar as worded; section 8 says how far short it
falls.

New files, and nothing else is touched: `hw/tb/Makefile.gl`,
`hw/tb/test_pilot_gl.py`. Both build products are already covered by
`.gitignore` (`hw/tb/results_*.xml`, `hw/tb/sim_build*/`); no ignore line
was added.

### Headline

- **The netlist behaves identically to the RTL on every test that can
  reach it.** Not merely "passes" — the per-test simulated time is
  equal, test for test, across all 20 (section 5). That is a much
  stronger statement than a green tick: the two designs take the same
  number of cycles to do the same things.
- **The one divergence was real, and it was in the testbench's
  preconditions, not in the netlist.** `lif_core`'s synapse memory has
  no reset. RTL Verilog hides that (`if (x)` silently takes the else
  branch); a gate netlist cannot. One test enables the core without ever
  writing a weight, and at gate level the unknown reaches the output
  queue's pointer bank. Writing the weights first makes the two runs
  agree to the nanosecond (section 6).
- **Two toolchain walls, and the pinned toolchain is on the wrong side
  of one of them.** Icarus 12.0 — the version every other suite in
  `hw/tb` uses — cannot simulate these cell models at all and fails
  silently. The oss-cad-suite build `tools.mk` pins can compile them but
  cannot host cocotb here. The run therefore uses a third Icarus, and
  section 3 records that as a deviation rather than hiding it.
- **Gate level costs less than expected.** 3.1x slower per simulated
  nanosecond than RTL, not the order of magnitude a 33,801-instance
  netlist suggests. The whole suite is 83 seconds. There is no
  performance reason not to run this on every harden.

---

## 1. What was run against what

### 1.1 The netlist

| | |
|---|---|
| Path | `hw/openlane/pilot_ihp/runs/shape-6x2/final/nl/tt_um_melihakbulut_nssoc.nl.v` |
| git blob | `e8f72bde4c5a02101a226f5d98bde36c1229c084` |
| Size | 2,570,202 bytes |
| Modules in it | **1** — fully flattened, `SYNTH_HIERARCHY_MODE: deferred_flatten` |
| Instances | 33,801 total; 12,418 standard cells, 21,383 fill/decap |
| Sequential cells | **1,275**, every one a `sg13g2_dfrbpq_1` |
| Unmapped instances | 0 |

**[fact, all of it: `git hash-object` and `grep -c '^module'` on the
file, `final/metrics.json` for the counts, and `make -f Makefile.gl
provenance` reproduces the first four rows.]**

`shape-6x2` is the submission harden. `docs/23` section 1.3 names this
directory as the run that moved the submission from 4x2 to 6x2, and
`docs/23` section 10 item 3 names this exact netlist as the one a
gate-level run should target.

Only 39 distinct cell types appear, and the one that matters for
simulation is `sg13g2_dfrbpq_1`: **there is no set-flop, no latch and no
macro in this netlist**, so every sequential element has a reset pin.
Whether that pin is *driven* by the design reset is a different
question, and section 6 is about the flops where it is not.

### 1.2 The RTL it was synthesized from

The run was pinned with `hw/openlane/pin_rtl.py` against commit
**`e1361fe`**, per the `docs/18` precedent and the `docs/20` section 1.2
mechanism. `docs/23` section 1.2 records the blob list; it was
re-verified here rather than copied:

```
c6f26c165faa81c97a27bce6644bc670f3b36542  hw/rtl/aer_fifo.v
b196828f65c271d849cad0ad21536c561d2079af  hw/rtl/lif_core.v
e6c1e646643840e2a553924b56dfab64022e5c39  hw/rtl/npu_regbank.v
9aaaa394e7a6ef855f5584fb85d53e688ac3e0b5  hw/rtl/npu_regs.vh
a1fdc4ce9dedb0f3635749953cb3e929a39d7703  hw/rtl/pilot_top.v
89e62789ad016c7cb51ad69247f6066335074f8c  hw/rtl/scrub.v
f7c7ec187a0df4eb09a8405dcda285de0fc2e44e  hw/rtl/secded_dec.v
b5710b8a679c3e378e74953b621b99f0d8dc3014  hw/rtl/secded_enc.v
62b5f4d2a1eae095d9d4a8634ede55237e2c924d  hw/rtl/tmr_voter.v
e294afcf03e1947906086beeba2fd0c40b29441d  hw/rtl/tt_um_melihakbulut_nssoc.v
```

Two independent checks, both **[fact]**:

1. The pinned snapshot the run consumed still exists, and
   `git hash-object` over its ten files reproduces this table exactly.
   The run's `resolved.json` names that snapshot by absolute path in
   `VERILOG_FILES`, so this is the source the flow read, not a
   reconstruction of it.
2. Every file in the **current working tree's** `hw/rtl/` has the same
   blob as `e1361fe:hw/rtl/`. The RTL side of this comparison is
   therefore the same RTL the netlist came from, and no argument is
   needed about drift.

**The tree moved under this work, for the fifth time in this project,
and again it did not matter.** A concurrent session committed `9e9c7d4`
("Close the aer_fifo proof gap, and record how a green gate hid it")
while these runs were executing. `hw/rtl` is byte-identical across it
**[fact, per-file blob comparison above, run at `9e9c7d4`]**.

### 1.3 The cell models, and how they were found

Not assumed — read out of the run itself. `Makefile.gl` resolves
`PDK_ROOT`, `PDK` and `STD_CELL_LIBRARY` from
`hw/openlane/pilot_ihp/runs/shape-6x2/resolved.json` and builds the path
from them, so the models under the simulator are the ones that hardened
this netlist and cannot silently become whichever version `~/.ciel`
currently symlinks. There are two `ihp-sg13g2` versions installed on
this machine; guessing would have been a coin flip.

| | |
|---|---|
| PDK | `ihp-sg13g2`, ciel version `c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c` |
| Models | `.../ihp-sg13g2/libs.ref/sg13g2_stdcell/verilog/sg13g2_stdcell.v` |
| git blob | `c4efa342f0d1f6a523c6a03bac258ef6e3729556` |
| Contents | 84 cell modules and 17 UDPs, self-contained; no `primitives.v` and no `-DFUNCTIONAL` as on sky130 |

**[fact]**. This is the same PDK commit `docs/15` section 5.3 records
the TTIHP26b dev container pinning, so the models are not a local
substitution.

---

## 2. The flow

```bash
cd hw/tb
make -f Makefile.gl provenance    # what would be read, with blobs
make -f Makefile.gl               # the run: 20 tests, one expected FAIL
GL_PRELOAD=1 make -f Makefile.gl  # the same run with section 6's precondition: 21/21
```

`Makefile.gl` follows the `docs/11` section 2 convention — a standalone
fragment, its own `SIM_BUILD` and results file, no edit to
`hw/tb/Makefile`. It is **not** wired into `TB=` dispatch, deliberately:
`hw/tb/Makefile`'s `TB_FRAGMENTS` list is not a file this document owns,
and a gate-level run is not interchangeable with an RTL one.

### 2.1 The trap the sibling project's flow has, and this one does not

`radhard-edge-ai/hw/tb/Makefile` resolves its netlist with

```make
GL_RUN ?= $(shell ls -td $(PWD)/../openlane/mvp_top/runs/*/ | head -1)
```

In that project's run directory it happens to be right. Here it would be
wrong: `hw/openlane/pilot_ihp/runs/` holds eleven directories, including
synthesis-only probes (`ihp-synth-flatten`), DRC-only reruns
(`ihp-klayoutdrc`), memory-ECC synthesis checks, and **two full sign-offs
at different tile shapes** (`shape-3x4` and `shape-6x2`). The newest is
not the submission. A gate-level PASS against a netlist nobody is taping
out is worse than no gate-level result at all, because it reads like
one.

`GL_RUN` here is a named directory with no wildcard in it, and
`provenance` prints the netlist's git blob so a quoted result names the
bytes it came from. `GL_TAG=shape-3x4 make -f Makefile.gl` points it
somewhere else explicitly; nothing in the file assumes 6x2.

### 2.2 `-gspecify` is required, not an optimisation

`sg13g2_dfrbpq_1` drives its flip-flop UDP from `delayed_CLK` and
`delayed_D`, which exist only as the delayed-signal outputs of the
`$setuphold` calls inside its `specify` block. With Icarus's default
`-gno-specify` those nets have no driver at all. Section 3 is about what
that costs.

All module path delays in these models are literal `0`, and there are no
`UNIT_DELAY` or `FUNCTIONAL` hooks of the kind the sky130 models expose.
So **this is a zero-delay functional gate-level run**: it checks the
netlist's logic and its flip-flop mapping, not its timing. That is the
right division of labour — the same run directory contains post-route
STA on three corners, all clean, `docs/23` section 3 — and Icarus does
not implement the timing checks that would make an SDF-annotated run say
anything STA has not already said. SDF files for all three corners are
present at `final/sdf/` if that changes.

---

## 3. The toolchain, and a deviation recorded rather than hidden

`make -f tools.mk toolcheck` was run and passes: the pinned
oss-cad-suite checkout is present and its yosys is `0.67+146`, matching
the pin. **The gate-level run does not use its Icarus, and cannot.**
Two independent walls:

### 3.1 Icarus 12.0 cannot simulate this netlist, and fails silently

12.0 is what `iverilog` on PATH resolves to on this machine, and
therefore what every other suite in `hw/tb` uses. On these models:

```
12.0: warning: Timing checks are not supported and delayed signal
      "delayed_CLK" will not be driven.
13.0: warning: Timing checks are not supported. Delayed reference and
      data signals become copies of the original reference and data
      signals.
```

Under 12.0 every flip-flop in the design is clocked by an undriven net,
nothing ever updates, and the netlist sits at its reset value for the
whole run. **The first attempt at this work reported 21 of 21 tests
failing with every register reading back `0x00000000`** — which reads
exactly like a dead design and is not one. Nothing in the cocotb log
says otherwise; the evidence is in the compile warnings, thousands of
lines earlier.

**This is not a new discovery.** `docs/15` section 5.4 records the same
trap, from the template's own `make GATES=yes` path, on the superseded
`tt-harden` netlist, and notes that Tiny Tapeout's `gl_test` action
installs `TinyTapeout/iverilog` v13.0 rather than a distribution build,
so CI is fine and a laptop is not. What is new here is that the trap has
now been hit a second time by a different flow, which is the argument
for the guard: `Makefile.gl` reads the major version and **errors out**
below 13 with the reason, so this can never again present as a design
failure.

### 3.2 The pinned oss-cad-suite Icarus cannot host cocotb here

`OSS_CAD_SUITE/bin/iverilog` is 14.0-devel and compiles the netlist
correctly — it emits the 13.0-style warning and the flops work. But its
`bin/vvp` is a wrapper that exports `PYTHONHOME` into the oss-cad-suite
tree and re-execs through the suite's own `ld-linux` with
`--inhibit-rpath`. cocotb's embedded interpreter then resolves against
the suite's Python 3.11 instead of the project venv's 3.12:

```
Failed to initialize Python
        error: failed to get the Python codec of the filesystem encoding
ModuleNotFoundError: No module named 'pygpi'
```

Bypassing the wrapper — `libexec/vvp` with `LD_LIBRARY_PATH` pointed at
the suite's `lib/` — segfaults instead, because the suite ships its own
`libc.so.6` **[fact, exit 139]**. This is a packaging conflict between
oss-cad-suite and a venv-installed cocotb; it is not something this
repository can fix, and no amount of `SIM_CMD_PREFIX` gets around it.

### 3.3 What was actually used, and why the comparison is still fair

| Tool | Path | Version |
|---|---|---|
| Icarus (gate level **and** the RTL side of section 5) | `~/.local/opt/iverilog13/usr/bin/iverilog` | 13.0 stable |
| cocotb | `hw/.venv` | 2.0.1 |
| Icarus on PATH, used by every other `hw/tb` suite | `~/.local/bin/iverilog` | 12.0 stable |
| yosys, sby (governed by `tools.mk`, not used here) | pinned oss-cad-suite | 0.67+146 |

Forcing the gate-level side onto 13.0 would put two variables into a
one-variable comparison, so **the RTL side was re-run on 13.0 too**, and
on 12.0 as a control:

| RTL run | Result | Simulated | Wall |
|---|---|---|---|
| `make -f Makefile.pilot`, Icarus 12.0 | **27/27 PASS** | 2,135,040 ns | 40 s |
| `make -f Makefile.pilot`, Icarus 13.0 | **27/27 PASS** | 2,135,040 ns | 40 s |

and the two are identical test for test — same status and the **same
simulated time to the hundredth of a nanosecond on all 27** **[fact,
parsed from both logs]**. The simulator is therefore not a variable in
section 5, and the RTL baseline is confirmed green after this work as
well as before it.

---

## 4. Which tests ran, which could not, and why

27 tests exist in `hw/tb/test_pilot_top.py`. **20 run at gate level. 7
cannot.**

### 4.1 The partition is derived, not hand-written

A hand-maintained skip list is precisely the failure this whole exercise
exists to catch: it goes stale silently, and a gate-level suite that
quietly stops covering half the design is worth less than none, because
it reads as evidence.

`hw/tb/test_pilot_gl.py` therefore computes the split by parsing
`test_pilot_top.py` with `ast` and asking, for every test **and
transitively for every module-level helper it calls**, whether any
`dut.<attr>` access names something that is not a port of the Tiny
Tapeout wrapper. A test that grows a hierarchical reference tomorrow
leaves the gate-level set tomorrow, and the count printed at the top of
every run changes with it. Following calls is not decoration:
`_fill_output_queue` polls `dut.u_pilot.fo_full`, and three tests reach
the hierarchy only through it.

The module contains no tests of its own; it re-exports the `Test`
objects it keeps. `test_pilot_top.py` is neither modified nor
monkey-patched, and the same code runs on both sides.

### 4.2 The seven, with the reference that excluded each

Printed by every run, reproduced verbatim:

| Test | Reaches |
|---|---|
| `test_dispatcher_stranded_in_fetch_recovers_and_is_flagged` | `dut.u_pilot.dstate` |
| `test_evq_out_ovf_counter_saturates_and_clears` | `dut.u_pilot.cnt_evqo`, `.evqo_drop`, `.fclr_evqo`, `.sync_push`; and `.fo_full` through `_fill_output_queue` |
| `test_fsm_upset_reaches_status_and_the_err_pin` | `dut.u_pilot.u_lif.state` |
| `test_lost_sync_echo_is_counted_and_flagged` | `dut.u_pilot.cnt_evqo`, `.fo_full`, `.sticky_ovf`, `.sync_push`, `.sync_word` |
| `test_output_backpressure_is_not_an_overflow` | `dut.u_pilot.fo_full`, `dut.u_pilot.u_evq_out.drop_cnt` |
| `test_parked_core_holds_err_cfg_on_the_live_term` | `dut.u_pilot.sticky_errcfg`, `dut.u_pilot.u_lif.state` |
| `test_show_ahead_stranded_request_recovers_and_is_flagged` | `dut.u_pilot.oh_req` |

`test_pilot_top.py`'s own header says three tests reach into the
hierarchy. Seven do. The header is counting the three tests that
*deliberately inject an upset*; the other four reach in to observe or to
set up, which is just as fatal to a flattened netlist. That is not a
correction to the header's claim — it is the header counting a different
thing — but it is worth knowing that the port-driven fraction of the
suite is 74 %, not 89 %.

### 4.3 Why "flattened" is not the whole reason, and what the real one is

The obvious explanation is that `deferred_flatten` leaves one module, so
there is no `u_pilot` to descend into. That is true and it is not the
whole story, because **the names survive**: yosys keeps them as single
identifiers containing dots, and the netlist contains
`\u_pilot.u_lif.state`, `\u_pilot.fo_full`, `\u_pilot.u_evq_out.u_wptr_a.q`
and about two hundred more. Iterating the top-level scope from cocotb
finds 46,155 children, including `u_pilot.u_lif.state[0..3]` **[fact]**.

Two things stop that from being a way back in.

**First, cocotb cannot look them up by name.** `vpi_handle_by_name`
splits on `.`, so `dut["u_pilot.fo_empty"]` asks the simulator for a
child `u_pilot` and fails. Only a full iteration of the scope, keyed on
`_name`, reaches them — which is what the debug scripts in section 6
had to do. So the RTL tests could not be pointed at the netlist even in
principle without rewriting how they address signals.

**Second, and decisively: a deposit into a netlist net is a stuck-at
fault, not an upset.** Depositing `state = 4'b0001` onto
`u_pilot.u_lif.state[3:0]` at gate level and then clocking once gives:

```
state before deposit           = 0000
state immediately after deposit = 0001
state one clock later          = 1001
```

**[fact, measured]**. Bit 0 is still 1 a cycle later — not because the
flop holds it, but because the net is driven by a cell output that has
not changed, so the deposited value is never overwritten. The FSM
meanwhile reacted to the corruption and set bit 3. That is a *permanent*
fault held on a wire, which is a different experiment from the
single-cycle flip of a storage bit that `docs/16` specifies. It is the
same class of error `docs/16` records the fault injector already making
once — depositing on a driven net instead of on state — and it would be
a regression to make it again here in order to raise the test count.

**So six of the seven are not adaptable at all** (they deposit or force),
and the seventh, `test_output_backpressure_is_not_an_overflow`, only
observes and could in principle be adapted with a name-indexed handle
lookup. It was not, and the honest reason is scope: it would be one test
written twice, and the observation it makes (`fo_full` and a drop
counter) is the one thing this run has independent evidence for anyway,
since the show-ahead and overflow behaviour it guards is exercised
port-side by `test_evq_out_is_show_ahead`, which does run and does
match.

**What this costs, stated plainly:** the fault-injection half of the
verification story — SEU in the LIF FSM, the stranded dispatcher, the
stranded show-ahead request, the destroyed SYNC echo, the saturating
overflow counter — has **no gate-level evidence at all**. Section 8
carries that.

---

## 5. The result

### 5.1 Headline numbers

| Run | Tests | Result | Wall | Simulated |
|---|---|---|---|---|
| `make -f Makefile.gl` | 20 | **19 PASS, 1 FAIL** | 177 s | 2,761,090 ns |
| `GL_PRELOAD=1 make -f Makefile.gl` | 21 | **21 PASS, 0 FAIL** | 83 s | 1,426,700 ns |
| `make -f Makefile.pilot` (RTL, Icarus 13.0) | 27 | **27 PASS, 0 FAIL** | 40 s | 2,135,040 ns |
| `make -f Makefile.pilot` (RTL, Icarus 12.0) | 27 | **27 PASS, 0 FAIL** | 40 s | 2,135,040 ns |

Wall times are from four sequential runs on an otherwise idle machine
and are the only load-dependent numbers in this document; earlier
measurements taken while two suites ran concurrently were up to 2.8x
higher. **The simulated times are not load-dependent and do not vary at
all** — every figure in this document reproduced exactly across every
repetition.

The default run is the honest one and it is red by one test; section 6
is that test. `GL_PRELOAD=1` adds a preamble that writes the weight
memory and turns it green, at the cost of one extra test in the count
and of a run that no longer reproduces the finding. The default is
deliberately the red one.

The 177 s / 83 s difference is almost entirely the failing test burning
1,380,510 ns of simulated time in a bounded loop that never terminates.

### 5.2 With the precondition supplied, nothing diverges

Every one of the 20 gate-level tests takes **exactly the same simulated
time as the RTL run of the same test**. Not approximately: equal to the
hundredth of a nanosecond, which for a suite driven entirely through a
bit-banged serial port means the netlist and the RTL take the same
number of clock cycles to do the same things, including every
back-pressure stall, every SECDED syndrome walk and every inference.

| Test | RTL (ns) | GL (ns) | Equal |
|---|---|---|---|
| `test_gl_preload_weight_memory` | — | 18,810 | preamble |
| `test_reset_values` | 49,410 | 49,410 | yes |
| `test_reset_pins_and_directions` | 110 | 110 | yes |
| `test_reset_released_asynchronously` | 8,700 | 8,700 | yes |
| `test_register_access` | 34,110 | 34,110 | yes |
| `test_chip_select_setup` | 19,150 | 19,150 | yes |
| `test_input_queue_overflow` | 32,410 | 32,410 | yes |
| `test_soft_reset_flushes_queues_keeps_config` | 15,410 | 15,410 | yes |
| `test_state_clear_and_state_port` | 49,410 | 49,410 | yes |
| `test_sync_barrier` | 18,810 | 18,810 | yes |
| `test_axon_out_of_range_is_dropped_and_counted` | 27,310 | 27,310 | yes |
| `test_config_lock_while_busy` | 102,110 | 102,110 | yes |
| `test_parallel_aer_pins` | 32,780 | 32,780 | yes |
| `test_evq_out_is_show_ahead` | 46,400 | 46,400 | yes |
| `test_inference_matches_golden` | 137,810 | 137,810 | yes |
| `test_inference_with_tile_offset` | 100,410 | 100,410 | yes |
| `test_secded_single_bit_correction` | 146,610 | 146,610 | yes |
| `test_secded_syndrome_walk` | 192,210 | 192,210 | yes |
| `test_secded_double_bit_detection_and_e10` | 125,910 | 125,910 | yes |
| `test_tmr_masks_a_corrupted_config_replica` | 236,410 | 236,410 | yes |
| `test_fault_clr_bit_assignment` | 32,410 | 32,410 | yes |

**[fact, `run4.log` against `rtl_iv13.log`, compared programmatically
rather than by eye.]**

Three of these are worth naming for what they now mean:

- **`test_tmr_masks_a_corrupted_config_replica` passes at gate level.**
  This is the direct answer to the failure `docs/16` section 4
  records — yosys `opt_dff` and `opt_merge` collapsing the three
  configuration replicas into one physical bank — asked of the netlist itself
  rather than of a cell count. The three replicas are still three in the
  hardened netlist, and corrupting one is still masked.
- **`test_inference_matches_golden` passes at gate level.** The
  spike-for-spike, neuron-state-for-neuron-state comparison against
  `sw/golden` now holds for 33,801 placed cells, not only for the RTL.
- **`test_secded_syndrome_walk` passes at gate level.** The whole
  syndrome space of the SECDED codec survives synthesis, which is the
  kind of wide combinational structure a mapper is most likely to get
  subtly wrong.

### 5.3 What gate level costs

RTL: 53,999 simulated ns per wall second. Gate level: 17,245. **A factor
of 3.13** **[fact, two sequential runs on an idle machine, from the
suite footers]**. For a netlist with
33,801 instances and a 124-buffer clock tree, that is cheap — cheap
enough that there is no performance argument for not re-running this on
every harden. Elaboration is 2.0 s and the `sim.vvp` is 29,277,176 bytes **[fact,
measured]**.

---

## 6. The one divergence, and what it turned out to be

### 6.1 The symptom

`test_axon_out_of_range_is_dropped_and_counted` failed at gate level
with `output queue never drained`, after 1,380,510 ns. At RTL it
completes in 27,310 ns. The failure is at the *second* drain: the
over-range drop and its counter both behave correctly first.

Reading the register map from the port side:

| | RTL | gate level |
|---|---|---|
| `STATUS` after the in-range spike | `0x00000006` (`IN_EMPTY`, `OUT_EMPTY`) | `0x00000002` (`IN_EMPTY` only) |
| `EVQ_STAT` | `0x00000000` | `0x00000000` |
| `EVQ_OUT` reads | not reached | `0x00000000`, forever |

So the netlist reports an output queue that is *not empty* while the
same register block reports a fill level of *zero* — a self-contradiction
that immediately says the state is not simply different, it is unknown.

### 6.2 Localising it

`pilot_top.v` line 1842 gives `evq_out_empty = fo_empty && !oh_valid`,
and `out_fill = fo_level + oh_valid`. A run that shows `out_fill == 0`
and `evq_out_empty == 0` needs `fo_empty` to be neither 0 nor 1.

Probing the surviving netlist names — by full scope iteration, since
by-name lookup does not work (section 4.3) — confirms it:

```
after-over-range: fo_empty=1 fo_full=0 fo_ptr_mm=0 evq_ptr_mm=0 oh_req=0 ...
iter0:            fo_empty=X fo_full=X fo_ptr_mm=X evq_ptr_mm=X oh_req=X fo_rd_en=X fo_rd_valid=X
```

and the same probe against the RTL shows every one of those signals
staying at a defined value throughout **[fact, both logs]**. A scan of
all 12,354 readable named nets shows 2,564 already X *before* the spike
— all inside `u_evq_in`'s unreset data memory, which is expected and
harmless — and 2,157 further named nets going X *after* it.

### 6.3 The cause

`lif_core`'s synapse memory is `reg [3:0] wmem [0:N_SYN-1]`, 256 entries,
**with no reset** — resetting it would cost 256 flops' worth of reset
routing for no functional gain, and `lif_core.v` is explicit that the
scan never writes it. Before the first weight write it holds x in *any*
simulation, RTL or gate.

`test_axon_out_of_range_is_dropped_and_counted` is the only port-driven
test that **enables the core without writing a single weight first**,
and in suite order it is test 10 of 20 — the first test that loads
weights is `test_inference_matches_golden` at 14.

What happens next is the textbook difference between the two levels:

- **RTL is X-optimistic.** `if (x) a; else b;` takes the else branch, so
  an unknown never reaches a register through a conditional. The unknown
  weights are silently swallowed and the queue behaves.
- **The netlist is X-pessimistic.** There is no `if`; there is a mux and
  comparator tree, and it propagates the x into `fo_wr_en`, thence into
  the EVQ_OUT pointer bank, and `fo_empty` goes x. `STATUS.OUT_EMPTY`
  then reads 0 and `drain()`'s 400-iteration bound runs out.

### 6.4 Proving it, in both directions

Two variants of the same test were run on both designs, identical except
that one writes an all-zero weight array before enabling the core:

| Variant | RTL | gate level |
|---|---|---|
| weights written first | PASS, 39,210 ns | **PASS, 39,210 ns** |
| weights not written | PASS, 23,910 ns | **FAIL**, 1,380,510 ns |

**[fact, four runs.]** The first row is the confirmation: with the
precondition supplied, the twentieth test matches the RTL to the
nanosecond like the other nineteen. The second row is the divergence,
isolated and reproducible on demand.

The four diagnostic modules used in sections 6.1 to 6.4 — the
step-by-step `STATUS` log, the internal-net probe, the whole-design X
scan and the two-variant experiment — were throwaway cocotb modules and
are **not** kept in the repository. Reproducing them needs no new
machinery: each is a `@cocotb.test()` that imports the helpers from
`test_pilot_top` and is pointed at either design with
`COCOTB_TEST_MODULES=<module> make -f Makefile.gl` or
`... make -f Makefile.pilot`, which is why both fragments leave
`COCOTB_TEST_MODULES` overridable. The two-variant experiment is the
body of `test_axon_out_of_range_is_dropped_and_counted` with one
`load_weights(p, [[0] * n_neurons for _ in range(n_axons)], n_neurons)`
inserted after `state_clr`, run twice; the net probe needs the
scope-iteration index of section 4.3.

A detail worth recording because it nearly hid the result: run the two
variants *in that order in one simulation* and both pass, because the
weight memory is not reset between cocotb tests and the first variant
has already defined it. The failure only appears when the unwritten case
runs first — which is exactly its position in the real suite.

### 6.5 What this is, and what it is not

**It is not a netlist defect.** The netlist does the only thing a
netlist can do with an unknown input.

**It is not an RTL defect either**, but it is an RTL *blind spot*: the
RTL suite has been passing this test on X-optimism, and would have gone
on doing so indefinitely. In silicon the flops power up to definite
values, so the design behaves definitely — but with arbitrary weights,
which is not what the test believes it is testing. The test asserts only
`CNT_AXON_OOR`, so nothing it claims is wrong; it is just resting on
less than it looks like.

**It is exactly the class of thing gate-level simulation exists to
find**, and it is the fourth time in this project that the difference
between the RTL and what is downstream of it has produced a surprise —
after the merged configuration TMR (`docs/16` section 4: 362 netlist
references to `cfg_a[`, zero to `cfg_b[` and `cfg_c[`), the fault
injector depositing on a driven net rather than on storage (`docs/16`
section 3.3), and the pointer TMR that could not be believed until
flip-flop cells were counted in a hardened netlist (`docs/22`).

**No fix is proposed here** and none is applied to `test_pilot_top.py`.
Adding a weight write to that test would be a one-line change owned by
whoever owns the RTL suite, and it would remove the only current
gate-level demonstration that the two levels can be told apart. The
`GL_PRELOAD=1` preamble supplies the precondition for the gate-level
suite only, and says so in its docstring.

---

## 7. Reproducing this

```bash
make -f tools.mk toolcheck        # yosys 0.67+146; does NOT govern section 3

cd hw/tb

# what would be read, with blobs
make -f Makefile.gl provenance

# the run as reported: 20 tests, 19 PASS, 1 FAIL (section 6)
make -f Makefile.gl

# the same with the section 6 precondition: 21 tests, 21 PASS
GL_PRELOAD=1 make -f Makefile.gl

# the RTL side of section 5, on the same simulator
PATH=$HOME/.local/opt/iverilog13/usr/bin:$PATH make -f Makefile.pilot

# the RTL baseline as the repository normally runs it
make -f Makefile.pilot

# another harden, if there is one
GL_TAG=shape-3x4 make -f Makefile.gl
```

The RTL-blob verification of section 1.2:

```bash
git ls-tree --name-only HEAD hw/rtl/ | while read f; do
  [ "$(git hash-object "$f")" = "$(git rev-parse "e1361fe:$f")" ] || echo "DIFFERS: $f"
done
```

Build products land in `hw/tb/sim_build_gl_<tag>/` and
`hw/tb/results_gl_<tag>.xml`, both already matched by existing
`.gitignore` lines.

---

## 8. What this proves, and what it does not

### 8.1 Proved

1. **The submission netlist implements the RTL's function.** 20 of 27
   tests, driven entirely through the Tiny Tapeout port list, pass against
   the placed-and-routed netlist and consume the same number of cycles
   as the RTL doing the same work. Register map, serial protocol at its
   minimum chip-select setup, the parallel AER pins, the event path with
   its show-ahead contract and its overflow drop, two end-to-end
   inferences checked against `sw/golden`, the full SECDED syndrome
   walk, double-bit detection with the E10 substitution, and
   configuration TMR masking — all of it survives synthesis, placement,
   CTS and routing.
2. **The configuration TMR is still three replicas after hardening.**
   Asked of the netlist directly rather than inferred from cell counts.
3. **The netlist is clean of X at reset except where the RTL is.** After
   reset, every named net outside `u_evq_in`'s unreset data memory holds
   a defined value.
4. **The RTL suite is green on two Icarus versions**, 27/27 on both, with
   identical per-test simulated time — so the section 5 comparison has
   one variable in it.

### 8.2 Not proved

1. **No timing.** Zero-delay run; the cell models carry no delays and no
   SDF was annotated. Timing is signed off by post-route STA on three
   corners in the same run directory (`docs/23` section 3), and the two
   results are complementary, not overlapping. In particular a
   hold-time failure would be invisible here.
2. **No fault injection at gate level, at all.** Every SEU test is
   RTL-only (section 4.2). The pointer TMR, the LIF FSM upset recovery,
   the bounded dispatcher wait, the stranded show-ahead request and the
   EVQ_OUT overflow accounting have **no gate-level evidence**. `docs/22`
   section 9's flip-flop count remains the only netlist-level evidence
   for the pointer TMR.
3. **This is not the netlist the ROADMAP bar names.** P1 asks for "GL
   smoke on the **TT-generated** netlist". This is a local LibreLane
   3.0.5 `Classic` harden; the TTIHP26b GDS action runs
   `librelane==3.0.0.dev44` in its own container. The PDK commit is the
   same and `docs/15` section 5.3 argues a local close is strong
   evidence about shape and configuration — but the bar as worded is met
   by the `gl_test` action, and this run does not substitute for it. It
   does something the action does not: the action runs the five tests in
   `tt/test/`, this runs twenty.
4. **`tt/runs/` still has no 6x2 harden**, so
   `sw/tests/test_synthesis_guards.py` continues to scan the
   `wave5-ihp-b` 4x2 netlist (`docs/23` section 10 item 4). Nothing here
   changes that.
5. **One adaptable test was not adapted.**
   `test_output_backpressure_is_not_an_overflow` observes without
   depositing and could run at gate level with a name-indexed handle
   lookup. Section 4.3 gives the reasoning for leaving it; it is a
   choice, not an impossibility.
6. **The suite is not in CI.** `docs/19`'s parity gate does not know
   about `Makefile.gl`, and adding it would need a decision about which
   Icarus CI installs — the guard in section 3.1 would fail the job on a
   distribution 12.0, which is the correct behaviour and also a new
   dependency.

### 8.3 Open items this leaves

1. **Fix or annotate `test_axon_out_of_range_is_dropped_and_counted`.**
   It should write the weight memory before enabling the core. Owned by
   the RTL suite; see section 6.5 for why it is not done here.
2. **Decide whether `GL_PRELOAD` should default on.** It should not
   while section 6 is the newest finding in this document; it probably
   should once the test above is fixed, at which point the preamble
   becomes dead weight and can be deleted.
3. **Re-run against the GDS action's netlist** when the action next
   runs, and record whether the twenty tests still agree. That, not
   this, is what closes the ROADMAP P1 bar.
4. **Gate-level fault injection**, if it is wanted, needs a mechanism
   that reaches flip-flop state rather than netlist nets — section 4.3
   measures why a deposit is a stuck-at here. That is a real piece of
   work and it is not scheduled.
