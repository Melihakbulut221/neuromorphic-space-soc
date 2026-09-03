# 53 — The workload, sized: the clock is not the constraint and the transport is

`docs/48-floorplan-and-capacitance.md` section 7a,
`docs/49-synpre-and-the-binding-path.md` section 11.2 and
`docs/50-memory-read-register.md` section 7.4 each end with the same
obligation, stated most sharply in the second:

> **A 13.8 % clock shortfall is a 13.8 % throughput shortfall on a
> workload nobody has sized, against mission profiles whose stated
> requirement is that the part be idle most of the time.** … **it is a
> reason to size the workload**, and the obligation belongs where
> `docs/48` put it: … has to say what 43.10 MHz costs the workload
> before either number is published.

**This document sizes it.** It turns `docs/05-market-positioning.md`
section 3.4's four prose mission profiles into cycles per second, it
measures what the connection built in `docs/51-npu-integration.md`
actually delivers per cycle, and it puts the two next to each other.

**The answer is that the mission does not need 50 MHz and is not
rescued by it either.** The heaviest of the four profiles — an
event-camera payload at the rate a flown space instrument measured —
costs **5.9 % of the cycle budget at 43.10 MHz and 5.1 % at 50 MHz**.
The lightest costs **0.004 %**. The one with a latency requirement is
met by **five orders of magnitude**. And the one requirement any of the
four profiles states as a NUMBER is a power requirement, on which
**43.10 MHz is 13.8 % better than 50 MHz and the energy per inference is
identical to 0.05 %**.

**This is not a recommendation to write 43 MHz down.** Section 9 refuses
that explicitly and says why: the derived requirement is not a
frequency, the layout that reached 43.10 MHz fails three sign-off
criteria and is not a physical sign-off, and `docs/05` section 4 rule 5
forbids publishing either number. What changes is not the target but its
**rank**: four documents have optimised a clock that no mission profile
binds, while the two things the profiles do bind — **energy under a duty
cycle** and **the serial transport** — have never been measured and
never been ranked.

Convention, as elsewhere: **[fact]** = measured in this environment or
read out of a file; **[estimate]** = derived or judged; **[assumption]**
= chosen, with the effect of choosing differently stated at the point of
choosing; **[planned]** = intended, with nothing behind it yet.

**The pilot is untouched, and so is everything else.**
`docs/34-pilot-freeze.md` pins the TTIHP26b submission by blob hash and
the shuttle closes 2026-09-21. **This document modifies no RTL, no
testbench, no flow script and no test in this repository.** Its
measurements were made by a harness that lives outside the working tree
and reads the repository's RTL and the existing cocotb suite's drivers
by absolute path; section 13 lists the two files this document adds,
both of them documentation. `hw/soc/tb/` and `hw/soc/fi/` were not
entered.

---

## 1. Verdict first

| Question | Answer |
|---|---|
| **Is any mission profile in `docs/05` section 3.4 specified in cycles?** | **No, and one of the four is specified in milliwatts.** Profile 1 says "orbit-average power must stay in the tens of milliwatts". **That is the only number in the section**, and it is not a frequency. Section 3 |
| **What does the heaviest profile cost?** | An event-camera payload at Falcon Neuro's measured rate: **5.9 % of the cycle budget at 43.10 MHz, 5.1 % at 50 MHz**; **10.2 % and 8.8 %** at two standard deviations above its mean **[estimate, on a measured event rate and measured per-event costs]**. Section 6.1 |
| **What does the lightest cost?** | Nine OPS-SAT-class telemetry channels: **0.004 % at 43.10 MHz**. Four to five orders of margin. Section 6.2 |
| **Latency to a classification?** | **13.06 us** for one frame and **78.38 us** for the whole six-frame inference, at 43.10 MHz **[estimate, a measured cycle count times a measured period]**, against a profile that says "faster than a ground loop". Section 6.3 |
| **What does the design deliver per cycle?** | Measured on `soc_npu` with the frozen pilot inside it: **182.57 cycles per serial frame and 6.86 cycles per inbound pin event** **[estimate, solved from two measured workloads; the model predicts four other measured workloads to within 0.8 %]**. Section 4 |
| **What dominates?** | **The serial transport, by 27x per event and by 93 to 98 % of every workload's cycles** **[fact]**. Section 5 |
| **Does the clock barely matter, then?** | **No, and this is the distinction the question turns on.** The transport is synchronous, so the clock scales it exactly: 50/43.10 is **+16.0 %** of throughput and nothing more. **The transport is a 27x architectural factor and the clock is a 1.16x one**, and no mission number is close enough to the boundary for the second to decide it. Section 6.4 |
| **Is there a case where 50 MHz decides it?** | **Measured, and no.** The frame-rate ceiling is **19,505 Hz at 43.10 MHz against 22,655 Hz at 50** — a parameter that would have to move **20x** from the assumed 1 kHz to bind, at which point 16 % does not save it. And **the pilot's eight neurons cannot emit more than 8 spikes per frame against a transport that supports 232** **[estimate]**. Section 6.5 |
| **Power?** | **34.835 mW typ, 27.774 slow, 46.095 fast**, at 20 ns and extracted parasitics, **on `docs/47`'s own sign-off run** — **[fact, `full3/19-openroad-stapostpnr/*/power.rpt`], and no document in this repository has ever quoted it**, five of them saying "no power number" while the file was in the run directory they report from. Section 7 |
| **Energy per inference?** | **2.353 uJ at 50 MHz and 2.354 uJ at 43.10 MHz, typ corner, +0.045 %** **[estimate]**. **Energy per inference is invariant under the clock**, because it is cycles times energy per cycle and neither term moved. Section 7.2 |
| **Does the target stand?** | **Not as a mission requirement — nothing in `docs/05` needs it.** Section 9 |
| **Does it move to 43?** | **No, and this document refuses it.** Section 9.2 gives three reasons and the first is that 43.10 MHz is the number the layout reached. |
| **So what is the constraint?** | **Energy under a duty cycle, and the transport.** Both are unmeasured and unranked; one of them is the only quantified requirement in `docs/05` section 3.4. Section 9.3 |
| **What must not be published?** | **Neither number.** `docs/05` section 4 rule 5, and a layout that fails setup, max slew and max cap at the slow corner and has never seen Magic DRC or LVS. Section 9.4 |

---

## 2. Reproducing the instrument before moving it

`docs/44` section 5.2 set the rule and every document since has followed
it. Two instruments are used here and both were reproduced first.

| What | Published | Measured here |
|---|---|---|
| `docs/47` section 8.2 sign-off, slow corner | **−3.2029 ns on 2,003 endpoints** | **−3.2029 / 2,003** **[fact, `hw/openlane/signoff_report.py hw/soc/pnr/runs/full3`, exit 0]** |
| the same run's other three criteria | hold **−0.2015 on 3** at fast; max slew **1 / 14 / 0**; max cap **12 / 10 / 10** | **every figure** **[fact, the same report]** |
| `docs/51` section 8.1, one node-window register access | **176 clock cycles** | **176**, measured again from a cold reset through the frozen pilot **[fact, section 4.1 row W6]** |
| `docs/51` section 7.2's inference, as event counts | **22 events in, 12 out**, no drops, no ECC event, no fault cause | **22 / 12 / 0 / 0 / 0**, read out of the hardware's own `CNT` and `CNT_DROP` registers **[fact, section 4.1 row W1]** |
| `docs/15` section 4.6, the pilot's own power | **4.88 mW** at typical, 50 MHz | not re-measured; quoted from that document and used only for the comparison in section 7.1 |

**The derived-Fmax convention is `docs/31` section 4.2's**, `T − WNS`,
so 43.10 MHz means a period of **23.2029 ns** and 50 MHz means
**20.0000 ns**. Every "per second" figure below is a measured cycle
count divided by one of those two periods, and the document states which.

---

## 3. The requirement, derived from `docs/05` section 3.4

The four profiles, quoted in full because the derivation has to be
attackable at the text and not only at the arithmetic:

> - Always-on health monitoring of bus telemetry with wake-on-anomaly,
>   where orbit-average power must stay in the tens of milliwatts.
> - Event-camera payloads (lightning mapping, sprite detection, debris
>   streak detection) producing inherently sparse address-event streams.
> - Attitude/collision-relevant event detection requiring on-board
>   reaction faster than a ground loop.
> - Long-idle mission phases (transfer, storage orbits) where a
>   frame-based accelerator would burn its budget doing nothing.

**Read as requirements rather than as marketing, these are three
different kinds of thing and only one of them is a throughput
requirement.**

| Profile | Kind of requirement | Stated quantity |
|---|---|---|
| 1, telemetry health monitoring | **power** | **"tens of milliwatts", orbit-average** |
| 2, event-camera payload | **throughput** | none — "inherently sparse" |
| 3, attitude/collision reaction | **latency** | "faster than a ground loop" |
| 4, long-idle phases | **power**, under a duty cycle | none |

> **THE ONLY NUMBER IN `docs/05` SECTION 3.4 IS A POWER NUMBER**
> **[fact, it is the only numeral in the four bullets]**. Three
> documents have now treated the section as a throughput specification
> that failed to state its throughput. It is not: it is a power
> specification that states its power, plus two profiles that give the
> shape of a workload without its rate, plus one latency requirement
> stated in the units of a ground station. **The parameter it binds is
> not the clock, and section 7 is what happens when the stated
> requirement is taken at face value.**

The rest of this section supplies the rates the profiles do not.

### 3.1 Profile 2, the event-camera payload — the one with a flown instrument behind it

`docs/02-npu-architecture.md` section 1.5 names the reference instance
and it is the right one: **Falcon Neuro**, two DAVIS240C event sensors
on the International Space Station, flown for exactly the lightning and
sprite detection this profile lists
(https://www.frontiersin.org/journals/remote-sensing/articles/10.3389/frsen.2024.1436898/full).
That paper reports its own event rates, which is what makes this profile
sizeable at all:

| Quantity | Value |
|---|---|
| average event rate, 100 ms bins, over all recordings | **16,700 events/s** **[fact, cited paper]** |
| mean with each recording weighted equally | **53,444 events/s** **[fact]** |
| standard deviation of that mean | **134,982 events/s** **[fact]** |
| sensor | 240 x 180 pixels **[fact]** |
| burst behaviour | "lightning causes an order of magnitude more events in a small time segment" **[fact, the paper's own words]** |

The two means differ by 3.2x and the paper says why: three long
night-time recordings over uninhabited areas dominate the time-weighted
figure. **Both are carried below**, because which one is the
"requirement" is a mission-design question this document is not
entitled to settle, and the conclusion does not depend on it.

**The standard deviation is four times the size of the mean**, which is
what "sparse and bursty" means when it is measured instead of asserted.
The burst case used below is **mean + 2 sd = 323,408 events/s**
**[estimate, arithmetic on two measured quantities]**.

Three things have to be assumed to get from an event rate to a cycle
cost, and each is stated with what a different choice would do.

**[assumption 1] One camera event is one synaptic event — one axon
spike into the fabric.** This is the model `docs/10-npu-mvp-spec.md`
section 7.1's event word is built for and the one `docs/02` section 1.5
describes. *If a front end down-samples or accumulates events before the
fabric sees them, the inbound rate falls and every margin below
improves.* The assumption is therefore the pessimistic one.

**[assumption 2] The network is evaluated on a 1 kHz time base — one
TICK and one SYNC barrier per millisecond.** Nothing in `docs/05` or
`docs/10` fixes a frame rate. 1 kHz is chosen because it is fast enough
that the 100 ms binning of the measured event rate is not violated and
slow enough to be a plausible integration window for an event-driven
classifier. *This is the assumption the conclusion is most sensitive to,
and section 6.5 sweeps it over three decades rather than defending it:
the answer is unchanged at 100 Hz and at 10 kHz, and fails at 100 kHz at
both clocks.*

**[assumption 3] The classifier emits ten output spikes per frame.**
Nothing measures this; a classifier is many-to-few by construction, and
ten is chosen as an order of magnitude above the pilot's whole spike
budget for a frame. *Section 6.5 gives the value at which this
assumption binds — 232 spikes per frame at 43.10 MHz — and notes that
the pilot's eight neurons cannot reach 9.*

### 3.2 Profile 1, telemetry health monitoring

`docs/02` section 1.5 names **OPS-SAT-AD** as the benchmark, and the
published dataset is **9 telemetry channels** — three magnetometer and
six photodiode — over 2,123 annotated fragments **[fact,
https://www.nature.com/articles/s41597-025-05035-3 and
https://pmc.ncbi.nlm.nih.gov/articles/PMC12041257/]**.

**[assumption 4] The sampling rate.** The benchmark paper states that
segments "have varying lengths and sampling frequency" and fixes no
rate **[fact, the same paper]**, so there is no number to read. Three
values are carried below — **1 Hz, 10 Hz and 1 kHz per channel** — of
which the first two bracket ordinary CubeSat housekeeping cadence and
the third is four orders above it. *The conclusion is the same at all
three, which is why no single value is chosen.*

### 3.3 Profile 3, reaction faster than a ground loop

`docs/49` section 11.2 already read this correctly and this document
adopts its reading without adding to it: **"faster than a ground loop"
is seconds to minutes, not nanoseconds** **[estimate, from the text]**.
A ground loop for a LEO CubeSat is bounded below by pass scheduling and
is at best minutes; even a continuous relay is hundreds of milliseconds
of round trip. **One second is used below as the most demanding reading
of it.**

### 3.4 Profile 4, long-idle phases

This is not a rate at all. It is the requirement that the part cost
nearly nothing when nothing is happening — the whole architectural
argument of `docs/05` section 3.3's "activity-proportional compute". It
is a power requirement under a duty cycle, and section 7.3 is what this
design does about it, which is nothing.

---

## 4. What the design delivers, measured

### 4.1 The measurements

`soc_npu` with `hw/rtl/pilot_top.v` instantiated inside it, at
`N_NODES = 1`, 8 x 8, `SER_HALF = 2`, both queues 8 deep — the
elaboration `soc_top.v` uses. Each workload is a **fresh reset, a fresh
`docs/10` section 11.1 bring-up, and then the stream**; the clock starts
at the first `EVQ_IN` write and stops when the last barrier has been
collected, **so configuration and weight loading are not in the number**
— they are a per-mission cost and not a per-event one.

`n_in` and `n_out` are read out of the block's own `CNT` register and
`CNT_DROP` is checked to be zero in every row, so the event counts are
the hardware's and not the harness's.

| Workload | frames | **cycles** | n_in | n_out | pin events | serial frames |
|---|---:|---:|---:|---:|---:|---:|
| **W1**, `docs/51` section 7's six-frame inference | 6 | **3,378** | 22 | 12 | 16 | 18 |
| **W2**, the same shape four times | 24 | **12,477** | 88 | 42 | 64 | 66 |
| **W3**, 24 frames with no synaptic event | 24 | **9,000** | 48 | 24 | 24 | 48 |
| **W4**, 24 frames of six spikes each | 24 | **16,560** | 192 | 60 | 168 | 84 |
| **W3b**, W3 with one APB write per event instead of two | 24 | **8,928** | 48 | 24 | 24 | 48 |
| **W4b**, W4 the same way | 24 | **16,488** | 192 | 60 | 168 | 84 |
| **W5**, the inbound pin path with no APB transfer in the loop | — | **63** for 7 intervals | 8 | 0 | 8 | 0 |
| **W6**, one node-window register access from cold reset | — | **176** | 0 | 0 | 0 | 1 |

**[fact for every cycle count and every event count]**

"Pin events" is `n_in` minus the frame count — every SPIKE and TICK,
which `docs/51` section 4 establishes take the parallel AER pins.
"Serial frames" is the frame count plus `n_out` — one `EVQ_IN` write per
SYNC, which has no pin, plus one `EVQ_OUT` read per drained word, which
has no TYPE on the pins. Both are structural consequences of
`pilot_top.v`'s pin contract and neither is a choice made here.

**W1 is `docs/51`'s inference and the counts agree with it**: 22 in, 12
out, 16 over the pins and 18 over the serial port, which is that
document's "18 engine frames" and "16 pin events" arriving as a
measurement rather than as the estimate section 8.3 states them as.

### 4.2 The two constants, solved rather than assumed

Fitting `cycles = a x pin_events + b x serial_frames` to **W3b and W4b**
— the two rows whose writer performs one APB transfer per event, so
that the harness's own `ST_INJ_FULL` poll is not charged to the design:

| | |
|---|---:|
| **a, cycles per inbound pin event** | **6.8571** |
| **b, cycles per serial frame** | **182.5714** |

**[estimate, solved from two measured workloads]**

**And the model was not fitted to the rows it is checked against.**
Predicting the other four:

| Workload | measured | predicted | error | **serial share** |
|---|---:|---:|---:|---:|
| W1 | 3,378 | 3,396.0 | **+0.53 %** | **97.3 %** |
| W2 | 12,477 | 12,488.6 | **+0.09 %** | **96.6 %** |
| W3 | 9,000 | 8,928.0 | −0.80 % | 97.4 % |
| W4 | 16,560 | 16,488.0 | −0.43 % | 92.6 % |

**[estimate, arithmetic on measured rows]**

Two independent checks on the constants, neither of which is the
regression:

- **b against W6.** One register access measured **176 cycles** from
  cold reset. The marginal serial frame is **182.57**, which is 176 plus
  about six cycles of engine sequencing and CPU handshaking around it.
  The two numbers were produced by different mechanisms — one is a bus
  latency, the other the slope of a line fitted to two workloads and
  checked against four more — and they agree to **3.7 %**.
- **a against W5.** With both engines disabled the injection queue was
  filled, then `IN_EN` was raised and the strobes on the die's own
  `AER_IN_STB` pin counted with no APB transfer inside the measurement:
  **7 intervals in 63 cycles, exactly 9.00 cycles per event** **[fact]**.
  The marginal figure is **6.86**, which is *lower*, and the reason is
  visible in the block: the drain engine and the injection engine are
  separate and share only the transport, **so inbound pin work partly
  hides behind an outbound serial frame that is already in flight.**
  6.86 is what a mixed stream costs; 9.00 is what the engine costs when
  there is nothing to hide behind.

> **AND `docs/51`'S "4 CYCLES" IS THE PIN CONTRACT, NOT THE DELIVERED
> COST.** That document and `soc_npu.v`'s own header both quote four
> clock cycles for an inbound SPIKE or TICK, which is the strobe on the
> pins. **The engine that drives that strobe costs 9.00 cycles per event
> and a mixed stream costs 6.86** **[fact and estimate respectively]**.
> The asymmetry `docs/51` states as **44x** is therefore **27x** when
> both sides are measured the same way — 182.57 against 6.86 — and it is
> a correction in the direction that makes the pins look *worse*, not
> better. Section 11 records it.

### 4.3 Delivered rates

Every row is a measured or derived cycle count divided by one of the two
periods of section 2.

| | cycles | **at 43.10 MHz** | **at 50 MHz** | ratio |
|---|---:|---:|---:|---:|
| one serial frame | 182.57 | 4.236 us — **236,061/s** | 3.651 us — **273,865/s** | 1.160 |
| one node-window register access | 176 | 4.084 us — 244,875/s | 3.520 us — 284,091/s | 1.160 |
| one inbound pin event, mixed stream | 6.86 | **6,285,134/s** | **7,291,667/s** | 1.160 |
| one inbound pin event, engine alone | 9.00 | 4,788,673/s | 5,555,556/s | 1.160 |
| **one inference frame** (W1's average) | 563.0 | **13.06 us — 76,551/s** | **11.26 us — 88,810/s** | 1.160 |
| **the whole six-frame inference** (W1) | 3,378 | **78.38 us — 12,759/s** | **67.56 us — 14,802/s** | 1.160 |

**[estimate for every rate; the cycle counts are section 4.1's and the
periods are section 2's]**

**The ratio column is 1.160 in every row and that is the point of
printing it.** Everything in this block is synchronous and nothing has a
fixed time constant, so the clock scales the whole table and nothing
else. **A 13.8 % clock shortfall is exactly a 13.8 % throughput
shortfall, as `docs/49` section 11.2 said it was** — the question this
document answers is not whether that is true but whether 13.8 % of
anything here is close to a requirement.

---

## 5. Where the cycles go

| Workload | serial | pins | serial share |
|---|---:|---:|---:|
| W1, the `docs/51` inference | 3,286 | 110 | **97.3 %** |
| W3b, empty frames | 8,763 | 165 | **98.2 %** |
| W4b, six spikes per frame | 15,336 | 1,152 | **93.0 %** |

**[estimate, `b x serial_frames` and `a x pin_events` against the
measured totals of section 4.1]**

> **THE SERIAL TRANSPORT IS 93 TO 98 % OF THE EVENT PATH IN EVERY
> WORKLOAD MEASURED, AND THE DENSEST ONE IS THE LOW END.** W4b carries
> seven times as many spikes per frame as W1 and the serial share falls
> only from 97.3 % to 93.0 %, because every one of those extra spikes
> costs 6.86 cycles against a barrier's 182.57. **Making the workload
> seven times denser moves the split by four percentage points.**
>
> **AND THAT IS WHAT THE FIRST QUESTION IN THE BRIEF WAS ASKING, SO IT
> IS WORTH BEING PRECISE ABOUT WHAT IT DOES AND DOES NOT MEAN.** It does
> **not** mean the clock is irrelevant: the transport is synchronous and
> the clock scales it exactly, so 50 MHz is 16.0 % more serial frames
> per second than 43.10 MHz, in every row of section 4.3. What it means
> is that **the connection's cost is set by an architectural decision
> with a factor of 27 in it, and the clock is a factor of 1.16 on top**.
> `docs/51` section 3.4 already priced the serial transport and
> `docs/10` section 8 item 2 already specifies the thing that removes it
> — a symmetric mesh link with valid/ready, one event per cycle. **That
> is a factor of 182 against the clock's 1.16**, and section 9.3 is why
> it should be ranked accordingly.

---

## 6. The requirement against the delivery

### 6.1 Profile 2: the event-camera payload

Assumptions 1 to 3 of section 3.1, at 1 kHz frames and ten output spikes
per frame. Each row is `events/s x 6.8571` for the inbound pins, plus
`2,000 x 182.5714` for the SYNC in and the barrier out, plus
`10,000 x 182.5714` for the output spikes.

| Event rate | inbound | barriers | outputs | **total, cycles/s** | **% at 43.10 MHz** | **% at 50 MHz** |
|---|---:|---:|---:|---:|---:|---:|
| **16,700/s**, time-weighted mean | 114,514 | 365,143 | 1,825,714 | **2,305,370** | **5.35 %** | **4.61 %** |
| **53,444/s**, recording-weighted mean | 366,471 | 365,143 | 1,825,714 | **2,557,328** | **5.93 %** | **5.11 %** |
| 188,426/s, mean + 1 sd | 1,292,056 | 365,143 | 1,825,714 | 3,482,913 | 8.08 % | 6.97 % |
| **323,408/s**, mean + 2 sd | 2,217,641 | 365,143 | 1,825,714 | **4,408,498** | **10.23 %** | **8.82 %** |

**[estimate for every cell; the event rates are section 3.1's measured
facts, the per-event costs are section 4.2's, and the percentages are
those two divided by the two periods of section 2]**

**The profile is met at 43.10 MHz with a factor of ten of margin at the
burst rate, and 50 MHz changes the margin from 9.8x to 11.3x.**

**What is binding inside that number is worth naming: it is the output
spikes, not the camera.** At the recording-weighted mean the inbound
stream is 366,471 cycles/s and the ten output spikes per frame are
1,825,714 — **five times as much, for a stream 5.3 times smaller**. The
camera's events go over the pins at 6.86 cycles; the classifier's answers
go over the serial port at 182.57.

### 6.2 Profile 1: telemetry health monitoring

Nine OPS-SAT-AD channels, one frame per sample, and eight output spikes
per frame — the pilot's entire neuron count, which is the most it can
possibly emit.

| Sampling rate per channel | **total, cycles/s** | **% at 43.10 MHz** | **% at 50 MHz** |
|---|---:|---:|---:|
| **1 Hz** | **1,887** | **0.0044 %** | 0.0038 % |
| 10 Hz | 18,874 | 0.0438 % | 0.0377 % |
| 1 kHz — four orders above housekeeping cadence | 1,887,428 | **4.38 %** | 3.77 % |

**[estimate; the channel count is section 3.2's fact and the rate is
assumption 4]**

**Assumption 4 does not matter.** The profile is met by four to five
orders of magnitude at any plausible reading of it, and by a factor of
23 even at a rate nobody would ask for.

### 6.3 Profile 3: reaction faster than a ground loop

| | cycles | at 43.10 MHz | at 50 MHz |
|---|---:|---:|---:|
| one frame, injection to barrier | 563 | **13.06 us** | 11.26 us |
| the whole six-frame inference | 3,378 | **78.38 us** | 67.56 us |
| one node-window register access | 176 | 4.08 us | 3.52 us |

**[estimate, section 4.1's measured cycle counts over section 2's
periods]**

**Against one second — the most demanding reading of "faster than a
ground loop" — one classification takes 13.06 us, which is 1.3 x 10^-3
percent of the budget.** The margin is **76,551x** at 43.10 MHz and
**88,810x** at 50. **This profile cannot distinguish the two clocks and
could not distinguish either of them from 1 MHz.**

### 6.4 The summary of the three sizeable profiles

| Profile | requirement | **cost at 43.10 MHz** | **cost at 50 MHz** | **margin at 43.10** |
|---|---|---:|---:|---:|
| 1, telemetry | 9 channels at 1 Hz | 0.0044 % | 0.0038 % | **23,000x** |
| 2, event camera | Falcon Neuro, mean + 2 sd | 10.23 % | 8.82 % | **9.8x** |
| 3, reaction latency | one second | 0.0013 % | 0.0011 % | **76,551x** |

**[estimate, sections 6.1 to 6.3]**

> **NO PROFILE IN `docs/05` SECTION 3.4 REQUIRES 50 MHz, AND THE
> NEAREST ONE HAS AN ORDER OF MAGNITUDE OF MARGIN AT 43.10.** The clock
> would have to be **4.4 MHz** for the event-camera profile at its burst
> rate to consume the whole budget **[estimate, 43.0981 x 0.1023]**.
> That is a factor of ten below the number four documents have been
> trying to reach and a factor of six below the bottom of `docs/02`'s
> stated range.

### 6.5 Where the assumptions bind, since that is what a derivation is for

**Assumption 2, the frame rate**, swept over three decades at the
recording-weighted event rate:

| Frame rate | **% at 43.10 MHz** | **% at 50 MHz** |
|---|---:|---:|
| 100 Hz | 1.36 % | 1.17 % |
| **1 kHz** (assumed) | **5.93 %** | **5.11 %** |
| 10 kHz | 51.68 % | 44.55 % |
| 100 kHz | **509 %** | **439 %** |

**[estimate]**

**The ceiling is 19,505 Hz at 43.10 MHz and 22,655 Hz at 50** **[estimate,
solving the budget for the frame rate]**. So the assumption would have to
be wrong by a factor of **20** before the clock is in the argument at
all, and at 100 kHz — a factor of 100 — **neither clock closes and the
16 % is irrelevant to which.**

**Assumption 3, the output spike rate.** Solving the budget for the
number of output spikes per frame at 1 kHz:

| | **spikes per frame at saturation** |
|---|---:|
| at 43.10 MHz | **232** |
| at 50 MHz | **270** |

**[estimate]**

> **AND THE PILOT HAS EIGHT NEURONS.** The most `pilot_top` at 8 x 8 can
> emit in one frame is **eight spikes and one barrier echo**, so the
> geometry caps the outbound stream at **nine serial frames per frame**
> against a transport that supports **234**. **At the shipped geometry
> the transport has 26x of headroom over what the fabric can physically
> produce, and the clock decides none of it** **[estimate, arithmetic on
> the measured constants and the elaborated geometry]**. Even at the
> pilot's maximum output the frame-rate ceiling is **23,405 Hz at
> 43.10 MHz and 27,186 Hz at 50**.
>
> **This is the sharpest form of the answer.** The parameter that
> decides whether this workload fits is **how many events cross the
> serial transport per frame**, and at the geometry that exists it
> cannot reach a twenty-sixth of the ceiling. The clock moves that
> ceiling by 16 %.

---

## 7. Power, which is the requirement `docs/05` section 3.4 actually states

### 7.1 The number, which was in the run directory the whole time

`docs/45` section 8, `docs/47` section 9, `docs/48` section 8,
`docs/49` section 12 and `docs/50` section 10 all end with the same
line: **"one clock, one mode, no scan, no test, no power number."**

**There is a power number, and it is in `docs/47`'s own sign-off run.**
`OpenROAD.STAPostPNR` writes a `power.rpt` per corner and
`power__*__total` into `final/metrics.json`, on extracted parasitics, at
the same three corners that produce the timing numbers those five
documents quote.

| Corner | internal | switching | leakage | **total** |
|---|---:|---:|---:|---:|
| `nom_slow_1p08V_125C` | 16.922 mW | 10.751 mW | 0.102 mW | **27.774 mW** |
| `nom_typ_1p20V_25C` | 20.950 mW | 13.787 mW | 0.098 mW | **34.835 mW** |
| `nom_fast_1p32V_m40C` | 28.422 mW | 17.331 mW | 0.342 mW | **46.095 mW** |

**[fact, `hw/soc/pnr/runs/full3/19-openroad-stapostpnr/<corner>/power.rpt`,
the run whose timing is `docs/47` section 8.2's]**

**Four things must be said about it before it is used, and the fourth is
the one that decides how much weight it can carry.**

1. **It is at 20 ns, not at 23.2029 ns.** The SDC period is the target,
   not the closing period, so this is the power of a design running at
   50 MHz — a frequency it does not reach. Section 7.2 scales it.
2. **The split is 60 % internal, 40 % switching, 0.3 % leakage** at typ.
   By group at typ: combinational 46.0 %, sequential 31.4 %,
   macro 11.7 %, clock 11.0 % **[fact, the same report]**. **The six
   SRAM macros are 4.068 mW of it**, which is the one term a duty cycle
   would not remove by clock gating alone.
3. **`report_power` was run with no activity annotation.** The flow's
   `corner.tcl` calls `report_power -corner $corner_name` and nothing
   before it reads a VCD or a SAIF **[fact,
   `librelane/scripts/openroad/sta/corner.tcl`]**, so the switching
   figures rest on OpenSTA's default propagated activity and not on the
   toggle rates of any program this repository has run. **This is an
   estimate wearing a measurement's clothes and it is labelled here as
   what it is.**
4. **It is nonetheless the only power figure this SoC has ever had**,
   and the reason it is worth quoting is not its precision but its order
   of magnitude: **tens of milliwatts**, which is the unit `docs/05`
   section 3.4 profile 1 states its requirement in. **A figure whose
   ORDER OF MAGNITUDE can be trusted is enough to answer a requirement
   stated to an order of magnitude, and it is not enough for anything
   else** — section 15 item 1 is what would make it enough.

**For comparison, the pilot alone is 4.88 mW at typical and 50 MHz**
**[fact, `docs/15` section 4.6, quoted not re-measured]**, so `soc_top`
is **7.1x** the tile — which is the right order for a design that is
`docs/47` section 6.3's 27,565 cells against the tile's 9,487, plus six
SRAM macros.

### 7.2 Energy per inference, which is where the clock stops mattering entirely

Dynamic power scales with frequency and leakage does not, so at
43.0981 MHz:

| Corner | at 50 MHz | **scaled to 43.10 MHz** |
|---|---:|---:|
| slow | 27.774 mW | **23.954 mW** |
| typ | 34.835 mW | **30.040 mW** |
| fast | 46.095 mW | **39.779 mW** |

**[estimate, dynamic scaled by 43.0981/50 and leakage carried
unchanged]**

**43.10 MHz is 13.8 % less power than 50 MHz on the one requirement
`docs/05` section 3.4 quantifies.** The clock shortfall is on the right
side of that requirement.

And then the number that ends the argument:

| Corner | **energy per cycle at 50 MHz** | **at 43.10 MHz** | change |
|---|---:|---:|---:|
| slow | 555.486 pJ | 555.812 pJ | **+0.059 %** |
| typ | 696.693 pJ | 697.006 pJ | **+0.045 %** |
| fast | 921.903 pJ | 922.999 pJ | **+0.119 %** |

| | at 50 MHz | at 43.10 MHz |
|---|---:|---:|
| **W1's six-frame inference, 3,378 cycles, typ** | **2.353 uJ** | **2.354 uJ** |
| per event carried across the connection (34 events) | 69.2 nJ | 69.2 nJ |
| per inference frame | 392 nJ | 392 nJ |

**[estimate, section 7.1's power over the two frequencies times section
4.1's measured cycle count]**

> **ENERGY PER INFERENCE IS INVARIANT UNDER THE CLOCK TO WITHIN
> 0.045 %.** It is cycles times energy per cycle; the cycle count is a
> property of the design and the transport and did not move, and the
> energy per cycle is dominated by dynamic switching, which is per-cycle
> by construction. **The only term that changes is leakage, which is
> 0.3 % of the total and is paid for longer at a lower clock.**
>
> **SO IF THE MISSION'S CONSTRAINT IS ENERGY PER INFERENCE — WHICH IS
> WHAT AN "ACTIVITY-PROPORTIONAL" PART IS SOLD ON — THE CLOCK IS NOT A
> PARAMETER OF IT AT ALL.** `docs/50` section 7.2 established that
> `cycles x period` is the figure of merit for wall-clock work and used
> it to reject the memory read register. The same arithmetic applied to
> energy gives `cycles x energy-per-cycle`, in which the period does not
> appear. **Four documents have optimised the one term of the product
> that the mission's stated requirement does not contain.**

### 7.3 And profile 4 is not met, for a reason that has nothing to do with the clock

`docs/05` section 3.4 profile 4 is long-idle mission phases, and
section 3.3's whole differentiation argument against GOLDFINCH-1 is
"the chip must idle at microwatts and wake on activity".

**This design idles at 27.8 to 46.1 mW.** It has **one clock and one
mode** — `docs/47` section 9, `docs/48` section 8, `docs/49`
section 12 and `docs/50` section 10 all state it — no clock gating, no
retention, no wake-on-event path that does not run the whole SoC. At the
telemetry profile's own duty cycle the part is **0.0044 % busy and
100 % powered** **[estimate, sections 6.2 and 7.1]**.

> **THIS IS THE ONE REQUIREMENT GAP THIS ANALYSIS FINDS, AND IT IS FOUR
> ORDERS OF MAGNITUDE WIDE.** "Tens of milliwatts orbit-average" is met
> today only because the part is *small*, not because it is
> *activity-proportional*; "microwatts when idle" is not met at all and
> nothing in the design is aimed at it. **A 16 % clock improvement is
> not a step towards it and a 16 % clock shortfall is not a step away
> from it.**

---

## 8. The comparison that keeps this honest: GR801

`docs/01-reference-decomposition.md` is the scaling analysis and the
sanity check is whether a requirement met with this much margin is
plausible for a part this far below its reference.

| | GR801 / Akida 1.0 | **this SoC** | ratio |
|---|---|---|---:|
| process | 28 nm FDSOI **[fact, `docs/01` §2]** | 130 nm bulk, open PDK **[fact]** | — |
| clock | AKD1000 is **300 MHz** in TSMC 28 nm **[fact, `docs/01` §3.3]** | **43.10 MHz** at post-route sign-off **[fact, `docs/47` §8.2]** | **6.96x** |
| `docs/01`'s FO4-scaled prediction for a 130 nm retarget | **50–75 MHz** **[estimate, `docs/01` §3.3]** | 43.10 measured | **13.8 % below the low end** |
| `docs/01`'s open-flow band | "25–50 MHz" **[`docs/01` §3.3]** | 43.10 measured | **inside it** |
| on-chip SRAM | **11.2 MB** **[fact, `docs/01` §2]** | six macros; `docs/01` §3.4 predicts 100–128 KB at 25 mm2 | — |
| memory-density gap | | | **70–90x** **[estimate, `docs/01` §3.2]** |
| peak compute | 1024 MACs/clock **[fact]** | `docs/01` §3.4 estimates this class at **1–4 %** of it | **25–100x** |

**Two readings, and the second is the sanity check.**

**1. `docs/01`'s two clock bands disagree and the measurement lands in
the conservative one.** Section 3.3 of that document gives an FO4-scaled
prediction of 50–75 MHz and, in the next bullet, an empirical open-flow
band of 25–50 MHz. **43.10 MHz is 13.8 % below the first and comfortably
inside the second** **[fact for the measurement, estimate for both
bands]**. That is not a failure of `docs/01` — it is a document that
stated two bands and did not have to choose; the measurement chooses.
**And what it says about the 50 MHz target is that the target took the
optimistic band's floor as a requirement.**

**2. The gap to the reference is a gap in SIZE, not in RATE, and that is
why the derived requirement is plausible.** The clock gap to the
reference is **7x** and the memory gap is **70–90x**; the compute gap is
**25–100x**. If the binding shortfall against GR801 were throughput, a
requirement met with 9.8x of margin at the burst rate would be
suspicious. It is not: **the part is 7x slower and 70–90x smaller, and
the requirement derived in section 3 is a requirement about rate.**

**3. And the check runs against the reference's own lead application.**
`docs/05` section 1.1 lists GR801's advertised applications and
lightning detection is the first of them; Falcon Neuro is the flown,
measured instance of that application. **A part at 1–4 % of GR801's
compute absorbs that instrument's event stream at 118x its
recording-weighted mean and 376x its time-weighted mean, inbound**
**[estimate, section 4.3 over section 3.1]**. The requirement is
therefore neither absurdly large — a 130 nm open-PDK part covers it —
nor so small that it proves nothing:

> **THE ONE PLACE THE TWO NUMBERS ARE THE SAME ORDER OF MAGNITUDE IS THE
> OUTBOUND TRANSPORT.** The serial ceiling is **236,061 events/s at
> 43.10 MHz and 273,865 at 50**, and Falcon Neuro's burst input rate at
> mean + 2 sd is **323,408 events/s** **[estimate over facts]**. **A
> hypothetical one-in-one-out fabric would not carry that burst at
> either clock** — 0.73x at 43.10 and 0.85x at 50. A classifier is
> many-to-few and does not have that shape, so this is a bound and not a
> finding. **But it is the sanity check working**: the only place in
> this analysis where the mission's numbers and the part's numbers meet
> is a place the clock cannot reach either, and the thing that would
> reach it is `docs/10` section 8 item 2's mesh link.

---

## 9. The recommendation

### 9.1 The target does not stand as a mission requirement

**No profile in `docs/05` section 3.4 requires 50 MHz.** The heaviest
costs 10.23 % of the cycle budget at 43.10 MHz at two standard
deviations above a flown instrument's measured mean; the lightest costs
0.0044 %; the latency profile is met by 76,551x. **The clock would have
to fall to 4.4 MHz for any of them to bind** **[estimate, section 6.4]**.

**50 MHz's provenance is now fully accounted for and none of it is a
mission.** `docs/02`'s architecture table gives a **range**, "25–50 MHz,
easily met" **[fact]**; `docs/06` calls 50 MHz "the 50 MHz TT envelope";
`docs/15` measured the pilot against the 50 MHz `tt/info.yaml`
**declares**; `docs/49` section 11.2 established that the tile that
declared it **has no SRAM macro in it** while `soc_top` has six, one of
which contributes **9.5277 ns — 47.6 % of the period — on a single arc
no design change can shorten** **[fact, `docs/49` §11.1]**. **`docs/01`
section 3.3 is the only place the number is derived at all, and section 8
above shows it derived two bands and 43.10 MHz is inside one of them.**

### 9.2 AND 43.10 MHz MUST NOT BE WRITTEN DOWN EITHER

**This is a refusal and it is the first thing this document was asked
for.** Three reasons, in order of how much they bind.

**1. It is the number the layout reached.** Deriving a requirement that
happens to sit below a measured result is not the same as adopting the
result as the requirement, and the difference is not rhetorical: **the
derived requirement in section 6 is not a frequency at all.** It is
"the part must carry N serial frames per second", N is set by the frame
rate and the output spike count, and at the geometry that exists N is
capped at nine per frame by the fabric (section 6.5) and not by the
clock. **A requirement written as a frequency would be a requirement
written in the units of the answer**, which is what `docs/50`
section 7.3 refused when it declined to keep a register that improved
the sign-off number and made the part slower.

**2. `docs/05` section 4 rule 5 forbids it.** "Any figure published
externally must be traceable to measurement or clearly labelled as a
design target." **43.10 MHz is neither.** It is a measured
*non-closure*: the derived Fmax of a run that **fails setup on 2,003
endpoints, fails max slew at the slow corner and fails max cap at all
three** **[fact, section 2]**, on a layout that has never seen Magic
DRC, KLayout DRC or Netgen LVS because the one available SRAM macro
fails all three inside the vendor views **[fact, `docs/47` §9,
`docs/12` §§7.5 and 8]**. **Publishing 43.10 MHz would publish an Fmax
from a layout nobody has shown to be manufacturable.**

**3. Two parts in one project would carry two clocks and one of them is
being fabricated.** `tt/info.yaml` declares 50 MHz and `docs/15`
section 4.6's re-derivation closes the 6x2 submission shape at
**50.7 MHz derated** **[fact]**. A datasheet that says 50 MHz for the
tile and 43 MHz for the SoC invites the question of which one the
project's clock is, and the answer — "they are different parts on
different schedules" — is correct and is not what a reader takes away.

### 9.3 The shape of the recommendation is (c): the target was the wrong parameter

**Retire 50 MHz as a REQUIREMENT and keep it as a FLOW CONSTRAINT.**
The distinction is operational:

| | |
|---|---|
| **As a requirement** | **Withdrawn.** No mission profile binds it, and section 6 is the derivation. Nothing external may claim it or 43.10. |
| **As the SDC period** | **Keep 20 ns, unchanged.** `docs/47` through `docs/50` are four measurement rounds against a fixed 20 ns period; changing it would make every slack in them incomparable, for no gain — the flow needs a target and this one is already the one every measurement was made against. **A target that is not a requirement is still a legitimate optimisation goal.** |
| **As a sign-off criterion** | **Still failing, still a defect.** `Checker.SetupViolations` gates and fails. A failing checker is a failing checker regardless of what the mission needs, and `docs/49` section 10 is four paragraphs on why a green reading is worth exactly what the gate behind it is worth. |

**What changes is the RANK, and that is the actionable part.**
`docs/50` section 12 item 1 is the clearest statement of it in the
record and it ranked this decision first:

> **DECIDE THE TARGET BEFORE SPENDING ANOTHER CYCLE ON IT** … **What is
> owed is one sentence in `docs/05` or `docs/09` saying what the part
> has to do per second.** Until it exists, "closes at 20 ns" is not a
> goal, it is a habit.

**That sentence is section 6.** With it written, `docs/49` section 14's
and `docs/50` section 12's remaining timing items — the memory read
register, `SYNPRE`'s reversal condition, `mtime` — **do not become
wrong; they become unranked.** Nothing in `docs/05` is waiting on any of
them, and section 7.2 shows they do not move the figure of merit the
mission profiles are written in. The two things that should be ranked
above them are the two this document could not measure because nothing
built them:

**FIRST: energy under a duty cycle.** Profiles 1 and 4 are power
requirements, profile 1 is the only quantified requirement in the
section, and the design has one clock, one mode and 27.8–46.1 mW of
continuously burning silicon at a 0.0044 % duty cycle (section 7.3).
**The requirement gap here is four orders of magnitude and the clock gap
is 16 %.** What is needed first is not a design but a measurement: a
`report_power` with real activity from the whole-SoC run's own toggle
rates — **a VCD `hw/soc/tb/tb_soc.v` already dumps behind its `+vcd`
plusarg** **[fact]** — against the `full3` netlist. That turns
section 7.1's estimate-in-a-measurement's-clothes into a number, and
only then is it worth deciding what to gate.

**SECOND: the transport.** 182.57 cycles per serial frame against 6.86
for a pin event is a factor of 27, the transport is 93–98 % of every
workload measured, and `docs/10` section 8 item 2 already specifies the
replacement — a symmetric mesh link at one event per cycle, **a factor
of 182 against the clock's 1.16**. `docs/51` section 3.4 priced the
serial transport correctly and argued correctly that it is the right
transport for *configuration*; **section 5 above measures that it is
also carrying the entire event path**, because the pin contract gives
SYNC no inbound pin and the outbound pins no TYPE field.

**THIRD, and only then: the timing.** `docs/49` section 14 item 1's
memory read register was measured and rejected by `docs/50`; `mtime`
remains the most-deferred item in the record and is still ranked. None
of that changes. What changes is that it is no longer blocking anything
a mission needs.

### 9.4 What may and may not be said outside the repository

`docs/05` section 4 binds this and the rules are quoted rather than
paraphrased.

| | |
|---|---|
| **May not be published** | **50 MHz as an achieved figure** (it is not achieved), **43.10 MHz as a target** (it is a measured non-closure), and **any Fmax at all from `full3`** while that layout has no DRC or LVS result. Rule 5. |
| **May be published, labelled** | "**Design target 50 MHz; the current layout closes at less and the shortfall is not on the mission's critical path**" — provided both halves travel together. Rule 5's "clearly labelled as a design target". |
| **Is the stronger claim anyway** | **That the mission profiles have been sized.** "Three of four profiles are met with two to five orders of magnitude of margin; the fourth is a power requirement the design does not meet and the mechanism is named." That is a claim about a *derived requirement against a measurement*, which is what rule 5 exists to encourage, and it is worth more externally than a frequency. |
| **Power** | **27.8–46.1 mW may be quoted only as a flow estimate at default switching activity**, never as measured consumption. Rule 5 again, and section 7.1 item 3. |

---

## 10. What this does NOT cover

Stated at length, because a throughput model built from one simulated
inference on one geometry is not a mission model and this document would
be worth less than nothing if it were read as one.

- **One workload, one geometry, one configuration.** Every cycle
  measurement is `soc_npu` at 8 x 8, one node, `SER_HALF = 2`, on the
  `docs/51` stimulus and three variants of it. `docs/51` section 15
  already says the end-to-end demonstration is one inference at one
  geometry; **this document adds six workloads and does not add a
  second geometry, a second node, tiling, ECC injection or an upset.**
- **THE PILOT GEOMETRY CANNOT RUN THE EVENT-CAMERA PROFILE AT ALL, AND
  SECTION 6.1 IS NOT A CLAIM THAT IT CAN.** `pilot_top` at 8 x 8 has
  **eight axons**; a DAVIS240C has **43,200 pixels**; and `docs/10`
  section 9 states the limitation explicitly — *"the axon dimension is
  NOT splittable in v0.1 — a layer's fan-in must satisfy fan-in <=
  N_AXONS"* **[fact]**. **Section 6.1 sizes the TRANSPORT against the
  mission's event RATE and says nothing about capability.** What it
  establishes is that if a fabric existed that could consume that
  stream, the connection would carry it at 43.10 MHz; what would have to
  exist first is `docs/02` section 3's Candidate C with an event
  convolution front end, or a down-sampling stage in front of the
  fabric, neither of which is built. **A reader who takes 5.9 % as
  "the pilot does lightning detection" has taken the wrong number.**
- **The full-scale node is not measured and is not modelled.**
  `docs/10` section 5's 512-neuron node reads 32 weight words per
  synaptic event where the pilot reads one. **Nothing here measures the
  fabric's own per-event cost at any geometry**, so every number above
  is about the CONNECTION and not about the inference engine. A
  full-scale node could be the bottleneck and this document would not
  see it.
- **The mission rates are one instrument and one benchmark.** Falcon
  Neuro is two DAVIS240C sensors on the ISS, which is not a CubeSat, not
  the sensor a payload would fly in 2028, and not necessarily
  representative of debris-streak or star-tracker event rates — two of
  the three applications profile 2 names. OPS-SAT-AD is nine channels of
  one CubeSat's telemetry. **Two data points are not a mission model.**
- **Four assumptions carry the event-camera derivation** and they are
  numbered in section 3.1 and 3.2 rather than buried. Assumption 2, the
  frame rate, is the one the conclusion is most sensitive to and
  section 6.5 sweeps it; **the conclusion survives a factor of ten in
  either direction and does not survive a factor of a hundred, at
  either clock.**
- **The power number is not a power measurement.** Section 7.1 item 3:
  no VCD, no SAIF, OpenSTA's default propagated activity. It is right to
  an order of magnitude and is used only where an order of magnitude is
  what the requirement is stated to.
- **Nothing here is at gate level.** Every cycle count is RTL
  simulation, as `docs/51` section 15's last line already says of its
  own. The 43.10 MHz and the power figures are from a placed and routed
  netlist that **has never been simulated** — `docs/49` section 12's
  "nothing has ever simulated `soc_top`'s netlist" is unchanged.
- **No fault is injected anywhere in this document**, and the campaign
  through the connection that `docs/51` section 18 ranks first is not
  this document's subject. A workload sizing says nothing about what an
  upset does to it.
- **The duty-cycle argument of section 7.3 has no mechanism behind it.**
  There is no clock gating in this design, so "0.0044 % busy" is a
  statement about cycles and not about energy. **Nothing here shows that
  a duty-cycled version of this part would reach microwatts**; it shows
  that the current one does not and that the clock is not why.
- **The whole-SoC cycle cost of an inference is not measured here.**
  W1's 3,378 cycles are the event stream at block level, after
  bring-up. `docs/51` section 8.3's whole-program delta is
  **+28,528 cycles [fact]** of which about 14,700 is the work
  **[estimate, that document's]**, and this document did not
  re-decompose it.
- **`docs/05`'s profiles were not re-validated.** They are labelled
  **[estimate]** in that document — "candidate profiles for validation
  in the roadmap phase" — and sizing an unvalidated profile does not
  validate it. **If a fifth profile appears with a hard rate in it, this
  analysis is re-run and may come out differently.**

---

## 11. Corrections and refinements to earlier documents

- **`docs/51` section 4's "asymmetry of about 44x" is 27x when both
  sides are measured the same way.** That figure divides the 176-cycle
  serial frame by the **four cycles of the pin contract**; the engine
  that drives the pin costs **9.00 cycles per event measured** and a
  mixed stream costs **6.86**. 182.57 / 6.86 = **26.6**. This is not an
  error in that document — it states 4 cycles as the pin cost and the
  pin cost is 4 cycles — but the ratio it derives is between a
  transport's delivered cost and a pin's contract cost, and the
  delivered-to-delivered ratio is smaller. Section 4.2.
- **`docs/45` section 8, `docs/47` section 9, `docs/48` section 8,
  `docs/49` section 12 and `docs/50` section 10 all say "no power
  number". There is one**, in `full3`'s own sign-off step, at three
  corners, on extracted parasitics. Section 7.1. **The line those
  documents should have carried is "no power number with real switching
  activity", which is still true.** This is the same shape as `docs/50`
  section 8.1's finding that `soc_bus.sby` had been failing since
  `docs/47` with nobody looking: **a file in a run directory that five
  documents report from, that none of them opened.**
- **`docs/49` section 11.2's "a 13.8 % clock shortfall is a 13.8 %
  throughput shortfall" is exactly right and is confirmed here** —
  section 4.3's ratio column is 1.160 in every row. What that document
  could not say, and this one can, is **what 13.8 % of the throughput is
  a shortfall against**: between 0.0044 % and 10.23 % of the cycle
  budget, depending on the profile.
- **`docs/50` section 7.4's "neither workload is a mission profile"
  stands, and its sensitivity figure is now usable.** That document
  measured **25 % of cycles per extra cycle of memory latency** on two
  CPU-bound programs and said a future workload could be priced against
  it without re-running anything. **The event path is transport-bound
  and not memory-bound, so 25 % is an upper bound on it rather than an
  estimate of it — and even at that upper bound the event-camera profile
  goes from 5.93 % of the cycle budget to 7.4 %** **[estimate]**. **The
  memory read register `docs/50` rejected on wall-clock grounds would
  also have been invisible to every mission profile**: the rejection
  stands and gains a second, independent reason.
- **`docs/01` section 3.3 gives two clock bands that disagree and the
  measurement is inside the conservative one.** Section 8 reading 1.
  Not an error; a choice that document did not have to make and this one
  does.
- **`docs/48` section 7a's "43.10 MHz is inside the range `docs/02`
  states" is correct and is now the weaker of the two available
  statements.** The stronger one is that no mission profile reaches
  within a factor of ten of either end of that range.

---

## 12. What changes elsewhere if this recommendation is taken

| Where | Change |
|---|---|
| **`docs/13-nlnet-application.md`** | It contains **no clock-frequency claim for this SoC** **[fact, `grep MHz` over that file returns only an FPGA `TRELLIS_COMB` figure inside its own README-accuracy audit]**, so nothing in it becomes wrong. **What it may gain** is section 9.4's stronger claim: the mission profiles are sized, three of four are met with two to five orders of margin, the fourth is a named unmet power requirement. That is a better sentence for a funding application than a frequency, and it is the kind of claim `docs/05` section 4 rule 5 was written to reward. |
| **`docs/05-market-positioning.md`** | Section 3.4's four profiles stay **[estimate]** and are not rewritten. **What could be added, if the developer wants it, is the derived column** — profile 1 at 0.0044 %, profile 2 at 5.9–10.2 %, profile 3 at 76,551x, profile 4 unmet — with a pointer here. **Section 4's rules need no change**; they already forbid what section 9.4 forbids, and this document is an instance of rule 5 being applied rather than a case for amending it. |
| **`README.md`** | Must carry no frequency for the SoC. Not checked here; **checking it is the one follow-up this document owes and does not perform**, because `docs/13`'s own README-accuracy audit records README claims that the logs behind them did not support. |
| **`ROADMAP.md`** | If it ranks a timing gate, section 9.3 says the rank is wrong and gives the two items that should sit above it. Not edited here. |
| **`docs/09-formal-verification-plan.md` or `docs/15`** | `docs/49` section 14 item 2 assigned the workload-sizing obligation to one of those two. **It is discharged here instead**, in a document of its own, because it is about the SoC and `docs/15` is about a frozen tile. Neither of those documents needs editing; this row exists so the obligation is not left looking open. |
| **The flow** | **Nothing.** `hw/soc/pnr/config.json` keeps `CLOCK_PERIOD` at 20 ns, for the reason in section 9.3: four documents' slacks are comparable only because it did not move. |
| **The RTL** | **Nothing, today.** Section 9.3's first two items are a measurement and an architecture change, and the measurement comes first for the reason `docs/38` section 10 item 4 and `docs/51` section 18 both give: protecting or optimising before measuring costs area and buys nothing. |

---

## 13. Files touched

| File | Change |
|---|---|
| `docs/53-workload-and-the-clock.md` | this document |
| `docs/00-index.md` | one row, which `sw/tests/test_doc_links.py` requires |

**No other file in this repository was modified** **[fact,
`git status`]**. In particular nothing under `hw/`, `sw/`, `tt/`,
`formal/`, `regmap/` or `scripts/` was written, and `hw/soc/tb/` and
`hw/soc/fi/` were not entered at all.

**The measurement harness is deliberately outside the working tree.**
`test_npu_throughput.py` and its `Makefile` live in a scratch directory,
compile `hw/soc/rtl/soc_npu.v`, `hw/soc/rtl/soc_npu_ser.v` and the seven
frozen `hw/rtl/` files by absolute path, and `import` the existing
`hw/soc/tb/cocotb/test_soc_npu.py` for its bus drivers, its `docs/10`
section 11.1 bring-up and its stimulus — **so no driver, no register
offset and no golden model is restated here.** Section 14 reproduces it,
and the reason it is a scratch directory rather than a seventh Makefile
in `hw/soc/tb/cocotb/` is that another block was being written into that
directory while this document was being measured.

---

## 14. Reproducing this

The published figures, first:

```
V=$HOME/Documents/caravel-lif-crossbar/.venv-flow/bin/python
$V hw/openlane/signoff_report.py hw/soc/pnr/runs/full3
#   -3.2029 / 2003 at nom_slow_1p08V_125C, and the other two corners

cat hw/soc/pnr/runs/full3/19-openroad-stapostpnr/nom_typ_1p20V_25C/power.rpt
#   34.835 mW total; the same file exists for the other two corners
```

The cycle measurements. The harness is two files; recreate them in any
directory outside the tree, with `MODULE = test_npu_throughput`,
`TOPLEVEL = soc_npu`, the nine Verilog sources of
`hw/soc/tb/cocotb/Makefile.soc_npu`, the same six `-P` overrides, and

```
export PYTHONPATH=<harness dir>:<repo>/hw/soc/tb/cocotb
PATH=<repo>/hw/.venv/bin:$PATH make
```

The harness defines one workload per `@cocotb.test()`; each does
`Env.reset()`, `bring_up()` and `cwr(C_CTRL, IN_EN|OUT_EN)` from the
imported suite, then times the stream between the first `EVQ_IN` write
and the last barrier, and asserts `CNT_DROP == 0` and that the
hardware's `CNT` agrees with the stream it collected. **The two
constants of section 4.2 are then solved from W3b and W4b and checked
against W1, W2, W3 and W4, which the fit never saw.**

Expected output, which is section 4.1:

```
W1_docs51_6_frames            6   3378  22  12  16  18
W2_docs51_x4_24_frames       24  12477  88  42  64  66
W3_24_empty_frames           24   9000  48  24  24  48
W4_24_frames_6_spikes        24  16560 192  60 168  84
W4b_24x6_no_full_poll        24  16488 192  60 168  84
W3b_24_empty_no_full_poll    24   8928  48  24  24  48
W5_pin_path_alone   8 strobes, 63 cycles first to last, 9.00 per event
W6_one_register_access                            176 cycles
```

---

## 15. What the next document should establish

Two measurements, both of them gaps section 10 names, and neither of
them a design.

1. **`report_power` with the whole-SoC run's own switching activity**,
   against the `full3` netlist, so that section 7.1's estimate becomes a
   measurement and the duty-cycle question of section 7.3 can be asked
   with a number behind it. The VCD exists; nothing has been pointed at
   it. **This is the smallest piece of work in the record that closes
   the largest requirement gap in it.**
2. **The fabric's own per-event cost, at a geometry that is not 8 x 8.**
   Everything in this document is about the connection; `docs/10`
   section 5's 32-word read at 512 neurons is the number that decides
   whether the *inference engine* is ever the bottleneck, and no
   document has it. Until it exists, section 6's margins are margins on
   the transport and are silent about the fabric.
