# Funding and shuttle plan: NLnet grant and TTIHP26b

Research report for the neuromorphic space SoC (GR801-class retarget to
130 nm, see `docs/00-reference-brief.md`). All web facts checked on
2026-08-24; items that could not be fully verified are marked
**[unverified]** or **[estimate]**.

Two external clocks drive the plan:

- **TTIHP26b shuttle closes 2026-09-21** (four weeks away).
- **NLnet calls reopen 2026-09-03, next submission deadline 2026-11-03
  12:00 CEST** (https://nlnet.nl/propose/).

---

## Part A — NLnet funding

### A.1 Current call situation (August 2026)

NLnet is in a transition period. The apply page
(https://nlnet.nl/propose/) states there are currently **no open
calls**: calls reopen on **September 3rd 2026** with a submission
deadline of **November 3rd 2026, 12:00 CEST (noon)**. The long-running
NGI Zero programme is winding down — the thirteenth and final call of
the NGI Zero Commons Fund closed on June 1st 2026
(https://nlnet.nl/commonsfund/) — and NLnet is preparing successor
programmes under the "Open Internet Stack" umbrella
(https://nlnet.nl/news/2026/20260612-NGIZero-stocktaking.html):

| Fund | Scope | Fit for this project |
|---|---|---|
| **Restack** (https://nlnet.nl/restack/) | "Technology building blocks across the internet stack", explicitly including **"libre chips and hardware"**; EUR 7 million in small/medium R&D grants through 2030 | **Primary target.** Open silicon is named in scope. |
| CodeSupply | Maintenance/supply-chain support for existing code **[scope unverified — page thin as of Aug 2026]** | Not a fit for new silicon |
| ELFA (https://nlnet.nl/ELFA/) | "Encrypted Local First Architecture" — E2E-encrypted, local-first software | Not a fit (software only) |
| NGI Taler / NGI Fediversity pilots | Still open on the regular bi-monthly schedule | Not a fit (payments / hosting topics) |

**Conclusion: apply to Restack when the call opens on 2026-09-03;
submit well before the 2026-11-03 deadline.** The historic bi-monthly
cadence (Feb 1 / Apr 1 / Jun 1 / Aug 1 / Oct 1 / Dec 1) is suspended
during the transition; Nov 3 is the confirmed next deadline. Expect the
cadence to resume in some form afterwards **[unverified]**.

### A.2 Grant size

- Commons Fund and Restack both state a request range of **EUR 5,000 to
  50,000** for a first proposal, "with the possibility to scale up
  significantly if there is proven potential"
  (https://nlnet.nl/restack/, https://nlnet.nl/commonsfund/).
- Under the Commons Fund rules, follow-up proposals could go to
  EUR 150,000 per proposal with a EUR 500,000 lifetime cap per third
  party (https://nlnet.nl/commonsfund/guideforapplicants/). Restack
  follow-up limits are not yet published **[unverified]**.

### A.3 Eligibility (individual, Turkey-based)

From the NGI Zero Commons Fund eligibility page
(https://nlnet.nl/commonsfund/eligibility/) — Restack-specific rules
are not yet published, but NLnet's baseline policy has been stable:

- **Individuals are eligible.** There are "no categorical exclusions of
  persons who may not receive support" — natural persons, companies,
  non-profits all qualify.
- Geography: "inhabitants of the EU and countries associated to Horizon
  Europe are given priority." **Türkiye is an associated country to
  Horizon Europe** for the 2021-2027 framework
  (https://research-and-innovation.ec.europa.eu/strategy/strategy-research-and-innovation/europe-world/international-cooperation/association-horizon-europe/turkiye_en,
  https://tubitak.gov.tr/en/node/14570), so a Turkey-based applicant
  falls inside the **priority group**, not the exception path.
  Association for the 2028-2034 period is still under negotiation as of
  2026 **[monitor]** — irrelevant for a 2026 application against the
  2021-2027 framework.
- Even for non-associated countries, projects "of exceptional quality"
  with "a clear European dimension" are eligible. This project's
  European dimension is strong regardless: the target PDK is from IHP
  (a German Leibniz institute), fabrication is in Frankfurt (Oder), and
  the output strengthens the European open-silicon commons.

### A.4 What NLnet funds — open-silicon precedents

NLnet has funded roughly 1,430 projects over the NGI period
(https://nlnet.nl/news/2026/20260612-NGIZero-stocktaking.html),
including a substantial open-hardware/silicon portfolio
(https://nlnet.nl/thema/Hardware.html). Verified precedent project
pages (all URLs return 200 as of 2026-08-24):

| Project | Relevance | URL |
|---|---|---|
| Libre-SOC | Full open SoC effort (~EUR 400k across grants), taped out at 180 nm | https://nlnet.nl/project/Libre-RISCV/ |
| Chips4Makers | Libre standard cells + 0.18 um ASIC manufacturing of Libre-SOC test chip | https://nlnet.nl/project/Chips4Makers/ |
| Coriolis2 | Open ASIC layout tooling (Sorbonne) for Libre-SOC | https://nlnet.nl/project/Coriolis2/ |
| FABulous Demo SoC | Open eFPGA fabric + RISC-V SoC built with open tools | https://nlnet.nl/project/FABulous-SoC/ |
| LunaPnR | Open place-and-route tool | https://nlnet.nl/project/LunaPnR/ |
| LibreSilicon | Open semiconductor process | https://nlnet.nl/project/LibreSilicon/ |
| LiteX | FPGA/ASIC SoC framework | https://nlnet.nl/project/LiteX/ |
| NaxRiscv | Out-of-order RISC-V with ASIC synthesis | https://nlnet.nl/project/NaxRiscv/ |

Notable gap: **no space/SpaceWire/satellite-silicon precedent was found
in the funded-projects list.** The application should therefore not
lean on a "space fund" framing; frame it as an **open-silicon commons
building block** (open SNN IP, open fault-tolerance IP, open flow on a
European open PDK) whose first application domain happens to be small
satellites. ASIC tapeouts, standard cells, and EDA tools are all
squarely within precedent.

### A.5 Application format

Based on the historic NLnet form (the Restack form opens 2026-09-03 and
should be re-checked then **[re-verify at call opening]**):

- Contact info, project name, requested amount (EUR 5,000-50,000).
- **Abstract, maximum 1,200 characters** — explain the whole project
  and expected outcomes. Longer outlines can go in attachments
  (confirmed in applicant reports, e.g.
  https://ar.al/2024/06/01/small-technology-foundation-funding-application-for-nlnet-foundation-ngi-zero-core-seventh-call/).
- Prior experience of the applicant.
- **"Compare your own project with existing or historical efforts"** —
  a dedicated field; for this project: GR801 (proprietary, 28 nm FDSOI),
  BrainChip Akida (proprietary IP), open SNN cores such as ODIN/ReckOn
  (open but not fault-tolerant, not SoC-integrated, not on an open PDK),
  Libre-SOC (open SoC but general-purpose, no fault tolerance or space
  interfaces).
- Budget plan: what the money will be used for, broken into work
  packages/activities with amounts.
- Two-stage evaluation (Commons Fund weights, likely similar for
  Restack **[unverified]**): technical excellence/feasibility 30%,
  relevance/impact/strategic potential 40%, cost effectiveness 30%;
  threshold 5.0/7.0. Stage 2 is an interactive Q&A on comparisons,
  sustainability, and budget justification
  (https://nlnet.nl/commonsfund/guideforapplicants/).
- On selection, a **Memorandum of Understanding** is negotiated (sample:
  https://nlnet.nl/foundation/request/sample_MoU.pdf) defining tasks,
  milestones, and payment per completed milestone (no upfront payment;
  payments follow delivered, published results).
- NLnet runs a monthly office hour for applicant questions
  (https://nlnet.nl/officehour/).

### A.6 Open-licensing mandate — and the private-repo tension

The licensing requirement is absolute: "any software and hardware must
be published under a recognised open source license **in its entirety**"
(https://nlnet.nl/commonsfund/guideforapplicants/); "project results
always become available under a free or open source license"
(https://nlnet.nl/commonsfund/). MoU milestone payments are tied to
published results.

**This repository is currently private.** An NLnet application is a
commitment that every funded artifact — RTL, testbenches, flow scripts,
documentation, bring-up results — is published under free licenses
(e.g. Apache-2.0 or CERN-OHL-S for hardware sources, CC-BY for docs).
The sibling project's "public at tapeout" posture is **not compatible**
with an NLnet grant timeline: the repo (or a curated public mirror of
the funded scope) must be public no later than the MoU stage, and being
public at submission time materially helps evaluation (reviewers check
prior work). Decision required before applying (action item 5).

### A.7 Timeline: submission to decision to MoU

Observed 2026 data points for the Commons Fund: the December 2025 call
was announced on 2026-03-02 (44 projects,
https://nlnet.nl/news/2026/20260302-announce-commons-fund.html) and the
February 2026 call on 2026-04-09 (57 projects,
https://nlnet.nl/news/2026/20260409-announce-commons-fund.html) —
i.e. **roughly 2-3 months from deadline to selection announcement**,
including one Q&A round. MoU negotiation typically adds **1-2 months**
before work formally starts **[estimate from applicant reports]**. For
the 2026-11-03 deadline: decision around **January-February 2027**, MoU
and start around **February-April 2027**. First disbursements only
after first milestones are delivered and published.

### A.8 Skeleton application draft

**Working title:** "Open fault-tolerant neuromorphic SoC for small
satellites" (project short name to decide; repo name
`neuromorphic-space-soc` works).

**Abstract draft (1,142 characters, limit 1,200):**

> Small satellites increasingly need on-board AI inference, but the
> only radiation-tolerant neuromorphic SoC announced to date
> (Frontgrade Gaisler GR801) is proprietary, built on 28 nm FDSOI, and
> out of reach for university and small-team missions. This project
> develops an open-source, fault-tolerant SoC for event-driven neural
> inference on CubeSat-class satellites: a RISC-V management core, a
> clean-room event-driven spiking neural network engine with low-bit
> quantized weights, ECC-protected on-chip memory, and spacecraft
> interfaces (SpaceWire, CAN, SPI, I2C, UART), hardened by architecture
> (TMR control logic, memory scrubbing, fault counters) rather than by
> a proprietary process. All RTL, the verification suite, and the
> physical-design flow are published under free licenses and target
> IHP's open-source SG13G2 130 nm PDK, with silicon validation on
> affordable community shuttles (Tiny Tapeout) and radiation
> pre-screening of the fabricated parts. The result is a reusable,
> auditable European open-silicon building block: a reference design
> and IP set that lets any team fly inspectable AI hardware instead of
> black-box accelerators.

**Budget sketch (EUR 15-30k window; all figures [estimate]):**

| Work package | Content | EUR |
|---|---|---|
| WP1 SNN engine + hardening IP | Event-driven SNN fabric RTL, TMR/ECC/scrub blocks, verification suite (developer time, ~5 months) | 10,000 |
| WP2 SoC integration + flow | RV32 manager integration, SpaceWire/CAN/peripheral subset, LibreLane sg13g2 flow, docs (developer time, ~3 months) | 6,500 |
| WP3 Shuttle silicon | TTIHP26b pilot (8 tiles, ~EUR 560) + follow-up TT run (16-32 tiles, EUR 1,120-2,240) + devkits/breakout PCBs | 3,500 |
| WP4 Bring-up hardware | Test boards, FPGA host board, instrumentation for characterization | 2,500 |
| WP5 Radiation pre-screening | TID (Co-60) campaign on shuttle parts, test-board mods, logistics; facility-dependent | 5,000 |
| **Total** | | **27,500** |

Rationale for the developer-time rates: NLnet funds individuals at
modest, justified rates; the budget must map to concrete published
milestones (MoU structure rewards small, verifiable work packages).

---

## Part B — TTIHP26b shuttle (Tiny Tapeout on IHP SG13G2)

### B.1 Shuttle confirmed, dates

TTIHP26b is **confirmed and currently open** — it is listed as an open
shuttle with a live countdown on https://tinytapeout.com/ alongside
SKY26c. Per the shuttle index (https://app.tinytapeout.com/shuttles/),
TTIHP26b **launched 2026-07-27 and closes 2026-09-21**, maps to IHP
fab run IHP-2609, with **chips expected 2027-06-25** and estimated
board delivery **2027-08-16** **[dates from the shuttle app as indexed
2026-08-24; re-confirm in the dashboard before purchase]**.

Reference cadence of prior IHP runs (two per year):

- TTIHP25a: closed 2025-03-28, delivery ~Feb 2026
  (https://tinytapeout.com/chips/ttihp25a/)
- TTIHP25b: autumn 2025 run (https://tinytapeout.com/chips/ttihp25b/)
- TTIHP26a: closed 2026-03-23 (https://tinytapeout.com/chips/ttihp26a/)
- TTIHP27a: expected ~March 2027 **[extrapolation, unannounced]** —
  natural backup / second-run slot.

Fab-to-board lag on IHP runs is long (~9-11 months tapeout to boards);
prior runs were partially subsidized by SwissChips and the German BMBF
FMD-QNC project (https://tinytapeout.com/chips/ttihp25a/).

### B.2 Tile geometry and pricing: IHP vs SKY130

Hard numbers from the Tiny Tapeout build system
(`tt-support-tools/tech/*/tile_sizes.yaml`,
https://raw.githubusercontent.com/TinyTapeout/tt-support-tools/main/tech/ihp-sg13g2/tile_sizes.yaml
and
https://raw.githubusercontent.com/TinyTapeout/tt-support-tools/main/tech/sky130A/tile_sizes.yaml):

| Metric | SKY130 | IHP SG13G2 | Ratio |
|---|---|---|---|
| 1x1 tile | 161.00 x 111.52 um = 0.01795 mm2 | 202.08 x 154.98 um = 0.03132 mm2 | IHP 1.74x larger |
| Largest block def | 8x4 (1378.16 x 511.36 um = 0.705 mm2) | 8x4 (1724.16 x 710.64 um = 1.225 mm2) | — |
| Available shapes (IHP) | — | 1x1, 1x2, 2x1, 2x2, 3x1, 3x2, 3x4, 4x1, 4x2, 4x4, 5x4, 6x1, 6x2, 6x4, 8x1, 8x2, 8x4 | — |

- **Pricing:** ~**EUR 70 per tile** on IHP shuttles; analog pins EUR 40
  each for the first two, EUR 100 thereafter (not needed here —
  digital-only design). Current prices:
  https://app.tinytapeout.com/calculator (per
  https://tinytapeout.com/faq/ and https://tinytapeout.com/specs/analog/).
  So: 4 tiles ~EUR 280, 8 tiles ~EUR 560, 32 tiles ~EUR 2,240, plus a
  devkit/PCB order.
- **Max tiles per design:** block templates exist up to **8x4 = 32
  tiles**; whether 32 tiles are purchasable on a given shuttle is
  shuttle-dependent **[confirm in the calculator/dashboard]**.
- **IO per design (TT mux):** fixed regardless of tile count —
  **8 dedicated inputs (`ui_in`), 8 dedicated outputs (`uo_out`),
  8 bidirectional (`uio`)**, plus clock and reset supplied by the TT
  infrastructure; ~50 MHz practical clock ceiling
  (https://tinytapeout.com/faq/). A SpaceWire link (DS-encoded, 2 pins
  per direction) fits comfortably in this budget alongside UART/SPI.

### B.3 Density: SG13G2 vs SKY130 (the "2x" hypothesis is wrong)

Measured from the PDK libraries, not marketing figures:

- `sg13g2_stdcell` (IHP-Open-PDK,
  https://github.com/IHP-GmbH/IHP-Open-PDK): CoreSite 0.48 x 3.78 um;
  `sg13g2_nand2_1` = 1.92 x 3.78 um = 7.26 um2, i.e. **raw density
  ~138 kGE/mm2**.
- `sky130_fd_sc_hd`: raw density **266 kGE/mm2** (SkyWater docs,
  https://skywater-pdk.readthedocs.io/en/main/contents/libraries/foundry-provided.html).

So SG13G2 standard cells are about **2x less dense per mm2 than SKY130
HD** — the opposite of the "roughly 2x SKY130" working assumption.
However, the IHP TT tile is 1.74x larger, so **per-tile logic capacity
is roughly 0.9x of a SKY130 tile** (raw ~4.3 kGE per IHP tile vs
~4.8 kGE per SKY130 tile; practical capacity at the ~70% utilization
demonstrated on our prior SKY130 TT submission is ~2.5-3 kGE per IHP
tile). Plan tile budgets with SKY130 intuition, then add ~10% margin.
What SG13G2 gives back: a faster process (competitive timing at
50 MHz+ with margin) and the European fab/radiation story below.

### B.4 Digital flow maturity and SRAM on SG13G2 (2026)

- **PDK:** IHP-Open-PDK is mature and actively released (June 2026
  release documented at https://ihp-open-pdk-docs.readthedocs.io/;
  https://www.ihp-microelectronics.com/services/research-and-prototyping-service/fast-design-enablement/open-source-pdk).
- **LibreLane:** the TT flow itself hardens IHP projects with LibreLane
  (https://github.com/TinyTapeout/ttihp-verilog-template), and IHP
  publishes its own LibreLane full-chip templates
  (https://github.com/IHP-GmbH/ihp-sg13cmos5l-librelane-template).
  OpenROAD-flow-scripts carries an `ihp-sg13g2` platform
  (https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/tree/master/flow/platforms/ihp-sg13g2).
  DRC/LVS is KLayout-based; Magic/Netgen integration is newer and still
  maturing (https://wiki.f-si.org/index.php?title=IHP_Open_PDK_integration_with_Magic,_Netgen,_and_LibreLane).
  Verdict: the digital flow is production-grade for TT-scale designs.
- **SRAM:** IHP ships compiled macros (`RM_IHPSG13_*`, e.g.
  `RM_IHPSG13_1P_1024x32_c2_bm_bist`) in the open PDK. TT documents
  per-tile densities when instantiating them
  (https://tinytapeout.com/specs/memory/): 1024x8 single-port
  ~5,390 bits/tile; **1024x32 single-port ~8,820 bits/tile**; 1024x32
  dual-port ~4,680 bits/tile — and warns that "integrating the IHP SRAM
  macro at this stage is not trivial." OpenRAM support for SG13G2
  exists in the ecosystem but its production-readiness is unclear
  **[unverified]**; plan on RM_IHPSG13 macros. Fallback options: DFF
  RAM (~320 FF/tile) and latch RAM (~512 bits/tile demonstrated on
  SKY130; SG13G2 figures unpublished **[estimate]**).
- **Hard ceiling for the memory strategy:** even at 8,820 bits/tile, a
  32-tile design fully packed with SRAM holds only ~35 KB. The
  "hundreds of kB, ECC-protected" SoC memory target of the reference
  brief **cannot be met on Tiny Tapeout**; TT is the pilot vehicle, not
  the product vehicle.

### B.5 Radiation attractiveness of SG13G2

Honest summary — the data is encouraging but mostly from the SiGe
BiCMOS side of the process, not from `sg13g2_stdcell` digital logic:

- A 112 Gb/s radiation-hardened optical transceiver in IHP 130 nm SiGe
  BiCMOS (SG13G2 family) survived X-ray TID to **1.2 Mrad(Si)** and
  showed **no SEL under heavy ions up to LET 65.2 MeV cm2/mg**
  (https://www.researchgate.net/publication/351632595_A_112_Gbs_Radiation-Hardened_Mid-Board_Optical_Transceiver_in_130-nm_SiGe_BiCMOS_for_Intra-Satellite_Links).
- SiGe HBTs have well-documented intrinsic TID tolerance
  (https://www.researchgate.net/publication/260356025_Radiation_Effects_in_SiGe_Technology),
  and 130 nm CMOS nodes generically show usable TID behavior in HEP
  applications (https://www.sciencedirect.com/science/article/abs/pii/S0168900207015501).
- IHP has developed radiation-hardened 130 nm library work targeting
  ~200 krad with SEL-aware design rules **[secondary source, primary
  paper not located in this pass — find and cite before using in the
  application]**.
- SG13G2 is used for monolithic pixel detectors beam-tested at CERN,
  indicating an active rad-effects research community around the node.

Positioning consequence: consistent with the reference brief, bulk
130 nm CMOS logic gets **no platform SEL/TID guarantee** — hardening is
architectural (TMR, ECC, scrubbing), and the TT pilot chip is itself
the cheapest instrument to produce first TID/SEE data for
`sg13g2_stdcell`-based logic. That measurement campaign is exactly the
NLnet WP5 budget line, and it is a contribution the open community
currently lacks.

### B.6 What fits in N tiles — recommended tile budget

Capacity model: ~4.3 kGE raw / ~2.5-3 kGE practical per IHP tile
(B.3), SRAM per B.4.

| Option | Tiles | Cost | Content | Verdict |
|---|---|---|---|---|
| Minimal pilot | 2x2 = 4 | ~EUR 280 | 16-32 LIF neuron crossbar, latch-based 4-bit weights, event interface, TMR/EDAC demonstrator counters | Fits, but no SRAM macro learning |
| **Recommended pilot (TTIHP26b)** | **4x2 = 8** | **~EUR 560 + devkit** | One RM_IHPSG13 1024x8 macro (~2 tiles) as ECC-wrapped weight memory, 32-neuron event-driven SNN slice (~3 tiles), minimal sequencer or SERV-class RV32 control (~1-2 tiles), fault counters + SpaceWire-lite/UART host link (~1 tile) | Exercises every risky element of the full SoC: SRAM macro integration, ECC wrapper, SNN datapath, sg13g2 timing closure |
| Full-SoC attempt | 8x4 = 32 | ~EUR 2,240 | RV32 manager + multi-node SNN + SpaceWire codec + ~16 KB ECC SRAM (4x 1024x32 macros ~ 15 tiles, ~45 kGE logic left) | Marginal; only as a second run (TTIHP27a) after pilot results |
| Product MVP | — | — | Hundreds-of-kB SRAM class | Not possible on TT; needs a dedicated IHP MPW slot (price list: https://www.ihp-microelectronics.com/services/research-and-prototyping-service/mpw-prototyping-service/schedule-price-list), potentially FMD/university-subsidized **[investigate]** |

**Recommendation: buy 4x2 = 8 tiles on TTIHP26b for the pilot block,
and hold the full-SoC integration for TTIHP27a or an IHP MPW,
depending on NLnet outcome.**

### B.7 Deltas from the proven SKY130 rootless flow

The existing assets — a rootless LibreLane flow on SKY130 and a shipped
TT submission pipeline — carry over almost entirely. Concrete deltas:

1. **PDK install:** IHP-Open-PDK instead of open_pdks/sky130A; TT's
   IHP template CI pulls the right PDK snapshot automatically; for
   local rootless hardening, mirror the container-free approach with
   the pinned PDK release from
   https://github.com/IHP-GmbH/IHP-Open-PDK **[verify pin against the
   ttihp template's `config`]**.
2. **Template:** `ttihp-verilog-template`
   (https://github.com/TinyTapeout/ttihp-verilog-template) instead of
   the SKY130 template; same `info.yaml` / `tt_um_` top-level / GitHub
   Actions structure.
3. **Cell library:** `sky130_fd_sc_hd` to `sg13g2_stdcell` (9-track,
   3.78 um row height, 1.2 V core). Re-baseline synthesis area and the
   STA scripts' library/corner names; fewer cell variants and drive
   strengths than SKY130 **[quantify during first harden]**.
4. **Density planning:** ~0.9x gates per tile vs SKY130 (B.3) — add
   ~10% area margin when porting SKY130-sized blocks.
5. **Memory:** OpenRAM/DFF-RAM habits replaced by RM_IHPSG13 macro
   instantiation with ECC wrapper; known-nontrivial integration
   (https://tinytapeout.com/specs/memory/) — budget schedule for it.
6. **Signoff:** KLayout-based DRC/LVS instead of Magic/Netgen; the
   precheck differs from the SKY130 precheck accordingly.
7. **Simulation:** unchanged (Icarus/cocotb testbenches port as-is;
   sg13g2 Verilog cell models ship in the PDK).
8. **Timing:** faster process; the 50 MHz TT envelope is comfortable —
   keep the same STA discipline, swap liberty files.

---

## Combined timeline

| Date | Event | Source |
|---|---|---|
| 2026-09-03 | NLnet calls reopen (Restack et al.) | https://nlnet.nl/propose/ |
| **2026-09-21** | **TTIHP26b closes (submit + pay before this date)** | https://app.tinytapeout.com/shuttles/ **[re-confirm]** |
| 2026-10 | Draft Restack application review window; office-hour question slot | https://nlnet.nl/officehour/ |
| **2026-11-03 12:00 CEST** | **NLnet submission deadline** | https://nlnet.nl/propose/ |
| ~2027-01/02 | NLnet selection decision (observed 2-3 month lag) | A.7 **[estimate]** |
| ~2027-02/04 | MoU signed, funded work starts | A.7 **[estimate]** |
| ~2027-03 | TTIHP27a expected close (second-run option) | **[extrapolated, unannounced]** |
| 2027-06-25 | TTIHP26b chips expected (fab run IHP-2609) | https://app.tinytapeout.com/shuttles/ |
| 2027-08-16 | TTIHP26b boards delivered (estimate); bring-up + radiation pre-screening begins | https://app.tinytapeout.com/shuttles/ |

Note the favorable coupling: the TTIHP26b submission (September 2026)
becomes concrete, citable evidence of capability in the NLnet
application (November 2026), and the NLnet grant, if awarded
(early 2027), funds the bring-up, radiation campaign, and the
second-run silicon of the same design line.

## Action items

1. **Decide TTIHP26b entry and freeze pilot-block scope** (8-tile
   content per B.6) — developer. Immediately; the shuttle closes
   2026-09-21.
2. **Port the TT pipeline to `ttihp-verilog-template` and produce a
   first sg13g2 harden of the pilot block** (deltas 1-4, 6 of B.7) —
   engineering.
3. **Prototype RM_IHPSG13 1024x8 integration with the ECC wrapper**
   in the 4x2 floorplan; fall back to latch RAM in a 2x2 if macro
   integration does not close in time — engineering.
4. **Purchase tiles and submit on app.tinytapeout.com** before
   2026-09-21; re-confirm deadline, price, and max-tile policy in the
   dashboard — developer.
5. **Resolve the licensing/publication decision**: make the repo (or a
   public mirror of the NLnet-funded scope) public with Apache-2.0 /
   CERN-OHL-S / CC-BY licensing before the NLnet submission — developer.
6. **Write the Restack application when the call opens 2026-09-03**
   (skeleton in A.8); attach the architecture outline and budget;
   submit at least a week before 2026-11-03 — developer, with
   engineering supplying the comparison matrix and work-package
   estimates.
7. **Scope the radiation pre-screening**: identify a Co-60 TID facility
   and obtain quotes to firm up WP5; locate and cite the primary
   IHP rad-hard 130 nm library paper (B.5 gap) — developer.
8. **Track TTIHP27a announcement** and the IHP MPW/FMD subsidy options
   for the full-SoC run — developer.
