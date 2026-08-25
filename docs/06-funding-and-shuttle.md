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
| WP3 Shuttle silicon | TTIHP26b pilot (8 tiles ~EUR 560 default, 12 tiles ~EUR 840 for the SRAM-macro variant, per B.6) + follow-up TT run gated per B.6.2 (TTIHP27a on pre-silicon evidence, or silicon-results-gated TTIHP27b/IHP MPW; 16-32 tiles, EUR 1,120-2,240) + devkits/breakout PCBs | 3,500 |
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
  closes before TTIHP26b silicon exists, so it can only serve as a
  pre-silicon-gated follow-up slot (B.6.2).

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

- **PDK:** IHP-Open-PDK is actively developed and released (June 2026
  release documented at https://ihp-open-pdk-docs.readthedocs.io/;
  https://www.ihp-microelectronics.com/services/research-and-prototyping-service/fast-design-enablement/open-source-pdk).
  However, IHP's own documentation describes the current content as an
  "experimental preview" / "alpha release" that "is not intended to be
  used for production at this moment", to be tagged with a production
  version when ready (https://ihp-open-pdk-docs.readthedocs.io/,
  re-checked 2026-08-25) — the same caveat docs/04 carries. **[fact]**
  The underlying SG13G2 process and the commercial PDK are
  production-proven; the caveat applies to the open design-kit views,
  not the silicon.
- **LibreLane:** the TT flow itself hardens IHP projects with LibreLane
  (https://github.com/TinyTapeout/ttihp-verilog-template), and IHP
  publishes its own LibreLane full-chip templates
  (https://github.com/IHP-GmbH/ihp-sg13cmos5l-librelane-template).
  OpenROAD-flow-scripts carries an `ihp-sg13g2` platform
  (https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/tree/master/flow/platforms/ihp-sg13g2).
  DRC/LVS is KLayout-based; Magic/Netgen integration is newer and still
  maturing (https://wiki.f-si.org/index.php?title=IHP_Open_PDK_integration_with_Magic,_Netgen,_and_LibreLane).
  Verdict: the digital flow is proven at TT scale (hundreds of shipped
  designs per IHP shuttle), while the open PDK itself remains
  pre-production per the caveat above.
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

- A 112 Gb/s radiation-hardened optical transceiver was designed in
  **SG13RH** — the rad-hard sibling PDK of SG13G2, not the open PDK —
  in IHP 130 nm SiGe BiCMOS
  (https://www.researchgate.net/publication/351632595_A_112_Gbs_Radiation-Hardened_Mid-Board_Optical_Transceiver_in_130-nm_SiGe_BiCMOS_for_Intra-Satellite_Links).
  The paper reports **no irradiation of the transceiver itself**; it
  cites prior characterization of the technology: SiGe HBTs evaluated
  to TID levels of **1.2 Mrad(Si)**, and the RH standard-cell library
  free of SEU and SEL up to **LET 62 MeV cm2/mg**. **[fact — SG13RH
  results; they transfer to SG13G2 only via the shared 130 nm CMOS
  backbone, per docs/04 section 1.2]**
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

The 2x2 default this section previously recommended has been overtaken
by measurement. `docs/15-pilot-tile-plan.md` section 4 hardened the
actual pilot RTL through the complete `Classic` flow: the design places
**136,107 um2** of standard cells, and the tile geometry is now read
out of `tt-support-tools` `tech/ihp-sg13g2/tile_sizes.yaml` and the DEF
templates rather than interpolated, giving **126,685 um2** of placement
rows in a 2x2 block and **259,837 um2** in a 4x2 **[fact, docs/15
sections 4.1 and 4.3]**. 2x2 would need 107.4 % utilization — not tight
but impossible — and 4x2 closed at 52.38 % with zero DRC, LVS, antenna
and timing violations. **The flip-flop-RAM pilot is a 4x2 = 8-tile
design; that is measured, not projected.**

| Option | Tiles | Cost | Content | Verdict |
|---|---|---|---|---|
| **Default pilot (TTIHP26b)** | **4x2 = 8** | **~EUR 560 + devkit** | 8 LIF neurons x 8 axons with flip-flop 4-bit weights, AER event queues, serial host port, (72, 64) SECDED weight-word codec, TMR-voted configuration, fault counters and four fault pins (docs/15 section 1) | **Default.** No SRAM-macro dependency. Hardened end to end at this shape: 52.38 % utilization, 0 DRC, 0 LVS, 0 antenna, 0 timing violations on three corners **[fact, docs/15 section 5.3]** |
| Superseded: 2x2 = 4 minimal pilot | 2x2 = 4 | ~EUR 280 + devkit | 16-32 LIF neuron crossbar (tt-um-lif-crossbar lineage), latch/FF-based 4-bit weights, event interface, TMR/EDAC demonstrator counters | **Not available.** Needs 107.4 % of the 2x2 placement rows for the content above; the synthesis netlist alone is 85.1 % of a 2x2 before a single repair buffer **[fact, docs/15 section 4.3]** |
| SRAM-macro variant (only if the 2026-09-07 go/no-go passes) | 3x4 or 6x2 = 12 | ~EUR 840 + devkit | The 8-tile content above with the flip-flop synapse file replaced by one `RM_IHPSG13_1P_512x32` (16 kbit) or `1P_512x16` (8 kbit) macro under an ECC read path plus a scrubber, and the fault counters restored to their full 32-bit register-map width | **12 tiles, not 8.** Macro plus halo reserves 92,280 um2 and the logic needs 194,439 um2 of rows at 70 %, i.e. 286,719 um2 against 4x2's 259,837 = 110.3 % **[fact for the areas, estimate for the halo and the utilization; docs/15 section 6]**. Confirm the purchasable shape with Tiny Tapeout: the template's `info.yaml` comment lists no four-row shape while `tile_sizes.yaml` carries 3x4 |
| Full-SoC attempt | 8x4 = 32 | ~EUR 2,240 | RV32 manager + multi-node SNN + SpaceWire codec + ~16 KB ECC SRAM (4x 1024x32 macros ~ 15 tiles, ~45 kGE logic left) | Marginal; TTIHP27a only on pre-silicon evidence — TTIHP26b silicon arrives after TTIHP27a closes (B.6.2) |
| Product MVP | — | — | Hundreds-of-kB SRAM class | Not possible on TT; needs a dedicated IHP MPW slot (price list: https://www.ihp-microelectronics.com/services/research-and-prototyping-service/mpw-prototyping-service/schedule-price-list), potentially FMD/university-subsidized **[investigate]** |

The macro named in the earlier revision of this table, "one RM_IHPSG13
1024x8 macro (~2 tiles)", is withdrawn on geometry rather than on area.
`RM_IHPSG13_1P_1024x8_c2_bm_bist` is **336.46 um** tall **[fact,
installed PDK LEF `SIZE`]** and every two-row Tiny Tapeout block on this
technology — 1x2 through 8x2 — is **313.74 um** tall **[fact,
`tt-support-tools` `tech/ihp-sg13g2/tile_sizes.yaml`]**. The macro is
taller than the block it was gated against, before any halo, PDN ring or
core margin. Every 1024-word part in the family shares that height.
The parts that fit a two-row block are the 191.34 um `1P_512x32` and
`1P_512x16` and the 118.78 um `1P_256x32` (docs/12 section 6.5).

**Recommendation (revised 2026-08-25, after the flow run): the TTIHP26b
submission is the 4x2 = 8-tile flip-flop-RAM pilot — 8 neurons x 8
axons with the SECDED and TMR demonstrators on the real datapath, no
RM_IHPSG13 dependency. The submission tree exists at that shape and
closes to a GDS locally (docs/15). The SRAM-macro variant is a 12-tile
design and is gated by B.6.1. The full-SoC integration is gated per
B.6.2.**

### B.6.1 Effort budget and go/no-go against the 2026-09-21 close

As of 2026-08-25 there are **27 days** to the TTIHP26b close. The
developer is solo and time-sliced across other projects; sustainable
capacity for this pilot is taken as ~2-3 h/day, i.e. **~55-80 h
total** to the deadline **[estimate]**. At HEAD the verified RTL base
is one block (`hw/rtl/aer_fifo.v` plus the generated `npu_regs.vh`);
everything below is new work.

Hour budget for the **default pilot** (all figures [estimate]; unit
costs consistent with docs/03 and docs/09 where they exist). The budget
is unchanged from the revision that assumed 2x2: the tile-count
correction in B.6 changes the shape the design is placed in, not the
work it takes to build it, and the flow iterations were budgeted
loosely enough to absorb a bigger block.

| Item | Hours |
|---|---|
| Port TT pipeline to `ttihp-verilog-template`, pin the PDK, swap liberty/STA scripts (B.7 deltas 1-4, 6) | 8-12 |
| LIF crossbar slice + FF 4-bit weight storage + event interface, adapted from the tt-um-lif-crossbar lineage | 15-25 |
| TMR/EDAC demonstrator counters + register hookup | 6-10 |
| Verification of the new slice against the golden model; existing formal/CI jobs kept green | 10-16 |
| sg13g2 harden iterations, precheck, submission and payment | 10-16 |
| **Total** | **49-79** |

The total fits the ~55-80 h capacity only if the low-to-mid estimates
hold; the upper bound consumes the entire capacity. The default scope
therefore has **no slack for the SRAM macro**. The **SRAM-macro
variant** adds on top of the above: `RM_IHPSG13_1P_512x32` (or
`1P_512x16`) + ECC-read-path and scrubber integration closed through
DRC/LVS in the local rootless flow (~25-50 h, given the open
LVS/GDS-merge issues that docs/04 calls "exactly the kind of issue that
costs weeks at tapeout time"), sequencer or SERV integration
(~10-20 h), UART host link (20-40 h per the docs/03 verdict table), and
a larger floorplan/timing pass (~8-16 h) — **~65-125 h additional
[estimate]**, i.e. out of reach of the remaining capacity unless the
macro work closes early. It also costs a further ~EUR 280, because the
macro variant is 12 tiles rather than 8 (B.6).

**Go/no-go date: 2026-09-07** (14 days before close). **The gate
decides macro content, not tile count.** 4x2 = 8 tiles is what the
flip-flop-RAM pilot needs anyway and is what the submission tree is
built at; the question the gate answers is whether the synapse file
inside those tiles is flip-flops or an SRAM macro — and, if it is a
macro, whether the shuttle order is raised to 12 tiles to hold it.

The SRAM-macro variant is taken only if, by that date, all three hold:

1. an `RM_IHPSG13_1P_512x32` or `1P_512x16` macro with its ECC read
   path passes DRC **and** LVS in the local rootless flow at the block
   shape it would actually ship in (`1024x8` is withdrawn: it is taller
   than any two-row block, B.6);
2. a 12-tile shape is purchasable for TTIHP26b — confirm with Tiny
   Tapeout, since `tile_sizes.yaml` carries 3x4 and the template's own
   `info.yaml` comment lists only two-row shapes (docs/15 section 6);
3. the ~65-125 h above fits what is left of the capacity.

Otherwise the 8-tile flip-flop-RAM pilot is submitted as it stands and
the macro-integration learning moves to the TTIHP27a pre-silicon track
(B.6.2).

**Status as of 2026-08-25, ahead of the gate date:** condition 1 has
been tested and fails. `docs/12-sg13g2-flow-bringup.md` sections 7 and
8 hardened one `RM_IHPSG13_1P_512x32_c2_bm_bist` in a registered
wrapper — i.e. without the ECC read path, strictly easier than the gate
asks for — and it places, routes and closes timing, but does not sign
off: Magic DRC and KLayout DRC both report errors that are 100 % inside
the vendor macro geometry, and Netgen LVS fails on CDL-versus-GDS
hierarchy naming (IHP-Open-PDK issue #239) plus a bus-delimiter
mismatch. Both blocking causes are upstream of this repository. The
recommendation recorded there is **NO-GO for TTIHP26b**; the gate can
be closed early on that evidence.

### B.6.2 Second-run gating — corrected

The earlier framing "second run (TTIHP27a) after pilot results" does
not close against this document's own dates: TTIHP26b silicon is
expected 2027-06-25 (boards ~2027-08-16), roughly three months
**after** the extrapolated TTIHP27a close (~2027-03). No pilot silicon
result can exist before TTIHP27a closes. **[fact — dates per B.1]**
The gate is therefore redefined:

- **TTIHP27a (target, ~2027-03):** gated on **pre-silicon evidence**
  only — a clean sg13g2 harden of the enlarged design, RM_IHPSG13
  macro integration closed through DRC/LVS, and the formal/CI suite
  green on the pilot flow. Funding reality: with MoU start ~2027-02/04
  and disbursements following published milestones (A.7), a TTIHP27a
  tile purchase would be out-of-pocket, not grant-funded.
- **Silicon-results-gated run:** retargeted to **TTIHP27b (~autumn
  2027 [extrapolated, unannounced])** or an IHP MPW slot, chosen after
  TTIHP26b bring-up data exists (boards ~2027-08-16).

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
| **2026-09-07** | **Pilot go/no-go on macro content: the 12-tile SRAM-macro variant only if an `RM_IHPSG13_1P_512x32`/`1P_512x16` with its ECC read path closes DRC/LVS in the local rootless flow and a 12-tile shape is purchasable; otherwise submit the 8-tile flip-flop-RAM pilot. Already answerable NO-GO on the docs/12 evidence** | B.6.1 |
| **2026-09-21** | **TTIHP26b closes (submit + pay before this date)** | https://app.tinytapeout.com/shuttles/ **[re-confirm]** |
| 2026-10 | Draft Restack application review window; office-hour question slot | https://nlnet.nl/officehour/ |
| **2026-11-03 12:00 CEST** | **NLnet submission deadline** | https://nlnet.nl/propose/ |
| ~2027-01/02 | NLnet selection decision (observed 2-3 month lag) | A.7 **[estimate]** |
| ~2027-02/04 | MoU signed, funded work starts | A.7 **[estimate]** |
| ~2027-03 | TTIHP27a expected close — pre-silicon-gated follow-up option (B.6.2); precedes TTIHP26b silicon | **[extrapolated, unannounced]** |
| 2027-06-25 | TTIHP26b chips expected (fab run IHP-2609) | https://app.tinytapeout.com/shuttles/ |
| 2027-08-16 | TTIHP26b boards delivered (estimate); bring-up + radiation pre-screening begins | https://app.tinytapeout.com/shuttles/ |
| ~2027-09/10 | TTIHP27b expected close — earliest silicon-results-gated run (B.6.2) | **[extrapolated, unannounced]** |

Note the favorable coupling: the TTIHP26b submission (September 2026)
becomes concrete, citable evidence of capability in the NLnet
application (November 2026), and the NLnet grant, if awarded
(early 2027), funds the bring-up, the radiation campaign, and the
silicon-results-gated follow-up run (TTIHP27b or an IHP MPW, per
B.6.2). A pre-silicon TTIHP27a entry (~2027-03) would precede first
disbursements and be out-of-pocket (A.7).

## Action items

1. **Decide TTIHP26b entry and freeze pilot-block scope** (4x2 = 8-tile
   flip-flop-RAM content per B.6, with the SRAM-macro variant gated per
   B.6.1) — developer. Immediately; the shuttle closes 2026-09-21.
   Buying 8 tiles rather than 4 raises the shuttle line from ~EUR 280
   to ~EUR 560, which WP3 already carries.
2. **Port the TT pipeline to `ttihp-verilog-template` and produce a
   first sg13g2 harden of the pilot block** (deltas 1-4, 6 of B.7) —
   engineering. **Done**: `tt/` is generated and the design closes to a
   GDS at 4x2 locally (docs/15 sections 5.3 and 8).
3. **Prototype RM_IHPSG13 integration with the ECC read path** against
   the 2026-09-07 go/no-go (B.6.1) — engineering. **Done, negative**:
   `RM_IHPSG13_1P_512x32_c2_bm_bist` places, routes and closes timing
   but fails Magic DRC, KLayout DRC and Netgen LVS on causes that are
   entirely inside the vendor views (docs/12 sections 7 and 8). The
   8-tile flip-flop-RAM pilot is what is submitted.
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
8. **Track the TTIHP27a and TTIHP27b announcements** and the IHP
   MPW/FMD subsidy options for the follow-up runs (gating per B.6.2) —
   developer.
