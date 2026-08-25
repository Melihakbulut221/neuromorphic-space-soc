# 10 — NPU MVP Micro-architecture Specification v0.1

Date: 24 August 2026
Status: v0.1 working spec for the event-driven inference engine MVP.
Grounding: implements the recommendation of `docs/02-npu-architecture.md`
(Candidate B — single time-multiplexed LIF neuron core, architected as one
node of a future mesh) at the full 512-neuron scale. For the NPU block,
this spec SUPERSEDES the physical envelope of
`docs/01-reference-decomposition.md` section 4 (64-96 KB fabric SRAM,
resident weights near 30-60 KB, single-pass models up to roughly 60-120k
4-bit parameters): the 144 KB configuration of section 5 exceeds that
sky130-derived envelope on every axis, and its physical feasibility rests
on the IHP SG13G2 foundry SRAM macros (`RM_IHPSG13_1P_*`, ~25-40 KiB/mm²
including periphery) per `docs/04-technology-and-flow.md` section 3.1 and
the recomputed Candidate B feasibility row of `docs/02` section 3 (~156 KB
weight SRAM ~4-6.2 mm² on SG13G2 foundry macros, out of reach of
OpenRAM-density sky130 — a hard dependency on the IHP-primary technology
decision, stated in `docs/02` section 4). The
`docs/01` envelope remains the reference for the whole-SoC budget, and
the parameterization of section 2 (N_NEURONS, N_AXONS) allows a smaller
instantiation — e.g. the 256-neuron fallback point of `docs/02` — if SoC
integration forces it. Conventions carried over
from the developer's prior 130 nm accelerator practice: a bit-exact integer
golden model as the executable specification, round-shift-saturate
arithmetic discipline, a single-source register map, and pytest regression
before any RTL exists.

The golden model in `sw/golden/` is the normative executable form of the
equations in section 4; the RTL, when written, is verified against it
bit-for-bit. Section 13 maps every numbered equation to the pytest that
exercises it.

## 1. Scope and execution model

One event-driven neurosynaptic core (tinyODIN-class):

- N_NEURONS leaky integrate-and-fire (LIF) neurons, time-multiplexed over
  a single physical update pipeline. Default N_NEURONS = 512.
- N_AXONS input axons addressing a crossbar-organized synaptic weight
  SRAM of N_AXONS x N_NEURONS 4-bit signed weights. Default N_AXONS = 512
  (256k synapses, 128 KB data).
- AER (address-event representation) event queues in and out.
- Configuration and observability over a 32-bit config bus (APB-class)
  from the RV32 management core; the register list in section 10 is the
  input to the future single-source `regmap/regmap.yaml`.
- Multi-pass execution for networks larger than the physical core:
  weight slices resident in QSPI flash, loaded per pass, events replayed
  (section 9).
- Inference only. No on-chip learning, no convolution engine in v0.1
  (Candidate C territory, see `docs/02` section 4).

The core never requires the CPU in the spike-processing loop: events in,
events out, CPU touches only configuration, weight loading, and pass
sequencing.

## 2. Parameters

All counts are Verilog module parameters; the arithmetic widths are fixed
by this spec revision.

| Parameter | Default | Range | Notes |
|---|---|---|---|
| N_NEURONS | 512 | 1..1024 | physical neurons per core (10-bit id space) |
| N_AXONS | 512 | 1..1024 | input axon id space per pass |
| W_BITS | 4 | fixed v0.1 | signed two's complement weights |
| V_BITS | 16 | fixed v0.1 | signed membrane potential |
| R_BITS | 4 | fixed v0.1 | refractory counter |
| WEIGHTS_PER_WORD | 16 | fixed v0.1 | 64-bit weight SRAM data word |
| EVQ_IN_DEPTH | 64 | impl. choice | input event FIFO |
| EVQ_OUT_DEPTH | 64 | impl. choice | output event FIFO |

Derived, at defaults: 256k synapses, 128 KB weight data + 16 KB SECDED
check bits (section 5), 1.5 KB neuron state — consistent with the
Candidate B budget in `docs/02` section 3.

## 3. Neuron state layout

Per-neuron state word, 24 bits, held in the neuron state memory
(SRAM or FF file, N_NEURONS x 24):

| Bits | Field | Meaning |
|---|---|---|
| [15:0] | V | membrane potential, signed 16-bit two's complement, range [-32768, +32767] |
| [19:16] | R | refractory countdown, unsigned 4-bit, 0 = not refractory |
| [23:20] | reserved | zero in v0.1; future per-neuron parity/flags hook |

Threshold, reset potential, leak shift, synaptic shift and refractory
period are core-global configuration (one layer per pass), not per-neuron
state — per-neuron thresholds are a v0.2 candidate, not in this spec.

State after hardware reset is UNDEFINED (state memory is not reset by the
reset net); software must run CTRL.STATE_CLR (section 11.1) before
enabling the core. The golden model starts from the post-STATE_CLR state:
V = 0, R = 0 for all neurons.

## 4. LIF update equations (bit-exact, normative)

Notation: all arithmetic below is exact integer arithmetic followed by
explicit saturation where stated. Signedness and widths are stated per
operation; the golden model implements these equations literally, with no
floating point anywhere in the evaluation path. Configuration symbols:
threshold THETA, reset potential V_RESET, leak shift S_LEAK, synaptic
shift S_SYN, refractory period T_REFR (validation ranges in section 6).

### 4.1 Synaptic event processing

Consuming one input spike event with axon id `a` updates neurons
j = 0, 1, ..., CFG_NEUR-1 in ascending order. For each neuron j:

Refractory gate — if R[j] > 0, the event is discarded for this neuron: no
state change, no spike, proceed to neuron j+1 (equation E7, section 4.3).
Otherwise:

(E1) Weight decode. The stored 4-bit code is interpreted as signed two's
complement:

    w = sext4(W[a][j]),  w in [-8, +7]

(E2) Synaptic contribution. The weight is scaled by the configured left
shift, exactly (no truncation, no rounding):

    c = w * 2^S_SYN,  S_SYN in [0, 7]  =>  c in [-1024, +896]

If the weight word holding W[a][j] is flagged uncorrectable by ECC, c = 0
is substituted (equation E10, section 11.2).

(E3) Saturating integration. The contribution is added to the membrane
potential and the sum is saturated to the signed 16-bit range:

    V'[j] = sat16(V[j] + c)
    sat16(x) = +32767 if x > +32767; -32768 if x < -32768; else x

The pre-saturation sum fits in 18 signed bits; the RTL must compute it at
full width and then clamp. Two's complement wraparound is a specification
violation (a wrapped positive overflow would silently lose a spike).

(E4) Spike condition. Evaluated after E3, on every non-gated synaptic
event, including events whose contribution is zero:

    spike(j)  <=>  V'[j] >= THETA        (signed compare)

The compare uses the post-saturation value. Checking before the update, or
one event late, is a specification violation (this exact off-by-one was a
verified bug class in the developer's prior LIF silicon work; E4's
check-after-update ordering is deliberate and tested).

(E5) Reset on spike. If spike(j):

    V''[j] = V_RESET
    R[j]   = T_REFR

and one output spike event with neuron id TILE_OFF + j is emitted
(TILE_OFF is the multi-pass tile offset, section 9; 0 in single-pass use).
If no spike, V''[j] = V'[j] and R[j] is unchanged.

### 4.2 Tick (timestep) event processing

Consuming one TICK event updates neurons j = 0..CFG_NEUR-1 in ascending
order. For each neuron j, two independent actions:

(E6) Leak as right-shift toward zero (applied when CFG_FLAGS.LEAK_EN = 1),
with a minimum decrement of 1 so that every nonzero potential reaches zero
in bounded time:

    if V[j] == 0:        V'[j] = 0
    else:
        m = |V[j]| >> S_LEAK          (logical shift of the magnitude)
        if m == 0: m = 1
        V'[j] = V[j] - m   if V[j] > 0
        V'[j] = V[j] + m   if V[j] < 0

Properties (normative): |V'| < |V| for V != 0; the sign never flips; the
magnitude |V[j]| is computed at 16-bit unsigned width (|-32768| = 32768 is
representable). S_LEAK = 0 clears the potential in one tick. Leak applies
regardless of the refractory state.

(E7) Refractory countdown and gating:

    on TICK:            R'[j] = R[j] - 1 if R[j] > 0, else 0
    on synaptic event:  R[j] > 0 gates E1..E5 for that (event, neuron):
                        no integration, no spike, no state change

TICK events never emit spikes: E6 moves V strictly toward zero and
V_RESET < THETA is enforced by configuration validation, so no threshold
crossing is possible on a tick.

### 4.3 Ordering and determinism

(E8) The core is a deterministic function of (initial state, configuration,
weights, input event stream). Normative ordering rules:

1. Input events are consumed strictly in FIFO arrival order; all neuron
   updates for event k complete before event k+1 begins.
2. Within one synaptic event, neurons are scanned in ascending index j,
   and output spikes are emitted in scan order (ascending TILE_OFF + j).
3. The output stream is the concatenation of per-event emissions in input
   event order. Event arrival order therefore outranks neuron id order
   across events.
4. TICK processing emits nothing and completes before the next event.

No arbitration, no clock-dependent reordering, no dropped events on the
processing path. This is what makes the golden model bit-exact against
the RTL and what makes fault-injection results attributable.

### 4.4 Invariants

- Between events, V[j] < THETA holds for every non-refractory neuron
  (post-spike V_RESET < THETA; leak only shrinks magnitude). The only way
  to violate it is a debug write through N_DATA or an SEU; E4's
  check-always-after-update rule bounds the consequence to one spike on
  the next event touching that neuron.
- V[j] in [-32768, +32767] and R[j] in [0, 15] always (E3, E5, E7).

## 5. Synapse memory organization

- Logical array: W[a][j], a in [0, N_AXONS), j in [0, N_NEURONS), 4-bit
  signed. Linear bit address: (a * N_NEURONS + j) * 4 — axon-major, so
  one event's weight column is a contiguous burst.
- Physical word: 64 data bits = 16 weights, plus 8 SECDED check bits
  (72-bit macro word, 12.5 percent overhead). Word index of W[a][j]:
  (a * N_NEURONS + j) / WEIGHTS_PER_WORD.
- At defaults: 16384 words = 128 KB data + 16 KB check bits = 144 KB
  physical — the dominant NPU area, in line with the `docs/02` estimate;
  the 256-neuron / 64k-synapse fallback point (F1 in `docs/02`) shrinks
  this 4x with no architectural change, which is why N_NEURONS and
  N_AXONS are module parameters.
- One synaptic event reads N_NEURONS / WEIGHTS_PER_WORD = 32 words
  (defaults) and the pipeline applies E1..E5 to 16 neurons per word read.
- Write access: config-bus load port (W_ADDR auto-increment, W_DATA_LO /
  W_DATA_HI commit, section 10) in v0.1; a QSPI DMA path is the planned
  full-chip addition (section 9).
- ECC behavior on read: single-bit errors corrected inline (CNT_SEC
  increments); double-bit detection substitutes zero per E10 (section
  11.2).

## 6. Configuration parameters and validation

Core-global, loaded per pass. The golden model rejects out-of-range
values with an error; the RTL latches STATUS.ERR_CFG and refuses to start.

| Symbol | Register | Range | Reset | Notes |
|---|---|---|---|---|
| THETA | CFG_THRESH | [1, +32767] | 256 | signed compare per E4; must be positive |
| V_RESET | CFG_VRESET | [-32768, THETA-1] | 0 | must be below threshold |
| S_LEAK | CFG_LEAK | [0, 15] | 3 | right-shift per E6 |
| S_SYN | CFG_SYNSHIFT | [0, 7] | 0 | weight scale per E2 |
| T_REFR | CFG_REFR | [0, 15] | 0 | 0 disables refractory |
| CFG_NEUR | CFG_NEUR | [1, N_NEURONS] | N_NEURONS | active neurons this pass |
| CFG_AXON | CFG_AXON | [1, N_AXONS] | N_AXONS | valid axon id bound; events with a >= CFG_AXON are dropped and counted (CNT_AXON_OOR) |
| LEAK_EN | CFG_FLAGS[1] | 0/1 | 1 | gates E6 |
| TS_EN | CFG_FLAGS[0] | 0/1 | 0 | timestamp word on AER (section 7.3) |

Configuration writes while STATUS.BUSY = 1 are ignored and latch ERR_CFG
(CTRL, STATUS_CLR and FAULT_CLR remain writable).

## 7. AER event interface

### 7.1 Local event word (16-bit)

| Bits | Field |
|---|---|
| [15:14] | TYPE |
| [13:10] | reserved, zero |
| [9:0] | ID (axon id on input, neuron id on output) |

TYPE encoding:

| TYPE | Name | Input meaning | Output meaning |
|---|---|---|---|
| 00 | SPIKE | synaptic event, ID = axon id (E1..E5) | spike, ID = TILE_OFF + neuron id |
| 01 | TICK | timestep boundary (E6, E7) | not emitted |
| 10 | SYNC | frame barrier: when consumed, all prior events are fully processed and a SYNC is emitted downstream | barrier echo |
| 11 | reserved | dropped, counted | not emitted |

SYNC is the determinism and multi-pass handshake primitive: the CPU (or
an upstream mesh node) injects SYNC after a frame; the emitted SYNC plus
STATUS.SYNC_DONE tells the sequencer the output stream for the frame is
complete. TICK generation itself is external in v0.1 (CPU timer or
upstream node) — the core consumes time, it does not create it.

### 7.2 Input and output queues

- Input: EVQ_IN_DEPTH-entry FIFO, valid/ready handshake on the link side
  (backpressure, no in-mesh drops). The software injection port EVQ_IN
  drops on full and counts (CNT_EVQ_OVF, STATUS.OVF_SEEN).
- Output: EVQ_OUT_DEPTH-entry FIFO, valid/ready on the link side. A full
  output queue stalls the update pipeline (spikes are never dropped);
  deadlock freedom across a mesh is the future router's obligation,
  recorded in the freeze list (section 8).

### 7.3 Optional timestamp

With CFG_FLAGS.TS_EN = 1, every event word is followed by a 16-bit
timestamp word (free-running tick counter). Timestamps are observability
metadata only: processing semantics and the golden model are defined by
logical order (E8), never by timestamp values.

## 8. Frozen mesh-node interface

Per `docs/02` section 4 point 2, the core is specified from day one as
one node of a mesh, so Candidate C is a scale-out, not a redesign. The
following are FROZEN at v0.1 and may only be extended, not changed:

1. The 16-bit local event word of section 7.1 (TYPE / reserved / 10-bit ID
   split).
2. The mesh link word: 24 bits, {DST_NODE[3:0], SRC_NODE[3:0],
   EVENT[15:0]} — up to 16 nodes; a node forwards words whose DST_NODE
   differs from its NODE_ID register. In single-node v0.1 builds the
   8-bit routing prefix is tied off at the boundary.
3. Link handshake: valid/ready, backpressure-based, no drops on the
   processing path (section 7.2).
4. SYNC barrier semantics (section 7.1) as the frame/pass handshake.
5. The register map layout of section 10, including NODE_ID and the
   per-node fault counter block — one identical regmap instance per node
   at a per-node base address.

Adding a router, more nodes, or a convolution-capable node datapath must
not require changes to any of the five items above.

## 9. Multi-pass execution over QSPI-resident weights

The physical core holds exactly one N_AXONS x N_NEURONS weight slice.
Models larger than one slice live in QSPI flash as a sequence of pass
images, following the multi-pass concept of the reference architecture
(`docs/01` section 2.2).

- A pass = {load weight slice (W_BASE in QSPI -> weight SRAM), load
  configuration (section 6) and PASS_TILE_OFF, replay the input event
  stream, collect output events until SYNC}.
- Pass sequencing is owned by the RV32 management core through the
  register map in v0.1 (simple, observable — per `docs/02` open question
  5); a dedicated DMA/sequencer is a full-chip upgrade that must not
  change pass semantics.
- The input event stream of a pass is replayed from a buffer in system
  SRAM (or regenerated by the CPU); output events of a layer become the
  input events of the next layer, preserving per-timestep order (E8).

Two pass dimensions are supported in v0.1:

1. Layer-serial: one layer per pass; N layers = N passes minimum.
2. Output-neuron tiling, for layers wider than N_NEURONS:

(E9) Neuron-tiling equivalence. Partition a layer's output neurons into
ordered contiguous tiles of at most N_NEURONS. Run one pass per tile with
the corresponding weight column slice and PASS_TILE_OFF = tile base,
replaying the identical input event stream each pass. Concatenating, for
each input event, the tiles' emissions in tile order yields a stream
bit-identical to a hypothetical single core wide enough for the whole
layer. This holds because neuron trajectories are mutually independent
in v0.1 (no lateral coupling): each neuron's state depends only on the
event stream, its own weight column, and the configuration.

Limitation (explicit): the axon dimension is NOT splittable in v0.1 — a
layer's fan-in must satisfy fan-in <= N_AXONS. Axon-split passes would
interleave saturation and threshold crossings in a different order and
break bit-exactness; supporting them needs a deferred-threshold pass mode,
deferred to v0.2 (section 14).

Limitation (explicit): tiling does not lift the event-word ID bound. An
E9 pass emits ids TILE_OFF + j, and both the ID field of the frozen
16-bit event word (section 7.1) and PASS_TILE_OFF (section 10) are 10
bits wide: every tile must satisfy TILE_OFF + tile width <= 1024, so the
total width of a tiled layer is hard-capped at 1024 = 2^10 neurons. The
golden model enforces the bound: `NetworkRunner` rejects layers wider
than 1024 at construction, and `LIFCore` rejects tile_offset outside
[0, 1023] as well as tile_offset + n_neurons > 1024. Layers wider than
1024 neurons cannot be represented on the frozen event interface and are
refused, not approximated.

Bandwidth anchor (estimate): a full 128 KB slice over QSPI x4 at 50 MHz
(25 MB/s) takes about 5.2 ms; per-pass slices are usually smaller. The
pass-latency budget model required by `docs/01` open question 5 will use
these numbers; no latency claim is made here.

## 10. Register list (feeds the future regmap)

32-bit registers, byte offsets, one block instance per node. Access
codes as in house practice: RO, RW, WO, W1C (write-1-to-clear), SC
(self-clearing). This table is the input to the future single-source
`regmap/regmap.yaml`; the YAML, its generated header and this section
must not diverge once the regmap flow is instantiated.

### sys

| Offset | Name | Access | Reset | Description |
|---|---|---|---|---|
| 0x00 | ID | RO | 0x4E505531 | "NPU1" identity constant |
| 0x04 | VERSION | RO | 0x00000001 | spec/regmap version |
| 0x08 | SCRATCH | RW | 0x0 | read/write test register, no side effects |
| 0x0C | CTRL | RW | 0x8 | b0 EN (RW), b1 STATE_CLR (SC, zero all neuron state), b2 SOFT_RST (SC, flush queues and pipeline, config retained), b3 SCRUB_EN (RW, reset 1) |
| 0x10 | STATUS | RO | 0x6 | b0 BUSY, b1 EVQ_IN_EMPTY, b2 EVQ_OUT_EMPTY, b3 SYNC_DONE, b4 ERR_CFG, b5 DED_SEEN, b6 OVF_SEEN |
| 0x14 | STATUS_CLR | W1C | 0x0 | clear mask for STATUS b3..b6 |

### cfg (section 6)

| Offset | Name | Access | Reset | Description |
|---|---|---|---|---|
| 0x20 | CFG_NEUR | RW | N_NEURONS | active neuron count, [1, N_NEURONS] |
| 0x24 | CFG_AXON | RW | N_AXONS | valid axon id bound, [1, N_AXONS] |
| 0x28 | CFG_THRESH | RW | 0x100 | THETA, bits [15:0], signed, [1, 32767] |
| 0x2C | CFG_VRESET | RW | 0x0 | V_RESET, bits [15:0], signed, < THETA |
| 0x30 | CFG_LEAK | RW | 0x3 | S_LEAK, bits [3:0] |
| 0x34 | CFG_SYNSHIFT | RW | 0x0 | S_SYN, bits [2:0] |
| 0x38 | CFG_REFR | RW | 0x0 | T_REFR, bits [3:0] |
| 0x3C | CFG_FLAGS | RW | 0x2 | b0 TS_EN, b1 LEAK_EN |

### pass (section 9)

| Offset | Name | Access | Reset | Description |
|---|---|---|---|---|
| 0x40 | PASS_TILE_OFF | RW | 0x0 | TILE_OFF added to emitted neuron ids, bits [9:0] |
| 0x44 | W_BASE | RW | 0x0 | QSPI byte address of the current pass weight slice |
| 0x48 | PASS_ID | RW | 0x0 | software pass bookkeeping, bits [7:0] |

### wmem / nstate

| Offset | Name | Access | Reset | Description |
|---|---|---|---|---|
| 0x50 | W_ADDR | RW | 0x0 | weight SRAM word index; auto-increments on commit |
| 0x54 | W_DATA_LO | WO | — | weight word bits [31:0], staged |
| 0x58 | W_DATA_HI | WO | — | weight word bits [63:32]; write commits the 64-bit word (ECC bits generated in hardware) |
| 0x60 | N_ADDR | RW | 0x0 | neuron index for state access |
| 0x64 | N_DATA | RW | — | neuron state word: [15:0] V, [19:16] R, [23:20] reserved; debug and pass state save/restore |

### fault (section 11)

| Offset | Name | Access | Reset | Description |
|---|---|---|---|---|
| 0x70 | CNT_SEC | RO | 0x0 | corrected single-bit ECC events |
| 0x74 | CNT_DED | RO | 0x0 | uncorrectable double-bit ECC events |
| 0x78 | CNT_EVQ_OVF | RO | 0x0 | software-port event drops on full input queue |
| 0x7C | CNT_AXON_OOR | RO | 0x0 | events dropped for axon id >= CFG_AXON |
| 0x80 | FAULT_ADDR | RO | 0x0 | weight SRAM word index of the last DED |
| 0x84 | ECC_INJ | WO | — | b0 flip one bit, b1 flip two bits on the next W_DATA commit (verification hook, netlist-audited out of flight builds) |
| 0x88 | FAULT_CLR | W1C | 0x0 | clear the fault counters |

### aer

| Offset | Name | Access | Reset | Description |
|---|---|---|---|---|
| 0x90 | EVQ_STAT | RO | 0x0 | [7:0] input fill, [15:8] output fill |
| 0x94 | EVQ_IN | WO | — | software event injection (16-bit event word) |
| 0x98 | EVQ_OUT | RO | 0x0 | pop output event; b31 VALID, [15:0] event word |
| 0x9C | NODE_ID | RW | 0x0 | mesh node address, bits [3:0] (section 8) |

## 11. Reset and fault behavior

### 11.1 Reset

- Asynchronous assertion, synchronized deassertion (house rule S-02
  class); reset returns all registers of section 10 to their reset
  values and flushes both event queues.
- Neuron state and weight SRAM are NOT cleared by reset. Bring-up order:
  reset -> load weights -> configure -> CTRL.STATE_CLR (hardware
  sequencer zeroes all N_NEURONS state words; BUSY while running) ->
  CTRL.EN.
- CTRL.SOFT_RST flushes the pipeline and queues, keeps configuration and
  memories.

### 11.2 Weight SRAM ECC (E10)

SECDED per 64-bit word (section 5). On read:

- single-bit error: corrected inline, CNT_SEC increments; the scrubber
  (background walk while the input queue is empty, SCRUB_EN) rewrites
  corrected words to prevent accumulation.
- double-bit error:

(E10) uncorrectable word => c = 0 is substituted for every weight in the
affected word (E2 bypassed for those 16 synapses), CNT_DED increments,
FAULT_ADDR latches the word index, STATUS.DED_SEEN is set, and processing
CONTINUES. The core is fail-operational: a dead weight word degrades the
network, it does not stop the node. The CPU decides whether to reload the
slice from QSPI.

ECC_INJ provides the standard error-injection hook for verifying both
paths end-to-end; flight netlists are audited to exclude injection logic.

### 11.3 Membrane state: graceful degradation (no ECC in v0.1)

Neuron state carries no ECC in v0.1, by design (per `docs/02` open
question 6, to be backed by a fault-injection measurement):

- an upset in V is bounded by LIF dynamics themselves: worst case one
  spurious (or one missed) spike, then E6 drives the corrupted value back
  toward rest — the minimum-step-1 leak guarantees return in bounded
  time (strictly bounded by |V| ticks; approximately geometric, on the
  order of 100 ticks at S_LEAK = 3 from full scale).
- an upset in R is bounded by T_REFR <= 15 ticks of wrong gating.
- the 4 reserved state bits (section 3) are the hook for per-neuron
  parity if the fault-injection campaign shows the unprotected-state bet
  is wrong.

### 11.4 Control path

Scheduler and sequencer FSMs use Hamming-distance-2 state encodings with
default-case recovery to a SAFE state that latches STATUS.ERR_CFG; the
FSM + configuration register set is the core's TMR domain, per house
hardening rules. Event queue fault semantics are in section 7.2. A
watchdog kick output (state-advance pulse) is provided for the SoC-level
watchdog.

## 12. Deviation from Akida (clean-room note)

This design is clean-room with respect to BrainChip Akida and the GR801
integration of it. Only concept-level facts from public product briefs
and public secondary literature were used (via `docs/00`-`docs/02`):
event-driven processing, low-bit (4-bit) quantized weights, a mesh of
nodes, multi-pass execution of networks larger than the fabric. No
proprietary documentation, RTL, or reverse engineering of any kind was
involved. Deliberate divergences, stated explicitly:

- Neuron model: this core implements classical digital LIF dynamics
  (leak-as-shift, threshold-reset-refractory). Public descriptions of
  Akida 1.0 indicate rank-order/event coding rather than classical LIF;
  no attempt is made to reproduce Akida's coding scheme.
- No on-chip learning of any kind (Akida advertises edge learning in a
  final layer); v0.1 is inference-only.
- No convolution engines; fully-connected event processing only.
- Weight precision is 4-bit only in v0.1 (1/2-bit packing is a listed
  extension), versus Akida's 1/2/4-bit hybrid support.
- Sizing (512 neurons, 256k synapses per node) follows this project's
  130 nm SRAM budget, not any Akida configuration.

The time-multiplexed microarchitecture class follows the openly published
ODIN/tinyODIN line (Solderpad-licensed academic RTL, cited in `docs/02`);
this spec and its golden model are nevertheless written fresh, and the
reuse-policy decision of `docs/02` open question 2 (reference-only versus
code reuse) remains open for the RTL phase.

## 13. Golden model and traceability

Executable specification: `sw/golden/lif_core.py` (single-core equations
E1..E8, E10) and `sw/golden/network.py` (multi-pass runner, E9). The core
evaluation path uses Python integers only — no floating point exists in
any state update, by construction and by test.

Every numbered equation maps to at least one pytest in `sw/tests/`; the
mapping is enforced mechanically by
`sw/tests/test_traceability.py::test_every_spec_equation_has_a_test`,
which parses this document for equation tags and fails if any tag lacks a
matching `test_e<n>_*` test.

| Eq | Contract | Test (sw/tests/) |
|---|---|---|
| E1 | 4-bit signed weight decode and range | test_lif_core.py::test_e1_* |
| E2 | synaptic contribution shift, exactness | test_lif_core.py::test_e2_* |
| E3 | saturating 16-bit integration, no wrap | test_lif_core.py::test_e3_* |
| E4 | spike iff V' >= THETA, check after update | test_lif_core.py::test_e4_* |
| E5 | reset to V_RESET, refractory load, emitted id | test_lif_core.py::test_e5_* |
| E6 | leak as right-shift toward zero, min step 1 | test_lif_core.py::test_e6_* |
| E7 | refractory gating and countdown | test_lif_core.py::test_e7_* |
| E8 | FIFO order, ascending scan, determinism | test_events.py::test_e8_* |
| E9 | multi-pass neuron-tiling equivalence | test_multipass.py::test_e9_* |
| E10 | DED zero-substitution, fail-operational | test_lif_core.py::test_e10_* |

End-to-end behavior (3-layer network, two-pattern classification above
chance, single-pass versus tiled equivalence at network level) is covered
by `test_e2e.py`.

## 14. Open items toward v0.2

1. Axon-dimension multi-pass (deferred-threshold pass mode) for layers
   with fan-in > N_AXONS.
2. 1/2-bit weight packing modes (density multiplier from `docs/01`
   section 5).
3. Per-neuron threshold/leak tables (costs one more state field; decide
   after the first workload mapping).
4. QSPI DMA weight loader and hardware pass sequencer (semantics frozen
   by section 9; only the sequencing owner changes).
5. Regmap YAML instantiation and generated headers from section 10.
6. TICK self-generation (internal timestep timer) versus external-only.
7. Neuron-state parity decision, gated on the fault-injection campaign
   (section 11.3).
