# 17 — Design wave 2: review record and the wave-3 plan

Date: 25 August 2026
Status: review record complete; the wave-3 plan in section 7 is input to
`ROADMAP.md`. This document closes design wave 2 as committed at
`be6ebd9` ("Design wave 2: RTL blocks, formal proofs, clean sg13g2
sign-off, TT submission") and stands to wave 2 as
`docs/07-design-review.md` stands to the research phase and wave 1.

It exists because wave 2 produced a large number of claims and no single
place a reader could check them. The verification totals live in
`docs/11`, the physical results in `docs/12`, the tile arithmetic in
`docs/15`, the formal status in `docs/09`, and the review that produced
the repairs was never written down at all. A funder, a reviewer, or the
developer six months from now needs one document that says what was
delivered, what evidence supports each claim, how the evidence was
produced, and what is still unsupported. That is this document.

Conventions, as in documents 01-15. **[fact]** = measured in this
environment on the stated date, or read out of a file in this
repository at the stated path. **[estimate]** = derived, projected or
judged. **[claim]** = asserted somewhere in the repository but not
independently checkable from the tree; used sparingly and always with
the reason. Where a number was recomputed, the arithmetic is shown. No
area or utilization figure appears without naming its PDK, per the
docs/07 verdict.

Every count in section 2 was produced by running the command in the
table, from the repository root or from `hw/tb`, on 25 August 2026
between 12:29 and 12:56 local. They are not copied from `docs/11`. Where
they agree with `docs/11` that is a reproduction; where they do not,
sections 2.5, 6.4 and 8 say so.

**A caveat this document inherits and must repeat.** `docs/11`'s header
warns that the repository is edited by several workstreams in parallel
and that a count differing from its section 8 is "a change to be
explained, not noise". That warning was live during this record's own
measurement window: `hw/rtl/pilot_top.v` and `hw/tb/test_pilot_top.py`
were both edited by another workstream while these numbers were being
taken; untracked `hw/rtl/scrub.v`, `formal/scrub*` and
`hw/tb/test_fi_campaign.py` appeared; and a second `sby` process running
in the same `formal/` tree destroyed a task directory out from under
this record's formal work, twice within twenty minutes. Section 3.5 turns the
first of those into evidence, section 6.5 turns the last into a finding,
and section 8 states which tree each number belongs to. Every number
below is tagged with the clock time it was taken.

---

## 1. Scope and method

### 1.1 What is reviewed

The whole of `be6ebd9` against its parent `b5346a9`: 93 files, 23,098
insertions **[fact, `git show --stat be6ebd9`]**. Concretely:

- RTL: `hw/rtl/npu_regbank.v`, `lif_core.v`, `secded_enc.v`,
  `secded_dec.v`, `tmr_voter.v`, `pilot_top.v`,
  `tt_um_melihakbulut_nssoc.v`, plus contract changes to `aer_fifo.v`;
- formal: `formal/npu_regbank_props.v`, `lif_ctrl_props.v`,
  `secded_props.v`, `tmr_voter_props.v` and the additions to
  `aer_fifo_props.v`, with their `.sby` jobs and makefile fragments;
- simulation: five new cocotb suites and their drivers, plus
  `sw/tests/test_secded.py`, `test_regmap.py`, `test_flow_evidence.py`
  and `test_tt_submission.py`;
- physical: `hw/openlane/`, and the results recorded in `docs/12`;
- submission: `scripts/gen_tt_submission.py` and the generated `tt/`;
- documents: `docs/12`, `docs/13`, `docs/14`, `docs/15` outright, and
  substantial revisions to `docs/06`, `docs/09` and `docs/11`.

### 1.2 How this record was produced

Reconstruction from artefacts, not from a hand-over summary. In order:
`docs/07` was read for the house format; `git log` and `git show` for
what actually changed; the property files, testbenches and result files
for what is actually verified; and the documents for what is claimed.
Every verification suite was then executed rather than quoted. Where a
document and the tree disagree, the tree wins and the disagreement is
recorded as a finding (section 6.4).

### 1.3 Boundary between proven, tested, measured and estimated

This document uses four words and does not blur them. They are stated
here because the value of the rest of the document depends on the
distinction holding.

| Word | Means | Example in wave 2 |
|---|---|---|
| **proven** | A solver returned UNSAT over the whole reachable input space of the elaborated model, and the property set was shown to be non-vacuous by a passing cover task | `secded` S1..S5 at BMC depth 1 over `$anyconst` data and error vectors — exhaustive because the codec is combinational |
| **tested** | A finite stimulus was run and compared against a reference; the result holds for that stimulus and says nothing about any other | the 24 `lif_core` tests at four geometries |
| **measured** | A tool reported a number about a concrete artefact in this environment | 136,107 um2 placed cell area on `sg13g2`, from the LibreLane run |
| **estimated** | Derived from measured inputs by a model, or judged | the 107.4 % utilization a 2x2 block would need, and every hour figure in section 7 |

Two boundaries are worth stating explicitly because wave 2 crosses them
and the crossings are easy to misread:

1. A `prove` task at default parameters is proven **for those
   parameters**. `npu_regbank prove` is a proof about a 512x512
   instance; `prove_n256` and `prove_cnt2` are separate proofs about
   separate instances. Nothing in this repository proves the register
   bank for all parameterizations.
2. "Verified in lockstep against a golden model" is a claim about the
   *model's* interface, not the RTL's. Section 3.4 is what happens when
   that distinction is not made.

---

## 2. What wave 2 delivered, and what verifies it

### 2.1 The artefacts

Six RTL blocks plus an integration, 3,234 lines of Verilog **[fact,
`wc -l hw/rtl/*.v`]**, against 1,610 lines of formal properties
**[fact, `wc -l formal/*.v`]** and five cocotb suites.

| Block | RTL | Lines | Reference model | cocotb suite | Formal job |
|---|---|---|---|---|---|
| AER event FIFO | `aer_fifo.v` | 130 | in-test scoreboard | `test_aer_fifo.py` | `aer_fifo.sby`, 4 tasks |
| NPU register bank | `npu_regbank.v` | 933 | `sw/golden/regmap_gen.py` (generated) | `test_npu_regbank.py` | `npu_regbank.sby`, 5 tasks |
| LIF datapath | `lif_core.v` | 446 | `sw/golden/lif_core.py` | `test_lif_core_rtl.py` | `lif_ctrl.sby`, 8 tasks (control path only) |
| SECDED (72,64) codec | `secded_enc.v`, `secded_dec.v` | 187 | `sw/golden/secded.py` | `test_secded.py` | `secded.sby`, 3 tasks |
| TMR voter | `tmr_voter.v` | 61 | in-test majority model | `test_tmr_voter.py` | `tmr_voter.sby`, 8 tasks |
| Pilot integration + TT wrapper | `pilot_top.v`, `tt_um_melihakbulut_nssoc.v` | 1,477 | `lif_core.py` + `regmap_gen.py`, driven through the TT pins | `test_pilot_top.py` | none |

The pilot integration has **no formal job**. That is a deliberate
position — it integrates blocks each proven separately — and it is also
the single largest verification gap in wave 2, because integration is
where wave 2's own defects were found (sections 3.3 and 3.5). It is
carried as an open item in section 6.1.

### 2.2 Verification, re-measured

All three suites were executed for this record. Commands are exactly
those in `docs/11` section 8.

**Register map and Python golden model**, from the repository root,
measured 12:29 local **[fact]**:

| Target | Command | Result |
|---|---|---|
| Register-map sync | `.venv/bin/python regmap/generate.py --check` | exit 0, no output |
| Golden-model suite | `.venv/bin/python -m pytest -q` | **145 passed in 0.44 s** |

Composition, from `--collect-only` **[fact]**: `test_lif_core.py` 41,
`test_secded.py` 37, `test_tt_submission.py` 16,
`test_flow_evidence.py` 16, `test_regmap.py` 12, `test_multipass.py` 9,
`test_events.py` 7, `test_traceability.py` 4, `test_e2e.py` 3. Sum 145.
This reproduces `docs/11` section 8.1 exactly, file for file.

**cocotb suites**, from `hw/tb`, measured 12:29:45 to 12:31:44 local
against a working tree identical to `be6ebd9` **[fact]**:

| Target | Command | Reported line |
|---|---|---|
| aer_fifo | `make` | `TESTS=11 PASS=11 FAIL=0 SKIP=0` |
| npu_regbank, 512x512 | `make -f Makefile.regbank` | `TESTS=33 PASS=33 FAIL=0 SKIP=0` |
| npu_regbank, 256x256 | `make -f Makefile.regbank small` | `TESTS=33 PASS=33 FAIL=0 SKIP=0` |
| lif_core, 32x32 | `make -f Makefile.lif` | `TESTS=24 PASS=24 FAIL=0 SKIP=0` |
| lif_core, 8x4 | `make -f Makefile.lif N_NEURONS=8 N_AXONS=4 …` | `TESTS=24 PASS=24 FAIL=0 SKIP=0` |
| lif_core, 64x16 | `make -f Makefile.lif N_NEURONS=64 N_AXONS=16 …` | `TESTS=24 PASS=24 FAIL=0 SKIP=0` |
| secded, both elaborations | `make -f Makefile.secded` | `TESTS=12 PASS=3 FAIL=0 SKIP=9` (encoder run) and `TESTS=12 PASS=9 FAIL=0 SKIP=3` (decoder run) |
| tmr_voter, three widths | `make -f Makefile.tmr` | `TESTS=7 PASS=6 FAIL=0 SKIP=1` at each of WIDTH 1, 8 and 32 |
| pilot, 8x8, q4x4 | `make -f Makefile.pilot` | `TESTS=21 PASS=21 FAIL=0 SKIP=0` |

Every driver returned exit 0. **108 distinct cocotb tests** across the
six suites: 11 + 33 + 24 + 12 + 7 + 21 = 108 **[fact]**. This
reproduces `docs/11` section 8.2.

The `SKIP` counts are structural and not coverage holes. In `secded` the
skips are the other elaboration's tests — the decoder run skips the
three encoder tests and the encoder run skips the nine decoder ones; in
`tmr_voter` the one skip is a width-gated test that is generated only
where it is reachable. A reader auditing a `SKIP` count should establish
which of the two it is before treating it as a gap.

The pilot suite is parameterized like the others, and `docs/11` records
it green at seven geometries. Two more were run for this record — 4x8
and 16x16, both against `hw/rtl/pilot_top.v` at its committed content
(SHA-256 `6a47e674…`) — and both returned `TESTS=22 PASS=22 FAIL=0
SKIP=0` **[fact, 12:52 local]**. Twenty-two rather than twenty-one
because the working tree's testbench had by then gained the uncommitted
test of section 3.5; the geometry independence is what the run
establishes. The other six geometry result files in `hw/tb`
(`4x8`, `8x4`, `8x16`, `8x8_q2x2`, `8x8_q8x8`, `16x16`, timestamped
11:18-11:19) each record 21 tests, 0 failures, 0 skips **[fact, parsed
from the JUnit files]** — but those were produced by the wave-2
workstream before this record began, not by it, and they are untracked.

Six of the nine invocations run *the same test list at a different
geometry or width*, and three of them elaborate more than once. Summed
across all 12 elaborations, these nine commands executed **215 tests:
200 pass, 0 fail, 15 structural skips** **[fact, summed from the
`TESTS=`/`PASS=`/`FAIL=`/`SKIP=` lines of the nine runs]**. Both numbers
are true and they answer different questions: 108 is how much was
written, 215 is how much was run. `docs/11` reports 108; this record
reports both, because the parameter sweep is a substantial part of what
wave 2 bought and 108 alone hides it.

**Formal**, `make -C formal everything` from the repository root:
**28 `DONE (PASS, rc=0)` lines, no `DONE` line of any other kind, exit
0, 11 min 58.7 s wall** **[fact, 12:43:44-12:55:43 local]**. The gate
comprises **28 tasks across five jobs** — 4 `aer_fifo`, 5
`npu_regbank`, 3 `secded`, 8 `tmr_voter`, 8 `lif_ctrl` **[fact, counted
from the `[tasks]` sections of the four `.sby` files and the target
lists in `formal/Makefile` and its three fragments]**. An earlier
attempt terminated on an environment collision rather than on a
verification result; that is a finding in its own right (section 6.5)
and the per-task verification of the clean run is in section 8.

Counting each property set once at its default parameters, the five jobs
carry **374 assert obligations** (21 + 251 + 64 + 23 + 15) and **67
cover obligations** (5 + 31 + 15 + 9 + 7), and every cover obligation is
reached **[fact, counted from the per-task JUnit files and `PASS`
summaries of this record's own run; the figures reproduce `docs/11`
section 8.3]**. The `lif_ctrl` `LIF_LIVENESS` arm adds two asserts and
the `LIF_SAFE_ENTRY` arm replaces the 15 covers with 2; those are
different elaborations of one file, not extra property sets, and are
outside the totals.

### 2.3 Physical sign-off: ROADMAP gate G0

Gate G0 asks for a DRC/LVS-clean `sg13g2` harden on at least one block.
Run `trial-03-signoff` on `aer_fifo`, executed 2026-08-25 08:50:58 to
09:02:18 local from `hw/openlane/aer_fifo/config.json` exactly as
committed, 80 flow stages, 680.4 s of summed step runtime **[fact,
`docs/12` section 4]**:

| Check | Step | Result |
|---|---|---|
| Magic DRC | `64-magic-drc` | 0 errors |
| KLayout DRC, deep, `no_recommended` | `65-klayout-drc` | 0 errors |
| Netgen LVS | `70-netgen-lvs` | 0 on all seven counters |
| KLayout XOR against the Magic GDS | `62-klayout-xor` | 0 differences |
| Antenna, post-detailed-routing | `46-openroad-checkantennas-1` | 0 nets, 0 pins |
| Detailed-routing DRC | `44-openroad-detailedrouting` | 0 |
| Disconnected pins | `48-odb-reportdisconnectedpins` | 0 |
| Power-grid connectivity | `56-openroad-irdropreport` | 0 on VPWR and VGND |
| Setup / hold / max-slew / max-cap | `55-openroad-stapostpnr` | 0 violations, all three corners |

The seven Netgen counters are named individually in `docs/12` section
4.1 and all read 0. This is the strongest single claim wave 2 makes, and
its evidence is real but not durable. The run trees still exist on the
build machine — `hw/openlane/aer_fifo/runs/` holds `trial-01`,
`trial-02-nohdi`, `trial-03-signoff` and `config-recheck`, about 1 GB —
and `sw/tests/test_flow_evidence.py` reads the sign-off run directly and
checks all sixteen documented figures against it, passing rather than
skipping at the time of writing **[fact, re-run 2026-08-25]**. What is
not durable is their survival: the run trees are gitignored, so a fresh
clone or a wiped build directory leaves only `docs/12`'s transcription,
and the guard test then skips instead of failing. `docs/12` section 9
carries the reproduction commands for that case. Treat the G0 result as
**measured, currently machine-checkable, and reproducible from the
recorded commands** — not as a claim resting on transcription alone.

The pilot itself also closes, which is a stronger result than G0 asked
for and belongs in the same place: the full `Classic` flow at 4x2, run
against the submission's own `config_merged.json`, reaches a GDS with
52.38 % utilization, 0 detailed-route DRC, 0 Magic DRC, 0 Netgen LVS, 0
antenna violations and 0 setup/hold/max-cap/max-slew violations on
three corners **[fact, `docs/15` section 5.3]**. One metric is not zero
and `docs/15` says so out loud: `design__max_fanout_violation__count:
72`, identically on all three corners.

### 2.4 The submission tree

`tt/` is a generated port of `ttihp-verilog-template` at
`6598bef4d3159f19fe471a2a2225df52e6f5ad25`, with tile geometry and
schema from `tt-support-tools` `01d5d281` **[fact, `docs/15` section
8.1]**. It is built by `scripts/gen_tt_submission.py` and guarded three
independent ways by `sw/tests/test_tt_submission.py`: `MANIFEST.sha256`
against the files, `tt/src` against `hw/rtl`, and the whole tree against
a fresh in-memory regeneration. Measured for this record: **16 passed**
**[fact, `.venv/bin/python -m pytest sw/tests/test_tt_submission.py -q`]**.

Validation against the real `tt-support-tools`: `--check-docs` passes
and `--create-user-config` resolves `DIE_AREA` to `0 0 854.40 313.74`
and accepts the 43-bit port list with no extras **[fact, `docs/15`
section 8.5]**. Gate-level smoke on the locally produced post-route
netlist is 5 of 5 **[fact, same]**.

What that does **not** establish is precheck. Precheck runs a pin
placement check against the shuttle mux, a top-level-uniqueness check on
the GDS and the shuttle's own KLayout DRC deck, none of which the local
`Classic` flow runs — and the Tiny Tapeout configuration switches
KLayout DRC off locally (`RUN_KLAYOUT_DRC: 0`). The honest summary is:
the design fits, routes and closes timing locally; nothing yet says it
is acceptable to the shuttle.

### 2.5 What the totals do not say

Three qualifications a skeptical reader should apply to section 2.2.

1. **145, 108 and 28 count artefacts, not coverage.** They are the right
   numbers for detecting a regression and the wrong numbers for judging
   how much of the design is verified. Section 6 is where that question
   is answered, and it is answered negatively in several places.
2. **The parameter sweeps are narrow.** `lif_core` is exercised at four
   geometries in the full suite (4x4, 8x4, 32x32, 64x16) and at three
   more for the geometry-sensitive cases (961x4, 1000x4, 1024x4); the
   specification allows 1..1024. `npu_regbank` is proven at two
   geometries and one reduced counter width. Nothing covers the space.
3. **One suite is a drift guard over another workstream's output.**
   `sw/tests/test_tt_submission.py` goes red the moment `hw/rtl` is
   edited without regenerating `tt/`, which is a state the repository
   passes through routinely mid-wave. A red there means "the submission
   tree is stale", and the fix is `python3 scripts/gen_tt_submission.py`
   — never an edit under `tt/`.

---

## 3. The review method, and what it caught that ordinary review would not

### 3.1 Three adversarial waves

Wave 2's artefacts were reviewed in three passes, each adversarial in
the `docs/07` sense: a candidate finding is not reported until it has
been re-verified against primary evidence, and a candidate that fails
re-verification is recorded as rejected rather than dropped. The commit
message records **64 evidenced findings** across the three waves
**[claim — the count is asserted in the `be6ebd9` commit message and is
not independently checkable from the tree, because no finding ledger was
written to a file and the wave is a single squashed commit]**.

This document is the first place the method itself is recorded. Its
fingerprints are, however, all over the tree and each of them *is*
checkable:

- `formal/lif_ctrl_props.v` opens with the mutation experiment that
  justifies the job's existence;
- the mutation runs survive as `hw/tb/results_mut_m1..m7.xml` (untracked
  — section 6.2);
- `docs/09`'s target table gained a measured **Status** column, which
  split target #4 into #4a and #4b because only the voter half is
  provable against today's RTL, downgraded #2 to "closed, with the
  cross-check delivered by simulation rather than by `eqy`", and
  downgraded #5 to "partial";
- `docs/11` section 7.4 records where engine diversity does *not* reach,
  naming the two assertions;
- `docs/12` section 10.1 records three errata this workstream raised
  against files it did not own, kept visible after they were applied;
- `docs/15` section 8.4 does the same for two RTL changes.

None of those is the kind of thing a document writes about itself unless
something forced it to.

### 3.2 The acceptance rule

The rule that makes the difference is narrow and worth stating exactly:

> A repair is accepted only when the corresponding test or proof has
> been shown to **fail** against the reintroduced defect.

Not "a test was added". Not "the property now passes". The defect is put
back, the suite is run, and the specific test that is supposed to catch
it is observed failing. If it does not fail, the repair is not a repair
— it is a change that happens to coexist with a green suite.

This is what ordinary review cannot do. Ordinary review reads the RTL
and the test and asks whether they agree. Both can agree and both can be
wrong in the same direction, which is precisely the failure mode of
sections 3.3 and 3.4. Reintroducing the defect is the only cheap
experiment that distinguishes "the test checks this" from "the test is
consistent with this".

The cost is real: it needs a source override so the suite can be pointed
at a modified copy of the RTL without editing the tree. Two drivers have
one — `LIF_SRC` in `Makefile.lif` and `REGBANK_SRC` in
`Makefile.regbank` **[fact — grepped; no other driver has one]**. Any
block acquiring a mutation campaign should add the same two-line pattern
inside its own fragment rather than a shared one.

### 3.3 The two defects that tests and properties had locked in

The dangerous case is not an untested behaviour. It is a behaviour whose
test and whose formal property were both written by reading the RTL. A
property phrased in the design's own terms is a tautology dressed as a
theorem: it passes, it will keep passing after the defect is introduced,
and it will keep passing after the defect ships.

Wave 2 found this twice, both in the register bank, and repaired both by
re-deriving the property from the specification. The repairs are in the
tree and each one states, in its own words, the defect class it exists
to catch.

**Defect A — the configuration lock set.** `docs/10` section 6 fixes
which registers a configuration write may not touch while the core is
busy. The design implements that as an internal decode wire,
`sel_cfg_locked`. A property written over `sel_cfg_locked` cannot
detect a wrong locked set, because it *is* the locked set; and a cocotb
test that drives one register cannot distinguish the specified set from
any larger or smaller one.

The repair, `formal/npu_regbank_props.v` lines 52-56 and 147-151:

> The locked and unlocked sets are restated here from the
> specification, by generated offset, NOT taken from the design's own
> `sel_cfg_locked` / `wr_block` wires: a property phrased in terms of
> the design's locked set cannot detect a wrong locked set.

> These lists are deliberately independent of `sel_cfg_locked`: if the
> design locked one register too few or one too many, P8 has to fail
> rather than follow.

and on the simulation side, `hw/tb/test_npu_regbank.py` lines 100-107,
which enumerate `LOCKED` (17 names) and `UNLOCKED` (6 names)
> by register name from the specification side, never derived from the
> design's own decode wire, so a locked set that grows or shrinks in the
> RTL is caught rather than mirrored.

Three checks now hold the set in place: `f_spec_locked` /
`f_spec_unlocked` in P8, built from the generated `ADDR_*` offsets;
`test_config_lock_covers_every_locked_register`, which drives all 17
locked and all 6 unlocked registers rather than one of each; and
`test_regmap_walk_is_complete`, which asserts that the two lists
*partition* the writable half of the generated map and that the locked
set has exactly 17 members. The last of these is the one that survives a
future edit: adding a writable register to `regmap.yaml` and forgetting
to classify it now fails a test, rather than silently leaving it
unlocked.

**Defect B — the `ERR_CFG` event set.** `docs/10` section 6 makes
`STATUS.ERR_CFG` the report for "out-of-range configuration or config
write while BUSY". The design raises it from several internal terms. A
property written over the design's own `sts_evt` term for `ERR_CFG`
cannot detect a *missing* term, for the same reason.

The repair, `formal/npu_regbank_props.v` lines 184-194, restates the two
configuration-error conditions

> likewise restated rather than borrowed from the design, so that
> removing one of the design's own event terms is a counterexample and
> not a vacuity

as `f_spec_en_write_bad` (a `CTRL` write that sets `EN` while the
configuration is out of range) and `f_spec_en_bad` (an enabled core
whose configuration is out of range at all). The second is the one that
matters. Without it, a configuration write that *invalidates a
configuration that was valid when `EN` was set* produces a state in
which `STATUS` reports `CTRL.EN = 1`, `en` is held low, and no error is
reported anywhere — a core that silently will not start, which the
single-source register description of `ERR_CFG` forbids. The RTL header
convention C5 spells the same reasoning out, and
`test_err_cfg_latches_on_a_write_that_invalidates_a_running_config`
(`hw/tb/test_npu_regbank.py:922`) is the directed test.

A third site follows the same pattern and is worth naming even though it
is defensive rather than a repair: P10 restates `cfg_valid` over the
*exported* configuration ports from the `docs/10` section 6 range table,
because "a port wired to the wrong register would make the two
disagree". P3..P8 assert on the internal `r_*` registers, which leaves
the ports — the only thing the rest of the chip sees — unchecked.

**What the tree proves about these two, and what it does not.** The
repairs, the reasoning and the tests are all in the tree and quoted
above **[fact]**. The *pre-repair* states are not, because wave 2 is a
single squashed commit: there is no diff in which P8 reads
`sel_cfg_locked`. A reader who wants to check that these were live
defects rather than defensive hardening has one cheap experiment
available, and it is the acceptance rule of section 3.2 run backwards:
edit `f_spec_locked` to drop one address, or delete `f_spec_en_bad`, and
confirm that the corresponding task stops failing. That takes minutes
and this record recommends it be added to the mutation campaign in
section 7.3 rather than asserted here.

### 3.4 The five LIF handshake mutants that survived a lockstep suite

The most transferable result of wave 2 is a negative one about a phrase
that appears in every verification plan.

`hw/rtl/lif_core.v` is verified in lockstep against
`sw/golden/lif_core.py`: identical configuration, weights, event and
tick streams, with the entire neuron state file and the emitted spike
stream compared after every command. That is a strong result about
arithmetic. It is *no* result about the control interface, because the
golden model has no notion of `valid`/`ready`, of a command arbiter, or
of a stall. Whatever the model does not represent is unconstrained, and
unconstrained silently.

An earlier revision of `docs/11`'s coverage table recorded the LIF
datapath's formal job as "none; covered by golden-model lockstep". That
claim was disproved by measurement:

> **Five independent mutants of `ev_ready`, `tick_ready`, the
> `state_clr` priority and the held-spike interaction survived the
> entire lockstep suite.**
> — `docs/11` section 1.1

`formal/lif_ctrl_props.v`'s header states the same result in its own
words ("a mutation experiment confirmed it — five independent mutants
… all survived the entire lockstep suite") as the reason the job exists
at all.

The mutation runs survive as JUnit files. Read for this record
**[fact, `hw/tb/results_mut_m*.xml`, parsed]**:

| Mutant | Test that kills it in the repaired suite | Failures |
|---|---|---|
| `m1_ev_ready_ignores_state_clr` | `test_arbitration_state_clr_outranks_both_channels` | 1 of 24 |
| `m2_tick_ready_ignores_ev_valid` | `test_arbitration_spike_outranks_tick_and_loses_neither`, `test_no_deadlock_with_both_channels_held` | 2 of 24 |
| `m3_priority_event_over_clear` | `test_arbitration_state_clr_outranks_both_channels` | 1 of 24 |
| `m4_held_spike_swallows_clear` | `test_held_spike_does_not_swallow_state_clr` | 1 of 24 |
| `m5_ready_deadlock_both_valid` | `test_arbitration_spike_outranks_tick_and_loses_neither`, `test_no_deadlock_with_both_channels_held` | 2 of 24 |
| `m6_default_recovers_to_idle` | `test_safe_state_on_corrupted_fsm_encoding` | 1 of 24 |
| `m7_safe_without_err_cfg` | `test_safe_state_on_corrupted_fsm_encoding` | 1 of 24 |

Each file records 24 tests, so each was run against the *repaired*
suite; each shows exactly the named test failing and everything else
passing. That is the acceptance rule of section 3.2, executed and
archived, seven times.

The repair was deliberately two-sided: directed handshake tests, which
kill the mutants on one stimulus and grew the suite from 16 tests to 24,
**and** `formal/lif_ctrl.sby`, which proves H1..H9 over the whole input
space. Either alone would have been weaker, and the second is what makes
the result parameter-independent.

`m6` and `m7` carry a second lesson that generalizes past this block.
Both are mutants of the SAFE state's default arm; both survive
`lif_prove` and `lif_bmc_live`, and only `lif_bmc_safe` catches them.
The reason is structural: "the state encoding is always one of the five
legal codewords" is itself an H8 assertion, and k-induction assumes
every assertion at steps 0..k-1 before checking step k — so in `prove`
the previous encoding is *assumed* legal, the antecedent "if the
previous encoding was illegal" is false at every checked step, and a
default arm that silently resumes in IDLE and latches nothing passes.
`lif_bmc_safe` starts the trace on an illegal encoding instead of from
reset, which is the only way to reach the antecedent. **Do not drop
`bmc_safe` from the gate on the grounds that `prove` covers it.**

### 3.5 The method observed running

While this record's measurements were being taken, another workstream
ran the acceptance rule on a live defect in the same tree. Watching it
happen is better evidence for the method than any description of it, so
it is recorded here with times and file contents.

At 12:31:53 local, `hw/rtl/pilot_top.v` carried an uncommitted one-line
change against `be6ebd9` **[fact, `git diff`, captured verbatim]**:

```
-    wire err_cfg_any = sticky_errcfg || lif_err_cfg;
+    wire err_cfg_any = sticky_errcfg;
```

That is exactly the defect `docs/15` section 8.4 item 1 describes and
that `be6ebd9` repairs: with only the sticky term, `STATUS.ERR_CFG` and
the `ERR` pin can report a still-parked neuron core as recovered.

At 12:34:21 the RTL was back at its committed content and
`hw/tb/test_pilot_top.py` had gained a 101-line test,
`test_parked_core_holds_err_cfg_on_the_live_term`, whose docstring
records the experiment and its outcome:

> the sticky term alone therefore answers every host-visible stimulus,
> and reverting `err_cfg_any` to `sticky_errcfg` passes the rest of this
> suite — measured, 21 of 21. That makes the live term untested, not
> unnecessary; this test closes that gap.

Two things are worth extracting. First, this is the acceptance rule
finding a *gap in the test suite* rather than a bug in the RTL: the RTL
was already right, and the experiment proved that nothing was holding it
right. Second, the reason the gap existed is mechanical and general —
the sticky flop is re-armed on every clock edge while the core is
parked, and its assignment sits later in the same `always` block than
the `STATUS_CLR` clear, so it wins. One term therefore answers every
stimulus a host can produce, and the other term is invisible from the
pins. A suite driven only through the package will not find that class
of redundancy on its own.

This record ran the pilot suite twice more against the moving tree, in
isolated build directories so as not to disturb the other workstream
**[fact]**: at 12:34:59, 22 tests with 1 failure — an unmet setup
precondition inside the new, still-unfinished test (`STATUS` read
`0x0B` with `BUSY` still set), not the property it checks; at 12:38:43,
22 tests, 22 pass. Neither of those is a baseline result, and neither is
quoted anywhere else in this document. **The committed baseline is the
12:31:44 run in section 2.2 — 21 tests, 21 pass, against a working tree
byte-identical to `be6ebd9`.** The "21 of 21" in the docstring above is
a different measurement of a different thing: it is the mutated RTL
passing the 21 tests that existed before this one was written.

### 3.6 What this method does not do

Stated so the method is not oversold. It finds defects that a test
*could* catch and does not. It says nothing about behaviour no test
addresses at all, which is the larger class; the pilot integration has
no formal job and no fault-injection campaign, and no amount of mutation
testing on the blocks below it changes that. It is also only as good as
the mutant list, and every mutant in this repository was written by
hand.

---

## 4. Reading the sby status line: "PASS 0 0" is not a weak result

This section exists because a reader who opens `formal/tmr_voter_bmc/status`,
sees

```
PASS 0 0
```

and concludes that zero steps ran or zero properties were checked will
make exactly the wrong inference about the strongest proofs in the
repository. All eight `tmr_voter` tasks write that line.

sby writes `<STATUS> <retcode> <total_time>` at exit.

- **`<STATUS>`** is the verdict, one of `PASS`, `FAIL`, `UNKNOWN`,
  `ERROR`, `TIMEOUT`, `CANCELLED`. sby also drops a summary file *named
  after the verdict* in the same directory, so the presence of
  `formal/<task>/PASS` rather than `formal/<task>/FAIL` is itself the
  result.
- **`<retcode>`** is sby's process exit code: `0` when the verdict
  matches what the job expected, `2`/`4`/`8`/`16`/`32` for
  FAIL/UNKNOWN/TIMEOUT/ERROR/CANCELLED, and `1` for a `PASS` that was
  *not* expected — which is how a job declaring `expect fail` reports
  that the bug it was pinning has been fixed. This is the field a make
  target or a CI step keys on.
- **`<total_time>`** is **elapsed child-process (CPU) time in whole
  seconds** — `getrusage(RUSAGE_CHILDREN)` user+system, computed in
  sby's `sby_core.py` and written by the launcher as
  `f"{task.status} {task.retcode} {task.total_time}"` **[fact, read
  from the installed sby source, `docs/11` section 7.3]**.

The third field is a **cost**. It is not a proof depth, not a number of
solver steps, and not a number of properties. The trailing zero on the
voter says the whole task — `read_verilog`, `prep`, SMT export and solve
— finished in under one second of CPU, which is unsurprising for a
combinational voter. The log shows the work:

```
$ grep 'step 0\|Status:' formal/tmr_voter_bmc/logfile.txt
...  Checking assumptions in step 0..
...  Checking assertions in step 0..
...  Status: passed
```

A depth-1 BMC checks exactly one time step, and for a combinational
model driven by `$anyconst` that single step ranges over the entire
input space — 2^(3xWIDTH) for the voter, 2^64 x 2^72 for the SECDED
codec. Depth-1 BMC on these two blocks is a **full proof, not a bounded
one**, and it is the acceptance criterion `docs/09` targets #2 and #4a
ask for.

The comparison that settles the point, both numbers from the *same*
`make -C formal everything` run in section 8: `formal/tmr_voter_bmc/status`
reads `PASS 0 0` while `formal/aer_fifo_bmc/status` reads
**`PASS 0 395`** — 395 seconds of child CPU, the most expensive task in
the gate **[fact, read from the two status files]**. The expensive one
is the *weaker* result — a bounded check to depth 40 on a sequential
design — and the free one is exhaustive over its whole input space.
Cost tracks how hard the model was to solve, not how much the answer is
worth. Ten of the 28 tasks in that run write `PASS 0 0`: all eight
`tmr_voter` tasks, `secded_cover`, and `lif_ctrl_cover_safe`.

The status line is the right thing to gate a build on and the wrong
thing to judge proof strength by. Strength is decided by four checks,
each of which catches a different way a `PASS` can be hollow **[all from
`docs/11` section 7.4]**:

1. **Did the properties reach the model?** Count `type="ASSERT"` and
   `type="COVER"` testcases in `formal/<task>/<task>.xml`. The
   `ifdef FORMAL` blocks lose their entire property set, with no error,
   if the model is ever read without `read_verilog -formal`, and the
   task then passes trivially. A collapsing assert count is the symptom.
   The count also confirms a `chparam` override took effect: the voter's
   property file states one per-bit assertion plus seven
   width-independent ones, so its assert count must be `WIDTH + 7`, and
   the measured counts are 8, 15 and 39 at WIDTH 1, 8 and 32.
2. **Was the mode actually a proof?** For a `prove` task, both
   `basecase` and `induction` must return pass in `formal/<task>/PASS`
   and the last line must read `successful proof by k-induction.` A
   basecase-only result is a bounded check wearing a proof's name.
3. **Are the properties non-vacuous?** Every block ships cover
   obligations, and a cover task must pass *and* report reached
   statements. `tmr_voter` and `lif_ctrl` each carry more than one cover
   task for structural reasons — the voter's cover set is
   width-conditional, and `S_SAFE` is unreachable from reset by
   construction so a reset-rooted cover about it would be meaningless.
4. **Did anything get optimized away?** `grep -i warning` the logfile.
   The expected output on this tree is one benign
   "Replacing memory … with list of registers" line per `aer_fifo` task
   and **three** per `lif_ctrl` task — one for each of `lif_core`'s
   `wmem`, `vmem` and `rmem` arrays — and none at all from
   `npu_regbank`, `secded` or `tmr_voter` **[fact, measured in
   section 8; `docs/11` section 7.4 states zero for `lif_ctrl` and is
   wrong, see section 6.4 item 5]**. Anything else — an unresolved
   module, a `chparam` that did not apply, a blackboxed instance —
   deserves reading before the `PASS` is believed.

Check 1 is also where wave 2 found a real limit in its own
engine-diversity argument, and the honesty of that entry is worth
noting. `secded bmc` reports 23 assertions and `secded bmc_abc` reports
21 in the AIGER model. The two missing are C1 and C2, identified by name
from `formal/secded_bmc_abc/model/design_aiger.ywa`. The mechanism is
that `design_aiger.ys` runs `opt -full` before `aigmap` while
`design_smt2.ys` runs no optimization at all, so C1 — which asserts
`enc_check == code[71:64]` against an encoder ending in
`assign code_out = {check_out, data_in};` — is discharged structurally
and cleaned away. C1 and C2 therefore **hold**, by a stronger route than
a solver, but the engine-diversity argument covers 21 of the codec's 23
assertions and not all 23. Closing that is a third task with `opt`
suppressed, and it is in section 7.3.

---

## 5. Tile sizing: the measurement that moved the pilot from 2x2 to 4x2

### 5.1 The numbers

`docs/06` section B.6 carried a 2x2 (4-tile) pilot as the default.
Wave 2 measured it and it does not fit. The measurement chain, in order,
with each link's status:

| Quantity | Value | Status |
|---|---|---|
| `pilot_top` at 8x8, post-techmap, local Yosys 0.33 on `sg13g2_stdcell` | 105,245 um2 | **[fact]** |
| `tt_um_melihakbulut_nssoc` at 8x8, post-techmap, same flow | 105,452 um2 | **[fact]** |
| Pre-placement synthesis netlist through the TT flow | 107,782 um2, 1,037 flops | **[fact]** |
| Timing-repair buffers inserted after CTS | 25,494 um2 | **[fact]** |
| **Placed standard-cell area at 4x2** | **136,107 um2** | **[fact, the LibreLane run]** |
| 2x2 placement rows, from `tt_block_2x2_pgvdd.def` | 126,685 um2 | **[fact, read from the DEF template]** |
| 4x2 placement rows, same source | 259,837 um2 | **[fact]**, confirmed independently by the flow's own `design__core__area` 259,837 |

The utilization a 2x2 block would need is therefore

    136,107 / 126,685 = 1.0744  ->  107.4 %

and the utilization 4x2 actually achieved is 52.38 % **[fact]**. The
107.4 % is an **[estimate]** — it applies a measured placed area to a
different die — but it is an estimate built on a fact rather than on
another estimate, and its error runs the wrong way for the small shape:
a denser floorplan makes the resizer work harder, so a real 2x2 run
would need *more* than 107.4 %, not less. The floor is firmer still: the
pre-placement netlist alone, 107,782 um2, is 85.1 % of a 2x2 before a
single repair buffer exists, and the flow then inserted 25,494 um2 of
them.

Full table, from `docs/15` section 4.3, with only the 4x2 row a
measurement:

| Shape | Tiles | Cost | Placement rows (um2) | Utilization needed | Verdict |
|---|---|---|---|---|---|
| 2x2 | 4 | ~EUR 280 | 126,685 | **107.4 %** | impossible |
| 3x2 | 6 | ~EUR 420 | 193,261 | 70.4 % | above anything this project has achieved |
| **4x2** | **8** | **~EUR 560** | **259,837** | **52.4 %** | **measured: closes, 0 DRC, 0 timing violations** |
| 6x2 | 12 | ~EUR 840 | 392,988 | 34.6 % | room to grow |
| 3x4 | 12 | ~EUR 840 | 443,784 | 30.7 % | room to grow |

Reference points for what a utilization number means in this project:
the sibling programme's shipped SKY130 Tiny Tapeout design closed at
70.66 %, the `aer_fifo` trial here landed at 51.8 %, and the pilot
closed at 52.38 %. 3x2 sits above all three, which is why the decision
is 4x2 and not 3x2.

Two corrections inside that chain deserve to be visible, because both
made the case for 2x2 *worse* and both were self-reported. The previous
revision interpolated a tile pitch and overestimated every two-row shape
by 6-8 %, giving 4x2 a 290,667 um2 block where the DEF and the flow both
say 268,060. And `docs/12` section 6.5's interpolated geometry — which
had been used to size the SRAM macro question — was superseded by the
same measurement, with `docs/12` explicitly deferring to `docs/15` as
the authority for tile geometry.

### 5.2 Why 2x2 cannot be rescued

The decisive number is not the total but the split. `lif_core` at 8x8
alone is 43,512 um2 measured standalone; the wrapper at 8x8 is 105,452
um2. The difference, **61,940 um2**, is the register bank, the serial
host port, the event queues, the dispatcher, the ECC-checked weight
loader, the TMR domain, the SECDED codec and the fault counters.

A 2x2 block at a realistic 70 % utilization holds
126,685 x 0.70 / 1.2907 = **68,700 um2** of post-techmap cells, where
1.2907 is this design's measured tool-delta-and-growth factor. So the
observability and hardening set consumes **about 90 % of a 2x2 block
before a single neuron is instantiated**. The smallest configuration the
design will elaborate at all (4 neurons x 8 axons) still needs 88.3 %.

Stripping content does not rescue it either. Deleting both
demonstrators and one event queue recovers, from measured pieces, about
23,112 um2, plus an estimated 12,200 um2 of ECC staging and
configuration replica flops — roughly 35,300 um2, leaving about 70,150
um2, which still needs 71.5 % in 2x2. A 2x2 submission would have to
delete the fault tolerance and still be marginal, which removes the
pilot's reason to exist: the case for this chip is that it is a cheap
instrument for first TID and SEE data on `sg13g2_stdcell` logic, and
that argument needs the counters.

The consequence for the funding envelope is nil — `docs/06` section B.6
already carries EUR 560 for the 8-tile option — and the consequence for
the 2026-09-07 go/no-go is that it stops deciding *how many tiles to
buy* and becomes *whether the SRAM macro goes into the tiles being
bought anyway*. Section 6.3 records that this second question is also
already answered, negatively.

### 5.3 A number that disagrees with itself: 113.7 % versus 107.4 %

`ROADMAP.md` section P1 states that the integrated pilot "needs 113.7
percent utilization in 4 tiles", and the `be6ebd9` commit message
repeats the same figure. `docs/15` section 4.3 states 107.4 %.

Both cannot be right, and the one that is checkable is 107.4 %:
`docs/15` shows its numerator (136,107 um2, the flow's measured placed
area), its denominator (126,685 um2, read out of
`tt_block_2x2_pgvdd.def`), and the division; and the same document's
4x2 row is confirmed independently by
`or_metrics_out.json`'s `design__core__area` of 259,837. `ROADMAP.md`
quotes 113.7 % against the post-techmap figure 105,245 um2 and does not
state the denominator it divided by, so the arithmetic cannot be
reproduced from what is written. The most likely reading is that the
ROADMAP text predates the DEF-template measurement and still carries the
interpolated tile geometry that `docs/12` section 10.1 records as
superseded **[estimate — the direction of the error is consistent with
the interpolation, but no revision of `ROADMAP.md` exists that would
confirm it, since wave 2 is one commit]**.

Nothing in the decision changes: 107.4 % and 113.7 % both say 2x2 is
impossible, and the correction moves the number toward the *less*
alarming end while leaving the verdict identical. But an external reader
who checks the two documents against each other finds a contradiction in
the first place they look, and the figure that would be quoted into an
NLnet application is whichever one they found first. This is a blocking
documentation correction for section 7.3, and `ROADMAP.md` is
integrator-owned, so it is written up in section 10 rather than fixed
here.

---

## 6. What remains open and unverified

Listed honestly. Most of these are recorded elsewhere in the repository
already and are collected here so that one list exists; the seven in
sections 6.4 and 6.5 are new, found while checking the others. Nothing
here is a reason to stop.

### 6.1 The formal program

`docs/09`'s target table now carries a measured status column, which is
the single most useful thing wave 2 did for this section. Reading it
back:

| Target | Status |
|---|---|
| #1 sync AER FIFO | **closed** |
| #2 SECDED codec | **closed**, with the track-2 cross-check delivered by lockstep simulation, not by `eqy`; **no eqy job exists in this repository** |
| #3 async FIFO / CDC | **blocked on RTL** — no asynchronous FIFO exists; the pilot is single-clock |
| #4a TMR voter | **closed** |
| #4b TMR replica resynchronization | **blocked on RTL — nothing to prove**; `tmr_voter.v` deliberately has no resync path and `pilot_top.v` states that none is implemented |
| #5 control-FSM any-state recovery | **partial** — the pattern exists and is applied to exactly one FSM, `lif_core`'s control path, with K = 1. The scheduler, multi-pass sequencer, scrub controller and link controllers have no RTL. **The fault-injection campaign this target is required to agree with has not been run** |
| #6 register file / CSR write-enable | **closed for the register bank**; the TMR'd-CSR clause reuses 4a and is exercised in RTL, not proven. `pilot_top.v` votes 55 configuration bits through the proven voter, but **no property in this repository binds the register bank to the voter** |
| #7 bus arbiter / interconnect | **blocked on RTL** |
| #8 QSPI / weight-streaming handshake | **blocked on RTL** |
| #9 SpaceWire codec link FSM | **not started** |
| #10 management core integration | **not started**; the core decision is itself open |

**Four of eleven rows are closed** — #1, #4a and #6 outright (#6 for the
register bank, with its TMR'd-CSR clause exercised rather than proven),
and #2 with a named substitution for its cross-check. One is partial,
four are blocked on RTL that does not exist, and two are not started.
That is a reasonable position 27 days into a design programme and it is
not what "formal proofs green" sounds like. Anyone quoting the formal
programme externally should quote this table and not the 28-task count.

Additional gaps inside the closed rows:

- **Engine diversity does not reach two SECDED assertions** (section 4).
  21 of 23 are checked by both engine families.
- **`npu_regbank` is proven at two geometries and one reduced counter
  width**, not for all parameterizations.
- **The pilot integration has no formal job at all.** It is an
  integration of proven blocks, which is a real argument, and it is also
  where both of wave 2's locked-in defects (section 3.3) and the live
  one (section 3.5) were found.

### 6.2 Simulation and fault injection

- **No fault-injection campaign exists at `be6ebd9`.** `docs/09`
  target #5 requires the formal any-state result and an FI campaign to
  agree, and one half of that pair is missing. (An untracked
  `hw/tb/test_fi_campaign.py` appeared in the working tree while this
  record was being written; see the note at the end of section 7.3. It
  is not committed and not reviewed, so it does not change this entry.)
  The sibling programme has
  the method already: a 512-line cocotb harness, 200 single-fault
  injections classified MASKED / CORRECTED / SDC / DETECTED / HANG, a
  fixed campaign seed, ~7 s of wall time
  (`/home/hasanmelih/Documents/radhard-edge-ai`, its `docs/27` and
  `hw/tb/test_fi_campaign.py`). The recorded harness lessons transfer
  directly: sample `busy` post-NBA rather than on the edge, pre-set
  outputs to a sentinel so a misrouted result cannot alias a correct
  one, drive `force`/`release` from `cocotb.handle`, and give the
  campaign its own testbench target rather than folding it into a
  functional suite.
- **The mutation evidence is not durable.** `hw/tb/results_mut_m*.xml`
  are the primary evidence for section 3.4 and they are gitignored
  (`hw/tb/results_*.xml`). They do not survive a fresh clone, and the
  mutated sources were never in the tree at all — they were passed
  through `LIF_SRC` from outside it. A reader who clones this repository
  today cannot reproduce or even inspect the experiment.
- **Only two blocks can be mutation-tested**, because only
  `Makefile.lif` and `Makefile.regbank` have a source override.
- **The suites are single-simulator.** ROADMAP P1's verification bar
  asks for "cocotb suites green in two simulators where feasible"; every
  run in this record is Icarus.

### 6.3 Physical and submission

- **Precheck has never run** (section 2.4). The local `Classic` flow
  does not run the pin-placement check, the top-level-uniqueness check,
  or the shuttle's KLayout DRC deck, and the TT configuration disables
  KLayout DRC locally.
- **The GDS that would be manufactured has not been produced.** The
  local close used LibreLane 3.0.5 against a dev container that pins
  `librelane==3.0.0.dev44`; the PDK commit is the same. A local close is
  strong evidence about shape and configuration; it is not the artefact.
- **`design__max_fanout_violation__count: 72`** on all three corners,
  plus a 1,038-terminal clock net. Not a blocker — slew and capacitance
  are within limits at every corner — and not zero.
- **The SRAM macro question is closed negatively and the gate date has
  not caught up.** `RM_IHPSG13_1P_512x32_c2_bm_bist` places, routes and
  closes timing, and then fails Magic DRC (1,106,478 error boxes, which
  the report itself says should be divided by 3 or 4, so roughly
  277,000-369,000 distinct violations), KLayout DRC (2,316) and Netgen
  LVS (359). Every Magic error box was tested against the macro
  footprint: 1,106,478 inside, **0 outside** — the standard cells, the
  PDN and the routing are clean and the vendor layout is what the deck
  objects to. The experiment was run *without* the ECC wrapper the gate
  asks for, i.e. under strictly easier conditions. `docs/12` section 8
  recommends recording the NO-GO now rather than on 2026-09-07; nothing
  has recorded it.
- **Six smaller physical items** are carried in `docs/12` section 10.2
  and are not repeated here, of which two matter for anything going to
  silicon: `TIMING_VIOLATION_CORNERS` is left at the PDK default `*typ*`
  so slow and fast do not gate the flow, and `VSRC_LOC_FILES` is unset
  so the IR-drop numbers are indicative only.
- **Run trees are gitignored and about 1.6 GB.** Every number cited from
  them is transcribed into `docs/12` and `docs/15`; anything not
  transcribed requires a re-run.

### 6.4 Documentation defects found while writing this record

All four are in files this record does not own; all four are cheap.

1. **`ROADMAP.md` and `docs/15` give different 2x2 utilizations**
   (113.7 % vs 107.4 %), section 5.3. The commit message carries the
   superseded figure too.
2. **`docs/15` section 8.4 lists two "changes needed" that have already
   been made.** Item 1 asks for `lif_core`'s `err_cfg` to be connected
   in `pilot_top`; at HEAD it is connected, at `pilot_top.v:1041`,
   `:1270`, `:1306` and `:1361` **[fact]**. Item 2 asks for
   `tt_um_pilot.v` to be renamed; at HEAD there is no `hw/rtl/tt_um_pilot.v`
   at all, the module is `tt_um_melihakbulut_nssoc` in
   `hw/rtl/tt_um_melihakbulut_nssoc.v`, and `tt/src` holds one wrapper
   file rather than an adapter plus a wrapper **[fact]**. The name
   `tt_um_pilot` still appears on **fifteen lines** of `docs/15`
   **[fact, `grep -n tt_um_pilot docs/15-pilot-tile-plan.md`]**, in its
   header and in sections 1, 2, 4.1, 4.2, 4.4, 5.1, 5.2, 8.3 and 8.4. A
   reader following section 8.3 will look for a file that is not there.
3. **`docs/15` section 8.5 records `test_tt_submission.py` at 15 tests;
   it is 16** **[fact, measured]**. `docs/11` section 8.1 has 16. Minor,
   and exactly the kind of drift the two-document split invites.
4. **`README.md`'s document index stops at `docs/15`** and will need
   this file added. `docs/07` finding F-14 was the same defect one wave
   earlier, which suggests the index needs a generator or a test rather
   than another manual fix.
5. **`docs/11` section 7.4 check 4 states the wrong expected warning
   output for `lif_ctrl`.** It says the `npu_regbank`, `lif_ctrl`,
   `secded` and `tmr_voter` tasks emit no Yosys warnings at all;
   `lif_ctrl_prove` emits three, one per flattened memory array in
   `lif_core.v` (lines 348, 361, 362) **[fact, measured in section 8]**.
   The other three jobs are as documented. This is the only one of the
   six defects here that degrades a *check* rather than a claim: a
   reader running check 4 as written will investigate three benign
   lines, and — worse for a check whose purpose is to catch silent
   losses — may learn to ignore warning output on that job.
6. **`docs/15` section 8.5 opens "`hw/rtl` is not yet under version
   control"** (`docs/15-pilot-tile-plan.md:940` at `be6ebd9`), which was
   true while wave 2 was in progress and is false in the very commit
   that contains the sentence. It matters because the whole paragraph
   builds on it: it names `tt/MANIFEST.sha256` as *the* anchor for which
   RTL the flow numbers belong to, when the commit hash is now a
   stronger one. Still present in the working tree at 12:59
   (`:1034`) **[fact]**.

All six are stated against `be6ebd9`. Two of them were being repaired
in the working tree while this record closed: by 12:59 local, an
uncommitted revision of `docs/15` had reduced the `tt_um_pilot`
occurrences from fifteen to eight and rewritten the `err_cfg` passage to
record that the connection has been made, and an uncommitted revision of
`docs/11` had reworked the mutation-evidence paragraph **[fact,
`git diff`]**. Neither is committed, so both findings stand against the
reviewed commit; both should be checked off rather than re-raised when
those revisions land. `ROADMAP.md` still carries 113.7 % **[fact,
`grep -c 113.7 ROADMAP.md` returns 1 at 12:59]**.

### 6.5 A harness fragility found while writing this record

`make -C formal everything` is not safe to run concurrently with any
other `sby` invocation in the same `formal/` tree, and it fails in a way
that reads like a verification result.

This record's first attempt at the gate terminated with

```
SBY 12:39:13 [aer_fifo_cover] DONE (ERROR, rc=16)
SBY 12:39:13 The following tasks failed: ['cover']
make: *** [Makefile:27: cover] Error 16
```

after 9 min 45 s **[fact]**. The cause is not a proof failure. The task
had **reached all five cover statements** — `aer_fifo_props.v` lines
161, 162, 163, 164 and 167, each with a witness step recorded in the
summary — and then died writing the fifth trace file:

```
FileNotFoundError: [Errno 2] No such file or directory: 'engine_0/trace4.vcd'
```

At that moment a second process,
`sby -f aer_fifo.sby cover`, was running in the same directory, started
about 40 s earlier by another workstream **[fact, `ps`]**. `sby -f`
force-removes and recreates the task directory, so
`formal/aer_fifo_cover/engine_0/` was deleted out from under the first
run's engine.

Three consequences. First, the gate stops at its first job, so tasks
5..28 never ran and the run says nothing about them. Second, `ERROR
rc=16` is not `FAIL rc=2`, and the distinction is the whole diagnosis —
a reader who sees "the formal gate failed" and does not read the log
will look for a broken proof that does not exist. Third, `docs/11`
already warns about concurrent sby runs against the same task directory,
in prose; this is the first time the failure has been captured with its
message. The fix is a lock or a per-invocation working directory in
`formal/Makefile`, which is integrator-owned (section 10).

The clean re-run, once the competing process had finished, returned 28
of 28 `PASS` in 11 min 58.7 s (section 8) — so the proofs were never in
question. The hazard recurred a second time the same afternoon, while
section 8 was being written: `formal/aer_fifo_prove/status` disappeared
mid-read because a third workstream had started
`sby -f aer_fifo.sby prove` **[fact]**. On a machine where more than one
workstream runs, this is not a rare race; it is the normal case.

### 6.6 Items only the owner can close

Engineering cannot substitute for any of these, and two of them gate
everything else.

| # | Item | Deadline | Blocks |
|---|---|---|---|
| O-1 | Tiny Tapeout account, TTIHP26b slot reserved at 4x2, ~EUR 560 paid | 2026-09-21 | the entire pilot |
| O-2 | Sign or reject `docs/14` section 11 | **2026-08-31** | the public push, and through it precheck and the GDS; also `docs/13` fields D-6/D-7 |
| O-3 | Push to a public repository so the GDS action and precheck run | before 2026-09-21, after O-2 | the manufactured artefact |
| O-4 | Record the 2026-09-07 go/no-go as NO-GO on the SRAM macro | 2026-09-07, answerable now | closes the macro question |
| O-5 | NLnet decisions D-1..D-17, office hour, submission | 2026-08-26 to 2026-10-29 | the application |

O-2 is the tightest and the least reversible. `tt/LICENSE.PENDING.md`
records the state plainly: a Tiny Tapeout submission is a public
repository, and publishing a tree with no `LICENSE` grants nothing to
anyone, which is worse than any of the candidate licences. `docs/14`'s
own hard deadline is 2026-10-15 for the NLnet application; the
2026-08-31 date is the memo's sign-or-reject action, and it is the one
that matters for the shuttle, because O-3 cannot happen before it.

---

## 7. Wave 3, prioritized against the two deadlines

### 7.1 The clocks

| Date | Days from 2026-08-25 | Event |
|---|---|---|
| 2026-08-26 | 1 | NLnet office hour, 16:00 CEST |
| **2026-08-31** | **6** | **`docs/14` sign-or-reject due** |
| 2026-09-03 | 9 | NLnet calls reopen; re-verify the form |
| 2026-09-07 | 13 | SRAM-macro go/no-go (answerable now, negatively) |
| **2026-09-21** | **27** | **TTIHP26b closes** |
| 2026-10-15 | 51 | `docs/14` hard deadline; D-6, D-7, D-14, D-15 close |
| 2026-10-29 | 65 | Target NLnet submission date |
| 2026-11-03 | 70 | NLnet hard deadline, 12:00 CEST |

Capacity, from `docs/06` section B.6.1: about 2-3 h/day, i.e. **~55-80 h
to 2026-09-21** **[estimate]**. The pilot build budget of 49-79 h in
that same section is now largely spent — the design exists, is verified,
and closes to a GDS — so the question for wave 3 is not whether the
pilot can be built but what the remaining capacity should buy.

### 7.2 Owner track — nothing engineering can substitute for

Sequenced, not prioritized: each one blocks the next.

| # | Action | Effort | By |
|---|---|---|---|
| W-1 | Sign or reject `docs/14` section 11 | 1-2 h reading + a decision | 2026-08-31 |
| W-2 | Create the Tiny Tapeout account; reserve a TTIHP26b 4x2 slot; pay ~EUR 560 | 1-2 h | as early as possible, hard stop 2026-09-21 |
| W-3 | Push the repository (or the submission scope) publicly under the W-1 licence and let the GDS action run | 1-2 h, plus action runtime | immediately after W-1 and W-2 |
| W-4 | Read precheck's result and act on it | 2-8 h, unknowable until W-3 | before 2026-09-21 |
| W-5 | Record the SRAM-macro go/no-go as NO-GO, citing `docs/12` section 8 | under 1 h | 2026-09-07, answerable now |
| W-6 | NLnet: office hour (D-12), call reopen re-verification (D-13), then D-1..D-17 on the `docs/13` section 8 schedule | 10-20 h spread over ten weeks | 2026-08-26 to 2026-10-29 |

All effort figures are **[estimate]**. W-4 is the only one whose upper
bound is genuinely unknown, because precheck runs three checks the local
flow has never run (section 2.4); a pin-placement or top-level
uniqueness failure is a same-day fix, a KLayout DRC failure on the
shuttle deck could be worse.

**The critical path to the shuttle runs entirely through the owner
track.** W-1 gates W-3 gates W-4, and W-2 has a fixed close. Engineering
has no item on the critical path, which is the single most important
scheduling fact in this document.

### 7.3 Engineering track, prioritized

Priority 1 is "must land before the shuttle close"; priority 2 is
"before the NLnet package is finalized"; priority 3 is "wave-3 substance
that neither deadline forces".

| # | Item | Why here | Effort |
|---|---|---|---|
| **P1-a** | Correct the 2x2 utilization figure in `ROADMAP.md` to 107.4 % with its arithmetic, and align the pilot sizing paragraph with `docs/15` section 4.3 | An external reader hits the contradiction in the first document they open, and this number is a candidate for the NLnet application (section 5.3) | 1-2 h |
| **P1-b** | Bring `docs/15` to HEAD: retire the `tt_um_pilot` name on all fifteen lines that still carry it, drop the name adapter that no longer exists, mark 8.4 items 1 and 2 as applied, fix the 15/16 test count, and drop the "not yet under version control" premise from 8.5 | Section 6.4 items 2, 3 and 6; the submission document is what a reviewer reads alongside `tt/`. Partly in progress already — see the note at the end of section 6.4 | 2-3 h |
| **P1-c** | Add `docs/16` (if one exists) and `docs/17` to the `README.md` index, and add a test that fails when a `docs/*.md` file is missing from it | Second wave running in which the index has gone stale (`docs/07` F-14 was the first) | 1-2 h |
| **P1-d** | Regenerate `tt/` and re-run `sw/tests/test_tt_submission.py` immediately before the push, and after every `hw/rtl` edit that lands before it | The drift guard is only a guard if it is run; `hw/rtl` was edited three times during this record's measurement window alone | under 1 h per event |
| **P1-e** | Serialize the formal gate: a lock file or a per-invocation working directory in `formal/Makefile` | Section 6.5; the gate currently produces `ERROR rc=16` that reads like a proof failure, on a machine where several workstreams run, and it did so twice in one afternoon | 2-4 h |
| **P1-f** | Correct `docs/11` section 7.4 check 4's expected warning output (three lines for `lif_ctrl`, not zero) | Section 6.4 item 5; a wrong expected output on a vacuity check is worse than no check, because it teaches the reader to ignore the output | under 1 h |
| **P2-a** | Fault-injection campaign on `pilot_top`, modelled on the sibling programme's `docs/27` | `docs/09` target #5 requires the FI campaign and the formal any-state result to agree; only one exists. It is also the strongest single piece of evidence the NLnet application can carry, because it produces a measured SDC rate rather than a promise | 12-20 h |
| **P2-b** | Produce the three NLnet attachments (D-9) | `docs/13` schedules them for 2026-10-20 and names engineering as the owner | 8-16 h |
| **P2-c** | Make the mutation evidence durable: commit the mutant definitions (a patch set or a generator, not seven copies of the RTL) and a script that runs the campaign and writes a tracked summary | Section 6.2; today the primary evidence for section 3.4 does not survive a clone | 4-8 h |
| **P3-a** | A formal job for the pilot integration, starting with the two bindings nothing currently checks: register bank to TMR voter, and the show-ahead adapter to `aer_fifo`'s registered read port | Section 6.1; integration is where every wave-2 defect was found | 16-32 h |
| **P3-b** | Extend the mutation campaign to `npu_regbank` (the `REGBANK_SRC` override already exists) and use it to close section 3.3's open question by mutating `f_spec_locked` and `f_spec_en_bad` | Turns section 3.3's "the tree does not prove these were live defects" into a measurement | 8-16 h |
| **P3-c** | A third `secded` task with `opt` suppressed, so C1 and C2 are seen by both engine families | Section 4; closes the one named hole in the engine-diversity argument | 2-4 h |
| **P3-d** | `TIMING_VIOLATION_CORNERS` override, `MAX_FANOUT_CONSTRAINT` and a re-run | `docs/12` 10.2 item 6 and `docs/15` 5.3; neither is a blocker and both are cheap | 3-6 h |
| **P3-e** | Second simulator (Verilator or nvc) on at least the `secded`, `tmr_voter` and `aer_fifo` suites | ROADMAP P1 asks for two simulators "where feasible"; these three are the feasible ones | 8-16 h |

All effort figures are **[estimate]**, derived from the sibling
programme's comparable items where one exists (P2-a from a 512-line
harness that already works; P2-b from `docs/13`'s own scoping) and
judged otherwise.

**Two of these were already in flight while this record was being
written**, and a reader comparing the plan against the working tree
should know it. By 12:47 local the tree carried untracked
`hw/rtl/scrub.v`, `formal/scrub.sby`, `formal/scrub_props.v` and nine
`formal/scrub_*` task directories — a scrub controller with its own
proof, which is the first new RTL for `docs/09` target #5's list — and
untracked `hw/tb/Makefile.fi` and `hw/tb/test_fi_campaign.py`, which is
P2-a **[fact, `git status`]**. None of it is committed, none of it is
wired into `make -C formal everything` (`formal/Makefile` is unmodified,
so the gate is still 28 tasks), and none of it is reviewed. It is listed
here as work in progress, not as a delivery; the acceptance rule of
section 3.2 applies to it like everything else.

### 7.4 Roll-up, and what does not fit

| Band | Items | Effort |
|---|---|---|
| Priority 1, before 2026-09-21 | P1-a .. P1-f | **8-13 h** |
| Priority 2, before the NLnet package | P2-a .. P2-c | **24-44 h** |
| Priority 3, wave-3 substance | P3-a .. P3-e | **37-74 h** |
| Owner track | W-1 .. W-6 | **16-35 h** |

Against ~55-80 h of engineering capacity to 2026-09-21, priority 1 fits
comfortably and leaves 42-72 h. Priority 2 fits inside that if the
owner track does not consume it, and the owner track is where the
uncertainty is: W-4 alone could take 8 h at short notice. The
recommendation is therefore to treat **priority 1 plus P2-a as the
wave-3 scope to the shuttle close**, hold P2-b for the October window
where `docs/13` already schedules it, and let priority 3 run after the
shuttle.

Two things explicitly do not fit and should not be attempted before
2026-09-21:

- **Reopening the SRAM macro.** `docs/06` B.6.1 budgets 65-125 h for the
  macro variant and `docs/12` has already returned a definitive negative
  under conditions easier than the gate asks for. Spending the remaining
  capacity on an upstream PDK defect would consume the pilot's slack and
  still not guarantee a signoff-clean GDS.
- **Any of `docs/09` targets #3, #7, #8, #9, #10.** All are blocked on
  RTL that does not exist, and writing the RTL to unblock them is P3
  work at the SoC scale (`ROADMAP.md` P3, ~1015-1895 h), not wave-3 work.

### 7.5 What wave 3 should not claim

For the avoidance of the failure mode this project has already
demonstrated it is prone to: at the end of wave 3, with everything above
delivered, the honest statements will still be that the formal programme
has closed four of eleven targets, that the pilot integration is
verified by simulation and fault injection rather than proof, that no
silicon exists, and that every radiation statement remains a positioning
statement about a fault-tolerant architecture for a LEO mission profile
and not a measured result. Wave 2's review record exists partly because
overstated claims get caught here; the same applies to wave 3's.

---

## 8. Baseline re-run at the close of this record

Run to confirm the repository still holds. The tree state is stated with
each result, because another workstream was editing `hw/tb/test_pilot_top.py`,
`regmap/regmap.yaml`, `sw/golden/secded.py` and `docs/regmap-npu.md`
throughout this session and had added untracked `hw/rtl/scrub.v`,
`formal/scrub*` and `hw/tb/test_fi_campaign.py`.

| Gate step | Command | Result |
|---|---|---|
| Register map | `.venv/bin/python regmap/generate.py --check` | **exit 0, no output**, both at 12:29 against a tree identical to `be6ebd9` and at 12:47 with `regmap/regmap.yaml` modified **[fact]** |
| Golden model | `.venv/bin/python -m pytest -q` | **145 passed** at 12:29 (0.44 s) and **145 passed** at 12:47 (0.30 s) **[fact]** |
| cocotb, six suites, nine invocations | the `docs/11` section 8.2 command list | 108 distinct tests, 215 executions, 200 pass, 0 fail, 15 structural skips; every driver exit 0 **[fact, 12:29:45-12:31:44, tree identical to `be6ebd9`]** |
| Formal gate | `make -C formal everything` | **28 `DONE (PASS, rc=0)`, no `DONE` line of any other kind, exit 0, 11 min 58.7 s wall** **[fact, 12:43:44-12:55:43]** |

The formal gate needed two attempts and the first failure is a finding
rather than a result. It died at 12:39:13 with `ERROR rc=16` after
`aer_fifo_cover` had reached all five of its cover statements, because a
second `sby -f aer_fifo.sby cover` started by another workstream
recreated the task directory underneath it (section 6.5). The re-run was
queued behind the competing process and is the row above.

Per-task verification of that run, read from the task directories rather
than from the console **[fact]**:

- **28 of 28 tasks report `PASS` with retcode 0.** All four `prove`
  tasks that should be inductions end their `PASS` file with
  `successful proof by k-induction.`
- **Assert counts reproduce `docs/11` section 8.3 exactly**: `aer_fifo`
  21, `npu_regbank` 251, `lif_ctrl` 64 (66 in `bmc_live`), `secded` 23,
  `tmr_voter` 15 at WIDTH 8 and 8 / 39 at WIDTH 1 / 32 — which is the
  `WIDTH + 7` signature that confirms the `chparam` overrides took
  effect. Total 374 at default parameters.
- **Every cover obligation is reached**: `aer_fifo` 5 of 5,
  `npu_regbank` 31 of 31, `lif_ctrl` 15 of 15 plus 2 of 2 in
  `cover_safe`, `secded` 9 of 9, `tmr_voter` 7 of 7 and 6 of 6 at
  WIDTH 1. Total 67 at default parameters.
- **The two AIGER tasks behave as `docs/11` section 7.4 predicts**:
  their JUnit files hold no per-property testcases, and the engine's own
  structural line reads `PI/PO/Reg = 25/15/25` for the voter and
  `137/21/137` for the codec — 15 assert outputs against the SMT path's
  15, and 21 against the SMT path's 23. The two-assertion gap of
  section 4 is still there.
- **Ten of the 28 tasks write `PASS 0 0`** — all eight `tmr_voter`
  tasks plus `secded_cover` and `lif_ctrl_cover_safe` — while
  `aer_fifo_bmc` writes `PASS 0 395`, i.e. 395 seconds of child CPU
  **[fact, read from the `status` files of this run]**. That is section
  4's argument reproduced end to end inside a single gate: the most
  expensive task in the run is the bounded one, and the free ones are
  the exhaustive ones.

One expected-output statement in `docs/11` did not reproduce, and it is
a check rather than a claim, so it matters. `docs/11` section 7.4 check
4 says the `aer_fifo` tasks each emit exactly one benign
memory-flattening warning and that "the `npu_regbank`, `lif_ctrl`,
`secded` and `tmr_voter` tasks emit none at all". Measured on this run,
`lif_ctrl_prove` emits **three**, of exactly the same benign class
**[fact]**:

```
Warning: Replacing memory \rmem with list of registers. See lif_core.v:362
Warning: Replacing memory \vmem with list of registers. See lif_core.v:361
Warning: Replacing memory \wmem with list of registers. See lif_core.v:348
```

`npu_regbank`, `secded` and `tmr_voter` emit none, as stated. The three
are Yosys reporting that `lif_core`'s three memory arrays were flattened
into flops for the solver, which is the same thing the `aer_fifo` line
reports and is not a defect — but a reader following check 4 as written
will treat them as anomalies. Corrected expected output: **one** warning
per `aer_fifo` task, **three** per `lif_ctrl` task, none elsewhere.
Recorded as a `docs/11` erratum in section 6.4.

**A reproduction note, learned the hard way.** Re-run
`make -C formal everything` on a machine with no other `sby` running and
expect 28 `DONE (PASS, rc=0)` lines and exit 0 in roughly 12-14 minutes;
`docs/11` section 8.3 records two such runs at 11 min 34 s and
13 min 60 s, and this one took 11 min 58.7 s. If it does not reproduce,
check `ps` for a second `sby` before checking the proofs. As this
section was being written, a third workstream started
`sby -f aer_fifo.sby prove` and `formal/aer_fifo_prove/status` vanished
mid-read **[fact]** — the same hazard, a second time, inside one
afternoon.

---

## 9. Verdict

Wave 2 is sound and the evidence behind it is real. Six RTL blocks and
an integration exist; 145 Python tests, 108 cocotb tests and 28 formal
tasks stand behind them, and all three suites were re-run for this
record and came back green — 145 passed, 215 cocotb executions with 0
failures, and 28 of 28 formal tasks `PASS` with every one of the 67
cover obligations reached. One block has a DRC/LVS-clean `sg13g2`
sign-off and the pilot itself closes to a GDS at 4x2 with zero DRC, zero
LVS and zero timing violations on three corners; and a validated Tiny
Tapeout submission tree exists at that shape. Every number in section 2
was reproduced rather than copied.

The review method is the part worth keeping. Requiring a repair to be
accepted only when the corresponding test or proof is shown to fail
against the reintroduced defect is what turned "covered by lockstep
against a golden model" from a coverage-table entry into a measured
falsehood, and what caught two properties that had been written from the
RTL and could therefore never have failed. Neither result was available
to review-by-reading, and both were cheap once the mutation override
existed.

Three things a skeptical reader should hold against wave 2. The formal
programme closes four of eleven targets and is blocked on absent RTL for
four more, which is a reasonable position that does not sound like
"formal green". The pilot integration — where every defect wave 2 found
actually lived — has no proof and no fault-injection campaign. And the
repository's own numbers disagree with each other in two checkable
places: `ROADMAP.md`'s 113.7 % against `docs/15`'s 107.4 %, and
`docs/11`'s expected warning output for `lif_ctrl`. Both are short
fixes, and both are the sort of thing that gets quoted outward before it
gets corrected.

Verdict: **wave 2 is a sound base for wave 3, and the binding constraint
on the shuttle is not engineering.** The critical path to 2026-09-21
runs through the licensing sign-off due 2026-08-31, the Tiny Tapeout
account and payment, and the public push that lets precheck run — none
of which engineering can do. The engineering work that must land before
the close totals 8-13 hours.

---

## 10. Notes for the owners of files this record does not own

This record owns only `docs/17-wave2-review-record.md`. Six changes it
would otherwise have made, with the file and the reason:

1. **`ROADMAP.md`, section P1** — replace "113.7 percent utilization in
   4 tiles" with 107.4 %, showing the arithmetic
   (136,107 um2 placed / 126,685 um2 of 2x2 placement rows) and citing
   `docs/15` section 4.3; align the glue-area sentence with `docs/15`
   section 4.4's 61,940 um2 or state that its 61,733 um2 is
   `pilot_top`-based rather than wrapper-based. Section 5.3.
2. **`README.md`** — add `docs/17-wave2-review-record.md` to the
   document index, and consider a test that fails when a `docs/*.md`
   file is absent from it; this is the second wave in which the index
   has gone stale (`docs/07` F-14 was the first).
3. **`formal/Makefile`** — serialize the gate. A lock file around
   `everything`, or a per-invocation working directory, so that a
   concurrent `sby -f` in the same tree cannot delete a running task's
   directory and produce `ERROR rc=16`. Section 6.5 has the captured
   failure.
4. **`docs/15`** (owned by the pilot workstream) — fifteen lines still
   name `tt_um_pilot`, and both the file `hw/rtl/tt_um_pilot.v` and the
   generated name adapter they describe are gone at HEAD; section 8.4's
   two "changes needed" have both been applied and should be marked as
   such rather than deleted, per this repository's habit of keeping the
   trail visible; section 8.5's `test_tt_submission.py` count is 15 and
   should be 16, and its "`hw/rtl` is not yet under version control"
   premise is false in the commit that carries it. Section 6.4. An
   uncommitted revision addressing most of this was in the working tree
   at 12:59.
5. **`docs/11` section 7.4, check 4** — the expected warning output is
   wrong for `lif_ctrl`: it emits three benign memory-flattening lines,
   not zero. Corrected expected output is in section 8 of this record.
   This is the highest-value of the six because it degrades a check
   whose whole purpose is to notice when something has been silently
   optimized away.
6. **`.gitignore`** — `hw/tb/results_*.xml` currently excludes the
   mutation evidence that `docs/11` section 1.1 and section 3.4 of this
   record both cite as primary. Either commit a tracked summary of the
   campaign or keep the mutant definitions in the tree; the current
   state is a citation to a file a fresh clone does not have.
   Section 6.2.
