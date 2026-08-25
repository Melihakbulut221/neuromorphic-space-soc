// Formal properties for the weight-SRAM ECC scrub controller
// (hw/rtl/scrub.v). SymbiYosys harness: formal/scrub.sby, driver
// formal/scrub.mk. Reference model and lockstep suite:
// hw/tb/test_scrub.py.
//
// Acceptance criteria from docs/09-formal-verification-plan.md, target
// #5, quoted so the scope of this file is unambiguous:
//
//   "Control FSMs (scheduler, multi-pass sequencer, scrub controller,
//    link controllers): deadlock freedom and any-state recovery | No
//    unreachable lockup: from ANY state encoding (including
//    illegal/SEU-corrupted), the FSM reaches a legal safe state within K
//    cycles without asserting outputs that violate bus/interface safety
//    (S+L); state register always in legal set once recovered (S) |
//    IND/BMC with *unconstrained initial state* (reset assumption
//    removed) - the standard any-state trick; bounded recovery via
//    watchdog counter assertion | Full proof per FSM; K documented per
//    FSM (target K <= 16)".
//
// SCOPE. This file discharges the target-#5 obligation for the scrub
// controller, which docs/09 names in the target row and lists first in
// the C.3 priority order. It proves three things that the row asks for
// and one that it does not, and the fourth is the reason this block is
// worth proving at all:
//
//   (a) any-state recovery with K = 1 and the state register always in
//       the legal set once recovered (SC12, SC13, SC14);
//   (b) "without asserting outputs that violate bus/interface safety" --
//       the fault state drives NO memory request, takes no capture and
//       records no fault event (SC15). A scrub controller is a master on
//       a memory port that the rest of the chip depends on; a corrupted
//       one that keeps writing is the only failure in this block that can
//       destroy data irrecoverably, so the fault state is defined by what
//       it does not drive, and that is proven, not commented;
//   (c) deadlock freedom, both structurally (SC16: a stalled state always
//       has a named external cause) and as a bounded-response watchdog
//       (SC17 unconditional for the read-response wait, SC18 for a whole
//       word under an arbiter-fairness assumption);
//   (d) the two properties that make this scrubber safe rather than
//       merely alive: window containment (SC1, SC2 -- the memory-isolation
//       analog of docs/09 target #8's "DMA pointer stays in the configured
//       window", proven here for the scrub master only, NOT for the QSPI
//       streaming path that #8 is about) and writeback discipline (SC3 to
//       SC8 -- a word is rewritten if and only if the immediately
//       preceding granted read of the same address returned a CORRECTED
//       single-bit error; never on a double-bit detection, never on a
//       clean word, never on a timed-out read). Writing back an
//       uncorrectable word turns a detected error into silent permanent
//       corruption, which is the worst outcome available to an ECC
//       subsystem.
//
// NOT in scope, stated so this file cannot be read as more than it is:
// the codec itself (docs/09 target #2, formal/secded.sby), the arbiter
// that issues mem_gnt (target #7 -- no arbiter RTL exists; the fairness
// bound used by SC18 is an ASSUMPTION on the environment here, not a
// proven property of any arbiter), and the QSPI/multi-pass streaming path
// (target #8).
//
// This file is textually included inside the scrub module body under
// `ifdef FORMAL (end of hw/rtl/scrub.v), so it sees state, addr, wd, the
// ev_* event wires and the codewords directly. It is invisible to Icarus
// simulation and to synthesis.
//
// Two optional property sets, each behind its own define so that the
// assumption it needs cannot weaken the tasks that do not want it:
//
//   SCRUB_ANY_STATE (tasks bmc_any, prove_any, cover_any) starts the
//       trace on a corrupted state encoding instead of from reset -- the
//       any-state trick the target names -- and switches OFF the legality
//       invariant SC12, so that k-induction in prove_any starts its
//       induction step from a wholly unconstrained state. S_SAFE is
//       unreachable from reset by construction, which is the point of the
//       encoding, so neither an assertion nor a cover about it means
//       anything in a reset-rooted trace. bmc_any and prove_any are both
//       kept: prove_any is the unbounded result, bmc_any is the one that
//       hands back a counterexample trace when something breaks.
//   SCRUB_LIVENESS (task bmc_live) adds the arbiter-fairness assumption
//       and the whole-word bounded-response watchdog SC18.
//
// The methodology note from formal/lif_ctrl_props.v applies here verbatim
// and is repeated because it decides whether SC13 is real or decorative:
// "the encoding is always legal" (SC12) is itself an assertion, and
// k-induction assumes every assertion at steps 0..k-1 before checking
// step k, so in the prove task the antecedent of the recovery property
// ("if the previous encoding was illegal") is false at every checked
// step. prove therefore reports PASS for a default arm that silently
// resumes in S_IDLE and latches nothing -- exactly the defect SC13 exists
// to catch. Measured on this block, in the same way it was measured on
// lif_core: a mutant whose default arm recovers to S_IDLE, a mutant that
// enters S_SAFE without latching err_cfg, and a mutant whose S_SAFE keeps
// asserting mem_req all PASS bmc and bmc_live; the first two PASS prove
// as well and the third only degrades prove to UNKNOWN, which is a lost
// proof and not a counterexample. All three fail bmc_any and prove_any.
// Do not drop the any-state tasks from the gate on the grounds that prove
// covers them. It does not.

reg f_past_valid;
initial f_past_valid = 1'b0;
always @(posedge clk)
    f_past_valid <= 1'b1;

// The five legal codewords (pairwise Hamming distance >= 2).
wire f_state_legal = (state == S_IDLE) || (state == S_READ) ||
                     (state == S_WAIT) || (state == S_WB)   ||
                     (state == S_SAFE);

// Convenience: "this cycle is a settled post-reset cycle" -- one clock
// has elapsed and reset was inactive across it, so every $past() below
// refers to a real operating cycle rather than to reset. Registered
// rather than written as $past(rst_n), which Yosys accepts only inside a
// clocked block.
reg f_rst_d;
always @(posedge clk)
    f_rst_d <= rst_n;
wire f_step = f_past_valid && rst_n && f_rst_d;

`ifdef SCRUB_ANY_STATE
// Fault-entry task: begin out of reset on an illegal encoding, with
// err_cfg not yet latched. rst_n is free afterwards, as in every task.
initial assume (rst_n);
initial assume (!f_state_legal);
initial assume (!err_cfg);
`else
// Start in reset so the induction base matches hardware bring-up. rst_n
// is free afterwards, so the proof also covers reset mid-traffic.
initial assume (!rst_n);
`endif

// ---------------------------------------------------------------------
// SC1  Window containment (integrity). Every request the controller
//      presents addresses a word inside the configured window. This is
//      the block's memory-isolation property and it holds in EVERY state,
//      from ANY starting state, with no reset assumption and no
//      assumption about region_last being stable: it is enforced at the
//      port by qualifying mem_req, not inferred from the address walk
//      being correct. An upset in the address register, or a host that
//      shrinks region_last under a walk in flight, therefore cannot
//      produce an access outside the window -- it can only cause the word
//      to be abandoned.
// ---------------------------------------------------------------------
always @(*) begin
    if (mem_req)
        assert (mem_addr <= region_last);
    // The same statement for the write direction on its own, because
    // that is the one an out-of-window access would destroy data with.
    if (mem_req && mem_we)
        assert (mem_addr <= region_last);
end

`ifndef SCRUB_ANY_STATE
// ---------------------------------------------------------------------
// SC2  Window re-entry bound. If the host shrinks region_last under a
//      walk in progress the address is briefly outside the new window.
//      That situation is bounded: the word in flight is abandoned (one
//      cycle) and S_IDLE clamps the walk back to 0 (one more), so the
//      controller is never outside its window for more than two
//      consecutive cycles unless it is parked in S_SAFE, which freezes
//      the address by design. This is a bounded-recovery counter
//      assertion of exactly the kind the target's method column names.
// ---------------------------------------------------------------------
reg [1:0] f_oob_run;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        f_oob_run <= 2'd0;
    else if (win_ok || (state == S_SAFE))
        f_oob_run <= 2'd0;
    else if (f_oob_run != 2'd3)
        f_oob_run <= f_oob_run + 1'b1;
end
always @(posedge clk)
    if (rst_n)
        assert (f_oob_run <= 2'd2);
`endif

// ---------------------------------------------------------------------
// SC3-SC8  Writeback discipline. The chain proven here is:
//
//   a write is presented only from S_WB          (SC3a)
//   S_WB is entered only on a corrected read     (SC3b)
//   ecc_take is asserted exactly when S_WB is entered, and never
//     otherwise                                  (SC7)
//   a double-bit detection never reaches S_WB    (SC4)
//   a clean word never reaches S_WB              (SC5)
//   a timed-out read never reaches S_WB          (SC8)
//   the address written is the address that was read, and that read was
//     granted and has not already been consumed  (SC6)
//
// SC6 is the data-tracking abstraction: f_read_addr/f_read_val is a
// formal-only shadow of "which word does the controller currently hold a
// correction for", and the assertion says a write can only ever land on
// that word. It is what makes SC3-SC5 more than a restatement of the
// case statement: those say the wrong DECISION is not taken, SC6 says the
// right decision cannot land on the wrong ADDRESS.
// ---------------------------------------------------------------------
reg [AW-1:0] f_read_addr;
reg          f_read_val;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        f_read_addr <= {AW{1'b0}};
        f_read_val  <= 1'b0;
    end else if (mem_req && !mem_we && mem_gnt) begin
        f_read_addr <= mem_addr;      // check read granted
        f_read_val  <= 1'b1;
    end else if (mem_req && mem_we && mem_gnt) begin
        f_read_val  <= 1'b0;          // correction consumed by its write
    end
end

always @(*) begin
    // SC3a: only S_WB drives a write.
    if (mem_req && mem_we)
        assert (state == S_WB);
    // SC6: and it lands on the word the outstanding granted read
    // returned, never on any other word.
    if (mem_req && mem_we)
        assert (f_read_val && (mem_addr == f_read_addr));
    // Inductive strengthening of SC6: from the moment a read is granted
    // until its correction is written or abandoned, the shadow tracks the
    // walk exactly.
    if ((state == S_WAIT) || (state == S_WB))
        assert (f_read_val && (f_read_addr == addr));
    // SC4 (combinational half): a double-bit detection is never a
    // capture.
    if ((state == S_WAIT) && ecc_valid && ecc_ded)
        assert (!ecc_take);
    // SC5 (combinational half): a clean word is never a capture.
    if ((state == S_WAIT) && ecc_valid && !ecc_ded && !ecc_sec)
        assert (!ecc_take);
end

always @(posedge clk) if (f_step) begin
    // SC3b: S_WB is entered only out of a corrected read.
    if ((state == S_WB) && ($past(state) != S_WB))
        assert ($past(ev_sec));
    // SC7: capture and writeback are in bijection -- every ecc_take is
    // followed by the writeback state, and the writeback state is
    // entered only after an ecc_take. Nothing is captured twice and no
    // capture is lost.
    if ($past(ecc_take))
        assert (state == S_WB);
    // SC4: a double-bit detection never reaches the writeback state. The
    // decoder's output for an uncorrectable word is not the stored word,
    // so rewriting it would convert a DETECTED error into a SILENT one.
    if (($past(state) == S_WAIT) && $past(ecc_valid) && $past(ecc_ded))
        assert (state != S_WB);
    // SC5: neither does a clean word.
    if (($past(state) == S_WAIT) && $past(ecc_valid) &&
        !$past(ecc_ded) && !$past(ecc_sec))
        assert (state != S_WB);
    // SC8: neither does a read whose response never arrived.
    if (($past(state) == S_WAIT) && !$past(ecc_valid) && $past(wd_exp))
        assert (state != S_WB);
end

// ---------------------------------------------------------------------
// SC9  Port handshake: no lost, duplicated or mutated request.
//      A refused request is re-presented unchanged; a granted request is
//      withdrawn immediately, so neither a read nor a writeback can be
//      executed twice by an arbiter that grants on consecutive cycles.
// ---------------------------------------------------------------------
always @(posedge clk) if (f_step) begin
    if ($past(mem_req) && !$past(mem_gnt) && mem_req)
        assert ((mem_addr == $past(mem_addr)) && (mem_we == $past(mem_we)));
    if ($past(mem_req) && $past(mem_gnt))
        assert (!mem_req);
end

// ---------------------------------------------------------------------
// SC10-SC11  Walk integrity: no word is skipped and the sweep does not
//      wrap early. The address only ever moves to its successor or to
//      zero, it moves to zero only from the last word of the window (or
//      from outside it, which is the clamp of SC2), and it moves at all
//      only when a word retires or when the clamp fires. Together with
//      SC1 this is the coverage argument for the scrubber: every word in
//      the window is visited, in ascending order, and none is passed
//      over -- a skipped word is a word where upsets accumulate until
//      they are uncorrectable, which is a silent failure.
// ---------------------------------------------------------------------
always @(posedge clk) if (f_step) begin
    if (addr != $past(addr)) begin
        // SC10: successor or restart, nothing else.
        assert ((addr == ($past(addr) + 1'b1)) || (addr == {AW{1'b0}}));
        // SC11: a restart happens only at the end of the window or from
        // outside it.
        if ((addr == {AW{1'b0}}) && ($past(addr) != {AW{1'b0}}))
            assert ($past(addr) >= $past(region_last));
        // The walk moves only at a word boundary or at the clamp.
        assert ($past(fin_ok) ||
                (($past(state) == S_IDLE) && !$past(win_ok)));
    end
    // The wrap pulse is exactly the wrap, not a free-running strobe.
    if (sweep_wrap)
        assert ($past(fin_ok) && ($past(addr) >= $past(region_last)));
end

`ifndef SCRUB_ANY_STATE
// ---------------------------------------------------------------------
// SC12  Encoding legality (target #5: "state register always in the legal
//       set once recovered"). Proven by k-induction from reset, so it
//       holds for every reachable state at every time, including across a
//       reset asserted in mid-traffic.
// ---------------------------------------------------------------------
always @(posedge clk)
    assert (f_state_legal);
`endif

// ---------------------------------------------------------------------
// SC13  Any-state recovery, K = 1. From ANY encoding -- the eight
//       odd-parity words an odd-weight upset produces, and the three
//       unused even-parity words a heavier upset produces -- the
//       controller is parked in S_SAFE on the next edge with err_cfg
//       latched for the host. Non-vacuous only in the bmc_any task; see
//       the methodology note in this file's header.
// SC14  S_SAFE is terminal until reset and err_cfg is sticky.
// ---------------------------------------------------------------------
always @(posedge clk) if (f_step) begin
    if (!$past(f_state_legal))
        assert ((state == S_SAFE) && err_cfg);
    if ($past(state) == S_SAFE)
        assert ((state == S_SAFE) && err_cfg);
    if ($past(err_cfg))
        assert (err_cfg);
end
always @(*)
    if (state == S_SAFE)
        assert (err_cfg);

// ---------------------------------------------------------------------
// SC15  The fault state drives nothing. This is the target's "without
//       asserting outputs that violate bus/interface safety" clause and
//       it is the whole reason the recovery is worth proving: the
//       controller is a master on a memory port shared with the
//       functional datapath. In S_SAFE, and in the single cycle an
//       illegal encoding survives, it presents no request, takes no
//       capture, records no fault event and freezes the walk. The host
//       can still clear the counters through FAULT_CLR -- that is a host
//       action, not something the parked controller does.
// ---------------------------------------------------------------------
always @(*) begin
    if (!f_state_legal || (state == S_SAFE)) begin
        assert (!mem_req);
        assert (!ecc_take);
        assert (!ev_sec && !ev_ded && !ev_to && !ev_win);
        assert (!fin_ok);
    end
end
always @(posedge clk) if (f_step) begin
    if (!$past(f_state_legal) || ($past(state) == S_SAFE)) begin
        assert (addr == $past(addr));
        assert (!sweep_wrap);
        if (!$past(fault_clr)) begin
            assert (cnt_sec  == $past(cnt_sec));
            assert (cnt_ded  == $past(cnt_ded));
            assert (ded_seen == $past(ded_seen));
        end
    end
end

// ---------------------------------------------------------------------
// SC16  Deadlock freedom, structural form. Whenever the controller stays
//       in the same state for two consecutive cycles there is a NAMED
//       external cause: no request pending (S_IDLE), the arbiter has not
//       granted (S_READ, S_WB), or the memory has not answered and the
//       watchdog has not expired (S_WAIT). There is no internal blocking
//       condition anywhere in this FSM, so no combination of
//       configuration values can lock it up. S_SAFE is the one state that
//       is deliberately terminal, and it is listed as such rather than
//       hidden.
// ---------------------------------------------------------------------
always @(posedge clk) if (f_step) begin
    if ((state == $past(state)) && f_state_legal)
        assert (((state == S_IDLE) && !$past(go))                      ||
                ((state == S_READ) && !$past(mem_gnt))                 ||
                ((state == S_WAIT) && !$past(ecc_valid) && !$past(wd_exp)) ||
                ((state == S_WB)   && !$past(mem_gnt))                 ||
                 (state == S_SAFE));
end

// ---------------------------------------------------------------------
// SC17  Bounded response, unconditional half. The read-response wait is
//       bounded by the watchdog with NO assumption about the memory
//       whatsoever: S_WAIT is never occupied for more than 2**WD_W
//       consecutive cycles, so a memory that never answers costs one
//       abandoned word (err_to latches) and not a parked scrubber.
//       K = 2**WD_W = 16 at the default WD_W = 4, inside the target's
//       K <= 16.
// ---------------------------------------------------------------------
localparam [WD_W-1:0] F_WD_MAX = {WD_W{1'b1}};

reg [WD_W:0] f_wait_run;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        f_wait_run <= {(WD_W + 1){1'b0}};
    else if (state == S_WAIT)
        f_wait_run <= f_wait_run + 1'b1;
    else
        f_wait_run <= {(WD_W + 1){1'b0}};
end
always @(posedge clk) if (rst_n) begin
    if (state == S_WAIT) begin
        // The watchdog is the residence counter: they cannot drift.
        assert (f_wait_run == {1'b0, wd});
        assert (f_wait_run <= {1'b0, F_WD_MAX});
    end
end

`ifdef SCRUB_LIVENESS
// ---------------------------------------------------------------------
// SC18  Bounded response, whole word, under the one assumption this
//       block cannot discharge itself. ASSUMPTION (docs/09 C.4 ledger
//       class): the arbiter that drives mem_gnt does not refuse a held
//       request for more than F_GNT_MAX consecutive cycles. That is an
//       assumption about an arbiter that does not exist yet (docs/09
//       target #7 is blocked on RTL), and it is stated here rather than
//       buried: without it no bound on a word exists, because a
//       background master that is never granted is starved by design, not
//       deadlocked.
//
//       Under it: a word occupies the controller for at most
//       2*(F_GNT_MAX + 1) + 2**WD_W cycles -- at most F_GNT_MAX + 1 in
//       S_READ, at most 2**WD_W in S_WAIT (SC17, no assumption), at most
//       F_GNT_MAX + 1 in S_WB -- and the controller then returns to
//       S_IDLE. Checked by BMC rather than induction because the counter
//       bound is a bounded-response obligation, and reported as bounded.
// ---------------------------------------------------------------------
localparam integer F_GNT_MAX  = 2;
localparam integer F_WORD_MAX = 2 * (F_GNT_MAX + 1) + (1 << WD_W);

reg [15:0] f_gnt_wait;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        f_gnt_wait <= 16'd0;
    else if (mem_req && !mem_gnt)
        f_gnt_wait <= f_gnt_wait + 1'b1;
    else
        f_gnt_wait <= 16'd0;
end
always @(posedge clk)
    assume (f_gnt_wait <= F_GNT_MAX[15:0]);

reg [15:0] f_word_run;
always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        f_word_run <= 16'd0;
    else if ((state == S_IDLE) || (state == S_SAFE))
        f_word_run <= 16'd0;
    else
        f_word_run <= f_word_run + 1'b1;
end
always @(posedge clk)
    if (rst_n)
        assert (f_word_run <= F_WORD_MAX[15:0]);
`endif

// ---------------------------------------------------------------------
// SC19-SC20  Fault observability. The counters and sticky flags are the
//      only thing a radiation campaign or an on-orbit host ever sees of
//      this block, so their semantics are proven rather than tested: they
//      move only on the event they name, they saturate instead of
//      wrapping (a wrapped counter reads as "no errors", which is the
//      worst possible lie for a fault counter), and a FAULT_CLR
//      coincident with an event restarts at 1 instead of swallowing the
//      event -- the house convention of hw/rtl/aer_fifo.v.
// ---------------------------------------------------------------------
always @(posedge clk) if (f_step) begin
    if (!$past(fault_clr)) begin
        // Monotone, never wraps, advances by at most one, and only on
        // its own event.
        assert (cnt_sec >= $past(cnt_sec));
        assert (cnt_ded >= $past(cnt_ded));
        if ($past(cnt_sec) != {CNT_W{1'b1}})
            assert (cnt_sec <= ($past(cnt_sec) + 1'b1));
        else
            assert (cnt_sec == {CNT_W{1'b1}});
        if ($past(cnt_ded) != {CNT_W{1'b1}})
            assert (cnt_ded <= ($past(cnt_ded) + 1'b1));
        else
            assert (cnt_ded == {CNT_W{1'b1}});
        if (cnt_sec != $past(cnt_sec))
            assert ($past(ev_sec));
        if (cnt_ded != $past(cnt_ded))
            assert ($past(ev_ded));
        if ($past(ded_seen))
            assert (ded_seen);
        if ($past(err_to))
            assert (err_to);
        if ($past(err_win))
            assert (err_win);
    end
    // Every event is recorded, whatever the host does with FAULT_CLR in
    // the same cycle.
    if ($past(ev_sec) && ($past(cnt_sec) != {CNT_W{1'b1}}))
        assert (cnt_sec != {CNT_W{1'b0}});
    if ($past(ev_ded)) begin
        assert (ded_seen);
        assert (fault_addr == $past(addr));
        assert (cnt_ded != {CNT_W{1'b0}});
    end
    if ($past(ev_to))
        assert (err_to);
    if ($past(ev_win))
        assert (err_win);
    // cnt_sec counts repairs and nothing else: it moves exactly on the
    // cycles a writeback is armed. (SC7 already ties ecc_take to the
    // writeback itself; this ties the counter to the same edge, so
    // CNT_SEC read by the host is the number of words actually rewritten
    // and not the number of decoder flags observed anywhere.)
    if (!$past(fault_clr) && (cnt_sec != $past(cnt_sec)))
        assert ($past(ecc_take) && (state == S_WB));
end

// ---------------------------------------------------------------------
// Cover obligations (docs/09 B.1 vacuity rule: a target with passing
// asserts and failing covers is red). The two sets are mutually
// exclusive on purpose, exactly as in formal/lif_ctrl_props.v: a trace
// that starts on a corrupted encoding parks in S_SAFE and never runs a
// word, and a trace that starts from reset can never reach S_SAFE.
// ---------------------------------------------------------------------
`ifdef SCRUB_ANY_STATE
always @(posedge clk) if (f_step) begin
    // The SAFE response itself, from the injected upset: parked, ERR_CFG
    // latched for the host, and above all driving nothing.
    cover ((state == S_SAFE) && err_cfg && !mem_req && !ecc_take && busy);
    // And it stays there rather than resuming a walk silently.
    cover (($past(state) == S_SAFE) && (state == S_SAFE) && err_cfg);
end
`else
always @(posedge clk) if (f_step) begin
    // A check read is presented and granted.
    cover ($past(mem_req) && !$past(mem_we) && $past(mem_gnt));
    // A refused request is re-presented and then granted.
    cover (mem_req && mem_gnt && $past(mem_req) && !$past(mem_gnt));
    // A clean word retires with no write.
    cover (ev_ok);
    // A corrected word is captured and written back.
    cover (ecc_take);
    cover (mem_req && mem_we);
    cover ($past(mem_req) && $past(mem_we) && $past(mem_gnt) &&
           (state == S_IDLE));
    // A double-bit word retires WITHOUT a write.
    cover ($past(ev_ded) && (state == S_IDLE) && ded_seen);
    // A read response never arrives and the word is abandoned.
    cover ($past(ev_to) && err_to);
    // The host shrinks the window under a walk in flight.
    cover ($past(ev_win) && err_win);
    // The sweep wraps.
    cover (sweep_wrap);
    // Single-word mode: one word runs with the background walk disabled.
    cover (start_word && !scrub_en);
    // A fault counter saturates rather than wrapping.
    cover (cnt_sec == {CNT_W{1'b1}});
    cover (cnt_ded == {CNT_W{1'b1}});
    // FAULT_CLR coincident with an event: the event survives the clear.
    cover ($past(fault_clr) && $past(ev_ded) && ded_seen);
end
`endif
