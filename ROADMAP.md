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
| 2026-09-07 | Internal go/no-go: RM_IHPSG13 SRAM macro closes DRC/LVS in the local rootless flow | selects 8-tile macro pilot (go) vs 2x2 latch-RAM pilot (no-go default) |
| 2026-09-21 | TTIHP26b closes (fab IHP-2609) | pilot design frozen and submitted |
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
on at least one block.

### P1 — TTIHP26b pilot (to 2026-09-21)

Default content (2x2 tiles, latch/FF RAM, no SRAM-macro dependency —
docs/06 revised default): a reduced LIF slice (32 neurons, FF synapse
storage) implementing the docs/10 update equations bit-exactly, AER
input/output FIFOs (the formally proven block), the NPU register-bank
subset from `regmap/regmap.yaml`, and fault-tolerance demonstrators
(TMR voter bank + SECDED codec with error counters) observable via the
TT IO budget. Upgrade path (go/no-go 2026-09-07): 8 tiles with one
RM_IHPSG13 SRAM macro under BIST.

Verification bar for submission: cocotb suites green in two simulators
where feasible, golden-model lockstep on the LIF slice, formal proofs
green (FIFO now; register-bank write-enable and SECDED before freeze),
GL smoke on the TT-generated netlist.

Gate G1: TT submission accepted by precheck; formal/CI targets green;
hour-budgeted WBS in docs/06 held within its go/no-go checkpoints.

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
