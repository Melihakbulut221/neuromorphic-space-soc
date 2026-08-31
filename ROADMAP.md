# ROADMAP

Phased plan for the Neuromorphic Space SoC: a GR801-class fault-tolerant
neuromorphic SoC (RISC-V management core + event-driven LIF inference
engine + spacecraft interfaces) on 130 nm, IHP SG13G2 primary / SKY130
fallback (docs/04), open RTL-to-GDS flow, solo developer.

Issued at the close of the research phase, conditional on the blocking
actions of the independent review (docs/07 section 5) — all of which are
applied in the same change set as this document. Effort figures are
tagged with their source document; unsourced figures are [estimate].

## 1. External clocks

| Date | Event | Consequence |
|---|---|---|
| 2026-09-03 | NLnet calls reopen (Restack fund) | open-licensing decision must be made; application drafting starts |
| 2026-09-07 | Internal go/no-go: RM_IHPSG13 SRAM macro closes DRC/LVS in the local rootless flow | selects the macro content of the pilot, no longer its tile count (see the P1 sizing note) |
| 2026-09-21, 20:00 UTC (23:00 Istanbul) | TTIHP26b closes (fab IHP-2609) | pilot design frozen and submitted. The time of day was never recorded here until a live check on 2026-08-31; a deadline whose hour is unknown is a deadline missed by a day |
| 2026-11-03 | NLnet Restack submission deadline | application submitted |
| spring 2027 (date TBC) | TTIHP27a closes | full-SoC slot IF the pre-silicon gate passes |
| 2027-06-25 | TTIHP26b silicon arrives (boards ~2027-08) | pilot bring-up and characterization |
| H2 2027 | TTIHP27b / IHP open-source MPW | silicon-results-gated full-SoC run (docs/06 revised gate) |

The pilot-first strategy: silicon-prove the PDK, the flow, an SNN slice,
and the hardening demonstrators on a cheap TT run before committing the
full SoC. The full-SoC second run is gated on pre-silicon evidence for
TTIHP27a (clean sg13g2 harden, macro integration closed, formal/CI
green) or on pilot silicon results for TTIHP27b/IHP MPW (docs/06).

## 2. Phases and gates

### P0 — Baseline closure (now to 2026-08-31)

- Close all docs/07 blocking actions (physical re-baseline, NPU candidate
  physics, radiation-claim corrections, shuttle-plan arithmetic,
  architecture-supersession errata).
- Bring up the sg13g2 LibreLane flow in the rootless environment; trial
  harden of `aer_fifo` as the smoke vehicle.
- RM_IHPSG13 SRAM macro LEF/GDS study (docs/04 open question 2) — feeds
  the 2026-09-07 go/no-go.

Gate G0: docs/07 blocking list closed; sg13g2 trial harden DRC/LVS clean
on at least one block. **Met 2026-08-25** by run `trial-03-signoff` on
`aer_fifo`: all 80 flow stages completed in 680 s with Magic DRC 0,
KLayout DRC 0 (deep, no-recommended), Netgen LVS 0 on all seven
counters, XOR 0, antenna 0 nets and 0 pins after detailed routing,
0 disconnected pins, 0 power-grid violations, and 0 setup, hold,
max-slew and max-cap violations across all three corners. Recorded with
pinned tool and PDK versions in `docs/12-sg13g2-flow-bringup.md`.

### P1 — TTIHP26b pilot (to 2026-09-21)

**Status 2026-08-31: engineering complete, owner actions outstanding.**
The pilot is signed off at 6x2 = 12 tiles and the RTL is frozen. Every
geometric and timing counter reads zero on the run built from the file
the Tiny Tapeout tooling actually hardens, the derate is proven applied
in the flow-written constraints, the slow corner closes at +1.2262 ns,
the Tiny Tapeout precheck passes ten of ten, and thirty-five census
guards confirm the redundancy is present in the shipped netlist rather
than only in the source. `docs/31-signoff-6x2.md` is the record and
`docs/34-pilot-freeze.md` pins the artifact set.

Two decisions below are superseded by measurement and kept for the
record: the tile shape moved from 4x2 to 6x2 when the design outgrew the
70 percent planning criterion (`docs/22`, `docs/23`), which takes the
cost from EUR 560 to EUR 840 in tiles alone — but see the corrected total
below; and the 2026-09-07 SRAM-macro go/no-go was
overtaken, since the pilot ships flip-flop RAM and the macro variant is
a twelve-tile design in its own right.

What remains is not engineering: a Tiny Tapeout account, a TTIHP26b 6x2
slot, **EUR 955** — corrected 2026-08-31 from a live check of the Tiny
Tapeout pricing: twelve tiles at EUR 70 is EUR 840, but the tile-only
figure this document and docs/06 had been quoting omits the EUR 300
devkit, which is subsidised to EUR 100 while 88 of the first 100 remain,
and EUR 15 of shipping — and a push to a repository so the GDS action and
the
hosted precheck can run. That last step has never executed and is the
only part of this phase this repository cannot do for itself. The
licensing decision in `docs/14` is still unsigned and a submission
repository is public, so it gates the push.

The original content and sizing analysis follows.

Content (flip-flop RAM, no SRAM-macro dependency): a reduced LIF slice
implementing the docs/10 update equations bit-exactly, AER input/output
FIFOs (the formally proven block), the NPU register-bank subset from
`regmap/regmap.yaml`, and fault-tolerance demonstrators (TMR voter bank
+ SECDED codec with error counters) observable through the Tiny Tapeout
IO budget.

**Tile sizing, measured (supersedes the 2x2 default carried from
docs/06 B.6):** the integrated pilot does not fit 2x2. Synthesized on
`sg13g2_stdcell`, `pilot_top` at 8x8 neurons is 105,245 um2 post-techmap,
which needs 113.7 percent utilization in 4 tiles — and 88.5 percent even
under the most optimistic placed-area calibration. The glue alone
(register bank, serial port, queues, dispatcher, weight loader, TMR,
SECDED — everything except `lif_core`) is 61,733 um2, about 95 percent
of what 2x2 holds at 70 percent utilization with zero neurons.
**Decision: 4x2 = 8 tiles at EUR 560**, which the docs/06 B.6 budget
already carries, so the funding envelope is unchanged. Consequently the
2026-09-07 go/no-go no longer decides the tile count; it decides whether
the die carries an SRAM macro. Note the macro variant is itself larger
than 8 tiles: `RM_IHPSG13_1P_512x32` with its halo is 92,278 um2 against
a 264,507 um2 4x2 core, leaving 172,229 um2 for logic that needs
210,866 — that variant is a 3x4 = 12-tile design and must be costed as
one if it is ever chosen.

Verification bar for submission: cocotb suites green in two simulators
where feasible, golden-model lockstep on the LIF slice, formal proofs
green (FIFO now; register-bank write-enable and SECDED before freeze),
GL smoke on the TT-generated netlist.

Gate G1: TT submission accepted by precheck; formal/CI targets green;
hour-budgeted WBS in docs/06 held within its go/no-go checkpoints.

**G1 status: met locally, not yet met hosted.** The precheck passes ten
of ten on the sign-off GDS and the formal and CI targets are green. What
the gate cannot claim is the hosted half: the Tiny Tapeout GDS action has
never run, because running it requires the repository to be pushed. The
local precheck is the same deck, but a gate that says "accepted by
precheck" should mean the one that gates the shuttle, so this stays open
until the action has run. Note also that the local precheck needs KLayout
0.30.9 — the system 0.28.16 aborts the PDK deck and reports a failure
that is not real.

### P2 — NLnet Restack application (2026-09-03 to 2026-11-03)

- Open-licensing decision: NLnet requires free licensing of funded work.
  Decision point (owner: developer): publish the repo at submission time
  or commit to publication in the application. Blocks submission.
- Application package from docs/06 part A: abstract draft, EUR 27.5k
  budget sketch (shuttle slots, bring-up hardware, radiation pre-screen,
  developer time), comparison with existing efforts (Libre-SOC,
  Chips4Makers, FABulous precedents).
- All positioning language per docs/05 rules (LEO 10-30 krad class,
  fault-tolerant wording, no >=100 krad claims) — corrected text only
  (docs/07 F-8/F-9/F-10 fixes).

Gate G2: application submitted before 2026-11-03; repo license state
consistent with what the application promises.

### P3 — SoC design wave (2026-09 to mid-2027)

Workstreams, in dependency order:

1. NPU RTL: LIF core per docs/10 (E1-E10 bit-exact vs golden model,
   lockstep cocotb), synapse memory with SECDED, AER mesh-node
   interface. Pilot slice is the first instantiation. ~200-350 h
   [estimate].
2. Management subsystem: Ibex integration (sv2v early prototype
   milestone is the single-point-dependency check, docs/03), PMP-based
   static partition supervisor per docs/09 S2, interrupt/timer/watchdog
   per docs/08 conventions. ~150-300 h [estimate].
3. Interfaces, base set first (2x UART, SPI, I2C, GPIO, QSPI), then
   SpaceWire codec and CAN 2.0B (Mohor adaptation, stated GR801
   deviation): base 280-475 h per the corrected docs/03 roll-up, CPI
   as an optional line item (+40-80 h) outside the base.
4. Formal program: targets 1-10 per docs/09 part C, in CI from week 1
   (FIFO already green): 155-310 h (docs/09; roughly a third to a
   half of the interface base, corrected comparison).
5. Software track: bare-metal supervisor with Frama-C/CBMC
   absence-of-runtime-error evidence (docs/09 S2). ~80-160 h [estimate].
6. Physical: hierarchical tile hardening, MBIST/scan (prior DFT
   experience), multi-corner STA. ~150-300 h [estimate].

Roll-up: ~1015-1895 h. At a solo part-time 15-25 h/week alongside other
programs [estimate], that is 12-24 months of calendar; the full-SoC RTL
freeze therefore lands mid-2027 at the earliest, which is consistent
with the TTIHP27b / IHP MPW target and makes TTIHP27a a stretch that
only the pre-silicon gate can justify. NLnet funding, if granted,
buys focused time and moves the freeze left.

Gate G3: RTL freeze with all docs/09 F-gates green; regmap/spec/golden
model/RTL in proven sync; interface set demonstrated against golden
models.

### P4 — Pilot bring-up (2027-06 to 2027-09)

TT board bring-up, host software against the register map, LIF-slice
functional characterization vs golden model, TMR/SECDED demonstrator
exercise, results memo. Feeds the TTIHP27b/MPW gate and the NLnet
reporting milestones.

Gate G4: pilot silicon report — bit-exactness on silicon, demonstrator
behavior, flow lessons folded back into P3.

### P5 — Full-SoC tapeout and pre-screen (H2 2027 onward)

Full-SoC run on the gated shuttle; radiation pre-screen per docs/10 of
the sibling program conventions: Co-60 TID pre-screen and proton
facility options identified in prior project work; positioning remains
LEO 10-30 krad, fault-tolerant by architecture. Flight-model claims are
out of scope for this phase and this document.

## 3. Near-term work queue (next two weeks)

1. sg13g2 flow bring-up + `aer_fifo` trial harden (G0 evidence).
2. RM_IHPSG13 macro DRC/LVS study for the 2026-09-07 go/no-go.
3. Pilot RTL: 32-neuron LIF slice from docs/10 parameters + register
   bank RTL from `regmap.yaml` + TMR voter and SECDED demonstrators,
   each with cocotb + golden-model lockstep and formal where in the
   docs/09 first-ten list.
4. TT submission repo + pin/tile plan for the default 2x2 pilot.
5. NLnet application skeleton instantiated from docs/06 with corrected
   positioning language; license decision memo for the 2026-09-03
   reopen.
6. Formal targets 2-3 (register-bank write-enable, SECDED) into CI.

## 4. Backlog (non-blocking)

- docs/09 S1 area table recomputed on SG13G2 (rejection stands on the
  MB-class RAM argument) — applied with this change set.
- Golden-model tiling bound enforcement (docs/07 F-13) — applied with
  this change set; must hold before RTL-vs-model verification starts.
- `aer_fifo` contract tightenings (F-18/F-19) — applied with this
  change set.
- Mesh scale-out (docs/02 Candidate C) — contingent on an event-camera
  payload requirement.
- seL4-on-CVA6 product tier (docs/09 S3) — interface discipline only
  for now.
- CPI front end — optional line item pending docs/08 CPI decision.

## 5. Binding rules inherited by all phases

- Positioning: docs/05 section 4 (LEO 10-30 krad class, fault-tolerant
  wording, never >=100 krad claims, multi-market framing).
- Repo: English only, no emojis, sole-developer attribution, neutral
  engineering voice.
- Method: spec-first with frozen golden models; every RTL change
  re-proven (docs/09 maintenance rules); facts vs estimates tagged in
  all documents; no area/SRAM number quoted without naming its PDK
  (docs/07 verdict).
