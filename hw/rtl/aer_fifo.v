// AER event FIFO: parameterized synchronous FIFO carrying address-event
// (AER) words between the event interfaces and the NPU pipeline
// (docs/10-npu-mvp-spec.md section 7: EVQ_IN / EVQ_OUT, 16-bit local
// event word, 64-deep by default).
//
// Contract:
//   - Registered output: an accepted read presents its data on rd_data on
//     the next clock edge, flagged by rd_valid for one cycle.
//   - Overflow-safe: a write while full is dropped (never corrupts stored
//     events or pointers) and counted in a sticky saturating drop counter,
//     surfaced at the register block as CNT_EVQ_OVF / STATUS.OVF_SEEN.
//     This is the software injection port (EVQ_IN) semantics; a link-side
//     producer gets lossless backpressure by gating wr_en with !full.
//     A write coincident with a read while full is still dropped: full is
//     evaluated before the read frees a slot (conservative, formally proven).
//   - A read while empty is refused; rd_data holds its last value.
//   - drop_clr maps to FAULT_CLR; a drop coincident with the clear
//     restarts the counter at 1 so the event is not lost (house convention).
//   - level is exact occupancy (0..DEPTH), full == (level == DEPTH),
//     empty == (level == 0); level feeds EVQ_STAT.
//
// The registered output is a decision, not an accident, and it is the
// one thing here that a consumer has to design around. hw/rtl/npu_regbank.v
// convention C9 requires its EVQ_OUT source to be SHOW-AHEAD
// (first-word-fall-through): valid means "a word is presented now", the
// data is that word, and both hold until the pop advances the queue.
// This module does not meet that contract and deliberately still does
// not, because the alternative is worse: a show-ahead read port needs a
// combinational read of mem[], which turns the storage into an
// asynchronous-read register file. No synchronous SRAM macro can
// implement one, so at NPU scale (docs/10 section 7.2 sizes EVQ at 64
// entries per node, and the mesh has one per node) the queue could never
// be retargeted from flip-flops to a macro. It would also invalidate the
// four proofs in formal/aer_fifo.sby, which assert the registered
// timing directly (P5: rd_valid == $past(rd_ok), and rd_data holds
// otherwise).
//
// The gap is closed on the consumer side by a one-entry show-ahead
// adapter, which costs one flop-width plus a valid bit and no bandwidth
// that any register-mapped host can notice. hw/rtl/pilot_top.v section 8
// carries the reference implementation (oh_valid / oh_data / oh_pop) and
// the full comparison of the three options that were considered.
//
// DEPTH must be a power of two, >= 2 (enforced by an elaboration guard).
// Plain Verilog-2005, Icarus-clean; the formal properties
// (formal/aer_fifo_props.v) are textually included under `ifdef FORMAL
// and are invisible to simulation and synthesis.
`default_nettype none

module aer_fifo #(
    parameter WIDTH  = 16,             // AER event word width (docs/10 section 7.1)
    parameter DEPTH  = 64,             // entries, power of two >= 2 (EVQ_*_DEPTH)
    parameter DROP_W = 16,             // sticky drop counter width
    parameter AW     = $clog2(DEPTH)   // derived pointer width, do not override
) (
    input  wire              clk,
    input  wire              rst_n,
    // write side (AER producer)
    input  wire              wr_en,
    input  wire [WIDTH-1:0]  wr_data,
    output wire              full,
    // read side (event pipeline)
    input  wire              rd_en,
    output reg  [WIDTH-1:0]  rd_data,
    output reg               rd_valid,
    output wire              empty,
    // occupancy and overflow observability
    output wire [AW:0]       level,
    input  wire              drop_clr,
    output reg  [DROP_W-1:0] drop_cnt
);

    // Elaboration guard: a DEPTH outside the contract (power of two, >= 2)
    // takes the generate branch and references a module that deliberately
    // does not exist, so elaboration fails with the module name as the
    // message in every tool (Icarus, Yosys). Plain-2005 construct; DEPTH=1
    // would otherwise degenerate the [AW-1:0] index part-selects to [-1:0].
    generate
        if (DEPTH < 2 || (DEPTH & (DEPTH - 1)) != 0) begin : g_bad_depth
            ERROR_aer_fifo_DEPTH_must_be_a_power_of_two_ge_2 guard ();
        end
    endgenerate

    localparam [DROP_W-1:0] DROP_MAX = {DROP_W{1'b1}};

    // These four pointers are the highest-rate silent corruptor measured
    // anywhere in the pilot, and they are unprotected. The fault-injection
    // campaign put 24 single-bit upsets into them and 22 corrupted the
    // drained event stream with nothing flagged: whole bursts re-emitted,
    // events duplicated, events lost, events fabricated, and an unwritten
    // slot presented as a spike. An event interface has no sequence number
    // and no length field -- docs/10 section 7.1 freezes the word at TYPE
    // plus a 10-bit ID -- so a consumer cannot tell any of those from a
    // real spike train. Twelve flip-flops, one percent of the register
    // count, carry 46 percent of the design's residual silent corruption
    // (docs/16 section 5.2).
    //
    // TMR here is the best protection-per-flip-flop available in the
    // design and it is the named next hardening step. Whoever takes it:
    // the obvious implementation does not work. Three pointer replicas
    // written from the same enable and the same increment are provably
    // equivalent, so yosys `opt_dff` normalises them and `opt_merge`
    // hashes them into one bank -- the design ships one physical pointer
    // read three times, a voter that agrees with itself, and a claim in
    // the datasheet that is false. That is not hypothetical: it is
    // exactly what happened to the configuration TMR in pilot_top.v, it
    // survived review because a check read a null result as a positive
    // one, and it was caught only by counting flip-flop cells in the real
    // hardened netlist. Use the pattern that was proven to work there --
    // `pilot_cfg_bank`, keep_hierarchy plus an XOR mix that makes the
    // replicas structurally non-equivalent rather than merely
    // differently-polarised -- and extend
    // `sw/tests/test_synthesis_guards.py` to count these banks too, with
    // a mutation check, before believing any of it. Note also that this
    // module is a formally proven leaf instantiated twice and named in
    // several .sby file lists, so the four proofs and the eleven cocotb
    // tests are part of the change, not a follow-up to it.
    //
    // Pointers carry one extra wrap bit; occupancy is their difference.
    reg [AW:0] wr_ptr;
    reg [AW:0] rd_ptr;
    reg [WIDTH-1:0] mem [0:DEPTH-1];

    assign level = wr_ptr - rd_ptr;
    assign full  = (level == DEPTH[AW:0]);
    assign empty = (wr_ptr == rd_ptr);

    wire wr_ok   = wr_en && !full;   // accepted write
    wire rd_ok   = rd_en && !empty;  // accepted read
    wire wr_drop = wr_en && full;    // dropped write

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr   <= {(AW + 1){1'b0}};
            rd_ptr   <= {(AW + 1){1'b0}};
            rd_data  <= {WIDTH{1'b0}};
            rd_valid <= 1'b0;
            drop_cnt <= {DROP_W{1'b0}};
        end else begin
            if (wr_ok) begin
                mem[wr_ptr[AW-1:0]] <= wr_data;
                wr_ptr <= wr_ptr + 1'b1;
            end
            if (rd_ok) begin
                rd_data <= mem[rd_ptr[AW-1:0]];
                rd_ptr  <= rd_ptr + 1'b1;
            end
            rd_valid <= rd_ok;
            if (drop_clr)
                drop_cnt <= wr_drop ? {{(DROP_W - 1){1'b0}}, 1'b1}
                                    : {DROP_W{1'b0}};
            else if (wr_drop && drop_cnt != DROP_MAX)
                drop_cnt <= drop_cnt + 1'b1;
        end
    end

`ifdef FORMAL
`include "aer_fifo_props.v"
`endif

endmodule

`default_nettype wire
