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
SECDED codec, a TMR voter and a scrub controller — 6,856 lines of
Verilog. Verification is 234 Python tests against frozen bit-exact golden
models, 166 cocotb tests, 54 SymbiYosys proof tasks, a seeded
fault-injection campaign of 378 upsets classified against the golden
model, and a gate-level run in which 370 of 370 comparable injections
classify identically to RTL. `docs/34-pilot-freeze.md` pins the whole
artifact set by hash.

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

The watchdog's own state is now protected, and `docs/41` is the record.
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
have since deferred with the reason written down each time. That is a
deliberate ordering, not an oversight: the fabric is being made correct
before it is made survivable.

**The subsystem has been laid out, and it fails setup at its 20 ns
constraint.** `docs/45` synthesised `soc_top` whole for the first time —
it elaborated at the first attempt with no RTL edit, which is worth
saying because the reason it had never been done was not that it was
hard. `docs/47` then placed and routed it with six real RM_IHPSG13 SRAM
macros: it routes clean, and it does not meet timing. The memory is
**4.29 times the standard-cell logic** and 46.9 % of the die. No
frequency is published for this design, per `docs/05` section 4 rule 5:
a number read off a layout that also fails max slew and max cap and has
never been through Magic DRC or LVS is not a result to put in a front
door.

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
one: **27.8–46.1 mW** across three corners. Energy per inference is
invariant under the clock to 0.045 %, because it is cycles times
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

*Does not exist.* No silicon. No spacecraft interfaces. No radiation
test data. No gate-level result for anything under `hw/soc/`. No DRC,
LVS or XOR on the laid-out SoC, and that one is a PDK property rather
than a schedule: `docs/12` measured 1,106,478 Magic errors inside a
single RM_IHPSG13 macro's own footprint and recorded it a no-go for this
PDK version. No licence. No funding.

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
purpose.** The corpus is past thirty documents, and a second hand-kept
list is a list that drifts — this one already had, silently. The index is
generated against the directory and `sw/tests/test_doc_links.py` fails if
a document is missing from it or a cross-reference names a file that does
not exist, so it cannot go stale without the suite saying so. Start
there.

## Layout

- `hw/rtl/` — RTL blocks; `hw/tb/` — cocotb testbenches, one `Makefile.<block>` each
- `formal/` — SymbiYosys configurations and property files; `make -C formal everything` runs the full gate
- `sw/golden/` — bit-exact integer golden models (the abstract specification); `sw/tests/` — their pytest suite
- `regmap/` — the register map single source and its generators
- `hw/openlane/` — physical flow configurations for IHP SG13G2
