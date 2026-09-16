<!--
SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
SPDX-License-Identifier: CC-BY-4.0
-->

# 82 — Gate-level fault injection inside the gated domains: T2, raised on the layout

`docs/76-the-second-and-third-clock-gates.md` section 14 item 2 and
`docs/77-the-clock-gate-enables-and-what-actually-costs-them.md` section
17 item 2 ask for the same experiment, and each says why it is the one
that matters:

> **A gate-level fault-injection campaign into the gated domains.**
> `docs/76` section 14 item 2, unchanged and now sharper: T2 says a
> frozen fault line true in cycle N has the block clocked at the end of
> N+1, and **nothing in either document raises one**. `docs/74`'s and
> `docs/75`'s machinery already runs on a LibreLane netlist; the arms
> are this document's two layouts, and the question is whether the
> detected-fault rate moves. It is the one experiment that could
> falsify section 4.

T2 was proved on an abstraction (`hw/soc/formal/clkgate_wake.v`, three
free inputs) and executed at RTL on a fault-free workload, where the
case it is about — a slow term rising while the clock is stopped — is
unreachable by construction (`docs/77` section 8: "a slow term can only
rise while the clock is stopped if an upset raises it, and neither
workload injects one"). This document injects one. It takes the
gate-level bench of `docs/74`, elaborates it on the two layouts
`docs/77` built and on the ungated layout `docs/76` built, walks every
flip-flop's clock pin back to its root so that "inside the accelerator's
domain" is a list of netlist indices and not a CTS figure, and then does
two things: it flips replica bits of the accelerator's cause bank while
the block is asleep and counts the edges until the gated clock net
rises — which is T2, measured on the cell that implements it — and it
runs the bench's ordinary single-bit campaign into flip-flops of both
gated domains at cycles where the domain is asleep, on all three arms,
at the same sites.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file in the working tree; **[estimate]** = derived or
judged; **[assumption]** = chosen, with the effect of choosing
differently stated.

**The pilot is untouched and so is every frozen directory.**
`docs/34-pilot-freeze.md` pins the TTIHP26b submission by git blob hash
and the shuttle closes 2026-09-21. **Nothing in `hw/rtl/`, `hw/tb/`,
`tt/`, `formal/` or `hw/openlane/` is modified, and `hw/tb/Makefile.fi`
was not invoked.** `hw/soc/pnr/runs/` was read and not written. No file
under `hw/soc/rtl/` is modified by this document; the netlists it
injects into are the ones `docs/76` and `docs/77` signed off, and the
RTL they were mapped from is commit `5384ee5`'s.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Does stopping a block's clock cost a detection?** | **No, and the one arm that behaves differently is the one without a gate.** Of the 23 injections that run on all three arms, the classification differs on exactly one: a fabric ownership bit that the two GATED arms mask and the UNGATED one hangs on. Section 7. |
| **Does T2 hold on a placed netlist?** | **Yes, exactly, with no variance.** A fault line forced true while the block is asleep has its own clock back after **2 edges on all 75 injections** of the registered-wake arm, and 1 on both controls. Section 6. |
| **Is the upset recorded?** | **Every time.** All 75 injections changed the sticky word, and all 25 of each control. A stopped clock delays the recording by one edge; it does not lose it. |
| **What is the 2 made of?** | The price of taking the fault line OUT of the gate's enable and putting it behind a flip-flop --- exactly the trade `docs/77` made and priced, now measured on a placed netlist rather than argued from an abstraction. The combinational arm's 1 is the other side of the same trade. |
| **What do the two gated arms say about each other?** | **Nothing, and that is a result.** They are identical in all 23 campaign records but one latency value. The difference between the registered wake and the combinational enable lives entirely on the fault lines and does not reach the ordinary state of the blocks they gate. |
| **How big is the sample?** | **Small, and stated as small**: 23 injections per arm at 23 sites and one cycle each, on one workload, plus 75 direct-test injections on the gated arm. No rate is computed from it. Section 7.3. |
| **What did nine of the 32 planned sites do?** | **Held an unknown value at their injection cycle, on every arm identically, and were skipped.** They are reset-less registers in a domain whose clock is stopped, in a workload that never writes them: there is no state there to upset. Counting them is the measurement. |

---

---

## 2. What was asked, stated on the cell

### 2.1 T2, and what it predicts at the clock-gate output

`docs/77` section 6.2 proves, with no assumption:

| | statement |
|---|---|
| **T2** | `slow(N−1) ⟹ en(N)` — a frozen term true in any cycle has the block clocked at the end of the next |

and `docs/76` section 5.1 says what "the end of the next" is on an
`sg13g2_lgcp_1`: the latch is transparent while `CLK` is low, closes on
the rising edge, and `GCLK = latch_q & CLK`, so **the enable's settled
value during cycle N decides the edge that ends cycle N**.

The bench names edges: edge *c* is 10 ns × *c* after reset release and
a force lands a quarter cycle after it (`docs/74` section 5.2a). So an
upset forced at edge *c* is a term that is true during cycle *c*. On
`docs/76`'s combinational enable (`s77base`), that term is in the
enable in the same cycle and the gate passes **edge *c*+1**. On
`docs/77`'s registered wake (`s77gate`), `wake_q` samples the term at
edge *c*+1, `en_i` is high during cycle *c*+1, and the gate passes
**edge *c*+2**. T2 is the statement that it is never later than that,
and on the ungated layout (`s76base`) the flip-flop's clock is `clk_i`
and the next edge is *c*+1 whatever the enable says.

The record therefore carries one number per injection that T2 is a
bound on: **`own_first` − `cycle`**, the number of free-clock edges
between the force and the first rising edge of the injected
flip-flop's OWN clock net. **1** is a flip-flop that is being clocked;
**2** is the registered wake's one cycle; **−1** is a flip-flop whose
clock never came back before the run ended.

### 2.2 Which upset raises a frozen term

`docs/77` section 6.4 lists the nine fault lines and censuses that
eight of them reach no input port. The one this document raises
directly is `prot_mismatch`, the accelerator's cause-bank voter
disagreeing with one of its three replicas (`soc_npu.v`, `sticky_ev[C_CFG_TMR −
C_STICKY0] = prot_mismatch`). It is chosen because it is the only fault
line whose source is a set of flip-flops the netlist names and this
project has already censused at gate level (`docs/75` section 3: the
NPU cause bank's **25 / 25 / 25** by the voter's fan-in cone), so
"flip one replica bit" is a site list and not a search. Flipping any
one of the 75 makes the voter disagree with that replica in the same
delta; the vote itself does not move; and the line is a function of
registers that are not being clocked, so it stays up until they are —
which is exactly the shape of term T2 is about.

It is also recorded in two places the bench can read without a clock
from the block: the sticky bit `C_CFG_TMR` of the protected word,
which needs the block's clock (that is the point), and
`soc_busstat.v`'s `NPUTMR` counter, which is on the ungated clock and
**counts every cycle the line is high** (`if (ev[gi]) cnt_q <= cnt_q +
1`, `hw/soc/rtl/soc_busstat.v` line 369). The second is a clock the
fault line does not control, so the counter's increment is a
measurement of how many free-clock edges the line stood before the
block was clocked and the replica rewritten: **1 on a combinational
enable, 2 on the registered wake** if T2 holds, more if it does not.

---

## 3. The domains, flip-flop by flip-flop

`docs/76` section 7 and `docs/77` section 12.2 give each domain's
population as a count per clock root out of the CTS log, which names no
flip-flop. `hw/soc/flow/clkgate_domains.py` (new) reads the netlist,
takes every flip-flop's `CLK` pin and walks it back through the clock
tree — buffers and delay cells only; a cell with more than one input on
a clock path is refused — to the first net that is either an
`sg13g2_lgcp_1`'s `GCLK` or has no driving cell. The root is the domain,
and every flip-flop gets one.

| root | `s77gate` | `s77base` | `s76base` | CTS log, `s77gate` |
|---|---:|---:|---:|---:|
| `u_ibex.clk` (Ibex's own gate) | 2,323 (2,312 with a public Q-net name) | 2,323 | 2,323 | 2,323 |
| **`clk_npu`** | **2,089** (2,010 named) | 2,089 | — | 2,089 |
| **`clk_bus`** | **55** (55 named) | 55 | — | 55 |
| `clk_i` (`clk_i_regs`, ungated) | 1,405 (1,255 named) | 1,404 | 3,551 | 1,405 |
| total | **5,872** | 5,871 | 5,874 | |

**[fact, `clkgate_domains.py` on the three `final/nl/soc_top.nl.v`;
the last column is `CTS-0010` / `CTS-0011` in each run's CTS log]** —
the walk reproduces the CTS sink counts on every root of all three
layouts, and the roots sum to the flip-flop count the bench elaborates.
That is control 5 of section 4.2, and it is what licenses calling a
netlist index "inside the accelerator's domain".

What the two gated domains hold, read off the same table on `s77gate`
**[fact]**:

- **`clk_npu`, 2,089**: the frozen die, `u_npu.u_node0.*`, **1,242**;
  the wrapper's own registers, `u_npu.*` outside the die, **736**
  (the three 25-bit cause-bank replicas, the two queues with their
  replicated pointers, the window and event FSMs, the serial
  transport, `wake_hold[1:0]`); the fabric-side read-data register
  `s_rdata_npu[31:0]`, **32**; and **79** anonymous flip-flops, which
  are the mixed and inverted replica bits yosys builds without a
  name (`docs/75` section 3.4).
- **`clk_bus`, 55**: `soc_bus`'s state exactly as `docs/76` section 7
  itemises it — `issue_en`, `err_rvalid`, `last_was_d`, the two
  two-bit outstanding counters, the two three-bit locks, and the seven
  four-deep ownership queues with their two-bit fill counts.
- **`wake_q` is on the ungated clock, as `docs/77` section 5.1 says it
  must be.** It has no name in the netlist; the cell that drives
  `g_clkgate.u_npu_cg.en_i` is one `sg13g2_nand3_1` (`_54122_`) and
  its `A` input is the Q of `sg13g2_dfrbpq_1 _79254_`, whose `CLK`
  pin is `clknet_leaf_25_clk_i_regs` — domain `clk_i` in the table,
  netlist index 341. The enable's fan-in cone cut at every
  flip-flop holds **2,011** flip-flops: 1,674 of Ibex, 218 on `clk_i`,
  107 on `clk_npu` and 12 on `clk_bus` **[fact, `gl_netlist.py`'s
  `cone_flops` on the `en_i` net]**. The 107 on `clk_npu` include
  the cause-bank replicas: not through `npu_act_slow`, which is behind
  `wake_q`, but through the accelerator's interrupt output, Ibex's
  controller and the fabric's request — which is `docs/77` section 3's
  path, seen from the other end. **A single replica upset cannot use
  it**, because the interrupt is a function of the VOTED word and one
  replica does not move a vote; section 6 checks that the enable did
  not move in the force's own delta.

---

## 4. The arms, and the controls

### 4.1 Three builds of one bench

| arm | layout | netlist md5 | flip-flops | enable | build |
|---|---|---|---:|---|---|
| **gated, registered wake** | `s77gate` | `f9606a3e…` | 5,872 | `docs/77`'s: `req_i \| psel_i \| wake_q \| wake_hold` | `hw/soc/out/gl77` |
| **gated, combinational** | `s77base` | `97953c51…` | 5,871 | `docs/76`'s: one OR over 28 terms including `\|sticky_ev` | `hw/soc/out/gl77base` |
| **ungated** | `s76base` | `517ed47e…` | 5,874 | none, `CLKGATE = 0` | `hw/soc/out/gl77ungated` |

**[fact, each build's `provenance.txt`]**. `s77base` is byte-identical
to `docs/76`'s `s76gate` (`docs/80` section 3: same DEF and netlist
digest), so the second arm is `docs/76`'s layout under `docs/77`'s
name, and the three netlists differ by the enable and by nothing this
campaign injects into: every site is chosen by Q-net name and a name
that is absent from any arm is injected into none. All three are
elaborated by `hw/soc/flow/fi_core_gl.sh` from the same RTL build
directory `docs/74` used (`hw/soc/out/fi-h74rtl`: the same workload
bytes, the same ELF symbols) with Icarus 13, and all three carry the
clock-gate shadow of section 5.3.

`hw/soc/out/gl75*` are not these builds: they are `docs/75`'s, on
`s71boot`, `s75w9` and the two synthesis netlists, none of which has a
clock gate (`provenance.txt` in each).

### 4.2 The controls

`docs/42` section 5.1's discipline, `docs/74` section 7's list, run
by `gl_gated.py golden` on every arm before anything was injected:

| control | `s77gate` | `s77base` | `s76base` (ungated) |
|---|---|---|---|
| **1.** the bench elaborated as many flip-flops as the netlist parse lists | 5,872 = 5,872 | 5,871 = 5,871 | 5,874 = 5,874 |
| **2.** the clean run's length, against the RTL bench's | 18,681 (RTL 18,682) | 18,681 (RTL 18,682) | 18,682 (RTL 18,682) |
| **2.** its signature, console characters and hash | `9c07ef12`, 19, `6d6942c8` | the same three | the same three |
| **2.** the idle window it opens and closes on | 206..16,910 | 206..16,910 | 208..16,910 |
| **3.** the clean run reproduces, and is identical with the watchdog held off | yes, 18,681 | yes, 18,681 | yes, 18,682 |

**[fact, `gl_gated_controls.log` in each build directory.]** The three
arms agree on the workload to the character. Where they differ is the
gate and only the gate: the ungated arm's window opens two cycles later
and its clean run is one cycle longer, and its `npu_first_low` is -1
because a clock that never stops has no first low edge to report.

---

## 5. The bench, and the one thing that had to change

`hw/soc/tb/tb_soc_fi_gl.v` is `docs/74`'s instrument. Three things
were added, **each off by default**, so that every record `docs/74`
and `docs/75` report is produced by the same bench behaviour as
before.

### 5.1 The release waits for the flip-flop's own clock

`docs/74` section 4.1's upset is a force on the cell's `int_fwire_IQ`
from a quarter cycle after one free-clock edge to a quarter cycle
after the next. That is an upset only because the cell samples D at
the edge inside the window: a register that holds captures the
corruption, a register that reloads does not, and on release the net
returns to the primitive's own drive. **A flip-flop behind a closed
gate samples nothing at that edge.** Releasing it after one free-clock
edge hands Q back to a primitive that still holds the OLD value, and
the upset vanishes — a one-cycle transient on the output, which is
what the previous attempt's three probe records show
(`hw/soc/out/gl77/checks/primitive_a*_ownclk0.out`: `persist=0`,
`cg_bs_tmr=1`, the block clocked at *c*+2 and the force gone at
*c*+1) and which is not what a particle does to a storage node.

`+own_clk=1` holds the force until the injected flip-flop's **own**
clock net has risen once since the force, plus a quarter cycle. The
net is the one on the cell's `CLK` pin, a leaf of one clock tree
(`FI_GL_CLK_CASES`, emitted per flip-flop by `gl_netlist.py` beside
the force and release cases). For a flip-flop on a running clock this
is the same edge as before. For a flip-flop whose gate is closed it is
what a stored upset looks like from outside the cell: the node stays
flipped until the block is clocked, the cell then samples D computed
from the flipped value, and the release shows the design's decision.
A flip-flop whose clock never comes back is **never released**; the
record says so (`released=0`) and reports the value still on the net
rather than calling it persisted.

### 5.2 The observation

Every record now carries `own_first`, the edge index of the first
rising edge of the injected flip-flop's own clock after the force, and
`own_edges`, how many it had to the end of the run; and, on an arm
with the shadow, the same two numbers for the two gate outputs
`clk_npu` and `clk_bus` themselves, the two enables sampled just
before the force and one delta after it, the accelerator's cause word
voted from its three replica banks before and after, the cycles on
which a replica disagreed with the vote, and the three bus-statistics
counters `NPUCOR` / `NPUDET` / `NPUTMR` before and after. `+stop_after=N`
ends a run N edges after the injection so that a run whose only
purpose is to watch the gate open does not have to run the program to
its end; such a record is `done=0` and is not classified.

### 5.3 The clock-gate shadow

`hw/soc/fi/gl_gated.py emit-cg` writes `fi_gl_cg.vh` per netlist —
the two gated clock nets and their enables where the netlist has them
(`s76base` has neither and the free clock stands in, which the record
says through `cg_gates=0`), the 75 replica flip-flops of the cause bank
by their netlist names, a majority vote over them, and the 48 counter
flip-flops of the three `busstat` counters. `fi_core_gl.sh` compiles
it in with `-DFI_GL_CG` when the file exists, exactly as it does the
register-file and watchdog shadows. It is a bench instrument and not a
pin, in the sense `docs/74` section 4.3 gives the phrase: in silicon
the counters are `BUSSTAT` registers over the bus and the cause word is
`NPU` register space, and reading them from the bench is reading what
the CPU could read.

### 5.4 What did not change

`+own_clk=0`, the default, releases at the next free-clock edge as
`docs/74` did, at the same instants: the force at edge + `CLK_HALF/2`
and the release at the next `posedge clk` + `CLK_HALF/2`. The record
keys `docs/74`'s classifier reads are unchanged and the new keys are
appended after them; `campaign.py`'s `parse_record` and `classify` are
not modified. The three arms' clean runs publish the RTL clean run's
answer (section 4.2), which is the same check `docs/74` section 5.1
made.


---

## 6. The direct test: T2, measured on the cell that implements it

T2 is a latency bound, so the instrument is a stopwatch and not a
verdict. Every flip-flop of the accelerator's cause bank is forced to
its complement in a cycle in which the block is asleep, the force is
held until that flip-flop's OWN clock rises (section 5.2's primitive),
and the bench records the index of that edge. `own_latency` is the
number of edges the flip-flop waited: **1 is "the clock was already
running", and T2's bound --- clocked at the end of N+1 --- is 2**
[fact, the field's definition in `hw/soc/tb/tb_soc_fi_gl.v` around line
726].

Twenty-five sites per replica bank, one draw each, at 67 distinct
workload cycles.

| arm | enable | injections | `own_latency` | gate's own first edge |
|---|---|---:|---|---|
| **`s77gate`**, gated, registered wake | `docs/77`'s | **75** (25 per bank A, B, C) | **2 on every one of the 75** | 2 |
| `s77base`, gated, combinational | `docs/76`'s | 25 (bank A) | **1 on all 25** | 1 |
| `s76base`, ungated | none | 25 (bank A) | **1 on all 25** | 1 |

**[fact, `records_direct.csv` in each build directory.]**

**T2 HOLDS, exactly, with no variance.** Not "at most 2" observed as a
maximum over a distribution: 2 on all seventy-five injections, at
seventy-five different sites and sixty-seven different workload cycles.
The registered-wake gate stops the clock, the forced fault line raises
`wake_q` at the next system edge, and the gated net's first rising edge
is the one after that. The proof said one cycle of wake latency and the
netlist takes exactly one cycle of wake latency.

**The two controls say what the 2 is made of.** On `s76base` there is
no gate and the flip-flop's clock is the system clock, so the latency
is 1 and the free-running clock counts 255 or 256 edges over the same
window against the gated arm's 5 [fact, `own_edges`]. On `s77base` ---
`docs/76`'s combinational enable, which carries `|sticky_ev` --- the
latency is also 1, and that is the measurement `docs/77` section 11
predicted from the other side: the combinational gate never stops the
clock for a cycle in which a fault line is high, because the fault line
is IN its enable. The 2 is therefore the price of taking `|sticky_ev`
out of the enable and putting it behind a flip-flop, which is exactly
the trade `docs/77` made and priced, now measured on a placed netlist
rather than argued from an abstraction.

**The upset is recorded in every case.** All 75 injections changed the
sticky word (`sticky_before` differs from `sticky_after` on all 75, and
on all 25 of each control) [fact]. A stopped clock delays the
recording by one edge; it does not lose it. That is the whole of what
`docs/76` section 14 item 2 asked.

**Five of the 75 persist past the window, and they are not a
counterexample.** `persist = 1` on five rows: one bit of each of the
three configuration replicas (`u_cfg_a.bits[8]`, `u_cfg_b.bits[19]`,
`u_cfg_c.bits[8]`) and two anonymous cells in the B and C cones
[fact]. Those are configuration bits, not cause bits: nothing rewrites
them within the 64-edge window the test cuts at, so a flipped
configuration bit stays flipped, in the gated arm and in both controls
alike (each control shows one). The controls are the point --- the
persistence is a property of the register, not of the gate.

---

## 7. The campaign: does the gate change what a campaign sees?

Section 6 measured the wake path on the cell that implements it. This
section asks the question `docs/76` section 14 item 2 actually posed:
**does stopping the clock change the rate at which upsets are
detected?** One plan of 32 sites is drawn from the gated domains --- 20
in the accelerator's, 12 in the fabric's --- each with the workload
cycle at which it is injected, and the SAME plan is run on all three
arms, matched by Q-net name so that no arm is injected anywhere the
others are not.

**Nine of the 32 sites hold an UNKNOWN value at their injection cycle
and are skipped on every arm, identically** **[fact, each arm's
`gl_campaign_gated.log`]**. They are registers with no reset ---
`\u_npu.u_node0.u_lif.w_data_all` is the largest group --- inside a
domain whose clock is stopped, in a workload that never writes them: a
gate-level model leaves such a flip-flop at X until something clocks a
value into it, and forcing an unknown bit to its complement produces
another unknown. There is no state there to upset. The campaign counts
them and moves on; the first three runs of this job aborted on the
first one instead, which is why the tool now says how many rather than
how few.

That leaves **23 injections run on every arm**.

### 7.1 The result

| | | MASKED | HANG | released | never clocked |
|---|---|---:|---:|---:|---:|
| **accelerator domain**, 11 records | `s77gate` | 10 | 1 | 1 | **10** |
| | `s77base` | 10 | 1 | 1 | **10** |
| | `s76base` (ungated) | 10 | 1 | 11 | 0 |
| **fabric domain**, 12 records | `s77gate` | 9 | 3 | 12 | 0 |
| | `s77base` | 9 | 3 | 12 | 0 |
| | `s76base` (ungated) | 8 | 4 | 12 | 0 |

**[fact, `gl_gated.py report` over the three `records_gated.csv`.]** No
injection in any arm was CORRECTED, none produced silent data
corruption, and none was DETECTED --- these are ordinary data and
control flip-flops, not the fault lines section 6 injected, and nothing
in the design watches them.

**The classification differs between arms on 0 of the 11 accelerator
records and on 1 of the 12 fabric records.** The one difference is
`\u_bus.q_owner[1] [0]` at cycle 3096: the two gated arms mask it, and
the **ungated** arm hangs on it.

### 7.2 What that answers

**Stopping the clock did not cost this campaign a single detection.**
In the accelerator's domain, 10 of the 11 upsets were never sampled at
all on the gated arms --- the clock did not come back inside the window
--- and all 11 were sampled on the ungated arm, and the outcome is the
same on all three: ten masked, one hang. An upset that a stopped clock
prevents from being sampled was, in every one of these ten cases, an
upset that changed nothing when it was sampled.

**And the one arm that behaves differently is the one without a gate.**
`q_owner` is the fabric's ownership state; upset at cycle 3096 it
wedges the ungated build and is harmless in both gated builds. One site
out of twenty-three is not a claim that gating improves robustness, and
this document does not make one. It is, precisely, the falsification
that `docs/76` section 14 item 2 asked for and did not get: if the gate
degraded detection, this campaign is where it would show, and what it
shows instead is a single difference pointing the other way.

**What the two gated arms say about each other is nothing, and that is
also a result.** `s77gate` and `s77base` --- the registered wake and the
combinational enable it replaced --- are identical in all 23 records but
one latency value. The difference between those two designs lives
entirely on the fault lines, where section 6 measured it as exactly one
edge, and it does not reach the ordinary state of the blocks they gate.

### 7.3 The size of the sample, stated as the sample it is

Twenty-three injections per arm, at 23 sites, at one cycle each, on one
workload. That is small, it is stated as small, and no rate is computed
from it. What it can carry is the comparison, because the three arms
run the same 23 sites at the same cycles and differ in one place; what
it cannot carry is a cross-section, a per-bit probability, or any
statement about sites the plan did not draw. `docs/74`'s campaign is the
instrument for rates and this is not that instrument.

---

## 8. What this does NOT cover

Everything `docs/74` section 12 and `docs/75` section 10 list stands
here unchanged: the same bench, the same zero-delay cell models, the
same macros' `FUNCTIONAL` core, the same workload, the same
classifier. What is specific to this document:

- **T2 is tested on ONE of the nine fault lines.** `prot_mismatch` is
  the one whose source flip-flops the netlist names and this project
  had censused; `q_cor_ev`, `q_det_ev`, `fetch_expire`, `ser_timeout`,
  `win_expire`, `win_orphan`, `oh_expire` and `aer_stb_mm` are reached
  by the campaign of section 7 only if a drawn site happens to feed
  one, and section 7 says how many did. The proof of T2 does not
  distinguish between the lines — `slow_i` is one free input — and
  the netlist's `npu_act_slow` is one OR, so a line that reaches the
  OR reaches `wake_q` the same way; but that is an argument about the
  netlist and not a measurement on each line.
- **The die's own upsets are not fault lines, and the enable does not
  see them.** 1,242 of the 2,089 flip-flops behind `clk_npu` are
  `hw/rtl/pilot_top.v`'s. Its ERR / SEC / DED / TMR pins are level
  causes in the wrapper's cause word (`C_ERR` to `C_TMR`), not sticky
  ones, not in `npu_act_slow`, and not counted by `busstat`. An upset
  inside the sleeping die that the die's own redundancy would correct
  on its next clock is neither corrected nor reported until something
  else wakes the block. That is `docs/76` section 3.2's design and not
  a defect this document found; it is stated here because the
  campaign's `own_latency = −1` rows are mostly this, and a reader
  should not take them for the enable failing.
- **No timing.** The registered wake's one cycle is a cycle of a
  zero-delay simulation. Whether the enable meets its clock-gating
  check is `docs/77` section 9.2's question and it does not close at
  the slow corner on either layout; nothing here changes that.
- **The force lands a quarter cycle after an edge**, in a block whose
  clock is stopped, so "the term is true in cycle *c*" is exact by
  construction. A particle does not choose its instant; a term that
  rose late in the cycle on silicon would be one cycle later still
  at the registered wake, which is the same bound shifted, not a
  different one.
- **One workload, one seed, one parameter point** — `docs/42`'s
  workload, which never touches the accelerator, so every accelerator
  injection lands in a block the program never reads. That is what
  makes the accelerator's domain asleep for the whole window and it is
  also why the classifier's verdict on those records is MASKED
  regardless of what the block did: the oracle is the run's output.
  The `recorded` column is what the block did.
- **No rate, and the sample is small.** Section 7 is sized to the
  hours available on a contended machine, not to a confidence bound;
  the site list and its seed are in the plan file, and a larger draw
  is one argument.
- **Neither layout has DRC, LVS, XOR or an equivalence result**,
  `docs/71` section 11, and this document adds none.
- **Every wall figure is contended**: two place-and-route runs,
  several `sby` jobs and the riscv-formal proofs were live on this
  machine throughout, at a load of about nine on twenty cores.

---

## 9. Reproducing this

```bash
# 0. the domains, on each netlist (control 5)
python3 hw/soc/flow/clkgate_domains.py hw/soc/pnr/runs/s77gate/final/nl/soc_top.nl.v \
  --tsv hw/soc/out/gl77/domains.tsv

# 1. the clock-gate shadow and the bench, per arm (repeat for s77base -> gl77base,
#    s76base -> gl77ungated); fi_core_gl.sh compiles the shadow in when it exists
python3 hw/soc/fi/gl_gated.py emit-cg hw/soc/pnr/runs/s77gate/final/nl/soc_top.nl.v \
  hw/soc/out/gl77/fi_gl_cg.vh
hw/soc/flow/fi_core_gl.sh hw/soc/pnr/runs/s77gate/final/nl/soc_top.nl.v \
  hw/soc/out/fi-h74rtl hw/soc/out/gl77                          # shadow: -DFI_GL_CG

# 2. the controls, per arm: four clean runs, golden.json
python3 hw/soc/fi/gl_gated.py golden --build hw/soc/out/gl77 \
  --rtl-golden hw/soc/out/fi-h74rtl/golden_rtl.log

# 3. the direct test, T2: every cause-bank replica flip-flop, one draw each,
#    the force held until the flip-flop's own clock, the run cut 64 edges later
python3 hw/soc/fi/gl_gated.py direct --build hw/soc/out/gl77 --arm s77gate \
  --rtl-golden hw/soc/out/fi-h74rtl/golden_rtl.log --jobs 1 --early 300 \
  --stop-after 64 --own-clk 1 --draws 1
python3 hw/soc/fi/gl_gated.py direct --build hw/soc/out/gl77base --arm s77base \
  --rtl-golden hw/soc/out/fi-h74rtl/golden_rtl.log --jobs 1 --early 300 \
  --stop-after 64 --own-clk 1 --draws 1 --banks A

# 4. the campaign: one plan from the gated arm, run on every arm by Q-net name
python3 hw/soc/fi/gl_gated.py plan --build hw/soc/out/gl77 --npu 20 --bus 12 \
  --out hw/soc/out/gl77/plan_gated.csv
for spec in gl77:s77gate gl77base:s77base gl77ungated:s76base; do
  python3 hw/soc/fi/gl_gated.py campaign --build hw/soc/out/${spec%%:*} \
    --arm ${spec##*:} --plan hw/soc/out/gl77/plan_gated.csv --jobs 1 --own-clk 1
done
python3 hw/soc/fi/gl_gated.py report --plan hw/soc/out/gl77/plan_gated.csv \
  --arms s77gate=hw/soc/out/gl77/records_gated.csv \
         s77base=hw/soc/out/gl77base/records_gated.csv \
         s76base=hw/soc/out/gl77ungated/records_gated.csv
```

`hw/soc/out/gl77*/` are gitignored build products by `docs/38` section
11's rule; every record, log and trace this document quotes is there.

---

## 10. Files touched

| file | change |
|---|---|
| `docs/82-gate-level-fault-injection-inside-the-gated-domains.md` | this document |
| `docs/00-index.md` | one row |
| `hw/soc/flow/clkgate_domains.py` | new: every flip-flop's clock root, checked against the CTS log |
| `hw/soc/fi/gl_gated.py` | new: the clock-gate shadow, the controls, the direct test, the plan, the campaign and the report |
| `hw/soc/fi/gl_netlist.py` | `FI_GL_CLK_CASES`, one wait per flip-flop on its own clock net, emitted beside the force and release cases |
| `hw/soc/tb/tb_soc_fi_gl.v` | `+own_clk`, `+stop_after`, `+cgtrace`, the clock-gate shadow under `-DFI_GL_CG`, and the own-clock observation on every record; all off by default |
| `hw/soc/flow/fi_core_gl.sh` | compiles `fi_gl_cg.vh` in when it exists, as it does the two other shadows |

**Nothing in `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is
modified and `hw/tb/Makefile.fi` was not invoked. No file under
`hw/soc/rtl/` is modified by this document.** `hw/soc/pnr/runs/` was
read and not written; the run directories that appeared there during
this work (`s84rdreg`, `s84clint4`) are the owner's and were not
touched.

**The execution suites were not run for this document and did not need
to be.** Nothing under `hw/soc/rtl/` changed, so `scripts/run_cocotb.sh`
and `pytest sw/tests` would be measuring the same tree they measured for
`docs/77`; the artefacts this document produces are campaign records
under `hw/soc/out/gl77*`, which are gitignored build products by
`docs/38` section 11's rule. What was run, and is reported in sections 6
and 7, is the bench itself: three elaborations, nine control runs and
144 injections.

---

## 11. What the next block should be

1. **The other eight fault lines, raised one at a time.** Section 8's
   first bullet. Each has a source register the netlist names
   (`q_cor_ev` the queue pointers' replicas, `q_det_ev` the entries'
   parity, `aer_stb_mm` the two strobe flags, the four expiries their
   guard counters); the direct test of section 6 is one site list per
   line and the same `--stop-after 64` run. It is the same afternoon
   of machine time as section 6, and it turns "T2 on one line" into
   "T2 on nine".
2. **The die's status pins in the enable, or a reason not to.**
   Section 8's second bullet: an upset inside the sleeping die is
   neither corrected nor reported until the block is next used. The
   die's `tmr_seen` / `sec_seen` / `ded_seen` pins are its own sticky
   registers (`hw/rtl/pilot_top.v` lines 2533 to 2535, `sticky_tmr`
   and its siblings), which is frozen, so they cannot rise without
   the die's clock and cannot be a wake term; a periodic wake — `wake_hold` fired from
   the scrubber's interval, say — is the shape of a repair, and what
   it costs is `docs/76` section 8.4's idle figure. That is a mission
   decision, and it should be priced before it is built.
3. **A larger draw of section 7's plan.** The plan file carries the
   seed and the site list; `--npu` and `--bus` are the sample, and
   nothing else about the campaign changes with them.
4. **`docs/77` section 17's other items are untouched by this
   document**, and item 1 there (`WAKE_GNT`) was built concurrently
   with this work on a different RTL than these netlists; its layout,
   when it exists, is a fourth arm for exactly this campaign.
