// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// The scrubber's own invariants, textually included at the end of
// hw/soc/rtl/soc_mem_ecc.v under `ifdef FORMAL, because they name
// state the row port does not show. soc_mem_ecc.sby's harness,
// soc_mem_ecc_props.v, states everything observable at the ports.
//
//   M6  the pointer moves only on an examined row: a scrub read the bus
//       pre-empted leaves it where it was
//   M7  a scrub read is never issued in the cycle after a scrub read,
//       and never while the bus has the port
//   M8  a write-back happens only in the examine cycle and only with a
//       lane the decoder corrected

`ifdef FORMAL
  generate if (HARDEN) begin : g_int_props
    reg f_int_past_valid;
    initial f_int_past_valid = 1'b0;
    always @(posedge clk_i) f_int_past_valid <= 1'b1;

    always @(posedge clk_i)
      if (f_int_past_valid && $past(rst_ni) && rst_ni && !$past(s_hit))
        assert (g_scrub.sptr == $past(g_scrub.sptr));

    always @(*) begin
      if (s_go) begin
        assert (!req_i);
        assert (!g_scrub.srd_q);
      end
      if (s_wb) begin
        assert (s_hit);
        assert (sec_any);
        assert (!req_i);
      end
      if (s_hit) assert (g_scrub.srd_q && !req_i);
    end

    always @(posedge clk_i) begin
      cover (f_int_past_valid && rst_ni && s_go);
      cover (f_int_past_valid && rst_ni && s_hit);
      cover (f_int_past_valid && rst_ni && $past(g_scrub.srd_q) && $past(req_i));
      cover (f_int_past_valid && rst_ni && $past(s_hit)
             && g_scrub.sptr == {AW{1'b0}} && $past(g_scrub.sptr) != {AW{1'b0}});
    end
  end endgenerate
`endif
