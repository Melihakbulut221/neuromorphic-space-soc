// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// GPIO, stated as properties.
//
// Textually included at the end of the soc_gpio module body under
// `ifdef FORMAL, the arrangement soc_bus, soc_apb_bridge, soc_clint,
// soc_wdog and soc_busstat already use.
//
// =====================================================================
// WHAT THESE PROPERTIES ARE ABOUT
// =====================================================================
//
// They were written from grip.pdf chapter 62 -- tables 923 to 937 and
// the prose of 62.2 -- and from the AMBA 3 APB slave contract, NOT
// from soc_gpio.v. The method is soc_clint_props.v's: every piece of
// architectural state is RECONSTRUCTED from the ports alone, in ghost
// registers that read PSEL, PENABLE, PWRITE, PADDR, PWDATA and gpio_i
// and nothing inside the design, and the design's outputs are then
// asserted equal to what the ghosts say. A block that stored the wrong
// register, applied the wrong logical operation, synchronised by one
// stage instead of two, or gated the interrupt wrongly fails a property
// here, and a property that merely restated the design's own state
// encoding would be worth nothing (docs/09's vacuity rule).
//
//   P1  APB: the block always completes and never errors.
//   P2  OUTPUT, DIRECTION and IMASK are what the specification says
//       they are after any sequence of plain, OR, AND and XOR writes
//       (tables 925, 926, 927, 937); IPOL and IEDGE after plain writes
//       (928, 929). Every one reads back as itself.
//   P3  The pins: gpio_o is OUTPUT and gpio_oe_o is DIRECTION, this
//       cycle, always.
//   P4  DATA is gpio_i delayed by exactly two clocks (62.2) -- not
//       one, not three, and never the OUTPUT register.
//   P5  A line's flag is set by a detection under the mask, in the
//       polarity and mode the registers select (62.2), and by nothing
//       else; it falls only to a write of 1 to its own IFLAG bit
//       (table 934), and a detection in the cycle of that write wins.
//   P6  irq_o is the OR of IFLAG and IMASK, which is what makes it a
//       level the handler can drop by clearing the flag and software
//       can silence by masking.
//   P7  Nothing changes on a read, on a write to an unnamed offset, or
//       on a write to a read-only register. The reserved upper bits of
//       every register read zero. CAP reports this configuration and
//       IAVAIL reports every line.
//
// =====================================================================
// WHAT THEY DO NOT COVER
// =====================================================================
//
//   * Anything about a pad. gpio_i is free here; that it is connected
//     to the pin gpio_o drives is a property of the board or of
//     hw/soc/tb/tb_soc.v's model of one, and the whole-SoC run is
//     where that is demonstrated.
//   * Metastability. Two flip-flops in series is what the
//     specification asks for and what P4 checks is present; whether
//     two is enough for a given pin, clock and process is not a
//     property of RTL.
//   * Liveness of the interrupt: nothing here says the handler ever
//     runs. The cover job reaches every detection mode so that the
//     properties are known not to hold vacuously.
//   * No fault model. The block is unprotected and the header says so.

`ifdef FORMAL

  reg f_past_valid;
  initial f_past_valid = 1'b0;
  always @(posedge clk_i) f_past_valid <= 1'b1;

  // Two cycles of history are needed for the synchroniser property,
  // so a second flag says when $past($past()) is meaningful.
  reg f_past2_valid;
  initial f_past2_valid = 1'b0;
  always @(posedge clk_i) f_past2_valid <= f_past_valid;

  initial assume (!rst_ni);

  // The APB master this block will actually see is soc_apb_bridge.v,
  // whose proof (A1-A11) establishes that PENABLE is never high without
  // PSEL and that a SETUP cycle precedes every ACCESS cycle. Those are
  // assumed here rather than re-proved, so the properties below are
  // about the slave and not about a master no bridge would be.
  always @(*) if (penable_i) assume (psel_i);

  // ---- the ghosts: the architectural state from the ports alone ----
  wire f_wr = psel_i && penable_i && pwrite_i;
  wire [NBITS-1:0] f_w = pwdata_i[NBITS-1:0];

  reg [NBITS-1:0] f_out, f_dir, f_imask, f_ipol, f_iedge, f_flag;
  reg [NBITS-1:0] f_d1, f_d2, f_d3;    // gpio_i, one, two, three clocks ago

  // Table 937: New value = <Old value> logical-op <Write data>.
  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      f_out <= 0; f_dir <= 0; f_imask <= 0; f_ipol <= 0; f_iedge <= 0;
    end else if (f_wr) begin
      case (paddr_i)
        12'h004: f_out   <= f_w;
        12'h054: f_out   <= f_out | f_w;
        12'h064: f_out   <= f_out & f_w;
        12'h074: f_out   <= f_out ^ f_w;
        12'h008: f_dir   <= f_w;
        12'h058: f_dir   <= f_dir | f_w;
        12'h068: f_dir   <= f_dir & f_w;
        12'h078: f_dir   <= f_dir ^ f_w;
        12'h00C: f_imask <= f_w;
        12'h05C: f_imask <= f_imask | f_w;
        12'h06C: f_imask <= f_imask & f_w;
        12'h07C: f_imask <= f_imask ^ f_w;
        12'h010: f_ipol  <= f_w;
        12'h014: f_iedge <= f_w;
        default: ;
      endcase
    end
  end

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      f_d1 <= 0; f_d2 <= 0; f_d3 <= 0;
    end else begin
      f_d1 <= gpio_i; f_d2 <= f_d1; f_d3 <= f_d2;
    end
  end

  // 62.2, per line: level mode fires while the synchronised value
  // equals IPOL; edge mode fires in the cycle the synchronised value
  // becomes IPOL. Both only under the mask.
  wire [NBITS-1:0] f_level  = ~(f_d2 ^ f_ipol);
  wire [NBITS-1:0] f_edge   = (f_d2 ^ f_d3) & f_level;
  wire [NBITS-1:0] f_detect = f_imask & ((f_iedge & f_edge) | (~f_iedge & f_level));
  wire [NBITS-1:0] f_clr    = (f_wr && paddr_i == 12'h044) ? f_w : {NBITS{1'b0}};

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) f_flag <= 0;
    else         f_flag <= (f_flag & ~f_clr) | f_detect;
  end

  // ---- P1. APB --------------------------------------------------------
  always @(*) begin
    assert (pready_o);
    assert (!pslverr_o);
  end

  // ---- P2. The registers are the specification's -----------------------
  // These are the induction-strengthening invariants as well as the
  // checks: each ties one piece of the design's state to the ghost that
  // reconstructs it, so k-induction starts from a consistent state.
  always @(*) begin
    assert (out_q   == f_out);
    assert (dir_q   == f_dir);
    assert (imask_q == f_imask);
    assert (ipol_q  == f_ipol);
    assert (iedge_q == f_iedge);
    assert (iflag_q == f_flag);
    assert (sync1   == f_d1);
    assert (sync2   == f_d2);
    assert (prev    == f_d3);
  end

  // and they read back as themselves, with the reserved bits zero
  always @(*)
    if (psel_i && penable_i && !pwrite_i) begin
      case (paddr_i)
        12'h000: assert (prdata_o == {{(32-NBITS){1'b0}}, f_d2});
        12'h004: assert (prdata_o == {{(32-NBITS){1'b0}}, f_out});
        12'h008: assert (prdata_o == {{(32-NBITS){1'b0}}, f_dir});
        12'h00C: assert (prdata_o == {{(32-NBITS){1'b0}}, f_imask});
        12'h010: assert (prdata_o == {{(32-NBITS){1'b0}}, f_ipol});
        12'h014: assert (prdata_o == {{(32-NBITS){1'b0}}, f_iedge});
        12'h018: assert (prdata_o == 32'h0);                       // BYPASS
        12'h01C: begin                                             // CAP
          assert (prdata_o[18] == 1'b0);                           // PU
          assert (prdata_o[17] == 1'b0);                           // IER
          assert (prdata_o[16] == 1'b1);                           // IFL
          assert (prdata_o[12:8] == 5'd1);                         // IRQGEN
          assert (prdata_o[4:0] == NBITS - 1);                     // NLINES
          assert (prdata_o[31:19] == 0 && prdata_o[15:13] == 0
                  && prdata_o[7:5] == 0);
        end
        12'h040: assert (prdata_o == {{(32-NBITS){1'b0}}, {NBITS{1'b1}}});
        12'h044: assert (prdata_o == {{(32-NBITS){1'b0}}, f_flag});
        default: assert (prdata_o == 32'h0);
      endcase
    end

  // ---- P3. The pins ----------------------------------------------------
  always @(*) begin
    assert (gpio_o    == f_out);
    assert (gpio_oe_o == f_dir);
  end

  // ---- P4. DATA is the input two clocks ago, from the port -------------
  // Stated on the port history directly, not through the ghost, so the
  // ghost's own delay chain is not what is being trusted.
  always @(posedge clk_i)
    if (f_past2_valid && rst_ni && $past(rst_ni) && $past(rst_ni, 2)
        && psel_i && penable_i && !pwrite_i && paddr_i == 12'h000)
      assert (prdata_o[NBITS-1:0] == $past(gpio_i, 2));

  // ---- P5. The flag ----------------------------------------------------
  genvar fi;
  generate
    for (fi = 0; fi < NBITS; fi = fi + 1) begin : g_props
      // set only by a detection under the mask
      always @(posedge clk_i)
        if (f_past_valid && rst_ni && $past(rst_ni)
            && !$past(iflag_q[fi]) && iflag_q[fi])
          assert ($past(f_detect[fi]) && $past(imask_q[fi]));
      // cleared only by its own write-one bit, and only when no
      // detection arrived in that cycle
      always @(posedge clk_i)
        if (f_past_valid && rst_ni && $past(rst_ni)
            && $past(iflag_q[fi]) && !iflag_q[fi])
          assert ($past(f_wr) && $past(paddr_i) == 12'h044
                  && $past(pwdata_i[fi]) && !$past(f_detect[fi]));
      // a masked line never sets its flag
      always @(posedge clk_i)
        if (f_past_valid && rst_ni && $past(rst_ni)
            && !$past(imask_q[fi]) && !$past(iflag_q[fi]))
          assert (!iflag_q[fi]);
    end
  endgenerate

  // ---- P6. The interrupt is a level of the flags under the mask --------
  always @(*) assert (irq_o == (|(iflag_q & imask_q)));
  always @(*) if (!rst_ni) assert (!irq_o);

  // ---- P7. Frame: reads and stray writes change nothing ----------------
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && !$past(f_wr)) begin
      assert (out_q   == $past(out_q));
      assert (dir_q   == $past(dir_q));
      assert (imask_q == $past(imask_q));
      assert (ipol_q  == $past(ipol_q));
      assert (iedge_q == $past(iedge_q));
    end
  always @(posedge clk_i)
    if (f_past_valid && rst_ni && $past(rst_ni) && $past(f_wr)
        && ($past(paddr_i) == 12'h000 || $past(paddr_i) == 12'h018
            || $past(paddr_i) == 12'h01C || $past(paddr_i) == 12'h040
            || $past(paddr_i) == 12'h020 || $past(paddr_i) == 12'h048
            || $past(paddr_i) == 12'h04C || $past(paddr_i) == 12'h050
            || $past(paddr_i) == 12'h100 || $past(paddr_i) == 12'hFFC)) begin
      assert (out_q   == $past(out_q));
      assert (dir_q   == $past(dir_q));
      assert (imask_q == $past(imask_q));
      assert (ipol_q  == $past(ipol_q));
      assert (iedge_q == $past(iedge_q));
      // and a stray write does not clear a flag
      assert ((iflag_q & $past(iflag_q)) == $past(iflag_q));
    end

  // ---- vacuity ------------------------------------------------------------
  // docs/09 B.1. Every behaviour above has to be reachable, or the job
  // proves nothing about the case it names.
  always @(posedge clk_i) begin
    // a pin driven high and read back as an input two clocks later
    cover (f_past2_valid && rst_ni && psel_i && penable_i && !pwrite_i
           && paddr_i == 12'h000 && prdata_o[0] && $past(gpio_i[0], 2));
    // each detection mode, on line 0
    cover (f_past_valid && rst_ni && $past(f_detect[0]) && !$past(f_iedge[0])
           && $past(f_ipol[0]) && iflag_q[0]);                    // level high
    cover (f_past_valid && rst_ni && $past(f_detect[0]) && !$past(f_iedge[0])
           && !$past(f_ipol[0]) && iflag_q[0]);                   // level low
    cover (f_past_valid && rst_ni && $past(f_detect[0]) && $past(f_iedge[0])
           && $past(f_ipol[0]) && iflag_q[0]);                    // rising
    cover (f_past_valid && rst_ni && $past(f_detect[0]) && $past(f_iedge[0])
           && !$past(f_ipol[0]) && iflag_q[0]);                   // falling
    // the race: a clear and a detection in one cycle, flag still set
    cover (f_past_valid && rst_ni && $past(f_clr[0]) && $past(f_detect[0])
           && iflag_q[0]);
    // a flag actually cleared
    cover (f_past_valid && rst_ni && $past(iflag_q[0]) && !iflag_q[0]);
    // the interrupt high, then dropped by a clear
    cover (f_past_valid && rst_ni && irq_o);
    cover (f_past_valid && rst_ni && $past(irq_o) && !irq_o);
    // each logical operation, observed changing a register
    cover (f_past_valid && rst_ni && $past(f_wr) && $past(paddr_i) == 12'h054
           && out_q != $past(out_q));
    cover (f_past_valid && rst_ni && $past(f_wr) && $past(paddr_i) == 12'h068
           && dir_q != $past(dir_q));
    cover (f_past_valid && rst_ni && $past(f_wr) && $past(paddr_i) == 12'h07C
           && imask_q != $past(imask_q));
    // a pin configured as an output and driven
    cover (rst_ni && gpio_oe_o[0] && gpio_o[0]);
  end

`endif
