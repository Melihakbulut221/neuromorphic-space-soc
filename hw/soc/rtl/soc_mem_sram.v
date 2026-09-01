// soc_mem, built on IHP SG13G2 RM_IHPSG13 SRAM macros.
//
// THIS FILE DECLARES A MODULE CALLED `soc_mem`. It is a drop-in
// replacement for hw/soc/rtl/soc_mem.v -- same module name, same
// parameters, same ports in name, width, direction and order -- and
// exactly one of the two files may be read into any given build.
// sw/tests/test_soc_synthesis_guards.py asserts the two port lists are
// equal, because a width a replacement gets wrong does not stop
// elaboration.
//
//   soc_mem.v        the BEHAVIOURAL model. Simulation, cocotb, formal,
//                    gate-level co-simulation. It infers a register
//                    array and its area is a property of the model.
//   soc_mem_sram.v   THIS FILE. Place-and-route and any timing or area
//                    number that is meant to be about the part. It
//                    instantiates real macros and cannot be simulated
//                    without the PDK's behavioural macro models.
//
// docs/45 section 3 measured what the behavioural model costs if it is
// taken literally: the two instances soc_top.v creates are 589,824
// registers, and `proc; opt_clean` on the RAM alone takes 1,693.86 s and
// 2.77 GB. docs/45 section 9 item 2 asked for this file. docs/47 is it.
//
// ---------------------------------------------------------------------
// THE MAPPING, AND WHY THESE MACROS
//
// The PDK ships 27 RM_IHPSG13 macros. Two properties decide which are
// usable here and both are measured in docs/47 section 4:
//
//   1. BYTE WRITES. soc_mem's contract carries be_i[3:0] and Ibex emits
//      `sb` and `sh`. A macro without the per-bit write mask A_BM
//      cannot serve it without a read-modify-write, which is a protocol
//      change and not a wrapper. That excludes RM_IHPSG13_1P_8192x32_c4
//      -- the densest 32-bit part in the library, and the only one that
//      would have built 64 KiB in two instances.
//
//   2. THE READ ARC. A_CLK -> A_DOUT at slow_1p08V_125C is a function
//      of macro DEPTH and it spans 5.2678 ns (256 and 512 words) to
//      9.6611 ns (8192 words) across the family. At a 20 ns period that
//      is between 26 % and 48 % of the cycle spent inside the macro
//      before the first gate of the read return path.
//
// The two builds below are the choices docs/47 section 4.3 makes and
// the alternatives it tabulates:
//
//   WORDS = 16384  (64 KiB RAM, SOC_SIZE_RAM)
//     4 x RM_IHPSG13_1P_2048x64_c2_bm_bist
//     1,966,536 um2, the smallest 64 KiB build in the library.
//     Read arc 9.2941 ns at slow. 4 macros of 784.48 x 626.70.
//
//   WORDS = 2048   (8 KiB boot ROM, SOC_SIZE_ROM)
//     2 x RM_IHPSG13_1P_1024x32_c2_bm_bist
//     280,366 um2. Read arc 7.5512 ns at slow. 416.64 x 336.46 each.
//     There is no 2048x32 part; two 1024x32 is the exact fit.
//
// A 64-bit macro holds two 32-bit words per row, so the word index
// splits into a bank, a row and a HALF, and the half selects both the
// write mask and the half of A_DOUT that is returned. The half select
// is registered alongside the bank select, so the read multiplexer is
// driven from state and not from this cycle's address.
//
// ---------------------------------------------------------------------
// WHAT THIS DOES NOT DO, stated here rather than in a document, because
// a reader of this file is the person it matters to:
//
//   * NO ECC AND NO SCRUBBING. soc_mem.v's header already says this of
//     the behavioural model and it is not fixed by making the storage
//     real. A macro word is 32 bits of data and nothing else. docs/38
//     section 7 and soc_top.v's own header carry the consequence:
//     SecureIbex is fixed at 0 because MemECC would require seven SECDED
//     check bits per word that no memory in this design stores. Adding
//     them means 39-bit rows, which means a different macro geometry
//     and a different area, and it is not done here.
//
//   * NO INITIAL CONTENTS. INIT_FILE and INIT_WORD are accepted so that
//     soc_top.v's instantiation is unchanged, and they are IGNORED. An
//     SRAM macro powers up undefined. The behavioural ROM is loaded by
//     $readmemh; a ROM built out of SRAM is not a ROM until something
//     writes it, and this design contains nothing that can. docs/47
//     section 4.4 states this as an open architectural item -- it needs
//     either a mask ROM, a serial load path, or a boot from an external
//     interface -- and it is not a layout question.
//
//   * NO BIST. Every macro's A_BIST_* port set is parked: A_BIST_EN is
//     tied low and the rest are tied to zero, which is what makes the
//     functional port set the one that is timed. The macros carry a
//     BIST interface and this design does not drive it.
//
//   * READ-DURING-WRITE returns the macro's behaviour and not the
//     behavioural model's. soc_mem.v returns the OLD word on a write
//     cycle; here A_REN is low during a write, so A_DOUT holds. No
//     master in this SoC consumes rdata on a write response, so the
//     difference is not observable through soc_bus's protocol, but it
//     is a difference and it is why this file must not be substituted
//     into a simulation.

`timescale 1ns / 1ps

module soc_mem #(
    parameter integer WORDS     = 4096,
    parameter         RO        = 1'b0,
    parameter         INIT_FILE = "",
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
    output wire [31:0] rdata_o,
    output reg         err_o
);

  // Protocol, unchanged from soc_mem.v: soc_bus.v rules S1-S4, always
  // ready, fixed one-cycle response, in order by construction.
  assign gnt_o = req_i;

  wire write_attempt = req_i && we_i;
  wire do_write      = write_attempt && !RO;

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      rvalid_o <= 1'b0;
      err_o    <= 1'b0;
    end else begin
      rvalid_o <= req_i;
      err_o    <= write_attempt && RO;
    end
  end

  // Byte enables expanded to the macro's per-BIT mask. A_BM[i] = 1
  // writes bit i (the PDK's SRAM_1P_behavioral_bm_bist declares exactly
  // that), so a byte enable becomes eight ones.
  wire [31:0] bm32 = {{8{be_i[3]}}, {8{be_i[2]}}, {8{be_i[1]}}, {8{be_i[0]}}};

  // Tied high on every macro. 16 of the 27 RM_IHPSG13 datasheets call
  // this MANDATORY and the other 11 call it recommended; the parts used
  // here are in the second group and it is tied anyway, because the
  // difference between the two groups is not a difference anybody
  // should have to remember. docs/12 section 6.4e.
  wire dly = 1'b1;

  // THE GENERATE BRANCHES ARE THREE INDEPENDENT `if`s AND NOT AN
  // if/else-if CHAIN, and that is a physical-design requirement rather
  // than a style. An `else if` nests the second branch inside an
  // ANONYMOUS generate block, so the ROM's macro instances come out of
  // Yosys named `u_rom.genblk1.g_rom_1024x32.u_b0` -- a name whose
  // middle component is invented by the tool and can change with it.
  // hw/soc/pnr/config.json has to name every macro instance exactly,
  // under MACROS.<macro>.instances, or the run dies at
  // OpenROAD.CheckMacroInstances. Flat, labelled branches make the
  // instance names a property of this file.
  generate
  // -------------------------------------------------------------------
  // 64 KiB RAM: 4 x RM_IHPSG13_1P_2048x64_c2_bm_bist
  //
  //   widx[13:12] bank        4 banks x 4096 words
  //   widx[11:1]  macro row   2048 rows of 64 bits
  //   widx[0]     half        two 32-bit words per row
  // -------------------------------------------------------------------
  if (WORDS == 16384) begin : g_ram_2048x64

    wire [13:0] widx = addr_i[15:2];
    wire [1:0]  bank = widx[13:12];
    wire [10:0] row  = widx[11:1];
    wire        half = widx[0];

    wire [63:0] din = {wdata_i, wdata_i};
    wire [63:0] bm  = half ? {bm32, 32'h0} : {32'h0, bm32};

    wire [63:0] dout0, dout1, dout2, dout3;

    // The read multiplexer is driven from REGISTERED select, captured
    // on the request that produced the data, and held while req_i is
    // low so that rdata_o holds exactly as soc_mem.v's does.
    reg [1:0] bank_q;
    reg       half_q;
    always @(posedge clk_i or negedge rst_ni)
      if (!rst_ni) begin
        bank_q <= 2'b00;
        half_q <= 1'b0;
      end else if (req_i) begin
        bank_q <= bank;
        half_q <= half;
      end

    reg [63:0] dsel;
    always @(*) begin
      case (bank_q)
        2'd0:    dsel = dout0;
        2'd1:    dsel = dout1;
        2'd2:    dsel = dout2;
        default: dsel = dout3;
      endcase
    end
    assign rdata_o = half_q ? dsel[63:32] : dsel[31:0];

    RM_IHPSG13_1P_2048x64_c2_bm_bist u_b0 (
        .A_CLK(clk_i), .A_MEN(req_i && (bank == 2'd0)),
        .A_WEN(do_write), .A_REN(!do_write),
        .A_ADDR(row), .A_DIN(din), .A_BM(bm), .A_DLY(dly), .A_DOUT(dout0),
        .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
        .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(11'h0),
        .A_BIST_DIN(64'h0), .A_BIST_BM(64'h0));

    RM_IHPSG13_1P_2048x64_c2_bm_bist u_b1 (
        .A_CLK(clk_i), .A_MEN(req_i && (bank == 2'd1)),
        .A_WEN(do_write), .A_REN(!do_write),
        .A_ADDR(row), .A_DIN(din), .A_BM(bm), .A_DLY(dly), .A_DOUT(dout1),
        .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
        .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(11'h0),
        .A_BIST_DIN(64'h0), .A_BIST_BM(64'h0));

    RM_IHPSG13_1P_2048x64_c2_bm_bist u_b2 (
        .A_CLK(clk_i), .A_MEN(req_i && (bank == 2'd2)),
        .A_WEN(do_write), .A_REN(!do_write),
        .A_ADDR(row), .A_DIN(din), .A_BM(bm), .A_DLY(dly), .A_DOUT(dout2),
        .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
        .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(11'h0),
        .A_BIST_DIN(64'h0), .A_BIST_BM(64'h0));

    RM_IHPSG13_1P_2048x64_c2_bm_bist u_b3 (
        .A_CLK(clk_i), .A_MEN(req_i && (bank == 2'd3)),
        .A_WEN(do_write), .A_REN(!do_write),
        .A_ADDR(row), .A_DIN(din), .A_BM(bm), .A_DLY(dly), .A_DOUT(dout3),
        .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
        .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(11'h0),
        .A_BIST_DIN(64'h0), .A_BIST_BM(64'h0));

  // -------------------------------------------------------------------
  // 8 KiB boot ROM: 2 x RM_IHPSG13_1P_1024x32_c2_bm_bist
  //
  //   widx[10]   bank         2 banks x 1024 words
  //   widx[9:0]  macro row    1024 rows of 32 bits
  //
  // RO = 1 makes A_WEN dead, so these are read-only by construction and
  // not only by the err_o answer above. They are also EMPTY: see the
  // header.
  // -------------------------------------------------------------------
  end
  if (WORDS == 2048) begin : g_rom_1024x32

    wire [10:0] widx = addr_i[12:2];
    wire        bank = widx[10];
    wire [9:0]  row  = widx[9:0];

    wire [31:0] dout0, dout1;

    reg bank_q;
    always @(posedge clk_i or negedge rst_ni)
      if (!rst_ni)      bank_q <= 1'b0;
      else if (req_i)   bank_q <= bank;

    assign rdata_o = bank_q ? dout1 : dout0;

    RM_IHPSG13_1P_1024x32_c2_bm_bist u_b0 (
        .A_CLK(clk_i), .A_MEN(req_i && !bank),
        .A_WEN(do_write), .A_REN(!do_write),
        .A_ADDR(row), .A_DIN(wdata_i), .A_BM(bm32), .A_DLY(dly),
        .A_DOUT(dout0),
        .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
        .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(10'h0),
        .A_BIST_DIN(32'h0), .A_BIST_BM(32'h0));

    RM_IHPSG13_1P_1024x32_c2_bm_bist u_b1 (
        .A_CLK(clk_i), .A_MEN(req_i && bank),
        .A_WEN(do_write), .A_REN(!do_write),
        .A_ADDR(row), .A_DIN(wdata_i), .A_BM(bm32), .A_DLY(dly),
        .A_DOUT(dout1),
        .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
        .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(10'h0),
        .A_BIST_DIN(32'h0), .A_BIST_BM(32'h0));

  // -------------------------------------------------------------------
  // Anything else is a mapping that does not exist. Loudly, at
  // elaboration, rather than quietly with a wrong address decode.
  // -------------------------------------------------------------------
  end
  if (WORDS != 16384 && WORDS != 2048) begin : g_unsupported

    // synthesis translate_off
    initial begin
      $display("soc_mem_sram.v: no macro mapping for WORDS=%0d", WORDS);
      $finish;
    end
    // synthesis translate_on
    UNSUPPORTED_SOC_MEM_SRAM_WORDS u_unsupported ();
    assign rdata_o = 32'h0;

  end
  endgenerate

endmodule
