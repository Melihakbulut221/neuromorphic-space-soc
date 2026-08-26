# Neuromorphic Space SoC — pilot device datasheet

Device: the ROADMAP phase P1 pilot, hardened and submitted as
`tt_um_melihakbulut_nssoc` on the Tiny Tapeout TTIHP26b shuttle
(IHP SG13G2, 130 nm bulk CMOS).

Revision: 0.1, 26 August 2026. Status: **pre-silicon**. The design is
frozen for content and is being re-hardened after the configuration-TMR
fix of 2026-08-26; silicon is expected 2027-06-25 with boards around
2027-08 (`ROADMAP.md` section 1).

## 0. How to read the numbers in this document

Every quantity is tagged:

- **[measured]** — obtained from a tool run or an installed file in this
  repository, and the artifact is named.
- **[target]** — a design goal, not yet demonstrated on the object it
  describes.
- **[TBD]** — not known, and not estimated here.
- **[in flux]** — measured, but against an artifact that is being
  regenerated right now. The figure is directionally right and the exact
  value will move; section 7.2 lists every one of them.

Where a figure is [measured], the reader can reproduce it: the commands
are in section 9.

This datasheet takes `regmap/regmap.yaml` as the single source of truth
for the register map, `hw/rtl/` as the single source of truth for
behaviour, and the mapped netlists under `tt/runs/` as the single source
of truth for what physically exists. Where a prose document in this
repository disagrees with one of those, this datasheet follows the
source and section 10 records the disagreement.

---

## 1. Overview

### 1.1 What the device is

The pilot is a single, self-contained spiking-neural-network processing
node on a small piece of 130 nm silicon. Instead of multiplying arrays
of numbers the way a conventional accelerator does, it processes
*events*: a host or a sensor announces that input line *a* fired, the
chip adds that line's stored synaptic weights into the membrane
potentials of its neurons, and any neuron whose potential crosses a
programmable threshold emits an output event of its own and resets. Work
happens only when an event arrives, which is what makes the style
attractive for a power-limited spacecraft payload. Around that
event-processing datapath the device carries the fault-tolerance
machinery that is the actual point of the exercise: error-correcting
codes on the weight storage, triple-redundant voted configuration
registers, a scrub path that repairs a corrected word in place, fault
counters, and four dedicated output pins that make every one of those
events visible on an oscilloscope with no host software running. It is
programmed and observed over a three-wire serial port, and its event
interface is also exposed on dedicated pins so that a bench can drive it
without a host at all.

### 1.2 What the device is not

This is a shuttle pilot: an engineering vehicle whose purpose is to
prove a PDK, a flow, an SNN datapath slice and a set of hardening
demonstrators on cheap silicon before a full SoC is committed. Stated
plainly, and binding on every public description of this part
(`docs/05-market-positioning.md` section 4):

- **It is not a flight part.** There is no screening, no qualification,
  no lot traceability, no reliability programme. It is a multi-project
  shuttle die in a Tiny Tapeout carrier.
- **It is fault-tolerant by architecture, not radiation-hardened by
  process.** IHP SG13G2 is a commercial bulk 130 nm technology with no
  intrinsic single-event-latchup immunity. Every tolerance property this
  device has comes from TMR, ECC, scrubbing and monitors, and section 6
  reports exactly how far that goes and where it stops.
- **The design target is LEO-class total dose, 10-30 krad(Si)**
  **[target]**, pending test data. No total-dose, single-event-upset
  rate, cross-section or latch-up figure has been measured for this
  device, and none is claimed. The fault-injection campaign of section
  6.2 reports *conditional* outcomes — what happens given that an upset
  lands somewhere — and says nothing whatever about how often that
  happens (`docs/16` section 7.5).
- **It is not a general-purpose accelerator.** Inference only, no
  on-chip learning, no convolution engines, 4-bit weights only.
- **It carries no management processor.** The full-SoC architecture
  places an RV32 core beside this block; the pilot is driven from its
  host serial port instead, which is what a bring-up board does anyway.
- **It carries no SRAM macro.** All storage is flip-flops. The IHP
  SRAM macro was evaluated and is a NO-GO for this shuttle
  (`docs/12-sg13g2-flow-bringup.md` sections 7 and 8), which is why the
  pilot geometry is small.

### 1.3 Feature summary

| Item | Value | Tag |
|---|---|---|
| Technology | IHP SG13G2, 130 nm bulk CMOS | [measured] |
| Tile shape | Tiny Tapeout 4x2 (8 tiles) | [measured] |
| Die area (4x2 block) | 268,059 um2 | [measured] |
| Core (placement rows) area | 259,837 um2 | [measured] |
| Neurons | 8 | [measured] |
| Input axons | 8 | [measured] |
| Synapses | 64, 4-bit signed, in flip-flops | [measured] |
| Membrane potential | 16-bit signed per neuron | [measured] |
| Event queues | 2 x 4 entries, 16-bit words | [measured] |
| Weight word protection | (72,64) Hsiao SECDED, single-error correcting, double-error detecting | [measured] |
| Configuration protection | 55 bits, triple modular redundancy, majority voted | [measured] |
| Host interface | Mode-0 SPI slave, 40-bit frames | [measured] |
| Total flip-flops, mapped netlist | 1155 | [measured, in flux] |
| Clock target | 50 MHz | [target] |
| Power | see section 7.3 | [TBD] |
| Radiation performance | see section 7.3 | [TBD] |

The 8 x 8 geometry is an elaboration parameter, not an architectural
limit. `hw/rtl/pilot_top.v` accepts N_NEURONS and N_AXONS as powers of
two in [4, 16]; the architecture the pilot instantiates a slice of is
specified at 512 x 512 (`docs/10-npu-mvp-spec.md` section 2). The pilot
is the geometry that fits eight Tiny Tapeout tiles.

---

## 2. Block diagram and block descriptions

```
                    ui_in[2:0]                          uo_out[0]
                  SER_SCK/CS_N/MOSI                      SER_MISO
                         |                                   ^
                         v                                   |
                 +-------------------------------------------+------+
                 |            SERIAL HOST INTERFACE                 |
                 |   mode-0 SPI slave, 40-bit frame, 2FF sync       |
                 +----------------------+---------------------------+
                                        | 32-bit register access
                                        v
   +------------------------------------+-----------------------------+
   |                          REGISTER BANK                           |
   |   regmap/regmap.yaml subset + 3 pilot-only registers             |
   |   fault counters (8-bit, saturating), sticky status bits         |
   +---+------------------------+---------------------+---------------+
       |                        |                     |
       | 55-bit config          | 64-bit weight word  | events / state
       v                        v                     v
   +---+-------+        +-------+--------+        +---+---------------+
   | TMR       |        | SECDED CODEC   |        |  AER EVENT QUEUES |
   | 3 x 55-b  |        | secded_enc     |        |  EVQ_IN  16b x 4  |<- ui_in[4:3]
   | replicas  |        | 72-bit stored  |        |  EVQ_OUT 16b x 4  |   AER_IN_*
   | + voter   |        | word           |        |                   |
   +---+-------+        | secded_dec     |        +---+---------------+
       |                +---+--------+---+            |            ^
       | voted              |        ^                v            |
       | config             |        |          +-----+------------+--+
       |                    |        |          | EVENT DISPATCHER    |
       |                    |        | SCRUB    | TYPE decode, axon    |
       |                    |        | write-   | bound check, SYNC    |
       |                    |        | back     | echo, bounded fetch  |
       |                    |        |          +-----+---------------+
       |                    |    +---+-------+        |
       |                    |    | SCRUB     |<- ui_in[6] SCRUB_STB
       |                    |    | CONTROL   |
       |                    |    +-----------+
       v                    v (16 decoded weights)
   +---+--------------------+-----------------------------------------+
   |                        LIF NEURON CORE                           |
   |  wmem 8x8 x 4b  |  vmem 8 x 16b  |  rmem 8 x 4b                  |
   |  Hamming-distance-2 FSM, S_SAFE park, err_cfg out                |
   +------------------------------+-----------------------------------+
                                  |
                                  v  spikes
                          EVQ_OUT --> uio[7:4] AER_OUT_ID
                                      uo_out[3] AER_OUT_VLD

   Fault visibility pins: uo_out[4] ERR, [5] SEC, [6] DED, [7] TMR
```

### 2.1 LIF neuron core (`hw/rtl/lif_core.v`)

The arithmetic. It holds the synaptic weight file (`wmem`, 8 x 8 4-bit
signed values), the membrane potentials (`vmem`, 8 x 16-bit signed) and
the refractory counters (`rmem`, 8 x 4-bit), and implements equations
E1 to E7 of section 4 exactly. One synaptic event sweeps all neurons in
ascending index order; one TICK event applies leak and decrements the
refractory counters. Its control FSM uses a Hamming-distance-2
even-parity state encoding over five legal states, so any single-bit
upset in the state register lands on a word no legal transition can
produce: the core parks in `S_SAFE`, freezes the neuron state file and
raises `err_cfg`, which reaches `STATUS.ERR_CFG` and the ERR pin.
Recovery is `CTRL.SOFT_RST`. The core is verified bit-for-bit against
`sw/golden/lif_core.py` and carries eight SymbiYosys proof tasks.

The core carries no runtime active-neuron count by design, which is why
`CFG_NEUR` is read-only in this device (deviation D2, section 5.5).

### 2.2 AER event queues (`hw/rtl/aer_fifo.v`, two instances)

Two 16-bit x 4-entry FIFOs. `EVQ_IN` accepts events from two sources —
the serial `EVQ_IN` register and the `AER_IN_STB` pin — and drops on
full, counting the drop in `CNT_EVQ_OVF` and setting `STATUS.OVF_SEEN`.
`EVQ_OUT` collects spikes and SYNC echoes; it never drops, because the
core's `out_ready` is `!full`, so a full output queue stalls the update
pipeline instead. Both queues are formally proven (`prove`, `prove_d4`,
`bmc`, `cover` all PASS).

`aer_fifo` is a registered-output queue, and the register map defines
`EVQ_OUT` as a single-access pop. A one-entry show-ahead holding
register between the two closes that gap; it is the reference
implementation of the register bank's convention C9. `EVQ_STAT.OUT_FILL`
counts the held word, so the fill level a host reads is the number of
events it can still get out.

### 2.3 Register bank

The programmer's view. It implements the subset of `regmap/regmap.yaml`
listed in section 5.3 plus three pilot-only observability registers, all
addresses and reset values taken from the generated header
`hw/rtl/npu_regs.vh` and never hand-copied — an elaboration guard fails
the build if the generator moves a field this module encodes
structurally. It holds the fault counters (8 bits, saturating, deviation
D1) and the sticky status bits, and it drives the four fault pins.

The standalone architecture register bank `hw/rtl/npu_regbank.v` — the
full 4 KB node window with a valid/ready bus slave interface — exists
and is verified, but is **not** instantiated in this pilot; the pilot's
register file is inside `pilot_top.v` behind the serial port.

### 2.4 SECDED codec (`hw/rtl/secded_enc.v`, `hw/rtl/secded_dec.v`)

A (72, 64) Hsiao single-error-correcting, double-error-detecting code:
64 data bits (16 four-bit weights) plus 8 check bits, 12.5 percent
overhead. This is not a bolted-on demonstrator — the 64-bit word a host
writes through `W_DATA_LO`/`W_DATA_HI` *is* the data field of a
physically stored 72-bit codeword. On commit the check field is
computed, the armed `ECC_INJ` pattern is XORed into the stored word, the
decoder runs, and the weight loader writes 16 weights into `lif_core`
**from the decoder output**. A corrected single-bit upset therefore
never reaches the datapath, and an uncorrectable word contributes zero
to every neuron (equation E10). `CNT_SEC`, `CNT_DED`, `FAULT_ADDR`,
`STATUS.DED_SEEN` and the SEC and DED pins record what happened.

### 2.5 TMR voter (`hw/rtl/tmr_voter.v`)

Every configuration bit that reaches the neuron core — THETA, V_RESET,
S_LEAK, S_SYN, T_REFR, the mode flags and PASS_TILE_OFF, 55 bits in
total — is held in three independent replicas and majority-voted before
it leaves the register block. Software reads the voted value, so a
masked upset is invisible to it; `CNT_TMR` and the TMR pin make it
visible to the operator, which is the fault-visibility convention this
project takes from GRLIB practice (`docs/08` section 2.3).

The three replicas are `pilot_cfg_bank` submodule instances carrying
`keep_hierarchy`, and each instance stores its value under a different
polarity: replica A true, replica B fully complemented, replica C with
the odd bits complemented. Both mechanisms exist because of the defect
described in section 6.3, and neither is trusted on its own —
`sw/tests/test_synthesis_guards.py` counts the flip-flop cells per bank
in the mapped netlist of both synthesis flows and fails if any bank
collapses.

Honest limit, stated in `tmr_voter.v`'s own contract: nothing
resynchronises a faulty replica. A disagreement persists until software
rewrites the configuration, which repairs all three banks. `CNT_TMR`
counts episodes (one per rising edge of mismatch), not cycles.

### 2.6 Scrub controller

Scrubbing exists in this device as a *strobed re-check*, not as a
free-running background walker. A rising edge on the `SCRUB_STB` pin
re-reads the stored 72-bit codeword through the decoder; with
`CTRL.SCRUB_EN` set (its reset value) a correctable word is written back
repaired. Because the injected error survives in the stored word, a
bench can re-check it as often as it likes, and `ECC_INJ_POS` moves the
injected bit anywhere in the 72-bit codeword so the full syndrome space
is walkable on silicon.

The full background scrub controller `hw/rtl/scrub.v` — address walk,
lowest-priority memory port, structural window containment, and the rule
that a double-bit detection never writes back — exists and is verified
in this repository but is **not** instantiated in this pilot. It belongs
to the SRAM-macro build.

### 2.7 Serial host interface

A mode-0 SPI slave (CPOL 0, CPHA 0), MSB first, one register per frame.
`SER_SCK`, `SER_CS_N` and `SER_MOSI` are two-flop synchronised and
edge-detected inside the `clk` domain, which is the origin of the three
host timing obligations in section 5.2. Writes commit on the 40th rising
edge rather than at chip-select release, so an aborted frame changes
nothing.

### 2.8 Event dispatcher

Glue with one architectural job: pop a word from `EVQ_IN`, decode its
TYPE field, and drive the core. SPIKE events with an axon id at or above
`CFG_AXON` are dropped and counted in `CNT_AXON_OOR`; TICK goes straight
through; SYNC is held until the core is idle, then echoed into `EVQ_OUT`
with `STATUS.SYNC_DONE` set; the reserved TYPE is dropped without a
counter. Its fetch state carries a bounded wait with a timeout that
raises `ERR_CFG` — added in response to the deadlock the fault-injection
campaign found (section 6.2).

---

## 3. Signal description

The device presents the fixed Tiny Tapeout port budget: 8 dedicated
inputs, 8 dedicated outputs, 8 bidirectionals, plus clock and reset from
the shuttle infrastructure. All 24 are assigned; one input is reserved.
`uio_oe` is the constant `0xF0`, so the bidirectional directions are
fixed at elaboration. **[measured, `hw/rtl/tt_um_melihakbulut_nssoc.v`]**

### 3.1 Dedicated inputs

| Pin | Name | Function |
|---|---|---|
| ui_in[0] | SER_SCK | Serial clock, mode 0 (CPOL 0, CPHA 0), max clk/4 |
| ui_in[1] | SER_CS_N | Frame select, active low |
| ui_in[2] | SER_MOSI | Serial data in, MSB first |
| ui_in[3] | AER_IN_STB | External AER event strobe, rising-edge triggered |
| ui_in[4] | AER_IN_TICK | 0 = SPIKE at AER_IN_ADDR, 1 = TICK |
| ui_in[5] | AER_OUT_ACK | External AER consumer acknowledge, rising-edge |
| ui_in[6] | SCRUB_STB | ECC re-check / scrub pulse, rising-edge triggered |
| ui_in[7] | reserved | Tie low |

### 3.2 Dedicated outputs

| Pin | Name | Function |
|---|---|---|
| uo_out[0] | SER_MISO | Serial data out, MSB first |
| uo_out[1] | BUSY | STATUS.BUSY |
| uo_out[2] | AER_IN_RDY | Input queue has room for one more event |
| uo_out[3] | AER_OUT_VLD | An event id is presented on AER_OUT_ID |
| uo_out[4] | ERR | STATUS.ERR_CFG (live or sticky) or STATUS.OVF_SEEN |
| uo_out[5] | SEC | Sticky: at least one single-bit ECC error corrected |
| uo_out[6] | DED | Sticky STATUS.DED_SEEN |
| uo_out[7] | TMR | Sticky: the configuration voter masked a disagreement |

Four of the eight outputs are fault pins, deliberately: it makes every
hardening event visible on an oscilloscope with no host software, which
is what a radiation-effects bench needs. All four clear through
`STATUS_CLR` or `FAULT_CLR`.

ERR has an important asymmetry. `STATUS.ERR_CFG` is the OR of a sticky
bit that `STATUS_CLR` clears and a *live* level from the neuron core's
parked-FSM output. While the core is parked, `STATUS_CLR` cannot clear
the bit — reporting a fault as gone while the core is still refusing
work would be worse than not reporting it. The live signal is also
latched into the sticky bit, so `CTRL.SOFT_RST`, which is the recovery
for that fault, does not erase the evidence that the upset happened.

### 3.3 Bidirectionals

| Pin | Direction | Name | Function |
|---|---|---|---|
| uio[3:0] | input | AER_IN_ADDR | Axon id for the strobed event |
| uio[7:4] | output | AER_OUT_ID | Emitted neuron id |

The nibbles are exact for this geometry because N_AXONS and N_NEURONS
are both 8. The full 16-bit event word is always readable over the
serial `EVQ_OUT` register; the uio nibble is the low four bits of its ID
field, for a consumer that wants the event stream without a host.

### 3.4 Clock, reset and enable

`clk` and `rst_n` come from the shuttle infrastructure. `rst_n`
deassertion is not guaranteed synchronous to `clk`, so the wrapper
carries a two-flop synchroniser: the assertion path stays asynchronous
and the deassertion is synchronous, so a reset release landing inside a
setup window cannot leave different flip-flops in different reset
states. `ena` is driven by the Tiny Tapeout multiplexer and is sunk
explicitly; the design has no use for it.

**Neuron state and weight storage are not on the reset net.** Reset
returns the registers of section 5.3 to their reset values and flushes
both queues, and leaves `vmem`, `rmem` and `wmem` undefined. Software
must load weights and run `CTRL.STATE_CLR` before enabling the core.
This is deliberate: it is what lets `CTRL.SOFT_RST` recover a parked
core without destroying the neuron state an operator is trying to read.

---

## 4. Neuron model

This section is what an implementer needs to write a driver or a
bit-exact model. The equation tags are the normative ones from
`docs/10-npu-mvp-spec.md` section 4, and each is bound to at least one
test in `sw/tests/` by a traceability check that fails if any tag lacks
a matching test.

### 4.1 Per-neuron state

24 bits per neuron:

| Bits | Field | Meaning |
|---|---|---|
| [15:0] | V | membrane potential, signed 16-bit two's complement, [-32768, +32767] |
| [19:16] | R | refractory countdown, unsigned 4-bit, 0 = not refractory |
| [23:20] | reserved | zero; the hook for per-neuron parity if it is ever added |

Readable and writable through `N_ADDR`/`N_DATA`. State after hardware
reset is UNDEFINED.

### 4.2 Synaptic event processing

Consuming one SPIKE event with axon id `a` updates neurons
j = 0, 1, ..., N-1 in ascending order. For each neuron j:

**Refractory gate (E7).** If R[j] > 0 the event is discarded for this
neuron: no state change, no spike, proceed to j+1. Otherwise:

**(E1) Weight decode.** The stored 4-bit code is signed two's
complement:

```
w = sext4(W[a][j]),   w in [-8, +7]
```

**(E2) Synaptic contribution.** Scaled by the configured left shift,
exactly — no truncation, no rounding:

```
c = w * 2^S_SYN,   S_SYN in [0, 7]   =>   c in [-1024, +896]
```

If the weight word holding W[a][j] is flagged uncorrectable by ECC,
c = 0 is substituted (E10).

**(E3) Saturating integration.** Computed at full width, then clamped:

```
V'[j]    = sat16(V[j] + c)
sat16(x) = +32767 if x > +32767; -32768 if x < -32768; else x
```

The pre-saturation sum fits in 18 signed bits. Two's-complement
wraparound is a specification violation — a wrapped positive overflow
would silently lose a spike.

**(E4) Spike condition.** Evaluated *after* E3, on every non-gated
synaptic event, including events whose contribution is zero:

```
spike(j)  <=>  V'[j] >= THETA        (signed compare)
```

The compare uses the post-saturation value. Checking before the update,
or one event late, is a specification violation; the check-after-update
ordering is deliberate and tested.

**(E5) Reset on spike.** If spike(j):

```
V''[j] = V_RESET
R[j]   = T_REFR
```

and one output spike event with neuron id `TILE_OFF + j` is emitted. If
no spike, V''[j] = V'[j] and R[j] is unchanged.

### 4.3 Tick processing

Consuming one TICK event updates neurons j = 0..N-1 in ascending order,
with two independent actions and no spikes ever emitted.

**(E6) Leak as right-shift toward zero**, applied when
`CFG_FLAGS.LEAK_EN` = 1, with a minimum decrement of 1 so that every
nonzero potential reaches zero in bounded time:

```
if V[j] == 0:  V'[j] = 0
else:
    m = |V[j]| >> S_LEAK        (logical shift of the magnitude)
    if m == 0: m = 1
    V'[j] = V[j] - m   if V[j] > 0
    V'[j] = V[j] + m   if V[j] < 0
```

Normative properties: |V'| < |V| for V != 0; the sign never flips; the
magnitude is computed at 16-bit unsigned width so |-32768| = 32768 is
representable; S_LEAK = 0 clears the potential in one tick. Leak applies
regardless of refractory state.

**(E7) Refractory countdown.** On TICK, R'[j] = R[j] - 1 if R[j] > 0,
else 0.

TICK never emits: E6 moves V strictly toward zero, and configuration
validation enforces V_RESET < THETA, so no threshold crossing is
possible on a tick.

### 4.4 Ordering and determinism (E8)

The core is a deterministic function of (initial state, configuration,
weights, input event stream):

1. Input events are consumed strictly in FIFO arrival order; all neuron
   updates for event k complete before event k+1 begins.
2. Within one synaptic event, neurons are scanned in ascending index j
   and output spikes are emitted in scan order.
3. The output stream is the concatenation of per-event emissions in
   input event order. Event arrival order outranks neuron id order
   across events.
4. TICK processing emits nothing and completes before the next event.

No arbitration, no clock-dependent reordering, no dropped events on the
processing path. This is what makes a software model bit-exact against
the hardware, and it is what makes a fault-injection result
attributable to the fault rather than to timing.

### 4.5 Event word format

16 bits, frozen at v0.1 and extendable but not changeable:

| Bits | Field |
|---|---|
| [15:14] | TYPE |
| [13:10] | reserved, zero |
| [9:0] | ID (axon id on input, neuron id on output) |

| TYPE | Name | Input meaning | Output meaning |
|---|---|---|---|
| 00 | SPIKE | synaptic event, ID = axon id | spike, ID = TILE_OFF + neuron id |
| 01 | TICK | timestep boundary | not emitted |
| 10 | SYNC | frame barrier: when consumed, all prior events are fully processed and a SYNC is emitted downstream | barrier echo |
| 11 | reserved | dropped, not counted | not emitted |

SYNC is the determinism and multi-pass handshake primitive. The host
injects SYNC after a frame; the emitted SYNC plus `STATUS.SYNC_DONE`
tells the host that the output stream for that frame is complete. TICK
generation is external — the core consumes time, it does not create it.

With `CFG_FLAGS.TS_EN` = 1 every event word is followed by a 16-bit
free-running tick-counter word. Timestamps are observability metadata
only: processing semantics are defined by logical order (E8), never by
timestamp values.

### 4.6 Multi-pass execution, and what it means for a driver

The physical core holds exactly one N_AXONS x N_NEURONS weight slice.
Networks larger than that are executed as a sequence of passes, and the
sequencing is entirely the host's job in this device — there is no DMA
and no hardware sequencer. A pass is:

1. Load the weight slice for this pass through
   `W_ADDR`/`W_DATA_LO`/`W_DATA_HI`.
2. Load configuration (section 5.4) and `PASS_TILE_OFF`.
3. Replay the input event stream for this pass.
4. Collect output events until the SYNC echo appears.

Two pass dimensions are supported:

**Layer-serial.** One layer per pass. The output events of a layer
become the input events of the next, preserving per-timestep order.

**(E9) Output-neuron tiling.** For layers wider than N_NEURONS,
partition the layer's output neurons into ordered contiguous tiles of at
most N_NEURONS. Run one pass per tile with the corresponding weight
column slice and `PASS_TILE_OFF` = tile base, replaying the *identical*
input event stream each pass. Concatenating, for each input event, the
tiles' emissions in tile order yields a stream bit-identical to a
hypothetical core wide enough for the whole layer. This holds because
neuron trajectories are mutually independent — there is no lateral
coupling — so each neuron's state depends only on the event stream, its
own weight column, and the configuration.

**Two limits, both hard, both explicit:**

- **The axon dimension is not splittable.** A layer's fan-in must
  satisfy fan-in <= N_AXONS. Axon-split passes would interleave
  saturation and threshold crossings in a different order and break
  bit-exactness. A deferred-threshold pass mode would be needed and is
  not in this revision.
- **The tiling bound is 1024 neurons per layer.** Both the ID field of
  the frozen event word and `PASS_TILE_OFF` are 10 bits, so every tile
  must satisfy TILE_OFF + tile width <= 1024. A layer wider than 1024
  neurons cannot be represented on the event interface and is **refused,
  not approximated** — the golden model rejects such layers at
  construction, and a driver should do the same.

Three consequences a driver author must plan for.

First, tiling multiplies the *event* traffic, not just the weight
traffic: the same input stream is replayed once per tile, so a four-tile
layer costs four replays through the queue and four full weight loads.

Second, **the tiles of one layer share the physical state file, and the
driver owns the bookkeeping.** Each tile is a different set of neurons,
so each tile has its own V and R; the device holds only one tile's worth
at a time. A tile must therefore start from the state that tile ended
with, not from the previous tile's. For a single frame that means
`CTRL.STATE_CLR` before each tile's pass. For a sequence of frames it
means saving each tile's state through `N_ADDR`/`N_DATA` at the end of
its pass and restoring it before that tile's next pass — which is what
that register pair exists for.

Third, the emission order is defined and the driver must preserve it
when reassembling: for each input event, the tiles' emissions
concatenated in ascending tile order. Because the passes are run
serially, the device produces them grouped by tile; recovering the
equivalent single-core stream is a reordering the host performs, not
something the hardware does.

---

## 5. Programming model

### 5.1 Address model

The architecture defines a 12-bit byte-address space — one 4 KB window
per node instance — of 32-bit word-aligned registers, with a constant
identity word and a version word at the base of every block. This
mirrors the GRLIB model of memory-mapped peripherals with plug-and-play
discovery (`docs/08` section 2.1). `ID` reads `0x4E505531`, the ASCII
string `NPU1` with the vendor byte `0x4E` leading.

In this device the window is reached over the serial port, and
`ADDR[6:0]` in the command byte is the byte offset shifted right by two.
Every offset in the map is below 0x100, so the whole map is reachable in
seven bits.

### 5.2 Host protocol and timing

**Frame: 40 `SER_SCK` cycles.**

```
bits 39..32   command byte { WR, ADDR[6:0] },  WR = 1 writes
bits 31..0    register data, MSB first
```

Reads: the addressed register is captured when the command byte
completes and is shifted out on the following falling edges, so the host
samples data bit 31 on `SER_SCK` cycle 9. Read side effects — there is
exactly one, the `EVQ_OUT` pop — happen once, at that capture. Writes
commit on the 40th rising edge, not at chip-select release, so an
aborted frame changes nothing.

**Three host obligations. All three are real constraints, and host
software that violates any of them will read or write the wrong thing.**

| Id | Obligation | Why |
|---|---|---|
| **H1** | `SER_SCK` <= `clk`/4 | The serial port lives entirely in the `clk` domain behind two-flop synchronisers. |
| **H2** | **`SER_CS_N` must fall at least one full `SER_SCK` period before the first `SER_SCK` edge** | The frame-start reset has to clear the synchroniser before the first sampled clock edge arrives. A host that drops the select and clocks immediately risks losing the first command bit. |
| **H3** | `SER_CS_N` must stay high at least one full `SER_SCK` period *between* frames | The bit counter is held at zero only while the synchronised select reads inactive. A deselect that is never seen leaves the counter running and the next frame decodes at the wrong offset. |

H2 and H3 are not theoretical. H2 is a trap recorded in a sibling
project's shipped submission and applies here for the same reason; H3
was found during this pilot's bring-up with a half-period gap. Both
boundaries are held by the cocotb suite at their exact values.

### 5.3 Register map

Access codes: RO read-only, RW read-write, WO write-only, W1C
write-1-to-clear, SC self-clearing write.

Reset values are those of `regmap/regmap.yaml`. Where this device
differs, the pilot column says so; those differences are the documented
deviations of section 5.5.

#### sys

| Offset | Name | Access | Reset | Bit fields |
|---|---|---|---|---|
| 0x00 | ID | RO | 0x4E505531 | Identity constant, ASCII `NPU1` |
| 0x04 | VERSION | RO | 0x00000001 | Spec/regmap version |
| 0x08 | SCRATCH | RW | 0x00000000 | Read/write test register, no side effects |
| 0x0C | CTRL | RW | 0x00000008 | b0 EN (RW), core enable; b1 STATE_CLR (SC), zero all neuron state, BUSY while running; b2 SOFT_RST (SC), flush queues and pipeline, configuration retained; b3 SCRUB_EN (RW), ECC scrub enable |
| 0x10 | STATUS | RO | 0x00000006 | b0 BUSY; b1 EVQ_IN_EMPTY; b2 EVQ_OUT_EMPTY; b3 SYNC_DONE (sticky); b4 ERR_CFG (sticky + live); b5 DED_SEEN (sticky); b6 OVF_SEEN (sticky) |
| 0x14 | STATUS_CLR | W1C | 0x00000000 | Write-1-to-clear mask for STATUS b3..b6 |

`CTRL` reads back b2 as zero: `SOFT_RST` is self-clearing and is never
observable as set.

#### cfg — core-global configuration, loaded per pass

| Offset | Name | Access | Reset (arch) | Reset (pilot) | Bit fields |
|---|---|---|---|---|---|
| 0x20 | CFG_NEUR | RW | 0x00000200 | 0x00000008, **RO** | CNT [10:0], neurons swept per event, [1, N_NEURONS] |
| 0x24 | CFG_AXON | RW | 0x00000200 | 0x00000008 | CNT [10:0], events with axon id >= CFG_AXON are dropped and counted |
| 0x28 | CFG_THRESH | RW | 0x00000100 | same | THETA [15:0], signed, [1, +32767], must be positive |
| 0x2C | CFG_VRESET | RW | 0x00000000 | same | VRESET [15:0], signed, must be below THETA |
| 0x30 | CFG_LEAK | RW | 0x00000003 | same | S_LEAK [3:0], right shift per tick, [0, 15] |
| 0x34 | CFG_SYNSHIFT | RW | 0x00000000 | same | S_SYN [2:0], left shift on decoded weights, [0, 7] |
| 0x38 | CFG_REFR | RW | 0x00000000 | same | T_REFR [3:0], ticks of post-spike gating, [0, 15]; 0 disables |
| 0x3C | CFG_FLAGS | RW | 0x00000002 | same | b0 TS_EN, timestamp word on every AER event; b1 LEAK_EN, enable leak on TICK |

#### pass — multi-pass sequencing

| Offset | Name | Access | Reset | Bit fields | In pilot |
|---|---|---|---|---|---|
| 0x40 | PASS_TILE_OFF | RW | 0x00000000 | OFF [9:0], added to emitted neuron ids | yes |
| 0x44 | W_BASE | RW | 0x00000000 | QSPI byte address of the current pass weight slice | **no** |
| 0x48 | PASS_ID | RW | 0x00000000 | NUM [7:0], software pass bookkeeping | **no** |

`W_BASE` and `PASS_ID` are multi-pass sequencer bookkeeping with no
hardware effect in a single-pass build. In this device they read as zero
and reject writes, like any unmapped offset.

#### mem — weight load port and neuron state access

| Offset | Name | Access | Reset | Bit fields |
|---|---|---|---|---|
| 0x50 | W_ADDR | RW | 0x00000000 | Weight SRAM word index; auto-increments on W_DATA_HI commit |
| 0x54 | W_DATA_LO | WO | 0x00000000 | Weight word bits [31:0] |
| 0x58 | W_DATA_HI | WO | 0x00000000 | Weight word bits [63:32]; the write commits the 64-bit word and generates the ECC check field in hardware |
| 0x60 | N_ADDR | RW | 0x00000000 | Neuron index for state access |
| 0x64 | N_DATA | RW | 0x00000000 | V [15:0] signed membrane potential; R [19:16] refractory countdown |

Weight packing: weight k of word w occupies data bits [4k+3:4k], linear
index 16w + k, axon-major — so one event's weight column is a contiguous
burst. In this device `W_DATA_LO`/`W_DATA_HI` read back the *stored* ECC
data field rather than being pure write-only staging, which is what
makes an injected upset visible until it is scrubbed (deviation D4).

#### fault — counters and injection hooks

| Offset | Name | Access | Reset | Bit fields |
|---|---|---|---|---|
| 0x70 | CNT_SEC | RO | 0x00000000 | Corrected single-bit ECC events |
| 0x74 | CNT_DED | RO | 0x00000000 | Uncorrectable double-bit ECC events (E10 substitution applied) |
| 0x78 | CNT_EVQ_OVF | RO | 0x00000000 | Event drops on a full input queue |
| 0x7C | CNT_AXON_OOR | RO | 0x00000000 | Events dropped for axon id >= CFG_AXON |
| 0x80 | FAULT_ADDR | RO | 0x00000000 | Weight word index of the last double-bit detection |
| 0x84 | ECC_INJ | WO | 0x00000000 | b0 SINGLE (SC), flip one bit on the next W_DATA commit; b1 DOUBLE (SC), flip two bits |
| 0x88 | FAULT_CLR | W1C | 0x00000000 | b0 CNT_SEC, b1 CNT_DED, b2 CNT_EVQ_OVF, b3 CNT_AXON_OOR, b4 FAULT_ADDR; bits [31:5] ignored by the architecture block |

**Counter width.** In this device the four counters are 8 bits wide and
**saturate**, not 32 (deviation D1). Reads zero-extend to 32 bits. This
matters for interpretation and for fault analysis — see section 6.4.

**`FAULT_CLR` bit 5** is a pilot-only clear for `CNT_TMR`. The
architecture block ignores it, so a host that writes `0x3F` is portable
across both implementations; that portability is deliberate and is the
reason bit 5 is used rather than a lower one.

#### aer — queue access and mesh addressing

| Offset | Name | Access | Reset | Bit fields |
|---|---|---|---|---|
| 0x90 | EVQ_STAT | RO | 0x00000000 | IN_FILL [7:0], input queue occupancy; OUT_FILL [15:8], output queue occupancy (including the show-ahead held word) |
| 0x94 | EVQ_IN | WO | 0x00000000 | 16-bit event word; drops on full and counts in CNT_EVQ_OVF |
| 0x98 | EVQ_OUT | RO | 0x00000000 | EVENT [15:0], valid when VALID = 1; VALID b31, 0 = queue was empty |
| 0x9C | NODE_ID | RW | 0x00000000 | NID [3:0], mesh node address; a frozen link-word field |

#### Pilot-only observability registers (deviation D5)

These three occupy the unmapped region of the same window and do not
change the architecture register-map contract.

| Offset | Name | Access | Bit fields |
|---|---|---|---|
| 0x0A0 | ECC_INJ_POS | RW | POS [6:0], the codeword bit that ECC_INJ.SINGLE flips. ECC_INJ.DOUBLE flips POS and (POS + 1) mod 72, a valid double error for any Hsiao code. Reset 0, so an ECC_INJ write alone is already deterministic |
| 0x0A4 | TMR_INJ | RW | REP [9:8]: 00 = none, 01 = replica A, 10 = B, 11 = C; BIT [5:0] selects a bit of the voted configuration vector |
| 0x0A8 | CNT_TMR | RO | Saturating count of voter disagreement episodes, one per rising edge of mismatch; cleared by FAULT_CLR bit 5 |

`TMR_INJ` emulates an upset on one replica's **read path**; the storage
flip-flops are not disturbed, so no replica resynchronisation is
exercised by it. That is consistent with the voter's contract, and it is
a different thing from a real upset in a replica bank — see section 6.3.

### 5.4 Configuration validation

Values are checked against these ranges. An out-of-range value with
`CTRL.EN` set, or any configuration write while `STATUS.BUSY` = 1,
latches `STATUS.ERR_CFG` and the core refuses to start.

| Symbol | Register | Range |
|---|---|---|
| THETA | CFG_THRESH | [1, +32767] |
| V_RESET | CFG_VRESET | [-32768, THETA-1] |
| S_LEAK | CFG_LEAK | [0, 15] |
| S_SYN | CFG_SYNSHIFT | [0, 7] |
| T_REFR | CFG_REFR | [0, 15] |
| CFG_AXON | CFG_AXON | [1, N_AXONS] |

`CTRL`, `STATUS_CLR` and `FAULT_CLR` remain writable while BUSY, which
is what makes recovery from a parked core possible.

### 5.5 Documented deviations from the architecture register map

| Id | Deviation | Reason |
|---|---|---|
| D1 | Fault counters are 8 bits and saturate, not 32 | Area, on a device an operator reads out every few seconds |
| D2 | `CFG_NEUR` is read-only and reports the elaborated geometry | The neuron core carries no runtime active-neuron count; implementing one would be RTL with no golden reference. `CFG_AXON` is fully writable and does drive the drop rule |
| D3 | `W_ADDR` is a weight-word index, not a byte address | One 16-weight word per commit; auto-increments on `W_DATA_HI` exactly as the map specifies |
| D4 | `W_DATA_LO`/`W_DATA_HI` read back the *stored* ECC data field | They are the physical data field, so an injected upset is visible until it is scrubbed. That is the demonstrator |
| D5 | Three pilot-only registers at 0x0A0, 0x0A4, 0x0A8 | Observability; unmapped region of the same window |

---

## 6. Fault tolerance

### 6.1 What is protected, and by what

| Structure | Mechanism | Reporting |
|---|---|---|
| Weight word on load and on scrub | (72,64) Hsiao SECDED: single-bit corrected inline, double-bit detected with zero substitution (E10) and processing continues | CNT_SEC, CNT_DED, FAULT_ADDR, STATUS.DED_SEEN, SEC and DED pins |
| Configuration (55 bits) | Triple modular redundancy, majority voted before it leaves the register block | CNT_TMR, TMR pin |
| Neuron-core control FSM | Hamming-distance-2 even-parity state encoding, default-case recovery to S_SAFE, state file frozen | STATUS.ERR_CFG (live and sticky), ERR pin; recovery via CTRL.SOFT_RST |
| Event dispatcher fetch | Bounded wait with timeout | STATUS.ERR_CFG, ERR pin |
| Stored weight codeword | Strobed re-check with repair write-back when CTRL.SCRUB_EN is set | CNT_SEC, SEC pin |
| Input queue overflow | Drop with count | CNT_EVQ_OVF, STATUS.OVF_SEEN, ERR pin |
| Out-of-range axon id | Drop with count | CNT_AXON_OOR |

The device is **fail-operational** on an uncorrectable weight word: a
dead word degrades the network, it does not stop the node. The host
decides whether to reload the slice.

### 6.2 Measured effectiveness

The fault-injection campaign of `docs/16-fault-injection-campaign.md`
flips one bit of one architectural flip-flop at a time in RTL simulation
and judges the result against the golden model. 255 injections, seed
`0x16F12026`, 8 x 8 geometry, 22.23 ms of simulated time. Outcomes are
classified MASKED (no effect), CORRECTED (a mechanism repaired it and
counted it), DETECTED (the device flagged it), SDC (silent data
corruption — wrong output or wrong retained state, nothing flagged) and
HANG.

**Headline, current design [measured]:**

| Outcome | Count | Share |
|---|---:|---:|
| MASKED | 83 | 32.5% |
| CORRECTED | 42 | 16.5% |
| DETECTED | 39 | 15.3% |
| **SDC** | **91** | **35.7%** |
| HANG | 0 | 0% |

**Every hardened structure held, with zero counterexamples [measured]:**

| Structure | Result |
|---|---|
| Neuron-core FSM | 12/12 DETECTED; all twelve parked in S_SAFE and recovered via SOFT_RST |
| Configuration TMR | 15/15 CORRECTED, counted and pinned — but read section 6.3 before quoting this |
| SECDED single-bit | 12/12 CORRECTED, inference bit-exact, CNT_DED = 0 |
| SECDED double-bit | 4/4 DETECTED, never miscorrected; E10 substitution exact on the event stream in all four |
| Scrub loop | 7/7 CORRECTED with the stored word read back byte-identical to the loaded word |

**Every silent corruption came from a structure this device does not
claim to protect.** Per-structure SDC rates [measured]:

| Structure | Flip-flops | SDC rate | n |
|---|---:|---:|---:|
| Refractory counters (`rmem`) | 32 | 100.0% | 12 |
| Membrane potentials (`vmem`) | 128 | 91.7% | 24 |
| AER queue pointers | 12 | 91.7% | 24 |
| Live synapse weights (`wmem`) | 256 | 56.2% | 16 |
| EVQ_OUT adapter / valid flags | 35 | 42.9% | 14 |
| Event dispatcher | 18 | 33.3% | 18 |
| Neuron scan state | 23 | 28.6% | 21 |
| AER queue storage | 128 | 21.9% | 32 |
| Register-bank configuration | 75 | 6.2% | 16 |

One failure class was found by this campaign and fixed: the event
dispatcher could enter its fetch state without an outstanding read and
wait there forever, leaving `STATUS.BUSY` stuck high. Five of 255
injections hit it. A bounded wait with a timeout that raises `ERR_CFG`
costs 7 flip-flops and one comparator; after the fix all five outcomes
become DETECTED and **nothing else moves** — not one MASKED, CORRECTED
or SDC record changes class.

### 6.3 Correction: the configuration TMR did not physically exist until 2026-08-26

**A datasheet that hides a corrected defect is worthless, so this is
stated in full.**

Until 26 August 2026 the three 55-bit configuration replicas were three
`reg` vectors written from the same expression on the same clock edge.
That is correct RTL and it is a defect in silicon. Yosys `opt_dff`
rewrites each bank's hold multiplexer into an enable flip-flop, which
erases the only structural difference between them, and `opt_merge` then
hashes the three now-identical banks into one and rewires the other two
names to it. **The netlist that fed the first 4x2 harden contains 362
references to `cfg_a[` and zero to `cfg_b[` or `cfg_c[` [measured].**
The same collapse appeared in the sky130 run and in the ECP5 fit: 1045
flip-flops in all three, against 1161 declared by the RTL.

In that netlist the voter read one physical register bank three times.
Against a real upset in that bank, the majority vote would have returned
the corrupted value — masking nothing, counting nothing, lighting no
pin.

**The 15/15 CORRECTED result of section 6.2 is not withdrawn, and it is
not sufficient.** At RTL the three replicas *are* three distinct
signals, the campaign deposited into one at a time, and the voter masked
every one: the voting logic is correct and was measured correct. What
RTL fault injection is structurally incapable of seeing is a redundant
structure that synthesis proves equivalent and deletes. No longer run,
no larger sample and no better oracle could have caught this.

**The fix.** Each replica is now its own `pilot_cfg_bank` module
instance carrying `keep_hierarchy`, and each instance stores its value
under a different polarity — A true, B fully complemented, C with odd
bits complemented — so the three instances derive three different module
types that no structural hash can merge, and so that even a flow that
ignores the attribute entirely still cannot fold bit *i* of A into bit
*i* of B. Two mechanisms that were tried and rejected are worth
recording because one of them *looks* like it works: `(* keep *)` leaves
the flip-flop count unchanged at 1045 while filling the netlist with
`assign cfg_b[3] = cfg_a[3];` lines — the attribute lands on the wire,
not the storage — and `(* syn_keep *)` is a vendor attribute Yosys
ignores outright.

**Verified, by this document's author, against the netlist:** the
current LibreLane synthesis output carries **1155 `sg13g2_dfrbpq_1`
flip-flops with 55 under each of `u_cfg_a`, `u_cfg_b` and `u_cfg_c`**
[measured, `tt/runs/tmr-reharden/06-yosys-synthesis/`]. That is the +110
the three banks cost. `sw/tests/test_synthesis_guards.py` — eight tests,
all passing when run for this document — re-derives it on every
invocation from both synthesis flows, counts flip-flop *cells* rather
than grepping for signal names, and additionally compares the whole
design's declared population against the mapped one so that any future
redundant structure is covered the day it is added.

**Honest limit on the fix.** Only two distinct per-bit functions exist
(x and ~x), so under a forced flatten that defeats the attribute,
replica C merges bitwise into A and B and the domain degrades to
duplication-with-detection rather than correction. No encoding can do
better: a third per-bit function would have to mix in a second signal,
which turns a single upset into a multi-bit error and defeats the voter
it is meant to protect.

### 6.4 What is not protected, and the residual risk

**The honest statement.** Roughly a third of single-bit upsets injected
into this device's architectural flip-flops produce a wrong result that
nothing on the chip flags — 91 of 255, 35.7% [measured]. Every one of
them came from a structure the device does not claim to protect, which
is a statement about design honesty and not a mitigation: the protected
structures are a minority of the flip-flops, and the unprotected
majority carries the network's live state. A host that reads only this
device's fault counters and fault pins will, on those occasions, be told
that nothing happened while the spike stream or the neuron state is
wrong. There is no mechanism in this device that closes that gap, and
none is claimed. The specific unprotected structures, in order of how
much of that risk they are expected to carry, are:

1. **Live synapse weights (`wmem`, 256 flip-flops, 56.2% SDC).** The ECC
   protects the 72-bit staging word; once the loader has copied the
   nibbles into the neuron core, nothing checks them again. This is the
   largest structure in the device and therefore the largest expected
   source of silent corruption. **Mitigation, zero silicon cost:** the
   host periodically reloads the whole weight image through the existing
   ECC-checked loader, which repairs `wmem` from a protected source and
   bounds the corruption to the reload interval. This belongs in the
   driver contract.
2. **Neuron state (`vmem` 91.7%, `rmem` 100.0% SDC, 160 flip-flops
   together).** No parity, no ECC, no TMR, and deliberately not even on
   the reset net. A wrong V biases every subsequent event until the
   neuron next spikes or the host issues `STATE_CLR`; a spurious
   refractory count gates that neuron entirely for up to 15 ticks. Only
   two of 24 `vmem` injections were genuinely masked, both by the same
   mechanism — the shift-based leak quantises neighbouring potentials
   into the same result, so a one-LSB error can be erased by a tick —
   and that does not reach past the low bits. **Mitigation, host
   policy:** issue `STATE_CLR` at frame boundaries to bound the
   persistence. For a demonstrator whose job is to make upsets visible,
   a host-readable unprotected state file is an instrument rather than a
   defect, and the `N_ADDR`/`N_DATA` port turns every one of these into
   a measurement.
3. **AER queue pointers (12 flip-flops, 91.7% SDC).** The highest
   per-bit rate in the device, and the corruption is the kind no
   consumer can detect: whole bursts re-emitted, events duplicated,
   events lost, events fabricated out of never-written queue slots. An
   event interface has no sequence numbers and no length field, so a
   fabricated spike is indistinguishable from a real one downstream.
   This is the best protection-per-flip-flop available in the design and
   is the first item on the next hardening wave; it is not in this
   device.
4. **Telemetry (counters and stickies, 48 flip-flops).** For a device
   whose stated purpose is to *measure* upset response, the counters are
   the product, and they are unprotected in both directions. 13 of 18
   injections into them produced a flag or a counter movement while the
   output was perfectly correct — a false alarm. And because the
   counters saturate at 8 bits rather than counting to 32, one flip of
   `CNT_SEC` bit 7 turns a count of 0 into 128. Worse, records can be
   *erased*: an upset in `CNT_SEC` bit 0 took a real count of 1 back to
   0 while the SEC pin stayed lit, and an upset in the sticky cleared the
   pin while the counter still read 1. **Mitigation, host policy,
   available today at zero cost:** treat any disagreement between a
   counter reading nonzero and its sticky bit as a detected fault. Both
   corruption directions are visible as exactly that disagreement.
5. **Latent register corruption.** Fifteen injections left an
   architectural register wrong after a run the device otherwise handled
   cleanly — `W_ADDR`, `SCRATCH`, `NODE_ID`, `CFG_AXON`, `CTRL.EN`,
   `CTRL.SCRUB_EN` and the two injection registers. Eight of the fifteen
   were masked for that run and would be inherited whole by the next
   host command sequence; a weight load that starts from a corrupted
   `W_ADDR` writes the whole image to the wrong offset. **Mitigation,
   host policy:** the driver must rewrite `W_ADDR` and `CTRL` before
   every use rather than trusting a previously set value.
6. **One telemetry gap with no host-side fix.** An upset in the output
   queue pointers can raise `STATUS.OVF_SEEN` with `CNT_EVQ_OVF` still
   reading zero, because only the input queue's drop counter is exposed.
   The operator is told an overflow happened and given no count for it.
   That is defensible as designed — the output queue cannot drop under
   normal operation — but an upset breaks that invariant and the
   telemetry has no room for the result.

One further property, measured, that is easy to miss: **E10 keeps the
values right, it does not keep the rate right.** Zeroing a weight word
that feeds stimulated axons pushed enough neurons over threshold that
the run emitted more spikes than the output path could hold and raised
`STATUS.OVF_SEEN`. A fail-operational substitution that changes the
spike rate can still saturate the path downstream of it.

### 6.5 Bounds on the evidence in section 6.2

These bound what the numbers mean and should be read before any of them
is quoted:

- **Sample sizes are small**: one to five injections per bit position, 4
  to 32 per group.
- **One workload**, one geometry sampled with a second as a check.
- **The campaign represents 85% of the design's flip-flops.** The serial
  shift engine, the input synchronisers, the SYNC echo path, the ECC
  loader state and a handful of single flops are not injected into.
- **The fault model is single-bit, flip-flop-only, at RTL, with zero
  delay.** No multi-bit upsets, no single-event transients in
  combinational logic — so the SECDED decoder, the TMR voter and the
  read multiplexers are outside the model entirely — no stuck-at faults,
  no latch-up, no gate-level or timing-aware injection.
- **Nothing here is a rate.** These are conditional probabilities given
  that an upset lands somewhere. Deriving an upset rate, a cross-section
  or a total-dose figure from them is not possible and is not
  attempted.
- **Every DETECTED outcome assumes someone is looking.** The device has
  no watchdog and no interrupt. A host that never polls `STATUS` and
  never watches the fault pins sees a detected fault and a silent one
  identically: nothing.
- **Counting a corrupted retained neuron state as SDC is a choice.** A
  campaign that compared only the spike stream would report `vmem` at
  29% and `rmem` at 25% instead of 91.7% and 100%. This datasheet takes
  the stricter view because the state is architecturally visible through
  `N_ADDR`/`N_DATA` and is the neuron's memory.

---

## 7. Electrical and physical characteristics

### 7.1 What is known

| Parameter | Value | Tag | Source |
|---|---|---|---|
| Technology | IHP SG13G2, 130 nm bulk CMOS | [measured] | flow configuration |
| Tile shape | Tiny Tapeout 4x2, 8 tiles | [measured] | `tt/` submission tree |
| Die area | 268,059 um2 | [measured] | `54-openroad-rcx` and the shuttle DEF template, agreeing to rounding |
| Core / placement-row area | 259,837 um2 | [measured] | same |
| Pin count | 8 in, 8 out, 8 bidirectional, plus clk, rst_n, ena | [measured] | wrapper port list |
| Mapped flip-flops | 1155 `sg13g2_dfrbpq_1` | [measured, in flux] | `tt/runs/tmr-reharden/06-yosys-synthesis/` |
| of which configuration TMR | 55 in each of three banks | [measured] | same |
| Serial clock ceiling | `clk`/4 | [measured] | RTL contract, held at the boundary by the test suite |
| Clock target | 50 MHz (20 ns) | [target] | `ROADMAP.md`; the harden runs at this constraint |

**FPGA fit, as an independent implementation check — not an ASIC
timing statement.** The same RTL, unchanged, synthesises, places, routes
and packs on an open-source Lattice ECP5 toolchain with zero source
changes, zero block RAM and zero DSP. On a speed-grade-6 ECP5 85F the
design reached **47.87 MHz before the TMR fix and 46.45 MHz after it**
[measured, seed 0], passing a 25 MHz constraint with roughly 1.9x margin
on all three ULX3S device options and missing 50 MHz. The critical path
lives in the neuron core's register-file read multiplexer trees, which
exist only because the arrays did not map to block RAM; the pre-fix
netlist reached 60.05 MHz on a speed-grade-8 part, which the ULX3S board
class does not carry. **This says nothing about ASIC
timing, area, power or radiation behaviour**, and it must not be quoted
as if it did — an ECP5 is itself an SRAM-configured FPGA whose own
configuration memory upsets.

**Post-route static timing.** The re-harden in progress closes all three
IHP PVT corners at the 20 ns constraint with **zero setup, hold,
max-capacitance and max-slew violations**, worst setup slack +6.4359 ns
on the slow corner and worst hold slack +0.1192 ns on the fast corner
[measured, in flux, `tt/runs/tmr-reharden/55-openroad-stapostpnr/`].
The design's sign-off before the TMR fix was equivalent in character:
all three corners clean, worst setup slack +5.3141 ns, zero DRC, zero
LVS and zero antenna violations.

**Verification status, run for this document [measured]:**

- `sw/tests/`: 152 passed, 1 skipped — including the eight synthesis
  guards and the mechanical cross-check that `regmap/regmap.yaml` and
  the normative register list do not diverge in name, offset, access or
  reset.
- `hw/tb/Makefile.pilot`: 23 cocotb tests, zero failures, driving the
  Tiny Tapeout top level.

### 7.2 Figures that are in flux

The configuration-TMR fix changed flip-flop counts and areas, and the
4x2 harden is being regenerated as this is written. Do not quote the
following against a fixed value; they will move.

| Quantity | Before the fix | Current run | Note |
|---|---|---|---|
| Mapped flip-flops | 1045 | **1155** | +110, the three banks; the direction is settled, the exact total will not move again for this content |
| Post-synthesis cell area | 107,782 um2 | **126,647 um2** | different hierarchy mode as well as the extra logic |
| Placed standard-cell area | 136,107 um2 | **158,268 um2** | |
| Utilization of the 4x2 block | 52.38% | **60.9%** | still well inside the tile |
| Worst slow-corner setup slack | +5.3141 ns | **+6.4359 ns** | |
| Total power at 50 MHz, typical | 4.36 mW | not yet re-measured | the pre-fix figure is real but describes a design with one configuration bank instead of three |

The re-harden had not completed physical verification when this revision
was written: post-route STA is clean, and DRC, LVS and antenna results
for the current netlist are **pending**. The pre-fix run's results for
those checks were all zero.

The synthesis flow for this design now requires
`SYNTH_HIERARCHY_MODE: "deferred_flatten"`, which flattens *after* the
configuration banks have become standard cells. Without it the parameterised
bank module types would be counted as unmapped instances and the harden
would abort. Any other flow configuration hardening this module needs
the same key.

### 7.3 TBD

None of the following is known for this device, and no estimate is
offered:

- **Supply voltage, current and total power on silicon.** [TBD] The
  4.36 mW figure above is a flow-computed power estimate at the typical
  corner, from the post-route parasitic-extracted netlist of the
  *superseded* pre-fix design. It is not a silicon measurement, it does
  not describe the current netlist, and it says nothing about power
  under a realistic event workload — the flow's activity assumptions are
  not this device's.
- **Timing at silicon**: achieved Fmax, setup and hold at the real
  process corners, and the temperature range over which they hold.
  [TBD]
- **I/O electrical characteristics**: levels, drive strength, input
  thresholds, capacitance. These belong to the Tiny Tapeout carrier's
  pad ring, not to this design. [TBD]
- **Total ionising dose tolerance.** [TBD] The design target is
  LEO-class, 10-30 krad(Si); no total-dose test has been performed.
- **Single-event upset cross-section, LET threshold, single-event
  latch-up behaviour, single-event functional interrupt rate.** [TBD]
  All require beam data this project does not have. Bulk 130 nm has no
  intrinsic latch-up immunity.
- **Package thermal characteristics, operating temperature range,
  lifetime and reliability figures.** [TBD]
- **Gate-level fault-injection results.** Not run. The campaign of
  section 6.2 is at RTL; the one defect that only a netlist could reveal
  is the subject of section 6.3.

---

## 8. Bring-up

The order below is the order in which a fault in one step invalidates
everything after it, so it should be followed as written.

**Step 0 — before the chip.** Confirm the host's serial timing meets
H1, H2 and H3 (section 5.2) on a scope, against a dummy load, before
connecting the device. Two of the three obligations have already caused
real bring-up failures on this design and on a sibling one, and both
present as *plausible but wrong* register data rather than as an obvious
failure.

**Step 1 — power and clock.** Apply power, apply a clock at or below
25 MHz to start (the FPGA fit proves that point on hardware-realistic
parts; 50 MHz is a target the silicon has not yet been asked about), and
hold `rst_n` low, then release it. Tie `ui_in[7]` low.

**Step 2 — prove the serial link before believing anything else.**
Read `ID` at 0x00. It must read `0x4E505531`. If it does not, stop: no
other reading from the device means anything. Then read `VERSION` at
0x04 (`0x00000001`), and write-then-read `SCRATCH` at 0x08 with a
walking-ones pattern. `SCRATCH` has no side effects and is there for
exactly this.

**Step 3 — read the reset state.** Read `STATUS` at 0x10; it should
read `0x00000006` (both queues empty, not busy, nothing sticky set).
Read `CTRL` at 0x0C; it should read `0x00000008` (`SCRUB_EN` set,
core disabled). Read `CFG_NEUR` and `CFG_AXON`; both report the
elaborated geometry. Confirm the four fault pins are low.

**Step 4 — clear the neuron state.** Neuron state after reset is
undefined and is *not* cleared by the reset net. Write `CTRL.STATE_CLR`,
poll `STATUS.BUSY` until it falls, then read a few neurons through
`N_ADDR`/`N_DATA` and confirm they read zero. Do not skip the readback:
this is the first step whose failure would otherwise be invisible until
the first inference disagrees with the model.

**Step 5 — load weights, and check the ECC path on the way.** For each
weight word: write `W_ADDR`, write `W_DATA_LO`, then write `W_DATA_HI`,
which commits the word, generates the check field and auto-increments
`W_ADDR`. Read `CNT_SEC` and `CNT_DED` afterwards; both must be zero on
a clean load. Read `W_DATA_LO`/`W_DATA_HI` back and compare — in this
device they return the stored ECC data field, so the comparison is a
real check of the storage.

**Step 6 — configure and validate.** Write `CFG_THRESH`, `CFG_VRESET`,
`CFG_LEAK`, `CFG_SYNSHIFT`, `CFG_REFR`, `CFG_FLAGS`, `CFG_AXON` and
`PASS_TILE_OFF`. Then read `STATUS` and confirm `ERR_CFG` is clear. A
set `ERR_CFG` here means a value was out of range or was written while
BUSY; fix it and clear it through `STATUS_CLR` before proceeding.
Because configuration passes through the TMR domain, this write is also
what repairs all three replicas — it is the resynchronisation the
hardware does not do by itself.

**Step 7 — first inference.** Set `CTRL.EN`. Inject events through the
`EVQ_IN` register (or the `AER_IN_STB` pin), finish the frame with a
SYNC event, poll `STATUS.SYNC_DONE`, then drain `EVQ_OUT` until `VALID`
reads zero. Compare the drained stream against `sw/golden/lif_core.py`
run on the same weights, configuration and events. It should match
bit-for-bit; if it does not, the fault is in the host driver or in step
4 or 5, not in the neuron model.

**Step 8 — exercise the hardening demonstrators, one at a time.** These
are the reason the device exists.

1. *SECDED single-bit.* Write `ECC_INJ_POS` to a codeword bit, write
   `ECC_INJ` bit 0, commit a weight word. Expect `CNT_SEC` = 1, the SEC
   pin lit, `CNT_DED` = 0, and an inference identical to the clean run.
   Walk `ECC_INJ_POS` across all 72 positions; the full syndrome space is
   reachable.
2. *SECDED double-bit.* Same with `ECC_INJ` bit 1. Expect `CNT_DED` = 1,
   the DED pin, `STATUS.DED_SEEN`, `FAULT_ADDR` holding the word index,
   `CNT_SEC` = 0, and an inference that matches a model built with that
   one weight word zeroed — degraded, not garbage.
3. *Scrub.* With the single-bit error still in the stored word and
   `CTRL.SCRUB_EN` set, pulse `SCRUB_STB` and read the word back; it
   should be repaired. With `SCRUB_EN` clear, the error persists and can
   be re-checked as often as wanted.
4. *Configuration TMR.* Write `TMR_INJ` to hold one bit of one replica's
   read path wrong, run the same inference, and require an identical
   spike stream with `CNT_TMR` incremented and the TMR pin lit. Note the
   limit of this hook: it injects on the read path, not into the storage
   flip-flop, so it does not exercise the physical replica banks
   (section 6.3). Clear it by rewriting the configuration.
5. *FSM park and recovery.* This one cannot be commanded — it is what a
   real upset in the neuron core's state register looks like. If ERR
   lights and `STATUS.BUSY` will not fall, `CTRL.SOFT_RST` is the
   recovery; the neuron state file survives it, and the sticky `ERR_CFG`
   survives it too, so the evidence is not erased.

**Step 9 — establish the telemetry cross-check before any long run.**
Write the host-side rule from section 6.4 into the bench script: a
counter reading nonzero while its sticky bit is clear, or a sticky bit
set while its counter reads zero, is a *detected fault of the telemetry
itself*. Also confirm `FAULT_CLR` = `0x3F` clears everything including
`CNT_TMR`.

**Step 10 — driver hygiene, permanently.** Rewrite `W_ADDR` and `CTRL`
before every use rather than trusting a previously set value; reload the
weight image periodically through the ECC-checked loader; issue
`STATE_CLR` at frame boundaries when bounded state persistence matters.
These three cost nothing and each of them removes a measured failure
mode that no silicon in this device removes.

---

## 9. Reproducing the measurements in this document

```
# Golden model, register-map cross-check, synthesis guards, submission guards
.venv/bin/python -m pytest sw/tests/ -q

# Pilot device simulation, driving the Tiny Tapeout top level
cd hw/tb && make -f Makefile.pilot

# Fault-injection campaign of record
cd hw/tb && make -f Makefile.fi

# Formal proofs
make -C formal everything

# ECP5 fit and Fmax
cd hw/fpga && make fit
```

Flip-flop and area figures come from the run trees under `tt/runs/`;
the per-replica flip-flop counts are re-derived on every `pytest`
invocation by `sw/tests/test_synthesis_guards.py` rather than being read
out of a stored report.

## 10. Disagreements between repository documents found while writing this

Recorded, not corrected — these files are owned elsewhere.

1. **`docs/15-pilot-tile-plan.md` section 4.2** states that "the TMR
   replicas survive synthesis, and this was measured rather than
   assumed", quoting 1,036 and 1,037 flip-flops from two flows. That
   conclusion is contradicted by `hw/rtl/pilot_top.v` header section 9,
   by the correction in `docs/16` section 4, by
   `sw/tests/test_synthesis_guards.py` and by the netlist itself. The
   measurement it rests on is a whole-design flip-flop *total*, which
   cannot distinguish a merged bank from an unmerged one without a
   declared-count baseline to compare against.
2. **`docs/15` section 4.2** also states that the submission does not
   carry `SYNTH_HIERARCHY_MODE: deferred_flatten` and that "this project
   has no `keep_hierarchy` attribute anywhere in `hw/rtl`". Both are now
   false: `tt/src/config.json` and `scripts/gen_tt_submission.py` set the
   key, and `pilot_cfg_bank` carries the attribute.
3. **`hw/fpga/README.md`** still presents the TMR collapse as an open
   finding ("this directory does not fix that") and quotes 1045
   `TRELLIS_FF`, 3449 `TRELLIS_COMB` and 47.87 MHz as current figures.
   The fix has landed; the post-fix ECP5 figures are 1155, 4503 and
   46.45 MHz.
4. **Pre-fix flip-flop count is quoted as two different numbers.**
   `docs/15` says 1,036 / 1,037; `docs/16` and `hw/rtl/pilot_top.v` say
   1045. The difference is tool version and flow configuration, but the
   repository would benefit from one reconciled statement.
5. **Declared flip-flop count is quoted as two different numbers.**
   `docs/16` section 2 says the post-fix design holds 1167 by an RTL
   hand count; `sw/tests/test_synthesis_guards.py` and
   `hw/rtl/pilot_top.v` say the RTL declares 1161 as counted by Yosys
   after `proc`. The two use different bases and neither is wrong, but
   they are not distinguished where they are quoted.
6. **`docs/15` section 5.1** says 22 cocotb tests in the pilot suite;
   the suite run for this document reports 23.

## 11. References

| Document | What it holds |
|---|---|
| `regmap/regmap.yaml` | The register map, single source of truth |
| `docs/10-npu-mvp-spec.md` | The normative neuron model and equations E1-E10 |
| `docs/15-pilot-tile-plan.md` | Die content, pin contract, tile budget, submission tree |
| `docs/16-fault-injection-campaign.md` | The fault-injection campaign and its bounds |
| `docs/12-sg13g2-flow-bringup.md` | IHP SG13G2 flow bring-up and the SRAM macro evaluation |
| `docs/18-cross-pdk-portability.md` | The same design hardened on a second PDK |
| `docs/05-market-positioning.md` section 4 | The binding positioning rules restated in section 1.2 |
| `docs/08-gr801-datasheet-notes.md` | The GRLIB conventions this register map deliberately mirrors |
| `docs/00-reference-brief.md` | The GR801 public product brief this project shadows |
| `hw/rtl/` | Behaviour, single source of truth |
| `sw/golden/` | The bit-exact executable specification |
