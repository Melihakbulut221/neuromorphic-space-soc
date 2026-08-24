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
// DEPTH must be a power of two. Plain Verilog-2001, Icarus-clean; the
// formal properties (formal/aer_fifo_props.v) are textually included under
// `ifdef FORMAL and are invisible to simulation and synthesis.
`default_nettype none

module aer_fifo #(
    parameter WIDTH  = 16,             // AER event word width (docs/10 section 7.1)
    parameter DEPTH  = 64,             // entries, power of two (EVQ_*_DEPTH)
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

    localparam [DROP_W-1:0] DROP_MAX = {DROP_W{1'b1}};

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
