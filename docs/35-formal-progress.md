# 35 — Formal programme progress, 2026-08-31

What this document is: a record of one pass over the formal programme of
`docs/09-formal-verification-plan.md`, made while the RTL is frozen for
the 2026-09-21 shuttle. No file under `hw/rtl/` was touched, and nothing
here required an RTL change — proving properties of existing code changes
nothing about the code, which is why this was the workstream available.

Conventions as in documents 01-09: **[fact]** is verifiable from the
repository or from a measurement recorded here; **[estimate]** is
judgment, with the derivation stated.

Everything below was checked against the working tree rather than against
the plan's own status column, because that column had drifted in both
directions: one row (#4b) understated what the repository contains, and
two (#1 and #5) overstated it.

---

## 1. The true status of the ten targets

The plan's status column has been updated in place; this table is the
audit that produced it, so that the change is reviewable rather than
merely present.

Scope of the edit to `docs/09`, checked mechanically by diffing the table
cell by cell: the only cells that changed are the eleven **Status** cells
and the column header's date. Exactly one line outside the table changed —
the sentence above it reading "the Status column is measured against the
working tree of 2026-08-25", whose date moved for the same reason the
header's did. Leaving the two dates disagreeing would have made the
column's own definition wrong, which seemed worse than touching one date
of prose; it is flagged here rather than left to be found.

| # | What the column claimed on 2026-08-25 | What the repository actually contains | Verdict |
|---|---|---|---|
| 1 | closed; 4 tasks; "4 of 4 covers reached" | 4 tasks, but **9** cover statements — the count was left over from before the pointer-TMR and entry-parity work. And the property set had a hole: every property was written over the design's own `wr_ok`/`rd_ok`/`wr_drop` wires, so a silently refused write satisfied all of them | **claim was optimistic**; now closed on stronger evidence, 6 tasks |
| 2 | closed, cross-check by simulation not by eqy | Exactly as described. `git ls-files` still returns no `.eqy` file | **accurate** |
| 3 | blocked on RTL, pilot is single-clock | `hw/rtl/pilot_top.v` has one clock port. Two-flop pin synchronizers exist and are correctly not claimed | **accurate** |
| 4a | closed, 8 tasks | The voter proof is as described. The criterion's last clause, "the masking theorem ... is reported per protected block", had **no instance** — the column did not say so | **accurate but incomplete**; the instance now exists |
| 4b | "blocked on RTL — nothing to prove" | **Wrong against the repository.** A resynchronization path exists and always did, in `hw/rtl/aer_fifo.v` | **claim was wrong**; now closed for that domain |
| 5 | partial; "`formal/scrub.mk` is not yet included from `formal/Makefile`, so its 9 tasks are not in `make -C formal everything`" | It **is** included: `formal/Makefile` carries the `include`, `scrub_all` in `everything` and `scrub_clean` in `clean-all`. The fragment's own header repeated the same stale claim | **claim was stale**; the row stays partial for the reason that actually holds (three named FSMs have no RTL) |
| 6 | closed for the register bank; "no property in this repository binds the register bank to the voter" | Accurate as written | **accurate**; the missing clause is now closed |
| 7 | blocked on RTL, no arbiter | The only occurrences of "arbiter" in `hw/rtl` are comments in `scrub.v` describing one it would be a master on | **accurate** |
| 8 | blocked on RTL, no QSPI | The only occurrence of "QSPI" in `hw/rtl` is a comment in `npu_regbank.v` | **accurate** |
| 9 | not started, no codec RTL | Nothing in `hw/rtl` mentions SpaceWire or ECSS | **accurate** |
| 10 | not started, no core | Nothing in `hw/rtl` mentions Ibex, PicoRV32, VexRiscv or RISC-V | **accurate** |

Summary: of eleven rows, **seven were accurate as written** (2, 3, 6, 7,
8, 9, 10), one was accurate but silent about a clause of its own criterion
that nothing met (4a), one overstated the strength of its evidence (1),
one was stale (5), and one was wrong (4b). The rows that moved to
**closed** are the two that could move without RTL, and every row that did
not move is blocked on RTL that does not exist.

---

## 2. What was closed

### 2.1 Target #4b — replica re-convergence, for the queue pointer domain

The row said the target was blocked on RTL that does not exist. It looked
at `hw/rtl/tmr_voter.v` (which deliberately has no resync path — restoring
a replica belongs to the protected block) and at `hw/rtl/pilot_top.v`
(whose configuration banks are restored by a host rewrite). It did not
look at `hw/rtl/aer_fifo.v`, because the queue carries its own inline
majority rather than instantiating the voter. That is where the resync
path is [fact]:

> Next pointer state, computed once from the VOTED value and loaded into
> all three replicas. Loading unconditionally rather than under an
> increment enable is what makes the domain self-correcting: a replica
> corrupted at any time is rewritten from the vote on the next edge.

Closed by two new tasks in `formal/aer_fifo.sby`, `resync` and
`resync_cover`, driven by a new property set `AER_PTR_RESYNC` in
`formal/aer_fifo_props.v`. The set replaces the reset-rooted one rather
than joining it, for the same reason `lif_ctrl.sby`'s `bmc_safe` and
`scrub.sby`'s `bmc_any` carry their own: the starting state is different,
and the invariants P5 and P10 stand on are false at step 0 here by
construction.

- The trace starts **out of reset**, on an arbitrary state in which one
  replica of a pointer already differs from the other two, with the six
  injection vectors held at **zero** — the fault has happened and has
  stopped, which is the precondition the target's clause names. The only
  restriction is that a majority exists, which is all a bitwise majority
  over three claims.
- **P15**: one edge later, all three replicas of each pointer hold the
  same value. **N = 1.**
- **P16**: and it is the right value — the vote of the diverged cycle,
  advanced by the operation that cycle accepted. A domain that
  re-converged on the corrupted replica would satisfy P15 and destroy the
  queue, so P15 alone is not the theorem.
- **P17**: the diverged cycle itself is already masked and already
  flagged, in both directions.
- The initial state is fully symbolic, so BMC at depth 2 is already
  exhaustive over the class; the task runs to 6 to show the domain stays
  converged and to reach the covers. 6 of 6 covers reached.

Still open, and stated in the row: the configuration TMR domain has no
resync path, so #4b is closed for the queue pointers and open for the
configuration word. That half needs RTL that does not exist and no
property was invented to paper over it.

### 2.2 Target #6's fourth clause, and target #4a's "per protected block"

Target #6's fourth clause is "TMR'd CSRs vote correctly (reuse #4)". The
status column was explicit that nothing discharged it: *"`hw/rtl/pilot_top.v`
votes 55 configuration bits through the proven voter, but no property in
this repository binds the register bank to the voter."* Target #4a's
acceptance criterion has a matching gap: the masking theorem is to be
"reported per protected block", and the pilot's one protected block had
no report.

New: `formal/tmr_voter_cfg_props.v`, `formal/tmr_voter_cfg.sby`,
`formal/tmr_voter_cfg.mk` — 7 sby tasks plus a parameter guard. The
harness instantiates the same two RTL modules `hw/rtl/pilot_top.v`
composes — three `pilot_cfg_bank` replicas with the pilot's three
polarity masks and MIX on replica C, under one `tmr_voter` — and drives
them against a reference model of the configuration word written from the
register map, not read out of any bank.

Why this is the clause worth spending the effort on rather than an easy
row: **the failure it catches is masked by the very mechanism it is
about.** If replica C's storage transform stopped round-tripping, C would
present a value the other two do not; the voter would mask it; `cfg_v`
would still be right; every functional output of the chip would be
correct. What has silently happened is that triple redundancy has become a
duplex with a permanently wrong third rail, and the *next* upset in A or B
is no longer masked. The fault-tolerance claim is gone and nothing
functional has moved.

Stated with the counterweight it needs, because the case should not be
overstated: a *permanently* wrong replica is not invisible to the existing
suite. It raises `cfg_mismatch` on every cycle, and
`hw/tb/test_pilot_top.py` asserts `CNT_TMR == 0` in the fault-free case,
so mutants C1 and C2 of section 4.3 would have been caught in simulation —
as a fault counter reading rather than as a failure, but caught. What
simulation cannot reach is the value-dependent case: a transform wrong for
one configuration word out of 2^55, which is mutant C5, and which every
assertion-carrying task here fails on. The same gap covers the MIX bank's
read-modify-write on a partial write, a path the polarity banks do not
have and which no proof in the repository reached.

The same POL/MIX construction on `hw/rtl/aer_fifo.v`'s pointer replicas
*is* already covered, as a side effect of P7a; `pilot_cfg_bank` is a
different module at a different width with a different rotation modulus
and a per-bit write port, and none of that carries over.

Proven: G1 round-trip per replica, G2 replica agreement, G3 masking under
a fault free in every bit and every cycle in any one replica, G4 exact
mismatch reporting, G5 the fault-free case on its own.

Not claimed, and said so in the fragment header so that "it PASSes" cannot
be read as more: the register decode that drives the write port (target #6
proper), the `CFG_RST_VAL` assembly, replica resync (#4b — this domain has
none), and the **anti-merge argument**. POL and MIX exist so that yosys
`opt_merge` cannot collapse the three banks into one; that is a property
of the mapped netlist, not of RTL semantics, and a mutant that gives
replica C `MIX = 0` keeps every property in this job true while destroying
the defence. `sw/tests/test_synthesis_guards.py` counts flip-flops in both
flows and is what catches that one. The two kinds of evidence do not
substitute for each other and neither was dropped.

**What the harness copies, stated plainly.** `hw/rtl/pilot_top.v` has no
`ifdef FORMAL` hook and the pilot is frozen, so the composition is rebuilt
from the same RTL modules rather than bound into the instance. Three
things are therefore copied and not proven: the width, the three POL
masks, and which replica carries MIX. `make -C formal -f tmr_voter_cfg.mk
tmr_cfg_params` greps the RTL for those exact literals and fails if any
has moved; it runs first in `tmr_cfg_all`, so the copy cannot drift
silently. The reset image is deliberately **not** copied — `CFG_RST_VAL`
is assembled inside `pilot_top` from generated constants, and reproducing
that assembly would be copying the thing a proof should not assume — so
`RST_VAL` is a harness parameter and the job runs at three of them.

---

## 3. What was strengthened

### 3.1 The AER FIFO acceptance contract (target #1)

The failure mode docs/07 caught in the register bank's lock property —
*"a property phrased in terms of the design's locked set cannot detect a
wrong locked set"* — was still present in the event queue, which is the
block carrying the "no data loss/duplication" clause of target #1.

Every property in `formal/aer_fifo_props.v` was written over `wr_ok`,
`rd_ok` and `wr_drop`. Those are internal wires. A design that quietly
declined an offered write, did not advance the queue and did not count a
drop keeps all of them true, because the reference model `f_writes` counts
the design's own acceptance signal.

Measured rather than argued [fact, 2026-08-31]: a mutant whose `wr_ok`
additionally excludes a write coincident with an accepted read — one lost
event per collision, no drop counted, no flag raised, and every cover
still reachable — **PASSES `prove`, `prove_d4`, `bmc` and `cover`** on the
property set as it stood.

Added **P14**, the module header's own contract restated over the ports
and nothing else:

- **P14a** (ports only): `level` moves by exactly
  `(wr_en && !full) - (rd_en && !empty)` each cycle. This is the whole
  theorem, and **P14a alone kills the mutant** — verified by disabling
  P14b/c and re-running.
- **P14b**: the design's acceptance wires equal the specification's
  conditions, and every offered write has exactly one outcome
  (`wr_ok ^ wr_drop`). Stated at the cut as well so a counterexample is
  readable and so P4's counting property is about offered writes rather
  than about whatever the design chose to call a drop.
- **P14c** (ports only): an offered read on a non-empty queue is always
  answered — delivered on the next cycle, or discarded and announced on
  this one. There is no third outcome.

### 3.2 Two stale completion claims in files that assert them

`formal/scrub.mk`'s header stated it was "NOT YET WIRED INTO
`formal/Makefile`" and that its nine tasks were therefore outside
`make -C formal everything`. It has been wired for some time. Corrected in
the fragment and in the docs/09 row, both by reading `formal/Makefile`
rather than the claim.

`formal/ecc.mk` and `formal/tmr_voter_props.v` both stated that the
re-convergence clause of target #4 is "proven NOWHERE" and blocked on RTL
that does not exist. Corrected to point at `hw/rtl/aer_fifo.v` and at the
new `resync` tasks, and to say precisely which domain remains open.

### 3.3 A toolchain regression, found and fixed

The brief asked for a check that a standalone `make -f <block>.mk`
resolves to the pinned toolchain. It does — and it then runs in the wrong
directory, in **all five** fragments [fact]:

```
$ make -C formal -f ecc.mk secded_cover
cd /home/hasanmelih/Documents/neuromorphic-space-soc && .../sby -f secded.sby cover
FileNotFoundError: [Errno 2] No such file or directory: 'secded.sby'
```

Cause: each fragment computed its own directory as
`$(abspath $(dir $(lastword $(MAKEFILE_LIST))))` *after* including
`../tools.mk`. An `include` permanently appends the included file to
`MAKEFILE_LIST`, so `lastword` was `tools.mk` and the directory was the
repository root. The fragments were correct when included from
`formal/Makefile`, because there `SBY` is already set and the include is
skipped — so the aggregate gate never saw it and the documented standalone
command was broken. The regression arrived with the toolchain pin.

Fixed in all five fragments (and in the new one) by capturing the
directory before the include. Verified: all six now expand to
`cd .../formal && sby -f <block>.sby <task>`.

---

## 4. Mutation evidence

A property that cannot be shown to fail proves nothing. Every property
added or restated above was checked by reintroducing the defect it exists
to catch, in a scratch copy of `hw/rtl/` under the session scratchpad, and
running the affected tasks. All results [fact, 2026-08-31], pinned
toolchain (`OSS_CAD_SUITE_YOSYS_PIN` 0.67+146).

### 4.1 The acceptance hole (section 3.1)

| Mutant | `prove` | `prove_d4` | `bmc` | `cover` | with P14 |
|---|---|---|---|---|---|
| **A** — `wr_ok` excludes a write coincident with an accepted read: one event silently lost per collision, no drop counted | PASS | PASS | PASS | PASS, 9 of 9 covers reached | **FAIL** |

All four survivals are complete runs, not extrapolations: the `cover` run
on the mutant reached every one of the nine cover statements, including
the deep `empty && f_seen_full` at step 130, so the mutant is not caught
by the vacuity rule either.

The "with P14" column is `prove_d4` and `prove`, both failing at P14a
(ports only) and P14b. With P14b and P14c disabled, **P14a alone still
fails**, which is what makes the port-level statement the load-bearing one
rather than the internal restatement.

### 4.2 The resync path (section 2.1)

| Mutant | `prove` | `prove_d4` | `bmc` | `resync` | `resync_cover` |
|---|---|---|---|---|---|
| **B** — each replica advances from its OWN value instead of from the vote (an increment enable per replica, exactly the shape the target's method column names and the RTL comment defends) | PASS | PASS | PASS | **FAIL** | **FAIL** |

Mutant B leaves every existing property true: from reset all three
replicas start equal and advance on the same voted decision, so P7a and
P7b hold, and the domain is simply no longer self-correcting. Nothing in
the repository could see that before `resync`. `cover` was not run to
completion on this mutant — it does not change reachability and the
run was stopped to free the machine — so the row above reports the three
assertion-carrying tasks, which are the ones that could have caught it.

### 4.3 The configuration TMR domain (section 2.2)

Five mutants, each reintroducing a defect the job exists to catch:

| Mutant | `prove` | `prove_w8` | `bmc` | `prove_abc` | `cover` |
|---|---|---|---|---|---|
| **C1** — `cfg_dec` layer-2 rotation off by one (`(i+1) % LO` -> `i % LO`) | FAIL | FAIL | FAIL | FAIL | pass |
| **C2** — MIX bank applies POL inside the encode (`cfg_enc(nxt ^ POL)` instead of `cfg_enc(nxt) ^ POL`) | FAIL | FAIL | FAIL | FAIL | pass |
| **C3** — `tmr_voter` loses the `(in_b & in_c)` majority term | FAIL | FAIL | FAIL | FAIL | pass |
| **C4** — polarity banks lose their per-bit write enable, so a partial write overwrites bits it must not touch | FAIL | FAIL | FAIL | FAIL | pass |
| **C5** — `cfg_dec` wrong for exactly one stored word (an extra `^ (&c)`) | FAIL | FAIL | FAIL | FAIL | pass |

That `cover` passes on all five is the expected result and is worth
stating: the cover task checks that the proven behaviours are reachable,
not that they are right. A gate reporting otherwise would be measuring
something else.

C5 is the one that argues for a proof rather than a test here. It is
reachable at a single 55-bit configuration value, so no directed stimulus
finds it. Note also, in the other direction and to keep the claim honest:
C1 and C2 raise `cfg_mismatch` permanently, and
`hw/tb/test_pilot_top.py` asserts `CNT_TMR == 0` in the fault-free case,
so those two would not have escaped simulation. C5 would have.

---

## 5. Cost of the gate

Task count and property statements:

| | before | after |
|---|---|---|
| sby tasks in `make -C formal everything` | 45 | **54** |
| non-sby guard targets in the gate | 0 | 1 (`tmr_cfg_params`) |
| `.sby` files | 7 | 8 |
| property files | 8 | 9 |
| `assert`/`assume`/`cover` statements | 587 | **643** |
| of which `cover` | 112 | **126** |

### 5.1 The whole gate

`make -C formal everything` was run to completion on the pinned toolchain
after every change in this document [fact, 2026-08-31]:

```
54 of 54 SymbiYosys tasks DONE (PASS), 0 FAIL, 0 ERROR
0 unreached cover statements anywhere in the suite
wall time 7011 s = 1 h 56 min 51 s
sum of per-task solver time 6984 s
```

Caveat on that number, stated because it is the headline one: the run
overlapped for its first ~100 minutes with the mutation experiments of
section 4, so up to four solver processes shared the machine. It is an
**upper** bound. Scaling by the one task with a recorded idle-machine
figure — `aer_fifo.sby cover`, 41 min 55 s on 2026-08-30 against 58 min
43 s here — puts an uncontended gate at roughly **1 h 20 min to 1 h 30
min** [estimate, from that single 1.4x factor].

Four tasks are 88 % of it, and none of them is new:

| Task | This run |
|---|---|
| `aer_fifo.sby cover` | 58 min 43 s |
| `lif_ctrl.sby bmc` | 24 min 11 s |
| `aer_fifo.sby bmc` | 18 min 21 s |
| `lif_ctrl.sby bmc_live` | 6 min 23 s |
| everything else — the other 50 tasks together | **7 min 25 s** |

### 5.2 What the nine new tasks cost

Measured inside that same gate run [fact]:

| Task | Mode | Elapsed |
|---|---|---|
| `aer_fifo.sby resync` | bmc depth 6 | < 1 s |
| `aer_fifo.sby resync_cover` | cover depth 6 | < 1 s |
| `tmr_voter_cfg.sby prove` | prove depth 4, boolector | < 1 s |
| `tmr_voter_cfg.sby prove_rst1` | prove depth 4 | < 1 s |
| `tmr_voter_cfg.sby prove_rstx` | prove depth 4 | < 1 s |
| `tmr_voter_cfg.sby prove_abc` | prove, abc pdr | 1 s |
| `tmr_voter_cfg.sby prove_w8` | prove depth 4 | < 1 s |
| `tmr_voter_cfg.sby bmc` | bmc depth 20 | 4 s |
| `tmr_voter_cfg.sby cover` | cover depth 8 | < 1 s |
| **all nine** | | **5 s, or 0.07 % of the gate** |

Standalone, including process startup and the parameter guard, the whole
`tmr_cfg_all` block takes 14 s. The task count went up by 20 % and the
runtime did not move.

### 5.3 What P14 cost

P14 adds assertions to the set the three `aer_fifo` assertion-carrying
jobs all carry, so it is the only part of this pass with a real price.
Measured against the pristine `HEAD` property file, run concurrently on
the same machine so the two sides see the same load [fact]:

| Task | without P14 | with P14 | delta |
|---|---|---|---|
| `aer_fifo.sby prove` | 1 min 32 s | 2 min 07 s | +35 s (+38 %) |
| `aer_fifo.sby bmc` | 15 min 22 s | 18 min 21 s | +179 s (+19 %) |
| `aer_fifo.sby cover` | 1 h 00 min 08 s | 58 min 43 s | none — cover mode does not evaluate assertions; the 85 s is run-to-run noise |

So P14 costs about **3.5 minutes**, or 3 % of the gate. That is the price
of the finding in section 3.1, and it is worth paying: the property set it
replaces could not detect an event queue that lost events.

### 5.4 Is this still something a person will actually run

`docs/19` warns to budget hours rather than minutes for this suite. That
guidance is unchanged and still right, and this pass neither improved it
nor meaningfully worsened it. The measured figure is 54 tasks in
1 h 56 min 51 s. Subtracting the two measured additions — 5 s for the nine
new tasks, 214 s for P14 — the same run would have been 6792 s = **1 h 53
min** for the old 45 [derived from the two measurements above, not a
separate run: the pristine gate was started and stopped once the
comparison it was for had been obtained per task instead]. Nine more
tasks, three minutes more, and the three minutes buy the section 3.1
finding.

The honest answer is the same as before: not casually, and not per-commit
on a laptop. `aer_fifo.sby cover` alone is half the suite, and this change
did not create that and does not fix it. The two levers for bringing it
down are the ones already recorded in the header of `formal/aer_fifo.sby`
— dropping fault injection from the cover job (which also drops P9, the
anti-vacuity check on the fault model) or moving it to the `btor btormc`
engine, which returns in under a second and for that reason has not been
adopted without someone first confirming the deep cover is genuinely
reached. Neither has been pulled here.

What *is* cheap is per-block work. Every block except `aer_fifo` and
`lif_ctrl` closes in under two minutes — `npu_regbank` in 97 s, `scrub`,
`secded`, `tmr_voter`, `lif_mem` and the new `tmr_voter_cfg` in seconds —
so `make -C formal -f <block>.mk <block>_all` is a usable inner loop. As
of section 3.3 it once again runs in the right directory, which it had not
done since the toolchain pin landed.

---

## 6. What remains, and why

Ordered by what it would take, not by what it would be worth.

1. **#4b for the configuration domain** — needs RTL. The banks would have
   to be reloaded from the vote, as the queue pointers are. That is a
   change to a frozen pilot and it is not a formal-track decision. Until
   then the domain's masking is proven and its re-convergence does not
   exist to prove.
2. **#3, #7, #8, #9, #10** — need RTL that does not exist: an
   asynchronous FIFO and a second clock domain, an arbiter/interconnect, a
   QSPI streaming path, a SpaceWire codec, a management core. Five of the
   eleven rows, and no property was invented for any of them. The
   temptation on #3 is real and was refused: the pilot does have two-flop
   pin synchronizers, and a property over their registers inside a
   single-clock model would look like the row and prove none of it.
3. **#5's remaining FSMs** — the scheduler, the multi-pass sequencer and
   the link controllers have no RTL. The row stays *partial* however good
   the scrub controller's evidence gets.
4. **#5's fault-injection cross-check** — the acceptance criterion says
   the formal any-state result and the force/release campaign "must
   agree", and nothing in the repository compares them. That needs no RTL
   and is the largest piece of unclaimed ground reachable from here; it
   sits across `hw/tb/` and `formal/`, which is why it was not done in a
   pass that owns only one of them.
5. **#2's eqy cross-check** — still no `.eqy` job anywhere. Documented as
   a strengthening rather than a repair since 2026-08-25, and still not
   scheduled.
6. **The register-bank-to-voter binding at the instance** — section 2.2's
   harness rebuilds `pilot_top`'s composition instead of binding into it,
   because that file has no `ifdef FORMAL` hook and the pilot is frozen.
   The parameter guard keeps the copy honest, but the honest description
   is "proven for the composition the RTL builds, checked to be the
   composition the RTL builds", not "proven in place". Adding the hook is
   a one-line RTL change and is the right thing to do the moment the
   freeze lifts.

### Follow-ups for files this pass does not own

- `docs/19` records the formal suite as **45** tasks in four places: the
  correction at its head, the `Formal` row of its evidence table, the
  release-readiness table, and its "Formal verification" paragraph. It is
  **54** as of this document. Its statement that the property files carry
  **542** `assert`/`assume`/`cover` statements over eight files is now 643
  over nine.
- `docs/11` section 8 is the operating manual for re-running the suite and
  does not yet name `aer_fifo.sby resync` / `resync_cover` or the
  `tmr_voter_cfg` block.
- No `.gitignore` change is needed. The new job's sby working directories
  are named `tmr_voter_cfg_*`, which the existing `formal/tmr_voter*/`
  rule already covers; the name was chosen for that reason as well as for
  being accurate, and the fragment header says so rather than leaving it
  to be discovered.
