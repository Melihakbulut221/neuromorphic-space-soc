# 32 — Gate level, re-run against the netlist the RTL is actually in

Status: complete. `docs/24` and `docs/26` describe the `shape-6x2`
netlist, and four RTL waves have landed since it was hardened. Both
suites have been re-pointed at the sign-off harden of the current RTL,
`signoff-6x2` — **1,296 flip-flops against the 1,275 those documents
describe** — and re-run in full. The functional result is unchanged. The
fault-injection result is unchanged where the design is unchanged, and
section 5.3 is the first gate-level evidence for the three structures
wave 6 to wave 9 added. Section 6 closes the disagreement `docs/26`
left open, with the experiment `docs/26` section 10.2 specifies, and the
answer is not the one that document guessed at.

**No document other than this one is edited.** Section 8 lists, location
by location, what `docs/24` and `docs/26` now say wrongly.

Convention, inherited from `docs/18`, `docs/22` and `docs/27`:
**[fact]** = measured in this environment or read out of an installed
file; **[estimate]** = derived or judged.

Run trees under `hw/openlane/*/runs/` and `tt/runs/` are **gitignored**,
so every number is quoted with the run tag and the step directory it
came from.

Files changed: `hw/tb/Makefile.gl`, `hw/tb/Makefile.glfi`,
`hw/tb/test_gl_fi.py`, and the new log
`hw/tb/gl_fi_results_signoff-6x2.json`. **`hw/tb/test_pilot_gl.py` is
not changed at all**, which is section 3.1's point rather than an
omission. `hw/tb/gl_fi_results.json` — `docs/26`'s record of the
`shape-6x2` campaign — is deliberately **not** overwritten; section 1.4
says why it nearly was.

### Headline

- **Three separate pieces of staleness were in the harness, not only in
  the documents.** The gate-level suites defaulted to a superseded run
  directory, carried the netlist's RTL commit as the literal `e1361fe`,
  and wrote their log to a name that does not carry the harden. Pointed
  at a new netlist as shipped, they would have compared it against the
  old netlist's RTL campaign and destroyed the file the comparison is
  made through. Section 1.4.
- **The functional suite is unchanged, test for test.** 20 of 31 tests
  run at gate level, the same 20 as `docs/24`; none that ran has stopped
  running; every one takes the same simulated time as the RTL to the
  nanosecond; and the one divergence is still the same X-pessimism on
  the same unreset memory. The RTL suite has grown from 27 tests to 31
  and all four new ones are RTL-only, so the port-driven fraction has
  fallen from 74 % to 65 %. Section 3.
- **The injector still models an upset on the new netlist, and it had to
  be re-proved, not assumed.** Every instance path in `docs/26`'s
  method validation moved. `cfg_axon[3]` is a different anonymous
  flip-flop; the four one-bit valid flags are eight rails under four new
  names; two of the directed cases place their injection on a term that
  is a wire in the RTL and does not exist in the netlist at all.
  Section 4.
- **The rails' polarity transform does not survive synthesis.** The RTL
  builds each rail pair with a per-rail storage polarity and argues it
  as an attribute-independent defence against `opt_merge`. In this
  netlist both rails store the true value: yosys folds the two
  inversions away. The rails are still two distinct flip-flops — that is
  measured, and it is `keep_hierarchy` doing it, not the transform.
  Section 4.3.
- **561 injections, 370 of them like-for-like with the RTL campaign, and
  all 370 classify identically.** `docs/26` had 355 of 357. **No group
  carries a class difference**, and the two histograms are equal in
  every class. Section 5.
- **The new redundancy works at gate level.** All eight valid-flag
  rails, all eight queue entry-parity flip-flops and both dispatcher
  check flip-flops injected, and none of the eighteen is SDC — sixteen
  of sixteen rail injections DETECTED, and the seven `evq_mem` records
  that `docs/26` reported as SDC on both sides are now DETECTED on both
  sides, which is the wave-9 entry parity measured on the netlist.
  Section 5.3.
- **The `docs/26` disagreement is closed, and the AER queue sentinel is
  not the explanation.** With the sentinel fill disabled the RTL still
  returns the corrupted stream, on all four records, unchanged in every
  field; and neither placement sweep meets the other, 24 runs each way.
  The class difference has separately disappeared because the RTL
  repaired the erasable report — but the class label was never the
  finding, and the output divergence it was hiding has survived four RTL
  waves and three hardens. Section 6.

---

## 1. Which netlist, and how it was chosen

### 1.1 The run

| | |
|---|---|
| Path | `hw/openlane/pilot_ihp/runs/signoff-6x2/final/nl/tt_um_melihakbulut_nssoc.nl.v` |
| git blob | `91cb371f6d526b826926b5c2e1147b6e95bb1ff9` |
| Size | 2,565,946 bytes |
| Modules in it | **1** — fully flattened, `SYNTH_HIERARCHY_MODE: deferred_flatten` |
| Instances | 33,564 total; 12,546 standard cells, 21,018 fill |
| Sequential cells | **1,296**, every one a `sg13g2_dfrbpq_1`; no latch, no macro |
| Unmapped instances | 0 |
| Named children under the top scope | **46,035** |
| Shape | 6x2, `DIE_AREA [0, 0, 1289.28, 313.74]`, the submission shape of `docs/23` |
| PDK | `ihp-sg13g2`, ciel `c4b8b4e5e7a05f375cca3815d51b3a37721fbf5c` |
| Cell models | `.../sg13g2_stdcell/verilog/sg13g2_stdcell.v`, blob `c4efa342f0d1f6a523c6a03bac258ef6e3729556` |

**[fact]**. The PDK and the models are the same ones `docs/24` and
`docs/26` used, resolved the same way — out of the run's own
`resolved.json`, never whichever version `~/.ciel` currently symlinks.

This run was produced by a concurrent session while this work was
executing, and it is the right netlist for exactly one reason: **its
pinned RTL is the current `hw/rtl`**. Section 1.2 checks that rather
than assuming it.

Its sign-off decks are that session's result and not this document's
claim, but they bear on whether this is a netlist worth measuring, so
they are quoted: `route__drc_errors: 0`, `magic__drc_error__count: 0`,
`klayout__drc_error__count: 0`, `design__lvs_error__count: 0`,
`route__antenna_violation__count: 0`, `design__violations: 0`,
`flow__errors__count: 0`, `design__instance_unmapped__count: 0`
**[fact, `final/metrics.json`]**.

**The runs below were started against `54-openroad-fillinsertion/`
while the geometric decks were still executing, and finished against a
netlist that turned out to be the same bytes.** `final/nl/` and the
step-54 netlist have the same git blob,
`91cb371f6d526b826926b5c2e1147b6e95bb1ff9` **[fact]** — the steps after
fill insertion extract, check and stream out, and none of them edits the
netlist. This is recorded rather than glossed because starting a
measurement against an intermediate artifact is only sound if the
identity is checked afterwards, and it was.

### 1.2 The RTL it contains, derived and not quoted

`hw/openlane/pin_rtl.py` copies the RTL into a snapshot directory and
the run's `resolved.json` names that directory by absolute path. Hashing
its ten files and searching for the commit whose `hw/rtl` tree has
exactly those blobs gives **`bc91c71`**, which is `HEAD`, and the
working tree is clean **[fact]**.

That derivation is now what the fault-injection suite does at run time;
it used to be a literal. Section 1.4.

| wave | commit | in `shape-6x2` | in `tr-margin` | in `signoff-6x2` |
|---|---|---|---|---|
| the timeout retirement | `3458d36` | no | yes | yes |
| the eight valid-flag rails | `2c6c052` | no | yes | yes |
| queue entry parity | `634ca3e` | no | no | **yes** |
| dispatcher parity checks | `bc91c71` | no | no | **yes** |

**[fact, per-file blob comparison of each run's pinned snapshot against
each commit's `hw/rtl` tree]**.

### 1.3 What the twenty-one added flip-flops are

Parsed out of the three netlists rather than counted from the RTL: every
net driven by a `sg13g2_dfrbpq_1` `Q` pin, which is the same set the
injector is allowed to target.

| | `shape-6x2` | `tr-margin` | `signoff-6x2` |
|---|---|---|---|
| flip-flops | 1,275 | 1,277 | **1,296** |

`shape-6x2` -> `tr-margin`, **+2**: eight flip-flops leave
(`aer_out_vld`, `u_pilot.lif_out_valid`, `u_pilot.fi_rd_valid`,
`u_pilot.fo_rd_valid`, `u_pilot.fetch_timeout`, `u_pilot.oh_timeout`,
and two anonymous pilot-level flops) and ten arrive (the eight rails,
and two anonymous flops). The four one-bit valid flags became eight
rails, and the two one-cycle timeout report registers were retired.

`tr-margin` -> `signoff-6x2`, **+19**, and nothing left:

| | flops |
|---|---|
| `u_pilot.u_evq_in.u_par.bits[0..3]` | 4 |
| `u_pilot.u_evq_out.u_par.bits[0..3]` | 4 |
| `u_pilot.u_disp_chk.bits[0..1]` | 2 |
| `u_pilot.evq_par_q` | 1 |
| `u_pilot.cnt_evqp[0..7]` | 8 |

**[fact]**. **Eleven of the nineteen are the new redundancy itself** —
the two four-entry parity banks, the two-bit dispatcher check bank and
the one-bit parity-error report; the other eight are the counter that
makes it observable. None of the eleven had ever been injected at gate
level, and section 5.3 is the first time.

### 1.4 Three pieces of staleness in the harness, not in the documents

The task that produced this document was "re-run these suites against
the current netlist". Doing that exposed three things that would each
have produced a wrong number quietly.

**The default run directory.** Both fragments defaulted to
`GL_TAG ?= shape-6x2`. That is a named directory with no wildcard in it,
which is the guard `docs/24` section 2.1 argues for and it is still the
right shape — but it was **two hardens out of date**, and a fragment
that must be moved by hand had not been moved. It now defaults to
`signoff-6x2`, and `Makefile.gl` additionally refuses to run against a
directory whose `resolved.json` does not say `deferred_flatten`, because
a synthesis-only probe and a sign-off netlist are indistinguishable by
file name.

**The netlist's RTL commit was a literal.** `test_gl_fi.py` carried
`NETLIST_RTL = os.environ.get("GLFI_NETLIST_RTL", "e1361fe")` and used
it to pick the RTL fault-injection campaign to compare against: the
newest committed campaign whose `hw/rtl` tree equals the netlist's. The
*rule* is right and is the reason `docs/26`'s numbers are honest. The
*constant* is what goes stale, and it had. Pointed at `signoff-6x2` as
shipped, the suite would have compared a 1,296-flip-flop netlist against
the fault-injection campaign of a 1,275-flip-flop design and reported
every difference between two designs as a difference between two levels
— which is precisely the failure the comment above that line warns
about. It is now derived from the run's own `resolved.json`, as
section 1.2 describes, and written into the log as `netlist_rtl`.

**The log file name did not carry the harden.** The campaign wrote
`hw/tb/gl_fi_results.json` unconditionally. A run against the new
netlist would have overwritten `docs/26`'s record of the old one —
destroying the only file through which the two can be compared, in the
same command that produced the thing to compare it with. The name now
carries the run tag, with `shape-6x2` keeping the unsuffixed name so
`docs/26` section 9 still reproduces verbatim.

None of the three is a mistake in `docs/24` or `docs/26`. All three are
what a harness pinned to one photograph does when the subject moves.

---

## 2. The toolchain, and the two traps re-confirmed

Unchanged from `docs/24` section 3, and re-checked here rather than
inherited:

| Tool | Path | Version |
|---|---|---|
| Icarus, gate level and the RTL side of section 3.2 | `~/.local/opt/iverilog13/usr/bin/iverilog` | 13.0 stable |
| Icarus on PATH, used by every other `hw/tb` suite | `~/.local/bin/iverilog` | 12.0 stable |
| cocotb | `hw/.venv` | 2.0.1 |
| yosys (governed by `tools.mk`, not used here) | pinned oss-cad-suite | 0.67+146 |

**[fact]**. `make -f tools.mk toolcheck` passes and does not govern this
run, for the two reasons `docs/24` section 3 records: Icarus 12 leaves
`sg13g2_dfrbpq_1`'s `delayed_CLK` undriven so every flip-flop in the
netlist clocks on `z`, and the pinned oss-cad-suite Icarus cannot host a
venv-installed cocotb here. Both guards are still in both fragments and
both were exercised: the version guard is what stops a distribution
Icarus 12 from reporting a dead design, and in the fault-injection
suite, a campaign of 100 % MASKED.

One measurement worth keeping because it is the only one that has to be
repeated on every simulator change: **the RTL suite is green on both
Icarus versions with identical per-test simulated time**, 31 of 31 and
2,454,198.03 ns on 12.0 and on 13.0 **[fact, two runs]**. The simulator
is therefore not a variable in section 3.2.

---

## 3. The functional suite

### 3.1 The partition: 20 of 31, and eleven excluded

`test_pilot_gl.py` computes the split by parsing `test_pilot_top.py`
with `ast` and asking, for every test and transitively for every
module-level helper it calls, whether any `dut.<attr>` access names
something that is not a port of the Tiny Tapeout wrapper. **That file
needed no edit at all**, which is the point of having derived the
partition instead of writing it down: the RTL suite grew four tests and
the gate-level count changed on its own.

| | `docs/24` | now |
|---|---|---|
| tests in `test_pilot_top.py` | 27 | **31** |
| run at gate level | 20 | **20** |
| RTL-only | 7 | **11** |
| port-driven fraction | 74 % | **65 %** |

**[fact]**. The gate-level set is the *same twenty tests*; **nothing
that ran at gate level has stopped running**. All four tests added since
`docs/24` reach into the hierarchy, and all four are new SEU or
observability tests for the new redundancy:

| Test | Reaches |
|---|---|
| `test_queue_parity_discard_is_counted_and_flagged` | `dut.u_pilot.cnt_evqp`, `.u_evq_in.rd_idx`, `.u_evq_in.u_par.bits` |
| `test_dispatcher_state_upset_is_detected_not_acted_on` | `dut.u_pilot.disp_chk_bad`, `.dstate` |
| `test_event_word_upset_is_detected_rather_than_issued` | `dut.u_pilot.dstate`, `.evw`, `.evw_chk_bad`, `.lif_ev_valid`, `.u_disp_chk.bits` |
| `test_unread_event_word_bits_are_outside_the_check` | `dut.u_pilot.dstate`, `.evw`, `.evw_chk_bad`, `.u_disp_chk.bits` |

**[fact, printed by every run]**. One of `docs/24`'s original seven has
also grown references: `test_dispatcher_stranded_in_fetch_recovers_and_is_flagged`
reached only `dut.u_pilot.dstate` there and now reaches
`.disp_chk_bad` and `.u_disp_chk.bits` as well. It was already excluded,
so the count did not move — but it is a working example of why the
partition is derived: the printout tracked the edit with no maintenance.

`docs/24` section 4.3's argument for why these cannot be adapted is
unchanged and is now load-bearing for four more tests: a deposit into a
netlist net is a stuck-at, and the gate-level answer to these four
questions is the fault-injection suite, where it is section 5.3.

### 3.2 The result, beside `docs/24`'s

| Run | Tests | Result | Simulated |
|---|---|---|---|
| `make -f Makefile.gl`, `signoff-6x2` | 20 | **19 PASS, 1 FAIL** | 2,761,090.02 ns |
| `GL_PRELOAD=1`, `signoff-6x2` | 21 | **21 PASS, 0 FAIL** | 1,426,700.02 ns |
| `make -f Makefile.gl`, `tr-margin` | 20 | **19 PASS, 1 FAIL** | 2,761,090.02 ns |
| `GL_PRELOAD=1`, `tr-margin` | 21 | **21 PASS, 0 FAIL** | 1,426,700.02 ns |
| `docs/24`, `shape-6x2` | 20 | 19 PASS, 1 FAIL | 2,761,090 ns |
| `docs/24`, `shape-6x2`, `GL_PRELOAD=1` | 21 | 21 PASS, 0 FAIL | 1,426,700 ns |
| `make -f Makefile.pilot` (RTL, Icarus 13.0) | 31 | **31 PASS** | 2,454,198.03 ns |
| `make -f Makefile.pilot` (RTL, Icarus 12.0) | 31 | **31 PASS** | 2,454,198.03 ns |

**[fact]**. The three netlists — 1,275, 1,277 and 1,296 flip-flops, from
three different hardens with different placements — produce **identical
simulated time on all twenty tests**, and each one equals the RTL run of
the same test to the hundredth of a nanosecond. `docs/24` section 5.2's
per-test table therefore reproduces exactly and is not repeated here.

That is a stronger statement than it was in `docs/24`, because it is now
across three hardens rather than one: the netlist and the RTL take the
same number of clock cycles to do the same things, and that does not
depend on the placement.

### 3.3 The one divergence is the same one

`test_axon_out_of_range_is_dropped_and_counted` still fails at gate
level and still passes with `GL_PRELOAD=1`, at the same 1,380,510 ns and
27,310 ns respectively **[fact]**. `docs/24` section 6's diagnosis is
unchanged and is not re-derived here: `lif_core`'s 256-entry synapse
memory has no reset, RTL Verilog is X-optimistic about it and a netlist
cannot be, and this is the one port-driven test that enables the core
without writing a weight first.

`docs/24` section 8.3 item 1 — "fix or annotate that test" — is **still
open**, and it is worth saying that four RTL waves have gone past
without it being done. It is owned by whoever owns `test_pilot_top.py`.

---

## 4. Re-validating the injector before counting anything

`docs/26` section 4's rule is that nothing is counted until the injector
is proved to model an upset **on the netlist being measured**. Every
instance path in that validation moved between `shape-6x2` and
`signoff-6x2`, so this is not a formality.

### 4.1 The six measurements, reproduced exactly

| | `docs/26`, `shape-6x2` | here, `signoff-6x2` |
|---|---|---|
| A. uninjected control event stream | `[1, 2, 5, 6, 4, 2]`, golden-exact | **identical** |
| B/C. `scratch[0]` before / during force / after release / settled | 0 / 1 / 1 / 1, `SCRATCH` reads `0x00000001` | **identical** |
| D. the same net by deposit, cycles held | still 1 after **177** cycles | **identical, 177** |
| D2. `u_lif.state` deposit vs force | `0000` / `0001` / `1001` / `1001`, both | **identical, both** |
| D3. `SCRATCH` after a hard reset | force `0x00000000`, deposit `0x00000001` | **identical** |
| E. `u_lif.state[0]` upset | DETECTED, `STATUS = 0x00000015` | **identical** |

**[fact, logged]**. D3 is the decisive one and it is the reason the
deposit primitive is rejected: after a genuine upset the flip-flop holds
the wrong value and the design's own asynchronous reset clears it; after
a deposit the flip-flop holds the *right* value and only the wire is
wrong, so the fault survives a recovery no physical upset survives.

### 4.2 What had to be re-derived, and what that cost

**`cfg_axon[3]` is a different flip-flop.** `docs/26` section 3.3
identified it, by controlled experiment, as `u_pilot._0255_`. In this
netlist `_0254_` and `_0255_` do not exist and the anonymous
pilot-level set is `_0250_` to `_0253_`; the same experiment returns
**`u_pilot._0253_`**, again exactly one net moving with the bit
**[fact]**. Had that name been written down rather than measured, the
suite would have injected into the wrong flip-flop or into nothing.

**Four of the eight rails lost their instance prefix.** The RTL campaign
names both rails of a flag `<instance>.bits`. In the netlist the `POL=0`
rail's `assign q = bits ^ 0` is the identity, so yosys merges the
storage with the wire the rail drives and the flip-flop keeps the
*consumer's* name — there is no `u_ohv_a.` prefix anywhere. The `POL=1`
rail keeps an instance-internal name. Four explicit mappings were added,
each justified by the rail instance's own `.q()` connection and each
checked against the parsed flip-flop set before use:

| RTL target | netlist net |
|---|---|
| `u_ohv_a.bits` | `u_pilot.oh_valid_a` |
| `u_lif.u_op_a.bits` | `u_pilot.u_lif.op_a` |
| `u_evq_in.u_rdv_a.bits` | `u_pilot.u_evq_in.rdv_a` |
| `u_evq_out.u_rdv_a.bits` | `u_pilot.u_evq_out.rdv_a` |

**[fact]**. The `b` rails resolve through the existing replica-bank rule
with no new mapping. The two queue entry-parity banks and the dispatcher
check bank needed no mapping either: both are
`(* keep *) reg [W-1:0] bits` inside a named module, so they arrive as
`...u_par.bits[i]` and `u_disp_chk.bits[i]` and the existing rule finds
them.

**Two directed cases place on a term the netlist does not have.** The
`report_kept` and `report_erased` scripts — the two the `docs/26`
disagreement is about — anchor with `("until", "fetch_expire", 1, 90)`.
`fetch_expire` is a *wire* in the RTL and there is **no net of that name
in the netlist**: synthesis folded the term into the logic it feeds. The
first gate-level run against this netlist reported both cases NOT
CONSTRUCTED, which would have withdrawn the two records under
examination at the moment they were being re-examined.

An `until` is an observation used to *place* an injection and never to
classify one, so it does not have to land on a flip-flop — that rule is
about what may be *forced*. The term is therefore recomputed from the
registers it is a function of, with every operand of the RTL expression
present and none approximated:

```
fetch_expire = (dstate == D_FETCH) && !fi_rd_valid
               && (fetch_wait == FETCH_WAIT_MAX)
oh_expire    = oh_req && !fo_rd_valid && (oh_wait == OH_WAIT_MAX)
```

`dstate`, `fetch_wait`, `oh_wait` and `oh_req` are flip-flop outputs;
`fi_rd_valid` and `fo_rd_valid` survive as named wires and are read
directly. `blk_rst_n` is the one operand not read: it is high
throughout a directed case, which runs inside burst 0's busy window
after bring-up and before any soft reset. `test_00` asserts that both
terms evaluate, so a future netlist that folds one of the operands away
fails loudly instead of silently withdrawing the records.

**A counter was added to the campaign and the observation set was a
copy.** The RTL campaign grew `cnt_evq_par` with the entry parity. The
gate-level `read_observations` listed the counters literally, so the
classifier — which iterates `fi.COUNTERS` — raised `KeyError` inside
every injection: ten failed tests and "the gate-level campaign injected
nothing". Loud, and still the wrong message. The counter addresses are
now derived from `fi.COUNTERS`, and a counter that resolves to neither
the generated register map nor a campaign constant fails with a message
naming it.

### 4.3 A finding: the rails' polarity transform is gone

`pilot_top.v`'s header argues the per-rail storage polarity as an
attribute-independent defence: two flip-flops with the same
`(D, EN, reset)` signature are one bank after `opt_merge`, and a
polarity difference gives structural hashing nothing to match.

Sampled over 240 cycles of a full burst, on all four flags, **the two
rails never disagree**: 0 of 240 samples on each, 0 undefined **[fact]**.
Reading the netlist confirms the mechanism: `u_pilot.u_ohv_b._3_` is a
**buffer** from `oh_valid_d` to the flip-flop's `D`, and
`u_pilot.u_ohv_b._4_` is a **buffer** from its `Q` to `oh_valid_b`. The
`bits <= d ^ 1` / `q = bits ^ 1` pair is a double inversion and yosys
folds it away. The same shape holds for all four `b` rails.

Three things follow, and they should not be run together.

1. **Functionally nothing is wrong.** Both rails store the flag's true
   value, the consumer still computes `a && b` and `a != b`, and the
   sweep in section 5.3 confirms the flags behave as two rails.
2. **The defence that is actually working is `keep_hierarchy`, not the
   transform.** There are two distinct flip-flops per flag in the
   netlist — asserted, not assumed — but not because their stored
   functions differ, since they do not. For the one-bit rails the
   polarity is the *only* transform; the configuration replicas combine
   it with the per-replica MIX function, and this measurement says
   nothing about those.
3. **It is a claim about the RTL that the netlist does not support**, in
   the same class as `docs/16` section 4's merged configuration TMR and
   `docs/22`'s pointer TMR, and it is the fifth time in this project
   that asking the netlist has answered differently from the RTL. It is
   reported here and no fix is proposed: `hw/rtl/**` is not this
   document's to change.

**[estimate]** The exposure is that a flow which applies
`opt_merge -share_all`, or one that does not read yosys attributes,
would have nothing left to stop the two rails collapsing into one. The
LibreLane flow used here does not, which is why the netlist has eight.

---

## 5. The campaign

### 5.1 Headline numbers

| | | `docs/26`, `shape-6x2` |
|---|---|---|
| Gate-level injections | **561** | 522 |
| Distinct mapped flip-flops injected into | **347** of the netlist's **1,296** | 334 of 1,275 |
| Injections that are exact like-for-like matches with an RTL record | **370** | 357 |
| Of those, classifying **identically** | **370** | 355 |
| Classifying differently | **0** | 2 |
| `SKIPPED_X` | **0** | 0 |
| `NOT_CONSTRUCTED` | **0** | 0 |
| Wall | 3,220.7 s for the suite, 3,115.9 s for the campaign | 3,354.6 / 3,322.4 |

**[fact, `hw/tb/gl_fi_results_signoff-6x2.json`]**. "Exact like-for-like"
means the same group, the same target, the same bit and the same drawn
`(burst, delay)` phase, matched record to record against the RTL log at
`bc91c71` (blob `b843e7118371185e93cdda0aba21d473b23eec15`, 378
injections) — not a comparison of aggregates that happen to have the
same shape.

Over those 370, the two histograms are **equal in every class**:

| | MASKED | CORRECTED | DETECTED | SDC | HANG |
|---|---|---|---|---|---|
| **Gate level**, 370 injections | 94 | 188 | 82 | 6 | 0 |
| **RTL**, the same 370 | 94 | 188 | 82 | 6 | 0 |

Over all 561 gate-level injections, including the 191 the RTL campaign
does not make: **103 MASKED, 353 CORRECTED, 99 DETECTED, 6 SDC,
0 HANG**.

The eight-injection gap between 378 and 370 is entirely the eight
records section 5.4 accounts for, each of which is a target with no
recoverable flip-flop in this netlist.

### 5.2 Group by group

**Twenty-four groups are identical, record for record**: same count,
same class in every class.

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
| `evq_mem` | 32 | 25 | 0 | 7 | 0 | 0 |
| **`evq_par`** | **8** | **6** | 0 | **2** | 0 | 0 |
| **`disp_chk`** | **4** | **2** | 0 | **2** | 0 | 0 |
| `evq_hold` | 18 | 7 | 0 | 9 | 2 | 0 |
| `dispatch` | 18 | 4 | 0 | 14 | 0 | 0 |
| `regbank_cnt` | 18 | 5 | 4 | 9 | 0 | 0 |
| `telemetry_primed` | 6 | 1 | 3 | 2 | 0 | 0 |
| `wdog_fetch` | 6 | 6 | 0 | 0 | 0 | 0 |
| `wdog_oh` | 6 | 6 | 0 | 0 | 0 | 0 |
| `wdog_fetch_dir` | 6 | 1 | 0 | 5 | 0 | 0 |
| `wdog_oh_dir` | 6 | 1 | 0 | 5 | 0 | 0 |
| `ecc_port_single` | 12 | 0 | 12 | 0 | 0 | 0 |
| `ecc_port_double` | 4 | 0 | 0 | 4 | 0 | 0 |
| `ecc_ff` | 7 | 0 | 7 | 0 | 0 | 0 |

**[fact]**. Four groups agree on **every injection that ran** and differ
only in how many ran, because a target has no recoverable flip-flop in
this netlist (section 5.4): `cfg_tmr_a` 4 of 5, `cfg_tmr_b` 1 of 5,
`lif_scan` 22 of 24, `regbank_cfg` 15 of 16.

**No group carries a class difference.** That is the change from
`docs/26` section 5.2, which had two, and section 6 is what happened to
them.

Four rows are worth naming for what they now mean.

- **`evq_mem`: the 7 records that were SDC at RTL are DETECTED at both
  levels now.** `docs/26` recorded 25 MASKED and 7 SDC in this group on
  both sides. The entry parity turned those seven into detections, and
  the netlist agrees record for record — this is the wave-9 repair
  measured on the design that would be manufactured, not on the RTL that
  proposed it.
- **`evq_par`, 8 of 8, and `disp_chk`, 4 of 4, identical to RTL.** The
  two structures added last are in the netlist and behave there exactly
  as they behave in the RTL. Section 5.3 sweeps them exhaustively as
  well.
- **`evq_ptr`: 72 of 72 CORRECTED**, unchanged from `docs/26`, on 36
  distinct pointer replica flip-flops.
- **`lif_fsm`: 12 of 12 DETECTED**, unchanged. The HD-2 encoding
  argument still holds on the mapped netlist.

### 5.3 The new redundancy, swept exhaustively

Three structures had never been injected at gate level. Two of them had
never been injected exhaustively at either level.

**The eight valid-flag rails.** The RTL campaign covers six — `oh_valid`,
EVQ_OUT's `rd_valid` and `lif_core`'s `out_pend` — and leaves **EVQ_IN's
`rd_valid` rails out of its target list entirely**, so two flip-flops of
wave-6 redundancy had never been injected anywhere. All eight are swept
here, at two phases each:

| | n | MASKED | CORRECTED | DETECTED | SDC |
|---|---|---|---|---|---|
| `rail_sweep`, all 8 rails x 2 phases | **16** | 0 | 0 | **16** | **0** |

**[fact]**. Sixteen of sixteen DETECTED, zero SDC. That is exactly the
claim two rails make and no more: they **detect** what they cannot
correct, and a disagreement the design does not notice is the failure
mode that did not occur. The fourteen of those sixteen that have an RTL
twin under `lif_scan` and `evq_hold` classify the same way there.

**The two queue entry-parity banks and the dispatcher check bank.**
Every flip-flop of all three, once each:

| bank | flip-flops | MASKED | CORRECTED | DETECTED | SDC |
|---|---|---|---|---|---|
| `u_evq_in.u_par.bits[0..3]` | 4 | 4 | 0 | 0 | **0** |
| `u_evq_out.u_par.bits[0..3]` | 4 | 4 | 0 | 0 | **0** |
| `u_disp_chk.bits[0..1]` | 2 | 1 | 0 | 1 | **0** |

**[fact]**. Zero SDC across all ten. The MASKED records are the honest
outcome for a check bit on a slot the workload never reads back, and
they are the same shape as the RTL campaign's own `evq_par` result
(6 MASKED, 2 DETECTED of 8) — a parity bit that is upset on an entry
nobody reads costs nothing, and one that is upset on an entry that is
read causes the entry to be discarded and counted, which is a detection.
The one DETECTED dispatcher-check record is the check bank doing its
job at gate level.

**These ten flip-flops did not exist in any netlist before this run.**
They are in `signoff-6x2` and in nothing earlier; a run against
`tr-margin` reports all three banks absent, with the prefix it searched
for and the commit the netlist came from, rather than skipping them
**[fact, `GL_TAG=tr-margin` run]**.

**The configuration TMR, re-swept.** `docs/26` section 5.3's exhaustive
sweep is re-established on the new netlist: **all 165 replica flip-flops
— 55 in each of the three banks — injected once each, 165 CORRECTED,
0 SDC, 0 MASKED** **[fact]**. Zero MASKED matters as much as zero SDC:
a dead flop would come back MASKED and a shared flop would corrupt two
replicas at once and vote through.

### 5.4 What could not be injected, and why

Nine targets are reported unreachable, two more than `docs/26`'s seven.
**Only seven of the nine cost an injection**, because the RTL campaign
has no record for the other two either:

| target | reason | records lost |
|---|---|---|
| `u_cfg_a.bits[32]`, `u_cfg_b.bits[0,12,16,43]` | the name did not survive synthesis and the campaign samples 5 of 55 bits, so which flop carries the bit cannot be recovered. The domain is covered instead by the 165-flop sweep | 5 |
| `u_lif.out_event[14]` | **there is no flip-flop.** `lif_core.v` writes constants into bits 15:10, so the netlist has ten, not sixteen | 2 |
| `ctrl_scrub_en` | no flip-flop of that name survives; the scrub-enable bit was absorbed into the logic it gates | 1 |
| **`fetch_timeout`, `oh_timeout`** | **retired from the RTL by `3458d36`.** No flip-flop in the netlist — and none in the RTL either, so the RTL campaign draws their phases and records nothing | **0** |

**[fact, all four rows, checked against the parsed set of flip-flop
output nets rather than against a name search]**.

The last row is a small correction that belongs to whoever owns
`test_fi_campaign.py`: its `target_list` still names `fetch_timeout` and
`oh_timeout` in the `wdog_fetch` and `wdog_oh` groups. Both are
harmless — they consume a drawn phase and produce no record on either
side — but the target list is describing storage the design has not had
since `3458d36`, in the same way `docs/26` section 10.2 item 2 records
for `out_event[14]`.

`SKIPPED_X` never fired, on 561 injections. `docs/26` section 3.5's
mechanism exists because the AER queue memories have no sentinel fill at
gate level and are X until the design writes them; every injection into
them still landed on a defined bit.

### 5.5 Coverage

| structure | flip-flops | injected | share |
|---|---|---|---|
| `lif_core` (neuron core) | 506 | 54 | 11 % |
| `pilot_top` top level | 438 | 55 | 13 % |
| configuration TMR replicas | 165 | 165 | **100 %** |
| AER queue storage | 128 | 16 | 12 % |
| AER pointer replicas | 36 | 36 | **100 %** |
| **valid-flag rails** | **8** | **8** | **100 %** |
| **AER entry parity banks** | **8** | **8** | **100 %** |
| **dispatcher check bank** | **2** | **2** | **100 %** |
| wrapper (reset sync, output pins) | 5 | 3 | 60 % |
| **total** | **1,296** | **347** | **27 %** |

**[fact, parsed from the netlist and from the injection log; the
structure column is assigned by name prefix]**.

**Every one of the 1,296 flip-flops drives a named net**, so `docs/26`
section 8.1's reachability claim holds unchanged at the larger size:
1,187 keep a name derived from the RTL, 105 of the remaining 109 are
inside a replicated bank whose identity is still in the name, and the
last four are the pilot-level anonymous group of `docs/26` section 3.3
**[fact]**. The 27 % is the RTL campaign's sampling policy, inherited on
purpose; the five structures swept exhaustively are the five where
exhaustiveness answers a question a sample cannot.

---

## 6. The disagreement, closed

`docs/26` section 6 reported two of 357 like-for-like injections
classifying differently — `report_erased` in each of the two bounded
waits, SDC at RTL and MASKED at gate level — and section 6.3 said
plainly what was not claimed: **that the cause was isolated**. One
uncontrolled difference between the two harnesses was known and could
not be removed. The RTL campaign pre-fills both AER queue memories with
the `0xF0F0` sentinel and the gate-level campaign cannot, and the four
divergent records were exactly the ones whose divergence is in the queue
read path. Section 10.2 item 1 named the experiment that would settle
it: an RTL run with the sentinel fill disabled.

### 6.1 The class difference is gone, and it is not the finding

`3458d36` made the fault report unerasable. At RTL, `report_erased` is
now DETECTED rather than SDC, and the gate-level run agrees: **370 of
370 like-for-like injections classify identically, including all twelve
directed cases**. The two SDC records `docs/16` section 5.8 ranked its
wave-6 repair on no longer exist on either side, because the design they
described has been repaired.

That is not the same as the disagreement being resolved, and treating it
as such would be the easy mistake here. `docs/26` section 6.1 was
explicit that **the class label was not the finding; the output was**:

| construction | RTL event stream | gate-level event stream | golden |
|---|---|---|---|
| `wdog_fetch_dir` / `report_kept` | `[0, 1, 2, 3, 4, 2]` | **`[1, 2, 5, 6, 4, 2]`** | `[1, 2, 5, 6, 4, 2]` |
| `wdog_fetch_dir` / `report_erased` | `[0, 1, 2, 3, 4, 2]` | **`[1, 2, 5, 6, 4, 2]`** | same |
| `wdog_oh_dir` / `report_kept` | `[0, 1, 2, 3, 4, 2]` | **`[1, 2, 5, 6, 4, 2]`** | same |
| `wdog_oh_dir` / `report_erased` | `[0, 1, 2, 3, 4, 2]` | **`[1, 2, 5, 6, 4, 2]`** | same |

**[fact, both logs, on the wave-9 design at both levels]**. `STATUS` is
`0x16` for all four at both levels; `out_ok` is `False` at RTL and
`True` at gate level in all four. **The output divergence has survived
four RTL waves and three hardens unchanged.** It is now the only thing
left of the disagreement, and it is the thing `docs/26` said mattered.

### 6.2 The experiment `docs/26` specifies: the sentinel disabled

Run at RTL, on the same commit the netlist was synthesized from, with
one function replaced and nothing else touched.

`hw/tb/test_fi_campaign.py` is not this document's file to change, so
the RTL and the campaign are extracted from `bc91c71` into a scratch
tree and `fill_fifo_sentinel` is rebound to a stub that keeps its timing
— one clock edge and 3 ns, which the campaign's bring-up is timed
against — and drops the writes. That leaves exactly one variable.

| | RTL, sentinel ON | RTL, sentinel OFF |
|---|---|---|
| `wdog_fetch_dir` / `report_kept` | `[0, 1, 2, 3, 4, 2]` | **`[0, 1, 2, 3, 4, 2]`** |
| `wdog_fetch_dir` / `report_erased` | `[0, 1, 2, 3, 4, 2]` | **`[0, 1, 2, 3, 4, 2]`** |
| `wdog_oh_dir` / `report_kept` | `[0, 1, 2, 3, 4, 2]` | **`[0, 1, 2, 3, 4, 2]`** |
| `wdog_oh_dir` / `report_erased` | `[0, 1, 2, 3, 4, 2]` | **`[0, 1, 2, 3, 4, 2]`** |

**[fact, one run, eight records, `DETECTED` and `STATUS = 0x16`
throughout]**. The sentinel-on half is asserted to reproduce the
committed campaign before the sentinel-off half is read, so a run that
failed to reproduce the baseline could not be mistaken for a result.

**The sentinel is not the cause.** Removing it changes nothing: not the
class, not the flags, not one word of the event stream. `docs/26`
section 6.3's leading alternative explanation is **excluded by
measurement**, and the two arguments that document offered against it —
that the RTL's wrong words are `0, 1, 2, 3` rather than the sentinel,
and that the undefined queue slots are on the gate-level side — are now
supported by a direct test rather than being suggestive.

### 6.3 Placement, swept on both sides

A one-cycle difference in where the construction lands would explain the
divergence as well as a difference between the two levels. `docs/26`
section 6.2 swept six placements per construction **at gate level** and
found none that reproduced the RTL's stream. The mirror question — is
there an **RTL** placement that returns the golden stream, that is, one
where the RTL behaves the way the netlist does — was never asked, and
without it "no gate-level placement matches the RTL" and "the two levels
differ" are not the same statement.

Both are asked here, by the same mechanism in both directions: the
script anchors on the first `D_IDLE` after BUSY rises, and prepending a
wait moves the anchor to a later one.

| sweep | runs | result |
|---|---|---|
| gate level, 2 nets x 2 constructions x 6 placements | **24** | every one returns the golden stream; **none** reproduces the RTL's |
| RTL, the same 24 | **24** | every one returns `[0, 1, 2, 3, 4, 2]`; **none** returns golden |

**[fact, `notes.disagreement_probe` in
`hw/tb/gl_fi_results_signoff-6x2.json`, and the RTL run of section 6.2]**.
Forty-eight runs, and the two levels do not meet anywhere in the
alignment neighbourhood.

### 6.4 What is closed, and what is left

**Closed.** The experiment `docs/26` section 10.2 item 1 specifies has
been run and is decisive: **the AER queue sentinel fill does not explain
the divergence**. With placement excluded on both sides as well, the
difference between the two campaigns on these four records is a
difference **between the two levels**, not between the two harnesses.
`docs/26` section 6.3's "not claimed: that the cause is isolated" is
superseded.

**What that means for the design.** On the netlist that would be
manufactured, the deadlock these constructions build recovers with the
**correct output**, at every placement tested, on three hardens. At RTL
the same construction recovers with a corrupted event stream. The
neuron state file is golden at both levels — the RTL records carry
`state_ok = 1` with `spikes_ok = 0` — so the divergence is in the output
path and not in the inference.

**What is not established.** *Which* level is right about the silicon.
Nothing here says the netlist is more trustworthy than the RTL on this
point; it says they differ and that the harness is not why. The
gate-level side is X-pessimistic and the RTL side is X-optimistic, and
`docs/24` section 6 is a worked example of that difference producing a
result on this very design — but the queue read path here is not
obviously an X question, and no evidence in this document decides it.

**The one uncontrolled difference that remains** is the device boundary:
the RTL campaign drives `pilot_top`'s named ports and the gate-level
campaign drives the Tiny Tapeout wrapper's pins, because that is what
the netlist is. Two things bound it and neither closes it. The wrapper
is a pin map and a two-flop reset synchronizer, and the **uninjected
control run through those pins reproduces the golden stream exactly**
(section 4.1, measurement A), so the wrapper does not corrupt the event
path in general. Excluding it outright needs an RTL run of these four
constructions *through the wrapper*, which is a fifth harness and is not
built here.

**Consequence for `docs/16` section 5.8.** Its ranking rested on two SDC
records that no longer exist at either level, because the repair it
asked for was made. What replaces them is narrower and still real: this
construction returns a wrong event stream at RTL and a right one on the
netlist, on a design where the report itself is now unerasable at both.

---

## 7. What it cost

**Every wall time in this document is load-dependent and most of them
were measured on a machine that was running a place-and-route flow and
two other simulations.** That is stated first because `docs/24` section
5.3 and `docs/26` section 7 both quote cost ratios measured on an idle
machine, and these do not reproduce them.

| | injections / tests | wall | per unit |
|---|---|---|---|
| Gate-level campaign, `signoff-6x2` | 561 | 3,115.9 s | **5.55 s / injection** |
| RTL campaign of record, `bc91c71` | 378 | 443.1 s | **1.17 s / injection** |
| ratio | | | **4.74x** **[estimate]** |
| Gate-level functional, `tr-margin`, idle machine | 20 | 103.5 s | 26,684 ns / s |
| Gate-level functional, `GL_PRELOAD=1`, idle machine | 21 | 66.3 s | 21,534 ns / s |
| RTL functional, Icarus 12.0, idle machine | 31 | 47.9 s | 51,192 ns / s |
| ratio | | | **1.9x to 2.4x** **[estimate]** |
| Gate-level functional, `signoff-6x2`, contended | 20 | 328.0 s | 8,417 ns / s |

**[fact for the measurements, estimate for the ratios]**. Every wall
figure is cocotb's own `REAL TIME` footer, on both sides, so the two
columns are measured the same way; the campaign row's 3,115.9 s is the
figure the suite writes into its log, and the whole run including
elaboration was 3,220.7 s. The campaign
ratio brackets with `docs/26`'s: that document measured 4.1x under
partial contention and 3.4x on a quieter machine, and 4.74x here under
heavier contention is the same statement. The functional ratio came out
*lower* than `docs/24`'s 3.13x, on a different test mix — the twenty
gate-level tests are not the thirty-one RTL ones — so the two are not
directly comparable and neither is presented as a correction of the
other.

The conclusion is the one both earlier documents drew and it is
unchanged: **gate level costs a small multiple, not an order of
magnitude.** The 165-injection configuration sweep is the single largest
block and is the one part that could be sampled rather than swept if the
budget ever mattered.

Elaboration is unchanged in kind: one `sim.vvp` per netlist, built once
and reused by every test in the run.

---

## 8. Corrections to `docs/24` and `docs/26`

Neither document is edited. What each now says wrongly, location by
location:

### 8.1 `docs/24`

| Location | Now |
|---|---|
| Status line, headline, section 4: "20 of the 27 tests" | The suite is **31** tests. The gate-level twenty are unchanged; the RTL-only set is **11**, not 7 |
| Section 4.2's table of seven | Four rows short — the four tests of section 3.1 above |
| Section 4.2: "the port-driven fraction of the suite is 74 %" | **65 %** |
| Section 1.1: netlist, blob, 1,275 flip-flops, 33,801 instances | Describes `shape-6x2`, which is two hardens superseded. The current sign-off is `signoff-6x2`, **1,296** flip-flops |
| Section 1.2: "the current working tree's `hw/rtl` has the same blob as `e1361fe`" | Was true when written; four waves have landed since |
| Sections 2, 7: `make -f Makefile.gl` runs against `shape-6x2` | The default is now `signoff-6x2`; `GL_TAG=shape-6x2` reproduces the document |
| Section 8.2 item 2: "no fault injection at gate level, at all" | Closed by `docs/26`, and closed again here for the structures added since |
| Section 8.3 item 1: fix or annotate the over-range test | **Still open** after four RTL waves |
| Section 8.3 item 3: re-run against the GDS action's netlist | **Still open**. This is a local LibreLane harden, as `docs/24` and `docs/26` both are |

### 8.2 `docs/26`

| Location | Now |
|---|---|
| Section 1.1: netlist, 1,275 flip-flops | `shape-6x2`. Superseded; **1,296** |
| Section 1.2: the RTL baseline is the `a13a93f` campaign, 365 injections | For `signoff-6x2` the derived baseline is the **`bc91c71`** campaign, **378** injections |
| Section 3.2's rename table: `u_lif.out_pend` -> `u_pilot.lif_out_valid`, `oh_valid` -> `aer_out_vld`, `u_evq_out.rd_valid` -> `u_pilot.fo_rd_valid` | **All three flip-flops are gone.** Each flag is now two rails; section 4.2 above is the replacement table |
| Section 3.3: `cfg_axon[3]` is `u_pilot._0255_` | **`u_pilot._0253_`** in this netlist. The identification is by experiment and re-derives itself; the name in the document is a photograph |
| Section 5.4: `u_lif.out_event[14]` is an RTL injection into a flip-flop that does not exist | Unchanged and still true |
| Section 6, and section 6.3's "not claimed: that the cause is isolated" | **Isolated now.** The sentinel is excluded by measurement; section 6 below |
| Section 8.1: "all 1,275 flip-flops drive a named net" | Still true of all **1,296** |
| Section 9: `make -f Makefile.glfi` writes `hw/tb/gl_fi_results.json` | True only for `GL_TAG=shape-6x2`; other hardens write `gl_fi_results_<tag>.json` |
| Section 10.2 item 5: "if the submission re-hardens, re-run this campaign before quoting any of its numbers for the new design" | Done. That is this document |

---

## 9. Reproducing this

```bash
make -f tools.mk toolcheck        # yosys 0.67+146; does NOT govern section 2

cd hw/tb

# what would be read, with blobs and the RTL snapshot
make -f Makefile.gl   provenance
make -f Makefile.glfi provenance

# the functional suite: 20 tests, 19 PASS, 1 FAIL (section 3.3)
make -f Makefile.gl
GL_PRELOAD=1 make -f Makefile.gl          # 21 tests, 21 PASS

# the RTL side of section 3.2, on the same simulator
PATH=$HOME/.local/opt/iverilog13/usr/bin:$PATH \
  make -f Makefile.pilot SIM_BUILD=/tmp/sb_iv13 \
       COCOTB_RESULTS_FILE=/tmp/rtl_iv13.xml

# the campaign
make -f Makefile.glfi                      # section 5
make -f Makefile.glfi GLFI_GROUPS=__none__ # the method validation alone
make -f Makefile.glfi GLFI_GROUPS=rail_sweep,new_redundancy

# the previous netlists, unchanged
GL_TAG=shape-6x2 make -f Makefile.gl
GL_TAG=tr-margin make -f Makefile.glfi
```

**One dependency is fragile and is stated rather than hidden.** The
derivation of section 1.2 reads the RTL snapshot that
`hw/openlane/pin_rtl.py` made for the harden, and the run's
`resolved.json` names it under a scratch directory that does not
survive a machine reboot. When it is gone the suite **fails with a
message saying so** rather than falling back to a guess, and
`GLFI_NETLIST_RTL=<commit>` supplies the answer by hand:

```bash
GLFI_NETLIST_RTL=bc91c71 make -f Makefile.glfi   # signoff-6x2
GLFI_NETLIST_RTL=e1361fe GL_TAG=shape-6x2 make -f Makefile.glfi
```

The derived value is written into every log as `netlist_rtl`, so a log
that already exists never has to be re-derived to be read.

Section 6.2's experiment is an RTL run and is **not** in this
repository, because `hw/tb/test_fi_campaign.py` is not this document's
file to change. It is reproduced by extracting the RTL and the campaign
from the commit the netlist came from into a scratch tree and rebinding
one function:

```bash
D=$(mktemp -d)/dis; mkdir -p $D/hw/tb $D/hw/rtl
for f in pilot_top lif_core aer_fifo tmr_voter secded_enc secded_dec \
         npu_regbank scrub tt_um_melihakbulut_nssoc; do
  git show bc91c71:hw/rtl/$f.v > $D/hw/rtl/$f.v
done
git show bc91c71:hw/rtl/npu_regs.vh    > $D/hw/rtl/npu_regs.vh
git show bc91c71:hw/tb/test_fi_campaign.py > $D/hw/tb/test_fi_campaign.py
ln -s "$PWD/sw" $D/sw     # from the repository root
```

with a cocotb module beside the campaign that does only this:

```python
import test_fi_campaign as fi

async def _no_sentinel(dut):          # the real one's timing, no writes
    await RisingEdge(dut.clk)
    await Timer(3, unit="ns")

# for sentinel in (True, False):
#     fi.fill_fifo_sentinel = fi.fill_fifo_sentinel if sentinel \
#                             else _no_sentinel
#     for group, case, _n, steps in fi.watchdog_cases():
#         if case in ("report_kept", "report_erased"):
#             rec = await fi.injection(dut, geo, group, case, None, 0,
#                                      None, script=steps)
```

driven by `Makefile.fi` with `TOPLEVEL := pilot_top` and the extracted
sources. The sentinel-on half must reproduce the committed campaign
before the sentinel-off half is read; section 6.2's run asserts that.

---

## 10. What holds, what is superseded, what could not be re-established

### 10.1 Conclusions that still hold, re-established on the new netlist

1. **The netlist implements the RTL's function.** `docs/24` section 8.1
   item 1, now on a 1,296-flip-flop netlist and on three hardens at
   once. Twenty port-driven tests, identical simulated time to the RTL,
   test for test.
2. **The configuration TMR is three independent banks, bit for bit.**
   `docs/24` section 8.1 item 2 and `docs/26` section 10.1 item 3.
   165 of 165 replica flip-flops corrected, none masked, none SDC.
3. **The pointer TMR has functional netlist evidence.** `docs/26`
   section 10.1 item 2. 72 of 72 corrected into 36 replica flip-flops.
4. **The injector models an upset and not a stuck-at.** `docs/26`
   section 10.1 item 4. All six measurements reproduce exactly on the
   new netlist, including the reset experiment that separates the two
   primitives outright.
5. **Every sequential element of the netlist is reachable.** `docs/26`
   section 10.1 item 5, at 1,296 rather than 1,275.
6. **The hardening claims survive the step from RTL to netlist.**
   `docs/26` section 10.1 item 1, and more strongly: 370 like-for-like
   injections and **370** identical classifications, where `docs/26` had
   355 of 357.
7. **The RTL suite is green on two Icarus versions with identical
   per-test simulated time.** `docs/24` section 8.1 item 4, at 31 tests
   rather than 27.
8. **Gate level costs a small multiple, not an order of magnitude.**
   `docs/24` section 5.3 and `docs/26` section 7, as a conclusion. The
   specific ratios are section 10.3 item 1.

### 10.2 Superseded

1. **The netlist `docs/24` and `docs/26` describe.** `shape-6x2`, 1,275
   flip-flops, is two hardens out of date. Everything either document
   says about *that* netlist remains true of it and is no longer a
   statement about the design being manufactured.
2. **The two SDC records of `docs/26` section 6 and `docs/16` section
   5.8.** They do not exist at either level on the wave-9 design,
   because the repair they asked for was made. What remains of the
   disagreement is the output divergence, and section 6 is it.
3. **`docs/26` section 6.3's "not claimed: that the cause is
   isolated".** The sentinel is excluded by measurement and placement is
   excluded on both sides. The residual is the device boundary, named in
   section 6.4.
4. **`docs/26` section 3.2's rename table, in three rows.** The three
   one-bit valid-flag flip-flops it maps are gone; each flag is two
   rails. Section 4.2 is the replacement.
5. **`docs/26` section 3.3's `u_pilot._0255_`.** The bit is
   `u_pilot._0253_` here. The identification re-derives itself, which is
   why this is a superseded number and not a broken suite.
6. **`docs/24`'s test counts.** 27 becomes 31, seven RTL-only becomes
   eleven, 74 % port-driven becomes 65 %.
7. **`docs/24` section 8.2 item 2 and section 8.3 item 4**, already
   closed by `docs/26`, are closed again for the three structures added
   since.
8. **The claim that the rails' polarity transform is what keeps them
   apart.** Section 4.3. It is `keep_hierarchy`; the transform is not in
   the netlist.

### 10.3 Could not be re-established

1. **`docs/24` section 5.3's 3.13x and `docs/26` section 7's 4.1x, as
   numbers.** Every long run here shared the machine with a
   place-and-route flow and other simulations. The campaign ratio came
   out 4.74x and the functional one 1.9x to 2.4x on a different test
   mix; both are tagged **[estimate]** in section 7 and neither is
   offered as a correction. Re-measuring them properly needs an idle
   machine and is a twenty-minute job for whoever wants the number.
2. **`docs/24` section 6.2's whole-design X scan** — 2,564 named nets X
   before the over-range spike and 2,157 further nets X after it. Those
   figures came from throwaway diagnostic modules that `docs/24` section
   6.4 records as deliberately not kept, and they were not rebuilt. What
   *is* re-established is the narrower and more useful claim: over 561
   injections, `SKIPPED_X` never fired, so no injection in this campaign
   landed on an undefined bit.
3. **Anything about the TT-generated netlist.** `docs/24` section 8.2
   item 3 and `docs/26` section 8.3 item 5 stand unchanged: this is a
   local LibreLane harden of the submission shape, not the TTIHP26b GDS
   action's container, and the ROADMAP P1 bar as worded is still met
   only by that action. Re-running there remains open.
4. **Which level is right about the section 6 divergence.** The two are
   shown to differ for a reason that is not the harness. Nothing here
   says which of them predicts the silicon.
5. **Timing.** Zero-delay functional run, as in both earlier documents.
   A fault whose effect depends on a hold violation is invisible here;
   post-route STA on three corners in the same run directory is the
   complementary evidence.
6. **CI.** `docs/19`'s parity gate still does not know about either
   fragment, and adding them still needs the decision about which Icarus
   CI installs that `docs/24` section 8.2 item 6 records.

### 10.4 Open items this leaves

1. **`test_axon_out_of_range_is_dropped_and_counted` should write the
   weight memory before enabling the core.** `docs/24` section 8.3 item
   1, now four RTL waves old. Owned by whoever owns
   `test_pilot_top.py`.
2. **`test_fi_campaign.py`'s target list names three registers the
   design does not have**: `u_lif.out_event[14]` (`docs/26` section 10.2
   item 2) and now `fetch_timeout` and `oh_timeout`, retired by
   `3458d36`. All three are harmless and all three make the target list
   describe a design that is gone.
3. **EVQ_IN's two `rd_valid` rails are not in the RTL campaign's target
   list.** They are injected here and they behave; adding them at RTL
   would make the two campaigns symmetric over the rails.
4. **An RTL run of the four `report_*` constructions through the Tiny
   Tapeout wrapper** would remove the last uncontrolled difference in
   section 6.
5. **The `GL_TAG` default has to be moved by hand on every re-harden.**
   That is deliberate (section 1.4), and it is also exactly the thing
   that went stale once. A check that fails when the default run's
   pinned RTL is not `HEAD` would catch it; it is not written here
   because it would fail legitimately whenever the RTL is ahead of the
   last harden, which is most of the time.
