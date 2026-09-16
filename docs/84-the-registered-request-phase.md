<!--
SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
SPDX-License-Identifier: CC-BY-4.0
-->
# 84 — The registered request phase, built, proved and priced

`docs/72` section 15 item 5 named this change and did not price it: *"A registered request phase in the fabric is a latency cost on
every load and a `docs/50`-class change; it is named here as the thing
the paths have in common, not priced."* `docs/83` then measured that
nothing else is the thing the paths have in common — **wire is 3.6 % of
a violating path at the median**, and the median violating path is **88
gate stages deep**. A floorplan moves wire.

This document builds the change behind `soc_bus.v`'s new `REQ_REG`,
proves the default is the same machine it was, proves the property set
at both settings, and prices both sides.

**The price is now two numbers instead of one estimate.** The deepest
endpoint class in the netlist — the CLINT's response registers, which
`docs/73` section 7.3 and `docs/83` both identified — goes from **81
combinational levels to 16**, the design's maximum from **81 to 69**, and
its median from **39 to 20**. The same workload that runs in **416,673**
cycles runs in **520,398**, which is **24.89 % more**.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged, with the
derivation stated.

**Everything below was run for this document.** Three synthesis runs
(`s87-gold-syn`, `s87-rr0-syn`, `s87-rr1-syn`), two whole-SoC
simulations (`sim-rr0`, `sim-rr1`), six SymbiYosys tasks, one yosys
equivalence miter, the `soc_bus` cocotb suite twice, and
`sw/tests`. No number here is copied from another document except
where it is named as such.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Is the default unchanged?** | **Yes, and proved rather than inspected.** A miter of the committed fabric against the parameterised one at `REQ_REG = 0` closes: `Of those cells 231 are proven and 0 are unproven. / Equivalence successfully proven!` **[fact]**. The netlist is not bit-identical — 47,114 cells against 46,453 — which is the `docs/77` section 18.2 situation and is why the claim is a proof. |
| **Does the property set still hold?** | **Yes, at both settings, every task.** `bmc`, `prove`, `cover` and the three `_rr` tasks all `DONE (PASS, rc=0)` **[fact]**. One property failed induction at `REQ_REG = 1` and was made **stronger**, not weaker; section 4.2. |
| **What does it buy?** | **The depth.** Maximum 81 → 69 levels, median 39 → 20, mean 41.3 → 30.8, endpoints deeper than 40 levels 3,124 (48.90 %) → 2,203 (34.13 %) **[fact]**. The CLINT's `s_rdata_clint[*]`, the deepest endpoint class in the design, goes **81 → 16**. |
| **What does it cost in cycles?** | **+103,725 cycles, +24.89 %**, 416,673 → 520,398, `[TB] PASS` at both **[fact]**. |
| **What does it cost in area?** | **+7,618.97 um2, +1.08 %** against the same file at `REQ_REG = 0`. The register is **68 flip-flops** in the mapped netlist; the design-wide delta is **+67**, so one flip-flop elsewhere went with them **[fact]**. |
| **Does it cost head-of-line blocking?** | **No, and the first version of this document said it did.** The blocking is the round-robin arbiter's and is there at both settings; the instruction port's grant count while the data port's slave refuses is the same at both, and its first grant comes one cycle *earlier* at `REQ_REG = 1` **[fact, section 2.4a]**. |
| **Should the default change?** | **No, not on this evidence.** Section 9. A quarter of the cycle count is not bought back by a depth number alone: what closes the design is slack on a placed and routed layout, and no layout of this netlist has been run. |

---

## 2. What was built

`hw/soc/rtl/soc_bus.v` gains `parameter integer REQ_REG = 0`, beside
nothing — it is the file's first parameter. Its header gains a section
stating the contract; the four paragraphs below are that section's
argument in short.

### 2.1 Two events where there was one

The change is not "put flip-flops on five outputs". It is that **the
grant and the transfer stop being the same cycle**, and every piece of
bookkeeping in the file has to be told which of the two it belongs to.

Five names cross the boundary and everything downstream reads them
rather than reading the arbitration:

| name | meaning | at `REQ_REG = 0` |
|---|---|---|
| `accepted` | a master is granted this cycle | `any_win && target_ready` |
| `xfer` | a request is handed to its target this cycle | the same signal |
| `xfer_tgt`, `xfer_own` | which target, which master | `tgt`, `d_wins` |
| `req_busy` | the request register holds something | the constant `1'b0` |

`last_was_d` and the outstanding counters turn on `accepted`, because a
grant is the master's event. **The ownership queue and the error slave's
response strobe turn on `xfer`**, because a response is the slave's
event — and that is the single most likely way to get this change wrong.
`q_owner` matches a response to the master that asked for it, and it is
popped by the slave's `rvalid`. If the request reaches the slave a cycle
after the grant and the push does not move with it, a response arriving
in the gap pops an entry belonging to a different request, and every
later response at that slave goes to the wrong master.

### 2.2 The register is a skid buffer, so throughput does not change

`cap_ok = !r_val || r_xfer` is the whole throughput statement: the
register accepts a request whenever it is empty **or is being emptied in
the same cycle**. A master can therefore still be granted in the cycle it
asks, and still granted on every consecutive cycle. What grows is
latency, by exactly one cycle, on every transaction. Section 6 is what
that is worth on a real workload, and it is more than the phrase "a
latency cost on every load" suggests.

`mi_gnt_o` and `md_gnt_o` stop depending on `s_gnt_i` entirely. That is
the point: at `REQ_REG = 1` a grant is a function of the two masters'
requests, the outstanding counters and one register bit, and of nothing
downstream of the decode.

### 2.3 Counters stay on the grant, and the queue cannot overflow

`cnt_i`, `cnt_d`, `lock_i` and `lock_d` deliberately stay on the grant.
They enforce `MAX_OUT` and the same-slave restriction **on the master**,
and a master owns a request from the moment it is granted one; counting
them at the transfer would let a master be granted a third request while
its second was still in the register. The consequence is that a slave's
queue occupancy lags its masters' counts by at most one entry. The queue
is sized `QD = 2 * MAX_OUT = 4` and the register holds one of the at most
four granted requests, so the queue still cannot overflow —
`soc_bus_props.v` F6 and F8 are what say so, not that sentence.

### 2.4 The error slave, a refused request, reset, and the lock

* **The error slave** moves behind the register with everything else. It
  is always ready, so a captured request addressed to it transfers on the
  next cycle and `err_rvalid` follows one cycle after that: the same
  one-cycle error latency, displaced like every other response. An
  unmapped access still reaches the core as `data_err_i` and still costs
  exactly one `rvalid`.
* **A refused request** is not captured. A captured request the slave does
  not grant is **held**: `s_req_o`, `s_addr_o`, `s_we_o`, `s_be_o` and
  `s_wdata_o` do not change until `gnt`. That is Ibex protocol rule 1
  obeyed by this fabric **toward its slaves**, which the combinational
  form does not obey: at `REQ_REG = 0` the arbitration winner can change
  while a slave is still refusing, because `can_issue_i` and
  `can_issue_d` turn on as responses return, and the refused slave then
  sees its request vanish. It is a new property, F3e, and it is the one
  structural thing the parameter buys besides the depth. **F3e with its
  `REQ_REG != 0` guard removed is falsified at `REQ_REG = 0` in four
  steps of bmc** — failed assertions at `soc_bus_props.v:546` and `:547`,
  the `s_req_o` and `s_addr_o` clauses, engine smtbmc yices,
  `DONE (FAIL, rc=2)`
  **[fact, scratch job `scratchpad/f3e0/`, 2026-09-16]** — which is what
  makes "the combinational fabric does not satisfy it" a result rather
  than a reading of the source. What it does **not** cost is
  head-of-line blocking; section 2.4a is the measurement, and the
  sentence that used to stand here was wrong in both halves.
* **Reset** clears the register asynchronously like every other register
  in the file, and `issue_en` keeps the fabric shut for one further cycle
  after release. Nothing is in flight across a reset.
* **The lock** is untouched. It is enforced on the grant, from `lock_i`
  and `lock_d`, which the register does not sit in front of. A master
  switching target still waits for its outstanding count to reach zero,
  and that count now includes a request sitting in the register, so the
  dead cycle the header prices at one becomes two.

### 2.4a Head-of-line blocking is the arbiter's, and it is there at both settings

**This section replaces a claim this document made and had not
measured.** Until 2026-09-16 the bullet above, `soc_bus.v`'s header and
section 8 all said: *"The price is head-of-line blocking: while the
register holds a request for a slave that withholds `gnt`, neither master
is granted, where the combinational fabric would have let the other master
go elsewhere. No slave in this SoC withholds `gnt`, so the case is
unreachable here."* **[superseded 2026-09-16]** Both halves are false.

**Two slaves withhold `gnt`.** `hw/soc/rtl/soc_apb_bridge.v:84` is
`assign gnt_o = req_i && (state == ST_IDLE);` and
`hw/soc/rtl/soc_npu.v:1010` is
`assign gnt_o = req_i && may_accept && (win_state == W_IDLE) && (!win_out || rvalid_o);`.
Both are exercised by the very run section 6 prices: each of the 1,150
console characters counted in `hw/soc/out/sim-rr1/sim.log` was written
through the APB bridge, and the same image runs the NPU self-test
(`npu: 0x0000000c events` in that log). The state is
reachable on this tree, and the property set's own cover R2 —
`cover (f_fly && !f_fly_xfer)`, a captured request its slave has not yet
taken — is reached in `cover_rr`.

**And the combinational fabric blocks too.** `wire [2:0] tgt = d_wins ? tgt_d : tgt_i;`
feeds `wire target_ready = (tgt == ERRSLV[2:0]) ? 1'b1 : s_gnt_i[tgt];`,
`i_wins` is `can_issue_i && !d_wins`, and `last_was_d` advances only on
`accepted`. So when the arbitration winner's slave refuses, the loser is
refused with it, and the round-robin bit does not move, so it goes on
being refused. The blocking belongs to the round-robin arbiter, not to
the register.

`hw/soc/tb/tb_soc_bus_hol.v` is the bench that says so. The instruction
port sits at the always-ready RAM, the data port at a slave shaped like
the APB bridge — `gnt` only when idle — and both masters request
continuously for 201 cycles after reset:

| the data port's slave | instruction-port grants, `REQ_REG = 0` | `REQ_REG = 1` | data-port grants, 0 → 1 | first instruction grant, cycle, 0 → 1 |
|---|---:|---:|---:|---:|
| ready | 100 | 100 | 101 → 101 | 2 → 2 |
| refuses 3 cycles per transaction | 50 | 50 | 51 → 51 | 2 → 2 |
| refuses 10 per transaction | 19 | 19 | 19 → 20 | 2 → 2 |
| refuses 50 per transaction | 4 | 4 | 4 → 5 | 2 → 2 |
| refuses for 4 cycles from reset | 99 | **100** | 100 → 100 | 4 → **3** |
| refuses for 172 cycles from reset | 15 | **16** | 16 → 16 | 172 → **171** |
| never grants | 0 | 0 | 0 → 1 | never → never |

**[fact, `hw/soc/tb/tb_soc_bus_hol.v` under Icarus 12, log in
`scratchpad/hol2/hol.log`, 2026-09-16.]** The command is in the bench's
own header. The two refusal lengths from reset are taken from the two
slaves that really refuse: `soc_bus.v`'s header prices the peripheral
bridge at "four or more" cycles and `soc_bus.v`'s port-5 note prices the
NPU at "about 172".

**The instruction port's grant count is the same at both settings, or one
higher at `REQ_REG = 1`, in every case measured** — including the slave
that never grants, where both settings starve it completely. Where there
is a difference at all it is in the register's favour: its first grant
arrives one cycle earlier, because the grant no longer waits for the
*other* master's slave.

**The one asymmetry the bench found needs a master that breaks rule 1.**
If the data master asserts `req` for a single cycle and withdraws it
without having been granted — which protocol rule 1 forbids, and which
`soc_bus_props.v:172` assumes of both master ports — then at
`REQ_REG = 0` its request simply evaporates and the
instruction port is granted in all 201 cycles, while at `REQ_REG = 1` the
request was captured, and it blocks the instruction port for as long as
its slave refuses: 201 grants against 0 at a slave that never grants, and
201 against 22 at one that refuses for 172 cycles **[fact, the same log,
`+MODE=1`]**.

One number in that mode is worth keeping apart from the blocking, because
it is the cycle cost of section 6 seen in a second instrument: with the
data port idle and the RAM always ready, the instruction port gets 201
grants in 201 cycles at `REQ_REG = 0` and **134** at `REQ_REG = 1`. That
is not blocking, it is `MAX_OUT`: two outstanding requests over a
round trip that is one cycle longer is two grants every three cycles.

### 2.5 The clock-gate enable gains one term

`clk_en_o` gains `|| req_busy`. G1 to G5 in the header enumerate the
reasons this module can have work to do at the end of a cycle, and at
`REQ_REG = 1` there is a sixth, written into the header as G6: a
captured request can be handed to its slave in a cycle when neither
master is asking for anything and no response is coming back. **F10 is
what would have caught its omission** — the register's valid bit would
have cleared in a cycle the gate removed — and the term is there for that
reason rather than for an argument that it is needed.

### 2.6 Plumbing

`hw/soc/rtl/soc_top.v` gains `parameter integer REQ_REG = 0` and
forwards it to `u_bus`, exactly as it forwards `CLKGATE` and
`WAKE_GNT`. `hw/soc/flow/syn_soc_top.sh` and `hw/soc/flow/sim_soc.sh`
take it as `SOC_REQ_REG` and `hw/soc/tb/cocotb/Makefile.soc_bus` as
`REQ_REG`, each defaulting to 0 and each emitting nothing at 0.
`sw/tests/test_soc_synthesis_guards.py` gains
`test_the_registered_request_phase_ships_off_and_is_forwarded`, which
pins the default in both modules, checks the forwarding, and fails if
any RTL file or any flow script this repository does not know about
selects the parameter. It is mutation-checked: setting `soc_top.v`'s
default to 1 makes it fail **[fact]**.

**It did not originally guard the stage that can satisfy it.** Pinning
`parameter integer REQ_REG = 0` in the RTL says nothing about what
`hw/soc/flow/sim_soc.sh` and `hw/soc/flow/syn_soc_top.sh` do when
`SOC_REQ_REG` is unset, and those two are what select the knob for every
shipped run; `hw/soc/tb/cocotb/Makefile.soc_bus` is the same for the
block-level suite. `SOC_REQ_REG=${SOC_REQ_REG:-1}` in either script
would have moved the shipped synthesis, the shipped simulation and with
them the 416,673-cycle figure, with nothing turning red. Since
2026-09-16 the guard asserts `SOC_REQ_REG=${SOC_REQ_REG:-0}` in each
script it allows to carry the knob, and `REQ_REG ?= 0` in the Makefile.
All three are mutation-checked: flipping each default to 1 in turn makes
the test fail, at `test_soc_synthesis_guards.py:2114`, `:2114` and
`:2121` **[fact, 2026-09-16]**.

---

## 3. The default is not bit-exact, and it is equivalent

The honest statement first: **the netlist changes at `REQ_REG = 0`.**

| | committed fabric | `REQ_REG = 0` | delta |
|---|---:|---:|---:|
| cells | 47,114 | 46,453 | **-661** |
| flip-flops | 5,998 | 5,998 | 0 |
| chip area | 704,104.0020 um2 | 702,750.8754 um2 | -1,353.1266, **-0.19 %** |

**[fact, `hw/soc/out/s87-gold-syn` and `s87-rr0-syn`, each run's own
`area.rpt` and the run summary of `syn_soc_top.sh`.]** Naming the
winner's payload, putting the two arms around it and routing the queue
through `xfer` gives the mapper a different expression tree, and it
folds it differently — here, slightly smaller. `docs/77` section 18.2 is
the precedent for both the observation and what to do about it.

So the claim that matters was proved. `git show HEAD:hw/soc/rtl/soc_bus.v`
as `gold`, the working file at its default as `gate`, both flattened,
`async2sync` for the asynchronous resets:

```
read_verilog -I hw/soc/rtl <committed soc_bus.v>
rename soc_bus gold
prep -flatten -top gold
design -stash A
read_verilog -I hw/soc/rtl hw/soc/rtl/soc_bus.v
rename soc_bus gate
prep -flatten -top gate
design -stash B
design -copy-from A -as gold gold
design -copy-from B -as gate gate
async2sync
equiv_make gold gate equiv
prep -flatten -top equiv
opt -full
equiv_simple -seq 5
equiv_induct -seq 5
equiv_status -assert
```

It closes in `equiv_simple` alone:

```
9. Executing EQUIV_SIMPLE pass.
Found 8 unproven $equiv cells (2 groups) in equiv:
  Trying to prove $equiv for \last_was_d: success!
 Grouping SAT models for \push:
  Trying to prove $equiv for \push [0]: success!
...
Proved 8 previously unproven $equiv cells.

10. Executing EQUIV_INDUCT pass.
No selected unproven $equiv cells found in equiv.
Proved 0 previously unproven $equiv cells.

11. Executing EQUIV_STATUS pass.
Found 231 $equiv cells in equiv:
  Of those cells 231 are proven and 0 are unproven.
  Equivalence successfully proven!
```

**[fact, 2026-09-16, yosys 0.67+94; the miter was run again the same day
after the corrections below and printed the same three numbers — 231
cells, 231 proven, 0 unproven — from a `gold` taken fresh out of
`git show HEAD:hw/soc/rtl/soc_bus.v`, md5
`7ba0a36aea86e7de84de8128b151ba7e`.]** The eight cells that needed a SAT
call are exactly the eight the change touches: `last_was_d`, whose enable
went from `accepted` to a differently-spelled `accepted`, and the seven
bits of `push`, which went from `accepted && (tgt == k)` to
`xfer && (xfer_tgt == k)`. `REQ_REG = 0` is the same sequential machine
as the code before the parameter existed. **A cell count would not have
shown that, and in this case would have suggested the opposite.**

---

## 4. What the property set says, at both settings

### 4.1 The runs

`hw/soc/formal/soc_bus.sby` gains three tasks rather than an edit to the
default, the way `regfile_scrub.sby` sets `SCRUB`: `bmc_rr`, `prove_rr`
and `cover_rr` carry a task-prefixed `chparam -set REQ_REG 1 soc_bus`,
and the three original tasks run the script they have always run.

| task | setting | engine | result | elapsed |
|---|---|---|---|---:|
| `bmc` | `REQ_REG = 0` | smtbmc yices, depth 24 | `DONE (PASS, rc=0)` | 45 s |
| `prove` | `REQ_REG = 0` | smtbmc yices, depth 12 | `DONE (PASS, rc=0)`, `returned pass for basecase`, `returned pass for induction` | 15 s |
| `cover` | `REQ_REG = 0` | smtbmc yices, depth 24 | `DONE (PASS, rc=0)`, **20 cover statements reached**, none unreached | 5 s |
| `bmc_rr` | `REQ_REG = 1` | smtbmc yices, depth 24 | `DONE (PASS, rc=0)` | 108 s |
| `prove_rr` | `REQ_REG = 1` | smtbmc yices, depth 12 | `DONE (PASS, rc=0)`, `returned pass for basecase`, `returned pass for induction` | 28 s |
| `cover_rr` | `REQ_REG = 1` | smtbmc yices, depth 24 | `DONE (PASS, rc=0)`, **24 cover statements reached**, none unreached | 6 s |

**[fact, `sby -f soc_bus.sby` from `hw/soc/formal/`, re-run 2026-09-16
after the corrections of sections 2.4a and 5.2; each job's own
`logfile.txt`.]** **The elapsed column is not a result.** sby runs the
six tasks concurrently and these ran beside a synthesis and a whole-SoC
simulation, so the figures moved between runs of the same files — 27 / 8
/ 2 / 70 / 16 / 3 s on the first pass **[superseded 2026-09-16]**, then
40 / 15 / 4 / 95 / 25 / 3, then the column above. The verdicts and the
cover counts did not move in any of them. `cover_rr` reaches R2 — a
captured request its slave has not taken, `soc_bus_props.v:927` — at
step 4, which is the state section 2.4a is about. Every task that passed
before the parameter existed passes at both settings. The four extra
covers at `REQ_REG = 1` are R1 to R4, the request register's own
witnesses; they are in a `generate` and not under an `if`, because an
assertion with a constant-false antecedent is vacuously true and costs
nothing, while a **cover** with a constant-false condition is
unreachable and `docs/09` section B.1 makes that a red result.

### 4.2 The one failure, and why the repair made a property stronger

`prove_rr` failed on its first run, at `soc_bus_props.v:366`, which is
I6 — the invariant that the ghost request phase reconstructed from the
ports IS the design's request phase.

The counterexample, read out of `trace_induct.vcd`: k-induction started
in a state with the fabric's register **full**, the ghost owning it for
the data port and the design owning it for the instruction port. A
hundred idle cycles later the register drained and the two disagreed.

**That state is unreachable and nothing excluded it.** Both bits are
loaded from the same grant, so no real trace can produce the
disagreement — but the property as first written only looked at the
register in the cycle it **drains**, so no earlier cycle ruled the state
out.

**The RTL was not touched, and the repair asserts the property in MORE
cycles rather than fewer.** The register's target and ownership bits are
now checked in every cycle the register is full — `req_busy || xfer`
where it had been `xfer` — which is strictly stronger than the version
that failed, and which is what makes it inductive: loaded together, held
together, equal in every cycle they exist. This is the `docs/09` section
B.3 shape and not a defect, and it is recorded in the property's own
comment so that the next reader does not re-derive the weaker form.

### 4.3 What changed in the property file, and what did not

Nothing was weakened. **At `REQ_REG = 0` every clause elaborates to the
clause that was there before the parameter**, the ghost register folds to
a constant zero, and the `prove` task's own numbers are unchanged.

What was split is the grant/transfer conflation: the per-master
outstanding counts stay on the grant, the per-slave queues move to the
transfer, and the difference — at most one request, in the fabric's
register — is carried by a port-reconstructed ghost and named
`f_out_i_slv` / `f_out_d_slv` where an invariant needs it. Two properties
are **added** at `REQ_REG = 1`:

* **I6**, above, which is what stops the reconstruction being a
  definition the rest of the file would then be circular in;
* **F3e**, Ibex protocol rule 1 toward the slave, which the
  combinational request phase does not satisfy.

F3d, the payload check, is transported rather than dropped: at
`REQ_REG = 1` protocol rule 2 lets a master change its pins the cycle
after its grant, so the comparison is against a ghost copy taken **from
the master ports** at the grant. `soc_bus.v`'s own `r_addr`, `r_we`,
`r_be` and `r_wdata` are named nowhere in the property file.

F10 now covers the request register too. Its seven fields are enumerated
through what they drive — `req_busy` is `r_val`, `xfer_tgt` and
`xfer_own` are `r_tgt` and `r_own`, and the four broadcast outputs are
the payload — because the registers live in a generate arm that does not
elaborate at all at `REQ_REG = 0`, so a hierarchical reference to them
would not compile in the configuration the design ships. The mapping is
total, and `sw/tests/test_soc_clkgate_guards.py` checks that it is still
written down. **That guard caught its absence on the first attempt**,
which is what it is for.

---

## 5. What it buys: the depth

This is the number the whole change exists for.
`hw/soc/pnr/logic_depth.py`, on each run's own `soc_top.netlist.v`,
`SOC_MEM=sram` at 20 ns, same flow and same corner library:

| | committed fabric | `REQ_REG = 0` | `REQ_REG = 1` |
|---|---:|---:|---:|
| max | **81** | 79 | **69** |
| p99 | 79 | 78 | **68** |
| p90 | 74 | 74 | **66** |
| median | **39** | 40 | **20** |
| mean | 41.3 | 40.8 | **30.8** |
| endpoints deeper than 40 levels | 3,124 (48.90 %) | 3,191 (49.95 %) | **2,203 (34.13 %)** |
| endpoints | 6,388 | 6,388 | 6,455 |
| combinational cells | 41,105 | 40,444 | 40,501 |
| sequential cells | 6,001 | 6,001 | 6,068 |

**[fact, `hw/soc/out/s87-gold-syn`, `s87-rr0-syn` and `s87-rr1-syn`.
Both `REQ_REG` arms were synthesised again on 2026-09-16, after the
corrections in this document, into `hw/soc/out/s88-rr0-syn` and
`s88-rr1-syn`: the netlists come back **byte-identical** — md5
`aadbc2026888ac6651052877a31abf14` and `fa283986d0c5c5a3c871ff343573a336`
— and `area.rpt` identical line for line, which is what a comment-only
edit to the RTL should do and is the check that it was one.]**

The committed fabric's column reproduces, to the digit, the profile that
sent this work here: max 81, p99 79, p90 74, median 39, mean 41.3, 48.90
per cent deeper than 40. **The same profile comes back from
`hw/soc/out/s86-abcps-syn`, the run whose abc delay target is expressed
in picoseconds rather than nanoseconds** — a thousandfold tightening —
and from `s85-wg0-syn`, which is the run `docs/77` section 18.5 reports:
`max 81 p99 79 p90 74 median 39 mean 41.3`, `3124 (48.90 %)` in all
three **[fact, `logic_depth.py` on each netlist]**. The depth is not
placement, and it is not synthesis effort.

**What the picosecond target actually changed is worth stating, so the
control is read as what it is.** `s86-abcps-syn` and `s87-gold-syn`
differ in **206 lines of 305,927**, and every one of those 206 is a
drive-strength substitution on an identical instance name — 80
`sg13g2_buf_2` → `sg13g2_buf_1`, 53 `sg13g2_inv_2` → `_1`, 38
`sg13g2_nor3_2` → `_1`, and 35 more of the same shape
**[fact, `diff` of the two `soc_top.netlist.v`, 2026-09-16]**. Cell
count, instance names and structure are unchanged, which is why the
depth profile is identical to the digit. A thousandfold tightening of
the delay target moved **sizing** and did not restructure anything: abc
had no shorter arrangement of this logic to find, which is the result,
but it is a weaker statement than "abc tried to restructure and could
not".

### 5.1 The deepest endpoint class, which is the whole argument

| | deepest endpoint class | its depth |
|---|---|---:|
| committed fabric | `s_rdata_clint[*]` | **81** |
| `REQ_REG = 0` | `u_ibex...prefetch_buffer_i.stored_addr_q[*]` | 79 |
| `REQ_REG = 1` | `s_addr[*]`, `s_be[*]`, `s_wdata[*]` | **69** |

and the class named in `docs/73` section 7.3 and `docs/83`, tracked
across all three:

| | `s_rdata_clint[*]` | `s_rdata_apb[*]` | `s_rdata_npu[*]` |
|---|---:|---:|---:|
| committed fabric | **81** | 17 | 12 |
| `REQ_REG = 0` | 76 | 16 | 9 |
| `REQ_REG = 1` | **16** | 16 | 11 |

**[fact, the same three netlists, endpoints grouped by the net their
flip-flop drives.]**

**The CLINT's response registers go from 81 levels to 16.** That is the
one-cycle bus read cut exactly where `docs/72` section 15 item 5 said it
was: the register-file read, the SECDED correction, the ALU, the fabric
decode, the slave's own address decode and its read multiplexer no
longer share one period.

And what replaces them at the top is the fabric's own request register,
at 69 — `s_addr`, `s_be` and `s_wdata` are `soc_top.v`'s names for
`soc_bus`'s registered outputs. **That is the other half of the same
path**, now ending in a flip-flop instead of continuing into a slave: the
core's register-file read, its SECDED correction, its ALU and this
fabric's arbitration. The change did not shorten that half; it stopped it
being concatenated with the half after it.

The histogram says the same thing in a different shape: the `70-79`
bucket, 1,783 endpoints in the committed netlist and 1,406 at
`REQ_REG = 0`, is **empty** at `REQ_REG = 1`, and the `10-19` bucket
grows from 1,742 to 2,338 **[fact, `logic_depth.py --hist`]**.

### 5.2 A caution about the tool, which cost an hour

The first three synthesis runs made for this document were mapped by
**yosys 0.33**, because `tools.mk`'s pinned checkout
(`$HOME/Downloads/oss-cad-suite-linux-x64-20260804`) is absent in this
environment and its documented fallback takes `yosys` from `PATH`. One of
those three is still on disk — `hw/soc/out/s87-rr0b-syn`, whose `syn.log`
opens `Yosys 0.33 (git sha1 2584903a060)` and whose `soc_top_syn.ys`
carries no `REQ_REG` chparam, so it is the `REQ_REG = 0` arm. It has a
different depth profile for the *same* RTL: **max 79, p99 79, p90 74,
median 28, mean 38.0, 2,824 endpoints (44.25 %) deeper than 40**
**[fact, `logic_depth.py` on `hw/soc/out/s87-rr0b-syn/soc_top.netlist.v`,
2026-09-16]**. This document first published that line as *"max 79,
median 28, mean 38.4, 2,892 (45.31 %)"* with no file named
**[superseded 2026-09-16: the mean and both counts do not reproduce, and
a figure that cannot name its run is not a figure]**. Every number in section 5 is from runs
made with the 0.67+94 build the repository's other results were produced
with, and the committed fabric's column reproducing the published profile
exactly is the control that says so. `tools.mk`'s own header already
makes this point — *"a report that cannot name the tool that produced it
is evidence of nothing"* — and this is one more instance of it.

---

## 6. What it costs: cycles

The whole system-on-chip, same image, same testbench, both settings:

| | `SOC_REQ_REG=0` | `SOC_REQ_REG=1` | delta |
|---|---:|---:|---:|
| run length | **416,673** cycles | **520,398** cycles | **+103,725, +24.89 %** |
| cycles in the image | 220,279 | 268,066 | +47,787, +21.69 % |
| boot hand-over at cycle | 196,394 | 252,332 | +55,938 |
| console characters decoded | 1,150 | 1,150 | 0 |
| QSPI frames on CS0 | 6 | 6 | 0 |
| software self-check | `RESULT PASS`, fail mask 0 | `RESULT PASS`, fail mask 0 | — |
| verdict | `[TB] PASS` | `[TB] PASS` | — |

**[fact, `hw/soc/out/sim-rr0/sim.log` and `sim-rr1/sim.log`, both re-run
2026-09-16 and identical to the first run line for line but for the
run directory printed in the banner.]** The
baseline reproduces today's tree exactly: 416,673 cycles is the figure
`docs/77` section 18.4 measured.

**A quarter of the cycle count is far more than the phrase "a cycle on
every load" prepares a reader for, and the reason is that it is not only
loads.** Every transaction on this fabric pays the cycle, and instruction
fetch is most of them. Ibex's prefetch buffer hides some of it — two
outstanding fetches pipeline across the extra stage — but the data port
does not: a load stalls the pipeline until its response returns, so its
cycle is paid in full, and so is the second fetch after every branch.
`docs/72` section 15 item 5 wrote *"it costs a cycle on every load"*; the
measurement says the cost is one cycle on every **bus transaction**, and
that the workload has about a hundred thousand of them
**[estimate, from the delta and the one-cycle-per-transaction model]**.

### 6.1 And what it costs the netlist

| | `REQ_REG = 0` | `REQ_REG = 1` | delta |
|---|---:|---:|---:|
| cells | 46,453 | 46,577 | +124 |
| flip-flops | 5,998 | 6,065 | **+67** |
| chip area | 702,750.8754 um2 | 710,369.8434 um2 | **+7,618.9680, +1.08 %** |
| kGE | 96.830 | 97.879 | +1.049 |

**[fact, `hw/soc/out/s87-rr0-syn` and `s87-rr1-syn`, each run's
`area.rpt` and run summary.]** The register is 74 bits as written — one
valid, three target, one owner, 32 address, one write enable, four byte
enables, 32 write data — and **68 of them survive mapping**: counting
flip-flops in `hw/soc/out/s87-rr1-syn/soc_top.netlist.v` by the net each
`Q` drives gives `u_bus.g_req_reg.r_val` 1, `r_tgt` 3, `r_own` 1, and the
payload flops under the top-level names they drive, `s_addr` 26 — six
address bits fold away — `s_we` 1, `s_be` 4, `s_wdata` 32
**[fact, that netlist, 2026-09-16]**. The design-wide delta is **+67**,
so one flip-flop elsewhere went with them. The document first read that
delta back as the register's own size **[superseded 2026-09-16]**.
**124 more cells for 68 more flip-flops** is the whole combinational
cost: the arbitration is unchanged, and what the register replaced was a
multiplexer tree that is still there.

---

## 7. The execution suites

| suite | `REQ_REG = 0` | `REQ_REG = 1` |
|---|---|---|
| `hw/soc/tb/cocotb` `soc_bus` | **17 of 17 PASS** | **17 of 17 PASS** |
| Verilator default-flag lint | clean | clean |
| `pytest sw/tests -k "bus or soc_bus or spdx or lint"` | 6 passed, 524 deselected | — |
| `pytest sw/tests -k "guard or memmap or synthesis"` | 267 passed, 263 deselected | — |

**[fact, re-run 2026-09-16.]** The two selection rows first read *"6
passed, 522 deselected"* and *"266 passed"* **[superseded 2026-09-16:
they were taken before the last two tests in the tree existed, and they
do not reproduce]**. The seventeenth cocotb test is
`test_a_refused_slave_blocks_the_other_master_at_both_settings`, section
2.4a's claim asserted where the suite runs it. The cocotb suite runs at both settings through
the new `REQ_REG` knob in `Makefile.soc_bus`, which exports
`SOC_BUS_REQ_REG` for `test_soc_bus.py` to read, exactly as
`Makefile.soc_npu` does for `WAKE_GNT`. **It did not pass at
`REQ_REG = 1` on the first attempt, and the first attempt is the useful
result.**

> **13 OF 16 FAILED, AND TWELVE OF THEM WERE ONE LINE IN ONE MONITOR.**
> (The suite had sixteen tests then; the seventeenth is section 2.4a's,
> added 2026-09-16.)
> `BusMonitor` checks S2 — the broadcast payload is the granted master's
> — **in the grant cycle**, which is precisely the cycle the parameter
> moves. Transporting that check rather than dropping it (remember the
> payload at the grant; compare it against the broadcast in every cycle
> the slave's own req is high) recovered twelve of the thirteen, and
> makes the suite check the broadcast in **more** cycles at
> `REQ_REG = 1` than at 0, because a held request is checked in every
> cycle it is held. It is the same statement as the proved F3d.
>
> Writing it exposed a second, smaller error of the same kind in the
> transported monitor itself: it captured the grant and then checked the
> broadcast in that same cycle, which reads the request the slave has
> not been given yet. The check has to come before the capture.
>
> **The thirteenth is not a test scope problem and was not treated as
> one.** `test_gnt_follows_the_slave` asserts that a master is *not*
> granted while its target slave withholds `gnt` — a property `REQ_REG`
> removes on purpose, because taking the slave off the master's critical
> path is the entire change. That test now has an explicit branch: at
> `REQ_REG = 1` it asserts the replacement contract instead — exactly
> one request is accepted, no second one while the slave waits, and the
> captured request is presented unchanged for as long as the slave
> withholds. That is F3e executed.

---

## 8. What is NOT here, and what it costs the conclusion

* **No place and route, and therefore no slack.** Logic depth is a
  netlist property and is what this change was aimed at, but what closes
  a design is slack on a placed and routed database at the slow corner.
  `docs/83` measured that wire is 3.6 % of a violating path, which is the
  reason to believe the depth is the binding term — it is not a
  substitute for measuring it. **This is the missing evidence, and it is
  one four-hour run.**
* **No fault-injection campaign at `REQ_REG = 1`.** The register is 68
  new flip-flops in the path every access takes, and `docs/74` and
  `docs/82`'s campaigns have not seen it. The formal set proves the
  fabric's protocol; it says nothing about what an upset in `r_addr`
  does, and the honest answer is that it corrupts one transaction the
  same way an upset in the combinational broadcast would, with a longer
  window.
* **The 24.89 % is one workload.** It is the corpus's own whole-SoC
  image, which is the right workload for comparison against every other
  cycle figure here, and it is not a benchmark suite.
* ~~**Head-of-line blocking is stated and not measured**, because no
  slave in this SoC withholds `gnt` and the case is unreachable on this
  tree.~~ **[superseded 2026-09-16.]** It is measured, in section 2.4a,
  and there is nothing to charge the parameter for: two slaves here do
  withhold `gnt`, and the instruction port's grant count while the data
  port's slave refuses is the same at both settings. What `REQ_REG = 1`
  pins in the suite is the one-deep register's own contract, not the
  blocking: `test_gnt_follows_the_slave` drives **one master at a time**
  and asserts that exactly one request is accepted, that no second is
  accepted while the slave waits, and that the captured request is
  presented unchanged — it cannot observe head-of-line blocking, which by
  definition needs a second master. The two-master case is
  `test_a_refused_slave_blocks_the_other_master_at_both_settings`, added
  2026-09-16, which asserts the instruction port gets **no** grant while
  the data port's slave refuses **at both settings**. What is still not
  measured is the effect **on the real slaves in a whole-SoC run**:
  section 2.4a's bench drives `soc_bus` alone with a model of a refusing
  slave, and the only whole-SoC number either setting has is the cycle
  count of section 6, which does not decompose into who was waiting for
  whom.
* **The two-cycle target switch of section 2.4 is derived, not
  measured** **[estimate]**. It is part of the 24.89 % and is not
  separable from it by these runs.
* **ONE TEST IS RED AND IT IS THIS DOCUMENT'S DOING.** The three new
  `.sby` tasks take `hw/soc/formal` from 83 tasks across 20 jobs to
  **86 across 20**, and
  `sw/tests/test_roadmap_is_current.py::test_the_newest_formal_count_in_the_documents_matches_the_tree`
  requires the newest count stated in `docs/00-index.md` and in
  `ROADMAP.md` to be the tree's. Both still say 83 **[fact, `pytest
  sw/tests -q` on the finished tree, 2026-09-16: 529 passed, 1 failed,
  486.52 s; the message is "docs/00-index.md's NEWEST formal count says
  83 tasks; the tree has 86 across 20 jobs"]**. The figure was deliberately not edited
  here, because the count is a roadmap statement and this document's
  author was not the one to make it; the fix is one number in each file
  — `docs/00-index.md` line 525 and `ROADMAP.md` line 293, both reading
  "83 tasks across 20 jobs" — and the guard is doing exactly what its
  own docstring says it was written for. **It is still red and still
  needs the owner's hand**; nothing in the corrections of 2026-09-16
  touched it, because they added no formal task.

---

## 9. Recommendation

**Keep `REQ_REG = 0`, and run one layout before revisiting it.**

The reason is the ratio, and it is not close on this evidence. The
change buys a depth profile that is better by every measure — maximum 81
to 69, median 39 to 20, a third fewer endpoints past 40 levels, and the
design's deepest endpoint class cut by a factor of five. It costs **a
quarter of the cycle count**. `docs/83` section 4 already narrowed what
that depth is worth: the fabric captures 54 of 3,529 violating endpoints
and the CLINT 138, against 1,224 in the register file and 864 elsewhere
in Ibex. **Cutting the chain the CLINT sits at the end of does not by
itself close a design whose worst endpoint is a register-file SECDED
check bit**, and until a layout says how much slack the shorter chain
actually returns, 24.89 % of the cycle count is being spent against a
number nobody has.

What has changed is that the trade is now a trade. `docs/72` section 15
item 5 could only say the cycle was owed; the cost is measured, the depth
is measured, the default is proved untouched, and the property set holds
at both settings. One item of section 8 closed on 2026-09-16 and did not
move this recommendation: head-of-line blocking is measured in section
2.4a and costs nothing, because the round-robin arbiter was already
charging it. **The two that would move it are still open — the layout
and the fault-injection campaign — and the layout is the one to run.** The next move is a layout of `s87-rr1-syn`, measured to
sign-off against `docs/83`'s own baseline, with the same instrument
(`hw/soc/pnr/path_composition.py`) on the same report. If the shorter
chain returns slack in proportion, the question becomes whether a
quarter of the cycle count buys a frequency this mission needs; if it
does not, this document is the record of why the structure was not the
answer either, and the register file is where the remaining work is.

---

## 10. Files

| file | change |
|---|---|
| `hw/soc/rtl/soc_bus.v` | `REQ_REG`, the request register, the `xfer` boundary, the `req_busy` term in `clk_en_o`, and the header section that states the contract |
| `hw/soc/rtl/soc_top.v` | the parameter, defaulted 0, forwarded to `u_bus` |
| `hw/soc/formal/soc_bus_props.v` | the grant/transfer split, I2b, I6, F3e, F3d's ghost capture, F10's coverage of the request register, R1 to R4 |
| `hw/soc/formal/soc_bus.sby` | `bmc_rr`, `prove_rr`, `cover_rr` |
| `hw/soc/flow/syn_soc_top.sh` | `SOC_REQ_REG` |
| `hw/soc/flow/sim_soc.sh` | `SOC_REQ_REG` |
| `hw/soc/tb/cocotb/Makefile.soc_bus` | `REQ_REG`, exported as `SOC_BUS_REQ_REG` |
| `hw/soc/tb/cocotb/test_soc_bus.py` | the transported S2 monitor, the branched `test_gnt_follows_the_slave`, and the two-master `test_a_refused_slave_blocks_the_other_master_at_both_settings` |
| `hw/soc/tb/tb_soc_bus_hol.v` | the two-master bench section 2.4a's table is measured on |
| `sw/tests/test_soc_synthesis_guards.py` | the default guard |
| `hw/soc/pnr/logic_depth.py` | the instrument section 5 is measured with |

Run trees: `hw/soc/out/s87-gold-syn`, `s87-rr0-syn`, `s87-rr1-syn`,
`s87-rr0b-syn` (the yosys 0.33 run section 5.2 is about),
`s88-rr0-syn` and `s88-rr1-syn` (the 2026-09-16 re-synthesis, byte-identical
to the `s87` pair), `sim-rr0`, `sim-rr1`, and
`hw/soc/formal/soc_bus_{bmc,prove,cover}` and their `_rr` counterparts.
