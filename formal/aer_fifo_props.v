// Formal properties for aer_fifo (SymbiYosys harness, formal/aer_fifo.sby).
//
// This file is textually included inside the aer_fifo module body under
// `ifdef FORMAL (end of hw/rtl/aer_fifo.v), so it sees the internal state
// (mem, wr_ptr, rd_ptr, wr_ok, rd_ok, wr_drop, level) directly. It is
// invisible to Icarus simulation and to synthesis.
//
// EVERY property below is proven UNDER A SINGLE-REPLICA POINTER FAULT.
// hw/rtl/aer_fifo.v declares six free fault vectors under `ifdef FORMAL,
// one per pointer replica, XORed into the replica on its way to the
// voter; they are unconstrained every cycle except for the one
// restriction TMR actually claims, at most one faulty replica per
// pointer, assumed below. So the fault-free case is the special case
// where the solver picks zero, and P1..P6 are masking theorems rather
// than statements made beside one. Nothing selects this: it is on in all
// four jobs of formal/aer_fifo.sby, and it costs nothing to run.
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
//   P7  pointer TMR masking. The three replicas of each pointer agree
//       with each other at all times, and the VOTED pointer is
//       bit-identical to a fault-free reference count of the accepted
//       operations, whatever the faulty replica is doing. Everything
//       this module presents -- level, full, empty, the mem[] index,
//       and through them rd_data and rd_valid -- is a function of the
//       voted pointers alone, so P7 is what makes P1..P6 hold under a
//       fault, and P1..P6 are what say the masking is complete.
//   P8  the correction is reported, exactly. ptr_mismatch is high if and
//       only if a replica is actually faulty this cycle: no missed
//       correction, and no false alarm during ordinary traffic. Both
//       halves matter for a part whose product is a fault count --
//       docs/16 section 5.2 is a list of corruptions that were silent,
//       and a flag that also fired on clean cycles would be no better.
//
// Checked by reachability (mode cover):
//   P6  the read port is registered and NOT show-ahead. P5 pins the
//       timing from above (rd_valid is exactly $past(rd_ok) and rd_data
//       holds otherwise); P6 pins the shape from below by exhibiting a
//       state in which a word is queued and rd_data is not that word.
//       See the aer_fifo.v header: two consumers are built on this shape,
//       and if the queue is ever made first-word-fall-through this cover
//       goes unreachable and the job fails, which is the intended alarm.
//
// Checked by reachability (mode cover), added with the pointer TMR:
//   P9  a corrected upset is reachable while the queue is doing work,
//       so P8's flag is not vacuously false and P7's masking is not
//       proven over an empty set of faults.
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
// P7 / P8: pointer TMR. The fault model, first, because everything here
// depends on it being exactly the claim the hardware makes.
//
// f_inj_* are the six free vectors declared in hw/rtl/aer_fifo.v. Each
// is XORed into one replica between the bank and the voter, and each is
// free EVERY CYCLE and over every bit, so this covers a single-cycle
// strike, a replica stuck wrong for an unbounded time, and a fault that
// moves from one replica to another between cycles. The single
// assumption is at most one faulty replica per pointer at a time, which
// is what a bitwise majority over three can correct and no more. The two
// pointers are constrained independently, so one faulty replica in each
// at the same time is inside the proof.
//
// Injecting at the replica's output rather than at its stored bits is
// exact here and not a simplification: every bank is reloaded from the
// voted value on every edge, so a corrupted output and corrupted storage
// have identical consequences at every net in the module.
// ---------------------------------------------------------------------

wire f_w_bad_a = |f_inj_wa;
wire f_w_bad_b = |f_inj_wb;
wire f_w_bad_c = |f_inj_wc;
wire f_r_bad_a = |f_inj_ra;
wire f_r_bad_b = |f_inj_rb;
wire f_r_bad_c = |f_inj_rc;

always @(*) begin
    assume (!(f_w_bad_a && f_w_bad_b));
    assume (!(f_w_bad_a && f_w_bad_c));
    assume (!(f_w_bad_b && f_w_bad_c));
    assume (!(f_r_bad_a && f_r_bad_b));
    assume (!(f_r_bad_a && f_r_bad_c));
    assume (!(f_r_bad_b && f_r_bad_c));
end

wire f_ptr_faulty = f_w_bad_a || f_w_bad_b || f_w_bad_c
                 || f_r_bad_a || f_r_bad_b || f_r_bad_c;

always @(*) if (rst_n) begin
    // P7a: the replicas themselves never diverge. Each is loaded from
    // the voted value, so a fault is corrected at the next edge rather
    // than accumulated -- this is the property that the voted-feedback
    // shape buys, and without it a second upset would meet a domain
    // already carrying the first.
    assert (wr_ptr_a == wr_ptr_b);
    assert (wr_ptr_a == wr_ptr_c);
    assert (rd_ptr_a == rd_ptr_b);
    assert (rd_ptr_a == rd_ptr_c);

    // P7b: the masking theorem. f_writes / f_reads are the fault-free
    // reference: they count accepted operations and are not part of the
    // hardware. The voted pointer equals that count exactly, so no
    // reachable fault of the assumed class can move it by a single
    // event -- which is the whole list of corruption modes docs/16
    // section 5.2 recorded (bursts re-emitted, events duplicated, lost,
    // fabricated, or an unwritten slot presented as a spike).
    assert (wr_ptr == f_writes[AW:0]);
    assert (rd_ptr == f_reads[AW:0]);

    // P8: exact reporting, both directions.
    assert (ptr_mismatch == f_ptr_faulty);
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
    // P6: a word is queued and the read port is not presenting it. Only
    // a registered-output queue can reach this state.
    cover (!empty && rd_data != mem[rd_ptr[AW-1:0]]);
    // P9: a pointer upset is corrected while the queue is delivering an
    // event. If the fault model were ever constrained into vacuity --
    // an assumption tightened until no fault is reachable -- P7 and P8
    // would still pass and this cover would fail, which is the intended
    // alarm.
    cover (ptr_mismatch && rd_valid);
    cover (ptr_mismatch && full);
end
