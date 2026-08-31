// Peripheral bus device table.
//
// The APB-side counterpart of soc_pnp.v: two words per peripheral slot
// (identification word and one bank address register) in a table at the
// slot the memory map reserves for it, which is GRLIB's bridge base +
// 0xFF000 convention (grlib.pdf section 5.3, adopted by
// docs/08-gr801-datasheet-notes.md section 3 row 3).
//
// The bank address register on the peripheral side compares address bits
// [19:8], so a 4 KiB slot is expressed EXACTLY here, unlike the system
// side where the 1 MiB field granularity forces three regions to be
// rounded up. docs/memmap-soc.md section 4 names those three.
//
// Contents are generated from regmap/memmap.yaml. Read-only; a write is
// accepted and discarded, which is the documented behaviour for
// unoccupied space behind a GRLIB bridge and is what the surrounding
// bridge does everywhere else.

`timescale 1ns / 1ps

module soc_apb_pnp (
    input  wire        psel_i,
    input  wire        penable_i,
    input  wire [11:0] paddr_i,
    input  wire        pwrite_i,
    input  wire [31:0] pwdata_i,
    output reg  [31:0] prdata_o,
    output wire        pready_o,
    output wire        pslverr_o
);

  // The table is combinational and read-only, so the handshake inputs
  // and the write payload do not reach any logic. Named rather than left
  // dangling so a lint pass reports nothing.
  wire _unused = &{1'b0, psel_i, penable_i, pwrite_i, pwdata_i, 1'b0};

  assign pready_o  = 1'b1;
  assign pslverr_o = 1'b0;

  wire [9:0] word_addr = paddr_i[11:2];

  reg [31:0] apb_pnp_data;
  always @(*) begin
`include "soc_apb_pnp_rom.vh"
  end

  always @(*) prdata_o = apb_pnp_data;

endmodule
