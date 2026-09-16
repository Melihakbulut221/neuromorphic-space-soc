# ROADMAP

Phased plan for the Neuromorphic Space SoC: a GR801-class fault-tolerant
neuromorphic SoC (RISC-V management core + event-driven LIF inference
engine + spacecraft interfaces) on 130 nm, IHP SG13G2 primary / SKY130
fallback (docs/04), open RTL-to-GDS flow, solo developer.

Effort figures are tagged with their source document; unsourced figures
are [estimate]. **[fact]** = measured in this environment or read out of
a file in the working tree; **[planned]** = an intention with a date
attached and no artifact behind it yet.

> **AMENDED 2026-09-12, and the amendment is the same defect this
> revision was written to fix.**
>
> The 2026-09-05 revision below opens by observing that its predecessor
> "cited nothing above `docs/34`" while thirty-four documents had
> landed. Between 2026-09-05 and 2026-09-12 **thirteen more landed --
> `docs/69` through `docs/81`** -- and this file cited none of them until
> an audit on 2026-09-11 forced citations to `docs/74`, `docs/75`,
> `docs/77`, `docs/79` and `docs/81` into the sections they bear on.
> **Eight are still uncited here**: `docs/69` (the boot block's
> campaign), `docs/70` through `docs/73` (the post-GRT resizer and the
> CLINT placement probe), `docs/76` (the second and third clock gates),
> `docs/78` (the public mirror) and `docs/80` (the artefact digests).
>
> They are uncited rather than contradicted -- nothing in the sections
> below is false because of them -- but a roadmap that cites no document
> from the last week is a roadmap written from memory, which is exactly
> the sentence the paragraph below wrote about its own predecessor. It
> recurred within seven days of being named. `docs/00-index.md` section
> 5 is the complete list and is the thing to read instead of this file
> for what exists.
>
> **Revised 2026-09-05. What this revision does, and why it was needed.**
>
> The previous revision was issued 2026-08-31 and cited nothing above
> `docs/34`. Between 2026-08-31 and 2026-09-05 — **six calendar days**
> — thirty-four documents landed, `docs/35` through `docs/68`
> **[fact, `git log --diff-filter=A -- docs/`; `docs/35` to `docs/67`
> are committed in that window and `docs/68` is in the working tree at
> the time of writing]**. In that window the
> management core was brought up, the fabric and the memory map were
> frozen, the accelerator was connected and later fed from flash, seven
> fault-injection campaigns were run and measured, the SoC was
> synthesised whole, placed and routed, its power measured under a
> mission duty cycle, riscv-formal was run against the core, GPIO and
> QSPI were built, and the memory was protected.
>
> None of that was in this plan. Section 2 now says, phase by phase,
> what is done and which document is the evidence; section 2.7 says
> which gates were **overtaken by events** rather than met; section 3
> is the estimate-versus-outcome record, which is the part of this
> document with the most reusable content in it. Nothing that was
> written down and then refuted has been deleted — where a plan was
> wrong, the plan and the measurement that refuted it are both here.

## 1. External clocks

| Date | Event | Consequence |
|---|---|---|
| 2026-09-03 | NLnet calls reopened (Restack fund) | open-licensing decision must be made; application drafting is in its final pass (docs/13) |
| ~~2026-09-07~~ | ~~Internal go/no-go: RM_IHPSG13 SRAM macro closes DRC/LVS in the local rootless flow~~ | **Superseded 2026-08-25 by `docs/12` section 8, thirteen days early: NO-GO.** The experiment was run under conditions strictly easier than the gate asked for and returned 1,106,478 Magic error boxes, 2,316 KLayout errors and 359 LVS errors, all inside the vendor macro **[fact, docs/12 section 7.5]**. `docs/54` sharpens it: the KLayout count is 100 % a property of the vendor cell as shipped, with this project's flow contributing zero, and the deck swap that would exit it trades a verified deck for an unverified one. **The macros still cannot be signed off on this PDK version, and every physical result for the SoC inherits that.** |
| **2026-09-21, 20:00 UTC (23:00 Istanbul)** | **TTIHP26b closes (fab IHP-2609)** | ~~**Sixteen days out.**~~ **Ten days out, counted 2026-09-11.** Pilot design frozen and submitted. The engineering is complete; the remaining steps are owner actions and ~~one of them is blocked on `docs/14` (P1 below)~~ **none of them is blocked on `docs/14`**. *Corrected 2026-09-11. The day count was written on 2026-09-05, when sixteen was right, and was never moved. The licence clause stopped being true on 2026-09-09: `docs/14-licensing-decision.md` carries `SIGNED 2026-09-09`, the root `LICENSE` exists, `tt/LICENSE` is the full CERN-OHL-W-2.0 text at 310 lines, and `tt/LICENSE.PENDING.md` was deleted by commit `13402ad` **[fact, all four read off the tree]**. P1 below had recorded all four two days before this row was last touched, so the file was directing work from a state its own next section said no longer existed. What is open is the slot purchase and the push — section 4* |
| 2026-11-03, 12:00 CEST | NLnet Restack submission deadline | application submitted. Internal submission target 2026-10-29 (docs/13 section 8) |
| spring 2027 (date TBC, **unannounced**) | TTIHP27a would close | full-SoC slot IF a pre-silicon gate passed. `docs/37` records that **no IHP run after 26b is announced** **[fact]**, so this row is an extrapolation and is tagged as one |
| 2027-06-25 | TTIHP26b silicon arrives (boards ~2027-08) | pilot bring-up and characterization |
| H2 2027 | TTIHP27b / IHP open-source MPW | silicon-results-gated full-SoC run (docs/06 revised gate) |

The pilot-first strategy: silicon-prove the PDK, the flow, an SNN slice,
and the hardening demonstrators on a cheap TT run before committing the
full SoC. That strategy is intact, and one thing has changed under it:
**the full SoC now exists in RTL and has been through synthesis and
place-and-route, so the second run is no longer gated only on the
pilot's silicon.** It is gated on two things the pilot cannot settle —
the SRAM macro sign-off blocker above, which is upstream, and a timing
constraint the layout does not meet (P3 workstream 6).

## 2. Phases and gates

### P0 — Baseline closure (closed 2026-08-25)

Gate G0: docs/07 blocking list closed; sg13g2 trial harden DRC/LVS clean
on at least one block. **Met 2026-08-25** by run `trial-03-signoff` on
`aer_fifo`: all 80 flow stages completed in 680 s with Magic DRC 0,
KLayout DRC 0 (deep, no-recommended), Netgen LVS 0 on all seven
counters, XOR 0, antenna 0 nets and 0 pins after detailed routing,
0 disconnected pins, 0 power-grid violations, and 0 setup, hold,
max-slew and max-cap violations across all three corners. Recorded with
pinned tool and PDK versions in `docs/12-sg13g2-flow-bringup.md`.

**Re-met on the current design, 2026-09-11, by run `g0gates2`** — the
same zeros with all four corner checkers live, 17 of 19 in-flow checkers
gating fully, on RTL that includes the replicated queue pointers.
`docs/12` section 4 now cites that run and section 4.7a keeps this one
beside it. What follows is why the move was necessary.

**Scope correction, 2026-09-11. The gate is met and the sentence above
is true; what it is true OF is narrower than it reads.**
`trial-03-signoff` ran on **2026-08-25**. On **2026-08-29**, commit
`c5a5a6e` replicated the AER queue pointers, and the replication
defence in `hw/rtl/aer_fifo.v` is `keep_hierarchy` on twelve bank
instances plus the POL+MIX storage transform. So every number in the
paragraph above was measured on an `aer_fifo` **without replicated
pointers**, and no run since has produced a comparable one: under the
flatten this config was still using, yosys honours the attribute, nine
`$paramod` submodule types survive, and `librelane/steps/pyosys.py`
counts every cell type whose name begins with `$` as unmapped -- so a
parameterised user module is counted the same as a gate that failed to
map, and the flow stops at `Checker.YosysUnmappedCells` with *"9
Unmapped Yosys instances found"*. **Nothing was unmapped**: inside those
nine, every cell is an sg13g2 cell.

`hw/openlane/pilot_ihp`, `hw/openlane/pilot_sky130` and `tt/src` have
all carried `SYNTH_HIERARCHY_MODE: deferred_flatten` against exactly
this failure since before the pointers were replicated, and
`pilot_sky130`'s own comment describes it verbatim. **The block's own
sign-off configuration was the one that did not**, and for thirteen days
it could not build the block's RTL -- invisible because nothing re-ran
it. *(Thirteen, not eleven, corrected 2026-09-12: the window runs from
`c5a5a6e` on 2026-08-29 to `g0gates2` on 2026-09-11. "Eleven" was
computed from `b6738e5`, the freeze commit this paragraph used to name
by mistake.)* The key is now set, with the reasoning, in
`hw/openlane/aer_fifo/config.json`, and `g0gates2` is the run it made
possible. `trial-03-signoff` is not re-run and its numbers stand as
recorded (`docs/64`), in `docs/12` section 4.7a.

### P1 — TTIHP26b pilot (to 2026-09-21) — engineering complete, owner actions open

**Status 2026-09-05: unchanged from 2026-08-31 in substance, and the
deadline is sixteen days out.** *(Corrected 2026-09-12: the same
find-and-replace left this reading "now eleven days as of 2026-09-10
out" inside a sentence dated 2026-09-05, so the line carried two dates
and agreed with neither. Sixteen is right for 2026-09-05. As of
2026-09-12 it is **nine days**, and section 4 is where the live count
belongs.)* The pilot is signed off at
6x2 = 12 tiles and the RTL is frozen. Every geometric and timing counter
reads zero on the run built from the file the Tiny Tapeout tooling
actually hardens, the derate is proven applied in the flow-written
constraints, the slow corner closes at +1.2262 ns, the Tiny Tapeout
precheck passes ten of ten, and thirty-five census guards confirm the
redundancy is present in the shipped netlist rather than only in the
source. `docs/31-signoff-6x2.md` is the record and
`docs/34-pilot-freeze.md` pins the artifact set by hash.

Two decisions are superseded by measurement and kept for the record: the
tile shape moved from 4x2 to 6x2 when the design outgrew the 70 percent
planning criterion (`docs/22`, `docs/23`); and the 2026-09-07 SRAM-macro
go/no-go was overtaken (section 1).

What remains is not engineering: a Tiny Tapeout account, a TTIHP26b 6x2
slot, **EUR 955** — twelve tiles at EUR 70 is EUR 840, plus the EUR 300
devkit subsidised to EUR 100 while 88 of the first 100 remain, plus
EUR 15 of shipping **[fact, docs/37 section 3]** — and a push to a
repository so the GDS action and the hosted precheck can run.

~~**The push is blocked, and the block has not moved since 2026-08-25.**
A Tiny Tapeout submission is a public repository; `tt/LICENSE.PENDING.md`
in the generated tree says so in its own words and refuses to carry a
`LICENSE` file until `docs/14` is signed. `docs/14` is unsigned, its own
signature deadline of 2026-08-31 has passed, and there is no `LICENSE`
file at the repository root **[fact, `ls` at HEAD `ed51de0`]**. This is
the single item on this roadmap where sixteen days of engineering
capacity cannot substitute for one signature.~~ *(The "sixteen days" in
that struck sentence is restored 2026-09-12: a blind find-and-replace
had rewritten it to "eleven days as of 2026-09-10", inside a paragraph
`docs/64` says to leave exactly as it was written. A struck paragraph is
a record of what was believed on its date; editing its numbers makes it
a record of nothing.)*

**UNBLOCKED 2026-09-09, and this file was the last place still saying
otherwise.** All four of that paragraph's facts are now false:
`docs/14-licensing-decision.md` carries `SIGNED 2026-09-09`, the root
`LICENSE` exists, `tt/LICENSE` is the full CERN-OHL-W-2.0 text, and
`tt/LICENSE.PENDING.md` has been deleted. `scripts/ci_local.sh` asserts
the negation of all four on every run and has been green for a day,
`README.md` says "signed", and this file kept directing the work queue
from a state that no longer existed. It is struck rather than deleted,
`docs/64`'s rule, because what it recorded was true on its date.

**THE ONE THING THAT IS ACTUALLY BLOCKING, as of 2026-09-10.** GitHub
Actions is refusing to start jobs on this account -- *"the job was not
started because recent account payments have failed or your spending
limit needs to be increased"* -- and the Tiny Tapeout GDS action is the
one step of this project that has no local substitute, because the
artefact that reaches the fab is produced by that job from `tt/src`.
~~the Tiny Tapeout GDS action is the one step of this project that has
no local substitute~~ **— and that is false, measured 2026-09-10.**
`tt/tt/tt_tool.py --harden --ihp --no-docker` IS the substance of
`tt-gds-action`: the composite action is six shell steps around
`tt_tool.py` and nothing else. It ran here in **24 min 11 s**, all 74
flow steps, exit 0, and reproduced the frozen submission **bit for
bit** — the netlist joins the `52b2debf…` family, and the powered
netlist, DEF, LEF, SPICE, SDC and `metrics.csv` all hash equal, with
`metrics.json` agreeing on **194 of 194 keys** and the GDS byte-identical
once its 46 timestamp records are zeroed.

What is genuinely runner-only is four things, none of them the
artefact: the Pages upload; place-and-route inside the LibreLane
*container* rather than against the rootless shim set (synthesis is
provably the same `pyosys 0.67` wheel, P&R is not proven); whatever
`tt-support-tools@main` is on push day, since `tools-ref` is unpinned;
and independent re-execution itself.

**And the billing wall is in front of PRIVATE minutes, not public
ones.** The public mirror's first push started a run six seconds later
that executed for 75 seconds. So a Tiny Tapeout submission repository —
public by definition — is not blocked by it.

Gate G1: TT submission accepted by precheck; formal/CI targets green;
hour-budgeted WBS in docs/06 held within its go/no-go checkpoints.

**G1 status: met locally, not yet met hosted, and the reason has
changed.** The precheck passes ten of ten on the sign-off GDS and the
formal and CI targets are green. *Re-established 2026-09-10 on the
frozen submission GDS `4091b468…` from a rootless virtualenv in 70
seconds, with the resulting `drc_sg13g2.xml` byte-identical to the
2026-08-31 run, and then made to go red eleven times including on an
injected 0.05 × 2.00 um Metal1 width violation.* ~~The hosted half — the
Tiny Tapeout GDS action — has never run, because running it requires the
repository to be pushed, and that is now waiting on the account rather
than on a signature.~~ The local precheck needs KLayout 0.30.9; the
system 0.28.16 aborts the PDK deck and reports a failure that is not
real.

> **G1's HOSTED HALF IS MET, 2026-09-11.** The submission was pushed to
> <https://github.com/Melihakbulut221/tt-um-melihakbulut-nssoc> -- a
> repository whose ROOT is the contents of `tt/`, which is the shape the
> Tiny Tapeout tooling reads and the shape that fails silently when it
> is wrong. All 32 tracked files, `MANIFEST.sha256` verifying 31 of 31
> at the new root, and every source file `info.yaml` declares present.
>
> Three of the four hosted jobs passed on the first push **[fact, run
> `34557306023`]**:
>
> | job | result |
> |---|---|
> | `gds` | **success** -- the hosted harden, 675,878 um of global route, 479,173 um detailed |
> | `precheck` | **success** -- the Tiny Tapeout hosted precheck |
> | `gl_test` | **success** -- the gate-level test on the built netlist |
> | `viewer` | failed, then **success** once GitHub Pages was enabled |
>
> The `viewer` failure was `Creating Pages deployment failed / HttpError:
> Not Found` on a repository where Pages had never been switched on. It
> is a repository setting and says nothing about the design; it was
> enabled 2026-09-12 and the job re-run.
>
> **And the account was not the blocker either.** GitHub Actions bills
> PRIVATE minutes; a Tiny Tapeout submission repository is public by
> definition, and these four jobs started six seconds after the push
> with no payment of any kind. The paragraph struck above named the
> account because the only runs anyone had watched were on the private
> development repository.

### P2 — NLnet Restack application (to 2026-11-03)

- ~~**Open-licensing decision: still open, and now on the critical path
  for two deadlines rather than one.**~~ **CLOSED 2026-09-09.**
  `docs/14` section 11 is signed: rows 1 to 9 accepted as defaulted,
  CERN-OHL-W-2.0 for hardware, Apache-2.0 for tooling, CC-BY-4.0 for
  documents and data, and stage 1's mechanics executed the same day.
  Rows 10 and 11 remain scheduled, and row 11 — `docs/02` open question
  2 — still forbids any public claim of independent implementation.
- Application package: `docs/13`, rewritten 2026-09-05 against the
  evidence that now exists. The scope it asks NLnet to fund had to move
  again, because NLnet cannot pay for work completed before the grant
  and thirty-four documents of the previously proposed scope have been
  completed since the last revision (docs/13 section 2.2).
- All positioning language per docs/05 section 4, with two prohibitions
  now carried explicitly: **no clock frequency may be published**
  (docs/53 section 9.2, docs/60), and **nothing may imply the SoC is
  manufacturable today** (docs/12 section 8, docs/54).

Gate G2: application submitted before 2026-11-03; repo license state
consistent with what the application promises. **Open.**

### P3 — SoC design wave — largely executed, and not in the order this plan gave

The plan listed six workstreams "in dependency order" and put the NPU
RTL first. **The actual order was the reverse of the first two**: the
management subsystem was built first (`docs/38`-`docs/40`), hardened
(`docs/41`-`docs/44`), synthesised and placed (`docs/45`, `docs/47`),
and only then was the frozen pilot instantiated inside it (`docs/51`).
That was not a deviation from the plan so much as a discovery about it:
the accelerator was already built and frozen as the pilot, so what the
SoC needed first was everything the plan had assumed around it.

| # | Workstream, as planned | Plan estimate | What exists, and the evidence | What remains |
|---|---|---|---|---|
| 1 | NPU RTL: LIF core per docs/10 (E1-E10 bit-exact vs golden model, lockstep cocotb), synapse memory with SECDED, AER mesh-node interface | ~200-350 h [estimate] | **Built and frozen** as the pilot; instantiated, not copied, inside `soc_top` and reached over the same four serial pins the die will have. A program on Ibex out of the boot ROM configures it, loads ECC-checked weights, feeds a six-frame event stream and reads spikes back, checked against `sw/golden/lif_core.py` computed at build time (`docs/51`). Since `docs/66` the weight image comes from a modelled W25Q128JV over QSPI, which is where a flight part would feed it | The **AER mesh-node interface is not built**. `docs/10` section 8 item 2's mesh link is ranked by `docs/53` at a factor of **182** against the clock's 1.16, so it is the transport item that matters. A second node does not exist |
| 2 | Management subsystem: Ibex integration, PMP-based static partition supervisor per docs/09 S2, interrupt/timer/watchdog per docs/08 | ~150-300 h [estimate] | **Built.** Ibex `small-pmp` at a pinned commit through sv2v with **zero patches to Ibex** (`docs/38`); CLINT, GRLIB-style GPTIMER and a three-stage escalating watchdog (`docs/40`); watchdog state protected (`docs/41`); register file SECDED-protected (`docs/43`); observability at `BUSSTAT` (`docs/44`); `mtime` protected by a codeword rather than a copy (`docs/58`) | The **supervisor is a workload, not a deliverable**. `docs/46` ran a four-partition PMP-isolated supervisor to decide the watchdog window and found the **PMP registers are the worst stratum in that campaign by wrong answers, 23 of 58**, because S2 isolation made them live architectural state nothing had priced. ~~`docs/46` names five requirements that would have to enter `docs/09` track 3~~ **-- entered 2026-09-14.** `docs/09` part B track 3 now carries R1-R5 with their sources, a fourth fallback trigger T4, and the `csr_pmp` result as an unpriced fault surface this track's own S2 choice created. The amendment names what the record was hiding: **R1 contradicts the event-driven loop the S2 bullet specifies**, so the windowed watchdog is a precondition on the supervisor's dispatch discipline rather than a peripheral setting. The request had sat in another document's open items for thirteen days |
| 3 | Interfaces, base set first (2x UART, SPI, I2C, GPIO, QSPI), then SpaceWire codec and CAN 2.0B | base 280-475 h (docs/03 corrected roll-up) | **Three of the base set built**: console UART since `docs/39`; GPIO end to end with a k-induction proof and pins driven through a modelled board (`docs/65`); QSPI from scratch on APB with two chip selects, verified against a behavioural W25Q128JV written from Winbond datasheet Revision M (`docs/66`). Four candidates fetched by commit, elaborated and priced without being built (`docs/65` sections 8-9) | **Second UART, SPI, I2C, SpaceWire and CAN unbuilt.** They are priced rather than guessed: SpaceWire `spacewire_reloaded` at **17.5 kGE** with 64-entry FIFOs, Mohor CAN **18.1 kGE**, `verilog-i2c` **12.5 kGE**, OpenTitan `spi_host` **65.05 kGE — 171 % of the Ibex core [fact, docs/65]**. `docs/65` section 9.4's structural finding stands: **one APB-to-Wishbone bridge serves two of the four cores**, so that bridge and its proof are the item to do once. **Two of the four are LGPL and `docs/14` section 5.2 argues they are a bad fit for silicon** — that is a licensing decision, not an engineering one |
| 4 | Formal program: targets 1-10 per docs/09 part C, in CI from week 1 | 155-310 h (docs/09) | **Running at three scales.** Pilot: **54 tasks across 8 property sets** (`formal/`, counted 2026-09-05 by `make -C formal -n everything \| grep -c "sby -f"`). SoC: ~~**56 tasks across 14 property sets**~~ **-- that correction was itself stale when written. Re-counted 2026-09-14 by summing the `[tasks]` sections: **64 tasks across 15 jobs**. The fifteenth is `clkgate_wake.sby` with six, added by `docs/77`, and it is in neither of the two earlier figures. A roadmap correcting an index with a number that was already out of date is the defect this file's own 2026-09-12 amendment was written about, recurring one cell away from it** (`hw/soc/formal`, counted from the `[tasks]` sections). **`docs/00-index.md` section 6 is behind on both** — it says 45 over 7 and 52 over 14, which were right on their dates; `tmr_voter_cfg.sby` and `soc_boot.sby` are the difference. ISA: riscv-formal brought up against Ibex — **70 of 79 bounded checks PASS and 79 of 79 cover obligations PASS**, five defects found and **not one in Ibex's execution**, including a defect in riscv-formal itself where `insn_div.v` and `insn_rem.v` compute an unsigned result (`docs/63`) | `reg_ch0` on the SECDED register file is **proved to check cycle 18 and does not close at 21, 23 or 25** — four hours under all six engines the pinned suite offers, and four of the six cannot close even the stock core's version (`docs/63`). Three routes are ranked there. The M-extension gap carries forward and the phase-1-to-phase-2 delta over it is **undefined, not clean**. `soc_npu.v` still has no property set (`docs/56`) Re-counted 2026-09-15: `hw/soc/formal` carries **83 tasks across 20 jobs**, five jobs added (`soc_npu`, `regfile_scrub`, `regfile_scrub_abs`, `soc_apb_wb`, `clkgate_wake_gnt`); earlier figures left standing, `docs/64`'s rule. Re-counted again 2026-09-16: **86 tasks across 20 jobs**, the three added being `soc_bus.sby`'s `_rr` trio for `docs/84`; the 2026-09-15 figure is restored to 83 and left standing, `docs/64`'s rule. |
| 5 | Software track: bare-metal supervisor with Frama-C/CBMC absence-of-runtime-error evidence (docs/09 S2) | ~80-160 h [estimate] | **Partly, and not the part that was estimated.** A bring-up program, a partitioned supervisor (`docs/46`) and a boot flow with a loader, a RAM sweep that writes whole codewords, image checksums and a three-boot escalation demonstrated end to end (`docs/68`) | **No Frama-C or CBMC evidence exists.** Nothing in this workstream has been run through either tool. This is the one P3 workstream whose plan estimate is still entirely ahead of the project |
| 6 | Physical: hierarchical tile hardening, MBIST/scan, multi-corner STA | ~150-300 h [estimate] | **`soc_top` synthesised as one design** — 27,694 cells, 3,077 flip-flops, 392,932.8900 um2, 54.141 kGE, **1.11 % smaller than the sum of the nine blocks** (`docs/45`). **Placed and routed whole with six real RM_IHPSG13 macros**: 0 detailed-routing DRC errors, 0 disconnected pins, 0 power-grid violations, 1 antenna violating net, 37,156 nets, 3,095,532 um of wire (`docs/47`). With the accelerator in it, the same die, the same channel, the same six macro origins, 0 DRC (`docs/61`). Floorplan mapped from the DEF with eighteen self- and cross-checks (`docs/59`). Multi-corner STA throughout. **Power measured with the run's own switching activity** (`docs/57`) | **The layout does not meet its timing constraint** and the miss is measured, not estimated. ~~**No Magic DRC, no LVS, no XOR, no gate-level simulation** for the SoC, and that is upstream (section 1).~~ **All four have since been run, 2026-09-11 correction.** `docs/77` puts Magic DRC and the KLayout deck on `soc_top`'s own geometry -- **39,969,214 boxes examined, 0 outside**, and KLayout **9,668 / 0 outside**; `docs/79`'s LVS arm reports *"circuits match uniquely"*; XOR is 0 in the same run tree; and `docs/74` is a gate-level fault-injection campaign on the core with `docs/75`'s two-by-two on two placed layouts. What is still true is narrower and is what this cell should have said: ~~**none of those four has been re-run since the 2026-09-11 RTL repair**, so each describes a netlist the tree no longer contains~~ -- `paper/main.tex` section 2 carries the same marker for the same reason. **Half-closed 2026-09-13:** run `s83romecc5` places and routes the current RTL, including the ROM's two `512x16` check macros that every previous layout omitted, and two of the four decks have been re-run on it -- Netgen LVS `Circuits match uniquely` with all seven counters zero (`s83lvsbb2`), and KLayout DRC 11,048 markers -- 6,584 distinct shapes, `docs/54` section 3.1's double-count -- with **0 outside the vendor macro hierarchy** across a deck declaring 173 rule categories (`s83kdrc`). Magic DRC has since been re-run too -- 182 boxes, 20 inside a macro footprint, and all 162 others within 0.5 um of a macro edge with none in open routing area (`s83antmdrc`) -- and the two residual antenna violations were repaired in `s83ant`, which reaches 0/0 with the same eight macros and a cleaner setup WS. XOR has since been re-run as well -- `design__xor_difference__count` = 0 on the antenna-repaired layout (`s83antxor`, 2026-09-14) -- so all four deck families now have a result on the current RTL. What remains untouched is that **no campaign, STA or power number has been re-measured on either layout** -- all of those still describe `rom0` builds. `docs/67` section 11. **MBIST and scan do not exist.** Four remedies were measured and closed: floorplan (`docs/48`), `SYNPRE` (`docs/49`, `docs/62`), the RAM read register (`docs/50`), and the capacitance constraint (`docs/48`) |

**Roll-up: retired rather than restated.** The previous revision rolled
these six lines up to ~1015-1895 h and converted that to 12-24 months of
calendar at 15-25 h/week, concluding that the full-SoC RTL freeze lands
mid-2027 at the earliest. **The calendar conversion is refuted by the
record**: four of the six workstreams are substantially executed, the
other two are part-built, and `docs/38` through `docs/68` landed in six
calendar days **[fact]**. The
hours were never measured, so no ratio can be computed for them, and
that is itself the finding — **this project measures the area, timing,
power and fault response of everything it builds, and has never once
recorded how long any of it took.** Until it does, an hour-based plan
here would be a number with nothing behind it, which is exactly what
section 5's binding rules forbid elsewhere.

What replaces it is the "What remains" column above, which is a work
list with sizes attached where a document measured one. The two items
that gate a second shuttle run are named in section 1 and neither is an
effort problem: the macro sign-off is upstream, and the timing miss is
RTL or target.

Gate G3, as written: "RTL freeze with all docs/09 F-gates green;
regmap/spec/golden model/RTL in proven sync; interface set demonstrated
against golden models." **Overtaken by events — see section 2.7.**

### P4 — Pilot bring-up (2027-06 to 2027-09)

TT board bring-up, host software against the register map, LIF-slice
functional characterization vs golden model, TMR/SECDED demonstrator
exercise, results memo. Feeds the TTIHP27b/MPW gate and the NLnet
reporting milestones.

One thing has changed in this phase's favour and it is worth recording:
the host software is no longer speculative. `docs/51` argued and then
built the connection so that **there is one implementation of the die's
host protocol and it is the one in the SoC's own regression** — a bench
harness for silicon and the SoC's own driver are the same code path.

Gate G4: pilot silicon report — bit-exactness on silicon, demonstrator
behavior, flow lessons folded back into P3.

### P5 — Full-SoC tapeout and pre-screen (H2 2027 onward)

Full-SoC run on the gated shuttle; radiation pre-screen: Co-60 TID
pre-screen and proton facility options identified in prior project work;
positioning remains LEO 10-30 krad, fault-tolerant by architecture.
Flight-model claims are out of scope for this phase and this document.

Two preconditions are now explicit rather than assumed, because both
have been measured:

1. **The SRAM macros cannot be signed off on this PDK version**
   (`docs/12` section 8, `docs/54`). Any full-SoC run either waits on
   upstream, or ships without macros and pays the capacity, or changes
   PDK. `docs/67` has already made one of those trades under a different
   forcing function: the RAM is **32 KiB instead of 64** because the
   check bits went into the usable word rather than into a seventh macro
   at +491,634 um2.
2. **The layout does not meet its timing constraint**, and four
   candidate remedies have been measured and closed (P3 workstream 6).
   What is left is RTL or the target, and `docs/53` has already argued
   that no mission profile in `docs/05` section 3.4 requires the target.

### 2.7 Gates and plan items overtaken by events

Recorded rather than quietly rewritten. Each row is a place where the
plan turned out to be about the wrong thing.

| Plan item | What overtook it | Where |
|---|---|---|
| 2026-09-07 SRAM-macro go/no-go | Decided NO-GO thirteen days early, on an experiment run under strictly easier conditions than the gate asked for. The two exits were then both examined and both stay shut | `docs/12` section 8, `docs/54` |
| G3's "RTL freeze" | **There was no freeze event and there could not have been.** The SoC's RTL kept moving through synthesis, place-and-route and five hardening waves; `docs/45`, `docs/47`, `docs/61` and `docs/67` each measured a different tree. The pilot froze (`docs/34`) and the SoC did not. What replaced a freeze is a **reproduction discipline**: every document re-measures its predecessor's numbers before reporting new ones — `docs/61` reproduces eight instruments, four byte-exactly; `docs/62` reproduces thirteen | `docs/34`, `docs/61`, `docs/62` |
| G3's "interface set demonstrated against golden models" | GPIO and QSPI were demonstrated against something stronger and different: a **specification-derived model of a real part**, a behavioural W25Q128JV built from Winbond datasheet Revision M that applies the AC table's timing at its own terminals and counts every departure in a register the suite asserts is zero | `docs/66` |
| P3's dependency order (NPU RTL first) | Reversed. The accelerator was already frozen as the pilot; what the SoC needed first was the fabric, the map, the interrupts and the watchdog, none of which the plan listed as a workstream | `docs/39`, `docs/40`, `docs/51` |
| The plan had no bus, no memory map and no boot flow | All three turned out to be load-bearing design work with arguments behind them. The interconnect is **not AMBA AHB and none is claimed**; AMBA 3 APB is implemented and **proved compliant by k-induction** because it is small enough for the claim to be backed. The map is frozen as `regmap/memmap.yaml` with a generator that refuses a map Ibex's reset vector cannot reach. The flight ROM is decided as a **mask-programmed array** and the 8 KiB macro pair this PDK forces is named a stand-in | `docs/39`, `docs/68` |
| The plan had no power workstream | Power turned out to be the requirement the mission actually states — `docs/05` section 3.4's only number is "tens of milliwatts" — and the clock turned out not to be. `docs/53` found four documents had optimised the one term of the product the requirement does not contain | `docs/53`, `docs/57` |
| The plan treated fault injection as one pilot artifact (`docs/16`) | It became the project's method. **Seven RTL campaigns over five named populations**, each with a paired counterfactual, and three documents' own refusals to quote an improvement carried forward rather than netted off | `docs/60` section 8 |
| The clock target as a requirement | Retired as a requirement while kept as an SDC period, so four rounds of slack stay comparable. Its provenance was a Tiny Tapeout tile with no SRAM macro in it, and none of `docs/05`'s four mission profiles is specified in cycles. The pilot's own declared target stays on `tt/info.yaml` because it is a different part on a different schedule; **no SoC frequency is published anywhere**, and section 6 carries that as a binding rule | `docs/53`, `docs/60` |

## 3. The estimate-versus-outcome record

This project has repeatedly written down a prediction and then measured
it. That record is more useful than any single number in it, because it
calibrates what a prediction from this project is worth. Roughly ordered
by how badly the estimate missed.

| Predicted | Measured | Ratio or verdict | Where |
|---|---|---|---|
| "This design idles at 27.8 to 46.1 mW" — `report_power` with no switching activity | Waiting: **5.539 mW**. The whole duty-cycled run: **17.876 mW**. Orbit-average at profile 1's own 0.0044 % duty: **5.540 mW** | **6.29x high for an idle part.** The same unannotated number was **right to 2.8 % for a busy one** — the error is entirely in the idle case, and the reason is a clock gate six documents said did not exist | `docs/53` → `docs/57` |
| `docs/12`: "nearly three orders of magnitude" between the Magic and KLayout DRC counts on the macro | Normalised for the two decks' counting conventions, a factor of **4 to 9** — and on the contact-enclosure rule the decks **corroborate** | Largely an artefact of comparing a raw marker count with a hierarchically deduplicated one. Magic overstates by 3-4x; KLayout's deep mode understates by **53.0x** against its own flat mode | `docs/12` → `docs/54` |
| `docs/41`: TMR on `mtime` at +27,000 um2, unsynthesised | **+25,792.0740 um2 and exactly +256 flip-flops**, six designs against one baseline on one source list | **4.68 % high**, and now a fact rather than an estimate. The estimate was good; what was wrong was the idea it supported — replication was declined in favour of a codeword at **+8 flip-flops** | `docs/41` → `docs/58` |
| `docs/61`: `SYNPRE` costs +4.4 %, by carrying `docs/49`'s absolute area onto a new denominator | **+30,850.4322 um2 and +1,589 cells, +4.9406 %** — and the same change costs **more area and fewer cells** here | The method was the error, not the arithmetic: an absolute figure was rebased instead of re-measured | `docs/61` → `docs/62` |
| The nine blocks' areas will not compose into the whole design | `soc_top` as one design is **1.11 % smaller** than their sum, an order shown to be the mapper's own noise | Areas compose to about one and a half percent. **Timing does not**: integration costs **1.90 ns**, on a critical path that leaves the core, crosses the fabric and comes back — a path no per-block synthesis in this repository contains | `docs/45` |
| `docs/47`: "this is the frequency of this design **in this floorplan**", offered as a hypothesis with three pieces of evidence and no control | Two more floorplans built by a generator that reproduces `docs/47`'s own byte for byte. **Both are worse at every stage measured**; one global router did not terminate in 33 minutes against 8.033 seconds | **Hypothesis refuted by its own control.** The density penalty never bound, so `docs/47`'s placement was already the HPWL-optimal one for these macro pin positions | `docs/47` → `docs/48` |
| `docs/48`: `SYNPRE` "acts on the SECDED encoder that terminates the binding path", promoting it from declined to first | It acts on the **decoder**. The two cones are **disjoint**, so the most a perfect, free `SYNPRE` could do to the worst slack is **nothing** — and it was built and hardened anyway, because a pre-layout structural argument is what `docs/47` and `docs/48` exist to distrust | Built, measured, declined. Re-asked once the cone changed (`docs/61`) and measured **worse than it was when it was on the wrong cone**: −1.0109 ns, 2.5x the noise floor. **Three documents priced the same parameter and the price rose each time** | `docs/48` → `docs/49` → `docs/62` |
| `docs/42`: a corrupted loop bound keeps petting the watchdog, so build a **window** | The window caught **0 of 30** dead machines and produced **7 spurious escalations**. On a second workload its measured benefit (0.25 % [0.07-0.89]) and its measured cost (0.27 % [0.08-1.00]) are the same size, from one site each | **Recommendation reversed: remove it.** The class it was built for is caught by the per-phase kick budget, 4 of 4 on the same records replayed verbatim, and removed at source by the register file | `docs/42` → `docs/43` → `docs/46` |
| `docs/42`: the register file carries most of the rate, so parity over 31 words is the cheapest measured-value hardening | Built as SECDED instead. Register-file strata **3 SDC and 4 HANG in 100 → 0 and 0 in 200**; design-weighted SDC **2.8 % ± 1.6 → 1.3 % ± 0.4**; watchdog catch over the dead set **33 of 36 → 28 of 28** | **Prediction held.** Cost **+13.8 % of the core, 12.3 % of the lockstep `docs/38` declined at +152 %** | `docs/42` → `docs/43` |
| `docs/43`: the register-file codec spent the timing margin on the read path | It did not. Every one of the ten worst paths in both configurations starts at a **configuration input driven by a constant**, and the binding check is an asynchronous reset recovery check on an unbuffered 2,328-fanout net | The attribution was wrong; the measurement that replaced it is **2.7928 ns on the register file alone**, where nothing else can move | `docs/43` → `docs/44` |
| `docs/49`: registering the RAM read data is the only mechanism that puts both halves of the binding path inside the period | It did exactly that, completely: **444 macro-launched violating endpoints → zero**, **+0.7772 ns**, 1.94x the noise floor and the **first setup improvement in four documents the repository was entitled to claim** | **And the part gets slower, which stopped the change.** The program takes **+25.23 %** cycles, a second program **+25.72 %**; multiplied out, **21.04 % slower** in wall time. Not kept | `docs/49` → `docs/50` |
| `docs/03`: sv2v is a single point of failure for the whole management-core path | Less of one than priced: the pinned Yosys reads Ibex SystemVerilog directly through its bundled `slang` plugin, blocked by **exactly one construct**. And sv2v then carried OpenTitan's 52-module `spi_host` closure with **zero patches and two rewritten lines** | The risk was real and was over-priced. The coupled decision `docs/03` set — "if sv2v is rejected during CPU bring-up, both fall back together" — resolved in the direction of keeping both | `docs/03` → `docs/38` → `docs/65` |
| `docs/41`: a residue check over `mtime` would be the cheap detector | A **residue-mod-3 detector costs 98.694 % of what the corrector costs and corrects nothing**, because the cost of any check over a 64-bit counter is the reduction tree and not the shadow register | Refuted by measurement. Parity, the genuinely cheap detector, is 36.0 % | `docs/41` → `docs/58` |
| `docs/06` B.6: the pilot is a 2x2 default | 4x2 on measured area (`docs/15`), then **6x2** on routing convergence, timing and clock skew after the design outgrew the planning criterion (`docs/22`, `docs/23`) | Tiles EUR 560 → EUR 840; all-in **EUR 955** once the devkit and shipping the tile-only figure omitted are counted | `docs/06` → `docs/15` → `docs/23` → `docs/37` |

Two structural lessons come out of that table and both are already
binding practice:

1. **A pre-layout structural argument is a hypothesis.** Rows 6, 7 and
   10 are all cases where an argument about where the delay must be was
   measured and found wrong — and row 11 is the control that keeps the
   lesson honest, because there the structural argument was right and
   the change was still not kept. `docs/44`'s measured **0.4 ns instrument
   noise floor** exists so that a delta smaller than the instrument is
   not reported as a result, and three documents have since refused to
   claim an improvement on that ground.
2. **A mechanism's value is a property of a pair, not of a run.** Every
   campaign since `docs/42` runs each injection twice — once with the
   mechanism and once with it removed by an asserted substitution —
   because "the watchdog escalated" is not a catch rate until the same
   upset on the same machine with no backstop says whether the machine
   was in fact dead.

## 4. Near-term work queue (next nine days as of 2026-09-12, to the shuttle close)

Ordered by what blocks what, not by size.

> **Rewritten 2026-09-12, and the reason is worth more than the list.**
> Items 1, 2 and 4 below were struck on the same day an audit found them
> still standing. Every one had been DONE for days -- 1 and 2 on
> 2026-09-09, 4 on 2026-09-11 -- and each was recorded as done in the
> section of this very file above this one. So the queue was directing
> the owner to do work the file itself knew was finished, and it led
> with it. A work queue that outranks its own record is worse than no
> queue: it costs the reader the one thing a queue is for, which is
> knowing what to do next. `docs/81` is about a green result read wider
> than what it looked at; this is the same error in a plainer form -- a
> stale instruction read as a live one.
>
> **There is exactly one thing on this list that a person must still
> do, and it is item 1.**

1. **Buy the TTIHP26b 6x2 slot and claim a subsidised devkit** while any
   of the 88 remain. **EUR 955** — twelve tiles at EUR 70 is EUR 840,
   plus the EUR 300 devkit subsidised to EUR 100, plus EUR 15 shipping
   **[fact, `docs/37` section 3]**. **Deadline 2026-09-21 20:00 UTC —
   nine days.** Nothing in this repository substitutes for it and
   nothing else on this list is waiting on anything else.
2. **Close the `docs/13` open decisions that are not blocked on
   `docs/14`** — the requested amount, the rate and the project name —
   against the 2026-10-29 internal submission target. The public-URL field is no longer among them:
   `docs/13` section 3.3 now carries both published repositories.
3. Not before the above: `soc_npu.v`'s formal property set (`docs/56`),
   and `reg_ch0` by one of `docs/63`'s three ranked routes.
   *2026-09-15:* the property set exists -- `hw/soc/formal/soc_npu.sby`,
   H5 over all reachable states, bmc/prove/cover PASS, `docs/56`
   section 9.4's closing marker. `reg_ch0` is answered at the register
   file by routes 2 and 3 together: `regfile_scrub_abs.sby`'s `abc pdr`
   task proves R1-R4 unbounded with the codec abstracted (`docs/63`
   section 23), the codec being `regfile_secded.sby`'s separate theorem;
   the real-codec job `regfile_scrub.sby` stalls on the parity network
   under four engines and is kept as the measurement of that. The
   M-extension checks under bitwuzla close nothing at 7200 s on either
   core (`docs/63` section 22).

*The three items this queue used to lead with, struck rather than
deleted:*

- ~~**Sign or reject `docs/14`.** It blocks the shuttle push (16 days)
  and the application (59 days), and no engineering substitutes for it.~~
  **Signed 2026-09-09.** P1 above and `docs/14` section 11 both record
  it; this line went on asking for three more days.
- ~~**If signed: land the licence mechanics** — `LICENSE`, SPDX headers,
  the path map, third-party notices — and regenerate `tt/` so
  `LICENSE.PENDING.md` is replaced rather than shipped.~~ **Landed
  2026-09-09.** All four exist, `scripts/ci_local.sh` asserts the
  negation of the old state on every run, and `tt/LICENSE.PENDING.md`
  was deleted by `13402ad`.
- ~~**Push, and let the GDS action and the hosted precheck run.** This
  closes the open half of G1 and it is the only part of P1 this
  repository cannot do for itself.~~ **Done 2026-09-11**, and it closed
  exactly what it promised: the submission is at
  <https://github.com/Melihakbulut221/tt-um-melihakbulut-nssoc>, and
  run `34557306023` is **green on all four jobs — `gds`, `precheck`,
  `gl_test` and `viewer`**. G1's hosted half is met; see P1 above for
  what the one failure along the way was and why it was not about the
  design.
*Removed 2026-09-14: this section carried items numbered 5 and 6 below
the struck block, and they were verbatim copies of the live items 2 and
3 above it. So a queue rewritten on 2026-09-12 specifically to stop
directing the owner at work that was already done presented three live
items as five, and left its own predecessors behind while doing it. The
rewrite note below is about that class of residue; this was an instance
of it, one screen away, for two days.*

## 5. Backlog (non-blocking)

- **Frama-C / CBMC absence-of-runtime-error evidence** for the software
  track (docs/09 S2). The one P3 workstream entirely ahead of the
  project.
- **MBIST and scan.** Never started; the plan's physical workstream
  assumed prior DFT experience would carry them.
- **The AER mesh link** (`docs/10` section 8 item 2), ranked by
  `docs/53` at a factor of 182 against the clock's 1.16. A second NPU
  node does not exist.
- **The remaining interfaces**, with the licensing question decided
  first for the two LGPL cores (`docs/14` section 5.2, `docs/65`).
- **The two upstream reports drafted in `docs/54`**, the load-bearing
  one being a question that document refuses to answer for itself: is
  0.02 um Activ enclosure inside the vendor's own SRAM marker a
  qualified rule?
- ~~**The ROM's check macros** (`docs/67` section 15 item 2), now
  conditional on the 8 KiB stand-in rather than owed by the design,
  because `docs/68` decided the flight ROM is a mask-programmed array
  whose bit is a via.~~ **Done 2026-09-13**, run `s83romecc5`: placed,
  routed, 0 detailed-routing DRC errors, LVS matched uniquely. The
  conditional stands -- on `docs/68`'s decision they still protect the
  stand-in rather than a flight part -- so what closed is the geometry,
  not the question of whether the design wants them.
- Mesh scale-out (docs/02 Candidate C) — contingent on an event-camera
  payload requirement.
- seL4-on-CVA6 product tier (docs/09 S3) — interface discipline only.
- CPI front end — optional line item pending docs/08 CPI decision.

## 6. Binding rules inherited by all phases

- Positioning: docs/05 section 4 (LEO 10-30 krad class, fault-tolerant
  wording, never >=100 krad claims, multi-market framing, and rule 5's
  requirement that every published figure be traceable to measurement or
  clearly labelled a target).
- **Two prohibitions carried into every external document**: no clock
  frequency may be published (docs/53 section 9.2, docs/60), and nothing
  may imply the SoC is manufacturable today (docs/12 section 8,
  docs/54).
- Repo: English only, no emojis, sole-developer attribution, neutral
  engineering voice.
- Method: spec-first with frozen golden models; every RTL change
  re-proven (docs/09 maintenance rules); facts vs estimates tagged in
  all documents; no area/SRAM number quoted without naming its PDK
  (docs/07 verdict).
- **Reproduce before reporting.** A document that publishes a new number
  first reproduces the instrument that produced the old one; where the
  two disagree, the disagreement is the result (`docs/61`, `docs/62`,
  `docs/64`).
- **Measure the pair.** A protective mechanism is reported against a
  run of the same draws with the mechanism removed, never against its
  absence (`docs/42` onward).
