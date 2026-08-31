// Formal properties for the watchdog (SymbiYosys harness,
// hw/soc/formal/soc_wdog.sby).
//
// WHERE THESE PROPERTIES COME FROM, which matters more than what they
// say. Every one of them is one of the five requirements W1-W5 stated in
// the header of hw/soc/rtl/soc_wdog.v and argued in
// docs/40-interrupts-timers-watchdog.md section 5. Those requirements
// were written before the RTL, as a policy for what a watchdog has to do
// when the core it watches is protected by nothing else.
//
// THEY ARE SAFETY PROPERTIES, NOT A SECOND IMPLEMENTATION. This file
// does not mirror the counter, the prescaler or the reload. It could
// have -- and then it would be a copy of the design, which this
// repository has twice been bitten by. What it states instead is what
// must never happen, in terms of the escalation outputs and the status
// register as they are seen from outside:
//
//   * the enable never reads back as clear on an armed part (W1);
//   * a write without the key never changes an escalation output (W5);
//   * stage 2 is never reached except out of stage 1 (W3);
//   * stage 3 is never reached before the ESCALATE-th stage 2 (W3);
//   * the record of what happened is never lost or reduced (W4).
//
// The one place a ghost mirrors design state is the reset counter, and
// it has to: "the pin follows the count" is not sayable without a count.
// It is reconstructed from rst_req_o's own rising edges, so it is a
// count of the OUTPUT and not a copy of the register.
//
// WHAT IS NOT PROVEN HERE:
//
//   * Liveness of any kind. Nothing below says the watchdog ever fires.
//     A block whose counter never reached zero satisfies every property
//     in this file, which is why the cover task is not optional and why
//     hw/soc/tb/cocotb/test_soc_wdog.py measures the timeout in clocks.
//   * The timeout ARITHMETIC. That (reload + 1) * PRESCALE clocks elapse
//     between a kick and stage 1 is a measurement, not a proof; it is
//     test_the_timeout_is_reload_plus_one_prescaler_periods.
//   * Anything about the register OFFSETS. This block has a one-hot
//     register port; which APB offsets soc_gptimer.v maps onto it is
//     that block's suite.
//   * Anything about what the core does with nmi_o, or about the system
//     reset rst_req_o drives. Both are outside this module.
//   * Reset behaviour beyond the initial state.

reg f_past_valid;
initial f_past_valid = 1'b0;
always @(posedge clk_i) f_past_valid <= 1'b1;

initial assume (!rst_por_ni);

// ---------------------------------------------------------------------
// Environment: what soc_gptimer.v guarantees on the register port
// ---------------------------------------------------------------------
//
// The select is one-hot or zero. A shell that asserted two selects would
// be asking this block to service two registers in one cycle, which is
// not something its interface can express.
always @(*)
    assume ((sel_i & (sel_i - 4'd1)) == 4'd0);

// ---------------------------------------------------------------------
// Ghost state, reconstructed from the PORTS
// ---------------------------------------------------------------------
//
// f_armed: what the bootstrap pin decided, once, when power-on reset
// released. This is the whole of W1's escape hatch and nothing else may
// move it.
reg f_armed;
reg f_armed_valid;
always @(posedge clk_i or negedge rst_por_ni) begin
    if (!rst_por_ni) begin
        f_armed       <= 1'b1;
        f_armed_valid <= 1'b0;
    end else if (!f_armed_valid) begin
        f_armed       <= !dis_i;
        f_armed_valid <= 1'b1;
    end
end

// f_resets: rising edges of rst_req_o, saturating. Counted from the
// OUTPUT, so it is not a copy of the design's counter.
//
// A REGISTERED ghost necessarily lags by one cycle: it can only see the
// rise after the edge that produced it, while the design's own counter
// incremented at that edge. f_resets_now closes the gap by adding the
// pulse that is starting in this very cycle, and every property below
// uses that rather than the register. Stated here because the first
// version did not, and the bounded check reported three "failures" at
// step 11 that were entirely an artefact of the ghost.
localparam integer F_CNT_W = 8;
reg [F_CNT_W-1:0] f_resets;
reg               f_rst_q;
wire              f_rst_rise = rst_req_o && !f_rst_q;

wire [F_CNT_W-1:0] f_resets_now =
    (f_rst_rise && ~&f_resets) ? (f_resets + 1'b1) : f_resets;

always @(posedge clk_i or negedge rst_por_ni) begin
    if (!rst_por_ni) begin
        f_resets <= 0;
        f_rst_q  <= 1'b0;
    end else begin
        f_rst_q  <= rst_req_o;
        f_resets <= f_resets_now;
    end
end

// f_ever_reset: has stage 2 ever happened. W4's "the record survives"
// is stated against this.
reg f_ever_reset;
wire f_ever_now = f_ever_reset || f_rst_rise;
always @(posedge clk_i or negedge rst_por_ni)
    if (!rst_por_ni) f_ever_reset <= 1'b0;
    else             f_ever_reset <= f_ever_now;

// How long rst_req_o has been asserted, so the pulse length is checkable
// without reading the design's own counter.
reg [F_CNT_W-1:0] f_held;
always @(posedge clk_i or negedge rst_por_ni)
    if (!rst_por_ni)     f_held <= 0;
    else if (!rst_req_o) f_held <= 0;
    else if (~&f_held)   f_held <= f_held + 1'b1;

// A keyed write, as W5 defines one.
wire f_keyed   = we_i && (sel_i != 4'd0) && (wdata_i[31:16] == KEY);
wire f_unkeyed = we_i && (sel_i != 4'd0) && (wdata_i[31:16] != KEY);

// ---------------------------------------------------------------------
// I1-I2: strengthening invariants, needed for induction and nothing else
// ---------------------------------------------------------------------
//
// k-induction starts from an arbitrary state, so without these it starts
// from one where the ghost bookkeeping and the design's own counters
// disagree. Both are also real checks: a block whose reset counter
// drifted from the number of resets it had actually driven would fail
// I1, and one whose pin did not follow its own counter would fail I2.
always @(posedge clk_i) if (rst_por_ni && f_armed_valid) begin
    // I1. The ghost count of rst_req_o rising edges is the design's
    //     saturating reset counter.
    assert (f_resets_now == rst_count);
    // I2. The bootstrap decision the ghost latched is the one the design
    //     latched.
    assert (f_armed == !dis_q);
    // I3. The pulse length bookkeeping agrees with the design's, so the
    //     pulse-length property below is not proved against a ghost that
    //     has drifted.
    assert (rst_req_o == (rst_hold != 0));
    assert (!rst_req_o || (f_held + rst_hold == RST_CYCLES));

    // I4. The ghost's "a reset has happened" and the design's WDOGRST
    //     bit are the same fact. Needed only for induction, which
    //     otherwise starts from a state where a design that has reset
    //     twice sits beside a ghost that has never seen one, and W4a
    //     fails there for reasons that say nothing about the design.
    assert (f_ever_now == rst_seen);
end

// ---------------------------------------------------------------------
// W1: armed, and software cannot disarm it
// ---------------------------------------------------------------------
always @(posedge clk_i) if (rst_por_ni && f_armed_valid) begin
    // W1a. Reading the control register on an armed part always reports
    //      EN, RS and IE set, whatever has been written to it. This is
    //      the property, stated where a driver can observe it.
    if (sel_i[2]) begin
        assert (rdata_o[0] == f_armed);   // EN
        assert (rdata_o[1] == f_armed);   // RS
        assert (rdata_o[3] == f_armed);   // IE
    end

    // W1b. The bootstrap decision is made once. Nothing -- no write, no
    //      later movement of dis_i, no escalation -- changes it.
    if (f_past_valid && $past(rst_por_ni) && $past(f_armed_valid))
        assert (f_armed == $past(f_armed));

    // W1c. A part held off by the pin never escalates. This bounds the
    //      one hole W1 admits: the pin can silence the block completely,
    //      and that is the only thing that can.
    if (!f_armed) begin
        assert (!nmi_o);
        assert (!rst_req_o);
    end
end

// ---------------------------------------------------------------------
// W5: no write without the key has any effect
// ---------------------------------------------------------------------
//
// Stated over the escalation outputs and the status register, which is
// everything a write could usefully corrupt. The strong half is the
// second one: an unkeyed acknowledge must not clear a pending NMI,
// because if it could, a core storing wild values could hold itself in
// stage 1 forever and stage 2 would never arrive.
always @(posedge clk_i)
    if (f_past_valid && $past(rst_por_ni) && rst_por_ni && $past(f_unkeyed)) begin
        // W5a. An unkeyed write cannot clear a pending stage 1.
        //
        // The exception is stage 2 itself: the reset clears the pending
        // NMI, and it may start in the same cycle as the write. That is
        // W3b doing its job and not the write doing anything, so the
        // antecedent excludes it. The first version excluded it with
        // $past(rst_req_o) instead of rst_req_o and the bounded check
        // found the difference at step 11 -- a counter that expired into
        // stage 2 in the same cycle an unkeyed write arrived.
        if ($past(nmi_o) && !rst_req_o)
            assert (nmi_o);
        // W5b. An unkeyed write cannot change the timeout.
        //
        // Stated over the reload register rather than over the outputs,
        // because "the write did not cause this reset" is not sayable
        // without a shadow model of a run in which the write did not
        // happen -- and building one would make this file a second
        // implementation. The reload is the thing a write could usefully
        // corrupt: lengthening it is how software with no other way in
        // would try to neutralise the block. It moves for exactly two
        // reasons, a keyed write and the stage-2 restore, and neither is
        // this.
        if (!$past(stage2))
            assert (reload == $past(reload));
        // W5c. An unkeyed write cannot clear the record.
        assert (f_ever_now == $past(f_ever_now) || f_ever_now);
    end

// ---------------------------------------------------------------------
// W3: the ladder, and that each rung is reached only from the one below
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && $past(rst_por_ni) && rst_por_ni) begin
    // W3a. Stage 2 is entered only out of an UNACKNOWLEDGED stage 1.
    //      This is the property that makes the acknowledge meaningful:
    //      software that answers the warning is never reset for it.
    if (f_rst_rise) assert ($past(nmi_o));

    // W3b. Stage 2 clears stage 1. It has to: Ibex initialises mtvec to
    //      boot_addr on boot, so a core released from this reset with
    //      nmi_o still high vectors to boot_addr + 0x7C -- four bytes
    //      below its own reset vector -- before executing anything.
    if (rst_req_o) assert (!nmi_o);

    // W3c. Stage 2 lasts exactly RST_CYCLES and is not extendable.
    if (rst_req_o && $past(rst_req_o))
        assert (f_held <= RST_CYCLES[F_CNT_W-1:0]);
    if ($past(rst_req_o) && !rst_req_o)
        assert ($past(f_held) == RST_CYCLES[F_CNT_W-1:0] - 1'b1);

    // W3d. Stage 3 is reached only at the ESCALATE-th stage 2, and never
    //      before. A pin that asserted on the first reset would be a
    //      different and much noisier policy than the one docs/40
    //      section 5 argues for.
    assert (wdog_no == !(f_resets_now >= ESCALATE[F_CNT_W-1:0]));

    // W3e. Stage 3 latches. Once the platform has been told, it is not
    //      untold by anything short of a power cycle.
    if (!$past(wdog_no)) assert (!wdog_no);
end

// ---------------------------------------------------------------------
// W4: the record survives the reset this block causes
// ---------------------------------------------------------------------
always @(posedge clk_i) if (rst_por_ni && f_armed_valid) begin
    if (sel_i[3]) begin
        // W4a. WDOGRST reports whether a watchdog reset has happened
        //      since power-on, and reports it correctly in both
        //      directions -- a bit that were always set would satisfy
        //      only half of this.
        assert (rdata_o[1] == f_ever_now);
        // W4b. RSTCNT is the number of stage-2 events, saturating.
        assert (rdata_o[15:8] == f_resets_now);
        // W4c. ESCALATED agrees with the pin, so a reader of the
        //      register and a reader of the board see the same thing.
        assert (rdata_o[2] == !wdog_no);
        // W4d. DISABLED reports the bootstrap decision.
        assert (rdata_o[3] == !f_armed);
        // W4e. NMI reports the pending stage 1, so that the same flag
        //      the acknowledge clears is the one a reader sees.
        assert (rdata_o[0] == nmi_o);
    end
end

// The counter never wraps, which is what "saturating" has to mean: a
// count that returned to zero after 255 resets would report "nothing has
// happened" in the worst possible circumstances.
always @(posedge clk_i)
    if (f_past_valid && $past(rst_por_ni) && rst_por_ni)
        assert (f_resets_now >= $past(f_resets_now));

// ---------------------------------------------------------------------
// Cover: docs/09 B.1 vacuity rule -- every proven behaviour reachable
//
// This set matters more here than usual. Every property above is a
// SAFETY property, so a block that never did anything would satisfy all
// of them; the covers are what say the ladder is climbable.
// ---------------------------------------------------------------------
always @(posedge clk_i) if (f_past_valid && rst_por_ni) begin
    cover (nmi_o);                              // stage 1 reachable
    cover (rst_req_o);                          // stage 2 reachable
    cover (!wdog_no);                           // stage 3 reachable
    cover (nmi_o && f_keyed && sel_i[3]);       // an acknowledge is offered
    cover (f_past_valid && $past(nmi_o) && !nmi_o && !rst_req_o);
                                                // ...and works
    cover (f_resets_now == 1);
    cover (f_resets_now == 2);
    cover (f_unkeyed);                          // unkeyed writes happen
    cover (!f_armed);                           // the pin can hold it off
end
