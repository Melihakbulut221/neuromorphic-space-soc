# Sample testbench for a Tiny Tapeout project

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
