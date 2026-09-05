# 44 — Where the margin actually went, and a counter an operator can read

`docs/43-core-hardening.md` closes with two numbers and one admission.

The numbers are section 7.4's: the SECDED register file costs **0.6926 ns
of setup slack at 20 ns** and takes the core from **62.6 MHz to
56.8 MHz**, because "the decoder sits on the register read path and the
register read path feeds the ALU".

The admission is section 10's first bullet, ranked first again in section
12:

> **The correction is invisible outside a simulator.** … In silicon a
> corrected upset and no upset are the same event, so **this design
> cannot tell an operator that it is being hit** … That is the single
> largest gap this document opens.

This document does both. It recovers what can be recovered of the timing
and it routes the correction out to a register software can read. **The
larger of its two results is that the first number was measuring
something else.** Every one of the ten worst setup paths at the slow
corner, in *both* of `docs/43`'s configurations, starts at
`cheriot_enable_i[0]` — a four-bit configuration input that `soc_top.v`
drives with the constant `4'b1010`. A register-file decoder cannot be on
that path; its inputs come from flip-flops and a primary input cannot
reach them. And the 56.8 MHz is not a logic path at all: at 17.62 ns the
binding check in the hardened build is the **asynchronous reset recovery
check on an unbuffered 2,328-fanout net**, identical in the two hardened
builds to four decimal places.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
intended, with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was modified.
Three files in `hw/rtl/` are **read**: `secded_enc.v`, `secded_dec.v` and
`tmr_voter.v`, instantiated in place and not copied. Section 13 lists
every file.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| Was `docs/43` section 7.4's timing cost real? | **The delta is real and the attribution is not.** The path it measured runs from `cheriot_enable_i[0]`, which `soc_top.v` ties to a constant, to `data_req_o`; all ten worst setup paths at the slow corner start there in both builds **[fact]**. The decoder is not on it and cannot be. Section 5.1 |
| Then what is the 62.6 → 56.8 MHz? | **Two different limits, neither of them the codec.** The baseline's 62.6 MHz is set by that same false path. The hardened build's 56.8 MHz is set by the **reset recovery check**: `rst_ni` drives 2,328 flip-flop reset pins through no buffer tree at all, 10.9223 ns of lumped-cap delay, and the two hardened builds report **bit-identical slacks at every probe** — −0.1653, −0.0773, −0.0373 **[fact]**. What the protection cost there is 222 more flip-flops on an unbuffered net, which is a place-and-route obligation and not a logic cost. Section 5.3 |
| So what does the codec actually cost in time? | **2.7928 ns on the register read path at the slow corner**, measured on the register file alone where nothing else can move: arrival at `rdata_a_o` goes from 5.5282 ns unprotected to 8.3210 ns with `docs/43`'s read path **[fact]**. Section 5.4 |
| What was recovered? | **0.2593 ns, 9.3 % of it, for +1,201.5486 um2 on the module** **[fact]**. `FASTCORR` takes the frozen decoder's `data_out` off the read path and XORs the raw word with a mask built from its syndrome instead, skipping a 64-wide OR, an eight-bit subtract and a multiplexer. It is **proved bit-for-bit identical** to the decoder's output over a free codeword, on two engine families. Sections 5.4 and 9.3 |
| Is that all that was available? | **No, and the alternative is priced rather than described.** `SYNPRE` hoists the syndrome's XOR tree to the other side of the read multiplexer and recovers **1.8677 ns, 66.9 %**, for **+31,229.1126 um2** — one parity tree per register, 11.3 % of the unprotected core **[fact]**. It is measured and **not taken**: the SoC's 20 ns target is met with 1.55 ns of margin as built, and eleven per cent of the core is the wrong thing to spend to widen a margin that is not binding. Section 5.5 |
| Why not the classic replay? | **Because Ibex has no input that stalls a mid-flight instruction, and building one is a fork rather than a port.** A replay needs a stall that reaches `ibex_id_stage`'s controller: `ibex_top`, `ibex_core` and `ibex_id_stage`, three files instead of one, in the control path of a CPU this project cannot re-verify. Upstream's own hardened configuration does not replay either — `RegFileECC` raises `alert_major_internal` and does not correct. Section 5.6 |
| Can an operator now see a corrected upset? | **Yes, and the demonstration is a load instruction and not a hierarchical read.** All four of `docs/42`'s `x23` records, replayed against the SoC, end with the golden answer and with **software reading `CNT_RFSEC = 1`** out of BUSSTAT **[fact]**. Section 8.2 |
| What does that cost the pinning story? | **A patch to Ibex — three hunks in one generated file, applied by a script, never committed.** `hw/soc/ext/ibex` is still a pristine checkout and `hw/soc/gen` is still unedited sv2v output; `hw/soc/genp/ibex_top.v` is derived from the second by `hw/soc/flow/ibex_fault_port.py`, whose every anchor is asserted to occur exactly once so a moved pin stops the build instead of patching the wrong place. Section 4 states all of it, including what `docs/43`'s port-list guard had to be weakened to |
| Where does it land? | **BUSSTAT, `0xFF915000`, APB slot `0x015`, fast interrupt line 10** — the slot the frozen map has reserved since `docs/39` for "system-bus error latch and ECC counters". Four saturating counters and four stickies, `docs/41` section 10 item 3's TMRERR among them. Section 6 |
| Measured area | **The shipped core is 316,051.6590 um2, +14.64 % over the 275,682.6198 baseline** **[fact]**, of which the telemetry is +5,172.5520. `soc_busstat` is **7,060.5486 um2**, 2.56 % of the unprotected core. The watchdog's fault line costs nothing measurable: 15,579.7614 against `docs/43`'s 15,695.7318, which is 115.97 um2 in the cheap direction and is mapping noise. Section 7 |
| Did the cycle-count invariant hold? | **Yes, exactly.** 22 checks, fail mask 0, watchdog stage 1 at cycle 174,128, core asleep after **185,443 cycles**, 587 console characters, 0 framing errors — identical to `docs/40`, `docs/41` and `docs/43`. The fault-injection ROM image is still `c48d8d73…` and its clean run is still 18,682 cycles with signature `9c07ef12` **[fact]**. Section 8.1 |
| Is it proved? | 7 formal jobs, 29 tasks, all PASS. The load-bearing new one is **C5**: the fast correction equals the frozen decoder's output for every codeword and every error vector. Section 9.3 |
| Was the campaign re-run, and what was the delta? | **Re-run in full, and the delta is zero at the strongest resolution the harness has: the two 1,400-record files are byte-identical**, `md5 3fe1ed38…`, and the two logs differ in one line — the path **[fact]**. Not "the rates agree", which two records moving in opposite directions would also satisfy: no record moved. Design-weighted SDC **1.3 % ± 0.4** and HANG **0.3 % ± 0.2** with the watchdog held off, 28 of 28 dead machines caught, 0 spurious escalations in 1,228, 190 corrections all ending golden, 0 uncorrectable — every one `docs/43` section 8's own number. Section 9 |
| What is the worst thing this document leaves? | **The whole-core timing instrument cannot resolve the effect it is used to measure.** A source change that is provably off the read path moves the reported slack by up to 0.3988 ns and the same critical path's tail by 1.1526 ns on identical RTL **[fact]**. Section 5.2 says how that was measured; section 10 says what it means for every timing number in `docs/38`, `docs/43` and this document. |

---

## 2. What was built

| File | What it is |
|---|---|
| `hw/soc/rtl/soc_busstat.v` | **BUSSTAT.** Four saturating counters, four stickies, an enable and an interrupt, in the slot the frozen map reserved |
| `hw/soc/flow/ibex_fault_port.py` | The `ibex_top` patch: three hunks, anchored, applied to a generated copy, never committed |
| `hw/soc/rtl/ibex_regfile_secded.v` | `rf_ecc_err_o`; `FASTCORR`, the recovery; `SYNPRE`, the alternative that is measured and declined |
| `hw/soc/rtl/soc_wdog.v`, `soc_gptimer.v` | `tmr_ev_o` — `docs/41` section 10 item 3's fault line, at last |
| `hw/soc/rtl/soc_top.v` | The block, the two fault lines, and fast interrupt line 10 |
| `hw/soc/sta/ibex_tieoffs.sdc` | The SoC's own tie-offs as a case analysis, so a timing number can be about logic that exists |
| `hw/soc/flow/sta_regfile.sh` | The register file's read path timed on its own, which is where the recovery is measurable at all |
| `hw/soc/formal/soc_busstat_props.v`, `.sby` | B1–B6, at two counter widths |
| `hw/soc/formal/regfile_secded_props.v` | **C5**, the equivalence the recovery rests on |
| `hw/soc/tb/cocotb/test_soc_busstat.py` | Ten tests, including the clear-versus-event race and the two reset domains |
| `sw/tests/test_soc_synthesis_guards.py` | The counter census, the connection check, and the patch's own anchor check |
| `hw/soc/tb/sw/soc_timers.h`, `fi_workload.c`, `tb_soc_fi.v` | The software-visible readout, behind a define, so the campaign's image stays byte-identical |

---

## 3. `mtime` is not done, and this is where that is said

`docs/43` section 12 ranks `mtime` second and `docs/41` section 7.4
ranked it first among the things it left unprotected. It is still
unprotected and this document does not touch it.

The reason is that the timing work turned out to be measurement work
first — sections 5.1 to 5.3 are three corrections to how this repository
has been reading its own timing numbers since `docs/38`, and none of them
was visible before the register file made the numbers worth arguing
about. Between finishing that and building the telemetry there was no
room left to protect a 64-bit counter properly, and a half-protected
`mtime` would be worse than an unprotected one because it would look
done.

**It is not started, not partly built, and not in this document's file
list.** Section 11 ranks it first.

---

## 4. The route out of the core, and what it costs

### 4.1 There is no route that is not a patch, and this was checked

`docs/43` section 12 item 1 states the choice: "a port on `ibex_top` — a
patch to Ibex … — or a route out of the core that does not exist yet."
Three candidates were examined before accepting the first.

**`alert_major_internal_o` already leaves `ibex_top` and `soc_top.v`
already connects it.** In `hw/soc/gen/ibex_core.v` it is
`rf_ecc_err_comb | pc_mismatch_alert | csr_shadow_err | …`, and
`rf_ecc_err_comb` is exactly the register file's ECC error. So the route
exists — and its gate is `RegFileECC`, which follows `SecureIbex`, and
turning it on makes `ibex_core` instantiate
`prim_secded_inv_39_32_{enc,dec}`. That is the **second SECDED codec on
one die** that `docs/38` section 8.5 declined `SecureIbex` over and that
`docs/43` section 6.1 spent a section promising not to build. The route
is real and the toll is the one thing this project has twice refused to
pay **[fact, `hw/soc/gen/ibex_core.v` lines 1028–1099 and 1117]**.

**The register file's own unused ports go nowhere.** `rcap_a_o` and
`rcap_b_o` are 35 bits wide and tied off at `BaseIsa = RV32I`; they enter
`ibex_core` and stop. They reach no boundary.

**Verilog has no third channel.** A hierarchical reference is not
synthesisable and a module cannot see a net it is not connected to.

So: a port.

### 4.2 The smallest patch that reaches the SoC

`ibex_top` instantiates the register file **directly** — not through
`ibex_core` — so the port crosses exactly one hierarchy level and the
patch is three hunks in one file:

```
hw/soc/gen/ibex_top.v          sv2v output, UNTOUCHED
        |
        |  hw/soc/flow/ibex_fault_port.py
        v
hw/soc/genp/ibex_top.v         + rf_ecc_err_o in the port list
                               + output wire [2:0] rf_ecc_err_o;
                               + .rf_ecc_err_o(rf_ecc_err_o) on the
                                 ibex_register_file_ff instance
```

**At `IBEX_REGFILE=upstream` the port is still added and tied to zero**,
because upstream's register file has no codec and therefore nothing to
report. That is deliberate: `soc_top.v` connects the port
unconditionally, so `docs/43` section 5.4's `IBEX_REGFILE=upstream`
isolation builds keep working and report an honest zero, and no `ifdef`
has to be kept in step with a file list.

**Every anchor is asserted to occur exactly once**, and that is the
property that makes this a patch rather than a hazard. A pin that renames
`alert_major_bus_o` or restructures the register-file instantiation stops
the build with the anchor named. It is a Python script and not a `.patch`
file for one specific reason: the three register-file branches of
`ibex_top`'s generate chain are near-identical, so `patch`'s context
matching would place the instance hunk in the `_ff`, `_fpga` or `_latch`
branch with equal confidence. The script locates it *relative to* the
unique `ibex_register_file_ff #(` line instead.

### 4.3 Four costs, stated plainly

**1. `hw/soc/ext/ibex` and `hw/soc/gen` are still untouched, and the
build's `ibex_top` is no longer what sv2v emitted.** Both halves are
true and the second is the one that matters. `docs/43` section 3.2 cost 1
said the build's Ibex was no longer bit-for-bit the one the commit names
because of a substituted *file*; now it is also because of a patched
*top*. Calling the output "generated" does not make it not a patch. What
is true is that it is **derived rather than vendored**: nothing is
committed, the three hunks are eighty lines of Python, and regenerating
from a moved pin either re-applies them or fails.

**2. `docs/43`'s port-list guard has been weakened, from equality to a
prefix.**
`sw/tests/test_soc_regfile_guards.py::test_the_substitute_declares_upstreams_ports_in_upstreams_order`
asserted that the substitute's port list *equalled* upstream's. It cannot
any more: the substitute declares one port upstream does not have. The
test now asserts that upstream's list is a prefix and that the only
addition is `rf_ecc_err_o` by name, so it is still a closed statement
rather than a licence to append — but it is a weaker one, and the
weakening is a cost of this feature and not a tidy-up.

**3. The obligation on a moved pin grows.** `docs/43` section 3.2 cost 3
required `ibex_regfile_secded.v` to be re-read against upstream whenever
the pin moves. This adds `ibex_top`'s port list and its register-file
instantiation to that reading.

**4. `soc_top.v` and the flow are now coupled, and loudly.** `soc_top.v`
connects `.rf_ecc_err_o(rf_ecc_err)` with no `ifdef`, so a flow that
forgets `IBEX_FAULT_PORT=1` fails at elaboration with the port's name in
the message. That is the coupling; it is checked by the build every time
rather than by a comment.

**What is unchanged.** sv2v still converts 30 of 30 Ibex modules with
zero errors and zero patches. The conversion is not touched; one of its
outputs is post-processed on the way into the build.

---

## 5. The timing, which turned out to be a measurement problem

### 5.1 The worst path is a path `soc_top.v` does not have

`docs/43` section 7.4's table is two numbers from
`hw/soc/flow/sta_ibex.sh`, which times `ibex_top` **standalone**, with
every input a free port carrying 20 % of the period as input delay. That
is the right default for a block whose environment is not fixed and it
was the right default in `docs/38`. Reading the *paths* rather than the
slacks shows what it became here.

**All ten worst setup paths at the slow corner, in both configurations,
start at `cheriot_enable_i[0]`** **[fact,
`hw/soc/out/h44-{base,doc43}/small-pmp/sta.log`]**. Nine of the ten end
at `instr_addr_o[*]` or `data_addr_o[*]`; the tenth, which is the
reported worst, ends at `data_req_o`.

`cheriot_enable_i` is a four-bit multi-bit-encoded configuration input
and `soc_top.v` drives it with `4'b1010`, `ibex_pkg::IbexMuBiOff`: the
CHERIoT half of this dual-ISA core held off. **In the SoC the path does
not exist.**

And the decoder cannot be on it in any case. The decoder's inputs are
`rf_data[raddr]` and `rf_chk[raddr]`, both flip-flop outputs; no
combinational path runs from a primary input into them. So the sentence
`docs/43` section 7.4 attaches to its number —

> The decoder sits on the register read path and the register read path
> feeds the ALU, so this is the one place in the design where a
> correction mechanism is **in series** with the thing it protects

— is true about the design and is **not** what the two numbers under it
measured.

`hw/soc/sta/ibex_tieoffs.sdc` is the fix, and it is deliberately narrow:
it case-analyses `cheriot_enable_i` and nothing else. `soc_top.v` ties
many more inputs — `test_en_i`, `hart_id_i`, `boot_addr_i`,
`debug_req_i`, `fetch_enable_i`, the scramble ports — and constraining
all of them would report a still smaller design and would make a bigger
claim than the evidence supports, since several are legitimately variable
on a real part. **One input was measured to dominate; that one is
constrained; the unconstrained recipe is still run beside it.**
`SOC_TIEOFFS=1` turns it on and the default is off, so `docs/38`'s and
`docs/43`'s numbers reproduce from this flow untouched.

| slow corner, 20 ns | worst setup, default recipe | worst setup, tie-offs applied |
|---|---:|---:|
| `small-pmp`, upstream register file | 2.4337 | **5.7647** |
| `small-pmp`, `docs/43`'s register file | 1.7411 | **3.5468** |

**[fact]**

### 5.2 The instrument's noise is most of the signal, and here is the measurement of it

Before any of the numbers below can be read, one thing has to be
established: **the flow has not drifted.**

- `hw/soc/out/h44-base/small-pmp/ibex_top.netlist.v` is **byte-identical**
  to `docs/43`'s baseline netlist, `md5 3efbe801…`: 18,921 cells, 2,106
  flip-flops, 275,682.6198 um2, +2.4337 ns **[fact]**.
- `hw/soc/out/h44-doc43/` is `docs/43`'s `ibex_regfile_secded.v`
  restored and re-synthesised in this session. Its netlist is
  **byte-identical** to `docs/43`'s, `md5 3f742dc3…`: 22,796 cells,
  2,328 flip-flops, 313,733.1960 um2, +1.7411 ns **[fact]**.

Both of `docs/43` section 7's headline netlists reproduce exactly. What
follows is therefore about the instrument and not about the tools moving
underneath it.

**Two changes that add no gate level to the register read path, and what
they did to the reported slack.**

| pair | what differs | Δ worst setup, 20 ns, slow, tie-offs | Δ closing period |
|---|---|---:|---:|
| `h44-doc43` → `h44-slowcorr` | an output port the enclosing build does **not** connect, and a dead expression widened | 3.5468 → 3.7053, **+0.1585** | 15.57 → 15.37 ns |
| `h44-fast` → `h44-port` | the same read path, with the fault report's cone made live | 3.3665 → 2.9677, **−0.3988** | 15.80 → 16.30 ns |

**[fact]**

Neither change adds a gate level to the read path. The first is
strictly dead: an unconnected port and a widened dead expression, both of
which `opt_clean` removes, so the two netlists are computing the same
function with the same structure and differ only in what the mapper
chose. The second is weaker and the difference is worth stating rather
than glossing: making the report cone live adds **fanout** to the
syndrome nets the read path also uses, so it could in principle slow the
read path by loading it — but it adds no logic in series, and it moved
the number in the *worse* direction while `FASTCORR` was supposed to move
it in the better one. The reported slack moves by up to 0.3988 ns
anyway, because ABC re-maps a 22,000-cell design differently when
anything about it changes.

**The sharpest form of it is inside one path.** The worst synchronous
path of `h44-slowcorr` and of `h44-fast` runs through the register file
and then through the same ALU and PMP cone — identical RTL, downstream of
the only thing that differs. Split at the register file's last gate:

| | register file's portion | the shared tail | total arrival |
|---|---:|---:|---:|
| `h44-slowcorr` | 4.7717 | 7.2730 | 12.0447 |
| `h44-fast` | 3.9579 | **8.4256** | 12.3835 |

**[fact, the slow-corner `report_checks` output of both builds]**

The register file's portion is **0.8138 ns shorter** in the build that
was built to make it shorter. The tail, on RTL that is character for
character the same, is **1.1526 ns longer**. The second effect is larger
than the first and it is entirely the mapper's.

> **A whole-core setup slack from this flow is not an instrument with
> better than about 0.4 ns of resolution, and a single critical path's
> composition moves by more than 1 ns for reasons that have nothing to do
> with the change under test** **[estimate, from the two controlled pairs
> above]**.

*Amended 2026-09-05 by `docs/70-boot-hardening-placed.md` section 5.3.
This figure is a **synthesis** floor for **whole-core setup**, and
`docs/61` section 9.1, `docs/62` section 1 and `docs/67` section 5.3
have each quoted it after place-and-route because it was the only
floor in the corpus. The same kind of control, run on two layouts of
one design, gives **0.5031 ns** for slow-corner setup, **0.0198 ns**
for fast-corner hold and **12,962 um2** for placed standard-cell area
**[estimate, one pair, as this one is]**. No verdict in those three
documents changes.*

*Amended again 2026-09-05 by `docs/71-layout-reproducibility.md` section 7. The same
netlist laid out twice through the same flow gives a **byte-identical**
sign-off report — 199 metrics, the DEF and the OpenDB database — so
neither this 0.4 ns nor `docs/70`'s post-layout figures is instrument
noise: they are the flow's **sensitivity to a changed netlist**,
deterministic and repeatable. They stand as the threshold for reading a
delta between two netlists and do not apply to a re-run of one.*

That is why section 5.4 measures the register file on its own, and why
this document does not claim the whole-core numbers confirm anything at
the scale of the effect.

### 5.3 And the 56.8 MHz is the reset net

`docs/43` section 7.4's frequency table is `hw/soc/flow/sweep_ibex.sh`, a
bisection on the clock period. Re-run in this session on three
configurations:

| Configuration | Closes `setup_all` at | Frequency | **Binding path group** |
|---|---:|---:|---|
| `small-pmp`, upstream register file | 15.98 ns | 62.6 MHz | `setup_sync` — the `cheriot_enable_i` path of 5.1 |
| `small-pmp`, SECDED, `FASTCORR = 0` | 17.62 ns | 56.8 MHz | **`setup_async`** |
| `small-pmp`, SECDED, `FASTCORR = 1` | 17.62 ns | 56.8 MHz | **`setup_async`** |

**[fact]**. The baseline row reproduces `docs/38` section 8.6 and
`docs/43` section 7.4 exactly, and the two hardened rows report
**bit-identical slacks at every probe** — −0.1653 at 17.41, −0.0773 at
17.52, −0.0373 at 17.57 **[fact]** — which is the first sign that
whatever binds them is not in the datapath.

It is not. The `asynchronous` group's worst path is one net:

```
Startpoint: rst_ni (input port clocked by clk_i)
Endpoint:   _40820_ (recovery check against rising-edge clock clk_i)
   4.0000    4.0000 ^ input external delay
  10.9223   14.9223 ^ rst_ni (in)
   0.0000   14.9223 ^ _40820_/RESET_B (sg13g2_dfrbpq_1)
```

**[fact, `hw/soc/out/h44-slowcorr/small-pmp/path_slow_setup_async.rpt`]**

`rst_ni` drives **2,328 flip-flop reset pins directly from the input
port, through no buffer at all**, and 10.9223 ns is what the SDC's
`sg13g2_buf_4` costs into that much capacitance. The baseline's version
of the same net drives 2,106 pins and costs 9.7445 ns.

> **`docs/43`'s "the protection costs 1.64 ns of period and 5.8 MHz,
> −9.3 %" is, at the hardened end, the cost of putting 222 more
> flip-flops on an unbuffered reset net** **[estimate, from the two path
> reports]**. It is a real number about a real netlist and it is not a
> number about the decoder. A clock tree and a reset tree are what
> place-and-route builds, and no SoC block has been through
> place-and-route — `docs/38` section 10 item 3 already carries that as
> an obligation.

**The honest frequency, on the paths that exist.** Bisecting on
`setup_sync` with the tie-offs of 5.1 applied, so that neither the false
path nor the unbuffered reset is in the gate:

| Configuration | Closes at | Frequency |
|---|---:|---:|
| upstream register file | 12.80 ns | **78.1 MHz** |
| SECDED, `docs/43`'s file | 15.57 ns | 64.2 MHz |
| SECDED, `FASTCORR = 0` | 15.37 ns | 65.1 MHz |
| SECDED, `FASTCORR = 1` | 15.80 ns | 63.3 MHz |
| SECDED, `FASTCORR = 1`, fault port live — **as shipped** | 16.30 ns | **61.3 MHz** |
| SECDED, `FASTCORR = 1`, `SYNPRE = 1` | 15.02 ns | 66.6 MHz |

**[fact, bisection on the fixed netlist; see section 14]**

Read that table with section 5.2 in hand. The three rows that share a
read path — 64.2, 65.1, 63.3 — span 0.9 MHz **for no reason attributable
to the design**, and the shipped row's 61.3 is 2.0 MHz below the row it
differs from only by a report cone that is not on the read path. **The
one difference in this table that is larger than the noise is the first
one**: the protection costs somewhere around 13 to 17 MHz of
logic-limited frequency, and the SoC's target is 50 MHz.

### 5.3a A method note, because it changes what a bisection means

**All eight probes of the baseline bisection produced a byte-identical
netlist** **[fact, `md5sum` over
`hw/soc/out/sweep-small-pmp-setup_all-h44base/p*/small-pmp/ibex_top.netlist.v`
gives one hash]**.

`docs/38` section 8.6 describes the method as "re-synthesising at every
probe, so that the number `abc` optimises for and the number STA checks
are the same number". The re-synthesis happens; the optimisation does
not. Yosys's `abc -D` takes **picoseconds**, and the flow passes the
period in nanoseconds — 14 to 22 — so every probe asks ABC for a target
three orders of magnitude beyond reach and gets its maximum-delay-effort
result unchanged.

**The frequencies are still correct**: a bisection for the period at
which one netlist's slack crosses zero is exactly what they report. What
is not correct is the stated rationale, and one consequence follows from
it — the bisection is a linear solve and does not need synthesis at all,
which is why section 5.3's tie-off table was produced by re-running STA
on the fixed netlists in seconds rather than by fourteen more syntheses.
`docs/38` section 8.6 is corrected in section 12.

### 5.4 What the codec costs, and what was recovered, measured where it can be

`hw/soc/flow/sta_regfile.sh`: `ibex_register_file_ff` synthesised alone
at `soc_top.v`'s parameters, constrained by `hw/soc/sta/ibex.sdc.in`
unaltered, all three corners. Every path in this netlist is
input-to-flop or flop-to-output, so the 20 % IO delay is a large part of
every number and **the slacks are not comparable to the core's**. The
differences between the rows are, which is what the script is for, and
the arrival time at `rdata_a_o` is reported beside the slack so the raw
quantity is visible.

| Configuration | Cells | Flops | Area, um2 | arrival at `rdata_a_o`, slow |
|---|---:|---:|---:|---:|
| upstream's `ibex_register_file_ff` | 4,804 | 992 | 94,153.1094 | 5.5014 |
| this file, `HARDEN = 0` | 5,797 | 992 | 93,469.9878 | **5.5282** |
| `HARDEN = 1, SCRUB = 0` | 7,041 | 1,209 | 113,987.9412 | 7.8891 |
| `HARDEN = 1, FASTCORR = 0` — `docs/43`'s read path | 8,304 | 1,214 | 126,842.2470 | **8.3210** |
| `HARDEN = 1, FASTCORR = 1` — as shipped | 8,432 | 1,214 | 128,043.7956 | **8.0617** |
| `HARDEN = 1, SYNPRE = 1` — measured, not shipped | 10,539 | 1,214 | 159,272.9082 | **6.4533** |

**[fact]**

> **The codec costs 2.7928 ns on the register read path**, `FASTCORR = 0`
> against `HARDEN = 0` **[estimate, the difference of two
> measurements]**.
>
> **`FASTCORR` recovers 0.2593 ns of it, 9.3 %, for +1,201.5486 um2 and
> +128 cells** **[estimate, the difference of two measurements]**.

**These module numbers are not `docs/43` section 7.2's and must not be
subtracted from them.** The module now has a fault port, so its report
logic is live where `docs/43`'s was dead. `docs/43` measured four of
these configurations; the two this document did not change reproduce to
four decimal places — `upstream` at 94,153.1094 and `HARDEN = 0` at
93,469.9878 **[fact]**, which is the check that the recipe is the same
recipe — and the two it did change moved for the port alone:
`SCRUB = 0` from 115,216.0254 to 113,987.9412 and `docs/43`'s hardened
row from 125,179.5384 to this document's `FASTCORR = 0`'s 126,842.2470.
**Both directions appear**, which is what a live report cone plus a
different dead-logic boundary does to a mapper, and neither difference is
a saving or a cost of anything.

**What `FASTCORR` does.** `hw/rtl/secded_dec.v` computes

```
data_out = sec ? (data_raw ^ corr_mask) : data_raw
```

and `sec` is `syn_nonzero && syn_odd && (data_hit || check_hit)`, where
`data_hit` is a 64-wide OR of the column comparisons and `check_hit`
contains an eight-bit subtract. On the **data** path that qualification
is redundant: `corr_mask[j] = 1` means the syndrome equals H column *j*,
every column is nonzero and of odd weight — which is what makes this code
SECDED at all — so `sec` is 1 whenever the mask is nonzero, and when the
mask is zero both arms of the multiplexer are `data_raw`. The register
file therefore XORs the raw word with a mask it builds from the decoder's
**syndrome**, and does not wait for the OR, the subtract, the AND that
joins them or the multiplexer they select.

**The columns are derived and not written down.** Writing H into this
project's file a second time is the duplication `docs/38` section 8.5
refused and `docs/43` section 6.1 promised not to commit, and it would be
the worst kind — two copies of a constant that must agree and that no
build step compares. So the columns are computed by the pilot's own
encoder on the thirty-two unit vectors: `col_j = enc(1 << j)`. The
synthesiser folds all thirty-two instances, and
`test_the_correction_masks_columns_are_folded_and_cost_no_cells` fails if
a front end ever stops.

**And it is proved, not argued.** The paragraph above is an argument
about a matrix, which is the kind of thing this repository has learned to
distrust. `hw/soc/formal/regfile_secded.sby` property **C5** states
`data_raw ^ corr_mask == data_out[31:0]` over a **free codeword and a
free error vector**, with no guard on the error weight, on two engine
families, and the cover obligations say the equality is not holding
vacuously: the mask is reachably nonzero, and the decoder reachably
reports uncorrectable while the mask is zero. Section 8.4.

**And the register file's own 124-injection cocotb campaign runs against
`FASTCORR = 1`** and comes back with the same 107 CORRECTED, 17 MASKED,
0 SDC, 0 DETECTED it did in `docs/43` **[fact]**, which is the
behavioural half: a proof about a codeword says nothing about a codeword
that has been through a read multiplexer.

**The scrub still uses the frozen decoder's `data_out`, unaltered.** It
is not on the read path, and being literally the proved decoder's output
is worth more there than the levels it costs.

### 5.5 The alternative that would have worked, priced and declined

The only structural way to take the **syndrome tree** off the read path
is to compute it before the multiplexer instead of after it. The
syndrome is linear in the stored word and the multiplexer is a selection,
so the two orders compute the same thing — but hiding *k* levels of a
tree behind a multiplexer needs 2^k copies of the tree, and the tree is
four levels deep. There is no partial version that helps: a tree placed
between two multiplexer stages is still in series with both.

`SYNPRE = 1` builds the full version, one parity tree per register, and
the measurement is section 5.4's last row:

> **`SYNPRE` recovers 1.8677 ns of the codec's 2.7928 ns — 66.9 % — for
> +31,229.1126 um2 on the module and +31,965.0030 um2 on the core**
> **[estimate, differences of measurements]**. That is **11.6 % of the
> unprotected core** on top of the protection's own 14.6 %.

**It is not shipped, and the reason is a target and not a preference.**
The SoC's SDC period is 20 ns and the shipped core meets it with
**+1.5514 ns** at the slow corner **[fact]**; on the paths that exist it
closes at 16.30 ns, 61.3 MHz, against a 50 MHz target. A margin that is
not binding is not worth eleven per cent of a core to widen, and
`docs/09`'s 50–80 MHz estimate is not violated by either configuration.

**The reversal condition, so this is a decision and not a deferral.** If
a clock target above about 60 MHz is ever adopted — after
place-and-route, which on this project's history moves these numbers
down — `SYNPRE` is the lever and its price is now a number rather than a
guess. `sw/tests` asserts that nothing in the design sets it, so it
cannot drift into the build the way `docs/43` section 12 item 5 warns a
disabled mechanism can.

### 5.6 Why not a replay, which is the classic answer

The standard answer to "a corrector is on the fast path" is that it need
not be: detect combinationally, and take a replay cycle to correct, since
a corrected read is rare and a stalled cycle is much cheaper than a
lengthened one. `docs/42`'s own recommendation shape. It was examined and
rejected, on two findings rather than on a preference.

**1. Detection is not cheaper than correction here, only *slightly*
cheaper.** Syndrome-zero detection still needs the syndrome, which is the
four-level XOR tree — 0.86 ns of the codec's 2.79 on the measured path.
What a replay would save is the correction stage, about 1.08 ns. So the
classic answer buys at most 39 % of the cost, which is less than
`SYNPRE` buys without stalling anything.

**2. Ibex has no input that stalls a mid-flight instruction, and
building one is a fork.** The ID-stage stall terms — `stall_mem`,
`stall_multdiv`, `stall_branch`, `stall_ld_hz` — are internal to
`ibex_id_stage`. Driving one from outside needs a port on
`ibex_id_stage`, a port and a wire on `ibex_core`, and a port on
`ibex_top`: **three files instead of one, in the control path of a CPU
this project does not verify and cannot re-verify.** Section 4's patch is
three hunks in one file because the register file is instantiated in
`ibex_top` directly; the stall is not that shape.

**And upstream does not do it either**, which is the corroboration rather
than the argument: `RegFileECC` in `ibex_core.v` raises
`alert_major_internal` on a register-file ECC error and does **not**
correct and does **not** replay **[fact,
`hw/soc/gen/ibex_core.v` lines 1073–1083 and 1117]**. The replay
machinery a replay needs is machinery Ibex has never had.

**A trap is not a replay either, and this was checked too.** An NMI does
re-execute the interrupted instruction after `mret`, so a fault line into
`irq_nm_i` looks like a replay — but interrupts are taken *between*
instructions, so the instruction that read the corrupted register has
already committed its result by the time the line is sampled. It would
announce a corruption it had already let through.

---

## 6. BUSSTAT: four counters, two reset domains, one interrupt

### 6.1 It goes where the map already put it

`docs/memmap-soc.md` section 3 has carried, since `docs/39` froze the
map:

```
0xFF915000   slot 0x015   BUSSTAT   irq 22   line 10   reserved
"System-bus error latch and ECC counters; AHBSTAT in spirit, not in
 name"
```

Nothing about the address, the slot, the interrupt number or the line is
new. `regmap/memmap.yaml` changes one word — `reserved` becomes
`implemented` — and `soc_top.v` decodes it. The generated map, the device
table, the header and the linker script all follow from that one edit,
which is what the generator is for.

### 6.2 Four counters and not one, and what each one is the unit of

`pilot_top.v` folds its LIF core's corrections into the same `CNT_SEC` as
its weight-load path and says in a comment what that costs: "a host
reading CNT_SEC cannot tell a synapse array correction from a load-path
one". That was the right call there because the register map was already
frozen. Here it is not, so the counters are separated where separating
them answers a different question.

| Register | Offset | Unit |
|---|---|---|
| `CNT_RFSEC` | `+0x08` | **UPSETS.** Single-bit upsets the register file's *scrub* repaired. The walk reaches every register, so an upset the program does not overwrite first raises this **exactly once** — on the cycle the repaired word is written back. **This is the upset-rate counter** |
| `CNT_RFRD` | `+0x0C` | **CYCLES** in which a read port returned a corrected word. One upset read ten times before the scrub reaches it counts ten. An upper bound on the upset count and a lower bound on nothing |
| `CNT_RFDED` | `+0x10` | Syndromes the codec could not correct: two upsets in one register between two scrubs |
| `CNT_TMRERR` | `+0x14` | Mismatches the watchdog's voter masked — `docs/41` W6, and `docs/41` section 10 item 3's fault line |
| `STATUS` | `+0x00` | Four stickies, and bit 8 = the interrupt line |
| `IRQEN` | `+0x04` | One enable per source. **Zero at reset** |
| `CLR` | `+0x18` | Write-1-to-clear, one bit per source. Write-only |

**`CNT_RFSEC` and `CNT_RFRD` are carried separately precisely so that no
reader can mistake one for the other**, and the second is worth carrying
because `CNT_RFRD` much larger than `CNT_RFSEC` is the observable
signature of upsets being read before they are scrubbed — which is
`docs/43` section 6.4's unbounded scrub period, made visible for the
first time.

**The event bit that feeds `CNT_RFSEC` is gated on the scrub actually
writing.** `u_dec_s` decodes the register the pointer names on every
cycle, including the cycles the core is writing and the scrub is stalled,
so an ungated report would count one upset once per stalled cycle.
Section 8.2 shows the gate working: on `docs/42`'s `x23` bit-3 record the
bench's ungated `sec_cycles` reads 2 and the SoC's `CNT_RFSEC` reads 1,
for one upset.

**All four saturate.** A counter that wraps is indistinguishable from one
that has barely moved, and nothing downstream can tell the difference.

### 6.3 Two reset domains, and the brick that made them two

The **record** — four counters and four stickies — is in the **power-on**
domain, by `docs/40` W4's argument applied to telemetry: a watchdog
stage-2 reset must not erase the evidence of what caused it, and the most
valuable reading of an upset counter is the one taken after the reset it
explains.

The **interrupt enable** is in the **system** domain, and it is in a
different domain from the record on purpose. `docs/40` section 7.2 spent
a section on a brick this project built once: a mechanism installed
before software went wrong, which survived the reset that going wrong
caused, and which then fired again on the fresh boot for ever. An enabled
fault interrupt with a sticky still set is exactly that shape — the
handler would be entered before the boot code had installed one. So
`IRQEN` clears on every system reset, the record does not, and a fresh
boot sees the whole history and is interrupted by none of it until it
asks to be.

`test_a_sticky_survives_a_system_reset_and_the_enable_does_not` is the
check, and formal property B4 is the proof.

### 6.4 Clearing, and the argument against it

`docs/43` section 5.3 states the rule this block has to answer to: "A
record software can erase is a record an upset can erase." Here the
record **is** software-clearable, and that is a decision:

- A rate is a count over an interval and an interval needs an origin. A
  counter that can never be zeroed reports a total and cannot report a
  rate, and the rate is what a telemetry frame carries.
- Saturation makes the unclearable version worse, not better: a counter
  that has saturated and cannot be cleared is dead for the rest of the
  mission.
- `pilot_top.v`'s `FAULT_CLR` makes the same choice for the same kind of
  register, so this is the convention this project already has.

**The cost, stated: a wild store to `CLR` erases the record.** It is the
same exposure every clearable status register in this SoC has, it is not
key-gated — unlike the watchdog, this block cannot brick anything — and
it is named here rather than left to be found.

**An event and its clear in the same cycle resolve in favour of the
event.** That is not a corner case: it is the cycle the telemetry frame
is being built. `test_an_event_in_the_cycle_of_its_own_clear_is_not_lost`
and formal property B1 are the two checks.

### 6.5 A defect found by building it, and what it says about X

The first version of the counter computed `{1'b0, cnt} + {0…, ev}` and
saturated on the carry — arithmetically identical to what is there now,
and synthesising the same. **It made two of the four counters read X for
the whole of every SoC simulation.**

The cause is upstream's and not this block's. `rf_ecc_err_i[1]` and `[2]`
are the read-port reports, and a read port's syndrome is a function of
`raddr_a_i`, which comes from `instr_rdata_id` — a flip-flop Ibex does
**not** reset at `SecureIbex = 0`. So for the first instructions after
reset the read address is X in simulation, the syndrome is X, the report
is X, and an **added** X poisons the counter permanently. A **branched**
X does not: the branch is simply not taken.

It was found because a clean run printed `sw_bst_rd=X` beside
`sw_bst_sec=0`, which is the only reason the report prints all four
counters rather than the one the demonstration needs.

**Two things follow and both are recorded rather than fixed.** In
simulation these counters do not include any correction that happened
while the read address was still X — section 10. And `docs/43`'s own
`sec_cycles` counter has always had the same exposure and never showed
it, because `if (sec_any)` is a branch: it has been silently not counting
that window for a whole document.

---

## 7. Measured area

### 7.1 The core

Same recipe as `docs/38` section 8.1, `docs/41` section 6.5 and
`docs/43` section 7.1: Yosys on `ihp-sg13g2` typical, `abc` at a 20 ns
delay target with the same driving cell and load, `stat -liberty`. Gate
equivalent = `sg13g2_nand2_1` = 7.2576 um2.

| Configuration | Cells | Flops | Area, um2 | vs baseline |
|---|---:|---:|---:|---:|
| `small-pmp`, upstream register file | 18,921 | 2,106 | **275,682.6198** | — |
| `docs/43`'s file, re-measured here | 22,796 | 2,328 | **313,733.1960** | +13.80 % |
| `FASTCORR = 0`, port not connected | 22,894 | 2,328 | 314,212.7268 | +13.97 % |
| `FASTCORR = 1`, port not connected | 22,497 | 2,328 | 310,879.1070 | +12.77 % |
| **`FASTCORR = 1`, fault port live — as shipped** | 22,338 | 2,328 | **316,051.6590** | **+14.64 %** |
| `FASTCORR = 1`, `SYNPRE = 1` | 24,210 | 2,328 | 342,844.1100 | +24.36 % |

**[fact, all measured in one session; rows 1 and 2 reproduce `docs/38`
section 8.4 and `docs/43` section 7.1 byte-identically]**

> **The shipped core is +40,369.0392 um2 over the unprotected baseline,
> +14.64 %, and +222 flip-flops** **[estimate, the difference of two
> measurements]**.
>
> **The fault report costs +5,172.5520 um2 inside the core**, the
> difference between the two `FASTCORR = 1` rows: the same read path,
> with the report's cone dead in one and live in the other **[estimate]**.
> `docs/43` section 6.5 predicted that number would be zero for as long
> as nothing could read it, and it was.

**Do not subtract row 3 from row 4 and call it the cost of `FASTCORR`.**
Row 4 is 3,333.62 um2 *smaller* than row 3, and the reason is not a
saving: with the port unconnected, `FASTCORR = 1` leaves the decoders'
whole column-comparison and multiplexer cone driving nothing, and
`opt_clean` deletes it. Row 5 is the one to read, because in the shipped
design that cone drives the counters. Section 5.4's module measurement is
where `FASTCORR`'s own cost is separable, and it is +1,201.5486 um2.

### 7.2 The blocks

`hw/soc/flow/syn_soc.sh`, the recipe `docs/40`, `docs/41` and `docs/43`
measured with:

| Block | Cells | Flops | Area, um2 | % of the unprotected Ibex |
|---|---:|---:|---:|---:|
| `soc_busstat` | 442 | 72 | **7,060.5486** | 2.561 % |
| `soc_wdog`, with `tmr_ev_o` | 1,035 | 131 | **15,579.7614** | 5.651 % |
| `soc_wdog` as `docs/43` shipped it | 1,042 | 131 | 15,695.7318 | 5.693 % |

**[fact]**

**The watchdog's fault line costs nothing measurable, and the difference
is in the cheap direction, which is the direction this repository has
learned to write down.** Adding an output port made the block 115.9704
um2 and 7 cells *smaller* at the same 131 flip-flops. A port cannot
reduce logic; this is the mapping noise of section 5.2 at block scale,
and quoting it as a saving would be exactly the error `docs/41` section
6.5 records.

`soc_busstat`'s 72 flip-flops are 4 counters × 16 bits + 4 stickies + 4
enables, and `sw/tests/test_soc_synthesis_guards.py` derives that
arithmetic from the module's own `CNT_W` rather than writing 72 down.

> **The whole telemetry costs 12,117.1302 um2** — +5,172.5520 in the
> core, +7,060.5486 for the block, −115.9704 at the watchdog —
> **4.40 % of the unprotected core** **[estimate, the sum of three
> measurements]**.

---

## 8. Verification and evidence

### 8.1 The cycle-count invariant held

`docs/43` section 9.1's table, re-measured:

| | `docs/40`, `docs/41`, `docs/43` | now |
|---|---|---|
| whole-SoC run, checks | 22, fail mask 0 | 22, fail mask 0 |
| watchdog stage 1 | cycle 174,128 | cycle 174,128 |
| core asleep after | 185,443 cycles | **185,443 cycles** |
| console | 587 characters, 0 framing errors | 587 characters, 0 framing errors |
| `docs/42`'s workload, ROM image | `c48d8d732610b323a7243a88408df00a` | identical |
| `docs/42`'s clean fault-injection run | 18,682 cycles, sig `9c07ef12` | identical |

**[fact]**. Not one cycle moved. That is what a design should look like
after a change whose datapath half is *proved* to compute the same
function and whose other half adds a peripheral nothing accesses and an
interrupt whose enable resets to zero.

**Why the new interrupt cannot move it**, stated rather than left to the
measurement: `soc_busstat`'s `irq_o` is `|(sticky & irqen)` and `irqen`
resets to zero, so fast line 10 is low until software writes `IRQEN`, and
the bring-up program never does.

### 8.2 An operator can see a corrected upset, and the demonstration is a load instruction

This is the result `docs/43` section 12 item 1 asked for, and the shape
of the evidence matters as much as the numbers. `docs/43`'s CORRECTED
column was populated by a hierarchical read of a counter `opt_clean`
deletes — "a bench observation and not an operator channel", in its own
words. Here the program executes `lw` from `0xFF915008` and the value is
read out of RAM.

`docs/42`'s four `x23` records — the ones section 8.1 of that document is
entirely about, and the ones `docs/43` showed the register file removes
at source — replayed against the SoC with the counters built:

| site | bit | cycle | outcome | bench `sec_cycles` | **software `CNT_RFSEC`** |
|---|---:|---:|---|---:|---:|
| `x23` | 24 | 14,073 | golden | 1 | **1** |
| `x23` | 15 | 9,940 | golden | 1 | **1** |
| `x23` | 29 | 9,670 | golden | 1 | **1** |
| `x23` | 3 | 5,720 | golden | **2** | **1** |

**[fact, `hw/soc/out/fi-bst`, four directed runs]**, against a clean run
that reads 0, 0, 0, 0 on all four counters **[fact]**.

**The fourth row is the one worth reading twice.** The bench counter says
2 and the SoC counter says 1, for one injected upset, and both are
right: `sec_cycles` counts cycles in which *any* decoder corrected —
including the cycles the scrub was stalled behind a core write and
decoded the same corrupted register again — while `CNT_RFSEC` is gated on
the scrub actually writing back and therefore counts the upset once.
Section 6.2 designed that difference; this is it happening. `CNT_RFRD`
reads 0 on all four, which says the corrupted register was never read
before the scrub reached it.

**What this does not show.** Four injections into one register are not a
rate, the counters were read once at the end of a run rather than
polled, and nothing here exercises the interrupt on a real program.

### 8.3 cocotb

| Suite | Tests | Result |
|---|---:|---|
| `test_soc_bus` | 13 | 13 pass |
| `test_soc_apb_bridge` | 11 | 11 pass |
| `test_soc_clint` | 12 | 12 pass |
| `test_soc_gptimer` | 10 | 10 pass |
| `test_soc_wdog` | 14 | 14 pass |
| `test_soc_wdog_win` | 13 | 13 pass |
| `test_soc_wdog_fi` | 3 | 3 pass, 220 injections inside |
| `test_ibex_regfile_secded` | 6 | 6 pass, 124 injections inside |
| **`test_soc_busstat`** | **10** | **10 pass** |

**[fact]**. The 82 tests of `docs/40`, `docs/41` and `docs/43` are
unchanged and were re-run — including the register file's own
124-injection campaign, which now runs against `FASTCORR = 1` and is a
behavioural check of the recovery on top of the proof, and the
watchdog's 220-injection campaign, which is the check that `tmr_ev_o`
changed nothing inside the block it observes.

**`sw/tests`, the whole tree: 315 collected, 315 passed** **[fact]**.
`docs/43` closed at 295. Five of the new tests are this document's — two
in the register-file guards, where one of `docs/43`'s became two, and
three in the synthesis guards — and two more are the per-document rows
`test_doc_links.py` generates for documents that landed. The rest is the
tree growing around this work rather than because of it, and the number
is given as a total because that is what running the suite prints.

### 8.4 Formal

| Job | Tasks | Result |
|---|---|---|
| `soc_bus` | bmc, prove, cover | all PASS |
| `soc_apb_bridge` | bmc, prove, cover | all PASS |
| `soc_clint` | bmc, prove, cover | all PASS |
| `soc_wdog` | bmc, prove, prove_w0, cover | all PASS |
| `soc_wdog_tmr` | 8 tasks | all PASS |
| `regfile_secded` | bmc, prove, prove_abc, cover | all PASS |
| **`soc_busstat`** | **bmc, prove, prove_w16, cover** | **all PASS** |

**7 jobs, 29 tasks** **[fact]**. `docs/43` closed at 6 and 25.

**`regfile_secded` gains C5, which is what the timing recovery rests
on.** Over a free data word and a free 40-bit error vector, with **no
guard on the error weight**: `data_raw ^ corr_mask == data_out[31:0]`.
The mask's columns are derived inside the proof the same way the RTL
derives them — from `hw/rtl/secded_enc.v` on the unit vectors — so the
proof follows the codec if it ever changes rather than certifying a copy
of it. Cover obligations went from 5 to 7 and both new ones are reached:
the mask is nonzero somewhere, and the decoder reports uncorrectable
while the mask is zero. Without the second, C5 could hold vacuously.

**`soc_busstat` is proved at two counter widths.** `CNT_W = 4` for the
default tasks, because the saturation **cover** is the point of the job
and a counter 65,535 increments from its top is not reachable in a
bounded model — a job that could not reach it would report a green
result for a case it never examined, which is this repository's recurring
defect. `prove_w16` runs the whole property set again at the width
`soc_top.v` instantiates, without that cover. No property mentions 4 or
16; every one is written against `CNT_W` and `CNT_MAX`.

### 8.5 The netlist census

Two questions, both of the `docs/43` section 9.4 shape — a green
functional result on a netlist that no longer contains the thing.

**The register file.** Unchanged: 992 data + 217 check + 5 scrub-pointer
flip-flops at `HARDEN = 1`, 992 at `HARDEN = 0`, on two technology
mappers **[fact]**. `FASTCORR` moves no flip-flop.

**The counters.** New. `soc_busstat` has no redundancy for a synthesiser
to collapse, so this is the same question in another form: four
saturating counters that nothing else in the design reads. Every
functional test drives the event lines by hand and reads the registers
back, and every one would pass on a netlist in which a counter had been
reduced to its sticky bit. The census counts **72** and derives the
expectation from `CNT_W` **[fact]**.

**And the connection, which is the failure this whole document is
about.** `test_the_fault_lines_are_connected_in_soc_top` reads
`soc_top.v` and fails if either fault line is missing or tied off.
`pilot_top.v` records why: four ECC status wires left unconnected, so the
codes corrected and nothing on the chip said so, and a campaign measured
84 corrections and had to classify every one MASKED — with every proof
and every test green.

**And the patch.** `test_the_ibex_top_patch_applies_to_the_pinned_output`
runs `ibex_fault_port.py`'s anchor checks against the current
`hw/soc/gen/ibex_top.v` in both modes without building, and fails if the
patch has grown past three hunks.

### 8.6 The RTL census still covers the whole core

`hw/soc/flow/fi_coverage.sh`, re-run against the elaboration this
document builds:

```
flip-flop signals elaborated : 145
  named by a campaign site   : 145
  not named                  : 0

flip-flop BITS elaborated    : 2431
  covered by the campaign    : 2431  (100.0 %)
  not covered                : 0
```

**[fact]**. Identical to `docs/43` section 9.4.

---

## 9. The campaign

`docs/43`'s campaign A is re-run on the design this document builds,
with the same seeded draws, the same byte-identical workload image and
the same 100 draws per stratum over 14 strata — 1,400 injections, each
run twice, 2,800 simulations.

**The answer is that nothing moved, and "nothing" is meant literally: the
two 1,400-record files are byte-identical.** Section 9.2.

**There was an argument that nothing would move, and it is worth stating
because it is not what settles the matter.** The datapath change is
*proved* equivalent (C5), the SoC run is cycle-identical, the ROM image
is byte-identical, and the two additions the design carries — a fault
port and a peripheral — are read-only observers of state the core already
had. **An expectation is not a measurement**, which is why the campaign
was run anyway: `docs/43` section 9.4's whole point is that a proof
cannot see what a synthesiser did, and `docs/41` section 8.4's is that a
campaign can be measuring something other than what it says.

### 9.1 The five controls

`docs/42` section 5.1's controls, all five, on the build this document
ships **[fact, `hw/soc/out/fi-h44/campaign.log`]**:

| control | result |
|---|---|
| 1, the site list | 148 sites, every path, index and width agrees with `targets.py` |
| 2, the clean run | **18,682 cycles, sig `9c07ef12`**, 19 console characters, no announcement; measured window 208..16910 |
| 3, the disarmed clean run | reproduces exactly, and is identical with the watchdog held off; budget leaves 11.0 escalation ladders |
| 4a, positive | bit 20 of `x2` at cycle 8,559 classifies **CORRECTED**, so deposits land |
| 4b, negative | bit 40 of `mcycle`, which this program never reads, classifies MASKED |

Every one of these numbers is `docs/42`'s and `docs/43`'s, unchanged.
Control 2 in particular is the check that matters most here: the same
cycle count and the same signature from the same ROM image on a design
whose register read path has been rebuilt.

### 9.2 The delta is zero, at the strongest resolution the harness has

**The two `records.csv` files are byte-identical.**

```
3fe1ed3887d72072d69c9c9008814fd2  hw/soc/out/fi-h1/records.csv    docs/43
3fe1ed3887d72072d69c9c9008814fd2  hw/soc/out/fi-h44/records.csv   this document
```

**[fact]**. 1,400 records each, 27 columns, and every field the same: the
same draws, the same armed and disarmed classification, the same truth,
the same cycle counts for both runs, the same announcement channels, the
same watchdog stage and latency, the same per-record correction counts.
The two `campaign.log` files differ in **one line**, which is the path
the records were written to **[fact, `diff`]**.

That is a stronger statement than "the rates agree", and it is worth
being precise about why. An aggregate delta of zero is consistent with
two records moving in opposite directions. This is not: no record moved.

**What the comparison is against, stated because a delta compared
against the wrong thing is the commonest way this goes wrong.** The
baseline is `docs/43`'s **campaign A**, in `hw/soc/out/fi-h1/`, written
at 06:26 on 2026-09-01 — before any change in this document existed. It
is **not** `docs/42`'s campaign: `docs/42` drew 1,300 injections over 13
strata weighted by 2,198 bits, and `docs/43` drew 1,400 over 14 weighted
by 2,451, having added the `regfile_ecc` stratum for the 253 flip-flops
its own protection introduced. **That change of denominator is
`docs/43`'s and this document inherits it unchanged**; `docs/43` section
8.2 flags what part of its weighted improvement came from it, and none
of that argument is re-made or re-used here. This document compares 14
strata against the same 14, with the same weights, from the same seed —
which is why "identical" is available as an answer at all.

**What that licenses and what it does not.** It licenses exactly one
claim: **nothing this document changed moved the campaign.** It does not
re-measure the hardening's value, it does not revisit `docs/42`, and
every caveat `docs/43` section 8 attaches to these numbers — one
workload, one seed, RTL only, single-bit only, an oracle that sees the
run's output and not the machine's architectural state, and a zero row
that means "below about 3.7 %" and not zero — applies here word for
word, because they are the same numbers.

**The numbers themselves**, quoted so this document can be read without
`docs/43` open, all **[fact, `hw/soc/out/fi-h44/campaign.log`]**:

| | `docs/42` | `docs/43` campaign A | **this document** |
|---|---|---|---|
| `regfile`: MASKED / CORRECTED / SDC / DETECTED / HANG | 78 / 0 / **3** / 15 / **4** | 6 / 94 / 0 / 0 / 0 | **6 / 94 / 0 / 0 / 0** |
| `regfile_ecc`: same | — | 4 / 96 / 0 / 0 / 0 | **4 / 96 / 0 / 0 / 0** |
| design-weighted SDC, watchdog held off | 2.8 % ± 1.6 | 1.3 % ± 0.4 | **1.3 % ± 0.4** |
| design-weighted HANG, watchdog held off | 2.1 % ± 1.8 | 0.3 % ± 0.2 | **0.3 % ± 0.2** |
| design-weighted SDC, watchdog armed | 2.7 % ± 1.6 | 1.2 % ± 0.4 | **1.2 % ± 0.4** |
| design-weighted HANG, watchdog armed | 1.4 % ± 1.5 | 0.0 % ± 0.0 | **0.0 % ± 0.0** |
| upsets that leave the core DEAD | 36 of 1,300 | 28 of 1,400 | **28 of 1,400** |
| of those, the watchdog escalated | 33 — 91.7 % | 28 — **100.0 %** [87.9 – 100] | **28 — 100.0 %** [87.9 – 100] |
| spurious escalations over survivable upsets | 0 of 1,106 | 0 of 1,228 | **0 of 1,228** |
| wrong answer with nothing announced | 118 of 1,300 | 110 of 1,400 | **110 of 1,400** |

### 9.2a What this result changed in the rest of this document

Sections 5 to 8 were written while the campaign was still running, and
three places were written conservatively **because** the data was
missing. They have been changed deliberately rather than left to be read
as though they had always said this, and the changes are listed so a
reader can see which way each went:

- **The verdict table's campaign row** said "launched, controls green,
  and not finished, with no measured delta". It now states the delta.
  **Stronger, and the data supports it.**
- **Section 11's first item** was "finish the campaign". It is gone;
  `mtime` moves up, and the harness defect of section 9.5 becomes an
  item of its own rather than a rider on that one.
- **Section 10's first bullet** said the campaign had not been
  completed. It now says something **weaker about this document, not
  stronger**: an identical campaign is not a wider one, and the reason
  it is identical is that an RTL campaign cannot see either of the two
  things this document built. That bullet got longer because the result
  came in, not shorter.

Nothing in sections 5, 6 or 7 moved, because no number in them ever
depended on the campaign.

### 9.3 Nothing outside the register file changed either

The register-file strata were never the risk here: C5 proves that
datapath computes the same function. **The risk was everything else** —
a fault port and a peripheral could have perturbed the core's timing
through the synthesiser, and the campaign runs RTL, where they cannot,
but the campaign is also the only thing that would have shown it if the
elaboration had drifted.

Every stratum outside the register file is identical, per class, in both
the armed and the disarmed table **[fact]**: `fetch_fifo` 9 SDC,
`controller` 8, `id_ctrl` 8, `multdiv` 7, `if_id` 5, and 0 in
`pc_fetch`, `lsu`, `csr_trap`, `csr_pmp`, `csr_cnt`, `csr_debug` and
`top_ctrl`. The disarmed HANG column is the same 13 in the same five
strata. `docs/42` section 6.3's other half stands where it stood:
**`controller` still carries the highest per-bit rate in the core at 13
of 100 into fifteen flip-flops, and nothing in this document goes near
it.**

The site table is identical too, down to the single-digit rows:
`debug_mode_q` 7 of 7, `instr_valid_id_q` 1 of 1, `ls_fsm_cs` 3 HANG of
7, `ctrl_fsm_cs` 1 SDC and 5 HANG of 28, `rdata_q` 8 of 72, `imd_val_q`
8 of 96 **[fact, section 7 of both logs]**.

### 9.4 What the mechanisms did, and one row that must not be misread

`docs/43`'s section 6 of the report, on this build **[fact]**:

| mechanism | count |
|---|---:|
| register file, single-bit corrected | **190** of 1,400 injections |
| of those, ended with the golden answer | **190** |
| register file, **uncorrectable** seen | **0** |
| W7, a kick rejected as too early | **0** |
| W8, a phase out of kicks | **0** |
| escalations, of which early kicks / spent budgets | 62, of which **0 / 0** |

**190 corrections, 190 of them golden, and zero uncorrectable syndromes
in 1,400 injections** is the register file working, and it is the same
190 `docs/43` measured. It is also the first time those corrections are
counted by something other than a testbench: section 8.2 is where the
same events are read by a load instruction.

**And the two zeros must not be read as evidence about W7 or W8.** This
is campaign A's configuration: `WINS = 0` and the kick budget disarmed,
which is the inert setting, and `soc_wdog.sby`'s property **W7b**
*proves* that neither mechanism can fire there. So "W7 fired 0 times" in
this table is a **consistency check on the proof**, not a measurement of
W7's value — a nonzero entry would have meant the block was firing in a
configuration where it is provably unable to. All 62 escalations are
ordinary expiries, which is what a watchdog with no contract armed can
produce and all it can produce.

**Where W7's actual value is measured, and what this document defers
to.** `docs/43` section 8.4 armed it on a rewritten workload and found 0
of 30 dead machines caught and 7 spurious escalations in 1,232
survivable upsets. `docs/46-watchdog-window-decision.md` takes that
question further on a second workload and **recommends removing W7
before floorplanning**. Nothing in this document argues otherwise, and
nothing in it depends on W7 either way: the fault line this document
adds to the watchdog is `tmr_ev_o`, which is `prot_mismatch` from W6's
voter. That signal exists at `WINDOW = 0`, so `CNT_TMRERR` and its
interrupt survive W7's removal untouched.

### 9.5 What running it cost, and a harness defect found on the way

2,800 simulations at nine concurrent processes, sharing a 20-thread host
with a second campaign that was not this document's, **3 h 3 m of wall
time** — 08:01 to 11:04 **[fact, the campaign's start and the
`records.csv` timestamp]**.

**That is not the interval `docs/42` and `docs/43` quote and the
difference is worth one sentence**, because quoting the same-shaped
number for a differently-shaped thing is how a cost gets understated.
Those documents measure from `tb_soc_fi.vvp` to `records.csv`, which
here is 3 h 43 m: this build was elaborated at 07:20 and the run that
produced the records began forty minutes later, an earlier attempt
having been abandoned. `docs/43` measured 5,600 simulations in 1 h
17 m at sixteen concurrent processes with the machine to itself: **72.7
simulations a minute against this run's 15.3, and 4.5 against 1.7 per
process** **[estimate, arithmetic on two measured intervals]**. The
per-process figure is the one that says what happened — this host was
oversubscribed by a factor of about two and a half, which is the machine
being shared and not the design being slower.

**A record-for-record replay would have been the better experiment and
was not practical, for a reason worth writing down.**
`campaign.py --directed` replays an explicit record list — the same
draws, `was` beside `now`, which is exactly the comparison section 9.2
ended up getting for free. It **accepts `--jobs` and ignores it**: the
directed loop runs the two simulations of each record serially. Measured
at 0.67 records per minute under load, 1,400 records is about 35 hours
against roughly 3 for the same work through the parallel path. That is a
defect of the harness rather than of a measurement — it is why
`docs/43` section 5.4's four-record replays were quick and a
1,400-record one is not attempted by anybody — and it is section 11 item
6.

---

## 10. What this does NOT cover

Stated at length, because this repository has been bitten by a green
check read as wider than the thing it examined thirteen times —
`docs/28` 4.4a, `docs/34` 8.5, `docs/36` 3.3, `docs/38` 7.3 and 8.2,
`docs/39` 3, twice in `docs/40`, `docs/41` 8.4, `docs/42` 5.1, and
`docs/43` 9.5 and 9.6.

- **An identical campaign is not a wider one.** Section 9.2's result is
  that nothing moved; it is not that anything was learned about the
  design's fault behaviour that `docs/43` had not already measured.
  Every limit `docs/43` section 8 puts on those numbers is inherited
  verbatim — one workload, one seed, RTL only, single-bit only, an
  oracle that sees the run's output and not the machine's architectural
  state, and zero rows that mean "below about 3.7 %". **In particular
  the campaign says nothing about the two things this document actually
  built.** It injects into the RTL, where `FASTCORR` is a different
  expression for the same function and the fault port drives a counter
  nothing in the workload reads; a campaign that could see either would
  have to be at gate level, and section 11 item 3 is that.
- **The timing instrument cannot resolve the effect it measures.**
  Section 5.2. Two controlled pairs move the reported whole-core slack by
  0.1585 ns and 0.3988 ns for changes that are provably off the read
  path, and one critical path's tail moves by 1.1526 ns on identical
  RTL. **Every whole-core timing delta in `docs/38`, `docs/43` and this
  document smaller than about 0.4 ns is inside the noise**, including
  `docs/38` section 8.5's 0.27 ns for lockstep. Section 5.4's module
  measurement is not subject to this and is the only number here that
  attributes a delay to a structure.
- **No place-and-route, and section 5.3 now depends on that more than
  before.** The 56.8 MHz is set by an unbuffered 2,328-fanout reset net.
  A reset tree would change it, and nothing here predicts by how much.
  Equally, the tie-off frequencies of section 5.3 are pre-layout with no
  parasitics and no clock tree, and on this project's history they move
  down.
- **The tie-off recipe constrains one input.** `soc_top.v` ties a dozen;
  section 5.1 says why only `cheriot_enable_i` is constrained and that a
  fuller case analysis would report a smaller design on a bigger
  assumption. Neither recipe is the truth; both are reported.
- **`CNT_RFRD` and `CNT_RFDED` do not count corrections that happen
  while Ibex's read address is still X in simulation.** Section 6.5.
  This is a simulation artefact of an unreset upstream flip-flop, it
  applies to `docs/43`'s own bench counters too, and it means the
  software-visible read-port count is a lower bound in every simulation
  in this repository.
- **`CNT_RFSEC` is an upset count only while the scrub reaches every
  register.** Its period is data-dependent and unbounded in the limit —
  `docs/43` section 6.4, still open. A register the program overwrites
  before the scrub arrives sheds its upset uncounted, so **this counter
  is a lower bound on the upset rate and not an estimate of it.**
- **`soc_busstat` is not protected.** No code, no replication. An upset
  in a counter corrupts a number, and an upset in a sticky erases a
  report. The block that exists to report faults is the block in this
  SoC least able to survive one, and the argument for leaving it that way
  is only that its corruption is loud in one direction and silent in the
  other, which is not much of an argument.
- **Nothing here protects the register file's addresses**, and nothing
  here is a fault model for the codec's own combinational logic. The
  SECDED decoder is a large combinational cone on a critical path and a
  single-event transient in it is outside every measurement in this
  repository.
- **The interrupt has never fired in a program.** Section 8.2 reads the
  counters at the end of a run; no software here enables `IRQEN`, takes
  the interrupt, or acknowledges it. `test_soc_busstat` exercises the
  line at the block's ports and that is all.
- **One workload, one seed, RTL only, single-bit only**, with an oracle
  that sees the run's output and not the machine's architectural state —
  `docs/42` section 9's first bullet, unchanged.
- **`soc_top.v` has still never been synthesised as one design.**

---

## 11. What the next block should be

1. **`mtime`.** `docs/41` section 7.4 ranked it above everything it left
   unprotected, `docs/43` section 12 ranked it second, and section 3
   above says why it is not here. It is now the oldest open item in the
   SoC and it is the only one that has been deferred three documents
   running. A 64-bit counter that the whole timing subsystem reads and
   that no code protects is not a hard problem; it is a problem that
   keeps losing to more interesting ones.

2. **Protect BUSSTAT, or state that it will not be.** Section 10 names
   the shape: the block whose job is to report faults is the block least
   able to survive one. An upset in a sticky erases a report and an
   upset in a counter corrupts a number. The watchdog's W6 is the
   pattern and its price is known — `docs/41` section 6.5 measured
   +5,091 um2 for a 22-bit word — so this is a decision with a number
   behind it rather than an open question. **A saturating counter is a
   bad TMR candidate and a good parity one**, which is a design input
   that did not exist before this block did.

3. **A gate-level campaign on the core**, which `docs/42` section 4.4
   named and `docs/43` section 12 ranked third and which this document
   makes more valuable again: the SECDED decoder's read path is now a
   different cone from the one `docs/43` measured, the netlist has 31
   fewer check flip-flops than the RTL, and neither difference is
   visible to an RTL campaign.

4. **Place and route one SoC block, and re-read section 5.3 after.**
   Two of this document's three timing corrections are about artefacts
   that only exist before layout — an unbuffered reset net and a
   free-floating configuration input. Until something is placed and
   routed, every frequency in this repository is a synthesis number
   about a netlist with no clock tree, and section 5.2 now says those
   numbers have about 0.4 ns of noise as well.

5. **A software supervisor that reads BUSSTAT and does something.**
   The counters exist and nothing polls them. `docs/42` section 10's
   third bullet — "the recovery policy is more software than
   hardware" — has a new instrument to be written against, and until it
   is, section 8.2's demonstration is the whole of the evidence that
   this feature is usable.

6. **Give `campaign.py --directed` the `--jobs` it already accepts.**
   Section 9.5. It is the mode that produces a record-for-record
   comparison instead of an aggregate, it is the mode every future
   hardening's evidence would be stronger for, and it is serial — 35
   hours against 3 for the same 1,400 records. This document got the
   record-for-record answer only because the delta happened to be
   exactly zero and a `diff` could say so; a document whose delta is
   small and nonzero will not be that lucky.

---

## 12. Corrections to earlier documents

- **`docs/43` section 7.4**, "the decoder sits on the register read path
  and the register read path feeds the ALU", as an explanation of the
  0.6926 ns and the 5.8 MHz. The *sentence* is true of the design;
  neither number measures it. The slack figures come from a path that
  starts at a configuration input `soc_top.v` ties to a constant
  (section 5.1) and the frequency figures from an unbuffered reset net
  (section 5.3). The measurement of the decoder's own cost is section
  5.4's **2.7928 ns on the read path**.
- **`docs/43` section 7.4**'s hold note said the hardened design "is not
  being credited with improving hold" because 5.6 ps is noise. Section
  5.2 now puts a number on how much noise this flow has, and it is much
  larger than 5.6 ps; the note was right and was righter than it knew.
- **`docs/38` section 8.6**, "bisection on the clock period,
  re-synthesising at every probe, so that the number `abc` optimises for
  and the number STA checks are the same number". The re-synthesis
  happens and the optimisation does not: `abc -D` is in picoseconds and
  every probe passes a nanosecond figure, so all eight probes produce a
  byte-identical netlist (section 5.3a). The frequencies stand; the
  rationale does not.
- **`docs/38` section 8.5**'s 0.27 ns for `SecureIbex` is inside the
  noise measured in section 5.2 and should be read as "no measurable
  difference", not as a small one.
- **`docs/43` section 6.5 and section 10 bullet 1** — "the correction is
  invisible outside a simulator", "this design cannot tell an operator
  that it is being hit" — are closed by section 8.2 and are no longer
  true of the design.
- **`docs/43` section 12 item 1** is done for the register file and for
  TMRERR. Item 2, `mtime`, is not; section 3 says so.
- **`docs/46-watchdog-window-decision.md`** recommends removing W7
  before floorplanning, and **nothing in this document contests that.**
  Section 9.4 says why the two zeros beside W7 and W8 in this campaign
  are not evidence either way — they are the inert configuration
  behaving as `soc_wdog.sby`'s W7b proves it must. The one place this
  document touches the watchdog is `tmr_ev_o`, and that signal is W6's
  `prot_mismatch`, which exists at `WINDOW = 0`: **`CNT_TMRERR`, its
  sticky and its interrupt all survive W7's removal without a line
  changing.** If W7 goes, section 7.2's `soc_wdog` area row goes with
  it and this document's +115.97 um2 observation about the port becomes
  a measurement of a block that no longer exists in that configuration;
  the fault line does not.
- **`docs/41` section 10 item 3**, "Nothing raises an alarm on TMRERR …
  A fault line into BUSSTAT, or a fast interrupt, is the obvious next
  step and neither exists" — the fault line exists and reaches
  `CNT_TMRERR`; the interrupt exists and is disabled at reset.
- **`docs/43` section 9.2**'s test
  `test_the_report_costs_nothing_because_nothing_can_read_it` said in its
  own docstring that a future change giving the report a port would fail
  there, "and that failure would be the good news". It failed. It is now
  two assertions: the bench counters still cost nothing, and the port
  exists.

---

## 13. Files touched

`docs/34` section 2 pins the pilot by git blob hash of the files in
`hw/rtl/` and section 5 lists the flow configs. **Nothing in either set
is modified** **[fact]**.

| File | Change |
|---|---|
| `hw/soc/rtl/soc_busstat.v` | new — the counters |
| `hw/soc/flow/ibex_fault_port.py` | new — the `ibex_top` patch |
| `hw/soc/flow/sta_regfile.sh` | new — the read path, timed on its own |
| `hw/soc/sta/ibex_tieoffs.sdc` | new — the SoC's tie-offs as a case analysis |
| `hw/soc/formal/soc_busstat_props.v`, `soc_busstat.sby` | new — B1–B6 |
| `hw/soc/tb/cocotb/test_soc_busstat.py`, `Makefile.soc_busstat` | new — ten tests |
| `hw/soc/rtl/ibex_regfile_secded.v` | `rf_ecc_err_o`, `FASTCORR`, `SYNPRE` |
| `hw/soc/rtl/soc_wdog.v`, `soc_gptimer.v` | `tmr_ev_o` |
| `hw/soc/rtl/soc_top.v` | the block, the two fault lines, fast line 10 |
| `hw/soc/formal/regfile_secded_props.v` | C5 and its two covers |
| `hw/soc/formal/Makefile` | the `busstat` target |
| `hw/soc/flow/ibex_sources.sh` | `IBEX_FAULT_PORT` |
| `hw/soc/flow/syn_ibex.sh`, `syn/ibex_syn.ys.in` | `IBEX_RF_FASTCORR`, `IBEX_RF_SYNPRE` |
| `hw/soc/flow/sta_ibex.sh`, `sta/ibex_sta.tcl.in` | `SOC_TIEOFFS` |
| `hw/soc/flow/sweep_ibex.sh` | `SWEEP_TAG`, so three sweeps can run at once |
| `hw/soc/flow/syn_regfile.sh` | the `slowcorr` and `synpre` rows, and an STA netlist |
| `hw/soc/flow/syn_soc.sh`, `sim_soc.sh`, `fi_core.sh` | `soc_busstat.v`, and `IBEX_FAULT_PORT=1` |
| `hw/soc/tb/tb_soc_fi.v`, `tb/sw/fi_workload.c`, `tb/sw/soc_timers.h` | the software-visible readout, behind `FI_BUSSTAT` |
| `sw/tests/test_soc_regfile_guards.py` | the port guard weakened and stated; the folding check |
| `sw/tests/test_soc_synthesis_guards.py` | the counter census, the connection, the patch |
| `regmap/memmap.yaml` | BUSSTAT `reserved` → `implemented`, and its description |
| `docs/memmap-soc.md`, `sw/golden/memmap_gen.py` | generated from it |
| `.gitignore` | `hw/soc/genp/`, and the new sby working directories |
| `docs/44-margin-and-observability.md` | this document |
| `docs/00-index.md` | one row |

**`hw/rtl/secded_enc.v`, `secded_dec.v` and `tmr_voter.v` are read and not
modified.** The register file instantiates the first two in place — and
now uses the first to *derive* the correction mask's columns, so this
document adds one more reason the codec must stay a single copy rather
than weakening the argument for it.

---

## 14. Reproducing this

```
make -f hw/soc/tools.soc.mk fetch-ibex fetch-sv2v fetch-rvgcc
hw/soc/flow/sv2v_ibex.sh hw/soc/ext/ibex hw/soc/gen \
                         hw/soc/tools/sv2v-Linux/sv2v

# behaviour is unchanged: 22 checks, 185,443 cycles
hw/soc/flow/sim_soc.sh

cd hw/soc/tb/cocotb
for m in soc_bus soc_apb_bridge soc_clint soc_gptimer soc_wdog \
         soc_wdog_win soc_wdog_fi ibex_regfile_secded soc_busstat; do
  make -f Makefile.$m
done

cd hw/soc/formal && make            # seven jobs, twenty-nine tasks

.venv/bin/python -m pytest sw/tests

# ---- area and timing -------------------------------------------------
# The baseline, and docs/43's own file restored, both of which must
# reproduce byte-identically before anything else is believed.
IBEX_REGFILE=upstream hw/soc/flow/syn_ibex.sh small-pmp 20 hw/soc/out/h44-base
IBEX_REGFILE=secded IBEX_RF_FASTCORR=default \
  hw/soc/flow/syn_ibex.sh small-pmp 20 hw/soc/out/h44-doc43   # docs/43's file
IBEX_REGFILE=secded IBEX_RF_FASTCORR=0 \
  hw/soc/flow/syn_ibex.sh small-pmp 20 hw/soc/out/h44-slowcorr
IBEX_REGFILE=secded IBEX_RF_FASTCORR=1 \
  hw/soc/flow/syn_ibex.sh small-pmp 20 hw/soc/out/h44-fast
IBEX_REGFILE=secded IBEX_FAULT_PORT=1 \
  hw/soc/flow/syn_ibex.sh small-pmp 20 hw/soc/out/h44-port     # as shipped
IBEX_REGFILE=secded IBEX_RF_SYNPRE=1 \
  hw/soc/flow/syn_ibex.sh small-pmp 20 hw/soc/out/h44-synpre
for d in h44-base h44-doc43 h44-slowcorr h44-fast h44-port h44-synpre; do
  hw/soc/flow/sta_ibex.sh small-pmp 20 hw/soc/out/$d           # default recipe
done

# The false path of section 5.1, seen rather than argued:
grep -c "Startpoint: cheriot_enable_i" \
     hw/soc/out/h44-doc43/small-pmp/sta.log     # 30 = 10 paths x 3 corners

# The same netlists with the SoC's tie-offs applied, and the bisection
# that needs no synthesis because section 5.3a measured that the netlist
# does not depend on the period.
for d in h44-base h44-doc43 h44-slowcorr h44-fast h44-port h44-synpre; do
  lo=8; hi=22
  for i in $(seq 10); do
    p=$(python3 -c "print(f'{($lo+$hi)/2:.2f}')")
    s=$(SOC_TIEOFFS=1 hw/soc/flow/sta_ibex.sh small-pmp $p hw/soc/out/$d \
        | awk '$1=="GATE" && $2=="setup_sync"{print $3}')
    if [ "$(python3 -c "print(1 if $s>=0 else 0)")" = 1 ]; then hi=$p; else lo=$p; fi
  done
  echo "$d closes setup_sync at $hi ns"
done

# The frequency table of section 5.3, by docs/38 section 8.6's method.
IBEX_REGFILE=upstream SWEEP_TAG=h44base \
  hw/soc/flow/sweep_ibex.sh small-pmp 14 20 7                  # 62.6 MHz
IBEX_REGFILE=secded IBEX_RF_FASTCORR=0 SWEEP_TAG=h44slow \
  hw/soc/flow/sweep_ibex.sh small-pmp 15 22 7                  # 56.8 MHz
IBEX_REGFILE=secded IBEX_RF_FASTCORR=1 SWEEP_TAG=h44fast \
  hw/soc/flow/sweep_ibex.sh small-pmp 15 22 7                  # 56.8 MHz
# and the fact that makes section 5.3a a correction:
md5sum hw/soc/out/sweep-small-pmp-setup_all-h44base/p*/small-pmp/ibex_top.netlist.v

# The register file alone, which is where the recovery is measurable.
hw/soc/flow/syn_regfile.sh                     # six configurations
hw/soc/flow/sta_regfile.sh                     # their read paths
hw/soc/flow/syn_soc.sh soc_busstat             # 442 cells, 72 flops
hw/soc/flow/syn_soc.sh soc_wdog                # 1,035 cells, 131 flops

# ---- the campaign, and the demonstration -----------------------------
hw/soc/flow/fi_core.sh     hw/soc/out/fi-h44
hw/soc/flow/fi_coverage.sh hw/soc/out/fi-h44
FI_REGFILE=secded hw/soc/fi/campaign.py --build hw/soc/out/fi-h44 \
                  --draws 100 --jobs 18

# Section 9.2's result, which is the whole delta:
md5sum hw/soc/out/fi-h1/records.csv hw/soc/out/fi-h44/records.csv
diff   hw/soc/out/fi-h1/campaign.log hw/soc/out/fi-h44/campaign.log

# Section 8.2. The build that reads BUSSTAT from software; its ROM image
# is NOT byte-identical to docs/42's and it is not used for the campaign.
SW_DEFINES=-DFI_BUSSTAT hw/soc/flow/fi_core.sh hw/soc/out/fi-bst
vvp hw/soc/out/fi-bst/tb_soc_fi.vvp +budget=61940            # all zero
for bc in "24 14073" "15 9940" "29 9670" "3 5720"; do
  set -- $bc
  vvp hw/soc/out/fi-bst/tb_soc_fi.vvp +site=22 +bit=$1 +cycle=$2 \
      +budget=61940 | grep -E "RECORD (sig|rf_sec|sw_bst)"
done
```

`hw/soc/out/` and `hw/soc/genp/` are gitignored, by the rule `docs/38`
section 11 already applies: fetched or generated, never vendored.
