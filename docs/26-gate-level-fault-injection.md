# 26 — Gate-level fault injection on the submission netlist

Status: complete. **522 single-event upsets were injected into 334
mapped flip-flops of the placed-and-routed submission netlist. 357 of
them are exact like-for-like matches with the RTL campaign of record —
same target, same bit, same drawn cycle — and 355 of the 357 classify
identically.** Every hardening claim the pilot makes survives the step
from RTL to netlist. Two records disagree, both the same construction,
and section 6 takes them apart rather than smoothing them: at RTL the
two bounded-wait nets deadlock and return a wrong answer that an upset
in the report can hide, and **on the netlist the same construction
recovers with the golden answer at every placement tested**, so the two
SDC records `docs/16` section 5.8 rests its wave-6 ranking on do not
reproduce at gate level. The erasable one-bit report itself reproduces
exactly.

### Headline

- **The injector models an upset, and that is measured before anything
  is counted.** A one-cycle `Force` on a mapped flip-flop's `Q` net,
  released after one active clock edge. Section 4 proves on this netlist
  that the flip-flop *captures* the corruption (it reads back through
  the register port long after release) and that a **reset clears it,
  while a deposit on the same net survives the reset** — the experiment
  that separates a real upset from the stuck-at the RTL technique would
  have modelled here.
- **The pointer TMR now has functional netlist evidence: 72 of 72
  CORRECTED**, into 36 distinct replica flip-flops. `docs/16` section
  3.3 records that the day before this group was retargeted, the same 24
  phases reported 23 SDC against the same working hardware; `docs/22`
  section 9's cell count was until now the only netlist-level evidence.
- **The configuration TMR is three independent banks, bit for bit.** All
  165 replica flip-flops injected once each: **165 CORRECTED, 0 SDC,
  0 MASKED**. This is the question `docs/16` section 4 could not ask,
  asked exhaustively of the design that will be manufactured.
- **Every sequential element of this netlist is reachable this way.**
  All 1,275 flip-flops drive a named net; 1,170 keep an RTL-derived
  name, and 101 of the remaining 105 are inside replicated banks whose
  identity is still in the name. The 26 % that was injected into is the
  RTL campaign's sampling policy, not a ceiling.
- **Gate level costs 4.1x per injection**, not an order of magnitude.
  The whole campaign is 55 minutes.
- **Two by-products of building the target map**: `u_lif.out_event[14]`
  is an RTL injection into a flip-flop synthesis proved constant and
  removed, and `cfg_axon[3]` survives with no name at all and had to be
  identified by a controlled experiment (sections 3.3 and 5.4).

New files, and nothing else is touched: `hw/tb/Makefile.glfi`,
`hw/tb/test_gl_fi.py`, `hw/tb/gl_fi_results.json`. Build products land in
`hw/tb/sim_build_glfi_shape-6x2/` and `hw/tb/results_glfi_shape-6x2.xml`,
both already matched by existing `.gitignore` lines (`hw/tb/sim_build*/`,
`hw/tb/results_*.xml`); no ignore line was added.

This closes `docs/24` section 8.2 item 2 and section 8.3 item 4.

---

## 1. What was run against what

### 1.1 The netlist, the models and the tools

| | |
|---|---|
| Netlist | `hw/openlane/pilot_ihp/runs/shape-6x2/final/nl/tt_um_melihakbulut_nssoc.nl.v` |
| git blob | `e8f72bde4c5a02101a226f5d98bde36c1229c084` |
| Modules in it | 1 — fully flattened, `SYNTH_HIERARCHY_MODE: deferred_flatten` |
| Sequential cells | **1,275**, every one a `sg13g2_dfrbpq_1`; no latch, no macro |
| Cell models | `.../ihp-sg13g2/libs.ref/sg13g2_stdcell/verilog/sg13g2_stdcell.v`, blob `c4efa342f0d1f6a523c6a03bac258ef6e3729556` |
| Simulator | Icarus 13.0 stable, `-gspecify`, zero-delay functional run |
| cocotb | 2.0.1, project venv |

**[fact, `make -f Makefile.glfi provenance`]**. This is the same netlist,
the same models and the same Icarus that `docs/24` used, resolved the
same way — out of the run's own `resolved.json`, never "the latest run"
and never whichever PDK `~/.ciel` currently symlinks. `Makefile.glfi`
carries `docs/24` section 3.1's version guard verbatim, and it matters
more here than there: under Icarus 12 every flip-flop in the netlist
clocks on `z`, so this suite would report every injection MASKED, which
reads like a perfectly hardened chip.

`make -f tools.mk toolcheck` passes (yosys `0.67+146`, matching the pin).
It does not govern this run, for the two reasons `docs/24` section 3
records: Icarus 12 cannot simulate these models and the pinned
oss-cad-suite Icarus cannot host cocotb here. The deviation is the same
one, recorded again rather than inherited silently.

### 1.2 The RTL campaign this is compared against

`hw/tb/fi_campaign_results.json`, blob
`3906c53d1f7e9da31dd050f2498e464ce03e13c5`, **365 injections**, seed
`0x16F12026`, geometry 8 x 8 — the log committed at `a13a93f` after the
safety-net groups were added. The netlist's elaborated geometry is
8 x 8 as well **[fact: 128 `vmem` flops = 8 neurons x 16 bits, 48 `smem`
= 8 x 6, 32 `wchk` = 4 words x 8]**, so the two campaigns are comparable
without a geometry argument.

Two things about that log are checked here rather than assumed, and both
are **[fact]**:

1. **It was produced from the RTL the netlist came from.** `hw/rtl/` at
   `a13a93f` is byte-identical to `hw/rtl/` at `e1361fe`, the commit
   `hw/openlane/pin_rtl.py` pinned the `shape-6x2` harden against
   (`docs/24` section 1.2). Verified per file with `git rev-parse`. The
   two campaigns therefore describe the same design at two levels, not
   two designs.
2. **The blob is quoted because that file moves.** It is produced by a
   different suite, it was regenerated once during this work, and
   `hw/rtl/pilot_top.v` is under concurrent edit in the working tree as
   this is written. Every number in section 5 is against those bytes.
   A later RTL campaign, especially one run against modified RTL, is a
   different comparison and this document does not claim to describe
   it — and if the RTL moves, the gate-level side is the one still
   describing the netlist that is being manufactured.

---

## 2. The method, and the three mechanisms that were rejected

### 2.1 The wall

`docs/24` section 4.3 already measured why the RTL campaign's technique
does not transfer. A cocotb value assignment is a **deposit**, and on a
netlist net a deposit is held until that net's *driver* re-evaluates. The
driver is a standard cell whose output does not change while the design
holds its state, so the deposit becomes a permanent fault on the node.
That is the identical error `docs/16` records the fault injector making
once before — the pointer TMR measured 23 SDC of 24 against a working
majority vote until the target was moved off the voted wire — and
repeating it here to raise an injection count would be a regression, not
a result.

### 2.2 What was chosen

**A `Force` on the net driven by a mapped flip-flop's `Q` pin, held for
exactly one clock period, then `Release`.** The force is applied 3 ns
past a rising edge — the same offset the RTL campaign uses, and for the
same recorded reason, that an injection made *on* the edge is overwritten
by that edge's own update before anything samples it — and released 3 ns
past the next rising edge. The window therefore spans exactly one active
clock edge:

- during the window the fan-out cone sees the corrupted value, so the
  fault propagates as an upset would;
- at the edge inside the window the driving flip-flop samples its own `D`
  input, which was computed from the corrupted value. Where the register
  holds — an enable implemented as a feedback mux, which is the only way
  to build one from `sg13g2_dfrbpq_1`, since it has no enable pin — that
  `D` *is* the corrupted value, so the flop captures the corruption and
  the upset persists after release. Where the register is reloaded every
  cycle the flop captures the new value and the upset does not persist.
  **The injector decides neither; the design's own next-state logic
  does**, which is precisely the property a deposit destroys;
- on release the net returns to the cell's drive, so nothing is held on a
  wire and there is no stuck-at.

Section 3 does not assert any of that. It measures it.

### 2.3 The three rejections, with the evidence

**Driving the flip-flop model's internal state.** Impossible in these
models, not merely inconvenient. The whole functional body of
`sg13g2_dfrbpq_1` is:

```verilog
not (int_fwire_r, delayed_RESET_B);
ihp_dff_r_err (xcr_0, delayed_CLK, delayed_D, int_fwire_r);
ihp_dff_r (int_fwire_IQ, notifier, delayed_CLK, delayed_D, int_fwire_r, xcr_0);
buf (Q, int_fwire_IQ);
```

**[fact, read out of the models blob above]**. The state is the output of
an *unnamed* UDP instance. There is no `q` reg of the kind sky130's
models expose, the UDP instances have no names to reach through VPI, and
UDP state is not writable through VPI in any case. `int_fwire_IQ` is
reachable, but it is a net driven by that UDP and buffered straight to
`Q`, so forcing it is the same experiment as forcing `Q` and no closer to
the storage.

**A modified cell model with an injection port.** Rejected on provenance.
`Makefile.gl` resolves the models out of the run's own `resolved.json`
precisely so that what is under the simulator is what hardened the
netlist; there are two `ihp-sg13g2` versions installed on this machine
and guessing would be a coin flip. A local edit of that file makes every
number in this document conditional on a patch, and the patch would have
to be trusted at exactly the point where the purpose of the exercise is
to stop trusting an abstraction. It would also have to be re-applied,
correctly, on every machine that reproduces this.

**SDF annotation.** Rejected as irrelevant to the problem. SDF changes
delays, not the name space, so it makes no flip-flop reachable that is
not reachable now — and reachability, not timing, is what section 4.3 of
`docs/24` identified as the obstacle. Icarus does not implement the
timing checks that would make an annotated run say more than the
post-route STA already in the same run directory (`docs/23` section 3,
`docs/24` section 2.2). SDF files for all three corners are present at
`final/sdf/` if that ever changes.

---

## 3. Reaching the flip-flops at all

### 3.1 The name index

`deferred_flatten` leaves one module, but the names survive as single
escaped identifiers containing dots: `\u_pilot.u_lif.state[0]` is a wire
in the netlist. cocotb cannot look those up, because `vpi_handle_by_name`
splits on `.`. `test_gl_fi.py` therefore iterates the whole top-level
scope once and keys the handles on `_name`: **46,155 named children in
0.5 s** **[fact, measured]**, of which the injectable ones are the
**1,275** nets that a `sg13g2_dfrbpq_1` `Q` pin drives.

That set is parsed out of the netlist file itself, not inferred from
names. A target that does not resolve into it is **not injected**; it is
reported as unreachable with the reason. That rule is the one thing
standing between this suite and a new spelling of the pointer-TMR
mistake.

### 3.2 What synthesis renamed, and how each rename was justified

The RTL campaign's target paths do not all exist in the netlist, and the
differences are not cosmetic — they are real storage under another name.
Every mapping below is justified by the RTL line that causes it.

| RTL target | Netlist net | Why |
|---|---|---|
| `u_lif.wmem[i]` bit `b` | `u_pilot.u_lif.w_data_all[4*i+b]` | `lif_core.v` 570: `assign w_data_all[gw*64+gk*4 +: 4] = wmem[gw*WPW+gk]`, `WPW=16`, so the index arithmetic collapses to `4*i+b` for every `i` |
| `u_lif.out_pend` | `u_pilot.lif_out_valid` | `lif_core.v` 707: `assign out_valid = out_pend` |
| `u_lif.out_event[b]` | `u_pilot.lif_out_event[b]`, `b < 10` only | `lif_core.v` 851: `out_event <= {2'b00, 4'b0000, spike_id}` |
| `u_evq_in.drop_cnt[b]` | `u_pilot.fi_drop[b]` | `pilot_top.v` 1197: `.drop_cnt(fi_drop)` |
| `u_evq_out.rd_valid` / `rd_data[b]` | `u_pilot.fo_rd_valid` / `fo_rd_data[b]` | `pilot_top.v` 1240-1241 |
| `oh_valid` | `aer_out_vld` | `pilot_top.v` 1329: `assign aer_out_vld = oh_valid` |
| `sticky_sec` / `sticky_ded` / `sticky_tmr` | `sec_seen` / `ded_seen` / `tmr_seen` | `pilot_top.v` 1907-1909 |
| `evw[b]` | `u_pilot.ev_id[b]` (`b<10`), `u_pilot.evw[b]` (`10..13`), `u_pilot.ev_type[b-14]` | `pilot_top.v` 1438-1439: `ev_id = evw[9:0]`, `ev_type = evw[15:14]` |

In every case yosys kept one name for a group of aliased nets and it is
not always the one the RTL campaign uses. The 16-bit `evw` is the
clearest: all sixteen flip-flops survive, under three different names.

### 3.3 Storage with no usable name at all, resolved by experiment

`cfg_axon[3]` is a writable bit of a writable register and **there is no
net of that name anywhere in the netlist** **[fact, zero matches for
`cfg_axon[3]`]**. Four flip-flops in the whole design carry a
yosys-internal name at the pilot level (`u_pilot._0252_` to
`u_pilot._0255_`), and guessing which is which is exactly the assumption
this suite exists not to make. It is measured instead: `test_00` writes
`CFG_AXON` with bit 3 clear, snapshots those four nets, writes it with
bit 3 set, snapshots again, and keeps whichever moved. **Exactly one
did: `u_pilot._0255_`** **[fact, logged]**. The bit is then injected like
any other.

### 3.4 Replicated banks, where the index survived only in part

Within a replicated bank, synthesis kept `bits[i]` as a net name for only
some of the flops:

| Bank | Flip-flops | Names of the form `bits[i]` |
|---|---|---|
| `u_cfg_a` | 55 | 51 |
| `u_cfg_b` | 55 | 4 |
| `u_cfg_c` | 55 | 29 |
| each of the 12 AER pointer replicas | 3 | 0 to 3 |

**[fact, parsed from the netlist]**. Of the 1,275 flip-flops, **1,170
keep an RTL-derived name and 105 do not — and 101 of those 105 are inside
a replicated bank**, with the remaining four the pilot-level anonymous
group of section 3.3.

The suite treats the two cases differently, on purpose:

- **AER pointer replicas.** The RTL campaign injects the *whole* width of
  every pointer bank (three bits, and each bank has exactly three
  flops), so assigning the unnamed flops to the unnamed bit indices in a
  deterministic order injects **provably the same set of flip-flops**.
  Group totals are therefore exact; only a per-bit label inside one bank
  may be permuted, and each record carries `bit_index_exact` saying
  which it is.
- **Configuration replicas.** The RTL campaign samples 5 of 55 bits, so
  the same trick would inject *different physical bits* under the RTL's
  labels. It is not done. Those targets are reported unreachable by
  name, and the domain is instead covered by a full sweep of all 165
  replica flip-flops (section 5.3), which is a stronger experiment than
  the RTL one rather than a weaker one.

### 3.5 What is not injectable, and why

`test_fi_campaign.fill_fifo_sentinel` has no gate-level equivalent. A
pre-fill written by deposit would be a stuck-at; written by force it
would evaporate on release. The two AER queue memories are therefore X
until the design writes them, exactly as `docs/24` section 6.2 measured.
An injection into a slot that is still X is not a bit flip, so it is
recorded as `SKIPPED_X` with the reason and **never classified** — a
campaign that quietly counted those as MASKED would be reporting
robustness it never tested.

---

## 4. Validating the method before trusting a number

`test_00_method` runs first and everything after it depends on it. Six
measurements, all on this netlist.

**A. The harness is not the variable.** An uninjected run through the
Tiny Tapeout pins reproduces the golden model exactly — event stream
`[1, 2, 5, 6, 4, 2]`, the whole neuron state file, no flag, no counter,
no fault pin **[fact]**. The stimulus, the workload, the weight seed, the
golden model and the classifier are imported from `test_fi_campaign`
rather than reimplemented, so this is the RTL campaign's own control run
executed against the netlist.

**B and C. The force reaches the design, and the flip-flop captures it.**
On `u_pilot.scratch[0]`, a flip-flop output by the parsed map:

| | |
|---|---|
| before | 0 |
| during the force | 1 |
| after release | 1 |
| four cycles later | 1 |
| `SCRATCH` read over the serial port | `0x00000001` |

**[fact, logged]**. The last row is the one that matters. `SCRATCH` is 32
flip-flops whose only job is to hold what the host wrote; reading a 1
back through the register port, long after the force is gone, means the
storage element itself holds the corrupted value. **That is the
difference between an upset and a glitch**, and it is measured rather
than argued. The design then overwrites it normally (`SCRATCH` written
to 0 reads 0), so the release genuinely returned the net to its cell.

**D. A deposit on the same net is a stuck-at.** Same target, same
instant, the RTL campaign's primitive:

| | |
|---|---|
| during the deposit | 1 |
| eight cycles later | 1 |
| **177 cycles later**, after a full serial read frame | still 1 |
| `SCRATCH` read | `0x00000001` |
| after a register write makes the driver re-evaluate | 0 |

**[fact, logged]**. The corruption lasted as long as the *injector* left
it there, not as long as the design took to recover from it. On a
one-cycle upset model that is a factor of 177 in exposure, in the
dangerous direction.

**D2. The two primitives on a live FSM.** `docs/24` section 4.3's
measurement, reproduced with both primitives at the same point of the
same stimulus:

| | before | during | one edge later | two edges later |
|---|---|---|---|---|
| deposit | `0000` | `0001` | `1001` | `1001` |
| force/release | `0000` | `0001` | `1001` | `1001` |

**[fact]**. They agree here, and the agreement is worth stating plainly:
on a target where the design's own reaction happens to hold the injected
bit — `lif_core` parks in `S_SAFE` and stays there — the two primitives
are indistinguishable. **The contrast is not visible on every target,
which is exactly why it cannot be checked on only one.**

**D3. The experiment that separates them outright.** A reset. After a
genuine upset the flip-flop holds the wrong value, so an asynchronous
reset — the design's own recovery — clears it. After a deposit the
flip-flop holds the *right* value and only the wire is wrong, so the
reset changes nothing on that node.

| `SCRATCH` after a hard reset | |
|---|---|
| upset by force/release | `0x00000000` — cleared, as a real upset must be |
| upset by deposit | `0x00000001` — survives a recovery no real upset survives |

**[fact, logged]**. This is the decisive one: the deposit models a fault
the manufactured chip cannot have, because no physical upset survives its
own reset.

**E. Agreement with a structure whose RTL outcome is already known.**
`lif_core`'s five legal FSM encodings are the even-parity words of a
four-bit vector, so every single-bit upset must land on an illegal word
and park the core with `ERR_CFG` raised. At gate level the probe returns
**DETECTED, `STATUS = 0x00000015`** **[fact]**, and the full `lif_fsm`
group agrees with the RTL campaign injection for injection (section 5).

---

## 5. The result

### 5.1 Headline numbers

| | |
|---|---|
| Gate-level injections | **522** |
| Distinct mapped flip-flops injected into | **334** of the netlist's 1,275 |
| Injections that are exact like-for-like matches with an RTL record | **357** |
| Of those, classifying **identically** | **355** |
| Classifying differently | **2**, and section 6 is about them |
| `SKIPPED_X` (the net was undefined when the injection was due) | **0** |
| `NOT_CONSTRUCTED` | **0** |
| Wall | 3,354.6 s for the whole suite, 3,322.4 s for the campaign |

**[fact, `hw/tb/gl_fi_results.json`]**. "Exact like-for-like" means the
same group, the same target, the same bit and the same drawn
`(burst, delay)` phase, matched record to record against the RTL log —
not a comparison of aggregates that happen to have the same shape.

Gate-level distribution over those 357, beside the RTL campaign's 365:

| | MASKED | CORRECTED | DETECTED | SDC | HANG |
|---|---|---|---|---|---|
| **Gate level**, 357 injections | 90 | 188 | 53 | 26 | 0 |
| **RTL**, 365 injections | 91 | 193 | 53 | 28 | 0 |

The eight-injection difference in the denominator is entirely the eight
targets section 5.4 lists as unreachable, each of which is MASKED,
CORRECTED or SDC at RTL. The two SDC records that are missing at gate
level are not among them: they are the two of section 6.

Over all 522 gate-level injections, including the 165 the RTL campaign
does not make: **90 MASKED, 353 CORRECTED, 53 DETECTED, 26 SDC, 0 HANG**.

### 5.2 Group by group

Twenty groups are **identical, record for record**: same count, same
class in every class.

| group | n | MASKED | CORRECTED | DETECTED | SDC | HANG |
|---|---|---|---|---|---|---|
| `lif_fsm` | 12 | 0 | 0 | 12 | 0 | 0 |
| `lif_vmem` | 24 | 0 | 24 | 0 | 0 | 0 |
| `lif_rmem` | 12 | 0 | 12 | 0 | 0 | 0 |
| `lif_wmem` | 16 | 3 | 13 | 0 | 0 | 0 |
| `lif_wmem_unread` | 4 | 4 | 0 | 0 | 0 | 0 |
| `lif_wchk` | 12 | 0 | 12 | 0 | 0 | 0 |
| `lif_wchk_unread` | 2 | 2 | 0 | 0 | 0 | 0 |
| `lif_smem` | 18 | 0 | 18 | 0 | 0 | 0 |
| `cfg_tmr_c` | 5 | 0 | 5 | 0 | 0 | 0 |
| `evq_ptr` | 72 | 0 | 72 | 0 | 0 | 0 |
| `evq_mem` | 32 | 25 | 0 | 0 | 7 | 0 |
| `evq_hold` | 14 | 7 | 0 | 1 | 6 | 0 |
| `dispatch` | 18 | 8 | 0 | 4 | 6 | 0 |
| `regbank_cnt` | 18 | 5 | 4 | 9 | 0 | 0 |
| `telemetry_primed` | 6 | 1 | 3 | 2 | 0 | 0 |
| `wdog_fetch` | 9 | 6 | 0 | 3 | 0 | 0 |
| `wdog_oh` | 9 | 6 | 0 | 3 | 0 | 0 |
| `ecc_port_single` | 12 | 0 | 12 | 0 | 0 | 0 |
| `ecc_port_double` | 4 | 0 | 0 | 4 | 0 | 0 |
| `ecc_ff` | 7 | 0 | 7 | 0 | 0 | 0 |

Four groups agree on **every injection that ran** and differ only in how
many ran, because a target has no flip-flop behind it in this netlist
(section 5.4): `cfg_tmr_a` 4 of 5, `cfg_tmr_b` 1 of 5, `lif_scan` 19 of
21, `regbank_cfg` 15 of 16. In each case the classes of the injections
that did run are equal to the RTL's for the same targets.

Two groups carry a real difference: `wdog_fetch_dir` and `wdog_oh_dir`,
one record each. Section 6.

**Three of these are worth naming for what they now mean.**

- **`evq_ptr`: 72 of 72 CORRECTED at gate level.** `docs/16` section 3.3
  records that the day before this group was retargeted it reported 23
  SDC of 24 against a working majority vote, because the injector was
  depositing on the voted wire. The gate-level run is the independent
  confirmation that could not be had before: **36 distinct pointer
  replica flip-flops in the placed-and-routed netlist**, every one
  injected, every upset masked at the outputs and counted in `CNT_TMR`.
  `docs/24` section 8.2 item 2 says the pointer TMR's only netlist-level
  evidence was `docs/22`'s flip-flop count. It is not any more.
- **`lif_fsm`: 12 of 12 DETECTED.** The HD-2 encoding argument holds on
  the mapped netlist, where nothing prevents a synthesiser from
  re-encoding a state register.
- **The whole SECDED domain is unchanged**: 12 of 12 single-bit weight
  words corrected, 4 of 4 doubles detected with the E10 substitution
  exact, and every coded-memory group (`lif_vmem`, `lif_rmem`,
  `lif_wmem`, `lif_wchk`, `lif_smem`, 82 injections) has **zero SDC** at
  gate level, exactly as at RTL.

### 5.3 The configuration TMR domain, swept flip-flop by flip-flop

This group has no RTL twin: the netlist makes a stronger experiment
possible than the RTL does.

`docs/16` section 4 records that yosys once merged the three
configuration replicas into a single physical bank, and that the RTL
test could not see it. `docs/24` section 5.2 answered that at the
netlist level with one functional test. This asks it of every stored
bit: **all 165 replica flip-flops — 55 in each of the three banks —
injected once each. 165 CORRECTED, 0 SDC, 0 MASKED** **[fact]**.

Zero MASKED matters as much as zero SDC. If any pair of banks shared
storage, an upset in the shared flop would corrupt two replicas at once
and the vote would carry it through; if a flop were dead, the injection
would come back MASKED. Neither happened for any of the 165. The three
banks are three independent registers of equal width in the design that
will be manufactured, and every bit of all three is voted and counted.

### 5.4 What could not be injected, and why

Seven targets, costing eight injections:

| target | reason |
|---|---|
| `u_cfg_a.bits[32]`, `u_cfg_b.bits[0,12,16,43]` | the name did not survive synthesis and the campaign samples 5 of 55 bits, so which flop carries the bit cannot be recovered (section 3.4). The domain is covered instead by the 165-flop sweep above |
| `u_lif.out_event[14]` | **there is no flip-flop.** `lif_core.v` 851 writes `out_event <= {2'b00, 4'b0000, spike_id}`, so bits 15:10 are constants and synthesis removed them: the netlist has ten, not sixteen. The RTL injection lands on storage the manufactured design does not have. It classifies MASKED at RTL, which is consistent — but it is not a measurement of anything |
| `ctrl_scrub_en` | no flip-flop of that name survives; the scrub-enable bit was absorbed into the logic it gates |

**[fact, all three, and the first two are checked against the parsed set
of flip-flop output nets rather than against a name search.]**

`SKIPPED_X` never fired. The mechanism of section 3.5 exists because the
AER queue memories have no sentinel fill at gate level and are X until
the design writes them, but **every one of the 32 `evq_mem` injections
landed on a defined bit** and the group matches the RTL exactly. The
absence of the sentinel is still a difference between the two harnesses
and section 6 is careful about it.

---

## 6. The disagreement

**Two of 357 like-for-like injections classify differently, and they are
the same case in each of the two bounded-wait safety nets.**

| | RTL | gate level |
|---|---|---|
| `wdog_fetch_dir` / `report_erased` | **SDC** | **MASKED** |
| `wdog_oh_dir` / `report_erased` | **SDC** | **MASKED** |

`docs/16` section 5.8 is built on those two records. Its headline — the
first in that document that is not an improvement — is that an upset
which clears the one-cycle timeout pulse in the single cycle it is high
"erases the report entirely: the design deadlocks, recovers, returns a
wrong answer, and reads `STATUS = 0x06` with every counter at zero and
every fault pin low", and its wave-6 ranking puts the −2 flip-flop fix
above all five other items.

### 6.1 The class label is not the finding; the output is

Underneath the two labels, four records differ, and they differ in the
same thing:

| construction | RTL event stream | gate-level event stream | golden |
|---|---|---|---|
| `wdog_fetch_dir` / `report_kept` (the control) | `[0, 1, 2, 3, 4, 2]` | `[1, 2, 5, 6, 4, 2]` | `[1, 2, 5, 6, 4, 2]` |
| `wdog_fetch_dir` / `report_erased` | `[0, 1, 2, 3, 4, 2]` | `[1, 2, 5, 6, 4, 2]` | same |
| `wdog_oh_dir` / `report_kept` | `[0, 1, 2, 3, 4, 2]` | `[1, 2, 5, 6, 4, 2]` | same |
| `wdog_oh_dir` / `report_erased` | `[0, 1, 2, 3, 4, 2]` | `[1, 2, 5, 6, 4, 2]` | same |

**[fact, both logs]**. **At gate level the deadlock-and-recovery returns
the golden answer.** The flags agree exactly — `STATUS` is `0x16` for
every `report_kept` and `0x06` for every `report_erased` at both levels,
so the erasable one-bit report is just as erasable in the netlist as in
the RTL. What does not reproduce is the *wrong answer* the erasure was
hiding. With a correct output and no flag, the gate-level record is
MASKED rather than SDC by the classifier's own rule, and the two SDC
records fall out of the residual.

Note that the RTL records themselves carry `spikes_ok = 0` with
`state_ok = 1`: at RTL the neuron state file is golden and only the
drained event stream is wrong, so the divergence is in the output path,
not in the inference.

### 6.2 It is not a placement artefact, and that was tested

A one-cycle difference in where the first deposit lands would explain
this as well as a difference between the two levels, so the two were
told apart before either was reported. The directed script anchors on
the first cycle `dstate` reads `D_IDLE` after `BUSY` rises; prepending a
wait moves the anchor to a later `D_IDLE`.

**Both constructions, in both nets, at six placements each — 24
additional gate-level runs — return the golden stream every time. No
gate-level placement reproduces the RTL's event stream** **[fact,
`hw/tb/gl_fi_results_disagreement.json`,
`make -f Makefile.glfi GLFI_GROUPS=disagreement_probe`]**.

### 6.3 What this document does and does not claim about it

**Claimed.** On the netlist that would be manufactured, the deadlock
constructed by `report_kept` and `report_erased` recovers with the
correct output, at every placement tested. The two SDC records `docs/16`
section 5.8 rests on **do not reproduce at gate level**.

**Not claimed: that the weakness is not real.** The report *is* one
flip-flop wide in the netlist, an upset *does* clear it, and `STATUS`
*does* read `0x06` afterwards with every counter at zero — all of that
reproduces exactly. A recovery that the host cannot see is a recovery
the mission cannot report, which is the argument for the fix
independently of whether this particular stimulus also corrupts the
output.

**Not claimed: that the cause is isolated.** One harness difference
between the two campaigns is known and cannot be removed (section 3.5):
the RTL campaign pre-fills both AER queue memories with the `0xF0F0`
sentinel and the gate-level one cannot. The four divergent records are
exactly the ones whose divergence is in the queue read path, so the
sentinel is the leading alternative explanation and it has **not** been
excluded. Two things argue against it and neither is conclusive: the
RTL's wrong words are `0, 1, 2, 3`, not the sentinel, so no sentinel
word reached the drain; and the gate-level side is the one with
undefined queue slots, which would be expected to make it *worse* than
the RTL rather than correct.

**Consequence for whoever owns `hw/rtl/pilot_top.v`.** The RTL has
already moved past this: the working tree at the time of writing retires
both pulse registers. That is a change to a design this netlist is not.
If `shape-6x2` is what ships, the structure in silicon is the pre-fix
one, and the gate-level evidence about it is the four records above —
erasable report confirmed, silent output corruption not reproduced. The
right next step is an RTL run with the sentinel fill disabled, which
would settle in one experiment whether the difference is the harness or
the level. That is an RTL-suite change and is not made here.

---

## 7. What it cost

| | |
|---|---|
| Gate level, this campaign | 522 injections, 3,322 s → **6.4 s per injection**, 13,357 simulated ns per wall second |
| RTL, the campaign of record | 365 injections, 567 s → **1.55 s per injection** |
| Ratio | **4.1x** wall per injection |

**[fact, both logs]**. The RTL fault-injection campaign was running
concurrently on the same machine for part of this run; an earlier
gate-level run of 513 injections on a less contended machine took
2,728 s, or 5.3 s per injection, a ratio of 3.4x. Both bracket
`docs/24` section 5.3's measured 3.13x for the functional suite, and the
conclusion is the same one: **gate-level costs a small multiple, not an
order of magnitude, and there is no performance argument against running
this on every harden.** The 165-injection configuration sweep is 1,135 s
of the total and is the one part that could be sampled rather than
swept if the budget ever mattered.

Elaboration is unchanged from `docs/24`: the same `sim.vvp`, built once.

---

## 8. Coverage, stated honestly

### 8.1 How much of the netlist is reachable at all

**All of it.** Every one of the 1,275 flip-flops in the netlist drives a
net that carries a name, so every one is addressable through the scope
index of section 3.1 and injectable by the primitive of section 2.2.
There is no latch, no macro and no unmapped instance to be unreachable
in. That is a stronger statement than this work started expecting, and
it is a property of `deferred_flatten` keeping dotted names rather than
of anything done here.

**1,170 of the 1,275 (91.8 %) keep a name derived from the RTL**, so a
target can be named the way the RTL names it. The other 105 do not, and
**101 of those 105 are inside a replicated bank** — the configuration
replicas and the AER pointer replicas — where the *bank* is still in the
name and the bank is what a replica-level claim is about. The remaining
four are pilot-level anonymous flops, one of which was identified by
experiment (section 3.3).

### 8.2 How much was actually injected into

| structure | flip-flops | injected | share |
|---|---|---|---|
| `lif_core` (neuron core) | 506 | 54 | 11 % |
| `pilot_top` top level | 434 | 59 | 14 % |
| configuration TMR replicas | 165 | 165 | 100 % |
| AER queue storage | 128 | 16 | 12 % |
| AER pointer replicas | 36 | 36 | 100 % |
| wrapper (reset sync, output pins) | 6 | 4 | 67 % |
| **total** | **1,275** | **334** | **26 %** |

**[fact, parsed from the netlist and from the injection log]**.

The 26 % is not a limitation of the method; it is the RTL campaign's
sampling policy, inherited on purpose. `docs/16` samples wide registers
at low / mid / high bit positions rather than exhaustively, because the
target list is meant to read as a hardening priority list rather than as
a hierarchy scrape. The two structures this document swept exhaustively
are the two where exhaustiveness answers a question a sample cannot:
whether three replicas are three registers.

### 8.3 What is not covered

1. **No timing.** Zero-delay functional run, exactly as `docs/24`. A
   fault whose effect depends on a hold violation is invisible here, and
   post-route STA on three corners (`docs/23` section 3) is the
   complementary evidence.
2. **Single-bit, single-cycle, one flip-flop.** No multi-bit upsets, no
   multi-cycle transients, no combinational SETs, no upsets in the clock
   or reset trees. The exceptions are the directed cases, which write a
   whole register at once and report the popcount, exactly as at RTL.
3. **One workload.** The same eight-command stimulus as `docs/16`, so
   every masking rate here is a statement about that workload. The
   `*_unread` control groups are the guard against reading them as
   anything wider.
4. **No sentinel fill in the AER queue memories** (section 3.5). It
   never caused a skipped injection, and section 6 says where it is
   still a live alternative explanation.
5. **This is not the TT-generated netlist.** Same limitation as
   `docs/24` section 8.2 item 3: a local LibreLane 3.0.5 harden, not the
   TTIHP26b GDS action's container.
6. **Not in CI.** `docs/19`'s parity gate does not know about
   `Makefile.glfi`, and adding it needs the same decision about which
   Icarus CI installs that `docs/24` section 8.2 item 6 records.

---

## 9. Reproducing this

```bash
make -f tools.mk toolcheck          # yosys 0.67+146; does NOT govern section 1.1

cd hw/tb
make -f Makefile.glfi provenance    # netlist, models, and the pinned RTL baseline
make -f Makefile.glfi               # the campaign: 522 injections, ~55 min

# the method validation alone, ~30 s of it
make -f Makefile.glfi GLFI_GROUPS=__none__

# one structure at a time
make -f Makefile.glfi GLFI_GROUPS=evq_ptr,lif_fsm

# section 6's placement sweep
make -f Makefile.glfi GLFI_GROUPS=disagreement_probe GLFI_TAG=disagreement

# against a different harden, if there is one
make -f Makefile.glfi GL_TAG=shape-3x4
```

One book-keeping note. `hw/tb/gl_fi_results.json` as committed was
produced before section 6's placement sweep was added to the suite, so
the sweep lives in its own log. A fresh `make -f Makefile.glfi` now runs
the sweep as part of the campaign — it adds about two minutes and no
records, since the probe explicitly does not classify into the histogram
— so a re-run reproduces the same 522 injections with the sweep's
findings additionally under `notes.disagreement_probe`.

The RTL baseline is **derived, not configured**: the suite takes the
newest commit that touched `hw/tb/fi_campaign_results.json` whose
`hw/rtl` tree is identical to the RTL this netlist was synthesized from
(`e1361fe`, `docs/24` section 1.2). When the RTL moves on, this pin does
not move with it — which is the point, and `make -f Makefile.glfi
provenance` prints which commit was chosen. `GLFI_RTL_REF` overrides it;
`GLFI_RTL_REF=WORKTREE` reads the working tree, which is right only when
the two suites are being changed together on purpose.

---

## 10. What this proves, and what it leaves open

### 10.1 Proved

1. **The hardening claims survive the step from RTL to netlist.** 357
   like-for-like injections, 355 identical classifications, and every
   structure the design makes an explicit promise about keeps it on the
   placed-and-routed netlist: FSM 12/12 detected, SECDED 12/12 corrected
   and 4/4 detected, coded memories 82 injections with zero SDC, pointer
   TMR 72/72 corrected.
2. **The pointer TMR has netlist-level functional evidence for the first
   time.** 36 replica flip-flops, all injected, all masked and counted.
   `docs/22` section 9's cell count is no longer the only evidence.
3. **The configuration TMR is three independent banks in silicon, bit
   for bit.** 165 of 165 replica flip-flops corrected, none masked,
   none SDC.
4. **The injector models an upset and not a stuck-at**, proved on this
   netlist by four measurements, of which the reset experiment (section
   4, D3) separates the two primitives outright.
5. **Every sequential element of the netlist is reachable** by this
   method (section 8.1), so the 26 % that was injected is a budget
   decision rather than a ceiling.

### 10.2 Open

1. **The section 6 disagreement needs one more experiment to close**:
   an RTL run with the AER queue sentinel fill disabled. It is an
   RTL-suite change and belongs to whoever owns `test_fi_campaign.py`.
2. **`u_lif.out_event[14]` is an RTL injection into a flip-flop that
   does not exist.** Harmless today — it classifies MASKED, which is
   what a non-existent flop would give — but the RTL target list is
   spending an injection on nothing, and a future edit that made those
   bits real would not be noticed by it.
3. **Re-run against the GDS action's netlist** when it next runs, as
   `docs/24` section 8.3 item 3 asks for the functional suite. The same
   argument applies to this one.
4. **CI**, with the same Icarus-version decision `docs/24` names.
5. **The RTL has moved past this netlist.** `hw/rtl/pilot_top.v` now
   retires the pulse registers of section 6 and re-rails three valid
   flags. None of that is in `shape-6x2`. If the submission re-hardens,
   this campaign should be re-run against the new netlist before any of
   its numbers are quoted for the new design; if it does not, these
   numbers describe what ships and the RTL campaign no longer does.
