// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

// System-bus device table.
//
// A read-only table of device records at the address the memory map
// freezes for it. The record LAYOUT is GRLIB's plug-and-play layout
// (grlib.pdf section 5.3) and the contents come from
// regmap/memmap.yaml through regmap/generate_memmap.py, so the table and
// the map cannot drift: docs/08-gr801-datasheet-notes.md section 4 item
// 2 asked for exactly this generator and this is it.
//
// IT IS NOT AN AMBA AHB PLUG-AND-PLAY TABLE. There is no AHB in this
// SoC. The layout is mirrored because a documented layout is what makes
// a device table readable by something other than its author; the bus
// underneath is this project's own, and
// docs/39-soc-bus-and-memory-map.md section 7 states the claim made and
// the claim not made. A GRLIB tool pointed at this table will parse the
// records and report vendor 0x09 with device codes it does not
// recognise, which is the truthful result.
//
// Cost: the table is sparse -- about a hundred non-zero words in 1024 --
// so it is a case statement with a zero default rather than a memory.
// That synthesises to the constant multiplexer it is, with no storage.
// Whether it stayed that way is measured, not assumed: see
// docs/39-soc-bus-and-memory-map.md section 6.
//
// Protocol: soc_bus.v rules S1-S4. Always ready, one-cycle response.
// Writes are answered with err rather than ignored.

`timescale 1ns / 1ps

module soc_pnp (
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

  // be_i and wdata_i are part of the slave port and are unused here: the
  // table is read-only, so a write is refused before its payload
  // matters. Named so a lint pass reports nothing and a reader is not
  // left wondering whether the omission was deliberate.
  wire _unused = &{1'b0, be_i, wdata_i, 1'b0};

  assign gnt_o = req_i;

  wire [9:0] word_addr = addr_i[11:2];

  reg [31:0] pnp_data;
  always @(*) begin
`include "soc_pnp_rom.vh"
  end

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      rvalid_o <= 1'b0;
      rdata_o  <= 32'h0;
      err_o    <= 1'b0;
    end else begin
      rvalid_o <= req_i;
      err_o    <= req_i && we_i;
      rdata_o  <= pnp_data;
    end
  end

endmodule
