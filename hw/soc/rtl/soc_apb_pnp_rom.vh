
// Peripheral bus device table, two words per slot. `word_addr` is
// PADDR[11:2] inside the table's own 4 KiB slot. Not guarded,
// for the same reason soc_pnp_rom.vh is not.

case (word_addr)
  10'h000: apb_pnp_data = 32'h0900C022;
  10'h001: apb_pnp_data = 32'h0000FF01;
  10'h002: apb_pnp_data = 32'h0900C023;
  10'h003: apb_pnp_data = 32'h0100FF01;
  10'h004: apb_pnp_data = 32'h0901A024;
  10'h005: apb_pnp_data = 32'h0200FF01;
  10'h006: apb_pnp_data = 32'h09011028;
  10'h007: apb_pnp_data = 32'h0800FF01;
  10'h008: apb_pnp_data = 32'h0901102C;
  10'h009: apb_pnp_data = 32'h0900FF01;
  10'h00A: apb_pnp_data = 32'h0901F030;
  10'h00B: apb_pnp_data = 32'h0D00FF01;
  10'h00C: apb_pnp_data = 32'h090FE032;
  10'h00D: apb_pnp_data = 32'h1100FF01;
  10'h00E: apb_pnp_data = 32'h0902D033;
  10'h00F: apb_pnp_data = 32'h1200FF01;
  10'h010: apb_pnp_data = 32'h09028034;
  10'h011: apb_pnp_data = 32'h1300FF01;
  10'h012: apb_pnp_data = 32'h09045035;
  10'h013: apb_pnp_data = 32'h1400FF01;
  10'h014: apb_pnp_data = 32'h09052036;
  10'h015: apb_pnp_data = 32'h1500FF01;
  10'h016: apb_pnp_data = 32'h09057037;
  10'h017: apb_pnp_data = 32'h1600FF01;
  10'h018: apb_pnp_data = 32'h09087020;
  10'h019: apb_pnp_data = 32'h1700FF01;
  10'h01A: apb_pnp_data = 32'h0902C020;
  10'h01B: apb_pnp_data = 32'h1800FF01;
  10'h01C: apb_pnp_data = 32'h09013038;
  10'h01D: apb_pnp_data = 32'h1900FF01;
  10'h01E: apb_pnp_data = 32'h09000020;
  10'h01F: apb_pnp_data = 32'hFF00FF01;
  default: apb_pnp_data = 32'h0000_0000;
endcase
