# ECP5 / ULX3S fit-and-timing check

This directory holds a second, independent implementation path for the
same RTL that goes to the ASIC: yosys `synth_ecp5` plus nextpnr-ecp5 plus
ecppack, targeting a Lattice ECP5 in the CABGA381 package (the ULX3S
board part). It is a portability and timing probe. It is not a board
support package and there is no bring-up design here.

Everything below is measured output from the flow in this directory
unless it is tagged as an estimate.

## What was run

    cd hw/fpga
    make                       # 85F, speed grade 6, 25 MHz -> bitstream
    make FREQ=50               # same, 50 MHz constraint
    make fit                   # 85F, 45F and 12F, print achieved Fmax
    make report                # resources and timing from the last run

Toolchain (fact, recorded from the run):

  - yosys 0.67+146 (git sha1 468ba27d9)
  - nextpnr-0.10-111-g2fb1d198
  - ecppack from the same oss-cad-suite build

The Makefile finds these the way `hw/tb/Makefile` finds cocotb: check
PATH first, and if the tools are not all there, re-invoke make once with a
discovered `oss-cad-suite/bin` prepended. Nothing is installed and nothing
outside `build/` is written. Override with `OSS_CAD_BIN=`.

Source set is exactly what the ASIC top pulls in:
`tt_um_melihakbulut_nssoc.v`, `pilot_top.v`, `lif_core.v`, `aer_fifo.v`,
`tmr_voter.v`, `secded_enc.v`, `secded_dec.v`, and `npu_regs.vh` via
`-I ../rtl`. `scrub.v` and `npu_regbank.v` are not included because
`pilot_top.v` does not instantiate them. `FORMAL` is left undefined so the
`formal/*_props.v` includes stay out. Elaboration parameters are the
defaults, 8 neurons by 8 axons, EVQ depth 4/4, CNT_W 8. `read_verilog`
runs in its default Verilog-2005 mode; passing `-sv` was tried and
produced identical cell counts, so the sources need no SystemVerilog.

`ulx3s.lpf` is a pin map written for this check only; its header explains
the two places it is deliberately wrong for real hardware.

## Result: the flow completes

Synthesis, place, route and bitstream generation all succeed. No errors,
no inferred latches (yosys reports "No latch inferred" for every candidate
signal), and `ecppack --compress` produces a 331 KB `.bit`.

### Resource usage

Post `synth_ecp5`, before packing:

| cell        | count |
|-------------|-------|
| LUT4        |  3191 |
| PFUMX       |   741 |
| L6MUX21     |   332 |
| CCU2C       |    93 |
| TRELLIS_FF  |  1045 |

After nextpnr packing, the same design as the fitter sees it:

| resource     | used | 85F    | 45F    | 12F    |
|--------------|------|--------|--------|--------|
| TRELLIS_COMB | 3449 | 4%     | 7%     | 14%    |
| TRELLIS_FF   | 1045 | 1%     | 2%     | 4%     |
| TRELLIS_IO   |   43 | 11%    | 17%    | 21%    |
| DCCA         |    1 | 1%     | 1%     | 1%     |
| DP16KD (BRAM)|    0 | 0%     | 0%     | 0%     |
| MULT18X18D   |    0 | 0%     | 0%     | 0%     |

Zero BRAM and zero DSP. The design is pure logic and flops, which is what
a rad-hard ASIC target wants: nothing here is locked to a vendor hard
macro. The cost is that `lif_core`'s `wmem`, `vmem` and `rmem` arrays and
`aer_fifo`'s `mem` are all mapped to registers plus multiplexer trees
(yosys emits "Replacing memory ... with list of registers" for each of the
four). That is where the 741 PFUMX and 332 L6MUX21 come from, and it is
the reason the critical path looks the way it does.

### Fits on every ULX3S device option

The same LPF and the same netlist route on all three, at speed grade 6,
package CABGA381:

| device | achieved Fmax | 25 MHz | 50 MHz |
|--------|---------------|--------|--------|
| 85F    | 47.87 MHz     | PASS   | FAIL   |
| 45F    | 47.85 MHz     | PASS   | FAIL   |
| 12F    | 46.80 MHz     | PASS   | FAIL   |

25 MHz passes with roughly 1.9x margin on all three. There is no device
sizing problem: even the 12F is 14% full.

### 50 MHz is missed by 4 to 6 percent

The ROADMAP system-clock target of 50 MHz is not met on a speed grade 6
part. This is not seed noise. Five 85F placements:

| seed | Fmax     |
|------|----------|
| 0    | 47.87 MHz|
| 1    | 47.09 MHz|
| 2    | 47.70 MHz|
| 3    | 48.33 MHz|
| 4    | 47.90 MHz|

The exact failure text from nextpnr is:

    ERROR: Max frequency for clock '$glbnet$clk$TRELLIS_IO_IN': 47.87 MHz (FAIL at 50.00 MHz)

The critical path is 20.89 ns, 7.29 ns of logic and 13.60 ns of routing,
and it lives entirely inside `u_pilot.u_lif`: a state register out through
the register-file read multiplexer chain (the PFUMX/L6MUX21 trees noted
above), through the membrane-compare carry chain, and into the `vmem`
write path. Routing dominates, and it is the register-file-as-LUTs
structure that spreads the logic out, not the ASIC-relevant arithmetic.

Two things follow. First (fact): on a speed grade 8 ECP5, the same netlist
reaches 60.05 MHz and passes at 50 MHz. Second (estimate): because the
bottleneck is a mux tree that exists only because the arrays did not map
to block RAM, the 50 MHz shortfall is an artifact of the FPGA mapping and
says little about whether the ASIC closes at 50 MHz. An FPGA build that
wanted 50 MHz on a -6 part would map `wmem` to a DP16KD and add a pipeline
stage on the read; neither change belongs in the ASIC RTL.

Conservative reading: 25 MHz is proven on hardware-realistic parts,
50 MHz is not, on this board class.

## What this proves, and what it does not

Proves:

  - **Portability.** The RTL is standards-clean enough that a second,
    completely independent implementation stack takes it from source to
    bitstream with zero source changes and zero errors. The ASIC flow is
    no longer the only tool that has ever read this code.
  - **No hard-macro dependence.** Zero BRAM, zero DSP, one clock, 43 IO.
  - **A hardware platform exists for the fault-injection campaign.** The
    campaign in `hw/tb/test_fi_campaign.py` currently runs in simulation.
    A routed ECP5 bitstream is a place to run the same stimulus at clock
    speed, which buys orders of magnitude more injected events per hour
    than Icarus does. That is the real reason to keep this directory.

Does not prove, and must not be quoted as proving:

  - **Anything about radiation behaviour.** An ECP5 fit says nothing about
    TID, SEL, SEU cross-section or LET threshold on the target process.
    Worse, an ECP5 is an SRAM-configured FPGA: its own configuration
    memory upsets, and an upset there is indistinguishable from a design
    upset unless the FPGA configuration is scrubbed independently. Beam
    time on this board would measure the ECP5, not the design.
  - **ASIC timing.** Different library, different corners, different
    interconnect model. 47.9 MHz on a -6 ECP5 is not a number that
    transfers.
  - **Area or power on the target process.**
  - **That the mitigation logic is present in silicon.** See below.

## Finding: the configuration TMR is optimised away

Checking the ECP5 netlist against the RTL turned up something that is not
an FPGA problem at all.

`pilot_top.v` declares three 55-bit configuration replicas, `cfg_a`,
`cfg_b` and `cfg_c` (line 661), written identically and voted by
`u_cfg_vote`. They have identical D inputs, identical clock and identical
reset, so yosys's `opt` pass merges them into one 55-bit bank. Measured
(fact): after `proc; opt`, `cfg_a`, `cfg_b` and `cfg_c` alias to the same
55 net bits rather than 165 distinct ones. Running `opt_merge` alone does
not do it; the full `opt` does. `synth_ecp5` runs `opt`.

This is not confined to the FPGA flow. The already-committed ASIC netlist
at
`hw/openlane/pilot_sky130/runs/sky-01-synth/06-yosys-synthesis/tt_um_melihakbulut_nssoc.nl.v`
contains 1045 flip-flops, the same count as the ECP5 build, and mentions
only `cfg_a[54:0]`; `cfg_b` and `cfg_c` do not appear. The voter survives
because the fault-injection XORs `inj_a`/`inj_b`/`inj_c` differ and keep
`cfg_mismatch` live, so the register-level fault-injection tests still see
a mismatch signal working, but all three voter inputs come from one
physical register bank. Against a real upset in that bank, the voter votes
three copies of the same wrong value.

This directory does not fix that; `hw/rtl` is not owned here. Flagging it
is the point. The usual fix is a synthesis attribute on the three
replicas, and it needs to be applied and then verified by counting flops
in the netlist, not assumed.

## Files

| file          | what it is |
|---------------|------------|
| `Makefile`    | the flow, exactly as run; rootless tool discovery |
| `ulx3s.lpf`   | pin map for the fit check only, not for bring-up |
| `README.md`   | this file |
| `build/`      | generated, gitignored |
