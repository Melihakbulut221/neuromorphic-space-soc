# ECP5 / ULX3S fit-and-timing check

This directory holds a second, independent implementation path for the
same RTL that goes to the ASIC: yosys `synth_ecp5` plus nextpnr-ecp5 plus
ecppack, targeting a Lattice ECP5 in the CABGA381 package (the ULX3S
board part). It is a portability and timing probe. It is not a board
support package and there is no bring-up design here.

Everything below is measured output from the flow in this directory
unless it is tagged as an estimate.

**Re-measured 2026-08-29 at commit `0448282`.** Every resource and
timing table in this file previously described the pre-configuration-TMR
netlist of 2026-08-25 (1045 `TRELLIS_FF`, 3449 `TRELLIS_COMB`,
47.87 MHz). Three rounds of hardening have landed since — the
configuration TMR fix (`e45d52d`), the `lif_core` memory ECC, and the
AER pointer TMR (`c5a5a6e`) — so the whole flow was re-run rather than
adjusted. The superseded figures are kept beside the new ones. Three
conclusions this file drew have changed sign and are called out where
they appear: **the design is no longer DSP-free**, **speed grade 8 no
longer reaches 50 MHz**, and **`make report` now under-reports**.

## What was run

    cd hw/fpga
    make                       # 85F, speed grade 6, 25 MHz -> bitstream
    make FREQ=50               # same, 50 MHz constraint
    make fit                   # 85F, 45F and 12F, print achieved Fmax
    make report                # resources and timing from the last run

Toolchain (fact, recorded from the run):

  - yosys 0.67+146 (git sha1 468ba27d9-dirty)
  - nextpnr-0.10-111-g2fb1d198
  - Project Trellis ecppack 1.4-79-g56bb170, from the same oss-cad-suite
    build

All three re-confirmed on 2026-08-29; the toolchain did not move between
the two campaigns recorded below, so every difference in the tables is
the design.

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
no inferred latches (yosys reports "No latch inferred" 14 times and
reports an inferred latch zero times), and `ecppack --compress` produces
a **352 KB** `.bit` (360,776 bytes; was 331 KB on 2026-08-25).

### Resource usage

Post `synth_ecp5`, before packing. **These are design totals**, summed
over the top module and the fifteen modules that now survive it —
three `pilot_cfg_bank` instances and twelve `aer_ptr_bank` instances,
all carrying `keep_hierarchy` so that synthesis cannot merge the
redundancy away:

| cell        | top module | in 3 `pilot_cfg_bank` | in 12 `aer_ptr_bank` | **design total** | 2026-08-25 |
|-------------|-----------:|----------------------:|---------------------:|-----------------:|-----------:|
| LUT4        |       4923 |                   474 |                   60 |         **5457** |       3191 |
| PFUMX       |       1078 |                   139 |                    0 |         **1217** |        741 |
| L6MUX21     |        397 |                    84 |                    0 |          **481** |        332 |
| CCU2C       |        126 |                     0 |                    0 |          **126** |         93 |
| TRELLIS_FF  |       1074 |                   165 |                   36 |         **1275** |       1045 |
| MULT18X18D  |          1 |                     0 |                    0 |            **1** |          0 |

**`make report` under-reports, and this is a trap worth naming.** Its
`awk` reads the `=== tt_um_melihakbulut_nssoc ===` stat block, which is
yosys's *local* count for the top module and therefore excludes every
kept submodule. It prints 1074 flip-flops where the design has 1275 —
and the 201 it drops are exactly the redundant banks, the thing this
directory exists to check is present. Read the "top module" column above
as what `make report` prints and the "design total" column as the truth;
nextpnr's post-packing `TRELLIS_FF` line agrees with the total.

After nextpnr packing, the same design as the fitter sees it:

| resource     | used | 85F    | 45F    | 12F    | 2026-08-25 (used) |
|--------------|------|--------|--------|--------|------------------:|
| TRELLIS_COMB | 5811 | 6%     | 13%    | 23%    |              3449 |
| TRELLIS_FF   | 1275 | 1%     | 2%     | 5%     |              1045 |
| TRELLIS_IO   |   43 | 11%    | 17%    | 21%    |                43 |
| DCCA         |    1 | 1%     | 1%     | 1%     |                 1 |
| DP16KD (BRAM)|    0 | 0%     | 0%     | 0%     |                 0 |
| MULT18X18D   |    1 | 0%     | 1%     | 3%     |                 0 |

Zero BRAM still. **Zero DSP is no longer true, and the "no hard-macro
dependence" claim below is narrowed accordingly.** One `MULT18X18D` is
inferred. It is not a design decision and it was not noticed when the
RTL that causes it landed:

    hw/rtl/lif_core.v:822
        smem[st_addr * ST_C +: ST_C] <= st_wr_chk;

`ST_C` is a localparam, but yosys emits a `$mul` for the variable part
select's base address anyway, and `synth_ecp5` maps it through
`mul2dsp.v` and `lattice/dsp_map_18x18.v` onto a hard multiplier. The
instance is `u_pilot.u_lif.st_addr_MULT18X18D_A2` and its `src`
attribute in `build/tt_um_melihakbulut_nssoc.json` names all three
files, which is how this was traced rather than guessed **[fact]**.
`smem` is the neuron-state ECC check field added by the memory
hardening, so the DSP arrived with that wave. It is on the critical
path — see below. On the ASIC flow the same expression is an address
decode and costs no macro, so this is an FPGA-mapping artifact rather
than an RTL defect; but it is a hard-macro dependence in this flow and
the previous sentence claiming there were none was written before it
existed. **[estimate on the ASIC side; fact on the ECP5 side]**

The other cost is unchanged: `lif_core`'s `wmem`, `vmem` and `rmem`
arrays and `aer_fifo`'s `mem` are all mapped to registers plus
multiplexer trees (yosys emits "Replacing memory ... with list of
registers" for each of the four, and for no others — `smem` and `wchk`
are flat vectors, not arrays). That is where the 1217 PFUMX and 481
L6MUX21 come from, and it is still the reason the critical path looks
the way it does.

### Fits on every ULX3S device option

The same LPF and the same netlist route on all three, at speed grade 6,
package CABGA381:

| device | achieved Fmax | 25 MHz | 50 MHz | 2026-08-25 Fmax |
|--------|---------------|--------|--------|----------------:|
| 85F    | 28.06 MHz     | PASS   | FAIL   |       47.87 MHz |
| 45F    | 26.54 MHz     | PASS   | FAIL   |       47.85 MHz |
| 12F    | 26.94 MHz     | PASS   | FAIL   |       46.80 MHz |

The achieved figure is the same whether the run is constrained at 25 MHz
or at 50 MHz — `make fit FREQ=25` and `make fit FREQ=50` produce
identical numbers on all three parts, which is why one column serves
both.

25 MHz still passes on all three, but the margin is now roughly **1.1x**,
not the 1.9x this file used to record. That is the number that moved
most, and it moved because three rounds of redundancy hardening landed
between the two measurements. There is still no device sizing problem:
the 12F is 23% full on `TRELLIS_COMB`, up from 14%.

### 50 MHz is missed by roughly a factor of two

The ROADMAP system-clock target of 50 MHz is not met on a speed grade 6
part, and the shortfall is far larger than the 4-6% this file used to
report. This is not seed noise. Five 85F placements, `FREQ=50`,
`ALLOW_FAIL=1`:

| seed | Fmax      | 2026-08-25 |
|------|-----------|-----------:|
| 0    | 28.06 MHz |  47.87 MHz |
| 1    | 27.75 MHz |  47.09 MHz |
| 2    | 26.81 MHz |  47.70 MHz |
| 3    | 27.71 MHz |  48.33 MHz |
| 4    | 26.50 MHz |  47.90 MHz |

Seed spread is 1.56 MHz, 5.7% of the 27.37 MHz mean — wider than the
1.24 MHz of the old sweep, and nowhere near the 19.81 MHz that separates
the two campaigns at seed 0. The gap is the design, not the placer.

The exact failure text from nextpnr is:

    Warning: Max frequency for clock '$glbnet$clk$TRELLIS_IO_IN': 28.06 MHz (FAIL at 50.00 MHz)

The critical path is **35.64 ns, 12.01 ns of logic and 23.63 ns of
routing** (was 20.89 ns, 7.29 + 13.60). It **no longer lives entirely
inside `u_pilot.u_lif`**: it starts at the top-level `aer_in_rdy`
flip-flop, crosses into the neuron core through the `wmem` read
multiplexer chain (the PFUMX/L6MUX21 trees noted above), passes through
`u_pilot.u_lif.st_addr_MULT18X18D_A2` — the inferred DSP — and ends at
`u_pilot.u_lif.smem_TRELLIS_FF_Q_4`, a neuron-state check-field
flip-flop. Both endpoints are structures the memory hardening created.
Routing still dominates at 66% of the path.

Two things follow, and the first of them has reversed. **First (fact):
speed grade 8 no longer rescues the design.** The same netlist on an -8
85F reaches **35.11 MHz and still FAILS at 50 MHz**. This file
previously recorded 60.05 MHz and a pass on that part; that was the
2026-08-25 netlist and it is superseded. There is no speed grade in this
package that closes 50 MHz for the current design. Second (estimate,
unchanged): because the bottleneck is still a mux tree that exists only
because the arrays did not map to block RAM, the 50 MHz shortfall
remains an artifact of the FPGA mapping and says little about whether
the ASIC closes at 50 MHz — the ASIC flow's own slow-corner numbers are
in `docs/22-reharden-wave5.md` and are the ones to read for that
question. An FPGA build that wanted 50 MHz on a -6 part would map `wmem`
to a DP16KD and add a pipeline stage on the read; neither change belongs
in the ASIC RTL.

Conservative reading, revised: 25 MHz is still proven on
hardware-realistic parts, but with about 12% margin rather than 90%. Any
further growth in the neuron core should expect to re-open even that,
and this table should be re-run — not extrapolated — after the next
hardening wave.

## What this proves, and what it does not

Proves:

  - **Portability.** The RTL is standards-clean enough that a second,
    completely independent implementation stack takes it from source to
    bitstream with zero source changes and zero errors. The ASIC flow is
    no longer the only tool that has ever read this code.
  - **Near-total independence from vendor hard macros.** Zero BRAM, one
    clock, 43 IO. *Narrowed 2026-08-29:* this line said "zero DSP" and
    that is no longer true — one `MULT18X18D` is now inferred from
    `hw/rtl/lif_core.v:822`, and it sits on the critical path. See the
    resource-usage section. The claim that survives is that no *storage*
    macro is required and that the mapping is not locked to a vendor
    primitive: the DSP is yosys choosing a hard multiplier for an address
    computation, not the design asking for one. Checked rather than
    assumed — `synth_ecp5 -nodsp` on the same sources produces **zero**
    `MULT18X18D` and the top module's LUT4 count *falls* from 4923 to
    4658 **[fact, 2026-08-29]**. The unqualified "zero DSP" must not be
    quoted, and `-nodsp` is worth considering as the default for this
    probe.
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
    interconnect model. 28.1 MHz on a -6 ECP5 is not a number that
    transfers (47.9 MHz when this line was written; the point is
    unchanged and the arrow only got longer).
  - **Area or power on the target process.**
  - **That the mitigation logic is present in silicon.** See below.

## Finding: the configuration TMR was optimised away (repaired)

**Status: fixed in commit `e45d52d`.** The finding below is what this
directory's netlist check turned up and it was correct; the defect no
longer exists. Each replica is now a `keep_hierarchy` `pilot_cfg_bank`
instance carrying a per-replica storage polarity — plain Verilog, so it
does not depend on one tool honouring one attribute. Mapped flip-flops go
1,045 to 1,155 in this ECP5 flow as well as in the ASIC flow,
`synth_ecp5` reports three separate `pilot_cfg_bank` modules at 55 flops
each, and `sw/tests/test_synthesis_guards.py` counts them in both flows
and fails on three separate mutations of the fix. Cost on ECP5 at the
time: Fmax 47.87 to 46.45 MHz, still passing 25 MHz with margin.

**Still holding on 2026-08-29, and the same technique now covers a
second structure [fact, re-measured].** `synth_ecp5` reports three
`pilot_cfg_bank` modules at **55 flip-flops each** and twelve
`aer_ptr_bank` modules at **3 flip-flops each** — 165 + 36 = 201 flops
of redundancy that no structural hash merged, out of 1,275 in the
design. The AER pointer TMR of `c5a5a6e` uses the same construction
(one module instance per replica, per-replica storage polarity,
`keep_hierarchy`) for the same reason, and this flow confirms it
survives a second, independent synthesiser. The per-module counts are in
the resource table above; note that `make report` does **not** show them,
for the reason given there.

The original finding, retained because the reasoning is what matters:

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

This directory did not fix it; `hw/rtl` is not owned here. Flagging it was
the point. The last sentence of the original note — that the fix "needs to
be applied and then verified by counting flops in the netlist, not
assumed" — is exactly what was done, and it turned out to matter: the
obvious fix, a `(* keep *)` attribute on the three replicas, does NOT
work. It preserves the names while the flip-flops stay merged, filling the
netlist with `assign cfg_b[3] = cfg_a[3]` aliases at an unchanged flop
count. A previous check in `docs/15` section 4.2 had read that unchanged
count as proof that no merge occurred, which is how the defect survived
review.

## Files

| file          | what it is |
|---------------|------------|
| `Makefile`    | the flow, exactly as run; rootless tool discovery |
| `ulx3s.lpf`   | pin map for the fit check only, not for bring-up |
| `README.md`   | this file |
| `build/`      | generated, gitignored |
