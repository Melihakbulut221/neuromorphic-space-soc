# Management CPU and interface IP survey

Document 03 of the research phase. Scope: (1) selection of the RV32
management core that replaces the GR801's NOEL-V in the 130 nm retarget,
(2) a per-interface survey of open IP for the GR801 interface set.

Conventions used throughout:

- **Fact** — verifiable from the cited source (license text, repository,
  documentation).
- **Estimate** — this project's engineering judgment (gate counts scaled
  to 130 nm, adaptation hours). Estimates are marked "(est.)" and must be
  re-validated when the block enters implementation.
- Effort figures are engineering hours for one person familiar with the
  open flow (Icarus Verilog / Verilator simulation, Yosys synthesis,
  OpenROAD place-and-route), including testbench and fault-injection
  hookup, excluding silicon bring-up.

Carried-over decision rules from prior project experience (confirmed
here, not re-litigated):

1. **The deciding filter is verification observability, not license.**
   The hardening strategy (TMR insertion, fault injection, upset
   counters) requires hand-auditable Verilog RTL where every state
   element can be named, instrumented, and flipped in simulation.
2. **VHDL cores are disqualified** for datapath/control IP. Icarus and
   Verilator do not consume VHDL; GHDL-based conversion produces
   machine-generated Verilog whose signal names and structure defeat
   fault-injection observability and reviewable TMR insertion.
3. Machine-generated Verilog (from SpinalHDL, Chisel, sv2v, GHDL) is
   acceptable only if the output is stable, human-readable, and the
   generator is part of the reproducible build; it is graded case by
   case below.

---

## 1. Management CPU selection

### 1.1 Role and requirements

In GR801 the NOEL-V is a system manager: it boots the chip, configures
the neuromorphic engine, moves data between interfaces and the inference
fabric, and runs housekeeping/telemetry. It is not the compute engine.
The 130 nm equivalent therefore needs:

- RV32IMC class (RV32E acceptable floor; M extension strongly preferred
  for filter/CRC/housekeeping math). No FPU, no MMU.
- Small enough that a TMR or lockstep instance fits the area budget:
  target under ~50 kGE for the unhardened core (est.).
- Hand-auditable Verilog reachable by the open flow (Icarus, Verilator,
  Yosys) without proprietary tools.
- Upstream GCC support and a bare-metal or Zephyr software path.
- A credible story for lockstep or TMR at the core boundary.
- License compatible with open publication and eventual commercial use.

### 1.2 Candidates

#### NOEL-V (Frontgrade Gaisler) — the reference, assessed honestly

- Facts: RV64GC-capable (also configurable down to RV32 subsets),
  dual-issue in-order pipeline, VHDL, distributed inside GRLIB under
  GPL with a paid commercial license option
  (https://www.gaisler.com/products/noel-v,
  https://www.gaisler.com/products/grlib). The GR801 uses the
  fault-tolerant (FT) variant, which is part of the commercial GRLIB-FT,
  not the GPL release.
- Assessment: does not fit this project, for three independent reasons.
  (a) **Size**: a dual-issue RV64GC core with FPU/MMU is hundreds of
  kGE (est.) — at 130 nm it would dominate the die that also has to
  carry an SNN fabric and SRAM. (b) **Language/flow**: VHDL plus deep
  GRLIB/AMBA library coupling violates rule 2; the open Icarus/Yosys
  flow cannot consume it, and extracting a NOEL-V from GRLIB is a
  project in itself. (c) **Hardening access**: the FT features that make
  NOEL-V attractive in GR801 are exactly the parts not in the GPL drop.
  GPL is also viral into surrounding RTL, which conflicts with mixed
  licensing of the rest of the SoC.
- Verdict: rejected. Kept in this document only as the reference point.

#### VexRiscv (SpinalHDL)

- Facts: RV32I[M][C] plugin-based core written in SpinalHDL (Scala),
  which generates plain Verilog; MIT license
  (https://github.com/SpinalHDL/VexRiscv). Very wide deployment in
  LiteX-based SoCs and multiple open-silicon tapeouts; Zephyr supports
  LiteX/VexRiscv targets upstream
  (https://docs.zephyrproject.org/latest/boards/enjoydigital/litex_vexriscv/doc/index.html).
- Estimates: small configurations around 15–35 kGE at 130 nm; the
  README's FPGA datapoints (roughly 500–3000 LUT depending on config)
  support the low end.
- Flow fit: the generated Verilog is Verilog-2001-clean and simulates in
  Icarus/Verilator; Yosys synthesizes it directly. Caveat under rule 3:
  the source of truth is Scala. Any TMR/lockstep instrumentation either
  lives in the SpinalHDL layer (adds a Scala toolchain to the
  reproducible build) or is applied to a frozen generated snapshot
  (loses regeneration). Generated names are readable but not
  hand-written; fault-injection scripts must be regenerated with the
  core.
- Verdict: strong candidate, best-in-class area/performance per gate;
  the generator dependency is the only real cost.

#### Ibex (lowRISC)

- Facts: RV32IMC/EMC (+B options), 2-stage (optional 3-stage)
  SystemVerilog core, Apache-2.0 license
  (https://github.com/lowRISC/ibex). It has a documented security
  configuration (SecureIbex) including **dual-core lockstep with a
  delayed shadow core and output comparison**, ECC on the register file
  and icache, bus integrity, and dummy-instruction insertion
  (https://ibex-core.readthedocs.io/en/latest/03_reference/security.html).
  The top level is deliberately split so RAMs/register file sit outside
  the replicated core logic
  (https://ibex-core.readthedocs.io/en/latest/02_user/integration.html).
  Ibex ships an in-repo open synthesis flow that runs **sv2v then
  Yosys/OpenSTA** (https://github.com/lowRISC/ibex/blob/master/syn/README.md);
  sv2v converts IEEE 1800-2017 SystemVerilog to Verilog-2005
  (https://github.com/zachjs/sv2v). Ibex is in production silicon as the
  OpenTitan Earl Grey core in lockstep configuration
  (https://lowrisc.org/news/ibex-inside-how-and-why-we-built-opentitans-riscv-core/).
  Verification quality is high (co-simulation against Spike, riscv-dv
  random instruction streams, upstream CI).
- Estimates: small RV32IMC configuration roughly 25–45 kGE at 130 nm;
  the lockstep (shadow core plus comparators) approximately doubles the
  core logic, so a SecureIbex-style instance lands near 60–100 kGE
  before memories. A plain core with external project-level TMR is the
  cheaper hardening route if area is tight.
- Flow fit: SystemVerilog is a real cost — Icarus does not handle the
  Ibex SV subset, so the simulation/synthesis input is the sv2v output.
  Mitigations: the sv2v step is already scripted and maintained by
  lowRISC in-repo (the exact path this project would use), sv2v output
  preserves module and signal names well, and Verilator consumes the
  original SV directly for fast simulation. Fault-injection scripts
  target the sv2v output, which is regenerated deterministically.
- Verdict: strong candidate; the only core in the list whose upstream
  has a documented, silicon-proven fault-detection story.

#### PicoRV32 (YosysHQ)

- Facts: RV32E/I[M][C] single-file Verilog-2001 core, ISC license
  (https://github.com/YosysHQ/picorv32). Effectively in maintenance
  mode; enormous deployment history in open-silicon shuttles
  (Caravel/Efabless harness SoCs used it as the management core).
- Estimates: 10–25 kGE at 130 nm depending on configuration (the README
  reports 750–2000 LUTs on FPGA). CPI is about 4 (multi-cycle,
  non-pipelined), so sustained performance is several times below Ibex
  or VexRiscv at the same clock.
- Flow fit: the best in the field — one hand-written Verilog file,
  simulates and synthesizes everywhere, trivially instrumentable.
  Software is bare-metal GCC; no meaningful Zephyr path.
- Verdict: viable low-risk fallback; the performance floor and dormant
  upstream argue against it as primary.

#### SERV (olofk)

- Facts: bit-serial RV32I, ISC license, hand-written Verilog, claims and
  repeatedly demonstrates the smallest RISC-V footprint; Zephyr runs on
  the Servant reference SoC (https://github.com/olofk/serv).
- Estimates: 2–5 kGE at 130 nm; throughput is roughly 1/32 of a
  word-parallel core per cycle — too slow to serve as the SoC manager
  that must feed the inference fabric and service interfaces.
- Verdict: rejected as the management CPU, but noted as an attractive
  ultra-cheap **auxiliary safety monitor / watchdog processor** whose
  TMR costs almost nothing; kept on the shelf for the hardening
  architecture.

#### CV32E40P and CV32E20 (OpenHW Group)

- Facts: CV32E40P is the industrially verified RI5CY successor, 4-stage
  RV32IMC(+F option), SystemVerilog, Solderpad Hardware License 2.x
  (https://github.com/openhwgroup/cv32e40p). CV32E20 (repo name CVE2)
  is OpenHW's small-core track derived from the same zero-riscy lineage
  as Ibex, Apache-2.0 (https://github.com/openhwgroup/cve2).
- Estimates: CV32E40P roughly 50–80 kGE at 130 nm — more core than the
  manager role needs; CV32E20 is essentially an Ibex sibling with a
  younger open-flow story.
- Flow fit: both are SystemVerilog and need sv2v for Icarus/Yosys, like
  Ibex, but neither ships an in-repo open synthesis flow, and neither
  documents a lockstep configuration the way Ibex does.
- Verdict: no advantage over Ibex for this role; CV32E40P additionally
  oversized. Rejected.

### 1.3 Comparison table

Gate counts are (est.) at 130 nm, unhardened core, excluding memories.

| Core | ISA | Source language | License | Gate count (est.) | Open-flow fit | Hardening story | Software | Upstream health |
|---|---|---|---|---|---|---|---|---|
| NOEL-V | RV64GC (config.) | VHDL (GRLIB) | GPL / commercial | 100s of kGE | None (rule 2) | FT variant is commercial-only | GCC, Linux | Active (vendor) |
| VexRiscv | RV32IMC | SpinalHDL -> Verilog | MIT | 15–35 kGE | Good (generated V2001) | DIY; via generator layer | GCC, Zephyr (LiteX) | Active |
| Ibex | RV32IMC(B) | SystemVerilog (sv2v) | Apache-2.0 | 25–45 kGE | Good (in-repo sv2v+Yosys flow) | Documented lockstep, ECC, silicon-proven | GCC, Zephyr (OpenTitan) | Active (lowRISC) |
| PicoRV32 | RV32IMC | Verilog-2001 | ISC | 10–25 kGE | Excellent | DIY (simple core helps) | GCC bare-metal | Maintenance |
| SERV | RV32I | Verilog | ISC | 2–5 kGE | Excellent | Trivial TMR; too slow for role | GCC, Zephyr (Servant) | Active |
| CV32E40P | RV32IMC(F) | SystemVerilog | Solderpad 2.x | 50–80 kGE | Needs own sv2v flow | Verified, no lockstep config | GCC bare-metal | Active (OpenHW) |
| CV32E20 | RV32IMC | SystemVerilog | Apache-2.0 | 25–45 kGE | Needs own sv2v flow | Inherits Ibex lineage, less documented | GCC bare-metal | Active, younger |

### 1.4 Recommendation

**Primary: Ibex (RV32IMC, small configuration).** It is the only
candidate where the fault-tolerance requirement is met by documented,
silicon-proven upstream features (delayed-shadow lockstep, register file
ECC, bus integrity) rather than by this project alone, and its
maintained sv2v+Yosys flow is exactly the open toolchain this project
runs. The SystemVerilog-via-sv2v step is an accepted cost under rule 3:
the conversion is deterministic, scripted upstream, and produces
readable Verilog-2005 that Icarus consumes and fault-injection scripts
can target. Decision point for implementation: plain Ibex + project TMR
(cheaper) versus SecureIbex-style lockstep (upstream-supported); to be
settled by the area budget in `docs/04`.

**Fallback: VexRiscv.** If the sv2v path proves brittle in practice
(conversion regressions, unnameable nets in fault scripts), VexRiscv
provides an MIT-licensed, Verilog-2001-native alternative with the best
area/performance in class, at the cost of adopting the SpinalHDL
generator into the build. PicoRV32 remains a last-resort contingency:
lowest integration risk, lowest performance, dormant upstream.

SERV is additionally recommended — independently of the primary choice —
as a candidate implementation for the hardened housekeeping/watchdog
monitor, where its 2–5 kGE (est.) footprint makes full TMR nearly free.

---

## 2. Interface IP survey

### 2.1 Ground rules and prior findings

Prior findings from a related 130 nm project, adopted as the baseline
here (facts about that project's outcome; hours are estimates):

- CAN: the Mohor SJA1000-style core (LGPL, Verilog, Wishbone, CAN 2.0B —
  **no FD**) was the workable candidate at ~70–110 h adaptation.
- SpaceWire: a from-scratch DS (data-strobe) codec was estimated at
  80–115 h and preferred over existing VHDL cores.
- VHDL cores break the fault-injection/TMR observability flow and are
  disqualified (rule 2).
- The deciding filter is verification observability, not license.

One licensing fact that applies to CAN regardless of which core is
chosen: the CAN protocol is patented/licensed by Bosch, and commercial
silicon implementations require a Bosch CAN protocol license
(stated e.g. in the CTU CAN FD README,
https://github.com/Blebowski/CTU-CAN-FD). This is a
commercialization-phase issue, not a research-phase blocker, but it
must appear in the ROADMAP cost line.

### 2.2 Per-interface analysis

#### SpaceWire (GR801: 4-port router at 200 Mbps)

- Facts: SpaceWire Light (Joris van Rantwijk) is the reference open
  implementation of an ECSS-E-ST-50-12C encoder/decoder — but it is
  **VHDL**, licensed GPLv2 with LGPLv2.1 offered for the non-GRLIB parts
  (https://opencores.org/projects/spacewire_light,
  https://github.com/freecores/spacewire_light). Under rule 2 it is
  disqualified as-is: exactly the conflict flagged in the prior finding.
- New finding: **spacewire_reloaded** (https://github.com/lcapossio/spacewire_reloaded)
  is a modernization of SpaceWire Light that includes a **Verilog-2001
  translation of the standalone (non-GRLIB) core**, replaces the GPL
  GRLIB bus glue with LGPL-intended AXI4-Lite/AXI-Stream wrappers, and
  carries a cocotb regression suite with high line coverage. This is
  the first credible Verilog-language SpaceWire codec found in the open.
  Caveats (est.): translated code must pass an observability audit
  (named state, no opaque generate soup) before it displaces the
  from-scratch plan; license is stated as intended-LGPL, to be confirmed
  in the repo's license file at adoption time.
- Plan: baseline remains the from-scratch DS codec at 80–115 h (est.),
  with spacewire_reloaded as either an adoption candidate (audit ~15 h,
  adaptation 40–70 h if clean, est.) or a behavioral cross-check model
  for the from-scratch codec. The GR801-style 4-port **router**
  (wormhole switching, arbitration, time-codes) is a separate, much
  larger effort (200+ h, est.) and is deferred: phase 1 scopes a single
  codec node, which covers CubeSat point-to-point links.
- Verdict: realistic. Codec in scope; router deferred.

#### CAN / CAN FD (GR801: 2x CAN FD)

- Facts: the Mohor core (https://github.com/freecores/can, LGPL,
  Verilog, Wishbone) implements CAN 2.0B only. **CTU CAN FD** is the
  prominent open CAN FD core, but it is **VHDL** (VHDL-93 RTL), and its
  current upstream license requires a paid agreement for commercial RTL
  use (https://github.com/Blebowski/CTU-CAN-FD); earlier MIT-era
  snapshots survive in forks (e.g.
  https://github.com/AlSaqr-platform/can_bus). Antmicro demonstrated
  taking CTU CAN FD into a custom ASIC by converting the VHDL through
  the GHDL Yosys plugin
  (https://antmicro.com/blog/2022/12/open-source-can-core-for-a-custom-asic/)
  — proving flow feasibility, but the conversion output is exactly the
  machine-generated Verilog that rule 2 exists to keep out of the
  fault-injection perimeter.
- Assessment: **no hand-written open Verilog CAN FD core is known to
  this survey as of August 2026.** Writing one from scratch (new bit
  timing with BRS, new CRC17/CRC21, ISO stuff-count) is a 150–250 h
  class effort (est.) with a demanding compliance test burden.
- Plan: ship CAN 2.0B via the Mohor core (70–110 h adaptation, est.,
  per prior finding), declare FD a documented deviation from GR801, and
  keep two FD options in the ROADMAP appendix: (a) clean-room Verilog
  FD extension of the Mohor timing/CRC path, (b) re-audit of a
  GHDL-converted CTU CAN FD outside the TMR perimeter with black-box
  fault handling. CubeSat buses today are overwhelmingly classic CAN,
  so 2.0B covers the near-term mission profile (est./judgment).
- Verdict: CAN 2.0B realistic; CAN FD not realistic in phase 1 under
  the observability rule.

#### QSPI memory controller (GR801: 2 chip selects)

- Facts: OpenTitan **spi_host** supports standard/dual/quad SPI, is
  Apache-2.0 SystemVerilog and passes through the same sv2v path as
  Ibex (https://opentitan.org/book/hw/ip/spi_host/,
  https://github.com/lowRISC/opentitan). ZipCPU's qspiflash controller
  is Verilog but GPLv3 (https://github.com/ZipCPU/qspiflash), which
  is viral into the SoC — avoided.
- Assessment: a QSPI flash read/XIP controller with 2 CS is a small,
  well-understood block; from-scratch is 60–100 h (est.) including an
  XIP AHB/AXI-lite front end; adopting spi_host is attractive if Ibex
  (and thus the sv2v flow) is confirmed, 40–70 h integration (est.).
- Verdict: realistic. Candidate: OpenTitan spi_host (Apache-2.0, SV via
  sv2v) or from-scratch Verilog.

#### SPI master (GR801: 1x, 2 chip selects)

- Facts: simple SPI masters exist on OpenCores (e.g. R. Herveille's
  simple_spi, permissive BSD-style header, Verilog, Wishbone,
  https://opencores.org/projects/simple_spi).
- Assessment: 20–40 h (est.) whether adapted or rewritten; this block
  is small enough that from-scratch with a project-standard register
  interface is often cheaper than auditing third-party code.
- Verdict: realistic, trivial.

#### I2C (GR801: 2x)

- Facts: **alexforencich/verilog-i2c** — MIT, hand-written Verilog,
  master and slave, well-regarded testbenches
  (https://github.com/alexforencich/verilog-i2c). The classic OpenCores
  i2c controller (Herveille) is Verilog with a permissive BSD-style
  header (https://opencores.org/projects/i2c).
- Assessment: 30–50 h (est.) for adaptation of verilog-i2c including
  register-interface glue and observability hookup.
- Verdict: realistic. Candidate: alexforencich/verilog-i2c (MIT,
  Verilog).

#### UART (GR801: 3x)

- Facts: **alexforencich/verilog-uart** — MIT, hand-written Verilog
  (https://github.com/alexforencich/verilog-uart). ZipCPU wbuart32 is
  GPLv3 (https://github.com/ZipCPU/wbuart32) — avoided for license
  virality, not quality.
- Assessment: 20–40 h (est.) for three instances plus FIFOs and a
  common register map; a UART is also a natural first TMR
  demonstration block.
- Verdict: realistic, trivial. Candidate: alexforencich/verilog-uart
  (MIT, Verilog).

#### GPIO (GR801: 16x)

- Assessment: register-file block with direction/interrupt logic;
  from-scratch under 20 h (est.). No third-party IP justified.
- Verdict: realistic, trivial, from-scratch.

#### CPI — Camera Parallel Interface (GR801: 8-bit)

- Facts: CPI in the GR801 brief is an 8-bit parallel input; the
  commodity equivalent is the OV7670/OV5640-class DVP interface (pixel
  clock, HREF/HSYNC, VSYNC, 8 data bits). Countless open FPGA capture
  examples exist; the logic is a synchronizer, line/frame framing, and
  a CDC FIFO into on-chip SRAM or a DMA channel.
- Assessment: this is the cheapest "headline" interface on the chip and
  directly feeds the SNN vision use case. From-scratch 40–80 h (est.)
  including CDC verification and a frame-capture testbench. From-scratch
  is preferred over adapting any specific open example because the block
  is small and the DMA/SRAM back end is project-specific.
- Verdict: realistic and cheap; in scope, from-scratch.

#### PCIe Gen3 x4 — out of scope, with reasons

- Facts: PCIe Gen3 runs 8 GT/s per lane with 128b/130b coding; even
  Gen1 requires a 2.5 GT/s SerDes. SerDes/PHY blocks are mixed-signal
  IP that does not exist in open form for 130 nm open PDKs; open PCIe
  work such as alexforencich/verilog-pcie explicitly targets FPGA
  **hard** PCIe blocks, not a soft PHY
  (https://github.com/alexforencich/verilog-pcie).
- Assessment: 8 GT/s is beyond 130 nm digital logic regardless of IP
  availability (est.: practical 130 nm SerDes designs top out around
  2.5–3.2 Gbps and are full-custom analog projects on their own).
  There is no realistic path in this project's flow or budget.
- Verdict: out of scope. The bandwidth role (host offload) is covered
  architecturally by SpaceWire plus QSPI staging at CubeSat data rates.

#### Gigabit Ethernet (GMII) — out of scope, with reasons

- Facts: open, high-quality GbE MAC RTL exists — alexforencich's
  verilog-ethernet, MIT, Verilog
  (https://github.com/alexforencich/verilog-ethernet) — and GMII/RGMII
  assumes an **external PHY chip**, so no on-die SerDes is needed
  (unlike PCIe).
- Assessment: this makes GbE the "closest to feasible" of the two
  excluded interfaces; the blockers are practical, not absolute
  (est.): 125 MHz GMII/RGMII DDR I/O timing closure at 130 nm on an
  open flow is tight; a space-grade external GbE PHY contradicts the
  low-cost CubeSat BOM; and the mission profile's telemetry/payload
  rates are served by SpaceWire at 100–200 Mbps. Verification of a
  MAC+DMA+stack path would consume hundreds of hours better spent on
  the SNN fabric.
- Verdict: out of scope for phase 1; revisit only if a mission
  requirement demands it, using verilog-ethernet as the known-good
  candidate.

### 2.3 Verdict table

Hours are (est.); "language" is the language the project would actually
integrate.

| Interface | GR801 spec | 130 nm open-flow verdict | Candidate IP | License | Language | Effort (est.) |
|---|---|---|---|---|---|---|
| SpaceWire codec | Router 4x, 200 Mbps | Realistic (codec only; router deferred) | From-scratch DS codec; spacewire_reloaded as candidate/reference (https://github.com/lcapossio/spacewire_reloaded) | n/a / LGPL-intended | Verilog | 80–115 h scratch; 55–85 h if adoption audit passes |
| CAN | 2x CAN FD | CAN 2.0B realistic; FD not in phase 1 | Mohor CAN (https://github.com/freecores/can) | LGPL | Verilog | 70–110 h |
| CAN FD | — | Not realistic under observability rule | CTU CAN FD is VHDL + commercial license upstream (https://github.com/Blebowski/CTU-CAN-FD); no hand-written open Verilog FD core found | — | — | 150–250 h if clean-room FD later |
| QSPI (2 CS) | Memory controller | Realistic | OpenTitan spi_host (https://opentitan.org/book/hw/ip/spi_host/) or from-scratch | Apache-2.0 | SV via sv2v / Verilog | 40–100 h |
| SPI (2 CS) | 1x master | Realistic, trivial | From-scratch or simple_spi (https://opencores.org/projects/simple_spi) | BSD-style | Verilog | 20–40 h |
| I2C | 2x | Realistic | alexforencich/verilog-i2c (https://github.com/alexforencich/verilog-i2c) | MIT | Verilog | 30–50 h |
| UART | 3x | Realistic, trivial | alexforencich/verilog-uart (https://github.com/alexforencich/verilog-uart) | MIT | Verilog | 20–40 h |
| GPIO | 16x | Realistic, trivial | From-scratch | n/a | Verilog | <20 h |
| CPI camera | 8-bit parallel | Realistic and cheap | From-scratch DVP capture | n/a | Verilog | 40–80 h |
| PCIe | Gen3 x4 | Out of scope (SerDes/PHY impossible at 130 nm open flow) | — | — | — | — |
| GbE | 10/100/1000 GMII | Out of scope (I/O timing, PHY BOM, verification cost) | (verilog-ethernet if ever revisited, https://github.com/alexforencich/verilog-ethernet) | MIT | Verilog | — |

### 2.4 Roll-up and consequences for the ROADMAP

- Total interface effort, phase-1 scope (SpaceWire codec, CAN 2.0B,
  QSPI, SPI, I2C, UART, GPIO, CPI): roughly 320–555 h (est.) before
  TMR insertion and fault-injection campaigns.
- Every selected interface IP is hand-written (or hand-auditable)
  Verilog under MIT/LGPL/BSD-style/Apache licenses; no GPL RTL enters
  the SoC; the only GPL-family item is LGPL (Mohor CAN, and
  spacewire_reloaded if adopted), consistent with the prior project's
  accepted position.
- Two deviations from GR801 must be stated openly in positioning
  documents: CAN FD downgraded to CAN 2.0B, and SpaceWire router
  reduced to a single codec node. Both are defensible for the
  CubeSat-class mission profile and both have documented upgrade paths.
- The Bosch CAN protocol license is a commercialization cost item
  independent of IP choice.
- The CPU recommendation (Ibex via sv2v) and the QSPI candidate
  (OpenTitan spi_host via sv2v) share one toolchain dependency; if the
  sv2v path is rejected during CPU bring-up, both fall back together
  (VexRiscv + from-scratch QSPI), which keeps the decision coupled and
  should be resolved by a single early prototype milestone.
