// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// NPU register bank: the configuration, status and observability register
// file of one NPU node. It implements regmap/regmap.yaml exactly, through
// the generated header hw/rtl/npu_regs.vh -- every address, reset value and
// field position below comes from that header, never from a hand-copied
// literal. The one deliberate exception is the CFG_NEUR / CFG_AXON reset
// value, which docs/10 section 6 gives symbolically and which therefore
// comes from the N_NEURONS / N_AXONS parameters, cross-checked against the
// generated literal by an elaboration guard (C8).
// Normative register list: docs/10-npu-mvp-spec.md section 10.
//
// ---------------------------------------------------------------------
// 1. Bus contract (single-beat valid/ready memory-mapped slave)
// ---------------------------------------------------------------------
//
// Request channel:
//   bus_req_valid / bus_req_ready   handshake, one transaction per
//                                   accepting edge
//   bus_req_write                   1 = write, 0 = read
//   bus_req_addr[11:0]              byte offset inside the 4 KB node window
//   bus_req_wdata[31:0]             write data, word granularity
// Response channel:
//   bus_rsp_valid                   exactly one cycle per accepted
//                                   transaction, on the next clock edge
//   bus_rsp_rdata[31:0]             read data, valid in that cycle; holds
//                                   its last value between reads
//   bus_rsp_error                   the accepted transaction addressed an
//                                   unmapped offset
//
// A transaction is accepted on a rising clock edge with
// bus_req_valid && bus_req_ready. All register updates and all
// side-effect strobes are registered at the accepting edge, so they are
// visible in the same cycle as the response beat -- one uniform timing
// rule for the whole block.
//
// bus_req_ready is high in every cycle except the one immediately after an
// accepted EVQ_OUT read. That single wait state is what makes the
// read-and-pop of EVQ_OUT atomic: the read returns the queue head and the
// pop strobe that consumes it lands one cycle later, so the next request
// must not be accepted until the queue has actually advanced (see the
// EVQ_OUT contract below). The wait state depends only on the address of
// the previous transaction, never on the queue state, so the bus timing of
// every offset is deterministic. No other offset ever stalls.
//
// Word granularity only: there are no byte lane strobes. All registers are
// 32-bit words on a 32-bit word-aligned peripheral bus (regmap.yaml meta),
// so a bridge assembles full words before presenting a write. Address bits
// [1:0] are part of the decode comparison and every mapped offset has
// [1:0] = 00, so a misaligned access decodes as unmapped by construction.
//
// Adaptation (docs/08 section 2.3 GRLIB conventions, section 3 row 20:
// little-endian, 32-bit registers, one 4 KB slot per instance). Both
// bridges below see the same single-beat request/response pair; both must
// present bus_req_valid until it is accepted and must withdraw it as soon
// as it is, because this slave accepts one transaction per accepting edge
// and an APB access phase lasts more than one cycle.
//   - AMBA APB bridge: PWRITE -> bus_req_write, PADDR[11:0] ->
//     bus_req_addr, PWDATA -> bus_req_wdata, PREADY <- bus_rsp_valid,
//     PRDATA <- bus_rsp_rdata, PSLVERR <- bus_rsp_error. bus_req_valid is
//     NOT PSEL && PENABLE: that is asserted for the whole access phase,
//     which is at least two PCLK cycles here (PREADY comes from the
//     registered response beat), so it would be accepted twice and would
//     commit a weight word or step W_ADDR twice. The bridge must hold a
//     one-shot instead:
//         always @(posedge PCLK or negedge PRESETn)
//           if (!PRESETn)                    apb_taken <= 1'b0;
//           else if (!(PSEL && PENABLE))     apb_taken <= 1'b0;
//           else if (bus_req_valid && bus_req_ready) apb_taken <= 1'b1;
//         assign bus_req_valid = PSEL && PENABLE && !apb_taken;
//     This is correct for any number of wait states, so it also covers the
//     EVQ_OUT wait state and any future throttling. APB2 masters that have
//     no PSLVERR simply leave bus_rsp_error unconnected, which matches the
//     GRLIB behavior that accesses to unoccupied ranges behind a bridge
//     have no effect.
//   - SPI/QSPI register bridge: the shift register presents one command
//     word (write flag + offset) and one data word, raises bus_req_valid
//     and holds it until bus_req_valid && bus_req_ready, then drops it and
//     latches bus_rsp_rdata / bus_rsp_error on bus_rsp_valid to shift back
//     out. A bridge that pulses bus_req_valid for a fixed single cycle
//     would lose a transaction against the EVQ_OUT wait state.
//
// ---------------------------------------------------------------------
// 2. Access classes (regmap.yaml "access" column)
// ---------------------------------------------------------------------
//
//   RO  read-only. ID and VERSION are wired constants; STATUS, EVQ_STAT,
//       CNT_*, FAULT_ADDR and EVQ_OUT are driven only by hardware event
//       inputs. Writes to an RO offset are ignored and are NOT an error
//       (GRLIB convention: no effect).
//   RW  read-write, masked to the declared field bits; bits outside a
//       declared field are unwritable and read 0.
//   WO  write-only: W_DATA_LO, W_DATA_HI, ECC_INJ, EVQ_IN. Writes are
//       stored / acted on, reads return 0x00000000.
//   W1C write-1-to-clear ports: STATUS_CLR and FAULT_CLR hold no state and
//       read 0x00000000; a written 1 clears the addressed sticky bit or
//       counter.
//   SC  self-clearing: CTRL.STATE_CLR and CTRL.SOFT_RST are set by a
//       write-1 and clear themselves on the next clock edge, so each is a
//       one-cycle strobe on the corresponding output and reads back as 1
//       only in the single cycle it is asserted. ECC_INJ.SINGLE/DOUBLE are
//       the other SC form: they arm until the hardware consumes them, i.e.
//       until the next W_DATA_HI commit (regmap.yaml: "on the next W_DATA
//       commit"), and are exported as ecc_inj_single / ecc_inj_double
//       because the register itself is write-only. "Consumed by the
//       commit" means consumed by the exported handshake, not by the
//       accepting edge: see C7.
//
// ---------------------------------------------------------------------
// 3. Conventions this block defines (not fixed by regmap.yaml)
// ---------------------------------------------------------------------
//
// C1. Hardware wins every hardware-event / software-clear race.
//     A sticky STATUS bit set by its hardware event in the same cycle as a
//     STATUS_CLR write-1 stays set; a counter incremented in the same cycle
//     as its FAULT_CLR write-1 restarts at 1; FAULT_ADDR latched in the
//     same cycle as its clear keeps the newly latched address. An observed
//     fault is never lost to a clear that raced it. This is the same
//     convention as the aer_fifo drop counter (hw/rtl/aer_fifo.v).
//     The single documented exception is the N_DATA staging register: a bus
//     write wins over a coincident hardware load (n_data_ld), because a
//     software state restore must not be overwritten by a stale prefetch.
//
// C2. FAULT_CLR bit assignment. regmap.yaml declares the five clear bits
//     as fields (one per fault-block register, in offset order from 0x70
//     upward), so the assignment below is generated, not local policy:
//       bit 0 -> CNT_SEC        bit 1 -> CNT_DED
//       bit 2 -> CNT_EVQ_OVF    bit 3 -> CNT_AXON_OOR
//       bit 4 -> FAULT_ADDR
//     Every use indexes bus_req_wdata through BIT_FAULT_CLR_* from the
//     generated header, and an elaboration guard checks that the generated
//     positions still line up with the packed counter order. Bits [31:5]
//     are ignored. The written mask is re-exported one cycle later on
//     fault_clr[4:0] so the SoC can clear distributed copies of the same
//     record from the same write (aer_fifo drop_clr from bit 2).
//
// C3. STATUS live bits and EVQ_STAT are registered snapshots of their
//     hardware inputs, not combinational feedthroughs. This gives STATUS
//     the literal reset value of regmap.yaml (0x00000006: not BUSY, both
//     queues empty) independently of what the datapath drives during reset,
//     keeps the bus read path free of datapath combinational logic, and
//     costs one cycle of staleness on b0..b2 and on the fill counts.
//
// C4. Configuration lock (docs/10 section 6): "configuration writes while
//     STATUS.BUSY = 1 are ignored and latch ERR_CFG (CTRL, STATUS_CLR and
//     FAULT_CLR remain writable)". The locked set implemented here is the
//     17 registers whose value enters the per-pass configuration or the
//     memory load port: CFG_NEUR, CFG_AXON, CFG_THRESH, CFG_VRESET,
//     CFG_LEAK, CFG_SYNSHIFT, CFG_REFR, CFG_FLAGS, PASS_TILE_OFF, W_BASE,
//     PASS_ID, W_ADDR, W_DATA_LO, W_DATA_HI, N_ADDR, N_DATA, NODE_ID.
//     Deliberately NOT locked, beyond the three the spec names: SCRATCH
//     (bus test register, no side effects), EVQ_IN (runtime software event
//     injection, useless if it were gated by BUSY) and ECC_INJ
//     (verification hook, armed while the core runs). A blocked write
//     changes no state and sets STATUS.ERR_CFG.
//     The lock engages on hw_busy OR on the STATUS.BUSY snapshot of it, not
//     on the snapshot alone. STATUS.BUSY is one cycle behind hw_busy (C3),
//     so keying only off the snapshot would leave a one-cycle hole in which
//     a configuration write accepted on the very edge hw_busy rises is
//     neither ignored nor flagged. Taking the union closes that hole and
//     keeps the lock engaged for the one extra cycle in which software can
//     still read STATUS.BUSY = 1, so the software-visible rule "the write
//     is refused exactly while STATUS.BUSY reads 1" is never violated in
//     the permissive direction.
//
// C5. Configuration validation (docs/10 section 6 table). cfg_valid is a
//     continuous function of the configuration registers: THETA in
//     [1, 32767], V_RESET < THETA (signed), CFG_NEUR in [1, N_NEURONS],
//     CFG_AXON in [1, N_AXONS]. The remaining rows of that table (S_LEAK,
//     S_SYN, T_REFR, the flag bits) cannot go out of range because their
//     fields are exactly as wide as their ranges. CFG_NEUR and CFG_AXON
//     are checked against the N_NEURONS / N_AXONS parameters, which are
//     also their reset values (C8), so a smaller instantiation is valid
//     out of reset.
//     The "refuses to start" half of the rule is implemented by gating the
//     en output with cfg_valid; CTRL.EN still reads back what software
//     wrote, so the diagnostic path is EN written 1, EN reads 1, en stays
//     low, STATUS.ERR_CFG set. Two validation conditions latch ERR_CFG,
//     not one: writing CTRL.EN = 1 while the configuration is out of
//     range, and the level condition CTRL.EN = 1 while the configuration
//     is out of range. (The other two ERR_CFG sources are the blocked
//     configuration write of C4 and the FSM SAFE-state input hw_err_cfg.)
//     The second exists because a configuration write can
//     invalidate a configuration that was valid when EN was set; without
//     it, STATUS would report CTRL.EN = 1, en low and no error, which
//     contradicts the single-source register description of ERR_CFG
//     ("out-of-range configuration or config write while BUSY"). An
//     out-of-range value written while EN = 0 is not an error: nothing has
//     been asked to start yet, and software is mid-way through loading a
//     configuration. The TILE_OFF + CFG_NEUR <= 1024 bound of docs/10
//     section 9 is NOT checked here: it is a property of a pass schedule,
//     enforced by the golden model and the pass sequencer.
//
// C6. Weight load port handshake. {w_commit, w_addr, w_data} is one write
//     port to the weight SRAM: w_commit is the enable, and w_addr / w_data
//     are the address and data of that write. They are only meaningful
//     while w_commit is asserted.
//     W_ADDR auto-increment (regmap.yaml: "auto-increments on W_DATA_HI
//     commit") is the one register that changes on a write addressed to a
//     different offset. It wraps at 2^32; the yaml declares no field for
//     W_ADDR, so all 32 bits are writable and counted. Because the
//     increment happens at the accepting edge like every other register
//     update (section 1), the value software reads back after a commit is
//     already the next index -- but the word just committed belongs at the
//     PREVIOUS index. So w_addr is not r_w_addr: it is the value W_ADDR
//     held when the commit was accepted, captured at that edge and held
//     until the next commit. Software therefore sees
//         W_ADDR = A, write W_DATA_LO/W_DATA_HI  ->  word lands at A,
//         W_ADDR reads A+1 from the next transaction onwards,
//     which is what docs/10 section 10 ("weight SRAM word index;
//     auto-increments on commit") describes. The cost is one 32-bit
//     capture register; the alternative, delaying the increment to the
//     w_commit cycle, would make a W_ADDR read issued immediately after a
//     commit return the stale index.
//
// C7. ECC_INJ arm lifetime. The arm bits are consumed by the exported
//     w_commit handshake, not by the accepting edge of the W_DATA_HI
//     write. Clearing them at the accepting edge (one cycle before
//     w_commit) would mean no cycle ever shows an armed hook together with
//     the commit that is supposed to corrupt it, which makes the docs/10
//     section 11.2 injection hook dead silicon. They are therefore cleared
//     on w_commit, so they are asserted throughout the commit cycle and
//     drop on the edge that ends it. Back-to-back commits consume one arm:
//     the first commit clears it, the second sees it low.
//
// C8. CFG_NEUR / CFG_AXON reset from the N_NEURONS / N_AXONS parameters,
//     not from the RST_CFG_NEUR / RST_CFG_AXON literals of the generated
//     header. docs/10 section 6 gives those two reset values symbolically
//     ("N_NEURONS", "N_AXONS") while regmap.yaml can only carry the
//     512-default literal, and docs/10 section 1 explicitly supports
//     smaller instantiations. Resetting from the literal would bring a
//     256-neuron build out of reset with CFG_NEUR = 512 > N_NEURONS, so
//     cfg_valid would be low, en would be gated off and STATUS.ERR_CFG
//     would latch as soon as software set CTRL.EN -- the core could not be
//     started at all. The literals are kept as a cross-check: an
//     elaboration guard fails the build if the header literal and the
//     parameter disagree at the 512 default.
//
// C9. EVQ_OUT source contract. The hw_evq_out_* inputs must come from a
//     show-ahead (first-word-fall-through) queue: hw_evq_out_valid means
//     "a word is presented", hw_evq_out_data is that word, and the word is
//     held unchanged until evq_out_pop consumes it, on which edge the
//     queue advances to the next word. hw/rtl/aer_fifo.v as written does
//     NOT satisfy this -- it is a registered-output queue whose rd_data
//     appears one cycle after rd_en (its header, contract bullet 1) --
//     so a show-ahead read port or a one-entry output adapter is required
//     between the two. See also the EVQ_OUT wait state in section 1: a
//     bus read returns the presented head at the accepting edge and the
//     pop lands one cycle later, so the next transaction is held off until
//     the queue has advanced. Without that wait state, back-to-back reads
//     would each return the same head while each issued a pop, destroying
//     one event per read, which docs/10 section 7.2 forbids ("spikes are
//     never dropped").
//
// Verilog-2005, Icarus-clean. The formal properties
// (formal/npu_regbank_props.v) are textually included under `ifdef FORMAL
// and are invisible to simulation and synthesis.
`default_nettype none

module npu_regbank #(
    parameter ADDR_W    = 12,   // regmap.yaml meta.addr_bits, do not override
    parameter DATA_W    = 32,   // regmap.yaml meta.data_bits, do not override
    parameter N_NEURONS = 512,  // docs/10 section 2, CFG_NEUR upper bound
    parameter N_AXONS   = 512,  // docs/10 section 2, CFG_AXON upper bound
    parameter CNT_W     = 32    // fault counter width; 32 in silicon, a
                                // smaller value is a formal/verification
                                // knob that makes saturation reachable
) (
    input  wire              clk,
    input  wire              rst_n,

    // ---- memory-mapped slave, single beat -----------------------------
    input  wire              bus_req_valid,
    output wire              bus_req_ready,
    input  wire              bus_req_write,
    input  wire [ADDR_W-1:0] bus_req_addr,
    input  wire [DATA_W-1:0] bus_req_wdata,
    output reg               bus_rsp_valid,
    output reg  [DATA_W-1:0] bus_rsp_rdata,
    output reg               bus_rsp_error,

    // ---- CTRL (0x0C) --------------------------------------------------
    output wire              en,             // CTRL.EN gated by cfg_valid
    output wire              scrub_en,       // CTRL.SCRUB_EN
    output reg               state_clr,      // CTRL.STATE_CLR, 1-cycle strobe
    output reg               soft_rst,       // CTRL.SOFT_RST, 1-cycle strobe

    // ---- cfg block (0x20..0x3C) ---------------------------------------
    output wire [10:0]       cfg_neur,
    output wire [10:0]       cfg_axon,
    output wire [15:0]       cfg_thresh,
    output wire [15:0]       cfg_vreset,
    output wire [3:0]        cfg_leak,
    output wire [2:0]        cfg_synshift,
    output wire [3:0]        cfg_refr,
    output wire              cfg_ts_en,
    output wire              cfg_leak_en,
    output wire              cfg_valid,      // docs/10 section 6 ranges met

    // ---- pass block (0x40..0x48) --------------------------------------
    output wire [9:0]        pass_tile_off,
    output wire [31:0]       w_base,
    output wire [7:0]        pass_id,

    // ---- weight load port (0x50..0x58, 0x84) --------------------------
    // One SRAM write port (C6): w_commit is the write enable, w_addr and
    // w_data are the address and data of that write and are meaningful
    // only while w_commit is asserted. w_addr is the index W_ADDR held
    // when the commit was accepted, i.e. before the auto-increment.
    output reg  [31:0]       w_addr,         // index of the committed word
    output wire [63:0]       w_data,         // {W_DATA_HI, W_DATA_LO}
    output reg               w_commit,       // 1-cycle strobe, w_data valid
    // Armed through the whole w_commit cycle, cleared on the edge that
    // ends it (C7), so the consumer samples arm and commit together.
    output reg               ecc_inj_single, // ECC_INJ.SINGLE, armed
    output reg               ecc_inj_double, // ECC_INJ.DOUBLE, armed

    // ---- neuron state port (0x60..0x64) -------------------------------
    output wire [31:0]       n_addr,
    output wire [19:0]       n_data,         // {R[3:0], V[15:0]} staging (N_DATA_W)
    output reg               n_data_wr,      // software wrote the staging reg
    output reg               n_data_rd,      // software read it (prefetch req)
    input  wire              n_data_ld,      // datapath loads the staging reg
    input  wire [19:0]       n_data_hw,      // width guarded against N_DATA_W

    // ---- AER software ports (0x90..0x9C) ------------------------------
    output wire [15:0]       evq_in_data,
    output reg               evq_in_wr,      // 1-cycle push strobe
    // Output queue contract (C9), REQUIRED of whatever drives these two
    // inputs: show-ahead / first-word-fall-through. hw_evq_out_valid means
    // "a word is presented now", hw_evq_out_data is that word, and both
    // hold unchanged until evq_out_pop is asserted; the queue advances on
    // the edge that ends the evq_out_pop cycle. hw/rtl/aer_fifo.v is a
    // registered-output queue (its rd_data appears one cycle AFTER rd_en)
    // and does not meet this contract as written -- it needs a show-ahead
    // read port or a one-entry output adapter in between.
    output reg               evq_out_pop,    // 1-cycle pop strobe
    input  wire              hw_evq_out_valid,
    input  wire [15:0]       hw_evq_out_data,
    input  wire [7:0]        hw_evq_in_fill,
    input  wire [7:0]        hw_evq_out_fill,
    output wire [3:0]        node_id,

    // ---- STATUS inputs (0x10) -----------------------------------------
    input  wire              hw_busy,
    input  wire              hw_evq_in_empty,
    input  wire              hw_evq_out_empty,
    input  wire              hw_sync_done,   // sets STATUS.SYNC_DONE
    input  wire              hw_err_cfg,     // sets STATUS.ERR_CFG (FSM SAFE)

    // ---- fault event inputs (0x70..0x88) ------------------------------
    input  wire              hw_sec,         // CNT_SEC++
    input  wire              hw_ded,         // CNT_DED++, DED_SEEN, FAULT_ADDR
    input  wire              hw_evq_ovf,     // CNT_EVQ_OVF++, OVF_SEEN
    input  wire              hw_axon_oor,    // CNT_AXON_OOR++
    input  wire [31:0]       hw_fault_addr,
    output reg  [4:0]        fault_clr       // re-exported FAULT_CLR mask (C2)
);

`include "npu_regs.vh"

    // Elaboration guard: a parameterization outside the contract takes the
    // generate branch and references a module that deliberately does not
    // exist, so elaboration fails with the module name as the message in
    // every tool (same construct as hw/rtl/aer_fifo.v).
    generate
        if (ADDR_W != 12 || DATA_W != 32) begin : g_bad_bus
            ERROR_npu_regbank_ADDR_W_must_be_12_and_DATA_W_must_be_32 guard ();
        end
        if (CNT_W < 2 || CNT_W > 32) begin : g_bad_cnt
            ERROR_npu_regbank_CNT_W_must_be_between_2_and_32 guard ();
        end
        if (N_NEURONS < 1 || N_NEURONS > 1024 || N_AXONS < 1 || N_AXONS > 1024) begin : g_bad_size
            ERROR_npu_regbank_N_NEURONS_and_N_AXONS_must_be_1_to_1024 guard ();
        end
        // Drift guards: the few field layouts this module encodes in a port
        // width or a zero-padding constant, checked against the generated
        // header so a regmap.yaml change that invalidates them fails
        // elaboration instead of quietly producing a wrong register.
        if (BIT_CTRL_EN != 0 || BIT_CTRL_STATE_CLR != 1
            || BIT_CTRL_SOFT_RST != 2 || BIT_CTRL_SCRUB_EN != 3) begin : g_ctrl_moved
            ERROR_npu_regbank_CTRL_field_layout_changed_in_regmap_yaml guard ();
        end
        if (BIT_STATUS_BUSY != 0 || BIT_STATUS_EVQ_IN_EMPTY != 1
            || BIT_STATUS_EVQ_OUT_EMPTY != 2 || BIT_STATUS_SYNC_DONE != 3
            || BIT_STATUS_OVF_SEEN != 6) begin : g_status_moved
            ERROR_npu_regbank_STATUS_field_layout_changed_in_regmap_yaml guard ();
        end
        if (BIT_N_DATA_R + WIDTH_N_DATA_R != 20) begin : g_n_data_moved
            ERROR_npu_regbank_N_DATA_field_layout_changed_in_regmap_yaml guard ();
        end
        if (BIT_EVQ_STAT_IN_FILL != 0 || WIDTH_EVQ_STAT_IN_FILL != 8
            || BIT_EVQ_STAT_OUT_FILL != 8 || WIDTH_EVQ_STAT_OUT_FILL != 8
            || BIT_EVQ_OUT_EVENT != 0 || WIDTH_EVQ_OUT_EVENT != 16
            || BIT_EVQ_OUT_VALID != 31) begin : g_aer_moved
            ERROR_npu_regbank_EVQ_field_layout_changed_in_regmap_yaml guard ();
        end
        if (BIT_ECC_INJ_SINGLE != 0 || BIT_ECC_INJ_DOUBLE != 1) begin : g_inj_moved
            ERROR_npu_regbank_ECC_INJ_field_layout_changed_in_regmap_yaml guard ();
        end
        // C2: the FAULT_CLR bits must stay in fault-block offset order,
        // because the counters are packed in that order below.
        if (BIT_FAULT_CLR_CNT_SEC != 0 || BIT_FAULT_CLR_CNT_DED != 1
            || BIT_FAULT_CLR_CNT_EVQ_OVF != 2
            || BIT_FAULT_CLR_CNT_AXON_OOR != 3
            || BIT_FAULT_CLR_FAULT_ADDR != 4) begin : g_fclr_moved
            ERROR_npu_regbank_FAULT_CLR_field_layout_changed_in_regmap_yaml guard ();
        end
        // C8 cross-check: CFG_NEUR / CFG_AXON reset from the parameters,
        // so the generated reset literals -- which can only carry the
        // regmap.yaml 512 default -- are no longer the reset source. They
        // must still agree with the parameters at that default build, or
        // regmap.yaml and docs/10 section 6 have drifted apart.
        if (N_NEURONS == 512 && RST_CFG_NEUR != N_NEURONS) begin : g_neur_rst
            ERROR_npu_regbank_CFG_NEUR_reset_literal_disagrees_with_N_NEURONS guard ();
        end
        if (N_AXONS == 512 && RST_CFG_AXON != N_AXONS) begin : g_axon_rst
            ERROR_npu_regbank_CFG_AXON_reset_literal_disagrees_with_N_AXONS guard ();
        end
    endgenerate

    localparam [10:0] NEUR_MAX = N_NEURONS;
    localparam [10:0] AXON_MAX = N_AXONS;

    // Widths taken from the generated field table rather than re-typed.
    localparam integer STS_LO     = BIT_STATUS_SYNC_DONE;   // first sticky bit
    localparam integer STS_HI     = BIT_STATUS_OVF_SEEN;    // last sticky bit
    localparam integer N_DATA_W   = BIT_N_DATA_R + WIDTH_N_DATA_R;
    localparam integer CFG_FLAGS_W = BIT_CFG_FLAGS_LEAK_EN + 1;
    localparam integer EVQ_W      = WIDTH_EVQ_OUT_EVENT;    // frozen event word

    // ------------------------------------------------------------------
    // Transaction acceptance. One wait state after an accepted EVQ_OUT
    // read (section 1, C9): that read returned the queue head and its pop
    // strobe is asserted in the very next cycle, so accepting another
    // transaction on that edge would let a second EVQ_OUT read sample the
    // head the first one already took. The stall is registered and keys
    // only off the address of the accepted read, so it is one cycle wide,
    // deterministic, and independent of the queue state.
    // ------------------------------------------------------------------
    reg evq_out_stall;

    assign bus_req_ready = !evq_out_stall;

    wire acc    = bus_req_valid && bus_req_ready;
    wire acc_wr = acc &&  bus_req_write;
    wire acc_rd = acc && !bus_req_write;

    // ------------------------------------------------------------------
    // Address decode: one select per mapped offset, straight from
    // npu_regs.vh. The selects are mutually exclusive because the
    // generator rejects duplicate offsets (regmap/generate.py validate()).
    // ------------------------------------------------------------------
    wire sel_id            = (bus_req_addr == ADDR_ID);
    wire sel_version       = (bus_req_addr == ADDR_VERSION);
    wire sel_scratch       = (bus_req_addr == ADDR_SCRATCH);
    wire sel_ctrl          = (bus_req_addr == ADDR_CTRL);
    wire sel_status        = (bus_req_addr == ADDR_STATUS);
    wire sel_status_clr    = (bus_req_addr == ADDR_STATUS_CLR);
    wire sel_cfg_neur      = (bus_req_addr == ADDR_CFG_NEUR);
    wire sel_cfg_axon      = (bus_req_addr == ADDR_CFG_AXON);
    wire sel_cfg_thresh    = (bus_req_addr == ADDR_CFG_THRESH);
    wire sel_cfg_vreset    = (bus_req_addr == ADDR_CFG_VRESET);
    wire sel_cfg_leak      = (bus_req_addr == ADDR_CFG_LEAK);
    wire sel_cfg_synshift  = (bus_req_addr == ADDR_CFG_SYNSHIFT);
    wire sel_cfg_refr      = (bus_req_addr == ADDR_CFG_REFR);
    wire sel_cfg_flags     = (bus_req_addr == ADDR_CFG_FLAGS);
    wire sel_pass_tile_off = (bus_req_addr == ADDR_PASS_TILE_OFF);
    wire sel_w_base        = (bus_req_addr == ADDR_W_BASE);
    wire sel_pass_id       = (bus_req_addr == ADDR_PASS_ID);
    wire sel_w_addr        = (bus_req_addr == ADDR_W_ADDR);
    wire sel_w_data_lo     = (bus_req_addr == ADDR_W_DATA_LO);
    wire sel_w_data_hi     = (bus_req_addr == ADDR_W_DATA_HI);
    wire sel_n_addr        = (bus_req_addr == ADDR_N_ADDR);
    wire sel_n_data        = (bus_req_addr == ADDR_N_DATA);
    wire sel_cnt_sec       = (bus_req_addr == ADDR_CNT_SEC);
    wire sel_cnt_ded       = (bus_req_addr == ADDR_CNT_DED);
    wire sel_cnt_evq_ovf   = (bus_req_addr == ADDR_CNT_EVQ_OVF);
    wire sel_cnt_axon_oor  = (bus_req_addr == ADDR_CNT_AXON_OOR);
    wire sel_fault_addr    = (bus_req_addr == ADDR_FAULT_ADDR);
    wire sel_ecc_inj       = (bus_req_addr == ADDR_ECC_INJ);
    wire sel_fault_clr     = (bus_req_addr == ADDR_FAULT_CLR);
    wire sel_evq_stat      = (bus_req_addr == ADDR_EVQ_STAT);
    wire sel_evq_in        = (bus_req_addr == ADDR_EVQ_IN);
    wire sel_evq_out       = (bus_req_addr == ADDR_EVQ_OUT);
    wire sel_node_id       = (bus_req_addr == ADDR_NODE_ID);

    wire dec_hit = sel_id | sel_version | sel_scratch | sel_ctrl
                 | sel_status | sel_status_clr
                 | sel_cfg_neur | sel_cfg_axon | sel_cfg_thresh
                 | sel_cfg_vreset | sel_cfg_leak | sel_cfg_synshift
                 | sel_cfg_refr | sel_cfg_flags
                 | sel_pass_tile_off | sel_w_base | sel_pass_id
                 | sel_w_addr | sel_w_data_lo | sel_w_data_hi
                 | sel_n_addr | sel_n_data
                 | sel_cnt_sec | sel_cnt_ded | sel_cnt_evq_ovf
                 | sel_cnt_axon_oor | sel_fault_addr | sel_ecc_inj
                 | sel_fault_clr
                 | sel_evq_stat | sel_evq_in | sel_evq_out | sel_node_id;

    // ------------------------------------------------------------------
    // Register storage
    // ------------------------------------------------------------------
    reg [31:0] r_scratch;
    reg        r_ctrl_en;
    reg        r_ctrl_scrub_en;
    reg [2:0]  r_sts_live;     // b0 BUSY, b1 EVQ_IN_EMPTY, b2 EVQ_OUT_EMPTY
    reg [STS_HI:STS_LO] r_sts_sticky;  // SYNC_DONE, ERR_CFG, DED_SEEN, OVF_SEEN
    reg [10:0] r_cfg_neur;
    reg [10:0] r_cfg_axon;
    reg [15:0] r_cfg_thresh;
    reg [15:0] r_cfg_vreset;
    reg [3:0]  r_cfg_leak;
    reg [2:0]  r_cfg_synshift;
    reg [3:0]  r_cfg_refr;
    reg [CFG_FLAGS_W-1:0] r_cfg_flags;  // b0 TS_EN, b1 LEAK_EN
    reg [9:0]  r_tile_off;
    reg [31:0] r_w_base;
    reg [7:0]  r_pass_id;
    reg [31:0] r_w_addr;
    reg [31:0] r_w_lo;
    reg [31:0] r_w_hi;
    reg [31:0] r_n_addr;
    reg [N_DATA_W-1:0] r_n_data;
    reg [31:0] r_fault_addr;
    reg [WIDTH_EVQ_STAT_IN_FILL+WIDTH_EVQ_STAT_OUT_FILL-1:0] r_evq_stat;
    reg [EVQ_W-1:0] r_evq_in;
    reg [3:0]  r_node_id;

    // Fault counters, packed so the four instances share one loop body.
    localparam integer CI_SEC = 0;
    localparam integer CI_DED = 1;
    localparam integer CI_OVF = 2;
    localparam integer CI_OOR = 3;
    localparam [CNT_W-1:0] CNT_MAX  = {CNT_W{1'b1}};
    localparam [CNT_W-1:0] CNT_ONE  = 1;
    localparam [CNT_W-1:0] CNT_ZERO = 0;
    reg [4*CNT_W-1:0] r_cnt;

    // ------------------------------------------------------------------
    // Configuration lock and validation (C4, C5)
    // ------------------------------------------------------------------
    wire sts_busy = r_sts_live[BIT_STATUS_BUSY];

    // The lock engages on the live input as well as on the STATUS snapshot
    // of it (C4). The snapshot alone leaves a one-cycle hole on the rising
    // edge of hw_busy; the union closes it and never unlocks earlier than
    // software can observe STATUS.BUSY = 0.
    wire cfg_lock = hw_busy || sts_busy;

    wire sel_cfg_locked = sel_cfg_neur | sel_cfg_axon | sel_cfg_thresh
                        | sel_cfg_vreset | sel_cfg_leak | sel_cfg_synshift
                        | sel_cfg_refr | sel_cfg_flags
                        | sel_pass_tile_off | sel_w_base | sel_pass_id
                        | sel_w_addr | sel_w_data_lo | sel_w_data_hi
                        | sel_n_addr | sel_n_data | sel_node_id;

    wire wr_block = acc_wr && sel_cfg_locked && cfg_lock;
    wire wr_ok    = acc_wr && !wr_block;

    wire theta_ok  = (r_cfg_thresh != 16'h0000) && (r_cfg_thresh[15] == 1'b0);
    wire vreset_ok = ($signed(r_cfg_vreset) < $signed(r_cfg_thresh));
    wire neur_ok   = (r_cfg_neur != 11'd0) && (r_cfg_neur <= NEUR_MAX);
    wire axon_ok   = (r_cfg_axon != 11'd0) && (r_cfg_axon <= AXON_MAX);
    assign cfg_valid = theta_ok && vreset_ok && neur_ok && axon_ok;

    // ------------------------------------------------------------------
    // Per-register write enables. Exactly one can be high at a time
    // (the selects are mutually exclusive); proven in the formal harness.
    // ------------------------------------------------------------------
    wire we_scratch       = wr_ok && sel_scratch;
    wire we_ctrl          = wr_ok && sel_ctrl;
    wire we_status_clr    = wr_ok && sel_status_clr;
    wire we_cfg_neur      = wr_ok && sel_cfg_neur;
    wire we_cfg_axon      = wr_ok && sel_cfg_axon;
    wire we_cfg_thresh    = wr_ok && sel_cfg_thresh;
    wire we_cfg_vreset    = wr_ok && sel_cfg_vreset;
    wire we_cfg_leak      = wr_ok && sel_cfg_leak;
    wire we_cfg_synshift  = wr_ok && sel_cfg_synshift;
    wire we_cfg_refr      = wr_ok && sel_cfg_refr;
    wire we_cfg_flags     = wr_ok && sel_cfg_flags;
    wire we_pass_tile_off = wr_ok && sel_pass_tile_off;
    wire we_w_base        = wr_ok && sel_w_base;
    wire we_pass_id       = wr_ok && sel_pass_id;
    wire we_w_addr        = wr_ok && sel_w_addr;
    wire we_w_data_lo     = wr_ok && sel_w_data_lo;
    wire we_w_data_hi     = wr_ok && sel_w_data_hi;
    wire we_n_addr        = wr_ok && sel_n_addr;
    wire we_n_data        = wr_ok && sel_n_data;
    wire we_ecc_inj       = wr_ok && sel_ecc_inj;
    wire we_fault_clr     = wr_ok && sel_fault_clr;
    wire we_evq_in        = wr_ok && sel_evq_in;
    wire we_node_id       = wr_ok && sel_node_id;

    // Read-side side effects
    wire re_n_data  = acc_rd && sel_n_data;
    wire re_evq_out = acc_rd && sel_evq_out;

    // ------------------------------------------------------------------
    // Event sources
    // ------------------------------------------------------------------
    // A write to CTRL that sets EN while the configuration is out of range
    // is the "refuses to start" diagnostic of docs/10 section 6 (C5).
    wire en_bad_cfg  = acc_wr && sel_ctrl && bus_req_wdata[BIT_CTRL_EN] && !cfg_valid;
    // ... and so is an enabled core whose configuration has been made
    // out of range by a later write. Without this term STATUS would read
    // CTRL.EN = 1, en low and ERR_CFG clear, which the single-source
    // description of ERR_CFG forbids (C5).
    wire en_cfg_bad_live = r_ctrl_en && !cfg_valid;
    wire evt_err_cfg = hw_err_cfg || wr_block || en_bad_cfg || en_cfg_bad_live;

    wire [STS_HI:STS_LO] sts_evt;
    assign sts_evt[BIT_STATUS_SYNC_DONE] = hw_sync_done;
    assign sts_evt[BIT_STATUS_ERR_CFG]   = evt_err_cfg;
    assign sts_evt[BIT_STATUS_DED_SEEN]  = hw_ded;
    assign sts_evt[BIT_STATUS_OVF_SEEN]  = hw_evq_ovf;

    wire [3:0] cnt_evt;
    assign cnt_evt[CI_SEC] = hw_sec;
    assign cnt_evt[CI_DED] = hw_ded;
    assign cnt_evt[CI_OVF] = hw_evq_ovf;
    assign cnt_evt[CI_OOR] = hw_axon_oor;

    // FAULT_CLR mask (C2). Every bit position comes from the generated
    // header, so regmap.yaml stays the single source of the assignment;
    // bits [31:5] have no field and are ignored.
    localparam integer CI_ADDR = 4;          // FAULT_ADDR slot in fclr
    wire [CI_ADDR:0] fclr;
    assign fclr[CI_SEC]  = we_fault_clr && bus_req_wdata[BIT_FAULT_CLR_CNT_SEC];
    assign fclr[CI_DED]  = we_fault_clr && bus_req_wdata[BIT_FAULT_CLR_CNT_DED];
    assign fclr[CI_OVF]  = we_fault_clr && bus_req_wdata[BIT_FAULT_CLR_CNT_EVQ_OVF];
    assign fclr[CI_OOR]  = we_fault_clr && bus_req_wdata[BIT_FAULT_CLR_CNT_AXON_OOR];
    assign fclr[CI_ADDR] = we_fault_clr && bus_req_wdata[BIT_FAULT_CLR_FAULT_ADDR];

    // The weight word commit advances W_ADDR at this edge (C6) and captures
    // the pre-increment index for the exported handshake; the ECC_INJ arm
    // is consumed one cycle later, by the exported w_commit itself (C7).
    wire w_commit_now = we_w_data_hi;

    // ------------------------------------------------------------------
    // sys block: SCRATCH, CTRL
    // ------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            r_scratch       <= RST_SCRATCH;
            r_ctrl_en       <= RST_CTRL[BIT_CTRL_EN];
            r_ctrl_scrub_en <= RST_CTRL[BIT_CTRL_SCRUB_EN];
            state_clr       <= RST_CTRL[BIT_CTRL_STATE_CLR];
            soft_rst        <= RST_CTRL[BIT_CTRL_SOFT_RST];
        end else begin
            if (we_scratch)
                r_scratch <= bus_req_wdata;
            if (we_ctrl) begin
                r_ctrl_en       <= bus_req_wdata[BIT_CTRL_EN];
                r_ctrl_scrub_en <= bus_req_wdata[BIT_CTRL_SCRUB_EN];
            end
            // SC bits: set by write-1, self-clear on the next edge
            state_clr <= we_ctrl && bus_req_wdata[BIT_CTRL_STATE_CLR];
            soft_rst  <= we_ctrl && bus_req_wdata[BIT_CTRL_SOFT_RST];
        end
    end

    // ------------------------------------------------------------------
    // STATUS: registered live snapshot (C3) + sticky bits (C1)
    // ------------------------------------------------------------------
    integer s;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            r_sts_live   <= RST_STATUS[2:0];
            r_sts_sticky <= RST_STATUS[6:3];
        end else begin
            r_sts_live[BIT_STATUS_BUSY]          <= hw_busy;
            r_sts_live[BIT_STATUS_EVQ_IN_EMPTY]  <= hw_evq_in_empty;
            r_sts_live[BIT_STATUS_EVQ_OUT_EMPTY] <= hw_evq_out_empty;
            for (s = STS_LO; s <= STS_HI; s = s + 1) begin
                if (sts_evt[s])
                    r_sts_sticky[s] <= 1'b1;                    // hardware wins
                else if (we_status_clr && bus_req_wdata[s])
                    r_sts_sticky[s] <= 1'b0;
            end
        end
    end

    // ------------------------------------------------------------------
    // cfg block
    // ------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            r_cfg_neur     <= NEUR_MAX;    // C8: docs/10 section 6 resets
            r_cfg_axon     <= AXON_MAX;    // these two symbolically

            r_cfg_thresh   <= RST_CFG_THRESH[WIDTH_CFG_THRESH_THETA-1:0];
            r_cfg_vreset   <= RST_CFG_VRESET[WIDTH_CFG_VRESET_VRESET-1:0];
            r_cfg_leak     <= RST_CFG_LEAK[WIDTH_CFG_LEAK_S_LEAK-1:0];
            r_cfg_synshift <= RST_CFG_SYNSHIFT[WIDTH_CFG_SYNSHIFT_S_SYN-1:0];
            r_cfg_refr     <= RST_CFG_REFR[WIDTH_CFG_REFR_T_REFR-1:0];
            r_cfg_flags    <= RST_CFG_FLAGS[CFG_FLAGS_W-1:0];
        end else begin
            if (we_cfg_neur)     r_cfg_neur     <= bus_req_wdata[WIDTH_CFG_NEUR_CNT-1:0];
            if (we_cfg_axon)     r_cfg_axon     <= bus_req_wdata[WIDTH_CFG_AXON_CNT-1:0];
            if (we_cfg_thresh)   r_cfg_thresh   <= bus_req_wdata[WIDTH_CFG_THRESH_THETA-1:0];
            if (we_cfg_vreset)   r_cfg_vreset   <= bus_req_wdata[WIDTH_CFG_VRESET_VRESET-1:0];
            if (we_cfg_leak)     r_cfg_leak     <= bus_req_wdata[WIDTH_CFG_LEAK_S_LEAK-1:0];
            if (we_cfg_synshift) r_cfg_synshift <= bus_req_wdata[WIDTH_CFG_SYNSHIFT_S_SYN-1:0];
            if (we_cfg_refr)     r_cfg_refr     <= bus_req_wdata[WIDTH_CFG_REFR_T_REFR-1:0];
            if (we_cfg_flags)    r_cfg_flags    <= bus_req_wdata[CFG_FLAGS_W-1:0];
        end
    end

    // ------------------------------------------------------------------
    // pass block
    // ------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            r_tile_off <= RST_PASS_TILE_OFF[WIDTH_PASS_TILE_OFF_OFF-1:0];
            r_w_base   <= RST_W_BASE;
            r_pass_id  <= RST_PASS_ID[WIDTH_PASS_ID_NUM-1:0];
        end else begin
            if (we_pass_tile_off) r_tile_off <= bus_req_wdata[WIDTH_PASS_TILE_OFF_OFF-1:0];
            if (we_w_base)        r_w_base   <= bus_req_wdata;
            if (we_pass_id)       r_pass_id  <= bus_req_wdata[WIDTH_PASS_ID_NUM-1:0];
        end
    end

    // ------------------------------------------------------------------
    // mem block: weight load port and neuron state staging
    // ------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            r_w_addr <= RST_W_ADDR;
            w_addr   <= RST_W_ADDR;
            r_w_lo   <= RST_W_DATA_LO;
            r_w_hi   <= RST_W_DATA_HI;
            r_n_addr <= RST_N_ADDR;
            r_n_data <= RST_N_DATA[N_DATA_W-1:0];
        end else begin
            if (we_w_addr)          r_w_addr <= bus_req_wdata;
            else if (w_commit_now)  r_w_addr <= r_w_addr + 32'd1;   // C6
            // The exported index is the pre-increment one: it names the
            // word this commit carries, and is held until the next commit.
            if (w_commit_now)       w_addr   <= r_w_addr;           // C6
            if (we_w_data_lo) r_w_lo <= bus_req_wdata;
            if (we_w_data_hi) r_w_hi <= bus_req_wdata;
            if (we_n_addr)    r_n_addr <= bus_req_wdata;
            if (we_n_data)         r_n_data <= bus_req_wdata[N_DATA_W-1:0]; // C1 exception
            else if (n_data_ld)    r_n_data <= n_data_hw;
        end
    end

    // ------------------------------------------------------------------
    // fault block: counters (C1 restart-at-1), FAULT_ADDR, ECC_INJ arming
    // ------------------------------------------------------------------
    integer c;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            r_cnt <= {(4*CNT_W){1'b0}};
        end else begin
            for (c = 0; c < 4; c = c + 1) begin
                if (fclr[c])
                    r_cnt[c*CNT_W +: CNT_W] <= cnt_evt[c] ? CNT_ONE : CNT_ZERO;
                else if (cnt_evt[c] && r_cnt[c*CNT_W +: CNT_W] != CNT_MAX)
                    r_cnt[c*CNT_W +: CNT_W] <= r_cnt[c*CNT_W +: CNT_W] + CNT_ONE;
            end
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            r_fault_addr   <= RST_FAULT_ADDR;
            ecc_inj_single <= RST_ECC_INJ[BIT_ECC_INJ_SINGLE];
            ecc_inj_double <= RST_ECC_INJ[BIT_ECC_INJ_DOUBLE];
        end else begin
            if (hw_ded)             r_fault_addr <= hw_fault_addr;  // hardware wins
            else if (fclr[CI_ADDR]) r_fault_addr <= 32'h00000000;
            if (we_ecc_inj) begin
                ecc_inj_single <= bus_req_wdata[BIT_ECC_INJ_SINGLE];
                ecc_inj_double <= bus_req_wdata[BIT_ECC_INJ_DOUBLE];
            end else if (w_commit) begin
                // Consumed by the exported handshake, not by the accepting
                // edge (C7): the arm is still up during the w_commit cycle
                // that is supposed to corrupt the word, and drops here.
                ecc_inj_single <= 1'b0;
                ecc_inj_double <= 1'b0;
            end
        end
    end

    // ------------------------------------------------------------------
    // aer block: EVQ_STAT snapshot (C3), EVQ_IN word, NODE_ID
    // ------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            r_evq_stat <= RST_EVQ_STAT[WIDTH_EVQ_STAT_IN_FILL+WIDTH_EVQ_STAT_OUT_FILL-1:0];
            r_evq_in   <= RST_EVQ_IN[EVQ_W-1:0];
            r_node_id  <= RST_NODE_ID[WIDTH_NODE_ID_NID-1:0];
        end else begin
            r_evq_stat <= {hw_evq_out_fill, hw_evq_in_fill};
            // EVQ_IN carries the same frozen 16-bit local event word as
            // EVQ_OUT.EVENT (docs/10 section 7.1), so its width tracks that
            // field rather than a literal; regmap.yaml declares no field of
            // its own for the write-only injection port.
            if (we_evq_in)  r_evq_in  <= bus_req_wdata[EVQ_W-1:0];
            if (we_node_id) r_node_id <= bus_req_wdata[WIDTH_NODE_ID_NID-1:0];
        end
    end

    // ------------------------------------------------------------------
    // Read multiplexer. Unmapped offsets (including misaligned ones) read
    // 0x00000000 and raise bus_rsp_error, and so do the WO and W1C ports,
    // which hold no readable state.
    //
    // Every arm starts from the all-zero default and writes only the bits
    // the register actually occupies, using the generated field positions
    // and widths. That keeps the undeclared bits at zero by construction
    // and keeps every assignment exactly as wide as its target, so the
    // block lints clean under Verilator's default width checks -- a bare
    // `rd_next = r_cfg_neur` is an 11-into-32 implicit extension.
    // ------------------------------------------------------------------
    reg [DATA_W-1:0] rd_next;
    always @(*) begin
        rd_next = {DATA_W{1'b0}};
        case (bus_req_addr)
            ADDR_ID:      rd_next = RST_ID;
            ADDR_VERSION: rd_next = RST_VERSION;
            ADDR_SCRATCH: rd_next = r_scratch;
            ADDR_CTRL: begin
                rd_next[BIT_CTRL_EN]        = r_ctrl_en;
                rd_next[BIT_CTRL_STATE_CLR] = state_clr;
                rd_next[BIT_CTRL_SOFT_RST]  = soft_rst;
                rd_next[BIT_CTRL_SCRUB_EN]  = r_ctrl_scrub_en;
            end
            ADDR_STATUS: begin
                rd_next[STS_LO-1:0]    = r_sts_live;
                rd_next[STS_HI:STS_LO] = r_sts_sticky;
            end
            ADDR_CFG_NEUR:      rd_next[WIDTH_CFG_NEUR_CNT-1:0]        = r_cfg_neur;
            ADDR_CFG_AXON:      rd_next[WIDTH_CFG_AXON_CNT-1:0]        = r_cfg_axon;
            ADDR_CFG_THRESH:    rd_next[WIDTH_CFG_THRESH_THETA-1:0]    = r_cfg_thresh;
            ADDR_CFG_VRESET:    rd_next[WIDTH_CFG_VRESET_VRESET-1:0]   = r_cfg_vreset;
            ADDR_CFG_LEAK:      rd_next[WIDTH_CFG_LEAK_S_LEAK-1:0]     = r_cfg_leak;
            ADDR_CFG_SYNSHIFT:  rd_next[WIDTH_CFG_SYNSHIFT_S_SYN-1:0]  = r_cfg_synshift;
            ADDR_CFG_REFR:      rd_next[WIDTH_CFG_REFR_T_REFR-1:0]     = r_cfg_refr;
            ADDR_CFG_FLAGS:     rd_next[CFG_FLAGS_W-1:0]               = r_cfg_flags;
            ADDR_PASS_TILE_OFF: rd_next[WIDTH_PASS_TILE_OFF_OFF-1:0]   = r_tile_off;
            ADDR_W_BASE:        rd_next = r_w_base;
            ADDR_PASS_ID:       rd_next[WIDTH_PASS_ID_NUM-1:0]         = r_pass_id;
            ADDR_W_ADDR:        rd_next = r_w_addr;
            ADDR_N_ADDR:        rd_next = r_n_addr;
            ADDR_N_DATA:        rd_next[N_DATA_W-1:0]                  = r_n_data;
            ADDR_CNT_SEC:       rd_next[CNT_W-1:0] = r_cnt[CI_SEC*CNT_W +: CNT_W];
            ADDR_CNT_DED:       rd_next[CNT_W-1:0] = r_cnt[CI_DED*CNT_W +: CNT_W];
            ADDR_CNT_EVQ_OVF:   rd_next[CNT_W-1:0] = r_cnt[CI_OVF*CNT_W +: CNT_W];
            ADDR_CNT_AXON_OOR:  rd_next[CNT_W-1:0] = r_cnt[CI_OOR*CNT_W +: CNT_W];
            ADDR_FAULT_ADDR:    rd_next = r_fault_addr;
            ADDR_EVQ_STAT: rd_next[WIDTH_EVQ_STAT_IN_FILL
                                   + WIDTH_EVQ_STAT_OUT_FILL - 1:0] = r_evq_stat;
            ADDR_EVQ_OUT: begin
                rd_next[WIDTH_EVQ_OUT_EVENT-1:0] = hw_evq_out_data;
                rd_next[BIT_EVQ_OUT_VALID]       = hw_evq_out_valid;
            end
            ADDR_NODE_ID: rd_next[WIDTH_NODE_ID_NID-1:0] = r_node_id;
            // ADDR_STATUS_CLR, ADDR_FAULT_CLR: W1C ports, no state.
            // ADDR_W_DATA_LO, ADDR_W_DATA_HI, ADDR_ECC_INJ, ADDR_EVQ_IN:
            // write-only. Both classes, and every unmapped offset, keep
            // the all-zero default.
            default: ;
        endcase
    end

    // ------------------------------------------------------------------
    // Response channel and registered side-effect strobes
    // ------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bus_rsp_valid <= 1'b0;
            bus_rsp_rdata <= 32'h00000000;
            bus_rsp_error <= 1'b0;
            w_commit      <= 1'b0;
            n_data_wr     <= 1'b0;
            n_data_rd     <= 1'b0;
            evq_in_wr     <= 1'b0;
            evq_out_pop   <= 1'b0;
            evq_out_stall <= 1'b0;
            fault_clr     <= 5'b00000;
        end else begin
            bus_rsp_valid <= acc;
            bus_rsp_error <= acc && !dec_hit;
            if (acc_rd)
                bus_rsp_rdata <= rd_next;
            w_commit    <= w_commit_now;
            n_data_wr   <= we_n_data;
            n_data_rd   <= re_n_data;
            evq_in_wr   <= we_evq_in;
            evq_out_pop <= re_evq_out && hw_evq_out_valid;
            // One wait state per accepted EVQ_OUT read, so the pop above
            // is consumed before another read can sample the queue (C9).
            // Keyed off the address alone, so the stall is the same
            // whether or not the queue had a word to give.
            evq_out_stall <= re_evq_out;
            fault_clr   <= fclr;
        end
    end

    // ------------------------------------------------------------------
    // Datapath-facing outputs
    // ------------------------------------------------------------------
    assign en            = r_ctrl_en && cfg_valid;   // C5, "refuses to start"
    assign scrub_en      = r_ctrl_scrub_en;
    assign cfg_neur      = r_cfg_neur;
    assign cfg_axon      = r_cfg_axon;
    assign cfg_thresh    = r_cfg_thresh;
    assign cfg_vreset    = r_cfg_vreset;
    assign cfg_leak      = r_cfg_leak;
    assign cfg_synshift  = r_cfg_synshift;
    assign cfg_refr      = r_cfg_refr;
    assign cfg_ts_en     = r_cfg_flags[BIT_CFG_FLAGS_TS_EN];
    assign cfg_leak_en   = r_cfg_flags[BIT_CFG_FLAGS_LEAK_EN];
    assign pass_tile_off = r_tile_off;
    assign w_base        = r_w_base;
    assign pass_id       = r_pass_id;
    // w_addr is not here: it is the registered commit index of C6, driven
    // in the mem block above.
    assign w_data        = {r_w_hi, r_w_lo};
    assign n_addr        = r_n_addr;
    assign n_data        = r_n_data;
    assign evq_in_data   = r_evq_in;
    assign node_id       = r_node_id;

`ifdef FORMAL
`include "npu_regbank_props.v"
`endif

endmodule

`default_nettype wire
