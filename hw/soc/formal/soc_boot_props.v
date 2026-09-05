// BOOTREG, stated as properties.
//
// Textually included at the end of the soc_boot module body under
// `ifdef FORMAL, the arrangement every other fabric block uses.
//
// The set is short because the block is, and because the thing worth
// proving about it is not arithmetic -- it is an ACCESS property. The
// whole argument of hw/soc/rtl/soc_boot.v's header is that the one
// field with authority is the one software cannot write, and that is a
// statement about every reachable APB transaction, which is exactly
// what a proof is for and exactly what a directed suite can only
// sample.
//
//   D1  THE BOOT COUNTER IS NOT WRITABLE. No APB write of any value to
//       any offset changes it. This is the block's reason for existing,
//       and it is D1 because docs/40 W1's independence argument is
//       worth nothing if a wild store can reach the counter.
//   D2  It only ever counts up, it saturates, and it changes ONLY on a
//       release of the system reset -- so a boot that ends in a reset
//       is counted exactly once, and a system reset held asserted for
//       any number of cycles is still one boot.
//   D3  The power-on boot reads zero. `armed_q` is what makes that
//       true and D3 is what makes it a property rather than a comment:
//       until a second release has happened the counter is zero.
//   D4  THE STRAPS ARE SAMPLED ONCE. Once VALID is set, neither the
//       strap field nor the watchdog-pin field ever changes again,
//       whatever the pins do -- soc_wdog.v W1's "a pin that could
//       disable the watchdog at any moment would be a hardware
//       backdoor", one block across. VALID itself never falls.
//   D5  The report and the epoch change ONLY on a write to their own
//       offset, and a system reset does not touch them: that is what
//       "survives the reset it describes" means, and it is the half of
//       docs/41's power-on-domain argument this block relies on.
//   D6  Nothing in this block is reset by the SYSTEM reset. Stated as
//       the conjunction of D2, D4 and D5 rather than separately,
//       because between them they cover every flip-flop the block has.
//   D7  A well-behaved APB slave: always completes, never errors, and
//       every read is the state it names.
//   D8  BSTAT's two derived flags are exactly the comparisons a loader
//       would otherwise write down a second time.
//
// WHAT THEY DO NOT COVER. Nothing here says the straps are CONNECTED to
// anything (sw/tests/test_soc_boot_guards.py does, and the answer is
// that in hardware they are connected to nothing, which is the design);
// nothing says the boot counter counts BOOTS rather than reset releases
// -- the equivalence is soc_top.v's wiring of rst_sys_n and a whole-SoC
// run is the evidence; and there is no fault model over this block's
// own state, which section 9 of docs/68 lists as unprotected.

`ifdef FORMAL

  reg f_past_valid;
  initial f_past_valid = 1'b0;
  always @(posedge clk_i) f_past_valid <= 1'b1;

  initial assume (!rst_por_ni);
  initial assume (!rst_ni);
  // The system reset cannot be released while power-on reset is held:
  // soc_top.v derives rst_sys_n from rst_ni and the watchdog request.
  always @(*) if (!rst_por_ni) assume (!rst_ni);

  // The release, named once. The block samples `rst_ni` into `sys_q`
  // every clock and counts on the edge where `rst_ni` is high and the
  // sample is not, so THIS is the release -- evaluated with the values
  // the flip-flops had going INTO the edge, which is what `$past` of it
  // gives. Writing it as an edge between $past(rst_ni) and rst_ni is
  // the obvious thing and it is a different event by one cycle; the
  // first version of these properties did exactly that and the bounded
  // check found it in five steps.
  wire f_release = rst_ni && !sys_q;

  // ---- D1. No write reaches the counter ----------------------------
  //
  // Written over `wr` and not over a particular offset, so it holds for
  // every offset the decode has and every offset it does not.
  always @(posedge clk_i)
    if (f_past_valid && $past(rst_por_ni) && rst_por_ni && $past(wr)
        && !$past(f_release))
      assert (cnt_q == $past(cnt_q));

  // ---- D2. Monotone, saturating, and only on a release -------------
  always @(posedge clk_i)
    if (f_past_valid && $past(rst_por_ni) && rst_por_ni) begin
      assert (cnt_q >= $past(cnt_q));
      if ($past(cnt_q) == CNT_MAX) assert (cnt_q == CNT_MAX);
      if (cnt_q != $past(cnt_q))
        assert ($past(armed_q) && $past(f_release)
                && (cnt_q == $past(cnt_q) + 1));
      // And a system reset held asserted for any number of cycles is
      // still one boot: with no release, nothing moves.
      if (!$past(f_release)) assert (cnt_q == $past(cnt_q));
    end

  // ---- D3. The power-on boot is boot zero --------------------------
  always @(posedge clk_i)
    if (f_past_valid && rst_por_ni && !armed_q)
      assert (cnt_q == {CNT_W{1'b0}});

  // ---- D4. The straps are sampled once -----------------------------
  always @(posedge clk_i)
    if (f_past_valid && $past(rst_por_ni) && rst_por_ni && $past(valid_q)) begin
      assert (valid_q);
      assert (strap_q == $past(strap_q));
      assert (wdis_q  == $past(wdis_q));
    end

  // And VALID never falls short of a power cycle.
  always @(posedge clk_i)
    if (f_past_valid && $past(rst_por_ni) && rst_por_ni && $past(valid_q))
      assert (valid_q);

  // ---- D5. The record survives the reset it describes --------------
  always @(posedge clk_i)
    if (f_past_valid && $past(rst_por_ni) && rst_por_ni) begin
      if (!($past(wr) && $past(paddr_i) == REG_BRPT))
        assert (brpt_q == $past(brpt_q));
      else
        assert (brpt_q == $past(pwdata_i));
      if (!($past(wr) && $past(paddr_i) == REG_EPOCH))
        assert (epoch_q == $past(epoch_q));
      else
        assert (epoch_q == $past(pwdata_i));
    end

  // ---- D7. APB ------------------------------------------------------
  always @(*) begin
    assert (pready_o);
    assert (!pslverr_o);
  end

  always @(*)
    if (psel_i && penable_i && !pwrite_i) begin
      if (paddr_i == REG_BRPT)  assert (prdata_o == brpt_q);
      if (paddr_i == REG_EPOCH) assert (prdata_o == epoch_q);
      if (paddr_i == REG_BSTAT) assert (prdata_o[7:0] == cnt_w);
      if (paddr_i == REG_BSTRAP) begin
        assert (prdata_o[15:0] == strap_w);
        assert (prdata_o[31]   == valid_q);
        assert (prdata_o[16]   == wdis_q);
      end
    end

  // ---- D8. The derived flags are the comparisons -------------------
  //
  // LAST is stated ONE BIT WIDER than the counter, and that is not
  // pedantry: at CNT_W = 3 the counter saturates at 7, and `cnt_q + 1`
  // in three bits is 0, so the natural-looking form of this property is
  // false at the top of the range while the design is right. The
  // bounded check found it at step 16. The design's own form --
  // `cnt_q >= LIMIT_C - 1` -- cannot wrap, which is why it is written
  // that way and why restating it here in the plus-one form is worth
  // doing at all.
  always @(*) begin
    assert (last_attempt == (({1'b0, cnt_q} + {{CNT_W{1'b0}}, 1'b1})
                             >= {1'b0, LIMIT_C}));
    assert (over_limit   == (cnt_q >= LIMIT_C));
    // OVER implies LAST: a loader that checks only one of them is not
    // wrong, and this is what makes that true.
    if (over_limit) assert (last_attempt);
  end

  // ---- vacuity -----------------------------------------------------
  always @(posedge clk_i) begin
    // The straps get sampled at all, and to something non-zero.
    cover (f_past_valid && rst_por_ni && valid_q && strap_q != {NSTRAP{1'b0}});
    // A second boot, and a third: the counter moves without a power
    // cycle, which is the whole mechanism.
    cover (f_past_valid && rst_por_ni && rst_ni
           && cnt_q == {{(CNT_W-1){1'b0}}, 1'b1});
    cover (f_past_valid && rst_por_ni && rst_ni && over_limit);
    // A report written, then a system reset, then still there: the
    // property D5 states, as a witness rather than an implication.
    cover (f_past_valid && rst_por_ni && !rst_ni && brpt_q != 32'h0);
    cover (f_past_valid && rst_por_ni && rst_ni && $past(!rst_ni)
           && brpt_q != 32'h0 && epoch_q != 32'h0);
    // And a write that was refused: the counter is non-zero and a write
    // to its own offset happened in the same cycle.
    cover (f_past_valid && rst_por_ni && $past(wr)
           && $past(paddr_i) == REG_BSTAT && cnt_q != {CNT_W{1'b0}});
  end

`endif
