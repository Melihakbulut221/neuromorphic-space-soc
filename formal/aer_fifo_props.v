// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Formal properties for aer_fifo (SymbiYosys harness, formal/aer_fifo.sby).
//
// This file is textually included inside the aer_fifo module body under
// `ifdef FORMAL (end of hw/rtl/aer_fifo.v), so it sees the internal state
// (mem, wr_ptr, rd_ptr, wr_ok, rd_ok, wr_drop, level) directly. It is
// invisible to Icarus simulation and to synthesis.
//
// EVERY property below is proven UNDER A SINGLE-REPLICA POINTER FAULT
// AND A SINGLE-BIT FAULT IN THE FETCHED QUEUE ENTRY.
// hw/rtl/aer_fifo.v declares six free fault vectors under `ifdef FORMAL,
// one per pointer replica, XORed into the replica on its way to the
// voter; they are unconstrained every cycle except for the one
// restriction TMR actually claims, at most one faulty replica per
// pointer, assumed below. So the fault-free case is the special case
// where the solver picks zero, and P1..P6 are masking theorems rather
// than statements made beside one. Nothing selects this: it is on in all
// four jobs of formal/aer_fifo.sby, and it costs nothing to run.
//
// The entry-parity fault model is the same shape and runs in the same
// four jobs. hw/rtl/aer_fifo.v declares one further free vector over the
// FETCHED codeword {check bit, data word}, free every cycle and
// constrained to the weight one check bit can claim: at most one bit
// wrong, assumed below. So P1..P6 hold under a queue-entry upset as well
// as under a pointer upset, and P10..P12 are what say an entry upset is
// discarded and counted rather than delivered as a spike.
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
//   P10 the stored-parity invariant. A slot that is currently in the
//       queue holds a check bit equal to the even parity of its data
//       word, stated over P5's anyconst slot and therefore over every
//       slot. P11 and P12 are conditioned on that slot being the one the
//       read pointer is on, which is how the invariant reaches the head.
//   P11 the detection is reported, exactly, in both directions. par_err
//       is high if and only if a read was accepted while the fetched
//       codeword actually carried an upset. No missed discard, and no
//       false discard during ordinary traffic -- the second half matters
//       as much as the first here, because a false discard is a lost
//       event manufactured by the protection itself.
//   P12 the safety theorem, and the one the campaign is about: an event
//       is never DELIVERED corrupted. Whenever rd_valid is high, rd_data
//       is the word that was written into that slot. Under the fault
//       model an upset entry is either not fetched or not flagged valid,
//       so no consumer can be handed a fabricated spike.
//   P8  the correction is reported, exactly. ptr_mismatch is high if and
//       only if a replica is actually faulty this cycle: no missed
//       correction, and no false alarm during ordinary traffic. Both
//       halves matter for a part whose product is a fault count --
//       docs/16 section 5.2 is a list of corruptions that were silent,
//       and a flag that also fired on clean cycles would be no better.
//   P14 acceptance is the PORT-LEVEL contract, not the design's own
//       opinion of it. Everything above is written in terms of wr_ok,
//       rd_ok and wr_drop, which are internal wires; the whole set is
//       therefore consistent with a design that quietly declines to
//       accept an offered write and records nothing about it. Measured,
//       not supposed: a mutant whose wr_ok additionally excludes a write
//       coincident with an accepted read -- one lost event per collision,
//       no drop counted, no flag raised -- PASSES prove, prove_d4, bmc
//       and cover as this file stood before P14 [fact, 2026-08-31]. That
//       is the same defect class docs/07 caught in the register bank's
//       lock property, where an assertion phrased over the design's own
//       locked set could not detect a wrong locked set. P14 restates the
//       header's contract over the PORTS -- wr_en, rd_en, full, empty,
//       level, drop_cnt, rd_valid, par_err -- so an offered write is
//       either taken (level rises) or dropped (drop_cnt rises), and an
//       offered read on a non-empty queue is always answered, either as
//       a delivery or as an announced discard. There is no third outcome.
//
// Checked in the resync task only (`AER_PTR_RESYNC`, mode bmc), and
// carrying docs/09 target #4b:
//   P15 replica re-convergence, N = 1. The trace starts out of reset on
//       an arbitrary state in which the three replicas of a pointer have
//       ALREADY DIVERGED -- one of them holding a value the other two do
//       not -- and with the injection vectors held at zero, i.e. with the
//       fault removed. On the next edge all three replicas hold the same
//       value again. This is the "after fault removal, replicas
//       re-converge within N cycles" clause of target #4, and N is 1.
//   P16 and they re-converge on the RIGHT value: the voted pointer of the
//       diverged cycle, advanced by the operation that cycle accepted.
//       A resync that agreed on the corrupted replica's value would
//       satisfy P15 and destroy the queue, so P15 alone is not the
//       theorem.
//   P17 during the diverged cycle itself the module is already correct
//       and already talking: the vote takes the value the two healthy
//       replicas hold, and ptr_mismatch is exactly the divergence.
//
// Why this file can carry #4b at all, when docs/09 recorded the target as
// blocked on RTL that does not exist: the resynchronization path is in
// hw/rtl/aer_fifo.v, not in hw/rtl/tmr_voter.v or hw/rtl/pilot_top.v,
// which are the two files the target row looked at. The queue's pointer
// domain computes its next state once FROM THE VOTED VALUE and loads it
// unconditionally into all three replicas, so a replica corrupted at any
// time is rewritten from the vote on the next edge; the RTL says so in
// the comment above the aer_ptr_bank instances. That is a resync path,
// it is the only one in the design, and P15/P16 are its proof. The
// configuration domain of hw/rtl/pilot_top.v still has none -- its banks
// hold their own state and are restored by a host rewrite -- so #4b is
// closed for the queue pointers and open for the configuration word, and
// docs/09 says exactly that rather than one word for both.
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

`ifdef AER_PTR_RESYNC
// =====================================================================
// P15 / P16 / P17: replica re-convergence (docs/09 target #4b)
// =====================================================================
//
// This property set REPLACES the one below rather than joining it, for
// the same reason formal/lif_ctrl.sby's bmc_safe and formal/scrub.sby's
// bmc_any carry their own sets: the starting state is different. Here the
// whole state is free -- including mem[] and the stored parity vector --
// so the invariants P5 and P10 stand on are false at step 0 by
// construction, and asserting them in this task would report a failure
// about the fault model rather than about the design.
//
// The trace starts out of reset, with the injection vectors held at ZERO
// (the fault is removed, which is the precondition the target's clause
// names) and with the replicas of at least one pointer already diverged.
// The initial state is otherwise unconstrained, so BMC at depth 2 is
// already exhaustive over every diverged state the class contains; the
// task runs deeper to show the domain stays converged and to reach the
// covers.
//
// The one restriction is the one TMR claims and no more: at least two
// replicas of each pointer agree, i.e. a majority exists. A state in
// which all three disagree is outside what a bitwise majority can
// correct, and the design does not claim it.
// ---------------------------------------------------------------------

// No injected fault: this task is about a corruption that has already
// happened and has stopped, not about one in progress. P7/P8 cover the
// in-progress case, in every other task, and there the injection is free.
always @(*) begin
    assume (f_inj_wa == {PW{1'b0}});
    assume (f_inj_wb == {PW{1'b0}});
    assume (f_inj_wc == {PW{1'b0}});
    assume (f_inj_ra == {PW{1'b0}});
    assume (f_inj_rb == {PW{1'b0}});
    assume (f_inj_rc == {PW{1'b0}});
    assume (f_inj_mem == PAR_ZERO);
end

wire f_w_diverged = (wr_ptr_a != wr_ptr_b) || (wr_ptr_a != wr_ptr_c);
wire f_r_diverged = (rd_ptr_a != rd_ptr_b) || (rd_ptr_a != rd_ptr_c);

// A majority exists on each pointer: two of the three replicas agree.
wire f_w_maj = (wr_ptr_a == wr_ptr_b) || (wr_ptr_a == wr_ptr_c)
                                      || (wr_ptr_b == wr_ptr_c);
wire f_r_maj = (rd_ptr_a == rd_ptr_b) || (rd_ptr_a == rd_ptr_c)
                                      || (rd_ptr_b == rd_ptr_c);

initial assume (rst_n);
initial assume (f_w_maj && f_r_maj);
initial assume (f_w_diverged || f_r_diverged);   // something really is wrong

// P17: the diverged cycle is already masked and already reported. Stated
// for every cycle, not only the first, so it is an iff on the flag rather
// than a statement about one step.
always @(*) if (rst_n) begin
    if (wr_ptr_b == wr_ptr_c) assert (wr_ptr == wr_ptr_b);
    if (wr_ptr_a == wr_ptr_c) assert (wr_ptr == wr_ptr_a);
    if (wr_ptr_a == wr_ptr_b) assert (wr_ptr == wr_ptr_a);
    if (rd_ptr_b == rd_ptr_c) assert (rd_ptr == rd_ptr_b);
    if (rd_ptr_a == rd_ptr_c) assert (rd_ptr == rd_ptr_a);
    if (rd_ptr_a == rd_ptr_b) assert (rd_ptr == rd_ptr_a);
    assert (ptr_mismatch == (f_w_diverged || f_r_diverged));
end

always @(posedge clk) if (f_past_valid) begin
    // P15: N = 1. One edge after ANY diverged state, with no fault
    // present, the three replicas of each pointer hold the same value.
    // This is what the unconditional load from the voted value buys, and
    // it is exactly what a per-replica increment enable would lose.
    assert (wr_ptr_a == wr_ptr_b);
    assert (wr_ptr_a == wr_ptr_c);
    assert (rd_ptr_a == rd_ptr_b);
    assert (rd_ptr_a == rd_ptr_c);

    // P16: on the right value. The corrupted replica is not what they
    // agree on -- the vote of the diverged cycle is, advanced by the
    // operation that cycle accepted. rst_n is free in this task as in
    // every other, so the guard excludes the edge on which an asserted
    // reset legitimately takes the pointers to zero instead; P15 above
    // needs no such guard, because a reset re-converges the replicas too.
    if (rst_n && $past(rst_n)) begin
        assert (wr_ptr_a == ($past(wr_ptr) + {{AW{1'b0}}, $past(wr_ok)}));
        assert (rd_ptr_a == ($past(rd_ptr) + {{AW{1'b0}}, $past(rd_ok)}));
    end
end

// Non-vacuity. If the assumptions above were ever tightened until no
// diverged state existed, P15..P17 would pass over an empty set and
// these covers would fail, which is the intended alarm.
// The divergence itself is only ever present at step 0 -- that is the
// whole claim -- so it has to be covered by an unclocked statement.
// Written as a clocked cover it is unsatisfiable by construction, which
// the cover job reported rather than left to be assumed [fact,
// 2026-08-31]; it is the same shape of correction the P13 note above
// records.
always @(*) if (rst_n) begin
    cover (ptr_mismatch);
    cover (f_w_diverged && f_r_diverged);   // both pointers hit at once
end

always @(posedge clk) if (f_past_valid && rst_n) begin
    cover ($past(ptr_mismatch) && !ptr_mismatch);          // resynchronized
    cover ($past(f_w_diverged) && !f_w_diverged && $past(wr_ok));
    cover ($past(f_r_diverged) && !f_r_diverged && $past(rd_ok));
    cover ($past(ptr_mismatch) && rd_valid);   // resync under live traffic
end

`else
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
// P14: acceptance is the contract at the PORTS
//
// Everything above this line is written over wr_ok, rd_ok and wr_drop,
// which are internal wires. A design that silently declined an offered
// write and recorded nothing would keep every one of those properties
// true, and one did: see the P14 note in the header. What follows is the
// module header's own contract, restated over the ports and nothing else.
//
//   "Overflow-safe: a write while full is dropped ... and counted"
//   "A read while empty is refused"
//   "level is exact occupancy (0..DEPTH)"
//
// f_wr_take / f_rd_take are the SPECIFICATION's acceptance conditions,
// built from the input ports and the two status outputs. They are not
// read out of the design, so a design whose acceptance differs from them
// fails here instead of being followed.
// ---------------------------------------------------------------------

wire f_wr_take = wr_en && !full;
wire f_rd_take = rd_en && !empty;

always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    // P14a: occupancy moves by exactly the operations the ports offered
    // and the flags allowed. One equation, ports only, and it is what
    // makes "no event is lost between wr_en and level" a theorem.
    assert ({1'b0, level} == ({1'b0, $past(level)}
                              + {{(AW + 1){1'b0}}, $past(f_wr_take)}
                              - {{(AW + 1){1'b0}}, $past(f_rd_take)}));

    // P14c: an offered read on a non-empty queue is always answered, and
    // there are exactly two answers -- the event is delivered on the next
    // cycle, or it is discarded and announced on this one. A refusal that
    // is neither is the read-side form of the same silent loss.
    assert ((rd_valid || $past(par_err)) == $past(f_rd_take));
end

always @(*) if (rst_n) begin
    // P14b: the design's own acceptance wires ARE the specification's
    // conditions. P14a already implies this at the level output; stating
    // it at the cut as well is what makes a counterexample readable, and
    // it pins wr_drop to the ports so that P4's counting property is
    // about offered writes rather than about whatever the design chose
    // to call a drop.
    assert (wr_ok   == f_wr_take);
    assert (rd_ok   == f_rd_take);
    assert (wr_drop == (wr_en && full));
    // ... so every offered write has exactly one outcome, and no offered
    // write has none.
    if (wr_en) assert (wr_ok ^ wr_drop);
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

// readout: each token appears on the registered output, unmodified.
//
// The qualifier is rd_pass and not rd_ok, and that is the entry-parity
// change written into P5 rather than beside it. rd_pass is "the read was
// accepted AND the fetched codeword checked", so under a single-bit
// entry upset the two differ exactly on the reads this hardening
// discards. Asserting the old form would be asserting that a corrupted
// entry is still delivered correctly, which is the claim the check
// exists to refuse; asserting this form says the delivered word is
// unmodified whenever it is delivered at all, which is P12 restated on
// the two tokens. The remaining reads are covered by P11 (they are
// reported) and by P1/P3 (they still advance the queue by exactly one).
always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    if ($past(rd_pass) && $past(rd_ptr) == f_addr1 && $past(f_in1))
        assert (rd_valid && rd_data == f_data1);
    if ($past(rd_pass) && $past(rd_ptr) == f_addr2 && $past(f_in2))
        assert (rd_valid && rd_data == f_data2);
    // rd_valid is exact: raised iff a read was accepted and checked
    assert (rd_valid == $past(rd_pass));
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

// The entry fault model: at most one bit of the fetched codeword is
// wrong. `x & (x - 1)` clears the lowest set bit, so it is zero exactly
// for a vector of weight 0 or 1 -- plain Verilog-2005, no $countones.
// This is the claim a single check bit makes and no more: an even-weight
// error passes the check and is delivered, which hw/rtl/aer_fifo.v's
// header states and hw/tb/test_aer_fifo.py measures rather than leaving
// to be discovered.
always @(*)
    assume ((f_inj_mem & (f_inj_mem - 1'b1)) == PAR_ZERO);

wire f_mem_faulty = |f_inj_mem;

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
// P10 / P11 / P12: entry parity
// ---------------------------------------------------------------------
//
// P10 is the invariant the other two stand on, and it reuses P5's
// anyconst slot rather than stating itself DEPTH times. f_addr1 is a
// symbolic constant the solver picks freely, so proving the statement
// for it proves it for every address; the first draft of this section
// wrote a generate loop over all DEPTH slots instead, on the reasoning
// that P11 needs the invariant AT rd_ptr and a symbolic constant is one
// fixed address inside a trace. That reasoning is wrong and it is
// expensive: measured on this design, sixty-four sixteen-input XOR
// reductions inside the inductive invariant took the prove job from 41
// seconds to over ten minutes without converging. The correct move is
// below -- state the invariant once, and CONDITION the properties that
// need it at the head on f_addr1 being the head. Universal
// quantification over f_addr1 then delivers them at every reachable head
// address, which is what "for all a: a == rd_ptr -> P(a)" means.
//
// Inductiveness, which is the same argument P5's mem invariant makes:
// the only writer of both fields is `if (wr_ok)`, which sets mem[wr_idx]
// and the bank's bit from the same wr_data on the same edge, so a slot
// entering the queue enters it consistent; a slot leaving the queue
// drops out of f_in1; and while a slot is in the queue neither field
// moves, because the write index is the tail and the tail is not in the
// queue unless the queue is full, when there is no write.

always @(*) if (rst_n) begin
    // P10: an in-flight slot's check bit is the even parity of its word.
    // Both of P5's tokens, not just the first: P5's readout assertions
    // are now qualified by rd_pass, and rd_pass carries information only
    // where the invariant holds. Measured -- with the invariant stated
    // for f_addr1 alone, the induction step fails on token TWO's readout
    // (aer_fifo_props.v:205), because the solver is free to start in a
    // state where slot f_addr2 holds a check bit that is not its word's
    // parity, pass the check with a compensating injection, and deliver
    // a word that is not f_data2.
    if (f_in1)
        assert (par_shadow[f_addr1[AW-1:0]] == ^mem[f_addr1[AW-1:0]]);
    if (f_in2)
        assert (par_shadow[f_addr2[AW-1:0]] == ^mem[f_addr2[AW-1:0]]);

    // P11: exact reporting, both directions, on P8's footing. The
    // forward half says an upset entry is never handed over quietly; the
    // reverse half says the protection never invents a loss of its own,
    // which for a structure whose whole output is a discard matters just
    // as much -- a checker that fired on clean traffic would destroy
    // events at the rate the queue runs at.
    //
    // Qualified by the anyconst slot being the one the read pointer is
    // on, which is how P10 reaches the head; f_in1 is implied by
    // rd_ok && f_addr1 == rd_ptr, since a read is accepted only when the
    // queue is not empty.
    if (rd_ok && f_addr1 == rd_ptr)
        assert (par_err == f_mem_faulty);

    // ... and the half that needs no invariant at all: when no read is
    // accepted there is nothing to discard and nothing to report,
    // whatever any slot holds.
    if (!rd_ok)
        assert (!par_err);
end

always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    // P12: no corrupted event is ever DELIVERED. If the fetched codeword
    // carried an upset, rd_valid cannot be high on the following cycle,
    // so a consumer is never handed a word that is not the word that was
    // written. Stated on the injection vector rather than on mem[] so
    // that it is one assertion about every slot rather than a statement
    // about P5's two tokens.
    //
    // Under the weight-one fault model the whole vector is asserted
    // zero, not just its data field: an upset in the check BIT is also
    // refused, which is a good event discarded rather than a bad one
    // delivered. That is the safe direction to fail in and it is the
    // price of putting the check bit inside the codeword it protects;
    // P11 reports it and hw/tb/test_aer_fifo.py measures it.
    if (rd_valid && $past(f_addr1 == rd_ptr))
        assert ($past(f_inj_mem) == PAR_ZERO);
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

// "an entry has been discarded at some point in this trace", for P13.
reg f_seen_par;
initial f_seen_par = 1'b0;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        f_seen_par <= 1'b0;
    else if (par_err)
        f_seen_par <= 1'b1;
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
    // P13: the entry-parity fault model is not vacuous either. A stored
    // word is fetched, fails its check and is discarded; and the queue
    // goes on to deliver a good event AFTERWARDS, which is what says the
    // discard consumed the entry rather than parking the read pointer on
    // it. If the assumption above were ever tightened into vacuity, P11
    // and P12 would still pass and these two covers would fail.
    //
    // The second one is written against the sticky f_seen_par and not
    // against $past(par_err), and that is a correction rather than a
    // preference: par_err high at cycle t means rd_pass was LOW at t,
    // and rd_valid at t+1 is exactly $past(rd_pass), so
    // `$past(par_err) && rd_valid` is unsatisfiable by construction.
    // The cover job found it -- unreached at depth 150 -- which is the
    // job doing its work on the property file rather than on the design
    // [fact, 2026-08-30].
    cover (par_err);
    cover (rd_valid && f_seen_par);
end

`endif  // AER_PTR_RESYNC
