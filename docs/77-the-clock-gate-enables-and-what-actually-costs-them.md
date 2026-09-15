# 77 — The clock-gate enables: the fault lines are not what costs the checks, the CPU's own address is, and one check closes for a reason that is not the repair

`docs/76-the-second-and-third-clock-gates.md` section 14 ranked one
repair first and called it the only item on its list that was a defect
rather than an experiment:

> **Take `|sticky_ev` off the accelerator's enable path.** Section 9.5:
> the accelerator's clock-gating check misses by 3.96 ns at the slow
> corner, and the cone that costs it is the eleven fault lines that are
> there for observability.

**That is the wrong cone, and this document measures which one it is.**
On `docs/76`'s own signed-off netlist, with its own STA setup, cutting
the launch domains one at a time: the worst path into the accelerator's
enable that starts **inside the accelerator** — which is where every one
of the fault lines starts — is **−1.3129 ns**. The worst that starts in
the ungated domain is **−2.6166**. The **−5.0198** launches from
`u_ibex.gen_regfile_ff.register_file_i.raddr_a_i[2]`, **the flip-flop
that also gives the whole design its −6.3505 ns WNS**, and it reaches
the enable through the CPU's register-file read, the ALU, the load-store
address, the fabric's address mux and the slave decode. For the fabric's
gate the same cut is starker: **−0.7495 from Ibex, and +5.5158 MET from
everything else.**

**So the repair `docs/76` ranked first would have moved neither check.**
It is built here anyway, because it is right for a different and better
reason, and building it is the only way to prove the diagnosis on the
flow's own instrument.

**What is built.** `soc_npu.v`'s enable is split by ARRIVAL and not by
importance. `req_i` and `psel_i` stay combinational, because they are
the only two things that can rise and fall while the block's clock is
stopped. Everything else — all eight of the fault lines that are
functions of the block's registers, and the ninth is `psel_i`-qualified
— moves behind **one flip-flop on the ungated clock**. A term that is a
function of registers that are not being clocked cannot pulse and
vanish: it rises when the upset lands and it stays up until the block is
clocked, so a wake one cycle later loses nothing.

**And that is proved rather than asserted, in the two halves it divides
into.** `hw/soc/formal/clkgate_wake.sby` proves by k-induction that the
registered-wake enable is complete whenever `docs/76`'s was (**T1**) and
that a frozen term true in any cycle has the block clocked at the end of
the next one (**T2**, which needs no assumption at all and is what
covers the upset). The side condition T1 rests on — *`slow` is a
function of the block's state* — is discharged on the design by a
**fan-in cone census in yosys, cut at every sequential cell**, which
fails if any input port is reachable. **That census found a fault line
nobody's reading of the file had: `C_INJ_OVF` carries `psel_i`.**

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file in the working tree; **[estimate]** = derived or
judged; **[assumption]** = chosen, with the effect of choosing
differently stated; **[planned]** = intended, with nothing behind it yet.

**The pilot is untouched and so is every frozen directory.**
`docs/34-pilot-freeze.md` pins the TTIHP26b submission by git blob hash
and the shuttle closes 2026-09-21. **Nothing in `hw/rtl/`, `hw/tb/`,
`tt/`, `formal/` or `hw/openlane/` is modified, and `hw/tb/Makefile.fi`
was not invoked.** `hw/rtl/pilot_top.v` is instantiated and never
copied.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Do the two checks close at the slow corner now?** | **ONE DOES AND ONE DOES NOT, AND NEITHER MOVEMENT IS THE REPAIR'S TO CLAIM.** `u_bus_cg` goes **−0.7495 to +0.3966 MET** and `u_npu_cg` **−5.0198 to −4.2111**, on a pair of layouts in one session whose netlists differ by one flip-flop. Decomposed: **`soc_bus.v` was not modified**, its enable is one gate deep in both runs and 0.084 ns SLOWER in the repaired one, and its input arrives **1.2065 ns earlier** — its check closed because the netlist landed differently. The accelerator's 0.8087 ns is **0.4346 the repair** (four cells to one) and **0.4220 the netlist**. Section 9.3 |
| **Was `docs/76` right about the cone?** | **No, and the correction is measured on its own netlist.** Domain-cut STA: the accelerator's fault lines are worth at most **−1.3129 ns** of the **−5.0198**, and the fabric's gate has no non-Ibex path worse than **+5.5158 MET**. Section 3 |
| **What does cost them?** | **The CPU's own critical path.** Both checks launch from Ibex's register-file read address, through the ALU and the load-store address, and the accelerator's is **already 2.36 ns past the check's required time before the last five gates**. It is the design's WNS launch flop. Section 3.3 |
| **What was built, then?** | **The split by arrival**: `req_i | psel_i` combinational, everything else — the fault lines included — behind one flip-flop on the ungated clock. **One flip-flop, and it lands on `clk_i_regs` where CTS puts it.** Section 5 |
| **What did the safety property cost?** | **One cycle of wake latency on a fault, and provably nothing else.** T2 is a bound and not a hope: a frozen term true in any cycle has the block clocked at the end of the next. And on the two workloads measured it costs **zero cycles of anything**, because a frozen term can only rise while the clock is stopped if an upset raises it — section 8's duty figures are identical to `docs/76`'s to the cycle. Section 6 |
| **Is the proof a proof?** | **Two halves, and the document says which is which.** T1 and T2 by k-induction on the transformation, from two side conditions; A1 measured (the same bit-exact equivalence `docs/76` used, re-run here); A2 machine-checked by cone census, with the mutation that makes it fail. **What is NOT proved is what `docs/76` section 10 already said could not be: `soc_npu` instantiates the frozen die.** Sections 6 and 15 |
| **Did the behaviour change?** | **No, and it is measured twice.** The repaired gated build against its own ungated control: **5,138 paths at 415,345 clock edges, zero cycles differing.** Invariants **220,256** and **415,324**, 28 of 28, mask 0, `BSTAT 0x00030000`, 1,135 console characters, 0 framing errors; supervisor `sig = 216f8ce6`. Section 7 |
| **What did it cost in the netlist?** | **+1 flip-flop, +498 cells, +829.4454 um2 (+0.12 %) at synthesis.** The flip-flop is `wake_q` and CTS puts it on `clk_i_regs`: 1,405 ungated sinks against 1,404, with `clk_npu` at 2,089 and `clk_bus` at 55 unchanged. Section 12 |
| **How is that told apart?** | **By decomposing the slack at a boundary both netlists have**: the last cell whose fan-out leaves the enable's own chain. Above it the arrival is the CPU's and the netlist's; below it every cell exists only to compute `en_i`. And by a baseline that reproduces `docs/76`'s layout **on every metric and both checks to six decimal places**, through an interruption and a resume. Sections 9.1 and 9.3 |
| **Did the busy-power question get settled?** | **Yes, and `docs/76`'s +11.840 mW is withdrawn as a measurement of the gates.** This pair holds the gate count at three and moves busy power at typ from **45.167 to 22.142 mW**, 20.73 of the 23.03 in the same Combinational group `docs/76` localised. Idle is stable to **0.34 %** across the pair, so the one claim that document made survives on a third layout. Section 9.5 |
| **What would close the checks?** | **A wakefulness-qualified grant** — the slave refusing `gnt_o` in a cycle it is not clocked — which takes `req_i` off the combinational enable at the price of one cycle per sleep interval. **Measured: 56 intervals on the whole-SoC self-test for the accelerator and 12,153 for the fabric**, so the two are priced two orders of magnitude apart. Ranked, priced and NOT taken. Section 11 |
| **What is NOT covered?** | Section 15 |

---

## 2. Reproducing the instruments before moving them

`docs/44` section 5.2's rule, and it matters more here than usual: this
document's first claim is that a published number was misattributed, so
the number itself has to be reproduced before the attribution is
touched.

| What | Published | Measured here |
|---|---|---|
| `docs/76` section 9.5, the two clock-gating checks at the slow corner | **−0.7495** and **−5.0198 ns** | **−0.749507** and **−5.019787**, on `hw/soc/pnr/runs/s76gate`'s own sign-off netlist and SPEF, through `hw/soc/flow/power_report.tcl`'s library and derate setup **[fact]** |
| the same two at typ and fast | `u_npu_cg` **+4.1210** and **+9.5364** | **+4.120988** and **+9.536351**; `u_bus_cg` +6.844797 and +11.374052 **[fact]** |
| `docs/76` section 9.4, the layout's own setup WNS | **−6.3505 / +3.2377 / +9.0223 ns** | **−6.3505 / 3.2377 / 9.0223** **[fact]** |
| `docs/76` section 8.3, the power of the two layouts, all twelve figures | `s76gate` 35.122 / 45.199 / 57.681 busy and 6.748 / **8.287** / 10.452 idle; `s76base` 26.585 / **33.359** / 42.148 and 15.049 / **18.745** / 23.416 | **35.122 / 45.167 / 57.611 and 6.748 / 8.287 / 10.452; 26.612 / 33.394 / 42.191 and 15.048 / 18.744 / 23.414** **[fact]** |
| `docs/76` section 7, the CTS sink census | 1,404 / 2,323 / 2,089 / 55 / 9 | **the same five, on a re-run of that document's netlist through this session's flow** **[fact]** |
| `docs/76` section 9.2, the two synthesis netlists | 45,622 cells / 5,874 flops / 685,381.4352 um2 and 45,763 / 5,871 / 691,131.9114 | **the same six figures, re-synthesised here** **[fact]** |
| `docs/76` section 7, the two gates' duty on the self-test | **25,029 (6.0261 %)** and **401,274 (96.6122 %)** | **25,029 / 6.0261 % and 401,274 / 96.6122 %** **[fact]** |
| `docs/76` section 7 / `docs/57` section 5.2, the supervisor | 43,728 / 63.2767 %, 69,081 / 99.9638 %, window 39,804 / 57.5985 %, both 39,782 / 99.9447 % | **all six, to the digit** **[fact]** |
| `docs/46` section 7.1, the supervisor's answer | `sig = 216f8ce6`, 7 kicks, `wdog_win 00000003` | **`216f8ce6`, 7 kicks, `00000003`** **[fact]** |
| `docs/68` section 8 / `docs/76` section 6.1, the whole-SoC invariants | **220,256** in the image, **415,324** for the run | **220,256 / 415,324**, 28 of 28, mask 0, `0x00030000`, 1,135, 0 **[fact]** |
| `docs/57` section 5.2, the supervisor's window split | 29,302 busy, 39,804 idle, 69,106 total | **29,302 / 39,804 / 69,106** **[fact]** |
| `docs/75` section 3 / `docs/76` section 6.4, the TMR cone census | watchdog **29/29/29**, boot **23/23/23**, NPU cause bank **25/25/25** | **the same three, on this document's netlist** **[fact]** |

**The twelve power figures reproduce to between 0.000 % and 0.12 %, and
the residual is an instrument sensitivity worth having.** This
document's annotation is taken from its own supervisor dump, which has
**3,114** register bits against `docs/76`'s 3,113 and a busy activity of
**0.071189** against 0.071212 — one flip-flop's difference, `wake_q`.
The idle figures move by at most **0.01 %** and the busy ones by up to
**0.12 %** (57.681 published against 57.611 here, at the fast corner). **That is the floor below which a power delta measured with
this annotation means nothing**, and section 9.5 needs it.

**And one instrument was EXTENDED rather than reproduced, which is
stated because a document that quietly grows a tool has not published
its method.** `hw/soc/flow/clkgate_check.py duty` now also reports the
number of **sleep intervals** behind each enable. `docs/76` section 7
quoted "774 sleep intervals" for the fabric on the supervisor and
nothing in that file could produce the figure. It is reported here as
**773 wakes** on the same dump, and the difference is the definition: a
wake is a low-to-high transition, and a run that ends with the gate shut
has one interval more than it has wakes. Section 11 is what the number
is for.

---

## 3. What actually costs the two checks

### 3.1 The instrument: cut the launch domains, one at a time

An `sg13g2_lgcp_1` declares `clock_gating_integrated_cell`, so OpenSTA
derives a full-cycle setup check on `GATE` against `CLK`'s rising edge.
The endpoint is one pin; what a slack does not say is **which of the
enable's terms brought the path**. So: partition every sequential cell
in the netlist by the clock net that reaches its `CLK` pin, then
`set_false_path -from` each domain in turn and ask for the worst
remaining path to the gate's `GATE` pin.

The partition is the netlist's and it closes on `docs/76`'s own census:

| domain | cells | what it is |
|---|---:|---|
| `u_ibex.clk` | **2,323** | the core, behind the gate `ibex_top` binds |
| `clk_i_regs` | **1,404** | everything ungated |
| `clk_npu` | **2,089** | the accelerator and the frozen die |
| `clk_bus` | **55** | the fabric |
| other | **3** | the three `sg13g2_lgcp_1` cells' own `CLK` pins |
| **total** | **5,874** | 5,871 registers, 3 gates |

**[fact, on `s76gate`'s sign-off netlist]** — the same five numbers
`docs/76` section 7 read out of `CTS-0010` and `CTS-0011`.

### 3.2 The result, and it is not the fault lines

Worst path to each gate's `GATE` pin at the **slow** corner, as launch
domains are removed:

| launches allowed | **`u_npu_cg`** | **`u_bus_cg`** |
|---|---:|---:|
| all — the sign-off number | **−5.019787** | **−0.749507** |
| everything but Ibex | **−2.616595** | **+5.515841 MET** |
| ...and not the ungated domain either | **−1.312921** | **+6.802477 MET** |
| ...and not the fabric either | −1.312921 | +6.802477 |
| ...and not the accelerator either | **no path** | **no path** |

**[fact]**

> **EVERY ONE OF THE ELEVEN — NINE — FAULT LINES LAUNCHES IN THE
> `clk_npu` DOMAIN, AND THE WORST PATH FROM THAT WHOLE DOMAIN IS
> −1.3129 ns OF THE −5.0198.** `|sticky_ev` is the OR of the queues'
> pointer votes, the entry parity, the cause bank's 25-bit majority
> voter, the strobe mismatch and the bounded waits; every one of those
> is a combinational function of registers inside `soc_npu` or inside
> the die, so every one of them starts on `clk_npu`. The cone
> `docs/76` section 9.5 named is worth **at most a quarter of the
> violation, and removing it entirely would have left −5.0198
> unchanged** — because the binding path does not pass through it.
>
> **AND THE FABRIC'S GATE HAS NOTHING IN IT AT ALL.** With Ibex's
> launches removed its check MEETS by **+5.5158 ns**. `docs/76` section
> 9.5 called that gate's miss "a buffering distance rather than a
> structural problem"; it is neither. It is the CPU.

A second reading of the same data, taken by walking the ranking rather
than cutting whole domains: the **75 worst startpoints** into the
accelerator's enable were enumerated one at a time — false-pathing each
in turn and re-asking — down to a slack of **−2.3518**, and **not one
of them is in the `clk_npu` domain**: 69 are Ibex registers and 6 are
ungated ones **[fact]**.

### 3.3 What the path actually is

`_81736_` is `u_ibex.gen_regfile_ff.register_file_i.raddr_a_i[2]`
**[fact, the netlist's own name on the flip-flop's `Q` net]**, and the
ten flip-flops that hold the next ten ranks are `raddr_a_i[0..4]` and
`raddr_b_i[0..4]` — the register file's two read-address ports. It is
also the launch of the design's worst path full stop: `_81736_ → _78585_/D`
is **−6.350531**, which is `s76gate`'s WNS **[fact]**.

The path to the accelerator's gate, stage by stage, from the sign-off
report:

| | time, ns | |
|---|---:|---|
| clock reaches `_81736_/CLK` | 2.056580 | Ibex's own tree insertion |
| `_81736_/Q` | 2.539281 | the register-file read address |
| ... 18.5 ns of the CPU's datapath ... | | an adder, a carry chain, an XOR/XNOR chain, a 32-bit mux with one buffered select |
| the last cell before the enable's own logic | **22.477057** | |
| five more gates | | `nor2b`, `nor3`, `nor2b`, `nor2b`, `nand2_1` |
| **`GATE`** | **25.139307** | |
| **required** | **20.119518** | 20 ns + 0.6718 clock − 0.25 uncertainty + 0.0687 CRPR − 0.3710 setup |

**[fact]**

> **THE LAST FIVE GATES COST 2.66 ns OF A 22.60 ns PATH, AND THE PATH
> IS ALREADY 2.36 ns LATE WHEN IT REACHES THEM.** How many of those five
> are the accelerator's enable and how many are the fabric's slave
> decode cannot be read off a netlist `abc` flattened and renamed, so
> the statement this document makes is the one that does not need the
> boundary: **the check misses by AT LEAST 2.36 ns with every gate of
> the enable deleted**, because 22.477057 is already past the required
> time of 20.119518. **Section 9.3 measures the floor rather than
> computing it**: on a layout whose enable is ONE cell, the
> CPU-derived signal arrives at 22.437502 against a required time of
> 20.071708, so the check is **2.366 ns late before that cell switches**
> and the cell itself costs another 1.845.
>
> **FOR THE FABRIC THE ARITHMETIC IS AIRTIGHT AND NEEDS NO LAYOUT.** Its
> enable is one `nand4_1` and that cell drives the `GATE` pin directly.
> Its input arrives at **21.223860** and the required time is
> **20.852640**, so **the fabric's check fails by 0.3712 ns with its
> enable's only gate contributing nothing** **[fact]**. No RTL can
> repair it.

One more number from the same report, because it is a physical finding
and not a logical one: the accelerator's last enable gate is a
`sg13g2_nand2_1` driving **0.167540 pF** with a **1.556 ns** output
transition, and it alone costs **1.336 ns** of the 2.66 **[fact]**. A
minimum-strength cell on the wire to the gate is half of what the
enable's own logic costs.

---

## 4. The tension, stated before any RTL

`docs/55-npu-connection-hardening.md` and `docs/44-margin-and-observability.md`
built a reporting path on purpose. `docs/52` section 10 had found the
defect it closes — *79 upsets absorbed by mechanisms that worked and
visible to nothing* — and the answer was three fault lines out of
`soc_npu` into `soc_busstat`'s counters (`npu_cor_ev`, `npu_det_ev`,
`npu_tmr_ev`) and nine sticky bits in a TMR-protected cause word that
software acknowledges. **A clock-gated flip-flop still holds state and
can still be upset; what it cannot do is report the upset**, because the
voter's correction, the queue's parity discard and the cause bank's own
mismatch are all recorded by registers that need a clock. `|sticky_ev`
is in the accelerator's wake condition for exactly that reason, and
`docs/76` section 3.2 is right that this is the thing gating a
fault-tolerant block gets wrong by default.

**So taking the fault lines out of the enable to buy timing margin would
trade a measured safety property for a number, and this project has
refused that exchange before.** `docs/50` section 8.1's rule is *extend,
do not relax*.

**This document does not make that trade, and section 3 is why it did
not have to**: the fault lines were never what cost the margin. What is
done to them is a change of *when the enable is computed* and not of
*what it means* — and because the enable's function is unchanged, the
distinction is checkable rather than rhetorical. Section 7 checks it:
the repaired design's `npu_clk_en` is the same waveform, cycle for
cycle, that `docs/76`'s design produced.

**Where the meaning does change is under a fault, and that is stated
here rather than buried.** If an upset raises a fault line inside a
block whose clock is stopped, `docs/76`'s design would have started the
clock at the end of that same cycle and this one starts it one cycle
later. **The upset is recorded either way** — the line is a
combinational function of registers that are not moving, so it is still
up when the clock arrives — and T2 in section 6 is the proof that one
cycle is the bound. **What is lost is one cycle of reporting latency on
a fault, and nothing else.**

---

## 5. The repair

### 5.1 The split, by arrival

`soc_npu.v`'s enable was one 28-term OR. It is now two:

```verilog
// TRANSIENT AND EXTERNAL, therefore COMBINATIONAL.
wire npu_act_fast = req_i | psel_i;

// FROZEN WHILE THE CLOCK IS STOPPED, therefore REGISTERABLE.
wire npu_act_slow =
      rvalid_o | win_out | (win_state != W_IDLE) | (win_guard != 0)
    | flush_pulse | scrub_pulse
    | (|(sticky_ev & STICKY_FROZEN))
    | ser_busy | ser_start | ser_done | ser_timeout
    | (ev_state != E_IDLE) | ev_start | aer_in_stb
    | inj_rd_en | inj_rd_valid | cap_wr_en | cap_rd_en | cap_rd_valid
    | oh_req | (oh_guard != 0) | (~inj_empty) | (~cap_empty)
    | node_busy | node_aer_out_vld | (~node_aer_in_rdy);

reg wake_q;
always @(posedge clk_free_i or negedge rst_ni)
  if (!rst_ni) wake_q <= 1'b1;
  else         wake_q <= npu_act_fast | npu_act_slow;

assign clk_en_o = npu_act_fast || wake_q || (wake_hold != HOLD_ZERO);
```

**`req_i` and `psel_i` are the fast half because they are the only two
things in the list that can rise and fall while this block's clock is
stopped.** `gnt_o` is combinational — `req_i && win_state == W_IDLE` —
so a request this block has granted and then not clocked in is a request
it has dropped. Every other term is produced inside the block or inside
the die, and the die is on the same gated clock.

**The wake bit is on the UNGATED clock and that is the whole of why it
works.** A wake bit on `clk_npu` could not start the clock it is gated
by. `soc_npu` gains one port, `clk_free_i`, `soc_top.v` hands it `clk_i`,
and **it is not a second clock domain**: `clk_npu` is `clk_i` with edges
removed by the gate, so every `clk_npu` edge is a `clk_i` edge at the
same instant and no crossing is created. OpenSTA analyses the path from
the accelerator's registers to `wake_q` as an ordinary same-clock path,
and section 9.4 shows where it lands: not on the worst path from
anywhere.

**`wake_hold` is unchanged at `HOLD_CYCLES = 4`** — `docs/76` section
5.3's margin for the frozen die's settling chains — and
`sw/tests/test_soc_clkgate_guards.py` still pins the value.

### 5.2 The ninth fault line, which the census found and nobody's reading had

`npu_act_slow` carries `sticky_ev & STICKY_FROZEN` and not `sticky_ev`,
and the one bit the mask removes is **`C_INJ_OVF`**:

```verilog
assign sticky_ev[C_INJ_OVF - C_STICKY0] = inj_wr_en && inj_full;
wire inj_wr_en = apb_wr && (paddr_i == R_EVQ_IN);
wire apb_wr    = psel_i && penable_i && pwrite_i;
```

It carries `psel_i`, so it is not a function of the block's registers,
so it is not frozen while the clock is stopped — and a registered wake
could therefore be one cycle behind it in the cycle it matters. **It can
only be true in a cycle in which `psel_i` is high, and `psel_i` is in
the fast half**, so masking it out of the slow half loses nothing and
buys the census an equality with zero instead of a list of exceptions.

**Nothing found this by reading the file.** The cone census in section
6.4 found it, on the first run, in a term `docs/55`, `docs/56` and
`docs/76` all describe as "the fault lines".

### 5.3 What is NOT changed, and why

**`soc_bus.v` is not touched.** Section 3.2 measures that its enable has
no non-Ibex path worse than **+5.5158 ns MET**, and section 3.3 that its
one gate contributes nothing to the 0.3712 ns it is late by. There is
nothing in that enable to move. **A repair to a file that measurement
says cannot help is a change to the design's risk surface for no
return**, and `docs/76`'s F10 — five terms, five mutations, k-induction
— stands unmodified and was re-run here.

---

## 6. The proof

### 6.1 What can be proved, and what `docs/76` already said cannot

`docs/76` section 10 states the limit this work inherits:

> **THE ACCELERATOR'S ENABLE IS NOT PROVED, IT IS MEASURED.** F10 is a
> theorem about `soc_bus` and about nothing else.

The reason is structural and has not changed. `soc_npu` instantiates
`hw/rtl/pilot_top.v`, which `docs/34` freezes, whose 2,152 flip-flops
are not this project's to abstract and whose property set lives in
`formal/` and may not be extended. A k-induction proof of *"no register
in `soc_npu` moves while the enable is low"* would have to quantify over
the die's state, and replacing the die with a free-input stub makes the
statement **false** rather than hard — a stub whose outputs move on
their own is a die that changes state with its clock stopped.

**So this document proves the TRANSFORMATION and discharges its side
conditions separately, and says which is which.** That is a weaker
object than F10 and a stronger one than `docs/76` had for this block,
which had only the measured equivalence.

### 6.2 The theorem

`hw/soc/formal/clkgate_wake.v` is an abstraction with three free inputs:
`fast_i` (the transient external terms), `slow_i` (the terms that are
functions of state) and `changed_i` (*the block's state moves at the
edge that ends this cycle*). It holds the wake bit exactly as
`soc_npu.v` holds it.

| | statement |
|---|---|
| **A1** *(assumed here, measured in section 7)* | `docs/76`'s enable is complete: `changed ⟹ fast \| slow` |
| **A2** *(assumed here, machine-checked in section 6.4)* | `slow` is a function of the block's state: `!changed(N−1) ⟹ slow(N) == slow(N−1)` |
| **T1** *(proved)* | the registered-wake enable is complete too: `changed ⟹ fast \| wake` |
| **T2** *(proved, and it needs NEITHER A1 nor A2)* | `slow(N−1) ⟹ en(N)` — a frozen term true in any cycle has the block clocked at the end of the next |

**T1 is what makes the substitution sound.** Everything `docs/76`
section 4.2 says about F10's transport applies to it unchanged: the
gated instance's state can differ from the ungated one's only at an edge
the gate removed, and T1 says the ungated instance's state does not
change at those edges either.

**T2 is what the fault lines are for, kept.** It uses no assumption, so
it holds in exactly the case A1 and A2 are not about: an upset raising a
line inside a block whose clock is stopped. The line is a combinational
function of registers that are not moving, so it stays up; T2 says the
clock is running one cycle later; a block that is clocked with the line
still up records it. **One cycle, bounded, not "eventually".**

### 6.3 The result, the fault task, and the mutation

| task | engine | result |
|---|---|---|
| `bmc`, depth 24 | `smtbmc yices` | **PASS** |
| `prove`, k-induction, depth 12 | `smtbmc yices` | **PASS**, *"successful proof by k-induction"*, basecase and induction |
| `cover`, depth 24 | `smtbmc yices` | **PASS, 3 of 3 reached** |
| `bmc_upset` — **A2 dropped** | `smtbmc yices` | **PASS** |
| `prove_upset` — **A2 dropped** | `smtbmc yices` | **PASS by k-induction** |
| `cover_upset` — **A2 dropped** | `smtbmc yices` | **PASS, 4 of 4 reached** |

**[fact, `hw/soc/formal/clkgate_wake_*`, under a second on this
machine]**

**The three `upset` tasks are not a weaker version of the other three;
they are the second half of the job.** An upset that flips a register
inside a block whose clock is stopped is precisely a `slow` term rising
in a cycle in which the state did not move — which is what A2 forbids.
So the tasks that drop A2 are the tasks that model the fault, **T1 is
not asserted there and T2 is**, and W4 — *a frozen term rises while the
gate is shut, with no fast term anywhere near it, and one cycle later
the clock is running* — is **reachable only there**. Under A2 it is
unreachable, and that is the formal statement of section 8's measurement
that a fault-free machine never pays the cycle.

**And A2 is load-bearing.** In a scratch copy outside the working tree,
with A2 dropped and T1 asserted anyway, `bmc` **FAILS at step 2**
**[fact]** — the counterexample is the one-cycle lag itself.

### 6.4 A2, discharged on the design by a cone census

The side condition is not left as prose.
`sw/tests/test_soc_clkgate_guards.py` elaborates `soc_npu.v` in yosys
from `Makefile.soc_npu`'s own source list, flattens it, walks the fan-in
cone of `npu_act_slow` **cut at every sequential cell**, and reports
which of the module's input ports are reachable. Three tests:

| test | result |
|---|---|
| `npu_act_slow` reaches no input port | **NONE** — 978 net bits visited **[fact]** |
| `npu_act_fast` is exactly the two transient inputs | **`{req_i, psel_i}`** **[fact]** |
| the mutation: put `C_INJ_OVF` back into the slow half | the census reaches **`paddr_i`, `penable_i`, `psel_i`, `pwrite_i`** and the guard **FAILS** **[fact]** |

**And a fourth**: `wake_q` is clocked by `clk_free_i` in `soc_npu.v` and
`soc_top.v` hands it the ungated `clk_i` while handing the block
`clk_npu`. A wake bit on the gated clock is a bit that cannot start the
clock it gates, and it would be one line's mistake.

**The per-term census is what makes the split a measurement.** Run on
each of the nine fault lines and the twenty other terms separately, the
only one that reaches an input port is `C_INJ_OVF`; `q_cor_ev`,
`q_det_ev`, `prot_mismatch`, `fetch_expire`, `ser_timeout`,
`win_expire`, `win_orphan`, `oh_expire` and `aer_stb_mm` are all clean,
and so are `inj_full`, `inj_empty`, `cap_empty`, `cap_wr_en`,
`cap_rd_en`, `inj_rd_en`, `inj_rd_valid`, `cap_rd_valid`, `ev_start`,
`aer_in_stb`, `oh_req`, `rvalid_o`, `win_out` and `ser_busy`
**[fact]**.

---

## 7. The behaviour did not change

### 7.1 Two builds from one source tree, one parameter apart

`docs/76` section 6's instrument, unchanged: `SOC_CLKGATE=0` elaborates
**no enable at all**, and `hw/soc/flow/clkgate_check.py equiv` walks two
dumps in lockstep comparing every VCD path under a scope at every rising
clock edge, by path and not by identifier.

| | result |
|---|---|
| paths under `tb_soc.dut` | 5,139 in the baseline, 5,147 in the gated build, **5,138 compared** |
| exclusions, named | `tb_soc.dut.clk_bus`, `tb_soc.dut.clk_npu`, `tb_soc.dut.npu_clk_en` — the three signals this change creates |
| cycles compared | **415,345** |
| **cycles differing** | **0** |

**[fact, `hw/soc/out/h77-g/equiv-design.txt`]**

The paths present in only one build are all the mechanism itself and are
listed by the tool: `g_noclkgate._unused_cg` in the baseline, and in the
gated build the two gate cells' `en_latch` and `test_en_i`, plus
`u_npu.g_clkgate`'s `npu_act`, `npu_act_fast`, `npu_act_slow`,
`wake_hold` and `wake_q`.

**A1 is what that measures.** The theorem in section 6.2 assumes
`docs/76`'s enable is complete; this is the evidence for it, on this
document's RTL rather than on that document's.

### 7.2 The invariants, and the log

| | HEAD, `866d38f` (`docs/76`) | this document |
|---|---|---|
| `sim_soc.sh`, the whole SoC | 220,256 cycles in the image, 415,324 for the run, 28 of 28, mask 0, `BSTAT 0x00030000`, 1,135 console characters, 0 framing errors | **the same seven** **[fact]** |
| the whole `sim.log` | — | **byte-identical apart from the output directory named in its banner** **[fact, `diff`]** |
| `fi_core.sh`'s supervisor, clean | `sig = 216f8ce6`, 7 kicks, `wdog_win 00000003` | **the same three** **[fact]** |
| the UNGATED build of this RTL | — | **220,256 / 415,324 / 28 of 28 / mask 0 / `0x00030000` / 1,135 / 0** **[fact]** |

### 7.3 And the same statement executed on the accelerator, which `docs/76` did not have

`docs/76` section 4.5 ran F10 as a cocotb test on `soc_bus` — sample the
whole of the module's state at every edge and assert it did not move in
a cycle where the enable was low — and had no equivalent for `soc_npu`.
This document adds three to `hw/soc/tb/cocotb/test_soc_npu.py`, on the
golden inference, which is the one workload in that suite that drives
the serial transport, both queues, the event engine and the LIF datapath
at once:

| test | what it is | result |
|---|---|---|
| `test_no_state_moves_in_a_cycle_the_gate_would_have_removed` | **A1, executed.** Walk the module's hierarchy once, sample every scalar register under it — the die's included — at every edge, and assert none moved in a cycle where `clk_en_o` was low | **shut on 395 of 8,514 cycles over 2,249 signals, and nothing moved in any of them** **[fact]** |
| `test_a_request_is_never_accepted_at_an_edge_the_gate_removes` | the fast half's contract: `req_i` or `psel_i` high with `clk_en_o` low would be a transaction accepted at an edge the gate removes | **0 of the cycles that carried one** **[fact]** |
| `test_a_frozen_term_has_the_clock_running_one_cycle_later` | **T2, executed**: `npu_act_slow` high in a cycle and `clk_en_o` low in the next | **0 of the cycles checked** **[fact]** |

**And they can fail, which is the point of them.** Two mutations of
`soc_npu.v`, built in a scratch copy outside the working tree:

| the enable, mutated | `test_no_state_moves...` |
|---|---|
| `npu_act_fast = req_i` — the APB face moved out of the fast half | **FAIL** |
| `npu_act_fast = psel_i` — the fabric face moved out of the fast half | **FAIL** |
| none — the file as committed | **PASS** |

**[fact]**

> **THE SECOND MUTATION IS WHY THE WATCHER IS ARMED AT RESET AND NOT
> AFTER BRING-UP.** In the first form of the test the sampler started
> after the die was configured, which meant it saw the APB face only —
> `run_stream` polls `EVQ_OUT` over APB and never touches the register
> window — and the `req_i` mutation **passed**. Moving one line to arm
> the watcher from reset brings the bring-up's fabric accesses inside
> the window, and it fails. That is `docs/76` section 4.5's finding
> restated: what a simulation catches is what its workload reaches, and
> the way to find out which is to mutate the design and look.

---

## 8. The gates still close as often, to the cycle

`clkgate_check.py duty`, on the repaired design's own enables:

| workload | cycles | **`bus_clk_en` low** | **`npu_clk_en` low** |
|---|---:|---:|---:|
| `docs/46`'s supervisor, whole run | 69,106 | **43,728, 63.2767 %** | **69,081, 99.9638 %** |
| the same, the WFI window only | 39,804 (57.5985 %) | **39,782, 99.9447 %** | **39,782, 99.9447 %** |
| `docs/51`'s whole-SoC self-test | 415,345 | 25,029, **6.0261 %** | **401,274, 96.6122 %** |

**[fact]** — **every one of these is `docs/76` section 7's number, to
the cycle and to the fourth decimal place.**

> **THE REGISTERED WAKE COSTS NO GATED CYCLES ON EITHER WORKLOAD, AND
> SECTION 6.3 IS WHY IT COULD NOT.** A slow term can only rise while the
> clock is stopped if an upset raises it, and neither workload injects
> one; on a fault-free machine every slow term rises in a cycle where a
> fast term already had the clock running, and `wake_hold`'s four cycles
> cover the tail. **The power claim of `docs/76` therefore transports
> unchanged** — this is the same enable waveform, not a similar one.

New in this document, because section 11 needs it: the number of **sleep
intervals**, which is what a wakefulness-qualified grant would cost one
cycle of each.

| | **`bus_clk_en`** | **`npu_clk_en`** |
|---|---:|---:|
| supervisor: wakes / mean interval | **773 / 56.6 cycles** | **0 / —** |
| whole-SoC self-test: wakes / mean interval | **12,153 / 2.1 cycles** | **56 / 7,165.6 cycles** |

**[fact]** — the fabric's 773 on the supervisor is `docs/76` section 7's
"774 sleep intervals" counted as wakes, and the accelerator's 0 is that
document's "changes state once in the whole run": it goes low and never
comes back.

---

## 9. The layouts, and the two checks

### 9.1 The pair, and the determinism check that comes free with it

Two LibreLane runs, `hw/soc/pnr/config-ecc.json` (the file `docs/70`,
`docs/71` and `docs/76` used), the same floorplan, PDK, tool binaries
and machine, from two netlists that differ by **one flip-flop and 498
cells**: `s77base` from `docs/76`'s own `s76-rom0-gate` netlist and
`s77gate` from this document's.

**`s77base` reproduces `s76gate` — `docs/76`'s layout — on every metric
this document reads.** Setup WNS **−6.35053 / +3.23766 / +9.02232**,
hold **+0.369957 / +0.155963 / +0.00133171**, TNS **−11,455**, **3,131**
violating endpoints, **4,573,457 um** of routed wire, **487** setup and
**53** hold repair buffers, **91** max-slew and **28** max-cap
violations, DRC **0**, and both clock-gating checks at **−0.749507** and
**−5.019787** to six decimal places **[fact]**.

> **AND IT DOES THAT THROUGH AN INTERRUPTION AND A RESUME**, which is
> worth recording because it was not planned. Both runs were killed at
> step 37 and restarted with `-F OpenROAD.DetailedRouting` on their own
> saved state. `docs/71` section 12 measured that a resumed run and an
> uninterrupted one agree at every step from 38 on, on one netlist;
> this is that result again, on a netlist `docs/71` never saw, and it is
> what licenses every comparison below. **A baseline that reproduces the
> published run to six decimal places is a baseline.**

### 9.2 The two checks, at all three corners

| check | corner | `s77base` | **`s77gate`** | delta |
|---|---|---:|---:|---:|
| **`u_bus_cg`** | **slow** | **−0.749507** | **+0.396582 MET** | **+1.146089** |
| `u_bus_cg` | typ | +6.844797 | +7.597583 | +0.752786 |
| `u_bus_cg` | fast | +11.374052 | +11.642539 | +0.268487 |
| **`u_npu_cg`** | **slow** | **−5.019787** | **−4.211051** | **+0.808736** |
| `u_npu_cg` | typ | +4.120988 | +4.745079 | +0.624091 |
| `u_npu_cg` | fast | +9.536351 | +9.782541 | +0.246190 |

**[fact, ns]**

And the design around them, because a check that moves on a layout whose
whole timing moved is not a check that was repaired:

| | `s77base` | `s77gate` |
|---|---:|---:|
| setup WNS, slow / typ / fast | −6.3505 / +3.2377 / +9.0223 | **−4.6799 / +4.3153 / +9.5579** |
| setup TNS, slow | −11,455 | **−8,267** |
| setup violating endpoints, slow | 3,131 | **3,088** |
| hold WS, slow / typ / fast | +0.3700 / +0.1560 / +0.0013 | **+0.5842 / +0.2741 / +0.0969** |
| routed wirelength, um | 4,573,457 | **4,457,105 (−2.5 %)** |
| setup / hold repair buffers | 487 / 53 | **364 / 20** |
| max slew / max cap, slow | 91 / 28 | **67 / 33** |
| detailed-routing DRC | 0 | **0** |
| die area, um2 | 4,786,290 | 4,786,290 |
| `sg13g2_lgcp_1` in the layout | 3 | 3 |

**[fact]**

> **ONE OF THE TWO CHECKS CLOSES AND THE OTHER DOES NOT, AND THE DESIGN'S
> OWN WNS MOVED 1.6706 ns ON A CHANGE CONFINED TO ONE MODULE'S ENABLE.**
> `docs/71`'s rule — a delta between two layouts of this flow is a delta
> of netlists — is why neither number may be read as a repair without
> the decomposition in 9.3. **`soc_bus.v` was not modified at all, and
> its gate is the one that closed.**

### 9.3 Which movement is the repair, and which is the netlist

A clock-gating check's slack is `required − arrival`, and the arrival
splits at one point that is unambiguous in both netlists: **the output
of the last cell whose fan-out leaves the enable's own chain.** Above
that point the signal is the CPU's; below it, every cell exists only to
compute `en_i`. In `s77base` that boundary is `_51302_`, whose output
feeds the enable's `nor3` and one cell outside it; in `s77gate` it is
`_46817_`, whose output feeds the enable's `nand3` and one cell outside
it **[fact, the two netlists at those nets]**.

| **`u_npu_cg`, slow corner** | `s77base` | `s77gate` | delta |
|---|---:|---:|---:|
| arrival at the boundary | 22.859484 | 22.437502 | **−0.421982** |
| the enable's own chain, to the `GATE` pin | **2.279823** over 4 cells | **1.845257** over 1 cell | **−0.434566** |
| data required time | 20.119518 | 20.071708 | −0.047810 |
| **slack** | **−5.019787** | **−4.211051** | **+0.808736** |

| **`u_bus_cg`, slow corner** | `s77base` | `s77gate` | delta |
|---|---:|---:|---:|
| arrival at the boundary | 21.020115 | 19.813578 | **−1.206537** |
| the enable's own chain (one `nand4_1` and a repair buffer) | 0.582031 | 0.666084 | **+0.084053** |
| data required time | 20.852640 | 20.876244 | +0.023604 |
| **slack** | **−0.749507** | **+0.396582** | **+1.146089** |

**[fact, ns]**

> **SO THE ACCELERATOR'S 0.81 ns IS ABOUT HALF THE REPAIR AND HALF THE
> NETLIST, AND THE FABRIC'S 1.15 ns IS NONE OF THE REPAIR AT ALL.**
>
> The accelerator's enable went from four cells to one and the chain got
> **0.4346 ns** faster, which is the change this document makes and the
> only part of either number it may claim. The CPU-derived signal also
> happened to arrive **0.4220 ns** earlier, which it did because the
> netlist has 498 more cells somewhere else and placed differently.
>
> **The fabric's gate closed with its enable one gate deep in both runs,
> that gate 0.0841 ns SLOWER in the repaired layout, and its input
> arriving 1.2065 ns earlier.** `soc_bus.v` is byte-identical between
> the two builds. **That check closing is a placement outcome and this
> document does not claim it**, which is exactly the trap `docs/76`
> section 8.5 named for power and which this pair sprang for timing.
>
> **AND THERE IS A COUNTER-EXAMPLE IN THE SAME PAIR THAT KEEPS THE
> ACCOUNT HONEST**, section 9.4: the branch that lost the whole fault
> cone got *worse*.

### 9.4 The domain cut, repeated on both new layouts

Section 3's instrument, run again:

| launches allowed | `s77base` `u_npu_cg` | **`s77gate` `u_npu_cg`** | `s77base` `u_bus_cg` | **`s77gate` `u_bus_cg`** |
|---|---:|---:|---:|---:|
| all | **−5.019787** | **−4.211051** | **−0.749507** | **+0.396582** |
| not Ibex | −2.616595 | **−1.576257** | +5.515841 | +4.279988 |
| ...nor the ungated domain | −1.312921 | −1.576257 | +6.802477 | +4.279988 |
| ...nor the accelerator | no path | no path | no path | no path |

**[fact]**

Three readings, and the second is the awkward one.

**THE DIAGNOSIS REPRODUCES.** `s77base`'s three numbers are `s76gate`'s
to six decimal places, on a second layout of the same netlist: Ibex
−5.0198, the ungated domain −2.6166, the accelerator's own −1.3129. The
finding of section 3 is not one run's.

**THE ACCELERATOR-DOMAIN BRANCH GOT WORSE, −1.3129 TO −1.5763, ON THE
CHANGE THAT TOOK THE FAULT CONE OFF IT.** What is left of that branch is
the `wake_hold` comparison — three flip-flops on `clk_npu` through one
`nor2` and one `and2` into the `nand3` — where before it was the nine
fault lines through four. **Shallower logic, 0.26 ns worse slack**, and
the only thing that can account for it is where the cells landed. It is
reported because it is the same kind of evidence as the fabric's gate
closing and it points the other way.

**AND THE UNGATED BRANCH IS NO LONGER VISIBLE**, because `wake_q` — the
one flip-flop this document adds, on `clk_i_regs` — reaches the `GATE`
pin through the same single `nand3` and is not the worst path from
anywhere. The register that carries the whole frozen half of the enable
costs the check nothing.

### 9.5 Power, and `docs/76`'s busy-window question, settled

One annotation serves both layouts and that is what makes this pair a
cleaner comparison than `docs/76`'s: **both netlists have three
integrated clock gates**, so the activity file is the same file, and
`docs/76` section 8.1's warning about tying `PWR_GATES` to
`PWR_EXCL_NPU` does not arise. The activity is this document's
supervisor dump, section 2's instrument.

| | window | **slow** | **typ** | **fast** |
|---|---|---:|---:|---:|
| `s77base` = `docs/76`'s design | **computing** | 35.122 | **45.167** | 57.611 |
| `s77base` | **waiting** | 6.748 | **8.287** | 10.452 |
| **`s77gate`** | **computing** | 17.695 | **22.142** | 28.163 |
| **`s77gate`** | **waiting** | 6.768 | **8.315** | 10.489 |

**[fact, mW]**

> **THE IDLE FIGURE IS STABLE TO 0.34 % ACROSS THE PAIR AND THE BUSY ONE
> HALVES.** 8.287 against 8.315 mW at typ, and 45.167 against 22.142 —
> a factor of **2.04**, on two netlists one flip-flop apart that both
> carry the same three gates.
>
> **THAT SETTLES `docs/76` SECTION 8.5.** That document measured busy
> power RISING 33.359 → 45.199 mW when the two gates were added, found
> the whole delta in the Combinational group's `repair_design` cells,
> and refused to attribute it because one pair of runs cannot separate a
> placement effect from the gates. **This is the second pair, and the
> gate count is held fixed.** The Combinational group at typ, busy:
>
> | | gates | Combinational, busy, typ |
> |---|---:|---:|
> | `s76base` | 1 | **6.243 mW** |
> | `s77base` = `s76gate` | 3 | **24.504 mW** |
> | **`s77gate`** | **3** | **3.778 mW** |
>
> **[fact]** — 20.73 mW of the 23.03 mW difference between the two
> three-gate netlists is in that one group, and it is the group
> `docs/76` section 8.5 item 3 already localised. **A design whose
> Combinational busy power ranges over 3.8 to 24.5 mW across three
> netlists that carry one gate, three gates and three gates is a design
> whose busy power the gates do not order.** `docs/76`'s +11.840 mW is
> inside that range and is now withdrawn as a measurement of anything
> the gates did; this document's −23.025 mW is withdrawn on the same
> grounds and for the same reason. **What survives, on a third layout,
> is the idle figure and its mechanism.**

And `docs/76` section 14 item 7 — the whole-SoC program's activity, the
one this corpus has never had — is cheap once the layouts exist, so it
was taken. `docs/51`'s self-test, 415,345 cycles, split by the
accelerator's own enable:

| window | cycles | `s77base`, typ | `s77gate`, typ |
|---|---:|---:|---:|
| the whole run | 415,345 | 45.175 | 21.538 |
| **`npu_clk_en = 1`** | **14,071** | **51.900** | **27.994** |
| `npu_clk_en = 0` | 401,274 | 44.882 | 21.309 |

**[fact, mW]**

> **THE ACCELERATOR RUNNING COSTS +7.018 mW ON ONE LAYOUT AND +6.685 ON
> THE OTHER — 5 % apart, on two layouts whose totals differ by a factor
> of two.** That is the number `docs/76` item 7 asked for and it is the
> only one in this section that is stable across the netlist: **the
> incremental cost of clocking the accelerator is a property of the
> accelerator, and the absolute totals are properties of a placement.**
>
> **NO PER-INFERENCE ENERGY IS PUBLISHED**, and `docs/57` section 10.3's
> reason is unchanged: this is `report_power` on a Liberty model with a
> zero-delay dump behind it, and `docs/76` section 8.7's table still
> binds. What may be said outside the repository is what that table
> says, with one row now stronger — **the idle figure and its 2.26x are
> reproduced on a third layout** — and one row weaker: the busy figures
> are not comparable between layouts at all.

---

## 10. And a third comparison, which is the one that says the enable did not change

`docs/76`'s own gated dump is still in the working tree, so the repaired
design can be walked against **the design it repairs** rather than only
against an ungated control — and with **no exclusions at all**:

| comparison | scope | paths | cycles | **paths that ever differ** |
|---|---|---:|---:|---|
| the repaired build against `docs/76`'s gated build | `tb_soc.dut` | **5,146 compared** | **415,345** | **NONE. 0 cycles differing.** |

**[fact, `hw/soc/out/h77-g/equiv-vs-76.txt`]**

The four paths that exist in only one build are `u_npu._unused_free` —
the tie-off for the new clock port at `CLKGATE = 0` — and
`g_clkgate`'s `npu_act_fast`, `npu_act_slow` and `wake_q`.

> **`npu_clk_en` IS NOT AMONG THE DIFFERENCES, AND IT WAS NOT
> EXCLUDED.** The gated clock net `clk_npu`, the enable `npu_clk_en`,
> the combined `npu_act` and the `wake_hold` counter are all compared
> and all identical at every one of 415,345 clock edges. **The repair
> changes WHEN the enable is computed and not WHAT it computes**, and
> that is a measurement over 5,146 signals rather than a claim about a
> Boolean identity.
>
> It is also the reason section 8's duty figures are `docs/76`'s to the
> cycle, and the reason the power argument of that document transports
> without being re-run against a different waveform.

The identity itself is short, and the netlist shows the mapper found it.
`docs/76`'s enable is `npu_act || (wake_hold != 0)`; this one is
`npu_act_fast || wake_q || (wake_hold != 0)`. `wake_q` is the previous
cycle's `npu_act`, and `wake_hold` reloads to 4 on every cycle in which
`npu_act` is true — so in any cycle where `wake_q` is set, `wake_hold`
is non-zero as well and the old enable was already high. In the other
direction, `npu_act` true with `npu_act_fast` false means a frozen term
is true, and a frozen term can only have risen in a cycle where the
block was clocked, which needed the enable, which set `wake_q`. **The
two are the same function of the design's history in every fault-free
state, and differ only under an upset — which is exactly what section
6.3's `upset` tasks are about.** The argument is written out because it
is short; **what it rests on is the walk above and not the other way
round.**

In the synthesised netlists the two enables are different shapes, and
this is a fact about the netlists rather than about a placement.
`docs/76`'s is a four-cell chain — `nor3` → `nor2b` → `nor2b` →
`nand2_1` — fed by a shared `nor2b` that also drives something outside
it, so **the CPU-derived branch enters four cells from the `GATE`
pin**. This document's is `nand3(wake_q, fast, wake_hold == 0)`, fed by
a shared `a21oi` that also drives something outside it, so **the
CPU-derived term enters at the last cell**, with `wake_q` and the hold
comparison as its two other inputs **[fact, the two
`soc_top.netlist.v` files traced back from the net
`g_clkgate.u_npu_cg.en_i`, with each cell's fan-out counted to find
where the enable's own chain begins]**. That is the change section 9.3
measures on the die.

---

## 11. What would close the checks, what it costs, and why it is not taken

Section 3 says the checks cannot be closed by restructuring either
enable. What is left is to take the CPU-derived term out of the
combinational enable altogether, and there is exactly one way to do that
without losing a transaction: **the slave refuses to accept one in a
cycle it is not clocked.**

```
gnt_o    = req_i && awake && (win_state == W_IDLE)   // was: req_i && ...
pready_o = awake                                      // was: 1'b1
clk_en_o = wake_q || (wake_hold != 0)                 // no combinational
                                                      // CPU term at all
```

Both fabrics support it. `soc_bus.v`'s `target_ready` is `s_gnt_i[tgt]`
and a master's grant waits on it; `soc_apb_bridge.v` waits on
`pready_i`. So a slave that says "not yet" for one cycle is a slave the
fabric already knows how to wait for, and the enable's only late input
becomes a flip-flop `D` pin — **an ordinary setup path, and one whose
failure mode is a wake that arrives a cycle later rather than a glitch
on a clock net.**

**The price is one cycle per sleep interval, and it is measured rather
than estimated** (section 8):

| | sleep intervals | cost, whole-SoC self-test (415,324 cycles) | cost, supervisor (69,106) |
|---|---:|---:|---:|
| **the accelerator** | **56** | **56 cycles, 0.013 %** | **0 cycles** |
| **the fabric** | **12,153** | **12,153 cycles, 2.93 %** | **773 cycles, 1.12 %** |

**[fact for the interval counts; estimate for the cycle costs, one
measured count against one measured run length]**

> **THE TWO ARE PRICED TWO ORDERS OF MAGNITUDE APART AND SHOULD NOT BE
> DECIDED TOGETHER.** The accelerator sleeps in 56 long intervals of a
> mean 7,166 cycles; the fabric sleeps in 12,153 intervals of a mean
> 2.1. A wakefulness-qualified grant on the accelerator costs 0.013 % of
> a program that performs an inference. On the fabric it is a permanent
> CPI tax on every access after every idle gap, in the one block every
> access in the SoC passes through.

**Neither is taken here, and the reason is a judgement rather than a
measurement, so it is stated as one.** These endpoints are among the
**3,088** the slow corner still fails on in the repaired layout, in a
design whose CPU consumes **22.4 ns of a 20 ns period** at that corner
and whose WNS is **−4.6799 ns** launched from the same register-file
read address. **Buying them back with a permanent change to the SoC's
bus handshake — one that changes the cycle count of every program and
therefore every invariant this corpus quotes — is paying in silicon for
a check at a corner the part does not meet for reasons the gates have
nothing to do with.** `docs/76`'s own framing is the right one and it
survives the correction: a violated setup check at a clock gate is a
possible glitch on a clock net rather than a wrong data bit, and this
project still has no instrument for the width of such a glitch
(`docs/75` section 14 item 1).

**And section 9.3 sharpens the judgement rather than softening it.** The
fabric's check meets on this layout by **+0.3966 ns** without one line
of `soc_bus.v` changing, on a placement that also handed the whole
design 1.6706 ns. A repair that costs 12,153 cycles of CPI to buy
1.15 ns, in a design where the netlist gives and takes that much on its
own, is a bad trade twice over. **The accelerator's half is different
and section 17 ranks it**: 56 cycles, a floor of −2.4 ns that no enable
can beat, and a check that would then close by construction rather than
by placement.

---

## 12. Cost

### 12.1 Synthesis

`syn_soc_top.sh 20`, `SOC_MEM=sram SOC_ROM_HARDEN=0`, the flow's own
`abc -D 20` and `abc.constr`:

| netlist | cells | flip-flops | area um2 |
|---|---:|---:|---:|
| `s76-rom0-base`, CLKGATE = 0 | 45,622 | 5,874 | 685,381.4352 |
| `s76-rom0-gate`, `docs/76`'s design | 45,763 | **5,871** | 691,131.9114 |
| **`s77-rom0-gate`, this document's** | **46,261** | **5,872** | **691,961.3568** |

**[fact; the first two reproduce `docs/76` section 9.2 exactly]**

**+1 flip-flop, +498 cells, +829.4454 um2 — 0.12 % of the design.** The
flip-flop is `wake_q`. The 498 cells are not the enable, which got
*smaller* — one `nand3` where there were five gates — and this document
does not root-cause them further than `docs/76` section 9.2 did its own
five: the enable's fan-out changed, the mapper responded, and the
evidence that it is not a design change is section 10's 5,146 paths at
415,345 edges with zero differences.

### 12.2 Where the flip-flop lands

`CTS-0010` and `CTS-0011` on the two layouts of this session:

| clock net | `s77base` (`docs/76`'s netlist) | **`s77gate`** |
|---|---:|---:|
| `clk_i`, six macros and three gate `CLK` pins | 9 | 9 |
| **`clk_i_regs`, ungated** | **1,404** | **1,405** |
| `u_ibex.clk` | 2,323 | 2,323 |
| `clk_npu` | 2,089 | 2,089 |
| `clk_bus` | 55 | 55 |
| **total** | **5,880** | **5,881** |

**[fact]**

**The `s77base` column is `docs/76` section 7's census, reproduced by a
fresh run of that document's netlist through this session's flow** —
which is `docs/71`'s determinism, re-checked on a netlist that document
never saw. **And the one flip-flop this change adds is on the UNGATED
net, which is the only net it could do its job from.** Nothing moved
between the gated domains.

### 12.3 The hardening census is intact

`gl_netlist.py --tmr-census` by fan-in cone, on this document's netlist:

| structure | published | measured |
|---|---|---|
| watchdog `u_prot_a/b/c` | 29/29/29 | **29/29/29** |
| boot `u_prot_a/b/c` | 23/23/23 | **23/23/23** |
| NPU cause bank `u_cfg_a/b/c` | 25/25/25 | **25/25/25** |

**[fact]**

---

## 13. Files touched, and the suites

| file | change |
|---|---|
| `docs/77-the-clock-gate-enables-and-what-actually-costs-them.md` | this document |
| `docs/00-index.md` | one row |
| `docs/76-the-second-and-third-clock-gates.md` | a dated note on section 14, pointing at section 14 of this document. **No number in that document is edited**; section 14 below is where its two are corrected |
| `hw/soc/rtl/soc_npu.v` | `clk_free_i`; the `npu_act_fast` / `npu_act_slow` split; `wake_q`; `STICKY_FROZEN` and the paragraph naming `C_INJ_OVF`; the section that states the split is by arrival and what the census discharges; the corrected sticky-line count |
| `hw/soc/rtl/soc_top.v` | `.clk_free_i(clk_i)` on `u_npu`, with the reason |
| `hw/soc/formal/clkgate_wake.v` | new: the transformation, as an abstraction, with its header stating what cannot be proved and why |
| `hw/soc/formal/clkgate_wake_props.v` | new: A1, A2, T1, T2 and the four covers |
| `hw/soc/formal/clkgate_wake.sby` | new: six tasks in two groups, `sound` and `upset` |
| `hw/soc/formal/Makefile` | the `clkwake` target, in `all` |
| `hw/soc/flow/clkgate_check.py` | `duty` also reports sleep intervals and their mean length, which section 11 prices |
| `hw/soc/tb/cocotb/test_soc_npu.py` | the second `Clock` on `clk_free_i`, since `soc_npu` is the toplevel there and the two clocks are one net in `soc_top.v`; and the three tests of section 7.3 |
| `sw/tests/test_soc_clkgate_guards.py` | the fan-in cone census (three tests and its mutation), the wake-bit wiring guard, and `s77*gate` added to the netlist glob |
| `.gitignore` | the new formal job's six task directories, by the same rule as the other fourteen |

**No file under `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/`
was written** **[fact, `git status`]**.

Build products, all gitignored:

| directory | what is in it |
|---|---|
| `hw/soc/out/s77-rom0-gate` | the synthesis this document's layout was made from |
| `hw/soc/pnr/runs/s77base`, `s77gate` | the two layouts, beside `docs/76`'s own in the same tree |
| `hw/soc/out/h77-g`, `h77-b` | the whole-SoC pair, one source tree one parameter apart, with `equiv-design.txt` and `equiv-vs-76.txt` |
| `hw/soc/out/h77-sup-r0` | the supervisor at the layout's `ROM_HARDEN = 0`, which the power annotation is taken from |
| `hw/soc/out/pwr77-sup`, `pwr77-self` | the activity JSON and the five annotation scripts |
| `hw/soc/out/pwr77-s77base`, `pwr77-s77gate` | the `report_power` outputs on this document's two layouts, six each |
| `hw/soc/out/pwr77-s76base`, `pwr77-s76gate` | the same six on `docs/76`'s two layouts, which is section 2's reproduction |
| `hw/soc/out/pwr77self-s77base`, `pwr77self-s77gate` | the self-test's three windows at three corners, `docs/76` item 7 |
| `hw/soc/out/s77-pnr-base.log`, `s77-pnr-gate.log`, `s77-syn-gate.log` | the flow logs |

### 13.1 The suites, re-run

| suite | result | what it was |
|---|---|---|
| `.venv/bin/python -m pytest sw/tests -q` | **490 passed, 0 failed** — 4 m 05 s | `docs/76` reports **484**. The six added are the cone census's three, the wake-bit wiring guard, one more parametrisation of the three-gate netlist census, and the one `test_doc_links.py` discovers for this document |
| `scripts/run_cocotb.sh` | **401 passed, 0 failed, 0 suites not clean** | `docs/76` reports **398**; `soc_npu` goes from 31 tests to 34 |
| `cd hw/soc/formal && make` | **15 jobs, 64 tasks, 64 PASS, 0 FAIL** | `docs/76` reports **14 jobs, 58 tasks**. The six added are `clkgate_wake`'s |

**[fact]**

---

## 14. Corrections to earlier documents

1. **`docs/76` section 9.5's attribution of the accelerator's
   clock-gating check to `|sticky_ev`, and section 14 item 1's repair
   built on it, are both wrong.** The cone that costs the check is the
   CPU's register-file read address through the ALU, the load-store
   address, the fabric's address mux and the slave decode; the fault
   lines are worth **at most −1.3129 ns of the −5.0198**, and removing
   them from the enable entirely leaves the number where it was. Section
   3. **The two slack figures themselves are correct and were
   reproduced to six decimal places before the attribution was
   touched.**
2. **`docs/76` section 9.5's reading of the fabric's gate — "a
   buffering distance rather than a structural problem" — is also
   wrong, and in the other direction.** It is not a buffering distance:
   with Ibex's launches removed the check MEETS by **+5.5158 ns**, and
   with them allowed the enable's single `nand4_1` receives its input
   **0.3712 ns after the check's required time**. Nothing in that
   enable can be moved to repair it. Section 3.3.
3. **`|sticky_ev` is NINE cause lines and not eleven.** `docs/76` says
   eleven in three places (sections 1, 3.2 and 9.5) and
   `hw/soc/rtl/soc_npu.v`'s own header said it too. `NSTICKY` is
   `NCAUSE - C_STICKY0 = 14 - 5 = 9`, and there are nine
   `assign sticky_ev[...]` lines in the file. Corrected in the RTL by
   this document. No published measurement depends on the count.
4. **`docs/76` section 5.1's "`sw/tests/test_soc_clkgate_guards.py`
   fails if either becomes so [registered]" was true of one of the two.**
   The guard `test_the_fabric_enable_is_purely_combinational` reads
   `soc_bus.v` only; nothing in that file constrained `soc_npu.v`'s
   enable. It is still true of the fabric and it is still enforced. What
   now constrains the accelerator's is a different and stronger thing —
   the cone census of section 6.4 — because "not registered" is not what
   that enable needs to be. Section 5.
5. **`docs/76` section 1's "Wake latency is zero cycles by
   construction" needs one qualification.** It is zero for `req_i` and
   `psel_i`, which is what the sentence was about — a slave answering a
   request in the cycle it arrives. It is **one cycle for a term that
   rises while the clock is stopped**, which can only happen under an
   upset, and T2 in section 6.2 is the bound. Sections 4 and 6.
6. **`docs/76` section 7's "774 sleep intervals" could not be produced
   by the file it was attributed to.** `hw/soc/flow/clkgate_check.py`
   had no interval counter. It has one now, and on the same dump it
   reports **773 wakes** with a mean interval of 56.6 cycles — the
   difference being that a run ending with the gate shut has one
   interval more than it has wakes. Section 8.
7. **`docs/76` section 14 item 1's shape is built, and its content is
   not.** That item asked for one flip-flop in the ungated domain "set
   by `|sticky_ev` and cleared when the accelerator has been clocked".
   What is built is one flip-flop in the ungated domain set by the whole
   frozen half of the enable and cleared by quiescence — because the
   census found that the fault lines are not the terms that needed
   moving, and because a bit cleared by "has been clocked" is a bit that
   cannot hold the clock on for the block's own work. Section 5.

---

## 15. What this does NOT cover

- **THE ACCELERATOR'S CHECK DOES NOT CLOSE, AND THE FABRIC'S CLOSES FOR
  A REASON THIS DOCUMENT DOES NOT CLAIM.** Section 9.3 decomposes both.
  **The design fails 3,088 setup endpoints at the slow corner in the
  repaired layout and 3,131 in the baseline**, and one of these two is
  among them; what this document changes is which part of that the
  enable is responsible for, and section 11 is the priced option that
  would close the rest and was not taken.
- **A SECOND LAYOUT PAIR WOULD BE NEEDED TO CALL THE FABRIC'S GATE
  CLOSED.** It meets by **+0.3966 ns** on this netlist, on a placement
  that also gave the whole design 1.6706 ns of WNS; nothing here says it
  would meet on the next netlist, and `docs/71`'s rule is why. **A check
  that closes because of where the cells landed is not a check that was
  repaired**, and the RTL that would repair it is the one section 11
  prices and refuses.
- **THE ACCELERATOR'S ENABLE IS STILL NOT PROVED COMPLETE, AND
  `docs/76` SECTION 10 ALREADY SAID WHY.** What is proved here is the
  TRANSFORMATION — that a complete enable stays complete when its frozen
  half is registered — from two side conditions, one of which (A1) is
  the measured equivalence and not a theorem. **A program that drives
  the die into a state neither workload reaches is not covered**, and
  `wake_hold` is still the margin that exists because of it.
- **NO FAULT IS INJECTED ANYWHERE IN THIS DOCUMENT.** T2 says a frozen
  term true in cycle N has the block clocked at the end of N+1; nothing
  here raises one in silicon or in a gate-level model and watches it be
  recorded. **`docs/76` section 14 item 2 asked for exactly that
  campaign and it is still unbuilt**, and it is the one experiment that
  could falsify the argument in section 4.
- **THE COMBINATIONAL COFACTOR IS CHECKED, THE TEMPORAL ONE IS
  ARGUED.** The census proves `npu_act_slow` is a function of registers
  and of nothing else. That those registers cannot change while the
  clock is stopped is true of every synchronous design and is not
  separately checked here — in particular the die's `node_busy`,
  `node_aer_out_vld` and `node_aer_in_rdy` are taken to be functions of
  `pilot_top`'s own registers because it is a synchronous block on the
  same gated clock, which is read from its source and not proved.
- **NO SILICON AND NO SIGN-OFF POWER ANALYSIS**, `docs/57` section 13's
  list unchanged; no glitch power, no IR drop, no package.
- **NEITHER LAYOUT IS SIGNED OFF.** Both fail setup at the slow corner
  and max slew and max cap, and neither has been through Magic DRC,
  KLayout DRC or Netgen LVS, because the one available SRAM macro fails
  all three inside the vendor views (`docs/12` sections 7.5 and 8,
  `docs/54`).
- **ONE GEOMETRY, ONE CONFIGURATION, ONE CLOCK PERIOD**, and the two
  layouts ran CONCURRENTLY on the same 20 threads with two sibling
  projects on the machine — which affects nothing in the result
  (`docs/71`) and everything in the wall times.
- **THE DIAGNOSIS IS ONE LAYOUT'S.** Section 3's domain cut is measured
  on `s76gate`, and `docs/71`'s rule says a delta between two layouts of
  this flow is a delta of netlists. What makes the diagnosis a
  structural statement rather than one placement's is that it is
  reproduced on `s77base` and `s77gate` in section 9 — three layouts,
  the same launch flop, the same ordering of the domains.
- **NO SCAN, NO DFT, NO TEST MODE.** Both gates take `test_en_i(1'b0)`.

---

## 16. Reproducing this

The toolchain is the repository's, resolved through `tools.mk`; `VVP` is
`$HOME/Downloads/oss-cad-suite-linux-x64-20260804/oss-cad-suite/bin/vvp`
and `STA` is `$HOME/.local/opt/llbin/sta`.

```bash
# 0. the diagnosis, on docs/76's own signed-off run. The script reads
#    hw/soc/flow/power_report.tcl's library, SPEF and derate setup and
#    then asks for the worst path to each gate's GATE pin as launch
#    domains are removed with set_false_path.
#    -0.749507 and -5.019787 at the slow corner; then -2.616595 and
#    -1.312921 for the accelerator as Ibex and the ungated domain go.
#    The two probe scripts are about twenty lines of OpenSTA Tcl each,
#    run through the interpreter power_soc_top.sh uses and with
#    power_report.tcl's library, SPEF, SDC and 0.95/1.05 derate setup
#    copied verbatim. The first is `find_timing_paths -to <GATE pin>`
#    and prints slack and startpoint; the second partitions every
#    sequential cell by the clock net on its CLK pin, then applies
#    `set_false_path -from` one partition at a time and re-asks.
#    Neither writes anything and nothing in the repository depends on
#    them, which is why they are described here rather than committed.

# 1. the formal job, and the mutation that shows A2 is load-bearing
cd hw/soc/formal && make clkwake && cd -
#   bmc PASS, prove PASS by k-induction, cover 3 of 3
#   bmc_upset PASS, prove_upset PASS by k-induction, cover_upset 4 of 4
#   the mutation is clkgate_wake_props.v with T1's `ifndef NO_A2 removed,
#   built in a scratch directory: bmc FAILS at step 2.

# 2. the cone census, which is A2 discharged on the design
.venv/bin/python -m pytest sw/tests/test_soc_clkgate_guards.py -q
#   16 passed; the census tests take under a second each

# 3. the two whole-SoC builds, one source tree, one parameter apart
SOC_VVP_ARGS=+vcd hw/soc/flow/sim_soc.sh $PWD/hw/soc/out/h77-g
mv tb_soc.vcd hw/soc/out/h77-g/
SOC_CLKGATE=0 SOC_VVP_ARGS=+vcd hw/soc/flow/sim_soc.sh $PWD/hw/soc/out/h77-b
mv tb_soc.vcd hw/soc/out/h77-b/
#   220,256 / 415,324 / 28 of 28 / mask 0 / 0x00030000 / 1,135 / 0, both

# 4. every signal, at every edge  (about 20 min on 2.7 GB x 2)
python3 hw/soc/flow/clkgate_check.py equiv \
    hw/soc/out/h77-b/tb_soc.vcd hw/soc/out/h77-g/tb_soc.vcd \
    --clock tb_soc.dut.clk_i --scope tb_soc.dut \
    --exclude tb_soc.dut.clk_bus --exclude tb_soc.dut.clk_npu \
    --exclude tb_soc.dut.npu_clk_en
#   5,138 compared, 415,345 cycles, 0 differing

# 5. and against docs/76's own dump, with NO exclusions
python3 hw/soc/flow/clkgate_check.py equiv \
    hw/soc/out/h76-g2/tb_soc.vcd hw/soc/out/h77-g/tb_soc.vcd \
    --clock tb_soc.dut.clk_i --scope tb_soc.dut
#   5,146 compared, 415,345 cycles, 0 differing

# 6. duty, and the sleep intervals section 11 prices
python3 hw/soc/flow/clkgate_check.py duty hw/soc/out/h77-g/tb_soc.vcd \
    --clock tb_soc.dut.clk_i \
    --enable tb_soc.dut.bus_clk_en --enable tb_soc.dut.npu_clk_en

# 7. the supervisor, at the layout's configuration, for the power
FI_WORKLOAD=supervisor SOC_ROM_HARDEN=0 \
    hw/soc/flow/fi_core.sh $PWD/hw/soc/out/h77-sup-r0
(cd hw/soc/out/h77-sup-r0 && $VVP -n tb_soc_fi.vvp +armed=0 +vcd)
#   sig = 216f8ce6, 7 kicks, wdog_win 00000003
hw/soc/flow/power_soc_top.sh extract \
    hw/soc/out/h77-sup-r0/tb_soc_fi.vcd tb_soc_fi hw/soc/out/pwr77-sup
#   all 69,106 / busy 29,302 / idle 39,804
for w in busy idle; do
  hw/soc/flow/power_soc_top.sh annotate hw/soc/out/pwr77-sup $w tb_soc_fi
done

# 8. the synthesis, and the two layouts
SOC_MEM=sram SOC_ROM_HARDEN=0 \
    hw/soc/flow/syn_soc_top.sh 20 $PWD/hw/soc/out/s77-rom0-gate
#   46,261 cells, 5,872 flops, 691,961.3568 um2, 3 sg13g2_lgcp_1
for t in base:s76-rom0-gate gate:s77-rom0-gate; do
  tag=${t%%:*}; nl=${t##*:}
  SYN_NETLIST=$PWD/hw/soc/out/$nl/soc_top.netlist.v \
  PNR_CONFIG=$PWD/hw/soc/pnr/config-ecc.json \
  PNR_STATE=$PWD/hw/soc/pnr/state/s77$tag.state.json \
  hw/soc/flow/pnr_soc_top.sh s77$tag --overwrite -F Yosys.JsonHeader \
      -S Yosys.Synthesis -S Checker.YosysUnmappedCells \
      -S Checker.YosysSynthChecks -S Checker.NetlistAssignStatements \
      -i $PWD/hw/soc/pnr/state/s77$tag.state.json
done
grep -hE "CTS-001[01]" hw/soc/pnr/runs/s77{base,gate}/2*-openroad-cts/*.log
#   Both runs were interrupted at step 37 in this session and resumed on
#   their own saved state with
#       hw/soc/flow/pnr_soc_top.sh s77<tag> -F OpenROAD.DetailedRouting
#   which is docs/71 section 12's form. It is recorded because it
#   happened, and section 9.1 is the evidence that it cost nothing: the
#   baseline reproduces docs/76's layout on every metric.

# 9. the power, on the two layouts, three corners each. ONE annotation
#    serves both, because both netlists have three gates -- which is
#    what makes this pair a cleaner comparison than docs/76's.
for t in base gate; do
  for w in busy idle; do
    PWR_RUN=$PWD/hw/soc/pnr/runs/s77$t \
      hw/soc/flow/power_soc_top.sh report hw/soc/out/pwr77-$t $w
  done
done

# 10. the censuses and the suites
python3 hw/soc/fi/gl_netlist.py \
    hw/soc/out/s77-rom0-gate/soc_top.netlist.v --tmr-census npu
.venv/bin/python -m pytest sw/tests -q     # 489 passed
scripts/run_cocotb.sh                      # 398 passed, 0 not clean
cd hw/soc/formal && make                   # 15 jobs, 64 tasks, 64 PASS
```

**Cost, quoted with the configuration it was measured in**, on a shared
20-thread host running **two place-and-route flows, a formal gate, a
cocotb suite and an activity extraction concurrently for most of the
session**, with two sibling projects on the machine throughout. **[fact
for the figures; the wall times are costs and not benchmarks]**

| | |
|---|---:|
| `clkgate_wake`, all six tasks | **under 1 s each** |
| the cone census, three tests | **0.85 s each** |
| one whole-SoC run with `+vcd` | about **5 min**, **2.7 GB** |
| `clkgate_check.py equiv`, 5,146 paths over 2.7 GB x 2 | about **20 min** |
| `clkgate_check.py duty`, one 2.7 GB dump | about **3 min** |
| the supervisor with `+vcd` | about **2 min**, **212 MB** |
| the `soc_npu` cocotb suite, 34 tests | **2 m 13 s**, of which the state walk over 2,249 signals is 1 m 50 s |
| **the two layouts**, 62 and 64 timed steps | run CONCURRENTLY on the same 20 threads, so neither is a benchmark of anything |
| `vcd_activity.py` on the supervisor's dump | about **1 min** |
| one `syn_soc_top.sh` | about **2 min** |
| `pytest sw/tests` | **4 m 05 s** |
| the whole formal set, 15 jobs | about **9 min** |

---

## 17. What the next block should be

1. **The accelerator's wakefulness-qualified grant, measured.** Section
   11 prices it at **56 cycles of 415,324** — 0.013 % — and it is the
   only change that could make that gate's check close BY CONSTRUCTION,
   because section 9.3 says the enable's own chain is already one cell
   and section 3 says the rest of the path is the CPU's. It is one line in `gnt_o`, one
   in `pready_o`, and the removal of `npu_act_fast` from the enable;
   what it costs the corpus is that **415,324 stops being the
   invariant**, and what it would buy is the first clock-gating check in
   this design that closes at the slow corner. **Build it behind a
   parameter, lay it out beside this document's `s77gate`, and report
   whether the check closes** — and then decide, with the number in
   hand, whether a slave that answers a cycle late is worth it.
   **Do not do the same for the fabric** until that question is
   answered: 12,153 intervals is a different kind of price.
   **BUILT 2026-09-15, behind `soc_npu.v`'s `WAKE_GNT`, default 0 -- see
   section 18**, which has the default-unchanged evidence, the corner
   results, the formal result, the measured cost against the 56
   predicted here, and the recommendation. The layout beside `s77gate`
   is what section 18 does NOT have, and it says why.
2. **A gate-level fault-injection campaign into the gated domains.**
   `docs/76` section 14 item 2, unchanged and now sharper: T2 says a
   frozen fault line true in cycle N has the block clocked at the end of
   N+1, and **nothing in either document raises one**. `docs/74`'s and
   `docs/75`'s machinery already runs on a LibreLane netlist; the arms
   are this document's two layouts, and the question is whether the
   detected-fault rate moves. It is the one experiment that could
   falsify section 4.
3. **The `nand2_1` on the enable's wire.** Section 3.3 measures the last
   gate of `docs/76`'s enable driving 0.167540 pF with a 1.556 ns
   transition and costing 1.336 ns — a minimum-strength cell on a long
   wire to the gate, which is a max-slew violation the resizer did not
   take. Whether that is the placer's or the resizer's, and whether a
   `set_dont_touch` or a driving-cell constraint on the two enable nets
   moves it, is one experiment on a saved state and costs no RTL.
   `docs/72`'s instrumentation is the shape of it.
4. **`SCRUB_IVL_RST` against idle power.** `docs/76` section 14 item 3,
   untouched: the RAM scrubber is **16.46 %** of idle switching, the
   interval is a reset parameter, and the trade is scrub rate against
   idle current. One sweep, no RTL change.
5. **The CLINT's `TICK_DIV` as a prescaler**, `docs/76` section 14 item
   4, untouched.
6. **The fourth gate: `u_apb` and `u_pnp`**, `docs/76` section 14 item
   5 — and with this document's split in hand the shape is clearer:
   both blocks' enables would be `req_i | psel_i` fast and their own
   state slow, and `soc_apb_bridge` already carries a property set an
   F10 could be added to.
7. **`.A_REN(req_i && !do_write)`**, still. `docs/57` section 8.3's six
   AND gates and 0.147 mW, unbuilt in three documents now.
