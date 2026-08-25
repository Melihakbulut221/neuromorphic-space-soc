// Weight-SRAM ECC scrub controller (docs/10 section 11.2, register
// CTRL.SCRUB_EN of docs/regmap-npu.md). Background walker: it steps
// through the protected word window one word per visit to S_IDLE, reads
// each codeword through the SECDED decoder, and rewrites the word in
// place when the decoder reports a corrected single-bit error, so that
// upsets do not accumulate into an uncorrectable pair between two
// functional reads.
//
// This module is the CONTROL path only. It owns the address walk, the
// memory-port handshake, the writeback decision and the fault
// observability; it deliberately carries no codeword data. The SECDED
// codec (hw/rtl/secded_enc.v, hw/rtl/secded_dec.v) and the memory data
// mux live outside it, exactly as they do in hw/rtl/pilot_top.v. The data
// contract with that outside logic is one line: capture the decoder's
// corrected word on the ecc_take pulse and hold it while mem_we is
// asserted. Keeping the 72-bit codeword out of this module is what makes
// the whole block hand-auditable and its proofs cheap.
//
// Contract:
//
//   - Memory port. mem_req/mem_we/mem_addr with a single-cycle mem_gnt
//     acknowledge. The scrubber is BACKGROUND traffic and must be the
//     lowest-priority master at the arbiter: it presents a request and
//     waits, indefinitely if the functional port never yields. It never
//     asserts a request the functional path can be blocked by, because it
//     holds no grant of its own -- it only ever occupies a cycle the
//     arbiter has already decided to give it.
//
//   - Window containment. Every request is qualified by
//     mem_addr <= region_last, at the port, combinationally. This is the
//     memory-isolation property of the block and it is enforced
//     structurally rather than being inferred from the address walk being
//     correct: an upset in the address register, or a host that shrinks
//     region_last under a walk in progress, cannot produce an access
//     outside the configured window. A word whose address falls outside
//     the window is abandoned (err_win latches) and the walk restarts at
//     0 from S_IDLE, which is at most two cycles later.
//
//   - Writeback discipline. A memory write is issued if and only if the
//     immediately preceding granted read of the SAME address returned
//     ecc_valid with ecc_sec set and ecc_ded clear. A double-bit
//     detection NEVER writes back: the decoder's output for an
//     uncorrectable word is not the stored word, so rewriting it would
//     turn a detected error into a silent, permanent corruption, and the
//     substitution rule for such a word is a datapath matter (equation
//     E10, docs/10 section 11.2), not a memory-repair matter. A clean
//     word is not rewritten either, and neither is a word whose read
//     response never arrived.
//
//   - Read-response watchdog. After a granted read the controller waits
//     for ecc_valid for at most 2**WD_W - 1 cycles and then abandons the
//     word, latching err_to and advancing. This is what makes progress
//     independent of the memory returning anything at all: the controller
//     cannot be parked forever by a dead response path.
//
//   - Fault observability, all in the house style of hw/rtl/aer_fifo.v
//     and hw/rtl/npu_regbank.v: cnt_sec / cnt_ded are saturating, fault_clr
//     maps to FAULT_CLR and a fault event coincident with the clear
//     restarts the counter at 1 rather than being swallowed; ded_seen is
//     STATUS.DED_SEEN; fault_addr is the word index of the LAST
//     double-bit detection (docs/regmap-npu.md 0x080).
//
//   - SEU recovery (docs/10 section 11.4). The FSM uses the same
//     Hamming-distance-2 encoding family as hw/rtl/lif_core.v: the five
//     codewords are even-parity 4-bit words, so every single-bit upset
//     lands on an odd-parity word that no legal transition can produce.
//     All eleven illegal words take the default arm, which parks the
//     controller in S_SAFE and latches err_cfg (STATUS.ERR_CFG) on the
//     next edge -- K = 1. S_SAFE issues no request, takes no capture,
//     moves no counter and freezes the address; it is left only by reset.
//     A scrub controller that kept driving a shared memory port from a
//     corrupted state is the one failure in this block that can destroy
//     data the rest of the chip depends on, so the fault state is defined
//     by what it does NOT drive.
//
// Single-word mode. scrub_step is a one-cycle pulse (the pilot's
// SCRUB_STB pin after its edge detector, hw/rtl/pilot_top.v section 5)
// that runs exactly one word even with scrub_en low. A pulse coincident
// with the start of a word is retained, not lost, by the same convention
// the aer_fifo drop counter uses for drop_clr.
//
// Parameters: AW is the word-index width of the protected region; CNT_W
// the saturating fault-counter width; WD_W the read-response watchdog
// width. All three must be >= 1 (elaboration guard below).
//
// Plain Verilog-2005, Icarus-clean; the formal properties
// (formal/scrub_props.v) are textually included under `ifdef FORMAL and
// are invisible to simulation and synthesis. The cycle-accurate reference
// model is hw/tb/test_scrub.py, which runs it against this RTL in
// lockstep every cycle (make -f Makefile.scrub in hw/tb).
`default_nettype none

module scrub #(
    parameter AW    = 10,   // protected-window word-index width
    parameter CNT_W = 16,   // saturating SEC/DED counter width
    parameter WD_W  = 4     // read-response watchdog width
) (
    input  wire              clk,
    input  wire              rst_n,

    // control (docs/regmap-npu.md CTRL.SCRUB_EN, FAULT_CLR)
    input  wire              scrub_en,     // continuous background walk
    input  wire              scrub_step,   // one-cycle single-word request
    input  wire [AW-1:0]     region_last,  // last protected word, inclusive
    input  wire              fault_clr,    // FAULT_CLR write

    // shared memory port; the scrubber is the lowest-priority master
    output wire              mem_req,
    output wire              mem_we,       // 0 = check read, 1 = writeback
    output wire [AW-1:0]     mem_addr,
    input  wire              mem_gnt,

    // SECDED result for the word returned by the granted read
    input  wire              ecc_valid,
    input  wire              ecc_sec,
    input  wire              ecc_ded,
    output wire              ecc_take,     // capture the corrected word now

    // observability
    output wire              busy,
    output wire [AW-1:0]     scrub_addr,   // walk progress telemetry
    output wire              sweep_wrap,   // one-cycle pulse at each wrap
    output wire [CNT_W-1:0]  cnt_sec,
    output wire [CNT_W-1:0]  cnt_ded,
    output wire              ded_seen,     // STATUS.DED_SEEN, sticky
    output wire [AW-1:0]     fault_addr,   // FAULT_ADDR, last DED word
    output wire              err_to,       // sticky: read response timed out
    output wire              err_win,      // sticky: address left the window
    output wire              err_cfg       // STATUS.ERR_CFG, illegal encoding
);

    // Elaboration guard, same construct as hw/rtl/aer_fifo.v: an
    // out-of-contract parameter references a module that deliberately
    // does not exist, so elaboration fails with the name as the message.
    generate
        if (AW < 1 || CNT_W < 1 || WD_W < 1) begin : g_bad_param
            ERROR_scrub_AW_CNT_W_and_WD_W_must_all_be_at_least_1 guard ();
        end
    endgenerate

    localparam [CNT_W-1:0] CNT_MAX  = {CNT_W{1'b1}};
    localparam [CNT_W-1:0] CNT_ZERO = {CNT_W{1'b0}};
    localparam [CNT_W-1:0] CNT_ONE  = {{(CNT_W - 1){1'b0}}, 1'b1};
    localparam [AW-1:0]    ADDR_ZERO = {AW{1'b0}};

    // FSM encoding (docs/10 section 11.4). The five codewords are the
    // even-parity words of a 4-bit vector, so every pair is at Hamming
    // distance >= 2, every single-bit upset lands on an odd-parity word,
    // and the eight odd-parity words plus the three unused even-parity
    // words (1010, 1100, 1111) all take the default arm.
    localparam [3:0] S_IDLE = 4'b0000,   // between words; samples requests
                     S_READ = 4'b0011,   // check read presented, awaiting grant
                     S_WAIT = 4'b0101,   // read granted, awaiting ecc_valid
                     S_WB   = 4'b0110,   // writeback presented, awaiting grant
                     S_SAFE = 4'b1001;   // parked after an illegal encoding

    reg [3:0]       state;
    reg [AW-1:0]    addr;        // word under scrub
    reg [WD_W-1:0]  wd;          // read-response watchdog
    reg             step_pend;   // single-word request latched
    reg             wrap_r;
    reg [CNT_W-1:0] cnt_sec_r;
    reg [CNT_W-1:0] cnt_ded_r;
    reg             ded_seen_r;
    reg [AW-1:0]    fault_addr_r;
    reg             err_to_r;
    reg             err_win_r;
    reg             err_cfg_r;

    // Window check against the LIVE configuration input, not against a
    // latched copy: a latched limit is itself an upset target, and the
    // property worth having is containment in the window the host has
    // configured right now.
    wire win_ok  = (addr <= region_last);
    wire in_txn  = (state == S_READ) || (state == S_WAIT) || (state == S_WB);
    wire wd_exp  = (wd == {WD_W{1'b1}});

    // Port. mem_req is qualified by win_ok, so containment is structural.
    assign mem_req    = ((state == S_READ) || (state == S_WB)) && win_ok;
    assign mem_we     = (state == S_WB);
    assign mem_addr   = addr;
    assign busy       = (state != S_IDLE);
    assign scrub_addr = addr;
    assign sweep_wrap = wrap_r;
    assign cnt_sec    = cnt_sec_r;
    assign cnt_ded    = cnt_ded_r;
    assign ded_seen   = ded_seen_r;
    assign fault_addr = fault_addr_r;
    assign err_to     = err_to_r;
    assign err_win    = err_win_r;
    assign err_cfg    = err_cfg_r;

    // The four word-terminating events. Each is qualified by a legal
    // working state, so nothing is counted, captured or advanced while
    // the controller is parked in S_SAFE or sitting on an illegal
    // encoding.
    wire ev_win = in_txn && !win_ok;                       // window left
    wire ev_to  = (state == S_WAIT) && win_ok && !ecc_valid && wd_exp;
    wire ev_sec = (state == S_WAIT) && win_ok && ecc_valid && !ecc_ded && ecc_sec;
    wire ev_ded = (state == S_WAIT) && win_ok && ecc_valid && ecc_ded;
    wire ev_ok  = (state == S_WAIT) && win_ok && ecc_valid && !ecc_ded && !ecc_sec;

    assign ecc_take = ev_sec;

    // A word retires -- and only then does the address move on. An
    // abandoned window-violating word does not advance: its address is
    // outside the window and S_IDLE restarts the walk at 0.
    wire fin_ok = ev_to || ev_ded || ev_ok ||
                  ((state == S_WB) && win_ok && mem_gnt);

    wire go         = (scrub_en || step_pend) && win_ok;
    wire start_word = (state == S_IDLE) && go;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state        <= S_IDLE;
            addr         <= ADDR_ZERO;
            wd           <= {WD_W{1'b0}};
            step_pend    <= 1'b0;
            wrap_r       <= 1'b0;
            cnt_sec_r    <= CNT_ZERO;
            cnt_ded_r    <= CNT_ZERO;
            ded_seen_r   <= 1'b0;
            fault_addr_r <= ADDR_ZERO;
            err_to_r     <= 1'b0;
            err_win_r    <= 1'b0;
            err_cfg_r    <= 1'b0;
        end else begin
            wrap_r <= 1'b0;

            // ---- state ------------------------------------------------
            case (state)
                S_IDLE: begin
                    wd <= {WD_W{1'b0}};
                    if (go)
                        state <= S_READ;
                end
                S_READ: begin
                    if (!win_ok)
                        state <= S_IDLE;
                    else if (mem_gnt) begin
                        state <= S_WAIT;
                        wd    <= {WD_W{1'b0}};
                    end
                end
                S_WAIT: begin
                    if (!win_ok)
                        state <= S_IDLE;
                    else if (ecc_valid)
                        state <= (ecc_ded || !ecc_sec) ? S_IDLE : S_WB;
                    else if (wd_exp)
                        state <= S_IDLE;
                    else
                        wd <= wd + 1'b1;
                end
                S_WB: begin
                    if (!win_ok)
                        state <= S_IDLE;
                    else if (mem_gnt)
                        state <= S_IDLE;
                end
                S_SAFE: begin
                    state <= S_SAFE;    // terminal until reset
                end
                default: begin
                    // Illegal encoding: an upset, not a reachable
                    // transition. Park and tell the host (docs/10 11.4).
                    state     <= S_SAFE;
                    err_cfg_r <= 1'b1;
                end
            endcase

            // ---- address walk -----------------------------------------
            if (fin_ok) begin
                addr   <= (addr >= region_last) ? ADDR_ZERO : (addr + 1'b1);
                wrap_r <= (addr >= region_last);
            end else if ((state == S_IDLE) && !win_ok) begin
                addr <= ADDR_ZERO;
            end

            // ---- single-word request latch ----------------------------
            if (start_word)
                step_pend <= scrub_step;
            else if (scrub_step)
                step_pend <= 1'b1;

            // ---- fault counters and sticky flags ----------------------
            // FAULT_CLR convention, verbatim from hw/rtl/aer_fifo.v: an
            // event coincident with the clear restarts the counter at 1
            // and re-sets the flag, so no fault is lost to a clear.
            if (fault_clr)
                cnt_sec_r <= ev_sec ? CNT_ONE : CNT_ZERO;
            else if (ev_sec && cnt_sec_r != CNT_MAX)
                cnt_sec_r <= cnt_sec_r + 1'b1;

            if (fault_clr)
                cnt_ded_r <= ev_ded ? CNT_ONE : CNT_ZERO;
            else if (ev_ded && cnt_ded_r != CNT_MAX)
                cnt_ded_r <= cnt_ded_r + 1'b1;

            if (fault_clr)
                ded_seen_r <= ev_ded;
            else if (ev_ded)
                ded_seen_r <= 1'b1;

            if (fault_clr)
                fault_addr_r <= ev_ded ? addr : ADDR_ZERO;
            else if (ev_ded)
                fault_addr_r <= addr;

            if (fault_clr)
                err_to_r <= ev_to;
            else if (ev_to)
                err_to_r <= 1'b1;

            if (fault_clr)
                err_win_r <= ev_win;
            else if (ev_win)
                err_win_r <= 1'b1;
        end
    end

`ifdef FORMAL
`include "scrub_props.v"
`endif

endmodule

`default_nettype wire
