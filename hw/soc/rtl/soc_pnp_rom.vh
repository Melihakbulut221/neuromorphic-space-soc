
// GENERATED FILE - edit regmap/memmap.yaml and run regmap/generate_memmap.py
//
// Body of the device table read multiplexer, textually included
// inside soc_pnp.v. `word_addr` is addr[11:2]. Not guarded with
// `ifndef: it is a case body, not a header, and a guard on a
// body include is a trap in a shared macro namespace.

case (word_addr)
  // ---- master records ----
  10'h000: pnp_data = 32'h0900A020;
  10'h008: pnp_data = 32'h0900B020;
  // ---- slave records ----
  10'h200: pnp_data = 32'h09001020;
  10'h201: pnp_data = 32'h00008000;
  10'h202: pnp_data = 32'h00000001;
  10'h204: pnp_data = 32'h0001FFF2;
  10'h208: pnp_data = 32'h09010020;
  10'h209: pnp_data = 32'h10000000;
  10'h20A: pnp_data = 32'h00000001;
  10'h20C: pnp_data = 32'h1001F002;
  10'h210: pnp_data = 32'h09002020;
  10'h211: pnp_data = 32'h00002000;
  10'h212: pnp_data = 32'h00000001;
  10'h214: pnp_data = 32'hC001FFF2;
  10'h218: pnp_data = 32'h09011020;
  10'h219: pnp_data = 32'h02000000;
  10'h21A: pnp_data = 32'h00000000;
  10'h21C: pnp_data = 32'hD001FE02;
  10'h220: pnp_data = 32'h09012020;
  10'h221: pnp_data = 32'h08000000;
  10'h222: pnp_data = 32'h00000000;
  10'h224: pnp_data = 32'hD801F802;
  10'h228: pnp_data = 32'h09003020;
  10'h229: pnp_data = 32'h00010000;
  10'h22A: pnp_data = 32'h00000001;
  10'h22C: pnp_data = 32'hE000FFF3;
  10'h230: pnp_data = 32'h09004020;
  10'h231: pnp_data = 32'h00400000;
  10'h232: pnp_data = 32'h00000000;
  10'h234: pnp_data = 32'hF800FFC3;
  10'h238: pnp_data = 32'h09005020;
  10'h239: pnp_data = 32'h01000000;
  10'h23A: pnp_data = 32'h00000000;
  10'h23C: pnp_data = 32'hFE00FF03;
  10'h240: pnp_data = 32'h09006020;
  10'h241: pnp_data = 32'h00100000;
  10'h242: pnp_data = 32'h00000001;
  10'h244: pnp_data = 32'hFF90FFF3;
  10'h248: pnp_data = 32'h09007020;
  10'h249: pnp_data = 32'h00001000;
  10'h24A: pnp_data = 32'h00000001;
  10'h24C: pnp_data = 32'hFFF0FFF3;
  // ---- identity and endianness ----
  10'h3FC: pnp_data = 32'h4E530001;
  10'h3FD: pnp_data = 32'h00000001;
  default: pnp_data = 32'h0000_0000;
endcase
