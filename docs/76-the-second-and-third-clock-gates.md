# 76 — The second and third clock gates: the fabric and the accelerator stop, and F9 does not have to be weakened to let them

`docs/57-power-under-a-duty-cycle.md` section 16 ranked one design change
second and priced it in a sentence that was not about area:

> **Every gated domain is a new false path, a new hold risk at the
> enable, and a new way for a block to be asleep when the fabric
> addresses it.** `soc_bus.v`'s no-starvation property F9 and its
> response-ownership queues assume every slave answers; a slave whose
> clock is off does not. **That is a formal re-proof, not a gate.**

**This is that change, and the re-proof is not what it looked like.**
F9 is not weakened, not re-stated and not given a new antecedent. What is
added is one property — **F10, the clock-gate enable is COMPLETE** —
proved by k-induction, and it says that in every cycle where the fabric's
enable is low no register in `soc_bus` changes value. A design whose
state does not change is a design whose state does not change whether or
not it is clocked, so the gated fabric and the ungated one have the same
state in every cycle, and **F1 to F9 transport unchanged rather than
being re-argued against a sleeping slave.** `docs/50` section 8.1's rule
— *extend, do not relax* — is followed by adding a theorem rather than by
editing a hypothesis.

**Three integrated clock gates where there was one**, and the census is
the netlist's:

| | `s76base`, CLKGATE = 0 | **`s76gate`, the design** |
|---|---:|---:|
| `sg13g2_lgcp_1` in the netlist | **1** | **3** |
| flip-flops on the **ungated** clock, from CTS | **3,551** | **1,404** |
| `u_ibex.clk` | 2,323 | 2,323 |
| **`clk_npu`** | — | **2,089** |
| **`clk_bus`** | — | **55** |
| share of the design behind a gate | **39.5 %** | **76.0 %** |

**[fact, `grep sg13g2_lgcp_1` on the two netlists and `CTS-0010` /
`CTS-0011` in the two CTS logs]**

**Measured on two place-and-route runs one parameter apart, whose
`resolved.json` differ in NO key: idle power at the typical corner falls
from 18.745 mW to 8.287 mW, a factor of 2.26, and the orbit average at
`docs/05` profile 1's own 0.0044 % duty cycle falls with it** **[fact
for the two powers, estimate for the average]**. `docs/57` section 6
priced the entire remaining switching-activity range at **1.22 mW**;
this is **10.458**.

**And the accelerator's clock is stopped 96.6 % of the whole-SoC
self-test — a program that performs an inference — and 99.96 % of
`docs/46`'s supervisor** **[fact]**. `docs/57` section 9 measured that
`soc_npu` multiplies the SoC's idle power by 5.588 because it has no
gate; `docs/61` section 7.3 measured that all 2,178 flip-flops it brought
sit on the ungated net. Both of those are now false statements about this
design.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file in the working tree; **[estimate]** = derived or
judged; **[assumption]** = chosen, with the effect of choosing
differently stated; **[planned]** = intended, with nothing behind it yet.

**The pilot is untouched and so is every frozen directory.**
`docs/34-pilot-freeze.md` pins the TTIHP26b submission by git blob hash
and the shuttle closes 2026-09-21. **Nothing in `hw/rtl/`, `hw/tb/`,
`tt/`, `formal/` or `hw/openlane/` is modified, and `hw/tb/Makefile.fi`
was not invoked.** `hw/rtl/pilot_top.v` is instantiated and never copied,
exactly as `docs/51` instantiates it, and the one thing this document
does to it is **stop its clock from outside**, which is the only thing a
frozen block's clock allows.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **What is gated?** | **The fabric (`u_bus`, 55 flip-flops) and the accelerator (`u_npu` and the frozen die inside it, 2,089), as two domains.** Section 3 |
| **What is not, and why?** | **The CLINT, and it is the largest target in the design.** `TICK_DIV = 1`, so `mtime` increments and its SECDED codeword is re-encoded on every clock edge: a complete enable for that block is the constant 1 and an incomplete one stops the architectural time base. Measured here at **53.75 % of all idle switching**. The GPTIMER prescaler and the UART baud divider are the same argument at 15.38 % and 14.36 %. Section 3.3 |
| **What became of F9?** | **Nothing. It is the property it was, and it is still proved.** The obligation is discharged by F10 — the enable is complete, so the gated and ungated fabrics have identical state in every cycle — and not by adding "and the slave is awake" to F9's antecedent. F10 is proved by k-induction and **every one of its five terms is load-bearing: five mutations, five failures, each on the register whose motion that term makes visible.** Section 4 |
| **What wakes each domain, and how late is it?** | **Nothing wakes them; they are never asleep when they are needed.** Both enables are combinational functions of the cycle's own inputs, and an integrated clock gate latches its enable on the falling edge, so an enable that rises in cycle N produces the edge that ENDS cycle N. **Wake latency is zero cycles by construction**, and the slave's `gnt` is combinational anyway. Section 5 |
| **Is the accelerator one domain or several?** | **One, and the transport is why.** `soc_npu_ser` divides `clk_i` to make `ser_sck`, which `pilot_top` samples on `clk`. Two domains would put a clock-domain crossing on the die's serial port — inside a block that is frozen and cannot be given a synchroniser. Section 3.2 |
| **Did the behaviour change?** | **No, and it is measured rather than argued.** Two whole-SoC builds from one source tree, one parameter apart: **5,140 signal paths compared at every one of 415,345 clock edges, and the only three that ever differ are the two gated clock nets and the accelerator's own enable; with those three named and excluded, 5,137 paths and ZERO cycles differing.** A second comparison against `HEAD`'s design over the whole testbench adds 5,195 paths and finds only a testbench filename string and one Verilog function's argument storage. The invariants are **220,256 and 415,324**, 28 of 28 checks, mask 0, `BSTAT 0x00030000`, 1,135 console characters, 0 framing errors — unchanged. The supervisor's answer is `sig = 216f8ce6` and its two logs are byte-identical. Section 6 |
| **How often do the gates close?** | **The fabric's on 63.28 % of `docs/46`'s supervisor and the accelerator's on 99.96 %; in the WFI window both close on 99.94 % of cycles.** On `docs/51`'s whole-SoC self-test, which performs an inference, the accelerator's still closes on **96.61 %**. Section 7 |
| **What does it buy?** | **Idle power at the typical corner falls from 18.745 mW to 8.287 mW — a factor of 2.26 — and the orbit average at profile 1's own 0.0044 % duty cycle falls with it, 18.746 to 8.289.** The mechanism is visible in the group split: Sequential 2.40x and Clock 2.41x, which are the 2,144 flip-flops' clock pins and the tree that used to reach them. **`docs/57` section 6 priced the ENTIRE remaining switching-activity range at 1.22 mW; this is 10.458, which is 8.6x that bound.** Section 8.4 |
| **And what does it cost in power?** | **The busy figure RISES, 33.359 to 45.199 mW, and this document reports it without attributing it to the gates.** The same two designs at synthesis go the other way (60.073 to 40.216), the gated netlist is 19.3 % more expensive with NO annotation at all, and the whole delta is in the Combinational group's `repair_design` cells on a layout that routes 6.8 % more wire. `docs/71`'s rule — a delta between two layouts of this flow is a delta of netlists — is why it is not attributed, and section 8.5 names the run that would settle it. Section 8.5 |
| **What does it cost in area?** | **Below the mapper's own noise, and the noise is measured rather than assumed.** Two `sg13g2_lgcp_1` are **54.432 um2**; `soc_bus` with its enable is **38.6694 um2 SMALLER** than the same block with the enable tied high, and `soc_npu` at CLKGATE = 1 is **180.684 um2 smaller and 3 flip-flops fewer** than at CLKGATE = 0. Section 9 |
| **A gate that changes the flip-flop count is a behavioural change.** | **This one does not, and the seven flip-flops that move are named.** The whole-SoC count goes 5,874 to 5,871: **+2 for the wake-hold counter — three bits in the RTL, two flip-flops in the netlist — and −5 for a duplicate copy of `ev_state` and a registered copy of `aer_stb_state` that the UNGATED build's mapper creates and the gated one does not.** Not a state change: `ev_state` is one 4-bit register in the RTL either way, and section 6's bit-exact equivalence is the proof of it. Section 9.2 |
| **Do the gates close their own timing?** | **NO, AND THAT IS THE NEGATIVE FINDING OF THIS DOCUMENT.** An integrated clock gate's enable is a FULL-CYCLE setup path against the rising edge, and at the **slow** corner both miss it at sign-off: `u_bus_cg` by **−0.7495 ns** and `u_npu_cg` by **−5.0198 ns**. Both MEET it at typical and fast. They are 2 of the 3,131 setup endpoints that corner already fails on, and the design fails it on 3,055 without them — but **a violated setup check at a clock gate is a possible glitch on a clock net and not a wrong data bit**. The cone that costs the accelerator's is `\|sticky_ev`, the eleven fault lines that are in the enable precisely so a sleeping accelerator can still report an upset; the repair is named, costs one flip-flop and one cycle of wake latency on a fault, and is ranked first in section 14. Section 9.5 |
| **Did anything else break?** | **One guard, and repairing it made it stronger.** `test_the_aer_strobe_gate_is_in_the_netlist_and_costs_no_flip_flop` asserted that removing `docs/56`'s combinational strobe gate makes the netlist smaller; on this design it **inverted**, for the register-duplication reason above. It is now a **fan-in cone census** of the die's strobe pin, which cannot invert, and it fails on a mutation the cell count would have missed. Section 9.3 |
| **What is NOT covered?** | Section 10 |

---

## 2. Reproducing the instruments before moving them

`docs/44` section 5.2's rule. **Seven instruments are used here and all
seven were reproduced first**, and four of them are `docs/57`'s own.

| What | Published | Measured here |
|---|---|---|
| `docs/47` section 9 / `docs/53` section 7.1 / `docs/57` section 2, unannotated power on `full3` | **27.774 / 34.835 / 46.095 mW** | **27.7743 / 34.8347 / 46.0951 mW**, to every digit, `power_soc_top.sh report … default` **[fact]** |
| `docs/57` section 8.1's unannotated per-macro column | 0.9573 / 0.9527 / 0.9464 / 0.9464 / 0.1508 / 0.1144 mW | **the same six, to four decimal places** **[fact]** |
| **`docs/57` section 4.2, the clock gate measured** | `u_ibex.clk` at **1.9995** transitions per cycle awake and **0.0004** in WFI | **1.9995 and 0.0004**, on a design five documents newer **[fact]** |
| **`docs/57` section 5.2, the supervisor's window split** | 29,302 busy, 39,804 idle, 69,106 total, **57.6 % idle** | **29,302 / 39,804 / 69,106, 57.5985 %** **[fact]** |
| `docs/46` section 7.1 / `docs/57` section 2, the supervisor's answer | `sig = 216f8ce6`, window 9,376..67,296 | **`216f8ce6`, 9,376..67,296** **[fact]** |
| `docs/68` section 8 / `docs/75` section 7.5, the whole-SoC invariants | **220,256** in the image, **415,324** for the run | **220,256 / 415,324**, 28 of 28, mask 0, `0x00030000`, 1,135, 0 **[fact]** |
| `docs/75` section 3, the TMR cone census | watchdog **29/29/29**, boot **23/23/23**, NPU cause bank **25/25/25** | **the same three, on all four netlists this document builds** **[fact]** |

**And one instrument was NOT reproduced, which is stated rather than
smoothed over.** `docs/57` section 5.2's **5.539 mW idle and 33.890 mW
busy** are figures for `hw/soc/pnr/runs/full3`, a layout that
`docs/57` section 3.2 itself found **does not contain the accelerator**,
and its dumps are gone. They cannot be re-derived here: this design's
workload does not bind to that netlist — the RAM's macros moved from
`u_ram.g_ram_2048x64` to `u_ram.g_ram_2048x64_ecc` behind `docs/67`'s
codec, and the register population is 3,113 bits against that document's
2,905. **What is reproduced is the instrument, the mechanism and the
workload; what replaces the two numbers is section 8's own baseline,
measured on the design that exists with its ungated control beside it.**
That is `docs/70`'s form and it is the stronger comparison anyway: the
two layouts differ by one parameter and by nothing else.

---

## 3. What is gated, what is not, and why

### 3.1 The fabric

`soc_bus.v` gains one output, `clk_en_o`, and no state:

```verilog
assign clk_en_o = !issue_en || mi_req_i || md_req_i
               || (|s_rvalid_i) || err_rvalid;
```

Five terms, one per reason this module can have work to do at the edge
that ends the cycle, and the file's header names them G1 to G5. **They
are not a power-management policy**: the enable reads this module's own
ports and two of its own registers and nothing else — in particular it
does not read `core_sleep_o`, which is what `docs/57` section 16
proposed. Section 4 is why that matters and
`sw/tests/test_soc_clkgate_guards.py` is where it is enforced.

**`cnt_i`, `cnt_d` and `q_fill` are deliberately absent.** A master with
an outstanding request is waiting for a slave, and waiting costs this
module nothing until the response arrives. An "something is outstanding"
term would hold the fabric's clock on for the 172 cycles of an NPU
register-window access and buy nothing. **F10 is what says so**, because
the enable it proves complete does not contain one — and section 7's
cocotb measurement is what shows it matters: on a 40-cycle slave, **the
fabric's enable is low for 39 of the 40 cycles** **[fact]**.

### 3.2 The accelerator, as one domain

`soc_npu.v` gains `clk_en_o` and one three-bit counter. The enable is a
disjunction of every reason the block or the die behind it could have
work to do, written out in the file; the classes are:

| class | terms |
|---|---|
| the fabric slave face | `req_i`, `rvalid_o`, `win_out`, `win_state != W_IDLE`, `win_guard != 0` |
| the peripheral face | `psel_i`, `flush_pulse`, `scrub_pulse` |
| **anything that has to be RECORDED** | `\|sticky_ev` — all eleven cause lines |
| the serial transport | `ser_busy`, `ser_start`, `ser_done`, `ser_timeout` |
| the event engine and the queues | `ev_state != E_IDLE`, `ev_start`, `aer_in_stb`, `inj_rd_en`, `inj_rd_valid`, `cap_wr_en`, `cap_rd_en`, `cap_rd_valid`, `oh_req`, `oh_guard != 0`, `!inj_empty`, `!cap_empty` |
| **the die** | `node_busy`, `node_aer_out_vld`, `!node_aer_in_rdy` |

**The third row is the one that gating a fault-tolerant block gets wrong
by default, and it is a finding rather than a detail.** A clock-gated
flip-flop still holds state and can still be upset; what it cannot do is
*report* the upset, because the voter's correction, the queue's parity
discard and the cause bank's own mismatch are all recorded by registers
that need a clock. `soc_busstat.v` counts `npu_cor_ev`, `npu_det_ev` and
`npu_tmr_ev`, and a sleeping accelerator would have absorbed the upset
and told nobody — which is exactly the defect `docs/52` section 10 named
("79 upsets absorbed by mechanisms that worked and visible to nothing")
and `docs/55` closed. **`|sticky_ev` in the wake condition is what keeps
it closed**: an upset inside a sleeping accelerator wakes it up.

**IT IS ONE DOMAIN AND NOT SEVERAL, and the transport is the reason.**
`soc_npu_ser` generates `ser_sck` by dividing `clk_i` (`SER_HALF = 2`),
and `pilot_top` samples that pin on its own `clk`. Splitting the CPU face
from the die would make the die's serial port a crossing between a
divided clock and a stopped one — a real clock-domain crossing, in a
block that has none and **cannot be given one, because `hw/rtl/` is
frozen and the only thing reachable from outside `pilot_top` is its
clock**. The die stops with its transport or not at all. The same
argument disposes of a finer split inside the die: `pilot_top`'s
internals are not this project's to partition.

### 3.3 The CLINT cannot be gated, and it is the largest target

`docs/57` section 7.3 measured `u_clint` at **52.43 %** of all idle
switching and asked whether it was the next gate. Measured again here on
the design as it stands:

| block | flip-flop bits | **computing** | **waiting** |
|---|---:|---:|---:|
| `u_ibex` | 2,436 | **85.22 %** | 0.02 % |
| **`u_clint`** | 108 | 3.47 % | **53.75 %** |
| **`u_ram`** | 84 | 1.49 % | **16.46 %** |
| **`u_timer0`** (with the watchdog) | 100 | 0.85 % | **15.38 %** |
| **`u_uart0`** | 29 | 0.81 % | **14.36 %** |
| `u_rom` | 33 | 4.10 % | 0.00 % |
| **`u_bus`** | 38 | 3.92 % | **0.00 %** |
| `u_boot` | 120 | 0.00 % | 0.02 % |
| **`u_npu`** | 32 | 0.01 % | **0.00 %** |
| `u_pnp`, `u_apb`, `u_apbpnp`, top | 133 | 0.15 % | 0.00 % |
| **total transitions** | **3,113 bits** | **6,495,753** | **485,141** |

**[fact, `power_soc_top.sh annotate --blocks` on the supervisor's two
windows]**

**The bit counts are the DUMP'S register population and not the
netlist's**, which is `docs/57` section 13's caveat and matters twice
here. A bit enters the population by moving at least once in the run, so
a block the workload never exercises appears at a fraction of its width:
**`u_npu`'s 32 is the accelerator's moving bits on a program that never
uses it, against 2,089 flip-flops in the netlist**, and `u_bus`'s 38 is
against 55. The shares in the two right-hand columns are shares of the
transitions that happened, and those are exact.

> **THE FABRIC AND THE ACCELERATOR CARRY 0.00 % OF THE IDLE SWITCHING
> BETWEEN THEM, AND GATING THEM IS STILL WORTH 10.458 mW.** That is not a
> contradiction, it is `docs/57` section 6's finding restated: this
> design's power is **clock-driven**. That document measured the entire
> range of switching activity the two workloads occupy at **1.22 mW,
> 3.6 %**, against **28.4 mW** for the one gate that existed. What these
> two gates remove is not data switching — there is none to remove — it
> is **2,144 flip-flops' clock pins and the tree that reaches them**, and
> section 8.4 measures that the two groups those live in fall by 2.40x
> and 2.41x while the block-level switching table above does not move at
> all.
>
> **AND THE THREE COUNTERS THAT DO CARRY THE IDLE SWITCHING CANNOT BE
> GATED, WHICH IS A DESIGN ANSWER AND NOT A FAILURE.** `soc_clint.v`
> ships `TICK_DIV = 1`, so `mtime` increments on every clock edge and
> `docs/58`'s H6 re-encodes its SECDED codeword on every edge with it: a
> COMPLETE enable for that block is the constant 1, and an incomplete one
> stops the architectural time base. **A CLINT whose `mtime` stops is not
> a CLINT.** `soc_gptimer`'s prescaler and `soc_uart`'s baud divider are
> the same argument at a smaller size. **The one lever that exists there
> is `TICK_DIV`, and it is a prescaler and not a sleep gate**: at
> `TICK_DIV = N` the 72 flip-flops of the time base need a clock once in
> N cycles and the tick counter still needs one every cycle, at the cost
> of the cycle-accurate `mtime` the bring-up program computes its
> deadlines from. Not taken, and section 14 ranks it.

### 3.4 `u_ram` at 16.46 % of idle switching is new, and it is `docs/67`'s scrubber

`docs/57` measured `u_ram` at **0.00 %** of idle switching. It is
**16.46 %** here, and nothing about the gates caused it: `docs/67` put
`soc_mem_ecc.v` under both memories with a background scrubber whose
interval resets to 255, so the RAM is walked continuously whether or not
anything is using it. **It is now the second-largest consumer of idle
switching in the SoC** **[fact]**, and like the CLINT it is not a gate
question — a scrubber that stops is not a scrubber. It has a knob the
CLINT does not: `SCRUB_IVL_RST`, which trades scrub rate against idle
switching directly and is a mission parameter rather than a design one.
Section 14.

### 3.5 What is not gated here, and what it would have been worth

`u_apb`, `u_pnp`, `u_apbpnp`, `u_gpio`, `u_qspi`, `u_scrub`, `u_busstat`,
`u_boot` and the two memories' request paths keep their clock, and so do
the three blocks section 3.3 says cannot lose it. **1,404 flip-flops
remain on `clk_i_regs`**, and that number is the ceiling on a fourth
gate rather than its value: the CLINT's time base and codeword, the
GPTIMER's prescaler and counters, the watchdog and the UART's divider
are inside it and none of them can be taken. What is left carries
**0.00 % of the idle switching** between it and the fabric, so a fourth
gate buys clock-pin energy and nothing else — the same thing these two
buy, at a fraction of the population.

Each needs its own completeness argument, and they are not all the same
size: `soc_apb_bridge` is three states and one response register and
already carries a property set F10 could be added to, while `soc_pnp`
needs an RTL change first — it reloads `rdata_o` from the broadcast
address on **every** cycle whether or not it was addressed, so its
enable is either a 32-bit comparator or a `req_i` qualification on that
register. They are ranked in section 14 and not taken, for the reason
`docs/64` gives about scope: this document already changes three RTL
files and one formal property set, and **a gate whose enable is asserted
rather than proved is what `docs/57` warned against.**

---

## 4. F9, and why it did not have to change

### 4.1 The obligation, stated as `docs/57` and `docs/61` stated it

`docs/61` section 11 named the price of this change in one line:
*"`soc_bus.v`'s no-starvation property F9 and its response-ownership
queues assume every slave answers; a slave whose clock is off does
not"* — and recommended not building the gate until
`hw/soc/formal/soc_bus.sby` was green at HEAD. It is green: `docs/50`
section 8.1 repaired it, and section 2 above re-ran it.

The obligation is real and it is sharper than "a slave might be slow".
F9's antecedent contains `&s_gnt_i` — **every slave ready** — and a
slave whose clock is stopped cannot assert `gnt`. To a property, a slave
that cannot answer and a slave that refuses to answer are the same
slave. The tempting repair is to add "and the slave is awake" to F9's
antecedent, and **that is exactly the relaxation `docs/50` section 8.1
refused**: it would make the fairness bound conditional on a signal the
property has no way to bound, and the boot cycle that document caught
would fall out of the property set a second time.

**And there is a second reason not to touch F9, which is worth stating
because it also bounds what F9 was ever worth.** `soc_bus`'s properties
are proved on the module, where `s_gnt_i` is a free six-bit input, so
`&s_gnt_i` is reachable there. In the assembled SoC it is not: every
slave's `gnt_o` is qualified by its own `req_i`, the fabric drives at
most one `s_req_o` at a time, so **all six slaves are never
simultaneously granting.** F9 is a statement about the arbiter under an
environment assumption, and it is the narrow statement
`soc_bus_props.v`'s own header says it is. Adding a wakefulness term to
it would have been narrowing an antecedent that is already narrow, to
buy a property nobody could then check. **F10 has no antecedent about
the environment at all** — it is unconditional on the module's own
state — which is why it is the one that carries this change.

### 4.2 The repair is a theorem about the enable, not a change to F9

**F10.** In every cycle where `clk_en_o` is low, no register in `soc_bus`
changes value.

```verilog
always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni
                            && !$past(clk_en_o)) begin
    assert (issue_en   == $past(issue_en));
    assert (last_was_d == $past(last_was_d));
    assert (err_rvalid == $past(err_rvalid));
    assert (cnt_i      == $past(cnt_i));
    assert (cnt_d      == $past(cnt_d));
    assert (lock_i     == $past(lock_i));
    assert (lock_d     == $past(lock_d));
    for (f_g = 0; f_g < F_NS; f_g = f_g + 1) begin
        assert (q_owner[f_g] == $past(q_owner[f_g]));
        assert (q_fill[f_g]  == $past(q_fill[f_g]));
    end
end
```

**Why that is enough.** `soc_top.v` replaces the fabric's clock with
`ICG(clk_i, clk_en_o)`. The gated instance's state can differ from the
ungated one's only at an edge the gate removed, and F10 says the ungated
instance's state does not change at those edges either. By induction on
cycles the two are equal in every cycle; their outputs are combinational
functions of that state and of the same inputs; **so the gated fabric
satisfies exactly the properties the ungated one satisfies, F9
included.** F1 to F9 are not restated, not re-parameterised and not
re-proved against a sleeping slave. **The property set gains a theorem
and loses nothing, which is what "extend rather than relax" means.**

**And it says nothing about asynchronous reset, which is why the gate is
safe at boot.** Every register in `soc_bus` is reset on `negedge rst_ni`
with no clock, so a stopped gate cannot hold a stale value through a
reset; the guard `$past(rst_ni) && rst_ni` excludes the reset edge for
that reason and not to avoid a failure.

**The gate is instantiated in `soc_top.v` and not inside `soc_bus.v`, and
that placement is the whole reason the transport argument works.** Every
property in `soc_bus_props.v` samples `posedge clk_i`. If the module
gated its own clock, F1 to F9 would be properties of a design whose clock
the property set could not see, and **F9 in particular counts cycles**.
Proved as written, on an ungated clock, plus F10, the substitution is
sound and visibly so.

### 4.3 The result, and the vacuity check

| task | engine | result |
|---|---|---|
| `bmc`, depth 24 | `smtbmc yices` | **PASS** |
| `prove`, k-induction, depth 12 | `smtbmc yices` | **PASS**, *"successful proof by k-induction"*, basecase and induction |
| `cover`, depth 24 | `smtbmc yices` | **PASS, 20 of 20 reached** (was 16 of 16) |

**[fact, `hw/soc/formal/soc_bus_*/PASS`, 20.4 s for all three]**

Three covers are new and they are not decoration. `docs/09` section B.1
makes an assert set with unreachable behaviour a red result, and **F10 is
satisfied by an enable that is the constant 1** — a proof that a clock
gate nobody built is safe. So:

- **G1** — `cover (!clk_en_o)`: the gate closes at all.
- **G2, G3** — `cover (!clk_en_o && f_out_i != 0)` and the same for the
  data port: **it closes while a request is outstanding**, which is the
  case section 3.1 says the missing "outstanding" term buys.

### 4.4 Five mutations, five failures, one per term

A property that cannot fail is not a property. Each of the enable's five
terms was deleted in turn, in a scratch copy outside the working tree,
and `bmc` re-run:

| the enable, mutated | result | the assertion that fired |
|---|---|---|
| `!issue_en` dropped | **FAIL** | `issue_en == $past(issue_en)` |
| `md_req_i` dropped | **FAIL** | `last_was_d == $past(last_was_d)` |
| `err_rvalid` dropped | **FAIL** | `err_rvalid == $past(err_rvalid)` |
| `mi_req_i` dropped | **FAIL** | `cnt_i == $past(cnt_i)` |
| `(\|s_rvalid_i)` dropped | **FAIL** | `cnt_d == $past(cnt_d)` |
| **none — the file as committed** | **PASS** | — |

**[fact, `sby -f soc_bus_mut.sby bmc` on six builds]**

**Every term is load-bearing and each fails on the register whose motion
that term exists to make visible.** The enable is therefore not merely
sufficient; nothing in it is redundant.

### 4.5 What the simulation catches, and what it does not

The same statement is checked by execution in
`hw/soc/tb/cocotb/test_soc_bus.py`: sample the whole of `soc_bus`'s state
at every edge of a mixed workload and assert it did not move in any cycle
where the enable was low. **It passes, and it catches two of the five
mutations.**

| mutation | formal `bmc` | cocotb |
|---|---|---|
| `!issue_en` dropped | **FAIL** | pass |
| `md_req_i` dropped | **FAIL** | pass |
| `err_rvalid` dropped | **FAIL** | pass |
| `mi_req_i` dropped | **FAIL** | **FAIL** |
| `(\|s_rvalid_i)` dropped | **FAIL** | pass |
| the enable replaced by `1'b1` | (vacuity: covers G1-G3 unreachable) | **FAIL, 2 tests** |

**[fact, `make -f Makefile.soc_bus SOC_BUS_SRC=<mutant>`]**

> **THIS IS THE ARGUMENT FOR HAVING BOTH, AND IT IS THE ARGUMENT FOR THE
> FABRIC'S GATE RESTING ON THE PROOF.** The three mutations the
> simulation misses are misses of exactly the kind `docs/50` section
> 8.1's counterexample was: **`!issue_en` is the boot cycle**, which
> `setup()` has already passed by the time the test begins sampling, and
> the other two are states this workload does not reach. A k-induction
> proof quantifies over every reachable state and a workload visits the
> ones it happens to visit. The cocotb test earns its place by running
> against the RTL a simulator elaborates and by failing in a minute; it
> does not earn the gate.

### 4.6 F9 is not the only property a stopped clock touches, and the rest are not proved

**Every property set in this repository is proved on a module whose
`clk_i` is a port, and after this change several of those modules sit
inside a gated domain.** The instantiated ones are `soc_npu_ser` from
`hw/soc/formal/`, and `aer_fifo`, `lif_ctrl`, `lif_mem` and `tmr_voter`
from the pilot's own `formal/` — `docs/34` freezes that directory, so
none of the second group may be extended here in any case.

**For `soc_bus` the transport is a theorem.** For all of those it is
**the same measured equivalence section 6 reports and nothing more** —
which is sound, because a design whose state is identical in every cycle
satisfies the same properties, but the premise is measured over two
workloads rather than proved over every reachable state. **This is the
sharpest limitation of the accelerator's gate and it is stated here
rather than in a footnote.**

Three things bound it. `tmr_voter` and the two `secded` blocks are
**combinational** and carry no clock at all, so a stopped clock cannot
reach them. `npu_regbank` and `scrub` carry property sets and are **not
instantiated in this SoC** — `pilot_top` builds its own configuration
bank and does its ECC repair inline — so their proofs are untouched by
this change. And the whole formal set was re-run: **14 jobs, 58 tasks,
58 PASS, 0 FAIL** (section 12.1), which is the check that the RTL
changes did not disturb what the proofs are proved on.

---

## 5. Waking: what starts each domain, and how late it is

This is where `docs/57` said the bugs would be, so it is stated as a
mechanism rather than as a claim.

### 5.1 Zero cycles, and it is a property of the cell

An `sg13g2_lgcp_1` is a **latch-then-AND**, `clock_gating_integrated_cell
: "latch_posedge"` in the Liberty: the latch is transparent while `CLK`
is low, **closes on the rising edge**, and `GCLK = latch_q & CLK`. So the
value that decides an edge is the enable's **settled value during
cycle N**, and the edge it decides is the one that **ENDS cycle N**. An
enable that is a combinational function of cycle N's own inputs
therefore opens the gate in time for the edge that captures those
inputs, and the block is never a cycle behind.

Both enables are exactly that. `soc_bus`'s is one `assign` over its ports
and two of its own registers. `soc_npu`'s is one `assign` over its ports,
its FSM states, its queue flags and the die's status pins. **Neither is
registered, and `sw/tests/test_soc_clkgate_guards.py` fails if either
becomes so**, because a registered enable would cost one cycle on every
wake of the block every access in the SoC passes through.

**AND THAT MAKES THE ENABLE A FULL-CYCLE TIMING PATH, NOT A HALF-CYCLE
ONE.** Because the latch closes on the rising edge, OpenSTA's clock
gating check requires the enable to be stable at that edge: the data
required time is one clock period minus the cell's own setup, and the
launch is the previous rising edge. It is an ordinary setup path that
happens to end at a clock gate — **and section 9.5 is what that costs on
this design, because one of the two does not make it.**

### 5.2 So a gated slave never answers late

The three things that could make a gated slave look broken to the fabric,
and what each resolves to:

| the worry | what actually happens |
|---|---|
| *"a peripheral whose clock starts on its first APB access answers one cycle late"* | It does not start on the access; it starts **for** the access. `req_i` and `psel_i` are terms of the enable, so the clock edge that captures the request is not the edge after the request — it is the edge that ends the request's own cycle. And `gnt_o` is combinational in both blocks (`req_i && win_state == W_IDLE` for the NPU window), so the grant does not wait for a clock at all. |
| *"a domain woken by an interrupt must be awake to see the interrupt"* | Neither gated domain has an interrupt input. The NPU's `irq_o` is an **output**, `\|(cause & irq_mask)`, combinational over registers that hold their value with the clock stopped — so a pending interrupt survives the gate and keeps being asserted. The fabric has none. |
| *"a fault-tolerant block cannot report a fault with its clock stopped"* | True, and it is the reason `\|sticky_ev` is in the accelerator's enable. Section 3.2. |

### 5.3 And one margin, because the die is frozen

`soc_npu`'s enable also carries `wake_hold`, a 3-bit counter that keeps
the clock running for **`HOLD_CYCLES = 4`** cycles after the last
activity term goes away. It is **not a correctness term** — the design
would be correct at 0 if the enable is complete — and it is not there
because anything was found to need it. It is there because
`hw/rtl/pilot_top.v` is frozen: its 2,152 flip-flops include two-flop
input synchronisers and internal settling chains that no term of
`npu_act` names, its property set is `formal/` and is not this work's to
extend, and **completeness for it is measured (section 6) rather than
proved**. Four cycles covers a two-flop synchroniser and one cycle of
slack. It costs **two flip-flops** — three bits in the RTL, two after mapping —
and four clocked cycles per wake, against 2,089 flip-flops of clock per
idle cycle.

`win_guard` and `oh_guard` are in the enable for a related but different
reason, and it is worth naming because it is not a correctness term
either: both are cleared to zero the cycle **after** the thing they were
counting goes away, so leaving them out would freeze a stale non-zero
count. Neither can cause a spurious expiry — both expiries are qualified
by `win_out` and `oh_req` — so nothing would misbehave. **They are there
because the verification instrument is bit-exact equivalence, and a
design that is only almost equivalent cannot be checked that way.**

---

## 6. The behaviour did not change, and it is measured four ways

`docs/64`'s standard: an argument of that kind is checked, not trusted.

### 6.1 Two builds from one source tree, one parameter apart

`SOC_CLKGATE=0` is a measurement knob on three flow scripts and on
nothing else; `soc_top.v`'s `CLKGATE` defaults to 1 and
`sw/tests/test_soc_clkgate_guards.py` enforces that nothing in the design
sets it to 0. The CLKGATE = 0 arm elaborates **no enable at all** — not
an enable that is ignored — which is `docs/41` section 6.5's rule about
what a baseline has to be.

| what | HEAD, `179dba2` | with the gates |
|---|---|---|
| `hw/soc/flow/sim_soc.sh`, the whole SoC | 220,256 cycles in the image, 415,324 for the run, 28 of 28 checks, fail mask 0, `BSTAT 0x00030000`, 1,135 console characters, 0 framing errors | **220,256 / 415,324 / 28 of 28 / mask 0 / `0x00030000` / 1,135 / 0** **[fact]** |
| the whole `sim.log` | — | **byte-identical apart from the output directory named in its banner** **[fact, `diff`]** |
| `hw/soc/flow/fi_core.sh`'s supervisor, clean run | `sig = 216f8ce6`, window 9,376..67,296, 7 kicks, `wdog_win 00000003` | **byte-identical log** **[fact, `diff`]** |

### 6.2 Every signal, at every edge, for the whole run

`hw/soc/flow/clkgate_check.py equiv` walks two dumps in lockstep and
compares every VCD path under a scope at every rising clock edge, **by
path and not by identifier** — the two dumps assign identifiers
independently — with the whole timestamp applied before the comparison,
which is `vcd_activity.py`'s rule and is there for its reason: a VCD
orders the changes inside a timestamp by identifier rather than by
cause, so a per-line comparison would be a comparison of sort order.
A path present in only one dump is **reported and not compared**, and
the count of those is part of the result.

Two comparisons, because they answer different questions:

| comparison | scope | paths | cycles | **paths that ever differ** |
|---|---|---:|---:|---|
| **A**: `HEAD` `179dba2`'s design against the gated one | `tb_soc.dut.u_npu`, `tb_soc.dut.u_bus` | **1,184** | 415,345 | **1**: `u_bus.clk_i`, the gated clock itself |
| **A'**: the same pair, the whole testbench | `tb_soc` | **5,195** | 415,345 | **2**, both named below and neither a design signal |
| **B**: two builds from ONE source tree, one parameter apart | `tb_soc.dut` | **5,140** | 415,345 | **3**: `clk_bus`, `clk_npu`, `npu_clk_en` |
| **B'**: the same pair with those three excluded | `tb_soc.dut` | **5,137** | 415,345 | **NONE. 0 cycles differing.** |

**[fact]**

**Comparison B's three are the whole of what this change creates**:
the two gated clock nets and the accelerator's enable. `bus_clk_en` is
not among them, because `soc_bus` computes it unconditionally and it is
therefore the same signal in both builds — which is itself the check
that the enable is a statement about the fabric and not a knob. **B' is
the same walk with those three named and removed, and it reports zero
differences over 5,137 paths and 415,345 clock edges** **[fact]**.

The seven paths that exist in only one build are listed by the tool and
are all the change itself: `g_noclkgate._unused_cg` in the baseline, and
in the gated build the two gate cells' `en_latch` and `test_en_i`,
`npu_act` and `wake_hold`.

**AND B' HAD TO BE RUN TWICE, WHICH IS AN INSTRUMENT DEFECT WORTH
RECORDING.** The first attempt excluded `tb_soc.dut.clk_bus` and
reported the same 25,029 differing cycles under the name
`tb_soc.dut.u_bus.clk_i`. A VCD identifier carries several aliases — a
top-level wire, the port it drives, the net inside the instance — and
`clkgate_check.py` tested the exclusion per alias and then took the
shortest survivor, so **excluding one name for a net pushed the
comparison onto the next name for the same net**. An exclusion now
applies to the identifier, decided over all of its aliases before any is
chosen; the file's own comment records it.

**Comparison A's two are named rather than filtered**, because a
comparison whose exclusions are not published is not a comparison:

- **`tb_soc.flash_fname`** — the testbench's own string holding the path
  of the flash image, which differs because the two builds were written
  to two output directories.
- **`tb_soc.dut.u_clint.wmerge.old`** — the `old` **argument of a Verilog
  function**, not a register. Icarus dumps a function's locals as static
  storage whose value between calls is whatever the last evaluation left,
  and the gated build has fewer combinational re-evaluations because two
  clock nets stop toggling. It is a property of the dump and not of the
  design; `soc_clint.v` line 384 is the function.

**Not one design register, not one output, not one interrupt line, in
either comparison.**

### 6.3 And the dumps themselves are smaller, which is the saving in bytes

| | baseline | gated |
|---|---:|---:|
| whole-SoC dump, `tb_soc.vcd` | **2,732,078,225 B** | **2,663,356,100 B** (**−2.52 %**) |
| supervisor dump, `tb_soc_fi.vcd` | **239,575,049 B** | **227,551,971 B** (**−5.02 %**) |

**[fact, `ls -la`]** — a VCD is a list of value changes, so this is the
switching the gates removed, counted by a tool that has no model of
anything. It is not a power measurement and it is not offered as one.

### 6.4 The hardening census is intact

`gl_netlist.py --tmr-census` by fan-in cone, on all four netlists this
document builds (gated and ungated, at `ROM_HARDEN` 0 and 1):

| structure | published | measured, all four |
|---|---|---|
| watchdog `u_prot_a/b/c` | 29/29/29 | **29/29/29** |
| boot `u_prot_a/b/c` | 23/23/23 | **23/23/23** |
| NPU cause bank `u_cfg_a/b/c` | 25/25/25 | **25/25/25** |

**[fact]** — no replica merged, and the accelerator's cause bank in
particular is unchanged by having its clock gated.

---

## 7. How often the gates close

`hw/soc/flow/clkgate_check.py duty`, on the design's own enables.

| workload | cycles | **`bus_clk_en` low** | **`npu_clk_en` low** |
|---|---:|---:|---:|
| `docs/46`'s supervisor, whole run | 69,106 | **43,728, 63.2767 %** | **69,081, 99.9638 %** |
| the same, **the WFI window only** | 39,804 (57.5985 %) | **39,782, 99.9447 %** | **39,782, 99.9447 %** |
| `docs/51`'s whole-SoC self-test | 415,345 | 25,029, **6.0261 %** | **401,274, 96.6122 %** |

**[fact]**

And the same thing seen at the clock nets rather than at the enables,
which is `docs/57` section 4.2's own instrument:

| clock net | sinks, `s76base` | sinks, `s76gate` | **computing** | **waiting** |
|---|---:|---:|---:|---:|
| `clk_i`, the six macros and each gate's own `CLK` pin | 7 | **9** | 2.0000 | 2.0000 |
| `clk_i_regs`, everything ungated | **3,551** | **1,404** | 2.0000 | 2.0000 |
| `u_ibex.clk` | 2,323 | 2,323 | **1.9995** | **0.0004** |
| **`clk_bus`** | — | **55** | 1.7307 | **0.0011** |
| **`clk_npu`** | — | **2,089** | **0.0003** | **0.0011** |
| **total** | **5,881** | **5,880** | | |

**[fact: the sink counts are `CTS-0010` and `CTS-0011` in the two CTS
logs; the transition rates are per cycle on the supervisor's two
windows, from `s76gate`'s own RTL]**

**The two sink columns close on the two netlists' own flip-flop counts,
and that is the check that the census is a census.** `s76base`:
3,551 + 2,323 + 7 = **5,881** = 5,874 registers plus the six macros and
one gate. `s76gate`: 1,404 + 2,323 + 2,089 + 55 + 9 = **5,880** = 5,871
registers plus the six macros and three gates. **The 2,147 flip-flops
that leave `clk_i_regs` are the 2,144 on the two new nets plus the 3 the
mapper removed** (section 9.2), and nothing is unaccounted for.

Four readings.

**THE FIRST IS THAT `u_ibex.clk` REPRODUCES `docs/57` EXACTLY** — 1.9995
and 0.0004 — on a design that has gained the accelerator, the memory
codec, the boot block, a GPIO port and a QSPI controller since that
measurement. The instrument is the same instrument.

**THE SECOND IS THAT `clk_npu` IS 0.0003 WHILE THE CORE IS BUSY.** On a
workload that never touches the accelerator, its 2,089 flip-flops are
stopped 99.98 % of the time whether or not the CPU is working. That is
the shape `docs/05` section 3.3 calls activity-proportional, and
`docs/57` section 9's closing sentence — *"the block whose entire
architectural claim is 'activity-proportional compute' is the one part of
the SoC that is not activity-proportional"* — is what it answers.

**AND THE GATES DO NOT THRASH**, which is the thing a wide enable over
many terms could easily have done. Over the supervisor's 69,106 cycles
`bus_clk_en` changes state **1,547 times — 774 sleep intervals, mean
length 56.5 cycles** — and every one of those transitions is in the busy
window, where the mean interval is 5.1 cycles. `npu_clk_en` changes
state **once in the whole run** **[fact]**. In the WFI window neither
enable moves at all: both go low at the `wfi` and stay low until the
timer interrupt.

**THE FOURTH IS THAT THE FABRIC'S GATE IS WORTH LITTLE ON A BUSY PROGRAM
AND A LOT ON AN IDLE ONE**, 6.03 % against 99.94 %, which is exactly what
it is for. Ibex issues an instruction fetch nearly every cycle when it is
running; when it is in WFI it issues nothing, and the fabric has nothing
to do but hold its 55 bits of state: three scalars, two two-bit
outstanding counters, two three-bit slave locks, and seven four-deep
ownership queues with their two-bit write indices.

---

## 8. Power

### 8.1 The method, and the two things that changed since `docs/57`

`docs/57` section 5's recipe, unchanged in shape: `docs/46`'s
time-triggered supervisor — **the only program in this repository with a
duty cycle**, and the only one whose shape is `docs/05` section 3.4
profile 1's — dumped, split into its `core_sleep_o = 0` and
`core_sleep_o = 1` windows, and turned into `set_power_activity` by
`vcd_activity.py` and `power_activity.py`. Two things had to change and
both are in `power_soc_top.sh` rather than in this document's arithmetic:

1. **The macro derivations.** `docs/67` put `soc_mem_ecc.v` under the
   RAM, so its four macros are now driven by the codec's row port
   (`row_en`, `row_we`, `row_addr`) and not by the fabric's `req_i` and
   `do_write`, and the bank select moved from `addr_i[15:14]` to
   `row_addr[12:11]`. `PWR_MEM=legacy` keeps `docs/57`'s spelling so that
   document's figures stay reproducible from this script.
2. **The gates that exist.** `PWR_GATES` says whether the target netlist
   has one integrated clock gate or three. **Annotating a gate the
   netlist does not have fails loudly; not annotating one it does have
   fails silently**, with the gated net taking the tool's default — so
   the default is the design and the reduced set has to be asked for.
   `PWR_EXCL_NPU` was split out of the same switch, because this document
   annotates one netlist with three gates and one with one and **both
   contain the accelerator**: tying the two together would have made the
   two power figures figures of two different register populations,
   which is not a comparison of gates.

**The two annotations differ by exactly two lines** — the two new gates'
`GATE` pins — and `diff` is in section 11 step 7. Same register
population (3,113 bits, activity 0.071212 busy and 0.003915 idle), same
ports, same eighteen macro pins, same Ibex gate. **Everything that could
move the number except the gates is held fixed by construction.**

### 8.2 The mechanism, on the synthesis netlists

Taken first because it isolates what the gates do to **clock-pin
energy**, which is the whole mechanism: an unrouted netlist has no wire
capacitance, so its switching column is a cell-pin figure and its total
is dominated by internal power. That is `docs/57` section 9's own
caveat, restated, and it is why this table is the SECOND measurement and
not the first.

`hw/soc/out/s76-rom0-{base,gate}/soc_top.sta.v`, typical corner, no
parasitics, the same SDC, the same annotation:

| | CLKGATE = 0 | **CLKGATE = 1** | ratio |
|---|---:|---:|---:|
| **computing** | **60.073 mW** | **40.216 mW** | **0.669x** |
| **waiting** | **34.636 mW** | **9.226 mW** | **0.266x** |

**[fact, mW at typ]**

**Idle falls by 25.41 mW, a factor of 3.75.** The busy figure falls too,
by 19.86 mW, and that is **an artefact of the workload rather than a
saving a mission would see**: `docs/46`'s supervisor never touches the
accelerator, so `clk_npu` is stopped 99.98 % of the time whether the CPU
is busy or not (section 7). **A workload that uses the accelerator would
show a much smaller busy saving and the same idle one**, and section 14
item 7 is the measurement that would say by how much.

Only the typical corner is quoted. The slow and fast columns exist in the
run directories and are **not** reported here: without parasitics the
fast corner's Sequential group comes out at 95.4 % of a 137 mW total,
which is not a figure this document is willing to stand behind, and
`docs/47` section 9's caveat about the macro Liberty being characterised
at −55 C compounds it.

### 8.3 The layouts, with extracted parasitics

Two LibreLane runs from two netlists one `chparam` apart, extracted
parasitics, three corners, the same annotation. `hw/soc/pnr/runs/s76base`
and `hw/soc/pnr/runs/s76gate`; section 9.4 is the layouts themselves and
their `resolved.json` diff, which is **empty**.

| | window | **slow** | **typ** | **fast** |
|---|---|---:|---:|---:|
| `s76base`, CLKGATE = 0 | **computing** | 26.585 | **33.359** | 42.148 |
| `s76base` | **waiting** | 15.049 | **18.745** | 23.416 |
| **`s76gate`, the design** | **computing** | 35.122 | **45.199** | 57.681 |
| **`s76gate`** | **waiting** | **6.748** | **8.287** | **10.452** |
| `s76base`, no annotation at all | — | 35.405 | 44.670 | 56.661 |
| `s76gate`, no annotation at all | — | 41.631 | 53.305 | 67.777 |

**[fact, mW]**

### 8.4 What the gates buy, and it is the idle figure

**Idle at typ falls from 18.745 mW to 8.287 mW: −10.458 mW, a factor of
2.26** **[fact]**. The group split says it is the mechanism and nothing
else:

| group, typ, **waiting** | `s76base` | `s76gate` | ratio |
|---|---:|---:|---:|
| **Sequential** | **10.423** | **4.337** | **2.40x** |
| **Clock** | **4.479** | **1.857** | **2.41x** |
| Combinational | 3.579 | 1.883 | 1.90x |
| Macro | 0.265 | 0.210 | 1.26x |
| **total** | **18.745** | **8.287** | **2.26x** |

**[fact, mW]**

> **THE TWO GROUPS THAT FALL BY 2.4x ARE THE TWO THE GATES ACT ON**, and
> they fall by almost exactly the same factor: **Sequential is the
> clock-pin energy of the 2,144 flip-flops that lost their clock, and
> Clock is the tree that used to reach them.** Nothing else could produce
> that pair of numbers, and `docs/57` section 6 already said it would be
> those two: this design's power is clock-driven, and the entire range of
> switching activity the two workloads occupy is worth 1.22 mW.
>
> **SO THE GATES BUY 10.458 mW AND THE BOUND THEY HAD TO BEAT WAS
> 1.2 mW.** That is `docs/57` section 6's measured price for every
> technique that reduces toggling — operand isolation, bus encoding, a
> quieter protocol — and these two gates are worth **8.6x** it
> **[estimate, one measured saving against one measured bound]**.

### 8.5 And the busy figure RISES, which is reported and not attributed

**`s76gate` computing is 45.199 mW against `s76base`'s 33.359: +11.840,
a factor of 1.355** **[fact]**. It is stated first and explained second
because a document that buried it would not be worth reading.

**It is not the gates' own logic and the evidence is four-fold.**

1. **The same two designs at SYNTHESIS, with no placement and no
   parasitics, go the other way**: section 8.2 measures computing at
   **60.073 mW ungated and 40.216 gated**. The gates reduce busy power by
   19.9 mW on the netlists and the layouts reverse it, so what changed is
   the layout.
2. **The gated netlist is more expensive with NO annotation at all** —
   53.305 mW against 44.670, **+19.3 %** **[fact]** — which is a figure
   taken before any measured activity enters, and therefore a property of
   the netlist and its parasitics.
3. **The rise is entirely in one group.** Sequential falls
   16.830 → 13.288 and Clock falls 7.008 → 4.367 exactly as the mechanism
   predicts; **Combinational rises 6.209 → 24.528**, and 18.319 of the
   18.32 mW delta is there **[fact]**.
4. **And inside that group it is concentrated in `repair_design`'s
   own cells.** Summed per instance: `fanout*` buffers burn **4.348 mW
   against 0.689** in the baseline and `rebuffer*` **3.591 against
   0.055**; the largest single consumer is a `sg13g2_buf_16` driving nine
   loads at the end of an XOR/XNOR carry chain **[fact]**. The gated
   layout routes **6.8 % more wirelength**, carries **400 more
   timing-repair buffers** and **31 more max-slew violations** at the
   slow corner (section 9.4).

> **`docs/71` SECTION 7's RULE APPLIES AND IS WHY THIS IS NOT ATTRIBUTED
> TO THE GATES.** That document established that this flow is
> bit-reproducible run to run, and therefore that *a delta between two
> layouts of it is a delta of netlists*. These are two different
> netlists — section 9.2 measures that `abc` remapped 141 cells and moved
> five flip-flops on a change that alters no behaviour — placed and
> routed differently. **The busy delta is a placement-and-routing
> outcome measured on one pair of runs, and one pair of runs cannot
> separate it from the gates.** What would: a third layout of the same
> gated netlist at a different floorplan density, or the gated netlist
> with the two `prim_clock_gating` instances replaced by wires so the
> netlist is otherwise identical. **Neither was run and this document
> does not claim the busy figure either way.**
>
> **WHAT IT DOES CLAIM IS THE IDLE FIGURE**, because that one moves in
> the direction, in the groups and by the factor the mechanism requires,
> and because the mission's own duty cycle multiplies it by 0.999956.

### 8.6 The orbit average, at `docs/05` profile 1's own duty cycle

`docs/53` section 6.2 sized profile 1 — nine OPS-SAT-AD telemetry
channels at 1 Hz — at **0.0044 % of the cycle budget**. At that duty
cycle:

| | `s76base` | **`s76gate`** |
|---|---:|---:|
| 0.000044 x computing | 0.0015 | 0.0020 |
| 0.999956 x waiting | 18.7442 | 8.2869 |
| **orbit average, typ** | **18.746 mW** | **8.289 mW** |

**[estimate, a measured duty cycle against two measured powers]**

> **THE ORBIT AVERAGE IS THE IDLE POWER TO THREE DECIMAL PLACES, AND AT
> THIS DUTY CYCLE IT ALWAYS WILL BE** — which is `docs/57` section 11.1's
> finding, unchanged. **The requirement is stated in tens of milliwatts
> and the measurement goes from 18.7 to 8.3**: met before and met with
> more than twice the margin after. `docs/05` section 3.4 profile 4's
> "microwatts when idle" is **still not met**, and the gap goes from
> about **1.3 to 1.9 orders of magnitude to about 0.9 to 1.6**
> **[estimate]**.
>
> **AND THE COMPARISON WITH `docs/57`'s 5.539 mW IS NOT A REGRESSION,
> IT IS A DIFFERENT DESIGN.** That figure is the idle power of a layout
> with **3,085 flip-flops and no accelerator**; this one has **5,871**,
> the accelerator among them, plus the memory codec, the boot block, a
> GPIO port and a QSPI controller. The like-for-like number is the pair
> in this section, measured on one pair of runs one parameter apart.

### 8.7 What may and may not be said outside the repository

`docs/05` section 4 rule 5 binds this, and `docs/57` section 11.3's
table applies with two of its rows changed.

| | |
|---|---|
| **May not be published** | **"8.3 mW idle"** on its own, **"45.2 mW computing"** on its own, and **any per-inference energy at all** — `docs/57` section 10.3's reason is unchanged, and section 8.5's is new: the busy figure is not attributed. |
| **May be published, with all of it or none of it** | "**Pre-silicon flow estimate at measured RTL switching activity: orbit-average power falls by a factor of 2.26, from 18.7 mW to 8.3 mW at the typical corner, on two placed and routed layouts one parameter apart that both fail setup at the slow corner, both fail max slew and max cap, have never been through DRC or LVS, and whose busy-window figures this measurement does not separate from their placement.**" |
| **Is the stronger claim anyway** | **The ratio and its mechanism**: "76.0 % of the design's flip-flops are behind an integrated clock gate, against 39.5 % before; measured on the design's own workload the two new gates are shut for 99.94 % of the idle window, and the idle power's Sequential and Clock groups fall by 2.40x and 2.41x." That is a claim about a *measured ratio* with a named mechanism, it does not depend on either absolute number being right, and it is what rule 5 exists to encourage. |
| **Never** | Any of it as **measured consumption**. |


---

## 9. Cost

### 9.1 The two blocks, on their own recipe

`yosys stat -liberty` on `ihp-sg13g2` typical, `abc -D 20` with the
flow's own `abc.constr`, one parameter apart:

| | CLKGATE = 0 | CLKGATE = 1 | delta |
|---|---:|---:|---:|
| `soc_bus`, flip-flops | 55 | **55** | **0** |
| `soc_bus`, area um2 | 10,947.3336 | **10,908.6642** | **−38.6694** |
| `soc_npu` with the pilot elaborated, flip-flops | 2,092 | **2,089** | **−3** |
| `soc_npu`, area um2 | 221,552.6796 | **221,371.9956** | **−180.6840** |

**[fact]**

**BOTH DELTAS ARE NEGATIVE AND NEITHER IS A SAVING.** One
`sg13g2_lgcp_1` is **27.216 um2** by the Liberty and two of them are
**54.432**; the fabric's enable is a five-input OR and the
accelerator's is a wide OR plus a three-bit counter. The measured
numbers are smaller than the ungated build's because **yosys's mapper
responds to the enable's fan-out**, and section 9.2 names how. The
honest statement is that **the gates' area is below this flow's own
mapping noise**, and the number that is not noise is the cell count:
**one `sg13g2_lgcp_1` becomes three.**

### 9.2 The flip-flop count moves by three, and the seven that move are named

A gate that changes the design's state is a behavioural change. This one
does not, and the arithmetic is published rather than netted off.

| netlist | cells | flip-flops | area um2 |
|---|---:|---:|---:|
| `s76-rom0-base`, CLKGATE = 0, the layout baseline | 45,622 | **5,874** | 685,381.4352 |
| `s76-rom0-gate`, CLKGATE = 1, the design | 45,763 | **5,871** | 691,131.9114 |
| `s76-base`, CLKGATE = 0, `ROM_HARDEN = 1` | 46,957 | **5,977** | 698,368.0032 |
| `s76-gate`, CLKGATE = 1, `ROM_HARDEN = 1` | 47,088 | **5,974** | 703,738.5894 |

**[fact, `syn_soc_top.sh 20`, four runs]**

**+2 built, −5 removed, net −3, and all seven are localised.** The two
built are `soc_npu`'s `wake_hold`, three bits wide in the RTL and two
flip-flops after mapping. The five removed are found by synthesising
`soc_npu` **hierarchically** with `pilot_top` black-boxed — the flat
netlist is anonymous and cannot answer this — and mapping every
flip-flop back to the RTL net its Q drives. **Every module but
`soc_npu`'s own body is identical between the two builds**, including
both `aer_fifo` instances, all three `soc_tmr_bank` replicas, every
`aer_ptr_bank` and `soc_npu_ser`:

| the flip-flop, by the net its Q drives | CLKGATE = 0 | CLKGATE = 1 |
|---|---:|---:|
| `ev_state` | **8** | **4** |
| `aer_stb_state` | **1** | **0** |
| one `abc` `flip_bits` cell | 1 | 1 (a different one) |
| `g_clkgate.wake_hold` | 0 | **2** |
| **`soc_npu`'s own total** | **219** | **216** |

**[fact]**

> **`ev_state` IS ONE FOUR-BIT REGISTER IN THE RTL AND THE UNGATED BUILD
> STORES IT TWICE.** `aer_stb_state` is a bare `ev_state == E_PIN_S`
> comparison, a wire in the source, and the ungated build materialises it
> as a register of its own. Both are **register duplication decisions by
> the mapper**, taken on cost grounds that the enable's extra fan-out
> changes; neither is a bit of state the design has or lacks. The proof
> that this is not a design change is section 6's: **5,195 signal paths
> compared at 415,345 clock edges with zero differences**, on two builds
> from one source tree.
>
> This document does not root-cause yosys's cost model further, and says
> so in section 10. What it does is name the flip-flops, so that the next
> reader of a census does not have to rediscover them.

### 9.3 And one guard had to be repaired, which made it stronger

`sw/tests/test_soc_synthesis_guards.py::test_the_aer_strobe_gate_is_in_the_netlist_and_costs_no_flip_flop`
is `docs/56` H5's census: the strobe gate is the one hardening in this
repository whose whole mechanism is combinational, so it adds no
flip-flop and no flip-flop count can see it. It asserted that **removing
the gate makes the netlist smaller in cells at the same flip-flop
count**.

**Measured on this design it inverted**: intact **3,367** cells, mutant
**3,406** — the mutant 39 cells **larger** **[fact]**. The mechanism is
section 9.2's: the mutation replaces `aer_in_stb && aer_stb_state` with
`aer_in_stb`, which is exactly the edit that changes whether the mapper
duplicates `ev_state` and materialises `aer_stb_state`. The intact and
mutated designs then differ by a register duplication as well as by the
gate, and **the sign of the cell delta is the mapper's decision rather
than the gate's cost.**

Setting `CLKGATE = 0` for the census did not fix it — intact 3,358,
mutant 3,377 **[fact]** — which is what said the effect is the mapper's
and not the enable's.

**The repair is to stop measuring a size and measure the structure.**
The guard now takes the **fan-in cone of the die's strobe pin**
`obs_aer_in_stb_o`, using `hw/soc/fi/gl_netlist.py`'s own walker — the
same one `docs/75` runs on the shipped netlist, imported rather than
reimplemented:

| build | flip-flops the strobe pin depends on |
|---|---|
| intact, `docs/76`'s RTL | `aer_in_stb`, **`ev_state`** |
| intact, `HEAD`'s RTL | `aer_in_stb`, **`aer_stb_state`** |
| the mutation the test builds | **`aer_in_stb` alone** |
| `wire aer_stb_state = 1'b1;` — a mutation the cell count did not catch | **`aer_in_stb` alone**, and the guard **FAILS** |

**[fact]**

The guard therefore asserts what H5 means — *the die's strobe depends on
more than the strobe flag* — and it is now insensitive to which of the
two forms the mapper leaves the comparison in. It passes on this
document's RTL and on `179dba2`'s, in a worktree, unchanged otherwise.

### 9.4 The layouts

Two LibreLane runs, `hw/soc/pnr/config-ecc.json`, the same floorplan,
the same PDK, the same tool binaries, the same machine, from two
netlists that differ by one `chparam`. `docs/71` established that this
flow is bit-reproducible run to run, so **every delta below is a delta
of netlists** and not of the tool.

**The configuration is identical and it is asserted rather than
assumed.** `hw/soc/pnr/config-ecc.json` (`md5 bae01711…`, the file
`docs/70` and `docs/71` used), and:

```
python3 -c "
import json
a=json.load(open('hw/soc/pnr/runs/s76base/resolved.json'))
b=json.load(open('hw/soc/pnr/runs/s76gate/resolved.json'))
print(sorted(k for k in set(a)|set(b) if a.get(k)!=b.get(k)))"
  []
```

**[fact]** — **not one key differs, `VERILOG_FILES` included.** The only
difference between the two runs is the netlist handed in through
`-i <state>`: `md5 ac75d0b3…` against `md5 b3b42bad…`.

| | `s76base` | **`s76gate`** | delta |
|---|---:|---:|---:|
| **`sg13g2_lgcp_1` in the layout** | **1** | **3** | **+2** |
| **clock-gate cell area, um2** | **27.216** | **81.648** | **+54.432**, exactly 2 x 27.216 |
| sequential cells | 5,874 | 5,871 | −3 |
| **clock buffers** | **757** | **651** | **−106** |
| **clock-buffer area, um2** | **20,577.1** | **18,164.0** | **−2,413.1** |
| clock inverters | 271 | 272 | +1 |
| timing-repair buffers | 12,216 | 12,616 | +400 |
| of those, hold | **3** | **53** | **+50** |
| of those, setup | 458 | 487 | +29 |
| standard cells, excluding fill | 61,603 | 62,036 | +433 |
| placed standard-cell area, um2 | 895,033 | 900,851 | +5,818 |
| **die area, um2** | **4,786,290** | **4,786,290** | **0** |
| utilisation | 0.724129 | 0.725470 | +0.0013 |
| routed wirelength, um | 4,281,703 | **4,573,457** | **+291,754, +6.8 %** |
| detailed-routing DRC | **0** | **0** | 0 |
| antenna nets / diodes | 3 / 589 | 1 / 546 | |
| **setup WNS, slow, ns** | **−4.5752** | **−6.3505** | **−1.7753** |
| **setup TNS, slow, ns** | **−7,205.49** | **−11,454.97** | **−4,249.48** |
| setup violating endpoints, slow | 3,055 | **3,131** | +76 |
| setup WNS, typ / fast, ns | +4.7620 / +9.8010 | +3.2377 / +9.0223 | −1.52 / −0.78 |
| hold WS, fast, ns | **−0.0123, 1 violation** | **+0.0013, 0** | +0.0136 |
| max slew, slow / typ / fast | 60 / 24 / 15 | 91 / 20 / 16 | |
| max cap, all three | 23 | 28 | +5 |
| max fanout | 549 | 505 | −44 |

**[fact, both `final/metrics.json` and `hw/openlane/signoff_report.py`]**

Four readings, and two of them are costs.

**THE CLOCK-GATE CELL AREA IS EXACTLY THREE CELLS.** `81.648 = 3 x
27.216` and `design__instance__count__class:clock_gate_cell` is 3, so
the layout's own metric agrees with the netlist grep and with the CTS
sink census. That is the census surviving to the die.

**AND THE CLOCK TREE GOT SMALLER, WHICH WAS NOT EXPECTED.** 106 fewer
clock buffers and 2,413 um2 less clock-buffer area, because
`clk_i_regs`'s average sink wire length falls from **1,572.53 um to
872.26 um** when 2,144 of its 3,551 sinks move onto two trees of their
own **[fact, `CTS-0101`]** — `clk_npu` at 1,465.36 um over 2,089 sinks
and `clk_bus` at **97.42 um over 55**, which is a tree that barely
leaves the cells it serves.

**THE FIRST COST IS SETUP AT THE SLOW CORNER**: −1.7753 ns of WNS,
−4,249 ns of TNS, 76 more violating endpoints. Section 9.5 is one of
them and the rest are the ordinary consequence of a different netlist on
a different placement. `docs/71`'s rule applies here too and this
document does not attribute the whole of it to the gates.

**THE SECOND IS 50 MORE HOLD BUFFERS AND 6.8 % MORE ROUTED WIRE.** The
hold buffers are the direct consequence of two new clock trees whose
insertion delays differ from `clk_i_regs`'s: worst-case clock skew rises
from 0.9583 to 0.9888 ns for setup and 0.9732 to 1.0601 for hold
**[fact]**. That is the "new hold risk at the enable" `docs/57`
section 16 named, and it is the one it named that the flow absorbed on
its own — hold closes at all three corners in the gated run, and the
UNGATED one is the one with a hold violation.


### 9.5 The clock-gating check, and neither enable closes it at the slow corner

**This is the finding of the cost section and it is a negative one.**

An `sg13g2_lgcp_1` declares `clock_gating_integrated_cell` in its
Liberty, so OpenSTA derives a setup check on `GATE` against `CLK`'s
rising edge with no constraint written by hand. Section 5.1 says why
that is a **full-cycle** path. Measured on `s76gate`, at the slow corner:

| gate | check | slow | typ | fast |
|---|---|---:|---:|---:|
| `g_clkgate.u_bus_cg.u_icg` | post-GRT (`37-openroad-stamidpnr-3`) | **+0.7197 MET** | — | — |
| `g_clkgate.u_bus_cg.u_icg` | **sign-off** (`49-openroad-stapostpnr`) | **−0.7495 VIOLATED** | — | — |
| `g_clkgate.u_npu_cg.u_icg` | post-GRT | **−3.9624 VIOLATED** | — | — |
| **`g_clkgate.u_npu_cg.u_icg`** | **sign-off** | **−5.0198 VIOLATED** | **+4.1210 MET** | **+9.5364 MET** |

**[fact, `violator_list.rpt` and `max.rpt` of the two STA steps; ns]**

**Both gates miss at the slow corner and both make it at typical and
fast.** The fabric's makes it at the post-GRT STA and loses 1.47 ns to
routing and the final resizer; the accelerator's misses at both. Two
entries of `s76gate`'s **3,131** violating setup endpoints at that corner
are these:

```
[setup reg-reg] _81736_/Q -> g_clkgate.u_npu_cg.u_icg/GATE : -5.019787
[setup reg-reg] _81736_/Q -> g_clkgate.u_bus_cg.u_icg/GATE : -0.749507
```

**[fact]** — and they launch from the **same flip-flop**, which is what
a shared term in the two enables looks like after `abc`: the fabric's
`mi_req_i | md_req_i` and the accelerator's `req_i` are both fed from
Ibex's request path.


> **NEITHER CLOSES AT THE SLOW CORNER, AND THE ACCELERATOR'S MISSES BY
> SEVEN TIMES AS MUCH.** The reason it misses by so much is the term
> that makes its gate safe.
> `npu_act` carries `|sticky_ev` — all eleven cause lines — so that an
> upset inside a sleeping block wakes it up rather than going unrecorded
> (section 3.2). Several of those lines are themselves deep: `q_det_ev`
> is the two queues' entry-parity and read-valid votes, `prot_mismatch`
> is a 25-bit majority voter's disagreement output, `win_orphan` and the
> three expiries are FSM-state comparisons. **The term that exists for
> fault observability is the term that costs the timing.**
>
> **The fabric's enable is five signals ORed together and it misses by
> 0.75 ns**, which is a buffering distance rather than a structural
> problem: it MET the check by +0.72 ns before detailed routing and the
> final resizer, so what it lost is wire. The accelerator's is
> structural.

**What this does and does not mean.** They are 2 of **3,131** violating
setup endpoints at a corner where the ungated design already fails on
**3,055** (section 9.4), so they are not a new failing corner and neither
is the worst path — `s76gate`'s WNS is −6.3505 and the worse of these is
−5.0198. But a violated setup check at a clock gate is not
an ordinary violated setup check: the consequence of the enable arriving
late is a **glitch on a clock net**, not a wrong data bit, and this
document does not measure how wide such a glitch would be —
`docs/75` section 14 item 1 already records that this project has no
instrument for that question.

**The repair is named and not taken, and section 14 ranks it first.**
`|sticky_ev` does not have to be in the combinational enable at all. A
fault event may set a **sticky wake request in the UNGATED domain** —
one flip-flop on `clk_i_regs`, cleared when the accelerator has been
awake long enough to record what happened — which takes the whole
eleven-line cone off the enable's path at the cost of **one cycle of
wake latency on a fault and one flip-flop**. One cycle is the right
price there: what the fault needs is for the block to be clocked in
order to record it, and one cycle late is recorded.

---

## 10. What this does NOT cover

- **NO SILICON, AND NO SIGN-OFF POWER ANALYSIS.** Everything in section 8
  is `report_power` on a Liberty model, with no glitch power (the dump is
  a zero-delay RTL simulation), no temperature feedback, no IR drop and
  no package. `docs/57` section 13's list applies here unchanged.
- **THE BUSY-WINDOW POWER FIGURE IS NOT ATTRIBUTED, AND SECTION 8.5 IS
  WHY.** `s76gate` computing measures 11.840 mW MORE than `s76base`, the
  whole of it in the Combinational group, on a layout that routes 6.8 %
  more wire — while the same two designs at synthesis go the other way
  by 19.9 mW. One pair of runs cannot separate a netlist-and-placement
  effect from the gates, and this document does not try. **The idle
  figure is claimed and the busy figure is reported.**
- **NEITHER LAYOUT IS SIGNED OFF.** Both fail setup at the slow corner
  and max slew and max cap at three, and neither has been through Magic
  DRC, KLayout DRC or Netgen LVS, because the one available SRAM macro
  fails all three inside the vendor views (`docs/12` sections 7.5 and 8,
  `docs/54`). `RUN_MAGIC_DRC`, `RUN_KLAYOUT_DRC`, `RUN_KLAYOUT_XOR` and
  `RUN_LVS` are all 0.
- **THE ACCELERATOR'S ENABLE IS NOT PROVED, IT IS MEASURED.** F10 is a
  theorem about `soc_bus` and about nothing else. For `soc_npu` the
  statement is section 6's: two builds, one source tree, **5,137 paths,
  415,345 cycles, zero differences**. **That is a statement about the workloads measured**, and
  the workloads measured are `docs/51`'s self-test and `docs/46`'s
  supervisor. A program that drives the die into a state neither of them
  reaches is not covered, and `wake_hold` is the margin that exists
  because of it. **In particular the accelerator's own gate is never
  observed closing and re-opening under a sustained event stream**: the
  supervisor never touches it, and the self-test's inference is one
  burst.
- **NO FAULT IS INJECTED ANYWHERE IN THIS DOCUMENT.** In particular, an
  upset in a flip-flop whose clock is stopped is not modelled. The
  reasoning of section 3.2 says the enable wakes on `|sticky_ev` so that
  a *detected* fault is recorded; nothing here measures what a gated
  domain does to the *rate* at which faults are detected, and a
  gate-level campaign on `s76gate` would be the instrument for it.
- **THE GATE'S OWN TIMING IS CHECKED ONLY BY THE FLOW'S OWN STA, AND ONE
  OF THE TWO CHECKS FAILS.** Section 9.5. No `set_clock_gating_check` is
  written and none is needed — the cell's Liberty declares
  `clock_gating_integrated_cell` and OpenSTA derives the check from it —
  but the check that results is a full-cycle setup path and the
  accelerator's enable misses it at the slow corner. **Nothing in this
  document measures what that would do in silicon**; a violated setup
  check on a clock gate's enable is a possible glitch on a clock net,
  and the width of a physical glitch is exactly the number `docs/75`
  section 14 item 1 already says this project cannot ask for.
- **NO SCAN, NO DFT, NO TEST MODE.** Both gates take `test_en_i(1'b0)`,
  exactly as `soc_top.v` gives Ibex `test_en_i(1'b0)`. A scan chain would
  need those tied to a test-enable pin and there is none.
- **ONE GEOMETRY, ONE CONFIGURATION, ONE CLOCK PERIOD.** 20 ns, the
  `config-ecc.json` floorplan, `ROM_HARDEN = 0` for the layouts and the
  design's own default for the equivalence runs. **The two layouts ran
  CONCURRENTLY on the same 20 threads**, which affects nothing in the
  result — `docs/71` measured that this flow's output does not depend on
  thread count — and everything in section 11's wall times.
- **THE POWER IS ONE WORKLOAD'S, AND IT IS A WORKLOAD THAT NEVER TOUCHES
  THE ACCELERATOR.** `docs/46`'s supervisor is the only program in this
  repository with a duty cycle, which is why `docs/57` chose it and why
  this document does; it is also why the accelerator's gate is shut for
  99.96 % of it. **The energy of an inference with the accelerator's
  clock gated is not measured here** and section 14 item 7 is what would
  measure it.
- **THE FLIP-FLOP COUNT MOVES BY 3 AND THE MECHANISM IS NAMED BUT NOT
  ROOT-CAUSED FURTHER.** Section 9.2 localises it to a register
  duplication yosys performs in the ungated build and not in the gated
  one; it does not explain the mapper's cost model, and the evidence that
  it is not a design change is section 6's equivalence and not an
  argument about yosys.

---

## 11. Reproducing this

The toolchain is the repository's, resolved through `tools.mk` rather
than off `PATH`; `VVP` below is
`$HOME/Downloads/oss-cad-suite-linux-x64-20260804/oss-cad-suite/bin/vvp`
and `sby` and `yosys` come from the same checkout.

```bash
# 0. the instruments, before anything is claimed to move
mkdir -p hw/soc/out/pwr-inst
hw/soc/flow/power_soc_top.sh report hw/soc/out/pwr-inst default
#   27.7743 / 34.8347 / 46.0951 mW on full3, docs/47 section 9

# 1. the formal proof, and the five mutations
cd hw/soc/formal && make bus && cd -
#   bmc PASS, prove PASS by k-induction, cover PASS 20 of 20
#   the mutants are soc_bus.v with one term of clk_en_o deleted, built
#   in a scratch directory with a three-line .sby that reads
#   soc_bus.v, soc_memmap.vh and soc_bus_props.v and runs `bmc`.

# 2. the cocotb suite, and the two mutations it catches
cd hw/soc/tb/cocotb && make -f Makefile.soc_bus && cd -
sed "s/assign clk_en_o = .*/assign clk_en_o = 1'b1;/" hw/soc/rtl/soc_bus.v > /tmp/mut_bus.v
cd hw/soc/tb/cocotb && make -f Makefile.soc_bus SOC_BUS_SRC=/tmp/mut_bus.v \
    SIM_BUILD=sim_build_mut76 COCOTB_RESULTS_FILE=results_mut76.xml

# 3. the two whole-SoC builds, one source tree, one parameter apart
SOC_VVP_ARGS=+vcd hw/soc/flow/sim_soc.sh $PWD/hw/soc/out/h76-g2
mv tb_soc.vcd hw/soc/out/h76-g2/            # tb_soc.v dumps to the cwd
SOC_CLKGATE=0 SOC_VVP_ARGS=+vcd hw/soc/flow/sim_soc.sh $PWD/hw/soc/out/h76-b2
mv tb_soc.vcd hw/soc/out/h76-b2/
#   220,256 / 415,324 / 28 of 28 / mask 0 / 0x00030000 / 1,135 / 0, both

# 4. every signal, at every edge  (about 35 min on 2.7 GB x 2)
#    With no --exclude this reports the three paths the change creates;
#    excluding them is what makes the result an explicit zero. The two
#    gated clock nets are reached by their SHORTEST alias, which is
#    tb_soc.dut.clk_bus and tb_soc.dut.clk_npu and not u_bus.clk_i.
python3 hw/soc/flow/clkgate_check.py equiv \
    hw/soc/out/h76-b2/tb_soc.vcd hw/soc/out/h76-g2/tb_soc.vcd \
    --clock tb_soc.dut.clk_i --scope tb_soc.dut \
    --exclude tb_soc.dut.clk_bus --exclude tb_soc.dut.clk_npu \
    --exclude tb_soc.dut.npu_clk_en

# 5. how often the gates close  (about 30 s on the same dump)
python3 hw/soc/flow/clkgate_check.py duty hw/soc/out/h76-g2/tb_soc.vcd \
    --clock tb_soc.dut.clk_i \
    --enable tb_soc.dut.bus_clk_en --enable tb_soc.dut.npu_clk_en

# 6. the supervisor, at the LAYOUT'S configuration, for the power
FI_WORKLOAD=supervisor SOC_ROM_HARDEN=0 \
    hw/soc/flow/fi_core.sh $PWD/hw/soc/out/h76-sup-r0b
(cd hw/soc/out/h76-sup-r0b && $VVP -n tb_soc_fi.vvp +armed=0 +vcd)
#   sig = 216f8ce6, window 9,376..67,296
python3 hw/soc/flow/clkgate_check.py duty \
    hw/soc/out/h76-sup-r0b/tb_soc_fi.vcd --clock tb_soc_fi.dut.clk_i \
    --enable tb_soc_fi.dut.bus_clk_en --enable tb_soc_fi.dut.npu_clk_en \
    --window tb_soc_fi.dut.core_sleep_o=1

# 7. the activity, and the two annotations that differ by two pins
hw/soc/flow/power_soc_top.sh extract \
    hw/soc/out/h76-sup-r0b/tb_soc_fi.vcd tb_soc_fi hw/soc/out/pwr-sup
#   all 69,106 / busy 29,302 / idle 39,804  -- docs/57 section 5.2
for w in busy idle; do
  hw/soc/flow/power_soc_top.sh annotate hw/soc/out/pwr-sup $w tb_soc_fi
  cp hw/soc/out/pwr-sup/act.$w.tcl hw/soc/out/pwr-gate/act.$w.tcl
  PWR_GATES=ibex hw/soc/flow/power_soc_top.sh annotate hw/soc/out/pwr-sup $w tb_soc_fi
  cp hw/soc/out/pwr-sup/act.$w.tcl hw/soc/out/pwr-base/act.$w.tcl
done
diff hw/soc/out/pwr-base/act.busy.tcl hw/soc/out/pwr-gate/act.busy.tcl
#   exactly two lines: the two new gates' GATE pins

# 8. the four syntheses
SOC_MEM=sram                  hw/soc/flow/syn_soc_top.sh 20 $PWD/hw/soc/out/s76-gate
SOC_MEM=sram SOC_CLKGATE=0    hw/soc/flow/syn_soc_top.sh 20 $PWD/hw/soc/out/s76-base
SOC_MEM=sram SOC_ROM_HARDEN=0 hw/soc/flow/syn_soc_top.sh 20 $PWD/hw/soc/out/s76-rom0-gate
SOC_MEM=sram SOC_ROM_HARDEN=0 SOC_CLKGATE=0 \
                              hw/soc/flow/syn_soc_top.sh 20 $PWD/hw/soc/out/s76-rom0-base
grep -c sg13g2_lgcp_1 hw/soc/out/s76-rom0-{base,gate}/soc_top.netlist.v   # 1 and 3

# 9. the two layouts, docs/70 section 14 step 2's form with the tag changed
for t in gate base; do
  SYN_NETLIST=$PWD/hw/soc/out/s76-rom0-$t/soc_top.netlist.v \
  PNR_CONFIG=$PWD/hw/soc/pnr/config-ecc.json \
  PNR_STATE=$PWD/hw/soc/pnr/state/s76$t.state.json \
  hw/soc/flow/pnr_soc_top.sh s76$t --overwrite -F Yosys.JsonHeader \
      -S Yosys.Synthesis -S Checker.YosysUnmappedCells \
      -S Checker.YosysSynthChecks -S Checker.NetlistAssignStatements \
      -i $PWD/hw/soc/pnr/state/s76$t.state.json
done
grep -hE "CTS-001[01]" hw/soc/pnr/runs/s76{base,gate}/2*-openroad-cts/*.log

# 10. the power, on the two layouts, three corners each
for t in base gate; do
  for w in busy idle; do
    PWR_RUN=$PWD/hw/soc/pnr/runs/s76$t \
      hw/soc/flow/power_soc_top.sh report hw/soc/out/pwr-$t $w
  done
done

# 11. the censuses and the suites
python3 hw/soc/fi/gl_netlist.py <netlist> --tmr-census npu   # wdog, boot
.venv/bin/python -m pytest sw/tests -q
scripts/run_cocotb.sh
cd hw/soc/formal && make
```

**Cost, quoted with the configuration it was measured in**, on a shared
20-thread host that was running **two place-and-route flows, a formal
gate and a cocotb suite concurrently for most of the session**, and one
sibling project's work throughout. **[fact for the figures; the wall
times are costs and not benchmarks]**

| | |
|---|---:|
| `soc_bus` formal, all three tasks | **20.4 s** |
| the five formal mutations, `bmc` each | about **15 s** each |
| the cocotb `soc_bus` suite, 16 tests | **0.54 s** of simulated work |
| one whole-SoC run with `+vcd` | about **5 min**, **2.7 GB** |
| `clkgate_check.py equiv`, 5,195 paths over 2.7 GB x 2 | about **35 min** |
| `clkgate_check.py duty`, one 2.7 GB dump | **30 s** |
| the supervisor with `+vcd` | about **2 min**, **228 MB** |
| `vcd_activity.py` on the supervisor's dump | **1 min 4 s** |
| one `syn_soc_top.sh` | about **1 min** |
| one `report_power` with SPEF, one corner | about **90 s**, and the matrix is 18 of them |
| **the two layouts**, 58 and 59 timed steps | **167.8 min** and **172.6 min** of step time, of which detailed routing is **70.0** and **60.4** — run CONCURRENTLY on the same 20 threads, so neither is a benchmark of anything |

---

## 12. Files touched

| file | change |
|---|---|
| `docs/76-the-second-and-third-clock-gates.md` | this document |
| `docs/00-index.md` | one row |
| `hw/soc/rtl/soc_bus.v` | `clk_en_o`, the five-term enable, and the header section that states G1 to G5 and why the gate is not in this file |
| `hw/soc/rtl/soc_npu.v` | `CLKGATE`, `HOLD_CYCLES`, `clk_en_o`, `npu_act`, the `wake_hold` counter, and the section that states why it is one domain and why `\|sticky_ev` is in the enable |
| `hw/soc/rtl/soc_top.v` | `CLKGATE`, the two `prim_clock_gating` instances, the ungated arm, and the block comment listing what is gated and what is not |
| `hw/soc/formal/soc_bus_props.v` | **F10** and the three G covers |
| `hw/soc/flow/clkgate_check.py` | new: the two-dump equivalence and the gate-duty instrument |
| `hw/soc/flow/power_soc_top.sh` | `PWR_MEM` for `docs/67`'s memory topology, `PWR_GATES` for which gates the target netlist has, `PWR_EXCL_NPU` split out of it |
| `hw/soc/flow/power_report.tcl` | the RAM's `g_ram_2048x64_ecc` spelling added to the per-macro list beside the old one, and `get_cells -quiet` so an absent name is skipped rather than warned about. Since `docs/67` that list had matched nothing on any new netlist |
| `hw/soc/flow/syn_soc_top.sh` | `SOC_CLKGATE`, and the knob printed in the summary line |
| `hw/soc/flow/sim_soc.sh` | `SOC_CLKGATE` |
| `hw/soc/flow/fi_core.sh` | `SOC_CLKGATE` |
| `hw/soc/tb/cocotb/test_soc_bus.py` | two tests, section 4.5 |
| `sw/tests/test_soc_clkgate_guards.py` | new: eleven guards, section 9 and the mutation evidence |
| `sw/tests/test_soc_synthesis_guards.py` | the AER strobe guard repaired from a cell count to a fan-in cone census, section 9.3 |

**No file under `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/`
was written** **[fact, `git status`]**.

Build products, all gitignored (`docs/38` section 11's rule):

| directory | what is in it |
|---|---|
| `hw/soc/out/s76-base`, `s76-gate` | the two syntheses at `ROM_HARDEN = 1` |
| `hw/soc/out/s76-rom0-base`, `s76-rom0-gate` | the two the layouts were made from |
| `hw/soc/pnr/runs/s76base`, `s76gate` | the two layouts, and `hw/soc/out/s76-pnr-{base,gate}.log` |
| `hw/soc/out/h76-base`, `h76-gate` | the first whole-SoC pair: `HEAD`'s design against the gated one, with comparison A' in `h76-gate/equiv-whole.txt` |
| `hw/soc/out/h76-b2`, `h76-g2` | the second pair, one source tree and one parameter apart, with comparisons B and B' in `h76-g2/equiv-whole.txt` and `h76-g2/equiv-design.txt` |
| `hw/soc/out/h76-sup-base`, `h76-sup-gate` | the supervisor pair at the shipped `ROM_HARDEN` |
| `hw/soc/out/h76-sup-r0`, `h76-sup-r0b` | the supervisor at the layout's `ROM_HARDEN = 0`, which the power annotation is taken from |
| `hw/soc/out/pwr-sup` | the activity JSON and the four annotation scripts |
| `hw/soc/out/pwr-base`, `pwr-gate`, `pwr-inst` | the `report_power` outputs: eighteen on the two layouts, six on the two synthesis netlists, three reproducing `docs/47` on `full3` |

### 12.1 The suites, re-run

This work modified RTL that every SoC suite elaborates, so none of the
three is optional and all three were run to completion **[fact]**.

| suite | result | what it was |
|---|---|---|
| `.venv/bin/python -m pytest sw/tests -q` | **484 passed, 0 failed** — 4 m 18 s on a quiet machine and 22 m 53 s with two place-and-route flows running | `docs/75` reports **472**. The twelve added are `sw/tests/test_soc_clkgate_guards.py`'s eleven and the one `test_doc_links.py` discovers for this document |
| `scripts/run_cocotb.sh` | **398 passed, 0 failed, 0 suites not clean** | `docs/75` reports **396**; `soc_bus` goes from 14 tests to 16 |
| `cd hw/soc/formal && make` | **14 jobs, 58 tasks, 58 PASS, 0 FAIL** | the count `docs/69` established and `docs/75` re-ran. F10 and the three G covers are new statements inside existing tasks, not new tasks |

---

## 13. Corrections to earlier documents

1. **`docs/57` section 16's "the enable for a peripheral domain is
   `core_sleep_o` and `!s_req` and the absence of a pending response"
   is not what was built, and should not be.** An enable that reads the
   core's sleep state is a statement about the core: it cannot be proved
   complete inside the block it gates, and it is wrong the first time a
   slave has work to do with the core asleep — which is what a
   wake-on-event path is, and which is the whole of `docs/05` section
   3.4 profile 1. Both enables here read their own block and nothing
   else, and `sw/tests/test_soc_clkgate_guards.py` enforces it.
   Sections 3.1 and 4.
2. **`docs/57` section 16's framing of the price — "that is a formal
   re-proof, not a gate" — is right about the size and wrong about the
   shape.** It is not a re-proof of F9; it is one added property that
   makes F9's proof transport. Section 4.
3. **`docs/61` section 7.3's "every one of the 2,178 new flip-flops is on
   the ungated net" and section 11's "the accelerator is the largest
   single consumer of idle power" are both superseded.** 2,089 of them
   are on `clk_npu`, which is stopped for 96.6 % of the whole-SoC
   self-test. Sections 1 and 7.
4. **`docs/57` section 7.3's per-block idle table is superseded for four
   of its rows.** `u_clint` 52.43 % becomes **53.75 %**, `u_timer0`
   24.59 % becomes **15.38 %**, `u_uart0` 22.96 % becomes **14.36 %**,
   and **`u_ram` 0.00 % becomes 16.46 %** — the last is `docs/67`'s
   scrubber and not a change in the memories' traffic. Section 3.3.
5. **`docs/57` section 7.3's "those 237 could lose their clock while the
   231 kept theirs" is right in principle and wrong in its arithmetic
   for this design.** The design has grown: the population outside the
   core is 1,404 ungated flip-flops after these two gates, not 468, and
   the 231 free-running counter bits are now three blocks and a memory
   scrubber. Section 3.
6. **`docs/60-soc-datasheet.md` section 1's "what is deliberately
   absent" and section 4.3's "it has one clock and one mode" were
   corrected once by `docs/57` item 10 and need correcting again.**
   There are **three** integrated clock gates covering **76.0 %** of the
   design's flip-flops, in three domains with three different enables.
   Section 1.
7. **`sw/tests/test_soc_synthesis_guards.py`'s AER strobe guard was a
   cell-count inequality and could invert.** It is now a fan-in cone
   census. Section 9.3. Not an error in `docs/56`, which the guard was
   written for; an instrument that measured the right thing by a proxy
   that stopped holding.
8. **`hw/soc/flow/power_report.tcl`'s per-macro list has matched nothing
   since `docs/67`.** It names `u_ram.g_ram_2048x64.u_b0` through
   `u_b3`, and `docs/67` renamed the RAM's generate arm to
   `g_ram_2048x64_ecc` when it put the codec underneath. `get_cells` on
   an absent instance is a **warning and not an error**, and the script
   skipped the row afterwards, so every `report_power` run on a netlist
   built since that document has silently reported two macro rows
   instead of six. No published figure is wrong — the TOTAL line does
   not depend on that loop — but four rows that should have existed did
   not. Both spellings are now in the list and the lookup is `-quiet`.
   Section 12.

---

## 14. What the next block should be

1. **Take `|sticky_ev` off the accelerator's enable path.** Section 9.5:
   the accelerator's clock-gating check misses by 3.96 ns at the slow
   corner, and the cone that costs it is the eleven fault lines that are
   there for observability. One flip-flop in the ungated domain, set by
   `|sticky_ev` and cleared when the accelerator has been clocked,
   removes the whole cone from the path for one cycle of wake latency on
   a fault. **It is the only item here that is a defect and not an
   experiment.**
2. **A gate-level fault-injection campaign on `s76gate`, into the gated
   domains.** This document's whole argument for `|sticky_ev` in the
   accelerator's enable is that a sleeping block must still report an
   upset, and **nothing here injects one**. `docs/74`'s and `docs/75`'s
   machinery already runs on a LibreLane netlist; the arms are the two
   layouts this document builds, and the question is whether the
   detected-fault rate moves. It is the one item that could falsify
   section 3.2.
3. **`SCRUB_IVL_RST` against idle power.** Section 3.4 measures the RAM
   scrubber at **16.46 % of idle switching**, which nothing in the corpus
   knew. The interval is a register and a reset parameter, the trade is
   scrub rate against idle current, and `docs/67` owns the first half of
   that argument while `docs/05` section 3.4 profile 4 owns the second.
   One sweep, no RTL change.
4. **The CLINT's `TICK_DIV` as a prescaler.** Section 3.3: the time base
   cannot be gated but it can be slowed, and at `TICK_DIV = N` the 72
   flip-flops of `mtime` and its codeword need a clock once in N cycles.
   What it costs is the cycle-accurate `mtime` the bring-up program
   computes deadlines from, so it is a mission decision and not a
   hardening one.
5. **The fourth gate: `u_apb` and `u_pnp`.** Both have completeness
   arguments as short as the fabric's — `req_i || state != IDLE ||
   rvalid_o` for the bridge — and `soc_apb_bridge` already carries a
   property set F10 could be added to. `soc_pnp` needs one RTL change
   first: it reloads `rdata_o` from the broadcast address on every cycle
   whether or not it was addressed, so its enable is either a 32-bit
   comparator or a `req_i` qualification on that register.
6. **`.A_REN(req_i && !do_write)`**, still. `docs/57` section 8.3's six
   AND gates and 0.147 mW, `docs/61` section 18 item 9, unbuilt in both.
   It is not a project and it should not keep waiting for one.
7. **The whole-SoC program's activity, against these netlists.** Section
   8 measures busy and idle on `docs/46`'s supervisor, which never
   touches the accelerator. The energy of an inference **with the
   accelerator in the netlist and its clock gated** is a number this
   project has never had, and `docs/57` section 10.3 is why the one it
   published had to be withdrawn. It needs a `ROM_HARDEN = 0` whole-SoC
   build and one 2.7 GB dump through `vcd_activity.py`.
