# 52 — Upsets through the NPU connection, measured before anything is hardened

`docs/51-npu-integration.md` section 14 item 7 is one line:

> **No fault-injection campaign through the connection.** `docs/16`
> measures upsets in the die through its own pins; nothing measures what
> an upset in the transport or the event engine does to an inference.

and section 18 makes it the next block, with the reason and the
discipline:

> This is the first block in the SoC that sits **between two measured
> things** and is itself unmeasured … **hardening before measuring is the
> mistake `docs/38` section 10 item 4 names**: the campaign's answer
> determines what needs protecting, and protecting the wrong thing costs
> area and buys nothing.

**This document is that campaign. 700 injections, seven strata of 100,
each run twice — 1,400 simulations, 31 minutes 34 seconds of wall time
on 18 processes** **[fact]**.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[planned]** =
an intention with nothing behind it yet.

**The pilot is untouched.** `docs/34` pins the TTIHP26b submission by
git blob hash and the shuttle closes 2026-09-21. Nothing in `hw/rtl/`,
`hw/tb/`, `tt/`, `formal/` or `hw/openlane/` was modified; seven files in
`hw/rtl/` are **read and instantiated**, and `hw/soc/flow/fi_npu.sh`
refuses to elaborate if `git diff` over `hw/rtl/` is not empty **[fact]**.
Section 14 lists every file.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| What is the silent-corruption rate of the connection? | **4.2 % ± 1.6 of upsets corrupt the inference with nothing in the hardware saying so** **[fact]**, design-weighted over the connection's 738 injectable bits. The campaign's own SDC column is **0 of 700** and section 6.2 is why that number must not be quoted instead |
| Which population carries it? | **The transport and the event engine, and not the queues.** `ser` 2.18 points, `engine` 1.71, `window` 0.21, `cfgreg` 0.07, and the two queue strata — **41.2 % and 9.2 % of the flip-flops — contribute zero** **[fact]**. Section 6.3 |
| Can an upset kill the machine? | **Yes, and only one way: 7 of 600, all of them a lost fabric response.** Four draws into the transport's half-period counter, one into its state, two into the window's state **[fact]**. Section 7.1 |
| Does the watchdog catch that? | **7 of 7, 100 % [64.6 – 100], every one at stage 2, and all seven then completed with the golden answer. Zero spurious escalations in 607 survivable upsets** **[fact]**. Section 7.1 |
| What did the golden model buy? | **Nine records in which the spike stream was right and the neuron state file was wrong** — the class `docs/42` section 9 names as the single largest reason its own rate is a lower bound, produced 9 times here **[fact]**. And it separated 41 wrong inferences from 45 deviations that were not wrong answers at all. Section 9 |
| Is the protection that is there doing anything? | **74 corrections and 5 rail disagreements in 700 injections, and an operator could see none of them** **[fact]**. Section 10 |
| Does the connection's own recovery earn its place? | **Yes, and the counterfactual says by how much**: with the bounded fetch wait removed, one of the three records it fired on goes from *a correct inference plus a fault flag* to *no inference at all* **[fact]**. Section 7.2 |
| Is `docs/51` section 18's reversal condition met? | **Yes.** 14 of 265 bring-up-phase draws corrupted the inference; the sequence's own read-backs caught 3; **every one of the 14 was silent to every hardware channel** **[fact]**. `W_DATA_HI` needs a read-back. Section 11.4 |
| What should be hardened first? | **Not the biggest structure and not the one with the highest rate.** Section 12 |
| Is the campaign complete over the connection? | **Yes: 730 of 730 elaborated flip-flop bits are named by a site** **[fact]**, verified by an independent Yosys census and not by the campaign's own controls. Section 5.2 |

---

## 2. What was built

Seven new files, all under `hw/soc/`, and one document:

| File | What it is |
|---|---|
| `hw/soc/tb/sw/fi_npu.c` | The workload. The `docs/51` section 7 demonstration and nothing else, as short as it can be made, checked against `sw/golden/lif_core.py`'s answer compiled into the ROM |
| `hw/soc/tb/tb_soc_npu_fi.v` | The instrument. Runs the whole SoC with the frozen die inside it, deposits one bit at one cycle, and prints a machine-readable record. It classifies nothing |
| `hw/soc/fi/npu_targets.py` | The site list, written once, in one language. It generates the Verilog the testbench includes **and** the dump the campaign checks that Verilog against |
| `hw/soc/fi/npu_campaign.py` | Controls, draw, run, classify, report |
| `hw/soc/fi/npu_coverage.py` | The other direction: given a Yosys census of every flip-flop that elaborates, which of them the site list does *not* name |
| `hw/soc/fi/npu_counterfactual.py` | The counterfactual build: a scratch copy of `soc_npu.v` with its one recovery mechanism removed, by an **asserted** substitution |
| `hw/soc/flow/fi_npu.sh`, `build_sw_npu_fi.sh`, `fi_npu_coverage.sh` | Build, elaborate once, census |

The division between the testbench and the campaign is the one `docs/16`,
`docs/41` and `docs/42` already use, for their reason: **the instrument
measures and the classifier judges, and they are different files.** A
testbench that classified would be a testbench that could be written
around a result.

---

## 3. Three populations, and one of them is inside frozen silicon

### 3.1 Why not one

`docs/51` section 14 item 1 records what is unprotected here, and the
list is **not homogeneous**:

> The two queues are `aer_fifo` and carry its entry parity, pointer
> voting and drop counting. The event engine's state, the transport's
> shift register, the window's captured request and every register in the
> NPUCFG block have **no protection at all**.

An upset in the transport corrupts **one register access**. An upset in
the event path corrupts **an inference**. An upset in the cause register
corrupts **what the operator is told**. Those lead to three different
decisions, so a campaign that sampled the block uniformly and reported an
average would describe none of them. `docs/41` section 3.1 states the
criterion this ranking uses — **persistence times silence**, not how
important a register sounds — and `docs/42` section 4.1 makes the
arithmetic argument for stratifying at all.

| stratum | population | bits | share | what it is |
|---|---|---:|---:|---|
| `ser` | transport | 134 | 18.2 % | the SoC's 40-bit shift engine and its phase counters |
| `die_ser` | transport, **frozen die** | 87 | — | `pilot_top`'s own half of the same transport |
| `window` | register path | 79 | 10.7 % | the node window's captured request, FSM and response |
| `cfgreg` | register path | 13 | 1.8 % | the NPUCFG control and cause registers |
| `engine` | event path | 140 | 19.0 % | the event engine's FSM and the show-ahead adapter |
| `evq_data` | event path | 304 | 41.2 % | the two queues' stored words, entry parity and read capture |
| `evq_ptr` | event path | 68 | 9.2 % | the two queues' voted pointers, dual-rail flag and drop counters |

**[fact, `python3 hw/soc/fi/npu_targets.py`]**. The share column is over
the connection's 738 bits and excludes the die.

`ser` at 134 flip-flops is the same number `docs/51` section 11 measured
with Yosys on `soc_npu_ser` standalone, which is an independent check
that the list is the whole of that module rather than a reader's
selection from it **[fact]**.

### 3.2 The die is inside the design under test, and its records are separable

`hw/rtl/pilot_top.v` is **instantiated, not copied** (`docs/51` section
3), so its flip-flops are reachable from this testbench. Injecting into
them is legitimate as measurement — `docs/16` already did, on the block
alone — but the records must be told apart, because:

- an upset in the **connection** is a property of a design **still
  open**. It can be hardened, and section 12 says what to harden;
- an upset in the **die** is a property of **silicon already
  committed**. `docs/34` pins the submission and the shuttle closes in
  eighteen days. Nothing found there can be fixed in that die.

So `die_ser` is a stratum of its own, every table prints it apart, and
**every design-weighted figure in this document is computed over the
connection's 738 bits with the die excluded** **[fact,
`npu_campaign.py`'s `OPEN_STRATA`]**. A rate that mixed the two would be
a number nobody could act on.

**And `die_ser` is deliberately not a re-measurement of the die.** It is
the die's own half of the serial transport — the pin synchronizers and
the 40-bit shift engine `soc_npu_ser.v` talks to — chosen so that **the
same 40-bit frame, implemented twice on the two sides of one pin
boundary, is measured with the same draws.** It is 87 of `pilot_top`'s
1,294 flip-flops, **6.7 %** **[fact,
`hw/soc/out/fi-npu/fi_npu_coverage.txt`]**, and `hw/soc/fi/npu_coverage.py`
prints that ratio with the sentence that it is not a coverage figure.
`docs/16` measured the whole block with its own target list and 255
injections and `docs/32` confirmed the result against the netlist;
nothing here supersedes either.

---

## 4. Two oracles, and the campaign reports both

### 4.1 What `docs/42` had to settle for, and what is available here

`docs/42` section 3 considered three oracles for the core and chose **an
undeposited run of the same program on the same design**, stating at
length what that costs:

> This oracle measures *deviation*, not *correctness* … *It also does not
> license a claim about latent corruption.* An upset that leaves a
> register wrong in a way this program never reads is MASKED here and
> would be SDC under an architectural-state oracle … **This is the single
> largest reason the measured SDC rate is a lower bound.**

**Here the specification is executable and it is compiled into the ROM.**
`hw/soc/flow/gen_npu_vectors.py` runs `sw/golden/lif_core.py` — which
`docs/10` section 13 makes the normative executable form of the section 4
equations — at **build time**, and emits the expected event stream and
the expected neuron state file as constants. `fi_npu.c` compares against
those constants and never against the hardware.

So this campaign carries **both** oracles and reports them side by side:

| | what it is | what it decides |
|---|---|---|
| **the run oracle** | the whole published result against the golden RUN | the CLASS. `docs/42`'s, unchanged |
| **the model oracle** | `fi_mask` bits F_LEN, F_STREAM and F_STATE, against `sw/golden/lif_core.py` | whether the INFERENCE was wrong |

**F_STATE is the one that is not available anywhere else in this
repository's SoC campaigns.** The program reads back the whole neuron
state file — `V` and `R` for all eight neurons — and compares it against
the model. That is an **architectural-state oracle for the NPU**, and it
is exactly what `docs/42` says its own campaign did not have. `docs/16`
section 1.6 names the class it catches and keeps `spikes_ok` and
`state_ok` apart for the same reason; `fi_mask` keeps them in two bits.
Section 9 counts how many records it actually separated, and the answer
is nine.

### 4.2 The self-checks are still a detection channel, and the two roles are kept apart

`fi_mask` is nonzero when the program noticed. That is a detection
channel, exactly as in `docs/42`. What is different is that the thing it
compared against is the specification, so the campaign is additionally
entitled to read three of its bits as *"the inference was wrong"*.

`npu_campaign.py` uses them in both roles and labels which is which. It
still decides MASKED from the whole compared result and never from
`fi_mask` alone, which is `docs/16` section 1.6's rule that the design's
own flags are never allowed to declare an answer correct.

**This has one consequence that dominates the reading of section 6 and it
is stated before the numbers rather than after: because the program
checks the inference against the model, and because `fi_mask` is an
announcement channel, a corrupted inference is DETECTED by construction
and can never be SDC.** Section 6.2 is what replaces the SDC column.

---

## 5. The controls, each of which is a way to report a confident number while measuring nothing

### 5.1 Nine checks, and every one of them can end the campaign

Seven of the nine **gate**: a failure aborts before any data point. The
other two — 4b and 4c — verify that their deposit landed and then
**report** the class rather than requiring one, and the text below says
why for each. **[fact, all nine passing,
`hw/soc/out/fi-npu/campaign.log`]**

**1. The elaborated design is the one `npu_targets.py` describes.** The
testbench dumps every site's index, stratum, name, `$bits` width and full
hierarchical path; the campaign compares all five. **96 sites, 825 bits,
every field agreeing.**

**1b. No target is a voted or continuously driven wire.** Every
`evq_ptr` target must end in `.bits`, which is `aer_ptr_bank`'s and
`aer_flag_rail`'s **storage** and never their `q` output. `docs/41`
section 8.1 records this campaign's ancestor depositing into a driven
voter output twice and reporting the result as if it said something about
the replicas.

**2. The clean run is clean in every channel.** 14,057 cycles, signature
`8c215696`, 19 console characters, 12 events collected against 22
injected, `CNT` = `0x000c0016`, no trap, no alert, no watchdog
escalation, no console framing error.

**2b. The NPU's own channels are silent too**, which control 2 of
`docs/42` had no equivalent of: the cause register, both drop counters,
the die's `CNT_EVQ_OVF` and `CNT_AXON_OOR`, the interrupt line, and all
three of `aer_fifo`'s protection reports are zero. A clean run in which a
queue had already corrected a pointer would make every CORRECTED record
in the campaign unattributable.

**2c. The program's own hang bound has margin, measured.** `fi_npu.c`
bounds a barrier wait at `FI_SPIN_MAX` polls of `EVQ_OUT` and publishes
the largest run of empty polls it actually saw. **The clean run's longest
is 21 and the bound is 168, which is 8.0x** — and the campaign aborts if
the bound is within 4x. A bound set without the measurement is either a
hang detector that fires on a healthy run, which would make every
injected classification meaningless, or one so loose that a wedged engine
costs more simulated time than the campaign has.

**3. It reproduces, and it is identical with the watchdog held off.**
The second condition is what makes the two columns of section 6
comparable.

**4a. A deposit lands.** Clearing `CTRL.IN_EN` mid-inference stops every
inbound event; it must not classify MASKED. It classifies **DETECTED**.

**4b. A deposit reaches inside `hw/rtl/pilot_top.v`.** The two halves of
the design under test are reached by different hierarchical paths and a
case arm that works for one says nothing about the other. This one gates
on the deposit landing and **reports** the class rather than requiring
one — bit 31 of the die's `rx_sh` mid-frame classifies MASKED, which is
a legitimate answer for a shift register that is about to be reloaded,
and a control that demanded otherwise would be a control tuned until it
passed.

**4c. A deposit can be absorbed.** Bit 7 of the capture queue's drop
counter, which nothing in this SoC can increment and which `soc_npu.v`
leaves unconnected, classifies **MASKED**. A campaign in which nothing is
ever MASKED is a campaign whose oracle is too tight.

**Control 4a earned its place immediately, and the fix was to measure
rather than to move the constant.** The first version drew its cycle at
one eighth of the measured window and the control failed. It was right
to: the window opens **before** the bring-up, which is two dozen
176-cycle serial frames, so the deposit landed on a register the program
had not written yet and then wrote — and MASKED was the correct answer.
The testbench now reports the cycle at which `ctrl_in_en` first goes high
(**4,700** **[fact]**) and the control places its deposit a quarter of
the way from there to the end of the window. **A control that fails
because its own setup was wrong is a control working; the temptation it
creates is to move the number until it passes, and that is how `docs/41`
section 6.6's list gets longer.**

**Control 4c is weaker than `docs/42`'s and this document says so.** The
capture queue's drop counter is the one site in this campaign that
`opt_clean` removes (section 5.2), so MASKED there is guaranteed by
construction rather than measured. It is kept because it is the cheapest
demonstration that the oracle admits MASKED at all, and it is labelled.

### 5.2 Coverage: every flip-flop in the elaborated connection

A site list is a list a person wrote. The campaign's own controls verify
that every site it **names** elaborates, which is the opposite question
from whether every flip-flop that **elaborates** is named — and only the
second one is about coverage. `docs/42` section 4.2 records what asking
the second question found on the core: three whole structures missing,
128 flip-flops of debug CSRs among them, none of it reachable from inside
the campaign.

`hw/soc/flow/fi_npu_coverage.sh` asks it here. Yosys elaborates `soc_npu`
with `pilot_top` **black-boxed** — the same scope `docs/51` section 11
measured — flattens it, and dumps every flip-flop that survives;
`hw/soc/fi/npu_coverage.py` attributes each one.

```
flip-flop signals elaborated : 84
  named by a campaign site   : 84
  not named                  : 0

flip-flop BITS elaborated    : 730
  covered by the campaign    : 730  (100.0 %)
  not covered                : 0

the site list declares       : 738 bits over 85 sites

SITES THE CAMPAIGN INJECTS INTO THAT SYNTHESIS REMOVES:
      8  u_cap.drop_cnt  (evq_ptr)
```

**[fact, `hw/soc/out/fi-npu/fi_npu_coverage.txt`]**

**The arithmetic closes: 738 declared, minus the eight bits of the
capture queue's unconnected drop counter, is 730** — the census total.
That is the same shape as `docs/42` section 4.2's 2,198 − 19 − 1 = 2,178,
and it is a bias in a known direction: it can only inflate the masked
fraction, and only by 8 of 738 bits.

**Two things in that script are load-bearing rather than tidy**, and both
were found by the census being wrong before they were added:

- `attrmap -modattr -remove keep_hierarchy` before `flatten`.
  `aer_fifo.v` carries the attribute on its pointer banks, its parity
  bank and its `rd_valid` rails as one of its two anti-merge defences, so
  without this line `flatten` skips all of them and the census silently
  misses 58 flip-flops per queue. `hw/soc/flow/syn_soc.sh`'s own comment
  records the same trap costing the hardened watchdog a wrong area
  number.
- `memory_map`. Without it the queues' storage stays a `$mem` cell and
  the 256 bits that are the largest single structure in this campaign
  would not be flip-flops at all.

**And one defect in the attribution, recorded because it produced a
plausible wrong answer.** The first version of `npu_coverage.py`'s regex
stripped the array index from a signal name, folding `u_inj.mem[0]` ..
`[7]` into one 128-bit `u_inj.mem`. It then reported all sixteen
queue-storage sites as *removed by synthesis* and 256 bits as
*uncovered*, and the two halves cancelled into a coverage figure of
**64.9 %** that looked exactly like a real hole in the campaign. It is
100.0 %. The lesson is `docs/38` section 7.5's: a number that is wrong in
two places at once can still look like a finding.

### 5.3 The queue sentinel, which is a harness decision with a cost

`aer_fifo`'s storage array has **no reset** — it is a memory, and a
memory that reset every entry could never be retargeted to an SRAM macro,
which is the argument that file's own header makes — and its entry-parity
bank has none for the same reason. So both are `x` in every slot the
design has not yet written.

**X is not a physical state.** A flip-flop in silicon powers up to a zero
or a one; `x` is the simulator declining to say which. `x ^ 1` is `x`, so
an injection into an X bit lands, changes nothing, and the run comes back
MASKED — which is exactly the quiet nothing a mis-targeted injector
produces (`docs/42` section 8.5 item 1).

So the testbench pre-loads both arrays with `0xF0F0`, which is what
`hw/tb/test_fi_campaign.py`'s `fill_fifo_sentinel` already does for the
die's own queues, with the same constant and for this reason: its TYPE
field is the reserved `2'b11` that `docs/10` section 7.1 says the node
drops and does not count, so a sentinel that reached the datapath could
not be mistaken for an event. The parity bank is filled with the
sentinel's **own** even parity — `^0xF0F0` is 0 — so every unwritten slot
is self-consistent; a fill that left the two disagreeing would arm the
queue's own parity check on entries nothing wrote, and the campaign would
be measuring a fault the harness injected.

**The fill changes nothing in the clean run: 14,057 cycles and signature
`8c215696` with it and without it** **[fact]**.

**What it costs, stated.** It is an uncontrolled difference between this
campaign and any future gate-level one, exactly as `docs/32` section 6
records for the die, whose netlist memories cannot be filled this way.
`docs/32` ran the experiment — the RTL campaign with the fill disabled —
and found it changed nothing on the four records it was suspected of
explaining. **Nothing equivalent has been run here**, and section 13 says
so.

### 5.4 Two harness defects, and what each cost

Recorded because each is a way a campaign can report a confident number
while measuring nothing, and because `docs/42` section 8.5 makes the same
list.

**1. Thirty-seven minutes of wall time thrown away by verifying deposits
at the end.** `hw/soc/fi/campaign.py` collects every record and then
checks that each deposit landed. The first run of this campaign did the
same, ran all 1,400 simulations, and then died on the **first** record it
checked, with a `before` value of `0000000000000000000000000000xxxx` —
the sentinel of section 5.3 was not yet written. Verification now happens
**inside the worker**, so a bad deposit ends the campaign on the first
record rather than after every simulation has been paid for, and the X
case has its own message naming the site and the fix.

**2. Two campaigns running against one output directory.** A launch that
appeared to fail had in fact started; a second launch produced two
processes writing the same `campaign.log` and racing to write the same
`records.csv`. Caught by the host's load average being twice what 18
processes should produce and by 37 concurrent simulations where there
should have been 18. Both were killed and the campaign of record was
re-run from a clean directory. **Nothing was published from that run**,
and it is recorded because a records file written by two campaigns would
have been indistinguishable from one written by either.

**3. `--replay` did not reproduce the report it replays, and the two
rows that were wrong were the two summary rows.** `csv` writes `True`
and `False` as strings and a non-empty string is truthy, so the
`frozen` column came back true for every record: the **CONNECTION**
aggregate was empty and the **FROZEN DIE** aggregate was 700 rows wide.
Every per-stratum table and every design-weighted figure was unaffected,
because they select on `stratum` — **which is exactly how a defect like
this survives being looked at**. `hw/soc/fi/campaign.py`'s `alert_seen`
docstring records the same defect in the other direction on the core's
campaign, and neither was caught by anything except running the replay
and diffing it. **It is now diffed: `--replay` on this campaign's
`records.csv` reproduces its `campaign.log` line for line from
`1. CLASSIFICATION` onward** **[fact]**, and that is the check `docs/44`
section 9.2 makes between two campaigns, made here of one campaign
against itself.

---

## 6. The measured distribution

### 6.1 Classification, in `docs/16` section 1.6's five classes

**With the watchdog armed — the SoC as `docs/51` built it:**

| stratum | bits | n | MASKED | CORRECTED | SDC | DETECTED | HANG |
|---|---:|---:|---:|---:|---:|---:|---:|
| `ser` | 134 | 100 | 81 | 0 | 0 | 19 | 0 |
| `window` | 79 | 100 | 95 | 0 | 0 | 5 | 0 |
| `cfgreg` | 13 | 100 | 80 | 0 | 0 | 20 | 0 |
| `engine` | 140 | 100 | 76 | 0 | 0 | 24 | 0 |
| `evq_data` | 304 | 100 | 98 | 0 | 0 | 2 | 0 |
| `evq_ptr` | 68 | 100 | 15 | **74** | 0 | 11 | 0 |
| **CONNECTION** | **738** | **600** | **445** | **74** | **0** | **81** | **0** |
| `die_ser` — frozen | 87 | 100 | 86 | 0 | 0 | 14 | 0 |

**With the watchdog held off — the counterfactual, and the only column
that differs:**

| stratum | MASKED | CORRECTED | SDC | DETECTED | HANG |
|---|---:|---:|---:|---:|---:|
| `ser` | 81 | 0 | 0 | 14 | **5** |
| `window` | 95 | 0 | 0 | 3 | **2** |
| every other connection stratum | unchanged | unchanged | unchanged | unchanged | 0 |
| **CONNECTION** | **445** | **74** | **0** | **74** | **7** |
| `die_ser` — frozen | 86 | 0 | 0 | 14 | 0 |

**[fact, `hw/soc/out/fi-npu/campaign.log` sections 1 and 2]**

Of the 88 DETECTED with the watchdog held off, **86 also produced a wrong
or missing answer**. `docs/16` section 1.6's warning applies unchanged:
detected is recoverable, not harmless.

**CORRECTED is reachable in this block, for the first time in an SoC
campaign in this repository outside the watchdog's own.** `docs/42`
reported it at 0 of 1,300 and kept the column at zero so that a design
which could reach it would be visibly different. This is that design:
`aer_fifo`'s triple-redundant pointers vote and reload every replica from
the vote on the next edge, and **74 of 100 draws into `evq_ptr` came back
CORRECTED, all 74 with the golden answer** **[fact]**. Section 10 is what
an operator can see of that, and the answer is nothing.

### 6.2 The SDC column is 0 of 700, and that number must not be quoted on its own

**It is a property of the oracle, not of the hardware.** `fi_npu.c`
compares the event stream and the whole neuron state file against
`sw/golden/lif_core.py`'s constants, and a nonzero `fail_mask` is an
announcement channel. So **every corrupted inference is DETECTED by
construction and SDC is structurally unreachable for it.** Reporting
"0 % SDC" would be reporting that this program noticed, which is a
statement about this program.

**The honest number is the one an application would see, and the campaign
carries the data to compute it.** Take a wrong inference — the model
oracle says F_LEN, F_STREAM or F_STATE — and ask whether any **hardware**
channel announced it: the NPUCFG cause register's fault bits, either drop
counter, the die's `CNT_EVQ_OVF` or `CNT_AXON_OOR`, the interrupt line, a
bus error at the core, an Ibex alert pin, or the watchdog.

| | n | 95 % Wilson |
|---|---:|---|
| upsets that corrupted the inference | **41 of 700** | — |
| of those, announced by **hardware** | **3** | — |
| **of those, silent to every hardware channel** | **38** | — |

**[fact]**

| stratum | bits | share | silent wrong inference | contribution | 95 % |
|---|---:|---:|---:|---:|---|
| `ser` | 134 | 18.2 % | **12 / 100** | **2.18 %** | 7.0 – 19.8 % |
| `engine` | 140 | 19.0 % | **9 / 100** | **1.71 %** | 4.8 – 16.2 % |
| `window` | 79 | 10.7 % | 2 / 100 | 0.21 % | 0.6 – 7.0 % |
| `cfgreg` | 13 | 1.8 % | 4 / 100 | 0.07 % | 1.6 – 9.8 % |
| `evq_ptr` | 68 | 9.2 % | **0 / 100** | 0.00 % | 0.0 – 3.7 % |
| `evq_data` | 304 | 41.2 % | **0 / 100** | 0.00 % | 0.0 – 3.7 % |
| **connection, design-weighted** | **738** | | | **4.17 % ± 1.60** | |

**[fact for the measured columns; the contributions are arithmetic on
them, `[estimate]`]**

**Note added 2026-09-05: the `engine` row's 1.71 points and `docs/56`'s
0.58 are not a before and after.** This table draws 100 injections
proportionally over the 140-bit `engine` stratum, gets 9, and weights
9 % by 140 of 738 bits. `docs/56-npu-event-engine-hardening.md` section
3.4 splits the same stratum into five sub-strata, draws 100 into each,
weights each by its own width and gets 4.713 bit-equivalents of 140 —
3.37 % of the stratum, **0.58 points** of a connection that had grown to
809 injectable bits by then. The RTL did not change between the two
figures: `docs/55`'s campaign of record measured the same unsplit stratum
at 8 of 100. The two are different estimators of one quantity over two
denominators — on 809 bits this table's own 9 % would weight to 1.56, not
1.71 **[estimate]** — and **neither may be subtracted from the other**.
The hardening that followed is measured on replayed draws, in `docs/56`
section 8, and that is where a before and after exists.

Two further figures from the same records **[fact]**:

- **the connection-weighted rate of ANY silent deviation** — a wrong
  answer *or* a counter, a block end state or a console stream that
  differs, with no hardware channel raised — is **6.83 % ± 1.97**;
- **the frozen die's own transport, reported apart: 11 of 100 silent
  wrong inferences [6.3 – 18.6], and 0 of the 11 announced by
  hardware.**

**Read the two zero rows correctly.** `evq_data` and `evq_ptr` produced
no silent wrong inference in 100 draws each. That is not a rate of zero;
it is a rate below about 3.7 %, and `docs/42` section 4.5's reading of a
zero row applies here word for word. What makes those rows load-bearing
anyway is that they are **41.2 % and 9.2 % of the block**, so even at the
top of their intervals they cannot be where the rate lives.

### 6.3 Ranked by consequence, which is neither the flip-flop count nor the rate

`docs/42` section 6.3 found the core's flip-flop count and its risk close
to **inversely** ordered. Here they are close to **unrelated**, and the
table has three columns because there are three consequences:

| stratum | bits | share | corrupts an inference, silently | kills the machine | lies to the operator |
|---|---:|---:|---:|---:|---:|
| `evq_data` | 304 | 41.2 % | **0 / 100** | 0 / 100 | 0 / 100 |
| `engine` | 140 | 19.0 % | 9 / 100 | 0 / 100 | 1 / 100 |
| `ser` | 134 | 18.2 % | **12 / 100** | **5 / 100** | 2 / 100 |
| `window` | 79 | 10.7 % | 2 / 100 | **2 / 100** | 0 / 100 |
| `evq_ptr` | 68 | 9.2 % | **0 / 100** | 0 / 100 | 11 / 100 |
| `cfgreg` | 13 | 1.8 % | 4 / 100 | 0 / 100 | **16 / 100** |

**[fact]**. "Lies to the operator" is a record in which the block's own
telemetry reported a fault **and the inference was correct** — a false
alarm, counted below at 30 of 700.

**Three readings, and they point at three different remedies.**

**The largest structure in the block is the safest one.** `evq_data` is
41.2 % of the connection's flip-flops and produced nothing at all: 98 of
100 MASKED, 2 DETECTED. The reason is not robustness, it is occupancy —
at any moment the queues hold a couple of live entries out of eight
slots, so most of those 304 bits are storage nothing will read. **A
hardening wave that started with the biggest structure would spend its
whole budget there.**

**The block with the highest per-bit rate contributes almost nothing.**
`cfgreg` is thirteen flip-flops and produces a false fault report in 16
of 100 draws — the highest per-bit consequence anywhere in this campaign
— and it is 1.8 % of the block, so it contributes 0.07 of the 4.17 points
of silent corruption. That does not make it unimportant; it makes it
important for a **different reason**, which is section 12 item 3.

**The transport carries both of the things that matter and it is not the
biggest.** 2.18 of the 4.17 points of silent corruption, and 5 of the 7
machines that died.

### 6.4 The same frame, twice, on the two sides of a pin boundary

`ser` and `die_ser` implement the same 40-bit mode-0 frame — one in RTL
this project can still change, one in silicon `docs/34` has committed —
and the campaign asked both the same question with the same draws.

| | bits | silent wrong inference | hardware announced | dead machines |
|---|---:|---:|---:|---:|
| `ser`, the SoC's half | 134 | 12 / 100 | 0 | **5** |
| `die_ser`, the die's half | 87 | 11 / 100 | 0 | **0** |

**[fact]**

**Per draw the two are indistinguishable at this sample size; per bit the
die's half is about 1.4x worse**, because it does the same job in
two-thirds of the flip-flops **[estimate, 11/87 against 12/134 is
1.41]**. Both
are completely silent: **neither side of the boundary has any way to tell
a host that a frame went wrong.**

The one asymmetry is real and is a property of the SoC rather than of the
die: **all five dead machines are on the SoC's side.** An upset in
`ser.tick` or `ser.state` leaves a frame that never ends, so `busy_o`
never falls, so `win_state` never leaves `W_WAIT`, so `rvalid` never
returns and Ibex — a two-stage in-order machine that stalls the pipeline
on a load — waits for ever. **The die cannot do that to the SoC**,
because the die is a slave on a clock the SoC drives: a corrupted die-side
frame returns wrong data, and wrong data is a wrong answer rather than a
hang.

---

## 7. The counterfactuals

### 7.1 The pair: what the machine does with no backstop, and what the watchdog does about it

Every injection is run **twice** — same site, same bit, same cycle, same
seed — once with `wdog_dis_i` low and once with it high. `soc_wdog.v` W1
samples that pin once as power-on reset releases and ignores it for ever
after, so it is a board strap and not a back door.

**This is `docs/42` section 7.1's counterfactual asking a different
question.** There it asked whether the backstop reaches a corrupted
**core**. Here it asks whether it reaches **a CPU that has stalled on a
peripheral** — and that is a mechanism nothing in this repository had
measured, because the node register window is the first slave in the SoC
that holds the fabric response for 176 cycles by design.

| truth, from the disarmed run | n | escalated | quiet | caught | 95 % |
|---|---:|---:|---:|---:|---|
| **OK** — finished, golden answer | 607 | **0** | 607 | 0.0 % | 0.0 – 0.6 % |
| **WRONG** — finished, wrong answer | 86 | 0 | 86 | 0.0 % | 0.0 – 4.3 % |
| **DEAD** — never finished | **7** | **7** | 0 | **100.0 %** | 64.6 – 100 % |

**[fact]**

**(a) 7 of 7. Every upset that leaves this SoC dead is caught, at stage
2, and all seven then completed with the golden answer** after the reset
restarted the program **[fact]**. Time from the deposit to the first
transition on a pin: **min 1,913, median 1,987, max 4,902 clocks**,
against a programmed timeout of 2,048 **[fact]**.

**(b) Zero spurious escalations in 607 injections the machine would have
survived, and no outcome made worse in 700** **[fact]**. That is
`docs/42`'s result reproduced on a different block; it is **not**
`docs/43` section 8.4's, whose seven spurious escalations came from W7's
cadence window, which is built here and not armed.

**(c) The seven are all one mechanism and it is six flip-flops' worth of
state.** Four draws into `ser.tick` — the transport's half-period counter
— one into `ser.state`, and two into `win_state` **[fact]**. Nothing else
in 600 connection draws produced a dead machine.

> **THE ONLY WAY THIS BLOCK KILLS THE MACHINE IS BY LOSING THE FABRIC
> RESPONSE, AND THE WATCHDOG'S ANSWER TO THAT IS A SYSTEM RESET.** Seven
> of seven is as complete as a catch rate gets, and it is worth being
> exact about what was caught: the SoC rebooted and re-ran the whole
> inference. Section 12 item 1 is the cheaper answer, and the campaign is
> what says it is worth building.

**(d) 86 of 86 wrong answers escalated nothing, and that is not a
criticism.** A watchdog has no view of a result. The program kept
accessing the NPU, and therefore kept kicking, with a corrupted
inference. `docs/42` section 8.1's `x23` finding has no analogue here for
a reason worth recording: **this workload's kick is inside the register
accessor**, so a machine that stops making accesses stops kicking, which
is precisely the failure mode being measured. Section 13 says what that
leaves uncovered.

### 7.2 The second counterfactual: the connection's own recovery, removed

"The protection works" is not a measurement unless the same experiment on
the design without it produces a different number. `docs/41` section 8.3
built its whole result that way.

**The connection has exactly one recovery mechanism of its own.**
Everything else it carries it inherited: both queues are `hw/rtl/aer_fifo.v`
and their pointer voting, entry parity and dual-rail `rd_valid` come with
them — and that file is in the frozen directory, so there is no
`HARDEN = 0` to build and none may be made. What `soc_npu.v` added is the
**bounded wait on an injection-queue fetch**, which expires, returns the
engine to idle, and latches `IRQ_CAUSE.FETCH_ER`. `FETCH_MAX` is
constrained to 1..15 by an elaboration guard, so it cannot be turned off
with a parameter.

`hw/soc/fi/npu_counterfactual.py` therefore generates a scratch copy of
`soc_npu.v` with the expiry arm and its report removed, by an **asserted**
substitution: if the anchor text is not present exactly once, the script
fails. A generator that quietly produced an unmodified copy would give a
counterfactual identical to the design, which reads as *"the mechanism
does nothing"* — and `docs/49` section 8.1 is four pages on a flow step
that elaborates, exits zero and changes nothing. `fi_npu.sh` writes a
`SUBSTITUTED` marker into the build directory so a records file from that
build cannot be mistaken for one from the design of record.

**The bound fired on three records in 700. Replayed verbatim — same site,
same bit, same cycle — against the build without it [fact]:**

| record | design of record | counterfactual |
|---|---|---|
| `engine.ev_state` bit 0, cycle 2,920 | **12 events, 6 frames, signature `8c215696` — the golden inference** — plus `IRQ_CAUSE` = `0x40` | **0 events, 0 frames, signature `8d61daa3`** |
| `evq_data.inj_mem5` bit 15, cycle 8,058 | 11 events, `IRQ_CAUSE` = `0x40` | 11 events, **`IRQ_CAUSE` = `0x00`** |
| `evq_data.inj_mem3` bit 11, cycle 5,954 | 6 events, `IRQ_CAUSE` = `0x40` | 6 events, **`IRQ_CAUSE` = `0x00`** |

> **ON ONE RECORD IN THREE THE BOUNDED WAIT WAS THE DIFFERENCE BETWEEN A
> CORRECT INFERENCE AND NO INFERENCE AT ALL. ON THE OTHER TWO IT WAS THE
> DIFFERENCE BETWEEN A REPORTED FAULT AND A SILENT ONE.** Neither
> outcome was available without running it.

That is a **positive** result and it is worth contrasting with `docs/43`
section 8.4, where the same kind of experiment found W7 *"built, proved,
measured, and its measured value on this workload is zero"*. The
difference is not that one mechanism is better designed; it is that this
one addresses a failure this workload produces and that one did not. **A
mechanism's value is a property of the pair, and only a campaign can
report it.**

**Three records is three records.** The interval on "one in three" is
enormous and this document does not quote a rate from it. What the
replay establishes is that the mechanism is **reachable, exercised and
consequential**, which is the claim `docs/51` made for it structurally
and could not measure.

---

## 8. The exposure arithmetic: 176 cycles per register access

`docs/51` section 8.1 measures a register access at **176 clock cycles**.
`docs/51` section 11 measures the transport at **134 flip-flops**, which
is 18.2 % of the connection. **Those two numbers pull in opposite
directions and a per-flip-flop rate cannot say so**, which is exactly the
kind of thing this section exists to make arithmetic.

The testbench counts, inside the measured window, the cycles for which
each of the three engines is busy **[fact, the clean run]**:

| | busy cycles | of the 12,012-cycle window | flip-flops | of the connection's 738 |
|---|---:|---:|---:|---:|
| the serial transport | 10,200 | **84.9 %** | 134 | **18.2 %** |
| the node window FSM | 7,308 | 60.8 % | 79 | 10.7 % |
| the event engine | 3,260 | 27.1 % | 140 | 19.0 % |

> **THE TRANSPORT IS A FIFTH OF THE FLIP-FLOPS AND FIVE SIXTHS OF THE
> TIME.** A block that is slow is exposed for longer, and the whole
> content of "176 cycles per register access" as a reliability statement
> is in that line.

**`docs/53` reaches the same conclusion from the other side and the two
are worth reading together, with their denominators kept apart.** That
document measures the transport at **182.5714 cycles per serial frame
against 6.8571 per inbound pin event** and concludes it is **93 to 98 %
of the event path in every workload it ran** **[fact, `docs/53` sections
5 and 6]**. The 84.9 % above is a **different fraction**: it is over the
whole measured window of a program that also boots, drives a UART and
runs a CPU, not over the NPU work alone. The two do not contradict each
other and neither substitutes for the other — `docs/53` says the
transport dominates the *throughput*, this says it dominates the
*exposure*, and they are the same fact about the same 176 cycles seen
from two ends.

**And the per-record data says the exposure is not merely arithmetic — it
is the whole of the effect** **[fact]**:

| stratum | deposits landed | MASKED | DETECTED | HANG |
|---|---|---:|---:|---:|
| `ser` | while the transport was **busy** (89) | 70 | **14** | **5** |
| `ser` | while it was **idle** (11) | **11** | 0 | 0 |
| `die_ser` | while the transport was **busy** (84) | 70 | **14** | 0 |
| `die_ser` | while it was **idle** (16) | **16** | 0 | 0 |

**Every consequential upset in either half of the transport landed while
a frame was in flight. Not one of the 27 idle-cycle deposits mattered.**
The mechanism is plain in the RTL once the measurement points at it:
`ST_IDLE`'s transition reloads `tx`, `rx`, `bit_cnt`, `hcnt` and `tick`
from the caller, so an upset that arrives between frames is overwritten
before the next frame reads it. **The transport is not vulnerable; a
transport with a frame in it is.**

**Two consequences, and the second is the one that matters for a
decision.**

**Read as a susceptibility, the transport's rate should be scaled by its
duty cycle and this campaign already did that.** 89 of 100 `ser` draws
landed in a busy cycle, against the 84.9 % the clean run measures — the
draw is uniform in the window, so the two agree, and the stratum's
measured rate is already a time-weighted one for this workload **[fact,
`[estimate]` for the agreement being the reason]**.

**Read as a design statement, the exposure moves with the workload and
the rate moves with it.** A program that made fewer register accesses and
more events would leave the transport idle for most of the window and its
contribution would fall; a full-scale node loading 16,384 weight words
over this transport (`docs/51` section 3.4) would leave it busy for
essentially all of a very much longer window. **The 2.18 points this
campaign attributes to the transport are a property of this workload's
access pattern and section 13 says so.**

---

## 9. What the golden model bought

`docs/42` section 3 chose the undeposited run as its oracle and said what
it could not license. This campaign has that oracle **and** the
specification. These are the records the second one separated **[fact]**:

| | n |
|---|---:|
| differs from the golden RUN (`docs/42`'s oracle) | **86** |
| of which the MODEL says the inference was wrong | **41** |
| — wrong spike stream | 32 |
| — wrong neuron state file | 32 |
| — **wrong state file, RIGHT spike stream** | **9** |
| — wrong spike stream, right state file | 9 |
| of which the model says the inference was RIGHT | **45** |

**Three things that measurement buys, in the order they matter.**

**1. Nine records in which the answer looked right and the machine was
wrong.** The spike stream — twelve words, six spikes and six barrier
echoes — matched the model exactly, and the neuron state file did not.
`docs/16` section 1.6 names that class precisely: *"An upset that leaves
V wrong but produces no wrong spike inside an eight-command run has not
been masked; it has been deferred."* **Under an output-only oracle all
nine are MASKED.** They are 22 % of the wrong inferences in this
campaign, and by stratum they are `ser` 4, `die_ser` 3, `window` 2
**[fact]** — that is, the *configuration and transport* path, which is
exactly where a corrupted write lands in state that the next frame will
read and this frame will not.

> **`docs/42` SECTION 9's FIRST BULLET SAYS AN ARCHITECTURAL-STATE ORACLE
> IS THE SINGLE LARGEST REASON ITS OWN RATE IS A LOWER BOUND. THIS
> CAMPAIGN HAD ONE, AND IT FOUND NINE RECORDS IN 700 THAT THE OTHER
> ORACLE WOULD HAVE CALLED CLEAN.**

**2. It separates a wrong answer from a moved counter.** 45 of the 86
deviations are not wrong inferences at all: the run produced the golden
twelve events and the golden state file, and what differed was the cause
register, an event count or the console. **`docs/42`'s oracle could not
have told those apart from a corrupted inference** — it compares the
whole published result and reports that it differs. Here the difference
is a class boundary: **28 of those 45 set nothing in `fi_mask` but F_TELEM**
— the block reported a fault that did not happen (section 11.2) — **14
set nothing but F_CNT**, the hardware's own event counters having been
flipped, and **3 are a bring-up read-back that failed**.

**3. It removes a caveat rather than adding a claim.** `docs/42` had to
say its oracle *"does not license any claim that the golden run is
correct"*, because the reference run and the injected run share whatever
the RTL gets wrong. `sw/golden/lif_core.py` is an independent
implementation of `docs/10` section 4's equations in a different
language, run at build time, and `docs/51` section 7.1 already
establishes that the SoC's run and the pilot's own suite are the same
inference on the same numbers. **A wrong-answer record here is a
deviation from the specification and not only from another run of the
same RTL.**

**What it does NOT buy, stated because the gap is the same shape as the
one it closes.** The state file is read back **once**, at the end, over
sixteen 176-cycle frames. An upset that corrupts a neuron's state and is
then overwritten by a later frame's arithmetic is invisible here exactly
as it would be under `docs/42`'s oracle. This is an
architectural-state oracle **at one instant**, not a continuous one.

---

## 10. The protection that is there, and what an operator can see of it

`docs/51` section 14 item 1 is precise about the position: the queues
carry `aer_fifo`'s protection because they *are* `aer_fifo`, and
`soc_npu.v` brings `ptr_mismatch` and `par_err` out of both instances and
**connects them to nothing** — because this SoC has no fault-counter
block of its own and NPU-only telemetry does not belong outside BUSSTAT,
which `docs/41` owns. `rv_mismatch` is not brought out at all.

The campaign counted every one of them, at the bench **[fact]**:

| mechanism | records it moved on | of those, golden answer | of those, announced to software |
|---|---:|---:|---:|
| pointer vote corrected a replica | **74** | **74** | **0** |
| `rd_valid` rails disagreed | 5 | 5 | **0** |
| entry parity discarded an entry | 2 | 0 | 2 |
| the engine's bounded fetch wait expired | 3 | 0 | 3 |

> **SEVENTY-NINE UPSETS WERE ABSORBED BY MECHANISMS THAT WORKED, AND NO
> SOFTWARE AND NO PIN COULD SEE ANY OF THEM.** In silicon a corrected
> pointer upset is indistinguishable from no upset at all.

The two that *were* announced were announced **by their consequence and
not by the mechanism**: an entry the parity check discarded is an event
that never arrived, so the program's cross-check of the hardware's own
in/out counts caught it. The fetch bound is the exception and it is the
only one of the four with a channel: it latches `IRQ_CAUSE.FETCH_ER`, and
all three records reported it.

**This is the same separation `docs/43` draws for the register file's
correction counter** — read hierarchically, not a pin, and the report
says so where it uses it — and it is the same problem: a protection with
no telemetry cannot be trusted in flight, because nothing distinguishes
*"the mechanism has never fired"* from *"the mechanism is broken"*.
`docs/16` section 7.6 makes the general form of the argument.

**And it is cheap to close.** The cause register has seven bits and 25
spare; the two queue instances already drive four wires that go nowhere.
Section 12 item 2.

---

## 11. Findings

### 11.1 The connection's only lethal failure is a lost fabric response, and it is a handful of flip-flops

Seven dead machines in 600 connection draws, and **all seven are the
transport's phase state or the window's state** — `ser.tick` ×4,
`ser.state` ×1, `win_state` ×2 **[fact]**. The chain is one sentence
long: a corrupted phase leaves a frame that never ends → `busy_o` never
falls → `win_state` never leaves `W_WAIT` → `rvalid` never returns →
Ibex stalls the pipeline on the load for ever.

`docs/51` section 8.2 already recorded that the window withholds `gnt`
for 176 cycles and that this is the first slave slow enough to make a
fabric property visible. **What this campaign adds is that the same
property is the block's only way to kill the SoC**, and that a
system-level backstop is currently the only thing that answers it.

### 11.2 The cause register produces a false fault report in 16 of 100 draws

Thirty records in 700 have the block's own telemetry reporting a fault
**on a run whose inference was correct**, and **two of the thirty are on
a run that was otherwise entirely clean** **[fact]**. Where they come
from:

| site | records | what the operator is told |
|---|---:|---|
| `sticky_inj_ovf` bit 0 | 7 | an `EVQ_IN` write was refused by a full queue. It was not |
| `sticky_fetch_er` bit 0 | 7 | an injection fetch expired. It did not |
| `inj_drop_cnt` | 11 | the injection queue dropped events. It did not |
| `irq_mask` | 2 | — |
| `ser.rx`, `engine.ev_state` | 3 | — |

**Twenty-eight of the thirty set nothing in `fi_mask` except F_TELEM**:
the twelve events were right, the neuron state file was right, the
hardware's own in/out counts agreed with the stream, and the part
reported a fault **[fact]**.

This is `docs/41` section 3.1's criterion producing exactly the failure
it predicts. A sticky fault bit is **persistent** — nothing rewrites it
until software clears it — and its corruption is **silent**, because
there is no second copy to disagree with. `docs/41` section 3.2's table
of the watchdog's own worst bits is the same list in a different block.

**Why it matters more than 0.07 points of corruption rate.** A part that
reports faults that did not happen is a part whose fault reports stop
being actionable. Every recovery policy `docs/09`'s S2 supervisor might
implement reads this register.

### 11.3 The event engine's counters are protected by software and by nothing else

Of the 24 `engine` records that produced a wrong answer, **14 are
`cnt_in` or `cnt_out`** and their only symptom is that the hardware's own
count of events delivered and drained disagrees with the stream the
program collected **[fact]**. `fi_npu.c` cross-checks the two — as
`test_ibex.c` check 26 does — so `F_CNT` fires and the record is
DETECTED.

**That detection is entirely a property of the software.** Nothing in
`soc_npu.v` compares those counters against anything. A driver that read
`NPUCFG.CNT` to decide how many events to expect, which is the obvious
use for it, would be reading a corrupted number with nothing to say so.
`docs/51` section 7.2 calls the cross-check *"a second path to the same
conclusion"*; the campaign's finding is that in this design it is the
**only** path.

### 11.4 `docs/51` section 18's reversal condition is met: the weight and configuration path needs a read-back

`docs/51` section 18 wrote the condition under which this campaign could
invalidate a decision that document had just taken:

> The campaign can invalidate a decision this document has just taken —
> if an upset in the transport can corrupt a weight word silently, then
> `W_DATA_HI`'s commit needs a read-back that the bring-up sequence does
> not currently do.

**It can.** Of the 265 draws that landed before the block was enabled —
the state clear, the eight configuration writes, the four ECC-checked
weight words and their read-backs — **14 corrupted the inference. The
bring-up sequence's own read-backs caught 3. Every one of the 14 was
silent to every hardware channel** **[fact]**.

The clearest single record is `ser.tx` bit 32 at cycle 3,081 **[fact]**.
`tx` is the 40-bit frame `{WR, ADDR[6:0], data[31:0]}`, so bit 32 is
`ADDR[0]`: **the write went to the wrong register**, the die accepted it,
and `fi_npu.c`'s one configuration read-back — `CFG_THRESH`, which
`docs/51` section 7.2 explains was put there for exactly this class —
read the register that was **not** corrupted and passed.

**The die's ECC does not help and it is worth saying why.** A weight word
whose value is corrupted on the way in is encoded as a **valid codeword
of the wrong value**. `CNT_SEC` and `CNT_DED` stay at zero, the program's
check of them passes, and the inference comes out wrong with a clean bill
of health. This is the failure `docs/51` section 7.2 says looks like an
arithmetic defect.

**What closes it** is a read-back of what was committed rather than of
one register chosen in advance: `W_ADDR` after every word (which the
sequence already reads once, at the end) is not enough, and reading the
weight array back is not possible — `docs/10` section 10's map has no
weight read port. **The available answer is to read back every
configuration register that was written, at 176 cycles each**, which for
the eight of them is 1,408 cycles once per bring-up **[estimate,
arithmetic on `docs/51` section 8.1's measurement]**. Section 12 item 4.

---

## 12. What to harden first, ranked by consequence

**Ranked by what a fix buys and not by where the flip-flops are.** Every
item names the measurement it rests on. None of it is built; this
document measures and recommends, and `docs/38` section 10 item 4's
discipline is that the campaign comes first.

**1. Bound the transport's frame and the window's response.**
*[the measurement: 7 of 7 dead machines, section 7.1; 5 of them
`ser.tick` and `ser.state`, 2 `win_state`]*

`soc_npu_ser.v`'s own header says the transport *"has no timeout. A frame
always completes in a fixed number of cycles because nothing in the
protocol can stall it"* — which is true of the protocol and false of the
silicon, because a flipped `tick` or `state` is a frame that does not
complete. A frame-length bound in `soc_npu_ser` that forces `ST_IDLE`,
raises `done_o` with an error flag and lets the window return a bus
error would convert **5 of 5** of those records from *a system reset* to
*a load access fault the program can handle*, and a matching bound on
`win_state` covers the other 2.

**This is the third instance of one pattern in this repository and the
first two are why it is first here.** `hw/rtl/pilot_top.v` section 8
bounds its dispatcher's `D_FETCH` wait because `docs/16` section 5.1
measured five HANGs and no fault indication at all; `soc_npu.v` bounds
its injection fetch for the same reason, and section 7.2 above measures
that bound converting a lost inference into a correct one. **The
transport is the one place in this block where the pattern was not
applied, and it is the one place that kills the machine.**

Cost **[estimate]**: a counter the transport already has (`tick` is 16
bits and a frame is 171 cycles), one comparator, one flag, and a bus
error path the window already implements for `win_err_q`. It is not TMR
and it is not parity.

**2. Give the queues' protection somewhere to report.**
*[the measurement: 79 absorbed upsets, 0 visible, section 10]*

Four wires already leave the two `aer_fifo` instances and go nowhere.
The cause register has 25 unused bits. Two sticky bits — a corrected
pointer disagreement and a discarded entry — plus two saturating counters
would make the entire protection of this block observable, and would
distinguish *"nothing has happened"* from *"the protection is broken"*,
which nothing currently can.

`docs/51` section 14 item 1 declined this on the grounds that inventing a
fault-counter block here would put NPU-only telemetry outside BUSSTAT.
**That argument is about where the counters live, not about whether the
events are visible**, and the cause register is already this block's own
report. The campaign's contribution is the number: 79 events in 700
injections is not a hypothetical.

**3. Triple-modular-redundant the thirteen-bit control and cause bank.**
*[the measurement: 16 false fault reports in 100 draws, section 11.2]*

`ctrl_in_en`, `ctrl_out_en`, `irq_mask`, `sticky_inj_ovf` and
`sticky_fetch_er` are thirteen flip-flops that are written once and never
rewritten by the block, and whose corruption is silent. That is
`docs/41` section 3.1's rule verbatim, and `docs/41` section 3.2's own
protected word is 22 bits — this is smaller.

Cost **[estimate]**: `hw/soc/rtl/soc_tmr_bank.v` exists, is proved, and is
already instantiated in the watchdog; three replicas of thirteen bits is
**26 additional flip-flops**, which against the connection's 717 is
**3.6 %** and against `docs/51` section 11's 57,805.50 um² is a fraction
of a percent. Nothing here has been synthesised and no area is claimed.

**4. Read back the configuration the bring-up wrote.**
*[the measurement: 14 of 265 bring-up-phase draws, 3 caught, section
11.4]*

This is **software**, not silicon, and it is the cheapest item on the
list. `fi_npu.c` and `test_ibex.c` read back **one** configuration
register; reading back all eight costs **1,408 cycles once per bring-up**
**[estimate, eight of `docs/51` section 8.1's 176]**.

**It closes half the class and this document is precise about which
half.** Of the eleven bring-up-phase records that corrupted the inference
and passed every read-back the sequence does, **six are in the transport
on one side of the pin boundary or the other and five are in the event
engine** — the show-ahead adapter and the AER strobe, which are not
configuration at all and which a configuration read-back cannot see
**[fact]**. And a read-back covers the eight configuration **registers**
and **not the weight array**, because `docs/10` section 10's map has no
weight read port: a weight word corrupted on the way in is stored as a
valid SECDED codeword of the wrong value and there is no way to ask the
die what it holds.

**So the honest form of the recommendation is: read back every
configuration register, and record that the weight path remains
unverifiable through this interface.** Closing the second half needs
something the die does not have — a weight read port or a checksum
register — and that is a full-scale-node requirement rather than a
change to this SoC. `docs/10` section 14 is where it belongs.

**5. Nothing for the queues.**
*[the measurement: `evq_data` 0 silent wrong inferences in 100 draws over
41.2 % of the block; `evq_ptr` 0 in 100 over 9.2 %, with 74 CORRECTED]*

The two largest structures in the connection carry its whole protection
budget already and produced no silent corruption at all. **A hardening
wave aimed at the biggest structure would have started here and bought
nothing**, and `docs/51` section 11 already records that the queues are
53.5 % of the connection's area. That is the concrete form of what
`docs/38` section 10 item 4 warns about.

**And one thing this campaign does NOT recommend.** Parity or ECC over
the transport's `tx` and `rx` shift registers, which is where 12 of the
41 wrong inferences live. It would be a check over a register that
changes every half period, it would not catch the die-side half of the
same failure (`die_ser`, 11 more), and the die-side half cannot be fixed
at all. **The cheaper and more complete answer to a corrupted frame is a
read-back at the register level (item 4) and an end-to-end check at the
inference level, both of which cover both sides of the pin boundary.**

---

## 13. What this campaign does NOT cover

Stated at length, because this repository has been bitten by a green
check read wider than the thing it examined — `docs/41` section 6.6 now
lists eleven instances and `docs/51` section 13 item 2 is the twelfth.
**Even the clean numbers here would not license the claim that the
connection is adequately protected.** Worst first.

- **The SDC column is zero because of the oracle, and section 6.2's 4.2 %
  is the number that replaces it.** Anyone quoting "0 % SDC" from the
  classification table would be quoting a property of a program that
  checks its answer against the specification, on a block whose eventual
  application may not.
- **One workload, one stimulus, one geometry, one seed.** 8 x 8, one
  node, six frames, 22 events, no tiling, no multi-pass, no ECC
  injection, no second node. `docs/51` section 15 says the same of its
  own demonstration and this campaign inherits it whole. A workload with
  a different ratio of register accesses to events would move the
  exposure of section 8 and therefore the rates of section 6.2.
- **The rates are conditional on an upset having landed in the injection
  window**, on a uniform choice of flip-flop within a stratum and a
  uniform cycle. **It is not a failures-in-time figure** and cannot be
  turned into one without a cross-section this project has not measured
  and an orbit-flux model it does not have. `docs/16` section 7.5.
- **RTL, single-bit, flip-flop only.** No gate-level netlist, no
  back-annotated timing, no multi-bit strike, no single-event transient
  in combinational logic. `docs/32` section 5.1's 370 of 370 like-for-like
  agreement is the strongest evidence in this repository that RTL
  injection is trustworthy — and it was established on the die, not on
  this connection, whose netlist has never been simulated at all
  (`docs/51` section 11's last paragraph).
- **The queue sentinel is an uncontrolled difference from any future
  gate-level campaign** (section 5.3), and unlike `docs/32` section 6,
  the experiment that would settle it — this campaign with the fill
  disabled — has not been run.
- **The die is in the campaign and is not covered by it.** `die_ser` is
  87 of `pilot_top`'s 1,294 flip-flops, 6.7 %, and it is the serial front
  end and nothing else. `docs/16` is the die's campaign.
- **The interrupt is never armed.** `IRQ_MASK` resets to zero and this
  workload never writes it, so the cause register is measured as a
  **report** and not as a branch. An upset that raises a spurious
  interrupt on a system whose handler acts on it is outside this
  campaign, and section 11.2's sixteen false fault reports are exactly
  the population that would.
- **The watchdog catch rate is conditional on this workload's kick
  pattern**, and the pattern is unusual: `fi_npu.c` kicks inside the
  register accessor, so a machine that stops making register accesses
  stops kicking within 176 cycles. A program that kicked from a timer
  interrupt would keep kicking while the main thread was stalled on the
  NPU, and none of section 7.1's seven catches would happen. **The 100 %
  is a property of the pair.**
- **The counterfactual on the fetch bound is three records.** Section 7.2.
- **Two upsets are not covered**, and nothing about a voted pointer
  claims they are.
- **Nothing here is a whole-SoC campaign.** The core is `docs/42`'s, the
  watchdog is `docs/41`'s, and the fabric, the memories, the CLINT, the
  timers and the UART are still unmeasured — `soc_top.v`'s own header
  says so.
- **The campaign cannot fail because a flip-flop vanished in synthesis.**
  Every site exists in the RTL whatever the netlist holds; section 5.2
  names the eight bits that do not survive `opt_clean`.

---

## 14. Files, and reproducing this

### 14.1 Files added

```
hw/soc/fi/npu_targets.py            the site list, and the Verilog it generates
hw/soc/fi/npu_campaign.py           controls, draw, run, classify, report
hw/soc/fi/npu_coverage.py           flip-flop census attribution
hw/soc/fi/npu_counterfactual.py     the build with the fetch bound removed
hw/soc/tb/tb_soc_npu_fi.v           the instrument
hw/soc/tb/sw/fi_npu.c               the workload
hw/soc/flow/fi_npu.sh               build and elaborate once
hw/soc/flow/build_sw_npu_fi.sh      the workload's build, with the golden model
hw/soc/flow/fi_npu_coverage.sh      the Yosys flip-flop census
docs/52-npu-connection-fault-injection.md   this document
```

Modified: `docs/00-index.md`, one row, which `sw/tests/test_doc_links.py`
requires. **Nothing else.** No file that `docs/34` section 2 or section 5
pins is added, removed or altered, and `hw/soc/out/` is already
gitignored by the rule `docs/38` section 11 applies: fetched or
generated, never vendored.

**Seven files in `hw/rtl/` are read and instantiated** — `pilot_top.v`,
`lif_core.v`, `aer_fifo.v`, `scrub.v`, `secded_enc.v`, `secded_dec.v`,
`tmr_voter.v` — which is `docs/51` section 16's list unchanged.
`hw/soc/flow/fi_npu.sh` runs `git diff --quiet -- hw/rtl` after
elaboration and **refuses to continue if it is dirty**, because a
campaign is a different consumer from a test suite and
`sw/tests/test_soc_npu_guards.py` is not in this flow's path.

### 14.2 Reproducing

```
hw/soc/flow/fi_npu.sh          hw/soc/out/fi-npu   # build, elaborate once
hw/soc/flow/fi_npu_coverage.sh hw/soc/out/fi-npu   # the coverage census
hw/soc/fi/npu_campaign.py --build hw/soc/out/fi-npu --draws 100 --jobs 18
```

`--replay records.csv` re-prints the whole report from a saved run
without re-simulating anything, which is what every number in sections 6
to 10 was regenerated from — **and it is checked against the run's own
log rather than trusted**, section 5.4 item 3:

```
diff <(sed -n '/^1. CLASSIFICATION/,$p' hw/soc/out/fi-npu/campaign.log) \
     <(sed -n '/^1. CLASSIFICATION/,$p' <replay dir>/campaign.log)
```

The counterfactual of section 7.2:

```
python3 hw/soc/fi/npu_counterfactual.py /tmp/soc_npu_nofetchbound.v
SOC_NPU_SRC=/tmp/soc_npu_nofetchbound.v \
    hw/soc/flow/fi_npu.sh hw/soc/out/fi-npu-cf
hw/soc/fi/npu_campaign.py --build hw/soc/out/fi-npu-cf \
    --directed hw/soc/out/fi-npu/records.csv
```

### 14.3 Cost, measured

**1,407 `vvp` invocations — 1,400 for the campaign and 7 for the controls
— in 31 minutes 34 seconds of wall time at 18 concurrent processes on a
20-thread host** **[fact, 06:09:53 to 06:41:27, the campaign's start and
the `records.csv` timestamp]**. That is **44.6 simulations a minute and
2.48 per process per minute** **[estimate, arithmetic on two measured
times]**.

The clean run is 14,057 cycles and about **7.3 seconds** of Icarus; a run
that reaches the 52,690-cycle budget costs about **27** **[fact for the
first, `[estimate]` for the second]**. Elaboration is once, and the
census is a separate two-minute Yosys run.

**For comparison, and quoted the same way `docs/44` section 9.5 insists
on**: `docs/42` measured 2,600 simulations in 53 minutes at 18 processes
(49.1 a minute, 2.73 per process); `docs/43` measured 5,600 in 1 h 17 m
at sixteen (72.7 a minute, 4.5 per process). **This design under test is
larger than either — it contains the whole SoC and the whole frozen die —
and it is about 10 % slower per process than `docs/42`'s** **[estimate,
arithmetic on three measured intervals]**.

---

## 15. What the next block should be

**Not another campaign.** This one and `docs/42` between them now cover
the core and the connection, and the three items in section 12 that are
worth building are cheap, small and each rests on a number.

**The order the measurements argue for**, and it is not the order of
increasing difficulty:

1. **Section 12 item 4, the configuration read-back**, because it is
   software, it costs 1,408 cycles once, and it closes the half of
   `docs/51` section 18's reversal condition that can be closed from
   this side of the pin boundary. The other half — a weight word stored
   as a valid codeword of the wrong value — needs a register the die
   does not have, and section 12 item 4 says so rather than implying the
   read-back covers it.
2. **Section 12 item 1, the transport and window bounds**, because they
   are the only lethal failure this block has and because a system reset
   is a coarse answer to a stuck frame.
3. **Section 12 items 2 and 3 together**, because they are both about the
   cause register and re-hardening one bank twice would be wasteful.

**And it is worth recording that `docs/53` ranks the same block first for
an unrelated reason.** That document sizes the mission workload and
concludes that the transport, not the clock, is where the throughput
headroom is — *"the transport, where `docs/10` section 8 item 2's mesh
link is a factor of 182 against the clock's 1.16"*. **The two documents
arrive at the serial transport from opposite directions and neither
argument is the other's.** `docs/53`'s is about how fast the part can go;
this one's is about the block being exposed for five sixths of the run
and being the only thing that can stall the CPU. A change that replaced
this transport with the mesh link would move both, and neither document
is entitled to claim the other's benefit.

**And one thing that should be said plainly about what this campaign
licenses.** It licenses *"the connection's silent-corruption rate under
single-bit upsets in this workload's injection window is 4.2 % ± 1.6, it
is carried by the transport and the event engine, the queues carry none
of it, and the block's only lethal failure is caught by the watchdog
seven times in seven."* It does **not** license "the NPU connection is
adequately protected". That is a smaller claim than the numbers look, and
it is the one this document makes.

**The whole-SoC invariant is unchanged at 213,971 cycles** — nothing in
this work touches the bring-up program or any RTL — and every document
after this one should still quote `docs/51`'s number.
