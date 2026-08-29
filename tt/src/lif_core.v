// lif_core: time-multiplexed LIF neuron datapath (docs/10-npu-mvp-spec.md
// sections 1-4), pilot configuration with flip-flop synapse storage.
//
// One physical update pipeline serves N_NEURONS leaky integrate-and-fire
// neurons over an N_AXONS x N_NEURONS crossbar of 4-bit signed weights.
// The golden model sw/golden/lif_core.py is the normative executable
// specification; this module reproduces it bit for bit and is verified
// against it in lockstep by hw/tb/test_lif_core_rtl.py
// (make -f Makefile.lif in hw/tb). Lockstep constrains the arithmetic,
// not the control interface: the command-arbitration, handshake and
// SAFE-state behavior below is the part the golden model cannot express,
// and it is covered separately by the directed handshake tests in the
// same suite and by the proofs in formal/lif_ctrl_props.v
// (make -f lif_ctrl.mk lif_all in formal).
//
// Pilot scope (docs/02 section 3, Candidate A storage class, reached by
// fallback trigger F1): the synapse array is a flip-flop file (default
// 32 x 32 x 4 b = 4 kb) written through a one-weight-per-cycle load port
// -- no SRAM macro. Since the memory-hardening section below the array
// carries its own SECDED code, so E10 (uncorrectable-word zero
// substitution) IS implemented in this configuration, at exactly the
// 16-weight word granularity the golden model's word_index() defines.
// Every numbered equation of spec section 4 is implemented here. Neuron
// state (V, R) is likewise a flip-flop file and is likewise coded.
// E9 (multi-pass neuron tiling) touches the datapath only
// through cfg_tile_off, added to emitted neuron ids per E5; pass
// sequencing is owned upstream (spec section 9).
//
// Equations implemented (docs/10 section 4, bit-exact):
//   E1  w = sext4(W[a][j])                       4-bit signed decode
//   E2  c = w << S_SYN                           exact, S_SYN in [0, 7],
//       so c in [-1024, +896]: an 11-bit signed intermediate is exact
//   E3  V' = sat16(V + c)                        full-width sum (18-bit
//       signed), then clamp to [-32768, +32767] -- never a two's
//       complement wrap (a wrapped positive overflow would lose a spike)
//   E4  spike iff V' >= THETA (signed compare)   checked AFTER the update,
//       on every non-gated event, including zero contributions
//   E5  on spike: V = V_RESET, R = T_REFR, emit id = TILE_OFF + j
//   E6  leak toward zero by max(|V| >> S_LEAK, 1); the sign never flips;
//       |V| is computed at 16-bit unsigned width (|-32768| = 16'h8000 =
//       32768 is representable); gated by cfg_leak_en, independent of R
//   E7  refractory: R > 0 gates E1..E5 for that (event, neuron) with no
//       state change; TICK decrements R toward zero
//   E8  one command is consumed at a time, neurons are scanned in
//       ascending j, spikes are emitted in scan order: the core is a
//       deterministic function of (state, configuration, weights, input
//       event order); TICK processing emits nothing
//
// Cycle schedule (one neuron per cycle, ascending j, no pipelining):
//
//   S_IDLE  1 cycle minimum between commands. A command is accepted on
//           the clock edge where its valid and ready are both high;
//           priority is state_clr > synaptic event > tick. Debug state
//           writes (dbg_wr_en) and weight loads land here by contract.
//   S_EV    N_NEURONS cycles for a synaptic event: on cycle j the core
//           reads V[j], R[j] and W[axon][j], applies E7 then E1..E5, and
//           writes V[j] / R[j] back on the same edge. A spike enters the
//           1-deep output holding register (out_valid / out_event); while
//           that register is occupied and out_ready is low the scan
//           stalls, adding one cycle per stalled cycle, so backpressure
//           reaches the pipeline and no spike is ever dropped (spec
//           section 7.2).
//   S_TICK  N_NEURONS cycles: on cycle j, E6 leak and E7 countdown for
//           neuron j. Never emits, never stalls (spec section 4.2).
//   S_CLR   N_NEURONS cycles: zero V and R (CTRL.STATE_CLR, spec 11.1).
//   S_SAFE  fault parking state (spec section 11.4). Entered only from an
//           illegal state encoding, i.e. from an upset; latches
//           STATUS.ERR_CFG on the err_cfg output, freezes the neuron
//           state file, accepts no further command, emits nothing new
//           (a spike already held still drains), and is left only by
//           reset (blk_rst_n, which CTRL.SOFT_RST asserts in the pilot).
//           The weight load port is unaffected, like everywhere else --
//           see the w_wr_en bullet of the Contract block.
//
//   Throughput at full output bandwidth: N_NEURONS + 1 cycles per
//   synaptic event or tick (32 + 1 at the pilot default). Latency of the
//   first spike of an event: 1 + (j + 1) cycles for the first spiking
//   neuron j. The scan cost is independent of the event's sparsity --
//   this is the time-multiplexing trade of docs/02 Candidate B, kept
//   here so the pilot datapath is the same datapath.
//
// Output interface is aer_fifo write-side compatible: out_valid -> wr_en,
// out_event -> wr_data, out_ready -> !full. out_event is the frozen
// 16-bit local event word of spec section 7.1:
// {TYPE = 2'b00 SPIKE, 4'b0000 reserved, ID[9:0] = TILE_OFF + j}.
// The holding register is overwritten on the same edge the FIFO samples
// it, so a spike can be emitted every cycle while out_ready holds.
//
// CFG_NEUR / CFG_AXON (spec section 6 and register map 0x20 / 0x24) have
// no port here. This is a deliberate design decision, not an omission,
// and it is restated here because hw/rtl/npu_regbank.v does implement a
// writable, range-validated CFG_NEUR register and exports it on a
// cfg_neur output: in any integration of the two, that output has no
// consumer in this module and the N_NEURONS parameter is authoritative
// for the active neuron count. hw/rtl/pilot_top.v resolves the same
// question the other way round for its own register file -- its
// deviation D2 makes CFG_NEUR read-only and reports N_NEURONS -- so the
// pilot never presents the host with a setting that does nothing. An SoC
// that instantiates npu_regbank in front of this core must do one of the
// two: either tie CFG_NEUR read-only to N_NEURONS as the pilot does, or
// accept that writes to it are ignored by the datapath.
//
// Why the parameter is authoritative: the golden model, which this
// datapath must match bit for bit, carries no runtime active-neuron
// count. n_neurons is fixed at construction, the scan always covers all
// of it, and NetworkRunner models a partial E9 tile as a narrower core
// rather than as a reduced CFG_NEUR. Implementing a runtime CFG_NEUR
// would therefore be RTL with no golden reference. It is not needed for
// E9 correctness in this build: an unused top neuron whose weight column
// is zero and whose state is cleared holds V = 0 forever (leak preserves
// zero), and THETA >= 1 by configuration validation, so it can never
// emit. Software runs a partial tile by zeroing the unused weight
// columns before the pass; test_e9_partial_tile_matches_a_narrower_core
// is the evidence. The cost is scan cycles, not correctness.
//
// Contract (register-block obligations, not re-checked here):
//   - configuration inputs hold golden-validated values (LIFConfig ranges,
//     spec section 6) and are stable while busy is high;
//   - every index port addresses an entry that exists: ev_axon < N_AXONS
//     (the CFG_AXON out-of-range drop and the CNT_AXON_OOR counter live
//     upstream, spec section 6), w_wr_axon < N_AXONS,
//     w_wr_neuron < N_NEURONS and dbg_addr < N_NEURONS. The index widths
//     round up to a power of two, so at a non-power-of-two geometry these
//     ports can encode indices with no array entry behind them, and such
//     an access reads or writes outside the flip-flop file;
//   - cfg_tile_off + N_NEURONS <= 1024 (frozen 10-bit event-word ID
//     field, spec section 9 limitation), so spike_id never wraps;
//   - weight-load writes (w_wr_en) and debug state writes (dbg_wr_en) are
//     issued only while busy is low. The two ports behave differently if
//     that obligation is broken, and the difference is structural:
//       * w_wr_en is NOT interlocked. It sits outside the state machine
//         and commits in any state, S_SAFE included. It cannot corrupt
//         the scan's write-back, because the scan never writes wmem, but
//         a weight write during S_EV to the index the scan is about to
//         read (w_rd_index) changes the value that event integrates --
//         a read-during-write race on one synapse, and the reason the
//         idle-only obligation exists.
//       * dbg_wr_en IS interlocked: the vmem/rmem write lives inside the
//         S_IDLE arm of the case, so it is structurally impossible for a
//         debug write to race the scan's own write-back. The failure
//         mode of a mid-scan debug write is therefore a silently dropped
//         write, not a corrupted neuron.
//   - state_clr is sampled only while the neuron scan is idle. A spike
//     still held in the output register does not block it: the clear runs
//     and the held spike drains normally. Pulses raised during S_EV /
//     S_TICK / S_CLR / S_SAFE are ignored, not queued.
//
// Spec deviation, input event ordering (docs/10 section 4.3 E8 rule 1):
// SPIKE and TICK arrive here on two independent valid/ready channels with
// a fixed SPIKE-over-TICK priority, so the interface cannot express the
// relative arrival order of the two event types. E8 rule 1 requires
// events to be consumed in FIFO arrival order; that ordering is real for
// SPIKEs among themselves (one channel, one command in flight), but a
// TICK that arrived before a SPIKE is overtaken by it if both are
// presented at once. Providing the mechanism in this module would mean a
// single merged command channel carrying the 2-bit TYPE field of spec
// section 7.1, which is a different port list and a change of the
// pilot integration, so it is recorded as a deviation instead.
// Consequence for the host: the source MUST serialize the two channels --
// present at most one of ev_valid / tick_valid at a time, and raise the
// next one only after the previous command has been accepted. Under that
// restriction the interface reproduces E8 rule 1 exactly.
// hw/rtl/pilot_top.v already satisfies it by construction: its dispatcher
// pops one word from a single input FIFO, decodes the TYPE field, and
// drives exactly one of the two valids from the D_ISSUE state, so
// arrival order in that FIFO is the consumption order. A future mesh link
// receiver has the same obligation.
//
// Neuron and weight state after hardware reset is UNDEFINED (spec section
// 3): the V/R/weight flip-flop files are deliberately not on the reset
// net; software issues state_clr and loads weights before enabling
// traffic. Only the control registers reset. The FSM uses a
// Hamming-distance-2 state encoding with default-case recovery to the
// S_SAFE parking state, which latches STATUS.ERR_CFG on the err_cfg
// output, exactly as spec section 11.4 requires; err_cfg is a level
// output for the register block's ERR_CFG sticky bit and is cleared only
// by reset. The three memory files carry their own codes; the check
// storage is not on the reset net either, for the same reason and with
// the same consequence -- it is defined by the first STATE_CLR and the
// first weight load, exactly like the data it covers.
//
// =====================================================================
// MEMORY HARDENING (added after the docs/16 fault-injection campaign)
// =====================================================================
//
// What the campaign measured, at the 8 x 8 pilot geometry, per structure
// [fact, docs/16 sections 3 and 6]:
//
//   structure   FF    SDC rate   rate x FF ("expected silent corruptions")
//   wmem       256      56.2%      144   rank 1
//   vmem       128      91.7%      117   rank 2
//   rmem        32     100.0%       32   rank 3
//
// Those three were the whole residual risk: every structure the pilot
// already claimed to protect held 50 for 50. They are hardened here.
//
// -- 1. Choice per structure, and the arithmetic behind it -------------
//
// The choice is per structure because the cost of a code is set by the
// WORD it covers, not by the array it lives in, and the three arrays
// have very different natural word sizes.
//
//   wmem  SECDED (72,64) over 16 consecutive weights, one codeword per
//         word, reusing the proven hw/rtl/secded_enc.v + secded_dec.v.
//         8 check bits per 64 data bits = 12.5% overhead: +8 FF per 16
//         weights, +32 FF at 8 x 8. Corrects any single-bit upset in the
//         word, detects any double.
//
//   vmem  SECDED (26,20) over the 20-bit neuron state word {R[3:0],
//   rmem  V[15:0]} -- ONE codeword covering both files, not two.
//         6 check bits per neuron = +48 FF at 8 neurons. Corrects any
//         single-bit upset in V, in R or in the check field itself.
//
// The two decisions that are not obvious, stated with their numbers:
//
//   (a) Why 16 weights per codeword rather than per-weight parity.
//       Parity on a 4-bit weight costs 1 FF per 4 = 25% overhead
//       (+64 FF at 8 x 8) and only DETECTS. The (72,64) code costs
//       12.5% (+32 FF) and CORRECTS. The wide word is both cheaper and
//       stronger, and the 16-weight granularity is not a free choice
//       either: it is exactly WEIGHTS_PER_WORD in sw/golden/lif_core.py,
//       so word_index(axon, j) in the golden model names the same word
//       this hardware codes, and E10 becomes expressible against the
//       model rather than against a comment. The reason not to go wider
//       is the read mux, not the code: one codeword must be read whole
//       on every scan cycle.
//
//   (b) Why rmem is not TMR, which is what its 100% SDC rate invites.
//       TMR on rmem costs +64 FF (two extra copies of 32) and protects
//       32 bits: 2.0 added flip-flops per protected bit. Coding V and R
//       together costs 6 check bits per neuron and protects 160 bits:
//       0.3 added flip-flops per protected bit. And the 6 is not a
//       compromise -- a SECDED code over V ALONE (16 data bits) needs
//       5 Hamming checks plus an overall parity bit, which is also 6.
//       So rmem, the structure with the worst per-bit rate in the whole
//       design, is protected at ZERO marginal flip-flop cost by sharing
//       the codeword V had to pay for anyway. That is the cheapest large
//       win available and it is cheaper than the one the campaign's own
//       recommendation named.
//
// Options considered and rejected, with the reason:
//
//   TMR on all three (+832 FF, 72% of the whole design's register count)
//     -- rejected on area, and it buys nothing a SECDED word does not,
//     since the threat model here is one flipped bit.
//   Parity + invalidate on vmem (+8 FF) -- rejected because there is no
//     value to substitute. V IS the neuron's memory; "invalidate" means
//     losing it, so the policy converts an SDC into a detected loss
//     rather than into a correct answer, and the campaign already showed
//     that 24 of 34 state upsets corrupt only the RETAINED state, which
//     is precisely the case a correction fixes and an invalidation does
//     not.
//   Periodic scrubbing alone (hw/rtl/scrub.v) -- rejected as the primary
//     mechanism because scrubbing needs a code to scrub against; it is a
//     way of bounding the accumulation of errors a code can already
//     correct, not a substitute for the code. What this module does get
//     for free is described in section 3 below.
//   Host reload of the weight image (docs/16 section 5.4) -- kept as a
//     complementary policy, not as the mechanism. It bounds wmem
//     corruption by the reload interval and costs no silicon, but it
//     cannot touch vmem or rmem, which have no protected source to be
//     restored from.
//
// -- 2. Transparency ---------------------------------------------------
//
// In the absence of an injected fault this module is bit-for-bit and
// cycle-for-cycle what it was before the hardening, and that is a
// requirement rather than an observation: sw/golden/lif_core.py is the
// frozen specification and hw/tb/test_lif_core_rtl.py runs bit-exact
// lockstep against it. Both codes are systematic and combinational: a
// clean codeword decodes to its own data field with sec = ded = 0, so
// every value the datapath consumes is the value the unhardened module
// consumed, in the same cycle. No pipeline stage was added, no handshake
// changed, no state was added to the FSM. The only new ports are four
// LEVEL outputs (wmem_sec, wmem_ded, state_sec, state_ded); the
// instantiation in hw/rtl/pilot_top.v leaves them unconnected, which is
// legal and which is why this change needs no edit there.
//
// The one behaviour that is new in the fault-free case is a write that
// writes the same value it read (section 3). It changes no observable.
//
// -- 3. Write-back scrubbing, at zero flip-flop cost --------------------
//
// The neuron state file is now written on EVERY cycle the scan visits a
// neuron, including the two cases the unhardened module skipped: a
// refractory-gated neuron under E7, and a TICK on a neuron with R = 0
// and leak disabled. The value written in those cases is the value that
// was read -- after correction. In the fault-free case that is a write
// of the identical word and changes nothing, which is what keeps the
// lockstep exact. After an upset it is a repair: the corrected state and
// its recomputed check field replace the corrupted ones, so a single-bit
// error in vmem or rmem does not merely fail to propagate, it is gone by
// the next event or tick that touches that neuron. This is the scrub
// loop of docs/10 section 11.2 obtained from the existing scan instead
// of from a scrubber, and it costs no flip-flop and no cycle.
//
// wmem does NOT get this, and the difference is worth being exact
// about. The scan never writes wmem, so there is no visit to scrub on.
// The load port is a read-modify-write and it does re-encode the whole
// codeword, so a full weight-image reload -- the mitigation docs/16
// section 5.4 recommends and the only way the pilot's loader writes at
// all -- leaves every word exactly clean. A partial write of one weight
// does not repair the other fifteen; the reasoning, and why splicing
// into decoded data was tried and rejected, is at the load-port
// read-modify-write below.
//
// -- 4. What a double-bit error does -----------------------------------
//
//   wmem   E10, docs/10 section 11.2 and sw/golden/lif_core.py
//          poison_word(): every weight of an uncorrectable word
//          contributes zero for as long as the word stays uncorrectable,
//          and wmem_ded is raised while the scan reads it. Fail-
//          operational, and bit-exact against a golden core built with
//          that word poisoned.
//   vmem   the data field passes through uncorrected and state_ded is
//   rmem   raised. There is no fail-operational substitution for a
//          membrane potential -- any value this module could invent
//          would be a spec deviation with no golden reference -- so the
//          policy is report, not repair. The host's recovery is
//          CTRL.STATE_CLR.
//
// One consequence of the write-back scrub that is stated rather than
// discovered later: an uncorrectable neuron state word is announced on
// the cycle it is read, and the same cycle's write-back re-encodes the
// word around the data it could not repair. So a double error is
// reported ONCE, when it is read, and is part of the neuron's state
// afterwards rather than being reported on every following scan. The
// alternative -- freezing the neuron so the flag keeps firing -- would
// make a two-bit upset stop the datapath, which is a worse failure for a
// fail-operational part than a wrong V. Whichever way, the record is a
// telemetry event and it is the register block's job to keep it.
//
// -- 5. Surviving synthesis --------------------------------------------
//
// This design has already been bitten once by redundancy that synthesis
// could prove equivalent and therefore merged away (hw/rtl/pilot_top.v
// header section 9: three configuration TMR replicas became one bank).
// The structures added here are not replicas -- a check field is not
// equal to anything, so opt_merge has nothing to hash it against -- but
// "not a replica" is an argument, and an argument is not evidence.
// The evidence is sw/tests/test_synthesis_guards.py, which counts
// flip-flop CELLS per structure in the MAPPED netlist of both flows and
// fails if smem, wchk, wmem, vmem or rmem is short of its declared
// width. The specific hazard it is aimed at is stated there: the check
// field is a pure function of the data field in every reachable state,
// so a tool that could reason across sequential state could replace the
// storage with the encoder and leave a decoder that always reports a
// clean word. Nothing in yosys does that today. The test is what says
// so tomorrow.
//
// The check storage is declared as a FLAT packed vector rather than as
// an array, for two reasons that are both about being checkable: yosys
// gives a flat vector a single netname so the guard test can count it
// exactly, and the constant-index generate that assembles the weight
// codewords keeps the 16 nibble reads of one word from becoming 16
// independent address decoders over the whole array.
//
// -- 6. Cost, measured -------------------------------------------------
//
// Flip-flops, counted in the MAPPED sg13g2 netlist of the whole pilot
// (tt_um_melihakbulut_nssoc at 8 x 8, yosys 0.67+146, the pinned
// checkout of tools.mk) [fact]:
//
//   structure          before   after   added
//   wmem  data            256     256       0
//   wchk  check             0      32     +32
//   vmem  data            128     128       0
//   rmem  data             32      32       0
//   smem  check             0      48     +48
//   whole pilot          1155    1235     +80
//
// So 416 of the pilot's flip-flops -- 34% of the design, and all three
// of the campaign's top-ranked structures -- move from unprotected to
// single-error-correcting for 80 added flip-flops, 6.9% of the register
// count.
//
// Cell area, same netlist, `stat -liberty sg13g2_stdcell_typ_1p20V_25C`
// [fact]:
//
//                              before      after     delta
//   tt_um_melihakbulut_nssoc  119,637    140,352   +20,716   +17.3%
//     of which sequential      56,583     60,501    +3,919
//     of which combinational   63,054     79,851   +16,798
//   lif_core standalone        42,066     63,104   +21,037   +50.0%
//
// The cost is combinational, four to one over the flip-flops, and it is
// itemised rather than lumped [fact, per-module `stat` on the same run]:
// secded_dec on the weight read 4,588, secded_enc on the weight write
// 2,177, two lif_state_dec at 1,468 each, one lif_state_enc 595 -- 10,296
// for the codecs -- and about 6,700 of codeword multiplexing and write
// decode inside lif_core. That ratio is the whole reason coding beat
// replication here: TMR would have inverted it.
//
// Against the tile budget of docs/15 section 4.3 [estimate, and labelled
// as one because it scales a measured placed area rather than re-running
// the harden]: the 4x2 shape this pilot is submitted on offers 259,837
// um2 of placement rows, and the measured placed standard-cell area
// before this change was 136,107 um2, 52.4% utilisation. Scaling by the
// synthesis ratio above puts the hardened design near 159,700 um2 and
// 61.5%. The hardening therefore consumes roughly 9% of the 4x2
// placement-row budget and the shape does not change. That is the number
// to re-derive from a real harden before it is quoted as a fact.
//
// Plain Verilog-2005, Icarus-clean.
`default_nettype none

module lif_core #(
    parameter N_NEURONS = 32,  // pilot default (docs/02 Candidate A scale)
    parameter N_AXONS   = 32,  // spec range for both: 1..1024
    // derived index widths, do not override
    parameter NEUR_W = (N_NEURONS <= 1) ? 1 : $clog2(N_NEURONS),
    parameter AXON_W = (N_AXONS   <= 1) ? 1 : $clog2(N_AXONS),
    parameter WIDX_W = (N_AXONS * N_NEURONS <= 1)
                       ? 1 : $clog2(N_AXONS * N_NEURONS)
) (
    input  wire        clk,
    input  wire        rst_n,

    // configuration (golden LIFConfig ranges, stable while busy)
    input  wire [15:0] cfg_thresh,      // THETA, signed, [1, +32767]
    input  wire [15:0] cfg_vreset,      // V_RESET, signed, < THETA
    input  wire [3:0]  cfg_leak_shift,  // S_LEAK, [0, 15]
    input  wire [2:0]  cfg_syn_shift,   // S_SYN, [0, 7]
    input  wire [3:0]  cfg_refr,        // T_REFR, [0, 15]
    input  wire        cfg_leak_en,     // CFG_FLAGS.LEAK_EN
    input  wire [9:0]  cfg_tile_off,    // PASS_TILE_OFF (spec section 9)

    // control
    input  wire        state_clr,       // CTRL.STATE_CLR pulse (idle only)
    output wire        busy,            // command or emission in flight
    output wire        err_cfg,         // STATUS.ERR_CFG, latched in S_SAFE
                                        // (spec section 11.4); level output,
                                        // sticky until reset

    // Memory ECC telemetry (header section MEMORY HARDENING). Four level
    // outputs, one pair per coded file, asserted for the cycle the scan
    // reads a word that needed correcting or could not be corrected.
    // Not sticky and not counted here: the docs/08 section 2.3
    // fault-visibility convention makes counting the register block's
    // job, exactly as tmr_voter.v's mismatch output does. Leaving them
    // unconnected is legal and is what hw/rtl/pilot_top.v does today;
    // wiring them to CNT_SEC / CNT_DED and the SEC / DED pins is the
    // integration step that makes these corrections visible in
    // telemetry.
    output wire        wmem_sec,        // synapse word: single-bit corrected
    output wire        wmem_ded,        // synapse word: uncorrectable (E10)
    output wire        state_sec,       // neuron state word: corrected
    output wire        state_ded,       // neuron state word: uncorrectable

    // synapse weight load port (FF array, one weight per cycle, idle only)
    input  wire              w_wr_en,
    input  wire [AXON_W-1:0] w_wr_axon,
    input  wire [NEUR_W-1:0] w_wr_neuron,
    input  wire [3:0]        w_wr_data,   // 4-bit signed code (E1)

    // AER input: synaptic events and ticks
    input  wire              ev_valid,
    input  wire [AXON_W-1:0] ev_axon,
    output wire              ev_ready,
    input  wire              tick_valid,
    output wire              tick_ready,

    // AER spike output, aer_fifo write-side compatible
    output wire        out_valid,
    output reg  [15:0] out_event,
    input  wire        out_ready,

    // debug/state port (N_ADDR/N_DATA model; combinational read,
    // write lands in IDLE only)
    input  wire [NEUR_W-1:0] dbg_addr,
    output wire [15:0]       dbg_v,
    output wire [3:0]        dbg_r,
    input  wire              dbg_wr_en,
    input  wire [15:0]       dbg_wr_v,
    input  wire [3:0]        dbg_wr_r
);

    // Elaboration guard, aer_fifo house style: an out-of-range geometry
    // takes this branch and references a module that deliberately does not
    // exist, so elaboration fails with the module name as the message in
    // every tool (Icarus, Yosys). The 1..1024 bound is spec section 2;
    // the upper end is the 10-bit event-word ID space (spec section 7.1).
    generate
        if (N_NEURONS < 1 || N_NEURONS > 1024 ||
            N_AXONS   < 1 || N_AXONS   > 1024) begin : g_bad_geometry
            ERROR_lif_core_N_NEURONS_and_N_AXONS_must_be_in_1_to_1024 guard ();
        end
    endgenerate

    // FSM state encoding (spec section 11.4). All five codewords are the
    // even-parity words of a 4-bit vector, so every pair is at Hamming
    // distance >= 2 and every single-bit upset lands on an odd-parity word
    // -- an encoding no legal transition can produce. Those eight illegal
    // words, and the three unused even-parity words, all take the default
    // arm, which enters S_SAFE and latches err_cfg.
    localparam [3:0] S_IDLE = 4'b0000,
                     S_EV   = 4'b0011,
                     S_TICK = 4'b0101,
                     S_CLR  = 4'b0110,
                     S_SAFE = 4'b1001;

    reg [3:0]        state;
    reg              err_cfg_r;  // STATUS.ERR_CFG, set on entry to S_SAFE
    reg [NEUR_W-1:0] jj;         // neuron scan index (E8 ascending order)
    reg [AXON_W-1:0] ev_axon_r;  // latched axon id of the event in flight
    reg              out_pend;   // output holding register occupied

    // -----------------------------------------------------------------
    // Coded memory files (header section MEMORY HARDENING)
    // -----------------------------------------------------------------
    // Geometry of the synapse code. One SECDED (72,64) codeword covers
    // WPW = 16 consecutive weights of the axon-major linear index, which
    // is WEIGHTS_PER_WORD and word_index() in sw/golden/lif_core.py. A
    // geometry whose synapse count is not a multiple of 16 leaves the top
    // of the last codeword unpopulated; those nibbles are tied to zero in
    // the codeword on both the encode and the decode side, so they never
    // exist as storage and never perturb a syndrome.
    localparam integer N_SYN   = N_AXONS * N_NEURONS;
    localparam integer WPW     = 16;                       // weights/word
    localparam integer N_WWORD = (N_SYN + WPW - 1) / WPW;  // codewords
    localparam integer WW_W    = (N_WWORD <= 1) ? 1 : $clog2(N_WWORD);
    // Neuron state code: extended Hamming (26,20) over {R[3:0], V[15:0]}.
    localparam integer ST_D = 20;  // data bits per neuron
    localparam integer ST_C = 6;   // check bits per neuron

    // State and weight flip-flop files -- deliberately not on the reset
    // net (spec section 3: post-reset state is UNDEFINED until STATE_CLR).
    // wmem / vmem / rmem keep their pre-hardening shape and name: they are
    // the arrays hw/tb/test_fi_campaign.py deposits upsets into, and a
    // fault map is worth nothing if the target names move under it.
    reg [3:0]  wmem [0:N_SYN-1];              // axon-major (spec section 5)
    reg [15:0] vmem [0:N_NEURONS-1];
    reg [3:0]  rmem [0:N_NEURONS-1];
    // Check fields, flat packed rather than arrays -- see header section 5.
    reg [8*N_WWORD-1:0]    wchk;   // 8 SECDED check bits per 16 weights
    reg [ST_C*N_NEURONS-1:0] smem; // 6 check bits per neuron state word

    // Read port of the scan. Axon-major linear index, spec section 5.
    wire [WIDX_W-1:0] w_rd_index = ev_axon_r * N_NEURONS + jj;
    wire [WIDX_W-1:0] w_wr_index = w_wr_axon * N_NEURONS + w_wr_neuron;

    // Split each linear synapse index into (codeword, nibble-in-codeword).
    // The 4-bit widening is what keeps the nibble select legal at
    // geometries with fewer than 16 synapses, where WIDX_W < 4.
    wire [WIDX_W+3:0] w_rd_idx_x = {4'd0, w_rd_index};
    wire [WIDX_W+3:0] w_wr_idx_x = {4'd0, w_wr_index};
    wire [3:0]        w_rd_nib   = w_rd_idx_x[3:0];
    wire [3:0]        w_wr_nib   = w_wr_idx_x[3:0];
    wire [WW_W-1:0]   w_rd_word;
    wire [WW_W-1:0]   w_wr_word;
    generate
        if (N_WWORD <= 1) begin : g_single_wword
            assign w_rd_word = {WW_W{1'b0}};
            assign w_wr_word = {WW_W{1'b0}};
        end else begin : g_many_wwords
            assign w_rd_word = w_rd_idx_x[WW_W+3:4];
            assign w_wr_word = w_wr_idx_x[WW_W+3:4];
        end
    endgenerate

    // Every codeword's 64-bit data field, assembled once with CONSTANT
    // array indices so the sixteen nibble taps of a word cost no address
    // decode at all; the only mux is the codeword select below.
    wire [64*N_WWORD-1:0] w_data_all;
    genvar gw, gk;
    generate
        for (gw = 0; gw < N_WWORD; gw = gw + 1) begin : g_wword
            for (gk = 0; gk < WPW; gk = gk + 1) begin : g_wnib
                if (gw * WPW + gk < N_SYN) begin : g_live
                    assign w_data_all[gw*64 + gk*4 +: 4] = wmem[gw*WPW + gk];
                end else begin : g_pad
                    assign w_data_all[gw*64 + gk*4 +: 4] = 4'd0;
                end
            end
        end
    endgenerate

    // Scan-side decode. One codeword in, sixteen corrected weights out,
    // of which the scan consumes one.
    wire [63:0] w_rd_code_d = w_data_all[{w_rd_word, 6'd0} +: 64];
    wire [7:0]  w_rd_code_c = wchk[{w_rd_word, 3'd0} +: 8];
    wire [63:0] w_rd_fixed;
    wire [7:0]  w_rd_syn;
    wire        w_rd_sec, w_rd_ded;
    secded_dec u_w_rd_dec (
        .code_in  ({w_rd_code_c, w_rd_code_d}),
        .data_out (w_rd_fixed),
        .syndrome (w_rd_syn),
        .sec      (w_rd_sec),
        .ded      (w_rd_ded)
    );

    // (E10, docs/10 section 11.2) An uncorrectable word contributes zero
    // for every one of its sixteen weights, fail-operational, matching
    // LIFCore.poison_word() in sw/golden/lif_core.py exactly.
    wire [3:0] w_code = w_rd_ded ? 4'd0
                                 : w_rd_fixed[{w_rd_nib, 2'd0} +: 4];

    // Load-port read-modify-write: take the addressed codeword's data
    // field as it stands, splice the new nibble in, re-encode. The result
    // is a codeword with a ZERO syndrome -- the write leaves the word
    // exactly consistent, not merely correctable.
    //
    // The alternative, splicing into the DECODED data so that a
    // single-bit error elsewhere in the word is repaired by the write,
    // was built and rejected on two grounds. The first is decisive and
    // is not an area argument: the decoder makes the whole codeword
    // depend on the check field, so during a word's first load -- when
    // fifteen of its sixteen nibbles have not been written yet and the
    // check field is still undefined -- the re-encode feeds its own
    // undefined output back in and the word never becomes defined at
    // all. Splicing raw breaks that loop; the word is defined the moment
    // its sixteenth nibble lands, which is what the unhardened module
    // did too. The second is that it costs a second secded_dec.
    //
    // What is given up, stated plainly: a single-bit error already
    // present in one of the fifteen nibbles the write does not touch is
    // absorbed into the accepted data instead of being corrected, so
    // that weight is silently wrong afterwards and no flag fires. That
    // is no worse than the unhardened module, it cannot happen during a
    // full-word or full-image load (every nibble is overwritten), and
    // the pilot's loader only ever writes whole 64-bit words through the
    // ECC staging register. A design that gains a partial-word update
    // path should revisit this.
    reg [63:0] w_wr_merged;
    always @* begin
        w_wr_merged = w_data_all[{w_wr_word, 6'd0} +: 64];
        w_wr_merged[{w_wr_nib, 2'd0} +: 4] = w_wr_data;
    end

    wire [7:0]  w_wr_chk;
    wire [71:0] w_wr_code;
    secded_enc u_w_wr_enc (
        .data_in   (w_wr_merged),
        .check_out (w_wr_chk),
        .code_out  (w_wr_code)
    );

    // Neuron state decode, scan port and debug port. Two decoders because
    // the two addresses are independent; the debug port must present the
    // corrected value or a host reading the state file back would see the
    // upset this module just masked.
    wire [ST_C-1:0] st_scan_c = smem[jj * ST_C +: ST_C];
    wire [ST_D-1:0] st_scan_d;
    wire            st_scan_sec, st_scan_ded;
    lif_state_dec u_st_scan_dec (
        .code_in  ({st_scan_c, rmem[jj], vmem[jj]}),
        .data_out (st_scan_d),
        .syndrome (),
        .sec      (st_scan_sec),
        .ded      (st_scan_ded)
    );
    wire [15:0] v_cur = st_scan_d[15:0];
    wire [3:0]  r_cur = st_scan_d[19:16];

    wire [ST_C-1:0] st_dbg_c = smem[dbg_addr * ST_C +: ST_C];
    wire [ST_D-1:0] st_dbg_d;
    wire            st_dbg_sec, st_dbg_ded;
    lif_state_dec u_st_dbg_dec (
        .code_in  ({st_dbg_c, rmem[dbg_addr], vmem[dbg_addr]}),
        .data_out (st_dbg_d),
        .syndrome (),
        .sec      (st_dbg_sec),
        .ded      (st_dbg_ded)
    );

    // (E1)(E2) signed decode and exact left shift. c in [-1024, +896]
    // fits an 11-bit signed value exactly at every legal (w, S_SYN), so
    // the shift cannot lose a bit: -8 << 7 = -1024 = 11'b100_0000_0000
    // and +7 << 7 = +896.
    wire signed [10:0] w_sext  = {{7{w_code[3]}}, w_code};
    wire signed [10:0] contrib = w_sext <<< cfg_syn_shift;

    // (E3) full-width signed sum, then clamp -- never a two's complement
    // wrap. 16-bit V plus 11-bit c needs 17 bits; 18 is carried so the
    // comparison constants below are unambiguous.
    wire signed [17:0] v_sum = $signed(v_cur) + contrib;
    wire [15:0] v_sat = (v_sum > 18'sd32767)  ? 16'h7FFF :
                        (v_sum < -18'sd32768) ? 16'h8000 : v_sum[15:0];

    // (E4) signed compare on the post-update, post-saturation value.
    wire spike = $signed(v_sat) >= $signed(cfg_thresh);

    // (E6) magnitude at 16-bit unsigned width (|-32768| = 16'h8000 =
    // 32768), logical shift, minimum step 1, applied toward zero so the
    // sign never flips. v_cur == 0 is a special case: without it the
    // minimum step would push zero to -1.
    wire [15:0] v_mag    = v_cur[15] ? (~v_cur + 16'd1) : v_cur;
    wire [15:0] leak_raw = v_mag >> cfg_leak_shift;
    wire [15:0] leak_m   = (leak_raw == 16'd0) ? 16'd1 : leak_raw;
    wire signed [17:0] v_leak_sum =
        v_cur[15] ? ($signed(v_cur) + $signed({2'b00, leak_m}))
                  : ($signed(v_cur) - $signed({2'b00, leak_m}));
    // |leak_m| <= |v_cur| for v_cur != 0, so the result stays inside the
    // 16-bit signed range and the truncation below is exact.
    wire [15:0] v_leak = (v_cur == 16'd0) ? 16'd0 : v_leak_sum[15:0];

    // (E5)(E9) emitted id; the caller guarantees TILE_OFF + j fits 10 bits.
    // NEUR_W <= 10 by the geometry guard, so jj zero-extends into the
    // 10-bit addition context without truncation.
    wire [9:0] spike_id = cfg_tile_off + jj;

    wire last_j    = (jj == N_NEURONS - 1);
    wire wr_accept = out_pend && out_ready;   // FIFO takes the held spike
    wire can_go    = !out_pend || out_ready;  // scan may process a neuron

    assign out_valid  = out_pend;
    assign busy       = (state != S_IDLE) || out_pend;
    assign err_cfg    = err_cfg_r;
    // Command arbitration, one grant per cycle, priority
    // state_clr > synaptic event > tick (E8 rule 1 at the interface,
    // spec section 4.3). Both readys are qualified by S_IDLE, so no
    // second command is ever accepted before the one in flight retires,
    // and S_SAFE accepts nothing.
    assign ev_ready   = (state == S_IDLE) && !state_clr;
    assign tick_ready = (state == S_IDLE) && !state_clr && !ev_valid;

    assign dbg_v = st_dbg_d[15:0];
    assign dbg_r = st_dbg_d[19:16];

    // ECC telemetry, qualified by the cycle the scan actually consumes
    // the word so an idle decoder cannot report on a stale address.
    // A refractory neuron's weight is never consumed (E7), so a
    // correction in a word only that neuron would have read is not
    // announced -- which is correct: nothing read it.
    wire w_rd_used  = (state == S_EV) && can_go && (r_cur == 4'd0);
    wire st_rd_used = ((state == S_EV) && can_go) || (state == S_TICK);
    assign wmem_sec  = w_rd_sec    && w_rd_used;
    assign wmem_ded  = w_rd_ded    && w_rd_used;
    assign state_sec = st_scan_sec && st_rd_used;
    assign state_ded = st_scan_ded && st_rd_used;

    // -----------------------------------------------------------------
    // Neuron state write port
    // -----------------------------------------------------------------
    // One writer per cycle, selected by the state: the debug port in
    // S_IDLE, the scan in S_EV / S_TICK / S_CLR, nobody in S_SAFE or in
    // any illegal encoding -- which is what freezes the state file there
    // (spec section 11.4), exactly as the per-arm writes it replaces did.
    //
    // The scan arms write on every visited neuron, including the two
    // cases the unhardened module skipped (a refractory neuron under E7,
    // and a TICK on a neuron with R = 0 and leak off). The value written
    // there is the value that was read, after correction: identical in
    // the fault-free case, a repair after an upset. Header section 3.
    reg              st_we;
    reg [NEUR_W-1:0] st_addr;
    reg [15:0]       st_v;
    reg [3:0]        st_r;

    always @* begin
        st_we   = 1'b0;
        st_addr = jj;
        st_v    = v_cur;
        st_r    = r_cur;
        case (state)
            S_IDLE: if (dbg_wr_en) begin
                st_we   = 1'b1;
                st_addr = dbg_addr;
                st_v    = dbg_wr_v;
                st_r    = dbg_wr_r;
            end
            S_EV: if (can_go) begin
                st_we = 1'b1;
                if (r_cur == 4'd0) begin    // (E7) R > 0 gates E1..E5
                    if (spike) begin        // (E4) after the update
                        st_v = cfg_vreset;  // (E5)
                        st_r = cfg_refr;    // (E5)
                    end else begin
                        st_v = v_sat;       // (E3)
                    end
                end
            end
            S_TICK: begin
                st_we = 1'b1;
                if (r_cur != 4'd0) st_r = r_cur - 4'd1;   // (E7)
                if (cfg_leak_en)   st_v = v_leak;         // (E6)
            end
            S_CLR: begin                                  // spec 11.1
                st_we = 1'b1;
                st_v  = 16'd0;
                st_r  = 4'd0;
            end
            default: ;   // S_SAFE and every illegal encoding: file frozen
        endcase
    end

    wire [ST_C-1:0] st_wr_chk;
    lif_state_enc u_st_enc (
        .data_in   ({st_r, st_v}),
        .check_out (st_wr_chk)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state     <= S_IDLE;
            err_cfg_r <= 1'b0;
            jj        <= {NEUR_W{1'b0}};
            ev_axon_r <= {AXON_W{1'b0}};
            out_pend  <= 1'b0;
            out_event <= 16'd0;
        end else begin
            // Weight load port. Independent of the FSM and idle-only by
            // contract; the scan never writes wmem, so there is no
            // structural conflict, only the contract-level race noted in
            // the header. The check field of the addressed codeword is
            // recomputed over the CORRECTED data with the new nibble
            // spliced in, so the write leaves a consistent codeword
            // whether or not the word already carried an error.
            if (w_wr_en) begin
                wmem[w_wr_index]              <= w_wr_data;
                wchk[{w_wr_word, 3'd0} +: 8]  <= w_wr_chk;
            end

            // Neuron state file. Data and check field are written
            // together, always -- there is no path that updates one
            // without the other, which is the invariant the decoders
            // depend on.
            if (st_we) begin
                vmem[st_addr]                  <= st_v;
                rmem[st_addr]                  <= st_r;
                smem[st_addr * ST_C +: ST_C]   <= st_wr_chk;
            end

            // The held spike leaves for the FIFO on this edge. A spike
            // emitted by the scan below re-asserts out_pend and overwrites
            // out_event in the same edge; the FIFO samples the old word,
            // so the two never collide.
            if (wr_accept)
                out_pend <= 1'b0;

            case (state)
                S_IDLE: begin
                    jj <= {NEUR_W{1'b0}};
                    if (state_clr)
                        state <= S_CLR;
                    else if (ev_valid) begin
                        ev_axon_r <= ev_axon;
                        state     <= S_EV;
                    end else if (tick_valid)
                        state <= S_TICK;
                end

                S_EV: begin
                    if (can_go) begin
                        // (E7) R > 0 gates E1..E5; (E4) checked after the
                        // update; (E5) emits. The state write itself is
                        // in the st_we block above.
                        if ((r_cur == 4'd0) && spike) begin
                            out_pend  <= 1'b1;               // (E5) emit
                            out_event <= {2'b00, 4'b0000, spike_id};
                        end
                        jj <= jj + 1'b1;
                        if (last_j) begin
                            jj    <= {NEUR_W{1'b0}};
                            state <= S_IDLE;
                        end
                    end
                end

                S_TICK: begin
                    jj <= jj + 1'b1;
                    if (last_j) begin
                        jj    <= {NEUR_W{1'b0}};
                        state <= S_IDLE;
                    end
                end

                S_CLR: begin                                     // spec 11.1
                    jj <= jj + 1'b1;
                    if (last_j) begin
                        jj    <= {NEUR_W{1'b0}};
                        state <= S_IDLE;
                    end
                end

                // Spec section 11.4: a corrupted encoding does not resume
                // silently. The core parks in S_SAFE, latches ERR_CFG for
                // the host, and accepts nothing further (both readys are
                // low outside S_IDLE, so no event is consumed and lost).
                // The neuron state file is frozen: st_we is asserted only
                // from the S_IDLE / S_EV / S_TICK / S_CLR arms of the
                // write-port decode above, and S_SAFE selects none of
                // them. The weight load port is outside the case and is
                // not frozen, in this state or any other. A spike already
                // in the output holding register still drains, because
                // that transfer is outside the case -- it is a validly
                // computed spike and dropping it would itself lose an
                // event.
                S_SAFE: begin
                    state     <= S_SAFE;
                    err_cfg_r <= 1'b1;
                end

                default: begin             // HD-2 corruption recovery
                    state     <= S_SAFE;
                    err_cfg_r <= 1'b1;
                end
            endcase
        end
    end

    // Deliberately unread bits, sunk so lint and synthesis agree that
    // they are unused rather than accidentally dropped. The debug-port
    // decoder's flags are not exported: a host reading the state file
    // back compares it against its own image, and the scan port already
    // announces every correction the datapath acted on.
    wire _unused = &{1'b0, w_rd_syn, w_wr_code, st_dbg_sec, st_dbg_ded,
                     1'b0};

// Two property sets, one at a time. They model different faults and want
// different starting states -- the control set is rooted at reset with a
// legal FSM encoding, the memory set starts from a stored codeword that
// carries an injected error -- so mixing them would leave the memory
// tasks carrying the control invariants as extra proof burden for no
// extra coverage. formal/lif_ctrl.sby selects the first,
// formal/lif_mem.sby the second.
`ifdef FORMAL
`ifdef LIF_MEM_FORMAL
`include "lif_mem_props.v"
`else
`include "lif_ctrl_props.v"
`endif
`endif

endmodule

// =====================================================================
// lif_state_enc / lif_state_dec: SECDED (26, 20) for the neuron state
// =====================================================================
//
// One codeword per neuron covers the whole 20-bit state word
// {R[3:0], V[15:0]}, so the refractory counter -- the structure with the
// worst measured per-bit silent-corruption rate in the design, 100% in
// docs/16 section 3 -- rides for free on the check bits the membrane
// potential had to pay for anyway. See the MEMORY HARDENING section of
// the lif_core header for the cost arithmetic and for why this is not
// TMR.
//
// Why these modules are in this file rather than in one of their own.
// hw/rtl/lif_core.v is named in six independent build descriptions
// (hw/tb/Makefile.lif, Makefile.pilot, Makefile.fi, hw/fpga/Makefile,
// hw/openlane/*/config.json and formal/lif_ctrl.sby) and a seventh in
// sw/tests/test_synthesis_guards.py. A new file would have to be added
// to all of them or the design would fail to elaborate in whichever was
// missed. hw/rtl/pilot_top.v carries pilot_cfg_bank the same way and for
// the same reason.
//
// The code. Extended Hamming: five Hamming check bits over the 20 data
// bits, plus one overall-parity bit, giving minimum distance 4 --
// single-error correcting and double-error detecting. The (72,64) Hsiao
// code of secded_enc.v is not used here because at 20 data bits the
// Hsiao construction saves nothing: both need six check bits, and the
// extended-Hamming syndrome is a position index, which is smaller to
// decode than 26 column comparisons.
//
// Construction, normative and shared by both modules below. Number the
// code positions 1..25 in the classical Hamming order. The five check
// positions are the powers of two (1, 2, 4, 8, 16); the remaining 20 are
// the data positions, in ascending order, and they are exactly 20 --
// which is why 20 is the natural data width for a 5-bit Hamming
// syndrome:
//
//   data bit j  0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19
//   position    3  5  6  7  9 10 11 12 13 14 15 17 18 19 20 21 22 23 24 25
//
// H_MASK[i] below is the 20-bit mask of the data bits whose position has
// bit i set, i.e. the i-th Hamming parity group. The masks are derived
// from that table and nothing else; sw/tests and formal/lif_mem.sby both
// re-derive the same code independently and would fail on a typo.
//
// Codeword layout, systematic and matching secded_enc.v's convention
// (data low, check high):
//
//   code[19:0]   data field, data bit j at bit j
//   code[24:20]  the five Hamming check bits, check i at bit 20 + i
//   code[25]     overall parity, chosen so ^code == 0 for a clean word
//
// Decode rules:
//
//   ^code == 0 and syndrome == 0     clean word, no flag
//   ^code == 1                       an odd number of bits is wrong. If
//                                    the syndrome names a code position
//                                    that bit is flipped back and sec is
//                                    raised; a syndrome of zero means the
//                                    overall-parity bit itself took the
//                                    hit and the data is already right.
//                                    A syndrome of 26..31 names no
//                                    position -- it takes at least three
//                                    errors to produce one -- and is
//                                    reported uncorrectable rather than
//                                    miscorrected.
//   ^code == 0 and syndrome != 0     an even, nonzero number of bits is
//                                    wrong: ded, never corrected.
//
// So sec means "corrected", not merely "odd parity", exactly as in
// secded_dec.v. Purely combinational, no state, no clock: a clean
// codeword decodes to its own data field in the same cycle, which is
// what makes the hardening invisible to the golden-model lockstep.
//
// Plain Verilog-2005, Icarus-clean.
`default_nettype none

module lif_state_enc #(
    parameter DATA_W  = 20,  // fixed by the 20-bit state word, do not override
    parameter CHECK_W = 6
) (
    input  wire [19:0] data_in,
    output wire [5:0]  check_out
);

    // Elaboration guard, aer_fifo house style: a build that overrides the
    // widths references a module that deliberately does not exist, so it
    // fails at elaboration with the reason in the message.
    generate
        if (DATA_W != 20 || CHECK_W != 6) begin : g_bad_width
            ERROR_lif_state_enc_is_fixed_at_26_20 guard ();
        end
    endgenerate

    localparam [19:0] H_MASK0 = 20'hAAD5B;  // positions with bit 0 set
    localparam [19:0] H_MASK1 = 20'h3366D;  // ... bit 1
    localparam [19:0] H_MASK2 = 20'h3C78E;  // ... bit 2
    localparam [19:0] H_MASK3 = 20'hC07F0;  // ... bit 3
    localparam [19:0] H_MASK4 = 20'hFF800;  // ... bit 4

    wire [4:0] ham;
    assign ham[0] = ^(data_in & H_MASK0);
    assign ham[1] = ^(data_in & H_MASK1);
    assign ham[2] = ^(data_in & H_MASK2);
    assign ham[3] = ^(data_in & H_MASK3);
    assign ham[4] = ^(data_in & H_MASK4);

    // The overall-parity bit closes the codeword: ^{check_out, data_in}
    // is zero for every clean word, which is the distance-4 property the
    // double-error detection rests on.
    assign check_out = {^{ham, data_in}, ham};

endmodule

module lif_state_dec #(
    parameter DATA_W  = 20,  // fixed by the 20-bit state word, do not override
    parameter CHECK_W = 6
) (
    input  wire [25:0] code_in,
    output wire [19:0] data_out,
    output wire [5:0]  syndrome,  // {overall parity, 5-bit Hamming syndrome}
    output wire        sec,       // single-bit error corrected
    output wire        ded        // uncorrectable, detected
);

    generate
        if (DATA_W != 20 || CHECK_W != 6) begin : g_bad_width
            ERROR_lif_state_dec_is_fixed_at_26_20 guard ();
        end
    endgenerate

    // Identical to lif_state_enc; each module stays self-contained and
    // hand-auditable, the same way secded_enc.v and secded_dec.v each
    // carry their own copy of the H matrix. A divergence between the two
    // breaks formal/lif_mem.sby, which composes them, immediately.
    localparam [19:0] H_MASK0 = 20'hAAD5B;
    localparam [19:0] H_MASK1 = 20'h3366D;
    localparam [19:0] H_MASK2 = 20'h3C78E;
    localparam [19:0] H_MASK3 = 20'hC07F0;
    localparam [19:0] H_MASK4 = 20'hFF800;

    wire [19:0] data_raw = code_in[19:0];
    wire [4:0]  ham_raw  = code_in[24:20];

    wire [4:0] ham_calc;
    assign ham_calc[0] = ^(data_raw & H_MASK0);
    assign ham_calc[1] = ^(data_raw & H_MASK1);
    assign ham_calc[2] = ^(data_raw & H_MASK2);
    assign ham_calc[3] = ^(data_raw & H_MASK3);
    assign ham_calc[4] = ^(data_raw & H_MASK4);

    wire [4:0] syn = ham_calc ^ ham_raw;
    wire       par = ^code_in;          // zero for every clean codeword

    assign syndrome = {par, syn};

    // Position view of the same table: data bit j is identified by a
    // syndrome equal to its Hamming position. The positions are distinct
    // and none of them is a power of two, so at most one bit of corr_mask
    // is ever set and it can never collide with a check-bit syndrome.
    wire [19:0] corr_mask;
    genvar j;
    generate
        for (j = 0; j < 20; j = j + 1) begin : g_position
            wire [4:0] pos = {H_MASK4[j], H_MASK3[j], H_MASK2[j],
                              H_MASK1[j], H_MASK0[j]};
            assign corr_mask[j] = (syn == pos);
        end
    endgenerate

    wire data_hit  = |corr_mask;                        // a data position
    wire check_hit = (syn != 5'd0) && ((syn & (syn - 5'd1)) == 5'd0);
                                                        // a check position
    wire ovp_hit   = (syn == 5'd0);                     // the parity bit

    // A syndrome of 26..31 names no code position at all; it needs at
    // least three errors to appear and is degraded to "uncorrectable"
    // rather than allowed to miscorrect.
    wire correctable = data_hit || check_hit || ovp_hit;

    assign sec = par && correctable;
    assign ded = (!par && (syn != 5'd0)) || (par && !correctable);

    // A flipped check or parity bit needs no data repair; the flag still
    // fires, so a correction is never silent.
    assign data_out = sec ? (data_raw ^ corr_mask) : data_raw;

endmodule

`default_nettype wire
