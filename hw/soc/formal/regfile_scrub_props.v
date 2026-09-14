// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0
// The register file, with its storage and its scrub, proved.
//
// WHAT THIS JOB IS FOR, AND WHY IT EXISTS BESIDE regfile_secded.sby
//
// regfile_secded.sby proves the (40,32) SHORTENING of the codec and
// says so in its header: "no storage, no read multiplexer, no scrub,
// no addresses". docs/63 section 11 item 3 then measured the property
// that DOES involve storage and scrub -- riscv-formal's reg check on
// the substituted core -- and found it proves to check cycle 18 and
// times out at 21, 23 and 25 under six engines at four hours each,
// because the solver is made to reason about the whole core between
// the write and the read.
//
// docs/63 ranked four routes out. This file is ROUTE 2, in its own
// words: "a check that asked only the register file -- write a word,
// wait N cycles with the scrub running, read it back -- would be the
// size of regfile_secded.sby and would close by induction. It would
// prove the register file, not the core's use of it, and it would be
// an honest and much stronger statement about the scrub than anything
// here." Route 1 was to state the claim at 18 and stop, which docs/63
// did. This is the route that closes it.
//
// WHAT IS PROVED (the R properties), and what is not
//
//   R1  read-after-write survives the scrub. Once the core writes x to
//       register r and does not write r again, port A reads x from r,
//       at every later cycle, while the scrub walks and rewrites.
//   R2  the scrub walks every architectural register. ptr_q visits each
//       of 1..31 (cover), and never visits 0.
//   R3  the scrub and the core never contend. The write port is the
//       core's on any cycle it writes; the scrub takes only the cycles
//       the core leaves.
//   R4  a fault-free file reports no error. With no upset injected, the
//       three bits of rf_ecc_err_o are never raised.
//
// NOT proved: what happens under an upset. That is the fault-injection
// campaigns' subject (docs/43, docs/74), and formal/lif_ctrl.sby's
// bmc_safe is the template for the any-state form. This job establishes
// the fault-FREE contract the scrub must keep, which the core's reg
// check could not reach at depth 25.
//
// THE MODEL. The real hw/soc/rtl/ibex_regfile_secded.v is instantiated
// with SCRUB=1; nothing is abstracted. Route 3 (an uninterpreted codec)
// was docs/63's "most likely to make cycle 25 tractable" -- it is not
// needed here, because without the core in the cone the real codec is
// small enough to induct over.

`default_nettype none

// THE CLOCK IS A PORT, as in every working job in this directory. A
// free internal `reg clk_i` is not a clock to the solver -- it may hold
// it constant, so no edge ever fires, assertions sampled at posedge
// misfire and every cover stays unreached. That is exactly what the
// first two runs of this job did: R4 "failed" at step 2 and 30 of 31
// visit covers were unreached at depth 40. With clk_i as a top-level
// input, prep treats it as the stepped clock and smtbmc advances it.
module regfile_scrub_props (
    input wire clk_i
);

  reg  rst_ni;
  reg  [4:0]  raddr_a_i, raddr_b_i, waddr_a_i;
  reg  [31:0] wdata_a_i;
  reg         we_a_i;
  wire [31:0] rdata_a_o, rdata_b_o;
  wire [34:0] rcap_a_o, rcap_b_o;
  wire [2:0]  rf_ecc_err_o;

  ibex_register_file_ff #(
      .SCRUB (1)
  ) dut (
      .clk_i            (clk_i),
      .rst_ni           (rst_ni),
      .test_en_i        (1'b0),
      .dummy_instr_id_i (1'b0),
      .dummy_instr_wb_i (1'b0),
      .cheriot_enable_i (4'b0),
      .raddr_a_i        (raddr_a_i),
      .rdata_a_o        (rdata_a_o),
      .rcap_a_o         (rcap_a_o),
      .raddr_b_i        (raddr_b_i),
      .rdata_b_o        (rdata_b_o),
      .rcap_b_o         (rcap_b_o),
      .waddr_a_i        (waddr_a_i),
      .wdata_a_i        (wdata_a_i),
      .wcap_a_i         (35'b0),
      .we_a_i           (we_a_i),
      .rf_ecc_err_o     (rf_ecc_err_o)
  );

  // ---- reset discipline: held for the first cycle, then released ----
  initial assume (!rst_ni);
  reg past_valid = 1'b0;
  always @(posedge clk_i) past_valid <= 1'b1;
  always @(*) if (!past_valid) assume (!rst_ni);
  reg released = 1'b0;
  always @(posedge clk_i) if (rst_ni) released <= 1'b1;
  always @(*) if (released) assume (rst_ni);

  // Register 0 is hard-wired zero in the ISA; the core never writes it.
  // Constraining the environment to the ISA is what makes R1 provable
  // rather than vacuously false on a write to x0.
  always @(*) if (we_a_i) assume (waddr_a_i != 5'd0);

  // ---- R1: read-after-write survives the scrub ----------------------
  // A free register index and a free value, chosen once by the solver.
  // Once the core has written `val` to `idx` and never writes `idx`
  // again, port A must read `val` from `idx` forever after.
  (* anyconst *) reg [4:0]  idx;
  (* anyconst *) reg [31:0] val;
  always @(*) assume (idx != 5'd0);

  reg  armed = 1'b0;                     // `val` has landed in `idx`
  always @(posedge clk_i or negedge rst_ni)
    if (!rst_ni)                                    armed <= 1'b0;
    else if (we_a_i && waddr_a_i == idx)            armed <= (wdata_a_i == val);

  // After arming, the environment does not write `idx` again -- that is
  // the "does not write r again" half of the claim.
  always @(*) if (armed && we_a_i) assume (waddr_a_i != idx);

  always @(posedge clk_i)
    if (rst_ni && past_valid && armed && raddr_a_i == idx)
      assert (rdata_a_o == val);

  // R2 and R3 are in ibex_regfile_secded_props.v, included INTO the
  // module, where scrub_go and scrub_ptr are in scope natively.

  // ---- R4: a fault-free file reports no error -----------------------
  always @(posedge clk_i)
    if (rst_ni && past_valid)
      assert (rf_ecc_err_o == 3'b000);

endmodule

`default_nettype wire
