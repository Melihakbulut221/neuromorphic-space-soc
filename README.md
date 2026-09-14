# Neuromorphic Space SoC

A fault-tolerant system-on-chip for on-board AI inference in small-satellite
missions, implemented on a 130 nm technology with an open-source RTL-to-GDS
flow. The architecture class follows the Frontgrade Gaisler GR801 (public
product brief, April 2026): a RISC-V management processor, an event-driven
neuromorphic inference engine, on-chip SRAM, and a set of spacecraft
interfaces — retargeted from STM 28 nm FDSOI to a 130 nm node at a scale
that is realistic for an open PDK and a small team.

## Reference architecture (GR801, public brief)

| Block | GR801 (28 nm FDSOI) | This project (130 nm, targets under study) |
|---|---|---|
| Management CPU | NOEL-V FT, RV64GC single core | RV32 core, selection in research phase |
| AI engine | Akida 1.0, 8 nodes x 4 engines, 1/2/4-bit weights | Event-driven SNN fabric, sizing in research phase |
| On-chip RAM | 8 MB shared + 3.2 MB Akida-private | Hundreds of kB class, ECC-protected |
| External memory | QSPI controller, 2 chip selects | QSPI controller |
| Interfaces | PCIe Gen3 x4, SpaceWire router 4x, GbE, CAN FD 2x, SPI, 2x I2C, 3x UART, CPI, 16 GPIO | Subset: SpaceWire codec, CAN, SPI, I2C, UART, GPIO, optional 8-bit CPI; PCIe/GbE out of scope |
| Hardening | ECC on CPU/memories, fault detection on Akida memories | Layered: control TMR, memory ECC + scrub, fault counters |

## Status

**The pilot is frozen and signed off; the SoC around it is not built.**
Read `docs/00-index.md` for the full what-exists-and-what-does-not, and
`ROADMAP.md` for the plan. In short, as of 2026-09-03:

*Exists, and is verified.* An event-driven LIF inference core, its AER
event queues, a register bank generated from a single-source map, a
SECDED codec, a TMR voter and a scrub controller — ~~6,856 lines of
Verilog~~ **6,883 lines of Verilog** (`wc -l hw/rtl/*.v`, nine files;
7,011 with the generated `npu_regs.vh` header). Verification is
**166 cocotb tests** (`grep -c '@cocotb.test' hw/tb/test_*.py`, ten
modules, which is also `docs/34` section 7's figure), **54 SymbiYosys
proof tasks** (`make -C formal -n everything | grep -c "sby -f"`, which
is `docs/35` section 5's 54 of 54 DONE/PASS), a seeded fault-injection
campaign of **378 upsets** classified against the golden model
(`docs/16`'s headline table, the committed log re-taken at the freeze
commit `b6738e5`), and a gate-level run in which **370 of 370**
comparable injections classify identically to RTL (`docs/32` section
5.1). `docs/34-pilot-freeze.md` pins the whole artifact set by hash.

*Re-counted 2026-09-10, and one of those numerals was carrying a claim
it cannot support.* This paragraph said **234 Python tests**, and no
document in the corpus says 234 — the freeze measured 231 and the suite
has grown with every SoC block and every document since, because
`sw/tests/test_doc_links.py` parametrises one case per document.
`.venv/bin/python -m pytest --collect-only -q` collects **503** at the
repository root today. That is a count of the *whole* tree and not of
the pilot, so the pilot figure is dropped rather than refreshed: there
is no command that returns a pilot-only Python count, and a number with
no command behind it is what this paragraph had. The line count moved
too, 6,856 to 6,883, and 6,856 appears nowhere else either. The other
four reproduce, to the digit, from the commands printed beside them.

*Manufacturable, on every check an open flow can run.* The 6x2 pilot
signs off on IHP SG13G2 with Magic DRC, KLayout DRC, XOR, all four
Netgen LVS unmatched counters, antenna, power grid and illegal overlap
at zero,
setup and hold clean on three corners with a real 5 percent derate, and
the Tiny Tapeout precheck at 10 of 10. No silicon exists and the hosted
GDS action has not run.

*Exists, and is unhardened.* A management subsystem, begun after the
pilot froze and kept strictly separate from it. Ibex (`small-pmp`:
RV32IMC, PMP, no lockstep) is brought up through sv2v on the pinned
toolchain and runs a self-checking bare-metal program; a memory map
frozen as a single generated source; and a fabric that speaks Ibex's own
protocol internally with real AMBA 3 APB at the peripheral boundary,
proved compliant by k-induction. The bring-up program runs end to end
out of boot ROM through that fabric with the console decoded off a real
serial line. `docs/38` and `docs/39` are the records.

It now also has interrupts, timers and a watchdog: a RISC-V CLINT on the
system bus, a GRLIB-style GPTIMER on the peripheral bus, and a watchdog
that escalates through a non-maskable interrupt to a system reset to an
external pin, cannot be disabled or slowed by the software it watches,
and keeps its record through the reset it causes. A timer interrupt is
taken and returned from on the real fabric; the whole escalation ladder
runs end to end across three boots of the SoC in one simulation.
`docs/40` is the record, and it argues the decision *not* to build a
platform interrupt controller rather than assuming it.

The watchdog's own state is now triplicated in the netlist, and
`docs/41` is the record — with the limit `docs/79` later measured: the
three replicas are **not placement-separated**, so this is a netlist
property and not yet a property of a part.
The eight fields nothing rewrites — the bootstrap latch, the stage-1
pending flag, the reset record and count, the reset stretch — are
bundled into one word and tripled under the pilot's own proved voter,
because six of them are single bits and three replicas cannot be held
apart over one bit. The counter, the reload and the prescaler are
deliberately left as single points, and the price of that is measured
rather than argued. It costs 1.85 % of the Ibex core, it is counted in
the mapped netlist rather than assumed to have survived synthesis, and
162 fault injections into the block's own flip-flops classify every
upset in the protected word as corrected — against a counterfactual run
on the unprotected block where two single-bit upsets left the watchdog
silently disarmed.

The management core has now been measured, and `docs/42` is the record:
1,300 stratified single-bit upsets into Ibex running the whole SoC, each
one run twice — once with the watchdog armed and once with its bootstrap
pin held high — because "the watchdog escalated" is not a catch rate
until the same upset on the same machine with no backstop says whether
the machine was in fact dead. Design-weighted silent corruption is
2.8 % ± 1.6; the watchdog catches 91.7 % of the upsets that leave the
core dead, with zero spurious escalations. Two findings decided what to
do next: 45 % of the core's flip-flops are the architectural register
file and they carry most of the rate, and a corrupted loop bound leaves
a machine looping for ever while petting the watchdog on schedule.

Both are now addressed, and `docs/43` is the record — and one of them
did not work. The register file is SECDED-protected with the codec this
project already owns and has proved, corrected on read and scrubbed out
of the storage, substituted into Ibex by a *file list* rather than by
editing anything, so the pristine checkout and its sv2v output are
untouched. The campaign was re-run with identical draws — same site,
same bit, same cycle, a byte-identical workload image — and the
register-file strata went from 3 silent corruptions and 4 hangs in 100
to **0 and 0 in 200**, design-weighted silent corruption from 2.8 % to
1.3 %, and the watchdog's catch rate over the dead set from 33 of 36 to
28 of 28. It costs +13.8 % of the core's area and 9.3 % of its clock
frequency, because a decoder on the register read path runs in series
with the thing it protects where a shadow core would have run in
parallel.

The windowed watchdog did not deliver, and the document says so.
`docs/42` recommended it for a machine that loops for ever while petting
the watchdog on schedule — but a window fires on a kick that arrives too
*early*, and that machine kicks on time. Replayed verbatim against a
build with the window armed and nothing else, all four of those records
come back exactly as they did. What does catch them is a per-phase kick
budget, built after the window was found not to reach them, which caught
4 of 4; and the register file removes the class at source in any case.
The window itself caught 0 of 30 dead machines in the re-run campaign
and produced 7 escalations on machines that were fine, so the
zero-spurious-escalation result `docs/41` reported does not survive it.
It ships disabled.

The rest of the SoC is still **almost entirely unhardened** — no ECC on
the 72 KiB of memory, no scrubbing outside the register file, no TMR
outside the watchdog's protected word, and nothing on the CLINT's
`mtime`, which `docs/41` section 7.4 ranked next and which two documents
have since deferred with the reason written down each time.
*Corrected 2026-09-05:* `mtime` is protected since
`docs/58-clint-time-base-hardening.md`, and the memories since
`docs/67-memory-protection.md` — every row of the RAM and the boot ROM
carries a SECDED check field, is corrected on read, answers an
uncorrectable word with a bus error and is walked by a scrubber, at
the price of the RAM being 32 KiB rather than 64; that document says
why that was cheaper than a seventh macro. That is a
deliberate ordering, not an oversight: the fabric is being made correct
before it is made survivable.
*Corrected again 2026-09-05:* **the SoC boots.**
`docs/68-boot-flow.md` puts a loader in the boot ROM that initialises
every word of the RAM before anything reads it — an SRAM whose rows
carry check bits powers up with an uncorrectable in every word, not a
zero — copies a checksummed image out of the QSPI flash, verifies it by
reading the RAM back, and jumps to it, with a boot report and a boot
counter no software can write in the BOOTREG slot the map has reserved
since `docs/39`. The 28-check bring-up program now runs from RAM out of
a flash image: **220,256 cycles for the program and 415,324 for the
run**, against 217,630 for the identical program fetched from the ROM.
*Added 2026-09-05:* **and the block that decides whether it boots again
is now triplicated in the netlist**, which `docs/68` section 16 asked for and
`docs/69-boot-hardening.md` is the record of. Eighteen of that block's
92 flip-flops are bundled into one word and tripled under the same
proved voter the watchdog uses; the other 74 get nothing, and 64 of
those are the boot report and the epoch — **69.6 % of the block's state
with none of its consequence**, which is the ranking a flip-flop count
would have got backwards. One bit moved onto the protected list because
the campaign put it there: the system-reset sample is rewritten every
clock, so it sheds an upset on its own, but the boot counter it
increments is saturating and power-on-only and never comes back. **572
injections, 276 of 276 into the protected word corrected and announced,
against a first-ever baseline on the unprotected block where the boot
counter was displaced by as much as 128 boots with nothing on the part
saying so.** It costs 1.9 % of the Ibex core and zero cycles.

**The subsystem has been laid out, and it fails setup at its 20 ns
constraint.** `docs/45` synthesised `soc_top` whole for the first time —
it elaborated at the first attempt with no RTL edit, which is worth
saying because the reason it had never been done was not that it was
hard. `docs/47` then placed and routed it with six real RM_IHPSG13 SRAM
macros: it routes clean, and it does not meet timing. The memory is
~~**4.29 times the standard-cell logic**~~ and 46.9 % of the die.
*Corrected 2026-09-10: 4.29 divides the macro area by a standard-cell
area that `docs/59` section 6.3 identifies as the **rejected
`deferred_flatten` netlist's**, not the netlist that was hardened.
Measured against what is actually placed in `hw/soc/pnr/runs/full3` the
ratio is **4.2285** (`docs/59` section 11), and on
`hw/soc/pnr/runs/npu2`, the first layout that contains the accelerator,
it is **2.7445** (`docs/61` section 13 item 4). The die share is not
corrected and does not move: the same six macros, 2,246,899.85 um2, sit
on the same 4,786,287.408 um2 die in both runs.* No
frequency is published for this design, per `docs/05` section 4 rule 5:
a number read off a layout that also fails max slew and max cap and had
not then been through Magic DRC or LVS is not a result to put in a front
door. *(The deck half of that sentence stopped being true on 2026-09-11
-- `docs/77` and `docs/79` -- and the slew and cap half has not. No
frequency is published, for the reason that still holds.)*

Four remedies were tried and `docs/48` through `docs/50` measured all
four. A second floorplan is worse, and the existing one is already
optimal for these macro pins. Two flow settings worth 18 ns had already
been spent before the shortfall existed, which nobody had checked.
`SYNPRE` acts on a cone disjoint from the binding path — the correction
to that attribution is the result, not the run. Registering the RAM read
is the only measured improvement, and it makes the part **21 % slower in
wall-clock**, because a higher clock that spends more cycles per load is
not a faster part.

**Then `docs/53` asked what the mission needs, and found the question
had been the wrong one.** The transport, not the clock, is the
architectural factor: the serial link to the NPU is **93–98 % of every
workload's cycles**, a 27x term against the clock's 1.16x. Sized against
Falcon Neuro's flown event rates, the hardest profile uses about **10 %
of what the part delivers**; the clock would have to fall to 4.4 MHz
before any profile binds.

And the requirement that `docs/05` actually quantifies is **power**, in
tens of milliwatts — the only numeral in that section, which five
documents had read past. `docs/47`'s own sign-off run already carried
one: ~~**27.8–46.1 mW** across three corners~~.
*Corrected 2026-09-10: that range is `report_power` with no switching
activity annotated at all, and `docs/57-power-under-a-duty-cycle.md`
measured it against the whole-SoC run's own toggle rates. At the typical corner and 20 ns, on
`hw/soc/pnr/runs/full3`: **busy 33.890 mW** with the core's clock
running, **idle 5.539 mW** with it gated in WFI, and **orbit-average
5.540 mW** at the **0.0044 %** duty cycle `docs/53` section 6.2 sized
profile 1 at — the orbit average is the idle figure to four decimal
places, and at that duty cycle it always will be (`docs/57` section
11.1). The unannotated estimate was right to 2.8 % on the busy case and
wrong by a factor of **6.29** on the idle one, and the mechanism is a
clock gate six documents had said this design did not have. **Those
three figures are for a layout `docs/57` section 3.2 found does not
contain the accelerator.** On layouts that do,
`docs/76-the-second-and-third-clock-gates.md` section 8 measures **idle
8.287 mW and orbit-average 8.289 mW** at the same duty cycle, and
`docs/77-the-clock-gate-enables-and-what-actually-costs-them.md` section
9.5 **8.315 mW idle and 22.142 mW computing** on the layout after it —
and `docs/77` publishes no busy figure as a property of the design,
because it measures the busy totals as a placement's and not a
design's. Every one of these is a pre-silicon flow estimate on a layout
that fails setup at the slow corner, fails max slew and max cap, and had
not then been through Magic DRC, LVS or XOR; `docs/05` section 4 rule 5
says all of that travels with the number or none of it does. Corrected
2026-09-11: all four decks have been run (`docs/77`, `docs/79`). The
setup, slew and cap failures are unchanged and they are the half that
still governs these numbers.*
Energy per inference is invariant under the clock to 0.045 %, because
it is cycles times
energy-per-cycle and the period appears in neither. Four documents had
optimised the one term of that product the stated requirement does not
contain. So 20 ns stays as the SDC constraint and the setup failure
stays a defect — but the rank changed: power with real switching
activity first, the transport second, timing third.

Operators can now see a corrected upset: `docs/44` routed the register
file's fault line out through a real patch to Ibex and landed **BUSSTAT
at `0xFF915000`**, the slot the map has reserved since `docs/39`, with
four saturating counters and stickies that survive a reset. It also
found that `docs/43`'s timing attribution was wrong — every worst path
started at an input tied to a constant, and the binding constraint was
an unbuffered 2,328-fanout reset net.

*Does not exist.* No silicon. ~~No spacecraft interfaces.~~ One
spacecraft interface since 2026-09-05: a 16-pin GPIO port, built,
proved and driven through the pins by the bring-up program
(`docs/65-gpio-and-the-interface-ip-assessment.md`); and a
register-mode QSPI flash controller with two chip selects that feeds
the NPU its weight image from a modelled flash
(`docs/66-qspi-flash-controller.md`). SpaceWire, CAN, SPI and I2C are
fetched, pinned and priced in `docs/65` and still not built. No radiation
test data. No gate-level result for anything under `hw/soc/`. ~~No DRC,
LVS or XOR on the laid-out SoC~~ **-- corrected. All four decks have run
on `soc_top`'s own geometry since 2026-09-11 (`docs/77`, `docs/79`), and
on 2026-09-13 all three deck families ran on a layout built from the
current RTL that also carries the ROM's two check macros: `Circuits
match uniquely`; 11,048 KLayout markers -- **6,584 distinct shapes**,
because `Sdiod.d` and `Sdiod.e` report the same set and `docs/54`
section 3.1 says to count it that way -- of which 0 are outside the
vendor macro hierarchy; and 182 Magic boxes of which 20 are inside a
macro footprint and **all 162 others lie within 0.5 um of a macro
edge**, none in open routing area; and the KLayout XOR deck reports
**0 differences** (`docs/67` section 11). All four deck families have
now run on a layout built from the current RTL.** What the original sentence got right is the reason,
and the reason is a PDK property rather than a schedule: `docs/12`
measured 1,106,478 Magic errors inside a single RM_IHPSG13 macro's own
footprint and recorded it a no-go for this PDK version, which is why
every deck result here is stated as *inside the macro* or *outside* it
rather than as a total. No licence. No funding.

**The NPU is connected, and `docs/51` is the record.** Until it, this
repository held a RISC-V SoC and a separate neuromorphic accelerator
that had never been in the same simulation. `hw/rtl/pilot_top.v` — the
frozen TTIHP26b submission, instantiated and not copied — is now inside
`soc_top.v`, reached over the same four serial pins the die will have,
and a program on Ibex out of the boot ROM configures it, loads its
weights, feeds it a six-frame event stream and reads the spikes back
**against an answer `sw/golden/lif_core.py` computed at build time**.
27 checks, fail mask 0, **215,428 cycles** — `docs/51` measured 213,971
and `docs/55` section 8.5 says where the other 1,457 went, all of them
software. The transport is serial because that is what the die has: it
costs 176 clock cycles per register access, and what it buys is that
there is exactly one implementation of the die's host protocol and it is
the one in the SoC's own regression.

**And it is now hardened where a campaign said to harden it, which this
paragraph used to deny.** `docs/52` measured the connection, `docs/55`
built the four items it ranked, and `docs/56` split the event engine
into five strata and bounded the one that carried the rate. What is
still unprotected is unprotected because a measurement said so, and each
of those documents names which one.

The block after the connection was its fault-injection campaign. It sat
between two blocks whose upset behaviour had been measured — the die in
`docs/16`, the core in `docs/42` — and was itself unmeasured, and
hardening it before measuring it is the mistake `docs/38` section 10
item 4 names. `docs/52` is that campaign and `docs/55` and `docs/56` are
what it produced.

## Licence

Three licences, one per kind of thing, decided in
`docs/14-licensing-decision.md` and signed 2026-09-09.

| Class | Licence |
|---|---|
| RTL, testbenches, constraints, formal jobs, flow configuration | `CERN-OHL-W-2.0` |
| Generators, golden models, harnesses, flow drivers, analysis, CI | `Apache-2.0` |
| Documents in `docs/` and measurement data | `CC-BY-4.0` |

`LICENSES.md` is the map: every tracked path, in or out, with what is
held back and why. Every source file carries an SPDX tag; the files that
cannot hold a comment are covered by path in `.reuse/dep5`.
*Corrected 2026-09-10: this said ~~161 files~~, which is not what the
checker says. `scripts/spdx_check.py` prints the count on every run —
`N tagged, N covered by path, 0 missing, 0 wrong` — and it moves
whenever a file is added under a covered prefix; three runs in the hour
this was written returned 190, 191 and 191 covered by path, against 329,
332 and 335 tagged. So the numeral
is dropped rather than re-pinned. The claim that matters is that the
files are covered by path and that nothing is missing or wrong, and the
checker below is what establishes it.*

The map is checked rather than asserted:

```bash
python3 scripts/spdx_check.py
```

It fails on an untagged or mis-tagged source file.

**Run every check the way the workflow does, without the workflow:**

```bash
scripts/ci_local.sh all --record
```

That script is the definition; `.github/workflows/checks.yml` is a
wrapper that calls it, so the two cannot drift, and the checks do not
depend on a runner. **Three** checks skip locally, with the reason
printed, because this machine has no pandoc and no TeX; a skip is not a
pass and the summary says how many there were. *(Corrected 2026-09-11:
this said two. The paper job skips both the build and the bibliography
check that needs the build, and `ci-local-log.tsv` recorded skipped=3
while this sentence said two -- the log and the prose disagreed and the
prose was the one a reader sees.)*

*Corrected 2026-09-10: this said the checks "had never executed" in CI
because every run since 2026-09-03 was refused before starting. 53 of
the 61 runs since then executed; only the eight from 2026-09-10 are
non-starts. The `licence` job failed for a real reason —
`ModuleNotFoundError: No module named 'yaml'` — which is now fixed.*
Two
files are under a licence this project did not choose —
`hw/soc/rvformal/insns/insn_div.v` and `insn_rem.v` are corrected copies
of riscv-formal's models and carry upstream's ISC notice inline.


## Documents

- `docs/00-reference-brief.md` — GR801 public-brief summary and initial scaling observations
- `docs/01-reference-decomposition.md` — GR801 architecture decomposition and 28 nm to 130 nm scaling analysis
- `docs/02-npu-architecture.md` — event-driven inference engine options and recommendation
- `docs/03-cpu-and-ip-survey.md` — management CPU and interface IP survey (licensing, verification fit)
- `docs/04-technology-and-flow.md` — 130 nm technology selection, memory strategy, flow and cost
- `docs/05-market-positioning.md` — mission profile, competitive landscape, positioning rules
- `docs/06-funding-and-shuttle.md` — NLnet grant plan and TTIHP26b shuttle logistics
- `docs/07-design-review.md` — independent review of the research phase and design wave 1
- `docs/08-gr801-datasheet-notes.md` — GR801/GRLIB programmer-visible conventions and proximity checklist
- `docs/09-formal-verification-plan.md` — formal verification program (RTL formal, golden-model refinement, software track)
- `docs/10-npu-mvp-spec.md` — NPU MVP micro-architecture specification v0.1
- `docs/11-verification-harness.md` — how to run the simulation and formal harness
- `docs/12-sg13g2-flow-bringup.md` — IHP SG13G2 flow bring-up, trial harden and SRAM macro inventory
- `docs/13-nlnet-application.md` — NLnet Restack application draft
- `docs/14-licensing-decision.md` — open-licensing decision memo (NLnet terms, dependency licenses, export interaction)
- `docs/15-pilot-tile-plan.md` — pilot die content, pin contract and tile budget
- `docs/16-fault-injection-campaign.md` — seeded upset campaign, measured outcome distribution and per-structure ranking
- `docs/17-wave2-review-record.md` — independent review record for design wave 2
- `docs/regmap-npu.md` — generated register-map documentation (single source: `regmap/regmap.yaml`)
- `ROADMAP.md` — phased plan with gates

**`docs/00-index.md` is the canonical list and this one stops at 17 on
purpose.** The corpus is past eighty documents (`ls docs/*.md | wc -l`
is 85), and a second hand-kept list is a list that drifts — this one
already had, silently.

*Corrected 2026-09-10, and the correction is narrower than the sentence
it replaces.* This said the index "is generated against the directory".
**It is not generated. It is hand-written and checked against the
directory**, which is a weaker property and the one that is true:
`sw/tests/test_doc_links.py` discovers every `docs/*.md` plus this file
and `ROADMAP.md` on disk and fails if a document is not named in the
index, if the index names a document that does not exist, or if any
cross-reference in any of them names a file that does not exist. No
script writes `docs/00-index.md`; `scripts/build_docs.py` only renders
it, and falls back to a generated listing when it is absent.

**So the set of documents cannot go stale without the suite saying so,
and the numbers inside them can.** *This paragraph quoted the index as
opening with "Every count below carries the command that produced it"
and then argued the index did not support it. The index withdrew that
sentence itself on 2026-09-10 — its own correction note says the claim
mattered most here of anywhere in the corpus and that `README.md`
repeats it, which this file then went on doing for a day.* What the
index claims now is narrower and holds: every count in **section 2.1**
names an artefact and carries a command that reads it, and section 6's
re-measurements each name a command. The gap the old sentence was
pointing at is still there and is not covered by the narrower claim:
**section 5, the per-document table that is most of the file, is two
columns wide, carries hundreds of counts in prose and has no command
column at all.** Nothing in the suite fails when one of those counts
drifts.

Run section 2.1's own four commands against the tree and the drift is
visible in both directions. On **2026-09-10** every one of the four
disagreed with the row it sat in — 295 Python tests collected against
503, 145 cocotb functions against 166, 45 formal tasks against 54, and
"9 `.v` files, 5,366 lines" against 6,883 — and the rows were then
brought up to date. Re-run on **2026-09-11**, one day later, and one of
the four has already moved again: **505 tests collected, not 503**.
Three still hold. Section 6 exists precisely because this keeps
happening, and it is a record of past drift rather than a guard against
the next one. Start there anyway — it is the only list of what exists —
but re-run a count before quoting it.

## Layout

- `hw/rtl/` — RTL blocks; `hw/tb/` — cocotb testbenches, one `Makefile.<block>` each
- `formal/` — SymbiYosys configurations and property files; `make -C formal everything` runs the full gate
- `sw/golden/` — bit-exact integer golden models (the abstract specification); `sw/tests/` — their pytest suite
- `regmap/` — the register map single source and its generators
- `hw/openlane/` — physical flow configurations for IHP SG13G2
