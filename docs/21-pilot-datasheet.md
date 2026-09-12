# Neuromorphic Space SoC — pilot device datasheet

Device: the ROADMAP phase P1 pilot, hardened and submitted as
`tt_um_melihakbulut_nssoc` on the Tiny Tapeout TTIHP26b shuttle
(IHP SG13G2, 130 nm bulk CMOS).

Revision: 0.1, 26 August 2026. Status: **pre-silicon**. The design is
frozen for content and is being re-hardened after the configuration-TMR
fix of 2026-08-26; silicon is expected 2027-06-25 with boards around
2027-08 (`ROADMAP.md` section 1).

*Updated 2026-08-30.* The re-hardening is **complete**, and the tile
shape changed while it ran: the submission is **Tiny Tapeout 6x2 =
12 tiles**, not 4x2 = 8. Content is unchanged — the same 8 x 8 geometry,
the same protections, the same pin contract — and what moved is the
number of tiles the hardened design needs. Sections 7.1 and 7.2 carry
the replacement figures and `docs/23-tile-shape-decision.md` is the
decision record. The **[in flux]** tag of section 0 no longer applies to
any figure in this document.

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
codes on the weight storage, configuration registers triplicated and
voted in the netlist *(section 6.6)*
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
| Configuration protection | 55 bits, triple modular redundancy, majority voted **in the netlist** | [measured] *See section 6.6, added 2026-09-09.* |
| Host interface | Mode-0 SPI slave, 40-bit frames | [measured] |
| Total flip-flops, mapped netlist | 1155 | [measured, in flux] |
| Clock target | 50 MHz | [target] |
| Power | see section 7.3 | [TBD] |
| Radiation performance | see section 7.3 | [TBD] |

*Superseded 2026-08-30 — four rows.* **Tile shape: Tiny Tapeout 6x2,
12 tiles. Die area 404,499 um2, core 392,988 um2. Total mapped
flip-flops 1275, tag [measured] rather than [measured, in flux].**
**[fact, `docs/23` sections 1.4 and 2.1, and `docs/22` section 9.5.]**
Section 7.1 carries the full replacement set and section 7.2 says what
moved the shape. Every other row of this table is unaffected: the
geometry, the protection schemes and the host interface are the same
design at a larger tile count.

*Note added 2026-08-30.* The **Clock target** row is a [target] and
stays one; it is not a claim that the design closes at 50 MHz. What the
post-route sign-off does and does not establish about that target moved
on this date — see section 7.1's correction note, which withdraws the
4x2 closure claim and re-derives the submitted 6x2 shape at
**+0.2913 ns and 50.7 MHz** with the 5 % OCV derate applied.

The 8 x 8 geometry is an elaboration parameter, not an architectural
limit. `hw/rtl/pilot_top.v` accepts N_NEURONS and N_AXONS as powers of
two in [4, 16]; the architecture the pilot instantiates a slice of is
specified at 512 x 512 (`docs/10-npu-mvp-spec.md` section 2). The pilot
is the geometry that fits eight Tiny Tapeout tiles. *Superseded
2026-08-30: it is the geometry that needs **twelve**.* Two rounds of
hardening — the `lif_core` memory ECC and the AER pointer TMR — grew it
past the 70 % planning criterion at eight **[fact, `docs/22`
section 9.4]**.

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
   |   regmap/regmap.yaml subset + 5 pilot-only registers             |
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
listed in section 5.3 plus five pilot-only observability registers, all
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
a matching test, or if the matching test has been gutted of its
assertions -- a name alone does not count as coverage
(`docs/11` section 7, corrected 2026-09-11).

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

**`FAULT_CLR` bits 5, 6 and 7** are pilot-only clears: bit 5 for
`CNT_TMR`, bit 6 for `CNT_EVQ_OUT_OVF`, bit 7 for `CNT_EVQ_PAR`. The
architecture block ignores every bit above 4, so a host that writes
**`0xFF`** clears everything in either implementation; that portability
is deliberate and is the reason the pilot allocates upward from bit 5
rather than reusing a lower one.

> **CORRECTED 2026-09-09.** Until this date the paragraph above read
> "**`FAULT_CLR` bit 5** is a pilot-only clear for `CNT_TMR` … a host
> that writes **`0x3F`** is portable across both implementations". That
> was true when it was written and only bit 5 existed. It has been
> wrong since `CNT_EVQ_OUT_OVF` took bit 6 (2026-08-29) and
> `CNT_EVQ_PAR` took bit 7 (`docs/30`): `hw/rtl/pilot_top.v` line 255,
> the frozen die, says "the portable clear-everything write is now
> `0xFF`". The superseded `0x3F` is left visible here rather than
> deleted. A host that still writes `0x3F` clears `CNT_SEC`, `CNT_DED`,
> `CNT_EVQ_OVF`, `CNT_AXON_OOR`, `FAULT_ADDR` and `CNT_TMR`, and leaves
> `CNT_EVQ_OUT_OVF` and `CNT_EVQ_PAR` standing — which on this device
> is silently reading a stale event-loss count, not a harmless
> omission. `regmap/regmap.yaml` carried the same stale `0x3F` into the
> generated `docs/regmap-npu.md` and was corrected on the same date.
> **`tt/docs/info.md` still says `0x3F` and still lists only three
> pilot-only registers**; `tt/` is frozen for the shuttle and is not
> corrected here. `sw/tests/test_tt_submission.py`
> `test_pilot_only_registers_and_fault_clr_bits_are_documented` pins
> that gap so it cannot grow, and section 10 records it.

#### aer — queue access and mesh addressing

| Offset | Name | Access | Reset | Bit fields |
|---|---|---|---|---|
| 0x90 | EVQ_STAT | RO | 0x00000000 | IN_FILL [7:0], input queue occupancy; OUT_FILL [15:8], output queue occupancy (including the show-ahead held word) |
| 0x94 | EVQ_IN | WO | 0x00000000 | 16-bit event word; drops on full and counts in CNT_EVQ_OVF |
| 0x98 | EVQ_OUT | RO | 0x00000000 | EVENT [15:0], valid when VALID = 1; VALID b31, 0 = queue was empty |
| 0x9C | NODE_ID | RW | 0x00000000 | NID [3:0], mesh node address; a frozen link-word field |

#### Pilot-only observability registers (deviation D5)

These five occupy the unmapped region of the same window and do not
change the architecture register-map contract. The list is the decode in
`hw/rtl/pilot_top.v` (the `SA_*` localparams around line 1181, copied
byte for byte into `tt/src/pilot_top.v`), not a hand-kept list.

| Offset | Name | Access | Bit fields |
|---|---|---|---|
| 0x0A0 | ECC_INJ_POS | RW | POS [6:0], the codeword bit that ECC_INJ.SINGLE flips. ECC_INJ.DOUBLE flips POS and (POS + 1) mod 72, a valid double error for any Hsiao code. Reset 0, so an ECC_INJ write alone is already deterministic |
| 0x0A4 | TMR_INJ | RW | REP [9:8]: 00 = none, 01 = replica A, 10 = B, 11 = C; BIT [5:0] selects a bit of the voted configuration vector |
| 0x0A8 | CNT_TMR | RO | Saturating count of voter disagreement episodes, one per rising edge of mismatch; cleared by FAULT_CLR bit 5 |
| 0x0AC | CNT_EVQ_OUT_OVF | RO | Saturating count of OUTPUT-queue writes that were refused and lost; cleared by FAULT_CLR bit 6. It is not `aer_fifo`'s own drop counter and it is not `CNT_EVQ_OVF` (0x78), which counts the INPUT queue — `hw/rtl/pilot_top.v` section 5.1 is why both exist. Added 2026-08-29 after the fault-injection campaign found an overflow raising `STATUS.OVF_SEEN` with no count behind it |
| 0x0B0 | CNT_EVQ_PAR | RO | Saturating count of queue entries DISCARDED because the stored word failed its entry parity check, both queue instances in one count; cleared by FAULT_CLR bit 7. `hw/rtl/pilot_top.v` section 5.2 and `docs/30` are why it is one counter and not two |

> **ADDED 2026-09-09.** The last two rows are new to this datasheet, not
> new to the device: `0x0AC` and `0x0B0` have been in the decode of the
> frozen die since 2026-08-29 and `docs/30` respectively, and this table
> said "These three" until today. Nothing checked it. The gap was found
> by review of `sw/tests/test_tt_submission.py`, whose skip comment
> claimed these registers were "checked by its own table" when no such
> check existed anywhere in the tree — a green result read wider than
> what it looked at, which is the failure mode this corpus names in
> `docs/64`, occurring live at HEAD. The check now exists and is named
> above the table.

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
| D5 | Five pilot-only registers at 0x0A0, 0x0A4, 0x0A8, 0x0AC, 0x0B0 | Observability; unmapped region of the same window. **Corrected 2026-09-09**: this row said "Three ... at 0x0A0, 0x0A4, 0x0A8" and had done since before `CNT_EVQ_OUT_OVF` (0x0AC, 2026-08-29) and `CNT_EVQ_PAR` (0x0B0, `docs/30`) entered the decode. Section 5.3 carries the full table |

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
and judges the result against the golden model. Outcomes are classified
MASKED (no effect), CORRECTED (a mechanism repaired it and counted it),
DETECTED (the device flagged it), SDC (silent data corruption — wrong
output or wrong retained state, nothing flagged) and HANG.

**Corrected 2026-08-29.** Revision 0.1 of this section printed a
255-injection distribution — 91 SDC, 35.7% — under the heading
"Headline, **current design**". That label was wrong by the time it was
read: the 255-injection run predates the `lif_core` memory hardening of
2026-08-27 and the AER pointer TMR of 2026-08-29, so it described a
design this datasheet no longer describes. It was the most quotable
stale figure in the repository. The superseded table is retained at the
end of this section rather than deleted, because a datasheet that
silently improves its own numbers is not auditable.

**Corrected 2026-09-05.** The "campaign of record" below is the
335-injection run read at `0448282`, which was the committed log on
2026-08-29 when this section was corrected the first time. The committed
log moved three times after that and this datasheet was not edited:
`2c6c052` (366 injections, 18 SDC; `docs/16` section 5.11), `634ca3e`
(374, 11 SDC; `docs/29-queue-storage-protection.md`) and `bc91c71`, then
the freeze commit `b6738e5` (**378 injections, 6 SDC**;
`docs/30-dispatcher-protection.md` section 5 and
`docs/33-rail-transform.md` section 7). The file this datasheet ships
with, `hw/tb/fi_campaign_results.json` at blob `312d3c76`, reports
**378 injections: 97 MASKED (25.7 %), 193 CORRECTED (51.1 %), 82
DETECTED (21.7 %), 6 SDC (1.6 %), 0 HANG**, 445.7 s of wall time
**[fact, read out of the file at HEAD; `git log -p` on the file for the
sequence]**. **That is the campaign of record for the frozen die**, and
`docs/60-soc-datasheet.md` section 9 already quotes it. The 335-injection
table below is retained by the same rule that retained the 255-injection
one — it was true of the design at `0448282` — and this section's own
warning applies one more time: **do not pair 7.8 % with 1.6 %**, because
the 378-injection design carries dual-rail valid flags, queue-entry
parity and dispatcher detection that the 335-injection design did not,
and the injections into them are new targets. Retired injections and
record-by-record diffs are in `docs/16` section 5.9 onward, `docs/29`
and `docs/30`. `docs/64-document-reconciliation.md` section 3.1 has the
trace.

**Headline, ~~campaign of record~~ campaign at `0448282` [measured] —
superseded, see above.** Read out of
`hw/tb/fi_campaign_results.json` at commit `0448282`: **335 injections**,
seed `0x16f12026`, 8 x 8 geometry, 891.6 s of wall time. Simulated time
28.77 ms, per `docs/16` section 3.4.

| Outcome | Count | Share |
|---|---:|---:|
| MASKED | 79 | 23.6% |
| CORRECTED | 193 | 57.6% |
| DETECTED | 37 | 11.0% |
| **SDC** | **26** | **7.8%** |
| HANG | 0 | 0% |

**Do not pair 7.8% with 35.7%.** They are not the same experiment and
the difference between them is not all design improvement. The
335-injection run injects into 80 flip-flops of memory check field and
24 flip-flops of pointer replica that did not exist in the 255-injection
design; those 80 added injections are corrections and maskings in
hardware the earlier run had no way to sample, so putting one over the
other divides by a denominator the earlier run did not have. That is
arithmetic, not a result. `docs/16` states the rule and gives the two
defensible comparisons, both of which are like-for-like:

- **Memory hardening:** 91/255 = 35.7% SDC → 48/255 = 18.8% SDC, the
  identical 255 injections before and after (`docs/16` section 3.2).
- **Pointer TMR:** per structure — the AER pointers went from **22 SDC
  of 24** to **0 SDC of 72** (`docs/16` section 5.2); and across the 263
  targets the post-hardening and post-wave-5 runs share, SDC is **26 of
  263 in both** (`docs/16` section 3.4). Wave 5 removed one structure
  from the SDC list and moved nothing else, which is what a change
  confined to the pointers should do.

  *One caution on the "22", noted 2026-08-29 and not resolved here.*
  `docs/16` states this figure two ways: **22** SDC and 1 HANG of 24 in
  its section 3.4 headline and in section 5.2, and **23** SDC and 1 HANG
  of 24 in the retired-targets row of section 3.4 and in section 5.1.
  The two cannot both be right — 23 + 1 would leave nothing else in a
  group of 24, and the pre-hardening rate this datasheet is superseding
  is 91.7% of 24, which is exactly 22. This document therefore uses 22
  and flags the disagreement rather than quietly picking a side;
  `docs/16` owns the campaign and is where it should be settled.

**Every hardened structure held, with zero counterexamples [measured,
from the `groups` object of the campaign log]:**

| Structure | Group(s) | Result |
|---|---|---|
| Neuron-core FSM | `lif_fsm` | 12/12 DETECTED |
| Configuration TMR | `cfg_tmr_a/b/c` | 15/15 CORRECTED, counted and pinned — read section 6.3 before quoting this |
| AER pointer TMR | `evq_ptr` | 72/72 CORRECTED, 0 SDC, 0 HANG — read `docs/16` section 3.3 before quoting this |
| SECDED single-bit | `ecc_port_single` | 12/12 CORRECTED |
| SECDED double-bit | `ecc_port_double` | 4/4 DETECTED, never miscorrected |
| Scrub / ECC storage loop | `ecc_ff` | 7/7 CORRECTED |
| Membrane potentials, hardened | `lif_vmem` | 24/24 CORRECTED |
| Refractory counters, hardened | `lif_rmem` | 12/12 CORRECTED |
| Synapse weights, hardened | `lif_wmem` | 13 CORRECTED + 3 MASKED of 16, 0 SDC |
| Neuron-state and synapse check fields | `lif_smem`, `lif_wchk` | 18/18 and 12/12 CORRECTED |

**Every silent corruption still comes from a structure this device does
not claim to protect**, and there are now five such structures rather
than nine. Per-structure SDC, current campaign [measured; flip-flop
counts are the RTL declaration counts of `docs/16` section 2]:

| Structure | Group | Flip-flops | SDC | n | SDC rate |
|---|---|---:|---:|---:|---:|
| EVQ_OUT show-ahead adapter / read port | `evq_hold` | 35 | 6 | 14 | 42.9% |
| Event dispatcher | `dispatch` | 18 | 6 | 18 | 33.3% |
| Neuron scan and emission state | `lif_scan` | 23 | 6 | 21 | 28.6% |
| AER queue storage | `evq_mem` | 128 | 7 | 32 | 21.9% |
| Register-bank configuration | `regbank_cfg` | 75 | 1 | 16 | 6.2% |
| every other group | — | — | **0** | 234 | 0.0% |

Cross-cutting, same log [measured]: **20 of the 37 DETECTED outcomes
also had a corrupted output**; **3 of the 26 SDC outcomes corrupted only
the retained neuron state**, all three the mis-steered scan index;
**15 latent register corruptions**; **185 telemetry mismatches**, which
rise when the device reports *more*, not less — 72 of them are the
pointer injections correctly incrementing `CNT_TMR`.

Two failure classes were found by this campaign and fixed. The event
dispatcher could enter its fetch state without an outstanding read and
wait there forever, leaving `STATUS.BUSY` stuck high; five of 255
injections hit it, and a bounded wait with a timeout that raises
`ERR_CFG` costs 7 flip-flops and one comparator. The same shape recurred
in the show-ahead adapter's `oh_req` and took the same fix; it is the
**one** record out of 263 common targets that changed class between the
post-hardening and post-wave-5 runs, HANG to DETECTED. In both cases
nothing else moved — not one MASKED, CORRECTED or SDC record changed
class.

**Superseded table, retained [measured on 2026-08-26, describing a
design that no longer exists].** 255 injections, before the memory
hardening and the pointer TMR:

| Outcome | Count | Share |
|---|---:|---:|
| MASKED | 83 | 32.5% |
| CORRECTED | 42 | 16.5% |
| DETECTED | 39 | 15.3% |
| **SDC** | **91** | **35.7%** |
| HANG | 0 | 0% |

Its per-structure SDC rates, superseded by the table above, were:
`rmem` 100.0% of 12, `vmem` 91.7% of 24, AER queue pointers 91.7% of 24,
`wmem` 56.2% of 16, EVQ_OUT adapter 42.9% of 14, dispatcher 33.3% of 18,
neuron scan 28.6% of 21, AER queue storage 21.9% of 32, register-bank
configuration 6.2% of 16. The first four are the structures that were
hardened; the last five are unchanged and are the current table.

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

**The same failure mode, caught before tape-out rather than after
(added 2026-08-30).** A second replicated domain has since been added —
the four AER queue pointers, each held in three `aer_ptr_bank` replicas
behind a bitwise majority vote (`hw/rtl/aer_fifo.v`) — and the hazard
there was **sharper** than in the configuration domain, not milder: all
three replicas of a pointer are loaded from one net, the voted next
pointer, which is precisely the signature `opt_merge` hashes on. Without
the per-replica storage transform the collapse would have been the
expected outcome rather than a risk.

It did not happen, and that is a measurement rather than an
expectation. The shipped netlist carries **3 flip-flops under each of
the twelve pointer banks**, 36 in total, out of 1,275, with the
configuration domain still at 55/55/55 beside it **[measured,
`docs/22` sections 3 and 9.3, counted in
`final/nl/tt_um_melihakbulut_nssoc.nl.v` after placement, CTS and
routing have all had a chance to touch it]**. The synthesis netlist
agrees with the final netlist on both PDKs, so nothing downstream of
mapping ate a bank either.

Two points carry forward from the correction above rather than being
re-learned. The guard **counts cells, not names**: `(* keep *)` was
already measured to leave replica wire names in a netlist whose storage
had disappeared. And the guard that covers this was **skipping** rather
than passing until a hardening run existed that postdated the RTL
declaring the banks — a skip on *provenance*, deliberately not on the
netlist, because a netlist-shaped skip would skip on exactly the symptom
the file exists to catch. `test_pointer_tmr_survives_the_real_hardening_flow`
now passes **[measured, `docs/22` section 3]**. The difference between
this case and the one above is only when it was measured: the
configuration TMR was found collapsed *after* a harden had already
shipped a netlist to this datasheet, and the pointer TMR was found
intact before one did.

### 6.4 What is not protected, and the residual risk

**The honest statement, corrected 2026-08-29.** This paragraph opened
"roughly a third of single-bit upsets ... 91 of 255, 35.7% [measured]".
That was the pre-hardening campaign and is superseded; see section 6.2.
On the campaign of record it is **26 of 335, 7.8% [measured]**
*(corrected 2026-09-05: on the frozen 378-injection log it is **6 of
378, 1.6 %** **[fact, `hw/tb/fi_campaign_results.json`]**, and the
pairing rule below applies to 7.8 % against 1.6 % as well)* — and
the two figures must not be paired, for the denominator reason section
6.2 gives. The qualitative statement is what survives the correction and
it survives unchanged: **every silent corruption still comes from a
structure the device does not claim to protect.** That is a statement
about design honesty and not a mitigation — the unprotected structures
still carry the event path and the queue storage, and three of the six
items below are unchanged by two rounds of hardening. A host that reads only this
device's fault counters and fault pins will, on those occasions, be told
that nothing happened while the spike stream or the neuron state is
wrong. There is no mechanism in this device that closes that gap, and
none is claimed. The specific unprotected structures, in order of how
much of that risk they are expected to carry, are:

**Corrected 2026-08-29 — items 1, 2 and 3 below have since been
hardened and are no longer unprotected.** The list is retained in its
original order because the *reasoning* in each item is why the hardening
was done, and the reasoning is the auditable part. What changed, read
from `hw/tb/fi_campaign_results.json`:

- **Item 1, live synapse weights (`wmem`).** 56.2% SDC of 16 → **0 SDC
  of 16** (13 CORRECTED, 3 MASKED), with a `wchk` check field that is
  itself 12/12 CORRECTED. The host-reload mitigation is no longer the
  only defence; it remains good driver practice.
- **Item 2, neuron state (`vmem`, `rmem`).** 91.7% and 100.0% SDC →
  **0 SDC of 24 and 0 SDC of 12**, all 36 CORRECTED, with an `smem`
  check field at 18/18 CORRECTED. The "no parity, no ECC, no TMR"
  sentence in that item is superseded outright.
- **Item 3, AER queue pointers.** 91.7% SDC of 24 → **0 SDC of 72**, all
  72 CORRECTED and counted on `CNT_TMR`. The sentence "it is not in this
  device" was true when written and is now false; the pointer TMR
  landed in `hw/rtl/aer_fifo.v` at commit `c5a5a6e`. Read `docs/16`
  section 3.3 before quoting the 72/72, and section 6.3 of this document
  for why a redundant structure measured correct at RTL is not yet
  proved present in silicon.

Items 4, 5 and 6 are **unchanged and still current** on the
335-injection campaign: telemetry is still unprotected in both
directions (13 of 18 `regbank_cnt` injections still moved a counter or a
flag with the output correct), latent register corruption is still
**15** injections, and the `STATUS.OVF_SEEN` / `CNT_EVQ_OVF` gap is
still there. So are the five structures listed in section 6.2's current
per-structure table, which is where the residual 7.8% now lives.

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
- **The campaign does not represent every flip-flop in the design.** The
  serial shift engine, the input synchronisers, the SYNC echo path, the
  ECC loader state and a handful of single flops are not injected into.
  *Corrected 2026-08-29:* this bullet said "85%", a figure computed
  against the 255-injection target list. The represented population has
  since grown twice — 996 flip-flops, then 1,076, then 1,100 — and
  `docs/16` section 2 carries the current coverage table and is the only
  place the percentage should be read from. It is not restated here.
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
- **Counting a corrupted retained neuron state as SDC is a choice.** This
  datasheet takes the stricter view because the state is architecturally
  visible through `N_ADDR`/`N_DATA` and is the neuron's memory.
  *Corrected 2026-08-29:* the illustration this bullet used — "`vmem` at
  29% and `rmem` at 25% instead of 91.7% and 100%" — is superseded,
  because `vmem` and `rmem` now report 0 SDC on either counting rule.
  The choice still costs something, but far less: on the 335-injection
  campaign only **3 of the 26 SDC outcomes** corrupted the retained state
  alone rather than the event stream, and all three are the mis-steered
  scan index of `lif_scan` **[measured,
  `state_only_divergence` in `hw/tb/fi_campaign_results.json`]**. A
  stream-only campaign would report 23 SDC rather than 26. *Corrected
  2026-09-05: on the frozen 378-injection log `state_only_divergence`
  is **4 of 6 SDC** **[fact, the same key at HEAD]**, so a stream-only
  campaign would report 2; which structures the four sit in is not
  read out here.*

---

### 6.6 Correction, 2026-09-09: the three replicas are not separated on the die

Sections 1.1, 3 and 6.1 above say the configuration is protected by
triple modular redundancy, and they are **left standing** because they
were true of what had been measured when they were written: three banks
of 55 flip-flops in the mapped netlist, counted by cells rather than by
names, in two synthesis flows and with every preservation attribute
stripped. Section 6.3 is the record of how that came to be measured at
all.

`docs/79-replica-placement-and-equivalence.md` measured the other half,
on **this device's own frozen sign-off layout**, from the run's final
DEF **[fact, 2026-09-09]**: the three banks share one region;
**103 of the 165 configuration flip-flops have their nearest fellow
configuration flip-flop in a different replica**, against a median
cross-replica separation of 113.47 um; 49 cross-replica pairs abut; and
the closest pairs are the same bit of the same word. No placement
constraint was applied, none was requested, and none is available before
the shuttle.

So the correct statement about this part is that the configuration is
**triplicated in the netlist**. Section 6.2's campaign result stands as
an RTL result and section 6.3's census stands as a netlist result;
neither is a statement about a die whose replicas touch.

Section 1.2's rule applies unchanged and now has a third clause: no
total-dose figure, no cross-section, **and no separation**. A distance
is not a safety argument in either direction --- nothing here says a
common-mode upset occurs at any fluence, and nothing here says a
different separation would prevent one. What the measurement removes is
the evidence for reading section 6.1 as a property of the manufactured
die.

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

*Superseded 2026-08-30. The table above is the `tmr-reharden` state and
is kept as it stood.* Replacement values, and the runs they are read
from — `tt/runs/wave5-ihp-b/` for the current RTL at 4x2, and
`hw/openlane/pilot_ihp/runs/shape-6x2/` for the shape actually
submitted:

| Parameter | Above | **Current** | Tag |
|---|---|---|---|
| Tile shape | 4x2, 8 tiles | **Tiny Tapeout 6x2, 12 tiles** | [measured] |
| Die area | 268,059 um2 | **404,499 um2** | [measured] |
| Core / placement-row area | 259,837 um2 | **392,988 um2** | [measured] |
| Mapped flip-flops | 1155, [in flux] | **1275 `sg13g2_dfrbpq_1`** | **[measured]** — no longer in flux |
| of which configuration TMR | 55 in each of three banks | **55 in each of three banks** | [measured] — unchanged |
| of which AER pointer TMR | not present | **3 in each of twelve banks**, 36 total | [measured] |
| Placed standard-cell area | 158,268 um2 | **185,840 um2** | [measured] |
| Utilization | 60.91 % | **47.2887 %** | [measured] |

**[fact, `docs/22` sections 9.3 and 9.5 and `docs/23` sections 1.4, 2.1
and 5; the pointer-bank census is counted with
`sw/tests/test_synthesis_guards.py`'s own flip-flop predicate over the
shipped netlist.]** The die and core areas moved for one reason only —
the tile is larger. The design's own placed area differs between the two
shapes by 85 um2, 0.05 %.

**Source paths.** Every `tt/runs/tmr-reharden/…` path in this section
should be read as **`tt/runs/wave5-ihp-b/…`** for the current 4x2
figures, or as `hw/openlane/pilot_ihp/runs/shape-6x2/…` for the
submitted shape. `tt/runs/` is gitignored, so the run tag and the metric
key are the record rather than the path.

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

*Superseded 2026-08-30.* **The re-harden is no longer in progress**; it
completed twice at 4x2 and twice more at twelve tiles. All three IHP PVT
corners still close at 20 ns with **zero setup, hold, max-capacitance
and max-slew violations**, at worst setup slack **+0.9121 ns** and worst
hold slack **+0.1180 ns** at 4x2 (`wave5-ihp-b`, `0448282`), and
**+1.2347 ns** and **+0.1089 ns** on the submitted 6x2 shape — the best
slow corner of any harden of this netlist **[measured, `docs/22`
sections 9.3 and 9.5; `docs/23` section 3.1]**. Slow-corner Fmax is
**53.3 MHz** at 6x2 against the 50 MHz declared **[estimate, arithmetic
on a measured slack]**. The margin has narrowed by about 5.2 ns since
the +6.4359 ns above, spent by the memory ECC and returned in part by
every step since; `docs/22` section 2.3 records the resulting caution,
that on this design netlist size does not predict slack in either
direction.

> **Corrected 2026-08-30 — the 4x2 "closes" claim above is withdrawn,
> the 6x2 one survives, and every slack in this section is an
> un-derated number.**
>
> `docs/28` section 4.4(b) establishes that this flow has never applied
> the 5 % on-chip-variation derate its configuration asks for.
> `TIME_DERATING_CONSTRAINT` is the integer `5` in both PDKs and
> LibreLane's `base.sdc` computes the factor as `expr 5 / 100`, which is
> Tcl integer division and yields `0`; the derate factors are 1.0 and
> 1.0 while every log line reports "Setting timing derate to: 5%". Every
> setup and hold slack quoted anywhere above is therefore correct as
> reported and carries **no OCV margin at all**.
>
> Both runs this section names were re-derived by re-running the
> sign-off corner standalone on their own shipped netlist, parasitics,
> constraints and liberty — the method of `docs/28` section 11, which
> reproduces each run's own metric to 17 significant digits before the
> derate lines are added **[fact]**:
>
> | Run | Shape | Setup, as the flow signs off | **Setup, 5 % derate applied** | Hold, fast, as signed off | **Hold, fast, derated** |
> |---|---|---|---|---|---|
> | `wave5-ihp-b` | 4x2 | +0.9121 | **-0.0675** | +0.1180 | **+0.0846** |
> | `shape-6x2` | **6x2, submitted** | +1.2347 | **+0.2913** | +0.1089 | **+0.0898** |
>
> **[fact, standalone OpenSTA on `final/{nl,spef,sdc}` of each run at
> `nom_slow_1p08V_125C` and `nom_fast_1p32V_m40C`.]**
>
> **What this changes, in order of how much it matters.**
>
> - **"All three IHP PVT corners still close at 20 ns … at 4x2" is false
>   under the honest definition.** At 4x2 the slow corner is
>   **-0.0675 ns** with the derate applied — a miss, not a close. The
>   sentence is true only of a sign-off that applies no derate. 4x2 is
>   not the submitted shape (section 7.2), so this corrects the record
>   rather than the submission.
> - **The 6x2 statement stands.** The submitted shape closes the slow
>   corner at **+0.2913 ns** derated, 1.46 % of the cycle. It is a close,
>   and it is thin.
> - **Hold closes on every corner under either definition**, at 4x2 and
>   at 6x2. The derate costs hold about 0.02-0.03 ns and does not take it
>   negative.
> - **Slow-corner Fmax is 50.7 MHz at 6x2, not 53.3 MHz**, and
>   **49.8 MHz at 4x2**, against the 50 MHz declared **[estimate,
>   arithmetic on a measured slack, on the linearity `docs/28`
>   section 5.6 measures]**. The 53.3 MHz figure above is the
>   un-derated one and is kept as what was reported.
>
> **The declared 50 MHz is still met on the submitted shape, and the
> margin is 0.7 MHz rather than 3.3 MHz.** `docs/28` section 6.2 adopts
> a configuration that takes it to **+0.7510 ns and 51.95 MHz** derated
> on this RTL and shape, for four flow keys and +0.102 % of area; that
> configuration is not yet through its geometric decks (`docs/28`
> section 10 item 7), so this document does not adopt its numbers.

**Verification status, run for this document [measured]:**

- `sw/tests/`: 152 passed, 1 skipped — including the eight synthesis
  guards and the mechanical cross-check that `regmap/regmap.yaml` and
  the normative register list do not diverge in name, offset, access or
  reset.
- `hw/tb/Makefile.pilot`: 23 cocotb tests, zero failures, driving the
  Tiny Tapeout top level.

*Superseded 2026-08-30, and it should be re-derived rather than patched.*
The synthesis-guard file alone is now **17 passed, 0 skipped**: the
skipped test was `test_pointer_tmr_survives_the_real_hardening_flow`,
which declined to assert a property no run on disk could witness, and it
passes against the wave-5 netlists **[measured, `docs/22` sections 3 and
9.2]**. The whole-suite figure above is stale in both directions and
`docs/22` open item 5 says to re-run it rather than adjust it by hand.
The last whole-suite run on record is **1 failed, 195 passed**, and the
one failure is deliberate: `test_tile_shape_is_the_documented_decision`
asserts `tiles == "4x2"` and the documented decision moved to 6x2, so
the guard caught the submission moving with it. It is a one-line change
in a file `docs/23` did not own **[measured, `docs/23` section 9.2]**.

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

> **Superseded 2026-08-30: this table is no longer in flux, and the
> flux warning above it is withdrawn.** Four hardens have completed
> since — two at 4x2 and two at twelve tiles — and the figures below are
> [measured] against a named run rather than directionally right. The
> table above is kept as the record of what was in motion.
>
> | Quantity | "Current run" above | **4x2 at `0448282`** | **6x2, submitted** |
> |---|---|---|---|
> | Mapped flip-flops | 1155 | **1275** | **1275** |
> | Post-synthesis cell area | 126,647 um2 | **151,789.11 um2** | **151,789.11 um2** |
> | Placed standard-cell area | 158,268 um2 | **185,755 um2** | **185,840 um2** |
> | Utilization | 60.9 % | **71.4890 %** | **47.2887 %** |
> | Worst slow-corner setup slack | +6.4359 ns | **+0.9121 ns** | **+1.2347 ns** |
> | *…the same, with the 5 % OCV derate actually applied* | *+5.7331 ns* | ***-0.0675 ns*** | ***+0.2913 ns*** |
> | Total power at 50 MHz, typical | not yet re-measured | **5.191 mW** | **5.130 mW** |
>
> **[measured, `docs/22` sections 9.3 and 9.5 and `docs/23` sections 2.1,
> 3.1 and 3.3.]**
>
> Three things the table does not say on its own.
>
> - **The power figure is now measured, and it is not a silicon
>   measurement.** 5.130 mW at 6x2 breaks down as 4.2402 mW internal,
>   0.8755 mW switching and 14.35 uW leakage, and it is the flow's own
>   estimate from **default switching activity**, not an
>   annotated-activity analysis. The 4.36 mW this section carried was a
>   real figure for a design 36 % smaller. Section 7.3's [TBD] on silicon
>   power stands unchanged.
> - **"Utilization of the 4x2 block … still well inside the tile" is
>   retracted.** At 71.49 % the design is *inside the tile* and **outside
>   the 70 % planning criterion**, by 5,527 um2 or 2.13 % of the core.
>   Those are two different statements: 4x2 closed to a GDS with zero DRC
>   on every deck, and the planning margin — the allowance for a precheck
>   that places differently and for a shuttle-side reharden — was gone.
>   That finding is what moved the submission to **6x2**, where the same
>   netlist sits at 47.29 % with 32.44 % of the core spare **[fact,
>   `docs/22` sections 4.2 and 9.4, `docs/23` sections 2.2 and 6]**.
> - **DRC, LVS and antenna are no longer pending; they are complete and
>   all zero, including KLayout DRC.** On the submitted 6x2 run: route
>   DRC 0, Magic DRC 0, KLayout DRC 0, Netgen LVS 0 on all seven
>   counters, antenna 0 nets and 0 pins with **zero repair diodes**, 0
>   power-grid violations, `design__violations` 0 and
>   `flow__errors__count` 0 **[measured, `docs/23` sections 2.1, 3.3 and
>   4.4, and the seven `design__lvs_*` counters read directly from
>   `hw/openlane/pilot_ihp/runs/shape-6x2/final/metrics.json`; the
>   KLayout deck is also closed at `c5a5a6e` on 4x2 by `docs/22`
>   section 2.4]**. The Magic/KLayout XOR is still not run on IHP and is
>   not claimed.

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
  *superseded* pre-fix design. *Updated 2026-08-30: the current
  equivalent is **5.130 mW** on the submitted 6x2 netlist, and every
  word of this bullet applies to it unchanged* — it is the same
  flow-computed estimate from the same default activity assumptions, on
  a design that has grown, and it is **not** a silicon measurement
  **[measured, `docs/23` section 3.3]**. It is not a silicon measurement, it does
  not describe the current netlist, and it says nothing about power
  under a realistic event workload — the flow's activity assumptions are
  not this device's.
- **Timing at silicon**: achieved Fmax, setup and hold at the real
  process corners, and the temperature range over which they hold.
  [TBD]
- **On-chip-variation margin in the sign-off.** [TBD] *Added
  2026-08-30.* Every setup and hold figure in section 7.1 is quoted
  from a flow that reports applying a 5 % OCV derate and applies none
  — `TIME_DERATING_CONSTRAINT` is an integer and `base.sdc` divides it
  by 100 in Tcl integer arithmetic **[fact, `docs/28` section 4.4b]**.
  Section 7.1's correction note re-derives both runs with the derate
  applied by hand, which is evidence but is **not a flow gate**: no run
  in this repository has yet signed off through the flow with OCV
  derating, and no figure here should be read as carrying a derated
  sign-off until one does (`docs/28` section 10 item 1).
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
itself*. Also confirm `FAULT_CLR` = `0xFF` clears everything including
`CNT_TMR`, `CNT_EVQ_OUT_OVF` and `CNT_EVQ_PAR`. **Corrected
2026-09-09**: this step said `0x3F`, which leaves the last two
counters standing and would have made the very telemetry cross-check
this step establishes read a stale value as a live one. Section 5.3
carries the reasoning and the superseded number.

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
7. **`tt/docs/info.md` under-describes the die it ships with.** Added
   2026-09-09. **CLOSED 2026-09-11.** *The gap described below is gone
   and the paragraph is left standing as the record of what the
   submitted datasheet omitted between 2026-08-29, when
   `CNT_EVQ_OUT_OVF` entered the decode, and the regeneration. Read it
   in the past tense. What closed it: `tt/` was regenerated from a
   `scripts/gen_tt_submission.py` that no longer writes the pilot-only
   addresses down at all — `_pilot_decode()` reads them out of
   `hw/rtl/pilot_top.v` and `_pilot_only_table()` exits the generator
   if the two sets disagree, and `_fault_clr_bits()` does the same for
   the mask. `tt/docs/info.md` now lists `CNT_EVQ_OUT_OVF` at 0x0AC and
   `CNT_EVQ_PAR` at 0x0B0, allocates `FAULT_CLR` bits 6 and 7 to them,
   says "Writing `0xFF` clears everything", and carries its own dated
   note leaving the superseded `0x3F` standing rather than deleting it.
   `sw/tests/test_tt_submission.py`'s
   `test_pilot_only_registers_and_fault_clr_bits_are_documented` no
   longer pins the two names: the pinned set emptied, so the pin was
   retired rather than widened — a widened pin cannot tell a fix from a
   regression — and what stands in its place is the two-directional
   form, that every register the die decodes appears in the shipped
   table and that the superseded mask does not. The comments at
   `sw/tests/test_tt_submission.py` lines 475 and 606 are that
   retirement written out.* Its pilot-only register table lists three registers
   (0x0A0, 0x0A4, 0x0A8) and its `FAULT_CLR` table lists bits 0 to 5,
   ending "Writing `0x3F` clears everything". The die those files
   accompany — `tt/src/pilot_top.v`, byte-identical to
   `hw/rtl/pilot_top.v` — decodes `CNT_EVQ_OUT_OVF` at 0x0AC and
   `CNT_EVQ_PAR` at 0x0B0 and allocates `FAULT_CLR` bits 6 and 7 to
   them, and its own line 255 says the portable clear-everything write
   is `0xFF`. So an operator following the submitted datasheet reads a
   stale event-loss count and never learns the two counters exist.
   `tt/` is frozen for the shuttle and `tt/docs/info.md` is generated by
   `scripts/gen_tt_submission.py`, whose `PILOT_ONLY_REGS` list (around
   line 162) and `FAULT_CLR` template (around line 1010 to 1020) are
   where the omission actually lives; neither file is corrected here,
   and correcting them regenerates `tt/`. Section 5.3 of this document
   is now complete and is the reference to use in the meantime.
   `sw/tests/test_tt_submission.py`
   `test_pilot_only_registers_and_fault_clr_bits_are_documented` pins
   the omission to exactly these two registers and exactly this clear
   value, so a third undocumented register or a further-drifted mask
   fails the suite instead of passing it.
8. **`docs/15` section 3 deviation D5 says four pilot-only registers**
   and lists 0x0A0, 0x0A4, 0x0A8, 0x0AC. There are five; `CNT_EVQ_PAR`
   at 0x0B0 arrived with `docs/30` and D5 was not revisited. `docs/15`
   is a historical plan record and is not edited to match today; this
   entry is the correction, and section 5.3 above carries the live list.

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
