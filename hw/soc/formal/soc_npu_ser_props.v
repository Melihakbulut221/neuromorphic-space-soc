// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// Formal properties for hw/soc/rtl/soc_npu_ser.v.
//
// WHAT THESE ARE WRITTEN AGAINST. They are the serial host protocol of
// hw/rtl/pilot_top.v section 2 -- the frame format P1-P4 and the three
// HOST OBLIGATIONS H1, H2 and H3 that section states -- expressed over
// this module's PORTS. That document is the normative statement of what
// the TTIHP26b die accepts; this module has to be correct against it and
// not against itself.
//
// Nothing here restates the state encoding of soc_npu_ser.v. The one
// place the design's own state is named is the strengthening invariant
// block at the end, which exists because k-induction starts from an
// arbitrary state, and each of those is a real check as well as a proof
// aid -- the same discipline docs/39 section 5.5 records for the fabric.
//
// WHY THE HOST OBLIGATIONS ARE THE INTERESTING PROPERTIES. H2 and H3
// are not stylistic: pilot_top.v two-flop synchronizes all four serial
// pins, so a select that falls too close to the first clock edge loses
// the first command bit, and a deselect that is never SEEN leaves the
// die's bit counter running so the next frame decodes at the wrong
// offset. That second failure was found during the pilot's own bring-up
// with a half-period gap, and it is the shape of defect that produces a
// register map which is subtly wrong rather than obviously broken.
//
// WHAT IS NOT PROVED HERE:
//   - LIVENESS. Nothing says a frame ever completes. A design whose
//     tick counter never reached HALF-1 satisfies every assertion below,
//     which is why the cover task is not optional.
//   - THE DIE. These properties say what this module puts on the wire.
//     Whether the die interprets it as intended is
//     hw/soc/tb/cocotb/test_soc_npu.py's subject, where the frozen
//     pilot is the thing being driven.
//   - MISO SAMPLING. The cycle SER_MISO is sampled in is a TIMING
//     argument about the die's own synchronizers (soc_npu_ser.v's
//     header), not a protocol rule, and no property here can see the
//     die. It is checked by reading every register's reset value
//     through the transport in the cocotb suite.
//   - HALF > 2. Every task runs at one parameter point; the frame-length
//     arithmetic below is parameterised but nothing sweeps it.
//
// WHAT docs/55 ADDED, AND WHY IT IS AN INVARIANT AND NOT A COVER
//
// The module now carries a FRAME BOUND: a counter that runs for as long
// as a frame is in flight and, at GUARD_MAX, forces ST_IDLE, releases
// the select and raises `timeout_o` beside `done_o`. docs/52 section 7.1
// is the measurement that asked for it -- seven upsets in 600 left the
// whole SoC dead and five of them were a corrupted `tick` or `state`
// here, a frame that never ends.
//
// A mechanism that fires only under a fault cannot be proved to WORK by
// a proof that has no fault model. What CAN be proved, and is the claim
// worth making, is the other half:
//
//   I10 states GUARD as an EXACT FUNCTION of the frame position, and
//   I11 concludes GUARD < GUARD_MAX.
//
// Together they say THE BOUND CAN NEVER FIRE ON A HEALTHY FRAME -- which
// is the property that stops this mechanism from being a new way to fail
// an access that would have succeeded. If a future protocol change made
// a frame one half period longer without moving HALVES_FRAME with it,
// I11 fails here rather than the SoC taking a bus error in the field.
//
// It is also what keeps P2 provable. P2 says a select is not released
// before the fortieth edge, which an aborted frame deliberately
// violates; with I11 in the inductive hypothesis, the abort is
// unreachable and P2 needs no exception clause. THE EXCEPTION IS THEREFORE
// NOT WRITTEN, and that is a decision: an assertion weakened by
// `&& !timeout_o` would still pass on a design whose bound fired every
// frame.

`ifdef FORMAL

  reg f_past_valid = 1'b0;
  always @(posedge clk_i) f_past_valid <= 1'b1;

  // -------------------------------------------------------------------
  // Environment: the only thing assumed of the caller
  // -------------------------------------------------------------------
  // A1. The design starts in reset. Same convention as
  //     soc_bus_props.v and soc_clint_props.v, and the same reason: a
  //     bounded check that began in an arbitrary state would be
  //     checking a machine that no reset ever produced.
  initial assume (!rst_ni);

  // A2. No start while the transport is held in reset. Nothing else is
  //     assumed of the caller: addr_i, we_i and wdata_i may change
  //     freely in any cycle that is not a start, and start_i may be
  //     asserted while busy -- D4 is the property that says what
  //     happens then.
  always @(*)
    if (!rst_ni) assume (!start_i);

  // -------------------------------------------------------------------
  // Ghost state
  // -------------------------------------------------------------------
  // ONE GHOST, AND EVERY DWELL PROPERTY IS WRITTEN OVER $past OF THE PIN
  // INSTEAD.
  //
  // The first version of this file counted "cycles since SER_SCK last
  // changed" in a register and compared it against HALF. It fails, and
  // the reason is worth recording because it is the same shape of defect
  // as docs/40 section 7.5's three testbench findings: a counter that
  // observes a pin by comparing it with its OWN registered copy sees the
  // change one cycle late, so at the very cycle a dwell property wants
  // to read the OLD level's dwell it is already reporting the new one's.
  // The bound then reads 1 where the design held the level for HALF, and
  // every symptom of it looks like a design defect. Sampling $past of
  // the pin at fixed offsets has no such lag and needs no invariant to
  // tie it to anything.
  //
  // f_sck_edges survives because P2 counts edges across a whole frame,
  // which $past cannot express at any fixed depth, and f_we survives
  // because it captures a port value the frame is checked against.
  reg [7:0] f_sck_edges;
  reg       f_we;
  reg       f_sck_q;

  // One registered copy of the pin, used only to NAME the edge. Every
  // dwell below is measured with $past of the pin itself, so this
  // register's one-cycle view is never on the measurement path.
  always @(posedge clk_i or negedge rst_ni)
    if (!rst_ni) f_sck_q <= 1'b0;
    else         f_sck_q <= ser_sck_o;

  wire f_sck_rise = !ser_cs_n_o && ser_sck_o && !f_sck_q;

  always @(posedge clk_i or negedge rst_ni)
    if (!rst_ni) begin
      f_sck_edges <= 8'd0;
      f_we        <= 1'b0;
    end else begin
      if (ser_cs_n_o)      f_sck_edges <= 8'd0;
      else if (f_sck_rise) f_sck_edges <= f_sck_edges + 8'd1;
      if (start_i && !busy_o) f_we <= we_i;
    end

  // "Has the design been out of reset for the whole of the last N
  // cycles." Every dwell property needs it, because a reset asserted
  // inside the window aborts the frame -- and resets the DIE's own bit
  // counter with it, so the obligation restarts rather than carrying
  // across. The bounded check found this by asserting reset mid-frame
  // and starting another frame two cycles later, which is a sequence
  // nothing in this SoC produces and nothing in the protocol forbids.
  reg [15:0] f_up;
  always @(posedge clk_i or negedge rst_ni)
    if (!rst_ni)             f_up <= 16'd0;
    else if (f_up != F_CAP)  f_up <= f_up + 16'd1;

  localparam [15:0] F_CAP    = 16'd200;
  localparam [15:0] F_HALF   = HALF[15:0];
  localparam [15:0] F_PERIOD = 2 * HALF[15:0];

  // -------------------------------------------------------------------
  // P: the frame format (pilot_top.v section 2)
  // -------------------------------------------------------------------
  // P1. SER_SCK is low whenever the die is not selected. CPOL = 0 means
  //     the idle level is low, and a clock edge outside a frame is an
  //     edge the die's counter would see if the select glitched.
  always @(*)
    if (rst_ni && ser_cs_n_o) assert (!ser_sck_o);

  // P2. A frame carries EXACTLY 40 SER_SCK rising edges. Never a
  //     forty-first inside one select, and the select is not released
  //     before the fortieth.
  always @(*)
    if (rst_ni) assert (f_sck_edges <= 8'd40);

  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni)
        && $past(!ser_cs_n_o) && ser_cs_n_o)
      assert ($past(f_sck_edges) == 8'd40);

  // P3/P4 are properties of the DIE's INTERPRETATION and are not
  // assertable over this module's outputs. What is assertable is that
  // the frame the module puts on the wire is the transaction it was
  // given: bit 39, the command byte's write flag, is on SER_MOSI at the
  // first rising edge of the frame. f_we is captured from the PORT at
  // the start, so a module that shifted its own idea of the command out
  // could not satisfy this.
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni)
        && f_sck_rise && (f_sck_edges == 8'd0))
      assert (ser_mosi_o == f_we);

  // -------------------------------------------------------------------
  // H: the host obligations, as fixed-depth samples of the pins
  // -------------------------------------------------------------------
  // The three loops below are the whole of H1, H2, H3 and H4. Each says
  // "the pin held this value for the N cycles before the edge", stated
  // as N separate samples rather than as a counter, and each is guarded
  // by the design having been out of reset for those N cycles.
  genvar gk;
  generate
    // H1. SER_SCK <= clk/4: every level is held for at least HALF clk
    //     cycles before it may change.
    for (gk = 1; gk <= HALF; gk = gk + 1) begin : g_h1
      always @(posedge clk_i)
        if (f_past_valid && rst_ni && (f_up > F_HALF)
            && (ser_sck_o != $past(ser_sck_o)))
          assert ($past(ser_sck_o, gk) == $past(ser_sck_o));
    end

    // H4. SER_MOSI is stable for at least HALF clk cycles before every
    //     SER_SCK rising edge. H1 is about the clock RATE; this is the
    //     setup requirement the die's two-flop MOSI synchronizer imposes
    //     on the DATA, and it is the reason this module drives the next
    //     bit at the END of the previous high half rather than at the
    //     edge. pilot_top.v section 2 does not state it as a numbered
    //     obligation, which is precisely why it is easy to violate.
    for (gk = 1; gk <= HALF; gk = gk + 1) begin : g_h4
      always @(posedge clk_i)
        if (f_past_valid && rst_ni && (f_up > F_HALF) && f_sck_rise)
          assert ($past(ser_mosi_o, gk) == ser_mosi_o);
    end

    // H2. SER_CS_N falls at least one full SER_SCK period -- 2*HALF clk
    //     cycles -- before the FIRST SER_SCK edge of a frame. The die's
    //     frame-start reset has to clear its synchronizer before the
    //     first sampled clock edge arrives.
    for (gk = 1; gk <= 2 * HALF; gk = gk + 1) begin : g_h2
      always @(posedge clk_i)
        if (f_past_valid && rst_ni && (f_up > F_PERIOD)
            && f_sck_rise && (f_sck_edges == 8'd0))
          assert (!$past(ser_cs_n_o, gk));
    end

    // H3. SER_CS_N stays high at least one full SER_SCK period BETWEEN
    //     frames. The die holds its bit counter at zero only while the
    //     SYNCHRONIZED select reads inactive, so a deselect that is
    //     never seen leaves the counter running and the next frame
    //     decodes at the wrong offset. That failure was found during the
    //     pilot's own bring-up with a half-period gap.
    for (gk = 1; gk <= 2 * HALF; gk = gk + 1) begin : g_h3
      always @(posedge clk_i)
        if (f_past_valid && rst_ni && (f_up > F_PERIOD)
            && $past(ser_cs_n_o) && !ser_cs_n_o)
          assert ($past(ser_cs_n_o, gk));
    end
  endgenerate

  // -------------------------------------------------------------------
  // D: the transaction interface
  // -------------------------------------------------------------------
  // D1. done_o implies the frame is over: the die is deselected and the
  //     module is idle again. A done that arrived mid-frame would let a
  //     caller start a second transaction on top of the first.
  always @(*)
    if (rst_ni && done_o) begin
      assert (ser_cs_n_o);
      assert (!ser_sck_o);
      assert (!busy_o);
    end

  // D1b. `timeout_o` never rises on its own. The caller distinguishes a
  //      completed frame from an aborted one by reading timeout_o IN THE
  //      done_o cycle; a timeout without a done would be an abort no
  //      caller ever hears about, which is the failure the bound exists
  //      to remove, reintroduced one level up.
  always @(*)
    if (rst_ni && timeout_o) assert (done_o);

  // D1c. An aborted frame returns no data. A caller that ignored
  //      timeout_o must not be able to read a partial frame as a
  //      register value; soc_npu.v's node window turns the pair into a
  //      bus error, and this is the property that says there is nothing
  //      else it could have done with the word.
  always @(*)
    if (rst_ni && timeout_o) assert (rdata_o == 32'd0);

  // D2. done_o is exactly one cycle wide, and never two in a row.
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && $past(done_o))
      assert (!done_o);

  // D3. busy_o rises only because of a start, and falls only with a
  //     done. Together these are "exactly one done per accepted start",
  //     which is what the arbiter above this module counts on to know
  //     whose frame completed.
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && !$past(busy_o) && busy_o)
      assert ($past(start_i));

  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && $past(busy_o) && !busy_o)
      assert (done_o);

  // D4. A start that is refused changes nothing. Asserting start_i while
  //     busy must not restart, retarget or corrupt the frame in flight:
  //     the module either stays busy or finishes the frame it already
  //     had. The `|| done_o` is not a weakening -- the frame in flight
  //     may legitimately complete in the very cycle a refused start is
  //     presented, and induction found that case.
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni)
        && $past(busy_o) && $past(start_i) && !$past(done_o))
      assert (busy_o || done_o);

  // D5. The module is quiet when it is idle: deselected, clock low, and
  //     no data on MOSI. An idle transport that left the select
  //     asserted would leave the die inside a frame for ever.
  always @(*)
    if (rst_ni && !busy_o && !done_o) begin
      assert (ser_cs_n_o);
      assert (!ser_sck_o);
    end

  // -------------------------------------------------------------------
  // Strengthening invariants (k-induction only)
  //
  // Each is also a real check: a design that clocked outside a select,
  // counted its bits wrong, or left the select asserted in ST_IDLE would
  // fail one of them.
  // -------------------------------------------------------------------
  always @(posedge clk_i) if (f_past_valid && $past(rst_ni) && rst_ni) begin
    // I1. The state encoding is one of the four states.
    assert (state <= ST_GAP);
    // I2. The select is asserted exactly in the states that own a
    //     frame. ST_IDLE never asserts it; ST_GAP releases it partway
    //     through, so it is not constrained here.
    assert (!(state == ST_IDLE) || ser_cs_n_o);
    assert (!(state == ST_SETUP) || !ser_cs_n_o);
    assert (!(state == ST_SHIFT) || !ser_cs_n_o);
    // I3. The half-period counter never runs past its limit.
    assert (tick < HALF[15:0]);
    // I4. The bit counter is inside the frame.
    assert (bit_cnt < NBITS[5:0]);
    // I5. hcnt is a small phase index, never a wild value.
    assert (hcnt <= 2'd2);
    // I5a. And it is TIGHTER than that in three of the four states.
    //      docs/55 needs this: I10 below expresses `guard` as
    //      hcnt * HALF + ..., and hcnt is two bits, so an induction that
    //      began in ST_SETUP with hcnt = 3 would wrap it to 0 on the next
    //      half period and the position formula would jump backwards.
    //      Each clause is also a real check -- a design that reached the
    //      shift phase with a gap-phase index would be a design whose
    //      frame had lost its place.
    assert (!(state == ST_IDLE)  || (hcnt == 2'd0));
    assert (!(state == ST_SETUP) || (hcnt <= 2'd1));
    assert (!(state == ST_SHIFT) || (hcnt <= 2'd1));
    // I6. The clock is low outside the high half of a shift.
    assert ((state == ST_SHIFT && hcnt == 2'd1) || !ser_sck_o);
    // I7. The ghost edge count -- built from the PIN alone -- agrees
    //     with the design's own bit counter. This is what ties the
    //     observation to the accounting and is what makes P2 provable.
    //
    //     THE GHOST LAGS BY ONE CYCLE and the term says so. It counts a
    //     rise by comparing the pin with its own registered copy, so the
    //     increment lands at the END of the first cycle of the high
    //     half. `tick != 0` is exactly "the rise has already been
    //     counted", and it is right at every HALF.
    assert (!(state == ST_SHIFT)
            || (f_sck_edges == ({2'd0, bit_cnt}
                                + {7'd0, (hcnt[0] && (tick != 16'd0))})));
    assert (!(state == ST_SETUP) || (f_sck_edges == 8'd0));
    // In ST_GAP the count is 40 while the select is still asserted, and
    // falls to zero one cycle after it is released -- one cycle,
    // because the ghost clears on the SAMPLED select, exactly as the die
    // does. So the two values are the only two possible, and the
    // stronger of the pair is stated separately for the cycles it holds.
    assert (!(state == ST_GAP)
            || (f_sck_edges == 8'd40) || (f_sck_edges == 8'd0));
    assert (!((state == ST_GAP) && !ser_cs_n_o) || (f_sck_edges == 8'd40));
    // I9. The one registered pin copy agrees with the level the state
    //     encoding implies for the PREVIOUS cycle. Without it, induction
    //     may start from a state where f_sck_q disagrees with the pin
    //     and fabricate an extra edge; with it, f_sck_rise names exactly
    //     the edges the design produces.
    assert (f_sck_q ==
            (((state == ST_SHIFT) && (hcnt == 2'd1) && (tick != 16'd0))
          || ((state == ST_SHIFT) && (hcnt == 2'd0) && (tick == 16'd0)
              && (bit_cnt != 6'd0))
          || ((state == ST_GAP) && (hcnt == 2'd0) && (tick == 16'd0))));

    // I10. THE FRAME BOUND'S COUNTER IS AN EXACT FUNCTION OF THE FRAME
    //      POSITION. `f_pos` below is "clk cycles since the first cycle
    //      of ST_SETUP", computed from the state encoding alone, and the
    //      counter has to equal it in every cycle. This is what makes
    //      I11 provable rather than assumed, and it is a real check of
    //      its own: a guard that was cleared or held anywhere inside a
    //      frame would satisfy I11 while doing nothing.
    assert (f_guard == f_pos);

    // I11. AND THEREFORE THE BOUND CANNOT FIRE ON A HEALTHY FRAME.
    //      This is the property docs/55 section 4 rests on. The bound is
    //      a fault-tolerance mechanism, and a fault-tolerance mechanism
    //      that can fire without a fault is a new way to fail an access
    //      that would have succeeded. Nothing in this file can prove the
    //      bound WORKS -- there is no fault model here, and docs/55
    //      section 8's campaign is where that is measured -- but this
    //      says it costs nothing when there is no fault.
    assert (f_guard < GUARD_MAX[15:0]);
  end

  // ---- the frame position, from the state encoding alone -------------
  //
  // Written as a `wire` rather than folded into the assertion so that a
  // counterexample trace prints it. The three arms are the three phases
  // of the frame in soc_npu_ser.v's own HALVES_ constants; nothing here
  // reads `guard`.
  localparam [15:0] F_HSETUP = HALVES_SETUP[15:0];
  localparam [15:0] F_HSHIFT = HALVES_SHIFT[15:0];

  wire [15:0] f_guard = {{(16 - GUARD_W){1'b0}}, guard};

  wire [15:0] f_pos =
      (state == ST_SETUP)
        ? ({14'd0, hcnt} * F_HALF + tick)
    : (state == ST_SHIFT)
        ? ((F_HSETUP + {10'd0, bit_cnt} * 16'd2 + {14'd0, hcnt}) * F_HALF
           + tick)
    : (state == ST_GAP)
        ? ((F_HSETUP + F_HSHIFT + {14'd0, hcnt}) * F_HALF + tick)
    : 16'd0;

  // -------------------------------------------------------------------
  // Cover: the frame is reachable, in both directions, twice in a row
  // -------------------------------------------------------------------
  // Without these every assertion above is satisfied by a design that
  // never leaves ST_IDLE.
  always @(posedge clk_i) begin
    cover (f_past_valid && rst_ni && done_o);                      // C1
    cover (f_past_valid && rst_ni && done_o && f_we);              // C2
    cover (f_past_valid && rst_ni && done_o && !f_we);             // C3
    cover (f_past_valid && rst_ni && busy_o && (bit_cnt == 6'd39));// C4
    cover (f_past_valid && rst_ni && (state == ST_GAP));           // C5
    // C6. The counter reaches the last cycle of a healthy frame. Without
    //     it, I11 would be satisfied by a design whose guard never left
    //     zero -- and I10 would be satisfied by a design that never left
    //     ST_IDLE. This is the reachability half of the bound's claim:
    //     a healthy frame gets to within HALVES_SLACK * HALF of the
    //     bound and no further.
    cover (f_past_valid && rst_ni
           && (f_guard == GUARD_MAX[15:0] - HALVES_SLACK[15:0] * F_HALF
                          - 16'd1));                               // C6
  end

`endif
