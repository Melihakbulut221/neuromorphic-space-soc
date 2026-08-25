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
// -- no SRAM macro, therefore no ECC path. E10 (uncorrectable-word zero
// substitution) has no hardware to attach to in this configuration and
// returns with the SRAM-macro build; every other numbered equation of
// spec section 4 is implemented here. Neuron state (V, R) is likewise a
// flip-flop file. E9 (multi-pass neuron tiling) touches the datapath only
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
// by reset.
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

    // State and weight flip-flop files -- deliberately not on the reset
    // net (spec section 3: post-reset state is UNDEFINED until STATE_CLR).
    reg [3:0]  wmem [0:N_AXONS*N_NEURONS-1];  // axon-major (spec section 5)
    reg [15:0] vmem [0:N_NEURONS-1];
    reg [3:0]  rmem [0:N_NEURONS-1];

    // Read port of the scan. Axon-major linear index, spec section 5.
    wire [WIDX_W-1:0] w_rd_index = ev_axon_r * N_NEURONS + jj;
    wire [WIDX_W-1:0] w_wr_index = w_wr_axon * N_NEURONS + w_wr_neuron;

    wire [15:0] v_cur  = vmem[jj];
    wire [3:0]  r_cur  = rmem[jj];
    wire [3:0]  w_code = wmem[w_rd_index];

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

    assign dbg_v = vmem[dbg_addr];
    assign dbg_r = rmem[dbg_addr];

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
            // the header.
            if (w_wr_en)
                wmem[w_wr_index] <= w_wr_data;

            // The held spike leaves for the FIFO on this edge. A spike
            // emitted by the scan below re-asserts out_pend and overwrites
            // out_event in the same edge; the FIFO samples the old word,
            // so the two never collide.
            if (wr_accept)
                out_pend <= 1'b0;

            case (state)
                S_IDLE: begin
                    jj <= {NEUR_W{1'b0}};
                    if (dbg_wr_en) begin
                        vmem[dbg_addr] <= dbg_wr_v;
                        rmem[dbg_addr] <= dbg_wr_r;
                    end
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
                        if (r_cur == 4'd0) begin  // (E7) R > 0 gates E1..E5
                            if (spike) begin      // (E4) after the update
                                vmem[jj]  <= cfg_vreset;         // (E5)
                                rmem[jj]  <= cfg_refr;           // (E5)
                                out_pend  <= 1'b1;               // (E5) emit
                                out_event <= {2'b00, 4'b0000, spike_id};
                            end else begin
                                vmem[jj] <= v_sat;               // (E3)
                            end
                        end
                        jj <= jj + 1'b1;
                        if (last_j) begin
                            jj    <= {NEUR_W{1'b0}};
                            state <= S_IDLE;
                        end
                    end
                end

                S_TICK: begin
                    if (r_cur != 4'd0)                           // (E7)
                        rmem[jj] <= r_cur - 4'd1;
                    if (cfg_leak_en)                             // (E6)
                        vmem[jj] <= v_leak;
                    jj <= jj + 1'b1;
                    if (last_j) begin
                        jj    <= {NEUR_W{1'b0}};
                        state <= S_IDLE;
                    end
                end

                S_CLR: begin                                     // spec 11.1
                    vmem[jj] <= 16'd0;
                    rmem[jj] <= 4'd0;
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
                // The neuron state file is frozen: every vmem/rmem write
                // in this module lives inside an S_EV / S_TICK / S_CLR /
                // S_IDLE arm, so none of them can fire here. The weight
                // load port is outside the case and is not frozen, in
                // this state or any other. A spike already in the output
                // holding register still drains, because that transfer is
                // outside the case -- it is a validly computed spike and
                // dropping it would itself lose an event.
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

`ifdef FORMAL
`include "lif_ctrl_props.v"
`endif

endmodule

`default_nettype wire
