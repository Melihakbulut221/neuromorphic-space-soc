# 41 — Hardening the watchdog: ranking the state by what its corruption costs

`docs/40-interrupts-timers-watchdog.md` closes with the sharpest
sentence in it, and this document is the answer to it:

> **the watchdog and the CLINT counter have no protection at all**. A
> watchdog that an upset can silently disarm is worse than no watchdog,
> because the system believes it has one. Whatever the campaign finds,
> the block whose job is to catch upsets should not be the least
> protected thing in the design.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
an intention with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `formal/`, `tt/` or `hw/openlane/` was modified.
One file in `hw/rtl/` is **read**: `tmr_voter.v`, instantiated in place
rather than copied, and `test_the_voter_is_the_blob_the_pilot_freeze_pins`
asserts it is still the blob `docs/34` section 2 names. Section 12 lists
every file touched.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| What is protected? | The eight fields whose corruption is **permanent or silent**: the bootstrap latch, the stage-1 pending flag, the reset record, the saturating reset count, the reset stretch, and the new mismatch report. 22 bits, tripled. Section 3 |
| What is deliberately **not** protected? | `counter`, `reload` and `pre` — 36 flip-flops, more than the protected word — because the block rewrites all three itself and an upset in them is bounded rather than permanent. Section 7 |
| How is a 1-bit flag tripled, given the replication bound? | It is not. The flags are **bundled** into one 22-bit word and the word is tripled, which is what buys the width the MIX transform needs. Section 4 |
| Does the redundancy survive synthesis? | **Yes, and it is counted, not assumed.** 102 flip-flops mapped, 22 per replica, on two flows, with every protective attribute deleted from the text of the source. Removing the MIX transform from one replica costs 11 flip-flops; from both, 22 **[fact]**. Section 6 |
| Does the transform reach the *mapped* netlist? | **Yes here, unlike `docs/33`.** Replica A is 22 bare flip-flops; B and C carry 11 inverters and a distinct XOR cone each **[fact]**. That is a bonus and not the defence, and section 6.4 says why |
| What does it cost? | **+5,091.06 um2**, +88.9 % of the unhardened watchdog, **+1.85 % of the Ibex core** **[fact]**. 1.6 % of what declining lockstep in `docs/38` would have cost. Section 6.5 |
| Did the hardening change any behaviour? | **No, and this is measured rather than argued.** The whole-SoC run is cycle-identical to `docs/40`: stage 1 at cycle 174,128, core asleep after 185,443 cycles, 587 console characters, 0 framing errors **[fact]**. Section 9.1 |
| Is it proved? | 5 formal jobs, 20 tasks, all PASS; the new composition job proves masking by k-induction at four widths and on two engine families, 6 of 6 cover obligations reached **[fact]**. Section 9.3 |
| Is it *measured*? | **162 injections into the block's own flip-flops. 126 of 126 into the protected word came back CORRECTED — masked at the ports and counted. 0 SDC, 0 HANG, 0 disarmed** **[fact]**. Section 8. *Superseded in part 2026-09-05: the zero spurious escalations section 8.3 reports hold for upsets in the watchdog's own state, which is what this campaign injects into. `docs/43-core-hardening.md` sections 4 and 8.4 measured the windowed mode later built on this block against upsets in the core and found **7 spurious escalations in 1,232 survivable upsets**, so a zero-spurious-escalation headline no longer holds for the block as shipped* |
| Does the same experiment on the unprotected block look different? | **Yes, and that is the point.** 32 injections into the same state with `HARDEN = 0`: 27 SDC, 1 HANG, **2 left the watchdog reading disarmed**, and only 6 of 32 preserved the escalation order **[fact]**. Section 8.3 |
| Is `mtime` protected? | **No.** It is the highest-ranked thing this document does not do, and section 7.4 says why it is second and not first |

---

## 2. What was built

| File | What it is |
|---|---|
| `hw/soc/rtl/soc_tmr_bank.v` | One physical replica of a TMR domain: the POL + MIX storage transform, derived from `pilot_cfg_bank` in `hw/rtl/pilot_top.v` with three stated differences |
| `hw/soc/rtl/soc_wdog.v` | Rebuilt around it. A sixth requirement, **W6**, joins W1-W5 in the header |
| `hw/soc/formal/soc_wdog_tmr_props.v`, `soc_wdog_tmr.sby` | The composition proof: three replicas under one voter, with a fault model |
| `hw/soc/tb/cocotb/test_soc_wdog_fi.py`, `Makefile.soc_wdog_fi` | The fault-injection campaign, and the unhardened counterfactual |
| `sw/tests/test_soc_synthesis_guards.py` | The netlist census: does the redundancy survive synthesis |
| `hw/rtl/tmr_voter.v` | **Read, not modified.** Instantiated in place |

---

## 3. What actually needs protecting, ranked by consequence

### 3.1 The criterion is persistence times silence

Not everything in this block deserves TMR, and the ranking cannot be
"how important does the register sound". Two questions decide it:

1. **What rewrites this register?** A register the block itself
   overwrites every tick sheds an upset on its own. A register written
   once in a mission keeps one for the mission. And *every* register in
   this file is in the power-on reset domain by W4 — the watchdog's own
   reset does not reach it — so "written once" really does mean for the
   mission.
2. **Does its corruption announce itself?** A watchdog that resets the
   part too early is wrong and loud. A watchdog that has quietly stopped
   being a watchdog is wrong and silent, and the system believes it has
   one.

Everything that is persistent *and* silent is protected. Everything the
block rewrites is not. That is the whole rule, and section 7 is the
other half of it.

### 3.2 The protected list, worst first

| Field | Bits | What one upset does |
|---|---:|---|
| `dis_q` | 1 | **Sets `armed` low and the block stops.** No expiry, no NMI, no reset, ever — with `EN` reading 0 and `WDOGSTAT.DISABLED` reading 1 on a board that never asserted the pin. This is the single worst bit in the design and it is the reason the section exists |
| `dis_seen` | 1 | Re-opens the sampling window W1 closes, turning a bootstrap pin back into a live one. On a board that ties `dis_i` high, that disarms the watchdog |
| `nmi_pend` | 1 | To 0: stage 1 never becomes stage 2, so **the watchdog warns for ever and never acts** — exactly the failure W5's key check exists to stop *software* doing, done by an upset in hardware. To 1: a system reset a full timeout early |
| `rst_seen` | 1 | The record W4 exists for. Losing it leaves the operator with a machine that reboots for no discoverable reason, which `docs/40` section 5.5 calls the worst possible failure report from a spacecraft |
| `rst_count` | 8 | Both a record and a policy. Up: the external pin asserts on a healthy part. Down: the "resetting has not worked" signal never arrives |
| `rst_hold` | 5 | The only state in this file that can assert a **system reset** on its own; downward it truncates the reset pulse the rest of the SoC is being held by |
| `tmr_err` | 1 | New. The sticky mismatch flag, section 5.3 |
| `tmr_count` | 4 | New. The saturating mismatch counter |

**22 bits at `soc_top.v`'s parameters** — `PROT_W = 17 + RST_W`, and
`RST_W = ceil(log2(RST_CYCLES + 1)) = 5` at `RST_CYCLES = 16`. The
field offsets are named constants used by the packing, the unpacking and
the register reads alike, because `docs/40` section 7.4 records what one
literal bit position cost this file.

### 3.3 What the ranking rejects, and it is most of the flip-flops

`counter`, `reload` and `pre` are **36 flip-flops against the protected
word's 22**, and they are left alone. Section 7 is the argument and
section 8.2 is the price, measured.

---

## 4. The replication bound is real, and this project has hit it twice

### 4.1 The bound

`hw/rtl/pilot_top.v` section 8.2 proves that three replicas cannot be
held apart over **one** bit: there are exactly two storage functions,
`x` and `~x`, so whichever a third replica picks it is bit-for-bit
identical to one of the other two and `opt_merge` hashes it away.
`docs/30-dispatcher-protection.md` section 3.3 re-derived the general
statement when `dstate` turned out to be two bits: over `W` bits the
affine transforms give `2 * (2^W - 1)` coordinate functions — **2** at
`W = 1`, **6** at `W = 2`, **14** at `W = 3` — and three replicas need
six distinct ones, so **three bits is the first width at which a third
replica has functions left to take**.

Six of the eight fields in section 3.2 are one bit wide. Naively
replicating any of them would produce a netlist with one flip-flop and
a voter voting it against itself, and — this is the part that matters —
**every functional test and every proof in this repository would still
pass**.

### 4.2 The answer is the bundle, not a cleverer one-bit trick

`docs/33-rail-transform.md` section 5 proves the one-bit case cannot be
rescued: a rail storing `~x` for a flag whose safe value is 0 must hold
1 after reset, this library has no asynchronous flip-flop `dfflibmap`
will use that does that, so the cell is always built by inversion and
the inversion always meets the correction. There is no portable RTL fix
at one bit.

So the bits are **concatenated into one 22-bit word and the word is
replicated**. That is the move `hw/rtl/pilot_top.v`'s own header already
names — "state bundled into one `W >= 4` bank so that MIX applies" — and
which `docs/30` could not make for `dstate`, because that state is two
bits and lives in a module with nothing else to bundle it with. Here
every protected bit is in one file and one reset domain, so the bundle
costs nothing but a naming convention. At `W = 22` the transforms offer
`2 * (2^22 - 1)` coordinate functions and three replicas need 66.

`soc_tmr_bank.v` carries an elaboration guard on `W >= 4`, because below
four bits a half of the MIX split is one bit wide, the layer-2 rotation
`(i+1) % LO` degenerates to the identity, and a stored bit can fall back
to weight 1 — silently disarming the defence. `pilot_cfg_bank` carries
that guard at its instantiation; here it is in the module, because in
this design the bundle width is what a future edit is most likely to
change.

### 4.3 Two mixed replicas rather than one, and the `docs/33` debt

The pilot pays for the XOR mixing once: A and B are separated by
polarity, and only C needs a third storage function. That is correct and
it is cheaper. It also has a consequence `docs/33` measured after the
fact: **to separate B from A on every bit, `POL_B` has to be all ones**,
which makes B's reset image all ones, which is a flip-flop `dfflibmap`
has to build by inversion, and `abc` folds that inversion against the
bank's own correction. The polarity is erased at technology mapping. It
does not matter — `dfflibmap` runs after the last pass that can merge
anything — but the artifact then carries one defence where the RTL
states two, and `docs/33` exists because a header said otherwise.

Giving B the mixing too removes the constraint:

| Replica | `POL` | `MIX` | Stored function of bit *i* |
|---|---|---|---|
| `u_prot_a` | `0x0000…` | 0 | `v[i]` — weight 1 |
| `u_prot_b` | `0x5555…` | 1 | `enc_i(v) ^ POL_B[i]` — weight 2 or 3 |
| `u_prot_c` | `0xAAAA…` | 1 | `enc_i(v) ^ POL_C[i]` — weight 2 or 3 |

B and C are separated from A because no function of weight two or more
can equal `v[i]` or `~v[i]` for any *i* — that is provable and not
measured. They are separated from each other by `POL_B = ~POL_C` on
every bit. And **neither reset image is uniform**, so `dfflibmap` has
inverters to place on some bits and not others, and its inverters land
in an XOR tree rather than annihilating against a matching one. Section
6.4 measures what that bought.

The cost of paying for the mixing twice is stated rather than glossed:
an upset in B or C now presents two or three wrong bits at that
replica's output instead of one. Against a **single** fault that is
free — they are all in one replica, which is precisely what a bitwise
majority masks. Against a **double** fault it raises the chance that two
upsets in two replicas land on the same bit of the voted word, by
roughly the same factor, order `3/22` instead of `1/22`
**[estimate on the factor; the widening itself is fact]**. It buys a
second replica that is structurally distinct after mapping as well as
before it, which is a first-order property traded against a
second-order one.

---

## 5. The power-on domain cuts both ways, and the bank is written every
cycle because of it

`docs/40` section 7.2 is the sharpest finding in that document: putting
state outside the reset domain is what makes the record survive, and it
is also what makes a stale configuration survive. **The same double edge
applies to the protection**, because the replicas are not reset either.

### 5.1 A bank that holds its value accumulates corruption

`pilot_cfg_bank` has a per-bit write enable and holds where the enable
is low, which is right for a configuration register that software
rewrites. It is wrong here. `rst_seen` is written once in a mission. The
bootstrap latch is written on the first clock after reset and never
again. A held bank repairs a corrupted replica only at the next write,
so in this domain the first upset would be masked and then **wait** —
and the second upset, in a different replica on the same bit, would not
be corrected, because two of three now disagree.

So `soc_tmr_bank` has **no write enable**: the whole word is written
from the voted value on every clock edge. That makes the voter a
continuous scrubber and bounds the exposure to a coincident second
upset at **one clock cycle** rather than the rest of the mission. It is
also cheaper per bit than the pilot's bank, because with no partial
write the MIX replica needs no decode-substitute-encode multiplexer,
only the encode in and the decode out.

`soc_wdog_tmr_props.v` states this as **T6** on its own rather than
letting it fall out of T1, so that a future change reintroducing a write
enable fails a property whose name says what was lost.

### 5.2 What is still true of the power-on domain

Nothing here changes the fact that a *reset* never repairs this word.
The scrub is what repairs it, and the scrub requires the clock. If the
clock stops, the watchdog stops and so does its protection — which is
the same gap `soc_wdog.v` already records under "no independent clock".

### 5.3 The report is inside the protected word, on purpose

`docs/16-fault-injection-campaign.md` section 5.8 measured this
repository's own safety-net report and found it was the single point of
failure: an upset could erase the announcement of the very event it
caused. `docs/16` section 5.9 is the fix, at minus two flip-flops.

So `tmr_err` and `tmr_count` are **fields of the protected word**, not
registers beside it. The write-back that repairs the replica and the
write that records the repair are the same write on the same edge, so
there is no cycle in which the report exists as separate, unprotected
state — `docs/30` section 4.2's rule applied without amendment. An upset
in the report bit itself is both corrected and counted, because it is a
disagreement like any other.

Neither field is clearable, for the same reason `WDOGRST` and `RSTCNT`
are not: a record software can erase is a record an upset can erase.

---

## 6. Does the redundancy survive synthesis?

A synthesiser is built to delete deliberately redundant logic, and this
repository has been burned by exactly that twice: `hw/rtl/pilot_top.v`
section 9 records the configuration TMR merging away entirely, and
`docs/38` section 8.5 measured **15,455 um2** of an unguarded lockstep
that the mapper was removing — a report produced without the guard
would have understated the cost of lockstep by 2.6 % while shipping a
netlist whose redundancy had been partly optimised away.

Every functional test in this repository would pass on a netlist with
one replica instead of three. So would every proof. So would the
fault-injection campaign in section 8, which deposits into RTL
registers that exist in the RTL whatever the netlist holds.
`sw/tests/test_soc_synthesis_guards.py` is the only check that looks at
what the foundry would receive.

### 6.1 The flip-flop budget, counted

`hw/soc/flow/syn_soc.sh soc_wdog`, Yosys on `ihp-sg13g2` at the typical
corner, the same recipe `docs/39` and `docs/40` measured with:

| | flip-flops |
|---|---:|
| `reload` (16) + `counter` (16) + `pre` (4), unprotected by decision | 36 |
| `u_prot_a` | 22 |
| `u_prot_b` | 22 |
| `u_prot_c` | 22 |
| **total** | **102** |

**[fact]**, and the test derives the expected 36 and 22 from the
parameter declarations and the field list in the source rather than
writing them down, so a width change moves the expectation with it.

### 6.2 With every protective attribute deleted from the text

`(* keep_hierarchy *)` on the bank is the weaker of the two defences and
is not portable to a front end that does not read yosys attributes. So
the guard deletes both attributes from the **text** of a scratch copy —
which no pass can honour and none can re-derive — and forces the flatten
before synthesis:

| sources | ASIC recipe | `synth_ecp5` |
|---|---:|---:|
| as committed | 102 | 102 |
| every `keep` and `keep_hierarchy` deleted | **102** | **102** |

**[fact]**. Nothing is lost. The POL/MIX storage transform carries the
whole structure on its own, on two different technology mappers.

### 6.3 The mutations, because a guard that cannot fail is not a guard

| mutation | mapped flip-flops |
|---|---:|
| none | 102 |
| `.MIX(0)` on replica C | **91** |
| `.MIX(0)` on replicas B **and** C | **80** |
| `HARDEN = 0` | **53** |

**[fact]**, all with the attributes deleted. The middle two are the
pigeonhole measured rather than argued: with `MIX` off, a replica stores
`v[i] ^ POL[i]`, one of the only two storage functions a single bit has,
and `POL_C = 0xAAAA…` is zero on the 11 even bits of 22 — so on exactly
those bits replica C stores what replica A stores and structural hashing
merges the pair. Eleven lost from C; eleven more when B goes the same
way. **Neither mutation is visible to any simulation or any proof in
this repository**: `.MIX(0)` is functionally identical RTL, bit for bit
at every port.

`HARDEN = 0` gives 53 and not 58, and the five missing flip-flops are
the report: with no redundancy the mismatch wire is a constant zero, so
`tmr_err` and `tmr_count` are dead and the optimiser correctly deletes
them. The test derives that too.

### 6.4 The mapped cells — the `docs/33` question, answered

Cells whose instance path lies under each replica, in the netlist
`syn_soc.sh` writes **[fact]**:

| replica | `POL` | `MIX` | cells |
|---|---|---|---|
| `u_prot_a` | `0x0000…` | 0 | 22 × `dfrbpq_1` |
| `u_prot_b` | `0x5555…` | 1 | 22 × `dfrbpq_1`, 38 × `xor2_1`, 11 × `inv_1`, 6 × `xnor2_1` |
| `u_prot_c` | `0xAAAA…` | 1 | 22 × `dfrbpq_1`, 39 × `xor2_1`, 11 × `inv_1`, 5 × `xnor2_1` |
| outside the banks | | | 539 cells, of which 36 × `dfrbpq_1` |

715 cells, 102 flip-flops, both matching `syn_soc.sh`'s own report.

**The transform reaches the mapped netlist here, and in `docs/33` it did
not.** Eleven inverters survive in each mixed replica — one per bit
where `POL` is 1 — and the two XOR cones are not the same shape as each
other (38/6 against 39/5). That is exactly the mechanism `docs/33`
section 3 identified when it explained why `u_cfg_b` escaped and the
one-bit rails did not: a non-uniform reset image means only some bits
are re-inverted, and a D cone that is a gate tree means `dfflibmap`'s
inverter is absorbed into a *different* gate rather than annihilating
against a matching one. Section 4.3 chose the masks to get this, and
this table is the measurement that says it worked.

**It is a bonus and not the defence, and this document will not repeat
`docs/33`'s mistake of describing it as one.** What stops the merge is
that no two replicas present the same stored function to `opt_merge`,
which runs *before* technology mapping. The evidence that the defence
held is the flip-flop count in 6.1 and 6.2. If a future PDK folded these
inverters away, section 6.1 would still pass and nothing would be lost.

### 6.5 Measured area

Same recipe as `docs/39` section 6 and `docs/40` section 9: Yosys
`stat -liberty` on `ihp-sg13g2` typical, `abc` with the same driving
cell, the same load, the same 20 ns delay target. Gate equivalent =
`sg13g2_nand2_1` = 7.2576 um2. The Ibex reference is **275,682.6198
um2** (`hw/soc/out/small-pmp/area.rpt`).

| Block | Cells | Flops | Area, um2 | kGE | % of Ibex |
|---|---:|---:|---:|---:|---:|
| `soc_wdog`, `HARDEN = 0` | 395 | 53 | **5,727.7962** | 0.789 | 2.078 % |
| `soc_wdog`, `HARDEN = 1` | 715 | 102 | **10,818.8514** | 1.491 | 3.924 % |
| `soc_gptimer`, `HARDEN = 0` | 1,518 | 222 | **23,841.3294** | 3.285 | 8.648 % |
| `soc_gptimer`, `HARDEN = 1` | 1,818 | 271 | **28,670.4306** | 3.950 | 10.400 % |
| `soc_wdog` as `docs/40` shipped it, at `dbbef96` | 402 | 53 | 5,785.9704 | 0.797 | 2.099 % |

**[fact for every measured row; the percentages are arithmetic on them]**

> **The cost of W6 is +5,091.0552 um2 on the watchdog, +88.9 %, and
> +1.85 % of the Ibex core** **[estimate, the difference of two
> measurements]**. Inside the GPTIMER it is +4,829.1012 um2, +20.3 % of
> that block.

Three readings.

**The comparison must be against `HARDEN = 0` and not against
`docs/40`'s 5,785.97**, and the difference is small but it is the kind
of thing this repository writes down. W6 rewrote the next-state logic as
one combinational function so that the hardened and unhardened
configurations run identical policy; at `HARDEN = 0` that refactor is
**7 cells and 58.17 um2 cheaper** than the sequential version `docs/40`
measured, at the same 53 flip-flops. Quoting the delta against the older
number would put the cost of W6 at 5,032.88 um2 — **understating it by
58.17 um2**, by crediting the hardening with a saving the refactor made.
The direction is the small one here; the habit is not.

**Where the area goes.** 49 flip-flops, and the encode/decode trees:
sections 6.1 and 6.4 account for all of it. The two mixed replicas cost
77 cells each against replica A's 22, so the mixing is 110 cells — about
a third of the increase in cells — and section 4.3 is what it buys.

**Against the alternative that was declined.** `docs/38` section 8.5
measured `SecureIbex` at 585,233 um2 against `small-pmp`'s 275,683 —
**+309,550 um2, +112 %** — for *detection* of core faults, not
correction. W6 costs **1.6 % of that** **[estimate, arithmetic on two
measurements]** and corrects rather than detects, on the block that
`docs/38` section 10 item 4 named as the only backstop that decision
left. That is not an argument that lockstep is unnecessary; it is the
observation that the cheapest thing in the ordering had not been done.

### 6.6 What the netlist census cannot see

Stated at length, because this repository has been bitten eight times by
a green check being read as wider than what it examined — `docs/28` 4.4a,
`docs/34` 8.5, `docs/36` 3.3, `docs/38` 7.3 and 8.2, `docs/39` 3, and
twice in `docs/40`, including the mutation harness that reported a pass
because a build failure produced no `FAIL` lines to parse.

- **It counts flip-flops, and asserts nothing about any other cell.**
  Section 6.4 is a *report*, not an assertion. A future PDK with a
  set-capable flip-flop would leave different cells standing, and a test
  that failed on that would be recording the tool rather than the
  design — `docs/20` section 11's rule.
- **It examines `soc_wdog` alone and `soc_gptimer` around it. It does
  not run the whole SoC through synthesis.** `soc_top.v` has never been
  synthesised as one design in this repository.
- **It says nothing about placement or routing.** No block under
  `hw/soc/` has been through either. A merge inside an OpenROAD
  optimisation pass would be invisible to it, and the pilot's own
  experience in `docs/27` and `docs/31` is that the flow can behave
  differently from what synthesis alone predicts.
- **It says nothing about whether the replicas are correct.** Three
  banks that all store the wrong function are three banks. Section 9.3
  is where the round trip is proved.
- **It says nothing about the unprotected state**, which is 36 of the
  102 flip-flops it counts.
- **It cannot detect a change of parameters at the instance.** A future
  edit setting all three replicas to the same `POL` and `MIX` would
  census as three banks under `keep_hierarchy` and collapse without it;
  the attribute-free test in 6.2 is what catches that, and
  `test_the_watchdog_instantiates_that_voter_and_three_distinct_banks`
  is a second, textual check on the same thing. Neither alone is enough.
- **It runs one liberty at one corner.** No timing was measured for any
  of this and no STA has been run on it.

---

## 7. What was deliberately left unprotected, and why

This list matters as much as the protected one, and it is longer.

### 7.1 `counter` — 16 flip-flops

An upset moves the deadline. It cannot do anything else: the counter is
reloaded at the next expiry and at every kick, so nothing accumulates,
and the bound on the displacement is the same constant W2 already fixes
— `2^WIDTH * PRESCALE` clocks, the longest timeout the block can be
talked into, because no longer value fits in the counter.

Measured, section 8.2: the worst single deadline any `counter` injection
moved was **512 clocks against the 1,024-clock bound** at the campaign's
parameters, all 16 injections left the block armed, all 16 completed the
escalation ladder, and all 16 ended in the identical final state
**[fact]**.

### 7.2 `reload` — 16 flip-flops, and this is the interesting one

`reload` **is** in the power-on domain, so by the criterion in 3.1 it
looks persistent. It is not, and the reason is a fix `docs/40` section
7.2 already had to make for an unrelated reason: **a stage-2 reset
restores the reload to the maximum.** That was written because a short
timeout software installed before it went wrong survived the reset that
going wrong caused, and bricked the SoC in an unbreakable reset loop.
The same line is what bounds an upset here: the worst a corrupted reload
can do is run one escalation ladder at the wrong timeout, after which
the block itself puts the maximum back.

So the design already contained the recovery, and W6's job was to notice
it. What W6 adds is that **the protected state records the event
correctly while it happens** — `rst_seen`, `rst_count` and the external
pin are all in the voted word — so a spurious ladder is a ladder the
operator can see.

Measured, section 8.2: 16 injections, **all 16 left the block armed, all
16 completed the ladder, none left the record weaker than the clean
run**. One produced an **extra** escalation ladder — a spurious system
reset — which is the price named here, and it is conservative in the
direction `docs/40` section 5.4 argues is the right one for a
spacecraft **[fact]**.

That one record also produced the campaign's largest number and it is
worth stating plainly: a `reload` upset moves *every* deadline until the
restore, so its **cumulative** displacement reached 1,536 clocks — more
than one full timeout — even though no **single** deadline moved by more
than 512. The first version of the acceptance criterion was written over
the cumulative figure and failed. The criterion was wrong, not the
design, and section 8.4 records it.

### 7.3 `pre` — 4 flip-flops

The prescaler phase. An upset moves the tick by at most `PRESCALE - 1`
clocks out of `2^WIDTH * PRESCALE`. Measured worst displacement: **2
clocks** **[fact]**.

### 7.4 `mtime` — 128 flip-flops in `soc_clint`, and it is not done

`docs/40` names the CLINT's counter in the same sentence as the
watchdog, and this document does not protect it. That is a decision
about **ordering**, not a claim that it is safe, and the honest ranking
puts `mtime` second:

- **It is persistent.** `mtime` is monotonic and free-running and never
  reloads, so an upset displaces it *for ever* — worse, by the section
  3.1 criterion, than anything in section 7.1 to 7.3.
- **It is fairly silent.** A single-bit flip in a high bit jumps the
  architectural clock by up to `2^63` ticks, and every deadline software
  computes as `mtime + delta` is then wrong. `docs/40` section 10 item 2
  calls it "a silently wrong clock" and that is accurate.
- **But it cannot disarm anything.** A wrong `mtime` produces wrong
  *deadlines*; the watchdog is the backstop for missed deadlines, and
  the backstop was the unprotected thing. Protecting the backstop before
  the thing it backs up is the right order, and it is the order
  `docs/40` section 13 asked for in as many words.
- **And it is expensive.** `soc_clint` is 163 flip-flops and 16,683.48
  um2, already 6.05 % of Ibex **[fact, `docs/40` section 9]**. `mtime`
  plus `mtimecmp` is 128 of those flip-flops; tripling them adds 256
  more. Scaling this document's own measured cost — 49 added flip-flops
  for 5,091 um2 — puts the same treatment of the CLINT at roughly
  **+27,000 um2, about +10 % of the Ibex core** **[estimate, a
  flip-flop-count scaling of one measurement; nothing was synthesised]**,
  more than five times what W6 cost, on state that is not the backstop.

A cheaper answer probably exists and is not designed here: `mtime`
increments by one every tick, so a residue or parity check over it would
*detect* an upset for a handful of flip-flops, at the price of correcting
nothing — the same trade `docs/30` section 3.3 took for `dstate` when
correction turned out to be unavailable. That is **[planned]** and
nothing behind it.

### 7.5 What is not protected anywhere, and is not state

The **voter is combinational**. `hw/rtl/tmr_voter.v` has no clock and no
storage, which is deliberate — "a voter never adds a failure mode of its
own" — but it means a single-event *transient* in the voter's own logic
is a fault model neither the campaign nor the proof expresses. Every
injection in section 8 is a flip-flop upset.

The **register port** into this block is unprotected: `sel_i`, `we_i`
and `wdata_i` come from `soc_gptimer`. W5's key check is what stands
between a corrupted bus transaction and this block's registers, and it
is a key check, not a code.

---

## 8. Fault injection into the watchdog's own state

The strongest evidence available is to inject into the hardened state
and show the protection classifies the upset, rather than reasoning that
it would.

### 8.1 Method

`hw/soc/tb/cocotb/test_soc_wdog_fi.py`, following
`docs/16-fault-injection-campaign.md` sections 1.2 to 1.6.

- **The DUT is `soc_wdog` itself, and only the stimulus reaches into the
  hierarchy.** Every observation is one a bench with a logic analyser
  and a register read could make: `nmi_o`, `rst_req_o`, `wdog_no`, and
  the four-bit register port. There is no pin that injects an upset.
- **Per injection:** power-on reset, bring-up (program a short reload
  and kick, so the ladder takes hundreds of clocks instead of a
  million), then a workload that runs the whole escalation ladder twice
  — alive and kicking, then a warning that is acknowledged, then two
  full ladders that are not — with one bit of one flip-flop XORed at a
  seeded-random cycle inside the measured window.
- **The golden model decides right from wrong, always.** It is a run of
  the same workload with no deposit. The design's own flags only decide
  whether a wrong answer was *announced*.
- **Targets are the replicas' storage registers**, `u_prot_{a,b,c}.bits`
  — never the voted `prot` wire. `docs/16` section 1.8 records this
  campaign's ancestor depositing into a continuously driven voter output
  twice and reporting the result as if it said something about the
  replicas; `test_00_control` asserts no target is that wire.
- **Classification**, exactly one class per injection, in `docs/16`
  section 1.6's order: HANG, DETECTED, SDC, CORRECTED, MASKED.
- **Six further per-record facts**, because five classes cannot carry
  them and the section 7 argument is about them: `order_ok`,
  `ladder_ok`, `armed_at_end`, `final_ok`, `no_weaker`, and the two
  deadline displacements.

**Harness honesty checks** run before any data point, and each is a way
the campaign could report a confident number while measuring nothing:
the clean run reproduces itself and classifies MASKED; the workload
demonstrably reaches all three stages and every stage-2 reset restores
the reload to the maximum; no target is the voted wire; **a probe
deposit into a replica must come back CORRECTED** — MASKED there means
the deposit is not landing and the whole campaign is measuring nothing;
and every drawn cycle lands inside the measured window.

**Reproducibility.** The seed is derived per target bit rather than
consumed from one stream, so the cycle drawn for `counter` bit 3 is the
same number whatever else is in the target list — which is what makes
section 8.3's counterfactual comparable target by target. Two runs of
the hardened campaign produced identical counts in every column
**[fact]**.

### 8.2 The hardened result

`make -f Makefile.soc_wdog_fi`, 162 injections, WIDTH 8, PRESCALE 4,
RST_CYCLES 8, ESCALATE 2. Clean run 488 cycles; injection window 481;
golden event order `nmi+ nmi- nmi+ nmi- rst+ rst- nmi+ nmi- rst+ wdogn-
rst-` **[fact]**.

**Whole campaign: 126 CORRECTED, 29 SDC, 7 MASKED, 0 DETECTED, 0 HANG.**
There is no DETECTED record because DETECTED means *flagged and still
wrong at the ports*, and nothing in this block produced one: every
upset the design flagged, it also corrected.

| group | n | classes | armed | ladder | order | final | worst deadline | worst cumulative |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| `u_prot_a.bits` | 42 | **42 CORRECTED** | 42/42 | 42/42 | 42/42 | 42/42 | 0 | 0 |
| `u_prot_b.bits` | 42 | **42 CORRECTED** | 42/42 | 42/42 | 42/42 | 42/42 | 0 | 0 |
| `u_prot_c.bits` | 42 | **42 CORRECTED** | 42/42 | 42/42 | 42/42 | 42/42 | 0 | 0 |
| `counter` | 16 | 11 SDC, 5 MASKED | 16/16 | 16/16 | 16/16 | 16/16 | 512 | 512 |
| `reload` | 16 | 14 SDC, 2 MASKED | 16/16 | 16/16 | 15/16 | 14/16 | 512 | **1,536** |
| `pre` | 4 | 4 SDC | 4/4 | 4/4 | 4/4 | 4/4 | 2 | 2 |

**[fact]**

**Every one of the 126 injections into the protected word came back
CORRECTED** — the ports produced the golden trace cycle for cycle, the
final register reads matched, and `WDOGSTAT.TMRCNT` moved. Not one was
MASKED, and that distinction is the whole reason the acceptance
criterion is written as "CORRECTED" and not as "never SDC": an injection
that never reached a flip-flop comes back MASKED, and MASKED is exactly
the quiet nothing a mis-targeted injector produces.

The unprotected groups are SDC against a **cycle-exact** oracle and that
is the honest classification — the deadline did move. What section 7
claims about them is not that the upset is invisible but that it is
bounded, and the four right-hand columns are that claim measured: every
one of the 36 injections left the block armed, completed the escalation
ladder and left the record no weaker than the clean run.

### 8.3 The counterfactual: the same campaign on the unprotected block

"The protection works" is not a measurement unless the same experiment
on the unprotected design produces a different number. So the harness
has a mode that builds the block with `HARDEN = 0` — exactly as
`docs/40` shipped it — and injects into the single plain register bank.
The acceptance criteria become reports rather than gates there, because
they are promises W6 makes and this is the design that does not make
them.

| group | n | classes | armed | ladder | order | final | weaker |
|---|---:|---|---:|---:|---:|---:|---:|
| `g_prot_plain.plain` | 32 | 27 SDC, 4 MASKED, **1 HANG** | **30/32** | 30/32 | **6/32** | 13/32 | **3** |
| `counter` | 16 | 11 SDC, 5 MASKED | 16/16 | 16/16 | 16/16 | 16/16 | 0 |
| `reload` | 16 | 14 SDC, 2 MASKED | 16/16 | 16/16 | 15/16 | 14/16 | 0 |
| `pre` | 4 | 4 SDC | 4/4 | 4/4 | 4/4 | 4/4 | 0 |

**[fact]**. The three unprotected rows are identical to section 8.2's,
target by target and draw by draw, which is what the per-bit seeding
buys and is also a check that the two runs differ only where they should.

> **Two of the 32 injections left the watchdog reading disarmed.** Both
> are the two draws of bit 0 — `dis_q`. One of them is the campaign's
> only HANG, recorded as "stage 1 never arrived": the watchdog stopped,
> silently, and never fired again **[fact]**.

That is the failure this whole document exists to prevent, produced on
demand, in a simulation, from a single bit flip. In the hardened block
the same two deposits are two of the 126 CORRECTED records.

Seven of the 32 also produced an **extra** escalation ladder — a
spurious system reset — and two failed to complete the ladder at all.
Against the same state in the hardened block: **0 and 0** across all 126
injections.

*Superseded in part 2026-09-05.* That zero is a property of this
campaign, whose upsets are in the watchdog's own state. The windowed
mode `docs/43-core-hardening.md` added to this block afterwards (W7)
measured **7 spurious escalations in 1,232 survivable upsets** when the
upsets are in the core — 0.6 % [0.3 – 1.2], all seven stopping at
stage 1 **[fact, `docs/43` section 8.4, `hw/soc/out/fi-h2/`]** — and
`docs/43` says this document's zero-spurious headline does not survive
that feature. It is retired here as well, where the claim is made, so
that a reader of this document alone learns it.

The third `weaker` record is neither of the disarmed pair: it is a draw
on bit 20, part of `rst_hold`, which left the part armed but with the
escalation record short of the clean run's. In the hardened block the
two draws on that bit are two more CORRECTED records.

### 8.4 Two findings from writing the criteria

**A criterion written over the wrong quantity.** The first version
asserted that no injection could move an escalation event by more than
`2^WIDTH * PRESCALE` clocks, which is the bound W2 makes a constant of
the netlist. It failed at 1,536 clocks. The design was right and the
criterion was wrong: W2 bounds a **single deadline**, and an upset in
`reload` persists across every deadline until a stage-2 reset restores
the maximum, so its effect accumulates. The harness now measures both
and asserts only the per-deadline figure, with the cumulative one
reported beside it. A criterion that had been quietly relaxed to make a
red test green would have thrown away the more interesting number.

**A harness defect presenting as a design result.** Two of 126 protected
injections came back MASKED in an intermediate run, from a design that
had masked and counted them correctly. The drawn cycle had landed after
the workload's final `WDOGSTAT` read, so the report existed and nothing
looked at it. The injection window now closes before the read-back and
`test_00_control` asserts that it does. This is the same shape as the
eight instances listed in section 6.6 — a measurement narrower than the
conclusion drawn from it — and it was caught by asking *why* an
injection was MASKED rather than recording that it was.

### 8.5 What the campaign does not cover

- **RTL, single-bit, flip-flop only.** No gate-level netlist, no
  back-annotated timing, no multi-bit strike, no single-event transient
  in combinational logic — including the voter, which has no state to
  inject into. `docs/16` section 7.4 makes the same disclaimer at
  length, and `docs/26` and `docs/32` are what closing it looked like
  for the pilot. Nothing equivalent has been done for any SoC block.
- **It says nothing about rates.** Every number is conditional on an
  upset having landed in the injection window, on a uniform choice of
  target and bit.
- **DETECTED depends on someone looking.** `WDOGSTAT.TMRERR` and
  `TMRCNT` are registers. Nothing raises an interrupt or a pin on them,
  and the software that would read them is the software the watchdog
  exists because it may have failed. `docs/16` section 7.6.
- **One workload, one parameter point, one seed.** WIDTH 8 and PRESCALE
  4; `soc_top.v` instantiates 16 and 16 and nothing here runs at those.
- **Two upsets are not covered** and nothing about three replicas claims
  they are. Section 5.1 bounds the window in which a second upset is
  uncorrectable to one clock cycle; it does not eliminate it.
- **The bring-up phase and the power-on reset are outside the window.**
- **It cannot fail because a replica vanished in synthesis.** Every
  target path exists in the RTL whatever the netlist holds. Section 6 is
  the separate criterion and neither substitutes for the other.

---

## 9. Verification

### 9.1 The regression: the hardening changed nothing

The strongest evidence that W6 is transparent to the policy is that
every measurement `docs/40` recorded reproduces **exactly**:

| | `docs/40` | now |
|---|---|---|
| whole-SoC run, checks | 22, fail mask 0 | 22, fail mask 0 |
| watchdog stage 1 | cycle 174,128 | cycle 174,128 |
| core asleep after | 185,443 cycles | 185,443 cycles |
| console | 587 characters, 0 framing errors | 587 characters, 0 framing errors |
| escalation demo | stage1 2, stage2 2, stage3 1, 37,405 cycles | stage1 2, stage2 2, stage3 1, 37,405 cycles |
| `WDOGSTAT` across three boots | `0x…000` → `0x…102` → `0x…206` | unchanged |

**[fact]**. Not one cycle moved. The whole SoC — Ibex, the fabric, the
boot ROM, the console — cannot tell the difference, which is what a
hardening that does not change behaviour should look like.

### 9.2 cocotb

| Suite | Tests | Result |
|---|---:|---|
| `test_soc_bus` | 13 | 13 pass |
| `test_soc_apb_bridge` | 11 | 11 pass |
| `test_soc_clint` | 12 | 12 pass |
| `test_soc_gptimer` | 10 | 10 pass |
| `test_soc_wdog` | 14 | 14 pass |
| `test_soc_wdog_fi` | 3 | 3 pass, 162 injections inside |

**[fact]**. The 60 tests of `docs/40` are unchanged and were re-run
against the hardened block; they are written over W1-W5 as a
specification, so they are a genuine regression on the policy and not a
description of the new implementation.

`sw/tests`, the whole tree: **279 passed** **[fact]**, including the 11
new synthesis guards.

### 9.3 Formal

| Job | tasks | result |
|---|---|---|
| `soc_bus` | bmc, prove, cover | all PASS |
| `soc_apb_bridge` | bmc, prove, cover | all PASS |
| `soc_clint` | bmc, prove, cover | all PASS |
| `soc_wdog` | bmc, prove, cover | all PASS, `prove` by k-induction |
| **`soc_wdog_tmr`** | prove, prove_w4, prove_w5, prove_w21, prove_rst1, prove_abc, bmc, cover | **all PASS** |

**5 jobs, 20 tasks, 41 of 41 cover obligations reached, 0 unreached**
**[fact]**.

**`soc_wdog.sby` now elaborates the protection**, so all of W1-W5 is
proved over the *voted* state. That is a regression statement and not a
redundancy statement, and it cannot be one: `soc_wdog` has no port
through which a fault can be injected, so in that job the replicas are
always in agreement and the voter is proved to be a wire.

**`soc_wdog_tmr.sby` adds the fault model.** Three `soc_tmr_bank`
replicas under one `tmr_voter`, with a free vector per replica XORed in
at the voter — free every cycle and over every bit, restricted only to
one faulty replica at a time, which is all a bitwise majority claims. It
proves, by k-induction:

- **T1** every replica presents the reference word — the round trip,
  which fails if `mix_enc` and `mix_dec` are not inverses, if the
  polarity is applied on one side only, or if the reset image is stored
  unencoded;
- **T2** the three agree with each other in the absence of a fault,
  stated separately because it is the redundancy claim itself;
- **T3** masking: the voted word is the reference under a fault free in
  every bit of any one replica, which may move between replicas from one
  cycle to the next;
- **T4** the mismatch flag is exactly that fault, both directions,
  because `soc_wdog` counts it into `TMRCNT` and a flag that also fired
  on clean cycles would make that count a fiction;
- **T5** the fault-free case on its own;
- **T6** the scrub — one cycle after the fault stops the replicas agree
  again, which is the property section 5.1's unconditional write exists
  for.

Four widths (22, 21, 5, 4), two reset images, and two engine families
(`smtbmc boolector` and `abc pdr`), which is `docs/09` C.4 item 7's
engine diversity expressed as a task.

Why this is worth a proof rather than a test: the failure it catches is
silent in the one direction that matters. If replica C's transform did
not round-trip, C would present a value the other two do not, the voter
would mask it, and every functional test, every proof in `soc_wdog.sby`
and the whole-SoC run would still pass. The triple redundancy would have
quietly become a duplex with a permanently wrong third rail, and the
**next** upset — in A or in B — would not be masked. Nothing observable
would have changed. That is the argument
`formal/tmr_voter_cfg_props.v` makes for the pilot, and `soc_tmr_bank`
is a different module with no write enable, a different width and MIX on
two replicas, so none of that proof carries over.

**A drift guard, because the composition is copied.** The harness rebuilds
what `soc_wdog.v`'s `g_prot_tmr` block builds, so three POL masks and
which replicas carry MIX are copied rather than proved.
`make -C hw/soc/formal wdog_tmr_params` reads all six back out of the
RTL and fails if any has moved; it runs first in the `wdogtmr` target.
Verified by mutation: changing one bit of `POL_B` in the RTL makes it
exit 1 **[fact]**. The **width** is deliberately not guarded — `PROT_W`
is computed from the field layout and reproducing that arithmetic in the
harness would be copying the thing most likely to change — so the proof
runs at four widths instead.

### 9.4 Mutation evidence for the proof

Five mutations against scratch copies, tasks `prove` / `prove_w5` /
`bmc` / `cover` **[fact]**:

| mutation | prove | w5 | bmc | cover |
|---|---|---|---|---|
| baseline | PASS | PASS | PASS | PASS |
| polarity applied **inside** the encode, `mix_enc(d ^ POL)` | FAIL | FAIL | FAIL | FAIL |
| decode rotation off by one, `c[i % LO]` | FAIL | FAIL | FAIL | pass |
| a replica **holds** its value instead of writing every cycle | unknown | unknown | FAIL | pass |
| the voter loses a majority term | FAIL | FAIL | FAIL | pass |
| **`MIX` off on both mixed replicas** | **PASS** | **PASS** | **PASS** | **PASS** |

Two rows are worth reading rather than counting.

The third returns *unknown* from `prove` at depth 4 rather than FAIL —
k-induction does not converge on it — and is caught by `bmc`. That is
recorded rather than smoothed over: the mutation is caught, by a
different task than the obvious one, and a summary that reported only
`prove` would have called it uncaught.

**The last row is the honest negative and it is the most important line
in this section.** Turning off the anti-merge transform keeps every
property in the job true, because a design in which yosys hashed the
three banks into one still satisfies T1 to T6 — there is simply one bank
answering three times. The formal job cannot see it. The netlist census
can, and measures it at 80 flip-flops instead of 102 (section 6.3).
Neither is a substitute for the other, and both are needed to say the
protection exists.

---

## 10. What is not built

1. **`mtime` and `mtimecmp` are unprotected.** Section 7.4. This is the
   top of the next hardening wave, not a closed question.
2. **`counter`, `reload` and `pre` are unprotected**, by decision, with
   the price measured. Section 7.
3. **Nothing raises an alarm on `TMRERR`.** The mismatch is counted and
   sticky in a register and that is all. A fault line into `BUSSTAT`,
   or a fast interrupt, is the obvious next step and neither exists.
4. **No windowed watchdog mode, no independent clock, no boot flow, no
   pad ring.** All four are unchanged from `docs/40` section 10.1.
5. **No place-and-route, no timing, no gate-level simulation and no
   gate-level fault injection** on any of this. The pilot has all four
   (`docs/24`, `docs/26`, `docs/31`, `docs/32`); no SoC block has any.
6. **The core's own fault-injection campaign**, which `docs/38` section
   10 item 4 made a consequence of declining lockstep, is still not
   done. This document makes it more valuable, not less: the backstop it
   would measure is now itself measured.
7. **`soc_top.v` has never been synthesised as one design.**

`docs/40` section 10.2's list of what the checkers do not cover stands
unchanged for the blocks it names; section 6.6 and section 8.5 are this
document's own additions to it.

---

## 11. Corrections to `docs/40`

- **Section 10.1 item 2** — "No hardening of any of this. The watchdog
  has no parity, no redundancy and no TMR" — is now true only of the
  CLINT and of the three registers in section 7. The watchdog's
  persistent state is triplicated.
- **Section 13's closing paragraph** asked for this work and its
  recommendation stands: the core's fault-injection campaign is still
  the next block, and `BUSSTAT` after it.
- **Section 9's area table** row for `soc_wdog` (402 cells, 5,785.97
  um2) and for `soc_gptimer` (1,500 cells, 23,733.94 um2) are
  superseded by section 6.5 here. The `soc_clint`, `soc_bus` and
  `soc_fabric_meas` rows are unaffected.
- **Section 8.2's formal table** (4 jobs, 12 tasks, 35 of 35 cover) is
  superseded by section 9.3 (5 jobs, 20 tasks, 41 of 41).

---

## 12. Files touched

`docs/34` section 2 pins the pilot by git blob hash of the files in
`hw/rtl/` and section 5 lists the flow configs. **Nothing in either set
is modified** **[fact]**.

| File | Change |
|---|---|
| `hw/soc/rtl/soc_tmr_bank.v` | new |
| `hw/soc/rtl/soc_wdog.v` | W6: the protected word, the three replicas, the voter, the report; `HARDEN` parameter |
| `hw/soc/formal/soc_wdog_tmr_props.v`, `hw/soc/formal/soc_wdog_tmr.sby` | new |
| `hw/soc/formal/soc_wdog.sby` | reads the two new sources |
| `hw/soc/formal/Makefile` | `wdogtmr` and `wdog_tmr_params` targets |
| `hw/soc/tb/cocotb/test_soc_wdog_fi.py`, `Makefile.soc_wdog_fi` | new |
| `hw/soc/tb/cocotb/Makefile.soc_wdog`, `Makefile.soc_gptimer` | read the two new sources |
| `hw/soc/flow/sim_soc.sh`, `hw/soc/flow/syn_soc.sh` | the same, plus the `attrmap` before the final flatten — see below |
| `sw/tests/test_soc_synthesis_guards.py` | new, 11 tests |
| `docs/41-watchdog-hardening.md` | this document |
| `docs/00-index.md` | one row, which `sw/tests/test_doc_links.py` requires |
| `README.md` | the fault-tolerance paragraph, which said the watchdog was unprotected |

**`hw/rtl/tmr_voter.v` is read and not modified.** The watchdog
instantiates it in place, so the SoC's majority gate is the one
`formal/tmr_voter.sby` proves exhaustively and `hw/tb/test_tmr_voter.py`
checks against an independent Python model, rather than a copy that can
drift. `test_the_voter_is_the_blob_the_pilot_freeze_pins` asserts
`git hash-object` still gives `62b5f4d2a1ea…`, which is both a check
that the freeze holds and a check that the SoC has not forked the
primitive.

**One change to `syn_soc.sh` deserves naming**, because it was a
measurement defect and not a feature. The final flatten now strips
`keep_hierarchy` first. Without that line `flatten` skips the three
replica instances, `stat -liberty` reports four modules, and the awk
that parses it silently reads cells and flip-flops from one scope and
the area from another: the hardened watchdog measured **715 cells, 204
flip-flops, 6,188.50 um2** against a true **102** flip-flops and
**10,818.85 um2** **[fact]**. A census that reads the wrong scope is the
same defect `docs/33` records one level up, and it was caught by the
flip-flop count being impossible rather than by the area looking wrong.

---

## 13. Reproducing this

```
# behaviour is unchanged
hw/soc/flow/sim_soc.sh                          # 22 checks, 185,443 cycles
SW_DEFINES=-DWDOG_RESET_DEMO \
  hw/soc/flow/sim_soc.sh hw/soc/out/sim-soc-wdog   # the escalation ladder

cd hw/soc/tb/cocotb
make -f Makefile.soc_bus
make -f Makefile.soc_apb_bridge
make -f Makefile.soc_clint
make -f Makefile.soc_gptimer
make -f Makefile.soc_wdog
make -f Makefile.soc_wdog_fi                    # 162 injections

# the counterfactual of section 8.3
SOC_WDOG_FI_UNHARDENED=1 make -f Makefile.soc_wdog_fi \
  EXTRA_COMPILE_ARGS=-Psoc_wdog.HARDEN=0 \
  SIM_BUILD=sim_build_soc_wdog_fi_h0 \
  COCOTB_RESULTS_FILE=results_soc_wdog_fi_h0.xml

cd hw/soc/formal && make                        # five jobs, twenty tasks
make -C hw/soc/formal wdog_tmr_params           # the drift guard alone

.venv/bin/python -m pytest sw/tests             # 279, incl. the 11 guards

hw/soc/flow/syn_soc.sh soc_wdog                 # 715 cells, 102 flops
hw/soc/flow/syn_soc.sh soc_gptimer
```

The `HARDEN = 0` rows of section 6.5 are produced by the same two
commands with `parameter integer HARDEN = 1` temporarily set to 0 in
`hw/soc/rtl/soc_wdog.v`; `syn_soc.sh` takes no parameter override.
`sw/tests/test_soc_synthesis_guards.py::test_harden_zero_removes_the_replicas`
does the same thing through `chparam` and asserts the flip-flop count,
so the configuration is exercised on every run of the suite even though
the area figure is not.

---

## 14. What the next block should be

Unchanged from `docs/40` section 13, and this document strengthens the
recommendation rather than altering it: **the management core's own
fault-injection campaign.** `docs/38` section 10 item 4 left the
question "whether the watchdog suffices is open", and the arithmetic has
moved again — the backstop now not only exists but is measured, so the
campaign can ask how much of the core's silent-error rate a *protected*
backstop catches rather than how much an unprotected one appears to.

Two smaller things should be scheduled behind it and named here so they
do not become omissions: **`mtime`**, which section 7.4 ranks above
everything this document left in section 7, and **a fault line for
`TMRERR`**, which section 10 item 3 leaves as telemetry nobody is
obliged to read.
