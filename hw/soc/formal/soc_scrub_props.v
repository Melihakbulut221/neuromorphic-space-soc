// SCRUB, stated as properties.
//
// Textually included at the end of the soc_scrub module body under
// `ifdef FORMAL. The counter properties are soc_busstat_props.v's B1-B6
// restated over six sources, because the record half of this block is
// that block's structure; C6 and C7 are this block's own.
//
//   C1  A counted event is never lost, whatever else happens in the
//       cycle: the counter is nonzero and the sticky is set afterwards.
//   C2  A counter saturates and never wraps: it never decreases except
//       when software clears it, and it stays at the top.
//   C3  A sticky falls only to its own clear, including across a system
//       reset.
//   C4  The interrupt enable is cleared by a system reset and the
//       interrupt is exactly `sticky & irqen`; out of power-on reset
//       the line is low.
//   C5  A well-behaved APB slave: always completes, never errors.
//   C6  THE SCRUBBERS RUN OUT OF RESET. Whenever the system reset is
//       asserted, both enables are high and the interval is IVL_RST;
//       the three control outputs are exactly what CTRL holds. docs/44
//       section 11's rule as an invariant: this block cannot come up
//       with a scrubber off.
//   C7  The uncorrectable address of a memory changes ONLY on that
//       memory's ded event, and then to the address presented with it;
//       a clear does not touch it and the other memory's events do not
//       either.
//
// WHAT THEY DO NOT COVER, soc_busstat_props.v's list applied here:
// nothing says the count is the upset rate (that is soc_mem_ecc.v's
// scrubber, measured in test_soc_mem.py); the event inputs are FREE, so
// nothing here says they are connected (sw/tests/test_soc_memory_guards.py
// does); and there is no fault model over this block's own state.

`ifdef FORMAL

  reg f_past_valid;
  initial f_past_valid = 1'b0;
  always @(posedge clk_i) f_past_valid <= 1'b1;

  initial assume (!rst_por_ni);
  initial assume (!rst_ni);
  always @(*) if (!rst_por_ni) assume (!rst_ni);

  genvar fi;
  generate
    for (fi = 0; fi < NSRC; fi = fi + 1) begin : g_props

      // ---- C1. An event is never lost ---------------------------
      always @(posedge clk_i)
        if (f_past_valid && $past(rst_por_ni) && rst_por_ni
            && $past(ev[fi])) begin
          assert (cnt[fi] != {CNT_W{1'b0}});
          assert (sticky[fi]);
        end

      // ---- C2. Monotone, and saturating ---------------------------
      always @(posedge clk_i)
        if (f_past_valid && $past(rst_por_ni) && rst_por_ni
            && !$past(clr[fi])) begin
          assert (cnt[fi] >= $past(cnt[fi]));
          if ($past(cnt[fi]) == CNT_MAX)
            assert (cnt[fi] == CNT_MAX);
        end

      // ---- C3. A sticky falls only to its own clear ---------------
      always @(posedge clk_i)
        if (f_past_valid && $past(rst_por_ni) && rst_por_ni
            && $past(sticky[fi]) && !sticky[fi])
          assert ($past(clr[fi]) && !$past(ev[fi]));

      // ---- no cross-talk ------------------------------------------
      always @(posedge clk_i)
        if (f_past_valid && $past(rst_por_ni) && rst_por_ni
            && !$past(clr[fi]) && !$past(ev[fi]))
          assert (cnt[fi] == $past(cnt[fi]));

    end
  endgenerate

  // ---- C4. The enable is system-reset state, the record is not ----
  always @(*)
    if (!rst_ni) assert (irqen == {NSRC{1'b0}});

  always @(*)
    assert (irq_o == (|(sticky & irqen)));

  always @(*)
    if (!rst_por_ni) assert (!irq_o);

  // ---- C5. APB ----------------------------------------------------
  always @(*) begin
    assert (pready_o);
    assert (!pslverr_o);
  end

  // ---- C6. The scrubbers run out of reset, and CTRL is the control
  always @(*)
    if (!rst_ni) begin
      assert (ram_en_o);
      assert (rom_en_o);
      assert (ivl_o == IVL_RST);
    end

  always @(*) begin
    assert (ram_en_o == ram_en_q);
    assert (rom_en_o == rom_en_q);
    assert (ivl_o    == ivl_q);
  end

  // ---- C7. The uncorrectable address follows its own ded event ----
  always @(posedge clk_i)
    if (f_past_valid && $past(rst_por_ni) && rst_por_ni) begin
      if ($past(ram_ded_i)) assert (ram_addr_q == $past(ram_addr_i));
      else                  assert (ram_addr_q == $past(ram_addr_q));
      if ($past(rom_ded_i)) assert (rom_addr_q == $past(rom_addr_i));
      else                  assert (rom_addr_q == $past(rom_addr_q));
    end

  // ---- reads are the state ----------------------------------------
  always @(*)
    if (psel_i && penable_i && !pwrite_i) begin
      if (paddr_i == REG_RAMSEC)
        assert (prdata_o == {{(32-CNT_W){1'b0}}, cnt[S_RAMSEC]});
      if (paddr_i == REG_ROMDED)
        assert (prdata_o == {{(32-CNT_W){1'b0}}, cnt[S_ROMDED]});
      if (paddr_i == REG_STATUS)
        assert (prdata_o[NSRC-1:0] == sticky);
      if (paddr_i == REG_RAMADDR)
        assert (prdata_o == ram_addr_q);
      if (paddr_i == REG_CTRL)
        assert (prdata_o == {ivl_q, 14'h0, rom_en_q, ram_en_q});
    end

  // ---- vacuity ----------------------------------------------------
  always @(posedge clk_i) begin
    cover (f_past_valid && rst_por_ni && sticky[S_RAMSEC]);
    cover (f_past_valid && rst_por_ni && sticky[S_ROMDED]);
    cover (f_past_valid && rst_por_ni
           && $past(ev[S_RAMRD]) && $past(clr[S_RAMRD])
           && cnt[S_RAMRD] == {{(CNT_W-1){1'b0}}, 1'b1});
    cover (f_past_valid && rst_por_ni && cnt[S_ROMRD] == CNT_MAX);
    cover (f_past_valid && rst_por_ni && irq_o);
    cover (f_past_valid && rst_por_ni && $past(irq_o) && !irq_o);
    cover (f_past_valid && rst_por_ni && !rst_ni && sticky[S_RAMDED]);
    // a scrubber stopped and slowed by software, then restored by reset
    cover (f_past_valid && rst_ni && !ram_en_o && ivl_o == 16'd7);
    // stopped by software two cycles ago, a system reset last cycle,
    // walking again now: the reset restores the enable asynchronously,
    // so the cycle IN reset already reads enabled and the witness has
    // to look one further back
    cover (f_past_valid && rst_por_ni && $past(!ram_en_o, 2)
           && !$past(rst_ni) && ram_en_o);
    cover (f_past_valid && rst_por_ni && ram_addr_q != 32'h0
           && rom_addr_q != 32'h0 && ram_addr_q != rom_addr_q);
  end

`endif
