// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Formal properties for the lif_core control path: command arbitration,
// the two input handshakes, the output handshake, scan integrity and the
// spec section 11.4 SAFE state. SymbiYosys harness: formal/lif_ctrl.sby,
// driver formal/lif_ctrl.mk.
//
// Why this job exists. The LIF datapath is verified against the bit-exact
// golden model sw/golden/lif_core.py in lockstep
// (hw/tb/test_lif_core_rtl.py). That lockstep constrains the arithmetic
// and the neuron state, and nothing else: the golden model has no notion
// of valid/ready, of a command arbiter, or of a stall, so a testbench
// that only compares state and spikes leaves the whole control interface
// unconstrained. A mutation experiment confirmed it -- five independent
// mutants of ev_ready, tick_ready, the state_clr priority and the
// held-spike interaction all survived the entire lockstep suite. The
// directed handshake tests added to that suite kill them; this job proves
// the same properties over the whole input space instead of over one
// stimulus. docs/09 section B.1 vacuity rule applies: every assert set
// ships with cover obligations.
//
// This file is textually included inside the lif_core module body under
// `ifdef FORMAL (end of hw/rtl/lif_core.v), so it sees state, jj,
// ev_axon_r, out_pend, can_go, last_j and the state codewords directly.
// It is invisible to Icarus simulation and to synthesis.
//
// Proven by k-induction (mode prove):
//   H1  grant discipline: ev_ready and tick_ready are asserted only in
//       S_IDLE, so no second command can be accepted while one is in
//       flight (E8 rule 1: all updates for command k complete before
//       command k+1 begins).
//   H2  priority as specified: state_clr outranks both event channels
//       (it forces both readys low), and a synaptic event outranks a
//       tick (ev_valid forces tick_ready low). At most one of the three
//       commands is granted in any cycle.
//   H3  no lost command: every accepted handshake -- ev_valid && ev_ready,
//       tick_valid && tick_ready, or state_clr sampled in S_IDLE -- is
//       followed by exactly the matching state on the next edge, with the
//       scan index reset to 0 and, for a synaptic event, the axon id
//       latched from the accepting edge.
//   H4  no phantom or duplicated command: S_EV, S_TICK and S_CLR are
//       entered only out of an accepted handshake of the matching kind.
//       With H3 this is a bijection between accepted commands and
//       executed scans.
//   H5  scan integrity: the index advances by exactly one per processed
//       neuron, never skips one under a stall, and the state leaves the
//       scan only on the last neuron -- so every accepted command visits
//       every neuron exactly once, in ascending order.
//   H6  output handshake: out_valid is never retracted without out_ready,
//       the held event word is stable while it waits, out_valid rises
//       only out of S_EV (TICK, CLR, SAFE and IDLE never emit), and a
//       held spike is never overwritten before it is taken.
//   H7  deadlock freedom, structural form: a scan that fails to advance
//       is always a scan whose output is being refused downstream
//       (out_valid && !out_ready) -- there is no internal blocking
//       condition. S_TICK and S_CLR never stall at all. In S_IDLE every
//       request is granted in the same cycle it is presented, so no
//       request is ever ignored.
//   H8  SAFE state (spec section 11.4): the encoding is always one of the
//       five codewords; any illegal encoding moves to S_SAFE and latches
//       err_cfg on the next edge; S_SAFE is terminal until reset; err_cfg
//       is sticky; and in S_SAFE the scan index and the neuron state file
//       are frozen and nothing new is emitted.
//   H9  debug-port interlock: a debug state write outside S_IDLE moves
//       nothing, and inside S_IDLE it lands at the addressed neuron.
//       This is the structural claim the RTL Contract block makes about
//       dbg_wr_en, proven rather than asserted in a comment.
//
// Two optional property sets, each enabled by its own define so that the
// assumption it needs cannot weaken the tasks that do not want it:
//   LIF_LIVENESS   (task bmc_live) a bounded-liveness watchdog. Under the
//       sink-fairness assumption that out_ready is not low on two
//       consecutive cycles, a held ev_valid is granted within
//       2*N_NEURONS + 4 cycles, and likewise tick_valid. The obligation
//       is re-armed (the watchdog is cleared) while state_clr is
//       requested or while the core is parked in S_SAFE, because neither
//       is a state in which service is owed.
//   LIF_SAFE_ENTRY (tasks bmc_safe and cover_safe) starts the trace from
//       a corrupted state encoding instead of from reset. S_SAFE is
//       unreachable from reset by construction -- that is the point of
//       the encoding -- so neither an assertion nor a cover about it
//       means anything in a reset-rooted trace.
//
// One methodology note worth stating plainly, because it decides whether
// H8 is real or decorative. The invariant "the encoding is always legal"
// is itself one of the H8 assertions, and k-induction assumes every
// assertion at steps 0..k-1 before checking step k. So in the prove task
// the state at step k-1 is assumed legal, which makes the antecedent of
// the recovery property ("if the previous encoding was illegal") false at
// every checked step: prove reports PASS for a default arm that silently
// resumes in IDLE and latches nothing, which is exactly the defect this
// property set was written to catch. Measured: two mutants of the default
// arm (recover to IDLE; enter SAFE without latching ERR_CFG) both survive
// prove and bmc_live, and both fail bmc_safe. The recovery behavior is
// therefore checked only by bmc_safe, whose trace starts on an illegal
// encoding, and by test_safe_state_on_corrupted_fsm_encoding in
// hw/tb/test_lif_core_rtl.py, which injects the same upsets into the
// state register. Do not drop bmc_safe from the gate on the grounds that
// prove already covers it -- it does not.

reg f_past_valid;
initial f_past_valid = 1'b0;
always @(posedge clk)
    f_past_valid <= 1'b1;

// The five legal codewords (pairwise Hamming distance >= 2).
wire f_state_legal = (state == S_IDLE) || (state == S_EV)  ||
                     (state == S_TICK) || (state == S_CLR) ||
                     (state == S_SAFE);

`ifdef LIF_SAFE_ENTRY
// Fault-entry task: begin out of reset on an illegal encoding, with
// err_cfg not yet latched. rst_n is free afterwards, as in every task.
initial assume (rst_n);
initial assume (!f_state_legal);
initial assume (!err_cfg);
`else
// Start in reset so the induction base matches hardware bring-up.
// rst_n is free afterwards, so the proof also covers reset mid-traffic.
initial assume (!rst_n);
`endif

// Environment assumptions, taken verbatim from the RTL Contract block:
// every index port addresses an entry that exists. NEUR_W and AXON_W
// round up to a power of two, so at a non-power-of-two geometry the ports
// can encode indices with no array entry behind them; upstream bounds
// them (docs/10 section 6, CFG_NEUR / CFG_AXON), and the golden model has
// no such neuron either. Without this the 3 x 2 task reports a debug
// read-back mismatch at dbg_addr == 3, which is an out-of-range access,
// not a control-path defect.
always @(*) begin
    assume (dbg_addr    < N_NEURONS);
    assume (w_wr_neuron < N_NEURONS);
    assume (w_wr_axon   < N_AXONS);
    assume (ev_axon     < N_AXONS);
end

// The three command grants. state_clr has no ready of its own: it is
// consumed exactly when it is sampled in S_IDLE (RTL header contract --
// pulses raised in any other state are ignored, not queued).
wire f_ev_acc   = ev_valid   && ev_ready;
wire f_tick_acc = tick_valid && tick_ready;
wire f_clr_acc  = (state == S_IDLE) && state_clr;

// ---------------------------------------------------------------------
// Reset
// ---------------------------------------------------------------------
always @(posedge clk) if (f_past_valid && !$past(rst_n)) begin
    assert (state == S_IDLE);
    assert (!err_cfg);
    assert (!out_valid);
    assert (jj == {NEUR_W{1'b0}});
end

// ---------------------------------------------------------------------
// H1 / H2: grant discipline, priority, mutual exclusion
// ---------------------------------------------------------------------
always @(*) begin
    // H1: a ready is a promise that the core will start the command on
    // this edge, and it can only keep that promise from S_IDLE.
    if (ev_ready)   assert (state == S_IDLE);
    if (tick_ready) assert (state == S_IDLE);

    // H2: state_clr > synaptic event > tick.
    if (state_clr) begin
        assert (!ev_ready);
        assert (!tick_ready);
    end
    if (ev_valid) assert (!tick_ready);

    // H2: at most one command is granted per cycle.
    assert (!(f_ev_acc   && f_tick_acc));
    assert (!(f_ev_acc   && f_clr_acc));
    assert (!(f_tick_acc && f_clr_acc));
end

// ---------------------------------------------------------------------
// H9: debug-port interlock (the claim the RTL Contract block makes)
// ---------------------------------------------------------------------
always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    // A debug state write outside S_IDLE is structurally impossible: the
    // vmem/rmem write lives inside the S_IDLE arm of the case. So a
    // mid-scan debug write is a dropped write, never a write that races
    // the scan's own write-back. Excluding the neuron the scan is itself
    // updating ($past(jj)) leaves the write as the only possible mover.
    if ($past(dbg_wr_en) && ($past(state) != S_IDLE) &&
        (dbg_addr == $past(dbg_addr)) && ($past(jj) != $past(dbg_addr))) begin
        assert (dbg_v == $past(dbg_v));
        assert (dbg_r == $past(dbg_r));
    end
    // In S_IDLE the same write does land, at the addressed neuron.
    if (($past(state) == S_IDLE) && $past(dbg_wr_en) &&
        (dbg_addr == $past(dbg_addr))) begin
        assert (dbg_v == $past(dbg_wr_v));
        assert (dbg_r == $past(dbg_wr_r));
    end
end

// ---------------------------------------------------------------------
// H3 / H4: accepted commands and executed scans are in bijection
// ---------------------------------------------------------------------
always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    // H3: no accepted command is lost.
    if ($past(f_ev_acc)) begin
        assert (state == S_EV);
        assert (ev_axon_r == $past(ev_axon));
        assert (jj == {NEUR_W{1'b0}});
    end
    if ($past(f_tick_acc)) begin
        assert (state == S_TICK);
        assert (jj == {NEUR_W{1'b0}});
    end
    if ($past(f_clr_acc)) begin
        assert (state == S_CLR);
        assert (jj == {NEUR_W{1'b0}});
    end

    // H4: no scan runs that no command asked for, and none runs twice.
    if ((state == S_EV) && ($past(state) != S_EV))
        assert ($past(f_ev_acc));
    if ((state == S_TICK) && ($past(state) != S_TICK))
        assert ($past(f_tick_acc));
    if ((state == S_CLR) && ($past(state) != S_CLR))
        assert ($past(f_clr_acc));
end

// ---------------------------------------------------------------------
// H5: scan integrity -- every neuron visited exactly once, in order
// ---------------------------------------------------------------------
always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    if ($past(state) == S_EV) begin
        if ($past(can_go)) begin
            if ($past(last_j)) begin
                assert (state == S_IDLE);
                assert (jj == {NEUR_W{1'b0}});
            end else begin
                assert (state == S_EV);
                assert (jj == $past(jj) + 1'b1);
            end
        end else begin
            // Stalled by the sink: hold the neuron, do not abandon or
            // skip it. This is the property that makes spec 7.2
            // ("a full output queue stalls the pipeline") true.
            assert (state == S_EV);
            assert (jj == $past(jj));
            assert (ev_axon_r == $past(ev_axon_r));
        end
    end
    if ($past(state) == S_TICK) begin
        if ($past(last_j)) begin
            assert (state == S_IDLE);
            assert (jj == {NEUR_W{1'b0}});
        end else begin
            assert (state == S_TICK);
            assert (jj == $past(jj) + 1'b1);
        end
    end
    if ($past(state) == S_CLR) begin
        if ($past(last_j)) begin
            assert (state == S_IDLE);
            assert (jj == {NEUR_W{1'b0}});
        end else begin
            assert (state == S_CLR);
            assert (jj == $past(jj) + 1'b1);
        end
    end
end

// ---------------------------------------------------------------------
// H6: output handshake (aer_fifo write side)
// ---------------------------------------------------------------------
always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    if ($past(out_valid) && !$past(out_ready)) begin
        assert (out_valid);                       // never retracted
        assert (out_event == $past(out_event));   // and never overwritten
    end
    // A spike enters the holding register only out of a neuron scan.
    if (out_valid && !$past(out_valid))
        assert ($past(state) == S_EV);
    // TICK, CLR, SAFE and IDLE never emit (spec section 4.2).
    if (($past(state) == S_TICK) || ($past(state) == S_CLR) ||
        ($past(state) == S_SAFE) || ($past(state) == S_IDLE))
        assert (!(out_valid && !$past(out_valid)));
end

// ---------------------------------------------------------------------
// H7: deadlock freedom, structural form
// ---------------------------------------------------------------------
always @(*) if (state == S_IDLE) begin
    // No request presented to an idle core is ever ignored: the winner of
    // the arbitration is served in the very cycle it is presented.
    if (!state_clr && ev_valid)                assert (ev_ready);
    if (!state_clr && !ev_valid && tick_valid) assert (tick_ready);
end

always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    // The only condition that can hold a scan is an output the sink is
    // refusing. There is no internal blocking term, so the core cannot
    // deadlock against itself; progress is the sink's obligation.
    if (($past(state) == S_EV) && (state == S_EV) && (jj == $past(jj)))
        assert ($past(out_valid) && !$past(out_ready));
    // S_TICK and S_CLR cannot stall at all.
    if (($past(state) == S_TICK) && (state == S_TICK))
        assert (jj != $past(jj));
    if (($past(state) == S_CLR) && (state == S_CLR))
        assert (jj != $past(jj));
end

// ---------------------------------------------------------------------
// H8: SAFE state (docs/10 section 11.4)
// ---------------------------------------------------------------------
always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    // The encoding is closed: legal in, legal out; illegal in, S_SAFE out.
    assert (f_state_legal);
    if (!$past(f_state_legal)) begin
        assert (state == S_SAFE);
        assert (err_cfg);
    end
    // S_SAFE is terminal until reset, and it holds ERR_CFG asserted.
    if ($past(state) == S_SAFE) begin
        assert (state == S_SAFE);
        assert (err_cfg);
        assert (busy);
        assert (!ev_ready);
        assert (!tick_ready);
        assert (jj == $past(jj));
        assert (ev_axon_r == $past(ev_axon_r));
        // Neuron state is frozen: every vmem/rmem write in the module
        // lives inside an S_IDLE / S_EV / S_TICK / S_CLR arm.
        if (dbg_addr == $past(dbg_addr)) begin
            assert (dbg_v == $past(dbg_v));
            assert (dbg_r == $past(dbg_r));
        end
    end
    // ERR_CFG is sticky: only reset clears it.
    if ($past(err_cfg)) assert (err_cfg);
    if (state == S_SAFE) assert (err_cfg);
end

// ---------------------------------------------------------------------
// Bounded liveness (task bmc_live only)
// ---------------------------------------------------------------------
`ifdef LIF_LIVENESS
// Sink fairness. Without some fairness on out_ready no bound exists, and
// that is correct: a downstream queue that never drains stalls the core
// forever by design (spec 7.2). One refused cycle per accepted cycle is
// the weakest assumption that still exercises the stall path.
always @(posedge clk) if (f_past_valid)
    assume (out_ready || $past(out_ready));

localparam [15:0] F_WAIT_MAX = 2 * N_NEURONS + 4;

reg [15:0] f_ev_wait;
reg [15:0] f_tick_wait;
initial f_ev_wait   = 16'd0;
initial f_tick_wait = 16'd0;

always @(posedge clk) begin
    if (!rst_n || !ev_valid || ev_ready || state_clr || (state == S_SAFE))
        f_ev_wait <= 16'd0;
    else
        f_ev_wait <= f_ev_wait + 16'd1;

    // A tick is legitimately outranked while a synaptic event is offered
    // (H2), and the host serializes the two channels by contract (RTL
    // header, spec deviation note), so ev_valid re-arms the obligation.
    if (!rst_n || !tick_valid || tick_ready || state_clr || ev_valid ||
        (state == S_SAFE))
        f_tick_wait <= 16'd0;
    else
        f_tick_wait <= f_tick_wait + 16'd1;
end

always @(posedge clk) if (f_past_valid && rst_n) begin
    assert (f_ev_wait   <= F_WAIT_MAX);
    assert (f_tick_wait <= F_WAIT_MAX);
end
`endif

// ---------------------------------------------------------------------
// Reachability covers (docs/09 section B.1 vacuity rule)
// ---------------------------------------------------------------------
// The two cover sets are mutually exclusive on purpose. A trace that
// starts on a corrupted encoding parks in S_SAFE and never runs a scan,
// so the operational covers below are not reachable in it, and a trace
// that starts from reset can never reach S_SAFE. Mixing them in one task
// would leave one half permanently unreached, which under the docs/09
// vacuity rule is indistinguishable from a broken cover.
`ifdef LIF_SAFE_ENTRY
always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    // The SAFE response itself, from the injected upset: parked, ERR_CFG
    // latched for the host, refusing both command channels.
    cover ((state == S_SAFE) && err_cfg && !ev_ready && !tick_ready && busy);
    // And it stays there rather than resuming silently.
    cover (($past(state) == S_SAFE) && (state == S_SAFE) && err_cfg);
end
`else
always @(posedge clk) if (f_past_valid && rst_n && $past(rst_n)) begin
    cover (f_ev_acc);
    cover (f_tick_acc);
    cover (f_clr_acc);
    // The arbitration actually arbitrates: each priority level wins over
    // a live request at every lower level.
    cover (f_clr_acc && ev_valid && tick_valid);
    cover (f_ev_acc && tick_valid);
    // A complete synaptic-event scan retires.
    cover (($past(state) == S_EV) && (state == S_IDLE));
    cover (($past(state) == S_TICK) && (state == S_IDLE));
    cover (($past(state) == S_CLR) && (state == S_IDLE));
    // A spike is emitted, refused, held, and finally taken.
    cover (out_valid && ($past(state) == S_EV));
    cover (out_valid && !out_ready);
    cover (out_valid && !out_ready && $past(out_valid) && !$past(out_ready));
    cover ($past(out_valid) && $past(out_ready) && !out_valid);
    // A new command is accepted while a spike is still held.
    cover (f_ev_acc && out_valid);
    // A debug state write lands, and a mid-scan one is dropped.
    cover (($past(state) == S_IDLE) && $past(dbg_wr_en));
    cover (($past(state) != S_IDLE) && $past(dbg_wr_en));
end
`endif
