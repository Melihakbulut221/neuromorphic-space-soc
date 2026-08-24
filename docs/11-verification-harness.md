# 11 — Verification Harness

Date: 24 August 2026
Status: harness live; all gates green at the commit that introduces this
document.
Scope: the single-source register map flow, the first RTL module
(`hw/rtl/aer_fifo.v`) with its cocotb regression, and the SymbiYosys
formal proof. Conventions carried over from the developer's prior 130 nm
accelerator practice: one YAML source of truth for the register map,
cocotb + Icarus suites driven by a `TB=` Makefile, pytest as the sync
enforcer, and everything runnable rootless.

## 1. Layout

| Path | Role |
|---|---|
| `regmap/regmap.yaml` | register map single source (normative list: `docs/10-npu-mvp-spec.md` section 10) |
| `regmap/generate.py` | emits `docs/regmap-npu.md`, `sw/golden/regmap_gen.py`, `hw/rtl/npu_regs.vh`; `--check` verifies sync |
| `sw/tests/test_regmap.py` | sync test: generated files fresh, YAML equal to the docs/10 section 10 table |
| `hw/rtl/aer_fifo.v` | AER event FIFO (docs/10 section 7 EVQ semantics), Verilog-2001 |
| `hw/tb/Makefile`, `hw/tb/test_aer_fifo.py` | cocotb + Icarus suite, `TB=aer_fifo` default |
| `formal/aer_fifo.sby`, `formal/aer_fifo_props.v` | SymbiYosys jobs and properties (included into the module under `ifdef FORMAL`) |
| `formal/Makefile` | `make prove prove_d4 bmc cover` with rootless sby discovery |

## 2. Prerequisites (rootless)

- Icarus Verilog and Yosys on PATH (here: `~/.local/bin`, Icarus 12.0).
- Python venv for cocotb/pytest, deliberately separate from the
  golden-model `.venv/` used by the docs/10 work:

      python3 -m venv hw/.venv
      hw/.venv/bin/pip install cocotb pytest pyyaml

- SymbiYosys: `formal/Makefile` takes `sby` from PATH, else falls back to
  the known oss-cad-suite checkouts
  (`~/oss-cad-suite/bin`, `~/Documents/gt2n-soc/tools/oss-cad-suite/bin`,
  `~/Downloads/oss-cad-suite-linux-x64-20260804/oss-cad-suite/bin`).
  sby brings its own yosys and SMT solvers; nothing needs root.

## 3. Register map flow

    hw/.venv/bin/python regmap/generate.py            # regenerate outputs
    hw/.venv/bin/python regmap/generate.py --check    # fails if stale
    hw/.venv/bin/python -m pytest sw/tests/test_regmap.py -q

Edit only `regmap/regmap.yaml`; the generated files carry a GENERATED
header and are enforced by the `--check` sync test. The pytest suite
(7 tests) additionally cross-checks the YAML against the docs/10
section 10 table mechanically (name, offset, access, literal resets), so
the spec and the map cannot drift apart silently. A full
`pytest sw/tests` run also executes the golden-model suites owned by
docs/10 section 13.

## 4. RTL simulation (cocotb + Icarus)

    cd hw/tb && make            # TB=aer_fifo, SIM=icarus defaults

The Makefile finds cocotb in `hw/.venv` by itself (it re-invokes make
with the venv on PATH when needed); `make TB=<block>` selects future
suites, radhard-edge-ai style. `EXTRA_COMPILE_ARGS` passes through, e.g.
for coverage builds.

`test_aer_fifo.py`: 11 tests, all passing — reset state, fill/drain
order, registered-output timing, simultaneous read/write at constant
occupancy, overflow-drop counting against a full FIFO, drop on
coincident read+write at full, drop-counter clear (including the
coincident-drop restart-at-1 convention), drop-counter saturation
(no wrap), read-on-empty refusal, a 2000-cycle randomized scoreboard
against a Python model of the whole contract, and reset mid-traffic
with recovery.

## 5. Formal proof (SymbiYosys)

    cd formal && make           # prove prove_d4 bmc cover
    make prove                  # the induction gate alone

Tasks in `aer_fifo.sby` (engine smtbmc/yices):

| Task | Mode | Result |
|---|---|---|
| `prove` | k-induction, depth 15, default parameters (WIDTH=16, DEPTH=64) | PASS — successful proof by k-induction |
| `prove_d4` | same properties at DEPTH=4, WIDTH=8 via `chparam` | PASS |
| `bmc` | bounded check, depth 40 | PASS |
| `cover` | reachability, depth 150 | PASS — all 4 covers reached |

Proven properties (P1..P5 in `formal/aer_fifo_props.v`):

1. **Level bookkeeping** — `level` equals accepted writes minus accepted
   reads, never exceeds DEPTH; pointers advance by exactly 0 or 1.
2. **No spurious empty/full** — flags are exact functions of the level
   and follow single-operation transitions.
3. **Never overflow-corrupts** — a write while full changes neither
   pointer, level, nor stored data; a read while empty changes nothing.
4. **Drop bookkeeping** — the sticky counter increments exactly on
   dropped writes, saturates instead of wrapping, clears by `drop_clr`
   with the coincident-drop restart-at-1 convention.
5. **FIFO order preservation** — two-token method: two solver-chosen
   consecutive writes are stored uncorrupted and re-emerge in order and
   unmodified on the registered output; `rd_valid` is exact.

Reset is unconstrained after the initial state, so the proof includes
reset-mid-traffic. The properties see module internals because the file
is included at the end of the `aer_fifo` module body under
`ifdef FORMAL`; simulation and synthesis never see it.

## 6. Gate summary

Green means all three of:

    hw/.venv/bin/python -m pytest sw/tests/test_regmap.py -q   # 7 passed
    cd hw/tb && make                                           # 11/11 PASS
    cd formal && make                                          # 4/4 DONE (PASS)
