# 14 — Licensing and publication: decision memo

Date: 25 August 2026. **Rewritten 5 September 2026** against the tree as
it now stands.
Status: **decision memo, not a decision.** Section 9 carries a
recommendation and a dated action plan; nothing in this document is
binding until the developer signs section 11.
Decision owner: developer. Prepared by: engineering.

Labels: **[fact]** = verified against a cited primary source or read out
of a file in the working tree on the stated date; **[estimate]** =
judgement; **[legal]** = a question this memo deliberately does not
answer because it needs qualified advice.

---

## 0. Read this first: this memo is on the critical path

**The TTIHP26b shuttle closes 2026-09-21 at 20:00 UTC. That is sixteen
days from today. A Tiny Tapeout submission is a public repository. This
repository cannot be made public until the decision below is taken.**

The chain is short and every link is a fact:

1. There is **no `LICENSE` file at HEAD** `ed51de0` **[fact]**.
2. `tt/LICENSE.PENDING.md` — a generated file in the submission tree —
   refuses to carry one, and says why in its own words: publishing the
   design sources with no licence "grants nothing at all, which is worse
   for the project than any of the candidate licences" **[fact]**.
3. `docs/15` section 8.5 lists "Decide the licence" as item 2 of the
   things left for the developer — of which "the first three are owner
   actions that cannot be done from this environment at all" — and
   states in that item that it "blocks the push, not the build". Item 4
   of the same list records that pushing is the only way to get the GDS
   action and the **precheck** to run, and that precheck is not a subset
   of the local run **[fact]**.
4. `ROADMAP.md` gate G1 is therefore met locally and not hosted, and has
   been in that state since 2026-08-25.

**So this memo blocks the shuttle before it blocks the grant.** The
NLnet deadline is 2026-11-03, fifty-nine days out; the shuttle is
sixteen. The previous revision set its own signature deadline at
2026-08-31 and treated 2026-10-15 as the binding date. That ordering was
wrong: it read the decision as an application dependency when it is
first a fabrication dependency.

**What is needed is a signature on section 11, not more analysis.** This
revision is arranged so that the signature can be given in one sitting:

| Question | Answered in |
|---|---|
| What is in the tree right now, and what has already attached | section 2 |
| What NLnet's terms require, and when | section 3 |
| What the Tiny Tapeout submission requires | section 3A |
| The licence of every dependency actually in the tree | section 5 |
| The licence options and what each costs and forecloses | sections 6 and 8 |
| The recommendation and a plan that fits sixteen days | section 9 |
| The signature | section 11 |

---

## 1. The question

An NLnet grant is a commitment to publish every funded artefact under a
free licence; the sibling programme's "public at tapeout" posture does
not fit that. `docs/06` action item 5 and `ROADMAP.md` P2 both name the
decision and neither makes it.

Four things have to be decided, and they are separable:

1. **When** does anything become public — at the shuttle push, at
   application, at MoU signature, or at each delivery?
2. **What** becomes public — everything, or a defined funded scope?
3. **Under which licences** — separately for RTL, for documents, and for
   software, and consistent with what the dependencies allow.
4. **What does publication do to the export-safe posture** of
   `docs/05-market-positioning.md` section 4?

Sections 3 to 7 answer each; section 8 lays out the options; section 9
recommends.

---

## 2. Where the repository stands today

Re-read 2026-09-05 at HEAD `ed51de0`. **[fact]** for every item.

- **No `LICENSE` file at the repository root.** The repository is
  private.
- **426 tracked files** (`git ls-files | wc -l`), of which 71 are
  documents under `docs/`.
- The independent review (`docs/07`, rejected finding R-7) held that an
  absent licence is not a defect *while the decision is open and owned*.
  That was written on 2026-08-25, before the memo's own deadline passed
  and before the shuttle was sixteen days out. It is no longer a
  comfortable position.

### 2.1 One statement in the previous revision is now false

The 25 August revision said: *"No third-party RTL has been vendored into
the repository yet. That is a large advantage: the licence decision is
still being made before any inbound obligation attaches."*

**Inbound obligations have since attached, in two tracked places.**
Neither is a problem — both are permissive — but both need a notice, and
the "before anything attaches" argument can no longer be made.

| What | Where | Upstream | Licence | State |
|---|---|---|---|---|
| Tiny Tapeout template scaffolding: `.github/`, `.devcontainer/`, `.vscode/`, `src/config.json`, `test/Makefile`, `test/tb.v`, `test/requirements.txt` | tracked under `tt/` | `TinyTapeout/ttihp-verilog-template` at commit `6598bef4d3159f19fe471a2a2225df52e6f5ad25`; `src/config.json` is **byte-identical** to upstream | Apache-2.0 | Provenance is already recorded in `tt/README.md` and is **machine-checkable** — `scripts/gen_tt_submission.py --diff-template` re-fetches the template and proves the claim for every file that carries it. What is missing is the notice, which cannot be added until a licence exists |
| `insn_div.v` and `insn_rem.v` — **corrected copies** of riscv-formal's own instruction models | tracked under `hw/soc/rvformal/insns/` | `YosysHQ/riscv-formal` at commit `c992aa61fdfe0846c5ed90324c596202a1c69b76` | **ISC** (`ext/riscv-formal/COPYING`, Claire Xenia Wolf, 2017) | 109 and 110 lines against upstream's 66. `docs/63` section 7.5 records why they exist: upstream's models compute an **unsigned** division and remainder, confirmed on four counterexamples from two runs. Upstream ships no per-file notice, so ISC's "the above copyright notice and this permission notice appear in all copies" is discharged by shipping `COPYING` or an equivalent notice — **and this repository ships neither**. That is an action item, not a blocker |

### 2.2 Everything else third-party is fetched, not vendored

`hw/soc/tools.soc.mk` fetches six upstream trees and two toolchains into
**gitignored** directories, pinned by commit or by sha256, and
`soc-toolcheck` refuses a dirty checkout. `git ls-files` returns nothing
under `hw/soc/ext/`, `hw/soc/tools/`, `hw/soc/gen/`, `hw/soc/genrvfi/`
or `tt/tt/` **[fact]**. Section 5 is the full table.

This is the discipline that keeps the decision cheap, and it was a
choice rather than an accident: the harness that binds riscv-formal to
this core lives in `hw/soc/rvformal/`, **outside** the checkout, and the
two corrections of section 2.1 are the only files that had to cross that
line.

### 2.3 Two tracked files exist because Ibex expects the integrator to supply them

Neither is copied from Ibex and both must match upstream's port list,
which is the whole reason they live here:

- `hw/soc/rtl/prim_clock_gating.v` — `ibex_top.sv` instantiates
  `prim_clock_gating` and provides no synthesis implementation. This
  file binds the real `sg13g2_lgcp_1` integrated clock gate instead of
  upstream's behavioural stand-in.
- `hw/soc/rtl/ibex_regfile_secded.v` — the SECDED-protected
  architectural register file of `docs/43`, substituted into the build
  by a **file list** rather than by editing anything. The pinned
  checkout and its sv2v output are untouched. `docs/43` section 3
  already prices the four things "zero patches to Ibex" no longer
  covers, and `docs/44` section 10 records that the file carries
  upstream's port list — which is why it has no error output.

The provenance discipline is the same one applied to the generated
trees: where a rewrite was unavoidable, it was applied to the
**generated** file and not to upstream's, twice — sv2v's unsized
replication in OpenTitan's RACL policy default (`docs/65` section 8.2)
and the one declaration `yosys-slang` refuses in Ibex's RVFI block
(`docs/63`). **No upstream file is modified anywhere in this project**,
so no upstream file ever has to be redistributed as modified.

### 2.4 The artefact set is much larger than it was

The 25 August revision listed "the register-map single source and its
generator, the NPU golden model, `hw/rtl/aer_fifo.v` with its cocotb
regression, the SymbiYosys proof, and documents 00-13". The tree now
also holds a management subsystem, a bus and a frozen memory map, an
interrupt and timing subsystem, a watchdog, a protected register file,
observability, a connected accelerator, GPIO, QSPI, memory protection, a
boot flow, seven fault-injection campaigns, a riscv-formal bring-up and
a placed-and-routed SoC — `docs/38` through `docs/68`. **The scope table
of section 4 is a bigger job than it was in August, and that is an
argument for deciding now rather than in October.**

---

## 3. What NLnet actually requires, and when

Verified 2026-08-25 and re-verified 2026-08-29 against nlnet.nl primary
sources (`docs/13` section 1.3). **[fact]** for every quotation.

### 3.1 At application time: nothing must be public

- The form has no required repository field; "Website" is an optional
  100-character text field.
- Anonymity is explicitly permitted before selection: "You don't need to
  reveal your real name to us, prior to the project being granted."
- So **publication is not a precondition of submitting.** `docs/06`
  A.6's implication that submission itself requires it is wrong.

The countervailing pressure is evaluation, not eligibility. Stage 2
involves "independent verification of facts, methods and claims". A
private repository means every claim in the experience field has to be
taken on trust or evidenced by attachment. **[estimate]** That is a
scoring handicap on a 30 %-weighted criterion, not a disqualification —
and it is a larger handicap now than it was in August, because the
rewritten `docs/13` rests on thirty-four documents of measurement that a
reviewer cannot read.

### 3.2 At MoU signature: the licence is a named term of the contract

The sample MoU contains, as a term: "The source code of the Project
shall be made publicly available under GPLv3, or any later version" —
filled in per project. The licence choice therefore cannot be deferred
past MoU negotiation, and it is much better to arrive with a considered
answer than to accept the template's suggestion. A project that has
already published under its chosen licences negotiates from a fact.

Two further obligations start at MoU signature, not at first delivery:
public progress reports "every two months", and "a public status page
for the project".

### 3.3 At delivery: publication is the payment trigger

- "There is a donation amount attached to each task, which you unlock by
  **publishing** the associated results."
- "All scientific outcomes must be published as open access, and any
  software and hardware must be published under a recognised open source
  license **in its entirety**."
- No payment up front.

**Not at application, licence fixed at MoU, publication required at each
milestone.**

### 3.4 Two requirements that only bite later

- Follow-up funding above 50 kEUR requires that the earlier project's
  deliverables were published under recognised free licences, that any
  software artefacts were WCAG compliant, and that security-audit
  findings were handled. **[fact]** Keep funded software command-line
  and file-based and the WCAG clause is inert. **[estimate]**
- Patents must be disclosed at application. **[fact]** Nothing to
  disclose here.

### 3.5 What NLnet explicitly does *not* require

> "This condition however does not in any way exclude the legitimate
> holders of copyrights and other associated rights of dealing with your
> project results under additional licenses, even proprietary ones."
> **[fact]**

The developer retains copyright and may additionally licence the same
work commercially. Dual licensing is only possible while the developer
holds or controls all the copyright in the dual-licensed work — which is
a reason to keep third-party inbound code in clearly separated
directories, which section 2.2 shows is already the practice.

---

## 3A. What the Tiny Tapeout submission requires

New in this revision, because it is the binding deadline.

1. **The submission is a public repository.** The GDS that gets
   manufactured is produced by an action running in it, and the hosted
   precheck — which is not a subset of the local run, adding a
   pin-placement check against the shuttle mux, a top-level-uniqueness
   check and the shuttle's own DRC deck — runs there too (`docs/15`
   section 8.5 item 4). **[fact]**
2. **Tiny Tapeout does not mandate a licence on the design sources.**
   The template is Apache-2.0 for its own scaffolding and the FAQ says
   to update the copyright headers. So nothing forces a choice — which
   is exactly why publishing with no `LICENSE` would be the worst
   outcome available: it makes the sources public and grants nothing.
3. **The mechanics land in the source repository, not in `tt/`.** Every
   `.v` and `.vh` file under `tt/src/` is copied byte for byte out of
   `hw/rtl/`, and `tt/` is generated by
   `scripts/gen_tt_submission.py`. So the SPDX headers go into
   `hw/rtl/`, the `LICENSE` goes into the generator's file set,
   `LICENSE.PENDING.md` is removed by the same change, and the tree is
   regenerated. **[fact, `tt/README.md`]**
4. **The scaffolding stays Apache-2.0 as received**, and the
   regenerated `README.md` should say so where `LICENSE.PENDING.md` now
   sits.
5. **`MANIFEST.sha256` changes when the headers do.** `docs/34` pins the
   frozen artifact set by hash and states the rule for what may change
   without re-running what. Adding SPDX headers to `hw/rtl/*.v` changes
   the RTL blobs, so the freeze record has to be re-pinned — **read
   `docs/34` before adding the headers, not after.** This is the one
   place where the licence mechanics touch the frozen design, and it is
   the reason to do it in the next few days rather than in the last
   week.

---

## 4. What has to be open: scoping "in its entirety"

"In its entirety" attaches to the *project* defined in the MoU annex,
not to every file the developer owns. The practical rule:

- Everything named in the MoU milestones is public under the named
  licence, complete and buildable — no withheld headers, no "contact me
  for the constraints file".
- Work outside the funded scope may stay private, but only if the public
  scope stands on its own. A public RTL block that cannot be simulated,
  hardened or verified without a private script would breach the spirit
  and probably the letter. **[estimate]**
- The partition must be mechanical, not editorial: a directory boundary
  and a CI job that builds the public tree from a clean checkout with no
  access to the private one. If that job is green, the scope claim is
  true; if it is not, the claim is aspiration.

**Applied to the tree as it now stands**, the natural boundary is
everything that carries evidence and nothing that carries positioning:

| In scope | Out of scope |
|---|---|
| `hw/rtl/` (the pilot), `hw/soc/rtl/`, `hw/soc/{flow,syn,sta,pnr,fi,formal,tb,rvformal}/`, `hw/tb/`, `hw/openlane/`, `hw/fpga/`, `formal/`, `regmap/`, `sw/`, `scripts/`, `tt/`, `tools.mk`, `hw/soc/tools.soc.mk`, `conftest.py`, `pytest.ini`, `.github/` | Commercial positioning material, customer-facing pricing, product-line strategy. `docs/05` section 3.2(c) already marks that motivation as internal |
| `docs/` — with one question the owner must answer, below | |

**The one live question in the scope table is `docs/`.** Seventy-one
documents are a large part of what makes this project's claims checkable
— `docs/13` section 2.1's whole argument is that the evidence is the
asset — and they also contain the market analysis (`docs/05` section 3),
the funding plan (`docs/06`), the application draft (`docs/13`) and this
memo. Three defensible answers:

| Answer | Effect |
|---|---|
| **(a) Publish all of `docs/`** | Maximum evidence value. Publishes the funding strategy and the commercial framing, including this memo and `docs/13`'s open-decision table |
| **(b) Publish the technical documents; hold `docs/05` section 3, `docs/06`, `docs/13`, `docs/14`** | The evidence chain stays complete — every document a technical claim cites is public — and the business material is not. Requires checking that no technical document's cross-reference lands on a withheld one, which `sw/tests/test_doc_links.py` already has the machinery to check |
| **(c) Publish only what a milestone names** | Least work now, most work later, and it breaks the corpus: `docs/00-index.md` is a map of a set that would no longer exist |

Recommendation: **(b)**, and the deciding argument is not commercial
sensitivity — it is that `docs/13` and this memo contain **dated open
decisions and an unsigned signature block**, which are working documents
and not results. **[estimate]** They can be published later, once they
are decisions.

---

## 5. What the dependencies force

Re-read 2026-09-05 by opening each licence file in the working tree.
**[fact]** for every licence identification, with the file named.

| Dependency | How it enters | Pinned at | Licence, and where it was read | What it forces |
|---|---|---|---|---|
| **Ibex** (the management core) | `git clone` into `hw/soc/ext/ibex`, gitignored; sv2v output into `hw/soc/gen/` and `hw/soc/genrvfi/`, also gitignored | commit `34b0705760ef3dfa00e99637432473d2be8f22f3` | **Apache-2.0** — `hw/soc/ext/ibex/LICENSE` is the Apache 2.0 text | Nothing restrictive; inbound-compatible with a permissive or a reciprocal outbound licence. Note that the **sv2v output is a derivative of Ibex** and would carry Apache-2.0 if it were ever shipped. Today it is regenerated on every build and is gitignored, so nothing is redistributed. If a release ever ships a pre-converted tree, it ships under Apache-2.0 with notices |
| **riscv-formal** | `git clone` into `hw/soc/ext/riscv-formal`, gitignored — **plus two corrected copies tracked** in `hw/soc/rvformal/insns/` (section 2.1) | commit `c992aa61fdfe0846c5ed90324c596202a1c69b76` | **ISC** — `hw/soc/ext/riscv-formal/COPYING`, "Copyright (C) 2017 Claire Xenia Wolf", the ISC permission text | Permissive. Requires the copyright notice and the permission notice in **all copies**, which the two tracked files do not currently carry. **Action: add an ISC notice header to both, or ship `COPYING` beside them.** Small, and it must happen before the repository is public |
| **sv2v** | release binary downloaded into `hw/soc/tools/sv2v-Linux`, gitignored, pinned by tag **and** sha256 `552799a1…` | v0.0.13 | **BSD 3-Clause** — `hw/soc/tools/sv2v-Linux/LICENSE`, "Copyright 2019-2024 Zachary Snow / Copyright 2011-2015 Tom Hawkins" | A translator. Its licence governs the tool, not the tool's output — the output's licence comes from the input, which is Ibex's. Nothing to do unless the binary is redistributed, which it is not |
| **riscv-none-elf-gcc** (xpack) | release archive downloaded into `hw/soc/tools/rvgcc`, gitignored, pinned by tag **and** sha256 `aaaa8060…` | 15.2.0-1 | GCC and its components, per-component texts under `hw/soc/tools/rvgcc/distro-info/licenses/` | A compiler. GCC's runtime-library exception is why compiled output carries no copyleft obligation. Nothing to do unless the toolchain is redistributed, which it is not |
| **OpenTitan** (`spi_host`, assessed only) | sparse `git clone` into `hw/soc/ext/opentitan`, gitignored — `hw/ip/spi_host`, `prim`, `prim_generic`, `tlul`, `spi_device/rtl`, `top_earlgrey/rtl`, `dv/sv/dv_utils` | commit `1e1dace7680251f88ab11adedd8766222f333962` | **Apache-2.0** — `hw/soc/ext/opentitan/LICENSE` | Inbound-compatible. **Nothing under `hw/soc/rtl/` instantiates it**; `docs/65` converted and priced it at 65.05 kGE and then recommended QSPI from scratch instead, which `docs/66` built at 2.713 kGE |
| **`spacewire_reloaded`** (SpaceWire candidate, assessed only) | `git clone` into `hw/soc/ext/spacewire_reloaded`, gitignored | commit `450d2254bb980dc08825a575e205acbbefbc8a69` | **LGPL-2.1-or-later** — `LGPL-2.1.txt` in the tree **and an SPDX tag in every source file**; `docs/65` section 9.1 confirms the "intended-LGPL" of `docs/03` at the pinned commit | **Section 5.2.** Nothing instantiates it. This is the decision that has to be taken before its bridge is written, not after |
| **Mohor CAN** (assessed only) | `git clone` into `hw/soc/ext/can`, gitignored | commit `470f0e7ab174dfef01a05f5d5ad01f28f6f4dc17` | **LGPL-2.1-or-later** per the header of every file, **plus the Bosch protocol notice**: "The CAN protocol is developed by Robert Bosch GmbH and protected by patents. Anybody who wants to implement this CAN IP core on silicon has to obtain a CAN protocol license from Bosch." | Section 5.2, **and a patent obligation no open licence removes**. NLnet would want it disclosed. Nothing instantiates it |
| **`verilog-i2c`** (assessed only) | `git clone` into `hw/soc/ext/verilog-i2c`, gitignored | commit `a65be4045e898a52e791c6ee71f8f79a7cd2e129` | **MIT** — `COPYING`, "Copyright (c) 2015-2017 Alex Forencich" | Inbound-compatible. Nothing instantiates it |
| **IHP Open PDK** (SG13G2, incl. `RM_IHPSG13_*`) | pinned upstream release, not vendored | the LibreLane-pinned commit recorded in `docs/12` | Apache-2.0 (`LICENSE` in `IHP-GmbH/IHP-Open-PDK`); IHP describes the open content as preview only, not for production | Do not vendor or redistribute PDK files. Check per-file headers before redistributing any macro view — an Apache-2.0 repository can still contain differently-licensed third-party files |
| **Tiny Tapeout template** | **tracked**, seven paths under `tt/` (section 2.1) | commit `6598bef4d3159f19fe471a2a2225df52e6f5ad25` | Apache-2.0 | A derived shuttle repository is already under an open licence for its scaffolding. TT does **not** mandate publishing the design, so publication remains a separate voluntary act — see section 3A |
| **tinyODIN / ODIN / ReckOn** | reference only, not in the tree | — | Solderpad v2.1 (`docs/02`, `docs/03`) | Reuse is permitted with attribution. Whether any was reused decides whether "clean-room" may be written — `docs/02` open question 2, still open. Section 5.1 |
| **GRLIB / NOEL-V, the GR801 brief** | reference only | — | GRLIB is GPL with a paid commercial option; the FT variant is commercial-only. Vendor documents are copyrighted | No GRLIB RTL enters the design. No manual text, table or register layout is copied — conventions may be *followed*, with deviations documented, which is what `docs/08` does. A copyright rule, not a licence choice, and it applies whether or not the repository is public |

### 5.0 The fact that makes this decidable in one sitting

**Every inbound licence that touches a tracked file is permissive** —
Apache-2.0 for the Tiny Tapeout scaffolding, ISC for the two
riscv-formal corrections. **The two LGPL cores touch nothing tracked and
nothing instantiated.** So the outbound choice in section 6 is
**unconstrained by inbound obligations**: Apache-2.0, CERN-OHL-W-2.0 and
CERN-OHL-S-2.0 are all available, and the decision turns entirely on
what the project wants, not on what it is forced into.

That was the previous revision's headline advantage, and it survives.
What does not survive is the reason given for it — the advantage now
comes from the fetch-don't-vendor discipline of section 2.2, not from
there being nothing inbound at all.

### 5.1 The "clean-room" claim is still not free, and its deadline has passed

`docs/02` open question 2 has not been answered: the project has not
decided between reusing Solderpad-licensed tinyODIN/ODIN RTL, using it
only as a golden reference, and implementing independently. Those are
three different licensing outcomes and three different truthful
sentences. The word is removed from the `docs/13` abstract for that
reason (`docs/13` D-14), and the previous revision set 2026-09-02 for
the answer. **That date has passed and the question is still open.**

It is cheap to settle and it gets more expensive every week the RTL
grows. It does **not** block the shuttle: nothing in `tt/src/` claims
clean-room provenance, and `docs/13` does not use the word.

### 5.2 LGPL RTL is a bad fit for silicon, and the decision has moved closer

LGPL's central mechanism is the user's ability to replace the library
with a modified version and relink. There is no accepted equivalent for
a block fused into a fabricated die, and the obligation is at best
unclear and at worst read as requiring the netlist and the means to
re-implement the part. That ambiguity would sit inside a chip that also
carries a Bosch patent obligation, and it would complicate the
dual-licensing option of section 3.5. **[estimate]**, and the kind of
estimate that should be replaced by advice before any adoption
**[legal]**.

What has changed since August is that the question is now concrete
rather than hypothetical. `docs/65` fetched, elaborated and priced all
four candidates, and its section 9.4 makes the shape of the decision
clear:

- **SpaceWire and CAN are the LGPL question**, and they are the two
  interfaces `docs/01` treats as GR801-defining. SpaceWire is
  17.5 kGE with 64-entry FIFOs; CAN is 18.1 kGE **[fact, docs/65]**.
- **I2C is MIT and QSPI was built from scratch**, so neither is
  affected — `docs/66` built a 2.713 kGE APB flash controller rather
  than wrapping OpenTitan's 65.05 kGE `spi_host`.
- **One APB-to-Wishbone bridge serves both CAN and I2C**, so a decision
  to decline the LGPL cores does not orphan that bridge — it still pays
  for itself on I2C alone.

Practical consequence: **decline the LGPL cores from the funded scope,
and take advice before adopting either.** If SpaceWire is adopted later,
it lives in its own directory with its own licence file and its own
notice, and the question gets proper advice first. An independent
SpaceWire implementation is the alternative and it is not costed here.

---

## 6. Licence options

### 6.1 RTL and other hardware sources

| Option | What it does | For this project | What it forecloses |
|---|---|---|---|
| **Apache-2.0** | Permissive, with an express patent grant and a patent-retaliation clause. Written for software; widely used for RTL (Ibex, OpenTitan, the IHP PDK, the TT templates) | Maximum adoption and zero inbound friction — every dependency in section 5 is already compatible. Simplest possible licence story | **Reciprocity, permanently, for everything published under it.** A permissive grant cannot be withdrawn from what has already been released: a competitor can take the fault-tolerance IP, improve it and close it, and no later relicensing of the project recovers that |
| **CERN-OHL-W-2.0** (weakly reciprocal) | Purpose-built for hardware. Modifications to the covered source must be released under the same licence; a larger product that *incorporates* it need not be opened. The "Available Component" definition lets a design depend on generally available parts without dragging their sources in | Improvements flow back; a satellite integrator can still embed it in an otherwise-proprietary payload. That matches the intended users precisely — university programmes that will publish, and newspace integrators who will not | **Direct upstream contribution.** Code intended to be merged into an Apache-2.0 upstream project cannot be CERN-OHL-W; it must be Apache-2.0 and contributed upstream rather than mirrored. That is a real cost here, because `docs/13`'s ecosystem case and `docs/54`'s two drafted upstream reports both depend on contributing upstream. Section 6.5 handles it |
| **CERN-OHL-S-2.0** (strongly reciprocal) | Same family, but conveying a product built from the covered source obliges you to release the complete source for **the whole product** | Strongest commons protection | **Most of the adoption.** "Put your entire satellite payload design under CERN-OHL-S" is a conversation most integrators will decline **[estimate]**. Note the one-way compatibility: CERN-OHL-W covered source may be treated as CERN-OHL-S if all its available components satisfy the stricter definition, **so starting at W does not permanently foreclose S** |

Assessment: **CERN-OHL-W-2.0 for RTL and hardware sources.** It is the
only one of the three designed for hardware, it keeps improvements
flowing back, it does not impose a term the target adopters will refuse,
and it is the only one of the three whose main cost is recoverable
(section 6.5) while Apache-2.0's is not.

Reciprocity is also the honest match to the project's own argument:
`docs/05` section 3.2(b) sells auditability as the differentiator. A
licence that lets a derivative be closed undercuts that argument; weak
reciprocity preserves it without making the block unusable.

### 6.2 Software

Golden models, register-map and memory-map generators, host and bring-up
software, test harnesses, analysis scripts, flow scripts that do not
themselves become hardware: **Apache-2.0.** It matches Ibex, OpenTitan
and the IHP PDK, it carries an explicit patent grant, and it is the
licence people expect on tooling they are meant to reuse. The golden
models are the executable specification of the RTL, so a permissive
licence here maximises the chance that someone else's implementation is
checked against them — which is the point.

### 6.3 Documents and data

- Technical documents (`docs/`): **CC-BY-4.0.** Attribution only. NLnet
  requires open access for scientific outcomes; CC-BY satisfies it and
  keeps the documents quotable. CC-BY-SA is defensible but share-alike
  on documentation mostly creates friction for people quoting a table
  into their own differently-licensed report. **[estimate]**
- Measurement data — the fault-injection result files, the flow metrics,
  and a future radiation dataset: **CC0-1.0** or **CC-BY-4.0**.
  Recommendation CC-BY-4.0 for consistency; the argument for CC0 is that
  facts are not copyrightable anyway and CC0 removes the argument.
  **[D]** — developer's call.

### 6.4 Summary of the proposed licence set

| Artefact class | Proposed licence |
|---|---|
| RTL, testbenches, constraints, flow scripts producing hardware | CERN-OHL-W-2.0 |
| Golden models, generators, host/bring-up software, analysis scripts, CI | Apache-2.0 |
| Documents in `docs/` | CC-BY-4.0 |
| Measurement datasets | CC-BY-4.0 (CC0-1.0 alternative) |
| Tracked third-party code (section 2.1) | **unchanged** — Apache-2.0 for the TT scaffolding, ISC for the two riscv-formal corrections, each with its own notice |

Mechanics: SPDX identifiers in every file header, a `LICENSES/`
directory holding the full texts, a `LICENSES.md` mapping paths to
licences, and a CI check that fails on a source file without an SPDX
tag. That check is also what makes the section 4 scope claim
mechanically true rather than editorially asserted — the same standard
this repository already applies to its flow guards.

### 6.5 The one thing CERN-OHL-W costs, and how it is paid

`docs/13`'s ecosystem field promises that the redundancy-survival
checker, the catalogue of constructions and the reproducible test cases
go **upstream** — to yosys, LibreLane and IHP-Open-PDK — as issues with
minimal reproducers. `docs/54` has already drafted two upstream reports
for IHP-Open-PDK. None of those recipients takes CERN-OHL-W code.

The fix is a boundary, not an exception: **anything written to be merged
into a named upstream project is Apache-2.0 from the moment it is
written, and lives in a directory the `LICENSES.md` map names.** The
checker is tooling and is Apache-2.0 under section 6.2 anyway; the
upstream reports are prose and are not licensed at all. So the cost is
paid by drawing the boundary once, and it should be drawn in the scope
table of section 9 rather than discovered at the first pull request.

---

## 7. The export-control interaction

**[legal]** throughout. This section frames the question and records the
project's own rules; it is not advice.

What is settled and internal to the project:

- `docs/05` section 4 rule 2: the device is "fault-tolerant", never
  "rad-hard". Rule 3: never claim, target or advertise total-dose
  ratings at or above 100 krad(Si). Rule 1: the stated class is LEO,
  10-30 krad(Si), pending test data. Rule 4: multi-market framing. Rule
  5: any published figure must be traceable to measurement or clearly
  labelled a target.
- These rules already assume public text. Publishing the repository does
  not create a new claim surface; it enlarges an existing one that is
  already governed.

Two prohibitions have been added since August and both are now operative
on every public artefact:

- **No clock frequency may be published** (`docs/53` section 9.2,
  `docs/60`). The refusal is on three grounds, of which the first is
  that the available number is the one a failing layout reached.
- **Nothing may imply the SoC is manufacturable today** (`docs/12`
  section 8, `docs/54`). The SRAM macros cannot be signed off on this
  PDK version, and the SoC layout has no Magic DRC, LVS or XOR result at
  all. The pilot is a different claim and a defensible one: it is
  flip-flop RAM, it carries no macro, and every geometric counter on it
  reads zero.

What publication changes:

1. **Irreversibility.** Published RTL and published data cannot be
   withdrawn. Everything published must be inside the `docs/05` envelope
   at the moment of publication. This argues for a publication
   checklist, not against publication.
2. **Direction of travel.** Publication tends to *reduce* exposure
   rather than increase it: dual-use regimes generally treat information
   already in the public domain differently from controlled technology
   **[developer-supplied; confirm before relying on it]**. Whether that
   holds under the Turkish implementation of the relevant regime, and
   what obligations attach to the *act* of publishing, is the question
   that needs advice. **[legal]**
3. **The dataset is the sharp edge.** RTL and documents stay inside the
   envelope by construction. A measured total-dose dataset could come
   back above the class the project advertises. Handling rule, decided
   in advance rather than under pressure: publish the measurement as
   measured, describe it as a measurement of a specific design in a
   specific library under a specific procedure, and do **not** convert
   it into a device rating, a marketing claim or a qualification
   statement.
4. **NLnet reinforces the same discipline.** The review team verifies
   claims independently; the application text and the repository text
   must agree, and both are governed by `docs/05`.

Net assessment: publication and the export-safe posture are compatible,
and are compatible *because* the positioning rules were set
conservatively before publication was on the table. The residual item is
item 2. **[legal]**

**And a scheduling note that the shuttle forces.** The previous revision
put the export advice at 2026-09-30, before a 2026-10-05 publication.
The shuttle needs a public repository on 2026-09-21. Section 9 resolves
this by separating the two publications: **the shuttle tree is the
pilot, which carries no radiation claim and no dataset**, and it can go
out under the same licence set without waiting for advice on item 2. The
advice is needed before the radiation dataset is published, which is a
2027 event.

---

## 8. The options

| Option | Description | Effect on the shuttle | Effect on NLnet | What it forecloses | Verdict |
|---|---|---|---|---|---|
| **A** | Stay private; do not apply | **Forfeits TTIHP26b.** The pilot is frozen, signed off and precheck-clean and would not be fabricated | n/a | The 2027-06-25 silicon, and with it P4, and with it the silicon evidence every later claim rests on | **Rejected.** Restack's budget is "expected [to be fully allocated] early 2027" **[fact]**, so the funding option does not stay open either |
| **B** | Publish the entire repository now under one licence | Satisfies it | Strongest evaluation position | Nothing structurally, but it publishes working documents with unsigned decisions in them (section 4) | **Rejected as over-broad**: publishes commercial positioning and open-decision tables and gains nothing for it |
| **C** | Publish a defined scope now under the section 6.4 licence set; the rest stays private until its own gate | **Satisfies it**, and is the only option that does so on the current schedule | Satisfies every requirement; strong evaluation position; nothing to renegotiate at MoU | Optionality — publication is one-way | **Recommended** |
| **D** | Publish nothing until MoU signature | **Forfeits TTIHP26b**, exactly as option A does | Legal minimum (section 3.1) | The same things option A forecloses | **Rejected, and more sharply than in August.** The previous revision rejected it for giving up evaluation benefit; it now also costs the shuttle. Sixteen days is not enough to change that |

**The shuttle column is what reorders this table.** In August, options C
and D differed by a few months of evaluation advantage. They now differ
by whether a frozen, signed-off, precheck-clean design gets fabricated.

On the sibling precedent: "public at tapeout" is a sound rule for a
product whose competitive value is in the design itself and whose funder
is the developer. It is not compatible with a funder that pays per
published milestone, because the first milestones are RTL and proofs.
The two rules coexist by scope: funded artefacts follow the funder's
rule, unfunded product work keeps the tapeout gate. That is option C,
and it is a reconciliation rather than a surrender. It is also worth
noting that **the pilot IS at tapeout** — publishing it satisfies the
sibling rule rather than breaking it.

One thing option C does not do is preserve optionality. Publication is
one-way, and it lands before the funding decision is known. The argument
that it is worth taking on its own merits: the project's stated
differentiator is auditability (`docs/05` section 3.2(b)), the pilot
goes to a community shuttle whose ecosystem norm is publication, and the
prior `tt-um-lif-crossbar` design is already public.

---

## 9. Recommendation and action plan

**Recommendation: option C.** Publish a defined scope, under
CERN-OHL-W-2.0 for hardware sources, Apache-2.0 for software,
CC-BY-4.0 for documents and data; keep commercial and product-line
material private; decline the two LGPL cores from the funded scope
pending advice; state the scope and the licences in the NLnet
application so that the MoU has nothing to negotiate.

**And publish in two stages, because the two deadlines want different
things.** This is the change from the August plan.

### Stage 1 — the shuttle, by 2026-09-21

The minimum that makes the push legitimate. It touches the frozen design
(section 3A item 5), so it goes first.

**Stage 1 does not require this repository to be public.** The Tiny
Tapeout submission is its own repository, generated by
`scripts/gen_tt_submission.py` from this one, so what stage 1 publishes
is the `tt/` tree and the design sources it carries — not this
repository's history. That is why the mirror-versus-same-repo question
in stage 2 can wait, and why the shuttle can be met without answering
it.

| By | Action | Owner |
|---|---|---|
| **now** | **Sign section 11.** Everything below is mechanical | developer |
| +1 day | Add `LICENSES/` with the three full texts; add SPDX headers to `hw/rtl/*.v` and `*.vh`; add the ISC notice to `hw/soc/rvformal/insns/insn_div.v` and `insn_rem.v` (section 2.1) | engineering |
| +1 day | Re-pin `docs/34`'s freeze record against the new RTL blob hashes, and say in that document that the change is headers only | engineering |
| +2 days | Regenerate `tt/`: `LICENSE` in place of `LICENSE.PENDING.md`, the scaffolding note in `README.md`, `MANIFEST.sha256` refreshed | engineering |
| +3 days | Draw the scope boundary: one table, every path in and every path out, including the `docs/` answer of section 4 and the upstream-contribution boundary of section 6.5 | engineering |
| +4 days | CI: SPDX tag check fails the build on an untagged source file; a clean-checkout build of the public tree with no access to private paths | engineering |
| **by 2026-09-21, 20:00 UTC** | Buy the 6x2 slot (**EUR 955** with the subsidised devkit), push, let the GDS action and the hosted precheck run | developer |

### Stage 2 — the application, by 2026-10-29

| By | Action | Owner |
|---|---|---|
| 2026-09-30 | Answer `docs/02` open question 2 (section 5.1), which is overdue and decides whether "clean-room" may ever be written | developer |
| 2026-09-30 | Obtain advice on section 7 item 2 **[legal]**. Not a stage-1 blocker; needed before any radiation dataset | developer |
| 2026-10-05 | Decide whether the public tree is this repository made public or a curated mirror — the deciding question is whether the existing git history is publishable as-is. **Check before this date, not after** | developer |
| 2026-10-15 | `docs/13` D-6 and D-7 closed with real URLs; the application text describes the published state as a fact rather than a promise | developer |
| 2026-10-29 | Submit the application | developer |
| at MoU | Name the section 6.4 licences as MoU terms; stand up the public status page and the two-monthly reporting cadence | developer |
| at each milestone | Publish the milestone artefacts complete, then request payment | developer |

Explicitly deferred, not decided here:

- **SpaceWire and CAN adoption** and their LGPL and Bosch-patent
  consequences (section 5.2). Out of the funded scope; revisit with
  advice when the interface phase starts. `docs/65` has already priced
  the alternatives.
- CC0 versus CC-BY for datasets (section 6.3).
- Whether `docs/13` and this memo are published once they are decisions
  rather than drafts (section 4 answer (b)).

---

## 10. Consequences of accepting the recommendation

- **The shuttle push is unblocked**, and P1's remaining items become
  purchasing and pushing.
- `ROADMAP.md` gate G2 becomes satisfiable: the repository state and the
  application's promises agree, because the promise is in the past
  tense.
- The `docs/13` experience and website fields gain verifiable URLs,
  which is worth real score on a 30 %-weighted criterion, and matters
  more now than in August because the application rests on thirty-four
  documents a reviewer would otherwise have to take on trust.
  **[estimate]**
- Commercial optionality is preserved: the developer keeps copyright and
  may licence additionally, including proprietarily (section 3.5). This
  depends on not accepting third-party contributions into the
  dual-licensed tree without a contributor agreement or a matching
  licence grant — a governance item to set up **before** the repository
  attracts contributors, which publication will start doing immediately.
  **[estimate]**
- The publication decision is irreversible, and it lands before the
  funding decision is known.
- The mechanical work is larger than the 12-20 h the August revision
  estimated, because the tree has roughly doubled since — but the
  stage-1 half of it is small and is listed above by day. **[estimate]**

---

## 11. Sign-off

Defaults are marked. Signing the defaults is a complete decision;
striking one is also a complete decision. Nothing here needs to be
researched further before it can be signed.

| # | Item | Default | Decision | Date | Signature |
|---|---|---|---|---|---|
| 1 | **Option C**: publish a defined scope now, in the two stages of section 9 | accept | accept / reject / amend | | |
| 2 | RTL and hardware sources: **CERN-OHL-W-2.0** | accept | accept / reject / amend | | |
| 3 | Software, generators, harnesses, CI: **Apache-2.0** | accept | accept / reject / amend | | |
| 4 | Documents in `docs/`: **CC-BY-4.0** | accept | accept / reject / amend | | |
| 5 | Measurement datasets: **CC-BY-4.0** (CC0-1.0 alternative) | accept | accept / reject / amend | | |
| 6 | `docs/` scope: **answer (b)** — publish the technical documents, hold `docs/05` section 3, `docs/06`, `docs/13` and `docs/14` until they are decisions rather than drafts (section 4) | accept | (a) / **(b)** / (c) | | |
| 7 | Upstream-contribution boundary: anything written for a named upstream project is **Apache-2.0 from the start** (section 6.5) | accept | accept / reject / amend | | |
| 8 | **Decline the two LGPL cores** (SpaceWire, CAN) from the funded scope pending advice (section 5.2) | accept | accept / reject / amend | | |
| 9 | Stage-1 mechanics, including re-pinning `docs/34` for the header change (section 3A item 5) | approved | approved / amend | | |
| 10 | Export advice on section 7 item 2, before any radiation dataset and **not** before the shuttle | scheduled 2026-09-30 | done / scheduled / waived with reasons | | |
| 11 | `docs/02` open question 2 — Solderpad reuse versus independent implementation (section 5.1) — **overdue** | 2026-09-30 | answer: reuse / reference only / independent | | |

Until rows 1 to 5 are completed, `docs/13` D-6 and D-7 remain open, the
application must not be submitted with a claim about the repository's
public state, **and the TTIHP26b submission cannot be pushed.**
