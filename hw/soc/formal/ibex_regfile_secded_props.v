// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0
//
// Included into hw/soc/rtl/ibex_regfile_secded.v under `ifdef FORMAL,
// the arrangement every fabric block in this directory uses, so that
// the scrub's INTERNALS -- scrub_go, scrub_ptr -- are in scope natively.
// The first version of this job referenced them hierarchically from an
// outside wrapper (dut.scrub_go), and prep bound that name to a stale
// duplicate net with the wrong width; the trace showed dut.scrub_go = 1
// while we_a_i = 1, which the RTL's own `assign scrub_go = !we_a_i`
// makes impossible. That was the wrapper's bug, not the design's.
//
// R2 and R3 live here for that reason. R1 and R4 speak only through the
// ports and stay in regfile_scrub_props.v.
`ifdef FORMAL
  reg f_past_valid = 1'b0;
  always @(posedge clk_i) f_past_valid <= 1'b1;

  // ---- R2: the scrub walks every register, and never x0 --------------
  always @(posedge clk_i)
    if (rst_ni && f_past_valid) assert (g_plain_rf.scrub_ptr != 5'd0);

  genvar fr;
  generate
    for (fr = 1; fr < 32; fr = fr + 1) begin : g_visit
      always @(posedge clk_i)
        if (rst_ni && f_past_valid) cover (g_plain_rf.scrub_ptr == fr[4:0]);
    end
  endgenerate

  // ---- R3: no contention on the write port ---------------------------
  always @(posedge clk_i)
    if (rst_ni && f_past_valid) assert (!(g_plain_rf.scrub_go && we_a_i));
`endif
