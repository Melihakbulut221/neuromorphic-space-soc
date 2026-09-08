// SPDX-FileCopyrightText: 2026 Hasan Melih Akbulut
// SPDX-License-Identifier: CERN-OHL-W-2.0

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
//   * ECC AND SCRUBBING, as of docs/67, at HARDEN = 1 -- and the reason
//     the RAM is now HALF the macro it was. A 64-bit row holds ONE
//     32-bit word as four (16,8) byte codewords, so 64 KiB of
//     RM_IHPSG13_1P_2048x64 holds 32 KiB of protected words and the
//     map says 32 KiB; the ROM keeps its two 1024x32 data macros and
//     gains a 512x16 check macro per bank for the (39,32) word code.
//     hw/soc/rtl/soc_mem_ecc.v is the codec, the correction, the error
//     response and the scrubber, shared with soc_mem.v; this file only
//     puts macros under its row port. docs/67 section 3 costs the
//     alternatives -- a seventh 2048x64 for check bits at +25.0 % of
//     the macro area with a read-modify-write on every sb and sh, or a
//     4096x16 at +13.1 % with one on every store -- and section 8
//     says what the ROM's check bits are worth on a macro nothing in
//     this design can write. At HARDEN = 0 with WORDS = 8192 the same
//     four macros hold one word per row with no code at all, which is
//     the baseline docs/67 measures the codec against; WORDS = 16384
//     is docs/47's two-words-per-row mapping, kept unchanged.
//
//   * NO INITIAL CONTENTS. INIT_FILE and INIT_WORD are accepted so that
//     soc_top.v's instantiation is unchanged, and they are IGNORED. An
//     SRAM macro powers up undefined. The behavioural ROM is loaded by
//     $readmemh; a ROM built out of SRAM is not a ROM until something
//     writes it, and this design contains nothing that can. docs/47
//     section 4.4 states this as an open architectural item -- it needs
//     either a mask ROM, a serial load path, or a boot from an external
//     interface -- and it is not a layout question. THE ROM'S CHECK
//     MACROS ARE IN THE SAME POSITION: whatever loads the two data
//     macros loads the two check macros, through the same row port and
//     the same encoder, or the first fetch traps. docs/67 section 8.
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
//
// ---------------------------------------------------------------------
// RDREG -- THE RESPONSE REGISTER. THIS FILE IS WHY IT EXISTS.
// ---------------------------------------------------------------------
//
// The read arc above is not a cost that can be optimised: it is the
// vendor's Liberty for a hard macro. docs/47's sign-off decomposes its
// binding path as 1.8834 ns of clock to A_CLK, 9.5277 ns INSIDE the
// macro, and 13.1261 ns of 26 standard-cell stages from A_DOUT to a
// register-file SECDED check bit -- 24.5371 ns of arrival against
// 21.3342 ns required. docs/48 tried floorplan and capacitance, docs/49
// tried logic restructuring, and docs/49 section 11.1 concluded that ONE
// FLIP-FLOP in this file is the only measured mechanism that puts both
// halves inside 20 ns.
//
// RDREG = 1 is that flip-flop, 32 of them, and it is placed AFTER the
// bank and half multiplexers rather than at each macro's A_DOUT. The
// alternative costs 4 x 64 = 256 flip-flops on the RAM to save the two
// multiplexer stages, and docs/50 section 4 measures the multiplexers at
// well inside the 9.9231 ns the first half has spare.
//
// The protocol consequence is one extra cycle of response latency, on
// this slave only, and hw/soc/rtl/soc_mem.v's header states the rest of
// it. The peripherals are not behind a macro and do not pay: RDREG is a
// parameter of this module and the fabric has no stage of its own.

`timescale 1ns / 1ps

module soc_mem #(
    parameter integer WORDS     = 4096,
    parameter         RO        = 1'b0,
    parameter         INIT_FILE = "",
    parameter integer INIT_WORD = 0,
    // One extra response stage. See the header.
    parameter         RDREG     = 1'b0,
    // The code and the scrubber; soc_mem.v and soc_mem_ecc.v.
    parameter integer HARDEN    = 1,
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
    // Unused and tied off in the HARDEN = 0 arms.
    input  wire        scrub_en_i,
    input  wire [15:0] scrub_ivl_i,
    output wire        sec_o,
    output wire        rd_o,
    output wire        ded_o,
    output wire [31:0] evt_addr_o
);

  // ===================================================================
  // WHICH ARMS ELABORATE
  //
  //   WORDS = 16384              docs/47's mapping, two words per 64-bit
  //                              row, no code. HARDEN must be 0.
  //   WORDS = 8192               one word per row through soc_mem_ecc:
  //                              the byte code at HARDEN = 1, the same
  //                              four macros with no code at HARDEN = 0
  //                              (the control docs/67 measures against).
  //   WORDS = 2048, HARDEN = 0   docs/47's ROM, two 1024x32 macros.
  //   WORDS = 2048, HARDEN = 1   the same two, plus one 512x16 check
  //                              macro per bank for the (39,32) code.
  //
  // PLAIN is the pair that keeps docs/47's response logic and instance
  // paths byte for byte; the codec arms take their response from
  // soc_mem_ecc.v and drive the ports from there.
  // ===================================================================
  localparam PLAIN = (WORDS == 16384) || (WORDS == 2048 && HARDEN == 0);

  // The raw read return of the PLAIN arms, driven by whichever of them
  // has a mapping for WORDS and read by g_rsp. Declared at module scope
  // because the arms that drive it and the block that reads it are
  // siblings; the codec arms leave it undriven and unread.
  wire [31:0] rd_raw;

  // The bus write, as the PLAIN arms decode it; the codec arms decode
  // their own inside soc_mem_ecc.
  wire write_attempt = req_i && we_i;
  wire do_write      = write_attempt && !RO;

  generate
  if (PLAIN) begin : g_rsp
    assign sec_o      = 1'b0;
    assign rd_o       = 1'b0;
    assign ded_o      = 1'b0;
    assign evt_addr_o = 32'h0;
    wire _unused_scrub = &{1'b0, scrub_en_i, scrub_ivl_i, 1'b0};

    // Protocol, unchanged from soc_mem.v: soc_bus.v rules S1-S4, always
    // ready, fixed response latency, in order by construction. RDREG
    // changes the latency and nothing else; gnt_o is combinational from
    // req_i in both arms, so this memory still accepts one request per
    // cycle.
    assign gnt_o = req_i;

    reg rv0;
    reg er0;

    always @(posedge clk_i or negedge rst_ni) begin
      if (!rst_ni) begin
        rv0 <= 1'b0;
        er0 <= 1'b0;
      end else begin
        rv0 <= req_i;
        er0 <= write_attempt && RO;
      end
    end

    // ---- the response, with or without the extra stage ------------------
    //
    // The two arm names are soc_mem.v's, deliberately: the compiled-object
    // check in hw/soc/flow/sim_soc.sh and the netlist check in docs/50 look
    // for the same string whichever memory model is in the build.
    if (!RDREG) begin : g_rd1

      assign rvalid_o = rv0;
      assign rdata_o  = rd_raw;
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
          // rv0 is the cycle in which this request's word is on A_DOUT and
          // the bank and half selects captured with the request are
          // driving the multiplexers, so this is the edge that has the
          // word to capture. Gating on it also holds rdata_o between
          // responses, as the unregistered arm's A_DOUT does.
          if (rv0) rd1 <= rd_raw;
        end
      end

      assign rvalid_o = rv1;
      assign rdata_o  = rd1;
      assign err_o    = er1;

    end
  end
  endgenerate

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
    assign rd_raw = half_q ? dsel[63:32] : dsel[31:0];

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
  if (WORDS == 2048 && HARDEN == 0) begin : g_rom_1024x32

    wire [10:0] widx = addr_i[12:2];
    wire        bank = widx[10];
    wire [9:0]  row  = widx[9:0];

    wire [31:0] dout0, dout1;

    reg bank_q;
    always @(posedge clk_i or negedge rst_ni)
      if (!rst_ni)      bank_q <= 1'b0;
      else if (req_i)   bank_q <= bank;

    assign rd_raw = bank_q ? dout1 : dout0;

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

  end

  // -------------------------------------------------------------------
  // 32 KiB of protected RAM: the SAME 4 x RM_IHPSG13_1P_2048x64_c2_bm_bist,
  // one word per row, through soc_mem_ecc.v (docs/67).
  //
  //   row[12:11]  bank        4 banks x 2048 rows
  //   row[10:0]   macro row   2048 rows of 64 bits, one word and its
  //                           four byte-lane check fields each
  //
  // At HARDEN = 0 the codec is absent and the upper 32 bits of every
  // row are never written and never read: the one-word-per-row control
  // against which the codec's own cost is measured.
  // -------------------------------------------------------------------
  if (WORDS == 8192) begin : g_ram_2048x64_ecc

    wire        row_en, row_we;
    wire [12:0] row_addr;
    wire [63:0] row_din, row_bm, row_dout;

    soc_mem_ecc #(
        .WORDS (8192), .RO (RO), .HARDEN (HARDEN), .ECC_BYTE (1'b1),
        .RDREG (RDREG), .RW (64)
    ) u_ecc (
        .clk_i (clk_i), .rst_ni (rst_ni),
        .req_i (req_i), .addr_i (addr_i), .we_i (we_i), .be_i (be_i),
        .wdata_i (wdata_i), .gnt_o (gnt_o), .rvalid_o (rvalid_o),
        .rdata_o (rdata_o), .err_o (err_o),
        .row_en_o (row_en), .row_we_o (row_we), .row_addr_o (row_addr),
        .row_din_o (row_din), .row_bm_o (row_bm), .row_dout_i (row_dout),
        .scrub_en_i (scrub_en_i), .scrub_ivl_i (scrub_ivl_i),
        .sec_o (sec_o), .rd_o (rd_o), .ded_o (ded_o), .evt_addr_o (evt_addr_o)
    );

    wire [1:0]  bank = row_addr[12:11];
    wire [10:0] mrow = row_addr[10:0];
    wire        rden = row_en && !row_we;

    wire [63:0] dout0, dout1, dout2, dout3;

    // The bank select is captured on a READ and held across writes, so
    // the multiplexer follows A_DOUT, which itself holds across a write.
    reg [1:0] bank_q;
    always @(posedge clk_i or negedge rst_ni)
      if (!rst_ni)      bank_q <= 2'b00;
      else if (rden)    bank_q <= bank;

    reg [63:0] dsel;
    always @(*) begin
      case (bank_q)
        2'd0:    dsel = dout0;
        2'd1:    dsel = dout1;
        2'd2:    dsel = dout2;
        default: dsel = dout3;
      endcase
    end
    assign row_dout = dsel;

    RM_IHPSG13_1P_2048x64_c2_bm_bist u_b0 (
        .A_CLK(clk_i), .A_MEN(row_en && (bank == 2'd0)),
        .A_WEN(row_we), .A_REN(!row_we),
        .A_ADDR(mrow), .A_DIN(row_din), .A_BM(row_bm), .A_DLY(dly),
        .A_DOUT(dout0),
        .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
        .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(11'h0),
        .A_BIST_DIN(64'h0), .A_BIST_BM(64'h0));

    RM_IHPSG13_1P_2048x64_c2_bm_bist u_b1 (
        .A_CLK(clk_i), .A_MEN(row_en && (bank == 2'd1)),
        .A_WEN(row_we), .A_REN(!row_we),
        .A_ADDR(mrow), .A_DIN(row_din), .A_BM(row_bm), .A_DLY(dly),
        .A_DOUT(dout1),
        .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
        .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(11'h0),
        .A_BIST_DIN(64'h0), .A_BIST_BM(64'h0));

    RM_IHPSG13_1P_2048x64_c2_bm_bist u_b2 (
        .A_CLK(clk_i), .A_MEN(row_en && (bank == 2'd2)),
        .A_WEN(row_we), .A_REN(!row_we),
        .A_ADDR(mrow), .A_DIN(row_din), .A_BM(row_bm), .A_DLY(dly),
        .A_DOUT(dout2),
        .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
        .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(11'h0),
        .A_BIST_DIN(64'h0), .A_BIST_BM(64'h0));

    RM_IHPSG13_1P_2048x64_c2_bm_bist u_b3 (
        .A_CLK(clk_i), .A_MEN(row_en && (bank == 2'd3)),
        .A_WEN(row_we), .A_REN(!row_we),
        .A_ADDR(mrow), .A_DIN(row_din), .A_BM(row_bm), .A_DLY(dly),
        .A_DOUT(dout3),
        .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
        .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(11'h0),
        .A_BIST_DIN(64'h0), .A_BIST_BM(64'h0));

  end

  // -------------------------------------------------------------------
  // 8 KiB of protected boot ROM: docs/47's 2 x RM_IHPSG13_1P_1024x32 for
  // the words, plus 2 x RM_IHPSG13_1P_512x16_c2_bm_bist for the seven
  // check bits of the (39,32) word code, one per bank (docs/67).
  //
  //   row[10]    bank         2 banks x 1024 words
  //   row[9:0]   macro row    1024 rows of 32 bits in the data macro
  //   row[9]     half         which 7-bit field of the 512x16's 16-bit
  //   row[8:0]   check row    row holds this word's check bits
  //
  // The check macro has 512 rows of 16 bits: rows 0..511 keep their
  // check field in bits [6:0], rows 512..1023 in bits [13:7], selected
  // by row[9]. Bits [15:14] are never written. The ROM is read-only to
  // the bus, so the only writer of all four macros is the scrubber's
  // write-back of a corrected word, through A_BM.
  // -------------------------------------------------------------------
  if (WORDS == 2048 && HARDEN != 0) begin : g_rom_1024x32_ecc

    wire        row_en, row_we;
    wire [10:0] row_addr;
    wire [38:0] row_din, row_bm, row_dout;

    soc_mem_ecc #(
        .WORDS (2048), .RO (RO), .HARDEN (1), .ECC_BYTE (1'b0),
        .RDREG (RDREG), .RW (39)
    ) u_ecc (
        .clk_i (clk_i), .rst_ni (rst_ni),
        .req_i (req_i), .addr_i (addr_i), .we_i (we_i), .be_i (be_i),
        .wdata_i (wdata_i), .gnt_o (gnt_o), .rvalid_o (rvalid_o),
        .rdata_o (rdata_o), .err_o (err_o),
        .row_en_o (row_en), .row_we_o (row_we), .row_addr_o (row_addr),
        .row_din_o (row_din), .row_bm_o (row_bm), .row_dout_i (row_dout),
        .scrub_en_i (scrub_en_i), .scrub_ivl_i (scrub_ivl_i),
        .sec_o (sec_o), .rd_o (rd_o), .ded_o (ded_o), .evt_addr_o (evt_addr_o)
    );

    wire       bank = row_addr[10];
    wire [9:0] mrow = row_addr[9:0];
    wire       half = row_addr[9];
    wire       rden = row_en && !row_we;

    wire [31:0] dout0, dout1;
    wire [15:0] cout0, cout1;
    wire [15:0] cdin = {2'b00, row_din[38:32], row_din[38:32]};
    wire [15:0] cbm  = half ? {2'b00, row_bm[38:32], 7'h00}
                            : {9'h000, row_bm[38:32]};

    reg bank_q, half_q;
    always @(posedge clk_i or negedge rst_ni)
      if (!rst_ni) begin
        bank_q <= 1'b0;
        half_q <= 1'b0;
      end else if (rden) begin
        bank_q <= bank;
        half_q <= half;
      end

    wire [15:0] csel = bank_q ? cout1 : cout0;
    wire [6:0]  chk  = half_q ? csel[13:7] : csel[6:0];
    assign row_dout = {chk, bank_q ? dout1 : dout0};

    RM_IHPSG13_1P_1024x32_c2_bm_bist u_b0 (
        .A_CLK(clk_i), .A_MEN(row_en && !bank),
        .A_WEN(row_we), .A_REN(!row_we),
        .A_ADDR(mrow), .A_DIN(row_din[31:0]), .A_BM(row_bm[31:0]),
        .A_DLY(dly), .A_DOUT(dout0),
        .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
        .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(10'h0),
        .A_BIST_DIN(32'h0), .A_BIST_BM(32'h0));

    RM_IHPSG13_1P_1024x32_c2_bm_bist u_b1 (
        .A_CLK(clk_i), .A_MEN(row_en && bank),
        .A_WEN(row_we), .A_REN(!row_we),
        .A_ADDR(mrow), .A_DIN(row_din[31:0]), .A_BM(row_bm[31:0]),
        .A_DLY(dly), .A_DOUT(dout1),
        .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
        .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(10'h0),
        .A_BIST_DIN(32'h0), .A_BIST_BM(32'h0));

    RM_IHPSG13_1P_512x16_c2_bm_bist u_c0 (
        .A_CLK(clk_i), .A_MEN(row_en && !bank),
        .A_WEN(row_we), .A_REN(!row_we),
        .A_ADDR(mrow[8:0]), .A_DIN(cdin), .A_BM(cbm),
        .A_DLY(dly), .A_DOUT(cout0),
        .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
        .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(9'h0),
        .A_BIST_DIN(16'h0), .A_BIST_BM(16'h0));

    RM_IHPSG13_1P_512x16_c2_bm_bist u_c1 (
        .A_CLK(clk_i), .A_MEN(row_en && bank),
        .A_WEN(row_we), .A_REN(!row_we),
        .A_ADDR(mrow[8:0]), .A_DIN(cdin), .A_BM(cbm),
        .A_DLY(dly), .A_DOUT(cout1),
        .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
        .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(9'h0),
        .A_BIST_DIN(16'h0), .A_BIST_BM(16'h0));

  end

  // -------------------------------------------------------------------
  // Anything else is a mapping that does not exist. Loudly, at
  // elaboration, rather than quietly with a wrong address decode.
  // -------------------------------------------------------------------
  if (!PLAIN && WORDS != 8192 && WORDS != 2048) begin : g_unsupported

    // synthesis translate_off
    initial begin
      $display("soc_mem_sram.v: no macro mapping for WORDS=%0d HARDEN=%0d",
               WORDS, HARDEN);
      $finish;
    end
    // synthesis translate_on
    UNSUPPORTED_SOC_MEM_SRAM_WORDS u_unsupported ();

  end
  endgenerate

endmodule
