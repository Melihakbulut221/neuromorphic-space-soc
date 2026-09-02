// Word-addressed memory behind one system-bus slave port.
//
// SCOPE, stated first because it bounds every claim made with this file
// in the loop: this is a BEHAVIOURAL MODEL of a memory, not a memory.
// It infers a register array, it has no ECC, no scrubbing, no macro
// behind it and no wrapper for one. The real SoC needs SRAM macros with
// stored check bits -- docs/38 section 7 already records that
// regenerating check bits on read makes the core's integrity check
// vacuous, and that trap is inherited here: this model has no check bits
// at all, and soc_top.v therefore fixes SecureIbex to 0 and says so.
//
// What it is for: giving the fabric and the memory map something real to
// talk to, so that a compiled program can be fetched, executed and
// observed through the actual decode. That is what it is used for in
// hw/soc/tb/tb_soc.v and nothing more.
//
// Protocol: soc_bus.v rules S1-S4. Always ready (gnt = req), fixed
// response latency, in order by construction.
//
// RO = 1 makes it a ROM: a write is not performed and is answered with
// err, so a stray store into the boot ROM is a store access fault rather
// than a silent no-op.
//
// ---------------------------------------------------------------------
// RDREG -- THE RESPONSE REGISTER, AND WHY A BEHAVIOURAL MODEL HAS ONE
// ---------------------------------------------------------------------
//
// RDREG = 1 adds one pipeline stage to the response, so a granted
// request is answered TWO cycles later instead of one. Nothing about
// this model needs it: an inferred register array has no read arc worth
// breaking. It is here because hw/soc/rtl/soc_mem_sram.v needs it and
// because the two files must have the SAME PROTOCOL TIMING or every
// cycle count measured in simulation is a count for a different SoC.
//
// docs/50 is the measurement. The short version: the binding path of
// docs/47's sign-off starts at an SRAM macro's A_DOUT and the macro's
// own A_CLK -> A_DOUT arc is 9.5277 ns of a 20 ns period, so no amount
// of placement, routing or logic restructuring can reach the target
// while that arc and the whole read return path share one cycle. RDREG
// is the split.
//
// WHAT IT DOES NOT DO. It does not change gnt: this memory is still
// always ready and still accepts a request every cycle, so the extra
// cycle is LATENCY and not throughput. Two granted requests are in
// flight at once and their responses come back in order, one rvalid
// each, which is exactly what soc_bus.v's S1 and S3 already allow --
// see that file's protocol block, rule 3, "It may be one or more cycles
// after the grant".
//
// THE WRITE RESPONSE IS DELAYED TOO, and that is not an oversight. Rule
// 3 gives every granted request exactly one rvalid and rule 4 requires
// them in order. A memory that answered writes in one cycle and reads
// in two would reorder its own responses the first time a store
// followed a load, and the fabric's ownership queue would hand the
// load's data to whoever owned the store. Latency here is a property of
// the SLAVE, not of the access.

`timescale 1ns / 1ps

module soc_mem #(
    parameter integer WORDS     = 4096,
    parameter         RO        = 1'b0,
    parameter         INIT_FILE = "",
    // Byte offset of the first word of INIT_FILE within this memory.
    parameter integer INIT_WORD = 0,
    // One extra response stage. See the header.
    parameter         RDREG     = 1'b0
) (
    input  wire        clk_i,
    input  wire        rst_ni,

    input  wire        req_i,
    input  wire [31:0] addr_i,
    input  wire        we_i,
    input  wire [3:0]  be_i,
    input  wire [31:0] wdata_i,
    output wire        gnt_o,
    output wire        rvalid_o,
    output wire [31:0] rdata_o,
    output wire        err_o
);

  reg [31:0] mem [0:WORDS-1];

  // Zeroed rather than left x. A fetch from uninitialised memory should
  // decode as an illegal instruction and trap, not propagate x through
  // the core and make every downstream signal unreadable.
  integer i;
  initial begin
    for (i = 0; i < WORDS; i = i + 1) mem[i] = 32'h0000_0000;
    if (INIT_FILE != "") $readmemh(INIT_FILE, mem, INIT_WORD);
  end

  assign gnt_o = req_i;

  // Word index. The fabric has already decoded the region, so the low
  // bits are what selects inside it; the modulo makes an out-of-range
  // index alias rather than read out of bounds, which matters only if
  // the region size and WORDS disagree. soc_top.v derives WORDS from the
  // generated map so they cannot.
  wire [31:0] widx = (addr_i >> 2) % WORDS;

  wire write_attempt = req_i && we_i;
  wire do_write      = write_attempt && !RO;

  // ---- stage 0: the array, unchanged ---------------------------------
  reg        rv0;
  reg        er0;
  reg [31:0] rd0;

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      rv0 <= 1'b0;
      rd0 <= 32'h0;
      er0 <= 1'b0;
    end else begin
      rv0 <= req_i;
      er0 <= write_attempt && RO;
      if (req_i) begin
        rd0 <= mem[widx];
        if (do_write) begin
          if (be_i[0]) mem[widx][7:0]   <= wdata_i[7:0];
          if (be_i[1]) mem[widx][15:8]  <= wdata_i[15:8];
          if (be_i[2]) mem[widx][23:16] <= wdata_i[23:16];
          if (be_i[3]) mem[widx][31:24] <= wdata_i[31:24];
        end
      end
    end
  end

  // ---- the response, with or without the extra stage ------------------
  //
  // TWO NAMED GENERATE ARMS AND NOT A TERNARY, and the reason is
  // docs/49 section 8.1: a parameter override that is silently dropped
  // looks exactly like one that took. Exactly one of `g_rd1` and `g_rd2`
  // exists in any elaborated design, so the arm's name in the compiled
  // object is a witness for the parameter's value, and
  // hw/soc/flow/sim_soc.sh refuses to run if the wrong one is there.
  // The same two names appear in hw/soc/rtl/soc_mem_sram.v.
  generate
  if (!RDREG) begin : g_rd1

    assign rvalid_o = rv0;
    assign rdata_o  = rd0;
    assign err_o    = er0;

  end
  if (RDREG) begin : g_rd2

    reg        rv1;
    reg        er1;
    reg [31:0] rd1;

    always @(posedge clk_i or negedge rst_ni) begin
      if (!rst_ni) begin
        rv1 <= 1'b0;
        rd1 <= 32'h0;
        er1 <= 1'b0;
      end else begin
        rv1 <= rv0;
        er1 <= er0;
        // Gated on rv0 so rdata_o HOLDS between responses exactly as the
        // unregistered arm's does; the value is meaningless while
        // rvalid_o is low either way, and holding is what makes the two
        // arms' waveforms differ by a delay and nothing else.
        if (rv0) rd1 <= rd0;
      end
    end

    assign rvalid_o = rv1;
    assign rdata_o  = rd1;
    assign err_o    = er1;

  end
  endgenerate

endmodule
