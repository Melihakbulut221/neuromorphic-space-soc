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
// one-cycle response, in order by construction.
//
// RO = 1 makes it a ROM: a write is not performed and is answered with
// err, so a stray store into the boot ROM is a store access fault rather
// than a silent no-op.

`timescale 1ns / 1ps

module soc_mem #(
    parameter integer WORDS     = 4096,
    parameter         RO        = 1'b0,
    parameter         INIT_FILE = "",
    // Byte offset of the first word of INIT_FILE within this memory.
    parameter integer INIT_WORD = 0
) (
    input  wire        clk_i,
    input  wire        rst_ni,

    input  wire        req_i,
    input  wire [31:0] addr_i,
    input  wire        we_i,
    input  wire [3:0]  be_i,
    input  wire [31:0] wdata_i,
    output wire        gnt_o,
    output reg         rvalid_o,
    output reg  [31:0] rdata_o,
    output reg         err_o
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

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      rvalid_o <= 1'b0;
      rdata_o  <= 32'h0;
      err_o    <= 1'b0;
    end else begin
      rvalid_o <= req_i;
      err_o    <= write_attempt && RO;
      if (req_i) begin
        rdata_o <= mem[widx];
        if (do_write) begin
          if (be_i[0]) mem[widx][7:0]   <= wdata_i[7:0];
          if (be_i[1]) mem[widx][15:8]  <= wdata_i[15:8];
          if (be_i[2]) mem[widx][23:16] <= wdata_i[23:16];
          if (be_i[3]) mem[widx][31:24] <= wdata_i[31:24];
        end
      end
    end
  end

endmodule
