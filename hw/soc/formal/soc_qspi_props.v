// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// The QSPI controller, stated as properties.
//
// Textually included at the end of the soc_qspi module body under
// `ifdef FORMAL, the arrangement every other job in this directory uses.
//
// =====================================================================
// WHAT THESE PROPERTIES ARE ABOUT
// =====================================================================
//
// They were written from soc_qspi.v's HEADER -- the register map and the
// pin protocol it states -- from the AMBA 3 APB slave contract, and from
// the W25Q128JV datasheet's description of an SPI mode 0 frame (section
// 6.1, table 9.6), NOT from the RTL below the header. The method is
// soc_gpio_props.v's: the architectural state is reconstructed from the
// ports alone in ghost registers, and the design's registers, outputs
// and read data are asserted equal to what the ghosts say; those ghost
// equalities double as the induction-strengthening invariants.
//
//   Q1  APB: the block always completes and never errors. A read
//       changes no register and clears no flag except that a read of
//       RX clears DR. A write to an unnamed offset changes nothing.
//   Q2  The registers are what the header says after any sequence of
//       writes: CONF, CTRL.IEN, CMD and ADDR, with CONF, CMD and ADDR
//       REFUSED while BUSY and LOST set when that happens; TX taken
//       whenever written. Every one reads back as itself, reserved bits
//       zero.
//   Q3  The chip selects: at most one low at any time; none low unless
//       BUSY; the one that is low is the one CONF.CS names, and CONF
//       cannot change while BUSY; every one high through the whole
//       deselect gap.
//   Q4  SCK, mode 0: low whenever no chip select is low; it changes
//       only on the block's own tick and never twice within DIV + 1
//       clocks; the first rising edge after CS falls is at least
//       DIV + 1 clocks later; CS rises only with SCK low and at least
//       DIV + 1 clocks after the last falling edge; and after CS rises
//       no chip select falls for 8 (DIV + 1) clocks.
//   Q5  The lanes: outputs never change on a clock where SCK rises;
//       IO2 and IO3 are driven high whenever IO0 is driven alone; IO1
//       is driven only in a four-lane phase; nothing is driven while
//       every chip select is high.
//   Q6  The opcode goes out first: at the k-th rising edge of a frame,
//       0 <= k < 8, IO0 carries OP bit 7 - k with only IO0 and the two
//       held-high lanes driven. With ADDR set, rising edges 8..31
//       (single) or 8..13 (quad) carry ADDR MSB first.
//   Q7  Every frame has the header's length: the number of rising
//       edges between CS falling and CS rising is
//         8 + (ADDR ? (AQUAD ? 6 : 24) : 0) + DUMMY
//           + LEN * (DQUAD ? 2 : 8)
//       counted from the pins by a ghost and compared when CS rises,
//       for every frame that is not aborted; and never exceeded.
//   Q8  DR, DONE, LOST, TXE, BUSY and the interrupt: DR rises only at a
//       falling edge of a data-in phase and falls only to a read of RX
//       or an abort; DONE rises only when BUSY falls and falls only to
//       its write-one, a start or an abort; BUSY rises only on an
//       accepted CMD write; irq_o is IEN and (DONE or DR).
//
// =====================================================================
// WHAT THEY DO NOT COVER
// =====================================================================
//
//   * The data path's VALUE: that RX holds the bytes sampled on the
//     lanes in the right lane order, and that TX's bytes go out in the
//     right order. Those are the cocotb suite's, checked against a
//     flash model whose contents are known; a ghost that assembled the
//     word here would be the design's shift register written a second
//     time. Q6 fixes the direction and order of the wire for the opcode
//     and the address, which go through the same shifter.
//   * The dummy clocks' lane pattern in detail, beyond Q5.
//   * Anything about a device: io_i is free.
//   * Liveness: nothing here says a frame ever ends, because a frame
//     paused at DR waits for software for ever by design. The cover job
//     reaches complete frames so the properties are known not to hold
//     vacuously.
//   * No fault model. The block is unprotected and the header says so.

`ifdef FORMAL

  reg f_past_valid;
  initial f_past_valid = 1'b0;
  always @(posedge clk_i) f_past_valid <= 1'b1;

  initial assume (!rst_ni);

  // The APB master this block sees is soc_apb_bridge.v, whose proof
  // establishes that PENABLE is never high without PSEL, that a SETUP
  // cycle precedes every ACCESS cycle, and that the address, direction
  // and data hold from SETUP through ACCESS. Assumed here, not re-proved.
  always @(*) if (penable_i) assume (psel_i);
  always @(posedge clk_i)
    if (f_past_valid && psel_i && penable_i)
      assume ($past(psel_i) && !$past(penable_i)
              && paddr_i == $past(paddr_i) && pwrite_i == $past(pwrite_i)
              && pwdata_i == $past(pwdata_i));
  always @(posedge clk_i)
    if (f_past_valid && $past(psel_i) && $past(penable_i))
      assume (!penable_i);

  // ---- the ghosts: the architectural state from the ports alone ----
  wire f_acc = psel_i && penable_i;
  wire f_wr  = f_acc && pwrite_i;
  wire f_rd  = f_acc && !pwrite_i;

  reg [DIV_W-1:0] f_div;
  reg [CS_W-1:0]  f_cs;
  reg             f_ien;
  reg [7:0]       f_op;
  reg [3:0]       f_dummy;
  reg             f_addr_en, f_aquad, f_dquad, f_write;
  reg [LEN_W-1:0] f_len;
  reg [23:0]      f_addr;
  reg [31:0]      f_tx;
  reg             f_lost;

  wire f_start = f_wr && (paddr_i == 12'h014) && !busy_q;
  wire f_abort = f_wr && (paddr_i == 12'h004) && pwdata_i[0];

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      f_div <= 0; f_cs <= 0; f_ien <= 0; f_op <= 0; f_dummy <= 0;
      f_addr_en <= 0; f_aquad <= 0; f_dquad <= 0; f_write <= 0;
      f_len <= 0; f_addr <= 0; f_tx <= 0; f_lost <= 0;
    end else begin
      if (f_wr && paddr_i == 12'h004) f_ien <= pwdata_i[1];
      if (f_wr && paddr_i == 12'h010) f_tx  <= pwdata_i;
      if (f_wr && paddr_i == 12'h008 && pwdata_i[3]) f_lost <= 1'b0;
      if (busy_q && f_wr && (paddr_i == 12'h014 || paddr_i == 12'h000
                             || paddr_i == 12'h018))
        f_lost <= 1'b1;
      if (!busy_q && f_wr && paddr_i == 12'h000) begin
        f_div <= pwdata_i[DIV_W-1:0];
        f_cs  <= pwdata_i[8 +: CS_W];
      end
      if (!busy_q && f_wr && paddr_i == 12'h018) f_addr <= pwdata_i[23:0];
      if (!busy_q && f_wr && paddr_i == 12'h014) begin
        f_op <= pwdata_i[7:0]; f_dummy <= pwdata_i[11:8];
        f_addr_en <= pwdata_i[12]; f_aquad <= pwdata_i[13];
        f_dquad <= pwdata_i[14]; f_write <= pwdata_i[15];
        f_len <= pwdata_i[16 +: LEN_W];
      end
    end
  end

  // ---- pin observations -------------------------------------------------
  wire f_any_cs = ~&cs_no;                      // some chip select low
  reg  f_sck_q, f_cs_q;                         // the pins one clock ago
  // Reset with the design: a reset raises every chip select and drops
  // SCK, and a history that remembered otherwise would see a phantom
  // edge in the first clock after it.
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      f_sck_q <= 1'b0;
      f_cs_q  <= 1'b0;
    end else begin
      f_sck_q <= sck_o;
      f_cs_q  <= f_any_cs;
    end
  end
  wire f_sck_rise = f_past_valid && sck_o && !f_sck_q;
  wire f_sck_fall = f_past_valid && !sck_o && f_sck_q;

  // Rising edges since CS fell; clocks since the last SCK change, since
  // CS fell, since the last falling edge and since CS rose. Each "since"
  // counter reads 1 on the clock after the event and saturates.
  reg [19:0] f_nrise;
  reg [7:0]  f_since_edge, f_since_csfall, f_since_fall, f_since_csrise;
  reg        f_seen_fall;
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      f_nrise <= 0; f_since_edge <= 8'hFF; f_since_csfall <= 8'hFF;
      f_since_fall <= 8'hFF; f_since_csrise <= 8'hFF; f_seen_fall <= 0;
    end else begin
      if (f_since_edge != 8'hFF)   f_since_edge   <= f_since_edge + 1;
      if (f_since_csfall != 8'hFF) f_since_csfall <= f_since_csfall + 1;
      if (f_since_fall != 8'hFF)   f_since_fall   <= f_since_fall + 1;
      if (f_since_csrise != 8'hFF) f_since_csrise <= f_since_csrise + 1;
      if (f_past_valid && sck_o != f_sck_q) f_since_edge <= 1;
      if (f_sck_fall) begin f_since_fall <= 1; f_seen_fall <= 1; end
      if (f_sck_rise) f_nrise <= f_nrise + 1;
      if (f_past_valid && f_any_cs && !f_cs_q) begin
        f_since_csfall <= 1; f_nrise <= 0; f_seen_fall <= 0;
      end
      if (f_past_valid && !f_any_cs && f_cs_q) f_since_csrise <= 1;
    end
  end

  // The counters are reset in the clock AFTER the event they time, so
  // an "age" reads zero during the event's own clock and the counter
  // afterwards; a property that asks "how long since" reads the age.
  wire [7:0] f_edge_age   = (sck_o != f_sck_q)      ? 8'd0 : f_since_edge;
  wire [7:0] f_csfall_age = (f_any_cs && !f_cs_q)   ? 8'd0 : f_since_csfall;
  wire [7:0] f_fall_age   = f_sck_fall              ? 8'd0 : f_since_fall;
  wire [7:0] f_csrise_age = (!f_any_cs && f_cs_q)   ? 8'd0 : f_since_csrise;
  wire [19:0] f_nrise_now = (f_any_cs && !f_cs_q)   ? 20'd0 : f_nrise;

  // The frame's expected length in rising edges, from the registers
  // captured at the start (which cannot change while BUSY, Q2).
  wire [19:0] f_addr_clk = f_addr_en ? (f_aquad ? 20'd6 : 20'd24) : 20'd0;
  wire [19:0] f_unit     = f_dquad ? 20'd2 : 20'd8;
  wire [19:0] f_data_clk = f_len * f_unit;
  wire [19:0] f_frame_len = 20'd8 + f_addr_clk + {16'd0, f_dummy} + f_data_clk;
  wire [7:0]  f_half     = {4'h0, div_q} + 8'd1;     // clocks per half period

  // ---- Q1. APB ---------------------------------------------------------
  always @(*) begin
    assert (pready_o);
    assert (!pslverr_o);
  end
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && $past(f_rd)) begin
      assert (div_q == $past(div_q));
      assert (cs_q == $past(cs_q));
      assert (ien_q == $past(ien_q));
      assert (op_q == $past(op_q));
      assert (len_q == $past(len_q));
      assert (addr_q == $past(addr_q));
      assert (tx_q == $past(tx_q));
      assert (lost_q == $past(lost_q));
      if ($past(paddr_i) != 12'h00C && $past(dr_q)) assert (dr_q);
      if ($past(done_q)) assert (done_q);
    end
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && $past(f_wr)
        && ($past(paddr_i) == 12'h01C || $past(paddr_i) == 12'h020
            || $past(paddr_i) == 12'h100 || $past(paddr_i) == 12'hFFC)) begin
      assert (div_q == $past(div_q));
      assert (cs_q == $past(cs_q));
      assert (ien_q == $past(ien_q));
      assert (op_q == $past(op_q));
      assert (len_q == $past(len_q));
      assert (addr_q == $past(addr_q));
      assert (tx_q == $past(tx_q));
      assert (lost_q == $past(lost_q));
      // BUSY and DR are the sequencer's and move on their own clock;
      // a stray write cannot START a frame, which Q8 states.
    end

  // ---- Q2. The registers are the header's --------------------------------
  always @(*) begin
    assert (div_q == f_div);
    assert (cs_q == f_cs);
    assert (ien_q == f_ien);
    assert (op_q == f_op);
    assert (dummy_q == f_dummy);
    assert (addr_en_q == f_addr_en);
    assert (aquad_q == f_aquad);
    assert (dquad_q == f_dquad);
    assert (write_q == f_write);
    assert (len_q == f_len);
    assert (addr_q == f_addr);
    assert (tx_q == f_tx);
    assert (lost_q == f_lost);
  end
  always @(*)
    if (f_rd) begin
      case (paddr_i)
        12'h000: begin
          assert (prdata_o[DIV_W-1:0] == f_div);
          assert (prdata_o[8 +: CS_W] == f_cs);
          assert (prdata_o[7:DIV_W] == 0);
          assert (prdata_o[31:8+CS_W] == 0);
        end
        12'h004: assert (prdata_o == {30'h0, f_ien, 1'b0});
        12'h008: begin
          assert (prdata_o[0] == busy_q);
          assert (prdata_o[1] == dr_q);
          assert (prdata_o[2] == done_q);
          assert (prdata_o[3] == f_lost);
          assert (prdata_o[4] == (state == S_WAITTX));
          assert (prdata_o[31:5] == 0);
        end
        12'h00C: assert (prdata_o == rx_q);
        12'h010: assert (prdata_o == 32'h0);
        12'h014: begin
          assert (prdata_o[7:0] == f_op);
          assert (prdata_o[11:8] == f_dummy);
          assert (prdata_o[15:12] == {f_write, f_dquad, f_aquad, f_addr_en});
          assert (prdata_o[16 +: LEN_W] == f_len);
        end
        12'h018: assert (prdata_o == {8'h0, f_addr});
        default: assert (prdata_o == 32'h0);
      endcase
    end

  // ---- Q3. The chip selects --------------------------------------------------
  always @(*) assert ((cs_no == {NCS{1'b1}}) || $onehot(~cs_no));
  always @(*) if (f_any_cs) assert (busy_q);
  genvar ci;
  generate
    for (ci = 0; ci < NCS; ci = ci + 1) begin : g_cs
      always @(*) if (!cs_no[ci]) assert (cs_q == ci);
    end
  endgenerate
  always @(*) if (state == S_GAP) assert (cs_no == {NCS{1'b1}});

  // ---- Q4. SCK, mode 0 ---------------------------------------------------------
  always @(*) if (!f_any_cs) assert (!sck_o);
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && sck_o != $past(sck_o)) begin
      assert ($past(tick));
      assert ($past(f_edge_age) >= f_half - 8'd1);
    end
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && f_sck_rise
        && $past(f_nrise_now) == 0)
      assert ($past(f_csfall_age) >= f_half - 8'd1);
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && !f_any_cs
        && $past(f_any_cs)) begin
      assert (!$past(sck_o));
      if ($past(f_seen_fall)) assert ($past(f_fall_age) >= f_half - 8'd1);
    end
  // The gap belongs to the frame that ended: its length is fixed by the
  // DIV that frame ran at, and CONF may be rewritten once BUSY falls,
  // so the half period is captured when CS rises.
  reg [7:0] f_half_at_rise;
  always @(posedge clk_i or negedge rst_ni)
    if (!rst_ni) f_half_at_rise <= 8'd1;
    else if (!f_any_cs && f_cs_q) f_half_at_rise <= f_half;
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && f_any_cs
        && !$past(f_any_cs))
      assert ($past(f_csrise_age) >= f_half_at_rise * 8'd8 - 8'd1);

  // ---- Q5. The lanes -------------------------------------------------------------
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && f_sck_rise) begin
      assert (io_o == $past(io_o));
      assert (io_oe_o == $past(io_oe_o));
    end
  always @(*) begin
    if (io_oe_o[0] && !io_oe_o[1]) begin
      assert (io_oe_o[3:2] == 2'b11);
      assert (io_o[3:2] == 2'b11);
    end
    if (io_oe_o[1]) assert (io_oe_o == 4'b1111);
    if (!f_any_cs) assert (io_oe_o == 4'b0000);
  end

  // ---- Q6. The opcode, then the address, MSB first on the wire ----------------
  // f_nrise_now rather than f_nrise: at DIV = 0 the first rising edge
  // is the clock after CS fell, when the ghost counter is still being
  // reset.
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && f_sck_rise
        && $past(f_nrise_now) < 20'd8) begin
      assert ($past(io_oe_o) == 4'b1101);
      assert ($past(io_o[0]) == f_op[3'd7 - $past(f_nrise_now[2:0])]);
    end
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && f_sck_rise
        && f_addr_en && $past(f_nrise_now) >= 20'd8
        && $past(f_nrise_now) < 20'd8 + f_addr_clk) begin
      if (f_aquad) begin
        assert ($past(io_oe_o) == 4'b1111);
        assert ($past(io_o) == f_addr[23 - 4 * ($past(f_nrise_now[4:0]) - 5'd8) -: 4]);
      end else begin
        assert ($past(io_oe_o) == 4'b1101);
        assert ($past(io_o[0]) == f_addr[23 - ($past(f_nrise_now[4:0]) - 5'd8)]);
      end
    end

  // ---- Q7. Every frame has the header's length --------------------------------------
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && !f_any_cs
        && $past(f_any_cs) && $past(state) != S_CSHOLD)
      assert (0);   // CS rises only out of the hold state
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && !f_any_cs
        && $past(f_any_cs) && !$past(f_aborted))
      assert ($past(f_nrise) == f_frame_len);
  always @(*) if (f_any_cs && f_cs_q) assert (f_nrise <= f_frame_len);

  // An abort marks the frame so Q7 does not ask an aborted frame to be
  // whole.
  reg f_aborted;
  always @(posedge clk_i or negedge rst_ni)
    if (!rst_ni) f_aborted <= 0;
    else if (f_abort && state != S_IDLE && state != S_CSHOLD
             && state != S_GAP) f_aborted <= 1;
    else if (!busy_q) f_aborted <= 0;

  // ---- Q8. The flags ----------------------------------------------------------------
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && dr_q && !$past(dr_q))
      assert ($past(f_any_cs) && !f_write && f_len != 0 && $past(sck_o)
              && !sck_o);
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && !dr_q && $past(dr_q))
      assert (($past(f_rd) && $past(paddr_i) == 12'h00C) || $past(f_abort));
  // an abort with SCK high takes effect at the falling edge: the lanes
  // are released there and CS rises a half period later
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && $past(abort_pend)
        && !abort_pend)
      assert (!sck_o && io_oe_o == 4'b0000 && state == S_CSHOLD);
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && done_q && !$past(done_q))
      assert ($past(busy_q) && !busy_q);
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && !done_q && $past(done_q))
      assert (($past(f_wr) && $past(paddr_i) == 12'h008 && $past(pwdata_i[2]))
              || $past(f_start) || $past(f_abort));
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni)) begin
      if (busy_q && !$past(busy_q)) assert ($past(f_start));
      if (!busy_q && $past(busy_q)) assert ($past(state) == S_GAP);
      if (lost_q && !$past(lost_q))
        assert ($past(busy_q) && $past(f_wr)
                && ($past(paddr_i) == 12'h014 || $past(paddr_i) == 12'h000
                    || $past(paddr_i) == 12'h018));
    end
  always @(*) assert (irq_o == (ien_q && (done_q || dr_q)));
  always @(*) if (state == S_WAITTX) assert (busy_q && f_write);
  // a word in TX never waits in the pause for more than one clock
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && $past(state) == S_WAITTX
        && $past(tx_full_q))
      assert (state == S_SHIFT);

  // The address byte the sequencer is sending: A23-16 first.
  wire [7:0] f_abyte = (abytes_left == 2'd3) ? addr_q[23:16]
                     : (abytes_left == 2'd2) ? addr_q[15:8] : addr_q[7:0];

  // ---- structural invariants, for induction --------------------------------------
  //
  // The sequencer's position in the frame, in rising edges completed,
  // from its own counters. The ghost from the pins must agree with it
  // at every clock of a frame: that equality is what makes Q6 and Q7
  // inductive.
  wire [19:0] f_aunit = aquad_q ? 20'd2 : 20'd8;
  wire [19:0] f_dunit = dquad_q ? 20'd2 : 20'd8;
  // The ghost counts a rising edge in the clock AFTER the one it is
  // seen in, so the current unit's edge is counted only once SCK has
  // been high for a clock.
  wire [19:0] f_in_unit = (state == S_SHIFT && sck_q && f_sck_q) ? 20'd1 : 20'd0;
  wire [19:0] f_pos =
      (phase == PH_OP)    ? (20'd8 - {16'd0, unit_left}) + f_in_unit
    : (phase == PH_ADDR)  ? 20'd8 + (20'd3 - {18'd0, abytes_left}) * f_aunit
                            + (f_aunit - {16'd0, unit_left}) + f_in_unit
    : (phase == PH_DUMMY) ? 20'd8 + f_addr_clk + ({16'd0, dummy_q}
                            - {16'd0, unit_left}) + f_in_unit
    : (state == S_WAITRX || state == S_WAITTX)
                          ? 20'd8 + f_addr_clk + {16'd0, dummy_q}
                            + (f_len - bytes_left) * f_dunit
    :                       20'd8 + f_addr_clk + {16'd0, dummy_q}
                            + (f_len - bytes_left) * f_dunit
                            + (f_dunit - {16'd0, unit_left}) + f_in_unit;

  always @(*) begin
    assert (busy_q == (state != S_IDLE));
    // CONF cannot change while BUSY, so the divider never overshoots
    // inside a frame; in IDLE a smaller DIV may have just been written.
    if (state != S_IDLE) assert (div_cnt <= div_q);
    if (state == S_IDLE || state == S_GAP) begin
      assert (!sck_q);
      assert (cs_n_q == {NCS{1'b1}});
      assert (io_oe_q == 4'b0000);
    end
    if (state == S_GAP) assert (gap_cnt >= 4'd1 && gap_cnt <= 4'd8);
    if (state != S_IDLE && state != S_GAP) assert ($onehot(~cs_n_q));
    // The pin ghosts are reset in the clock after CS falls, so they are
    // compared with the sequencer only once CS has been low a clock.
    if (state == S_CSSET) begin
      assert (!sck_q && phase == PH_OP && unit_left == 4'd8);
      assert (io_oe_q == 4'b1101 && out_phase && !quad_phase);
      assert (abytes_left == 2'd3 && bytes_left == len_q);
      if (f_cs_q) assert (f_nrise == 0 && !f_seen_fall);
    end
    if (state == S_WAITRX || state == S_WAITTX) begin
      assert (!sck_q && phase == PH_DATA && bytes_left != 0);
      assert (bytes_left <= len_q && f_nrise == f_pos);
      assert (byte_idx == 2'd0 && len_q != 0);
      assert (out_phase == write_q && quad_phase == dquad_q);
      assert (io_oe_q == (write_q ? (dquad_q ? 4'b1111 : 4'b1101)
                                  : (dquad_q ? 4'b0000 : 4'b1101)));
      if (!dquad_q) assert (io_o_q[3:2] == 2'b11);
    end
    if (state == S_WAITRX) assert (dr_q && !out_phase);
    if (state == S_WAITTX) assert (out_phase);
    if (abort_pend) assert (state == S_SHIFT && sck_q && !dr_q && f_aborted);
    if (state == S_WAITTX) assert (out_phase);
    if (state == S_CSHOLD) begin
      assert (!sck_q);
      if (!f_aborted) assert (f_nrise == f_frame_len);
      assert (f_nrise <= f_frame_len);
    end
    if (state == S_SHIFT || state == S_CSSET) begin
      assert (unit_left >= 4'd1);
      if (f_cs_q) assert (f_nrise == f_pos);
      if (phase == PH_OP)
        assert (unit_left <= 4'd8 && out_phase && !quad_phase
                && io_oe_q == 4'b1101 && abytes_left == 2'd3
                && bytes_left == len_q);
      // the first unit's falling edge decrements unit_left, so a whole
      // first unit with SCK low is only ever the setup state
      if (state == S_SHIFT && phase == PH_OP && unit_left == 4'd8)
        assert (sck_q);
      if (phase == PH_ADDR)
        assert (out_phase && quad_phase == aquad_q && addr_en_q
                && abytes_left >= 2'd1 && abytes_left <= 2'd3
                && unit_left <= f_aunit[3:0]
                && io_oe_q == (aquad_q ? 4'b1111 : 4'b1101)
                && bytes_left == len_q);
      if (phase == PH_DUMMY)
        assert (!out_phase && unit_left <= dummy_q && dummy_q != 0
                && bytes_left == len_q);
      if (phase == PH_DATA)
        assert (out_phase == write_q && quad_phase == dquad_q
                && bytes_left >= 1 && bytes_left <= len_q
                && unit_left <= f_dunit[3:0] && len_q != 0);
      // what is on the lanes is the register's bit for this unit, and
      // the shifter holds what is still to come: this is what makes Q6
      // inductive rather than merely true from reset
      if (phase == PH_OP) begin
        assert (io_o_q[0] == op_q[unit_left - 4'd1]);
        assert (cur == (op_q << (4'd8 - unit_left)));
      end
      if (phase == PH_ADDR && !aquad_q) begin
        assert (io_o_q[0] == f_abyte[unit_left - 4'd1]);
        assert (cur == (f_abyte << (4'd8 - unit_left)));
      end
      if (phase == PH_ADDR && aquad_q) begin
        assert (io_o_q == ((unit_left == 4'd2) ? f_abyte[7:4] : f_abyte[3:0]));
        assert (cur == ((unit_left == 4'd2) ? f_abyte : {f_abyte[3:0], 4'h0}));
      end
      // the current byte's lane pattern in the data phase
      if (phase == PH_DATA && !write_q)
        assert (io_oe_q == (dquad_q ? 4'b0000 : 4'b1101));
      if (phase == PH_DATA && write_q)
        assert (io_oe_q == (dquad_q ? 4'b1111 : 4'b1101));
    end
  end

  // ---- the ghost ages against the divider, for induction ----------------------
  //
  // Each "since" ghost counts from a pin event; the design counts the
  // same interval in its divider and, in the gap, in gap_cnt. Tying the
  // two is what lets the Q4 timing properties be proved by induction
  // rather than only checked from reset. All in 9-bit arithmetic so a
  // small age and a reloaded divider cannot underflow.
  wire [8:0] f_age_edge9   = {1'b0, f_edge_age};
  wire [8:0] f_age_csfall9 = {1'b0, f_csfall_age};
  wire [8:0] f_age_fall9   = {1'b0, f_fall_age};
  wire [8:0] f_div9        = {5'd0, div_cnt};
  wire [8:0] f_half9       = {1'b0, f_half};
  always @(*) if (rst_ni) begin
    if (state != S_IDLE)
      assert (f_age_edge9 + f_div9 + 9'd1 >= f_half9);
    if (state == S_CSSET)
      assert (f_age_csfall9 + f_div9 + 9'd1 >= f_half9);
    if (state == S_CSHOLD)
      assert (f_age_fall9 + f_div9 + 9'd1 >= f_half9);
    if (state == S_GAP) begin
      // captured in the clock after CS rises, so compared from then on
      if (!f_cs_q) assert (f_half_at_rise == f_half);
      assert ({1'b0, f_csrise_age} ==
              (9'd8 - {5'd0, gap_cnt}) * f_half9 + (f_half9 - 9'd1 - f_div9));
    end
    if (state == S_IDLE)
      assert ({1'b0, f_csrise_age} >= {1'b0, f_half_at_rise} * 9'd8);
    // captured from f_half, which is DIV + 1: never zero, never above
    // the widest half period, so the gap bound cannot underflow
    assert (f_half_at_rise >= 8'd1 && f_half_at_rise <= (8'd1 << DIV_W));
  end

  // ---- vacuity ------------------------------------------------------------
  always @(posedge clk_i) begin
    cover (f_past_valid && rst_ni && !f_any_cs && $past(f_any_cs)
           && $past(f_nrise) == 20'd8);                        // opcode only
    cover (f_past_valid && rst_ni && !f_any_cs && $past(f_any_cs)
           && f_addr_en && f_aquad && f_dquad && f_len != 0
           && f_dummy != 0 && !f_aborted);                     // a quad I/O read
    cover (f_past_valid && rst_ni && !f_any_cs && $past(f_any_cs)
           && f_addr_en && !f_aquad && !f_dquad && f_len != 0
           && !f_aborted);                                     // a single read
    cover (f_past_valid && rst_ni && $past(state) == S_WAITRX
           && state == S_SHIFT);                                // resumed after DR
    cover (f_past_valid && rst_ni && $past(state) == S_WAITTX
           && state == S_SHIFT);                                // resumed after TXE
    cover (f_past_valid && rst_ni && done_q && !$past(done_q));
    cover (f_past_valid && rst_ni && lost_q && !$past(lost_q));
    cover (f_past_valid && rst_ni && irq_o);
    cover (f_past_valid && rst_ni && $past(f_abort) && $past(state) == S_SHIFT);
    cover (f_past_valid && rst_ni && !cs_no[NCS-1]);           // the last chip select
    cover (f_past_valid && rst_ni && !f_any_cs && $past(f_any_cs)
           && f_dummy != 0 && f_len == 0 && !f_aborted);       // dummy then end
    cover (f_past_valid && rst_ni && f_sck_rise && div_q != 0); // a slower clock
  end

`endif
