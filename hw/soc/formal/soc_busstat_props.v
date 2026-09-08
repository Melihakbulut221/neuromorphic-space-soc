// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// BUSSTAT, stated as properties.
//
// Textually included at the end of the soc_busstat module body under
// `ifdef FORMAL, the arrangement soc_bus, soc_apb_bridge, soc_clint and
// soc_wdog already use.
//
// =====================================================================
// WHAT THESE PROPERTIES ARE ABOUT
// =====================================================================
//
// This block exists because docs/43 section 10's first bullet says the
// register file's correction "cannot tell an operator that it is being
// hit". Everything a counter has to do to fix that is a property of the
// COUNT, so that is what is stated:
//
//   B1  A counted event is never lost. Whatever else happens in the
//       cycle -- a clear, a read, a saturation -- a cycle in which the
//       event line is high leaves a counter that is not zero and a
//       sticky that is set. This is the property a telemetry counter is
//       FOR, and it is the one a clear-versus-increment race silently
//       breaks.
//   B2  The counter saturates and never wraps. A wrapped counter is
//       indistinguishable from a counter that has barely moved, and
//       nothing downstream can detect the difference. Stated as: the
//       count never decreases except when software clears it.
//   B3  A sticky bit is set by an event and cleared ONLY by its own
//       clear bit. It is not cleared by a system reset, because the
//       most valuable reading of these counters is the one taken after
//       the watchdog reset they explain (docs/40 W4's argument, applied
//       to telemetry).
//   B4  The interrupt enable IS cleared by a system reset, and the
//       interrupt is exactly `sticky & irqen`. This is the pair that
//       stops docs/40 section 7.2's brick from being rebuilt here: a
//       fault line that survived the reset it caused and re-entered a
//       handler the fresh boot had not installed yet.
//   B5  The block is a well-behaved APB slave: it always completes and
//       it never errors.
//   B6  Sources do not cross-talk. Clearing one counter leaves the
//       other three alone, which is the whole reason there are four.
//
// =====================================================================
// WHAT THEY DO NOT COVER, and this is the important half
// =====================================================================
//
//   * NOTHING HERE SAYS THE COUNT IS THE UPSET RATE. B1 says an event
//     on the wire is counted. Whether `rf_ecc_err_i[0]` is raised once
//     per upset is a property of ibex_regfile_secded.v's scrub, not of
//     this block, and it is measured in docs/44 section 7 rather than
//     proved anywhere.
//   * The event inputs are FREE here. A proof that a free wire is
//     counted says nothing about whether the wire is connected, which
//     is exactly the failure pilot_top.v shipped once: four ECC status
//     wires left unconnected, every proof and every test still green.
//     sw/tests/test_soc_regfile_guards.py and the SoC run of docs/44
//     section 8.2 are what check the connection.
//   * No fault model. This block is NOT protected -- no TMR, no code --
//     and an upset in a counter corrupts a number rather than a
//     behaviour. docs/44 section 9 lists that among what is not done.

`ifdef FORMAL

  // Past-valid, the house pattern: nothing may be asserted about $past
  // before there has been a past.
  reg f_past_valid;
  initial f_past_valid = 1'b0;
  always @(posedge clk_i) f_past_valid <= 1'b1;

  // The reset assumption of every job in this tree: power-on reset is
  // asserted at time zero, and the system reset is a strict consequence
  // of it -- soc_top.v drives rst_ni from a synchroniser that cannot be
  // high while rst_por_ni is low.
  initial assume (!rst_por_ni);
  initial assume (!rst_ni);
  always @(*) if (!rst_por_ni) assume (!rst_ni);

  genvar fi;
  generate
    for (fi = 0; fi < NSRC; fi = fi + 1) begin : g_props

      // ---- B1. An event is never lost ---------------------------
      // The antecedent deliberately does NOT exclude a clear in the
      // same cycle. That race is the one way a telemetry counter
      // silently drops the event that arrives while the frame is being
      // read, and it is the reason the RTL resolves it in favour of
      // the event.
      always @(posedge clk_i)
        if (f_past_valid && $past(rst_por_ni) && rst_por_ni
            && $past(ev[fi])) begin
          assert (cnt[fi] != {CNT_W{1'b0}});
          assert (sticky[fi]);
        end

      // ---- B2. Monotone, and saturating ---------------------------
      always @(posedge clk_i)
        if (f_past_valid && $past(rst_por_ni) && rst_por_ni
            && !$past(clr[fi])) begin
          assert (cnt[fi] >= $past(cnt[fi]));
          // and it stays at the top once it gets there
          if ($past(cnt[fi]) == CNT_MAX)
            assert (cnt[fi] == CNT_MAX);
        end

      // ---- B3. A sticky falls only to its own clear ---------------
      // Including across a SYSTEM reset, which is the half that makes
      // this a record rather than a status bit.
      always @(posedge clk_i)
        if (f_past_valid && $past(rst_por_ni) && rst_por_ni
            && $past(sticky[fi]) && !sticky[fi])
          assert ($past(clr[fi]) && !$past(ev[fi]));

      // ---- B6. No cross-talk --------------------------------------
      always @(posedge clk_i)
        if (f_past_valid && $past(rst_por_ni) && rst_por_ni
            && !$past(clr[fi]) && !$past(ev[fi]))
          assert (cnt[fi] == $past(cnt[fi]));

    end
  endgenerate

  // ---- B4. The enable is system-reset state, the record is not ----
  always @(*)
    if (!rst_ni) assert (irqen == {NSRC{1'b0}});

  always @(*)
    assert (irq_o == (|(sticky & irqen)));

  // Out of power-on reset there is nothing to report and nothing
  // enabled, so the line is low. This is the statement that the fresh
  // boot is not interrupted by its own history until it asks to be.
  always @(*)
    if (!rst_por_ni) assert (!irq_o);

  // ---- B5. APB ----------------------------------------------------
  always @(*) begin
    assert (pready_o);
    assert (!pslverr_o);
  end

  // ---- reads are the state ----------------------------------------
  // Stated for the two registers a driver has to be able to trust.
  always @(*)
    if (psel_i && penable_i && !pwrite_i) begin
      if (paddr_i == REG_RFSEC)
        assert (prdata_o == {{(32-CNT_W){1'b0}}, cnt[S_RFSEC]});
      if (paddr_i == REG_STATUS)
        assert (prdata_o[NSRC-1:0] == sticky);
    end

  // ---- vacuity ----------------------------------------------------
  // docs/09 B.1. Every behaviour above has to be reachable, or the job
  // proves nothing about the case it names.
  always @(posedge clk_i) begin
    cover (f_past_valid && rst_por_ni && cnt[S_RFSEC] == {CNT_W{1'b0}}
           && $past(ev[S_RFSEC]) == 1'b0);
    cover (f_past_valid && rst_por_ni && sticky[S_RFSEC]);
    cover (f_past_valid && rst_por_ni && sticky[S_TMRERR]);
    // the race: an event and its clear in the same cycle
    cover (f_past_valid && rst_por_ni
           && $past(ev[S_RFSEC]) && $past(clr[S_RFSEC])
           && cnt[S_RFSEC] == {{(CNT_W-1){1'b0}}, 1'b1});
    // saturation actually reached
    cover (f_past_valid && rst_por_ni && cnt[S_RFDED] == CNT_MAX);
    // the interrupt fires, and then goes away when the sticky is cleared
    cover (f_past_valid && rst_por_ni && irq_o);
    cover (f_past_valid && rst_por_ni && $past(irq_o) && !irq_o);
    // a system reset that leaves the record standing
    cover (f_past_valid && rst_por_ni && !rst_ni && sticky[S_RFSEC]);
  end

`endif
