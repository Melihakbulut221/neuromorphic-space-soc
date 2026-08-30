#!/usr/bin/env python3
"""Generate the Tiny Tapeout submission tree (tt/) from this repository.

This repository is the single source of truth. Everything under tt/ is
derived: the RTL is copied byte for byte out of hw/rtl, the register
addresses in the datasheet come from sw/golden/regmap_gen.py (itself
generated from regmap/regmap.yaml), and the scaffolding is a recorded
port of the upstream Tiny Tapeout template. Nothing under tt/ is meant
to be hand-edited; a SHA-256 manifest is written so that drift in either
direction is detectable, and sw/tests/test_tt_submission.py fails the
build when it happens.

Usage:
    python3 scripts/gen_tt_submission.py            # write tt/
    python3 scripts/gen_tt_submission.py --check    # fail on drift, write nothing
    python3 scripts/gen_tt_submission.py --diff-template
                                                    # network: prove that the
                                                    # files this script claims
                                                    # are verbatim really are

Upstream provenance (recorded, not fetched at generation time so that the
generator is reproducible offline):

    https://github.com/TinyTapeout/ttihp-verilog-template
    commit 6598bef4d3159f19fe471a2a2225df52e6f5ad25 ("chore: update tags
    for TTIHP26b"), 2026-07-27.

    Tile geometry and the info.yaml schema were read from
    https://github.com/TinyTapeout/tt-support-tools
    commit 01d5d2814fa9dd61e9d211e0b235a4a592a9316a, 2026-08-20, which is
    the branch (main) that the TTIHP26b GDS action installs.

Re-porting procedure when Tiny Tapeout moves the template: run
--diff-template, update the VERBATIM literals and TEMPLATE_COMMIT below
from the reported diff, re-run without arguments, re-run the pytest.
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tt"

TEMPLATE_URL = "https://github.com/TinyTapeout/ttihp-verilog-template"
TEMPLATE_REF = "main"
TEMPLATE_COMMIT = "6598bef4d3159f19fe471a2a2225df52e6f5ad25"
SUPPORT_TOOLS_COMMIT = "01d5d2814fa9dd61e9d211e0b235a4a592a9316a"

# ---------------------------------------------------------------------
# Submission identity
# ---------------------------------------------------------------------
# The shuttle assembles every project into one die, and tt-support-tools
# configure.py asserts that macro instance names are unique across the
# shuttle, so the top level has to be namespaced tt_um_<user>_<project>.
# The repository's own wrapper carries that name (hw/rtl/TOP_MODULE.v),
# so the submission is a straight copy: there is no generated name
# adapter and no extra hierarchy level between the pin list and the
# design. Renaming here means renaming hw/rtl/<top>.v, hw/tb/Makefile.pilot
# and this constant together; sw/tests/test_tt_submission.py fails if the
# three disagree.
TOP_MODULE = "tt_um_melihakbulut_nssoc"

AUTHOR = "Hasan Melih Akbulut"
TITLE = "NSSOC-P1 fault-tolerant spiking neuron pilot"
DESCRIPTION = (
    "8x8 leaky integrate-and-fire neuron tile with a TMR-voted "
    "configuration domain, a SECDED-protected weight path, AER event "
    "queues and on-chip fault counters"
)
CLOCK_HZ = 50_000_000

# Tile shape. First set to 4x2 by docs/15-pilot-tile-plan.md section 4;
# moved to 6x2 by docs/23-tile-shape-decision.md.
#
# 4x2 is no longer viable on the planning criterion. docs/22 section 9
# measures the current design at 185,755 um2 placed into a 259,837 um2
# 4x2 core -- 71.489 % utilization against a 70 % criterion, i.e. 2.13 %
# of the core short. It still routed DRC-clean, so that is a planning
# failure rather than a flow failure, but it leaves no headroom at all.
#
# Twelve tiles come in two shapes at the same price, and docs/23 hardens
# both rather than scaling the 4x2 numbers. 6x2 wins: 47.29 %
# utilization, zero setup, hold, max-slew and max-cap violations on all
# three corners, detailed routing converged in a single pass of five
# iterations, zero antenna diodes required. 3x4 buys 5.4 points more
# utilization headroom that the design does not need, and pays for it
# with one 6.27 ps hold violation at the fast corner, a second
# detailed-route pass, and a purchasability on TTIHP26b that could not be
# confirmed -- tile_sizes.yaml and the shuttle's own pinned DEF set carry
# 3x4, but the ttihp-verilog-template info.yaml comment lists no
# four-row shape. 6x2 is in that comment, is in Tiny Tapeout's billing
# table at twelve tiles, and has shipped on ttihp25a, 25b and 26a.
TILES = "6x2"

# RTL copied verbatim from hw/rtl. Order matters twice: source_files[0] is
# what tt-support-tools check_ports reads first, so the top level leads,
# and the same order is used for the Icarus command line in test/Makefile.
RTL_SOURCES = [
    TOP_MODULE + ".v",
    "pilot_top.v",
    "lif_core.v",
    "aer_fifo.v",
    "tmr_voter.v",
    "secded_enc.v",
    "secded_dec.v",
]
# Included textually by pilot_top.v. Not a source file: Yosys and Icarus
# both resolve `include relative to the including file, so it only has to
# sit next to pilot_top.v in src/. It is a build dependency all the same
# -- see test_makefile().
RTL_INCLUDES = ["npu_regs.vh"]

SOURCES = list(RTL_SOURCES)

# Register subset the pilot implements, in address order, with the
# one-line meaning a bench operator needs. Addresses and access codes are
# NOT written here: they are pulled from sw/golden/regmap_gen.py and
# cross-checked against this table, so a register-map edit that moves an
# offset either updates the datasheet or fails this generator.
REG_SUBSET = [
    ("ID", "RO", "Reads 0x4E505531. First thing to check on a live chip."),
    ("VERSION", "RO", "Register-map version."),
    ("SCRATCH", "RW", "Read/write scratch, no side effects."),
    ("CTRL", "RW", "EN, STATE_CLR, SOFT_RST, SCRUB_EN."),
    ("STATUS", "RO", "BUSY, IN_EMPTY, OUT_EMPTY, SYNC_DONE, ERR_CFG, DED_SEEN, OVF_SEEN."),
    ("STATUS_CLR", "W1C", "Clears the sticky STATUS bits."),
    ("CFG_NEUR", "RW", "Reads back the elaborated neuron count. Read-only in the pilot (D2)."),
    ("CFG_AXON", "RW", "Active axon count; drives the out-of-range drop rule."),
    ("CFG_THRESH", "RW", "Firing threshold. TMR domain."),
    ("CFG_VRESET", "RW", "Reset potential. TMR domain."),
    ("CFG_LEAK", "RW", "Leak shift. TMR domain."),
    ("CFG_SYNSHIFT", "RW", "Synaptic weight shift. TMR domain."),
    ("CFG_REFR", "RW", "Refractory period. TMR domain."),
    ("CFG_FLAGS", "RW", "Datapath mode flags. TMR domain."),
    ("PASS_TILE_OFF", "RW", "Per-pass tile offset added to the accumulator. TMR domain."),
    ("W_ADDR", "RW", "Weight-word index, auto-incremented by a W_DATA_HI write (D3)."),
    ("W_DATA_LO", "WO", "Low half of the 64-bit weight word; reads back the stored ECC data field (D4)."),
    ("W_DATA_HI", "WO", "High half; writing it commits the word through the SECDED encoder."),
    ("N_ADDR", "RW", "Neuron index for the state port."),
    ("N_DATA", "RW", "Membrane potential and refractory counter of neuron N_ADDR."),
    ("CNT_SEC", "RO", "Corrected single-bit ECC errors. Saturating, 8 bits in the pilot (D1)."),
    ("CNT_DED", "RO", "Detected uncorrectable ECC errors. Saturating."),
    ("CNT_EVQ_OVF", "RO", "Input events dropped for a full queue. Saturating."),
    ("CNT_AXON_OOR", "RO", "Events dropped for an axon id above CFG_AXON. Saturating."),
    ("FAULT_ADDR", "RO", "Weight-word index of the last uncorrectable word."),
    ("ECC_INJ", "WO", "Arms a single-bit or double-bit injection into the next stored codeword."),
    ("FAULT_CLR", "W1C", "Clears the fault counters and the sticky fault pins; one bit per counter, see above."),
    ("EVQ_STAT", "RO", "Occupancy of both event queues."),
    ("EVQ_IN", "WO", "Pushes one 16-bit event word into the input queue."),
    ("EVQ_OUT", "RO", "Pops one 16-bit event word from the output queue."),
    ("NODE_ID", "RW", "Node identifier carried in emitted events."),
]

# Pilot-only registers. They live in the unmapped region of the same
# window and are deliberately not part of regmap/regmap.yaml, so they are
# spelled out here (docs/15 section 3, deviation D5).
PILOT_ONLY_REGS = [
    (0x0A0, "ECC_INJ_POS", "RW", "Bit position, 0..71, that ECC_INJ corrupts in the stored codeword."),
    (0x0A4, "TMR_INJ", "RW", "{REP[1:0], BIT[5:0]}: holds one bit of one configuration replica wrong."),
    (0x0A8, "CNT_TMR", "RO", "Voter disagreements masked since the last FAULT_CLR. Saturating. Cleared by FAULT_CLR bit 5."),
]

PINOUT_UI = [
    ("SER_SCK", "Serial clock, mode 0 (CPOL 0, CPHA 0), at most clk/4"),
    ("SER_CS_N", "Frame select, active low"),
    ("SER_MOSI", "Serial data in, MSB first"),
    ("AER_IN_STB", "Event strobe, rising edge"),
    ("AER_IN_TICK", "0 = SPIKE at AER_IN_ADDR, 1 = TICK"),
    ("AER_OUT_ACK", "Consumer acknowledge, rising edge"),
    ("SCRUB_STB", "ECC re-check / scrub pulse, rising edge"),
    ("", "Reserved, tie low"),
]
PINOUT_UO = [
    ("SER_MISO", "Serial data out, MSB first"),
    ("BUSY", "STATUS.BUSY"),
    ("AER_IN_RDY", "Input queue has room for one more event"),
    ("AER_OUT_VLD", "An event id is presented on AER_OUT_ID"),
    ("ERR", "STATUS.ERR_CFG or STATUS.OVF_SEEN: a configuration fault, a queue overflow, or a control-state upset"),
    ("SEC", "Sticky: at least one single-bit ECC error corrected"),
    ("DED", "Sticky STATUS.DED_SEEN"),
    ("TMR", "Sticky: the configuration voter masked a disagreement"),
]
PINOUT_UIO = [
    ("AER_IN_ADDR[0]", "in"), ("AER_IN_ADDR[1]", "in"),
    ("AER_IN_ADDR[2]", "in"), ("AER_IN_ADDR[3]", "in"),
    ("AER_OUT_ID[0]", "out"), ("AER_OUT_ID[1]", "out"),
    ("AER_OUT_ID[2]", "out"), ("AER_OUT_ID[3]", "out"),
]

# ---------------------------------------------------------------------
# LibreLane configuration overrides
# ---------------------------------------------------------------------
# CORRECTED 2026-08-26. This block used to be empty, on the reasoning
# that "the replicas are not merged, because Yosys opt_merge does not
# merge flip-flops unless asked with -share_all". That reasoning was
# wrong and the measurement behind it was misread. opt_merge does not
# merge bit-level flip-flops on its own, but `opt_dff` first normalises
# the three identically-written replicas into identical enable
# flip-flops, and opt_merge then hashes THOSE into one bank. The
# artifact proves it: the netlist that fed the 4x2 harden,
# tt/runs/tt-harden/06-yosys-synthesis/tt_um_melihakbulut_nssoc.nl.v,
# has 362 references to `cfg_a[` and zero to `cfg_b[` or `cfg_c[`.
# The earlier `(* keep *)` experiment reported "the same 1036" because the
# attribute preserves the WIRE name while the storage still merges --
# the flip-flop count never moved, which is the number that mattered.
#
# hw/rtl/pilot_top.v header section 9 now builds each replica as a
# `pilot_cfg_bank` instance carrying `keep_hierarchy`, so this design
# is in exactly the position the sibling edge-AI project is in: under
# the LibreLane default SYNTH_HIERARCHY_MODE ("flatten",
# librelane/steps/pyosys.py) the three instances survive into the mapped
# netlist as derived module types whose names begin with `$paramod`, and
# the Checker.YosysUnmappedCells step counts every cell type starting
# with `$` as an unmapped instance (librelane/steps/pyosys.py, the
# design__instance_unmapped__count metric). The GDS action would abort.
#
# "deferred_flatten" is the documented answer and the one the sibling
# programme runs through GDS: LibreLane resynthesizes the already-mapped
# netlist with `synth -flatten`, which removes the hierarchy AFTER the
# banks are standard cells, so nothing can hash them together. Measured
# here on sg13g2 with the repository's own Yosys 0.33, using the
# standalone recipe of sw/tests/test_synthesis_guards.py: 1155
# flip-flops, 55 under each of u_cfg_a / u_cfg_b / u_cfg_c, and no cell
# type beginning with `$` left in the netlist. That recipe is not
# byte-for-byte LibreLane -- before the fix it read 1045 where the real
# 4x2 run read 1037 -- which is exactly why the guard test measures its
# own recipe rather than asserting a hardcoded LibreLane number.
#
# sw/tests/test_synthesis_guards.py is the check that keeps this true.
CONFIG_OVERRIDES: "dict[str, object]" = {
    "SYNTH_HIERARCHY_MODE": "deferred_flatten",
    # ------------------------------------------------------------------
    # The six keys below are what makes this design meet timing, and
    # until 2026-08-31 not one of them was in the submission path. That
    # was a shipping defect rather than a missing optimisation, and
    # docs/31 measured it rather than inferring it: hardening the
    # submission configuration on this RTL misses the slow corner by
    # -1.8321 ns derated, on 18 violating endpoints -- and the flow
    # reports that run CLEAN, because without SETUP_VIOLATION_CORNERS the
    # setup checker examines only the typical corner, which passes at
    # +6.8753. The adopted configuration is worth 3.0588 ns on the same
    # sources and the shuttle would have taken none of it.
    #
    # What each key is worth individually is in docs/28; the sign-off
    # that proves the combination is docs/31.
    # ------------------------------------------------------------------
    # A float deliberately: the PDKs ship this as the integer 5 and
    # LibreLane divides it with Tcl integer division, so an integer here
    # applies no derate at all while the log still prints "5%".
    "TIME_DERATING_CONSTRAINT": 5.0,
    # Without this the setup checker resolves its corners from
    # TIMING_VIOLATION_CORNERS, which both PDKs ship as ["*typ*"], so the
    # slow corner is gated by nothing. HOLD_VIOLATION_CORNERS already
    # ships as ["*"], so only setup was ever exposed.
    "SETUP_VIOLATION_CORNERS": ["*"],
    # Make the slow corner visible to place-and-route rather than only to
    # the final timing analysis, so repair happens where the violations
    # actually are.
    "PNR_CORNERS": ["nom_typ_1p20V_25C", "nom_slow_1p08V_125C"],
    # The repair that buys the margin: post-global-route, where the
    # estimate is close enough to act on. The only setup repair the
    # default flow runs is post-CTS, where the slow corner reads 4.28 ns
    # optimistic and so honestly finds nothing to fix.
    "RUN_POST_GRT_RESIZER_TIMING": 1,
    "RUN_POST_GRT_DESIGN_REPAIR": 1,
    "GRT_RESIZER_SETUP_SLACK_MARGIN": 0.5,
}

# =====================================================================
# Files taken verbatim from the upstream template. --diff-template proves
# that claim against the live repository.
# =====================================================================

VERBATIM = {}

VERBATIM[".github/workflows/gds.yaml"] = """name: gds

on:
  push:
  workflow_dispatch:

jobs:
  gds:
    runs-on: ubuntu-24.04
    steps:
      - name: checkout repo
        uses: actions/checkout@v6
        with:
          submodules: recursive

      - name: Build GDS
        uses: TinyTapeout/tt-gds-action@ttihp26b
        with:
          pdk: ihp-sg13g2

  precheck:
    needs: gds
    runs-on: ubuntu-24.04
    steps:
      - name: Run Tiny Tapeout Precheck
        uses: TinyTapeout/tt-gds-action/precheck@ttihp26b

  gl_test:
    needs: gds
    runs-on: ubuntu-24.04
    steps:
      - name: checkout repo
        uses: actions/checkout@v6
        with:
          submodules: recursive

      - name: GL test
        uses: TinyTapeout/tt-gds-action/gl_test@ttihp26b

  viewer:
    needs: gds
    runs-on: ubuntu-24.04
    permissions:
      pages: write # to deploy to Pages
      id-token: write # to verify the deployment originates from an appropriate source
    steps:
      - uses: TinyTapeout/tt-gds-action/viewer@ttihp26b
"""

VERBATIM[".github/workflows/test.yaml"] = """name: test
on: [push, workflow_dispatch]
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - name: Checkout repo
        uses: actions/checkout@v6
        with:
          submodules: recursive

      - name: Install iverilog
        shell: bash
        run: sudo apt-get update && sudo apt-get install -y iverilog

      # Set Python up and install cocotb
      - name: Setup python
        uses: actions/setup-python@v6
        with:
          python-version: '3.11'

      - name: Install Python packages
        shell: bash
        run: pip install -r test/requirements.txt

      - name: Run tests
        run: |
          cd test
          make clean
          make
          # make will return success even if the test fails, so check for failure in the results.xml
          ! grep failure results.xml

      - name: Test Summary
        uses: test-summary/action@v2.4
        with:
          paths: "test/results.xml"
        if: always()

      - name: upload waveform and test results
        if: success() || failure()
        uses: actions/upload-artifact@v7
        with:
          name: test-results
          path: |
            test/tb.fst
            test/results.xml
            test/output/*
"""

VERBATIM[".github/workflows/docs.yaml"] = """name: docs

on:
  push:
  workflow_dispatch:

jobs:
  docs:
    runs-on: ubuntu-24.04
    steps:
      - name: Checkout repo
        uses: actions/checkout@v6
        with:
          submodules: recursive

      - name: Build docs
        uses: TinyTapeout/tt-gds-action/docs@ttihp26b
"""

VERBATIM[".github/workflows/fpga.yaml"] = """name: fpga

on:
  push:
    # Comment out (or remove) the following line to run the FPGA workflow on every push:
    branches: none
  workflow_dispatch:

jobs:
  fpga:
    runs-on: ubuntu-24.04
    steps:
      - name: checkout repo
        uses: actions/checkout@v6
        with:
          submodules: recursive

      - name: FPGA bitstream for TT ASIC Sim (ICE40UP5K)
        uses: TinyTapeout/tt-gds-action/fpga/ice40up5k@ttihp26b
"""

VERBATIM[".devcontainer/Dockerfile"] = """ARG VARIANT=ubuntu-24.04
FROM mcr.microsoft.com/vscode/devcontainers/base:${VARIANT}

ENV DEBIAN_FRONTEND=noninteractive
ENV PDK_ROOT=/home/vscode/ttsetup/pdk
ENV PDK=ihp-sg13g2
ARG TT_SUPPORT_TOOLS_BRANCH=main

RUN apt update
RUN apt install -y iverilog gtkwave python3 python3-pip python3-venv python3-tk python-is-python3 libcairo2 verilator libpng-dev libqhull-dev

# Clone tt-support-tools
RUN mkdir -p /ttsetup
RUN git clone -b ${TT_SUPPORT_TOOLS_BRANCH} https://github.com/TinyTapeout/tt-support-tools /ttsetup/tt-support-tools

COPY test/requirements.txt /ttsetup/test_requirements.txt
COPY .devcontainer/copy_tt_support_tools.sh /ttsetup

RUN python -m venv /ttsetup/venv
RUN /ttsetup/venv/bin/pip install -r /ttsetup/test_requirements.txt -r /ttsetup/tt-support-tools/requirements.txt

# Install verible (for formatting)
RUN umask 022 && \\
    curl -L https://github.com/chipsalliance/verible/releases/download/v0.0-4023-gc1271a00/verible-v0.0-4023-gc1271a00-linux-static-x86_64.tar.gz | \\
    tar zxf - -C /usr/local --strip-components=1 && \\
    chmod 755 /usr/local/bin

# Install LibreLane
RUN /ttsetup/venv/bin/pip install librelane==3.0.0.dev44
"""

VERBATIM[".devcontainer/devcontainer.json"] = """// For format details, see https://aka.ms/devcontainer.json. For config options, see the README at:
// https://github.com/microsoft/vscode-dev-containers/tree/v0.183.0/containers/ubuntu
{
  "name": "Tiny Tapeout Dev Container",
  "build": {
    "dockerfile": "Dockerfile",
    "context": ".."
  },
  "runArgs": [
    "--memory=10GB"
  ],
  "customizations": {
    "vscode": {
      "settings": {
        "terminal.integrated.defaultProfile.linux": "bash"
      },
      "extensions": ["mshr-h.veriloghdl", "surfer-project.surfer"]
    }
  },
  "features": {
    "ghcr.io/devcontainers/features/docker-in-docker:2": {
      "moby": true,
      "azureDnsAutoDetection": true,
      "version": "latest",
      "dockerDashComposeVersion": "none"
    }
  },
  "postCreateCommand": "echo 'source /ttsetup/venv/bin/activate' >> ~/.bashrc",
  "postStartCommand": "/ttsetup/copy_tt_support_tools.sh"
}
"""

VERBATIM[".devcontainer/copy_tt_support_tools.sh"] = """#! /bin/sh

if [ ! -L tt ]; then
    cp -R /ttsetup/tt-support-tools tt
    cd tt && git pull && cd ..
fi
"""

VERBATIM[".vscode/extensions.json"] = """{
  "recommendations": [
    "mshr-h.veriloghdl",
    "surfer-project.surfer"
  ]
}"""

VERBATIM[".vscode/settings.json"] = """{
  "verilog.linting.linter": "verilator",
  "verilog.formatting.verilogHDL.formatter": "verible-verilog-format"
}
"""

VERBATIM["test/requirements.txt"] = """pytest==8.4.2
cocotb==2.0.1
"""

TEST_README_UPSTREAM = """# Sample testbench for a Tiny Tapeout project

This is a sample testbench for a Tiny Tapeout project. It uses [cocotb](https://docs.cocotb.org/en/stable/) to drive the DUT and check the outputs.
See below to get started or for more information, check the [website](https://tinytapeout.com/hdl/testing/).

## Setting up

1. Edit [Makefile](Makefile) and modify `PROJECT_SOURCES` to point to your Verilog files.
2. Edit [tb.v](tb.v) and replace `tt_um_example` with your module name.

## How to run

To run the RTL simulation:

```sh
make -B
```

To run gatelevel simulation, first harden your project and copy `../runs/wokwi/results/final/verilog/gl/{your_module_name}.v` to `gate_level_netlist.v`.

Then run:

```sh
make -B GATES=yes
```

If you wish to save the waveform in VCD format instead of FST format, edit tb.v to use `$dumpfile("tb.vcd");` and then run:

```sh
make -B FST=
```

This will generate `tb.vcd` instead of `tb.fst`.

## How to view the waveform file

Using GTKWave

```sh
gtkwave tb.fst tb.gtkw
```

Using Surfer

```sh
surfer tb.fst
```
"""

# Appended to the upstream test/README.md. Recorded because it costs a
# debugging session to rediscover.
TEST_README_EXTRA = """
---

## A note on gate-level simulation with a distribution Icarus

`make -B GATES=yes` needs more than stock Icarus Verilog. The
`ihp-sg13g2` standard-cell simulation models drive their outputs from
`delayed_D`, `delayed_CLK` and `delayed_RESET_B`, which are the
negative-timing-check outputs of `$setuphold` and `$recrem`. A simulator
that does not implement those leaves the delayed signals undriven, and
Icarus says so:

```
warning: Timing checks are not supported and delayed signal "delayed_CLK" will not be driven.
```

Every flip-flop output is then stuck at `x` for the whole simulation.
The symptom is not a crash: the design simply reads back zeros, so it
looks like a broken netlist rather than a broken model.

Measured on this project with Icarus 12.0 (stable) and the netlist from
a completed local harden: 1 of 5 tests passes. Driving the delayed
signals from their undelayed sources in a scratch copy of
`sg13g2_stdcell.v` and changing nothing else: 5 of 5 pass, matching the
RTL run exactly.

The Tiny Tapeout `gl_test` workflow does not have this problem - it
installs `TinyTapeout/iverilog` v13.0 rather than a distribution build.
If you want to run gate-level simulation locally, use that build.

Where the netlist comes from: `gate_level_netlist.v` is not checked in
and nothing in this repository produces it. Either take it from the GDS
action's `tt_submission` artifact, or copy it out of a local harden:

```sh
cp ../runs/wokwi/final/nl/<top_module>.nl.v gate_level_netlist.v
```

Delete it when you are done. A stale netlist left in place makes
`GATES=yes` silently test the previous revision.
"""

# The upstream src/config.json, byte for byte. CONFIG_OVERRIDES, when
# non-empty, is appended as extra keys; tt-support-tools config_utils
# reads this file with json.load, which keeps the last value for a
# duplicated key and then drops every "//" comment key, so appending is
# safe and the upstream comments survive in the file for a human reader.
VERBATIM["src/config.json"] = """{
  "//": "DO NOT EDIT THIS FILE before reading the comments below:",

  "//": "This is the default configuration for Tiny Tapeout projects. It should fit most designs.",
  "//": "If you change it, please make sure you understand what you are doing. We are not responsible",
  "//": "if your project fails because of a bad configuration.",

  "//": "!!! DO NOT EDIT THIS FILE unless you know what you are doing !!!",

  "//": "If you get stuck with this config, please open an issue or get in touch via the discord.",

  "//": "Here are some of the variables you may want to change:",

  "//": "PL_TARGET_DENSITY_PCT - You can increase this if Global Placement fails with error GPL-0302.",
  "//": "Users have reported that values up to 80 worked well for them.",
  "PL_TARGET_DENSITY_PCT": 60,

  "//": "CLOCK_PERIOD - Increase this in case you are getting setup time violations.",
  "//": "The value is in nanoseconds, so 20ns == 50MHz.",
  "CLOCK_PERIOD": 20,

  "//": "Hold slack margin - Increase them in case you are getting hold violations.",
  "PL_RESIZER_HOLD_SLACK_MARGIN": 0.1,
  "GRT_RESIZER_HOLD_SLACK_MARGIN": 0.05,

  "//": "RUN_LINTER, LINTER_INCLUDE_PDK_MODELS - Disabling the linter is not recommended!",
  "RUN_LINTER": 1,
  "LINTER_INCLUDE_PDK_MODELS": 1,

  "//": "If you need a custom clock configuration, read the following documentation first:",
  "//": "https://tinytapeout.com/faq/#how-can-i-map-an-additional-external-clock-to-one-of-the-gpios",
  "CLOCK_PORT": "clk",

  "//": "Configuration docs: https://librelane.readthedocs.io/en/latest/reference/configuration.html",

  "//": "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!",
  "//": "!!! DO NOT CHANGE ANYTHING BELOW THIS POINT !!!",
  "//": "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!",

  "//": "Save some time",
  "RUN_KLAYOUT_XOR": 0,
  "RUN_KLAYOUT_DRC": 0,

  "//": "Don't put clock buffers on the outputs",
  "DESIGN_REPAIR_BUFFER_OUTPUT_PORTS": 0,

  "//": "Reduce wasted space",
  "TOP_MARGIN_MULT": 1,
  "BOTTOM_MARGIN_MULT": 1,
  "LEFT_MARGIN_MULT": 6,
  "RIGHT_MARGIN_MULT": 6,

  "//": "Absolute die size",
  "FP_SIZING": "absolute",

  "GRT_ALLOW_CONGESTION": 1,

  "FP_IO_HLENGTH": 2,
  "FP_IO_VLENGTH": 2,

  "FP_PDN_VPITCH": 38.87,

  "//": "Clock",
  "RUN_CTS": 1,

  "//": "Don't generate power rings",
  "FP_PDN_MULTILAYER": 0,

  "//": "MAGIC_DEF_LABELS may cause issues with LVS",
  "MAGIC_DEF_LABELS": 0,

  "//": "Only export pin area in LEF (without any connected nets)",
  "MAGIC_WRITE_LEF_PINONLY": 1
}
"""

# Upstream .gitignore, plus one entry. Not in the verbatim set.
GITIGNORE_UPSTREAM = """.DS_Store
.idea
*.vcd
*.fst
*.fst.hier
runs
tt_submission
src/user_config.json
src/config_merged.json
test/sim_build
test/__pycache__/
test/results.xml
test/gate_level_netlist.v
"""

GITIGNORE_EXTRA = """
# tt-support-tools is copied in here by the dev container and by the GDS
# action (.devcontainer/copy_tt_support_tools.sh). It is a checkout of
# someone else's repository and must never be committed into this tree.
/tt/
"""


# =====================================================================
# Generated files
# =====================================================================


def _banner(comment: str) -> str:
    return (
        f"{comment} GENERATED by scripts/gen_tt_submission.py in the\n"
        f"{comment} neuromorphic-space-soc repository. Do not edit this file:\n"
        f"{comment} edit the source repository and regenerate. Drift is caught\n"
        f"{comment} by MANIFEST.sha256 and by sw/tests/test_tt_submission.py.\n"
    )


def info_yaml() -> str:
    lines = []
    lines.append("# Tiny Tapeout project information.")
    lines.append("#")
    lines.append("# GENERATED by scripts/gen_tt_submission.py in the")
    lines.append("# neuromorphic-space-soc repository. Do not edit here.")
    lines.append("#")
    lines.append(f"# Schema: tt-support-tools project_info.py, yaml_version 6")
    lines.append(f"# ({SUPPORT_TOOLS_COMMIT[:12]}).")
    lines.append("project:")
    lines.append(f'  title:        "{TITLE}"')
    lines.append(f'  author:       "{AUTHOR}"')
    lines.append('  discord:      ""')
    lines.append(f'  description:  "{DESCRIPTION}"')
    lines.append('  language:     "Verilog"')
    lines.append("")
    lines.append("  # 50 MHz. A local place-and-route of this design at this tile")
    lines.append("  # shape closes with +1.23 ns of setup slack and +0.60 ns of")
    lines.append("  # hold slack on the slow corner (sg13g2_stdcell 1.08 V, 125 C),")
    lines.append("  # with a clock tree and extracted parasitics: zero setup, hold,")
    lines.append("  # max-cap and max-slew violations on all three PVT corners.")
    lines.append("  # Not a signoff; see docs/23 section 3 in the source")
    lines.append("  # repository.")
    lines.append(f"  clock_hz:     {CLOCK_HZ}")
    lines.append("")
    lines.append("  # Tile shape. docs/23: placed, this design is 185,840 um2 of")
    lines.append("  # sg13g2 standard cells, which no longer fits the 70 % planning")
    lines.append("  # criterion in a 4x2 core of 259,837 um2 (docs/22 measures")
    lines.append("  # 71.489 %). 6x2 offers 392,988 um2 and a full local harden")
    lines.append("  # there closes at 47.29 % utilization with zero detailed-route")
    lines.append("  # DRC errors, zero Magic and KLayout DRC, zero LVS errors and")
    lines.append("  # zero antenna violations. The alternative twelve-tile shape,")
    lines.append("  # 3x4, was hardened too and is the runner-up on every count")
    lines.append("  # except utilization; docs/23 has both side by side.")
    lines.append(f'  tiles: "{TILES}"')
    lines.append("")
    lines.append(f'  top_module:  "{TOP_MODULE}"')
    lines.append("")
    lines.append("  source_files:")
    for src in SOURCES:
        lines.append(f'    - "{src}"')
    lines.append("")
    lines.append("# Pin contract. Identical to hw/rtl/pilot_top.v section 1 and to")
    lines.append("# docs/15 section 2 in the source repository.")
    lines.append("pinout:")
    lines.append("  # Inputs")
    for i, (name, _) in enumerate(PINOUT_UI):
        lines.append(f'  ui[{i}]: "{name}"')
    lines.append("")
    lines.append("  # Outputs")
    for i, (name, _) in enumerate(PINOUT_UO):
        lines.append(f'  uo[{i}]: "{name}"')
    lines.append("")
    lines.append("  # Bidirectional pins: uio_oe is the constant 0xF0, so uio[3:0]")
    lines.append("  # are always inputs and uio[7:4] are always outputs.")
    for i, (name, _) in enumerate(PINOUT_UIO):
        lines.append(f'  uio[{i}]: "{name}"')
    lines.append("")
    lines.append("# Do not change!")
    lines.append("yaml_version: 6")
    return "\n".join(lines) + "\n"


def _reg_table(addr, access):
    rows = ["| Offset | Register | Access | Meaning |", "|---|---|---|---|"]
    for name, want_access, desc in REG_SUBSET:
        if name not in addr:
            raise SystemExit(
                f"register {name} is in the pilot subset but not in "
                f"sw/golden/regmap_gen.py -- the register map moved, update "
                f"REG_SUBSET in scripts/gen_tt_submission.py"
            )
        if access[name] != want_access:
            raise SystemExit(
                f"register {name}: regmap says access={access[name]}, this "
                f"generator says {want_access} -- update REG_SUBSET"
            )
        rows.append(f"| 0x{addr[name]:03X} | {name} | {want_access} | {desc} |")
    return "\n".join(rows)


def _pilot_only_table():
    rows = ["| Offset | Register | Access | Meaning |", "|---|---|---|---|"]
    for off, name, acc, desc in PILOT_ONLY_REGS:
        rows.append(f"| 0x{off:03X} | {name} | {acc} | {desc} |")
    return "\n".join(rows)


def _pin_table(pins, kind):
    rows = [f"| Pin | Name | Function |", "|---|---|---|"]
    for i, (name, fn) in enumerate(pins):
        rows.append(f"| {kind}[{i}] | {name or '-'} | {fn} |")
    return "\n".join(rows)


def info_md(addr, access) -> str:
    return f"""<!--
GENERATED by scripts/gen_tt_submission.py in the neuromorphic-space-soc
repository. Do not edit here; edit the source repository and regenerate.

Register offsets and access codes in this file are read from
sw/golden/regmap_gen.py, which is generated from regmap/regmap.yaml, so
the datasheet cannot drift away from the hardware.
-->

## How it works

{TITLE.split(' ', 1)[0]} is the pilot test chip of a fault-tolerant neuromorphic
system-on-chip for small-satellite missions. It is one node slice of that
architecture, shrunk to a Tiny Tapeout block, and it carries the parts
that are worth measuring on real silicon rather than in simulation.

**The datapath.** An 8 x 8 leaky integrate-and-fire crossbar: eight
neurons, eight axons, 64 four-bit signed synapses held in flip-flops.
Events arrive as SPIKE or TICK words. A SPIKE accumulates the addressed
axon's weight column into every neuron's membrane potential; a TICK
applies the leak, compares against the threshold, emits an event for
every neuron that fired, resets it and starts its refractory count. The
arithmetic is bit-exact against a Python reference model in the source
repository, checked event by event and neuron by neuron.

**Fault tolerance, on the real datapath rather than beside it.** Three
mechanisms, all observable from outside with nothing but an
oscilloscope:

- *SECDED.* The 64-bit weight word that software writes is the data
  field of a physically stored (72, 64) Hsiao codeword. On commit the
  check field is computed, the armed `ECC_INJ` pattern is XORed into the
  stored codeword, the decoder runs, and the weight loader writes the 16
  weights into the crossbar *from the decoder output*. A corrected
  single-bit upset therefore never reaches the datapath, and an
  uncorrectable word contributes zero weight instead of garbage. The
  injected error survives in the stored word, so the same fault can be
  re-checked from the `SCRUB_STB` pin as often as you like;
  `ECC_INJ_POS` moves the injected bit anywhere in the 72-bit codeword,
  so the whole syndrome space is walkable on silicon.
- *TMR.* Every configuration bit that reaches the crossbar - threshold,
  reset potential, leak, synaptic shift, refractory period, the flag
  bits and the tile offset, 55 bits in total - is held in three replicas
  and voted before it leaves the register block. `TMR_INJ` holds one bit
  of one replica wrong. Software still reads the voted value, the
  inference still produces exactly the same spike stream, and `CNT_TMR`
  and the TMR pin still record that it happened.
- *Control-state upsets.* The neuron core's control state machine is
  encoded in five words that are pairwise at Hamming distance 2, so a
  single-bit upset in that register always produces a word no legal
  transition can make. The core then parks in a safe state, freezes the
  neuron state file, refuses further work, and raises `STATUS.ERR_CFG`
  and the ERR pin. A bench measuring upset rates sees the event on a
  pin, with no polling. While the core is parked the bit cannot be
  cleared - `STATUS_CLR` will not report a live fault as gone.
  `CTRL.SOFT_RST` is the recovery: it restarts the core and keeps both
  the configuration and the neuron state. The bit survives that reset,
  so recovering before you poll does not lose the event; `STATUS_CLR`
  then clears it.

Four of the eight dedicated outputs are fault pins (ERR, SEC, DED, TMR).
That is deliberate: every hardening event is visible on a scope with no
host software running, which is what a bench measuring upset rates
actually needs.

**Honest limits.** Three, and every one of them matters to somebody
measuring this part:

- The TMR injector drives a replica's read path, not its storage
  flip-flop, so there is no replica resynchronization on this chip. A
  configuration rewrite restores all three replicas.
- The fault counters are 8 bits and saturate, rather than the 32 bits of
  the architecture's register map. At a high event rate, read them
  often.
- There is no SRAM macro and no management processor on this die. The
  chip is driven from the serial port, which is what a bring-up board
  does anyway.

## How to test

### Talking to the chip

The host port is a mode-0 SPI slave (CPOL 0, CPHA 0), MSB first, one
register per frame. A frame is 40 `SER_SCK` cycles: a command byte
`{{WR, ADDR[6:0]}}` followed by 32 data bits. `ADDR[6:0]` is the register
offset in the tables below shifted right by two.

Reads: the addressed register is captured when the command byte
completes and shifted out on the following falling edges, so the host
samples data bit 31 on `SER_SCK` cycle 9. Read side effects (the
`EVQ_OUT` pop) happen once, at that capture. Writes commit on the 40th
rising edge, not at `CS_N` release, so an aborted frame changes nothing.

Three host obligations, and all three are real - each one is held at its
boundary value by the regression suite:

1. `SER_SCK` at most `clk`/4. The serial port lives entirely in the
   `clk` domain behind two-flop synchronizers.
2. `SER_CS_N` must fall at least one full `SER_SCK` period **before** the
   first `SER_SCK` edge. A host that drops the select and clocks
   immediately risks losing the first command bit.
3. `SER_CS_N` must stay high at least one full `SER_SCK` period
   **between** frames. The bit counter is held at zero only while the
   synchronized select reads inactive, so a deselect that is never seen
   leaves the counter running and the next frame decodes at the wrong
   offset. This was found during bring-up with a half-period gap.

### First contact

Read offset 0x000. It returns `0x4E505531` (ASCII "NPU1"). If it does
not, check obligations 1 to 3 before suspecting the chip.

### A minimal inference

1. Write `CFG_AXON` = 8, and the neuron parameters (`CFG_THRESH`,
   `CFG_VRESET`, `CFG_LEAK`, `CFG_SYNSHIFT`, `CFG_REFR`).
2. Load weights: for each of the four weight words, write `W_ADDR`, then
   `W_DATA_LO`, then `W_DATA_HI`. The `W_DATA_HI` write commits the
   72-bit codeword and auto-increments `W_ADDR`.
3. Write `CTRL.EN` = 1.
4. Push events: either write 16-bit event words to `EVQ_IN` over the
   serial port, or strobe them in on the pins - put the axon id on
   `uio[3:0]`, set `AER_IN_TICK` for a TICK or clear it for a SPIKE, and
   pulse `AER_IN_STB`. Watch `AER_IN_RDY` for backpressure.
5. Read results: poll `EVQ_STAT` and read `EVQ_OUT`, or watch
   `AER_OUT_VLD` and read the emitted neuron id off `uio[7:4]`, then
   pulse `AER_OUT_ACK`. Neuron state is readable at any time through
   `N_ADDR` / `N_DATA`.

### Exercising the fault tolerance

**Single-bit ECC correction.** Write `ECC_INJ_POS` with a bit position
0..71, write `ECC_INJ` with the SINGLE bit set, then commit a weight word
(`W_ADDR`, `W_DATA_LO`, `W_DATA_HI`). The SEC pin goes high, `CNT_SEC`
increments, and the weights that reach the crossbar are the correct ones
- run the inference and compare. The corrupted codeword stays corrupted,
so pulsing `SCRUB_STB` re-runs the check as often as you want. Set
`CTRL.SCRUB_EN` first and each check writes the repaired word back
instead, after which the SEC pin stops firing on that word.

**Double-bit ECC detection.** Same sequence with the DOUBLE bit of
`ECC_INJ` set. The DED pin goes high, `CNT_DED` increments,
`FAULT_ADDR` holds the offending weight-word index, and those 16 weights
contribute zero to the inference rather than a wrong value.

**TMR masking.** Write `TMR_INJ` with a replica selector (01, 10 or 11)
and a bit index 0..54. The TMR pin goes high and `CNT_TMR` increments,
while the voted configuration reads back correct and the spike stream is
bit-identical to the uncorrupted run. Clear it by writing `TMR_INJ` = 0
or by rewriting the configuration register.

**Control-state upsets.** There is no injection hook for this one, and
that is the honest position: a fault injector for the neuron core's own
state register would be logic that only exists to be wrong. On a bench
it is what you are waiting to see. If an upset lands in that register,
the core parks, `STATUS.ERR_CFG` and the ERR pin go high and stay high,
`STATUS.BUSY` stays high because the core never returns to idle, and no
further event is processed. `STATUS_CLR` will not clear it while the
core is parked. Recover with `CTRL.SOFT_RST`: the configuration and the
neuron state survive and the core runs again, but `STATUS.ERR_CFG` and
the ERR pin stay high so the event is not lost by recovering from it.
Clear them with `STATUS_CLR` once it is recorded.

**Clearing.** `FAULT_CLR` is a write-1-to-clear mask, one bit per
counter, in the architecture register map's order:

| Bit | Clears |
|---|---|
| 0 | `CNT_SEC`, and the SEC pin |
| 1 | `CNT_DED` |
| 2 | `CNT_EVQ_OVF` |
| 3 | `CNT_AXON_OOR` |
| 4 | `FAULT_ADDR` |
| 5 | `CNT_TMR`, and the TMR pin (pilot-only, see below) |

Bits 0 to 4 are the architecture register map's own assignment. Bit 5 is
this pilot's, because `CNT_TMR` is a pilot-only register and the map
leaves bits 5 and up unassigned. Writing `0x3F` clears everything.
`STATUS_CLR` clears the sticky `STATUS` bits, and with them the DED pin;
the ERR pin follows `STATUS.ERR_CFG` and `STATUS.OVF_SEEN`.

### Register map

Offsets are byte offsets; the serial command byte carries the offset
shifted right by two. `W1C` = write one to clear, `WO` = write only,
`RO` = read only.

{_reg_table(addr, access)}

Three registers exist only on this pilot. They sit in the unmapped
region of the same window and do not change the architecture's register
map:

{_pilot_only_table()}

`W_BASE` and `PASS_ID` of the architecture register map are not
implemented here: both are multi-pass sequencer bookkeeping with no
hardware effect in a single-pass build. They read as zero and reject
writes, like any other unmapped offset.

### Pinout detail

Dedicated inputs:

{_pin_table(PINOUT_UI, "ui")}

Dedicated outputs:

{_pin_table(PINOUT_UO, "uo")}

Bidirectionals. `uio_oe` is fixed at `0xF0` in the design, so `uio[3:0]`
are always inputs and `uio[7:4]` are always outputs:

| Pin | Direction | Name | Function |
|---|---|---|---|
| uio[3:0] | input | AER_IN_ADDR | Axon id of the strobed event |
| uio[7:4] | output | AER_OUT_ID | Emitted neuron id |

The full 16-bit event word is always readable over `EVQ_OUT`; the uio
nibble is the low four bits of its id field, for a consumer that wants
the event stream without a host.

### The full regression

`test/` in this repository holds a self-contained cocotb smoke test that
runs without any of the source repository. The complete suite - 21
cocotb tests driving this exact port list, plus a bit-exact Python
reference model, plus SymbiYosys proofs of the event queue, the voter
and the SECDED codec - lives in the source repository.

## External hardware

An SPI master. Any microcontroller board with a mode-0 SPI peripheral
will do, and the demo board's RP2040 is enough. A logic analyser or
oscilloscope on the four fault pins is useful but not required. No
external memory, no level shifting, no other hardware.
"""


def readme_md() -> str:
    return f"""<!--
GENERATED by scripts/gen_tt_submission.py in the neuromorphic-space-soc
repository. Do not edit here; edit the source repository and regenerate.
-->

![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg)

# {TITLE}

Tiny Tapeout TTIHP26b submission, {TILES} tiles, IHP SG13G2.

- Datasheet source: [docs/info.md](docs/info.md)
- Top module: `{TOP_MODULE}`

## Status

The design has been taken through a full local LibreLane `Classic` run
at {TILES} against this repository's own `src/config_merged.json`. It closes
at 47.29 % utilization with zero detailed-route DRC errors, zero Magic
DRC errors, zero KLayout DRC errors, zero Netgen LVS errors, zero antenna
violations, and zero setup, hold, max-cap and max-slew violations across
all three PVT corners. The tile shape was chosen on measured area, and
re-chosen when the design outgrew the first choice: placed, the design is
185,840 um2 of standard cells, which overruns the 70 % planning criterion
in a 4x2 core of 259,837 um2. Both twelve-tile shapes were then hardened
rather than estimated, and {TILES} won. Full working in
`docs/15-pilot-tile-plan.md` and `docs/23-tile-shape-decision.md` in the
source repository.

That local run is evidence, not a substitute for the GDS action and the
Tiny Tapeout precheck, which are what actually gate a submission.

## This tree is generated

Every file here is produced by `scripts/gen_tt_submission.py` in the
source repository `neuromorphic-space-soc`. Do not edit anything in this
tree: edit the source repository and regenerate. `MANIFEST.sha256`
records a SHA-256 for every generated file, and a test in the source
repository fails if the two disagree in either direction.

Every `.v` and `.vh` file under `src/` is copied byte for byte out of
the source repository's `hw/rtl/`. Nothing here is a generated stand-in:
the top level `{TOP_MODULE}` carries its shuttle-unique name in the
source repository as well, so what is hardened is what is simulated
there.

## Scaffolding provenance

`.github/`, `.devcontainer/`, `.vscode/`, `src/config.json`,
`test/Makefile`, `test/tb.v` and `test/requirements.txt`
are ported from the upstream Tiny Tapeout template:

    {TEMPLATE_URL}
    commit {TEMPLATE_COMMIT}

`src/config.json` is byte-identical to upstream. Running
`scripts/gen_tt_submission.py --diff-template` in the source repository
re-fetches the template and proves that claim for every file that carries
it.

## Licence

**Not yet decided.** See `LICENSE.PENDING.md`. This tree must not be
published until that file is replaced with a real licence.

## Running the tests

```sh
cd test
make -B
```

Requires `iverilog` and the packages in `test/requirements.txt`.
"""


def license_pending_md() -> str:
    return """<!--
GENERATED by scripts/gen_tt_submission.py in the neuromorphic-space-soc
repository. Do not edit here; edit the source repository and regenerate.
-->

# Licence: decision open

This tree deliberately carries **no `LICENSE` file**, and that is a
blocking item rather than an oversight.

The upstream Tiny Tapeout template ships Apache-2.0 for its own
scaffolding. The design sources in `src/` are not the template's, and the
licence that applies to them has not been decided. The decision memo is
`docs/14-licensing-decision.md` in the source repository
`neuromorphic-space-soc`; it recommends CERN-OHL-W-2.0 for hardware
sources, Apache-2.0 for software and CC-BY-4.0 for documents, and it is
**unsigned**. Section 9 of that memo puts the signature deadline at
2026-08-31 and the shuttle submission at 2026-09-21.

Consequences, stated plainly:

1. A Tiny Tapeout submission is a public repository. Publishing this
   tree without a licence publishes the design sources with no grant at
   all, which is worse for the project than any of the candidate
   licences.
2. The licence decision therefore has to be made **before** the
   submission, not before the memo's own 2026-10-15 deadline.
3. Until it is made, this tree can be built, tested and prechecked in a
   private repository, but it must not be pushed to a public one.

What to do when the memo is signed: add the chosen `LICENSE` file, add
SPDX headers to the files in `src/` in the source repository (they are
copied here byte for byte, so the headers have to be added there), note
in this file's place that the scaffolding listed in `README.md` remains
Apache-2.0 as received from the template, and regenerate.
"""


def test_makefile() -> str:
    sources = " ".join(SOURCES)
    includes = " ".join(f"$(SRC_DIR)/{name}" for name in RTL_INCLUDES)
    return (
        _banner("#")
        + f"""#
# Ported from the upstream template ({TEMPLATE_COMMIT[:12]}). Two changes:
# PROJECT_SOURCES, and PROJECT_INCLUDES below.
#
# See https://docs.cocotb.org/en/stable/quickstart.html for more info

# defaults
SIM ?= icarus
FST ?= -fst # Use more efficient FST format
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../src
PROJECT_SOURCES = {sources}

# Headers the sources pull in with `include. They are not compiled on
# their own, so they never appear in VERILOG_SOURCES -- which means the
# cocotb rule that rebuilds sim.vvp cannot see them either, and an
# incremental `make` after editing one silently re-runs the PREVIOUS
# elaboration and reports a pass for code that was never compiled.
# Adding them as prerequisites of the same target fixes that; see the
# extra dependency line at the end of this file.
PROJECT_INCLUDES = {includes}

ifneq ($(GATES),yes)

# RTL simulation:
SIM_BUILD				= sim_build/rtl
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))

else

# Gate level simulation:
SIM_BUILD				= sim_build/gl
COMPILE_ARGS    += -DGL_TEST
COMPILE_ARGS    += -DFUNCTIONAL
COMPILE_ARGS    += -DSIM
VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13g2/libs.ref/sg13g2_io/verilog/sg13g2_io.v
VERILOG_SOURCES += $(PDK_ROOT)/ihp-sg13g2/libs.ref/sg13g2_stdcell/verilog/sg13g2_stdcell.v

# this gets copied in by the GDS action workflow
VERILOG_SOURCES += $(PWD)/gate_level_netlist.v

endif

# Allow sharing configuration between design and testbench via `include`:
COMPILE_ARGS 		+= -I$(SRC_DIR)

# Include the testbench sources:
VERILOG_SOURCES += $(PWD)/tb.v
TOPLEVEL = tb

# List test modules to run, separated by commas and without the .py suffix:
COCOTB_TEST_MODULES = test

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim

# Rebuild when an included header changes. This has to come AFTER the
# include above, because it adds prerequisites to a target that cocotb's
# Makefile.icarus defines ($(SIM_BUILD)/sim.vvp); a prerequisite-only
# line leaves cocotb's recipe alone. Without it, `make` after a header
# edit is a false PASS: iverilog is never re-run and the old sim.vvp is
# executed.
$(SIM_BUILD)/sim.vvp: $(PROJECT_INCLUDES)
"""
    )


def test_tb_v() -> str:
    return (
        _banner("//")
        + f"""//
// Ported from the upstream template ({TEMPLATE_COMMIT[:12]}). The only
// change is the instantiated module name.
`default_nettype none
`timescale 1ns / 1ps

/* This testbench just instantiates the module and makes some convenient wires
   that can be driven / tested by the cocotb test.py.
*/
module tb ();

  // Dump the signals to a FST file. You can view it with gtkwave or surfer.
  initial begin
    $dumpfile("tb.fst");
    $dumpvars(0, tb);
    #1;
  end

  // Wire up the inputs and outputs:
  reg clk;
  reg rst_n;
  reg ena;
  reg [7:0] ui_in;
  reg [7:0] uio_in;
  wire [7:0] uo_out;
  wire [7:0] uio_out;
  wire [7:0] uio_oe;

  {TOP_MODULE} user_project (
      .ui_in  (ui_in),    // Dedicated inputs
      .uo_out (uo_out),   // Dedicated outputs
      .uio_in (uio_in),   // IOs: Input path
      .uio_out(uio_out),  // IOs: Output path
      .uio_oe (uio_oe),   // IOs: Enable path (active high: 0=input, 1=output)
      .ena    (ena),      // enable - goes high when design is selected
      .clk    (clk),      // clock
      .rst_n  (rst_n)     // not reset
  );

endmodule
"""
    )


def test_gtkw() -> str:
    return """[*]
[*] GTKWave save file for the Tiny Tapeout port list.
[*]
[dumpfile] "tb.fst"
[timestart] 0
[size] 1376 600
[pos] -1 -1
[treeopen] tb.
[sst_width] 297
[signals_width] 230
[sst_expanded] 1
[sst_vpaned_height] 158
@28
tb.user_project.ena
@29
tb.user_project.clk
@28
tb.user_project.rst_n
@200
-Inputs
@22
tb.user_project.ui_in[7:0]
@200
-Bidirectional Pins
@22
tb.user_project.uio_in[7:0]
tb.user_project.uio_oe[7:0]
tb.user_project.uio_out[7:0]
@200
-Output Pins
@22
tb.user_project.uo_out[7:0]
[pattern_trace] 1
[pattern_trace] 0
"""


# The smoke test is a plain template rather than an f-string: it is full
# of braces and format specifiers of its own. Placeholders are @NAME@.
TEST_PY_TEMPLATE = '''"""Self-contained smoke test for the Tiny Tapeout submission.

GENERATED by scripts/gen_tt_submission.py in the neuromorphic-space-soc
repository. Do not edit here; edit the source repository and regenerate.

This file deliberately does NOT import the source repository's golden
model: a submission repository has to be testable on its own, and the
Tiny Tapeout `test` workflow checks out nothing else. What it covers is
the part that a broken port map, a broken pin contract or a broken host
protocol would break, and that a datasheet reader would hit first:

  * reset leaves uio_oe at 0xF0 and every fault pin quiescent
  * the identity register reads back over the serial port
  * a write/read round trip through SCRATCH
  * the read-only rule (a write to VERSION changes nothing)
  * an end-to-end event: weights loaded through the SECDED codec, one
    SPIKE strobed in on the AER pins, the neuron id read off uio[7:4],
    and the pin-side acknowledge retiring the entry

The full regression - bit-exact inference against a Python reference
model, the SECDED syndrome walk, the double-bit E10 substitution, the
scrub loop and the TMR masking proof - lives in the source repository
and runs against this same port list.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

CLK_NS = 20          # 50 MHz, the clock_hz in info.yaml
HALF = 2 * CLK_NS    # serial half period, i.e. SER_SCK = clk/4, the limit

# ui_in bit positions
SER_SCK, SER_CS_N, SER_MOSI = 0, 1, 2
AER_IN_STB, AER_IN_TICK, AER_OUT_ACK, SCRUB_STB = 3, 4, 5, 6
# uo_out bit positions
SER_MISO, BUSY, AER_IN_RDY, AER_OUT_VLD = 0, 1, 2, 3
ERR, SEC, DED, TMR = 4, 5, 6, 7

ADDR_ID = @ADDR_ID@
ADDR_VERSION = @ADDR_VERSION@
ADDR_SCRATCH = @ADDR_SCRATCH@
ADDR_CTRL = @ADDR_CTRL@
ADDR_STATUS = @ADDR_STATUS@
ADDR_CFG_NEUR = @ADDR_CFG_NEUR@
ADDR_CFG_AXON = @ADDR_CFG_AXON@
ADDR_CFG_THRESH = @ADDR_CFG_THRESH@
ADDR_CFG_SYNSHIFT = @ADDR_CFG_SYNSHIFT@
ADDR_CFG_FLAGS = @ADDR_CFG_FLAGS@
ADDR_W_ADDR = @ADDR_W_ADDR@
ADDR_W_DATA_LO = @ADDR_W_DATA_LO@
ADDR_W_DATA_HI = @ADDR_W_DATA_HI@

ID_VALUE = 0x4E505531        # ASCII "NPU1"
CTRL_EN, CTRL_STATE_CLR = 1, 2
ST_BUSY, ST_OUT_EMPTY = 1 << 0, 1 << 2


class Pins:
    """Python-side shadow of the input pins.

    cocotb value deposits are scheduled, not immediate: a
    read-modify-write of dut.ui_in.value with no await in between reads
    the pre-deposit value and silently drops the previous bit write. Keep
    the shadow and only ever write the whole word.
    """

    def __init__(self, dut):
        self.dut = dut
        self.ui = 1 << SER_CS_N      # CS_N idles high, everything else low
        self.uio = 0

    def set_ui(self, bit, val):
        self.ui = (self.ui & ~(1 << bit)) | ((val & 1) << bit)
        self.dut.ui_in.value = self.ui

    def set_uio(self, val):
        self.uio = val & 0x0F
        self.dut.uio_in.value = self.uio


def uo(dut, bit):
    """X-safe single-bit sample of uo_out."""
    s = str(dut.uo_out.value)
    return 1 if s[7 - bit] == "1" else 0


def uio_out_nibble(dut):
    """uio_out[7:4], the emitted neuron id."""
    s = str(dut.uio_out.value)
    return int("".join("1" if c == "1" else "0" for c in s[:4]), 2)


async def spi_byte(p, tx):
    """One mode-0 byte, MSB first. Returns the byte shifted out on MISO.

    MISO is sampled just after the rising edge, which is where a mode-0
    master samples it; the slave changes it on the falling edge.
    """
    rx = 0
    for i in range(7, -1, -1):
        p.set_ui(SER_MOSI, (tx >> i) & 1)
        await Timer(HALF, unit="ns")
        p.set_ui(SER_SCK, 1)
        await Timer(1, unit="ns")
        rx = (rx << 1) | uo(p.dut, SER_MISO)
        await Timer(HALF - 1, unit="ns")
        p.set_ui(SER_SCK, 0)
    return rx


async def frame(p, write, addr, data=0):
    """One 40-bit frame: command byte then 32 data bits.

    The leading and trailing chip-select gaps are one full SER_SCK period
    each. Both are host obligations, not politeness: the frame reset has
    to clear the two-flop synchronizer before the first sampled clock
    edge, and the deselect has to be seen before the next frame starts or
    the bit counter carries over and the next frame decodes at the wrong
    offset.
    """
    p.set_ui(SER_CS_N, 0)
    await Timer(2 * HALF, unit="ns")
    await spi_byte(p, ((1 if write else 0) << 7) | ((addr >> 2) & 0x7F))
    out = 0
    for shift in (24, 16, 8, 0):
        out = (out << 8) | await spi_byte(p, (data >> shift) & 0xFF)
    await Timer(HALF, unit="ns")
    p.set_ui(SER_CS_N, 1)
    await Timer(2 * HALF, unit="ns")
    return out


async def rd(p, addr):
    return await frame(p, False, addr)


async def wr(p, addr, data):
    await frame(p, True, addr, data)


async def reset(dut):
    """Bring the DUT up. Returns the pin shadow used by every helper."""
    p = Pins(dut)
    cocotb.start_soon(Clock(dut.clk, CLK_NS, unit="ns").start())
    dut.ena.value = 1
    dut.ui_in.value = p.ui
    dut.uio_in.value = p.uio
    dut.rst_n.value = 0
    for _ in range(6):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    for _ in range(6):
        await RisingEdge(dut.clk)
    return p


@cocotb.test()
async def test_reset_state(dut):
    """After reset the direction word is fixed and no pin is asserted."""
    p = await reset(dut)

    assert int(dut.uio_oe.value) == 0xF0, (
        "uio_oe must be 0xF0 (uio[3:0] in, uio[7:4] out), got "
        + str(dut.uio_oe.value)
    )
    for name, bit in (("BUSY", BUSY), ("AER_OUT_VLD", AER_OUT_VLD),
                      ("ERR", ERR), ("SEC", SEC), ("DED", DED), ("TMR", TMR)):
        assert uo(dut, bit) == 0, name + " asserted after reset"
    assert uo(dut, AER_IN_RDY) == 1, "input queue not ready after reset"
    assert p.ui & (1 << SER_CS_N), "the testbench must idle CS_N high"


@cocotb.test()
async def test_identity(dut):
    """The identity register is the first thing a bench reads."""
    p = await reset(dut)
    got = await rd(p, ADDR_ID)
    assert got == ID_VALUE, "ID: expected %#010x, got %#010x" % (ID_VALUE, got)


@cocotb.test()
async def test_scratch_round_trip(dut):
    """Write and read back, which exercises both frame directions."""
    p = await reset(dut)
    for value in (0xA5A5_5A5A, 0x0000_0001, 0xFFFF_FFFF, 0x0000_0000):
        await wr(p, ADDR_SCRATCH, value)
        got = await rd(p, ADDR_SCRATCH)
        assert got == value, (
            "SCRATCH: wrote %#010x, read %#010x" % (value, got)
        )


@cocotb.test()
async def test_read_only_register_rejects_writes(dut):
    """A write to a read-only register must not change it."""
    p = await reset(dut)
    before = await rd(p, ADDR_VERSION)
    await wr(p, ADDR_VERSION, 0xDEAD_BEEF)
    after = await rd(p, ADDR_VERSION)
    assert after == before, (
        "VERSION changed from %#010x to %#010x on a write" % (before, after)
    )


@cocotb.test()
async def test_spike_in_and_out_on_the_pins(dut):
    """One event, end to end, without touching the serial event queues.

    Weights go in through the SECDED encoder, the SPIKE is strobed in on
    the AER pins, the emitted neuron id is read off uio[7:4], and the
    pin-side acknowledge retires it. That is the whole pin contract in
    one test.
    """
    p = await reset(dut)

    # Follow the elaborated geometry rather than assuming it.
    n_neurons = await rd(p, ADDR_CFG_NEUR)
    n_axons = await rd(p, ADDR_CFG_AXON)
    assert 4 <= n_neurons <= 16 and 4 <= n_axons <= 16, (
        "implausible geometry read back: %d neurons, %d axons"
        % (n_neurons, n_axons)
    )

    await wr(p, ADDR_CTRL, CTRL_STATE_CLR)
    for _ in range(4):
        if (await rd(p, ADDR_STATUS)) & ST_BUSY == 0:
            break
    else:
        raise AssertionError("STATE_CLR never completed")

    await wr(p, ADDR_CFG_THRESH, 1)
    await wr(p, ADDR_CFG_SYNSHIFT, 0)
    await wr(p, ADDR_CFG_FLAGS, 0)

    # Only axon 1 drives neuron 2, and it drives it over threshold.
    # Weights are axon-major, 16 four-bit weights per 64-bit word, weight
    # k of a word at bits [4k+3:4k].
    flat = [0] * (n_axons * n_neurons)
    flat[1 * n_neurons + 2] = 7
    await wr(p, ADDR_W_ADDR, 0)
    for base in range(0, len(flat), 16):
        word = 0
        for k, weight in enumerate(flat[base:base + 16]):
            word |= (weight & 0xF) << (4 * k)
        await wr(p, ADDR_W_DATA_LO, word & 0xFFFFFFFF)
        await wr(p, ADDR_W_DATA_HI, (word >> 32) & 0xFFFFFFFF)

    await wr(p, ADDR_CTRL, CTRL_EN)
    assert uo(dut, AER_IN_RDY) == 1, "input queue not ready before the spike"

    p.set_uio(1)                 # axon id 1
    p.set_ui(AER_IN_TICK, 0)     # SPIKE, not TICK
    for _ in range(4):
        await RisingEdge(dut.clk)
    p.set_ui(AER_IN_STB, 1)
    for _ in range(4):
        await RisingEdge(dut.clk)
    p.set_ui(AER_IN_STB, 0)

    for _ in range(200):
        await RisingEdge(dut.clk)
        if uo(dut, AER_OUT_VLD):
            break
    else:
        raise AssertionError("AER_OUT_VLD never asserted after a SPIKE")
    assert uio_out_nibble(dut) == 2, (
        "AER_OUT_ID must carry neuron id 2, got %d" % uio_out_nibble(dut)
    )

    p.set_ui(AER_OUT_ACK, 1)
    for _ in range(6):
        await RisingEdge(dut.clk)
    p.set_ui(AER_OUT_ACK, 0)
    for _ in range(6):
        await RisingEdge(dut.clk)
    assert uo(dut, AER_OUT_VLD) == 0, "the pin acknowledge must retire the event"
    assert (await rd(p, ADDR_STATUS)) & ST_OUT_EMPTY, "output queue not empty"

    # Nothing in this test should have tripped a fault pin.
    for name, bit in (("ERR", ERR), ("SEC", SEC), ("DED", DED), ("TMR", TMR)):
        assert uo(dut, bit) == 0, name + " asserted during a clean run"
'''

TEST_PY_ADDRESSES = [
    "ID", "VERSION", "SCRATCH", "CTRL", "STATUS", "CFG_NEUR", "CFG_AXON",
    "CFG_THRESH", "CFG_SYNSHIFT", "CFG_FLAGS", "W_ADDR", "W_DATA_LO",
    "W_DATA_HI",
]


def test_py(addr) -> str:
    text = TEST_PY_TEMPLATE
    for name in TEST_PY_ADDRESSES:
        text = text.replace(f"@ADDR_{name}@", f"0x{addr[name]:03X}")
    leftover = re.findall(r"@[A-Z_]+@", text)
    if leftover:
        raise SystemExit(f"unsubstituted placeholder in test.py: {leftover}")
    return text


# =====================================================================
# Assembly
# =====================================================================


def _load_regmap():
    sw = str(ROOT / "sw")
    if sw not in sys.path:
        sys.path.insert(0, sw)
    try:
        from golden.regmap_gen import ACCESS, ADDR  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment problem
        raise SystemExit(
            f"cannot import sw/golden/regmap_gen.py ({exc}); run "
            f"regmap/generate.py first"
        )
    return ADDR, ACCESS


def build() -> "dict[str, bytes]":
    """Return the whole submission tree as {relative path: bytes}."""
    addr, access = _load_regmap()
    files: "dict[str, bytes]" = {}

    for path, text in VERBATIM.items():
        files[path] = text.encode()

    files[".gitignore"] = (GITIGNORE_UPSTREAM + GITIGNORE_EXTRA).encode()
    files["test/README.md"] = (TEST_README_UPSTREAM + TEST_README_EXTRA).encode()
    files["README.md"] = readme_md().encode()
    files["LICENSE.PENDING.md"] = license_pending_md().encode()
    files["info.yaml"] = info_yaml().encode()
    files["docs/info.md"] = info_md(addr, access).encode()
    files["test/Makefile"] = test_makefile().encode()
    files["test/tb.v"] = test_tb_v().encode()
    files["test/tb.gtkw"] = test_gtkw().encode()
    files["test/test.py"] = test_py(addr).encode()

    if CONFIG_OVERRIDES:
        cfg = VERBATIM["src/config.json"].rstrip().rstrip("}").rstrip()
        extra = ",\n".join(
            f'  "{k}": {v!r}'.replace("'", '"') for k, v in CONFIG_OVERRIDES.items()
        )
        files["src/config.json"] = (
            cfg
            + ",\n\n"
            + "  \"//\": \"Added by scripts/gen_tt_submission.py:\",\n"
            + extra
            + "\n}\n"
        ).encode()

    for name in RTL_SOURCES + RTL_INCLUDES:
        src = ROOT / "hw" / "rtl" / name
        if not src.is_file():
            raise SystemExit(f"missing RTL source: {src}")
        files[f"src/{name}"] = src.read_bytes()

    manifest = "".join(
        f"{hashlib.sha256(files[p]).hexdigest()}  {p}\n" for p in sorted(files)
    )
    files["MANIFEST.sha256"] = manifest.encode()
    return files


def write(files, target: Path) -> int:
    """Write the tree, removing generated files that are no longer produced."""
    known = set(files)
    if target.exists():
        for existing in sorted(target.rglob("*")):
            if existing.is_file():
                rel = existing.relative_to(target).as_posix()
                if rel not in known and is_generated(rel):
                    existing.unlink()
    written = 0
    for rel, data in sorted(files.items()):
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or dest.read_bytes() != data:
            dest.write_bytes(data)
            written += 1
    for script in (".devcontainer/copy_tt_support_tools.sh",):
        (target / script).chmod(0o755)
    return written


# Local artifacts of the Tiny Tapeout tooling and of a local flow run.
# Every one of these is in the generated tt/.gitignore; they are listed
# again here so that neither --check nor the write path ever touches
# them. In particular "tt" is the directory that the dev container and
# the GDS action copy tt-support-tools into, which sits at tt/tt.
ARTIFACT_DIRS = frozenset(
    ("runs", "sim_build", "tt", "__pycache__", "tt_submission", "output",
     ".pytest_cache", ".git")
)
ARTIFACT_FILES = frozenset(
    ("src/user_config.json", "src/config_merged.json",
     "test/gate_level_netlist.v", "test/results.xml", "commit_id.json")
)
ARTIFACT_SUFFIXES = (".fst", ".vcd", ".fst.hier", ".pyc")


def is_generated(rel: str) -> bool:
    """True for a tree-relative path this generator owns.

    False for a developer's local run artifacts, so that a --check run
    after `tt_tool.py --create-user-config`, a cocotb run or a LibreLane
    harden does not report drift, and so that the write path never
    deletes them.

    The argument is relative to the submission root on purpose. Taking an
    absolute path here would be a silent trap: the submission root is
    itself called "tt", so every absolute path inside it contains the
    artifact component "tt" and the whole guard would answer False.
    """
    parts = rel.split("/")
    if ARTIFACT_DIRS.intersection(parts[:-1]):
        return False
    if rel in ARTIFACT_FILES:
        return False
    if parts[-1].endswith(ARTIFACT_SUFFIXES):
        return False
    return True


def check(files, target: Path) -> "list[str]":
    """Return a list of human-readable drift descriptions; empty means clean."""
    problems = []
    if not target.exists():
        return [f"{target} does not exist; run scripts/gen_tt_submission.py"]
    for rel, data in sorted(files.items()):
        dest = target / rel
        if not dest.is_file():
            problems.append(f"missing: tt/{rel}")
        elif dest.read_bytes() != data:
            problems.append(f"differs from the generator: tt/{rel}")
    for existing in sorted(target.rglob("*")):
        if not existing.is_file():
            continue
        rel = existing.relative_to(target).as_posix()
        if rel not in files and is_generated(rel):
            problems.append(f"not produced by the generator: tt/{rel}")
    return problems


def diff_template() -> int:
    """Re-fetch the upstream template and check the verbatim claim."""
    import shutil
    import subprocess
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="tt-template-"))
    try:
        clone = tmp / "template"
        subprocess.run(
            ["git", "clone", "--quiet", "--depth", "1", "--branch", TEMPLATE_REF,
             TEMPLATE_URL, str(clone)],
            check=True,
        )
        head = subprocess.run(
            ["git", "-C", str(clone), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        print(f"upstream {TEMPLATE_URL} {TEMPLATE_REF} = {head}")
        if head != TEMPLATE_COMMIT:
            print(f"NOTE: recorded TEMPLATE_COMMIT is {TEMPLATE_COMMIT}")
        bad = 0
        for rel, text in sorted(VERBATIM.items()):
            up = clone / rel
            if not up.is_file():
                print(f"GONE      {rel}: no longer in the template")
                bad += 1
                continue
            if up.read_bytes() != text.encode():
                print(f"CHANGED   {rel}")
                bad += 1
            else:
                print(f"verbatim  {rel}")
        # .gitignore is the one derived file with a byte-exact upstream
        # base (the generator only appends to it), so drift in it is
        # detectable the same way. test/Makefile, test/tb.v and
        # test/tb.gtkw are rewritten, so only a human re-port can tell
        # whether upstream changed something that matters.
        for rel, base in ((".gitignore", GITIGNORE_UPSTREAM),
                          ("test/README.md", TEST_README_UPSTREAM)):
            up = clone / rel
            if not up.is_file():
                print(f"GONE      {rel}: no longer in the template")
                bad += 1
                continue
            same = up.read_bytes() == base.encode()
            print(f"{'unchanged' if same else 'CHANGED':9} {rel} "
                  f"(upstream base of a derived file)")
            bad += 0 if same else 1
        print("\nRewritten from the template, re-port by hand if upstream "
              "changed them:\n  test/Makefile, test/tb.v, test/tb.gtkw, "
              "README.md, docs/info.md, info.yaml")
        return 1 if bad else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "target", nargs="?", default=str(TARGET),
        help="submission tree to write (default: tt/)",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="report drift and exit non-zero; write nothing",
    )
    parser.add_argument(
        "--diff-template", action="store_true",
        help="re-fetch the upstream template and verify the verbatim files "
             "(needs network)",
    )
    args = parser.parse_args()

    if args.diff_template:
        return diff_template()

    target = Path(args.target).resolve()
    files = build()

    if args.check:
        problems = check(files, target)
        if problems:
            print("Tiny Tapeout submission tree is out of date:")
            for problem in problems:
                print(f"  {problem}")
            print("Run: python3 scripts/gen_tt_submission.py")
            return 1
        print(f"tt/ matches the generator ({len(files)} files)")
        return 0

    written = write(files, target)
    print(f"{len(files)} files in {target} ({written} written or updated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
