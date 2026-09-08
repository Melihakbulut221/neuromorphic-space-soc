# 75 — A correction that cost a reset, and a census that could not have seen a merge

`docs/74-core-gate-level-campaign.md` closed with two things and they
are the same thing seen from two sides.

> **And in every one of the 174 the SoC reset itself one clock after the
> upset.** … the honest class for these 174 is a reset the announcement
> channel missed.

> Counted by name, the watchdog's protected word has **29, 14 and 15**
> replica flip-flops in the netlist … counted by the voter's fan-in
> cone, **29, 29, 29**.

The first is a protection that works and charges the mission a restart
for every upset it corrects. The second is an instrument that, on the
object closest to silicon, reports half of two replicas missing. Both
came out of the same act: **measuring the netlist instead of the RTL.**
This document does the census work first, because if the replicas were
not what the corpus said they were then the 174 injections landed on a
structure nobody had described — and then repairs the reset path,
proves the repair, and measures it the way this project measures.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file in the working tree; **[estimate]** = derived or
judged; **[planned]** = an intention with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is modified and
`hw/tb/Makefile.fi` was not invoked. `hw/rtl/tmr_voter.v` is **read** in
place by the watchdog, the boot block and the NPU, exactly as before.
`hw/soc/pnr/runs/` was read and not written except for this document's
own new run directory. Section 12 lists every file.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Was any published replica count wrong?** | **No. Not one.** All nine replicas of the three TMR structures were re-measured by the voter's fan-in cone: the watchdog's **29 / 29 / 29**, the boot block's **23 / 23 / 23**, the NPU cause bank's **25 / 25 / 25**, in the block synthesis the guards use AND in every one of the **65 whole-SoC netlists the working tree has kept** **[fact]**. `docs/41`'s 22 per replica, `docs/55`'s 21, `docs/56`'s 25 and `docs/69`'s 23 were each right at the width the word had when they were written. Section 3 |
| **Then which instrument was undercounting?** | **Not the guards'.** The waves did **not** rely on the census `docs/74` section 6.6 caught undercounting. That is a census by **Q-net name**, built in `docs/74` for a different job — mapping RTL site names onto netlist flip-flops. Every guard in `sw/tests` counts by **instance path**, which is a different instrument, and in the guards' own recipe `flatten` runs *after* `dfflibmap`, so the flip-flop built behind an inverter for a reset-to-one bit is created inside the bank module and keeps the prefix. Measured on one netlist, side by side: instance path **29 / 29 / 29**, cone **29 / 29 / 29**, Q-net name **0 / 14 / 15**. Section 3.2 |
| **Was any guard blind?** | **Not to a merge, and yes to something else — and the something else is worse.** Three banks of the right size are not three banks if the voter reads one of them twice. A voter with `.in_b(qa)` passes *every* count in this repository — per replica, total, attribute-free, both flows — and its vote is a majority over two distinct values, so an upset in replica A is not masked at all. The cone census catches it and nothing else does. Section 4.3 |
| **And the shipped netlist?** | **Nothing in this repository had ever censused it.** `docs/41` section 6.6 said so in its own list of limits, `docs/55`, `docs/56` and `docs/69` repeated it, and `docs/74` was the first document to look — by hand, once, at one structure. `sw/tests/test_soc_shipped_netlist_guards.py` is now that check, over every retained netlist, and the mutation it is proved against is a merge performed on a scratch copy of a real one. Section 4.4 |
| **What was the reset decode?** | **`assign rst_req_o = in_reset;` where `in_reset = (rst_hold != 0)` and `rst_hold` is bits 21:17 of the VOTED word.** Combinational, five bits wide, over a majority of three replicas two of which present `mix_dec` — an XOR tree over all 29 flip-flops of the bank. `soc_top.v` then builds `rst_raw_n = rst_ni && !wdog_rst_req` and hangs the SoC's reset synchroniser off it **asynchronously**, under a comment that says "rst_req is a registered signal in this clock domain". **It was not.** Section 5 |
| **Glitch, or intended?** | **Glitch, and the netlist says so three ways.** The settled decode is correct on all 174 records (the vote masked every upset and the word ends right); the same deposit at RTL does not reset; and the whole-netlist reset census shows what no argument would have: of the **five** distinct asynchronous-reset fan-in source sets in `soc_top`, four are driven by nothing or by one or two *registered* signals, and the fifth — `rst_raw_n` — is driven by **25 flip-flops of the three replica banks and nothing else**: 5 of A (exactly bits 17 to 21), 10 of B, 10 of C **[fact]**. Section 6 |
| **What is the fix?** | **W9: one flip-flop, and no behaviour change at all.** `in_reset_q` is the same predicate computed from `prot_n` instead of `prot`, so the two are equal on every cycle of every run — proved by k-induction, `soc_wdog_props.v` W9a — and `rst_req_o = in_reset && in_reset_q` is the signal it always was. In the netlist the AND of a glitchy decode with a flip-flop holding zero is zero, and the masking is logical rather than structural, so `abc` may factor it any way it likes. Section 7 |
| **Is the fix proved on the netlist?** | **Yes, by SAT on the mapped cells, not by looking at the wiring.** No assignment to the mapped netlist's inputs asserts `rst_req_o` while `in_reset_q` is zero **[fact]**, and the two mutations that could make that vacuous — removing the gate, and ORing instead of ANDing — both fail it. Section 7.4 |
| **Resets per corrected upset** | **1.0000 before, 0.0000 after, and the voter's masking rate does not move.** 174 injections into the same 87 replica flip-flops at the same 174 cycles, on two layouts from one flow: on `s71boot` every one of the 174 is CORRECTED **and** raises a `wdog_rst_o` event, with a run length of exactly injection-edge plus 18,683; on `s75w9` every one of the 174 is CORRECTED and **none** raises one **[fact]**. The two arms agree in every other field the classifier and the voter shadow produce, down to which 4 / 8 / 8 of the upset replicas held rather than being rewritten. Section 8 |
| **Is the zero a property of W9 or of the netlist?** | **W9, and the calibration is a two-by-two rather than an argument.** The same 174 injections were also run on both designs' *synthesis* netlists — mapped by `abc` on separate occasions, no clock tree, no placement: the repaired one gives **0 of 174** and the unrepaired one **174 of 174**, with the same injection-edge-plus-18,683 run length. **The row is the design and the column is nothing.** This is what `docs/55` section 8 refused a 19 % delta for the lack of. Section 8.5 |
| **What does it cost?** | **+1 flip-flop and +401.2092 um2 on the block** — 15,503.3298 to 15,904.5390, **+2.588 %**, **+0.1455 % of the Ibex core** **[fact, two synthesised designs on one source list]**. On the whole SoC, 647,548.0200 to 648,191.0736 um2, **+643.0536, +0.0993 %**, at 5,873 → 5,874 flip-flops. **And on the layout: no die area, no hold margin at any corner, no DRC, and the same deferred-error list corner for corner** — hold closes at +0.062088 / +0.231403 / +0.451156 ns against `s71boot`'s +0.062133 / +0.273524 / +0.589658, and setup *improves* by 2.1105 ns, which `docs/71`'s rule says is a delta of netlists and which this document does not claim for W9. Section 9 |
| **And what does the added flip-flop expose?** | **One unprotected bit on the reset path, and it cannot be tripled** — `hw/rtl/pilot_top.v` section 8.2's bound, one bit has two storage functions and three replicas need three. Its two corruption directions are not symmetric and neither is a way to reset the part: upset to 1 is masked by `in_reset` = 0, and upset to 0 during a genuine stretch is a one-clock notch that `soc_top.v`'s two-stage synchroniser does not pass. Section 7.3 |
| **What is not covered** | Zero-delay simulation, so the *width* of the physical glitch this repairs is still unmeasured and unmeasurable here; one workload, one seed; no timing, DRC, LVS or equivalence on either layout; the cone census cannot run in the attribute-free flow, where `abc` dissolves every net it could anchor on. Section 10 |

---

## 2. The order, and why the census comes first

Two open items, and the cheaper one is done first because its result
could change how the other reads: **if the replicas were not what the
documents said, then `docs/74`'s 174 injections landed on a structure
nobody had described**, and nothing that follows from them means what
it says.

They were what the documents said. Section 3 is that measurement, and
it is reported before anything else because it is the licence for
everything after it: the 174 injections of `docs/74` section 10.2, and
the ones in section 8 of this document, went into three banks of 29
flip-flops each, disjoint, exactly as `docs/41` designed and every wave
since has claimed.

---

## 3. The census, re-measured

### 3.1 Three instruments, and they do not agree

There are three ways to ask which flip-flops belong to a replica, and
the corpus has used two of them without ever putting them side by side.

| instrument | what it counts | where it works | where it does not |
|---|---|---|---|
| **by instance path** | flip-flops whose flattened cell name carries `…u_prot_b.` | every recipe in `sw/tests`, because `flatten` runs after `dfflibmap` there and the inverted flop is created inside the bank module | LibreLane's `soc_top.nl.v`, where every cell is `_00268_` |
| **by Q-net name** | flip-flops whose Q net is called `…u_prot_b.bits` | nothing, on this technology | anywhere `dfflibmap` has run: the flop that stores an inverted bit is a **different cell** from the one that carried the name, and it carries none |
| **by fan-in cone** | flip-flops the voter's input actually depends on | everywhere the voter's input net survives — the guards' flows and the shipped netlist | the attribute-free flow, section 3.5 |

`docs/74` section 6.6's "29, 14 and 15" is the middle row, and the
question this document had to answer is whether the hardening waves had
been relying on it. **They had not.** `docs/41`, `docs/55`, `docs/56` and
`docs/69` each reported a count taken by `Census.in_instance` in
`sw/tests/test_soc_synthesis_guards.py`, which is the first row. The
middle row belongs to `hw/soc/fi/gl_netlist.py --census`, which exists
to map `docs/42`'s RTL site names onto netlist flip-flops for the
gate-level campaign, and which `docs/74` is itself the document that
caught, corrected and replaced with a cone.

### 3.2 `docs/74`'s two numbers, reproduced

```
$ python3 hw/soc/fi/gl_netlist.py \
      hw/soc/pnr/runs/s71boot/final/nl/soc_top.nl.v --wdog-census
watchdog protected word, replica flip-flops by cone: A 29 (29 named),
B 29 (14 named), C 29 (15 named)
5873 flip-flops
```

**[fact]**, on the file `docs/74` names, `md5
2e43d08ff422be8ce7a0efd17b1cc3da`, 10,831,575 bytes, unmodified. 29/29/29
by cone and 29/14/15 by name, exactly as published.

### 3.3 Every published count, by all three instruments

The cone census was generalised from the watchdog to any TMR structure
(`hw/soc/fi/gl_netlist.py --tmr-census`) and run over the block
synthesis each guard performs and over the shipped netlist:

**Block synthesis — the object the guards examine [fact]**

| structure | published | document | by instance path | by cone | by Q-net name |
|---|---:|---|---|---|---|
| `soc_wdog` `u_prot_a/b/c` | 29 | `docs/41` (as 22), `docs/43` widened it | **29 / 29 / 29** | **29 / 29 / 29** | 0 / 14 / 15 |
| `soc_boot` `u_prot_a/b/c` | 23 | `docs/69` | **23 / 23 / 23** | **23 / 23 / 23** | 0 / 11 / 12 |
| `soc_npu` `u_cfg_a/b/c` | 25 | `docs/55` (as 21), `docs/56` widened it | **25 / 25 / 25** | **25 / 25 / 25** | 0 / 12 / 13 |

**The shipped netlist, `s71boot`'s `final/nl/soc_top.nl.v` [fact]**

| structure | by cone | by Q-net name | union of the three cones |
|---|---|---|---:|
| `u_timer0.u_wdog.g_prot_tmr` | **29 / 29 / 29** | 29 / 14 / 15 | **87** |
| `u_boot.g_prot_tmr` | **23 / 23 / 23** | 23 / 11 / 12 | **69** |
| `u_npu.g_cfg_tmr` | **25 / 25 / 25** | 25 / 12 / 13 | **75** |

The boot block's 23/23/23 and 23/11/12 are `docs/74` section 6.6's, and
the NPU's **25/25/25 against 25/12/13 is new** — that structure had
never been looked at in a whole-SoC netlist at all.

**And over the whole retained corpus.** The same census was run on
**every whole-SoC netlist in the working tree — 65 of them**, 18
LibreLane final netlists and 47 synthesis netlists, from `s45` through
this document's own `s75`:

| structure | netlists containing it | by cone | by Q-net name | union |
|---|---:|---|---|---:|
| the watchdog's protected word | **64** | 29 / 29 / 29 in all 64 | 29 / 14 / 15 in all 64 | 87 in all 64 |
| the NPU cause bank | **35** | 25 / 25 / 25 in all 35 | 25 / 12 / 13 in all 35 | 75 in all 35 |
| the boot block's decision word | **10** | 23 / 23 / 23 in all 10 | 23 / 11 / 12 in all 10 | 69 in all 10 |

**[fact]**, every set of three disjoint. The one netlist of the 65 that
contains none of them is `s45-hier`, `docs/45`'s hierarchical
elaboration probe, which has no `soc_wdog` instance to census. **No
netlist this project has ever produced has a merged replica**, and none
has a voter reading one replica twice.

### 3.4 Why the Q-net census undercounts, restated as an arithmetic

`POL_B = 0x5555…` and `POL_C = 0xAAAA…`, so on every bit exactly one of
B and C resets to one; `sg13g2` has no set flip-flop; `dfflibmap`
legalises a reset-to-one flop as a reset-to-zero flop storing the
inverse behind an inverter; the resulting cell is not the cell the name
was attached to. The two mixed replicas therefore keep **one name per
bit of the word between them** — 14 + 15 = 29 for the watchdog, 11 + 12
= 23 for the boot block, 12 + 13 = 25 for the NPU — and
`test_the_name_census_undercounts_and_the_cone_does_not` asserts that
identity rather than the split, because the split follows from the
masks and the identity follows from the mechanism.

In the block synthesis even replica A comes out 0 by Q-net name, because
there `opt_clean` prefers `u_prot_a.q_o` to `u_prot_a.bits` for the same
net. That is the same lesson one step further: **a name is a hypothesis**
(`docs/74` section 6.1), and which alias survives is not a property of
the design.

### 3.5 Where the cone census does not work, stated

In the attribute-free flow — `keep_hierarchy` and `keep` deleted from
the **text** of the sources, `flatten` forced before synthesis, which is
`docs/41` section 6.2's strongest test — the anchor nets do not survive.
Measured: `g_prot_tmr.qb` is still a public netname in the yosys result
and **0 of its 29 bits are driven by any cell** **[fact]**, because
`abc` rewrote the cone it named and left the name pointing at bits
nothing drives. The cone census refuses such an anchor rather than
returning an empty cone (`replica_output` requires every bit driven),
and reports width 0, which the guards are written to read as *the
census failed* and never as *the replica merged*.

**So in that flow the instrument stays what it has always been: the
TOTAL flip-flop count**, which `docs/41` section 6.2 chose for exactly
this reason and whose docstring already said why. It is strictly wider
than a per-replica census and it is what catches storage lost anywhere
in the block. Measured again here, with the W9 flip-flop included:
**132 = 44 unprotected + 1 for W9's registered request + 3 × 29**, in
the ASIC recipe and in `synth_ecp5`, with every attribute deleted
**[fact]**.

---

## 4. The guards, repaired

### 4.1 One cone implementation, not two

`sw/tests/test_soc_synthesis_guards.py` now imports
`hw/soc/fi/gl_netlist.py` and runs **the campaign's own cone walker** on
its own yosys result, rather than carrying a second copy of the idea.
That is the rule
`test_the_verdict_rule_is_one_file_and_not_two_copies_of_one` states
about the STA verdict, applied to this. The walker is generic over the
key type, so one function serves two front ends — nets in a structural
netlist, bit indices in a yosys JSON — and
`test_the_two_instruments_agree_on_every_replica_of_every_structure`
runs both against the instance-path census on all nine replicas.

### 4.2 What the cone adds that the count cannot

A count says each replica is the right size. It cannot say the three
are **different**. The new assertion is that the three cones are
pairwise disjoint and their union is 3 × PROT_W — 87, 69 and 75 — which
is the property the vote actually needs.

### 4.3 The mutation, and it is the finding of this section

`test_a_voter_wired_to_one_replica_twice_is_caught_only_by_the_cone`
changes one argument in a scratch copy of `soc_wdog.v`:

```verilog
    tmr_voter #(.WIDTH(PROT_W)) u_prot_vote (
        .in_a     (qa),
        .in_b     (qa),      // was qb
```

Measured on that design **[fact]**:

| check | intact | mutant |
|---|---|---|
| `in_instance` per replica | 29 / 29 / 29 | **29 / 29 / 29** |
| total flip-flops | 132 | **132** |
| cone per voter input | 29 / 29 / 29 | 29 / 29 / 29 |
| **union of the three cones** | **87** | **58** |
| **flip-flops shared by two voter inputs** | 0 | **29** |

`(* keep *)` on `soc_tmr_bank`'s storage keeps replica B's flip-flops in
the netlist although nothing reads them, so the mutant is a design with
three intact banks whose vote is `maj(qa, qa, qc) = qa`. **An upset in
replica A is not masked.** Every count in this repository passes on it,
every functional test passes, every proof passes — the mutation is
never made in the tree — and the cone census fails.

It is worth naming the shape precisely, because it is not the one this
work went looking for: **not an instrument that undercounted, but an
instrument that counted the right number of the wrong thing.**
`hw/rtl/pilot_top.v` section 9 records the pilot's configuration TMR
merging away entirely and `docs/33` records this repository getting the
distinction between "the storage is there" and "the storage is
distinguishable" wrong once already. This is the third member of that
family and the first one a flip-flop count cannot reach at all.

The anchor had to be the **voter's own input pin** for this to work.
Anchoring on the bank's output wire `qb` — which is the same net in a
correct design — misses it, because in the mutant `qb` still exists and
is still driven by replica B; it is simply not what the voter reads.
`replica_output` therefore tries `u_prot_vote.in_b` first and falls back
to `qb` only where that name did not survive, which is the shipped
netlist, and it **reports which candidate it used** in every row.

### 4.4 The shipped netlist, checked for the first time

`sw/tests/test_soc_shipped_netlist_guards.py` is new and runs the cone
census over every whole-SoC netlist the working tree has kept. Its
mutation is a merge performed on a scratch copy of a real netlist:
every flip-flop the voter reads through `qc` has its Q net renamed onto
the corresponding flip-flop of replica B, which is what `opt_merge`
leaves behind — one bank, read twice — at an unchanged flip-flop count.
The guard fails on it **[fact]**.

Those files are git-ignored build products, so on a fresh clone these
tests **skip**, with the command that regenerates them. A skip here is
not evidence of anything and the file says so.

---

## 5. The decode, found

### 5.1 What it is

`hw/soc/rtl/soc_wdog.v`, as `ad3d068` shipped it:

```verilog
  wire [RST_W-1:0] rst_hold  = prot[P_RSTHOLD +: RST_W];
  ...
  wire in_reset = (rst_hold != 0);
  ...
  assign rst_req_o = in_reset;
```

`P_RSTHOLD` is 17 and `RST_W` is 5, so `rst_hold` is bits 21:17 of
`prot`, and `prot` is `prot_store`, which is the **voter's output**.
`rst_req_o` is therefore a five-input OR-reduce of a combinational
function of `maj(qa, qb, qc)`, where `qb` and `qc` are `mix_dec` of
their banks' storage — a product of two unit-triangular GF(2) matrices,
which is to say an XOR tree over all 29 flip-flops of the bank.

And `hw/soc/rtl/soc_top.v`:

```verilog
  // The synchroniser is not decoration. rst_req is a registered signal
  // in this clock domain, so rst_sys_n would otherwise DEASSERT on a
  // clock edge, which is a recovery-time violation at every flop in the
  // SoC. Asynchronous assert, synchronous deassert, two stages.
  wire wdog_rst_req;
  wire rst_raw_n = rst_ni && !wdog_rst_req;

  reg [1:0] rst_sync;
  always @(posedge clk_i or negedge rst_raw_n)
```

**The consumer documents the assumption and the producer did not meet
it.** That sentence is the whole finding of this section. It is not a
disagreement about what the design should do; it is a stated invariant
that was false, in a comment written by the same hand that wrote the
producer, and nothing in the repository checked it.

### 5.2 Glitch, or a decode that is right about another case?

There are three readings available — a transient on the decode during
the cycle the voter is correcting; a decode that is combinationally
correct and a reset that was intended for a case this one resembles;
or something else — and the evidence has to pick one rather than the
reader.

**It is a glitch on the decode, and not a decode that is
combinationally correct about a case this one resembles.** Three
measurements, and none of them is an argument:

1. **The settled value is right on all 174 records.** `docs/74`
   section 10.2's probe shows `qa`, `qb` and `qc` agreeing on the
   correct word two nanoseconds after the edge, with `rst_raw_n` having
   fallen and risen inside one time step; the run's published signature,
   mask, console and magic are golden on every one of the 174.
2. **The same deposit at RTL does not reset.** `docs/74` section 10.2
   item 2 measured it on the HEAD RTL, and this document re-measures the
   whole of it: the RTL clean run and the **complete 2,451-bit flip-flop
   trace of the core over all 18,682 cycles are byte-identical** before
   and after W9, so nothing in the RTL of either design is doing what
   the netlist does. Section 7.5.
3. **The whole-netlist reset census, section 6**, which shows that this
   is the only asynchronous reset in the SoC whose fan-in is a decode
   at all — so there is no "case this one resembles" anywhere else in
   the design to have been designed for.

It is a glitch **in its detail** and a hazard **in its substance**, and
`docs/74` section 10.2 item 1 draws that line correctly: the order in
which twenty-nine flip-flops propagate through an XOR tree in one delta
is the simulator's, and silicon has no deltas. What silicon has is
twenty-nine clock-to-Q delays and an XOR tree of unequal path lengths
feeding a voter feeding an asynchronous reset with no synchroniser and
no filter. **This document does not measure the width of the physical
pulse and cannot** — section 10.

---

## 6. Every asynchronous reset in the SoC, and what feeds it

The sharpest measurement in this document, and it needed no simulation.
`hw/soc/fi/gl_netlist.py --reset-cones` groups every flip-flop's
`RESET_B` net by the **set of flip-flops that feeds it
combinationally**. On `s71boot`'s netlist — 5,873 flip-flops, 1,949
distinct reset nets **[fact]**:

| sources | reset nets | flip-flops reset | what the sources are |
|---:|---:|---:|---|
| 0 | 1,255 | 1,651 | the power-on port, directly |
| 1 | 644 | 3,955 | `rst_sys_n` |
| 2 | 32 | 173 | `rst_sys_n` and `u_npu.u_node0.soft_rst` |
| 2 | 17 | 92 | `rst_sys_n` and `u_npu.flush_pulse` |
| **25** | **1** | **2** | **`u_prot_a.bits` × 5, `u_prot_b.bits` × 10, `u_prot_c.bits` × 10** |

**[fact]**. Four of the five source sets are a port or one or two
*registered* signals, and a flip-flop's output does not glitch. The
fifth is `rst_raw_n` — the net the SoC's reset synchroniser hangs off,
and therefore the net every other flip-flop in the design is ultimately
held in reset by — and its combinational fan-in is 25 flip-flops of the
watchdog's three replica banks and **nothing else**. Replica A
contributes exactly the five flops at positions 17 to 21, which is
`rst_hold`; B and C contribute ten each, because their mixed decode
needs two stored bits per decoded bit.

Two readings follow and both are worth stating.

**The NPU got this right, for the reason the watchdog got it wrong.**
`u_npu.flush_pulse` and `u_npu.u_node0.soft_rst` are *registers*, one
bit each, and `blk_rst_n = rst_ni && !flush_pulse` is an AND of a port
and a flip-flop. That is W9's shape, arrived at independently in
`docs/51`'s block because the flush is naturally a pulse. The watchdog's
stretch is naturally a counter, and a counter has to be decoded.

**The boot block has no reset output at all.** `soc_boot.v`'s ports are
the APB slave and the pins; the decode of its voted word reaches
register reads and nothing else. So the hazard is unique to the
watchdog, and this is measured over the netlist rather than inferred
from the RTL.

**And the same census on the repaired design.** On `s75w9`'s netlist
the five source sets are the same five and the wide one is **26**: the
same 25 replica flip-flops, plus `u_timer0.u_wdog.in_reset_q`, which
survives to the top level of the flattened netlist under its own name
**[fact]**. The 25 are still in the cone and that is the point — W9
does not remove them, it makes them unable to assert without a
flip-flop's agreement, and section 7.4 is the proof that `abc` did not
undo it. A structural check alone could not tell the two apart, which is
why `test_every_asynchronous_reset_is_driven_by_a_flip_flop_that_dominates_it`
is written as the weaker of the two guards and says so.

---

## 7. W9

### 7.1 What it is

```verilog
  reg in_reset_q;
  always @(posedge clk_i or negedge rst_por_ni) begin
    if (!rst_por_ni) in_reset_q <= 1'b0;
    else             in_reset_q <= (prot_n[P_RSTHOLD +: RST_W] != 0);
  end

  assign rst_req_o = in_reset && in_reset_q;
```

`prot` is `prot_n` one clock later — through the three replicas and the
voter when `HARDEN` is on, through `plain` when it is off — so
`in_reset_q` and `in_reset` are **equal on every cycle of every run**.
`rst_req_o` is the signal it was, bit for bit, and nothing about the
block's policy, its ladder, its stretch length or its register map
changes.

It is computed from `prot_n` and **not** registered off `in_reset`
deliberately: registering `in_reset` would make the flop the decode's
own output one clock late, so a glitch straddling an edge could be
sampled by it, and the assertion would be delayed by a cycle as well.
This way the flop's D is the pre-storage function, which is settled at
the edge for the same reason every other flop's D is.

### 7.2 Why the gate survives resynthesis

The masking is **logical**, not structural. `abc` may factor
`(|rst_hold) & in_reset_q` any way it likes; every product term it can
produce still contains `in_reset_q`, because proving it redundant would
need sequential reasoning a combinational mapper does not have. That is
why section 7.4 is a SAT proof about the mapped cells and not a search
for an AND gate in the wiring.

Confirmed on the shipped-netlist census: after W9 the one wide reset
cone is **26** flip-flops — the same 25, plus
`u_timer0.u_wdog.in_reset_q`, present by name at the top level of the
whole-SoC netlist **[fact]**. The 25 are still there, and that is the
point: they are still in the cone and they can no longer assert it.

### 7.3 What the added flip-flop costs, stated rather than netted off

It is one unprotected bit on the reset path and **it cannot be
tripled**. `hw/rtl/pilot_top.v` section 8.2 proves that three replicas
cannot be held apart over one bit — there are two storage functions and
a third replica is bit-for-bit identical to one of the other two — and
bundling it into the protected word would put it back behind the very
decode W9 exists to get the reset out from behind. So it is single, and
its two corruption directions are not symmetric:

| upset | effect |
|---|---|
| `in_reset_q` 0 → 1 while the word says no reset | `rst_req_o` stays 0: the AND still has `in_reset` = 0. **The upset cannot assert the reset on its own** — it is masked by the very term it was added to guard. What it does do is put the block back into its pre-W9 shape for one clock, so a change of the protected word *in that same clock* could glitch through; that is the coincidence below and it needs two events. |
| `in_reset_q` 1 → 0 during a genuine stage-2 stretch | `rst_req_o` drops for one clock inside a `RST_CYCLES`-clock assertion, so `wdog_rst_o` shows a notch an operator watching the pin would see as two pulses. It does not shorten the reset: `soc_top.v`'s two-stage synchroniser needs **two** clocks of `rst_raw_n` high before `rst_sys_n` rises, and one is not two, so the SoC's flip-flops stay in reset for the whole stretch. The two synchroniser flip-flops themselves see a runt on their own asynchronous reset — that is a recovery question about two flops and not a release of the SoC, and it is **not measured here**. |

Neither direction is a way to reset the part. What remains is a
**coincidence**: an upset in `in_reset_q` in the same cycle as a change
of the protected word, which needs two events, and it is named here
rather than argued away.

### 7.4 Proved on the netlist, with the mutations

`test_no_transient_of_the_voted_word_can_reach_the_system_reset`
synthesises `soc_wdog` to `sg13g2`, reads the mapped netlist back with
the cells' own liberty functions, and asks yosys's SAT solver whether
any assignment asserts `rst_req_o` with `in_reset_q` at zero.

```
Imported 2468 cells to SAT database.
Import proof-constraint: \rst_req_o = 1'0
SAT proof finished - no model found: SUCCESS!
```

**[fact]**. And the mutations, because a guard that cannot fail is not a
guard **[fact]**:

| mutation | flip-flops | the proof |
|---|---:|---|
| none | 132 | **passes** |
| `rst_req_o = in_reset` (the pre-W9 design, exactly) | **131** | cannot be stated: `in_reset_q` drives nothing, `opt_clean` deletes it, and yosys refuses the constraint. The guard fails on a MISSING signal rather than passing on one. |
| `rst_req_o = in_reset \|\| in_reset_q` | 132 | **`SAT proof finished - model found: FAIL!`** — the flip-flop is present, the count is unchanged, and the logic is wrong. |

The second mutation is the one that matters: it says the proof is about
the logic and not about whether a name is in the file.

### 7.5 The behaviour did not change, and it is measured four ways

The argument is that `in_reset_q == in_reset` on every cycle, so
`rst_req_o` is unchanged. `docs/64`'s standard is that an argument of
that kind is checked, not trusted.

| what | HEAD, `ad3d068` | with W9 |
|---|---|---|
| `hw/soc/flow/fi_core.sh`'s clean run, `SOC_ROM_HARDEN=0` | 18,682 cycles, signature `9c07ef12`, mask `00000000`, 4 rounds, exit `00000000`, magic `600dc0de` | **byte-identical log** |
| the **whole 2,451-bit flip-flop trace of the core**, every site of `docs/42`'s table on every one of 18,682 cycles, 45,810,716 bytes | | **byte-identical**, `cmp` clean **[fact]** |
| `hw/soc/flow/sim_soc.sh`, the whole SoC | 220,256 cycles in the image, 415,324 for the run, 28 of 28 checks, fail mask 0, `BSTAT` `0x00030000`, 1,135 console characters, 0 framing errors | **220,256 / 415,324 / 28 of 28 / mask 0 / `0x00030000` / 1,135 / 0** **[fact]** |
| `SW_DEFINES=-DWDOG_RESET_DEMO sim_soc.sh`, the escalation ladder | `docs/68` section 8: three boots, 9,067 cycles in the third, **318,131** for the run | stage 1 at 215,040, stage 2 and 3 at 218,256, three stages seen, `RSTCNT` 2, three hand-overs, 9,067 cycles in the third image, **318,131** for the run **[fact]** |

`docs/68` section 8 asked that every document after it quote **220,256
for the program and 415,324 for the run** and say which it means. Both,
and they are unchanged.

The trace comparison is the strongest of the four and also the narrowest:
it covers the 2,451 core flip-flops `hw/soc/fi/targets.py` lists, which
is what `fi_core.sh`'s trace root elaborates, and **not** the watchdog's
own state. The watchdog is covered by the row above it and below it, and
by W9a.

### 7.6 Formal

`hw/soc/formal/soc_wdog_props.v` gains three statements and
`soc_wdog.sby` proves them at both configurations **[fact]**:

- **W9a** `in_reset_q == in_reset`, on every cycle after power-on
  reset. This is the claim the whole "no behaviour change" argument
  rests on, and it is proved by k-induction at depth 15 rather than
  argued in a comment.
- **W9b** `rst_req_o == (rst_hold != 0)`, which is the consequence a
  reader of `docs/40` and `docs/41` needs: the block's contract is
  unchanged. It duplicates the strengthening invariant I3, and is
  written out anyway because I3 is guarded by `f_armed_valid` and could
  be moved by a later proof-engineering change, while this is the
  requirement.
- **W9c** a cover, `in_reset_q && in_reset && rst_req_o`, reached at
  step 5 — because two signals that were both always zero would satisfy
  W9a and W9b and say nothing.

`bmc`, `prove`, `prove_w0` and `cover` all PASS.

### 7.7 cocotb, and the mutation that this one CAN fail on

`hw/soc/tb/cocotb/test_soc_wdog.py` gains
`test_the_registered_reset_request_tracks_the_decode_every_cycle`: it
samples `in_reset_q`, `in_reset` and `rst_req_o` on **every clock edge**
of two full climbs of the ladder, asserts W9a and W9b on each, and then
asserts that the reset was actually asserted on enough of those cycles
that the equality was not checked against zero throughout. The suite is
**15 tests, all pass** where `docs/74` reported 14 **[fact]**.

**What it cannot do, stated in the test itself:** it cannot fail on the
design W9 replaced. `rst_req_o = in_reset` and `rst_req_o = in_reset &&
in_reset_q` are the same function of the same state on every cycle, so
no simulation distinguishes them. What it catches is **W9 implemented
wrongly**, and that mutation is measured rather than imagined:

| `soc_wdog.v`, scratch copy | cocotb result |
|---|---|
| as committed | 15 tests, **0 failed** |
| `in_reset_q <= in_reset;` — the flip-flop registered off the DECODE instead of the pre-storage function | 15 tests, **1 failed**, and it is this one: *"W9a: in_reset_q is 0 and the decode of the voted word says 1"* |

**[fact, `SOC_WDOG_SRC=<mutant> make -f Makefile.soc_wdog`]**. The other
fourteen tests pass on the mutant — including the pulse-length check,
which tolerates a reset one clock late — so this is the only thing in
the RTL suite that would notice, and the mutation it notices is a real
one: a flop registered off `in_reset` samples the decode's own output,
so a glitch straddling an edge would be latched by the very flip-flop
added to reject it.

**And formal cannot see the defect W9 fixes.** `rst_req_o = in_reset`
and `rst_req_o = in_reset && in_reset_q` are the same function of the
same state on every cycle, so no proof, no simulation and no RTL
fault-injection campaign in this repository can tell them apart. It is
exactly the `.MIX(0)` shape of `docs/41` section 6.3, and it gets the
same treatment: a check on the mapped netlist with the mutations that
make it fail, plus a gate-level campaign.

---

## 8. The campaign

### 8.1 The design, and the seed problem that had to be fixed first

The question is **resets per corrected upset**, and the number that
answers it has to come from the same injections on two designs that
differ by W9 and by nothing else. Four runs, a two-by-two:

| | unrepaired | repaired |
|---|---|---|
| **the layout** — LibreLane, `config-ecc.json`, `docs/67`'s floorplan | `s71boot`, `md5 2e43d08f…`, the netlist `docs/74` measured | `s75w9`, `md5 1cf2c9a0…`, this document's, from the same flow with the same arguments |
| **the synthesis netlist it was placed from** | `s70-rom0-syn` | `s75-rom0-syn` |

The layout pair is the measurement; the synthesis pair is the
calibration, and it is there because a reader is entitled to ask
whether a netlist with no clock tree glitches at all. `docs/55` section
8 refused a 19 % delta for the lack of exactly this, and `docs/56`
section 8.2 and `docs/58` section 8.4 made the rule.

**And the seed had to be re-keyed before any of it meant anything.**
`docs/74`'s sweep keys each flip-flop's two draws on
`random.Random("%d:wdog:%d" % (SEED, flop_index))`. W9 adds one
flip-flop to `soc_wdog`, every netlist index after it moves by one, and
the same seed would have drawn **different cycles** for the repaired
design. Two arms injected at different instants are not a
counterfactual. `--plan position` keys on `(bank, position within the
bank)` instead, and the run prints the check that says those positions
are the same bits:

```
plan check: bank A, 29 of 29 flip-flops named, at positions 0:0,1:1,...,28:28
plan check: bank B, 14 of 29 named, at positions 1:1,3:3,5:5,...,27:27
plan check: bank C, 15 of 29 named, at positions 0:0,2:2,4:4,...,28:28
```

**[fact]** — every named replica flip-flop sits at the position equal to
its bit number, in every bank, in every one of the four netlists. So
position *k* of the cone-ordered bank is bit *k* of the protected word,
and the four runs inject into the same 87 bits at the same 174 RTL
cycles. `docs/74`'s default is unchanged and its 174 records still
reproduce.

The injection instant is an RTL cycle in every arm, converted by each
netlist's own measured row shift (`gl_map.py`, section 5.2 of
`docs/74`): **−1 for `s71boot` and 0 for the other three**, because
`s71boot`'s clock tree makes its flip-flops leave reset one edge later
than the RTL's and the other three netlists' do not. That is a property
of the netlist, it is measured rather than assumed, and it is why the
plan is expressed in RTL cycles.

### 8.2 The controls, per arm

Every arm ran `docs/74` section 7's controls before injecting and all
of them passed **[fact]**:

| control | `gl75base` (`s71boot`) | `gl75w9` (`s75w9`) |
|---|---|---|
| 1. the bench elaborated exactly the flip-flops the parse found | 5,873 / 5,873 | **5,874 / 5,874** |
| 2. the clean run publishes the RTL clean run's answer in every compared field | 18,681 cycles, `9c07ef12`, 19 characters, hash `6d6942c8` | **18,682 cycles**, `9c07ef12`, 19 characters, hash `6d6942c8` |
| 3. it reproduces, and is identical with the watchdog held off | yes | yes |
| 4a. positive control: bit 20 of `x2` at mid-window | CORRECTED, persisted | CORRECTED, persisted |
| 4b. negative control: a bit this program never reads | MASKED | MASKED |
| the voter shadow on the clean run | 0 mismatch cycles, `tmr_count` 0, `tmr_err` 0 | 0, 0, 0 |

**And the mapping did not move.** `gl_map.py` on the repaired netlists
returns the same category counts as `docs/74`'s on `s71boot`, entry for
entry — 663 `trace+name`, 2 `trace`, 299 `trace&alias`, 1,295 `alias`,
60 `merged`, 8 ambiguous, 95 constant, 4 weak, 1 withdrawn, 17 deleted,
7 none; 2,319 mapped and 132 not **[fact]**. W9 changed which flip-flop
is which RTL bit not at all.

### 8.3 The counterfactual: the unrepaired layout, on the pin

174 injections into the 87 replica flip-flops of `s71boot`, two cycles
each, watchdog armed, on the image that carries the voter shadow **and**
the `wdog_rst_o` event counter — which is the difference from `docs/74`,
whose sweeps ran before that counter existed and which established the
restarts from run lengths instead.

| | A | B | C | all |
|---|---:|---:|---:|---:|
| injections | 58 | 58 | 58 | **174** |
| CORRECTED | 58 | 58 | 58 | **174** |
| MASKED / SDC / DETECTED / HANG | 0 | 0 | 0 | **0** |
| golden answer published | 58 | 58 | 58 | 174 |
| voter mismatch cycles seen | 1 | 1 | 1 | 1 in every run |
| `tmr_count` after | 1 | 1 | 1 | 1 in every run |
| replica rewritten from the vote on the next edge | 54 | 50 | 50 | 154 |
| **`wdog_rst_o` events** | **58** | **58** | **58** | **174** |
| edge-sampled stage 1 / 2 / 3 | 0 | 0 | 0 | **0** |

**[fact, `hw/soc/out/gl75base/records_gl_wdog.csv`]**. **Resets per
corrected upset: 1.0000.** `docs/74` section 10.2's 174 of 174, its 20
replicas that held rather than being rewritten (4 + 8 + 8), and its
mismatch and `tmr_count` of exactly one, all reproduce.

And the restart is visible a second way, which is the one `docs/74` had:
**every record's cycle count is its injection edge plus exactly
18,683** — the clean run, started again — on all 174, with no spread at
all **[fact]**. The two channels disagree in the way that matters:
`wdog_rst_o` **fired** on every run and the edge-sampled stage counters
say **nothing happened**, in the same record.

### 8.4 The repair

The same 174 injections, into the same 87 bits at the same 174 RTL
cycles — **the two plans are identical row for row, `(bank, cycle)` for
`(bank, cycle)`** **[fact]** — on the layout of the repaired design.

| | baseline `s71boot` | repaired `s75w9` |
|---|---:|---:|
| injections | 174 | 174 |
| **CORRECTED** | **174** | **174** |
| MASKED / SDC / DETECTED / HANG | 0 | 0 |
| golden answer published | 174 | 174 |
| voter mismatch cycles seen by the shadow | 1 in every run | 1 in every run |
| `tmr_err` after | 1 in every run | 1 in every run |
| `tmr_count` after | 1 in every run | 1 in every run |
| replica held rather than rewritten, A / B / C | 4 / 8 / 8 | **4 / 8 / 8** |
| run length minus injection edge | **+18,683 on all 174** | no two the same; the run simply finishes |
| **`wdog_rst_o` events** | **174** | **0** |
| **resets per corrected upset** | **1.0000** | **0.0000** |

**[fact, `hw/soc/out/gl75base/records_gl_wdog.csv` and
`hw/soc/out/gl75w9/records_gl_wdog.csv`]**

**The number that was asked for went to zero, and the voter's masking
rate did not move.** Not "did not move much": the two arms agree in
every field the classifier and the voter shadow produce — the class on
all 174, the mismatch count, the sticky flag, the saturating counter,
and even *which twenty* of the 174 upset replicas held their corrupted
value rather than being rewritten from the vote on the next edge, bank
for bank. The only column that differs is the reset.

### 8.5 The calibration: is the zero a property of W9 or of the netlist?

A reader is entitled to two objections and both are answered by
measurement rather than by argument.

**"The repaired layout is a different layout. Perhaps it simply does not
glitch."** The synthesis netlists answer it. `s75-rom0-syn` — the
repaired design mapped by `abc` with no clock tree, no timing repair and
no placement, an independently derived netlist that shares nothing with
`s75w9` except the RTL — gives **174 of 174 CORRECTED and 0 of 174
`wdog_rst_o` events** on the same plan **[fact,
`hw/soc/out/gl75syn/records_gl_wdog.csv`]**, with the same 4 / 8 / 8
persistence and the same mismatch and count. Two independently mapped
netlists of the repaired design, one placed and one not, both zero.

**"Perhaps a netlist without a clock tree does not glitch either, and
the comparison is between kinds of netlist rather than between
designs."** `s70-rom0-syn`, the *unrepaired* design's synthesis netlist,
is the fourth arm and it closes that: **174 of 174 CORRECTED and 174 of
174 `wdog_rst_o` events**, with the same run-length signature the
unrepaired layout has — injection edge plus exactly 18,683 on every one
**[fact, `hw/soc/out/gl75synbase/records_gl_wdog.csv`]**. A netlist with
no clock tree glitches exactly as readily.

**The two-by-two, on one plan of 174 injections [fact]:**

| resets per corrected upset | unrepaired | repaired |
|---|---:|---:|
| **the layout** (`s71boot` / `s75w9`) | **174 / 174 = 1.0000** | **0 / 174 = 0.0000** |
| **the synthesis netlist** (`s70-rom0-syn` / `s75-rom0-syn`) | **174 / 174 = 1.0000** | **0 / 174 = 0.0000** |

and the masking, in the same four runs:

| | `s71boot` | `s75w9` | `s70-rom0-syn` | `s75-rom0-syn` |
|---|---:|---:|---:|---:|
| CORRECTED | 174 | 174 | 174 | 174 |
| MASKED / SDC / DETECTED / HANG | 0 | 0 | 0 | 0 |
| voter mismatch cycles | 1 each | 1 each | 1 each | 1 each |
| `tmr_err` / `tmr_count` after | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| replica held, A / B / C | 4 / 8 / 8 | 4 / 8 / 8 | 4 / 8 / 8 | 4 / 8 / 8 |

**The row is the design and the column is nothing.** Four runs on four
netlists, two of them placed and routed and two not, mapped by `abc` on
four separate occasions; the reset follows the RTL and not the mapping,
and the protection's own behaviour follows neither. **The plan is
byte-identical across all four** — the same `(bank, cycle)` in the same
order, 174 rows **[fact]** — so this is one experiment with one variable.

**And what the two-by-two says about the mechanism.** The baseline
layout restarts on every one of its 174 records with a run length of
exactly injection-edge plus 18,683 — no spread at all — while the
repaired layout's run lengths are simply the clean run's. That is not a
statistical difference; it is the same event happening 174 times and
then not happening 174 times, at the same 174 instants, on two netlists
from one flow whose RTL differs by one flip-flop and one AND gate.

### 8.6 What the campaign does not settle

- **It is a zero-delay simulation on both sides.** The baseline's 174
  resets are a delta-order artefact in their detail (`docs/74` section
  10.2 item 1) and a hazard in their substance; the repair's zero is
  neither, because a flip-flop holding zero masks a glitch of any width.
  So the *asymmetry* is real — the repaired design cannot produce the
  event by any timing — while the baseline's *rate* is not a silicon
  rate and is not offered as one.
- **174 injections into 87 flip-flops, two cycles each, one workload,
  one seed.** No rate, `docs/16` section 7.5.
- **Nothing was injected into `in_reset_q`**, section 7.3.
- **The classifier is `campaign.py`'s**, unchanged, and it calls all 174
  of the baseline's records CORRECTED. `docs/74` section 10.2 is right
  that this is a property of the oracle; the `wdog_rst_o` event counter
  is the channel that is not, and this document adds it to the record
  rather than reclassifying anything.

---

## 9. Cost

### 9.1 The block, on its own recipe

`docs/41` section 6.5's method: yosys `stat -liberty` on `ihp-sg13g2`
typical, `abc -D 20`, the same three files, one source list, two
designs differing by W9 and by nothing else **[fact]**.

| `soc_wdog` | cells | flip-flops | area, um2 |
|---|---:|---:|---:|
| HEAD, `ad3d068` | 959 | 131 | **15,503.3298** |
| with W9 | 985 | **132** | **15,904.5390** |
| **delta** | **+26** | **+1** | **+401.2092** |

**+2.588 % of the block** and **+0.1455 % of the Ibex core**
(275,682.6198 um2, `hw/soc/out/small-pmp/area.rpt`, `docs/41`'s
reference) **[estimate, arithmetic on measurements]**.

Against what `docs/41` priced W6 at — +5,091.0552 um2 for the
protection — W9 is **7.88 %** of that, and it is the part that makes the
protection stop charging the mission a restart.

### 9.2 The layout, beside the one it replaces

`docs/70` section 3.1's form: two layouts from one flow, one
configuration, one floorplan, one machine, differing by their netlists.
`docs/71` measured that this flow is bit-reproducible, so every
difference below is a difference of netlists and of nothing else
**[fact, both `final/metrics.json`]**:

| | `s71boot`, HEAD | `s75w9`, with W9 | delta |
|---|---:|---:|---:|
| setup WNS, worst corner, ns | −9.1085 | **−6.9980** | **+2.1105** |
| setup TNS, ns | −19,989.82 | **−8,658.87** | +11,330.95 |
| setup WNS, typical corner, ns | +1.7820 | +3.0394 | +1.2574 |
| hold WS, fast corner, ns | +0.062133 | +0.062088 | −0.000045 |
| hold WS, typical corner, ns | +0.273524 | +0.231403 | −0.042121 |
| hold WS, slow corner, ns | +0.589658 | +0.451156 | −0.138502 |
| placed standard-cell area, um2 | 876,321 | 888,851 | +12,530 |
| instances | 176,663 | 176,746 | +83 |
| routed wirelength, um | 4,248,250 | 4,346,366 | +98,116 |
| die area, um2 | 4,786,290 | **4,786,290** | **0** |
| `route__drc_errors`, the router's own count | 0 | 0 | 0 |
| deferred errors at the end of the flow | setup at the slow corner; max slew and max cap at three corners | **the same list, corner for corner** | — |

**Hold closes at all three corners in both, the router reports zero DRC
in both, and the die does not change by one database unit.** Setup
improves by 2.1105 ns and TNS by 11,331 ns.

That zero is the **router's** count and not a sign-off result:
`RUN_MAGIC_DRC`, `RUN_KLAYOUT_DRC`, `RUN_KLAYOUT_XOR` and `RUN_LVS` are
all off in this configuration and `docs/71` section 11 says why. Neither
layout has a DRC, LVS or XOR result, and this document adds none.

**That improvement is not claimed for W9 and is stated so that it cannot
be read as one.** `docs/71` established that a delta between two layouts
of this flow is a delta of netlists, and this netlist differs from
`s71boot`'s by considerably more than W9: `abc` re-mapped the whole
design at the same delay target and produced **740 more cells** for one
added flip-flop and one added gate (section 9.3). `docs/70`'s control
pair — two netlists differing by a one-cell refactor — moved setup by
0.5031 ns, so 2.1105 is 4.2 times that control and is a real movement of
the netlist rather than of the tool; what it is *not* is a property of
the one flip-flop this document added. **What is claimed is the negative
statement, which is the one that matters here: W9 costs no die area, no
hold margin at any corner, no DRC and no new class of deferred error.**

### 9.3 The whole SoC, synthesised

`hw/soc/flow/syn_soc_top.sh 20`, `SOC_MEM=sram`, the ROM unhardened,
which is `docs/70` section 3.1's configuration and the one `docs/71`
placed **[fact]**:

| | `s70-rom0-syn`, HEAD | `s75-rom0-syn`, with W9 | delta |
|---|---:|---:|---:|
| cells | 45,546 | 46,286 | +740 |
| flip-flops | 5,873 | **5,874** | **+1** |
| `soc_top` chip area, um2 | 647,548.0200 | 648,191.0736 | **+643.0536** |
| reported area including macros, um2 | 685,153.2744 | 685,796.3280 | +643.0536 |

**+0.0993 %**. The area delta at the top is **larger than the block's
401.2092**, and the cell count moves by 740 for one added flip-flop and
one added gate. That is not a cost of W9 and it is not netted off
either: it is the mapping noise `docs/70` section 6 and `docs/71`
measured and named — the same design re-mapped by `abc` at a delay
target lands differently — and the two figures are reported side by
side rather than one of them being chosen. The number a reader should
carry is **+1 flip-flop**, which is exact, and **about 400 um2 on the
block**, which is measured on the smallest scope that isolates the
change.

### 9.4 Wall, and it is contended

**Every figure below was measured on a machine running this document's
own place-and-route, two of its own gate-level sweeps at six and eight
jobs, and two sibling projects.** Load average was between 4 and 31
throughout and was above 28 for the whole of detailed routing.
`docs/74` section 14 and `docs/71` section 14 make the same statement;
these numbers are worth less than theirs.

| | n | wall | per simulation |
|---|---:|---|---|
| `syn_soc_top.sh 20` on the repaired RTL | 1 | **3 m** | — |
| `pnr_soc_top.sh s75w9`, `Yosys.JsonHeader` through `Checker.*` | 1 | **2 h 44 m 03 s** (22:26:34 to 01:10:37) | — |
| gate-level image, elaborated by Icarus 13 | 4 | **3 s** each | — |
| gate-level clean run with the 110 MB flip-flop trace | 4 | up to **20 m** under this load | — |
| `gl_map.py`, 5,874 flip-flops against 2,451 RTL bits | 3 | **1 m 43 s** | — |
| the sweep, unrepaired layout `s71boot`, 8 jobs | 174 | **2 h 42 m** | 440 s of one job; median 426 |
| the sweep, repaired layout `s75w9`, 8 jobs | 174 | **2 h 30 m** | 341 s; median 350 |
| the sweep, repaired synthesis netlist, 6 jobs | 174 | **2 h 36 m** | 260 s; median 253 |
| the sweep, unrepaired synthesis netlist, 5 jobs | 174 | **3 h 15 m** | 265 s; median 232 |

**The unrepaired arms are the slow ones, and that is the finding showing
up in the cost column**: every injection in them restarts the SoC, so
every simulation runs the workload roughly twice. On the layouts,
**76,554 s of simulator CPU against 59,321** for the same 174
injections; on the synthesis netlists, **46,082 against 45,160**
**[fact]**. The layout pair's 29 % is the resets and the difference in
how long a restarted run takes to reach its budget; the synthesis
pair's 2 % is not, because those two runs were contended differently —
which is exactly why no conclusion in this document rests on a wall
figure.

---

## 10. What this does NOT cover

Everything `docs/74` section 12 and `docs/42` section 9 say still
stands. What is specific to this document:

- **No timing, and therefore no measurement of the thing W9 prevents.**
  The gate-level model is zero-delay. Whether the physical glitch on
  `wdog_rst_req` in the *unrepaired* layout is ever wide enough to
  reset the flip-flops it reaches is a question of `s71boot`'s own
  parasitics, and **nothing in this repository asks it**: static timing
  analysis does not check the width of a glitch on an asynchronous
  reset. `docs/74` section 10.2 item 1 drew that line and this document
  does not move it. What is measured here is that the hazard exists in
  the netlist, that the RTL cannot express it, and that after W9 no
  assignment to the mapped netlist can assert the reset without a
  flip-flop's agreement.
- **The one-clock notch of section 7.3 is argued from `soc_top.v`'s
  synchroniser, not measured.** No injection was made into
  `in_reset_q`; it is one flip-flop of 5,874 and the sweeps in section
  8 draw from the replica banks.
- **The cone census does not work in the attribute-free flow**, section
  3.5, and the total flip-flop count is what guards that flow. So the
  disjointness assertion — the one that catches a voter reading one
  replica twice — is made in the flows that keep the bank as a module,
  and not in the one that deletes every attribute.
- **The census reads whatever netlists the working tree has kept.** On
  a fresh clone `sw/tests/test_soc_shipped_netlist_guards.py` skips
  entirely, and a skip is not evidence.
- **One workload, one seed, one parameter point**, and the injection is
  a single-bit upset in storage. No single-event transient in
  combinational logic, which for this finding is a particular gap: the
  hazard W9 removes is precisely a transient, and the campaign that
  measures W9 injects only into flip-flops.
- **Neither layout has DRC, LVS, XOR or an equivalence check**,
  `docs/71` section 11, and this document adds none.
- **`docs/74` section 12's list of what its own campaign does not cover
  applies unchanged** to the sweeps in section 8, which use the same
  bench, the same classifier and the same clean run.
- **The two guards on W9 are not the same strength and are not
  interchangeable.** The SAT proof is a statement about the mapped
  netlist of `soc_wdog` alone, synthesised by this file's own recipe;
  the structural check on the shipped netlist only asserts that W9's
  flip-flop is *in* the reset's fan-in cone, which does not by itself
  make it dominate. Nothing in this repository runs the SAT proof on
  `soc_top`'s netlist, and the reason is mechanical rather than
  principled: the SRAM macros are black boxes yosys's SAT pass cannot
  import.
- **The 65-netlist census is a census of what this machine kept.** Most
  of those netlists are historical and several are configurations no
  document ships; the agreement across them is evidence that no flow
  this project has run has ever merged a replica, and it is not a
  statement about any netlist that was not retained.
- **Nothing here re-measures the other blocks' gate-level behaviour.**
  The boot block's 23 replicas and the NPU cause bank's 25 were
  censused and **not** injected into, at gate level, by this document or
  by `docs/74`.

---

## 11. Reproducing this

```bash
# ---- the census, which needs no simulation ----
python3 hw/soc/fi/gl_netlist.py <netlist.v> --tmr-census wdog   # boot, npu
python3 hw/soc/fi/gl_netlist.py <netlist.v> --reset-cones
python3 hw/soc/fi/gl_netlist.py     hw/soc/pnr/runs/s71boot/final/nl/soc_top.nl.v --wdog-census

# ---- the guards ----
.venv/bin/python -m pytest sw/tests/test_soc_synthesis_guards.py                            sw/tests/test_soc_shipped_netlist_guards.py

# ---- formal, and the cocotb mutation ----
cd hw/soc/formal && make wdog && cd -
cd hw/soc/tb/cocotb && make -f Makefile.soc_wdog && cd -
sed 's/in_reset_q <= (prot_n\[P_RSTHOLD +: RST_W\] != 0)/in_reset_q <= in_reset/'     hw/soc/rtl/soc_wdog.v > /tmp/mutant.v
cd hw/soc/tb/cocotb && make -f Makefile.soc_wdog SOC_WDOG_SRC=/tmp/mutant.v     SIM_BUILD=sim_build_mutW9 COCOTB_RESULTS_FILE=results_mutW9.xml

# ---- the repaired design, synthesised and placed ----
SOC_MEM=sram SOC_ROM_HARDEN=0     hw/soc/flow/syn_soc_top.sh 20 $PWD/hw/soc/out/s75-rom0-syn
SYN_NETLIST=$PWD/hw/soc/out/s75-rom0-syn/soc_top.netlist.v \
PNR_CONFIG=$PWD/hw/soc/pnr/config-ecc.json \
PNR_STATE=$PWD/hw/soc/pnr/state/s75w9.state.json \
hw/soc/flow/pnr_soc_top.sh s75w9 --overwrite -F Yosys.JsonHeader \
    -S Yosys.Synthesis -S Checker.YosysUnmappedCells \
    -S Checker.YosysSynthChecks -S Checker.NetlistAssignStatements \
    -i $PWD/hw/soc/pnr/state/s75w9.state.json

# ---- the RTL side, with the trace root docs/74 section 16 builds ----
mkdir -p hw/soc/out/fi-h75rtl
python3 hw/soc/fi/gl_map.py --emit-rtl-trace hw/soc/out/fi-h75rtl/fi_rtl_trace.v
SOC_ROM_HARDEN=0 FI_EXTRA_SRC=$PWD/hw/soc/out/fi-h75rtl/fi_rtl_trace.v \
  FI_EXTRA_ROOT=fi_rtl_trace hw/soc/flow/fi_core.sh $PWD/hw/soc/out/fi-h75rtl
VVP=$HOME/Downloads/oss-cad-suite-linux-x64-20260804/oss-cad-suite/bin/vvp
$VVP -n hw/soc/out/fi-h75rtl/tb_soc_fi.vvp +armed=1 +budget=200000 \
  +trace=$PWD/hw/soc/out/fi-h75rtl/golden_rtl.trace \
  > hw/soc/out/fi-h75rtl/golden_rtl.log
IBEX_FAULT_PORT=1 hw/soc/flow/fi_gl_alias.sh $PWD/hw/soc/out/gl75

# ---- one gate-level image per netlist, then the sweep ----
# NL is the netlist, OUT the build directory: gl75base for s71boot
# (the unrepaired counterfactual) and gl75w9 for s75w9 (the repair).
GLVVP=$HOME/.local/opt/iverilog13/usr/bin/vvp
hw/soc/flow/fi_core_gl.sh $NL $PWD/hw/soc/out/fi-h75rtl $OUT
$GLVVP -n $OUT/tb_soc_fi_gl.vvp +armed=1 +budget=200000 \
  +wdog_rld=127 +wdog_pre=16 +trace=$OUT/golden_gl.trace > $OUT/golden_gl.log
cp hw/soc/out/gl75/fi_alias.json $OUT/
python3 hw/soc/fi/gl_map.py --rtl-trace hw/soc/out/fi-h75rtl/golden_rtl.trace \
  --gl-trace $OUT/golden_gl.trace --flops $OUT/flops.tsv \
  --alias $OUT/fi_alias.json --out $OUT/map.json --report $OUT/map.txt
python3 hw/soc/fi/gl_map.py --emit-rf $OUT/map.json $OUT/flops.tsv $OUT/fi_gl_rf.vh
python3 hw/soc/fi/gl_netlist.py x --emit-wdog $OUT/fi_gl_wdog.vh
hw/soc/flow/fi_core_gl.sh $NL $PWD/hw/soc/out/fi-h75rtl $OUT   # both shadows
python3 hw/soc/fi/gl_campaign.py wdog --build $OUT --map $OUT/map.json \
  --rtl-golden hw/soc/out/fi-h75rtl/golden_rtl.log --draws 2 --jobs 8 \
  --plan position
```

**`--plan position` is not optional for the comparison** and section 8.1
says why: `docs/74` keyed each flip-flop's draw on its index in the
netlist, W9 moved every index after `in_reset_q` by one, and two arms of
a counterfactual injected at different cycles are not a counterfactual.
The default is unchanged, so `docs/74`'s own 174 records still
reproduce.

---

## 12. Files touched

| file | change |
|---|---|
| `docs/75-the-reset-on-a-corrected-upset.md` | this document |
| `docs/00-index.md` | one row |
| `hw/soc/rtl/soc_wdog.v` | **W9**: the requirement in the header, `in_reset_q`, and `assign rst_req_o = in_reset && in_reset_q` |
| `hw/soc/formal/soc_wdog_props.v` | W9a, W9b and the W9c cover |
| `hw/soc/fi/gl_netlist.py` | the cone census generalised to any TMR structure and given two front ends over one walker (`tmr_census`, `TMR_STRUCTURES`, `StructuralNetlist`, `JsonNetlist`), `--tmr-census`; `reset_cones` and `--reset-cones`; `is_flop` widened so the walker cannot step through a flip-flop it does not recognise. `wdog_replicas` is kept unchanged because `docs/74` quotes it |
| `hw/soc/fi/gl_campaign.py` | `--plan position`, the plan check that prints where each named replica flop sits, and `wdog_rst_events` in the records and the summary |
| `hw/soc/tb/cocotb/test_soc_wdog.py` | one test, section 7.7 |
| `sw/tests/test_soc_synthesis_guards.py` | the cone census beside the instance census on all nine replicas, the disjointness assertion, the voter-wired-twice mutation, the W9 SAT proof and its two mutations, the top-level reset-path assertion, and `_geometry()` grown by W9's flip-flop |
| `sw/tests/test_soc_shipped_netlist_guards.py` | new: the first mechanical census of the netlist the foundry would receive |
| `docs/40`, `docs/41`, `docs/55`, `docs/56`, `docs/58`, `docs/69`, `docs/74` | one dated in-place note each, section 13 |

`hw/soc/out/*` and `hw/soc/pnr/runs/*` are gitignored build products,
`docs/38` section 11's rule, and hold every record and log this document
quotes:

| directory | what is in it |
|---|---|
| `hw/soc/out/s75-rom0-syn` | the repaired design synthesised, `syn.log`, `area.rpt`, `soc_top.netlist.v` |
| `hw/soc/pnr/runs/s75w9` | the layout, `md5 1cf2c9a0…`, and `hw/soc/out/s75-pnr-w9.log` |
| `hw/soc/out/fi-h75rtl` | the RTL side: the clean run and the 45,810,716-byte flip-flop trace |
| `hw/soc/out/gl75` | the alias JSON `fi_gl_alias.sh` writes, shared by every arm |
| `hw/soc/out/gl75base` | **arm 1**, the unrepaired layout `s71boot` |
| `hw/soc/out/gl75w9` | **arm 2**, the repaired layout `s75w9` |
| `hw/soc/out/gl75syn` | **arm 3**, the repaired synthesis netlist |
| `hw/soc/out/gl75synbase` | **arm 4**, the unrepaired synthesis netlist |
| `hw/soc/out/s75-sim`, `s75-sim-wdog` | the two whole-SoC runs of section 7.5 |

Each `gl75*` directory holds its own `flops.tsv`, `map.json`,
`map.txt`, `golden_gl.log`, the 110 MB clean-run trace,
`records_gl_wdog.csv` and `gl_wdog.log`.

### 12.1 The suites, re-run

This work modified RTL that every SoC suite elaborates, so none of the
three is optional and all three were run to completion **[fact]**:

| suite | result | what it was |
|---|---|---|
| `.venv/bin/python -m pytest sw/tests -q` | **472 passed, 0 failed**, 3 m 32 s on an idle machine and 14 m 39 s when run beside four gate-level sweeps | `docs/74` reports 456. The 16 added are five cone and instrument tests, the voter-wired-twice mutation, three W9 guards, six shipped-netlist tests and the one `test_doc_links.py` discovers for this document |
| `scripts/run_cocotb.sh` | **396 passed, 0 failed, 0 suites not clean, exit 0** | `docs/74` reports 395; `soc_wdog` goes from 14 tests to 15 |
| `cd hw/soc/formal && make` | **14 jobs, 58 tasks, 58 PASS, 0 FAIL** | the count `docs/69` established. W9a, W9b and W9c are new statements inside existing tasks, not new tasks |
| `make -f Makefile.soc_wdog lint` | clean, Verilator 5.051, no warnings | |

And the two mutation results, which are the evidence that the new
checks can fail: `test_the_reset_gate_mutations_both_fail_the_proof`
(section 7.4), and the cocotb mutation of section 7.7, **15 tests, 1
failed, and it is the W9 test** **[fact]**.

**Nothing in `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is
modified and `hw/tb/Makefile.fi` was not invoked. `docs/34`'s freeze is
untouched.** The run directories under `hw/soc/pnr/runs/` that belong to
other sessions were read and not written; `s75w9` is this document's own
and is new.

---

## 13. Corrections to earlier documents

Every one is a dated in-place note, `docs/64` section 2's rule; no
original sentence is edited.

- **`docs/40` section 7.2**: a third way state outside the reset domain
  reaches the reset it causes, and it is not a policy question.
- **`docs/41` section 6.1**: the 22 was right and so was the instrument;
  the budget in that table is 132 today, at a 29-bit word plus W9.
- **`docs/41` section 6.6**: two more things the census could not see —
  three banks that are not three DIFFERENT banks, and the netlist the
  foundry receives — both now checked.
- **`docs/41` section 1**: W4's argument, qualified by `docs/74` section
  10.2 and closed by W9.
- **`docs/55` section 1** and **`docs/56` section 9.4**: 21 and 25 per
  replica, confirmed by the cone.
- **`docs/58` section 4.4**: the one wave with no replica count to
  re-measure, and why that is the point of H6.
- **`docs/69` section 1**: 23 per replica, confirmed by the cone; and
  `soc_boot` drives no reset, so the hazard is the watchdog's alone.
- **`docs/74` sections 6.6, 10.2 and 17 item 1**: the census is three
  instruments, and the fix is made.

---

## 14. What the next block should be

1. **The width of the glitch, on the unrepaired layout.** W9 removes the
   hazard; nothing here says how big it was. `s71boot` has extracted
   parasitics and three corners, and the question — how long
   `wdog_rst_req` can be high after an edge that changes the protected
   word — is a delay calculation on a cone of 25 flip-flops, an XOR tree
   and a majority gate. It is the one number this document wanted and
   could not have.
2. **`docs/74` section 17 items 2 to 6 are unchanged**, and none of them
   is touched here: the merged instruction register, the re-encoded
   state machines, the 587 alias-mapped bits, and the oracle.
3. **The other two TMR structures have never been injected at gate
   level.** `docs/74` censused the boot block's replicas and did not
   inject into them; the NPU cause bank was not censused until this
   document. Both are 23 and 25 flip-flops in three disjoint banks, and
   both would take one sweep each on an existing image.
4. **`in_reset_q` is one unprotected flip-flop on the reset path and
   nothing has injected into it.** Section 7.3 argues both directions of
   its corruption from `soc_top.v`'s synchroniser; two draws on the
   existing image would measure them.
5. **A guard on the property rather than on the one place it was
   broken.** W9's SAT proof asks about `soc_wdog`'s `rst_req_o`.
   Section 6's reset-cone census asks the general question — *is any
   asynchronous reset in this design driven by a decode?* — and it can
   be asked of any netlist in one second. Making it a rule with an
   allowlist, rather than a check that happens to know the watchdog's
   name, is one afternoon and would have caught this before the layout
   existed.
6. **The disjointness assertion does not run in the attribute-free
   flow**, section 3.5, because `abc` dissolves every net the cone can
   anchor on there. A `keep` on the voter's three input wires alone —
   not on the banks — would restore the anchor without restoring any
   of the defences that flow exists to remove. It is one attribute and
   one measurement.
