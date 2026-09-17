<!--
SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
SPDX-License-Identifier: CC-BY-4.0
-->
# 86 — An external review, worked

An independent third party read the public mirror at `36efe03`,
reproduced every claim it made on a fresh clone, and wrote eleven
findings with a reproduction block, an acceptance block and a scope
guard each. This is what happened to them.

The review's own instruction was followed first: **re-run each
reproduction before acting on it**, and stop on any finding that does
not reproduce rather than inventing a fix. That mattered. Of the
eleven, nine reproduced as written, two reproduced with their
diagnosis wrong, and the reproduction turned up **three defects the
review did not have**.

Convention, as elsewhere: **[fact]** = measured in this environment on
the stated date.

---

## 1. Verdict first

| | |
|---|---|
| **Findings worked** | 11 of 11 |
| **Acceptance blocks met in full** | 9 |
| **Met in part, with the shortfall stated** | 2 (F2, F6) |
| **Front door, this repository** | 17 passed / 3 failed / 3 skipped, exit 1 → **22 / 0 / 1, exit 0** |
| **Front door, the mirror** | 8 / 6 / 9, exit 1 → **16 / 0 / 7, exit 0** |
| **Mirror test suite** | 499 passing / 47 skipped → **536 / 42** |
| **`check_claims` in the mirror** | 1 wrong → **0 wrong** |
| **Found by reproducing, not in the review** | 3 |
| **Found by the proofs, in my own fixes** | 2 |

**The most useful thing the review did was not a finding.** It was the
instruction to re-run the reproduction, because two of its diagnoses
were wrong in the same direction: it attributed all three of F0's
failures to mirror generation, and one of them (F0c) is a defect in
the development repository that the mirror merely inherits. A fix
applied to the mirror would have left it in place.

---

## 2. The three defects the reproduction found and the review did not

**`scripts/ci_local.sh` did not use its own interpreter.** It resolves
one at line 54 and then used a bare `python3` at sixteen call sites, so
on a machine whose system python is not the venv the licence, docs,
paper, mirror and suite gates all failed for the interpreter rather
than for the thing they check. A gate that fails for the wrong reason
is worse than no gate: it trains the reader to ignore it.

**Twenty-two formal directories were undispositioned.** Nineteen are
results `docs/63` sections 22 and 23 already record in full — the
twelve M-extension checks bounded at 7,200 s under bitwuzla, and the
seven register-file scrub tasks. What was missing was the row, not the
work. **A measurement that is documented but not dispositioned is
still an undispositioned non-PASS.** The other three were `soc_npu`'s
proofs reading PASS-STALE: they had been proved before `WAKE_GNT` was
added to `soc_npu.v`, so the verdict was about different bytes. Re-run
against today's RTL, all three pass again **[fact, 2026-09-17]**.

**Two skips were avoidable.** The paper build probed for `pdflatex`
while `paper/Makefile` resolves tectonic first, so it skipped on every
machine that has tectonic and no TeX Live — which is this one. The
probe is now the Makefile's own.

---

## 3. The two defects the proofs found in my own fixes

Both are the reason the review's standing constraint — *re-run the
affected proofs before claiming a fix* — is the most valuable sentence
in it.

**The APB timeout delivered two responses for one request.** After a
timeout fired, a slave that asserted PREADY late sent the machine back
to idle and answered again. A6 and A9 both forbid it and the fabric's
ownership queue would mis-pop on it. `&& !to_fired` closes it, and a
simulation test drives the late PREADY so it stays closed. **Found by
`prove_to`, not by reading.**

**The crash register broke five guards, and every one of them was
right to break.** The flip-flop budget derivation, the unprotected-flop
allow-list and the `HARDEN = 0` baseline all pinned a number that the
33 new flip-flops moved. They now name the 33 as a term rather than
absorbing it, and `docs/68` section 9.1's 92 stays 92, because 92 is
what it measured.

---

## 4. Finding by finding

### F0, F0a, F0b, F0c, F0d — the front door

`scripts/ci_local.sh all` is the command `README.md` tells a reader to
run and `.github/workflows/checks.yml` invokes. It exited 1.

Five causes, not the three the review found. Two were mirror-only and
both were the same shape, *a tool that is correct upstream and cannot
run in the tree it generates*:

* **F0a.** The redaction assertion fired on an already-redacted
  fragment. The assertion was not the defect and deleting it would
  have been — its comment states the guarantee, that a fragment
  REWORDED upstream must fail the build because the alternative is
  that it travels. Each entry now carries an explicit marker and a
  zero-match is accepted **only** when the marker proves a previous
  run redacted it. Three rows, and the third is the one that matters:

  | pattern | marker | outcome |
  |---|---|---|
  | matches once | absent | redact — the upstream case |
  | matches zero | present | already done — the mirror case |
  | matches zero | absent | **FAIL** — the reworded case |

  `sw/tests/test_mirror_redaction_is_idempotent.py` proves all three.
  Writing it turned up that one entry is a fixed point and the other
  two are not: `ci_local.sh`'s redacted form still matches the pattern
  that found the original, because `'(account status, not published)'`
  is itself a `'[^']*'` match. So the property that holds for all three
  is not *the pattern is gone* but *the marker is present and
  regenerating changes nothing*.

* **F0b.** The logs named development commits as bare hashes that
  resolve nowhere in the mirror, so `check_claims` called the last row
  WRONG — in a file whose entire purpose is that a measurement names
  the commit it was taken at. Deleting the row or substituting a mirror
  commit would have been fabricating provenance. The hash is kept and
  prefixed, `upstream:587fdd8`, the convention is in each log's own
  header, and the claim now reports `man` with that reason. A claim may
  name one output meaning *this tree cannot re-derive this, and here is
  why*; it is a value the command PRINTS, so a tree that CAN re-derive
  it still must.

* **F0c** is **not** a mirror artefact, which is where the review's
  diagnosis is wrong. `\mbox` entered `paper/main.tex` on 2026-09-13
  inside a dated correction note, the file is byte-identical in both
  trees and the renderer fails in both. `\mbox` means *do not break
  this across lines*, so it maps to a non-breaking span rather than
  being swallowed, and the same construct is what the thesis's `\dcite`
  expands to.

  **The gate was never missing.** It has been in `ci_local.sh` since it
  was written and it caught the defect the moment it was run. The
  problem is that it was not run: `ci-local-log.tsv`'s last row was
  2026-09-10 and the defect arrived on the 13th. The same property is
  now also in `pytest`, which runs on every change. *A guard in a place
  nobody runs* is `docs/78`'s rule read the other way round.

* **F0d.** The log now names the commit that made the front door green,
  on a clean tree.

### F5 — what the line and proof counts do not cover

`hw/rtl/npu_regbank.v` (936 lines) and `hw/rtl/scrub.v` (332) are
complete, tested and proved, and are built into nothing: not
`pilot_top.v`, which carries its own inline banks; not the TTIHP26b
submission, whose `source_files` names neither; not `soc_top.v`, which
instantiates `soc_scrub`, a different module in a different file.

**1,268 of 6,883 lines (18.4 %) and 14 of 54 proof tasks (25.9 %)**
**[fact]**. Nothing is wrong with the modules or the proofs. What was
missing is anyone saying so, and the review named the right fix: state
the scope, do not shrink the set. `README.md`, `docs/11`'s new `Built
into` column and `docs/09` row 6 each say it now.

Stating it once fixes today. `sw/tests/test_no_orphan_modules.py` makes
the next one fail: every module under `hw/rtl/` must be reachable by
instantiation from `tt_um_melihakbulut_nssoc` or `soc_top`, or carry a
row in `hw/known-unbuilt.txt` with a reason. It fires in both
directions — a new orphan, and a fossil row for a module that IS built.

The ledger is beside the frozen tree and not inside it. The first
version put it in `hw/rtl/` and `test_soc_npu_guards.py` caught it
within the minute, which is the freeze doing its job.

### F6 — the evidence, and where this falls short

Every `runs/` tree is gitignored, for the good reason that a 113 MB GDS
does not belong in git. The consequence was that nothing this corpus
says about layout could be checked from a clone.

The evidence is small. `final/metrics.json` is about 10 kB and
`resolved.json` about 30 kB; fifteen cited runs is **722 kB**, now
under `docs/evidence/`. `sw/tests/evidence.py` is what the tests read
them through: the live run tree wins when present, the record answers
when it is not, and `source` says which — so a test reports *checked
against the recorded artefact* rather than *checked*, which is a weaker
claim and deliberately weaker.

| | before | after |
|---|---|---|
| mirror tests passing | 499 | **536** |
| mirror tests skipped | 47 | **42** |
| `test_flow_evidence` skips | 11 | **5** |

**The acceptance asked for fewer than thirty skips and this is
forty-two.** Twenty-two of the remainder need a whole-SoC netlist or a
populated `hw/soc/gen`; committing those is the thing the finding
itself says not to do. Five need the run tree's own step directories
and logs, five need a DEF, one needs a gitignored clone of the Tiny
Tapeout tools. Seven are the redaction guard, which is inapplicable in
the mirror by construction and says so. Getting under thirty would
mean committing artefacts that should not be committed, so the number
is reported rather than reached.

These files are NOT in `docs/80-artefact-digests.tsv`. That file's own
header says every path in it is gitignored on purpose: its job is to
pin what git cannot see. These are tracked, so git pins them already
and a second copy would be a weaker guarantee. What git cannot tell you
is whether the record still matches the run tree it came from, and
`sw/tests/test_recorded_evidence.py` checks exactly that.

### F1 — the accelerator's flush reset

`blk_rst_n` was `rst_ni && !flush_pulse`, one combinational net driving
`aer_fifo`'s ASYNCHRONOUS `rst_n` and read synchronously by the
one-hold register at the same time. It was the only reset in this SoC
reaching flip-flops without the two-stage deassert `soc_top.v:352-359`
builds for every other one.

`aer_fifo.v` is frozen, so the port cannot gain a synchronous flush and
the fix lives in `soc_npu.v`: `blk_rst_n` is now asynchronous assert
with synchronous deassert and drives nothing but the two queues, and
the synchronous consumers read `blk_flush`.

**Measured, not assumed.** A new simulation test pins all three claims:
assert is immediate, `blk_flush` is the exact complement of
`blk_rst_n` at every edge, and release lands **three edges** after the
pulse clears rather than one **[fact]**. Deleting the synchroniser
makes it fail; it was checked that way.

The lint pragma is four lines wide and sits on the synchroniser alone.
A reset synchroniser IS a register asynchronously reset and
synchronously shifted whose output resets something else
asynchronously; `SYNCASYNCNET` sees that shape and cannot tell it from
the defect the shape removes. Anywhere else in the block it still
fails.

### F2 — the crash record

`soc_top.v:568` read `.crash_dump_o ()` while `:569` wired
`double_fault_seen_o` out to a pin: the SoC exported the FACT of a
fatal fault and dropped everything that would say where it happened.

Only the faulting PC is kept, and that is a choice. `crash_dump_o` is
160 bits and BOOTREG's slot has room for one register at its own next
free offset, `0x010`. It lives in `soc_boot` because that block is
already in the power-on domain — the one place whose registers survive
the reset a double fault causes. First fault and not last, because a
fault the watchdog resets is likely to recur for the same reason.
Neither word is clearable.

**Cost, against the unmodified block, yosys 0.33 with
`sg13g2_stdcell_typ_1p20V_25C` [fact, 2026-09-17]:**

| | before | after | delta |
|---|---|---|---|
| flip-flops | 143 | 176 | **+33** (32 PC + 1 flag) |
| area, um2 | 12,316.2984 | 14,807.1672 | **+2,490.87** |
| of `soc_boot` | | | +20.22 % |
| of the SoC's 933,010 um2 of standard cells | | | **+0.267 %** |

**Where this falls short.** The acceptance asks for a cocotb test that
injects a double fault and reads the PC back after the watchdog reset.
There is no whole-SoC cocotb testbench here — every suite is per block
— so the four new tests drive the capture directly and hold `rst_ni`
low while `rst_por_ni` stays high, which IS the watchdog reset, three
times over. Ibex actually taking the fault is Ibex's behaviour and is
not what this register is. **The whole-SoC injection is not done.**

### F3 — the APB timeout, and what it costs in AMBA clauses

`ST_ACCESS` had exactly one exit. Not a live bug at today's parameters
— eight of nine mapped slaves drive PREADY as the literal 1 — but
`soc_apb_wb.v` has a genuinely non-constant PREADY and is written and
proved, so the first wait-state slave wired in makes it live.

**There is no protocol-clean timeout, and finding that out is most of
the work.** Dropping PSEL and PENABLE is a master-side abort, which APB
does not have and A4 forbids. Holding them means a late PREADY no
longer ends the transfer, which is A5. One of the two has to give, and
A4 is the one kept.

So at `APB_TIMEOUT != 0` the parameter costs exactly three AMBA
clauses — **A5, A9 and A10** — each antecedent-guarded and each stated
where it is deviated from. At `APB_TIMEOUT = 0`, the default, it costs
none of them, and the synthesised netlist is **identical**: 193 cells
and 93 flip-flops before and after **[fact]**. Three new invariants
(A12, A12a, A12b) are the price of keeping the rest inductive.

### F4 — the QSPI budget

The header stated a CEILING and the budget under it was stated
nowhere: no `set_input_delay` on `qspi_io_i` anywhere, so the flow used
LibreLane's blanket `IO_PCT` synthetic delay, which is a fraction of
the clock period and not a model of a flash.

The arithmetic is now in the three places that must agree, with every
input naming its file:

> `DIV >= ceil((tCLQV + 2 x board) / CLOCK_PERIOD) - 1`

`tCLQV = 6.0 ns` is the part's. The 2.0 ns board allowance each way is
**ASSUMED** and named as one in all three places, because there is no
board, no pad ring and no pad model here; the SDC holds it as a
variable so a measurement can replace it.

**Then measured**, which is what a ceiling cannot give. OpenSTA 3.1.0
over the sign-off netlist at the typical corner with the fragment
sourced: the input path closes at **+9.4682 ns** and the SCK output
path at **+16.7764 ns** **[fact, 2026-09-18]**.

**No synchroniser belongs on this path**, and the RTL now says why
rather than leaving it to be reached for. `io_i` is source-synchronous:
the flash launches it off the SCK this block generates from `clk_i`.
Two flops on a read-data lane would delay the data two clocks relative
to the shift sequencer and corrupt every word read.

### F8 — the register-file property

Two of the three acceptance bullets were already met before the review
was written: `docs/63` section 23 records both the bounded route (the
real codec, which does not close, with the reason located in the
parity trees) and the abstracted one (`regfile_scrub_abs.sby`, R1–R4
proved unbounded in 44 seconds). The third was genuinely open and is
now closed: `formal-dispositions.tsv`'s thirteen `reg_ch0` rows stay
exactly as recorded on 2026-09-11 and the file's header names the
replacement, and `docs/63` gains section 24 for the distinction the
corpus did not contain — `regfile_scrub_abs` proves a property of the
BLOCK, `reg_ch0` a property of the CORE, and only the first is what a
file swap needs.

**The review's preferred route, attempted and reported.** It ranked
equivalence third and strongest: prove `ibex_regfile_secded` equivalent
to upstream's `ibex_register_file_ff` on the fault-free input space,
using the `eqy` machinery `formal/eqy/` already has. That was tried.

Two obstacles the review does not mention, and both are results. The
gold side lives in `hw/soc/gen/`, which is gitignored vendored Ibex and
is therefore absent from the mirror and from a fresh clone — so this
job cannot run where most of the suite runs. And the two modules are
**not interface-identical**: the substituted file adds `rf_ecc_err_o`,
so `eqy` refuses to combine them outright. `formal/eqy/regfile_shim.v`
restricts the question to the sixteen ports upstream has, which is
written out rather than hidden in a tool flag.

With that, at `SCRUB = 0` and depth 16 **[fact, 2026-09-18]**:

| | |
|---|---|
| partitions proved equivalent | **12 of 13** |
| unresolved | `rdata_a_o` |
| its verdict | `UNKNOWN` — *reached maximum number of time steps* |

**The one that did not close was not refuted.** It reached the bound
and stopped, at depth 5 and again at depth 16, and an unbounded engine
did not finish either. So the honest statement is that twelve of the
thirteen output partitions of the substituted register file are proved
equivalent to upstream's on the fault-free input space, and the
thirteenth — one of the two read ports, and only one, which is itself
worth a look — is bounded-unresolved. That is more than the corpus had
and less than the review hoped for, and `formal/eqy/regfile_secded.eqy.in`
is committed so the next person starts where this stopped rather than
where it began.

### F7 and section 5 — documentation

`ROADMAP.md` gains the macro-edge keep-out experiment as a named,
costed item, and a table of what a foundry and a test house will ask
for that this repository does not have. The review's second F7 action
needed no change: no summary sentence reads as *the SoC layout is
DRC-clean*, and `paper/main.tex` carries an explicit house rule against
the phrasing.

### F10 — the pytest numeral

`README.md` said the root collects 503; a fresh clone collects 532 and
this machine 543. **The correction is to stop printing the number.**
`test_soc_clkgate_guards.py` parametrises one case per gate-level
netlist under the gitignored `hw/soc/out/`, so running synthesis
changes the count without changing a tracked file. The other four
numerals name a command *and* a value because both are stable; this one
now names the command only. The 2026-09-10 and 2026-09-11 entries stand
as written — they were right on their dates.

---

## 5. What the review got wrong, stated plainly

Two things, and both in the same direction — a diagnosis reaching one
step further than its evidence.

1. **"All three failures are mirror-generation artefacts."** F0c is
   not. It is a development-repository defect that the mirror
   inherits, and a fix applied to the mirror would have left it
   standing upstream.
2. **F8's three options described as untaken.** `docs/63` section 23,
   dated 2026-09-15 and 2026-09-16, records options 1 and 2 both taken
   and measured. The review read sections 17.2 and 23 and reported the
   state before the latter.

Neither is a serious error and both are the kind a reader of a large
corpus makes. They are recorded because this document would be
dishonest without them: the review found eleven real things, and the
two it got wrong were found by the procedure it insisted on.

---

## 6. What none of this changes

No silicon. No beam. No frequency. The part is placed and routed and is
a core-only block with no pad frame, which section 5b of `ROADMAP.md`
now says in one place. Every hardening claim remains a mechanism plus a
simulated fault-injection campaign.

---

*2026-09-18. Nothing was built for this document; it records eleven
findings worked, three defects the reproduction added, two the proofs
found in the fixes, and two places where the acceptance was not
reached.*
