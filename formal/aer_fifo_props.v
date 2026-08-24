// Formal properties for aer_fifo (SymbiYosys harness, formal/aer_fifo.sby).
//
// This file is textually included inside the aer_fifo module body under
// `ifdef FORMAL (end of hw/rtl/aer_fifo.v), so it sees the internal state
// (mem, wr_ptr, rd_ptr, wr_ok, rd_ok, wr_drop, level) directly. It is
// invisible to Icarus simulation and to synthesis.
//
// Proven by k-induction (mode prove):
//   P1  level bookkeeping: level == accepted writes - accepted reads,
//       level <= DEPTH, and pointers advance by exactly 0 or 1.
//   P2  no spurious empty/full: the flags are exact functions of level,
//       never both, and follow single-op transitions.
//   P3  never overflow-corrupts: a write while full changes neither the
//       write pointer nor the level (count invariant); a read while empty
//       changes nothing.
//   P4  drop bookkeeping: the sticky counter increments exactly on a
//       dropped write, saturates instead of wrapping, and clears by
//       drop_clr (coincident drop restarts at 1).
//   P5  FIFO order preservation (two-token method): two arbitrary
//       consecutively written events are read out in order, unmodified,
//       on the registered output.
//
// Reset is left free after the initial state, so the proof also covers
// reset-mid-traffic behavior.

reg f_past_valid;
initial f_past_valid = 1'b0;
always @(posedge clk)
    f_past_valid <= 1'b1;

// Start in reset so the induction base matches hardware bring-up.
initial assume (!rst_n);

// ---------------------------------------------------------------------
// P1 / P3: accepted-operation accounting (count invariant)
// ---------------------------------------------------------------------

reg [31:0] f_writes, f_reads;
initial begin
    f_writes = 32'd0;
    f_reads  = 32'd0;
end
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        f_writes <= 32'd0;
        f_reads  <= 32'd0;
    end else begin
        if (wr_ok) f_writes <= f_writes + 32'd1;
        if (rd_ok) f_reads  <= f_reads + 32'd1;
    end
end

always @(*) if (rst_n) begin
    assert (level <= DEPTH[AW:0]);                        // P1
    assert (f_writes - f_reads == {{(31 - AW){1'b0}}, level});  // P1/P3
end

always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    // pointers move by exactly the accepted operation, nothing else
    assert (wr_ptr == $past(wr_ptr) + {{AW{1'b0}}, $past(wr_ok)});  // P1
    assert (rd_ptr == $past(rd_ptr) + {{AW{1'b0}}, $past(rd_ok)});  // P1
    // P3: a dropped write must not advance the write side
    if ($past(wr_drop))
        assert (wr_ptr == $past(wr_ptr));
end

// ---------------------------------------------------------------------
// P2: no spurious empty/full
// ---------------------------------------------------------------------

always @(*) if (rst_n) begin
    assert (empty == (level == {(AW + 1){1'b0}}));
    assert (full  == (level == DEPTH[AW:0]));
    assert (!(full && empty));
end

always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    if ($past(wr_ok) && !$past(rd_ok)) assert (!empty);
    if ($past(rd_ok) && !$past(wr_ok)) assert (!full);
    if (!$past(wr_ok) && !$past(rd_ok)) assert (level == $past(level));
end

// ---------------------------------------------------------------------
// P4: sticky drop counter bookkeeping
// ---------------------------------------------------------------------

always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    if ($past(drop_clr))
        assert (drop_cnt == ($past(wr_drop) ? {{(DROP_W - 1){1'b0}}, 1'b1}
                                            : {DROP_W{1'b0}}));
    else if ($past(wr_drop) && $past(drop_cnt) != DROP_MAX)
        assert (drop_cnt == $past(drop_cnt) + 1'b1);
    else
        assert (drop_cnt == $past(drop_cnt));  // sticky, saturating
end

// ---------------------------------------------------------------------
// P5: order preservation, two-token method. f_addr1/f_addr2 are two
// arbitrary consecutive slots in the extended (wrap-bit) pointer domain;
// the solver picks them, so the proof covers every pair of consecutive
// writes. Their payloads are pinned by assumption and checked on readout.
// ---------------------------------------------------------------------

(* anyconst *) reg [AW:0] f_addr1;
wire [AW:0] f_addr2 = f_addr1 + 1'b1;
(* anyconst *) reg [WIDTH-1:0] f_data1, f_data2;

// token k is inside the FIFO iff its slot lies between the pointers
wire f_in1 = (f_addr1 - rd_ptr) < level;
wire f_in2 = (f_addr2 - rd_ptr) < level;

always @(*) begin
    if (wr_ok && wr_ptr == f_addr1) assume (wr_data == f_data1);
    if (wr_ok && wr_ptr == f_addr2) assume (wr_data == f_data2);
end

// stored tokens are never corrupted while in flight (induction invariant)
always @(*) if (rst_n) begin
    if (f_in1) assert (mem[f_addr1[AW-1:0]] == f_data1);
    if (f_in2) assert (mem[f_addr2[AW-1:0]] == f_data2);
    // and token 1 always sits closer to the read pointer than token 2
    if (f_in1 && f_in2)
        assert ((f_addr1 - rd_ptr) < (f_addr2 - rd_ptr));
end

// readout: each token appears on the registered output, unmodified
always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    if ($past(rd_ok) && $past(rd_ptr) == f_addr1 && $past(f_in1))
        assert (rd_valid && rd_data == f_data1);
    if ($past(rd_ok) && $past(rd_ptr) == f_addr2 && $past(f_in2))
        assert (rd_valid && rd_data == f_data2);
    // rd_valid is exact: raised iff a read was accepted
    assert (rd_valid == $past(rd_ok));
    if (!$past(rd_ok))
        assert (rd_data == $past(rd_data));  // registered output holds
end

// ---------------------------------------------------------------------
// Reachability covers: the interesting states are not vacuous
// ---------------------------------------------------------------------

reg f_seen_full;
initial f_seen_full = 1'b0;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        f_seen_full <= 1'b0;
    else if (full)
        f_seen_full <= 1'b1;
end

always @(posedge clk) if (f_past_valid && rst_n) begin
    cover (full);
    cover (empty && f_seen_full);  // a FIFO that was once full was drained
    cover ($past(wr_drop) && rd_valid);
    cover (drop_cnt == 2);
end
