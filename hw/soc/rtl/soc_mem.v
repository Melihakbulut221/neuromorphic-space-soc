// Word-addressed memory behind one system-bus slave port.
//
// SCOPE, stated first because it bounds every claim made with this file
// in the loop: this is a BEHAVIOURAL MODEL of a memory, not a memory.
// It infers a register array, it has no macro behind it and no wrapper
// for one. What it DOES carry, since docs/67, is the same code, the
// same correction and the same scrubber the macro build carries,
// because both instantiate hw/soc/rtl/soc_mem_ecc.v: the check bits a
// row stores, the byte lanes a write touches, the error a read answers
// with and the cycle on which the scrubber walks are ONE implementation
// with a register array under it here and six RM_IHPSG13 macros under
// it in soc_mem_sram.v. Until docs/67 this header said "no ECC, no
// scrubbing" and soc_top.v fixed SecureIbex to 0 for want of check bits
// no memory stored; the check bits are stored now, and soc_mem_ecc.v's
// header says how.
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
// HARDEN -- THE CODE, AND THE TWO ARMS OF THIS FILE
// ---------------------------------------------------------------------
//
// HARDEN = 0 is the model every document from docs/39 to docs/66 ran:
// one 32-bit register array, a read one cycle after the grant, byte
// enables applied straight to the word. It is kept byte for byte in the
// g_plain arm below, because it is the baseline docs/67 measures
// against and because sw/tests/test_soc_synthesis_guards.py's rule is
// that a baseline comes from the SAME file with the protection off.
//
// HARDEN = 1 is the g_ecc arm: the same 32-bit `mem` array -- named and
// indexed exactly as before, so every hierarchical read a testbench
// makes of it still reads the DATA -- beside a `chk` array holding the
// check field of each row, and soc_mem_ecc between the two and the bus.
// The two arrays together are one row of the macro build's 64-bit (or
// 39-bit) storage, and a testbench that injects an upset may land it in
// either.
//
// THE ROM'S CHECK BITS ARE COMPUTED AT LOAD, BY THE FROZEN ENCODER. A
// ROM built out of SRAM holds whatever loaded it, and in simulation
// what loads it is $readmemh; the check field is then derived word by
// word by driving each word through an instance of hw/rtl/secded_enc.v
// inside the same initial block. No H matrix is copied into this file
// and none could be: soc_mem_ecc.v's decoder is what will read those
// bits back, so a check field that came from anywhere but the
// repository's one encoder would make every fetch trap. In the macro
// build the ROM's contents AND its check bits are whatever writes the
// macro before the core leaves reset -- docs/67 section 8 is what that
// is -- and the same rule holds: they are loaded together or not at all.
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
    parameter         RDREG     = 1'b0,
    // The code and the scrubber. See the header and soc_mem_ecc.v.
    parameter integer HARDEN    = 1,
    // Byte codewords (the RAM) or one word codeword (the ROM).
    parameter         ECC_BYTE  = 1'b1
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
    output wire        err_o,

    // The scrubber's control and the codec's reports; soc_mem_ecc.v.
    // Unused and tied off at HARDEN = 0.
    input  wire        scrub_en_i,
    input  wire [15:0] scrub_ivl_i,
    output wire        sec_o,
    output wire        rd_o,
    output wire        ded_o,
    output wire [31:0] evt_addr_o
);

  // The data array, in BOTH arms and at module scope, so that
  // `dut.u_ram.mem[i]` reads a 32-bit data word whatever HARDEN is.
  reg [31:0] mem [0:WORDS-1];

  // Zeroed rather than left x. A fetch from uninitialised memory should
  // decode as an illegal instruction and trap, not propagate x through
  // the core and make every downstream signal unreadable.
  integer i;
  initial begin
    for (i = 0; i < WORDS; i = i + 1) mem[i] = 32'h0000_0000;
    if (INIT_FILE != "") $readmemh(INIT_FILE, mem, INIT_WORD);
  end

  generate
  // ===================================================================
  // HARDEN = 0: the model of record from docs/39 to docs/66, unchanged.
  // ===================================================================
  if (!HARDEN) begin : g_plain

    assign gnt_o = req_i;

    // Word index. The fabric has already decoded the region, so the low
    // bits are what selects inside it; the modulo makes an out-of-range
    // index alias rather than read out of bounds, which matters only if
    // the region size and WORDS disagree. soc_top.v derives WORDS from
    // the generated map so they cannot.
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
    // The same two names appear in hw/soc/rtl/soc_mem_sram.v and in
    // soc_mem_ecc.v, which carries them for the HARDEN = 1 arm.
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

    assign sec_o      = 1'b0;
    assign rd_o       = 1'b0;
    assign ded_o      = 1'b0;
    assign evt_addr_o = 32'h0;
    wire _unused_scrub = &{1'b0, scrub_en_i, scrub_ivl_i, 1'b0};

  end

  // ===================================================================
  // HARDEN = 1: the codec and the scrubber over the same array.
  // ===================================================================
  if (HARDEN) begin : g_ecc

    localparam integer RW = ECC_BYTE ? 64 : 39;
    localparam integer CW = RW - 32;
    localparam integer AW = $clog2(WORDS);

    // The check field of every row, beside the data.
    reg [CW-1:0] chk [0:WORDS-1];

    // The row port, in the macro's shape: a read lands in q_* at the
    // edge and holds until the next read, a write changes q_* not at
    // all. SRAM_1P_behavioral_bm_bist does exactly this.
    wire          row_en, row_we;
    wire [AW-1:0] row_addr;
    wire [RW-1:0] row_din, row_bm;
    reg  [31:0]   q_mem;
    reg  [CW-1:0] q_chk;

    soc_mem_ecc #(
        .WORDS    (WORDS),
        .RO       (RO),
        .HARDEN   (1),
        .ECC_BYTE (ECC_BYTE),
        .RDREG    (RDREG),
        .RW       (RW)
    ) u_ecc (
        .clk_i (clk_i), .rst_ni (rst_ni),
        .req_i (req_i), .addr_i (addr_i), .we_i (we_i), .be_i (be_i),
        .wdata_i (wdata_i), .gnt_o (gnt_o), .rvalid_o (rvalid_o),
        .rdata_o (rdata_o), .err_o (err_o),
        .row_en_o (row_en), .row_we_o (row_we), .row_addr_o (row_addr),
        .row_din_o (row_din), .row_bm_o (row_bm),
        .row_dout_i ({q_chk, q_mem}),
        .scrub_en_i (scrub_en_i), .scrub_ivl_i (scrub_ivl_i),
        .sec_o (sec_o), .rd_o (rd_o), .ded_o (ded_o),
        .evt_addr_o (evt_addr_o)
    );

    always @(posedge clk_i) begin
      if (row_en) begin
        if (row_we) begin
          mem[row_addr] <= (mem[row_addr] & ~row_bm[31:0])
                         | (row_din[31:0] & row_bm[31:0]);
          chk[row_addr] <= (chk[row_addr] & ~row_bm[RW-1:32])
                         | (row_din[RW-1:32] & row_bm[RW-1:32]);
        end else begin
          q_mem <= mem[row_addr];
          q_chk <= chk[row_addr];
        end
      end
    end

    // The check field at load. Every row's data is driven through ONE
    // instance of the frozen encoder inside the initial block, with a
    // zero-delay step between the drive and the sample so the
    // continuous assignments inside the encoder have settled. An
    // all-zero word encodes to an all-zero check field, so the rows
    // $readmemh did not fill are valid codewords too.
    //
    // For the byte code each lane is encoded on its own, exactly as
    // soc_mem_ecc.v's g_enc_byte does; for the word code the whole word
    // is, and the eighth check bit is dropped as it is there.
    reg  [63:0] init_din;
    wire [7:0]  init_chk;
    wire [71:0] init_code_unused;
    secded_enc u_init_enc (
        .data_in   (init_din),
        .check_out (init_chk),
        .code_out  (init_code_unused)
    );

    // A CORRECTED observation of one word, for a testbench that reads
    // the memory hierarchically. `mem[i]` is the raw data field and a
    // bench that compares it against an expected value is comparing
    // storage the codec has not yet decoded -- which is not what an
    // operator reading the word over the bus would see, and which turned
    // six corrected upsets in a published word into six phantom traps
    // in the first run of docs/67's campaign. `observe` decodes lane by
    // lane through the frozen decoder, exactly as a bus read would,
    // and never touches the row port or the scrubber. Simulation only:
    // this file is never synthesised.
    reg  [63:0] obs_row;
    wire [31:0] obs_word;
    genvar ol;
    for (ol = 0; ol < 4; ol = ol + 1) begin : g_obs
      wire [63:0] d64;
      wire [7:0]  syn_unused;
      wire        sec_unused, ded_unused;
      secded_dec u_obs_dec (
          .code_in  ({obs_row[32+8*ol +: 8], 56'h0, obs_row[8*ol +: 8]}),
          .data_out (d64),
          .syndrome (syn_unused),
          .sec      (sec_unused),
          .ded      (ded_unused)
      );
      assign obs_word[8*ol +: 8] = d64[7:0];
    end

    task observe;
      input  integer      idx;
      output [31:0]       word;
      begin
        if (ECC_BYTE) begin
          obs_row = {chk[idx], mem[idx]};
          #0;
          word = obs_word;
        end else begin
          word = mem[idx];
        end
      end
    endtask

    // Two initial blocks and not one with a runtime `if`, because the
    // part-select widths differ between the two layouts and a branch
    // that never runs still has to elaborate against the other's `chk`.
    integer w, l;
    if (ECC_BYTE) begin : g_init_byte
      initial begin
        init_din = 64'h0;
        q_mem    = 32'h0;
        q_chk    = {CW{1'b0}};
        // After the module-scope initial block has loaded `mem`: both
        // run at time zero, and this one is ordered behind it by the #0.
        #0;
        for (w = 0; w < WORDS; w = w + 1)
          for (l = 0; l < 4; l = l + 1) begin
            init_din = {56'h0, mem[w][8*l +: 8]};
            #0;
            chk[w][8*l +: 8] = init_chk;
          end
      end
    end
    if (!ECC_BYTE) begin : g_init_word
      initial begin
        init_din = 64'h0;
        q_mem    = 32'h0;
        q_chk    = {CW{1'b0}};
        #0;
        for (w = 0; w < WORDS; w = w + 1) begin
          init_din = {32'h0, mem[w]};
          #0;
          chk[w] = init_chk[6:0];
        end
      end
    end

  end
  endgenerate

endmodule
