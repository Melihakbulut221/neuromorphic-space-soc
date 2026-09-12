<!--
SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
SPDX-License-Identifier: CC-BY-4.0
-->

# 81 — What nothing was running: three green suites, a sign-off of a design that had moved, and a checker counting the wrong thing

Convention, as everywhere here: **[fact]** = measured in this
environment or read out of a file in the working tree; **[estimate]** =
derived or judged; **[planned]** = an intention with a date and no
artifact behind it.

An audit sweep on 2026-09-11 worked through a ranked list of what a
ten-agent batch had left open. Most of it was ordinary: an exception to
retire, a stale figure to re-measure, a guard to widen or narrow. Four
items were not, and they share a shape this corpus has now hit often
enough to name.

**Every one of the four was green.** Not red and ignored — green,
reported as passing, and quoted in a document. What was wrong in each
case was that the green covered less than the sentence resting on it.

---

## 1. Three cocotb suites that nothing ran

`scripts/run_cocotb.sh` opens by claiming it runs *every cocotb suite in
the repository*. On 2026-09-11 it ran neither of these **[fact]**:

| Suite | Tests | Why it was invisible |
|---|---:|---|
| `hw/tb/test_aer_fifo.py` | 20 | its makefile is named `Makefile`, and the discovery glob is `Makefile.*` — a name with no dot in it does not match |
| `hw/soc/tb/cocotb/test_soc_npu_defects.py` | 4 | `Makefile.soc_npu`'s default `MODULE` is `test_soc_npu`; this one is reached only by typing `MODULE=` by hand |
| `hw/soc/tb/cocotb/test_soc_wdog_strap.py` | 3 | same, under `Makefile.soc_wdog` |

The first is the AER event FIFO — the block ROADMAP gate G0 signs off
on, and the one whose pointers are triplicated. The other two were each
written to **fail against the RTL as it was before a fix** and pass
against the RTL as it is. That is the strongest regression evidence the
batch produced, and an edit re-opening either defect would have passed
every check in the tree.

The runner's own `tt/test` block, added 2026-09-10, describes exactly
this failure for `tt/`'s plain `Makefile` and fixes it there. The same
sentence was true of `hw/tb/Makefile`, four lines above, and was not
noticed **[fact]**.

**What was added is not the three fixes.** Those are two lines and a
table. What was added is a **completeness check**: every `test_*.py` in
the two testbench directories must be some makefile's default `MODULE`,
or named in the runner's `EXTRA_MODULES` table, or listed in
`SKIP_MODULES` with a reason. Anything else is an error in the runner,
at the moment the file is added, rather than a suite that quietly never
runs. A fourth orphan is now loud.

One consequence worth stating, because it is the same defect in
miniature: the first version of the fix ran the extra modules through a
`printf | while read` loop. That is a subshell, so `run_one`'s
`pass_total` and `suite_fail` increments were lost with it — the suites
would have run, printed their lines, and contributed nothing to the
totals or the exit code. It is a here-string now, with the reason
written where the loop is.

---

## 2. The sign-off run was a sign-off of a different design

ROADMAP gate G0 read, from 2026-08-25:

> **Met 2026-08-25** by run `trial-03-signoff` on `aer_fifo`: all 80
> flow stages completed in 680 s with Magic DRC 0, KLayout DRC 0, Netgen
> LVS 0 on all seven counters, XOR 0, antenna 0 nets and 0 pins after
> detailed routing, 0 disconnected pins, 0 power-grid violations, and 0
> setup, hold, max-slew and max-cap violations across all three corners.

Every number in it is correct **[fact]**. Two things were nevertheless
wrong with the sentence, and neither is visible from the numbers.

**The design moved on 2026-08-29.** Commit `c5a5a6e` replicated the AER
queue pointers.

> *Corrected 2026-09-12: this named `b6738e5` and dated it six days after
> `trial-03-signoff`. `b6738e5` is the pilot FREEZE commit of 2026-08-31,
> which `docs/34` pins and which changed no logic; the replication is
> `c5a5a6e`, "Replicate the AER queue pointers, and record what is not yet
> proved", 2026-08-29. Four days after the sign-off run, not six. The
> error came from reading the freeze commit as the change it froze, and it
> reached four documents before an audit caught it in the fifth.*
 `trial-03-signoff` hardened a block with **1,071**
flip-flops; the block has **1,164**, and the 93 of difference are the
three replica banks the entire hardening argument is about. A sign-off
of a block without its redundancy is a sign-off of a different block.

**Three of its four corner checkers were bound to nothing.**
`hw/openlane/checker_audit.py` on that run tree calls
`Checker.SetupViolations` PARTIAL — *"matches 1 of 3 measured corners;
unchecked: nom_fast_1p32V_m40C, nom_slow_1p08V_125C"* — and
`Checker.MaxCapViolations` and `Checker.MaxSlewViolations` NO-GATE. All
three metrics read 0 at all three corners on that run, so **nothing was
hidden**. What was missing is any mechanism that would have stopped the
run had something been there. G0's sentence was quoting the gates.

### 2.1 And for thirteen days no re-harden was possible

The obvious close — re-run the trial — failed, and how it failed is the
part worth keeping.

```
9 Unmapped Yosys instances found.
```

Nothing was unmapped. `hw/rtl/aer_fifo.v`'s replication defence is
`keep_hierarchy` on twelve bank instances plus the POL+MIX storage
transform, and under `SYNTH_HIERARCHY_MODE: flatten` yosys honours the
attribute — the log says `Keeping aer_fifo.u_wptr_a (found
keep_hierarchy attribute)` nine times — so nine `$paramod` submodule
types survive into `stat.json`. LibreLane then counts them:

```python
safe = ["$assert"]
unmapped_cells = [cells[y] for y in cells.keys()
                  if y not in safe and y.startswith("$")]
metric_updates["design__instance_unmapped__count"] = sum(unmapped_cells)
```

*(`librelane/steps/pyosys.py`, v3.0.5.)* Every cell type whose name
begins with `$`. A parameterised user module is counted the same as a
`$_AND_` that failed to map. Inside those nine, every cell is an sg13g2
cell **[fact]**.

`SYNTH_HIERARCHY_MODE: deferred_flatten` is the answer and it was
already in the repository three times over: `hw/openlane/pilot_ihp`,
`hw/openlane/pilot_sky130` and `tt/src` all carry it, and
`pilot_sky130`'s comment states this failure mode verbatim —
*"a plain flatten leaves `$paramod` module types that
Checker.YosysUnmappedCells counts as unmapped instances and aborts on"*.
`hw/openlane/aer_fifo` was the one that did not carry it, and the gap
was invisible because **nothing re-ran that config**. The block's own
sign-off configuration could not build the block's own RTL for eleven
days.

### 2.2 What replaced it

Run `g0gates2`, 2026-09-11, on the RTL as it stands, with all four
corner checkers live **[fact]**:

| | `trial-03-signoff` | `g0gates2` |
|---|---:|---:|
| Flip-flops | 1,071 | **1,164** |
| Magic DRC / KLayout DRC / XOR / LVS | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |
| Setup / hold / max-slew / max-cap | 0 | 0 |
| ...corners each was **checked** at | 1 / 3 / 0 / 0 | **3 / 3 / 3 / 3** |
| In-flow checkers gating fully | not measured | **17 of 19** |
| Setup worst slack, slow corner | 18.0553 ns | 11.0738 ns |

The 7 ns of setup slack is what triplicating a pointer and voting it
costs at a 30 ns clock. Against the 50 MHz Tiny Tapeout envelope the
slow-corner headroom goes, **on either basis and stated on both because
the first version of this sentence mixed them**:

| | `trial-03-signoff` | `g0gates2` |
|---|---:|---:|
| slow-corner setup WNS at 30 ns | 18.0553 ns | 11.0738 ns |
| launch-to-capture path | 11.9447 ns | 18.9262 ns |
| as a frequency | 83.72 MHz | 52.84 MHz |
| margin on the 20 ns PERIOD | 40.28 % | **5.37 %** |
| headroom on the 50 MHz FREQUENCY | 67.44 % | **5.67 %** |

*Corrected 2026-09-12. This read "from about 40 % to **5.6 %**", which
took the old end off the period basis and the new end off the frequency
basis. The two happen to be close for `g0gates2` -- 5.37 against 5.67 --
and far apart for `trial-03-signoff`, 40.28 against 67.44, so the pair
as written overstated the fall. Like for like it is 40.28 % to 5.37 %,
or 67.44 % to 5.67 %. The conclusion does not move and that is why the
error survived a reading: the part still clears 50 MHz, and the margin
is still thin enough to be worth a number rather than the word
"clears".* `docs/12` section 4 is the full record and
section 4.7a keeps `trial-03-signoff` beside it, per `docs/64`.

The two checkers that do not gate are `Checker.LintWarnings` (1 warning;
`ERROR_ON_LINTER_WARNINGS` is False by default) and
`Checker.WireLength` (no threshold set, so it warns only).

---

## 3. A digest that pins nothing, reported as VERIFIED

`docs/80`'s manifest pins 329 artefacts by SHA-256 and `--check`
reported **329 verified, 0 changed** **[fact, 2026-09-10]**. Five of
those rows are zero-byte files:

```
formal/eqy/out/secded_dec.pass
formal/eqy/out/secded_enc.pass
formal/eqy/out/tmr_voter.pass
formal/eqy/out/secded_dec_mutant.failed
formal/eqy/out/voter_mutant.failed
```

They are `eqy` stamp files: the verdict is in the **name**, and the
content is nothing. All five therefore carry the same digest —
`e3b0c442…`, the SHA-256 of the empty string — so the digest column
distinguishes a `.pass` from a `.failed` not at all, and swapping one
empty artefact for another is invisible to the instrument whose whole
purpose is to catch a swap.

Nothing is actually lost here: the five `.log` files beside them **are**
pinned, and each carries `DONE (PASS, rc=0)` or `DONE (FAIL, rc=2)` in
its text. The defect is in the report, not the coverage. `--check` now
counts them apart:

```
324 verified, 5 vacuous, 0 missing, 0 changed, 0 extractor-drift, of 329 pinned
```

and prints, for each, that the row shows the file existed under that
name and the digest column shows nothing. Exit code is unchanged: an
empty stamp file is legitimately empty, and this is a reporting
distinction, not a failure.

The same pass fixed a second thing in the manifest's own header, which
had hard-coded *"the whole set is 1.9 GB"* into a file that now covers
**5.163 GB** — a stale number published inside the artefact whose job is
to prevent stale evidence. The header line is computed from the rows on
every `--write` now, in decimal, because `docs/80` counts in decimal.

---

## 4. One byte in eight, on the oldest peripheral

`hw/soc/rtl/soc_uart.v` has one holding register and two branches of one
`always` block that both assign `thr_full`. The register-write branch
came first, so on the one system clock in `8*(SCALER+1)` where a DATA
write lands in the same cycle as the serialiser's load, Verilog's
last-assignment-wins gave the flag to the loader:

```verilog
thr      <= pwdata      // the new byte is stored
thr_full <= 1'b1        // ... and then
thr_full <= 1'b0        // the loader clears it in the same cycle
```

The frame that goes out is correct. The byte just written sits in a
register nothing will ever load, and STATUS reports the write accepted
on the way out, because TF reads `thr_full` and `thr_full` is now clear.

`hw/soc/tb/cocotb/test_soc_uart_defects.py` walks a second blind write
across all eight phases of the bit boundary at SCALER = 0. On the RTL as
it was, **phase 3 of 8** put `0xAA` on the line and nothing after it;
the other seven phases produced one of the two correct outcomes
**[fact]**:

```
Phase -> frames on the line:
  {0: [0x55], 1: [0x55], 2: [0x55], 3: [0xAA],
   4: [0xAA, 0x55], 5: [0xAA, 0x55], 6: [0xAA, 0x55], 7: [0xAA, 0x55]}
```

`[0x55]` alone is the documented overwrite of a full holding register,
which GRLIB's part also does. `[0xAA, 0x55]` is both bytes. `[0xAA]` is
the defect. The property that separates them, and the one the test
asserts, is **the last byte written is always the last byte
transmitted**: a driver may lose an earlier byte to a documented
overwrite; it may never lose its most recent one to a race.

The fix is the order — the register-write block moved after the
serialiser, so the write's `thr_full <= 1'b1` is the last assignment.
The same cycle sends the old byte and keeps the new one.

**Why it survived to 2026-09-11.** All five programs in `hw/soc/tb/sw`
poll TE before writing, and a polling driver cannot reach the window:
TE high means the holding register is empty, so the loader has nothing
to take. `tb_soc.v` decodes the console output of exactly those
programs. The suite's third test drives a polling writer over the same
eight phases and loses nothing on either version of the RTL — it is the
control that explains the silence, and it is why it is in the file.

### 4.1 The test had this defect too, first

The first version of the frame collector called `recv_byte` in a loop
and caught `AssertionError` to mean "no more frames". `recv_byte`
asserts the line is idle when it is called — which is right for it, and
`test_soc_uart.py` records what reading a frame from three clocks in
costs. But the loop could not tell *"no more frames"* from *"the frame
had already started before I looked"*: both arrive as the same
exception. It read the second as the first and reported five phases of
eight as a swallowed byte on a transmitter that was sending correctly.

It is a background monitor now, started before anything is written, so
it never misses a start bit and never has to guess. The general form is
`docs/64`'s: **TIMEOUT, KILLED and ERROR are three different words**,
and so are "nothing came" and "I arrived late".

---

## 4a. A gate that could never be green

`scripts/verify.sh` writes the row in `verification-log.tsv` and exits
non-zero when anything is wrong. On 2026-09-11 it exited non-zero on a
tree where nothing was wrong, and had done since 2026-09-09 **[fact]**:

```
509 passed, 0 failed   462 cocotb, 0 failed   425 formal pass, 35 other
rc=1
```

The 35 are every non-PASS formal task directory, and all 35 are under
`hw/soc/out/rvf*` — the vendored Ibex `riscv-formal` runs. Not one is in
this project's own property sets, which are **54 PASS in `formal/` and
64 PASS in `hw/soc/formal/` with nothing else**. Each of the 35 already
had a written decision behind it in `docs/63`: four are riscv-formal's
own model computing an unsigned division and remainder where Ibex is
right (section 7.5); two are a depth bound, not a defect (section 8.3);
sixteen are multiply and divide checks stopped after 35 to 40 minutes
each because bit-blasting a 32x32 multiplier is the classic hard case
(section 8.4); thirteen are the register check and its six-engine
timeout sweep, where the non-verdict **is** the measurement (sections
17.2 and 18).

`verify.sh`'s own header refused to fix this the easy way, and was
right to:

> Nothing here whitelists the known-and-explained failures of `docs/63`,
> because an allowlist maintained inside a counter is how a counter
> starts lying, and this file exists because of one that did. If the
> project wants a green gate it has to first decide, in a tracked
> artefact, which of the thirty-five are expected — and that is a
> decision about the formal work, not about this script.

`formal-dispositions.tsv` is that artefact: 35 rows, each naming the
directory, its expected verdict word, the `docs/63` section that decided
it and the date. **It changes no count.** `formal_other` in the log is
still 35 and always will be. What it adds is `formal_undispositioned`,
and that is what the exit code now reads — so a new red turns the gate
red on the run it appears, while the 35 stay counted, stay printed on
stderr and stay amber.

Three ways it fails, all exercised:

| Mutation | Result |
|---|---|
| a row deleted | that directory is undispositioned, `rc=1` |
| a row's verdict word changed (`FAIL` → `STOPPED`) | drift reported, `rc=1` |
| a row naming a directory that now PASSES | hole reported, `rc=1` |
| unmutated | `rc=0` |

And the case that would have made it useless: on a machine with no run
trees — which is every clone, because these paths are all git-ignored —
it reports zero of everything and exits **0**. A disposition whose
directory is absent is MISSING, not a hole, which is `docs/80` section
3's distinction reused.

The last piece is that any of this runs at all. `verify.sh --dispositions`
does the formal scan alone in about a second, because the full run
re-runs pytest and cocotb first and takes twenty minutes — nobody edits
a 35-row table three times under that, so in practice the drift and hole
checks would never have been exercised, and an unexercised guard is the
subject of this whole document. `scripts/ci_local.sh checkers` runs it.

---

## 5. What ties them together

Each of the four is the same sentence with different nouns: **a green
result read wider than what it looked at.**

- A runner that says "every cocotb suite" and globs `Makefile.*`.
- A gate that says "0 violations across all three corners" where three
  of four checkers were bound to one corner or none.
- A manifest that says "verified" over the digest of emptiness.
- A `STATUS` register that says a write was accepted when the byte is
  gone.
- And one that fails the other way: a gate that exited non-zero on a
  clean tree, every day, so its exit code carried no information at all.
  A check that can never be green is as empty as one that can never be
  red.

None of them was a lie and none was a bug in the usual sense. In each
case an instrument reported truly about a smaller thing than the
sentence quoting it described, and nothing in the tree connected the two.

The corresponding repairs are not the four fixes, which are small. They
are the four checks that make the *scope* mechanical: the runner's
completeness check, `checker_audit.py` wired into `ci_local.sh`,
`--check`'s VACUOUS class, and a test that asserts a property rather
than an outcome. `docs/64`'s rule covers the other half — a superseded
measurement is left standing with a date, never rewritten — and
`docs/12` section 4.7a is this document's largest application of it.

## 6. What this does not cover

- **The three unreached suites were green, and that is luck.** Nothing
  here establishes that they were green on every commit since they were
  written; only that they are green now and will be run from now on.
- **`g0gates2` is one run.** It is not a re-measurement of `docs/12`
  sections 5 through 12, which still rest on `trial-03-signoff` and on
  the standard-cell library rather than on the design.
- **`checker_audit.py` reads a run tree**, so it says what gated on a
  run that happened. It cannot say what would gate on a run that has not
  been made, and it is not a substitute for the config keys being right.
- **The UART sweep is one scaler value.** It shows the window exists at
  SCALER = 0 and is closed there; the window's width is
  `1/(8*(SCALER+1))` of the stream by construction and that is an
  argument, not a measurement.
- **The five vacuous rows are still pinned.** Their paths are evidence
  that the stamp existed; nothing here makes the digest column say more
  about them than it can.
- **No campaign, deck or layout in this repository was re-run because of
  section 1.** The three suites' results are simulation, and everything
  physical still rests on the run trees `docs/80` pins.
