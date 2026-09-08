# 74 — The core at gate level: docs/42 and docs/43 replayed on the sign-off netlist, record for record

`docs/42-core-fault-injection.md` section 4.4 closed with a sentence
that every hardening wave since has left standing:

> `hw/soc/` has no gate-level simulation flow at all, `docs/38`
> synthesised `ibex_top` standalone and never simulated the netlist,
> and the SoC has never been synthesised as one design. It is named in
> section 10 as an open item and not claimed.

`docs/43` section 9.4 then measured the first thing a gate-level
campaign would see and an RTL campaign cannot: **31 fewer check
flip-flops in the netlist than in the RTL**, because the eighth check
bit of the shortened code is identically zero and the optimiser
deletes its storage. `docs/47`, `docs/62`, `docs/70` and `docs/71` each
repeated, in their lists of what they do not cover, that no gate-level
simulation of `soc_top` exists. This document is that simulation, and
the campaign that runs on it: **the 1,400 injections of `docs/43`'s
campaign of record, replayed one for one on the netlist of the sign-off
layout**, on the flip-flop the trace of both designs identifies as the
twin of each RTL bit, at the same cycle, classified by the same
classifier against a gate-level clean run, and compared with the RTL
record for record — `docs/32` section 5's standard, which on the
pilot's NPU gave 370 of 370.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
intended, with nothing behind it yet.

**The pilot is untouched.** `docs/34-pilot-freeze.md` pins the TTIHP26b
submission by hash and the shuttle closes 2026-09-21. Nothing in
`hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is modified and
`hw/tb/Makefile.fi` was not invoked; `hw/rtl/secded_dec.v` is **read**
by the gate-level bench's shadow decoder exactly as the register file
reads it. **No RTL under `hw/soc/rtl/` is modified either.** Section
15 lists every file.

**One netlist, stated by path and digest.**
`hw/soc/pnr/runs/s71boot/final/nl/soc_top.nl.v`, `md5
2e43d08ff422be8ce7a0efd17b1cc3da`, 10,831,575 bytes — the final netlist
of the layout `docs/71` proved bit-reproducible, which `docs/72` and
`docs/73` then read and did not write. Section 2 says what choosing it
over the synthesis netlist costs, which is nothing that this campaign
can measure.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| How many injections? | **1,424 gate-level injections in 1,739 simulations**: 1,175 of `docs/43`'s 1,400 records replayed with the watchdog held off, 315 of them armed as well, 174 into the watchdog's three replica banks, and 75 into flip-flops the netlist has and the RTL site table does not **[fact]**. A first pass of 450 records was discarded for the reason section 5.2a gives, and the register file's 180 records were re-run once more on a repaired instrument, section 9.3 |
| How many comparable? | **1,175 of 1,400** — an RTL record whose site bit has a netlist twin, identified by trace, by the elaborated design's own alias names, or both, replayed at the measured instant. **46 of the 1,175 are injections into a flip-flop synthesis made the twin of two RTL registers at once**, so the like-for-like set is **1,129**; 225 records have no twin. Sections 6 and 9 |
| How many identical? | **1,158 of 1,175** classify identically with the watchdog held off — **1,126 of the 1,129 like-for-like** — and **313 of 315** armed **[fact]**. Section 9 |
| The disagreements | **17**, and they are two structures: **15 are injections into the instruction register `opt_merge` stored once for two RTL copies** (eleven MASKED become DETECTED, and one each MASKED→SDC, MASKED→HANG, DETECTED→HANG, SDC→DETECTED — the netlist worse every time), and **2 are the multiplier's re-encoded state** (SDC at RTL, DETECTED on the netlist). Section 9.3 |
| Did the RTL itself move? | The same 1,400 records replayed on the HEAD RTL — the SoC of `docs/44` to `docs/73` around a core no wave since `docs/43` has touched — came back **0 changed of 1,400** against `docs/43`'s log, histogram for histogram and record for record **[fact]**. Section 8.1 |
| What does the netlist have that the RTL does not, and the reverse? | **2,319 of the RTL site table's 2,451 bits have a netlist twin and 132 do not**: 17 removed by synthesis, 4 re-encoded state bits with no twin at all, 1 whose alias-named flop turned out to be a re-encoded register, 8 ambiguous, 4 identified by too weak a trace, and 98 that never change in the clean run and whose name did not survive. **60 more are stored in ONE flip-flop for two RTL registers.** Under `u_ibex.` the netlist has **2,313 named flip-flops, 2,288 of them some RTL bit's twin and 25 not** — the re-encoded controller and divider state, and constants. Section 6 |
| What did the synthesised redundancy do? | **The register file corrected 171 of 180 upsets in the gates that will be manufactured — the RTL's 171, record for record, 0 SDC, 0 DETECTED, 0 uncorrectable — and the watchdog's three replica banks voted out 174 of 174.** Section 10. The watchdog's vote also **reset the SoC every time**, through a combinational decode into an asynchronous reset that the RTL cannot produce: section 10.2, the sharpest finding here |
| The name census that would have been wrong | Counted by name, the watchdog's protected word has **29, 14 and 15** replica flip-flops in the netlist and the boot block's **23, 11 and 12**; counted by the voter's fan-in cone, **29, 29, 29** and **23, 23, 23**. Half of each mixed replica stores an inverted image, `dfflibmap` builds it behind an inverter, and the flip-flop that results has no name. Section 6.6 |
| What is not covered | No single-event transient in combinational logic — the SECDED decoder is 528 cells and none of them is a site; no timing; one workload; one seed; the RAM zeroed at time zero. Section 12 |
| Wall | **14 h 03 m for the 1,327-simulation replay at 12 jobs**, 5 h 59 m for the RTL replay it is compared against, 2 m 19 s for the gate-level clean run against the RTL's 10.3 s — **13.5x on the clean run, 7.4x per replayed injection**. Every figure was measured beside the owner's place-and-route and two sibling projects and is contended. Section 14 |

---

## 2. The netlist, and why this one

### 2.1 Which file

| | |
|---|---|
| Path | `hw/soc/pnr/runs/s71boot/final/nl/soc_top.nl.v` |
| md5 | `2e43d08ff422be8ce7a0efd17b1cc3da` |
| Size | 10,831,575 bytes, one module, flattened |
| Sequential cells | **5,873**: 5,871 `sg13g2_dfrbpq_1`, 2 `sg13g2_dfrbpq_2`; no latch |
| Macros | 6: four `RM_IHPSG13_1P_2048x64_c2_bm_bist` (the RAM, `ROM_HARDEN = 0` build), two `RM_IHPSG13_1P_1024x32_c2_bm_bist` (the ROM) |
| Synthesised from | `hw/soc/out/s70-rom0-syn/soc_top.netlist.v`, `md5 a8d5ef81446ce6d2aa2eb4c1e0fdff79`, the netlist `docs/69` section 7.4 reports at 45,546 cells and 5,873 flip-flops and `docs/70` and `docs/71` placed |
| RTL | HEAD, `1378aed`, `SOC_MEM=sram SOC_ROM_HARDEN=0`, register file `secded`, fault port on |
| Cell models | `.../sg13g2_stdcell/verilog/sg13g2_stdcell.v`, `md5 ca98e34e6c582bfdc01eb1cd77a5d1db`, from the pinned PDK `c4b8b4e5…` |
| Macro models | `.../sg13g2_sram/verilog/RM_IHPSG13_1P_{2048x64,1024x32}_c2_bm_bist.v` and `RM_IHPSG13_1P_core_behavioral_bm_bist.v`, compiled `-DFUNCTIONAL` |
| Simulator | Icarus 13.0 at `~/.local/opt/iverilog13`, for the reason `docs/24` section 3 measured and `hw/tb/Makefile.gl` enforces: Icarus 12 leaves `sg13g2_dfrbpq_1`'s `delayed_CLK` undriven |

**[fact, `hw/soc/out/gl74/provenance.txt` and `hw/soc/fi/gl_netlist.py --census`]**

### 2.2 What the layout netlist costs against the synthesis netlist

The task allowed a synthesis netlist if the layout netlist's
timing-repair buffers made name mapping impractical. They do not, and
this is measured rather than assumed: both files were parsed with the
same parser, and

| | synthesis `a8d5ef81…` | layout `2e43d08f…` |
|---|---:|---:|
| flip-flops | 5,873 | 5,873 |
| flip-flop instance names | identical, in the same order | |
| flip-flop Q-net names | 5,823 identical | |
| Q-net names that differ | 50, all output-port flip-flops of `gpio_o`, `gpio_oe_o`, `qspi_io_oe_o` and `u_timer0.t_ie`, whose port net the layout drives through an inserted output buffer, so the flop's Q became `netNN` | |
| D-net names identical | 4,975 of 5,873 | |
| CLK-net names identical | 0 of 5,873 (the clock tree) | |

**[fact]**. The resizer and the clock tree changed what drives a
flip-flop and what it drives through; they changed which flip-flops
exist and what the Q net of every core flip-flop is called not at all.
So the object closest to silicon is also the one that costs nothing to
map, and it is the one used.

### 2.3 What that netlist is not

It is the netlist of a layout with `RUN_MAGIC_DRC`, `RUN_KLAYOUT_DRC`,
`RUN_KLAYOUT_XOR` and `RUN_LVS` all off (`docs/71` section 11), that
does not meet its timing constraint (`docs/70` section 6), and that
`Yosys.EQY` has never checked against the RTL. This document does not
change any of that. What it adds is the first behavioural evidence that
the netlist implements the RTL's function — section 5 — which is a
different and weaker thing than equivalence.

---

## 3. What was built

| File | What it is |
|---|---|
| `hw/soc/fi/gl_netlist.py` | Parses the netlist once: every sequential cell in file order, its instance and Q net; the Verilog the bench includes (a concatenation of every Q net, a force case and a release case over every flip-flop by index); a census by name against `targets.py`; fan-in cones, and the watchdog replica census by cone |
| `hw/soc/fi/gl_map.py` | Which netlist flip-flop is which RTL bit, derived from a per-cycle trace of both designs on the clean run and from the elaborated design's alias names; the RTL trace root it generates; the register-file shadow wiring it generates from the mapping |
| `hw/soc/fi/gl_campaign.py` | The gate-level campaign: controls, the replay of an RTL records file, the netlist-only sweep, the watchdog replica sweep, and the three-way reconciliation |
| `hw/soc/tb/tb_soc_fi_gl.v` | The instrument, `tb_soc_fi.v` pointed at the netlist: same clock, reset, pin ties, console receiver, termination rule, drain and RECORD keys; a force in place of a deposit; the macro arrays in place of `u_ram.mem` |
| `hw/soc/tb/fi_rf_shadow.v` | The register file's correction counters, recomputed by the bench from the netlist's own storage flip-flops with `hw/rtl/secded_dec.v` |
| `hw/soc/flow/fi_core_gl.sh` | Build and elaborate once, with provenance |
| `hw/soc/flow/fi_gl_alias.sh` | `fi_coverage.sh`'s elaboration written as JSON before anything renames, so that every name a net carried is known |

Modified, each by a few lines and each backward-compatible:
`hw/soc/flow/fi_core.sh` (a `SOC_ROM_HARDEN` knob, and `FI_EXTRA_SRC`
/ `FI_EXTRA_ROOT` for a second elaboration root); `hw/soc/tb/tb_soc_fi.v`
(the ROM check-bit deposit compiled out under `FI_ROM_PLAIN`, which
only that knob sets); `hw/soc/fi/campaign.py` (the directed replay runs
through the same pool as the campaign; it was serial). Section 15.

---

## 4. The bench, and what is different from the RTL instrument

`tb_soc_fi.v` is the instrument of `docs/42`, `docs/43`, `docs/46` and
`docs/67`; `tb_soc_fi_gl.v` is the same instrument with the design
under test replaced. Everything that could stay the same did. Four
things could not.

### 4.1 The upset is a force on the cell's output node, for one edge

An RTL deposit XORs a `reg` in place. There is no `reg` in a netlist:
every flip-flop is a cell whose Q drives a net, and `docs/24` section
4.3 measured that a deposit onto a driven net is a stuck-at. So the
upset is `docs/26` section 4's primitive, re-validated on the pilot's
sign-off netlist in `docs/32` section 4.1: a **force** from a quarter
cycle after one edge to a quarter cycle after the next, then a release.
During the window the fan-out cone sees the flipped value; at the edge
inside it the cell samples the D its own logic computed from that
value, so a register that holds captures the corruption and a register
that reloads does not; on release the net returns to the cell's own
drive. The record carries the value before the force, the value
**during** it — which is what proves the force took — and the value
after release, which is the design's decision and not the injector's.

One thing is different from the pilot's harness and it is a simulator
limit, not a modelling choice: `vvp` cannot force a bit-select of a
vector net, and every Q net of a multi-bit register is one. The force
therefore lands on `int_fwire_IQ` inside the cell — the scalar wire
between `sg13g2_dfrbpq_1`'s flip-flop primitive and its output buffer —
which is what drives Q and nothing else. Releasing it hands Q back to
the primitive exactly as releasing the net would.

Control 5 in section 7 is the measurement that this is the same fault
as the RTL deposit: the whole mapped flip-flop state after the
injection, cycle for cycle, on both sides.

### 4.2 The memories are the macro models' arrays

`soc_mem.v`'s register arrays are six SRAM macros here. The words
`tb_soc_fi.v` reads with `dut.u_ram.mem[i]` — the phase word, the exit
magic, the signature, the mask, the trap count — are read out of the
macro models' `memory` arrays, bank and row selected as
`soc_mem_sram.v` selects them (RAM: 8,192 rows of 64 bits,
`{check[31:0], data[31:0]}`, bank = word[12:11]; ROM: 2,048 rows of 32
bits, bank = word[10]). The boot ROM is loaded into its two macros at
time zero from the same `fi_workload.hex` the RTL bench loads, at the
same word offset (32, the reset vector).

**The RAM macros are zeroed at time zero, data and check field.**
`soc_mem.v` zeroes its array and says why ("a fetch from uninitialised
memory should decode as an illegal instruction and trap, not propagate
x"); the silicon's RAM powers up undefined, `docs/68` section 4 built
the loader's sweep for exactly that reason, and this bench models the
RTL's initial condition and not the silicon's, because the comparison
it serves is with the RTL. An all-zero row is a valid codeword. What
the run does with the macros left undefined was measured once and is
section 5.3.

### 4.3 What the netlist does not carry, and what stands in

Three things the RTL bench reads by hierarchical name are not in the
netlist by any name.

- **The watchdog's kick request, its early-kick and budget flags, and
  its programmed reload.** Internal nets whose names did not survive.
  The kick statistics are reported as `-1`; the timeout the campaign
  derives its budget from is the RTL clean run's reload and prescale
  (127 and 16, a 2,048-clock timeout, a 4,096-clock ladder), passed in
  as plusargs and recorded in every RECORD as such. Neither the early
  nor the budget flag enters any classification (`campaign.py`
  classifies on pins and published words), so nothing is lost that a
  class rests on.
- **The register file's correction counters.** `docs/43` section 6.5:
  they drive no port, `opt_clean` deletes them, and in silicon a
  corrected upset is indistinguishable from no upset. The gate-level
  CORRECTED class needs them, so the bench recomputes them:
  `fi_rf_shadow.v` reads the 31 registers' 32 data and 7 check
  flip-flops, the scrub pointer and the two read addresses — all of
  which **are** flip-flops in the netlist, wired by the mapping section
  6 derives, with the storage polarity it found — and runs
  `hw/rtl/secded_dec.v` three times as the register file does, counting
  cycles with a correctable syndrome exactly as `ibex_regfile_secded.v`
  counts them. It is a bench instrument and not an operator channel,
  which is precisely what the RTL counters were.
- **The watchdog's voter.** For section 10.2 the bench also reads the
  three replica images as the voter sees them — replica A's flip-flops
  directly (`POL_A = 0`, `MIX = 0`), and the netlist's own `qb` and `qc`
  nets — votes them, counts the cycles on which a replica disagrees
  with the vote, and reads the voted word's W6 report, `tmr_err` and
  `tmr_count`, which in silicon is `WDOGSTAT` over the bus.

### 4.4 What is the same

The clock and its period, the twenty-cycle reset, the pin ties (`strap_i
= 0`, GPIO inputs low, QSPI lanes pulled up, `wdog_dis_i` from the
armed plusarg), the console receiver, the termination rule (`core_sleep_o`
high after having been low, with the exit magic in RAM), the
twenty-four-bit-time drain, the RECORD keys, and the classifier: every
gate-level record is classified by `hw/soc/fi/campaign.py`'s own
`classify`, unchanged, against a gate-level clean run.

---

## 5. The clean run at both levels, and the one clock between them

### 5.1 The same answer

| | RTL, HEAD, `ROM_HARDEN = 0`, Icarus 12 | gate level, Icarus 13 |
|---|---|---|
| completes | yes, 18,682 cycles | yes, **18,681** |
| signature, mask, rounds | `9c07ef12`, `00000000`, 4 | identical |
| exit, magic | `00000000`, `600dc0de` | identical |
| console | 19 characters, hash `6d6942c8`, 0 framing errors | identical |
| slept at the end | yes | yes |
| announcements | none: no watchdog stage, no trap, no alert | none |
| measured window | 208..16910 | **206**..16910 |
| register-file corrections | 0 | 0 (the shadow) |
| reproduces | exactly | exactly |
| identical with the watchdog held off | yes | yes |

**[fact, `hw/soc/out/fi-h74rtl/golden_rtl.log`, `hw/soc/out/gl74/gl_campaign.log` controls 2 and 3]**.
The RTL clean run is `docs/42`'s to the cycle — 18,682, signature
`9c07ef12`, window 208..16910 — on the HEAD RTL with the ROM
unhardened, so `docs/43` section 9.1's invariant holds through
`docs/44` to `docs/73` and through that knob.

### 5.2 The one clock between the two designs, and where it comes from

The two runs differ by one cycle in the count and by two in the
window's opening, and the difference is in the bench's relation to the
design, not in the design. The whole-register trace of section 6.2
settles it: **the netlist's flip-flops hold, after clock edge *t*,
exactly what the RTL's hold after edge *t + 1***, for every one of
2,319 mapped bits over 18,681 edges. The two benches release reset on
the same edge (195 ns, the twentieth); the RTL's flip-flops evaluate
that edge before the bench's blocking reset assignment and stay in
reset for one more clock, the netlist's flip-flops sit behind a clock
tree of buffer cells, see the edge a delta later than the bench does,
and leave reset on it. The RTL clean run **re-compiled and re-run on
Icarus 13 is byte-identical in its trace to the Icarus 12 run**, 18,683
rows both **[fact]**, so this is not a simulator difference.
`gl_map.py` refuses to produce a mapping unless exactly one shift in
−2..+2 makes every toggling register-file bit identical; it found −1
and nothing else, and every replayed edge carries it. The window opens
two cycles earlier rather than one because the bench samples the phase
word out of the macro array at the edge, where the RTL bench reads the
array live; the difference is in the observation and the replay does
not use the window.

### 5.2a The clock the RTL bench does not count, found by control 5 and measured on every record

That was supposed to be the whole story, and the first gate-level pass
was run on it: a record's cycle, minus one. Control 5 — the same
injection at both levels, every mapped flip-flop compared cycle for
cycle afterwards — passed on three records and then, on a fourth chosen
because its RTL outcome was DETECTED, **did not**: `fetch_addr_q[4]` at
cycle 9609 derailed the RTL (64 traps) and did nothing at all to the
netlist (golden answer, the force did not persist). The traces say why.
At RTL the deposit landed on the fetch address `c0000138`; at gate level
the force landed on `c000015c`, the address of one edge earlier; the
register loads a branch target on that edge, so the netlist's flip-flop
was reloaded from D and the corruption vanished, while the RTL's, one
edge later, held it into the fetch.

**The RTL bench does not deposit on the cycle it names.** `tb_soc_fi.v`
waits `while (cycles < arg_cycle) @(posedge clk)` and deposits a quarter
cycle later; `cycles` is incremented by a second process on the same
edge, and which of the two the simulator runs first is a race the bench
leaves to the scheduler. A probe root that prints the simulation time
of the deposit shows it **[fact]**: `x16[13]` requested at 5756 lands at
57,757 ns, edge 5756; `fetch_addr_q[4]` requested at 9609 lands at
96,297 ns, edge **9610**. Nothing in `docs/42` or `docs/43` is wrong
about what happened in any run — every record is a deposit that did
land, on one edge, deterministically for that record — but **the
`cycle` column of every RTL record is the edge or the edge after it,
and the bench cannot say which**. And the gate-level bench, which
inherited the same loop, had the same race under Icarus 13: its probe
shows the force for edge 5755 landing on 5756 and the force for 9608
landing on 9608 **[fact]**. Two benches each off by a clock at the
scheduler's discretion cannot replay one another "at the same cycle".

Two things were done about it, and the first pass was discarded.

1. **Every RTL record's instant was measured.** `gl_campaign.py
   instants` re-runs each of the 1,400 records on the HEAD RTL build
   with the trace root and a budget four clocks past its cycle, and
   takes the first row on which the injected register differs from the
   clean run. **686 of 1,400 landed one edge after their cycle; 714 on
   it** **[fact, `hw/soc/out/gl74/instants.csv`]**, between 42 and 57
   of every 100 in every stratum, with no rule a reader could apply by
   hand. This is the instant of record, and the HEAD replay of section
   8.1 — the same executable — reproduces `docs/43` on all 1,400, so it
   is `docs/43`'s instant too.
2. **The gate-level bench was made to name the edge.** `tb_soc_fi_gl.v`
   now waits an absolute time from reset release — edge *c* is
   10 ns × *c* after it — forces a quarter cycle later, and reports the
   time in the record; on both probe records the force lands on the
   row asked for **[fact]**. The replay's edge is the record's measured
   row plus the −1 of section 5.2.

The first pass, 450 records at "cycle minus one" on a bench with the
same race, is not reported anywhere in this document except here; its
log is kept as `hw/soc/out/gl74/gl_campaign_pass1_abandoned.log`. Every
number from section 8.2 on is the second pass.

**What this means for `docs/42` and `docs/43`.** Their draws are
uniform over a window whether an edge is added or not, so no
distribution in either document moves; the `x23` records, the
`debug_mode_q` records, every record that document names by cycle is a
record of a deposit one edge later than written on roughly half of
them. Section 13 notes it in both. It is the tenth entry on the list
`docs/42` section 8.5 started: a way a campaign reports a confident
number, in this case a cycle, that it did not measure.

### 5.3 The RAM left undefined

One clean run with `+zero=0`, the RAM macros left as the model powers
them up — undefined — and nothing else changed: **18,681 cycles,
signature `9c07ef12`, 19 characters, hash `6d6942c8`, no trap, no
alert, no watchdog stage, the magic posted** **[fact,
`hw/soc/out/gl74/golden_gl_nozero.log`]**. This workload writes every
word it reads before it reads it, so the bench's zeroing changes nothing
about the clean run. It is kept, because an injected run that never
finishes reads whatever is there, and the comparison with the RTL
should not depend on that.

---

## 6. The flip-flop sets, reconciled

`docs/42` section 4.4 asked for two things a gate-level campaign would
see: the registers synthesis removes, and the flip-flops synthesis adds.
Both were enumerated before anything was injected, and the enumeration
had three stages because the first two are not enough on their own.

### 6.1 By name, which is the first word and would have been the wrong one

`gl_netlist.py --census` looks for each of the site table's 2,451 bits
under its own name with `u_ibex.` in front. **1,418 are there and
1,033 are not** **[fact, `hw/soc/out/gl74/census_by_name.txt`]** — every
CSR, most of the IF/ID register, all of the debug and PMP state, the
load/store address. Read as a census that would say the netlist lacks
40 % of the core. It lacks nothing of the kind: yosys keeps one public
name per net, and the one it keeps is whichever alias `opt_clean`
preferred. `mie` is `mie_q`, the wire its `rdata_o` drives; `mepc` and
`mtval` are `crash_dump_o[…]`; the IF/ID instruction register's bits
19:15 are `gen_regfile_ff.register_file_i.raddr_a_i`, the register
file's read-address port, and bits 7:11 its write-address port. `docs/32`
section 4.2 found the same thing on the pilot's rails. A name is a
hypothesis.

### 6.2 By trace, which is a measurement

Both benches run the clean workload with nothing injected and write,
on every falling edge, every register — the RTL bench its 2,451 site
bits through a second elaboration root that `gl_map.py` generates and
`fi_core.sh`'s new `FI_EXTRA_ROOT` compiles in, the netlist bench its
5,873 flip-flops. Two bits that are the same storage have the same
trace for 18,681 edges; a flip-flop that stores the complement has the
complemented trace. The RTL bit maps to the netlist flop whose trace
equals its own or its complement.

What a trace cannot decide is a bit that never moves — and in this
workload **1,391 of the 2,451 site bits never change**: 594 register-file
bits the program never writes, every PMP and debug register, most of
the trap CSRs, the upper halves of the counters. Two flops that are
constant have the same trace whatever they are.

### 6.3 By alias, which is the elaborated design's own testimony

`hw/soc/flow/fi_gl_alias.sh` runs `fi_coverage.sh`'s elaboration —
the same sources, the same parameters, `ibex_top` flattened — stopped
after `opt_clean` and before anything renames, and writes it as JSON.
Every public wire on a net is then known, so that "the netlist's
`mie_q[3]` is the RTL's `u_mie_csr.rdata_q[3]`" is read out of yosys
rather than guessed. The same JSON carries the RTL census of section
4.2 of `docs/42`: a site bit that no flip-flop cell drives after
`opt_clean` is one synthesis removed.

### 6.4 The mapping, decided in this order

| decided by | meaning | bits |
|---|---|---:|
| `trace+name` | one flop by trace, and it carries the RTL's name or an alias of it | **663** |
| `trace&alias` | several flops by trace (bits that agree on every cycle of this run), exactly one of them an alias | **299** |
| `trace` | one flop by trace, no name agrees, at least 16 transitions | **2** |
| `alias` | constant over the run; exactly one netlist flop carries an alias name, and its trace agrees | **1,295** |
| `merged` | mapped, but the flop is the twin of two live RTL registers | **60** |
| — mapped and injected | | **2,319** |
| `deleted` | no flip-flop in the RTL census: removed by synthesis | 17 |
| `ambiguous` | several by trace, none or several by alias | 8 |
| `constant` | constant over the run and no alias survives | 95 |
| `trace(weak)` | one by trace, no alias, fewer than 16 transitions | 4 |
| `alias(withdrawn)` | the alias-named flop toggles while the RTL bit is constant | 1 |
| `none` | a live bit with no trace twin at all | 7 |
| — not injected | | **132** |

**[fact, `hw/soc/out/gl74/map.txt`]**. Per stratum:

| stratum | bits | mapped | not by name alone | unmapped | what is unmapped |
|---|---:|---:|---:|---:|---|
| `regfile` | 992 | 992 | 92 | 0 | |
| `pc_fetch` | 70 | 66 | 43 | 4 | `fetch_addr_q[1:0]`, `stored_addr_q[1:0]`: the two low address bits, one of which has no twin and three of which equal every other always-zero bit |
| `fetch_fifo` | 133 | 133 | 21 | 0 | |
| `if_id` | 136 | 114 | 26 | 22 | 17 deleted (`instr_expanded_id_o`, `instr_new_id_q`), `instr_gets_expanded_id_o` (deleted per `fi_coverage.sh`; ambiguous here), `instr_rdata_alu_id_o[1:0]` and `pc_id_o[0]`, constant bits with many trace-equals |
| `controller` | 15 | 10 | 0 | 5 | `ctrl_fsm_cs[2:0]` re-encoded and `[3]` withdrawn (section 7), `debug_cause_q[1]` constant with no alias |
| `id_ctrl` | 71 | 69 | 29 | 2 | `imd_val_q[33:32]` |
| `lsu` | 74 | 59 | 22 | 15 | the five CHERIoT residue bits, `rdata_q` (8 bits constant in this run, no alias), `ls_fsm_cs[3]`, `data_type_q[0]` (8 transitions, weak) |
| `multdiv` | 75 | 72 | 22 | 3 | `md_state_q[2:0]` re-encoded |
| `csr_trap` | 214 | 195 | 31 | 19 | `cpuctrlsts`, `mtvec[7:0]` (Ibex forces them to zero), `priv_lvl_q`, one bit each of `mstatus`, `mstack`, `mcounteren` |
| `csr_pmp` | 155 | 155 | 0 | 0 | all by alias: `csr_pmp_addr_o`, `csr_pmp_cfg_o`, `csr_pmp_mseccfg_o` |
| `csr_cnt` | 131 | 130 | 0 | 1 | `mcountinhibit[1]`, the bit yosys drops |
| `csr_debug` | 128 | 101 | 0 | 27 | 26 bits of `dcsr` whose fields are constant in Ibex, `depc[0]` |
| `regfile_ecc` | 253 | 222 | 15 | 31 | the 31 eighth check bits, `docs/43` section 6.3 |
| `top_ctrl` | 4 | 1 | 0 | 3 | `core_busy_q[3:1]`: one flop for the four-bit encoding, section 6.5 |

**[fact]**. "Not by name alone" is the count that would have been
injected into the wrong flop, or into nothing, had the name been
trusted: **301** of the 2,319.

### 6.5 What exists in one and not in the other

**Removed by synthesis: 20 site bits, and 31 more the RTL census
already knew about.** `fi_coverage.sh`, re-run on the HEAD build,
reports **2,431 of the site table's 2,451 bits elaborating** — the same
arithmetic `docs/43` section 9.4 closes — and names the same three
registers `docs/42` section 4.2 does: `instr_expanded_id_o` (16 bits),
`instr_gets_expanded_id_o` (2) and `instr_new_id_q` (1), plus
`mcountinhibit[1]`. This document's own census, taken from the
elaborated design's JSON before `opt_dff`, flags **17** of those 20 as
`deleted`; the other three come out `ambiguous` and `constant` and are
not injected either. The 31 eighth check bits are `docs/43` section
6.3's and are absent by name, by alias and by trace. **Every RTL
injection into these 51 bits measured nothing physical**, in `docs/42`
and in `docs/43`, and none of them is replayed here. Bias direction:
the masked fraction, and only upward.

**Stored in one flip-flop for two RTL registers: 60 bits, and the
four-bit busy encoding.** Ibex keeps two copies of the 32-bit
instruction register in the ID stage — `instr_rdata_id_o` for the
decoder and controller, `instr_rdata_alu_id_o` for the operand path —
so that neither has to drive both. They have the same D, the same
enable and the same reset, and `opt_merge` stored bits 2 to 31 of both
in **one** flop each (bits 1:0 are constant `2'b11` in this run and
could not be told apart). An RTL upset in one copy corrupts the decode
and leaves the immediate intact, or the reverse; the netlist upset
corrupts both. **`docs/42`'s `instr_rdata_alu_id_o` row — 25
injections, 3 SDC — and its `instr_rdata_id_o` injections are therefore
not like-for-like with anything in the silicon.** They are replayed
into the shared flop and reported apart, section 9.4. `ibex_top`'s
`core_busy_q` is a four-bit multi-bit encoding whose bits are functions
of one another at `SecureIbex = 0`; **the netlist has one flip-flop for
all four**, so bit 0 maps and bits 3:1 are refused by the weak-trace
rule, and `docs/42`'s `top_ctrl` stratum — 100 injections, 12 DETECTED,
3 HANG — is a stratum of single-bit upsets into an encoding that does
not exist. Its 29 comparable records all reach that one flip-flop and
all 29 classify identically.

**Re-encoded: three state machines.** yosys's `fsm` pass recoded
**`ctrl_fsm_cs` from 4 bits into 8 flip-flops, `md_state_q` from 3 into
5, and `mult_state_q` from 2 into 3** **[fact, the parsed netlist]**.
Not one of `ctrl_fsm_cs`'s or `md_state_q`'s seven RTL bits has a twin —
a binary state bit is a function of several one-hot flops and equals
none of them — while two of `mult_state_q`'s three netlist flops do
carry the RTL's traces. All sixteen netlist state flip-flops are swept
on their own in section 11, where they turn out to be the most lethal
storage in the design.

**Added by synthesis under `u_ibex.`: 25 named flip-flops that are no
RTL bit's twin** — the 5 + 5 + 1 re-encoded state flops above,
`div_valid`, `controller_run_o`, a third `data_type_q` bit, and 12 that
are constant over the run. Not the "twenty-one" of `docs/32` section
1.3's kind; nothing here is redundancy the RTL added, and everything is
what a synthesiser does to a design it is allowed to re-encode.

**Inverted storage: 1 of 2,319.** `scrub_ptr[0]` resets to one, has no
set flip-flop to map to, and is stored inverted in an anonymous cell
(`_00268_`). The shadow decoder reads it through the polarity the trace
found.

### 6.6 The watchdog and the boot block, counted by name and counted by cone

The task asked for injections into `u_prot_a/b/c` as they exist in the
netlist. Counted by name they exist as follows **[fact]**:

| bank | RTL width | named flops in the netlist |
|---|---:|---:|
| `u_timer0.u_wdog.g_prot_tmr.u_prot_a.bits` | 29 | 29 |
| `…u_prot_b.bits` | 29 | **14** (the odd bits) |
| `…u_prot_c.bits` | 29 | **15** (the even bits) |
| `u_boot.g_prot_tmr.u_prot_a.bits` | 23 | 23 |
| `…u_prot_b.bits` | 23 | **11** |
| `…u_prot_c.bits` | 23 | **12** |

Read as a census that says the synthesiser halved replicas B and C of
both protected words — the exact failure `docs/41` section 6 and
`sw/tests/test_soc_synthesis_guards.py` exist to catch. It did not.
`POL_B = 0x5555…` and `POL_C = 0xAAAA…` make every other bit of B and
of C reset to one; `sg13g2` has no set flip-flop; `dfflibmap` builds a
reset-to-one flop as a reset-to-zero flop storing the inverse behind
an inverter; and the flop that results is a different cell from the
one that carried the name, so it carries none. **Traced back from the
voter's own `qb` and `qc` nets, each bank has 29 flip-flops (14 named
and 15 anonymous, 15 and 14), and the boot block's 23 (11 + 12, 12 +
11)** **[fact, `gl_netlist.py --wdog-census`, and the same cone over
`u_boot`]**. Section 10.2 injects into all 87.

---

## 7. The controls, each of which is a way to report a number while measuring nothing

`docs/42` section 5.1 had four and two of them caught a defect; `docs/52`
section 5.1 had nine. These are the gate-level bench's, all passing
**[fact, `hw/soc/out/gl74/gl_campaign.log`]**:

1. **The bench elaborated exactly the flip-flops the parse found**:
   5,873 and 5,873. An index into the force case that named a
   different cell from the one in `flops.tsv` would inject into the
   wrong flop and nothing else would notice.
2. **The gate-level clean run publishes the RTL clean run's answer**
   in every field the classifier compares — section 5.1 — and is silent
   in every announcement channel.
3. **It reproduces, and is identical with the watchdog held off.**
4. **A force takes, a positive control cannot be MASKED, a negative
   control can.** Bit 20 of `x2` — netlist flop #5170 — at the
   mid-window classifies **CORRECTED** and persisted after release; bit
   40 of `mcycle` classifies **MASKED**. Every record in every campaign
   additionally asserts that the value *during* the force is the
   complement of the value before it, and **no record in 1,576
   injections failed that assertion**.
5. **The injection is the same fault at both levels.** Four records
   were run at both levels with the whole mapped flip-flop state
   written out per cycle, and compared over the 964 flops the mapping
   identifies by trace: `fetch_fifo.rdata_q[77]`, `multdiv.op_numerator_q[25]`,
   `regfile.x16[13]` and `lsu.addr_last_q[7]` come back **0 of 964
   differing anywhere in 18,681 cycles** **[fact]**. An upset deposited
   into an RTL register and an upset forced onto its netlist flip-flop
   leave the two designs in the same state, cycle for cycle, for the
   rest of the run.
6. **The trace alignment is unique**, section 5.2: exactly one shift in
   −2..+2 makes every toggling register-file bit identical, and
   `gl_map.py` refuses to emit a mapping otherwise.
7. **The RTL clean run is simulator-independent**, section 5.2.

**Control 5 earned its place twice.** Its first version passed on three
records and failed on the fourth, which is section 5.2a's injection-
instant race and cost the first pass of the campaign. Re-run against
the measured instants it passes on all four — and on the way it caught
a second thing: `ctrl_fsm_cs[3]`, whose netlist flop carries the RTL
name but **toggles while the RTL bit is constant**, because the `fsm`
pass re-encoded the register and kept a name. That is a mapping the
alias rule would have made, and it is now refused by rule (`gl_map.py`
checks every alias-only mapping against the trace it has); 7 records
were withdrawn from the replay by it. Both are the shape `docs/42`
section 8.5 and `docs/52` section 5.4 record: a campaign reporting a
confident number about the wrong flip-flop.

---

## 8. The campaign

### 8.1 The RTL replay first: did the RTL move under the design?

`hw/soc/flow/fi_core.sh` had not been run since `docs/67`. Every wave
from `docs/44` to `docs/73` changed the SoC around the core — the
accelerator, the memory codec, the boot block, GPIO, QSPI — and none
changed the core. The netlist is HEAD's; `docs/43`'s campaign of record
is the RTL of 2026-09-01. Before the netlist is compared with anything,
the 1,400 records were replayed on the HEAD RTL, `ROM_HARDEN = 0`,
with the campaign's own `--directed` mode, made parallel for the
purpose (section 15):

| | `docs/43`, `fi-h1`, 2026-09-01 | HEAD, `fi-h74rtl`, `ROM_HARDEN = 0` |
|---|---|---|
| records | 1,400 | 1,400, the same site, bit and cycle each |
| armed class, held-off class or truth changed | — | **0 of 1,400** |
| held-off histogram MASKED / CORRECTED / SDC / DETECTED / HANG | 1,025 / 190 / 37 / 135 / 13 | **1,025 / 190 / 37 / 135 / 13** |
| clean run | 18,682 cycles, window 208..16910 | 18,682, 208..16910 |
| wall | 53 min at 18 jobs (`docs/42`) | **6 h 0 min at 8 jobs**, beside twelve gate-level simulations and the owner's place-and-route |

**[fact, `hw/soc/out/fi-h74rtl/directed.csv` against
`hw/soc/out/fi-h1/records.csv`, joined row by row]**. Not one record
moved. That is the calibration `docs/56` section 8.2 and `docs/58`
section 8.4 demand before a delta is quoted, and here it is exact over
every stratum: whatever the netlist campaign says differently from
`docs/43` is a difference between the two levels and not between two
RTLs. From here on "the RTL class" means this replay's, which is
`docs/43`'s.

### 8.2 The gate-level replay

| | |
|---|---|
| RTL records offered | 1,400 |
| with a netlist twin the campaign injects through | **1,175** |
| without | 225, itemised in section 9.5 |
| replayed with the watchdog held off | **1,175** |
| of those also replayed armed | **152** — every record whose RTL armed class differs from its held-off class, whose RTL run escalated, or whose RTL truth is DEAD, plus 100 drawn uniformly from the rest |
| injection edge | the record's measured RTL row (section 5.2a) minus one (section 5.2) |
| forces that did not take | **0** — every record asserts that the value during the force is the complement of the value before it |
| upsets that survived the release | 1,020 of 1,175; 155 were overwritten by the design at the edge inside the window, which is what a reloaded register does to an upset |
| wall | **50,582 s** for 1,327 simulations at 12 jobs, contended; per simulation min 110.7 s, median 404.3 s, max 1,924.7 s |

**[fact, `hw/soc/out/gl74b/records_gl.csv` and `gl_campaign.log`]**

---

## 9. Record for record

### 9.1 The comparable set

| | |
|---|---:|
| RTL records with a netlist twin, replayed | **1,175** |
| **held-off class identical** | **1,158** |
| of the 1,129 like-for-like (the merged flops excluded) | **1,126** |
| truth (OK / WRONG / DEAD) identical | 1,162 |
| armed class identical, of the 315 run armed | **313** |
| disagreements (held-off class, truth, or armed class) | **17** |

**[fact, `hw/soc/out/gl74b/reconcile.txt`]**. Per stratum, comparable
against identical:

| stratum | comparable | identical | differing |
|---|---:|---:|---:|
| `regfile` | 100 | 100 | 0 |
| `pc_fetch` | 87 | 87 | 0 |
| `fetch_fifo` | 100 | 100 | 0 |
| `if_id` | 85 | 70 | **15** |
| `controller` | 62 | 62 | 0 |
| `id_ctrl` | 96 | 96 | 0 |
| `lsu` | 75 | 75 | 0 |
| `multdiv` | 95 | 93 | 2 |
| `csr_trap` | 88 | 88 | 0 |
| `csr_pmp` | 100 | 100 | 0 |
| `csr_cnt` | 99 | 99 | 0 |
| `csr_debug` | 79 | 79 | 0 |
| `regfile_ecc` | 80 | 80 | 0 |
| `top_ctrl` | 29 | 29 | 0 |

And by how the twin was identified — which is the check on the mapping
itself, because a mapping made by a weaker rule should disagree more
often if it is wrong:

| identified by | comparable | identical |
|---|---:|---:|
| `trace+name` | 331 | 330 |
| `trace&alias` | 210 | 209 |
| `alias` (constant in the clean run, name only) | 587 | **587** |
| `trace` (renamed, no alias agrees) | 1 | 0 |
| **`merged`** (one netlist flop, two RTL registers) | **46** | **32** |

**[fact]**. **The 587 `alias` mappings — the ones with no behavioural
evidence behind them, section 12 — disagree on none.** That is the
strongest check available on the weakest part of the mapping: 587 bits
identified by a name yosys kept, and the netlist behaves as the RTL
does on every one. **Excluding the 46 merged records, whose netlist
flop is not the twin of one RTL register but of two, the like-for-like
set is 1,129 and 1,126 of them classify identically.**

### 9.2 The two histograms

Over the 1,175 comparable records, watchdog held off:

| | MASKED | CORRECTED | SDC | DETECTED | HANG |
|---|---:|---:|---:|---:|---:|
| **RTL** | 836 | 171 | 36 | 126 | 6 |
| **netlist** | 823 | **171** | 34 | 139 | 8 |

Over the 1,129 like-for-like records (the merged flops removed):

| | MASKED | CORRECTED | SDC | DETECTED | HANG |
|---|---:|---:|---:|---:|---:|
| **RTL** | 807 | 171 | 32 | 113 | 6 |
| **netlist** | 806 | **171** | 30 | 116 | 6 |

**[fact]**. `docs/32` section 5.1's histograms were equal in every
class on the pilot; these are not, and the differences are the 17
records of section 9.3 and nothing else. **CORRECTED is equal at 171
on both sides**, which is section 10.1. **The netlist's silent-
corruption count is lower than the RTL's, not higher** — 34 against
36 over the comparable set, 30 against 32 like-for-like — and the
movement is two records of the merged instruction register and two of
the re-encoded multiplier state, in both cases from SDC to DETECTED.
No stratum's SDC count rises.

### 9.3 Every disagreement, and its cause

**Seventeen**, in two groups, and a third group of eight that this
document created and then removed.

**Group A, and it was mine: eight register-file records, withdrawn by
repairing the instrument.** The first reconciliation had 25
disagreements, eight of them in `regfile` and `regfile_ecc`, all with
identical published output and identical truth at both levels and
differing only in CORRECTED against MASKED — that is, only in whether
the correction counter moved. Six were corrections the RTL counted and
the netlist did not; two the reverse. **The cause is a defect in
`hw/soc/tb/fi_rf_shadow.v`, this document's own bench instrument, and
it was found by probing the shadow's input beside its output on one
record**: at the injection edge the shadow's `data_i[63]` was 1 — the
corrupted flip-flop — while its decoded view of the same register read
`0x00007f30`, the clean stack pointer. The shadow read the array
through `function rdata(input [4:0] a)` and assigned
`wire [31:0] raw_s = rdata(ptr_i);`. **A continuous assignment is
sensitive to the signals in its expression, and `data_i` appears only
inside the function body**, so Icarus re-evaluated the select when the
address changed and never when the storage did. The scrub pointer holds
for as long as the core is writing — which is exactly the window in
which an upset waits to be corrected — so the shadow reported a
register as clean while the flip-flop under it was corrupted.

With the select written into the expression, the **180 register-file
records were re-run in full, armed and held off** (`hw/soc/out/gl74e`,
360 simulations, 2 h 42 m at 16 jobs): **180 of 180 now classify
identically to the RTL, held off and armed**, the eight disagreements
are gone, and the two histograms over the stratum are equal —
**171 CORRECTED and 9 MASKED on both sides**. The original records are
kept as `records_gl_shadow_v1.csv` beside the merged file. This is the
eleventh entry on the list `docs/42` section 8.5 began and the second
in this document: **an instrument that reports a confident number about
storage it is not reading.**

**Group B: fifteen records into the merged instruction register**,
section 9.4. `opt_merge` stored bits 2 to 31 of `instr_rdata_id_o` and
`instr_rdata_alu_id_o` in one flip-flop each, so a netlist upset
corrupts both RTL registers at once. Eleven MASKED become DETECTED, one
MASKED becomes SDC, one MASKED becomes HANG, one DETECTED becomes HANG,
one SDC becomes DETECTED — **the netlist is worse on all fifteen**, and
seven of them are the flip-flops the netlist names `raddr_a_i`,
`raddr_b_i`, `waddr_a_i` and `csr_addr`, which are the same shared word
seen from its consumers. **This is not a difference of level, it is a
difference of design**: the RTL has two registers there and the silicon
has one.

**Group C: two records into the multiplier's re-encoded state.**
`mult_state_q` is two bits in the RTL and three flip-flops in the
netlist, of which the trace identifies two as the RTL's. Both records
are **SDC at RTL and DETECTED on the netlist**: the same upset that
silently produced a wrong product at RTL puts the one-hot sequencer
into a state the program's dual-computation self-check notices
(`ann_sw` true on both). The netlist is *better* on both, for the same
reason section 11 finds it worse elsewhere — a re-encoded state machine
fails differently, and this campaign has 2 records of it here and 27 in
section 11.

**What no disagreement is.** None is a mapping error: the 587
alias-mapped bits, the ones with no behavioural evidence behind them,
now classify **587 of 587 identically**, and `trace+name` is 330 of
331 with the single exception in group C. None is a timing effect —
there is no timing. And none is in a stratum whose flip-flops the
netlist and the RTL agree about: `pc_fetch`, `fetch_fifo`,
`controller`, `id_ctrl`, `lsu`, `csr_trap`, `csr_pmp`, `csr_cnt`,
`csr_debug`, `regfile`, `regfile_ecc` and `top_ctrl` are **identical on
every one of their 995 comparable records**.

### 9.4 The merged registers, kept apart

`opt_merge` stored bits 2 to 31 of Ibex's two ID-stage instruction
registers in one flip-flop each (section 6.5), and 46 of `docs/43`'s
records draw into one or the other of them. They are replayed —
refusing to would leave the netlist's most-injected structure
unmeasured — and they are reported apart, because **an upset in that
flip-flop is an upset in both RTL registers at once and no RTL record
describes it**.

| | n | identical | differing |
|---|---:|---:|---:|
| records whose netlist flop is shared by two RTL registers | 46 | 32 | **14** |
| all other comparable records | 1,129 | 1,126 | 3 |

**[fact]**. Fourteen of the campaign's seventeen disagreements are
here — fifteen counting the one bit whose twin the mapping reached by
trace rather than by the merge rule, and their direction is one-way: **eleven MASKED become DETECTED,
one MASKED becomes SDC, one MASKED becomes HANG, one DETECTED becomes
HANG** — the netlist is *worse* on every one. That is what the
structure predicts. At RTL an upset in `instr_rdata_alu_id_o` corrupts
the operand path and leaves the decoder's copy intact, or the reverse;
in the netlist both see it, so an upset that the RTL absorbed in one
consumer reaches two. Two of the fourteen are the register file's own
address port (`raddr_a_i`, `waddr_a_i` in the netlist's naming) and one
is `csr_addr`, which is the same fact seen from the consumer's side:
those five-bit ports are *not* separate registers in the netlist, they
are bits 19:15, 24:20 and 31:20 of the shared instruction word.

**This is the finding that most changes what the RTL campaign means.**
`docs/42` section 6 measured `if_id` at 5 % SDC and 20 % DETECTED and
ranked it fifth by contribution; on the netlist the same 85 records give
34 wrong-or-announced outcomes where the RTL gave 20. No rate is quoted
from it — 46 records, one workload — but the direction is structural and
will not go away with a bigger sample.

### 9.5 What was not comparable

225 of the 1,400 RTL records have no netlist twin the campaign will
inject through **[fact, `reconcile.txt` section 4]**:

| reason | records | what it is |
|---|---:|---|
| `constant` | 89 | the RTL bit never changes in the clean run and no netlist flip-flop carries a name it can be identified by: `dcsr` 19, `cpuctrlsts` 8, `ls_fsm_cs` 5, `rdata_q` 13, `debug_cause_q` 10, `cap_rx_fsm_q` 4, `imd_val_q` 4, the eighth check bit of thirteen registers, and eight more |
| `trace(weak)` | 73 | mapped by a trace with fewer than sixteen transitions and no agreeing alias — 71 of them `core_busy_q[3:1]`, which is one flip-flop in the netlist (section 6.5), and 2 `data_type_q[0]` |
| `none` | 28 | a live RTL bit with no trace twin at all: `ctrl_fsm_cs[2:0]` 21 and `md_state_q[2:0]` 5, both re-encoded, and `fetch_addr_q[1]` 2 |
| `deleted` | 14 | `instr_expanded_id_o` 13 and `instr_new_id_q` 1 — `docs/42` section 4.2's registers, which do not exist in silicon |
| `alias(withdrawn)` | 7 | `ctrl_fsm_cs[3]`, whose alias-named netlist flop toggles while the RTL bit is constant, section 7 control 5 |
| `ambiguous` | 12 | `stored_addr_q` 11 and `pc_id_o[0]` 1 |
| **total** | **225** | |

Three of those groups are covered by other measurements rather than
left open: the re-encoded state machines are swept on their own netlist
flip-flops in section 11, the four `core_busy_q` bits are one flop that
29 other records reach, and the deleted registers are the point of
section 6.5.

---

## 10. What the synthesised redundancy actually did

### 10.1 The register file's code, on 217 check flip-flops and 992 data flip-flops

`docs/43` built the SECDED register file and measured it at RTL; its
section 9.4 counted 1,214 flip-flops in a mapped netlist of the block
alone. On the sign-off netlist of the whole SoC the same structure is
present, by name, at the same size: **992 data flip-flops, 217 check
flip-flops** (seven per register, the eighth deleted as section 6.3 of
that document derived) **and the 5-bit scrub pointer** — 1,214, and the
campaign injected into 180 of them from `docs/43`'s draws.

| | records | CORRECTED | MASKED | SDC | DETECTED | HANG |
|---|---:|---:|---:|---:|---:|---:|
| `regfile` (data), netlist | 100 | **94** | 6 | **0** | 0 | 0 |
| `regfile` (data), RTL | 100 | 94 | 6 | 0 | 0 | 0 |
| `regfile_ecc` (check bits, scrub pointer), netlist | 80 | **77** | 3 | **0** | 0 | 0 |
| `regfile_ecc`, RTL | 80 | 77 | 3 | 0 | 0 | 0 |

**[fact]**. **171 of 180 corrected on the netlist and 171 at RTL,
record for record, with zero SDC, zero DETECTED, zero HANG and zero
uncorrectable syndromes on either side**, and every one of the 171
ended with the golden answer. The nine MASKED are the same nine at both
levels and are the class `docs/43` section 9.2 had to argue for: a
register the program overwrites before the scrub reaches it has shed
the upset without the codec seeing it.

**So the protection is in the netlist and it works there.** That is
the claim `docs/43` could not make: its evidence was an RTL campaign
plus a flip-flop count, and a count cannot show that the codec on the
read path was not restructured into something that decodes differently.
Here the same 180 upsets are corrected by the gates that will be
manufactured, and the four disagreements about *which* record was
corrected are section 9.3 group A.

### 10.2 The watchdog's three replicas, on 87 flip-flops: the vote holds, the count counts, and the chip resets

Every one of the 87 replica flip-flops section 6.6 enumerated by cone —
29 of A, 29 of B, 29 of C — was upset twice, at two cycles drawn per
flop inside the window, **with the watchdog armed**, on the image that
also carries the voter shadow: 174 injections.

| bank | n | golden answer | voter mismatch cycles seen | `tmr_count` after | `tmr_err` after | persisted after release |
|---|---:|---:|---:|---:|---:|---:|
| A | 58 | 58 | 1 in every run | 1 in every run | 1 | 4 |
| B | 58 | 58 | 1 | 1 | 1 | 8 |
| C | 58 | 58 | 1 | 1 | 1 | 8 |

**[fact, `hw/soc/out/gl74s/records_gl_wdog.csv`]**. On the RTL's own
terms — `docs/41` section 8.2's 126 of 126 and `docs/43` section 9.2's
168 of 168 — this is 174 of 174 CORRECTED: the vote masked every upset,
the W6 report inside the word recorded exactly one mismatch every time,
and the run ended with the golden signature, mask, console and magic.
The replica that was upset was rewritten from the voted word on the
next edge in 154 of 174 cases, which is the scrub `soc_wdog.v` says it
is; the 20 that held did so because the word was being written that
edge anyway.

**And in every one of the 174 the SoC reset itself one clock after the
upset.** The run lengths give it away before any trace does: every
record's cycle count is its injection edge plus 18,683 or 18,684 — the
clean run, started again — with 19 console characters and not 38,
because the restart came before the program's console output, and with
`trap_count` and `nmi_count` at zero because the restarted `crt0`
zeroed them. The bench's watchdog pins saw nothing: no stage-1 NMI, no
stage-2 pulse, no `wdog_no`. A probe on the netlist's own `rst_raw_n`
and the three voter inputs, on `u_prot_a.bits[0]` at edge 14531
**[fact]**:

```
t = 145,507,000 ps  force: qa bit 0 = 1, qb = qc = 0  (vote 0)
t = 145,515,000 ps  the edge: the banks reload from prot_n, which now
                    carries tmr_err = 1, tmr_count = 1
                    qb = 00000000001100000000000000010   (bits 18, 19)
                    qc = 00000000000000000000000101010
                    qb = 00000000000000000000000101010
                    qc = 00000000000000000000000111010
                    rst_raw_n FELL, then rose, in the same time step
t = 145,517,000 ps  qa = qb = qc = ...110010, settled and correct
```

The mechanism is in the replica transform. Banks B and C store the word
mixed and inverted (`soc_tmr_bank.v`, `MIX = 1`), and their voter inputs
`qb` and `qc` are `mix_dec` of the stored bits: **combinational
functions of several flip-flops each**. When the word changes on an
edge, the twenty-nine flip-flops of a bank update in the simulator's
delta order, the decode passes through intermediate values that are
words the bank never stored, and for one delta both `qb` and `qc` had
bit 18 or 19 set — `rst_hold`, the stage-2 stretch field, bits 17 to 21.
Two of three is a majority; `in_reset = (rst_hold != 0)`; `rst_raw_n =
rst_ni && !wdog_rst_req` is **asynchronous** and needs no width. The
RTL cannot do this: `mix_dec` is a function evaluated once per event
and the replica's output changes atomically. The netlist has no atomic
anything.

Three things must be kept apart about it.

1. **It is a zero-delay artefact in its detail and a hazard in its
   substance.** The order in which twenty-nine flip-flops' outputs
   propagate through an XOR tree in one delta is the simulator's, and
   silicon has no deltas. What silicon has instead is twenty-nine
   clock-to-Q delays and an XOR tree of unequal path lengths feeding a
   voter feeding an asynchronous reset with no synchroniser, no filter
   and no registered stage between them. Whether the physical glitch on
   `wdog_rst_req` is ever wide enough to reset the flip-flops it reaches
   is a question of the layout's delays, and **nothing in this
   repository's sign-off asks it**: STA does not check the width of a
   glitch on an asynchronous reset. It is reported as a hazard the
   netlist has and the RTL does not, and not as a measured silicon
   reset rate.
2. **The same experiment at RTL does not reset.** A deposit into
   `u_prot_a.bits[0]`, `[4]` and `[17]` at the same edge on the HEAD RTL
   completes at 18,682 cycles with no reset request **[fact]**, which
   is what `docs/41` measured and reported.
3. **It is not the injection's doing.** The force made the word change
   (the W6 record); the glitch is in how a changed word reaches the
   reset. Any event that changes the protected word — a stage-1 NMI
   setting `nmi_pend`, an early kick, a spent budget, the stretch
   counting down — moves several mixed bits on one edge and takes the
   same path. On this workload the word never changes after boot in the
   clean run, which is why the clean run is clean; section 9.3 says
   what the armed replay saw when a stage-1 escalation changed it.

**What the class is.** `campaign.py`'s classifier does not compare
cycle counts (`docs/42` section 5), samples the watchdog pins at clock
edges, and so calls all 174 CORRECTED. That label is kept in the table
because it is what the classifier of record says, and it is wrong in
the way `docs/52` section 6.2 warns about: it is a property of the
oracle. **The honest class for these 174 is a reset the announcement
channel missed**: the answer is golden because the program ran again,
and an operator watching `wdog_rst_o` at clock edges would not have
been told. A pin watched for events rather than sampled would: the
bench now counts every rising event on `wdog_rst_o` (`wdog_rst_events`,
added after the sweeps ran, on a fourth image), and the same injection
on it reports **`wdog_rst_events = 1`** with every edge-sampled stage
counter at zero **[fact, `hw/soc/out/gl74/checks/async_a0.out`]**. The
174 records of the table were taken without that counter and are
classified by the edge-sampled pins; their restart is established by
their run lengths.

**What this does to `docs/41`.** Its 126 of 126 stands as a statement
about the RTL. Its claim that the protected word is safe to put on the
reset path — W4, "the reason its own state has to be outside this
domain" — acquires a qualification the netlist supplies: the state is
safe, the decode of it into an asynchronous reset is not shown to be.
The fix is one flip-flop: a registered `in_reset`, or a stage-2 request
taken from the voted word one clock later. It is not made here, because
`hw/soc/rtl/` is not this document's to change and because the right
measurement to make first is the one item 1 names.

---

## 11. The flip-flops the RTL campaign never reached

Section 6.5's 25 named flip-flops under `u_ibex.` that are no RTL bit's
twin — 13 that change in the clean run and 12 that do not — were each
upset three times at cycles drawn per flop, with the watchdog held off,
on the image that carries both shadows: 75 injections **[fact,
`hw/soc/out/gl74c/records_gl_sweep.csv`]**.

| netlist flip-flop | what it is | n | MASKED | SDC | DETECTED | HANG |
|---|---|---:|---:|---:|---:|---:|
| `controller_i.ctrl_fsm_cs[1]`, `[3]`, `[6]`, `[8]` | four of the eight one-hot state flops the `fsm` pass made of the RTL's 4-bit `ctrl_fsm_cs` | 12 | 0 | 0 | 0 | **12** |
| `controller_i.ctrl_fsm_cs[2]`, `[4]`, `[5]`, `[9]` | the other four | 12 | 11 | 0 | 1 | 0 |
| `controller_i.controller_run_o` | a registered "controller is running" the RTL derives combinationally | 3 | 0 | 0 | 0 | **3** |
| `multdiv_i.md_state_q[1]`, `[2]`, `[5]`, `[6]` | four of the five one-hot flops of the RTL's 3-bit `md_state_q` | 12 | 3 | **8** | 0 | 1 |
| `multdiv_i.md_state_q[4]` | the fifth | 3 | 3 | 0 | 0 | 0 |
| `multdiv_i.gen_mult_fast.mult_state_q[3]` | the third flop of the RTL's 2-bit `mult_state_q` | 3 | 0 | 0 | 3 | 0 |
| `multdiv_i.div_valid` | a registered divider-valid the RTL derives combinationally | 3 | 0 | 2 | 1 | 0 |
| `load_store_unit_i.data_type_q[2]` | a third data-type bit | 3 | 3 | 0 | 0 | 0 |
| `load_store_unit_i.rdata_q[31:24]` | eight flops constant in this run | 24 | 24 | 0 | 0 | 0 |
| **all** | | **75** | **44** | **10** | **5** | **16** |

**The controller's re-encoding changed what an upset in it does.** The
RTL campaign's 28 draws into the 4-bit binary `ctrl_fsm_cs` came back
17 MASKED, 5 DETECTED, 5 HANG, 1 SDC — 21 % wrong or dead, `docs/42`
section 6.4. The netlist stores the same machine one-hot in eight
flip-flops, and **four of the eight kill the core in 12 of 12 draws**:
a one-hot state with two bits set, or none, has no next state, and the
`controller_run_o` flop the synthesiser added dies the same way in 3 of
3. Over the 27 draws into the state machine's netlist flops, **15 are
HANG** — 56 %, against 18 % for HANG alone at RTL. The divider's
sequencer went the same way: 8 SDC in 12 draws into its one-hot bits
where the RTL's binary `md_state_q` gave 0 SDC in 5. **These are
flip-flops the RTL campaign could not have injected, because they do
not exist in the RTL**, and they are the most lethal storage in the
netlist per bit: `docs/42` section 6.3's "the controller dominates the
risk" is more true of the silicon than of the RTL that measured it.
The samples are three per flop and are quoted as counts, not rates.

The twelve constant flops behave as constants: 24 of 24 into the
LSU's upper `rdata_q` byte MASKED, and the three constant one-hot bits
either MASKED or HANG exactly as their live siblings.

---

## 12. What this campaign does NOT cover

Stated at length, in the discipline `docs/42` section 9 and `docs/52`
section 13 set, and everything those two lists say stands here.

- **No single-event transient.** A force on a flip-flop's output for
  one clock is an upset in storage. The SECDED decoder on the register
  file's read path is **528 combinational cells** (`docs/43`), the
  voter is combinational, the fetch-address adder is combinational, and
  none of them is a site. `docs/42` section 4.4 item 3 named this and
  it is still true at gate level: a campaign that reaches the netlist
  reaches its flip-flops, and a CPU is mostly not flip-flops.
- **No timing.** Zero-delay cell models and the macros' `FUNCTIONAL`
  core. A fault whose effect depends on the setup miss `docs/70`
  section 6 measured, or on hold, is invisible; three-corner STA in
  `s71boot`'s run directory is the complementary evidence and it does
  not close.
- **The RAM zeroed, the ROM loaded by the bench.** Section 4.2. The
  silicon's RAM is undefined until the loader sweeps it and its ROM is
  a mask ROM this PDK cannot build (`docs/68` section 3).
- **One workload, one seed, one parameter point** — `docs/42`'s, on
  purpose, so the records could be replayed. Nothing here says what a
  program that used the PMP or took interrupts would see.
- **The oracle is the run's output**, `docs/42` section 3. A netlist
  flop left wrong in a way this program never reads is MASKED. The
  shadow decoder narrows this for the register file only.
- **The gate-level CORRECTED class rests on a bench instrument.** The
  shadow decoder reads storage the silicon does not report; in silicon
  a corrected upset in the register file is invisible, `docs/43`
  section 6.5, and that is unchanged by measuring it.
- **The armed run was made for 315 of the 1,175 replayed records.** Every
  record whose RTL armed class differs from its held-off class, whose
  RTL run escalated, or whose RTL truth is DEAD, plus 100 drawn
  uniformly from the rest, plus all 180 register-file records because
  their re-run (section 9.3) was made armed and held off throughout.
  The held-off class is the one every table in `docs/42` section 6 and
  `docs/43` section 8 is built on and it was measured for every
  replayed record.
- **1,391 of the site table's bits do not change in the clean run**,
  and 1,295 of them are mapped by name alone. The alias is yosys's own
  and the netlist has exactly one flop under it, so the mapping is not
  a guess; but nothing in this document proves by behaviour that an
  `alias`-mapped flop is the RTL's, the way the trace proves it for the
  other 964.
- **Nothing outside `u_ibex` and the watchdog's word was injected.**
  The boot block's replicas were censused and not injected; the
  memories, the fabric, the CLINT and the NPU connection have their own
  RTL campaigns and no gate-level one.
- **One netlist, one layout, one PDK version**, and a layout that has
  no DRC, LVS or XOR result, `docs/71` section 11.
- **No rate**, `docs/16` section 7.5.
- **Every wall figure is contended**, section 14.

---

## 13. Corrections to earlier documents

Every one is a dated in-place note, by `docs/64` section 2's rule; no
original sentence is edited.

- **`docs/42` section 4.4**, "the SoC has never been synthesised as one
  design … named in section 10 as an open item and not claimed":
  closed, with what the netlist turned out to contain.
- **`docs/42` section 5.1 control 5**, and with it every record's
  `cycle` column: the deposit lands on the named cycle or the one
  after it, 686 of 1,400 late, section 5.2a. No distribution moves.
- **`docs/43` section 9.4**, "the campaign injects into all 248 [check
  flip-flops] and 31 of those injections are into storage the netlist
  does not contain": confirmed on the sign-off netlist by three
  independent means, and the other 217 measured working.
- **`docs/47` section 9** ("no gate-level simulation of `soc_top`
  exists") and **section 11 item 5** ("a gate-level simulation of
  `soc_top`", the open item): both closed.
- **`docs/62` section 13**'s "NOTHING HERE WAS SIMULATED AT THE GATE
  LEVEL": superseded for the design of `docs/70` onward, not for the
  `SYNPRE` netlist that document measured.
- **`docs/70` section 11**, **`docs/71` section 11** and **`docs/72`
  section 12**: the gate-level half of their "`Yosys.EQY` is off and no
  gate-level simulation exists" is closed on this very layout's
  netlist; the equivalence half is not, and is not touched.

**Not corrected, deliberately: `docs/41` section 8.2's 126 of 126.**
Section 10.2 measures the same structure on the netlist and finds the
vote intact and the reset path hazardous. That is an addition to what
`docs/41` measured, not an error in it, and it is stated in this
document rather than as a note in that one, because a one-line note
could not carry it.

---

*Two notes added 2026-09-07 by `docs/75-the-reset-on-a-corrected-upset.md`.*

**Section 10.2 and section 17 item 1: done.** `soc_wdog.v` now carries
W9, one flip-flop between the combinational decode of the voted word and
`rst_req_o`, at no change of behaviour — the two operands of the added
AND are proved equal on every cycle by k-induction — and the gate is
proved on the mapped netlist by SAT, with the two mutations that make
that proof fail. `docs/75` section 6 also answers a question this
document did not ask: over the whole of `s71boot`'s netlist there are
**five** distinct asynchronous-reset fan-in source sets, four of them a
port or one or two registered signals, and the fifth is `rst_raw_n`,
driven by **25 flip-flops of the three replica banks and nothing else**.
This was the only place in the SoC where a decode reached an
asynchronous reset.

**Section 6.6's census is now three instruments and not two, and the
distinction matters more than the numbers.** The "29, 14 and 15" here is
a census by **Q-net name**. `docs/75` section 3 re-measured every replica
count published since `docs/41` — the watchdog's, the boot block's and
the NPU cause bank's — by the voter's fan-in cone, and confirmed all of
them; but it also established that the guards in `sw/tests` had never
used a Q-net census. They count by **instance path**, which is exact in
their own recipe and blind on the netlist LibreLane writes, and neither
this document nor any before it had ever censused that netlist
mechanically. `sw/tests/test_soc_shipped_netlist_guards.py` now does,
over every retained netlist, with the disjointness assertion this
document's cone census implied and did not state.

---

## 14. Cost, measured and contended

**Every figure here was measured on a machine that ran the owner's
place-and-route, two sibling projects and up to eighteen of this
document's own simulations at once**, and load average was between 3
and 28 throughout. `docs/32` section 7 and `docs/71` section 14 make
the same statement; these numbers are worth less than theirs, because
nothing here ever had the machine to itself.

| | n | wall | per simulation |
|---|---:|---|---|
| RTL clean run, Icarus 12 | 1 | **10.3 s** | — |
| gate-level clean run, no trace, Icarus 13 | 1 | **2 m 18.8 s** | — |
| gate-level clean run with the 110 MB flip-flop trace | 1 | 3 m 14.9 s | — |
| RTL replay of `docs/43`'s 1,400 records, 8 jobs | 2,800 | **5 h 59 m** | 61.6 s of one job |
| the injection-instant measurement, 1,400 short RTL runs, 6 jobs | 1,400 | 57 m | 14.7 s |
| **the gate-level replay, 12 jobs** | **1,327** | **14 h 03 m** | **457 s of one job**; median 404 s, min 110.7 s, max 1,924.7 s |
| the watchdog replica sweep, armed, 6 jobs | 174 | 5 h 43 m | 197 s |
| the netlist-only flop sweep, 6 jobs | 75 | 3 h 06 m | 149 s |

**[fact, the files' own timestamps and the campaign logs]**

**Gate level costs about an order of magnitude here, not the small
multiple `docs/24` and `docs/32` measured on the pilot.** The clean run
alone is **13.5x** the RTL's (138.8 s against 10.3 s) **[estimate,
arithmetic on two measurements]**, and per replayed injection under
contention the ratio is **7.4x** (457 s against 61.6 s). Two things
account for the difference from the pilot's 3–5x, and neither is the
injector: this design is **5,873 flip-flops and 52,286 cells against
the pilot's 1,296 and 12,546**, and its gate-level bench additionally
carries six behavioural SRAM macros and, for the records that reach the
budget, a 62,129-cycle run against the RTL's identical one.

**The single largest cost in this document is not a campaign.** The
1,400-record instant measurement and the two clean runs are minutes;
the 1,327 gate-level simulations are fourteen hours; and the first
pass, discarded for the reason section 5.2a gives, cost another
fourteen. **A gate-level campaign on this SoC is a day per pass**, and
that is the number to plan the next one with.

---

## 15. Files touched

| file | change |
|---|---|
| `docs/74-core-gate-level-campaign.md` | this document |
| `docs/00-index.md` | one row |
| `hw/soc/fi/gl_netlist.py`, `hw/soc/fi/gl_map.py`, `hw/soc/fi/gl_campaign.py` | new |
| `hw/soc/tb/tb_soc_fi_gl.v` | new; a `wdog_rst_events` counter was added after the sweeps ran, section 10.2, and the records there were taken without it |
| `hw/soc/tb/fi_rf_shadow.v` | new, and repaired once during this work: the array selects are written into the assignments' expressions rather than hidden in a function, section 9.3 group A |
| `hw/soc/flow/fi_core_gl.sh`, `hw/soc/flow/fi_gl_alias.sh` | new |
| `hw/soc/flow/fi_core.sh` | `SOC_ROM_HARDEN` (empty by default: the design's own value), `FI_EXTRA_SRC` and `FI_EXTRA_ROOT` (empty by default), and the codec-arm exclusion made aware of the ROM knob |
| `hw/soc/tb/tb_soc_fi.v` | the ROM check-bit deposit under `ifndef FI_ROM_PLAIN`, which only `SOC_ROM_HARDEN=0` defines; every build before this one is unchanged |
| `hw/soc/fi/campaign.py` | the `--directed` replay runs its pairs through the campaign's thread pool; the records are classified in file order as before |
| `docs/42-core-fault-injection.md`, `docs/43-core-hardening.md`, `docs/47-soc-place-and-route.md`, `docs/62-synpre-remeasured.md`, `docs/70-boot-hardening-placed.md`, `docs/71-layout-reproducibility.md`, `docs/72-post-grt-resizer.md` | one dated in-place note each, section 13 |

`hw/soc/out/fi-h74rtl/` and `hw/soc/out/gl74*/` are gitignored build
products, `docs/38` section 11's rule, and hold the RTL replay, the
traces, the mapping, every record and every log this document quotes:
`gl74` the netlist parse, the alias JSON, the clean-run trace and the
mapping; `gl74b` the campaign of record (with `records_gl_shadow_v1.csv`,
the pre-repair register-file rows) and the reconciliation; `gl74c` the
netlist-only sweep; `gl74s` the watchdog sweep; `gl74d` the
asynchronous-pulse check; `gl74e` the register-file re-run.

**Nothing in `hw/rtl/`, `hw/tb/`, `tt/`, `formal/` or `hw/openlane/` is
modified and `hw/tb/Makefile.fi` was not invoked. `docs/34`'s freeze is
untouched. No file under `hw/soc/rtl/` is modified.** `hw/soc/pnr/runs/`
was read and not written; the run directories that appeared there
during this work (`s73clintmgp3`, `s73v2fence`, `s73clint-pre`) are the
owner's and were not touched.

The Python suite: **456 passed, 0 failed** **[fact, `.venv/bin/python -m pytest sw/tests -q`, 2 m 27 s]** — `docs/73` section 13 reports 455 with that document present, and `sw/tests/test_doc_links.py` discovers the corpus, so this document adds exactly one test.

**And the cocotb suites, which are not optional here**, because this
work changed `hw/soc/fi/campaign.py`, `hw/soc/flow/fi_core.sh` and
`hw/soc/tb/tb_soc_fi.v` — files the RTL campaigns of `docs/42`,
`docs/43`, `docs/46` and `docs/67` are reported from: `scripts/run_cocotb.sh`,
**395 passed, 0 failed, 0 suites not clean, exit 0** **[fact]**, the
count `docs/67` established and `docs/70` to `docs/73` left standing.
The RTL fault-injection instrument is additionally proved unmoved by
measurement rather than by a test count: the clean run of `docs/42`'s
workload on the HEAD build is **18,682 cycles, signature `9c07ef12`,
window 208..16910**, and all 1,400 of `docs/43`'s records replay to
their published classes (section 8.1).

---

## 16. Reproducing this

```bash
# 0. the RTL side, HEAD, the layout's configuration, with the trace root
mkdir -p hw/soc/out/fi-h74rtl
python3 hw/soc/fi/gl_map.py --emit-rtl-trace hw/soc/out/fi-h74rtl/fi_rtl_trace.v
SOC_ROM_HARDEN=0 FI_EXTRA_SRC=$PWD/hw/soc/out/fi-h74rtl/fi_rtl_trace.v \
  FI_EXTRA_ROOT=fi_rtl_trace hw/soc/flow/fi_core.sh $PWD/hw/soc/out/fi-h74rtl
VVP=$HOME/Downloads/oss-cad-suite-linux-x64-20260804/oss-cad-suite/bin/vvp
$VVP -n hw/soc/out/fi-h74rtl/tb_soc_fi.vvp +armed=1 +budget=200000 \
  +trace=$PWD/hw/soc/out/fi-h74rtl/golden_rtl.trace > hw/soc/out/fi-h74rtl/golden_rtl.log
hw/soc/flow/fi_coverage.sh $PWD/hw/soc/out/fi-h74rtl          # 2431 of 2431

# 1. the RTL replay of docs/43's records on HEAD
FI_REGFILE=secded python3 hw/soc/fi/campaign.py --build hw/soc/out/fi-h74rtl \
  --directed hw/soc/out/fi-h1/records.csv --jobs 8

# 2. the netlist: census by name, the bench, the clean run with its trace
python3 hw/soc/fi/gl_netlist.py hw/soc/pnr/runs/s71boot/final/nl/soc_top.nl.v --census
hw/soc/flow/fi_core_gl.sh hw/soc/pnr/runs/s71boot/final/nl/soc_top.nl.v \
  hw/soc/out/fi-h74rtl hw/soc/out/gl74
GLVVP=$HOME/.local/opt/iverilog13/usr/bin/vvp
$GLVVP -n hw/soc/out/gl74/tb_soc_fi_gl.vvp +armed=1 +budget=200000 \
  +wdog_rld=127 +wdog_pre=16 +trace=$PWD/hw/soc/out/gl74/golden_gl.trace

# 3. the mapping, the shadow, the rebuild
IBEX_FAULT_PORT=1 hw/soc/flow/fi_gl_alias.sh hw/soc/out/gl74
cd hw/soc/out/gl74
python3 ../../fi/gl_map.py --rtl-trace ../fi-h74rtl/golden_rtl.trace \
  --gl-trace golden_gl.trace --flops flops.tsv --alias fi_alias.json \
  --out map.json --report map.txt
python3 ../../fi/gl_map.py --emit-rf map.json flops.tsv fi_gl_rf.vh
cd ../../../..
hw/soc/flow/fi_core_gl.sh hw/soc/pnr/runs/s71boot/final/nl/soc_top.nl.v \
  hw/soc/out/fi-h74rtl hw/soc/out/gl74                         # shadow: -DFI_GL_RF

# 4. the campaign
python3 hw/soc/fi/gl_campaign.py run --build hw/soc/out/gl74 --map hw/soc/out/gl74/map.json \
  --records hw/soc/out/fi-h1/records.csv --rtl-golden hw/soc/out/fi-h74rtl/golden_rtl.log \
  --rtl-build hw/soc/out/fi-h74rtl --rtl-vvp $VVP --jobs 12 --armed subset --subset 100 \
  --trace-check 3

# 5. the sweeps, on a second image that also carries the voter shadow
mkdir -p hw/soc/out/gl74s && cp hw/soc/out/gl74/fi_gl_rf.vh hw/soc/out/gl74s/
python3 hw/soc/fi/gl_netlist.py x --emit-wdog hw/soc/out/gl74s/fi_gl_wdog.vh
hw/soc/flow/fi_core_gl.sh hw/soc/pnr/runs/s71boot/final/nl/soc_top.nl.v \
  hw/soc/out/fi-h74rtl hw/soc/out/gl74s                        # -DFI_GL_RF -DFI_GL_WDOG
python3 hw/soc/fi/gl_campaign.py wdog  --build hw/soc/out/gl74s --map hw/soc/out/gl74/map.json \
  --rtl-golden hw/soc/out/fi-h74rtl/golden_rtl.log --draws 2 --jobs 6
python3 hw/soc/fi/gl_campaign.py sweep --build hw/soc/out/gl74s --map hw/soc/out/gl74/map.json \
  --rtl-golden hw/soc/out/fi-h74rtl/golden_rtl.log --rtl-trace hw/soc/out/fi-h74rtl/golden_rtl.trace \
  --draws 3 --constants --jobs 6

# 5b. the register file re-run on the repaired shadow, and the merge
mkdir -p hw/soc/out/gl74e && cp hw/soc/out/gl74b/fi_gl_rf.vh hw/soc/out/gl74e/
hw/soc/flow/fi_core_gl.sh hw/soc/pnr/runs/s71boot/final/nl/soc_top.nl.v \
  hw/soc/out/fi-h74rtl hw/soc/out/gl74e
python3 - <<'PY'                     # the 200 regfile/regfile_ecc records
import csv
r=[x for x in csv.DictReader(open('hw/soc/out/fi-h1/records.csv'))
   if x['stratum'] in ('regfile','regfile_ecc')]
w=csv.DictWriter(open('hw/soc/out/gl74e/records_rf_only.csv','w',newline=''),
                 fieldnames=list(r[0].keys())); w.writeheader(); w.writerows(r)
PY
python3 hw/soc/fi/gl_campaign.py run --build hw/soc/out/gl74e --map hw/soc/out/gl74/map.json \
  --records hw/soc/out/gl74e/records_rf_only.csv --instants hw/soc/out/gl74/instants.csv \
  --rtl-golden hw/soc/out/fi-h74rtl/golden_rtl.log --jobs 16 --armed all \
  --records-out records_gl_rf.csv
# the 180 rows replace their twins in gl74b/records_gl.csv; the originals
# are kept as records_gl_shadow_v1.csv

# 6. the reconciliation
python3 hw/soc/fi/gl_campaign.py reconcile --build hw/soc/out/gl74 --map hw/soc/out/gl74/map.json \
  --records hw/soc/out/fi-h1/records.csv --head hw/soc/out/fi-h74rtl/directed.csv
```

`hw/soc/out/gl74/golden_gl.trace` is 110 MB (5,873 characters a line,
18,682 lines) and is written once.

---

## 17. What the next block should be

1. **Register the watchdog's stage-2 request, or take it from the voted
   word one clock later.** Section 10.2 is the sharpest thing this
   document found: on the netlist a change of the protected word puts a
   combinational glitch on an asynchronous system reset, and 174 of 174
   replica upsets restarted the SoC without any edge-sampled channel
   saying so. The fix is one flip-flop in `hw/soc/rtl/soc_wdog.v`; the
   measurement that should come first is **whether the physical pulse is
   wide enough to matter**, which is a question for `s71boot`'s own
   parasitics and delays and not for a zero-delay simulation. Until one
   of the two is done, `docs/41`'s W4 argument stands for the state and
   not for the decode.
2. **Split the merged instruction register, or price not splitting it.**
   Section 9.4: `opt_merge` stored two RTL registers in one flip-flop on
   60 bits, and every one of the fourteen disagreements it produced made
   the netlist worse than the RTL. `keep` on one of the two copies, or
   `opt_merge -nomux` off, would separate them; the cost is 30
   flip-flops and the benefit is that an upset reaches one consumer
   instead of two. **Nothing here measures whether that trade is worth
   making** — it measures that the trade is currently being made by the
   optimiser, silently, on the register `docs/42` ranked third by
   contribution.
3. **Re-run this campaign against a netlist whose state machines are not
   re-encoded**, or accept the re-encoding and re-stratify. Section 11:
   the one-hot `ctrl_fsm_cs` and `md_state_q` are the most lethal
   storage in the netlist per bit and have no RTL twin at all, so
   `docs/42`'s `controller` and `multdiv` strata do not describe them.
   `fsm_encoding` is a yosys attribute; measuring binary against one-hot
   on this design is one synthesis and one campaign.
4. **The 587 alias-mapped bits deserve a behavioural check.** Section
   12: they are mapped by yosys's own alias names and disagree on 5 of
   587, but nothing proves by behaviour that the flop under the name is
   the RTL's. A second workload that writes the PMP and the trap CSRs —
   `docs/46`'s supervisor is one — would move most of them into the
   trace-identified set and cost one campaign.
5. **`docs/42` section 9's first bullet is still the biggest gap and is
   now bigger.** The oracle is the run's output; an upset that leaves a
   netlist flip-flop wrong in a way this program never reads is MASKED
   at both levels. The gate-level campaign adds 3,553 flip-flops the RTL
   campaign never had an opinion about, and 44 of the 75 swept in
   section 11 are MASKED for exactly that reason.
6. **The remaining items of `docs/72` section 15 and `docs/73` section
   15 are unchanged**, and none of them is touched by this document.
